# Data handling and privacy

Design DNA runs locally and includes no telemetry, analytics beacon, hosted
service, or automatic upload. That does not make every input safe to use.
Rendered review, evaluation, and support artifacts can capture confidential
source code, unreleased copy, client assets, page text, URLs, console messages,
screenshots, accessibility names, and environment-derived output.

## Data classes

| Class | Examples | Default handling |
| --- | --- | --- |
| Public | Published pages, public evidence sources, openly licensed assets | May be used in local review and retained with source and license records. |
| Internal | Unreleased layouts, ordinary project code, internal test data | Keep within the approved project and review team. Remove when the review record is no longer needed. |
| Confidential | Client strategy, private previews, proprietary assets, non-public URLs | Obtain the accountable owner's approval before capture. Use an isolated local workspace, sanitize reports, and set a written retention date. |
| Restricted | Credentials, authentication material, payment data, health data, government identifiers, private communications, data about children | Do not put it into Design DNA prompts, fixtures, screenshots, reports, or support packages. Use a specialist-controlled test environment with synthetic data. |

## Tool behavior

- The static scanner reads project files locally and reports bounded excerpts.
  Review those excerpts before sharing the report.
- Font audit reads font declarations and local font metadata. It must not be
  treated as a license determination.
- Rendered review can take screenshots and collect browser-visible diagnostics.
  Use only approved local or public targets. Its sanitization is defense in
  depth, not a guarantee that application-specific secrets are impossible.
- The evaluation harness passes only explicitly named environment variables.
  It redacts exact values from captured text and scans temporary run artifacts
  for exact UTF-8, UTF-16, Base64, and URL-safe Base64 forms. Detection or an
  incomplete scan blocks promotion and retention. Use short-lived,
  least-privilege credentials because transformed or indirectly disclosed
  values may evade exact matching.
- Online evidence and link checks are opt-in. Requests are restricted to exact
  allowlisted hosts and diagnostics omit credentials, queries, and source URL
  paths.
- Checked-in test attestations identify the active interpreter by a portable
  token plus its executable-byte SHA-256, not by a local executable path.
  Known workspace, home, temporary, and interpreter paths are redacted from
  retained unittest output before its digest is calculated.
- Checked-in route verification stores the canonical package path as
  `skills/design-dna` and every discovery or installed route as a `~/...`
  identity. The release audit rehydrates those labels against an explicitly
  selected home and rejects local absolute paths in retained proof records.
  Ordinary HTTP and HTTPS evidence URLs are not treated as local paths.
- Codex plugin validation runs the publisher-pinned validator bytes under
  Python isolation with a minimal child environment and private snapshots of
  the distributable plugin surface and pure-Python PyYAML source. No validator
  stdout, stderr, output length, or output hash is retained; only the exact
  success-contract booleans and bound input identities enter the attestation.
  The publisher pin is not an OpenAI signature.

## Before capture

1. Confirm that the operator is authorized to inspect the project and target.
2. Replace real people, accounts, orders, payments, messages, and credentials
   with synthetic fixtures.
3. Decide who may receive the output, where it may be stored, and the deletion
   date.
4. Use a dedicated browser profile or logged-out session unless authenticated
   behavior is explicitly in scope and approved.
5. Check image, font, copy, and dataset rights separately from privacy.

## Before sharing

Open every JSON report, Markdown review, screenshot, archive, and console log.
Remove confidential paths, non-public hostnames, query strings, identifiers,
personal data, and client material. Hashes can still be correlatable; do not
publish hashes of restricted or low-entropy secrets.

Portable release records reduce workstation disclosure; they do not sanitize
arbitrary project content. Review retained test output even when automatic path
redaction passed.

## Retention and deletion

Design DNA does not schedule deletion for the operator. Keep the minimum
evidence needed for the stated review or release claim, record a retention
owner and date, and remove expired artifacts from workspaces, backups, support
packages, and shared storage. A backup or source-control history may preserve a
copy after ordinary deletion; account for that before capture.

## Commercial deployment gate

Before providing Design DNA to another organization, the seller must identify
the data controller or accountable owner, approved storage and subprocessors,
retention and deletion rules, incident contact, cross-border restrictions, and
any required agreement or notice. This document is an operational boundary, not
legal advice or a privacy certification.
