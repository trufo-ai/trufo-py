# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for intf/credentials.py — credential storage."""

import json
from unittest.mock import patch

import pytest

from trufo.api.session import TrufoSession


# Patch CONFIG_DIR, CREDENTIALS_FILE, SESSION_FILE to use tmp_path
@pytest.fixture(autouse=True)
def _patch_config_paths(tmp_path, monkeypatch):
    """Redirect all credential file operations to tmp_path."""
    monkeypatch.setattr("trufo.intf.credentials.CONFIG_DIR", tmp_path / ".trufo")
    monkeypatch.setattr(
        "trufo.intf.credentials.CREDENTIALS_FILE",
        tmp_path / ".trufo" / "credentials",
    )
    monkeypatch.setattr(
        "trufo.intf.credentials.SESSION_FILE",
        tmp_path / ".trufo" / "session",
    )


# import after fixture definition so patches apply at call time
from trufo.intf.credentials import (
    clear_session,
    load_api_key,
    load_session,
    save_api_key,
    save_session,
)


class TestLoadApiKey:
    """load_api_key reads from env var or credentials file."""

    def test_returns_none_when_no_key(self):
        assert load_api_key() is None

    def test_reads_from_env_var(self, monkeypatch):
        monkeypatch.setenv("TRUFO_API_KEY", "env-key-123")
        assert load_api_key() == "env-key-123"

    def test_env_var_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("TRUFO_API_KEY", "  key  ")
        assert load_api_key() == "key"

    def test_reads_from_file(self, tmp_path):
        save_api_key("file-key-456")
        assert load_api_key() == "file-key-456"

    def test_env_var_takes_precedence(self, tmp_path, monkeypatch):
        save_api_key("file-key")
        monkeypatch.setenv("TRUFO_API_KEY", "env-key")
        assert load_api_key() == "env-key"


class TestSaveApiKey:
    """save_api_key writes key with restricted permissions."""

    def test_saves_to_file(self, tmp_path):
        save_api_key("my-api-key")
        cred_file = tmp_path / ".trufo" / "credentials"
        assert cred_file.exists()
        assert cred_file.read_text().strip() == "my-api-key"

    def test_file_permissions_are_600(self, tmp_path):
        save_api_key("key")
        cred_file = tmp_path / ".trufo" / "credentials"
        mode = cred_file.stat().st_mode & 0o777
        assert mode == 0o600

    def test_clears_existing_session(self, tmp_path):
        # save a session first
        session = TrufoSession(access_token="at", refresh_token="rt")
        save_session(session)
        sess_file = tmp_path / ".trufo" / "session"
        assert sess_file.exists()

        # saving a new api key should clear the session
        save_api_key("new-key")
        assert not sess_file.exists()


class TestLoadSession:
    """load_session reads tokens from env vars or session file."""

    def test_returns_none_when_no_session(self):
        assert load_session() is None

    def test_reads_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("TRUFO_ACCESS_TOKEN", "at-env")
        monkeypatch.setenv("TRUFO_REFRESH_TOKEN", "rt-env")
        session = load_session()
        assert session is not None
        assert session.access_token == "at-env"
        assert session.refresh_token == "rt-env"

    def test_reads_from_file(self, tmp_path):
        session = TrufoSession(access_token="at-file", refresh_token="rt-file")
        save_session(session)

        loaded = load_session()
        assert loaded is not None
        assert loaded.access_token == "at-file"
        assert loaded.refresh_token == "rt-file"

    def test_returns_none_on_corrupt_file(self, tmp_path):
        sess_file = tmp_path / ".trufo" / "session"
        sess_file.parent.mkdir(parents=True, exist_ok=True)
        sess_file.write_text("not-valid-json")
        assert load_session() is None


class TestSaveSession:
    """save_session writes tokens with restricted permissions."""

    def test_saves_to_file(self, tmp_path):
        session = TrufoSession(access_token="at", refresh_token="rt")
        save_session(session)

        sess_file = tmp_path / ".trufo" / "session"
        data = json.loads(sess_file.read_text())
        assert data["access_token"] == "at"
        assert data["refresh_token"] == "rt"

    def test_file_permissions_are_600(self, tmp_path):
        session = TrufoSession(access_token="at", refresh_token="rt")
        save_session(session)

        sess_file = tmp_path / ".trufo" / "session"
        mode = sess_file.stat().st_mode & 0o777
        assert mode == 0o600


class TestClearSession:
    """clear_session removes session file."""

    def test_removes_session_file(self, tmp_path):
        session = TrufoSession(access_token="at", refresh_token="rt")
        save_session(session)
        sess_file = tmp_path / ".trufo" / "session"
        assert sess_file.exists()

        clear_session()
        assert not sess_file.exists()

    def test_no_error_when_no_session(self):
        # should not raise
        clear_session()
