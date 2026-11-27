# Local Signing (Docker)

The Docker image `ghcr.io/trufo-ai/trufo-local` runs C2PA Signing in Local mode as a local HTTP service on your infrastructure. Callers in **any language** (Node.js, Go, .NET, Java, Rust, Python) send input and output file paths over HTTP, and the container signs locally while keeping raw media on your machine.

---

## Choose an Image

Both multi-arch (`linux/amd64`, `linux/arm64`) images serve only `GET /health` and `POST /c2pa/sign`. The container does not proxy other Trufo API routes (`/ai-system/*`, `/c2pa/software-agent/*`, `/bind/*`, `/content/*`) — call those on `TRUFO_API_URL` directly:

- **`ghcr.io/trufo-ai/trufo-local:2.4`** (default): C2PA signing + all media actions (`resize`, `crop`, `trim`, `transcode`, `repackage`, `redact`), no watermarking.
- **`ghcr.io/trufo-ai/trufo-local:2.4-full`**: Adds CPU watermark embedding for every watermark-supported format (including HEIC, HEIF, and AVIF with bundled `heif-enc` and `ffmpeg`).

| Approximate footprint | Signing-only (`2.4`) | Full (`2.4-full`) |
| --- | --- | --- |
| Pulled (compressed) | ~320–350 MB | ~550–620 MB |
| Unpacked | ~0.8–0.9 GB | ~1.7–1.9 GB |
| Idle memory | ~110 MiB | ~300 MiB |

---

## Prerequisites

- Docker with Compose (or Kubernetes / ECS).
- An **`sdk-download` key** (put in `.env`; requires the *Trufo Library License* accepted in [Agreements](https://app.trufo.ai/settings/org#agreements) and a signing plan, or test SDK access from `support@trufo.ai`).
- A **`c2pa-sign-prod` key** (plus completed OV) or **`c2pa-sign-test` key** (with `TRUFO_API_URL=https://test.api.trufo.ai`), sent per request.
- Outbound HTTPS to `packages.trufo.ai` on container startup and to `TRUFO_API_URL` on each signing request.

---

## Quick Start

1. **Fetch `compose.yaml` and `.env.example`** from [`trufo-local/`](../../trufo-local/):

```bash
mkdir trufo-local && cd trufo-local
curl -fsSLO https://raw.githubusercontent.com/trufo-ai/trufo-py/main/trufo-local/compose.yaml
curl -fsSL -o .env https://raw.githubusercontent.com/trufo-ai/trufo-py/main/trufo-local/.env.example
chmod 600 .env
```

2. **Add your `sdk-download` key** to `.env` after `TRUFO_SDK_DOWNLOAD_API_KEY=`.

3. **Review `compose.yaml`:**

```yaml
services:
  trufo-local:
    image: ghcr.io/trufo-ai/trufo-local:2.4   # or 2.4-full for watermarking
    user: "1000:1000"                         # match owner of your media folders (id -u / id -g)
    env_file: .env
    environment:
      TRUFO_API_URL: https://api.trufo.ai     # EU: https://eu.api.trufo.ai · test: https://test.api.trufo.ai
      TRUFO_LOCAL_INPUT_DIRS: /srv/media/in   # colon-separated allowed input dirs
      TRUFO_LOCAL_OUTPUT_DIRS: /srv/media/out # colon-separated allowed output dirs
    volumes:
      - /srv/media/in:/srv/media/in:ro
      - /srv/media/out:/srv/media/out
    ports:
      - "127.0.0.1:8080:8080"
    restart: unless-stopped
```

Create `/srv/media/in` and `/srv/media/out` before starting so Docker does not auto-create them owned by `root`.

4. **Start and verify health:**

```bash
docker compose up -d
docker compose ps    # wait for "(healthy)" (~5–20s on first start while engine downloads)
curl -s http://127.0.0.1:8080/health
# {"status":"healthy","version":"2.4.0","engine_version":"2.4.0"}
# 2.4-full images also report the watermark engine:
# {"status":"healthy","version":"2.4.0-full","engine_version":"2.4.0","watermark_engine_version":"<version>"}
```

When a new container starts, the entrypoint uses `TRUFO_SDK_DOWNLOAD_API_KEY` to download and hash-verify the engine wheels from `packages.trufo.ai` into `/tmp` before the service becomes healthy (restarting the same container reuses `/tmp`); a refused or missing key stops the container with an explicit message in `docker compose logs`.

---

## Sign a File

Send `X-API-Key` with each request:

```bash
curl -s http://127.0.0.1:8080/c2pa/sign \
  -H "X-API-Key: $TRUFO_C2PA_SIGN_PROD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "media_input_path": "/srv/media/in/photo.jpg",
    "media_output_path": "/srv/media/out/photo.jpg",
    "actions": [["publish", {}]],
    "manifest_settings": {"manifest_title": "photo.jpg", "ingredient_title": "photo.jpg"}
  }'
# {"media_output_path":"/srv/media/out/photo.jpg","warnings":[]}
```

| Field | Required | Description |
| --- | --- | --- |
| `media_input_path` | Yes | Absolute path inside `TRUFO_LOCAL_INPUT_DIRS` |
| `media_output_path` | Yes | Absolute path inside `TRUFO_LOCAL_OUTPUT_DIRS` |
| `actions` | Yes | Same schema as [Actions and Assertions](../reference/actions-and-assertions.md) |
| `assertions`, `manifest_settings`, `manifest_title` / `ingredient_title` (top-level aliases; do not combine with the same field in `manifest_settings`), `branded_gp_id`, `signed_input_policy`, `signed_ingredient_policy`, `skip_manifest_storage` | No | Same schema as [Signing API](../reference/signing-api.md) |
| `remote_manifest_settings` | No | `{"fetch": false}` or `{"allowed_hosts": ["manifests.example.com"]}` (`2.4.1` image or later); see [Remote Manifests](../reference/actions-and-assertions.md#remote-manifests) |
| `watermark_settings` | No | `{"profile": "default"}` or `{"profile": "fast"}` (`2.4-full` only) |

**Important path rules:**
- **Extension normalization:** The returned `media_output_path` resolves symlinks and normalizes the extension to match the signed format (e.g., `.jpeg` / `.JPG` → `.jpg`, `.tif` → `.tiff`, or the new format after `transcode`/`repackage`). Always read the output path from the response JSON.
- **Overwrite behavior:** The output path is overwritten if it already exists — send one request per output path at a time and use unique filenames per job.
- **Ingredient `media`:** Unlike the input file, ingredient `media` is passed as base64 inside the JSON `assertions` (not as a path). The bytes stay on your machine; only hashes/lengths are sent during claim setup, while the finished manifest can include ingredient thumbnails and C2PA history.

### AI labeling with Docker

Register your AI system once against `https://api.trufo.ai/ai-system/add` (or `eu.api.trufo.ai`) with your `c2pa-sign-prod` or `c2pa-sign-test` key, then reference `"ai_system_id"` in `assertions` when calling `http://127.0.0.1:8080/c2pa/sign`. See [AI Labeling](ai-labeling.md).

---

## Sidecar & Production Deployment

### Calling from another container (Docker Compose / Kubernetes / ECS)

Mount the same media folders at the same paths in both containers, drop `ports:` if nothing on the host calls `trufo-local`, and call `http://trufo-local:8080/c2pa/sign` (or `http://127.0.0.1:8080/c2pa/sign` in a shared Kubernetes pod / ECS task network).

### Folder permissions

On startup, the service verifies read/execute on input folders and write/execute on output folders:
1. Set `user: "<uid>:<gid>"` to match the folder owner (`stat -c '%u:%g' <folder>`).
2. Or `chown` the folders to the container user (default `10001:0`).
3. On SELinux hosts (Fedora/RHEL), append `:z` (or `:ro,z`) to volume mounts.
4. Under rootless Docker, `user: "0:0"` maps to your host user; under Podman, use `podman unshare chown`.

### Concurrency, memory, and cold starts

- **Concurrency:** Each container signs **two files concurrently**; additional requests queue. Scale horizontally (more replicas) for higher concurrency.
- **Memory:** Budget ~256 MiB for typical still images in `2.4`, ~1.25 GiB for two concurrent multi-GB video signs, and benchmark with your largest files for `2.4-full`. Account for kernel page cache under container memory limits.
- **Startup downloads & key expiry:** Each new container downloads engine wheels (~70 MB in `2.4-full`) into `/tmp`, verified by hash; restarts reuse `/tmp`. Configure startup/readiness probes against `/health` with a 60s start period. Rotate `TRUFO_SDK_DOWNLOAD_API_KEY` before its 390-day expiry so newly scheduled containers can start.
- **Read-only root filesystem:** Mount `/tmp` as executable `tmpfs` (native engine wheels execute from `/tmp`):

```yaml
    read_only: true
    tmpfs:
      - /tmp:exec
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
```

- **Faster CPU watermarking:** The `2.4-full` image omits `g++`; add `g++` in a thin child `Dockerfile` if you want JIT compilation for faster repeated CPU watermarking, and consider `{"profile": "fast"}` for CPU video.
- **Network security:** `trufo-local` speaks plain HTTP. Bind only to `127.0.0.1` or a private container network.

---

## Versions, Upgrades, and Errors

- Floating minor tags (`2.4`, `2.4-full`) track the latest `2.4.x` patch; exact tags (`2.4.0`, `2.4.0-full`) never change. There is no `latest` tag.
- Upgrade with `docker compose pull && docker compose up -d`.
- Common HTTP errors: `401 MissingAuthentication`, `400 InvalidMediaInputPath` / `InvalidMediaOutputPath`, `404 MediaInputPathNotFound`, `400 WatermarkNotAvailable` (watermark sent to signing-only image), `400 UnsupportedSDKVersion`, `502 TrufoAPIError`. Startup errors print exact actionable messages in `docker compose logs`.

---

## Licenses and Source

The `trufo-local` wrapper and `trufo` SDK are Apache-2.0; the downloaded engine packages are under the [Trufo Library License](https://trufo.ai/legal/trufo_library_license/v_1_1_0.html). Third-party notices live at `/usr/share/doc/trufo-local/NOTICE` ([signing-only](../../trufo-local/NOTICE), [full](../../trufo-local/NOTICE-full)), and bundled library license texts live at `/usr/share/doc/trufo-local/licenses/`.

Corresponding GPL, LGPL, and MPL sources are published alongside each tag as `<version>-source` / `<version>-full-source` (the full source image also holds the signing-only sources). To extract a source image:

```bash
docker create --platform linux/amd64 --name trufo-local-source ghcr.io/trufo-ai/trufo-local:2.4.0-source none
docker cp trufo-local-source:/sources ./trufo-local-2.4.0-source
docker rm trufo-local-source
```

If you mirror or redistribute an image, include its matching `-source` image.

## Reference

- Local signing behavior & `manifest_settings`: [Signing API](../reference/signing-api.md#local-mode)
- Actions & assertions: [Actions and Assertions](../reference/actions-and-assertions.md)
- Deprecations (including 2.1 image sunset): [Deprecations](../reference/deprecations.md)
