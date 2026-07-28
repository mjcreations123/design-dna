# Design DNA

Design DNA is a cross-host website-design skill for work that should feel
specific, current, coherent, truthful, and fully implemented rather than
templated or vibe-coded. It combines positive art direction, system craft,
content truth, responsive and accessibility baselines, and rendered review. It
does not claim to prove human authorship or guarantee that AI involvement is
undetectable.

## One supported route per host

This personal distribution uses one direct skill route in each host:

| Host | Sole supported installed route |
| --- | --- |
| Codex | `C:\Users\motty\.agents\skills\design-dna` |
| Claude Code | `C:\Users\motty\.claude\skills\design-dna` |

The canonical source is `skills/design-dna` inside this package.
`.codex-plugin/plugin.json` is package-development metadata; it is not an
additional installed route. Do not install this package as a Codex plugin while
the direct Codex route exists, because that can expose a duplicate skill.

After an update, start a new Codex task or Claude conversation so the host
reloads skill discovery.

## How to use it

Use the host's exact skill invocation when you want to make it explicit:

| Host | Explicit request |
| --- | --- |
| Codex | `$design-dna Create a current, project-specific website from the supplied facts and assets. Implement the real interactions, then perform an adversarial rendered specificity review and revise every reproducible flaw.` |
| Claude Code | `/design-dna Create a current, project-specific website from the supplied facts and assets. Implement the real interactions, then perform an adversarial rendered specificity review and revise every reproducible flaw.` |

Both hosts may also discover it automatically from an ordinary request such as:

- “Build a polished website for this local business from the supplied facts.”
- “Redesign this dashboard without losing its working information density.”
- “Review this page for generic pattern clusters, weak hierarchy, unfinished
  behavior, accessibility problems, and production residue.”

Automatic discovery depends on the host and request. Use the explicit form when
you need deterministic selection, and check the compatibility matrix before
treating implicit discovery as verified.

The skill is a set of instructions and references, not a button or separate
website builder. The host still uses its available file, browser, rendering,
image, and test capabilities to do the work.

## Maintainer workflow

Maintainer tools require Python 3.10 or newer. Development validation also
requires the complete version-pinned direct and transitive dependency closure
in `maintainer/requirements-dev.txt`. The package supplies deterministic
`date`, `date-time`, and `uri` checks instead of silently relying on optional
schema-library extras.

From this package root:

```powershell
python -m pip install -r maintainer\requirements-dev.txt
python -B -m unittest discover -s maintainer\tests -p "test_*.py" -v
python -B maintainer\scripts\validate_evidence.py --plugin-root .
python -B maintainer\scripts\check_links.py .
python -B maintainer\scripts\audit_package.py --plugin-root .
python -B maintainer\scripts\attest_tests.py `
  --plugin-root . `
  --output maintainer\attestations\test-attestation.json
```

Compiled Python artifacts are intentionally omitted from content identities,
but they are forbidden in `skills/design-dna`, `maintainer/scripts`, and
`maintainer/tests`. Every executable maintainer entrypoint source-loads a
standard-library-only residue preflight before local imports; `common.py` is a
library-only module reached only after that gate. The preflight also refuses
package or untrusted `PYTHONPATH` entries that can shadow standard-library or
pinned release imports. Use `-B` as shown and keep
`PYTHONDONTWRITEBYTECODE=1` in automated test/release environments. Remove any
`__pycache__`, `.pyc`, or `.pyo` residue before development audit or release.

Synchronize the canonical runtime transactionally. The backup directories must
already exist and remain outside discovery roots:

```powershell
python -B maintainer\scripts\sync_skill.py `
  --source skills\design-dna `
  --target C:\Users\motty\.agents\skills\design-dna `
  --discovery-root C:\Users\motty\.agents\skills `
  --backup-root C:\Users\motty\.agents\skill-backups `
  --replace

python -B maintainer\scripts\sync_skill.py `
  --source skills\design-dna `
  --target C:\Users\motty\.claude\skills\design-dna `
  --discovery-root C:\Users\motty\.claude\skills `
  --backup-root C:\Users\motty\.claude\skill-backups `
  --replace
```

Then check the complete intended route set. Include every active host discovery
root that could contain another copy:

```powershell
python -B maintainer\scripts\detect_routes.py `
  --canonical skills\design-dna `
  --root C:\Users\motty\.agents\skills `
  --root C:\Users\motty\.codex\skills `
  --root C:\Users\motty\.codex\plugins\cache `
  --root C:\Users\motty\.claude\skills `
  --expected C:\Users\motty\.agents\skills\design-dna `
  --expected C:\Users\motty\.claude\skills\design-dna `
  --output maintainer\attestations\route-verification.json
```

Run the development audit during editing. The test attestation binds the exact
test, tooling, schema, pinned dependency closure, command, and output state. The route record
binds the complete discovery roots, intended routes, canonical hash, and
installed hashes. Update the compatibility matrix from those records, then
generate the release manifest only after the runtime, package metadata,
maintainer tooling, schemas, tests, fixtures, evidence, evaluation artifacts,
installed mirrors, compatibility records, and documentation are frozen.

After that source freeze, use this exact order:

```powershell
python -B maintainer\scripts\attest_tests.py `
  --plugin-root . `
  --output maintainer\attestations\test-attestation.json

# Synchronize both installed mirrors and create route-verification.json using
# the commands above, then update the compatibility matrix from those records.

python -B maintainer\scripts\build_manifest.py `
  --skill-root skills\design-dna `
  --output maintainer\release-manifest.json

python -B maintainer\scripts\build_manifest.py `
  --skill-root skills\design-dna `
  --output maintainer\release-manifest.json `
  --check

python -B maintainer\scripts\audit_package.py --plugin-root .
python -B maintainer\scripts\audit_package.py --plugin-root . --release
```

Do not regenerate an attestation or manifest after another source edit and call
it current; restart the ordered freeze sequence. `audit_package.py --release`
rechecks the machine records against current files and live routes. It is
intentionally stricter: missing controlled host behavior, retained rendered
evidence, or independent review attribution must remain a release failure
rather than being converted into a claim.
