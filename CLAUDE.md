# trufo-py

Python SDK for the Trufo Provenance Service (TPS). Provides helpers for C2PA
signing, CAWG identity and metadata assertions, AI-disclosure labeling, and
certificate enrollment.

## Key facts for AI assistants

- Current version: see `pyproject.toml` (`version = "X.Y.Z"`).
- The local-engine extras require **Linux x86_64 (glibc 2.28+) + CPython 3.12** — the
  trufo-provenance native wheel is published only as `cp312-manylinux_2_28_x86_64`. The
  base `trufo` package is pure Python (3.10+, any platform). Two tiers:
  `local-sign-only` (distributed signing, no watermark engine, no torch) and
  `local-full` (adds `trufo-pawprint` + torch for local watermark embedding);
  `provenance` is the legacy alias of `local-sign-only`.
- Watermarking is **off by default**; a `["watermark", {...}]` action requests it, with
  `effort` = `require` (bare default) / `require_if_supported` / `best_effort` setting
  failure tolerance (`WatermarkEffort` enum). Supported: JPEG/PNG/WebP/TIFF,
  WAV/FLAC/MP3/M4A.
- `sign_c2pa_distributed()` uses the production remote signing endpoint and requires
  completed Organization Validation plus `c2pa-sign-prod` and `tsa` API keys.
- `sign_c2pa_distributed_test()` uses the test remote signing endpoint and requires
  `c2pa-sign-test` and `tsa` API keys.
- Test signing runs on its own host (`test.api.trufo.ai`, `TRUFO_API_URL_TEST`) with the
  same routes as production; the legacy `/test/c2pa/sign` path remains during deprecation.

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
| Watermarking | `docs/quickstart/6_watermarking.md` |
| C2PA API reference | `docs/api/api_c2pa.md` |
| Auth API reference | `docs/api/api_auth.md` |
| TCA CA reference | `docs/api/tca_ca.md` |
| TCA RA reference | `docs/api/tca_ra.md` |
| CLI reference | `docs/cli.md` |
| Feature support matrix | `docs/c2pa_feature_list.md` |
| Changelog | `CHANGELOG.md` |
| Contribution policy | `CONTRIBUTING.md` |

## Signing modes

Two modes exist; see `docs/c2pa_feature_list.md` for the full feature matrix.

| Mode | Function | Requires local engine extra | Media sent to server |
|---|---|---|---|
| Hosted (server) | `sign_c2pa`, `sign_c2pa_test` | No | Yes |
| Distributed | `sign_c2pa_distributed`, `sign_c2pa_distributed_test` | Yes (`trufo[local-sign-only]`; `trufo[local-full]` for watermarking) | No |
