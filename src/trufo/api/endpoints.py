# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Trufo API endpoint definitions.
"""

import os

TRUFO_API_URL = "https://api.trufo.ai"
TRUFO_API_URL_EUROPE = "https://eu.api.trufo.ai"
# test signing runs on its own host; unlike the main API there is no dedicated
# per-user test endpoint yet (dedicated test sandboxes may come later, which
# would require a package update to configure)
TRUFO_API_URL_TEST = "https://test.api.trufo.ai"
TRUFO_CA_URL = "https://ca.trufo.ai"
TRUFO_TSA_URL = "https://tsa.trufo.ai"
TRUFO_OCSP_URL = "https://ocsp.trufo.ai"

# webapp origin — where the browser is sent during loopback sign-in.
# Overridable so the flow can be exercised against a non-production webapp; the
# API base URL is chosen separately via TrufoSession(base_api_url=...).
TRUFO_APP_URL = os.environ.get("TRUFO_APP_URL", "https://app.trufo.ai")

# account / device auth (RFC 8628 — browser on a DIFFERENT machine)
DEVICE_AUTHORIZE = "/account/device/authorize"
DEVICE_TOKEN = "/account/device/token"
# account / loopback auth (RFC 8252 + PKCE — browser on the SAME machine)
LOOPBACK_TOKEN = "/account/loopback/token"
LOOPBACK_AUTH_PATH = "/loopback"  # path on TRUFO_APP_URL, not on the API
ACCOUNT_REFRESH = "/account/refresh"

# registration authority
RA_CSR_JWT = "/ra/c2pa/csr-jwt"
RA_CAWG_INTERIM_CSR_JWT = "/ra/cawg-interim/csr-jwt"

# generator product
GP_INSTANCE_CREATE = "/gproduct/instance/create"
GP_CREDENTIAL_REGISTER = "/gproduct/instance/credential/register"

# TPS content endpoints
TPS_C2PA_SIGN = "/c2pa/sign"
# legacy hosted test path on the main host; superseded by TRUFO_API_URL_TEST +
# TPS_C2PA_SIGN, kept live during deprecation
TPS_C2PA_SIGN_TEST = "/test/c2pa/sign"
TPS_C2PA_GET_S3_URL = "/c2pa/io/get-s3-url"
TPS_CONTENT_RECOVER = "/content/recover"
TPS_CONTENT_GET = "/content/get"
TPS_CONTENT_LIST = "/content/list"
TPS_CONTENT_STATUS = "/content/status"
TPS_BIND_WATERMARK = "/bind/watermark"
TPS_BIND_RESERVE = "/bind/reserve"
TPS_BIND_COMMIT = "/bind/commit"
TPS_C2PA_AI_DISCLOSURE_ADD = "/c2pa/ai-disclosure/add"
TPS_C2PA_AI_DISCLOSURE_LIST = "/c2pa/ai-disclosure/list"
