# Location and wayfinding

Use this for addresses, branch finders, venue maps, service areas, pickup
points, directions, floor plans, or movement through a place. Use data
visualization instead when geography encodes an analytical comparison.

## Start with the location task

Identify whether the user needs to:

- confirm that a place or service area applies;
- compare branches by distance, hours, inventory, access, or service;
- travel to an entrance, pickup point, room, seat, or facility;
- understand a route, boundary, closure, or accessibility condition;
- hand off to a trusted navigation provider.

Do not make a map the only path to an address, result, instruction, or decision.

## Model truthful place data

For each applicable location, maintain:

- official name, address, coordinates, and data owner;
- timezone, regular hours, exceptions, and last-confirmed date;
- phone or contact route;
- entrance, floor, unit, landmark, pickup, parking, transit, and access notes;
- services, inventory, appointment or eligibility constraints;
- temporary closure, relocation, service-area, or route restrictions.

Do not invent pins, travel times, current location, traffic, accessibility,
service coverage, or open/closed status. Explain uncertainty and freshness.

## Coordinate map and list

- Give every marker an accessible name and corresponding list/result item.
- Synchronize selection, focus, hover, and expanded detail without requiring
  hover or precise pointing.
- Preserve active filters, search area, result count, and selected location.
- Keep current context when zooming, panning, loading more, or returning from
  details.
- Cluster dense markers without hiding the underlying count or accessible path.
- Make distance units, origin, sorting method, and calculation limits explicit.
- Offer text search, structured results, and address copy even when tiles fail.

For a single destination, a clear address, landmarks, access notes, and
directions handoff may outperform an embedded map.

## Handle permissions and privacy

Request device location only after explaining the benefit and providing a
manual alternative. Handle denied, approximate, stale, unavailable, and
revoked permission. Do not retain, transmit, or infer precise location beyond
the approved purpose. Treat location analytics and third-party map embeds as
privacy and consent decisions.

## Design the journey

- Make the origin, destination, direction, next decision, and route status clear.
- Distinguish north-up map orientation from turn-by-turn or venue-relative
  orientation.
- Pair color, line style, labels, landmarks, and written steps.
- Show accessible entrances and routes only from verified data.
- Support detours, closures, multiple entrances, indoor transitions, and safe
  recovery when the user goes off route where the product claims to do so.
- Preserve critical instructions in low-connectivity and printable forms when
  the context warrants it.

## Third-party handoff

Name what will open, which destination will be shared, and whether the user
leaves the site. Use approved, correctly encoded destinations. Preserve a copy
or return path. Do not imply that an external provider's route, availability,
privacy, or accessibility has been verified unless it has.

## Verify

Test:

- valid, ambiguous, partial, international, and no-result searches;
- one, many, dense, unavailable, closed, and stale locations;
- marker-list synchronization by keyboard, touch, pointer, and screen reader;
- denied location, failed tiles, slow network, offline fallback, and external
  app absence;
- narrow, short-height, zoomed, high-contrast, reduced-motion, and RTL layouts;
- long translated addresses, non-Latin place names, and locale-aware distance;
- actual pins, entrances, service boundaries, hours, and directions targets.

Block release for a materially wrong address, pin, entrance, service area,
hours claim, or inaccessible-only route.
