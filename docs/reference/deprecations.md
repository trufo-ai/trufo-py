# Deprecations Reference

Deprecated endpoints, request parameters, SDK helpers, and local engine versions. **New integrations should never use any item listed on this page.**

---

## Scheduled Sunsets

### December 31, 2026 (`2026-12-31T23:59:00+00:00`)

| Deprecated | Replacement | Behavior after sunset |
| --- | --- | --- |
| Local mode with `trufo-provenance` `2.0.x` or earlier (from `0.3.0`) | `trufo-provenance` `2.2.0+` (`pip install -U "trufo[local-sign-only]"` / `"trufo[local-full]"`) | `400 UnsupportedSDKVersion` |

### January 31, 2027 (`2027-01-31T23:59:00+00:00`)

| Deprecated | Replacement | Behavior after sunset |
| --- | --- | --- |
| `ai_disclosure` assertion entry in `assertions` | `ai_system` entry ([AI Labeling](../topics/ai-labeling.md)) | `400 UnsupportedAssertion` |
| `POST /c2pa/ai-disclosure/add`, `POST /c2pa/ai-disclosure/list` | `POST /ai-system/add`, `POST /ai-system/list` | `410` (with `Deprecation`, `Sunset`, `Link` headers) |
| Watermark `mode` parameter (`"provenance"`, `"compliance"`) | `wid_allocation_mode` (`"per_embed"` replaces `"provenance"`) | `400 UnsupportedParameter` (all `trufo` 2.1 and earlier `/bind/watermark` calls send `mode` — upgrade to `trufo` 2.2+) |
| Local mode with `trufo-provenance` `2.1.x` or `trufo-local:2.1` Docker images | `trufo-provenance` `2.2.0+` / `ghcr.io/trufo-ai/trufo-local:2.4` (or `2.4-full`) | `400 UnsupportedSDKVersion` |

### Migrating from `ai_disclosure` to `ai_system`

| Old (`ai_disclosure`) | New (`ai_system`) |
| --- | --- |
| `["ai_disclosure", {}]` | Register an AI system via `POST /ai-system/add` and send `["ai_system", {"ai_system_id": ..., "ai_involvement": "ai_generated"}]` |
| `ai_disclosure_id` | Register an AI system with `c2pa_ai_disclosure` |
| `first_party_operated` + `software_agent_id` | `c2pa_first_party_attestable: true` (the AI system's `name` + `version` become the software agent) |
| `set_source_type` | Automatic |
| `aidisc_...` registrations | Not automatically converted; list via `/c2pa/ai-disclosure/list` before sunset to copy bodies if needed |

---

## Deprecated Parameters and Endpoints (No Fixed Sunset Date)

| Deprecated | Replacement | Behavior |
| --- | --- | --- |
| Watermark `effort` parameter | `effort_policy` | Works with warning; providing both returns `400` |
| `POST /c2pa/io/get-s3-url` | `POST /io/get-s3-upload-url` | Alias with identical schema |
| `POST /test/c2pa/sign` on production hosts | `POST https://test.api.trufo.ai/c2pa/sign` | Returns `410` with `Deprecation` and `Link` headers |
| Test keys on production Local mode or `/io/get-s3-upload-url` | `https://test.api.trufo.ai` (`REQUEST` / Local mode) | Returns `410` with `Deprecation` header |

---

## Deprecated Python SDK Helpers

All legacy helpers remain importable (emitting `DeprecationWarning`) until the next major release:

| Deprecated helper | Replacement |
| --- | --- |
| `sign_c2pa()` / `sign_c2pa_test()` | `sign_c2pa_cloud()` / `sign_c2pa_cloud_test()` |
| `sign_c2pa_distributed()` / `sign_c2pa_distributed_test()` | `sign_c2pa_local()` / `sign_c2pa_local_test()` |
| `get_c2pa_s3_upload_url()` | `get_s3_upload_url()` |
| `sign_c2pa_s3()` | `submit_c2pa_sign()` + `wait_for_task()` |
| `sign_c2pa_via_s3()` | `sign_c2pa_cloud(..., execution_mode=ExecutionMode.TASK, mime_type=...)` |
| `sign_c2pa_s3_test()` / `sign_c2pa_via_s3_test()` | `sign_c2pa_cloud_test()` (test host does not support tasks) |
| `pip install "trufo[provenance]"` | `pip install "trufo[local-sign-only]"` |

---

## Deprecation Response Headers

Deprecated endpoints and assertions can carry standard RFC headers:

| Header | Format |
| --- | --- |
| `Deprecation` | `@<unix-timestamp>` (RFC 9745) |
| `Sunset` | HTTP-date (RFC 8594) |
| `Link` | `<URL>; rel="successor-version"` |
