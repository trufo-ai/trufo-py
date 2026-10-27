# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the trufo-local folder-list parser."""

import pytest
from entrypoint import parse_folder_list


def test_folder_list_is_resolved(tmp_path, monkeypatch):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    monkeypatch.setenv("TRUFO_LOCAL_INPUT_DIRS", f"{tmp_path}/a:{tmp_path}/a/../b")
    assert parse_folder_list("TRUFO_LOCAL_INPUT_DIRS") == [tmp_path / "a", tmp_path / "b"]


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
        parse_folder_list("TRUFO_LOCAL_INPUT_DIRS")
