#!/usr/bin/env python3
"""Validate the maintainer-only v2 evidence registry and risk authorization graph."""

from __future__ import annotations

_CACHE_PREFLIGHT_PATH = (
    __file__.replace("\\", "/").rsplit("/", 1)[0] + "/cache_preflight.py"
)
with open(_CACHE_PREFLIGHT_PATH, "rb") as _cache_preflight_stream:
    _CACHE_PREFLIGHT_SOURCE = _cache_preflight_stream.read()
exec(
    compile(_CACHE_PREFLIGHT_SOURCE, _CACHE_PREFLIGHT_PATH, "exec"),
    {
        "__file__": _CACHE_PREFLIGHT_PATH,
        "__name__": "_design_dna_cache_preflight",
    },
)
del _CACHE_PREFLIGHT_PATH, _CACHE_PREFLIGHT_SOURCE, _cache_preflight_stream

import argparse
import hashlib
import re
from datetime import date
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from check_links import external_status
from common import (
    ToolFailure,
    absolute,
    assert_no_reparse_path,
    emit,
    is_within,
    load_json,
    strict_format_checker,
    walk_entries,
)


HEADINGS = (
    "Claim", "Observation", "Scope and limitations", "Counterexamples",
    "Positive action", "Supports", "Validation", "Retention",
)
RISK_ID = re.compile(r"\bRISK-[A-Z]+-\d+\b")
EVIDENCE_ID = re.compile(r"\bEVD-\d+\b")
STATUSES = {"candidate", "active", "retired", "rejected"}
ALLOWED_BASES = {"owner_policy"}
OWNER_POLICY_BINDINGS = {
    "RISK-HIER-001": "hierarchy_follows_content_and_task",
    "RISK-CODE-001": "semantic_maintainable_implementation",
    "RISK-MOTION-001": "motion_has_user_or_experience_purpose",
    "RISK-RESIDUE-001": "release_residue",
    "RISK-TRUTH-001": "fabricated_proof_or_business_facts",
    "RISK-CONTEXT-001": "infer_vintage_from_category",
    "RISK-CULTURE-001": "representation_and_cultural_context",
    "RISK-REPEAT-001": "cross_project_pattern_history",
}


class NoDuplicateLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise yaml.constructor.ConstructorError(
                "mapping", node.start_mark, f"duplicate key: {key}", key_node.start_mark
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


NoDuplicateLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def strict_yaml(text: str) -> object:
    return yaml.load(text, Loader=NoDuplicateLoader)


def frontmatter(path: Path) -> tuple[dict[str, object], str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not match:
        raise ValueError("missing or unclosed YAML frontmatter")
    metadata = strict_yaml(match.group(1))
    if not isinstance(metadata, dict):
        raise ValueError("frontmatter must be a mapping")
    return metadata, text[match.end():]


def issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def section_map(body: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", body))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        result[match.group(1).strip()] = body[match.end():end].strip()
    return result


def validate(
    plugin_root: Path,
    schema_path: Path,
    *,
    online: bool,
    strict_due: bool,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, object]]:
    assert_no_reparse_path(plugin_root)
    if not plugin_root.is_dir():
        raise ToolFailure(
            "plugin-root-missing",
            "Plugin root does not exist.",
            plugin_root,
        )
    assert_no_reparse_path(schema_path)
    if not schema_path.is_file():
        raise ToolFailure(
            "evidence-schema-missing",
            "Evidence schema does not exist.",
            schema_path,
        )
    schema = load_json(schema_path)
    validator = Draft202012Validator(
        schema,
        format_checker=strict_format_checker(),
    )
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    evidence_root = plugin_root / "maintainer" / "evidence"
    cards_root = evidence_root / "cards"
    index_path = evidence_root / "index.yml"
    assert_no_reparse_path(evidence_root, stop=plugin_root)
    if not evidence_root.is_dir():
        raise ToolFailure(
            "evidence-root-missing",
            "Evidence root does not exist.",
            evidence_root,
        )
    assert_no_reparse_path(cards_root, stop=evidence_root)
    if not cards_root.is_dir():
        raise ToolFailure(
            "evidence-cards-missing",
            "Evidence cards directory does not exist.",
            cards_root,
        )
    # Enumerate the complete evidence tree before parsing it. This rejects
    # unreferenced link-like entries as well as links used by cards or snapshots.
    for _entry in walk_entries(evidence_root):
        pass
    assert_no_reparse_path(index_path, stop=evidence_root)
    try:
        index = strict_yaml(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return [issue("invalid-evidence-index", str(index_path), str(exc))], warnings, {}
    if not isinstance(index, dict):
        return [issue("invalid-evidence-index", str(index_path), "Index must be a mapping.")], warnings, {}
    unexpected_index_fields = set(index) - {
        "schema_version",
        "owner",
        "last_reviewed",
        "next_review",
        "risks",
        "rejected_hypotheses",
    }
    if unexpected_index_fields:
        failures.append(issue(
            "invalid-evidence-index-field",
            "maintainer/evidence/index.yml",
            ", ".join(sorted(map(str, unexpected_index_fields))),
        ))
    if index.get("schema_version") != 2:
        failures.append(issue("invalid-evidence-index-schema", "maintainer/evidence/index.yml", "schema_version must be 2."))
    if str(index.get("owner", "")).strip().casefold() in {"", "owner", "maintainer", "skill maintainer", "unknown", "tbd"}:
        failures.append(issue("invalid-evidence-owner", "maintainer/evidence/index.yml", "Use an accountable, non-generic owner."))
    try:
        reviewed = date.fromisoformat(str(index.get("last_reviewed", "")))
        next_review = date.fromisoformat(str(index.get("next_review", "")))
        if reviewed > date.today():
            failures.append(issue("future-index-review", "maintainer/evidence/index.yml", str(reviewed)))
        if reviewed > next_review:
            failures.append(issue("invalid-index-chronology", "maintainer/evidence/index.yml", "last_reviewed must not follow next_review."))
        interval = (next_review - reviewed).days
        if not 1 <= interval <= 180:
            failures.append(issue("invalid-index-review-interval", "maintainer/evidence/index.yml", f"{interval} days"))
        if next_review < date.today():
            target = failures if strict_due else warnings
            target.append(issue("evidence-index-overdue", "maintainer/evidence/index.yml", str(next_review)))
    except ValueError as exc:
        failures.append(issue("invalid-index-date", "maintainer/evidence/index.yml", str(exc)))

    risks = index.get("risks")
    if not isinstance(risks, dict) or not risks:
        failures.append(issue("invalid-risk-index", "maintainer/evidence/index.yml", "risks must be a nonempty mapping."))
        risks = {}
    rejected_hypotheses = index.get("rejected_hypotheses", {})
    if not isinstance(rejected_hypotheses, dict):
        failures.append(issue("invalid-rejected-hypotheses", "maintainer/evidence/index.yml", "rejected_hypotheses must be a mapping."))
        rejected_hypotheses = {}

    owner_policy_path = plugin_root / "skills" / "design-dna" / "policy" / "owner-defaults.yml"
    assert_no_reparse_path(owner_policy_path, stop=plugin_root)
    try:
        owner_policy = strict_yaml(owner_policy_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        failures.append(issue("basis-artifact-invalid", str(owner_policy_path), str(exc)))
        owner_policy = {}
    owner_defaults = (
        owner_policy.get("defaults", {})
        if isinstance(owner_policy, dict)
        else {}
    )
    if not isinstance(owner_defaults, dict):
        owner_defaults = {}

    cards: dict[str, dict[str, object]] = {}
    supports: dict[str, set[str]] = {}
    for path in sorted(cards_root.glob("EVD-*.md")):
        relative = path.relative_to(plugin_root).as_posix()
        assert_no_reparse_path(path, stop=cards_root)
        try:
            metadata, body = frontmatter(path)
        except (OSError, UnicodeError, yaml.YAMLError, ValueError) as exc:
            failures.append(issue("invalid-evidence-frontmatter", relative, str(exc)))
            continue
        for error in sorted(validator.iter_errors(metadata), key=lambda item: list(item.path)):
            failures.append(issue("invalid-evidence-schema", relative, error.message))
        evidence_id = str(metadata.get("id", ""))
        if evidence_id != path.stem:
            failures.append(issue("evidence-id-mismatch", relative, f"{evidence_id!r} != {path.stem!r}"))
        if evidence_id in cards:
            failures.append(issue("duplicate-evidence-id", relative, evidence_id))
        cards[evidence_id] = metadata
        sections = section_map(body)
        for heading in HEADINGS:
            if heading not in sections:
                failures.append(issue("missing-evidence-section", relative, heading))
            elif len(sections[heading].strip()) < 8:
                failures.append(issue("empty-evidence-section", relative, heading))
        if str(metadata.get("owner", "")).strip().casefold() in {
            "",
            "owner",
            "maintainer",
            "skill maintainer",
            "unknown",
            "tbd",
        }:
            failures.append(issue("invalid-evidence-owner", relative, str(metadata.get("owner"))))
        if str(metadata.get("publisher", "")).strip().casefold() in {
            "",
            "publisher",
            "unknown",
            "tbd",
        }:
            failures.append(issue("invalid-evidence-publisher", relative, str(metadata.get("publisher"))))
        try:
            created = date.fromisoformat(str(metadata["created"]))
            retrieved = date.fromisoformat(str(metadata["retrieved"]))
            last_reviewed = date.fromisoformat(str(metadata["last_reviewed"]))
            card_next_review = date.fromisoformat(str(metadata["next_review"]))
            today = date.today()
            if any(value > today for value in (created, retrieved, last_reviewed)):
                failures.append(issue("future-evidence-date", relative, "created, retrieved, and last_reviewed may not be in the future."))
            if not (created <= last_reviewed <= card_next_review and retrieved <= last_reviewed):
                failures.append(issue("invalid-evidence-chronology", relative, "created and retrieved must be <= last_reviewed <= next_review."))
            interval = (card_next_review - last_reviewed).days
            maximum_interval = (
                90
                if metadata.get("source_type") in {
                    "platform_documentation",
                    "platform_guidance",
                    "expert_guidance",
                    "community_synthesis",
                    "qualitative_community",
                    "owner_preference",
                }
                else 180
            )
            if not 1 <= interval <= maximum_interval:
                failures.append(issue("invalid-review-interval", relative, f"{interval} days"))
            if metadata.get("status") == "active" and card_next_review < date.today():
                target = failures if strict_due else warnings
                target.append(issue("evidence-overdue", relative, str(card_next_review)))
        except (KeyError, ValueError):
            pass
        card_supports = set(RISK_ID.findall(sections.get("Supports", "")))
        supports[evidence_id] = card_supports
        if not card_supports:
            failures.append(issue("evidence-supports-empty", relative, "The Supports section must name at least one risk ID."))
        if metadata.get("status") in {"retired", "rejected"} and card_supports:
            failures.append(issue("inactive-evidence-authorizes-risk", relative, ", ".join(sorted(card_supports))))
        if metadata.get("source_type") == "internal_evaluation":
            artifact_path = absolute(plugin_root / str(metadata.get("artifact_path", "")))
            if not is_within(artifact_path, plugin_root):
                failures.append(issue("evaluation-artifact-missing", relative, str(metadata.get("artifact_path"))))
            else:
                assert_no_reparse_path(artifact_path, stop=plugin_root)
                if not artifact_path.is_file():
                    failures.append(issue(
                        "evaluation-artifact-missing",
                        relative,
                        str(metadata.get("artifact_path")),
                    ))
                else:
                    actual_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
                    if actual_hash != metadata.get("artifact_sha256"):
                        failures.append(issue("evaluation-artifact-hash-mismatch", relative, actual_hash))
        if (
            metadata.get("status") == "active"
            and metadata.get("source_type")
            in {"platform_documentation", "platform_guidance"}
        ):
            snapshot_relative = metadata.get("source_snapshot_path")
            snapshot_digest = metadata.get("source_snapshot_sha256")
            if not isinstance(snapshot_relative, str) or not isinstance(
                snapshot_digest, str
            ):
                failures.append(issue(
                    "source-snapshot-missing",
                    relative,
                    "Active fast-moving platform evidence needs a hash-bound short source snapshot.",
                ))
            else:
                snapshot_path = absolute(plugin_root / snapshot_relative)
                snapshot_root = absolute(evidence_root / "snapshots")
                if (
                    not is_within(snapshot_path, snapshot_root)
                ):
                    failures.append(issue(
                        "source-snapshot-path-invalid",
                        relative,
                        snapshot_relative,
                    ))
                else:
                    assert_no_reparse_path(snapshot_root, stop=evidence_root)
                    assert_no_reparse_path(snapshot_path, stop=snapshot_root)
                    if not snapshot_path.is_file():
                        failures.append(issue(
                            "source-snapshot-path-invalid",
                            relative,
                            snapshot_relative,
                        ))
                    else:
                        try:
                            snapshot_bytes = snapshot_path.read_bytes()
                            actual_digest = hashlib.sha256(snapshot_bytes).hexdigest()
                            snapshot = load_json(snapshot_path)
                            if actual_digest != snapshot_digest:
                                failures.append(issue(
                                    "source-snapshot-hash-mismatch",
                                    relative,
                                    actual_digest,
                                ))
                            required_snapshot = {
                                "schema_version",
                                "evidence_id",
                                "retrieved",
                                "url",
                                "locator",
                                "excerpt",
                            }
                            if (
                                not isinstance(snapshot, dict)
                                or set(snapshot) != required_snapshot
                                or snapshot.get("schema_version") != 1
                            ):
                                failures.append(issue(
                                    "source-snapshot-shape-invalid",
                                    relative,
                                    snapshot_relative,
                                ))
                            else:
                                bindings = {
                                    "evidence_id": "id",
                                    "retrieved": "retrieved",
                                    "url": "url",
                                    "locator": "locator",
                                }
                                for field, metadata_field in bindings.items():
                                    if snapshot.get(field) != metadata.get(metadata_field):
                                        failures.append(issue(
                                            "source-snapshot-binding-mismatch",
                                            relative,
                                            field,
                                        ))
                                excerpt = snapshot.get("excerpt")
                                words = (
                                    re.findall(r"\b[\w\u2019'-]+\b", excerpt)
                                    if isinstance(excerpt, str)
                                    else []
                                )
                                if not 5 <= len(words) <= 25:
                                    failures.append(issue(
                                        "source-snapshot-excerpt-invalid",
                                        relative,
                                        f"Expected 5-25 words; found {len(words)}.",
                                    ))
                        except (OSError, UnicodeError, ValueError, ToolFailure) as exc:
                            failures.append(issue(
                                "source-snapshot-invalid",
                                relative,
                                str(exc),
                            ))
        url = metadata.get("url")
        if online and isinstance(url, str) and url.startswith(("http://", "https://")):
            healthy, status_text = external_status(url, 10)
            if not healthy:
                warnings.append(issue("evidence-link-unhealthy", relative, status_text))

    referenced_cards: set[str] = set()
    indexed_pairs: set[tuple[str, str]] = set()
    active_risks = 0
    for risk_id, record in risks.items():
        risk_path = f"maintainer/evidence/index.yml:{risk_id}"
        if not RISK_ID.fullmatch(str(risk_id)):
            failures.append(issue("invalid-risk-id", risk_path, str(risk_id)))
            continue
        if not isinstance(record, dict):
            failures.append(issue("invalid-risk-record", risk_path, "Risk record must be a mapping."))
            continue
        unexpected_fields = set(record) - {"status", "basis", "evidence"}
        if unexpected_fields:
            failures.append(issue(
                "invalid-risk-record-field",
                risk_path,
                ", ".join(sorted(map(str, unexpected_fields))),
            ))
        status = record.get("status")
        if status not in STATUSES:
            failures.append(issue("invalid-risk-status", risk_path, str(status)))
        basis = record.get("basis")
        evidence_ids = record.get("evidence", [])
        if basis is not None and basis not in ALLOWED_BASES:
            failures.append(issue("invalid-risk-basis", risk_path, str(basis)))
        if evidence_ids and basis:
            failures.append(issue("ambiguous-risk-authorization", risk_path, "Use evidence or an explicit basis, not both."))
        if not evidence_ids and not basis:
            failures.append(issue("risk-authorization-missing", risk_path, "Risk needs evidence or an allowed explicit basis."))
        if evidence_ids and (not isinstance(evidence_ids, list) or len(evidence_ids) != len(set(map(str, evidence_ids)))):
            failures.append(issue("invalid-risk-evidence-list", risk_path, "Evidence must be a unique list."))
            continue
        if basis == "owner_policy":
            binding = OWNER_POLICY_BINDINGS.get(str(risk_id))
            if binding is None or binding not in owner_defaults:
                failures.append(issue(
                    "owner-policy-basis-unbound",
                    risk_path,
                    f"No owner-policy default binds {risk_id}.",
                ))
        if status == "active":
            active_risks += 1
        active_evidence_count = 0
        active_publishers: set[str] = set()
        has_authoritative_source = False
        has_repeated_evaluation = False
        for evidence_id in map(str, evidence_ids):
            referenced_cards.add(evidence_id)
            indexed_pairs.add((str(risk_id), evidence_id))
            card_status = cards.get(evidence_id, {}).get("status")
            if evidence_id not in cards:
                failures.append(issue("indexed-evidence-missing", risk_path, evidence_id))
            elif card_status in {"retired", "rejected"}:
                failures.append(issue("risk-uses-inactive-evidence", risk_path, evidence_id))
            elif card_status == "active":
                active_evidence_count += 1
                card = cards[evidence_id]
                publisher = str(card.get("publisher", "")).strip().casefold()
                if publisher:
                    active_publishers.add(publisher)
                if (
                    card.get("source_type") in {"standard", "official_guidance"}
                    and card.get("confidence") == "high"
                ):
                    has_authoritative_source = True
                if (
                    card.get("source_type") == "internal_evaluation"
                    and len(set(map(str, card.get("evaluation_hosts", [])))) >= 2
                    and len(set(map(str, card.get("evaluation_projects", [])))) >= 2
                ):
                    has_repeated_evaluation = True
            if evidence_id in supports and str(risk_id) not in supports[evidence_id]:
                failures.append(issue(
                    "index-card-claim-mismatch",
                    risk_path,
                    f"{evidence_id} does not declare support for {risk_id}.",
                ))
        if status == "active" and basis is None and active_evidence_count == 0:
            failures.append(issue("active-risk-without-active-evidence", risk_path, "At least one listed card must be active; candidate cards may be supplemental."))
        if (
            status == "active"
            and basis is None
            and active_evidence_count > 0
            and not has_authoritative_source
            and not has_repeated_evaluation
            and len(active_publishers) < 2
        ):
            failures.append(issue(
                "active-risk-evidence-threshold",
                risk_path,
                "Promotion needs one high-confidence standard/official source, two independent active publishers, or a hash-bound repeated evaluation across at least two projects and two hosts.",
            ))

    for hypothesis, record in rejected_hypotheses.items():
        hypothesis_path = f"maintainer/evidence/index.yml:rejected_hypotheses.{hypothesis}"
        if not isinstance(record, dict) or not isinstance(record.get("evidence"), list) or not str(record.get("reason", "")).strip():
            failures.append(issue("invalid-rejected-hypothesis", hypothesis_path, "Needs evidence list and reason."))
            continue
        for evidence_id in map(str, record["evidence"]):
            referenced_cards.add(evidence_id)
            if evidence_id not in cards:
                failures.append(issue("rejected-hypothesis-evidence-missing", hypothesis_path, evidence_id))

    for evidence_id, card_risks in supports.items():
        for risk_id in card_risks:
            if risk_id not in risks:
                failures.append(issue("unknown-risk-reference", f"maintainer/evidence/cards/{evidence_id}.md", risk_id))
            elif (risk_id, evidence_id) not in indexed_pairs:
                failures.append(issue("card-index-reverse-mismatch", f"maintainer/evidence/cards/{evidence_id}.md", risk_id))
    unindexed_cards = set(cards) - referenced_cards
    for evidence_id in sorted(unindexed_cards):
        failures.append(issue("evidence-card-unindexed", f"maintainer/evidence/cards/{evidence_id}.md", "Card is not used by a risk or rejected hypothesis."))

    return failures, warnings, {
        "cards": len(cards),
        "risks": len(risks),
        "active_risks": active_risks,
        "rejected_hypotheses": len(rejected_hypotheses),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    plugin = Path(__file__).resolve().parents[2]
    parser.add_argument("--plugin-root", type=Path, default=plugin)
    parser.add_argument("--schema", type=Path, default=Path(__file__).resolve().parents[1] / "schemas" / "evidence-frontmatter.schema.json")
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--allow-overdue", action="store_true")
    args = parser.parse_args()
    try:
        failures, warnings, details = validate(
            absolute(args.plugin_root), absolute(args.schema),
            online=args.online, strict_due=not args.allow_overdue,
        )
        emit({"ok": not failures, "failures": failures, "warnings": warnings, "details": details})
        return 1 if failures else 0
    except ToolFailure as exc:
        emit({"ok": False, "failures": [exc.issue.as_dict()], "warnings": []})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
