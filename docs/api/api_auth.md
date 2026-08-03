# API Auth

Documentation for programmatic access to Trufo Provenance Service (TPS) API endpoints. For a quick setup guide, see the [Auth Quickstart](../quickstart/0_auth.md) page.

## Base URLs

| Service                    | URL                          | Description                     |
| -------------------------- | ---------------------------- | ------------------------------- |
| TPS API (Global-sync)      | `https://api.trufo.ai`       | Trufo API                       |
| TPS API (Europe-only)      | `https://eu.api.trufo.ai`    | Trufo API (Europe)              |
| TPS API (test)             | `https://test.api.trufo.ai`  | [test] Trufo API                |
| Certificate Authority      | `https://ca.trufo.ai`        | [CA] EST enrollment (RFC 7030)  |
| Timestamp Authority        | `https://tsa.trufo.ai`       | [CA] Timestamping (RFC 3161)    |
| Timestamp Authority (test) | `https://test.tsa.trufo.ai`  | [test] Timestamping (RFC 3161)  |
| OCSP Responder             | `https://ocsp.trufo.ai`      | [CA] OCSP stapling              |
| Package Index              | `https://packages.trufo.ai`  | [SDK] Private wheel index       |

Test and regional variants follow one convention: `{qualifier}.{service}.trufo.ai` (e.g. `test.api`, `eu.api`, `test.tsa`). The legacy test-TSA name `tsa.test.trufo.ai` remains available during deprecation.

## Regional Endpoints

The SDK defaults to `https://api.trufo.ai`. To restrict processing to the dedicated EU server, please call `https://eu.api.trufo.ai`. When using the dedicated EU server, sensitive content data will be stored in dedicated EU clusters per our DPA and TIA. Other endpoints will route to the nearest server. Users have the option to select, per API request, which endpoint to hit; please note that certain types of data will or will not be available cross-region.

The recommended method to target the dedicated EU server for a login session is:

```python
from trufo.api.endpoints import TRUFO_API_URL_EUROPE
from trufo.api.session import TrufoSession

session = TrufoSession(base_api_url=TRUFO_API_URL_EUROPE)
```

When using other function calls within the SDK, you will want to set `trufo_api_url` to be `TRUFO_API_URL_EUROPE`, for example:

```python
from trufo.api.endpoints import TRUFO_API_URL_EUROPE
from trufo.api.tps.sign_c2pa import sign_c2pa

signed_bytes = sign_c2pa(
  api_key,
  media_bytes,
  trufo_api_url=TRUFO_API_URL_EUROPE,
)
```

Direct API calls should also use the corresponding URL.

## API Headers

All requests to the TPS (except for OCSP) require authentication. Some endpoints require an access token while other endpoints require an API key. See individual endpoint docs for specifics.

**Access token** — included via the `Authorization` header as a Bearer token:

```
Authorization: Bearer eyJhbG...
```

**Full example:**

```
POST /endpoint HTTP/1.1
Host: api.trufo.ai
Content-Type: application/json
Authorization: Bearer eyJhbG...

{ "field": "value" }
```

All requests must be made over TLS 1.3+ (HTTPS). Plaintext HTTP connections are rejected.

Error responses return a JSON object with a `detail` field:

```json
{ "detail": "ErrorCode" }
```

The main exceptions to the standard `Authorization: Bearer` auth are:

- Device authorization flow (API key only). See below.
- CSR JWT issuance via client assertion. See [tca_ra.md](tca_ra.md).
- TCA endpoints (EST, TSA, OCSP). See [tca_ca.md](tca_ca.md).

## API Key Scopes

Every API key is issued with a single scope. The scope determines which endpoints the key can call.

| Scope            | Used for                                                            |
| ---------------- | ------------------------------------------------------------------- |
| `trufo-api`      | Device authorization flow & administrative actions                  |
| `c2pa-sign-prod` | C2PA & CAWG signing (production hosts)                              |
| `c2pa-sign-test` | C2PA & CAWG signing (test host `test.api.trufo.ai`)                 |
| `tsa`            | RFC 3161 timestamping (`tsa.trufo.ai`)                              |
| `c2pa-decode`    | Watermark decoding & recovery of provenance (`/content/recover`)    |
| `sdk-download`   | Private package index downloads (the `PIP_EXTRA_INDEX_URL` credential for `packages.trufo.ai`) |

Create keys at [app.trufo.ai/settings/org](https://app.trufo.ai/settings/org) under *API Keys*. Note that the keys will be of the form `{scope}:{key}` for readability.

## Access Token

The TPS supports OAuth 2.0 device authorization flow for headless environments. Both steps require a `trufo-api` scoped key, included via the `X-API-Key` header:

```
X-API-Key: trufo-api:...
```

### Step 1 — `POST /account/device/authorize`

Initiate device authorization.

**Auth:** API key (`trufo-api` scope).

**Request body:** `{}`

**Response (200):**

```json
{
  "device_code": "abc123...",
  "user_code": "ABCD-1234",
  "verification_uri": "https://app.trufo.ai/device",
  "verification_uri_complete": "https://app.trufo.ai/device?code=ABCD-1234",
  "expires_in": 300,
  "interval": 5
}
```

### Step 2 — User Approval

The user visits `verification_uri_complete` in a browser and approves the device.

### Step 3 — `POST /account/device/token`

Poll for tokens. The device polls until the user approves or the code expires.

**Auth:** API key (`trufo-api` scope).

```json
{
  "device_code": "abc123..."
}
```

**Response (approved — 200):**

```json
{
  "access_token": "eyJhbG...",
  "refresh_token": "eyJhbG..."
}
```

**Response (pending — 400):**

```json
{
  "detail": "authorization_pending"
}
```

**Errors:**

| Code | Detail                  | Description               |
| ---- | ----------------------- | ------------------------- |
| 400  | `authorization_pending` | User has not yet approved |
| 400  | `expired_token`         | Device code expired       |
| 400  | `access_denied`         | User denied the request   |
| 404  | `DeviceCodeNotFound`    | Invalid device code       |

### Python SDK

```python
from trufo.api.session import TrufoSession

session = TrufoSession()
session.init_session(api_key="trufo-api:...")
# Prints verification URL, then polls automatically
```

## Token Refresh

### `POST /account/refresh`

Exchange a refresh token for a new access + refresh token pair. Each refresh token is single-use.

**Auth:** None (the refresh token itself is the credential).

```json
{
  "refresh_token": "eyJhbG..."
}
```

**Response (200):**

```json
{
  "access_token": "eyJhbG...",
  "refresh_token": "eyJhbG..."
}
```

**Errors:**

| Code | Detail                | Description        |
| ---- | --------------------- | ------------------ |
| 401  | `InvalidRefreshToken` | Token is malformed |
| 401  | `TokenExpired`        | Token has expired  |
| 401  | `TokenRevoked`        | Token was revoked  |

## TrufoSession

`TrufoSession` provides authenticated API access with automatic token refresh on 401.

### New Login

```python
from trufo.api.session import TrufoSession

session = TrufoSession()
session.init_session(api_key="trufo-api:...")

# Make authenticated requests
data = session.make_request("/some/endpoint", {"key": "value"})
```

### Existing Tokens

```python
session = TrufoSession(access_token="...", refresh_token="...")
data = session.make_request("/some/endpoint", {"key": "value"})
```

### Credential Persistence

Session tokens and API keys can be persisted to `~/.trufo/` via the `trufo.util.credentials` module:

```python
from trufo.util.credentials import TrufoApiKey, load_api_key, load_session, save_session

# Load a trufo-api key (env var or ~/.trufo/credentials/trufo_api_key)
api_key = load_api_key(TrufoApiKey.TRUFO_API)

# Load a c2pa-sign-prod / c2pa-sign-test key
prod_key = load_api_key(TrufoApiKey.C2PA_SIGN_PROD)
test_key = load_api_key(TrufoApiKey.C2PA_SIGN_TEST)

# Load a tsa key
tsa_key = load_api_key(TrufoApiKey.TSA)

# Load a c2pa-decode key
decode_key = load_api_key(TrufoApiKey.C2PA_DECODE)

# Load saved session (env vars or ~/.trufo/session)
# Raises RuntimeError if no session is configured
session = load_session()

# Save session after login
save_session(session)
```

See `src/trufo/util/credentials.py` for the full credential storage layout and environment variables.

---

For a step-by-step setup guide and runnable examples, see `docs/quickstart/0_auth.md`.