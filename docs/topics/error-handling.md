# Error Handling, Warnings, and Retries

Handle Trufo API errors, non-fatal server warnings, retryability and billing safety, async `TASK` recovery, and session token refresh cleanly in production.

---

## Error Envelope and Request IDs

Trufo HTTP endpoints return errors as JSON with a stable code or message in `detail`:

```json
{ "detail": "InsufficientPermissionForAction", "action": "create_apikey" }
```

Two exceptions:
- **HTTP `422` (schema validation):** `detail` is a list of `{type, loc, msg}` field errors.
- **RFC 8628 / RFC 6749 auth endpoints** (`/account/device/token`, `/account/loopback/token`): lowercase codes (`authorization_pending`, `access_denied`, `expired_token`, `invalid_grant`).

Every response includes an `X-Request-ID` header. Log it on errors and include it when contacting [support@trufo.ai](mailto:support@trufo.ai).

---

## Python SDK Exceptions

| Exception | Raised by | Key attributes / handling |
| --- | --- | --- |
| `requests.HTTPError` | `sign_c2pa_cloud()`, `bind_watermark()`, `bind_reserve()`, `bind_commit()`, `recover_content()`, `get_task()`, `get_content()`, `list_content()`, `set_content_status()`, and REST helpers | Inspect `exc.response.status_code`, `exc.response.headers.get("X-Request-ID")`, and `exc.response.json().get("detail")` |
| `trufo.TaskFailedError` | `wait_for_task()`, `sign_c2pa_cloud(..., execution_mode="task")`, `sign_c2pa_s3()`, `sign_c2pa_via_s3()`, `bind_watermark(..., execution_mode="task")` | Subclass of `RuntimeError`. Retains `exc.task_id` and `exc.task` (`TaskInfo` with `status`, `error_code`, `error_http_status`, `error_message`) |
| `trufo.TaskWaitTimeoutError` | `wait_for_task()` and `TASK`-mode helpers when `wait_seconds` is exceeded or a poll times out | Subclass of `TimeoutError`. Retains `exc.task_id`. **The server task is not cancelled** — poll `get_task(api_key, exc.task_id)` instead of resubmitting |
| `trufo.api.session.AuthError` | `TrufoSession` when login or `401` token refresh fails | Re-authenticate (`trufo login` / `init_session()`) |
| `trufo.api.loopback_auth.BrowserUnavailableError` | `run_loopback_login()` on headless hosts | `TrufoSession.init_session()` catches this automatically and falls back to the device flow |
| `ValueError` | Client-side validation (e.g., invalid `execution_mode`, missing output download URL, or removed test S3 helpers) | Fix the caller argument; do not retry |

```python
import requests
from trufo import (
    TaskFailedError,
    TaskWaitTimeoutError,
    get_task,
    sign_c2pa_cloud,
)

try:
    signed = sign_c2pa_cloud(api_key, media_bytes, actions=actions)
except requests.HTTPError as exc:
    resp = exc.response
    request_id = resp.headers.get("X-Request-ID") if resp is not None else None
    detail = resp.json().get("detail") if resp is not None and resp.content else str(exc)
    print(f"HTTP {resp.status_code if resp else '?'} ({request_id}): {detail}")
    raise
except TaskFailedError as exc:
    print(f"Task {exc.task_id} {exc.task.status.value}: {exc.task.error_code} ({exc.task.error_http_status})")
    raise
except TaskWaitTimeoutError as exc:
    # Server task is still running — poll rather than resubmitting
    latest = get_task(api_key, exc.task_id)
    print(f"Still waiting on {exc.task_id}: {latest.status.value}")
```

---

## Non-Fatal Server Warnings (`TrufoServerWarning`)

Successful responses (`HTTP 200` and `TASK` `result.warnings`) can carry a `warnings` list when Trufo completed the request but skipped or altered something — for example:

- Watermarking skipped on an unsupported asset under `effort_policy: "best_effort"`
- Metadata dropped when converting or transcoding formats
- Unreadable incoming C2PA manifest stripped under `signed_input_policy: "auto"`
- Deprecation notices for aging SDK or engine versions

In Python, both Cloud and Local modes re-emit each entry as `trufo.TrufoServerWarning` (a subclass of `UserWarning`). Capture them explicitly in pipelines where a skipped watermark or stripped manifest should trigger logging or alerting:

```python
import warnings
from trufo import TrufoServerWarning, sign_c2pa_cloud

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always", TrufoServerWarning)
    signed = sign_c2pa_cloud(api_key, media_bytes, actions=actions)

for w in caught:
    print(f"Trufo warning: {w.message}")
```

In raw REST or `trufo-local` Docker integrations, inspect the `warnings` array on the JSON response (and `result.warnings` on `GET /tasks/{task_id}`).

---

## Retryability and Idempotency

**Failed requests do not bill** — with one exception: `POST /content/recover` still bills `input_bytes` on `400 UndecodableMedia`. However, if a client times out *after* the server completes a non-idempotent call, retrying creates a second charge or record.

| Route / Operation | Safe to retry? | Notes |
| --- | --- | --- |
| Read endpoints (`GET /tasks/{task_id}`, `POST /content/{get,list}`, `POST /cert/list`, `POST /gproduct/list`, `POST /account/info`, `POST /org/*` reads, `POST /billing/*` reads) | **Yes** | Pure reads |
| `POST /bind/commit` | **Yes (same manifest)** | Idempotent on identical retries; returns `409 AlreadyCommitted` if retried with a different manifest |
| `POST /content/status` | **Yes** | Setting the same `"active"` / `"inactive"` state is idempotent |
| `POST /cert/revoke` | **Yes (with `revocation_time`)** | Repeating without `revocation_time` returns `400 AlreadyRevoked`; concurrent revokes return `409` |
| `POST /org/ov/upload`, `POST /gproduct/{pv,bpv}/upload`, `POST /io/get-s3-upload-url` | **Yes** | Allocates a new key/URL; discard the unused one |
| EST `GET .../cacerts`, OCSP queries, TSA `GET /policy` | **Yes** | Stateless reads |
| **`POST /c2pa/sign` (Cloud or Local)** | **No** | Not deduplicated — retrying after a lost response bills a second sign. Use generous HTTP timeouts (and `TASK` mode for large files) |
| **`POST /bind/watermark`** | **No** | Allocates a new `wid` and bills per completion |
| **`POST /bind/reserve`** | **No** | Allocates a new reservation against the 10,000 live `per_embed` cap (`429 ReservationLimitExceeded`) |
| **`POST /content/recover`** | **Careful** | Read-only, but each call bills `input_bytes` (including `400 UndecodableMedia`) |
| **`POST /account/refresh`** | **No** | Refresh tokens are **single-use** and rotate on every call; concurrent refreshes with the same token invalidate each other |

### Retry policy by HTTP status

- **`502`, `503`, `504`, or connection error before request receipt:** Retry idempotent operations with exponential backoff and jitter. For non-idempotent calls (`POST /c2pa/sign`, `POST /bind/watermark`), only retry if you are sure the request never reached the server, or accept the risk of a duplicate sign.
- **`429`:** Back off before retrying. If `detail` is `ReservationLimitExceeded`, commit or wait for expired `per_embed` reservations rather than retrying immediately.
- **`401` (`TokenExpired`):** Refresh the Bearer session once via `POST /account/refresh` (`TrufoSession` does this automatically — pass an `on_refresh` callback to persist the rotated refresh token atomically so parallel workers do not reuse an old token). Do not retry `InvalidAPIKey`, `APIKeyRevoked`, or `APIKeyExpired`.
- **`400`, `403`, `404`, `409`, `422`:** Permanent caller, permission, or state errors — do not blind-retry.

---

## Async `TASK` Recovery and Presigned URLs

`wait_for_task()` polls immediately, then every 1s (first 10s), every 10s (up to 10 minutes), and every 60s thereafter. It intentionally does **not** retry task submissions or server failures.

- **Client timeout (`TaskWaitTimeoutError`):** The task continues running on Trufo. Resume polling with `get_task(api_key, exc.task_id, trufo_api_url=...)` on the **same regional host** (`api.trufo.ai` or `eu.api.trufo.ai`) rather than resubmitting `/c2pa/sign`.
- **Expired download link:** Each `GET /tasks/{task_id}` call mints a fresh presigned `download_url` valid for `min(900s, remaining availability)`. If a download link expires before you finish downloading, call `get_task()` again — do not re-sign. Once `result.expires_ts` has passed, `download_url` becomes `null` and the output is no longer stored.
- **Expired upload link:** `POST /io/get-s3-upload-url` returns `expires_at` (Unix epoch seconds). If your S3 `PUT` fails with `403` because the URL expired, call `/io/get-s3-upload-url` for a fresh link and re-upload before calling `/c2pa/sign`.
- **Task failure (`TaskFailedError`):** Inspect `exc.task.status` (`failed` vs `expired`), `exc.task.error_code`, `exc.task.error_http_status`, and `exc.task.error_message`. If `status == "expired"` (queued past `startby_ts`), no signing ran and it is safe to resubmit.

---

## Common Error Triage

| Status | `detail` | Likely cause & fix |
| --- | --- | --- |
| `400` | `MixedCredentials` | Sent both `X-API-Key` and `Authorization: Bearer`; send exactly one |
| `400` | `{"code": "task_required", ...}` | File > 10 MB, or media action on audio/video/PDF/SVG in `REQUEST` mode; use `execution_mode="task"` (or Local mode on test host) |
| `400` | `ManifestStorageRequired` | Combined `per_embed` watermarking with `skip_manifest_storage=True`; drop `skip_manifest_storage` or use `per_ai_system` |
| `400` | `RemoteManifestUnavailable: ...` | Input or ingredient referenced a remote manifest that could not be fetched (under `keep`, or under `auto` with `creation`/`ai_system`); embed the manifest or allow the host in Local mode |
| `400` | `Conflict: ...` | Incompatible combination (e.g., `transcode`/`repackage` with `c2pa.created`, or `all_actions_included: true` with `parentOf` without `action_history`) |
| `400` | `UnsupportedSDKVersion` | Local engine/SDK too old; upgrade `trufo-provenance` or `ghcr.io/trufo-ai/trufo-local:2.4` |
| `401` | `TokenExpired` | Access token (~2h lifetime) expired; refresh via `/account/refresh` or `TrufoSession` |
| `403` | `APIKeyScopeNotAllowed` | Wrong API key scope for the endpoint (see [Platform API](../reference/platform-api.md#api-keys)) |
| `403` | `MissingOrganizationValidation` / `OVNotActive` | Organization Validation not active yet; complete OV in [app.trufo.ai](https://app.trufo.ai) or test on `test.api.trufo.ai` |
| `403` | `NoEligiblePlan` | Missing required subscription plan (e.g., C2PA Signing, Watermark API, `c2pa_custom_domain`, or CAWG Organization Certificate) |
| `403` | `C2PACreatedUserAssertionsNotAuthorized` | Used `creation`, `parentOf`, `action_history`, or `placement="created"` without an approved `branded_gp_id` |
| `403` | `InvalidC2PACustomDomain` | Custom assertion label, redaction reason, or custom action does not match an active Domain Validation record (`/domain/dv/*`) |
| `403` | `WorkingOrgRequired` / `ManagementOrgRequired` / `BillingOrgRequired` | Endpoint called from the wrong org type in an organization group |
| `409` | `AlreadyCommitted` | `/bind/commit` retried with a different manifest than the one already committed |
| `410` | `Test keys are not accepted on this host...` | Sent a `*-test` key to `api.trufo.ai` / `eu.api.trufo.ai`; target `https://test.api.trufo.ai` |
| `429` | `ReservationLimitExceeded` | Hit 10,000 live `per_embed` reservations; commit pending reservations or wait for expiry |

---

## Reference

- Error envelope, HTTP conventions, and API key scopes: [Platform API](../reference/platform-api.md)
- Signing errors and task schemas: [Signing API](../reference/signing-api.md)
- Watermark commit/recovery errors: [Watermarking and Content API](../reference/watermarking-api.md)
- Docker `trufo-local` errors: [Local Signing (Docker)](signing-local-docker.md#versions-upgrades-and-errors)
