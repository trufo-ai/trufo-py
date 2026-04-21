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

- A `c2pa-sign-test` API key (scope required by `/test/c2pa/sign`). See [0_auth.md](0_auth.md).
- `cawg_identity` is required when any assertions are present.

---

## Example

```python
from trufo.api.tps.sign_c2pa import sign_c2pa_test

signed_bytes = sign_c2pa_test(
    api_key,
    media_bytes,
    assertions=[
        ["cawg_metadata", {
            "assertion": {
                "@context": {"dc": "http://purl.org/dc/elements/1.1/"},
                "dc:creator": ["Alice"],
                "dc:rights": "© 2026 Alice. All rights reserved.",
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
        ["cawg_identity", {"cawg_identity_id": "test"}],
    ],
)
```

## `cawg_metadata` Namespaces

The `assertion` dict must include an `@context` mapping. Only the following namespace prefixes and their exact URIs are accepted:

| Prefix | URI |
|--------|-----|
| `Iptc4xmpCore` | `http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/` |
| `Iptc4xmpExt` | `http://iptc.org/std/Iptc4xmpExt/2008-02-29/` |
| `dc` | `http://purl.org/dc/elements/1.1/` |
| `exif` | `http://ns.adobe.com/exif/1.0/` |
| `exifEX` | `http://cipa.jp/exif/2.32/` |
| `pdf` | `http://ns.adobe.com/pdf/1.3/` |
| `pdfx` | `http://ns.adobe.com/pdfx/1.3/` |
| `photoshop` | `http://ns.adobe.com/photoshop/1.0/` |
| `tiff` | `http://ns.adobe.com/tiff/1.0/` |
| `xmp` | `http://ns.adobe.com/xap/1.0/` |

For more details, see [cawg.io/metadata/1.1](https://cawg.io/metadata/1.1/).

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
- Complete runnable example: [3_cawg_publish.py](3_cawg_publish.py)

---

## Appendix A: `cawg_metadata` Examples

From the CAWG metadata assertion spec §3.1 (non-normative).

**Image:**

```python
["cawg_metadata", {
    "assertion": {
        "@context": {
            "exif": "http://ns.adobe.com/exif/1.0/",
            "exifEX": "http://cipa.jp/exif/2.32/",
            "tiff": "http://ns.adobe.com/tiff/1.0/",
            "Iptc4xmpCore": "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/",
            "Iptc4xmpExt": "http://iptc.org/std/Iptc4xmpExt/2008-02-29/",
            "dc": "http://purl.org/dc/elements/1.1/",
            "photoshop": "http://ns.adobe.com/photoshop/1.0/",
        },
        "photoshop:DateCreated": "Aug 31, 2022",
        "Iptc4xmpExt:DigitalSourceType": "https://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture",
        "Iptc4xmpExt:LocationCreated": {
            "Iptc4xmpExt:City": "San Francisco",
        },
        "Iptc4xmpExt:PersonInImage": ["Erika Fictional"],
        "Iptc4xmpCore:AltTextAccessibility": "Photo of Erika Fictional standing in front of the Golden Gate Bridge at sunset.",
        "exif:GPSVersionID": "2.2.0.0",
        "exif:GPSLatitude": "39,21.102N",
        "exif:GPSLongitude": "74,26.5737W",
        "exif:GPSAltitudeRef": 0,
        "exif:GPSAltitude": "100963/29890",
        "exif:GPSTimeStamp": "2019-09-22T18:22:57Z",
        "exif:GPSSpeedRef": "K",
        "exif:GPSSpeed": "4009/161323",
        "exif:GPSImgDirectionRef": "T",
        "exif:GPSImgDirection": "296140/911",
        "exif:GPSDestBearingRef": "T",
        "exif:GPSDestBearing": "296140/911",
        "exif:GPSHPositioningError": "13244/2207",
        "exif:ExposureTime": "1/100",
        "exif:FNumber": 4.0,
        "exif:ColorSpace": 1,
        "exif:DigitalZoomRatio": 2.0,
        "tiff:Make": "CameraCompany",
        "tiff:Model": "Shooter S1",
        "exifEX:LensMake": "CameraCompany",
        "exifEX:LensModel": "17.0-35.0 mm",
        "exifEX:LensSpecification": {"@list": [1.55, 4.2, 1.6, 2.4]},
    },
}]
```

**PDF:**

```python
["cawg_metadata", {
    "assertion": {
        "@context": {
            "dc": "http://purl.org/dc/elements/1.1/",
            "xmp": "http://ns.adobe.com/xap/1.0/",
            "pdf": "http://ns.adobe.com/pdf/1.3/",
            "pdfx": "http://ns.adobe.com/pdfx/1.3/",
        },
        "dc:created": "2015 February 3",
        "dc:title": ["This is a test file"],
        "xmp:CreatorTool": "TeX",
        "pdf:Producer": "pdfTeX-1.40.14",
        "pdf:Trapped": "Unknown",
        "pdfx:PTEX.Fullbanner": "This is pdfTeX, Version 3.1415926-2.5-1.40.14 (TeX Live 2013) kpathsea version 6.1.1",
    },
}]
```

---
