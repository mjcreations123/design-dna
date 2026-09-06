#!/usr/bin/env python3
"""Report current delivery eligibility using the complete packaged readiness check.

This is read-only. A stored pass flag alone never authorizes a deliverable link.
Deployment, live verification, aesthetics and owner approval remain separate.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def load_validator():
    path = Path(__file__).resolve().with_name("init_project_state.py")
    spec = importlib.util.spec_from_file_location("_design_dna_delivery_validator", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def current_readiness_failures(project: Path, validator) -> list[str]:
    """Match --check-ready, and independently require the full final gate.

    readiness_failures alone assumes validate_state already ran. A profile
    cannot remove the universal final-site gate from this delivery boundary.
    """
    version = validator.release_version(Path(__file__).resolve().parents[1])
    failures, _warnings = validator.validate_state(project, version)
    failures.extend(validator.owner_recurrence_integration_failures(project / ".design-dna", require_resolved=True))
    failures.extend(validator.owner_pattern_contract_failures(project, phase="ready"))
    if not failures:
        failures.extend(validator.readiness_failures(project))
    final = project / ".design-dna/evidence/gate.json"
    manifest = project / ".design-dna/route-manifest.json"
    if not final.is_file() or not manifest.is_file():
        failures.append("Complete final gate and route manifest are required for every delivery profile.")
        return failures
    gate = json.loads(final.read_text(encoding="utf-8"))
    section = (
        f"- Route manifest: .design-dna/route-manifest.json plus sha256:{hashlib.sha256(manifest.read_bytes()).hexdigest()}\n"
        f"- Gate result: .design-dna/evidence/gate.json plus sha256:{hashlib.sha256(final.read_bytes()).hexdigest()}\n"
    )
    failures.extend(validator.final_gate_failures(section, project=project,
        record_path=project / ".design-dna/visual-review.md", expected_build_id=str(gate.get("build_id", ""))))
    return list(dict.fromkeys(failures))


def status(project: Path, *, validator=None) -> dict:
    validator = validator or load_validator()
    project = project.absolute()
    report = {
        "schema_version": 1, "record_type": "design-dna-delivery-status",
        "project": str(project), "delivery_status": "blocked",
        "deliverable_link_allowed": False, "routes": [], "gate_records": {},
        "failures": [], "deployment": "not-verified-by-this-check",
        "live_verification": "not-verified-by-this-check",
        "owner_approval": "not-verified-by-this-check", "automatic_aesthetic_pass": False,
    }
    try:
        validator.assert_no_reparse_ancestors(project)
        if not project.is_dir():
            raise ValueError("Project root does not exist.")
        initial_tree = validator.project_tree_identity(project)
        final_bytes = None
        for phase, name in (("first-screen", "first-screen-gate.json"), ("final", "gate.json"), ("maintenance", "maintenance-gate.json")):
            relative = f".design-dna/evidence/{name}"
            path = project / relative
            if not path.exists():
                report["gate_records"][phase] = {"status": "absent", "verdict": "the gate did not run"}
                continue
            path = validator.safe_binding_path(project, relative, record_path=project / ".design-dna/state.json")
            raw = path.read_bytes()
            gate = json.loads(raw.decode("utf-8"))
            if phase == "final":
                final_bytes = raw
            if not isinstance(gate, dict) or gate.get("tool") != "gate.py" or gate.get("phase") != phase:
                raise ValueError(f"{relative} is not the expected gate record.")
            report["gate_records"][phase] = {"status": "stored-unverified",
                "verdict": gate.get("verdict"), "build_id": gate.get("build_id"),
                "pass_claim": gate.get("pass") is True}
        final = report["gate_records"].get("final", {})
        if final.get("pass_claim") is not True:
            report["failures"].append("No passing final gate is recorded for the complete website.")
            return report
        failures = current_readiness_failures(project, validator)
        report["failures"].extend(failures)
        if failures:
            return report
        # Readiness validates this exact gate against current source/runtime,
        # dossier, manifest, full coverage and all required evidence records.
        final_path = validator.safe_binding_path(project, ".design-dna/evidence/gate.json", record_path=project / ".design-dna/state.json")
        if final_path.read_bytes() != final_bytes or validator.project_tree_identity(project) != initial_tree:
            raise ValueError("The final gate or build changed during readiness verification; rerun the check.")
        gate = json.loads(final_bytes.decode("utf-8"))
        if gate.get("deliverable_link_allowed") is not True:
            report["failures"].append("The current final gate does not permit a deliverable link.")
            return report
        report["gate_records"]["final"]["status"] = "current-readiness-verified"
        report["delivery_status"] = "local-evidence-ready"
        report["deliverable_link_allowed"] = True
        report["routes"] = [{"key": route["key"], "url": route["url"]} for route in gate["routes"]]
    except Exception as exc:
        report["failures"].append(f"{type(exc).__name__}: {exc}")
        report["delivery_status"] = "blocked"
        report["deliverable_link_allowed"] = False
        report["routes"] = []
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("."))
    args = parser.parse_args()
    report = status(args.project)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["deliverable_link_allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
