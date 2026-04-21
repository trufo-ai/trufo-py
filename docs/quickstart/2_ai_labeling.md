# Quickstart: AI Labeling

Label media content as AI-generated using the C2PA `c2pa.ai-disclosure` assertion.

## What This Does

The `ai_disclosure` assertion inserts a `c2pa.ai-disclosure` entry into the C2PA manifest. Validators and content-provenance tools (e.g. [Content Credentials](https://contentcredentials.org)) surface this as an "AI generated" signal.

## Requirements

- A TPS API key. See [0_tps_access.md](0_tps_access.md).
- When `assertions` is non-empty, at least one `cawg_identity` entry must be present.

---

## Minimal Example

```python
from trufo.api.tps.generate_c2pa import generate_c2pa_test
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.TPS)

signed_bytes = generate_c2pa_test(
    api_key,
    media_bytes,
    assertions=[
        ["ai_disclosure", {}],
        ["cawg_identity", {"cawg_identity_id": "test"}],
    ],
)
```

---

## Setting Digital Source Type (Optional)

For conformance with C2PA v2.4 (§18.16.12.3), you can additionally set `digitalSourceType = trainedAlgorithmicMedia` on the ingredient. This only takes effect when the input media has no existing C2PA manifest.

> **Validator compatibility:** `digitalSourceType` in C2PA ingredients was introduced in C2PA v2.4 and is not yet supported by most existing validators. The `c2pa.ai-disclosure` assertion is sufficient for labeling in the vast majority of cases. `set_source_type` is the only conformant way to set this field unless you run a full custom Generator Product workflow. Contact Trufo or CAI/C2PA for questions.

```python
assertions=[
    ["ai_disclosure", {"set_source_type": True}],
    ["cawg_identity", {"cawg_identity_id": "test"}],
]
```

---

## Reference

- `assertions` field reference: [../api/api_c2pa.md](../api/api_c2pa.md)
- Complete runnable example: [2_ai_labeling.py](2_ai_labeling.py)
