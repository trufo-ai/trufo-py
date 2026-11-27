# Watermarking and Content API Reference

Normative specification for standalone watermark binding (`/bind/*`), watermark recovery (`/content/recover`), content record management (`/content/*`), and watermark billing.

For integrated watermarking during C2PA signing, see [Actions and Assertions — `watermark`](actions-and-assertions.md#watermark).

---

## Watermark Billing

Applies to every watermarking route (C2PA Signing Cloud/Local and Standalone Binding Cloud/Local):

- **Watermark ID units:** `1` per new ID, `0.1` per embed, and `0.1` per active ID per year (counted daily at UTC).
  - A `per_embed` mark bills 1 new ID (first embed included) and counts as an active ID from commit until deactivated via `/content/status`.
  - Registering an AI system bills 1 new ID per `ai_involvement_modes` entry (active from registration); each `per_ai_system` mark bills `0.1` per embed only.
- **Data processing:** C2PA Signing Cloud bills the input media bytes; C2PA Signing Local bills no data processing. Standalone Binding bills the input media bytes at `/bind/watermark` and the manifest bytes at `/bind/commit` (`/bind/reserve` bills none). Recovery bills input bytes plus returned manifest bytes (see below).
- **Video compute:** Video watermarked on Trufo's servers (Cloud signing or `/bind/watermark`) additionally bills `$0.30/GB` of input file size.

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

- **`cid`:** Typed nullable for compatibility, but returned for every successful embed (`per_embed` and `per_ai_system`, `REQUEST` and `TASK`); pass it to `/bind/commit`.
- **`per_embed`:** Reserves a new watermark ID for **24 hours** (1 hour on the test host); commit within that window. Bills 1 new ID (first embed included) and the input bytes (plus video compute) here, whether or not you later commit.
- **`per_ai_system`:** Embeds the AI system's existing ID for the given `ai_involvement` (`"ai_generated"` and `"ai_modified"` each have their own ID; the AI system must be active and registered for that mode, otherwise `400`). Bills `0.1` per embed and the input bytes (plus video compute) here; no new ID.

**Errors:** `400` invalid parameter/format/inactive AI system, `404 AISystemNotFound`, `422` schema error, `429 ReservationLimitExceeded` (10,000 live `per_embed` reservations per org), `501` `per_asset`.

### `POST /bind/reserve` (Local embed reservation)

Reserve a watermark ID to embed locally with `trufo[local-full]` (`watermark_media()`).

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `mime_type` | string | Yes | Encode-supported MIME type ([Media Format Support](media-formats.md)) |
| `wid_allocation_mode`, `ai_system_id`, `ai_involvement` | string | As above | Same rules and errors as `/bind/watermark` |

**Response (200):** `{"cid": "...", "wid_package": {"wid": "v1....", "expires_at": "..."}}` (`expires_at` RFC 3339 UTC). Pass `wid_package` unchanged to `watermark_media()`.  
Per-embed reservations expire after **24 hours** (1 hour on test host); nothing is billed at reserve — 1 new ID (first embed included) bills at `/bind/commit`. Per-AI-system packages expire after 1 hour and bill 0.1 per embed at issuance.

Not served by the `trufo-local` Docker images; local embedding uses the Python SDK (`trufo[local-full]`).

### `POST /bind/commit`

Complete a bind record after signing the watermarked file with your own certificate. Required for `per_embed` binds; optional for `per_ai_system` binds. Idempotent on identical retries (`409 AlreadyCommitted` if retried with a different manifest).

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `cid` | string | Yes | Record ID from `/bind/watermark` or `/bind/reserve` |
| `wid` | string | Yes | Watermark ID issued with that record |
| `manifest` | string | Yes | Base64 encoding of the raw C2PA manifest store (JUMBF) bytes — the store your signer produced, not the signed media file and not manifest JSON |

**Manifest declaration expected by `/bind/commit`:**
- **`per_embed`:** `c2pa.watermarked.bound` action + `c2pa.soft-binding` assertion in the claim's **created** assertions (Claim v2):
  ```json
  {
    "alg": "ai.trufo.pawprint.watermark",
    "blocks": [{ "scope": {}, "value": "<wid UTF-8 bytes as CBOR bstr>" }]
  }
  ```
  In the signed CBOR, `value` must be a byte string (`bstr`) holding the UTF-8 bytes of `wid`, not a text string — set this explicitly when building the assertion with `c2pa-rs` or another non-Python signer.
- **`per_ai_system`:** `c2pa.watermarked.unbound` action (no `c2pa.soft-binding` assertion).

Manifests omitting the expected declaration still commit with a warning in `warnings`. Trust status is not checked at commit. Commit bills the manifest bytes; for `/bind/reserve` `per_embed` records it also bills 1 new ID (first embed included). A `per_embed` ID counts as active from commit.

**Response (200):** `{"cid": "...", "wid": "...", "warnings": []}`.  
**Errors:**
- `400 InvalidWid`: `wid` is malformed or from the wrong ID space, or (for `per_ai_system` and test-host records) is not the ID issued with this record.
- `400`: unparseable manifest, a `cid` that is not a bind record, or a manifest ID that is already registered.
- `404`: unknown `cid`; `404 ReservationNotFound` when a well-formed production `per_embed` `wid` has no live reservation held by your organization for this record's route (for example, it expired).
- `409 AlreadyCommitted`: the record was already committed with a different `wid` or manifest.
- `422`: missing `manifest`.

---

## Watermark Recovery

### `POST /content/recover`

Read-only watermark decode and resolution. Production calls bill input bytes (even when the call fails with `400 UndecodableMedia`) and returned manifest bytes as data processing.

**Auth:** `X-API-Key` with `content-recover-prod` (production hosts; requires C2PA Signing or Watermark API plan) or `content-recover-test` (`https://test.api.trufo.ai`). Each key works only on its own host tier.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `media_input` | string | Yes | Base64-encoded media, sent inline (see WM decode in [Media Format Support](media-formats.md)). There is no `TASK` mode or `media_input_s3` for recovery; for long videos, send a shorter representative clip |
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

When the mark belongs to another organization and its `per_embed` record is `inactive` or not yet committed, the response is `detected: true` with `wid`, `confidence`, `wid_allocation_mode`, and `manifest_bytes` all `null`.

**Errors:** `400 UndecodableMedia` (input could not be parsed as a supported image, video, or audio format).

---

## Content Records (`/content/*`)

Manage your own organization's production signing and binding records. Not metered; no active plan required (so lapsed subscribers can still deactivate active IDs).

**Auth:** `X-API-Key` (`c2pa-sign-prod` or `watermark-prod`) or an access token (Bearer). Production hosts only.

**Record shape:** `cid`, `wid` (for `per_embed`), `ai_system_wid` (for `per_ai_system`), `mid`, `status` (`"active"` | `"inactive"` | `null`), `origin` (`c2pa_hosted` | `c2pa_distributed` | `bind_hosted` | `bind_distributed`), `mime_type`, `create_ts`, `commit_ts`.

### `POST /content/get`

**Request:** Exactly one of `cid`, `wid` (`v1.` or legacy `image.`/`audio.`), or `mid`. **Response (200):** record object. **Errors:** `400` malformed `wid`, `404` not found (does not match `ai_system_wid`), `422` zero or multiple keys.

### `POST /content/list`

**Request:** Optional `status` (`"active"` | `"inactive"`), `origin`, `created_after` (RFC 3339), `created_before` (RFC 3339), `cursor`, `limit` (`1..100`, default `50`).  
**Response (200):** `{"items": [...], "next_cursor": "..." | null}` (oldest first; `per_ai_system` records appear when `status` filter is omitted).

### `POST /content/status`

**Request:** Exactly one of `cid`, `wid`, or `mid`, plus `"status": "active" | "inactive"`. Idempotent; does not delete records or alter signed files. Switching a `per_embed` record to `"inactive"` stops resolution to other organizations immediately and removes it from active-ID billing at the next UTC daily count. **Errors:** as `/content/get`; `404` for records without a `wid` (including `per_ai_system` records).
