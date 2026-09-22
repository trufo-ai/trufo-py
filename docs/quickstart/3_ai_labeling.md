# Quickstart: AI Labeling

Disclose that content was generated or assisted by AI, in a way validators and
platforms recognize.

## What This Does

C2PA carries AI disclosure in two independent places, and they answer different
questions:

| Signal | Question it answers | Where it lives |
| ------ | ------------------- | -------------- |
| `c2pa.ai-disclosure` assertion | *What model made this, and with how much human oversight?* | An assertion in your manifest |
| `digitalSourceType` | *Is this asset itself AI-generated?* | A field on the creation action or ingredient |

The AI disclosure describes the model and human oversight. The source type
identifies AI generation; see the registration-dependent behavior below.

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

Use this when you do not want to publish details about the model.

---

## Detailed Disclosure

To name the model, its framework, or the level of human oversight, register the
disclosure once and reference it by id. Inline bodies are rejected at signing time —
registering lets you reuse the same disclosure across the assets you sign.

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

`set_source_type=True` records `digitalSourceType = trainedAlgorithmicMedia`.
For first-party model operation registered as described below, it accompanies
`c2pa.created` and the linked software agent. Otherwise, it is recorded on the
input ingredient.

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

The ingredient form uses a C2PA 2.4 field; older validators may reject it.

If the input already carries a manifest, or you are declaring an AI-generated asset
as an input to something else, express it as an ingredient instead — see
[5_ingredients.md](5_ingredients.md).

### First-party model operation

If you are operating the model (i.e. running in-house as opposed to calling an API,
or otherwise conducting "AI Provider" operations per the EU AI Act definitions),
then you may declare `c2pa.created` with `digitalSourceType=trainedAlgorithmicMedia`
by (1) in the AI disclosure, setting `first_party_operated=True` and linking a
registered software agent with `software_agent_id={swagent_id}`, and (2) setting
`set_source_type=True` when making the C2PA signing call. This ensures that
downstream validators (especially those that are not up to date) will reliably
mark the content as AI-generated.

In order to use this feature, an authorized
signatory must accept the Created Assertion Acknowledgement (in Organization
Settings → Agreements) on behalf of the organization, as it is important that
this feature is not used to write inaccurate information. Note that if C2PA
security requirements increase in the future, this feature may be moved to the
"branded-only" category that requires a bespoke Generator Product registration
with the C2PA.

Register the software agent first:

```python
from trufo.api.endpoints import TPS_C2PA_SOFTWARE_AGENT_ADD

resp = requests.post(
    TRUFO_API_URL + TPS_C2PA_SOFTWARE_AGENT_ADD,
    headers={"X-API-Key": api_key},
    json={"agent": {"name": "<generating application name>", "version": "<version>"}},
    timeout=60,
)
resp.raise_for_status()
swagent_id = resp.json()["software_agent_id"]
```

Include the following alongside `assertion` in your disclosure registration:

```python
"first_party_operated": True,
"software_agent_id": swagent_id,
```

These registration fields are not embedded in the AI disclosure. The software
agent's name and optional version/OS identify the application that created the
media. The AI disclosure remains a gathered assertion.

This creation workflow is for AI-generated output. It does not represent the
history of a photograph subsequently edited with generative AI. The source type
is fixed to `trainedAlgorithmicMedia`.

See the [registration reference](../api/api_c2pa.md#post-c2paai-disclosureadd)
for field requirements and errors.

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
