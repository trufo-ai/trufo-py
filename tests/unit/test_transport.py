# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What every API helper sends where: the credential, the host, the timeout, HTTP failures and
the server's warnings. The other test files assert request bodies and results only."""

import contextlib
import math
import re
import warnings
from pathlib import Path

import pytest
import requests

import trufo
from trufo import (
    ExecutionMode,
    TrufoServerWarning,
    bind_commit,
    bind_commit_test,
    bind_reserve,
    bind_reserve_test,
    bind_watermark,
    bind_watermark_test,
    get_content,
    get_s3_upload_url,
    get_task,
    list_content,
    recover_content,
    request_c2pa_cert,
    set_content_status,
    sign_c2pa_cloud,
    sign_c2pa_cloud_test,
    sign_c2pa_s3,
    sign_c2pa_via_s3,
    submit_bind_watermark,
    submit_c2pa_sign,
    wait_for_task,
)
from trufo.api.loopback_auth import exchange_loopback_code
from trufo.api.session import TrufoSession
from trufo.api.tps.sign_c2pa import get_c2pa_s3_upload_url
from trufo.crypt.algorithms import SigningAlgorithm
from trufo.crypt.keygen import generate_keypair

KEY = "key-5f1c9a"
MEDIA = b"media"
API = "https://api.example.test"
PROD = "https://api.trufo.ai"
TEST = "https://test.api.trufo.ai"
UPLOAD_URL = "https://upload.example/input"
DOWNLOAD_URL = "https://download.example/output"
TOKENS = {"access_token": "access-2", "refresh_token": "refresh-2"}
RECORD = {
    "cid": "content-1",
    "status": "active",
    "origin": "c2pa_hosted",
    "mime_type": "image/jpeg",
    "create_ts": "2026-09-08T00:00:00+00:00",
}
UPLOAD = {
    "upload_url": UPLOAD_URL,
    "media_input_s3": "input-reference",
    "expires_at": 1770000000,
    "duration": "5m",
}
TASK = {"execution_mode": ExecutionMode.TASK, "mime_type": "image/jpeg"}
S3_TASK = {"execution_mode": ExecutionMode.TASK}
# what carries a credential; a prepared request's headers ignore case
CREDENTIAL_HEADERS = ["X-API-Key", "Authorization", "Cookie"]


# Trufo's answer to each step a helper takes: its method, its path on the API or its URL, and
# its answer, given task_answer and the fields that carry the server's warnings; a wait-* step
# is a poll while waiting for the task, which a failure ends with a RuntimeError from it
def _steps(task, notice):
    return {
        "sign": ("POST", "/c2pa/sign", {"media_output": "b3V0", **notice}),
        "watermark": ("POST", "/bind/watermark", {"media_output": "b3V0", "wid": "w", **notice}),
        "reserve": (
            "POST",
            "/bind/reserve",
            {"cid": "c", "wid_package": {"wid": "w", "expires_at": "x"}},
        ),
        "commit": ("POST", "/bind/commit", notice),
        "get": ("POST", "/content/get", RECORD),
        "list": ("POST", "/content/list", {"items": [RECORD], "next_cursor": None}),
        "status": ("POST", "/content/status", {**RECORD, "status": "inactive"}),
        "recover": ("POST", "/content/recover", {"detected": False}),
        "upload-url": ("POST", "/io/get-s3-upload-url", UPLOAD),
        "upload": ("PUT", UPLOAD_URL, b""),
        "submit-sign": ("POST", "/c2pa/sign", (202, task("queued"))),
        "submit-watermark": ("POST", "/bind/watermark", (202, task("queued", "watermark"))),
        "poll-sign": ("GET", "/tasks/task-1", task(**notice)),
        "wait-sign": ("GET", "/tasks/task-1", task(**notice)),
        "wait-watermark": ("GET", "/tasks/task-1", task(task_type="watermark", **notice)),
        "download": ("GET", DOWNLOAD_URL, b"out"),
    }


SIGN_TASK = ("upload-url", "upload", "submit-sign", "wait-sign", "download")
WATERMARK_TASK = ("upload-url", "upload", "submit-watermark", "wait-watermark", "download")
_CALLER_LINE = pytest.mark.xfail(strict=True, reason="The warning is to point at the caller.")
# every helper that sends an API key: its call, with any trufo_api_url; the steps it takes, in
# order; its default host; and, if it re-emits the server's warnings, the marks of its case in
# test_server_warnings_point_at_the_caller
HELPERS = {
    "sign_c2pa_cloud": (
        lambda **h: sign_c2pa_cloud(KEY, MEDIA, **h),
        ("sign",),
        PROD,
        [_CALLER_LINE],
    ),
    "sign_c2pa_cloud-task": (
        lambda **h: sign_c2pa_cloud(KEY, MEDIA, **TASK, **h),
        SIGN_TASK,
        PROD,
        [_CALLER_LINE],
    ),
    "sign_c2pa_cloud_test": (
        lambda **h: sign_c2pa_cloud_test(KEY, MEDIA, **h),
        ("sign",),
        TEST,
        [_CALLER_LINE],
    ),
    "submit_c2pa_sign": (
        lambda **h: submit_c2pa_sign(KEY, "ref", **h),
        ("submit-sign",),
        PROD,
        None,
    ),
    "sign_c2pa_s3": (
        lambda **h: sign_c2pa_s3(KEY, "ref", **S3_TASK, **h),
        ("submit-sign", "wait-sign"),
        PROD,
        [_CALLER_LINE],
    ),
    "sign_c2pa_via_s3": (
        lambda **h: sign_c2pa_via_s3(KEY, MEDIA, "image/jpeg", **S3_TASK, **h),
        SIGN_TASK,
        PROD,
        [_CALLER_LINE],
    ),
    "get_s3_upload_url": (
        lambda **h: get_s3_upload_url(KEY, "image/jpeg", **h),
        ("upload-url",),
        PROD,
        None,
    ),
    "get_c2pa_s3_upload_url": (
        lambda **h: get_c2pa_s3_upload_url(KEY, "image/jpeg", **h),
        ("upload-url",),
        PROD,
        None,
    ),
    "get_task": (lambda **h: get_task(KEY, "task-1", **h), ("poll-sign",), PROD, None),
    "wait_for_task": (lambda **h: wait_for_task(KEY, "task-1", **h), ("wait-sign",), PROD, []),
    "bind_watermark": (lambda **h: bind_watermark(KEY, MEDIA, **h), ("watermark",), PROD, []),
    "bind_watermark-task": (
        lambda **h: bind_watermark(KEY, MEDIA, **TASK, **h),
        WATERMARK_TASK,
        PROD,
        [_CALLER_LINE],
    ),
    "bind_watermark_test": (
        lambda **h: bind_watermark_test(KEY, MEDIA, **h),
        ("watermark",),
        TEST,
        [_CALLER_LINE],
    ),
    "submit_bind_watermark": (
        lambda **h: submit_bind_watermark(KEY, "ref", **h),
        ("submit-watermark",),
        PROD,
        None,
    ),
    "bind_reserve": (lambda **h: bind_reserve(KEY, "image/jpeg", **h), ("reserve",), PROD, None),
    "bind_reserve_test": (
        lambda **h: bind_reserve_test(KEY, "image/jpeg", **h),
        ("reserve",),
        TEST,
        None,
    ),
    "bind_commit": (
        lambda **h: bind_commit(KEY, "c", "w", manifest_bytes=b"s", **h),
        ("commit",),
        PROD,
        [],
    ),
    "bind_commit_test": (
        lambda **h: bind_commit_test(KEY, "c", "w", manifest_bytes=b"s", **h),
        ("commit",),
        TEST,
        [_CALLER_LINE],
    ),
    "get_content": (lambda **h: get_content(KEY, cid="content-1", **h), ("get",), PROD, None),
    "list_content": (lambda **h: list_content(KEY, **h), ("list",), PROD, None),
    "set_content_status": (
        lambda **h: set_content_status(KEY, "inactive", cid="c", **h),
        ("status",),
        PROD,
        None,
    ),
    "recover_content": (lambda **h: recover_content(KEY, MEDIA, **h), ("recover",), PROD, None),
}
_DEPRECATED = {"sign_c2pa_s3", "sign_c2pa_via_s3", "get_c2pa_s3_upload_url"}
_IGNORE_DEPRECATION = pytest.mark.filterwarnings("ignore::DeprecationWarning")
# every helper that re-emits the server's warnings
WARNING_HELPERS = [name for name, row in HELPERS.items() if row[3] is not None]


def helpers(*names, caller_line=False):
    """The helpers named, or every one, as test parameters (call, steps, default host); with
    the marks of their caller-line case when ``caller_line``."""
    return [
        pytest.param(
            *HELPERS[name][:3],
            id=name,
            marks=[
                *(HELPERS[name][3] if caller_line else []),
                *([_IGNORE_DEPRECATION] if name in _DEPRECATED else []),
            ],
        )
        for name in names or HELPERS
    ]


def script(trufo_api, task_answer, steps, api_url, *, notices=()):
    """Answer ``steps`` on ``api_url``, with the server's warnings ``notices``; return the
    requests they are, in order, as (method, URL)."""
    notice = {"warnings": list(notices)} if notices else {}
    answers, expected = _steps(task_answer, notice), []
    for step in steps:
        method, where, answer = answers[step]
        expected.append((method, api_url + where if where.startswith("/") else where))
        trufo_api.answer(*expected[-1], answer)
    return expected


def _host(url):
    return url.split("/")[2]


@pytest.mark.parametrize("call, steps, host", helpers())
def test_api_key_goes_only_to_the_api_host(
    trufo_api, task_answer, logged, capsys, call, steps, host
):
    script(trufo_api, task_answer, steps, API)
    call(trufo_api_url=API)
    api_requests = [r for r in trufo_api.requests if r.url not in (UPLOAD_URL, DOWNLOAD_URL)]
    assert api_requests
    for request in api_requests:
        assert request.url.startswith(API + "/")
        assert request.headers["X-API-Key"] == KEY
        assert KEY not in repr((request.url, request.body))
    # nor logged or printed
    assert KEY not in logged() + "".join(capsys.readouterr())


@pytest.mark.parametrize(
    "call, steps, host", helpers("sign_c2pa_cloud-task", "sign_c2pa_via_s3", "bind_watermark-task")
)
def test_presigned_urls_get_no_credentials(trufo_api, task_answer, call, steps, host):
    script(trufo_api, task_answer, steps, API)
    call(trufo_api_url=API)
    presigned = [r for r in trufo_api.requests if _host(r.url) != _host(API)]
    assert [(r.method, r.url) for r in presigned] == [("PUT", UPLOAD_URL), ("GET", DOWNLOAD_URL)]
    assert presigned[0].headers["Content-Type"] == "image/jpeg"
    for request in presigned:
        assert not [name for name in CREDENTIAL_HEADERS if name in request.headers]
        assert KEY not in repr(request.headers)


@pytest.mark.parametrize("call, steps, host", helpers())
def test_default_host_per_helper(trufo_api, task_answer, call, steps, host):
    expected = script(trufo_api, task_answer, steps, host)
    call()
    # its steps in order, on its default host or a presigned URL
    assert [(r.method, r.url) for r in trufo_api.requests] == expected


@pytest.mark.parametrize(
    "base_api_url, auth_url",
    [(TEST, PROD), ("https://eu.api.trufo.ai", "https://eu.api.trufo.ai")],
)
def test_session_hosts(trufo_api, browser, device_answer, base_api_url, auth_url):
    trufo_api.answer("POST", f"{auth_url}/account/loopback/token", TOKENS)
    trufo_api.answer("POST", f"{auth_url}/account/device/authorize", device_answer)
    trufo_api.answer("POST", f"{auth_url}/account/device/token", TOKENS)
    refreshed = {"access_token": "access-3", "refresh_token": "refresh-3"}
    trufo_api.answer("POST", f"{auth_url}/account/refresh", refreshed)
    trufo_api.answer("POST", f"{base_api_url}/path", (401, {}), {})

    session = TrufoSession(base_api_url=base_api_url)
    session.init_session(KEY)
    session.init_session(KEY, use_device=True)
    session.make_request("/path", {})

    assert [r.url for r in trufo_api.requests] == [
        f"{auth_url}/account/loopback/token",
        f"{auth_url}/account/device/authorize",
        f"{auth_url}/account/device/token",
        f"{base_api_url}/path",
        f"{auth_url}/account/refresh",
        f"{base_api_url}/path",
    ]
    # the API key goes to sign-in only, and the bearer token to base_api_url only
    credentials = [
        (r.headers.get("X-API-Key"), r.headers.get("Authorization")) for r in trufo_api.requests
    ]
    assert credentials == [
        *[(KEY, None)] * 3,
        (None, "Bearer access-2"),
        (None, None),
        (None, "Bearer access-3"),
    ]


def _session_calls(trufo_api, device_answer):
    trufo_api.answer("POST", f"{PROD}/path", (401, {}), {})
    trufo_api.answer("POST", f"{PROD}/account/refresh", TOKENS)
    trufo_api.answer("POST", f"{PROD}/account/device/authorize", device_answer)
    trufo_api.answer("POST", f"{PROD}/account/device/token", TOKENS)
    TrufoSession(access_token="access-1", refresh_token="refresh-1").make_request("/path", {})
    TrufoSession().init_session(KEY, use_device=True)
    trufo_api.answer("POST", f"{PROD}/account/loopback/token", TOKENS)
    exchange_loopback_code(KEY, "code", "verifier", "http://127.0.0.1:1/callback")


def _certificate_calls(trufo_api):
    trufo_api.answer("POST", f"{PROD}/ra/c2pa/csr-jwt", {"csr_jwt": "csr-jwt"})
    trufo_api.answer("POST", "https://ca.trufo.ai/.well-known/est/c2pa-l1/simpleenroll", (400, {}))
    private_pem, _ = generate_keypair(SigningAlgorithm.ES256)
    with contextlib.suppress(RuntimeError):
        request_c2pa_cert("gpi_1", "gpic_1", private_pem, private_pem)


def _assert_timeouts(trufo_api):
    assert trufo_api.requests
    for request in trufo_api.requests:
        assert isinstance(request.timeout, (int, float)) and 0 < request.timeout < math.inf


@pytest.mark.parametrize("call, steps, host", helpers())
def test_every_helper_call_has_a_timeout(trufo_api, task_answer, call, steps, host):
    script(trufo_api, task_answer, steps, API)
    call(trufo_api_url=API)
    _assert_timeouts(trufo_api)


def test_every_sign_in_and_certificate_call_has_a_timeout(trufo_api, device_answer):
    _session_calls(trufo_api, device_answer)
    _certificate_calls(trufo_api)
    _assert_timeouts(trufo_api)


@pytest.mark.parametrize("status", [404, 503])
@pytest.mark.parametrize("call, steps, host", helpers())
def test_http_errors_raise(trufo_api, task_answer, call, steps, host, status):
    script(trufo_api, task_answer, steps, API)
    call(trufo_api_url=API)
    # each of its requests in turn fails, the others answered as before
    for request, step in zip(list(trufo_api.requests), steps, strict=True):
        script(trufo_api, task_answer, steps, API)
        trufo_api.answer(request.method, request.url, (status, {"detail": "Refused."}))
        waiting = step.startswith("wait-")
        with pytest.raises(RuntimeError if waiting else requests.HTTPError) as failure:
            call(trufo_api_url=API)
        error = failure.value.__cause__ if waiting else failure.value
        assert isinstance(error, requests.HTTPError) and error.response.status_code == status


@pytest.mark.parametrize("notices", [[], ["First notice.", "Second notice."]])
@pytest.mark.parametrize("call, steps, host", helpers(*WARNING_HELPERS))
def test_server_warnings(trufo_api, task_answer, call, steps, host, notices):
    script(trufo_api, task_answer, steps, API, notices=notices)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", TrufoServerWarning)
        call(trufo_api_url=API)
    assert [str(w.message) for w in caught if w.category is TrufoServerWarning] == notices


@pytest.mark.parametrize("call, steps, host", helpers(*WARNING_HELPERS, caller_line=True))
def test_server_warnings_point_at_the_caller(trufo_api, task_answer, call, steps, host):
    script(trufo_api, task_answer, steps, API, notices=["Notice."])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", TrufoServerWarning)
        call(trufo_api_url=API)
    # the lambda in HELPERS is the caller
    assert [(w.filename, w.lineno) for w in caught if w.category is TrufoServerWarning] == [
        (__file__, call.__code__.co_firstlineno)
    ]


def test_refresh_token_goes_only_to_refresh(trufo_api, device_answer):
    _session_calls(trufo_api, device_answer)
    (refresh,) = [r for r in trufo_api.requests if r.url.endswith("/account/refresh")]
    assert refresh.json == {"refresh_token": "refresh-1"}
    assert not [name for name in CREDENTIAL_HEADERS if name in refresh.headers]
    # the body as sent, whether JSON or form data
    others = [r for r in trufo_api.requests if r is not refresh]
    assert others and "refresh-1" not in repr([(r.url, r.headers, r.body) for r in others])


@pytest.mark.parametrize("engine_installed", [True, False])
@pytest.mark.parametrize("call, steps, host", helpers())
def test_version_headers(trufo_api, task_answer, fake_engine, engine_installed, call, steps, host):
    pyproject = (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text()
    assert re.search(r'^version = "(.+)"$', pyproject, re.M)[1] == trufo.__version__
    if not engine_installed:
        fake_engine.uninstall()
    script(trufo_api, task_answer, steps, API)
    call(trufo_api_url=API)
    for request in [r for r in trufo_api.requests if r.url.startswith(API)]:
        assert request.headers["X-TF-Version"] == trufo.__version__
        if engine_installed:
            assert request.headers["X-TFP-Version"] == fake_engine.version
        else:
            assert "X-TFP-Version" not in request.headers
