# Platform API Reference

Normative specification for Trufo HTTP conventions, hosts, regions, authentication, API key scopes, error envelopes, and interactive token endpoints.

- **Global API:** `https://api.trufo.ai`
- **Europe API:** `https://eu.api.trufo.ai`
- **Test API:** `https://test.api.trufo.ai` (C2PA signing in direct REQUEST and Local modes, watermark recovery, standalone binding, and certificate test flow)

---

## HTTP Conventions

- **Method:** Nearly every endpoint is `POST` with a JSON body (including reads); exceptions are `GET /tasks/{task_id}`, `GET /gproduct/pv/draft`, and `GET /gproduct/bpv/draft`, plus file-upload endpoints (`/org/ov/upload`, `/gproduct/pv/upload`, `/gproduct/bpv/upload`) which take `multipart/form-data`. Parameterless `POST` endpoints accept `{}`.
- **Transport:** TLS 1.3 or later is required; plaintext HTTP is rejected.
- **Request ID:** Every response carries an `X-Request-ID` header — include it when contacting [support@trufo.ai](mailto:support@trufo.ai).
- **Organization scoping:** Every API key, and every access token once its account belongs to an organization, is bound to a single organization (`org_...`). Endpoints never act cross-organization. An account with no organization yet can still sign in and call `POST /org/create` or `POST /org/invite/accept`, which return fresh tokens bound to the new organization.

### Authentication

Send **exactly one** credential per request:

| Credential | Header | Used for |
| --- | --- | --- |
| API key | `X-API-Key: {scope}:{key}` | Programmatic endpoints, scoped per product |
| Access token | `Authorization: Bearer {jwt}` | Account, organization, API key, billing, validation draft, and RA endpoints (obtained via `trufo login` / device flow) |

Sending both returns `400 MixedCredentials`. Sending neither returns `401 MissingAuthentication`.

### Warnings

Successful responses can carry a `warnings` array of non-fatal notices (e.g., skipped watermark under lenient effort, metadata dropped by a media action, untrusted incoming manifest, or deprecation notice). The Python SDK emits each notice as `trufo.TrufoServerWarning` (a subclass of `UserWarning`) in both Cloud and Local modes.

### Error Envelope

Errors return JSON with a stable code or message in `detail`:

```json
{ "detail": "InsufficientPermissionForAction", "action": "create_apikey" }
```

Two exceptions:
- Request-shape failures return HTTP `422` with `detail` as a list of `{type, loc, msg}` field errors.
- Device-authorization and loopback-token endpoints return RFC 8628 / RFC 6749 lowercase codes (`authorization_pending`, `access_denied`, `expired_token`, `invalid_grant`).

| Status | `detail` | Meaning |
| --- | --- | --- |
| 400 | `MixedCredentials` | Both `X-API-Key` and `Authorization: Bearer` were sent |
| 401 | `MissingAuthentication` | No credential |
| 401 | `MissingToken`, `InvalidToken`, `TokenExpired`, `OrgMembershipRevoked` | Access-token failure |
| 401 | `InvalidAPIKey`, `APIKeyRevoked`, `APIKeyExpired` | API-key failure |
| 403 | `APIKeyScopeNotAllowed` | Key scope does not cover this endpoint |
| 403 | `MFARequired` | Operation requires an MFA-verified session |
| 403 | `NotOrgMember`, `InsufficientPermissionForAction` | Organization membership or role insufficient |
| 403 | `WorkingOrgRequired`, `ManagementOrgRequired`, `BillingOrgRequired` | Organization type does not support this action |
| 403 | `NoEligiblePlan` | Organization lacks an active plan for this operation |
| 422 | *(field list)* | Request body failed schema validation |
| 500 | `Internal server error.` | Unhandled server error |

### Identifier Shapes

- `oid`: `org_...` (recorded in every signed manifest under `ai.trufo.identity`)
- `api_key`: `{scope}:{key}`
- `ai_system_id`: `aisys_...`
- Other IDs (`gp_...`, `gpi_...`, `gpic_...`, `swagent_...`, `cid`, `wid`, `task_id`) are opaque strings — pass them back unchanged.

---

## Regions

The API host you call determines where Cloud-mode content is processed. There is no per-request region parameter and no automatic cross-region routing.

| Data | Scope |
| --- | --- |
| Accounts, organizations, API keys | Shared — credentials work on either production endpoint |
| Generator products, instances, certificates, OV, PV/BPV, domain validation, billing | Shared — managed identically from `api.trufo.ai` or `eu.api.trufo.ai` |
| Cloud-mode media processing | Regional — calls to `eu.api.trufo.ai` stay in EU infrastructure |
| Cloud S3 uploads (`/io/get-s3-upload-url`, `TASK` mode) | Regional — upload, submit, and poll against the same endpoint |
| Signing records and watermark IDs | Shared — content signed via either endpoint is recoverable from either |
| AI systems (`/ai-system/*`) | Shared — registered once, usable on every endpoint (including test) |
| Software agent records (`/c2pa/software-agent/*`) | Regional — register on the same endpoint you sign against |
| Request logs | Regional |
| CA (`ca.trufo.ai`), OCSP (`ocsp.trufo.ai`), shared TSA (`tsa.trufo.ai`) | Global — dedicated TSA endpoints (including EU capacity) are available via [support@trufo.ai](mailto:support@trufo.ai) |

An organization's `default_content_region` setting applies to dashboard workflows only; it does not restrict which API host accepts your credentials.

---

## API Keys

API keys are created and revoked by an MFA-verified owner or admin in [Organization Settings → API Access](https://app.trufo.ai/settings/org#api-access) or via the [`/apikey/*` endpoints](account-and-org-api.md#api-keys). Full keys (`{scope}:{key}`) are shown once at creation and expire after up to **390 days**. Revocation propagates within one hour.

| Scope | Grants | Requires |
| --- | --- | --- |
| `trufo-api` | Sign-in for interactive sessions: device authorization flow (`/account/device/*`) and browser loopback login (`/account/loopback/token`) | — |
| `c2pa-sign-test` | `/c2pa/sign` on `test.api.trufo.ai`; `/ai-system/*` and `/c2pa/software-agent/*` on production hosts | — |
| `c2pa-sign-prod` | `/c2pa/sign`, `/io/get-s3-upload-url`, `/tasks/{task_id}`, `/content/{get,list,status}`, `/ai-system/*`, `/c2pa/software-agent/*` on production hosts | C2PA Signing plan |
| `watermark-test` | `/bind/*` on `test.api.trufo.ai`; `/ai-system/*` on production hosts | — |
| `watermark-prod` | `/bind/*`, `/io/get-s3-upload-url`, `/tasks/{task_id}`, `/content/{get,list,status}`, `/ai-system/*` on production hosts | C2PA Signing or Watermark API plan |
| `content-recover-test` | `/content/recover` on `test.api.trufo.ai` | — |
| `content-recover-prod` | `/content/recover` on production hosts | C2PA Signing or Watermark API plan |
| `tsa` | RFC 3161 timestamping on `tsa.trufo.ai` (or dedicated TSA host) | C2PA TSA plan |
| `sdk-download` | Downloading local engine wheels from `packages.trufo.ai` (Python SDK extras and Docker image) | C2PA Signing or Watermark API plan (or test SDK access from support@trufo.ai) + Trufo Library License |

---

## Agreements and Organization Validation

Managed in [app.trufo.ai](https://app.trufo.ai) by an MFA-verified owner or admin:

- **Organization Validation (OV):** Required for production signing, standalone binding, and certificate enrollment (`403 MissingOrganizationValidation` or `403 OVNotActive` until active).
- **Trufo Library License:** Required before creating `sdk-download` keys.
- **Created Assertion Acknowledgement:** Required before registering first-party AI systems (`c2pa_first_party_attestable: true`).

---

## Access Tokens (Device Authorization Flow)

Interactive and Registration Authority endpoints require an MFA-verified `Authorization: Bearer <jwt>` access token. Access tokens last ~2 hours; refresh tokens last **7 days** and rotate on every use (single-use). MFA status carries across refreshes.

Sign-in and refresh (`/account/device/*`, `/account/loopback/token`, `/account/refresh`) are served by both production hosts. `test.api.trufo.ai` does not serve them: it accepts tokens issued by `https://api.trufo.ai`, and `TrufoSession` signs in and refreshes there when it targets the test host.

`trufo login` (and `TrufoSession.init_session()`) uses browser loopback login on the local machine and falls back to the device flow when no browser is available; `trufo login --device` (`use_device=True`) forces the device flow for headless hosts. `TrufoSession.make_request()` sends `POST` with a JSON body only; call the `GET` draft endpoints and `multipart/form-data` upload endpoints with any HTTP client and `Authorization: Bearer <access_token>`.

### `POST /account/device/authorize`

**Auth:** `X-API-Key` (`trufo-api`). **Request:** `{}`.

**Response (200):** `device_code`, `user_code` (`XXXX-XXXX`), `verification_uri`, `verification_uri_complete`, `expires_in` (`300`), `interval` (`5`).

### `POST /account/device/token`

**Auth:** `X-API-Key` (`trufo-api`). **Request:** `{"device_code": "<string>"}`.

**Response (200):** `{"access_token": "...", "refresh_token": "..."}`.

**Errors:** `400 authorization_pending`, `400 access_denied`, `400 expired_token`.

### `POST /account/loopback/token`

**Auth:** `X-API-Key` (`trufo-api`). **Request:** `{"code": "<string>", "code_verifier": "<string>", "redirect_uri": "<string>"}` (RFC 8252 loopback redirect with PKCE; used by `trufo login`).

**Response (200):** `{"access_token": "...", "refresh_token": "..."}`.

**Errors:** `400 invalid_grant` (unknown, expired, or already-used code, or mismatched `code_verifier` / `redirect_uri`).

### `POST /account/refresh`

**Auth:** None (refresh token in body). **Request:** `{"refresh_token": "<string>"}`.

**Response (200):** `{"access_token": "...", "refresh_token": "..."}` (previous refresh token is revoked).

**Errors:** `401 InvalidRefreshToken`, `401 TokenExpired`, `401 TokenRevoked`.

### `POST /account/logout`

**Auth:** `Authorization: Bearer <jwt>`. **Request:** `{"refresh_token": "<string>"}`. Idempotent; revokes the refresh token immediately.

---

## Related References

- Account, Organization, and Billing API: [account-and-org-api.md](account-and-org-api.md)
- Signing & Tasks: [signing-api.md](signing-api.md)
- Actions & Assertions: [actions-and-assertions.md](actions-and-assertions.md)
- Watermarking & Content Records: [watermarking-api.md](watermarking-api.md)
- Certificates, TSA, and OCSP: [certificates-api.md](certificates-api.md)
- Deprecations & sunset headers: [deprecations.md](deprecations.md)
