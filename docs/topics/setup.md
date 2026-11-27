# Setup and Credentials

Install the Python SDK, configure your API keys, and choose the right host for your environment.

## Install

```bash
pip install trufo
```

The base `trufo` package is pure Python (Python 3.10+) and covers Cloud C2PA signing, Cloud watermarking, watermark recovery, and certificate enrollment.

To keep media on your machine in Local mode, see [Local Signing (Python SDK)](signing-local-python.md) or [Local Signing (Docker)](signing-local-docker.md).

Verify the install:

```bash
python -c "import trufo; print(trufo.__version__)"
```

---

## Hosts

Trufo serves three API hosts:

| Host | Purpose |
| --- | --- |
| `https://api.trufo.ai` | Production (global, SDK default) |
| `https://eu.api.trufo.ai` | Production (Europe) |
| `https://test.api.trufo.ai` | Test host — try signing, watermarking, recovery, and certificate enrollment without Organization Validation or a paid plan |

Key differences on `test.api.trufo.ai`:
- Outputs carry Trufo's test certificate (not trusted by public C2PA validators) and create no permanent signing records.
- Uses `-test` API key scopes (`c2pa-sign-test`, `watermark-test`, `content-recover-test`).
- Supports direct `REQUEST` signing and Local mode, not S3 `TASK` execution.
- `test.api.trufo.ai` does not serve `/ai-system/*` or `/c2pa/software-agent/*`. Send those registrations to a production host (`api.trufo.ai` or `eu.api.trufo.ai`); they accept either test or production keys. AI system registrations are shared across hosts (including test), while software agent records are regional: register them on the production host you sign against.
- `test.api.trufo.ai` does not serve sign-in or token refresh (`/account/*`); it accepts tokens issued by `https://api.trufo.ai`, and `TrufoSession` signs in and refreshes there when it targets the test host.

---

## Dashboard Prerequisites

Create and manage credentials at [app.trufo.ai](https://app.trufo.ai):

1. **Create an account and organization** at [app.trufo.ai/register](https://app.trufo.ai/register).
2. **Set up MFA** (passkey or authenticator app) at [app.trufo.ai/settings/user](https://app.trufo.ai/settings/user).
3. **Create API keys** at [Organization Settings → API Access](https://app.trufo.ai/settings/org#api-access) (for test-host development, steps 1–3 are enough).
4. **For production:** subscribe to the relevant plan, submit [Organization Validation (OV)](https://app.trufo.ai/settings/org/ov), and accept any required [Agreements](https://app.trufo.ai/settings/org#agreements) (*Trufo Library License* for `sdk-download`, *Created Assertion Acknowledgement* for first-party AI labeling).

---

## Storing API Keys

Trufo shows each newly created API key once, already formatted as `{scope}:{key}` (do not prepend the scope a second time). Store keys in environment variables (recommended for servers and CI) or locally via `trufo set-api-key`. When loading a key, the SDK checks environment variables first, then `~/.trufo/credentials/`.

**Environment variables (recommended for deployments):**

```bash
export TRUFO_C2PA_SIGN_TEST_API_KEY=<your-c2pa-sign-test-key>
export TRUFO_C2PA_SIGN_PROD_API_KEY=<your-c2pa-sign-prod-key>
export TRUFO_WATERMARK_TEST_API_KEY=<your-watermark-test-key>
export TRUFO_WATERMARK_PROD_API_KEY=<your-watermark-prod-key>
export TRUFO_CONTENT_RECOVER_TEST_API_KEY=<your-content-recover-test-key>
export TRUFO_CONTENT_RECOVER_PROD_API_KEY=<your-content-recover-prod-key>
export TRUFO_TSA_API_KEY=<your-tsa-key>
export TRUFO_API_KEY=<your-trufo-api-key>
```

| Variable | Key scope | Read by |
| --- | --- | --- |
| `TRUFO_C2PA_SIGN_TEST_API_KEY` / `TRUFO_C2PA_SIGN_PROD_API_KEY` | `c2pa-sign-test` / `c2pa-sign-prod` | `load_api_key()` |
| `TRUFO_WATERMARK_TEST_API_KEY` / `TRUFO_WATERMARK_PROD_API_KEY` | `watermark-test` / `watermark-prod` | `load_api_key()` |
| `TRUFO_CONTENT_RECOVER_TEST_API_KEY` / `TRUFO_CONTENT_RECOVER_PROD_API_KEY` | `content-recover-test` / `content-recover-prod` | `load_api_key()` |
| `TRUFO_TSA_API_KEY` | `tsa` | `load_api_key()` |
| `TRUFO_API_KEY` | `trufo-api` | `load_api_key()`, `trufo login` |
| `TRUFO_ACCESS_TOKEN` + `TRUFO_REFRESH_TOKEN` | Session tokens (set both or neither) | `load_session()` (checked before `~/.trufo/session`) |
| `TRUFO_SDK_DOWNLOAD_API_KEY` | `sdk-download` | The `trufo-local` Docker image at startup (see [Local Signing (Docker)](signing-local-docker.md)); for `pip`, put the key in `~/.netrc` instead (see [Local Signing (Python SDK)](signing-local-python.md)) |
| `TRUFO_API_URL` | — | The `trufo-local` Docker image only (defaults to `https://api.trufo.ai`). Python SDK functions do not read it; pass `trufo_api_url=...` explicitly |

**Local credential store:**

```bash
trufo set-api-key c2pa-sign-test <your-api-key>
trufo set-api-key c2pa-sign-prod <your-api-key>
trufo set-api-key watermark-test <your-api-key>
trufo set-api-key watermark-prod <your-api-key>
trufo set-api-key content-recover-test <your-api-key>
trufo set-api-key content-recover-prod <your-api-key>
trufo set-api-key tsa <your-api-key>
trufo set-api-key trufo-api <your-api-key>
# Saved to ~/.trufo/credentials/<scope>_api_key, hyphens as underscores (e.g., trufo_api_key); mode 0600 on POSIX
```

Load a key in Python:

```python
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_TEST)
assert api_key, "Set TRUFO_C2PA_SIGN_TEST_API_KEY or run: trufo set-api-key c2pa-sign-test <KEY>"
```

See [Platform API — API Keys](../reference/platform-api.md#api-keys) for every scope, what it grants, and rotation rules.

---

## Direct HTTP Requests

Any language can call Trufo's REST API directly over TLS 1.3+ using `X-API-Key`:

```python
import requests
from trufo.util.credentials import TrufoAPIKey, load_api_key

test_key = load_api_key(TrufoAPIKey.C2PA_SIGN_TEST)
resp = requests.post(
    "https://test.api.trufo.ai/c2pa/sign",
    json={"media_input": "<base64-bytes>", "actions": [], "assertions": []},
    headers={"X-API-Key": test_key},
    timeout=60,
)
resp.raise_for_status()
```

---

## Interactive Sessions (Registration Authority Endpoints)

Certificate management endpoints (`/gproduct/instance/*`, `/cert/revoke`, etc.) require an MFA-verified user access token (`Authorization: Bearer <jwt>`) rather than an API key. Obtain and save one using your `trufo-api` key:

```python
from trufo.api.session import TrufoSession
from trufo.util.credentials import TrufoAPIKey, load_api_key, save_session

api_key = load_api_key(TrufoAPIKey.TRUFO_API)

session = TrufoSession()
session.init_session(api_key=api_key)
# Opens a browser sign-in on this machine, or falls back to the device flow.
save_session(session)
```

On headless hosts, over SSH, or in containers, use the device code flow directly: `trufo login --device` on the CLI, or `session.init_session(api_key=api_key, use_device=True)` in Python. This avoids a browser opening on the wrong machine.

Load the saved session in subsequent runs:

```python
from trufo.util.credentials import load_session

session = load_session()  # automatically refreshes tokens on 401 and persists the new pair
```

`load_session()` always targets `https://api.trufo.ai`. For the Europe or test host, set `session.base_api_url` after loading (or construct `TrufoSession(base_api_url=..., access_token=..., refresh_token=...)` yourself). Sign-in and refresh still run on `https://api.trufo.ai` when the session targets `test.api.trufo.ai`.

`TrufoSession.make_request()` sends authenticated `POST` requests with a JSON body. For the few `GET` and `multipart/form-data` endpoints (see [HTTP Conventions](../reference/platform-api.md#http-conventions)), use any HTTP client with `Authorization: Bearer <session.access_token>`.

Refresh tokens last **7 days** and rotate on every use, so a session stays active while used at least once a week.

---

## Region Selection

Pass `TRUFO_API_URL_EUROPE` explicitly whenever you want Cloud-mode processing to run in EU infrastructure:

```python
from trufo import sign_c2pa_cloud
from trufo.api.endpoints import TRUFO_API_URL_EUROPE

signed_bytes = sign_c2pa_cloud(api_key, media_bytes, trufo_api_url=TRUFO_API_URL_EUROPE)
```

For `TrufoSession`:

```python
from trufo.api.endpoints import TRUFO_API_URL_EUROPE
from trufo.api.session import TrufoSession

session = TrufoSession(base_api_url=TRUFO_API_URL_EUROPE)
```

For `trufo-local` Docker, set the `TRUFO_API_URL` environment variable to `https://eu.api.trufo.ai` instead.

---

## Reference

- Platform auth, API keys, regions, and error envelope: [Platform API](../reference/platform-api.md)
- Complete runnable script: [setup.py](setup.py)
