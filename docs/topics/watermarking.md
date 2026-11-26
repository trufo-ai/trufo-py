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

In Local mode, watermarking requires `trufo[local-full]` ([Local Signing (Python SDK)](signing-local-python.md)) or `ghcr.io/trufo-ai/trufo-local:2.4-full` ([Local Signing (Docker)](signing-local-docker.md)).

---

## Binding Without Trufo Signing (`/bind/*`)

If you sign C2PA manifests with your own certificate and toolchain (`c2pa-rs`, `c2patool`, etc.), you can still embed Trufo watermarks via the standalone binding routes (requires a `watermark-prod` key + C2PA Signing or Watermark API plan + OV; or `watermark-test` on `test.api.trufo.ai`).

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

For large images (>10 MB), audio, or video on `/bind/watermark`, pass `execution_mode=ExecutionMode.TASK` and `mime_type=...` (or use `submit_bind_watermark()` + `wait_for_task()`).

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

- **For `per_embed` binds:** Add a `c2pa.watermarked.bound` action and a `c2pa.soft-binding` assertion (created placement) with algorithm `"ai.trufo.pawprint.watermark"` and block value set to the UTF-8 bytes of `wid` (e.g., `"v1...."` encoded as a CBOR byte string):

```json
{
  "alg": "ai.trufo.pawprint.watermark",
  "blocks": [{ "scope": {}, "value": "<wid UTF-8 bytes>" }]
}
```

- **For `per_ai_system` binds:** Pass `wid_allocation_mode="per_ai_system"`, `ai_system_id`, and `ai_involvement` to `bind_watermark()` or `bind_reserve()`, and record a `c2pa.watermarked.unbound` action in your manifest (no `c2pa.soft-binding` assertion; calling `bind_commit()` is optional).

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

---

## Managing Content Records

Every production sign or bind creates a content record. Per-embed watermark IDs count as active IDs until deactivated; look up, list, or toggle them with `get_content()`, `list_content()`, and `set_content_status()` (using a `c2pa-sign-prod` or `watermark-prod` key):

```python
from trufo import get_content, list_content, set_content_status

record = get_content(api_key, wid="v1.001a1b2c3d4")
set_content_status(api_key, "inactive", wid=record.wid)  # stops resolving & active-ID billing

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
- Complete runnable script: [watermarking.py](watermarking.py)
