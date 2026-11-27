# Storage Options and Privacy

Control whether Trufo retains signed manifests, whether thumbnails are embedded or transmitted, which region processes your media, and how storage interacts with watermark recovery.

---

## Summary of Privacy and Storage Levers

| Control | What it does | Trade-off |
| --- | --- | --- |
| **Local mode** (Python SDK or Docker) | Keeps original media and ingredient bytes on your infrastructure | Requires `sdk-download` key and Trufo Library License |
| `skip_manifest_storage=True` | Prevents Trufo from storing a copy of the finished manifest | Incompatible with `per_embed` watermarking (`400 ManifestStorageRequired`) |
| `thumbnail_settings.policy` | Controls claim and ingredient thumbnail generation (`auto`, `auto_no_ingredient`, `none`) | `"none"` shrinks manifest size and stops generated thumbnails from leaving your host, at the cost of no validator preview thumbnails |
| **EU endpoint** (`eu.api.trufo.ai`) | Keeps Cloud-mode media processing and request logs in EU infrastructure | Register software agents on the same region you sign against |

---

## Controlling Manifest Storage (`skip_manifest_storage`)

By default (`skip_manifest_storage=False`), Trufo stores a copy of the signed C2PA manifest so it can be retrieved later (for watermark recovery and content records).

Set `skip_manifest_storage=True` when you want Trufo to sign the claim without retaining a copy of the finished manifest:

```python
from trufo import sign_c2pa_cloud

signed_bytes = sign_c2pa_cloud(
    api_key,
    media_bytes,
    skip_manifest_storage=True,
)
```

In **Local mode** (`sign_c2pa_local()` or `trufo-local`), original media and ingredient bytes never leave your machine, but the finished manifest is still sent to Trufo unless `skip_manifest_storage=True`. For strict zero-media-and-manifest retention in Local mode, combine both:

```python
from trufo import sign_c2pa_local
from trufo.c2pa import ManifestSettings, ThumbnailPolicy, ThumbnailSettings

signed_bytes = sign_c2pa_local(
    api_key,
    media_bytes,
    skip_manifest_storage=True,
    manifest_settings=ManifestSettings(
        thumbnail_settings=ThumbnailSettings(policy=ThumbnailPolicy.NONE),
    ),
)
```

> **Note:** Every manifest signed through Trufo still includes the automatic `ai.trufo.identity` assertion (`oid` and validated legal name when OV is active), and request metadata is still metered for billing.

---

## Thumbnail Settings (`thumbnail_settings`)

C2PA manifests normally embed WebP thumbnails of the signed asset and its ingredients so validators can show visual previews. Thumbnails affect both **file size** and **privacy** (if manifest storage is enabled, generated thumbnails are inside the stored manifest).

```python
from trufo.c2pa import ManifestSettings, ThumbnailPolicy, ThumbnailSettings, ThumbnailSize

settings = ManifestSettings(
    thumbnail_settings=ThumbnailSettings(
        policy=ThumbnailPolicy.AUTO_NO_INGREDIENT,  # AUTO (default), AUTO_NO_INGREDIENT, or NONE
        size=ThumbnailSize.MEDIUM,                  # MEDIUM (512 px, default) or HIGH (1024 px)
    ),
)
```

| Policy | Claim thumbnail | Ingredient thumbnails | When to use |
| --- | --- | --- | --- |
| `AUTO` (default) | Generated | Generated when missing | Standard provenance display in C2PA validators |
| `AUTO_NO_INGREDIENT` | Generated | Not generated | Smaller manifests or when ingredient visuals shouldn't be newly thumbnailed |
| `NONE` | Not generated | Not generated | Minimum manifest overhead or strict privacy |

- **Sizes:** `MEDIUM` caps height+width at 512 px (WebP quality 80); `HIGH` caps at 1024 px (WebP quality 90). Alpha channels are preserved.
- **Inherited thumbnails:** Existing thumbnails already present inside a signed input's manifest history are preserved regardless of `policy`.

---

## Storing for Soft-Binding (Watermark Recovery)

Invisible watermarking interacts directly with manifest storage:

- **`per_embed` watermarking (bound):** Requires `skip_manifest_storage=False` (`400 ManifestStorageRequired` otherwise). Trufo stores the signed manifest bound to a unique watermark ID (`wid`) and content ID (`cid`) so `POST /content/recover` can return the full manifest even if downstream platforms strip C2PA metadata.
- **`per_ai_system` watermarking (unbound):** Embeds a shared AI-system watermark ID without storing a per-asset soft-binding record, so it can be combined with `skip_manifest_storage=True`.

Stored content records can be inspected or withdrawn via `/content/get`, `/content/list`, and `/content/status` (see [Watermarking and Recovery](watermarking.md#managing-content-records)).

---

## Regional Processing and Ephemeral Task Storage

- **Cloud region selection:** Call `https://eu.api.trufo.ai` (instead of `https://api.trufo.ai`) to keep Cloud-mode media processing and request logs in EU infrastructure. Your organization's `default_content_region` setting applies to dashboard workflows only — configure the API host explicitly in your client.
- **Async S3 tasks (`TASK` mode):** Ephemeral upload URLs expire after 1 hour; download URLs stay valid for up to 15 minutes (refreshable via `GET /tasks/{task_id}` for 24 hours). Ephemeral S3 input and output objects are deleted automatically after 1–2 days.

---

## Remote Manifests

Currently, Trufo embeds C2PA manifests directly inside the signed media file. Hosting manifests remotely (external manifest URLs rather than embedded JUMBF) is not yet supported on signing; if an incoming file references an external manifest by URL, Trufo currently refuses it (`400`) — see [Verification](verification.md#4-incoming-signed-files-and-remote-manifests).

---

## Reference

- `skip_manifest_storage`, `manifest_settings`, and Local mode egress: [Signing API](../reference/signing-api.md)
- Watermark allocation modes and content records: [Watermarking and Recovery](watermarking.md)
- Regions and hosts: [Platform API](../reference/platform-api.md#regions)
