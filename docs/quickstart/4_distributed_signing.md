# Quickstart: Distributed C2PA Signing

Build the C2PA manifest locally while keeping the C2PA signing key in Trufo's infrastructure.

## What This Does

`sign_c2pa_distributed()` creates the C2PA claim in the client and calls Trufo only to procure the C2PA claim signature. This means that the media file is not sent to the Trufo server and instead stays local.

## Requirements

- Install the optional provenance engine: `pip install "trufo[provenance]"`.
- A `c2pa-sign-test` API key for the remote claim-signing endpoint. See [0_auth.md](0_auth.md).
- A `tsa` API key for timestamping. Configure it with `trufo set-api-key tsa <your-api-key>` or `TRUFO_TSA_API_KEY`.
- When `assertions` is non-empty, at least one `cawg_identity` entry must be present.

> **EXPERIMENTAL:** Currently this feature is in an experimental state, and may change substantially in the next few weeks. Note that `sign_c2pa_distributed_test()` is available but `sign_c2pa_distributed()` (that uses a real C2PA certificate) is not.

---

## Minimal Example

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

## Adding Actions and Assertions

Distributed signing accepts the same `actions` and `assertions` shape as `sign_c2pa_test()`:

```python
signed_bytes = sign_c2pa_distributed_test(
    api_key,
    media_bytes,
    actions=[
        ["publish", {}],
    ],
    assertions=[
        ["ai_disclosure", {}],
        ["cawg_identity", {"cawg_identity_id": "test"}],
    ],
)
```

See [2_ai_labeling.md](2_ai_labeling.md) for `ai_disclosure` and [3_cawg_publish.md](3_cawg_publish.md) for CAWG metadata, training, and identity assertions.

---

## Distributed vs Hosted Signing

| Helper | Where manifest generation happens | What Trufo receives | Signing key location |
|--------|-----------------------------------|---------------------|----------------------|
| `sign_c2pa_test()` | Trufo server | media bytes or S3 reference | Trufo server |
| `sign_c2pa_distributed_test()` | your Python process | claim bytes-to-be-signed | Trufo server |

Use hosted signing when you want the simplest flow. Use distributed signing when your application needs to keep media processing and claim generation local.

---

## Troubleshooting

**`ImportError: The optional trufo-provenance dependency is required`**

Install the provenance extra:

```bash
pip install "trufo[provenance]"
```

**`A TSA API key is required for remote C2PA signing`**

Store a TSA key or pass `tsa_api_key` explicitly:

```bash
trufo set-api-key tsa <your-api-key>
```

**`'cawg_identity' is required when assertions are provided`**

Add a `cawg_identity` assertion. For test signing, use `cawg_identity_id="test"`.

---

## Reference

- Authentication setup: [0_auth.md](0_auth.md)
- C2PA signing API reference: [../api/api_c2pa.md](../api/api_c2pa.md)
- AI labeling quickstart: [2_ai_labeling.md](2_ai_labeling.md)
- CAWG publish quickstart: [3_cawg_publish.md](3_cawg_publish.md)
