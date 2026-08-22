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
    TRUFO_API_URL,
    TRUFO_API_URL_TEST,
    TRUFO_TSA_URL,
)
from trufo.api.tps.sign_c2pa import (
    C2PAS3SignedOutput,
    C2PAS3Upload,
    _validate_actions,
    _validate_assertions,
    _validate_redact_action,
    get_c2pa_s3_upload_url,
    sign_c2pa,
    sign_c2pa_distributed,
    sign_c2pa_distributed_test,
    sign_c2pa_s3,
    sign_c2pa_s3_test,
    sign_c2pa_test,
    sign_c2pa_via_s3,
    sign_c2pa_via_s3_test,
)
from trufo.c2pa import ThumbnailPolicy, ThumbnailSettings, ThumbnailSize
from trufo.util.credentials import TrufoApiKey
from trufo.api.headers import sdk_headers


def _expected_headers(api_key: str) -> dict[str, str]:
    """Headers the SDK is expected to send.

    Built via sdk_headers rather than hard-coded so a version bump does not
    break every assertion; what the tests pin is that the API key is correct
    and that the version headers are sent at all.
    """
    return sdk_headers(api_key)




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


class TestServerWarnings:
    """Server-side notices surface as catchable TrufoServerWarning."""

    @patch("trufo.api.tps.sign_c2pa.requests.post")
    def test_response_warnings_are_emitted(self, mock_post):
        import warnings as _warnings

        from trufo.util.warnings import TrufoServerWarning

        mock_post.return_value = _mock_response(
            {
                "media_output": base64.b64encode(b"signed").decode("utf-8"),
                "warnings": ["Watermarking is not supported for 'application/pdf' media."],
            }
        )

        with _warnings.catch_warnings(record=True) as caught:
            _warnings.simplefilter("always", TrufoServerWarning)
            result = sign_c2pa("prod-key", b"input-media")

        assert result == b"signed"
        assert len(caught) == 1
        assert issubclass(caught[0].category, TrufoServerWarning)
        assert "not supported" in str(caught[0].message)

    @patch("trufo.api.tps.sign_c2pa.requests.post")
    def test_no_warnings_when_absent(self, mock_post):
        import warnings as _warnings

        mock_post.return_value = _mock_response(
            {"media_output": base64.b64encode(b"signed").decode("utf-8")}
        )

        with _warnings.catch_warnings(record=True) as caught:
            _warnings.simplefilter("always")
            sign_c2pa("prod-key", b"input-media")

        assert caught == []


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
            actions=[
                ["publish", {}],
                ["redact", {"label": "c2pa.metadata", "reason": "c2pa.PII.present"}],
            ],
            assertions=[["cawg_identity", {"cawg_identity_id": "org_interim"}]],
            thumbnail_settings=ThumbnailSettings(
                policy=ThumbnailPolicy.AUTO_NO_INGREDIENT,
                size=ThumbnailSize.HIGH,
            ),
        )

        assert result == signed
        mock_post.assert_called_once_with(
            TRUFO_API_URL + TPS_C2PA_SIGN,
            json={
                "media_input": base64.b64encode(b"input-media").decode(),
                "actions": [
                    ["publish", {}],
                    ["redact", {"label": "c2pa.metadata", "reason": "c2pa.PII.present"}],
                ],
                "assertions": [["cawg_identity", {"cawg_identity_id": "org_interim"}]],
                "thumbnail_settings": {
                    "policy": "auto_no_ingredient",
                    "size": "high",
                },
            },
            headers=_expected_headers("prod-key"),
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
            TRUFO_API_URL_TEST + TPS_C2PA_SIGN,
            json={
                "media_input": base64.b64encode(b"input-media").decode(),
                "actions": [],
                "assertions": [],
            },
            headers=_expected_headers("test-key"),
            timeout=60,
        )

    @pytest.mark.parametrize("signer", [sign_c2pa, sign_c2pa_test])
    @patch("trufo.api.tps.sign_c2pa.requests.post")
    def test_assertions_without_cawg_identity_pass_silently(self, mock_post, signer, caplog):
        """CAWG identity is optional: no warning is emitted when absent."""
        signed = b"signed"
        mock_post.return_value = _mock_response(
            {"media_output": base64.b64encode(signed).decode("utf-8")}
        )

        with caplog.at_level("WARNING"):
            result = signer(
                "api-key",
                b"input-media",
                assertions=[["ai_disclosure", {}]],
            )

        assert result == signed
        assert caplog.records == []


class TestRemoteC2PASigning:
    """Remote C2PA signing wrappers delegate to the tfprov orchestrator."""

    _REMOTE_SIGNERS = [sign_c2pa_distributed, sign_c2pa_distributed_test]

    def test_test_signing_delegates_with_test_flag(self, monkeypatch):
        calls = _install_fake_remote_stack(monkeypatch, signed=b"signed-test")

        result = sign_c2pa_distributed_test(
            "remote-sign-key",
            b"input-media",
            actions=[["publish", {}]],
            assertions=[["cawg_identity", {"cawg_identity_id": "test"}]],
            tsa_api_key="tsa-key",
            thumbnail_settings=ThumbnailSettings(size=ThumbnailSize.HIGH),
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
        assert kwargs["trufo_api_url"] == TRUFO_API_URL_TEST
        assert kwargs["ocsp_stapler"] is calls["ocsp_stapler"]
        assert kwargs["thumbnail_settings"] == {"policy": "auto", "size": "high"}

        # a single timestamper is built with the resolved key and SDK TSA default
        assert [ts.api_key for ts in calls["timestampers"]] == ["tsa-key"]
        assert calls["timestampers"][0].url == TRUFO_TSA_URL
        assert kwargs["timestamper"] is calls["timestampers"][0]

    def test_prod_signing_delegates_with_endpoint_overrides(self, monkeypatch):
        calls = _install_fake_remote_stack(monkeypatch, signed=b"signed-prod")

        result = sign_c2pa_distributed(
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

        sign_c2pa_distributed("remote-sign-key", b"input-media", tsa_api_key="tsa-key")

        kwargs = calls["generate_claim_remote"]["kwargs"]
        assert kwargs["test"] is False
        assert kwargs["trufo_api_url"] == TRUFO_API_URL
        assert calls["timestampers"][0].url == TRUFO_TSA_URL

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

        with pytest.raises(ValueError, match="requires a non-empty"):
            signer(
                "remote-sign-key",
                b"input-media",
                assertions=[["cawg_identity", {"cawg_identity_id": ""}]],
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
    def test_assertions_without_cawg_identity_pass_silently(self, monkeypatch, signer, caplog):
        """CAWG identity is optional: no warning is emitted when absent."""
        _install_fake_remote_stack(monkeypatch, signed=b"signed")

        with caplog.at_level("WARNING"):
            result = signer(
                "remote-sign-key",
                b"input-media",
                assertions=[["ai_disclosure", {}]],
                tsa_api_key="tsa-key",
            )

        assert result == b"signed"
        assert caplog.records == []


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
            headers=_expected_headers("api-key"),
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
            headers=_expected_headers("prod-key"),
            timeout=60,
        )

    @patch("trufo.api.tps.sign_c2pa.requests.post")
    def test_sign_c2pa_s3_test_posts_to_test_endpoint(self, mock_post):
        mock_post.return_value = _mock_response({"media_output_s3": "https://download.example"})

        result = sign_c2pa_s3_test("test-key", "signed-input-reference")

        assert result == C2PAS3SignedOutput(media_output_s3="https://download.example")
        mock_post.assert_called_once_with(
            TRUFO_API_URL_TEST + TPS_C2PA_SIGN,
            json={
                "media_input_s3": "signed-input-reference",
                "actions": [],
                "assertions": [],
            },
            headers=_expected_headers("test-key"),
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
        mock_get_upload_url.assert_called_once_with(
            "prod-key",
            "image/jpeg",
            duration="5m",
            trufo_api_url=TRUFO_API_URL,
        )
        mock_put.assert_called_once_with(
            "https://upload.example",
            data=b"input-media",
            headers={"Content-Type": "image/jpeg"},
            timeout=60,
        )
        mock_put.return_value.raise_for_status.assert_called_once_with()
        mock_sign_s3.assert_called_once_with(
            "prod-key",
            "signed-input-reference",
            actions=[["publish", {}]],
            assertions=[["cawg_identity", {"cawg_identity_id": "org_interim"}]],
            manifest_title=None,
            ingredient_title=None,
            thumbnail_settings=None,
            trufo_api_url=TRUFO_API_URL,
        )
        mock_get.assert_called_once_with("https://download.example", timeout=60)
        mock_get.return_value.raise_for_status.assert_called_once_with()

    @pytest.mark.parametrize(
        "trufo_api_url",
        [TRUFO_API_URL, "https://api.trufo.example"],
        ids=["default", "supplied"],
    )
    @patch("trufo.api.tps.sign_c2pa.requests.get")
    @patch("trufo.api.tps.sign_c2pa.requests.put")
    @patch("trufo.api.tps.sign_c2pa.requests.post")
    def test_hosted_signers_use_selected_api_url(
        self,
        mock_post,
        _mock_put,
        mock_get,
        trufo_api_url,
    ):
        mock_post.side_effect = [
            _mock_response({"media_output": base64.b64encode(b"direct-signed").decode()}),
            _mock_response(
                {
                    "upload_url": "https://upload.example",
                    "media_input_s3": "signed-input-reference",
                    "expires_at": 1770000000,
                    "duration": "5m",
                }
            ),
            _mock_response({"media_output_s3": "https://download.example"}),
        ]
        mock_get.return_value.content = b"s3-signed"

        assert (
            sign_c2pa("prod-key", b"input-media", trufo_api_url=trufo_api_url) == b"direct-signed"
        )
        assert (
            sign_c2pa_via_s3(
                "prod-key",
                b"input-media",
                "image/jpeg",
                trufo_api_url=trufo_api_url,
            )
            == b"s3-signed"
        )

        assert [call.args[0] for call in mock_post.call_args_list] == [
            trufo_api_url + TPS_C2PA_SIGN,
            trufo_api_url + TPS_C2PA_GET_S3_URL,
            trufo_api_url + TPS_C2PA_SIGN,
        ]

    @patch("trufo.api.tps.sign_c2pa.requests.get")
    @patch("trufo.api.tps.sign_c2pa.requests.put")
    @patch("trufo.api.tps.sign_c2pa.sign_c2pa_s3_test")
    @patch("trufo.api.tps.sign_c2pa.get_c2pa_s3_upload_url")
    def test_sign_c2pa_via_s3_test_uses_test_signer(
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

        result = sign_c2pa_via_s3_test("test-key", b"input-media", "image/jpeg")

        assert result == b"signed-media"
        mock_sign_test_s3.assert_called_once_with(
            "test-key",
            "signed-input-reference",
            actions=None,
            assertions=None,
            manifest_title=None,
            ingredient_title=None,
            thumbnail_settings=None,
            trufo_api_url=TRUFO_API_URL_TEST,
        )

    @pytest.mark.parametrize("signer", [sign_c2pa_s3, sign_c2pa_s3_test])
    @patch("trufo.api.tps.sign_c2pa.requests.post")
    def test_s3_assertions_without_cawg_identity_pass_silently(self, mock_post, signer, caplog):
        """CAWG identity is optional: no warning is emitted when absent."""
        mock_post.return_value = _mock_response({"media_output_s3": "https://download.example"})

        with caplog.at_level("WARNING"):
            result = signer(
                "api-key",
                "signed-input-reference",
                assertions=[["ai_disclosure", {}]],
            )

        assert result == C2PAS3SignedOutput(media_output_s3="https://download.example")
        assert caplog.records == []


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
            # the id is an opaque server-validated string; any non-empty value
            # passes client-side
            (
                _validate_assertions,
                [["cawg_identity", {"cawg_identity_id": "ica:future-id"}]],
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
            # the resolved envelope is server-injected only; user input is rejected
            (
                _validate_assertions,
                "assertion",
                [["resolved", {"label": "ai.trufo.identity", "assertion": {}}]],
            ),
        ],
    )
    def test_invalid_entries_rejected(self, validator, entry_type, bad):
        with pytest.raises(ValueError, match=f"Invalid {entry_type} entry"):
            validator(bad)

    @pytest.mark.parametrize(
        "params",
        [
            {},
            {"effort_policy": "require"},
            {"effort_policy": "require_if_supported"},
            {"effort_policy": "best_effort"},
            {"effort": "require"},  # deprecated alias, still accepted
            {"mode": "provenance"},
            {"mode": "compliance", "ai_compliance_label": "ai_generated"},
            {"mode": "compliance", "ai_compliance_label": "ai_modified"},
            {"mode": "compliance", "ai_compliance_label": "undeclared"},
            {"mode": "compliance", "ai_compliance_label": "ai_generated", "effort_policy": "best_effort"},
        ],
    )
    def test_valid_watermark_action_accepted(self, params):
        _validate_actions([["watermark", params]])  # must not raise

    @pytest.mark.parametrize(
        "params, match",
        [
            ({"effort_policy": "maybe"}, "effort_policy"),
            ({"effort_policy": True}, "effort_policy"),
            ({"effort": "maybe"}, "effort_policy"),
            ({"effort": "require", "effort_policy": "require"}, "not both"),
            ({"apply": True}, "replaced by 'effort_policy'"),
            ({"mode": "attestation"}, "mode"),
            ({"mode": "compliance"}, "ai_compliance_label"),
            ({"mode": "compliance", "ai_compliance_label": "none"}, "ai_compliance_label"),
            ({"ai_compliance_label": "ai_generated"}, "compliance-mode"),
            ({"mode": "provenance", "ai_compliance_label": "ai_generated"}, "compliance-mode"),
            ({"wid_package": {"wid": "x"}}, "Unsupported watermark parameter"),
            ({"effort_policy": "require", "nonsense": 1}, "Unsupported watermark parameter"),
            (None, "parameter object"),
        ],
    )
    def test_invalid_watermark_params_rejected(self, params, match):
        with pytest.raises(ValueError, match=match):
            _validate_actions([["watermark", params]])

    def test_duplicate_watermark_action_rejected(self):
        with pytest.raises(ValueError, match="At most one watermark action"):
            _validate_actions([["watermark", {}], ["watermark", {}]])

    def _redact_actions(self, label, reason="c2pa.PII.present"):
        """An actions list holding a single redact entry."""
        params = {"label": label}
        if reason is not None:
            params["reason"] = reason
        return [["redact", params]]

    @pytest.mark.parametrize(
        "label",
        [
            "c2pa.metadata",
            "cawg.metadata",
            "cawg.training-mining",
            "cawg.identity",
            "cawg.metadata__2",
        ],
    )
    def test_each_redactable_label_accepted(self, label):
        _validate_actions(self._redact_actions(label))  # must not raise

    @pytest.mark.parametrize(
        "bad",
        [
            "c2pa.hash.data",
            "c2pa.actions.v2",
            # the allowlist is enumerated, not a namespace prefix
            "cawg.something-new",
            "c2pa.ai-disclosure",
            "ai.trufo.identity",
            "c2pa.metadata__abc",
            "c2pa.metadata__0",
            "c2pa.metadata__00",
            "c2pa.metadata__01",
            "c2pa.metadata__-1",
        ],
    )
    def test_invalid_redaction_labels_rejected(self, bad):
        with pytest.raises(ValueError, match="Invalid redaction entry"):
            _validate_actions(self._redact_actions(bad))

    @pytest.mark.parametrize("label", ["", None, 123, ["c2pa.metadata"]])
    def test_missing_or_non_string_label_rejected(self, label):
        with pytest.raises(ValueError, match="non-empty 'label'"):
            _validate_actions(self._redact_actions(label))

    def test_repeated_target_rejected(self):
        """The same assertion may not be targeted twice in one call."""
        actions = self._redact_actions("c2pa.metadata") + self._redact_actions(
            "c2pa.metadata", reason="c2pa.invalid.data"
        )
        with pytest.raises(ValueError, match="Duplicate redaction target"):
            _validate_actions(actions)

    def test_base_label_and_numbered_instance_are_distinct_targets(self):
        """The documented way to redact every instance of a repeated label."""
        actions = self._redact_actions("c2pa.metadata") + self._redact_actions("c2pa.metadata__1")
        _validate_actions(actions)  # must not raise

    @pytest.mark.parametrize("params", ["c2pa.metadata", None, 123, ["c2pa.metadata"]])
    def test_non_dict_params_rejected(self, params):
        with pytest.raises(ValueError, match="Invalid redact action parameters"):
            _validate_actions([["redact", params]])

    @pytest.mark.parametrize("reason", ["", "   ", None, 123, ["c2pa.PII.present"]])
    def test_missing_or_non_string_reason_rejected(self, reason):
        with pytest.raises(ValueError, match="non-empty 'reason'"):
            _validate_actions([["redact", {"label": "c2pa.metadata", "reason": reason}]])

    @pytest.mark.parametrize(
        "reason", [" c2pa.PII.present", "c2pa.PII.present ", "\tc2pa.PII.present"]
    )
    def test_padded_reason_rejected(self, reason):
        """Surrounding whitespace would miss the preset check and be forwarded as a
        custom value, failing server-side as an unregistered domain."""
        with pytest.raises(ValueError, match="Invalid redaction reason"):
            _validate_actions(self._redact_actions("c2pa.metadata", reason=reason))

    @pytest.mark.parametrize("reason", ["C2PA.PII.present", "C2pa.invalid.data", "c2PA"])
    def test_miscased_c2pa_namespace_rejected(self, reason):
        """The c2pa namespace is reserved, so a miscased preset is a bad reason
        rather than a custom value needing domain validation."""
        with pytest.raises(ValueError, match="Invalid redaction reason"):
            _validate_actions(self._redact_actions("c2pa.metadata", reason=reason))

    @pytest.mark.parametrize("actions", [5, "redact", {"redact": {}}])
    def test_non_list_actions_rejected(self, actions):
        with pytest.raises(ValueError, match="actions must be a list"):
            _validate_actions(actions)

    @pytest.mark.parametrize(
        "reason",
        [
            "c2pa.PII.present",
            "c2pa.invalid.data",
            "c2pa.trade-secret.present",
            "c2pa.government.confidential",
            "com.acme.gdpr-request",  # custom entity-namespaced value
        ],
    )
    def test_valid_redact_reason_accepted(self, reason):
        _validate_actions(self._redact_actions("c2pa.metadata", reason=reason))  # must not raise

    def test_reason_is_required(self):
        with pytest.raises(ValueError, match="non-empty 'reason'"):
            _validate_actions(self._redact_actions("c2pa.metadata", reason=None))

    def test_non_preset_c2pa_reason_rejected(self):
        with pytest.raises(ValueError, match="Invalid redaction reason"):
            _validate_actions(
                self._redact_actions("c2pa.metadata", reason="c2pa.not-a-real-reason"),
            )

    def test_redact_via_validate_redact_action_directly(self):
        _validate_redact_action(
            ["redact", {"label": "c2pa.metadata", "reason": "c2pa.PII.present"}]
        )  # must not raise

    @pytest.mark.parametrize(
        "entry",
        [
            ["redact"],  # missing params
            ["redact", {"label": "c2pa.metadata", "reason": "c2pa.PII.present"}, "extra"],
        ],
    )
    def test_malformed_redact_entry_shape_rejected(self, entry):
        """Every action entry must be exactly [name, params]; the generic
        shape check rejects malformed redact entries before name dispatch."""
        with pytest.raises(ValueError, match="Invalid action entry"):
            _validate_actions([entry])

    def test_several_redact_entries_allowed_each_with_its_own_reason(self):
        """One entry per assertion, each carrying its own reason."""
        actions = [
            ["redact", {"label": "c2pa.metadata", "reason": "c2pa.PII.present"}],
            ["redact", {"label": "cawg.metadata", "reason": "c2pa.trade-secret.present"}],
            ["redact", {"label": "cawg.training-mining", "reason": "com.acme.policy"}],
        ]
        _validate_actions(actions)  # must not raise
