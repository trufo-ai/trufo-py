# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
CLI commands for the C2PA certificate enrollment workflow.

Commands:
    add-gpi         Create a generator product instance.
    register-gpic   Register an instance credential (public key).
    get-c2pa-cert   Request a C2PA certificate (CSR JWT + EST enrollment).
"""

import argparse
import sys
from pathlib import Path

from trufo.api.tca.certs_c2pa import create_instance, register_credential
from trufo.util.credentials import load_session, save_session


def _require_session():
    """Load session or exit with error."""
    session = load_session()
    if not session:
        print("No active session. Run: trufo login", file=sys.stderr)
        sys.exit(1)
    return session


def cmd_add_gpi(args: argparse.Namespace) -> None:
    """Create a generator product instance."""
    session = _require_session()
    gpi_id = create_instance(session, args.gp, args.name)
    save_session(session)
    print(f"Instance created: {gpi_id}")


def cmd_register_gpic(args: argparse.Namespace) -> None:
    """Register an instance credential (public key)."""
    session = _require_session()
    public_key_pem = Path(args.pem).read_text(encoding="utf-8")
    gpic_id = register_credential(
        session,
        args.gpi,
        args.label,
        args.alg,
        public_key_pem,
    )
    save_session(session)
    print(f"Credential registered: {gpic_id}")


def register_subcommands(sub: argparse._SubParsersAction) -> None:
    """Register certificate-related subcommands on the parser."""
    # add-gpi
    p = sub.add_parser("add-gpi", help="Create a generator product instance.")
    p.add_argument("--gp", required=True, help="Generator product ID (gp_...).")
    p.add_argument("--name", required=True, help="Instance name.")
    p.set_defaults(func=cmd_add_gpi)

    # register-gpic
    p = sub.add_parser("register-gpic", help="Register an instance credential.")
    p.add_argument("--gpi", required=True, help="Instance ID (gpi_...).")
    p.add_argument("--label", required=True, help="Credential label.")
    p.add_argument("--alg", required=True, help="Key algorithm (ES256 or EdDSA).")
    p.add_argument("--pem", required=True, help="Path to public key PEM file.")
    p.set_defaults(func=cmd_register_gpic)
