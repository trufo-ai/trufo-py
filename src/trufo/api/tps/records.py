# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Content record management for the Trufo TPS: lookup, listing, and lifecycle status."""

from dataclasses import dataclass

import requests

from trufo.api.endpoints import (
    TPS_CONTENT_GET,
    TPS_CONTENT_LIST,
    TPS_CONTENT_STATUS,
    TRUFO_API_URL,
)
from trufo.api.headers import sdk_headers


@dataclass(frozen=True)
class ContentRecord:
    """One content record, created by a production sign or bind.

    ``wid`` is the watermark ID once a mark is embedded (and, on the bind
    routes, committed) and ``mid`` the manifest ID once a manifest is captured;
    a record with both is what public soft-binding resolution serves and what
    soft-binding resolution maintenance charges for. ``status`` is ``"active"``
    or ``"inactive"``. Unknown future fields are ignored.
    """

    cid: str
    status: str
    origin: str
    mime_type: str
    create_ts: str
    wid: str | None = None
    mid: str | None = None
    commit_ts: str | None = None


@dataclass(frozen=True)
class ContentPage:
    """One page of content records, oldest first; ``next_cursor`` is None on the last page."""

    items: list[ContentRecord]
    next_cursor: str | None


def _record(payload: dict) -> ContentRecord:
    return ContentRecord(
        cid=payload["cid"],
        status=payload["status"],
        origin=payload["origin"],
        mime_type=payload["mime_type"],
        create_ts=payload["create_ts"],
        wid=payload.get("wid"),
        mid=payload.get("mid"),
        commit_ts=payload.get("commit_ts"),
    )


def _key(cid: str | None, wid: str | None, mid: str | None) -> dict:
    keys = {k: v for k, v in (("cid", cid), ("wid", wid), ("mid", mid)) if v is not None}
    if len(keys) != 1:
        raise ValueError("Pass exactly one of cid, wid, mid.")
    return keys


def _post(api_key: str, url: str, body: dict) -> dict:
    resp = requests.post(url, json=body, headers=sdk_headers(api_key), timeout=60)
    resp.raise_for_status()
    return resp.json()


def get_content(
    api_key: str,
    *,
    cid: str | None = None,
    wid: str | None = None,
    mid: str | None = None,
    trufo_api_url: str = TRUFO_API_URL,
) -> ContentRecord:
    """Look up one of your organization's content records.

    Args:
        api_key: API key with scope ``c2pa-sign-prod`` or ``watermark-prod``.
        cid: The record's content id, as returned by the sign or bind call.
        wid: Its watermark ID, in any spelling; what a decode returns.
        mid: Its manifest ID (the soft-binding ``manifestId``).
        trufo_api_url: Freeform Trufo API base URL. Defaults to production.

    Exactly one of ``cid``, ``wid``, ``mid`` is required.

    Returns:
        The record.

    Raises:
        ValueError: If not exactly one key is given.
        requests.HTTPError: If the API returns a non-2xx response (404 when no
            record of yours matches).
    """
    return _record(_post(api_key, trufo_api_url + TPS_CONTENT_GET, _key(cid, wid, mid)))


def list_content(
    api_key: str,
    *,
    status: str | None = None,
    origin: str | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    trufo_api_url: str = TRUFO_API_URL,
) -> ContentPage:
    """List your organization's content records, oldest first, one page at a time.

    Args:
        api_key: API key with scope ``c2pa-sign-prod`` or ``watermark-prod``.
        status: ``"active"`` or ``"inactive"`` to list one lifecycle status only.
        origin: One route only: ``"c2pa_hosted"``, ``"c2pa_distributed"``,
            ``"bind_hosted"``, or ``"bind_distributed"``.
        created_after: RFC 3339 time; records created at or after it.
        created_before: RFC 3339 time; records created before it.
        cursor: The ``next_cursor`` of the previous page; omit for the first page.
        limit: Page size, 1 to 100.
        trufo_api_url: Freeform Trufo API base URL. Defaults to production.

    Returns:
        The page and the cursor for the next one.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    body: dict = {"limit": limit}
    for name, value in (
        ("status", status), ("origin", origin), ("created_after", created_after),
        ("created_before", created_before), ("cursor", cursor),
    ):
        if value is not None:
            body[name] = value
    payload = _post(api_key, trufo_api_url + TPS_CONTENT_LIST, body)
    return ContentPage(
        items=[_record(item) for item in payload["items"]],
        next_cursor=payload.get("next_cursor"),
    )


def set_content_status(
    api_key: str,
    status: str,
    *,
    cid: str | None = None,
    wid: str | None = None,
    mid: str | None = None,
    trufo_api_url: str = TRUFO_API_URL,
) -> ContentRecord:
    """Set one content record's lifecycle status.

    ``"inactive"`` withdraws the record from public soft-binding resolution and
    stops its soft-binding resolution maintenance from the next UTC day;
    ``"active"`` restores it. Idempotent.

    Args:
        api_key: API key with scope ``c2pa-sign-prod`` or ``watermark-prod``.
        status: ``"active"`` or ``"inactive"``.
        cid: The record's content id.
        wid: Its watermark ID, in any spelling.
        mid: Its manifest ID.
        trufo_api_url: Freeform Trufo API base URL. Defaults to production.

    Exactly one of ``cid``, ``wid``, ``mid`` is required.

    Returns:
        The record after the change.

    Raises:
        ValueError: If not exactly one key is given.
        requests.HTTPError: If the API returns a non-2xx response (404 when no
            record of yours matches).
    """
    body = {**_key(cid, wid, mid), "status": status}
    return _record(_post(api_key, trufo_api_url + TPS_CONTENT_STATUS, body))
