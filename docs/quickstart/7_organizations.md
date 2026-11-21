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
  member becomes the owner and you become an admin; only the new owner can undo it. The
  owner cannot be removed, so transfer ownership first.

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

`trufo login` signs you in with a `trufo-api` key, and the CLI session works in that
key's organization. If you do not belong to that organization, the sign-in is refused
([CLI](../cli.md)).

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
group**. The management organization has members and billing only: it does not sign and
holds no API keys, Organization Validation, products or certificates. Each sub-org works
as in [Every Organization](#every-organization), except that the management organization
pays for it and the management organization's owner acts as owner in it.

An organization in no organization group is a **standalone organization**. With one
organization, you need none of this.

### Create a Management Organization and Sub-Orgs

**Management organization.** The owner of a standalone organization creates one and names
it. You become its owner, your organization becomes its first sub-org, and from then on
the management organization pays for it. You stay in your organization until you switch.

<!-- TBD: dashboard location -->
<!-- TBD: owner decision: what happens to the founding organization's existing card, plans and contract -->

**Sub-orgs.** From the management organization, its owner creates a sub-org with a name
and a default processing region. It starts with no members, and the management
organization pays for it from its creation.

<!-- TBD: dashboard location -->

Both need MFA. Each sub-org submits its own Organization Validation and accepts its own
agreements.

### Roles Across an Organization Group

Roles are per organization: a person can be an admin in one sub-org and a member in
another. Your role in the management organization decides what you can do across the
organization group:

| Role in the management organization | In the management organization | In each sub-org |
| ----------------------------------- | ------------------------------ | --------------- |
| Owner | Manage people and billing; create sub-orgs; attach organizations; add people to sub-orgs as admin or member; remove people | Acts as owner |
| Admin | Manage billing; invite members; add people to sub-orgs as members; remove members | Only the role they hold there, if any |
| Member | See sub-orgs, members, plans and usage | Only the role they hold there, if any |

The management organization's owner does not appear in a sub-org's member list, but what
they do there is recorded in its activity under their own name. A sub-org can also have
an owner of its own.

### Add People Across Sub-Orgs

**Newcomers.** Someone in no organization joins the organization group with one ordinary
invitation, to the management organization or to any sub-org.

<!-- TBD: owner decision: restricting which email domains can be invited into an organization group -->

**People already in the organization group.** From the management organization, its
owner or an admin adds them to a sub-org: the owner as admin or member, an admin as
member. No invitation email is sent, and the person can switch to the sub-org at once.
The owner or an admin removes people from a sub-org the same way, with the limits in
[People and Ownership](#people-and-ownership).

<!-- TBD: dashboard location -->

A sub-org's own owner and admins can also invite by email. Someone in an organization
outside the organization group cannot be invited or added.

### Attach an Existing Organization

A standalone organization joins an organization group by request:

1. The management organization's owner sends a request with the organization's
   Organization ID. They can withdraw it until it is accepted.

   <!-- TBD: dashboard location -->

2. Trufo emails each owner of that organization a link to review it, valid for 7 days.
3. An owner opens the link, signed in to that organization with MFA, and accepts.

   <!-- TBD: dashboard location -->

By accepting, the owner agrees that the management organization's owner acts as owner in
the organization, that the management organization pays for it from the next 00:00 UTC,
and that its own plans end on the 1st of next month (the current month is already paid).
Acceptance is refused while the management organization lacks a plan for a product the
organization has.

The organization keeps its own members, API keys, certificates, Organization Validation,
agreements and activity.

### Working Across Organizations

**Switching.** In the dashboard you work in one organization at a time and switch between
those you can enter: the organizations you belong to, and every sub-org for the
management organization's owner. Switching needs MFA. Your next sign-in opens the
organization you last switched to.

<!-- TBD: dashboard location -->

**Open tabs.** After you switch, a tab still showing the previous organization is refused
with `409 SessionOrgChanged`. Reload the tab.

**Keys and the CLI.** Create API keys in each sub-org that needs them. To use the CLI in
another sub-org, store that sub-org's `trufo-api` key and run `trufo login` again.

### Billing in an Organization Group

The management organization pays for every organization in its organization group. This
is not a setting: it follows from being in the organization group. Its plans cover every
sub-org, and its owner and admins manage them.

<!-- TBD: owner decision: pricing in an organization group (whether base fees and included amounts count once for the organization group) -->

| When | Who pays |
| ---- | -------- |
| A sub-org is created | The management organization, from its creation |
| An organization is attached | The management organization, from the next 00:00 UTC |
| A sub-org is detached | The management organization until the next 00:00 UTC, then the organization itself |

A sub-org cannot add a card, start a plan or resume a cancelled one: Trufo refuses with
`403 OrgBilledByManagementOrg`. For charges from before it joined, its owners and admins
can still see its invoices and payments and update its payment method. Its usage and plan
pages show which of the management organization's plans cover it, and its own usage,
without amounts.

The management organization's usage page also shows each organization's usage.

<!-- TBD: dashboard location -->

When a plan of the management organization ends, it ends for every organization in the
organization group.

### Detach, Remove and Close

**Detach a sub-org.** The sub-org's owner, or the management organization's owner,
detaches it from within the sub-org. This is refused unless the sub-org has an owner who
belongs to no other organization of the organization group; to give it one, invite that
person as an admin, then [transfer ownership](#people-and-ownership).

<!-- TBD: dashboard location -->

When a sub-org detaches:

- people who also belong to another organization of the organization group are removed
  from it
- the management organization's owner no longer acts as owner in it
- it keeps its other members, API keys, certificates, OV, agreements and activity
- from the next 00:00 UTC it pays for itself; services that need a plan stop until it
  has one, and nothing is deleted

**Remove a person from the organization group.** The management organization's owner or
an admin removes someone from all its organizations at once. An admin can remove only
someone who is a member, not an admin, in each of those organizations; anyone who is an
owner must transfer ownership first. Their API keys keep working; Trufo lists the keys
they created so you can revoke them.

<!-- TBD: dashboard location -->

**Close the management organization.** Its owner can delete it only when it has no
sub-orgs left: detach or delete each one first.

<!-- TBD: dashboard location -->

### Limits

- One level: a sub-org cannot have sub-orgs, and a management organization cannot be
  attached to another.
- An organization is in at most one organization group.
- An account belongs to one organization group, or to one standalone organization.

---

## Reference

- Accounts, organizations and agreements: [../api/api_trufo.md](../api/api_trufo.md#accounts-and-organizations)
- Setup, API keys and sign-in: [0_setup.md](0_setup.md)
- CLI reference: [../cli.md](../cli.md)
