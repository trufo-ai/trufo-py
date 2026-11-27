# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Key generation, signing algorithm inference, and keys held in a KMS."""

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
)

from trufo import generate_keypair
from trufo.crypt.algorithms import ALG_TO_HASH, SigningAlgorithm, infer_signing_algorithm


def _public_pem(private_key):
    return private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)


@pytest.mark.parametrize(
    "algorithm, key_type, curve",
    [
        (SigningAlgorithm.ES256, ec.EllipticCurvePrivateKey, "secp256r1"),
        (SigningAlgorithm.ES384, ec.EllipticCurvePrivateKey, "secp384r1"),
        (SigningAlgorithm.ES512, ec.EllipticCurvePrivateKey, "secp521r1"),
        (SigningAlgorithm.EDDSA, ed25519.Ed25519PrivateKey, None),
    ],
)
def test_generate_keypair(algorithm, key_type, curve):
    private_pem, public_pem = generate_keypair(algorithm)
    # the private key in PKCS8, the public key in SubjectPublicKeyInfo
    assert private_pem.startswith(b"-----BEGIN PRIVATE KEY-----\n")
    assert public_pem.startswith(b"-----BEGIN PUBLIC KEY-----\n")
    private_key = load_pem_private_key(private_pem, password=None)
    assert isinstance(private_key, key_type)
    assert getattr(getattr(private_key, "curve", None), "name", None) == curve
    assert _public_pem(private_key) == public_pem


@pytest.mark.parametrize(
    "private_key, expected",
    [
        (ec.generate_private_key(ec.SECP256R1()), SigningAlgorithm.ES256),
        (ec.generate_private_key(ec.SECP384R1()), SigningAlgorithm.ES384),
        (ec.generate_private_key(ec.SECP521R1()), SigningAlgorithm.ES512),
        (ed25519.Ed25519PrivateKey.generate(), SigningAlgorithm.EDDSA),
        (ec.generate_private_key(ec.SECP256K1()), "Unsupported EC curve: secp256k1"),
        (rsa.generate_private_key(65537, 2048), "Unsupported key type: RSAPublicKey"),
    ],
    ids=["p256", "p384", "p521", "ed25519", "secp256k1", "rsa"],
)
def test_infer_signing_algorithm(private_key, expected):
    if isinstance(expected, SigningAlgorithm):
        assert infer_signing_algorithm(_public_pem(private_key)) is expected
    else:
        with pytest.raises(ValueError, match=expected):
            infer_signing_algorithm(_public_pem(private_key))


def test_infer_signing_algorithm_needs_a_pem():
    with pytest.raises(ValueError):
        infer_signing_algorithm(b"not a pem")


@pytest.mark.parametrize("provider", ["aws-kms", "gcp-kms"])
@pytest.mark.parametrize("algorithm", [SigningAlgorithm.ES256, SigningAlgorithm.ES384])
def test_kms_keys(kms_keys, provider, algorithm):
    private_pem, public_pem = generate_keypair(algorithm)
    key = kms_keys[provider](private_pem)
    curve_hash = ALG_TO_HASH[algorithm]

    assert _public_pem(key) == public_pem
    # the fake client checks that the KMS signs with the curve's hash
    key.public_key().verify(key.sign(b"data", ec.ECDSA(curve_hash)), b"data", ec.ECDSA(curve_hash))
    other_hash = hashes.SHA384() if algorithm is SigningAlgorithm.ES256 else hashes.SHA256()
    with pytest.raises(ValueError, match=f"ECDSA and {curve_hash.name} only"):
        key.sign(b"data", ec.ECDSA(other_hash))
    with pytest.raises(NotImplementedError, match="cannot be exported"):
        key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    with pytest.raises(NotImplementedError, match="cannot be exported"):
        key.private_numbers()
    with pytest.raises(NotImplementedError, match="key exchange"):
        key.exchange(ec.ECDH(), key.public_key())
    with pytest.raises(ValueError, match="P-256 or P-384"):
        kms_keys[provider](generate_keypair(SigningAlgorithm.ES512)[0])
