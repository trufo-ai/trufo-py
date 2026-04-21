# Trufo

Open-source SDK for Trufo's content provenance API services.

The library is currently in an alpha release state. TLS 1.3+ is required for all API requests.

## Workflow Examples (Quickstart)

There are a number of documents to get you started quickly with specific use cases:

| Example | Description |
|---------|-------------|
| [docs/quickstart/0_tps_access.md](docs/quickstart/0_tps_access.md) | Set up access to the TPS API server |
| [docs/quickstart/1_c2pa_cert.md](docs/quickstart/1_c2pa_cert.md) | Obtain a C2PA signing certificate from the Trufo CA |
| [docs/quickstart/2_ai_labeling.md](docs/quickstart/2_ai_labeling.md) | Label media as AI-generated with a C2PA manifest |
| [docs/quickstart/3_cawg_publish.md](docs/quickstart/3_cawg_publish.md) | Add CAWG assertions for organization-based publication |

## API Documentation (Detailed)

The full API documentation is spread across the following files:

| Document | Description |
|----------|-------------|
| [docs/api/api_access.md](docs/api/api_access.md) | API access setup (API keys, authentication) |
| [docs/api/api_c2pa.md](docs/api/api_c2pa.md) | C2PA generation (signing) — TPS endpoint reference |
| [docs/api/tca_ca.md](docs/api/tca_ca.md) | TCA Certificate Authority — enrollment, revocation, timestamping |
| [docs/api/tca_ra.md](docs/api/tca_ra.md) | TCA Registration Authority — instances, credentials, CSR JWTs |
| [docs/cli.md](docs/cli.md) | CLI for credential management (for development; use the Python API in production) |
