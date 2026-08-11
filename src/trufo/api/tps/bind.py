# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Standalone bind watermarking helpers for the Trufo TPS (test host).

Bind embeds a Trufo watermark without C2PA signing: you sign the watermarked
media with your own certificate. In provenance mode, complete the record by
submitting the signed media to :func:`bind_commit_test` — its manifest must
declare the mark with a ``c2pa.soft-binding`` assertion (algorithm
``ai.trufo.pawprint.watermark``, block value = the returned watermark ID)
paired with a ``c2pa.watermarked.bound`` action, per the C2PA specification.
Compliance mode embeds your organization's mark for a declared AI class in a
single call; there is nothing to commit.
"""

import base64
from dataclasses import dataclass

import requests

from trufo.api.endpoints import TPS_BIND_COMMIT, TPS_BIND_WATERMARK, TRUFO_API_URL_TEST
from trufo.api.headers import sdk_headers
from trufo.c2pa.watermark import AiComplianceLabel, WatermarkMode


@dataclass(frozen=True)
class BindWatermark:
    """Result of a bind watermark call.

    ``cid`` addresses the record for the commit step; compliance marks have
    no record, so no cid.
    """

    media: bytes
    wid: str
    cid: str | None = None


def _validate_mode(mode: str, ai_compliance_label: str | None) -> None:
    """Enforce the mode/label pairing before any bytes leave the client."""
    try:
        WatermarkMode(mode)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "The 'mode' parameter must be 'provenance' or 'compliance'."
        ) from exc
    if mode == WatermarkMode.COMPLIANCE.value:
        try:
            AiComplianceLabel(ai_compliance_label)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Compliance-mode watermarks require the 'ai_compliance_label' "
                "parameter: one of 'ai_generated', 'ai_modified', or 'undeclared'."
            ) from exc
    elif ai_compliance_label is not None:
        raise ValueError(
            "The 'ai_compliance_label' parameter applies only to compliance-mode "
            "watermarks."
        )


def bind_watermark_test(
    api_key: str,
    media_bytes: bytes,
    *,
    mode: str = "provenance",
    ai_compliance_label: str | None = None,
    trufo_api_url: str = TRUFO_API_URL_TEST,
) -> BindWatermark:
    """Embed a Trufo watermark in media, without C2PA signing.

    Args:
        api_key: API key with scope ``watermark-test`` (``X-API-Key`` header).
        media_bytes: Raw bytes of the media file to watermark.
        mode: ``"provenance"`` (default; per-content mark, commit completes
            the record) or ``"compliance"`` (your org's mark for a declared
            AI class; single call).
        ai_compliance_label: Declared AI class (``"ai_generated"``,
            ``"ai_modified"``, or ``"undeclared"``); required in compliance
            mode, rejected otherwise.
        trufo_api_url: Trufo API base URL. Defaults to the Trufo test host
            (test.api.trufo.ai).

    Returns:
        The watermarked media, the embedded watermark ID, and (provenance
        mode) the record ID for :func:`bind_commit_test`.

    Raises:
        ValueError: On an invalid mode/label pairing.
        requests.HTTPError: If the API returns a non-2xx response.
    """
    _validate_mode(mode, ai_compliance_label)
    body: dict = {
        "media_input": base64.b64encode(media_bytes).decode(),
        "mode": mode,
    }
    if ai_compliance_label is not None:
        body["ai_compliance_label"] = ai_compliance_label
    resp = requests.post(
        trufo_api_url + TPS_BIND_WATERMARK,
        json=body,
        headers=sdk_headers(api_key),
        timeout=120,
    )
    resp.raise_for_status()

    payload = resp.json()
    return BindWatermark(
        media=base64.b64decode(payload["media_output"]),
        wid=payload["wid"],
        cid=payload.get("cid"),
    )


def bind_commit_test(
    api_key: str,
    cid: str,
    signed_media_bytes: bytes,
    *,
    trufo_api_url: str = TRUFO_API_URL_TEST,
) -> None:
    """Complete a bind record with your C2PA-signed media.

    The media's manifest must declare the mark issued by
    :func:`bind_watermark_test` (see the module docstring for the required
    assertion); the API returns 400 and leaves the record incomplete
    otherwise.

    Args:
        api_key: API key with scope ``watermark-test`` (``X-API-Key`` header).
        cid: Record ID returned by :func:`bind_watermark_test`.
        signed_media_bytes: Raw bytes of the C2PA-signed watermarked media.
        trufo_api_url: Trufo API base URL. Defaults to the Trufo test host
            (test.api.trufo.ai).

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    resp = requests.post(
        trufo_api_url + TPS_BIND_COMMIT,
        json={
            "cid": cid,
            "media_input": base64.b64encode(signed_media_bytes).decode(),
        },
        headers=sdk_headers(api_key),
        timeout=120,
    )
    resp.raise_for_status()
