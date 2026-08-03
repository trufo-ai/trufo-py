# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Quickstart: embed and recover a Trufo watermark.

Demonstrates:
  - signing with a watermark, under each effort level
  - detecting a sign that completed without embedding one
  - recovering the watermark from the signed media

See docs/quickstart/6_watermarking.md for details.
Requires a c2pa-sign-test API key, and a c2pa-decode key for recovery.
"""

import warnings
from pathlib import Path

from trufo import TrufoServerWarning, recover_content, sign_c2pa_test
from trufo.c2pa import WatermarkEffort
from trufo.util.credentials import TrufoApiKey, load_api_key

# --- configuration ---

INPUT_FILE = Path("photo.jpg")       # a watermarkable format: JPEG, PNG, WebP,
OUTPUT_FILE = Path("watermarked.jpg")  # TIFF, WAV, FLAC, MP3, or M4A

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_TEST)
assert api_key, (
    "Set TRUFO_C2PA_SIGN_TEST_API_KEY or run: trufo set-api-key c2pa-sign-test <KEY>"
)

media_bytes = INPUT_FILE.read_bytes()


# --- 1. watermark, failing the sign if it cannot be embedded -----------------
# A bare ["watermark", {}] means effort "require": any failure is an error.

signed_bytes = sign_c2pa_test(
    api_key,
    media_bytes,
    actions=[["watermark", {}]],
)
OUTPUT_FILE.write_bytes(signed_bytes)
print(f"Watermarked {INPUT_FILE} -> {OUTPUT_FILE}")


# --- 2. mixed media: watermark whatever supports it --------------------------
# "require_if_supported" signs unsupported formats without a watermark rather
# than failing — useful when one pipeline handles many formats. The skip is
# reported as a warning, which is the only way to tell the outputs apart.

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always", TrufoServerWarning)
    signed_bytes = sign_c2pa_test(
        api_key,
        media_bytes,
        actions=[["watermark", {"effort": WatermarkEffort.REQUIRE_IF_SUPPORTED.value}]],
    )

if caught:
    for notice in caught:
        print(f"  signed WITHOUT a watermark: {notice.message}")
else:
    print("  watermark embedded")


# --- 3. recover a watermark --------------------------------------------------
# Works even after the C2PA manifest has been stripped — re-encoded, screenshot,
# or run through a metadata-scrubbing pipeline.

decode_key = load_api_key(TrufoApiKey.C2PA_DECODE)
if decode_key:
    result = recover_content(decode_key, OUTPUT_FILE.read_bytes())
    if result.detected:
        print(f"Recovered watermark {result.wid} (confidence {result.confidence:.4f})")
    else:
        print("No watermark detected")
else:
    print("Skipping recovery: run `trufo set-api-key c2pa-decode <KEY>`")
