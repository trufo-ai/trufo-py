# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for content record lookup, listing, and status."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from trufo.api.endpoints import TRUFO_API_URL
from trufo.api.headers import sdk_headers
from trufo.api.tps.records import get_content, list_content, set_content_status

_M = "trufo.api.tps.records"

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


def _response(payload, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


class TestGetContent:
    @patch(f"{_M}.requests.post")
    def test_looks_up_by_one_key(self, mock_post):
        mock_post.return_value = _response(_ITEM)
        record = get_content("key", wid="v1.001a1b2c3d4")
        assert (record.cid, record.mid, record.status) == ("0199-0001", "urn:c2pa:1", "active")
        call = mock_post.call_args
        assert call.args[0] == f"{TRUFO_API_URL}/content/get"
        assert call.kwargs["headers"] == sdk_headers("key")
        assert call.kwargs["json"] == {"wid": "v1.001a1b2c3d4"}

    def test_exactly_one_key(self):
        with pytest.raises(ValueError):
            get_content("key")
        with pytest.raises(ValueError):
            get_content("key", cid="c", mid="m")

    @patch(f"{_M}.requests.post")
    def test_missing_record_raises(self, mock_post):
        mock_post.return_value = _response({"detail": "No content record of yours matches."}, 404)
        with pytest.raises(requests.HTTPError):
            get_content("key", cid="nope")


class TestListContent:
    @patch(f"{_M}.requests.post")
    def test_sends_only_the_given_filters(self, mock_post):
        mock_post.return_value = _response({"items": [_ITEM], "next_cursor": "0199-0001"})
        page = list_content("key", status="active", created_after="2026-04-01T00:00:00Z",
                            cursor="0198-ffff", limit=1)
        assert page.next_cursor == "0199-0001" and page.items[0].wid == "v1.001a1b2c3d4"
        assert mock_post.call_args.args[0] == f"{TRUFO_API_URL}/content/list"
        assert mock_post.call_args.kwargs["json"] == {
            "limit": 1, "status": "active", "created_after": "2026-04-01T00:00:00Z", "cursor": "0198-ffff",
        }

    @patch(f"{_M}.requests.post")
    def test_first_page_sends_only_the_limit(self, mock_post):
        mock_post.return_value = _response({"items": [], "next_cursor": None})
        page = list_content("key")
        assert page.items == [] and page.next_cursor is None
        assert mock_post.call_args.kwargs["json"] == {"limit": 50}


class TestSetContentStatus:
    @patch(f"{_M}.requests.post")
    def test_posts_the_key_and_status(self, mock_post):
        mock_post.return_value = _response({**_ITEM, "status": "inactive"})
        record = set_content_status("key", "inactive", mid="urn:c2pa:1")
        assert record.status == "inactive" and record.cid == "0199-0001"
        assert mock_post.call_args.args[0] == f"{TRUFO_API_URL}/content/status"
        assert mock_post.call_args.kwargs["json"] == {"mid": "urn:c2pa:1", "status": "inactive"}

    def test_exactly_one_key(self):
        with pytest.raises(ValueError):
            set_content_status("key", "inactive")
