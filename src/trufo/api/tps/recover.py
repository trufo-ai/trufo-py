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

    What accompanies a detected watermark depends on the mark's kind: a
    provenance mark carries the stored C2PA manifest store as ``manifest_bytes``
    when one has been captured (validate it against your own copy of the
    media; ``manifest_json`` is its parse, present only when requested); a
    compliance mark carries the owning organization's declared AI class
    instead. ``oid`` is set only when the mark belongs to your own
    organization. Unknown future fields are ignored.
    """

    detected: bool
    wid: str | None = None
    confidence: float | None = None
    manifest_bytes: bytes | None = None
    manifest_json: dict | None = None
    ai_compliance_label: str | None = None
    oid: str | None = None


def recover_content(
    api_key: str,
    media_bytes: bytes,
    *,
    parse_manifest_json: bool = False,
    trufo_api_url: str = TRUFO_API_URL,
) -> ContentRecovery:
    """Decode a Trufo watermark from media and return its provenance.

    Accepts any parseable image or audio input; decoding is read-only and is
    not limited to the formats supported for watermark encoding.

    Args:
        api_key: API key with scope ``content-recover-test`` or
            ``content-recover-prod`` (``X-API-Key`` header). Each key works
            only against its own host tier.
        media_bytes: Raw bytes of the media file to decode.
        parse_manifest_json: Also return the stored manifest parsed as JSON
            (``manifest_json``). The bytes are the signed record; the parse is
            a convenience for callers without a local C2PA engine and is not a
            validation result.
        trufo_api_url: Freeform Trufo API base URL. Defaults to production;
            pass ``TRUFO_API_URL_TEST`` with a ``content-recover-test`` key.

    Returns:
        Detection flag with, when detected, the watermark ID, a detection
        confidence in (0, 1], and the stored C2PA manifest store bytes when
        available.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    resp = requests.post(
        trufo_api_url + TPS_CONTENT_RECOVER,
        json={
            "media_input": base64.b64encode(media_bytes).decode(),
            "parse_manifest_json": parse_manifest_json,
        },
        headers=sdk_headers(api_key),
        timeout=60,
    )
    resp.raise_for_status()

    payload = resp.json()
    manifest_b64 = payload.get("manifest_bytes")
    return ContentRecovery(
        detected=payload["detected"],
        wid=payload.get("wid"),
        confidence=payload.get("confidence"),
        manifest_bytes=base64.b64decode(manifest_b64) if manifest_b64 else None,
        manifest_json=payload.get("manifest_json"),
        ai_compliance_label=payload.get("ai_compliance_label"),
        oid=payload.get("oid"),
    )
