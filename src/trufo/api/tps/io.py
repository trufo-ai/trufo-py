# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared media upload helpers for signing and watermarking."""

from dataclasses import dataclass

import requests

from trufo.api.endpoints import TPS_GET_S3_UPLOAD_URL, TRUFO_API_URL
from trufo.api.headers import sdk_headers


@dataclass(frozen=True)
class S3Upload:
    """An upload URL and the Trufo reference to use after uploading."""

    upload_url: str
    media_input_s3: str
    expires_at: int
    duration: str


def get_s3_upload_url(
    api_key: str,
    mime_type: str,
    duration: str | None = None,
    *,
    trufo_api_url: str = TRUFO_API_URL,
) -> S3Upload:
    """Allocate a media upload using a signing or watermark API key.

    PUT the media bytes to ``upload_url`` with the supplied Content-Type.
    Submit ``media_input_s3`` to the same API region after the upload succeeds.
    ``duration`` may be omitted or set to ``"5m"``.
    """
    body = {"mime_type": mime_type}
    if duration is not None:
        body["duration"] = duration
    response = requests.post(
        trufo_api_url + TPS_GET_S3_UPLOAD_URL,
        json=body,
        headers=sdk_headers(api_key),
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    return S3Upload(
        upload_url=payload["upload_url"],
        media_input_s3=payload["media_input_s3"],
        expires_at=payload["expires_at"],
        duration=payload["duration"],
    )
