# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
C2PA signing helpers for the Trufo TPS.

Every manifest signed through Trufo endpoints carries an automatic
``ai.trufo.identity`` assertion injected server-side with the signing org's
id and, when the org has completed Organization Validation (OV), its
RA-validated legal name. Production signing requires completed OV (the API
returns 403 otherwise); test signing works without it. CAWG identity
assertions are optional; the ``cawg_identity_id`` value is validated
server-side.

Most signing helpers below accept optional ``manifest_title``/``ingredient_title``
arguments (the active manifest's ``dc:title`` and, for ingesting/transcoding
flows, the ``parentOf`` ingredient's ``dc:title``). When omitted, the engine
derives a default by sniffing the media content's MIME type. Always pass these
explicitly when the caller knows the real intended filename/identity of the
output or its parent -- in particular, do not rely on the sniffed default for
any format that shares an underlying container with a sibling format (e.g.
TIFF/DNG, HEIC/HEIF/AVIF), since content sniffing cannot distinguish them and
will silently pick the wrong title.
"""

import base64
from dataclasses import dataclass

import requests

from trufo.api.endpoints import (
    TPS_C2PA_GET_S3_URL,
    TPS_C2PA_SIGN,
    TPS_C2PA_SIGN_TEST,
    TRUFO_API_URL,
    TRUFO_TSA_URL,
)
from trufo.c2pa.actions import TrufoAction
from trufo.c2pa.assertions import UserAssertion
from trufo.util.credentials import TrufoApiKey, load_api_key
from trufo.util.optional_imports import require_provenance_module


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
    _validate_entry_names(assertions, UserAssertion, "assertion")

    # cawg identity checks; the identity id itself is validated server-side
    for name, params in assertions or []:
        match name:
            case UserAssertion.CAWG_IDENTITY.value:
                if not isinstance(params, dict):
                    raise ValueError("The cawg_identity assertion requires a parameter object.")
                cawg_identity_id = params.get("cawg_identity_id")
                if not isinstance(cawg_identity_id, str) or not cawg_identity_id:
                    raise ValueError(
                        "The cawg_identity assertion requires a non-empty "
                        "'cawg_identity_id' parameter."
                    )
            case _:
                pass


def _validate_actions(actions: list | None) -> None:
    """Validate client-side action requirements shared by C2PA helpers."""
    _validate_entry_names(actions, TrufoAction, "action")


def _validate_entry_names(entries: list | None, enum_type: type, entry_type: str) -> None:
    """Validate the name field of request entries against a public enum."""
    for entry in entries or []:
        try:
            enum_type(entry[0])
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid {entry_type} entry: {entry!r}") from exc


def _sign_c2pa_direct(
    endpoint: str,
    api_key: str,
    media_bytes: bytes,
    actions: list | None = None,
    assertions: list | None = None,
    manifest_title: str | None = None,
    ingredient_title: str | None = None,
    *,
    trufo_api_url: str = TRUFO_API_URL,
) -> bytes:
    """Sign media bytes through a C2PA signing endpoint."""
    _validate_actions(actions)
    _validate_assertions(assertions)

    body = {
        "media_input": base64.b64encode(media_bytes).decode(),
        "actions": actions or [],
        "assertions": assertions or [],
    }
    if manifest_title is not None:
        body["manifest_title"] = manifest_title
    if ingredient_title is not None:
        body["ingredient_title"] = ingredient_title

    resp = requests.post(
        trufo_api_url + endpoint,
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
    *,
    trufo_api_url: str = TRUFO_API_URL,
) -> C2PAS3Upload:
    """Request an ephemeral S3 upload URL for C2PA signing.

    The returned ``media_input_s3`` reference can be passed to
    :func:`sign_c2pa_s3` or :func:`sign_c2pa_s3_test` after uploading media
    bytes to ``upload_url``.

    Args:
        api_key: API key with scope ``c2pa-sign-prod`` or ``c2pa-sign-test``.
        mime_type: MIME type of the object to upload.
        duration: Optional server-supported duration value. Currently ``"5m"``.
        trufo_api_url: Freeform Trufo API base URL. Defaults to production.

    Returns:
        Ephemeral upload URL, signed media reference, expiry, and duration.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    body = {"mime_type": mime_type}
    if duration is not None:
        body["duration"] = duration

    resp = requests.post(
        trufo_api_url + TPS_C2PA_GET_S3_URL,
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
    manifest_title: str | None = None,
    ingredient_title: str | None = None,
    *,
    trufo_api_url: str = TRUFO_API_URL,
) -> C2PAS3SignedOutput:
    """Sign an uploaded ephemeral S3 object through a C2PA signing endpoint."""
    _validate_actions(actions)
    _validate_assertions(assertions)

    body = {
        "media_input_s3": media_input_s3,
        "actions": actions or [],
        "assertions": assertions or [],
    }
    if manifest_title is not None:
        body["manifest_title"] = manifest_title
    if ingredient_title is not None:
        body["ingredient_title"] = ingredient_title

    resp = requests.post(
        trufo_api_url + endpoint,
        json=body,
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
    manifest_title: str | None = None,
    ingredient_title: str | None = None,
    *,
    trufo_api_url: str = TRUFO_API_URL,
) -> C2PAS3SignedOutput:
    """Sign an uploaded ephemeral S3 object with production C2PA via the TPS.

    Requires completed Organization Validation for the caller's org; the API
    returns 403 otherwise.

    Args:
        api_key: API key with scope ``c2pa-sign-prod``.
        media_input_s3: Opaque reference returned by :func:`get_c2pa_s3_upload_url`.
        actions: Ordered list of ``[action_name, params]`` pairs (default ``[]``).
        assertions: List of ``[assertion_name, params]`` pairs (default ``[]``).
        manifest_title: Optional active-manifest title (``dc:title``); see the
            module docstring for when to set this explicitly.
        ingredient_title: Optional ``parentOf`` ingredient title (``dc:title``);
            see the module docstring for when to set this explicitly.
        trufo_api_url: Freeform Trufo API base URL. Defaults to production.

    Returns:
        Presigned S3 download URL for the signed output media.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    return _sign_c2pa_s3(
        TPS_C2PA_SIGN,
        api_key,
        media_input_s3,
        actions=actions,
        assertions=assertions,
        manifest_title=manifest_title,
        ingredient_title=ingredient_title,
        trufo_api_url=trufo_api_url,
    )


def sign_c2pa_s3_test(
    api_key: str,
    media_input_s3: str,
    actions: list | None = None,
    assertions: list | None = None,
    manifest_title: str | None = None,
    ingredient_title: str | None = None,
    *,
    trufo_api_url: str = TRUFO_API_URL,
) -> C2PAS3SignedOutput:
    """Sign an uploaded ephemeral S3 object with test C2PA via the TPS.

    Args:
        api_key: API key with scope ``c2pa-sign-test``.
        media_input_s3: Opaque reference returned by :func:`get_c2pa_s3_upload_url`.
        actions: Ordered list of ``[action_name, params]`` pairs (default ``[]``).
        assertions: List of ``[assertion_name, params]`` pairs (default ``[]``).
        manifest_title: Optional active-manifest title (``dc:title``); see the
            module docstring for when to set this explicitly.
        ingredient_title: Optional ``parentOf`` ingredient title (``dc:title``);
            see the module docstring for when to set this explicitly.
        trufo_api_url: Freeform Trufo API base URL. Defaults to production.

    Returns:
        Presigned S3 download URL for the signed output media.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    return _sign_c2pa_s3(
        TPS_C2PA_SIGN_TEST,
        api_key,
        media_input_s3,
        actions=actions,
        assertions=assertions,
        manifest_title=manifest_title,
        ingredient_title=ingredient_title,
        trufo_api_url=trufo_api_url,
    )


def sign_c2pa_via_s3(
    api_key: str,
    media_bytes: bytes,
    mime_type: str,
    actions: list | None = None,
    assertions: list | None = None,
    duration: str | None = None,
    manifest_title: str | None = None,
    ingredient_title: str | None = None,
    *,
    trufo_api_url: str = TRUFO_API_URL,
) -> bytes:
    """Upload, production-sign, and download media through the ephemeral S3 flow.

    Requires completed Organization Validation for the caller's org; the API
    returns 403 otherwise.

    This convenience helper composes the low-level helpers:
    :func:`get_c2pa_s3_upload_url` and :func:`sign_c2pa_s3`.

    Args:
        api_key: API key with scope ``c2pa-sign-prod``.
        media_bytes: Raw bytes of the media file to sign.
        mime_type: MIME type of the media file.
        actions: Ordered list of ``[action_name, params]`` pairs (default ``[]``).
        assertions: List of ``[assertion_name, params]`` pairs (default ``[]``).
        duration: Optional server-supported S3 URL duration. Currently ``"5m"``.
        manifest_title: Optional active-manifest title (``dc:title``); see the
            module docstring for when to set this explicitly.
        ingredient_title: Optional ``parentOf`` ingredient title (``dc:title``);
            see the module docstring for when to set this explicitly.
        trufo_api_url: Freeform Trufo API base URL. Defaults to production.

    Returns:
        Signed media bytes downloaded from the returned S3 output URL.

    Raises:
        requests.HTTPError: If an API, upload, or download request fails.
    """
    upload = get_c2pa_s3_upload_url(
        api_key,
        mime_type,
        duration=duration,
        trufo_api_url=trufo_api_url,
    )
    _upload_c2pa_s3_media(upload.upload_url, media_bytes, mime_type)
    signed_output = sign_c2pa_s3(
        api_key,
        upload.media_input_s3,
        actions=actions,
        assertions=assertions,
        manifest_title=manifest_title,
        ingredient_title=ingredient_title,
        trufo_api_url=trufo_api_url,
    )
    return _download_c2pa_s3_media(signed_output.media_output_s3)


def sign_c2pa_via_s3_test(
    api_key: str,
    media_bytes: bytes,
    mime_type: str,
    actions: list | None = None,
    assertions: list | None = None,
    duration: str | None = None,
    manifest_title: str | None = None,
    ingredient_title: str | None = None,
    *,
    trufo_api_url: str = TRUFO_API_URL,
) -> bytes:
    """Upload, test-sign, and download media through the ephemeral S3 flow.

    This convenience helper composes the low-level helpers:
    :func:`get_c2pa_s3_upload_url` and :func:`sign_c2pa_s3_test`.

    Args:
        api_key: API key with scope ``c2pa-sign-test``.
        media_bytes: Raw bytes of the media file to sign.
        mime_type: MIME type of the media file.
        actions: Ordered list of ``[action_name, params]`` pairs (default ``[]``).
        assertions: List of ``[assertion_name, params]`` pairs (default ``[]``).
        duration: Optional server-supported S3 URL duration. Currently ``"5m"``.
        manifest_title: Optional active-manifest title (``dc:title``); see the
            module docstring for when to set this explicitly.
        ingredient_title: Optional ``parentOf`` ingredient title (``dc:title``);
            see the module docstring for when to set this explicitly.
        trufo_api_url: Freeform Trufo API base URL. Defaults to production.

    Returns:
        Signed media bytes downloaded from the returned S3 output URL.

    Raises:
        requests.HTTPError: If an API, upload, or download request fails.
    """
    upload = get_c2pa_s3_upload_url(
        api_key,
        mime_type,
        duration=duration,
        trufo_api_url=trufo_api_url,
    )
    _upload_c2pa_s3_media(upload.upload_url, media_bytes, mime_type)
    signed_output = sign_c2pa_s3_test(
        api_key,
        upload.media_input_s3,
        actions=actions,
        assertions=assertions,
        manifest_title=manifest_title,
        ingredient_title=ingredient_title,
        trufo_api_url=trufo_api_url,
    )
    return _download_c2pa_s3_media(signed_output.media_output_s3)


def _upload_c2pa_s3_media(upload_url: str, media_bytes: bytes, mime_type: str) -> None:
    """Upload media bytes to an ephemeral presigned S3 URL."""
    resp = requests.put(
        upload_url,
        data=media_bytes,
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
    manifest_title: str | None = None,
    ingredient_title: str | None = None,
    *,
    trufo_api_url: str = TRUFO_API_URL,
) -> bytes:
    """Sign a media file with production C2PA via the TPS.

    Requires completed Organization Validation for the caller's org; the API
    returns 403 otherwise.

    Args:
        api_key: API key with scope ``c2pa-sign-prod`` (``X-API-Key`` header).
        media_bytes: Raw bytes of the media file to sign.
        actions: Ordered list of ``[action_name, params]`` pairs (default ``[]``).
        assertions: List of ``[assertion_name, params]`` pairs (default ``[]``).
        manifest_title: Optional active-manifest title (``dc:title``); see the
            module docstring for when to set this explicitly.
        ingredient_title: Optional ``parentOf`` ingredient title (``dc:title``);
            see the module docstring for when to set this explicitly.
        trufo_api_url: Freeform Trufo API base URL. Defaults to production.

    Returns:
        Signed media bytes.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    return _sign_c2pa_direct(
        TPS_C2PA_SIGN,
        api_key,
        media_bytes,
        actions=actions,
        assertions=assertions,
        manifest_title=manifest_title,
        ingredient_title=ingredient_title,
        trufo_api_url=trufo_api_url,
    )


def sign_c2pa_test(
    api_key: str,
    media_bytes: bytes,
    actions: list | None = None,
    assertions: list | None = None,
    manifest_title: str | None = None,
    ingredient_title: str | None = None,
    *,
    trufo_api_url: str = TRUFO_API_URL,
) -> bytes:
    """Sign a media file with C2PA via the TPS test endpoint.

    Args:
        api_key: API key with scope ``c2pa-sign-test`` (``X-API-Key`` header).
        media_bytes: Raw bytes of the media file to sign.
        actions: Ordered list of ``[action_name, params]`` pairs (default ``[]``).
        assertions: List of ``[assertion_name, params]`` pairs (default ``[]``).
        manifest_title: Optional active-manifest title (``dc:title``); see the
            module docstring for when to set this explicitly.
        ingredient_title: Optional ``parentOf`` ingredient title (``dc:title``);
            see the module docstring for when to set this explicitly.
        trufo_api_url: Freeform Trufo API base URL. Defaults to production.

    Returns:
        Signed media bytes.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    return _sign_c2pa_direct(
        TPS_C2PA_SIGN_TEST,
        api_key,
        media_bytes,
        actions=actions,
        assertions=assertions,
        manifest_title=manifest_title,
        ingredient_title=ingredient_title,
        trufo_api_url=trufo_api_url,
    )


def _resolve_tsa_api_key(tsa_api_key: str | None) -> str:
    """Return explicit TSA API key or load the configured SDK TSA key."""
    if tsa_api_key is not None:
        resolved_key = tsa_api_key.strip()
        if not resolved_key:
            raise ValueError("tsa_api_key cannot be empty.")
        return resolved_key

    configured_key = load_api_key(TrufoApiKey.TSA)
    if configured_key is None:
        raise RuntimeError(
            "A TSA API key is required for remote C2PA signing. Pass tsa_api_key "
            "or configure TRUFO_TSA_API_KEY."
        )
    return configured_key


def sign_c2pa_distributed_test(
    api_key: str,
    media_bytes: bytes,
    *,
    actions: list | None = None,
    assertions: list | None = None,
    tsa_api_key: str | None = None,
    trufo_tsa_url: str = TRUFO_TSA_URL,
    trufo_api_url: str = TRUFO_API_URL,
    manifest_title: str | None = None,
    ingredient_title: str | None = None,
) -> bytes:
    """Sign media locally using the Trufo test remote-signing endpoint.

    The media claim is built on the client while the C2PA claim-signing key
    stays server-side. This helper requires the optional ``trufo[provenance]``
    dependency group.

    Args:
        api_key: API key with scope ``c2pa-sign-test``.
        media_bytes: Raw bytes of the media file to sign.
        actions: Ordered list of ``[action_name, params]`` pairs (default ``[]``).
        assertions: List of ``[assertion_name, params]`` pairs (default ``[]``).
        tsa_api_key: TSA API key. Falls back to the ``TRUFO_TSA_API_KEY``
            environment variable or the SDK configured key.
        trufo_tsa_url: Trufo TSA URL. Defaults to ``TRUFO_TSA_URL``.
        trufo_api_url: Base URL for the Trufo API. Controls the preprocess,
            claim-sign, and CAWG identity-sign endpoints.
        manifest_title: Optional active-manifest title (``dc:title``); see the
            module docstring for when to set this explicitly.
        ingredient_title: Optional ``parentOf`` ingredient title (``dc:title``);
            see the module docstring for when to set this explicitly.

    Returns:
        Signed media bytes.
    """
    _validate_actions(actions)
    _validate_assertions(assertions)

    resolved_tsa_api_key = _resolve_tsa_api_key(tsa_api_key)
    remote_orchestrator = require_provenance_module("tfprov.c2pa_generator.remote_orchestrator")
    ocsp_stapler_mod = require_provenance_module("tfprov.c2pa_py.helpers.ocsp_stapler")
    timestamper_mod = require_provenance_module("tfprov.c2pa_py.helpers.timestamper")

    signed, _ = remote_orchestrator.generate_claim_remote(
        api_key,
        media_bytes,
        actions=actions or [],
        assertions=assertions or [],
        timestamper=timestamper_mod.TrufoTimestamper(
            api_key=resolved_tsa_api_key,
            url=trufo_tsa_url,
        ),
        ocsp_stapler=ocsp_stapler_mod.OcspStapler(),
        trufo_api_url=trufo_api_url,
        test=True,
        manifest_title=manifest_title,
        ingredient_title=ingredient_title,
    )
    return signed


def sign_c2pa_distributed(
    api_key: str,
    media_bytes: bytes,
    *,
    actions: list | None = None,
    assertions: list | None = None,
    tsa_api_key: str | None = None,
    trufo_tsa_url: str = TRUFO_TSA_URL,
    trufo_api_url: str = TRUFO_API_URL,
    manifest_title: str | None = None,
    ingredient_title: str | None = None,
) -> bytes:
    """Sign media locally using the Trufo production remote-signing endpoint.

    The media claim is built on the client while the C2PA claim-signing key
    stays server-side. This helper requires the optional ``trufo[provenance]``
    dependency group. Requires completed Organization Validation for the
    caller's org; the API returns 403 otherwise.

    Args:
        api_key: API key with scope ``c2pa-sign-prod``.
        media_bytes: Raw bytes of the media file to sign.
        actions: Ordered list of ``[action_name, params]`` pairs (default ``[]``).
        assertions: List of ``[assertion_name, params]`` pairs (default ``[]``).
        tsa_api_key: TSA API key. Falls back to the ``TRUFO_TSA_API_KEY``
            environment variable or the SDK configured key.
        trufo_tsa_url: Trufo TSA URL. Defaults to ``TRUFO_TSA_URL``.
        trufo_api_url: Base URL for the Trufo API. Controls the preprocess,
            claim-sign, and CAWG identity-sign endpoints.
        manifest_title: Optional active-manifest title (``dc:title``); see the
            module docstring for when to set this explicitly.
        ingredient_title: Optional ``parentOf`` ingredient title (``dc:title``);
            see the module docstring for when to set this explicitly.

    Returns:
        Signed media bytes.
    """
    _validate_actions(actions)
    _validate_assertions(assertions)

    resolved_tsa_api_key = _resolve_tsa_api_key(tsa_api_key)
    remote_orchestrator = require_provenance_module("tfprov.c2pa_generator.remote_orchestrator")
    ocsp_stapler_mod = require_provenance_module("tfprov.c2pa_py.helpers.ocsp_stapler")
    timestamper_mod = require_provenance_module("tfprov.c2pa_py.helpers.timestamper")

    signed, _ = remote_orchestrator.generate_claim_remote(
        api_key,
        media_bytes,
        actions=actions or [],
        assertions=assertions or [],
        timestamper=timestamper_mod.TrufoTimestamper(
            api_key=resolved_tsa_api_key,
            url=trufo_tsa_url,
        ),
        ocsp_stapler=ocsp_stapler_mod.OcspStapler(),
        trufo_api_url=trufo_api_url,
        test=False,
        manifest_title=manifest_title,
        ingredient_title=ingredient_title,
    )
    return signed
