# Owner-pattern contract gate

Use this only when the applicable owner record activates
`~/.design-dna/owner-pattern-contract.json`. The contract is accountable-owner
governance, not portable Design DNA taste guidance.

## What the contract closes

Each contract item must name a **failed relationship**. For example,
“numbering without sequence” is a failure; numbering itself remains available
for a real sequence. “Depth without information” is a failure; depth itself
remains available when it communicates containment, state, interaction,
material, or space.

This distinction makes the rule decisive without creating an inverse house
style. There is no aesthetic exception to a failure state: if an ingredient has
a real project role, the named failure is absent. If its only defense is that
the producer intended it, the failure remains open.

The contract does not identify who or what made a website. It proves only that
the owner-named visible failure relationships were reviewed and closed on the
bound candidate.

## Activate it

For a project in the contract's scope, initialize Design DNA with the contract
trigger and any separately applicable owner recurrence trigger. In an MJ's
Studio unrelated public build, the owner record requires both:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT_ROOT>" --profile showcase --trigger owner-recurrence-requirement --trigger owner-pattern-contract
```

If state already exists, use `--add-trigger` for each missing trigger. Do not
edit only one of the paired Project Contrast or Direction Challenge records.

Create the review once:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/owner_pattern_audit.py" "<PROJECT_ROOT>" --init-review
```

The initializer refuses to overwrite an existing review. A changed owner
contract invalidates its old SHA-256 binding; review the new contract and
reconcile the project record rather than silently refreshing the digest.

## Direction gate

Before broad implementation:

1. Fill the exact project identity and scope.
2. Bind the project direction record by path and SHA-256.
3. For every contract ID, set `disposition` to `controlled` and record:
   - the direction decision;
   - how it prevents the precise failure;
   - the current project basis.
4. Set the direction lane to `passed` and the top record to
   `direction-ready`.
5. Run `owner_pattern_audit.py <PROJECT_ROOT> --phase prebuild`, then the normal
   `init_project_state.py --check-prebuild` gate.

`pending`, `blocked`, omitted, duplicated, reordered, placeholder, or
contract-drifted items fail. A prose promise elsewhere does not substitute for
the record.

## Final gate

On the exact final route family:

1. Complete the ordinary rendered visual review.
2. Bind its file and SHA-256 plus the identical build ID in the owner-pattern
   review.
3. For every contract ID, inspect the relevant route family and set the final
   disposition to `absent` only when the precise failure relationship is absent.
4. Record a concrete observation and bind exactly one wide and one narrow
   full-page PNG with its project-relative path, SHA-256, CSS width, route or
   state, capture mode, and matching final build ID. The two captures must have
   different paths and bytes. Reuse of the same verified pair across several
   items is valid only when those pixels actually expose each relationship.
5. Set the final lane to `passed` and the top record to `reviewed`.
6. Run `owner_pattern_audit.py <PROJECT_ROOT> --phase ready`, then the normal
   `init_project_state.py --check-ready` gate.

The auditor byte-verifies the contract, review, direction evidence, visual
review, and PNG evidence. It validates PNG structure, checks declared wide and
narrow conditions, rejects wide/narrow evidence reuse or build drift, and
requires every contract item exactly once. It cannot decide aesthetics from
source code; the bound rendered observation remains accountable human or agent
review evidence and must be described honestly.
