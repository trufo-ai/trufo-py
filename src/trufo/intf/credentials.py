# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Local credential storage and CLI commands for trufo authentication.

Persists API key and session tokens to ~/.trufo/ with restricted
file permissions (0600). Environment variables take precedence.

File layout:
    ~/.trufo/
    ├── credentials     # API key (plaintext, chmod 600)
    └── session         # access + refresh tokens (JSON, chmod 600)

Environment variable overrides:
    TRUFO_API_KEY          → overrides credentials file
    TRUFO_ACCESS_TOKEN     → overrides session file (access token)
    TRUFO_REFRESH_TOKEN    → overrides session file (refresh token)

CLI commands:
    set-api-key <key>   Save API key to ~/.trufo/credentials.
    login               Authenticate via device authorization (opens browser).
    logout              Clear saved session tokens.
"""

import argparse
import json
import os
import stat
import sys
from pathlib import Path

from trufo.api.session import TrufoSession

CONFIG_DIR = Path.home() / ".trufo"
CREDENTIALS_FILE = CONFIG_DIR / "credentials"
SESSION_FILE = CONFIG_DIR / "session"
TSA_CREDENTIALS_FILE = CONFIG_DIR / "tsa_credentials"

_FILE_PERMISSIONS = stat.S_IRUSR | stat.S_IWUSR  # 0o600


def _ensure_config_dir() -> None:
    """Create ~/.trufo/ with restricted permissions if needed."""
    CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)


def _write_private(path: Path, content: str) -> None:
    """Write a file with 0600 permissions."""
    _ensure_config_dir()
    path.write_text(content, encoding="utf-8")
    path.chmod(_FILE_PERMISSIONS)


# --- API key ---


def load_api_key() -> str | None:
    """Load API key from env var or credentials file."""
    env_key = os.environ.get("TRUFO_API_KEY")
    if env_key:
        return env_key.strip()

    if CREDENTIALS_FILE.exists():
        content = CREDENTIALS_FILE.read_text(encoding="utf-8").strip()
        if content:
            return content

    return None


def save_api_key(api_key: str) -> None:
    """Write API key to ~/.trufo/credentials. Clears existing session."""
    _write_private(CREDENTIALS_FILE, api_key + "\n")
    clear_session()


# --- TSA API key ---


def load_tsa_key() -> str | None:
    """Load TSA API key from env var or tsa_credentials file."""
    env_key = os.environ.get("TRUFO_TSA_API_KEY")
    if env_key:
        return env_key.strip()

    if TSA_CREDENTIALS_FILE.exists():
        content = TSA_CREDENTIALS_FILE.read_text(encoding="utf-8").strip()
        if content:
            return content

    return None


def save_tsa_key(tsa_key: str) -> None:
    """Write TSA API key to ~/.trufo/tsa_credentials."""
    _write_private(TSA_CREDENTIALS_FILE, tsa_key + "\n")


# --- Session tokens ---


def load_session() -> TrufoSession | None:
    """Load a TrufoSession from env vars or session file.

    Returns None if no stored tokens are found.
    """
    access = os.environ.get("TRUFO_ACCESS_TOKEN")
    refresh = os.environ.get("TRUFO_REFRESH_TOKEN")
    if access and refresh:
        return TrufoSession(access_token=access.strip(), refresh_token=refresh.strip())

    if SESSION_FILE.exists():
        try:
            data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            return TrufoSession(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
            )
        except (json.JSONDecodeError, KeyError):
            return None

    return None


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


# --- CLI commands ---


def cmd_set_api_key(args: argparse.Namespace) -> None:
    """Save API key to ~/.trufo/credentials."""
    save_api_key(args.key)
    print("API key saved.")


def cmd_set_tsa_key(args: argparse.Namespace) -> None:
    """Save TSA API key to ~/.trufo/tsa_credentials."""
    save_tsa_key(args.key)
    print("TSA API key saved.")


def cmd_login(args: argparse.Namespace) -> None:
    """Authenticate via device authorization flow."""
    api_key = load_api_key()
    if not api_key:
        print("No API key configured. Run: trufo set-api-key <KEY>", file=sys.stderr)
        sys.exit(1)

    session = TrufoSession()
    session.init_session(api_key)
    save_session(session)
    print("Login successful.")


def cmd_logout(args: argparse.Namespace) -> None:
    """Clear saved session tokens."""
    clear_session()
    print("Session cleared.")


def register_subcommands(sub: argparse._SubParsersAction) -> None:
    """Register credential-related subcommands on the parser."""
    p = sub.add_parser("set-api-key", help="Save API key.")
    p.add_argument("key", help="Trufo API key.")
    p.set_defaults(func=cmd_set_api_key)

    p = sub.add_parser("set-tsa-key", help="Save TSA API key.")
    p.add_argument("key", help="Trufo TSA API key.")
    p.set_defaults(func=cmd_set_tsa_key)

    p = sub.add_parser("login", help="Authenticate via device authorization.")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("logout", help="Clear saved session.")
    p.set_defaults(func=cmd_logout)
