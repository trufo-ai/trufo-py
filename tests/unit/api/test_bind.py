# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the standalone bind watermarking helpers."""

import base64
from unittest.mock import MagicMock, patch

import pytest
import requests

from trufo.api.endpoints import TRUFO_API_URL_TEST
from trufo.api.headers import sdk_headers
from trufo.api.tps.bind import bind_commit_test, bind_watermark_test

_M = "trufo.api.tps.bind"

_MARKED_B64 = base64.b64encode(b"marked").decode()


def _response(payload, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


class TestBindWatermarkTest:
    @patch(f"{_M}.requests.post")
    def test_provenance_posts_and_parses(self, mock_post):
        mock_post.return_value = _response(
            {"media_output": _MARKED_B64, "wid": "image.0000000abcd", "cid": "c_1"}
        )

        result = bind_watermark_test("key", b"media-bytes")

        assert result.media == b"marked"
        assert result.wid == "image.0000000abcd"
        assert result.cid == "c_1"
        call = mock_post.call_args
        assert call.args[0] == f"{TRUFO_API_URL_TEST}/bind/watermark"
        assert call.kwargs["headers"] == sdk_headers("key")
        assert call.kwargs["json"] == {
            "media_input": base64.b64encode(b"media-bytes").decode(),
            "mode": "provenance",
        }

    @patch(f"{_M}.requests.post")
    def test_compliance_sends_label_and_has_no_cid(self, mock_post):
        mock_post.return_value = _response(
            {"media_output": _MARKED_B64, "wid": "image.0000001abcd", "cid": None}
        )

        result = bind_watermark_test(
            "key", b"media-bytes", mode="compliance", ai_compliance_label="ai_generated"
        )

        assert result.cid is None
        assert mock_post.call_args.kwargs["json"]["mode"] == "compliance"
        assert mock_post.call_args.kwargs["json"]["ai_compliance_label"] == "ai_generated"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"mode": "compliance"},  # label missing
            {"ai_compliance_label": "ai_generated"},  # label without compliance
            {"mode": "attestation"},  # unknown mode
            {"mode": "compliance", "ai_compliance_label": "none"},  # unknown label
        ],
    )
    def test_bad_mode_label_pairing_rejected_locally(self, kwargs):
        with pytest.raises(ValueError):
            bind_watermark_test("key", b"media-bytes", **kwargs)


class TestBindCommitTest:
    @patch(f"{_M}.requests.post")
    def test_posts_cid_and_signed_media(self, mock_post):
        mock_post.return_value = _response({"cid": "c_1", "wid": "image.0000000abcd"})

        bind_commit_test("key", "c_1", b"signed-bytes")

        call = mock_post.call_args
        assert call.args[0] == f"{TRUFO_API_URL_TEST}/bind/commit"
        assert call.kwargs["json"] == {
            "cid": "c_1",
            "media_input": base64.b64encode(b"signed-bytes").decode(),
        }

    @patch(f"{_M}.requests.post")
    def test_http_error_raises(self, mock_post):
        mock_post.return_value = _response({"detail": "manifest mismatch"}, status=400)
        with pytest.raises(requests.HTTPError):
            bind_commit_test("key", "c_1", b"signed-bytes")
