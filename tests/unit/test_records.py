# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Content records (lookup, listing and status) and watermark recovery."""

import base64

import pytest

from trufo import (
    RecoverContentResult,
    get_content,
    list_content,
    recover_content,
    set_content_status,
)
from trufo.api.endpoints import TRUFO_API_URL

KEY = "api-key"
ITEM = {
    "cid": "0199-0001",
    "wid": "v1.001a1b2c3d4",
    "mid": "urn:c2pa:1",
    "status": "active",
    "origin": "bind_hosted",
    "mime_type": "image/jpeg",
    "create_ts": "2026-09-08T00:00:00+00:00",
    "commit_ts": None,
}


def test_get_content(trufo_api, assert_frozen_fields):
    trufo_api.answer(
        "POST",
        f"{TRUFO_API_URL}/content/get",
        {**ITEM, "wid": None, "ai_system_wid": "v1.00001a2b3c4"},
    )
    record = get_content(KEY, cid="0199-0001")
    assert (record.cid, record.wid, record.mid, record.status, record.origin) == (
        "0199-0001",
        None,
        "urn:c2pa:1",
        "active",
        "bind_hosted",
    )
    assert (record.mime_type, record.create_ts, record.commit_ts, record.ai_system_wid) == (
        "image/jpeg",
        "2026-09-08T00:00:00+00:00",
        None,
        "v1.00001a2b3c4",
    )
    fields = "cid status origin mime_type create_ts wid mid commit_ts ai_system_wid"
    assert assert_frozen_fields(record) == fields.split()
    assert [r.json for r in trufo_api.requests] == [{"cid": "0199-0001"}]
    # exactly one key, checked before sending
    for keys in ({}, {"cid": "c", "mid": "m"}):
        with pytest.raises(ValueError, match="Pass exactly one of cid, wid, mid."):
            get_content(KEY, **keys)


@pytest.mark.parametrize(
    "filters, body",
    [
        (
            {
                "status": "active",
                "created_after": "2026-04-01T00:00:00Z",
                "cursor": "0198-ffff",
                "limit": 1,
            },
            {
                "limit": 1,
                "status": "active",
                "created_after": "2026-04-01T00:00:00Z",
                "cursor": "0198-ffff",
            },
        ),
        ({}, {"limit": 50}),
    ],
)
def test_list_content(trufo_api, assert_frozen_fields, filters, body):
    trufo_api.answer(
        "POST",
        f"{TRUFO_API_URL}/content/list",
        {"items": [ITEM], "next_cursor": "0199-0001"},
        {"items": [], "next_cursor": None},
    )
    page = list_content(KEY, **filters)
    assert (page.next_cursor, [item.wid for item in page.items]) == ("0199-0001", [ITEM["wid"]])
    assert assert_frozen_fields(page) == ["items", "next_cursor"]
    last = list_content(KEY, **filters)
    assert (last.items, last.next_cursor) == ([], None)
    assert [r.json for r in trufo_api.requests] == [body, body]


def test_set_content_status(trufo_api):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/content/status", {**ITEM, "status": "inactive"})
    record = set_content_status(KEY, "inactive", mid="urn:c2pa:1")
    assert (record.cid, record.status) == ("0199-0001", "inactive")
    assert [r.json for r in trufo_api.requests] == [{"mid": "urn:c2pa:1", "status": "inactive"}]
    with pytest.raises(ValueError, match="Pass exactly one of cid, wid, mid."):
        set_content_status(KEY, "inactive")


@pytest.mark.parametrize(
    "parse, answer, expected",
    [
        (
            False,
            {
                "detected": True,
                "wid": "image.001a1b2c3d4",
                "confidence": 0.98,
                "manifest_bytes": None,
            },
            RecoverContentResult(True, "image.001a1b2c3d4", 0.98),
        ),
        (
            True,
            {
                "detected": True,
                "wid": "v1.001a1b2c3d4",
                "confidence": 0.9,
                "manifest_bytes": base64.b64encode(b"\x00jumb").decode(),
                "manifest_json": {"manifests": [1]},
                "oid": "org_1",
                "status": "inactive",
            },
            RecoverContentResult(
                True,
                "v1.001a1b2c3d4",
                0.9,
                manifest_bytes=b"\x00jumb",
                manifest_json={"manifests": [1]},
                oid="org_1",
                status="inactive",
            ),
        ),
        (False, {"detected": False}, RecoverContentResult(False)),
        (
            False,
            {
                "detected": True,
                "wid_allocation_mode": "per_ai_system",
                "ai_involvement": "ai_generated",
                "ai_system": {"name": "Example Model"},
            },
            RecoverContentResult(
                True,
                wid_allocation_mode="per_ai_system",
                ai_involvement="ai_generated",
                ai_system={"name": "Example Model"},
            ),
        ),
    ],
)
def test_recover_content(trufo_api, assert_frozen_fields, parse, answer, expected):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/content/recover", answer)
    recovered = recover_content(KEY, b"media", parse_manifest_json=parse)
    assert recovered == expected
    fields = "detected wid confidence manifest_bytes manifest_json oid wid_allocation_mode"
    assert assert_frozen_fields(recovered) == f"{fields} ai_involvement ai_system status".split()
    assert [r.json for r in trufo_api.requests] == [
        {"media_input": base64.b64encode(b"media").decode(), "parse_manifest_json": parse}
    ]


def test_unknown_fields_are_ignored(trufo_api):
    added = {**ITEM, "added_later": 1}
    page = {"items": [added], "next_cursor": None, "added_later": 1}
    trufo_api.answer("POST", f"{TRUFO_API_URL}/content/get", added)
    trufo_api.answer("POST", f"{TRUFO_API_URL}/content/list", page)
    trufo_api.answer("POST", f"{TRUFO_API_URL}/content/recover", {"detected": False, "added": 1})
    assert get_content(KEY, cid="0199-0001").wid == list_content(KEY).items[0].wid == ITEM["wid"]
    assert recover_content(KEY, b"media") == RecoverContentResult(False)
