# Subscription and billing lifecycle

Use this for trials, plans, recurring charges, usage billing, invoices,
entitlements, payment failure, renewal, cancellation, and reactivation. Use the
ecommerce reference as well when physical goods or one-time retail are central.

## Expose the commercial contract

Before commitment, show the applicable:

- plan, billing period, currency, taxes, fees, included usage, limits, and overages;
- trial length, payment requirement, conversion date, and end behavior;
- discount duration, eligibility, and post-discount price;
- renewal timing, cancellation effective date, refund policy, and notice;
- seat, storage, feature, region, support, or entitlement differences;
- accountable terms, policy, and support route.

Do not hide material conditions in tooltips, low-contrast text, or a later
screen. Do not preselect a paid upgrade, recurring charge, insurance, or
marketing consent.

## Model plan changes

For upgrade, downgrade, seat change, add-on, pause, or reactivation, state:

- what changes now and at the next billing boundary;
- proration, credit, charge, refund, and tax treatment;
- affected users, data, features, quotas, and integrations;
- eligibility, pending approvals, and irreversible consequences;
- review, confirmation, receipt, and correction paths.

Use exact dates and amounts from the billing system when live. Label estimates,
quotes, and sample calculations. Prevent duplicate submission and preserve
idempotent recovery.

## Handle trial and renewal

Show current status and the next meaningful date. Distinguish free plan, trial,
grace period, scheduled cancellation, paused, delinquent, suspended, expired,
and cancelled. Do not imply that cancelling erases already-earned access,
stops an immediate charge, or retains data unless policy confirms it.

Make renewal reminders and trial conversion communication consistent across
product, email, invoice, and terms.

## Design payment failure and dunning

- Explain the failed amount, invoice, next retry, current access, grace period,
  and action required without exposing sensitive payment data.
- Preserve access appropriate to real policy; do not invent imminent deletion.
- Support update-payment, retry, alternate method, invoice retrieval, and
  support escalation where implemented.
- Distinguish recoverable payment failure from fraud, compliance, tax, or
  account restrictions.
- Confirm recovery and remove stale warnings after the billing system does.

## Make cancellation humane

Allow users to find cancellation without search tricks or coercive detours.
State effective date, remaining access, data retention, refunds or credits,
connected services, and reactivation conditions before confirmation. A
proportionate save offer may be presented once without blocking or
misrepresenting exit. Provide durable confirmation.

## Entitlements and billing authority

Show who may view invoices, change plans, add seats, update payment, or cancel.
Clarify when billing status and product entitlement are temporarily out of
sync. Do not infer permission from visual access to a control. Keep secrets,
full payment data, and restricted invoices out of client-visible source and
logs.

## Verify and escalate

Test trial start/end, renewal, upgrade, downgrade, proration, coupon expiry,
seat changes, tax or address change, multiple currencies, payment failure,
retry, grace, pause, cancellation, reactivation, refund, duplicate submission,
delayed webhooks, stale status, and partial service failure. Use sandboxes and
test clocks where available; never create a real charge without explicit
authority.

Require payments, accounting, tax, legal, privacy, security, and subscription
platform specialists for calculation correctness, processor behavior,
compliance, disputes, or production configuration.
