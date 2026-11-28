# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""C2PA signing in Cloud mode: the request body and the result, task submission, upload URLs
and the deprecated S3 helpers."""

import base64

import pytest

from trufo import (
    BindWatermarkResult,
    ExecutionMode,
    GetS3UploadURLResult,
    SignC2PAS3Result,
    TaskReceipt,
    TaskStatus,
    TaskType,
    bind_watermark,
    get_s3_upload_url,
    sign_c2pa_cloud,
    sign_c2pa_cloud_test,
    sign_c2pa_s3,
    sign_c2pa_via_s3,
    sign_c2pa_via_s3_test,
    submit_c2pa_sign,
)
from trufo.api.endpoints import TRUFO_API_URL, TRUFO_API_URL_TEST
from trufo.api.tps.sign_c2pa import get_c2pa_s3_upload_url, sign_c2pa_s3_test
from trufo.c2pa import (
    ManifestSettings,
    SignedIngredientPolicy,
    SignedInputPolicy,
    ThumbnailPolicy,
    ThumbnailSettings,
    ThumbnailSize,
)

KEY = "api-key"
MEDIA = b"media"
MEDIA_B64 = base64.b64encode(MEDIA).decode()
SIGNED = {"media_output": base64.b64encode(b"signed").decode()}
UPLOAD_URL = "https://upload.example/input"
DOWNLOAD_URL = "https://download.example/output"
UPLOAD = {
    "upload_url": UPLOAD_URL,
    "media_input_s3": "input-reference",
    "expires_at": 1770000000,
    "duration": "5m",
}


def test_request_body_and_result(trufo_api):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/c2pa/sign", SIGNED)
    actions = [
        ["publish", {}],
        ["redact", {"label": "c2pa.metadata", "reason": "c2pa.PII.present"}],
    ]
    assertions = [["cawg_identity", {"cawg_identity_id": "org_interim"}]]

    signed = sign_c2pa_cloud(
        KEY,
        MEDIA,
        actions=actions,
        assertions=assertions,
        manifest_title="signed.jpg",
        manifest_settings=ManifestSettings(
            thumbnail_settings=ThumbnailSettings(
                policy=ThumbnailPolicy.AUTO_NO_INGREDIENT, size=ThumbnailSize.HIGH
            ),
        ),
        branded_gp_id="gp_x",
        signed_input_policy=SignedInputPolicy.KEEP,
        signed_ingredient_policy=SignedIngredientPolicy.KEEP,
        skip_manifest_storage=True,
    )

    assert signed == b"signed"
    assert [r.json for r in trufo_api.requests] == [
        {
            "media_input": MEDIA_B64,
            "actions": actions,
            "assertions": assertions,
            "manifest_title": "signed.jpg",
            "manifest_settings": {
                "thumbnail_settings": {"policy": "auto_no_ingredient", "size": "high"}
            },
            "branded_gp_id": "gp_x",
            "signed_input_policy": "keep",
            "signed_ingredient_policy": "keep",
            "skip_manifest_storage": True,
        }
    ]


def test_cloud_test_signer_uses_test_host(trufo_api):
    trufo_api.answer("POST", f"{TRUFO_API_URL_TEST}/c2pa/sign", SIGNED)
    assert sign_c2pa_cloud_test(KEY, MEDIA) == b"signed"
    assert [r.json for r in trufo_api.requests] == [
        {"media_input": MEDIA_B64, "actions": [], "assertions": []}
    ]


@pytest.mark.parametrize(
    "operation, fields, task_type",
    [
        (
            sign_c2pa_cloud,
            {
                "branded_gp_id": "gp_x",
                "signed_input_policy": "keep",
                "signed_ingredient_policy": "keep",
                "skip_manifest_storage": True,
            },
            "c2pa_sign",
        ),
        (bind_watermark, {}, "watermark"),
    ],
)
def test_task_bytes_flow(trufo_api, task_answer, operation, fields, task_type):
    path = "/c2pa/sign" if task_type == "c2pa_sign" else "/bind/watermark"
    completed = task_answer(task_type=task_type)
    # fields a newer server adds are ignored
    completed["additional_status_field"] = "ignored"
    completed["result"]["additional_result_field"] = "ignored"
    trufo_api.answer("POST", f"{TRUFO_API_URL}/io/get-s3-upload-url", UPLOAD)
    trufo_api.answer("PUT", UPLOAD_URL, b"")
    trufo_api.answer("POST", f"{TRUFO_API_URL}{path}", (202, task_answer("queued", task_type)))
    trufo_api.answer("GET", f"{TRUFO_API_URL}/tasks/task-1", completed)
    trufo_api.answer("GET", DOWNLOAD_URL, b"output")

    result = operation(
        KEY, MEDIA, execution_mode=ExecutionMode.TASK, mime_type="image/jpeg", **fields
    )

    if task_type == "c2pa_sign":
        assert result == b"output"
    else:
        assert result == BindWatermarkResult(b"output", "watermark-1", "content-1")
    assert [(r.method, r.url.removeprefix(TRUFO_API_URL)) for r in trufo_api.requests] == [
        ("POST", "/io/get-s3-upload-url"),
        ("PUT", UPLOAD_URL),
        ("POST", path),
        ("GET", "/tasks/task-1"),
        ("GET", DOWNLOAD_URL),
    ]
    assert trufo_api.requests[0].json == {"mime_type": "image/jpeg"}
    assert trufo_api.requests[1].body == MEDIA
    submitted = {"media_input_s3": "input-reference", **fields, "execution_mode": "task"}
    if task_type == "c2pa_sign":
        submitted.update(actions=[], assertions=[])
    assert trufo_api.requests[2].json == submitted


@pytest.mark.parametrize("status", [202, 200])
def test_submit(trufo_api, task_answer, assert_frozen_fields, status):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/c2pa/sign", (status, task_answer("queued")))
    actions = [["publish", {}]]
    assertions = [["cawg_identity", {"cawg_identity_id": "org_interim"}]]
    if status != 202:
        with pytest.raises(ValueError, match="Expected task acceptance"):
            submit_c2pa_sign(KEY, "input-reference", actions, assertions)
        return

    receipt = submit_c2pa_sign(KEY, "input-reference", actions, assertions)

    assert receipt == TaskReceipt(
        "task-1", TaskType.C2PA_SIGN, TaskStatus.QUEUED, "2026-09-19T12:05:00Z", 60
    )
    assert (
        assert_frozen_fields(receipt)
        == "task_id task_type status startby_ts timeout_seconds".split()
    )
    (request,) = trufo_api.requests
    assert request.json == {
        "media_input_s3": "input-reference",
        "actions": actions,
        "assertions": assertions,
        "execution_mode": "task",
    }


@pytest.mark.parametrize(
    "get_upload_url, duration, body",
    [
        (get_s3_upload_url, None, {"mime_type": "image/jpeg"}),
        (get_c2pa_s3_upload_url, "5m", {"mime_type": "image/jpeg", "duration": "5m"}),
    ],
)
def test_upload_url(trufo_api, recwarn, assert_frozen_fields, get_upload_url, duration, body):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/io/get-s3-upload-url", UPLOAD)

    upload = get_upload_url(KEY, "image/jpeg", duration)

    assert upload == GetS3UploadURLResult(UPLOAD_URL, "input-reference", 1770000000, "5m")
    assert assert_frozen_fields(upload) == [
        "upload_url",
        "media_input_s3",
        "expires_at",
        "duration",
    ]
    (request,) = trufo_api.requests
    assert request.json == body
    deprecations = [str(w.message) for w in recwarn if w.category is DeprecationWarning]
    if get_upload_url is get_c2pa_s3_upload_url:
        assert deprecations == ["get_c2pa_s3_upload_url() is deprecated; use get_s3_upload_url()."]
    else:
        assert deprecations == []


def test_deprecated_s3_refusals():
    with (
        pytest.warns(DeprecationWarning, match="use submit_c2pa_sign"),
        pytest.raises(ValueError, match="S3 input requires"),
    ):
        sign_c2pa_s3(KEY, "input-reference")
    with pytest.raises(ValueError, match="REQUEST execution with bytes only"):
        sign_c2pa_s3_test(KEY, "input-reference")
    with pytest.raises(ValueError, match="REQUEST execution with bytes only"):
        sign_c2pa_via_s3_test(KEY, MEDIA, "image/jpeg")


@pytest.mark.parametrize("download_url", [DOWNLOAD_URL, None])
@pytest.mark.filterwarnings("ignore:get_c2pa_s3_upload_url:DeprecationWarning")
@pytest.mark.filterwarnings("ignore:sign_c2pa_s3:DeprecationWarning")
def test_deprecated_via_s3(trufo_api, task_answer, download_url):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/io/get-s3-upload-url", UPLOAD)
    trufo_api.answer("PUT", UPLOAD_URL, b"")
    trufo_api.answer("POST", f"{TRUFO_API_URL}/c2pa/sign", (202, task_answer("queued")))
    trufo_api.answer("GET", f"{TRUFO_API_URL}/tasks/task-1", task_answer(download_url=download_url))
    trufo_api.answer("GET", DOWNLOAD_URL, b"output")

    def sign():
        with pytest.warns(DeprecationWarning, match="use sign_c2pa_cloud"):
            return sign_c2pa_via_s3(
                KEY,
                MEDIA,
                "image/jpeg",
                actions=[["publish", {}]],
                assertions=[["cawg_identity", {"cawg_identity_id": "org_interim"}]],
                duration="5m",
                signed_input_policy="auto",
                signed_ingredient_policy="auto",
                execution_mode=ExecutionMode.TASK,
            )

    if download_url is None:
        with pytest.raises(ValueError, match="no longer available to download"):
            sign()
        return
    assert sign() == b"output"
    assert trufo_api.requests[0].json == {"mime_type": "image/jpeg", "duration": "5m"}
    assert trufo_api.requests[1].body == MEDIA
    assert trufo_api.requests[2].json == {
        "media_input_s3": "input-reference",
        "actions": [["publish", {}]],
        "assertions": [["cawg_identity", {"cawg_identity_id": "org_interim"}]],
        "signed_input_policy": "auto",
        "signed_ingredient_policy": "auto",
        "execution_mode": "task",
    }
    assert [r.url for r in trufo_api.requests[3:]] == [
        f"{TRUFO_API_URL}/tasks/task-1",
        DOWNLOAD_URL,
    ]


@pytest.mark.filterwarnings("ignore:sign_c2pa_s3:DeprecationWarning")
def test_deprecated_s3_result(trufo_api, task_answer, assert_frozen_fields):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/c2pa/sign", (202, task_answer("queued")))
    trufo_api.answer("GET", f"{TRUFO_API_URL}/tasks/task-1", task_answer())
    signed = sign_c2pa_s3(KEY, "input-reference", execution_mode=ExecutionMode.TASK)
    assert signed == SignC2PAS3Result(
        media_output_s3="output-reference",
        download_url=DOWNLOAD_URL,
        task_id="task-1",
        cid="content-1",
        wid="watermark-1",
    )
    assert assert_frozen_fields(signed) == "media_output_s3 download_url task_id cid wid".split()
