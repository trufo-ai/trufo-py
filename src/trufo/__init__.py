# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from trufo.api.tca.certs_c2pa import create_instance, register_credential, request_c2pa_cert
from trufo.api.tca.certs_cawg_interim import request_cawg_interim_cert
from trufo.api.tca.certs_test import request_c2pa_test_cert, request_cawg_test_cert
from trufo.api.tps.bind import (
    bind_commit,
    bind_commit_test,
    bind_reserve,
    bind_reserve_test,
    bind_watermark,
    bind_watermark_test,
    watermark_media,
)
from trufo.api.tps.records import get_content, list_content, set_content_status
from trufo.api.tps.recover import recover_content
from trufo.api.tps.sign_c2pa import (
    sign_c2pa,
    sign_c2pa_distributed,
    sign_c2pa_distributed_test,
    sign_c2pa_test,
    sign_c2pa_via_s3,
    sign_c2pa_via_s3_test,
)
from trufo.crypt.keygen import generate_keypair
from trufo.util.credentials import load_api_key, save_api_key
from trufo.util.warnings import TrufoServerWarning

__version__ = "1.3.1"

__all__ = [
    "__version__",
    "bind_commit",
    "bind_commit_test",
    "bind_reserve",
    "bind_reserve_test",
    "bind_watermark",
    "bind_watermark_test",
    "create_instance",
    "generate_keypair",
    "get_content",
    "list_content",
    "load_api_key",
    "recover_content",
    "register_credential",
    "request_c2pa_cert",
    "request_c2pa_test_cert",
    "request_cawg_interim_cert",
    "request_cawg_test_cert",
    "save_api_key",
    "set_content_status",
    "sign_c2pa",
    "sign_c2pa_distributed",
    "sign_c2pa_distributed_test",
    "sign_c2pa_test",
    "sign_c2pa_via_s3",
    "sign_c2pa_via_s3_test",
    "TrufoServerWarning",
    "watermark_media",
]

# register the trufo-py version with tfprov so X-TF-Version is sent on all
# remote calls; no-op if trufo-provenance is not installed
try:
    from tfprov.api.session import set_trufo_version as _set_trufo_version

    _set_trufo_version(__version__)
except ImportError:
    pass
