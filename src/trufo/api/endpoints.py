# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Trufo API endpoint definitions.
"""

import os

from trufo.util.deprecation import deprecated_aliases

TRUFO_API_URL = "https://api.trufo.ai"
TRUFO_API_URL_EUROPE = "https://eu.api.trufo.ai"
# test signing runs on its own host, which serves the content routes (signing,
# recovery, binding) for test keys
TRUFO_API_URL_TEST = "https://test.api.trufo.ai"
TRUFO_CA_URL = "https://ca.trufo.ai"
# test enrollment runs on its own host, which serves the test leaf types only
TRUFO_CA_URL_TEST = "https://test.ca.trufo.ai"
TRUFO_TSA_URL = "https://tsa.trufo.ai"
TRUFO_OCSP_URL = "https://ocsp.trufo.ai"

# webapp origin — where the browser is sent during loopback sign-in.
# Overridable so the flow can be exercised against a non-production webapp; the
# API base URL is chosen separately via TrufoSession(base_api_url=...).
TRUFO_APP_URL = os.environ.get("TRUFO_APP_URL", "https://app.trufo.ai")

# account / device auth (RFC 8628 — browser on a DIFFERENT machine)
DEVICE_AUTHORIZE_PATH = "/account/device/authorize"
DEVICE_TOKEN_PATH = "/account/device/token"
# account / loopback auth (RFC 8252 + PKCE — browser on the SAME machine)
LOOPBACK_TOKEN_PATH = "/account/loopback/token"
LOOPBACK_AUTH_PATH = "/loopback"  # path on TRUFO_APP_URL, not on the API
ACCOUNT_REFRESH_PATH = "/account/refresh"

# registration authority
RA_CSR_JWT_PATH = "/ra/c2pa/csr-jwt"
RA_CAWG_INTERIM_CSR_JWT_PATH = "/ra/cawg-interim/csr-jwt"

# generator product
GP_INSTANCE_CREATE_PATH = "/gproduct/instance/create"
GP_CREDENTIAL_REGISTER_PATH = "/gproduct/instance/credential/register"

# TPS content endpoints
TPS_C2PA_SIGN_PATH = "/c2pa/sign"
# legacy hosted test path on the production hosts, which answer it with 410;
# TRUFO_API_URL_TEST + TPS_C2PA_SIGN_PATH replaces it
TPS_C2PA_SIGN_TEST = "/test/c2pa/sign"
TPS_C2PA_GET_S3_URL = "/c2pa/io/get-s3-url"  # deprecated: use TPS_GET_S3_UPLOAD_URL_PATH
TPS_GET_S3_UPLOAD_URL_PATH = "/io/get-s3-upload-url"
TPS_CONTENT_RECOVER_PATH = "/content/recover"
TPS_CONTENT_GET_PATH = "/content/get"
TPS_CONTENT_LIST_PATH = "/content/list"
TPS_CONTENT_STATUS_PATH = "/content/status"
TPS_BIND_WATERMARK_PATH = "/bind/watermark"
TPS_BIND_RESERVE_PATH = "/bind/reserve"
TPS_BIND_COMMIT_PATH = "/bind/commit"
# TODO(sunset-2027-01-31): the ai-disclosure endpoints go; successor /ai-system/add and /list
TPS_C2PA_AI_DISCLOSURE_ADD = "/c2pa/ai-disclosure/add"
TPS_C2PA_AI_DISCLOSURE_LIST = "/c2pa/ai-disclosure/list"
TPS_AI_SYSTEM_ADD_PATH = "/ai-system/add"
TPS_AI_SYSTEM_LIST_PATH = "/ai-system/list"
TPS_AI_SYSTEM_STATUS_PATH = "/ai-system/status"
TPS_C2PA_SOFTWARE_AGENT_ADD_PATH = "/c2pa/software-agent/add"
TPS_C2PA_SOFTWARE_AGENT_LIST_PATH = "/c2pa/software-agent/list"


__getattr__ = deprecated_aliases(
    globals(),
    {
        "DEVICE_AUTHORIZE": "DEVICE_AUTHORIZE_PATH",
        "DEVICE_TOKEN": "DEVICE_TOKEN_PATH",
        "LOOPBACK_TOKEN": "LOOPBACK_TOKEN_PATH",
        "ACCOUNT_REFRESH": "ACCOUNT_REFRESH_PATH",
        "RA_CSR_JWT": "RA_CSR_JWT_PATH",
        "RA_CAWG_INTERIM_CSR_JWT": "RA_CAWG_INTERIM_CSR_JWT_PATH",
        "GP_INSTANCE_CREATE": "GP_INSTANCE_CREATE_PATH",
        "GP_CREDENTIAL_REGISTER": "GP_CREDENTIAL_REGISTER_PATH",
        "TPS_C2PA_SIGN": "TPS_C2PA_SIGN_PATH",
        "TPS_GET_S3_UPLOAD_URL": "TPS_GET_S3_UPLOAD_URL_PATH",
        "TPS_CONTENT_RECOVER": "TPS_CONTENT_RECOVER_PATH",
        "TPS_CONTENT_GET": "TPS_CONTENT_GET_PATH",
        "TPS_CONTENT_LIST": "TPS_CONTENT_LIST_PATH",
        "TPS_CONTENT_STATUS": "TPS_CONTENT_STATUS_PATH",
        "TPS_BIND_WATERMARK": "TPS_BIND_WATERMARK_PATH",
        "TPS_BIND_RESERVE": "TPS_BIND_RESERVE_PATH",
        "TPS_BIND_COMMIT": "TPS_BIND_COMMIT_PATH",
        "TPS_C2PA_SOFTWARE_AGENT_ADD": "TPS_C2PA_SOFTWARE_AGENT_ADD_PATH",
        "TPS_C2PA_SOFTWARE_AGENT_LIST": "TPS_C2PA_SOFTWARE_AGENT_LIST_PATH",
    },
)
