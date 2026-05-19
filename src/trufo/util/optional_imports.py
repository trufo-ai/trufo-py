# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Helpers for optional Trufo SDK dependency groups."""

from importlib import import_module
from types import ModuleType


def require_provenance_module(module_name: str = "tfprov") -> ModuleType:
    """Import a ``trufo-provenance`` module or raise a clear install error.

    ``trufo-provenance`` is intentionally optional so default ``trufo`` installs
    stay lightweight. Public wrappers that need the provenance engine should call
    this helper at runtime instead of importing ``tfprov`` at module import time.
    """
    try:
        return import_module(module_name)
    except ModuleNotFoundError as exc:
        root_module = module_name.split(".", maxsplit=1)[0]
        if exc.name == root_module:
            raise ImportError(
                "The optional trufo-provenance dependency is required. "
                'Install it with: pip install "trufo[provenance]".'
            ) from exc
        raise
