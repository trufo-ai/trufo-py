# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""API keys and the session: in the environment and in the files of ~/.trufo."""

import json
import logging
import os
import re
import stat

import pytest

from trufo.api.endpoints import TRUFO_API_URL
from trufo.api.session import TrufoSession
from trufo.util.credentials import (
    TrufoAPIKey,
    clear_session,
    load_api_key,
    load_session,
    save_api_key,
    save_session,
)

# each key type's environment variable and file
KEY_TYPES = [
    (TrufoAPIKey.TRUFO_API, "TRUFO_API_KEY", "trufo_api_key"),
    (TrufoAPIKey.C2PA_SIGN_PROD, "TRUFO_C2PA_SIGN_PROD_API_KEY", "c2pa_sign_prod_api_key"),
    (TrufoAPIKey.C2PA_SIGN_TEST, "TRUFO_C2PA_SIGN_TEST_API_KEY", "c2pa_sign_test_api_key"),
    (
        TrufoAPIKey.CONTENT_RECOVER_TEST,
        "TRUFO_CONTENT_RECOVER_TEST_API_KEY",
        "content_recover_test_api_key",
    ),
    (
        TrufoAPIKey.CONTENT_RECOVER_PROD,
        "TRUFO_CONTENT_RECOVER_PROD_API_KEY",
        "content_recover_prod_api_key",
    ),
    (TrufoAPIKey.WATERMARK_TEST, "TRUFO_WATERMARK_TEST_API_KEY", "watermark_test_api_key"),
    (TrufoAPIKey.WATERMARK_PROD, "TRUFO_WATERMARK_PROD_API_KEY", "watermark_prod_api_key"),
    (TrufoAPIKey.TSA, "TRUFO_TSA_API_KEY", "tsa_api_key"),
]


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_files_are_private(trufo_home, monkeypatch):
    key_file, session_file = trufo_home / "credentials" / "tsa_api_key", trufo_home / "session"
    save_api_key(TrufoAPIKey.TSA, "key-0")
    save_session(TrufoSession(access_token="access-0", refresh_token="refresh-0"))
    assert (_mode(key_file), _mode(session_file), _mode(key_file.parent)) == (0o600, 0o600, 0o700)

    # a file whose replacement fails is left as it was, and no other file is left
    def replace(source, destination):
        raise OSError("Replace failed.")

    monkeypatch.setattr(os, "replace", replace)
    with pytest.raises(OSError, match="Replace failed."):
        save_api_key(TrufoAPIKey.TSA, "key-1")
    with pytest.raises(OSError, match="Replace failed."):
        save_session(TrufoSession(access_token="access-1", refresh_token="refresh-1"))
    assert key_file.read_text() == "key-0\n"
    assert json.loads(session_file.read_text())["refresh_token"] == "refresh-0"
    assert sorted(path.name for path in trufo_home.rglob("*")) == [
        "credentials",
        "session",
        "tsa_api_key",
    ]


@pytest.mark.parametrize("key_type, env_var, file_name", KEY_TYPES)
def test_api_key_sources(trufo_home, monkeypatch, key_type, env_var, file_name):
    assert load_api_key(key_type) is None
    # a key type is the enum or its value
    save_api_key(key_type.value, "file-key")
    key_file = trufo_home / "credentials" / file_name
    assert (key_file.read_text(), _mode(key_file)) == ("file-key\n", 0o600)
    assert load_api_key(key_type) == "file-key"
    monkeypatch.setenv(env_var, "  env-key  ")
    assert load_api_key(key_type.value) == "env-key"
    # no other key type sees either
    assert [load_api_key(other) for other, _, _ in KEY_TYPES if other is not key_type] == [None] * 7


@pytest.mark.parametrize("key_type", ["invalid", "tps", ""])
def test_key_types(trufo_home, key_type):
    valid = ", ".join(key.value for key, _, _ in KEY_TYPES)
    message = re.escape(f"Invalid API key type: {key_type!r} (expected {valid})")
    with pytest.raises(ValueError, match=message):
        load_api_key(key_type)
    with pytest.raises(ValueError, match=message):
        save_api_key(key_type, "key")


@pytest.mark.parametrize(
    "environment, file_text, expected",
    [
        (
            {"TRUFO_ACCESS_TOKEN": " access-env ", "TRUFO_REFRESH_TOKEN": "refresh-env"},
            '{"access_token": "access-file", "refresh_token": "refresh-file"}',
            ("access-env", "refresh-env"),
        ),
        (
            {},
            '{"access_token": "access-file", "refresh_token": "refresh-file"}',
            ("access-file", "refresh-file"),
        ),
        (
            {"TRUFO_ACCESS_TOKEN": "access-env"},
            None,
            "Both TRUFO_ACCESS_TOKEN and TRUFO_REFRESH_TOKEN must be set (only one found).",
        ),
        (
            {"TRUFO_REFRESH_TOKEN": "refresh-env"},
            None,
            "Both TRUFO_ACCESS_TOKEN and TRUFO_REFRESH_TOKEN must be set (only one found).",
        ),
        ({}, "not-valid-json", "Corrupt session file"),
        ({}, '{"access_token": "access-file"}', "missing key: 'refresh_token'"),
        (
            {},
            None,
            "No session found. Run 'trufo login' or set TRUFO_ACCESS_TOKEN + TRUFO_REFRESH_TOKEN.",
        ),
    ],
)
def test_load_session(trufo_home, monkeypatch, environment, file_text, expected):
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    if file_text is not None:
        trufo_home.mkdir()
        (trufo_home / "session").write_text(file_text)
    if isinstance(expected, tuple):
        session = load_session()
        assert (session.access_token, session.refresh_token) == expected
    else:
        with pytest.raises(RuntimeError, match=re.escape(expected)):
            load_session()


def _refresh(trufo_api, session, access_token, refresh_token):
    """Make ``session`` refresh its tokens to the given ones, through a request that gets 401."""
    trufo_api.answer("POST", f"{TRUFO_API_URL}/path", (401, {}), {})
    trufo_api.answer(
        "POST",
        f"{TRUFO_API_URL}/account/refresh",
        {"access_token": access_token, "refresh_token": refresh_token},
    )
    session.make_request("/path", {})


def test_refreshed_tokens_are_saved(trufo_api, trufo_home, monkeypatch):
    session_file = trufo_home / "session"
    save_session(TrufoSession(access_token="access-0", refresh_token="refresh-0"))
    session = load_session()

    _refresh(trufo_api, session, "access-1", "refresh-1")
    assert json.loads(session_file.read_text()) == {
        "access_token": "access-1",
        "refresh_token": "refresh-1",
    }
    assert _mode(session_file) == 0o600
    assert [path.name for path in trufo_home.iterdir()] == ["session"]

    # a newer login wins
    save_session(TrufoSession(access_token="access-2", refresh_token="refresh-2"))
    _refresh(trufo_api, session, "stale-access", "stale-refresh")
    assert json.loads(session_file.read_text())["refresh_token"] == "refresh-2"

    # so does a logout
    clear_session()
    _refresh(trufo_api, session, "stale-access", "stale-refresh")
    assert not session_file.exists()

    # a session from the environment is never written
    monkeypatch.setenv("TRUFO_ACCESS_TOKEN", "access-env")
    monkeypatch.setenv("TRUFO_REFRESH_TOKEN", "refresh-env")
    session = load_session()
    _refresh(trufo_api, session, "access-3", "refresh-3")
    assert (session.access_token, session.refresh_token) == ("access-3", "refresh-3")
    assert not session_file.exists()


def test_save_and_clear_session(trufo_home):
    save_session(TrufoSession(access_token="access-0", refresh_token="refresh-0"))
    assert json.loads((trufo_home / "session").read_text()) == {
        "access_token": "access-0",
        "refresh_token": "refresh-0",
    }
    clear_session()
    assert not (trufo_home / "session").exists()
    # nothing to clear
    clear_session()


@pytest.mark.xfail(strict=True, reason="A blank variable is to count as unset.")
def test_blank_environment_key_falls_back_to_the_file(trufo_home, monkeypatch):
    monkeypatch.setenv("TRUFO_API_KEY", "  ")
    assert load_api_key(TrufoAPIKey.TRUFO_API) is None
    save_api_key(TrufoAPIKey.TRUFO_API, "file-key")
    assert load_api_key(TrufoAPIKey.TRUFO_API) == "file-key"


def test_unsaved_refresh_is_a_warning(trufo_api, trufo_home, monkeypatch, caplog):
    save_session(TrufoSession(access_token="access-0", refresh_token="refresh-0"))
    session = load_session()

    def replace(source, destination):
        raise OSError("Replace failed.")

    monkeypatch.setattr(os, "replace", replace)
    with caplog.at_level(logging.WARNING):
        _refresh(trufo_api, session, "access-1", "refresh-1")
    # the request was sent again, once, with the new token
    assert len(trufo_api.requests) == 3
    assert trufo_api.requests[-1].headers["Authorization"] == "Bearer access-1"
    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
        (logging.WARNING, "Could not persist refreshed session tokens: Replace failed.")
    ]
