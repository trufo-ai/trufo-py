# Quickstart: Ingredients

Manage the ingredients of a signed asset — the prior assets carried into its manifest.

## Declaring Ingredients

Describe prior or contributing assets in the manifest. Each
`["ingredient", {...}]` entry belongs in `assertions`; it is gathered by default.

Three relationships are available. Entries may carry base64 `media`, which is
validated when it has provenance and thumbnailed when supported:

- **`inputTo`** — an input to a computational process: a prompt, model, or dataset. Use `data_types` to say which (`c2pa.types.prompt`, `c2pa.types.model`, `c2pa.types.dataset`, ...).
- **`componentOf`** — a placed component of a composition; requires `media` in a thumbnail-capable image format.
- **`parentOf`** — the source asset before the edits represented by the active
  input. It requires `media`, is always a created declaration, and there may be
  at most one.

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    assertions=[
        ["ingredient", {"relationship": "inputTo", "title": "prompt.txt",
                        "data_types": [{"type": "c2pa.types.prompt"}]}],
    ],
)
```

## Branded provenance declarations

The forms below require a branded business product. The API rejects them when
the signing organization is not authorized.

Use `parentOf` when asset A was edited into the supplied asset B. Record the
operations between A and B in that ingredient's `action_history`; individual
eligible entries can use `placement="created"`:

```python
assertions = [[
    "ingredient",
    {
        "relationship": "parentOf",
        "title": "source-a.png",
        "media": source_a_base64,
        "action_history": [
            {"action": "c2pa.cropped"},
            {"action": "c2pa.resized", "placement": "created"},
        ],
    },
]]
```

Use the separate `creation` assertion only when the supplied asset itself was
created by the declared registered software agent. It cannot be combined with
`parentOf` and the input must not already contain a manifest:

```python
from trufo.c2pa import DigitalSourceType

assertions = [[
    "creation",
    {
        "digitalSourceType": DigitalSourceType.TRAINED_ALGORITHMIC_MEDIA.value,
        "softwareAgent": {"software_agent_id": "swagent_..."},
    },
]]
```

Creation and `parentOf` are always placed in the created claim set. Eligible AI,
custom, component, and input assertions opt in with an inline
`"placement": "created"`; CAWG assertions do not support created placement.

Normal signing defaults `allActionsIncluded` to true. Elevated requests
(creation, `parentOf`, action history, or a created placement) default it to
false. Set `ManifestSettings(all_actions_included=True)` only when your product
is authorized and the declaration really is complete.

See [api_c2pa.md](../api/api_c2pa.md) for the full parameter reference and conflict rules.

## Redaction

Remove specific assertions from a media file's existing C2PA manifest history.

### What This Does

Redaction is expressed as a `redact` **action** in the `actions` list. Each entry names one assertion and removes it from wherever it lives in the input's provenance chain: not just the immediate parent, but any earlier generation too. Repeat the entry to redact several assertions, each with its own reason. This is useful for stripping sensitive metadata (e.g. embedded camera/device metadata in `c2pa.metadata`) while preserving the rest of the provenance record and the file's continuity. Every redaction is recorded in the resulting manifest's `redacted_assertions` list, so the fact that a redaction happened, and which assertion was removed, is always part of the record.

Redaction removes whole assertions; individual fields within an assertion cannot be removed separately. Redaction is limited to the labels listed below; any other label, or a label that does not exist anywhere in the input's manifest history, fails the request.

### Requirements

- A `c2pa-sign-prod` or `c2pa-sign-test` API key, same as any other signing call. See
[0_setup.md](0_setup.md).
- The input file must already have a C2PA manifest — redacting a file with no existing
provenance history fails.
- The `redact` action is available on all signers: the fully-server signers (`sign_c2pa`,
`sign_c2pa_test`, `sign_c2pa_s3`, `sign_c2pa_s3_test`, `sign_c2pa_via_s3`, `sign_c2pa_via_s3_test`)
and the distributed signers (`sign_c2pa_distributed`, `sign_c2pa_distributed_test`), which
redact locally without sending media to Trufo. Distributed redaction requires the
`trufo[local-sign-only]` (or `local-full`) optional installation, same as any
distributed signing.

### Minimal Example

```python
from trufo import sign_c2pa
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_PROD)

signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    actions=[
        ["redact", {"label": "c2pa.metadata", "reason": "c2pa.PII.present"}],
    ],
)
```

This redacts every unnumbered occurrence of `c2pa.metadata` found anywhere in the input's manifest history — the immediate parent, or any earlier generation — and records why.

### The `redact` Action

A `redact` entry has the shape `["redact", {"label": ..., "reason": ...}]`:

- **`label`** — the one assertion to remove.
- **`reason`** — **required** rationale, recorded on the resulting `c2pa.redacted` action.

Repeat the entry to redact several assertions. Each entry carries its own reason:

```python
actions=[
    ["redact", {"label": "c2pa.metadata", "reason": "c2pa.PII.present"}],
    ["redact", {"label": "cawg.metadata", "reason": "c2pa.trade-secret.present"}],
]
```

The same assertion may not be targeted twice in one call.

#### Supported Labels

Four assertion labels may be redacted: `c2pa.metadata` (capture date, location,
GPS, device), `cawg.metadata` (byline, people depicted, credit, rights),
`cawg.training-mining` (AI-training permissions), and `cawg.identity` (the identity
assertion naming a signer). Any other label is rejected — see the
[reference](../api/api_c2pa.md#redact).

Removing a contributor from an asset generally takes both `cawg.metadata` and
`cawg.identity`: the first carries the byline, the second the certificate that names
the signer. Redacting either alone leaves the other in place.

#### Reason

Every `redact` action requires a `reason`, recorded on the resulting
`c2pa.redacted` action so a reviewer can see *why* something was removed, not just
that it was. Use one of the C2PA presets — `c2pa.PII.present`,
`c2pa.invalid.data`, `c2pa.trade-secret.present`, `c2pa.government.confidential` —
or a custom reverse-DNS value such as `com.example.internal-policy`, which requires
domain validation for that domain. See the
[reference](../api/api_c2pa.md#redact).

```python
actions=[["redact", {"label": "c2pa.metadata", "reason": "c2pa.trade-secret.present"}]]
```

### Targeting One Specific Instance

If a single manifest carries more than one assertion under the same base label (disambiguated as `label__1`, `label__2`, ..., numbered from 1), a bare label only matches the *unnumbered* instance — it does not also redact the numbered ones. To redact a specific numbered instance, suffix the label directly:

```python
actions=[["redact", {"label": "c2pa.metadata__1", "reason": "c2pa.PII.present"}]]
```

To redact every instance of a repeated label, add an entry for each exact instance:

```python
actions=[
    ["redact", {"label": "c2pa.metadata", "reason": "c2pa.PII.present"}],
    ["redact", {"label": "c2pa.metadata__1", "reason": "c2pa.PII.present"}],
]
```

Instance numbers come from the input's own manifest, so inspect it to see which instances are present.

### Combining With Other Actions

`redact` entries sit in the same list as any other action:

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    actions=[
        ["transcode", {"target_mime_type": "image/png"}],
        ["redact", {"label": "c2pa.metadata", "reason": "c2pa.PII.present"}],
    ],
    assertions=[["cawg_identity", {"cawg_identity_id": "org_interim"}]],
)
```

Where you place an entry sets where its `c2pa.redacted` action appears in the recorded history, but never what gets redacted: redaction always targets the input's *existing* manifest history, never the output of a transform in the same call.

### When Redaction Fails

A redaction the input cannot satisfy is rejected with `400`:

- the input has no C2PA manifest to redact from, or
- the label doesn't exist anywhere in the input's manifest history.

Redaction is all-or-nothing — if any entry can't be satisfied, nothing is signed.

---

## Reference

- `redact` action reference: [../api/api_c2pa.md](../api/api_c2pa.md#redact)
- Complete runnable example: [5_ingredients.py](5_ingredients.py)
