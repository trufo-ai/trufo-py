# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Watermark binding: embedding on Trufo's servers, reserving, embedding locally, committing."""

import base64
from types import SimpleNamespace

import pytest

from trufo import (
    BindReserveResult,
    BindWatermarkResult,
    ExecutionMode,
    TaskReceipt,
    TaskStatus,
    TaskType,
    bind_commit,
    bind_reserve,
    bind_reserve_test,
    bind_watermark,
    bind_watermark_test,
    submit_bind_watermark,
    watermark_media,
)
from trufo.api.endpoints import TRUFO_API_URL, TRUFO_API_URL_TEST
from trufo.c2pa import WatermarkSettings

KEY = "api-key"
MEDIA = b"media"
WID = "v1.001abcdef12"
MARKED = {"media_output": base64.b64encode(b"marked").decode(), "wid": WID, "cid": "c_1"}
PACKAGE = {"wid": WID, "expires_at": "2026-09-08T00:00:00+00:00", "added_later": "kept"}
PER_AI_SYSTEM = {
    "wid_allocation_mode": "per_ai_system",
    "ai_system_id": "aisys_1",
    "ai_involvement": "ai_generated",
}


def test_bind_watermark(trufo_api, assert_frozen_fields):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/bind/watermark", MARKED)
    marked = bind_watermark(KEY, MEDIA)
    assert marked == BindWatermarkResult(b"marked", WID, "c_1")
    assert assert_frozen_fields(marked) == ["media", "wid", "cid"]
    assert [r.json for r in trufo_api.requests] == [
        {"media_input": base64.b64encode(MEDIA).decode()}
    ]


@pytest.mark.parametrize(
    "bind, argument, kwargs, api_url, path",
    [
        (bind_watermark, MEDIA, {}, TRUFO_API_URL, "/bind/watermark"),
        (
            bind_watermark,
            MEDIA,
            {"execution_mode": ExecutionMode.TASK},
            TRUFO_API_URL,
            "/bind/watermark",
        ),
        (bind_watermark_test, MEDIA, {}, TRUFO_API_URL_TEST, "/bind/watermark"),
        (bind_reserve, "image/jpeg", {}, TRUFO_API_URL, "/bind/reserve"),
        (bind_reserve_test, "image/jpeg", {}, TRUFO_API_URL_TEST, "/bind/reserve"),
    ],
)
def test_allocation_keys(trufo_api, task_answer, bind, argument, kwargs, api_url, path):
    if kwargs:
        answer = (202, task_answer("queued", "watermark"))
    else:
        answer = {**MARKED, "wid_package": PACKAGE}
    trufo_api.answer("POST", f"{api_url}{path}", answer)
    # the rest of a task
    upload = {"upload_url": "https://upload.example/input", "media_input_s3": "input-reference"}
    trufo_api.answer(
        "POST", f"{api_url}/io/get-s3-upload-url", {**upload, "expires_at": 1, "duration": "5m"}
    )
    trufo_api.answer("PUT", upload["upload_url"], b"")
    trufo_api.answer("GET", f"{api_url}/tasks/task-1", task_answer(task_type="watermark"))
    trufo_api.answer("GET", "https://download.example/output", b"marked")

    bind(
        KEY, argument, **kwargs, **({"mime_type": "image/jpeg"} if kwargs else {}), **PER_AI_SYSTEM
    )

    (sent,) = [r.json for r in trufo_api.requests if r.url == f"{api_url}{path}"]
    assert sent.items() >= PER_AI_SYSTEM.items()


def test_mode_and_refusals(trufo_api):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/bind/watermark", MARKED)
    bind_watermark(KEY, MEDIA, mode="provenance")
    for kwargs, error in [
        ({"mode": "compliance"}, NotImplementedError),
        ({"ai_compliance_label": "ai_generated"}, TypeError),
        ({"mode": "attestation"}, ValueError),
        ({"mode": "provenance", "wid_allocation_mode": "per_embed"}, ValueError),
        ({"wid_allocation_mode": "per_asset"}, NotImplementedError),
        ({"ai_involvement": "ai_assisted"}, ValueError),
    ]:
        with pytest.raises(error):
            bind_watermark(KEY, MEDIA, **kwargs)
    # the deprecated mode was sent, and each refusal sent nothing
    assert [r.json.get("mode") for r in trufo_api.requests] == ["provenance"]


def test_bind_reserve(trufo_api, assert_frozen_fields):
    trufo_api.answer(
        "POST", f"{TRUFO_API_URL}/bind/reserve", {"cid": "c_1", "wid_package": PACKAGE}
    )
    reserved = bind_reserve(KEY, "image/jpeg")
    assert reserved == BindReserveResult("c_1", WID, PACKAGE["expires_at"], PACKAGE)
    assert assert_frozen_fields(reserved) == ["cid", "wid", "expires_at", "wid_package"]
    assert [r.json for r in trufo_api.requests] == [{"mime_type": "image/jpeg"}]


@pytest.mark.parametrize("settings", [None, WatermarkSettings(), WatermarkSettings("fast")])
def test_watermark_media(fake_engine, settings):
    assert watermark_media(MEDIA, PACKAGE, watermark_settings=settings) == fake_engine.watermarked
    (call,) = fake_engine.calls
    assert (call.function, call.args) == (
        "embed",
        (MEDIA, SimpleNamespace(**PACKAGE)),
    )
    assert call.kwargs == ({} if settings is None else {"mode": settings.profile.value})


def test_watermark_media_refusals(fake_engine):
    fake_engine.uninstall()
    # the settings are checked first
    with pytest.raises(TypeError, match="WatermarkSettings"):
        watermark_media(MEDIA, PACKAGE, watermark_settings="fast")
    with pytest.raises(ImportError, match=r"trufo\[local-full\]"):
        watermark_media(MEDIA, PACKAGE)


def test_bind_commit(trufo_api):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/bind/commit", {"cid": "c_1", "wid": WID})
    assert bind_commit(KEY, "c_1", WID, manifest_bytes=b"store") is None
    assert [r.json for r in trufo_api.requests] == [
        {"cid": "c_1", "wid": WID, "manifest": base64.b64encode(b"store").decode()}
    ]


@pytest.mark.parametrize(
    "sources",
    [{}, {"signed_media_bytes": b"signed media", "manifest_bytes": b"store"}],
)
def test_one_manifest_source(sources):
    with pytest.raises(
        ValueError, match="Provide exactly one of manifest_bytes or signed_media_bytes"
    ):
        bind_commit(KEY, "c_1", WID, **sources)


def test_signed_media_sends_only_the_store(trufo_api, fake_engine):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/bind/commit", {"cid": "c_1", "wid": WID})

    bind_commit(KEY, "c_1", WID, signed_media_bytes=b"signed media")

    assert [call.function for call in fake_engine.calls] == ["read_manifest_bytes"]
    # the store read from a file holding the media, and not the media
    assert [r.json for r in trufo_api.requests] == [
        {"cid": "c_1", "wid": WID, "manifest": base64.b64encode(b"store of signed media").decode()}
    ]


def test_submit_bind_watermark(trufo_api, task_answer):
    trufo_api.answer(
        "POST", f"{TRUFO_API_URL}/bind/watermark", (202, task_answer("queued", "watermark"))
    )
    receipt = submit_bind_watermark(KEY, "input-reference", **PER_AI_SYSTEM)
    assert receipt == TaskReceipt(
        "task-1", TaskType.WATERMARK, TaskStatus.QUEUED, "2026-09-19T12:05:00Z", 60
    )
    assert [r.json for r in trufo_api.requests] == [
        {"media_input_s3": "input-reference", **PER_AI_SYSTEM, "execution_mode": "task"}
    ]


@pytest.mark.parametrize("missing", ["engine", "bridge"])
def test_signed_media_needs_the_engine(fake_engine, missing):
    if missing == "engine":
        fake_engine.uninstall()
    else:
        fake_engine.bridge_available = False
    # refused before sending: a request would fail the test
    with pytest.raises(ImportError, match=r"trufo\[local-sign-only\]"):
        bind_commit(KEY, "c_1", WID, signed_media_bytes=b"signed media")
