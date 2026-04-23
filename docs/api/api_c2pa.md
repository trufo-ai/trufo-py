# C2PA Signing API

Endpoints for C2PA manifest generation and management of reusable assertion records.

- **Base URL:** `https://api.trufo.ai`
- **Test paths:** `/test/<route>` — signed with a test certificate; outputs may not be recognized by C2PA validators
- **Production paths:** `/<route>` — signed with a proper certificate; outputs are recognized by conformant C2PA validators; same schema as test

**Default Headers** (unless overridden by a specific endpoint):

- **Auth:** API key (`X-API-Key`) or access token (`Authorization: Bearer`)
- **Content type:** `application/json`

Authentication is per-endpoint; when using an API key, the scope must match the endpoint:


| Endpoint                         | Required auth                                                                 |
| -------------------------------- | ----------------------------------------------------------------------------- |
| `POST /c2pa/sign`                | API key with scope `c2pa-sign-prod`, **or** access token                      |
| `POST /test/c2pa/sign`           | API key with scope `c2pa-sign-test`, **or** access token                      |
| `POST /c2pa/ai-disclosure/add`   | API key with scope `c2pa-sign-prod` or `c2pa-sign-test`, **or** access token  |
| `POST /c2pa/ai-disclosure/list`  | API key with scope `c2pa-sign-prod` or `c2pa-sign-test`, **or** access token  |


When authenticating with an access token, the caller must be an activated member of the organization named in the request body (`oid`).

See [api_auth.md](api_auth.md) for full header conventions and the complete scope list, or the [Auth Quickstart](../quickstart/0_auth.md) for a setup guide.

---

## Common Workflows

### AIGC Labeling

See [2_ai_labeling.md](../quickstart/2_ai_labeling.md) for a quickstart guide for this use case.

### CAWG Publishing

See [3_cawg_publish.md](../quickstart/3_cawg_publish.md) for a quickstart guide for this use case.

---

## API Reference: `POST /c2pa/sign`, `POST /test/c2pa/sign`

Both endpoints share the same request/response schema. The production signer produces manifests recognized by conformant C2PA validators; the test signer produces manifests that are not.

### Request Body


| Field         | Type   | Required | Description                                        |
| ------------- | ------ | -------- | -------------------------------------------------- |
| `media_input` | string | Yes      | base64-encoded input media data                    |
| `actions`     | list   | No       | media processing instructions for the TPS to apply |
| `assertions`  | list   | No       | gathered assertions to include in the manifest     |


#### `media_input`

Base64-encoded bytes of the input file. The supported MIME types are listed below; more will be added over time (upon request).


| Category | MIME types                                                                                                             |
| -------- | ---------------------------------------------------------------------------------------------------------------------- |
| Image    | `image/jpeg`, `image/png`, `image/tiff`, `image/webp`, `image/avif`, `image/jxl`, `image/x-adobe-dng`, `image/svg+xml` |
| Video    | `video/mp4`, `video/quicktime`                                                                                         |
| Audio    | `audio/mpeg`, `audio/flac`, `audio/wav`, `audio/mp4`                                                                   |


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
| `"ai_disclosure"` | `{"set_source_type": false}`   | `c2pa.ai-disclosure`   |
| `"cawg_metadata"` | `{"assertion": {…}}`           | `cawg.metadata`        |
| `"cawg_training"` | `{"assertion": {…}}`           | `cawg.training-mining` |
| `"cawg_identity"` | `{"cawg_identity_id": "<id>"}` | `cawg.identity`        |


##### `ai_disclosure`

Marks the content as AI-generated via a `c2pa.ai-disclosure` assertion. By default, the minimal assertion body `{"modelType": "c2pa.types.model"}` is used; to attach a richer pre-registered assertion (e.g. identifying a specific model, dataset, or content profile), first register it via [`POST /c2pa/ai-disclosure/add`](#api-reference-post-c2paai-disclosureadd) and pass the returned `ai_disclosure_id`.


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
    "dc:creator": ["Alice"]
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

Attach a CAWG identity assertion. Only `"test"` is supported.


| Param              | Type   | Required | Description                   |
| ------------------ | ------ | -------- | ----------------------------- |
| `cawg_identity_id` | string | Yes      | Identity provider identifier. |


Currently, only `"test"` is supported in the test endpoint — any other value raises `NotImplementedError`.



### Response (200)

```json
{
  "media_output": "<base64-encoded signed media>"
}
```

---

## API Reference: `POST /c2pa/ai-disclosure/add`

Register a custom `c2pa.ai-disclosure` assertion body for the calling organization. Returns an opaque identifier that can be passed as the `ai_disclosure_id` param on the `ai_disclosure` assertion when calling `/c2pa/sign` or `/test/c2pa/sign`.

### Request Body


| Field       | Type   | Required | Description                                                                                    |
| ----------- | ------ | -------- | ---------------------------------------------------------------------------------------------- |
| `oid`       | string | Yes      | Organization ID that will own the stored disclosure.                                           |
| `assertion` | object | Yes      | A `c2pa.ai-disclosure` assertion body conforming to the `ai-model-disclosure-map` CDDL schema in C2PA 2.4 §18.29.1. See schema below. |


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
  "oid": "org_01JABC...",
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
- **403** — API-key scope not allowed, or access-token caller lacks the `c2pa_sign` permission on `oid`.

---

## API Reference: `POST /c2pa/ai-disclosure/list`

List the `c2pa.ai-disclosure` assertions stored for an organization.

### Request Body


| Field | Type   | Required | Description                                   |
| ----- | ------ | -------- | --------------------------------------------- |
| `oid` | string | Yes      | Organization ID whose disclosures to list.    |


### Response (200)


| Field   | Type  | Description                                                          |
| ------- | ----- | -------------------------------------------------------------------- |
| `items` | list  | Zero or more `{ ai_disclosure_id, assertion }` entries for this org. |


Each entry:


| Field              | Type   | Description                                                   |
| ------------------ | ------ | ------------------------------------------------------------- |
| `ai_disclosure_id` | string | Stored disclosure identifier, shape `aidisc_<uuidv7>`.        |
| `assertion`        | object | The stored `c2pa.ai-disclosure` assertion body, as submitted. |


```json
{
  "items": [
    {
      "ai_disclosure_id": "aidisc_0193f7e0abcd7a11bcde01234567890a",
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
- **403** — API-key scope not allowed, or access-token caller lacks the `c2pa_sign` permission on `oid`.
