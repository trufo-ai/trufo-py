# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Loopback authorization flow (RFC 8252 + PKCE, RFC 7636).

Same-machine sibling of ``auth.py``'s device flow. Use this when the CLI runs
on a machine that has a browser; use the device flow when it does not (an SSH
session, a container), because the loopback redirect cannot cross machines.

Handles:
- Generating a PKCE verifier/challenge pair
- Binding a one-shot listener on 127.0.0.1 to receive the redirect
- Opening the browser at the Trufo webapp
- Exchanging the authorization code (POST /account/loopback/token)

The listener binds 127.0.0.1 specifically, never 0.0.0.0: binding all
interfaces would expose the callback — and therefore the authorization code —
to anyone on the same network.
"""

import base64
import hashlib
import logging
import secrets
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from trufo.api.auth import TokenPair, extract_detail
from trufo.api.endpoints import (
    LOOPBACK_AUTH_PATH,
    LOOPBACK_TOKEN,
    TRUFO_API_URL,
    TRUFO_APP_URL,
)

logger = logging.getLogger(__name__)

# RFC 7636 §4.1 allows 43-128 characters; token_urlsafe(32) yields 43.
_VERIFIER_BYTES = 32
_STATE_BYTES = 32

# How long to wait for the user to finish in the browser. Deliberately NOT the
# same clock as the server's 60 s authorization-code lifetime: that one covers
# mint -> redeem, which is a machine-speed hop, while this one covers a human
# opening a browser and signing in. Do not "fix" one to match the other.
_DEFAULT_TIMEOUT = 300

# Path the CLI listens on. Checked so that an unrelated local request cannot
# consume our one-shot listener and strand the sign-in.
_CALLBACK_PATH = "/callback"


class BrowserUnavailableError(Exception):
    """Raised when no browser could be opened on this machine.

    Signals the caller to fall back to the device flow, which does not need a
    local browser or a local listener.
    """


_BROWSER_RESPONSE = b"""<!doctype html>
<html><body style="font-family: sans-serif; text-align: center; padding: 60px">
<h2>Signed in</h2><p>You can close this window and return to your terminal.</p>
</body></html>"""


@dataclass
class PKCEChallenge:
    """A PKCE verifier and its S256 challenge."""

    verifier: str
    challenge: str


def generate_pkce() -> PKCEChallenge:
    """Generate a PKCE verifier and its S256 challenge.

    Returns:
        PKCEChallenge. The verifier stays local; only the challenge is sent to
        the authorization server, so an observer of the browser traffic cannot
        redeem the resulting code.
    """
    verifier = secrets.token_urlsafe(_VERIFIER_BYTES)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return PKCEChallenge(verifier=verifier, challenge=challenge)


class _CallbackHandler(BaseHTTPRequestHandler):
    """One-shot handler that captures the code and state from the redirect."""

    def do_GET(self) -> None:  # noqa: N802 — name fixed by BaseHTTPRequestHandler
        parsed = urlparse(self.path)

        # ignore anything that is not our callback (a browser favicon prefetch,
        # say) so it cannot consume the one-shot listener
        if parsed.path != _CALLBACK_PATH:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        params = parse_qs(parsed.query)
        self.server.callback_seen = True  # type: ignore[attr-defined]
        self.server.auth_code = (params.get("code") or [None])[0]  # type: ignore[attr-defined]
        self.server.auth_state = (params.get("state") or [None])[0]  # type: ignore[attr-defined]

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(_BROWSER_RESPONSE)))
        self.end_headers()
        self.wfile.write(_BROWSER_RESPONSE)

    def log_message(self, format: str, *args: object) -> None:
        """Silence the default stderr access log."""
        logger.debug("Loopback callback: " + format, *args)


def run_loopback_login(
    api_key: str,
    base_url: str = TRUFO_API_URL,
    app_url: str = TRUFO_APP_URL,
    timeout: int = _DEFAULT_TIMEOUT,
) -> TokenPair:
    """Run the full loopback sign-in and return session tokens.

    Binds an ephemeral port on 127.0.0.1, opens the Trufo webapp in the user's
    browser, waits for the redirect carrying the authorization code, then
    exchanges that code for tokens.

    Args:
        api_key: Trufo API key with trufo-api scope.
        base_url: Trufo API base URL.
        app_url: Trufo webapp base URL (where the browser is sent).
        timeout: Max seconds to wait for the user to finish in the browser.

    Returns:
        TokenPair.

    Raises:
        BrowserUnavailableError: If no browser could be launched. The caller
            should fall back to the device flow. This — not a bind failure — is
            the signal that a machine is headless.
        OSError: If no loopback port can be bound. Rare; also a reason to fall
            back to the device flow.
        TimeoutError: If the user does not complete sign-in within timeout.
        RuntimeError: On state mismatch, a callback with no code, or a failed
            code exchange.
    """
    pkce = generate_pkce()
    state = secrets.token_urlsafe(_STATE_BYTES)

    # port 0 asks the OS for any free port; 127.0.0.1 keeps it off the network
    httpd = HTTPServer(("127.0.0.1", 0), _CallbackHandler)
    httpd.timeout = timeout
    httpd.auth_code = None  # type: ignore[attr-defined]
    httpd.auth_state = None  # type: ignore[attr-defined]
    httpd.callback_seen = False  # type: ignore[attr-defined]

    try:
        port = httpd.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}/callback"

        query = urlencode({
            "code_challenge": pkce.challenge,
            "state": state,
            "redirect_uri": redirect_uri,
        })
        authorize_url = f"{app_url}{LOOPBACK_AUTH_PATH}?{query}"

        # webbrowser.open returns False when it cannot find a browser to launch,
        # which is the real signal for "this machine is headless". Binding the
        # loopback port succeeds almost everywhere, including over SSH and in
        # containers, so a bind failure is NOT that signal.
        if not webbrowser.open(authorize_url):
            raise BrowserUnavailableError("No browser available on this machine.")

        print(f"Continue sign-in here: {authorize_url}")

        # loop rather than a single handle_request: an unrelated local request
        # (a favicon prefetch, a port scanner) answers 404 without consuming
        # our wait
        deadline = time.monotonic() + timeout
        while httpd.auth_code is None:  # type: ignore[attr-defined]
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            httpd.timeout = remaining
            httpd.handle_request()

        code = httpd.auth_code  # type: ignore[attr-defined]
        received_state = httpd.auth_state  # type: ignore[attr-defined]
        callback_seen = httpd.callback_seen  # type: ignore[attr-defined]
    finally:
        httpd.server_close()

    if code is None:
        if callback_seen:
            raise RuntimeError("Sign-in callback arrived without an authorization code.")
        raise TimeoutError(f"Timed out after {timeout}s waiting for browser sign-in.")

    # the state check is what stops a third party from feeding us a code that
    # belongs to a flow we did not start
    if not secrets.compare_digest(received_state or "", state):
        raise RuntimeError("State mismatch on loopback callback; sign-in aborted.")

    return exchange_loopback_code(
        api_key,
        code,
        pkce.verifier,
        redirect_uri,
        base_url=base_url,
    )


def exchange_loopback_code(
    api_key: str,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    base_url: str = TRUFO_API_URL,
) -> TokenPair:
    """POST /account/loopback/token to exchange an authorization code.

    Args:
        api_key: Trufo API key with trufo-api scope.
        code: Authorization code received on the loopback callback.
        code_verifier: The verifier matching the challenge sent earlier.
        redirect_uri: The same redirect_uri the code was issued for.
        base_url: Trufo API base URL.

    Returns:
        TokenPair.

    Raises:
        RuntimeError: If the exchange is rejected.
    """
    resp = requests.post(
        f"{base_url}{LOOPBACK_TOKEN}",
        headers={
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )

    if resp.status_code == 200:
        data = resp.json()
        return TokenPair(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
        )

    detail = extract_detail(resp)
    if detail == "invalid_grant":
        raise RuntimeError("Sign-in code was rejected or expired. Please try again.")
    raise RuntimeError(f"Loopback token exchange failed ({resp.status_code}): {detail}")
