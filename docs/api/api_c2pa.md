# Trufo C2PA Signing API

C2PA manifest generation in Cloud mode (direct or via S3) and in Local mode, which
keeps media on your machine; watermark recovery; AI system registration; and the
assertion records reused across signing requests.

- **Global API:** `https://api.trufo.ai`
- **Europe API:** `https://eu.api.trufo.ai`
- **Test API:** `https://test.api.trufo.ai` — C2PA signing with a test certificate, in Cloud mode (direct) and Local mode; watermark recovery and standalone binding

See [api_trufo.md](api_trufo.md) for authentication, error conventions, and regions.

---

## Common Declarations

### Endpoints

| Endpoint | Scope | Plan |
| -------- | ----- | ---- |
| `POST /c2pa/sign` | `c2pa-sign-prod` (test host: `c2pa-sign-test`) | C2PA Signing |
| `POST /io/get-s3-upload-url` | `c2pa-sign-prod` or `watermark-prod` (production hosts) | Corresponding signing or watermark access |
| `POST /c2pa/io/get-s3-url` **(deprecated alias)** | Same as `/io/get-s3-upload-url` | Same as `/io/get-s3-upload-url` |
| `POST /ai-system/add`, `/list`, `/status` | `c2pa-sign-prod` or `c2pa-sign-test` (production hosts only) | — |
| `POST /c2pa/ai-disclosure/add`, `/list` **(deprecated)** | `c2pa-sign-prod` or `c2pa-sign-test` (production hosts only) | — <!-- TODO(sunset-2027-01-31): this row goes; successor the /ai-system row --> |
| `POST /c2pa/software-agent/add`, `/list` | `c2pa-sign-prod` or `c2pa-sign-test` (production hosts only) | — |
| `POST /content/recover` | `content-recover-prod` (test host: `content-recover-test`) | C2PA Signing or Watermark API |
| `POST /bind/watermark`, `/bind/reserve`, `/bind/commit` | `watermark-prod` (test host: `watermark-test`) | C2PA Signing or Watermark API |

An account access token with the `c2pa_sign` permission may be used instead of an
API key on the signing, AI system, assertion-record, and content-record endpoints;
`/content/recover` and the `/bind/*` endpoints require an API key.

Local mode: see [Signing Modes](#signing-modes).

Production signing additionally requires completed Organization Validation —
without it, production signing returns `403 MissingOrganizationValidation`.

### Routes

Every production sign or bind creates a [content record](#content-records) whose
`origin` names its route:

| Route | SDK functions | `origin` |
| ----- | ------------- | -------- |
| C2PA Signing, Cloud (direct or via S3) | `sign_c2pa()`, `submit_c2pa_sign()` | `c2pa_hosted` |
| C2PA Signing, Local | `sign_c2pa_distributed()`, or the [Docker image](../local/docker.md) | `c2pa_distributed` |
| Watermarking, Cloud | `bind_watermark()`, then `bind_commit()` | `bind_hosted` |
| Watermarking, Local | `bind_reserve()`, `watermark_media()`, then `bind_commit()` | `bind_distributed` |

### Automatic assertions

Every manifest signed through Trufo carries an `ai.trufo.identity` assertion,
injected server-side and not suppressible by the caller:

| Field | Presence | Description |
| ----- | -------- | ----------- |
| `oid` | Always | Organization id of the signing credential |
| `orgName` | With active OV | The organization's validated legal name |

### Response warnings

Sign responses include a `warnings` list of non-fatal notices — work the server
completed differently than requested, and what Trufo found in the C2PA data of the
input or an ingredient. In Cloud mode, the Python SDK re-emits each as
a `TrufoServerWarning`; in Local mode, the engine emits each as a plain `UserWarning`,
the base class of `TrufoServerWarning`, so filter on `UserWarning` to catch both:

```python
import warnings

from trufo import TrufoServerWarning, sign_c2pa

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always", TrufoServerWarning)
    signed = sign_c2pa(api_key, media_bytes, actions=actions)

if caught:  # signed, with notices — e.g. no watermark embedded, or an untrusted input manifest
    for w in caught:
        log.warning("Trufo notice: %s", w.message)
```

`warnings.simplefilter("ignore", TrufoServerWarning)` silences only Trufo's
notices, `"error"` turns them into exceptions, and `logging.captureWarnings(True)`
routes them to the `py.warnings` logger.

<!-- TODO(sunset-2027-01-31): the deprecated mode and ai_disclosure clauses go; successor none -->

Messages you may see:

- A declined watermark (`Watermarking is not supported for '<mime>' media…`) or a
  best-effort watermark failure (`Watermarking failed: …`).
- What Trufo found in the C2PA data of the input or an ingredient: see
  [Signed inputs and ingredients](#signed-inputs-and-ingredients).
- Deprecations: the watermark [`mode`](#watermark), the
  [`ai_disclosure`](#ai_disclosure) entry and, in Local mode, the
  [engine version](#local-mode).

### Errors

Beyond the platform-wide codes in [api_trufo.md](api_trufo.md):

| Status | `detail` | Meaning |
| ------ | -------- | ------- |
| 400 | *(message)* | Request validation — malformed `actions`/`assertions`, watermark contract violations, an unsatisfiable redaction, a refused [`ingredient`](#ingredient) or [signed input](#signed-inputs-and-ingredients) |
| 400 | `AISystemInactive: …` | An inactive AI system (see [`ai_system`](#ai_system)) |
| 400 | `UnsupportedAssertion: …` | The deprecated `ai_disclosure` entry from 2027-01-31T00:00:00+00:00 (see [`ai_disclosure`](#ai_disclosure)) <!-- TODO(sunset-2027-01-31): this row goes; successor none --> |
| 400 | `UnsupportedParameter: …` | The deprecated watermark `mode` from 2027-01-31T00:00:00+00:00 (see [`watermark`](#watermark)) <!-- TODO(sunset-2027-01-31): this row goes; successor none --> |
| 400 | `InvalidCawgIdentityId` | Unknown `cawg_identity_id` |
| 400 | `MissingC2PACustomDomain` | A `custom` assertion without a label |
| 400 | `UnsupportedSDKVersion: …` | Local mode: the `trufo-py` or `trufo-provenance` version is below the minimum or past its support, or the engine is too old for a feature the request uses; the detail names the package and the reason (see [Local mode](#local-mode)) |
| 403 | `MissingOrganizationValidation` | Production signing before OV completes |
| 403 | `InvalidC2PACustomDomain` | The label's domain is not domain-validated for your organization |
| 403 | `NoEligiblePlan` | The organization lacks the required plan |
| 403 | `BPVNotActive: <reason>` | Branded Product Validation (BPV) for the generator product is not active; the detail explains why |
| 403 | `C2PACreatedUserAssertionsNotAuthorized: <reason>` | A created declaration this request is not authorized to make (see [`assertions`](#assertions)); the detail explains why |
| 404 | *(message)* | Unknown `ai_disclosure_id` or `software_agent_id` <!-- TODO(sunset-2027-01-31): the ai_disclosure_id half goes; successor none --> |
| 404 | `AISystemNotFound` | Unknown or another organization's `ai_system_id` (see [`ai_system`](#ai_system)) |
| 404 | `GProductNotFound` | No such generator product in your organization |
| 410 | `Test keys are not accepted on this host. …` | Local mode with a `c2pa-sign-test` key on a production host (see [Signing Modes](#signing-modes)) |
| 410 | `Test keys can't use upload links. …` | A test key on a production host's upload link (see [`POST /io/get-s3-upload-url`](#post-ioget-s3-upload-url)) |
| 501 | *(message)* | An unsupported watermark option: `"per_asset"` allocation, or the deprecated `mode` `"compliance"` (see [`watermark`](#watermark)) <!-- TODO(sunset-2027-01-31): the row's deprecated mode "compliance" clause goes; successor none --> |

**Retries and billing.** A sign is metered when it completes, so a failed request
never bills. Retries are not deduplicated: if a request completed but its response
was lost, retrying produces a second signed output and a second billed sign. Prefer
a generous client timeout over aggressive retries. `/bind/watermark` bills at
delivery on the same terms; a per-embed `/bind/reserve` bills at `/bind/commit`,
and a per-AI-system one when issued; `/bind/commit` is idempotent for an identical
retry. See [watermark billing](#watermark-billing).

---

## Signing Modes

Three flows, one operation shape. `actions` and `assertions` behave identically in all
of them, except where noted.

| | Cloud, direct | Cloud, via S3 | Local |
| --- | --- | --- | --- |
| Entry | `POST /c2pa/sign` | `/io/get-s3-upload-url` → upload → `POST /c2pa/sign` with TASK | `sign_c2pa_distributed()` in the [Python SDK](../local/python.md), or `POST /c2pa/sign` with file paths on the [Docker image](../local/docker.md) |
| Media reaches Trufo | Yes, in the body | Yes, via ephemeral S3 | **No** — the original media file is not sent |
| Manifest assembled by | Trufo | Trufo | Your machine (`trufo-provenance`) |
| Signing key | Trufo | Trufo | Trufo |
| Extra requirements | — | — | See [Local mode with the Python SDK](../local/python.md#requirements) or [Local mode with the Docker image](../local/docker.md#before-you-start) |

Cloud mode (direct) and Local mode have test variants on the test host only: use
a `c2pa-sign-test` key against `test.api.trufo.ai`, which the Python SDK's `_test`
helpers call by default. Test signing skips OV, produces manifests signed by the
test certificate (not accepted by conformant validators), and creates no
permanent signing record.

**Errors:**

| When | Status | `detail` |
| ---- | ------ | -------- |
| Local mode with a `c2pa-sign-test` key on a production host | 410 | `Test keys are not accepted on this host. Please use test.api.trufo.ai.` |

### `POST /c2pa/sign`

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `media_input` | string | Yes\* | base64-encoded input media |
| `media_input_s3` | string | Yes\* | Opaque reference from `/io/get-s3-upload-url`; TASK only |
| `execution_mode` | string | No | `request` (default) or `task`; `stream` is unsupported |
| `actions` | list | Yes | `[name, params]` pairs, applied in order |
| `assertions` | list | No | `[name, params]` pairs recorded in the manifest |
| `manifest_title` | string | No | The manifest title of the signed output asset. Omitted from the manifest when unset. |
| `ingredient_title` | string | No | The ingredient title assigned to the input asset (parent, via a `c2pa.opened` action). When unset: the input's manifest title, if it exists; otherwise, `input.{ext}`. |
| `manifest_settings` | object | No | Structured titles, thumbnail settings, and `all_actions_included`. |
| `branded_gp_id` | string | No | One of your organization's branded generator products (`gp_...`, listed on the dashboard's C2PA Signing API page, **Manage** tab); the content is signed as that product. Omit to sign with Trufo's own C2PA signer. |
| `signed_input_policy` | string | No | What happens when the input file already carries a C2PA manifest: `keep` or `auto`. When omitted, `auto` applies. See [Signed inputs and ingredients](#signed-inputs-and-ingredients). |
| `signed_ingredient_policy` | string | No | What happens when an ingredient's media already carries a C2PA manifest: `keep` or `auto`. When omitted, `auto` applies. See [Signed inputs and ingredients](#signed-inputs-and-ingredients). |

\* Provide exactly one: bytes for REQUEST, an S3 reference for TASK. There is no
automatic fallback. REQUEST has a 10 MB (10,000,000-byte) input cap; audio/video
watermarking requires TASK. Test endpoints support REQUEST only.

**REQUEST response (200):** `media_output` (base64), plus `warnings`.
**TASK response (202):** task acceptance, not the completed result; see [Tasks](#tasks).

Fallback titles are derived, not authored: an embedded manifest title is third-party
text re-signed as-is. Pass explicit titles when you need deterministic, curated
output — typically the asset's filename.

`manifest_title` and `ingredient_title` remain supported for compatibility. Do
not supply a title both directly and inside `manifest_settings`.

Manifest settings have the same shape in all three flows:

```python
from trufo.c2pa import ManifestSettings, ThumbnailPolicy, ThumbnailSettings, ThumbnailSize

settings = ManifestSettings(
    manifest_title="signed.jpg",
    ingredient_title="input.jpg",
    thumbnail_settings=ThumbnailSettings(
        policy=ThumbnailPolicy.AUTO,
        size=ThumbnailSize.HIGH,
    ),
)
signed_bytes = sign_c2pa(api_key, media_bytes, manifest_settings=settings)
```

`AUTO` generates a claim thumbnail and thumbnails for supported ingredients
that do not already carry one. `AUTO_NO_INGREDIENT` generates only the claim
thumbnail, while preserving inherited ingredient thumbnails. `NONE` generates
no thumbnails, while also preserving inherited ingredient thumbnails. The
`MEDIUM` preset scales thumbnails down to at most 512 px in height plus width,
at WebP quality 80; `HIGH` to at most 1024 px, at quality 90. Image alpha
transparency is preserved.

### `POST /io/get-s3-upload-url`

Shared by signing and watermarking. `/c2pa/io/get-s3-url` is a deprecated alias
with the same request and response; use `/io/get-s3-upload-url` instead.

Uploads serve [TASK](#tasks) execution, which only the production hosts run, so
they take a `c2pa-sign-prod` or `watermark-prod` key; a test key gets the 410
below. With a test key, use `sign_c2pa_test()` or `bind_watermark_test()`.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `mime_type` | string | Yes | MIME type of the object you will upload |
| `duration` | string | No | `"5m"` or `"standard"`; ignored |

**Response (200):** `media_input_s3` (opaque reference), `upload_url` (presigned PUT
— send the same `Content-Type`), `expires_at`, `duration` (always `"standard"`).

Upload, then call `/c2pa/sign` or `/bind/watermark` with `media_input_s3` and
`execution_mode: "task"`. Arbitrary S3 URLs are not accepted. Trufo checks the
uploaded bytes rather than trusting the declared type.

**Errors:**

| When | Status | `detail` |
| ---- | ------ | -------- |
| A `c2pa-sign-test` or `watermark-test` key on a production host | 410 | `Test keys can't use upload links. On test.api.trufo.ai, send the media in the request.` |

### Upload and download windows

| Link | Valid for |
| --- | --- |
| `upload_url` and `media_input_s3` | 1 hour, until `expires_at` |
| Output `download_url` | Up to 15 minutes; poll `GET /tasks/{task_id}` for a fresh link until `expires_ts`, 24 hours after the task finishes |

Uploaded and output files are deleted automatically 1–2 days after they are created.
A link works for anyone who holds it until it expires; treat links as secrets.

### Tasks

Submission returns HTTP 202 with `task_id`, `task_type` (`c2pa_sign` or
`watermark`), `status`, `startby_ts`, and `timeout_seconds`. IDs and timing are
server-generated; do not supply them in API input.

`GET /tasks/{task_id}` on the same API region returns those fields plus
`create_ts`, `update_ts`, `start_ts`, `finish_ts`, `duration_ms`, `progress`,
`file_size_bytes`, `file_mime_type`, `result`, and `error`. Authenticate with a
key for the same organization and operation. Status is `queued`, `running`,
`succeeded`, `failed`, or `expired`.

| Outcome | Fields |
| --- | --- |
| Signing result | `media_output_s3`, `download_url`, `expires_ts`, optional `cid`/`wid`, `warnings` |
| Watermark result | `media_output_s3`, `download_url`, `expires_ts`, `wid`, optional `cid`, `warnings` |
| Error | Stable `code` and corresponding `http_status`, and `message` when one applies (inside the HTTP 200 status response) |

`media_output_s3` is an opaque reference, not a URL. Download through
`download_url`; it is null after the retained output expires. Task info contains
no media bytes. Polling does not retry a failed task. Watermark completion does
not replace the subsequent `/bind/commit` step. With a per-AI-system watermark,
`wid` is the AI system's watermark ID.

| Checked | Which checks | A refusal |
| --- | --- | --- |
| At submission | Those a REQUEST runs before processing the media: a sign's watermark action, `branded_gp_id` and `assertions`; a bind's `mode` and watermark ID allocation | The HTTP status and `detail` a REQUEST would get; no task is created |
| While processing | The others, among them the [signed-input](#signed-inputs-and-ingredients) refusals and every [`ingredient`](#ingredient) error except the created-placement and unbranded `parentOf` refusals | `status: "failed"` and an `error` with `code` and `http_status`, plus `message` only when the media's format cannot be watermarked |

Error `code`s, with their `http_status`: `invalid_input` (400),
`permission_denied` (403), `input_not_found` (404), `capacity_exceeded` (429),
`processing_failed` (500), `execution_timeout` (504), `worker_lost` (500),
`start_timeout` (503, on an `expired` task) and `queue_submission_failed` (503,
returned as the `detail` of the submission, which gets no `task_id`). For an
`invalid_input` without a `message`, contact support@trufo.ai with the `task_id`.

### S3 task flow

The full flow with curl, signing a video:

```bash
API=https://api.trufo.ai
AUTH="X-API-Key: c2pa-sign-prod:<key>"

# 1. allocate an upload
curl -s -X POST "$API/io/get-s3-upload-url" -H "$AUTH" \
  -H "Content-Type: application/json" -d '{"mime_type": "video/mp4"}'
# {"media_input_s3": "trufos3://…", "upload_url": "https://…", "expires_at": …, "duration": "standard"}

# 2. upload with the same Content-Type
curl -s -X PUT "<upload_url>" -H "Content-Type: video/mp4" --data-binary @input.mp4

# 3. submit the task (HTTP 202)
curl -s -X POST "$API/c2pa/sign" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"media_input_s3": "<media_input_s3>", "execution_mode": "task", "actions": [["publish", {}]]}'
# {"task_id": "…", "task_type": "c2pa_sign", "status": "queued", …}

# 4. poll until "status" is "succeeded" (or "failed" or "expired")
curl -s "$API/tasks/<task_id>" -H "$AUTH"
# {"status": "succeeded", "result": {"download_url": "https://…", "expires_ts": "…", …}, …}

# 5. download the signed file
curl -s -o signed.mp4 "<download_url>"
```

### Local mode

Local mode keeps media on your machine: Trufo's engine, `trufo-provenance`,
assembles and hashes the C2PA claim locally for Trufo to sign; the original media
file is not sent.

This flow runs **through Trufo's engine**, in the Python SDK or the Docker image. It
is a multi-step protocol in which the client and server exchange state that must
stay consistent for the resulting manifest to be valid, so the individual calls are
not a supported public interface and are not documented here — driving them directly
produces invalid manifests and unusable signing records.

```python
from trufo import sign_c2pa_distributed

signed_bytes = sign_c2pa_distributed(api_key, media_bytes, actions=actions)
```

Requirements: a `c2pa-sign-prod` key and completed OV, plus a local engine extra
(`trufo[local-sign-only]` or `trufo[local-full]`) for the
[Python SDK](../local/python.md), or Docker for the
[Docker image](../local/docker.md).

In both, unless set, the input's ingredient title follows the
[`ingredient_title`](#post-c2pasign) fallback, ending in `input.<ext>`; set it
through `manifest_settings` to record the file's name. The generator info records
the host's operating system and kernel release as `operating_system`, for example
`Linux 6.8.0-45-generic`.

`sign_c2pa_distributed()` and `sign_c2pa_distributed_test()` accept
`branded_gp_id`, `signed_input_policy` and `signed_ingredient_policy`, as
`sign_c2pa()` does. Setting either policy, like sending an
[`ai_system`](#ai_system) entry, needs trufo-provenance 2.2.0 or later.

<!-- TODO(sunset-2027-01-31): the versions paragraph and its table go; successor none -->

**Versions.** Local mode with a trufo-provenance version in the table below signs
with its notice in `warnings` until the notice's date, and is refused (400) from
that date. Upgrade `trufo` to 2.2.0 or later with its local engine extra, or move the
[Docker image](../local/docker.md#versions-and-upgrades) to a 2.2 tag. `<version>`
is the installed version.

| trufo-provenance | Notice, until the date | 400, from the date |
| ---------------- | ---------------------- | ------------------ |
| 2.1.x | `trufo-provenance <version> is deprecated and will stop working after 2027-01-31T00:00:00+00:00. Please upgrade.` | `UnsupportedSDKVersion: trufo-provenance <version> is no longer supported (expired 2027-01-31T00:00:00+00:00). Please upgrade.` |
| 2.0.x or earlier (from 0.3.0, the supported minimum) | `trufo-provenance <version> is deprecated and will stop working after 2026-12-31T00:00:00+00:00. Please upgrade.` | `UnsupportedSDKVersion: trufo-provenance <version> is no longer supported (expired 2026-12-31T00:00:00+00:00). Please upgrade.` <!-- TODO(sunset-2026-12-31): this row goes; successor none --> |

---

## Request Schema

### Server selection

Call the endpoint for the region you want; there is no routing parameter. See
[Regions](api_trufo.md#regions).

```python
from trufo.api.endpoints import TRUFO_API_URL_EUROPE

signed_bytes = sign_c2pa(api_key, media_bytes, trufo_api_url=TRUFO_API_URL_EUROPE)
```

Organizations with a dedicated API pass its host explicitly via `trufo_api_url`.

### Supported media types

See [Media format support](media_format_support.md) for C2PA generation and
validation, watermark embedding and recovery, MIME detection, and subformat
restrictions. Format eligibility is separate from [execution mode](#tasks).

### `actions`

Ordered `[name, params]` pairs. Each media-transforming action feeds the next.

| Action | Params | Description |
| ------ | ------ | ----------- |
| `"transcode"` | `{"target_mime_type": "<mime>"}` | Convert to another format in the same media class |
| `"watermark"` | `{"wid_allocation_mode": "<wid_allocation_mode>", "effort_policy": "<effort_policy>"}` | Embed a Trufo watermark (off by default) |
| `"publish"` | `{}` | Mark for final distribution |
| `"redact"` | `{"label": "<label>", "reason": "<reason>"}` | Remove an assertion from the input's history |

#### `transcode`

Converts within a media class; cross-class conversion is rejected. The input must
already carry a C2PA manifest. Targets: `image/jpeg`, `image/png`, `image/webp`,
`image/avif`, `image/tiff`, `image/gif`, `audio/flac`, `audio/wav`, `audio/mp4`,
`audio/mpeg`, `video/mp4`, `video/quicktime`. An animated GIF, PNG, WebP or AVIF
keeps every frame, so its target must be `image/gif`, `image/png`, `image/webp`
or `image/avif`; it may hold up to 10,000 frames and 400 megapixels across
frames.

#### `watermark`

Embeds an imperceptible Trufo Pawprint watermark that carries a watermark ID.
**Off unless requested.** At most one watermark action per request.

| Param | Type | Description |
| ----- | ---- | ----------- |
| `wid_allocation_mode` | string | `"per_embed"` (default) or `"per_ai_system"`, below; `"per_asset"` is unsupported (HTTP 501) |
| `effort_policy` | string | Failure tolerance, below; `"require"` for a bare action. `effort` is a deprecated alias (a warning is returned; providing both is an error) |
| `mode` | string | Deprecated, below <!-- TODO(sunset-2027-01-31): this row goes; successor wid_allocation_mode --> |

- `"per_embed"`: a new watermark ID for this embed, which identifies one content
  record. The manifest declares it by a `c2pa.watermarked.bound` action and a
  `c2pa.soft-binding` assertion with algorithm `ai.trufo.pawprint.watermark`.
- `"per_ai_system"`: the watermark ID of the AI system named by the request's
  [`ai_system`](#ai_system) entry, for the entry's `ai_involvement`; no new ID is
  issued. The manifest records a `c2pa.watermarked.unbound` action and no soft
  binding.

Both work the same in Cloud and Local mode. See
[watermark billing](#watermark-billing); to watermark media you sign yourself,
see [Standalone Binding](#standalone-binding).

| `effort_policy` | Unsupported format | Runtime failure |
| --------------- | ------------------ | --------------- |
| `"require"` (default for a bare action) | Error | Error |
| `"require_if_supported"` | Signs unwatermarked, with a warning | Error |
| `"best_effort"` | Signs unwatermarked, with a warning | Signs unwatermarked, with a warning |

Format eligibility and restrictions are listed in
[Media format support](media_format_support.md). For examples, see the
[watermarking quickstart](../quickstart/6_watermarking.md).

**Errors:**

| When | Status | `detail` |
| ---- | ------ | -------- |
| `"per_ai_system"` without an `ai_system` entry | 400 | `The watermark's wid_allocation_mode 'per_ai_system' requires an 'ai_system' assertion.` |
| `"per_asset"` | 501 | `Per-asset watermark ID allocation is not supported.` |

<!-- TODO(sunset-2027-01-31): the deprecated mode paragraph and its two tables go; successor wid_allocation_mode -->

**Deprecated `mode`.** Until 2027-01-31T00:00:00+00:00, `mode` `"provenance"`
means `"per_embed"`, and the response's `warnings` (a task's result included)
carry one of these notices; from that instant, `mode` is refused. In Local mode,
the notices and the refusal apply only with trufo-provenance 2.2.0 or later.

**Notices:**

| When | Text |
| ---- | ---- |
| `mode` in a request from trufo-py older than 2.2 | `trufo-py <version> sends the deprecated watermark 'mode' parameter, which will stop working after 2027-01-31T00:00:00+00:00. Please upgrade trufo-py.` |
| `mode` sent by any other caller | `The watermark 'mode' parameter is deprecated and will stop working after 2027-01-31T00:00:00+00:00. Please use 'wid_allocation_mode' ('per_embed' replaces 'provenance').` |

**Errors:**

| When | Status | `detail` |
| ---- | ------ | -------- |
| `mode`, from 2027-01-31T00:00:00+00:00 | 400 | `UnsupportedParameter: the watermark 'mode' parameter is no longer supported (expired 2027-01-31T00:00:00+00:00). Please use 'wid_allocation_mode'.` |
| Both `mode` and `wid_allocation_mode` | 400 | `Provide the watermark 'wid_allocation_mode' parameter or the deprecated 'mode', not both.` |
| `mode` `"compliance"` | 501 | `Compliance watermarking is not supported.` |

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

Ordered `[name, params]` pairs. Assertions are gathered unless their documented
schema fixes or permits created placement. Created declarations require an
authorized branded generator product (`branded_gp_id`), limited to the source
types the product is approved for; without one, the only created declarations
are an [`ai_system`](#ai_system) entry's source-type labels. A created C2PA action requires
a `digitalSourceType`, except `c2pa.converted`, `c2pa.edited.metadata`,
`c2pa.enhanced`, `c2pa.opened`, `c2pa.placed`, `c2pa.published`,
`c2pa.redacted`, `c2pa.repackaged`, `c2pa.resized.proportional`,
`c2pa.transcoded`, `c2pa.watermarked`, `c2pa.watermarked.bound`, and
`c2pa.watermarked.unbound`.

| Assertion | Params | C2PA label |
| --------- | ------ | ---------- |
| `"ai_system"` | `{"ai_system_id": "<id>", "ai_involvement": "ai_generated"}` | `c2pa.actions` (`c2pa.created`, or `c2pa.opened` with a `c2pa.ingredient.v3` parent); `c2pa.ai-disclosure` when the AI system has one |
| `"ai_disclosure"` **(deprecated)** | `{"ai_disclosure_id": "<id>", "set_source_type": false}` | `c2pa.ai-disclosure` <!-- TODO(sunset-2027-01-31): this row goes; successor the ai_system row --> |
| `"cawg_metadata"` | `{"assertion": {…}}` | `cawg.metadata` |
| `"cawg_training"` | `{"assertion": {…}}` | `cawg.training-mining` |
| `"cawg_identity"` | `{"cawg_identity_id": "<id>"}` | `cawg.identity` |
| `"custom"` | `{"label": "<reverse-dns>", "assertion": {…}}` | Your label |
| `"ingredient"` | `{"relationship": "<rel>", …}` | `c2pa.ingredient.v3` |
| `"creation"` | `{"digitalSourceType": "<IPTC URI>", "softwareAgent": {…}}` | `c2pa.actions` (`c2pa.created`) |

#### `ai_system`

Names the [registered AI system](#post-ai-systemadd) that generates or modifies
the content:

```python
["ai_system", {"ai_system_id": "aisys_…", "ai_involvement": "ai_generated"}]
```

<!-- TODO(sunset-2027-01-31): "ai_disclosure or" goes from the next paragraph; successor none -->

`ai_involvement` is one of the AI system's `ai_involvement_modes`. A request
carries at most one `ai_system` entry, and no `ai_disclosure` or `creation` entry
with it.

An input without a C2PA manifest is labeled by the first of these that applies:

- Branded generator product (`branded_gp_id` set): signed as your branded
  generator product.
- Trufo AI Labeling Service (first-party AI system): signed with a `c2pa.created`
  action (`digitalSourceType = trainedAlgorithmicMedia`) whose software agent is
  the AI system.
- Declared AI ingredient (not first-party): the input is recorded as an
  AI-generated parent ingredient (`digitalSourceType = trainedAlgorithmicMedia`)
  and opened by your organization (`c2pa.opened`). This is not generally
  sufficient for interoperable AI disclosures.

Signing AI-modified content (`ai_modified`) requires a branded generator product.
A branded request writes the same `c2pa.created` action, with
`compositeWithTrainedAlgorithmicMedia` for `ai_modified`.

The recommended `c2pa.ai-disclosure` assertion comes from the optional model
disclosure (`c2pa_ai_disclosure`). It is gathered, never created.

If the input already carries a C2PA manifest, Trufo keeps it and declares no new
source type. If that manifest says camera-captured or human-created, the input is
rejected. This is the default
[`signed_input_policy`](#signed-inputs-and-ingredients), `auto`; with `keep`,
that input is kept too, and no AI source type is declared for it.

Under `auto`, a `redact` or `transcode` action also keeps such an input;
[Signed inputs and ingredients](#signed-inputs-and-ingredients) lists every case.

The test host writes the same labels, with the test certificate.

**Errors:**

| When | Status | `detail` |
| ---- | ------ | -------- |
| Local mode, an engine too old for the entry | 400 | `UnsupportedSDKVersion: the 'ai_system' assertion requires trufo-provenance 2.2.0 or later. Please upgrade.` |
| Two `ai_system` entries | 400 | `At most one 'ai_system' assertion is allowed per request.` |
| With the deprecated `ai_disclosure` entry | 400 | `The 'ai_system' assertion cannot be combined with the deprecated 'ai_disclosure' assertion; remove 'ai_disclosure'.` <!-- TODO(sunset-2027-01-31): this row goes; successor none --> |
| With a `creation` entry | 400 | `The 'ai_system' assertion cannot be combined with a 'creation' assertion; remove 'creation'.` |
| `ai_system_id` or `ai_involvement` missing | 400 | `The 'ai_system' assertion requires 'ai_system_id' and 'ai_involvement'.` |
| Extra keys in the entry | 400 | `The 'ai_system' assertion accepts only 'ai_system_id' and 'ai_involvement'; the software agent and source type come from the AI system's registration.` |
| `ai_involvement` unknown | 400 | `ai_involvement must be 'ai_generated' or 'ai_modified'.` |
| An unknown or another organization's `ai_system_id` | 404 | `AISystemNotFound` |
| The AI system is inactive | 400 | `AISystemInactive: AI system '<ai_system_id>' is inactive. Use an active AI system (see /ai-system/list).` |
| `ai_involvement` not in the system's modes | 400 | `ai_involvement '<value>' is not in the AI system's ai_involvement_modes.` |
| `ai_modified` without `branded_gp_id` | 400 | `ai_involvement 'ai_modified' requires a branded generator product (branded_gp_id).` |
| With `branded_gp_id`, the product is not approved for the entry's source type | 403 | `C2PACreatedUserAssertionsNotAuthorized: the digitalSourceType <uri> is not approved for this branded generator product.` |
| A signed input whose source class is `camera_captured` or `human_created`, under the default [`signed_input_policy`](#signed-inputs-and-ingredients) (`auto`), without a `redact` or `transcode` action | 400 | `The input carries a C2PA manifest whose source class is '<class>', which conflicts with ai_involvement '<ai_involvement>'.` |
| A `parentOf` ingredient, with `branded_gp_id`, on an input without a C2PA manifest (the entry's `c2pa.created` takes no parent) | 400 | `The creation assertion cannot be combined with a parentOf ingredient.` |

In Local mode with the Python SDK, the last two are raised by the call.

<!-- TODO(sunset-2027-01-31): this entry goes; successor ai_system -->

#### `ai_disclosure`

Deprecated: use [`ai_system`](#ai_system); see
[Moving From `ai_disclosure`](../quickstart/3_ai_labeling.md#moving-from-ai_disclosure).
Until 2027-01-31T00:00:00+00:00, the entry adds a `c2pa.ai-disclosure` assertion:
the [registered](#post-c2paai-disclosureadd) body whose `ai_disclosure_id` you
pass, or `{"modelType": "c2pa.types.model"}` when you pass none. With
`set_source_type: true`, an input without a C2PA manifest is also declared
`trainedAlgorithmicMedia`: by a `c2pa.created` action for a first-party
registration, otherwise on the input ingredient.

Sign responses that use the entry carry the `Deprecation` and `Sunset` headers
([Deprecations](api_trufo.md#deprecations)) and the notice below in `warnings`
(for a TASK, in the task result's `warnings`); from 2027-01-31T00:00:00+00:00,
the entry is refused.

**Notices:**

| When | Text |
| ---- | ---- |
| A sign request uses the entry | `The 'ai_disclosure' assertion is deprecated and will stop working after 2027-01-31T00:00:00+00:00. Please use the 'ai_system' assertion with an AI system registered at /ai-system/add.` |

**Errors:**

| When | Status | `detail` |
| ---- | ------ | -------- |
| The entry, from 2027-01-31T00:00:00+00:00 | 400 | `UnsupportedAssertion: the 'ai_disclosure' assertion is no longer supported (expired 2027-01-31T00:00:00+00:00). Please use the 'ai_system' assertion.` |

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

Declares a prior or contributing asset. Ingredients are your workflow's account
of the asset, not a Trufo attestation.

| Param | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `relationship` | string | Yes | `inputTo`, `componentOf`, or `parentOf` (the asset before the supplied input's edits) |
| `title` | string | No | The ingredient title (`dc:title`). When unset: the media's manifest title, if it exists; otherwise, `ingredient_{n}.{ext}` (media-less entries: `ingredient_{n}`), where `n` counts the request's `ingredient` entries from 0. Messages use `title`, else `ingredient_{n}`. |
| `data_types` | list | No | `[{"type": "c2pa.types.<kind>", "version": "…"}]` |
| `digital_source_type` | string | No | The IPTC `trainedAlgorithmicMedia` or `compositeWithTrainedAlgorithmicMedia` URI; not with `media` that carries a C2PA manifest |
| `media` | string | For `parentOf` | base64 bytes, in a format with **Yes** under C2PA validate in [Media format support](media_format_support.md); declare other formats with `format` (`componentOf` or `inputTo`). A `componentOf` entry needs `media` or `format`; an `inputTo` entry, neither |
| `format` | string | No | The media type of a declared ingredient (one without `media`), such as `video/mp4`; not with `media` |
| `placement` | string | No | `gathered` (default) or `created`, on a request authorized for created assertions; `parentOf` is always created. A declared ingredient is always gathered; created placement for it is refused for now and may be supported later. |
| `action_history` | list | No | Actions between a `parentOf` source and the supplied input; entries may independently set `placement`, `digitalSourceType` and `description`. An entry's action is a C2PA action or a custom one in a domain your organization has validated (for example `com.example.upscaled`) |

- Sent (`media`): a readable C2PA history is always kept with the ingredient,
  validation failures included;
  [`signed_ingredient_policy`](#signed-inputs-and-ingredients) sets what happens to
  C2PA data Trufo cannot read. Media without a C2PA manifest gets a thumbnail when
  it is an image.
- Declared (no `media`): no history is looked for; validators report its
  provenance as unknown.

At most one `parentOf` ingredient is allowed, it requires media, and it cannot be
combined with `creation`. A kept [signed input](#signed-inputs-and-ingredients) is
already the parent, so it cannot take a `creation` entry or a `parentOf` you send.

**Errors:**

| When | Status | `detail` |
| ---- | ------ | -------- |
| An ingredient sent as `media` in a format without **Yes** under C2PA validate | 400 | `Ingredient '<title>': Unsupported Format Error: <mime> is not supported in the C2PA validation setting. A componentOf or inputTo ingredient in this format can be declared with its 'format' and no 'media'. If you would like to request support, contact support@trufo.ai; feel free to provide a sample file and the use case context.` |
| A declared ingredient sets `placement` to `created` | 400 | `A declared ingredient (one without 'media') is always gathered; omit 'placement'. Setting 'placement' to 'created' requires sending the file as 'media', in a format Trufo can read, on a request authorized for created assertions. If you would like to request created placement for a format Trufo cannot read, contact support@trufo.ai; feel free to provide a sample file and the use case context.` |
| An ingredient's `format` is not a media type | 400 | `The ingredient 'format' must be a media type such as 'video/mp4'.` |
| A `componentOf` ingredient has neither `media` nor `format` | 400 | `The componentOf relationship requires ingredient 'media' or 'format'.` |
| An ingredient has both `media` and `format` | 400 | `Provide the ingredient 'media' or 'format', not both.` |
| A `parentOf` ingredient without `branded_gp_id` | 403 | `C2PACreatedUserAssertionsNotAuthorized: created user assertions are not authorized.` |
| A `parentOf` ingredient with `branded_gp_id` but no `media` | 400 | `The parentOf relationship requires ingredient 'media'.` |
| `digital_source_type` with `media` that carries a C2PA manifest | 400 | `The ingredient 'digital_source_type' cannot be combined with media that carries a C2PA manifest (mutually exclusive per the spec).` |

In the format refusal, `<mime>` reads `Unknown format` when the media type cannot
be detected.

#### `creation`

Declares that the supplied unsigned asset was created by a registered software
agent. It emits exactly one leading `c2pa.created` action and is always created:

```python
["creation", {
    "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    "softwareAgent": {"software_agent_id": "swagent_..."},
    "when": "2026-08-22T12:00:00Z",
}]
```

`when` is optional. The server resolves the software-agent id to the registered
agent record. Creation, external parents, action histories, and any created
placement default `allActionsIncluded` to false; explicitly asserting true is a
separately authorized completeness claim.

### Signed inputs and ingredients

Two fields, each `auto` (the default) or `keep`, set what Trufo does with a file
that already carries C2PA data: `signed_input_policy` for the input file, and
`signed_ingredient_policy` for every [`ingredient`](#ingredient) sent with `media`,
a `parentOf` included. Cloud and Local mode apply them alike. The Python SDK sends a
value only when you set one, as `SignedInputPolicy` or `SignedIngredientPolicy` from
`trufo.c2pa`, or as a string.

- **Valid**: the manifest is well-formed, and its signature, hashes and time stamp
  validate.
- **Trusted**: valid, and its signer is on the trust lists Trufo checks.
- **Cannot read**: no manifest can be read from the C2PA data.

| C2PA data in the file | `auto` (default) | `keep` |
| --------------------- | ---------------- | ------ |
| A readable manifest, valid or not | Kept, with its validation results recorded, unless the source-class check below refuses an input | Kept, with its validation results recorded |
| A manifest only referenced by URL | Refused (400): removing the data leaves the reference | Refused (400) |
| Other data Trufo cannot read, such as a malformed manifest store | Removed: an input is signed as if it carried none, and an ingredient is added without its history. A `redact` or `transcode` action on that input is then refused | Refused (400) |

A kept input becomes the `parentOf` ingredient, opened with `c2pa.opened`, and gets
no new `digitalSourceType`; [`redact`](#redact) removes assertions from its history.

**Source class.** Under `auto`, with an `ai_system` entry and no `redact` or
`transcode` action, Trufo refuses an input whose source class is `camera_captured`
or `human_created` (the 400 is listed under [`ai_system`](#ai_system)), and keeps
any other with a notice naming its class. `keep` skips this check. To find the
class, Trufo walks back from the active manifest through `parentOf` ingredients, by
each manifest's first action:

- `c2pa.created`: its `digitalSourceType` is the origin.
- `c2pa.opened`: go on to the parent's manifest or, for a parent without one, take
  that ingredient's `digitalSourceType`.
- Anything else: the origin is unknown.

Any action on the walk other than `c2pa.created` that carries
`trainedAlgorithmicMedia` or `compositeWithTrainedAlgorithmicMedia` is an AI edit.
Validation results and gathered assertions, such as `c2pa.ai-disclosure`, do not
affect the class.

| Origin | AI edit on the walk | Source class |
| ------ | ------------------- | ------------ |
| `trainedAlgorithmicMedia` | Any | `ai_generated` |
| `compositeWithTrainedAlgorithmicMedia` | Any | `ai_modified` |
| Any other (camera and human included), or unknown | Yes | `ai_modified` |
| `digitalCapture`, `computationalCapture`, `compositeCapture`, `negativeFilm`, `positiveFilm`, `print` | No | `camera_captured` |
| `digitalCreation`, `humanEdits` | No | `human_created` |
| Any other source type | No | `other` |
| Unknown | No | `none` |

**Notices.** Every notice whose When applies is sent, but a source-class notice
replaces the not-validated or untrusted one.

| When | Text |
| ---- | ---- |
| A kept input's manifest did not validate | `The input's C2PA manifest did not validate; Trufo kept it, and its validation failures are recorded in the new manifest.` |
| A kept input's manifest is valid but untrusted | `The input's C2PA manifest is valid but untrusted: its signer is not on the trust lists Trufo checks. Trufo kept it.` |
| `auto`, an `ai_system` entry and no `redact` or `transcode` action: the input's manifest did not validate | `The input already contains a C2PA manifest that did not validate, so (per auto mode) it is kept and a c2pa.opened action was added in lieu of a new c2pa.created with digitalSourceType set to trainedAlgorithmicMedia (or equivalent). Its validation failures are recorded in the new manifest. Please note that the existing C2PA manifest will resolve to a source classification of '<class>'.` |
| `auto`, an `ai_system` entry and no `redact` or `transcode` action: the input's manifest is valid | `The input already contains a valid <and trusted / but untrusted> C2PA manifest, so (per auto mode) it is kept and a c2pa.opened action was added in lieu of a new c2pa.created with digitalSourceType set to trainedAlgorithmicMedia (or equivalent). Please note that the existing C2PA manifest will resolve to a source classification of '<class>'.` |
| `auto`, an `ai_system` entry and a `redact` or `transcode` action | `The input already carries a C2PA manifest, so Trufo kept it for the requested <action> action; no new source type was declared.` |
| `keep` and an `ai_system` entry | `signed_input_policy is 'keep', so Trufo kept the input's C2PA manifest; no new source type was declared.` |
| `auto`: the input's C2PA data cannot be read and is removed | `The input carries C2PA data that Trufo cannot read, so (per auto mode) Trufo removed that data and signed the input as if it carried no C2PA data.` |
| An ingredient's manifest did not validate | `The C2PA manifest of ingredient '<title>' did not validate; Trufo kept it with the ingredient, and its validation failures are recorded in the new manifest.` |
| An ingredient's manifest is valid but untrusted | `The C2PA manifest of ingredient '<title>' is valid but untrusted: its signer is not on the trust lists Trufo checks. Trufo kept it with the ingredient.` |
| `auto`: an ingredient's C2PA data cannot be read and is removed | `Ingredient '<title>' carries C2PA data that Trufo cannot read, so (per auto mode) Trufo added the ingredient without its C2PA history; validators will report its provenance as unknown.` |

**Errors:**

| When | Status | `detail` |
| ---- | ------ | -------- |
| The input's C2PA data cannot be read: under `keep`, or under either value for a manifest only referenced by URL | 400 | `The input carries C2PA data that Trufo cannot read, so Trufo cannot keep or validate it. Please send a copy with intact C2PA data, or contact support@trufo.ai.` |
| The same, for an ingredient sent as `media` | 400 | `Ingredient '<title>' carries C2PA data that Trufo cannot read, so Trufo cannot validate it. Please send a copy with intact C2PA data, or contact support@trufo.ai.` |
| Local mode: the request sets `signed_input_policy` and the engine is older than trufo-provenance 2.2.0 | 400 | `UnsupportedSDKVersion: signed_input_policy requires trufo-provenance 2.2.0 or later. Please upgrade.` |
| Local mode: the request sets `signed_ingredient_policy` and the engine is older than trufo-provenance 2.2.0 | 400 | `UnsupportedSDKVersion: signed_ingredient_policy requires trufo-provenance 2.2.0 or later. Please upgrade.` |

---

## Standalone Binding

Bind embeds a Trufo watermark **without** Trufo signing: you sign the
watermarked media with your own certificate and complete the record with
`/bind/commit`, which maps the mark to your manifest for soft-binding
resolution. Two routes share the commit (see the routes table in the
[watermarking quickstart](../quickstart/6_watermarking.md#routes)): **Watermarking,
Cloud**, where `/bind/watermark` embeds the mark on Trufo's servers, and
**Watermarking, Local**, where `/bind/reserve` issues the watermark id and you embed
with the local engine.
A per-AI-system bind (`wid_allocation_mode` `"per_ai_system"`, with `ai_system_id`
and `ai_involvement`) embeds the AI system's watermark ID on either route. It is
not a C2PA soft binding, and there is nothing to commit.

Production requires a `watermark-prod` key, an active C2PA Signing or Watermark
API plan, and completed organization validation.
SDK: `bind_watermark()`, `bind_reserve()`, `watermark_media()`, `bind_commit()`
(`_test` variants for the test host).

### Watermark billing

Watermarking on every route, including C2PA signing with a watermark action,
bills watermark ID units: 10 per new ID, 1 per embed, and 1 per active ID per
year. A per-embed mark is a new ID plus one embed; a per-AI-system mark is one
embed of the AI system's ID. Registering an AI system issues one new ID per type
of AI involvement. An ID is active while it resolves: a per-embed ID from its
committed record until you deactivate it, an AI system's IDs from registration.
An AI system registered with a test key bills no new or active IDs.
Watermarking, Cloud also bills the media and manifest bytes as data processing;
Watermarking, Local bills the manifest bytes. Video watermarked on Trufo's servers
also bills video compute at $0.30/GB, measured by input file size.

### `POST /bind/watermark`

**Auth:** API key with the `watermark-prod` scope (`watermark-test` on the test host).

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `media_input` | string | Yes\* | base64-encoded media to watermark |
| `media_input_s3` | string | Yes\* | Trufo-issued upload reference from [`/io/get-s3-upload-url`](#post-ioget-s3-upload-url); TASK only |
| `execution_mode` | string | No | `request` (default) or `task`; `stream` is unsupported |
| `wid_allocation_mode` | string | No | How the watermark ID is allocated: `per_embed` (a new ID for this embed) or `per_ai_system` (the registered AI system's ID for `ai_involvement`); `per_asset` is reserved and unsupported. When omitted, `per_embed` applies. |
| `ai_system_id` | string | With `per_ai_system` | The registered AI system whose watermark ID is used. Required with `wid_allocation_mode` `per_ai_system`, and accepted only with it. |
| `ai_involvement` | string | With `per_ai_system` | `ai_generated` or `ai_modified`, one of the AI system's `ai_involvement_modes`. Required with `wid_allocation_mode` `per_ai_system`, and accepted only with it. |
| `mode` | string | No | Deprecated: use `wid_allocation_mode` (`per_embed` replaces `provenance`). `compliance` is reserved and unsupported. <!-- TODO(sunset-2027-01-31): this row goes; successor wid_allocation_mode --> |

\* Provide exactly one: bytes for REQUEST, an upload reference for TASK. TASK runs
on the production hosts only and returns 202; see [Tasks](#tasks).

**Response (200):**

| Field | Type | Description |
| ----- | ---- | ----------- |
| `media_output` | string | base64-encoded watermarked media |
| `wid` | string | The embedded watermark id |
| `cid` | string or null | Record id, for `/bind/commit` on a per-embed bind; null for a per-AI-system bind on the test host |
| `warnings` | list | Deprecation warnings, empty when none. |

Bind has no effort tiers: the watermark is always required, and an
unsupported format is an error; see [Media format support](media_format_support.md).
Unlike in an [`ai_system`](#ai_system) entry, `ai_modified` needs no branded
generator product on a bind.

**Errors:**

| When | Status | `detail` |
| ---- | ------ | -------- |
| `wid_allocation_mode` outside `per_embed`, `per_ai_system` and `per_asset` | 422 | *(field list)* |
| `ai_system_id` or `ai_involvement` without `per_ai_system` | 400 | `'ai_system_id' and 'ai_involvement' apply only with wid_allocation_mode 'per_ai_system'.` |
| `per_ai_system` without `ai_system_id` or `ai_involvement` | 400 | `wid_allocation_mode 'per_ai_system' requires 'ai_system_id' and 'ai_involvement'.` |
| `ai_involvement` unknown | 400 | `ai_involvement must be 'ai_generated' or 'ai_modified'.` |
| An unknown or another organization's `ai_system_id` | 404 | `AISystemNotFound` |
| The AI system is inactive | 400 | `AISystemInactive: AI system '<ai_system_id>' is inactive. Use an active AI system (see /ai-system/list).` |
| `ai_involvement` not in the system's modes | 400 | `ai_involvement '<value>' is not in the AI system's ai_involvement_modes.` |

The `per_asset` and deprecated `mode` refusals are listed under
[`watermark`](#watermark).

### `POST /bind/reserve`

**Auth:** API key with the `watermark-prod` scope (`watermark-test` on the test host).

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `mime_type` | string | Yes | MIME type of the media you will watermark locally (an encode-supported format) |
| `wid_allocation_mode`, `ai_system_id`, `ai_involvement` | string | As in `/bind/watermark` | As in [`/bind/watermark`](#post-bindwatermark), with the same errors |

**Response (200):**

| Field | Type | Description |
| ----- | ---- | ----------- |
| `cid` | string | Record id, for `/bind/commit` on a per-embed bind |
| `wid_package` | object | `{ "wid", "expires_at" }` — the watermark ID to embed with the engine; a per-embed reservation is valid for 24 hours (1 hour on the test host) |

A per-AI-system bind returns the AI system's watermark ID in the same
`wid_package`; on the test host, its `cid` is not a record. A per-AI-system
reservation bills its embed when issued and is valid for 1 hour.

### `POST /bind/commit`

**Auth:** API key with the `watermark-prod` scope (`watermark-test` on the test host).

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `cid` | string | Yes | Record id from `/bind/watermark` or `/bind/reserve` |
| `wid` | string | Yes | The watermark id issued with that record |
| `manifest` | string | One of | base64-encoded C2PA manifest store declaring the mark |
| `manifest_id` | string | One of | The manifest's id (its urn) when the manifest lives in your own store; requires `manifest_endpoint`, and the declaration is then your responsibility |
| `manifest_endpoint` | string | No | Base URI (`https://…`) of your own C2PA manifest store hosting this manifest at `{manifest_endpoint}/manifests/{manifestId}`; omit to have Trufo host it |

With `manifest`, the store must declare the mark: a `c2pa.soft-binding`
assertion with algorithm `ai.trufo.pawprint.watermark` and the record's
watermark id as its block value, paired with a `c2pa.watermarked.bound`
action, per the C2PA specification. The manifest is checked for this
declaration, not for trust status — sign with whatever certificate you use —
and its id is derived from the bytes. When `manifest_endpoint` is given, Trufo
keeps no copy and soft-binding resolution refers validators to your store;
otherwise Trufo stores and serves the manifest. An identical retry of a
completed commit succeeds; a different one is refused.

Commit is for per-embed binds only: committing a per-AI-system bind with the AI
system's watermark ID is refused with 400 `InvalidWid`; on the test host, a
per-AI-system `/bind/reserve` `cid` gets 404.

**Response (200):** `cid`, `wid`.

**Errors:**

| Status | Meaning |
| ------ | ------- |
| 400 | Malformed `wid`, no parseable manifest, `manifest_id` without an endpoint, or the manifest does not declare the record's mark (the record stays incomplete — fix and resubmit). `/bind/watermark` also rejects an unsupported media format |
| 404 | Unknown `cid`, a record not opened by a bind call, or a `wid` that is not a live reservation of yours for the record's route |
| 409 | The record was already completed with a different manifest |

---

## Watermark Recovery

### `POST /content/recover`

Decode a Trufo watermark and return its provenance — useful after a manifest has
been stripped.

**Auth:** API key with the `content-recover-prod` scope on the production hosts, or
`content-recover-test` on the test host (`test.api.trufo.ai`). Each key works only
against its own host tier. Production requires an active C2PA Signing or Watermark
API plan and bills the input bytes and returned manifest bytes per call as data
processing.

| Field | Type | Required |
| ----- | ---- | -------- |
| `media_input` | string | Yes — base64-encoded media |
| `parse_manifest_json` | bool | No (default `false`) — also return the stored manifest parsed as JSON |

**Response (200):** The decoded wid and detection confidence, plus what the wid
resolves to by its allocation mode: the stored manifest bytes for a `per_embed`
wid, or the AI system's public information for a `per_ai_system` wid. `oid` is set
only when the mark belongs to the caller's org.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `detected` | bool | Whether a Trufo watermark was found |
| `wid` | string or null | The decoded watermark id |
| `confidence` | float or null | Detection strength in (0, 1] — how strongly the signal was recovered, not a probability of correctness |
| `wid_allocation_mode` | string or null | How the watermark ID was allocated: `per_embed` or `per_ai_system`. |
| `ai_involvement` | string or null | `ai_generated` or `ai_modified`, for a `per_ai_system` watermark ID. |
| `ai_system` | object or null | The AI system's public information, for a `per_ai_system` watermark ID. |
| `manifest_bytes` | string or null | The stored C2PA manifest store, base64-encoded, when available for that record; validate it against your own copy of the media |
| `manifest_json` | object or null | The same manifest parsed as JSON, only when `parse_manifest_json` was set; a convenience for callers without a local C2PA engine, not a validation result |
| `status` | string or null | Whether the record's watermark ID is active (`active` \| `inactive`); present only on your own records. |
| `oid` | string or null | Your organization ID, present only when the mark is your organization's |

`ai_system`, the AI system a `per_ai_system` watermark ID identifies:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `name` | string | The AI system's name; with `version`, its C2PA `softwareAgent`. |
| `version` | string | The AI system's version; a new version is a new registration. |
| `c2pa_ai_disclosure` | object or null | A `c2pa.ai-disclosure` body (C2PA 2.4 § 18.28) describing the underlying model. |
| `org_name` | string or null | The organization's validated legal name, while its OV is active. |
| `ai_system_id` | string or null | Registration identifier; present only on your own AI systems. |
| `status` | string or null | The AI system's status (`active` \| `inactive`); present only on your own AI systems. |

What a watermark ID resolves to:

- A per-embed ID: its record's stored manifest, to any recover-key holder while the
  record is [active](#post-contentstatus), and always to your own organization.
- A per-AI-system ID: the AI system's public information, to any recover-key holder,
  even while the AI system is inactive. It is not a C2PA soft binding, so the C2PA
  soft-binding resolution API does not serve it.
- Any other ID: detection only.

Each host resolves only its own IDs: the test host resolves test IDs of both kinds.
Recovery has its own format eligibility and restrictions; see
[Media format support](media_format_support.md).

**Errors:**

| Status | Meaning |
| ------ | ------- |
| 400 | `UndecodableMedia`: the input could not be parsed as image, video, or audio |

---

## Content Records

Every production sign or bind creates a content record. A record with a
watermark id and a manifest id is what public soft-binding resolution serves; it
counts as one active ID ([watermark billing](#watermark-billing)) until you
deactivate it. Active IDs are counted once each UTC day.
The owner can look records up, list them, and switch each one off and on.
Production hosts only. SDK: `get_content()`, `list_content()`,
`set_content_status()`.

A per-AI-system embed's record carries the AI system's watermark ID as
`ai_system_wid` instead of `wid`. `/content/list` lists these records, except
under a `status` filter; `/content/get` does not find them by the AI system's
watermark ID, and they cannot be switched off. The AI system's IDs keep resolving,
even while the AI system is [inactive](#post-ai-systemstatus).

Unlike `/content/recover`, which decodes media and is metered, these take an
identifier or filters, touch only your own records, and are not metered.

**Auth (all three):** API key with the `c2pa-sign-prod` or `watermark-prod`
scope, or a dashboard session. No active plan is required, so a lapsed
subscriber can still deactivate its marks.

**The record:** `cid` (record id, returned by every sign and bind call), `wid`
(once the mark is embedded and, on the bind routes, committed), `ai_system_wid`
(watermark id of the AI system the mark identifies, shared by every item it
marks; set instead of `wid`), `mid` (once a manifest is captured), `status`
(`active` or `inactive`; null without a `wid`), `origin` (the route; see
[Routes](#routes)), `mime_type`, `create_ts`, `commit_ts`. Fields only ever gain
members.

### `POST /content/get`

Exactly one of `cid`, `wid` (current `v1.` or legacy `image.` / `audio.` form), `mid`. **Response (200):** the
record. **Errors:** 400 malformed `wid`; 404 when no record of yours matches;
422 when zero or several keys are given.

### `POST /content/list`

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `status` | string | No | `active` or `inactive` |
| `origin` | string | No | one route |
| `created_after` | string | No | RFC 3339; created at or after |
| `created_before` | string | No | RFC 3339; created before |
| `cursor` | string | No | Opaque; the `next_cursor` of the previous page |
| `limit` | int | No | 1 to 100 (default 50) |

**Response (200):** `items`, oldest first, and `next_cursor`. A short or empty
page is the last one, and `next_cursor` is then null; a full last page yields
one more, empty, page. The limit bounds one response.

### `POST /content/status`

Exactly one of `cid`, `wid`, `mid`, plus `status`: `inactive` withdraws the
record from public soft-binding resolution immediately and from active-ID
counting at the next daily count; `active` reverses both on the same timing.
Idempotent. Nothing is deleted and the signed asset is untouched. **Response (200):** the record after the
write. **Errors:** as `get`; 404 also for a record without a `wid`, such as a
per-AI-system one.

---

## AI Systems

Register an AI system once, then pass its `ai_system_id` when signing (an
[`ai_system`](#ai_system) entry) and watermarking. Its details cannot be changed after
registration: register each new version as a new AI system. Registrations are shared
between test and production signing. An AI system works on every regional endpoint
([Regions](api_trufo.md#regions)). Production hosts only.

**Auth (all three):** API key with the `c2pa-sign-prod` or `c2pa-sign-test` scope,
or an MFA-verified access token with the `c2pa_sign` permission. No plan is
required.

### `POST /ai-system/add`

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `name` | string | Yes | The AI system's name; with `version`, its C2PA `softwareAgent`. |
| `version` | string | Yes | The AI system's version; a new version is a new registration. |
| `ai_involvement_modes` | list of strings | Yes | Which of `ai_generated` and `ai_modified` the AI system supports (one or both). |
| `c2pa_first_party_attestable` | boolean | No | Default `false`. The organization operates the AI system and is accountable for its AI labels; requires the Created Assertion Acknowledgement. |
| `c2pa_ai_disclosure` | object | No | A `c2pa.ai-disclosure` body (C2PA 2.4 § 18.28) describing the underlying model. Without it, signs that use the AI system carry no `c2pa.ai-disclosure` assertion. |
| `nickname` | string | No | Display label only. |

For a first-party AI system (`c2pa_first_party_attestable: true`), an organization
owner or admin must first accept the Created Assertion Acknowledgement in
[Organization Settings → Agreements](https://app.trufo.ai/settings/org#agreements);
an automated agent may not accept it.

Registration assigns the AI system one production and one test watermark ID for
each value in `ai_involvement_modes`; see [watermark billing](#watermark-billing).
Its name, version, model disclosure and your organization's validated legal name
can appear publicly in signed content and watermark lookups.

**Response (201):** `{"ai_system_id": "aisys_…"}`.

**Errors:**

| Status | `detail` | Meaning |
| ------ | -------- | ------- |
| 400 | *(message)* | An invalid `c2pa_ai_disclosure` body; the detail explains why |
| 403 | `The Created Assertion Acknowledgement has not been accepted. It is a legal agreement that must be accepted in the dashboard by an owner or admin authorized to accept it for your organization, at https://app.trufo.ai/settings/org#agreements; an automated agent may not accept it on your organization's behalf. Once it is accepted, register the AI system again.` | `c2pa_first_party_attestable` before the Created Assertion Acknowledgement is accepted |
| 422 | *(field list)* with `Value error, ai_involvement_modes must be one or both of 'ai_generated' and 'ai_modified'.` | `ai_involvement_modes` empty, repeated or unknown |

#### `c2pa_ai_disclosure`

| Field | Type | Required | Notes |
| ----- | ---- | -------- | ----- |
| `modelType` | string | Yes | One of the permitted C2PA model-type values, e.g. `c2pa.types.model`, `c2pa.types.model.pytorch`, `c2pa.types.model.huggingface.transformers` |
| `modelName` | string | No | Human-readable model name |
| `modelIdentifier` | string | No | Machine-readable identifier (e.g. a PURL) |
| `contentProfile` | object | No | Only `humanOversightLevel`: `fully_autonomous` (the model produced the asset without human direction), `prompt_guided` (a human directed the model but did not review the output), or `human_validated` (a human reviewed and accepted the output) |
| `scientificDomain` | string or list | No | Dotted domain codes, e.g. `cs.AI` |
| `metadata` | object | No | Free-form |

### `POST /ai-system/list`

**Request:** `{}`. **Response (200):** up to 1,000 `items[]` of
`{ai_system_id, name, version, ai_involvement_modes, c2pa_first_party_attestable, c2pa_ai_disclosure, nickname, status}`.
Newest first.

### `POST /ai-system/status`

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `ai_system_id` | string | Yes | Registration identifier. |
| `status` | string | Yes | `inactive` rejects new signs and embeds that use the AI system; `active` restores it. |

Idempotent; nothing is deleted. Content already marked with an inactive AI system
keeps resolving, and the AI system's watermark IDs keep counting as active IDs
([watermark billing](#watermark-billing)). **Response (200):** the AI system's list
entry after the write. **Errors:** 404 `AISystemNotFound` for an unknown or another
organization's `ai_system_id`.

---

## Assertion Records

Reusable bodies registered once and referenced by id when signing. Both groups
accept a `c2pa-sign-prod` or `c2pa-sign-test` key and infer the owning organization
from the credential.

<!-- TODO(sunset-2027-01-31): the two ai-disclosure sections go, and the intro then names the software-agent endpoints only; successor AI Systems -->

### `POST /c2pa/ai-disclosure/add`

Deprecated: use [`POST /ai-system/add`](#post-ai-systemadd). Every 201 carries the
`Deprecation`, `Sunset` and
`Link: <https://api.trufo.ai/ai-system/add>; rel="successor-version"` headers
([Deprecations](api_trufo.md#deprecations)). From 2027-01-31T00:00:00+00:00, the
endpoint answers 410 with the same headers.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `assertion` | object | Yes | A `c2pa.ai-disclosure` body (C2PA 2.4 §18.28) |
| `nickname` | string | No | Display label; never signed |
| `first_party_operated` | boolean | No | Default `false`. Declares that your organization operates the model; private registration metadata, not embedded in the manifest. |
| `software_agent_id` | string | When `first_party_operated` is `true` | Existing software-agent registration owned by your organization, identifying the generating application/service. |

First-party registration requires an authorized organization owner/admin to accept
the Created Assertion Acknowledgement in **Organization Settings → Agreements**. This
check applies to both API-key scopes because registrations are shared between
test and production. Acceptance is checked at registration, not again at signing.

**Response (201):** `ai_disclosure_id`, shaped `aidisc_<uuid>`.

**Errors:**

| Code | Meaning |
| ---- | ------- |
| 403 | First-party operation requested before the organization accepted the Created Assertion Acknowledgement. |
| 404 | The linked software agent does not exist, was deleted, or belongs to another organization. |
| 410 | From 2027-01-31T00:00:00+00:00: `POST /c2pa/ai-disclosure/add is no longer supported (expired 2027-01-31T00:00:00+00:00). Please use POST /ai-system/add.` |
| 422 | First-party operation was declared without a nonempty `software_agent_id`. |

`assertion` takes the same fields as [`c2pa_ai_disclosure`](#c2pa_ai_disclosure).

### `POST /c2pa/ai-disclosure/list`

Deprecated: use [`POST /ai-system/list`](#post-ai-systemlist). Every 200 carries
the `Deprecation`, `Sunset` and
`Link: <https://api.trufo.ai/ai-system/list>; rel="successor-version"` headers.
From 2027-01-31T00:00:00+00:00, the endpoint answers 410 with the same headers.
List your registered bodies before then to reuse one as an AI system's
[`c2pa_ai_disclosure`](#c2pa_ai_disclosure).

**Request:** `{}`. **Response (200):** `items[]` of
`{ai_disclosure_id, nickname, assertion, first_party_operated, software_agent_id}`.
Older registrations return `first_party_operated: false` and `software_agent_id: null`.

**Errors:**

| Code | Meaning |
| ---- | ------- |
| 410 | From 2027-01-31T00:00:00+00:00: `POST /c2pa/ai-disclosure/list is no longer supported (expired 2027-01-31T00:00:00+00:00). Please use POST /ai-system/list.` |

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
