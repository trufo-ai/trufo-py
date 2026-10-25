# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Quickstart: sign a media file with a C2PA manifest.

Demonstrates the three signing modes:
  - simple       (media sent in the request body)
  - TASK via S3  (production only; see the companion guide)
  - distributed  (media never leaves this machine)

See docs/quickstart/2_c2pa_signing.md for details.
Requires a c2pa-sign-test API key — set TRUFO_C2PA_SIGN_TEST_API_KEY
or save it to ~/.trufo/credentials/c2pa_sign_test_api_key.
"""

import warnings
from pathlib import Path

from trufo import (
    TrufoServerWarning,
    sign_c2pa_test,
)
from trufo.util.credentials import TrufoAPIKey, load_api_key

# --- configuration ---

INPUT_FILE = Path("photo.jpg")
OUTPUT_FILE = Path("signed.jpg")

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_TEST)
assert api_key, (
    "Set TRUFO_C2PA_SIGN_TEST_API_KEY or run: trufo set-api-key c2pa-sign-test <KEY>"
)

media_bytes = INPUT_FILE.read_bytes()


# --- 1. simple signing -------------------------------------------------------
# The default choice. Media is sent in the request body.

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always", TrufoServerWarning)
    signed_bytes = sign_c2pa_test(
        api_key,
        media_bytes,
        actions=[["publish", {}]],
        assertions=[["cawg_identity", {"cawg_identity_id": "test"}]],
    )

OUTPUT_FILE.write_bytes(signed_bytes)
print(f"Signed {INPUT_FILE} -> {OUTPUT_FILE} ({len(signed_bytes)} bytes)")

# Notices are non-fatal: the sign succeeded, but something was skipped.
for notice in caught:
    print(f"  notice: {notice.message}")


# --- 2. signing large media via S3 -------------------------------------------
# TASK is not available on the test host. For production, use sign_c2pa(...,
# execution_mode=ExecutionMode.TASK, mime_type="image/jpeg"); see the guide.


# --- 3. distributed signing --------------------------------------------------
# The manifest is assembled locally and Trufo signs its claim; the original
# media file is not sent.
#
# Requires:  pip install "trufo[local-sign-only]"   (or "trufo[local-full]")
# Runs on Linux x86_64 with CPython 3.12.

try:
    from trufo import sign_c2pa_distributed_test

    signed_locally = sign_c2pa_distributed_test(
        api_key,
        media_bytes,
        assertions=[["cawg_identity", {"cawg_identity_id": "test"}]],
    )
    print(f"Signed locally ({len(signed_locally)} bytes)")
except ImportError as exc:
    print(f"Skipping distributed signing: {exc}")


# --- going to production -----------------------------------------------------
# Swap the helpers (sign_c2pa, sign_c2pa_distributed) and use a
# c2pa-sign-prod key. Production signing requires completed Organization
# Validation for your organization.
