# Quickstart: Ingredients

Manage the ingredients of a signed asset — the prior assets carried into its manifest.

## Declaring Ingredients

Describe prior or contributing assets in the manifest without uploading them. Each `["ingredient", {...}]` entry in `assertions` becomes a gathered `c2pa.ingredient.v3` assertion — your workflow's account of the asset, not a claim attributed to the Trufo signer. Whenever any ingredient entries are present, the manifest's `allActionsIncluded` is set to `false`.

Two relationships are available today; entries may optionally carry base64 `media`, which is thumbnailed (and validated when it carries its own C2PA manifest; manifest-free media is a visual record, not a cryptographic binding):

- **`inputTo`** — an input to a computational process: a prompt, model, or dataset. Use `data_types` to say which (`c2pa.types.prompt`, `c2pa.types.model`, `c2pa.types.dataset`, ...).
- **`componentOf`** — a placed component of a composition; requires `media` in a thumbnail-capable image format.

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

See [api_c2pa.md](../api/api_c2pa.md) for the full parameter reference and conflict rules.

## Redaction

Remove specific assertions from a media file's existing C2PA manifest history.

### What This Does

Redaction is expressed as a `redact` **action** in the `actions` list. Each entry names one assertion and removes it from wherever it lives in the input's provenance chain: not just the immediate parent, but any earlier generation too. Repeat the entry to redact several assertions, each with its own reason. This is useful for stripping sensitive metadata (e.g. embedded camera/device metadata in `c2pa.metadata`) while preserving the rest of the provenance record and the file's continuity. Every redaction is recorded in the resulting manifest's `redacted_assertions` list, so the fact that a redaction happened, and which assertion was removed, is always part of the record.

Redaction removes whole assertions; individual fields within an assertion cannot be removed separately. Redaction is limited to the labels listed below; any other label, or a label that does not exist anywhere in the input's manifest history, fails the request.

### Requirements

- A `c2pa-sign-prod` or `c2pa-sign-test` API key, same as any other signing call. See
[0_auth.md](0_auth.md).
- The input file must already have a C2PA manifest — redacting a file with no existing
provenance history fails.
- The `redact` action is available on all signers: the fully-server signers (`sign_c2pa`,
`sign_c2pa_test`, `sign_c2pa_s3`, `sign_c2pa_s3_test`, `sign_c2pa_via_s3`, `sign_c2pa_via_s3_test`)
and the distributed signers (`sign_c2pa_distributed`, `sign_c2pa_distributed_test`), which
redact locally without sending media to Trufo. Distributed redaction requires the
`trufo[local]` optional installation, same as any distributed signing.

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

The labels supported for redaction are listed below; more will be added over time (upon request).

| Label                    | Carries                                                             |
| ------------------------ | ------------------------------------------------------------------- |
| `"c2pa.metadata"`        | capture metadata — date/time, location, GPS coordinates, device      |
| `"cawg.metadata"`        | editorial metadata — byline/creator, people depicted, credit, rights |
| `"cawg.training-mining"` | AI-training and data-mining permissions and opt-outs                 |
| `"cawg.identity"`        | the identity binding a named signer to that manifest's assertions    |

Each label is enumerated individually rather than by namespace, so any label not listed — including other `cawg.*` labels and `c2pa.ai-disclosure` — is rejected.

Removing a contributor from an asset generally takes both `"cawg.metadata"` and `"cawg.identity"`: the first carries the byline, the second carries the identity certificate that names the signer. Redacting either one alone leaves the other in place.

#### Reason

A reason is required on every `redact` action. It is either one of the preset values or a custom entity-namespaced value:

| Preset                         | Redacted because the assertion contains |
| ------------------------------ | --------------------------------------- |
| `c2pa.PII.present`             | personally identifiable information |
| `c2pa.invalid.data`            | incorrect data |
| `c2pa.trade-secret.present`    | commercially sensitive information |
| `c2pa.government.confidential` | information restricted by a government |

```python
actions=[["redact", {"label": "c2pa.metadata", "reason": "c2pa.trade-secret.present"}]]
```

Each redacted assertion gets its own `c2pa.redacted` action recording this reason plus a direct reference to the specific assertion that was removed, so a reviewer of the provenance history can understand *why* something was removed, not just that it was.

You may also supply a **custom** reverse-DNS reason (e.g. `"com.example.internal-policy"`) instead of a preset. Custom reasons require that your organization has completed domain validation for that domain (the same domain-validation flow used for custom assertions).

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
