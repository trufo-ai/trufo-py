# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Content record management for the Trufo TPS: listing and lifecycle status."""

from dataclasses import dataclass

import requests

from trufo.api.endpoints import TPS_CONTENT_LIST, TPS_CONTENT_STATUS, TRUFO_API_URL
from trufo.api.headers import sdk_headers


@dataclass(frozen=True)
class ContentRecord:
    """One content record, created by a production sign or bind.

    ``wid`` is the watermark ID once a mark is embedded (and, on the bind
    routes, committed) and ``mid`` the manifest ID once a manifest is captured;
    a record with both is what
    public soft-binding resolution serves and what soft-binding resolution
    maintenance charges for. ``status`` is ``"active"`` or ``"inactive"``.
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
class ContentStatusUpdate:
    """Result of a status change: the record's id, watermark ID, and new status."""

    cid: str
    status: str
    wid: str | None = None


@dataclass(frozen=True)
class ContentPage:
    """One page of content records; ``next_cursor`` is None on the last page."""

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


def list_content(
    api_key: str,
    *,
    cursor: str | None = None,
    limit: int = 50,
    status: str | None = None,
    trufo_api_url: str = TRUFO_API_URL,
) -> ContentPage:
    """List your organization's content records, oldest first, one page at a time.

    Args:
        api_key: API key with scope ``c2pa-sign-prod`` or ``watermark-prod``.
        cursor: The ``next_cursor`` of the previous page; omit for the first page.
        limit: Page size, 1 to 100.
        status: ``"active"`` or ``"inactive"`` to list one lifecycle status only.
        trufo_api_url: Freeform Trufo API base URL. Defaults to production.

    Returns:
        The page and the cursor for the next one.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    body: dict = {"limit": limit}
    if cursor is not None:
        body["cursor"] = cursor
    if status is not None:
        body["status"] = status
    resp = requests.post(
        trufo_api_url + TPS_CONTENT_LIST, json=body, headers=sdk_headers(api_key), timeout=60
    )
    resp.raise_for_status()
    payload = resp.json()
    return ContentPage(
        items=[_record(item) for item in payload["items"]],
        next_cursor=payload.get("next_cursor"),
    )


def set_content_status(
    api_key: str,
    cid: str,
    status: str,
    *,
    trufo_api_url: str = TRUFO_API_URL,
) -> ContentStatusUpdate:
    """Set a content record's lifecycle status.

    ``"inactive"`` withdraws the record from public soft-binding resolution and
    stops its soft-binding resolution maintenance from the next day;
    ``"active"`` restores it.

    Args:
        api_key: API key with scope ``c2pa-sign-prod`` or ``watermark-prod``.
        cid: The record's content id, as returned by the sign or bind call.
        status: ``"active"`` or ``"inactive"``.
        trufo_api_url: Freeform Trufo API base URL. Defaults to production.

    Returns:
        The record's id, watermark ID, and new status.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response (404 when the
            record is not your organization's).
    """
    resp = requests.post(
        trufo_api_url + TPS_CONTENT_STATUS,
        json={"cid": cid, "status": status},
        headers=sdk_headers(api_key),
        timeout=60,
    )
    resp.raise_for_status()
    payload = resp.json()
    return ContentStatusUpdate(cid=payload["cid"], status=payload["status"], wid=payload.get("wid"))
