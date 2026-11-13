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
from trufo.api.tps.tasks import ExecutionMode
from trufo.c2pa import WatermarkSettings
from trufo.util.warnings import TrufoServerWarning

_M = "trufo.api.tps.bind"

_MARKED_B64 = base64.b64encode(b"marked").decode()
_WID = "v1.001abcdef12"
_PER_AI_SYSTEM = {
    "wid_allocation_mode": "per_ai_system",
    "ai_system_id": "aisys_1",
    "ai_involvement": "ai_generated",
}


def _response(payload, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


class TestBindWatermark:
    @patch(f"{_M}.requests.post")
    def test_default_bind_sends_no_mode(self, mock_post):
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
        }

    @pytest.mark.parametrize(
        "bind, arg, kwargs",
        [
            (bind_watermark, b"media-bytes", {}),
            (
                bind_watermark,
                b"media-bytes",
                {"execution_mode": ExecutionMode.TASK, "mime_type": "image/jpeg"},
            ),
            (bind_watermark_test, b"media-bytes", {}),
            (bind_reserve_test, "image/jpeg", {}),
        ],
    )
    @patch(f"{_M}._download_task_output", return_value=b"marked")
    @patch(f"{_M}.wait_for_task")
    @patch(f"{_M}._upload_task_input", return_value="s3-ref")
    @patch(f"{_M}.requests.post")
    def test_allocation_keys_sent_when_set(
        self, post, _upload, _wait, _download, bind, arg, kwargs
    ):
        post.return_value = _response(
            {
                "media_output": _MARKED_B64,
                "wid": _WID,
                "cid": "c_1",
                "task_id": "t_1",
                "wid_package": {"wid": _WID, "expires_at": "x"},
                "task_type": "watermark",
                "status": "queued",
                "startby_ts": "x",
                "timeout_seconds": 60,
            },
            status=202,
        )
        bind("key", arg, **kwargs, **_PER_AI_SYSTEM)
        assert post.call_args.kwargs["json"].items() >= _PER_AI_SYSTEM.items()

    @patch(f"{_M}.requests.post")
    def test_deprecated_mode_is_sent_and_server_warnings_reemitted(self, mock_post):
        mock_post.return_value = _response(
            {"media_output": _MARKED_B64, "wid": _WID, "warnings": ["'mode' is deprecated."]}
        )
        with pytest.warns(TrufoServerWarning, match="'mode' is deprecated"):
            bind_watermark("key", b"media-bytes", mode="provenance")
        assert mock_post.call_args.kwargs["json"]["mode"] == "provenance"

    @pytest.mark.parametrize(
        "kwargs, error",
        [
            ({"mode": "compliance"}, NotImplementedError),
            ({"ai_compliance_label": "ai_generated"}, TypeError),
            ({"mode": "attestation"}, ValueError),
            ({"mode": "provenance", "wid_allocation_mode": "per_embed"}, ValueError),
            ({"wid_allocation_mode": "per_asset"}, NotImplementedError),
            ({"ai_involvement": "ai_assisted"}, ValueError),
        ],
    )
    @patch(f"{_M}.requests.post")
    def test_unsupported_options_do_not_send_request(self, post, kwargs, error):
        with pytest.raises(error):
            bind_watermark("key", b"media-bytes", **kwargs)
        post.assert_not_called()


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
    @pytest.mark.parametrize("settings", [None, WatermarkSettings(), WatermarkSettings("fast")])
    def test_embeds_through_the_engine_boundary(self, settings):
        engine = MagicMock()
        engine.WatermarkIdPackage.side_effect = lambda **kw: kw
        engine.embed.return_value = b"marked"
        with patch.dict("sys.modules", {"tfprov.util": MagicMock(pawprint_import=engine)}):
            assert (
                watermark_media(
                    b"media", {"wid": _WID, "expires_at": "x"}, watermark_settings=settings
                )
                == b"marked"
            )
        options = {} if settings is None else {"mode": settings.profile.value}
        engine.embed.assert_called_once_with(b"media", {"wid": _WID, "expires_at": "x"}, **options)

    def test_wrong_settings_type_precedes_optional_import(self):
        with patch.dict("sys.modules", {"tfprov.util": None}):
            with pytest.raises(TypeError, match="WatermarkSettings"):
                watermark_media(b"media", {}, watermark_settings="fast")

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
    def test_test_variant_targets_the_test_host(self, mock_post):
        mock_post.return_value = _response({"cid": "c_1", "wid": _WID})
        bind_commit_test("key", "c_1", _WID, manifest_bytes=b"store")
        assert mock_post.call_args.args[0] == f"{TRUFO_API_URL_TEST}/bind/commit"

    @patch(f"{_M}.requests.post")
    def test_server_warnings_reemitted(self, mock_post):
        mock_post.return_value = _response(
            {"cid": "c_1", "wid": _WID, "warnings": ["The mark is not declared."]}
        )
        with pytest.warns(TrufoServerWarning, match="The mark is not declared"):
            bind_commit("key", "c_1", _WID, manifest_bytes=b"store")

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
        ],
    )
    def test_manifest_source_rules_enforced_locally(self, kwargs):
        with pytest.raises(
            ValueError, match="Provide exactly one of manifest_bytes or signed_media_bytes"
        ):
            bind_commit("key", "c_1", _WID, **kwargs)

    @patch(f"{_M}.requests.post")
    def test_http_error_raises(self, mock_post):
        mock_post.return_value = _response({"detail": "manifest mismatch"}, status=400)
        with pytest.raises(requests.HTTPError):
            bind_commit("key", "c_1", _WID, manifest_bytes=b"store")
