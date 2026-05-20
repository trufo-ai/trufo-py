# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for TPS C2PA signing helpers."""

import base64
import json
import types
from unittest.mock import MagicMock, patch

import pytest

from trufo.api.endpoints import (
    TPS_C2PA_GET_S3_URL,
    TPS_C2PA_SIGN,
    TPS_C2PA_SIGN_TEST,
    TRUFO_API_URL,
)
from trufo.api.tps.sign_c2pa import (
    C2PAS3SignedOutput,
    C2PAS3Upload,
    _validate_actions,
    _validate_assertions,
    get_c2pa_s3_upload_url,
    sign_c2pa,
    sign_c2pa_remote,
    sign_c2pa_remote_test,
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


def _install_fake_remote_stack(monkeypatch, signed: bytes = b"signed-remote-media"):
    """Install fake optional tfprov modules and capture remote wrapper plumbing."""
    calls = {
        "cg_request": object(),
        "claim_signer": object(),
        "identity_signers": {},
        "ocsp_stapler": object(),
    }

    def fake_require_provenance_module(module_name):
        calls.setdefault("optional_imports", []).append(module_name)
        match module_name:
            case "tfprov.c2pa_generator":
                return types.SimpleNamespace(
                    build_cg_request=fake_build_cg_request,
                    generate_claim=fake_generate_claim,
                )
            case "tfprov.crypt":
                return types.SimpleNamespace(
                    TrufoRemoteClaimSigner=fake_remote_claim_signer,
                    TrufoRemoteIdentitySigner=fake_remote_identity_signer,
                )
            case "tfprov.c2pa_py.helpers.ocsp_stapler":
                return types.SimpleNamespace(OcspStapler=fake_ocsp_stapler)
            case "tfprov.util.av_format":
                return types.SimpleNamespace(
                    get_media_probe_result=fake_get_media_probe_result,
                )
        raise AssertionError(f"Unexpected optional import: {module_name}")

    def fake_get_media_probe_result(media_bytes):
        calls["media_probe"] = media_bytes
        return types.SimpleNamespace(mime_type="image/jpeg")

    def fake_build_cg_request(**kwargs):
        calls["build_cg_request"] = kwargs
        return calls["cg_request"]

    def fake_remote_claim_signer(*, api_key):
        calls["remote_claim_signer"] = api_key
        return calls["claim_signer"]

    def fake_remote_identity_signer(*, api_key, cawg_identity_id):
        calls.setdefault("remote_identity_signers", []).append(
            {"api_key": api_key, "cawg_identity_id": cawg_identity_id}
        )
        signer = object()
        calls["identity_signers"][cawg_identity_id] = signer
        return signer

    def fake_ocsp_stapler():
        calls["ocsp_stapler_constructed"] = True
        return calls["ocsp_stapler"]

    def fake_generate_claim(*args, **kwargs):
        calls["generate_claim"] = {"args": args, "kwargs": kwargs}
        return json.dumps({"media_output": base64.b64encode(signed).decode()})

    monkeypatch.setattr(
        "trufo.api.tps.sign_c2pa.require_provenance_module",
        fake_require_provenance_module,
    )
    return calls


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
    @patch("trufo.api.tps.sign_c2pa.requests.post")
    def test_assertions_without_cawg_identity_warn(self, mock_post, signer, caplog):
        signed = b"signed"
        mock_post.return_value = _mock_response(
            {"media_output": base64.b64encode(signed).decode("utf-8")}
        )

        with caplog.at_level("WARNING", logger="trufo.api.tps.sign_c2pa"):
            result = signer(
                "api-key",
                b"input-media",
                assertions=[["ai_disclosure", {}]],
            )

        assert result == signed
        assert "Gathered assertions are being input by the client" in caplog.text


class TestRemoteC2PASigning:
    """Remote C2PA signing wrapper behavior."""

    def test_remote_test_signing_wires_optional_provenance_stack(self, monkeypatch):
        signed = b"signed-remote-media"
        calls = _install_fake_remote_stack(monkeypatch, signed=signed)

        result = sign_c2pa_remote_test(
            "remote-sign-key",
            b"input-media",
            actions=[["publish", {}]],
            assertions=[["cawg_identity", {"cawg_identity_id": "test"}]],
            tsa_api_key="tsa-key",
        )

        assert result == signed
        assert calls["optional_imports"] == [
            "tfprov.c2pa_generator",
            "tfprov.crypt",
            "tfprov.c2pa_py.helpers.ocsp_stapler",
            "tfprov.util.av_format",
        ]
        assert calls["media_probe"] == b"input-media"
        assert calls["build_cg_request"] == {
            "actions": [["publish", {}]],
            "assertions": [["cawg_identity", {"cawg_identity_id": "test"}]],
            "media_bytes": b"input-media",
            "mime_type": "image/jpeg",
        }
        assert calls["remote_claim_signer"] == "remote-sign-key"
        assert calls["remote_identity_signers"] == [
            {"api_key": "remote-sign-key", "cawg_identity_id": "test"}
        ]
        assert calls["ocsp_stapler_constructed"] is True
        assert calls["generate_claim"] == {
            "args": (calls["cg_request"],),
            "kwargs": {
                "claim_signer": calls["claim_signer"],
                "ocsp_stapler": calls["ocsp_stapler"],
                "tsa_api_key": "tsa-key",
                "cawg_identity_signers": calls["identity_signers"],
            },
        }

    def test_remote_test_signing_loads_configured_tsa_key(self, monkeypatch):
        calls = _install_fake_remote_stack(monkeypatch, signed=b"signed")

        def fake_load_api_key(key_type):
            calls["key_type"] = key_type
            return "configured-tsa-key"

        monkeypatch.setattr("trufo.api.tps.sign_c2pa.load_api_key", fake_load_api_key)

        assert sign_c2pa_remote_test("api-key", b"input-media") == b"signed"
        assert calls["key_type"] == "tsa"
        assert calls["generate_claim"]["kwargs"]["tsa_api_key"] == "configured-tsa-key"

    def test_remote_test_signing_requires_tsa_key_before_optional_imports(self, monkeypatch):
        require_provenance_module = MagicMock()
        monkeypatch.setattr("trufo.api.tps.sign_c2pa.load_api_key", lambda _key: None)
        monkeypatch.setattr(
            "trufo.api.tps.sign_c2pa.require_provenance_module",
            require_provenance_module,
        )

        with pytest.raises(RuntimeError, match="TSA API key"):
            sign_c2pa_remote_test("api-key", b"input-media")

        require_provenance_module.assert_not_called()

    def test_remote_prod_signing_is_explicit_stub(self):
        with pytest.raises(NotImplementedError, match="not implemented server-side"):
            sign_c2pa_remote("api-key", b"input-media")

    def test_remote_assertions_without_cawg_identity_warns_and_continues(self, monkeypatch, caplog):
        calls = _install_fake_remote_stack(monkeypatch, signed=b"signed")

        with caplog.at_level("WARNING", logger="trufo.api.tps.sign_c2pa"):
            result = sign_c2pa_remote_test(
                "api-key",
                b"input-media",
                assertions=[["ai_disclosure", {}]],
                tsa_api_key="tsa-key",
            )

        assert result == b"signed"
        assert "Gathered assertions are being input by the client" in caplog.text
        assert calls["generate_claim"]["kwargs"]["cawg_identity_signers"] == {}


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
        mock_sign_s3.return_value = C2PAS3SignedOutput(media_output_s3="https://download.example")
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
    @patch("trufo.api.tps.sign_c2pa.requests.post")
    def test_s3_assertions_without_cawg_identity_warn(self, mock_post, signer, caplog):
        mock_post.return_value = _mock_response({"media_output_s3": "https://download.example"})

        with caplog.at_level("WARNING", logger="trufo.api.tps.sign_c2pa"):
            result = signer(
                "api-key",
                "signed-input-reference",
                assertions=[["ai_disclosure", {}]],
            )

        assert result == C2PAS3SignedOutput(media_output_s3="https://download.example")
        assert "Gathered assertions are being input by the client" in caplog.text


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
