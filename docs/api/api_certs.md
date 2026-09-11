# Trufo Certificate API

Certificate enrollment (EST), revocation checking (OCSP), and timestamping (RFC 3161)
via the Trufo Certificate Authority, plus the Registration Authority endpoints that
authorize enrollment: validation, generator products, instances, and credentials.

- **Certificate Authority:** `https://ca.trufo.ai`
- **OCSP Responder:** `https://ocsp.trufo.ai`
- **Timestamp Authority:** `https://tsa.trufo.ai` (test: `https://test.tsa.trufo.ai`)
- **Registration Authority:** the Trufo API (`https://api.trufo.ai`, `https://eu.api.trufo.ai`)

Most organizations never call these endpoints directly — signing through
[api_c2pa.md](api_c2pa.md) uses Trufo's own certificates. These endpoints are for
teams that operate their own C2PA generator product and sign with their own
certificates. See the [certificates quickstart](../quickstart/1_certs.md).

---

## Common Declarations

### Two services, two auth models

CA, OCSP, and TSA are standards-based services with their own conventions
(HTTP Basic with a CSR JWT, unauthenticated OCSP, `X-API-Key` for TSA). The
Registration Authority endpoints live on the Trufo API and follow its conventions —
`POST` with a JSON body, an `X-API-Key` or Bearer credential, and
`{"detail": "Code"}` errors. See [api_trufo.md](api_trufo.md).

### Certificate types

| Leaf type | Purpose | Maximum validity |
| --------- | ------- | ---------------- |
| `c2pa-l1` | Production C2PA claim signing, assurance level 1 | 366 days |
| `c2pa-l2` | Production C2PA claim signing, assurance level 2 | 90 days |
| `c2pa-l1-test` | Test C2PA claim signing, assurance level 1 | 366 days |
| `c2pa-l2-test` | Test C2PA claim signing, assurance level 2 | 90 days |
| `cawg-interim` | Production CAWG identity signing | 366 days |
| `cawg-interim-test` | Test CAWG identity signing | 366 days |

Level 2 requires hardware-backed key protection; contact
[support@trufo.ai](mailto:support@trufo.ai) to enable it for your product.

A certificate is issued at the maximum validity unless the enrollment requests a
shorter `validity_days`. Test leaf types are issued by a separate test CA: they are
structurally valid but deliberately outside the production trust chain, and
conformant validators will not accept them.

### Accepted keys

CSR public keys must be **EC P-256 or EC P-384**; **P-256 is recommended** for
claim-signing leaves — it is the widest-supported curve across C2PA validators.
RSA, Ed25519, and P-521 keys are rejected with `400 KeyTypeNotAllowed`. (Instance credentials, which authenticate
enrollment requests, use a different key set — see
[Instance credentials](#instance-credentials).)

### Enrollment in one picture

```
Instance credential  ──►  POST /ra/c2pa/csr-jwt          (Trufo API: authorizes you)
                              │  csr_jwt (300s lifetime)
                              ▼
PKCS#10 CSR ─────────►  POST /.well-known/est/…/simpleenroll   (CA: issues the cert)
                              │
                              ▼
                        PKCS#7 chain (leaf + CA chain)
```

Production enrollment requires, in order: completed Organization Validation, an
approved Product Validation for the generator product, an active subscription, a
registered instance, and a registered instance credential.

---

## Certificate Authority

### `GET /.well-known/est/{leaf_type}/cacerts`

Retrieve the CA chain for a leaf type (RFC 7030).

**Auth:** none.

**Response (200):** `application/pkcs7-mime; smime-type=certs-only` — base64-encoded
DER PKCS#7 containing the issuing CA followed by the root.

**Errors:** `404 UnknownLeafType`.

### `POST /.well-known/est/{leaf_type}/simpleenroll`

Enroll a certificate (RFC 7030 simpleenroll).

**Auth:** HTTP Basic with an **empty username** and the CSR JWT as the password —
`Authorization: Basic base64(":" + csr_jwt)`.

**Headers:** `Content-Type: application/pkcs10`.

**Body:** base64-encoded DER PKCS#10 CSR (no PEM armor).

**Response (200):** `application/pkcs7-mime; smime-type=certs-only` — base64-encoded
DER PKCS#7 containing the issued leaf followed by the CA chain.

**Errors:**

| Status | `detail` | Meaning |
| ------ | -------- | ------- |
| 401 | `MissingAuth` | No Basic credential |
| 401 | `MalformedJWT`, `JWTExpired`, `InvalidSignature`, `InvalidAudience`, `MissingClaim`, `JWTDecodeError` | CSR JWT rejected |
| 401 | `UnknownLeafType`, `LeafTypeDisabled`, `InvalidDistinguishedName`, `InvalidValidityDays`, `ValidityExceedsMax`, `InvalidRecordId`, `InvalidInstanceId`, `InvalidIssuer`, `InvalidIat` | CSR JWT claims rejected (several may be joined with `;`) |
| 401 | `LeafTypeMismatch` | JWT `leaf_type` differs from the path |
| 401 | `JTIAlreadyUsed` | The CSR JWT was already redeemed (production only) |
| 400 | `InvalidContentType`, `InvalidCSR`, `InvalidCSRSignature`, `KeyTypeNotAllowed` | Request or CSR malformed |
| 404 | `UnknownLeafType` | Unknown path segment |
| 409 | `PublicKeyAlreadyUsed` | That public key already has a certificate — generate a fresh key pair |

The certificate subject comes entirely from the CSR JWT's `distinguished_name`, not
from the CSR. Test leaf types prefix the common name with `[TESTING] `.

### CSR JWT

The CSR JWT authorizes one enrollment. It is HS256, audience `tca-est`, and lives
300 seconds.

| Claim | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `iss` | string | Yes | `"trufo"` |
| `sub` | string | Yes | Subscriber organization id |
| `aud` | string | Yes | `"tca-est"` |
| `jti` | string | Yes | Unique token id; redeemed once (production) |
| `iat`, `exp` | integer | Yes | Issued-at and expiry (UNIX seconds) |
| `leaf_type` | string | Yes | Must equal the path segment |
| `distinguished_name` | object | Yes | Subject fields; `O` and `CN` required, `C`, `ST`, `L`, `OU` optional |
| `validity_days` | integer | No | 1 to the type maximum; omitted means the maximum |
| `record_id` | string | C2PA only | Product record UUID, embedded in the certificate |
| `instance_id` | string | C2PA only | Issuing instance id |

For production, Trufo's RA mints this token for you (see
[CSR JWT issuance](#csr-jwt-issuance)); you never construct it yourself.

### Test enrollment

Test certificates need no account, organization, or validation. The CSR JWT is
signed with the publicly known HMAC secret `hello-trufo` (HS256), using
`sub: "test-account"` and a test leaf type. 

`request_c2pa_test_cert()` and `request_cawg_test_cert()` in the Python SDK perform
the whole flow.

### CA certificate downloads

Unauthenticated `GET` endpoints returning a single DER certificate
(`application/pkix-cert`). These are the AIA CA-Issuers URLs referenced by issued
certificates; fetch them to build a trust store or complete a chain.

| Path | Certificate |
| ---- | ----------- |
| `/root-ca.crt` | Trufo C2PA Root CA — the trust anchor |
| `/c2pa-ca.crt` | C2PA Claim Signing CA — issuer of `c2pa-l1` leaves |
| `/ctsa-ca.crt` | C2PA Timestamping CA — issuer of TSA leaves |
| `/temp-cawg-ca.crt` | Interim CAWG Identity CA — issuer of `cawg-interim` leaves |

---

## OCSP

Certificate revocation status, RFC 6960. No authentication.

| Method and path | Description |
| --------------- | ----------- |
| `POST /` | DER OCSP request in the body; the issuer is identified from the request |
| `GET /{base64url_request}` | GET binding; base64url or standard base64, padded or not |
| `POST /c2pa`, `/cawg`, `/ctsa`, `/root` | Issuer-pinned variants |
| `GET /c2pa/{b64}`, `/cawg/{b64}`, `/ctsa/{b64}`, `/root/{b64}` | Issuer-pinned GET bindings |

**Headers:** `Content-Type: application/ocsp-request`; responses are
`application/ocsp-response`.

Build the request against the certificate's **direct issuing CA**, not the responder
certificate. Certificates carry the base endpoint in their AIA extension; the
issuer-pinned routes are optional and reject requests for a different issuer.

| Status | Meaning |
| ------ | ------- |
| `GOOD` | Not revoked |
| `REVOKED` | Revoked; carries the revocation time and, when recorded, a reason |
| `UNKNOWN` | The serial is not known to the identified issuer |
| `UNAUTHORIZED` | The request does not correspond to an issuer this responder answers for |
| `TRY_LATER` | Status temporarily unavailable; retry |

Responses are valid for 7 days (`thisUpdate` to `nextUpdate`) and are cached and
shared, so nonces are not echoed. Malformed requests return `400` with a plain-text
body.

The `root` profile answers for intermediate CA certificates; the others answer for
end-entity certificates of that type.

---

## Timestamp Authority

### `POST https://tsa.trufo.ai/`

RFC 3161 timestamping.

**Auth:** `X-API-Key` with a `tsa`-scoped key.

**Headers:** `Content-Type: application/timestamp-query`.

**Body:** DER `TimeStampReq`, at most 1024 bytes.

**Response (200):** `application/timestamp-reply` — DER `TimeStampResp`. Tokens are
RFC 3161 v2 with `signingCertificateV2`, as required by C2PA 2.2+. Accepted digest
algorithms: SHA-256, SHA-384, SHA-512.

**Errors:**

| Status | Body | Meaning |
| ------ | ---- | ------- |
| 401 | `MissingAPIKey`, `InvalidAPIKey`, `APIKeyRevoked`, `APIKeyExpired`, `InvalidAPIKeyScope` | Credential problem |
| 403 | `OrgNotAllowed` | The key's organization is not permitted on this endpoint (dedicated endpoints) |
| 400 | `InvalidContentType`, `EmptyRequestBody` | Malformed request |
| 413 | `RequestTooLarge` | Body exceeds 1024 bytes |

A malformed or unsupported `TimeStampReq` returns HTTP 200 carrying an RFC 3161
rejection (`badDataFormat`, or `badAlg` for an unsupported digest) rather than an
HTTP error — inspect the `TimeStampResp` status.

`GET /policy` returns the policy OID and supported digest algorithms as JSON.

Organizations provisioned with a dedicated timestamp endpoint call
`https://{your-host}.tsa.trufo.ai/` instead. It speaks the identical protocol and
takes the same `tsa` key; the endpoint accepts only its own organization's keys and
returns `403 OrgNotAllowed` otherwise.

### Test endpoint

`POST https://test.tsa.trufo.ai/` speaks the identical protocol with **no API key**.
Its responses carry the Trufo test policy OID `1.3.6.1.4.1.62524.2.1` and are signed
by a self-signed certificate outside the production chain: they verify
mechanically but are **not** trusted for production or C2PA use, and the endpoint
carries no availability guarantee. Use it to exercise an integration before
obtaining a `tsa` key.

---

## Registration Authority

These endpoints run on the Trufo API and follow its conventions
([api_trufo.md](api_trufo.md)): `POST` with JSON, an MFA-verified access token, and
an organization role. They authorize certificate enrollment for your own generator
product.

### Validation prerequisites

Two validations gate production enrollment:

| Validation | Scope | Establishes | Managed at |
| ---------- | ----- | ----------- | ---------- |
| Organization Validation (OV) | Organization | Your legal identity — supplies the certificate's `O` and `C` | [api_trufo.md](api_trufo.md#accounts-and-organizations) |
| Product Validation (PV) | Generator product | The product's conformance and assurance level — supplies `CN` and the record id | Below |

Both must be **active** (approved and unexpired) at the moment of enrollment.

### Generator products

A generator product represents one C2PA-producing product. Products are created in
the [Trufo dashboard](https://app.trufo.ai) as part of submitting a Product
Validation application; there is no API to create one.

| Endpoint | Auth | Request | Response |
| -------- | ---- | ------- | -------- |
| `POST /gproduct/list` | MFA, member+ | `oid` (required by the schema; the server uses your credential's organization) | `gproducts[]` with `gp_id`, `name`, `implementation`, `pv_status`, `pv_active`, `validated_expires_at`, `cancel_at` |
| `POST /gproduct/info` | MFA, member+ | `gp_id` | `gp_id`, `oid`, `name`, `created_by`, `created_at` |
| `POST /gproduct/info/edit` | MFA, owner/admin | `gp_id`, `name` | `status` |
| `POST /gproduct/cancel` | MFA, owner/admin | `gp_id` | `gp_id`, `cancel_at`, `removed` |

**Errors:** `404 GProductNotFound`, `403 OrgMismatch`, `400 NoFieldsToUpdate`,
`400 GPAlreadyCancelled`.

### Product Validation

Product Validation establishes that a generator product meets C2PA conformance and
assurance requirements. It is submitted and tracked in the
[dashboard](https://app.trufo.ai): the application carries legal attestations that a
person must make, so it is not a programmatic flow.

What matters for integration: the product's PV must be **approved and unexpired**
before instances can be created or certificates issued, and the approved record
supplies the certificate's common name and the product record id embedded in every
certificate it signs. Endpoints that require it return `403 PVNotActive` or
`400 ProductNotValidated`.

### Instances

An instance is one signing identity within a validated product: it holds its own
credentials and is issued its own certificates. Model one instance per independent
key holder — a single signing service, one regional server with its own HSM key, or
one device in a fleet. Deployments with many independent keys register many
instances.

| Endpoint | Auth | Request | Response |
| -------- | ---- | ------- | -------- |
| `POST /gproduct/instance/create` | MFA, owner/admin | `gp_id`, `name` | `gpi_id` (201) |
| `POST /gproduct/instance/list` | MFA, member+ | `gp_id` | `instances[]` with `gpi_id`, `name`, `record_id` |
| `POST /gproduct/instance/info` | MFA, member+ | `gpi_id` | Instance detail |
| `POST /gproduct/instance/edit` | MFA, owner/admin | `gpi_id`, `name` | `status` |
| `POST /gproduct/instance/delete` | MFA, owner/admin | `gpi_id` | `status` |

**Errors:** `404 GProductNotFound`, `404 InstanceNotFound`, `400 ProductNotValidated`,
`403 PVNotActive`, `403 OVNotActive`, `403 SubscriptionRequired`,
`403 BillingNotActive`, `403 GPCancelled`.

### Instance credentials

A credential is a public key you register for an instance; its private key signs the
client assertion that requests a CSR JWT. Private keys never leave your systems.

| Endpoint | Auth | Request | Response |
| -------- | ---- | ------- | -------- |
| `POST /gproduct/instance/credential/register` | MFA, owner/admin | `gpi_id`, `public_key_pem`, `key_algorithm` (`ES256` or `EdDSA`), optional `label` | `gpic_id` (201) |
| `POST /gproduct/instance/credential/list` | MFA, member+ | `gpi_id` | `credentials[]` with `gpic_id`, `gpi_id`, `key_algorithm`, `label`, `created_at`, `revoked`, `revoked_at` |
| `POST /gproduct/instance/credential/edit` | MFA, owner/admin | `gpic_id`, `label` | `status` |
| `POST /gproduct/instance/credential/revoke` | MFA, owner/admin | `gpic_id` | `status` |

Accepted keys: **EC P-256** (`ES256`) or **Ed25519** (`EdDSA`); the declared
algorithm must match the key. An instance may hold at most **two active
credentials**, which is what makes key rotation possible: register the replacement,
cut over, then revoke the old one.

**Errors:** `400` with an actionable message when the two-active-credential cap
is reached (revoke an existing credential first), `400 InvalidPublicKey`,
`400 UnsupportedKeyAlgorithm`, `400 AlgorithmMismatch`, `400 AlreadyRevoked`,
`404 InstanceNotFound`, `404 CredentialNotFound`.

### CSR JWT issuance

#### `POST /ra/c2pa/csr-jwt`

Exchange an instance-credential assertion for a CSR JWT.

**Auth:** the client assertion itself — no API key or access token.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `client_assertion` | string | Yes | JWS signed by the instance credential's private key |
| `leaf_type` | string | Yes | `c2pa-l1` |
| `validity_days` | integer | No | 1 to the type maximum |

**Client assertion claims** — algorithm `ES256` or `EdDSA`, lifetime at most 300
seconds (60 is recommended):

| Claim | Value |
| ----- | ----- |
| `iss` | Your instance id (`gpi_…`) |
| `sub` | The credential id (`gpic_…`) whose key signs the assertion |
| `aud` | `"trufo-ra"` |
| `iat`, `exp` | Issued-at and expiry |

**Response (200):** `csr_jwt` — present it to EST simpleenroll as the Basic password.

An instance may hold at most **three active certificates** (revoked and expired
certificates do not count). The cap never blocks rotation: request a shorter
`validity_days`, or revoke the certificate being replaced.

**Errors:** `401 ClientAssertionFailed`, `400 InvalidLeafType`,
`400 InvalidValidityDays`, `403 LeafTypeNotAllowed`, `403 PVNotActive`,
`403 OVNotActive`, `403 BillingNotActive`, `403 GPCancelled`,
`403` with an actionable message when the three-active-certificate cap is
reached (revoke one, or wait for one to expire),
`404 InstanceNotFound`, `404 ProductNotFound`.

The subject is assembled from your validations, not from your request: `O` from the
organization's validated legal name (or verified DBA), `C` from its registration
country, `CN` from the product name, `OU` from the product's organizational unit.

#### `POST /ra/cawg-interim/csr-jwt`

Issue a CSR JWT for an organization-level CAWG identity certificate. No instance or
credential is involved.

**Auth:** MFA-verified access token, owner/admin (`request_cawg_cert`).

**Request:** optional `validity_days` (1–366). The leaf type is always
`cawg-interim`.

**Response (200):** `csr_jwt`.

**Errors:** `400 InvalidValidityDays`, `403 NoEligiblePlan` (requires the CAWG
Organization Certificate plan), `403 OVNotActive`, `403 OrgNotValidated`.

### Domain Validation

Domain Validation (DV) proves your organization controls a domain. It is required
for two C2PA features that carry your own namespace:

- **Custom assertions** — embedding an assertion under a reverse-DNS label such as
  `com.example.metadata` requires DV for `example.com`.
- **Custom redaction reasons** — a non-preset, reverse-DNS `reason` on a `redact`
  action requires DV for the same domain.

Domains are validated in the [dashboard](https://app.trufo.ai) by publishing a DNS
record Trufo provides. Once active, signing requests using that namespace succeed;
without it they return `403 InvalidC2PACustomDomain`. See
[custom assertions](api_c2pa.md#custom).

### Certificates

| Endpoint | Auth | Request | Response |
| -------- | ---- | ------- | -------- |
| `POST /cert/list` | MFA, member+ | `{}` | `certs[]` with `serial_number`, `leaf_type`, `issue_time`, `expiry_time`, `revocation_status`, `revocation_reason`, `revocation_time`, `revocable`, and the issuing `gpi_id` / `gpi_name` / `gp_id` / `gp_name` where applicable |
| `POST /cert/revoke` | MFA, owner/admin | `serial_number`, `revocation_reason`, optional `revocation_time` | `status` |

`POST /cert/revoke` requires an MFA-verified user access token from an organization
owner or admin. A developer API key alone is insufficient.

The optional `revocation_time` sets the effective revocation cutoff. Supply an
ISO 8601 date and time with `Z` or an explicit UTC offset. Values are normalized
to UTC and must not be in the future. Omitting the field (or passing `null`)
uses the time the revocation is processed. Invalid timestamps return `422`.
The certificate list returns the effective cutoff as `revocation_time`.

```json
{
  "serial_number": "<certificate-serial-hex>",
  "revocation_reason": "key_compromise",
  "revocation_time": "2026-09-10T14:30:00-04:00"
}
```

This example sets the effective cutoff to `2026-09-10T18:30:00Z`.
The time cannot be changed by submitting another revocation request: an
already-revoked certificate returns `400 AlreadyRevoked`.

**Revocation reasons:** `unspecified`, `key_compromise`, `affiliation_changed`,
`superseded`, `cessation_of_operation`.

**Errors:** `404 NotFound`, `400 NotRevocable`, `400 InvalidRevocationReason`,
`400 AlreadyRevoked`, `502 RevocationFailed`.

Revocation is permanent and propagates through OCSP. A `502` means the request did
not complete and **must not be retried blindly** — re-list your certificates to
check the outcome first.

---

## Reference

- Certificates quickstart: [../quickstart/1_certs.md](../quickstart/1_certs.md)
- Platform conventions, OV, and API keys: [api_trufo.md](api_trufo.md)
- C2PA signing: [api_c2pa.md](api_c2pa.md)
