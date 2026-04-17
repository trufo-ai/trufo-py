# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for api/tca/c2pa_cert.py — C2PA certificate procurement."""

from unittest.mock import MagicMock, patch

import jwt as pyjwt

from trufo.api.tca.certs_c2pa import _build_gpic_assertion, create_instance, register_credential
from trufo.api.tca.tca_utils import LeafType

# --- LeafType ---


class TestLeafType:
    """LeafType enum values."""

    def test_c2pa_l1_value(self):
        assert LeafType.C2PA_L1.value == "c2pa-l1"

    def test_c2pa_l2_value(self):
        assert LeafType.C2PA_L2.value == "c2pa-l2"

    def test_c2pa_l1_test_value(self):
        assert LeafType.C2PA_L1_TEST.value == "c2pa-l1-test"

    def test_c2pa_l2_test_value(self):
        assert LeafType.C2PA_L2_TEST.value == "c2pa-l2-test"

    def test_is_str_subclass(self):
        assert isinstance(LeafType.C2PA_L1, str)


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
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            NoEncryption,
            PrivateFormat,
        )

        key = ec.generate_private_key(ec.SECP256R1())
        private_pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()

        jwt_str = _build_gpic_assertion("gpi_1", "gpic_2", private_pem, "ES256")

        # decode without verification to check claims
        payload = pyjwt.decode(jwt_str, options={"verify_signature": False})
        assert payload["iss"] == "gpi_1"
        assert payload["sub"] == "gpic_2"
        assert payload["aud"] == "trufo-ra"
        assert "iat" in payload
        assert "exp" in payload
