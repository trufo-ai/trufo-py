# C2PA Signing in Local Mode with the Python SDK

`sign_c2pa_distributed()` runs C2PA Signing in Local mode inside your Python process:

- the media stays on your machine;
- Trufo's engine, `trufo-provenance`, builds the manifest locally, including any
  watermark;
- Trufo receives the signing instructions, signs the claim with Trufo's certificate,
  and (unless opt-out), stores the finished manifest for soft-binding recovery and
  general audit records.

## When to Use It

Choose the Python SDK when the media must stay on your machine or is large, your
callers are in Python on Linux, or you embed watermarks locally. For other languages
or platforms, see [Local mode with the Docker image](docker.md); its
[full image](docker.md#choose-an-image) signs and watermarks like `trufo[local-full]`,
but on CPU only and without the
[Watermarking routes](../quickstart/6_watermarking.md#routes). Cloud mode is simpler
when uploading the media is fine.

## Requirements

- **Linux on x86_64 or arm64 (glibc 2.28+) with CPython 3.12.** The engine is
  published as Linux wheels (manylinux_2_28, x86_64 and aarch64), built and tested for
  CPython 3.12.
  The base `trufo` package is pure Python and runs on any platform with Python 3.10+.
- **System packages:** `libmagic` for file-type detection (Debian and Ubuntu:
  `libmagic1`), and `ffprobe` on the PATH to sign any audio or video (Debian and
  Ubuntu: `ffmpeg`).
- **API keys**, set up as in [0_setup.md](../quickstart/0_setup.md): an `sdk-download`
  key to install the engine, and a `c2pa-sign-test` key for the test host or a
  `c2pa-sign-prod` key, with completed Organization Validation, for production.

## Install

### Private Package Index

The engine packages, `trufo-provenance` and `trufo-pawprint`, come from Trufo's private
package index at `packages.trufo.ai`; the `trufo` package itself comes from public
PyPI. The index also serves Trufo's build of `pillow-heif` (1.8.1+trufo.1), which
the engine requires in both extras; a package mirror or allowlist needs it too. Set
up the index before installing an extra. It needs an `sdk-download` API key, created
at [app.trufo.ai/settings/org](https://app.trufo.ai/settings/org#api-access) under
*API Access → API Keys*. Creating one requires an active C2PA Signing or
Watermark API plan and the Trufo Library License, accepted at
[Organization Settings → Agreements](https://app.trufo.ai/settings/org#agreements).
Before purchasing a plan, see [Try It on the Test Host](#try-it-on-the-test-host).

Store the key in `~/.netrc` rather than in the index URL. pip sends it as an HTTP
basic-auth credential either way, but a URL-embedded key also lands in your shell
history, the process list, and pip and CI logs:

```bash
cat >> ~/.netrc <<'EOF'
machine packages.trufo.ai
  login __token__
  password <your-sdk-download-key>
EOF
chmod 600 ~/.netrc
```

The literal `__token__` goes in the login field and the key in the password field —
the same convention PyPI uses. Keep that order: a Trufo API key contains a colon,
which is also the separator in an HTTP basic-auth credential, so putting the key in
the login field makes it ambiguous to parse.

Then point pip at the index — no credential in the URL:

```bash
export PIP_EXTRA_INDEX_URL="https://packages.trufo.ai/simple/"
```

In CI, write the `~/.netrc` from your secret store as a build step instead of
committing it or exporting the key into the environment.

Treat the key like any other credential: keep it out of committed lockfiles and logs,
and revoke it from the dashboard if it is exposed.

### Extras

Install one of the two extras:

```bash
# C2PA Signing in Local mode, without the watermark engine
pip install "trufo[local-sign-only]"

# adds local watermark embedding: trufo-pawprint and PyTorch
pip install "trufo[local-full]"
```

Pick `local-sign-only` unless you embed watermarks locally. The watermark engine's
dependencies are heavy: pip installs PyTorch with its CUDA libraries on both
architectures, about 6 GB in all, and embedding runs on the CPU when no NVIDIA GPU is
present. A `local-sign-only` installation signs normally, but a watermark request
without the engine always fails with an install hint (see the
[Watermarking Quickstart](../quickstart/6_watermarking.md)). The legacy `provenance`
extra is an alias of `local-sign-only`.

## Sign a File

```python
from pathlib import Path

from trufo import sign_c2pa_distributed_test
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_TEST)
media_bytes = Path("input.jpg").read_bytes()

signed_bytes = sign_c2pa_distributed_test(api_key, media_bytes)
Path("signed.jpg").write_bytes(signed_bytes)
```

For production, swap the helper and the key:

```python
from trufo import sign_c2pa_distributed

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_PROD)
signed_bytes = sign_c2pa_distributed(api_key, media_bytes)
```

Both helpers take the same `actions`, `assertions`, `manifest_settings`,
`branded_gp_id`, `signed_input_policy`, `signed_ingredient_policy` and
`trufo_api_url` as `sign_c2pa()`, `transcode` included; see the
[C2PA Signing Quickstart](../quickstart/2_c2pa_signing.md) and
[`actions`](../api/api_c2pa.md#actions). With `trufo[local-full]`, a `watermark`
action embeds the mark locally; see the
[Watermarking Quickstart](../quickstart/6_watermarking.md). What Local mode records
by default: [Local mode](../api/api_c2pa.md#local-mode).

Trufo's [notices](../api/api_c2pa.md#response-warnings) arrive as Python
`UserWarning`s. Refusals carry the same texts as in Cloud mode and are raised by the
SDK call. When the SDK or engine version is deprecated, a notice gives the date
after which signing with it returns `400 UnsupportedSDKVersion`; upgrade before then.

## Try It on the Test Host

You can try Local mode on the test host without a plan or Organization Validation:

1. Accept the Trufo Library License at
   [Organization Settings → Agreements](https://app.trufo.ai/settings/org#agreements).
2. Email support@trufo.ai with your Organization ID
   ([Organization Settings](https://app.trufo.ai/settings/org)) to request SDK download
   access.
3. Once it is granted, create an `sdk-download` key and a `c2pa-sign-test` key.
4. Install as above and sign with `sign_c2pa_distributed_test()`. To try
   [branded signing](../quickstart/2_c2pa_signing.md#direct-signing), pass
   `branded_gp_id="test"`.

Signed files carry Trufo's test certificate, which validators report as untrusted.

## Local Watermark Settings

Watermarking is off by default. With `trufo[local-full]`, an explicit `watermark`
action requests it; `WatermarkSettings` chooses how the local engine runs:

```python
from pathlib import Path

from trufo import sign_c2pa_distributed, watermark_media
from trufo.c2pa import WatermarkProfile, WatermarkSettings

media_bytes = Path("input.mp4").read_bytes()
settings = WatermarkSettings(profile=WatermarkProfile.FAST)
signed_bytes = sign_c2pa_distributed(
    api_key,
    media_bytes,
    actions=[["watermark", {}]],
    watermark_settings=settings,
)

# with a reservation from bind_reserve(), for media you sign yourself
marked_bytes = watermark_media(
    media_bytes, reservation.wid_package, watermark_settings=settings
)
```

Both distributed signing helpers and `watermark_media()` accept these settings;
`WatermarkSettings(profile="fast")` accepts the string directly. Omitting settings
uses `default`: CPU FP32 and independent video frames. `fast` permits supported
CPU BF16 for images and video anchors, with FP32 fallback. The CPU encoder attempts
cached compilation on first use, so cold startup differs from warmed throughput.

Fast video interpolates watermark residuals between frames 0, 4, 8, ... and the
final frame, trading robustness for CPU throughput. Warm encoder comparisons on an
eight-thread AMD Ryzen 9 9950X3D measured 4.97× throughput, excluding startup, input
copies and codecs; a separate 40-clip, 360-case durability test recovered 74.4% with
fast CPU BF16 versus 86.7% with default CPU FP32.

An NVIDIA CUDA GPU is recommended and selected automatically when available.
Default video and both image profiles retain the original GPU implementation;
fast video uses FP32 anchors and is not recommended on GPU. Audio, including video
audio tracks, keeps its ordinary encoder in both profiles.

Settings stay local, outside action parameters, network requests and C2PA
assertions. Settings alone do not request watermarking. The shipped
[Docker images](docker.md) use fixed engine versions and do not support these profiles.

## Troubleshooting

**`No matching distribution found for trufo-provenance…` or `…for pillow-heif…`** —
pip cannot see the private index: set it up as in
[Private Package Index](#private-package-index). On a
host other than Linux with CPython 3.12, use
[Local mode with the Docker image](docker.md).

**pip reports HTTP 401 or 403 from `packages.trufo.ai`** — the key in `~/.netrc` is
not an active `sdk-download` key, or your organization has neither a plan nor SDK
download access (see [Private Package Index](#private-package-index)).

**`ImportError: The optional trufo-provenance dependency is required`**, or an
`ImportError` naming trufo-pawprint — install `trufo[local-sign-only]`, or
`trufo[local-full]` to embed watermarks.

**`RuntimeError: ffprobe is required for audio/video media probing.`** — install
FFmpeg so that `ffprobe` is on the PATH (Debian and Ubuntu: `ffmpeg`).

**`Test keys are not accepted on this host. Please use test.api.trufo.ai.`** — a
`c2pa-sign-test` key sent to a production host, which `sign_c2pa_distributed()` calls
by default. Use `sign_c2pa_distributed_test()`, or a `c2pa-sign-prod` key; see
[Signing Modes](../api/api_c2pa.md#signing-modes).

**`UnsupportedSDKVersion: …`** — the SDK or engine version is not supported, or the
engine is too old for a feature the request uses; the message names the package and
the reason.
Upgrade `trufo` with its local engine extra, which installs `trufo-provenance`; see
[Local mode](../api/api_c2pa.md#local-mode).

For other platforms, use [Local mode with the Docker image](docker.md), or contact
[support@trufo.ai](mailto:support@trufo.ai).

## Licenses

The `trufo` package is under the Apache License 2.0. The engine, `trufo-provenance`,
is under the
[Trufo Library License](https://trufo.ai/legal/trufo_library_license/v_1_1_0.html).

## Reference

- Setup and API keys: [0_setup.md](../quickstart/0_setup.md)
- Local mode with the Docker image: [docker.md](docker.md)
- C2PA Signing Quickstart: [2_c2pa_signing.md](../quickstart/2_c2pa_signing.md)
- C2PA API reference: [api_c2pa.md](../api/api_c2pa.md)
- SDK overview: [README](../../README.md)
