# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Checks for the engine tests, which run on the installed engine (tfprov)."""

import importlib

import pytest

# fail, not skip, the engine tests when what they run on is missing; here, before the test
# modules import it
for _module in ("tfprov", "fastapi", "httpx"):
    try:
        importlib.import_module(_module)
    except ImportError as exc:
        raise pytest.UsageError(
            f"The engine tests need {_module}, which cannot be imported: {exc}. Install "
            '"trufo[local-sign-only]" (see docs/local/python.md), fastapi and httpx.'
        ) from None
