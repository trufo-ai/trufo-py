# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Key pair generation utilities."""

from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from trufo.crypto.algorithms import ALG_TO_CURVE, SigningAlgorithm


def generate_keypair(algorithm: SigningAlgorithm) -> tuple[bytes, bytes]:
    """Generate a private/public key pair for the given algorithm.

    Args:
        algorithm: Signing algorithm determining key type and curve.

    Returns:
        Tuple of (private_key_pem, public_key_pem) as bytes.

    Raises:
        ValueError: If the algorithm is unsupported for key generation.
    """
    if algorithm == SigningAlgorithm.EDDSA:
        private_key = ed25519.Ed25519PrivateKey.generate()
    elif algorithm in ALG_TO_CURVE:
        private_key = ec.generate_private_key(ALG_TO_CURVE[algorithm])
    else:
        raise ValueError(f"Unsupported algorithm for key generation: {algorithm.alg_name}")

    private_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    public_pem = private_key.public_key().public_bytes(
        Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
    )

    return private_pem, public_pem
