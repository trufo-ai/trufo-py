# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Watermark recovery helper for the Trufo TPS."""

import base64
from dataclasses import dataclass

import requests

from trufo.api.endpoints import TPS_CONTENT_RECOVER, TRUFO_API_URL
from trufo.api.headers import sdk_headers


@dataclass(frozen=True)
class ContentRecovery:
    """Result of a watermark recovery call.

    The response will grow as recovery features land (e.g. the stored C2PA
    manifest once manifest capture is live); unknown future fields are ignored.
    """

    detected: bool
    wid: str | None = None
    confidence: float | None = None
    manifest: dict | None = None


def recover_content(
    api_key: str,
    media_bytes: bytes,
    *,
    trufo_api_url: str = TRUFO_API_URL,
) -> ContentRecovery:
    """Decode a Trufo watermark from media and return its provenance.

    Accepts any parseable image or audio input; decoding is read-only and is
    not limited to the formats supported for watermark encoding.

    Args:
        api_key: API key with scope ``c2pa-decode`` (``X-API-Key`` header).
        media_bytes: Raw bytes of the media file to decode.
        trufo_api_url: Freeform Trufo API base URL. Defaults to production.

    Returns:
        Detection flag with, when detected, the watermark ID, a detection
        confidence in (0, 1], and the stored C2PA manifest when available.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    resp = requests.post(
        trufo_api_url + TPS_CONTENT_RECOVER,
        json={"media_input": base64.b64encode(media_bytes).decode()},
        headers=sdk_headers(api_key),
        timeout=60,
    )
    resp.raise_for_status()

    payload = resp.json()
    return ContentRecovery(
        detected=payload["detected"],
        wid=payload.get("wid"),
        confidence=payload.get("confidence"),
        manifest=payload.get("manifest"),
    )
