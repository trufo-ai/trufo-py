# TCA Certificate Authority (CA) — API Reference

Certificate enrollment, revocation checking, and timestamping via the Trufo Certificate Authority.

> Auth and content types vary per endpoint — specified in each section.
> See [api_access.md](api_access.md) for general conventions.

---

## Certificate Types

| Leaf Type | Value | Description | Max Validity |
|-----------|-------|-------------|--------------|
| C2PA Level 1 | `c2pa-l1` | Production C2PA signing | 398 days |
| C2PA Level 2 | `c2pa-l2` | Production C2PA signing (extended) | 398 days |
| C2PA Level 1 Test | `c2pa-l1-test` | Test C2PA signing | 90 days |
| C2PA Level 2 Test | `c2pa-l2-test` | Test C2PA signing | 90 days |
| CAWG Interim | `cawg-interim` | Production CAWG identity signing | 398 days |
| CAWG Interim Test | `cawg-interim-test` | Test CAWG identity signing | 90 days |
| TSA | `ctsa` | Production timestamping | 398 days |
| TSA Test | `ctsa-test` | Test timestamping | 90 days |

These values are defined in `trufo.api.tca.tca_utils.LeafType`.

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
| `leaf_type` | string | Test leaf type value (e.g. `"c2pa-l1-test"`) |
| `distinguished_name` | object | `{ "O": "...", "CN": "..." }` |
| `record_id` | string | Unique ID (UUIDv7) |
| `instance_id` | string | `"gpi_"` + UUIDv7 |

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

**Auth:** None.
**Headers:** `Content-Type: application/ocsp-request`.

**Body:** DER-encoded OCSP request.

**Response:** DER-encoded OCSP response.

---

## TSA (Timestamp Authority)

### `POST https://tsa.trufo.ai/`

Request an RFC 3161 timestamp.

**Auth:** API key (tsa).
**Headers:** `Content-Type: application/timestamp-query`.

**Body:** DER-encoded timestamp request.

**Response:** DER-encoded timestamp response.

---

## Python SDK

| Function | Location | Description |
|----------|----------|-------------|
| `request_c2pa_test_cert()` | `trufo.api.tca.test_cert` | One-step test C2PA certificate enrollment |
| `request_cawg_test_cert()` | `trufo.api.tca.test_cert` | One-step test CAWG interim certificate enrollment |
| `build_csr()` | `trufo.api.tca.tca_utils` | Build a PKCS#10 CSR from a leaf private key |
| `est_enroll()` | `trufo.api.tca.tca_utils` | Submit CSR + CSR JWT to CA via EST simpleenroll |
| `extract_cert_chain()` | `trufo.api.tca.tca_utils` | Extract PEM certificate chain from PKCS#7 response |
