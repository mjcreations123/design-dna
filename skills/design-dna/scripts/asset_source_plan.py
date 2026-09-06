"""Freeze an observed media relationship before generating a project asset."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()

def canonical(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def timestamp(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("a timezone-qualified timestamp is required")
    return parsed

def prepare_source_plan(project, *, asset_id, observation, styles, selector, state_id, role):
    project = project.resolve()
    for file in (observation, styles):
        if not file.resolve().is_relative_to(project) or not file.is_file() or file.is_symlink():
            raise ValueError("source evidence must be contained ordinary project files")
    observed = json.loads(observation.read_text(encoding="utf-8"))
    measured = json.loads(styles.read_text(encoding="utf-8"))
    scripts = Path(__file__).resolve().parent
    if (observed.get("tool") != "observe_reference.mjs" or observed.get("source_study", {}).get("source_status") != "complete"
        or observed.get("producer_script_sha256") != sha(scripts / "observe_reference.mjs")
        or observed.get("source_study", {}).get("eligible_for_source_selection") is not True
        or measured.get("tool") != "extract_reference_styles.mjs" or measured.get("producer_script_sha256") != sha(scripts / "extract_reference_styles.mjs")
        or measured.get("id") != observed.get("id")):
        raise ValueError("asset preparation needs a completed eligible public-source observation")
    if not re.fullmatch(r"ASSET-[0-9]{3,}", asset_id) or len(role.strip()) < 12:
        raise ValueError("asset ID and explicit source media role are required")
    snapshots = {}
    for profile in ("wide", "narrow"):
        row = next((row for row in measured.get("component_styles", []) if row.get("profile") == profile
            and row.get("state_id") == state_id and row.get("selector") == selector), None)
        if not isinstance(row, dict) or not isinstance(row.get("media"), dict) or not row["media"].get("source_url"):
            raise ValueError(f"{profile} exact source media selector is not observed")
        snapshots[profile] = row
    payload = {"schema_version": 1, "record_type": "design-dna-asset-source-plan", "asset_id": asset_id,
        "created_at": datetime.now(timezone.utc).isoformat(), "source_id": observed["id"],
        "observation": {"path": observation.relative_to(project).as_posix(), "sha256": sha(observation)},
        "styles": {"path": styles.relative_to(project).as_posix(), "sha256": sha(styles)},
        "selector": selector, "state_id": state_id, "role": role, "measured_media": snapshots,
        "scope": "source-relationship-and-asset-preparation-only; no public build or delivery authorization"}
    data = canonical(payload).encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    file = project / ".design-dna" / "evidence" / "asset-source-plans" / f"{digest}.json"
    if not file.resolve().is_relative_to(project):
        raise ValueError("asset plan output escapes the project through a link")
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("xb") as handle:
        handle.write(data)
    return {"path": file.relative_to(project).as_posix(), "sha256": digest}

def generated_asset_source_plan_failures(project, asset, mapping):
    generated = asset.get("generated", {})
    match = re.search(r"(\.design-dna/evidence/asset-source-plans/[a-f0-9]{64}\.json)\s+(?:plus\s+)?sha256:([a-f0-9]{64})", str(generated.get("authorization_basis", "")))
    if match is None:
        return [f"Generated asset {asset.get('id')} needs a hash-bound source media plan prepared before generation; call asset_source_plan.py."]
    try:
        file = (project / match[1]).resolve()
        if not file.is_relative_to(project.resolve()) or file.is_symlink() or sha(file) != match[2] or file.stem != match[2]:
            raise ValueError("asset source plan is missing, unsafe or changed")
        plan = json.loads(file.read_text(encoding="utf-8"))
        if plan.get("record_type") != "design-dna-asset-source-plan" or plan.get("schema_version") != 1 or plan.get("asset_id") != asset.get("id"):
            raise ValueError("asset source plan identity differs")
        if timestamp(plan.get("created_at")) > timestamp(generated.get("generated_at")):
            raise ValueError("source media plan was authored after generation")
        sources = {row.get("id"): row for row in mapping.get("source_observations", [])}
        source = sources.get(plan.get("source_id"))
        if source is None or plan.get("observation") != {"path": source.get("path"), "sha256": source.get("sha256")}:
            raise ValueError("source plan does not bind this construction's selected source observation")
        for key in ("observation", "styles"):
            bound = plan[key]
            artifact = (project / bound["path"]).resolve()
            if not artifact.is_relative_to(project.resolve()) or artifact.is_symlink() or sha(artifact) != bound["sha256"]:
                raise ValueError("source plan evidence changed")
        observed = json.loads((project / plan["observation"]["path"]).read_text(encoding="utf-8"))
        if timestamp(observed.get("observed_at")) > timestamp(plan["created_at"]):
            raise ValueError("source plan predates its actual observation")
        styles = json.loads((project / plan["styles"]["path"]).read_text(encoding="utf-8"))
        for profile in ("wide", "narrow"):
            row = next((row for row in styles.get("component_styles", []) if row.get("profile") == profile
                and row.get("state_id") == plan["state_id"] and row.get("selector") == plan["selector"]), None)
            if row is None or plan["measured_media"].get(profile) != row:
                raise ValueError("source plan does not reproduce its generated media relationship")
        carriers = [row for row in mapping.get("decisions", []) if row.get("asset_role_binding", {}) and row["asset_role_binding"].get("asset_id") == asset.get("id")]
        if not carriers or any(row["source_mapping"].get("id") != plan["source_id"] or row["source_mapping"].get("source_selector") != plan["selector"]
            or row["asset_role_binding"].get("role") != plan["role"] for row in carriers):
            raise ValueError("generated output is assigned to a different media role than its pre-generation source plan")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return [f"Generated asset {asset.get('id')} source-plan authorization failed: {exc}"]
    return []

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--observation", required=True)
    parser.add_argument("--styles", required=True)
    parser.add_argument("--selector", required=True)
    parser.add_argument("--state", default="rest")
    parser.add_argument("--role", required=True)
    args = parser.parse_args()
    try:
        result = prepare_source_plan(args.project, asset_id=args.asset_id,
            observation=(args.project / args.observation).resolve(), styles=(args.project / args.styles).resolve(),
            selector=args.selector, state_id=args.state, role=args.role)
        print(json.dumps({"ok": True, "authorization_basis": result["path"] + " plus sha256:" + result["sha256"], **result}))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": {"code": "asset-source-plan-invalid", "message": str(exc)}}))
        raise SystemExit(1)
