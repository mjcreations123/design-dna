# Review data handling

Apply this whenever inspection, screenshots, browser diagnostics, evaluation,
or support artifacts could contain non-public material.

## Classify before capture

- Public: published pages and openly licensed assets.
- Internal: unreleased layouts, ordinary project code, and synthetic test data.
- Confidential: client strategy, private previews, proprietary assets, or
  non-public URLs.
- Restricted: credentials, authentication material, payment data, health data,
  government identifiers, private communications, or data about children.

Do not put restricted material into prompts, fixtures, screenshots, JSON
reports, or support bundles. Replace real accounts, orders, messages, payments,
and people with synthetic fixtures. For confidential material, obtain the
accountable owner's approval, define recipients and a deletion date, and keep
the work in an approved local environment.

## Browser and rendered review

- Prefer a logged-out or dedicated test profile.
- Inspect only targets the operator is authorized to access.
- Treat screenshots, accessibility names, console messages, URLs, and network
  diagnostics as potentially confidential.
- Never assume automated redaction knows every application-specific secret.
- Review each artifact manually before sharing it.

## Minimize and close

Capture only what the decision requires. Remove credentials, query strings,
personal data, confidential paths, and client material before sharing. Record
the retention owner and date, then remove expired outputs from workspaces,
backups, support packages, and shared storage.

This is an operational boundary, not legal advice or a privacy certification.
Escalate regulated data, consent, retention, deletion, or incident questions to
the accountable privacy, legal, security, or data owner.
