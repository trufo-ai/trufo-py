# Cloud Signing

Sign media with a C2PA manifest on Trufo's servers — directly in the request body for files up to 10 MB, or via ephemeral S3 uploads (`ExecutionMode.TASK`) for larger files and for media actions on audio and video.

To keep media on your own infrastructure, see [Local Signing (Python SDK)](signing-local-python.md) or [Local Signing (Docker)](signing-local-docker.md).

## Requirements

- `pip install trufo` (pure Python, no extra dependencies).
- A `c2pa-sign-test` key for `test.api.trufo.ai`, or a `c2pa-sign-prod` key + C2PA Signing plan + completed Organization Validation (OV) for production. See [Setup and Credentials](setup.md).
- Media in a supported format; see [Media Format Support](../reference/media-formats.md).

---

## Direct Signing (`REQUEST`)

Use direct signing for files up to **10 MB (10,000,000 bytes)**. Audio, video, and PDF files within that limit can be signed directly too, as long as the request has no media-processing action (`watermark`, `resize`, `crop`, `trim`, `transcode`, `repackage`); those actions on non-image input require `TASK` (`400 task_required` otherwise).

```python
from pathlib import Path

from trufo import sign_c2pa_cloud_test
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_TEST)
media_bytes = Path("input.jpg").read_bytes()

signed_bytes = sign_c2pa_cloud_test(api_key, media_bytes)
Path("signed.jpg").write_bytes(signed_bytes)
```

For production, swap in `sign_c2pa_cloud()` with a `c2pa-sign-prod` key:

```python
from trufo import sign_c2pa_cloud

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_PROD)
signed_bytes = sign_c2pa_cloud(api_key, media_bytes)
```

### Branded Generator Product signing

If your organization has an approved Branded Generator Product, pass its `gp_...` ID (shown in the dashboard under **C2PA Signing API → Manage**):

```python
BRANDED_GP_ID = "gp_..."
signed_bytes = sign_c2pa_cloud(api_key, media_bytes, branded_gp_id=BRANDED_GP_ID)
```

On the test host, pass `branded_gp_id="test"` to `sign_c2pa_cloud_test()` to test branded flows before your product is approved.

---

## Large Files, Audio, and Video (`TASK` via S3)

Use `ExecutionMode.TASK` for files over 10 MB, and for any media-processing action (watermarking, `resize`, `crop`, `trim`, `transcode`, `repackage`) on audio, video, or other non-image input. `TASK` mode runs on production hosts only (`api.trufo.ai` and `eu.api.trufo.ai`).

### Blocking helper (upload → submit → poll → download)

```python
from trufo import ExecutionMode, sign_c2pa_cloud

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_PROD)
signed_bytes = sign_c2pa_cloud(
    api_key,
    media_bytes,
    mime_type="video/mp4",
    execution_mode=ExecutionMode.TASK,
)
```

### Non-blocking task flow (submit now, poll and stream later)

For large video files or background job queues, upload and submit without holding a worker open, then poll `get_task()` or `wait_for_task()` against the same API region:

```python
from pathlib import Path

import requests
from trufo import get_s3_upload_url, get_task, submit_c2pa_sign, wait_for_task
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_PROD)

# 1. Allocate an ephemeral upload URL (valid 1 hour)
upload = get_s3_upload_url(api_key, mime_type="video/mp4")

# 2. Stream the file to S3 with the matching Content-Type
with Path("input.mp4").open("rb") as source:
    resp = requests.put(
        upload.upload_url,
        data=source,
        headers={"Content-Type": "video/mp4"},
        timeout=120,
    )
    resp.raise_for_status()

# 3. Submit the task (HTTP 202)
task = submit_c2pa_sign(api_key, upload.media_input_s3)
print("Submitted task:", task.task_id)

# 4. Poll until completion (default wait_seconds=600); emits result warnings as TrufoServerWarning
completed = wait_for_task(api_key, task.task_id, wait_seconds=600)
if completed.result.download_url is None:
    raise RuntimeError("The task output has expired.")

# Optional: persist the content ID (always set) and watermark ID (None without a watermark)
print("cid:", completed.result.cid, "wid:", completed.result.wid)

# 5. Stream the signed output to disk
with requests.get(completed.result.download_url, stream=True, timeout=120) as resp:
    resp.raise_for_status()
    with Path("signed.mp4").open("wb") as output:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            output.write(chunk)
```

- `TaskWaitTimeoutError.task_id` lets you resume polling without resubmitting.
- `TaskFailedError` exposes `.task.error_code`, `.task.error_http_status`, and `.task.error_message`.
- `download_url` links stay valid for up to 15 minutes; poll `get_task()` for a fresh link until `expires_ts` (24 hours after completion). Treat upload and download links as secrets.
- `get_task()` does not emit `TrufoServerWarning`; when you poll with it instead of `wait_for_task()`, read non-fatal notices from `task.result.warnings` yourself.

---

## Manifest Settings and Signed Inputs

### Titles and thumbnails (`ManifestSettings`)

Pass explicit `manifest_title` and `ingredient_title` (typically filenames) so validators display clean names: an unset `manifest_title` leaves the manifest untitled, and an unset `ingredient_title` falls back to the input's manifest title or `input.<ext>`. That fallback extension is derived by sniffing the bytes, which cannot tell formats that share a container apart (`TIFF` / `DNG`, `HEIC` / `HEIF` / `AVIF`), so always set titles for those formats.

```python
from trufo.c2pa import ManifestSettings, ThumbnailPolicy, ThumbnailSettings, ThumbnailSize

settings = ManifestSettings(
    manifest_title="sunset_edit.jpg",
    ingredient_title="sunset.jpg",
    thumbnail_settings=ThumbnailSettings(
        policy=ThumbnailPolicy.AUTO,   # or AUTO_NO_INGREDIENT, NONE
        size=ThumbnailSize.HIGH,       # MEDIUM (512 px, default) or HIGH (1024 px)
    ),
)
signed_bytes = sign_c2pa_cloud_test(api_key, media_bytes, manifest_settings=settings)
```

### Signed inputs (`signed_input_policy`)

When the input already carries a C2PA manifest, Trufo keeps it as the `parentOf` ingredient and records its validation results in the new manifest:

- **`auto` (default):** Keeps readable manifests (unless an `ai_system` assertion conflicts with a `camera_captured` or `human_created` input), fetches remote manifests from allowed hosts (recording them as inaccessible if unfetched, unless a source type is declared), and strips unreadable/corrupt C2PA data with a warning.
- **`keep`:** Refuses unreadable C2PA data (`400`) and unfetched remote manifests (`400 RemoteManifestUnavailable`), and skips the `ai_system` source-class check. See [Remote Manifests](../reference/actions-and-assertions.md#remote-manifests).

```python
from trufo.c2pa import SignedInputPolicy

signed_bytes = sign_c2pa_cloud_test(
    api_key,
    media_bytes,
    signed_input_policy=SignedInputPolicy.KEEP,
)
```

---

## Adding Actions, Assertions, and Handling Warnings

Pass `actions` (applied in order) and `assertions` as `[name, params]` pairs:

```python
signed_bytes = sign_c2pa_cloud(
    api_key,
    media_bytes,
    actions=[
        ["resize", {"width": 1600}],
        ["publish", {}],
    ],
    assertions=[
        ["cawg_identity", {"cawg_identity_id": "org_interim"}],
    ],
)
```

### Catching non-fatal warnings

Non-fatal notices (skipped watermarks, metadata dropped by a media action, untrusted incoming manifests) arrive in `warnings` and are emitted by the SDK signing helpers (and `wait_for_task()`) as `TrufoServerWarning`:

```python
import warnings
from trufo import TrufoServerWarning, sign_c2pa_cloud

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always", TrufoServerWarning)
    signed = sign_c2pa_cloud(api_key, media_bytes, actions=actions)

for w in caught:
    print("Trufo notice:", w.message)
```

### Region selection and retries

- **Europe endpoint:** Pass `trufo_api_url=TRUFO_API_URL_EUROPE` (`https://eu.api.trufo.ai`; `from trufo.api.endpoints import TRUFO_API_URL_EUROPE`). Use the same URL for `get_task()` / `wait_for_task()` on tasks submitted there.
- **Retries:** Signing is metered on completion and is not deduplicated. Use generous client timeouts rather than aggressive automatic retries on network timeouts.

---

## Troubleshooting

- **`403 MissingOrganizationValidation`:** Production signing requires approved OV; use `sign_c2pa_cloud_test()` while OV is pending.
- **`403 APIKeyScopeNotAllowed`:** Use `c2pa-sign-prod` for production hosts and `c2pa-sign-test` for `test.api.trufo.ai`.
- **`410 Test keys can't use upload links`:** S3 `TASK` uploads require a production key on a production host; use direct `REQUEST` bytes on the test host.

---

## Reference

- Privacy, `skip_manifest_storage`, and thumbnails: [Storage Options and Privacy](storage-options.md)
- Manifest settings, actions, assertions, and custom labels: [C2PA Manifests, Actions, and Assertions](c2pa-manifests.md)
- Signing endpoints, tasks, and `manifest_settings` JSON: [Signing API](../reference/signing-api.md)
- All actions, assertions, and `signed_input_policy`: [Actions and Assertions](../reference/actions-and-assertions.md)
- Supported formats and media action rules: [Media Format Support](../reference/media-formats.md)
- Complete runnable script: [signing_cloud.py](signing_cloud.py)
