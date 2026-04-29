# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for api/tca/certs_cawg_interim.py — CAWG interim certificate procurement."""

from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)

from trufo.api.tca.certs_cawg_interim import _request_cawg_interim_csr_jwt, request_cawg_interim_cert


_MODULE = "trufo.api.tca.certs_cawg_interim"


def _ec_p256_pem() -> bytes:
    """Generate a fresh EC P-256 private key in PKCS8 PEM form."""
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())


# --- _request_cawg_interim_csr_jwt ---


class TestRequestCawgInterimCsrJwt:
    """_request_cawg_interim_csr_jwt POSTs to the RA and returns the token."""

    def test_returns_csr_jwt(self):
        mock_client = MagicMock()
        mock_client.make_request.return_value = {"csr_jwt": "eyJ.fake.token"}

        result = _request_cawg_interim_csr_jwt(mock_client, None)

        assert result == "eyJ.fake.token"

    def test_calls_correct_endpoint(self):
        mock_client = MagicMock()
        mock_client.make_request.return_value = {"csr_jwt": "x"}

        _request_cawg_interim_csr_jwt(mock_client, None)

        path = mock_client.make_request.call_args[0][0]
        assert path == "/ra/cawg-interim/csr-jwt"

    def test_omits_validity_days_when_none(self):
        """When validity_days is None, the body should not include the key."""
        mock_client = MagicMock()
        mock_client.make_request.return_value = {"csr_jwt": "x"}

        _request_cawg_interim_csr_jwt(mock_client, None)

        body = mock_client.make_request.call_args[0][1]
        assert "validity_days" not in body

    def test_passes_validity_days_when_set(self):
        mock_client = MagicMock()
        mock_client.make_request.return_value = {"csr_jwt": "x"}

        _request_cawg_interim_csr_jwt(mock_client, 30)

        body = mock_client.make_request.call_args[0][1]
        assert body["validity_days"] == 30


# --- request_cawg_interim_cert ---


class TestRequestCawgInterimCert:
    """request_cawg_interim_cert orchestrates RA -> EST -> PEM chain."""

    @patch(f"{_MODULE}.extract_cert_chain")
    @patch(f"{_MODULE}.est_enroll")
    def test_returns_extract_cert_chain_output(self, mock_enroll, mock_extract):
        mock_client = MagicMock()
        mock_client.make_request.return_value = {"csr_jwt": "csr-jwt-x"}
        mock_enroll.return_value = b"pkcs7-b64"
        mock_extract.return_value = b"-----BEGIN CERTIFICATE-----\n..."

        result = request_cawg_interim_cert(mock_client, _ec_p256_pem())

        assert result == b"-----BEGIN CERTIFICATE-----\n..."

    @patch(f"{_MODULE}.extract_cert_chain")
    @patch(f"{_MODULE}.est_enroll")
    def test_uses_cawg_interim_leaf_type(self, mock_enroll, _mock_extract):
        mock_client = MagicMock()
        mock_client.make_request.return_value = {"csr_jwt": "x"}
        mock_enroll.return_value = b"x"

        request_cawg_interim_cert(mock_client, _ec_p256_pem())

        # est_enroll(csr_jwt, csr_der, leaf_type_value)
        _, _, leaf_type_value = mock_enroll.call_args[0]
        assert leaf_type_value == "cawg-interim"

    @patch(f"{_MODULE}.extract_cert_chain")
    @patch(f"{_MODULE}.est_enroll")
    def test_passes_validity_days_to_ra(self, mock_enroll, _mock_extract):
        mock_client = MagicMock()
        mock_client.make_request.return_value = {"csr_jwt": "x"}
        mock_enroll.return_value = b"x"

        request_cawg_interim_cert(mock_client, _ec_p256_pem(), validity_days=30)

        body = mock_client.make_request.call_args[0][1]
        assert body["validity_days"] == 30

    @patch(f"{_MODULE}.extract_cert_chain")
    @patch(f"{_MODULE}.est_enroll")
    def test_csr_jwt_threaded_through_to_est(self, mock_enroll, _mock_extract):
        """The CSR JWT returned by the RA should be the auth token to EST."""
        mock_client = MagicMock()
        mock_client.make_request.return_value = {"csr_jwt": "RA-issued-csr-jwt"}
        mock_enroll.return_value = b"x"

        request_cawg_interim_cert(mock_client, _ec_p256_pem())

        csr_jwt_arg, _csr_der, _leaf_type = mock_enroll.call_args[0]
        assert csr_jwt_arg == "RA-issued-csr-jwt"
