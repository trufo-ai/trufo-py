# TCA Registration Authority (RA) — API Reference

RA endpoints for managing generator products, instances, credentials, and requesting CSR JWTs for certificate enrollment. All RA endpoints are hosted at `https://api.trufo.ai`.

> **Default auth:** Access token (`Authorization: Bearer`).
> **Default content type:** `application/json`.
> See [api_access.md](api_access.md) for full header conventions.

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
| `key_algorithm` | string | Yes | `"ES256"` (EC P-256) or `"EdDSA"` (Ed25519) |
| `label` | string | Yes | Human-readable label |

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

### `POST /ra/csr-jwt`

**Auth:** Client assertion (instance credential) — not an access token.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `client_assertion` | string | Yes | JWT signed with instance private key |
| `leaf_type` | string | Yes | Certificate type (see [tca_ca.md](tca_ca.md) for values) |
| `validity_days` | integer | No | Requested validity in days (server enforces max) |

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
| `exp` | integer | Current UNIX timestamp + 60 |

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

---

## Python SDK

Some useful functions in the codebase:

| Function | Location | Description |
|----------|----------|-------------|
| `create_instance()` | `trufo.api.tca.c2pa_cert` | Create an instance via `TrufoSession` |
| `register_credential()` | `trufo.api.tca.c2pa_cert` | Register a credential via `TrufoSession` |
| `request_c2pa_cert()` | `trufo.api.tca.c2pa_cert` | End-to-end production enrollment (assertion → CSR JWT → EST → cert chain) |
