# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
trufo CLI entry point.

Assembles subcommands from intf/ modules.
"""

import argparse

from trufo.intf import credentials


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="trufo", description="Trufo CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    credentials.register_subcommands(sub)

    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
