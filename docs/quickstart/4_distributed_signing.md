# Quickstart: Distributed C2PA Signing

Build the C2PA manifest locally while keeping the C2PA signing key in Trufo's infrastructure.

## What This Does

`sign_c2pa_distributed()` creates the C2PA claim in the client and calls Trufo only to procure the C2PA claim signature. This means that the media file is not sent to the Trufo server and instead stays local.

## Requirements

- Install the optional local engine: `pip install "trufo[local]"` (see the [README](../../README.md#optional-local-engine) for the private-index setup). The legacy `provenance` extra also works, but signs without local watermark embedding.
- A `tsa` API key for RFC 3161 timestamping. Configure it with `trufo set-api-key tsa <your-api-key>` or `TRUFO_TSA_API_KEY`.
  (To try the timestamping flow before you have a key, the free test endpoint `https://tsa.test.trufo.ai/` accepts keyless requests; its tokens are not production-trusted.)
- For test signing, a `c2pa-sign-test` API key. For production signing, a `c2pa-sign-prod` API key and completed Organization Validation (OV) for your organization. See [0_auth.md](0_auth.md).

Every signed manifest automatically carries an `ai.trufo.identity` assertion with your organization id and (with active OV) your RA-validated legal name — see [Automatic assertions](../api/api_c2pa.md#automatic-assertions).

---

## Test Signing

Use `sign_c2pa_distributed_test()` with a `c2pa-sign-test` key for integration development:

```python
from pathlib import Path

from trufo import sign_c2pa_distributed_test
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_TEST)

media_bytes = Path("input.jpg").read_bytes()
signed_bytes = sign_c2pa_distributed_test(
    api_key,
    media_bytes,
    assertions=[
        ["cawg_identity", {"cawg_identity_id": "test"}],
    ],
)

Path("signed.jpg").write_bytes(signed_bytes)
```

`sign_c2pa_distributed_test()` automatically loads the TSA key from the existing SDK credential path. To pass it explicitly instead:

```python
signed_bytes = sign_c2pa_distributed_test(
    api_key,
    media_bytes,
    assertions=[
        ["cawg_identity", {"cawg_identity_id": "test"}],
    ],
    tsa_api_key="tsa_...",
)
```

Test-signed outputs are useful for integration development but are not intended to be accepted as production C2PA credentials by conformant validators.

---

## Production Signing

Use `sign_c2pa_distributed()` with a `c2pa-sign-prod` key to obtain a production C2PA claim signature. Production signing requires completed Organization Validation (OV) for the calling organization. Otherwise, the API returns `403 MissingOrganizationValidation`.

```python
from pathlib import Path

from trufo import sign_c2pa_distributed
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_PROD)

media_bytes = Path("input.jpg").read_bytes()
signed_bytes = sign_c2pa_distributed(
    api_key,
    media_bytes,
)

Path("signed.jpg").write_bytes(signed_bytes)
```

Both helpers automatically load the TSA key from the SDK credential path. To pass it explicitly, provide `tsa_api_key="tsa_..."`.

---

## Server Selection

The SDK defaults to the Global API endpoint. To instead use the Europe API endpoint, specify:

```python
from trufo.api.endpoints import TRUFO_API_URL_EUROPE

signed_bytes = sign_c2pa_distributed(
    api_key,
    media_bytes,
    trufo_api_url=TRUFO_API_URL_EUROPE,
)
```

Organizations provisioned with a dedicated API or TSA can set them explicitly:

```python
signed_bytes = sign_c2pa_distributed(
    api_key,
    media_bytes,
    trufo_api_url="https://company.api.trufo.ai",
    trufo_tsa_url="https://company.tsa.trufo.ai",
)
```

Please note that certain types of data will or will not be available cross-region.

---

## Adding Actions and Assertions

Both distributed signing helpers accept the same `actions` and `assertions` shape as the hosted signing helpers:

```python
signed_bytes = sign_c2pa_distributed(
    api_key,
    media_bytes,
    actions=[
        ["publish", {}],
    ],
)
```

See [2_ai_labeling.md](2_ai_labeling.md) for `ai_disclosure` and [3_cawg_publish.md](3_cawg_publish.md) for CAWG metadata, training, and identity assertions. For test signing, use `cawg_identity_id="test"`; production CAWG identities require the appropriate organization configuration.

---

## Distributed vs Hosted Signing

| Helper | Environment | Where manifest generation happens | What Trufo receives | Signing key location |
|--------|-------------|-----------------------------------|---------------------|----------------------|
| `sign_c2pa()` | Production | Trufo server | media bytes or S3 reference | Trufo server |
| `sign_c2pa_test()` | Test | Trufo server | media bytes or S3 reference | Trufo server |
| `sign_c2pa_distributed()` | Production | your Python process | claim bytes-to-be-signed | Trufo server |
| `sign_c2pa_distributed_test()` | Test | your Python process | claim bytes-to-be-signed | Trufo server |

Use hosted signing when you want the simplest flow. Use distributed signing when your application needs to keep media processing and claim generation local.

---

## Troubleshooting

**`ImportError: The optional trufo-provenance dependency is required`**

Install the local engine extra:

```bash
pip install "trufo[local]"
```

**`A TSA API key is required for remote C2PA signing`**

Store a TSA key or pass `tsa_api_key` explicitly:

```bash
trufo set-api-key tsa <your-api-key>
```

**`403 MissingOrganizationValidation`**

Production distributed signing requires completed Organization Validation for the calling organization. Use `sign_c2pa_distributed_test()` for test signing until OV is complete.

---

## Reference

- Authentication setup: [0_auth.md](0_auth.md)
- C2PA signing API reference: [../api/api_c2pa.md](../api/api_c2pa.md)
- AI labeling quickstart: [2_ai_labeling.md](2_ai_labeling.md)
- CAWG publish quickstart: [3_cawg_publish.md](3_cawg_publish.md)
