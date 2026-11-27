# 1. Choose Your C2PA Route

Use this page to pick the guide, signing architecture, and execution mode that match what you are building. Each guide is an end-to-end setup path; capability details live in [`../topics/`](../topics/) and normative specifications in [`../reference/`](../reference/).

---

## Route by Goal

| Goal | Start with |
| --- | --- |
| Create an account and organization, complete Organization Validation (OV), choose a plan, create API keys, and sign in from the CLI | [2. Trufo Account Setup](2-trufo-account-setup.md) |
| Sign images, audio, video, or documents through Trufo, from the test host to production | [3. Product Signing Setup](3-product-signing-setup.md) |
| Keep original media on your own infrastructure while Trufo signs | [3. Product Signing Setup](3-product-signing-setup.md) (Local mode) |
| Sign under your own product name, or declare asset creation and external edit histories | [3. Product Signing Setup](3-product-signing-setup.md) (Branded Generator Product) |
| Label AI-generated or AI-modified output for regulatory disclosure | [4. AI Labeling and Compliance](4-ai-labeling-compliance.md) |
| Sign with your own C2PA signer (`c2pa-rs`, camera firmware, desktop or mobile app) using Trufo-issued certificates | [5. BYO C2PA Certificates](5-byo-c2pa-certificates.md) |
| Sign `cawg.identity` assertions in your own signer with an organization CAWG certificate | [6. BYO CAWG Certificates](6-byo-cawg-certificates.md) |
| Add RFC 3161 timestamps and stapled OCSP responses to your own signer | [7. BYO Timestamps and OCSP](7-byo-timestamps-and-ocsp.md) |
| Keep provenance recoverable after platforms strip C2PA metadata | [8. Watermarking with Pawprint](8-watermarking-with-pawprint.md) |
| Verify signed files in CI, or validate a manifest recovered from a watermark | [Verification](../topics/verification.md) |

---

## Signing Architectures

Trufo supports three ways to produce a signed C2PA manifest. You can start on standard signing and move to a Branded Generator Product or your own signer later; the manifest content you design carries over.

| | Standard Trufo Signing | Branded Generator Product | Bring Your Own Signer |
| --- | --- | --- | --- |
| Who builds the manifest | Trufo (Cloud) or Trufo's local engine (Local) | Trufo (Cloud) or Trufo's local engine (Local) | You (`c2pa-rs`, `c2patool`, or your own implementation) |
| Who signs | Trufo, with Trufo's C2PA certificate | Trufo, with a certificate issued for your product | You, with your own key and a Trufo-issued certificate |
| Certificate identity | Trufo; your organization appears in the automatic `ai.trufo.identity` assertion | Your product name (`CN`) with `O=Trufo Inc., C=US`; to use your own organization in `O`, contact [support@trufo.ai](mailto:support@trufo.ai) | Your organization and product, from your OV and Product Validation (PV) records |
| C2PA Conformance on your side | Not required | Not required; Trufo reviews the product through Branded Product Validation (BPV) | Required, plus Trufo Product Validation (PV) |
| AI-generated labels (`ai_system` with `ai_generated`) | Yes | Yes | You write the assertions yourself |
| AI-edit labels, asset creation, and external edit histories (`ai_modified`, `creation`, `parentOf` with `action_history`) | No | Yes, limited to the source types the product is approved for | You write the assertions yourself |
| Execution options | Cloud, Local Python, Local Docker | Cloud, Local Python, Local Docker | Your own signer; Trufo provides certificates, timestamps, OCSP, and optional watermarking |
| Setup guide | [3](3-product-signing-setup.md) | [3](3-product-signing-setup.md) | [5](5-byo-c2pa-certificates.md), [6](6-byo-cawg-certificates.md), [7](7-byo-timestamps-and-ocsp.md) |

### Execution modes for Trufo signing

Cloud `REQUEST` mode sends media of up to 10 MB in the request body (`sign_c2pa_cloud()` or `POST /c2pa/sign`). Cloud `TASK` mode uploads media through S3 and is required for files over 10 MB and for media actions on audio, video, PDF, or SVG. Local mode, through the Python SDK or the Docker image, keeps original media on your infrastructure. See [2. Choose an Execution Mode and Region](3-product-signing-setup.md#2-choose-an-execution-mode-and-region) for requirements and region selection.

---

## For AI and Coding Agents

Read the documentation in this order:

1. **Capability guides:** [`../topics/`](../topics/) covers each capability with a runnable companion script: [setup.py](../topics/setup.py), [signing_cloud.py](../topics/signing_cloud.py), [ai_labeling.py](../topics/ai_labeling.py), [cawg_identity.py](../topics/cawg_identity.py), [ingredients.py](../topics/ingredients.py), [watermarking.py](../topics/watermarking.py), and [certificates.py](../topics/certificates.py). The scripts target the test host and read keys with `load_api_key()`.
2. **Normative specifications:** [`../reference/`](../reference/) defines every endpoint, field, error code, and API key scope. Use it as the source of truth for request and response schemas; start with [Platform API](../reference/platform-api.md).
3. **Test host first:** Use `https://test.api.trufo.ai` with `-test` keys (for example `c2pa-sign-test`) during development. It needs no OV or plan, and outputs carry a test certificate. Production signing is metered and retries are not deduplicated (see [Error Handling](../topics/error-handling.md#retryability-and-idempotency)).

### Credentials

Signing and watermarking endpoints take an API key in the `X-API-Key` header; the SDK reads it with `load_api_key()`. Account, organization, API key, billing, validation-draft, and certificate (RA) endpoints take an MFA-verified Bearer session instead: sign in with `trufo login --device` and load the session in Python with `load_session()`. See [5. Create API Keys](2-trufo-account-setup.md#5-create-api-keys) and [6. Sign In From the CLI and Agents](2-trufo-account-setup.md#6-sign-in-from-the-cli-and-agents).

### Actions that require a person in `app.trufo.ai`

- Creating the account and enabling MFA (passkey or authenticator app).
- Switching the active organization.
- Accepting legal agreements ([Agreements](2-trufo-account-setup.md#agreements): *Trufo Library License*, *Created Assertion Acknowledgement*).
- Final submission of Organization Validation (OV), Product Validation (PV), and Branded Product Validation (BPV). Agents can upload documents and save drafts beforehand (see [3. Product Signing Setup](3-product-signing-setup.md#4-branded-product-validation-bpv-and-product-validation-pv)).
- Approving a device sign-in (`trufo login --device`).

When a request fails with `403 MFARequired`, `403 MissingOrganizationValidation`, `403 NoEligiblePlan`, or a `403` that names a missing agreement, report the required human action rather than retrying.
