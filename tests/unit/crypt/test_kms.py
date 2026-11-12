# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for trufo.crypt.kms."""

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from trufo.crypt.algorithms import SigningAlgorithm
from trufo.crypt.keygen import generate_keypair


class TestKMSPrivateKey:
    """KMS keys refuse unsupported curves and mismatched hashes."""

    def test_kms_key_refuses_unsupported_curve_and_hash(self, kms_keys):
        with pytest.raises(ValueError, match="P-256 or P-384"):
            kms_keys["aws-kms"](generate_keypair(SigningAlgorithm.ES512)[0])
        key = kms_keys["aws-kms"](generate_keypair(SigningAlgorithm.ES256)[0])
        with pytest.raises(ValueError, match="sha256"):
            key.sign(b"data", ec.ECDSA(hashes.SHA384()))
