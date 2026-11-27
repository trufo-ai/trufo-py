# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What the signers refuse before they send anything or import the engine, and what they send
unchanged."""

import copy
import functools
import logging
import warnings

import pytest

from trufo import (
    ExecutionMode,
    sign_c2pa_cloud,
    sign_c2pa_cloud_test,
    sign_c2pa_local,
    sign_c2pa_local_test,
    submit_c2pa_sign,
)
from trufo.api.endpoints import TRUFO_API_URL_TEST
from trufo.c2pa import ManifestSettings

KEY = "api-key"
MEDIA = b"media"

# every signer; a request reaching Trufo or the engine fails the test (the engine is uninstalled)
SIGNERS = [
    pytest.param(sign_c2pa_cloud, id="cloud"),
    pytest.param(
        functools.partial(
            sign_c2pa_cloud, execution_mode=ExecutionMode.TASK, mime_type="image/png"
        ),
        id="cloud-task",
    ),
    pytest.param(sign_c2pa_cloud_test, id="cloud-test"),
    pytest.param(submit_c2pa_sign, id="submit"),
    pytest.param(sign_c2pa_local, id="local"),
    pytest.param(sign_c2pa_local_test, id="local-test"),
]


def check(trufo_api, expected, **entries):
    """Sign ``entries`` (actions, assertions) with sign_c2pa_cloud_test: sent unchanged when
    ``expected`` is None, else refused before sending with ``expected``, an (exception type,
    message pattern) pair."""
    if expected is not None:
        with pytest.raises(expected[0], match=expected[1]):
            sign_c2pa_cloud_test(KEY, MEDIA, **entries)
        return
    trufo_api.answer("POST", f"{TRUFO_API_URL_TEST}/c2pa/sign", {"media_output": ""})
    expected = copy.deepcopy(entries)
    sign_c2pa_cloud_test(KEY, MEDIA, **entries)
    (request,) = trufo_api.requests
    for name, value in expected.items():
        assert request.json[name] == value


def _redact(label, reason="c2pa.PII.present"):
    """A redact action entry."""
    return ["redact", {"label": label, "reason": reason}]


@pytest.mark.parametrize("signer", SIGNERS)
@pytest.mark.parametrize(
    "actions, message",
    [
        (5, "actions must be a list"),
        ("redact", "actions must be a list"),
        ({"redact": {}}, "actions must be a list"),
        ([[]], "Invalid action entry"),
        ([[123, {}]], "Invalid action entry"),
        ([["not_an_action", {}]], "Invalid action entry"),
        ([["redact"]], "Invalid action entry"),
        ([_redact("c2pa.metadata") + ["extra"]], "Invalid action entry"),
    ],
)
def test_malformed_actions(fake_engine, signer, actions, message):
    fake_engine.uninstall()
    with pytest.raises(ValueError, match=message):
        signer(KEY, MEDIA, actions=actions)


@pytest.mark.parametrize(
    "assertions",
    [
        [["not_an_assertion", {}]],
        [[]],
    ],
)
def test_malformed_assertions(trufo_api, assertions):
    check(trufo_api, (ValueError, "Invalid assertion entry"), assertions=assertions)


@pytest.mark.parametrize(
    "params, expected",
    [
        ({}, (ValueError, "requires a non-empty 'cawg_identity_id'")),
        ({"cawg_identity_id": ""}, (ValueError, "requires a non-empty 'cawg_identity_id'")),
        ([], (ValueError, "requires a parameter object")),
        # the id is checked by Trufo
        ({"cawg_identity_id": "ica:any-id"}, None),
    ],
)
def test_cawg_identity_needs_an_id(trufo_api, params, expected):
    check(trufo_api, expected, assertions=[["cawg_identity", params]])


@pytest.mark.parametrize(
    "actions, expected",
    [
        *[
            ([_redact(label)], None)
            for label in (
                "c2pa.metadata",
                "cawg.metadata",
                "cawg.training-mining",
                "cawg.identity",
                "cawg.metadata__2",
            )
        ],
        *[
            ([_redact(label)], (ValueError, "Invalid redaction entry"))
            for label in (
                "c2pa.hash.data",
                "c2pa.actions.v2",
                # the list is enumerated, not a namespace
                "cawg.something-new",
                "c2pa.ai-disclosure",
                "ai.trufo.identity",
                "c2pa.metadata__abc",
                "c2pa.metadata__0",
                "c2pa.metadata__00",
                "c2pa.metadata__01",
                "c2pa.metadata__-1",
            )
        ],
        *[
            ([_redact(label)], (ValueError, "non-empty 'label'"))
            for label in ("", None, 123, ["c2pa.metadata"])
        ],
        *[
            ([["redact", params]], (ValueError, "Invalid redact action parameters"))
            for params in ("c2pa.metadata", None, 123, ["c2pa.metadata"])
        ],
        (
            [_redact("c2pa.metadata"), _redact("c2pa.metadata", "c2pa.invalid.data")],
            (ValueError, "Duplicate redaction target"),
        ),
        # the documented way to redact every instance of a repeated label
        ([_redact("c2pa.metadata"), _redact("c2pa.metadata__1")], None),
        (
            [
                _redact("c2pa.metadata"),
                _redact("cawg.metadata", "c2pa.trade-secret.present"),
                _redact("cawg.training-mining", "com.acme.policy"),
            ],
            None,
        ),
    ],
)
def test_redact_labels(trufo_api, actions, expected):
    check(trufo_api, expected, actions=actions)


@pytest.mark.parametrize(
    "reason, expected",
    [
        *[
            (reason, None)
            for reason in (
                "c2pa.PII.present",
                "c2pa.invalid.data",
                "c2pa.trade-secret.present",
                "c2pa.government.confidential",
                "com.acme.gdpr-request",
            )
        ],
        *[
            (reason, (ValueError, "non-empty 'reason'"))
            for reason in ("", "   ", None, 123, ["c2pa.PII.present"])
        ],
        *[
            (reason, (ValueError, "Invalid redaction reason"))
            for reason in (
                # surrounding whitespace, which would pass as a custom reason
                " c2pa.PII.present",
                "c2pa.PII.present ",
                "\tc2pa.PII.present",
                # the c2pa namespace, in any case, holds only the presets
                "C2PA.PII.present",
                "C2pa.invalid.data",
                "c2PA",
                "c2pa.not-a-real-reason",
            )
        ],
    ],
)
def test_redact_reasons(trufo_api, reason, expected):
    check(trufo_api, expected, actions=[_redact("c2pa.metadata", reason)])


@pytest.mark.parametrize(
    "actions, expected",
    [
        *[
            ([["watermark", params]], None)
            for params in (
                {},
                {"effort_policy": "require"},
                {"effort_policy": "require_if_supported"},
                {"effort_policy": "best_effort"},
                {"effort": "require"},
                {"mode": "provenance"},
                {"wid_allocation_mode": "per_ai_system"},
            )
        ],
        *[
            ([["watermark", params]], (ValueError, message))
            for params, message in (
                ({"effort_policy": "maybe"}, "effort_policy"),
                ({"effort_policy": True}, "effort_policy"),
                ({"effort": "maybe"}, "effort_policy"),
                ({"effort": "require", "effort_policy": "require"}, "not both"),
                ({"apply": True}, "replaced by 'effort_policy'"),
                ({"mode": "attestation"}, "mode"),
                ({"wid_allocation_mode": "provenance"}, "WatermarkIDAllocationMode"),
                ({"mode": "provenance", "wid_allocation_mode": "per_embed"}, "'mode', not both"),
                ({"ai_compliance_label": "ai_generated"}, "Unsupported watermark parameter"),
                (
                    {"mode": "provenance", "ai_compliance_label": "ai_generated"},
                    "Unsupported watermark parameter",
                ),
                ({"wid_package": {"wid": "x"}}, "Unsupported watermark parameter"),
                ({"effort_policy": "require", "nonsense": 1}, "Unsupported watermark parameter"),
                (None, "parameter object"),
            )
        ],
        ([["watermark", {}], ["watermark", {}]], (ValueError, "At most one watermark action")),
    ],
)
def test_watermark_action(trufo_api, actions, expected):
    check(trufo_api, expected, actions=actions)


@pytest.mark.parametrize(
    "params, message",
    [
        *[
            ({"mode": "compliance", "effort_policy": effort}, "Compliance watermarking")
            for effort in ("require", "require_if_supported", "best_effort")
        ],
        ({"wid_allocation_mode": "per_asset"}, "Per-asset watermark ID allocation"),
    ],
)
def test_unsupported_watermark_modes(trufo_api, params, message):
    check(trufo_api, (NotImplementedError, message), actions=[["watermark", params]])


@pytest.mark.parametrize("signer", SIGNERS)
@pytest.mark.parametrize(
    "argument, enum_name",
    [
        ("signed_input_policy", "SignedInputPolicy"),
        ("signed_ingredient_policy", "SignedIngredientPolicy"),
    ],
)
def test_invalid_policies(fake_engine, signer, argument, enum_name):
    fake_engine.uninstall()
    with pytest.raises(ValueError, match=enum_name):
        signer(KEY, MEDIA, **{argument: "maybe"})


@pytest.mark.parametrize("field", ["manifest_title", "ingredient_title"])
def test_duplicate_manifest_settings(field):
    with pytest.raises(ValueError, match=f"duplicates direct field.*{field}"):
        sign_c2pa_cloud(
            KEY, MEDIA, manifest_settings=ManifestSettings(**{field: "a"}), **{field: "b"}
        )


@pytest.mark.parametrize("signer", [sign_c2pa_local, sign_c2pa_local_test])
@pytest.mark.parametrize(
    "kwargs, error, message",
    [
        ({"assertions": [["cawg_identity", {"cawg_identity_id": ""}]]}, ValueError, "non-empty"),
        ({"watermark_settings": {}}, TypeError, "WatermarkSettings"),
    ],
)
def test_local_checks_precede_the_engine(fake_engine, signer, kwargs, error, message):
    fake_engine.uninstall()
    with pytest.raises(error, match=message):
        signer(KEY, MEDIA, **kwargs)


def test_valid_entries_are_sent_unchanged(trufo_api, caplog):
    actions = [
        ["publish", {}],
        ["transcode", {}],
        _redact("c2pa.metadata"),
        ["watermark", {"effort_policy": "best_effort"}],
    ]
    assertions = [["ai_disclosure", {}], ["cawg_identity", {"cawg_identity_id": "org_interim"}]]
    with warnings.catch_warnings(), caplog.at_level(logging.DEBUG):
        warnings.simplefilter("error")
        check(trufo_api, None, actions=actions, assertions=assertions)
    assert caplog.records == []
