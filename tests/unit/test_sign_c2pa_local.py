# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""C2PA signing in Local mode: what the SDK hands the engine, and what it returns."""

import warnings

import pytest

from trufo import sign_c2pa_local, sign_c2pa_local_test
from trufo.api.endpoints import TRUFO_API_URL, TRUFO_API_URL_TEST
from trufo.c2pa import (
    ManifestSettings,
    RemoteManifestSettings,
    ThumbnailSettings,
    ThumbnailSize,
    WatermarkSettings,
)

KEY = "remote-sign-key"
MEDIA = b"media"
LOCAL_SIGNERS = [sign_c2pa_local, sign_c2pa_local_test]
# what every call hands the engine when nothing else is given
_DEFAULTS = {
    "actions": [],
    "assertions": [],
    "manifest_title": None,
    "ingredient_title": None,
    "branded_gp_id": None,
    "warning_stacklevel": 4,
}


@pytest.mark.parametrize(
    "signer, kwargs, engine_kwargs",
    [
        pytest.param(
            sign_c2pa_local_test,
            {
                "actions": [["publish", {}]],
                "assertions": [["cawg_identity", {"cawg_identity_id": "test"}]],
                "manifest_title": "signed.jpg",
                "ingredient_title": "photo.jpg",
                "manifest_settings": ManifestSettings(
                    thumbnail_settings=ThumbnailSettings(size=ThumbnailSize.HIGH)
                ),
                "branded_gp_id": "gp_x",
                "signed_input_policy": "keep",
                "signed_ingredient_policy": "keep",
                "skip_manifest_storage": True,
                "watermark_settings": WatermarkSettings("fast"),
            },
            {
                "actions": [["publish", {}]],
                "assertions": [["cawg_identity", {"cawg_identity_id": "test"}]],
                "trufo_api_url": TRUFO_API_URL_TEST,
                "test": True,
                "manifest_title": "signed.jpg",
                "ingredient_title": "photo.jpg",
                "branded_gp_id": "gp_x",
                "manifest_settings": {"thumbnail_settings": {"policy": "auto", "size": "high"}},
                "signed_input_policy": "keep",
                "signed_ingredient_policy": "keep",
                "skip_manifest_storage": True,
                "watermark_settings": {"profile": "fast"},
                "warning_stacklevel": 4,
            },
            id="test-all-fields",
        ),
        pytest.param(
            sign_c2pa_local,
            {
                "trufo_api_url": "https://api.trufo.example",
                "watermark_settings": WatermarkSettings(),
            },
            {
                **_DEFAULTS,
                "trufo_api_url": "https://api.trufo.example",
                "test": False,
                "watermark_settings": {"profile": "default"},
            },
            id="production-api-url",
        ),
        pytest.param(
            sign_c2pa_local,
            {},
            {**_DEFAULTS, "trufo_api_url": TRUFO_API_URL, "test": False},
            id="production-defaults",
        ),
        pytest.param(
            sign_c2pa_local_test,
            {},
            {**_DEFAULTS, "trufo_api_url": TRUFO_API_URL_TEST, "test": True},
            id="test-defaults",
        ),
    ],
)
def test_engine_call(fake_engine, signer, kwargs, engine_kwargs):
    assert signer(KEY, MEDIA, **kwargs) == fake_engine.signed
    (call,) = fake_engine.calls
    assert (call.function, call.args, call.kwargs) == (
        "generate_claim_remote",
        (KEY, MEDIA),
        engine_kwargs,
    )


@pytest.mark.parametrize("signer", LOCAL_SIGNERS)
def test_remote_manifest_settings_reach_the_engine(fake_engine, signer):
    settings = RemoteManifestSettings(fetch=False, allowed_hosts=["manifests.example.com"])
    signer(KEY, MEDIA, remote_manifest_settings=settings)
    assert fake_engine.calls[0].kwargs["remote_manifest_settings"] == {
        "fetch": False,
        "allowed_hosts": ["manifests.example.com"],
    }


@pytest.mark.parametrize("signer", LOCAL_SIGNERS)
def test_sdk_rejects_remote_manifest_settings_on_older_engine(fake_engine, signer):
    fake_engine.older()
    with pytest.raises(ValueError) as failure:
        signer(KEY, MEDIA, remote_manifest_settings=RemoteManifestSettings())
    assert str(failure.value) == (
        "UnsupportedSDKVersion: remote_manifest_settings requires trufo-provenance 2.4.1 or "
        "later. Please upgrade."
    )
    assert fake_engine.calls == []


@pytest.mark.parametrize("signer", LOCAL_SIGNERS)
def test_remote_manifest_settings_type(fake_engine, signer):
    with pytest.raises(TypeError, match="remote_manifest_settings"):
        signer(KEY, MEDIA, remote_manifest_settings={"fetch": False})
    assert fake_engine.calls == []


@pytest.mark.xfail(strict=True, reason="The type is to be checked before the engine is imported.")
@pytest.mark.parametrize("signer", LOCAL_SIGNERS)
def test_remote_manifest_settings_type_without_the_engine(fake_engine, signer):
    fake_engine.uninstall()
    with pytest.raises(TypeError, match="remote_manifest_settings"):
        signer(KEY, MEDIA, remote_manifest_settings={"fetch": False})


@pytest.mark.parametrize("signer", LOCAL_SIGNERS)
@pytest.mark.parametrize("argument", [None, "tsa_api_key", "trufo_tsa_url"])
def test_tsa_arguments_are_deprecated(fake_engine, signer, argument):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert signer(KEY, MEDIA, **({argument: "tsa-value"} if argument else {})) == b"signed"
    expected = (
        [
            (
                f"{argument} is deprecated and ignored; Trufo adds the timestamp when it signs.",
                __file__,
            )
        ]
        if argument
        else []
    )
    assert [(str(w.message), w.filename) for w in caught] == expected


@pytest.mark.parametrize("signer", LOCAL_SIGNERS)
def test_missing_engine(fake_engine, signer):
    fake_engine.uninstall()
    with pytest.raises(ImportError, match=r'"trufo\[local-sign-only\]".*"trufo\[local-full\]"'):
        signer(KEY, MEDIA)


@pytest.mark.parametrize("signer", LOCAL_SIGNERS)
def test_missing_engine_dependency_keeps_its_error(fake_engine, signer):
    fake_engine.break_import("tfprov.c2pa_generator.remote_orchestrator", "a_dependency")
    with pytest.raises(ModuleNotFoundError) as failure:
        signer(KEY, MEDIA)
    assert failure.value.name == "a_dependency"
