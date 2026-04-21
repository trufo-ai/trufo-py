# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Quickstart: label a media file as AI-generated via the TPS.

Attaches a C2PA manifest with:
  - AI disclosure  (c2pa.ai-disclosure)
  - CAWG identity assertion (test)

See docs/quickstart/2_ai_labeling.md for details.
Requires a c2pa-sign-test API key — set TRUFO_C2PA_SIGN_TEST_API_KEY
or save it to ~/.trufo/credentials/c2pa_sign_test_api_key.
"""

from pathlib import Path

from trufo.api.tps.sign_c2pa import sign_c2pa_test
from trufo.util.credentials import TrufoApiKey, load_api_key

# --- configuration ---

INPUT_FILE = Path("photo.jpg")
OUTPUT_FILE = Path("labeled.jpg")

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_TEST)
assert api_key, (
    "Set TRUFO_C2PA_SIGN_TEST_API_KEY or run: trufo set-api-key c2pa-sign-test <KEY>"
)

# --- build assertions ---

assertions = [
    # mark as AI-generated
    ["ai_disclosure", {}],
    # identity assertion (required when assertions are present)
    ["cawg_identity", {"cawg_identity_id": "test"}],
]

# --- sign ---

signed_bytes = sign_c2pa_test(api_key, INPUT_FILE.read_bytes(), assertions=assertions)

OUTPUT_FILE.write_bytes(signed_bytes)
print(f"Labeled: {OUTPUT_FILE} ({len(signed_bytes):,} bytes)")
