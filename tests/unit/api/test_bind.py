# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the bind helpers (tpls and lpls routes)."""

import base64
from unittest.mock import MagicMock, patch

import pytest
import requests

from trufo.api.endpoints import TRUFO_API_URL, TRUFO_API_URL_TEST
from trufo.api.headers import sdk_headers
from trufo.api.tps.bind import (
    bind_commit,
    bind_commit_test,
    bind_reserve,
    bind_reserve_test,
    bind_watermark,
    bind_watermark_test,
    watermark_media,
)

_M = "trufo.api.tps.bind"

_MARKED_B64 = base64.b64encode(b"marked").decode()
_WID = "v1.001abcdef12"


def _response(payload, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


class TestBindWatermark:
    @patch(f"{_M}.requests.post")
    def test_provenance_posts_and_parses(self, mock_post):
        mock_post.return_value = _response({"media_output": _MARKED_B64, "wid": _WID, "cid": "c_1"})

        result = bind_watermark("key", b"media-bytes")

        assert result.media == b"marked"
        assert result.wid == _WID
        assert result.cid == "c_1"
        call = mock_post.call_args
        assert call.args[0] == f"{TRUFO_API_URL}/bind/watermark"
        assert call.kwargs["headers"] == sdk_headers("key")
        assert call.kwargs["json"] == {
            "media_input": base64.b64encode(b"media-bytes").decode(),
            "mode": "provenance",
        }

    @patch(f"{_M}.requests.post")
    def test_compliance_sends_label_and_has_no_cid(self, mock_post):
        mock_post.return_value = _response(
            {"media_output": _MARKED_B64, "wid": "v1.0000001abcd", "cid": None}
        )

        result = bind_watermark_test(
            "key", b"media-bytes", mode="compliance", ai_compliance_label="ai_generated"
        )

        assert result.cid is None
        assert mock_post.call_args.args[0] == f"{TRUFO_API_URL_TEST}/bind/watermark"
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
            bind_watermark("key", b"media-bytes", **kwargs)


class TestBindReserve:
    @patch(f"{_M}.requests.post")
    def test_posts_mime_type_and_parses_the_package(self, mock_post):
        mock_post.return_value = _response(
            {"cid": "c_1", "wid_package": {"wid": _WID, "expires_at": "2026-09-08T00:00:00+00:00"}}
        )

        reservation = bind_reserve("key", "image/jpeg")

        assert mock_post.call_args.args[0] == f"{TRUFO_API_URL}/bind/reserve"
        assert mock_post.call_args.kwargs["json"] == {"mime_type": "image/jpeg"}
        assert (reservation.cid, reservation.wid) == ("c_1", _WID)
        # what the engine consumes is the package as the API issued it
        assert reservation.wid_package == {"wid": _WID, "expires_at": "2026-09-08T00:00:00+00:00"}

    @patch(f"{_M}.requests.post")
    def test_test_variant_targets_the_test_host(self, mock_post):
        mock_post.return_value = _response(
            {"cid": "c_1", "wid_package": {"wid": "v1.0000000abcd", "expires_at": "x"}}
        )
        bind_reserve_test("key", "audio/wav")
        assert mock_post.call_args.args[0] == f"{TRUFO_API_URL_TEST}/bind/reserve"


class TestWatermarkMedia:
    def test_embeds_through_the_engine_boundary(self):
        engine = MagicMock()
        engine.WatermarkIdPackage.side_effect = lambda **kw: kw
        engine.encode.return_value = b"marked"
        with patch.dict("sys.modules", {"tfprov.util.pawprint_import": engine}):
            with patch("tfprov.util.pawprint_import", engine, create=True):
                assert watermark_media(b"media", {"wid": _WID, "expires_at": "x"}) == b"marked"
        engine.encode.assert_called_once_with(b"media", {"wid": _WID, "expires_at": "x"})

    def test_missing_engine_gives_the_install_hint(self):
        with patch.dict("sys.modules", {"tfprov.util.pawprint_import": None, "tfprov.util": None}):
            with pytest.raises(ImportError, match="local-full"):
                watermark_media(b"media", {"wid": _WID, "expires_at": "x"})


class TestBindCommit:
    @patch(f"{_M}.requests.post")
    def test_posts_cid_wid_and_manifest_store(self, mock_post):
        mock_post.return_value = _response({"cid": "c_1", "wid": _WID})

        bind_commit("key", "c_1", _WID, manifest_bytes=b"store")

        call = mock_post.call_args
        assert call.args[0] == f"{TRUFO_API_URL}/bind/commit"
        assert call.kwargs["json"] == {
            "cid": "c_1",
            "wid": _WID,
            "manifest": base64.b64encode(b"store").decode(),
        }

    @patch(f"{_M}.requests.post")
    def test_manifest_id_with_own_endpoint(self, mock_post):
        mock_post.return_value = _response({"cid": "c_1", "wid": _WID})

        bind_commit_test(
            "key", "c_1", _WID, manifest_id="urn:c2pa:1", manifest_endpoint="https://m.example/c2pa"
        )

        assert mock_post.call_args.args[0] == f"{TRUFO_API_URL_TEST}/bind/commit"
        assert mock_post.call_args.kwargs["json"] == {
            "cid": "c_1",
            "wid": _WID,
            "manifest_id": "urn:c2pa:1",
            "manifest_endpoint": "https://m.example/c2pa",
        }

    @patch(f"{_M}._manifest_store_from_media", return_value=b"store")
    @patch(f"{_M}.requests.post")
    def test_signed_media_is_reduced_to_its_store_locally(self, mock_post, mock_extract):
        mock_post.return_value = _response({"cid": "c_1", "wid": _WID})

        bind_commit("key", "c_1", _WID, signed_media_bytes=b"signed-bytes")

        mock_extract.assert_called_once_with(b"signed-bytes")
        # the API never sees the media
        assert mock_post.call_args.kwargs["json"] == {
            "cid": "c_1",
            "wid": _WID,
            "manifest": base64.b64encode(b"store").decode(),
        }

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},  # no manifest source
            {"signed_media_bytes": b"signed-bytes", "manifest_bytes": b"store"},  # two
            {"manifest_id": "urn:c2pa:1"},  # id without the customer's endpoint
        ],
    )
    def test_manifest_source_rules_enforced_locally(self, kwargs):
        with pytest.raises(ValueError):
            bind_commit("key", "c_1", _WID, **kwargs)

    @patch(f"{_M}.requests.post")
    def test_http_error_raises(self, mock_post):
        mock_post.return_value = _response({"detail": "manifest mismatch"}, status=400)
        with pytest.raises(requests.HTTPError):
            bind_commit("key", "c_1", _WID, manifest_bytes=b"store")
