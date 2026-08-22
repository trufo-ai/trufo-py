# Trufo C2PA Signing API

C2PA manifest generation: hosted signing (direct or via S3), distributed signing
that keeps media on your machine, watermark recovery, and the assertion records
reused across signing requests.

- **Global API:** `https://api.trufo.ai`
- **Europe API:** `https://eu.api.trufo.ai`
- **Test API:** `https://test.api.trufo.ai` — same routes, signed with a test certificate

See [api_trufo.md](api_trufo.md) for authentication, error conventions, and regions.

---

## Common Declarations

### Endpoints

| Endpoint | Scope | Plan |
| -------- | ----- | ---- |
| `POST /c2pa/sign` | `c2pa-sign-prod` (test host: `c2pa-sign-test`) | C2PA Signing |
| `POST /c2pa/io/get-s3-url` | `c2pa-sign-prod` or `c2pa-sign-test` | C2PA Signing (production keys) |
| `POST /c2pa/ai-disclosure/add`, `/list` | `c2pa-sign-prod` or `c2pa-sign-test` | — |
| `POST /c2pa/software-agent/add`, `/list` | `c2pa-sign-prod` or `c2pa-sign-test` | — |
| `POST /content/recover` | `content-recover-prod` (test host: `content-recover-test`) | C2PA Signing (production keys) |
| `POST /bind/watermark`, `/bind/commit` | `watermark-test` (🟠 **test only**) | — |

An account access token with the `c2pa_sign` permission may be used instead of an
API key on the signing and assertion-record endpoints; `/content/recover` requires
an API key.

Distributed signing is performed by the SDK over a dedicated protocol whose
endpoints are an internal detail of that protocol, not a public interface. Use
`sign_c2pa_distributed()` — see [Signing modes](#signing-modes).

Production signing additionally requires completed Organization Validation —
without it, production signing returns `403 MissingOrganizationValidation`.

### Automatic assertions

Every manifest signed through Trufo carries an `ai.trufo.identity` assertion,
injected server-side and not suppressible by the caller:

| Field | Presence | Description |
| ----- | -------- | ----------- |
| `oid` | Always | Organization id of the signing credential |
| `orgName` | With active OV | The organization's validated legal name |

### Response warnings

Sign responses include a `warnings` list of non-fatal notices — work the server
completed differently than requested. The Python SDK re-emits each as a
`TrufoServerWarning`:

```python
import warnings

from trufo import TrufoServerWarning, sign_c2pa

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always", TrufoServerWarning)
    signed = sign_c2pa(api_key, media_bytes, actions=actions)

if caught:  # signed, but something was skipped — e.g. no watermark embedded
    for w in caught:
        log.warning("Trufo notice: %s", w.message)
```

`warnings.simplefilter("ignore", TrufoServerWarning)` silences only Trufo's
notices, `"error"` turns them into exceptions, and `logging.captureWarnings(True)`
routes them to the `py.warnings` logger.

Messages you may see: a declined watermark
(`Watermarking is not supported for '<mime>' media…`), a best-effort watermark
failure (`Watermarking failed: …`), and SDK-version deprecation notices.

### Errors

Beyond the platform-wide codes in [api_trufo.md](api_trufo.md):

| Status | `detail` | Meaning |
| ------ | -------- | ------- |
| 400 | *(message)* | Request validation — malformed `actions`/`assertions`, watermark contract violations, an unsatisfiable redaction |
| 400 | `InvalidCawgIdentityId` | Unknown `cawg_identity_id` |
| 400 | `MissingC2PACustomDomain` | A `custom` assertion without a label |
| 403 | `MissingOrganizationValidation` | Production signing before OV completes |
| 403 | `InvalidC2PACustomDomain` | The label's domain is not domain-validated for your organization |
| 403 | `NoEligiblePlan` | The organization lacks the required plan |
| 404 | *(message)* | Unknown `ai_disclosure_id` or `software_agent_id` |

**Retries and billing.** A sign is metered when it completes, so a failed request
never bills. Retries are not deduplicated: if a request completed but its response
was lost, retrying produces a second signed output and a second billed sign. Prefer
a generous client timeout over aggressive retries.

---

## Signing Modes

Four flows, one request shape. `actions` and `assertions` behave identically in all
of them.

| | Hosted | Hosted (S3) | Distributed |
| --- | --- | --- | --- |
| Entry | `POST /c2pa/sign` | `get-s3-url` → upload → `POST /c2pa/sign` | `sign_c2pa_distributed()` (SDK only) |
| Media reaches Trufo | Yes, in the body | Yes, via ephemeral S3 | **No** — only the claim hash |
| Manifest assembled by | Trufo | Trufo | Your process (`trufo-provenance`) |
| Signing key | Trufo | Trufo | Trufo |
| Extra requirements | — | — | Local engine extra, `tsa` key, Linux x86_64 + CPython 3.12 |

Each mode has a test variant: use a `c2pa-sign-test` key against
`test.api.trufo.ai`. Test signing skips OV and billing, produces manifests signed by
the test certificate (not accepted by conformant validators), and creates no
permanent signing record.

### `POST /c2pa/sign`

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `media_input` | string | Yes\* | base64-encoded input media |
| `media_input_s3` | string | Yes\* | Opaque reference from `/c2pa/io/get-s3-url` |
| `actions` | list | Yes | `[name, params]` pairs, applied in order |
| `assertions` | list | No | `[name, params]` pairs recorded in the manifest |
| `manifest_title` | string | No | The manifest title of the signed output asset. Omitted from the manifest when unset. |
| `ingredient_title` | string | No | The ingredient title assigned to the input asset (parent, via a `c2pa.opened` action). When unset: the input's manifest title, if it exists; otherwise, `input.{ext}`. |
| `thumbnail_settings` | object | No | Thumbnail policy and size preset. Defaults to `{"policy": "auto", "size": "medium"}`. |

\* Provide exactly one.

**Response (200):** `media_output` (base64) or `media_output_s3` (presigned download
URL), plus `warnings`.

Fallback titles are derived, not authored: an embedded manifest title is third-party
text re-signed as-is. Pass explicit titles when you need deterministic, curated
output — typically the asset's filename.

Thumbnail settings have the same shape in hosted, S3, and distributed signing:

```python
from trufo.c2pa import ThumbnailPolicy, ThumbnailSettings, ThumbnailSize

settings = ThumbnailSettings(
    policy=ThumbnailPolicy.AUTO,
    size=ThumbnailSize.HIGH,
)
signed_bytes = sign_c2pa(api_key, media_bytes, thumbnail_settings=settings)
```

`AUTO` generates a claim thumbnail and thumbnails for supported ingredients
that do not already carry one. `AUTO_NO_INGREDIENT` generates only the claim
thumbnail, while preserving inherited ingredient thumbnails. `NONE` generates
no thumbnails, while also preserving inherited ingredient thumbnails. The
`MEDIUM` preset is 512 px at WebP quality 80; `HIGH` is 1024 px at quality
90. Image alpha transparency is preserved.

### `POST /c2pa/io/get-s3-url`

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `mime_type` | string | Yes | MIME type of the object you will upload |
| `duration` | string | No | Currently `"5m"` |

**Response (200):** `media_input_s3` (opaque reference), `upload_url` (presigned PUT
— send the same `Content-Type`), `expires_at`, `duration`.

Upload, then call `/c2pa/sign` with `media_input_s3`. Trufo re-probes the uploaded
bytes rather than trusting the declared type. The signed output is returned as a
presigned download URL valid for the remainder of the reference's lifetime.

### Distributed signing

Distributed signing keeps media entirely on your machine: `trufo-provenance`
assembles and hashes the C2PA claim locally, and only the claim hash is sent to
Trufo to be signed.

This flow is available **exclusively through the SDK**. It is a multi-step protocol
in which the client and server exchange state that must stay consistent for the
resulting manifest to be valid, so the individual calls are not a supported public
interface and are not documented here — driving them directly produces invalid
manifests and unusable signing records.

```python
from trufo import sign_c2pa_distributed

signed_bytes = sign_c2pa_distributed(api_key, media_bytes, actions=actions)
```

Requirements: a local engine extra (`trufo[local-sign-only]` or
`trufo[local-full]`), a `tsa` key for timestamping, a `c2pa-sign-prod` key, and
completed OV. See the [signing quickstart](../quickstart/2_c2pa_signing.md).

---

## Request Schema

### Server selection

Call the endpoint for the region you want; there is no routing parameter. See
[Regions](api_trufo.md#regions).

```python
from trufo.api.endpoints import TRUFO_API_URL_EUROPE

signed_bytes = sign_c2pa(api_key, media_bytes, trufo_api_url=TRUFO_API_URL_EUROPE)
```

Organizations with a dedicated API or TSA pass those hosts explicitly via
`trufo_api_url` and `trufo_tsa_url`.

### Supported media types

| Category | MIME types |
| -------- | ---------- |
| Image | `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `image/avif`, `image/tiff`, `image/jxl`, `image/x-adobe-dng`, `image/svg+xml` |
| Audio | `audio/mpeg`, `audio/flac`, `audio/wav`, `audio/mp4` |
| Video | `video/mp4`, `video/quicktime` |
| Document | `application/pdf` |

The type is detected from the bytes, not from any declared value. Common aliases
resolve automatically (`audio/x-wav` → `audio/wav`, `audio/x-m4a` → `audio/mp4`);
an MP4 with no video stream is treated as `audio/mp4`. Contact
[support@trufo.ai](mailto:support@trufo.ai) about additional formats.

### `actions`

Ordered `[name, params]` pairs. Each media-transforming action feeds the next.

| Action | Params | Description |
| ------ | ------ | ----------- |
| `"transcode"` | `{"target_mime_type": "<mime>"}` | Convert to another format in the same media class |
| `"watermark"` | `{"mode": "<mode>", "effort_policy": "<effort_policy>", ...}` | Embed a Trufo watermark (off by default) |
| `"publish"` | `{}` | Mark for final distribution |
| `"redact"` | `{"label": "<label>", "reason": "<reason>"}` | Remove an assertion from the input's history |

#### `transcode`

Converts within a media class; cross-class conversion is rejected. The input must
already carry a C2PA manifest. Targets: `image/jpeg`, `image/png`, `image/webp`,
`image/avif`, `image/tiff`, `image/gif`, `audio/flac`, `audio/wav`, `audio/mp4`,
`audio/mpeg`, `video/mp4`, `video/quicktime`. Not available in distributed signing.

#### `watermark`

Embeds an imperceptible Trufo Pawprint watermark, declared in the manifest by a
`c2pa.watermarked.bound` action and a `c2pa.soft-binding` assertion with algorithm
`ai.trufo.pawprint.watermark`. **Off unless requested.** At most one watermark
action per request.

| Param | Type | Description |
| ----- | ---- | ----------- |
| `mode` | string | `"provenance"` (default) or `"compliance"` — what the embedded watermark ID resolves to |
| `ai_compliance_label` | string | Required in compliance mode, rejected otherwise: `"ai_generated"`, `"ai_modified"`, or `"undeclared"` |
| `effort_policy` | string | Failure tolerance, below; `"require"` for a bare action. `effort` is a deprecated alias (a warning is returned; providing both is an error) |

**Provenance mode** embeds a per-content watermark ID linked to this signing
record. **Compliance mode** (🟠 **test only**) embeds
your organization's reusable mark for the declared AI class: one watermark ID
per (label, modality) pair, issued on first use and shared by every
compliance sign after that. To watermark media you sign yourself, use
[standalone binding](#standalone-binding) instead of a sign-flow action.

| `effort_policy` | Unsupported format | Runtime failure |
| --------------- | ------------------ | --------------- |
| `"require"` (default for a bare action) | Error | Error |
| `"require_if_supported"` | Signs unwatermarked, with a warning | Error |
| `"best_effort"` | Signs unwatermarked, with a warning | Signs unwatermarked, with a warning |

Watermarkable formats: JPEG, PNG, WebP, TIFF, WAV, FLAC, MP3, M4A. See the
[watermarking quickstart](../quickstart/6_watermarking.md).

#### `redact`

Removes one named assertion from the input's existing manifest history, wherever it
occurs (C2PA §6.8). Repeat the entry for several labels; the same label may not be
targeted twice.

| Label | Carries |
| ----- | ------- |
| `c2pa.metadata` | Capture date/time, location, GPS, device |
| `cawg.metadata` | Byline/creator, people depicted, credit, rights |
| `cawg.training-mining` | AI-training and data-mining permissions |
| `cawg.identity` | The identity assertion binding a signer to that manifest |

Append `__N` (e.g. `c2pa.metadata__1`) to target one disambiguated instance; a bare
label matches only the unnumbered one.

`reason` is required — a preset, or a custom reverse-DNS value whose domain your
organization has domain-validated:

| Preset | Redacted because the assertion contains |
| ------ | --------------------------------------- |
| `c2pa.PII.present` | Personally identifiable information |
| `c2pa.invalid.data` | Incorrect data |
| `c2pa.trade-secret.present` | Commercially sensitive information |
| `c2pa.government.confidential` | Government-restricted information |

Redaction requires the input to have a manifest, and every label must resolve —
otherwise the request fails and nothing is signed. An entry's position sets where
its `c2pa.redacted` action appears, but redaction always targets the input's
existing history, never the output of a transform in the same call.

### `assertions`

Ordered `[name, params]` pairs, recorded as gathered assertions.

| Assertion | Params | C2PA label |
| --------- | ------ | ---------- |
| `"ai_disclosure"` | `{"ai_disclosure_id": "<id>", "set_source_type": false}` | `c2pa.ai-disclosure` |
| `"cawg_metadata"` | `{"assertion": {…}}` | `cawg.metadata` |
| `"cawg_training"` | `{"assertion": {…}}` | `cawg.training-mining` |
| `"cawg_identity"` | `{"cawg_identity_id": "<id>"}` | `cawg.identity` |
| `"custom"` | `{"label": "<reverse-dns>", "assertion": {…}}` | Your label |
| `"ingredient"` | `{"relationship": "<rel>", …}` | `c2pa.ingredient.v3` |

#### `ai_disclosure`

Marks content as AI-generated. With no parameters, the minimal body
`{"modelType": "c2pa.types.model"}` is used. To describe a specific model, register
the body first (below) and pass the returned `ai_disclosure_id` — inline bodies are
rejected.

`set_source_type: true` additionally sets `digitalSourceType` to
`trainedAlgorithmicMedia` on the parent ingredient, but only when the input has no
existing manifest. This field is new in C2PA 2.4 and many validators still flag
manifests carrying it, so leave it off unless you can tolerate that.

#### `cawg_metadata`

JSON-LD creator metadata. `assertion` must include an `@context` whose prefixes are
allowlisted and whose URIs match exactly:

| Prefix | URI |
| ------ | --- |
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

#### `cawg_training`

Declares AI training and data-mining permissions. `assertion` must contain exactly
one key, `entries`, mapping entry names to `{"use": …, "constraint_info"?: …}`.
`use` is `allowed`, `notAllowed`, or `constrained`. Standard entry names include
`cawg.ai_training`, `cawg.ai_generative_training`, `cawg.ai_inference`, and
`cawg.data_mining`.

#### `cawg_identity`

| Value | Environment | Description |
| ----- | ----------- | ----------- |
| `"test"` | Test | Shared Trufo test certificate; not recognized by validators |
| `"org_interim"` | Test, production | Your organization's CAWG interim certificate; requires the CAWG Organization Certificate plan |

#### `custom`

Embeds an assertion under your own reverse-DNS label (C2PA §6.2). The label must be
dot-separated reverse-DNS, may not use the `c2pa` namespace, and may not contain
`__`. Your organization must hold an active domain validation for the corresponding
domain — `com.example.metadata` requires `example.com`.

#### `ingredient`

Declares a prior or contributing asset. Ingredients are your workflow's account of
the asset, not a Trufo attestation; whenever any are present the manifest's
`allActionsIncluded` becomes `false`.

| Param | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `relationship` | string | Yes | `inputTo` (a prompt, model, or dataset) or `componentOf` (a placed component) |
| `title` | string | No | The ingredient title (`dc:title`). When unset: the media's manifest title, if it exists; otherwise, `ingredient_{n}.{ext}` (media-less entries: `ingredient_{n}`). |
| `data_types` | list | No | `[{"type": "c2pa.types.<kind>", "version": "…"}]` |
| `digital_source_type` | string | No | The IPTC `trainedAlgorithmicMedia` or `compositeWithTrainedAlgorithmicMedia` URI |
| `media` | string | For `componentOf` | base64 bytes; must be a thumbnail-capable image (JPEG, PNG, WebP, GIF, TIFF) |

Media carrying its own C2PA manifest is validated and referenced; manifest-free
media is thumbnailed as a described visual record, not a cryptographic binding, and
cannot also declare `digital_source_type`.

---

## Standalone Binding

🟠 **test only**.

Bind embeds a Trufo watermark **without** C2PA signing: you sign the
watermarked media with your own certificate. In provenance mode, the record
starts incomplete and `/bind/commit` completes it by verifying your signed
manifest declares the mark. In compliance mode a single call embeds your
organization's mark for a declared AI class — there is nothing to commit.
SDK: `bind_watermark_test()` / `bind_commit_test()`.

### `POST /bind/watermark`

**Auth:** API key with the `watermark-test` scope.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `media_input` | string | Yes | base64-encoded media to watermark |
| `mode` | string | No | `"provenance"` (default) or `"compliance"` |
| `ai_compliance_label` | string | In compliance mode | `"ai_generated"`, `"ai_modified"`, or `"undeclared"`; rejected outside compliance mode |

**Response (200):**

| Field | Type | Description |
| ----- | ---- | ----------- |
| `media_output` | string | base64-encoded watermarked media |
| `wid` | string | The embedded watermark id |
| `cid` | string or null | Record id for `/bind/commit`; null in compliance mode |

Bind has no effort tiers: the watermark is always required, and an
unsupported format (outside the watermarkable table above) is an error.

### `POST /bind/commit`

**Auth:** API key with the `watermark-test` scope.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `cid` | string | Yes | Record id from `/bind/watermark` |
| `media_input` | string | Yes | base64-encoded C2PA-signed watermarked media |

The manifest must declare the mark: a `c2pa.soft-binding` assertion with
algorithm `ai.trufo.pawprint.watermark` and the record's watermark id as its
block value, paired with a `c2pa.watermarked.bound` action, per the C2PA
specification. The manifest is checked for this declaration, not for trust
status — sign with whatever certificate you use.

**Response (200):** `cid`, `wid`.

**Errors:**

| Status | Meaning |
| ------ | ------- |
| 400 | Invalid mode/label pairing, unsupported media format, no parseable manifest, or the manifest does not declare the record's mark (the record stays incomplete — fix and resubmit) |
| 404 | Unknown `cid`, or a record not created by `/bind/watermark` |

---

## Watermark Recovery

### `POST /content/recover`

Decode a Trufo watermark and return its provenance — useful after a manifest has
been stripped.

**Auth:** API key with the `content-recover-prod` scope on the production hosts, or
`content-recover-test` on the test host (`test.api.trufo.ai`). Each key works only
against its own host tier.

| Field | Type | Required |
| ----- | ---- | -------- |
| `media_input` | string | Yes — base64-encoded media |

**Response (200):**

| Field | Type | Description |
| ----- | ---- | ----------- |
| `detected` | bool | Whether a Trufo watermark was found |
| `wid` | string or null | The decoded watermark id |
| `confidence` | float or null | Detection strength in (0, 1] — how strongly the signal was recovered, not a probability of correctness |
| `manifest` | object or null | Provenance marks: the stored manifest, when available for that record |
| `ai_compliance_label` | string or null | Compliance marks: the declared AI class |
| `oid` | string or null | Your organization ID, present only when the mark is your organization's |

Decoding accepts any parseable image or audio input, not only the formats supported
for embedding. What a detected watermark discloses depends on its kind: a
provenance mark reveals its details for content your own organization signed
(other organizations' marks report `detected` without further detail), while a
compliance mark reveals its declared AI class to any decoder — with `oid` marking
the ones your organization owns.

---

## Assertion Records

Reusable bodies registered once and referenced by id when signing. Both groups
accept a `c2pa-sign-prod` or `c2pa-sign-test` key and infer the owning organization
from the credential.

### `POST /c2pa/ai-disclosure/add`

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `assertion` | object | Yes | A `c2pa.ai-disclosure` body (C2PA 2.4 §18.29.1) |
| `nickname` | string | No | Display label; never signed |

**Response (201):** `ai_disclosure_id`, shaped `aidisc_<uuid>`.

`assertion` fields:

| Field | Type | Required | Notes |
| ----- | ---- | -------- | ----- |
| `modelType` | string | Yes | One of the permitted C2PA model-type values, e.g. `c2pa.types.model`, `c2pa.types.model.pytorch`, `c2pa.types.model.huggingface.transformers` |
| `modelName` | string | No | Human-readable model name |
| `modelIdentifier` | string | No | Machine-readable identifier (e.g. a PURL) |
| `contentProfile` | object | No | Only `humanOversightLevel`: `fully_autonomous`, `prompt_guided`, or `human_validated` |
| `scientificDomain` | string or list | No | Dotted domain codes, e.g. `cs.AI` |
| `metadata` | object | No | Free-form |

### `POST /c2pa/ai-disclosure/list`

**Request:** `{}`. **Response (200):** `items[]` of
`{ai_disclosure_id, nickname, assertion}`.

### `POST /c2pa/software-agent/add`

Register the software agent that produced or edited content, so it can be
referenced by id rather than repeated inline.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `agent` | object | Yes | Generator-info map: `name` (required), `version`, `operating_system` |
| `nickname` | string | No | Display label; never signed |

**Response (201):** `software_agent_id`, shaped `swagent_<uuid>`.

### `POST /c2pa/software-agent/list`

**Request:** `{}`. **Response (200):** `items[]` of
`{software_agent_id, nickname, agent}`.

---

## Reference

- Signing quickstart: [../quickstart/2_c2pa_signing.md](../quickstart/2_c2pa_signing.md)
- Platform conventions and API keys: [api_trufo.md](api_trufo.md)
- Certificates, OCSP, and TSA: [api_certs.md](api_certs.md)
