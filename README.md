# Trufo

Open-source library to simplify interactions with the Trufo Provenance Service (TPS).

The library is currently in an alpha release state. TLS 1.3+ is required for all API requests.

## Workflow Examples (Quickstart)

There are a number of documents to get you started quickly with specific use cases:


| Use case                           | Trufo Product                                                          | Quickstart                                                             |
| ---------------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Auth Setup                         | —                                                                      | [docs/quickstart/0_auth.md](docs/quickstart/0_auth.md)                 |
| C2PA Signing Certificate CSRs      | [C2PA Signing Certificates](https://app.trufo.ai/tca/certs/c2pa)       | [docs/quickstart/1_c2pa_cert.md](docs/quickstart/1_c2pa_cert.md)       |
| AI Labeling                        | [C2PA & CAWG Signing API](https://app.trufo.ai/prov/apis/c2pa-signing) | [docs/quickstart/2_ai_labeling.md](docs/quickstart/2_ai_labeling.md)   |
| Organization Stamping & Assertions | [C2PA & CAWG Signing API](https://app.trufo.ai/prov/apis/c2pa-signing) | [docs/quickstart/3_cawg_publish.md](docs/quickstart/3_cawg_publish.md) |


## Reference Documentation

The full reference documentation is spread across the following files:

| Service | Document                                     | Description                                                  |
| ------- | -------------------------------------------- | ------------------------------------------------------------ |
| Auth    | [docs/api/api_auth.md](docs/api/api_auth.md) | Headers, access tokens, sessions                             |
| TPS     | [docs/api/api_c2pa.md](docs/api/api_c2pa.md) | C2PA signing endpoints                                       |
| TCA     | [docs/api/tca_ca.md](docs/api/tca_ca.md)     | Certificate Authority — enrollment, revocation, timestamping |
| TCA     | [docs/api/tca_ra.md](docs/api/tca_ra.md)     | Registration Authority — instances, credentials, CSR JWTs   |
| CLI     | [docs/cli.md](docs/cli.md)                   | Credential management (dev tool; use the Python API in prod) |


