"""Freeze honest existing-site history and authorize only a measured maintenance delta.

This is deliberately not a pre-code construction journal.  The caller must use
the complete packaged V2 mapping and rendered-census validators, then preserve
the normal first-screen/final gates.  No boolean "already validated" escape is
accepted.  Local digests detect drift; they do not attest authorship or approval.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable


SCHEMA = 1
RECORD_TYPE = "design-dna-existing-site-maintenance-baseline"
HEX = re.compile(r"[a-f0-9]{64}\Z")
IGNORED = frozenset({".git", ".design-dna", "node_modules", ".venv", "__pycache__"})
MappingValidator = Callable[[dict], list[str]]
ScanValidator = Callable[[dict, dict], list[str]]


class MaintenanceError(ValueError):
    """An actionable, non-authorizing maintenance-boundary failure."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _timestamp(value: object) -> datetime:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise MaintenanceError("Maintenance rendered audit needs an exact timezone-aware timestamp.") from exc
    if result.tzinfo is None or result > datetime.now(timezone.utc):
        raise MaintenanceError("Maintenance rendered audit timestamp is naive or in the future.")
    return result


def mapping_core(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if key != "construction_authorization"}


def _reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    if not getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        return False
    tag = getattr(info, "st_reparse_tag", 0)
    # OneDrive cloud hydration tags do not redirect the pathname. Match the
    # canonical runtime's name-surrogate rule and fail closed on unknown tags.
    return bool(tag & 0x20000000) or tag in {0xA0000003, 0xA000000C} if tag else True


def _contained(project: Path, value: str | Path, *, existing: bool = True) -> Path:
    candidate = Path(value)
    candidate = candidate if candidate.is_absolute() else project / candidate
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(project)
    except ValueError as exc:
        raise MaintenanceError(f"Maintenance artifact is outside the project: {candidate}") from exc
    cursor = project
    for part in relative.parts:
        cursor = cursor / part
        if _reparse(cursor):
            raise MaintenanceError(f"Maintenance cannot traverse a symlink/reparse point: {cursor}")
    if existing and not candidate.is_file():
        raise MaintenanceError(f"Maintenance artifact is missing or not a regular file: {candidate}")
    if candidate.is_file() and candidate.stat().st_nlink != 1:
        raise MaintenanceError(f"Maintenance refuses hardlink aliases to mutable external bytes: {candidate}")
    return candidate


def _binding(project: Path, file: str | Path) -> dict:
    file = _contained(project, file)
    before = file.stat()
    digest = hashlib.sha256()
    size = 0
    with file.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    after = file.stat()
    if (size != before.st_size or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns or before.st_ino != after.st_ino
            or before.st_nlink != 1 or after.st_nlink != 1):
        raise MaintenanceError(f"Maintenance file changed during snapshot: {file}")
    return {"path": file.relative_to(project).as_posix(), "bytes": size, "sha256": digest.hexdigest()}


def _load(project: Path, path: str | Path) -> dict:
    file = _contained(project, path)
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise MaintenanceError(f"Maintenance record is unreadable: {file}: {exc}") from exc
    if not isinstance(payload, dict):
        raise MaintenanceError(f"Maintenance record must be a JSON object: {file}")
    return payload


def baseline_scan_path(project: Path, value: str | Path) -> Path:
    """Keep the old scan outside the mutable standard gate output target."""
    baseline = _contained(project, value)
    if baseline == project / ".design-dna/evidence/component-census.json":
        raise MaintenanceError(
            "Maintenance baseline census cannot use the mutable gate output "
            ".design-dna/evidence/component-census.json. Capture the complete baseline with "
            "--out .design-dna/evidence/maintenance-baselines/<unique-id>/component-census.json "
            "before --begin-maintenance; preserve that generated record and its media directories."
        )
    return baseline


def implementation_snapshot(project: Path) -> list[dict]:
    """Freeze all ordinary project files including compiled output and assets."""
    rows = []
    for current, directories, names in os.walk(project, followlinks=False):
        base = Path(current)
        kept = []
        for name in directories:
            if name in IGNORED:
                continue
            if _reparse(base / name):
                raise MaintenanceError(f"Maintenance inventory cannot traverse a reparse point: {base / name}")
            kept.append(name)
        directories[:] = sorted(kept)
        for name in sorted(names):
            # The project lock is operational metadata rewritten on acquire and
            # release. Only this exact root file is outside implementation.
            if base == project and name == ".design-dna.lock":
                continue
            rows.append(_binding(project, base / name))
    return sorted(rows, key=lambda row: row["path"])


def _validated(callback: Callable, *values: dict) -> None:
    if not callable(callback):
        raise MaintenanceError("Maintenance requires the packaged complete validators; a boolean cannot replace them.")
    failures = callback(*values)
    if not isinstance(failures, list) or not all(isinstance(item, str) for item in failures):
        raise MaintenanceError("Maintenance validator must return its complete list of failure strings.")
    if failures:
        raise MaintenanceError("Maintenance evidence is incomplete: " + " | ".join(failures))


def _decisions(payload: dict) -> dict[str, dict]:
    if payload.get("schema_version") != 2 or payload.get("record_type") != "design-dna-visible-decision-source-manifest":
        raise MaintenanceError("Maintenance requires an exact V2 component source map.")
    rows = payload.get("decisions")
    if not isinstance(rows, list) or not rows:
        raise MaintenanceError("Maintenance source map has no component decisions.")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("decision_id"), str) or not isinstance(row.get("component_id"), str):
            raise MaintenanceError("Maintenance source map has a malformed component decision.")
        if row["decision_id"] in result:
            raise MaintenanceError("Maintenance source map repeats a decision ID.")
        result[row["decision_id"]] = row
    return result


def _changes(value: object, baseline: list[dict], old_map: dict, next_map: dict) -> list[dict]:
    if not isinstance(value, list) or not value:
        raise MaintenanceError("Maintenance needs explicit planned file operations and component IDs before editing.")
    files = {row["path"] for row in baseline}
    old = _decisions(old_map)
    new = _decisions(next_map)
    available_components = {row["component_id"] for row in [*old.values(), *new.values()]}
    seen = set()
    result = []
    for change in value:
        if not isinstance(change, dict) or set(change) != {"path", "operation", "component_ids"}:
            raise MaintenanceError("Maintenance change must contain path, operation, and component_ids.")
        raw = change["path"]
        components = change["component_ids"]
        if (not isinstance(raw, str) or not raw or "\\" in raw or ":" in raw or any(c in raw for c in "*?[]\x00")
                or not PurePosixPath(raw).parts or PurePosixPath(raw).is_absolute() or ".." in PurePosixPath(raw).parts
                or PurePosixPath(raw).as_posix() != raw or any(part in IGNORED for part in PurePosixPath(raw).parts)
                or raw.casefold() in seen):
            raise MaintenanceError("Maintenance scope needs unique exact relative file paths, without globs or evidence/dependency directories.")
        operation = change["operation"]
        if operation not in {"add", "modify", "delete"} or (operation == "add") == (raw in files):
            raise MaintenanceError(f"Maintenance operation does not match the existing baseline: {raw} ({operation}).")
        if (not isinstance(components, list) or not components or not all(isinstance(item, str) for item in components)
                or len(components) != len(set(components)) or not set(components) <= available_components):
            raise MaintenanceError(f"Maintenance path {raw} needs known unique affected component IDs.")
        seen.add(raw.casefold())
        result.append({"path": raw, "operation": operation, "component_ids": sorted(components)})
    touched = {item for row in result for item in row["component_ids"]}
    for decision_id in old.keys() | new.keys():
        before, after = old.get(decision_id), new.get(decision_id)
        if before != after and any(row and row["component_id"] not in touched for row in (before, after)):
            raise MaintenanceError(f"Maintenance plan changes an undeclared component decision: {decision_id}.")
    if old_map.get("route_manifest") != next_map.get("route_manifest"):
        raise MaintenanceError("Scoped maintenance cannot silently expand or change the route manifest; use a separately authorized route plan.")
    return sorted(result, key=lambda row: row["path"])


def _scan(project: Path, scan: dict, source_map: dict, manifest: dict, validate_scan: ScanValidator, expected_snapshot: list[dict]) -> None:
    scanner = Path(__file__).with_name("scan_build_components.mjs")
    expected_cells = {
        (route["key"], viewport["name"], state["id"])
        for route in manifest.get("routes", []) for viewport in manifest.get("viewports", []) for state in route.get("states", [])
    }
    checks = scan.get("checks")
    cells = [(row.get("route_key"), row.get("viewport"), row.get("state_id")) for row in checks if isinstance(row, dict)] if isinstance(checks, list) else []
    reconciliation = scan.get("visible_decision_reconciliation", {})
    snapshot = scan.get("implementation_snapshot")
    _timestamp(scan.get("scanned_at"))
    if (scan.get("tool") != "scan_build_components.mjs" or scan.get("schema_version") != 3
            or scan.get("producer_script_sha256") != hashlib.sha256(scanner.read_bytes()).hexdigest()
            or scan.get("first_screen_only") is not False or scan.get("pass") is not True
            or scan.get("manifest_sha256") != _binding(project, ".design-dna/route-manifest.json")["sha256"]
            or snapshot != {"algorithm": "sha256-files-v1", "files": expected_snapshot, "sha256": _digest(expected_snapshot)}
            or not expected_cells or set(cells) != expected_cells or len(cells) != len(expected_cells)
            or any(row.get("pass") is not True for row in checks)
            or not isinstance(reconciliation, dict) or reconciliation.get("complete") is not True
            or set(reconciliation.get("implemented_decision_ids", [])) != set(_decisions(source_map))
            or any(reconciliation.get(name) != [] for name in (
                "missing_decision_ids", "unsourced_visible_decisions", "wrapper_inheritance_findings",
                "binding_cell_findings", "asset_role_findings", "construction_findings",
                "scaffold_findings", "fallback_findings", "placeholder_findings"))):
        raise MaintenanceError("Maintenance requires a current generated full-route/state/wide+narrow passing census with every visible decision directly source-bound and the exact implementation file snapshot.")
    _validated(validate_scan, scan, source_map)


def begin_legacy_maintenance(
    project: Path,
    *,
    planned_source_map: Path,
    baseline_scan: Path,
    planned_changes: list[dict],
    validate_mapping: MappingValidator,
    validate_scan: ScanValidator,
    output_path: Path | None = None,
) -> dict:
    """Write one create-only audited baseline before an explicitly planned delta."""
    project = project.resolve()
    baseline_scan = baseline_scan_path(project, baseline_scan)
    old = _load(project, ".design-dna/visible-decision-sources.json")
    planned = _load(project, planned_source_map)
    manifest = _load(project, ".design-dna/route-manifest.json")
    scan = _load(project, baseline_scan)
    _validated(validate_mapping, old)
    _validated(validate_mapping, planned)
    baseline = implementation_snapshot(project)
    _scan(project, scan, old, manifest, validate_scan, baseline)
    if scan.get("visible_decision_reconciliation", {}).get("manifest_sha256") != _binding(project, ".design-dna/visible-decision-sources.json")["sha256"]:
        raise MaintenanceError("Maintenance baseline census does not bind the exact existing source map bytes.")
    if not baseline:
        raise MaintenanceError("An empty project uses the fresh construction workflow, not existing-site maintenance.")
    changes = _changes(planned_changes, baseline, old, planned)
    identifier = "legacy-" + secrets.token_hex(16)
    output = _contained(project, output_path or f".design-dna/evidence/legacy-maintenance/{identifier}.json", existing=False)
    if not output.relative_to(project).as_posix().startswith(".design-dna/evidence/legacy-maintenance/"):
        raise MaintenanceError("Maintenance baseline must live in its separate evidence/legacy-maintenance directory.")
    payload = {
        "schema_version": SCHEMA, "record_type": RECORD_TYPE, "journal_id": identifier,
        "created_at": datetime.now(timezone.utc).isoformat(), "project": str(project),
        "history_status": "existing-history-unverified", "authorization_scope": "scoped-maintenance-only",
        "retroactive_precode_claim": False, "public_readiness": False, "owner_approved": False,
        "producer_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "route_manifest": _binding(project, ".design-dna/route-manifest.json"),
        "baseline_scan": _binding(project, baseline_scan),
        "baseline_source_map": old, "planned_source_map": planned,
        "planned_core_sha256": _digest(mapping_core(planned)),
        "implementation_files": baseline, "implementation_tree_sha256": _digest(baseline),
        "asset_files": [row for row in baseline if Path(row["path"]).suffix.lower() in {
            ".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".svg", ".mp4", ".webm",
            ".mov", ".mp3", ".ogg", ".wav", ".woff", ".woff2", ".ttf", ".otf", ".glb", ".gltf",
        }],
        "planned_changes": changes,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    _contained(project, output, existing=False)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return {"journal_id": identifier, "entry_path": output.relative_to(project).as_posix(), "entry_sha256": _binding(project, output)["sha256"]}


def legacy_maintenance_failures(
    project: Path,
    authorization: object,
    current_mapping: dict,
    *,
    validate_mapping: MappingValidator,
    validate_scan: ScanValidator,
    current_scan: Path | None = None,
    require_complete_delta: bool = False,
) -> list[str]:
    """Check frozen plan and allowed writes; readiness additionally needs a fresh full scan.

    A pre-implementation/resume caller uses current_scan=None.  A final/readiness
    caller MUST pass require_complete_delta=True and the newly generated scan.
    A scope-only success never constitutes rendered or public readiness.
    """
    try:
        project = project.resolve()
        if not isinstance(authorization, dict) or set(authorization) != {"journal_id", "entry_path", "entry_sha256"}:
            raise MaintenanceError("Maintenance authorization needs its exact separate baseline identity.")
        binding = _binding(project, authorization["entry_path"])
        if authorization["entry_sha256"] != binding["sha256"]:
            raise MaintenanceError("Maintenance baseline bytes drifted.")
        record = _load(project, authorization["entry_path"])
        if (record.get("schema_version") != SCHEMA or record.get("record_type") != RECORD_TYPE
                or record.get("journal_id") != authorization["journal_id"] or record.get("project") != str(project)
                or record.get("history_status") != "existing-history-unverified"
                or record.get("authorization_scope") != "scoped-maintenance-only"
                or any(record.get(field) is not False for field in ("retroactive_precode_claim", "public_readiness", "owner_approved"))
                or record.get("producer_script_sha256") != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
            raise MaintenanceError("Maintenance baseline is stale or misrepresents existing history as fresh, public, or owner-approved.")
        if _binding(project, record["route_manifest"]["path"]) != record["route_manifest"]:
            raise MaintenanceError("Maintenance route manifest changed outside its frozen scope.")
        if _binding(project, record["baseline_scan"]["path"]) != record["baseline_scan"]:
            raise MaintenanceError("Maintenance baseline rendered audit drifted.")
        baseline = record["implementation_files"]
        if not isinstance(baseline, list) or _digest(baseline) != record.get("implementation_tree_sha256"):
            raise MaintenanceError("Maintenance original implementation inventory is invalid.")
        old, planned = record["baseline_source_map"], record["planned_source_map"]
        _validated(validate_mapping, old)
        _validated(validate_mapping, planned)
        _validated(validate_mapping, current_mapping)
        if _digest(mapping_core(planned)) != record.get("planned_core_sha256") or mapping_core(current_mapping) != mapping_core(planned):
            raise MaintenanceError("Maintenance current source plan differs from the plan frozen before editing.")
        changes = _changes(record["planned_changes"], baseline, old, planned)
        manifest = _load(project, record["route_manifest"]["path"])
        _scan(project, _load(project, record["baseline_scan"]["path"]), old, manifest, validate_scan, baseline)
        before = {row["path"]: row for row in baseline}
        current = {row["path"]: row for row in implementation_snapshot(project)}
        actual = {name: "add" if name not in before else "delete" if name not in current else "modify"
                  for name in before.keys() | current.keys() if before.get(name) != current.get(name)}
        permitted = {row["path"]: row["operation"] for row in changes}
        outside = [f"{name} ({operation})" for name, operation in actual.items() if permitted.get(name) != operation]
        if outside:
            raise MaintenanceError("Maintenance changed files outside the frozen delta: " + ", ".join(sorted(outside)))
        if require_complete_delta and actual != permitted:
            raise MaintenanceError("Maintenance planned delta is incomplete; reopen the plan before changing its scope.")
        if require_complete_delta and current_scan is None:
            raise MaintenanceError("Maintenance readiness requires a fresh full rendered source-map census; a path-scope check is not readiness.")
        if current_scan is not None:
            scan = _load(project, current_scan)
            if _binding(project, current_scan) == record["baseline_scan"]:
                raise MaintenanceError("Maintenance cannot reuse its old rendered census as proof of the edited site.")
            _scan(project, scan, current_mapping, manifest, validate_scan, list(current.values()))
            current_map_path = project / ".design-dna/visible-decision-sources.json"
            if mapping_core(_load(project, current_map_path)) != mapping_core(current_mapping) or scan["visible_decision_reconciliation"]["manifest_sha256"] != _binding(project, current_map_path)["sha256"]:
                raise MaintenanceError("Maintenance final census does not bind the exact current component source map.")
            if _timestamp(scan.get("scanned_at")) <= _timestamp(_load(project, record["baseline_scan"]["path"]).get("scanned_at")):
                raise MaintenanceError("Maintenance final rendered census does not follow the existing baseline audit.")
        return []
    except (MaintenanceError, OSError, ValueError, TypeError, KeyError) as exc:
        return [str(exc)]
