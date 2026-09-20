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
class TaskAccepted:
    task_id: str
    task_type: TaskType
    status: TaskStatus
    startby_ts: str
    timeout_seconds: int


@dataclass(frozen=True)
class TaskError:
    code: str
    http_status: int


@dataclass(frozen=True)
class TaskOutput:
    media_output_s3: str
    download_url: str | None
    expires_ts: str


@dataclass(frozen=True)
class C2PASignTaskResult(TaskOutput):
    cid: str | None = None
    wid: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WatermarkTaskResult(TaskOutput):
    wid: str
    cid: str | None = None


@dataclass(frozen=True)
class TaskInfo(TaskAccepted):
    create_ts: str
    update_ts: str
    file_size_bytes: int
    file_mime_type: str
    start_ts: str | None = None
    finish_ts: str | None = None
    duration_ms: int | None = None
    progress: str | None = None
    error: TaskError | None = None
    result: C2PASignTaskResult | WatermarkTaskResult | None = None


class TaskFailed(RuntimeError):
    def __init__(self, task: TaskInfo):
        self.task = task
        self.task_id = task.task_id
        code = task.error.code if task.error else task.status.value
        super().__init__(f"Task {task.task_id} failed: {code}.")


class TaskWaitTimeout(TimeoutError):
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Stopped waiting for task {task_id}; server execution was not cancelled. Use get_task() to check its status.")


def _parse_task(payload: dict, schema):
    values = {f.name: payload[f.name] for f in fields(schema) if f.name in payload}
    values["task_type"] = TaskType(values["task_type"])
    values["status"] = TaskStatus(values["status"])
    if values.get("error"):
        values["error"] = TaskError(**values["error"])
    if values.get("result"):
        result_type = C2PASignTaskResult if values["task_type"] == TaskType.C2PA_SIGN else WatermarkTaskResult
        values["result"] = result_type(**values["result"])
    return schema(**values)


def _submit_task(api_key: str, endpoint: str, body: dict, *, trufo_api_url: str) -> TaskAccepted:
    response = requests.post(trufo_api_url + endpoint, json={**body, "execution_mode": "task"},
                             headers=sdk_headers(api_key), timeout=60)
    response.raise_for_status()
    if response.status_code != 202:
        raise ValueError("Expected task acceptance (HTTP 202); check that the endpoint supports TASK execution.")
    return _parse_task(response.json(), TaskAccepted)


def get_task(api_key: str, task_id: str, *, trufo_api_url: str = TRUFO_API_URL) -> TaskInfo:
    """Read status from the same API region used to submit the task."""
    response = requests.get(trufo_api_url + "/tasks/" + quote(task_id, safe=""),
                            headers=sdk_headers(api_key), timeout=30)
    response.raise_for_status()
    return _parse_task(response.json(), TaskInfo)


def wait_for_task(api_key: str, task_id: str, *, wait_seconds: float = 600,
                  poll_interval: float = 1, trufo_api_url: str = TRUFO_API_URL) -> TaskInfo:
    """Wait for a terminal outcome without retrying submission or server failures.

    The local waiting budget is checked between HTTP polls; an in-flight poll
    has its own 30-second HTTP timeout. TaskWaitTimeout retains the task ID.
    """
    if wait_seconds <= 0 or poll_interval <= 0:
        raise ValueError("Wait duration and polling interval must be positive.")
    deadline = time.monotonic() + wait_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TaskWaitTimeout(task_id)
        try:
            task = get_task(api_key, task_id, trufo_api_url=trufo_api_url)
        except requests.Timeout as exc:
            raise TaskWaitTimeout(task_id) from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Could not read task {task_id}; use get_task() to check its status.") from exc
        if task.status == TaskStatus.SUCCEEDED:
            if task.result is None:
                raise ValueError(f"Succeeded task {task_id} has no output reference.")
            if isinstance(task.result, C2PASignTaskResult):
                emit_server_warnings({"warnings": task.result.warnings})
            return task
        if task.status in (TaskStatus.FAILED, TaskStatus.EXPIRED):
            raise TaskFailed(task)
        time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))


def _download_task_output(task: TaskInfo) -> bytes:
    if task.result is None or task.result.download_url is None:
        raise ValueError(f"Output for task {task.task_id} is no longer available to download.")
    response = requests.get(task.result.download_url, timeout=120)
    response.raise_for_status()
    return response.content
