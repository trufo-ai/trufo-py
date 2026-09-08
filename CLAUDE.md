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
  `effort_policy` = `require` (bare default) / `require_if_supported` / `best_effort`
  setting failure tolerance (`WatermarkEffort` enum; `effort` is a deprecated alias)
  and `mode` = `provenance` (default) / `compliance` selecting the mark kind
  (`WatermarkMode`; compliance requires `ai_compliance_label` and is test-host only).
  Supported: JPEG/PNG/WebP/TIFF, WAV/FLAC/MP3/M4A, MP4.
- Routes are named by who embeds and who signs: tpts / lpts (Trufo signs; `sign_c2pa`,
  `sign_c2pa_distributed`) and tpls / lpls (the caller signs with their own certificate;
  `bind_watermark` → `bind_commit`, or `bind_reserve` → `watermark_media` →
  `bind_commit`). Production bind needs a `watermark-prod` key, a C2PA Signing or
  Watermark API plan, and completed Organization Validation; `_test` variants use the
  test host with `watermark-test`. Commit
  verifies the manifest declares the mark (soft-binding assertion +
  `c2pa.watermarked.bound`). Compliance mode is test-host only.
- Every production sign or bind creates a content record. `get_content` looks one up by
  `cid`, `wid`, or `mid`; `list_content` pages them oldest first (status / origin / creation
  window filters, ≤100 per page); `set_content_status(api_key, "inactive", wid=...)`
  withdraws a mark from public soft-binding resolution and stops its soft-binding
  resolution maintenance charge from the next UTC day. Production hosts only; no plan
  required.
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
| Setup — install, credentials | `docs/quickstart/0_setup.md` |
| Certificates (own signer) | `docs/quickstart/1_certs.md` |
| C2PA signing (hosted/S3/distributed) | `docs/quickstart/2_c2pa_signing.md` |
| AI labeling | `docs/quickstart/3_ai_labeling.md` |
| CAWG publish | `docs/quickstart/4_cawg_publish.md` |
| Ingredients & redaction | `docs/quickstart/5_ingredients.md` |
| Watermarking | `docs/quickstart/6_watermarking.md` |
| Platform API reference | `docs/api/api_trufo.md` |
| C2PA API reference | `docs/api/api_c2pa.md` |
| Certificate API reference | `docs/api/api_certs.md` |
| CLI reference | `docs/cli.md` |
| Changelog | `CHANGELOG.md` |
| Contribution policy | `CONTRIBUTING.md` |

## Signing modes

Two modes exist; see `docs/api/api_c2pa.md` for the full comparison.

| Mode | Function | Requires local engine extra | Media sent to server |
|---|---|---|---|
| Hosted (tpts) | `sign_c2pa`, `sign_c2pa_test` | No | Yes |
| Distributed (lpts) | `sign_c2pa_distributed`, `sign_c2pa_distributed_test` | Yes (`trufo[local-sign-only]`; `trufo[local-full]` for watermarking) | No |
