# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for content record listing and status."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from trufo.api.endpoints import TRUFO_API_URL
from trufo.api.headers import sdk_headers
from trufo.api.tps.records import list_content, set_content_status

_M = "trufo.api.tps.records"


def _response(payload, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


_ITEM = {
    "cid": "0199-0001",
    "wid": "v1.001a1b2c3d4",
    "mid": "urn:c2pa:1",
    "status": "active",
    "origin": "bind_hosted",
    "mime_type": "image/jpeg",
    "create_ts": "2026-09-08T00:00:00+00:00",
    "commit_ts": None,
}


class TestListContent:
    @patch(f"{_M}.requests.post")
    def test_pages_with_the_cursor(self, mock_post):
        mock_post.return_value = _response({"items": [_ITEM], "next_cursor": "0199-0001"})

        page = list_content("key", cursor="0198-ffff", limit=1, status="active")

        assert page.next_cursor == "0199-0001"
        record = page.items[0]
        assert (record.cid, record.wid, record.mid, record.status) == (
            "0199-0001", "v1.001a1b2c3d4", "urn:c2pa:1", "active"
        )
        call = mock_post.call_args
        assert call.args[0] == f"{TRUFO_API_URL}/content/list"
        assert call.kwargs["headers"] == sdk_headers("key")
        assert call.kwargs["json"] == {"limit": 1, "cursor": "0198-ffff", "status": "active"}

    @patch(f"{_M}.requests.post")
    def test_first_page_sends_only_the_limit(self, mock_post):
        mock_post.return_value = _response({"items": [], "next_cursor": None})
        page = list_content("key")
        assert page.items == [] and page.next_cursor is None
        assert mock_post.call_args.kwargs["json"] == {"limit": 50}


class TestSetContentStatus:
    @patch(f"{_M}.requests.post")
    def test_posts_the_status_and_parses_the_result(self, mock_post):
        mock_post.return_value = _response(
            {"cid": "0199-0001", "wid": "v1.001a1b2c3d4", "status": "inactive"}
        )
        result = set_content_status("key", "0199-0001", "inactive")
        assert (result.cid, result.wid, result.status) == ("0199-0001", "v1.001a1b2c3d4", "inactive")
        call = mock_post.call_args
        assert call.args[0] == f"{TRUFO_API_URL}/content/status"
        assert call.kwargs["json"] == {"cid": "0199-0001", "status": "inactive"}

    @patch(f"{_M}.requests.post")
    def test_foreign_record_raises(self, mock_post):
        mock_post.return_value = _response({"detail": "No content record for this cid."}, 404)
        with pytest.raises(requests.HTTPError):
            set_content_status("key", "0199-9999", "inactive")
