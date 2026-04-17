# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for intf/credentials.py — credential storage."""

import json
from unittest.mock import patch

import pytest

from trufo.api.session import TrufoSession


# Patch CONFIG_DIR, CREDENTIALS_DIR, SESSION_FILE to use tmp_path
@pytest.fixture(autouse=True)
def _patch_config_paths(tmp_path, monkeypatch):
    """Redirect all credential file operations to tmp_path."""
    monkeypatch.setattr("trufo.intf.credentials.CONFIG_DIR", tmp_path / ".trufo")
    monkeypatch.setattr(
        "trufo.intf.credentials.CREDENTIALS_DIR",
        tmp_path / ".trufo" / "credentials",
    )
    monkeypatch.setattr(
        "trufo.intf.credentials.SESSION_FILE",
        tmp_path / ".trufo" / "session",
    )
    # patch the file lookup dicts so they point into tmp_path
    from trufo.intf.credentials import TrufoApiKey

    monkeypatch.setattr(
        "trufo.intf.credentials._API_KEY_FILES",
        {
            TrufoApiKey.TPS: tmp_path / ".trufo" / "credentials" / "tps_api_key",
            TrufoApiKey.TSA: tmp_path / ".trufo" / "credentials" / "tsa_api_key",
        },
    )
    # clear any real env vars so they don't leak into tests
    for var in ("TRUFO_TPS_API_KEY", "TRUFO_TSA_API_KEY", "TRUFO_ACCESS_TOKEN", "TRUFO_REFRESH_TOKEN"):
        monkeypatch.delenv(var, raising=False)


from trufo.intf.credentials import (
    TrufoApiKey,
    clear_session,
    load_api_key,
    load_session,
    save_api_key,
    save_session,
)


class TestLoadApiKey:
    """load_api_key reads from env var or credentials file."""

    def test_returns_none_when_no_key(self):
        assert load_api_key(TrufoApiKey.TPS) is None

    def test_reads_tps_from_env_var(self, monkeypatch):
        monkeypatch.setenv("TRUFO_TPS_API_KEY", "env-key-123")
        assert load_api_key(TrufoApiKey.TPS) == "env-key-123"

    def test_reads_tsa_from_env_var(self, monkeypatch):
        monkeypatch.setenv("TRUFO_TSA_API_KEY", "tsa-env-key")
        assert load_api_key(TrufoApiKey.TSA) == "tsa-env-key"

    def test_env_var_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("TRUFO_TPS_API_KEY", "  key  ")
        assert load_api_key(TrufoApiKey.TPS) == "key"

    def test_reads_from_file(self, tmp_path):
        save_api_key(TrufoApiKey.TPS, "file-key-456")
        assert load_api_key(TrufoApiKey.TPS) == "file-key-456"

    def test_env_var_takes_precedence(self, tmp_path, monkeypatch):
        save_api_key(TrufoApiKey.TPS, "file-key")
        monkeypatch.setenv("TRUFO_TPS_API_KEY", "env-key")
        assert load_api_key(TrufoApiKey.TPS) == "env-key"

    def test_tps_and_tsa_are_independent(self, tmp_path):
        save_api_key(TrufoApiKey.TPS, "tps-key")
        save_api_key(TrufoApiKey.TSA, "tsa-key")
        assert load_api_key(TrufoApiKey.TPS) == "tps-key"
        assert load_api_key(TrufoApiKey.TSA) == "tsa-key"

    def test_accepts_string_key_type(self, tmp_path):
        save_api_key("tps", "string-key")
        assert load_api_key("tps") == "string-key"

    def test_invalid_key_type_raises(self):
        with pytest.raises(ValueError, match="Invalid API key type"):
            load_api_key("invalid")


class TestSaveApiKey:
    """save_api_key writes key with restricted permissions."""

    def test_saves_to_file(self, tmp_path):
        save_api_key(TrufoApiKey.TPS, "my-api-key")
        key_file = tmp_path / ".trufo" / "credentials" / "tps_api_key"
        assert key_file.exists()
        assert key_file.read_text().strip() == "my-api-key"

    def test_file_permissions_are_600(self, tmp_path):
        save_api_key(TrufoApiKey.TPS, "key")
        key_file = tmp_path / ".trufo" / "credentials" / "tps_api_key"
        mode = key_file.stat().st_mode & 0o777
        assert mode == 0o600

    def test_invalid_key_type_raises(self):
        with pytest.raises(ValueError, match="Invalid API key type"):
            save_api_key("bad", "key")


class TestLoadSession:
    """load_session reads tokens from env vars or session file."""

    def test_raises_when_no_session(self):
        with pytest.raises(RuntimeError, match="No session found"):
            load_session()

    def test_reads_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("TRUFO_ACCESS_TOKEN", "at-env")
        monkeypatch.setenv("TRUFO_REFRESH_TOKEN", "rt-env")
        session = load_session()
        assert session.access_token == "at-env"
        assert session.refresh_token == "rt-env"

    def test_raises_on_partial_env_vars(self, monkeypatch):
        monkeypatch.setenv("TRUFO_ACCESS_TOKEN", "at-env")
        with pytest.raises(RuntimeError, match="Both TRUFO_ACCESS_TOKEN and TRUFO_REFRESH_TOKEN"):
            load_session()

    def test_reads_from_file(self, tmp_path):
        session = TrufoSession(access_token="at-file", refresh_token="rt-file")
        save_session(session)

        loaded = load_session()
        assert loaded.access_token == "at-file"
        assert loaded.refresh_token == "rt-file"

    def test_raises_on_corrupt_file(self, tmp_path):
        sess_file = tmp_path / ".trufo" / "session"
        sess_file.parent.mkdir(parents=True, exist_ok=True)
        sess_file.write_text("not-valid-json")
        with pytest.raises(RuntimeError, match="Corrupt session file"):
            load_session()

    def test_raises_on_missing_key_in_file(self, tmp_path):
        sess_file = tmp_path / ".trufo" / "session"
        sess_file.parent.mkdir(parents=True, exist_ok=True)
        sess_file.write_text(json.dumps({"access_token": "at"}))
        with pytest.raises(RuntimeError, match="missing key"):
            load_session()


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
