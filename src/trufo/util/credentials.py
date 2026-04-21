# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Credential storage for trufo authentication.

Persists API keys and session tokens to ~/.trufo/ with restricted
file permissions (0600).

File layout (CLI — ``trufo set-api-key``, ``trufo login``):
    ~/.trufo/
    ├── credentials/
    │   ├── trufo_api_key           # trufo-api key (device flow)
    │   ├── c2pa_sign_prod_api_key  # c2pa-sign-prod key (/c2pa/sign)
    │   ├── c2pa_sign_test_api_key  # c2pa-sign-test key (/test/c2pa/sign)
    │   └── tsa_api_key             # tsa key (tsa.trufo.ai)
    └── session                     # access + refresh tokens (JSON)

Environment variables (programmatic — CI/CD, containers):
    TRUFO_API_KEY                   → trufo-api key
    TRUFO_C2PA_SIGN_PROD_API_KEY    → c2pa-sign-prod key
    TRUFO_C2PA_SIGN_TEST_API_KEY    → c2pa-sign-test key
    TRUFO_TSA_API_KEY               → tsa key
    TRUFO_ACCESS_TOKEN              → access token  (both must be set)
    TRUFO_REFRESH_TOKEN             → refresh token (both must be set)

Each credential has exactly one source: env var OR file. The env var
takes precedence — if set, the file is ignored for that credential.

``TrufoApiKey`` values match the server-side ``ApiKeyScope`` wire names,
so the enum doubles as the scope identifier when creating keys in the
Trufo dashboard.
"""

import json
import os
import stat
from enum import Enum
from pathlib import Path

from trufo.api.session import TrufoSession

CONFIG_DIR = Path.home() / ".trufo"
CREDENTIALS_DIR = CONFIG_DIR / "credentials"
SESSION_FILE = CONFIG_DIR / "session"

_FILE_PERMISSIONS = stat.S_IRUSR | stat.S_IWUSR  # 0o600


class TrufoApiKey(str, Enum):
    """API key types. Values match the server-side ``ApiKeyScope``."""

    TRUFO_API = "trufo-api"
    C2PA_SIGN_PROD = "c2pa-sign-prod"
    C2PA_SIGN_TEST = "c2pa-sign-test"
    TSA = "tsa"


# env var name and file path for each key type
_SESSION_ACCESS_TOKEN_ENV_VAR = "TRUFO_ACCESS_TOKEN"
_SESSION_REFRESH_TOKEN_ENV_VAR = "TRUFO_REFRESH_TOKEN"

# "trufo-api" uses a short env var to avoid the awkward TRUFO_TRUFO_API_API_KEY
_API_KEY_ENV_VARS = {
    TrufoApiKey.TRUFO_API:      "TRUFO_API_KEY",
    TrufoApiKey.C2PA_SIGN_PROD: "TRUFO_C2PA_SIGN_PROD_API_KEY",
    TrufoApiKey.C2PA_SIGN_TEST: "TRUFO_C2PA_SIGN_TEST_API_KEY",
    TrufoApiKey.TSA:            "TRUFO_TSA_API_KEY",
}
_API_KEY_FILES = {
    TrufoApiKey.TRUFO_API:      CREDENTIALS_DIR / "trufo_api_key",
    TrufoApiKey.C2PA_SIGN_PROD: CREDENTIALS_DIR / "c2pa_sign_prod_api_key",
    TrufoApiKey.C2PA_SIGN_TEST: CREDENTIALS_DIR / "c2pa_sign_test_api_key",
    TrufoApiKey.TSA:            CREDENTIALS_DIR / "tsa_api_key",
}


def _write_private(path: Path, content: str) -> None:
    """Write a file with 0600 permissions."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(_FILE_PERMISSIONS)


def _resolve_api_key_type(key_type: str | TrufoApiKey) -> TrufoApiKey:
    """Resolve a string or TrufoApiKey to TrufoApiKey.

    Raises:
        ValueError: If *key_type* is not a valid API key type.
    """
    if isinstance(key_type, TrufoApiKey):
        return key_type
    try:
        return TrufoApiKey(key_type)
    except ValueError:
        valid = ", ".join(k.value for k in TrufoApiKey)
        raise ValueError(f"Invalid API key type: {key_type!r} (expected {valid})") from None


# --- API key ---


def load_api_key(key_type: str | TrufoApiKey) -> str | None:
    """Load an API key from env var or credentials file.

    Args:
        key_type: A ``TrufoApiKey`` member or its string value (e.g.
            ``"trufo-api"``, ``"c2pa-sign-prod"``, ``"c2pa-sign-test"``,
            ``"tsa"``).

    Returns:
        The API key string, or ``None`` if not configured.

    Raises:
        ValueError: If *key_type* is not a valid API key type.
    """
    kt = _resolve_api_key_type(key_type)

    env_key = os.environ.get(_API_KEY_ENV_VARS[kt])
    if env_key:
        return env_key.strip()

    key_file = _API_KEY_FILES[kt]
    if key_file.exists():
        content = key_file.read_text(encoding="utf-8").strip()
        if content:
            return content

    return None


def save_api_key(key_type: str | TrufoApiKey, api_key: str) -> None:
    """Write an API key to ``~/.trufo/credentials/``.

    Args:
        key_type: A ``TrufoApiKey`` member or its string value.
        api_key: The API key value.

    Raises:
        ValueError: If *key_type* is not a valid API key type.
    """
    kt = _resolve_api_key_type(key_type)
    _write_private(_API_KEY_FILES[kt], api_key + "\n")


# --- Session tokens ---


def load_session() -> TrufoSession:
    """Load a TrufoSession from env vars or session file.

    Raises:
        RuntimeError: If no session is configured, the session file is
            corrupt, or env vars are partially set.
    """
    access = os.environ.get(_SESSION_ACCESS_TOKEN_ENV_VAR)
    refresh = os.environ.get(_SESSION_REFRESH_TOKEN_ENV_VAR)

    if access or refresh:
        if not (access and refresh):
            raise RuntimeError(
                f"Both {_SESSION_ACCESS_TOKEN_ENV_VAR} and {_SESSION_REFRESH_TOKEN_ENV_VAR} must be set (only one found)."
            )
        return TrufoSession(access_token=access.strip(), refresh_token=refresh.strip())

    if SESSION_FILE.exists():
        text = SESSION_FILE.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Corrupt session file ({SESSION_FILE}): {exc}") from exc
        try:
            return TrufoSession(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
            )
        except KeyError as exc:
            raise RuntimeError(
                f"Session file ({SESSION_FILE}) missing key: {exc}"
            ) from exc

    raise RuntimeError(
        f"No session found. Run 'trufo login' or set {_SESSION_ACCESS_TOKEN_ENV_VAR} + {_SESSION_REFRESH_TOKEN_ENV_VAR}."
    )


def save_session(session: TrufoSession) -> None:
    """Write session tokens to ~/.trufo/session."""
    data = json.dumps(
        {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
        }
    )
    _write_private(SESSION_FILE, data + "\n")


def clear_session() -> None:
    """Remove ~/.trufo/session if it exists."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
