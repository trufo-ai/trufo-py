# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Quickstart: label AI-generated media by naming a registered AI system.

Signs on the test host with one ai_system assertion. An input without a C2PA
manifest is labeled as AI-generated.

See docs/quickstart/3_ai_labeling.md for details.
Requires a c2pa-sign-test API key — set TRUFO_C2PA_SIGN_TEST_API_KEY
or save it to ~/.trufo/credentials/c2pa_sign_test_api_key — and an AI system
registered with POST /ai-system/add.
"""

from pathlib import Path

from trufo import sign_c2pa_test
from trufo.util.credentials import TrufoAPIKey, load_api_key

# --- configuration ---

# the ai_system_id from POST /ai-system/add ("aisys_…"); register once, not on
# each run: registrations cannot be deleted, and each issues one new watermark ID
# per type of AI involvement
AI_SYSTEM_ID = ""
assert AI_SYSTEM_ID, "Set AI_SYSTEM_ID to the ai_system_id returned by POST /ai-system/add"

# AI output without a C2PA manifest; a signed camera photo is refused
INPUT_FILE = Path("generated.png")
OUTPUT_FILE = Path("labeled.png")

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_TEST)
assert api_key, "Set TRUFO_C2PA_SIGN_TEST_API_KEY or run: trufo set-api-key c2pa-sign-test <KEY>"

# --- sign ---

signed_bytes = sign_c2pa_test(
    api_key,
    INPUT_FILE.read_bytes(),
    assertions=[
        ["ai_system", {"ai_system_id": AI_SYSTEM_ID, "ai_involvement": "ai_generated"}],
    ],
)

OUTPUT_FILE.write_bytes(signed_bytes)
print(f"Labeled {INPUT_FILE} -> {OUTPUT_FILE} ({len(signed_bytes):,} bytes)")
