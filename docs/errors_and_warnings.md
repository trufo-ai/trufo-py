# Errors and Warnings

How the SDK reports problems, and which failures are worth handling in
production code.

## The three kinds of signal

| Kind | Raised as | Means |
| ---- | --------- | ----- |
| Request rejected before the call | `ValueError` | The SDK validated your `actions`/`assertions` locally and refused to send them. Always a code fix. |
| Request failed at the API | `requests.HTTPError` | The API returned a non-2xx status. Inspect `exc.response.status_code` and the JSON `detail`. |
| Request succeeded, something was skipped | `TrufoServerWarning` | The sign completed, but the server did not do everything you asked — e.g. a lenient `watermark` effort that could not embed. |

Two SDK-specific types support this: `TrufoServerWarning` (below) and
`AuthError`, raised by `TrufoSession` when a session cannot be established or
refreshed.

---

## `TrufoServerWarning`

A `UserWarning` subclass, exported at the top level:

```python
from trufo import TrufoServerWarning
```

Trufo endpoints may return non-fatal notices alongside a successful response.
The SDK re-emits each one through Python's `warnings` machinery, in both the
hosted and distributed signing flows, so they surface identically wherever
you sign.

The notice you are most likely to see is a skipped watermark. With
`effort` set to `require_if_supported` or `best_effort`, a sign can succeed
without embedding a watermark (see the
[Watermarking Quickstart](quickstart/6_watermarking.md)); the warning is how
you find out. **If you use those effort levels, handle this warning** — it is
the only signal distinguishing watermarked output from unwatermarked output.

### Detecting a skipped watermark

```python
import warnings

from trufo import TrufoServerWarning, sign_c2pa

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always", TrufoServerWarning)
    signed = sign_c2pa(
        api_key,
        media_bytes,
        actions=[["watermark", {"effort": "best_effort"}]],
    )

if caught:
    for w in caught:
        log.warning("Trufo notice: %s", w.message)   # e.g. re-queue, alert
```

### Routing warnings into your logs

```python
import logging

logging.captureWarnings(True)          # sends warnings to the "py.warnings" logger
logging.getLogger("py.warnings").setLevel(logging.WARNING)
```

### Silencing or escalating

```python
import warnings

from trufo import TrufoServerWarning

warnings.simplefilter("ignore", TrufoServerWarning)   # never show them
warnings.simplefilter("error", TrufoServerWarning)    # raise instead (useful in CI)
```

Because the notices have their own category, these filters affect Trufo's
messages only — unrelated warnings from other libraries keep their behavior,
and vice versa. Python's default filters show a given warning once per call
site; `"always"` (as in the example above) reports every occurrence.

---

## Client-side validation (`ValueError`)

The SDK validates request structure before making a network call, so
malformed requests fail fast and locally. Representative messages:

| Message | Cause |
| ------- | ----- |
| `Invalid action entry: …` / `Invalid assertion entry: …` | Unknown name, or an entry that is not exactly `[name, params]`. |
| `At most one watermark action is allowed per request.` | More than one `watermark` entry. |
| `Unsupported watermark parameter(s): …` | A key other than `effort` in the watermark params. |
| `The watermark 'effort' parameter must be one of …` | An `effort` outside the three documented values. |
| `Duplicate redaction target: …` | The same assertion label redacted twice. |
| `The redact action requires a non-empty 'reason'.` | A `redact` entry missing its rationale. |
| `A TSA API key is required for remote C2PA signing.` | Distributed signing without a `tsa` key configured or passed. |

An `ImportError` naming `trufo[local-sign-only]` or `trufo[local-full]` means
a local-engine feature was used without the corresponding extra installed;
see the [README](../README.md#optional-local-engine).

---

## API errors (`requests.HTTPError`)

Signing helpers call `raise_for_status()`, so any non-2xx response raises.
The response body carries a JSON `detail` with a stable error code:

```python
import requests

try:
    signed = sign_c2pa(api_key, media_bytes)
except requests.HTTPError as exc:
    status = exc.response.status_code
    detail = exc.response.json().get("detail")
```

Common codes are documented with each endpoint in
[api_c2pa.md](api/api_c2pa.md) and [api_auth.md](api/api_auth.md); the ones
worth branching on:

| Status | `detail` | Handling |
| ------ | -------- | -------- |
| 400 | validation codes (e.g. `InvalidCawgIdentityId`) | Fix the request; retrying is futile. |
| 401 | `MissingAuthentication`, `InvalidAPIKey` | Credential problem. |
| 403 | `MissingOrganizationValidation` | Production signing before OV is complete — use the test host meanwhile. |
| 403 | `APIKeyScopeNotAllowed` | The key's scope does not cover this endpoint. |

---

## Reference

- Watermark effort levels: [quickstart/6_watermarking.md](quickstart/6_watermarking.md)
- Endpoint error tables: [api/api_c2pa.md](api/api_c2pa.md), [api/api_auth.md](api/api_auth.md)
- Auth setup: [quickstart/0_auth.md](quickstart/0_auth.md)
