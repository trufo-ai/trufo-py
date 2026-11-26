# Trufo

Open-source Python SDK and developer documentation for the Trufo Provenance Platform — C2PA Content Credentials, watermarking, and C2PA Certificate Authority services (certificates, timestamping, and OCSP).

Need help choosing an architecture or onboarding? Email [support@trufo.ai](mailto:support@trufo.ai).

---

## Start Here: Which Guide Fits You?

Pick the guide that matches what you are shipping:

| If you are… | Start with |
| --- | --- |
| Deciding between managed signing, branded signing, or running your own C2PA signer (and what to build now vs. later) | [Choosing Your C2PA Path](docs/guides/choosing-your-c2pa-path.md) |
| Labeling AI-generated or AI-edited media for EU AI Act / California SB 942 compliance | [AI Labeling for Compliance](docs/guides/ai-labeling-for-compliance.md) |
| Stamping brand identity or preserving provenance across DAM, CMS, and creative editing tools | [Brands and Creative Workflows](docs/guides/brands-and-creative-workflows.md) |
| Operating your own C2PA Generator Product (enrolling certificates, timestamping, OCSP stapling) | [Build Your Own Generator Product](docs/guides/build-your-own-generator-product.md) |
| Setting up teams, roles, Organization Validation, or multi-brand organization groups | [Account Management](docs/guides/account-management.md) |

---

## Account Setup

Every integration begins at [app.trufo.ai](https://app.trufo.ai):

1. **Create an account and organization** at [app.trufo.ai/register](https://app.trufo.ai/register).
2. **Enable MFA** (passkey or authenticator app) in [User Settings](https://app.trufo.ai/settings/user).
3. **Create a test API key** (e.g., `c2pa-sign-test`) in [Organization Settings → API Access](https://app.trufo.ai/settings/org#api-access) so you can develop immediately against `https://test.api.trufo.ai` — no plan or validation needed for test signing.
4. **Start Organization Validation (OV) early** at [app.trufo.ai/settings/org/ov](https://app.trufo.ai/settings/org/ov) — it gates production signing and certificates and typically takes a few business days.

Install the Python SDK (Python 3.10+):

```bash
pip install trufo
```

For full setup (all API key scopes, environment variables, regions, and Local mode), see [Setup and Credentials](docs/topics/setup.md).

---

## Using Trufo With a Coding Agent

If you are integrating Trufo with a coding agent (Claude Code, Codex, Cursor, etc.), point your agent at this repository and direct it to the layout below:

- **`docs/guides/`** — Use-case guides and best practices (human-first architecture & trade-offs).
- **`docs/topics/`** — Focused, runnable technical walkthroughs (`.md` + `.py` scripts).
- **`docs/reference/`** — Complete, normative wire specifications (endpoints, JSON payloads, enums, error codes, limits, format restrictions).

**Quick map for agents:**
- Auth, hosts, regions, API key scopes, error envelope → [docs/reference/platform-api.md](docs/reference/platform-api.md)
- `/c2pa/sign`, S3 tasks, Local mode, `manifest_settings` JSON → [docs/reference/signing-api.md](docs/reference/signing-api.md)
- Actions (`resize`, `crop`, `trim`, `transcode`, `repackage`, `watermark`, `publish`, `redact`), assertions, `/ai-system/*`, `signed_input_policy` → [docs/reference/actions-and-assertions.md](docs/reference/actions-and-assertions.md)
- Standalone `/bind/*`, `/content/recover`, `/content/*` records, watermark billing → [docs/reference/watermarking-api.md](docs/reference/watermarking-api.md)
- EST enrollment, RA endpoints, TSA (`tsa.trufo.ai`), OCSP (`ocsp.trufo.ai`) → [docs/reference/certificates-api.md](docs/reference/certificates-api.md)
- Supported MIME types, codecs, media action rules, size/pixel limits → [docs/reference/media-formats.md](docs/reference/media-formats.md)
- Deprecated parameters & sunset dates (do not emit in new integrations) → [docs/reference/deprecations.md](docs/reference/deprecations.md)

---

## Documentation Map

### Guides (by use case)

- [Choosing Your C2PA Path](docs/guides/choosing-your-c2pa-path.md)
- [AI Labeling for Compliance](docs/guides/ai-labeling-for-compliance.md)
- [Brands and Creative Workflows](docs/guides/brands-and-creative-workflows.md)
- [Build Your Own Generator Product](docs/guides/build-your-own-generator-product.md)
- [Account Management](docs/guides/account-management.md)

### Topics (by technical capability)

| Topic | Covers |
| --- | --- |
| [Setup and Credentials](docs/topics/setup.md) | Installing `trufo`, hosts, API key scopes, regions |
| [Cloud Signing](docs/topics/signing-cloud.md) | Direct signing, S3 async tasks, manifest settings, warnings |
| [Local Signing (Python SDK)](docs/topics/signing-local-python.md) | Keeping media on your machine with `trufo[local-sign-only]` / `trufo[local-full]` |
| [Local Signing (Docker)](docs/topics/signing-local-docker.md) | Self-hosted HTTP sidecar (`ghcr.io/trufo-ai/trufo-local`) for any language |
| [AI Labeling](docs/topics/ai-labeling.md) | Registering AI systems, `ai_system` assertions, `signed_input_policy` |
| [CAWG Identity and Metadata](docs/topics/cawg-identity.md) | `cawg_identity`, `cawg_metadata`, `cawg_training` |
| [Ingredients and Redaction](docs/topics/ingredients-and-redaction.md) | Declaring source assets, action histories, redacting assertions |
| [Watermarking and Recovery](docs/topics/watermarking.md) | Integrated watermarking, standalone `/bind/*`, recovery, content records |
| [Certificates, TSA, and OCSP](docs/topics/certificates-and-tsa.md) | Dummy certs, test flow, production EST enrollment, `c2pa-rs` TSA & OCSP |
| [Verification](docs/topics/verification.md) | Verifying signed assets and recovered manifests in local & CI pipelines |

### Reference (normative specifications)

- [Platform API](docs/reference/platform-api.md)
- [Signing API](docs/reference/signing-api.md)
- [Actions and Assertions](docs/reference/actions-and-assertions.md)
- [Watermarking and Content API](docs/reference/watermarking-api.md)
- [Certificates, TSA, and OCSP API](docs/reference/certificates-api.md)
- [Media Format Support](docs/reference/media-formats.md)
- [CLI Reference](docs/reference/cli.md)
- [Deprecations](docs/reference/deprecations.md)
