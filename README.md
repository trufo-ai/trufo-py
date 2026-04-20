# Trufo

Open-source SDK for Trufo's content provenance API services.

The library is currently in an alpha release state. TLS 1.3+ is required for all API requests.

## Documentation

| Document | Description |
|----------|-------------|
| [docs/api/api_access.md](docs/api/api_access.md) | API access setup (API keys, authentication) |
| [docs/api/api_c2pa.md](docs/api/api_c2pa.md) | C2PA generation (signing) — TPS endpoint reference |
| [docs/api/tca_ca.md](docs/api/tca_ca.md) | TCA Certificate Authority — enrollment, revocation, timestamping |
| [docs/api/tca_ra.md](docs/api/tca_ra.md) | TCA Registration Authority — instances, credentials, CSR JWTs |
| [docs/cli.md](docs/cli.md) | CLI for credential management (for development; use the Python API in production) |

## Examples

| Example | Description |
|---------|-------------|
| [examples/tps_test_sign_c2pa.py](examples/tps_test_sign_c2pa.py) | Sign a media file with C2PA via the TPS test endpoint |
| [examples/tca_get_c2pa_cert.py](examples/tca_get_c2pa_cert.py) | Obtain a C2PA test certificate from the Trufo CA |

## Internal Development

Please refer to the `lib-dev` skill in `skills/` for guidance on coding.

### Publishing to PyPI

Publishing uses **Trusted Publishing** (OIDC) via GitHub Actions — no API tokens needed.

1. Update `version` in `pyproject.toml`.
2. Merge to `main`.
3. Create a **GitHub Release** with a tag matching the version (e.g. `v0.1.0`).
4. The `publish.yml` workflow builds and uploads to PyPI automatically.

Configuration:
- **PyPI**: A trusted publisher is registered for `trufo-ai/trufo-py` → `publish.yml` → `pypi` environment.
- **GitHub**: A `pypi` environment is configured in the repo settings (Settings → Environments).
