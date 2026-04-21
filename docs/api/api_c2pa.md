# C2PA API Endpoints

Endpoints for C2PA manifest generation (signing). All endpoints are hosted at `https://api.trufo.ai`.

> **Default auth:** API key (`X-API-Key`) or access token (`Authorization: Bearer`).
> **Default content type:** `application/json`.
> See [api_access.md](api_access.md) for full header conventions.

> **`POST /c2pa/generate` (production) is not yet available.** It is pending updates to the C2PA and CAWG specifications. Use `POST /test/c2pa/generate` for development and integration testing.

---

# Common Workflows

## AIGC Labeling

## CAWG Publishing

---

# API Reference

## `POST /test/c2pa/generate`

Generate a C2PA-signed media file using the TPS C2PA test signer. The generated test files will NOT be marked as conformant by validators, but the API schema will match the production endpoint (coming soon!).

**Auth:** API key (trufo-api) or access token.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `media_input` | string | Yes | base64-encoded input media data |
| `actions` | list | No | media processing instructions for the TPS to apply |
| `assertions` | list | No | gathered assertions to include in the manifest |

### `media_input`

Base64-encoded bytes of the input file. The supported MIME types are listed below; more will be added over time (upon request).

| Category | MIME types |
|----------|------------|
| Image | `image/jpeg`, `image/png`, `image/tiff`, `image/webp`, `image/avif`, `image/jxl`, `image/x-adobe-dng`, `image/svg+xml` |
| Video | `video/mp4`, `video/quicktime` |
| Audio | `audio/mpeg`, `audio/flac`, `audio/wav`, `audio/mp4` |

### `actions`

Ordered list of `[action_name, params]` pairs. Each element of the `actions` list is a two-element array, and will be executed by the TPS in order.

| Action | Params | Description |
|--------|--------|-------------|
| `"transcode"` | `{"target_mime_type": "<mime>"}` | transcode to target format |
| `"publish"` | `{}` | mark for final distribution |

### `assertions`

Ordered list of `[assertion_name, params]` pairs. Each assertion is treated as a gathered assertion when signing the manifest. If `assertions` is provided, at least one `"cawg_identity"` entry must be present — the signer automatically references all gathered assertions through the identity assertion.

| Assertion | Params | C2PA label |
|-----------|--------|------------|
| `"ai_disclosure"` | `{"set_source_type": false}` | `c2pa.ai-disclosure` |
| `"cawg_metadata"` | `{"assertion": {…}}` | `cawg.metadata` |
| `"cawg_training"` | `{"assertion": {…}}` | `cawg.training-mining` |
| `"cawg_identity"` | `{"cawg_identity_id": "<id>"}` | `cawg.identity` |

#### `ai_disclosure`

Marks the content as AI-generated via a `c2pa.ai-disclosure` assertion. Uses a hardcoded default assertion body `{"modelType": "c2pa.types.model"}`.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `set_source_type` | bool | `false` | When `true` and the input has no existing C2PA manifest, sets `digitalSourceType = trainedAlgorithmicMedia` on the ingredient. See note below. |

> **Note on `set_source_type`:** Setting `digitalSourceType` in C2PA ingredients is specified in C2PA v2.4 (§18.16.12.3) and is not yet supported by most existing validators. The `c2pa.ai-disclosure` assertion alone suffices for labeling purposes; `set_source_type` is provided for forwards-compatible use. If you need to set Digital Source Type and cannot use this parameter (e.g. for a full Generator Product workflow), reach out to Trufo or CAI/C2PA directly.

```json
["ai_disclosure", {}]
```

With source type explicitly set:

```json
["ai_disclosure", {"set_source_type": true}]
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

Attach a CAWG identity assertion. Only `"test"` is supported.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `cawg_identity_id` | string | Yes | Identity provider identifier. |

Currently, only `"test"` is supported in the test endpoint — any other value raises `NotImplementedError`.

### Response (200)

```json
{
  "media_output": "<base64-encoded signed media>"
}
```
