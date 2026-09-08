# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Bind: Trufo watermarks on media you sign yourself.

Bind embeds a Trufo watermark without Trufo signing: you sign the watermarked
media with your own certificate, then complete the record with
:func:`bind_commit` by sending the signed manifest. The manifest must declare
the mark with a ``c2pa.soft-binding`` assertion (algorithm
``ai.trufo.pawprint.watermark``, block value = the watermark ID) paired with a
``c2pa.watermarked.bound`` action, per the C2PA specification. Trufo hosts the
manifest for soft-binding resolution unless you name your own manifest store
with ``manifest_endpoint``.

Two routes share the commit step:

- tpls (trufo-processing, local-signing): :func:`bind_watermark` embeds the
  mark on Trufo's servers and returns the marked media with its watermark ID
  and record ID; you sign, then :func:`bind_commit`.
- lpls (local-processing, local-signing): :func:`bind_reserve` issues the
  watermark ID and record ID for a MIME type, :func:`watermark_media` embeds
  the mark locally with the Trufo engine (``trufo[local-full]``), you sign,
  then :func:`bind_commit`.

Production requires a ``watermark-prod`` key, an active C2PA Signing or
Watermark API plan, and completed organization validation; the ``_test``
variants target the Trufo test host with a ``watermark-test`` key, where marks
are ephemeral and nothing is billed. Compliance mode (your organization's mark
for a declared AI class, a single :func:`bind_watermark` call with nothing to
commit) is available on the test host only.
"""

import base64
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import requests

from trufo.api.endpoints import (
    TPS_BIND_COMMIT,
    TPS_BIND_RESERVE,
    TPS_BIND_WATERMARK,
    TRUFO_API_URL,
    TRUFO_API_URL_TEST,
)
from trufo.api.headers import sdk_headers
from trufo.c2pa.watermark import AiComplianceLabel, WatermarkMode

_ENGINE_HINT = (
    "Local watermarking requires the Trufo engine. Install it with: "
    "pip install 'trufo[local-full]'."
)
_C2PA_HINT = (
    "Reading a manifest store out of signed media requires the local C2PA "
    "library. Install it with: pip install 'trufo[local-sign-only]', or send "
    "the manifest store bytes with manifest_bytes= instead."
)


@dataclass(frozen=True)
class BindWatermark:
    """Result of :func:`bind_watermark`.

    ``cid`` addresses the record for the commit step; compliance marks have
    no record, so no cid.
    """

    media: bytes
    wid: str
    cid: str | None = None


@dataclass(frozen=True)
class BindReservation:
    """Result of :func:`bind_reserve`: the record and the watermark ID to embed.

    ``wid_package`` is what :func:`watermark_media` consumes; ``expires_at`` is
    the RFC 3339 expiry of the reservation (24 hours; 1 hour on the test host).
    """

    cid: str
    wid: str
    expires_at: str
    # the package exactly as the server issued it, so fields added later pass through
    wid_package: dict = field(default_factory=dict)


def _validate_mode(mode: str, ai_compliance_label: str | None) -> None:
    """Enforce the mode/label pairing before any bytes leave the client."""
    try:
        WatermarkMode(mode)
    except (TypeError, ValueError) as exc:
        raise ValueError("The 'mode' parameter must be 'provenance' or 'compliance'.") from exc
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
            "The 'ai_compliance_label' parameter applies only to compliance-mode " "watermarks."
        )


def _post(api_key: str, url: str, body: dict) -> dict:
    resp = requests.post(url, json=body, headers=sdk_headers(api_key), timeout=120)
    resp.raise_for_status()
    return resp.json()


def bind_watermark(
    api_key: str,
    media_bytes: bytes,
    *,
    mode: str = "provenance",
    ai_compliance_label: str | None = None,
    trufo_api_url: str = TRUFO_API_URL,
) -> BindWatermark:
    """tpls step 1: embed a Trufo watermark in media on Trufo's servers.

    Args:
        api_key: API key with scope ``watermark-prod`` (``X-API-Key`` header);
            ``watermark-test`` on the test host.
        media_bytes: Raw bytes of the media file to watermark.
        mode: ``"provenance"`` (default; per-content mark, commit completes
            the record) or ``"compliance"`` (your org's mark for a declared
            AI class; single call, test host only).
        ai_compliance_label: Declared AI class (``"ai_generated"``,
            ``"ai_modified"``, or ``"undeclared"``); required in compliance
            mode, rejected otherwise.
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
    payload = _post(api_key, trufo_api_url + TPS_BIND_WATERMARK, body)
    return BindWatermark(
        media=base64.b64decode(payload["media_output"]),
        wid=payload["wid"],
        cid=payload.get("cid"),
    )


def bind_reserve(
    api_key: str,
    mime_type: str,
    *,
    trufo_api_url: str = TRUFO_API_URL,
) -> BindReservation:
    """lpls step 1: reserve a watermark ID for media you will watermark locally.

    Args:
        api_key: API key with scope ``watermark-prod`` (``watermark-test`` on
            the test host).
        mime_type: MIME type of the media (it must be an encode-supported
            format).
        trufo_api_url: Trufo API base URL. Defaults to production.

    Returns:
        The record ID and the reservation to pass to :func:`watermark_media`.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    payload = _post(api_key, trufo_api_url + TPS_BIND_RESERVE, {"mime_type": mime_type})
    package = payload["wid_package"]
    return BindReservation(
        cid=payload["cid"], wid=package["wid"], expires_at=package["expires_at"], wid_package=dict(package)
    )


def watermark_media(media_bytes: bytes, wid_package: dict) -> bytes:
    """lpls step 2: embed a reserved watermark ID with the local Trufo engine.

    Args:
        media_bytes: Raw bytes of the media file to watermark.
        wid_package: ``BindReservation.wid_package`` (or the ``wid_package``
            of a Trufo API response).

    Returns:
        The watermarked media bytes, in the input's format.

    Raises:
        ImportError: If the engine (``trufo[local-full]``) is not installed.
    """
    try:
        from tfprov.util import pawprint_import
    except ImportError as exc:
        raise ImportError(_ENGINE_HINT) from exc
    package = pawprint_import.WatermarkIdPackage(**wid_package)
    return pawprint_import.encode(media_bytes, package)


def _manifest_store_from_media(signed_media_bytes: bytes) -> bytes:
    """The serialized C2PA manifest store embedded in signed media."""
    try:
        from tfprov.c2pa_rs_bridge import rs_bridge
        from tfprov.util.av_format import get_extension, get_media_probe_result
    except ImportError as exc:
        raise ImportError(_C2PA_HINT) from exc
    if not rs_bridge.is_available():
        raise ImportError(_C2PA_HINT)
    probe = get_media_probe_result(signed_media_bytes)
    with tempfile.TemporaryDirectory(prefix="trufo-bind-") as tmp_dir:
        path = Path(tmp_dir) / f"signed.{get_extension(probe.mime_type)}"
        path.write_bytes(signed_media_bytes)
        return rs_bridge.read_manifest_bytes(path=str(path))


def bind_commit(
    api_key: str,
    cid: str,
    wid: str,
    *,
    manifest_bytes: bytes | None = None,
    manifest_id: str | None = None,
    manifest_endpoint: str | None = None,
    signed_media_bytes: bytes | None = None,
    trufo_api_url: str = TRUFO_API_URL,
) -> None:
    """Complete a bind record with your signed C2PA manifest.

    Give exactly one manifest source: ``manifest_bytes`` (the serialized
    C2PA manifest store), ``signed_media_bytes`` (the signed media; the store
    is read out locally, which needs ``trufo[local-sign-only]``), or
    ``manifest_id`` together with ``manifest_endpoint`` when the manifest
    lives in your own store and you want Trufo to record only its id. With
    bytes, the manifest must declare the mark issued with the record (see the
    module docstring); the API returns 400 and leaves the record incomplete
    otherwise.

    Args:
        api_key: API key with scope ``watermark-prod`` (``watermark-test`` on
            the test host).
        cid: Record ID from :func:`bind_watermark` or :func:`bind_reserve`.
        wid: Watermark ID issued with that record.
        manifest_bytes: Raw bytes of the C2PA manifest store.
        manifest_id: The manifest's id (its urn); requires ``manifest_endpoint``.
        manifest_endpoint: Base URI of your own C2PA manifest store
            (``https://…``; the manifest must be reachable at
            ``{manifest_endpoint}/manifests/{manifestId}``). Omit to have
            Trufo host the manifest.
        signed_media_bytes: Raw bytes of the C2PA-signed watermarked media.
        trufo_api_url: Trufo API base URL. Defaults to production.

    Raises:
        ValueError: If not exactly one manifest source is given, or
            ``manifest_id`` comes without ``manifest_endpoint``.
        ImportError: If ``signed_media_bytes`` is given without the local
            C2PA library.
        requests.HTTPError: If the API returns a non-2xx response.
    """
    sources = [s for s in (manifest_bytes, manifest_id, signed_media_bytes) if s is not None]
    if len(sources) != 1:
        raise ValueError(
            "Provide exactly one of manifest_bytes, manifest_id, or signed_media_bytes."
        )
    if manifest_id is not None and manifest_endpoint is None:
        raise ValueError("manifest_id requires manifest_endpoint.")
    if signed_media_bytes is not None:
        manifest_bytes = _manifest_store_from_media(signed_media_bytes)
    body: dict = {"cid": cid, "wid": wid}
    if manifest_bytes is not None:
        body["manifest"] = base64.b64encode(manifest_bytes).decode()
    else:
        body["manifest_id"] = manifest_id
    if manifest_endpoint is not None:
        body["manifest_endpoint"] = manifest_endpoint
    _post(api_key, trufo_api_url + TPS_BIND_COMMIT, body)


def bind_watermark_test(
    api_key: str,
    media_bytes: bytes,
    *,
    mode: str = "provenance",
    ai_compliance_label: str | None = None,
    trufo_api_url: str = TRUFO_API_URL_TEST,
) -> BindWatermark:
    """:func:`bind_watermark` against the Trufo test host (``watermark-test`` key)."""
    return bind_watermark(
        api_key,
        media_bytes,
        mode=mode,
        ai_compliance_label=ai_compliance_label,
        trufo_api_url=trufo_api_url,
    )


def bind_reserve_test(
    api_key: str,
    mime_type: str,
    *,
    trufo_api_url: str = TRUFO_API_URL_TEST,
) -> BindReservation:
    """:func:`bind_reserve` against the Trufo test host (``watermark-test`` key)."""
    return bind_reserve(api_key, mime_type, trufo_api_url=trufo_api_url)


def bind_commit_test(
    api_key: str,
    cid: str,
    wid: str,
    *,
    manifest_bytes: bytes | None = None,
    manifest_id: str | None = None,
    manifest_endpoint: str | None = None,
    signed_media_bytes: bytes | None = None,
    trufo_api_url: str = TRUFO_API_URL_TEST,
) -> None:
    """:func:`bind_commit` against the Trufo test host (``watermark-test`` key)."""
    bind_commit(
        api_key,
        cid,
        wid,
        manifest_bytes=manifest_bytes,
        manifest_id=manifest_id,
        manifest_endpoint=manifest_endpoint,
        signed_media_bytes=signed_media_bytes,
        trufo_api_url=trufo_api_url,
    )
