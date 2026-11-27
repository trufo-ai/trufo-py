# Watermarking and Recovery

Embed an imperceptible **Trufo Pawprint** watermark in images, audio, or video so provenance survives manifest stripping, and decode watermarks later via `POST /content/recover`.

---

## Allocation Modes and Effort Policies

Watermarking is **off by default**. Include at most one `["watermark", {...}]` entry in `actions` (always place it **last**, after any `resize`, `crop`, `trim`, or `transcode` actions).

### `wid_allocation_mode`

- **`"per_embed"` (default):** Issues a unique watermark ID per file, linked to that file's stored C2PA manifest.
- **`"per_ai_system"`:** Embeds the shared watermark ID of the AI system named in `assertions` (`ai_system` entry required). Recovers the organization and AI system details rather than an individual file's manifest.

### `effort_policy`

| `effort_policy` | Unsupported format | Runtime failure |
| --- | --- | --- |
| `"require"` (default for `{}`) | Error | Error |
| `"require_if_supported"` | Signs unwatermarked + `TrufoServerWarning` | Error |
| `"best_effort"` | Signs unwatermarked + `TrufoServerWarning` | Signs unwatermarked + `TrufoServerWarning` |

> **Important:** `"require_if_supported"` checks only whether the **MIME type** is watermark-capable. A file of a supported type that hits a per-file restriction — for example a CMYK JPEG, HDR content, a 1-bit TIFF, or a fragmented MP4 — still fails the sign. Use `"best_effort"` if those files should also fall back to signing without a watermark. See [Media Format Support](../reference/media-formats.md).

### Integrated signing examples

```python
from trufo import ExecutionMode, sign_c2pa_cloud
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_PROD)

# Per-embed watermark (image <= 10 MB in Cloud REQUEST mode)
signed_img = sign_c2pa_cloud(
    api_key,
    image_bytes,
    actions=[["watermark", {"effort_policy": "require_if_supported"}]],
)

# Video or >10 MB image in Cloud mode requires ExecutionMode.TASK
signed_vid = sign_c2pa_cloud(
    api_key,
    video_bytes,
    mime_type="video/mp4",
    execution_mode=ExecutionMode.TASK,
    actions=[["watermark", {}]],
)

# Per-AI-system watermark (paired with ai_system assertion)
signed_ai = sign_c2pa_cloud(
    api_key,
    image_bytes,
    assertions=[["ai_system", {"ai_system_id": ai_system_id, "ai_involvement": "ai_generated"}]],
    actions=[["watermark", {"wid_allocation_mode": "per_ai_system"}]],
)
```

In Local mode, watermarking during signing requires `trufo[local-full]` ([Local Signing (Python SDK)](signing-local-python.md)) or `ghcr.io/trufo-ai/trufo-local:2.4-full` ([Local Signing (Docker)](signing-local-docker.md)). The `trufo-local` Docker images serve only `/health` and `/c2pa/sign` — not `/bind/*` or `/content/*`; for standalone binding, use the Python SDK or Trufo Cloud (below).

---

## Binding Without Trufo Signing (`/bind/*`)

If you sign C2PA manifests with your own certificate and toolchain (`c2pa-rs`, `c2patool`, etc.), you can still embed Trufo watermarks via the standalone binding routes (requires a `watermark-prod` key + C2PA Signing or Watermark API plan + OV; or `watermark-test` on `test.api.trufo.ai`). These routes run on Trufo Cloud only: `/bind/watermark` embeds on Trufo's servers, while `/bind/reserve` + `watermark_media()` embeds locally with the Python SDK (`trufo[local-full]`); the `trufo-local` Docker images do not serve them.

| | `/bind/watermark` (Cloud embed) | `/bind/reserve` (local embed) |
| --- | --- | --- |
| `per_embed` reservation | New ID reserved for **24 hours** (1 hour on the test host); commit before then | Same |
| `per_embed` billing | 1 new ID (first embed included) + media bytes (+ video compute), billed at `/bind/watermark` | 1 new ID (first embed included), billed at `/bind/commit`; nothing at reserve |
| `per_ai_system` | Embeds the AI system's ID; `0.1` per embed + media bytes (+ video compute), billed at `/bind/watermark` | `wid_package` expires after **1 hour**; `0.1` per embed, billed at `/bind/reserve` |
| `/bind/commit` | Bills the manifest bytes; the `per_embed` ID counts as active from commit until deactivated | Bills the manifest bytes plus the `per_embed` new ID above; the ID counts as active from commit |

At most **10,000** live (issued, uncommitted, unexpired) `per_embed` reservations per organization (`429 ReservationLimitExceeded`). An abandoned `per_embed` bind simply lets its reservation expire — the watermark ID never becomes active, but an embed already performed by `/bind/watermark` stays billed. The test host bills nothing.

### Cloud watermarking + your own signer

```python
from trufo import bind_commit, bind_watermark
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.WATERMARK_PROD)

# 1. Trufo embeds the watermark and opens a content record
result = bind_watermark(api_key, media_bytes)

# 2. Sign result.media with YOUR certificate, declaring the watermark in the manifest
store_bytes = your_signer(result.media, wid=result.wid)

# 3. Complete the record with your signed C2PA manifest store bytes
bind_commit(api_key, result.cid, result.wid, manifest_bytes=store_bytes)
```

`BindWatermarkResult.cid` is typed `str | None` for compatibility, but current servers return a `cid` for every successful embed — `per_embed` and `per_ai_system`, `REQUEST` and `TASK`. Treat a missing `cid` as an error rather than skipping the commit for `per_embed` binds.

For large images (>10 MB), audio, or video on `/bind/watermark`, pass `execution_mode=ExecutionMode.TASK` and `mime_type=...` (or use `submit_bind_watermark()` + `wait_for_task()`). `TASK` runs on production hosts only; on `test.api.trufo.ai`, use `/bind/reserve` + `watermark_media()` for audio and video.

### Local watermarking + your own signer (`trufo[local-full]`)

```python
from trufo import bind_commit, bind_reserve, watermark_media

reservation = bind_reserve(api_key, "image/jpeg")
marked = watermark_media(media_bytes, reservation.wid_package)
store_bytes = your_signer(marked, wid=reservation.wid)
bind_commit(api_key, reservation.cid, reservation.wid, manifest_bytes=store_bytes)
```

*(If `trufo[local-sign-only]` or `trufo[local-full]` is installed, `bind_commit()` also accepts `signed_media_bytes=` instead of `manifest_bytes=`.)*

### What your own signer should declare in the manifest

- **For `per_embed` binds:** Add a `c2pa.watermarked.bound` action and a `c2pa.soft-binding` assertion in the **created** assertions of your Claim v2 manifest, with algorithm `"ai.trufo.pawprint.watermark"` and one block whose `value` is the UTF-8 bytes of `wid`:

```json
{
  "alg": "ai.trufo.pawprint.watermark",
  "blocks": [{ "scope": {}, "value": "<wid UTF-8 bytes>" }]
}
```

> **`c2pa-rs` and other non-Python signers:** The JSON above is illustrative. In the CBOR assertion, `value` must be a **CBOR byte string (`bstr`)** containing the UTF-8 bytes of `wid` (for example `b"v1.001a1b2c3d4"`), not a CBOR text string. In Rust, serialize the block `value` as `Vec<u8>` with `#[serde(with = "serde_bytes")]` (as c2pa-rs's own `SoftBinding` assertion type does) and set it to `wid.as_bytes().to_vec()`.

- **For `per_ai_system` binds:** Pass `wid_allocation_mode="per_ai_system"`, `ai_system_id`, and `ai_involvement` to `bind_watermark()` or `bind_reserve()`, and record a `c2pa.watermarked.unbound` action in your manifest (no `c2pa.soft-binding` assertion; calling `bind_commit()` is optional). The embedded ID is the AI system's ID for that `ai_involvement`: `"ai_generated"` and `"ai_modified"` each have their own ID, and the AI system must be registered (and active) for the mode you pass, otherwise the bind returns `400`.

A manifest that omits the expected declaration still commits, with a warning in the response. `bind_commit(manifest_bytes=...)` takes the raw C2PA manifest store (JUMBF) bytes; the REST `POST /bind/commit` takes the same bytes base64-encoded in `manifest`. See [Watermarking and Content API](../reference/watermarking-api.md#post-bindcommit).

---

## Recovering Watermarks (`POST /content/recover`)

Decode a Trufo watermark from a file — even after its C2PA manifest has been stripped — using a `content-recover-prod` key (or `content-recover-test` with `TRUFO_API_URL_TEST`):

```python
from trufo import recover_content
from trufo.api.endpoints import TRUFO_API_URL_TEST
from trufo.util.credentials import TrufoAPIKey, load_api_key

recover_key = load_api_key(TrufoAPIKey.CONTENT_RECOVER_TEST)

result = recover_content(recover_key, media_bytes, trufo_api_url=TRUFO_API_URL_TEST)
if result.detected:
    print("wid:", result.wid, "confidence:", result.confidence, "mode:", result.wid_allocation_mode)
    # per_embed: result.manifest_bytes (validate before relying on it; see topics/verification.md)
    # per_ai_system: result.ai_system, result.ai_involvement
```

`recover_content()` defaults to the production host (`api.trufo.ai`); always pass `trufo_api_url=TRUFO_API_URL_TEST` when recovering test-host marks. Pass `parse_manifest_json=True` if you want a convenience JSON parse alongside `manifest_bytes` (note that `manifest_json` is a parse, not a cryptographic validation result — see [Verification](verification.md)).

- **Transport:** `/content/recover` takes the whole file base64-encoded in one JSON request (`media_input`). There is no `TASK` mode or S3 upload reference for recovery, so keep payloads modest: for a long video, cut a shorter representative clip from it and recover from that instead of sending the full file.
- **What you get back:** `detected=True` with no `manifest_bytes` is normal for `per_ai_system` marks (you get `ai_system` / `ai_involvement` instead) and for another organization's `per_embed` record that has been set `inactive` (only detection is disclosed). Your own organization always sees its own records, active or inactive.

---

## Managing Content Records

Every production sign or bind creates a content record. Per-embed watermark IDs count as active IDs until deactivated; look up, list, or toggle them with `get_content()`, `list_content()`, and `set_content_status()` (using a `c2pa-sign-prod` or `watermark-prod` key):

```python
from trufo import get_content, list_content, set_content_status

record = get_content(api_key, wid="v1.001a1b2c3d4")
set_content_status(api_key, "inactive", wid=record.wid)
# inactive: other organizations' recover calls get detection only, and the ID leaves
# active-ID billing; your own organization can still look up and recover the record

page = list_content(api_key, status="active", created_after="2026-04-01T00:00:00Z")
for item in page.items:
    print(item.cid, item.wid, item.origin, item.create_ts)
```

Per-AI-system embeds record `ai_system_wid` (not `wid`) and cannot be deactivated per file.

---

## Troubleshooting

- **`Watermarking is not supported for <mime> media`:** Check [Media Format Support](../reference/media-formats.md) or use `effort_policy: "require_if_supported"` / `"best_effort"`.
- **`400 ManifestStorageRequired`:** `per_embed` watermarking cannot be combined with `skip_manifest_storage: true`.
- **`400 WatermarkNotAvailable` (Docker):** Switch from `trufo-local:2.4` to `trufo-local:2.4-full`.
- **Migrating from `mode: "provenance"` or `effort`:** Use `wid_allocation_mode: "per_embed"` and `effort_policy`; see [Deprecations](../reference/deprecations.md).

---

## Reference

- Standalone bind, recovery, content records, and watermark billing: [Watermarking and Content API](../reference/watermarking-api.md)
- Format restrictions for embedding and recovery: [Media Format Support](../reference/media-formats.md)
- Complete runnable script: [watermarking.py](watermarking.py) (integrated watermarking during signing and recovery on the test host; the standalone `/bind/*` and `/content/*` examples are inline above)
