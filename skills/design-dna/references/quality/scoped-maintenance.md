# Scoped maintenance of an existing site

An existing site has existing history. Do not manufacture a code-free baseline
or delete the working site to satisfy a new-construction check. The maintenance
workflow records that history as unverified while authorizing a precisely
scoped, source-bound change.

First revalidate the source observations, current V2 component map, and required
direction/owner records. Capture a complete current route/state/wide+narrow
component census with the packaged scanner, outside any served directory. Its
implementation snapshot must match the current project tree; a scan from before
an unreviewed source edit is stale.

Run the baseline scan from the project root with a new unique output directory:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/scan_build_components.mjs" --manifest .design-dna/route-manifest.json --build-id "<EXISTING_BUILD_ID>" --run-id "<UNIQUE_BASELINE_RUN_ID>" --out ".design-dna/evidence/maintenance-baselines/<UNIQUE_BASELINE_RUN_ID>/component-census.json"
```

Bind that exact output in `baseline_census`. Never use the mutable canonical
`.design-dna/evidence/component-census.json`: the next gate writes there. Keep
the baseline's generated frame/video directories alongside it, with the
generator's original paths and bytes unchanged.

Create a proposed V2 map as a separate file. Preserve source evidence for both
the current and proposed mappings. Use immutable content-transfer versions and
new asset IDs when material changes; replacing old evidence destroys the
baseline. The plan names exact added, modified, and removed files and the
affected source-bound component IDs. It cannot add routes silently.

For an asset replacement, prepare the new source-bound asset with a new ID and
filename before capturing the baseline. Keep old and new rows in one frozen
`assets.yml`, refresh both maps' binding to that exact manifest, and capture
the old site's census again. The proposed map then selects the new asset.
Retain the old asset bytes at their bound paths; overwriting/deleting them or
editing `assets.yml` after the baseline would invalidate the historical map.
Generated assets still require the source-plan authorization before generation.

Use [maintenance-plan-template.json](../../templates/maintenance-plan-template.json),
then freeze the plan before editing visible source:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT_ROOT>" --begin-maintenance .design-dna/maintenance-plan.json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT_ROOT>" --check-construction
```

The baseline is create-only. It retains both maps and the old scan, records the
existing tree, and activates the planned map with its separate maintenance
authorization. The check rejects changes outside the planned file/component
scope. Neither command is owner approval or a claim that old code was written
after new research.

After the exact planned change, run:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/gate.py" --project "<PROJECT_ROOT>" --build-id "<IMMUTABLE_MAINTENANCE_BUILD_ID>" --route-manifest .design-dna/route-manifest.json --phase maintenance
```

This phase runs the full current source, census, style, structure, mechanism,
signature, and rendered-QA checks. A new complete census must bind the exact
changed tree and map. It uses the audited maintenance baseline in place of
invented fresh-construction history and writes `maintenance-gate.json`, leaving
the ordinary final gate untouched. A pass verifies the scoped change only;
new-site approval, deployment, live status, and owner acceptance remain separate.
An incomplete plan, stale scan, or out-of-scope change leaves maintenance blocked.
