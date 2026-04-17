---
name: lib-dev
description: Development conventions for the trufo-py open-source library. Covers API documentation sourcing, module layout, and doc conventions. Use when writing docs, creating new API modules, or reviewing trufo-py code.
user-invocable: false
---

# trufo-py Library Development

## API Documentation

All API endpoint documentation in `docs/api/` must be sourced from the actual server code — never from the `.md` files themselves.

| Endpoint group | Source of truth |
|----------------|----------------|
| TPS endpoints (`/account/*`, `/gproduct/*`, `/c2pa/*`, `/test/*`) | `trufo-server/server/handlers/` and `trufo-server/core/schema/` |
| TCA endpoints (EST, TSA, OCSP) | `tca-server/servers/` |
| Auth & origin classification | `trufo-server/server/access/origin.py`, `trufo-server/server/access/account_auth.py` |
| Permissions (role → action mapping) | `trufo-server/core/account/org/permissions.py` |

When writing or updating `docs/api/*.md`, always read the handler code, schema definitions, and auth checks from the server repos. Do not copy from other markdown files or infer behavior.

## Module Layout

```
src/trufo/
├── api/
│   ├── tps/          # TPS API helpers (generate, validate, etc.)
│   ├── tca/          # TCA enrollment helpers (certs, EST, etc.)
│   ├── auth.py       # Shared auth utilities
│   ├── endpoints.py  # URL constants
│   └── session.py    # TrufoSession (authenticated requests)
├── crypto/           # Cryptographic utilities
├── intf/             # CLI interface
└── util/             # Shared utilities (credentials, etc.)
```

## Doc Format

See the existing `docs/api/*.md` files for the consistent endpoint documentation format:
- `### \`METHOD /path\`` heading
- `**Auth:**` shorthand line
- `**Headers:**` line (only for non-JSON content types)
- Field table with detailed sub-docs for complex fields
- `**Response ({code}):**` with JSON block
- `**Errors:**` table for non-obvious error codes
