# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Bind: Trufo watermarks on media you sign yourself.

Bind embeds a Trufo watermark without Trufo signing: you sign the watermarked
media with your own certificate, then complete the record with
:func:`bind_commit` by sending the signed manifest. The manifest must declare
the mark with a ``c2pa.soft-binding`` assertion (algorithm
``ai.trufo.pawprint.watermark``, block value = the watermark ID) paired with a
``c2pa.watermarked.bound`` action, per the C2PA specification. Trufo hosts the
manifest for soft-binding resolution.

Two routes share the commit step:

- tpls (trufo-processing, local-signing): :func:`bind_watermark` embeds the
  mark on Trufo's servers and returns the marked media with its watermark ID
  and record ID; you sign, then :func:`bind_commit`.
- lpls (local-processing, local-signing): :func:`bind_reserve` issues the
  watermark ID and record ID for a MIME type, :func:`watermark_media` embeds
  the mark locally with the Trufo engine (``trufo[local-full]``), you sign,
  then :func:`bind_commit`.

A per-AI-system bind (``wid_allocation_mode="per_ai_system"`` with
``ai_system_id`` and ``ai_involvement``) embeds your AI system's watermark ID
for that AI involvement instead of a new one. It is not a C2PA soft binding,
and its commit is optional but recommended. Declare it with a
``c2pa.watermarked.unbound`` action.

Production requires a ``watermark-prod`` key, an active C2PA Signing or
Watermark API plan, and completed organization validation; the ``_test``
variants target the Trufo test host with a ``watermark-test`` key, where marks
are ephemeral and nothing is billed. Compliance watermarking is unsupported.
"""

import base64
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import requests

from trufo.api.endpoints import (
    TPS_BIND_COMMIT_PATH,
    TPS_BIND_RESERVE_PATH,
    TPS_BIND_WATERMARK_PATH,
    TRUFO_API_URL,
    TRUFO_API_URL_TEST,
)
from trufo.api.headers import sdk_headers
from trufo.api.tps.io import _upload_task_input
from trufo.api.tps.tasks import (
    ExecutionMode,
    TaskReceipt,
    _download_task_output,
    _submit_task,
    wait_for_task,
)
from trufo.c2pa.ai_system import AIInvolvement
from trufo.c2pa.watermark import WatermarkIDAllocationMode, WatermarkMode, WatermarkSettings
from trufo.util.deprecation import deprecated_aliases
from trufo.util.warnings import emit_server_warnings

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
class BindWatermarkResult:
    """Result of :func:`bind_watermark`.

    ``cid`` addresses the record for the commit step.
    """

    media: bytes
    wid: str
    cid: str | None = None


@dataclass(frozen=True)
class BindReserveResult:
    """Result of :func:`bind_reserve`: the record and the watermark ID to embed.

    ``wid_package`` is what :func:`watermark_media` consumes; ``expires_at`` is
    the RFC 3339 expiry of the reservation: 24 hours for a per-embed one (1 hour
    on the test host), 1 hour for a per-AI-system one.
    """

    cid: str
    wid: str
    expires_at: str
    # the package exactly as the server issued it, so fields added later pass through
    wid_package: dict = field(default_factory=dict)


def _post(api_key: str, url: str, body: dict) -> dict:
    resp = requests.post(url, json=body, headers=sdk_headers(api_key), timeout=120)
    resp.raise_for_status()
    return resp.json()


def _allocation_fields(
    *,
    wid_allocation_mode: WatermarkIDAllocationMode | str | None,
    ai_system_id: str | None,
    ai_involvement: AIInvolvement | str | None,
    mode: str | None = None,
) -> dict:
    """Validate the watermark ID allocation arguments and return the set ones as request keys."""
    fields: dict = {}
    if mode is not None:
        # TODO(sunset-2027-01-31): WatermarkMode and the watermark 'mode' parameter go;
        # successor WatermarkIDAllocationMode
        if wid_allocation_mode is not None:
            raise ValueError(
                "Provide the watermark 'wid_allocation_mode' parameter or the deprecated "
                "'mode', not both."
            )
        WatermarkMode.validate(mode)
        fields["mode"] = mode
    if wid_allocation_mode is not None:
        fields["wid_allocation_mode"] = WatermarkIDAllocationMode.validate(
            wid_allocation_mode
        ).value
    if ai_system_id is not None:
        fields["ai_system_id"] = ai_system_id
    if ai_involvement is not None:
        fields["ai_involvement"] = AIInvolvement.validate(ai_involvement).value
    return fields


def bind_watermark(
    api_key: str,
    media_bytes: bytes,
    *,
    wid_allocation_mode: WatermarkIDAllocationMode | str | None = None,
    ai_system_id: str | None = None,
    ai_involvement: AIInvolvement | str | None = None,
    mode: str | None = None,
    execution_mode: ExecutionMode = ExecutionMode.REQUEST,
    mime_type: str | None = None,
    wait_seconds: float = 600,
    trufo_api_url: str = TRUFO_API_URL,
) -> BindWatermarkResult:
    """tpls step 1: embed a Trufo watermark in media on Trufo's servers.

    Args:
        api_key: API key with scope ``watermark-prod`` (``X-API-Key`` header);
            ``watermark-test`` on the test host.
        media_bytes: Raw bytes of the media file to watermark.
        wid_allocation_mode: ``"per_embed"`` (default when omitted) or ``"per_ai_system"``.
        ai_system_id: ID (``aisys_...``) of your AI system; required for ``"per_ai_system"``.
        ai_involvement: ``"ai_generated"`` or ``"ai_modified"``; required for ``"per_ai_system"``.
        mode: Deprecated: use ``wid_allocation_mode`` (``"per_embed"`` replaces
            ``"provenance"``). ``"compliance"`` is unsupported and raises
            NotImplementedError before sending a request.
        execution_mode: REQUEST (default) or explicit TASK; no automatic fallback.
        mime_type: Required for TASK bytes uploaded to S3.
        wait_seconds: Local TASK waiting budget (default 600), not the server
            execution timeout. TaskWaitTimeoutError retains the task ID.
        trufo_api_url: Trufo API base URL. Defaults to production; pass
            ``TRUFO_API_URL_TEST`` (or use :func:`bind_watermark_test`) for
            the test host.

    Returns:
        The watermarked media, the embedded watermark ID, and the record ID
        for :func:`bind_commit`.

    Raises:
        ValueError: On invalid or conflicting modes, invalid AI involvement,
            execution settings, or missing MIME type.
        NotImplementedError: For ``"per_asset"`` allocation or ``"compliance"`` mode.
        requests.HTTPError: If the API returns a non-2xx response.
    """
    allocation = _allocation_fields(
        wid_allocation_mode=wid_allocation_mode,
        ai_system_id=ai_system_id,
        ai_involvement=ai_involvement,
        mode=mode,
    )
    if ExecutionMode.validate(execution_mode) == ExecutionMode.TASK:
        if wait_seconds <= 0:
            raise ValueError("Wait duration must be positive.")
        reference = _upload_task_input(api_key, media_bytes, mime_type, trufo_api_url=trufo_api_url)
        receipt = submit_bind_watermark(
            api_key,
            reference,
            wid_allocation_mode=wid_allocation_mode,
            ai_system_id=ai_system_id,
            ai_involvement=ai_involvement,
            mode=mode,
            trufo_api_url=trufo_api_url,
        )
        task = wait_for_task(
            api_key, receipt.task_id, wait_seconds=wait_seconds, trufo_api_url=trufo_api_url
        )
        return BindWatermarkResult(_download_task_output(task), task.result.wid, task.result.cid)
    body: dict = {
        "media_input": base64.b64encode(media_bytes).decode(),
        **allocation,
    }
    payload = _post(api_key, trufo_api_url + TPS_BIND_WATERMARK_PATH, body)
    emit_server_warnings(payload)
    return BindWatermarkResult(
        media=base64.b64decode(payload["media_output"]),
        wid=payload["wid"],
        cid=payload.get("cid"),
    )


def submit_bind_watermark(
    api_key: str,
    media_input_s3: str,
    *,
    wid_allocation_mode: WatermarkIDAllocationMode | str | None = None,
    ai_system_id: str | None = None,
    ai_involvement: AIInvolvement | str | None = None,
    mode: str | None = None,
    trufo_api_url: str = TRUFO_API_URL,
) -> TaskReceipt:
    """Submit a Trufo upload reference for watermarking without waiting.

    Poll with get_task() or wait_for_task(). Completion does not replace the
    separate bind_commit() step after signing the watermarked media.
    """
    body = {
        "media_input_s3": media_input_s3,
        **_allocation_fields(
            wid_allocation_mode=wid_allocation_mode,
            ai_system_id=ai_system_id,
            ai_involvement=ai_involvement,
            mode=mode,
        ),
    }
    return _submit_task(api_key, TPS_BIND_WATERMARK_PATH, body, trufo_api_url=trufo_api_url)


def bind_reserve(
    api_key: str,
    mime_type: str,
    *,
    wid_allocation_mode: WatermarkIDAllocationMode | str | None = None,
    ai_system_id: str | None = None,
    ai_involvement: AIInvolvement | str | None = None,
    trufo_api_url: str = TRUFO_API_URL,
) -> BindReserveResult:
    """lpls step 1: reserve a watermark ID for media you will watermark locally.

    Args:
        api_key: API key with scope ``watermark-prod`` (``watermark-test`` on
            the test host).
        mime_type: MIME type of the media (it must be an encode-supported
            format).
        wid_allocation_mode: ``"per_embed"`` (default when omitted) or ``"per_ai_system"``.
        ai_system_id: ID (``aisys_...``) of your AI system; required for ``"per_ai_system"``.
        ai_involvement: ``"ai_generated"`` or ``"ai_modified"``; required for ``"per_ai_system"``.
        trufo_api_url: Trufo API base URL. Defaults to production.

    Returns:
        The record ID and the reservation to pass to :func:`watermark_media`.

    Raises:
        ValueError: On invalid allocation mode or AI involvement.
        NotImplementedError: For ``"per_asset"`` allocation.
        requests.HTTPError: If the API returns a non-2xx response.
    """
    body = {
        "mime_type": mime_type,
        **_allocation_fields(
            wid_allocation_mode=wid_allocation_mode,
            ai_system_id=ai_system_id,
            ai_involvement=ai_involvement,
        ),
    }
    payload = _post(api_key, trufo_api_url + TPS_BIND_RESERVE_PATH, body)
    package = payload["wid_package"]
    return BindReserveResult(
        cid=payload["cid"],
        wid=package["wid"],
        expires_at=package["expires_at"],
        wid_package=dict(package),
    )


def watermark_media(
    media_bytes: bytes,
    wid_package: dict,
    *,
    watermark_settings: WatermarkSettings | None = None,
) -> bytes:
    """lpls step 2: embed a reserved watermark ID with the local Trufo engine.

    Args:
        media_bytes: Raw bytes of the media file to watermark.
        wid_package: ``BindReserveResult.wid_package`` (or the ``wid_package``
            of a Trufo API response).
        watermark_settings: Optional local embedding profile.

    Returns:
        The watermarked media bytes, in the input's format.

    Raises:
        ImportError: If the engine (``trufo[local-full]``) is not installed.
        TypeError: If watermark_settings is not WatermarkSettings or None.
    """
    if watermark_settings is not None and not isinstance(watermark_settings, WatermarkSettings):
        raise TypeError("watermark_settings must be WatermarkSettings or None.")
    try:
        from tfprov.util import pawprint_import
    except ImportError as exc:
        raise ImportError(_ENGINE_HINT) from exc
    options = {}
    if watermark_settings is not None:
        options = {"mode": watermark_settings.profile.value}
    package = pawprint_import.WatermarkIdPackage(**wid_package)
    return pawprint_import.embed(media_bytes, package, **options)


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
    signed_media_bytes: bytes | None = None,
    trufo_api_url: str = TRUFO_API_URL,
) -> None:
    """Complete a bind record with your signed C2PA manifest.

    Give exactly one manifest source: ``manifest_bytes`` (the serialized C2PA
    manifest store) or ``signed_media_bytes`` (the signed media; the store is
    read out locally, which needs ``trufo[local-sign-only]``). The manifest
    should declare the mark issued with the record (see the module docstring);
    otherwise the API still commits it and emits a
    :class:`~trufo.util.warnings.TrufoServerWarning`.

    Args:
        api_key: API key with scope ``watermark-prod`` (``watermark-test`` on
            the test host).
        cid: Record ID from :func:`bind_watermark` or :func:`bind_reserve`.
        wid: Watermark ID issued with that record.
        manifest_bytes: Raw bytes of the C2PA manifest store.
        signed_media_bytes: Raw bytes of the C2PA-signed watermarked media.
        trufo_api_url: Trufo API base URL. Defaults to production.

    Raises:
        ValueError: If not exactly one manifest source is given.
        ImportError: If ``signed_media_bytes`` is given without the local
            C2PA library.
        requests.HTTPError: If the API returns a non-2xx response.
    """
    sources = [s for s in (manifest_bytes, signed_media_bytes) if s is not None]
    if len(sources) != 1:
        raise ValueError("Provide exactly one of manifest_bytes or signed_media_bytes.")
    if signed_media_bytes is not None:
        manifest_bytes = _manifest_store_from_media(signed_media_bytes)
    body = {"cid": cid, "wid": wid, "manifest": base64.b64encode(manifest_bytes).decode()}
    payload = _post(api_key, trufo_api_url + TPS_BIND_COMMIT_PATH, body)
    emit_server_warnings(payload)


def bind_watermark_test(
    api_key: str,
    media_bytes: bytes,
    *,
    wid_allocation_mode: WatermarkIDAllocationMode | str | None = None,
    ai_system_id: str | None = None,
    ai_involvement: AIInvolvement | str | None = None,
    mode: str | None = None,
    execution_mode: ExecutionMode = ExecutionMode.REQUEST,
    trufo_api_url: str = TRUFO_API_URL_TEST,
) -> BindWatermarkResult:
    """:func:`bind_watermark` against the Trufo test host (``watermark-test`` key)."""
    ExecutionMode.validate(execution_mode, test=True)
    return bind_watermark(
        api_key,
        media_bytes,
        wid_allocation_mode=wid_allocation_mode,
        ai_system_id=ai_system_id,
        ai_involvement=ai_involvement,
        mode=mode,
        trufo_api_url=trufo_api_url,
    )


def bind_reserve_test(
    api_key: str,
    mime_type: str,
    *,
    wid_allocation_mode: WatermarkIDAllocationMode | str | None = None,
    ai_system_id: str | None = None,
    ai_involvement: AIInvolvement | str | None = None,
    trufo_api_url: str = TRUFO_API_URL_TEST,
) -> BindReserveResult:
    """:func:`bind_reserve` against the Trufo test host (``watermark-test`` key)."""
    return bind_reserve(
        api_key,
        mime_type,
        wid_allocation_mode=wid_allocation_mode,
        ai_system_id=ai_system_id,
        ai_involvement=ai_involvement,
        trufo_api_url=trufo_api_url,
    )


def bind_commit_test(
    api_key: str,
    cid: str,
    wid: str,
    *,
    manifest_bytes: bytes | None = None,
    signed_media_bytes: bytes | None = None,
    trufo_api_url: str = TRUFO_API_URL_TEST,
) -> None:
    """:func:`bind_commit` against the Trufo test host (``watermark-test`` key)."""
    bind_commit(
        api_key,
        cid,
        wid,
        manifest_bytes=manifest_bytes,
        signed_media_bytes=signed_media_bytes,
        trufo_api_url=trufo_api_url,
    )


__getattr__ = deprecated_aliases(
    globals(), {"BindWatermark": "BindWatermarkResult", "BindReservation": "BindReserveResult"}
)
