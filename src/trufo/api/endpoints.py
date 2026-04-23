# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Trufo API endpoint definitions.
"""

TRUFO_API_URL = "https://api.trufo.ai"
TRUFO_CA_URL = "https://ca.trufo.ai"
TRUFO_TSA_URL = "https://tsa.trufo.ai"
TRUFO_OCSP_URL = "https://ocsp.trufo.ai"

# account / device auth
DEVICE_AUTHORIZE = "/account/device/authorize"
DEVICE_TOKEN = "/account/device/token"
ACCOUNT_REFRESH = "/account/refresh"

# registration authority
RA_CSR_JWT = "/ra/c2pa/csr-jwt"

# generator product
GP_INSTANCE_CREATE = "/gproduct/instance/create"
GP_CREDENTIAL_REGISTER = "/gproduct/instance/credential/register"

# TPS content endpoints
TPS_C2PA_SIGN_TEST = "/test/c2pa/sign"
TPS_C2PA_AI_DISCLOSURE_ADD = "/c2pa/ai-disclosure/add"
TPS_C2PA_AI_DISCLOSURE_LIST = "/c2pa/ai-disclosure/list"
