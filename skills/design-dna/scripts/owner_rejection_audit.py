#!/usr/bin/env python3
"""Audit a scoped, owner-authorized Design DNA rejection record.

The contract records what an accountable owner rejected in one exact public
candidate.  It is deliberately not a global style-ban mechanism.  This
dependency-free auditor verifies the candidate tree, its canonical manifest,
the first-party decision evidence, the relationship-cluster scope, and the
active/reopen or owner-confirmed resolution lifecycle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
TOOL_VERSION = "1.0.0"
ARTIFACT_TYPE = "design-dna-owner-rejection-audit"
DEFAULT_CONTRACT = ".design-dna/owner-rejection.json"
DEFAULT_OUTPUT = ".design-dna/owner-rejection-audit.json"
MANIFEST_ALGORITHM = "sha256-tab-lf-v1"
MAX_CONTRACT_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_BYTES = 16 * 1024 * 1024
MAX_PUBLIC_FILE_BYTES = 256 * 1024 * 1024
MAX_PUBLIC_TREE_BYTES = 2 * 1024 * 1024 * 1024
MAX_PUBLIC_FILES = 10000
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
DATE_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2}))?$"
)
LIFECYCLE_STATUSES = {"draft", "active-reopen", "resolved"}
CLASSIFICATIONS = {"internal", "confidential"}
RELATIONSHIP_AXES = {
    "type_posture",
    "cta_grammar",
    "edges_and_containers",
    "depth_and_effects",
    "section_rhythm",
    "material_and_media",
    "public_copy_behavior",
    "interaction_grammar",
    "responsive_behavior",
    "project_defined",
}
ROOT_FIELDS = {
    "schema_version",
    "created_with",
    "classification",
    "status",
    "recorded_at",
    "accountable_owner",
    "candidate",
    "owner_evidence",
    "rejected_relationship_cluster",
    "protected_foundations",
    "reopened_decisions",
    "replacement_constraints",
    "resolution",
}
GLOBAL_BAN_PATTERNS = (
    re.compile(r"\b(?:never|always)\s+(?:use|include|choose|allow|ship)\b", re.I),
    re.compile(
        r"\b(?:do\s+not|don't|must\s+not)\s+(?:ever\s+)?"
        r"(?:use|include|choose|allow|ship)\b",
        re.I,
    ),
    re.compile(r"\b(?:ban|banned|forbid|forbidden)\b", re.I),
    re.compile(r"\bunder\s+any\s+circumstances\b", re.I),
    re.compile(r"\b(?:all|every)\s+(?:future\s+)?(?:site|website|project)s?\b", re.I),
    re.compile(r"\bglobally\b", re.I),
)


class AuditError(RuntimeError):
    """A bounded I/O, path-safety, or integrity failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def issue(path: str, code: str, message: str) -> dict[str, str]:
    return {"path": path, "code": code, "message": message}


def finding(code: str, message: str, *, blocking: bool = True) -> dict[str, Any]:
    return {"code": code, "message": message, "blocking": blocking}


def nonblank(value: Any, *, maximum: int = 8000) -> bool:
    return isinstance(value, str) and 0 < len(value) <= maximum and bool(value.strip())


def exact_fields(
    value: Any,
    path: str,
    expected: set[str],
    errors: list[dict[str, str]],
) -> bool:
    if not isinstance(value, dict):
        errors.append(issue(path, "wrong-type", "must be an object"))
        return False
    actual = set(value)
    for missing in sorted(expected - actual):
        errors.append(issue(f"{path}.{missing}", "missing-field", "is required"))
    for unknown in sorted(actual - expected):
        errors.append(
            issue(
                f"{path}.{unknown}",
                "unknown-field",
                "is not allowed; rejection records fail closed",
            )
        )
    return actual == expected


def require_text(
    value: Any,
    path: str,
    errors: list[dict[str, str]],
    *,
    draft: bool,
    maximum: int = 8000,
) -> None:
    if draft and value is None:
        return
    if not nonblank(value, maximum=maximum):
        errors.append(issue(path, "invalid-text", "must be a nonblank bounded string"))


def validate_file_reference(
    value: Any,
    path: str,
    errors: list[dict[str, str]],
    *,
    draft: bool,
) -> None:
    if draft and value is None:
        return
    if not exact_fields(value, path, {"path", "sha256"}, errors):
        return
    if not nonblank(value.get("path"), maximum=1000):
        errors.append(issue(f"{path}.path", "invalid-path", "must be a nonblank project-relative path"))
    if not isinstance(value.get("sha256"), str) or not SHA256_PATTERN.fullmatch(value["sha256"]):
        errors.append(issue(f"{path}.sha256", "invalid-sha256", "must be a lowercase SHA-256 digest"))


def validate_authority(
    value: Any,
    path: str,
    errors: list[dict[str, str]],
    *,
    draft: bool,
    expected_decision: str,
    owner_id: Any,
) -> None:
    expected = {"accountable_owner_id", "relationship", "first_party", "decision_kind"}
    if not exact_fields(value, path, expected, errors):
        return
    require_text(value.get("accountable_owner_id"), f"{path}.accountable_owner_id", errors, draft=draft, maximum=64)
    relationship = value.get("relationship")
    if not (draft and relationship is None) and relationship != "accountable-owner":
        errors.append(issue(f"{path}.relationship", "invalid-authority", "must be accountable-owner"))
    first_party = value.get("first_party")
    if not (draft and first_party is None) and first_party is not True:
        errors.append(issue(f"{path}.first_party", "not-first-party", "must be true"))
    decision_kind = value.get("decision_kind")
    if not (draft and decision_kind is None) and decision_kind != expected_decision:
        errors.append(issue(f"{path}.decision_kind", "wrong-decision-kind", f"must be {expected_decision}"))
    evidence_owner = value.get("accountable_owner_id")
    if not draft and evidence_owner != owner_id:
        errors.append(issue(f"{path}.accountable_owner_id", "owner-mismatch", "must match accountable_owner.id"))


def validate_owner_evidence(
    value: Any,
    path: str,
    errors: list[dict[str, str]],
    *,
    draft: bool,
    expected_acceptance: str,
    expected_decision: str,
    owner_id: Any,
) -> None:
    expected = {"file", "authority", "verbatim_excerpt", "scope", "acceptance_status"}
    if not exact_fields(value, path, expected, errors):
        return
    validate_file_reference(value.get("file"), f"{path}.file", errors, draft=draft)
    validate_authority(
        value.get("authority"),
        f"{path}.authority",
        errors,
        draft=draft,
        expected_decision=expected_decision,
        owner_id=owner_id,
    )
    require_text(value.get("verbatim_excerpt"), f"{path}.verbatim_excerpt", errors, draft=draft)
    require_text(value.get("scope"), f"{path}.scope", errors, draft=draft)
    acceptance = value.get("acceptance_status")
    if not (draft and acceptance is None) and acceptance != expected_acceptance:
        errors.append(issue(f"{path}.acceptance_status", "wrong-acceptance-status", f"must be {expected_acceptance}"))


def validate_contract_payload(payload: Any) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    """Strictly validate the dependency-free contract shape and lifecycle."""

    errors: list[dict[str, str]] = []
    if not exact_fields(payload, "$", ROOT_FIELDS, errors):
        return errors, payload if isinstance(payload, dict) else None
    assert isinstance(payload, dict)
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(issue("$.schema_version", "unsupported-version", f"must equal {SCHEMA_VERSION}"))
    require_text(payload.get("created_with"), "$.created_with", errors, draft=False, maximum=200)
    if payload.get("classification") not in CLASSIFICATIONS:
        errors.append(issue("$.classification", "invalid-classification", "must be internal or confidential"))
    status_value = payload.get("status")
    if status_value not in LIFECYCLE_STATUSES:
        errors.append(issue("$.status", "invalid-lifecycle", "must be draft, active-reopen, or resolved"))
    draft = status_value == "draft"
    recorded_at = payload.get("recorded_at")
    if not (draft and recorded_at is None):
        if not isinstance(recorded_at, str) or not DATE_PATTERN.fullmatch(recorded_at):
            errors.append(issue("$.recorded_at", "invalid-date", "must be an ISO date or date-time"))

    owner = payload.get("accountable_owner")
    owner_id: Any = None
    if exact_fields(owner, "$.accountable_owner", {"id", "display_name", "authority_basis"}, errors):
        owner_id = owner.get("id")
        if not (draft and owner_id is None):
            if not isinstance(owner_id, str) or not ID_PATTERN.fullmatch(owner_id):
                errors.append(issue("$.accountable_owner.id", "invalid-id", "must be a lowercase portable ID"))
        require_text(owner.get("display_name"), "$.accountable_owner.display_name", errors, draft=draft, maximum=200)
        require_text(owner.get("authority_basis"), "$.accountable_owner.authority_basis", errors, draft=draft)

    candidate = payload.get("candidate")
    candidate_digest: Any = None
    if exact_fields(
        candidate,
        "$.candidate",
        {"project_relative_root", "manifest_algorithm", "manifest_sha256", "files"},
        errors,
    ):
        require_text(candidate.get("project_relative_root"), "$.candidate.project_relative_root", errors, draft=draft, maximum=1000)
        algorithm = candidate.get("manifest_algorithm")
        if not (draft and algorithm is None) and algorithm != MANIFEST_ALGORITHM:
            errors.append(issue("$.candidate.manifest_algorithm", "unsupported-manifest-algorithm", f"must be {MANIFEST_ALGORITHM}"))
        candidate_digest = candidate.get("manifest_sha256")
        if not (draft and candidate_digest is None):
            if not isinstance(candidate_digest, str) or not SHA256_PATTERN.fullmatch(candidate_digest):
                errors.append(issue("$.candidate.manifest_sha256", "invalid-sha256", "must be a lowercase SHA-256 digest"))
        files = candidate.get("files")
        if not isinstance(files, list):
            errors.append(issue("$.candidate.files", "wrong-type", "must be an array"))
        else:
            if not draft and not files:
                errors.append(issue("$.candidate.files", "empty-public-tree", "must name every file in the rejected public tree"))
            if len(files) > MAX_PUBLIC_FILES:
                errors.append(issue("$.candidate.files", "too-many-files", f"may contain at most {MAX_PUBLIC_FILES} entries"))
            seen: set[str] = set()
            order: list[str] = []
            for index, entry in enumerate(files):
                entry_path = f"$.candidate.files[{index}]"
                if not exact_fields(entry, entry_path, {"path", "sha256"}, errors):
                    continue
                path_value = entry.get("path")
                if not nonblank(path_value, maximum=1000):
                    errors.append(issue(f"{entry_path}.path", "invalid-path", "must be a nonblank public-root-relative path"))
                else:
                    order.append(path_value)
                    if path_value in seen:
                        errors.append(issue(f"{entry_path}.path", "duplicate-path", "must be unique"))
                    seen.add(path_value)
                digest = entry.get("sha256")
                if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
                    errors.append(issue(f"{entry_path}.sha256", "invalid-sha256", "must be a lowercase SHA-256 digest"))
            if order != sorted(order):
                errors.append(issue("$.candidate.files", "unsorted-manifest", "must be sorted by the UTF-8 project-relative path"))

    validate_owner_evidence(
        payload.get("owner_evidence"),
        "$.owner_evidence",
        errors,
        draft=draft,
        expected_acceptance="rejected",
        expected_decision="candidate-rejection",
        owner_id=owner_id,
    )

    cluster = payload.get("rejected_relationship_cluster")
    if exact_fields(cluster, "$.rejected_relationship_cluster", {"scope", "applies_to_candidate_manifest_sha256", "observations"}, errors):
        require_text(cluster.get("scope"), "$.rejected_relationship_cluster.scope", errors, draft=draft)
        cluster_digest = cluster.get("applies_to_candidate_manifest_sha256")
        if not (draft and cluster_digest is None):
            if not isinstance(cluster_digest, str) or not SHA256_PATTERN.fullmatch(cluster_digest):
                errors.append(issue("$.rejected_relationship_cluster.applies_to_candidate_manifest_sha256", "invalid-sha256", "must bind the exact candidate manifest"))
            elif cluster_digest != candidate_digest:
                errors.append(issue("$.rejected_relationship_cluster.applies_to_candidate_manifest_sha256", "candidate-binding-mismatch", "must equal candidate.manifest_sha256"))
        observations = cluster.get("observations")
        if not isinstance(observations, dict):
            errors.append(issue("$.rejected_relationship_cluster.observations", "wrong-type", "must be an object"))
        else:
            for unknown in sorted(set(observations) - RELATIONSHIP_AXES):
                errors.append(issue(f"$.rejected_relationship_cluster.observations.{unknown}", "unknown-axis", "is not a scoped relationship axis"))
            if not draft and len(observations) < 2:
                errors.append(issue("$.rejected_relationship_cluster.observations", "insufficient-cluster", "must describe at least two interacting relationship axes"))
            for axis, observation in observations.items():
                require_text(observation, f"$.rejected_relationship_cluster.observations.{axis}", errors, draft=False)
                if isinstance(observation, str) and any(pattern.search(observation) for pattern in GLOBAL_BAN_PATTERNS):
                    errors.append(issue(f"$.rejected_relationship_cluster.observations.{axis}", "global-style-ban", "must describe this candidate relationship, not impose a global style ban"))
        scope = cluster.get("scope")
        if isinstance(scope, str) and any(pattern.search(scope) for pattern in GLOBAL_BAN_PATTERNS):
            errors.append(issue("$.rejected_relationship_cluster.scope", "global-style-ban", "must remain scoped to the bound candidate"))

    list_values: dict[str, list[str]] = {}
    for field in ("protected_foundations", "reopened_decisions"):
        value = payload.get(field)
        if not isinstance(value, list):
            errors.append(issue(f"$.{field}", "wrong-type", "must be an array"))
            continue
        if not draft and not value:
            errors.append(issue(f"$.{field}", "empty-decision-boundary", "must contain at least one bounded decision"))
        normalized: set[str] = set()
        valid_values: list[str] = []
        for index, entry in enumerate(value):
            if not nonblank(entry):
                errors.append(issue(f"$.{field}[{index}]", "invalid-text", "must be a nonblank bounded string"))
                continue
            key = " ".join(entry.casefold().split())
            if key in normalized:
                errors.append(issue(f"$.{field}[{index}]", "duplicate-decision", "duplicates another entry"))
            normalized.add(key)
            valid_values.append(key)
        list_values[field] = valid_values
    overlap = set(list_values.get("protected_foundations", [])) & set(list_values.get("reopened_decisions", []))
    if overlap:
        errors.append(issue("$.reopened_decisions", "decision-boundary-conflict", "a decision cannot be both protected and reopened"))

    replacement = payload.get("replacement_constraints")
    if exact_fields(
        replacement,
        "$.replacement_constraints",
        {"asset_led_required", "photo_free_exception_available", "minimum_evidence", "closure"},
        errors,
    ):
        for field in ("asset_led_required", "photo_free_exception_available"):
            value = replacement.get(field)
            if not (draft and value is None) and not isinstance(value, bool):
                errors.append(issue(f"$.replacement_constraints.{field}", "wrong-type", "must be a boolean"))
        require_text(replacement.get("minimum_evidence"), "$.replacement_constraints.minimum_evidence", errors, draft=draft)
        require_text(replacement.get("closure"), "$.replacement_constraints.closure", errors, draft=draft)

    resolution = payload.get("resolution")
    if exact_fields(
        resolution,
        "$.resolution",
        {"status", "resolved_at", "replacement_candidate_manifest_sha256", "owner_evidence"},
        errors,
    ):
        expected_resolution = "owner-confirmed" if status_value == "resolved" else "pending"
        if resolution.get("status") != expected_resolution:
            errors.append(issue("$.resolution.status", "lifecycle-mismatch", f"must be {expected_resolution} when record status is {status_value}"))
        if status_value == "resolved":
            resolved_at = resolution.get("resolved_at")
            if not isinstance(resolved_at, str) or not DATE_PATTERN.fullmatch(resolved_at):
                errors.append(issue("$.resolution.resolved_at", "invalid-date", "must be an ISO date or date-time"))
            replacement_digest = resolution.get("replacement_candidate_manifest_sha256")
            if not isinstance(replacement_digest, str) or not SHA256_PATTERN.fullmatch(replacement_digest):
                errors.append(issue("$.resolution.replacement_candidate_manifest_sha256", "invalid-sha256", "must bind the accepted replacement candidate"))
            elif replacement_digest == candidate_digest:
                errors.append(issue("$.resolution.replacement_candidate_manifest_sha256", "unchanged-candidate", "must not equal the rejected candidate manifest"))
            validate_owner_evidence(
                resolution.get("owner_evidence"),
                "$.resolution.owner_evidence",
                errors,
                draft=False,
                expected_acceptance="accepted-replacement",
                expected_decision="replacement-acceptance",
                owner_id=owner_id,
            )
        else:
            for field in ("resolved_at", "replacement_candidate_manifest_sha256", "owner_evidence"):
                if resolution.get(field) is not None:
                    errors.append(issue(f"$.resolution.{field}", "premature-resolution", "must remain null until the accountable owner resolves the record"))
    return errors, payload


def is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def portable_path(value: Any, label: str) -> str:
    if not nonblank(value, maximum=1000):
        raise AuditError("invalid-path", f"{label} must be a nonblank project-relative POSIX path.")
    assert isinstance(value, str)
    if "\\" in value or "\x00" in value or any(ord(character) < 32 for character in value):
        raise AuditError("invalid-path", f"{label} must use safe POSIX separators.")
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or not parsed.parts or any(part in {"", ".", ".."} for part in parsed.parts):
        raise AuditError("invalid-path", f"{label} must remain inside the project.")
    return parsed.as_posix()


def project_file(root: Path, value: Any, label: str) -> Path:
    relative = portable_path(value, label)
    path = root.joinpath(*PurePosixPath(relative).parts)
    try:
        root_resolved = root.resolve(strict=True)
        path_resolved = path.resolve(strict=True)
        path_resolved.relative_to(root_resolved)
    except (OSError, ValueError) as exc:
        raise AuditError("unsafe-path", f"{label} does not resolve to a regular project file: {exc}") from exc
    if is_reparse(path) or not path.is_file():
        raise AuditError("unsafe-path", f"{label} must be a regular non-link file.")
    return path


def project_directory(root: Path, value: Any, label: str) -> Path:
    relative = portable_path(value, label)
    path = root.joinpath(*PurePosixPath(relative).parts)
    try:
        root_resolved = root.resolve(strict=True)
        path_resolved = path.resolve(strict=True)
        path_resolved.relative_to(root_resolved)
    except (OSError, ValueError) as exc:
        raise AuditError("unsafe-path", f"{label} does not resolve to a project directory: {exc}") from exc
    if is_reparse(path) or not path.is_dir():
        raise AuditError("unsafe-path", f"{label} must be a regular non-link directory.")
    return path


def hash_file(path: Path, *, maximum: int, label: str) -> tuple[str, int]:
    size = path.stat().st_size
    if size > maximum:
        raise AuditError("file-too-large", f"{label} exceeds the bounded audit size limit.")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest(), size


def canonical_manifest_bytes(entries: list[dict[str, str]]) -> bytes:
    """Return sha256-tab-lf-v1 bytes for already validated entries."""

    ordered = sorted(entries, key=lambda entry: entry["path"])
    return "".join(f"{entry['path']}\t{entry['sha256']}\n" for entry in ordered).encode("utf-8")


def manifest_digest(entries: list[dict[str, str]]) -> str:
    return hashlib.sha256(canonical_manifest_bytes(entries)).hexdigest()


def public_tree_manifest(public_root: Path) -> tuple[list[dict[str, str]], int]:
    entries: list[dict[str, str]] = []
    total = 0
    for current, directories, filenames in os.walk(public_root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in list(directories):
            candidate = current_path / name
            if is_reparse(candidate):
                raise AuditError("public-tree-link", f"Rejected public tree contains a symlink or reparse directory: {candidate.relative_to(public_root).as_posix()}")
        for name in filenames:
            candidate = current_path / name
            relative = candidate.relative_to(public_root).as_posix()
            if is_reparse(candidate) or not candidate.is_file():
                raise AuditError("public-tree-link", f"Rejected public tree contains a non-regular file: {relative}")
            digest, size = hash_file(candidate, maximum=MAX_PUBLIC_FILE_BYTES, label=f"public file {relative}")
            total += size
            if total > MAX_PUBLIC_TREE_BYTES:
                raise AuditError("public-tree-too-large", "Rejected public tree exceeds the cumulative audit size limit.")
            entries.append({"path": relative, "sha256": digest})
            if len(entries) > MAX_PUBLIC_FILES:
                raise AuditError("too-many-files", f"Rejected public tree contains more than {MAX_PUBLIC_FILES} files.")
    entries.sort(key=lambda entry: entry["path"])
    return entries, total


def verify_owner_evidence(root: Path, evidence: dict[str, Any], label: str) -> dict[str, Any]:
    reference = evidence["file"]
    path = project_file(root, reference["path"], f"{label} evidence")
    actual_hash, size = hash_file(path, maximum=MAX_EVIDENCE_BYTES, label=f"{label} evidence")
    if actual_hash != reference["sha256"]:
        raise AuditError("owner-evidence-hash-mismatch", f"{label} evidence SHA-256 does not match the declared file.")
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except UnicodeError as exc:
        raise AuditError("owner-evidence-not-utf8", f"{label} evidence must be UTF-8 text: {exc}") from exc
    if evidence["verbatim_excerpt"] not in text:
        raise AuditError("owner-excerpt-not-found", f"{label} verbatim excerpt is not present exactly in the hash-bound first-party evidence.")
    return {
        "kind": label,
        "path": path.relative_to(root).as_posix(),
        "sha256": actual_hash,
        "bytes": size,
        "accountable_owner_id": evidence["authority"]["accountable_owner_id"],
        "decision_kind": evidence["authority"]["decision_kind"],
    }


def runtime_schema_errors() -> list[dict[str, str]]:
    path = Path(__file__).resolve().parents[1] / "schemas" / "owner-rejection.schema.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [issue("$schema", "runtime-schema-unavailable", f"Packaged schema could not be read: {exc}")]
    errors: list[dict[str, str]] = []
    if not isinstance(payload, dict):
        return [issue("$schema", "runtime-schema-invalid", "Packaged schema root must be an object")]
    if payload.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append(issue("$schema.$schema", "runtime-schema-drift", "must declare JSON Schema draft 2020-12"))
    if set(payload.get("required", [])) != ROOT_FIELDS:
        errors.append(issue("$schema.required", "runtime-schema-drift", "root fields do not match the runtime validator"))
    status = payload.get("properties", {}).get("status", {})
    if set(status.get("enum", [])) != LIFECYCLE_STATUSES:
        errors.append(issue("$schema.properties.status", "runtime-schema-drift", "lifecycle states do not match the runtime validator"))
    algorithm = payload.get("$defs", {}).get("candidate", {}).get("properties", {}).get("manifest_algorithm", {})
    declared_constant = algorithm.get("oneOf", [{}, {}])[1].get("const") if isinstance(algorithm.get("oneOf"), list) and len(algorithm["oneOf"]) > 1 else None
    if declared_constant != MANIFEST_ALGORITHM:
        errors.append(issue("$schema.$defs.candidate.manifest_algorithm", "runtime-schema-drift", "manifest algorithm does not match the runtime validator"))
    return errors


def finalize(report: dict[str, Any]) -> dict[str, Any]:
    report["ready"] = bool(
        report.get("structural_valid")
        and report.get("lifecycle", {}).get("status") in {"active-reopen", "resolved"}
        and not report.get("gaps")
        and not any(entry.get("blocking") for entry in report.get("findings", []))
    )
    return report


def audit_payload(root: Path, payload: Any) -> dict[str, Any]:
    root = root.resolve(strict=True)
    errors, contract = validate_contract_payload(payload)
    errors = runtime_schema_errors() + errors
    report: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "tool_version": TOOL_VERSION,
        "structural_valid": not errors,
        "ready": False,
        "lifecycle": {
            "status": payload.get("status") if isinstance(payload, dict) else None,
            "meaning": "active-reopen preserves the scoped rejection; resolved requires separate hash-bound owner acceptance of a different replacement.",
        },
        "findings": [],
        "gaps": [],
        "evidence": {"verified": [], "bytes": 0},
        "limitations": [
            "This audit verifies declared files, hashes, owner evidence, authority binding, scope, and lifecycle; it does not score visual quality or infer owner identity from prose.",
            "A valid scoped rejection is not a global prohibition on any font, shape, color, effect, layout, or medium.",
        ],
    }
    for error in errors:
        report["findings"].append(
            finding(error["code"], f"{error['path']}: {error['message']}")
        )
    if errors or not isinstance(contract, dict):
        return finalize(report)
    if contract["status"] == "draft":
        report["gaps"].append(
            {
                "code": "truthful-draft",
                "message": "The record is an intentionally unresolved draft and makes no owner-rejection claim.",
            }
        )
        return finalize(report)

    candidate = contract["candidate"]
    try:
        public_root = project_directory(root, candidate["project_relative_root"], "rejected candidate public root")
        actual_entries, public_bytes = public_tree_manifest(public_root)
        declared_entries = candidate["files"]
        declared_digest = manifest_digest(declared_entries)
        actual_digest = manifest_digest(actual_entries)
        if declared_digest != candidate["manifest_sha256"]:
            raise AuditError("manifest-digest-mismatch", "candidate.manifest_sha256 does not match the canonical digest recomputed from the declared manifest entries.")
        declared_by_path = {entry["path"]: entry["sha256"] for entry in declared_entries}
        actual_by_path = {entry["path"]: entry["sha256"] for entry in actual_entries}
        if set(declared_by_path) != set(actual_by_path):
            missing = sorted(set(actual_by_path) - set(declared_by_path))
            stale = sorted(set(declared_by_path) - set(actual_by_path))
            parts: list[str] = []
            if missing:
                parts.append("unlisted public files: " + ", ".join(missing[:20]))
            if stale:
                parts.append("declared files absent from public tree: " + ", ".join(stale[:20]))
            raise AuditError("public-tree-entry-mismatch", "; ".join(parts))
        changed = sorted(path for path in actual_by_path if actual_by_path[path] != declared_by_path[path])
        if changed:
            raise AuditError("public-tree-hash-mismatch", "Rejected candidate file hashes changed: " + ", ".join(changed[:20]))
        if actual_digest != candidate["manifest_sha256"]:
            raise AuditError("public-tree-manifest-mismatch", "The exact public tree does not match the rejected candidate manifest digest.")
        report["evidence"]["verified"].append(
            {
                "kind": "rejected-public-tree",
                "root": public_root.relative_to(root).as_posix(),
                "manifest_algorithm": MANIFEST_ALGORITHM,
                "manifest_sha256": actual_digest,
                "files": len(actual_entries),
                "bytes": public_bytes,
            }
        )
        report["evidence"]["bytes"] += public_bytes
    except AuditError as exc:
        report["findings"].append(finding(exc.code, exc.message))

    try:
        verified = verify_owner_evidence(root, contract["owner_evidence"], "owner-rejection")
        report["evidence"]["verified"].append(verified)
        report["evidence"]["bytes"] += verified["bytes"]
    except AuditError as exc:
        report["findings"].append(finding(exc.code, exc.message))

    if contract["status"] == "resolved":
        try:
            verified = verify_owner_evidence(
                root,
                contract["resolution"]["owner_evidence"],
                "replacement-acceptance",
            )
            report["evidence"]["verified"].append(verified)
            report["evidence"]["bytes"] += verified["bytes"]
        except AuditError as exc:
            report["findings"].append(finding(exc.code, exc.message))
    return finalize(report)


def load_contract(path: Path) -> dict[str, Any]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise AuditError("contract-unreadable", f"Unable to read contract: {exc}") from exc
    if len(data) > MAX_CONTRACT_BYTES:
        raise AuditError("contract-too-large", "Owner-rejection contract exceeds the safe size limit.")
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError("contract-invalid-json", f"Owner-rejection contract is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuditError("contract-invalid-root", "Owner-rejection contract root must be an object.")
    return payload


def output_path(project: Path, value: Any) -> Path:
    relative = portable_path(value, "audit output")
    target = project.joinpath(*PurePosixPath(relative).parts)
    parent = target.parent
    try:
        parent_resolved = parent.resolve(strict=True)
        parent_resolved.relative_to(project.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise AuditError("unsafe-output", f"Audit output parent must be an existing project directory: {exc}") from exc
    if is_reparse(parent) or not parent.is_dir() or (target.exists() and is_reparse(target)):
        raise AuditError("unsafe-output", "Audit output must be a regular project path.")
    return target


def write_json(path: Path, payload: dict[str, Any]) -> None:
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
    except OSError as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise AuditError("output-write-failed", f"Unable to write audit report: {exc}") from exc


def run(project: Path, contract_arg: str) -> tuple[dict[str, Any], int]:
    project = project.resolve(strict=True)
    contract_path = project_file(project, contract_arg, "owner-rejection contract")
    report = audit_payload(project, load_contract(contract_path))
    report["project"] = str(project)
    report["contract"] = contract_path.relative_to(project).as_posix()
    return report, 0 if report["ready"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, nargs="?", default=Path.cwd())
    parser.add_argument("--contract", default=DEFAULT_CONTRACT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-incomplete", action="store_true", help="Write a truthful diagnostic even when the record is draft or invalid.")
    parser.add_argument("--stdout", action="store_true", help="Print the JSON audit report to stdout.")
    args = parser.parse_args()
    try:
        report, readiness_code = run(args.project, args.contract)
        project = args.project.resolve(strict=True)
        path = output_path(project, args.output)
        write_json(path, report)
        if args.stdout:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if args.allow_incomplete else readiness_code
    except AuditError as exc:
        error = {
            "artifact_type": ARTIFACT_TYPE,
            "tool_version": TOOL_VERSION,
            "ready": False,
            "error": {"code": exc.code, "message": exc.message},
        }
        if args.stdout:
            print(json.dumps(error, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(error, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
