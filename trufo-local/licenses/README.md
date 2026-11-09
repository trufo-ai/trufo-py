# trufo-local Licenses

The trufo-local images contain third-party software under its own licenses, including the GNU GPL and LGPL. Each image's NOTICE, at `/usr/share/doc/trufo-local/NOTICE` inside it, lists that software. This folder holds the license texts that the images' Python packages leave out, and both images carry it at `/usr/share/doc/trufo-local/licenses/`.

## What Each Image Carries

The signing-only image, built from [`Dockerfile`](https://github.com/trufo-ai/trufo-py/blob/main/trufo-local/Dockerfile), carries Debian's GPL build of FFmpeg, the LGPL libheif and libde265 libraries bundled with pillow-heif, the FFmpeg libraries bundled with opencv-python-headless, and more. Its [NOTICE](https://github.com/trufo-ai/trufo-py/blob/main/trufo-local/NOTICE) lists them all, and [`extra-sources.txt`](https://github.com/trufo-ai/trufo-py/blob/main/trufo-local/extra-sources.txt) lists the sources of the libraries its Python packages bundle. It also carries the JPEG XL library libjxl, with skcms, Highway and Brotli, bundled with jxlpy.

The full image adds watermarking. It is built from [`Dockerfile.full`](https://github.com/trufo-ai/trufo-py/blob/main/trufo-local/Dockerfile.full) on the signing-only image, and adds the libraries bundled with the torch, imagecodecs and soundfile Python packages, among them Intel MKL, OpenBLAS, GCC's libgomp and libgfortran, LAME, mpg123, FLAC, Ogg, Vorbis and Opus. It also adds Debian's `heif-enc`, with its x265 and libaom encoders. Its NOTICE is [`NOTICE-full`](https://github.com/trufo-ai/trufo-py/blob/main/trufo-local/NOTICE-full), and [`extra-sources-full.txt`](https://github.com/trufo-ai/trufo-py/blob/main/trufo-local/extra-sources-full.txt) lists the sources of the libraries those Python packages bundle.

## Files

| File | Covers |
|---|---|
| `libjxl.txt` | libjxl, the JPEG XL library bundled with jxlpy (BSD-3-Clause) |
| `libjxl-patents.txt` | Google's patent grant for libjxl |
| `skcms.txt` | skcms, in the libjxl_cms library bundled with jxlpy (BSD-3-Clause) |
| `highway.txt` | Highway, in the libjxl and libjxl_cms libraries bundled with jxlpy (BSD-3-Clause) |
| `brotli.txt` | Brotli, bundled with jxlpy (MIT) |
| `libgomp.txt` | GCC's OpenMP library, bundled with torch and imagecodecs (GPL-3.0 with the GCC Runtime Library Exception) |
| `libgfortran.txt` | GCC's Fortran library, bundled with torch on arm64 (GPL-3.0 with the GCC Runtime Library Exception) |
| `mkl.txt` | Intel oneAPI Math Kernel Library (MKL), built into torch on amd64 (Intel Simplified Software License) |
| `mkl-third-party-programs.txt` | The third-party notices Intel distributes with MKL |
| `openblas.txt` | OpenBLAS, bundled with torch on arm64 (BSD-3-Clause) |
| `lapack.txt` | The LAPACK code in OpenBLAS (BSD-style) |
| `arm-compute-library.txt` | The Arm Compute Library, bundled with torch on arm64 (MIT) |
| `half.txt` | The half library in the Arm Compute Library (MIT) |
| `kleidiai.txt` | KleidiAI, in the Arm Compute Library (Apache License 2.0) |
| `lame.txt` | LAME, in the libsndfile library bundled with soundfile (LGPL) |
| `mpg123.txt` | mpg123, in the libsndfile library bundled with soundfile (LGPL) |
| `flac.txt` | FLAC, in the libsndfile library bundled with soundfile (BSD-3-Clause) |
| `libogg.txt` | Ogg, in the libsndfile library bundled with soundfile (BSD-3-Clause) |
| `libvorbis.txt` | Vorbis, in the libsndfile library bundled with soundfile (BSD-3-Clause) |
| `opus.txt` | Opus, in the libsndfile library bundled with soundfile (BSD-3-Clause) |

## Trufo's Code

Trufo's own code is not under the GPL or LGPL. Debian's FFmpeg and `heif-enc` with x265, which are GPL, run as separate programs. The LGPL libraries, including libsndfile with LAME and mpg123 built in, are separate, dynamically loaded libraries. GCC's libgomp and libgfortran, which are GPL, load into the same process as Trufo's code under the GCC Runtime Library Exception.

## What Trufo Provides

As distributor, Trufo provides:

- **License texts and notices** in each image: its NOTICE, each Debian package's copyright and license in `/usr/share/doc/`, and this folder.
- **A source image** for each image version, in the image's repository (`ghcr.io/trufo-ai/trufo-local`), tagged with the image's exact version plus `-source`: `2.2.0-source` for `2.2.0`, `2.2.0-full-source` for `2.2.0-full`. It holds the complete corresponding source code of the image's GPL-, LGPL- and MPL-licensed software. The image's `ai.trufo.trufo-local.source` label names it, and [Licenses and Source](https://github.com/trufo-ai/trufo-py/blob/main/docs/local/docker.md#licenses-and-source) shows how to extract it.
- **A written offer** in each NOTICE, to provide the same source on request for at least three years after Trufo last distributes that image version.

## Running and Redistributing an Image

You owe nothing under these third-party licenses to run an image. To redistribute one, pass on its notices and its source; copying its source image with it makes that easy. Intel MKL's license also forbids reverse engineering or modifying MKL.

## Codec Patents

The images contain H.264, HEVC, ProRes and AAC encoders. When the full image watermarks a file, it re-encodes H.264 and HEVC video with x264 and x265, ProRes video with FFmpeg's `prores_ks` encoder, HEVC-coded HEIC and HEIF images with x265 through `heif-enc`, and AAC-LC audio with FFmpeg. Patent licensing for commercial codec use is separate from these copyright licenses, and is yours to assess.
