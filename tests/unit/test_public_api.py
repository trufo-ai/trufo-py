# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The SDK's public names: exported and deprecated names, and importing without the engine."""

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

import trufo
import trufo.c2pa

# the names a release keeps; a name left out of a later release fails here
EXPORTED_NAMES = {
    trufo: """
        __version__ ExecutionMode TaskType TaskStatus TaskReceipt TaskInfo SignC2PATaskResult
        BindWatermarkTaskResult TaskFailedError TaskWaitTimeoutError BindWatermarkResult
        BindReserveResult RecoverContentResult GetS3UploadURLResult SignC2PAS3Result
        TrufoServerWarning get_task wait_for_task submit_c2pa_sign submit_bind_watermark
        sign_c2pa_cloud sign_c2pa_cloud_test sign_c2pa_local sign_c2pa_local_test sign_c2pa_s3
        sign_c2pa_via_s3 sign_c2pa_via_s3_test get_s3_upload_url bind_watermark
        bind_watermark_test bind_reserve bind_reserve_test bind_commit bind_commit_test
        watermark_media get_content list_content set_content_status recover_content
        create_instance register_credential request_c2pa_cert request_c2pa_cert_test
        request_c2pa_dummy_cert request_cawg_dummy_cert request_cawg_interim_cert
        generate_keypair load_api_key save_api_key
    """,
    trufo.c2pa: """
        AIInvolvement DEFAULT_REMOTE_MANIFEST_HOSTS DigitalSourceType ManifestSettings
        RedactableAssertion RedactionReason RemoteManifestSettings SignedIngredientPolicy
        SignedInputPolicy ThumbnailPolicy ThumbnailSettings ThumbnailSize TrufoAction UserAssertion
        WatermarkEffort WatermarkIDAllocationMode WatermarkMode WatermarkProfile WatermarkSettings
    """,
}

_ENDPOINT_PATHS = [
    "DEVICE_AUTHORIZE",
    "DEVICE_TOKEN",
    "LOOPBACK_TOKEN",
    "ACCOUNT_REFRESH",
    "RA_CSR_JWT",
    "RA_CAWG_INTERIM_CSR_JWT",
    "GP_INSTANCE_CREATE",
    "GP_CREDENTIAL_REGISTER",
    "TPS_C2PA_SIGN",
    "TPS_GET_S3_UPLOAD_URL",
    "TPS_CONTENT_RECOVER",
    "TPS_CONTENT_GET",
    "TPS_CONTENT_LIST",
    "TPS_CONTENT_STATUS",
    "TPS_BIND_WATERMARK",
    "TPS_BIND_RESERVE",
    "TPS_BIND_COMMIT",
    "TPS_C2PA_SOFTWARE_AGENT_ADD",
    "TPS_C2PA_SOFTWARE_AGENT_LIST",
]


@pytest.mark.parametrize(
    "module_path, old, new",
    [
        ("trufo.util.credentials", "TrufoApiKey", "TrufoAPIKey"),
        ("trufo.api.tps.io", "C2PAS3Upload", "GetS3UploadURLResult"),
        ("trufo.api.tps.sign_c2pa", "C2PAS3Upload", "GetS3UploadURLResult"),
        ("trufo.api.tps.recover", "ContentRecovery", "RecoverContentResult"),
        ("trufo.api.tps.bind", "BindWatermark", "BindWatermarkResult"),
        ("trufo.api.tps.bind", "BindReservation", "BindReserveResult"),
        ("trufo.api.tps.sign_c2pa", "C2PAS3SignedOutput", "SignC2PAS3Result"),
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
        *[("trufo.api.endpoints", old, f"{old}_PATH") for old in _ENDPOINT_PATHS],
    ],
)
def test_deprecated_names_resolve(module_path, old, new):
    module = importlib.import_module(module_path)
    with pytest.warns(DeprecationWarning, match=f"{old} is deprecated; use {new}\\.") as record:
        alias = getattr(module, old)
    assert alias is getattr(module, new)
    assert record[0].filename == __file__
    with pytest.raises(AttributeError):
        getattr(module, "NoSuchName")


def test_import_loads_no_engine():
    code = """
import importlib
import importlib.abc
import pkgutil
import sys
attempted = []
class BlockEngines(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'tfprov', 'pawprint', 'torch', 'cv2', 'numpy'}:
            attempted.append(fullname)
            raise ModuleNotFoundError(f'No module named {fullname!r}', name=fullname)
sys.meta_path.insert(0, BlockEngines())
import trufo
for module in pkgutil.walk_packages(trufo.__path__, 'trufo.'):
    importlib.import_module(module.name)
assert not attempted, f'Importing the SDK imported an optional engine: {attempted}'
"""
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
    subprocess.run([sys.executable, "-c", code], env=env, check=True)


@pytest.mark.parametrize("module", EXPORTED_NAMES, ids=lambda module: module.__name__)
def test_exported_names(module):
    for name in EXPORTED_NAMES[module].split():
        assert name in module.__all__ and hasattr(module, name), name
    assert issubclass(trufo.TrufoServerWarning, UserWarning)
