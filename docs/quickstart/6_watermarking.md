# Quickstart: Watermarking

Embed an imperceptible Trufo watermark in your media as part of C2PA signing.

## What This Does

For supported image, audio, and video formats, Trufo can embed a **Trufo Pawprint watermark** — an imperceptible signal woven into the pixels or audio samples themselves. The watermark carries a watermark ID issued by Trufo, so information about the content survives even after the C2PA manifest has been stripped (e.g. by re-encoding, screenshots, or metadata-scrubbing pipelines). What the ID resolves to depends on how it is allocated:

- **Per embed** (the default): a new watermark ID for each file, linked to the file's content record and C2PA manifest (a C2PA soft binding).
- **Per AI system**: the watermark ID of a [registered AI system](3_ai_labeling.md#step-2--register-an-ai-system) for the type of AI involvement.

For companies seeking minimal compliance with the EU AI Act Article 50(2), per-AI-system watermarking embeds a single watermark ID in all content a registered AI system generates. The AI system can be identified, but individual content provenance records (e.g. C2PA soft-binding) cannot.

There are two ways to get either watermark:

- **As part of C2PA signing** — a `["watermark", {...}]` action in a `sign_c2pa*` call; Trufo embeds the mark and signs the manifest in one step. **Off by default** — the action requests it.
- **Standalone binding** — `bind_watermark()` embeds the mark and *you* sign the media with your own certificate; see [Binding Without Trufo Signing](#binding-without-trufo-signing).

Either way, the signed manifest declares a per-embed mark per the C2PA specification: a `c2pa.watermarked.bound` action plus a `c2pa.soft-binding` assertion with algorithm `ai.trufo.pawprint.watermark`, Trufo's entry in the official C2PA soft-binding algorithm registry. Trufo writes these when it signs; on a bind, your manifest should carry them. A per-AI-system mark is not a soft binding.

## Supported Formats

See [Media format support](../api/media_format_support.md) for embedding and
recovery eligibility, image restrictions, audio/video codecs, and track layouts.

## Execution Mode

In Cloud mode, REQUEST execution is limited to images up to 10 MB (10,000,000 bytes).
For larger images, audio, or video, explicitly select `ExecutionMode.TASK` and
pass `mime_type` to `sign_c2pa()` or `bind_watermark()`. The SDK uploads, submits,
polls, and downloads synchronously. `submit_bind_watermark()` accepts an existing
Trufo upload reference and returns immediately with a task ID. A completed
per-embed watermark task still requires signing and `bind_commit()`; it does not
commit the content record itself. Test endpoints accept REQUEST only.

## The `watermark` Action

A `["watermark", {...}]` entry in `actions` requests watermarking; at most one is allowed per request. Its parameters:

- `wid_allocation_mode` (a `WatermarkIDAllocationMode` value): `"per_embed"` (default) or `"per_ai_system"`, which needs an `ai_system` entry in the same request ([AI labeling](3_ai_labeling.md)). `"per_asset"` raises `NotImplementedError`.
- `effort_policy` (a `WatermarkEffort` value): what happens when the watermark cannot be applied. `effort` is a deprecated alias — it still works, with a warning; providing both keys is an error.

| `effort_policy` | Unsupported format | Runtime failure (e.g. missing library) |
| --------------- | ------------------ | -------------------------------------- |
| `"require"` (default for a bare action) | error | error |
| `"require_if_supported"` | signs unwatermarked, with a warning | error |
| `"best_effort"` | signs unwatermarked, with a warning | signs unwatermarked, with a warning |

For what watermarking bills, see [watermark billing](../api/api_c2pa.md#watermark-billing).

<!-- TODO(sunset-2027-01-31): the deprecated mode paragraph goes; successor wid_allocation_mode -->

The `mode` parameter (`WatermarkMode`) is deprecated: until 2027-01-31T23:59:00+00:00, `"provenance"` means `"per_embed"`, with a warning, and from that instant `mode` is refused (400). trufo 2.1 and earlier send `mode` on every `/bind/watermark` call (`bind_watermark`, `submit_bind_watermark`, `bind_watermark_test`; not `bind_reserve`) and do not show the warning, so upgrade to trufo 2.2.0 before then. Over HTTP, drop `"mode": "provenance"` (`per_embed` is the default). The notices and refusals are listed under [`watermark`](../api/api_c2pa.md#watermark).

### Examples

Watermark, failing the sign if it cannot be embedded:

```python
from trufo import sign_c2pa
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_PROD)

signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    actions=[
        ["watermark", {}],  # bare action == {"effort_policy": "require"}
    ],
)
```

Watermark whenever the format supports it, treating unsupported formats as fine — useful when one pipeline handles mixed media:

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    actions=[
        ["watermark", {"effort_policy": "require_if_supported"}],
    ],
)
```

Try to watermark, but never fail the sign over it:

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    actions=[
        ["watermark", {"effort_policy": "best_effort"}],
    ],
)
```

Watermark per AI system, in a request that names the AI system ([AI labeling](3_ai_labeling.md)):

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    assertions=[
        ["ai_system", {"ai_system_id": ai_system_id, "ai_involvement": "ai_generated"}],
    ],
    actions=[
        ["watermark", {"wid_allocation_mode": "per_ai_system"}],
    ],
)
```

The `trufo.c2pa` enums `WatermarkIDAllocationMode` and `WatermarkEffort` define the values.

## Routes

Four routes produce a signed, watermarked asset. They differ in where the mark is embedded and who signs the manifest: on the **Cloud** routes Trufo embeds the mark, and on the **Local** routes you embed it on your machine with Trufo's engine; on the **C2PA Signing** routes Trufo signs, and on the **Watermarking** routes you sign with your own certificate.

| Route | Step 1 | Step 2 | Step 3 | Step 4 | trufo-py |
| ----- | ------ | ------ | ------ | ------ | -------- |
| **C2PA Signing, Cloud** | `POST /c2pa/sign`: Trufo embeds the mark (when the `watermark` action is present) and signs; the record is complete | | | | `sign_c2pa` |
| **C2PA Signing, Local** | Trufo reserves the watermark ID and opens the record | you embed locally (Trufo engine) and build the manifest | Trufo signs the claim | Trufo stamps the ID and stores the manifest | `sign_c2pa_distributed` runs all four |
| **Watermarking, Cloud** | `POST /bind/watermark`: Trufo embeds the mark, reserves the ID, opens the record, returns the marked media | you sign with your own certificate | | `POST /bind/commit`: Trufo checks the manifest declares the ID, stamps and stores | `bind_watermark`, then `bind_commit` |
| **Watermarking, Local** | `POST /bind/reserve`: Trufo reserves the ID and opens the record for a MIME type | you embed locally (Trufo engine) | you sign with your own certificate | `POST /bind/commit`, as above | `bind_reserve`, `watermark_media`, then `bind_commit` |

Whoever embeds needs the engine: `trufo[local-full]` ([Local mode with the Python SDK](../local/python.md)) on either Local route, or the [full Docker image](../local/docker.md#choose-an-image) on C2PA Signing, Local (neither Docker image has the `/bind` routes); the Cloud routes need only the API. Whoever signs needs a certificate: Trufo's on the C2PA Signing routes, yours on the Watermarking routes, where your manifest should [declare the mark](../api/api_c2pa.md#post-bindcommit).

For a per-embed mark, every route except C2PA Signing, Cloud ends in a commit, since the record needs the manifest; the mark resolves publicly only once committed, so complete the flow before publishing a marked asset. A per-AI-system bind's commit is optional, since the AI system's ID resolves from its registration.

**Without the watermark engine** (a `local-sign-only` or legacy `provenance` installation), C2PA Signing in Local mode works normally — but a watermark request **always fails immediately** with an install hint (`ImportError`: the trufo-pawprint dependency is required), regardless of `effort_policy`, before anything is sent to the server. The `effort_policy` levels govern what happens when the *installed* engine cannot watermark a particular input; requesting a watermark without the engine installed is refused outright.

Additional notes for local embedding:

- An NVIDIA GPU (CUDA) is recommended and used automatically when available; otherwise the engine uses CPU. The full Docker image runs on CPU only.
- Watermarking M4A, raw AAC (ADTS), MP4 or MOV needs FFmpeg, and HEIC/HEIF or AVIF needs libheif's `heif-enc`. On Debian or Ubuntu: `apt install ffmpeg libheif-examples libheif-plugin-x265 libheif-plugin-aomenc`. The full Docker image includes both.

## Binding Without Trufo Signing

Requires an API key with the `watermark-prod` scope, an active C2PA Signing or Watermark API plan, and completed Organization Validation (`watermark-test` on the test host, where no validation is needed). Store it with `trufo set-api-key watermark-prod <KEY>` and load it with `load_api_key(TrufoAPIKey.WATERMARK_PROD)`. For production billing, see [watermark billing](../api/api_c2pa.md#watermark-billing).

If you sign C2PA manifests yourself (your own certificate and signing pipeline), bind gives you a Trufo watermark without handing Trufo the signature step. On the **Watermarking, Cloud** route Trufo embeds the mark:

```python
from trufo import bind_watermark, bind_commit
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.WATERMARK_PROD)

# 1. Trufo embeds the mark and opens a record
result = bind_watermark(api_key, media_bytes)

# 2. sign result.media with YOUR certificate; the manifest must declare the
#    mark: a c2pa.soft-binding assertion (alg "ai.trufo.pawprint.watermark",
#    value = result.wid) paired with a c2pa.watermarked.bound action
store_bytes = your_signer(result.media, wid=result.wid)  # the C2PA manifest store

# 3. the commit completes the record (and warns if the manifest does not declare the mark)
bind_commit(api_key, result.cid, result.wid, manifest_bytes=store_bytes)
```

On the **Watermarking, Local** route you embed locally with the engine (`trufo[local-full]`):

```python
from trufo import bind_reserve, watermark_media, bind_commit

reservation = bind_reserve(api_key, "image/jpeg")          # 1. Trufo issues the ID
marked = watermark_media(media_bytes, reservation.wid_package)  # 2. you embed
store_bytes = your_signer(marked, wid=reservation.wid)    # 3. you sign
bind_commit(api_key, reservation.cid, reservation.wid, manifest_bytes=store_bytes)  # 4.
```

If you have `trufo[local-sign-only]` or `trufo[local-full]` installed, you can also directly pass in the media file `signed_media_bytes=` instead of manifest `manifest_bytes=`.

A per-AI-system bind embeds your [AI system's](3_ai_labeling.md#step-2--register-an-ai-system) watermark ID instead of a new one. Pass `wid_allocation_mode="per_ai_system"`, `ai_system_id` and `ai_involvement`:

```python
result = bind_watermark(api_key, media_bytes, wid_allocation_mode="per_ai_system",
                        ai_system_id=ai_system_id, ai_involvement="ai_generated")
# result.wid is the AI system's watermark ID; sign result.media with YOUR certificate
```

On the **Watermarking, Local** route, pass the same arguments to `bind_reserve()`:

```python
reservation = bind_reserve(api_key, "image/jpeg", wid_allocation_mode="per_ai_system",
                           ai_system_id=ai_system_id, ai_involvement="ai_generated")
marked = watermark_media(media_bytes, reservation.wid_package)
store_bytes = your_signer(marked)  # the C2PA manifest store
bind_commit(api_key, reservation.cid, reservation.wid, manifest_bytes=store_bytes)  # optional
```

Declare the mark in your manifest the way Trufo-signed manifests do: a `c2pa.watermarked.unbound` action.

### Custom Manifest Storage

To host manifests in your own C2PA manifest store, contact support@trufo.ai.

## Managing Your Marks

Every production sign or bind creates a content record. A per-embed mark's
watermark ID is an active ID, [billed](../api/api_c2pa.md#watermark-billing)
from its committed record until you deactivate it. Look records up by the
watermark ID a decode returns, the manifest ID, or the record id, and switch
them off and on:

```python
from trufo import get_content, list_content, set_content_status

record = get_content(api_key, wid="v1.001a1b2c3d4")     # the record behind a decoded mark
set_content_status(api_key, "inactive", wid=record.wid)  # stops resolving and counting

page = list_content(api_key, status="active", origin="bind_hosted",
                    created_after="2026-04-01T00:00:00Z")
while True:
    for item in page.items:
        print(item.cid, item.wid, item.create_ts)
    if page.next_cursor is None:
        break
    page = list_content(api_key, status="active", origin="bind_hosted",
                        created_after="2026-04-01T00:00:00Z", cursor=page.next_cursor)

set_content_status(api_key, "active", cid=record.cid)    # restores it
```

An inactive record no longer resolves for validators and leaves the daily
active-ID count. A per-AI-system embed's record carries the AI system's
watermark ID as `ai_system_wid` instead of `wid`, and cannot be switched off.
The AI system's IDs keep resolving even while the AI system is
[inactive](../api/api_c2pa.md#post-ai-systemstatus);
[watermark billing](../api/api_c2pa.md#watermark-billing) says when they count as
active IDs. See the [API reference](../api/api_c2pa.md#content-records).

## Test vs Production

In production, a per-embed mark carries a new, unique watermark ID linked to a permanent record, and a per-AI-system mark carries the AI system's permanent ID for its type of AI involvement. On the test host, per-embed marks use a separate test ID space: the IDs are ephemeral and may be reissued, and their records resolve on the test host only. Per-AI-system test marks use the AI system's permanent test IDs. Test keys embed on the test host only, for integration development.

See [api_c2pa.md](../api/api_c2pa.md#signing-modes) for the full flow comparison (endpoints, auth, records) and [watermark billing](../api/api_c2pa.md#watermark-billing).

## Reading Watermarks

`recover_content()` decodes a watermark from media — even after the C2PA manifest has been stripped — and returns the watermark ID, the detection confidence, its `wid_allocation_mode`, and what the mark resolves to:

- A per-embed mark: the stored C2PA manifest store (`manifest_bytes`) when one has been captured.
- A per-AI-system mark: `ai_involvement` and `ai_system`, the AI system's public information (name, version, model disclosure and, while your Organization Validation is active, your organization's validated legal name), which anyone with a recover key can see; your own organization also sees its `ai_system_id` and `status`.

When the mark belongs to your own organization, `oid` is set and, for a per-embed mark, the result's `status` says whether its watermark ID is `active` or `inactive` ([content records](../api/api_c2pa.md#content-records)). `recover_content()` requires an API key with the `content-recover-test` scope (test host) or `content-recover-prod` scope (production hosts); each key works only against its own host tier.

`recover_content()` defaults to the production host, so test-host recovery — which is what pairs with the test signing flows on this page — must pass the test host explicitly:

```python
from trufo import recover_content
from trufo.api.endpoints import TRUFO_API_URL_TEST
from trufo.util.credentials import TrufoAPIKey, load_api_key

recover_key = load_api_key(TrufoAPIKey.CONTENT_RECOVER_TEST)

result = recover_content(recover_key, media_bytes, trufo_api_url=TRUFO_API_URL_TEST)
if result.detected:
    print(result.wid, result.confidence)
```

In production, use a `content-recover-prod` key and omit `trufo_api_url`.

`manifest_bytes` is the signed manifest store as captured. Per the C2PA specification a manifest obtained through soft-binding recovery must be validated like any other, so validate it against your own copy of the media (for example with `trufo-provenance` or c2patool) before relying on it. If you have no local C2PA engine and only need to read the manifest's contents, pass `parse_manifest_json=True` to also receive `manifest_json`, the server's parse; it is not a validation result.

Decoding is read-only; eligible inputs are listed under WM decode in
[Media format support](../api/media_format_support.md). In production each call
bills the bytes processed. See [api_c2pa.md](../api/api_c2pa.md#post-contentrecover)
for the full schema and errors.

## Troubleshooting

**`Watermarking is not supported for <mime> media.`**

The input does not meet the [watermark format policy](../api/media_format_support.md).
Convert it to a supported format, or use `require_if_supported` / `best_effort`
to permit signing without a watermark. The input must still meet the C2PA
generation policy.

**`Watermarking failed: <engine error>`**

The embed step failed at runtime. Under `require` and `require_if_supported` this fails the sign; under `best_effort` it is reported as a warning and the content is signed without a watermark.

**A sign succeeded — was it actually watermarked?**

Under `require_if_supported` and `best_effort` a skipped watermark is a warning, not an error. Catch `UserWarning` to detect it (in Cloud mode it arrives as its subclass `TrufoServerWarning`) — see [`warnings`](../api/api_c2pa.md#response-warnings) in the response reference.

**`At most one watermark action is allowed per request.`**

Combine your watermark preferences into a single `["watermark", {...}]` entry.

**`The watermark's wid_allocation_mode 'per_ai_system' requires an 'ai_system' assertion.`**

Add an `ai_system` entry naming your registered AI system to `assertions` ([AI labeling](3_ai_labeling.md)); its `ai_involvement` selects the AI system's watermark ID.

**`AISystemInactive: AI system '<ai_system_id>' is inactive. Use an active AI system (see /ai-system/list).`**

Use an active AI system, or reactivate this one with [`/ai-system/status`](../api/api_c2pa.md#post-ai-systemstatus). Content already marked with it keeps resolving.

<!-- TODO(sunset-2027-01-31): the deprecated-mode entry (warning and UnsupportedParameter) and the not-both entry below go, and the 501 entry drops its compliance text; successor wid_allocation_mode -->

**`Per-asset watermark ID allocation is not supported.` or `Compliance watermarking is not supported.`**

The SDK raises these as `NotImplementedError` before sending; over HTTP, the API returns them with a 501. Use `wid_allocation_mode` `"per_embed"` or `"per_ai_system"`.

**A warning that the watermark `mode` parameter is deprecated, or `UnsupportedParameter: the watermark 'mode' parameter is no longer supported (expired 2027-01-31T23:59:00+00:00). Please use 'wid_allocation_mode'.`**

Remove `mode` (`per_embed` is the default), or upgrade to trufo 2.2.0 and use `wid_allocation_mode`. trufo 2.1 and earlier refuse `wid_allocation_mode` in `sign_c2pa` before sending, and send `mode` on every `/bind/watermark` call, so binds from them need the upgrade.

**`Provide the watermark 'wid_allocation_mode' parameter or the deprecated 'mode', not both.`**

Remove `mode`.

**`ImportError` mentioning trufo-pawprint or the local engine**

Embedding a watermark locally needs `trufo[local-full]` (C2PA Signing, Local or Watermarking, Local) or the full Docker image (C2PA Signing, Local only); see [Local mode with the Python SDK](../local/python.md).

**`400 WatermarkNotAvailable` from the Docker image**

The signing-only image signs without watermarking; see [Choose an Image](../local/docker.md#choose-an-image). To embed a watermark while signing, use the full image (`2.3-full`), Cloud mode or `trufo[local-full]`.

---

For local embedding profiles and CPU optimization, see
[Local Watermark Settings](../local/python.md#local-watermark-settings). These
settings do not request watermarking by themselves.

## Reference

- Authentication setup: [0_setup.md](0_setup.md)
- C2PA signing API reference: [../api/api_c2pa.md](../api/api_c2pa.md)
- C2PA signing quickstart: [2_c2pa_signing.md](2_c2pa_signing.md)
- Local mode with the Python SDK: [../local/python.md](../local/python.md)
- Complete runnable example: [6_watermarking.py](6_watermarking.py)
