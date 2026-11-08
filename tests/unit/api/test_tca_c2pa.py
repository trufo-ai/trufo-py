# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for api/tca/c2pa_cert.py — C2PA certificate procurement."""

from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from trufo import request_c2pa_cert_test
from trufo.api.tca.certs_c2pa import (
    _build_gpic_assertion,
    create_instance,
    register_credential,
    request_c2pa_cert,
)
from trufo.crypt.tca_certs import LeafType

_MODULE = "trufo.api.tca.certs_c2pa"


def _ec_p256_pem() -> bytes:
    """Generate a fresh EC P-256 private key in PKCS8 PEM form."""
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())


# --- GP operations (mocked session) ---


class TestCreateInstance:
    """create_instance calls session.make_request and returns gpi_id."""

    def test_returns_gpi_id(self):
        mock_client = MagicMock()
        mock_client.make_request.return_value = {"gpi_id": "gpi_abc123"}

        result = create_instance(mock_client, "gp_test", "my-instance")

        assert result == "gpi_abc123"
        mock_client.make_request.assert_called_once()

    def test_passes_correct_body(self):
        mock_client = MagicMock()
        mock_client.make_request.return_value = {"gpi_id": "gpi_x"}

        create_instance(mock_client, "gp_42", "inst-name")

        call_args = mock_client.make_request.call_args
        body = call_args[0][1]
        assert body["gp_id"] == "gp_42"
        assert body["name"] == "inst-name"


class TestRegisterCredential:
    """register_credential calls session.make_request and returns gpic_id."""

    def test_returns_gpic_id(self):
        mock_client = MagicMock()
        mock_client.make_request.return_value = {"gpic_id": "gpic_xyz"}

        result = register_credential(mock_client, "gpi_1", "label", "ES256", "pem-data")

        assert result == "gpic_xyz"

    def test_passes_correct_body(self):
        mock_client = MagicMock()
        mock_client.make_request.return_value = {"gpic_id": "gpic_y"}

        register_credential(mock_client, "gpi_2", "my-key", "EdDSA", "pub-pem")

        body = mock_client.make_request.call_args[0][1]
        assert body["gpi_id"] == "gpi_2"
        assert body["key_algorithm"] == "EdDSA"
        assert body["public_key_pem"] == "pub-pem"


# --- GPIC assertion JWT ---


class TestBuildGpicAssertion:
    """_build_gpic_assertion produces a valid JWT."""

    def test_returns_decodable_jwt(self):
        key = ec.generate_private_key(ec.SECP256R1())
        private_pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()

        jwt_str = _build_gpic_assertion("gpi_1", "gpic_2", private_pem, "ES256")

        payload = pyjwt.decode(jwt_str, options={"verify_signature": False})
        assert payload["iss"] == "gpi_1"
        assert payload["sub"] == "gpic_2"
        assert payload["aud"] == "trufo-ra"
        assert "iat" in payload
        assert "exp" in payload


# --- end-to-end procurement (sub-steps mocked) ---


class TestRequestC2paCert:
    """request_c2pa_cert orchestrates assertion -> CSR JWT -> EST -> PEM chain."""

    @pytest.mark.parametrize(
        ("request_cert", "api_url", "ca_url"),
        [
            (request_c2pa_cert, "https://api.trufo.ai", "https://ca.trufo.ai"),
            (request_c2pa_cert_test, "https://test.api.trufo.ai", "https://test.ca.trufo.ai"),
        ],
    )
    @patch(f"{_MODULE}.extract_cert_chain")
    @patch("requests.post")
    def test_enrolls_c2pa_l1_at_hosts(self, mock_post, mock_extract, request_cert, api_url, ca_url):
        mock_post.side_effect = [
            MagicMock(status_code=200, **{"json.return_value": {"csr_jwt": "csr-jwt"}}),
            MagicMock(status_code=200, content=b"pkcs7"),
        ]
        mock_extract.return_value = b"pem"

        key_pem = _ec_p256_pem()
        result = request_cert("gpi_1", "gpic_1", key_pem.decode(), key_pem)

        assert result == b"pem"
        mock_extract.assert_called_once_with(b"pkcs7")
        assert [call.args[0] for call in mock_post.call_args_list] == [
            f"{api_url}/ra/c2pa/csr-jwt",
            f"{ca_url}/.well-known/est/c2pa-l1/simpleenroll",
        ]

    @patch(f"{_MODULE}.extract_cert_chain")
    @patch(f"{_MODULE}.est_enroll")
    @patch(f"{_MODULE}.build_csr")
    @patch(f"{_MODULE}._request_c2pa_csr_jwt")
    def test_csr_jwt_threaded_through_to_est(
        self, mock_csr_jwt, mock_build_csr, mock_enroll, mock_extract
    ):
        """The CSR JWT from the RA must be the auth token passed to EST."""
        mock_csr_jwt.return_value = "RA-issued-csr-jwt"
        mock_build_csr.return_value = b"csr-der"
        mock_enroll.return_value = b"pkcs7"
        mock_extract.return_value = b"pem"

        key_pem = _ec_p256_pem()
        request_c2pa_cert("gpi_1", "gpic_1", key_pem.decode(), key_pem)

        csr_jwt_arg, _csr_der, _leaf = mock_enroll.call_args[0]
        assert csr_jwt_arg == "RA-issued-csr-jwt"
