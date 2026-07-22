# Quickstart: Redaction

Remove specific assertions from a media file's existing C2PA manifest history.

## What This Does

The `redactions` parameter takes a list of assertion labels and removes each one from
wherever it lives in the input's provenance chain — not just the immediate parent, but any
earlier generation too. This is useful for stripping sensitive metadata (e.g. embedded
camera/device metadata in `c2pa.metadata`) while preserving the rest of the provenance record
and the file's continuity — the redacted assertion is marked as removed (`c2pa.redacted`), not
silently dropped, so the fact that a redaction happened remains part of the record.

Redaction only removes whole assertions — there's no way (yet) to remove specific fields from
an assertion while keeping the rest. It also only supports a small, closed set of labels today
(see below); attempting to redact anything else, or a label that doesn't exist anywhere in the
input's manifest history, fails the request.

## Requirements

- A `c2pa-sign-prod` or `c2pa-sign-test` API key, same as any other signing call. See
  [0_auth.md](0_auth.md).
- The input file must already have a C2PA manifest — redacting a file with no existing
  provenance history fails.
- `redactions` is only available on the fully-server signers (`sign_c2pa`, `sign_c2pa_test`,
  `sign_c2pa_s3`, `sign_c2pa_s3_test`, `sign_c2pa_via_s3`, `sign_c2pa_via_s3_test`) — not on
  the distributed signers.

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

- `redactions` field reference: [../api/api_c2pa.md](../api/api_c2pa.md#redactions)
- Complete runnable example: [5_redaction.py](5_redaction.py)
