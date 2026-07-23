# Quickstart: Redaction

Remove specific assertions from a media file's existing C2PA manifest history.

## What This Does

The `redactions` parameter takes a list of assertion labels and removes each one from
wherever it lives in the input's provenance chain — not just the immediate parent, but any
earlier generation too. This is useful for stripping sensitive metadata (e.g. embedded
camera/device metadata in `c2pa.metadata`) while preserving the rest of the provenance record
and the file's continuity. Every redaction is recorded in the resulting manifest's
`redacted_assertions` list, so the fact that a redaction happened — and which assertion was
removed — is always part of the record, never a silent drop.

Redaction only removes whole assertions — there's no way (yet) to remove specific fields from
an assertion while keeping the rest. It also only supports a small, closed set of labels today
(see below); attempting to redact anything else, or a label that doesn't exist anywhere in the
input's manifest history, fails the request.

## Requirements

- A `c2pa-sign-prod` or `c2pa-sign-test` API key, same as any other signing call. See
  [0_auth.md](0_auth.md).
- The input file must already have a C2PA manifest — redacting a file with no existing
  provenance history fails.
- `redactions` (and `redaction_reason`) is only available on the fully-server signers
  (`sign_c2pa`, `sign_c2pa_test`, `sign_c2pa_s3`, `sign_c2pa_s3_test`, `sign_c2pa_via_s3`,
  `sign_c2pa_via_s3_test`) — not on the distributed signers.

---

## Minimal Example

```python
from trufo import sign_c2pa
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_PROD)

signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    redactions=["c2pa.metadata"],
)
```

This redacts every occurrence of `c2pa.metadata` found anywhere in the input's manifest
history — the immediate parent, or any earlier generation.

## Supported Labels

Only a small, closed set of labels is currently supported:

| Label             | C2PA label      |
| ----------------- | --------------- |
| `"c2pa.metadata"` | `c2pa.metadata` |

## Targeting One Specific Instance

If a single manifest carries more than one assertion under the same base label (disambiguated
internally as `label__1`, `label__2`, ...), a bare label only matches the *unnumbered*
instance — it does not also redact the numbered ones. To redact a specific numbered instance,
suffix the label directly:

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    redactions=["c2pa.metadata__1"],
)
```

To redact every instance of a repeated label, list each exact instance explicitly:

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    redactions=["c2pa.metadata", "c2pa.metadata__1"],
)
```

There's currently no built-in way to discover how many instances exist or what they're called
— that requires inspecting the manifest yourself first.

Listing the same entry more than once (e.g. by accident) isn't an error — duplicates are
silently collapsed to a single request for that label.

## Recording a Reason

`redaction_reason` is an optional rationale for the redaction, drawn from a small closed set
(`RedactionReason` — `c2pa.PII.present`, `c2pa.invalid.data`, `c2pa.trade-secret.present`,
`c2pa.government.confidential`). **Supplying it is strongly recommended**: without it, the
redaction is still recorded in `redacted_assertions`, but there's no `c2pa.redacted` action
explaining why the assertion was removed — a reviewer of the provenance history sees that
something is missing, but not why.

```python
from trufo import sign_c2pa
from trufo.c2pa import RedactionReason

signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    redactions=["c2pa.metadata"],
    redaction_reason=RedactionReason.PII_PRESENT.value,
)
```

When supplied, each redacted assertion also gets its own `c2pa.redacted` action recorded in
the manifest, carrying this reason plus a direct reference to the specific assertion that was
removed — useful for a human reviewing the provenance history to understand *why* something was
redacted, not just that it was. When omitted, redaction still happens exactly as described
above (via `redacted_assertions`); no `c2pa.redacted` action is added, since a reason is
required for that action once it's present.

## Combining With Other Instructions

`redactions` is independent of `actions` and `assertions` — it always targets the input's
*existing* manifest history, regardless of what other actions run in the same call, so there's
no ordering to think about between them:

```python
signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    actions=[["transcode", {"target_mime_type": "image/png"}]],
    assertions=[["cawg_identity", {"cawg_identity_id": "org_interim"}]],
    redactions=["c2pa.metadata"],
)
```

---

## Reference

- `redactions`/`redaction_reason` field reference: [../api/api_c2pa.md](../api/api_c2pa.md#redactions)
- Complete runnable example: [5_redaction.py](5_redaction.py)
