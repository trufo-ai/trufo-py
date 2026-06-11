# C2PA Signing API

Endpoints for C2PA manifest generation and management of reusable assertion records.

- **Base URL:** `https://api.trufo.ai`
- **Test paths:** `/test/<route>` — signed with a test certificate; outputs may not be recognized by C2PA validators
- **Production paths:** `/<route>` — signed with a proper certificate; outputs are recognized by conformant C2PA validators; same schema as test

**Default Headers** (unless overridden by a specific endpoint):

- **Auth:** API key (`X-API-Key`) or access token (`Authorization: Bearer`)
- **Content type:** `application/json`

## Endpoints

Authentication is per-endpoint. The table below summarizes each endpoint; legends follow.

**Scope** — the API-key scope required when authenticating with a key: `prod` = `c2pa-sign-prod`, `test` = `c2pa-sign-test`. An account access token may be used in place of an API key on any of these endpoints (it requires the `c2pa_sign` permission and is scope-independent).

**Billing Product** — the required plan entitlement, or `—` if none. Gated endpoints return `403` when the caller's org lacks the plan.


| Endpoint                            | Scope       | Billing Product                  |
| ----------------------------------- | ----------- | -------------------------------- |
| **Signing**                         |             |                                  |
| `POST /c2pa/sign`                   | prod        | `c2pa_signing_api`               |
| `POST /test/c2pa/sign`              | test        | —                                |
| `POST /c2pa/io/get-s3-url`          | prod / test | `c2pa_signing_api` (prod only)   |
| **Assertion records**               |             |                                  |
| `POST /c2pa/ai-disclosure/add`      | prod / test | —                                |
| `POST /c2pa/ai-disclosure/list`     | prod / test | —                                |

The owning organization is inferred from the credential itself (the API key is bound to its org; an access token resolves to the caller's single org membership). Request bodies for c2pa endpoints do not take an `oid` field.

See [api_auth.md](api_auth.md) for full header conventions and the complete scope list, or the [Auth Quickstart](../quickstart/0_auth.md) for a setup guide.

---

## Common Workflows

### AIGC Labeling

See [2_ai_labeling.md](../quickstart/2_ai_labeling.md) for a quickstart guide for this use case.

### CAWG Publishing

See [3_cawg_publish.md](../quickstart/3_cawg_publish.md) for a quickstart guide for this use case.

### Remote (Distributed) Signing

See [4_distributed_signing.md](../quickstart/4_distributed_signing.md) for a quickstart guide for this use case.

### Python SDK helpers

For direct byte uploads, use `sign_c2pa()` for production signing and `sign_c2pa_test()` for the test signer:

```python
from trufo.api.tps.sign_c2pa import sign_c2pa
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_PROD)
signed_bytes = sign_c2pa(
  api_key,
  media_bytes,
  assertions=[
    ["cawg_identity", {"cawg_identity_id": "org_interim"}],
  ],
)
```

For larger media, use the S3 convenience helper:

```python
from trufo.api.tps.sign_c2pa import sign_c2pa_via_s3

signed_bytes = sign_c2pa_via_s3(
  api_key,
  media_bytes,
  mime_type="image/jpeg",
  assertions=[
    ["cawg_identity", {"cawg_identity_id": "org_interim"}],
  ],
)
```

---

# Standard Signing

## `POST /c2pa/sign`, `POST /test/c2pa/sign`

Both endpoints share the same request/response schema. The production signer produces manifests recognized by conformant C2PA validators; the test signer produces manifests that are not.

### Request Body

| Field            | Type   | Required | Description                                                            |
| ---------------- | ------ | -------- | ---------------------------------------------------------------------- |
| `media_input`    | string | Yes*     | base64-encoded input media data                                        |
| `media_input_s3` | string | Yes*     | server-signed ephemeral S3 input reference from `/c2pa/io/get-s3-url`  |
| `actions`        | list   | No       | media processing instructions for the TPS to apply                     |
| `assertions`     | list   | No       | gathered assertions to include in the manifest                         |

\* Provide exactly one of `media_input` or `media_input_s3`.

#### `media_input`

Base64-encoded bytes of the input file. The supported MIME types are listed below; more will be added over time (upon request).

| Category | MIME types                                                                                                                              |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Image    | `image/jpeg`, `image/png`, `image/tiff`, `image/webp`, `image/avif`, `image/jxl`, `image/gif`, `image/x-adobe-dng`, `image/svg+xml`     |
| Video    | `video/mp4`, `video/quicktime`                                                                                                          |
| Audio    | `audio/mpeg`, `audio/flac`, `audio/wav`, `audio/aac`, `audio/mp4`                                                                       |
| Document | `application/pdf`                                                                                                                        |

#### `media_input_s3`

Opaque server-signed input reference returned by [`POST /c2pa/io/get-s3-url`](#post-c2paioget-s3-url). Use this mode for larger media or workflows that should avoid sending base64 media through the JSON request body.

The flow is:

1. Call `POST /c2pa/io/get-s3-url` with the source media MIME type.
2. Upload the source media bytes to the returned `upload_url` with `Content-Type` set to the same MIME type.
3. Call `POST /c2pa/sign` or `POST /test/c2pa/sign` with `media_input_s3`.
4. Download the signed output from the returned `media_output_s3` URL.

The Python SDK provides low-level helpers for each step and high-level helpers (`sign_c2pa_via_s3()` and `sign_c2pa_test_via_s3()`) that perform the full upload/sign/download sequence.

#### `actions`

Ordered list of `[action_name, params]` pairs. Each element of the `actions` list is a two-element array, and will be executed by the TPS in order.

| Action        | Params                           | Description                 |
| ------------- | -------------------------------- | --------------------------- |
| `"transcode"` | `{"target_mime_type": "<mime>"}` | transcode to target format  |
| `"publish"`   | `{}`                             | mark for final distribution |

#### `assertions`

Ordered list of `[assertion_name, params]` pairs. Each assertion is treated as a gathered assertion when signing the manifest. If `assertions` is provided, at least one `"cawg_identity"` entry must be present — the signer automatically references all gathered assertions through the identity assertion.

| Assertion         | Params                         | C2PA label             |
| ----------------- | ------------------------------ | ---------------------- |
| `"ai_disclosure"` | `{"ai_disclosure_id": "<id>", "set_source_type": false}` | `c2pa.ai-disclosure`   |
| `"cawg_metadata"` | `{"assertion": {…}}`           | `cawg.metadata`        |
| `"cawg_training"` | `{"assertion": {…}}`           | `cawg.training-mining` |
| `"cawg_identity"` | `{"cawg_identity_id": "<id>"}` | `cawg.identity`        |
| `"custom"`        | `{"label": "<reverse-dns-label>", "assertion": {…}}` | entity-specific label  |

##### `ai_disclosure`

Marks the content as AI-generated via a `c2pa.ai-disclosure` assertion. By default, the minimal assertion body `{"modelType": "c2pa.types.model"}` is used; to attach a richer pre-registered assertion (e.g. identifying a specific model, dataset, or content profile), first register it via [`POST /c2pa/ai-disclosure/add`](#post-c2paai-disclosureadd) and pass the returned `ai_disclosure_id`.

| Param               | Type   | Default        | Description                                                                                                                                          |
| ------------------- | ------ | -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ai_disclosure_id`  | string | `null`         | When omitted, the default body `{"modelType": "c2pa.types.model"}` is used. When set, must be the `ai_disclosure_id` of a previously stored assertion — form: `aidisc_<uuidv7>`. The stored body replaces the default. |
| `set_source_type`   | bool   | `false`        | When `true` and the input has no existing C2PA manifest, sets `digitalSourceType = trainedAlgorithmicMedia` on the ingredient. Also, see note below. |

> **Note on `set_source_type`:** Setting `digitalSourceType` within C2PA ingredients is new to C2PA v2.4 (§18.16.12.3) and is not yet supported by most existing validators today (e.g. having this field may make the manifest show up as "invalid"). The `c2pa.ai-disclosure` assertion alone suffices for AI labeling purposes, though for forwards-compatibility purposes you may want to set both. If your use case allows for validators to temporarily display "invalid" messaging, we recommend setting both. If not, then include only the ai_disclosure.

Default disclosure (no digitalSourceType):

```json
["ai_disclosure", {}]
```

Default disclosure with digitalSourceType:

```json
["ai_disclosure", {"set_source_type": true}]
```

Reference a pre-stored disclosure:

```json
["ai_disclosure", {"ai_disclosure_id": "aidisc_0193f7e0abcd7a11bcde01234567890a"}]
```

##### `cawg_metadata`

Embed CAWG creator metadata (JSON-LD). The `assertion` param is required and must include an `@context` mapping with allowed namespace prefixes.

```json
["cawg_metadata", {
  "assertion": {
    "@context": {
      "dc": "http://purl.org/dc/elements/1.1/"
    },
    "dc:creator": ["[CREATOR NAME]"]
  }
}]
```

Allowed namespace prefixes and their required URIs:

| Prefix         | URI                                           |
| -------------- | --------------------------------------------- |
| `Iptc4xmpCore` | `http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/` |
| `Iptc4xmpExt`  | `http://iptc.org/std/Iptc4xmpExt/2008-02-29/` |
| `dc`           | `http://purl.org/dc/elements/1.1/`            |
| `exif`         | `http://ns.adobe.com/exif/1.0/`               |
| `exifEX`       | `http://cipa.jp/exif/2.32/`                   |
| `pdf`          | `http://ns.adobe.com/pdf/1.3/`                |
| `pdfx`         | `http://ns.adobe.com/pdfx/1.3/`               |
| `photoshop`    | `http://ns.adobe.com/photoshop/1.0/`          |
| `tiff`         | `http://ns.adobe.com/tiff/1.0/`               |
| `xmp`          | `http://ns.adobe.com/xap/1.0/`                |

Any prefix not in this list, or a URI that doesn't match exactly, is rejected.

##### `cawg_training`

Declare AI training and data-mining permissions per CAWG spec. The `assertion` param must contain an `entries` dict (no other top-level keys).

```json
["cawg_training", {
  "assertion": {
    "entries": {
      "cawg.ai_training": { "use": "notAllowed" },
      "cawg.ai_inference": { "use": "allowed" },
      "cawg.data_mining": { "use": "constrained", "constraint_info": "See license terms." }
    }
  }
}]
```

Each entry must have:

- `use` — **required**, one of `"allowed"`, `"notAllowed"`, `"constrained"`.
- `constraint_info` — optional, non-empty string (typically provided when `use` is `"constrained"`).

##### `cawg_identity`

Attach a CAWG identity assertion.

| Param              | Type   | Required | Description                   |
| ------------------ | ------ | -------- | ----------------------------- |
| `cawg_identity_id` | string | Yes      | Identity provider identifier. |

Supported values for `cawg_identity_id`:

| Value         | Endpoint        | Description                                                                                                              |
| ------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `"test"`      | Test            | Signs with a shared Trufo test certificate. Outputs are not recognized by C2PA validators. |
| `"org_interim"` | Test, Prod    | Signs with a Trufo-hosted org-specific CAWG interim certificate. Requires the `cawg_cert_organization` billing plan. If your org has the plan but signing fails, contact support. |

##### `custom`

Embed a custom assertion using a validated domain (C2PA §6.2).

| Param       | Type   | Required | Description |
| ----------- | ------ | -------- | ----------- |
| `label`     | string | Yes      | Reverse-DNS assertion label, e.g. `com.example.custom-metadata`. The `c2pa.*` namespace and labels containing `__` are reserved and rejected. |
| `assertion` | object | Yes      | Assertion data (arbitrary JSON object). |

Requires the `c2pa_custom_domain` billing plan and an active domain-validation (DV) record for the base domain of the label (scope `c2pa-custom-assertion`). For example, to use the label `com.example.custom-metadata`, the org must have a DV record for `example.com`.

Multiple `"custom"` entries may be included in a single request; each is validated independently against the org's DV records.

```json
["custom", {"label": "com.example.custom-metadata", "assertion": {"internalId": 1234}}]
```

### Response (200)

Direct media response:

```json
{
  "media_output": "<base64-encoded signed media>"
}
```

S3 media response:

```json
{
  "media_output_s3": "<presigned download URL for signed media>"
}
```

---

## `POST /c2pa/io/get-s3-url`

Mint an ephemeral presigned S3 upload URL for C2PA signing. The returned `media_input_s3` reference is passed to `/c2pa/sign` or `/test/c2pa/sign` after upload.

### Request Body

| Field       | Type   | Required | Description                                                |
| ----------- | ------ | -------- | ---------------------------------------------------------- |
| `mime_type` | string | Yes      | MIME type of the object the caller will upload             |
| `duration`  | string | No       | Ephemeral duration. Currently supported value: `"5m"`.     |

### Response (200)

| Field            | Type    | Description                                                   |
| ---------------- | ------- | ------------------------------------------------------------- |
| `media_input_s3` | string  | Opaque server-signed S3 input reference for signing           |
| `upload_url`     | string  | Presigned PUT URL for uploading input media                   |
| `expires_at`     | integer | Unix timestamp when the signed reference expires              |
| `duration`       | string  | Duration value used for object keys and expiry                |

```json
{
  "media_input_s3": "<opaque signed reference>",
  "upload_url": "https://...",
  "expires_at": 1770000000,
  "duration": "5m"
}
```

### Errors

- **401** — missing or invalid credential.
- **403** — API-key scope not allowed, access-token caller lacks the `c2pa_sign` permission, or production signing access is not active for the caller's organization.

---

# Remote (Distributed) Signing

In the case where the media content cannot be sent over an API call (e.g. due to file size or privacy concerns), use distributed signing: the C2PA manifest is assembled and hashed locally, and the resulting hash is sent to Trufo for signing. To remain conformant with the C2PA specification, currently the only way to do so is via the `trufo[provenance]` optional installation and using the `sign_c2pa_distributed()` Python function. See [4_distributed_signing.md](../quickstart/4_distributed_signing.md) for an end-to-end guide.

---

# Auxiliary APIs

## `POST /c2pa/ai-disclosure/add`

Register a custom `c2pa.ai-disclosure` assertion body for the calling organization. Returns an opaque identifier that can be passed as the `ai_disclosure_id` param on the `ai_disclosure` assertion when calling `/c2pa/sign` or `/test/c2pa/sign`.

### Request Body

| Field       | Type   | Required | Description                                                                                    |
| ----------- | ------ | -------- | ---------------------------------------------------------------------------------------------- |
| `nickname`  | string | No       | Human-readable display label for the stored disclosure (e.g. `"Llama 2 70B — autonomous"`). Shown in `/c2pa/ai-disclosure/list` to help identify entries. Not included in the signed assertion. |
| `assertion` | object | Yes      | A `c2pa.ai-disclosure` assertion body conforming to the `ai-model-disclosure-map` CDDL schema in C2PA 2.4 §18.29.1. See schema below. |

The owning org is inferred from the caller's credential — no `oid` field.

#### `assertion` schema

The request-side validator rejects bodies that don't match the C2PA 2.4 `ai-model-disclosure-map` shape. Field summary:

| Field                            | Type                   | Required | Notes                                                                                                |
| -------------------------------- | ---------------------- | -------- | ---------------------------------------------------------------------------------------------------- |
| `modelType`                      | string                 | Yes      | One of the 23 permitted C2PA model-type values (see C2PA 2.4 Table 12). Unknown values are rejected. |
| `modelName`                      | string                 | No       | Non-empty human-readable model name.                                                                 |
| `modelIdentifier`                | string                 | No       | Non-empty machine-readable identifier (e.g. a `pkg:huggingface/…` PURL).                             |
| `contentProfile`                 | object                 | No       | See sub-fields below.                                                                                |
| `contentProfile.humanOversightLevel` | string             | No       | One of `"fully_autonomous"`, `"prompt_guided"`, `"human_validated"`.                                 |
| `contentProfile.scientificDomain` | string or list[string] | No       | Each value must match `^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$` (e.g. `biology.genomics`).                 |
| `metadata`                       | object                 | No       | Free-form assertion metadata.                                                                        |

Any top-level key outside the above list is rejected. Fields introduced in draft/pending additions to the C2PA 2.4 spec are not accepted until finalized.

### Example

```json
{
  "nickname": "Llama 2 70B — autonomous",
  "assertion": {
    "modelType": "c2pa.types.model.huggingface.transformers",
    "modelIdentifier": "pkg:huggingface/meta-llama/Llama-2-70b-chat-hf@main",
    "contentProfile": { "humanOversightLevel": "fully_autonomous" }
  }
}
```

### Response (201)

| Field              | Type   | Description                                               |
| ------------------ | ------ | --------------------------------------------------------- |
| `ai_disclosure_id` | string | Stored disclosure identifier, shape `aidisc_<uuidv7>`.    |

```json
{ "ai_disclosure_id": "aidisc_0193f7e0abcd7a11bcde01234567890a" }
```

### Errors

- **400** — `assertion` fails the C2PA 2.4 schema check (e.g. unknown `modelType`, bad `humanOversightLevel`).
- **401** — missing or invalid credential.
- **403** — API-key scope not allowed, or access-token caller lacks the `c2pa_sign` permission.

---

## `POST /c2pa/ai-disclosure/list`

List the `c2pa.ai-disclosure` assertions stored for the caller's organization.

### Request Body

Empty. Send `{}`. The owning org is inferred from the caller's credential.

### Response (200)

| Field   | Type  | Description                                                                      |
| ------- | ----- | -------------------------------------------------------------------------------- |
| `items` | list  | Zero or more `{ ai_disclosure_id, nickname, assertion }` entries for this org.   |

Each entry:

| Field              | Type           | Description                                                                   |
| ------------------ | -------------- | ----------------------------------------------------------------------------- |
| `ai_disclosure_id` | string         | Stored disclosure identifier, shape `aidisc_<uuidv7>`.                        |
| `nickname`         | string or null | Display label supplied when the disclosure was added, or `null` if none.      |
| `assertion`        | object         | The stored `c2pa.ai-disclosure` assertion body, as submitted.                 |

```json
{
  "items": [
    {
      "ai_disclosure_id": "aidisc_0193f7e0abcd7a11bcde01234567890a",
      "nickname": "Llama 2 70B — autonomous",
      "assertion": {
        "modelType": "c2pa.types.model.huggingface.transformers",
        "modelIdentifier": "pkg:huggingface/meta-llama/Llama-2-70b-chat-hf@main",
        "contentProfile": { "humanOversightLevel": "fully_autonomous" }
      }
    }
  ]
}
```

### Errors

- **401** — missing or invalid credential.
- **403** — API-key scope not allowed, or access-token caller lacks the `c2pa_sign` permission.
