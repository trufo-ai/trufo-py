# Media format support

This reference defines media eligibility for C2PA generation and validation, and
Trufo watermark encoding and decoding (recovery). It covers the current hosted
APIs and local operations using Trufo SDK 1.5.2 with Provenance 1.6.0 and
Pawprint 0.4.0.

Support has two layers: the MIME type must be eligible for the operation, and the
file must pass that operation's parser, codec, layout, and preservation checks.
A supported container does not make every file in that container supported.
C2PA signing with watermarking requires eligibility for both operations.

See the [C2PA API reference](api_c2pa.md) for authentication, execution modes,
request limits, actions, and thumbnail eligibility, and the
[setup guide](../quickstart/0_setup.md) for installation requirements.

## MIME types

**Yes** means eligible, subject to per-file checks; **No** means unsupported.
C2PA validation support means the manifest can be read and checked, not that a
particular file has valid credentials. Watermark decoding support does not
guarantee detection or recovery of an ID.

| Media | MIME types | C2PA generate | C2PA validate | WM encode | WM decode |
| --- | --- | --- | --- | --- | --- |
| JPEG, PNG, WebP, TIFF | `image/jpeg`, `image/png`, `image/webp`, `image/tiff` | Yes | Yes | Yes | Yes |
| WAV, FLAC, MP3, M4A | `audio/wav`, `audio/flac`, `audio/mpeg`, `audio/mp4` | Yes | Yes | Yes | Yes |
| MP4, MOV | `video/mp4`, `video/quicktime` | Yes | Yes | Yes | Yes |
| AVIF, JPEG XL, DNG, PDF | `image/avif`, `image/jxl`, `image/x-adobe-dng`, `application/pdf` | Yes | Yes | No | No |
| Raw AAC (ADTS) | `audio/aac` | Yes | Yes | No | Yes |
| HEIC/HEIF, GIF, BMP | `image/heic`, `image/heif`, `image/gif`, `image/bmp` | No | No | No | Yes |
| SVG, WebM, AVI | `image/svg+xml`, `video/webm`, `video/avi`, `video/x-msvideo` | No | No | No | No |

Types not listed as eligible are unsupported. C2PA operations still require a
parseable file and a compatible native backend. For example, TIFF/DNG directory
structures, offsets, and existing C2PA tags must pass backend validation;
MIME eligibility does not bypass those guards. The watermark restrictions below
do not define C2PA codec or pixel-depth limits.

Media type is detected from the content. Supplying a MIME type does not bypass
file checks. Common aliases are normalized: `audio/x-wav` and `audio/vnd.wave`
to `audio/wav`, `audio/x-flac` to `audio/flac`, `audio/x-mpeg` to `audio/mpeg`,
`audio/x-m4a` to `audio/mp4`, `audio/x-hx-aac-adts` to `audio/aac`,
`image/x-tiff` to `image/tiff`, and `video/x-m4v` to `video/mp4`.
An MP4 containing audio but no video stream is treated as `audio/mp4`.
DNG identity tags distinguish DNG from ordinary TIFF.

## Image restrictions

These restrictions apply to watermark operations. Images must be static, with
at most 400 million pixels. Animation and image sequences are unsupported;
JPEG gain maps identified by Adobe HDR gain-map XMP are rejected.
Supported alpha is straight (unassociated); watermark processing
retains alpha and fully transparent source pixels. Lossy re-encoding can still
change pixel values.

| Format | Encode | Decode |
| --- | --- | --- |
| JPEG | 8-bit RGB or grayscale; baseline or progressive | 8-bit RGB or grayscale |
| PNG | 8/16-bit RGB or grayscale, with optional alpha; non-interlaced | Also accepts palette, low-bit-depth, and Adam7 inputs; 16-bit precision is retained |
| WebP | 8-bit RGB/RGBA, lossy or lossless | 8-bit RGB/RGBA |
| TIFF | 8/16-bit unsigned RGB or grayscale (black-is-zero or white-is-zero), optional straight alpha; compression: none, LZW, Deflate, or PackBits | Same layout, depth, and compression restrictions |
| HEIC/HEIF | Unsupported | Single 8/10/12-bit SDR image; explicit color matrix: RGB, BT.709, BT.470BG, or SMPTE 170M; no auxiliary/depth images or premultiplied alpha |
| GIF, BMP | Unsupported | Static RGB, grayscale, palette, or bilevel images, with optional alpha where decoded |

PNG rejects HDR metadata and PQ/HLG transfer signaling; when `cICP` is present,
it must specify an RGB matrix and full range. HEIC/HEIF rejects HDR signaling
and missing or unsupported color matrices. TIFF rejects BigTIFF, multiple pages,
pyramids, stacks, DNG, palette/CMYK/YCbCr layouts, extra channels, and
premultiplied alpha. CMYK JPEG is unsupported.

Encoding also checks metadata preservation: EXIF thumbnail directories are
rejected; TIFF rejects tags outside its supported set, including nested EXIF and
private tags; PNG rejects unknown chunks that cannot safely be copied. Recovery
does not require these encoding-only preservation checks.

## Audio and video restrictions

Watermark audio must be mono or stereo with finite samples. The following applies
to encoding and decoding except where a difference is stated.

| Audio format or track | Supported samples/codecs |
| --- | --- |
| WAV | Signed PCM 16/24/32-bit or 32-bit float; unsigned 8-bit is decode-only |
| FLAC | PCM 16/24-bit |
| MP3 | MPEG Layer III |
| M4A; audio tracks in MP4/MOV | AAC-LC; no HE-AAC or ALAC |
| Additional MOV audio tracks | Signed PCM 16/24/32-bit or 32-bit float, either byte order; unsigned 8-bit is decode-only |
| Raw AAC (ADTS) | AAC-LC, decode-only |

Standalone M4A/ADTS requires exactly one audio stream and no other tracks.
WAV encoding rejects metadata chunks outside its preservation set.

| Video codec | Container | Profiles | Depth / chroma |
| --- | --- | --- | --- |
| H.264 | MP4, MOV | Constrained Baseline, Baseline, Main, High, High 10 | 8/10-bit 4:2:0 |
| HEVC | MP4, MOV | Main, Main 10, Rext | 8/10/12-bit 4:2:0 |
| ProRes 422 | MOV | Proxy, LT, Standard, HQ | 10-bit 4:2:2 |

Video must be progressive SDR with an explicit BT.709, SMPTE 170M, or BT.470BG
color matrix and a declared limited or full range. PQ/HLG, BT.2020 primaries,
ProRes 4444, and other profiles or chroma layouts are unsupported.

| Container property | Watermark requirements |
| --- | --- |
| Video tracks | Exactly one, using the codec restrictions above |
| Audio tracks | Zero or more, each meeting the audio restrictions above |
| Subtitles | `mov_text` only; copied during encoding |
| Data tracks | At most one continuous `tmcd` timecode track, aligned to the video's frame rate, zero timeline start, and duration; regenerated during encoding. The timecode label need not start at `00:00:00:00` |
| Container structure | No fragmented MP4/MOV, encrypted media, or other track types |
| Encoding timing | Constant video frame rate with complete timestamps/durations and zero start; audio timestamps must be present and continuous |

Encoding embeds the same watermark ID in every video frame and each audio
stream. Subtitles and timecode do not carry the watermark. Recovery from an
individual frame, extracted track, or transcoded copy depends on the surviving
signal; it is not guaranteed.

## Unsupported inputs

Hosted watermark recovery returns `400 UndecodableMedia` for inputs outside
the supported types or per-file restrictions. For watermark actions during signing, see
[`effort_policy`](api_c2pa.md#watermark); a lenient watermark policy does not
make an unsupported C2PA format signable. Contact
[support@trufo.ai](mailto:support@trufo.ai) about additional formats, providing
a sample file and the use case.
