# Quickstart: AI Labeling

Label media content as AI-generated using the C2PA `c2pa.ai-disclosure` assertion and more.

## What This Does

The `ai_disclosure` assertion inserts a `c2pa.ai-disclosure` entry into the C2PA manifest. Validators (e.g. [Content Credentials](https://contentcredentials.org)) and content platforms parse this as an "AI generated" signal.

Additionally, the `{"set_source_type": True}` flag sets `digitalSourceType = trainedAlgorithmicMedia` on the ingredient. This only takes effect when the input media has no existing C2PA manifest.

## Requirements

- A `c2pa-sign-test` API key (scope required by `/test/c2pa/sign`). See [0_auth.md](0_auth.md).
- When `assertions` is non-empty, at least one `cawg_identity` entry must be present.

---

## Minimal Example

```python
from trufo.api.tps.sign_c2pa import sign_c2pa_test
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_TEST)

signed_bytes = sign_c2pa_test(
    api_key,
    media_bytes,
    assertions=[
        ["ai_disclosure", {"set_source_type": True}],
        ["cawg_identity", {"cawg_identity_id": "test"}],
    ],
)
```

> **Note on `set_source_type`:** Setting `digitalSourceType` within C2PA ingredients is new to C2PA v2.4 (§18.16.12.3) and is not yet supported by most existing validators today (e.g. having this field may make the manifest show up as "invalid"). The `c2pa.ai-disclosure` assertion alone suffices for AI labeling purposes, though for forwards-compatibility purposes you may want to set both. If your use case allows for validators to temporarily display "invalid" messaging, we recommend setting both. If not, then include only the ai_disclosure (by deleting `{"set_source_type": True}` from the example above).

---

## Reference

- `assertions` field reference: [../api/api_c2pa.md](../api/api_c2pa.md)
- Complete runnable example: [2_ai_labeling.py](2_ai_labeling.py)

