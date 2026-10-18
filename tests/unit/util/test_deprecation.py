# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Deprecated class names resolve to their renamed classes with a warning."""

import importlib

import pytest


@pytest.mark.parametrize(
    "module_path,old,new",
    [
        ("trufo.util.credentials", "TrufoApiKey", "TrufoAPIKey"),
        ("trufo.api.tps.io", "C2PAS3Upload", "GetS3UploadURLResult"),
        ("trufo.api.tps.sign_c2pa", "C2PAS3Upload", "GetS3UploadURLResult"),
        ("trufo.api.tps.recover", "ContentRecovery", "RecoverContentResult"),
        ("trufo.api.tps.bind", "BindWatermark", "BindWatermarkResult"),
        ("trufo.api.tps.bind", "BindReservation", "BindReserveResult"),
        ("trufo.api.tps.sign_c2pa", "C2PAS3SignedOutput", "SignC2PAS3Result"),
    ],
)
def test_old_name_warns_and_resolves_to_new(module_path, old, new):
    module = importlib.import_module(module_path)
    with pytest.warns(DeprecationWarning, match=f"{old} is deprecated; use {new}\\.") as record:
        alias = getattr(module, old)
    assert alias is getattr(module, new)
    assert record[0].filename == __file__
    with pytest.raises(AttributeError):
        getattr(module, "NoSuchName")
