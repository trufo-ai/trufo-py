# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for crypto/keygen.py."""

import pytest
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)

from trufo.crypto.algorithms import SigningAlgorithm
from trufo.crypto.keygen import generate_keypair


class TestGenerateKeypair:
    """generate_keypair returns valid PEM key pairs."""

    @pytest.mark.parametrize(
        "algorithm,key_class",
        [
            (SigningAlgorithm.ES256, ec.EllipticCurvePrivateKey),
            (SigningAlgorithm.ES384, ec.EllipticCurvePrivateKey),
            (SigningAlgorithm.ES512, ec.EllipticCurvePrivateKey),
            (SigningAlgorithm.EDDSA, ed25519.Ed25519PrivateKey),
        ],
    )
    def test_returns_pem_bytes(self, algorithm, key_class):
        priv, pub = generate_keypair(algorithm)
        assert isinstance(priv, bytes)
        assert isinstance(pub, bytes)
        assert priv.startswith(b"-----BEGIN PRIVATE KEY-----")
        assert pub.startswith(b"-----BEGIN PUBLIC KEY-----")

    @pytest.mark.parametrize(
        "algorithm,key_class",
        [
            (SigningAlgorithm.ES256, ec.EllipticCurvePrivateKey),
            (SigningAlgorithm.ES384, ec.EllipticCurvePrivateKey),
            (SigningAlgorithm.ES512, ec.EllipticCurvePrivateKey),
            (SigningAlgorithm.EDDSA, ed25519.Ed25519PrivateKey),
        ],
    )
    def test_private_key_loadable(self, algorithm, key_class):
        priv, _ = generate_keypair(algorithm)
        key = load_pem_private_key(priv, password=None)
        assert isinstance(key, key_class)

    @pytest.mark.parametrize(
        "algorithm",
        [
            SigningAlgorithm.ES256,
            SigningAlgorithm.ES384,
            SigningAlgorithm.ES512,
            SigningAlgorithm.EDDSA,
        ],
    )
    def test_public_key_loadable(self, algorithm):
        _, pub = generate_keypair(algorithm)
        key = load_pem_public_key(pub)
        assert key is not None

    def test_es256_correct_curve(self):
        priv, _ = generate_keypair(SigningAlgorithm.ES256)
        key = load_pem_private_key(priv, password=None)
        assert key.curve.name == "secp256r1"

    def test_es384_correct_curve(self):
        priv, _ = generate_keypair(SigningAlgorithm.ES384)
        key = load_pem_private_key(priv, password=None)
        assert key.curve.name == "secp384r1"

    def test_private_and_public_match(self):
        priv, pub = generate_keypair(SigningAlgorithm.ES256)
        private_key = load_pem_private_key(priv, password=None)
        public_key = load_pem_public_key(pub)
        # compare serialized public key bytes
        assert private_key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ) == public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

    def test_generates_unique_keys(self):
        priv1, _ = generate_keypair(SigningAlgorithm.ES256)
        priv2, _ = generate_keypair(SigningAlgorithm.ES256)
        assert priv1 != priv2
