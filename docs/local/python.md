# C2PA Signing in Local Mode with the Python SDK

`sign_c2pa_distributed()` runs C2PA Signing in Local mode inside your Python process:

- the media stays on your machine;
- Trufo's engine, `trufo-provenance`, builds the manifest locally, including any
  watermark;
- only the claim goes to Trufo, which signs it with Trufo's certificate.

## When to Use It

Choose the Python SDK when the media must stay on your machine or is large, your
callers are in Python on Linux, or you embed watermarks locally. For other languages
or platforms, see [Local mode with the Docker image](docker.md). Cloud mode is
simpler when uploading the media is fine.

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
PyPI. Set up the index before installing an extra. It needs an `sdk-download` API
key, created at [app.trufo.ai/settings/org](https://app.trufo.ai/settings/org#api-access)
under *API Access → API Keys*. Creating one requires an active C2PA Signing or
Watermark API plan and the Trufo Library License, accepted at
[Organization Settings → Agreements](https://app.trufo.ai/settings/org#agreements).

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
`branded_gp_id` and `trufo_api_url` as `sign_c2pa()`, `transcode` included; see the
[C2PA Signing Quickstart](../quickstart/2_c2pa_signing.md) and
[`actions`](../api/api_c2pa.md#actions). With `trufo[local-full]`, a `watermark`
action embeds the mark locally; see the
[Watermarking Quickstart](../quickstart/6_watermarking.md). What Local mode records
by default: [Local mode](../api/api_c2pa.md#local-mode).

Trufo's [notices](../api/api_c2pa.md#response-warnings) arrive as Python
`UserWarning`s. When the SDK or engine version is deprecated, a notice gives the date
after which signing with it returns `400 UnsupportedSDKVersion`; upgrade before then.

## Troubleshooting

**`No matching distribution found for trufo-provenance…`** — pip cannot see the
private index: set it up as in [Private Package Index](#private-package-index). On a
host other than Linux with CPython 3.12, use
[Local mode with the Docker image](docker.md).

**pip reports HTTP 401 or 403 from `packages.trufo.ai`** — the key in `~/.netrc` is
not an active `sdk-download` key, or your organization lacks the plan or the Trufo
Library License (see [Private Package Index](#private-package-index)).

**`ImportError: The optional trufo-provenance dependency is required`**, or an
`ImportError` naming trufo-pawprint — install `trufo[local-sign-only]`, or
`trufo[local-full]` to embed watermarks.

**`RuntimeError: ffprobe is required for audio/video media probing.`** — install
FFmpeg so that `ffprobe` is on the PATH (Debian and Ubuntu: `ffmpeg`).

For other platforms, use [Local mode with the Docker image](docker.md), or contact
[support@trufo.ai](mailto:support@trufo.ai).

## Licenses

The `trufo` package is under the Apache License 2.0. The engine, `trufo-provenance`,
is under the
[Trufo Library License](https://trufo.ai/legal/trufo_library_license/v_1_0_0.html).

## Reference

- Setup and API keys: [0_setup.md](../quickstart/0_setup.md)
- Local mode with the Docker image: [docker.md](docker.md)
- C2PA Signing Quickstart: [2_c2pa_signing.md](../quickstart/2_c2pa_signing.md)
- C2PA API reference: [api_c2pa.md](../api/api_c2pa.md)
- SDK overview: [README](../../README.md)
