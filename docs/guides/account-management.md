# Account Management

How Trufo accounts, organizations, roles, Organization Validation, regions, and multi-brand organization groups work — and best practices for setting them up cleanly.

All organization administration happens in the dashboard at [app.trufo.ai](https://app.trufo.ai).

---

## 1. Accounts, Organizations, and Roles

- **Your account** is your personal identity: one email address, your sign-in, and your MFA (passkey and/or TOTP authenticator app).
- **An organization** (`org_…`, shown in [Organization Settings](https://app.trufo.ai/settings/org)) is the customer entity: its members, API keys, Organization Validation (OV), certificates, agreements, and billing.
- Every API key belongs to **the organization**, not the person who created it. Removing a user revokes their personal access immediately while keeping service API keys running uninterrupted.

### Role permissions

| Capability | Owner | Admin | Member |
| --- | --- | --- | --- |
| View members, activity, agreements, OV status, products, certificates, plans, and usage | Yes | Yes | Yes |
| Sign content in the dashboard | Yes | Yes | Yes |
| Rename the organization or change its default processing region | Yes | Yes | No |
| Invite people | As admin or member | As member | No |
| Remove people | Admins and members | Members | No |
| Change roles and transfer ownership | Yes | No | No |
| Create, view, and revoke API keys | Yes | Yes | No |
| Submit OV / Product Validation and accept agreements | Yes | Yes | No |
| Manage products, instances, credentials, domains, and CAWG certs; revoke certs | Yes | Yes | No |
| Manage billing, invoices, and payments | Yes | Yes | No |

**Best practices for team hygiene:**
- **Always have at least two people with admin/owner access** so ownership transfers, OV renewals, and emergency revocations are never blocked by a single person being unavailable.
- **Require MFA from day one** ([User Settings](https://app.trufo.ai/settings/user)). Every administrative action — managing members, API keys, OV, agreements, products, certificates, and billing — requires an MFA-verified session (`403 MFARequired` otherwise).
- **Transfer ownership cleanly:** The owner cannot be removed directly. Change another member's role to **Owner** first (which moves you to **Admin**), then remove the departing account if needed.

---

## 2. Organization Validation (OV) and Agreements

### Organization Validation

OV confirms your organization's legal identity. Your validated legal name and registration country appear in your production certificates and in the automatic `ai.trufo.identity` assertion. Submit it at [app.trufo.ai/settings/org/ov](https://app.trufo.ai/settings/org/ov).

**How to get OV approved quickly (typically 2–5 business days):**
1. **Start OV while you build on `test.api.trufo.ai`** — don't wait until launch week.
2. **Use a publicly verifiable company phone number:** Trufo's CA team confirms the request via a live callback to the authorized representative at a publicly listed business number. Unlisted personal numbers or broken office lines are the #1 cause of delays.
3. **Prepare the authorized representative:** The representative must be an employee or legal agent authorized to sign the Master Services Agreement and Subscriber Agreement. If someone else is the representative, enter their email — Trufo emails them a signing link (valid for 7 days; owners and admins can resend it).

### Organization agreements

Agreements are accepted once for the organization by an owner or admin at [Organization Settings → Agreements](https://app.trufo.ai/settings/org#agreements) (automated agents may not accept legal agreements):

- **Trufo Library License** — required before creating `sdk-download` keys for Local mode.
- **Created Assertion Acknowledgement** — required before registering first-party AI systems (`c2pa_first_party_attestable: true`).

---

## 3. API Key Hygiene

Create scoped API keys in [Organization Settings → API Access](https://app.trufo.ai/settings/org#api-access). Full key values (`{scope}:{key}`) are shown once at creation and expire after up to **390 days**; the dashboard displays each key's expiry and last-used timestamp.

**Best practices:**
- **Separate test and production keys strictly** (`c2pa-sign-test` vs. `c2pa-sign-prod`) and keep them in your secret manager — never commit keys to repositories or container images.
- **Zero-downtime rotation:** Create the replacement key first, roll it out to your services (and `.env` for `trufo-local` Docker containers, which need an active `sdk-download` key whenever new containers start), then revoke the old key. Revocation takes effect within the hour.
- **Use least-privilege scopes:** Give signing workers only `c2pa-sign-prod`, timestamping services only `tsa`, and recovery jobs only `content-recover-prod`.

---

## 4. Regions and Data Residency

Trufo serves two production API endpoints:

- **Global:** `https://api.trufo.ai`
- **Europe:** `https://eu.api.trufo.ai`

**The endpoint your client calls controls where Cloud-mode media is processed and where request logs live.** Calling `https://eu.api.trufo.ai` keeps Cloud-mode media processing inside EU infrastructure.

Two important operational rules:
1. **`default_content_region` is a dashboard default, not an API firewall.** It sets the region used by dashboard workflows, but it does not block a misconfigured backend from calling `api.trufo.ai`. Enforce your target endpoint explicitly in your application configuration (e.g., `trufo_api_url=TRUFO_API_URL_EUROPE` or `TRUFO_API_URL=https://eu.api.trufo.ai` in Docker).
2. **Know what is regional vs. shared:** Accounts, organizations, API keys, AI system registrations, and signing/watermark records work across both endpoints; stored software-agent records and request logs are regional, so register software agents on the same endpoint you sign against.

---

## 5. Multi-Brand Setup: Standalone vs. Organization Groups

Most companies only need a **standalone organization**. Use an **Organization Group** when your company operates multiple legal entities (or distinct business units that each need their own OV, API keys, and signing identity) and wants centralized billing and user administration.

```text
Management organization     Central billing, plans, and cross-org user administration
├── Sub-organization A      Own members, API keys, OV, certificates, and signing
└── Sub-organization B      Own members, API keys, OV, certificates, and signing
```

### When to use a Sub-Org vs. a single Organization

- **Use separate sub-organizations** when each entity has its own legal name (separate OV), separate signing keys/CAWG identity, or distinct team access boundaries.
- **Stay in one standalone organization** if you just have multiple products or brands under one legal entity and one engineering team (you can register multiple AI systems or Branded Generator Products inside one organization).

### Creating and running an Organization Group

1. **Create the group:** As the owner of a standalone organization (with MFA), open [Organization Settings](https://app.trufo.ai/settings/org) and choose **Create Organization Group**. Your existing organization becomes the first sub-organization (keeping its ID, members, API keys, products, and history), and the new management organization takes over billing. **This conversion is permanent.**
2. **Create additional sub-organizations:** From the management organization's **Home** page, an owner or admin chooses **Create Sub-organization**, sets its name and default processing region, and assigns an owner from the group. Each sub-organization completes its own OV and accepts its own agreements.
3. **Manage people across sub-orgs:**
   - **Roles do not inherit automatically:** Being an owner or admin of the management organization lets you view sub-orgs, create new sub-orgs, and add/remove/update members of any sub-org from the management org's **Home** page — but it does not grant signing or product permissions inside a sub-org unless you also hold a role there.
   - **Adding people already in the group:** Select the sub-org on the management org's **Home** page and choose **Add User** (no invitation email needed; they gain access immediately).
   - **Inviting newcomers:** Invite by email from the management org (on the sub-org view) or directly inside a sub-org.
   - **Switching organizations:** Use the organization switcher in the dashboard sidebar (requires MFA). Your next sign-in opens the organization you last used.
4. **Billing and visibility:**
   - The management organization owns billing, payment methods, plans, invoices, and payments for every sub-organization in the group.
   - Sub-organizations can view their billing organization's plans and pricing on product overview pages and see their own product usage, while billing management and invoice details stay on the management organization.
   - The management organization's **Usage** page shows combined usage across the group as well as per-sub-organization breakdowns.
   - If a plan on the management organization ends, it ends for all sub-organizations in the group.

### Key structural limits to plan around

- **One level deep:** Sub-organizations cannot have their own sub-organizations.
- **Permanent membership:** A standalone organization cannot join an existing organization group later, and a sub-organization cannot leave a group or be deleted.
- **One group per account:** An email/account belongs either to one standalone organization or to one organization group.
- **Management organizations do not sign:** API keys, OV, products, certificates, and signing live strictly on sub-organizations (`403 WorkingOrgRequired` if attempted on a management org).

---

## Reference

- Platform auth, regions, API key scopes, and error codes: [Platform API](../reference/platform-api.md)
- Credential setup and hosts: [Setup and Credentials](../topics/setup.md)
