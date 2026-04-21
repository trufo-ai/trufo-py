# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Quickstart: attach CAWG assertions to media via the TPS.

Attaches a C2PA manifest with:
  - CAWG creator metadata  (JSON-LD, Dublin Core)
  - CAWG training/mining permissions
  - CAWG identity assertion  (test)

See docs/quickstart/3_cawg_publish.md for details.
Requires a c2pa-sign-test API key — set TRUFO_C2PA_SIGN_TEST_API_KEY
or save it to ~/.trufo/credentials/c2pa_sign_test_api_key.
"""

from pathlib import Path

from trufo.api.tps.sign_c2pa import sign_c2pa_test
from trufo.util.credentials import TrufoApiKey, load_api_key

# --- configuration ---

INPUT_FILE = Path("photo.jpg")
OUTPUT_FILE = Path("published.jpg")

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_TEST)
assert api_key, (
    "Set TRUFO_C2PA_SIGN_TEST_API_KEY or run: trufo set-api-key c2pa-sign-test <KEY>"
)

# --- build assertions ---

assertions = [
    # creator metadata (JSON-LD, Dublin Core)
    ["cawg_metadata", {
        "assertion": {
            "@context": {
                "dc": "http://purl.org/dc/elements/1.1/",
            },
            "dc:creator": ["Alice"],
            "dc:rights": "© 2026 Alice. All rights reserved.",
        },
    }],
    # AI training and data-mining permissions
    ["cawg_training", {
        "assertion": {
            "entries": {
                "cawg.ai_training": {"use": "notAllowed"},
                "cawg.ai_inference": {"use": "notAllowed"},
                "cawg.data_mining": {"use": "notAllowed"},
            },
        },
    }],
    # identity assertion (required when assertions are present)
    ["cawg_identity", {"cawg_identity_id": "test"}],
]

# --- sign ---

signed_bytes = sign_c2pa_test(
    api_key,
    INPUT_FILE.read_bytes(),
    assertions=assertions,
)

OUTPUT_FILE.write_bytes(signed_bytes)
print(f"Published: {OUTPUT_FILE} ({len(signed_bytes):,} bytes)")
