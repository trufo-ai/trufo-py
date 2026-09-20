# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Explicit task submission, typed status, and synchronous waiting."""

import time
from dataclasses import dataclass, field, fields
from enum import Enum
from urllib.parse import quote

import requests

from trufo.api.endpoints import TRUFO_API_URL
from trufo.api.headers import sdk_headers
from trufo.util.warnings import emit_server_warnings


class ExecutionMode(str, Enum):
    REQUEST = "request"
    TASK = "task"
    STREAM = "stream"

    @staticmethod
    def validate(mode: str, *, test: bool = False) -> "ExecutionMode":
        selected = ExecutionMode(mode)
        if selected == ExecutionMode.STREAM:
            raise NotImplementedError("Stream execution is not supported.")
        if test and selected != ExecutionMode.REQUEST:
            raise ValueError("The test endpoint supports REQUEST execution only.")
        return selected


class TaskType(str, Enum):
    C2PA_SIGN = "c2pa_sign"
    WATERMARK = "watermark"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass(frozen=True)
class TaskReceipt:
    """Server receipt for an accepted task, not a completed result."""

    task_id: str
    task_type: TaskType
    status: TaskStatus
    startby_ts: str
    timeout_seconds: int


@dataclass(frozen=True)
class SignC2PATaskResult:
    """Signed output references, identifiers, and warnings; no media bytes."""

    media_output_s3: str
    download_url: str | None
    expires_ts: str
    cid: str | None = None
    wid: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BindWatermarkTaskResult:
    """Watermarked output references and identifiers; no media bytes."""

    media_output_s3: str
    download_url: str | None
    expires_ts: str
    wid: str
    cid: str | None = None


@dataclass(frozen=True)
class TaskInfo(TaskReceipt):
    """Task status, progress, result, and optional failure code/status.

    error_http_status describes the task failure, not the status-query response.
    """

    create_ts: str
    update_ts: str
    file_size_bytes: int
    file_mime_type: str
    start_ts: str | None = None
    finish_ts: str | None = None
    duration_ms: int | None = None
    progress: str | None = None
    error_code: str | None = None
    error_http_status: int | None = None
    result: SignC2PATaskResult | BindWatermarkTaskResult | None = None


class TaskFailedError(RuntimeError):
    """Waiting observed a failed or expired task; retains its status response."""

    def __init__(self, task: TaskInfo):
        self.task = task
        self.task_id = task.task_id
        code = task.error_code if task.error_code is not None else task.status.value
        super().__init__(f"Task {task.task_id} failed: {code}.")


class TaskWaitTimeoutError(TimeoutError):
    """The SDK stopped waiting; the server task was not cancelled."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Stopped waiting for task {task_id}; server execution was not cancelled. Use get_task() to check its status.")


def _parse_task_response(payload: dict, response_type):
    values = {f.name: payload[f.name] for f in fields(response_type) if f.name in payload}
    values["task_type"] = TaskType(values["task_type"])
    values["status"] = TaskStatus(values["status"])
    if response_type is TaskInfo and payload.get("error"):
        values["error_code"] = payload["error"]["code"]
        values["error_http_status"] = payload["error"]["http_status"]
    if values.get("result"):
        result_type = SignC2PATaskResult if values["task_type"] == TaskType.C2PA_SIGN else BindWatermarkTaskResult
        result = values["result"]
        values["result"] = result_type(**{f.name: result[f.name] for f in fields(result_type) if f.name in result})
    return response_type(**values)


def _submit_task(api_key: str, endpoint: str, body: dict, *, trufo_api_url: str) -> TaskReceipt:
    response = requests.post(trufo_api_url + endpoint, json={**body, "execution_mode": "task"},
                             headers=sdk_headers(api_key), timeout=60)
    response.raise_for_status()
    if response.status_code != 202:
        raise ValueError("Expected task acceptance (HTTP 202); check that the endpoint supports TASK execution.")
    return _parse_task_response(response.json(), TaskReceipt)


def get_task(api_key: str, task_id: str, *, trufo_api_url: str = TRUFO_API_URL) -> TaskInfo:
    """Read status from the same API region used to submit the task."""
    response = requests.get(trufo_api_url + "/tasks/" + quote(task_id, safe=""),
                            headers=sdk_headers(api_key), timeout=30)
    response.raise_for_status()
    return _parse_task_response(response.json(), TaskInfo)


def wait_for_task(api_key: str, task_id: str, *, wait_seconds: float = 600,
                  trufo_api_url: str = TRUFO_API_URL) -> TaskInfo:
    """Wait synchronously without retrying submission or server failures.

    Check immediately, then every second for 10 seconds, every 10 seconds until
    10 minutes, and every minute thereafter if the waiting budget permits.
    The local waiting budget is checked between HTTP polls; an in-flight poll
    has its own 30-second HTTP timeout. TaskWaitTimeoutError retains the task ID.
    """
    if wait_seconds <= 0:
        raise ValueError("Wait duration must be positive.")
    started = time.monotonic()
    deadline = started + wait_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TaskWaitTimeoutError(task_id)
        try:
            task = get_task(api_key, task_id, trufo_api_url=trufo_api_url)
        except requests.Timeout as exc:
            raise TaskWaitTimeoutError(task_id) from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Could not read task {task_id}; use get_task() to check its status.") from exc
        if task.status == TaskStatus.SUCCEEDED:
            if task.result is None:
                raise ValueError(f"Succeeded task {task_id} has no output reference.")
            if isinstance(task.result, SignC2PATaskResult):
                emit_server_warnings({"warnings": task.result.warnings})
            return task
        if task.status in (TaskStatus.FAILED, TaskStatus.EXPIRED):
            raise TaskFailedError(task)
        now = time.monotonic()
        elapsed = now - started
        interval = 1 if elapsed < 10 else 10 if elapsed < 600 else 60
        time.sleep(min(interval, max(0, deadline - now)))


def _download_task_output(task: TaskInfo) -> bytes:
    if task.result is None or task.result.download_url is None:
        raise ValueError(f"Output for task {task.task_id} is no longer available to download.")
    response = requests.get(task.result.download_url, timeout=120)
    response.raise_for_status()
    return response.content
