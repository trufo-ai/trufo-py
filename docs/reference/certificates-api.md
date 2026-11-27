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
| `c2pa-l1` | Production C2PA claim signing, Assurance Level 1 | 366 days | Also the only C2PA leaf type on `test.ca.trufo.ai` (Test Flow) |
| `c2pa-l2` | Production C2PA claim signing, Assurance Level 2 (hardware-backed keys) | 90 days | Contact [support@trufo.ai](mailto:support@trufo.ai) to enable on your product. Same issuing CA (`/c2pa-ca.crt`) and OCSP path (`/c2pa`) as `c2pa-l1` |
| `cawg-interim` | Production CAWG identity signing | 366 days | Organization-level |
| `c2pa-l1-test` | Dummy C2PA L1 certificate (conformance drafts) | 366 days | Enrolled on `ca.trufo.ai` (not `test.ca.trufo.ai`); chains to TCA Test Root CA; no account required |
| `cawg-interim-test` | Dummy CAWG identity certificate | 366 days | Enrolled on `ca.trufo.ai`; chains to TCA Test Root CA via the TCA Test CAWG Interim Issuing CA; no account required |
| `c2pa-l2-test` | Disabled | — | Returns `401 LeafTypeDisabled` on `ca.trufo.ai` |

- **CSR public keys:** Must be **EC P-256** (recommended for widest validator support) or **EC P-384**. RSA, Ed25519, and P-521 return `400 KeyTypeNotAllowed`.
- **Enrollment flow:** `Instance credential (client_assertion JWS)` → `POST /ra/c2pa/csr-jwt` → `csr_jwt` (300s lifetime, single-use) → `POST /.well-known/est/{leaf_type}/simpleenroll` with PKCS#10 CSR → PKCS#7 chain (leaf + issuing CA chain, root omitted).

---

## Certificate Authority (EST — RFC 7030)

### `GET /.well-known/est/{leaf_type}/cacerts`

Returns the CA certificate chain for `{leaf_type}`: on `ca.trufo.ai`, `c2pa-l1`, `c2pa-l2`, `cawg-interim`, `ctsa`, or the dummy `-test` equivalents; on `test.ca.trufo.ai`, `c2pa-l1` only (every other leaf type returns `404 UnknownLeafType`).

- **Auth:** None.
- **Response (200):** `Content-Type: application/pkcs7-mime; smime-type=certs-only` — base64-encoded DER PKCS#7 containing the issuing CA and the root CA (an unordered set; see [wire notes](#wire-notes-for-rust-go-and-c-clients)).
- **Errors:** `404 UnknownLeafType`.

### `POST /.well-known/est/{leaf_type}/simpleenroll`

Submit a PKCS#10 CSR and receive an issued certificate chain.

- **Auth:** HTTP Basic with empty username and the CSR JWT as password: `Authorization: Basic base64(":" + csr_jwt)`.
- **Headers:** `Content-Type: application/pkcs10`.
- **Body:** Base64-encoded DER PKCS#10 CSR (no PEM headers). The CSR subject DN is ignored; the CA builds the subject strictly from the CSR JWT's `distinguished_name` (and prepends `[TESTING] ` for dummy leaf types and all `test.ca.trufo.ai` certificates).
- **Response (200):** `Content-Type: application/pkcs7-mime; smime-type=certs-only` — base64-encoded DER PKCS#7 containing the issued leaf certificate and its issuing CA chain (**root CA is not included**; fetch from `cacerts` if needed). Order the certificates yourself (see [wire notes](#wire-notes-for-rust-go-and-c-clients)).
- **Errors:**
  - `400`: `InvalidContentType`, `InvalidCSR`, `InvalidCSRSignature`, `KeyTypeNotAllowed`
  - `401`: `MissingAuth`, `MalformedJWT`, `JWTExpired`, `InvalidSignature`, `InvalidAudience`, `MissingClaim`, `JWTDecodeError`, `UnknownLeafType`, `LeafTypeDisabled`, `LeafTypeMismatch`, `JTIAlreadyUsed`, `InvalidDistinguishedName`, `InvalidValidityDays`, `ValidityExceedsMax`, `InvalidRecordId`, `InvalidInstanceId`, `InvalidIssuer`, `InvalidIat`
  - `404`: `UnknownLeafType`
  - `409`: `PublicKeyAlreadyUsed` (generate a fresh leaf key pair)

### CSR JWT Format (HS256, 300s lifetime)

Minted by Trufo's RA for production and Test Flow. For **dummy enrollment** (`c2pa-l1-test`, `cawg-interim-test`) with no account, sign your own HS256 JWT with secret `hello-trufo` and `sub: "test-account"`, and enroll at `https://ca.trufo.ai/.well-known/est/{leaf_type}/simpleenroll` — `test.ca.trufo.ai` serves Test Flow `c2pa-l1` only. JTI replay prevention is skipped; dummy certs are issued by the TCA Test issuing CAs (root: TCA Test Root CA, the same root served at `https://test.ca.trufo.ai/root-ca.crt`), are not listed or revocable, and have no OCSP status to staple.

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
| `instance_id` | string | C2PA only | Generator product instance ID; the part after the last `_` (e.g. the UUID in `gpi_<uuid>`) must be a 36-character UUID (`401 InvalidInstanceId`) |

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

Unauthenticated revocation status at `https://ocsp.trufo.ai` (`https://test.ocsp.trufo.ai` for test certs). Covers Trufo CA-issued certificates only.

- **Endpoints:** `POST /` (DER `OCSPRequest` body, `Content-Type: application/ocsp-request`), `GET /{base64_or_base64url_request}`, plus optional issuer-pinned variants `POST`/`GET` on `/c2pa`, `/cawg`, `/ctsa`, and `/root` (status of Trufo's intermediate CAs, issued by `/root-ca.crt`). `test.ocsp.trufo.ai` answers for the Test Flow C2PA issuing CA (`/c2pa`) only.
- **Issuer mapping:** `c2pa-l1` and `c2pa-l2` leaves are both issued by the C2PA Claim Signing CA (`/c2pa-ca.crt`) and answered on `/c2pa`; `cawg-interim` on `/cawg` (`/temp-cawg-ca.crt`); `ctsa` on `/ctsa` (`/ctsa-ca.crt`). Build requests against the certificate's **direct issuing CA**, not the root.
- **Response (200):** `Content-Type: application/ocsp-response` — status `GOOD`, `REVOKED` (with `revocationTime` and optional reason), `UNKNOWN`, `UNAUTHORIZED`, or `TRY_LATER`. Malformed requests return `400` plain text.
- **Validity, caching & nonces:** Each signed response is valid for **7 days** (`thisUpdate` to `nextUpdate`) so it can be stapled; responses are cached and shared, and request nonces are not echoed.
- **Revocation propagation:** The responder refreshes its cached responses against CA revocation state roughly **every 60 seconds**, so a revocation appears in newly fetched responses within about a minute. Responses fetched before the revocation stay valid until their own `nextUpdate`.

---

## Timestamp Authority (RFC 3161)

### `POST https://tsa.trufo.ai/` (or dedicated `https://{host}.tsa.trufo.ai/`)

- **Auth:** `X-API-Key: tsa:<key>`.
- **Headers:** `Content-Type: application/timestamp-query`.
- **Body:** DER `TimeStampReq`, max **1,024 bytes**.
- **Response (200):** `Content-Type: application/timestamp-reply` — DER `TimeStampResp` (RFC 3161 v2 with `signingCertificateV2`). Accepted digest algorithms: **SHA-256**, **SHA-384**, **SHA-512**. Malformed/unsupported requests return HTTP 200 with RFC 3161 `badDataFormat` / `badAlg`.
- **Policy discovery:** `GET /policy` (unauthenticated; also on dedicated and test endpoints) returns:
  ```json
  {
    "status": "ok",
    "policy_oid": "<TSA policy OID>",
    "supported_hash_algorithms": ["SHA-256", "SHA-384", "SHA-512"],
    "timestamp_version": "v2",
    "specification": "RFC 3161"
  }
  ```
  `policy_oid` is the production C2PA timestamp policy (`1.3.6.1.4.1.62558.1.1`) on `tsa.trufo.ai` and the test policy (`1.3.6.1.4.1.62524.2.1`) on `test.tsa.trufo.ai`.
- **HTTP errors:** `400` (`InvalidContentType`, `EmptyRequestBody`), `401` (`MissingAPIKey`, `InvalidAPIKey`, `APIKeyRevoked`, `APIKeyExpired`, `InvalidAPIKeyScope`), `403` (`OrgNotAllowed` on dedicated endpoints), `413` (`RequestTooLarge`).

### Test TSA (`https://test.tsa.trufo.ai/`)

- `POST https://test.tsa.trufo.ai/` — no API key required; signs with a self-signed test certificate outside the production chain and outside `https://test.ca.trufo.ai/root-ca.crt` (OID `1.3.6.1.4.1.62524.2.1`, untrusted by validators).
- `POST https://test.tsa.trufo.ai/api-key` — identical test response, requires the literal header `X-API-Key: test-api-key-header` (otherwise `401 MissingAPIKey` / `401 InvalidAPIKey`) for testing header wiring.

---

## Registration Authority (Trufo API)

All RA endpoints run on `api.trufo.ai` / `eu.api.trufo.ai` (or `test.api.trufo.ai` for Test Flow, where OV, PV, and subscription checks are skipped for `c2pa-l1`).

**Test Flow sign-in:** `test.api.trufo.ai` has no sign-in or token-refresh routes. Obtain and refresh the Bearer access token for every authenticated RA route on `test.api.trufo.ai` from `https://api.trufo.ai` (device authorization `/account/device/*` and `/account/refresh`), then send it to `test.api.trufo.ai`. `TrufoSession(base_api_url=TRUFO_API_URL_TEST)` does this automatically.

### Generator products

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /gproduct/list` | MFA, member+ | `{"oid": "..."}` (required; `{}` returns `422`) | `gproducts[]`: `gp_id`, `name`, `implementation`, `pv_status`, `pv_active`, `branded`, `bpv_status`, `validated_expires_at`, `cancel_at` |
| `POST /gproduct/info` | MFA, member+ | `{"gp_id": "..."}` | `gp_id`, `oid`, `name`, `created_by`, `created_at` |
| `POST /gproduct/info/edit` | MFA, owner/admin | `{"gp_id": "...", "name": "..."}` | `status` |
| `POST /gproduct/cancel` | MFA, owner/admin | `{"gp_id": "..."}` | `gp_id`, `cancel_at`, `removed` |

### Product Validation (PV) and Branded Product Validation (BPV) drafts, uploads, and status

Drafts can be read, saved, and discarded programmatically, and supporting documents can be uploaded ahead of time. Once a draft is ready, an owner or admin reviews and submits the final application in [app.trufo.ai](https://app.trufo.ai).

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `GET /gproduct/pv/draft` | MFA, member+ | *(no body)* | `{"draft": {<PV draft fields>} \| null}` |
| `POST /gproduct/pv/draft/save` | MFA, owner/admin | Any subset of the PV draft fields below | `{"status": "ok"}` |
| `POST /gproduct/pv/draft/discard` | MFA, owner/admin | `{}` | `{"status": "ok"}` |
| `POST /gproduct/pv/status` | MFA, member+ | `{"gp_id": "..."}` | `gp_id`, `status` (`"none"` \| `"pending"` \| `"reviewing"` \| `"approved"` \| `"rejected"`), `application_id`, the submitted PV fields, `submitted_at`, `approved_at`, `validated_expires_at`, `has_validated_info`, `pv_active`, `reviewer_notes` |
| `POST /gproduct/pv/upload` | MFA, owner/admin | `multipart/form-data`: `file` + optional `gp_id` form field | `{"s3_key": "..."}` |
| `GET /gproduct/bpv/draft` | MFA, member+ | *(no body)* | `{"draft": {<BPV draft fields>} \| null}` |
| `POST /gproduct/bpv/draft/save` | MFA, owner/admin | Any subset of the BPV draft fields below | `{"status": "ok"}` |
| `POST /gproduct/bpv/draft/discard` | MFA, owner/admin | `{}` | `{"status": "ok"}` |
| `POST /gproduct/bpv/status` | MFA, member+ | `{"gp_id": "..."}` | `gp_id`, `status`, `application_id`, the submitted BPV fields, `submitted_at`, `approved_at`, `validated_expires_at`, `has_validated_info`, `bpv_active`, `reviewer_notes` |
| `POST /gproduct/bpv/upload` | MFA, owner/admin | `multipart/form-data`: `file` + optional `gp_id` form field | `{"s3_key": "..."}` |

**Drafts:** One PV draft and one BPV draft per organization. Every field is optional and nullable; `draft/save` updates only the fields present in the body and leaves the rest unchanged.

**Uploads (`/gproduct/pv/upload`, `/gproduct/bpv/upload`):** One file per request, max **50 MB** (`400 FileTooLarge` above that). Omit `gp_id` before the product exists (first draft); when supplied it must belong to your organization. The returned `s3_key` is an opaque reference — add it to the matching list field (`supporting_files` for PV; `trademark_evidence_files`, `sec_arch_diagram_files`, or `security_certification_files` for BPV) and save the draft.

**PV draft fields:**

| Field | Type | Notes |
| --- | --- | --- |
| `product_name`, `org_unit` | string | Product name and optional organizational unit (`OU`) for the certificate subject |
| `record_id` | string | C2PA conformance product record ID; locked once PV is approved |
| `assurance_level`, `spec_version` | string | Assurance level must match the product's plan; locked once PV is approved |
| `implementation` | string | `"backend"`, `"distributed"`, or `"edge"` (see [Certificates](../topics/certificates.md#production-certificate-enrollment)) |
| `contact_first_name`, `contact_last_name`, `contact_email`, `contact_phone_country_code`, `contact_phone` | string | Product contact |
| `security_key_storage`, `security_vuln_patching`, `security_tls`, `security_no_key_export` | boolean | Security practice attestations |
| `att_conformance`, `att_sec_arch_doc`, `att_level_1` | boolean | Conformance, security architecture, and Assurance Level 1 attestations |
| `att_backend`, `att_distributed`, `att_edge` | boolean | Architecture attestation; the one matching the product's implementation type is required at submission |
| `agree_terms`, `agree_authorized` | boolean | Agreements; required at submission |
| `supporting_files` | string[] | `s3_key` values from `/gproduct/pv/upload` |

**BPV draft fields:**

| Field | Type | Notes |
| --- | --- | --- |
| `c2pa_organization` | `"own"` \| `"trufo"` | Self-serve submissions in `app.trufo.ai` always set `"trufo"` (certificate carries your Product Name as `CN`, with `O=Trufo Inc.`, `C=US`, and `org_unit` cleared). Contact [support@trufo.ai](mailto:support@trufo.ai) to list under your own organization (`"own"`, which requires `att_c2pa_agreement` and sets `O`/`C` from your OV) |
| `att_c2pa_agreement` | boolean | C2PA agreement attestation (with `"own"`) |
| `org_unit`, `product_name`, `product_url` | string | Product identity; `org_unit` is plain ASCII ≤ 64 characters; `product_url` must start with `https://` |
| `name_has_trademarks`, `att_trademark_clearance` | boolean | Trademark declarations |
| `trademark_evidence_files` | string[] | `s3_key` values from `/gproduct/bpv/upload` (with `name_has_trademarks`) |
| `earliest_public_disclosure` | string | ISO 8601 date |
| `product_description`, `product_architecture`, `product_assertions` | string | Free-text product description, system architecture, and the assertions it declares |
| `att_created_gathered`, `att_all_actions_included` | boolean | Manifest-accuracy attestations |
| `external_clients` | boolean | Part of the product runs on apps or devices you do not operate |
| `external_direct_api` | boolean | Those apps or devices call Trufo directly rather than through your servers (with `external_clients`) |
| `external_credential_storage` | string | How those apps or devices authenticate and protect credentials (with `external_direct_api`) |
| `declares_captured_media`, `declares_non_genai_creation` | boolean | Whether the product declares captured media or non-GenAI digital creation |
| `capture_workflows` | string | Capture and creation workflows (with either `declares_*` field) |
| `sec_arch_diagram_files` | string[] | `s3_key` values from `/gproduct/bpv/upload` (with `external_clients` or either `declares_*` field) |
| `security_scanning_tools`, `security_access_controls` | string | Security program description |
| `att_vuln_remediation_software`, `att_vuln_remediation_hosting` | boolean | Vulnerability remediation attestations |
| `security_certification` | `"iso_27001"` \| `"soc_2"` \| `"none"` | Security certification held |
| `security_certification_files` | string[] | `s3_key` values from `/gproduct/bpv/upload` (cleared when `security_certification` is `"none"`) |
| `att_certification_scope` | boolean | Certification covers the systems described (with `"iso_27001"` or `"soc_2"`) |
| `contact_first_name`, `contact_last_name`, `contact_email`, `contact_phone_country_code`, `contact_phone` | string | Product contact |
| `agree_terms`, `agree_authorized` | boolean | Agreements |

### Instances (`/gproduct/instance/*`)

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /gproduct/instance/create` | MFA, owner/admin | `{"gp_id": "...", "name": "..."}` | `{"gpi_id": "..."}` (201) |
| `POST /gproduct/instance/list` | MFA, member+ | `{"gp_id": "..."}` | `{"instances": [{"gpi_id", "name", "record_id"}]}` |
| `POST /gproduct/instance/info` | MFA, member+ | `{"gpi_id": "..."}` | `{"gpi_id", "gp_id", "oid", "name", "record_id", "created_by", "created_at"}` (`created_at` ISO 8601 or `null`) |
| `POST /gproduct/instance/edit` | MFA, owner/admin | `{"gpi_id": "...", "name": "..."}` | `{"status": "ok"}` |
| `POST /gproduct/instance/delete` | MFA, owner/admin | `{"gpi_id": "..."}` | `{"status": "ok"}` |

`record_id` is the product's C2PA conformance record ID (from PV).

**Errors:** `400 ProductNotValidated`, `403 PVNotActive`, `403 OVNotActive`, `403 SubscriptionRequired`, `403 BillingNotActive`, `403 GPCancelled`, `404 GProductNotFound`, `404 InstanceNotFound`.

### Instance credentials (`/gproduct/instance/credential/*`)

At most **2 active credentials per instance** (enables zero-downtime key rotation). Accepted algorithms: **EC P-256 (`ES256`)** or **Ed25519 (`EdDSA`)** — P-384, RSA, and other keys return `400 UnsupportedKeyAlgorithm`.

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /gproduct/instance/credential/register` | MFA, owner/admin | `{"gpi_id": "...", "public_key_pem": "...", "key_algorithm": "ES256" \| "EdDSA", "label"?: "..."}` | `{"gpic_id": "..."}` (201) |
| `POST /gproduct/instance/credential/list` | MFA, member+ | `{"gpi_id": "..."}` | `{"credentials": [{"gpic_id", "gpi_id", "key_algorithm", "label", "created_at", "revoked", "revoked_at"}]}` (revoked credentials included, with `revoked: true`) |
| `POST /gproduct/instance/credential/edit` | MFA, owner/admin | `{"gpic_id": "...", "label": "..."}` | `{"status": "ok"}` |
| `POST /gproduct/instance/credential/revoke` | MFA, owner/admin | `{"gpic_id": "..."}` | `{"status": "ok"}` |

**Errors:** `400 InvalidPublicKey` (unparseable PEM), `400 UnsupportedKeyAlgorithm`, `400 AlgorithmMismatch` (`key_algorithm` does not match the key), `400` with a sentence detail when the instance already has 2 active credentials (revoke one first; revoked credentials do not count), `400 AlreadyRevoked` (revoke), `404 InstanceNotFound`, `404 CredentialNotFound` (edit, revoke).

### `POST /ra/c2pa/csr-jwt`

Exchange a signed `client_assertion` JWS for a single-use `csr_jwt`. **Auth:** `client_assertion` only (no API key or Bearer token). In Test Flow, call `https://test.api.trufo.ai/ra/c2pa/csr-jwt`.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `client_assertion` | string | Yes | Compact JWS (`ES256` or `EdDSA`, max 300s lifetime; 60s recommended) signed by the registered instance private key |
| `leaf_type` | string | Yes | `"c2pa-l1"` or `"c2pa-l2"` (Test Flow: `"c2pa-l1"` only) |
| `validity_days` | integer | No | `1..366` (`c2pa-l1`) or `1..90` (`c2pa-l2`) |

**`client_assertion` JWT payload:** `{"iss": "<gpi_id>", "sub": "<gpic_id>", "aud": "trufo-ra", "iat": <unix>, "exp": <unix>}` (JOSE header `alg`: `"ES256"` or `"EdDSA"`).

**Response (200):** `{"csr_jwt": "<hs256-jwt>"}`.

**Cap:** At most **3 active certificates per instance**; revoked and expired certificates do not count. At the cap, the request fails with `403` and a sentence detail ("There are already 3 active certificates for this GP instance. If you would like to issue a new one, please revoke one of the existing ones, or wait until one of the existing ones has expired.").

**Errors:** `400 InvalidLeafType`, `400 InvalidValidityDays`, `401 ClientAssertionFailed`, `403 LeafTypeNotAllowed`, `403 ProductNotValidated`, `403 PVNotActive`, `403 OVNotActive`, `403 BillingNotActive`, `403 GPCancelled`, `403` active-certificate cap (above), `404 InstanceNotFound`, `404 ProductNotFound`.

#### Wire notes for Rust, Go, and C clients

- **`ES256` JWS signatures** use the raw 64-byte `r || s` encoding (RFC 7518 §3.4), not the DER `ECDSA-Sig-Value` most crypto libraries return — convert before base64url-encoding. AWS and Google Cloud KMS return DER signatures.
- **EST `simpleenroll` request:** the body is the base64 encoding of the DER CSR (no PEM armor; line breaks are tolerated) with `Content-Type: application/pkcs10`. No `Content-Transfer-Encoding` header is needed.
- **EST responses** (`simpleenroll`, `cacerts`) are base64-encoded DER PKCS#7 bodies sent without a `Content-Transfer-Encoding` header; base64-decode the body unconditionally.
- **Certificate order:** a PKCS#7 `certificates` field is an unordered SET. Do not assume the leaf comes first: pick the certificate without `basicConstraints cA=TRUE` as the leaf, then order the CA certificates by following issuer → subject, leaf → intermediate, and exclude the self-signed root from the chain you sign with.

### `POST /ra/cawg-interim/csr-jwt`

**Auth:** MFA-verified access token, owner/admin (`request_cawg_cert`). **Request:** `{"validity_days"?: 1..366}`. **Response (200):** `{"csr_jwt": "..."}` (for `leaf_type: "cawg-interim"`). **Errors:** `400 InvalidValidityDays`, `403 NoEligiblePlan`, `403 OVNotActive`, `403 OrgNotValidated`. The Python SDK wraps this flow as `request_cawg_interim_cert()`.

### Domain Validation (`/domain/dv/*`)

Proves your organization controls a domain so you can use reverse-DNS names under it in C2PA requests. One validated domain covers all three uses:

- `custom` assertion labels (for example `com.example.review`),
- custom `redact` reasons (for example `com.example.legal-hold`), and
- custom action names in `action_history`.

Validating `example.com` authorizes every value equal to `com.example` or starting with `com.example.` — including names for subdomains (`com.example.sub.*`). Values in the `c2pa.*` namespace need no validation. Without an active validation covering a value, signing returns `403 InvalidC2PACustomDomain`; a `custom` entry without a `label` returns `400 MissingC2PACustomDomain`.

**Plan:** `/domain/dv/submit` and `/domain/dv/check` require the `c2pa_custom_domain` plan (`403 NoEligiblePlan` otherwise).

**Flow:** `submit` returns a `CNAME` challenge (`challenge_name` → `record_value`); publish it in your DNS, then call `check`. On success `status` becomes `"validated"` and `expires_at` is set 100 days out.

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /domain/dv/submit` | MFA, owner/admin | `{"oid": "...", "domain": "example.com", "scope"?: "c2pa-custom-assertion"}` | DV record |
| `POST /domain/dv/check` | MFA, owner/admin | `{"dv_id": "..."}` | DV record + `dns_evidence` |
| `POST /domain/dv/status` | MFA, member+ | `{"dv_id": "..."}` | DV record |
| `POST /domain/dv/list` | MFA, member+ | `{"oid": "..."}` | `{"domains": [<DV record>, ...]}` |
| `POST /domain/dv/cancel` | MFA, owner/admin | `{"dv_id": "..."}` | `{"dv_id", "removed", "cancel_at"}` |
| `POST /domain/dv/uncancel` | MFA, owner/admin | `{"dv_id": "..."}` | `{"dv_id"}` |

- **`scope`:** `"c2pa-custom-assertion"` (the only scope; the default).
- **DV record:** `dv_id`, `oid`, `domain`, `scope`, `status` (`"pending"` \| `"validated"`), `challenge_name`, `record_type` (`"CNAME"`), `record_value`, `submitted_at`, `validated_at`, `last_checked_at`, `expires_at`, `last_error`, `cancel_at` (timestamps ISO 8601 or `null`). Resubmitting the same domain returns the existing record.
- **Cancel:** a validated, billed domain stays active until `cancel_at` (`removed: false`); any other record (for example one still `"pending"`) is removed immediately (`removed: true`, `cancel_at: null`). `uncancel` clears a scheduled cancellation.
- **Errors:** `403 NoEligiblePlan`, `404 DomainDVNotFound`, `400 DomainDVAlreadyCancelled` (cancel), `400 DomainDVNotCancelled` (uncancel).

### Certificates (`/cert/list`, `/cert/revoke`)

**`POST /cert/list`** (MFA, member+, `{}`) returns `{"certs": [...]}` covering every certificate issued to your organization (active, expired, and revoked):

| Field | Type | Description |
| --- | --- | --- |
| `serial_number` | string | Certificate serial (hex) |
| `leaf_type` | string | `c2pa-l1`, `c2pa-l2`, `cawg-interim`, ... |
| `issue_time`, `expiry_time` | string | ISO 8601 |
| `revocation_status` | string | `"good"` or `"revoked"` (expiry is not reflected here; compare `expiry_time`) |
| `revocation_reason`, `revocation_time` | string \| null | Set when revoked |
| `revocable` | boolean | Whether `/cert/revoke` accepts this certificate (not whether it is still live) |
| `trufo_managed` | boolean | Trufo holds the key (Trufo-hosted CAWG certificates and Trufo-operated instances) |
| `gpi_id`, `gpi_name`, `gp_id`, `gp_name` | string \| null | Instance and product the certificate was issued for; `null` for organization-level CAWG certificates or when the instance has since been deleted |

**`POST /cert/revoke`** (MFA, owner/admin):

```json
{
  "serial_number": "<hex-serial>",
  "revocation_reason": "key_compromise",
  "revocation_time": "2026-09-10T18:30:00Z"
}
```

- **Response (200):** `{"status": "ok"}`. Revocation is permanent and reaches the OCSP responder within about a minute.
- `revocation_reason`: `"unspecified"`, `"key_compromise"`, `"affiliation_changed"`, `"superseded"`, `"cessation_of_operation"`.
- `revocation_time` (optional): RFC 3339 timestamp with `Z` or UTC offset, not in the future; backdates the revocation cutoff.
- **Already-revoked certificates:** resubmitting **without** `revocation_time` returns `400 AlreadyRevoked`. Resubmitting **with** `revocation_time` adjusts the existing cutoff; if a concurrent revocation of the same certificate wins, the call returns `409 RevocationConflict` — re-read `/cert/list` before retrying.
- Trufo-managed CAWG interim certificates (`revocable: false`) return `400 NotRevocable`.
- **Errors:** `400` (`NotRevocable`, `InvalidRevocationReason`, `AlreadyRevoked`), `404 NotFound`, `409 RevocationConflict`, `422` invalid timestamp, `502 RevocationFailed` (do not retry blindly — check `/cert/list` first).
