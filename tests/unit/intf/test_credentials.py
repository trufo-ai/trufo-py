# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for trufo.util.credentials — API-key and session storage."""

import json

import pytest

from trufo.api.session import TrufoSession

_ALL_API_KEY_ENV_VARS = (
    "TRUFO_API_KEY",
    "TRUFO_C2PA_SIGN_PROD_API_KEY",
    "TRUFO_C2PA_SIGN_TEST_API_KEY",
    "TRUFO_TSA_API_KEY",
    "TRUFO_ACCESS_TOKEN",
    "TRUFO_REFRESH_TOKEN",
)


# Patch CONFIG_DIR, CREDENTIALS_DIR, SESSION_FILE to use tmp_path
@pytest.fixture(autouse=True)
def _patch_config_paths(tmp_path, monkeypatch):
    """Redirect all credential file operations to tmp_path."""
    creds_dir = tmp_path / ".trufo" / "credentials"
    monkeypatch.setattr("trufo.util.credentials.CONFIG_DIR", tmp_path / ".trufo")
    monkeypatch.setattr("trufo.util.credentials.CREDENTIALS_DIR", creds_dir)
    monkeypatch.setattr(
        "trufo.util.credentials.SESSION_FILE",
        tmp_path / ".trufo" / "session",
    )
    # patch the file lookup dict so it points into tmp_path
    from trufo.util.credentials import TrufoApiKey

    monkeypatch.setattr(
        "trufo.util.credentials._API_KEY_FILES",
        {
            TrufoApiKey.TRUFO_API:      creds_dir / "trufo_api_key",
            TrufoApiKey.C2PA_SIGN_PROD: creds_dir / "c2pa_sign_prod_api_key",
            TrufoApiKey.C2PA_SIGN_TEST: creds_dir / "c2pa_sign_test_api_key",
            TrufoApiKey.TSA:            creds_dir / "tsa_api_key",
        },
    )
    # clear any real env vars so they don't leak into tests
    for var in _ALL_API_KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


from trufo.util.credentials import (
    TrufoApiKey,
    clear_session,
    load_api_key,
    load_session,
    save_api_key,
    save_session,
)


# (enum, env var, credential file name) — the full scope matrix
_ALL_SCOPES = [
    (TrufoApiKey.TRUFO_API,      "TRUFO_API_KEY",                "trufo_api_key"),
    (TrufoApiKey.C2PA_SIGN_PROD, "TRUFO_C2PA_SIGN_PROD_API_KEY", "c2pa_sign_prod_api_key"),
    (TrufoApiKey.C2PA_SIGN_TEST, "TRUFO_C2PA_SIGN_TEST_API_KEY", "c2pa_sign_test_api_key"),
    (TrufoApiKey.TSA,            "TRUFO_TSA_API_KEY",            "tsa_api_key"),
]


class TestLoadApiKey:
    """load_api_key reads from env var or credentials file."""

    @pytest.mark.parametrize("kt,_env,_fname", _ALL_SCOPES)
    def test_returns_none_when_no_key(self, kt, _env, _fname):
        assert load_api_key(kt) is None

    @pytest.mark.parametrize("kt,env,_fname", _ALL_SCOPES)
    def test_reads_from_env_var(self, monkeypatch, kt, env, _fname):
        monkeypatch.setenv(env, f"env-{kt.value}")
        assert load_api_key(kt) == f"env-{kt.value}"

    def test_env_var_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("TRUFO_API_KEY", "  key  ")
        assert load_api_key(TrufoApiKey.TRUFO_API) == "key"

    @pytest.mark.parametrize("kt,_env,_fname", _ALL_SCOPES)
    def test_reads_from_file(self, kt, _env, _fname):
        save_api_key(kt, f"file-{kt.value}")
        assert load_api_key(kt) == f"file-{kt.value}"

    def test_env_var_takes_precedence(self, monkeypatch):
        save_api_key(TrufoApiKey.TRUFO_API, "file-key")
        monkeypatch.setenv("TRUFO_API_KEY", "env-key")
        assert load_api_key(TrufoApiKey.TRUFO_API) == "env-key"

    def test_scopes_are_independent(self):
        for kt, _env, _fname in _ALL_SCOPES:
            save_api_key(kt, f"key-{kt.value}")
        for kt, _env, _fname in _ALL_SCOPES:
            assert load_api_key(kt) == f"key-{kt.value}"

    def test_accepts_string_key_type(self):
        save_api_key("c2pa-sign-test", "string-key")
        assert load_api_key("c2pa-sign-test") == "string-key"

    def test_invalid_key_type_raises(self):
        with pytest.raises(ValueError, match="Invalid API key type"):
            load_api_key("invalid")

    def test_legacy_tps_alias_is_rejected(self):
        # The old "tps" alias has been removed; ensure it is no longer accepted.
        with pytest.raises(ValueError, match="Invalid API key type"):
            load_api_key("tps")


class TestSaveApiKey:
    """save_api_key writes key with restricted permissions."""

    @pytest.mark.parametrize("kt,_env,fname", _ALL_SCOPES)
    def test_saves_to_file(self, tmp_path, kt, _env, fname):
        save_api_key(kt, "my-api-key")
        key_file = tmp_path / ".trufo" / "credentials" / fname
        assert key_file.exists()
        assert key_file.read_text().strip() == "my-api-key"

    @pytest.mark.parametrize("kt,_env,fname", _ALL_SCOPES)
    def test_file_permissions_are_600(self, tmp_path, kt, _env, fname):
        save_api_key(kt, "key")
        key_file = tmp_path / ".trufo" / "credentials" / fname
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
