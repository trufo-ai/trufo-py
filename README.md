# Trufo

Open-source Python SDK and developer documentation for the Trufo Provenance Platform — C2PA Content Credentials, watermarking, and C2PA Certificate Authority services (certificates, timestamping, and OCSP).

Need help choosing an architecture or onboarding? Email [support@trufo.ai](mailto:support@trufo.ai).

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

## Quickstart

Pick the guide that best suits your use case to get started with Trufo and C2PA.

| If you are... | Guide |
| --- | --- |
| Deciding how you want to approach C2PA, picking products & vendors. | [Choosing Your C2PA Path](docs/guides/choosing-your-c2pa-path.md) |
| Labeling AI-generated or AI-modified media for compliance (EU AI Act). | [AI Labeling for Compliance](docs/guides/ai-labeling-for-compliance.md) |
| Adding brand identity or preserving provenance in creative workflows. | [Brands and Creative Workflows](docs/guides/brands-and-creative-workflows.md) |
| Setting up an in-house C2PA Generator Product (certificates, timestamps). | [Build Your Own Generator Product](docs/guides/build-your-own-generator-product.md) |
| Managing accounts and organizations on Trufo; roles, billing, validation. | [Account Management](docs/guides/account-management.md) |

---

## Using a Coding Agent With Trufo

Point your coding agent (Claude Code, Codex, Cursor, etc.) at `https://github.com/trufo-ai/trufo-py` — it can read the SDK and `docs/` directly.

Before an agent can call Trufo on your behalf, complete the human-only steps in [app.trufo.ai](https://app.trufo.ai):

1. **Enable MFA and handle legal/validation steps yourself.** Automated agents cannot complete MFA, submit Organization Validation (OV) or Product Validation, or accept legal agreements (*Trufo Library License* for Local mode, *Created Assertion Acknowledgement* for first-party AI systems).
2. **Give the agent a scoped API key via environment variables** (start with `c2pa-sign-test` against `https://test.api.trufo.ai` so the agent can build and test without touching production or billing):
   ```bash
   export TRUFO_C2PA_SIGN_TEST_API_KEY=<your-c2pa-sign-test-key>
   ```
   Only grant production keys (`c2pa-sign-prod`, `sdk-download`, `tsa`, `watermark-prod`) once you are ready to run against production, and keep keys out of source control.
3. **For certificate/instance management only:** If the agent needs to call Registration Authority endpoints (which require an MFA-verified session rather than an API key), create a `trufo-api` key and approve one interactive sign-in (`TrufoSession.init_session()` or `trufo login`) so the session is saved locally.

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
