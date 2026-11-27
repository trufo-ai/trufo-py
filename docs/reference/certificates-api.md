# Certificates, TSA, and OCSP API Reference

Normative specification for Trufo Certificate Authority (EST), OCSP responder (RFC 6960), Timestamp Authority (RFC 3161), and Registration Authority (RA) endpoints.

- **Certificate Authority (EST):** `https://ca.trufo.ai` (test: `https://test.ca.trufo.ai`)
- **OCSP Responder:** `https://ocsp.trufo.ai` (test: `https://test.ocsp.trufo.ai`)
- **Timestamp Authority (TSA):** `https://tsa.trufo.ai` (test: `https://test.tsa.trufo.ai`)
- **Registration Authority (RA):** `https://api.trufo.ai` / `https://eu.api.trufo.ai` (test: `https://test.api.trufo.ai`)

CA, OCSP, and TSA are standards-based services with their own auth headers (HTTP Basic with CSR JWT, unauthenticated OCSP, `X-API-Key` for TSA). RA endpoints live on the Trufo API and follow [Platform API](platform-api.md) conventions.

---

## Certificate Types and Accepted Keys

| Leaf type | Purpose | Max validity | Notes |
| --- | --- | --- | --- |
| `c2pa-l1` | Production C2PA claim signing, Assurance Level 1 | 366 days | Also used on `test.ca.trufo.ai` for Test Flow |
| `c2pa-l2` | Production C2PA claim signing, Assurance Level 2 (hardware-backed keys) | 90 days | Contact [support@trufo.ai](mailto:support@trufo.ai) to enable on your product |
| `cawg-interim` | Production CAWG identity signing | 366 days | Organization-level |
| `c2pa-l1-test` | Dummy C2PA L1 certificate (conformance drafts) | 366 days | Test CA; no account required |
| `cawg-interim-test` | Dummy CAWG identity certificate | 366 days | Test CA; no account required |
| `c2pa-l2-test` | Disabled | — | Returns `401 LeafTypeDisabled` |

- **CSR public keys:** Must be **EC P-256** (recommended for widest validator support) or **EC P-384**. RSA, Ed25519, and P-521 return `400 KeyTypeNotAllowed`.
- **Enrollment flow:** `Instance credential (client_assertion JWS)` → `POST /ra/c2pa/csr-jwt` → `csr_jwt` (300s lifetime, single-use) → `POST /.well-known/est/{leaf_type}/simpleenroll` with PKCS#10 CSR → PKCS#7 chain (leaf + issuing CA chain, root omitted).

---

## Certificate Authority (EST — RFC 7030)

### `GET /.well-known/est/{leaf_type}/cacerts`

Returns the CA certificate chain for `{leaf_type}` (`c2pa-l1`, `c2pa-l2`, `cawg-interim`, `ctsa`, or `-test` equivalents).

- **Auth:** None.
- **Response (200):** `Content-Type: application/pkcs7-mime; smime-type=certs-only` — base64-encoded DER PKCS#7 containing the issuing CA followed by the root CA.
- **Errors:** `404 UnknownLeafType`.

### `POST /.well-known/est/{leaf_type}/simpleenroll`

Submit a PKCS#10 CSR and receive an issued certificate chain.

- **Auth:** HTTP Basic with empty username and the CSR JWT as password: `Authorization: Basic base64(":" + csr_jwt)`.
- **Headers:** `Content-Type: application/pkcs10`.
- **Body:** Base64-encoded DER PKCS#10 CSR (no PEM headers). The CSR subject DN is ignored; the CA builds the subject strictly from the CSR JWT's `distinguished_name` (and prepends `[TESTING] ` for dummy leaf types and all `test.ca.trufo.ai` certificates).
- **Response (200):** `Content-Type: application/pkcs7-mime; smime-type=certs-only` — base64-encoded DER PKCS#7 containing the issued leaf certificate followed by its issuing CA chain (**root CA is not included**; fetch from `cacerts` if needed).
- **Errors:**
  - `400`: `InvalidContentType`, `InvalidCSR`, `InvalidCSRSignature`, `KeyTypeNotAllowed`
  - `401`: `MissingAuth`, `MalformedJWT`, `JWTExpired`, `InvalidSignature`, `InvalidAudience`, `MissingClaim`, `JWTDecodeError`, `UnknownLeafType`, `LeafTypeDisabled`, `LeafTypeMismatch`, `JTIAlreadyUsed`, `InvalidDistinguishedName`, `InvalidValidityDays`, `ValidityExceedsMax`, `InvalidRecordId`, `InvalidInstanceId`, `InvalidIssuer`, `InvalidIat`
  - `404`: `UnknownLeafType`
  - `409`: `PublicKeyAlreadyUsed` (generate a fresh leaf key pair)

### CSR JWT Format (HS256, 300s lifetime)

Minted by Trufo's RA for production and Test Flow. For **dummy enrollment** (`c2pa-l1-test`, `cawg-interim-test`) with no account, sign your own HS256 JWT with secret `hello-trufo` and `sub: "test-account"` (JTI replay prevention is skipped; dummy certs are not listed or revocable).

| Claim | Type | Required | Description |
| --- | --- | --- | --- |
| `iss` | string | Yes | `"trufo"` |
| `sub` | string | Yes | Subscriber organization ID (or `"test-account"` for dummy) |
| `aud` | string | Yes | `"tca-est"` |
| `jti` | string | Yes | Unique token ID (single-use except dummy leaf types) |
| `iat`, `exp` | integer | Yes | Issued-at and expiry (Unix seconds) |
| `leaf_type` | string | Yes | Must match endpoint path segment |
| `distinguished_name` | object | Yes | `{"C": "US", "O": "...", "CN": "...", "ST"?: "...", "L"?: "...", "OU"?: "..."}` |
| `validity_days` | integer | No | `1` to leaf-type max; omitted uses max |
| `record_id` | string | C2PA only | Product record UUID (36-char format) |
| `instance_id` | string | C2PA only | Generator product instance ID |

### CA Certificate Downloads

Unauthenticated `GET` endpoints returning single DER certificates (`application/pkix-cert`):

| Path | Production (`ca.trufo.ai`) | Test (`test.ca.trufo.ai`) |
| --- | --- | --- |
| `/root-ca.crt` | Trufo C2PA Root CA (trust anchor) | TCA Test Root CA |
| `/c2pa-ca.crt` | C2PA Claim Signing CA | TCA Test C2PA Issuing CA |
| `/ctsa-ca.crt` | C2PA Timestamping CA | — |
| `/temp-cawg-ca.crt` | Interim CAWG Identity CA | — |

---

## OCSP Responder (RFC 6960)

Unauthenticated revocation status at `https://ocsp.trufo.ai` (`https://test.ocsp.trufo.ai` for test certs).

- **Endpoints:** `POST /` (DER `OCSPRequest` body, `Content-Type: application/ocsp-request`), `GET /{base64_or_base64url_request}`, plus optional issuer-pinned variants `POST`/`GET` on `/c2pa`, `/cawg`, `/ctsa`, `/root`.
- **Response (200):** `Content-Type: application/ocsp-response` — status `GOOD`, `REVOKED` (with `revocationTime` and optional reason), `UNKNOWN`, `UNAUTHORIZED`, or `TRY_LATER`. Malformed requests return `400` plain text.
- **Caching & nonces:** Responses are valid for **7 days** (`thisUpdate` to `nextUpdate`), cached and shared; request nonces are not echoed. Build requests against the certificate's **direct issuing CA**.

---

## Timestamp Authority (RFC 3161)

### `POST https://tsa.trufo.ai/` (or dedicated `https://{host}.tsa.trufo.ai/`)

- **Auth:** `X-API-Key: tsa:<key>`.
- **Headers:** `Content-Type: application/timestamp-query`.
- **Body:** DER `TimeStampReq`, max **1,024 bytes**.
- **Response (200):** `Content-Type: application/timestamp-reply` — DER `TimeStampResp` (RFC 3161 v2 with `signingCertificateV2`). Accepted digest algorithms: **SHA-256**, **SHA-384**, **SHA-512**. Malformed/unsupported requests return HTTP 200 with RFC 3161 `badDataFormat` / `badAlg`.
- **Policy discovery:** `GET /policy` returns the policy OID and supported digest algorithms as JSON.
- **HTTP errors:** `400` (`InvalidContentType`, `EmptyRequestBody`), `401` (`MissingAPIKey`, `InvalidAPIKey`, `APIKeyRevoked`, `APIKeyExpired`, `InvalidAPIKeyScope`), `403` (`OrgNotAllowed` on dedicated endpoints), `413` (`RequestTooLarge`).

### Test TSA (`https://test.tsa.trufo.ai/`)

- `POST https://test.tsa.trufo.ai/` — no API key required; signs with a self-signed test certificate outside the production chain (OID `1.3.6.1.4.1.62524.2.1`, untrusted for production).
- `POST https://test.tsa.trufo.ai/api-key` — identical test response, requires `X-API-Key: test-api-key-header` for testing header wiring.

---

## Registration Authority (Trufo API)

All RA endpoints run on `api.trufo.ai` / `eu.api.trufo.ai` (or `test.api.trufo.ai` for Test Flow, where OV, PV, and subscription checks are skipped for `c2pa-l1`).

### Generator products

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /gproduct/list` | MFA, member+ | `{"oid": "..."}` (optional; inferred from session) | `gproducts[]`: `gp_id`, `name`, `implementation`, `pv_status`, `pv_active`, `branded`, `bpv_status`, `validated_expires_at`, `cancel_at` |
| `POST /gproduct/info` | MFA, member+ | `{"gp_id": "..."}` | `gp_id`, `oid`, `name`, `created_by`, `created_at` |
| `POST /gproduct/info/edit` | MFA, owner/admin | `{"gp_id": "...", "name": "..."}` | `status` |
| `POST /gproduct/cancel` | MFA, owner/admin | `{"gp_id": "..."}` | `gp_id`, `cancel_at`, `removed` |

### Product Validation (PV) and Branded Product Validation (BPV) drafts, uploads, and status

Drafts can be read, saved, and discarded programmatically, and supporting documents can be uploaded ahead of time. Once a draft is ready, an owner or admin reviews and submits the final application in [app.trufo.ai](https://app.trufo.ai).

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `GET /gproduct/pv/draft` | MFA, member+ | *(no body)* | `{"draft": {...} \| null}` |
| `POST /gproduct/pv/draft/save` | MFA, owner/admin | Partial PV draft fields (e.g., `product_name`, `record_id`, `assurance_level`, `spec_version`, `implementation`, contact and security attestation fields, `supporting_files`) | `{"status": "ok"}` |
| `POST /gproduct/pv/draft/discard` | MFA, owner/admin | `{}` | `{"status": "ok"}` |
| `POST /gproduct/pv/status` | MFA, member+ | `{"gp_id": "..."}` | `gp_id`, `status`, submitted fields, review status |
| `POST /gproduct/pv/upload` | MFA, owner/admin | `multipart/form-data`: `file` + optional `gp_id` form field | Uploaded file reference for `supporting_files` |
| `GET /gproduct/bpv/draft` | MFA, member+ | *(no body)* | `{"draft": {...} \| null}` |
| `POST /gproduct/bpv/draft/save` | MFA, owner/admin | Partial BPV draft fields (e.g., `c2pa_organization`, `product_name`, `product_description`, `product_architecture`, `product_assertions`, `trademark_evidence_files`) | `{"status": "ok"}` |
| `POST /gproduct/bpv/draft/discard` | MFA, owner/admin | `{}` | `{"status": "ok"}` |
| `POST /gproduct/bpv/status` | MFA, member+ | `{"gp_id": "..."}` | `gp_id`, `status`, `application_id`, `submitted_at`, `approved_at`, `validated_expires_at`, `bpv_active`, `reviewer_notes` |
| `POST /gproduct/bpv/upload` | MFA, owner/admin | `multipart/form-data`: `file` + optional `gp_id` form field | Uploaded file reference for supporting/trademark files |

### Instances (`/gproduct/instance/*`)

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /gproduct/instance/create` | MFA, owner/admin | `{"gp_id": "...", "name": "..."}` | `{"gpi_id": "..."}` (201) |
| `POST /gproduct/instance/list` | MFA, member+ | `{"gp_id": "..."}` | `instances[]`: `gpi_id`, `name`, `record_id` |
| `POST /gproduct/instance/info` | MFA, member+ | `{"gpi_id": "..."}` | Instance detail |
| `POST /gproduct/instance/edit` | MFA, owner/admin | `{"gpi_id": "...", "name": "..."}` | `status` |
| `POST /gproduct/instance/delete` | MFA, owner/admin | `{"gpi_id": "..."}` | `status` |

**Errors:** `400 ProductNotValidated`, `403 PVNotActive`, `403 OVNotActive`, `403 SubscriptionRequired`, `403 BillingNotActive`, `403 GPCancelled`, `404 GProductNotFound`, `404 InstanceNotFound`.

### Instance credentials (`/gproduct/instance/credential/*`)

At most **2 active credentials per instance** (enables zero-downtime key rotation). Accepted algorithms: **EC P-256 (`ES256`)** or **Ed25519 (`EdDSA`)**.

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /gproduct/instance/credential/register` | MFA, owner/admin | `{"gpi_id": "...", "public_key_pem": "...", "key_algorithm": "ES256" \| "EdDSA", "label"?: "..."}` | `{"gpic_id": "..."}` (201) |
| `POST /gproduct/instance/credential/list` | MFA, member+ | `{"gpi_id": "..."}` | `credentials[]` |
| `POST /gproduct/instance/credential/edit` | MFA, owner/admin | `{"gpic_id": "...", "label": "..."}` | `status` |
| `POST /gproduct/instance/credential/revoke` | MFA, owner/admin | `{"gpic_id": "..."}` | `status` |

### `POST /ra/c2pa/csr-jwt`

Exchange a signed `client_assertion` JWS for a single-use `csr_jwt`. **Auth:** `client_assertion` only (no API key or Bearer token).

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `client_assertion` | string | Yes | Compact JWS (`ES256` or `EdDSA`, max 300s lifetime; 60s recommended) signed by the registered instance private key |
| `leaf_type` | string | Yes | `"c2pa-l1"` or `"c2pa-l2"` |
| `validity_days` | integer | No | `1..366` (`c2pa-l1`) or `1..90` (`c2pa-l2`) |

**`client_assertion` JWT payload:** `{"iss": "<gpi_id>", "sub": "<gpic_id>", "aud": "trufo-ra", "iat": <unix>, "exp": <unix>}` (JOSE header `alg`: `"ES256"` or `"EdDSA"`).

**Response (200):** `{"csr_jwt": "<hs256-jwt>"}`.

**Cap:** At most **3 active (unexpired, unrevoked) certificates per instance**.  
**Errors:** `400 InvalidLeafType`, `400 InvalidValidityDays`, `401 ClientAssertionFailed`, `403 LeafTypeNotAllowed`, `403 PVNotActive`, `403 OVNotActive`, `403 BillingNotActive`, `403 GPCancelled`, `403` active-cert cap, `404 InstanceNotFound`, `404 ProductNotFound`.

### `POST /ra/cawg-interim/csr-jwt`

**Auth:** MFA-verified access token, owner/admin (`request_cawg_cert`). **Request:** `{"validity_days"?: 1..366}`. **Response (200):** `{"csr_jwt": "..."}` (for `leaf_type: "cawg-interim"`). **Errors:** `400 InvalidValidityDays`, `403 NoEligiblePlan`, `403 OVNotActive`, `403 OrgNotValidated`.

### Domain Validation (`/domain/dv/*`)

Required for `custom` assertions and custom reverse-DNS `redact` reasons (`403 InvalidC2PACustomDomain` without active DV). Validation uses a DNS `CNAME` record returned by `/domain/dv/submit`.

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /domain/dv/submit` | MFA, owner/admin | `{"oid": "...", "domain": "example.com", "scope"?: "c2pa_custom_assertion"}` | `dv_id`, `status`, `challenge_name`, `record_type` (`"CNAME"`), `record_value` |
| `POST /domain/dv/check` | MFA, owner/admin | `{"dv_id": "..."}` | Updated DV record + `dns_evidence` |
| `POST /domain/dv/status` | MFA, member+ | `{"dv_id": "..."}` | DV record (`status`, `challenge_name`, `record_value`, `validated_at`, `expires_at`) |
| `POST /domain/dv/list` | MFA, member+ | `{"oid": "..."}` | `domains[]` |
| `POST /domain/dv/cancel` | MFA, owner/admin | `{"dv_id": "..."}` | `dv_id`, `removed`, `cancel_at` |
| `POST /domain/dv/uncancel` | MFA, owner/admin | `{"dv_id": "..."}` | `dv_id` |

### Certificates (`/cert/list`, `/cert/revoke`)

- **`POST /cert/list`** (MFA, member+, `{}`): returns `certs[]` with `serial_number`, `leaf_type`, `issue_time`, `expiry_time`, `revocation_status`, `revocation_reason`, `revocation_time`, `revocable`, `trufo_managed`, and product/instance IDs.
- **`POST /cert/revoke`** (MFA, owner/admin):
  ```json
  {
    "serial_number": "<hex-serial>",
    "revocation_reason": "key_compromise",
    "revocation_time": "2026-09-10T18:30:00Z"
  }
  ```
  - `revocation_reason`: `"unspecified"`, `"key_compromise"`, `"affiliation_changed"`, `"superseded"`, `"cessation_of_operation"`.
  - `revocation_time` (optional): RFC 3339 timestamp with `Z` or UTC offset, not in the future. Can be resubmitted on an already-revoked cert to adjust the cutoff time.
  - Trufo-managed CAWG interim certificates (`revocable: false`) return `400 NotRevocable`.
  - **Errors:** `400` (`NotRevocable`, `InvalidRevocationReason`, `AlreadyRevoked`), `404 NotFound`, `409 RevocationConflict`, `422` invalid timestamp, `502 RevocationFailed` (do not retry blindly — check `/cert/list` first).
