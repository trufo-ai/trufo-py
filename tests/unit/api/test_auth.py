# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for api/auth.py — device authorization flow."""

from unittest.mock import MagicMock, patch

import pytest

from trufo.api.auth import (
    DeviceAuthResponse,
    TokenPair,
    initiate_device_auth,
    poll_for_tokens,
    refresh_tokens,
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


class TestInitiateDeviceAuth:
    """initiate_device_auth sends correct request, parses response."""

    @patch("trufo.api.auth.requests.post")
    def test_returns_device_auth_response(self, mock_post):
        mock_post.return_value = _mock_response(
            200,
            {
                "device_code": "dev-code",
                "user_code": "ABC-123",
                "verification_uri": "https://app.trufo.ai/device",
                "verification_uri_complete": "https://app.trufo.ai/device?code=ABC-123",
                "expires_in": 600,
                "interval": 5,
            },
        )

        result = initiate_device_auth("test-api-key")

        assert isinstance(result, DeviceAuthResponse)
        assert result.device_code == "dev-code"
        assert result.user_code == "ABC-123"
        assert result.interval == 5

    @patch("trufo.api.auth.requests.post")
    def test_sends_api_key_header(self, mock_post):
        mock_post.return_value = _mock_response(
            200,
            {
                "device_code": "d",
                "user_code": "u",
                "verification_uri": "v",
                "verification_uri_complete": "vc",
                "expires_in": 60,
                "interval": 5,
            },
        )

        initiate_device_auth("my-key", base_url="https://example.com")

        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["headers"]["X-API-Key"] == "my-key"
        assert call_kwargs[0][0].startswith("https://example.com")

    @patch("trufo.api.auth.requests.post")
    def test_raises_on_failure(self, mock_post):
        mock_post.return_value = _mock_response(403, {"detail": "invalid key"})

        with pytest.raises(RuntimeError, match="Device authorize failed"):
            initiate_device_auth("bad-key")


class TestPollForTokens:
    """poll_for_tokens handles pending, success, expiry, denial."""

    @patch("trufo.api.auth.time.sleep")
    @patch("trufo.api.auth.requests.post")
    def test_returns_tokens_on_success(self, mock_post, _mock_sleep):
        mock_post.return_value = _mock_response(
            200,
            {
                "access_token": "at",
                "refresh_token": "rt",
            },
        )

        result = poll_for_tokens("key", "dev-code", interval=1, timeout=10)

        assert isinstance(result, TokenPair)
        assert result.access_token == "at"

    @patch("trufo.api.auth.time.sleep")
    @patch("trufo.api.auth.requests.post")
    def test_polls_on_pending_then_succeeds(self, mock_post, mock_sleep):
        pending = _mock_response(403, {"detail": "authorization_pending"})
        success = _mock_response(
            200,
            {
                "access_token": "at2",
                "refresh_token": "rt2",
            },
        )
        mock_post.side_effect = [pending, success]

        result = poll_for_tokens("key", "dev-code", interval=1, timeout=30)

        assert result.access_token == "at2"
        mock_sleep.assert_called_once_with(1)

    @patch("trufo.api.auth.time.sleep")
    @patch("trufo.api.auth.requests.post")
    def test_raises_on_expired_token(self, mock_post, _mock_sleep):
        mock_post.return_value = _mock_response(400, {"detail": "expired_token"})

        with pytest.raises(TimeoutError, match="Device code expired"):
            poll_for_tokens("key", "dev-code", interval=1, timeout=10)

    @patch("trufo.api.auth.time.sleep")
    @patch("trufo.api.auth.requests.post")
    def test_raises_on_access_denied(self, mock_post, _mock_sleep):
        mock_post.return_value = _mock_response(403, {"detail": "access_denied"})

        with pytest.raises(RuntimeError, match="denied"):
            poll_for_tokens("key", "dev-code", interval=1, timeout=10)


class TestRefreshTokens:
    """refresh_tokens exchanges a refresh token for a new pair."""

    @patch("trufo.api.auth.requests.post")
    def test_returns_new_token_pair(self, mock_post):
        mock_post.return_value = _mock_response(
            200,
            {
                "access_token": "new-at",
                "refresh_token": "new-rt",
            },
        )

        result = refresh_tokens("old-rt")

        assert result.access_token == "new-at"
        assert result.refresh_token == "new-rt"

    @patch("trufo.api.auth.requests.post")
    def test_raises_on_failure(self, mock_post):
        mock_post.return_value = _mock_response(401, {"detail": "token expired"})

        with pytest.raises(RuntimeError, match="Token refresh failed"):
            refresh_tokens("expired-rt")
