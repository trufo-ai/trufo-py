# Actions and Assertions Reference

Normative specification for `actions`, `assertions`, `signed_input_policy` / `signed_ingredient_policy`, `/ai-system/*`, and `/c2pa/software-agent/*`.

---

## `actions`

Ordered array of `[name, params]` pairs. Media actions run in order, each feeding its output into the next. An action whose input already satisfies its parameters is a no-op and records no C2PA action.

| Action | Params | C2PA action recorded |
| --- | --- | --- |
| `"resize"` | `{"width"?: int, "height"?: int}` | `c2pa.resized.proportional` |
| `"crop"` | `{"x": int, "y": int, "width": int, "height": int}` | `c2pa.cropped` |
| `"trim"` | `{"start"?: number, "end"?: number}` | `c2pa.trimmed` |
| `"transcode"` | `{"target_mime_type"?: str, "quality"?: int, "video_codec"?: str, "crf"?: int, "audio_codec"?: str, "audio_bitrate"?: int}` | `c2pa.transcoded` (or `c2pa.repackaged` if all streams copied) |
| `"repackage"` | `{"target_mime_type": "video/mp4" \| "video/quicktime"}` | `c2pa.repackaged` |
| `"watermark"` | `{"wid_allocation_mode"?: str, "effort_policy"?: str}` | `c2pa.watermarked.bound` (`per_embed`) or `c2pa.watermarked.unbound` (`per_ai_system`) |
| `"publish"` | `{}` | `c2pa.published` |
| `"redact"` | `{"label": str, "reason": str}` | `c2pa.redacted` |

Metadata that an output target cannot hold is reported in `warnings`. See [Media Format Support](media-formats.md#media-actions) for per-format rules, limits, and refusals.

### `resize`

Proportionally fits displayed pixels (after EXIF orientation / video rotation) inside `width`, `height`, or both (at least one required; ≥ 1 for images, ≥ 2 for video — video sides round down/to even). Inputs: JPEG, PNG, WebP, AVIF, TIFF, GIF, MP4, MOV. Updates EXIF/XMP stored dimensions. Video re-encodes at default CRF (H.264/H.265 kept, other codecs → H.264); other streams copied. Can combine with `c2pa.created`.

### `crop`

Keeps displayed rectangle `(x, y, width, height)` within image bounds (`x, y >= 0`; `width, height >= 1`; all four required and even for video). Same inputs as `resize`. Updates EXIF/XMP dimensions and EXIF subject area; drops EXIF/Photoshop thumbnails. Can combine with `c2pa.created`.

### `trim`

Exact cut from `start` to `end` in seconds (`>= 0`, `end > start`, at least one required, span ≥ 1 video frame or 1 audio sample). Inputs: FLAC, WAV, M4A, MP3, MP4, MOV. Re-encodes video and audio (PCM/FLAC lossless; AAC/MP3 at 192 kbit/s), copies cover pictures, trims chapters, drops subtitles and non-zero-start timecode. Can combine with `c2pa.created`.

### `transcode`

Re-encodes within the same media class or changes encoding settings (at least one parameter required). **Cannot be combined with `c2pa.created`** (`400 Conflict`) — sign first, then transcode the signed file. Copies audio/video streams that already match target requirements.

| Parameter | Applies to | Allowed values | Default |
| --- | --- | --- | --- |
| `target_mime_type` | All | `image/{jpeg,png,webp,avif,tiff,gif}`, `audio/{flac,wav,mp4,mpeg}`, `video/{mp4,quicktime}` (same class) | Input MIME (required for HEIC, HEIF, JXL, AVI) |
| `quality` | `image/jpeg`, `image/webp`, `image/avif` | Integer `0..100` | `90` |
| `video_codec` | `video/mp4`, `video/quicktime` | `"h264"`, `"h265"` | Source if H.264/H.265, else `"h264"` |
| `crf` | `video/mp4`, `video/quicktime` | Integer `0..51` (lower = higher quality) | `23` (H.264), `28` (H.265) |
| `audio_codec` | `video/mp4`, `video/quicktime` | `"aac"` | `"aac"` |
| `audio_bitrate` | `audio/mp4`, `audio/mpeg`, `video/mp4`, `video/quicktime` | `96`, `128`, `192`, `256`, `320` (kbit/s) | `192` |

### `repackage`

Remuxes MP4, MOV, or AVI streams into `video/mp4` or `video/quicktime` without re-encoding (`target_mime_type` required). Refuses streams the target container cannot hold (e.g., ProRes or PCM into MP4). Cannot be combined with `c2pa.created`.

### `watermark`

Off by default; at most one entry per request. Place **last** after media actions (a media change after `watermark` emits a warning).

| Param | Values | Default |
| --- | --- | --- |
| `wid_allocation_mode` | `"per_embed"` or `"per_ai_system"` (`"per_asset"` returns `501`) | `"per_embed"` |
| `effort_policy` | `"require"`, `"require_if_supported"`, `"best_effort"` | `"require"` |

- `"per_embed"`: allocates a new watermark ID, writes `c2pa.watermarked.bound` + `c2pa.soft-binding` (`alg: "ai.trufo.pawprint.watermark"`). Requires `skip_manifest_storage: false` (`400 ManifestStorageRequired`).
- `"per_ai_system"`: requires an `ai_system` assertion in the same request; embeds the AI system's shared ID and writes `c2pa.watermarked.unbound` (no soft-binding assertion).

### `publish`

Annotation-only (`{}`); records `c2pa.published`.

### `redact`

Removes one named assertion from the input's existing manifest history across all generations (C2PA §6.8). Repeat for multiple labels; duplicate labels refused (`400`). Fails (`400`) if the input has no manifest or the label is absent.

- **Allowed `label` base names:** `c2pa.metadata`, `cawg.metadata`, `cawg.training-mining`, `cawg.identity`. Append `__N` (e.g., `c2pa.metadata__1`) to target numbered instances; bare labels match only unnumbered instances.
- **Required `reason`:** `"c2pa.PII.present"`, `"c2pa.invalid.data"`, `"c2pa.trade-secret.present"`, `"c2pa.government.confidential"`, or a domain-validated reverse-DNS string.

---

## `assertions`

Ordered array of `[name, params]` pairs. `ai_system`, `creation`, `c2pa_metadata`, `cawg_metadata`, and `cawg_training` may each appear at most once (`400 DuplicateAssertion`). Assertions are `gathered` unless specified as `created`; `created` user declarations require an authorized `branded_gp_id` (`403 C2PACreatedUserAssertionsNotAuthorized`).

| Assertion | Params summary | C2PA label |
| --- | --- | --- |
| `"ai_system"` | `{"ai_system_id": "aisys_...", "ai_involvement": "ai_generated" \| "ai_modified"}` | `c2pa.actions` + optional `c2pa.ai-disclosure` |
| `"c2pa_metadata"` | `{"assertion": {"@context": {...}, ...}}` | `c2pa.metadata` |
| `"cawg_metadata"` | `{"assertion": {"@context": {...}, ...}}` | `cawg.metadata` |
| `"cawg_training"` | `{"assertion": {"entries": {...}}}` | `cawg.training-mining` |
| `"cawg_identity"` | `{"cawg_identity_id": "org_interim" \| "test"}` | `cawg.identity` |
| `"custom"` | `{"label": "<reverse-dns>", "assertion": {...}}` | Your label |
| `"ingredient"` | `{"relationship": "inputTo" \| "componentOf" \| "parentOf", ...}` | `c2pa.ingredient.v3` |
| `"creation"` | `{"digitalSourceType": "<IPTC URI>", "softwareAgent": {"software_agent_id": "swagent_..."}, ...}` | `c2pa.actions` (`c2pa.created`) |

### `ai_system`

At most one per request; cannot combine with `creation`. `ai_involvement` must be in the registered AI system's `ai_involvement_modes`.

- Unsigned input resolution order:
  1. `branded_gp_id` set → signed as your branded generator product (`c2pa.created`: `trainedAlgorithmicMedia` for `ai_generated`, `compositeWithTrainedAlgorithmicMedia` for `ai_modified`).
  2. `c2pa_first_party_attestable: true` → `c2pa.created` (`trainedAlgorithmicMedia`) with the AI system as software agent.
  3. `c2pa_first_party_attestable: false` → declared AI parent ingredient (`trainedAlgorithmicMedia`) + `c2pa.opened`.
- `ai_modified` requires `branded_gp_id` approved for `compositeWithTrainedAlgorithmicMedia`.
- Optional `c2pa_ai_disclosure` from the AI system registration is written as a gathered `c2pa.ai-disclosure` assertion.
- **Errors:** `404 AISystemNotFound`, `400 AISystemInactive`, `400` mode mismatch / `ai_modified` without `branded_gp_id` / source-class conflict / `parentOf` conflict with `branded_gp_id` on unsigned input, `403 C2PACreatedUserAssertionsNotAuthorized`.

### `c2pa_metadata`

JSON-LD capture/asset metadata (C2PA 2.4 §18.17.3, gathered only — omit `placement`). `@context` must declare every prefix used, matching exact URIs and supported fields:

| Prefix | URI | Supported fields |
| --- | --- | --- |
| `Iptc4xmpExt` | `http://iptc.org/std/Iptc4xmpExt/2008-02-29/` | `DigImageGUID`, `DigitalSourceType`, `EventId`, `Genre`, `ImageRating`, `ImageRegion`, `LocationCreated`, `LocationShown`, `MaxAvailHeight`, `MaxAvailWidth`, `RegistryId` |
| `crs` | `http://ns.adobe.com/camera-raw-settings/1.0/` | Standard Adobe Camera Raw settings (`Exposure`, `Contrast`, `Temperature`, `Tint`, `WhiteBalance`, `Crop*`, `ToneCurve*`, etc.) |
| `dc` | `http://purl.org/dc/elements/1.1/` | `coverage`, `date`, `format`, `identifier`, `language`, `relation`, `type` |
| `exif` | `http://ns.adobe.com/exif/1.0/` | Standard EXIF 1.0 capture & GPS fields (`DateTimeOriginal`, `ExposureTime`, `FNumber`, `FocalLength`, `GPSLatitude`, `GPSLongitude`, `ISOSpeedRatings`, etc.) |
| `exifEX` | `http://cipa.jp/exif/1.0/` | `BodySerialNumber`, `Gamma`, `ISOSpeed`, `ISOSpeedLatitudeyyy`, `ISOSpeedLatitudezzz`, `InteroperabilityIndex`, `LensMake`, `LensModel`, `LensSerialNumber`, `LensSpecification`, `PhotographicSensitivity`, `RecommendedExposureIndex`, `SensitivityType`, `StandardOutput-Sensitivity` |
| `pdf` | `http://ns.adobe.com/pdf/1.3/` | `Keywords`, `PDFVersion`, `Producer`, `Trapped` |
| `photoshop` | `http://ns.adobe.com/photoshop/1.0/` | `Category`, `City`, `ColorMode`, `Country`, `DateCreated`, `DocumentAncestors`, `History`, `ICCProfile`, `State`, `SupplementalCategories`, `TextLayers`, `TransmissionReference`, `Urgency` |
| `plus` | `http://ns.useplus.org/ldf/xmp/1.0/` | `FileNameAsDelivered`, `FirstPublicationDate`, `ImageFileFormatAsDelivered`, `ImageFileSizeAsDelivered`, `ImageType`, `Version` |
| `tiff` | `http://ns.adobe.com/tiff/1.0/` | `BitsPerSample`, `Compression`, `ImageLength`, `ImageWidth`, `Make`, `Model`, `Orientation`, `PhotometricInterpretation`, `PlanarConfiguration`, `PrimaryChromaticities`, `ReferenceBlackWhite`, `ResolutionUnit`, `SamplesPerPixel`, `TransferFunction`, `WhitePoint`, `XResolution`, `YCbCrCoefficients`, `YCbCrPositioning`, `YCbCrSubSampling`, `YResolution` |
| `xmp` | `http://ns.adobe.com/xap/1.0/` | `BaseURL`, `CreateDate`, `CreatorTool`, `Identifier`, `Label`, `MetadataDate`, `ModifyDate`, `Nickname`, `Rating`, `Thumbnails` |
| `xmpDM` | `http://ns.adobe.com/xmp/1.0/DynamicMedia/` | Dynamic media fields (`Tracks`, `audioSampleRate`, `duration`, `videoFrameRate`, `videoFrameSize`, `startTimecode`, `markers`, etc.) |
| `xmpMM` | `http://ns.adobe.com/xap/1.0/mm/` | `DerivedFrom`, `DocumentID`, `History`, `Ingredients`, `InstanceID`, `ManageTo`, `ManageUI`, `ManagedFrom`, `Manager`, `ManagerVariant`, `OriginalDocumentID`, `Pantry`, `RenditionClass`, `RenditionParams`, `VersionID`, `Versions` |
| `xmpTPg` | `http://ns.adobe.com/xap/1.0/t/pg/` | `Colorants`, `Fonts`, `MaxPageSize`, `NPages`, `PlateNames` |

Unsupported fields return `400 UnsupportedC2PAMetadataField`; invalid `@context` returns `400 InvalidMetadataContext`.

### `cawg_metadata`

JSON-LD creator/rights metadata (written as JSON; gathered only). Allowlisted `@context` URIs:

| Prefix | URI |
| --- | --- |
| `Iptc4xmpCore` | `http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/` |
| `Iptc4xmpExt` | `http://iptc.org/std/Iptc4xmpExt/2008-02-29/` |
| `dc` | `http://purl.org/dc/elements/1.1/` |
| `exif` | `http://ns.adobe.com/exif/1.0/` |
| `exifEX` | `http://cipa.jp/exif/2.32/` |
| `pdf` | `http://ns.adobe.com/pdf/1.3/` |
| `pdfx` | `http://ns.adobe.com/pdfx/1.3/` |
| `photoshop` | `http://ns.adobe.com/photoshop/1.0/` |
| `plus` | `http://ns.useplus.org/ldf/xmp/1.0/` |
| `schema` | `http://schema.org/` |
| `tiff` | `http://ns.adobe.com/tiff/1.0/` |
| `xmp` | `http://ns.adobe.com/xap/1.0/` |
| `xmpDM` | `http://ns.adobe.com/xmp/1.0/DynamicMedia/` |
| `xmpRights` | `http://ns.adobe.com/xap/1.0/rights/` |

### `cawg_training`

`assertion` must have a single key `entries` mapping entry names (`cawg.ai_training`, `cawg.ai_generative_training`, `cawg.ai_inference`, `cawg.data_mining`) to `{"use": "allowed" | "notAllowed" | "constrained", "constraint_info"?: "..."}`.

### `cawg_identity`

- `"org_interim"`: Your organization's managed CAWG interim certificate (production and test; requires CAWG Organization Certificate plan).
- `"test"`: Shared Trufo test CAWG certificate (`test.api.trufo.ai` only; `400 InvalidCawgIdentityId` on production hosts).

### `custom`

`{"label": "<reverse-dns>", "assertion": {...}}`. Label cannot use `c2pa` namespace or contain `__`, and requires active Domain Validation for the domain (`403 InvalidC2PACustomDomain`). Labels ending in `.metadata` are written as JSON and require a non-empty `@context` object (`400 InvalidMetadataContext`).

### `ingredient`

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `relationship` | string | Yes | `"inputTo"`, `"componentOf"`, or `"parentOf"` (at most one `parentOf`; requires `branded_gp_id` and `media`; cannot combine with `creation` or a kept signed input) |
| `title` | string | No | `dc:title`; falls back to media's manifest title, then `ingredient_{n}.{ext}` (or `ingredient_{n}`) |
| `media` | string | For `parentOf` | Base64 bytes (C2PA-validate eligible format); mutually exclusive with `format` |
| `format` | string | No | MIME type for declared ingredients (required on `componentOf` without `media`, and on `inputTo` with `data`) |
| `data` | string | No | Base64 inline payload on `inputTo` with `format` and no `media` (max 64,000 decoded bytes; > 8 KB warns) |
| `data_types` | array | No | `[{"type": "c2pa.types.<kind>", "version"?: "..."}]` |
| `digital_source_type` | string | No | IPTC `trainedAlgorithmicMedia` or `compositeWithTrainedAlgorithmicMedia` URI (mutually exclusive with signed `media`) |
| `placement` | string | No | `"gathered"` (default) or `"created"` (requires `branded_gp_id` and `media`; `parentOf` is always created) |
| `action_history` | array | No | Actions between a `parentOf` and the input. Each entry: `{action, digitalSourceType?, placement?, description?, softwareAgent?: {"software_agent_id": "swagent_..."}, when?: "<RFC3339 UTC>", parameters?: {...}}` |

**Allowed C2PA actions in `action_history`** (plus any domain-validated reverse-DNS custom action):
`c2pa.addedText`, `c2pa.adjustedColor`, `c2pa.changedSpeed`, `c2pa.converted`, `c2pa.cropped`, `c2pa.deleted`, `c2pa.drawing`, `c2pa.dubbed`, `c2pa.edited`, `c2pa.edited.metadata`, `c2pa.enhanced`, `c2pa.filtered`, `c2pa.mastered`, `c2pa.mixed`, `c2pa.orientation`, `c2pa.published`, `c2pa.remixed`, `c2pa.repackaged`, `c2pa.resized`, `c2pa.resized.proportional`, `c2pa.transcoded`, `c2pa.translated`, `c2pa.trimmed`, `c2pa.unknown`, `c2pa.watermarked.unbound`.

Every C2PA action in `action_history` requires `digitalSourceType` (`400 MissingDigitalSourceType`), **except** `c2pa.converted`, `c2pa.edited.metadata`, `c2pa.enhanced`, `c2pa.published`, `c2pa.repackaged`, `c2pa.resized.proportional`, `c2pa.transcoded`, and `c2pa.watermarked.unbound`. Only `c2pa.translated` accepts `parameters` (requiring BCP 47 `sourceLanguage` and `targetLanguage`).

### `creation`

Requires `branded_gp_id` and an unsigned input (cannot combine with `parentOf` or `ai_system`). Always created.

```json
["creation", {
  "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
  "softwareAgent": {"software_agent_id": "swagent_..."},
  "when": "2026-08-22T12:00:00Z",
  "description": "Generated from a text prompt"
}]
```

---

## Signed Inputs and Ingredients

`signed_input_policy` (input file) and `signed_ingredient_policy` (ingredient `media`) each accept `"auto"` (default) or `"keep"`:

| Existing C2PA data | `"auto"` (default) | `"keep"` |
| --- | --- | --- |
| Readable manifest (valid or invalid) | Kept as `parentOf` with validation results recorded (unless `ai_system` source-class check refuses an input) | Kept with validation results recorded |
| Manifest referenced only by URL | Refused (`400`) | Refused (`400`) |
| Unreadable / malformed C2PA data | Removed with a warning; signed as unsigned (a `redact` or `transcode` on that input then fails) | Refused (`400`) |

### `ai_system` source-class check (under `"auto"`)

When an `ai_system` assertion is present under `"auto"`, Trufo walks the input's `parentOf` chain by each manifest's first action (`c2pa.created` → origin; `c2pa.opened` → follow parent) and classifies the input:

| Origin | AI edit on walk | Source class | Behavior under `"auto"` + `ai_system` |
| --- | --- | --- | --- |
| `trainedAlgorithmicMedia` | Any | `ai_generated` | Kept (with notice) |
| `compositeWithTrainedAlgorithmicMedia` | Any | `ai_modified` | Kept (with notice) |
| Any other / unknown | Yes | `ai_modified` | Kept (with notice) |
| `digitalCapture`, `computationalCapture`, `compositeCapture`, `negativeFilm`, `positiveFilm`, `print` | No | `camera_captured` | **Refused (`400`) regardless of actions** |
| `digitalCreation`, `humanEdits` | No | `human_created` | **Refused (`400`) regardless of actions** |
| Other / unknown | No | `other` / `none` | Kept (with notice) |

Set `signed_input_policy: "keep"` (or omit `ai_system`) to skip this refusal.

---

## AI Systems (`/ai-system/*`)

Production hosts only (`api.trufo.ai` or `eu.api.trufo.ai`). Registrations are immutable and shared across all endpoints (including `test.api.trufo.ai`).

**Auth:** `c2pa-sign-prod`, `c2pa-sign-test`, `watermark-prod`, `watermark-test`, or MFA-verified access token with `c2pa_sign`. No plan required.

### `POST /ai-system/add`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | Yes | AI system name (paired with `version` as C2PA `softwareAgent`) |
| `version` | string | Yes | Version string (register a new AI system per version) |
| `ai_involvement_modes` | string[] | Yes | Non-empty subset of `["ai_generated", "ai_modified"]` |
| `c2pa_first_party_attestable` | boolean | No | Default `false`. Requires Created Assertion Acknowledgement accepted in dashboard (`403` otherwise) |
| `c2pa_ai_disclosure` | object | No | C2PA 2.4 §18.28 model disclosure: `{modelType (req), modelName?, modelIdentifier?, contentProfile?: {humanOversightLevel: "fully_autonomous" \| "prompt_guided" \| "human_validated"}, scientificDomain?, metadata?}` |
| `nickname` | string | No | Internal display label |

**Response (201):** `{"ai_system_id": "aisys_..."}`.

### `POST /ai-system/list`

**Request:** `{}`. **Response (200):** `{"items": [{ai_system_id, name, version, ai_involvement_modes, c2pa_first_party_attestable, c2pa_ai_disclosure, nickname, status}, ...]}` (up to 1,000, newest first).

### `POST /ai-system/status`

**Request:** `{"ai_system_id": "aisys_...", "status": "active" | "inactive"}`. Idempotent. Deactivating blocks new signs/embeds; existing watermarked content keeps resolving. **Errors:** `404 AISystemNotFound`.

---

## Software Agents (`/c2pa/software-agent/*`)

Regional (register on the same endpoint you sign against). **Auth:** `c2pa-sign-prod`, `c2pa-sign-test`, or access token with `c2pa_sign`.

- **`POST /c2pa/software-agent/add`:** Request `{"agent": {"name": str, "version"?: str, "operating_system"?: str}, "nickname"?: str}`. Response (201): `{"software_agent_id": "swagent_..."}`.
- **`POST /c2pa/software-agent/list`:** Request `{}`. Response (200): `{"items": [{software_agent_id, nickname, agent}, ...]}`.
