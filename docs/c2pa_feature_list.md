# C2PA Signing Feature Support Matrix

Three signing modes are available. Support varies by mode.

| mode | who assembles the manifest | who holds the signing key |
|---|---|---|
| fully-server | Trufo server | Trufo KMS |
| distributed | client (via `trufo-provenance`) | Trufo KMS (server provides signature only) |
| fully-local | client (via `trufo-provenance`) | client (own cert + key) |

---

## Actions

| action | notes | fully-server | distributed | fully-local |
|---|---|---|---|---|
| `publish` | | ✅ | ✅ | ❌ |
| `transcode` | | ✅ | ❌ | ❌ |

## Assertions

| assertion | notes | fully-server | distributed | fully-local |
|---|---|---|---|---|
| `ai_disclosure` | default | ✅ | ✅ | ❌ |
| `ai_disclosure` | registered | ✅ | ✅ | ❌ |
| `cawg_identity` | test | ✅ | ✅ | ❌ |
| `cawg_identity` | org-interim | ✅ | ✅ | ❌ |
| `cawg_metadata` | | ✅ | ✅ | ❌ |
| `cawg_training` | | ✅ | ✅ | ❌ |
| `ai.trufo.identity` | automatic, server-injected | ✅ | ✅ | N/A |

## C2PA Claim Signing

| | notes | fully-server | distributed | fully-local |
|---|---|---|---|---|
| claim signing | test | ✅ | ✅ | ❌ |
| claim signing | prod | ✅ | ✅ | ❌ |

## Infrastructure

| | notes | fully-server | distributed | fully-local |
|---|---|---|---|---|
| RFC 3161 timestamping | | ✅ | ✅ | ❌ |
| OCSP stapling | | ✅ | ✅ | ❌ |
| ephemeral S3 I/O | | ✅ | N/A | ❌ |
