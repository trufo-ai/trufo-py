# Signing API Reference

Normative specification for C2PA signing endpoints (`/c2pa/sign`), ephemeral S3 uploads (`/io/get-s3-upload-url`), asynchronous tasks (`GET /tasks/{task_id}`), Local mode behavior, `manifest_settings` wire JSON, and operational limits.

See [Platform API](platform-api.md) for hosts, auth headers, regions, and common errors, and [Actions and Assertions](actions-and-assertions.md) for `actions`, `assertions`, and `signed_input_policy`.

---

## Signing Modes and Routes

| Mode | Entry | Media reaches Trufo | Manifest built by | Signed by | `origin` |
| --- | --- | --- | --- | --- | --- |
| Cloud, direct (`REQUEST`) | `POST /c2pa/sign` (`media_input`) | Yes (base64 in JSON, ≤ 10 MB) | Trufo | Trufo | `c2pa_hosted` |
| Cloud, via S3 (`TASK`) | `/io/get-s3-upload-url` → PUT → `POST /c2pa/sign` (`media_input_s3`) | Yes (ephemeral S3) | Trufo | Trufo | `c2pa_hosted` |
| Local (Python SDK or Docker) | `sign_c2pa_local()` or `trufo-local` `POST /c2pa/sign` | **No** (original media stays local) | Local engine (`trufo-provenance`) | Trufo | `c2pa_distributed` |

**Automatic assertion:** Every manifest signed through Trufo includes `ai.trufo.identity` (`oid`, plus `orgName` when OV is active), injected server-side and not suppressible.

**Data egress in Local mode:** Original media bytes and ingredient `media` bytes stay on your machine. Trufo receives claim signing instructions and (unless `skip_manifest_storage: true`) retains the finished manifest — which includes generated thumbnails unless `thumbnail_settings.policy` is `"none"`, plus any embedded `ingredient.data`.

**Retries and billing:** Signing is metered when it completes; failed requests do not bill. Retries are **not** deduplicated — if a response is lost after server completion, retrying produces a second sign and a second charge. Prefer generous client timeouts over blind retries.

---

## `POST /c2pa/sign`

**Auth:** `X-API-Key` with `c2pa-sign-prod` (production hosts; requires C2PA Signing plan + active OV) or `c2pa-sign-test` (`https://test.api.trufo.ai`; no plan or OV required), or an access token with `c2pa_sign`.

### Request body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `media_input` | string | Yes\* | Base64-encoded input media (`REQUEST` only; max 10,000,000 raw bytes) |
| `media_input_s3` | string | Yes\* | Opaque reference from `/io/get-s3-upload-url` (`TASK` only) |
| `execution_mode` | string | No | `"request"` (default) or `"task"` (`"stream"` is unsupported) |
| `actions` | array | Yes | Ordered `[name, params]` pairs; see [Actions and Assertions](actions-and-assertions.md#actions) |
| `assertions` | array | No | Ordered `[name, params]` pairs; see [Actions and Assertions](actions-and-assertions.md#assertions) |
| `manifest_settings` | object | No | Structured titles, thumbnails, and `all_actions_included` (schema below) |
| `manifest_title` | string | No | Top-level alias for `manifest_settings.manifest_title` (do not set both) |
| `ingredient_title` | string | No | Top-level alias for `manifest_settings.ingredient_title` (do not set both) |
| `branded_gp_id` | string | No | Approved Branded Generator Product ID (`gp_...`), or `"test"` on `test.api.trufo.ai` |
| `signed_input_policy` | string | No | `"auto"` (default) or `"keep"` |
| `signed_ingredient_policy` | string | No | `"auto"` (default) or `"keep"` |
| `skip_manifest_storage` | boolean | No | Default `false`. When `true`, Trufo does not retain a copy of the signed manifest (incompatible with `per_embed` watermarking: `400 ManifestStorageRequired`) |

\* Provide exactly one of `media_input` or `media_input_s3`. Audio/video watermarking and files > 10 MB require `execution_mode: "task"`. The test host supports `REQUEST` only (no `TASK`).

### `manifest_settings` wire JSON

```json
{
  "manifest_title": "signed.jpg",
  "ingredient_title": "input.jpg",
  "thumbnail_settings": {
    "policy": "auto",
    "size": "medium"
  },
  "all_actions_included": true
}
```

| Field | Values | Default / Notes |
| --- | --- | --- |
| `manifest_title` | string \| null | Display title (`dc:title`) of the signed manifest; omitted when unset |
| `ingredient_title` | string \| null | Display title of the implicit input parent; falls back to input's manifest title, then `input.<ext>` |
| `thumbnail_settings.policy` | `"auto"`, `"auto_no_ingredient"`, `"none"` | Default `"auto"`. `"auto"` generates claim + missing ingredient thumbnails; `"auto_no_ingredient"` generates claim thumbnail only; `"none"` generates none. Inherited ingredient thumbnails are always preserved |
| `thumbnail_settings.size` | `"medium"`, `"high"` | Default `"medium"` (≤ 512 px height+width, WebP quality 80); `"high"` (≤ 1024 px, WebP quality 90). Alpha preserved |
| `all_actions_included` | boolean \| null | Defaults to `true` on standard signs, `false` when `creation`, `parentOf`, `action_history`, or `placement: "created"` is used. Refused (`400 Conflict`) if `true` with a `parentOf` that has no `action_history` |

### Responses

- **`REQUEST` (HTTP 200):**
  ```json
  { "media_output": "<base64-signed-bytes>", "warnings": [] }
  ```
  *(Sync `REQUEST` responses and `trufo-local` responses do not return `cid`/`wid`; use `POST /content/list` to query records created by sync/local signs.)*
- **`TASK` (HTTP 202):**
  ```json
  {
    "task_id": "...",
    "task_type": "c2pa_sign",
    "status": "queued",
    "startby_ts": "...",
    "timeout_seconds": 600
  }
  ```

### Common signing errors

| Status | `detail` | Meaning |
| --- | --- | --- |
| 400 | `ImageTooLarge: ...` | Image exceeds 400 megapixels |
| 400 | `Conflict: ...` | Incompatible combination (e.g., `transcode`/`repackage` with `c2pa.created`, or `all_actions_included: true` with `parentOf` without `action_history`) |
| 400 | `ManifestStorageRequired: ...` | `per_embed` watermark combined with `skip_manifest_storage: true` |
| 400 | `UnsupportedSDKVersion: ...` | Local mode engine/SDK too old for a requested feature or past support |
| 403 | `MissingOrganizationValidation` | Production signing before OV approval |
| 403 | `BPVNotActive: <reason>` | Branded Product Validation not active for `branded_gp_id` |
| 403 | `C2PACreatedUserAssertionsNotAuthorized: <reason>` | Request requires an authorized `branded_gp_id` |
| 404 | `GProductNotFound` | Unknown `branded_gp_id` in your organization |
| 410 | `Test keys are not accepted on this host...` | Test key used in Local mode against a production host |
| 429 | `ReservationLimitExceeded: ...` | Organization reached 10,000 live `per_embed` watermark reservations |

---

## `POST /io/get-s3-upload-url`

Allocates an ephemeral presigned S3 upload URL for `TASK` execution (production hosts only; test keys receive `410`).

**Auth:** `X-API-Key` with `c2pa-sign-prod` or `watermark-prod`.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `mime_type` | string | Yes | MIME type of the file you will PUT (must match `Content-Type` header on PUT) |
| `duration` | string | No | Accepted for compatibility; always returns `"standard"` |

**Response (200):**

```json
{
  "media_input_s3": "trufos3://...",
  "upload_url": "https://...",
  "expires_at": "2026-11-26T16:00:00Z",
  "duration": "standard"
}
```

- Upload URLs and `media_input_s3` references are valid for **1 hour**.
- Arbitrary S3 URLs are rejected; Trufo detects actual media type from the uploaded bytes.
- Ephemeral uploaded and output objects are deleted automatically after 1–2 days.

---

## `GET /tasks/{task_id}`

Poll an asynchronous `c2pa_sign` or `watermark` task on the **same API region** where it was submitted.

**Auth:** Same organization and scope (`c2pa-sign-prod` for `c2pa_sign`, `watermark-prod` for `watermark`).

**Response (200):** `task_id`, `task_type`, `status` (`queued` | `running` | `succeeded` | `failed` | `expired`), `create_ts`, `update_ts`, `start_ts`, `finish_ts`, `startby_ts`, `timeout_seconds`, `duration_ms`, `progress`, `file_size_bytes`, `file_mime_type`, `result`, `error`.

| Field | When `succeeded` |
| --- | --- |
| Signing `result` | `media_output_s3`, `download_url`, `expires_ts`, optional `cid`/`wid`, `warnings` |
| Watermark `result` | `media_output_s3`, `download_url`, `expires_ts`, `wid`, optional `cid`, `warnings` |

- `download_url` is valid for up to **15 minutes**; re-poll `GET /tasks/{task_id}` for a fresh link until `expires_ts` (**24 hours** after completion).
- When `failed` or `expired`, `error` carries `{code, http_status, message?}` inside the HTTP 200 status payload. Error codes: `invalid_input` (400), `permission_denied` (403), `input_not_found` (404), `capacity_exceeded` (429), `processing_failed` (500), `worker_lost` (500), `start_timeout` (503), `execution_timeout` (504). Queue rejection at submission returns `503 queue_submission_failed` with no `task_id`.

**Validation timing:** Watermark action validation, `branded_gp_id`, `assertions`, and created-placement checks run synchronously at submission (returning 4xx with no task created). Media-dependent checks (`signed_input_policy`, ingredient media parsing, format restrictions) run in the worker and surface in `error`.

---

## Local Mode

Local mode runs through `trufo-provenance` (via `sign_c2pa_local()` / `sign_c2pa_local_test()` in Python or `ghcr.io/trufo-ai/trufo-local` in Docker). The underlying multi-step client/server signing protocol is internal to the engine and not a direct HTTP API.

- **Generator info:** Records the local host OS and kernel release (e.g., `Linux 6.8.0-45-generic`).
- **Docker HTTP endpoint (`POST http://127.0.0.1:8080/c2pa/sign`):** Replaces `media_input` with `media_input_path` and `media_output_path` (absolute paths inside `TRUFO_LOCAL_INPUT_DIRS` / `TRUFO_LOCAL_OUTPUT_DIRS`) and accepts optional `watermark_settings: {"profile": "default" | "fast"}`. Returns `{"media_output_path": "...", "warnings": []}`.
- **Minimum engine versions by feature:**
  - `2.2.0+`: `ai_system`, `signed_input_policy`, `signed_ingredient_policy`
  - `2.3.0+`: `skip_manifest_storage`
  - `2.3.1+`: `c2pa_metadata`, `ingredient.data`, `creation.description`, `c2pa.translated` `parameters`, `plus`/`schema`/`xmpDM`/`xmpRights` in `cawg_metadata`
  - `2.3.2+`: `c2pa.transcoded` / `c2pa.repackaged` in `action_history`
  - `2.4.0+`: `resize`, `crop`, `trim`, `repackage`, `transcode` tuning parameters (`quality`, `crf`, `video_codec`, `audio_codec`, `audio_bitrate`), `all_actions_included: true` conflict check on `parentOf` without `action_history`

---

## Related References

- Actions, assertions, AI systems, and `signed_input_policy`: [actions-and-assertions.md](actions-and-assertions.md)
- Supported formats and media action limits: [media-formats.md](media-formats.md)
- Deprecations: [deprecations.md](deprecations.md)
