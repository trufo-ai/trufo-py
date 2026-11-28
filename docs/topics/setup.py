# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Companion script: authenticate with Trufo and persist tokens for reuse.

Steps:
  1. Load the `trufo-api` API key (env var or disk).
  2. Sign in: the loopback flow opens a browser on this machine (nothing to
     type); on a headless host it falls back to the device flow, which prints
     a URL and a confirmation code to approve from any browser.
  3. Save the session tokens so future runs skip sign-in.

See docs/topics/setup.md for setup instructions.
Requires TRUFO_API_KEY env var or ~/.trufo/credentials/trufo_api_key.
"""

from trufo.api.session import TrufoSession
from trufo.util.credentials import TrufoAPIKey, load_api_key, load_session, save_session

# --- load api key ---

api_key = load_api_key(TrufoAPIKey.TRUFO_API)
assert (
    api_key
), "trufo-api key not found. Set TRUFO_API_KEY or run: trufo set-api-key trufo-api <KEY>"

# --- sign in (loopback first, device flow as fallback) ---

session = TrufoSession()
session.init_session(api_key=api_key)
# Opens a browser on this machine and completes sign-in automatically.
# Without a local browser it falls back to the device flow and prints, e.g.:
#   Visit: https://app.trufo.ai/device?code=ABCD-1234
#   Confirm code: ABCD-1234
# Open the URL in any browser, check the code matches, and approve; the script
# polls until approved.  Pass use_device=True to skip the loopback attempt.

print("Authenticated.")
print(f"Access token: {session.access_token[:20]}...")

# --- persist for future runs ---

save_session(session)
print("Session saved to ~/.trufo/session")

# --- reload in future runs (skips sign-in) ---

# session = load_session()
# data = session.make_request("/some/endpoint", {"key": "value"})
