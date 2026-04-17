# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""EC private-key adapter backed by AWS KMS signing."""

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from trufo.crypto.awskms.awskms_helper import aws_key_spec_map


class EllipticCurvePrivateKeyAwsKms(ec.EllipticCurvePrivateKey):
    """Minimal EC private key interface backed by AWS KMS."""

    def __init__(self, kms_client, key_id: str):
        self._kms_client = kms_client
        self._key_id = key_id

        describe_response = self._kms_client.describe_key(KeyId=self._key_id)
        key_spec = describe_response["KeyMetadata"]["KeySpec"]
        _, self._signing_algorithm = aws_key_spec_map(key_spec)

        key_response = self._kms_client.get_public_key(KeyId=self._key_id)
        public_key_der = key_response["PublicKey"]

        public_key = serialization.load_der_public_key(public_key_der)
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            raise ValueError(f"KMS key {self._key_id} must be an EC key")

        self._public_key = public_key

    @property
    def curve(self) -> ec.EllipticCurve:
        return self._public_key.curve

    @property
    def key_size(self) -> int:
        return self._public_key.key_size

    def public_key(self) -> ec.EllipticCurvePublicKey:
        return self._public_key

    def sign(self, data: bytes, _signature_algorithm: ec.ECDSA) -> bytes:
        # KMS determines the signing algorithm from key metadata, not the caller
        response = self._kms_client.sign(
            KeyId=self._key_id,
            Message=data,
            MessageType="RAW",
            SigningAlgorithm=self._signing_algorithm,
        )
        return response["Signature"]

    def exchange(
        self,
        algorithm: ec.ECDH,
        peer_public_key: ec.EllipticCurvePublicKey,
    ) -> bytes:
        raise NotImplementedError("AWS KMS signer does not support ECDH exchange.")

    def private_numbers(self) -> ec.EllipticCurvePrivateNumbers:
        raise NotImplementedError("AWS KMS signer does not expose private numbers.")

    def private_bytes(self, encoding, format, encryption_algorithm):
        raise NotImplementedError("AWS KMS signer cannot export private key bytes.")

    def __copy__(self):
        return EllipticCurvePrivateKeyAwsKms(
            kms_client=self._kms_client,
            key_id=self._key_id,
        )

    def __deepcopy__(self, memo=None):
        return self.__copy__()
