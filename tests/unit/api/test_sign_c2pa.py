# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for TPS C2PA signing helpers."""

import base64
from unittest.mock import MagicMock, patch

import pytest

from trufo.api.endpoints import (
    TRUFO_API_URL,
    TPS_C2PA_GET_S3_URL,
    TPS_C2PA_SIGN,
    TPS_C2PA_SIGN_TEST,
)
from trufo.api.tps.sign_c2pa import (
    C2PAS3SignedOutput,
    C2PAS3Upload,
    _validate_actions,
    _validate_assertions,
    get_c2pa_s3_upload_url,
    sign_c2pa,
    sign_c2pa_s3,
    sign_c2pa_test,
    sign_c2pa_test_s3,
    sign_c2pa_test_via_s3,
    sign_c2pa_via_s3,
)


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


class TestS3C2PASigning:
    """Ephemeral S3 C2PA signing helpers."""

    @patch("trufo.api.tps.sign_c2pa.requests.post")
    def test_get_c2pa_s3_upload_url_posts_expected_body(self, mock_post):
        mock_post.return_value = _mock_response(
            {
                "upload_url": "https://upload.example",
                "media_input_s3": "signed-input-reference",
                "expires_at": 1770000000,
                "duration": "5m",
            }
        )

        upload = get_c2pa_s3_upload_url("api-key", "image/jpeg", duration="5m")

        assert upload == C2PAS3Upload(
            upload_url="https://upload.example",
            media_input_s3="signed-input-reference",
            expires_at=1770000000,
            duration="5m",
        )
        mock_post.assert_called_once_with(
            TRUFO_API_URL + TPS_C2PA_GET_S3_URL,
            json={"mime_type": "image/jpeg", "duration": "5m"},
            headers={"X-API-Key": "api-key"},
            timeout=60,
        )
        mock_post.return_value.raise_for_status.assert_called_once_with()

    @patch("trufo.api.tps.sign_c2pa.requests.post")
    def test_sign_c2pa_s3_posts_to_prod_endpoint(self, mock_post):
        mock_post.return_value = _mock_response({"media_output_s3": "https://download.example"})

        result = sign_c2pa_s3(
            "prod-key",
            "signed-input-reference",
            actions=[["publish", {}]],
            assertions=[["cawg_identity", {"cawg_identity_id": "org_interim"}]],
        )

        assert result == C2PAS3SignedOutput(media_output_s3="https://download.example")
        mock_post.assert_called_once_with(
            TRUFO_API_URL + TPS_C2PA_SIGN,
            json={
                "media_input_s3": "signed-input-reference",
                "actions": [["publish", {}]],
                "assertions": [["cawg_identity", {"cawg_identity_id": "org_interim"}]],
            },
            headers={"X-API-Key": "prod-key"},
            timeout=60,
        )

    @patch("trufo.api.tps.sign_c2pa.requests.post")
    def test_sign_c2pa_test_s3_posts_to_test_endpoint(self, mock_post):
        mock_post.return_value = _mock_response({"media_output_s3": "https://download.example"})

        result = sign_c2pa_test_s3("test-key", "signed-input-reference")

        assert result == C2PAS3SignedOutput(media_output_s3="https://download.example")
        mock_post.assert_called_once_with(
            TRUFO_API_URL + TPS_C2PA_SIGN_TEST,
            json={
                "media_input_s3": "signed-input-reference",
                "actions": [],
                "assertions": [],
            },
            headers={"X-API-Key": "test-key"},
            timeout=60,
        )

    @patch("trufo.api.tps.sign_c2pa.requests.get")
    @patch("trufo.api.tps.sign_c2pa.requests.put")
    @patch("trufo.api.tps.sign_c2pa.sign_c2pa_s3")
    @patch("trufo.api.tps.sign_c2pa.get_c2pa_s3_upload_url")
    def test_sign_c2pa_via_s3_composes_low_level_helpers(
        self,
        mock_get_upload_url,
        mock_sign_s3,
        mock_put,
        mock_get,
    ):
        mock_get_upload_url.return_value = C2PAS3Upload(
            upload_url="https://upload.example",
            media_input_s3="signed-input-reference",
            expires_at=1770000000,
            duration="5m",
        )
        mock_sign_s3.return_value = C2PAS3SignedOutput(
            media_output_s3="https://download.example"
        )
        mock_get.return_value.content = b"signed-media"

        result = sign_c2pa_via_s3(
            "prod-key",
            b"input-media",
            "image/jpeg",
            actions=[["publish", {}]],
            assertions=[["cawg_identity", {"cawg_identity_id": "org_interim"}]],
            duration="5m",
        )

        assert result == b"signed-media"
        mock_get_upload_url.assert_called_once_with("prod-key", "image/jpeg", duration="5m")
        mock_put.assert_called_once_with(
            "https://upload.example",
            content=b"input-media",
            headers={"Content-Type": "image/jpeg"},
            timeout=60,
        )
        mock_put.return_value.raise_for_status.assert_called_once_with()
        mock_sign_s3.assert_called_once_with(
            "prod-key",
            "signed-input-reference",
            actions=[["publish", {}]],
            assertions=[["cawg_identity", {"cawg_identity_id": "org_interim"}]],
        )
        mock_get.assert_called_once_with("https://download.example", timeout=60)
        mock_get.return_value.raise_for_status.assert_called_once_with()

    @patch("trufo.api.tps.sign_c2pa.requests.get")
    @patch("trufo.api.tps.sign_c2pa.requests.put")
    @patch("trufo.api.tps.sign_c2pa.sign_c2pa_test_s3")
    @patch("trufo.api.tps.sign_c2pa.get_c2pa_s3_upload_url")
    def test_sign_c2pa_test_via_s3_uses_test_signer(
        self,
        mock_get_upload_url,
        mock_sign_test_s3,
        _mock_put,
        mock_get,
    ):
        mock_get_upload_url.return_value = C2PAS3Upload(
            upload_url="https://upload.example",
            media_input_s3="signed-input-reference",
            expires_at=1770000000,
            duration="5m",
        )
        mock_sign_test_s3.return_value = C2PAS3SignedOutput(
            media_output_s3="https://download.example"
        )
        mock_get.return_value.content = b"signed-media"

        result = sign_c2pa_test_via_s3("test-key", b"input-media", "image/jpeg")

        assert result == b"signed-media"
        mock_sign_test_s3.assert_called_once_with(
            "test-key",
            "signed-input-reference",
            actions=None,
            assertions=None,
        )

    @pytest.mark.parametrize("signer", [sign_c2pa_s3, sign_c2pa_test_s3])
    def test_s3_assertions_require_cawg_identity(self, signer):
        with pytest.raises(ValueError, match="cawg_identity"):
            signer(
                "api-key",
                "signed-input-reference",
                assertions=[["ai_disclosure", {}]],
            )


class TestRequestValidation:
    """Client-side action/assertion name validation, pre-API-call.

    The cawg_identity requirement is exercised via the public signers above;
    this targets the entry-name/enum validation in the pure helpers, which is
    otherwise uncovered.
    """

    @pytest.mark.parametrize(
        "validator, value",
        [
            (_validate_actions, None),
            (_validate_actions, []),
            (_validate_actions, [["publish", {}], ["transcode", {}]]),
            (_validate_assertions, None),
            (_validate_assertions, []),
            (_validate_assertions, [["cawg_identity", {}]]),
        ],
    )
    def test_valid_inputs_pass(self, validator, value):
        validator(value)  # must not raise

    @pytest.mark.parametrize(
        "validator, entry_type, bad",
        [
            (_validate_actions, "action", [["not_an_action", {}]]),
            (_validate_actions, "action", [[]]),
            (_validate_actions, "action", [[123, {}]]),
            (_validate_assertions, "assertion", [["not_an_assertion", {}]]),
            (_validate_assertions, "assertion", [[]]),
        ],
    )
    def test_invalid_entries_rejected(self, validator, entry_type, bad):
        with pytest.raises(ValueError, match=f"Invalid {entry_type} entry"):
            validator(bad)
