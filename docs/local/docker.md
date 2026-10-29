# C2PA Signing in Local Mode with the Docker Image

The Docker image `ghcr.io/trufo-ai/trufo-local` runs C2PA Signing in Local mode as an
HTTP service on your own machine. Your applications name an input file and an output
file by path, and the service signs one into the other:

- the media stays on your machine;
- Trufo's engine builds the manifest locally, inside the container;
- only the claim goes to Trufo, which signs it with Trufo's certificate.

Any language that can send an HTTP request can call it.

## When to Use It

Choose the image when the media must stay on your machines and your callers use
another language or platform, or when you already run your services as containers.
Cloud mode is simpler when uploading the media is fine. To embed a watermark while
signing, use Cloud mode or [Local mode with the Python SDK](python.md). Compare the
modes in
[Signing Modes](../api/api_c2pa.md#signing-modes).

## Before You Start

- **Docker** with Compose. One image tag serves linux/amd64 and linux/arm64.
- **Two API keys** for your organization, set up as in [0_setup.md](../quickstart/0_setup.md):
  an `sdk-download` key, which the service uses to download Trufo's engine, and a
  `c2pa-sign-prod` key, sent with each signing request (`c2pa-sign-test` for the test
  host).
- **For production**, completed Organization Validation and the C2PA Signing plan:
  signing on `api.trufo.ai` or `eu.api.trufo.ai` needs both. Until then, set
  `TRUFO_API_URL` to the test host and send a `c2pa-sign-test` key (see
  [Prerequisites](../quickstart/0_setup.md#prerequisites)).
- **Outbound HTTPS** to `packages.trufo.ai` when a new container starts, and to the
  host in `TRUFO_API_URL` for each signing request. Apart from pulling the image, these
  are the only hosts the service connects to.

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
    image: ghcr.io/trufo-ai/trufo-local:2.1
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
# {"status":"healthy","version":"2.1.1","engine_version":"2.1.1"}
```

A new container first downloads and installs the engine, and is healthy after about
5 to 20 seconds. If it keeps restarting, `docker compose logs` shows why; see
[Start-Up Errors](#start-up-errors). After any change to `compose.yaml` or `.env`, run
`docker compose up -d` again.

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
| `assertions`, `manifest_title`, `ingredient_title`, `manifest_settings`, `branded_gp_id` | No | As in [`POST /c2pa/sign`](../api/api_c2pa.md#post-c2pasign) |

`actions` and `assertions` take the same entries as in Cloud mode, `transcode` included
(see [`actions`](../api/api_c2pa.md#actions)); a `watermark` action returns 400
`WatermarkNotAvailable`.

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
- **Ingredient `media`** in `assertions` goes to Trufo with the assertions, as in
  Cloud mode.

To check the result, open the signed file at [verify.trufo.ai](https://verify.trufo.ai).
Files signed through the production hosts validate against the C2PA Trust List; files
signed on the test host carry Trufo's test certificate, which validators report as
untrusted.

## AI Labeling

Register AI disclosures and software agents with Trufo's API or dashboard, in the
region of `TRUFO_API_URL`; the service only signs. Then pass the disclosure's ID:

```json
{
  "media_input_path": "/srv/media/in/generated.png",
  "media_output_path": "/srv/media/out/generated.png",
  "actions": [["publish", {}]],
  "assertions": [["ai_disclosure", {"ai_disclosure_id": "aidisc_...", "set_source_type": true}]]
}
```

To record `c2pa.created` with `trainedAlgorithmicMedia`, see
[First-party model operation](../quickstart/3_ai_labeling.md#first-party-model-operation).

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

Each new container downloads the engine from `packages.trufo.ai` with the
`sdk-download` key, checks it against a fixed hash and installs it in `/tmp`. A
restart or a reboot reuses it; anything that creates a new container, such as
`docker compose up -d` after a change or a pull, downloads it again. Within the hour
after you revoke the `sdk-download` key, new containers can no longer start; running
containers keep working, and so do restarted ones that still have the engine in `/tmp`.

`sdk-download` keys expire, after up to 390 days. Since new containers need a valid
key, replace the key in `.env` before it expires and run `docker compose up -d`.

### Capacity and Memory

The service signs two files at a time; further requests wait their turn. A request
whose client disconnects while waiting is not signed. A signing request that has
started finishes and is billed, even if its client disconnects; see
[Retries and billing](../api/api_c2pa.md#errors).

Allow about 256 MiB of memory for typical images, and about 1.25 GiB for two
concurrent signing requests of multi-gigabyte video. Under a container memory limit,
the page cache from reading and writing large files also counts until the kernel
reclaims it.

The image's health check calls `/health`, with a 60-second start period. `docker stop`
lets signing requests in progress finish within Docker's stop timeout.

### Read-Only Root Filesystem

The service writes only to `/tmp` and the output folders. The engine installs into
`/tmp` and runs native code from it, so a read-only root needs a writable `/tmp` that
allows execution. Compose's `tmpfs:` and Docker's `--tmpfs` mount without
execution by default; add `exec`. In `compose.yaml`, under the service:

```yaml
    read_only: true
    tmpfs:
      - /tmp:exec
```

A tmpfs `/tmp` starts empty, so each start of the container downloads the engine.

To also drop every capability and set `no-new-privileges`, add under the service:

```yaml
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
```

## Versions and Upgrades

The shipped `compose.yaml` uses `2.1`, the newest 2.1 image. Trufo rebuilds the image
for security fixes, and `2.1` moves to each rebuild; an exact version such as `2.1.1`
never changes. `/health` reports the image's `version` and its `engine_version`.

| Image | Engine (trufo-provenance) | Source image |
| ----- | ------------------------- | ------------ |
| `2.1.1` | 2.1.1 | `2.1.1-source` |

To upgrade, run `docker compose pull && docker compose up -d`. To stay on one image,
set `image: ghcr.io/trufo-ai/trufo-local:2.1.1`. When a signing response's `warnings`
says a version is deprecated, move to a newer image before the date it gives; after
that date, signing returns 400 `UnsupportedSDKVersion: …`.

## Security

- **Keys.** The image contains no key and no engine. The service keeps the
  `sdk-download` key in its environment and never writes it to disk; `docker inspect`
  shows it to anyone who can run Docker commands on the host. The API key sent with
  each signing request serves that request only and is never stored.
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
| 400 | `WatermarkNotAvailable` | A `watermark` action; this image signs without watermarking |
| 400 | *(message)* | The engine rejected the request, for example a malformed action |
| 400 | `UnsupportedSDKVersion: …` | The SDK or engine version in the image is below the supported minimum; the detail names the package (`trufo-py` or `trufo-provenance`). See [Versions and Upgrades](#versions-and-upgrades) |
| 4xx | *(Trufo's code)* | Trufo's API refused the signing request, for example `InvalidAPIKey`, `APIKeyScopeNotAllowed`, `MissingOrganizationValidation` or `NoEligiblePlan`; see [api_trufo.md](../api/api_trufo.md#error-envelope) and [api_c2pa.md](../api/api_c2pa.md#errors) |
| 422 | *(field list)* | The body failed schema validation |
| 502 | `TrufoAPIError` | Trufo's API returned a server error or an unreadable error, or could not be reached |
| 500 | `Internal server error.` | Anything unexpected |

## Licenses and Source

The service and the `trufo` package are under the Apache License 2.0. The engine,
`trufo-provenance`, is under the
[Trufo Library License](https://trufo.ai/legal/trufo_library_license/v_1_0_0.html).

The image's [NOTICE](../../trufo-local/NOTICE), at `/usr/share/doc/trufo-local/NOTICE`
inside the image, describes its third-party software, including software under the
GNU GPL and LGPL, and points to each Debian package's license in `/usr/share/doc/`.
Each image version has a source image in the same repository, tagged with the version
plus `-source`, holding the complete corresponding source code of its GPL-, LGPL- and
MPL-licensed software (about 1.2 GB). To extract it:

```bash
docker create --platform linux/amd64 --name trufo-local-source ghcr.io/trufo-ai/trufo-local:2.1.1-source none
docker cp trufo-local-source:/sources ./trufo-local-2.1.1-source
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
