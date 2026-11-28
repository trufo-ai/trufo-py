# CAWG Identity and Metadata

Attach Creator Assertions Working Group (CAWG) assertions to embed creator/rights metadata, AI training preferences, and a verified organization identity in a C2PA manifest.

| Assertion | C2PA label | Purpose |
| --- | --- | --- |
| `cawg_metadata` | `cawg.metadata` | JSON-LD creator, credit, location, and rights metadata |
| `cawg_training` | `cawg.training-mining` | AI training, inference, and data-mining permissions |
| `cawg_identity` | `cawg.identity` | Cryptographically binds a verified identity to all gathered assertions |

## Requirements

- Production: `c2pa-sign-prod` key + C2PA Signing plan + completed Organization Validation (OV).
- `cawg_identity_id="org_interim"` selects your organization's **Trufo-managed** CAWG interim certificate: Trufo provisions it and holds its key, so there is nothing to enroll. It requires the **CAWG Organization Certificate** plan and is accepted on production hosts and on `test.api.trufo.ai`. (CAWG certificates you enroll yourself through the [Certificates API](../reference/certificates-api.md) are for your own signing stack and cannot be selected through `cawg_identity_id`.)
- `cawg_identity_id="test"` selects a shared Trufo test CAWG certificate: `test.api.trufo.ai` only (`c2pa-sign-test` key + `sign_c2pa_cloud_test()`), no plan required. Production hosts reject it with `400 InvalidCawgIdentityId`.

All three CAWG assertions are optional and can be used independently or together. Every manifest signed through Trufo also automatically carries `ai.trufo.identity` with your `oid` and (with active OV) validated legal name.

---

## Example

```python
from trufo import sign_c2pa_cloud

signed_bytes = sign_c2pa_cloud(
    api_key,
    media_bytes,
    assertions=[
        ["cawg_metadata", {
            "assertion": {
                "@context": {"dc": "http://purl.org/dc/elements/1.1/"},
                "dc:creator": ["[CREATOR NAME]"],
                "dc:rights": "© 2026 [ORGANIZATION NAME]. All rights reserved.",
            },
        }],
        ["cawg_training", {
            "assertion": {
                "entries": {
                    "cawg.ai_training": {"use": "notAllowed"},
                    "cawg.data_mining": {"use": "notAllowed"},
                },
            },
        }],
        ["cawg_identity", {"cawg_identity_id": "org_interim"}],
    ],
)
```

---

## `cawg_metadata` Namespaces

`assertion` must include an `@context` mapping whose prefixes and URIs match the allowlisted table in [Actions and Assertions](../reference/actions-and-assertions.md#cawg_metadata).

```python
["cawg_metadata", {
    "assertion": {
        "@context": {
            "dc": "http://purl.org/dc/elements/1.1/",
            "photoshop": "http://ns.adobe.com/photoshop/1.0/",
            "Iptc4xmpCore": "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/",
            "Iptc4xmpExt": "http://iptc.org/std/Iptc4xmpExt/2008-02-29/",
        },
        "dc:creator": ["[CREATOR NAME]"],
        "dc:rights": "© 2026 [ORGANIZATION NAME]. All rights reserved.",
        "photoshop:DateCreated": "2026-08-31",
        "Iptc4xmpExt:DigitalSourceType":
            "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture",
        "Iptc4xmpExt:LocationCreated": {"Iptc4xmpExt:City": "San Francisco"},
        "Iptc4xmpCore:AltTextAccessibility":
            "Photo of a suspension bridge at sunset.",
    },
}]
```

Use `cawg_metadata` for creator, credit, and rights metadata; use `c2pa_metadata` for camera/capture EXIF details (note that `exifEX` uses URI `http://cipa.jp/exif/2.32/` in `cawg_metadata` and `http://cipa.jp/exif/1.0/` in `c2pa_metadata`). See [cawg.io/metadata/1.1](https://cawg.io/metadata/1.1/).

---

## `cawg_training` Entries

Standard entry names: `cawg.ai_training`, `cawg.ai_generative_training`, `cawg.ai_inference`, and `cawg.data_mining`. Each maps to `{"use": ...}` with `"allowed"`, `"notAllowed"`, or `"constrained"`. An entry may contain only `"use"` and an optional `"constraint_info"`, which must be a non-empty string (for example, a license URL or policy text) and belongs on `"constrained"` entries:

```python
["cawg_training", {
    "assertion": {
        "entries": {
            "cawg.ai_generative_training": {"use": "notAllowed"},
            "cawg.ai_training": {
                "use": "constrained",
                "constraint_info": "https://example.com/licensing/ai-training",
            },
            "cawg.data_mining": {
                "use": "constrained",
                "constraint_info": "Permitted for search indexing only; contact licensing@example.com.",
            },
        },
    },
}]
```

See [cawg.io/training-and-data-mining/1.1](https://cawg.io/training-and-data-mining/1.1/).

---

## Reference

- Full namespace & assertion reference: [Actions and Assertions](../reference/actions-and-assertions.md#cawg_metadata)
- Complete runnable script: [cawg_identity.py](cawg_identity.py)
