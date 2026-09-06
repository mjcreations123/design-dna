"""Connect scoped existing-site maintenance to the complete packaged validators."""
from __future__ import annotations

import json
from pathlib import Path


def is_maintenance_authorization(value: object) -> bool:
    return isinstance(value, dict) and str(value.get("journal_id", "")).startswith("legacy-")


def _module(validator):
    return validator.load_bundled_source_module(
        "_design_dna_legacy_maintenance", Path(__file__).with_name("legacy_maintenance.py")
    )


def _context(project: Path, validator, scan_paths: list[Path], selection_mapping: dict):
    manifest_path = project / ".design-dna" / "route-manifest.json"
    dossier_path = project / ".design-dna" / "reference-dossier.md"
    manifest = validator.read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("Maintenance requires the authoritative route manifest.")
    failures = validator.route_manifest_payload_failures(manifest)
    failures.extend(validator.route_manifest_reference_failures(manifest, project=project))
    failures.extend(validator.selected_cohort_failures(project, mapping_payload=selection_mapping))
    # These are the direction requirements before a scoped change. A fresh
    # site's earlier first-screen record is intentionally not fabricated.
    failures.extend(validator.prebuild_failures(project, require_first_screen=False, require_construction=False))
    failures.extend(validator.owner_pattern_contract_failures(project, phase="prebuild"))
    failures.extend(validator.owner_recurrence_integration_failures(project / ".design-dna", require_resolved=True))
    if failures:
        raise ValueError("Maintenance prerequisites: " + " | ".join(failures))
    body = dossier_path.read_text(encoding="utf-8")
    section = validator.markdown_sections(body).get("Route manifest", "")
    proof_identity = validator.markdown_label_value(section, "First-screen proof build ID and primary route key") or ""

    def validate_mapping(payload):
        return validator.visible_decision_source_manifest_failures(
            payload, project=project, route_manifest=manifest,
            route_manifest_path=manifest_path, proof_identity=proof_identity,
            require_construction_v2=True, allow_pending_construction_authorization=True,
        )

    def validate_scan(scan, mapping):
        matching_path = next((file for file in scan_paths if file.is_file() and validator.read_json(file) == scan), None)
        if matching_path is None:
            return ["Maintenance census is not one of the exact bound generated records."]
        failures = validator.packaged_runtime_record_failures(scan, tool="scan_build_components.mjs", require_pass=True)
        failures.extend(validator.census_runtime_failures(
            scan, expected_routes=manifest["routes"], expected_viewports=manifest["viewports"],
            first_screen=False, record_path=matching_path, project=project,
            decision_manifest_snapshot=mapping,
            decision_manifest_snapshot_sha256=scan.get("visible_decision_reconciliation", {}).get("manifest_sha256"),
        ))
        return failures

    return manifest_path, dossier_path, validate_mapping, validate_scan


def begin(project: Path, plan_path: Path, validator) -> dict:
    """Freeze the audited old site and proposed source map, then activate that map."""
    helper = _module(validator)
    plan_path = helper._contained(project, plan_path)
    plan = validator.read_json(plan_path)
    if not isinstance(plan, dict) or set(plan) != {"schema_version", "planned_source_map", "baseline_census", "planned_changes"} or plan.get("schema_version") != 1:
        raise ValueError("Maintenance plan needs schema_version 1, planned_source_map, baseline_census and planned_changes.")
    proposed = helper._contained(project, plan["planned_source_map"])
    baseline = helper.baseline_scan_path(project, plan["baseline_census"])
    planned = validator.read_json(proposed)
    active_path = project / ".design-dna" / "visible-decision-sources.json"
    dossier_path = project / ".design-dna" / "reference-dossier.md"
    validator._construction_activation_bytes(project, visible_path=active_path, dossier_path=dossier_path, payload=planned)
    current = validator.read_json(active_path)
    current_auth = current.get("construction_authorization") if isinstance(current, dict) else None
    if is_maintenance_authorization(current_auth) and helper.mapping_core(current) == helper.mapping_core(planned):
        changes, _digest = validator._construction_activation_bytes(project, visible_path=active_path, dossier_path=dossier_path, payload=current)
        if changes[1][1] != changes[1][2]:
            entry = helper._load(project, current_auth["entry_path"])
            if sorted(plan["planned_changes"], key=lambda row: row["path"]) != entry.get("planned_changes"):
                raise ValueError("Interrupted maintenance activation belongs to another scoped change plan; recover its original plan first.")
            failures = check(project, current, validator)
            if failures:
                raise ValueError("Interrupted maintenance authority cannot be recovered: " + " | ".join(failures))
            validator.activate_construction_binding(project, visible_path=active_path, dossier_path=dossier_path, payload=current)
            return {"action": "recovered-scoped-maintenance", "authorization": current_auth,
                    "history_status": "existing-history-unverified", "public_readiness": False}
    _manifest, _dossier, mapping_validator, scan_validator = _context(project, validator, [baseline], planned)
    # A caught write failure may leave only the create-only baseline. Reuse
    # that exact plan/scan/history instead of fabricating another beginning.
    pending = []
    journal_root = project / ".design-dna" / "evidence" / "legacy-maintenance"
    if journal_root.exists():
        validator.assert_no_reparse_ancestors(journal_root, stop=project)
        for file in sorted(journal_root.glob("legacy-*.json")):
            entry = helper._load(project, file)
            if (entry.get("baseline_source_map") == current
                and entry.get("planned_core_sha256") == helper._digest(helper.mapping_core(planned))
                and entry.get("baseline_scan") == helper._binding(project, baseline)
                and entry.get("planned_changes") == sorted(plan["planned_changes"], key=lambda row: row["path"])):
                authorization = {"journal_id": entry.get("journal_id"), "entry_path": file.relative_to(project).as_posix(),
                                 "entry_sha256": helper._binding(project, file)["sha256"]}
                candidate = {**planned, "construction_authorization": authorization}
                failures = helper.legacy_maintenance_failures(project, authorization, candidate,
                    validate_mapping=mapping_validator, validate_scan=scan_validator)
                if failures:
                    raise ValueError("Interrupted maintenance baseline cannot recover: " + " | ".join(failures))
                pending.append((authorization, candidate))
    if len(pending) > 1:
        raise ValueError("Multiple matching interrupted maintenance baselines exist; resolve the exact intended authority before activation.")
    if pending:
        authorization, candidate = pending[0]
        validator.activate_construction_binding(project, visible_path=active_path, dossier_path=dossier_path, payload=candidate)
        return {"action": "recovered-scoped-maintenance", "authorization": authorization,
                "history_status": "existing-history-unverified", "public_readiness": False}
    authorization = helper.begin_legacy_maintenance(
        project, planned_source_map=proposed, baseline_scan=baseline,
        planned_changes=plan["planned_changes"], validate_mapping=mapping_validator, validate_scan=scan_validator,
    )
    planned["construction_authorization"] = authorization
    # The immutable baseline already contains both old and proposed maps.
    # Atomic replacement cannot erase the historical source intent.
    validator.activate_construction_binding(project, visible_path=active_path, dossier_path=dossier_path, payload=planned)
    return {"action": "began-scoped-maintenance", "authorization": authorization,
            "history_status": "existing-history-unverified", "public_readiness": False}


def check(project: Path, payload: dict, validator, *, current_scan: Path | None = None, final: bool = False) -> list[str]:
    try:
        helper = _module(validator)
        auth = payload.get("construction_authorization")
        if not is_maintenance_authorization(auth):
            return ["Scoped maintenance requires an explicit existing-site baseline authorization."]
        entry = helper._load(project, auth["entry_path"])
        baseline = helper._contained(project, entry["baseline_scan"]["path"])
        scans = [baseline]
        if current_scan is not None:
            current_scan = helper._contained(project, current_scan)
            scans.append(current_scan)
        _manifest, _dossier, mapping_validator, scan_validator = _context(project, validator, scans, payload)
        return helper.legacy_maintenance_failures(
            project, auth, payload, validate_mapping=mapping_validator, validate_scan=scan_validator,
            current_scan=current_scan, require_complete_delta=final,
        )
    except (OSError, ValueError, TypeError, KeyError, validator.StateError) as exc:
        return [f"Scoped maintenance: {exc}"]
