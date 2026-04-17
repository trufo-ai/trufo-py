# API Access

Instructions on setting up programmatic access to Trufo Provenance Service (TPS) API endpoints.

## Base URLs

| Service | URL | Description |
|---------|-----|-------------|
| TPS API | `https://api.trufo.ai` | Trufo Provenance Service |
| Certificate Authority | `https://ca.trufo.ai` | CA, EST enrollment (RFC 7030) |
| Timestamp Authority | `https://tsa.trufo.ai` | CA, timestamping (RFC 3161) |
| OCSP Responder | `https://ocsp.trufo.ai` | CA, OCSP stapling |

## Setup

To get access, you must first create an API key on the (Trufo dashboard)[app.trufo.ai/settings/org] after setting up MFA (passkey or TOTP) for your account. Currently, only fixed-scope organization-level API keys are supported:

| Name | Scope |
|------|-------|
| Trufo API | usage of TPS API endpoints |
| Time Stamping | usage of the TSA timestamper |

In `src/trufo/api/` there are a number of helper functions that have all the API queries pre-configured within Python functions. The documentation of these helper functions for API access is included here, but is not included in other `docs/api/*.md` files. Please have your AI agent read the source code or alternatively, check out `examples/` or `tests/` for inspiration.

## API Headers

All requests to the TPS require authentication. Most endpoints require an access token; the device authorization flow requires the TPS API key instead. See individual endpoint docs for specifics.

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

## Access Token

The TPS supports OAuth 2.0 device authorization flow for headless environments. Both steps require a TPS API key, included via the `X-API-Key` header:

```
X-API-Key: tk_...
```

### Step 1 — `POST /account/device/authorize`

Initiate device authorization.

**Auth:** API key (trufo-api).

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

**Auth:** API key (trufo-api).

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

| Code | Detail | Description |
|------|--------|-------------|
| 400 | `authorization_pending` | User has not yet approved |
| 400 | `expired_token` | Device code expired |
| 400 | `access_denied` | User denied the request |
| 404 | `DeviceCodeNotFound` | Invalid device code |

### Python SDK

```python
from trufo.api.session import TrufoSession

session = TrufoSession()
session.init_session(api_key="tk_...")
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

| Code | Detail | Description |
|------|--------|-------------|
| 401 | `InvalidRefreshToken` | Token is malformed |
| 401 | `TokenExpired` | Token has expired |
| 401 | `TokenRevoked` | Token was revoked |

## TrufoSession

`TrufoSession` provides authenticated API access with automatic token refresh on 401.

### New Login

```python
from trufo.api.session import TrufoSession

session = TrufoSession()
session.init_session(api_key="tk_...")

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

# Load TPS API key (env var or ~/.trufo/credentials/tps_api_key)
api_key = load_api_key(TrufoApiKey.TPS)

# Load TSA API key (env var or ~/.trufo/credentials/tsa_api_key)
tsa_key = load_api_key(TrufoApiKey.TSA)

# Load saved session (env vars or ~/.trufo/session)
# Raises RuntimeError if no session is configured
session = load_session()

# Save session after login
save_session(session)
```

See `src/trufo/util/credentials.py` for the full credential storage layout and environment variables.
