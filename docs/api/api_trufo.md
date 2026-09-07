# Trufo Platform API

Authentication, API keys and scopes, and the conventions shared by every Trufo
endpoint: request format, errors, warnings, and regions.

- **Global API:** `https://api.trufo.ai`
- **Europe API:** `https://eu.api.trufo.ai`
- **Test API:** `https://test.api.trufo.ai` (C2PA signing only; see [api_c2pa.md](api_c2pa.md))

---

## Common Declarations

### Every endpoint is POST

The Trufo API is uniformly `POST` with a JSON body, including read operations.
Endpoints that take no parameters accept an empty object `{}`.

### Authentication

Every request must carry exactly one credential:

| Credential | Header | Used by |
| ---------- | ------ | ------- |
| API key | `X-API-Key: {scope}:{key}` | Programmatic access, scoped per product |
| Access token | `Authorization: Bearer {jwt}` | Interactive/session access, obtained via the device flow |

Sending both is rejected with `400 MixedCredentials`. Sending neither is
`401 MissingAuthentication`. TLS 1.3+ is required; plaintext HTTP is rejected.

### Warnings

Some responses carry a `warnings` list alongside a successful result — work Trufo
completed differently than requested, such as a watermark that could not be
embedded under a lenient effort. They are informational, never fatal.

The Python SDK re-emits each as a `TrufoServerWarning` (a `UserWarning` subclass
exported as `trufo.TrufoServerWarning`), so they surface identically across signing
modes and can be caught, filtered, or routed into logging. See
[Response warnings](api_c2pa.md#response-warnings).

### Error envelope

Errors return a JSON object with a stable code in `detail`:

```json
{ "detail": "InsufficientPermissionForAction" }
```

`InsufficientPermissionForAction` additionally carries the permission that was
missing:

```json
{ "detail": "InsufficientPermissionForAction", "action": "create_apikey" }
```

Two deliberate exceptions to the string form: request-shape failures return
FastAPI's `422` validation structure (`detail` is a list of field errors), and the
device-authorization endpoints return the lowercase codes required by RFC 8628
(`authorization_pending`, `access_denied`, `expired_token`).

Errors common to most endpoints:

| Status | `detail` | Meaning |
| ------ | -------- | ------- |
| 400 | `MixedCredentials` | Both an API key and a Bearer token were sent |
| 401 | `MissingAuthentication` | No credential |
| 401 | `MissingToken`, `InvalidToken`, `TokenExpired` | Access-token problem |
| 401 | `InvalidAPIKey`, `APIKeyRevoked`, `APIKeyExpired` | API-key problem |
| 403 | `APIKeyScopeNotAllowed` | The key's scope does not cover this endpoint |
| 403 | `MFARequired` | The operation requires an MFA-verified token |
| 403 | `NotOrgMember`, `InsufficientPermissionForAction` | Org membership or role insufficient |
| 403 | `NoEligiblePlan` | The org lacks an active plan for this operation |
| 422 | *(field list)* | Request body failed schema validation |
| 500 | `Internal server error.` | Unhandled server error |

Every response carries an `X-Request-ID` header — include it when contacting support.

### Organization scoping

Credentials are bound to one organization: an API key belongs to the org it was
created in, and an access token resolves to the caller's org membership. Endpoints
therefore never act cross-org.

### Identifier shapes

| Field | Shape |
| ----- | ----- |
| `oid` | `org_…` — organization, recorded in every signed manifest |
| `api_key` | `{scope}:{key}` |

Other identifiers Trufo returns (disclosure records, software agents, generator
products, instances, credentials) are opaque prefixed strings — pass them back
unchanged.

---

## Regions

Trufo serves two content regions. **The endpoint you call determines where your
content is processed and stored** — there is no per-request region parameter and
no automatic routing between them.

| Data | Scope |
| ---- | ----- |
| Accounts, organizations, API keys | Shared — the same credentials work on either endpoint |
| Media submitted for hosted signing | Processed by the endpoint you call; EU calls stay in EU infrastructure |
| Signing records and watermark IDs | Shared — content signed via either endpoint is recoverable from either |
| Stored assertion records (AI disclosures, software agents) | Regional — a record registered via one endpoint is not visible from the other |
| Request logs | Regional |

Register assertion records on the same endpoint you sign with. An organization's
`default_content_region` setting is a dashboard preference for new work; it does
not restrict which endpoints accept your credentials.

---

## Access Tokens

Interactive and certificate-related endpoints require an access token rather than
an API key. The OAuth 2.0 device authorization flow (RFC 8628) is the supported
headless method and requires a `trufo-api` scoped key.

### `POST /account/device/authorize`

Begin device authorization.

**Auth:** API key (`trufo-api`).
**Request:** `{}`

**Response (200):**

| Field | Type | Description |
| ----- | ---- | ----------- |
| `device_code` | string | Opaque code the client polls with |
| `user_code` | string | Short code the user enters, form `XXXX-XXXX` |
| `verification_uri` | string | Where the user approves |
| `verification_uri_complete` | string | Same, with the code pre-filled |
| `expires_in` | integer | Seconds until the code expires (300) |
| `interval` | integer | Minimum seconds between polls (5) |

### `POST /account/device/token`

Poll for tokens until the user approves.

**Auth:** API key (`trufo-api`).

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `device_code` | string | Yes | From `/account/device/authorize` |

**Response (200):** `access_token`, `refresh_token`.

**Errors:** `400 authorization_pending` (not yet approved — keep polling),
`400 access_denied` (user declined), `400 expired_token` (expired or unknown code).
The device code is single-use.

### `POST /account/refresh`

Exchange a refresh token for a new pair. Each refresh token is single-use and the
previous one is revoked.

| Field | Type | Required |
| ----- | ---- | -------- |
| `refresh_token` | string | Yes |

**Response (200):** `access_token`, `refresh_token`.

**Errors:** `401 InvalidRefreshToken`, `401 TokenExpired`, `401 TokenRevoked`.

Access tokens are short-lived (about two hours for programmatic origins); refresh
tokens last 7 days and are rotated on every use, so a session stays alive as long
as it is used weekly. MFA status carries across refreshes.

### `POST /account/logout`

Revoke a refresh token. Idempotent; the access token remains valid until it expires.

**Auth:** access token. **Request:** `refresh_token` (string, required).

---

## Multi-Factor Authentication

Multi-factor authentication is required on every account before an organization can
issue API keys, and it protects credential and organization management. Enrolment
(TOTP or passkey), recovery codes, and device approval are handled in the dashboard
at [app.trufo.ai](https://app.trufo.ai) — there is nothing to integrate
programmatically.

An access token obtained through the device flow inherits the MFA status of the
approving session, which is what lets it reach protected operations.

---

## Accounts and Organizations

Accounts, organizations, membership and roles, invitations, and Organization
Validation are managed in the dashboard at [app.trufo.ai](https://app.trufo.ai).
They are administrative operations performed once during onboarding rather than
part of a signing integration, so the SDK does not wrap them.

Two facts matter for programmatic use:

- **Every credential is bound to one organization.** An API key belongs to the
  organization it was created in; an access token resolves to the caller's
  organization. Requests never act across organizations.
- **Organization Validation (OV) gates production.** Production C2PA signing and
  production certificate enrollment require completed OV, and your organization's
  validated legal name is what appears in issued certificates and in the automatic
  `ai.trufo.identity` assertion. Until OV completes, production endpoints return
  `403 MissingOrganizationValidation` — use the test host meanwhile.

---

## API Keys

API keys authenticate programmatic access. Each key carries exactly one scope, and
keys are created and revoked in the dashboard under *Settings → API Keys*.

| Scope | Grants | Requires |
| ----- | ------ | -------- |
| `trufo-api` | Device authorization flow | — |
| `c2pa-sign-test` | C2PA signing on the test host | — |
| `c2pa-sign-prod` | C2PA signing on the production hosts | C2PA Signing plan |
| `content-recover-test` | Watermark recovery (`/content/recover`, test host) | — |
| `content-recover-prod` | Watermark recovery (`/content/recover`, production hosts) | C2PA Signing or Watermark API plan |
| `watermark-test` | Standalone binding (`/bind/*`, test host) | — |
| `watermark-prod` | Standalone binding (`/bind/*`, production hosts) | C2PA Signing or Watermark API plan |
| `tsa` | RFC 3161 timestamping (`tsa.trufo.ai`) | C2PA TSA plan |
| `sdk-download` | Downloading the local engine packages from Trufo's private package index | C2PA Signing plan |

Keys are issued as `{scope}:{key}`; Trufo stores only a hash and shows the full key
once, at creation. Keys expire — the dashboard shows each key's expiry and last use.

**Rotation.** Create the replacement key first, move traffic to it, then revoke the
old one. Revocation propagates within the hour.

Store keys with the CLI or environment variables rather than in code — see the
[setup quickstart](../quickstart/0_setup.md).

---

## Reference

- C2PA signing endpoints: [api_c2pa.md](api_c2pa.md)
- Certificates, OCSP, TSA, and the Registration Authority: [api_certs.md](api_certs.md)
- Setup guide: [../quickstart/0_setup.md](../quickstart/0_setup.md)
