# C2PA Signing Feature Support Matrix

Three signing modes are available. Support varies by mode.

| mode | who assembles the manifest | who holds the signing key |
|---|---|---|
| fully-server | Trufo server | Trufo KMS |
| remote-signing | client (via `trufo-provenance`) | Trufo KMS (server provides signature only) |
| fully-local | client (via `trufo-provenance`) | client (own cert + key) |

---

## Actions

| action | notes | fully-server | remote-signing | fully-local |
|---|---|---|---|---|
| `publish` | | ✅ | ✅ | ❌ |
| `transcode` | | ✅ | ❌ | ❌ |

## Assertions

| assertion | notes | fully-server | remote-signing | fully-local |
|---|---|---|---|---|
| `ai_disclosure` | default | ✅ | ✅ | ❌ |
| `ai_disclosure` | registered | ✅ | ✅ | ❌ |
| `cawg_identity` | test | ✅ | ✅ | ❌ |
| `cawg_identity` | org-interim | ✅ | ✅ | ❌ |
| `cawg_metadata` | | ✅ | ✅ | ❌ |
| `cawg_training` | | ✅ | ✅ | ❌ |

## C2PA Claim Signing

| | notes | fully-server | remote-signing | fully-local |
|---|---|---|---|---|
| claim signing | test | ✅ | ✅ | ❌ |
| claim signing | prod | ✅ | ✅ | ❌ |

## Infrastructure

| | notes | fully-server | remote-signing | fully-local |
|---|---|---|---|---|
| RFC 3161 timestamping | | ✅ | ✅ | ❌ |
| OCSP stapling | | ✅ | ✅ | ❌ |
| ephemeral S3 I/O | | ✅ | N/A | ❌ |
