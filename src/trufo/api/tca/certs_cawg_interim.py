# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
CAWG interim certificate procurement via Trufo RA and TCA.

Org-scoped enrollment: the CAWG interim cert identifies the calling
organization itself (no gproduct/instance/credential hierarchy). The
RA endpoint is gated on the ``request_cawg_interim_cert`` permission and an
active CAWG_CERT_ORGANIZATION subscription, so the caller must be
authenticated as an org admin (or owner) via TrufoSession.
"""

from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec

from trufo.api.endpoints import RA_CAWG_INTERIM_CSR_JWT
from trufo.api.session import TrufoSession
from trufo.api.tca.tca_utils import LeafType, build_csr, est_enroll, extract_cert_chain


# --- internal: CSR JWT request ---


def _request_cawg_interim_csr_jwt(client: TrufoSession, validity_days: int | None) -> str:
    """Request a CAWG interim CSR JWT from the Trufo RA.

    Corresponds to: POST /ra/cawg-interim/csr-jwt.

    Args:
        client: Authenticated TrufoSession.
        validity_days: Requested validity in days. ``None`` lets the
            server use its default.

    Returns:
        The CSR JWT string.

    Raises:
        RuntimeError: If the RA returns a non-200 status (raised by
            ``TrufoSession.make_request``).
    """
    body: dict = {}
    if validity_days is not None:
        body["validity_days"] = validity_days
    data = client.make_request(RA_CAWG_INTERIM_CSR_JWT, body)
    return data["csr_jwt"]


# --- public: end-to-end enrollment ---


def request_cawg_interim_cert(
    client: TrufoSession,
    private_key_signer: str | Path | bytes | ec.EllipticCurvePrivateKey,
    validity_days: int | None = None,
) -> bytes:
    """Run the full CAWG interim certificate enrollment pipeline.

    Pipeline: CSR JWT (from RA) → EST simpleenroll (CA) → PEM chain.

    The caller must be authenticated as an org admin (or owner) of an
    organization with an approved Organization Validation (OV) and an
    active ``cawg_cert_organization`` subscription.

    Args:
        client: Authenticated TrufoSession (Bearer JWT).
        private_key_signer: Leaf private key — PEM ``bytes``, a
            filesystem path (``str``/``Path``), or an
            ``ec.EllipticCurvePrivateKey`` (e.g. an AWS KMS adapter).
            The CA enforces the allowed key algorithms (currently
            EC P-256 / P-384).
        validity_days: Requested validity in days. Must be in
            ``[1, 366]``. ``None`` lets the server use its default
            (366).

    Returns:
        PEM bytes for the certificate chain (leaf + intermediates,
        self-signed root excluded).

    Raises:
        RuntimeError: If the RA request, EST enrollment, or PKCS#7
            parsing fails.
    """
    csr_jwt = _request_cawg_interim_csr_jwt(client, validity_days)
    csr_der = build_csr(private_key_signer)
    pkcs7_b64 = est_enroll(csr_jwt, csr_der, LeafType.CAWG_INTERIM.value)
    return extract_cert_chain(pkcs7_b64)
