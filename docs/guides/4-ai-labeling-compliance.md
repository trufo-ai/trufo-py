# 4. AI Labeling and Compliance

Set up machine-readable AI labels on generated and AI-edited media: a quick compliance path, the additions for full compliance, and the `digitalSourceType` cases that commonly cause refusals or unexpected labels.

Which obligations apply to you, and from when, depends on your jurisdiction and product (for example EU AI Act Article 50 or California SB 942). This guide covers the technical setup.

---

## 1. Quick Compliance vs. Full Compliance

| | Quick compliance (current deadlines) | Full compliance (2027 and later enforcement, durable auditability) |
| --- | --- | --- |
| AI label | AI-generated label: a C2PA `ai_system` assertion with `ai_involvement: "ai_generated"`, using a registered first-party AI system | Same, plus AI-edit labels (`ai_modified`) for AI edits and composites |
| Signing route | Standard Trufo signing, Cloud or Local | [Branded Generator Product](3-product-signing-setup.md) (BPV) where you declare AI edits, composites, or edits of user assets |
| Watermark | Optional `per_ai_system` watermark (one shared ID per AI system; identifies your organization and AI system) | `per_embed` watermark per file, so the full manifest can be recovered after platforms strip C2PA metadata ([8. Watermarking with Pawprint](8-watermarking-with-pawprint.md)) |
| Publisher identity | Organization identity added automatically (`ai.trufo.identity`) | Active OV, an organization CAWG identity (`cawg_identity` with `"org_interim"`), and AI-training preferences (`cawg_training`) |
| Inputs and sources | Single first-party model output | Ingredient provenance for multi-model and third-party pipelines: inputs (`inputTo`), components (`componentOf`), and edited originals (`parentOf`) |
| Data residency | Any host | `eu.api.trufo.ai` or Local mode where media must stay in the EU or on your infrastructure |
| Validation required | OV (production) | OV (plus BPV if declaring AI edits, composites, or edits of user assets) |

You can start with quick compliance and add the full-compliance pieces later.

---

## 2. Starter Path: First-Party AI Generator

This path applies when your organization operates the model that generated the output.

### Prerequisites

- Account, MFA, and a `c2pa-sign-test` key ([2. Trufo Account Setup](2-trufo-account-setup.md)).
- The *Created Assertion Acknowledgement* ([Agreements](2-trufo-account-setup.md#agreements)); registering a first-party AI system returns `403` without it.
- For production: active OV, a C2PA Signing plan, and a `c2pa-sign-prod` key.

### Register the AI system once

Register on a production host (`api.trufo.ai` or `eu.api.trufo.ai`) with either a test or production key. Registrations are immutable, cannot be deleted, and are shared across all hosts including `test.api.trufo.ai`. Register a new AI system for each model version, and include `"ai_modified"` in `ai_involvement_modes` only if you will sign AI edits under a Branded Generator Product.

```python
import requests

from trufo.api.endpoints import TPS_AI_SYSTEM_ADD_PATH, TRUFO_API_URL
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_TEST)  # a c2pa-sign-prod key is also accepted

resp = requests.post(
    TRUFO_API_URL + TPS_AI_SYSTEM_ADD_PATH,
    headers={"X-API-Key": api_key},
    json={
        "name": "<MODEL_NAME>",
        "version": "<MODEL_VERSION>",
        "ai_involvement_modes": ["ai_generated"],
        "c2pa_first_party_attestable": True,
        "c2pa_ai_disclosure": {"modelType": "c2pa.types.model"},
    },
    timeout=60,
)
resp.raise_for_status()
print(resp.json()["ai_system_id"])  # "aisys_..."; store it in your configuration
```

The AI system's name, version, and model disclosure can appear publicly in signed manifests and watermark lookups. `c2pa_ai_disclosure` is optional; when present, Trufo writes a `c2pa.ai-disclosure` assertion on every sign that names the AI system.

### Sign on the test host, then production

```python
from pathlib import Path

from trufo import sign_c2pa_cloud_test
from trufo.util.credentials import TrufoAPIKey, load_api_key

AI_SYSTEM_ID = "aisys_..."

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_TEST)
signed_bytes = sign_c2pa_cloud_test(
    api_key,
    Path("generated.png").read_bytes(),  # model output without a C2PA manifest
    manifest_title="generated.png",
    assertions=[
        ["ai_system", {"ai_system_id": AI_SYSTEM_ID, "ai_involvement": "ai_generated"}],
    ],
    actions=[
        ["watermark", {"wid_allocation_mode": "per_ai_system", "effort_policy": "require_if_supported"}],
    ],
)
Path("labeled.png").write_bytes(signed_bytes)
```

On an unsigned input, a first-party AI system produces a `c2pa.created` action with `digitalSourceType` `trainedAlgorithmicMedia` and the AI system as software agent. The `watermark` action is optional; remove it to sign without a watermark.

For production, use `sign_c2pa_cloud()` (or `sign_c2pa_local()`) with a `c2pa-sign-prod` key; the `assertions` and `actions` are unchanged. The runnable script is [ai_labeling.py](../topics/ai_labeling.py).

---

## 3. When You Need a Branded Generator Product

Standard signing covers `ai_generated` output from a first-party model. A Branded Generator Product ([3. Product Signing Setup](3-product-signing-setup.md#4-branded-product-validation-bpv-and-product-validation-pv)) is needed when:

- **Declaring AI edits or composites:** `ai_involvement: "ai_modified"` writes `compositeWithTrainedAlgorithmicMedia` and requires a `branded_gp_id` approved for that source type (`400` without one).
- **Editing user-uploaded media:** linking the original with a `parentOf` ingredient and recording edits in `action_history`, or declaring `creation` or `placement="created"` (see section 4).
- **Signing under your own product name:** a self-serve BPV certificate carries your product name (`CN`) with `O=Trufo Inc.`; to have your own organization in `O`, contact [support@trufo.ai](mailto:support@trufo.ai).

Prototype these on `test.api.trufo.ai` with `branded_gp_id="test"` and an AI system registered with `"ai_modified"` in `ai_involvement_modes`:

```python
signed_bytes = sign_c2pa_cloud_test(
    api_key,  # c2pa-sign-test key
    Path("ai_edit.png").read_bytes(),  # without a C2PA manifest
    branded_gp_id="test",
    assertions=[["ai_system", {"ai_system_id": AI_SYSTEM_ID, "ai_involvement": "ai_modified"}]],
)
```

---

## 4. `digitalSourceType` Issues and Third-Party Setups

### Wrapping a third-party AI API

If you call a model you do not operate, do not register it as first-party. Two supported patterns:

- **Register with `c2pa_first_party_attestable: false`.** Signing with that AI system records the output as a declared AI parent ingredient (`trainedAlgorithmicMedia`) opened by your organization (`c2pa.opened`), not as a `c2pa.created` action.
- **Declare third-party outputs as ingredients.** Add `inputTo` or `componentOf` ingredients with an ingredient-level `digital_source_type`. Only `trainedAlgorithmicMedia` and `compositeWithTrainedAlgorithmicMedia` can be written on an ingredient, and `digital_source_type` cannot be combined with ingredient `media` that carries its own C2PA manifest.

```python
from pathlib import Path

from trufo import sign_c2pa_cloud_test
from trufo.c2pa import DigitalSourceType
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_TEST)
signed_bytes = sign_c2pa_cloud_test(
    api_key,
    Path("composite.png").read_bytes(),
    manifest_title="composite.png",
    assertions=[
        ["ingredient", {
            "relationship": "componentOf",
            "title": "background.png",
            "format": "image/png",
            "digital_source_type": DigitalSourceType.TRAINED_ALGORITHMIC_MEDIA.value,
        }],
    ],
)
Path("composite_signed.png").write_bytes(signed_bytes)
```

Validators and platforms may display these disclosures differently from a `c2pa.created` action, or not at all. Test sample outputs against the validators that matter to you. If the upstream provider already signs its output with C2PA, Trufo keeps that manifest as the parent under the default `signed_input_policy: "auto"` and writes no new source type.

### User uploads that carry a camera or human-created manifest

Under the default `signed_input_policy: "auto"`, an `ai_system` assertion triggers a source-class check on the input's manifest chain. Inputs classified as `camera_captured` or `human_created` are refused (`400`), whatever the request's actions, so the new manifest does not contradict the existing provenance.

- `signed_input_policy: "keep"` skips the refusal, but it only preserves the incoming manifest: no `c2pa.created` and no new AI source type are written.
- To declare an AI edit of a user photo, sign the **edited output** under your `branded_gp_id`, attach the **original photo** as a `parentOf` ingredient, and record the edit in `action_history` with `compositeWithTrainedAlgorithmicMedia`. Omit `ai_system`: it cannot be combined with `parentOf` when `branded_gp_id` is set. The edited file must not carry a C2PA manifest of its own, because a readable manifest is kept as the parent and the supplied `parentOf` is then refused (`400`).

The `assertions` for that request:

```python
assertions=[["ingredient", {
    "relationship": "parentOf",
    "title": "user_photo.jpg",
    "media": original_b64,  # base64 of the original photo
    "action_history": [{
        "action": "c2pa.edited",
        "digitalSourceType": DigitalSourceType.COMPOSITE_WITH_TRAINED_ALGORITHMIC_MEDIA.value,
    }],
}]],
```

See [Ingredients and Redaction](../topics/ingredients-and-redaction.md#linking-an-externally-edited-parent-parentof--action_history) for a complete example.

### Inputs with remote manifests

Some files carry a URL to a remote manifest instead of an embedded one; Trufo fetches it from allowed hosts and applies the same rules as an embedded manifest. If it cannot be fetched, a request with `ai_system` or `creation` is refused under `"auto"` with `400 RemoteManifestUnavailable`; see [Remote Manifests](../reference/actions-and-assertions.md#remote-manifests) for the allowed-host settings.

---

## 5. Production Rollout and Verification

1. Complete OV and subscribe to a C2PA Signing plan ([2. Trufo Account Setup](2-trufo-account-setup.md)); for `ai_modified` or edits of user media, obtain an approved `branded_gp_id` ([3. Product Signing Setup](3-product-signing-setup.md)).
2. Switch to a `c2pa-sign-prod` key and `sign_c2pa_cloud()` / `sign_c2pa_local()`, targeting `https://api.trufo.ai` or `https://eu.api.trufo.ai` (`trufo_api_url=TRUFO_API_URL_EUROPE`).
3. Add publisher identity and training preferences for the full tier:

```python
from pathlib import Path

from trufo import sign_c2pa_cloud
from trufo.util.credentials import TrufoAPIKey, load_api_key

AI_SYSTEM_ID = "aisys_..."

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_PROD)
signed_bytes = sign_c2pa_cloud(
    api_key,
    Path("generated.png").read_bytes(),
    manifest_title="generated.png",
    assertions=[
        ["ai_system", {"ai_system_id": AI_SYSTEM_ID, "ai_involvement": "ai_generated"}],
        ["cawg_training", {"assertion": {"entries": {
            "cawg.ai_generative_training": {"use": "notAllowed"},
        }}}],
        ["cawg_identity", {"cawg_identity_id": "org_interim"}],  # requires cawg_cert_organization
    ],
    actions=[
        ["watermark", {"wid_allocation_mode": "per_embed", "effort_policy": "require_if_supported"}],
    ],
)
Path("labeled.png").write_bytes(signed_bytes)
```

4. Choose the watermark allocation mode and effort policy for your formats ([8. Watermarking with Pawprint](8-watermarking-with-pawprint.md)).
5. Verify sample outputs: `c2pa.actions` should show `c2pa.created` with `trainedAlgorithmicMedia` (or `compositeWithTrainedAlgorithmicMedia`), plus `c2pa.ai-disclosure` where requested. A `per_embed` watermark also writes `c2pa.soft-binding`; a `per_ai_system` watermark writes `c2pa.watermarked.unbound` without `c2pa.soft-binding` ([Verification](../topics/verification.md)).
6. Monitor `TrufoServerWarning` notices, which report skipped watermarks and kept incoming manifests ([Error Handling](../topics/error-handling.md#non-fatal-server-warnings-trufoserverwarning)).

---

## Reference

- AI system registration and signing behavior: [AI Labeling](../topics/ai-labeling.md)
- Publisher identity and training preferences: [CAWG Identity and Metadata](../topics/cawg-identity.md)
- Source types, created vs. gathered assertions: [C2PA Manifests, Actions, and Assertions](../topics/c2pa-manifests.md)
- `parentOf`, `action_history`, and ingredients: [Ingredients and Redaction](../topics/ingredients-and-redaction.md)
- Manifest retention and thumbnails: [Storage Options and Privacy](../topics/storage-options.md)
- Watermark modes and recovery: [Watermarking and Recovery](../topics/watermarking.md)
- Checking outputs: [Verification](../topics/verification.md)
- `ai_system`, source-class rules, and `/ai-system/*`: [Actions and Assertions](../reference/actions-and-assertions.md#ai_system)
