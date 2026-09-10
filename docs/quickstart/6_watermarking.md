# Quickstart: Watermarking

Embed an imperceptible Trufo watermark in your media as part of C2PA signing.

## What This Does

For supported image, audio, and video formats, Trufo can embed a **Trufo Pawprint watermark** — an imperceptible signal woven into the pixels or audio samples themselves. The watermark carries a watermark ID issued by Trufo, so information about the content survives even after the C2PA manifest has been stripped (e.g. by re-encoding, screenshots, or metadata-scrubbing pipelines). What the ID resolves to depends on the mark's mode:

- **Provenance** (the default): a unique per-content ID linked to your signing record.
- **Compliance** (🟠 **test only**): your organization's reusable mark declaring the content's AI class (`ai_generated`, `ai_modified`, or `undeclared`).

There are two ways to get a watermark, sharing both modes:

- **As part of C2PA signing** — a `["watermark", {...}]` action in a `sign_c2pa*` call; Trufo embeds the mark and signs the manifest in one step. **Off by default** — the action requests it.
- **Standalone binding** — `bind_watermark()` embeds the mark and *you* sign the media with your own certificate; see [Binding Without Trufo Signing](#binding-without-trufo-signing-bind).

Either way, the signed manifest declares the watermark per the C2PA specification: a `c2pa.watermarked.bound` action plus a `c2pa.soft-binding` assertion with algorithm `ai.trufo.pawprint.watermark`, Trufo's entry in the official C2PA soft-binding algorithm registry — Trufo writes these for you in the signing flow, while bind requires your manifest to carry them.

## Supported Formats

| Modality | Formats |
| -------- | ------- |
| Image    | JPEG, PNG, WebP, TIFF |
| Audio    | WAV, FLAC, MP3, M4A (`audio/mp4`) |
| Video    | MP4 (`video/mp4`; H.264/HEVC, 8-bit) |

For video, the same watermark ID is embedded in **every stream**: each frame of the video stream carries the full ID through the image watermark, and every audio stream carries it through the audio watermark — so the ID survives in an extracted audio track or a single surviving frame.

Signing formats outside this list succeeds normally; the watermark is simply not embedded, which the `effort_policy` setting below lets you treat as an error or a warning.

## The `watermark` Action

A `["watermark", {...}]` entry in `actions` requests watermarking; at most one is allowed per request. Its parameters:

- `mode` (a `WatermarkMode` value): `"provenance"` (default) or `"compliance"`.
- `ai_compliance_label` (an `AiComplianceLabel` value): the declared AI class. Required in compliance mode, rejected otherwise.
- `effort_policy` (a `WatermarkEffort` value): what happens when the watermark cannot be applied. `effort` is a deprecated alias — it still works, with a warning; providing both keys is an error.

| `effort_policy` | Unsupported format | Runtime failure (e.g. missing library) |
| --------------- | ------------------ | -------------------------------------- |
| `"require"` (default for a bare action) | error | error |
| `"require_if_supported"` | signs unwatermarked, with a warning | error |
| `"best_effort"` | signs unwatermarked, with a warning | signs unwatermarked, with a warning |

### Examples

Watermark, failing the sign if it cannot be embedded:

```python
from trufo import sign_c2pa
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_PROD)

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

Embed your organization's compliance mark for AI-generated content (🟠 **test only**, so via `sign_c2pa_test`):

```python
signed_bytes = sign_c2pa_test(
    api_key,
    media_bytes,
    actions=[
        ["watermark", {"mode": "compliance", "ai_compliance_label": "ai_generated"}],
    ],
)
```

The `trufo.c2pa` enums `WatermarkEffort`, `WatermarkMode`, and `AiComplianceLabel` hold the accepted values.

## Routes

Four routes produce a signed, watermarked asset. They differ in who embeds the mark (*processing*) and who signs the manifest (*signing*), and the names combine the two: **tpts** = trufo-processing + trufo-signing, **lpts** = local-processing + trufo-signing, **tpls** = trufo-processing + local-signing, **lpls** = local-processing + local-signing. tpts and lpts are the hosted and distributed C2PA Signing products; tpls and lpls are the standalone Watermark APIs.

| Route | Step 1 | Step 2 | Step 3 | Step 4 | trufo-py |
| ----- | ------ | ------ | ------ | ------ | -------- |
| **tpts** | `POST /c2pa/sign`: Trufo embeds the mark (when the `watermark` action is present) and signs; the record is complete | | | | `sign_c2pa` |
| **lpts** | SDK-internal protocol: Trufo reserves the watermark ID and opens the record | you embed locally (Trufo engine) and build the manifest | Trufo signs the claim | Trufo stamps the ID and stores the manifest | `sign_c2pa_distributed` runs all four |
| **tpls** | `POST /bind/watermark`: Trufo embeds the mark, reserves the ID, opens the record, returns the marked media | you sign with your own certificate | | `POST /bind/commit`: Trufo checks the manifest declares the ID, stamps, stores or refers | `bind_watermark`, then `bind_commit` |
| **lpls** | `POST /bind/reserve`: Trufo reserves the ID and opens the record for a MIME type | you embed locally (Trufo engine) | you sign with your own certificate | `POST /bind/commit`, as above | `bind_reserve`, `watermark_media`, then `bind_commit` |

Whoever embeds needs the engine: the local routes require the `trufo[local-full]` installation (see [README](../../README.md#optional-local-engine)); the Trufo-processing routes need nothing beyond the API. Whoever signs needs a certificate: the Trufo-signing routes use Trufo's; the local-signing routes use yours, and the manifest you sign must declare the mark (a `c2pa.soft-binding` assertion with algorithm `ai.trufo.pawprint.watermark` and the watermark ID as its block value, paired with a `c2pa.watermarked.bound` action) — Trufo writes these for you on the Trufo-signing routes.

Every route except tpts ends in a commit, because the record cannot be completed until the manifest exists; the mark resolves publicly only once it is committed, so complete the flow before publishing a marked asset.

**Without the watermark engine** (a `local-sign-only` or legacy `provenance` installation), lpts signing works normally — but a watermark request **always fails immediately** with an install hint (`ImportError`: the trufo-pawprint dependency is required), regardless of `effort_policy`, before anything is sent to the server. The `effort_policy` levels govern what happens when the *installed* engine cannot watermark a particular input; requesting a watermark without the engine installed is refused outright.

Additional notes for local embedding:

- The engine runs on CPU by default; an NVIDIA GPU (CUDA) is used automatically when available.
- File-type detection uses `python-magic`, which requires the `libmagic` system library on Linux and macOS.
- M4A watermarking uses the FFmpeg suite: install `ffmpeg` and `ffprobe` on the PATH, or point the `PAWPRINT_FFMPEG` and `PAWPRINT_FFPROBE` environment variables at the binaries.

## Binding Without Trufo Signing (tpls and lpls)

Requires an API key with the `watermark-prod` scope, an active C2PA Signing or Watermark API plan, and completed Organization Validation (`watermark-test` on the test host, where nothing is billed and no validation is needed). Store it with `trufo set-api-key watermark-prod <KEY>` and load it with `load_api_key(TrufoApiKey.WATERMARK_PROD)`. Production bills each bound asset as one watermark encode plus the bytes processed, and every committed record accrues soft-binding resolution maintenance (the watermark-to-manifest link kept for C2PA soft-binding resolution) per ID per day — see [billing](../api/api_c2pa.md#standalone-binding).

If you sign C2PA manifests yourself (your own certificate and signing pipeline), bind gives you a Trufo watermark without handing Trufo the signature step. On the **tpls** route Trufo embeds the mark:

```python
from trufo import bind_watermark, bind_commit
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.WATERMARK_PROD)

# 1. Trufo embeds the mark and opens a record
result = bind_watermark(api_key, media_bytes)

# 2. sign result.media with YOUR certificate; the manifest must declare the
#    mark: a c2pa.soft-binding assertion (alg "ai.trufo.pawprint.watermark",
#    value = result.wid) paired with a c2pa.watermarked.bound action
store_bytes = my_signer(result.media, wid=result.wid)  # the C2PA manifest store

# 3. the commit verifies the declaration and completes the record
bind_commit(api_key, result.cid, result.wid, manifest_bytes=store_bytes)
```

On the **lpls** route you embed locally with the engine (`trufo[local-full]`):

```python
from trufo import bind_reserve, watermark_media, bind_commit

reservation = bind_reserve(api_key, "image/jpeg")          # 1. Trufo issues the ID
marked = watermark_media(media_bytes, reservation.wid_package)  # 2. you embed
store_bytes = my_signer(marked, wid=reservation.wid)      # 3. you sign
bind_commit(api_key, reservation.cid, reservation.wid, manifest_bytes=store_bytes)  # 4.
```

The commit's manifest source is one of: `manifest_bytes=` (the store itself, what validators fetch), `signed_media_bytes=` (the signed file; the store is read out locally, which needs `trufo[local-sign-only]`), or `manifest_id=` with `manifest_endpoint=` when the manifest lives in your own C2PA manifest store and Trufo should only record its id. Add `manifest_endpoint=` to any form to have Trufo refer validators to your store instead of hosting the manifest:

```python
bind_commit(api_key, result.cid, result.wid, manifest_bytes=store_bytes,
            manifest_endpoint="https://manifests.example.com/c2pa")
```

The commit fails with a 400 — and the record stays incomplete — until the manifest declares the mark correctly; your certificate itself is not judged, only the declaration. A reservation lasts 24 hours (1 hour on the test host); an uncommitted mark never resolves. Compliance mode (🟠 **test only**) is a single call with nothing to commit:

```python
result = bind_watermark_test(
    api_key, media_bytes, mode="compliance", ai_compliance_label="ai_generated"
)
```

Bind has no `effort_policy`: the watermark is always required, and an unsupported format is an error. See the [API reference](../api/api_c2pa.md#standalone-binding) for schemas.

## Managing Your Marks

Every production sign or bind creates a content record, and each committed
record accrues soft-binding resolution maintenance for as long as Trufo keeps
its mark resolvable. Look records up by the watermark ID a decode returns, the
manifest ID, or the record id, and switch them off and on:

```python
from trufo import get_content, list_content, set_content_status

record = get_content(api_key, wid="v1.001a1b2c3d4")     # the record behind a decoded mark
set_content_status(api_key, "inactive", wid=record.wid)  # stops resolving and accruing

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

An inactive record no longer resolves for validators and stops counting from
the next UTC day. See the [API reference](../api/api_c2pa.md#content-records).

## Test vs Production

Production signing issues a unique watermark ID and links it to a permanent signing record. Test signing embeds a watermark from a separate test ID space: IDs are ephemeral, not unique, and test records are neither resolvable nor billed. Test-signed watermarks are for integration development only.

See [api_c2pa.md](../api/api_c2pa.md#signing-modes) for the full flow comparison (endpoints, auth, records, billing).

## Reading Watermarks

`recover_content()` decodes a watermark from media — even after the C2PA manifest has been stripped — and returns what the mark resolves to: for a provenance mark, the watermark ID, confidence, and the stored C2PA manifest store (`manifest_bytes`) when one has been captured; for a compliance mark, the declared AI class. `oid` is set when the mark belongs to your own organization. It requires an API key with the `content-recover-test` scope (test host) or `content-recover-prod` scope (production hosts); each key works only against its own host tier.

`recover_content()` defaults to the production host, so test-host recovery — which is what pairs with the test signing flows on this page — must pass the test host explicitly:

```python
from trufo import recover_content
from trufo.api.endpoints import TRUFO_API_URL_TEST
from trufo.util.credentials import TrufoApiKey, load_api_key

recover_key = load_api_key(TrufoApiKey.CONTENT_RECOVER_TEST)

result = recover_content(recover_key, media_bytes, trufo_api_url=TRUFO_API_URL_TEST)
if result.detected:
    print(result.wid, result.confidence, result.ai_compliance_label)
```

In production, use a `content-recover-prod` key and omit `trufo_api_url`.

`manifest_bytes` is the signed manifest store as captured. Per the C2PA specification a manifest obtained through soft-binding recovery must be validated like any other, so validate it against your own copy of the media (for example with `trufo-provenance` or c2patool) before relying on it. If you have no local C2PA engine and only need to read the manifest's contents, pass `parse_manifest_json=True` to also receive `manifest_json`, the server's parse; it is not a validation result.

Decoding is read-only and accepts any parseable image, video, or audio input, not just the encode-supported formats; an input the engine cannot decode returns a 400 `UndecodableMedia` error. In production each call bills one watermark decode plus the bytes processed (an undecodable input bills the bytes only). See [api_c2pa.md](../api/api_c2pa.md#post-contentrecover) for the full schema.

## Troubleshooting

**`Watermarking is not supported for <mime> media.`**

You requested a watermark with `effort_policy: require` on a format outside the supported table above. Either transcode first, or use `require_if_supported` / `best_effort` to sign such formats unwatermarked.

**`Watermarking failed: <engine error>`**

The embed step failed at runtime. Under `require` and `require_if_supported` this fails the sign; under `best_effort` it is reported as a warning and the content is signed without a watermark.

**A sign succeeded — was it actually watermarked?**

Under `require_if_supported` and `best_effort` a skipped watermark is a warning, not an error. Catch `TrufoServerWarning` to detect it — see [`warnings`](../api/api_c2pa.md#response-warnings) in the response reference.

**`At most one watermark action is allowed per request.`**

Combine your watermark preferences into a single `["watermark", {...}]` entry.

**`ImportError` mentioning trufo-pawprint or the local engine**

Distributed watermarking requires the full local engine. Install `trufo[local-full]` (see [README](../../README.md#optional-local-engine)).

---

## Reference

- Authentication setup: [0_setup.md](0_setup.md)
- C2PA signing API reference: [../api/api_c2pa.md](../api/api_c2pa.md)
- Distributed signing quickstart: [2_c2pa_signing.md](2_c2pa_signing.md)
- Complete runnable example: [6_watermarking.py](6_watermarking.py)
