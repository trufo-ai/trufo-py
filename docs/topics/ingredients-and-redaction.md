# Ingredients and Redaction

Declare source or contributing assets (`ingredient`), record edit histories (`parentOf` + `action_history`), run built-in media edits, and remove sensitive assertions (`redact`) from an incoming asset's manifest history.

---

## Declaring Ingredients

Each `["ingredient", {...}]` entry belongs in `assertions` (gathered by default). You can either send the ingredient's bytes (`media`, base64-encoded, in a format with **Yes** under C2PA validate in [Media Format Support](../reference/media-formats.md)), or declare it without bytes (`format`) for `componentOf` / `inputTo`:

- **`inputTo`:** An input to a computational process (prompt, model, dataset). Use `data_types` (e.g., `c2pa.types.generator.prompt`) and optionally embed up to 64 KB of base64 `data` alongside `format` (e.g., `text/plain`).
- **`componentOf`:** A placed component of a composite image, video, or audio mix.
- **`parentOf`:** The source asset before external edits produced the input file. Requires `media` and a Branded Generator Product (`branded_gp_id`).

Ingredient `media` is always sent inline as base64 inside the JSON `assertions` (there is no separate upload path for ingredients). In Local mode it stays on your host and only its hashes and lengths reach Trufo.

```python
import base64
from trufo import sign_c2pa_cloud

prompt = "A lighthouse at dusk, oil painting"

signed_bytes = sign_c2pa_cloud(
    api_key,
    media_bytes,
    assertions=[
        ["ingredient", {
            "relationship": "inputTo",
            "title": "prompt.txt",
            "data_types": [{"type": "c2pa.types.generator.prompt"}],
            "format": "text/plain",
            "data": base64.b64encode(prompt.encode("utf-8")).decode(),
        }],
        ["ingredient", {
            "relationship": "componentOf",
            "format": "video/webm",
            "title": "intro.webm",
        }],
    ],
)
```

Anyone with the signed file can read embedded `data` (notices warn above 8 KB; refused above 64 KB). When `media` is sent, any readable C2PA history on that ingredient is preserved; `signed_ingredient_policy` (`auto` or `keep`) controls how unreadable C2PA data is handled.

---

## Branded Provenance Declarations (`parentOf`, `action_history`, `creation`)

Recording `parentOf`, `action_history`, `creation`, or `placement: "created"` requires an approved Branded Generator Product (`branded_gp_id`), limited to the source types the product is approved for (on the test host, pass `branded_gp_id="test"`).

### Linking an externally edited parent (`parentOf` + `action_history`)

The edited input must not carry a C2PA manifest of its own: a readable manifest (even a stale or invalid one left behind by an editing tool) is kept as the input's parent, and a supplied `parentOf` is then refused (`400`). `signed_input_policy` offers only `"auto"` and `"keep"` — neither discards a readable manifest — so strip leftover C2PA data with an external tool before signing. (Under `"auto"`, C2PA data Trufo cannot read at all is removed automatically with a warning.)

```python
from trufo import sign_c2pa_cloud
from trufo.c2pa import DigitalSourceType, ManifestSettings

signed_bytes = sign_c2pa_cloud(
    api_key,
    edited_media_bytes,
    branded_gp_id="gp_...",
    manifest_settings=ManifestSettings(all_actions_included=True),
    assertions=[
        ["ingredient", {
            "relationship": "parentOf",
            "title": "original.png",
            "media": original_base64,
            "action_history": [
                {
                    "action": "c2pa.cropped",
                    "digitalSourceType": DigitalSourceType.HUMAN_EDITS.value,
                },
                {
                    "action": "c2pa.resized",
                    "digitalSourceType": DigitalSourceType.ALGORITHMICALLY_ENHANCED.value,
                    "placement": "created",
                },
            ],
        }],
    ],
)
```

### Declaring a newly created asset (`creation`)

Use `creation` only when the input has no existing manifest and was created directly by a registered software agent (`POST /c2pa/software-agent/add`):

```python
assertions = [[
    "creation",
    {
        "digitalSourceType": DigitalSourceType.TRAINED_ALGORITHMIC_MEDIA.value,
        "softwareAgent": {"software_agent_id": "swagent_..."},
        "description": "Generated from a text prompt",
    },
]]
```

**`all_actions_included`:** Standard signs default `allActionsIncluded` to `true`. Requests with `creation`, `parentOf`, `action_history`, or `placement: "created"` default it to `false` — pass `ManifestSettings(all_actions_included=True)` only when your manifest records every action since the parent (refused if `parentOf` has no `action_history`).

---

## Built-In Media Actions (`resize`, `crop`, `trim`, `transcode`, `repackage`)

When Trufo performs the edit itself, no `branded_gp_id` is needed — Trufo runs each action in order, records the C2PA action, preserves the incoming manifest as `parentOf`, and warns about any metadata the output format cannot hold:

```python
signed_bytes = sign_c2pa_cloud(
    api_key,
    media_bytes,
    actions=[
        ["crop", {"x": 0, "y": 0, "width": 1200, "height": 800}],
        ["resize", {"width": 800}],
        ["transcode", {"target_mime_type": "image/webp", "quality": 85}],
    ],
)
```

Note that `transcode` and `repackage` cannot be combined with a `c2pa.created` sign in the same request; sign first, then transcode the signed file.

---

## Redacting Assertions (`redact`)

Remove specific assertions from an incoming file's existing manifest history (across all prior generations) while preserving the rest of the provenance chain. Every redaction is recorded in the manifest's `redacted_assertions` list alongside its `reason`.

### Minimal example

```python
signed_bytes = sign_c2pa_cloud(
    api_key,
    signed_input_bytes,
    actions=[
        ["redact", {"label": "c2pa.metadata", "reason": "c2pa.PII.present"}],
    ],
)
```

### Rules to know

- **Supported labels:** `c2pa.metadata` (capture/GPS/device), `cawg.metadata` (byline/credit/rights), `cawg.training-mining`, and `cawg.identity`. To remove a contributor's identity completely, redact **both** `cawg.metadata` and `cawg.identity`. `custom` assertions and the automatic `ai.trufo.identity` assertion cannot be redacted.
- **Required `reason`:** One of `c2pa.PII.present`, `c2pa.invalid.data`, `c2pa.trade-secret.present`, `c2pa.government.confidential`, or a domain-validated reverse-DNS string (e.g., `com.example.internal-policy`).
- **Numbered instances:** If a manifest contains repeated labels (`c2pa.metadata`, `c2pa.metadata__1`), a bare label matches only the unnumbered one; add separate `redact` entries for numbered labels.
- **All-or-nothing:** Redaction fails (`400`) if the input has no C2PA manifest or if any named label does not exist anywhere in its history.
- **Always targets existing history:** Placing `redact` alongside `transcode` or `resize` sets where `c2pa.redacted` appears in the action list, but redaction always operates on the input's prior manifest history.

---

## Reference

- Full schemas, allowed `action_history` actions, and errors: [Actions and Assertions](../reference/actions-and-assertions.md)
- Media action format & metadata rules: [Media Format Support](../reference/media-formats.md#media-actions)
- Complete runnable script: [ingredients.py](ingredients.py)
