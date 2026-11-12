# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Private keys held in AWS KMS or Google Cloud KMS.

Each class is an ``ec.EllipticCurvePrivateKey`` that signs in the KMS, so the private key
never leaves it. Pass one as the instance key or the leaf key when requesting a
certificate. The caller supplies a configured KMS client. EC P-256 and P-384 keys are
supported.
"""

import hashlib

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_der_public_key,
    load_pem_public_key,
)

# the curve fixes the signing hash; sign() refuses any other
_CURVE_HASHES = {"secp256r1": hashes.SHA256, "secp384r1": hashes.SHA384}
_AWS_SIGNING_ALGORITHMS = {hashes.SHA256: "ECDSA_SHA_256", hashes.SHA384: "ECDSA_SHA_384"}


class _KMSPrivateKey(ec.EllipticCurvePrivateKey):
    """EC private key held in a KMS: it signs, but cannot be exported."""

    def __init__(self, public_key):
        if not (
            isinstance(public_key, ec.EllipticCurvePublicKey)
            and public_key.curve.name in _CURVE_HASHES
        ):
            raise ValueError("KMS key must be EC P-256 or P-384.")
        self._public_key = public_key
        self._hash = _CURVE_HASHES[public_key.curve.name]

    @property
    def curve(self) -> ec.EllipticCurve:
        return self._public_key.curve

    @property
    def key_size(self) -> int:
        return self._public_key.key_size

    @property
    def public_key_pem(self) -> str:
        """Public key as SubjectPublicKeyInfo PEM, the form ``register_credential`` takes."""
        return self._public_key.public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ).decode()

    def public_key(self) -> ec.EllipticCurvePublicKey:
        return self._public_key

    def sign(self, data: bytes, signature_algorithm: ec.EllipticCurveSignatureAlgorithm) -> bytes:
        """Sign *data* in the KMS with ECDSA and the hash the key's curve fixes."""
        if not (
            isinstance(signature_algorithm, ec.ECDSA)
            and isinstance(signature_algorithm.algorithm, self._hash)
        ):
            raise ValueError(f"KMS key signs with ECDSA and {self._hash.name} only.")
        return self._kms_sign(data)

    def _kms_sign(self, data: bytes) -> bytes:
        """Sign *data* in the KMS with the hash the key's curve fixes."""
        raise NotImplementedError

    def exchange(self, algorithm, peer_public_key):
        raise NotImplementedError("KMS keys do not support key exchange.")

    def private_numbers(self):
        raise NotImplementedError("KMS private keys cannot be exported.")

    def private_bytes(self, encoding, format, encryption_algorithm):
        raise NotImplementedError("KMS private keys cannot be exported.")

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


class AWSKMSPrivateKey(_KMSPrivateKey):
    """EC private key held in AWS KMS.

    The key spec must be ``ECC_NIST_P256`` or ``ECC_NIST_P384``.

    Args:
        client: boto3 KMS client, e.g. ``boto3.client("kms")``.
        key_id: Key ID, key ARN, alias name or alias ARN.
    """

    def __init__(self, client, key_id: str):
        self._client = client
        self._key_id = key_id
        super().__init__(load_der_public_key(client.get_public_key(KeyId=key_id)["PublicKey"]))

    def _kms_sign(self, data: bytes) -> bytes:
        """Sign *data* in AWS KMS."""
        response = self._client.sign(
            KeyId=self._key_id,
            Message=data,
            MessageType="RAW",
            SigningAlgorithm=_AWS_SIGNING_ALGORITHMS[self._hash],
        )
        return response["Signature"]


class GCPKMSPrivateKey(_KMSPrivateKey):
    """EC private key held in Google Cloud KMS.

    The key algorithm must be ``EC_SIGN_P256_SHA256`` or ``EC_SIGN_P384_SHA384``.

    Args:
        client: Cloud KMS client, e.g. ``kms.KeyManagementServiceClient()``.
        key_version_name: Key version resource name
            (``projects/.../cryptoKeys/.../cryptoKeyVersions/N``).
    """

    def __init__(self, client, key_version_name: str):
        self._client = client
        self._key_version_name = key_version_name
        public_key = client.get_public_key(request={"name": key_version_name})
        super().__init__(load_pem_public_key(public_key.pem.encode()))

    def _kms_sign(self, data: bytes) -> bytes:
        """Hash *data* and sign the digest in Cloud KMS."""
        digest = hashlib.new(self._hash.name, data).digest()
        response = self._client.asymmetric_sign(
            request={"name": self._key_version_name, "digest": {self._hash.name: digest}}
        )
        return response.signature
