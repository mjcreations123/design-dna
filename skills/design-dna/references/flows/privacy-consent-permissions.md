# Privacy, consent, and permissions

Use this for product-facing collection, disclosure, sharing, consent, tracking,
device access, visibility, retention, withdrawal, and user control. This complements
review-artifact [data handling](../quality/data-handling.md); it does not determine
legal basis, policy, security architecture, or regulatory compliance.

## Contents

- [Start with purpose and minimization](#start-with-purpose-and-minimization)
- [Explain at the decision point](#explain-at-the-decision-point)
- [Make choice meaningful](#make-choice-meaningful)
- [Provide lifecycle control](#provide-lifecycle-control)
- [Model truthful states and recovery](#model-truthful-states-and-recovery)
- [Keep the experience accessible](#keep-the-experience-accessible)
- [Verify and escalate](#verify-and-escalate)

## Start with purpose and minimization

For each requested datum, permission, or disclosure, establish:

- the user-facing purpose and necessary scope;
- whether it is essential, optional, conditional, or requested by a third party;
- who receives it, where it is shown, and which system is authoritative;
- retention, sharing, visibility, withdrawal, and deletion behavior;
- the consequence of accepting, refusing, limiting, or later changing it;
- an alternative path when one is genuinely supported.

Collect only what the confirmed service needs. Separate service-essential
processing from optional personalization, analytics, marketing, public sharing,
and device permissions. Never infer consent because data is available.

## Explain at the decision point

Use plain, specific, just-in-time explanations before the action occurs. State
what will be accessed or shared, with whom, why, for how long when known, and
what the user can change later. Put unexpected or consequential effects in the
main flow; a link to a privacy notice is supporting detail, not a substitute.

Request identity, location, camera, microphone, contacts, notifications,
files, health, financial, or similar access after the user can understand the
value and scope. Match the explanation to the exact platform prompt and
permission the product actually requests.

## Make choice meaningful

- Use explicit, granular choices for distinct optional purposes.
- Keep accept, refuse, limit, and withdraw actions clear and proportionate.
- Avoid prechecked consent, coerced bundles, deceptive hierarchy, or confusing
  negatives.
- Let refusal continue through the available reduced or alternate experience.
- Explain denied, restricted, one-time, temporary, and system-managed access.
- Do not repeatedly pressure users after refusal; re-request only with a
  relevant new action or changed need.

Do not describe an action as consent when another legal or operational basis
applies. Have the accountable legal or privacy specialist determine that basis.

## Provide lifecycle control

Where supported, let users inspect and change visibility, connected services,
sharing, consent, permissions, communication choices, export, correction, and
deletion from a discoverable place. Explain effects on features, other people,
shared records, retention obligations, backups, processors, and completion
timing before a consequential change.

Confirm receipt and completion separately when processing is delayed. Provide a
reference or status route where appropriate. Show public, organization-wide,
link-accessible, or third-party visibility before publication or sharing.

## Model truthful states and recovery

Represent the applicable requesting, granted, limited, denied, blocked,
expired, revoked, pending, processing, completed, partially completed, and
failed states. Read authoritative platform or server state when available;
never show a saved, revoked, or deleted success state before confirmation.

Design recovery for network failure, an unavailable platform setting,
conflicting device and account permissions, stale preferences, propagation
delay, third-party failure, reauthorization, account closure, and deletion
failure. State what changed, what remains active, what data may remain, and the
safe next action without exposing private information.

## Keep the experience accessible

Use visible labels, clear grouping, logical focus, keyboard access, status
announcements, readable contrast, and meaning beyond color or motion. Keep
language concise, inclusive, localizable, and understandable without legal
expertise. Avoid unnecessary cognitive load or urgency.

Escalate child-directed experiences, vulnerable users, sensitive attributes,
biometrics, health, finance, identity, precise location, public exposure, and
regulated or high-risk processing before implementation.

## Verify and escalate

Compare the interface with a current data and permission inventory. Trace what
is collected, sent, stored, shown, shared, retained, revoked, exported, and
deleted. Verify UI state against backend, platform, processor, notification,
and account behavior.

Test refusal, limited access, withdrawal, re-entry, cross-device changes,
session expiry, propagation delay, offline and server failure, third-party
outage, keyboard, screen reader, zoom, mobile, localization, and content
extremes. Confirm the documented core-service path still works when optional
access is declined.

Require privacy, legal, security, data-governance, accessibility, platform, and
domain specialists for lawful basis, notice and consent requirements, retention,
deletion, auditability, threat review, regulated processing, and compliance claims.
