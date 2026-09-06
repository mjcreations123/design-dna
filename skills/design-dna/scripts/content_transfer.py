"""Source copy rhythm, truthful adaptation authority, and composition lineage."""
from __future__ import annotations
import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath, PureWindowsPath

def normalized(value):
    return " ".join(str(value or "").split())

def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def read_bound(project, binding):
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
        raise ValueError("exact path/hash binding required")
    raw = binding["path"]
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise ValueError("bound file requires an exact portable project-relative path")
    relative = PurePosixPath(raw)
    if relative.is_absolute() or PureWindowsPath(raw).drive or raw != relative.as_posix() or any(part in {".", ".."} for part in relative.parts):
        raise ValueError("bound file path is not exactly contained in the project")
    root = Path(os.path.abspath(project))
    file = root.joinpath(*relative.parts)
    if not file.is_relative_to(root):
        raise ValueError("bound file path is outside the project")
    cursor = root
    for part in (None, *relative.parts):
        if part is not None:
            cursor = cursor / part
        info = cursor.lstat()
        has_reparse = bool(getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        tag = getattr(info, "st_reparse_tag", 0)
        # Match the runtime: OneDrive hydration tags do not redirect paths;
        # name-surrogate tags and unknown reparse metadata remain blocked.
        redirects = has_reparse and (not tag or bool(tag & 0x20000000) or tag in {0xA0000003, 0xA000000C})
        if stat.S_ISLNK(info.st_mode) or redirects:
            raise ValueError("bound file or an ancestor is a symlink/reparse point")
    before = file.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError("bound file must be an ordinary single-link file; hardlinks are forbidden")
    content = file.read_bytes()
    after = file.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_nlink) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_nlink):
        raise ValueError("bound file changed while it was being read")
    if hashlib.sha256(content).hexdigest() != binding["sha256"]:
        raise ValueError("bound file changed")
    return file

def content_transfer_failures(project: Path, mapping: dict, census: dict | None = None):
    try:
        return _content_transfer_failures(project, mapping, census)
    except (AttributeError, KeyError, TypeError, ValueError, OSError) as exc:
        return [f"Content transfer contract is malformed: {exc}"]

def _content_transfer_failures(project: Path, mapping: dict, census: dict | None = None):
    failures = []
    decisions = {row.get("decision_id"): row for row in mapping.get("decisions", []) if isinstance(row, dict)}
    source_styles = {}
    for decision in decisions.values():
        source = decision.get("source_mapping", {}).get("id")
        if source in source_styles:
            continue
        try:
            file = read_bound(project, decision.get("style_provenance", {}).get("record"))
            source_styles[source] = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            failures.append(f"Content transfer source {source}: {exc}")
    def source_row(source_id, selector, profile, state_id):
        return next((row for row in source_styles.get(source_id, {}).get("component_styles", [])
            if row.get("selector") == selector and row.get("profile") == profile and row.get("state_id") == state_id), None)
    component_rows = [row for styles in source_styles.values() for row in styles.get("component_styles", [])]
    if any(not isinstance(row.get("content_facts"), dict) for row in component_rows):
        failures.append("Source style capture lacks generated content/hierarchy facts; remeasure with the current extractor before construction.")
    relevant = any(normalized(row.get("content_facts", {}).get("text")) or
        row.get("content_facts", {}).get("previous_selector") is not None or
        row.get("content_facts", {}).get("parent_tag") not in {None, "html", "body"}
        for row in component_rows)
    if not relevant and mapping.get("content_transfer") is None:
        return failures
    binding = mapping.get("content_transfer")
    try:
        plan_file = read_bound(project, binding)
        alias = (project / ".design-dna" / "content-transfer.json").resolve()
        immutable = (project / ".design-dna" / "content-transfers" / (binding["sha256"] + ".json")).resolve()
        if plan_file not in {alias, immutable}:
            raise ValueError("plan must be content-transfer.json or immutable content-transfers/<sha256>.json")
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
        if set(plan) != {"schema_version", "record_type", "decisions"} or plan["schema_version"] != 1 or plan["record_type"] != "design-dna-content-transfer":
            raise ValueError("unsupported content transfer plan")
        rows = {row["decision_id"]: row for row in plan["decisions"]}
        if len(rows) != len(plan["decisions"]) or set(rows) != set(decisions):
            raise ValueError("plan decision IDs must exactly equal construction decisions")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return [*failures, f"Pre-code content/section-order authority is missing or invalid: {exc}"]
    for decision_id, decision in decisions.items():
        row = rows[decision_id]
        if set(row) != {"decision_id", "target_text", "authority", "parent_decision_id", "previous_decision_id", "arrangement_source"}:
            failures.append(f"Content transfer {decision_id} has an unsupported shape.")
            continue
        target = normalized(row.get("target_text"))
        authority_text = None
        if target:
            try:
                authority = read_bound(project, row["authority"])
                current_authority = authority.name in {"brief.md", "claims.md"} and authority.parent == (project / ".design-dna").resolve()
                immutable_authority = authority == (project / ".design-dna" / "content-authority" / (row["authority"]["sha256"] + ".md")).resolve()
                if not current_authority and not immutable_authority:
                    raise ValueError("public text must bind brief.md, claims.md, or their immutable content-authority/<sha256>.md snapshot")
                authority_text = normalized(authority.read_text(encoding="utf-8"))
                if target not in authority_text:
                    raise ValueError("exact intended public text is absent from the current project authority")
            except (OSError, ValueError) as exc:
                failures.append(f"Content transfer {decision_id}: {exc}")
        elif row.get("authority") is not None:
            failures.append(f"Content transfer {decision_id} gives copy authority to an empty-text component.")
        for cell in decision.get("bindings", []):
            profile, state_id = cell.get("viewport"), cell.get("source_state", {}).get("id")
            source_id = decision.get("source_mapping", {}).get("id")
            selector = decision.get("source_mapping", {}).get("source_selector")
            source = source_row(source_id, selector, profile, state_id)
            facts = source.get("content_facts") if isinstance(source, dict) else None
            if not isinstance(facts, dict):
                failures.append(f"Content transfer {decision_id}/{profile} lacks generated source text/hierarchy facts.")
                continue
            if bool(normalized(facts.get("text"))) != bool(target):
                failures.append(f"Content transfer {decision_id}/{profile} invents or omits a source text role.")
            arrangement = row.get("arrangement_source")
            if arrangement is not None:
                if not isinstance(arrangement, dict) or set(arrangement) != {"source_reference_id", "source_selector", "source_state_id"}:
                    failures.append(f"Content transfer {decision_id} has an invalid measured composition bridge.")
                    continue
                source_id = arrangement["source_reference_id"]
                source = source_row(source_id, arrangement["source_selector"], profile, arrangement["source_state_id"])
            order = source.get("content_facts") if isinstance(source, dict) else None
            if not isinstance(order, dict):
                failures.append(f"Content transfer {decision_id}/{profile} has no observed composition bridge.")
                continue
            for field, source_field in (("parent_decision_id", "parent_selector"), ("previous_decision_id", "previous_selector")):
                other_id = row.get(field)
                expected_selector = order.get(source_field)
                if other_id is None:
                    allowed = expected_selector is None or field == "parent_decision_id" and order.get("parent_tag") in {"html", "body"}
                    if not allowed:
                        failures.append(f"Content transfer {decision_id}/{profile} omits its observed {source_field}; the connection needs measured authority.")
                    continue
                other = decisions.get(other_id)
                other_plan = rows.get(other_id, {})
                other_arrangement = other_plan.get("arrangement_source")
                other_source = other_arrangement.get("source_reference_id") if isinstance(other_arrangement, dict) else (other or {}).get("source_mapping", {}).get("id")
                other_selector = other_arrangement.get("source_selector") if isinstance(other_arrangement, dict) else (other or {}).get("source_mapping", {}).get("source_selector")
                if other is None or other_source != source_id or other_selector != expected_selector:
                    failures.append(f"Content transfer {decision_id}/{profile} invents {field} instead of the observed source relationship.")
            if census is None:
                continue
            if census.get("first_screen_only") is True and decision_id not in mapping.get("proof_isolation", {}).get("decision_ids", decisions):
                continue
            if cell.get("route_key") not in {check.get("route_key") for check in census.get("checks", [])}:
                continue
            check = next((item for item in census.get("checks", []) if item.get("route_key") == cell.get("route_key") and item.get("viewport") == profile and item.get("state_id") == cell.get("state_id")), {})
            roots = [root for entry in check.get("decision_roots", []) if entry.get("decision_id") == decision_id for root in entry.get("roots", [])]
            actual = roots[0].get("content_facts") if len(roots) == 1 else None
            if not isinstance(actual, dict):
                failures.append(f"Content transfer {decision_id}/{profile} lacks exact rendered text/hierarchy facts.")
                continue
            if normalized(actual.get("text")) != target or any(actual.get(key) != facts.get(key) for key in ("tag", "role", "line_count")):
                failures.append(f"Content transfer {decision_id}/{profile} differs from its intended copy, source semantic role or measured line rhythm.")
            for field, actual_field in (("parent_decision_id", "parent_component"), ("previous_decision_id", "previous_component")):
                other = decisions.get(row.get(field))
                if actual.get(actual_field) != (other or {}).get("component_id"):
                    failures.append(f"Content transfer {decision_id}/{profile} rendered {field} differs from its pre-code measured connection.")
    return failures
