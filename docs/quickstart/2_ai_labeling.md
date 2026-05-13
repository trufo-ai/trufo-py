# Quickstart: AI Labeling

Label media content as AI-generated using the C2PA `c2pa.ai-disclosure` assertion and more.

## What This Does

The `ai_disclosure` assertion inserts a `c2pa.ai-disclosure` entry into the C2PA manifest. Validators (e.g. [Content Credentials](https://contentcredentials.org)) and content platforms parse this as an "AI generated" signal.

Additionally, the `{"set_source_type": True}` flag sets `digitalSourceType = trainedAlgorithmicMedia` on the ingredient. This only takes effect when the input media has no existing C2PA manifest.

## Requirements

- For production signing: a `c2pa-sign-prod` API key (scope required by `/c2pa/sign`). See [0_auth.md](0_auth.md).
- For test signing: a `c2pa-sign-test` API key (scope required by `/test/c2pa/sign`).
- Production examples that use `cawg_identity_id="org_interim"` require your organization to have CAWG organization identity signing enabled.
- When `assertions` is non-empty, at least one `cawg_identity` entry must be present.

---

## Minimal Example

```python
from trufo.api.tps.sign_c2pa import sign_c2pa
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_PROD)

signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    assertions=[
        ["ai_disclosure", {}],
        ["cawg_identity", {"cawg_identity_id": "org_interim"}],
    ],
)
```

For development-only test signing, use `sign_c2pa_test()` with a `c2pa-sign-test` API key and `cawg_identity_id="test"`. Test-signed outputs are useful for integration development but are not intended to be accepted as production C2PA credentials by conformant validators.

> **Note on `set_source_type`:** For the most proper behavior, you should pass `"set_source_type": True` in the `ai_disclosure` params. However, because `digitalSourceType` within C2PA ingredients is new to C2PA v2.4 (§18.16.12.3) and is not yet supported by most existing validators today (e.g. having this field may make the manifest show up as "invalid"), we do not recommend passing it in yet. The `c2pa.ai-disclosure` assertion alone suffices for AI labeling purposes, though for forwards-compatibility purposes you may want to set both. If your use case allows for validators to temporarily display "invalid" messaging, we recommend setting both. If not, then include only the ai_disclosure (by deleting `{"set_source_type": True}` from the example above).

## Using a Custom AI Disclosure

By default, `"ai_disclosure"` uses the minimal disclosure body `{"modelType": "c2pa.types.model"}`. If you would like to disclose specific details about the AI model being used, then you need to first register the profile via `POST /c2pa/ai-disclosure/add`.

```python
import requests

from trufo.api.endpoints import TPS_C2PA_AI_DISCLOSURE_ADD, TRUFO_API_URL

resp = requests.post(
    TRUFO_API_URL + TPS_C2PA_AI_DISCLOSURE_ADD,
    headers={"X-API-Key": api_key},
    json={
        "nickname": "image model v3.2, 2026-03-11",
        "assertion": {
            "modelType": "c2pa.types.model.huggingface.transformers",
            "modelName": "ImageGen Pro v3.2",
        },
    },
    timeout=60,
)
resp.raise_for_status()

ai_disclosure_id = resp.json()["ai_disclosure_id"]
```

The API returns an `ai_disclosure_id`, which can then be passed in the `ai_disclosure` assertion:

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    assertions=[
        ["ai_disclosure", {"ai_disclosure_id": "aidisc_0193f7e0abcd7a11bcde01234567890a"}],
        ["cawg_identity", {"cawg_identity_id": "org_interim"}],
    ],
)
```

See the full [C2PA API reference](../api/api_c2pa.md#api-reference-post-c2paai-disclosureadd) for the add/list endpoints and the accepted disclosure schema.

---

## Reference

- `assertions` field reference: [../api/api_c2pa.md](../api/api_c2pa.md)
- Complete runnable example: [2_ai_labeling.py](2_ai_labeling.py)
