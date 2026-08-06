# Ecommerce

Use this for catalog, product, cart, checkout, account, subscription, or
transactional retail experiences.

## Route by job

Use whichever modes illuminate each route's real jobs. Discovery may persuade,
specifications may support reading, and checkout may operate at the same time;
these are common relationships rather than required route forms or exclusive
labels. Share only the brand,
behavior, and system decisions that should actually remain common.

## Design the complete journey

Cover:

1. discovery, category, search, filter, sort, and no results;
2. product identity, media, variant, price, tax, stock, delivery, and returns;
3. comparison and compatibility when relevant;
4. cart editing, quantity, discounts, estimates, and persistence;
5. checkout identity, address, delivery, payment, review, and confirmation;
6. failure, retry, duplicate submission, interruption, and recovery;
7. order status, cancellation, return, refund, and support.

Do not optimize only one promotional view while leaving selection,
transaction, failure, and recovery unfinished.

## Preserve product truth

- Use approved names, images, specifications, prices, currencies, stock,
  delivery estimates, reviews, and sustainability claims.
- Distinguish product variants visually and programmatically.
- Do not select add-ons, insurance, tips, subscriptions, or marketing consent by
  stealth.
- Expose material conditions before purchase.
- Make limited stock or urgency claims only from real data.
- Clearly label concept stores and sandbox transactions.

## Make selection resilient

- Preserve filters, sort, scroll position, and viewed context.
- State why products are unavailable or incompatible.
- Keep product identity visible through cart and checkout.
- Prevent invalid variant combinations.
- Recalculate totals transparently.
- Handle long names, missing media, extreme prices, sale states, multiple
  currencies, and localized units.

## Protect checkout

- Allow review and correction before final submission.
- Prevent accidental duplicate purchase.
- Keep validation near the cause without erasing input.
- Explain taxes, fees, delivery, renewal, cancellation, and return terms.
- Provide guest checkout when the product and policy allow.
- Support password managers, paste, and accessible authentication.
- Confirm the outcome and provide a durable order reference.

## Cover recurring commerce

When the offer includes a trial, membership, replenishment, recurring box,
service plan, or usage-based charge, apply the complete
[subscription and billing lifecycle](../flows/subscription-billing.md).
Design trial conversion, renewal, upgrade, downgrade, proration, payment
failure, grace, pause, entitlement change, cancellation, reactivation, and
refund—not only the initial subscription selector.

## Verify

Test representative products and the worst plausible combinations across:

- mobile, keyboard, screen reader, zoom, and slow network;
- in-stock, low-stock, out-of-stock, preorder, and discontinued;
- invalid promotion, payment failure, address failure, and partial service
  failure;
- refresh, back navigation, timeout, session expiry, and duplicate submission;
- localization, RTL, tax, currency, shipping, and translated copy;
- return, refund, cancellation, and support paths.

Use payment sandboxes and test data. Do not charge a real payment, publish a
real product, or mutate production inventory without explicit authority.
