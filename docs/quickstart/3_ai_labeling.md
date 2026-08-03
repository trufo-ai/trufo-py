# Quickstart: AI Labeling

Disclose that content was generated or assisted by AI, in a way validators and
platforms recognize.

## What This Does

C2PA carries AI disclosure in two independent places, and they answer different
questions:

| Signal | Question it answers | Where it lives |
| ------ | ------------------- | -------------- |
| `c2pa.ai-disclosure` assertion | *What model made this, and with how much human oversight?* | An assertion in your manifest |
| `digitalSourceType` | *Is this asset itself AI-generated?* | A field on the ingredient |

The assertion is what validators such as
[Content Credentials](https://contentcredentials.org) read as an "AI generated"
signal. `digitalSourceType` is newer and less widely supported — see the caveat
below.

## Requirements

- A `c2pa-sign-test` or `c2pa-sign-prod` API key. See [0_setup.md](0_setup.md).
- Nothing else — AI labeling adds no plan requirement.

---

## Minimal Disclosure

One entry marks content as AI-generated, using the default disclosure body
`{"modelType": "c2pa.types.model"}`:

```python
from trufo import sign_c2pa
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_PROD)

signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    assertions=[
        ["ai_disclosure", {}],
    ],
)
```

This satisfies most AI-labeling requirements. Use it when you do not want to
publish details about the model.

---

## Detailed Disclosure

To name the model, its framework, or the level of human oversight, register the
disclosure once and reference it by id. Inline bodies are rejected at signing time —
registering keeps the disclosure consistent across every asset you sign and lets you
update the description in one place.

### Register it

```python
import requests

from trufo.api.endpoints import TPS_C2PA_AI_DISCLOSURE_ADD, TRUFO_API_URL

resp = requests.post(
    TRUFO_API_URL + TPS_C2PA_AI_DISCLOSURE_ADD,
    headers={"X-API-Key": api_key},
    json={
        "nickname": "image model v3.2",
        "assertion": {
            "modelType": "c2pa.types.model.huggingface.transformers",
            "modelName": "ImageGen Pro v3.2",
            "modelIdentifier": "pkg:huggingface/acme/imagegen-pro@v3.2",
            "contentProfile": {"humanOversightLevel": "prompt_guided"},
        },
    },
    timeout=60,
)
resp.raise_for_status()
ai_disclosure_id = resp.json()["ai_disclosure_id"]
```

`humanOversightLevel` is worth setting deliberately — it distinguishes fully
automated generation from human-directed or human-reviewed work:

| Value | Meaning |
| ----- | ------- |
| `fully_autonomous` | The model produced the asset without human direction |
| `prompt_guided` | A human directed the model but did not review the output |
| `human_validated` | A human reviewed and accepted the output |

See [api_c2pa.md](../api/api_c2pa.md#post-c2paai-disclosureadd) for the complete
schema, and `POST /c2pa/ai-disclosure/list` to enumerate what you have registered.

### Use it

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    assertions=[
        ["ai_disclosure", {"ai_disclosure_id": ai_disclosure_id}],
    ],
)
```

---

## Marking the Source Type

`set_source_type` additionally records `digitalSourceType = trainedAlgorithmicMedia`
on the asset's ingredient — the C2PA field stating that the asset itself is
AI-generated, rather than merely disclosing which model was involved.

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    assertions=[
        ["ai_disclosure", {"ai_disclosure_id": ai_disclosure_id, "set_source_type": True}],
    ],
)
```

It applies only when the input has no existing C2PA manifest — content you are
signing for the first time.

> **Caveat.** Setting `digitalSourceType` on an ingredient is new in C2PA 2.4
> (§18.16.12.3) and most deployed validators do not yet support it; a manifest
> carrying it may display as "invalid" in those tools. The `c2pa.ai-disclosure`
> assertion alone satisfies AI-labeling requirements, so enable `set_source_type`
> only if you want forward compatibility and can tolerate that display today.

If the input already carries a manifest, or you are declaring an AI-generated asset
as an input to something else, express it as an ingredient instead — see
[5_ingredients.md](5_ingredients.md).

Recording richer provenance — the editing history of a parent asset, and the
software agents that acted on it — is available on the **Business tier**. Contact
[support@trufo.ai](mailto:support@trufo.ai) to discuss the right configuration for
your product.

---

## Combining With Identity

AI disclosure says what made the content; a CAWG identity assertion says who
published it. They are complementary and commonly used together:

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    assertions=[
        ["ai_disclosure", {"ai_disclosure_id": ai_disclosure_id}],
        ["cawg_identity", {"cawg_identity_id": "org_interim"}],
    ],
)
```

See [4_cawg_publish.md](4_cawg_publish.md). For test signing use `sign_c2pa_test()`
with a `c2pa-sign-test` key and `cawg_identity_id="test"`.

---

## Reference

- Assertion reference: [../api/api_c2pa.md](../api/api_c2pa.md#assertions)
- Complete runnable example: [3_ai_labeling.py](3_ai_labeling.py)
