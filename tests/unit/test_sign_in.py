# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Signing in, in a browser on this machine (loopback) or on another (device), and the session's
requests and token refresh."""

import base64
import hashlib
import socket
import time
import webbrowser
from http.server import HTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from trufo.api.endpoints import TRUFO_API_URL, TRUFO_APP_URL
from trufo.api.loopback_auth import BrowserUnavailableError, generate_pkce, run_loopback_login
from trufo.api.session import AuthError, TrufoSession

KEY = "key-8d2e41"
TOKENS = {"access_token": "access-1", "refresh_token": "refresh-1"}
LOOPBACK_TOKEN_URL = f"{TRUFO_API_URL}/account/loopback/token"
AUTHORIZE_URL = f"{TRUFO_API_URL}/account/device/authorize"
DEVICE_TOKEN_URL = f"{TRUFO_API_URL}/account/device/token"
REFRESH_URL = f"{TRUFO_API_URL}/account/refresh"
PATH_URL = f"{TRUFO_API_URL}/path"


def _params(url):
    return {name: values[0] for name, values in parse_qs(urlsplit(url).query).items()}


def _assert_not_shown(logged, capsys, *secrets):
    """None of ``secrets`` is in a log record or in the output."""
    shown = logged() + "".join(capsys.readouterr())
    assert [secret for secret in secrets if secret in shown] == []


def test_loopback_sign_in(trufo_api, browser, logged, capsys):
    trufo_api.answer("POST", LOOPBACK_TOKEN_URL, TOKENS)

    tokens = run_loopback_login(KEY)

    assert (tokens.access_token, tokens.refresh_token) == ("access-1", "refresh-1")
    (opened,) = browser.opened
    params = _params(opened)
    assert opened.startswith(f"{TRUFO_APP_URL}/loopback?")
    assert set(params) == {"code_challenge", "state", "redirect_uri"}
    redirect = urlsplit(params["redirect_uri"])
    assert (redirect.scheme, redirect.hostname, redirect.path) == ("http", "127.0.0.1", "/callback")
    (redeemed,) = trufo_api.requests
    verifier = redeemed.json["code_verifier"]
    assert redeemed.json == {
        "code": "the-code",
        "code_verifier": verifier,
        "redirect_uri": params["redirect_uri"],
    }
    # the browser gets the unpadded S256 challenge, never the verifier
    assert 43 <= len(verifier) <= 128 and verifier not in opened
    digest = hashlib.sha256(verifier.encode()).digest()
    assert params["code_challenge"] == base64.urlsafe_b64encode(digest).decode().rstrip("=")
    browser.join()
    ((status, page),) = browser.answers
    assert status == 200 and "Authorization received" in page
    _assert_not_shown(logged, capsys, KEY, "access-1", "refresh-1", verifier)


def test_pkce_uses_a_fresh_verifier():
    assert generate_pkce().verifier != generate_pkce().verifier


def test_listener_is_loopback_only(monkeypatch):
    ports = []

    def open_browser(url):
        port = urlsplit(_params(url)["redirect_uri"]).port
        ports.append(port)
        if len(ports) == 1:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            # every other address, on this machine too, is refused
            with pytest.raises(OSError):
                socket.create_connection(("127.0.0.2", port), timeout=1).close()
            # a second sign-in meanwhile listens on a port of its own
            with pytest.raises(BrowserUnavailableError):
                run_loopback_login(KEY)
        return False

    monkeypatch.setattr(webbrowser, "open", open_browser)
    with pytest.raises(BrowserUnavailableError):
        run_loopback_login(KEY)
    assert len(set(ports)) == 2


def test_state_mismatch(browser):
    browser.visits = lambda params: [("/callback", {"code": "the-code", "state": "another-state"})]
    # nothing is redeemed: a request would fail the test
    with pytest.raises(RuntimeError, match="State mismatch on loopback callback; sign-in aborted."):
        run_loopback_login(KEY)


def test_callback_without_code(browser):
    # a state that is not ASCII is compared too
    browser.visits = lambda params: [("/callback", {"error": "access_denied", "state": "é"})]
    with pytest.raises(
        RuntimeError, match="Sign-in callback arrived without an authorization code."
    ):
        run_loopback_login(KEY, timeout=10)
    browser.join()
    ((status, page),) = browser.answers
    assert status == 400 and "Sign-in did not complete" in page


def test_loopback_timeout(browser):
    browser.visits = lambda params: []
    with pytest.raises(TimeoutError, match="Timed out after 1s waiting for browser sign-in."):
        run_loopback_login(KEY, timeout=1)


@pytest.mark.parametrize("why", ["no browser", "no loopback port", "use_device"])
def test_falls_back_to_the_device_flow(trufo_api, browser, device_answer, capsys, monkeypatch, why):
    browser.available = False
    if why == "no loopback port":

        def server_bind(server):
            raise OSError("No port.")

        monkeypatch.setattr(HTTPServer, "server_bind", server_bind)
    trufo_api.answer("POST", AUTHORIZE_URL, device_answer)
    trufo_api.answer("POST", DEVICE_TOKEN_URL, TOKENS)

    session = TrufoSession()
    session.init_session(KEY, use_device=why == "use_device")

    assert (session.access_token, session.refresh_token) == ("access-1", "refresh-1")
    fallback = "No local browser available; falling back to device sign-in.\n"
    output = capsys.readouterr().out
    assert (len(browser.opened), output.startswith(fallback)) == {
        "no browser": (1, True),
        "no loopback port": (0, True),
        "use_device": (0, False),
    }[why]


@pytest.mark.parametrize(
    "answer, message",
    [
        (
            (400, {"detail": "invalid_grant"}),
            "Sign-in code was rejected or expired. Please try again.",
        ),
        ((500, {"detail": "boom"}), r"Loopback token exchange failed \(500\): boom"),
    ],
)
def test_redemption_refused(trufo_api, browser, answer, message):
    trufo_api.answer("POST", LOOPBACK_TOKEN_URL, answer)
    with pytest.raises(RuntimeError, match=message):
        run_loopback_login(KEY)


def test_device_flow(trufo_api, device_answer, logged, capsys, monkeypatch):
    sleeps = []
    monkeypatch.setattr(time, "sleep", sleeps.append)
    trufo_api.answer("POST", AUTHORIZE_URL, device_answer)
    trufo_api.answer("POST", DEVICE_TOKEN_URL, (400, {"detail": "authorization_pending"}), TOKENS)

    session = TrufoSession()
    session.init_session(KEY, use_device=True)

    assert (session.access_token, session.refresh_token) == ("access-1", "refresh-1")
    assert capsys.readouterr().out == (
        f"Visit: {device_answer['verification_uri_complete']}\nConfirm code: ABCD-1234\n"
    )
    assert [(r.url, r.json) for r in trufo_api.requests] == [
        (AUTHORIZE_URL, None),
        (DEVICE_TOKEN_URL, {"device_code": "device-1"}),
        (DEVICE_TOKEN_URL, {"device_code": "device-1"}),
    ]
    assert sleeps == [5]
    _assert_not_shown(logged, capsys, KEY, "access-1", "refresh-1")


@pytest.mark.parametrize(
    "authorize, token, error, message",
    [
        (
            (403, {"detail": "Invalid key."}),
            TOKENS,
            RuntimeError,
            r"Device authorize failed \(403\): Invalid key.",
        ),
        (
            None,
            (400, {"detail": "expired_token"}),
            TimeoutError,
            "Device code expired. Please try again.",
        ),
        (
            None,
            (404, {"detail": "DeviceCodeNotFound"}),
            TimeoutError,
            "Device code expired. Please try again.",
        ),
        (
            None,
            (403, {"detail": "access_denied"}),
            RuntimeError,
            "Authorization was denied by the user.",
        ),
        (
            None,
            (500, {"detail": "boom"}),
            RuntimeError,
            r"Unexpected error polling device token \(500\): boom",
        ),
        (None, (400, {"detail": "authorization_pending"}), TimeoutError, "Timed out after 600s"),
    ],
)
def test_device_flow_outcomes(
    trufo_api, device_answer, monkeypatch, authorize, token, error, message
):
    now = 0

    def sleep(seconds):
        nonlocal now
        now += seconds

    monkeypatch.setattr(time, "monotonic", lambda: now)
    monkeypatch.setattr(time, "sleep", sleep)
    # None: the device sign-in starts
    trufo_api.answer("POST", AUTHORIZE_URL, device_answer if authorize is None else authorize)
    trufo_api.answer("POST", DEVICE_TOKEN_URL, token)
    with pytest.raises(error, match=message):
        TrufoSession().init_session(KEY, use_device=True)


def test_make_request(trufo_api, logged, capsys):
    session = TrufoSession(access_token="access-0", refresh_token="refresh-0")
    trufo_api.answer("POST", PATH_URL, {"result": "ok"})
    assert session.make_request("/path", {"key": "value"}) == {"result": "ok"}

    # a 401 refreshes the tokens once and sends once more
    trufo_api.answer("POST", PATH_URL, (401, {}), {"result": "again"})
    trufo_api.answer("POST", REFRESH_URL, TOKENS)
    assert session.make_request("/path", {"key": "value"}) == {"result": "again"}
    assert (session.access_token, session.refresh_token) == ("access-1", "refresh-1")

    # a 401 after the refresh ends the request
    trufo_api.answer(
        "POST", REFRESH_URL, {"access_token": "access-2", "refresh_token": "refresh-2"}
    )
    trufo_api.answer("POST", PATH_URL, (401, {"detail": "Expired."}))
    with pytest.raises(RuntimeError, match=r"API request failed \(401\): Expired."):
        session.make_request("/path", {"key": "value"})

    trufo_api.answer("POST", PATH_URL, (500, {"detail": "Server error."}))
    with pytest.raises(RuntimeError, match=r"API request failed \(500\): Server error."):
        session.make_request("/path", {"key": "value"})

    body = {"key": "value"}
    assert [(r.url, r.json, r.headers.get("Authorization")) for r in trufo_api.requests] == [
        (PATH_URL, body, "Bearer access-0"),
        (PATH_URL, body, "Bearer access-0"),
        (REFRESH_URL, {"refresh_token": "refresh-0"}, None),
        (PATH_URL, body, "Bearer access-1"),
        (PATH_URL, body, "Bearer access-1"),
        (REFRESH_URL, {"refresh_token": "refresh-1"}, None),
        (PATH_URL, body, "Bearer access-2"),
        (PATH_URL, body, "Bearer access-2"),
    ]
    tokens = [f"{kind}-{n}" for kind in ("access", "refresh") for n in range(3)]
    _assert_not_shown(logged, capsys, *tokens)


def test_session_errors(trufo_api):
    # no request without a session: a request would fail the test
    with pytest.raises(AuthError, match="No active session"):
        TrufoSession().make_request("/path", {})

    trufo_api.answer("POST", PATH_URL, (401, {}))
    with pytest.raises(AuthError, match="No refresh token available."):
        TrufoSession(access_token="access-0").make_request("/path", {})

    trufo_api.answer("POST", REFRESH_URL, (401, {"detail": "token expired"}))
    with pytest.raises(AuthError, match="Session expired. Please log in again."):
        TrufoSession(access_token="access-0", refresh_token="refresh-0").make_request("/path", {})


def test_other_paths_do_not_end_the_wait(trufo_api, browser):
    trufo_api.answer("POST", LOOPBACK_TOKEN_URL, TOKENS)
    browser.visits = lambda params: [
        ("/favicon.ico", {}),
        ("/callback", {"code": "the-code", "state": params["state"]}),
    ]
    assert run_loopback_login(KEY, timeout=10).access_token == "access-1"
    browser.join()
    assert [status for status, _ in browser.answers] == [404, 200]
