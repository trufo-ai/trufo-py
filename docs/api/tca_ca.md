# TCA Certificate Authority (CA)

Certificate enrollment, revocation checking, and timestamping via the Trufo Certificate Authority.

> Auth and content types vary per endpoint — specified in each section.
> See [api_auth.md](api_auth.md) for general conventions.

---

## Certificate Types

| Leaf Type | Value | Description | Max Validity |
|-----------|-------|-------------|--------------|
| C2PA Level 1 | `c2pa-l1` | Production C2PA signing | 366 days |
| C2PA Level 2 | `c2pa-l2` | Production C2PA signing (extended) | 90 days |
| C2PA Level 1 Test | `c2pa-l1-test` | Test C2PA signing | 366 days |
| C2PA Level 2 Test | `c2pa-l2-test` | Test C2PA signing | 90 days |
| CAWG Interim | `cawg-interim` | Production CAWG identity signing | 366 days |
| CAWG Interim Test | `cawg-interim-test` | Test CAWG identity signing | 366 days |
| TSA | `ctsa` | Production timestamping | 4110 days |
| TSA Test | `ctsa-test` | Test timestamping | 4110 days |

Maximum validity follows C2PA Certificate Policy v0.1 §7.1.2. A test leaf type
carries the same cap as the production type it mirrors. A shorter validity may
be requested when the certificate is enrolled.

These values are defined in `trufo.crypt.tca_certs.LeafType`.

---

## EST Endpoints (RFC 7030)

All EST endpoints are at `https://ca.trufo.ai`.

### `POST /.well-known/est/{leaf_type}/simpleenroll`

Enroll a certificate via EST simpleenroll.

**Auth:** HTTP Basic (CSR JWT).
**Headers:** `Content-Type: application/pkcs10`, `Authorization: Basic base64(":csr_jwt")`.

For production leaf types, the CSR JWT is obtained from the RA (see [tca_ra.md](tca_ra.md)). For test leaf types, it is signed with the publicly known HMAC secret `hello-trufo`.

**Body:** Base64-encoded DER PKCS#10 CSR.

**Response (200):** Base64-encoded DER PKCS#7 containing the issued certificate chain (leaf + intermediates).

### `GET /.well-known/est/{leaf_type}/cacerts`

Retrieve the CA certificate chain for a given leaf type.

**Auth:** None.

**Response:** Base64-encoded DER PKCS#7 containing the CA certificates.

---

## Test Certificate Enrollment

Test certificates can be enrolled without an account or organization. The CSR JWT is signed with the publicly known HMAC secret (`hello-trufo`) using HS256.

### Test CSR JWT Format

**Header:**

```json
{ "alg": "HS256", "typ": "JWT" }
```

**Payload:**

| Claim | Type | Description |
|-------|------|-------------|
| `iss` | string | `"trufo"` |
| `sub` | string | `"test-account"` |
| `aud` | string | `"tca-est"` |
| `jti` | string | Unique ID (UUIDv7) |
| `iat` | integer | Current UNIX timestamp |
| `exp` | integer | Current UNIX timestamp + 300 |
| `leaf_type` | string | Test leaf type value |
| `distinguished_name` | object | Certificate subject |
| `record_id` | string | Unique ID (UUIDv7) |
| `instance_id` | string | `"gpi_"` + UUIDv7 |

**`leaf_type`** — allowed test values:

| Value | Description |
|-------|-------------|
| `"c2pa-l1-test"` | C2PA Level 1 test signing |
| `"c2pa-l2-test"` | C2PA Level 2 test signing |
| `"cawg-interim-test"` | CAWG interim identity test signing |
| `"ctsa-test"` | TSA test timestamping |

**`distinguished_name`** — X.509 subject fields:

| Key | Description |
|-----|-------------|
| `"O"` | Organization name |
| `"CN"` | Common name |

For CAWG interim test certificates, the payload also includes:

| Claim | Type | Description |
|-------|------|-------------|
| `linkage_ids` | array | Empty array `[]` |

### Flow

1. Build a test CSR JWT (signed with `hello-trufo`)
2. Generate a leaf key pair and build a PKCS#10 CSR
3. Submit to `POST /.well-known/est/{leaf_type}/simpleenroll` (see above)
4. Extract the certificate chain from the PKCS#7 response

---

## OCSP (Certificate Revocation)

### `POST https://ocsp.trufo.ai/`

Check certificate revocation status.

The base endpoint automatically disambiguates the certificate type from the OCSP request issuer and routes the request to the corresponding OCSP responder for C2PA, CAWG, or CTSA certificates. Build the OCSP request with the certificate's direct issuing CA certificate, not with the OCSP responder certificate or a separate OCSP signing CA certificate.

**Auth:** None.
**Headers:** `Content-Type: application/ocsp-request`.

**Body:** DER-encoded OCSP request.

**Response:** DER-encoded OCSP response.

### `GET https://ocsp.trufo.ai/{base64url_request}`

The responder also supports the RFC 6960 HTTP GET binding. Base64url-encode the DER OCSP request with no padding and append it to the path.

### Profile-specific endpoints

Advanced callers may use explicit profile routes:

| Endpoint | Certificate profile |
|----------|---------------------|
| `https://ocsp.trufo.ai/c2pa` | C2PA signing certificates |
| `https://ocsp.trufo.ai/cawg` | CAWG identity certificates |
| `https://ocsp.trufo.ai/ctsa` | C2PA timestamping certificates |

These routes reject requests whose issuer does not match the selected profile. Use the base endpoint unless you specifically need route-level profile enforcement.

Common response statuses:

| Status | Meaning |
|--------|---------|
| `GOOD` | Certificate is valid and not revoked |
| `REVOKED` | Certificate has been revoked |
| `UNKNOWN` | Certificate serial is not found for a recognized issuer |
| `UNAUTHORIZED` | Issuer is not recognized, or the issuer does not match an explicit profile route |

---

## TSA (Timestamp Authority)

### `POST https://tsa.trufo.ai/`

Request an RFC 3161 timestamp.

**Auth:** API key (tsa), passed in the `X-API-Key` header.

**Headers:**

| Header | Value |
|--------|-------|
| `Content-Type` | `application/timestamp-query` |
| `X-API-Key` | The `tsa`-scoped API key |

The API key is 64 characters (a 16-character key id followed by a 48-character
secret). It may optionally carry a human-readable scope prefix separated by a
colon, e.g. `tsa:<64-char-key>`; the prefix is a visual label only and is
stripped server-side, so both `tsa:<key>` and the bare `<key>` are accepted.

**Body:** DER-encoded timestamp request (`TimeStampReq`).

**Response:** DER-encoded timestamp response (`TimeStampResp`).

**Errors:**

| Status | Meaning |
|--------|---------|
| `401` | Missing, malformed, or invalid `X-API-Key` |
| `403` | Key is valid but its owning org is not permitted on this endpoint (dedicated / white-labeled endpoints only) |

---

### Test endpoint

`POST https://tsa.test.trufo.ai/`

A free, keyless test endpoint speaking the same RFC 3161 protocol: no `X-API-Key`
header, no signup. Responses are signed with a self-signed test certificate and
always carry the Trufo test policy OID (`1.3.6.1.4.1.62524.2.1`), so tokens
verify protocol-mechanically but are deliberately **not** trusted for production
or C2PA use. No availability SLA. Use it to exercise your integration before
requesting a `tsa` API key.

## Python SDK

| Function | Location | Description |
|----------|----------|-------------|
| `request_c2pa_test_cert()` | `trufo.api.tca.certs_test` | One-step test C2PA certificate enrollment |
| `request_cawg_test_cert()` | `trufo.api.tca.certs_test` | One-step test CAWG interim certificate enrollment |
| `build_csr()` | `trufo.crypt.tca_certs` | Build a PKCS#10 CSR from a leaf private key |
| `est_enroll()` | `trufo.crypt.tca_certs` | Submit CSR + CSR JWT to CA via EST simpleenroll |
| `extract_cert_chain()` | `trufo.crypt.tca_certs` | Extract PEM certificate chain from PKCS#7 response |
