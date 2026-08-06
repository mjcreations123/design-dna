# Identity, account, and onboarding

Use this for signup, invitations, authentication, verification, profile,
membership, permissions, recovery, onboarding, export, and account exit. This
is a UX lifecycle contract, not a security or identity-architecture review.

## Map the lifecycle

Model only the states the product supports:

1. eligibility, invitation, or account creation;
2. email, phone, domain, age, or organization verification;
3. sign-in through password, passkey, magic link, SSO, or approved provider;
4. MFA enrollment, challenge, backup, and recovery;
5. initial setup, role or workspace choice, import, and first useful outcome;
6. returning sign-in, session expiry, reauthentication, and device management;
7. profile, privacy, consent, team membership, role, and ownership changes;
8. lockout, suspension, compromise, support, and recovery;
9. export, transfer, leave, deactivation, deletion, and retention notice.

Do not render unsupported methods, organizations, approvals, or recovery paths
as if they operate.

## Make state and consequence clear

- Explain why an account or verification step is needed before asking for data.
- Distinguish create account, join workspace, accept invitation, switch
  workspace, and request access.
- Show the signed-in identity, active organization, role, and consequential
  action scope where confusion can cause harm.
- Preserve the intended destination through sign-in when safe.
- State session expiry, resend timing, link expiry, retry limits, and support
  handoff truthfully.
- Never reveal whether another person's account exists when that would create
  privacy or security risk.

Use neutral, actionable error language. Do not blame the user or expose
internal authentication detail.

## Design recovery as a first-class path

Support the product's real alternatives for lost credentials, unavailable
devices, expired links, changed email or phone, unavailable SSO, and lost MFA
factors. Show which identity is being recovered and what will happen next.
Avoid dead-end "contact support" instructions unless staffed support and
response expectations are confirmed.

Consequential identity changes should require suitable reauthentication,
confirmation, notification, and reversal or escalation according to the real
security policy.

## Onboard toward value

- Ask only for information required now.
- Let users understand progress, requirements, and the first useful outcome.
- Permit skip, save, resume, or later completion when the product allows it.
- Distinguish optional personalization from required configuration.
- Preserve partial work across recoverable errors and handoffs.
- Avoid celebratory completion before setup is actually usable.
- Provide an empty-state path that teaches with the user's real objects, not
  invented activity.

## Account control and exit

Make profile, consent, connected services, devices, notifications, data
export, team departure, ownership transfer, and deletion discoverable according
to their consequence. Explain timing, retained data, lost access, downstream
effects, and whether an action can be reversed. Do not obstruct cancellation,
export, or deletion through visual hierarchy.

## Access and verification

Support password managers, paste, autofill, visible labels, useful input types,
show-password control, keyboard navigation, zoom, error association, status
announcements, and non-cognitive-test authentication alternatives. Test magic
links and one-time codes with clear focus and resend behavior without relying
on automatic code capture.

## Verify and escalate

Test invited, new, returning, unverified, expired, locked, suspended, deleted,
wrong-workspace, insufficient-permission, partial-onboarding, and recovery
states. Cover back/refresh, multiple tabs, delayed email, duplicate submission,
session expiry, device loss, network failure, and safe return from identity
providers.

Require security, privacy, legal, data-retention, and identity specialists for
the actual authentication protocol, authorization model, abuse resistance,
secrets, recovery assurance, regulated identity, or production threat review.
