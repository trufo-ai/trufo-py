# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the watermark recovery helper."""

import base64
from unittest.mock import MagicMock, patch

import pytest
import requests

from trufo.api.endpoints import TRUFO_API_URL
from trufo.api.tps.recover import recover_content
from trufo.api.headers import sdk_headers

_M = "trufo.api.tps.recover"


def _response(payload, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


class TestRecoverContent:
    @patch(f"{_M}.requests.post")
    def test_posts_media_and_parses_detection(self, mock_post):
        mock_post.return_value = _response(
            {"detected": True, "wid": "image.001a1b2c3d4", "confidence": 0.98, "manifest_bytes": None}
        )

        result = recover_content("key", b"media-bytes")

        assert result.detected is True
        assert result.wid == "image.001a1b2c3d4"
        assert result.confidence == 0.98
        assert result.manifest_bytes is None
        assert result.manifest_json is None
        assert result.ai_compliance_label is None
        assert result.oid is None
        call = mock_post.call_args
        assert call.args[0] == f"{TRUFO_API_URL}/content/recover"
        assert call.kwargs["headers"] == sdk_headers("key")
        assert call.kwargs["json"] == {
            "media_input": base64.b64encode(b"media-bytes").decode(),
            "parse_manifest_json": False,
        }

    @patch(f"{_M}.requests.post")
    def test_manifest_bytes_decoded_and_parse_requested(self, mock_post):
        store = b"\x00jumb"
        mock_post.return_value = _response(
            {
                "detected": True,
                "wid": "v1.001a1b2c3d4",
                "confidence": 0.9,
                "manifest_bytes": base64.b64encode(store).decode(),
                "manifest_json": {"manifests": [1]},
            }
        )

        result = recover_content("key", b"media-bytes", parse_manifest_json=True)

        assert result.manifest_bytes == store
        assert result.manifest_json == {"manifests": [1]}
        assert mock_post.call_args.kwargs["json"]["parse_manifest_json"] is True

    @patch(f"{_M}.requests.post")
    def test_compliance_mark_fields_are_parsed(self, mock_post):
        mock_post.return_value = _response(
            {
                "detected": True,
                "wid": "image.0000001abcd",
                "confidence": 0.9,
                "ai_compliance_label": "ai_generated",
                "oid": "org_1",
            }
        )

        result = recover_content("key", b"media-bytes")

        assert result.ai_compliance_label == "ai_generated"
        assert result.oid == "org_1"
        assert result.manifest_bytes is None

    @patch(f"{_M}.requests.post")
    def test_not_detected_returns_bare_result(self, mock_post):
        mock_post.return_value = _response({"detected": False})

        result = recover_content("key", b"media-bytes")

        assert result.detected is False
        assert result.wid is None
        assert result.confidence is None

    @patch(f"{_M}.requests.post")
    def test_http_error_raises(self, mock_post):
        mock_post.return_value = _response({"detail": "Forbidden"}, status=403)

        with pytest.raises(requests.HTTPError):
            recover_content("key", b"media-bytes")
