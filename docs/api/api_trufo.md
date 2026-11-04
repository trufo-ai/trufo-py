# Trufo Platform API

Authentication, API keys and scopes, and the conventions shared by every Trufo
endpoint: request format, errors, warnings, and regions.

- **Global API:** `https://api.trufo.ai`
- **Europe API:** `https://eu.api.trufo.ai`
- **Test API:** `https://test.api.trufo.ai` (C2PA signing, watermark recovery and standalone binding; see [api_c2pa.md](api_c2pa.md))

---

## Common Declarations

### Every endpoint is POST, except task status

The Trufo API is `POST` with a JSON body, including read operations; the one
exception is `GET /tasks/{task_id}`. Endpoints that take no parameters accept an
empty object `{}`.

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
embedded under a lenient effort, or a [deprecation](#deprecations) notice. They
are informational, never fatal.

The Python SDK re-emits each as a `TrufoServerWarning` (a `UserWarning` subclass
exported as `trufo.TrufoServerWarning`), and in Local mode the engine emits each as a
`UserWarning`, so they can be caught, filtered, or routed into logging. See
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

### Deprecations

<!-- TODO(sunset-2027-01-31): this paragraph and the next table go; successor none -->

The four deprecations below keep working until 2027-01-31T00:00:00+00:00 (the
start of 31 January 2027, UTC) and fail from that instant. Sign and bind
requests get a notice in `warnings`; the `/c2pa/ai-disclosure/*` endpoints
signal through headers only.

| Deprecated | Replacement | After 2027-01-31T00:00:00+00:00 | Who must act |
| ---------- | ----------- | ------------------------------- | ------------ |
| The [`ai_disclosure`](api_c2pa.md#ai_disclosure) entry | The [`ai_system`](api_c2pa.md#ai_system) entry | 400 `UnsupportedAssertion: …` | Sign requests that send it |
| [`POST /c2pa/ai-disclosure/add`, `/list`](api_c2pa.md#post-c2paai-disclosureadd) | [`POST /ai-system/add`, `/list`](api_c2pa.md#ai-systems) | 410 | Their callers |
| The watermark [`mode`](api_c2pa.md#watermark) | `wid_allocation_mode` (`per_embed` replaces `provenance`) | 400 `UnsupportedParameter: …` | Requests that send it, including every `/bind/watermark` call from trufo 2.1 or earlier, which always sends `mode` and does not show the notice |
| [Local mode](api_c2pa.md#local-mode) with trufo-provenance 2.1.x | trufo-provenance 2.2.0 or later | 400 `UnsupportedSDKVersion: …` | trufo 2.1 with a local engine extra, and the [Docker image](../local/docker.md#versions-and-upgrades)'s 2.1 tags |

<!-- TODO(sunset-2026-12-31): the next paragraph goes; successor none -->

Local mode with trufo-provenance 2.0.x or earlier (from 0.3.0, the supported
minimum) gets the same notice and error, but fails from
2026-12-31T00:00:00+00:00; users of trufo 2.0 or earlier with a local engine
extra must act.

Deprecated responses can carry these headers:

| Header | Value |
| ------ | ----- |
| `Deprecation` | `@<Unix time>` (RFC 9745): when the deprecation took effect |
| `Sunset` | An HTTP-date (RFC 8594): the date after which the request fails |
| `Link` | `<URL>; rel="successor-version"`: what replaces it |

<!-- TODO(sunset-2027-01-31): the two ai_disclosure rows go; successor none -->

| Response | Headers |
| -------- | ------- |
| [`/c2pa/ai-disclosure/add`, `/list`](api_c2pa.md#post-c2paai-disclosureadd): every 201 or 200, and their 410 from 2027-01-31T00:00:00+00:00 | `Deprecation`, `Sunset`, `Link` |
| A sign that uses the [`ai_disclosure`](api_c2pa.md#ai_disclosure) entry: REQUEST (200), TASK (202) and Local mode | `Deprecation`, `Sunset` |
| A test key's 410 in [Local mode](api_c2pa.md#signing-modes) on a production host | `Deprecation`, and `Link` to the same path on the test host |
| A test key's 410 on a production host's [upload link](api_c2pa.md#post-ioget-s3-upload-url) | `Deprecation` |
| The 410 of the legacy `POST /test/c2pa/sign` on a production host | `Deprecation`, and `Link` to `/c2pa/sign` on the test host |

The watermark `mode` and SDK-version notices carry no headers.

The test-key 410s apply without a notice period and to every SDK version, since
the server refuses them: the production hosts refuse test keys in Local mode and
on the upload link, and accept them on their registration endpoints.

### Organization scoping

Credentials are bound to one organization: an API key belongs to the org it was
created in, and an access token resolves to the caller's org membership. Endpoints
therefore never act cross-org.

### Identifier shapes

| Field | Shape |
| ----- | ----- |
| `oid` | `org_…` — organization, recorded in every signed manifest |
| `api_key` | `{scope}:{key}` |
| `ai_system_id` | `aisys_…` — AI system, from [`POST /ai-system/add`](api_c2pa.md#post-ai-systemadd) |

<!-- TODO(sunset-2027-01-31): "disclosure records" goes from the next paragraph; successor none -->

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
| Media submitted in Cloud mode | Processed by the endpoint you call; EU calls stay in EU infrastructure |
| Signing records and watermark IDs | Shared — content signed via either endpoint is recoverable from either |
| AI systems | Shared — an AI system registered via either endpoint works on either |
| Stored assertion records (deprecated AI disclosures, software agents) | Regional — a record registered via one endpoint is not visible from the other <!-- TODO(sunset-2027-01-31): "deprecated AI disclosures" goes; successor AI systems --> |
| Request logs | Regional |

Register stored assertion records on the same endpoint you sign with. An organization's
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
  `ai.trufo.identity` assertion. An owner or admin with MFA submits OV at
  [app.trufo.ai/settings/org/ov](https://app.trufo.ai/settings/org/ov), and Trufo
  reviews it. Until OV completes, production endpoints return
  `403 MissingOrganizationValidation` — use the test host meanwhile.

### Agreements

An organization owner or admin accepts agreements for the organization at
[Organization Settings → Agreements](https://app.trufo.ai/settings/org#agreements).
These features each need one:

| Agreement | Required for |
| --------- | ------------ |
| Trufo Library License | Creating `sdk-download` keys |
| Created Assertion Acknowledgement | Registering [first-party AI systems](api_c2pa.md#post-ai-systemadd) |

---

## API Keys

API keys authenticate programmatic access. Each key carries exactly one scope. An
organization owner or admin with MFA creates and revokes keys at
[Organization Settings → API Access → API Keys](https://app.trufo.ai/settings/org#api-access).

| Scope | Grants | Requires |
| ----- | ------ | -------- |
| `trufo-api` | Device authorization flow | — |
| `c2pa-sign-test` | C2PA signing on the test host, and the [AI system endpoints](api_c2pa.md#ai-systems) on the production hosts, which refuse it for Local mode and the upload link (410, [Deprecations](#deprecations)) | — |
| `c2pa-sign-prod` | C2PA signing and the [AI system endpoints](api_c2pa.md#ai-systems) on the production hosts | C2PA Signing plan |
| `content-recover-test` | Watermark recovery (`/content/recover`, test host) | — |
| `content-recover-prod` | Watermark recovery (`/content/recover`, production hosts) | C2PA Signing or Watermark API plan |
| `watermark-test` | Standalone binding (`/bind/*`, test host); the production hosts' upload link refuses it (410, [Deprecations](#deprecations)) | — |
| `watermark-prod` | Standalone binding (`/bind/*`, production hosts) | C2PA Signing or Watermark API plan |
| `tsa` | RFC 3161 timestamping (`tsa.trufo.ai`) | C2PA TSA plan |
| `sdk-download` | Downloading the local engine packages from Trufo's private package index, for the [Python SDK](../local/python.md) or the [Docker image](../local/docker.md) | C2PA Signing or Watermark API plan, and the Trufo Library License accepted ([Agreements](#agreements)) |

Keys are issued as `{scope}:{key}`; Trufo stores only a hash and shows the full key
once, at creation. Keys last up to 390 days — the dashboard shows each key's expiry
and last use.

**Rotation.** Create the replacement key first, move traffic to it, then revoke the
old one. Revocation propagates within the hour.

Store keys with the CLI or environment variables rather than in code — see the
[setup quickstart](../quickstart/0_setup.md).

---

## Reference

- C2PA signing endpoints: [api_c2pa.md](api_c2pa.md)
- Certificates, OCSP, TSA, and the Registration Authority: [api_certs.md](api_certs.md)
- Setup guide: [../quickstart/0_setup.md](../quickstart/0_setup.md)
