# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] — 2026-08-22

### Added

- Thumbnail settings:
  - Thumbnail size (medium [default] at ~256px Q80 WebP, high at ~512px Q90 WebP).
  - Thumbnail policy (none, generate if supported [active + ingredients], generate if supported [active only]).
- Declaring `c2pa.created`, along with `digitalSourceType` and `softwareAgent`. Branded business-tier only.
- Explicit `parentOf` ingredients, for declaring a source asset A that was edited into a supplied asset B, along with an `action_history` to describe the intervening edits. Branded business-tier only.
- Explicit placement (`created` vs. `gathered`) for eligible assertions, along with an `allActionsIncluded` declaration). Branded business-tier only.

### Changed

- `ManifestSettings`, accepted through the keyword-only `manifest_settings`, to group the active-manifest title, implicit-parent title, thumbnail settings, and all-actions-included settings. The legacy fields (`manifest_title` and `ingredient_title`) are still accepted.
- Normal implicit-parent signing defaults `allActionsIncluded` to true. Higher-trust declarations, such as `c2pa.created` inception or `parentOf` ingredient or `created` placement, defaults `allActionsIncluded` to false; true must be explicitly passed in.
- Local signing extras now require `trufo-provenance >= 1.2.0, < 1.3.0`.

## [1.1.2] — 2026-08-21

### Added

- Adding feature to send manifest bytes for soft-binding recovery in
  distributed signing mode.

## [1.1.1] — 2026-08-12

### Fixed

- Documentation still taught the removed `c2pa-decode` scope in twelve places
  (setup, watermarking quickstart, CLI and API references), including a
  `TrufoApiKey.C2PA_DECODE` sample that raises `AttributeError` on 1.1.0.
  All now use `content-recover-{test,prod}`.
- Documented the recovery host pairing: `recover_content()` defaults to the
  production host, so test-host recovery passes
  `trufo_api_url=TRUFO_API_URL_TEST` with a `content-recover-test` key. The
  quickstart sample and the docstring now show this.

## [1.1.0] — 2026-08-12

### Added

- Standalone bind helpers `bind_watermark_test` and `bind_commit_test`
  (exported at top level), covering the test-host bind chain:
  watermark → customer-signed manifest → commit.
- `WatermarkMode` and `AiComplianceLabel` enums for the watermark action.
- `recover()` responses carry `ai_compliance_label` and `oid`: a provenance
  mark returns the stored C2PA manifest when one has been captured; a
  compliance mark returns the owning organization's declared AI class.
  `oid` is set only when the mark belongs to your own organization.
- Browser sign-in for `trufo login`, using the OAuth 2.0 authorization code flow
  with PKCE over a loopback redirect (RFC 8252, RFC 7636). The CLI opens your
  browser and receives the result on `127.0.0.1`, so nothing has to be typed or
  copied. `trufo.api.loopback_auth` exposes `generate_pkce`,
  `run_loopback_login`, and `exchange_loopback_code`.
- `trufo login --device` forces the existing device authorization flow
  (RFC 8628), for when the CLI and browser are on different machines — over SSH
  or in a container, where a loopback redirect cannot reach the browser.

### Changed

- **Breaking:** the `c2pa-decode` credential scope is renamed
  `content-recover-{test,prod}`, matching the server's scope split. The old
  `TRUFO_C2PA_DECODE_API_KEY` variable and stored key file are no longer
  read, and the API no longer accepts `c2pa-decode` keys; mint a
  `content-recover-prod` (or `-test`) key and store it with
  `trufo set-api-key`.
- The watermark action's `effort` parameter is renamed `effort_policy`;
  `effort` remains accepted as a deprecated alias. The new `mode` parameter
  selects the mark kind (`provenance`, the default, or `compliance`, which
  requires `ai_compliance_label` and is test-host only).
- Every API call sends SDK version headers (`tf_version`, `tfp_version`)
  for server-side diagnostics.
- The local-signing extras require `trufo-provenance >= 1.1.0, < 1.2.0`.
- `trufo login` now prefers the loopback flow and falls back to the device flow
  automatically when no local listener can be bound. The device flow is
  unchanged and remains fully supported; existing scripts keep working.
- `TrufoSession.init_session` takes a `use_device` keyword argument (default
  `False`). The previous behaviour is `use_device=True`.

### Fixed

- `trufo add-gpi`, `register-gpic`, and `get-c2pa-cert` printed an uncaught
  traceback instead of "run trufo login" when no session was configured, because
  `load_session()` raises rather than returning `None`.

## [1.0.0] — 2026-08-03

### Added

#### Watermarking

- `watermark` action: `["watermark", {...}]` in `actions` embeds an imperceptible Trufo
  Pawprint watermark during C2PA signing, in supported image and audio formats (JPEG, PNG,
  WebP, TIFF; WAV, FLAC, MP3, M4A), hosted and distributed. Watermarking is off unless the
  action is present. The manifest declares it via a `c2pa.watermarked.bound` action and a
  `c2pa.soft-binding` assertion (algorithm `ai.trufo.pawprint.watermark`). See
  `docs/quickstart/6_watermarking.md`.
- `effort` parameter and `WatermarkEffort` enum: `"require"` (any failure fails the sign;
  the default for a bare action), `"require_if_supported"` (unsupported formats sign
  unwatermarked with a warning; runtime failures fail the sign), `"best_effort"` (any
  failure signs unwatermarked with a warning). At most one watermark action per request;
  client-side validation mirrors the server contract.
- Local-engine extras in two tiers: `pip install "trufo[local-sign-only]"` for distributed
  signing without the watermark engine (lightweight — no torch), and
  `pip install "trufo[local-full]"` to add `trufo-pawprint` for local watermark embedding.
  The `provenance` extra remains as the legacy alias of `local-sign-only`. A distributed
  watermark request without `local-full` always fails immediately with an install hint,
  regardless of `effort` — the effort levels govern failures of the installed engine, not
  a missing one.
- `TrufoServerWarning`: non-fatal notices returned by Trufo endpoints are re-emitted
  through Python's `warnings` machinery in both signing flows (previously the hosted
  helpers discarded them). Catch this category to detect a sign that completed without
  the watermark it requested under a lenient `effort`. See the `warnings` field in
  `docs/api/api_c2pa.md`.
- `recover_content()` and the `c2pa-decode` API key scope (`TrufoApiKey.C2PA_DECODE`,
  `TRUFO_C2PA_DECODE_API_KEY`, `trufo set-api-key c2pa-decode`): decode a Trufo watermark
  from media via `POST /content/recover` and return the watermark ID with a detection
  confidence. See `docs/quickstart/6_watermarking.md`.

#### Ingredients

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

- `ingredient` assertion entries: declare `inputTo` inputs (prompt, model, dataset — with
  `c2pa.types.*` data types and IPTC AI-disclosure digitalSourceType) and `componentOf`
  placed components. All user ingredients are gathered; `allActionsIncluded` is `false`
  whenever any are present. Entries may carry base64 `media` (hashed, thumbnailed,
  validated when manifest-bearing); `componentOf` requires it.
  See `docs/quickstart/5_ingredients.md`.

- `ai_disclosure` inline assertion bodies now fail fast with a register-first error
  instead of being silently discarded.

### Changed

- Test signing moved to its own host: the test helpers (`sign_c2pa_test`, the S3 test
  variants, and `sign_c2pa_distributed_test`) now default to `https://test.api.trufo.ai`
  with the same routes as production (`TRUFO_API_URL_TEST`). The legacy `/test/c2pa/sign`
  path on the main hosts remains available during deprecation.
- Every `[name, params]` entry in `actions` and `assertions` must be exactly two elements;
  longer entries are rejected client-side as malformed rather than partially read.
- New dependency wheel for watermarking.
- Installation of dependency wheels (for local provenance & watermarking components) now
  require an API key.

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

[Unreleased]: https://github.com/trufo-ai/trufo-py/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/trufo-ai/trufo-py/compare/v1.1.2...v1.2.0
[1.1.2]: https://github.com/trufo-ai/trufo-py/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/trufo-ai/trufo-py/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/trufo-ai/trufo-py/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/trufo-ai/trufo-py/compare/v0.5.2...v1.0.0
[0.5.2]: https://github.com/trufo-ai/trufo-py/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/trufo-ai/trufo-py/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/trufo-ai/trufo-py/compare/v0.4.2...v0.5.0
[0.4.2]: https://github.com/trufo-ai/trufo-py/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/trufo-ai/trufo-py/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/trufo-ai/trufo-py/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/trufo-ai/trufo-py/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/trufo-ai/trufo-py/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/trufo-ai/trufo-py/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/trufo-ai/trufo-py/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/trufo-ai/trufo-py/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/trufo-ai/trufo-py/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/trufo-ai/trufo-py/releases/tag/v0.1.0
