# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/trufo-ai/trufo-py/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/trufo-ai/trufo-py/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/trufo-ai/trufo-py/releases/tag/v0.1.0
