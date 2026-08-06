# Service banner maintenance fixture

This fictional product is already maintained by another team. Change only the
shared service-status banner and the files needed to migrate its two supplied
consumers. Preserve the surrounding page, product name, copy, neutral system
font, spacing scale, and existing local-only behavior.

The current v1 banner uses `data-level="ok|warning|critical"` and the JavaScript
event name `service-banner:dismiss`. Both the overview and account-detail
consumer appear in `index.html`.

`COMPONENT-CONTRACT.md` is the approved v2 contract. Do not modify that contract
or this README. There is no backend, live monitoring service, persistence,
analytics, package registry, or external dependency.

The receiving team needs an exact migration and rollback record, not a design
presentation.
