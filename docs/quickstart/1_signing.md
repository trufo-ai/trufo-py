# Quickstart: Signing

Sign a media file with a C2PA manifest — the core of the Trufo Provenance Service.

## What This Does

`sign_c2pa()` sends your media to Trufo, which assembles a C2PA manifest, signs it
with a production-trusted Trufo certificate, and returns the signed file. Every
manifest automatically carries an `ai.trufo.identity` assertion naming your
organization — see [Automatic assertions](../api/api_c2pa.md#automatic-assertions).

No certificate of your own is required: Trufo signs on your behalf. (To run your
own signer with your own certificate, see [7_c2pa_cert.md](7_c2pa_cert.md).)

## Requirements

- A `c2pa-sign-test` API key for test signing, or a `c2pa-sign-prod` key plus
  completed Organization Validation (OV) for production. See [0_auth.md](0_auth.md).
- `pip install trufo` — no optional extras needed for hosted signing.

---

## Test Signing

Start here: test signing needs no OV and is free. Outputs are signed with the
Trufo test certificate and are **not** recognized by conformant C2PA validators.

```python
from pathlib import Path

from trufo import sign_c2pa_test
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_TEST)

media_bytes = Path("input.jpg").read_bytes()
signed_bytes = sign_c2pa_test(api_key, media_bytes)

Path("signed.jpg").write_bytes(signed_bytes)
```

## Production Signing

Swap the helper and the key. Production signing requires completed OV; without it
the API returns `403 MissingOrganizationValidation`.

```python
from trufo import sign_c2pa
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_PROD)
signed_bytes = sign_c2pa(api_key, media_bytes)
```

## Large Media (S3)

For large files, upload to an ephemeral Trufo-signed S3 location instead of
sending bytes in the request body. `sign_c2pa_via_s3()` performs the whole
upload → sign → download sequence:

```python
from trufo import sign_c2pa_via_s3

signed_bytes = sign_c2pa_via_s3(api_key, media_bytes, mime_type="image/jpeg")
```

The lower-level helpers (`get_c2pa_s3_upload_url`, `sign_c2pa_s3`) are available
when you want to manage the upload yourself. See
[api_c2pa.md](../api/api_c2pa.md#media_input_s3).

---

## Adding Actions and Assertions

Both arguments take a list of `[name, params]` pairs: `actions` are instructions
Trufo applies in order, `assertions` are statements recorded in the manifest.

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    actions=[["publish", {}]],
    assertions=[["cawg_identity", {"cawg_identity_id": "org_interim"}]],
)
```

Where to go next, by what you want to record:

| Goal | Guide |
| ---- | ----- |
| Disclose AI-generated content | [2_ai_labeling.md](2_ai_labeling.md) |
| Attach organization identity and metadata | [3_cawg_publish.md](3_cawg_publish.md) |
| Keep media on your own machine while signing | [4_distributed_signing.md](4_distributed_signing.md) |
| Declare source assets, or redact from history | [5_ingredients.md](5_ingredients.md) |
| Embed a recoverable watermark | [6_watermarking.md](6_watermarking.md) |

The [feature support matrix](../c2pa_feature_list.md) shows which actions and
assertions each signing mode supports.

---

## Troubleshooting

**`403 MissingOrganizationValidation`**

Production signing requires completed OV for your organization. Use
`sign_c2pa_test()` until OV is complete.

**`403 APIKeyScopeNotAllowed`**

The key's scope doesn't match the endpoint — `c2pa-sign-prod` for production,
`c2pa-sign-test` for test.

**The sign succeeded but something was skipped**

Check the response `warnings` — the SDK re-emits them as `TrufoServerWarning`.
See [`warnings`](../api/api_c2pa.md#warnings).

---

## Reference

- Authentication setup: [0_auth.md](0_auth.md)
- C2PA signing API reference: [../api/api_c2pa.md](../api/api_c2pa.md)
- Feature support matrix: [../c2pa_feature_list.md](../c2pa_feature_list.md)
