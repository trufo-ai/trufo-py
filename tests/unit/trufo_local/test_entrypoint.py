# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the trufo-local start checks."""

import base64
import importlib.metadata
import io
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
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


def test_images_pin_their_private_packages():
    folder = entrypoint._REQUIREMENTS_FILE.parent

    def pins(filename):
        # compare the complete version and hashes, independent of the engine extras
        text = re.sub(r"\[.*?\]", "", (folder / filename).read_text())
        return dict(line.split("==", 1) for line in text.splitlines())

    signing_only = pins("requirements.txt")
    full = pins("requirements-full.txt")
    assert signing_only.keys() == {"trufo-provenance", "trufo-avio"}
    assert full.keys() == signing_only.keys() | {"trufo-pawprint"}
    for name, pin in signing_only.items():
        assert full[name] == pin


# the documented line of each start check, after a setting that fails it
_START_LINES = """
api-url TRUFO_API_URL must be an https:// address on trufo.ai, not "http://api.trufo.ai".
no-inputs TRUFO_LOCAL_INPUT_DIRS is not set. List the folders the service may read, separated by ":".
relative TRUFO_LOCAL_OUTPUT_DIRS: "out" is not an absolute path.
unmounted TRUFO_LOCAL_INPUT_DIRS: {tmp}/in is not mounted. Mount it at the same path inside the container.
unreadable Cannot read input folder {tmp}/in as user {user}. See {docs}#folder-permissions
unwritable Cannot write to output folder {tmp}/out as user {user}. See {docs}#folder-permissions
tmp Cannot write to /tmp as user {user}. Mount a writable folder at /tmp.
no-key TRUFO_SDK_DOWNLOAD_API_KEY is not set. Set it to your sdk-download key.
noexec trufo-provenance {version} cannot run from /tmp. Mount /tmp without noexec.
401 packages.trufo.ai refused TRUFO_SDK_DOWNLOAD_API_KEY (HTTP 401). Check that it is an active sdk-download key.
403 packages.trufo.ai refused TRUFO_SDK_DOWNLOAD_API_KEY (HTTP 403). Check that it is an active sdk-download key.
unreachable Could not reach packages.trufo.ai: No route to host.
"""
_SETTINGS = {
    "api-url": {"TRUFO_API_URL": "http://api.trufo.ai"},
    "no-inputs": {"TRUFO_LOCAL_INPUT_DIRS": ""},
    "relative": {"TRUFO_LOCAL_OUTPUT_DIRS": "out"},
    "unmounted": {"mounts": set()},
    "unreadable": {"denied": ["in"]},
    "unwritable": {"denied": ["out"]},
    "tmp": {"denied": ["tmp"]},
    "no-key": {"TRUFO_SDK_DOWNLOAD_API_KEY": ""},
    "noexec": {"noexec": True},
    "401": {"index_error": urllib.error.HTTPError("", 401, "", {}, None)},
    "403": {"index_error": urllib.error.HTTPError("", 403, "", {}, None)},
    "unreachable": {"index_error": urllib.error.URLError("No route to host")},
}


@pytest.fixture
def start(tmp_path, monkeypatch):
    """The container's start, with in/ and out/ listed and mounted, the engine not installed, and
    the package index, pip and exec stubbed: ``run()`` returns what it exits with. ``denied``
    (folder names), ``mounts``, ``noexec`` and ``index_error`` set what it finds; ``requests``,
    ``pip`` and ``exec`` record the stubs' calls."""
    for name in ("in", "out"):
        (tmp_path / name).mkdir()
    monkeypatch.setenv("TRUFO_API_URL", "https://api.trufo.ai")
    monkeypatch.setenv("TRUFO_LOCAL_INPUT_DIRS", f"{tmp_path}/in")
    monkeypatch.setenv("TRUFO_LOCAL_OUTPUT_DIRS", f"{tmp_path}/out")
    monkeypatch.setenv("TRUFO_SDK_DOWNLOAD_API_KEY", "sdk key/1")
    fake = SimpleNamespace(mounts={tmp_path}, denied=[], noexec=False, index_error=None)
    fake.requests, fake.pip, fake.exec = [], [], []

    def version(name):
        raise importlib.metadata.PackageNotFoundError(name)

    def urlopen(request, timeout):
        fake.requests.append(request)
        if fake.index_error:
            raise fake.index_error
        return io.BytesIO()

    def run():
        try:
            entrypoint.main()
        except SystemExit as exc:
            return exc.code

    monkeypatch.setattr(entrypoint, "parse_mount_points", lambda mountinfo: fake.mounts)
    monkeypatch.setattr(os, "access", lambda path, mode: Path(path).name not in fake.denied)
    monkeypatch.setattr(os, "statvfs", lambda path: Mock(f_flag=os.ST_NOEXEC * fake.noexec))
    monkeypatch.setattr(importlib.metadata, "version", version)
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(
        subprocess, "run", lambda args, env: fake.pip.append((args, env)) or Mock(returncode=0)
    )
    monkeypatch.setattr(os, "execv", lambda path, args: fake.exec.append(args))
    fake.run = run
    return fake


def test_index_key_handling(start):
    assert start.run() is None
    (request,) = start.requests
    credential = base64.b64encode(b"__token__:sdk key/1").decode()
    assert (request.full_url, request.unredirected_hdrs, request.headers) == (
        "https://packages.trufo.ai/simple/trufo-provenance/",
        {"Authorization": f"Basic {credential}"},
        {},
    )
    ((pip, env),) = start.pip
    assert {"--require-hashes", "--no-deps", "--user"} <= set(pip)
    assert "sdk key" not in str(pip) and "sdk%20key" not in str(pip)
    assert env["PIP_INDEX_URL"] == "https://__token__:sdk%20key%2F1@packages.trufo.ai/simple/"
    assert start.exec == [
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
    ]


@pytest.mark.parametrize(
    "check, line",
    [
        pytest.param(*entry.split(" ", 1), id=entry.split()[0])
        for entry in _START_LINES.split("\n")[1:-1]
    ],
)
def test_start_lines(start, tmp_path, monkeypatch, check, line):
    for setting, value in _SETTINGS[check].items():
        if setting.isupper():
            monkeypatch.setenv(setting, value)
        else:
            setattr(start, setting, value)
    expected = line.format(
        tmp=tmp_path,
        user=f"{os.getuid()}:{os.getgid()}",
        docs="https://github.com/trufo-ai/trufo-py/blob/main/docs/topics/signing-local-docker.md",
        version=entrypoint.read_pinned_versions()["trufo-provenance"],
    )
    assert (start.run(), start.exec) == (expected, [])
