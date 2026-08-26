#!/usr/bin/env python3
"""Audit the opt-in Connected Public Experience evidence contract.

The record makes continuity and state authority inspectable. It never scores
visual quality, requires an admin or backend, or infers that a local scenario
is a live public service.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any


ARTIFACT_TYPE = "design-dna-connected-public-experience-audit"
PREBUILD_ARTIFACT_TYPE = "design-dna-connected-public-experience-prebuild-audit"
TOOL_VERSION = "4"
DEFAULT_CONTRACT = ".design-dna/connected-public-experience.json"
DEFAULT_OUTPUT = ".design-dna/evidence/connected-public-experience-audit.json"
MAX_CONTRACT_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_BYTES = 8 * 1024 * 1024
MAX_STATE_BYTES = 2 * 1024 * 1024
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,159}$")
CAPTURE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,47}$")
CAPABILITY_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
APPLICABILITY_STATUSES = {"applicable", "not-applicable", "blocked"}
RECORD_STATUSES = {"draft", "direction-ready", "reviewed", "blocked"}
ROOT_STRATEGIES = {"not-required", "each-root-model", "named-invariant"}
STAFF_STATUSES = {"not-requested", "requested", "blocked"}
OPERATE_MODES = {"not-required", "operate", "blocked"}
FIXTURE_STATUSES = {"none", "approved", "sandbox", "local-fixture"}
FIXTURE_STATUS_PRIVACY_CLASSIFICATIONS = {
    "approved": "sanitized-approved",
    "sandbox": "sandbox",
    "local-fixture": "synthetic",
}
FINAL_STATUSES = {"draft", "complete", "blocked", "not-applicable"}
DELIVERY_STATUSES = {"concept", "demo", "staging", "production"}
CONTENT_STATUSES = {"approved", "scenario", "pending", "prohibited"}
BEHAVIOR_STATUSES = {
    "live", "local-only", "illustrative", "unavailable", "out-of-scope"
}
COVERAGE_ROLES = {
    "direct-entry",
    "action",
    "outcome",
    "recovery-or-continuation",
    "staff-back-office",
}
PROOF_DISPOSITIONS = {"planned", "final-bound", "superseded"}
VERIFICATION_CLASSES = {
    "recorded-review",
    "artifact-bound",
    "independently-verified",
    "live-verified",
}
PROJECT_CONTRAST_MAPPING_STATUSES = {"mapped", "not-applicable"}


class AuditError(RuntimeError):
    """A bounded, user-readable evidence or path failure."""


class FixtureDescriptorSemanticMismatch(AuditError):
    """A hash-bound staff descriptor does not describe its declared fixture."""


def issue(errors: list[dict[str, str]], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def substantive(value: object, minimum: int = 12) -> bool:
    return isinstance(value, str) and len(value.strip()) >= minimum


def normalized_semantic_text(value: object) -> str | None:
    """Compare fixture prose by normalized words, not incidental casing or spacing."""

    if not isinstance(value, str):
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", value).split())
    return normalized.casefold() or None


def valid_id(value: object) -> bool:
    return isinstance(value, str) and ID_PATTERN.fullmatch(value) is not None


def exact_object(
    value: object,
    expected: set[str],
    path: str,
    errors: list[dict[str, str]],
) -> dict[str, object] | None:
    if not isinstance(value, dict) or set(value) != expected:
        issue(errors, "invalid-shape", path, "Must use the packaged object shape.")
        return None
    return value


def exact_object_with_optional(
    value: object,
    required: set[str],
    optional: set[str],
    path: str,
    errors: list[dict[str, str]],
) -> dict[str, object] | None:
    """Accept only named compatibility additions; never an open evidence bag."""

    if (
        not isinstance(value, dict)
        or not required.issubset(value)
        or not set(value).issubset(required | optional)
    ):
        issue(errors, "invalid-shape", path, "Must use the packaged object shape.")
        return None
    return value


def nullable_text(value: object, path: str, errors: list[dict[str, str]]) -> None:
    if value is not None and not substantive(value, 1):
        issue(errors, "invalid-text", path, "Must be null or a nonempty string.")


def validate_file_ref(value: object, path: str, errors: list[dict[str, str]]) -> None:
    if value is None:
        return
    reference = exact_object(value, {"path", "sha256"}, path, errors)
    if reference is None:
        return
    if not isinstance(reference["path"], str) or not reference["path"].strip():
        issue(errors, "invalid-file-path", f"{path}.path", "Must be a nonempty project-relative path.")
    if not isinstance(reference["sha256"], str) or SHA256_PATTERN.fullmatch(reference["sha256"]) is None:
        issue(errors, "invalid-file-sha256", f"{path}.sha256", "Must be a lowercase SHA-256 digest.")


def valid_route(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or "\\" in value
        or "//" in value
        or "?" in value
        or "#" in value
    ):
        return False
    route = PurePosixPath(value)
    return not any(part in {"", ".", ".."} for part in route.parts[1:])


def zoned_datetime(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate_render_review_binding(
    value: object,
    path: str,
    errors: list[dict[str, str]],
) -> None:
    if value is None:
        return
    binding = exact_object(value, {"file", "capture_id"}, path, errors)
    if binding is None:
        return
    validate_file_ref(binding["file"], f"{path}.file", errors)
    if (
        not isinstance(binding["capture_id"], str)
        or CAPTURE_ID_PATTERN.fullmatch(binding["capture_id"]) is None
    ):
        issue(
            errors,
            "invalid-render-capture-id",
            f"{path}.capture_id",
            "Must name a schema-3 rendered-review capture ID.",
        )


def validate_functional_attestation(
    value: object,
    path: str,
    errors: list[dict[str, str]],
) -> None:
    """Validate the structured statement required when no run artifact exists."""

    if value is None:
        return
    attestation = exact_object(
        value,
        {
            "reviewer_id",
            "reviewer_role",
            "observed_at",
            "build_id",
            "route",
            "route_or_state",
            "state_conditions",
            "steps",
            "result",
            "limitations",
            "verification_class",
        },
        path,
        errors,
    )
    if attestation is None:
        return
    for field in ("reviewer_id", "reviewer_role", "route_or_state", "limitations"):
        if not substantive(attestation[field]):
            issue(errors, "invalid-functional-attestation", f"{path}.{field}", "Must be a substantive, accountable value.")
    if not zoned_datetime(attestation["observed_at"]):
        issue(errors, "invalid-functional-attestation-time", f"{path}.observed_at", "Must be an ISO-8601 time with an explicit timezone.")
    if not valid_id(attestation["build_id"]):
        issue(errors, "invalid-functional-attestation-build", f"{path}.build_id", "Must name a stable reviewed build ID.")
    if not valid_route(attestation["route"]):
        issue(errors, "invalid-functional-attestation-route", f"{path}.route", "Must name the exact normalized route observed by this functional review.")
    for field in ("state_conditions", "steps"):
        entries = attestation[field]
        if not isinstance(entries, list) or not entries or not all(substantive(entry) for entry in entries):
            issue(errors, "invalid-functional-attestation", f"{path}.{field}", "Must be a nonempty list of substantive conditions or exact steps.")
    if attestation["result"] not in {"passed", "failed", "blocked"}:
        issue(errors, "invalid-functional-attestation-result", f"{path}.result", "Must record passed, failed, or blocked.")
    if attestation["verification_class"] not in VERIFICATION_CLASSES:
        issue(errors, "invalid-functional-attestation-class", f"{path}.verification_class", "Must distinguish recorded review from artifact, independent, or live verification.")


def validate_staff_admin_split_coherence(
    applicability: dict[str, object] | None,
    staff: dict[str, object] | None,
    closure: dict[str, object] | None,
    errors: list[dict[str, str]],
) -> None:
    """Keep declared staff state coherent with the CPE applicability decision.

    `not-requested` is a true absence, not a way to hide an already-built
    fixture, staff boundary, or staff proof. A CPE not-applicable disposition
    has the additional requirement that the staff split is not-requested, so a
    requested or blocked branch cannot disappear behind the early N/A return.
    """

    if not isinstance(staff, dict):
        return

    not_applicable = (
        isinstance(applicability, dict)
        and applicability.get("status") == "not-applicable"
    )
    not_requested = staff.get("status") == "not-requested"

    if not_applicable and not not_requested:
        issue(
            errors,
            "not-applicable-staff-admin-incompatible",
            "$.staff_admin_split.status",
            "A not-applicable CPE record cannot declare requested or blocked staff/admin work; use applicable closure with staff proof, or mark CPE applicability blocked.",
        )

    # Every not-requested declaration, not only an N/A CPE record, must be a
    # genuinely empty nonstaff branch. This prevents a complete requested-staff
    # record from becoming ready merely by changing its status label.
    if not_requested:
        def nonstaff_incompatible(path: str, message: str) -> None:
            issue(
                errors,
                (
                    "not-applicable-staff-admin-incompatible"
                    if not_applicable
                    else "staff-admin-not-requested-incoherent"
                ),
                path,
                message,
            )

        if staff.get("operate_mode") != "not-required":
            nonstaff_incompatible(
                "$.staff_admin_split.operate_mode",
                "A not-requested staff/admin split can use only not-required Operate mode.",
            )
        for field in ("public_boundary", "back_office_boundary"):
            if staff.get(field) is not None:
                nonstaff_incompatible(
                    f"$.staff_admin_split.{field}",
                    "A not-requested staff/admin split cannot retain a public or back-office boundary.",
                )
        fixture = staff.get("fixture")
        if isinstance(fixture, dict) and (
            fixture.get("status") != "none"
            or any(
                fixture.get(field) is not None
                for field in ("authority", "content_or_state", "boundary", "descriptor")
            )
        ):
            nonstaff_incompatible(
                "$.staff_admin_split.fixture",
                "A not-requested staff/admin split can carry no fixture: use status none with null fixture fields and no descriptor.",
            )
        if staff.get("final_evidence") is not None:
            nonstaff_incompatible(
                "$.staff_admin_split.final_evidence",
                "A not-requested staff/admin split can carry no mapped staff/admin final evidence.",
            )
        if isinstance(closure, dict):
            for kind in ("rendered_evidence", "functional_path_evidence"):
                entries = closure.get(kind)
                if not isinstance(entries, list):
                    continue
                for index, entry in enumerate(entries):
                    if (
                        isinstance(entry, dict)
                        and isinstance(entry.get("coverage"), list)
                        and "staff-back-office" in entry["coverage"]
                    ):
                        nonstaff_incompatible(
                            f"$.final_closure.{kind}[{index}].coverage",
                            "A not-requested staff/admin split can carry no final staff-back-office evidence coverage.",
                        )

def validate_contract_payload(payload: object) -> tuple[list[dict[str, str]], dict[str, object] | None]:
    """Validate planning-safe shape; readiness semantics stay in audit_payload."""

    errors: list[dict[str, str]] = []
    root = exact_object(
        payload,
        {
            "schema_version", "created_with", "record_status", "classification",
            "applicability", "pre_direction_constraints",
            "selected_root_continuity", "root_variation", "staff_admin_split",
            "final_closure",
        },
        "$",
        errors,
    )
    if root is None:
        return errors, None
    if root["schema_version"] != 1:
        issue(errors, "unsupported-schema", "$.schema_version", "Must be schema version 1.")
    if not substantive(root["created_with"], 1):
        issue(errors, "invalid-created-with", "$.created_with", "Must name the creating Design DNA version.")
    if root["record_status"] not in RECORD_STATUSES:
        issue(
            errors,
            "invalid-record-status",
            "$.record_status",
            "Must be draft, direction-ready, reviewed, or blocked.",
        )
    if root["classification"] not in {"internal", "confidential"}:
        issue(errors, "invalid-classification", "$.classification", "Must be internal or confidential.")

    applicability = exact_object(
        root["applicability"],
        {"status", "reason", "blocking_dependency", "next_action"},
        "$.applicability",
        errors,
    )
    if applicability is not None:
        if applicability["status"] not in APPLICABILITY_STATUSES:
            issue(errors, "invalid-applicability", "$.applicability.status", "Must be applicable, not-applicable, or blocked.")
        for field in ("reason", "blocking_dependency", "next_action"):
            nullable_text(applicability[field], f"$.applicability.{field}", errors)

    pre = exact_object(
        root["pre_direction_constraints"],
        {"direct_entry_questions", "truth_and_entity_constraints"},
        "$.pre_direction_constraints",
        errors,
    )
    if pre is not None:
        questions = pre["direct_entry_questions"]
        if not isinstance(questions, list):
            issue(errors, "invalid-direct-entry-questions", "$.pre_direction_constraints.direct_entry_questions", "Must be an array.")
        else:
            for index, entry in enumerate(questions):
                item = exact_object(entry, {"entry", "question"}, f"$.pre_direction_constraints.direct_entry_questions[{index}]", errors)
                if item is not None:
                    for field in ("entry", "question"):
                        nullable_text(item[field], f"$.pre_direction_constraints.direct_entry_questions[{index}].{field}", errors)
        constraints = pre["truth_and_entity_constraints"]
        if not isinstance(constraints, list):
            issue(errors, "invalid-truth-constraints", "$.pre_direction_constraints.truth_and_entity_constraints", "Must be an array.")
        else:
            for index, entry in enumerate(constraints):
                item = exact_object(entry, {"subject", "constraint", "authority"}, f"$.pre_direction_constraints.truth_and_entity_constraints[{index}]", errors)
                if item is not None:
                    for field in ("subject", "constraint", "authority"):
                        nullable_text(item[field], f"$.pre_direction_constraints.truth_and_entity_constraints[{index}].{field}", errors)

    selected = exact_object(
        root["selected_root_continuity"],
        {
            "selected_root_id", "continuity_model", "handoffs_or_resets",
            "meaningful_path", "state_authority_crosswalk", "proof_plan",
        },
        "$.selected_root_continuity",
        errors,
    )
    if selected is not None:
        selected_id = selected["selected_root_id"]
        if selected_id is not None and not valid_id(selected_id):
            issue(errors, "invalid-selected-root", "$.selected_root_continuity.selected_root_id", "Must be null or a stable root ID.")
        nullable_text(selected["continuity_model"], "$.selected_root_continuity.continuity_model", errors)
        handoffs = selected["handoffs_or_resets"]
        if not isinstance(handoffs, list):
            issue(errors, "invalid-handoffs", "$.selected_root_continuity.handoffs_or_resets", "Must be an array.")
        else:
            for index, entry in enumerate(handoffs):
                item = exact_object(entry, {"from", "to", "carry_or_reset", "visitor_reason"}, f"$.selected_root_continuity.handoffs_or_resets[{index}]", errors)
                if item is not None:
                    for field in ("from", "to", "carry_or_reset", "visitor_reason"):
                        nullable_text(item[field], f"$.selected_root_continuity.handoffs_or_resets[{index}].{field}", errors)
        path = exact_object(selected["meaningful_path"], {"arrival", "decision", "action", "outcome", "recovery_or_continuation"}, "$.selected_root_continuity.meaningful_path", errors)
        if path is not None:
            for field in path:
                nullable_text(path[field], f"$.selected_root_continuity.meaningful_path.{field}", errors)
        crosswalk = selected["state_authority_crosswalk"]
        if not isinstance(crosswalk, list):
            issue(errors, "invalid-crosswalk", "$.selected_root_continuity.state_authority_crosswalk", "Must be an array.")
        else:
            for index, entry in enumerate(crosswalk):
                item = exact_object(entry, {"subject", "delivery", "content", "behavior", "authority"}, f"$.selected_root_continuity.state_authority_crosswalk[{index}]", errors)
                if item is None:
                    continue
                nullable_text(item["subject"], f"$.selected_root_continuity.state_authority_crosswalk[{index}].subject", errors)
                nullable_text(item["authority"], f"$.selected_root_continuity.state_authority_crosswalk[{index}].authority", errors)
                if item["delivery"] not in DELIVERY_STATUSES:
                    issue(errors, "invalid-delivery-status", f"$.selected_root_continuity.state_authority_crosswalk[{index}].delivery", "Use concept, demo, staging, or production.")
                if item["content"] not in CONTENT_STATUSES:
                    issue(errors, "invalid-content-status", f"$.selected_root_continuity.state_authority_crosswalk[{index}].content", "Use approved, scenario, pending, or prohibited.")
                if item["behavior"] not in BEHAVIOR_STATUSES:
                    issue(errors, "invalid-behavior-status", f"$.selected_root_continuity.state_authority_crosswalk[{index}].behavior", "Use live, local-only, illustrative, unavailable, or out-of-scope.")
        proof = exact_object(selected["proof_plan"], {"rendered", "functional"}, "$.selected_root_continuity.proof_plan", errors)
        if proof is not None:
            for kind in ("rendered", "functional"):
                items = proof[kind]
                if not isinstance(items, list):
                    issue(errors, "invalid-proof-plan", f"$.selected_root_continuity.proof_plan.{kind}", "Must be an array.")
                    continue
                for index, entry in enumerate(items):
                    item = exact_object_with_optional(
                        entry,
                        {"id", "purpose"},
                        {"final_disposition", "superseded_reason"},
                        f"$.selected_root_continuity.proof_plan.{kind}[{index}]",
                        errors,
                    )
                    if item is not None:
                        if not valid_id(item["id"]):
                            issue(errors, "invalid-proof-id", f"$.selected_root_continuity.proof_plan.{kind}[{index}].id", "Must be a stable ID.")
                        nullable_text(item["purpose"], f"$.selected_root_continuity.proof_plan.{kind}[{index}].purpose", errors)
                        if (
                            "final_disposition" in item
                            and item["final_disposition"] not in PROOF_DISPOSITIONS
                        ):
                            issue(errors, "invalid-proof-disposition", f"$.selected_root_continuity.proof_plan.{kind}[{index}].final_disposition", "Must be planned, final-bound, or superseded.")
                        if "superseded_reason" in item:
                            nullable_text(item["superseded_reason"], f"$.selected_root_continuity.proof_plan.{kind}[{index}].superseded_reason", errors)

    variation = exact_object_with_optional(
        root["root_variation"],
        {"strategy", "detail", "entries"},
        {"project_contrast_mapping"},
        "$.root_variation",
        errors,
    )
    if variation is not None:
        if variation["strategy"] not in ROOT_STRATEGIES:
            issue(errors, "invalid-root-strategy", "$.root_variation.strategy", "Must be not-required, each-root-model, or named-invariant.")
        nullable_text(variation["detail"], "$.root_variation.detail", errors)
        entries = variation["entries"]
        if not isinstance(entries, list):
            issue(errors, "invalid-root-entries", "$.root_variation.entries", "Must be an array.")
        else:
            for index, entry in enumerate(entries):
                item = exact_object(entry, {"root_id", "continuity_model", "named_invariant"}, f"$.root_variation.entries[{index}]", errors)
                if item is not None:
                    if not valid_id(item["root_id"]):
                        issue(errors, "invalid-root-id", f"$.root_variation.entries[{index}].root_id", "Must be a stable root ID.")
                    nullable_text(item["continuity_model"], f"$.root_variation.entries[{index}].continuity_model", errors)
                    nullable_text(item["named_invariant"], f"$.root_variation.entries[{index}].named_invariant", errors)
        if "project_contrast_mapping" in variation:
            mapping = variation["project_contrast_mapping"]
            if mapping is not None:
                item = exact_object(
                    mapping,
                    {"status", "selected_root_id", "counter_root_id", "not_applicable_reason"},
                    "$.root_variation.project_contrast_mapping",
                    errors,
                )
                if item is not None:
                    if item["status"] not in PROJECT_CONTRAST_MAPPING_STATUSES:
                        issue(errors, "invalid-project-contrast-mapping", "$.root_variation.project_contrast_mapping.status", "Must be mapped or not-applicable.")
                    for field in ("selected_root_id", "counter_root_id"):
                        if item[field] is not None and not valid_id(item[field]):
                            issue(errors, "invalid-project-contrast-root", f"$.root_variation.project_contrast_mapping.{field}", "Must be null or a stable root ID.")
                    nullable_text(item["not_applicable_reason"], "$.root_variation.project_contrast_mapping.not_applicable_reason", errors)

    staff = exact_object_with_optional(
        root["staff_admin_split"],
        {"status", "public_boundary", "back_office_boundary", "operate_mode", "fixture"},
        {"final_evidence"},
        "$.staff_admin_split",
        errors,
    )
    if staff is not None:
        if staff["status"] not in STAFF_STATUSES:
            issue(errors, "invalid-staff-status", "$.staff_admin_split.status", "Must be not-requested, requested, or blocked.")
        if staff["operate_mode"] not in OPERATE_MODES:
            issue(errors, "invalid-operate-mode", "$.staff_admin_split.operate_mode", "Must be not-required, operate, or blocked.")
        for field in ("public_boundary", "back_office_boundary"):
            nullable_text(staff[field], f"$.staff_admin_split.{field}", errors)
        fixture = exact_object_with_optional(
            staff["fixture"],
            {"status", "authority", "content_or_state", "boundary"},
            {"descriptor"},
            "$.staff_admin_split.fixture",
            errors,
        )
        if fixture is not None:
            if fixture["status"] not in FIXTURE_STATUSES:
                issue(errors, "invalid-fixture-status", "$.staff_admin_split.fixture.status", "Must be none, approved, sandbox, or local-fixture.")
            for field in ("authority", "content_or_state", "boundary"):
                nullable_text(fixture[field], f"$.staff_admin_split.fixture.{field}", errors)
            if "descriptor" in fixture:
                validate_file_ref(fixture["descriptor"], "$.staff_admin_split.fixture.descriptor", errors)
        if "final_evidence" in staff and staff["final_evidence"] is not None:
            final_evidence = exact_object(
                staff["final_evidence"],
                {"rendered_evidence_id", "functional_evidence_id"},
                "$.staff_admin_split.final_evidence",
                errors,
            )
            if final_evidence is not None:
                for field in ("rendered_evidence_id", "functional_evidence_id"):
                    if not valid_id(final_evidence[field]):
                        issue(errors, "invalid-staff-final-evidence", f"$.staff_admin_split.final_evidence.{field}", "Must name a stable final evidence ID.")

    closure = exact_object(root["final_closure"], {"status", "reviewed_build_id", "rendered_evidence", "functional_path_evidence", "proof_coverage", "conclusion", "limitations"}, "$.final_closure", errors)
    if closure is not None:
        if closure["status"] not in FINAL_STATUSES:
            issue(errors, "invalid-final-status", "$.final_closure.status", "Must be draft, complete, blocked, or not-applicable.")
        if closure["reviewed_build_id"] is not None and not valid_id(closure["reviewed_build_id"]):
            issue(errors, "invalid-reviewed-build", "$.final_closure.reviewed_build_id", "Must be null or a stable build ID.")
        for field in ("conclusion", "limitations"):
            nullable_text(closure[field], f"$.final_closure.{field}", errors)
        rendered = closure["rendered_evidence"]
        if not isinstance(rendered, list):
            issue(errors, "invalid-rendered-evidence", "$.final_closure.rendered_evidence", "Must be an array.")
        else:
            for index, entry in enumerate(rendered):
                item = exact_object_with_optional(
                    entry,
                    {"id", "route_or_state", "coverage", "file", "observation"},
                    {"route", "render_review"},
                    f"$.final_closure.rendered_evidence[{index}]",
                    errors,
                )
                if item is None:
                    continue
                if not valid_id(item["id"]):
                    issue(errors, "invalid-rendered-evidence-id", f"$.final_closure.rendered_evidence[{index}].id", "Must be a stable ID.")
                for field in ("route_or_state", "observation"):
                    nullable_text(item[field], f"$.final_closure.rendered_evidence[{index}].{field}", errors)
                validate_coverage(item["coverage"], f"$.final_closure.rendered_evidence[{index}].coverage", errors)
                validate_file_ref(item["file"], f"$.final_closure.rendered_evidence[{index}].file", errors)
                if "route" in item and item["route"] is not None and not valid_route(item["route"]):
                    issue(errors, "invalid-rendered-route", f"$.final_closure.rendered_evidence[{index}].route", "Must be a normalized project route beginning with '/'.")
                if "render_review" in item:
                    validate_render_review_binding(item["render_review"], f"$.final_closure.rendered_evidence[{index}].render_review", errors)
        functional = closure["functional_path_evidence"]
        if not isinstance(functional, list):
            issue(errors, "invalid-functional-evidence", "$.final_closure.functional_path_evidence", "Must be an array.")
        else:
            for index, entry in enumerate(functional):
                item = exact_object_with_optional(
                    entry,
                    {"id", "coverage", "result", "artifact", "recorded_result"},
                    {"attestation"},
                    f"$.final_closure.functional_path_evidence[{index}]",
                    errors,
                )
                if item is None:
                    continue
                if not valid_id(item["id"]):
                    issue(errors, "invalid-functional-evidence-id", f"$.final_closure.functional_path_evidence[{index}].id", "Must be a stable ID.")
                validate_coverage(item["coverage"], f"$.final_closure.functional_path_evidence[{index}].coverage", errors)
                if item["result"] not in {"not-run", "passed", "failed", "blocked"}:
                    issue(errors, "invalid-functional-result", f"$.final_closure.functional_path_evidence[{index}].result", "Must be not-run, passed, failed, or blocked.")
                validate_file_ref(item["artifact"], f"$.final_closure.functional_path_evidence[{index}].artifact", errors)
                nullable_text(item["recorded_result"], f"$.final_closure.functional_path_evidence[{index}].recorded_result", errors)
                if "attestation" in item:
                    validate_functional_attestation(item["attestation"], f"$.final_closure.functional_path_evidence[{index}].attestation", errors)
        coverage = exact_object(closure["proof_coverage"], {"direct_entry_evidence_ids", "recovery_or_continuation_evidence_ids"}, "$.final_closure.proof_coverage", errors)
        if coverage is not None:
            for field in coverage:
                values = coverage[field]
                if not isinstance(values, list) or not all(valid_id(value) for value in values):
                    issue(errors, "invalid-proof-coverage", f"$.final_closure.proof_coverage.{field}", "Must be an array of stable evidence IDs.")
    validate_staff_admin_split_coherence(
        applicability,
        staff,
        closure,
        errors,
    )
    return errors, root if not errors else None


def validate_coverage(value: object, path: str, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item in COVERAGE_ROLES for item in value
    ) or len(value) != len(set(value)):
        issue(errors, "invalid-coverage", path, "Must be a unique list of packaged evidence roles.")


def gap(gaps: list[dict[str, str]], code: str, message: str) -> None:
    gaps.append({"code": code, "message": message})


def portable_project_path(value: object, label: str) -> str:
    """Normalize one portable relative path without allowing Windows escapes."""

    if not isinstance(value, str) or not value or len(value) > 1000:
        raise AuditError(f"{label} must be a bounded nonempty project-relative path.")
    if (
        value.startswith(("/", "\\"))
        or "\\" in value
        or ":" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise AuditError(f"{label} must not contain absolute, dot, dot-dot, backslash, drive, or empty path components.")
    relative = PurePosixPath(value)
    if relative.is_absolute() or not relative.parts:
        raise AuditError(f"{label} must be a portable project-relative path.")
    return relative.as_posix()


def safe_project_file(root: Path, value: object, label: str) -> Path:
    """Resolve a project-relative ordinary file while refusing links and escapes."""

    relative = portable_project_path(value, label)
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    cursor = root
    for part in PurePosixPath(relative).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise AuditError(f"{label} must not traverse a symbolic-link or reparse-point component.")
    try:
        resolved_root = root.resolve(strict=True)
        resolved_candidate = candidate.resolve(strict=True)
        resolved_candidate.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise AuditError(f"{label} is outside or unavailable from the project root.") from exc
    if not resolved_candidate.is_file() or candidate.is_symlink() or resolved_candidate.is_symlink():
        raise AuditError(f"{label} must be an ordinary project file, not a link or directory.")
    return resolved_candidate


def bound_evidence_bytes(root: Path, reference: object, label: str) -> tuple[str, Path, bytes, str]:
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise AuditError(f"{label} must contain an exact file path and SHA-256 binding.")
    expected = reference.get("sha256")
    if not isinstance(expected, str) or SHA256_PATTERN.fullmatch(expected) is None:
        raise AuditError(f"{label} has an invalid SHA-256 binding.")
    relative = portable_project_path(reference.get("path"), f"{label}.path")
    path = safe_project_file(root, relative, label)
    try:
        before = path.stat()
        payload = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        raise AuditError(f"Unable to read {label}: {exc}") from exc
    if (
        len(payload) < 1
        or len(payload) > MAX_EVIDENCE_BYTES
        or before.st_size != len(payload)
        or after.st_size != len(payload)
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        raise AuditError(f"{label} is empty, oversized, or changed while it was read.")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected:
        raise AuditError(f"{label} SHA-256 does not match its recorded evidence.")
    return relative, path, payload, digest


def safe_evidence_file(root: Path, reference: object, label: str) -> tuple[str, str] | None:
    try:
        relative, _path, _payload, digest = bound_evidence_bytes(root, reference, label)
    except AuditError:
        return None
    return relative, digest


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_json_object(path: Path, label: str, *, maximum: int) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise AuditError(f"{label} must be an ordinary JSON file.")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise AuditError(f"Unable to read {label}: {exc}") from exc
    if not payload or len(payload) > maximum:
        raise AuditError(f"{label} is empty or exceeds the safe size limit.")
    try:
        decoded = json.loads(payload.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise AuditError(f"{label} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise AuditError(f"{label} must contain a JSON object.")
    return decoded


def direction_challenge_context(project: Path) -> tuple[set[str], str | None]:
    """Return declared roots and the actively chosen root without guessing."""

    payload = load_json_object(
        project / ".design-dna" / "direction-challenge.json",
        "Direction Challenge record",
        maximum=MAX_CONTRACT_BYTES,
    )
    roots = payload.get("roots")
    if not isinstance(roots, list):
        raise AuditError("Direction Challenge record does not expose declared roots.")
    root_ids = {
        item.get("id")
        for item in roots
        if isinstance(item, dict) and valid_id(item.get("id"))
    }
    if not root_ids:
        raise AuditError("Direction Challenge record has no usable root identities.")
    selection = payload.get("selection")
    chosen = selection.get("chosen_root_id") if isinstance(selection, dict) else None
    if chosen is not None and not valid_id(chosen):
        raise AuditError("Direction Challenge selected root is not a stable root ID.")
    return root_ids, chosen


def load_render_review_adapter() -> Any:
    """Load the Project Contrast schema-3 verifier by path, not import state."""

    module_name = "_design_dna_cpe_schema3_render_review_adapter"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    adapter_path = Path(__file__).with_name("project_contrast_audit.py")
    if not adapter_path.is_file() or adapter_path.is_symlink():
        raise AuditError("The packaged schema-3 rendered-review verifier is unavailable.")
    specification = importlib.util.spec_from_loader(
        module_name,
        loader=None,
        origin=str(adapter_path),
    )
    if specification is None:
        raise AuditError("The packaged schema-3 rendered-review verifier could not be loaded.")
    module = importlib.util.module_from_spec(specification)
    module.__file__ = str(adapter_path)
    sys.modules[module_name] = module
    try:
        source = adapter_path.read_bytes()
        code = compile(source, str(adapter_path), "exec", dont_inherit=True)
        exec(code, module.__dict__)
    except (OSError, TypeError, ValueError, ImportError) as exc:
        sys.modules.pop(module_name, None)
        raise AuditError(f"The packaged schema-3 rendered-review verifier could not initialize: {exc}") from exc
    return module


def rendered_screenshot_path(adapter: Any, report_relative: object, screenshot_path: object, label: str) -> str:
    if not isinstance(report_relative, str) or not isinstance(screenshot_path, str):
        raise AuditError(f"{label} has no portable schema-3 screenshot path.")
    combined = (PurePosixPath(report_relative).parent / PurePosixPath(screenshot_path)).as_posix()
    return adapter.portable_path(combined, f"{label}.screenshot.path")


def verify_rendered_evidence(
    project: Path,
    entry: dict[str, object],
    reviewed_build_id: object,
    adapter: Any,
    budget: Any,
    cache: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, object]:
    """Bind a final CPE row to one decoded schema-3 screenshot and build."""

    evidence_id = entry.get("id", "unknown")
    label = f"rendered evidence {evidence_id}"
    binding = entry.get("render_review")
    if not isinstance(binding, dict):
        raise AuditError(f"{label} must bind a schema-3 rendered-review report and capture ID.")
    reference = binding.get("file")
    capture_id = binding.get("capture_id")
    if not isinstance(reference, dict) or not isinstance(capture_id, str):
        raise AuditError(f"{label} has an incomplete schema-3 rendered-review binding.")
    report_path = reference.get("path")
    report_sha = reference.get("sha256")
    if not isinstance(report_path, str) or not isinstance(report_sha, str):
        raise AuditError(f"{label} has an invalid schema-3 rendered-review file reference.")
    cache_key = (report_path, report_sha)
    if cache_key not in cache:
        try:
            cache[cache_key] = adapter.load_schema3_render_review(
                project,
                reference,
                f"{label}.render_review.file",
                budget,
            )
        except Exception as exc:
            raise AuditError(f"{label} does not bind a valid path-bound schema-3 rendered-review package: {exc}") from exc
    review = cache[cache_key]
    if review.get("build_id") != reviewed_build_id:
        raise AuditError(f"{label} schema-3 build identity does not equal final_closure.reviewed_build_id.")
    captures = review.get("captures_by_id")
    if not isinstance(captures, dict):
        raise AuditError(f"{label} cannot inspect schema-3 rendered captures.")
    capture = captures.get(capture_id)
    if not isinstance(capture, dict):
        raise AuditError(f"{label} names an unknown schema-3 capture ID {capture_id!r}.")
    report_relative = review.get("report_relative_path")
    screenshot = capture.get("screenshot")
    if not isinstance(screenshot, dict):
        raise AuditError(f"{label} capture has no schema-3 PNG metadata.")
    try:
        screenshot_relative = rendered_screenshot_path(
            adapter, report_relative, screenshot.get("path"), label,
        )
        screenshot_reference = {
            "path": screenshot_relative,
            "sha256": screenshot.get("sha256"),
        }
        verification = adapter.verify_file_reference(
            project,
            screenshot_reference,
            f"{label}.schema3-screenshot",
            budget,
            capture=True,
        )
    except Exception as exc:
        raise AuditError(f"{label} capture is not a readable decoded schema-3 PNG artifact: {exc}") from exc
    file_reference = entry.get("file")
    if (
        not isinstance(file_reference, dict)
        or file_reference.get("path") != screenshot_relative
        or file_reference.get("sha256") != screenshot.get("sha256")
    ):
        raise AuditError(f"{label}.file must exactly bind the named schema-3 screenshot path and SHA-256.")
    if (
        verification.get("sha256") != screenshot.get("sha256")
        or verification.get("width") != screenshot.get("pixel_width")
        or verification.get("height") != screenshot.get("pixel_height")
    ):
        raise AuditError(f"{label} decoded PNG metadata does not match the named schema-3 capture.")
    declared_route = entry.get("route")
    actual_route = adapter.rendered_capture_route_path(capture.get("final_url"))
    if declared_route != actual_route:
        raise AuditError(f"{label} declared route does not match its schema-3 capture route.")
    return {
        "id": evidence_id,
        "capture_id": capture_id,
        "build_id": reviewed_build_id,
        "path": verification.get("path"),
        "sha256": verification.get("sha256"),
        "route": actual_route,
    }


def validate_fixture_descriptor(
    project: Path,
    reference: object,
    fixture: dict[str, object],
    label: str,
) -> None:
    """Require a privacy-safe descriptor that actually describes its staff fixture."""

    relative, _path, payload, _digest = bound_evidence_bytes(project, reference, label)
    if not relative.casefold().endswith(".json"):
        raise AuditError(f"{label} must be a privacy-safe JSON fixture descriptor.")
    try:
        descriptor = json.loads(payload.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise AuditError(f"{label} is not valid UTF-8 JSON: {exc}") from exc
    expected = {
        "schema_version",
        "privacy_classification",
        "contains_personal_data",
        "meaningful_state",
        "record_count",
        "authority",
        "boundary",
    }
    if not isinstance(descriptor, dict) or set(descriptor) != expected:
        raise AuditError(f"{label} must use the packaged privacy-safe fixture descriptor shape.")
    if (
        descriptor.get("schema_version") != 1
        or descriptor.get("privacy_classification") not in {"synthetic", "sanitized-approved", "sandbox"}
        or descriptor.get("contains_personal_data") is not False
        or not substantive(descriptor.get("meaningful_state"))
        or not isinstance(descriptor.get("record_count"), int)
        or isinstance(descriptor.get("record_count"), bool)
        or descriptor.get("record_count", 0) < 1
        or not substantive(descriptor.get("authority"))
        or not substantive(descriptor.get("boundary"))
    ):
        raise AuditError(f"{label} must declare non-personal, meaningful, nonempty fixture state with authority and boundary.")

    expected_classification = FIXTURE_STATUS_PRIVACY_CLASSIFICATIONS.get(
        fixture.get("status")
    )
    expected_fields = {
        "meaningful_state": fixture.get("content_or_state"),
        "authority": fixture.get("authority"),
        "boundary": fixture.get("boundary"),
    }
    mismatches = [
        field
        for field, expected_value in expected_fields.items()
        if normalized_semantic_text(descriptor.get(field))
        != normalized_semantic_text(expected_value)
    ]
    if (
        expected_classification is not None
        and descriptor.get("privacy_classification") != expected_classification
    ):
        mismatches.append("privacy_classification")
    if mismatches:
        fields = ", ".join(sorted(mismatches))
        raise FixtureDescriptorSemanticMismatch(
            f"{label} must semantically match staff_admin_split.fixture for "
            f"{fields}; a hash-bound descriptor cannot describe unrelated fixture prose."
        )


def load_active_capabilities_from_state(project: Path) -> set[str] | None:
    """Read only the explicit capability selection from a safe state record."""

    path = project / ".design-dna" / "state.json"
    if not path.exists():
        return None
    payload = load_json_object(path, "state.json", maximum=MAX_STATE_BYTES)
    contract = payload.get("evidence_contract")
    capabilities = contract.get("applicable_capabilities") if isinstance(contract, dict) else None
    records = payload.get("records")
    if (
        not isinstance(capabilities, list)
        or not all(isinstance(item, str) and CAPABILITY_PATTERN.fullmatch(item) for item in capabilities)
        or len(capabilities) != len(set(capabilities))
        or not isinstance(records, list)
        or not all(isinstance(item, str) and CAPABILITY_PATTERN.fullmatch(item) for item in records)
        or len(records) != len(set(records))
    ):
        raise AuditError("state.json does not expose safe records and explicit applicable_capabilities selections.")
    if "connected-public-experience" in capabilities and "connected-public-experience" not in records:
        raise AuditError("state.json activates Connected Public Experience without listing its canonical record.")
    return set(capabilities)


def safe_output_path(project: Path, output: str) -> Path:
    """Validate containment before creating a report directory or replacing data."""

    relative = portable_project_path(output, "audit output")
    root = project.resolve(strict=True)
    target = project.joinpath(*PurePosixPath(relative).parts)
    # Inspect every existing component before any mkdir so a malformed path
    # cannot create or escape an outside directory as a side effect.
    cursor = project
    for part in PurePosixPath(relative).parts[:-1]:
        cursor = cursor / part
        if cursor.exists():
            if cursor.is_symlink() or not cursor.is_dir():
                raise AuditError("Audit output parent must use existing regular directories only.")
            try:
                cursor.resolve(strict=True).relative_to(root)
            except (OSError, ValueError) as exc:
                raise AuditError("Audit output parent must remain inside the project root.") from exc
    if target.exists() and target.is_symlink():
        raise AuditError("Audit output may not replace a symbolic-link or reparse-point target.")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.parent.resolve(strict=True).relative_to(root)
    except (OSError, ValueError) as exc:
        raise AuditError("Audit output parent escaped the project root during creation.") from exc
    return target


def audit_prebuild_payload(
    project: Path,
    payload: object,
    active_capabilities: set[str] | frozenset[str] | tuple[str, ...] = (),
    *,
    capability_context: str = "caller",
) -> dict[str, object]:
    """Return a no-write implementation gate for the connected experience plan.

    This deliberately stops before final-closure evidence. A project can earn
    ``direction-ready`` only after applicability and the selected public path
    are resolved; final ``reviewed`` readiness still belongs to
    :func:`audit_payload` after implementation and evidence capture.
    """

    errors, contract = validate_contract_payload(payload)
    report: dict[str, object] = {
        "artifact_type": PREBUILD_ARTIFACT_TYPE,
        "tool_version": TOOL_VERSION,
        "phase": "prebuild",
        "automatic_aesthetic_pass": False,
        "structural_valid": not errors,
        "ready": False,
        "implementation_authorized": False,
        "findings": [],
        "gaps": [],
        "limitations": [
            "This no-write gate checks whether connected public continuity is resolved enough to begin implementation; it does not approve visual quality, claims, security, live operation, or production release.",
            "A prebuild pass does not satisfy final closure. Use the final Connected Public Experience readiness audit after rendering and functional verification.",
        ],
    }
    findings: list[dict[str, object]] = report["findings"]  # type: ignore[assignment]
    gaps: list[dict[str, str]] = report["gaps"]  # type: ignore[assignment]
    if errors or contract is None:
        findings.extend({**entry, "blocking": True} for entry in errors)
        return report

    capabilities = set(active_capabilities)
    report["active_capabilities"] = sorted(capabilities)
    report["capability_context"] = capability_context
    if capability_context == "missing":
        gap(
            gaps,
            "active-capability-context-missing",
            "Prebuild auditing needs a safe state.json capability selection or an explicit active capability context.",
        )
    elif capability_context == "mismatch":
        gap(
            gaps,
            "active-capability-context-mismatch",
            "Explicit capabilities do not equal the safe state.json selection; implementation cannot use an overridden project context.",
        )
    elif capability_context == "invalid-state":
        gap(
            gaps,
            "active-capability-context-invalid",
            "state.json cannot safely provide the active capability selection; implementation cannot infer the missing project context.",
        )
    if "connected-public-experience" not in capabilities:
        gap(
            gaps,
            "connected-capability-not-active",
            "Connected Public Experience cannot authorize implementation unless it is explicitly active in the project capability context.",
        )

    record_status = contract["record_status"]
    report["record_status"] = record_status
    if record_status == "draft":
        gap(
            gaps,
            "record-not-direction-ready",
            "A draft Connected Public Experience record cannot authorize implementation; resolve it and mark it direction-ready.",
        )
    elif record_status == "blocked":
        gap(
            gaps,
            "record-blocked",
            "A blocked Connected Public Experience record cannot authorize implementation.",
        )

    applicability = contract["applicability"]
    assert isinstance(applicability, dict)
    status = applicability["status"]
    report["applicability"] = status
    if status == "blocked":
        for field in ("reason", "blocking_dependency", "next_action"):
            if not substantive(applicability[field]):
                gap(
                    gaps,
                    f"blocked-{field}-missing",
                    f"Blocked applicability needs a substantive {field.replace('_', ' ')}.",
                )
        gap(
            gaps,
            "connected-public-experience-blocked",
            "Connected public applicability remains unresolved; do not begin implementation.",
        )
        return report

    if not substantive(applicability["reason"]):
        gap(
            gaps,
            (
                "not-applicable-reason-missing"
                if status == "not-applicable"
                else "applicability-reason-missing"
            ),
            "Resolve applicability with a substantive, project-specific reason.",
        )
    if applicability["blocking_dependency"] is not None:
        gap(
            gaps,
            "resolved-applicability-retains-blocker",
            "Applicable or not-applicable status cannot retain a blocking dependency; use blocked until it is resolved.",
        )
    if applicability["next_action"] is not None:
        gap(
            gaps,
            "resolved-applicability-retains-next-action",
            "Applicable or not-applicable status cannot retain a blocker-resolution next action.",
        )

    if status == "not-applicable":
        ready = not gaps
        report["ready"] = ready
        report["implementation_authorized"] = ready
        return report

    pre = contract["pre_direction_constraints"]
    assert isinstance(pre, dict)
    questions = pre["direct_entry_questions"]
    if not isinstance(questions, list) or not questions or not all(
        isinstance(item, dict)
        and substantive(item.get("entry"))
        and substantive(item.get("question"))
        for item in questions
    ):
        gap(
            gaps,
            "direct-entry-questions-missing",
            "Applicable continuity needs substantive direct-entry questions before direction implementation.",
        )
    constraints = pre["truth_and_entity_constraints"]
    if not isinstance(constraints, list) or not constraints or not all(
        isinstance(item, dict)
        and substantive(item.get("subject"))
        and substantive(item.get("constraint"))
        and substantive(item.get("authority"))
        for item in constraints
    ):
        gap(
            gaps,
            "truth-entity-constraints-missing",
            "Applicable continuity needs substantive truth and entity constraints with named authority before implementation.",
        )

    selected = contract["selected_root_continuity"]
    assert isinstance(selected, dict)
    selected_root_id = selected["selected_root_id"]
    if not valid_id(selected_root_id) or not substantive(selected["continuity_model"]):
        gap(
            gaps,
            "selected-root-model-missing",
            "Applicable continuity needs the selected root ID and a project-specific continuity model before implementation.",
        )
    handoffs = selected["handoffs_or_resets"]
    if not isinstance(handoffs, list) or not handoffs or not all(
        isinstance(item, dict)
        and all(
            substantive(item.get(field))
            for field in ("from", "to", "carry_or_reset", "visitor_reason")
        )
        for item in handoffs
    ):
        gap(
            gaps,
            "handoff-reset-missing",
            "Applicable continuity needs at least one named handoff or intentional reset with a visitor reason before implementation.",
        )
    meaningful_path = selected["meaningful_path"]
    if not isinstance(meaningful_path, dict) or not all(
        substantive(meaningful_path.get(field))
        for field in (
            "arrival",
            "decision",
            "action",
            "outcome",
            "recovery_or_continuation",
        )
    ):
        gap(
            gaps,
            "meaningful-path-missing",
            "Record arrival, decision, action, outcome, and recovery or continuation for the representative path before implementation.",
        )
    crosswalk = selected["state_authority_crosswalk"]
    if not isinstance(crosswalk, list) or not crosswalk or not all(
        isinstance(item, dict)
        and substantive(item.get("subject"))
        and substantive(item.get("authority"))
        and item.get("delivery") in DELIVERY_STATUSES
        and item.get("content") in CONTENT_STATUSES
        and item.get("behavior") in BEHAVIOR_STATUSES
        for item in crosswalk
    ):
        gap(
            gaps,
            "status-crosswalk-missing",
            "Applicable continuity needs a nonempty delivery/content/behavior authority crosswalk before implementation.",
        )

    proof_plan = selected["proof_plan"]
    plan_ids: list[str] = []
    proof_plan_valid = isinstance(proof_plan, dict)
    if proof_plan_valid:
        for kind in ("rendered", "functional"):
            items = proof_plan.get(kind)
            if (
                not isinstance(items, list)
                or not items
                or not all(
                    isinstance(item, dict)
                    and valid_id(item.get("id"))
                    and substantive(item.get("purpose"))
                    for item in items
                )
            ):
                proof_plan_valid = False
            elif isinstance(items, list):
                plan_ids.extend(str(item["id"]) for item in items)
    if not proof_plan_valid:
        gap(
            gaps,
            "proof-plan-missing",
            "Applicable continuity needs nonempty rendered and functional proof plans with stable IDs and substantive purposes before implementation.",
        )
    elif len(plan_ids) != len(set(plan_ids)):
        gap(
            gaps,
            "duplicate-proof-plan-id",
            "Rendered and functional prebuild proof-plan IDs must be unique so final evidence cannot bind ambiguously.",
        )

    if "direction-challenge" in capabilities:
        try:
            _expected_roots, chosen_root = direction_challenge_context(project)
        except AuditError as exc:
            gap(
                gaps,
                "direction-challenge-roots-unavailable",
                f"Direction Challenge selection is unavailable for selected-root continuity: {exc}",
            )
        else:
            if not valid_id(chosen_root):
                gap(
                    gaps,
                    "direction-challenge-selected-root-unavailable",
                    "Active Direction Challenge needs a chosen root before connected implementation.",
                )
            elif selected_root_id != chosen_root:
                gap(
                    gaps,
                    "direction-challenge-selected-root-mismatch",
                    "selected_root_continuity.selected_root_id must equal the active Direction Challenge chosen root before implementation.",
                )

    root_variation = contract["root_variation"]
    assert isinstance(root_variation, dict)
    mapping = root_variation.get("project_contrast_mapping")
    if (
        "project-contrast" in capabilities
        and isinstance(mapping, dict)
        and mapping.get("status") == "mapped"
        and mapping.get("selected_root_id") != selected_root_id
    ):
        gap(
            gaps,
            "project-contrast-selected-root-mismatch",
            "The Project Contrast selected-root mapping must equal selected_root_continuity.selected_root_id before implementation.",
        )

    staff = contract["staff_admin_split"]
    assert isinstance(staff, dict)
    if staff.get("status") == "blocked":
        gap(
            gaps,
            "staff-admin-blocked",
            "The connected staff/admin branch remains blocked and cannot be hidden by a direction-ready public path.",
        )
    elif staff.get("status") == "requested":
        if not all(
            substantive(staff.get(field))
            for field in ("public_boundary", "back_office_boundary")
        ):
            gap(
                gaps,
                "staff-admin-boundary-missing",
                "Requested staff/admin work needs explicit public and back-office boundaries before implementation.",
            )
        if staff.get("operate_mode") != "operate":
            gap(
                gaps,
                "operate-mode-required",
                "Requested staff/admin implementation must use the explicit Operate boundary.",
            )
        fixture = staff.get("fixture")
        if not isinstance(fixture, dict) or fixture.get("status") not in {
            "approved",
            "sandbox",
            "local-fixture",
        }:
            gap(
                gaps,
                "staff-admin-fixture-missing",
                "Requested staff/admin implementation needs approved, sandbox, or clearly local nonempty fixture state before implementation.",
            )
        elif not all(
            substantive(fixture.get(field))
            for field in ("authority", "content_or_state", "boundary")
        ):
            gap(
                gaps,
                "staff-admin-fixture-empty",
                "Requested staff/admin fixture planning needs authority, nonempty state, and a truthful boundary before implementation.",
            )
        else:
            descriptor = fixture.get("descriptor")
            if descriptor is None:
                gap(
                    gaps,
                    "staff-admin-fixture-descriptor-missing",
                    "Requested staff/admin implementation needs a hash-bound privacy-safe fixture descriptor before implementation.",
                )
            else:
                try:
                    validate_fixture_descriptor(
                        project,
                        descriptor,
                        fixture,
                        "staff/admin prebuild fixture descriptor",
                    )
                except FixtureDescriptorSemanticMismatch as exc:
                    gap(
                        gaps,
                        "staff-admin-fixture-descriptor-semantic-mismatch",
                        str(exc),
                    )
                except AuditError as exc:
                    gap(
                        gaps,
                        "staff-admin-fixture-descriptor-invalid",
                        str(exc),
                    )

    ready = not gaps
    report["ready"] = ready
    report["implementation_authorized"] = ready
    return report


def audit_payload(
    project: Path,
    payload: object,
    active_capabilities: set[str] | frozenset[str] | tuple[str, ...] = (),
    *,
    capability_context: str = "caller",
) -> dict[str, object]:
    """Return a no-write readiness report for an opt-in continuity record."""

    errors, contract = validate_contract_payload(payload)
    report: dict[str, object] = {
        "artifact_type": ARTIFACT_TYPE,
        "tool_version": TOOL_VERSION,
        "automatic_aesthetic_pass": False,
        "structural_valid": not errors,
        "ready": False,
        "findings": [],
        "gaps": [],
        "evidence": {"verified": []},
        "limitations": [
            "This audit checks declared continuity, status, and evidence bindings; it does not prove owner acceptance, production readiness, live operation, visual quality, originality, or human authorship.",
            "A passed functional row without a separate artifact is an accountable recorded-review attestation, not independently verified or live evidence.",
            "Schema-3 rendered-review links bind the report marker, exact decoded PNG capture, and declared build; they do not replace human rendered review or cryptographically prevent an actor from rewriting every owned artifact.",
        ],
    }
    findings: list[dict[str, object]] = report["findings"]  # type: ignore[assignment]
    gaps: list[dict[str, str]] = report["gaps"]  # type: ignore[assignment]
    if errors or contract is None:
        findings.extend({**entry, "blocking": True} for entry in errors)
        return report

    capabilities = set(active_capabilities)
    report["active_capabilities"] = sorted(capabilities)
    report["capability_context"] = capability_context
    if capability_context == "missing":
        gap(gaps, "active-capability-context-missing", "Standalone auditing needs a safe state.json capability selection or explicit --active-capability values; no readiness can be inferred.")
    elif capability_context == "mismatch":
        gap(gaps, "active-capability-context-mismatch", "Explicit CLI capabilities do not equal the safe state.json capability selection; do not override the active project context.")
    elif capability_context == "invalid-state":
        gap(gaps, "active-capability-context-invalid", "state.json exists but cannot safely provide the active capability selection; do not infer readiness.")
    if "connected-public-experience" not in capabilities:
        gap(gaps, "connected-capability-not-active", "This contract cannot be ready unless Connected Public Experience is explicitly active in the project capability context.")
    applicability = contract["applicability"]
    assert isinstance(applicability, dict)
    status = applicability["status"]
    report["applicability"] = status
    if status == "not-applicable":
        if not substantive(applicability["reason"]):
            gap(gaps, "not-applicable-reason-missing", "A selected capability may be not applicable only with a project-specific reason.")
        if contract["record_status"] != "reviewed":
            gap(gaps, "not-applicable-not-reviewed", "Record the not-applicable disposition as reviewed before readiness.")
        report["ready"] = not gaps
        return report
    if status == "blocked":
        for field in ("reason", "blocking_dependency", "next_action"):
            if not substantive(applicability[field]):
                gap(gaps, f"blocked-{field}-missing", f"Blocked applicability needs a substantive {field.replace('_', ' ')}.")
        gap(gaps, "connected-public-experience-blocked", "Connected public experience remains blocked; do not present readiness until the named dependency is resolved.")
        return report

    if not substantive(applicability["reason"]):
        gap(gaps, "applicability-reason-missing", "Explain why connected public continuity applies to this project.")
    if contract["record_status"] != "reviewed":
        gap(gaps, "record-not-reviewed", "Applicable connected-public experience needs a reviewed final record before readiness.")
    pre = contract["pre_direction_constraints"]
    assert isinstance(pre, dict)
    questions = pre["direct_entry_questions"]
    if not isinstance(questions, list) or not questions or not all(
        isinstance(item, dict) and substantive(item.get("entry")) and substantive(item.get("question"))
        for item in questions
    ):
        gap(gaps, "direct-entry-questions-missing", "Applicable continuity needs substantive pre-direction direct-entry questions.")
    constraints = pre["truth_and_entity_constraints"]
    if not isinstance(constraints, list) or not constraints or not all(
        isinstance(item, dict)
        and substantive(item.get("subject"))
        and substantive(item.get("constraint"))
        and substantive(item.get("authority"))
        for item in constraints
    ):
        gap(gaps, "truth-entity-constraints-missing", "Applicable continuity needs truth and entity constraints with authority.")

    selected = contract["selected_root_continuity"]
    assert isinstance(selected, dict)
    if not valid_id(selected["selected_root_id"]) or not substantive(selected["continuity_model"]):
        gap(gaps, "selected-root-model-missing", "Applicable continuity needs a selected-root ID and project-specific continuity model.")
    handoffs = selected["handoffs_or_resets"]
    if not isinstance(handoffs, list) or not handoffs or not all(
        isinstance(item, dict)
        and all(substantive(item.get(field)) for field in ("from", "to", "carry_or_reset", "visitor_reason"))
        for item in handoffs
    ):
        gap(gaps, "handoff-reset-missing", "Applicable continuity needs at least one named handoff or intentional reset with a visitor reason.")
    meaningful_path = selected["meaningful_path"]
    if not isinstance(meaningful_path, dict) or not all(
        substantive(meaningful_path.get(field))
        for field in ("arrival", "decision", "action", "outcome", "recovery_or_continuation")
    ):
        gap(gaps, "meaningful-path-missing", "Record arrival, decision, action, outcome, and recovery or continuation for the representative path.")
    crosswalk = selected["state_authority_crosswalk"]
    if not isinstance(crosswalk, list) or not crosswalk or not all(
        isinstance(item, dict)
        and substantive(item.get("subject"))
        and substantive(item.get("authority"))
        and item.get("delivery") in DELIVERY_STATUSES
        and item.get("content") in CONTENT_STATUSES
        and item.get("behavior") in BEHAVIOR_STATUSES
        for item in crosswalk
    ):
        gap(gaps, "status-crosswalk-missing", "Applicable continuity needs a clear delivery/content/behavior status crosswalk with authority.")
    proof_plan = selected["proof_plan"]
    if not isinstance(proof_plan, dict) or any(
        not isinstance(proof_plan.get(kind), list)
        or not proof_plan[kind]
        or not all(isinstance(item, dict) and valid_id(item.get("id")) and substantive(item.get("purpose")) for item in proof_plan[kind])
        for kind in ("rendered", "functional")
    ):
        gap(gaps, "proof-plan-missing", "Applicable continuity needs intended rendered and functional proof before implementation.")

    root_variation = contract["root_variation"]
    assert isinstance(root_variation, dict)
    active_direction_roots = capabilities & {"project-contrast", "direction-challenge"}
    entries = root_variation["entries"] if isinstance(root_variation["entries"], list) else []
    project_contrast_mapping = root_variation.get("project_contrast_mapping")
    project_contrast_no_root_applicability = (
        "project-contrast" in active_direction_roots
        and isinstance(project_contrast_mapping, dict)
        and project_contrast_mapping.get("status") == "not-applicable"
        and substantive(project_contrast_mapping.get("not_applicable_reason"))
    )
    roots_requiring_entries = set(active_direction_roots)
    if project_contrast_no_root_applicability:
        roots_requiring_entries.discard("project-contrast")
    if roots_requiring_entries:
        strategy = root_variation["strategy"]
        if strategy not in {"each-root-model", "named-invariant"} or not substantive(root_variation["detail"]):
            gap(gaps, "root-continuity-strategy-missing", "Applicable root-level Project Contrast or Direction Challenge work needs a named root-continuity strategy; do not assume all roots share a flow.")
        if not entries:
            gap(gaps, "root-continuity-entries-missing", "Record a viable continuity model or named invariant for each direction root with root-level applicability.")
        else:
            for entry in entries:
                if not isinstance(entry, dict) or not valid_id(entry.get("root_id")):
                    gap(gaps, "root-continuity-entry-invalid", "Each root-continuity entry needs a stable root ID.")
                    break
                if strategy == "each-root-model" and not substantive(entry.get("continuity_model")):
                    gap(gaps, "root-model-missing", "The each-root-model strategy needs a viable continuity model for every recorded root.")
                    break
                if strategy == "named-invariant" and not substantive(entry.get("named_invariant")):
                    gap(gaps, "root-invariant-missing", "The named-invariant strategy needs an explicit invariant for every recorded root.")
                    break
    entry_ids = {
        entry.get("root_id") for entry in entries
        if isinstance(entry, dict) and valid_id(entry.get("root_id"))
    }
    if "project-contrast" in active_direction_roots:
        if not isinstance(project_contrast_mapping, dict):
            gap(gaps, "project-contrast-root-mapping-missing", "Project Contrast needs an internally declared selected/counter root mapping or a substantive no-root-applicability disposition.")
        elif project_contrast_mapping.get("status") == "not-applicable":
            if not substantive(project_contrast_mapping.get("not_applicable_reason")):
                gap(gaps, "project-contrast-root-mapping-reason-missing", "A no-root-applicability Project Contrast disposition needs a substantive reason.")
        elif project_contrast_mapping.get("status") == "mapped":
            mapped_selected = project_contrast_mapping.get("selected_root_id")
            mapped_counter = project_contrast_mapping.get("counter_root_id")
            if (
                not valid_id(mapped_selected)
                or not valid_id(mapped_counter)
                or mapped_selected == mapped_counter
            ):
                gap(gaps, "project-contrast-root-mapping-invalid", "Project Contrast needs distinct stable selected and counter root IDs.")
            else:
                if mapped_selected != selected.get("selected_root_id"):
                    gap(gaps, "project-contrast-selected-root-mismatch", "The Project Contrast selected-root mapping must equal selected_root_continuity.selected_root_id.")
                if not {mapped_selected, mapped_counter}.issubset(entry_ids):
                    gap(gaps, "project-contrast-root-coverage-missing", "Project Contrast selected and counter root IDs must each have a continuity entry.")
        else:
            gap(gaps, "project-contrast-root-mapping-invalid", "Project Contrast root mapping must be mapped or not-applicable.")
    if "direction-challenge" in active_direction_roots:
        try:
            expected_roots, chosen_root = direction_challenge_context(project)
        except AuditError as exc:
            gap(gaps, "direction-challenge-roots-unavailable", f"Direction Challenge roots or selection are unavailable for continuity coverage: {exc}")
        else:
            if not expected_roots.issubset(entry_ids):
                gap(gaps, "direction-challenge-root-coverage-missing", "Each declared Direction Challenge root needs its own continuity model or named invariant.")
            if not valid_id(chosen_root):
                gap(gaps, "direction-challenge-selected-root-unavailable", "Active Direction Challenge needs a chosen root before final Connected Public Experience readiness.")
            elif selected.get("selected_root_id") != chosen_root:
                gap(gaps, "direction-challenge-selected-root-mismatch", "selected_root_continuity.selected_root_id must equal the active Direction Challenge chosen_root_id at final readiness.")
            elif chosen_root not in entry_ids:
                gap(gaps, "direction-challenge-selected-root-entry-missing", "The active Direction Challenge chosen root needs its own CPE continuity entry.")

    staff = contract["staff_admin_split"]
    assert isinstance(staff, dict)
    fixture = staff["fixture"] if isinstance(staff.get("fixture"), dict) else {}
    if staff["status"] == "requested":
        if not all(substantive(staff.get(field)) for field in ("public_boundary", "back_office_boundary")):
            gap(gaps, "staff-admin-boundary-missing", "A requested staff/admin path needs explicit public and back-office boundaries.")
        if staff["operate_mode"] != "operate":
            gap(gaps, "operate-mode-required", "A requested staff/admin back office must use Operate mode.")
        if fixture.get("status") not in {"approved", "sandbox", "local-fixture"}:
            gap(gaps, "staff-admin-fixture-missing", "A requested staff/admin path needs approved, sandbox, or clearly local non-empty fixture state; never an empty fake admin.")
        elif not all(substantive(fixture.get(field)) for field in ("authority", "content_or_state", "boundary")):
            gap(gaps, "staff-admin-fixture-empty", "A requested staff/admin fixture needs authority, non-empty content/state, and a truthful boundary.")
        descriptor = fixture.get("descriptor")
        if descriptor is None:
            gap(gaps, "staff-admin-fixture-descriptor-missing", "Requested staff/admin work needs a hash-bound privacy-safe fixture descriptor with meaningful nonempty state.")
        else:
            try:
                validate_fixture_descriptor(
                    project,
                    descriptor,
                    fixture,
                    "staff/admin fixture descriptor",
                )
            except FixtureDescriptorSemanticMismatch as exc:
                gap(gaps, "staff-admin-fixture-descriptor-semantic-mismatch", str(exc))
            except AuditError as exc:
                gap(gaps, "staff-admin-fixture-descriptor-invalid", str(exc))
    elif staff["status"] == "blocked":
        gap(gaps, "staff-admin-blocked", "The requested staff/admin branch remains blocked; preserve its named operational dependency.")

    closure = contract["final_closure"]
    assert isinstance(closure, dict)
    if closure["status"] != "complete":
        gap(gaps, "final-closure-incomplete", "Applicable continuity needs a complete final closure with rendered and functional path evidence.")
    if not valid_id(closure["reviewed_build_id"]):
        gap(gaps, "reviewed-build-missing", "Final continuity closure needs the exact reviewed build ID.")
    if not substantive(closure["conclusion"]) or not substantive(closure["limitations"]):
        gap(gaps, "final-conclusion-or-limitations-missing", "Final closure needs a result and explicit limitations.")
    rendered = closure["rendered_evidence"] if isinstance(closure["rendered_evidence"], list) else []
    functional = closure["functional_path_evidence"] if isinstance(closure["functional_path_evidence"], list) else []
    if not rendered:
        gap(gaps, "final-rendered-evidence-missing", "Final applicable continuity closure needs bound rendered evidence.")
    if not functional:
        gap(gaps, "functional-path-evidence-missing", "Final applicable continuity closure needs a functional path artifact or recorded result.")

    evidence_by_id: dict[str, dict[str, object]] = {}
    verified_rendered_ids: set[str] = set()
    valid_passed_functional_ids: set[str] = set()
    verified: list[dict[str, object]] = report["evidence"]["verified"]  # type: ignore[index,assignment]
    adapter: Any | None = None
    budget: Any | None = None
    render_cache: dict[tuple[str, str], dict[str, Any]] = {}
    if rendered:
        try:
            adapter = load_render_review_adapter()
            budget = adapter.EvidenceBudget()
        except AuditError as exc:
            gap(gaps, "schema3-render-review-verifier-unavailable", str(exc))
    for kind, items in (("rendered", rendered), ("functional", functional)):
        for index, entry in enumerate(items):
            if not isinstance(entry, dict) or not valid_id(entry.get("id")):
                continue
            evidence_id = str(entry["id"])
            if evidence_id in evidence_by_id:
                gap(gaps, "duplicate-final-evidence-id", "Rendered and functional final evidence IDs must be unique.")
                continue
            evidence_by_id[evidence_id] = {**entry, "_kind": kind}
            coverage = entry.get("coverage")
            if not isinstance(coverage, list) or not coverage:
                gap(gaps, "final-evidence-coverage-missing", f"Final {kind} evidence {evidence_id} needs a named coverage role.")
            if kind == "rendered":
                if not substantive(entry.get("route_or_state")) or not substantive(entry.get("observation")):
                    gap(gaps, "final-rendered-observation-missing", f"Rendered evidence {evidence_id} needs a route/state and observation.")
                if not valid_route(entry.get("route")):
                    gap(gaps, "final-rendered-route-missing", f"Rendered evidence {evidence_id} needs a normalized route matching its schema-3 capture.")
                elif adapter is not None and budget is not None:
                    try:
                        result = verify_rendered_evidence(
                            project,
                            entry,
                            closure.get("reviewed_build_id"),
                            adapter,
                            budget,
                            render_cache,
                        )
                    except AuditError as exc:
                        message = str(exc)
                        code = "final-rendered-schema3-invalid"
                        if "build identity does not equal" in message:
                            code = "final-rendered-build-mismatch"
                        elif "unknown schema-3 capture" in message:
                            code = "final-rendered-capture-unbound"
                        gap(gaps, code, message)
                    else:
                        verified_rendered_ids.add(evidence_id)
                        verified.append(result)
            else:
                functional_valid = True
                if entry.get("result") != "passed":
                    gap(gaps, "functional-path-not-passed", f"Functional path evidence {evidence_id} is not recorded as passed.")
                    functional_valid = False
                if not substantive(entry.get("recorded_result")):
                    gap(gaps, "functional-recorded-result-missing", f"Functional path evidence {evidence_id} needs an accountable recorded result.")
                    functional_valid = False
                artifact = entry.get("artifact")
                if artifact is not None and safe_evidence_file(project, artifact, f"functional evidence {evidence_id}") is None:
                    gap(gaps, "functional-artifact-invalid", f"Functional path artifact {evidence_id} must bind an exact readable project file and SHA-256.")
                    functional_valid = False
                attestation = entry.get("attestation")
                if artifact is None:
                    if not isinstance(attestation, dict):
                        gap(gaps, "functional-attestation-missing", f"Passed functional evidence {evidence_id} without a separate artifact needs a structured accountable attestation.")
                        functional_valid = False
                    else:
                        if attestation.get("verification_class") != "recorded-review":
                            gap(gaps, "functional-attestation-class-invalid", f"Artifact-free functional evidence {evidence_id} must be labeled recorded-review, not independently verified or live evidence.")
                            functional_valid = False
                        if attestation.get("build_id") != closure.get("reviewed_build_id"):
                            gap(gaps, "functional-attestation-build-mismatch", f"Functional attestation {evidence_id} must name the final reviewed build.")
                            functional_valid = False
                        if attestation.get("result") != entry.get("result"):
                            gap(gaps, "functional-attestation-result-mismatch", f"Functional attestation {evidence_id} result must match its evidence row.")
                            functional_valid = False
                elif isinstance(attestation, dict):
                    if attestation.get("build_id") != closure.get("reviewed_build_id"):
                        gap(gaps, "functional-attestation-build-mismatch", f"Functional attestation {evidence_id} must name the final reviewed build.")
                        functional_valid = False
                    if attestation.get("result") != entry.get("result"):
                        gap(gaps, "functional-attestation-result-mismatch", f"Functional attestation {evidence_id} result must match its evidence row.")
                        functional_valid = False
                if functional_valid:
                    valid_passed_functional_ids.add(evidence_id)

    proof_coverage = closure["proof_coverage"] if isinstance(closure["proof_coverage"], dict) else {}
    requirements = {
        "direct_entry_evidence_ids": ("direct-entry", "rendered"),
        "recovery_or_continuation_evidence_ids": ("recovery-or-continuation", None),
    }
    required_functional_roles = {"action", "outcome", "recovery-or-continuation"}
    functional_roles: set[str] = set()
    for field, (required_role, required_kind) in requirements.items():
        ids = proof_coverage.get(field)
        if not isinstance(ids, list) or not ids:
            gap(gaps, f"{field}-missing", f"Final closure needs explicit {required_role} evidence IDs.")
            continue
        for evidence_id in ids:
            entry = evidence_by_id.get(str(evidence_id))
            if entry is None:
                gap(gaps, "final-proof-id-unbound", f"Final closure references unknown evidence ID {evidence_id!r}.")
                continue
            coverage = entry.get("coverage")
            if not isinstance(coverage, list) or required_role not in coverage:
                gap(gaps, "final-proof-role-mismatch", f"Evidence {evidence_id!r} does not cover {required_role}.")
            if required_kind is not None and entry.get("_kind") != required_kind:
                gap(gaps, "direct-entry-rendered-capture-required", f"Evidence {evidence_id!r} cannot stand in for direct entry; direct entry needs a final schema-3 rendered capture.")
            if required_kind == "rendered" and str(evidence_id) not in verified_rendered_ids:
                gap(gaps, "direct-entry-rendered-capture-invalid", f"Evidence {evidence_id!r} is not a valid decoded schema-3 rendered capture.")
    for entry in evidence_by_id.values():
        if entry.get("_kind") == "functional" and str(entry.get("id")) in valid_passed_functional_ids:
            coverage = entry.get("coverage")
            if isinstance(coverage, list):
                functional_roles.update(item for item in coverage if isinstance(item, str))
    if not required_functional_roles.issubset(functional_roles):
        gap(gaps, "functional-path-roles-missing", "Passed functional evidence must cover action, outcome, and recovery or continuation.")
    if staff.get("status") == "requested":
        staff_binding = staff.get("final_evidence")
        if not isinstance(staff_binding, dict):
            gap(gaps, "staff-admin-final-evidence-mapping-missing", "Requested staff/admin work needs explicit rendered and functional final evidence IDs; a generic functional row is insufficient.")
        else:
            rendered_id = staff_binding.get("rendered_evidence_id")
            functional_id = staff_binding.get("functional_evidence_id")
            rendered_entry = evidence_by_id.get(str(rendered_id))
            functional_entry = evidence_by_id.get(str(functional_id))
            if (
                rendered_entry is None
                or rendered_entry.get("_kind") != "rendered"
                or str(rendered_id) not in verified_rendered_ids
                or not isinstance(rendered_entry.get("coverage"), list)
                or "staff-back-office" not in rendered_entry["coverage"]
            ):
                gap(gaps, "staff-admin-rendered-capture-missing", "Requested staff/admin work needs its explicitly mapped valid schema-3 rendered back-office capture in the final closure.")
            if (
                functional_entry is None
                or functional_entry.get("_kind") != "functional"
                or not isinstance(functional_entry.get("coverage"), list)
                or "staff-back-office" not in functional_entry["coverage"]
            ):
                gap(gaps, "staff-admin-functional-proof-missing", "Requested staff/admin work needs its explicitly mapped passed back-office functional proof in the final closure.")
            else:
                attestation = functional_entry.get("attestation")
                if not isinstance(attestation, dict):
                    gap(gaps, "staff-admin-functional-attestation-missing", "Requested staff/admin work needs its own structured passed functional attestation; a generic functional row is insufficient.")
                if str(functional_id) not in valid_passed_functional_ids:
                    gap(gaps, "staff-admin-functional-proof-invalid", "The mapped staff functional evidence is not a valid passed final path record.")
                elif isinstance(attestation, dict) and (
                    not isinstance(rendered_entry, dict)
                    or attestation.get("route") != rendered_entry.get("route")
                ):
                    gap(gaps, "staff-admin-functional-route-mismatch", "The mapped staff functional attestation must name the exact route bound by its mapped schema-3 staff capture.")

    if isinstance(proof_plan, dict):
        for kind, items in (("rendered", proof_plan.get("rendered")), ("functional", proof_plan.get("functional"))):
            if not isinstance(items, list):
                continue
            for plan in items:
                if not isinstance(plan, dict) or not valid_id(plan.get("id")):
                    continue
                plan_id = str(plan["id"])
                disposition = plan.get("final_disposition")
                if disposition == "final-bound":
                    evidence = evidence_by_id.get(plan_id)
                    if evidence is None or evidence.get("_kind") != kind:
                        gap(gaps, "proof-plan-final-binding-missing", f"{kind.title()} proof-plan ID {plan_id!r} is marked final-bound but has no matching final evidence row.")
                    elif kind == "rendered" and plan_id not in verified_rendered_ids:
                        gap(gaps, "proof-plan-final-binding-invalid", f"Rendered proof-plan ID {plan_id!r} does not resolve to a valid schema-3 final capture.")
                    elif kind == "functional" and plan_id not in valid_passed_functional_ids:
                        gap(gaps, "proof-plan-final-binding-invalid", f"Functional proof-plan ID {plan_id!r} does not resolve to a valid passed final path record.")
                elif disposition == "superseded":
                    if not substantive(plan.get("superseded_reason")):
                        gap(gaps, "proof-plan-superseded-reason-missing", f"Proof-plan ID {plan_id!r} is superseded without an explicit reason.")
                else:
                    gap(gaps, "proof-plan-unresolved", f"Proof-plan ID {plan_id!r} must be final-bound or explicitly superseded before final readiness.")

    report["ready"] = not gaps
    return report


def load_contract(path: Path) -> dict[str, object]:
    return load_json_object(path, "Connected public experience contract", maximum=MAX_CONTRACT_BYTES)


def write_json(path: Path, payload: dict[str, object]) -> None:
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp") as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def resolve_active_capabilities(
    project: Path,
    explicit: list[str],
) -> tuple[set[str], str]:
    """Prefer the project state and refuse CLI capability spoofing or absence."""

    if not all(CAPABILITY_PATTERN.fullmatch(value) for value in explicit):
        raise AuditError("--active-capability values must be stable lowercase capability identifiers.")
    explicit_set = set(explicit)
    if len(explicit_set) != len(explicit):
        raise AuditError("--active-capability values must not repeat.")
    try:
        state_capabilities = load_active_capabilities_from_state(project)
    except AuditError:
        # A present-but-invalid state must remain a not-ready boundary even if
        # a caller supplies flags; flags cannot silently replace project state.
        return explicit_set, "invalid-state"
    if state_capabilities is None:
        return (explicit_set, "explicit") if explicit_set else (set(), "missing")
    if explicit_set and explicit_set != state_capabilities:
        return state_capabilities, "mismatch"
    return state_capabilities, "state"


def run(
    project: Path,
    contract_arg: str,
    explicit_capabilities: list[str] | None = None,
) -> tuple[dict[str, object], int]:
    try:
        root = project.resolve(strict=True)
    except OSError as exc:
        raise AuditError("Project root does not exist.") from exc
    if not root.is_dir():
        raise AuditError("Project root does not exist or is not a directory.")
    contract_path = safe_project_file(root, contract_arg, "contract")
    capabilities, context = resolve_active_capabilities(root, explicit_capabilities or [])
    report = audit_payload(
        root,
        load_contract(contract_path),
        capabilities,
        capability_context=context,
    )
    report["project"] = str(root)
    report["contract"] = portable_project_path(contract_arg, "contract")
    return report, 0 if report["ready"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, nargs="?", default=Path.cwd())
    parser.add_argument("--contract", default=DEFAULT_CONTRACT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument(
        "--active-capability",
        action="append",
        default=[],
        help="Explicit capability only when safe state.json context is absent; repeat as needed.",
    )
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()
    try:
        report, readiness_code = run(
            args.project,
            args.contract,
            args.active_capability,
        )
        project = args.project.resolve(strict=True)
        output = safe_output_path(project, args.output)
        write_json(output, report)
        if args.stdout:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if args.allow_incomplete else readiness_code
    except (OSError, ValueError, AuditError) as exc:
        print(json.dumps({"artifact_type": ARTIFACT_TYPE, "ok": False, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
