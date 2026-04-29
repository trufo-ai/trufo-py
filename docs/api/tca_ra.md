# TCA Registration Authority (RA)

RA endpoints for managing generator products, instances, credentials, and requesting CSR JWTs for certificate enrollment. All RA endpoints are hosted at `https://api.trufo.ai`.

> **Default auth:** Access token (`Authorization: Bearer`).
> **Default content type:** `application/json`.
> See [api_auth.md](api_auth.md) for full header conventions.

---

## Generator Products

### `POST /gproduct/create`

Create a generator product.

**Auth:** Access token (org admin+, MFA).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `oid` | string | Yes | Organization ID |
| `name` | string | Yes | Human-readable product name |

**Response (201):**

```json
{
  "gp_id": "gp_..."
}
```

### `POST /gproduct/list`

List generator products for an organization.

**Auth:** Access token (org member).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `oid` | string | Yes | Organization ID |

### `POST /gproduct/info`

Get generator product details.

**Auth:** Access token (org member).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gp_id` | string | Yes | Generator product ID |

### `POST /gproduct/info/edit`

Edit generator product metadata.

**Auth:** Access token (org admin+).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gp_id` | string | Yes | Generator product ID |
| `name` | string | No | New product name |

### `POST /gproduct/delete`

Delete a generator product.

**Auth:** Access token (org admin+, MFA).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gp_id` | string | Yes | Generator product ID |

---

## Instances

Instances represent deployment environments of a generator product (e.g., production server, staging server).

### `POST /gproduct/instance/create`

Create a generator product instance. Requires an active subscription.

**Auth:** Access token (org admin+, MFA).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gp_id` | string | Yes | Generator product ID |
| `name` | string | Yes | Human-readable instance name |

**Response (201):**

```json
{
  "gpi_id": "gpi_..."
}
```

### `POST /gproduct/instance/list`

List instances for a generator product.

**Auth:** Access token (org member).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gp_id` | string | Yes | Generator product ID |

### `POST /gproduct/instance/info`

Get instance details.

**Auth:** Access token (org member, MFA).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gpi_id` | string | Yes | Instance ID |

### `POST /gproduct/instance/delete`

Delete an instance.

**Auth:** Access token (org admin+, MFA).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gpi_id` | string | Yes | Instance ID |

---

## Credentials

Credentials are public keys registered to an instance. The corresponding private key signs client assertion JWTs for certificate enrollment. Each instance supports up to 2 active credentials (for key rotation).

### `POST /gproduct/instance/credential/register`

Register an instance credential (public key).

**Auth:** Access token (org admin+, MFA).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gpi_id` | string | Yes | Instance ID |
| `public_key_pem` | string | Yes | PEM-encoded public key |
| `key_algorithm` | string | Yes | `"ES256"` or `"EdDSA"` |
| `label` | string | Yes | Human-readable label |

**`public_key_pem`** — must be a valid PEM public key. The server parses the key and verifies it matches `key_algorithm`:

| `key_algorithm` | Key Type | Curve |
|-----------------|----------|-------|
| `"ES256"` | EC | NIST P-256 (secp256r1) |
| `"EdDSA"` | OKP | Ed25519 |

Other key types (RSA, wrong EC curves) are rejected. A mismatch between the declared algorithm and the actual key returns `400 AlgorithmMismatch`. Each instance supports at most 2 active (non-revoked) credentials.

**Response (201):**

```json
{
  "gpic_id": "gpic_..."
}
```

### `POST /gproduct/instance/credential/list`

List credentials for an instance.

**Auth:** Access token (org member, MFA).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gpi_id` | string | Yes | Instance ID |

### `POST /gproduct/instance/credential/revoke`

Revoke an instance credential.

**Auth:** Access token (org admin+, MFA).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gpic_id` | string | Yes | Credential ID |

---

## CSR JWT

Request a CSR JWT from the RA. The CSR JWT authorizes certificate enrollment via EST (see [tca_ca.md](tca_ca.md)).

### `POST /ra/c2pa/csr-jwt`

**Auth:** Client assertion (instance credential) — not an access token.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `client_assertion` | string | Yes | JWT signed with instance private key |
| `leaf_type` | string | Yes | Certificate type |
| `validity_days` | integer | No | Requested validity in days |

**`leaf_type`** — allowed values for C2PA:

| Value | Description | Max Validity |
|-------|-------------|--------------|
| `"c2pa-l1"` | C2PA Level 1 production signing | 366 days |
| `"c2pa-l2"` | C2PA Level 2 production signing | 90 days |

**`validity_days`** — must be between 1 and the max for the leaf type. Defaults to the max if omitted.

**Response (200):**

```json
{
  "csr_jwt": "eyJhbG..."
}
```

### Client Assertion JWT Format

The `client_assertion` is a JWT signed by the instance's registered private key.

**Header:**

```json
{ "alg": "ES256", "typ": "JWT" }
```

**Payload:**

| Claim | Type | Description |
|-------|------|-------------|
| `iss` | string | Instance ID (`gpi_...`) |
| `sub` | string | Credential ID (`gpic_...`) |
| `aud` | string | `"trufo-ra"` |
| `iat` | integer | Current UNIX timestamp |
| `exp` | integer | Expiration — recommended `iat + 60`, hard max `iat + 300` |

### Errors

| Code | Detail | Description |
|------|--------|-------------|
| 400 | `InvalidLeafType` | Unsupported leaf type value |
| 400 | `InvalidValidityDays` | Exceeds maximum for the leaf type |
| 401 | `ClientAssertionFailed` | Signature verification failed |
| 403 | `BillingNotActive` | No active subscription |
| 403 | `GPCancelled` | Generator product is cancelled |
| 403 | `ProductNotValidated` | Product Validation not completed |
| 403 | `PVNotActive` | Product Validation not active |
| 403 | `OVNotActive` | Organization Validation not active |
| 404 | `InstanceNotFound` | Instance ID not found |
| 404 | `ProductNotFound` | Generator product not found |

### Prerequisites (Production)

Production certificate enrollment requires:

1. An authenticated account with an organization
2. Organization Validation (OV) approved
3. A Generator Product with Product Validation (PV) approved
4. An active subscription
5. An instance with a registered credential (public key)

### `POST /ra/cawg-interim/csr-jwt`

Request a CSR JWT for a CAWG interim certificate. Org-scoped: there is no gproduct or instance — the cert identifies the calling organization itself.

**Auth:** Access token (org admin+, MFA).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `validity_days` | integer | No | Requested validity in days. Range 1–366; defaults to 366 if omitted. |

The CSR JWT is always issued for `leaf_type = "cawg-interim"`. The cert subject DN is derived server-side from the org's validated_info — the caller does not specify it.

**Response (200):**

```json
{
  "csr_jwt": "eyJhbG..."
}
```

### CAWG Errors

| Code | Detail | Description |
|------|--------|-------------|
| 400 | `InvalidValidityDays` | `validity_days` outside [1, 366] |
| 401 | `MissingToken` / `InvalidToken` / `TokenExpired` | Bearer JWT missing or invalid |
| 403 | `MFARequired` | MFA not verified on the access token |
| 403 | `InsufficientPermissionForAction` | Caller lacks the `request_cawg_cert` permission (member role, etc.) |
| 403 | `NotOrgMember` | Caller is not in any organization |
| 403 | `NoEligiblePlan` | Org has no active `cawg_cert_organization` subscription |
| 403 | `OVNotActive` | Organization Validation not approved |
| 403 | `OVExpired` | Organization Validation has expired |
| 403 | `OrgNotValidated` | Org `validated_info` is missing |

### CAWG Prerequisites (Production)

Production CAWG interim certificate enrollment requires:

1. An authenticated account with an organization
2. The caller's role in the org is `owner` or `admin`
3. MFA verified on the access token
4. Organization Validation (OV) approved and not expired
5. An active `cawg_cert_organization` subscription

---

## Python SDK

Some useful functions in the codebase:

| Function | Location | Description |
|----------|----------|-------------|
| `create_instance()` | `trufo.api.tca.certs_c2pa` | Create an instance via `TrufoSession` |
| `register_credential()` | `trufo.api.tca.certs_c2pa` | Register a credential via `TrufoSession` |
| `request_c2pa_cert()` | `trufo.api.tca.certs_c2pa` | End-to-end production C2PA enrollment (assertion → CSR JWT → EST → cert chain) |
| `request_cawg_interim_cert()` | `trufo.api.tca.certs_cawg_interim` | End-to-end production CAWG interim enrollment (CSR JWT → EST → cert chain) |
