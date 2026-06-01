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
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

from trufo.api.tca.certs_c2pa import create_instance, register_credential, request_c2pa_cert
from trufo.crypt.algorithms import LeafType
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


def cmd_get_c2pa_cert(args: argparse.Namespace) -> None:
    """Request a C2PA certificate for a registered instance credential."""
    out_dir = Path(args.out_dir)
    leaf_key_path = out_dir / "leaf_key.pem"
    cert_chain_path = out_dir / "cert_chain.pem"

    if not args.overwrite:
        existing = [p for p in (leaf_key_path, cert_chain_path) if p.exists()]
        if existing:
            for p in existing:
                print(f"Error: file already exists: {p}", file=sys.stderr)
            print("Use --overwrite to overwrite existing files.", file=sys.stderr)
            sys.exit(1)

    instance_key_pem = Path(args.instance_key).read_text(encoding="utf-8")

    # generate fresh leaf key (always ES256 / P-256)
    leaf_key = ec.generate_private_key(ec.SECP256R1())

    cert_chain_pem = request_c2pa_cert(
        gpi_id=args.gpi,
        gpic_id=args.gpic,
        instance_key_pem=instance_key_pem,
        private_key_signer=leaf_key,
        leaf_type=LeafType(args.leaf_type),
        validity_days=args.validity_days,
    )

    out_dir.mkdir(parents=True, exist_ok=True)

    leaf_key_pem_bytes = leaf_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    leaf_key_path.write_bytes(leaf_key_pem_bytes)
    os.chmod(leaf_key_path, 0o600)

    cert_chain_path.write_bytes(cert_chain_pem)

    print(f"Leaf key:   {leaf_key_path}")
    print(f"Cert chain: {cert_chain_path}")


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

    # get-c2pa-cert
    leaf_type_choices = [t.value for t in LeafType]
    p = sub.add_parser("get-c2pa-cert", help="Request a C2PA certificate.")
    p.add_argument("--gpi", required=True, help="Instance ID (gpi_...).")
    p.add_argument("--gpic", required=True, help="Credential ID (gpic_...).")
    p.add_argument("--instance-key", required=True, help="Path to instance private key PEM.")
    p.add_argument("--leaf-type", default="c2pa-l1", choices=leaf_type_choices, help="Certificate type (default: c2pa-l1).")
    p.add_argument("--validity-days", type=int, default=None, help="Requested validity in days (server default if omitted).")
    p.add_argument("--out-dir", default=".", help="Output directory (default: current directory).")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing output files.")
    p.set_defaults(func=cmd_get_c2pa_cert)
