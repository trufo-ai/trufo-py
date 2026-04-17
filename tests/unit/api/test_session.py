# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for api/session.py — TrufoSession."""

from unittest.mock import MagicMock, patch

import pytest

from trufo.api.auth import DeviceAuthResponse, TokenPair
from trufo.api.session import AuthError, TrufoSession


def _mock_response(status_code: int, json_data: dict | None = None, text: str = ""):
    """Build a mock ``requests.Response``."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("No JSON")
    return resp


class TestTrufoSessionInit:
    """Construction and token storage."""

    def test_default_no_tokens(self):
        session = TrufoSession()
        assert session.access_token is None
        assert session.refresh_token is None

    def test_tokens_from_kwargs(self):
        session = TrufoSession(access_token="at", refresh_token="rt")
        assert session.access_token == "at"
        assert session.refresh_token == "rt"


class TestInitSession:
    """init_session runs device auth flow and stores tokens."""

    @patch("trufo.api.session.poll_for_tokens")
    @patch("trufo.api.session.initiate_device_auth")
    def test_stores_tokens_after_auth(self, mock_init, mock_poll):
        mock_init.return_value = DeviceAuthResponse(
            device_code="dc",
            user_code="UC",
            verification_uri="v",
            verification_uri_complete="vc",
            expires_in=60,
            interval=1,
        )
        mock_poll.return_value = TokenPair(access_token="new-at", refresh_token="new-rt")

        session = TrufoSession()
        session.init_session("api-key")

        assert session.access_token == "new-at"
        assert session.refresh_token == "new-rt"


class TestMakeRequest:
    """make_request sends authenticated POST with auto-refresh."""

    @patch("trufo.api.session.requests.post")
    def test_success(self, mock_post):
        mock_post.return_value = _mock_response(200, {"result": "ok"})

        session = TrufoSession(access_token="at", refresh_token="rt")
        data = session.make_request("/test", {"key": "val"})

        assert data == {"result": "ok"}

    def test_raises_auth_error_without_tokens(self):
        session = TrufoSession()
        with pytest.raises(AuthError, match="No active session"):
            session.make_request("/test", {})

    @patch("trufo.api.session.refresh_tokens")
    @patch("trufo.api.session.requests.post")
    def test_retries_once_on_401(self, mock_post, mock_refresh):
        first_resp = _mock_response(401, {"detail": "token expired"})
        second_resp = _mock_response(200, {"result": "ok"})
        mock_post.side_effect = [first_resp, second_resp]
        mock_refresh.return_value = TokenPair(access_token="new-at", refresh_token="new-rt")

        session = TrufoSession(access_token="old-at", refresh_token="old-rt")
        data = session.make_request("/test", {})

        assert data == {"result": "ok"}
        assert session.access_token == "new-at"

    @patch("trufo.api.session.requests.post")
    def test_raises_on_error_status(self, mock_post):
        mock_post.return_value = _mock_response(500, {"detail": "server error"})

        session = TrufoSession(access_token="at", refresh_token="rt")
        with pytest.raises(RuntimeError, match="API request failed"):
            session.make_request("/test", {})

    def test_refresh_without_refresh_token_raises(self):
        session = TrufoSession(access_token="at")
        with pytest.raises(AuthError, match="No refresh token"):
            session._refresh()

    @patch("trufo.api.session.refresh_tokens")
    def test_refresh_failure_raises_auth_error(self, mock_refresh):
        mock_refresh.side_effect = RuntimeError("refresh failed")

        session = TrufoSession(access_token="at", refresh_token="rt")
        with pytest.raises(AuthError, match="Session expired"):
            session._refresh()
