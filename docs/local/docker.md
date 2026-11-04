# C2PA Signing in Local Mode with the Docker Image

The Docker image `ghcr.io/trufo-ai/trufo-local` runs C2PA Signing in Local mode as an
HTTP service on your own machine. Your applications name an input file and an output
file by path, and the service signs one into the other:

- the media stays on your machine;
- Trufo's engine builds the manifest locally, inside the container;
- Trufo receives the signing instructions, signs the claim with Trufo's certificate,
  and (unless opt-out), stores the finished manifest for soft-binding recovery and
  general audit records.

Any language that can send an HTTP request can call it. The service comes in two
images: the signing-only image (`2.2`) and the full image (`2.2-full`), which also
embeds Trufo watermarks; see [Choose an Image](#choose-an-image).

## When to Use It

Choose the image when the media must stay on your machines and your callers use
another language or platform, or when you already run your services as containers.
Cloud mode is simpler when uploading the media is fine. Compare the modes in
[Signing Modes](../api/api_c2pa.md#signing-modes).

## Choose an Image

Both images run the same service from the same `compose.yaml`, and serve only
`/health` and `/c2pa/sign`, not the
[Watermarking routes](../quickstart/6_watermarking.md#routes) (`/bind/*`).

- **The signing-only image (`2.2`)**, the shipped default, signs without
  watermarking.
- **The full image (`2.2-full`)** also embeds Trufo watermarks while signing, on CPU
  only, in every format that [Media format support](../api/media_format_support.md)
  lists for watermark embedding (HEIC, HEIF and AVIF included).

| | Signing-only | Full |
| --- | ------------ | ---- |
| Pulled (compressed), linux/amd64 | about 340 MB | about 620 MB |
| Pulled (compressed), linux/arm64 | about 320 MB | about 550 MB |
| Unpacked, linux/amd64 | about 0.9 GB | about 1.9 GB |
| Unpacked, linux/arm64 | about 0.8 GB | about 1.7 GB |
| Idle memory, linux/amd64 | about 100 MiB | about 300 MiB |

To switch images, change the tag in `image:` and run `docker compose up -d`.

<!-- TODO(sunset-2027-01-31): the next line goes; successor none -->

If you run a 2.1 image, see [Versions and Upgrades](#versions-and-upgrades).

## Before You Start

- **Docker** with Compose. Every image tag (not the `-source` tags) serves
  linux/amd64 and linux/arm64.
- **Two API keys** for your organization, set up as in [0_setup.md](../quickstart/0_setup.md):
  an `sdk-download` key, which the service uses to download Trufo's engine (and, in
  the full image, the watermark engine), and a `c2pa-sign-prod` key, sent with each
  signing request (`c2pa-sign-test` for the test host).
- **For production**, completed Organization Validation and the C2PA Signing plan:
  signing on `api.trufo.ai` or `eu.api.trufo.ai` needs both. Until then, set
  `TRUFO_API_URL` to the test host and send a `c2pa-sign-test` key (see
  [Prerequisites](../quickstart/0_setup.md#prerequisites)).
- **Outbound HTTPS** to `packages.trufo.ai` when a new container starts, and to the
  host in `TRUFO_API_URL` for each signing request.

## Quick Start

**1. Get the two files** from the [`trufo-local`](../../trufo-local/) folder:

```bash
mkdir trufo-local && cd trufo-local
curl -fsSLO https://raw.githubusercontent.com/trufo-ai/trufo-py/main/trufo-local/compose.yaml
curl -fsSL -o .env https://raw.githubusercontent.com/trufo-ai/trufo-py/main/trufo-local/.env.example
chmod 600 .env
```

**2. Add your `sdk-download` key** to `.env`, after `TRUFO_SDK_DOWNLOAD_API_KEY=`.

**3. Edit `compose.yaml`.** As shipped:

```yaml
services:
  trufo-local:
    image: ghcr.io/trufo-ai/trufo-local:2.2   # signing only; with watermarking: 2.2-full
    user: "1000:1000"   # owner of the folders below; on the host: id -u and id -g
    env_file: .env
    environment:
      TRUFO_API_URL: https://api.trufo.ai   # EU: https://eu.api.trufo.ai · test: https://test.api.trufo.ai
      TRUFO_LOCAL_INPUT_DIRS: /srv/media/in   # folders it may read; separate several with ":"
      TRUFO_LOCAL_OUTPUT_DIRS: /srv/media/out   # folders it may write to
    volumes:   # each folder above, at the same path; :ro for folders it only reads
      - /srv/media/in:/srv/media/in:ro
      - /srv/media/out:/srv/media/out
    ports:
      - "127.0.0.1:8080:8080"   # reachable from this machine only
    restart: unless-stopped
```

Replace `/srv/media/in` and `/srv/media/out` with your folders, in both places each
appears, and create them before the first start. Set `user:` to their owner. Keep
`TRUFO_API_URL`, or set the EU or test host.

**4. Start the service:**

```bash
docker compose up -d
docker compose ps    # wait for "(healthy)"
curl -s http://127.0.0.1:8080/health
# {"status":"healthy","version":"2.2.0","engine_version":"2.2.0"}
# full image: {"status":"healthy","version":"2.2.0-full","engine_version":"2.2.0","watermark_engine_version":"0.5.4"}
```

A new container first downloads and installs its packages, and is healthy after
about 5 to 20 seconds; the full image after about 10 seconds or more. If it keeps
restarting, `docker compose logs` shows why; see [Start-Up Errors](#start-up-errors).
After any change to `compose.yaml` or `.env`, run `docker compose up -d` again.

## Sign a File

Each caller sends its own `c2pa-sign-*` key with every request:

```bash
export TRUFO_C2PA_SIGN_PROD_API_KEY=<your-c2pa-sign-prod-key>
curl -s http://127.0.0.1:8080/c2pa/sign \
  -H "X-API-Key: $TRUFO_C2PA_SIGN_PROD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"media_input_path": "/srv/media/in/photo.jpg", "media_output_path": "/srv/media/out/photo.jpg", "actions": [["publish", {}]]}'
# {"media_output_path":"/srv/media/out/photo.jpg","warnings":[]}
```

| Field | Required | Description |
| ----- | -------- | ----------- |
| `media_input_path` | Yes | Absolute path of the input file, inside an input folder |
| `media_output_path` | Yes | Absolute path for the signed file, inside an output folder |
| `actions` | Yes | As in [`POST /c2pa/sign`](../api/api_c2pa.md#post-c2pasign) |
| `assertions`, `manifest_title`, `ingredient_title`, `manifest_settings`, `branded_gp_id`, `signed_input_policy`, `signed_ingredient_policy` | No | As in [`POST /c2pa/sign`](../api/api_c2pa.md#post-c2pasign) |

`actions` and `assertions` take the same entries as in Cloud mode, `transcode` included
(see [`actions`](../api/api_c2pa.md#actions)). `signed_input_policy`,
`signed_ingredient_policy` and the `ai_system` entry need a 2.2 image. In the full
image, a [`watermark`](../api/api_c2pa.md#watermark) action embeds the mark locally,
with the same options as in Cloud mode (see
[watermark billing](../api/api_c2pa.md#watermark-billing)); the signing-only image
refuses one, whatever its
`effort_policy`, with 400 `WatermarkNotAvailable`, before anything reaches Trufo.

The response gives the path written and any [`warnings`](../api/api_c2pa.md#response-warnings).

- **The path written** has symlinks resolved and the signed format's extension: asking
  for `photo.png` with a JPEG input writes `photo.jpg`. `photo.jpeg` and `photo.JPG`
  also become `photo.jpg`, and `.tif` becomes `.tiff`; after a `transcode`, the
  extension follows the new format.
- **The output path** is overwritten: the signed file replaces any file there, so use
  output paths whose existing files you don't need.
- **Titles.** To record the input file's name, set it in `manifest_settings`:
  `"manifest_settings": {"ingredient_title": "photo.jpg"}`. The defaults and the
  generator information Local mode records are in
  [Local mode](../api/api_c2pa.md#local-mode).
- **Ingredient `media`** in `assertions`: the ingredient's bytes stay on your
  machine; the signing request carries only its SHA-256 and byte length. The
  finished manifest, which Trufo receives, can include the ingredient's thumbnail
  and C2PA history.

To check the result, open the signed file at [verify.trufo.ai](https://verify.trufo.ai).
Files signed through the production hosts validate against the C2PA Trust List; files
signed on the test host carry Trufo's test certificate, which validators report as
untrusted.

## AI Labeling

The service only signs, so register an AI system once with Trufo's API, on
`api.trufo.ai` or `eu.api.trufo.ai`, with your `c2pa-sign-prod` or `c2pa-sign-test`
key. It then works
with every `TRUFO_API_URL` in [Settings](#settings), the test host included.

```bash
curl -X POST https://api.trufo.ai/ai-system/add \
  -H "X-API-Key: <YOUR_C2PA_SIGNING_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "<AI_SYSTEM_NAME>",
    "version": "<AI_SYSTEM_VERSION>",
    "ai_involvement_modes": ["ai_generated"],
    "c2pa_first_party_attestable": true,
    "c2pa_ai_disclosure": {"modelType": "c2pa.types.model"}
  }'
# {"ai_system_id": "aisys_…"}
```

Set `c2pa_first_party_attestable` only if you operate the model
([step 1](../quickstart/3_ai_labeling.md#step-1--confirm-you-are-the-first-party-operator)
of the AI Labeling Quickstart); the fields are in
[`POST /ai-system/add`](../api/api_c2pa.md#post-ai-systemadd). Then name the AI system
in `assertions`:

```json
{
  "media_input_path": "/srv/media/in/generated.png",
  "media_output_path": "/srv/media/out/generated.png",
  "actions": [["publish", {}]],
  "assertions": [["ai_system", {"ai_system_id": "aisys_…", "ai_involvement": "ai_generated"}]]
}
```

[Step 3](../quickstart/3_ai_labeling.md#step-3--sign-with-the-ai-system) of the
quickstart gives the labels this produces. The per-AI-system watermark of
[step 4](../quickstart/3_ai_labeling.md#step-4--optionally-watermark-per-ai-system)
needs the full image.

<!-- TODO(sunset-2027-01-31): the next line goes; successor none -->

If you send the deprecated `ai_disclosure` entry, see
[Moving From `ai_disclosure`](../quickstart/3_ai_labeling.md#moving-from-ai_disclosure);
it stops working from 2027-01-31T00:00:00+00:00.

## Folders

The service reads input files and writes signed files only inside the folders you list:

- **Mount** each listed folder into the container at the same path as on the host,
  with `:ro` for folders it only reads. A listed folder may also sit inside a mounted
  one: mount `/srv/media` once to list `/srv/media/in` and `/srv/media/out`.
- **Name files by path.** The service checks paths as it sees them inside the
  container, so same-path mounts let your applications send the paths they already
  use. Each path must be absolute and, once symlinks and `..` are resolved, inside a
  listed folder.

Send one signing request per output path at a time. Signed files belong to the
service's user.

### Calling From Another Container

A caller in another container cannot reach the port published on `127.0.0.1`. Add
the caller to the same `compose.yaml`, so both share its network, and call
`http://trufo-local:8080`. Mount the same folders at the same paths in the caller,
and drop `ports:` if nothing on the host calls the service:

```yaml
services:
  trufo-local:
    # as shipped, without ports: if only containers call it
  my-app:
    image: <your-image>   # calls http://trufo-local:8080/c2pa/sign
    volumes:   # the same folders, at the same paths
      - /srv/media/in:/srv/media/in
      - /srv/media/out:/srv/media/out:ro
```

## Folder Permissions

At start, the service checks that its user has read and execute permission on each
input folder, and write and execute permission on each output folder. Otherwise it
stops with one of these lines:

```text
Cannot read input folder <folder> as user <uid>:<gid>. See https://github.com/trufo-ai/trufo-py/blob/main/docs/local/docker.md#folder-permissions
Cannot write to output folder <folder> as user <uid>:<gid>. See https://github.com/trufo-ai/trufo-py/blob/main/docs/local/docker.md#folder-permissions
```

A host folder that Docker creates because it was missing is owned by root: create
the folders yourself before the first start, or give them to the service's user
(fix 2).

Fix it in this order:

1. **Run as the folders' owner.** Set `user:` to the owner's IDs: `stat -c '%u:%g' <folder>`
   on the host, or `id -u` and `id -g` for folders you own.
2. **Give the folders to the service's user**, for example
   `sudo chown 1000:1000 /srv/media/out`. Without `user:`, the service runs as
   `10001:0`, so folders owned by group 0 grant it their group permissions.
3. **On SELinux hosts** (such as Fedora and RHEL), add `z` to the volume's options:
   `/srv/media/out:/srv/media/out:z`, or `:ro,z` for an input folder.
4. **Under rootless Docker or Podman**, container user IDs map to other IDs on the
   host. In rootless Docker, `user: "0:0"` is your own host user; in Podman,
   `podman unshare chown 1000:1000 <folder>` gives a folder to container user 1000.

## Settings

| Setting | In | Value |
| ------- | -- | ----- |
| `TRUFO_SDK_DOWNLOAD_API_KEY` | `.env` | Required. Your `sdk-download` key |
| `TRUFO_API_URL` | `environment:` | `https://api.trufo.ai` (default), `https://eu.api.trufo.ai` or `https://test.api.trufo.ai` |
| `TRUFO_LOCAL_INPUT_DIRS` | `environment:` | Required. Absolute paths of the folders the service may read, separated by `:` |
| `TRUFO_LOCAL_OUTPUT_DIRS` | `environment:` | Required. Absolute paths of the folders it may write to. A folder may be in both lists |
| `user:` | service | The `uid:gid` the service runs as; see [Folder Permissions](#folder-permissions). Without it: `10001:0` |
| `ports:` | service | `127.0.0.1:8080:8080` serves this machine only |
| `restart:` | service | `unless-stopped` restarts the service after a failure or a reboot |

## Running in Production

### Engine Download

Each new container downloads its packages from `packages.trufo.ai` with the
`sdk-download` key: the engine and, in the full image, the watermark engine
(`trufo-pawprint`) with its model weights. It checks them against fixed hashes and
installs them in `/tmp`; the full image's packages are about 70 MB to download and
take about 100 MB there.
A restart or a reboot reuses them; anything that creates a new container, such as
`docker compose up -d` after a change or a pull, downloads them again. Within the hour
after you revoke the `sdk-download` key, new containers can no longer start; running
containers keep working, and so do restarted ones that still have the packages in
`/tmp`.

`sdk-download` keys expire, after up to 390 days. Since new containers need a valid
key, replace the key in `.env` before it expires and run `docker compose up -d`.

### Capacity and Memory

The service signs two files at a time; further requests wait their turn. A request
whose client disconnects while waiting is not signed. A signing request that has
started finishes and is billed, even if its client disconnects; see
[Retries and billing](../api/api_c2pa.md#errors).

Each image's idle memory is in [Choose an Image](#choose-an-image). In the
signing-only image, allow about 256 MiB for typical still images, and about 1.25 GiB
for two concurrent signing requests of multi-gigabyte video; for the full image, set
the limit from a trial with your largest files. Under a container memory limit, the
page cache from reading and writing large files also counts until the kernel
reclaims it.

Both images' health checks call `/health`, with a 60-second start period. `docker stop`
lets signing requests in progress finish within Docker's stop timeout.

### Read-Only Root Filesystem

The service writes only to `/tmp` and the output folders. The packages install into
`/tmp` and run native code from it, so a read-only root needs a writable `/tmp` that
allows execution. Compose's `tmpfs:` and Docker's `--tmpfs` mount without
execution by default; add `exec`. In `compose.yaml`, under the service:

```yaml
    read_only: true
    tmpfs:
      - /tmp:exec
```

A tmpfs `/tmp` starts empty, so each start of the container downloads the packages;
it also counts toward the container's memory. In the full image, the packages take up
to about 170 MiB of it while they install; leave room for signing too.

To also drop every capability and set `no-new-privileges`, add under the service:

```yaml
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
```

## Versions and Upgrades

The shipped `compose.yaml` uses `2.2`, which moves to each 2.2.x release; an exact
version such as `2.2.0` never changes. Fixes, including security fixes, ship in the
newest minor version. The full image's `2.2-full` and `2.2.0-full` behave the same
way; there is no `latest` tag. `/health` reports the image's `version` and the
versions of its engines.

| Image | Engine (trufo-provenance) | Watermark engine (trufo-pawprint) | Source image |
| ----- | ------------------------- | --------------------------------- | ------------ |
| `2.2.0-full` | 2.2.0 | 0.5.4 | `2.2.0-full-source` |
| `2.2.0` | 2.2.0 | — | `2.2.0-source` |
| `2.1.2` | 2.1.2 | — | `2.1.2-source` |
| `2.1.1` | 2.1.1 | — | `2.1.1-source` |

To move to the newest 2.2.x, run `docker compose pull && docker compose up -d`. To
stay on one version, set `image: ghcr.io/trufo-ai/trufo-local:2.2.0` (or
`2.2.0-full`).

<!-- TODO(sunset-2027-01-31): the next paragraph goes; successor none -->

A `2.1` tag never moves to 2.2, and the 2.1 images stop signing from
2027-01-31T00:00:00+00:00 (see [Local mode](../api/api_c2pa.md#local-mode)). To
upgrade from 2.1, set `image:` to `ghcr.io/trufo-ai/trufo-local:2.2` (or `2.2-full`)
and run `docker compose up -d`.

When a signing response's `warnings` says a version is deprecated, move to a newer
image before the date it gives; from that date, signing returns 400
`UnsupportedSDKVersion: …`.

## Security

- **Keys.** Neither image contains a key, the engine or the watermark engine. The
  service keeps the `sdk-download` key in its environment and never writes it to
  disk; `docker inspect` shows it to anyone who can run Docker commands on the host.
  The API key sent with each signing request serves that request only and is never
  stored.
- **Port.** The service speaks plain HTTP. Keep port 8080 on `127.0.0.1`, as the
  shipped `compose.yaml` does, or on a private network that only your callers can
  reach.
- **User and files.** The service runs under any user ID, by default the non-root
  `10001:0`, and writes only to `/tmp` and the output folders. Give write access to
  the listed folders only to the systems that call the service.

Report vulnerabilities to [security@trufo.ai](mailto:security@trufo.ai).

## Errors

### Start-Up Errors

A service that cannot start writes one of these lines to `docker compose logs` (or, if
the install itself fails, pip's error) and exits; `restart: unless-stopped` retries it
with a growing delay. The `TRUFO_LOCAL_INPUT_DIRS` lines below also exist for
`TRUFO_LOCAL_OUTPUT_DIRS`.

| Line | Fix |
| ---- | --- |
| `TRUFO_API_URL must be an https:// address on trufo.ai, not "<value>".` | Set a host from [Settings](#settings) |
| `TRUFO_LOCAL_INPUT_DIRS is not set. List the folders the service may read, separated by ":".` | Set the list |
| `TRUFO_LOCAL_INPUT_DIRS: "<entry>" is not an absolute path.` | Start each path with `/` |
| `TRUFO_LOCAL_INPUT_DIRS: <entry> is not an existing folder.` | Check the path and its `volumes:` line |
| `TRUFO_LOCAL_INPUT_DIRS: <folder> is not mounted. Mount it at the same path inside the container.` | Add a `volumes:` line; see [Folders](#folders) |
| `Cannot read input folder …` or `Cannot write to output folder …` | See [Folder Permissions](#folder-permissions) |
| `Cannot write to /tmp as user <uid>:<gid>. Mount a writable folder at /tmp.` | See [Read-Only Root Filesystem](#read-only-root-filesystem) |
| `TRUFO_SDK_DOWNLOAD_API_KEY is not set. Set it to your sdk-download key.` | Add the key to `.env` |
| `trufo-provenance <version> cannot run from /tmp. Mount /tmp without noexec.` | Add `exec` to the `/tmp` mount; see [Read-Only Root Filesystem](#read-only-root-filesystem) |
| `packages.trufo.ai refused TRUFO_SDK_DOWNLOAD_API_KEY (HTTP <status>). Check that it is an active sdk-download key.` | Put an active `sdk-download` key in `.env` |
| `Could not reach packages.trufo.ai: <reason>.` | Allow outbound HTTPS to `packages.trufo.ai` |

### HTTP Errors

Errors return `{"detail": …}`.

| Status | `detail` | Cause |
| ------ | -------- | ----- |
| 401 | `MissingAuthentication` | No `X-API-Key` header |
| 400 | `InvalidMediaInputPath` | The input path is not absolute, is outside every input folder, or is a file the service's user cannot read |
| 404 | `MediaInputPathNotFound` | No file at the input path |
| 400 | `InvalidMediaOutputPath` | The output path is not absolute, is outside every output folder, or names an existing directory, or its folder is missing or not writable |
| 400 | `The output path is an existing directory.` | After the extension changes, the new name (for example `photo.jpg`) is an existing directory |
| 400 | `The output path is the input file.` | The output, with the signed format's extension, would replace the input |
| 400 | `WatermarkNotAvailable` | A `watermark` action sent to the signing-only image; use the full image (`2.2-full`) |
| 400 | `Watermarking failed: …` | Full image: the mark could not be embedded, under `effort_policy` `require` or `require_if_supported`; under `best_effort`, the file is signed without it and this text is in `warnings` |
| 400 | *(message)* | The engine rejected the request, for example a malformed action |
| 400 | `UnsupportedSDKVersion: …` | The image's SDK or engine version is not supported, or the engine is too old for a feature the request uses; the detail names the package and the reason. See [Versions and Upgrades](#versions-and-upgrades) |
| 4xx | *(Trufo's code or message)* | Trufo's API refused the request, for example `InvalidAPIKey`, `APIKeyScopeNotAllowed`, `MissingOrganizationValidation`, `NoEligiblePlan`, or `Test keys are not accepted on this host. …` (a `c2pa-sign-test` key with a production `TRUFO_API_URL`); see [api_trufo.md](../api/api_trufo.md#error-envelope) and [api_c2pa.md](../api/api_c2pa.md#errors) |
| 422 | *(field list)* | The body failed schema validation |
| 501 | `Per-asset watermark ID allocation is not supported.` | Full image: `wid_allocation_mode` `per_asset` |
| 501 | `Compliance watermarking is not supported.` | Full image: the deprecated `mode` `compliance` <!-- TODO(sunset-2027-01-31): this row goes; successor none --> |
| 502 | `TrufoAPIError` | Trufo's API returned a server error or an unreadable error, or could not be reached |
| 500 | `Internal server error.` | Anything unexpected |

## Licenses and Source

The service and the `trufo` package are under the Apache License 2.0. The engine
(`trufo-provenance`) and the full image's watermark engine (`trufo-pawprint`) are
under the
[Trufo Library License](https://trufo.ai/legal/trufo_library_license/v_1_0_0.html).

Each image's NOTICE, at `/usr/share/doc/trufo-local/NOTICE` inside the image
([signing-only](../../trufo-local/NOTICE), [full](../../trufo-local/NOTICE-full)),
describes its third-party software, including software under the GNU GPL and LGPL,
and points to each Debian package's license in `/usr/share/doc/`. In
`/usr/share/doc/trufo-local/licenses/`, the full image adds the license texts its
Python packages omit for the libraries they bundle.

Each image version has a source image in the same repository, tagged with its
version plus `-source` (`2.2.0-source`, `2.2.0-full-source`), holding the complete
corresponding source code of its GPL-, LGPL- and MPL-licensed software. The full
image's source image also holds the signing-only image's sources. The signing-only
source image is about 1.3 GB, and the full one about 1.4 GB. To extract one:

```bash
docker create --platform linux/amd64 --name trufo-local-source ghcr.io/trufo-ai/trufo-local:2.2.0-source none
docker cp trufo-local-source:/sources ./trufo-local-2.2.0-source
docker rm trufo-local-source
```

If you copy the image to your own registry or pass it to others, copy its `-source`
image with it.

## Reference

- Setup and API keys: [0_setup.md](../quickstart/0_setup.md)
- Local mode with the Python SDK: [python.md](python.md)
- C2PA API reference: [api_c2pa.md](../api/api_c2pa.md)
- Platform API reference: [api_trufo.md](../api/api_trufo.md)
- SDK overview: [README](../../README.md)
