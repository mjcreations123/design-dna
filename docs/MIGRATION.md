# Project-state migration

Design DNA project records are versioned separately from the package.

## Inspect first

Resolve the installed Design DNA skill root first. In the commands below,
replace `<DESIGN_DNA_SKILL_ROOT>` with that absolute directory and `<PROJECT>`
with the absolute project directory. Quoted absolute paths are intentional and
work from any current directory.

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT>" --check-state --json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT>" --migrate --dry-run --json
```

Review the selected project root, detected schema, affected records, unknown
legacy files, proposed backup location, and validation result.

## Migrate

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT>" --migrate --json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT>" --check-state --json
```

Migration stages the replacement, inventories retained legacy material, creates
a privacy-guarded backup, validates the new state, and restores the prior state
if installation or validation fails.

Project-state manifest schema 1 scalar assurance state migrates to
project-state manifest schema 2 cumulative
`assurance_profiles`. The migration report hash-binds the before/after state,
records the prior field and values, the target capabilities, every required
record, and the reason for the transition. Existing report history is carried
forward rather than replaced.

This does not replace the separate Markdown evidence-record schema. Its
current version remains 1; a record is not stale merely because its
frontmatter says `schema_version: 1`.

Asset-manifest schema 1 rows migrate to asset-manifest schema 2 without
manufacturing missing approval, exposure, type, disclosure, source-binding, or
generated-media evidence. Each migrated row becomes internal-only and
review-required, the unresolved fields remain explicit, the exact source is
preserved in the privacy-guarded backup, and the migration report binds the
source and migrated manifest hashes. `--check-state` can then pass while
`--check-ready` correctly blocks until an accountable reviewer resolves the
row. This is readiness for the records listed in `state.json`; migration does
not add or validate otherwise unlisted workflow, specialist, production, or
launch evidence.

When a formerly complete record does not satisfy the current persisted
assurance capabilities or its exact completion binding, migration changes that
record to `draft` instead of grandfathering stale evidence. The exact
pre-migration record remains in the backup, and `migration-report.json`
records its body hash, prior binding ID, path and hash, completion owner and
date, limitations, and the reasons that completion was withdrawn. Refill the
missing evidence, bind the current artifact, and mark the record complete
again; do not edit the report to conceal the downgrade.

Do not discard the backup until exploration, direction, claims, assets,
validation, handoff, review history, and privacy classifications have been
inspected by the accountable owner.

## Complete a record

A generated exploration, direction, direction-proof, visual-review, claims,
user-validation, or handoff record begins as a draft. Mark it complete only
after replacing the applicable template prompts with substantive evidence and
binding it to an independent build or artifact:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT>" --mark-complete visual-review --binding-kind build --binding-id "<BUILD_ID>" --binding-path "<RELATIVE_ARTIFACT_PATH>" --completion-owner "<OWNER>" --limitations "No known limitations within the reviewed scope." --json
```

The tool calculates content and artifact hashes. A later edit invalidates the
completion binding. Use
`python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT>" --mark-draft visual-review --json`
before revising a completed record.

Never place secrets, participant data, or confidential client material in an
unapproved committed record.
