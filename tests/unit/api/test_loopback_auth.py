# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for api/loopback_auth.py — RFC 8252 + PKCE sign-in."""

import base64
import hashlib
from unittest.mock import MagicMock, patch

import pytest

from trufo.api.loopback_auth import (
    exchange_loopback_code,
    generate_pkce,
    run_loopback_login,
)


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


class TestGeneratePKCE:
    """generate_pkce produces a spec-conformant verifier/challenge pair."""

    def test_challenge_is_s256_of_verifier(self):
        pkce = generate_pkce()
        expected = (
            base64.urlsafe_b64encode(hashlib.sha256(pkce.verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        assert pkce.challenge == expected

    def test_verifier_length_within_rfc_bounds(self):
        """RFC 7636 §4.1 requires 43-128 characters."""
        pkce = generate_pkce()
        assert 43 <= len(pkce.verifier) <= 128

    def test_each_call_is_unique(self):
        assert generate_pkce().verifier != generate_pkce().verifier

    def test_challenge_has_no_padding(self):
        """Base64url padding must be stripped, or the server comparison fails."""
        assert "=" not in generate_pkce().challenge


class TestExchangeLoopbackCode:
    """exchange_loopback_code posts the right body and maps errors."""

    @patch("trufo.api.loopback_auth.requests.post")
    def test_returns_token_pair(self, mock_post):
        mock_post.return_value = _mock_response(
            200, {"access_token": "at", "refresh_token": "rt"}
        )
        tokens = exchange_loopback_code(
            "key", "code", "verifier", "http://127.0.0.1:1234/callback"
        )

        assert tokens.access_token == "at"
        assert tokens.refresh_token == "rt"

        body = mock_post.call_args.kwargs["json"]
        assert body["code"] == "code"
        assert body["code_verifier"] == "verifier"
        assert body["redirect_uri"] == "http://127.0.0.1:1234/callback"
        assert mock_post.call_args.kwargs["headers"]["X-API-Key"] == "key"

    @patch("trufo.api.loopback_auth.requests.post")
    def test_invalid_grant_raises_actionable_error(self, mock_post):
        mock_post.return_value = _mock_response(400, {"detail": "invalid_grant"})
        with pytest.raises(RuntimeError, match="rejected or expired"):
            exchange_loopback_code(
                "key", "code", "verifier", "http://127.0.0.1:1234/callback"
            )

    @patch("trufo.api.loopback_auth.requests.post")
    def test_other_failure_surfaces_status_and_detail(self, mock_post):
        mock_post.return_value = _mock_response(500, {"detail": "boom"})
        with pytest.raises(RuntimeError, match="500"):
            exchange_loopback_code(
                "key", "code", "verifier", "http://127.0.0.1:1234/callback"
            )


class TestRunLoopbackLogin:
    """run_loopback_login binds loopback only and enforces the state check."""

    @patch("trufo.api.loopback_auth.exchange_loopback_code")
    @patch("trufo.api.loopback_auth.webbrowser.open", return_value=True)
    @patch("trufo.api.loopback_auth.HTTPServer")
    def test_binds_loopback_interface_only(self, mock_server_cls, mock_open, mock_exchange):
        """Binding 0.0.0.0 would expose the auth code to the local network."""
        server = MagicMock()
        server.server_address = ("127.0.0.1", 54321)
        mock_server_cls.return_value = server

        def _receive():
            server.auth_code = "the-code"
            # echo back whatever state went out in the browser URL
            server.auth_state = _state_from(mock_open.call_args[0][0])

        server.handle_request.side_effect = _receive

        run_loopback_login("key")

        bind_address = mock_server_cls.call_args[0][0]
        assert bind_address[0] == "127.0.0.1"
        assert bind_address[1] == 0  # ephemeral port, per RFC 8252 §7.3

    @patch("trufo.api.loopback_auth.exchange_loopback_code")
    @patch("trufo.api.loopback_auth.webbrowser.open", return_value=True)
    @patch("trufo.api.loopback_auth.HTTPServer")
    def test_sends_challenge_not_verifier_to_browser(
        self, mock_server_cls, mock_open, mock_exchange,
    ):
        """The verifier must never leave the machine in the browser URL."""
        server = MagicMock()
        server.server_address = ("127.0.0.1", 54321)
        mock_server_cls.return_value = server

        def _receive():
            server.auth_code = "the-code"
            server.auth_state = _state_from(mock_open.call_args[0][0])

        server.handle_request.side_effect = _receive

        run_loopback_login("key")

        url = mock_open.call_args[0][0]
        verifier = mock_exchange.call_args[0][2]
        assert verifier not in url
        assert "code_challenge=" in url
        assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A54321" in url

    @patch("trufo.api.loopback_auth.exchange_loopback_code")
    @patch("trufo.api.loopback_auth.webbrowser.open", return_value=True)
    @patch("trufo.api.loopback_auth.HTTPServer")
    def test_state_mismatch_aborts(self, mock_server_cls, mock_open, mock_exchange):
        """A code arriving with the wrong state belongs to a flow we did not start."""
        server = MagicMock()
        server.server_address = ("127.0.0.1", 54321)
        mock_server_cls.return_value = server

        def _receive():
            server.auth_code = "the-code"
            server.auth_state = "not-the-state-we-sent"

        server.handle_request.side_effect = _receive

        with pytest.raises(RuntimeError, match="State mismatch"):
            run_loopback_login("key")
        mock_exchange.assert_not_called()

    @patch("trufo.api.loopback_auth.exchange_loopback_code")
    @patch("trufo.api.loopback_auth.webbrowser.open", return_value=True)
    @patch("trufo.api.loopback_auth.HTTPServer")
    def test_timeout_when_no_code_arrives(self, mock_server_cls, mock_open, mock_exchange):
        server = MagicMock()
        server.server_address = ("127.0.0.1", 54321)
        mock_server_cls.return_value = server
        server.auth_code = None
        server.auth_state = None
        server.handle_request.side_effect = lambda: None

        with pytest.raises(TimeoutError):
            run_loopback_login("key", timeout=1)
        mock_exchange.assert_not_called()


def _state_from(url: str) -> str:
    """Pull the state parameter out of the browser URL."""
    from urllib.parse import parse_qs, urlparse

    return parse_qs(urlparse(url).query)["state"][0]
