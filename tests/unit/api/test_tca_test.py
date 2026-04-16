# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for api/tca/test_cert.py — test certificate enrollment helpers."""

from unittest.mock import patch

import jwt as pyjwt
import pytest

from trufo.api.tca.tca_utils import TEST_HMAC_SECRET, LeafType
from trufo.api.tca.test_cert import (
    _build_test_c2pa_csr_jwt,
    _build_test_cawg_csr_jwt,
    request_c2pa_test_cert,
    request_cawg_test_cert,
)


class TestBuildTestCsrJwt:
    """Test CSR JWT builders produce HS256 JWTs signed with the test secret."""

    def test_jwt_decodable_with_test_secret(self):
        jwt_str = _build_test_c2pa_csr_jwt(LeafType.C2PA_L1_TEST, "TestOrg", "TestCN")

        payload = pyjwt.decode(jwt_str, TEST_HMAC_SECRET, algorithms=["HS256"], audience="tca-est")
        assert payload["leaf_type"] == "c2pa-l1-test"
        assert payload["distinguished_name"]["O"] == "TestOrg"
        assert payload["distinguished_name"]["CN"] == "TestCN"

    def test_jwt_has_required_claims(self):
        jwt_str = _build_test_c2pa_csr_jwt(LeafType.C2PA_L2_TEST, "Org", "CN")

        payload = pyjwt.decode(jwt_str, TEST_HMAC_SECRET, algorithms=["HS256"], audience="tca-est")
        for claim in ("iss", "sub", "aud", "jti", "iat", "exp", "record_id", "instance_id"):
            assert claim in payload, f"Missing claim: {claim}"

    def test_cawg_jwt_has_empty_linkage_ids(self):
        jwt_str = _build_test_cawg_csr_jwt("Org", "CN")

        payload = pyjwt.decode(jwt_str, TEST_HMAC_SECRET, algorithms=["HS256"], audience="tca-est")
        assert payload["leaf_type"] == LeafType.CAWG_INTERIM_TEST.value
        assert payload["record_id"] == ""
        assert payload["instance_id"] == ""


class TestRequestC2paTestCert:
    """request_c2pa_test_cert orchestrates test cert enrollment."""

    def test_rejects_non_test_leaf_type(self):
        with pytest.raises(ValueError, match="must be a C2PA test type"):
            request_c2pa_test_cert("Org", "CN", b"private-key", leaf_type=LeafType.C2PA_L1)

    @patch("trufo.api.tca.test_cert.extract_cert_chain")
    @patch("trufo.api.tca.test_cert.est_enroll")
    @patch("trufo.api.tca.test_cert.build_csr")
    def test_returns_cert_chain(self, mock_csr, mock_enroll, mock_extract_chain):
        mock_csr.return_value = b"fake-csr-der"
        mock_enroll.return_value = b"fake-pkcs7"
        mock_extract_chain.return_value = b"chain-pem"

        result = request_c2pa_test_cert("MyOrg", "MyCN", b"fake-key-pem")

        assert result == b"chain-pem"

    @patch("trufo.api.tca.test_cert.extract_cert_chain")
    @patch("trufo.api.tca.test_cert.est_enroll")
    @patch("trufo.api.tca.test_cert.build_csr")
    def test_passes_leaf_type_to_est_enroll(self, mock_csr, mock_enroll, mock_extract_chain):
        mock_csr.return_value = b"c"
        mock_enroll.return_value = b"e"
        mock_extract_chain.return_value = b"ch"

        request_c2pa_test_cert("O", "CN", b"k", leaf_type=LeafType.C2PA_L2_TEST)

        est_call_args = mock_enroll.call_args[0]
        assert est_call_args[2] == "c2pa-l2-test"


class TestRequestCawgTestCert:
    """request_cawg_test_cert orchestrates CAWG interim test enrollment."""

    @patch("trufo.api.tca.test_cert.extract_cert_chain")
    @patch("trufo.api.tca.test_cert.est_enroll")
    @patch("trufo.api.tca.test_cert.build_csr")
    def test_uses_cawg_leaf_type(self, mock_csr, mock_enroll, mock_extract_chain):
        mock_csr.return_value = b"c"
        mock_enroll.return_value = b"e"
        mock_extract_chain.return_value = b"chain"

        result = request_cawg_test_cert("Org", "CN", b"k")

        assert result == b"chain"
        assert mock_enroll.call_args[0][2] == "cawg-interim-test"
