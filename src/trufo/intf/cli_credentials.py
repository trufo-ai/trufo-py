# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CLI commands for trufo credential management."""

import argparse
import sys

from trufo.api.session import TrufoSession
from trufo.util.credentials import (
    TrufoApiKey,
    load_api_key,
    save_api_key,
    save_session,
    clear_session,
)


# --- CLI commands ---


def cmd_set_api_key(args: argparse.Namespace) -> None:
    """Save API key to ~/.trufo/credentials/."""
    try:
        save_api_key(args.key_type, args.key)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    print(f"{args.key_type} API key saved.")


def cmd_login(args: argparse.Namespace) -> None:
    """Authenticate via device authorization flow."""
    api_key = load_api_key(TrufoApiKey.TRUFO_API)
    if not api_key:
        print(
            "No trufo-api key configured. Run: trufo set-api-key trufo-api <KEY>",
            file=sys.stderr,
        )
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
    p = sub.add_parser("set-api-key", help="Save an API key.")
    p.add_argument(
        "key_type",
        choices=[k.value for k in TrufoApiKey],
        help="API key scope (trufo-api, c2pa-sign-prod, c2pa-sign-test, tsa).",
    )
    p.add_argument("key", help="API key value.")
    p.set_defaults(func=cmd_set_api_key)

    p = sub.add_parser("login", help="Authenticate via device authorization.")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("logout", help="Clear saved session.")
    p.set_defaults(func=cmd_logout)
