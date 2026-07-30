# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Redaction

- `redact` action for all signers, hosted and distributed. A
  `["redact", {"label": ..., "reason": ...}]` entry in `actions` removes one assertion from
  the input's existing C2PA manifest history, wherever it occurs in that history. Repeat the
  entry to redact several, each with its own reason. Distributed signing redacts locally
  without sending media to Trufo. See `docs/quickstart/5_ingredients.md`.
- `RedactableAssertion` and `RedactionReason` enums in `trufo.c2pa`, holding the labels
  supported for redaction and the preset rationale values.
- A redaction the input cannot satisfy — no existing C2PA manifest, or a label absent from its
  manifest history — returns `400`.
- `TrufoAction.REDACT`, so the `redact` action is discoverable alongside the other action
  names accepted by `actions`.

- `ingredient` assertion entries: declare `inputTo` inputs (prompt, model,
  dataset — with `c2pa.types.*` data types and IPTC AI-disclosure digitalSourceType) and one
  `parentOf` upstream asset with its `action_history` of prior descriptive actions. All
  user ingredients are gathered; `allActionsIncluded` is `false` whenever any are present.
  Entries may carry base64 `media` (hashed, thumbnailed, validated when manifest-bearing);
  `componentOf` requires it.
  See `docs/quickstart/5_ingredients.md`.

### Changed

- Every `[name, params]` entry in `actions` and `assertions` must be exactly two elements;
  longer entries are rejected client-side as malformed rather than partially read.

### Removed

- `TrufoAction.REPACKAGE`. The action was a placeholder, no longer needed.


## [0.5.2] — 2026-07-26

### Added

- `TRUFO_API_URL_EUROPE` for explicit Europe-only TPS calls.

## [0.5.1] — 2026-07-22

### Changed

- Documented production distributed signing through `sign_c2pa_distributed()`, including
  its `c2pa-sign-prod`, TSA, and Organization Validation requirements. The quickstart now
  distinguishes it from the test-only `sign_c2pa_distributed_test()` flow.
- Raised the `trufo[provenance]` optional-extra minimum to `trufo-provenance>=0.3.1`
  so distributed signing does not install the raw-input manifest-selection bug fixed in
  provenance 0.3.1.

## [0.5.0] — 2026-07-21

### Added

- Automatic `ai.trufo.identity` assertion: every manifest signed through Trufo endpoints
  (hosted and distributed) now carries a Trufo-authored assertion with the signing
  organization's id and, when Organization Validation (OV) is active, its RA-validated
  legal name. See `docs/api/api_c2pa.md` ("Automatic assertions").

### Changed

- **CAWG identity assertions are now explicitly optional.** Removed the client-side warning
  for assertion lists without a `cawg_identity` entry, and removed the client-side allowlist
  of known `cawg_identity_id` values. `cawg_identity_id` is now an opaque, server-validated
  identifier (unrecognized values are rejected with `400 InvalidCawgIdentityId`), making room
  for future identity types.
- Production signing (`sign_c2pa` and related `/c2pa/sign` helpers, `sign_c2pa_distributed`)
  now requires completed Organization Validation for the caller's organization; the API
  returns `403 MissingOrganizationValidation` otherwise. Test signing helpers are unaffected.
- Distributed signing minimum versions: the Trufo API now requires trufo ≥ 0.5.0 and
  trufo-provenance ≥ 0.3.0 on distributed signing endpoints; older releases receive a `400`
  asking for an upgrade. Hosted signing is not version-gated.
- `trufo-provenance` optional extra pin updated to `>=0.3.0,<0.4`.
- The `"resolved"` assertion entry name is reserved for server-injected content and is
  rejected by client-side validation.

## [0.4.2] — 2026-06-24

### Fixed

- S3 signing branch (`sign_c2pa_via_s3` / `sign_c2pa_s3`): the media upload now passes the
  request body via `data=` instead of `content=`. `requests.put` has no `content` keyword,
  so the S3 upload step raised a `TypeError` and the S3 signing path could never complete.

## [0.4.1] — 2026-06-16

### Added

- Top-level exports in `trufo.__init__`: `sign_c2pa`, `sign_c2pa_test`, `sign_c2pa_via_s3`,
  `sign_c2pa_via_s3_test`, `sign_c2pa_distributed`, `sign_c2pa_distributed_test`,
  `generate_keypair`, `load_api_key`, `save_api_key`, `request_c2pa_test_cert`,
  `request_c2pa_cert`, `create_instance`, `register_credential`.

### Changed

- Renamed `sign_c2pa_test_s3` → `sign_c2pa_s3_test` and `sign_c2pa_test_via_s3` →
  `sign_c2pa_via_s3_test` for naming consistency (`_test` suffix throughout).
- Updated quickstart examples to use top-level `trufo` imports where applicable.

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

[Unreleased]: https://github.com/trufo-ai/trufo-py/compare/v0.5.1...HEAD
[0.5.1]: https://github.com/trufo-ai/trufo-py/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/trufo-ai/trufo-py/compare/v0.4.2...v0.5.0
[0.4.0]: https://github.com/trufo-ai/trufo-py/compare/v0.3.3...v0.4.0
[0.3.3]: https://github.com/trufo-ai/trufo-py/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/trufo-ai/trufo-py/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/trufo-ai/trufo-py/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/trufo-ai/trufo-py/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/trufo-ai/trufo-py/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/trufo-ai/trufo-py/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/trufo-ai/trufo-py/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/trufo-ai/trufo-py/releases/tag/v0.1.0
