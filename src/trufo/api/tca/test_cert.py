# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Test certificate enrollment helpers for Trufo TCA.

Provides test-only enrollment for C2PA and CAWG interim profiles.
"""

import time
from pathlib import Path

import jwt as pyjwt
from cryptography.hazmat.primitives.asymmetric import ec
from uuid_utils import uuid7

from trufo.api.tca.tca_utils import (
    TEST_HMAC_SECRET,
    LeafType,
    build_csr,
    est_enroll,
    extract_cert_chain,
)


def _build_test_c2pa_csr_jwt(
    leaf_type: LeafType,
    org_name: str,
    common_name: str,
) -> str:
    """Build a C2PA test CSR JWT signed with the public test HMAC secret.

    Args:
        leaf_type: Must be ``C2PA_L1_TEST`` or ``C2PA_L2_TEST``.
        org_name: Organization name for the certificate subject (O).
        common_name: Common name for the certificate subject (CN).

    Returns:
        Compact-serialized HS256 JWT string.

    Raises:
        ValueError: If *leaf_type* is not a C2PA test type.
    """
    if leaf_type not in (LeafType.C2PA_L1_TEST, LeafType.C2PA_L2_TEST):
        raise ValueError(f"leaf_type must be a C2PA test type, got {leaf_type.value}")

    now = int(time.time())
    payload = {
        "iss": "trufo",
        "sub": "test-account",
        "aud": "tca-est",
        "jti": str(uuid7()),
        "iat": now,
        "exp": now + 300,
        "leaf_type": leaf_type.value,
        "distinguished_name": {
            "O": org_name,
            "CN": common_name,
        },
        "record_id": str(uuid7()),
        "instance_id": f"gpi_{uuid7()}",
    }
    return pyjwt.encode(payload, TEST_HMAC_SECRET, algorithm="HS256")


def request_c2pa_test_cert(
    org_name: str,
    common_name: str,
    private_key_signer: str | Path | bytes | ec.EllipticCurvePrivateKey,
    leaf_type: LeafType = LeafType.C2PA_L1_TEST,
) -> bytes:
    """Obtain a test C2PA certificate via the test EST flow.

    No account authentication is required — the CSR JWT is signed with
    the publicly known test HMAC secret.

    Args:
        org_name: Organization name for the certificate subject.
        common_name: Common name for the certificate subject.
        private_key_signer: Leaf private key (PEM bytes, path, or
            ``ec.EllipticCurvePrivateKey``).
        leaf_type: Test leaf type (default: ``C2PA_L1_TEST``).

    Returns:
        PEM certificate chain bytes.
    """
    csr_jwt = _build_test_c2pa_csr_jwt(leaf_type, org_name, common_name)
    csr_der = build_csr(private_key_signer)
    pkcs7_b64 = est_enroll(csr_jwt, csr_der, leaf_type.value)
    cert_chain_pem = extract_cert_chain(pkcs7_b64)
    return cert_chain_pem


def _build_test_cawg_csr_jwt(
    org_name: str,
    common_name: str,
) -> str:
    """Build a CAWG interim test CSR JWT signed with the public test HMAC secret.

    Args:
        org_name: Organization name for the certificate subject (O).
        common_name: Common name for the certificate subject (CN).

    Returns:
        Compact-serialized HS256 JWT string.
    """
    now = int(time.time())
    payload = {
        "iss": "trufo",
        "sub": "test-account",
        "aud": "tca-est",
        "jti": str(uuid7()),
        "iat": now,
        "exp": now + 300,
        "leaf_type": LeafType.CAWG_INTERIM_TEST.value,
        "distinguished_name": {
            "O": org_name,
            "CN": common_name,
        },
        "record_id": "",
        "instance_id": "",
    }
    return pyjwt.encode(payload, TEST_HMAC_SECRET, algorithm="HS256")


def request_cawg_test_cert(
    org_name: str,
    common_name: str,
    private_key_signer: str | Path | bytes | ec.EllipticCurvePrivateKey,
) -> bytes:
    """Obtain a test CAWG interim certificate via the test EST flow.

    No account authentication is required — the CSR JWT is signed with
    the publicly known test HMAC secret.

    Args:
        org_name: Organization name for the certificate subject.
        common_name: Common name for the certificate subject.
        private_key_signer: Leaf private key (PEM bytes, path, or
            ``ec.EllipticCurvePrivateKey``).

    Returns:
        PEM certificate chain bytes.
    """
    csr_jwt = _build_test_cawg_csr_jwt(org_name, common_name)
    csr_der = build_csr(private_key_signer)
    pkcs7_b64 = est_enroll(csr_jwt, csr_der, LeafType.CAWG_INTERIM_TEST.value)
    cert_chain_pem = extract_cert_chain(pkcs7_b64)
    return cert_chain_pem
