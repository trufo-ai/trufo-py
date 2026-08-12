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

## Choosing a Mode

| Mode | Use when | Media sent to Trufo | Extra requirements |
| ---- | -------- | ------------------- | ------------------ |
| Simple | Default choice | Yes, in the request body | None |
| S3 | Media is large | Yes, via an ephemeral upload | None |
| Distributed | Media must not leave your infrastructure | No — only the claim hash | `trufo[local-sign-only]` or `[local-full]`, a `tsa` key, Linux x86_64 + CPython 3.12 |

Test and production are variants of each mode: the test helpers target the test
host and need no OV, and their output is **not** recognized by conformant C2PA
validators. Start on test, then swap the helper and the key.

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

## Titles

Manifests and their ingredients carry display names (`dc:title`) that validator
UIs show prominently. Pass them explicitly — typically the asset's filename:

```python
signed_bytes = sign_c2pa_test(
    api_key,
    media_bytes,
    manifest_title="sunset_edit.jpg",   # the signed output's display name
    ingredient_title="sunset.jpg",      # the input it was derived from
)
```

When omitted, the manifest carries no title, and the input's ingredient entry
falls back to the input's own manifest title, then a generic name. Fallbacks
are derived, not authored — see
[title fallbacks](../api/api_c2pa.md#post-c2pasign) for the exact order.

---

## S3 Signing

For large media, upload to an ephemeral Trufo-signed S3 location instead of
putting bytes in the request body. `sign_c2pa_via_s3()` performs the whole
upload → sign → download sequence:

```python
from trufo import sign_c2pa_via_s3

signed_bytes = sign_c2pa_via_s3(api_key, media_bytes, mime_type="image/jpeg")
```

`sign_c2pa_via_s3_test()` is the test-host equivalent. The lower-level helpers
(`get_c2pa_s3_upload_url`, `sign_c2pa_s3`, `sign_c2pa_s3_test`) are available when
you want to manage the upload yourself — see
[api_c2pa.md](../api/api_c2pa.md#post-c2paioget-s3-url).

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
