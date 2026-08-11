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
import json
import re
from datetime import date
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:
    print(json.dumps({
        "ok": False,
        "failures": [{
            "code": "dependency-missing",
            "message": (
                "Install the hash-locked dependencies from "
                "maintainer/requirements-dev.lock."
            ),
            "severity": "error",
        }],
        "warnings": [],
    }, indent=2))
    raise SystemExit(2) from None

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
    "RISK-AMBITION-001": "visible_ambition",
    "RISK-COMP-001": "public_orientation",
    "RISK-MEDIA-001": "sensory_media_strategy",
    "RISK-TYPE-003": "typography_comfort",
    "RISK-REVIEW-001": "owner_rejection_revalidation",
    "RISK-HIER-001": "content_hierarchy",
    "RISK-CODE-001": "semantic_implementation",
    "RISK-MOTION-001": "motion_and_interaction",
    "RISK-RESIDUE-001": "release_residue",
    "RISK-TRUTH-001": "truth_and_claims",
    "RISK-CONTEXT-001": "time_register",
    "RISK-CULTURE-001": "cultural_context",
    "RISK-REPEAT-001": "cross_project_comparison",
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


def derive_repeated_evaluation_claims(
    plugin_root: Path,
    bundle_path: Path,
) -> tuple[set[str], set[str], list[dict[str, str]]]:
    label = bundle_path.relative_to(plugin_root).as_posix()
    failures: list[dict[str, str]] = []
    bundle_schema_path = (
        plugin_root
        / "maintainer"
        / "schemas"
        / "evaluation-evidence-bundle.schema.json"
    )
    result_schema_path = (
        plugin_root
        / "maintainer"
        / "schemas"
        / "eval-result.schema.json"
    )
    for schema_path in (bundle_schema_path, result_schema_path):
        assert_no_reparse_path(schema_path, stop=plugin_root)
        if not schema_path.is_file():
            return set(), set(), [
                issue(
                    "evaluation-schema-missing",
                    label,
                    schema_path.relative_to(plugin_root).as_posix(),
                )
            ]
    try:
        bundle = load_json(bundle_path)
        bundle_schema = load_json(bundle_schema_path)
        result_schema = load_json(result_schema_path)
    except ToolFailure as exc:
        return set(), set(), [
            issue("evaluation-bundle-invalid", label, str(exc))
        ]
    bundle_validator = Draft202012Validator(
        bundle_schema,
        format_checker=strict_format_checker(),
    )
    for error in sorted(
        bundle_validator.iter_errors(bundle),
        key=lambda item: list(item.path),
    ):
        failures.append(
            issue("evaluation-bundle-schema-invalid", label, error.message)
        )
    if failures or not isinstance(bundle, dict):
        return set(), set(), failures
    result_validator = Draft202012Validator(
        result_schema,
        format_checker=strict_format_checker(),
    )
    result_root = absolute(
        plugin_root / "maintainer" / "evals" / "results"
    )
    hosts: set[str] = set()
    projects: set[str] = set()
    seen_paths: set[str] = set()
    for index, record in enumerate(bundle["result_files"]):
        assert isinstance(record, dict)
        relative = str(record["path"])
        item_label = f"{label}:result_files[{index}]"
        if relative.casefold() in seen_paths:
            failures.append(
                issue(
                    "evaluation-result-path-reused",
                    item_label,
                    relative,
                )
            )
            continue
        seen_paths.add(relative.casefold())
        result_path = absolute(plugin_root / relative)
        if not is_within(result_path, result_root):
            failures.append(
                issue(
                    "evaluation-result-path-invalid",
                    item_label,
                    relative,
                )
            )
            continue
        assert_no_reparse_path(result_root, stop=plugin_root)
        assert_no_reparse_path(result_path, stop=result_root)
        if not result_path.is_file():
            failures.append(
                issue(
                    "evaluation-result-missing",
                    item_label,
                    relative,
                )
            )
            continue
        try:
            result_bytes = result_path.read_bytes()
            result = load_json(result_path)
        except (OSError, ToolFailure) as exc:
            failures.append(
                issue("evaluation-result-invalid", item_label, str(exc))
            )
            continue
        actual_hash = hashlib.sha256(result_bytes).hexdigest()
        if actual_hash != record["sha256"]:
            failures.append(
                issue(
                    "evaluation-result-hash-mismatch",
                    item_label,
                    actual_hash,
                )
            )
            continue
        schema_errors = sorted(
            result_validator.iter_errors(result),
            key=lambda item: list(item.path),
        )
        if schema_errors:
            failures.extend(
                issue(
                    "evaluation-result-schema-invalid",
                    item_label,
                    error.message,
                )
                for error in schema_errors
            )
            continue
        assert isinstance(result, dict)
        skill_driver = result.get("drivers", {}).get("skill")
        model = (
            skill_driver.get("model_context")
            if isinstance(skill_driver, dict)
            else None
        )
        if (
            not isinstance(model, dict)
            or model.get("declaration_status") != "declared"
        ):
            failures.append(
                issue(
                    "evaluation-model-unreported",
                    item_label,
                    (
                        "Repeated-evaluation evidence needs a declared provider, "
                        "model, version, reasoning effort, and generation context."
                    ),
                )
            )
            continue
        model_core = {
            key: value
            for key, value in model.items()
            if key != "sha256"
        }
        model_digest = hashlib.sha256(
            json.dumps(
                model_core,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        if model.get("sha256") != model_digest:
            failures.append(
                issue(
                    "evaluation-model-context-hash-mismatch",
                    item_label,
                    model_digest,
                )
            )
            continue
        suite = str(result.get("suite", ""))
        result_host = str(result.get("host", ""))
        qualified_runs = 0
        for run in result.get("runs", []):
            if (
                not isinstance(run, dict)
                or run.get("variant") != "skill"
                or run.get("passed") is not True
                or not isinstance(run.get("artifact_bundle"), dict)
            ):
                continue
            if run.get("host") != result_host:
                failures.append(
                    issue(
                        "evaluation-host-mismatch",
                        item_label,
                        str(run.get("run_id", "")),
                    )
                )
                continue
            if (
                run.get("invocation_mode") == "implicit"
                and run.get("host_native_evidence_status") != "bound"
            ):
                failures.append(
                    issue(
                        "implicit-evaluation-unproven",
                        item_label,
                        str(run.get("run_id", "")),
                    )
                )
                continue
            case_id = str(run.get("case", ""))
            if not suite or not case_id or not result_host:
                failures.append(
                    issue(
                        "evaluation-project-identity-missing",
                        item_label,
                        str(run.get("run_id", "")),
                    )
                )
                continue
            qualified_runs += 1
            hosts.add(result_host)
            projects.add(f"{suite}/{case_id}")
        if qualified_runs == 0:
            failures.append(
                issue(
                    "evaluation-result-has-no-qualified-runs",
                    item_label,
                    relative,
                )
            )
    return hosts, projects, failures


def validate(
    plugin_root: Path,
    schema_path: Path,
    *,
    online: bool,
    strict_due: bool,
    release_mode: bool = False,
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
    snapshot_schema_path = schema_path.with_name(
        "evidence-snapshot.schema.json"
    )
    assert_no_reparse_path(snapshot_schema_path)
    if not snapshot_schema_path.is_file():
        raise ToolFailure(
            "evidence-snapshot-schema-missing",
            "Evidence snapshot schema does not exist.",
            snapshot_schema_path,
        )
    snapshot_validator = Draft202012Validator(
        load_json(snapshot_schema_path),
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
        if interval < 1:
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
            if (
                release_mode
                and metadata.get("status") == "active"
                and retrieved != last_reviewed
            ):
                failures.append(issue(
                    "release-evidence-not-retrieved-at-review",
                    relative,
                    (
                        "Release evidence must be retrieved again on its "
                        "recorded review date; a metadata-only review is not "
                        "freshness evidence."
                    ),
                ))
            interval = (card_next_review - last_reviewed).days
            if interval < 1:
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
                    else:
                        (
                            derived_hosts,
                            derived_projects,
                            derivation_failures,
                        ) = derive_repeated_evaluation_claims(
                            plugin_root,
                            artifact_path,
                        )
                        failures.extend(derivation_failures)
                        claimed_hosts = set(
                            map(str, metadata.get("evaluation_hosts", []))
                        )
                        claimed_projects = set(
                            map(str, metadata.get("evaluation_projects", []))
                        )
                        if claimed_hosts != derived_hosts:
                            failures.append(issue(
                                "evaluation-host-claim-mismatch",
                                relative,
                                (
                                    f"claimed={sorted(claimed_hosts)!r}; "
                                    f"derived={sorted(derived_hosts)!r}"
                                ),
                            ))
                        if claimed_projects != derived_projects:
                            failures.append(issue(
                                "evaluation-project-claim-mismatch",
                                relative,
                                (
                                    f"claimed={sorted(claimed_projects)!r}; "
                                    f"derived={sorted(derived_projects)!r}"
                                ),
                            ))
                        if (
                            not derivation_failures
                            and claimed_hosts == derived_hosts
                            and claimed_projects == derived_projects
                        ):
                            metadata["_derived_evaluation_hosts"] = sorted(
                                derived_hosts
                            )
                            metadata["_derived_evaluation_projects"] = sorted(
                                derived_projects
                            )
        snapshot_required = (
            metadata.get("status") == "active"
            and metadata.get("source_type")
            in {"platform_documentation", "platform_guidance"}
        )
        snapshot_relative = metadata.get("source_snapshot_path")
        snapshot_digest = metadata.get("source_snapshot_sha256")
        snapshot_declared = (
            snapshot_relative is not None or snapshot_digest is not None
        )
        if snapshot_required or snapshot_declared:
            if not isinstance(snapshot_relative, str) or not isinstance(
                snapshot_digest, str
            ):
                failures.append(issue(
                    "source-snapshot-missing",
                    relative,
                    (
                        "Active fast-moving platform evidence and any declared "
                        "retained source snapshot need both a safe path and an "
                        "exact SHA-256."
                    ),
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
                            snapshot_errors = sorted(
                                snapshot_validator.iter_errors(snapshot),
                                key=lambda item: list(item.path),
                            )
                            if snapshot_errors:
                                failures.append(issue(
                                    "source-snapshot-shape-invalid",
                                    relative,
                                    "; ".join(
                                        error.message
                                        for error in snapshot_errors[:5]
                                    ),
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
                                content_field = (
                                    "excerpt"
                                    if snapshot.get("content_kind")
                                    == "verbatim_excerpt"
                                    else "summary"
                                )
                                excerpt = snapshot.get(content_field)
                                words = (
                                    re.findall(r"\b[\w\u2019'-]+\b", excerpt)
                                    if isinstance(excerpt, str)
                                    else []
                                )
                                maximum_words = (
                                    25
                                    if content_field == "excerpt"
                                    else 60
                                )
                                if not 5 <= len(words) <= maximum_words:
                                    failures.append(issue(
                                        "source-snapshot-content-invalid",
                                        relative,
                                        (
                                            f"{content_field} expected 5-"
                                            f"{maximum_words} words; found "
                                            f"{len(words)}."
                                        ),
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
                target = failures if release_mode else warnings
                target.append(issue(
                    (
                        "release-evidence-retrieval-failed"
                        if release_mode
                        else "evidence-link-unhealthy"
                    ),
                    relative,
                    status_text,
                ))

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
                    and len(set(map(
                        str,
                        card.get("_derived_evaluation_hosts", []),
                    ))) >= 2
                    and len(set(map(
                        str,
                        card.get("_derived_evaluation_projects", []),
                    ))) >= 2
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
    parser.add_argument(
        "--release",
        action="store_true",
        help=(
            "Fail closed on overdue review, retrieval/review mismatch, and "
            "unsuccessful requested online retrieval."
        ),
    )
    args = parser.parse_args()
    try:
        failures, warnings, details = validate(
            absolute(args.plugin_root), absolute(args.schema),
            online=args.online,
            strict_due=(args.release or not args.allow_overdue),
            release_mode=args.release,
        )
        emit({"ok": not failures, "failures": failures, "warnings": warnings, "details": details})
        return 1 if failures else 0
    except ToolFailure as exc:
        emit({"ok": False, "failures": [exc.issue.as_dict()], "warnings": []})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
