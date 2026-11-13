# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Deprecated names resolve to their renamed objects with a warning."""

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
        ("trufo.api.endpoints", "TPS_C2PA_SIGN", "TPS_C2PA_SIGN_PATH"),
        ("trufo", "request_c2pa_test_cert", "request_c2pa_dummy_cert"),
        ("trufo", "request_cawg_test_cert", "request_cawg_dummy_cert"),
        ("trufo.api.tca.certs_test", "request_c2pa_test_cert", "request_c2pa_dummy_cert"),
        ("trufo.api.tca.certs_test", "request_cawg_test_cert", "request_cawg_dummy_cert"),
        ("trufo.crypt.tca_certs", "TEST_HMAC_SECRET", "DUMMY_HMAC_SECRET"),
        ("trufo.api.tca.certs_test", "TEST_HMAC_SECRET", "DUMMY_HMAC_SECRET"),
        ("trufo", "sign_c2pa", "sign_c2pa_cloud"),
        ("trufo", "sign_c2pa_test", "sign_c2pa_cloud_test"),
        ("trufo", "sign_c2pa_distributed", "sign_c2pa_local"),
        ("trufo", "sign_c2pa_distributed_test", "sign_c2pa_local_test"),
        ("trufo.api.tps.sign_c2pa", "sign_c2pa", "sign_c2pa_cloud"),
        ("trufo.api.tps.sign_c2pa", "sign_c2pa_test", "sign_c2pa_cloud_test"),
        ("trufo.api.tps.sign_c2pa", "sign_c2pa_distributed", "sign_c2pa_local"),
        ("trufo.api.tps.sign_c2pa", "sign_c2pa_distributed_test", "sign_c2pa_local_test"),
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
