# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for trufo-py version registration with the optional tfprov package."""

import importlib
import sys
import types


def _reload_trufo_with(monkeypatch, session_module):
    """Reload the ``trufo`` package with a given fake ``tfprov.api.session``.

    Passing ``None`` simulates ``trufo-provenance`` being uninstalled by forcing
    an ``ImportError`` on ``from tfprov.api.session import set_trufo_version``.
    """
    for name in ("tfprov.api.session", "tfprov.api", "tfprov"):
        monkeypatch.delitem(sys.modules, name, raising=False)

    if session_module is None:
        monkeypatch.setitem(sys.modules, "tfprov", None)
    else:
        monkeypatch.setitem(sys.modules, "tfprov", types.ModuleType("tfprov"))
        monkeypatch.setitem(sys.modules, "tfprov.api", types.ModuleType("tfprov.api"))
        monkeypatch.setitem(sys.modules, "tfprov.api.session", session_module)

    import trufo

    return importlib.reload(trufo)


def test_import_registers_version_with_tfprov(monkeypatch):
    recorded = []
    fake_session = types.ModuleType("tfprov.api.session")
    fake_session.set_trufo_version = lambda version: recorded.append(version)

    trufo = _reload_trufo_with(monkeypatch, fake_session)

    assert recorded == [trufo.__version__]


def test_import_without_tfprov_is_noop(monkeypatch):
    # reloading must not raise when trufo-provenance is unavailable
    trufo = _reload_trufo_with(monkeypatch, None)

    assert trufo.__version__
