# Account, Organization, and Billing API Reference

Normative specification for customer-accessible account, organization, API key, and billing endpoints on `https://api.trufo.ai` and `https://eu.api.trufo.ai`.

All endpoints on this page authenticate with an `Authorization: Bearer <jwt>` access token obtained via `trufo login` or the [device authorization flow](platform-api.md#access-tokens-device-authorization-flow), following [Platform API](platform-api.md) conventions. Each session is bound to the user's active organization; `oid` in request bodies defaults to the session's active organization where optional and must match it if supplied.

MFA changes, switching active organizations, accepting legal agreements, and final OV/PV/BPV submissions are completed in [app.trufo.ai](https://app.trufo.ai).

---

## Account

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /account/info` | Bearer | `{}` | `aid`, `email`, `email_verified`, `mfa_enabled`, `first_name`, `last_name`, `created_at` |
| `POST /account/info/edit` | Bearer | `{"first_name"?: "...", "last_name"?: "..."}` | `{"status": "ok"}` |
| `POST /account/mfa/passkey/list` | MFA | `{}` | `passkeys[]`: `id`, `name`, `created_at` |
| `POST /account/logout` | Bearer | `{"refresh_token": "..."}` | `{"status": "ok"}` |
| `POST /account/logout/all` | Bearer | `{}` | `{"status": "ok"}` (revokes all active sessions for the account) |

Token refresh (`POST /account/refresh`), device authorization (`POST /account/device/{authorize,token}`), and loopback login (`POST /account/loopback/token`) are specified in [Platform API](platform-api.md#access-tokens-device-authorization-flow).

---

## Organizations and Settings

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /org/create` | Bearer (no org yet) | `{"name": "...", "default_content_region"?: "global" \| "europe"}` | `oid`, `access_token`, `refresh_token`, `default_content_region` |
| `POST /org/list` | Bearer | `{}` | `orgs[]`: `oid`, `name`, `role`, `org_type`, `management_org` |
| `POST /org/info` | Bearer | `{"oid"?: "..."}` | `oid`, `name`, `created_by`, `created_at`, `default_content_region` |
| `POST /org/info/edit` | MFA, owner/admin | `{"oid"?: "...", "name": "..."}` | `{"status": "ok"}` |
| `POST /org/region/edit` | MFA, owner/admin | `{"oid"?: "...", "default_content_region": "global" \| "europe"}` | `{"status": "ok"}` |
| `POST /org/delete` | MFA, owner | `{"oid"?: "..."}` | `{"status": "ok"}`. Standalone organizations only: a sub-organization (`400 CannotDeleteSubordinateOrg`) and a management organization with active sub-organizations (`400 OrgHasSubordinateOrgs`) are refused |
| `POST /org/agreements` | MFA, member+ | `{}` | `agreements[]` with current version and latest `acceptance` record (if any) |
| `POST /org/activity` | MFA, member+ | `{"oid": "...", "category"?: "...", "from_ts"?: "...", "to_ts"?: "...", "limit"?: 50, "cursor"?: "..."}` | `{"events": [...], "next_cursor": str \| null, "categories": [...]}` (pass `next_cursor` back as `cursor` for the next page; `categories` lists valid `category` filters) |

### Organization Validation (OV) status and uploads

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /org/ov/status` | MFA, member+ | `{"oid"?: "..."}` | `oid`, `status`, `application_id`, submitted legal/address/contact fields, `submitted_at`, `approved_at`, `reviewer_notes`, `ov_active` (bool), `validated_expires_at` (expiry of the active validation, else `null`) |
| `POST /org/ov/upload` | MFA, owner/admin | `multipart/form-data`: `file` (PDF/image, max **50 MB**) + optional `oid` form field | `{"s3_key": "..."}` (reference the key in your OV submission). `400 FileTooLarge` above 50 MB |
| `POST /org/ov/rep-signing/resend` | MFA, owner/admin | `{"oid"?: "..."}` | `{"status": "ok"}` (invalidates prior link and emails a fresh 7-day signing link to the authorized rep) |

---

## Members and Invitations

Roles are `"owner"`, `"admin"`, and `"member"`.

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /org/member/list` | MFA, member+ | `{"oid"?: "..."}` | `members[]`: `aid`, `email`, `first_name`, `last_name`, `role`, `joined_at` |
| `POST /org/member/remove` | MFA, owner/admin | `{"oid"?: "...", "aid": "..."}` | `{"status": "ok"}` |
| `POST /org/member/role` | MFA, owner | `{"oid"?: "...", "aid": "...", "role": "owner" \| "admin" \| "member"}` | `{"status": "ok"}` |
| `POST /org/member/leave` | MFA, member+ | `{"oid"?: "..."}` | `{"status": "ok"}` (owners must transfer ownership first) |
| `POST /org/invite/send` | MFA, owner/admin | `{"oid"?: "...", "email": "...", "role"?: "member" \| "admin"}` | `{"invite_token": "..."}` |
| `POST /org/invite/list` | MFA, member+ | `{"oid"?: "..."}` | `invites[]`: `invite_token`, `email`, `role`, `invited_by`, `expires_at` |
| `POST /org/invite/resend` | MFA, owner/admin | `{"oid"?: "...", "invite_token": "..."}` | `{"status": "ok"}` |
| `POST /org/invite/revoke` | MFA, owner/admin | `{"oid"?: "...", "invite_token": "..."}` | `{"status": "ok"}` |
| `POST /org/invite/pending` | Bearer (verified email) | `{}` | Pending invitations addressed to the caller's email |
| `POST /org/invite/accept` | Bearer (verified email) | `{"invite_token": "..."}` | `oid`, `access_token`, `refresh_token` |

---

## Organization Groups and Sub-Organizations

These endpoints manage multi-brand organization groups (see [Trufo Account Setup](../guides/2-trufo-account-setup.md#standalone-organization-or-organization-group)). Management endpoints require an active **management organization** session (`403 ManagementOrgRequired` otherwise).

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /org/group/create` | MFA, owner (standalone org) | `{"name": "..."}` | `{"oid": "..."}` (the new management org, owned by the caller; permanent conversion). No new tokens are issued: the session stays on the converted organization, now the group's first sub-organization. Switch to the management organization in [app.trufo.ai](https://app.trufo.ai); switching there changes the dashboard session only, and existing `trufo login` tokens (including refreshed ones) stay bound to their organization. A sub-organization is refused with `403 BillingOrgRequired` and a management organization with `403 WorkingOrgRequired` |
| `POST /org/group/member/list` | MFA, management org owner/admin | `{}` | `members[]` across the organization group |
| `POST /org/subordinate/create` | MFA, management org owner/admin | `{"name": "...", "owner_aid": "...", "default_content_region"?: "global" \| "europe"}` | `{"oid": "..."}` |
| `POST /org/subordinate/list` | MFA, management org member+ | `{}` | `orgs[]`: `oid`, `name`, `default_content_region`, `member_count`, `created_at` |
| `POST /org/subordinate/usage` | MFA, management org member+ | `{"target_oid": "...", "range"?: "1h" \| "24h" \| "7d" \| "30d" \| "90d"}` | Usage breakdown for the sub-organization |
| `POST /org/subordinate/member/list` | MFA, management org owner/admin | `{"target_oid": "..."}` | `members[]` in `target_oid` |
| `POST /org/subordinate/member/add` | MFA, management org owner/admin | `{"target_oid": "...", "aid": "...", "role": "admin" \| "member"}` | `{"status": "ok"}` (`400 InvalidRole` for `"owner"`; use `/org/subordinate/member/role` to make an owner) |
| `POST /org/subordinate/member/remove` | MFA, management org owner/admin | `{"target_oid": "...", "aid": "..."}` | `{"status": "ok"}` |
| `POST /org/subordinate/member/role` | MFA, management org owner/admin | `{"target_oid": "...", "aid": "...", "role": "owner" \| "admin" \| "member"}` | `{"status": "ok"}` |
| `POST /org/subordinate/invite/send` | MFA, management org owner/admin | `{"target_oid": "...", "email": "...", "role"?: "member" \| "admin"}` | `{"invite_token": "..."}` |
| `POST /org/subordinate/invite/list` | MFA, management org owner/admin | `{"target_oid": "..."}` | `invites[]` in `target_oid` |
| `POST /org/subordinate/invite/resend` | MFA, management org owner/admin | `{"target_oid": "...", "invite_token": "..."}` | `{"status": "ok"}` |
| `POST /org/subordinate/invite/revoke` | MFA, management org owner/admin | `{"target_oid": "...", "invite_token": "..."}` | `{"status": "ok"}` |

---

## API Keys

API keys belong to a working organization (standalone or sub-organization; `403 WorkingOrgRequired` on a management org). See [API key scopes](platform-api.md#api-keys) for valid `scope` values and prerequisites.

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /apikey/create` | MFA, owner/admin | `{"oid"?: "...", "scope": "<scope>", "label": "...", "duration_days"?: 1..390}` | `apikey_id`, `api_key` (shown once), `expires_at` |
| `POST /apikey/list` | MFA, owner/admin | `{"oid"?: "..."}` | `keys[]`: `apikey_id`, `scope`, `label`, `enabled`, `expires_at`, `last_used_at` |
| `POST /apikey/info` | MFA, owner/admin | `{"apikey_id": "..."}` | `apikey_id`, `oid`, `aid`, `scope`, `label`, `enabled`, `expires_at`, `last_used_at`, `create_ts` |
| `POST /apikey/edit` | MFA, owner/admin | `{"apikey_id": "...", "label": "..."}` | `{"status": "ok"}` |
| `POST /apikey/revoke` | MFA, owner/admin | `{"apikey_id": "..."}` | `{"status": "ok"}` (propagates within one hour) |

---

## Billing, Plans, and Usage

In an organization group, billing is owned by the management organization (`403 BillingOrgRequired` on sub-organization billing mutations). Every sub-organization has the access granted by the management organization's active plans, so one subscription covers the whole group; if a management-organization plan ends, it ends for every sub-organization. Sub-organizations can still view plans, pricing, and their own usage.

Product identifiers (`tp`) accepted by pricing and subscription endpoints:
`c2pa_signing_api`, `c2pa_signing_api_branded`, `watermark_api`, `c2pa_custom_domain`, `c2pa_cert_lv1_backend`, `c2pa_cert_lv1_distributed`, `c2pa_cert_lv1_edge`, `c2pa_tsa_api`, `cawg_cert_organization`.

- `c2pa_cert_lv1_{backend,distributed,edge}`: Assurance Level 1 Generator Product certificates by where signing runs: `backend` (entirely on your backend servers), `distributed` (split between edge devices and a central signing backend), and `edge` (directly on conformant cameras or other edge devices). Assurance Level 2 (`c2pa-l2`) is enabled per product via [support@trufo.ai](mailto:support@trufo.ai). See [Certificates](../topics/certificates.md).
- `c2pa_custom_domain`: Domain Validation (`/domain/dv/*`), required for custom reverse-DNS assertion labels and custom redaction reasons.

### Read endpoints

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /billing/pricing?tp=<tp>` | Member+ | Query param `tp` (optional `oid`); body `{}` | `plans[]` with pricing tiers, currency, and intervals |
| `POST /billing/subscriptions` | Member+ | `{"oid": "..."}` | Active subscriptions, enrolled products, quantities, and cancellation dates |
| `POST /billing/usage` | Member+ | `{"oid": "...", "range"?: "1h" \| "24h" \| "7d" \| "30d" \| "90d"}` | Usage metrics by product |
| `POST /billing/account/info` | Owner/admin | `{"oid": "..."}` | Payment method, billing email, net terms, billing address |
| `POST /billing/invoices` | Owner/admin | `{"oid": "...", "limit"?: 20}` | `invoices[]` with line items, status, amounts, and invoice URLs |
| `POST /billing/charges` | Owner/admin | `{"oid": "...", "limit"?: 50}` | `payments[]` payment history |
| `POST /billing/credits/balance` | Owner/admin | `{"oid": "..."}` | Current credit balance |
| `POST /billing/credits/transactions` | Owner/admin | `{"oid": "...", "limit"?: 50}` | Credit balance ledger |

### Billing management endpoints

| Endpoint | Auth | Request | Response |
| --- | --- | --- | --- |
| `POST /billing/account/setup` | MFA, owner/admin | `{"oid": "...", "success_url": "...", "cancel_url": "..."}` | Hosted checkout URL to attach a payment method |
| `POST /billing/account/update` | MFA, owner/admin | `{"oid": "...", "billing_email"?: "...", "billing_address"?: {"line1"?: "...", "line2"?: "...", "city"?: "...", "state"?: "...", "postal_code"?: "...", "country"?: "..."}}` | Updated billing contact/address |
| `POST /billing/portal` | MFA, owner/admin | `{"oid": "...", "return_url": "..."}` | Hosted billing portal URL |
| `POST /billing/checkout` | Owner/admin | `{"oid": "...", "tp": "<tp>", "plan_id"?: "...", "success_url": "...", "cancel_url": "..."}` | Hosted checkout URL (card) or enrolled subscription status |
| `POST /billing/cancel-tp` | MFA, owner/admin | `{"oid": "...", "tp": "<tp>"}` | Scheduled cancellation details for the product |
| `POST /billing/un-cancel-tp` | MFA, owner/admin | `{"oid": "...", "tp": "<tp>"}` | Restored subscription status |

---

## Related References

- Platform conventions, auth, and error codes: [platform-api.md](platform-api.md)
- Certificates, PV/BPV drafts, domain validation, TSA, and OCSP: [certificates-api.md](certificates-api.md)
- Account and organization setup: [Trufo Account Setup](../guides/2-trufo-account-setup.md)
