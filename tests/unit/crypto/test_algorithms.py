# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for crypto/algorithms.py."""

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from trufo.crypto.algorithms import (
    ALG_TO_CURVE,
    ALG_TO_HASH,
    SigningAlgorithm,
    infer_signing_algorithm,
)


class TestSigningAlgorithm:
    """SigningAlgorithm enum properties."""

    def test_es256_alg_name(self):
        assert SigningAlgorithm.ES256.alg_name == "ES256"

    def test_es384_alg_name(self):
        assert SigningAlgorithm.ES384.alg_name == "ES384"

    def test_es512_alg_name(self):
        assert SigningAlgorithm.ES512.alg_name == "ES512"

    def test_eddsa_alg_name(self):
        assert SigningAlgorithm.EDDSA.alg_name == "EdDSA"

    def test_eddsa_hash_alg_is_none(self):
        assert SigningAlgorithm.EDDSA.hash_alg is None

    def test_ec_algorithms_have_hash_alg(self):
        for alg in (SigningAlgorithm.ES256, SigningAlgorithm.ES384, SigningAlgorithm.ES512):
            assert alg.hash_alg is not None


class TestAlgToCurve:
    """ALG_TO_CURVE maps EC algorithms to correct curves."""

    def test_es256_curve(self):
        assert isinstance(ALG_TO_CURVE[SigningAlgorithm.ES256], ec.SECP256R1)

    def test_es384_curve(self):
        assert isinstance(ALG_TO_CURVE[SigningAlgorithm.ES384], ec.SECP384R1)

    def test_es512_curve(self):
        assert isinstance(ALG_TO_CURVE[SigningAlgorithm.ES512], ec.SECP521R1)

    def test_eddsa_not_in_curve_map(self):
        assert SigningAlgorithm.EDDSA not in ALG_TO_CURVE


class TestAlgToHash:
    """ALG_TO_HASH maps algorithms to hash functions."""

    def test_es256_hash(self):
        assert isinstance(ALG_TO_HASH[SigningAlgorithm.ES256], hashes.SHA256)

    def test_es384_hash(self):
        assert isinstance(ALG_TO_HASH[SigningAlgorithm.ES384], hashes.SHA384)

    def test_es512_hash(self):
        assert isinstance(ALG_TO_HASH[SigningAlgorithm.ES512], hashes.SHA512)

    def test_eddsa_hash_is_none(self):
        assert ALG_TO_HASH[SigningAlgorithm.EDDSA] is None


class TestInferSigningAlgorithm:
    """infer_signing_algorithm from public key PEM."""

    def test_infer_es256(self):
        key = ec.generate_private_key(ec.SECP256R1())
        pub_pem = key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        assert infer_signing_algorithm(pub_pem) == SigningAlgorithm.ES256

    def test_infer_es384(self):
        key = ec.generate_private_key(ec.SECP384R1())
        pub_pem = key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        assert infer_signing_algorithm(pub_pem) == SigningAlgorithm.ES384

    def test_infer_es512(self):
        key = ec.generate_private_key(ec.SECP521R1())
        pub_pem = key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        assert infer_signing_algorithm(pub_pem) == SigningAlgorithm.ES512

    def test_infer_eddsa(self):
        key = ed25519.Ed25519PrivateKey.generate()
        pub_pem = key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        assert infer_signing_algorithm(pub_pem) == SigningAlgorithm.EDDSA

    def test_invalid_key_type_raises(self):
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(65537, 2048)
        pub_pem = key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        with pytest.raises(ValueError, match="Unsupported key type"):
            infer_signing_algorithm(pub_pem)

    def test_invalid_pem_raises(self):
        with pytest.raises(Exception):
            infer_signing_algorithm(b"not a pem")
