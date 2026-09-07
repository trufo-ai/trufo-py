# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Standalone bind watermarking helpers for the Trufo TPS.

Bind embeds a Trufo watermark without C2PA signing: you sign the watermarked
media with your own certificate. In provenance mode, complete the record with
:func:`bind_commit` by sending the signed manifest — the C2PA manifest
store itself, or the signed media that carries it. The manifest must declare
the mark with a ``c2pa.soft-binding`` assertion (algorithm
``ai.trufo.pawprint.watermark``, block value = the returned watermark ID)
paired with a ``c2pa.watermarked.bound`` action, per the C2PA specification.
Trufo hosts the manifest for soft-binding resolution unless you name your own
manifest store with ``manifest_endpoint``. Compliance mode embeds your
organization's mark for a declared AI class in a single call; there is nothing
to commit.

:func:`bind_watermark` and :func:`bind_commit` target production (a
``watermark-prod`` key, an active watermark-granting plan, completed OV);
the ``_test`` variants target the Trufo test host with a ``watermark-test``
key, where marks are ephemeral and nothing is billed. Compliance mode is
available on the test host only.
"""

import base64
from dataclasses import dataclass

import requests

from trufo.api.endpoints import (
    TPS_BIND_COMMIT,
    TPS_BIND_WATERMARK,
    TRUFO_API_URL,
    TRUFO_API_URL_TEST,
)
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


def bind_watermark(
    api_key: str,
    media_bytes: bytes,
    *,
    mode: str = "provenance",
    ai_compliance_label: str | None = None,
    trufo_api_url: str = TRUFO_API_URL,
) -> BindWatermark:
    """Embed a Trufo watermark in media, without C2PA signing.

    Args:
        api_key: API key with scope ``watermark-prod`` (``X-API-Key`` header);
            ``watermark-test`` on the test host.
        media_bytes: Raw bytes of the media file to watermark.
        mode: ``"provenance"`` (default; per-content mark, commit completes
            the record) or ``"compliance"`` (your org's mark for a declared
            AI class; single call).
        ai_compliance_label: Declared AI class (``"ai_generated"``,
            ``"ai_modified"``, or ``"undeclared"``); required in compliance
            mode (test host only), rejected otherwise.
        trufo_api_url: Trufo API base URL. Defaults to production; pass
            ``TRUFO_API_URL_TEST`` (or use :func:`bind_watermark_test`) for
            the test host.

    Returns:
        The watermarked media, the embedded watermark ID, and (provenance
        mode) the record ID for :func:`bind_commit`.

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


def bind_commit(
    api_key: str,
    cid: str,
    *,
    signed_media_bytes: bytes | None = None,
    manifest_bytes: bytes | None = None,
    manifest_endpoint: str | None = None,
    trufo_api_url: str = TRUFO_API_URL,
) -> None:
    """Complete a bind record with your signed C2PA manifest.

    Send exactly one of ``manifest_bytes`` (the serialized C2PA manifest
    store; preferred, it is small) or ``signed_media_bytes`` (the signed media
    carrying it). The manifest must declare the mark issued by
    :func:`bind_watermark` (see the module docstring for the required
    assertion); the API returns 400 and leaves the record incomplete
    otherwise.

    Args:
        api_key: API key with scope ``watermark-prod`` (``X-API-Key`` header);
            ``watermark-test`` on the test host.
        cid: Record ID returned by :func:`bind_watermark`.
        signed_media_bytes: Raw bytes of the C2PA-signed watermarked media.
        manifest_bytes: Raw bytes of the C2PA manifest store read from the
            signed media.
        manifest_endpoint: Base URI of your own C2PA manifest store when you
            host the manifest yourself (``https://…``; the manifest must be
            reachable at ``{manifest_endpoint}/manifests/{manifestId}``).
            Omit to have Trufo host it.
        trufo_api_url: Trufo API base URL. Defaults to production; pass
            ``TRUFO_API_URL_TEST`` (or use :func:`bind_commit_test`) for the
            test host.

    Raises:
        ValueError: If neither or both manifest sources are given.
        requests.HTTPError: If the API returns a non-2xx response.
    """
    if (signed_media_bytes is None) == (manifest_bytes is None):
        raise ValueError("Provide exactly one of signed_media_bytes or manifest_bytes.")
    body: dict = {"cid": cid}
    if manifest_bytes is not None:
        body["manifest"] = base64.b64encode(manifest_bytes).decode()
    else:
        body["media_input"] = base64.b64encode(signed_media_bytes).decode()
    if manifest_endpoint is not None:
        body["manifest_endpoint"] = manifest_endpoint
    resp = requests.post(
        trufo_api_url + TPS_BIND_COMMIT,
        json=body,
        headers=sdk_headers(api_key),
        timeout=120,
    )
    resp.raise_for_status()


def bind_watermark_test(
    api_key: str,
    media_bytes: bytes,
    *,
    mode: str = "provenance",
    ai_compliance_label: str | None = None,
    trufo_api_url: str = TRUFO_API_URL_TEST,
) -> BindWatermark:
    """:func:`bind_watermark` against the Trufo test host (``watermark-test`` key).

    Marks are ephemeral test IDs and nothing is billed; compliance mode is
    available here only.
    """
    return bind_watermark(
        api_key,
        media_bytes,
        mode=mode,
        ai_compliance_label=ai_compliance_label,
        trufo_api_url=trufo_api_url,
    )


def bind_commit_test(
    api_key: str,
    cid: str,
    *,
    signed_media_bytes: bytes | None = None,
    manifest_bytes: bytes | None = None,
    manifest_endpoint: str | None = None,
    trufo_api_url: str = TRUFO_API_URL_TEST,
) -> None:
    """:func:`bind_commit` against the Trufo test host (``watermark-test`` key)."""
    bind_commit(
        api_key,
        cid,
        signed_media_bytes=signed_media_bytes,
        manifest_bytes=manifest_bytes,
        manifest_endpoint=manifest_endpoint,
        trufo_api_url=trufo_api_url,
    )
