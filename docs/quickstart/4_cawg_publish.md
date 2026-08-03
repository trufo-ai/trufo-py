# Quickstart: CAWG Publish

Attach CAWG assertions to embed creator metadata, declare training permissions, and bind a verified identity to a C2PA manifest.

## What This Does

The CAWG (Creator Assertions Working Group) assertions add attribution and rights data to a C2PA manifest:

| Assertion | C2PA label | Purpose |
|-----------|-----------|----------|
| `cawg_metadata` | `cawg.metadata` | JSON-LD creator/rights metadata |
| `cawg_training` | `cawg.training-mining` | AI training and data-mining permissions |
| `cawg_identity` | `cawg.identity` | Bind a verified identity to the gathered assertions |

## Requirements

- For production signing: a `c2pa-sign-prod` API key (scope required by `/c2pa/sign`). See [0_setup.md](0_setup.md). Production signing also requires completed Organization Validation (OV) for your organization.
- For test signing: a `c2pa-sign-test` API key (scope required by the test host).
- Production examples that use `cawg_identity_id="org_interim"` require your organization to have CAWG organization identity signing enabled.

All CAWG assertions are optional. When a `cawg_identity` entry is present, it binds the verified identity to all gathered assertions in the manifest. Every signed manifest also automatically carries an `ai.trufo.identity` assertion with your organization id and (with active OV) your RA-validated legal name — see [Automatic assertions](../api/api_c2pa.md#automatic-assertions).

---

## Example

```python
from trufo import sign_c2pa

signed_bytes = sign_c2pa(
    api_key,
    media_bytes,
    assertions=[
        ["cawg_metadata", {
            "assertion": {
                "@context": {"dc": "http://purl.org/dc/elements/1.1/"},
                "dc:creator": ["[CREATOR NAME]"],
                "dc:rights": "© 2026 [CREATOR NAME]. All rights reserved.",
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

For development-only test signing, use `sign_c2pa_test()` with a `c2pa-sign-test` API key and `cawg_identity_id="test"`. Test-signed outputs are useful for integration development but are not intended to be accepted as production C2PA credentials by conformant validators.

## `cawg_metadata` Namespaces

The `assertion` dict must include an `@context` mapping. Trufo accepts the standard
CAWG namespaces — `dc`, `exif`, `exifEX`, `tiff`, `photoshop`, `xmp`, `pdf`, `pdfx`,
`Iptc4xmpCore`, and `Iptc4xmpExt` — each with its exact canonical URI; see the
[full table](../api/api_c2pa.md#cawg_metadata). A richer example:

```python
["cawg_metadata", {
    "assertion": {
        "@context": {
            "dc": "http://purl.org/dc/elements/1.1/",
            "photoshop": "http://ns.adobe.com/photoshop/1.0/",
            "Iptc4xmpCore": "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/",
            "Iptc4xmpExt": "http://iptc.org/std/Iptc4xmpExt/2008-02-29/",
        },
        "dc:creator": ["Erika Fictional"],
        "dc:rights": "© 2026 Example Media. All rights reserved.",
        "photoshop:DateCreated": "2026-08-31",
        "Iptc4xmpExt:DigitalSourceType":
            "https://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture",
        "Iptc4xmpExt:LocationCreated": {"Iptc4xmpExt:City": "San Francisco"},
        "Iptc4xmpCore:AltTextAccessibility":
            "Photo of a suspension bridge at sunset.",
    },
}]
```

Camera, lens, and GPS fields follow the same pattern under `exif`, `exifEX`, and
`tiff`. For the full vocabulary see
[cawg.io/metadata/1.1](https://cawg.io/metadata/1.1/).

---

## `cawg_training` Entries

| Entry | Description |
|-------|-------------|
| `cawg.ai_training` | AI model training |
| `cawg.ai_inference` | AI inference |
| `cawg.data_mining` | Data mining |

Each entry requires a `use` value: `"allowed"`, `"notAllowed"`, or `"constrained"`. When `"constrained"`, include a `constraint_info` string (e.g. a license URL or terms description).

For more details, see [cawg.io/training-and-data-mining/1.1](https://cawg.io/training-and-data-mining/1.1/).

---

## Reference

- `assertions` and `actions` field reference: [../api/api_c2pa.md](../api/api_c2pa.md)
- Complete runnable example: [4_cawg_publish.py](4_cawg_publish.py)
