# Travel and reservations

Use this for accommodation, transport, tours, dining, events, ticketing,
appointments, and inventory-bound reservations.

## Map the commitment

Model the actual sequence:

1. destination, venue, service, route, or experience discovery;
2. date, time, timezone, duration, party, traveler, room, seat, or resource selection;
3. availability, eligibility, accessibility, and required information;
4. base price, taxes, mandatory fees, deposits, add-ons, and currency;
5. review, policy acceptance, payment or hold, and confirmation;
6. calendar, ticket, receipt, directions, and pre-arrival information;
7. modification, transfer, cancellation, refund, disruption, and support.

Do not represent sample inventory, rates, countdowns, or availability as live.

## Keep options comparable

- Preserve dates, party, travelers, filters, and selected option through the journey.
- Identify exactly what varies: room, fare, seat, duration, inclusions,
  restrictions, refundability, baggage, accessibility, or cancellation.
- Show total price and material conditions before commitment.
- Distinguish request, hold, waitlist, quote, reservation, ticket, and confirmed purchase.
- Make local time, date boundaries, duration, and overnight changes explicit.
- Explain inventory freshness and what happens if availability changes.

## Design interruption and recovery

Preserve entered information through recoverable errors. Handle expired holds,
price changes, sold-out inventory, partial party availability, payment failure,
third-party failure, duplicate submission, back navigation, and session expiry.
When a handoff occurs, name the provider and preserve a safe return path.

Confirmation must include a durable reference, booked details, total, policy,
next step, and support path. Do not rely on a success animation alone.

## Prepare the real-world journey

Provide verified address, entrance, check-in, boarding, pickup, accessibility,
identity, age, documentation, safety, weather, and arrival requirements that
apply. Make changes and disruption prominent without fabricating real-time
monitoring. Offer printable, downloadable, or low-connectivity access when the
context requires it.

## Verify and escalate

Test one and many travelers, children or eligibility only when supported,
timezone and daylight-saving boundaries, unavailable and last-item inventory,
rate changes, discount failure, seat or room conflict, hold expiry, payment
failure, duplicate submission, modification, cancellation, refund, external
handoff, delayed confirmation, offline access, localization, keyboard, touch,
zoom, and screen reader.

Use payment, legal, accessibility, privacy, identity, travel, ticketing, tax,
and operations specialists for production rules. Block launch for incorrect
inventory, total price, policy, destination, time, confirmation, or apparently
live booking behavior.
