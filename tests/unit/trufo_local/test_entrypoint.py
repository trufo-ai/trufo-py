# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the trufo-local start checks."""

from pathlib import Path

import pytest
from entrypoint import is_trufo_api_url, parse_folder_list, parse_mount_points


def test_folder_list_is_resolved(tmp_path, monkeypatch):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    monkeypatch.setenv("TRUFO_LOCAL_INPUT_DIRS", f"{tmp_path}/a:{tmp_path}/a/../b")
    assert parse_folder_list("TRUFO_LOCAL_INPUT_DIRS", "read") == [tmp_path / "a", tmp_path / "b"]


@pytest.mark.parametrize(
    "value, error",
    [
        pytest.param(None, "is not set", id="unset"),
        pytest.param("", "is not set", id="empty"),
        pytest.param("relative/folder", "is not an absolute path", id="relative"),
        pytest.param("{tmp}/missing", "is not an existing folder", id="missing"),
        pytest.param("{tmp}/file", "is not an existing folder", id="file"),
    ],
)
def test_bad_folder_list_raises(tmp_path, monkeypatch, value, error):
    (tmp_path / "file").touch()
    if value is None:
        monkeypatch.delenv("TRUFO_LOCAL_INPUT_DIRS", raising=False)
    else:
        monkeypatch.setenv("TRUFO_LOCAL_INPUT_DIRS", value.format(tmp=tmp_path))
    with pytest.raises(ValueError, match=error):
        parse_folder_list("TRUFO_LOCAL_INPUT_DIRS", "read")


def test_mount_points_decode_octal_escapes():
    mountinfo = (
        "28 1 8:1 / / rw,relatime shared:1 - ext4 /dev/sda1 rw\n"
        "36 28 8:1 /home/me/my\\040media /srv/my\\040media rw,relatime - ext4 /dev/sda1 rw\n"
        "37 28 8:1 /home/me/in /srv/tab\\011and\\134slash ro master:1 - ext4 /dev/sda1 rw\n"
    )
    assert parse_mount_points(mountinfo) == {
        Path("/"),
        Path("/srv/my media"),
        Path("/srv/tab\tand\\slash"),
    }


@pytest.mark.parametrize(
    "url, accepted",
    [
        ("https://api.trufo.ai", True),
        ("https://trufo.ai", True),
        ("http://api.trufo.ai", False),
        ("api.trufo.ai", False),
        ("https://api.trufo.ai.example.com", False),
        ("https://eviltrufo.ai", False),
        ("https://api.trufo.ai@example.com", False),
    ],
)
def test_api_url_must_be_https_on_trufo_ai(url, accepted):
    assert is_trufo_api_url(url) is accepted
