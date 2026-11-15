# Quickstart: AI Labeling

When signing, you label content by naming the registered AI system that generates
or modifies it.

## What This Does

C2PA carries AI disclosure in two independent places, and they answer different
questions:

| Signal | Question it answers | Where it lives |
| ------ | ------------------- | -------------- |
| `c2pa.ai-disclosure` assertion | *What model made this, and with how much human oversight?* | An assertion in your manifest |
| `digitalSourceType` | *Is this asset itself AI-generated?* | A field on the creation action or ingredient |

If your organization operates a generative model, Trufo recommends declaring its
output with a `c2pa.created` action carrying
`digitalSourceType = trainedAlgorithmicMedia`, alongside the `c2pa.ai-disclosure`
assertion. This is the signal that today's C2PA validators most reliably surface as
AI-generated.

## Requirements

- trufo 2.2.0 or later (trufo 2.1 refuses an `ai_system` entry before sending it);
  in Local mode, also trufo-provenance 2.2.0 or later.
- A `c2pa-sign-test` or `c2pa-sign-prod` API key ([0_setup.md](0_setup.md)); AI
  labeling adds no plan requirement.
- Registration on a production host, `api.trufo.ai` (`TRUFO_API_URL`) or
  `eu.api.trufo.ai` (`TRUFO_API_URL_EUROPE`), with either key; the AI system works
  on every [regional endpoint](../api/api_trufo.md#regions).
- For a [first-party](#step-1--confirm-you-are-the-first-party-operator) AI system,
  the Created Assertion Acknowledgement ([step 2](#step-2--register-an-ai-system)).

---

## Step 1 — Confirm You Are the First-Party Operator

“First-party” means a client-side generative AI model outputs the content, and your
organization's client-side application routes it to Trufo to be signed, identifying
the AI system you registered with Trufo. Otherwise, register the AI system without
first-party: its content is then labeled as a declared AI ingredient
([step 3](#step-3--sign-with-the-ai-system)).

## Step 2 — Register an AI System

In the [Playground](https://app.trufo.ai/prov/apis/c2pa-signing?tab=playground),
choose the AI profile and register it under Register Entities → AI System. In the
API, use `POST /ai-system/add` below, with a test or production key. For a
first-party AI system (`c2pa_first_party_attestable: true`), an organization owner
or admin must first accept the Created Assertion Acknowledgement in
[Organization Settings → Agreements](https://app.trufo.ai/settings/org#agreements);
an automated agent may not accept it.

Its details cannot be changed after registration: register each new version as a
new AI system. Registrations are shared between test and production signing. The
recommended `c2pa.ai-disclosure` assertion comes from the optional model disclosure
(`c2pa_ai_disclosure`).

Registering an AI system
[issues one new watermark ID per type of AI involvement](../api/api_c2pa.md#watermark-billing).
Its name, version, model disclosure and your organization's validated legal name
can appear publicly in signed content and watermark lookups.

```python
import requests

from trufo.api.endpoints import TPS_AI_SYSTEM_ADD_PATH, TRUFO_API_URL
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_PROD)  # or TrufoAPIKey.C2PA_SIGN_TEST

resp = requests.post(
    TRUFO_API_URL + TPS_AI_SYSTEM_ADD_PATH,
    headers={"X-API-Key": api_key},
    json={
        "name": "<AI_SYSTEM_NAME>",
        "version": "<AI_SYSTEM_VERSION>",
        "ai_involvement_modes": ["ai_generated"],
        "c2pa_first_party_attestable": True,  # only if step 1 applies
        "c2pa_ai_disclosure": {"modelType": "c2pa.types.model"},
    },
    timeout=60,
)
resp.raise_for_status()
ai_system_id = resp.json()["ai_system_id"]
```

The response is `{"ai_system_id": "aisys_…"}`. See
[`POST /ai-system/add`](../api/api_c2pa.md#post-ai-systemadd) for the fields, the
`c2pa_ai_disclosure` body and the errors, and [AI Systems](../api/api_c2pa.md#ai-systems)
to list your AI systems or switch one off.

## Step 3 — Sign With the AI System

In the API, add one `ai_system` assertion to `assertions`:

```python
from trufo import sign_c2pa_cloud

signed_bytes = sign_c2pa_cloud(
    api_key,
    media_bytes,
    assertions=[
        ["ai_system", {"ai_system_id": ai_system_id, "ai_involvement": "ai_generated"}],
    ],
)
```

Over HTTP, including [Local mode with the Docker image](../local/docker.md#ai-labeling),
the entry is JSON:

```json
["ai_system", {"ai_system_id": "aisys_…", "ai_involvement": "ai_generated"}]
```

An input without a C2PA manifest is labeled by the first of these that applies:

- Branded generator product (`branded_gp_id` set): signed as your branded generator
  product.
- Trufo AI Labeling Service (first-party AI system): signed with a `c2pa.created`
  action (`digitalSourceType = trainedAlgorithmicMedia`) whose software agent is the
  AI system.
- Declared AI ingredient (not first-party): the input is recorded as an AI-generated
  parent ingredient (`digitalSourceType = trainedAlgorithmicMedia`) and opened by
  your organization (`c2pa.opened`). This is not generally sufficient for
  interoperable AI disclosures.

Signing AI-modified content (`ai_modified`) requires a branded generator product.

If the input already carries a C2PA manifest, Trufo keeps it and declares no new
source type. If that manifest says camera-captured or human-created, the input is
rejected. This is the default
[`signed_input_policy`](../api/api_c2pa.md#signed-inputs-and-ingredients), `auto`;
with `keep`, that input is kept too, and no AI source type is declared for it.

Under `auto`, a `redact` or `transcode` action also keeps such an input;
[Signed inputs and ingredients](../api/api_c2pa.md#signed-inputs-and-ingredients)
lists every case.

Test signing (`sign_c2pa_cloud_test()` with a `c2pa-sign-test` key) gives the same labels,
with the test certificate. Check the result at [verify.trufo.ai](https://verify.trufo.ai).

## Step 4 — Optionally, Watermark per AI System

For companies seeking minimal compliance with the EU AI Act Article 50(2),
per-AI-system watermarking embeds a single watermark ID in all content a registered
AI system generates. The AI system can be identified, but individual content
provenance records (e.g. C2PA soft-binding) cannot.

In the API, add this to `actions`, in a request with the `ai_system` assertion:

```json
["watermark", {"wid_allocation_mode": "per_ai_system"}]
```

See [the `watermark` action](6_watermarking.md#the-watermark-action) for its options,
and [Binding Without Trufo Signing](6_watermarking.md#binding-without-trufo-signing)
to watermark media you sign yourself.

---

## Combining With Identity

The `ai_system` entry says what made the content; a CAWG identity assertion says
who published it. They are complementary and commonly used together:

```python
signed_bytes = sign_c2pa_cloud(
    api_key,
    media_bytes,
    assertions=[
        ["ai_system", {"ai_system_id": ai_system_id, "ai_involvement": "ai_generated"}],
        ["cawg_identity", {"cawg_identity_id": "org_interim"}],
    ],
)
```

See [4_cawg_publish.md](4_cawg_publish.md). For test signing use `sign_c2pa_cloud_test()`
with a `c2pa-sign-test` key and `cawg_identity_id="test"`.

---

<!-- TODO(sunset-2027-01-31): the ai_disclosure migration section goes; successor none -->

## Moving From `ai_disclosure`

The `ai_disclosure` assertion is deprecated and will stop working after
2027-01-31T23:59:00+00:00. Please use the `ai_system` assertion with an AI system
registered at `/ai-system/add`.

| Old (`ai_disclosure`) | New (`ai_system`) |
| --------------------- | ----------------- |
| `["ai_disclosure", {}]` | Register an AI system ([step 2](#step-2--register-an-ai-system)). Every label of an input without a C2PA manifest declares an AI source type; there is no disclosure-only label. |
| `ai_disclosure_id` | An AI system with `c2pa_ai_disclosure` |
| `first_party_operated` + `software_agent_id` | `c2pa_first_party_attestable`; the AI system's `name` and `version` are the software agent |
| `set_source_type` | Automatic ([step 3](#step-3--sign-with-the-ai-system)) |
| `aidisc_…` registrations | Not converted |

---

## Troubleshooting

All `ai_system` errors are listed under [`ai_system`](../api/api_c2pa.md#ai_system);
the common ones:

**`404 AISystemNotFound`**

The `ai_system_id` is unknown or belongs to another organization;
[`/ai-system/list`](../api/api_c2pa.md#post-ai-systemlist) lists yours.

**`AISystemInactive: AI system '<ai_system_id>' is inactive. Use an active AI system (see /ai-system/list).`**

Use an active AI system, or reactivate this one with
[`/ai-system/status`](../api/api_c2pa.md#post-ai-systemstatus) (`"status": "active"`).

**`ai_involvement 'ai_modified' requires a branded generator product (branded_gp_id).`**

Pass `branded_gp_id`, one of your organization's branded generator products
approved for `compositeWithTrainedAlgorithmicMedia`
([`POST /c2pa/sign`](../api/api_c2pa.md#post-c2pasign)).

**`The input carries a C2PA manifest whose source class is '<class>', which conflicts with ai_involvement '<ai_involvement>'.`**

The input's manifest says camera-captured or human-created
([step 3](#step-3--sign-with-the-ai-system)). Check that the input is the AI
system's output. To sign it anyway, set `signed_input_policy` to `keep`; no AI
source type is declared.

**`UnsupportedSDKVersion: the 'ai_system' assertion requires trufo-provenance 2.2.0 or later. Please upgrade.`**

Local mode: upgrade trufo-provenance to 2.2.0 or later. The Docker image reports its
`engine_version` at `/health`; see [Versions and Upgrades](../local/docker.md#versions-and-upgrades).

---

## Reference

- `ai_system` assertion: [../api/api_c2pa.md#ai_system](../api/api_c2pa.md#ai_system)
- AI system registration: [../api/api_c2pa.md#ai-systems](../api/api_c2pa.md#ai-systems)
- Watermarking quickstart: [6_watermarking.md](6_watermarking.md)
- Complete runnable example: [3_ai_labeling.py](3_ai_labeling.py)
