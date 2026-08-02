# Quickstart: Watermarking

Embed an imperceptible Trufo watermark in your media as part of C2PA signing.

## What This Does

For supported image and audio formats, C2PA signing can embed a **Trufo Pawprint watermark** — an imperceptible signal woven into the pixels or audio samples themselves. The watermark carries a unique watermark ID issued by Trufo and linked to your signing record, so the provenance of the content can be recovered even after the C2PA manifest has been stripped (e.g. by re-encoding, screenshots, or metadata-scrubbing pipelines).

The signed manifest declares the watermark per the C2PA specification: a `c2pa.watermarked.bound` action plus a `c2pa.soft-binding` assertion with algorithm `ai.trufo.pawprint.watermark`, Trufo's entry in the official C2PA soft-binding algorithm registry.

**Watermarking is off by default.** Include a `["watermark", {...}]` action in `actions` to request it.

## Supported Formats

| Modality | Formats |
| -------- | ------- |
| Image    | JPEG, PNG, WebP, TIFF |
| Audio    | WAV, FLAC, MP3, M4A (`audio/mp4`) |

Other signable formats (e.g. PDF, video, SVG) cannot currently carry a watermark. Support will expand over time.

## The `watermark` Action

A `["watermark", {...}]` entry in `actions` requests watermarking; at most one is allowed per request. Its `effort` parameter (a `WatermarkEffort` value) sets what happens when the watermark cannot be applied:

| `effort` | Unsupported format | Runtime failure (e.g. missing library) |
| -------- | ------------------ | -------------------------------------- |
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
        ["watermark", {}],  # bare action == {"effort": "require"}
    ],
)
```

Watermark whenever the format supports it, treating unsupported formats as fine — useful when one pipeline handles mixed media:

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    actions=[
        ["watermark", {"effort": "require_if_supported"}],
    ],
)
```

Try to watermark, but never fail the sign over it:

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    actions=[
        ["watermark", {"effort": "best_effort"}],
    ],
)
```

The `trufo.c2pa.WatermarkEffort` enum holds the three values.

## Hosted vs Distributed

Watermarking works in both signing modes with the same request shape:

- **Hosted** (`sign_c2pa`, `sign_c2pa_test`, and the S3 variants) — the watermark is embedded on Trufo servers. No extra installation is required.
- **Distributed** (`sign_c2pa_distributed`, `sign_c2pa_distributed_test`) — the watermark is embedded locally by the Trufo engine, so your media never leaves your machine. The watermark ID is issued by the Trufo server during the preprocessing round-trip. Requires the `trufo[local]` optional installation (see [README](../../README.md#optional-local-engine)); a `provenance`-only installation can still sign, but a watermark request fails with an install hint (or a warning, under `best_effort`).

Additional notes for distributed (local) watermarking:

- The engine runs on CPU by default; an NVIDIA GPU (CUDA) is used automatically when available.
- File-type detection uses `python-magic`, which requires the `libmagic` system library on Linux and macOS.
- M4A watermarking uses the FFmpeg suite: install `ffmpeg` and `ffprobe` on the PATH, or point the `PAWPRINT_FFMPEG` and `PAWPRINT_FFPROBE` environment variables at the binaries.

## Test vs Production

Production signing issues a unique watermark ID and links it to a permanent signing record. Test signing embeds a watermark from a separate test ID space: IDs are ephemeral, not unique, and no signing record is created. Test-signed watermarks are for integration development only.

See [api_c2pa.md](../api/api_c2pa.md#signing-flows) for the full flow comparison (endpoints, auth, records, billing).

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

You requested a watermark with `effort: require` on a format outside the supported table above. Either transcode first, or use `require_if_supported` / `best_effort` to sign such formats unwatermarked.

**`Watermarking failed: <engine error>`**

The embed step failed at runtime. Under `require` and `require_if_supported` this fails the sign; under `best_effort` it is reported as a warning and the content is signed without a watermark.

**`At most one watermark action is allowed per request.`**

Combine your watermark preferences into a single `["watermark", {...}]` entry.

**`ImportError` mentioning the local engine**

Distributed watermarking requires the local engine. Install `trufo[local]` (see [README](../../README.md#optional-local-engine)).

---

## Reference

- Authentication setup: [0_auth.md](0_auth.md)
- C2PA signing API reference: [../api/api_c2pa.md](../api/api_c2pa.md)
- Distributed signing quickstart: [4_distributed_signing.md](4_distributed_signing.md)
