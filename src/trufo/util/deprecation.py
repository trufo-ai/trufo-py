# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Deprecated names kept importable after a rename."""

import warnings
from collections.abc import Callable
from typing import Any


def deprecated_aliases(namespace: dict[str, Any], aliases: dict[str, str]) -> Callable[[str], Any]:
    """Return a PEP 562 module ``__getattr__`` that serves deprecated names.

    Each old name in ``aliases`` resolves to the object bound to its new name in
    ``namespace`` and warns with ``DeprecationWarning``.
    """

    def __getattr__(name: str) -> Any:
        if name in aliases:
            warnings.warn(
                f"{name} is deprecated; use {aliases[name]}.", DeprecationWarning, stacklevel=2
            )
            return namespace[aliases[name]]
        raise AttributeError(f"module {namespace['__name__']!r} has no attribute {name!r}")

    return __getattr__
