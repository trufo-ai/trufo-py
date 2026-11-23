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
[`repackage`](api_c2pa.md#repackage) actions follow one rule: an action keeps the
metadata its output can hold, updates what the edit makes stale, names everything
else it did not keep in a [warning](api_c2pa.md#response-warnings), and refuses only
when picture or sound content would be lost or shown differently. A refusal does not
depend on whether the request would change the file: a request that changes nothing
passes the same checks, and only the work is skipped.

A re-encode in the source's format reuses the source's settings where they can be
read, such as a JPEG's quantization tables; when the format changes and no setting is
given, the [`transcode`](api_c2pa.md#transcode) defaults apply, such as quality 90.
A video's `crf` and a lossy audio bitrate cannot be read from the file, so their
defaults apply in either case.

Cloud mode and Local mode apply the same rules; in Local mode, audio and video
actions need `ffmpeg` and `ffprobe` on the PATH. The actions run on CPython 3.10 to
3.15.

| Input | `resize`, `crop` | `trim` | `transcode` targets | `repackage` targets |
| --- | --- | --- | --- | --- |
| Images | Yes | No | Any image type | No |
| MP4, MOV | Yes | Yes | MP4, MOV | MP4, MOV |
| FLAC, WAV, M4A, MP3 | No | Yes | Any audio type | No |
| AVI | No | No | MP4, MOV | MP4, MOV |

The image types are JPEG, PNG, WebP, AVIF, TIFF and GIF, and the audio types FLAC,
WAV, M4A and MP3. Other types, including HEIC/HEIF, JPEG XL, DNG and SVG, are
refused. Images may be animated.

Limits, on input and output: images of at most 400 million pixels, counting all of an
animation's frames, and at most 10,000 frames; JPEG at most 65,500 pixels on a side,
WebP 16,383 and GIF 65,535; video frames with a longer side of at most 8,192 and an
area of at most 35,389,440 pixels.

### What each target holds

What each target holds of a file in another format; a file kept in its own format
keeps everything its format holds, except as the lists below say. Everything else is
named in the warning.

| Target | Holds |
| --- | --- |
| `image/jpeg` | Pixel density, comments, ICC color profile, EXIF metadata up to 65,527 bytes and XMP metadata up to 65,504 bytes |
| `image/png` | Pixel density, comments, ICC color profile, EXIF and XMP metadata |
| `image/webp`, `image/avif` | ICC color profile, EXIF and XMP metadata |
| `image/tiff` | Pixel density, ICC color profile, XMP metadata |
| `image/gif` | Comments, XMP metadata without a NUL byte |
| `audio/flac` | Cover picture, metadata tags |
| `audio/wav` | Metadata tags |
| `audio/mp4`, `audio/mpeg` | Cover picture, chapters, metadata tags |
| `video/mp4` | A JPEG or PNG cover picture, chapters, `mov_text` subtitles, one timecode, metadata tags |
| `video/quicktime` | Chapters, `mov_text` subtitles, one timecode, metadata tags |

- **Held only by their own format**, so named when converting away: PNG text, other
  than comments; PNG background, significant bits and time; JPEG coding segments;
  WebP animation background color; IPTC metadata; TIFF descriptive tags.
- **Named whatever the action:** unrecognized metadata, such as other JPEG segments,
  PNG chunks that are not safe to copy, other WebP chunks, GIF extensions, AVIF items
  and TIFF tags; a TIFF's EXIF and GPS directories, as EXIF metadata; data tracks,
  such as Apple timed metadata and camera telemetry; and metadata tags the target did
  not write.
- **Named by an action:** a PNG written in another layout, such as a palette image
  written as RGB, loses its background and significant bits; a crop drops the EXIF
  thumbnail and a JPEG's Photoshop thumbnail, which show the whole picture; a trim
  drops subtitles, and a timecode when the span starts after the beginning.
- **Updated:** the stored dimensions in EXIF and XMP after a resize or crop; the EXIF
  subject area, moved with a crop; the timecode, written anew. An embedded C2PA
  manifest is never carried over: the new manifest keeps the input as its parent.

A JPEG re-encoded as JPEG writes its own coding segments in place of the source's
Adobe and Ducky segments, without a warning.

### Refused

- **Inputs:** a CMYK JPEG; a JPEG or AVIF with a gain map or other secondary images; a
  JPEG or WebP with data after the end of the image; a JPEG with extended XMP; an
  interlaced or HDR PNG, or one whose `cICP` is not full-range RGB; AVIF above 8 bits,
  with premultiplied alpha, HDR or BT.2020, or with color signaling other than sRGB
  and no ICC profile; a TIFF with more than one page, Photoshop layers, a pyramid,
  reduced-resolution pages, CMYK, samples other than 8 or 16 bits, compression other
  than none, LZW, Deflate or PackBits, or extra channels or premultiplied alpha; GIF
  plain text, or frames outside the logical screen; more than one video or audio
  stream, more than one timecode track, encrypted media, and, for a `resize` or
  `crop`, video rotated by other than quarter turns. Malformed EXIF makes an image
  unreadable (`Could not process the media file.`).
- **Picture:** transparency into JPEG, unless every pixel is opaque; partial
  transparency into GIF; 16-bit samples into JPEG, WebP, AVIF or GIF; a gray image with
  a gray ICC profile into WebP; PNG color signaling other than sRGB into another
  format.
- **Animations:** into JPEG or TIFF; into AVIF, one with transparency or one that does
  not loop forever; into WebP, one longer than 24 days; and, as inputs, more than 8
  bits a channel, a rotated or mirrored animation, an animated PNG whose default image
  is not a frame, and an animated AVIF with transparency or other extra tracks, or that
  does not loop forever.
- **Sound and video:** audio an encoder cannot code at its sample rate, channels or
  depth (AAC: up to 96 kHz and 8 channels; MP3: up to 48 kHz and 2 channels; FLAC: up
  to 24-bit integer samples and 8 channels); video to re-encode that is HDR,
  interlaced, or in a pixel format the codec cannot hold (planar YUV without alpha, at
  8 or 10 bits, or 12 bits for H.265).
- **After writing:** Trufo reads an audio or video output back and refuses it if a
  stream, the rotation, a chapter or the timecode went missing.

### Known limits

These are not detected, so no warning names them:

- after a crop, XMP image regions and the EXIF subject location still describe the
  uncropped picture; after a resize, the EXIF subject area and location keep the
  source's pixel coordinates;
- GIF frame delays are rounded to hundredths of a second, up to 655.35 s; animated PNG
  delays over 65.535 s are rounded to whole seconds; loop counts are capped at 65,536
  plays for GIF and 65,535 for WebP;
- WAV chunks that hold neither audio nor tags, such as cue points; FLAC application
  and cue sheet blocks; ID3 frames that do not map to tags; an M4A source's XMP; and
  an M4A's start offset, in a `transcode` to WAV, FLAC or MP3, are not carried over;
- a re-encoded AVI video with B-frames starts two frames after its audio.

### Audio and video

A `transcode`, `repackage`, `resize`, `crop` or `trim` keeps the file's streams: each
is copied when the target holds it and nothing asks to re-encode it, else re-encoded
(a `repackage` refuses instead). Into its own container, a file keeps every stream in
its own codec. Re-encoding video keeps its pixel format, color tags, pixel aspect
ratio, timestamps and rotation; re-encoding audio keeps its sample rate and channels.

A `trim` re-encodes every audio and video stream, copies cover pictures, and keeps
the chapters within the span, cut to it; one that only touches the span is dropped.
Its video begins with the first frame at or after `start`, up to one frame after the
audio. Its audio keeps its codec where Trufo writes that codec, else becomes AAC:

| Source audio | In | Written as |
| --- | --- | --- |
| PCM | WAV, MP4, MOV | PCM at its depth, sample for sample |
| FLAC | FLAC, MP4 | FLAC, sample for sample |
| AAC | M4A, MP4, MOV | AAC at 192 kbit/s |
| MP3 | MP3, MP4, MOV | MP3 at 192 kbit/s |
| Other, such as ALAC, Opus or AC-3 | M4A, MP4, MOV | AAC at 192 kbit/s |

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
