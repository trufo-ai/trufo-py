# Quickstart: Watermarking

Embed an imperceptible Trufo watermark in your media as part of C2PA signing.

## What This Does

For supported image and audio formats, C2PA signing can embed a **Trufo Pawprint watermark** — an imperceptible signal woven into the pixels or audio samples themselves. The watermark carries a watermark ID issued by Trufo, so information about the content survives even after the C2PA manifest has been stripped (e.g. by re-encoding, screenshots, or metadata-scrubbing pipelines). What the ID resolves to depends on the mark's mode:

- **Provenance** (the default): a unique per-content ID linked to your signing record.
- **Compliance** (🟠 **TEST** — `test.api.trufo.ai` only): your organization's reusable mark declaring the content's AI class (`ai_generated`, `ai_modified`, or `undeclared`).

The signed manifest declares the watermark per the C2PA specification: a `c2pa.watermarked.bound` action plus a `c2pa.soft-binding` assertion with algorithm `ai.trufo.pawprint.watermark`, Trufo's entry in the official C2PA soft-binding algorithm registry.

**Watermarking is off by default.** Include a `["watermark", {...}]` action in `actions` to request it.

## Supported Formats

| Modality | Formats |
| -------- | ------- |
| Image    | JPEG, PNG, WebP, TIFF |
| Audio    | WAV, FLAC, MP3, M4A (`audio/mp4`) |

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

Embed your organization's compliance mark for AI-generated content (🟠 **TEST** — `test.api.trufo.ai` only, so via `sign_c2pa_test`):

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

## Hosted vs Distributed

Watermarking works in both signing modes with the same request shape:

- **Hosted** (`sign_c2pa`, `sign_c2pa_test`, and the S3 variants) — the watermark is embedded on Trufo servers. No extra installation is required.
- **Distributed** (`sign_c2pa_distributed`, `sign_c2pa_distributed_test`) — the watermark is embedded locally by the Trufo engine, so your media never leaves your machine. The watermark ID is issued by the Trufo server during the preprocessing round-trip. Requires the `trufo[local-full]` optional installation (see [README](../../README.md#optional-local-engine)).

**Without the watermark engine** (a `local-sign-only` or legacy `provenance` installation), distributed signing works normally — but a watermark request **always fails immediately** with an install hint (`ImportError`: the trufo-pawprint dependency is required), regardless of `effort_policy`, before anything is sent to the server. The `effort_policy` levels govern what happens when the *installed* engine cannot watermark a particular input; requesting a watermark without the engine installed is refused outright.

Additional notes for distributed (local) watermarking:

- The engine runs on CPU by default; an NVIDIA GPU (CUDA) is used automatically when available.
- File-type detection uses `python-magic`, which requires the `libmagic` system library on Linux and macOS.
- M4A watermarking uses the FFmpeg suite: install `ffmpeg` and `ffprobe` on the PATH, or point the `PAWPRINT_FFMPEG` and `PAWPRINT_FFPROBE` environment variables at the binaries.

## Test vs Production

Production signing issues a unique watermark ID and links it to a permanent signing record. Test signing embeds a watermark from a separate test ID space: IDs are ephemeral, not unique, and no signing record is created. Test-signed watermarks are for integration development only.

See [api_c2pa.md](../api/api_c2pa.md#signing-modes) for the full flow comparison (endpoints, auth, records, billing).

## Reading Watermarks

`recover_content()` decodes a watermark from media and returns the watermark ID with a detection confidence — even after the C2PA manifest has been stripped. It requires an API key with the `c2pa-decode` scope:

```python
from trufo import recover_content
from trufo.util.credentials import TrufoApiKey, load_api_key

decode_key = load_api_key(TrufoApiKey.C2PA_DECODE)

result = recover_content(decode_key, media_bytes)
if result.detected:
    print(result.wid, result.confidence)
```

Decoding is read-only and accepts any parseable image or audio input, not just the encode-supported formats. See [api_c2pa.md](../api/api_c2pa.md#post-contentrecover) for the full schema.

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
