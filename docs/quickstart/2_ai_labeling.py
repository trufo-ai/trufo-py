# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Quickstart: label a media file as AI-generated via the TPS.

Attaches a C2PA manifest with:
  - AI disclosure  (c2pa.ai-disclosure)
  - CAWG identity assertion (test)

See docs/quickstart/2_ai_labeling.md for details.
Requires TRUFO_TPS_API_KEY env var or ~/.trufo/credentials/tps_api_key.
"""

from pathlib import Path

from trufo.api.tps.generate_c2pa import generate_c2pa_test
from trufo.util.credentials import TrufoApiKey, load_api_key

# --- configuration ---

INPUT_FILE = Path("photo.jpg")
OUTPUT_FILE = Path("labeled.jpg")

api_key = load_api_key(TrufoApiKey.TPS)
assert api_key, "Set TRUFO_TPS_API_KEY or run: trufo set-api-key tps <KEY>"

# --- build assertions ---

assertions = [
    # mark as AI-generated
    ["ai_disclosure", {}],
    # identity assertion (required when assertions are present)
    ["cawg_identity", {"cawg_identity_id": "test"}],
]

# --- sign ---

signed_bytes = generate_c2pa_test(api_key, INPUT_FILE.read_bytes(), assertions=assertions)

OUTPUT_FILE.write_bytes(signed_bytes)
print(f"Labeled: {OUTPUT_FILE} ({len(signed_bytes):,} bytes)")
