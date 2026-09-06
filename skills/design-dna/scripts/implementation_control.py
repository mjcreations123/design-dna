"""Generated failed-gate boundaries. These are audit evidence, not an OS sandbox."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


def write_prohibition(project: Path, gate_file: Path, record: dict, validator) -> Path:
    """Preserve the exact failed run and source inventory without overwriting history."""
    tree, files, visible, assets = validator.construction_source_snapshot(project)
    root = project / ".design-dna" / "evidence" / "implementation-prohibitions"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{record['run_id']}.json"
    payload = {
        "schema_version": 1, "record_type": "design-dna-implementation-prohibition",
        "run_id": record["run_id"], "phase": record["phase"],
        "checked_at": record["checked_at"], "gate": {
            "path": gate_file.relative_to(project).as_posix(),
            "sha256": hashlib.sha256(gate_file.read_bytes()).hexdigest(),
        },
        "build_tree_sha256": tree, "source_inventory": files,
        "visible_source_files": visible, "asset_files": assets,
        "broad_implementation_allowed": False if record["phase"] == "first-screen" else None,
        "delivery_allowed": False, "failures": record.get("failures", []),
        "recovery": "Repair the isolated proof and rerun its gate; broad implementation requires a later passing first-screen authorization.",
    }
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    return path


def prohibition_failures(project: Path, visible_payload: dict, validator) -> list[str]:
    """Detect broad source changes after a failed first-screen attempt.

    Proof repair remains possible. A later passing immutable first-screen
    predecessor can release this boundary, but only after its own isolation
    and construction checks succeed.
    """
    root = project / ".design-dna" / "evidence" / "implementation-prohibitions"
    if not root.is_dir():
        return []
    failures = []
    rows = []
    def timestamp(value):
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError("timestamp must include timezone")
        return result
    for path in root.glob("*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            if row.get("record_type") != "design-dna-implementation-prohibition" or row.get("schema_version") != 1:
                raise ValueError("unsupported prohibition record")
            timestamp(row.get("checked_at"))
            binding = row.get("gate")
            if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
                raise ValueError("invalid failed-gate binding")
            gate_path = (project / binding["path"]).resolve()
            if not gate_path.is_relative_to(project.resolve()) or gate_path.is_symlink() or not gate_path.is_file():
                raise ValueError("failed-gate file is unsafe or missing")
            if hashlib.sha256(gate_path.read_bytes()).hexdigest() != binding["sha256"]:
                raise ValueError("bound failed-gate hash drifted")
            gate = json.loads(gate_path.read_text(encoding="utf-8"))
            if gate.get("pass") is not False or any(gate.get(key) != row.get(key) for key in ("phase", "run_id", "checked_at")):
                raise ValueError("bound failed gate has a mismatched failure identity")
            inventory = row.get("source_inventory")
            if not isinstance(inventory, list):
                raise ValueError("source inventory is not a list")
            inventory_paths = set()
            for item in inventory:
                if (not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}
                    or not isinstance(item.get("path"), str) or item["path"] in inventory_paths
                    or not (project / item["path"]).resolve().is_relative_to(project.resolve())
                    or type(item.get("bytes")) is not int or item["bytes"] < 0
                    or not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"])):
                    raise ValueError("source inventory contains malformed or duplicate rows")
                inventory_paths.add(item["path"])
            if row.get("phase") == "first-screen":
                rows.append(row)
        except (OSError, ValueError, AttributeError, TypeError, KeyError) as exc:
            failures.append(f"Implementation prohibition is unreadable: {path.name}: {exc}")
    if not rows:
        return failures
    latest = max(rows, key=lambda row: timestamp(row["checked_at"]))
    if hasattr(validator, "prebuild_authorization_chain"):
        chain_failures, authorizations = validator.prebuild_authorization_chain(project)
        if not chain_failures and authorizations:
            try:
                if timestamp(authorizations[-1][1].get("authorized_at")) > timestamp(latest["checked_at"]):
                    return failures
            except (ValueError, TypeError):
                failures.append("Latest first-screen authorization has an invalid timestamp.")
    allowed = set(visible_payload.get("proof_isolation", {}).get("source_files", []))
    baseline = {row["path"]: row["sha256"] for row in latest.get("source_inventory", [])}
    _tree, current, _visible, _assets = validator.construction_source_snapshot(project)
    current_hashes = {row["path"]: row["sha256"] for row in current}
    changed = sorted(path for path in set(baseline) | set(current_hashes)
                     if baseline.get(path) != current_hashes.get(path) and path not in allowed)
    if changed:
        failures.append("Broad implementation changed after failed first-screen gate without authorization: " + ", ".join(changed))
    return failures
