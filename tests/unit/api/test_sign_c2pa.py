# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for TPS C2PA signing helpers."""

import base64
from unittest.mock import MagicMock, patch

import pytest

from trufo.api.endpoints import TRUFO_API_URL, TPS_C2PA_SIGN, TPS_C2PA_SIGN_TEST
from trufo.api.tps.sign_c2pa import sign_c2pa, sign_c2pa_test


def _mock_response(json_data: dict):
    """Build a mock ``requests.Response``."""
    resp = MagicMock()
    resp.json.return_value = json_data
    return resp


class TestDirectC2PASigning:
    """Direct media-byte C2PA signing helpers."""

    @patch("trufo.api.tps.sign_c2pa.requests.post")
    def test_sign_c2pa_posts_to_prod_endpoint(self, mock_post):
        signed = b"signed-prod"
        mock_post.return_value = _mock_response(
            {"media_output": base64.b64encode(signed).decode("utf-8")}
        )

        result = sign_c2pa(
            "prod-key",
            b"input-media",
            actions=[["publish", {}]],
            assertions=[["cawg_identity", {"cawg_identity_id": "org_interim"}]],
        )

        assert result == signed
        mock_post.assert_called_once_with(
            TRUFO_API_URL + TPS_C2PA_SIGN,
            json={
                "media_input": base64.b64encode(b"input-media").decode(),
                "actions": [["publish", {}]],
                "assertions": [["cawg_identity", {"cawg_identity_id": "org_interim"}]],
            },
            headers={"X-API-Key": "prod-key"},
            timeout=60,
        )
        mock_post.return_value.raise_for_status.assert_called_once_with()

    @patch("trufo.api.tps.sign_c2pa.requests.post")
    def test_sign_c2pa_test_posts_to_test_endpoint(self, mock_post):
        signed = b"signed-test"
        mock_post.return_value = _mock_response(
            {"media_output": base64.b64encode(signed).decode("utf-8")}
        )

        result = sign_c2pa_test("test-key", b"input-media")

        assert result == signed
        mock_post.assert_called_once_with(
            TRUFO_API_URL + TPS_C2PA_SIGN_TEST,
            json={
                "media_input": base64.b64encode(b"input-media").decode(),
                "actions": [],
                "assertions": [],
            },
            headers={"X-API-Key": "test-key"},
            timeout=60,
        )

    @pytest.mark.parametrize("signer", [sign_c2pa, sign_c2pa_test])
    def test_assertions_require_cawg_identity(self, signer):
        with pytest.raises(ValueError, match="cawg_identity"):
            signer(
                "api-key",
                b"input-media",
                assertions=[["ai_disclosure", {}]],
            )
