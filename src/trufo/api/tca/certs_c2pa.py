# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""C2PA certificate procurement via Trufo RA and TCA."""

import logging
import time
from pathlib import Path

import jwt as pyjwt
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from trufo.api.auth import extract_detail
from trufo.api.endpoints import (
    GP_CREDENTIAL_REGISTER,
    GP_INSTANCE_CREATE,
    RA_CSR_JWT,
    TRUFO_API_URL,
)
from trufo.api.session import TrufoSession
from trufo.api.tca.tca_utils import LeafType, build_csr, est_enroll, extract_cert_chain
from trufo.crypto.algorithms import infer_signing_algorithm

logger = logging.getLogger(__name__)


# --- generator product instance / credential ---


def create_instance(client: TrufoSession, gp_id: str, name: str) -> str:
    """Create a generator product instance.

    Corresponds to: POST /gproduct/instance/create
    Requires: authenticated session (Bearer JWT), product must have PV approved.

    Args:
        client: Authenticated TrufoSession.
        gp_id: Generator product ID.
        name: Human-readable instance name.

    Returns:
        The new gpi_id.
    """
    data = client.make_request(
        GP_INSTANCE_CREATE,
        {
            "gp_id": gp_id,
            "name": name,
        },
    )
    return data["gpi_id"]


def register_credential(
    client: TrufoSession,
    gpi_id: str,
    label: str,
    key_algorithm: str,
    public_key_pem: str,
) -> str:
    """Register an instance credential (public key).

    Corresponds to: POST /gproduct/instance/credential/register
    Requires: authenticated session (Bearer JWT), admin+ in org.
    Accepted key_algorithm values: "ES256" (EC P-256) or "EdDSA" (Ed25519).

    Args:
        client: Authenticated TrufoSession.
        gpi_id: Instance ID.
        label: Human-readable label.
        key_algorithm: JWA algorithm identifier ("ES256" or "EdDSA").
        public_key_pem: PEM-encoded public key.

    Returns:
        The new gpic_id.
    """
    data = client.make_request(
        GP_CREDENTIAL_REGISTER,
        {
            "gpi_id": gpi_id,
            "public_key_pem": public_key_pem,
            "key_algorithm": key_algorithm,
            "label": label,
        },
    )
    return data["gpic_id"]


# --- production certificate enrollment ---


def _build_gpic_assertion(
    gpi_id: str,
    gpic_id: str,
    instance_key_pem: str,
    algorithm: str,
) -> str:
    """Build a GPIC assertion JWT signed with the instance private key.

    The assertion proves the caller controls the registered instance
    credential.  Claims: ``iss`` = *gpi_id*, ``sub`` = *gpic_id*,
    ``aud`` = ``"trufo-ra"``, valid for 60 s.

    Args:
        gpi_id: Generator product instance ID (``"gpi_..."``)
        gpic_id: Instance credential ID (``"gpic_..."``)
        instance_key_pem: PEM-encoded instance private key.
        algorithm: JWA algorithm name (e.g. ``"ES256"``).

    Returns:
        Compact-serialized signed JWT string.
    """
    now = int(time.time())
    payload = {
        "iss": gpi_id,
        "sub": gpic_id,
        "aud": "trufo-ra",
        "iat": now,
        "exp": now + 60,
    }
    return pyjwt.encode(payload, instance_key_pem, algorithm=algorithm)


def _request_c2pa_csr_jwt(
    gpic_assertion: str,
    leaf_type: LeafType,
    validity_days: int | None = None,
) -> str:
    """Request a CSR JWT from the Registration Authority.

    Corresponds to: POST /ra/c2pa/csr-jwt.

    Args:
        gpic_assertion: Signed GPIC assertion JWT.
        leaf_type: Certificate type to request.
        validity_days: Requested validity in days.  If ``None``, the
            server uses its default for the leaf type.

    Returns:
        The CSR JWT string.

    Raises:
        RuntimeError: If the RA returns a non-200 status.
    """
    body: dict = {
        "client_assertion": gpic_assertion,
        "leaf_type": leaf_type.value,
    }
    if validity_days is not None:
        body["validity_days"] = validity_days

    # RA authenticates via client_assertion in the body, not Bearer JWT
    resp = requests.post(
        f"{TRUFO_API_URL}{RA_CSR_JWT}",
        headers={"Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    if resp.status_code != 200:
        detail = extract_detail(resp)
        raise RuntimeError(f"CSR JWT request failed ({resp.status_code}): {detail}")

    return resp.json()["csr_jwt"]


def request_c2pa_cert(
    gpi_id: str,
    gpic_id: str,
    instance_key_pem: str,
    private_key_signer: str | Path | bytes | ec.EllipticCurvePrivateKey,
    leaf_type: LeafType = LeafType.C2PA_L1,
    validity_days: int | None = None,
) -> bytes:
    """Run the full C2PA certificate enrollment pipeline.

    Pipeline: GPIC assertion → CSR JWT (via RA) → EST simpleenroll
    (via TCA) → PEM certificate chain.

    Args:
        gpi_id: Instance ID (e.g. ``"gpi_..."``)
        gpic_id: Credential ID (e.g. ``"gpic_..."``)
        instance_key_pem: Instance private key PEM (signs the GPIC
            assertion).
        private_key_signer: Leaf private key — PEM ``bytes``, a
            filesystem path (``str`` / ``Path``), or an
            ``ec.EllipticCurvePrivateKey`` (e.g. AWS KMS adapter).
        leaf_type: Certificate type (default: ``C2PA_L1``).
        validity_days: Requested validity in days.  ``None`` lets the
            server decide.

    Returns:
        PEM bytes for the certificate chain (leaf + intermediates,
        self-signed root excluded).
    """
    # 1. infer instance key algorithm for JWT signing
    instance_key_bytes = (
        instance_key_pem.encode() if isinstance(instance_key_pem, str) else instance_key_pem
    )
    instance_alg = infer_signing_algorithm(
        serialization.load_pem_private_key(instance_key_bytes, password=None)
        .public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )

    # 2. build GPIC assertion, request CSR JWT
    assertion = _build_gpic_assertion(gpi_id, gpic_id, instance_key_pem, instance_alg.alg_name)
    csr_jwt = _request_c2pa_csr_jwt(assertion, leaf_type, validity_days)

    # 3. build CSR with leaf signing key
    csr_der = build_csr(private_key_signer)

    # 4. EST enrollment
    pkcs7_b64 = est_enroll(csr_jwt, csr_der, leaf_type.value)

    # 5. extract certs
    cert_chain_pem = extract_cert_chain(pkcs7_b64)
    return cert_chain_pem
