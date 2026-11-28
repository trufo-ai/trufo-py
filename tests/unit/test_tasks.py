# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Waiting for a task: its outcomes, the polling schedule, and what is refused before upload."""

import functools
import time

import pytest
import requests

from trufo import (
    BindWatermarkTaskResult,
    ExecutionMode,
    SignC2PATaskResult,
    TaskFailedError,
    TaskWaitTimeoutError,
    bind_watermark,
    bind_watermark_test,
    get_task,
    sign_c2pa_cloud,
    sign_c2pa_cloud_test,
    sign_c2pa_s3,
    sign_c2pa_via_s3,
    wait_for_task,
)
from trufo.api.endpoints import TRUFO_API_URL

KEY = "api-key"
TASK_URL = f"{TRUFO_API_URL}/tasks/task-1"


@pytest.mark.parametrize(
    "status, code, http_status, message, expected",
    [
        ("failed", "execution_timeout", 504, None, "Task task-1 failed: execution_timeout."),
        ("expired", "start_timeout", 503, None, "Task task-1 failed: start_timeout."),
        (
            "failed",
            "invalid_input",
            400,
            "Fragmented MP4 is not supported.",
            "Task task-1 failed: invalid_input. Fragmented MP4 is not supported.",
        ),
    ],
)
def test_terminal_failure(trufo_api, task_answer, status, code, http_status, message, expected):
    answer = task_answer(status)
    answer["error"] = {
        "code": code,
        "http_status": http_status,
        "message": message,
        "additional_error_field": "ignored",
    }
    trufo_api.answer("GET", TASK_URL, answer)

    with pytest.raises(TaskFailedError) as failure:
        wait_for_task(KEY, "task-1")

    assert failure.value.task_id == "task-1"
    assert (
        failure.value.task.error_code,
        failure.value.task.error_http_status,
        failure.value.task.error_message,
    ) == (code, http_status, message)
    assert str(failure.value) == expected
    # read once, never submitted again
    assert [r.method for r in trufo_api.requests] == ["GET"]


@pytest.mark.parametrize(
    "task_type, result_type, fields",
    [
        ("c2pa_sign", SignC2PATaskResult, "media_output_s3 download_url expires_ts cid wid"),
        ("watermark", BindWatermarkTaskResult, "media_output_s3 download_url expires_ts wid cid"),
    ],
)
def test_successful_task_requires_a_result(
    trufo_api, task_answer, assert_frozen_fields, task_type, result_type, fields
):
    trufo_api.answer("GET", TASK_URL, task_answer(task_type=task_type))
    # read once or waited for
    for completed in (get_task(KEY, "task-1"), wait_for_task(KEY, "task-1")):
        assert (completed.error_code, completed.error_http_status, completed.error_message) == (
            None,
            None,
            None,
        )
        # the result typed by the task type
        assert completed.result == result_type(
            media_output_s3="output-reference",
            download_url="https://download.example/output",
            expires_ts="2026-09-20T12:00:00Z",
            cid="content-1",
            wid="watermark-1",
        )
    info = (
        "task_id task_type status startby_ts timeout_seconds create_ts update_ts file_size_bytes "
        "file_mime_type start_ts finish_ts duration_ms progress error_code error_http_status "
        "result error_message"
    )
    assert assert_frozen_fields(completed) == info.split()
    assert assert_frozen_fields(completed.result) == f"{fields} warnings".split()

    answer = task_answer()
    answer["result"] = None
    trufo_api.answer("GET", TASK_URL, answer)
    with pytest.raises(ValueError, match="Succeeded task task-1 has no output reference."):
        wait_for_task(KEY, "task-1")


@pytest.mark.parametrize("wait_seconds", [600, 665])
def test_poll_schedule(trufo_api, task_answer, monkeypatch, wait_seconds):
    now = 0
    polls = []

    def sleep(seconds):
        nonlocal now
        assert seconds > 0
        now += seconds

    def poll(request):
        polls.append(now)
        return task_answer("queued")

    monkeypatch.setattr(time, "monotonic", lambda: now)
    monkeypatch.setattr(time, "sleep", sleep)
    trufo_api.answer("GET", TASK_URL, poll)

    with pytest.raises(TaskWaitTimeoutError):
        wait_for_task(KEY, "task-1", wait_seconds=wait_seconds)

    expected = list(range(11)) + list(range(20, 600, 10))
    if wait_seconds > 600:
        expected += [600, 660]
    assert polls == expected
    assert now == wait_seconds
    with pytest.raises(ValueError, match="Wait duration must be positive."):
        wait_for_task(KEY, "task-1", wait_seconds=0)


@pytest.mark.parametrize(
    "error, raised, message",
    [
        (requests.Timeout(), TaskWaitTimeoutError, "server execution was not cancelled"),
        (requests.ConnectionError(), RuntimeError, r"use get_task\(\) to check its status"),
    ],
)
def test_wait_errors(trufo_api, error, raised, message):
    trufo_api.answer("GET", TASK_URL, error)
    with pytest.raises(raised, match=message) as failure:
        wait_for_task(KEY, "task-1")
    assert "task-1" in str(failure.value)
    if raised is TaskWaitTimeoutError:
        assert failure.value.task_id == "task-1"
    # nothing submitted again
    assert [r.method for r in trufo_api.requests] == ["GET"]


TASK_BYTES = {"execution_mode": ExecutionMode.TASK, "mime_type": "image/jpeg"}


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.parametrize(
    "operation, error, message",
    [
        (
            functools.partial(sign_c2pa_cloud_test, execution_mode=ExecutionMode.TASK),
            ValueError,
            "REQUEST execution only",
        ),
        (
            functools.partial(bind_watermark_test, execution_mode=ExecutionMode.TASK),
            ValueError,
            "REQUEST execution only",
        ),
        (
            functools.partial(sign_c2pa_cloud, execution_mode=ExecutionMode.STREAM),
            NotImplementedError,
            "Stream",
        ),
        (
            functools.partial(bind_watermark, execution_mode=ExecutionMode.STREAM),
            NotImplementedError,
            "Stream",
        ),
        (
            functools.partial(sign_c2pa_cloud, execution_mode=ExecutionMode.TASK),
            ValueError,
            "mime_type",
        ),
        (
            functools.partial(bind_watermark, execution_mode=ExecutionMode.TASK),
            ValueError,
            "mime_type",
        ),
        (
            functools.partial(sign_c2pa_cloud, **TASK_BYTES, wait_seconds=0),
            ValueError,
            "Wait duration",
        ),
        (
            functools.partial(bind_watermark, **TASK_BYTES, wait_seconds=0),
            ValueError,
            "Wait duration",
        ),
        (
            functools.partial(
                sign_c2pa_via_s3,
                mime_type="image/jpeg",
                execution_mode=ExecutionMode.TASK,
                wait_seconds=0,
            ),
            ValueError,
            "Wait duration",
        ),
        (
            functools.partial(sign_c2pa_s3, execution_mode=ExecutionMode.TASK, wait_seconds=0),
            ValueError,
            "Wait duration",
        ),
    ],
)
def test_execution_mode_refusals(operation, error, message):
    # refused before any upload: a request would fail the test
    with pytest.raises(error, match=message):
        operation(KEY, b"input")


def test_task_id_is_escaped(trufo_api, task_answer):
    # a request to any other path is unscripted
    trufo_api.answer("GET", f"{TRUFO_API_URL}/tasks/..%2Fcontent%2Fget%3Fx%23y", task_answer())
    assert get_task(KEY, "../content/get?x#y").task_id == "task-1"
