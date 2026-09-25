# Quickstart: C2PA Signing

Sign media with a C2PA manifest — the core of the Trufo Provenance Service. Three
modes: simple (media sent to Trufo), S3 (for large media), and distributed (media
stays on your machine).

## What This Does

Trufo assembles a C2PA manifest for your media, signs it with a Trufo certificate,
and returns the signed file. You do not need a certificate of your own — Trufo
signs on your behalf. (To sign with your own enrolled certificate instead, see
[1_certs.md](1_certs.md).)

Every manifest carries an automatic `ai.trufo.identity` assertion naming your
organization — see [Automatic assertions](../api/api_c2pa.md#automatic-assertions).

## Requirements

- A `c2pa-sign-test` API key for test signing, or a `c2pa-sign-prod` key plus
  completed Organization Validation (OV) for production. See [0_setup.md](0_setup.md).
- `pip install trufo` — simple and S3 signing need nothing else. Distributed
  signing additionally needs a local engine extra and a `tsa` key (below).
- Input matching the [media format support policy](../api/media_format_support.md).

## Choosing a Mode

| Mode | Use when | Media sent to Trufo | Extra requirements |
| ---- | -------- | ------------------- | ------------------ |
| Simple | Default choice | Yes, in the request body | None |
| S3 | Media is large | Yes, via an ephemeral upload | None |
| Distributed | Media must not leave your infrastructure | No — only the claim hash | `trufo[local-sign-only]` or `[local-full]`, a `tsa` key, Linux x86_64 + CPython 3.12 |

The test helpers target the test host (`test.api.trufo.ai`) and need no OV; you can use
them to test basic API functions before making a production-signed asset.
The test output is not recognized by conformant C2PA validators.

---

## Simple Signing

```python
from pathlib import Path

from trufo import sign_c2pa_test
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_TEST)

media_bytes = Path("input.jpg").read_bytes()
signed_bytes = sign_c2pa_test(api_key, media_bytes)

Path("signed.jpg").write_bytes(signed_bytes)
```

For production, swap the helper and the key:

```python
from trufo import sign_c2pa

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_PROD)
signed_bytes = sign_c2pa(api_key, media_bytes)
```

Production signing requires completed OV; without it the API returns
`403 MissingOrganizationValidation`.

---

## Manifest Settings

Manifests and their ingredients carry display names (`dc:title`) that validator
UIs show prominently. Pass them explicitly — typically the asset's filename:

Legacy `manifest_title` and `ingredient_title` keyword arguments remain
supported. New code can group them with thumbnail and action-completeness
settings:

```python
from trufo.c2pa import ManifestSettings

signed_bytes = sign_c2pa_test(
    api_key,
    media_bytes,
    manifest_settings=ManifestSettings(
        manifest_title="sunset_edit.jpg",  # signed output display name
        ingredient_title="sunset.jpg",     # implicit input-parent display name
    ),
)
```

When omitted, the manifest carries no title, and the input's ingredient entry
falls back to the input's own manifest title, then a generic name. Fallbacks
are derived, not authored — see
[title fallbacks](../api/api_c2pa.md#post-c2pasign) for the exact order.

Thumbnail generation is automatic. The default `MEDIUM` preset uses 512 px
WebP thumbnails at quality 80. Use `HIGH` when validator previews need more
detail:

```python
from trufo.c2pa import ManifestSettings, ThumbnailSettings, ThumbnailSize

signed_bytes = sign_c2pa_test(
    api_key,
    media_bytes,
    manifest_settings=ManifestSettings(
        thumbnail_settings=ThumbnailSettings(size=ThumbnailSize.HIGH),
    ),
)
```

The default `AUTO` policy creates the claim thumbnail and any missing
supported ingredient thumbnails without replacing inherited ones. Use
`ThumbnailPolicy.AUTO_NO_INGREDIENT` for a claim thumbnail only, or
`ThumbnailPolicy.NONE` to generate none. Inherited ingredient thumbnails are
preserved under every policy. See the [C2PA API reference](../api/api_c2pa.md#post-c2pasign)
for the full settings.

---

## S3 Signing

For large media, upload to an ephemeral Trufo-signed S3 location instead of
putting bytes in the request body. Specify `ExecutionMode.TASK` to have the SDK
upload → submit task → poll → download for you. This call blocks until completion:

```python
from trufo import ExecutionMode, sign_c2pa

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_PROD)
signed_bytes = sign_c2pa(
    api_key, media_bytes, mime_type="image/jpeg", execution_mode=ExecutionMode.TASK,
)
```

Use TASK for files above 10 MB (10,000,000 bytes), and for audio, video, or other
non-image processing (e.g. watermarking or transcoding). Signing-only calls for
supported formats under the size cap can use REQUEST. The SDK defaults to REQUEST
and never switches modes automatically; requests requiring TASK are rejected.
TASK is not supported on the test host.

The legacy S3 helpers are deprecated:

| Deprecated helper | Replacement |
|---|---|
| `get_c2pa_s3_upload_url()` | `get_s3_upload_url()`; both return `GetS3UploadURLResult` |
| `sign_c2pa_s3()` | `submit_c2pa_sign()` followed by `wait_for_task()` |
| `sign_c2pa_via_s3()` | `sign_c2pa(..., execution_mode=ExecutionMode.TASK, mime_type=...)` |
| `sign_c2pa_s3_test()` / `sign_c2pa_via_s3_test()` | `sign_c2pa_test()` with REQUEST bytes; test endpoints do not support tasks |

The production helpers remain callable with their existing signatures and require
explicit TASK execution for signing. Test S3 helpers reject before making a request.

To submit without waiting for processing, use `submit_c2pa_sign()` with a Trufo
upload reference, then `get_task()` or `wait_for_task()` against the same API
region. Upload and submission are synchronous HTTP calls; only processing runs
independently. The synchronous helpers use a local polling budget of
600 seconds by default (`wait_seconds`); `TaskWaitTimeoutError.task_id` lets you resume
polling without resubmitting. Stopping the wait does not cancel the task.
`wait_for_task()` checks immediately, then every second for the first 10 seconds,
every 10 seconds until 10 minutes, and every minute for longer waits. This schedule
is fixed; only the waiting budget is configurable.
See the [API contract](../api/api_c2pa.md#tasks).

```python
from pathlib import Path

import requests
from trufo import get_s3_upload_url, submit_c2pa_sign, get_task, wait_for_task
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_PROD)
upload = get_s3_upload_url(api_key, mime_type="image/tiff")
with Path("input.tiff").open("rb") as source:
    response = requests.put(
        upload.upload_url, data=source,
        headers={"Content-Type": "image/tiff"}, timeout=120,
    )
    response.raise_for_status()

task = submit_c2pa_sign(api_key, upload.media_input_s3)
print(task.task_id)  # save this ID to retrieve the result later

# elsewhere: check once, or wait for completion without resubmitting
status = get_task(api_key, task.task_id)
print(status.status.value)
completed = wait_for_task(api_key, task.task_id, wait_seconds=600)
if completed.result.download_url is None:
    raise RuntimeError("The task output has expired.")

with requests.get(completed.result.download_url, stream=True, timeout=120) as response:
    response.raise_for_status()
    with Path("signed.tiff").open("wb") as output:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            output.write(chunk)
```

`submit_c2pa_sign()` always submits a TASK, so it takes no `execution_mode`
argument. Reuse an existing Trufo upload reference to skip the upload step;
arbitrary S3 URLs are not accepted. Download from `download_url`, not the opaque
`media_output_s3` reference. `wait_for_task()` raises `TaskFailedError` for a failed or
expired task; its `.task` contains the status and error code. Increasing
`wait_seconds` does not increase the server's execution timeout.

---

## Distributed Signing

`sign_c2pa_distributed()` builds the C2PA claim inside your own process and calls
Trufo only to sign the claim hash. The media file never leaves your machine.

Install a local engine extra (see the [README](../../README.md#optional-local-engine)
for the private-index setup) and configure a `tsa` key for RFC 3161 timestamping:

```bash
pip install "trufo[local-sign-only]"     # add watermarking with "trufo[local-full]"
trufo set-api-key tsa <your-api-key>
```

```python
from trufo import sign_c2pa_distributed_test

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_TEST)
signed_bytes = sign_c2pa_distributed_test(
    api_key,
    media_bytes,
    assertions=[["cawg_identity", {"cawg_identity_id": "test"}]],
)
```

Use `sign_c2pa_distributed()` with a `c2pa-sign-prod` key for production. Both
helpers load the TSA key from the SDK credential path automatically; pass
`tsa_api_key="..."` to override.

Distributed signing does not support every feature — notably `transcode` — and
runs only on Linux x86_64 with CPython 3.12.

---

## Server Selection

The SDK defaults to the Global API endpoint. To use the Europe endpoint:

```python
from trufo.api.endpoints import TRUFO_API_URL_EUROPE

signed_bytes = sign_c2pa(api_key, media_bytes, trufo_api_url=TRUFO_API_URL_EUROPE)
```

Organizations with a dedicated API or TSA can set them explicitly via
`trufo_api_url` / `trufo_tsa_url`. See
[what is region-scoped](../api/api_trufo.md#regions).

---

## Adding Actions and Assertions

All modes accept the same request shape: `actions` are instructions Trufo applies
in order, `assertions` are statements recorded in the manifest. Each entry is a
`[name, params]` pair.

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    actions=[["publish", {}]],
    assertions=[["cawg_identity", {"cawg_identity_id": "org_interim"}]],
)
```

| Goal | Guide |
| ---- | ----- |
| Disclose AI-generated content | [3_ai_labeling.md](3_ai_labeling.md) |
| Attach organization identity and metadata | [4_cawg_publish.md](4_cawg_publish.md) |
| Declare source assets, or redact from history | [5_ingredients.md](5_ingredients.md) |
| Embed a recoverable watermark | [6_watermarking.md](6_watermarking.md) |

---

## Troubleshooting

**`403 MissingOrganizationValidation`** — production signing requires completed OV.
Use the test helpers until OV is complete.

**`403 APIKeyScopeNotAllowed`** — the key's scope doesn't match: `c2pa-sign-prod`
for production, `c2pa-sign-test` for test.

**`ImportError: The optional trufo-provenance dependency is required`** — install
`trufo[local-sign-only]` (or `[local-full]`) for distributed signing.

**`A TSA API key is required for remote C2PA signing`** — store a `tsa` key or pass
`tsa_api_key` explicitly.

**The sign succeeded but something was skipped** — check the response `warnings`;
the SDK re-emits them as `TrufoServerWarning`. See
[`warnings`](../api/api_c2pa.md#response-warnings).

---

## Reference

- Setup and credentials: [0_setup.md](0_setup.md)
- C2PA signing API reference: [../api/api_c2pa.md](../api/api_c2pa.md)
- Complete runnable example: [2_c2pa_signing.py](2_c2pa_signing.py)
