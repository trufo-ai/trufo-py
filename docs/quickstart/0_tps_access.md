# Quickstart: TPS Access

Step-by-step guide for getting programmatic access to the Trufo Provenance Service (TPS) API.

## Prerequisites

1. **Create an account** at [app.trufo.ai](https://app.trufo.ai).
2. **Set up MFA** — passkey or TOTP is required before API keys can be issued.
3. **Create a TPS API key** at [app.trufo.ai/settings/org](https://app.trufo.ai/settings/org) under *API Keys*, selecting scope **`trufo-api`**.

---

## Step 1 — Store Your API Key

The API key is a 64-character hex string issued by the dashboard. It can be saved via the CLI, set as an environment variable, or persisted to disk directly. The SDK checks the environment variable first, then the file.

**CLI (recommended):**

```bash
trufo set-api-key tps <your-api-key>
# Saved to ~/.trufo/credentials/tps_api_key (mode 0600)
```

**Environment variable:**

```bash
export TRUFO_TPS_API_KEY=<your-api-key>
```

**Load in code:**

```python
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.TPS)
assert api_key, "Set TRUFO_TPS_API_KEY or run: trufo set-api-key tps <KEY>"
```

---

## Step 2 — Authenticate via Device Flow

Most TPS endpoints require an *access token* (Bearer JWT), not the API key directly. The OAuth 2.0 device authorization flow is the supported headless auth method.

**CLI (recommended):**

```bash
trufo login
# Prints something like:
#   Visit: https://app.trufo.ai/device?code=ABCD-1234
#   Enter code: ABCD-1234
# Open the URL in a browser and approve — the CLI polls automatically.
# Tokens are saved to ~/.trufo/session
```

**Python:**

```python
from trufo.api.session import TrufoSession
from trufo.util.credentials import TrufoApiKey, load_api_key, save_session

api_key = load_api_key(TrufoApiKey.TPS)

session = TrufoSession()
session.init_session(api_key=api_key)
# Prints:
#   Visit: https://app.trufo.ai/device?code=ABCD-1234
#   Enter code: ABCD-1234
# Open the URL in a browser and approve — the script polls automatically.

save_session(session)
```

Once approved, `session.access_token` and `session.refresh_token` are set.

---

## Step 3 — Load Session in Subsequent Runs

Once `trufo login` (or `save_session()`) has run once, skip the device flow entirely:

```python
from trufo.util.credentials import load_session

session = load_session()
# Raises RuntimeError if no session is stored or tokens are missing
```

Refresh tokens are valid for **7 days** (server default). Each use of the refresh token issues a new pair, so a session stays alive as long as it is used at least once per week. After 7 days of inactivity, re-run `trufo login`.

---

## Step 4 — Make Requests

```python
data = session.make_request("/some/endpoint", {"key": "value"})
```

`TrufoSession.make_request()` handles token refresh automatically on 401. Each refresh token is single-use; the new pair is stored back on the session object.

For endpoints that accept an API key directly (e.g. the TPS signing endpoint), the key can be passed without a session:

```python
import requests

resp = requests.post(
    "https://api.trufo.ai/test/c2pa/generate",
    json={"media_input": "...", "actions": [], "assertions": []},
    headers={"X-API-Key": api_key},
)
```

---

## Reference

- Endpoint reference: [../api/api_access.md](../api/api_access.md)
- Complete runnable example: [0_tps_access.py](0_tps_access.py)
