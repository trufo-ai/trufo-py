# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared test fixtures for trufo-py tests."""

from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_pem_private_key,
)

from trufo.crypt.kms import AWSKMSPrivateKey, GCPKMSPrivateKey

# signing hash by key size, as the KMS key spec fixes it
_HASHES = {256: hashes.SHA256(), 384: hashes.SHA384()}


class _FakeAWSKMSClient:
    """boto3 KMS client stand-in that signs with a local EC key."""

    def __init__(self, private_pem: bytes):
        self._key = load_pem_private_key(private_pem, password=None)

    def get_public_key(self, KeyId):
        der = self._key.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        return {"PublicKey": der}

    def sign(self, KeyId, Message, MessageType, SigningAlgorithm):
        assert (MessageType, SigningAlgorithm) == ("RAW", f"ECDSA_SHA_{self._key.key_size}")
        return {"Signature": self._key.sign(Message, ec.ECDSA(_HASHES[self._key.key_size]))}


class _FakeGCPKMSClient:
    """Cloud KMS client stand-in that signs with a local EC key."""

    def __init__(self, private_pem: bytes):
        self._key = load_pem_private_key(private_pem, password=None)

    def get_public_key(self, request):
        pem = self._key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        return SimpleNamespace(pem=pem.decode())

    def asymmetric_sign(self, request):
        ((digest_name, digest),) = request["digest"].items()
        assert digest_name == f"sha{self._key.key_size}"
        prehashed = ec.ECDSA(Prehashed(_HASHES[self._key.key_size]))
        return SimpleNamespace(signature=self._key.sign(digest, prehashed))


@pytest.fixture
def kms_keys():
    """Factories wrapping a local EC private key PEM in each KMS key class, on a fake client."""
    return {
        "aws-kms": lambda pem: AWSKMSPrivateKey(_FakeAWSKMSClient(pem), "key-id"),
        "gcp-kms": lambda pem: GCPKMSPrivateKey(_FakeGCPKMSClient(pem), "key-version-name"),
    }
