# C2PA Generation — API Reference

Endpoints for C2PA manifest generation (signing). All endpoints are hosted at `https://api.trufo.ai`.

> **Default auth:** API key (`X-API-Key`) or access token (`Authorization: Bearer`).
> **Default content type:** `application/json`.
> See [api_access.md](api_access.md) for full header conventions.

> **Status:** The production endpoint (`POST /c2pa/generate`) is not yet available. Use the test endpoint (`POST /test/c2pa/generate`) for development and integration testing.

---

## `POST /c2pa/generate`

Generate a C2PA-signed media file. Signs with the TPS production signer (`tps_level1`). Requires account setup, organization validation, and certificate enrollment — see [tca_ra.md](tca_ra.md) and [tca_ca.md](tca_ca.md).

**Auth:** Access token.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `media_input` | string | Yes | Base64-encoded input media |
| `actions` | list | Yes | Media processing actions to apply |
| `assertions` | list | No | Assertions to include in the manifest (default `[]`) |
| `c2pa` | bool | Yes | Unused — pass `true` |
| `activate` | bool | Yes | Unused — pass `false` |

### `media_input`

Base64-encoded bytes of the input file. The MIME type is auto-detected from magic bytes. Supported types are defined by openprov's `GENERATE_TYPES` (see `openprov/util/av_format.py`):

| Category | MIME types |
|----------|------------|
| Image | `image/jpeg`, `image/png`, `image/tiff`, `image/webp`, `image/avif`, `image/heic`, `image/heif`, `image/jxl`, `image/x-adobe-dng`, `image/svg+xml` |
| Video | `video/mp4`, `video/quicktime` |
| Audio | `audio/mpeg`, `audio/flac`, `audio/wav`, `audio/mp4` |

### `actions`

List of `[action_name, params]` pairs. Each element is a two-element array. Pass `[]` for no-action signing (manifest only, no media processing).

| Action | Params | Description |
|--------|--------|-------------|
| `"transcode"` | `{"target_mime_type": "<mime>"}` | Transcode to target format |

Only `"transcode"` is implemented. The `target_mime_type` must be one of the supported MIME types above.

### `assertions`

List of `[assertion_name, params]` pairs. Each element is a two-element array. All assertions are optional.

| Assertion | Params | C2PA label |
|-----------|--------|------------|
| `"ai_disclosure"` | `{"model_disclosure_id": "<id>"}` | `c2pa.ai-disclosure` |
| `"cawg_metadata"` | `{"assertion": {…}}` | `cawg.metadata` |
| `"cawg_training"` | `{"assertion": {…}}` | `cawg.training-mining` |
| `"cawg_identity"` | `{"cawg_identity_id": "<id>"}` | `cawg.identity` |

#### `ai_disclosure`

Marks the content as AI-generated. If the input media has no existing C2PA manifest, the ingredient's `digitalSourceType` is set to `trainedAlgorithmicMedia`.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `model_disclosure_id` | string | No | Custom model disclosure identifier. **Not yet implemented** — if provided, the server raises `NotImplementedError`. Omit to use the default assertion body `{"modelType": "c2pa.types.model"}`. |

```json
["ai_disclosure", {}]
```

#### `cawg_metadata`

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

| Prefix | URI |
|--------|-----|
| `Iptc4xmpCore` | `http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/` |
| `Iptc4xmpExt` | `http://iptc.org/std/Iptc4xmpExt/2008-02-29/` |
| `dc` | `http://purl.org/dc/elements/1.1/` |
| `exif` | `http://ns.adobe.com/exif/1.0/` |
| `exifEX` | `http://cipa.jp/exif/2.32/` |
| `pdf` | `http://ns.adobe.com/pdf/1.3/` |
| `pdfx` | `http://ns.adobe.com/pdfx/1.3/` |
| `photoshop` | `http://ns.adobe.com/photoshop/1.0/` |
| `tiff` | `http://ns.adobe.com/tiff/1.0/` |
| `xmp` | `http://ns.adobe.com/xap/1.0/` |

Any prefix not in this list, or a URI that doesn't match exactly, is rejected.

#### `cawg_training`

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

#### `cawg_identity`

Attach a CAWG identity assertion.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `cawg_identity_id` | string | Yes | Identity provider identifier. Only `"test"` is currently supported — any other value raises `NotImplementedError`. |

```json
["cawg_identity", {"cawg_identity_id": "test"}]
```

### `c2pa` and `activate`

These fields are required by the request schema but are not used by the generate endpoint. They exist for a future managed content flow. Pass `true` and `false` respectively.

### Response (200)

```json
{
  "media_output": "<base64-encoded signed media>"
}
```

---

## `POST /test/c2pa/generate`

Test variant of the production endpoint above. Signs with the TPS test signer (`tps_test`). No account or organization required — any valid API key or access token satisfies authentication.

**Auth:** API key (trufo-api) or access token.

The request and response schema is identical to `POST /c2pa/generate` with the following restrictions:

- **`ai_disclosure`**: Do not submit `model_disclosure_id`. Only the default hardcoded assertion is available.
- **`cawg_identity`**: `cawg_identity_id` must be `"test"`. No other identity providers are available.

---

## Python SDK

| Function | Location | Description |
|----------|----------|-------------|
| _TBD_ | `trufo.api.tps.generate_c2pa` | C2PA generation helpers |
