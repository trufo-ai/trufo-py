# 2. Trufo Account Setup

Set up the account, organization, Organization Validation (OV), billing, API keys, and CLI sign-in that the other guides depend on. Test-host development needs steps 1, 2, and 5; production needs steps 1–5 (add step 6 for CLI/agent automation or certificate RA endpoints).

Most steps can be completed in [app.trufo.ai](https://app.trufo.ai) or through the [Account, Organization, and Billing API](../reference/account-and-org-api.md) with a signed-in session (step 6).

---

## 1. Register and Enable MFA

1. Register at [app.trufo.ai/register](https://app.trufo.ai/register).
2. Enable MFA (passkey or authenticator app) at [app.trufo.ai/settings/user](https://app.trufo.ai/settings/user).

MFA is required for API key management, most billing changes, member and organization administration, validation drafts, and certificate endpoints. Without an MFA-verified session these return `403 MFARequired`.

---

## 2. Set Up the Organization

Create an organization in [app.trufo.ai](https://app.trufo.ai) or accept an invitation from an existing owner or admin.

An organization (`org_...`) holds members, API keys, OV, products, certificates, agreements, and billing. API keys belong to the organization, not to the person who created them.

### Roles

| Role | Can do |
| --- | --- |
| `owner` | Everything an admin can do, plus change roles, transfer ownership, create an organization group, and delete the organization |
| `admin` | Manage members (other than admins) and invitations, API keys, billing, validation drafts and uploads, products, instances, and certificates |
| `member` | View members, activity, agreements, OV status, products, certificates, plans, and usage |

An organization has only one `owner`. Promoting another member to `owner` transfers ownership and demotes the prior owner to `admin`. Only the owner can change roles or create an organization group, and an `admin` cannot remove other admins.

Keep at least one admin in addition to the owner so revocations, key rotation, and administration are not blocked by one person's absence.

### Standalone organization or organization group

Most companies need one **standalone organization**. Use an **organization group** when separate legal entities or business units each need their own OV, API keys, and signing identity under central billing.

```text
Management organization     Billing and plans for the whole group
├── Sub-organization A      Members, API keys, OV, products, signing records
└── Sub-organization B      Members, API keys, OV, products, signing records
```

- **Creating a group** (dashboard, or `POST /org/group/create` as the MFA-verified owner of a standalone organization) is a permanent conversion. The existing organization becomes the first sub-organization and keeps its ID, members, keys, and history.
- **The management organization owns billing.** Its plans apply to every sub-organization; if a plan ends there, it ends for the whole group.
- **Working organizations** (standalone organizations and sub-organizations) own API keys, OV, products, and signing records. A management organization cannot hold API keys (`403 WorkingOrgRequired`).

See [Organization Groups and Sub-Organizations](../reference/account-and-org-api.md#organization-groups-and-sub-organizations) for the endpoints.

---

## 3. Start Organization Validation Early

OV confirms your organization's legal identity. It is required for production signing, standalone watermark binding, and production certificates (`403 MissingOrganizationValidation` or `403 OVNotActive` until active). Once active, your validated legal name appears in the automatic `ai.trufo.identity` assertion and in production certificate subjects.

Review typically takes 2–5 business days, so submit OV while you build on the test host:

1. Open [app.trufo.ai/settings/org/ov](https://app.trufo.ai/settings/org/ov) as an owner or admin.
2. Name an authorized representative who can sign the agreements. If that is someone else, Trufo emails them a signing link valid for 7 days (`POST /org/ov/rep-signing/resend` issues a new one).
3. Provide a publicly listed company phone number; Trufo confirms the request by calling it.
4. Submit in the dashboard.

Supporting documents can be uploaded ahead of time with `POST /org/ov/upload` (`multipart/form-data`, max 50 MB), and progress can be read with `POST /org/ov/status` (`status`, `ov_active`, `validated_expires_at`). See [Organization Validation (OV) status and uploads](../reference/account-and-org-api.md#organization-validation-ov-status-and-uploads).

### Agreements

An owner or admin accepts these once per organization at [Organization Settings → Agreements](https://app.trufo.ai/settings/org#agreements):

- **Trufo Library License:** required before creating `sdk-download` keys, which install the Local mode engine (Python extras and Docker image).
- **Created Assertion Acknowledgement:** required before registering a first-party AI system, one your organization operates and whose outputs Trufo records as created by it (`c2pa_first_party_attestable: true`).

---

## 4. Add Billing and Plans

Add a payment method or credits in the dashboard, then subscribe to the plans you need. In an organization group, do this on the management organization.

| Plan (`tp`) | Enables |
| --- | --- |
| `c2pa_signing_api` | Production C2PA signing (Cloud and Local) with `c2pa-sign-prod`; also covers standalone watermark binding and recovery |
| `c2pa_signing_api_branded` | Everything in `c2pa_signing_api` (standard C2PA signing and standalone watermark binding and recovery), plus signing with a Branded Generator Product (see [3. Product Signing Setup](3-product-signing-setup.md#4-branded-product-validation-bpv-and-product-validation-pv)) |
| `watermark_api` | Standalone watermark binding and recovery (`watermark-prod`, `content-recover-prod`) |
| `c2pa_custom_domain` | Domain Validation for custom assertion labels, redaction reasons, and action names |
| `c2pa_cert_lv1_backend`, `c2pa_cert_lv1_distributed`, `c2pa_cert_lv1_edge` | Assurance Level 1 certificates for your own signer, by where signing runs (see [5. BYO C2PA Certificates](5-byo-c2pa-certificates.md)) |
| `c2pa_tsa_api` | RFC 3161 timestamping (`tsa` key) |
| `cawg_cert_organization` | Your organization's CAWG certificate, for `cawg.identity` assertions in Trufo-signed manifests or in your own signer (see [6. BYO CAWG Certificates](6-byo-cawg-certificates.md)) |

An organization can hold at most one of `c2pa_signing_api`, `c2pa_signing_api_branded`, and `watermark_api`; self-serve checkout of a second returns `409`. To switch between them, contact [support@trufo.ai](mailto:support@trufo.ai).

Assurance Level 2 certificates (`c2pa-l2`) are enabled per product through [support@trufo.ai](mailto:support@trufo.ai).

Subscriptions, usage, and credit balance can be read with `POST /billing/subscriptions`, `POST /billing/usage`, and `POST /billing/credits/balance`. See [Billing, Plans, and Usage](../reference/account-and-org-api.md#billing-plans-and-usage).

---

## 5. Create API Keys

An MFA-verified owner or admin creates keys at [Organization Settings → API Access](https://app.trufo.ai/settings/org#api-access) or with `POST /apikey/create` (`scope`, `label`, optional `duration_days` from 1 to 390). The full key, formatted `{scope}:{key}`, is shown once.

| Scope | Used for | Requires |
| --- | --- | --- |
| `trufo-api` | CLI and agent sign-in (`trufo login`) | — |
| `c2pa-sign-test` / `c2pa-sign-prod` | C2PA signing on the test host / production hosts; AI system and software agent registration | Production: a C2PA Signing plan |
| `watermark-test` / `watermark-prod` | Standalone watermark binding | Production: C2PA Signing or Watermark API plan |
| `content-recover-test` / `content-recover-prod` | Watermark recovery | Production: C2PA Signing or Watermark API plan |
| `tsa` | RFC 3161 timestamping | C2PA TSA plan |
| `sdk-download` | Installing the Local mode engine (Python extras and Docker image) | C2PA Signing or Watermark API plan, or test SDK access from [support@trufo.ai](mailto:support@trufo.ai); plus the *Trufo Library License* |

[Platform API — API Keys](../reference/platform-api.md#api-keys) lists the exact endpoints each scope grants.

- Keys expire after at most **390 days**. To rotate, create the replacement, deploy it, then revoke the old key. Revocation propagates within one hour.
- Store keys in environment variables or a secret manager. The SDK reads `TRUFO_<SCOPE>_API_KEY` variables first, then `~/.trufo/credentials/` (see [Setup and Credentials](../topics/setup.md#storing-api-keys)).

---

## 6. Sign In From the CLI and Agents

Install the SDK and store your `trufo-api` key:

```bash
pip install trufo
trufo set-api-key trufo-api <your-trufo-api-key>   # or export TRUFO_API_KEY
```

Sign in:

```bash
trufo login           # opens a browser on this machine; falls back to the device flow
trufo login --device  # device flow for SSH, containers, and headless hosts
```

With `--device`, the CLI prints a URL and a code. Open the URL in any browser signed in to [app.trufo.ai](https://app.trufo.ai) with MFA, check the code, and approve. The session is saved to `~/.trufo/session`.

Use the saved session in Python:

```python
from trufo.util.credentials import load_session

session = load_session()  # refreshes on 401 and saves the new token pair
org = session.make_request("/org/info", {})
print(org["oid"], org["name"])
```

- **Token lifetimes:** access tokens last about 2 hours; refresh tokens last 7 days and rotate on every use (single-use), so a session stays active while used at least weekly. Parallel workers sharing one refresh token should pass an `on_refresh` callback to `TrufoSession` (see [Error Handling](../topics/error-handling.md#retry-policy-by-http-status)).
- **`make_request()`** sends `POST` with a JSON body. For the `GET` draft endpoints and `multipart/form-data` uploads, use any HTTP client with `Authorization: Bearer <session.access_token>`.
- **Organization binding:** each session is bound to one organization. Switching the active organization is done in [app.trufo.ai](https://app.trufo.ai).

### Session hosts

`load_session()` targets `https://api.trufo.ai` by default; set `session.base_api_url` to use another host. `test.api.trufo.ai` does not serve sign-in or token refresh, so a `TrufoSession` that targets it signs in and refreshes on `api.trufo.ai`. See [Setup and Credentials — Hosts](../topics/setup.md#hosts) and [Platform API — Regions](../reference/platform-api.md#regions).

---

## Reference

- Install, credentials, and hosts: [Setup and Credentials](../topics/setup.md)
- Account, organization, API key, and billing endpoints: [Account, Organization, and Billing API](../reference/account-and-org-api.md)
- Auth, scopes, regions, and error envelope: [Platform API](../reference/platform-api.md)
- CLI commands: [CLI Reference](../reference/cli.md)
