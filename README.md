# Trufo

Open-source Python SDK and developer documentation for the Trufo Provenance Platform — C2PA Content Credentials, watermarking, and C2PA Certificate Authority services (certificates, timestamping, and OCSP).

To get started, create an account at [app.trufo.ai/register](https://app.trufo.ai/register) with your organization (which you can update later). Make sure to enable MFA. There, you can see detailed product pricing and run some test API calls to get a sense of how things work.

You may also want to get started on Organization Validation (OV) early at [app.trufo.ai/settings/org/ov](https://app.trufo.ai/settings/org/ov) since it typically takes 2–5 business days to complete.

Need help choosing an architecture or onboarding? Email [support@trufo.ai](mailto:support@trufo.ai).

---

## Quickstart

Pick the guide that best suits your use case to get started with Trufo and C2PA.

| If you are... | Guide |
| --- | --- |
| Deciding how you want to approach C2PA, picking products & vendors. | [1. Choosing Your C2PA Path](docs/guides/1_choosing-your-c2pa-path.md) |
| Managing accounts and organizations on Trufo; roles, billing, validation. | [2. Account Management](docs/guides/2_account-management.md) |
| Labeling AI-generated or AI-modified media for compliance (EU AI Act). | [3. AI Labeling for Compliance](docs/guides/3_ai-labeling-for-compliance.md) |
| Adding brand identity or preserving provenance in creative workflows. | [4. Brands and Creative Workflows](docs/guides/4_brands-and-creative-workflows.md) |
| Setting up an in-house C2PA Generator Product (certificates, timestamps). | [5. Build Your Own Generator Product](docs/guides/5_build-your-own-generator-product.md) |

---

## Agentic Connection

Point your agent at `https://github.com/trufo-ai/trufo-py` so it can read the SDK and documentation directly. You will also want to install the Python SDK:

```bash
pip install trufo
```

Before an agent can call Trufo on your behalf, you will need to complete a few steps:

1. Create an account and enable MFA.
2. Complete any legal / validation steps.
3. Create scoped API keys as needed in [Organization Settings → API Access](https://app.trufo.ai/settings/org#api-access).

In particular, you will want to create a `trufo-api` key so the agent can establish an MFA-verified session via `trufo login` (giving it access to your org's read/management endpoints, test flows, and certificate/instance management). For the actual C2PA operations, there are two main methods based on where media processing takes place: local and cloud. If you plan for local, you will also want to accept the Trufo Library License at [Organization Settings → Agreements](https://app.trufo.ai/settings/org#agreements) and create an `sdk-download` key. For all API key scopes, regions, and environment variables, see [Setup and Credentials](docs/topics/setup.md).

---

## Documentation Map

### Guides (by use case)

1. [Choosing Your C2PA Path](docs/guides/1_choosing-your-c2pa-path.md)
2. [Account Management](docs/guides/2_account-management.md)
3. [AI Labeling for Compliance](docs/guides/3_ai-labeling-for-compliance.md)
4. [Brands and Creative Workflows](docs/guides/4_brands-and-creative-workflows.md)
5. [Build Your Own Generator Product](docs/guides/5_build-your-own-generator-product.md)

### Topics (by technical capability)

| Topic | Covers |
| --- | --- |
| [Setup and Credentials](docs/topics/setup.md) | Installing `trufo`, hosts, API key scopes, regions |
| [Cloud Signing](docs/topics/signing-cloud.md) | Direct signing, S3 async tasks, signed inputs, warnings |
| [Local Signing (Python SDK)](docs/topics/signing-local-python.md) | Keeping media on your machine with `trufo[local-sign-only]` / `trufo[local-full]` |
| [Local Signing (Docker)](docs/topics/signing-local-docker.md) | Self-hosted HTTP sidecar (`ghcr.io/trufo-ai/trufo-local`) for any language |
| [Storage Options and Privacy](docs/topics/storage-options.md) | `skip_manifest_storage`, thumbnails, EU residency, soft-binding storage, remote manifests |
| [C2PA Manifests, Actions, and Assertions](docs/topics/c2pa-manifests.md) | Manifest settings, created vs. gathered, actions, digital source types, software agents, C2PA/CAWG & custom assertions |
| [AI Labeling](docs/topics/ai-labeling.md) | Registering AI systems, `ai_system` assertions, `signed_input_policy` |
| [CAWG Identity and Metadata](docs/topics/cawg-identity.md) | `cawg_identity`, `cawg_metadata`, `cawg_training` |
| [Ingredients and Redaction](docs/topics/ingredients-and-redaction.md) | Declaring source assets, action histories, redacting assertions |
| [Watermarking and Recovery](docs/topics/watermarking.md) | Integrated watermarking, standalone `/bind/*`, recovery, content records |
| [Certificates](docs/topics/certificates.md) | Dummy certs, test flow, production EST enrollment (`c2pa-l1` / `c2pa-l2`), KMS, rotation, revocation |
| [Timestamping and OCSP](docs/topics/timestamping.md) | RFC 3161 timestamping (`tsa.trufo.ai`), OCSP stapling (`ocsp.trufo.ai`), `c2pa-rs` & OpenSSL wiring |
| [Verification](docs/topics/verification.md) | Verifying signed assets and recovered manifests in local & CI pipelines |

### Reference (normative specifications)

- [Platform API](docs/reference/platform-api.md)
- [Account, Organization, and Billing API](docs/reference/account-and-org-api.md)
- [Signing API](docs/reference/signing-api.md)
- [Actions and Assertions](docs/reference/actions-and-assertions.md)
- [Watermarking and Content API](docs/reference/watermarking-api.md)
- [Certificates, TSA, and OCSP API](docs/reference/certificates-api.md)
- [Media Format Support](docs/reference/media-formats.md)
- [CLI Reference](docs/reference/cli.md)
- [Deprecations](docs/reference/deprecations.md)
