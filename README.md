# Trufo

Open-source library to simplify interactions with the Trufo Provenance Service (TPS).

The Trufo Provenance Platform is under active development, with new provenance features and product workflows being added regularly. If you are building against the platform and have questions about the right integration path, please contact [support@trufo.ai](mailto:support@trufo.ai). We are happy to help.

## Install

```bash
pip install trufo
```

## Sign a File

With a `c2pa-sign-test` API key from [app.trufo.ai](https://app.trufo.ai) (see the [Auth Quickstart](docs/quickstart/0_setup.md)), stored first:

```bash
trufo set-api-key c2pa-sign-test <your-api-key>
```

```python
from pathlib import Path

from trufo import sign_c2pa_test
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_TEST)

signed_bytes = sign_c2pa_test(api_key, Path("input.jpg").read_bytes())
Path("signed.jpg").write_bytes(signed_bytes)
```

That is a complete C2PA signature — Trufo assembles and signs the manifest, so you need no certificate of your own. Swap in `sign_c2pa()` with a `c2pa-sign-prod` key for production-trusted output. See the [Signing Quickstart](docs/quickstart/2_c2pa_signing.md).

## What You Can Do

- **Sign C2PA manifests** — in [Cloud mode](docs/quickstart/2_c2pa_signing.md), or in [Local mode](#c2pa-signing-local) so media never leaves your machine
- **Label AI-generated content** with [C2PA AI disclosures](docs/quickstart/3_ai_labeling.md)
- **Stamp organization identity and metadata** via [CAWG](docs/quickstart/4_cawg_publish.md)
- **Embed and recover watermarks** that [survive manifest stripping](docs/quickstart/6_watermarking.md), with Trufo signing or your own
- **Manage your content records** — look up, list, and switch off the marks you keep resolvable ([content records](docs/api/api_c2pa.md#content-records))
- **Declare source assets, or redact** from provenance history ([ingredients](docs/quickstart/5_ingredients.md))
- **Enrol your own C2PA certificates** for a generator product ([CSRs](docs/quickstart/1_certs.md))

## C2PA Signing, Local

In Local mode, your media stays on your machine: Trufo's engine builds the manifest locally, and only the claim goes to Trufo, which signs it. Two ways to run it:

- **Python SDK:** `sign_c2pa_distributed()` with the `trufo[local-sign-only]` or `trufo[local-full]` extra; `local-full` adds local watermark embedding. See [Local mode with the Python SDK](docs/local/python.md).
- **Docker image:** `ghcr.io/trufo-ai/trufo-local`, an HTTP service on your machine that signs files by path, for callers in any language. See [Local mode with the Docker image](docs/local/docker.md).

## Workflow Examples (Quickstart)

There are a number of documents to get you started quickly with specific use cases:


| # | Use case                        | Quickstart                                                           |
| - | ------------------------------- | -------------------------------------------------------------------- |
| 0 | Setup — install and credentials | [0_setup.md](docs/quickstart/0_setup.md)                             |
| 1 | Certificates (your own signer)  | [1_certs.md](docs/quickstart/1_certs.md)                             |
| 2 | C2PA signing                    | [2_c2pa_signing.md](docs/quickstart/2_c2pa_signing.md)               |
| 3 | AI labeling                     | [3_ai_labeling.md](docs/quickstart/3_ai_labeling.md)                 |
| 4 | Organization stamping (CAWG)    | [4_cawg_publish.md](docs/quickstart/4_cawg_publish.md)               |
| 5 | Ingredients & redaction         | [5_ingredients.md](docs/quickstart/5_ingredients.md)                 |
| 6 | Watermarking & recovery         | [6_watermarking.md](docs/quickstart/6_watermarking.md)               |

Most integrations need only 0 and 2; quickstart 1 is for teams that operate their own C2PA generator product and sign with their own certificates.


## Reference Documentation

The full reference documentation is spread across the following files:

| Document                                       | Covers                                                                    |
| ---------------------------------------------- | ------------------------------------------------------------------------- |
| [docs/api/api_trufo.md](docs/api/api_trufo.md) | Accounts, organizations, MFA, API keys and scopes, Organization Validation, errors, regions |
| [docs/api/api_c2pa.md](docs/api/api_c2pa.md)   | C2PA signing in Cloud and Local modes, actions and assertions, standalone binding, watermark recovery, content records, assertion records |
| [docs/local/python.md](docs/local/python.md)   | C2PA Signing in Local mode with the Python SDK: extras, private package index, system packages |
| [docs/local/docker.md](docs/local/docker.md)   | C2PA Signing in Local mode with the Docker image: setup, settings, folders, errors, operations |
| [docs/api/media_format_support.md](docs/api/media_format_support.md) | C2PA and watermark format support, codecs, image and track restrictions |
| [docs/api/api_certs.md](docs/api/api_certs.md) | Certificate enrollment (EST), OCSP, timestamping, and the Registration Authority |
| [docs/cli.md](docs/cli.md)                     | CLI credential management                                                 |
