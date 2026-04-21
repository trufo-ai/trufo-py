# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Quickstart: authenticate with the TPS and persist tokens for reuse.

Steps:
  1. Load the `trufo-api` API key (env var or disk).
  2. Run the device authorization flow — visit the printed URL in a browser
     and approve the device.
  3. Save the session tokens so future runs skip the device flow.

See docs/quickstart/0_auth.md for setup instructions.
Requires TRUFO_API_KEY env var or ~/.trufo/credentials/trufo_api_key.
"""

from trufo.api.session import TrufoSession
from trufo.util.credentials import TrufoApiKey, load_api_key, load_session, save_session

# --- load api key ---

api_key = load_api_key(TrufoApiKey.TRUFO_API)
assert api_key, "trufo-api key not found. Set TRUFO_API_KEY or run: trufo set-api-key trufo-api <KEY>"

# --- device authorization flow ---

session = TrufoSession()
session.init_session(api_key=api_key)
# Prints two lines, e.g.:
#   Visit: https://app.trufo.ai/device?code=ABCD-1234
#   Enter code: ABCD-1234
# Open the URL in a browser and approve.  The script polls until approved.

print("Authenticated.")
print(f"Access token: {session.access_token[:20]}...")

# --- persist for future runs ---

save_session(session)
print("Session saved to ~/.trufo/session")

# --- reload in future runs (skips device flow) ---

# session = load_session()
# data = session.make_request("/some/endpoint", {"key": "value"})
