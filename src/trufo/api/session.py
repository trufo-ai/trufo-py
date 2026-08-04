# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Authenticated session for the Trufo API.

TrufoSession holds access + refresh tokens and handles authenticated
requests with automatic token refresh on 401.

Credential persistence (loading/saving API keys, tokens to disk) is
intentionally NOT handled here — that is environment-dependent and
belongs in the CLI or application layer.
"""

import logging

import requests

from trufo.api.auth import (
    extract_detail,
    initiate_device_auth,
    poll_for_tokens,
    refresh_tokens,
)
from trufo.api.endpoints import TRUFO_API_URL
from trufo.api.loopback_auth import run_loopback_login

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Raised when authentication fails and cannot be recovered."""


class TrufoSession:
    """Authenticated HTTP session for the Trufo API.

    Usage (new login):
        session = TrufoSession()
        session.init_session(api_key)
        data = session.make_request("/some/endpoint", {"key": "value"})

    Usage (existing tokens):
        session = TrufoSession(access_token=saved_access, refresh_token=saved_refresh)
        data = session.make_request("/some/endpoint", {"key": "value"})
    """

    def __init__(
        self,
        access_token: str | None = None,
        refresh_token: str | None = None,
        base_api_url: str = TRUFO_API_URL,
    ) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.base_api_url = base_api_url

    def init_session(self, api_key: str, use_device: bool = False) -> None:
        """Sign in and obtain tokens.

        Prefers the loopback flow (RFC 8252), which opens a browser on this
        machine and needs nothing typed. Falls back to the device flow
        (RFC 8628) when no loopback port can be bound — which is what happens
        on a headless host, where the browser is on a different machine and the
        loopback redirect could not reach us anyway.

        Args:
            api_key: Trufo API key with trufo-api scope.
            use_device: Skip loopback and use the device flow directly. Useful
                over SSH, where a browser may open on the wrong machine.
        """
        if not use_device:
            try:
                tokens = run_loopback_login(api_key, base_url=self.base_api_url)
                self.access_token = tokens.access_token
                self.refresh_token = tokens.refresh_token
                return
            except OSError as exc:
                logger.debug("Loopback listener unavailable (%s); using device flow.", exc)
                print("Could not start a local listener; falling back to device sign-in.")

        self._init_session_device(api_key)

    def _init_session_device(self, api_key: str) -> None:
        """Run the device authorization flow (RFC 8628) to obtain tokens.

        Prints the verification URL for the user, then polls until
        the user approves (or the code expires).
        """
        auth_resp = initiate_device_auth(api_key, base_url=self.base_api_url)

        # keep the pre-filled URL: the /device page has no code-entry field yet,
        # so the bare verification_uri would land the user on "Invalid link"
        print(f"Visit: {auth_resp.verification_uri_complete}")
        print(f"Confirm code: {auth_resp.user_code}")

        tokens = poll_for_tokens(
            api_key,
            auth_resp.device_code,
            base_url=self.base_api_url,
            interval=auth_resp.interval,
            timeout=auth_resp.expires_in,
        )
        self.access_token = tokens.access_token
        self.refresh_token = tokens.refresh_token

    def make_request(self, request_url: str, request_data: dict) -> dict:
        """Authenticated POST. Retries once with refreshed token on 401.

        Args:
            request_url: API path (e.g. "/gproduct/instance/create").
            request_data: JSON request body.

        Returns:
            Parsed JSON response dict.

        Raises:
            AuthError: If no tokens are available or refresh fails.
            RuntimeError: If the request fails after retry.
        """
        if not self.access_token:
            raise AuthError("No active session. Call init_session() or set tokens first.")

        url = f"{self.base_api_url}{request_url}"
        resp = self._post(url, self.access_token, request_data)

        if resp.status_code == 401:
            logger.debug("Got 401, attempting token refresh.")
            self._refresh()
            resp = self._post(url, self.access_token, request_data)

        if resp.status_code >= 400:
            detail = extract_detail(resp)
            raise RuntimeError(f"API request failed ({resp.status_code}): {detail}")

        return resp.json()

    def _refresh(self) -> None:
        """Refresh the token pair using the current refresh token."""
        if not self.refresh_token:
            raise AuthError("No refresh token available.")
        try:
            tokens = refresh_tokens(self.refresh_token, base_url=self.base_api_url)
        except RuntimeError as exc:
            raise AuthError("Session expired. Please log in again.") from exc
        self.access_token = tokens.access_token
        self.refresh_token = tokens.refresh_token

    @staticmethod
    def _post(url: str, access_token: str, data: dict) -> requests.Response:
        """Send an authenticated POST request."""
        return requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            json=data,
            timeout=30,
        )
