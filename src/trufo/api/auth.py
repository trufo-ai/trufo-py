# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Device authorization flow (RFC 8628) and token management.

Handles:
- Initiating device auth (POST /account/device/authorize)
- Polling for approval (POST /account/device/token)
- Token refresh (POST /account/refresh)
"""

import logging
import time
from dataclasses import dataclass

import requests

from trufo.api.endpoints import (
    ACCOUNT_REFRESH,
    DEVICE_AUTHORIZE,
    DEVICE_TOKEN,
    TRUFO_API_URL,
)

logger = logging.getLogger(__name__)


@dataclass
class TokenPair:
    """Access + refresh token pair."""

    access_token: str
    refresh_token: str


@dataclass
class DeviceAuthResponse:
    """Response from device/authorize."""

    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


def initiate_device_auth(
    api_key: str,
    base_url: str = TRUFO_API_URL,
) -> DeviceAuthResponse:
    """POST /account/device/authorize to get device + user codes.

    Args:
        api_key: Trufo API key with trufo-api scope.
        base_url: Trufo API base URL.

    Returns:
        DeviceAuthResponse with codes and verification URI.

    Raises:
        RuntimeError: If the request fails.
    """
    resp = requests.post(
        f"{base_url}{DEVICE_AUTHORIZE}",
        headers={"X-API-Key": api_key},
        timeout=30,
    )
    if resp.status_code != 200:
        detail = extract_detail(resp)
        raise RuntimeError(f"Device authorize failed ({resp.status_code}): {detail}")

    data = resp.json()
    return DeviceAuthResponse(
        device_code=data["device_code"],
        user_code=data["user_code"],
        verification_uri=data["verification_uri"],
        verification_uri_complete=data["verification_uri_complete"],
        expires_in=data["expires_in"],
        interval=data["interval"],
    )


def poll_for_tokens(
    api_key: str,
    device_code: str,
    base_url: str = TRUFO_API_URL,
    interval: int = 5,
    timeout: int = 300,
) -> TokenPair:
    """Poll POST /account/device/token until approved or expired.

    Args:
        api_key: Trufo API key.
        device_code: From initiate_device_auth.
        base_url: Trufo API base URL.
        interval: Seconds between polls (from server response).
        timeout: Max seconds to wait before giving up.

    Returns:
        TokenPair on approval.

    Raises:
        TimeoutError: If device code expires before user approves.
        RuntimeError: If access is denied or an unexpected error occurs.
    """
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        resp = requests.post(
            f"{base_url}{DEVICE_TOKEN}",
            headers={
                "X-API-Key": api_key,
                "Content-Type": "application/json",
            },
            json={"device_code": device_code},
            timeout=30,
        )

        if resp.status_code == 200:
            data = resp.json()
            return TokenPair(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
            )

        detail = extract_detail(resp)

        if detail == "authorization_pending":
            logger.debug("Authorization pending, polling again in %ds.", interval)
            time.sleep(interval)
            continue

        if detail in ("expired_token", "DeviceCodeNotFound"):
            raise TimeoutError("Device code expired. Please try again.")

        if detail == "access_denied":
            raise RuntimeError("Authorization was denied by the user.")

        raise RuntimeError(f"Unexpected error polling device token ({resp.status_code}): {detail}")

    raise TimeoutError(f"Timed out after {timeout}s waiting for user approval.")


def refresh_tokens(
    refresh_token: str,
    base_url: str = TRUFO_API_URL,
) -> TokenPair:
    """POST /account/refresh to get new access + refresh tokens.

    Each refresh token is single-use; the response contains a new pair.

    Args:
        refresh_token: Current refresh token (single-use).
        base_url: Trufo API base URL.

    Returns:
        TokenPair.

    Raises:
        RuntimeError: If the refresh fails (token expired, revoked, etc.).
    """
    resp = requests.post(
        f"{base_url}{ACCOUNT_REFRESH}",
        json={"refresh_token": refresh_token},
        timeout=30,
    )
    if resp.status_code != 200:
        detail = extract_detail(resp)
        raise RuntimeError(f"Token refresh failed ({resp.status_code}): {detail}")

    data = resp.json()
    return TokenPair(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
    )


def extract_detail(resp: requests.Response) -> str:
    """Extract error detail from a JSON response."""
    try:
        return resp.json().get("detail", resp.text)
    except (ValueError, AttributeError):
        return resp.text
