# CAWG Identity and Metadata

Attach Creator Assertions Working Group (CAWG) assertions to embed creator/rights metadata, AI training preferences, and a verified organization identity in a C2PA manifest.

| Assertion | C2PA label | Purpose |
| --- | --- | --- |
| `cawg_metadata` | `cawg.metadata` | JSON-LD creator, credit, location, and rights metadata |
| `cawg_training` | `cawg.training-mining` | AI training, inference, and data-mining permissions |
| `cawg_identity` | `cawg.identity` | Cryptographically binds a verified identity to all gathered assertions |

## Requirements

- Production: `c2pa-sign-prod` key + C2PA Signing plan + completed Organization Validation (OV).
- Using `cawg_identity_id="org_interim"` in production requires the **CAWG Organization Certificate** plan (Trufo provisions and manages your organization's CAWG interim certificate automatically).
- Test host: `c2pa-sign-test` key + `sign_c2pa_cloud_test()` with `cawg_identity_id="test"`.

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
            "https://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture",
        "Iptc4xmpExt:LocationCreated": {"Iptc4xmpExt:City": "San Francisco"},
        "Iptc4xmpCore:AltTextAccessibility":
            "Photo of a suspension bridge at sunset.",
    },
}]
```

Use `cawg_metadata` for creator, credit, and rights metadata; use `c2pa_metadata` for camera/capture EXIF details (note that `exifEX` uses URI `http://cipa.jp/exif/2.32/` in `cawg_metadata` and `http://cipa.jp/exif/1.0/` in `c2pa_metadata`). See [cawg.io/metadata/1.1](https://cawg.io/metadata/1.1/).

---

## `cawg_training` Entries

Standard entry names: `cawg.ai_training`, `cawg.ai_generative_training`, `cawg.ai_inference`, and `cawg.data_mining`. Each maps to `{"use": ...}` with `"allowed"`, `"notAllowed"`, or `"constrained"` (include `"constraint_info"` such as a license URL when `"constrained"`). See [cawg.io/training-and-data-mining/1.1](https://cawg.io/training-and-data-mining/1.1/).

---

## Reference

- Full namespace & assertion reference: [Actions and Assertions](../reference/actions-and-assertions.md#cawg_metadata)
- Complete runnable script: [cawg_identity.py](cawg_identity.py)
