# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.3] — 2026-05-12

### Added

- `sign_c2pa()` — helper for production C2PA signing via `/c2pa/sign`.
- Ephemeral S3 C2PA signing helpers for large-object workflows:
  - `get_c2pa_s3_upload_url()`
  - `sign_c2pa_s3()` / `sign_c2pa_test_s3()`
  - `sign_c2pa_via_s3()` / `sign_c2pa_test_via_s3()`
- `TPS_C2PA_SIGN` and `TPS_C2PA_GET_S3_URL` endpoint constants.

### Changed

- Refactored direct C2PA signing helpers to share request/response handling.

## [0.1.2] — 2026-05-05

### Added

- `DefaultCawgIdentityId` enum — typed constants for standard CAWG identity ID values (`TEST`, `ORG_INTERIM`).

## [0.1.1] — 2026-04-29

### Added

- `sign_c2pa_test()` — helper for signing media via the `/test/c2pa/sign` endpoint, including support for C2PA actions and CAWG identity assertions.
- `request_cawg_interim_cert()` — helper for procuring a CAWG interim certificate through the RA/CA enrollment flow.
- Endpoint path constants for `/c2pa/ai-disclosure/add` and `/c2pa/ai-disclosure/list`.
- `c2pa-sign-prod` and `c2pa-sign-test` API key scopes in credential management.
- Quickstart documentation: authentication, C2PA certificate enrollment, AI labeling, and CAWG publish flows.

### Fixed

- Corrected several inaccuracies in the API reference documentation.

## [0.1.0] — 2026-04-20

### Added

- Initial public release.
- `trufo.crypto`: signing algorithms (ES256/ES384/ES512/EdDSA), key generation, and AWS KMS signing adapter.
- `trufo.api`: device authorization flow (RFC 8628), authenticated session with automatic token refresh, and TCA certificate enrollment (CSR generation, EST enrollment, C2PA L1/L2 and test certificate flows).
- `trufo.intf`: credential storage and loading (env vars + file), CLI entry point.
- PyPI trusted publishing via GitHub Actions (OIDC, no API tokens required).

[Unreleased]: https://github.com/trufo-ai/trufo-py/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/trufo-ai/trufo-py/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/trufo-ai/trufo-py/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/trufo-ai/trufo-py/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/trufo-ai/trufo-py/releases/tag/v0.1.0
