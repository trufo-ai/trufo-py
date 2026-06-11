# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] — 2026-06-11

### Added

- Rename remote signing to distributed signing.
- Fleshing out `sign_c2pa_distributed()` using the `trufo[provenance]` optional dependency
  in a conformant manner; accepts `trufo_api_url` and `trufo_tsa_url` overrides to target
  non-production environments.
- `UserAssertion.CAWG_TRAINING` enum variant.
- Minor updates to documentation and supported MIME types.
- Automatic version registration: the trufo-py version is sent as the `X-TF-Version`
  request header on all distributed signing calls.

### Fixed

- `__version__` now correctly reflects the installed package version (was stuck at `0.3.0` due to a missed update in the v0.3.2 release).

## [0.3.2] — 2026-06-02

### Added

- `UserAssertion.CUSTOM` enum variant for custom assertion signing via the Trufo Provenance API.
- CLI commands for gproduct management: `add-gpi`, `register-gpic`, and C2PA certificate request.
- Documented `"custom"` assertion in `docs/api/api_c2pa.md`, including label constraints, billing requirements, and domain-validation prerequisites.

### Changed

- Updated `trufo-provenance` optional extra pin to `>=0.1.2,<0.2`.

## [0.3.1] — 2026-05-20

### Changed

- Refactored remote C2PA signing to build `CGRequest` objects through the explicit `tfprov` signing API, with explicit TSA keys and CAWG identity validation.
- Updated `trufo-provenance` optional extra pin to `>=0.1.1,<0.2`.

## [0.3.0] — 2026-05-20

### Added

- Public C2PA request enums for signing helpers:
  - `TrufoAction`
  - `UserAssertion`
- Public SDK crypto and certificate helpers used by certificate procurement workflows:
  - `trufo.crypt.algorithms`
  - `trufo.crypt.keygen`
  - `trufo.crypt.tca_certs`
- Remote C2PA signing helpers that build manifests locally while using Trufo-hosted remote signers:
  - `sign_c2pa_remote()`
  - `sign_c2pa_remote_test()`

### Changed

- Reorganized SDK-facing crypto, certificate, and C2PA request helpers to align with the new `tfprov` provenance-engine package split.
- Re-exported CAWG special identity IDs from the shared provenance engine instead of maintaining a separate SDK enum shim.
- Moved `trufo-provenance` from required SDK dependencies to the `provenance` optional extra, pinned to the compatible `0.1.x` provenance-engine release line, because base hosted-API SDK workflows do not require the provenance engine.
- Changed gathered C2PA assertions without explicit CAWG identities from a hard client-side error to a warning while the CAWG trust model remains interim.

### Tests

- Added coverage for public enum member values and string-enum behavior.
- Added client-side validation coverage for C2PA signing action and assertion names.

## [0.2.0] — 2026-05-12

Minor-version bump marks the general availability of the production C2PA signing API.

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

[Unreleased]: https://github.com/trufo-ai/trufo-py/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/trufo-ai/trufo-py/compare/v0.3.3...v0.4.0
[0.3.3]: https://github.com/trufo-ai/trufo-py/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/trufo-ai/trufo-py/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/trufo-ai/trufo-py/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/trufo-ai/trufo-py/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/trufo-ai/trufo-py/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/trufo-ai/trufo-py/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/trufo-ai/trufo-py/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/trufo-ai/trufo-py/releases/tag/v0.1.0
