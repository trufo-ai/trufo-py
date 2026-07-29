# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Quickstart: redact an assertion from an ingredient's C2PA manifest.

Removes c2pa.metadata from wherever it lives in the input's provenance
history (the immediate parent, or any earlier generation).

See docs/quickstart/5_ingredients.md for details.
Requires a c2pa-sign-prod API key — set TRUFO_C2PA_SIGN_PROD_API_KEY
or save it to ~/.trufo/credentials/c2pa_sign_prod_api_key.
Requires INPUT_FILE to already have a C2PA manifest.
"""

from pathlib import Path

from trufo import sign_c2pa
from trufo.util.credentials import TrufoApiKey, load_api_key

# --- configuration ---

INPUT_FILE = Path("signed_photo.jpg")
OUTPUT_FILE = Path("redacted.jpg")

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_PROD)
assert api_key, (
    "Set TRUFO_C2PA_SIGN_PROD_API_KEY or run: trufo set-api-key c2pa-sign-prod <KEY>"
)

# --- redact + sign ---

signed_bytes = sign_c2pa(
    api_key,
    INPUT_FILE.read_bytes(),
    actions=[
        ["redact", {"label": "c2pa.metadata", "reason": "c2pa.PII.present"}],
    ],
)

OUTPUT_FILE.write_bytes(signed_bytes)
print(f"Redacted: {OUTPUT_FILE} ({len(signed_bytes):,} bytes)")
