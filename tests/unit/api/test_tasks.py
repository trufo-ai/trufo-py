# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Task transport boundaries: submit once, poll separately, retain the handle."""

from unittest.mock import Mock, patch

import pytest
import requests

from trufo import ExecutionMode, bind_watermark, bind_watermark_test, sign_c2pa, sign_c2pa_test
from trufo.api.tps.tasks import TaskFailed, TaskWaitTimeout, wait_for_task


def response(payload=None, *, status=200, content=b""):
    return Mock(status_code=status, json=Mock(return_value=payload), content=content)


def task(status="succeeded", task_type="c2pa_sign"):
    return {
        "task_id": "task-1", "task_type": task_type, "status": status,
        "startby_ts": "2026-09-19T12:05:00Z", "timeout_seconds": 60,
        "create_ts": "2026-09-19T12:00:00Z", "update_ts": "2026-09-19T12:00:01Z",
        "file_size_bytes": 123, "file_mime_type": "image/jpeg",
        "result": {
            "media_output_s3": "output-reference", "download_url": "https://output.example",
            "expires_ts": "2026-09-20T12:00:00Z", "cid": "content-1", "wid": "watermark-1",
        } if status == "succeeded" else None,
    }


@pytest.mark.parametrize("operation,task_type", [(sign_c2pa, "c2pa_sign"), (bind_watermark, "watermark")])
def test_bytes_task_uploads_submits_polls_downloads_without_leaking_api_key(operation, task_type):
    accepted = task("queued", task_type)
    upload = {"upload_url": "https://input.example", "media_input_s3": "input-reference",
              "expires_at": 1770000000, "duration": "5m"}
    with patch("requests.post", side_effect=[response(upload), response(accepted, status=202)]) as post, \
         patch("requests.put", return_value=response()) as put, \
         patch("requests.get", side_effect=[response(task(task_type=task_type)), response(content=b"output")]) as get:
        result = operation("secret-key", b"input", execution_mode=ExecutionMode.TASK,
                           mime_type="image/jpeg", trufo_api_url="https://selected.example")
    assert (result if task_type == "c2pa_sign" else result.media) == b"output"
    if task_type == "watermark":
        assert (result.wid, result.cid) == ("watermark-1", "content-1")
    assert post.call_count == 2
    assert post.call_args.kwargs["json"]["execution_mode"] == "task"
    assert post.call_args.kwargs["json"]["media_input_s3"] == "input-reference"
    assert "media_input" not in post.call_args.kwargs["json"]
    assert get.call_args_list[0].args[0] == "https://selected.example/tasks/task-1"
    assert put.call_args.kwargs["headers"] == {"Content-Type": "image/jpeg"}
    assert "headers" not in get.call_args.kwargs


@pytest.mark.parametrize("status,code", [("failed", "execution_timeout"), ("expired", "start_timeout")])
def test_terminal_failure_keeps_task_id_and_does_not_resubmit(status, code):
    payload = task(status)
    payload["error"] = {"code": code, "http_status": 504 if status == "failed" else 503}
    with patch("requests.get", return_value=response(payload)), patch("requests.post") as post:
        with pytest.raises(TaskFailed) as failure:
            wait_for_task("key", "task-1")
    assert failure.value.task_id == "task-1"
    assert failure.value.task.error.code == code
    post.assert_not_called()


def test_wait_timeout_preserves_handle_without_cancelling_task():
    with patch("requests.get", side_effect=requests.Timeout), patch("requests.post") as post:
        with pytest.raises(TaskWaitTimeout) as failure:
            wait_for_task("key", "task-1")
    assert failure.value.task_id == "task-1"
    assert "not cancelled" in str(failure.value)
    post.assert_not_called()


def test_explicit_modes_reject_before_upload():
    with patch("requests.post") as post, patch("requests.put") as put:
        for operation in (sign_c2pa_test, bind_watermark_test):
            with pytest.raises(ValueError, match="REQUEST execution only"):
                operation("key", b"input", execution_mode=ExecutionMode.TASK)
        with pytest.raises(NotImplementedError, match="Stream"):
            sign_c2pa("key", b"input", execution_mode=ExecutionMode.STREAM)
        with pytest.raises(ValueError, match="mime_type"):
            sign_c2pa("key", b"input", execution_mode=ExecutionMode.TASK)
    post.assert_not_called()
    put.assert_not_called()
