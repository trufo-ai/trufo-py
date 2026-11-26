# Watermarking and Content API Reference

Normative specification for standalone watermark binding (`/bind/*`), watermark recovery (`/content/recover`), content record management (`/content/*`), and watermark billing.

For integrated watermarking during C2PA signing, see [Actions and Assertions — `watermark`](actions-and-assertions.md#watermark).

---

## Watermark Billing

Applies to every watermarking route (C2PA Signing Cloud/Local and Standalone Binding Cloud/Local):

- **Watermark ID units:** `1` per new ID, `0.1` per embed, and `0.1` per active ID per year (counted daily at UTC).
  - A `per_embed` mark bills 1 new ID (first embed included) and counts as an active ID from commit until deactivated via `/content/status`.
  - Registering an AI system bills 1 new ID per `ai_involvement_modes` entry (active from registration); each `per_ai_system` mark bills `0.1` per embed only.
- **Data processing & video compute:** Cloud routes bill media + manifest bytes (Local routes bill manifest bytes). Video watermarked on Trufo's servers additionally bills `$0.30/GB` of input file size.

---

## Standalone Binding (`/bind/*`)

Embed a Trufo watermark when **you** sign the C2PA manifest with your own certificate.

**Auth:** `X-API-Key` with `watermark-prod` (production hosts; requires C2PA Signing or Watermark API plan + active OV) or `watermark-test` (`https://test.api.trufo.ai`).

### `POST /bind/watermark` (Cloud embed)

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `media_input` | string | Yes\* | Base64-encoded media (`REQUEST`, ≤ 10 MB images) |
| `media_input_s3` | string | Yes\* | Upload reference from `/io/get-s3-upload-url` (`TASK`, production only; required for > 10 MB images, audio, video) |
| `execution_mode` | string | No | `"request"` (default) or `"task"` |
| `wid_allocation_mode` | string | No | `"per_embed"` (default) or `"per_ai_system"` (`"per_asset"` → `501`) |
| `ai_system_id` | string | With `per_ai_system` | Registered AI system ID |
| `ai_involvement` | string | With `per_ai_system` | `"ai_generated"` or `"ai_modified"` |

**`REQUEST` Response (200):** `{"media_output": "<b64>", "wid": "v1....", "cid": "...", "warnings": []}`.  
**`TASK` Response (202):** Standard task acceptance; poll `GET /tasks/{task_id}` (see [Signing API — Tasks](signing-api.md#get-taskstask_id)).

**Errors:** `400` invalid parameter/format/inactive AI system, `404 AISystemNotFound`, `422` schema error, `429 ReservationLimitExceeded` (10,000 live `per_embed` reservations per org), `501` `per_asset`.

### `POST /bind/reserve` (Local embed reservation)

Reserve a watermark ID to embed locally with `trufo[local-full]` (`watermark_media()`).

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `mime_type` | string | Yes | Encode-supported MIME type ([Media Format Support](media-formats.md)) |
| `wid_allocation_mode`, `ai_system_id`, `ai_involvement` | string | As above | Same rules and errors as `/bind/watermark` |

**Response (200):** `{"cid": "...", "wid_package": {"wid": "v1....", "expires_at": "..."}}`.  
Per-embed reservations expire after **24 hours** (1 hour on test host) and bill at `/bind/commit`. Per-AI-system reservations expire after 1 hour and bill at issuance.

### `POST /bind/commit`

Complete a bind record after signing the watermarked file with your own certificate. Required for `per_embed` binds; optional for `per_ai_system` binds. Idempotent on identical retries (`409` if retried with a different manifest).

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `cid` | string | Yes | Record ID from `/bind/watermark` or `/bind/reserve` |
| `wid` | string | Yes | Watermark ID issued with that record |
| `manifest` | string | Yes | Base64-encoded C2PA manifest store bytes |

**Manifest declaration expected by `/bind/commit`:**
- **`per_embed`:** `c2pa.watermarked.bound` action + created `c2pa.soft-binding` assertion:
  ```json
  {
    "alg": "ai.trufo.pawprint.watermark",
    "blocks": [{ "scope": {}, "value": "<wid UTF-8 bytes as CBOR bstr>" }]
  }
  ```
- **`per_ai_system`:** `c2pa.watermarked.unbound` action (no `c2pa.soft-binding` assertion).

Manifests omitting the expected declaration still commit with a warning in `warnings`. Trust status is not checked at commit.

**Response (200):** `{"cid": "...", "wid": "...", "warnings": []}`.  
**Errors:** `400` malformed `wid` or unparseable manifest, `404` unknown `cid` or expired/mismatched reservation, `409` already committed with a different manifest, `422` missing `manifest`.

---

## Watermark Recovery

### `POST /content/recover`

Read-only watermark decode and resolution. Production calls bill input bytes and returned manifest bytes as data processing.

**Auth:** `X-API-Key` with `content-recover-prod` (production hosts; requires C2PA Signing or Watermark API plan) or `content-recover-test` (`https://test.api.trufo.ai`). Each key works only on its own host tier.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `media_input` | string | Yes | Base64-encoded media (see WM decode in [Media Format Support](media-formats.md)) |
| `parse_manifest_json` | boolean | No | Default `false`. Also return `manifest_json` (convenience parse, not a validation result) |

**Response (200):**

| Field | Type | Description |
| --- | --- | --- |
| `detected` | boolean | Whether a Trufo watermark was found |
| `wid` | string \| null | Decoded watermark ID |
| `confidence` | number \| null | Detection strength in `(0, 1]` (signal strength, not a probability) |
| `wid_allocation_mode` | string \| null | `"per_embed"` or `"per_ai_system"` |
| `manifest_bytes` | string \| null | Base64-encoded stored C2PA manifest store (`per_embed`, when active or owned by caller) |
| `manifest_json` | object \| null | Parsed manifest JSON when `parse_manifest_json: true` |
| `ai_involvement` | string \| null | `"ai_generated"` or `"ai_modified"` (`per_ai_system`) |
| `ai_system` | object \| null | `{name, version, c2pa_ai_disclosure, org_name, ai_system_id?, status?}` (`ai_system_id` and `status` present only for your own AI systems) |
| `status` | string \| null | `"active"` or `"inactive"` (present only on caller's own `per_embed` records) |
| `oid` | string \| null | Caller's organization ID (present only when the mark belongs to caller's org) |

**Errors:** `400 UndecodableMedia` (input could not be parsed as a supported image, video, or audio format).

---

## Content Records (`/content/*`)

Manage your own organization's production signing and binding records. Not metered; no active plan required (so lapsed subscribers can still deactivate active IDs).

**Auth:** `X-API-Key` (`c2pa-sign-prod` or `watermark-prod`) or dashboard session. Production hosts only.

**Record shape:** `cid`, `wid` (for `per_embed`), `ai_system_wid` (for `per_ai_system`), `mid`, `status` (`"active"` | `"inactive"` | `null`), `origin` (`c2pa_hosted` | `c2pa_distributed` | `bind_hosted` | `bind_distributed`), `mime_type`, `create_ts`, `commit_ts`.

### `POST /content/get`

**Request:** Exactly one of `cid`, `wid` (`v1.` or legacy `image.`/`audio.`), or `mid`. **Response (200):** record object. **Errors:** `400` malformed `wid`, `404` not found (does not match `ai_system_wid`), `422` zero or multiple keys.

### `POST /content/list`

**Request:** Optional `status` (`"active"` | `"inactive"`), `origin`, `created_after` (RFC 3339), `created_before` (RFC 3339), `cursor`, `limit` (`1..100`, default `50`).  
**Response (200):** `{"items": [...], "next_cursor": "..." | null}` (oldest first; `per_ai_system` records appear when `status` filter is omitted).

### `POST /content/status`

**Request:** Exactly one of `cid`, `wid`, or `mid`, plus `"status": "active" | "inactive"`. Idempotent; does not delete records or alter signed files. Switching a `per_embed` record to `"inactive"` stops resolution to other organizations immediately and removes it from active-ID billing at the next UTC daily count. **Errors:** as `/content/get`; `404` for records without a `wid` (including `per_ai_system` records).
