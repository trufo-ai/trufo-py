# 8. Watermarking with Pawprint

This guide covers embedding Trufo Pawprint invisible watermarks so provenance survives manifest stripping, and recovering the manifest from a stripped or re-encoded file. It covers both the managed route, where Trufo signs, and the Bring Your Own (BYO) route, where you sign with your own C2PA signer.

---

## 1. Choose a Route and an Allocation Mode

### Route

| | Managed route | BYO route |
| --- | --- | --- |
| Who signs the C2PA manifest | Trufo | Your signer (`c2pa-rs`, `c2patool`, etc.) |
| How the watermark is requested | `["watermark", {...}]` action on `/c2pa/sign` | `/bind/*` routes |
| Cloud embedding | `sign_c2pa_cloud()` (inline for small images, or as an asynchronous task for large files) | `bind_watermark()` (`POST /bind/watermark`) |
| Local embedding | `sign_c2pa_local()` with `trufo[local-full]`, or Docker `ghcr.io/trufo-ai/trufo-local:2.4-full` | `bind_reserve()` (`POST /bind/reserve`) + `watermark_media()` with `trufo[local-full]` |
| Completion | Automatic | `bind_commit()` (`POST /bind/commit`) with your signed manifest store |

The `trufo-local` Docker images serve only `/health` and `/c2pa/sign`; they do not serve `/bind/*` or `/content/*`.

### Allocation mode (`wid_allocation_mode`)

| | `per_embed` (default) | `per_ai_system` |
| --- | --- | --- |
| Watermark ID | Unique `wid` per asset | Shared ID of a registered AI system, one per AI involvement mode (AI-generated or AI-modified) |
| Recovery returns | The stored C2PA manifest | Organization and AI system details |
| Manifest storage | Required; opting out of manifest storage returns `400 ManifestStorageRequired` | Compatible with opting out of manifest storage |

Watermark IDs, data processing, and video compute are billed as described in [Watermark Billing](../reference/watermarking-api.md#watermark-billing). To set up an AI system for `per_ai_system`, see [4. AI Labeling and Compliance](4-ai-labeling-compliance.md).

---

## 2. Complete the Prerequisites

1. A Trufo account with MFA ([2. Trufo Account Setup](2-trufo-account-setup.md)). `*-test` keys need no plan or Organization Validation (OV).
2. On production, OV is required for embedding (managed and BYO routes). Recovery-only callers (`/content/recover`) need only an active plan.
3. A plan: **C2PA Signing** for the managed route; **C2PA Signing** or **Watermark API** for the BYO route and for recovery.
4. API keys (see [5. Create API Keys](2-trufo-account-setup.md#5-create-api-keys) in [2. Trufo Account Setup](2-trufo-account-setup.md)):
   - Managed route: `c2pa-sign-test` or `c2pa-sign-prod`.
   - BYO route: `watermark-test` or `watermark-prod`.
   - Recovery: `content-recover-test` or `content-recover-prod`.
   - Local embedding (Python SDK or Docker): `sdk-download`, on both hosts.

Creating an `sdk-download` key requires both accepting the *Trufo Library License* and either an active C2PA Signing or Watermark API plan or test SDK access enabled by [support@trufo.ai](mailto:support@trufo.ai); otherwise it returns `403 NoEligiblePlan`. Local embedding with `trufo[local-full]` requires Linux and Python 3.12+; see [Local Signing (Python SDK)](../topics/signing-local-python.md#requirements).

Check that your formats can be watermarked in [Media Format Support](../reference/media-formats.md).

---

## 3. Set Up the Managed Route

### Test

On `test.api.trufo.ai`, Cloud mode handles images up to 10 MB inline (the `REQUEST` execution mode). The asynchronous `TASK` execution mode runs on production hosts only, so test audio, video, and larger images with Local mode (`sign_c2pa_local_test()` with `trufo[local-full]`).

```python
from pathlib import Path

from trufo import sign_c2pa_cloud_test
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_TEST)

signed_bytes = sign_c2pa_cloud_test(
    api_key,
    Path("photo.jpg").read_bytes(),
    actions=[["watermark", {"effort_policy": "require_if_supported"}]],
)
Path("watermarked.jpg").write_bytes(signed_bytes)
```

Place the `watermark` action last, after any `resize`, `crop`, `trim`, or `transcode` actions. For `per_ai_system`, add an `ai_system` assertion and `{"wid_allocation_mode": "per_ai_system"}`. A full script is in [watermarking.py](../topics/watermarking.py).

### Choose an effort policy

`effort_policy` sets what happens when a file cannot be watermarked: `"require"` (the default) fails the sign; `"require_if_supported"` signs without a watermark only when the MIME type is unsupported, so files of a supported type that hit a per-file restriction (such as CMYK JPEG, HDR content, 1-bit TIFF, or fragmented MP4) still fail; and `"best_effort"` signs without a watermark on any watermarking failure. Each fallback emits a `TrufoServerWarning` ([Non-Fatal Server Warnings](../topics/error-handling.md#non-fatal-server-warnings-trufoserverwarning)); see [`effort_policy`](../topics/watermarking.md#effort_policy).

### Move to production

- **Cloud:** switch to `sign_c2pa_cloud()` with a `c2pa-sign-prod` key. Use `execution_mode=ExecutionMode.TASK` for images over 10 MB and for any watermarking of audio or video ([Cloud Signing](../topics/signing-cloud.md#large-files-audio-and-video-task-via-s3)).
- **Local:** install `trufo[local-full]` after configuring the private package index and call `sign_c2pa_local()`, or run the Docker image `ghcr.io/trufo-ai/trufo-local:2.4-full` (the `2.4` image returns `400 WatermarkNotAvailable`). The Docker images serve the managed route only; `/bind/*` uses the Python SDK. `WatermarkSettings(profile="default" | "fast")` trades video durability for speed, with `"fast"` roughly 5× faster on CPU; see [Local Watermark Settings](../topics/signing-local-python.md#local-watermark-settings) and [Local Signing (Docker)](../topics/signing-local-docker.md).

---

## 4. Set Up the BYO Route

### Embed

Cloud embedding (`/bind/watermark`) or local embedding (`/bind/reserve` + `watermark_media()`), both followed by your signer and `/bind/commit`. `bind_reserve()` returns a `cid` and a `wid_package` (the reserved watermark ID and its expiry), which you pass unchanged to `watermark_media()`:

```python
from pathlib import Path

from trufo import bind_commit, bind_reserve, watermark_media
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.WATERMARK_PROD)


def sign_with_your_c2pa_signer(media: bytes, wid: str) -> bytes:
    """Sign `media` with your own signer and return the raw C2PA manifest store (JUMBF) bytes."""
    raise NotImplementedError


media_bytes = Path("photo.jpg").read_bytes()

# local embedding (trufo[local-full]); for Cloud embedding use
# result = bind_watermark(api_key, media_bytes) and result.media / result.wid / result.cid
reservation = bind_reserve(api_key, "image/jpeg")
marked_bytes = watermark_media(media_bytes, reservation.wid_package)

store_bytes = sign_with_your_c2pa_signer(marked_bytes, wid=reservation.wid)
bind_commit(api_key, reservation.cid, reservation.wid, manifest_bytes=store_bytes)
```

- On the test host, use `bind_watermark_test()`, `bind_reserve_test()`, and `bind_commit_test()` with a `watermark-test` key.
- For images over 10 MB, audio, or video on `/bind/watermark`, pass `execution_mode=ExecutionMode.TASK` and `mime_type=...` (production only). On the test host, use `/bind/reserve` + `watermark_media()` for audio and video.
- `/bind/watermark` bills the embed when it runs, whether or not you commit. `/bind/reserve` bills `per_ai_system` marks (`0.1` per embed) at reserve, and `per_embed` marks (1 new ID, first embed included) at `/bind/commit`.

### Declare the watermark in your manifest

For `per_embed`, add a `c2pa.watermarked.bound` action and a `c2pa.soft-binding` assertion (`alg` `"ai.trufo.pawprint.watermark"`, with one block whose `value` holds the UTF-8 bytes of `wid` as a CBOR byte string (`bstr`), not a text string) to the claim's created assertions. For `per_ai_system`, pass `wid_allocation_mode="per_ai_system"`, `ai_system_id`, and `ai_involvement` to the bind call, and record a `c2pa.watermarked.unbound` action with no `c2pa.soft-binding` assertion; see [What your own signer should declare in the manifest](../topics/watermarking.md#what-your-own-signer-should-declare-in-the-manifest).

### Commit

`bind_commit()` takes the raw manifest store bytes; `POST /bind/commit` takes them base64-encoded in `manifest`. Commit is required for `per_embed` (within 24 hours of embedding or reserving, or 1 hour on the test host) and optional for `per_ai_system`. Retry and error behavior is in [`POST /bind/commit`](../reference/watermarking-api.md#post-bindcommit).

---

## 5. Recover, Verify, and Manage Records

### Recover

```python
from pathlib import Path

from trufo import recover_content
from trufo.util.credentials import TrufoAPIKey, load_api_key

recover_key = load_api_key(TrufoAPIKey.CONTENT_RECOVER_PROD)

result = recover_content(recover_key, Path("stripped.jpg").read_bytes(), parse_manifest_json=True)
if result.detected and result.manifest_bytes:
    Path("recovered.c2pa").write_bytes(result.manifest_bytes)
```

- `recover_content()` defaults to production; pass `trufo_api_url=TRUFO_API_URL_TEST` (from `trufo.api.endpoints`) with a `content-recover-test` key for test-host marks.
- Media is sent inline as base64; there is no `TASK` mode or S3 upload for recovery. For long videos, recover from a shorter representative clip.
- Production calls bill the input bytes even when the call fails with `400 UndecodableMedia`, plus any returned manifest bytes.
- `detected=True` with no `manifest_bytes` is expected for `per_ai_system` marks (read `result.ai_system` and `result.ai_involvement`) and for another organization's inactive `per_embed` records.

### Verify a recovered manifest

Validate `manifest_bytes` together with the recovered media in `c2pa-rs`: the signature, certificate chain, timestamp, and OCSP checks must pass, while hard-binding hash mismatches (such as `assertion.dataHash.mismatch`) are expected on re-encoded files. Then confirm that `result.wid` matches the `value` in the manifest's `c2pa.soft-binding` assertion; the full recipe is in [Validating a Manifest Recovered via Watermark](../topics/verification.md#3-validating-a-manifest-recovered-via-watermark-contentrecover).

### Manage visibility

Every production sign or bind creates a content record. Use `get_content()`, `list_content()`, and `set_content_status()` with a `c2pa-sign-prod` or `watermark-prod` key (production hosts only, no plan required).

```python
from trufo import set_content_status
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.WATERMARK_PROD)

set_content_status(api_key, "inactive", wid="v1....")
```

Setting a `per_embed` record to `"inactive"` stops other organizations' recovery calls from returning its manifest and removes the ID from active-ID billing at the next UTC daily count; your own organization can still recover it. `per_ai_system` records cannot be deactivated per file. See [Content Records](../reference/watermarking-api.md#content-records-content).

---

## Reference

- [Watermarking and Recovery](../topics/watermarking.md) and [watermarking.py](../topics/watermarking.py)
- [Watermarking and Content API](../reference/watermarking-api.md)
- [Verification](../topics/verification.md)
- [Storage Options and Privacy](../topics/storage-options.md)
- [Error Handling, Warnings, and Retries](../topics/error-handling.md)
- [Media Format Support](../reference/media-formats.md)
- [Local Signing (Python SDK)](../topics/signing-local-python.md) and [Local Signing (Docker)](../topics/signing-local-docker.md)
