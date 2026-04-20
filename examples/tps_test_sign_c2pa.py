# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Example: sign a media file with C2PA via the Trufo TPS test endpoint.

Demonstrates manifest-only signing with assertions:
- AI disclosure (default)
- CAWG creator metadata (JSON-LD)
- CAWG training/mining permissions
- CAWG identity (test)

Requires a TPS API key (``TRUFO_TPS_API_KEY`` env var or
``~/.trufo/credentials/tps_api_key``).  No account setup needed.
"""

from pathlib import Path

from trufo.api.tps.generate_c2pa import generate_c2pa_test
from trufo.util.credentials import TrufoApiKey, load_api_key

# --- configuration ---

INPUT_FILE = Path("photo.jpg")
OUTPUT_FILE = Path("signed.jpg")

api_key = load_api_key(TrufoApiKey.TPS)
assert api_key, "Set TRUFO_TPS_API_KEY or run: trufo set-api-key tps <KEY>"

# --- read input ---

media_bytes = INPUT_FILE.read_bytes()

# --- build assertions ---

assertions = [
    # mark content as AI-generated (default model type)
    ["ai_disclosure", {}],
    # embed creator metadata (JSON-LD with Dublin Core)
    ["cawg_metadata", {
        "assertion": {
            "@context": {
                "dc": "http://purl.org/dc/elements/1.1/",
            },
            "dc:creator": ["Alice"],
            "dc:title": "Example image",
        },
    }],
    # declare training/mining permissions
    ["cawg_training", {
        "assertion": {
            "entries": {
                "cawg.ai_training": {"use": "notAllowed"},
                "cawg.ai_inference": {"use": "allowed"},
                "cawg.data_mining": {
                    "use": "constrained",
                    "constraint_info": "See license terms.",
                },
            },
        },
    }],
    # attach test identity assertion
    ["cawg_identity", {"cawg_identity_id": "test"}],
]

# --- sign ---

signed_bytes = generate_c2pa_test(api_key, media_bytes, assertions=assertions)

OUTPUT_FILE.write_bytes(signed_bytes)
print(f"Signed: {OUTPUT_FILE} ({len(signed_bytes):,} bytes)")
