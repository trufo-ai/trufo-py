# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for TPS C2PA signing helpers."""

import base64
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
from trufo.util.credentials import TrufoApiKey


def _mock_response(json_data: dict):
    """Build a mock ``requests.Response``."""
    resp = MagicMock()
    resp.json.return_value = json_data
    return resp


def _install_fake_remote_stack(
    monkeypatch,
    signed: bytes = b"signed-remote-media",
    warning_messages: list | None = None,
):
    """Install fake optional tfprov modules and capture generate_claim_remote plumbing."""
    calls = {
        "imports": [],
        "ocsp_stapler": object(),
        "timestampers": [],
    }

    def fake_timestamper(*, api_key, url=None):
        timestamper = types.SimpleNamespace(api_key=api_key, url=url)
        calls["timestampers"].append(timestamper)
        return timestamper

    def fake_ocsp_stapler():
        calls["ocsp_stapler_constructed"] = True
        return calls["ocsp_stapler"]

    def fake_generate_claim_remote(api_key, media_bytes, **kwargs):
        calls["generate_claim_remote"] = {
            "api_key": api_key,
            "media_bytes": media_bytes,
            "kwargs": kwargs,
        }
        return signed, warning_messages or []

    def fake_require_provenance_module(module_name):
        calls["imports"].append(module_name)
        match module_name:
            case "tfprov.c2pa_generator.remote_orchestrator":
                return types.SimpleNamespace(generate_claim_remote=fake_generate_claim_remote)
            case "tfprov.c2pa_py.helpers.ocsp_stapler":
                return types.SimpleNamespace(OcspStapler=fake_ocsp_stapler)
            case "tfprov.c2pa_py.helpers.timestamper":
                return types.SimpleNamespace(TrufoTimestamper=fake_timestamper)
        raise AssertionError(f"Unexpected optional import: {module_name}")

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
    """Remote C2PA signing wrappers delegate to the tfprov orchestrator."""

    _REMOTE_SIGNERS = [sign_c2pa_remote, sign_c2pa_remote_test]

    def test_test_signing_delegates_with_test_flag(self, monkeypatch):
        calls = _install_fake_remote_stack(monkeypatch, signed=b"signed-test")

        result = sign_c2pa_remote_test(
            "remote-sign-key",
            b"input-media",
            actions=[["publish", {}]],
            assertions=[["cawg_identity", {"cawg_identity_id": "test"}]],
            tsa_api_key="tsa-key",
        )

        assert result == b"signed-test"
        assert calls["imports"] == [
            "tfprov.c2pa_generator.remote_orchestrator",
            "tfprov.c2pa_py.helpers.ocsp_stapler",
            "tfprov.c2pa_py.helpers.timestamper",
        ]
        remote_call = calls["generate_claim_remote"]
        assert remote_call["api_key"] == "remote-sign-key"
        assert remote_call["media_bytes"] == b"input-media"

        kwargs = remote_call["kwargs"]
        assert kwargs["actions"] == [["publish", {}]]
        assert kwargs["assertions"] == [["cawg_identity", {"cawg_identity_id": "test"}]]
        assert kwargs["test"] is True
        assert kwargs["trufo_api_url"] == "https://api.trufo.ai"
        assert kwargs["ocsp_stapler"] is calls["ocsp_stapler"]

        # a single timestamper is built with the resolved key and no URL override
        assert [ts.api_key for ts in calls["timestampers"]] == ["tsa-key"]
        assert calls["timestampers"][0].url is None
        assert kwargs["timestamper"] is calls["timestampers"][0]

    def test_prod_signing_delegates_with_endpoint_overrides(self, monkeypatch):
        calls = _install_fake_remote_stack(monkeypatch, signed=b"signed-prod")

        result = sign_c2pa_remote(
            "remote-sign-key",
            b"input-media",
            actions=[["publish", {}]],
            assertions=[["cawg_identity", {"cawg_identity_id": "org_interim"}]],
            tsa_api_key="tsa-key",
            trufo_tsa_url="https://tsa.trufo.example",
            trufo_api_url="https://api.trufo.example",
        )

        assert result == b"signed-prod"
        kwargs = calls["generate_claim_remote"]["kwargs"]
        assert kwargs["actions"] == [["publish", {}]]
        assert kwargs["assertions"] == [["cawg_identity", {"cawg_identity_id": "org_interim"}]]
        assert kwargs["test"] is False
        assert kwargs["trufo_api_url"] == "https://api.trufo.example"

        # the TSA URL override flows into the timestamper
        assert calls["timestampers"][0].api_key == "tsa-key"
        assert calls["timestampers"][0].url == "https://tsa.trufo.example"
        assert kwargs["timestamper"] is calls["timestampers"][0]

    def test_prod_signing_uses_default_api_url(self, monkeypatch):
        calls = _install_fake_remote_stack(monkeypatch)

        sign_c2pa_remote("remote-sign-key", b"input-media", tsa_api_key="tsa-key")

        kwargs = calls["generate_claim_remote"]["kwargs"]
        assert kwargs["test"] is False
        assert kwargs["trufo_api_url"] == "https://api.trufo.ai"
        assert calls["timestampers"][0].url is None

    @pytest.mark.parametrize("signer", _REMOTE_SIGNERS)
    def test_returns_signed_bytes_discarding_orchestrator_warnings(self, monkeypatch, signer):
        _install_fake_remote_stack(
            monkeypatch, signed=b"signed", warning_messages=["preprocess warning"]
        )

        result = signer("remote-sign-key", b"input-media", tsa_api_key="tsa-key")

        # the orchestrator returns (bytes, warnings); only the bytes are surfaced
        assert result == b"signed"

    @pytest.mark.parametrize("signer", _REMOTE_SIGNERS)
    def test_validates_before_optional_imports(self, monkeypatch, signer):
        require_provenance_module = MagicMock()
        monkeypatch.setattr(
            "trufo.api.tps.sign_c2pa.require_provenance_module",
            require_provenance_module,
        )

        with pytest.raises(ValueError, match="Unsupported cawg_identity_id"):
            signer(
                "remote-sign-key",
                b"input-media",
                assertions=[["cawg_identity", {"cawg_identity_id": "unknown"}]],
                tsa_api_key="tsa-key",
            )

        require_provenance_module.assert_not_called()

    @pytest.mark.parametrize("signer", _REMOTE_SIGNERS)
    def test_loads_configured_tsa_key_when_not_passed(self, monkeypatch, signer):
        calls = _install_fake_remote_stack(monkeypatch, signed=b"signed")
        key_types = []
        monkeypatch.setattr(
            "trufo.api.tps.sign_c2pa.load_api_key",
            lambda key_type: key_types.append(key_type) or "configured-tsa-key",
        )

        assert signer("remote-sign-key", b"input-media") == b"signed"
        assert key_types == [TrufoApiKey.TSA]
        assert calls["timestampers"][0].api_key == "configured-tsa-key"

    @pytest.mark.parametrize("signer", _REMOTE_SIGNERS)
    def test_requires_tsa_key_before_optional_imports(self, monkeypatch, signer):
        require_provenance_module = MagicMock()
        monkeypatch.setattr("trufo.api.tps.sign_c2pa.load_api_key", lambda _key: None)
        monkeypatch.setattr(
            "trufo.api.tps.sign_c2pa.require_provenance_module",
            require_provenance_module,
        )

        with pytest.raises(RuntimeError, match="TSA API key"):
            signer("remote-sign-key", b"input-media")

        require_provenance_module.assert_not_called()

    @pytest.mark.parametrize("signer", _REMOTE_SIGNERS)
    def test_assertions_without_cawg_identity_warns_and_continues(
        self, monkeypatch, signer, caplog
    ):
        _install_fake_remote_stack(monkeypatch, signed=b"signed")

        with caplog.at_level("WARNING", logger="trufo.api.tps.sign_c2pa"):
            result = signer(
                "remote-sign-key",
                b"input-media",
                assertions=[["ai_disclosure", {}]],
                tsa_api_key="tsa-key",
            )

        assert result == b"signed"
        assert "Gathered assertions are being input by the client" in caplog.text


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
            (_validate_assertions, [["cawg_identity", {"cawg_identity_id": "test"}]]),
            (
                _validate_assertions,
                [["cawg_identity", {"cawg_identity_id": "org_interim"}]],
            ),
        ],
    )
    def test_valid_inputs_pass(self, validator, value):
        validator(value)  # must not raise

    @pytest.mark.parametrize(
        "bad, match",
        [
            ([["cawg_identity", {}]], "requires a non-empty"),
            ([["cawg_identity", {"cawg_identity_id": ""}]], "requires a non-empty"),
            ([["cawg_identity", {"cawg_identity_id": "unknown"}]], "Unsupported"),
            ([["cawg_identity", []]], "requires a parameter object"),
        ],
    )
    def test_invalid_cawg_identity_params_rejected(self, bad, match):
        with pytest.raises(ValueError, match=match):
            _validate_assertions(bad)

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
