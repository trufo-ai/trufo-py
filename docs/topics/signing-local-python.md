# Local Signing (Python SDK)

`sign_c2pa_local()` runs C2PA signing inside your own Linux Python process:

- **Your original media file stays on your machine.**
- Trufo's local engine (`trufo-provenance`) builds the manifest, runs any media actions, and embeds any watermark locally.
- Trufo receives the signing instructions and the claim to sign, signs the claim with Trufo's certificate, and receives the finished manifest — storing it unless you pass `skip_manifest_storage=True`.

For non-Python stacks or non-Linux hosts, see [Local Signing (Docker)](signing-local-docker.md).

---

## Requirements

- **OS & Python:** Linux on `x86_64` or `arm64` (glibc 2.28+), CPython **3.10 to 3.15**.
  - Local watermark embedding (`trufo[local-full]`) requires **Python 3.12+**.
  - Local JPEG XL signing requires **Python 3.12 or earlier** (use Python 3.12 if you need both).
- **System packages:**
  - `libmagic` (Debian/Ubuntu: `libmagic1`) for media type detection.
  - `ffprobe` for signing audio/video, plus `ffmpeg` for audio/video media actions or watermarking (Debian/Ubuntu: `ffmpeg`).
  - For watermarking HEIC, HEIF, or AVIF with `trufo[local-full]`: `heif-enc` **1.20.0+** with HEVC/AV1 encoder plugins (`libheif-examples`, `libheif-plugin-x265`, `libheif-plugin-aomenc`). Note that Ubuntu 24.04 ships an older `heif-enc`; the [full Docker image](signing-local-docker.md) bundles a compatible build.
- **API keys:** An `sdk-download` key and a `c2pa-sign-prod` or `c2pa-sign-test` key. Creating an `sdk-download` key requires accepting the *Trufo Library License* in [Agreements](https://app.trufo.ai/settings/org#agreements) and either an active paid signing/watermark plan or test SDK access enabled by [support@trufo.ai](mailto:support@trufo.ai) (see [Try It on the Test Host](#try-it-on-the-test-host)).

---

## Install

### 1. Configure Trufo's private package index

Engine wheels (`trufo-provenance`, `trufo-avio`, `trufo-pawprint`, and Trufo's `pillow-heif` build) come from `packages.trufo.ai`; `trufo` itself comes from PyPI.

Store your `sdk-download` key in `~/.netrc` rather than embedding it in the index URL (URL-embedded credentials leak into shell history and pip/CI logs):

```bash
cat >> ~/.netrc <<'EOF'
machine packages.trufo.ai
  login __token__
  password <your-sdk-download-key>
EOF
chmod 600 ~/.netrc

export PIP_EXTRA_INDEX_URL="https://packages.trufo.ai/simple/"
```

Keep `__token__` as the login and the full key as the password (Trufo keys contain a colon). In CI, write `~/.netrc` from your secret store during the build step.

### 2. Install an extra

```bash
# Local C2PA signing + media actions (lightweight, no watermark engine)
pip install "trufo[local-sign-only]"

# Adds local watermark embedding (trufo-pawprint + PyTorch, ~6 GB)
pip install "trufo[local-full]"
```

Choose `local-sign-only` unless you embed watermarks locally. If your ML inference workers pin a specific PyTorch/CUDA version, isolate `trufo[local-full]` in its own virtualenv or container.

---

## Sign a File

```python
from pathlib import Path

from trufo import sign_c2pa_local_test
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_TEST)
media_bytes = Path("input.jpg").read_bytes()

signed_bytes = sign_c2pa_local_test(api_key, media_bytes)
Path("signed.jpg").write_bytes(signed_bytes)
```

For production, swap in `sign_c2pa_local()` with a `c2pa-sign-prod` key:

```python
from trufo import sign_c2pa_local

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_PROD)
signed_bytes = sign_c2pa_local(api_key, media_bytes)
```

Both helpers take `api_key` and `media_bytes` positionally; everything else is keyword-only: `actions`, `assertions`, `manifest_title` / `ingredient_title`, `manifest_settings`, `watermark_settings`, `branded_gp_id`, `signed_input_policy`, `signed_ingredient_policy`, `skip_manifest_storage`, and `trufo_api_url`. Cloud-only parameters (`execution_mode`, `mime_type`, `wait_seconds`) are not accepted. Non-fatal notices are emitted as `TrufoServerWarning`, matching Cloud mode.

### Minimizing data sent to Trufo

Original media bytes never leave your machine. Trufo does receive your `actions` and `assertions` (ingredient bytes replaced by SHA-256 hashes and lengths), the claim to sign — including `generator_info` recording this host's OS and kernel release (e.g., `Linux 6.8.0-45-generic`) — and the finished manifest, which includes any generated thumbnail unless suppressed. The finished manifest is always transmitted (Trufo reads its manifest ID from it); it is stored unless you opt out. If your privacy policy requires keeping thumbnails and manifest copies off Trufo's storage:

- Pass `ThumbnailSettings(policy=ThumbnailPolicy.NONE)` inside `manifest_settings` (no new thumbnails are generated).
- Pass `skip_manifest_storage=True` so Trufo discards the manifest after reading its ID (compatible with non-watermarked signs and `per_ai_system` watermarks; not permitted with `per_embed` watermarks).

---

## Try It on the Test Host

1. Accept the *Trufo Library License* at [Organization Settings → Agreements](https://app.trufo.ai/settings/org#agreements).
2. Email [support@trufo.ai](mailto:support@trufo.ai) with your Organization ID to enable test-host SDK download access (if you do not yet have a plan).
3. Create an `sdk-download` key and a `c2pa-sign-test` key.
4. Install `trufo[local-sign-only]` or `trufo[local-full]` and call `sign_c2pa_local_test()` (optionally with `branded_gp_id="test"`).

---

## Local Watermark Settings

With `trufo[local-full]`, `WatermarkSettings` controls how the local watermark encoder runs (it does not turn watermarking on by itself — include `["watermark", {...}]` in `actions`):

```python
from trufo import sign_c2pa_local, watermark_media
from trufo.c2pa import WatermarkProfile, WatermarkSettings

settings = WatermarkSettings(profile=WatermarkProfile.FAST)

signed_bytes = sign_c2pa_local(
    api_key,
    media_bytes,
    actions=[["watermark", {}]],
    watermark_settings=settings,
)

# Standalone local watermarking with a reservation from bind_reserve():
marked_bytes = watermark_media(
    media_bytes, reservation.wid_package, watermark_settings=settings
)
```

- **`default`:** Every-frame video computation; highest durability.
- **`fast`:** Every-fourth-frame video computation with interpolation; roughly 5× faster on CPU, with lower durability (87% → 74% in Trufo benchmarks).
- **GPU:** An NVIDIA CUDA GPU is selected automatically when available (recommended for `default` video and image profiles; `fast` video is intended for CPU).
- **First-call warmup:** The first watermark after startup compiles kernels if `g++` is installed; without `g++`, watermarking still runs (more slowly) and logs a warning once.

---

## Troubleshooting

- **`No matching distribution found for trufo-provenance` / `pillow-heif`:** Configure `~/.netrc` and `PIP_EXTRA_INDEX_URL`, and verify you are on Linux CPython 3.10–3.15.
- **HTTP 401/403 from `packages.trufo.ai`:** Check that your `sdk-download` key is active and your org has a plan or test SDK access.
- **`ImportError` naming `trufo-provenance` or `trufo-pawprint`:** Install `trufo[local-sign-only]` (or `trufo[local-full]` for local watermarking). Requesting a watermark without `trufo-pawprint` always fails regardless of `effort_policy`.
- **`RuntimeError: ffprobe is required`:** Install `ffmpeg` so `ffprobe` is on `PATH`.
- **HEIC/HEIF/AVIF watermark failure:** Ensure `heif-enc` 1.20.0+ with x265/aomenc plugins is installed.
- **`410 Test keys are not accepted on this host`:** Use `sign_c2pa_local_test()` with a `c2pa-sign-test` key.

---

## Licenses

`trufo` is Apache-2.0. The local engine packages (`trufo-provenance`, `trufo-avio`, `trufo-pawprint`) are licensed under the [Trufo Library License](https://trufo.ai/legal/trufo_library_license/v_1_1_0.html).

## Reference

- Local signing protocol and `manifest_settings`: [Signing API](../reference/signing-api.md#local-mode)
- Docker alternative for any language: [Local Signing (Docker)](signing-local-docker.md)
- Watermarking options: [Watermarking and Recovery](watermarking.md)
