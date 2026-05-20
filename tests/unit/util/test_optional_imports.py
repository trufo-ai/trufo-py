# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for optional dependency import helpers."""

import types

import pytest

from trufo.util.optional_imports import require_provenance_module


def test_require_provenance_module_returns_imported_module(monkeypatch):
    """The helper returns the imported module when provenance is installed."""
    module = types.ModuleType("tfprov")

    def fake_import_module(module_name):
        assert module_name == "tfprov"
        return module

    monkeypatch.setattr("trufo.util.optional_imports.import_module", fake_import_module)

    assert require_provenance_module() is module


def test_require_provenance_module_raises_clear_install_error(monkeypatch):
    """Missing tfprov raises an install hint for the provenance extra."""

    def fake_import_module(module_name):
        raise ModuleNotFoundError(name="tfprov")

    monkeypatch.setattr("trufo.util.optional_imports.import_module", fake_import_module)

    with pytest.raises(ImportError, match=r"trufo\[provenance\]"):
        require_provenance_module()


def test_require_provenance_module_preserves_nested_import_errors(monkeypatch):
    """Missing dependencies inside tfprov are not rewritten as install-hint errors."""

    def fake_import_module(module_name):
        raise ModuleNotFoundError(name="nested_dependency")

    monkeypatch.setattr("trufo.util.optional_imports.import_module", fake_import_module)

    with pytest.raises(ModuleNotFoundError) as exc_info:
        require_provenance_module()

    assert exc_info.value.name == "nested_dependency"
