# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the trufo-local start checks."""

import importlib.metadata
import re
import subprocess
from pathlib import Path
from unittest.mock import Mock

import entrypoint
import pytest
from entrypoint import is_mounted, is_trufo_api_url, parse_folder_list, parse_mount_points

ONE_PIN = "trufo-provenance[c2pa]==2.2.0 --hash=sha256:aa\n"
TWO_PINS = (
    "trufo-provenance[c2pa,pawprint]==2.2.0 --hash=sha256:aa --hash=sha256:bb\n"
    "trufo-pawprint==0.5.2 --hash=sha256:cc\n"
)
TWO_PIN_VERSIONS = {"trufo-provenance": "2.2.0", "trufo-pawprint": "0.5.2"}


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
    "folder, mounted",
    [
        ("/srv/media", True),
        ("/srv/media/in", True),
        ("/srv", False),
        ("/tmp", False),
    ],
)
def test_folder_must_be_on_a_mounted_volume(folder, mounted):
    assert is_mounted(Path(folder), {Path("/"), Path("/srv/media")}) is mounted


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


@pytest.mark.parametrize(
    "text, installed, line, pip_runs",
    [
        pytest.param(
            TWO_PINS,
            TWO_PIN_VERSIONS,
            "trufo-provenance 2.2.0 and trufo-pawprint 0.5.2 are already installed.",
            0,
            id="both installed",
        ),
        pytest.param(
            TWO_PINS,
            {**TWO_PIN_VERSIONS, "trufo-pawprint": "0.5.1"},
            "Installing trufo-provenance 2.2.0 and trufo-pawprint 0.5.2 from packages.trufo.ai.",
            1,
            id="other pawprint",
        ),
        pytest.param(
            ONE_PIN, {}, "Installing trufo-provenance 2.2.0 from packages.trufo.ai.", 1, id="absent"
        ),
    ],
)
def test_installs_unless_every_pin_is_installed(
    tmp_path, monkeypatch, capsys, text, installed, line, pip_runs
):
    (tmp_path / "requirements.txt").write_text(text)
    monkeypatch.setattr(entrypoint, "_REQUIREMENTS_FILE", tmp_path / "requirements.txt")

    def version(name):
        if name not in installed:
            raise importlib.metadata.PackageNotFoundError(name)
        return installed[name]

    monkeypatch.setattr(importlib.metadata, "version", version)
    monkeypatch.setattr(entrypoint, "_check_index_access", lambda api_key: None)
    run = Mock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(subprocess, "run", run)
    entrypoint._install_pinned_packages("key")
    assert capsys.readouterr().err == f"{line}\n"
    assert run.call_count == pip_runs


def test_both_images_pin_the_same_engine():
    folder = entrypoint._REQUIREMENTS_FILE.parent
    signing_only, full = (
        re.sub(r"\[.*?\]", "", (folder / name).read_text().splitlines()[0])
        for name in ("requirements.txt", "requirements-full.txt")
    )
    assert signing_only == full
