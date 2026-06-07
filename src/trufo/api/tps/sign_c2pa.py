# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
C2PA signing helpers for the Trufo TPS.
"""

import base64
import json
import logging
from dataclasses import dataclass

import requests

from trufo.api.endpoints import (
    TPS_C2PA_GET_S3_URL,
    TPS_C2PA_SIGN,
    TPS_C2PA_SIGN_TEST,
    TRUFO_API_URL,
)
from trufo.c2pa.actions import TrufoAction
from trufo.c2pa.assertions import UserAssertion
from trufo.util.credentials import TrufoApiKey, load_api_key
from trufo.util.optional_imports import require_provenance_module

logger = logging.getLogger(__name__)

_MISSING_CAWG_IDENTITY_WARNING = (
    "Gathered assertions are being input by the client without specifying one or "
    "more CAWG identities. Once the CAWG trust model is mature (currently, there "
    "are only interim certificates being issued), it may be come mandatory to "
    "specify one or more CAWG identities."
)
_ALLOWED_CAWG_IDENTITY_IDS = {"test", "org_interim"}


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

    # cawg identity checks
    if assertions and not any(a[0] == UserAssertion.CAWG_IDENTITY.value for a in assertions):
        logger.warning(_MISSING_CAWG_IDENTITY_WARNING)
    for name, params in (assertions or []):
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
                if cawg_identity_id not in _ALLOWED_CAWG_IDENTITY_IDS:
                    allowed = ", ".join(sorted(_ALLOWED_CAWG_IDENTITY_IDS))
                    raise ValueError(
                        f"Unsupported cawg_identity_id: {cawg_identity_id!r}. "
                        f"Supported values are: {allowed}."
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
) -> bytes:
    """Sign media bytes through a C2PA signing endpoint."""
    _validate_actions(actions)
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
    _validate_actions(actions)
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


def sign_c2pa_remote_test(
    api_key: str,
    media_bytes: bytes,
    *,
    actions: list | None = None,
    assertions: list | None = None,
    tsa_api_key: str | None = None,
) -> bytes:
    """Sign media locally using the Trufo test remote-signing endpoint.

    The media claim is built on the client while the C2PA claim-signing key
    stays server-side. This helper requires the optional ``trufo[provenance]``
    dependency group.
    """
    _validate_actions(actions)
    _validate_assertions(assertions)

    resolved_tsa_api_key = _resolve_tsa_api_key(tsa_api_key)
    c2pa_generator = require_provenance_module("tfprov.c2pa_generator")
    crypt = require_provenance_module("tfprov.crypt")
    ocsp_stapler = require_provenance_module("tfprov.c2pa_py.helpers.ocsp_stapler")
    timestamper = require_provenance_module("tfprov.c2pa_py.helpers.timestamper")
    av_format = require_provenance_module("tfprov.util.av_format")

    media_probe = av_format.get_media_probe_result(media_bytes)
    CGRequest = c2pa_generator.CGRequest
    cg_request = CGRequest.build(
        actions=actions,
        assertions=assertions,
        media_bytes=media_bytes,
        mime_type=media_probe.mime_type,
    )
    claim_signer = crypt.TrufoRemoteClaimSigner(api_key=api_key)
    cawg_identities = [
        c2pa_generator.CawgIdentity(
            signer=crypt.TrufoRemoteIdentitySigner(
                api_key=api_key,
                cawg_identity_id=params["cawg_identity_id"],
            )
        )
        for name, params in (assertions or [])
        if name == UserAssertion.CAWG_IDENTITY.value
    ]
    generated = json.loads(
        c2pa_generator.generate_claim(
            cg_request,
            claim_signer=claim_signer,
            ocsp_stapler=ocsp_stapler.OcspStapler(),
            timestamper=timestamper.TrufoTimestamper(api_key=resolved_tsa_api_key),
            cawg_identities=cawg_identities,
        )
    )
    return base64.b64decode(generated["media_output"])


def sign_c2pa_remote(
    api_key: str,
    media_bytes: bytes,
    *,
    actions: list | None = None,
    assertions: list | None = None,
    tsa_api_key: str | None = None,
) -> bytes:
    """Production remote C2PA signing placeholder."""
    del api_key, media_bytes, actions, assertions, tsa_api_key
    raise NotImplementedError("Production remote C2PA signing is not implemented server-side yet.")
