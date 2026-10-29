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
identifies AI generation; see the registration-dependent behavior below. For
`c2pa.created` with `trainedAlgorithmicMedia`, follow
[First-party model operation](#first-party-model-operation).

## Requirements

- A `c2pa-sign-test` or `c2pa-sign-prod` API key. See [0_setup.md](0_setup.md).
  AI labeling adds no plan requirement.
- Disclosures and software agents registered in the region you sign in:
  `api.trufo.ai` and `test.api.trufo.ai` share registrations; `eu.api.trufo.ai` keeps
  its own. See [Regions](../api/api_trufo.md#regions).
- For [first-party model operation](#first-party-model-operation) only: the Created
  Assertion Acknowledgement, accepted for your organization.

---

## Minimal Disclosure

One entry adds an AI disclosure with the default model type, the body
`{"modelType": "c2pa.types.model"}`:

```python
from trufo import sign_c2pa
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_PROD)

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

Registrations are per region: if you sign on `eu.api.trufo.ai`, use
`TRUFO_API_URL_EUROPE` in place of `TRUFO_API_URL` here and in the software-agent
registration below.

In the dashboard, register it on the C2PA Signing API page, **Playground** tab
([app.trufo.ai/prov/apis/c2pa-signing?tab=playground](https://app.trufo.ai/prov/apis/c2pa-signing?tab=playground)):
select **AI (Third-Party)** or **AI (First-Party)**, then **Register Entities** →
**Register AI Disclosure**. The dashboard registers in your organization's default
region.

`humanOversightLevel` is worth setting deliberately — it distinguishes fully
automated generation from human-directed or human-reviewed work:

| Value | Meaning |
| ----- | ------- |
| `fully_autonomous` | The model produced the asset without human direction |
| `prompt_guided` | A human directed the model but did not review the output |
| `human_validated` | A human reviewed and accepted the output |

See [api_c2pa.md](../api/api_c2pa.md#post-c2paai-disclosureadd) for the complete
schema. `POST /c2pa/ai-disclosure/list` returns each registration with its
`assertion`, which signing embeds verbatim as the `c2pa.ai-disclosure` assertion.

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

Over HTTP, including [Local mode with the Docker image](../local/docker.md#ai-labeling),
the entry is JSON: `["ai_disclosure", {"ai_disclosure_id": "aidisc_...", "set_source_type": true}]`.

`set_source_type` applies only to input with no C2PA manifest — content you are
signing for the first time — and has no effect on any other input. Check the result
at [verify.trufo.ai](https://verify.trufo.ai).

The ingredient form uses a C2PA 2.4 field; older validators may reject it.

If the input already carries a manifest, or you are declaring an AI-generated asset
as an input to something else, express it as an ingredient instead — see
[5_ingredients.md](5_ingredients.md).

### First-party model operation

If you are operating the model (i.e. running in-house as opposed to calling an API,
or otherwise conducting "AI Provider" operations per the EU AI Act definitions),
then you may declare `c2pa.created` with `digitalSourceType=trainedAlgorithmicMedia`.
This ensures that downstream validators (especially those that are not up to date)
will reliably mark the content as AI-generated. Note that if C2PA security
requirements increase in the future, this feature may be moved to the
"branded-only" category that requires a bespoke Generator Product registration
with the C2PA.

1. **Accept the Created Assertion Acknowledgement.** An organization owner or admin
   accepts it on behalf of the organization at
   [Organization Settings → Agreements](https://app.trufo.ai/settings/org#agreements),
   as it is important that this feature is not used to write inaccurate information.
2. **Register the software agent** that generates the media:

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

3. **Register the AI disclosure** as in [Register it](#register-it), with these
   fields alongside `assertion`:

   ```python
   "first_party_operated": True,
   "software_agent_id": swagent_id,
   ```

4. **Sign with `set_source_type=True`**, as in [Marking the Source Type](#marking-the-source-type).

In the dashboard, steps 2 and 3 are on the C2PA Signing API page, **Playground** tab:
select **AI (First-Party)**, then under **Register Entities** use **Register Software
Agent**, then **Register AI Disclosure** with **My organization operates this model**
checked and the agent selected. The dashboard registers in your organization's
default region.

These registration fields are not embedded in the AI disclosure. The linked software
agent's `agent` map (see `POST /c2pa/software-agent/list`) becomes the
`softwareAgent` of `c2pa.created`: its name and optional version/OS identify the
application that created the media. The AI disclosure remains a gathered assertion.

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
