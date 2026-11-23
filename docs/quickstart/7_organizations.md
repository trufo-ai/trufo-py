# Quickstart: Organizations, People and Roles

How accounts, organizations and roles fit together. [Every Organization](#every-organization)
applies to all customers; [Organization Groups](#organization-groups) applies only if you
run several organizations.

All of this is managed in the dashboard at [app.trufo.ai](https://app.trufo.ai); the SDK
does not wrap it ([Accounts and Organizations](../api/api_trufo.md#accounts-and-organizations)).

---

## Every Organization

### Accounts and Organizations

Your account is you: one email address, your sign-in and your MFA. An organization is
the customer: its members, API keys, Organization Validation (OV), certificates,
agreements and billing. Each organization has an Organization ID (`org_…`), shown in
[Organization Settings](https://app.trufo.ai/settings/org).

An account belongs to one organization, which you get in one of two ways:

- **Create one.** Register at [app.trufo.ai/register](https://app.trufo.ai/register) and
  create a new organization. You become its owner.
- **Accept an invitation.** An owner or admin invites your email address. Accept it with
  an account that uses that address, creating one if you have none.

Only inside an [organization group](#organization-groups) can an account belong to
several organizations.

### Roles

Everyone in an organization is an owner, an admin or a member.

| What you can do | Owner | Admin | Member |
| --------------- | ----- | ----- | ------ |
| See members, activity, agreements, OV status, products, certificates, plans and usage | Yes | Yes | Yes |
| Sign content in the dashboard | Yes | Yes | Yes |
| Rename the organization, change its default processing region | Yes | Yes | No |
| Invite people | As admin or member | As member | No |
| Remove people | Admins and members | Members | No |
| Change roles, transfer ownership | Yes | No | No |
| Create, see and revoke API keys | Yes | Yes | No |
| Submit Organization Validation and Product Validation, accept agreements | Yes | Yes | No |
| Manage products, instances, credentials, domains and CAWG certificates; revoke certificates | Yes | Yes | No |
| Manage billing, see invoices and payments | Yes | Yes | No |

### People and Ownership

Owners and admins manage people under **Manage Users** at
[app.trufo.ai/settings/org](https://app.trufo.ai/settings/org#organization-members).

- **Invite.** Choose **Invite User**, then enter an email address and a role. An
  invitation expires after 7 days; you can resend or revoke it until then. Someone who
  already belongs to another organization cannot be invited.
- **Change a role.** The owner picks a new role in the **Role** column.
- **Remove.** Removed people lose access at once. API keys they created keep working,
  because keys belong to the organization.
- **Transfer ownership.** The owner picks **Owner** for another member and confirms. That
  member becomes the owner and you become an admin; only the new owner, or a sub-org's
  management organization, can undo it. The owner cannot be removed, so transfer
  ownership first.

### Sign-In Security

MFA belongs to your account. Set it up at
[app.trufo.ai/settings/user](https://app.trufo.ai/settings/user) with an authenticator
app (TOTP), a passkey, or both.

You need a session signed in with MFA to see or manage members, invitations, API keys,
Organization Validation, agreements, activity, products and certificates; to change the
organization's name, region, billing details or payment method, or cancel a plan; and to
approve a CLI sign-in (`trufo login`). Without MFA these return `403 MFARequired`
([Multi-Factor Authentication](../api/api_trufo.md#multi-factor-authentication)).

### Organization Validation

OV confirms your organization's legal identity; production signing and certificates
need it. An owner or admin submits it at
[app.trufo.ai/settings/org/ov](https://app.trufo.ai/settings/org/ov).

The application names an **authorized representative**: an employee or legal agent who
can sign the Subscriber Agreement for the organization and confirm the request when
Trufo calls the phone number you give.

- **If you are the representative,** you accept the Master Services Agreement and the
  Subscriber Agreement when you submit.
- **If someone else is,** enter their details. Trufo emails them a link to review and
  sign both agreements. It expires after 7 days, and an owner or admin can resend it
  until it is signed. The representative need not be a member; if their email address
  has a Trufo account, they sign in to it to sign.

### Agreements

Agreements are accepted for the organization, not for a person. Owners and admins accept
them under **Agreements** at
[app.trufo.ai/settings/org#agreements](https://app.trufo.ai/settings/org#agreements),
confirming they are authorized to accept for the organization. The authorized
representative also accepts the Master Services Agreement and Subscriber Agreement
through OV. [Agreements](../api/api_trufo.md#agreements) lists which features need which.

### API Keys and the CLI

An API key belongs to the organization it was created in, not to the person who created
it, and every request made with it acts in that organization. Owners and admins create
keys at [app.trufo.ai/settings/org#api-access](https://app.trufo.ai/settings/org#api-access)
([API Key Scopes](0_setup.md#api-key-scopes)).

`trufo login` signs you in with a `trufo-api` key, and the CLI session works in your
organization ([CLI](../cli.md)).

---

## Organization Groups

### When to Use a Management Organization

Use one when your company runs several organizations, such as legal entities that each
sign under their own validated name, and wants one place to pay and manage people.

```
Management organization   members, billing
├── Sub-organization A    members, API keys, OV, certificates, signing
└── Sub-organization B    members, API keys, OV, certificates, signing
```

A management organization and its sub-organizations (sub-orgs) form an **organization
group**. The management organization does not sign or watermark and holds no API keys,
Organization Validation, products or certificates; Trufo refuses such work there with
`403 WorkingOrgRequired`. Each sub-org works as in
[Every Organization](#every-organization), except that the management organization pays
for it and can also manage its people.

An organization in no organization group is a **standalone organization**. With one
organization, you need none of this.

### Create a Management Organization and Sub-Orgs

**Management organization.** Trufo creates it and adds its first owner, whose account
must not belong to any organization yet.

<!-- TBD: owner decision: how a customer asks Trufo for a management organization -->

**Sub-orgs.** From the management organization, its owner or an admin creates a sub-org
with a name, a default processing region and an owner chosen from the organization
group, who can be you. The management organization pays for it from its creation. To
work in it, add people to it, yourself included if you are not its owner
([Add People Across Sub-Orgs](#add-people-across-sub-orgs)).

<!-- TBD: dashboard location -->

Creating a sub-org needs MFA. Each sub-org submits its own Organization Validation and
accepts its own agreements.

### Roles Across an Organization Group

Roles are per organization: a person can be an admin in one sub-org and a member in
another. In the management organization, roles work as in [Roles](#roles) for its
members and billing, and also decide what you can do for its sub-orgs:

| What you can do from the management organization | Owner | Admin | Member |
| ------------------------------------------------ | ----- | ----- | ------ |
| See its sub-orgs and their usage | Yes | Yes | Yes |
| Create sub-orgs | Yes | Yes | No |
| Add people to a sub-org with any role, change their roles, remove them | Yes | Yes | No |

From any other organization, Trufo refuses these with `403 ManagementOrgRequired`.

A role in the management organization, owner included, gives no role in its sub-orgs. To
work in a sub-org you need a role there, so its member list shows everyone who can work
in it.

### Add People Across Sub-Orgs

**Newcomers.** Someone in no organization joins the organization group with one ordinary
invitation, to the management organization or to any sub-org.

<!-- TBD: owner decision: restricting which email domains can be invited into an organization group -->

**People already in the organization group.** From the management organization, its
owner or an admin adds them to a sub-org with any role. No invitation email is sent, and
the person can switch to the sub-org at once. Someone in no organization yet is refused
with `400 AccountNotInOrgGroup`; invite them instead.

<!-- TBD: dashboard location -->

The same people change roles in a sub-org and remove people from it, themselves
included. Making someone owner makes the sub-org's previous owner an admin; the owner
cannot be removed or given another role until someone else is made owner.

A sub-org's own owner and admins can also invite by email. Someone in an organization
outside the organization group cannot be invited or added.

### Working Across Organizations

**Switching.** In the dashboard you work in one organization at a time and switch between
the organizations you belong to. Switching needs MFA. Your next sign-in opens the
organization you last switched to, while you still belong to it.

<!-- TBD: dashboard location -->

**Losing access.** If you are removed from the organization a session works in, the
session ends with `401 OrgMembershipRevoked`; sign in again.

**Keys and the CLI.** Create API keys in each sub-org that needs them. A `trufo login`
session cannot switch, and opens in one of the organizations your account belongs to.

### Billing in an Organization Group

The management organization pays for every organization in its organization group. This
is not a setting: it follows from being in the organization group. Its plans cover every
sub-org, and its owner and admins manage them.

<!-- TBD: owner decision: pricing in an organization group (whether base fees and included amounts count once for the organization group) -->

A sub-org has no billing of its own: it cannot add a card, start, change or resume a
plan, or see plans, invoices or payments, and Trufo refuses these with
`403 BillingOrgRequired`. Its usage page shows the products the management organization
pays for and the sub-org's own usage, without amounts.

The management organization's usage page shows the organization group's usage, in total
and for each sub-org.

<!-- TBD: dashboard location -->

When a plan of the management organization ends, it ends for every organization in the
organization group.

### Limits

- One level: a sub-org cannot have sub-orgs.
- A standalone organization cannot join an organization group, and a sub-org cannot
  leave one.
- An organization is in at most one organization group.
- An account belongs to one organization group, or to one standalone organization.
- A sub-org cannot be deleted, and a management organization cannot be deleted while it
  has sub-orgs.

---

## Reference

- Accounts, organizations and agreements: [../api/api_trufo.md](../api/api_trufo.md#accounts-and-organizations)
- Setup, API keys and sign-in: [0_setup.md](0_setup.md)
- CLI reference: [../cli.md](../cli.md)
