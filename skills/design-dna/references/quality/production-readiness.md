# Production readiness

Use this near handoff when a website or web UI may move beyond a concept. Readiness is stage-, route-, and environment-specific evidence; it is not a visual impression or a blanket claim.

## Name the stage and boundary

| Stage | Evidence boundary |
| --- | --- |
| Concept | Truthful, reversible material; integrations and public facts may remain clearly labeled placeholders. |
| Demo | A bounded scenario with safe sample data and no implied production behavior. |
| Staging | Production-like build and configuration tested without exposing real users, secrets, payments, or destructive operations. |
| Production candidate | Approved facts, assets, integrations, disclosures, operational ownership, and release gates for the intended environment. |

State which routes, roles, locales, devices, integrations, and failure modes were assessed. Never call the whole product production-ready from one route, screenshot, build, scan, or synthetic score.

## Complete public discoverability

Verify, where relevant:

- unique page titles, descriptions, canonical intent, language, icons, and share previews;
- crawl and indexing policy, sitemap, redirects, status codes, and useful not-found behavior;
- structured data that matches visible, approved content;
- stable headings, link purpose, internal discovery, and site search behavior;
- contact, policy, ownership, and last-updated information;
- preview behavior when images, scripts, cookies, or authentication are unavailable.

Do not add search keywords, schema, reviews, prices, availability, authorship, or organization facts that the visible experience and approved source cannot support.

## Trigger specialist review

Escalate rather than making broad assurances when the work includes authentication or authorization, personal or sensitive data, payments, regulated claims, children, healthcare, finance, employment, location tracking, user-generated content, high-risk automation, contractual accessibility, or jurisdiction-specific obligations.

The appropriate specialists should assess applicable threat models, dependency and supply-chain risk, secrets, security headers, abuse paths, data minimization, consent, retention and deletion, incident response, terms, privacy disclosures, licensing, tax, and regulatory duties. Record the review performed and its scope; do not convert a checklist into a security, privacy, legal, or compliance certification.

## Prepare the operational handoff

Confirm ownership and recovery for:

- environment variables, secrets, service accounts, domains, certificates, and third parties;
- reproducible build artifact, configuration, migrations, seed data, and compatibility;
- caching, invalidation, redirects, scheduled work, and background jobs;
- health signals, logs, alerts, analytics governance, and support escalation;
- backup, restore, rollback, incident, maintenance, and decommission paths;
- content, pricing, policy, integration, and dependency updates after launch.

Document the expected release sequence, verification signals, rollback threshold, and named decision owner. Test production-like behavior through the safest available environment.

## Record the release evidence

For each release gate, keep the check, environment, build identifier, date, result, owner, limitation, and follow-up. Distinguish automated checks, rendered review, expert review, owner approval, and representative-user evidence.

A production candidate may still have explicit exceptions. Each exception needs an affected scope, user consequence, mitigation, owner, and review date. Unowned critical gaps, fabricated proof, unknown asset rights, apparently live but unconfigured actions, or unrecoverable consequential flows block release.

This reference does not authorize deployment, DNS changes, tracking, publishing, external messages, payments, or production-data mutation. Obtain explicit authority for externally acting release steps and report anything not verified.
