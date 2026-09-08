# Trufo

Open-source library to simplify interactions with the Trufo Provenance Service (TPS).

The Trufo Provenance Platform is under active development, with new provenance features and product workflows being added regularly. If you are building against the platform and have questions about the right integration path, please contact [support@trufo.ai](mailto:support@trufo.ai). We are happy to help.

## Install

```bash
pip install trufo
```

## Sign a File

With a `c2pa-sign-test` API key from [app.trufo.ai](https://app.trufo.ai) (see the [Auth Quickstart](docs/quickstart/0_setup.md)):

```python
from pathlib import Path

from trufo import sign_c2pa_test
from trufo.util.credentials import TrufoApiKey, load_api_key

api_key = load_api_key(TrufoApiKey.C2PA_SIGN_TEST)

signed_bytes = sign_c2pa_test(api_key, Path("input.jpg").read_bytes())
Path("signed.jpg").write_bytes(signed_bytes)
```

That is a complete C2PA signature — Trufo assembles and signs the manifest, so you need no certificate of your own. Swap in `sign_c2pa()` with a `c2pa-sign-prod` key for production-trusted output. See the [Signing Quickstart](docs/quickstart/2_c2pa_signing.md).

## What You Can Do

- **Sign C2PA manifests** — hosted, or [distributed](docs/quickstart/2_c2pa_signing.md) so media never leaves your machine
- **Label AI-generated content** with [C2PA AI disclosures](docs/quickstart/3_ai_labeling.md)
- **Stamp organization identity and metadata** via [CAWG](docs/quickstart/4_cawg_publish.md)
- **Embed and recover watermarks** that [survive manifest stripping](docs/quickstart/6_watermarking.md), with Trufo signing or your own
- **Manage your content records** — look up, list, and switch off the marks you keep resolvable ([content records](docs/api/api_c2pa.md#content-records))
- **Declare source assets, or redact** from provenance history ([ingredients](docs/quickstart/5_ingredients.md))
- **Enrol your own C2PA certificates** for a generator product ([CSRs](docs/quickstart/1_certs.md))

## Optional Local Engine

When using the standard C2PA Signing API, the raw digital media content is sent to the Trufo server for processing. In cases where data privacy is important or where the content file is large, a distributed API is available where media processing — including watermark embedding — is local (and signing is remote, on Trufo servers). Two local-engine tiers are available:

```bash
# distributed C2PA signing only — lightweight, no watermark engine
pip install "trufo[local-sign-only]"

# distributed signing + local watermark embedding — adds trufo-pawprint
# and its ML dependencies (torch; a substantially heavier install)
pip install "trufo[local-full]"
```

Pick `local-sign-only` unless you need watermarking in distributed signing: the watermark engine's dependencies are heavy (PyTorch), and a `local-sign-only` installation signs normally — but a watermark request without the engine always fails with an install hint (see the [Watermarking Quickstart](docs/quickstart/6_watermarking.md)). The legacy `provenance` extra is an alias of `local-sign-only`.

*Note: the local-engine installation currently requires Linux on x86_64 (glibc 2.28+) with CPython 3.12 — the `trufo-provenance` native wheel is published only as `cp312-manylinux_2_28_x86_64`. The base `trufo` package is pure Python and runs on any platform with Python 3.10+.*

### Private Package Index

New releases of `trufo-provenance` and `trufo-pawprint` are distributed through Trufo's private package index at `packages.trufo.ai` rather than public PyPI. Installing the `local-sign-only` (or `local-full`) extra requires an `sdk-download` API key, created at [app.trufo.ai/settings/org](https://app.trufo.ai/settings/org) under *API Keys* (requires an active C2PA Signing plan).

Store the key in `~/.netrc` rather than in the index URL. pip sends it as an HTTP basic-auth credential either way, but a URL-embedded key also lands in your shell history, the process list, and pip and CI logs:

```bash
cat >> ~/.netrc <<'EOF'
machine packages.trufo.ai
  login __token__
  password <your-sdk-download-key>
EOF
chmod 600 ~/.netrc
```

The literal `__token__` goes in the login field and the key in the password field — the same convention PyPI uses. Keep that order: a Trufo API key contains a colon, which is also the separator in an HTTP basic-auth credential, so putting the key in the login field makes it ambiguous to parse.

Then point pip at the index — no credential in the URL — and install normally:

```bash
export PIP_EXTRA_INDEX_URL="https://packages.trufo.ai/simple/"
pip install "trufo[local-sign-only]"   # or "trufo[local-full]"
```

In CI, write the `~/.netrc` from your secret store as a build step instead of committing it or exporting the key into the environment.

The `trufo` package itself resolves from public PyPI; only the engine packages come from the private index. Treat the key like any other credential: keep it out of committed lockfiles and logs, and revoke it from the dashboard if it is exposed.

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
| [docs/api/api_c2pa.md](docs/api/api_c2pa.md)   | C2PA signing (hosted, S3, distributed), actions and assertions, standalone binding, watermark recovery, content records, assertion records |
| [docs/api/api_certs.md](docs/api/api_certs.md) | Certificate enrollment (EST), OCSP, timestamping, and the Registration Authority |
| [docs/cli.md](docs/cli.md)                     | CLI credential management                                                 |
