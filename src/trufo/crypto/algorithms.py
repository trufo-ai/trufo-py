# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Signing algorithm definitions."""

from enum import Enum

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.serialization import load_pem_public_key


class SigningAlgorithm(Enum):
    """Supported signing algorithms (JWA identifiers)."""

    ES256 = ("ES256", "SHA256")
    ES384 = ("ES384", "SHA384")
    ES512 = ("ES512", "SHA512")
    EDDSA = ("EdDSA", None)

    def __init__(self, alg_name: str, hash_alg: str | None):
        self.alg_name = alg_name
        self.hash_alg = hash_alg


ALG_TO_CURVE = {
    SigningAlgorithm.ES256: ec.SECP256R1(),
    SigningAlgorithm.ES384: ec.SECP384R1(),
    SigningAlgorithm.ES512: ec.SECP521R1(),
}

ALG_TO_HASH: dict[SigningAlgorithm, hashes.HashAlgorithm | None] = {
    SigningAlgorithm.ES256: hashes.SHA256(),
    SigningAlgorithm.ES384: hashes.SHA384(),
    SigningAlgorithm.ES512: hashes.SHA512(),
    SigningAlgorithm.EDDSA: None,
}


def infer_signing_algorithm(public_key_pem: bytes) -> SigningAlgorithm:
    """Infer the signing algorithm from a PEM-encoded public key.

    Args:
        public_key_pem: PEM-encoded public key bytes.

    Returns:
        The matching SigningAlgorithm enum member.

    Raises:
        ValueError: If the key type or EC curve is unsupported.
    """
    key = load_pem_public_key(public_key_pem)

    if isinstance(key, ec.EllipticCurvePublicKey):
        curve_name = key.curve.name
        for alg, curve in ALG_TO_CURVE.items():
            if curve.name == curve_name:
                return alg
        raise ValueError(f"Unsupported EC curve: {curve_name}")

    if isinstance(key, ed25519.Ed25519PublicKey):
        return SigningAlgorithm.EDDSA

    raise ValueError(f"Unsupported key type: {type(key).__name__}")
