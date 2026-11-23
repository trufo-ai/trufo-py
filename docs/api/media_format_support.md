# Media format support

This reference defines media eligibility for C2PA generation and validation, Trufo
watermark embedding and recovery, and the media actions, in Cloud mode and Local
mode.

A file is supported when its MIME type is eligible for the operation and the file
passes that operation's checks; a supported container does not make every file in
it supported. Signing with a watermark needs eligibility for both operations.

See the [C2PA API reference](api_c2pa.md) for authentication, execution modes,
request limits, actions, and thumbnail eligibility, and
[Local mode with the Python SDK](../local/python.md) for local installation
requirements.

## MIME types

**Yes** means eligible, subject to per-file checks; **No** means unsupported.
C2PA validation support means the manifest can be read and checked, not that a
particular file has valid credentials. Watermark recovery support (**WM decode**)
does not guarantee that an ID is detected or recovered.

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

Types not listed as eligible are unsupported. C2PA signing accepts images of at
most 400 million pixels. Local mode with the Python SDK does not sign JPEG XL on
Python 3.13 or later. The image and the audio and video restrictions below apply to
watermark operations only; they do not define C2PA codec or pixel-depth limits.
[Media actions](#media-actions) has the actions' own.

An ingredient sent as `media` must be in a format with **Yes** under C2PA
validate; other formats can be declared with `format` instead (see
[`ingredient`](api_c2pa.md#ingredient)).

Media type is detected from the content. Common aliases are normalized:
`audio/x-wav` and `audio/vnd.wave` to `audio/wav`, `audio/x-flac` to
`audio/flac`, `audio/x-mpeg` to `audio/mpeg`, `audio/x-m4a` to `audio/mp4`,
`audio/x-hx-aac-adts` to `audio/aac`, `image/x-tiff` to `image/tiff`, and
`video/x-m4v` to `video/mp4`. Watermark operations also normalize `audio/x-aiff`
to `audio/aiff` and `image/mpo` to `image/jpeg`. An MP4 containing audio but no
video stream is treated as `audio/mp4`. DNG identity tags distinguish DNG from
ordinary TIFF.

## Image restrictions

Encoding rewrites the file in its source format, with the source's encoding
settings and metadata, except what the table lists as dropped or changed. Inputs
it cannot reproduce are rejected, not converted. Recovery is read-only and also
accepts the inputs listed under **Recovery only**.

| Format | Encode | Dropped or changed on encode | Recovery only |
| --- | --- | --- | --- |
| JPEG | 8-bit YCbCr, RGB, or grayscale, baseline or progressive; keeps quantization tables, chroma subsampling, ICC, EXIF (thumbnail included), XMP, comments, IPTC/Photoshop (APP13), DPI | Secondary images of a multi-picture JPEG (Ultra HDR or ISO gain maps, depth, burst, stereo) and the XMP declaring them; other APPn segments; quantization tables coarser at DC than at the highest frequency become standard quality-90 tables | CMYK, YCCK |
| PNG | 8/16-bit RGB, RGBA, grayscale, or grayscale with alpha, non-interlaced; keeps ICC, sRGB, gAMA, cHRM, SDR `cICP` (RGB, full range), EXIF, DPI, and safe-to-copy chunks such as text; rejects other chunks that are not safe to copy | `tRNS` written as an alpha channel; Apple `iDOT` chunks, C2PA `caBX` chunks, and an RGB image's suggested palette | Palette, 1/2/4-bit, interlaced, HDR (`cICP` PQ/HLG, `mDCv`, `cLLi`), animated |
| WebP | Static 8-bit RGB or RGBA, lossy or lossless; keeps ICC, EXIF, XMP | Lossy quality is matched by output size | Animated |
| TIFF | 8/16-bit RGB or grayscale (black- or white-is-zero), optional straight alpha; uncompressed, LZW, Deflate, or PackBits; strips or tiles, interleaved or planar; BigTIFF; multipage, every page carrying the same ID; keeps ICC, resolution, and descriptive tags such as description, make, model, orientation, software, date, artist, copyright, XMP, and IPTC | Other tags, including EXIF and GPS directories and private tags | YCbCr, CMYK, palette, JPEG-compressed, 1-bit, fax; packed 10/12-bit; pyramids, reduced-resolution pages, stacks |
| DNG | Unsupported | — | Linear DNG whose first image is full-resolution RGB |
| HEIC/HEIF | Static HEVC, 8/10/12-bit, BT.709 or BT.601 matrix, or unspecified, optional straight alpha; keeps depth, chroma subsampling, coding QP, color signaling, ICC, EXIF, XMP, thumbnail size | Tiled at 512 px; rotation, mirroring, and crop written into the pixels; secondary, depth, and auxiliary images (gain maps, mattes) and the XMP declaring them; alpha re-encoded lossily | Sequences, HDR or BT.2020, other matrices, premultiplied alpha, metadata items other than EXIF and XMP, grayscale with a color ICC profile, images not coded with HEVC or AV1 |
| AVIF | Static AV1, 8/10/12-bit, BT.709, BT.601, or identity (lossless RGB) matrix, or unspecified, single image or grid, optional straight alpha; keeps depth, chroma subsampling, quantizers (to the nearest encoder step), quantizer matrices, color signaling, ICC, EXIF, XMP, thumbnail size | Grids re-tiled at 512 px; rotation and mirroring written into the pixels; secondary, depth, and gain-map images and their XMP; alpha re-encoded at its source quantizer | Sequences, layered images, decoder model info, crops (`clap`), HDR or BT.2020, other matrices, premultiplied alpha, metadata items other than EXIF and XMP, grayscale with a color ICC profile |
| JPEG XL | 8/10/12/16-bit, lossless or lossy (XYB VarDCT); RGB with sRGB or Display P3 primaries, or grayscale; D65 white point; sRGB, BT.709, linear, or DCI transfer; optional straight alpha; keeps EXIF and XMP boxes; a recompressed JPEG (`jbrd`) is watermarked as that JPEG | Orientation written into the pixels; gain map (`jhgm`) and C2PA boxes | ICC profiles (except on a recompressed JPEG), other color encodings, HDR, animation, preview frames, layers, premultiplied alpha, other extra channels, VarDCT without XYB, lossy XYB modular, non-default resampling, other boxes, rotated recompressed JPEGs |
| GIF | Static or animated, up to 10,000 frames, every frame carrying the same ID; keeps the file block for block (palettes, delays, disposal, loop count, transparency, interlacing, comments, XMP, ICC) | Each frame's pixels re-coded to its own palette without dithering; C2PA blocks | Plain text extensions, other application extensions, frames outside the logical screen, more than 10,000 frames |
| BMP | Unsupported | — | Static images |

Encoding embeds the watermark in the color channels only. Grayscale stays
grayscale, straight alpha is kept exactly, and fully transparent pixels keep
their color, except where the table says alpha is re-encoded. Color profiles are
kept, never converted. Lossless sources stay lossless; lossy sources re-encode
with the parameters the file records and add one generation of codec loss. GIF
palette rounding makes the mark weaker than in other formats, and a coarse
palette can lose it.

Watermark operations reject images over 400 million pixels; encoding counts all
pages or frames together. Image and video frames must be at least 100 px on the
shortest side and 16,384 pixels (128 × 128) in total. HEIC/HEIF encoding, and
AVIF grid encoding, rejects images that would need more than 1,000 tiles (about
255 million pixels at 4:3, 126 million with alpha); recovery still reads them.
AVIF images over 268 million pixels cannot be read.

Recovery reads the primary image at native depth, without auxiliary images or
alpha; AVIF and animated PNG are read at 8 bits, and other color modes through
an 8-bit RGB conversion. Animated images and multipage TIFFs are read as up to
20 evenly spaced frames or full-resolution pages (fewer when they total more
than 400 million pixels), pooled like video frames. JPEG XL is read from its
first frame.

## Audio and video restrictions

Watermark encoding requires finite audio samples and keeps the sample rate,
channel layout, timing, and metadata, except as listed. WAV and FLAC support
speaker layouts through eight channels, including quad, 5.0, 5.1 back/side,
6.1, and 7.1. Each full-range channel carries the same ID; an explicitly
identified LFE channel remains unchanged. Multichannel WAV requires an explicit
WAVEFORMATEXTENSIBLE speaker mask; FLAC uses its standard assignment unless a
channel-mask tag overrides it. Unknown or ambisonic layouts are rejected.
MP3, AAC, and audio embedded in video containers remain limited to mono/stereo.

Lossless audio retains native sample rates, including qualified 44.1, 48, 88.2,
96, 176.4, and 192 kHz cases. Integer PCM is rounded to its original valid-bit
precision; only out-of-range output samples are saturated, with their count
reported in a warning. The complete track is not normalized. Float32 WAV
retains finite headroom beyond ±1.0. Recovery reads the channel mix, then individual
channels if the mix has no recoverable ID. A downmix that exactly cancels the
marked signal has no recoverable ID.

| Format | Encode | Dropped or changed on encode | Recovery only |
| --- | --- | --- | --- |
| WAV | Signed PCM 16/24/32-bit or 32-bit float; preserves native precision, channel order, speaker mask, and valid bits; legacy mono/stereo may omit the mask; keeps `LIST/INFO`, `bext`, and `iXML` chunks; rejects nonzero PCM padding bits and other chunks, including a C2PA manifest | Integer samples outside the representable range are saturated individually | Unsigned 8-bit PCM, ADPCM, µ-law, A-law, 64-bit float |
| FLAC | 16/24-bit, one to eight speaker channels; keeps channel order and supported speaker assignments, including explicit channel-mask tags, and other metadata blocks (tags, pictures) byte for byte | Seek table; compression level reset (still lossless); integer samples outside the representable range are saturated individually | Other bit depths |
| MP3 | CBR, ABR, or VBR; keeps ID3v2, APEv2, Lyrics3, and ID3v1 tags byte for byte | Bitrate approximated | Free-format streams |
| M4A | AAC-LC, exactly one audio stream, no timecode tracks or encryption; keeps container and stream tags, cover art, data tracks, gaps, and start offset | Bitrate approximated; Apple timed-metadata tracks | HE-AAC and other AAC profiles; fragmented files |
| Raw AAC (ADTS) | AAC-LC; keeps ID3v2, APEv2, Lyrics3, and ID3v1 tags byte for byte | Bitrate approximated; the first 1,024 samples are replaced by encoder priming | HE-AAC and other AAC profiles |
| OGG (Vorbis, Opus), AIFF | Unsupported | — | All |

| Video codec | Container | Profiles | Depth / chroma |
| --- | --- | --- | --- |
| H.264 | MP4, MOV | Constrained Baseline, Baseline, Main, High, High 10 | 8/10-bit 4:2:0 |
| HEVC | MP4, MOV | Main, Main 10, Rext | 8/10/12-bit 4:2:0 |
| ProRes 422 | MOV | Proxy, LT, Standard, HQ | 10-bit 4:2:2 |

Encoding re-encodes one progressive SDR video stream with its source codec,
profile, depth, chroma subsampling, dimensions, rotation, and pixel aspect ratio:
H.264 and HEVC at constant quality (CRF 18) capped at the source bitrate, ProRes
at its source profile. Every frame keeps its source presentation time, so
constant and variable frame rates and nonzero starts are kept. The color matrix
must be BT.709, SMPTE 170M, or BT.470BG, with limited or full range; an untagged
matrix or range is read as BT.709 limited range and stays untagged. HDR (PQ, HLG,
BT.2020), interlaced video, and other codecs and profiles (such as AV1, VP9,
MPEG-4, 4:2:2 or 4:4:4 H.264/HEVC, ProRes 4444) are recovery only. Encoding
rejects video with negative timestamps.

| Container property | Encoding | Recovery |
| --- | --- | --- |
| Video tracks | Exactly one | Reads the default (else first) video track |
| Audio tracks | AAC-LC, mono or stereo; in MOV also signed PCM 16/24/32-bit or 32-bit float, either byte order. Each is watermarked independently with the same ID; other audio tracks are copied without a watermark | Reads every audio track |
| Subtitles | Copied | Ignored |
| Timecode | At most one continuous `tmcd` track, aligned with the video's frame rate, zero start, and duration; regenerated | Ignored; multiple or discontinuous tracks accepted |
| Data tracks | Copied, and rejected if a track cannot be copied faithfully; Apple timed-metadata tracks (`mebx`, `mett`) are dropped | Ignored |
| Container structure | No fragmented MP4/MOV, encrypted media, or other track types | Fragmented MP4/MOV accepted; encrypted media unsupported |

Encoding embeds the same watermark ID in every video frame and each watermarked
audio track. Subtitles and timecode do not carry the watermark. Recovery reads
at least 20 evenly spaced video frames (every frame when there are fewer), or one
frame per second of video when that is more, and every audio track. When tracks
disagree, recovery returns the ID found in the most tracks.

## Media actions

The [`resize`](api_c2pa.md#resize), [`crop`](api_c2pa.md#crop),
[`trim`](api_c2pa.md#trim), [`transcode`](api_c2pa.md#transcode) and
[`repackage`](api_c2pa.md#repackage) actions change only what the request names.
Everything else about the file is kept, or the file is refused; the exception is
metadata the output has no place for, which is dropped as the tables below say. Cloud
mode and Local mode apply the same rules; in Local mode, audio and video actions need
`ffmpeg` and `ffprobe` on the PATH. The actions run on CPython 3.10 to 3.15 and do
not accept HEIC, HEIF or JPEG XL input.

| Input | `resize`, `crop` | `trim` | `transcode` targets | `repackage` targets |
| --- | --- | --- | --- | --- |
| Images | Yes | No | Any image type | No |
| MP4, MOV | Yes | Yes | MP4, MOV | MP4, MOV |
| FLAC, WAV, M4A, MP3 | No | Yes | Any audio type | No |
| AVI | No | No | MP4, MOV | MP4, MOV |

The image types are JPEG, PNG, WebP, AVIF, TIFF and GIF, and the audio types FLAC,
WAV, M4A and MP3. Other types, including HEIC/HEIF, JPEG XL, DNG and SVG, are
refused.

Images may be animated. Outputs are limited to 400 million pixels (an animation's
frames counted together), JPEG to 65,500 pixels on a side, WebP to 16,383 and GIF to
65,535, and video frames to 8,192 pixels on the longer side and 8,192 × 4,320 pixels.
An embedded C2PA manifest is never carried over: the new manifest keeps the input as
its parent.

### Image inputs

Besides the sizes above, the actions refuse the following; malformed EXIF makes an
image unreadable (`Could not process the media file.`).

| Format | Refused |
| --- | --- |
| JPEG | CMYK; a gain map or other secondary images (multi-picture, Ultra HDR, a JFIF thumbnail); extended XMP; data after the end of the image |
| PNG | Interlaced; HDR (`mDCv`, `cLLi`, or `cICP` with PQ or HLG); `cICP` that is not full-range RGB |
| WebP | Data after the end of the image |
| AVIF | More than 8 bits; depth maps, gain maps or other secondary images; HDR or BT.2020; premultiplied alpha; color signaling other than sRGB without an ICC profile |
| TIFF | More than one page; pyramids, reduced-resolution pages and stacks; samples other than 8 or 16 bits; CMYK; compression other than none, LZW, Deflate or PackBits; extra channels or premultiplied alpha; Photoshop layers |
| GIF | Plain text extensions; frames outside the logical screen |
| Animations | More than 10,000 frames; rotated or mirrored; 16-bit animated PNG; an animated PNG whose default image is not a frame; animated AVIF with transparency or other extra tracks, or that does not loop forever |

### Image outputs

An image transcoded into another format keeps its picture, or is refused:

| Target | Refused |
| --- | --- |
| `image/jpeg` | Transparency, unless every pixel is opaque; 16-bit samples; EXIF or XMP larger than a JPEG segment holds (about 64 KB) |
| `image/webp` | 16-bit samples; grayscale with a gray ICC profile |
| `image/avif` | 16-bit samples |
| `image/gif` | 16-bit samples; partial transparency |
| `image/png`, `image/tiff` | — |

GIF keeps up to 256 colors and reduces more by median cut, without dithering; a
transparent pixel stays transparent. An animation keeps each frame, drawn onto the
full canvas, its timing and its loop count, rounded to what the target holds (GIF
counts hundredths of a second); `image/avif` refuses an animation with transparency
or one that does not loop forever, and `image/webp` one longer than 24 days. A crop
crops every frame.

Metadata in an image from another format, by target. **Kept**; **Documented**:
dropped, as this table says; **Reported**: dropped and named in a response
[warning](api_c2pa.md#response-warnings); **Refused**: the file is refused. A resize
or a crop, or a transcode within one format, keeps all of this metadata except where
the **Same format** column says otherwise.

| Metadata | JPEG | PNG | WebP | AVIF | TIFF | GIF |
| --- | --- | --- | --- | --- | --- | --- |
| ICC color profile | Kept | Kept | Kept | Kept | Kept | Reported |
| EXIF metadata | Kept | Kept | Kept | Kept | Reported | Reported |
| XMP metadata | Kept | Kept | Kept | Kept | Kept | Kept; Reported when it holds a NUL byte |
| Pixel density | Kept | Kept | Documented | Documented | Kept | Documented |
| Comments | Kept | Kept | Documented | Documented | Documented | Kept |

| Metadata only its own format holds | Same format | Another format |
| --- | --- | --- |
| IPTC metadata (JPEG, TIFF) | Kept | Reported |
| PNG text, other than comments | Kept | Documented |
| PNG background, significant bits and time | Kept (see below) | Documented |
| PNG color signaling other than sRGB (`gAMA`, `cHRM`, `cICP`) | Kept | Refused |
| TIFF descriptive tags, such as description, make, model, software, date, artist and copyright | Kept | Reported |
| WebP animation background color | Kept | Documented |
| PNG chunks that are safe to copy | Kept | Reported |
| JPEG Adobe and Ducky segments, which describe the source's coding | Documented | Documented |
| TIFF EXIF and GPS directories, shown as EXIF metadata | Reported | Reported |
| Unrecognized metadata | Reported | Reported |

A PNG written in another layout, such as a palette image written as RGB, drops its
background and significant bits (Documented). Unrecognized metadata includes other
JPEG segments, PNG chunks that are not safe to copy, other WebP chunks, GIF
extensions, AVIF items and TIFF tags.

A crop moves the EXIF subject area with the picture, and drops the EXIF thumbnail and
a JPEG's Photoshop thumbnail, which show the whole picture (Documented). Known
limit: XMP image regions and the EXIF subject location are kept as they are, so they
still describe the uncropped picture.

### Audio

A `transcode` or `trim` re-encodes the audio stream at its sample rate and with its
channels, or refuses it; a file with more than one audio stream, besides a cover
picture, is refused.

| | `audio/flac` | `audio/wav` | `audio/mp4` (AAC) | `audio/mpeg` (MP3) |
| --- | --- | --- | --- | --- |
| Samples | The source's depth, up to 24 bits; 32-bit and floating-point refused; 16 bits from a lossy source | PCM at the source's depth, 16, 24 or 32 bits or floating-point; 16 bits from a lossy source | AAC at `audio_bitrate` | MP3 at `audio_bitrate` |
| Sample rate | Kept | Kept | Kept, at a rate AAC codes, up to 96 kHz | Kept, at a rate MP3 codes, up to 48 kHz |
| Channels | Up to 8 | Kept | Up to 8 | Up to 2 |
| Cover picture | Kept | Reported | Kept | Kept |
| Chapters | Reported | Reported | Kept | Kept |

Metadata tags are kept as far as the target holds them; the rest are Reported.
Documented: WAV chunks that hold neither audio nor tags, such as cue points; FLAC
application and cue sheet blocks; ID3 frames that do not map to tags; an M4A
source's XMP; and an audio file's start offset.

A trim re-encodes the audio in its own codec where Trufo writes that codec, else as
AAC; chapters within the span are kept, cut to it.

| Source audio | In | Written as |
| --- | --- | --- |
| PCM | WAV, MP4, MOV | PCM at its depth, sample for sample |
| FLAC | FLAC, MP4 | FLAC, sample for sample |
| AAC | M4A, MP4, MOV | AAC at 192 kbit/s |
| MP3 | MP3, MP4, MOV | MP3 at 192 kbit/s |
| Other, such as ALAC, Opus or AC-3 | M4A, MP4, MOV | AAC at 192 kbit/s |

### Video

A `transcode`, `repackage`, `resize`, `crop` or `trim` keeps the file's streams: each
is copied when the target holds it and nothing asks to re-encode it, else re-encoded
(a `repackage` refuses instead; a `trim` re-encodes every audio and video stream, and
its video begins with the first frame at or after `start`). A file with more than one
video stream, more than one timecode track or encrypted media is refused, and a
`resize` or `crop` refuses video rotated by other than quarter turns. Re-encoding
video keeps its pixel format, color tags, pixel aspect ratio, timestamps and rotation,
and refuses HDR, interlaced video and pixel formats other than planar YUV without
alpha, at 8 or 10 bits, or 12 bits for H.265.

| Stream or property | Kept as |
| --- | --- |
| Video | Copied, or re-encoded as H.264 or H.265 at `crf` |
| Audio | Copied, or re-encoded as AAC at `audio_bitrate`, at a rate AAC codes, up to 96 kHz, and up to 8 channels |
| `mov_text` subtitles | Copied; after a trim, Reported |
| Other subtitles | Copied within the same container, else Reported; after a trim, Reported |
| Data tracks, such as Apple timed metadata and camera telemetry | Reported |
| Cover picture | `video/mp4`: Kept, from another container only as JPEG or PNG, else Reported; `video/quicktime`: Reported |
| Chapters | Kept; after a trim, those within the span, cut to it (one that only touches it is dropped) |
| Timecode | Regenerated; after a trim that starts after the beginning, Reported |
| Container tags | Kept as the target writes them, else Reported as metadata tags |

Trufo reads the output back and refuses it if a stream, the rotation, a chapter or
the timecode went missing.

## Unsupported inputs

Format rejections include `Unsupported Format Error:` and name what is
unsupported. Signing and Cloud-mode watermark operations report media they cannot
read as `Could not process the media file.` Watermark recovery
(`POST /content/recover`) returns `400 UndecodableMedia` for inputs outside the
supported types or per-file restrictions. For watermark actions during signing,
see [`effort_policy`](api_c2pa.md#watermark). `require_if_supported` checks only
the media type, so a file of an eligible type that fails a restriction on this
page fails the sign; only `best_effort` signs it without a watermark. Signing
requires a C2PA-eligible format under every watermark policy. Contact
[support@trufo.ai](mailto:support@trufo.ai) about additional formats, providing
a sample file and the use case.
