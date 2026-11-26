# AI Labeling

Register an AI system once, then reference it when signing to attach compliant C2PA AI disclosures (`digitalSourceType` + `c2pa.ai-disclosure`).

For compliance strategy (EU AI Act Art. 50, California SB 942, first-party vs. third-party models, and `ai_modified` workflows), see [AI Labeling for Compliance](../guides/ai-labeling-for-compliance.md).

## Requirements

- `trufo` 2.2.0+ (and `trufo-provenance` 2.2.0+ in Local mode).
- A `c2pa-sign-test` or `c2pa-sign-prod` key (no extra plan required for AI labeling).
- For a first-party AI system (`c2pa_first_party_attestable: true`): an owner or admin must accept the **Created Assertion Acknowledgement** at [Organization Settings → Agreements](https://app.trufo.ai/settings/org#agreements) (automated agents may not accept legal agreements).

---

## Step 1 — Register an AI System

Register each model/version once on a production host (`https://api.trufo.ai` or `https://eu.api.trufo.ai`) using either a test or production key. Registrations are immutable (register a new AI system for each new model version) and work across both Global and Europe endpoints as well as the test host.

```python
import requests

from trufo.api.endpoints import TPS_AI_SYSTEM_ADD_PATH, TRUFO_API_URL
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_PROD)  # or C2PA_SIGN_TEST

resp = requests.post(
    TRUFO_API_URL + TPS_AI_SYSTEM_ADD_PATH,
    headers={"X-API-Key": api_key},
    json={
        "name": "<AI_SYSTEM_NAME>",
        "version": "<AI_SYSTEM_VERSION>",
        "ai_involvement_modes": ["ai_generated"],
        "c2pa_first_party_attestable": True,  # only if your org operates the model
        "c2pa_ai_disclosure": {"modelType": "c2pa.types.model"},
    },
    timeout=60,
)
resp.raise_for_status()
ai_system_id = resp.json()["ai_system_id"]  # "aisys_..."
```

Registering an AI system assigns one watermark ID per involvement mode (see [Watermark billing](../reference/watermarking-api.md#watermark-billing)). Its name, version, model disclosure, and your organization's validated legal name can appear publicly in signed manifests and watermark lookups.

You can list systems with `POST /ai-system/list` and deactivate/reactivate one with `POST /ai-system/status`.

---

## Step 2 — Sign With the AI System

Add an `ai_system` entry to `assertions`:

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

Over HTTP (including [Local Signing (Docker)](signing-local-docker.md)):

```json
["ai_system", {"ai_system_id": "aisys_...", "ai_involvement": "ai_generated"}]
```

### What Trufo writes on an unsigned input

1. **With `branded_gp_id`:** Signed as your Branded Generator Product (`c2pa.created` with `trainedAlgorithmicMedia` for `ai_generated`, or `compositeWithTrainedAlgorithmicMedia` for `ai_modified`).
2. **First-party AI system (`c2pa_first_party_attestable: true`):** Signed with `c2pa.created` (`trainedAlgorithmicMedia`) whose software agent is the AI system.
3. **Non-first-party AI system (`c2pa_first_party_attestable: false`):** Recorded as a declared AI parent ingredient (`trainedAlgorithmicMedia`) opened by your organization (`c2pa.opened`).

Signing `ai_modified` content requires a `branded_gp_id` approved for `compositeWithTrainedAlgorithmicMedia`.

### What happens if the input already carries a C2PA manifest

- Under the default `signed_input_policy: "auto"`, Trufo keeps the existing manifest and declares no new source type — **except** when the input's source class is `camera_captured` or `human_created`, which Trufo rejects (`400`) **regardless of the request's actions**.
- Setting `signed_input_policy` to `"keep"` skips the source-class check and keeps the existing manifest without declaring a new AI source type.

See [Signed inputs and ingredients](../reference/actions-and-assertions.md#signed-inputs-and-ingredients) for the full source-class rules.

---

## Step 3 — Optionally Watermark per AI System

For lightweight EU AI Act Article 50(2) marking, embed the AI system's shared watermark ID by adding a `watermark` action alongside the `ai_system` assertion:

```python
signed_bytes = sign_c2pa_cloud(
    api_key,
    media_bytes,
    assertions=[
        ["ai_system", {"ai_system_id": ai_system_id, "ai_involvement": "ai_generated"}],
    ],
    actions=[
        ["watermark", {"wid_allocation_mode": "per_ai_system"}],
    ],
)
```

See [Watermarking and Recovery](watermarking.md) for `effort_policy` and `per_embed` vs. `per_ai_system` details.

---

## Combining With Organization Identity

Pair `ai_system` (what made it) with `cawg_identity` (who published it):

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

On the test host, use `sign_c2pa_cloud_test()` with `c2pa-sign-test` and `cawg_identity_id="test"`.

---

## Troubleshooting

- **`404 AISystemNotFound`:** The `ai_system_id` is unknown or belongs to another organization (`/ai-system/list` lists yours).
- **`400 AISystemInactive`:** Reactivate with `/ai-system/status` (`"status": "active"`) or switch to an active system.
- **`400 ai_involvement 'ai_modified' requires a branded generator product`:** Pass a `branded_gp_id` approved for `compositeWithTrainedAlgorithmicMedia`.
- **`400` source-class conflict (`camera_captured` / `human_created`):** The input carries a camera or human-created manifest. Verify the input, or pass `signed_input_policy="keep"` / omit `ai_system`.
- **Migrating from `ai_disclosure`?** See [Deprecations](../reference/deprecations.md).

---

## Reference

- `ai_system` assertion & `/ai-system/*` endpoints: [Actions and Assertions](../reference/actions-and-assertions.md#ai_system)
- Complete runnable script: [ai_labeling.py](ai_labeling.py)
