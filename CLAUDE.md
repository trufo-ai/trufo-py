# trufo-py

Python SDK for the Trufo Provenance Service (TPS). Provides helpers for C2PA
signing, CAWG identity and metadata assertions, AI-disclosure labeling, and
certificate enrollment.

## Key facts for AI assistants

- Current version: see `pyproject.toml` (`version = "X.Y.Z"`).
- The `trufo[provenance]` optional dependency is **Linux-only**. macOS/Windows
  wheels are not published.
- `sign_c2pa_distributed()` uses the production remote signing endpoint and requires
  completed Organization Validation plus `c2pa-sign-prod` and `tsa` API keys.
- `sign_c2pa_distributed_test()` uses the test remote signing endpoint and requires
  `c2pa-sign-test` and `tsa` API keys.

## Documentation map

| Topic | File |
|---|---|
| Getting started | `README.md` |
| Auth setup (API keys, device flow) | `docs/quickstart/0_auth.md` |
| C2PA certificate CSRs | `docs/quickstart/1_c2pa_cert.md` |
| AI labeling (AIGC disclosure) | `docs/quickstart/2_ai_labeling.md` |
| CAWG publish (org stamping) | `docs/quickstart/3_cawg_publish.md` |
| Distributed signing | `docs/quickstart/4_distributed_signing.md` |
| Ingredients (incl. redaction) | `docs/quickstart/5_ingredients.md` |
| C2PA API reference | `docs/api/api_c2pa.md` |
| Auth API reference | `docs/api/api_auth.md` |
| TCA CA reference | `docs/api/tca_ca.md` |
| TCA RA reference | `docs/api/tca_ra.md` |
| CLI reference | `docs/cli.md` |
| Feature support matrix | `docs/c2pa_feature_list.md` |
| Changelog | `CHANGELOG.md` |
| Release process | `CONTRIBUTING.md` |

## Signing modes

Three modes exist; see `docs/c2pa_feature_list.md` for the full feature matrix.

| Mode | Function | Requires `trufo[provenance]` | Media sent to server |
|---|---|---|---|
| Hosted (server) | `sign_c2pa`, `sign_c2pa_test` | No | Yes |
| Distributed | `sign_c2pa_distributed`, `sign_c2pa_distributed_test` | Yes | No |
| Fully local | (not exposed via trufo-py) | Yes | No |
