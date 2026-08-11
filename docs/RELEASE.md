# Release procedure

## 1. Freeze source

- finish runtime, tooling, schema, evidence, fixture, documentation, and policy
  changes;
- remove compiled caches and temporary artifacts;
- confirm version consistency across both plugin manifests, runtime release,
  compatibility records, and changelog;
- confirm every dependency and evidence review date.

## 2. Validate

Run the complete test suite on every supported operating system and Python
version. Run evidence validation, link checking, plugin validation, project
state regressions, scanner adversarial regressions, and rendered-harness smoke
tests.

The strict audit derives the required release matrix from the `test` job in
`.github/workflows/ci.yml` and matches it one-for-one to Python CI contract
entries in `maintainer/compatibility/matrix.yml`. Every derived OS/Python entry
must have `package_audit` and `unit_tests` marked `passed` and backed by a valid
retained CI import. A local pass does not satisfy a remote matrix entry.

Skipped release tests require a current named waiver, exact test and environment
identity, rationale, expiry, and compensating evidence.

Waivers conform to
`maintainer/schemas/test-skip-waivers.schema.json`, bind the exact attested
input hashes, expire within 90 days, and live below
`maintainer/attestations/skip-waivers/`. Their hash-verified compensating
evidence lives below `maintainer/attestations/skip-evidence/`. Supply an
approved record only when a skip actually occurs:

```text
python -B maintainer/scripts/attest_tests.py --plugin-root . --skip-waiver-file maintainer/attestations/skip-waivers/APPROVED.json --output maintainer/attestations/test-attestation.json
```

An unwaived skip, stale extra waiver, environment mismatch, source change,
expired approval, or changed evidence is a strict release failure. Prefer
making a feasible test run on the supported platform; a waiver is not a routine
substitute.

## 3. Evaluate

Execute the controlled host/model matrix and independent rendered reviews.
Diagnostic builds cannot be promoted by changing their label. Every promoted
result must satisfy the current schemas and evaluation contract.

## 4. Build, attest, and synchronize

After the final runtime, test, tooling, schema, requirement, and workflow edit:

### Prepare the reviewable candidate

1. create the local test attestation;
2. create and check the external Codex Plugin Creator validation attestation;
3. create and check the isolated Codex/Claude installer-lifecycle attestation;
4. synchronize each intended direct installation transactionally;
5. verify the declared global filesystem discovery roots and installed hashes;
6. generate and check the current SBOM;
7. generate and check a provisional current release manifest against the
   actual previous release identity;
8. run the development audit;
9. commit that exact reviewable candidate;
10. run the remote OS/Python matrix on the candidate commit.

The checked-in provisional SBOM and manifest are required before candidate CI
because the CI development audit validates both. They establish a clean
candidate input; they are not the final release identity.

### Promote evidence and finalize

1. import each authenticated successful matrix artifact as described below;
2. update only the matching CI compatibility statuses and import timestamps;
3. complete the controlled host/model evaluations and independent rendered
   reviews required by the release contract;
4. update host compatibility status only from current attributable records;
5. rerun any local attestation whose bound input changed;
6. regenerate or check the SBOM after any bound runtime, manifest, license, or
   dependency change;
7. generate and check the **final** release manifest after all retained
   evidence, reviews, compatibility updates, and distributed documentation are
   in place;
8. run the development and strict release audits.

The CI import files and their matching compatibility status changes are
evidence-only edits expected after the candidate run; they must be present
before the final release manifest is generated. The final manifest replaces
the provisional candidate manifest. Any later edit to the attested runtime,
tests, tooling, schemas, requirements, or workflow invalidates the retained CI
binding and restarts this sequence.

### Exact pre-CI local sequence

Run these single-line commands from the frozen package root. Replace `<HOME>`
with the absolute current home directory, using the platform's normal path
separators. On Windows PowerShell, use `npm.cmd` in place of `npm` if script
execution policy blocks `npm.ps1`. A fresh Linux runner may add `--with-deps`
to the Playwright install command:

The copy-ready route proof below intentionally matches the distributed
compatibility contract: Codex at `<HOME>/.agents` and Claude Code at
`<HOME>/.claude`. Before running it, confirm that `CLAUDE_CONFIG_DIR` is unset
or resolves to `<HOME>/.claude`. `manage_install.py` supports a different
Claude configuration root, but do not let the release command silently verify
the default root when the actual install went elsewhere. For a custom root,
replace both Claude `--root` values and the Claude `--expected` value with the
effective configuration root for a local diagnostic run. Do not overwrite the
distributed route attestation with that diagnostic: the current portable
schema and compatibility contract encode only home-relative default roots.
Record the custom-root limitation, or extend and review that contract before
claiming the custom route is release-qualified.

```text
python -m pip install --disable-pip-version-check --require-hashes -r maintainer/requirements-dev.lock
npm --prefix maintainer ci --ignore-scripts --no-audit --no-fund
npm --prefix maintainer exec -- playwright install chromium
python -B maintainer/scripts/build_sbom.py --plugin-root . --output maintainer/sbom.spdx.json
python -B maintainer/scripts/build_sbom.py --plugin-root . --output maintainer/sbom.spdx.json --check
python -B maintainer/scripts/attest_tests.py --plugin-root . --output maintainer/attestations/test-attestation.json
python -B maintainer/scripts/attest_codex_plugin.py --plugin-root . --validator "<ABSOLUTE_PLUGIN_CREATOR_VALIDATOR>" --output maintainer/attestations/codex-plugin-validation.json
python -B maintainer/scripts/attest_codex_plugin.py --plugin-root . --validator "<ABSOLUTE_PLUGIN_CREATOR_VALIDATOR>" --output maintainer/attestations/codex-plugin-validation.json --check
python -B maintainer/scripts/attest_install_lifecycle.py --plugin-root . --output maintainer/attestations/install-lifecycle.json
python -B maintainer/scripts/attest_install_lifecycle.py --plugin-root . --output maintainer/attestations/install-lifecycle.json --check
python -B maintainer/scripts/manage_install.py recover --host all --dry-run
python -B maintainer/scripts/manage_install.py recover --host all
python -B maintainer/scripts/manage_install.py sync --host all
python -B maintainer/scripts/manage_install.py doctor --host all
python -B maintainer/scripts/detect_routes.py --canonical skills/design-dna --home "<HOME>" --root "<HOME>/.agents/skills" --root "<HOME>/.claude/skills" --root "<HOME>/.claude/plugins/cache" --root "<HOME>/.codex/plugins/cache" --root "<HOME>/.codex/skills" --expected "<HOME>/.agents/skills/design-dna" --expected "<HOME>/.claude/skills/design-dna" --output maintainer/attestations/route-verification.json
python -B maintainer/scripts/build_manifest.py --skill-root skills/design-dna --output maintainer/release-manifest.json --previous maintainer/releases/v3.3.0.manifest-identity.json
python -B maintainer/scripts/build_manifest.py --skill-root skills/design-dna --output maintainer/release-manifest.json --previous maintainer/releases/v3.3.0.manifest-identity.json --check
python -B maintainer/scripts/audit_package.py --plugin-root . --home "<HOME>" --codex-validator "<ABSOLUTE_PLUGIN_CREATOR_VALIDATOR>"
```

The SBOM is generated before the test attestation because release-identity
tests fail closed when its runtime or version binding is stale. Promote the
test attestation only after that exact run passes, then update the local
compatibility record from the promoted evidence. Keep package, install, host,
and remote-matrix checks pending until their own evidence exists. Build the
manifest last because it binds those promoted artifacts and compatibility
claims; rebuild it after any later proof changes.

Commit this passing candidate, run the remote matrix, retain and import the
authenticated evidence, complete the required evaluation records, and update
compatibility only from those records.

### Exact post-CI finalization

After every promoted evidence and compatibility edit is complete:

```text
python -B maintainer/scripts/build_sbom.py --plugin-root . --output maintainer/sbom.spdx.json --check
python -B maintainer/scripts/build_manifest.py --skill-root skills/design-dna --output maintainer/release-manifest.json --previous maintainer/releases/v3.3.0.manifest-identity.json
python -B maintainer/scripts/build_manifest.py --skill-root skills/design-dna --output maintainer/release-manifest.json --previous maintainer/releases/v3.3.0.manifest-identity.json --check
python -B maintainer/scripts/audit_package.py --plugin-root . --home "<HOME>" --codex-validator "<ABSOLUTE_PLUGIN_CREATOR_VALIDATOR>"
python -B maintainer/scripts/audit_package.py --plugin-root . --home "<HOME>" --codex-validator "<ABSOLUTE_PLUGIN_CREATOR_VALIDATOR>" --release
```

The actual previous promoted release identity remains
`maintainer/releases/v3.3.0.manifest-identity.json` because the later
candidates were not promoted. Change that copy-ready path only after a newer
version has genuinely completed promotion and its identity is retained.

The test proof records the current interpreter with a portable token and a
live-checked executable hash. The route proof stores only
`skills/design-dna` and `~/...` identities; `--home` is the explicit root used
both when creating and when rechecking that proof. The release audit rejects a
machine-local absolute path in distributed attestation records.

The Codex static proof runs the external validator from the Plugin Creator
system-skill route only when its path, byte count, and SHA-256 match the
publisher-reviewed pin in
`maintainer/trust/codex-plugin-validator.json`. It executes the already-read
validator bytes with Python `-I -B -X utf8` against private snapshots of the
bound plugin surface and pure-Python PyYAML source. It records the validator, interpreter,
dependency-source, and input identities, but retains no stdout or stderr
content or output hashes. Strict audit requires the same explicit validator and
replays the exact success contract.

The trust pin is a Design DNA publisher review, not an OpenAI signature or
vendor endorsement. A mismatch must never be “fixed” by copying the newly
observed hash. Obtain the validator revision through the trusted Codex update
route, diff and review the source, confirm its ingestion behavior, then
deliberately update the hash, byte count, review dates, review basis, and trust
boundary. Re-run every proof after that edit. New evidence requires a pin whose
review window includes the current date; an immutable historical release can
still be replayed with `attest_codex_plugin.py --check` when its attestation
timestamp fell inside the pin's original review window. That historical replay
does not satisfy a current `audit_package.py` release gate: current package
audits also require the pin review window to include today.

## 5. Commit, tag, and package

The remote matrix runs on a reviewable candidate commit. After importing its
evidence and completing the final manifest, commit the complete frozen release,
create an annotated version tag, and build the archive from that exact final
commit. Produce SHA-256 checksums, make the three descriptor/archive/checksum
detached signatures named by `release-package.json`, and separately verify any
claimed signed tag with the owner's established release key. Never generate a
disposable key merely to claim signing.

The release archive, checksum, signature, SBOM, changelog, compatibility matrix,
and evaluation summary must identify the same version and content.

After the frozen commit has an exact annotated `vVERSION` tag, create and
recheck the deterministic unsigned candidate bundle:

```text
python -B maintainer/scripts/package_release.py --plugin-root . --output-dir "<ABSOLUTE_RELEASE_OUTPUT>" --ref "vVERSION" --previous-manifest "<ABSOLUTE_PREVIOUS_MANIFEST_IDENTITY>" --home "<HOME>" --codex-validator "<ABSOLUTE_PLUGIN_CREATOR_VALIDATOR>" --release
python -B maintainer/scripts/package_release.py --plugin-root . --output-dir "<ABSOLUTE_RELEASE_OUTPUT>" --ref "vVERSION" --previous-manifest "<ABSOLUTE_PREVIOUS_MANIFEST_IDENTITY>" --home "<HOME>" --codex-validator "<ABSOLUTE_PLUGIN_CREATOR_VALIDATOR>" --release --check
```

`package_release.py` produces the bytes to sign; it does not turn that candidate
into an authenticated release.

### Detached-signature proof

The package builder does not generate a key or signature. After it creates the
bundle, the owner must use an already-established release key to make armored
detached signatures over all three files:

- `release-package.json` — the signed descriptor that binds version, ref,
  commit, release identity, archive hash and size, manifest, and SBOM;
- the `.zip` archive;
- the `.zip.sha256` checksum file.

The descriptor signature is mandatory. Signing only the archive and checksum
would leave the descriptor's version, commit, and release identity
unauthenticated.

Verify and attest the three signatures with the full primary fingerprint
obtained through an independent trusted channel:

```text
python -B maintainer/scripts/attest_signatures.py --plugin-root . --bundle-dir "<ABSOLUTE_BUNDLE_DIRECTORY>" --trusted-fingerprint "<FULL_PRIMARY_FINGERPRINT>" --gpg "<ABSOLUTE_EXTERNAL_GPG_EXECUTABLE>" --output "<ABSOLUTE_BUNDLE_DIRECTORY>/release-signature-attestation.json"
python -B maintainer/scripts/attest_signatures.py --plugin-root . --bundle-dir "<ABSOLUTE_BUNDLE_DIRECTORY>" --trusted-fingerprint "<FULL_PRIMARY_FINGERPRINT>" --gpg "<ABSOLUTE_EXTERNAL_GPG_EXECUTABLE>" --output "<ABSOLUTE_BUNDLE_DIRECTORY>/release-signature-attestation.json" --check
```

The verifier requires an absolute, operator-supplied GnuPG executable outside
the repository and release bundle, hashes that executable into the attestation,
disables automatic key retrieval, rejects short key IDs as the trust root, and
parses GnuPG's machine status channel fail-closed. The fingerprint and public
key must still be distributed independently of the release bundle; putting the
trust root only inside the material it authenticates would be circular.

This detached-signature attestation does not verify the Git tag signature.
If the release claims a signed tag, verify that annotated tag cryptographically
against the same independently established primary fingerprint as a separate
release gate. Do not substitute “annotated tag exists” for signature
verification.

No checked-in attestation, `.asc` file, key, or fingerprint is evidence until it
exists and passes live verification. If GnuPG, the established key, the three
signatures, or independent fingerprint distribution is absent, publish the
release as unsigned/unverified.

### Promote retained CI evidence

The workflow retains each OS/Python test attestation and clean development
package-audit JSON together for 30 days. It also retains the separate
rendered-browser log. Retention does not automatically promote any
compatibility status.

Before changing an OS/Python compatibility status from
`declared_not_observed`, an accountable maintainer must:

1. download the artifact through the authenticated repository workflow and
   preserve the original ZIP bytes;
2. record the repository, workflow bytes, run ID and attempt, commit SHA, job
   window and conclusion, matrix identity, artifact ID, authenticated-download
   assertion, and service-reported SHA-256 digest;
3. preserve byte-identical extracted `design-dna-test-attestation.json` and
   `design-dna-package-audit.json` files;
4. create
   `maintainer/compatibility/archive/ci-runs/<environment-id>/import.json`
   conforming to `maintainer/schemas/ci-run-import.schema.json`;
5. cite the workflow, import record, retained ZIP, and both extracted evidence
   files from the matching environment record;
6. change only the two verified checks to `passed`, set `checked_at` equal to
   the import timestamp, regenerate the final release manifest, and rerun the
   audit.

The verifier recomputes the workflow, artifact, and extracted-file hashes,
requires the service digest to equal the retained ZIP digest, checks the exact
OS/Python identity and successful job window, revalidates the embedded test
attestation against the current attested inputs, and requires a clean package
audit. Imported remote attestations must record zero skips because the exact
remote waiver environment cannot be replayed locally. Strict release remains
blocked until every workflow OS/Python pair has both verified passes. The
current rendered-browser log is diagnostic evidence, not a schema-qualified
`rendered_review` promotion record.

A passing badge, screenshot, copied log, artifact filename, or hand-authored
status alone is not immutable run evidence. Do not change the current
`declared_not_observed` statuses until the corresponding external runs and
retained records actually exist.

## 6. Publish

Publish only through approved distribution channels. Confirm install, update,
rollback, and removal from a clean account before announcing availability.
State supported hosts/models and remaining limitations exactly as verified.
