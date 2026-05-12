# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
C2PA signing helpers for the Trufo TPS.
"""

import base64
from dataclasses import dataclass

import requests

from trufo.api.endpoints import (
    TRUFO_API_URL,
    TPS_C2PA_GET_S3_URL,
    TPS_C2PA_SIGN,
    TPS_C2PA_SIGN_TEST,
)


@dataclass(frozen=True)
class C2PAS3Upload:
    """Ephemeral S3 upload target for C2PA signing."""

    upload_url: str
    media_input_s3: str
    expires_at: int
    duration: str


@dataclass(frozen=True)
class C2PAS3SignedOutput:
    """Ephemeral S3 signed output reference."""

    media_output_s3: str


def _validate_assertions(assertions: list | None) -> None:
    """Validate client-side assertion requirements shared by C2PA helpers."""
    if assertions and not any(a[0] == "cawg_identity" for a in assertions):
        raise ValueError("'cawg_identity' is required when assertions are provided")


def _sign_c2pa_direct(
    endpoint: str,
    api_key: str,
    media_bytes: bytes,
    actions: list | None = None,
    assertions: list | None = None,
) -> bytes:
    """Sign media bytes through a C2PA signing endpoint."""
    _validate_assertions(assertions)

    body = {
        "media_input": base64.b64encode(media_bytes).decode(),
        "actions": actions or [],
        "assertions": assertions or [],
    }

    resp = requests.post(
        TRUFO_API_URL + endpoint,
        json=body,
        headers={"X-API-Key": api_key},
        timeout=60,
    )
    resp.raise_for_status()

    return base64.b64decode(resp.json()["media_output"])


def get_c2pa_s3_upload_url(
    api_key: str,
    mime_type: str,
    duration: str | None = None,
) -> C2PAS3Upload:
    """Request an ephemeral S3 upload URL for C2PA signing.

    The returned ``media_input_s3`` reference can be passed to
    :func:`sign_c2pa_s3` or :func:`sign_c2pa_test_s3` after uploading media
    bytes to ``upload_url``.

    Args:
        api_key: API key with scope ``c2pa-sign-prod`` or ``c2pa-sign-test``.
        mime_type: MIME type of the object to upload.
        duration: Optional server-supported duration value. Currently ``"5m"``.

    Returns:
        Ephemeral upload URL, signed media reference, expiry, and duration.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    body = {"mime_type": mime_type}
    if duration is not None:
        body["duration"] = duration

    resp = requests.post(
        TRUFO_API_URL + TPS_C2PA_GET_S3_URL,
        json=body,
        headers={"X-API-Key": api_key},
        timeout=60,
    )
    resp.raise_for_status()

    payload = resp.json()
    return C2PAS3Upload(
        upload_url=payload["upload_url"],
        media_input_s3=payload["media_input_s3"],
        expires_at=payload["expires_at"],
        duration=payload["duration"],
    )


def _sign_c2pa_s3(
    endpoint: str,
    api_key: str,
    media_input_s3: str,
    actions: list | None = None,
    assertions: list | None = None,
) -> C2PAS3SignedOutput:
    """Sign an uploaded ephemeral S3 object through a C2PA signing endpoint."""
    _validate_assertions(assertions)

    resp = requests.post(
        TRUFO_API_URL + endpoint,
        json={
            "media_input_s3": media_input_s3,
            "actions": actions or [],
            "assertions": assertions or [],
        },
        headers={"X-API-Key": api_key},
        timeout=60,
    )
    resp.raise_for_status()

    return C2PAS3SignedOutput(media_output_s3=resp.json()["media_output_s3"])


def sign_c2pa_s3(
    api_key: str,
    media_input_s3: str,
    actions: list | None = None,
    assertions: list | None = None,
) -> C2PAS3SignedOutput:
    """Sign an uploaded ephemeral S3 object with production C2PA via the TPS.

    Args:
        api_key: API key with scope ``c2pa-sign-prod``.
        media_input_s3: Opaque reference returned by :func:`get_c2pa_s3_upload_url`.
        actions: Ordered list of ``[action_name, params]`` pairs (default ``[]``).
        assertions: List of ``[assertion_name, params]`` pairs (default ``[]``).

    Returns:
        Presigned S3 download URL for the signed output media.

    Raises:
        ValueError: If ``assertions`` is provided without a ``"cawg_identity"`` entry.
        requests.HTTPError: If the API returns a non-2xx response.
    """
    return _sign_c2pa_s3(
        TPS_C2PA_SIGN,
        api_key,
        media_input_s3,
        actions=actions,
        assertions=assertions,
    )


def sign_c2pa_test_s3(
    api_key: str,
    media_input_s3: str,
    actions: list | None = None,
    assertions: list | None = None,
) -> C2PAS3SignedOutput:
    """Sign an uploaded ephemeral S3 object with test C2PA via the TPS.

    Args:
        api_key: API key with scope ``c2pa-sign-test``.
        media_input_s3: Opaque reference returned by :func:`get_c2pa_s3_upload_url`.
        actions: Ordered list of ``[action_name, params]`` pairs (default ``[]``).
        assertions: List of ``[assertion_name, params]`` pairs (default ``[]``).

    Returns:
        Presigned S3 download URL for the signed output media.

    Raises:
        ValueError: If ``assertions`` is provided without a ``"cawg_identity"`` entry.
        requests.HTTPError: If the API returns a non-2xx response.
    """
    return _sign_c2pa_s3(
        TPS_C2PA_SIGN_TEST,
        api_key,
        media_input_s3,
        actions=actions,
        assertions=assertions,
    )


def sign_c2pa_via_s3(
    api_key: str,
    media_bytes: bytes,
    mime_type: str,
    actions: list | None = None,
    assertions: list | None = None,
    duration: str | None = None,
) -> bytes:
    """Upload, production-sign, and download media through the ephemeral S3 flow.

    This convenience helper composes the low-level helpers:
    :func:`get_c2pa_s3_upload_url` and :func:`sign_c2pa_s3`.

    Args:
        api_key: API key with scope ``c2pa-sign-prod``.
        media_bytes: Raw bytes of the media file to sign.
        mime_type: MIME type of the media file.
        actions: Ordered list of ``[action_name, params]`` pairs (default ``[]``).
        assertions: List of ``[assertion_name, params]`` pairs (default ``[]``).
        duration: Optional server-supported S3 URL duration. Currently ``"5m"``.

    Returns:
        Signed media bytes downloaded from the returned S3 output URL.

    Raises:
        ValueError: If ``assertions`` is provided without a ``"cawg_identity"`` entry.
        requests.HTTPError: If an API, upload, or download request fails.
    """
    upload = get_c2pa_s3_upload_url(api_key, mime_type, duration=duration)
    _upload_c2pa_s3_media(upload.upload_url, media_bytes, mime_type)
    signed_output = sign_c2pa_s3(
        api_key,
        upload.media_input_s3,
        actions=actions,
        assertions=assertions,
    )
    return _download_c2pa_s3_media(signed_output.media_output_s3)


def sign_c2pa_test_via_s3(
    api_key: str,
    media_bytes: bytes,
    mime_type: str,
    actions: list | None = None,
    assertions: list | None = None,
    duration: str | None = None,
) -> bytes:
    """Upload, test-sign, and download media through the ephemeral S3 flow.

    This convenience helper composes the low-level helpers:
    :func:`get_c2pa_s3_upload_url` and :func:`sign_c2pa_test_s3`.

    Args:
        api_key: API key with scope ``c2pa-sign-test``.
        media_bytes: Raw bytes of the media file to sign.
        mime_type: MIME type of the media file.
        actions: Ordered list of ``[action_name, params]`` pairs (default ``[]``).
        assertions: List of ``[assertion_name, params]`` pairs (default ``[]``).
        duration: Optional server-supported S3 URL duration. Currently ``"5m"``.

    Returns:
        Signed media bytes downloaded from the returned S3 output URL.

    Raises:
        ValueError: If ``assertions`` is provided without a ``"cawg_identity"`` entry.
        requests.HTTPError: If an API, upload, or download request fails.
    """
    upload = get_c2pa_s3_upload_url(api_key, mime_type, duration=duration)
    _upload_c2pa_s3_media(upload.upload_url, media_bytes, mime_type)
    signed_output = sign_c2pa_test_s3(
        api_key,
        upload.media_input_s3,
        actions=actions,
        assertions=assertions,
    )
    return _download_c2pa_s3_media(signed_output.media_output_s3)


def _upload_c2pa_s3_media(upload_url: str, media_bytes: bytes, mime_type: str) -> None:
    """Upload media bytes to an ephemeral presigned S3 URL."""
    resp = requests.put(
        upload_url,
        content=media_bytes,
        headers={"Content-Type": mime_type},
        timeout=60,
    )
    resp.raise_for_status()


def _download_c2pa_s3_media(download_url: str) -> bytes:
    """Download signed media bytes from an ephemeral presigned S3 URL."""
    resp = requests.get(download_url, timeout=60)
    resp.raise_for_status()
    return resp.content


def sign_c2pa(
    api_key: str,
    media_bytes: bytes,
    actions: list | None = None,
    assertions: list | None = None,
) -> bytes:
    """Sign a media file with production C2PA via the TPS.

    Args:
        api_key: API key with scope ``c2pa-sign-prod`` (``X-API-Key`` header).
        media_bytes: Raw bytes of the media file to sign.
        actions: Ordered list of ``[action_name, params]`` pairs (default ``[]``).
        assertions: List of ``[assertion_name, params]`` pairs (default ``[]``).
            If provided, ``"cawg_identity"`` must be one of the entries.

    Returns:
        Signed media bytes.

    Raises:
        ValueError: If ``assertions`` is provided without a ``"cawg_identity"`` entry.
        requests.HTTPError: If the API returns a non-2xx response.
    """
    return _sign_c2pa_direct(
        TPS_C2PA_SIGN,
        api_key,
        media_bytes,
        actions=actions,
        assertions=assertions,
    )


def sign_c2pa_test(
    api_key: str,
    media_bytes: bytes,
    actions: list | None = None,
    assertions: list | None = None,
) -> bytes:
    """Sign a media file with C2PA via the TPS test endpoint.

    Args:
        api_key: API key with scope ``c2pa-sign-test`` (``X-API-Key`` header).
        media_bytes: Raw bytes of the media file to sign.
        actions: Ordered list of ``[action_name, params]`` pairs (default ``[]``).
        assertions: List of ``[assertion_name, params]`` pairs (default ``[]``).
            If provided, ``"cawg_identity"`` must be one of the entries.

    Returns:
        Signed media bytes.

    Raises:
        ValueError: If ``assertions`` is provided without a ``"cawg_identity"`` entry.
        requests.HTTPError: If the API returns a non-2xx response.
    """
    return _sign_c2pa_direct(
        TPS_C2PA_SIGN_TEST,
        api_key,
        media_bytes,
        actions=actions,
        assertions=assertions,
    )
