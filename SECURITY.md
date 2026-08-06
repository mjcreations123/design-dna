# Security policy

## Scope

Security reports may cover the packaged maintainer tools, installer, release
process, evaluation harness, or instructions that could cause unsafe file,
credential, network, browser, or production behavior.

Design DNA does not claim to audit an application's authentication, payment
security, privacy compliance, backend, infrastructure, or deployment. Those
remain specialist reviews for the application being built.

## Reporting

Report suspected vulnerabilities privately through the support contact supplied
with the package or purchase. Do not place secrets, personal data, exploit code,
or confidential client material in a public issue.

This source package does not currently publish a security-reporting address or
hosted intake channel. That is an explicit commercial-release blocker: a seller
must configure and test a private reporting route in the transaction materials
before accepting payment. Do not invent an address or use a public issue for a
potential vulnerability.

Include:

- affected Design DNA version and host;
- operating system and relevant tool versions;
- minimal reproduction steps;
- expected and observed behavior;
- whether data, credentials, external systems, or production state were exposed;
- any temporary mitigation already applied.

Do not test against systems or data you do not own or have permission to assess.

## Handling

The maintainer should acknowledge receipt, reproduce the issue in an isolated
environment, classify impact and reach, prepare a regression test, and publish a
versioned fix or documented mitigation. Response times and support commitments
exist only when stated in a separate support agreement.

Never describe an unverified report as fixed. Retain the reproduction, fix,
verification evidence, affected versions, and disclosure decision.

Follow [Data handling and privacy](DATA_HANDLING.md) for screenshots,
evaluation artifacts, support bundles, and retention.
