# C2PA Signing API

Endpoints for C2PA manifest generation and signing.

- **Base URL:** `https://api.trufo.ai`
- **Test paths:** `/test/<route>` — signed with a test certificate; outputs may not be recognized by C2PA validators
- **Production paths:** `/<route>` — signed with a proper certificate; outputs are recognized by conformant C2PA validators; same schema as test

**Default Headers** (unless overridden by a specific endpoint):

- **Auth:** API key (`X-API-Key`) or access token (`Authorization: Bearer`)
- **Content type:** `application/json`

Authentication is per-endpoint; when using an API key, the scope must match the endpoint:


| Endpoint               | Required auth                                                       |
| ---------------------- | ------------------------------------------------------------------- |
| `POST /c2pa/sign`      | API key with scope `c2pa-sign-prod`, **or** access token            |
| `POST /test/c2pa/sign` | API key with scope `c2pa-sign-test`, **or** access token            |


See [api_auth.md](api_auth.md) for full header conventions and the complete scope list, or the [Auth Quickstart](../quickstart/0_auth.md) for a setup guide.

---

## Common Workflows

### AIGC Labeling

See [2_ai_labeling.md](../quickstart/2_ai_labeling.md) for a quickstart guide for this use case.

### CAWG Publishing

See [3_cawg_publish.md](../quickstart/3_cawg_publish.md) for a quickstart guide for this use case.

---

## API Reference

**Endpoints** (both share the same request/response schema below):

- `POST /c2pa/sign` — production signer; outputs recognized by conformant C2PA validators
- `POST /test/c2pa/sign` — test signer; outputs not recognized by C2PA validators

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

Marks the content as AI-generated via a `c2pa.ai-disclosure` assertion. Uses the default assertion body `{"modelType": "c2pa.types.model"}`.


| Param             | Type | Default | Description                                                                                                                                          |
| ----------------- | ---- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `set_source_type` | bool | `false` | When `true` and the input has no existing C2PA manifest, sets `digitalSourceType = trainedAlgorithmicMedia` on the ingredient. Also, see note below. |


> **Note on `set_source_type`:** Setting `digitalSourceType` within C2PA ingredients is new to C2PA v2.4 (§18.16.12.3) and is not yet supported by most existing validators today (e.g. having this field may make the manifest show up as "invalid"). The `c2pa.ai-disclosure` assertion alone suffices for AI labeling purposes, though for forwards-compatibility purposes you may want to set both. If your use case allows for validators to temporarily display "invalid" messaging, we recommend setting both. If not, then include only the ai_disclosure.

No digitalSourceType:

```json
["ai_disclosure", {}]
```

Include digitalSourceType:

```json
["ai_disclosure", {"set_source_type": true}]
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

