# Trufo

Open-source library to simplify interactions with the Trufo Provenance Service (TPS).

The Trufo Provenance Platform is under active development, with new provenance features and product workflows being added regularly. If you are building against the platform and have questions about the right integration path, please contact [support@trufo.ai](mailto:support@trufo.ai). We are happy to help.

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

New releases of `trufo-provenance` and `trufo-pawprint` are distributed through Trufo's private package index at `packages.trufo.ai` rather than public PyPI. Installing the `local` (or `provenance`) extra requires an `sdk-download` API key, created at [app.trufo.ai/settings/org](https://app.trufo.ai/settings/org) under *API Keys* (requires an active C2PA Signing plan). Configure the index alongside PyPI, then install normally:

```bash
export PIP_EXTRA_INDEX_URL="https://<your-sdk-download-key>@packages.trufo.ai/simple/"
pip install "trufo[local-sign-only]"   # or "trufo[local-full]"
```

The `trufo` package itself resolves from public PyPI; only the engine packages come from the private index. Treat the key like any other credential: keep it out of committed lockfiles and logs, and revoke it from the dashboard if it is exposed.

## Workflow Examples (Quickstart)

There are a number of documents to get you started quickly with specific use cases:


| Use case                           | Trufo Product                                                          | Quickstart                                                             |
| ---------------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Auth Setup                         | —                                                                      | [docs/quickstart/0_auth.md](docs/quickstart/0_auth.md)                 |
| C2PA Signing Certificate CSRs      | [C2PA Signing Certificates](https://app.trufo.ai/tca/certs/c2pa)       | [docs/quickstart/1_c2pa_cert.md](docs/quickstart/1_c2pa_cert.md)       |
| AI Labeling                        | [C2PA & CAWG Signing API](https://app.trufo.ai/prov/apis/c2pa-signing) | [docs/quickstart/2_ai_labeling.md](docs/quickstart/2_ai_labeling.md)   |
| Organization Stamping & Assertions | [C2PA & CAWG Signing API](https://app.trufo.ai/prov/apis/c2pa-signing) | [docs/quickstart/3_cawg_publish.md](docs/quickstart/3_cawg_publish.md) |
| Distributed Signing               | [C2PA & CAWG Signing API](https://app.trufo.ai/prov/apis/c2pa-signing) | [docs/quickstart/4_distributed_signing.md](docs/quickstart/4_distributed_signing.md) |
| Ingredients (e.g. Redaction)        | [C2PA & CAWG Signing API](https://app.trufo.ai/prov/apis/c2pa-signing) | [docs/quickstart/5_ingredients.md](docs/quickstart/5_ingredients.md)   |
| Watermarking                       | [C2PA & CAWG Signing API](https://app.trufo.ai/prov/apis/c2pa-signing) | [docs/quickstart/6_watermarking.md](docs/quickstart/6_watermarking.md) |


## Reference Documentation

The full reference documentation is spread across the following files:

| Service | Document                                     | Description                                                  |
| ------- | -------------------------------------------- | ------------------------------------------------------------ |
| Auth    | [docs/api/api_auth.md](docs/api/api_auth.md) | Headers, access tokens, sessions                             |
| TPS     | [docs/api/api_c2pa.md](docs/api/api_c2pa.md) | C2PA signing endpoints                                       |
| TCA     | [docs/api/tca_ca.md](docs/api/tca_ca.md)     | Certificate Authority — enrollment, revocation, timestamping |
| TCA     | [docs/api/tca_ra.md](docs/api/tca_ra.md)     | Registration Authority — instances, credentials, CSR JWTs   |
| CLI     | [docs/cli.md](docs/cli.md)                   | Credential management (dev tool; use the Python API in prod) |
| SDK     | [docs/errors_and_warnings.md](docs/errors_and_warnings.md) | Errors, warnings, and what to handle in production |


