# Media Format Support Reference

Normative eligibility rules for C2PA signing and validation, Trufo Pawprint watermark embedding and recovery, and media actions (`resize`, `crop`, `trim`, `transcode`, `repackage`) across Cloud and Local modes.

A file is supported when its MIME type is eligible for the operation and the file passes per-file checks. Signing with a watermark requires eligibility for both operations.

---

## MIME Types

**Yes** means eligible subject to per-file checks; **No** means unsupported.

| Media | MIME types | C2PA generate | C2PA validate | WM encode | WM decode |
| --- | --- | --- | --- | --- | --- |
| JPEG, PNG, WebP, TIFF | `image/jpeg`, `image/png`, `image/webp`, `image/tiff` | Yes | Yes | Yes | Yes |
| AVIF, JPEG XL, HEIC/HEIF, GIF | `image/avif`, `image/jxl`, `image/heic`, `image/heif`, `image/gif` | Yes | Yes | Yes | Yes |
| WAV, FLAC, MP3, M4A | `audio/wav`, `audio/flac`, `audio/mpeg`, `audio/mp4` | Yes | Yes | Yes | Yes |
| MP4, MOV | `video/mp4`, `video/quicktime` | Yes | Yes | Yes | Yes |
| DNG | `image/x-adobe-dng` | Yes | Yes | No | Yes |
| PDF | `application/pdf` | Yes | Yes | No | No |
| Raw AAC (ADTS) | `audio/aac` | No | No | Yes | Yes |
| BMP, OGG (Vorbis, Opus), AIFF | `image/bmp`, `audio/ogg`, `audio/aiff` | No | No | No | Yes |
| SVG, AVI, ANI | `image/svg+xml`, `video/avi`, `video/x-msvideo`, `application/x-navi-animation` | Yes | Yes | No | No |
| WebM | `video/webm` | No | No | No | No |

- **Image pixel cap:** C2PA signing accepts images up to **400 million pixels**.
- **Local Python SDK JPEG XL:** Requires CPython 3.12 or earlier to sign (and 3.12 to also use `transcode` or `trufo[local-full]`).
- **Ingredients with `media`:** Must have **Yes** under **C2PA validate**; other formats can be declared with `format` and no `media`.
- **MIME detection:** Detected from content bytes. Aliases normalized: `audio/x-wav` / `audio/vnd.wave` → `audio/wav`, `audio/x-flac` → `audio/flac`, `audio/x-mpeg` → `audio/mpeg`, `audio/x-m4a` → `audio/mp4`, `audio/x-hx-aac-adts` → `audio/aac`, `image/x-tiff` → `image/tiff`, `video/x-m4v` → `video/mp4` (watermark ops also normalize `audio/x-aiff` → `audio/aiff` and `image/mpo` → `image/jpeg`). Audio-only MP4 is treated as `audio/mp4`.

---

## Watermark Image Restrictions

Watermark encoding rewrites the file in its source format while preserving settings and metadata except where listed. Recovery is read-only and additionally accepts **Recovery only** inputs.

| Format | Encode | Dropped or changed on encode | Recovery only |
| --- | --- | --- | --- |
| JPEG | 8-bit YCbCr, RGB, or grayscale, baseline or progressive; keeps quantization tables, chroma subsampling, ICC, EXIF (thumbnail included), XMP, comments, IPTC/Photoshop (APP13), DPI | Secondary images (Ultra HDR / ISO gain maps, depth, burst, stereo) and declaring XMP; unrecognized APPn segments; quantization tables coarser at DC than highest frequency become standard quality-90 | CMYK, YCCK |
| PNG | 8/16-bit RGB, RGBA, grayscale, or grayscale+alpha, non-interlaced; keeps ICC, sRGB, gAMA, cHRM, SDR `cICP` (RGB, full range), EXIF, DPI, safe-to-copy chunks; rejects unsafe unknown chunks | `tRNS` becomes alpha channel; Apple `iDOT`, C2PA `caBX`, RGB suggested palette dropped | Palette, 1/2/4-bit, interlaced, HDR (`cICP` PQ/HLG, `mDCv`, `cLLi`), animated |
| WebP | Static 8-bit RGB or RGBA, lossy or lossless; keeps ICC, EXIF, XMP | Lossy quality matched by output size | Animated |
| TIFF | 8/16-bit RGB or grayscale, optional straight alpha; uncompressed, LZW, Deflate, or PackBits; strips or tiles; BigTIFF; multipage (same ID per page); keeps ICC, resolution, descriptive tags, XMP, IPTC | EXIF/GPS directories and private tags | YCbCr, CMYK, palette, JPEG-compressed, 1-bit, fax, packed 10/12-bit, pyramids, stacks |
| DNG | Unsupported | — | Linear DNG whose first image is full-resolution RGB |
| HEIC/HEIF | Static HEVC, 8/10/12-bit, BT.709/BT.601/unspecified matrix, optional straight alpha; keeps depth, subsampling, QP, color signaling, ICC, EXIF, XMP, thumbnail size | Tiled at 512 px; rotation/mirroring/crop baked into pixels; secondary/auxiliary images and declaring XMP; alpha re-encoded lossily | Sequences, HDR/BT.2020, other matrices, premultiplied alpha, non-EXIF/XMP metadata items, grayscale with color ICC, non-HEVC/AV1 |
| AVIF | Static AV1, 8/10/12-bit, BT.709/BT.601/identity/unspecified matrix, single or grid, optional straight alpha; keeps depth, subsampling, quantizers, color signaling, ICC, EXIF, XMP, thumbnail size | Grids re-tiled at 512 px; rotation/mirroring baked in; secondary/gain-map images and declaring XMP; alpha re-encoded at source quantizer | Sequences, layered, `clap` crops, HDR/BT.2020, other matrices, premultiplied alpha, non-EXIF/XMP metadata items, grayscale with color ICC |
| JPEG XL | 8/10/12/16-bit lossless or lossy (XYB VarDCT); RGB (sRGB/Display P3) or grayscale; D65; sRGB/BT.709/linear/DCI transfer; optional straight alpha; keeps EXIF & XMP boxes; `jbrd` JPEG watermarked as JPEG | Orientation baked in; gain map (`jhgm`) and C2PA boxes dropped | ICC (except `jbrd`), other color encodings, HDR, animation, preview frames, layers, premultiplied alpha, extra channels, rotated `jbrd` |
| GIF | Static or animated, up to 10,000 frames (same ID per frame); preserves palettes, delays, disposal, loop count, transparency, interlacing, comments, XMP, ICC | Per-frame palette recoded without dithering; C2PA blocks dropped | Plain text extensions, out-of-screen frames, > 10,000 frames |
| BMP | Unsupported | — | Static images |

**Size limits (watermarking):** ≤ 400 million pixels total (across all pages/frames); minimum 100 px shortest side and 16,384 pixels (128 × 128) total; HEIC/HEIF and AVIF grids ≤ 1,000 tiles; AVIF decode cap 268 million pixels.

---

## Watermark Audio and Video Restrictions

### Audio

Lossless WAV and FLAC retain native sample rates (44.1–192 kHz) and speaker layouts up to 8 channels (quad, 5.0, 5.1, 6.1, 7.1; LFE left unmarked; multichannel WAV requires `WAVEFORMATEXTENSIBLE` speaker mask). MP3, AAC, and audio in video containers are limited to mono/stereo.

| Format | Encode | Dropped or changed | Recovery only |
| --- | --- | --- | --- |
| WAV | Signed PCM 16/24/32-bit or float32; keeps `LIST/INFO`, `bext`, `iXML` | Individual out-of-range integer samples saturated (warned) | 8-bit unsigned, ADPCM, µ/A-law, float64 |
| FLAC | 16/24-bit, 1–8 channels; keeps tags & pictures | Seek table; compression level reset (lossless) | Other bit depths |
| MP3 | CBR/ABR/VBR; keeps ID3v2, APEv2, Lyrics3, ID3v1 | Bitrate approximated | Free-format streams |
| M4A | AAC-LC, 1 audio stream, unencrypted, non-fragmented | Bitrate approximated; Apple timed metadata dropped | HE-AAC, fragmented |
| Raw AAC (ADTS) | AAC-LC; keeps ID3v2/APEv2/Lyrics3/ID3v1 | Bitrate approximated; first 1,024 samples encoder priming | HE-AAC |
| OGG, AIFF | Unsupported | — | All |

### Video

| Video codec | Container | Profiles | Depth / chroma |
| --- | --- | --- | --- |
| H.264 | MP4, MOV | Constrained Baseline, Baseline, Main, High, High 10 | 8/10-bit 4:2:0 |
| HEVC | MP4, MOV | Main, Main 10, Rext | 8/10/12-bit 4:2:0 |
| ProRes 422 | MOV | Proxy, LT, Standard, HQ | 10-bit 4:2:2 |

- Progressive SDR only (BT.709, SMPTE 170M, BT.470BG, or untagged); H.264/HEVC re-encoded at CRF 18 capped at source bitrate; negative timestamps rejected. HDR (PQ/HLG/BT.2020), interlaced, AV1, VP9, 4:2:2/4:4:4 H.264/HEVC, and ProRes 4444 are recovery-only.
- **Container tracks (encode):** Exactly 1 video track; mono/stereo AAC-LC audio (plus signed PCM 16/24/32-bit or float32 in MOV) watermarked with the same ID, other audio copied unmarked; subtitles copied; ≤ 1 continuous aligned zero-start `tmcd` track; Apple `mebx`/`mett` timed metadata dropped; no fragmented MP4/MOV or encryption.

---

## Media Actions

Applies to `resize`, `crop`, `trim`, `transcode`, and `repackage`. An action keeps all metadata the target can hold, updates stale dimensions/timecodes, warns for any dropped metadata, and refuses only when picture or sound content would be lost or altered.

| Input | `resize`, `crop` | `trim` | `transcode` targets | `repackage` targets |
| --- | --- | --- | --- | --- |
| JPEG, PNG, WebP, AVIF, TIFF, GIF | Yes | No | Any of the 6 image targets | No |
| HEIC, HEIF, JPEG XL | No | No | Any of the 6 image targets | No |
| MP4, MOV | Yes | Yes | MP4, MOV | MP4, MOV |
| FLAC, WAV, M4A, MP3 | No | Yes | Any of the 4 audio targets | No |
| AVI | No | No | MP4, MOV | MP4, MOV |

**Size limits (input and output):** Images ≤ 400 MP (counting all animation frames) and ≤ 10,000 frames; JPEG ≤ 65,500 px/side, WebP ≤ 16,383, GIF ≤ 65,535; video frames ≤ 8,192 px on the longer side and ≤ 35,389,440 px area.

### Metadata held by each target

| Target | Holds |
| --- | --- |
| `image/jpeg` | DPI, comments, ICC, EXIF (≤ 65,527 B), XMP (≤ 65,504 B); IPTC/Photoshop (APP13) from a JPEG input |
| `image/png` | DPI, comments, ICC, EXIF, XMP |
| `image/webp`, `image/avif` | ICC, EXIF, XMP |
| `image/tiff` | DPI, ICC, XMP; IPTC and descriptive tags from a TIFF input |
| `image/gif` | Comments, XMP (without NUL) |
| `audio/flac` | Cover picture, tags |
| `audio/wav` | Tags |
| `audio/mp4`, `audio/mpeg` | Cover picture, chapters, tags |
| `video/mp4` | JPEG/PNG cover picture, chapters, `mov_text` subtitles, 1 timecode, tags |
| `video/quicktime` | Chapters, `mov_text` subtitles, 1 timecode, tags |

When the output keeps the input's format (`resize`, `crop`, or a same-format `transcode`), format-specific metadata is also kept: JPEG IPTC/Photoshop (APP13) resources and coding segments, PNG text and hints, WebP background color, and TIFF IPTC and descriptive tags. Converting to another format drops it (with a warning).

**Dropped and named in warnings:**
- Format-specific metadata when converting away (PNG text/hints, JPEG coding segments, WebP background color, IPTC, TIFF descriptive tags).
- Unrecognized chunks/segments/tags, TIFF EXIF/GPS directories, data tracks, and unsupported tags.
- `crop`: drops EXIF and Photoshop thumbnails (or whole EXIF if thumbnail cannot be safely stripped).
- `trim`: drops subtitles, and drops timecode when `start > 0`.
- `transcode`: keeps the primary image and drops secondary images (gain maps, depth maps, thumbnails) and declaring XMP from **JPEG (including Ultra HDR / MPF / ISO 21496)**, **HEIC/HEIF**, and **JPEG XL**. *(Non-JPEG trailing bytes after EOI are still refused.)*

### Refused inputs & conversions

- **Inputs:** Multi-picture HEIC/HEIF (burst/stereo) or sequences; HDR/BT.2020 HEIC/HEIF/AVIF/PNG/video; non-sRGB HEIC/AVIF/JXL without ICC (or JXL with ICC except `jbrd`); CMYK JPEG/TIFF; JPEG with extended XMP or non-JPEG trailing bytes; JPEG or AVIF with secondary images on **`resize` / `crop`**; interlaced PNG; multi-page/layered/pyramid/CMYK/JPEG-compressed TIFF; GIF plain text or out-of-screen frames; encrypted media; video rotated by non-quarter-turns on `resize`/`crop`; audio/video without exactly 1 primary stream.
- **Target constraints:** Non-opaque transparency into JPEG; partial transparency into GIF; 16-bit into JPEG/WebP/AVIF/GIF; non-sRGB PNG color signaling into another format; animations into JPEG/TIFF (or transparent/non-looping animations into AVIF; > 24-day animations into WebP); AAC > 96 kHz / 8 ch, MP3 > 48 kHz / 2 ch, FLAC > 24-bit / 8 ch.

### Error formatting

Format rejections include `Unsupported Format Error:` naming the specific reason. Unreadable files return `Could not process the media file.` (signing/binding) or `400 UndecodableMedia` (`/content/recover`). Under `watermark` `effort_policy: "require_if_supported"`, only MIME eligibility is checked; per-file restrictions still fail unless `best_effort` is used.
