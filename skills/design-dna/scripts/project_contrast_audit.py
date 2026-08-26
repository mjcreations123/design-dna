#!/usr/bin/env python3
"""Audit a qualitative, owner-authorized Design DNA Project Contrast record.

This tool verifies declared evidence and review boundaries. It deliberately does
not calculate a uniqueness score, infer AI use or authorship, compare fonts or
palettes, or require a style rotation. A rendered relationship remains a human
judgment bound to project evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit


SCHEMA_VERSION = 1
TOOL_VERSION = "1.7.0"
ARTIFACT_TYPE = "design-dna-project-contrast-audit"
DEFAULT_CONTRACT = ".design-dna/project-contrast.json"
DEFAULT_OUTPUT = ".design-dna/project-contrast-audit.json"
MAX_CONTRACT_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_EVIDENCE_BYTES = 512 * 1024 * 1024
# These are evidence-integrity floors, not recommended design breakpoints. A
# one-pixel PNG can prove a hash relationship but cannot function as a rendered
# wide or narrow review surface.
# Schema-3 render-review profiles cannot be smaller than this. Keep the
# adapter aligned with the shipped renderer instead of accepting evidence that
# no conforming renderer package could emit.
MIN_RENDERED_PROOF_VIEWPORT_WIDTH = 240
MIN_RENDERED_PROOF_VIEWPORT_HEIGHT = 240
ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
TRIGGER_OWNER_RECURRENCE = "owner-recurrence-requirement"
AUTHORITY_STATUSES = {
    "authorized", "not-authorized", "inherited-system", "not-applicable",
}
PREDICTION_STATUSES = {"planned", "observed", "revised", "not-applicable"}
LIFECYCLE_STATUSES = {"draft", "direction-ready", "proof-ready", "reviewed"}
LIFECYCLE_ORDER = {
    "draft": 0,
    "direction-ready": 1,
    "proof-ready": 2,
    "reviewed": 3,
}
CHALLENGE_METHODS = {
    "counter-model", "alternate-proof", "reference-decomposition", "not-needed",
}
COMPARATOR_RELATIONSHIPS = {
    "closest-sibling", "same-project-rejected", "approved-system", "known-template",
}
SHARED_ORIGINS = {"brand", "task", "platform", "accessibility", "maintenance"}
SHARED_STATUSES = {"accepted", "rebuild"}
CONTRAST_LEVELS = {
    "encounter", "opening", "body", "content-unit", "public-shell", "type-behavior",
    "media-role", "interaction-purpose", "mobile-encounter", "project-defined",
}
CONTRAST_RELATIONSHIPS = {"different", "shared-with-reason", "not-comparable"}
CONTRAST_STATUSES = {
    "planned", "observed", "revised", "accepted", "not-applicable",
}
COUNTERFACTUAL_RESULTS = {
    "not-interchangeable", "still-too-close", "not-applicable",
}
REVIEW_STATUSES = {"draft", "pending", "complete", "not-available"}
DISPOSITIONS = {"draft", "pending", "accepted", "rework", "blocked"}
OWNER_REVIEW_STATUSES = {"draft", "not-requested", "pending", "accepted", "rejected"}
STRUCTURAL_LEVELS = {"encounter", "opening", "body", "content-unit", "mobile-encounter"}
CAPTURE_MODES = {"full-page"}
CAPTURE_STATES = {"default", "interaction"}
VIEWPORT_CLASSES = {"wide", "narrow", "intermediate"}
COMPARATOR_EVIDENCE_KINDS = {"image", "structural-abstract"}
OWNER_REVIEW_RELATIONSHIPS = {
    "not-applicable",
    "producer",
    "accountable-owner",
    "owner-authorized-human",
    "independent-human",
}
OWNER_ACCEPTANCE_RELATIONSHIPS = {
    "accountable-owner",
    "owner-authorized-human",
}
REVIEW_RELATIONSHIPS = {
    "self-review",
    "independent-human",
    "independent-agent",
    "owner-authorized-independent",
}
INDEPENDENT_UNPRIMED_RELATIONSHIPS = {
    "independent-human",
    "independent-agent",
    "owner-authorized-independent",
}
REVIEW_EXPOSURES = {
    "unprimed-candidate-captures-only",
    "paired-candidate-and-authorized-comparator-evidence",
}
UNPRIMED_EXPOSURE = "unprimed-candidate-captures-only"
PAIRED_EXPOSURE = "paired-candidate-and-authorized-comparator-evidence"
SIGNATURE_AXIS_GROUPS = {"encounter", "surface-language"}
ROUTE_COVERAGE_ENTRY_KINDS = {"captured", "represented"}
CLOSEST_SIBLING_SELECTION_STATUSES = {"draft", "selected", "not-applicable"}
CLOSEST_SIBLING_SELECTION_SOURCE_KINDS = {
    "owner-authorized-ledger-snapshot",
    "owner-authorized-selection-record",
}
OWNER_APPROVAL_STATUSES = {"draft", "owner-approved", "not-approved"}
PAIRED_OUTCOME_RESULTS = {"not-interchangeable", "still-too-close", "inconclusive"}
ROUTE_COVERAGE_MODES = {
    "representative", "all-discovered-public-routes", "sampled-with-rationale",
}
PUBLIC_SHELL_CLASSIFICATIONS = {
    "technical-foundation", "approved-public-system", "candidate-public-shell",
}
SURFACE_OBSERVATION_READY_STATUSES = {"observed", "revised", "accepted"}
SIGNATURE_SELECTION_STATUSES = {"draft", "selected", "not-applicable"}
SIGNATURE_AXIS_STATUSES = {"selected", "not-applicable"}
CONTRACT_ROOT_FIELDS = {
    "schema_version", "created_with", "record_status", "classification", "scope",
    "source_to_encounter", "selected_direction", "exploration",
    "design_signature", "comparison", "evidence", "review",
}
UNRESOLVED_TEMPLATE_MARKERS = (
    re.compile(r"__[A-Za-z][A-Za-z0-9_-]{1,126}__"),
    re.compile(r"\{\{[A-Za-z][^{}\r\n]{0,126}\}\}"),
)
RENDER_REVIEW_SCHEMA_VERSION = 3
RENDER_REVIEW_TOOL = {
    "name": "design-dna-rendered-review",
    "version": "3.0.0",
    "report_schema": "render-review.schema.json",
}
RENDER_REVIEW_MARKER_TYPE = "design-dna-render-review-output"
RENDER_REVIEW_REPORT_NAME = "render-review.json"
RENDER_REVIEW_MARKER_NAME = ".design-dna-render-review.json"
SOURCE_SNAPSHOT_POLICY = "frozen-deny-by-default-public-root"
SOURCE_SNAPSHOT_DRIFT_CHECK = "passed-source-and-frozen-snapshot-before-report-and-commit"
SOURCE_SNAPSHOT_ROOT_KINDS = {
    "single-html-parent-public-subset",
    "explicit-dist-root",
    "explicit-build-root",
    "explicit-out-root",
    "explicit-public-root",
    "auto-selected-dist-root",
    "auto-selected-build-root",
    "auto-selected-out-root",
    "auto-selected-public-root",
    "explicit-target-public-root",
}
RENDER_REVIEW_TOP_LEVEL_FIELDS = {
    "schema_version",
    "tool",
    "output_identity",
    "execution_ok",
    "review_required",
    "automatic_visual_quality_pass",
    "quality_status",
    "execution",
    "privacy",
    "build",
    "source_snapshot",
    "capture_contract",
    "routes",
    "captures",
    "artifacts",
    "manual_review",
}
RENDER_REVIEW_CAPTURE_ID_PATTERN = re.compile(
    r"^[a-z][a-z0-9-]{0,47}$"
)


class AuditError(RuntimeError):
    """A bounded I/O, integrity, or safety failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def runtime_schema_errors() -> list[dict[str, str]]:
    """Sanity-check the schema shipped beside this portable stdlib-only tool.

    Full JSON Schema evaluation is deliberately not a runtime dependency. This
    guard catches a broken or stale packaged schema before the manual contract
    validator could silently drift away from it.
    """

    path = Path(__file__).resolve().parents[1] / "schemas" / "project-contrast.schema.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [item("$schema", "runtime-schema-unavailable", f"The packaged Project Contrast schema could not be read: {exc}" )]
    if not isinstance(payload, dict):
        return [item("$schema", "runtime-schema-invalid", "The packaged Project Contrast schema root must be an object.")]
    errors: list[dict[str, str]] = []
    if payload.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append(item("$schema", "runtime-schema-invalid", "The packaged Project Contrast schema must declare JSON Schema draft 2020-12."))
    required = payload.get("required")
    if not isinstance(required, list) or set(required) != CONTRACT_ROOT_FIELDS:
        errors.append(item("$schema.required", "runtime-schema-drift", "The packaged schema root fields do not match the runtime contract validator."))
    root_properties = payload.get("properties")
    created_with = (
        root_properties.get("created_with")
        if isinstance(root_properties, dict)
        else None
    )
    if (
        not isinstance(created_with, dict)
        or created_with.get("minLength") != 1
        or created_with.get("maxLength") != 200
        or created_with.get("pattern") != ".*\\S.*"
    ):
        errors.append(item(
            "$schema.properties.created_with",
            "runtime-schema-drift",
            "The packaged schema created_with rule must match the nonblank runtime validator.",
        ))
    definitions = payload.get("$defs")
    capture_required = (
        definitions.get("evidence", {}).get("properties", {}).get("captures", {})
        if isinstance(definitions, dict)
        else None
    )
    if not isinstance(capture_required, dict):
        errors.append(item("$schema.$defs.evidence", "runtime-schema-drift", "The packaged schema must define capture evidence."))
    else:
        item_required = capture_required.get("items", {}).get("required")
        expected_capture_fields = {
            "id", "route", "viewport", "capture_mode", "capture_state",
            "candidate_build_id", "file", "render_review",
        }
        if not isinstance(item_required, list) or set(item_required) != expected_capture_fields:
            errors.append(item("$schema.$defs.evidence.captures", "runtime-schema-drift", "The packaged schema capture fields do not match the runtime validator."))
        capture_properties = capture_required.get("items", {}).get("properties")
        capture_mode_schema = (
            capture_properties.get("capture_mode")
            if isinstance(capture_properties, dict)
            else None
        )
        capture_state_schema = (
            capture_properties.get("capture_state")
            if isinstance(capture_properties, dict)
            else None
        )
        if (
            not isinstance(capture_properties, dict)
            or not isinstance(capture_mode_schema, dict)
            or capture_mode_schema.get("const") != "full-page"
            or not isinstance(capture_state_schema, dict)
            or set(capture_state_schema.get("enum", []))
            != CAPTURE_STATES
        ):
            errors.append(item("$schema.$defs.evidence.captures", "runtime-schema-drift", "The packaged schema must separate full-page image mode from default or interaction state."))
    viewport_definition = definitions.get("viewport") if isinstance(definitions, dict) else None
    viewport_properties = (
        viewport_definition.get("properties")
        if isinstance(viewport_definition, dict)
        else None
    )
    viewport_width = (
        viewport_properties.get("width")
        if isinstance(viewport_properties, dict)
        else None
    )
    viewport_height = (
        viewport_properties.get("height")
        if isinstance(viewport_properties, dict)
        else None
    )
    if (
        not isinstance(viewport_width, dict)
        or viewport_width.get("minimum") != MIN_RENDERED_PROOF_VIEWPORT_WIDTH
        or not isinstance(viewport_height, dict)
        or viewport_height.get("minimum") != MIN_RENDERED_PROOF_VIEWPORT_HEIGHT
    ):
        errors.append(item(
            "$schema.$defs.viewport",
            "runtime-schema-drift",
            "The packaged Project Contrast viewport floor must match the shipped schema-3 renderer adapter.",
        ))
    required_definitions = {
        "designSignature",
        "ownerReview",
        "lifecycleStatus",
        "contrastPrompt",
        "routeCoverage",
        "sharedPublicShell",
        "surfaceGrammarObservation",
        "evidenceBinding",
        "structuralClaimEvidenceBinding",
        "renderReviewReference",
        "renderReviewCaptureBinding",
        "reviewEvidence",
        "closestSiblingSelection",
        "comparatorImageSource",
        "ownerApproval",
        "pairedOutcome",
        "routeCoverageMapEntry",
    }
    if not isinstance(definitions, dict) or not required_definitions.issubset(definitions):
        errors.append(item("$schema.$defs", "runtime-schema-drift", "The packaged schema must define lifecycle, contrast-prompt, design-signature, and owner-review records."))
        return errors
    lifecycle = definitions["lifecycleStatus"]
    if not isinstance(lifecycle, dict) or set(lifecycle.get("enum", [])) != LIFECYCLE_STATUSES:
        errors.append(item("$schema.$defs.lifecycleStatus", "runtime-schema-drift", "The packaged schema lifecycle states do not match the runtime validator."))
    contrast_prompt = definitions["contrastPrompt"]
    required_prompt_fields = {
        "encounter_collision", "public_shell_collision", "surface_grammar",
    }
    if (
        not isinstance(contrast_prompt, dict)
        or set(contrast_prompt.get("required", [])) != required_prompt_fields
    ):
        errors.append(item("$schema.$defs.contrastPrompt", "runtime-schema-drift", "The packaged schema contrast prompt fields do not match the runtime validator."))
    scope = definitions.get("scope")
    expected_scope_fields = {
        "project_id", "surface_scope", "route_coverage", "trigger", "comparison_authority",
    }
    if (
        not isinstance(scope, dict)
        or set(scope.get("required", [])) != expected_scope_fields
    ):
        errors.append(item("$schema.$defs.scope", "runtime-schema-drift", "The packaged schema scope fields do not match the runtime route-coverage validator."))
    comparison = definitions.get("comparison")
    expected_comparison_fields = {
        "comparators", "shared_decisions", "shared_public_shell", "contrast_claims",
        "surface_grammar_observations", "contrast_prompt", "counterfactual_swap_test",
    }
    if (
        not isinstance(comparison, dict)
        or set(comparison.get("required", [])) != expected_comparison_fields
    ):
        errors.append(item("$schema.$defs.comparison", "runtime-schema-drift", "The packaged schema comparison fields do not match the runtime public-grammar validator."))
    else:
        comparison_properties = comparison.get("properties")
        closest_selection_schema = (
            comparison_properties.get("closest_sibling_selection")
            if isinstance(comparison_properties, dict)
            else None
        )
        if (
            not isinstance(closest_selection_schema, dict)
            or closest_selection_schema.get("$ref") != "#/$defs/closestSiblingSelection"
        ):
            errors.append(item(
                "$schema.$defs.comparison.closest_sibling_selection",
                "runtime-schema-drift",
                "The packaged schema must expose the optional hash-bound closest-sibling selection record.",
            ))
    route_coverage_properties = (
        definitions.get("routeCoverage", {}).get("properties")
        if isinstance(definitions, dict)
        else None
    )
    route_map_schema = (
        route_coverage_properties.get("discovered_route_map")
        if isinstance(route_coverage_properties, dict)
        else None
    )
    route_map_items = route_map_schema.get("items") if isinstance(route_map_schema, dict) else None
    if (
        not isinstance(route_map_items, dict)
        or route_map_items.get("$ref") != "#/$defs/routeCoverageMapEntry"
    ):
        errors.append(item(
            "$schema.$defs.routeCoverage.discovered_route_map",
            "runtime-schema-drift",
            "The packaged schema must expose the optional discovered-route coverage map.",
        ))
    shell_properties = (
        definitions.get("sharedPublicShell", {}).get("properties")
        if isinstance(definitions, dict)
        else None
    )
    shell_approval_schema = (
        shell_properties.get("approval")
        if isinstance(shell_properties, dict)
        else None
    )
    if not isinstance(shell_approval_schema, dict):
        errors.append(item(
            "$schema.$defs.sharedPublicShell.approval",
            "runtime-schema-drift",
            "The packaged schema must expose scoped owner-approval evidence for an approved public system.",
        ))
    structural_binding = definitions.get("structuralClaimEvidenceBinding")
    structural_binding_properties = (
        structural_binding.get("properties")
        if isinstance(structural_binding, dict)
        else None
    )
    structural_capture_ids = (
        structural_binding_properties.get("capture_ids")
        if isinstance(structural_binding_properties, dict)
        else None
    )
    structural_comparator_ids = (
        structural_binding_properties.get("comparator_ids")
        if isinstance(structural_binding_properties, dict)
        else None
    )
    if (
        not isinstance(structural_binding, dict)
        or set(structural_binding.get("required", [])) != {"capture_ids", "comparator_ids", "note"}
        or not isinstance(structural_capture_ids, dict)
        or structural_capture_ids.get("minItems") != 1
        or not isinstance(structural_comparator_ids, dict)
        or structural_comparator_ids.get("minItems") != 1
    ):
        errors.append(item("$schema.$defs.structuralClaimEvidenceBinding", "runtime-schema-drift", "The packaged schema must require candidate and comparator evidence for accepted structural claims."))
    contrast_claim_items = (
        comparison.get("properties", {}).get("contrast_claims", {}).get("items")
        if isinstance(comparison, dict)
        else None
    )
    structural_claim_guard_found = False
    if isinstance(contrast_claim_items, dict):
        for guard in contrast_claim_items.get("allOf", []):
            if not isinstance(guard, dict):
                continue
            condition = guard.get("if")
            consequence = guard.get("then")
            condition_properties = condition.get("properties") if isinstance(condition, dict) else None
            evidence_schema = consequence.get("properties", {}).get("evidence") if isinstance(consequence, dict) else None
            level_schema = condition_properties.get("level") if isinstance(condition_properties, dict) else None
            relationship_schema = condition_properties.get("relationship") if isinstance(condition_properties, dict) else None
            status_schema = condition_properties.get("status") if isinstance(condition_properties, dict) else None
            if (
                isinstance(level_schema, dict)
                and set(level_schema.get("enum", [])) == STRUCTURAL_LEVELS
                and isinstance(relationship_schema, dict)
                and relationship_schema.get("const") == "different"
                and isinstance(status_schema, dict)
                and status_schema.get("const") == "accepted"
                and isinstance(evidence_schema, dict)
                and evidence_schema.get("$ref") == "#/$defs/structuralClaimEvidenceBinding"
            ):
                structural_claim_guard_found = True
                break
    if not structural_claim_guard_found:
        errors.append(item("$schema.$defs.comparison.contrast_claims", "runtime-schema-drift", "The packaged schema must require structured evidence for accepted different structural claims."))
    signature_items = (
        definitions.get("designSignature", {}).get("properties", {}).get("axes", {}).get("items")
        if isinstance(definitions, dict)
        else None
    )
    signature_axis_schema = (
        signature_items.get("properties", {}).get("axis")
        if isinstance(signature_items, dict)
        else None
    )
    signature_group_schema = (
        signature_items.get("properties", {}).get("group")
        if isinstance(signature_items, dict)
        else None
    )
    group_variants = (
        signature_group_schema.get("oneOf")
        if isinstance(signature_group_schema, dict)
        else None
    )
    group_values = set()
    if isinstance(group_variants, list):
        for variant in group_variants:
            if isinstance(variant, dict) and isinstance(variant.get("enum"), list):
                group_values.update(variant["enum"])
    if (
        not isinstance(signature_axis_schema, dict)
        or signature_axis_schema.get("$ref") != "#/$defs/id"
        or not isinstance(signature_group_schema, dict)
        or group_values != SIGNATURE_AXIS_GROUPS
    ):
        errors.append(item(
            "$schema.$defs.designSignature",
            "runtime-schema-drift",
            "The packaged schema must preserve project-defined signature identifiers and the encounter/surface-language grouping boundary without a universal axis inventory.",
        ))
    review_evidence = definitions.get("reviewEvidence")
    expected_review_fields = {
        "status", "reviewer_id", "relationship", "exposure", "observed_at", "frozen_at",
        "evidence", "reviewed_capture_ids", "reviewed_comparator_ids", "first_observation",
        "limitations",
    }
    if (
        not isinstance(review_evidence, dict)
        or set(review_evidence.get("required", [])) != expected_review_fields
    ):
        errors.append(item("$schema.$defs.reviewEvidence", "runtime-schema-drift", "The packaged schema review record must bind relationship, exposure, candidate captures, comparator evidence, and first observation."))
    review_definition = definitions.get("review") if isinstance(definitions, dict) else None
    paired_outcome_schema = (
        review_definition.get("properties", {}).get("paired_outcome")
        if isinstance(review_definition, dict)
        else None
    )
    owner_review_definition = definitions.get("ownerReview") if isinstance(definitions, dict) else None
    owner_review_properties = (
        owner_review_definition.get("properties")
        if isinstance(owner_review_definition, dict)
        else None
    )
    if (
        not isinstance(paired_outcome_schema, dict)
        or not isinstance(owner_review_properties, dict)
        or "candidate_build_id" not in owner_review_properties
        or "reviewed_capture_ids" not in owner_review_properties
    ):
        errors.append(item(
            "$schema.$defs.review",
            "runtime-schema-drift",
            "The packaged schema must expose paired outcome and exact owner-acceptance build/capture bindings.",
        ))
    render_review_path = Path(__file__).resolve().parents[1] / "schemas" / "render-review.schema.json"
    try:
        render_review_schema = json.loads(render_review_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(item("$render-review-schema", "runtime-schema-unavailable", f"The packaged rendered-review schema could not be read: {exc}"))
    else:
        schema_version = (
            render_review_schema.get("properties", {}).get("schema_version", {}).get("const")
            if isinstance(render_review_schema, dict)
            else None
        )
        tool = (
            render_review_schema.get("properties", {}).get("tool", {}).get("properties", {})
            if isinstance(render_review_schema, dict)
            else None
        )
        tool_name = tool.get("name") if isinstance(tool, dict) else None
        tool_version = tool.get("version") if isinstance(tool, dict) else None
        tool_schema = tool.get("report_schema") if isinstance(tool, dict) else None
        if (
            schema_version != RENDER_REVIEW_SCHEMA_VERSION
            or not isinstance(tool, dict)
            or not isinstance(tool_name, dict)
            or not isinstance(tool_version, dict)
            or not isinstance(tool_schema, dict)
            or tool_name.get("const") != RENDER_REVIEW_TOOL["name"]
            or tool_version.get("const") != RENDER_REVIEW_TOOL["version"]
            or tool_schema.get("const") != RENDER_REVIEW_TOOL["report_schema"]
        ):
            errors.append(item("$render-review-schema", "runtime-schema-drift", "The packaged rendered-review schema must expose the schema-3 tool identity used by Project Contrast capture bindings."))
    return errors


def item(path: str, code: str, message: str) -> dict[str, str]:
    return {"path": path, "code": code, "message": message}


def text_ok(value: object, *, minimum: int = 1, maximum: int = 8000) -> bool:
    return (
        isinstance(value, str)
        and minimum <= len(value.strip()) <= maximum
        and not any(ord(character) < 0x20 and character not in "\t\n\r" for character in value)
    )


def add_if_bad_string(
    errors: list[dict[str, str]], value: object, path: str, *, maximum: int = 8000,
) -> bool:
    if text_ok(value, maximum=maximum):
        return True
    errors.append(item(path, "invalid-string", "Expected a nonempty bounded text value."))
    return False


def add_if_bad_draftable_string(
    errors: list[dict[str, str]], value: object, path: str, *, maximum: int = 8000,
) -> bool:
    """Accept an intentionally unresolved draft value without treating prose as data."""

    if value is None:
        return True
    return add_if_bad_string(errors, value, path, maximum=maximum)


def exact_object(
    errors: list[dict[str, str]], value: object, path: str, expected: set[str],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(item(path, "invalid-object", "Expected a JSON object."))
        return None
    if set(value) != expected:
        errors.append(
            item(
                path,
                "invalid-properties",
                "Object has missing or unsupported properties.",
            )
        )
    return value


def exact_object_with_optional(
    errors: list[dict[str, str]],
    value: object,
    path: str,
    required: set[str],
    optional: set[str],
) -> dict[str, Any] | None:
    """Accept a forward-compatible optional field without hiding unknown data.

    The Project Contrast contract deliberately keeps old drafts readable while
    new readiness claims demand stronger evidence. This helper accepts only
    named optional additions; it never turns a permissive object into an open
    bag of unsupported claims.
    """

    if not isinstance(value, dict):
        errors.append(item(path, "invalid-object", "Expected a JSON object."))
        return None
    keys = set(value)
    if not required.issubset(keys) or not keys.issubset(required | optional):
        errors.append(
            item(
                path,
                "invalid-properties",
                "Object has missing or unsupported properties.",
            )
        )
    return value


def valid_id(errors: list[dict[str, str]], value: object, path: str) -> bool:
    if isinstance(value, str) and ID_PATTERN.fullmatch(value):
        return True
    errors.append(item(path, "invalid-id", "Expected a lowercase slug identifier."))
    return False


def valid_draftable_id(errors: list[dict[str, str]], value: object, path: str) -> bool:
    if value is None:
        return True
    return valid_id(errors, value, path)


def valid_enum(
    errors: list[dict[str, str]], value: object, path: str, allowed: set[str],
) -> bool:
    if value in allowed:
        return True
    errors.append(
        item(path, "invalid-value", "Expected one of: " + ", ".join(sorted(allowed)) + ".")
    )
    return False


def valid_unique_strings(
    errors: list[dict[str, str]], value: object, path: str, *, allow_empty: bool,
) -> list[Any] | None:
    if not isinstance(value, list):
        errors.append(item(path, "invalid-array", "Expected a JSON array."))
        return None
    if not allow_empty and not value:
        errors.append(item(path, "empty-array", "Expected at least one entry."))
    if not all(text_ok(entry, maximum=8000) for entry in value):
        errors.append(item(path, "invalid-array-entry", "Expected unique nonempty text entries."))
    if len({str(entry) for entry in value}) != len(value):
        errors.append(item(path, "duplicate-array-entry", "Entries must be unique."))
    return value


def valid_unique_ids(
    errors: list[dict[str, str]], value: object, path: str, *, allow_empty: bool,
) -> list[str] | None:
    """Validate a unique list of record-local evidence identifiers."""

    if not isinstance(value, list):
        errors.append(item(path, "invalid-array", "Expected a JSON array of identifiers."))
        return None
    if not allow_empty and not value:
        errors.append(item(path, "empty-array", "Expected at least one identifier."))
    resolved: list[str] = []
    seen: set[str] = set()
    for index, identifier in enumerate(value):
        if valid_id(errors, identifier, f"{path}[{index}]") and isinstance(identifier, str):
            if identifier in seen:
                errors.append(item(f"{path}[{index}]", "duplicate-evidence-id", "Evidence identifiers must be unique."))
            else:
                seen.add(identifier)
                resolved.append(identifier)
    return resolved


def valid_file_ref(
    errors: list[dict[str, str]], value: object, path: str,
) -> dict[str, Any] | None:
    result = exact_object(errors, value, path, {"path", "sha256"})
    if result is None:
        return None
    add_if_bad_string(errors, result.get("path"), f"{path}.path", maximum=1000)
    digest = result.get("sha256")
    if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
        errors.append(item(f"{path}.sha256", "invalid-sha256", "Expected an exact lowercase SHA-256 digest."))
    return result


def valid_datetime(errors: list[dict[str, str]], value: object, path: str) -> bool:
    if not isinstance(value, str):
        errors.append(item(path, "invalid-datetime", "Expected an ISO date-time with time zone."))
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(item(path, "invalid-datetime", "Expected an ISO date-time with time zone."))
        return False
    if parsed.tzinfo is None:
        errors.append(item(path, "missing-datetime-zone", "Date-time must include a time zone."))
        return False
    return True


def valid_route(errors: list[dict[str, str]], value: object, path: str) -> bool:
    """Accept a normalized, directly-addressable project route only."""

    if not isinstance(value, str) or not value.startswith("/"):
        errors.append(item(path, "invalid-route", "Expected an absolute project route beginning with '/'."))
        return False
    if any(token in value for token in ("?", "#", "\\", "\x00")):
        errors.append(item(path, "invalid-route", "Routes may not use query strings, fragments, backslashes, or NUL bytes."))
        return False
    if "//" in value or "/./" in value or "/../" in value or value.endswith("/.."):
        errors.append(item(path, "invalid-route", "Routes must be normalized project paths."))
        return False
    if any(not segment or segment in {".", ".."} for segment in value.split("/")[1:-1]):
        errors.append(item(path, "invalid-route", "Routes must not contain empty or traversal segments."))
        return False
    if any(ord(character) < 0x20 for character in value):
        errors.append(item(path, "invalid-route", "Routes must not contain control characters."))
        return False
    return True


def unresolved_template_markers(payload: object, path: str = "$") -> list[dict[str, str]]:
    """Find explicit unresolved template syntax without treating ordinary prose as a token."""

    errors: list[dict[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            errors.extend(unresolved_template_markers(value, f"{path}.{key}"))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            errors.extend(unresolved_template_markers(value, f"{path}[{index}]"))
    elif isinstance(payload, str):
        if any(marker.search(payload) for marker in UNRESOLVED_TEMPLATE_MARKERS):
            errors.append(
                item(
                    path,
                    "unresolved-template-marker",
                    "Replace explicit template-marker syntax before structural or readiness review.",
                )
            )
    return errors


def valid_build_ref(
    errors: list[dict[str, str]], value: object, path: str,
) -> dict[str, Any] | None:
    record = exact_object(errors, value, path, {"id", "file"})
    if record is None:
        return None
    valid_id(errors, record.get("id"), f"{path}.id")
    valid_file_ref(errors, record.get("file"), f"{path}.file")
    return record


def valid_viewport(
    errors: list[dict[str, str]], value: object, path: str,
) -> dict[str, Any] | None:
    record = exact_object(errors, value, path, {"id", "width", "height", "viewport_class"})
    if record is None:
        return None
    valid_id(errors, record.get("id"), f"{path}.id")
    for dimension in ("width", "height"):
        number = record.get(dimension)
        minimum = (
            MIN_RENDERED_PROOF_VIEWPORT_WIDTH
            if dimension == "width"
            else MIN_RENDERED_PROOF_VIEWPORT_HEIGHT
        )
        if not isinstance(number, int) or isinstance(number, bool) or number < minimum or number > 32_768:
            errors.append(item(
                f"{path}.{dimension}",
                "invalid-dimension",
                f"Expected an integer rendered-evidence viewport {dimension} from {minimum} through 32768.",
            ))
    valid_enum(errors, record.get("viewport_class"), f"{path}.viewport_class", VIEWPORT_CLASSES)
    return record


def valid_comparator_evidence(
    errors: list[dict[str, str]], value: object, path: str,
) -> dict[str, Any] | None:
    record = exact_object_with_optional(
        errors,
        value,
        path,
        {"kind", "file", "access", "retention", "purpose"},
        {"image_source"},
    )
    if record is None:
        return None
    kind = record.get("kind")
    valid_enum(errors, kind, f"{path}.kind", COMPARATOR_EVIDENCE_KINDS)
    valid_file_ref(errors, record.get("file"), f"{path}.file")
    for key in ("access", "retention", "purpose"):
        add_if_bad_string(errors, record.get(key), f"{path}.{key}")
    if "image_source" in record and record.get("image_source") is not None:
        valid_comparator_image_source(
            errors,
            record.get("image_source"),
            f"{path}.image_source",
        )
    if kind == "structural-abstract" and record.get("image_source") is not None:
        errors.append(item(
            f"{path}.image_source",
            "structural-abstract-has-image-source",
            "A structural abstract cannot claim image-source metadata; retain it as an explicitly limited structural comparator.",
        ))
    return record


def valid_comparator_image_source(
    errors: list[dict[str, str]], value: object, path: str,
) -> dict[str, Any] | None:
    """Validate metadata that keeps an image comparator tied to a whole route."""

    record = exact_object(
        errors,
        value,
        path,
        {"source_build", "route", "capture_state", "viewport", "extent"},
    )
    if record is None:
        return None
    valid_build_ref(errors, record.get("source_build"), f"{path}.source_build")
    valid_route(errors, record.get("route"), f"{path}.route")
    valid_enum(errors, record.get("capture_state"), f"{path}.capture_state", CAPTURE_STATES)
    valid_viewport(errors, record.get("viewport"), f"{path}.viewport")
    extent = exact_object(
        errors,
        record.get("extent"),
        f"{path}.extent",
        {"mode", "pixel_width", "pixel_height"},
    )
    if extent is not None:
        if extent.get("mode") != "full-page":
            errors.append(item(
                f"{path}.extent.mode",
                "invalid-image-extent",
                "An image comparator must declare a full-page extent rather than a crop or thumbnail.",
            ))
        for dimension in ("pixel_width", "pixel_height"):
            number = extent.get(dimension)
            if (
                not isinstance(number, int)
                or isinstance(number, bool)
                or number < MIN_RENDERED_PROOF_VIEWPORT_WIDTH
                or number > 32_768
            ):
                errors.append(item(
                    f"{path}.extent.{dimension}",
                    "invalid-image-extent-dimension",
                    "Comparator full-page image dimensions must be bounded rendered evidence, not a tiny placeholder.",
                ))
    return record


def valid_closest_sibling_selection(
    errors: list[dict[str, str]], value: object, path: str,
) -> dict[str, Any] | None:
    record = exact_object(
        errors,
        value,
        path,
        {
            "status", "source_kind", "evidence", "comparator_ids",
            "owner_authorization", "selection_reason",
        },
    )
    if record is None:
        return None
    valid_enum(errors, record.get("status"), f"{path}.status", CLOSEST_SIBLING_SELECTION_STATUSES)
    source_kind = record.get("source_kind")
    if source_kind is not None:
        valid_enum(
            errors,
            source_kind,
            f"{path}.source_kind",
            CLOSEST_SIBLING_SELECTION_SOURCE_KINDS,
        )
    if record.get("evidence") is not None:
        valid_file_ref(errors, record.get("evidence"), f"{path}.evidence")
    valid_unique_ids(errors, record.get("comparator_ids"), f"{path}.comparator_ids", allow_empty=True)
    for key in ("owner_authorization", "selection_reason"):
        add_if_bad_draftable_string(errors, record.get(key), f"{path}.{key}")
    return record


def valid_owner_approval(
    errors: list[dict[str, str]], value: object, path: str,
) -> dict[str, Any] | None:
    record = exact_object(errors, value, path, {"status", "scope", "evidence"})
    if record is None:
        return None
    valid_enum(errors, record.get("status"), f"{path}.status", OWNER_APPROVAL_STATUSES)
    add_if_bad_draftable_string(errors, record.get("scope"), f"{path}.scope")
    if record.get("evidence") is not None:
        valid_file_ref(errors, record.get("evidence"), f"{path}.evidence")
    return record


def valid_paired_outcome(
    errors: list[dict[str, str]], value: object, path: str,
) -> dict[str, Any] | None:
    record = exact_object(
        errors,
        value,
        path,
        {"result", "basis", "earliest_reopen_decision"},
    )
    if record is None:
        return None
    if record.get("result") is not None:
        valid_enum(errors, record.get("result"), f"{path}.result", PAIRED_OUTCOME_RESULTS)
    add_if_bad_draftable_string(errors, record.get("basis"), f"{path}.basis")
    add_if_bad_draftable_string(
        errors,
        record.get("earliest_reopen_decision"),
        f"{path}.earliest_reopen_decision",
    )
    return record


def valid_evidence_binding(
    errors: list[dict[str, str]], value: object, path: str, *,
    require_capture_ids: bool = False,
    require_comparator_ids: bool = False,
) -> dict[str, Any] | None:
    """Validate references to already hash-bound candidate/comparator evidence.

    The binding has deliberately freeform observation language. Its IDs make
    the claim inspectable without forcing a prescribed list of visual inputs.
    """

    record = exact_object(errors, value, path, {"capture_ids", "comparator_ids", "note"})
    if record is None:
        return None
    valid_unique_ids(
        errors,
        record.get("capture_ids"),
        f"{path}.capture_ids",
        allow_empty=not require_capture_ids,
    )
    valid_unique_ids(
        errors,
        record.get("comparator_ids"),
        f"{path}.comparator_ids",
        allow_empty=not require_comparator_ids,
    )
    add_if_bad_string(errors, record.get("note"), f"{path}.note")
    return record


def valid_render_review_capture_binding(
    errors: list[dict[str, str]], value: object, path: str,
) -> dict[str, Any] | None:
    """Validate the two-level link from a Project Contrast capture to schema-3.

    The report reference is intentionally an ID rather than a duplicated path
    or hash. The audit resolves it against the already hash-bound report list,
    then verifies the named renderer capture, route, browser viewport, state,
    and screenshot artifact.
    """

    record = exact_object(errors, value, path, {"report_id", "capture_id"})
    if record is None:
        return None
    valid_id(errors, record.get("report_id"), f"{path}.report_id")
    capture_id = record.get("capture_id")
    if not (
        isinstance(capture_id, str)
        and RENDER_REVIEW_CAPTURE_ID_PATTERN.fullmatch(capture_id)
    ):
        errors.append(item(
            f"{path}.capture_id",
            "invalid-render-review-capture-id",
            "Expected a schema-3 rendered-review capture identifier.",
        ))
    return record


def selected_signature_axes(signature: object) -> set[str]:
    """Return declared selected axis identifiers without imposing a house list."""

    if not isinstance(signature, dict):
        return set()
    axes = signature.get("axes")
    if not isinstance(axes, list):
        return set()
    return {
        axis.get("axis")
        for axis in axes
        if isinstance(axis, dict)
        and axis.get("status") == "selected"
        and isinstance(axis.get("axis"), str)
        and ID_PATTERN.fullmatch(axis["axis"]) is not None
    }


def selected_signature_axes_for_group(signature: object, group: str) -> set[str]:
    """Return selected, project-defined axes that intentionally name a group."""

    if group not in SIGNATURE_AXIS_GROUPS or not isinstance(signature, dict):
        return set()
    axes = signature.get("axes")
    if not isinstance(axes, list):
        return set()
    return {
        axis["axis"]
        for axis in axes
        if isinstance(axis, dict)
        and axis.get("status") == "selected"
        and axis.get("group") == group
        and isinstance(axis.get("axis"), str)
        and ID_PATTERN.fullmatch(axis["axis"]) is not None
    }


def lifecycle_text_required(
    errors: list[dict[str, str]], value: object, path: str, stage: str,
) -> None:
    if not text_ok(value):
        errors.append(
            item(
                path,
                "lifecycle-field-unresolved",
                f"{stage} requires project-specific text rather than a draft value.",
            )
        )


def lifecycle_list_required(
    errors: list[dict[str, str]], value: object, path: str, stage: str,
) -> list[object]:
    if not isinstance(value, list) or not value:
        errors.append(
            item(
                path,
                "lifecycle-evidence-unresolved",
                f"{stage} requires at least one project-specific record.",
            )
        )
        return []
    return value


def validate_lifecycle_stage(root: dict[str, Any], errors: list[dict[str, str]]) -> None:
    """Make the declared Project Contrast stage meaningful without a style recipe.

    Drafts may be deliberately empty. Every later stage is a truthful claim
    about how much project evidence has actually been settled, so unresolved
    draft fields at that stage are structural errors rather than aesthetic
    judgments.
    """

    record_status = root.get("record_status")
    if record_status not in LIFECYCLE_ORDER:
        return
    stage_order = LIFECYCLE_ORDER[record_status]
    if stage_order == LIFECYCLE_ORDER["draft"]:
        return

    scope = root.get("scope")
    source = root.get("source_to_encounter")
    direction = root.get("selected_direction")
    exploration = root.get("exploration")
    signature = root.get("design_signature")
    comparison = root.get("comparison")
    evidence = root.get("evidence")
    review = root.get("review")

    if isinstance(scope, dict):
        if not isinstance(scope.get("project_id"), str) or ID_PATTERN.fullmatch(scope["project_id"]) is None:
            errors.append(item("$.scope.project_id", "lifecycle-field-unresolved", f"{record_status} requires a project-safe identifier."))
        lifecycle_list_required(errors, scope.get("surface_scope"), "$.scope.surface_scope", record_status)
        route_coverage = scope.get("route_coverage")
        if isinstance(route_coverage, dict):
            lifecycle_text_required(
                errors,
                route_coverage.get("rationale"),
                "$.scope.route_coverage.rationale",
                record_status,
            )
        authority = scope.get("comparison_authority")
        if isinstance(authority, dict):
            lifecycle_text_required(errors, authority.get("basis"), "$.scope.comparison_authority.basis", record_status)
    if isinstance(source, dict):
        for key in ("visitor_occasion", "primary_job", "content_operation"):
            lifecycle_text_required(errors, source.get(key), f"$.source_to_encounter.{key}", record_status)
        materials = lifecycle_list_required(
            errors,
            source.get("subject_material"),
            "$.source_to_encounter.subject_material",
            record_status,
        )
        for index, material in enumerate(materials):
            if not isinstance(material, dict):
                continue
            for key in ("kind", "evidence", "design_consequence"):
                lifecycle_text_required(
                    errors,
                    material.get(key),
                    f"$.source_to_encounter.subject_material[{index}].{key}",
                    record_status,
                )
    if isinstance(direction, dict):
        for key in (
            "organizing_answer",
            "opening_encounter",
            "dominant_content_unit",
            "body_progression",
            "ending_or_next_state",
        ):
            lifecycle_text_required(errors, direction.get(key), f"$.selected_direction.{key}", record_status)
        lifecycle_list_required(
            errors,
            direction.get("observable_predictions"),
            "$.selected_direction.observable_predictions",
            record_status,
        )
    if isinstance(exploration, dict):
        for key in (
            "first_answer_risk",
            "challenging_answer",
            "selection_reason",
            "why_sufficient",
        ):
            lifecycle_text_required(errors, exploration.get(key), f"$.exploration.{key}", record_status)
        if exploration.get("challenge_method") not in CHALLENGE_METHODS:
            errors.append(item("$.exploration.challenge_method", "lifecycle-field-unresolved", f"{record_status} requires a documented challenge method."))
    if isinstance(signature, dict):
        selection_status = signature.get("selection_status")
        if selection_status == "draft":
            errors.append(item("$.design_signature.selection_status", "lifecycle-signature-unresolved", f"{record_status} requires either selected axes or an explicit not-applicable position."))
        lifecycle_text_required(errors, signature.get("selection_basis"), "$.design_signature.selection_basis", record_status)
        if selection_status == "selected" and not selected_signature_axes(signature):
            errors.append(item("$.design_signature.axes", "lifecycle-signature-unresolved", f"{record_status} selected a signature without a selected project-derived axis."))
        axes = signature.get("axes")
        if selection_status == "selected" and isinstance(axes, list):
            for index, axis in enumerate(axes):
                if (
                    isinstance(axis, dict)
                    and axis.get("status") == "selected"
                    and axis.get("group") not in SIGNATURE_AXIS_GROUPS
                ):
                    errors.append(item(
                        f"$.design_signature.axes[{index}].group",
                        "lifecycle-signature-axis-group-missing",
                        f"{record_status} selected axis {axis.get('axis')!r} needs an encounter or surface-language group; the identifier remains project-defined.",
                    ))
    if isinstance(comparison, dict):
        contrast_prompt = comparison.get("contrast_prompt")
        if isinstance(contrast_prompt, dict):
            for key in ("encounter_collision", "public_shell_collision", "surface_grammar"):
                lifecycle_text_required(
                    errors,
                    contrast_prompt.get(key),
                    f"$.comparison.contrast_prompt.{key}",
                    record_status,
                )
        public_shell = comparison.get("shared_public_shell")
        if isinstance(public_shell, dict):
            classification = public_shell.get("classification")
            if classification == "technical-foundation":
                lifecycle_text_required(
                    errors,
                    public_shell.get("technical_boundary"),
                    "$.comparison.shared_public_shell.technical_boundary",
                    record_status,
                )
                lifecycle_text_required(
                    errors,
                    public_shell.get("source"),
                    "$.comparison.shared_public_shell.source",
                    record_status,
                )
            elif classification in {"approved-public-system", "candidate-public-shell"}:
                for key in ("public_observation", "source"):
                    lifecycle_text_required(
                        errors,
                        public_shell.get(key),
                        f"$.comparison.shared_public_shell.{key}",
                        record_status,
                    )

    recurrence_required = (
        isinstance(scope, dict)
        and isinstance(scope.get("trigger"), list)
        and TRIGGER_OWNER_RECURRENCE in scope["trigger"]
    )
    if recurrence_required:
        # A recurrence escalation exists specifically to reopen the first
        # plausible answer. `not-needed` is useful for an ordinary bounded
        # record, but cannot honestly describe that escalation.
        if isinstance(exploration, dict):
            if exploration.get("challenge_method") == "not-needed":
                errors.append(item(
                    "$.exploration.challenge_method",
                    "lifecycle-owner-recurrence-counter-answer-required",
                    "owner-recurrence-requirement requires a materially different brief-native counter-answer; not-needed cannot close that escalation.",
                ))
            organizing_answer = direction.get("organizing_answer") if isinstance(direction, dict) else None
            challenging_answer = exploration.get("challenging_answer")
            if (
                isinstance(organizing_answer, str)
                and isinstance(challenging_answer, str)
                and organizing_answer.strip()
                and organizing_answer.strip() == challenging_answer.strip()
            ):
                errors.append(item(
                    "$.exploration.challenging_answer",
                    "lifecycle-owner-recurrence-counter-answer-collides",
                    "owner-recurrence-requirement cannot use the selected organizing answer as its counter-answer; reopen the encounter or body operation.",
                ))
        encounter_axes = selected_signature_axes_for_group(signature, "encounter")
        surface_axes = selected_signature_axes_for_group(signature, "surface-language")
        if not encounter_axes:
            errors.append(item(
                "$.design_signature.axes",
                "lifecycle-encounter-axis-missing",
                "owner-recurrence-requirement needs at least one material project-defined encounter axis with group encounter; this is not a style quota.",
            ))
        if not surface_axes:
            errors.append(item(
                "$.design_signature.axes",
                "lifecycle-surface-axis-missing",
                "owner-recurrence-requirement needs at least one material project-defined surface-language axis with group surface-language; this is not a font, palette, shape, or effect rule.",
            ))

    if stage_order < LIFECYCLE_ORDER["proof-ready"]:
        return

    if isinstance(evidence, dict):
        if not isinstance(evidence.get("candidate_build"), dict):
            errors.append(item("$.evidence.candidate_build", "lifecycle-proof-missing", "proof-ready requires a candidate-build identity."))
        lifecycle_list_required(errors, evidence.get("render_reviews"), "$.evidence.render_reviews", record_status)
        lifecycle_list_required(errors, evidence.get("captures"), "$.evidence.captures", record_status)
    if isinstance(comparison, dict):
        public_shell = comparison.get("shared_public_shell")
        if (
            isinstance(public_shell, dict)
            and public_shell.get("classification") in {"approved-public-system", "candidate-public-shell"}
            and public_shell.get("evidence") is None
        ):
            errors.append(item("$.comparison.shared_public_shell.evidence", "lifecycle-proof-missing", "proof-ready requires bound evidence for a declared public shell."))
    if recurrence_required and isinstance(scope, dict):
        if isinstance(comparison, dict):
            lifecycle_list_required(errors, comparison.get("comparators"), "$.comparison.comparators", record_status)

    if stage_order < LIFECYCLE_ORDER["reviewed"]:
        return

    if isinstance(comparison, dict):
        counterfactual = comparison.get("counterfactual_swap_test")
        if isinstance(counterfactual, dict):
            if counterfactual.get("method") != "reasoned-review":
                errors.append(item("$.comparison.counterfactual_swap_test.method", "lifecycle-review-missing", "reviewed requires a qualitative counterfactual method."))
            lifecycle_text_required(errors, counterfactual.get("remaining_identity"), "$.comparison.counterfactual_swap_test.remaining_identity", record_status)
            if counterfactual.get("result") not in COUNTERFACTUAL_RESULTS:
                errors.append(item("$.comparison.counterfactual_swap_test.result", "lifecycle-review-missing", "reviewed requires a counterfactual result."))
            if (
                recurrence_required
                and counterfactual.get("result") in {"not-interchangeable", "still-too-close"}
                and not counterfactual.get("removed_or_swapped")
            ):
                errors.append(item(
                    "$.comparison.counterfactual_swap_test.removed_or_swapped",
                    "lifecycle-counterfactual-items-required",
                    "A reviewed owner-recurrence counterfactual must name what was removed or swapped before claiming a result.",
                ))
            lifecycle_text_required(errors, counterfactual.get("follow_up"), "$.comparison.counterfactual_swap_test.follow_up", record_status)
    if isinstance(review, dict):
        unprimed = review.get("unprimed")
        paired = review.get("paired")
        if not isinstance(unprimed, dict) or unprimed.get("status") != "complete":
            errors.append(item("$.review.unprimed.status", "lifecycle-review-missing", "reviewed requires a complete unprimed review."))
        if not isinstance(paired, dict) or paired.get("status") not in {"complete", "not-available"}:
            errors.append(item("$.review.paired.status", "lifecycle-review-missing", "reviewed requires a complete paired review or an explicit not-available boundary."))
        if review.get("disposition") not in {"accepted", "rework", "blocked"}:
            errors.append(item("$.review.disposition", "lifecycle-review-missing", "reviewed requires an accepted, rework, or blocked disposition."))
        if recurrence_required:
            predictions = direction.get("observable_predictions") if isinstance(direction, dict) else None
            if isinstance(predictions, list) and not any(
                isinstance(prediction, dict)
                and prediction.get("status") in {"observed", "revised"}
                for prediction in predictions
            ):
                errors.append(item(
                    "$.selected_direction.observable_predictions",
                    "lifecycle-observable-prediction-unverified",
                    "reviewed owner-recurrence work needs at least one observed or revised project-specific prediction; all-not-applicable does not establish rendered follow-through.",
                ))


def validate_contract_payload(payload: object) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    """Validate the portable planning shape without reading project artifacts."""

    errors: list[dict[str, str]] = runtime_schema_errors()
    root = exact_object(
        errors,
        payload,
        "$",
        CONTRACT_ROOT_FIELDS,
    )
    if root is None:
        return errors, None
    if root.get("schema_version") != SCHEMA_VERSION:
        errors.append(item("$.schema_version", "unsupported-version", "schema_version must equal 1."))
    add_if_bad_string(errors, root.get("created_with"), "$.created_with", maximum=200)
    valid_enum(errors, root.get("record_status"), "$.record_status", LIFECYCLE_STATUSES)
    valid_enum(errors, root.get("classification"), "$.classification", {"internal", "confidential"})

    scope = exact_object(
        errors, root.get("scope"), "$.scope",
        {"project_id", "surface_scope", "route_coverage", "trigger", "comparison_authority"},
    )
    if scope is not None:
        valid_draftable_id(errors, scope.get("project_id"), "$.scope.project_id")
        surface_scope = valid_unique_strings(errors, scope.get("surface_scope"), "$.scope.surface_scope", allow_empty=True)
        if isinstance(surface_scope, list):
            for index, route in enumerate(surface_scope):
                valid_route(errors, route, f"$.scope.surface_scope[{index}]")
        route_coverage = exact_object_with_optional(
            errors,
            scope.get("route_coverage"),
            "$.scope.route_coverage",
            {"mode", "rationale"},
            {"discovered_route_map"},
        )
        if route_coverage is not None:
            valid_enum(errors, route_coverage.get("mode"), "$.scope.route_coverage.mode", ROUTE_COVERAGE_MODES)
            add_if_bad_draftable_string(errors, route_coverage.get("rationale"), "$.scope.route_coverage.rationale")
            route_map = route_coverage.get("discovered_route_map")
            if route_map is not None:
                seen_map_routes: set[str] = set()
                if not isinstance(route_map, list) or len(route_map) > MAX_STATIC_ROUTE_FILES:
                    errors.append(item(
                        "$.scope.route_coverage.discovered_route_map",
                        "invalid-array",
                        "Expected zero through 512 discovered-route coverage records.",
                    ))
                else:
                    for index, entry in enumerate(route_map):
                        label = f"$.scope.route_coverage.discovered_route_map[{index}]"
                        record = exact_object(
                            errors,
                            entry,
                            label,
                            {"route", "coverage", "representative_route", "equivalence_rationale"},
                        )
                        if record is None:
                            continue
                        route = record.get("route")
                        if valid_route(errors, route, f"{label}.route") and isinstance(route, str):
                            if route in seen_map_routes:
                                errors.append(item(
                                    f"{label}.route",
                                    "duplicate-route-coverage-map",
                                    "Each discovered route may have only one declared coverage mapping.",
                                ))
                            seen_map_routes.add(route)
                        valid_enum(errors, record.get("coverage"), f"{label}.coverage", ROUTE_COVERAGE_ENTRY_KINDS)
                        representative_route = record.get("representative_route")
                        if representative_route is not None:
                            valid_route(errors, representative_route, f"{label}.representative_route")
                        add_if_bad_draftable_string(
                            errors,
                            record.get("equivalence_rationale"),
                            f"{label}.equivalence_rationale",
                        )
        trigger = scope.get("trigger")
        if isinstance(trigger, list):
            observed: set[str] = set()
            for index, entry in enumerate(trigger):
                if not valid_id(errors, entry, f"$.scope.trigger[{index}]"):
                    continue
                if isinstance(entry, str) and entry in observed:
                    errors.append(item(f"$.scope.trigger[{index}]", "duplicate-trigger", "Triggers must be unique."))
                if isinstance(entry, str):
                    observed.add(entry)
        else:
            errors.append(item("$.scope.trigger", "invalid-array", "Expected a JSON array."))
        authority = exact_object(
            errors, scope.get("comparison_authority"), "$.scope.comparison_authority", {"status", "basis"},
        )
        if authority is not None:
            valid_enum(errors, authority.get("status"), "$.scope.comparison_authority.status", AUTHORITY_STATUSES)
            add_if_bad_draftable_string(errors, authority.get("basis"), "$.scope.comparison_authority.basis")

    source = exact_object(
        errors, root.get("source_to_encounter"), "$.source_to_encounter",
        {"visitor_occasion", "primary_job", "subject_material", "content_operation", "nontransferable_constraints"},
    )
    if source is not None:
        for key in ("visitor_occasion", "primary_job", "content_operation"):
            add_if_bad_draftable_string(errors, source.get(key), f"$.source_to_encounter.{key}")
        materials = source.get("subject_material")
        if not isinstance(materials, list) or len(materials) > 32:
            errors.append(item("$.source_to_encounter.subject_material", "invalid-array", "Expected zero through 32 subject-material records while draft."))
        elif isinstance(materials, list):
            for index, material in enumerate(materials):
                record = exact_object(
                    errors, material, f"$.source_to_encounter.subject_material[{index}]",
                    {"kind", "evidence", "design_consequence"},
                )
                if record is not None:
                    for key in ("kind", "evidence", "design_consequence"):
                        add_if_bad_draftable_string(errors, record.get(key), f"$.source_to_encounter.subject_material[{index}].{key}")
        valid_unique_strings(errors, source.get("nontransferable_constraints"), "$.source_to_encounter.nontransferable_constraints", allow_empty=True)

    direction = exact_object(
        errors, root.get("selected_direction"), "$.selected_direction",
        {"organizing_answer", "opening_encounter", "dominant_content_unit", "body_progression", "ending_or_next_state", "observable_predictions"},
    )
    if direction is not None:
        for key in ("organizing_answer", "opening_encounter", "dominant_content_unit", "body_progression", "ending_or_next_state"):
            add_if_bad_draftable_string(errors, direction.get(key), f"$.selected_direction.{key}")
        predictions = direction.get("observable_predictions")
        seen_prediction_ids: set[str] = set()
        if not isinstance(predictions, list) or len(predictions) > 24:
            errors.append(item("$.selected_direction.observable_predictions", "invalid-array", "Expected zero through 24 observable-prediction records while draft."))
        elif isinstance(predictions, list):
            for index, prediction in enumerate(predictions):
                label = f"$.selected_direction.observable_predictions[{index}]"
                record = exact_object(errors, prediction, label, {"id", "decision", "project_basis", "rendered_condition", "expected_observation", "status"})
                if record is None:
                    continue
                identifier = record.get("id")
                if valid_id(errors, identifier, f"{label}.id") and isinstance(identifier, str):
                    if identifier in seen_prediction_ids:
                        errors.append(item(f"{label}.id", "duplicate-id", "Prediction IDs must be unique."))
                    seen_prediction_ids.add(identifier)
                for key in ("decision", "project_basis", "rendered_condition", "expected_observation"):
                    add_if_bad_string(errors, record.get(key), f"{label}.{key}")
                valid_enum(errors, record.get("status"), f"{label}.status", PREDICTION_STATUSES)

    signature = exact_object(
        errors, root.get("design_signature"), "$.design_signature",
        {"selection_status", "selection_basis", "axes"},
    )
    if signature is not None:
        valid_enum(errors, signature.get("selection_status"), "$.design_signature.selection_status", SIGNATURE_SELECTION_STATUSES)
        add_if_bad_draftable_string(errors, signature.get("selection_basis"), "$.design_signature.selection_basis")
        axes = signature.get("axes")
        seen_axes: set[str] = set()
        if not isinstance(axes, list) or len(axes) > 32:
            errors.append(item("$.design_signature.axes", "invalid-array", "Expected zero through 32 project-defined signature-axis records."))
        elif isinstance(axes, list):
            for index, axis in enumerate(axes):
                label = f"$.design_signature.axes[{index}]"
                record = exact_object_with_optional(
                    errors, axis, label,
                    {"axis", "status", "project_basis", "decision", "observable_effect"},
                    {"group"},
                )
                if record is None:
                    continue
                axis_id = record.get("axis")
                valid_id(errors, axis_id, f"{label}.axis")
                if isinstance(axis_id, str) and ID_PATTERN.fullmatch(axis_id) is not None:
                    if axis_id in seen_axes:
                        errors.append(item(f"{label}.axis", "duplicate-axis", "A design-signature axis may appear only once."))
                    seen_axes.add(axis_id)
                group = record.get("group")
                # `group` is an optional migration field. New recurrence
                # readiness requires it only for the material selected axes;
                # legacy records remain inspectable and are reopened honestly.
                if group is not None:
                    valid_enum(errors, group, f"{label}.group", SIGNATURE_AXIS_GROUPS)
                valid_enum(errors, record.get("status"), f"{label}.status", SIGNATURE_AXIS_STATUSES)
                for key in ("project_basis", "decision", "observable_effect"):
                    add_if_bad_string(errors, record.get(key), f"{label}.{key}")
            if signature.get("selection_status") == "selected" and not axes:
                errors.append(item("$.design_signature.axes", "selected-signature-without-axis", "A selected signature needs at least one project-derived axis."))
            if signature.get("selection_status") == "not-applicable" and axes:
                errors.append(item("$.design_signature.axes", "not-applicable-signature-has-axis", "A not-applicable signature selection must not include axes."))
            if signature.get("selection_status") == "draft" and axes:
                errors.append(item("$.design_signature.axes", "draft-signature-has-axis", "A draft signature must remain empty until a project-selected basis is recorded."))

    exploration = exact_object(
        errors, root.get("exploration"), "$.exploration",
        {"first_answer_risk", "challenge_method", "challenging_answer", "selection_reason", "why_sufficient"},
    )
    if exploration is not None:
        for key in ("first_answer_risk", "challenging_answer", "selection_reason", "why_sufficient"):
            add_if_bad_draftable_string(errors, exploration.get(key), f"$.exploration.{key}")
        if exploration.get("challenge_method") is not None:
            valid_enum(errors, exploration.get("challenge_method"), "$.exploration.challenge_method", CHALLENGE_METHODS)

    comparison = exact_object_with_optional(
        errors, root.get("comparison"), "$.comparison",
        {
            "comparators", "shared_decisions", "shared_public_shell", "contrast_claims",
            "surface_grammar_observations", "contrast_prompt", "counterfactual_swap_test",
        },
        {"closest_sibling_selection"},
    )
    if comparison is not None:
        if comparison.get("closest_sibling_selection") is not None:
            valid_closest_sibling_selection(
                errors,
                comparison.get("closest_sibling_selection"),
                "$.comparison.closest_sibling_selection",
            )
        comparators = comparison.get("comparators")
        seen_comparators: set[str] = set()
        if not isinstance(comparators, list) or len(comparators) > 12:
            errors.append(item("$.comparison.comparators", "invalid-array", "Expected 0 through 12 comparator records."))
        elif isinstance(comparators, list):
            for index, comparator in enumerate(comparators):
                label = f"$.comparison.comparators[{index}]"
                record = exact_object_with_optional(
                    errors,
                    comparator,
                    label,
                    {"id", "relationship", "evidence"},
                    {"project_id"},
                )
                if record is None:
                    continue
                identifier = record.get("id")
                if valid_id(errors, identifier, f"{label}.id") and isinstance(identifier, str):
                    if identifier in seen_comparators:
                        errors.append(item(f"{label}.id", "duplicate-id", "Comparator IDs must be unique."))
                    seen_comparators.add(identifier)
                if record.get("project_id") is not None:
                    valid_draftable_id(errors, record.get("project_id"), f"{label}.project_id")
                valid_enum(errors, record.get("relationship"), f"{label}.relationship", COMPARATOR_RELATIONSHIPS)
                if record.get("evidence") is not None:
                    valid_comparator_evidence(errors, record.get("evidence"), f"{label}.evidence")
        shared = comparison.get("shared_decisions")
        if not isinstance(shared, list) or len(shared) > 24:
            errors.append(item("$.comparison.shared_decisions", "invalid-array", "Expected 0 through 24 shared-decision records."))
        elif isinstance(shared, list):
            for index, decision in enumerate(shared):
                label = f"$.comparison.shared_decisions[{index}]"
                record = exact_object(errors, decision, label, {"decision", "origin", "why_shared", "status"})
                if record is None:
                    continue
                add_if_bad_string(errors, record.get("decision"), f"{label}.decision")
                valid_enum(errors, record.get("origin"), f"{label}.origin", SHARED_ORIGINS)
                add_if_bad_string(errors, record.get("why_shared"), f"{label}.why_shared")
                valid_enum(errors, record.get("status"), f"{label}.status", SHARED_STATUSES)
        public_shell = exact_object_with_optional(
            errors,
            comparison.get("shared_public_shell"),
            "$.comparison.shared_public_shell",
            {"classification", "technical_boundary", "public_observation", "source", "evidence"},
            {"approval"},
        )
        if public_shell is not None:
            classification = public_shell.get("classification")
            valid_enum(
                errors,
                classification,
                "$.comparison.shared_public_shell.classification",
                PUBLIC_SHELL_CLASSIFICATIONS,
            )
            for key in ("technical_boundary", "public_observation", "source"):
                add_if_bad_draftable_string(
                    errors,
                    public_shell.get(key),
                    f"$.comparison.shared_public_shell.{key}",
                )
            if public_shell.get("evidence") is not None:
                valid_evidence_binding(
                    errors,
                    public_shell.get("evidence"),
                    "$.comparison.shared_public_shell.evidence",
                )
            if public_shell.get("approval") is not None:
                valid_owner_approval(
                    errors,
                    public_shell.get("approval"),
                    "$.comparison.shared_public_shell.approval",
                )
            if classification == "technical-foundation" and public_shell.get("public_observation") is not None:
                errors.append(item(
                    "$.comparison.shared_public_shell.public_observation",
                    "technical-foundation-has-public-shell",
                    "A technical-foundation classification cannot carry a public-shell observation; classify visible chrome as an approved-public-system or candidate-public-shell instead.",
                ))
            if classification == "technical-foundation" and public_shell.get("evidence") is not None:
                errors.append(item(
                    "$.comparison.shared_public_shell.evidence",
                    "technical-foundation-has-public-evidence",
                    "A technical-foundation classification cannot bind rendered public-shell evidence; classify visible chrome as an approved-public-system or candidate-public-shell instead.",
                ))
        claims = comparison.get("contrast_claims")
        seen_claims: set[str] = set()
        if not isinstance(claims, list) or len(claims) > 24:
            errors.append(item("$.comparison.contrast_claims", "invalid-array", "Expected 0 through 24 contrast claims."))
        elif isinstance(claims, list):
            for index, claim in enumerate(claims):
                label = f"$.comparison.contrast_claims[{index}]"
                record = exact_object(errors, claim, label, {"id", "domain", "level", "candidate_observation", "comparator_observation", "relationship", "subject_cause", "evidence", "status"})
                if record is None:
                    continue
                identifier = record.get("id")
                if valid_id(errors, identifier, f"{label}.id") and isinstance(identifier, str):
                    if identifier in seen_claims:
                        errors.append(item(f"{label}.id", "duplicate-id", "Contrast claim IDs must be unique."))
                    seen_claims.add(identifier)
                for key in ("domain", "candidate_observation", "comparator_observation", "subject_cause"):
                    add_if_bad_string(errors, record.get(key), f"{label}.{key}")
                valid_enum(errors, record.get("level"), f"{label}.level", CONTRAST_LEVELS)
                valid_enum(errors, record.get("relationship"), f"{label}.relationship", CONTRAST_RELATIONSHIPS)
                claim_evidence = record.get("evidence")
                structural_claim_requires_binding = (
                    record.get("level") in STRUCTURAL_LEVELS
                    and record.get("relationship") == "different"
                    and record.get("status") == "accepted"
                )
                if structural_claim_requires_binding:
                    valid_evidence_binding(
                        errors,
                        claim_evidence,
                        f"{label}.evidence",
                        require_capture_ids=True,
                        require_comparator_ids=True,
                    )
                elif record.get("level") == "public-shell":
                    valid_evidence_binding(errors, claim_evidence, f"{label}.evidence")
                elif isinstance(claim_evidence, dict):
                    valid_evidence_binding(errors, claim_evidence, f"{label}.evidence")
                else:
                    add_if_bad_string(errors, claim_evidence, f"{label}.evidence")
                valid_enum(errors, record.get("status"), f"{label}.status", CONTRAST_STATUSES)
        observations = comparison.get("surface_grammar_observations")
        seen_observations: set[str] = set()
        if not isinstance(observations, list) or len(observations) > 24:
            errors.append(item("$.comparison.surface_grammar_observations", "invalid-array", "Expected 0 through 24 freeform surface-grammar observations."))
        elif isinstance(observations, list):
            for index, observation in enumerate(observations):
                label = f"$.comparison.surface_grammar_observations[{index}]"
                record = exact_object(
                    errors,
                    observation,
                    label,
                    {
                        "id", "project_defined_label", "selected_signature_axis_refs",
                        "candidate_observation", "comparator_observation", "relationship",
                        "project_cause", "source", "evidence", "status",
                    },
                )
                if record is None:
                    continue
                identifier = record.get("id")
                if valid_id(errors, identifier, f"{label}.id") and isinstance(identifier, str):
                    if identifier in seen_observations:
                        errors.append(item(f"{label}.id", "duplicate-id", "Surface-grammar observation IDs must be unique."))
                    seen_observations.add(identifier)
                for key in (
                    "project_defined_label", "candidate_observation", "comparator_observation",
                    "project_cause", "source",
                ):
                    add_if_bad_string(errors, record.get(key), f"{label}.{key}")
                axis_refs = record.get("selected_signature_axis_refs")
                if not isinstance(axis_refs, list):
                    errors.append(item(f"{label}.selected_signature_axis_refs", "invalid-array", "Expected a JSON array of selected surface-axis references."))
                else:
                    seen_axis_refs: set[str] = set()
                    for axis_index, axis_ref in enumerate(axis_refs):
                        valid_id(errors, axis_ref, f"{label}.selected_signature_axis_refs[{axis_index}]")
                        if isinstance(axis_ref, str) and ID_PATTERN.fullmatch(axis_ref) is not None:
                            if axis_ref in seen_axis_refs:
                                errors.append(item(f"{label}.selected_signature_axis_refs[{axis_index}]", "duplicate-axis-reference", "Surface-axis references must be unique."))
                            seen_axis_refs.add(axis_ref)
                valid_enum(errors, record.get("relationship"), f"{label}.relationship", CONTRAST_RELATIONSHIPS)
                valid_evidence_binding(errors, record.get("evidence"), f"{label}.evidence")
                valid_enum(errors, record.get("status"), f"{label}.status", CONTRAST_STATUSES)
        contrast_prompt = exact_object(
            errors, comparison.get("contrast_prompt"), "$.comparison.contrast_prompt",
            {"encounter_collision", "public_shell_collision", "surface_grammar"},
        )
        if contrast_prompt is not None:
            for key in ("encounter_collision", "public_shell_collision", "surface_grammar"):
                add_if_bad_draftable_string(
                    errors,
                    contrast_prompt.get(key),
                    f"$.comparison.contrast_prompt.{key}",
                )
        counterfactual = exact_object(
            errors, comparison.get("counterfactual_swap_test"), "$.comparison.counterfactual_swap_test",
            {"method", "removed_or_swapped", "remaining_identity", "result", "follow_up"},
        )
        if counterfactual is not None:
            if counterfactual.get("method") not in {None, "reasoned-review"}:
                errors.append(item("$.comparison.counterfactual_swap_test.method", "invalid-value", "Only the qualitative reasoned-review method is supported."))
            valid_unique_strings(errors, counterfactual.get("removed_or_swapped"), "$.comparison.counterfactual_swap_test.removed_or_swapped", allow_empty=True)
            add_if_bad_draftable_string(errors, counterfactual.get("remaining_identity"), "$.comparison.counterfactual_swap_test.remaining_identity")
            if counterfactual.get("result") is not None:
                valid_enum(errors, counterfactual.get("result"), "$.comparison.counterfactual_swap_test.result", COUNTERFACTUAL_RESULTS)
            add_if_bad_draftable_string(errors, counterfactual.get("follow_up"), "$.comparison.counterfactual_swap_test.follow_up")

    evidence = exact_object(
        errors, root.get("evidence"), "$.evidence", {"candidate_build", "render_reviews", "captures"},
    )
    if evidence is not None:
        if evidence.get("candidate_build") is not None:
            valid_build_ref(errors, evidence.get("candidate_build"), "$.evidence.candidate_build")
        render_reviews = evidence.get("render_reviews")
        seen_render_reviews: set[str] = set()
        if not isinstance(render_reviews, list):
            errors.append(item("$.evidence.render_reviews", "invalid-array", "Expected a JSON array."))
        elif isinstance(render_reviews, list):
            for index, reference in enumerate(render_reviews):
                label = f"$.evidence.render_reviews[{index}]"
                record = exact_object(errors, reference, label, {"id", "file"})
                if record is None:
                    continue
                identifier = record.get("id")
                if valid_id(errors, identifier, f"{label}.id") and isinstance(identifier, str):
                    if identifier in seen_render_reviews:
                        errors.append(item(f"{label}.id", "duplicate-id", "Rendered-review IDs must be unique."))
                    seen_render_reviews.add(identifier)
                valid_file_ref(errors, record.get("file"), f"{label}.file")
        captures = evidence.get("captures")
        seen_captures: set[str] = set()
        if not isinstance(captures, list):
            errors.append(item("$.evidence.captures", "invalid-array", "Expected a JSON array."))
        elif isinstance(captures, list):
            for index, capture in enumerate(captures):
                label = f"$.evidence.captures[{index}]"
                record = exact_object(
                    errors,
                    capture,
                    label,
                    {
                        "id", "route", "viewport", "capture_mode", "capture_state",
                        "candidate_build_id", "file", "render_review",
                    },
                )
                if record is None:
                    continue
                identifier = record.get("id")
                if valid_id(errors, identifier, f"{label}.id") and isinstance(identifier, str):
                    if identifier in seen_captures:
                        errors.append(item(f"{label}.id", "duplicate-id", "Capture IDs must be unique."))
                    seen_captures.add(identifier)
                valid_route(errors, record.get("route"), f"{label}.route")
                valid_viewport(errors, record.get("viewport"), f"{label}.viewport")
                valid_enum(errors, record.get("capture_mode"), f"{label}.capture_mode", CAPTURE_MODES)
                valid_enum(errors, record.get("capture_state"), f"{label}.capture_state", CAPTURE_STATES)
                valid_id(errors, record.get("candidate_build_id"), f"{label}.candidate_build_id")
                valid_file_ref(errors, record.get("file"), f"{label}.file")
                valid_render_review_capture_binding(
                    errors,
                    record.get("render_review"),
                    f"{label}.render_review",
                )

    review = exact_object_with_optional(
        errors, root.get("review"), "$.review", {"unprimed", "paired", "disposition", "owner_review"},
        {"paired_outcome"},
    )
    if review is not None:
        if review.get("paired_outcome") is not None:
            valid_paired_outcome(
                errors,
                review.get("paired_outcome"),
                "$.review.paired_outcome",
            )
        for phase in ("unprimed", "paired"):
            record = exact_object(
                errors, review.get(phase), f"$.review.{phase}",
                {
                    "status", "reviewer_id", "relationship", "exposure", "observed_at",
                    "frozen_at", "evidence", "reviewed_capture_ids",
                    "reviewed_comparator_ids", "first_observation", "limitations",
                },
            )
            if record is None:
                continue
            valid_enum(errors, record.get("status"), f"$.review.{phase}.status", REVIEW_STATUSES)
            relationship = record.get("relationship")
            if relationship is not None:
                valid_enum(errors, relationship, f"$.review.{phase}.relationship", REVIEW_RELATIONSHIPS)
            exposure = record.get("exposure")
            if exposure is not None:
                valid_enum(errors, exposure, f"$.review.{phase}.exposure", REVIEW_EXPOSURES)
            for key in ("reviewer_id", "observed_at", "frozen_at", "evidence"):
                value = record.get(key)
                if value is None:
                    continue
                if key == "reviewer_id":
                    add_if_bad_string(errors, value, f"$.review.{phase}.{key}")
                elif key in {"observed_at", "frozen_at"}:
                    valid_datetime(errors, value, f"$.review.{phase}.{key}")
                else:
                    valid_file_ref(errors, value, f"$.review.{phase}.{key}")
            valid_unique_ids(
                errors,
                record.get("reviewed_capture_ids"),
                f"$.review.{phase}.reviewed_capture_ids",
                allow_empty=True,
            )
            valid_unique_ids(
                errors,
                record.get("reviewed_comparator_ids"),
                f"$.review.{phase}.reviewed_comparator_ids",
                allow_empty=True,
            )
            add_if_bad_draftable_string(
                errors,
                record.get("first_observation"),
                f"$.review.{phase}.first_observation",
            )
            add_if_bad_draftable_string(errors, record.get("limitations"), f"$.review.{phase}.limitations")
        valid_enum(errors, review.get("disposition"), "$.review.disposition", DISPOSITIONS)
        owner_review = exact_object_with_optional(
            errors, review.get("owner_review"), "$.review.owner_review",
            {"status", "reviewer_id", "relationship", "observed_at", "evidence", "limitations"},
            {"candidate_build_id", "reviewed_capture_ids"},
        )
        if owner_review is not None:
            valid_enum(errors, owner_review.get("status"), "$.review.owner_review.status", OWNER_REVIEW_STATUSES)
            if owner_review.get("reviewer_id") is not None:
                add_if_bad_string(errors, owner_review.get("reviewer_id"), "$.review.owner_review.reviewer_id")
            if owner_review.get("relationship") is not None:
                valid_enum(errors, owner_review.get("relationship"), "$.review.owner_review.relationship", OWNER_REVIEW_RELATIONSHIPS)
            if owner_review.get("observed_at") is not None:
                valid_datetime(errors, owner_review.get("observed_at"), "$.review.owner_review.observed_at")
            if owner_review.get("evidence") is not None:
                valid_file_ref(errors, owner_review.get("evidence"), "$.review.owner_review.evidence")
            add_if_bad_draftable_string(errors, owner_review.get("limitations"), "$.review.owner_review.limitations")
            if owner_review.get("candidate_build_id") is not None:
                valid_id(errors, owner_review.get("candidate_build_id"), "$.review.owner_review.candidate_build_id")
            if owner_review.get("reviewed_capture_ids") is not None:
                valid_unique_ids(
                    errors,
                    owner_review.get("reviewed_capture_ids"),
                    "$.review.owner_review.reviewed_capture_ids",
                    allow_empty=True,
                )

    errors.extend(unresolved_template_markers(payload))
    validate_lifecycle_stage(root, errors)

    return errors, root


def portable_path(value: object, label: str) -> str:
    if not text_ok(value, maximum=1000):
        raise AuditError("invalid-portable-path", f"{label} must be a bounded nonempty path.")
    text = str(value)
    if "\\" in text or ":" in text or "\x00" in text:
        raise AuditError("invalid-portable-path", f"{label} must use a portable project-relative POSIX path.")
    path = PurePosixPath(text)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise AuditError("invalid-portable-path", f"{label} must be normalized and project-relative.")
    if path.as_posix() != text:
        raise AuditError("invalid-portable-path", f"{label} must already be normalized.")
    return text


def project_file(root: Path, relative: str, label: str) -> Path:
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise AuditError("path-outside-project", f"{label} resolves outside the project root.") from exc
    current = candidate
    while current != root:
        if current.exists() and current.is_symlink():
            raise AuditError("linked-path-refused", f"{label} crosses a symbolic link.")
        current = current.parent
    return candidate


STATIC_PUBLIC_ROOT_NAMES = ("site", "public", "dist", "build", "out")
STATIC_ROUTE_SKIP_FILENAMES = {"404.html", "500.html", "error.html"}
STATIC_ROUTE_SKIP_DIRS = {".git", ".design-dna", "node_modules", "__pycache__"}
MAX_STATIC_ROUTE_FILES = 512


def discover_static_public_routes(root: Path) -> dict[str, object]:
    """Discover plainly static public routes only when the output root is unambiguous.

    This deliberately avoids guessing through application routers, source trees,
    redirects, or links. A non-discovery is a documented boundary, not a failed
    design judgment. It lets the audit catch an obviously partial static route
    scope without turning route coverage into a numerical style rule.
    """

    candidates: list[Path] = []
    root_index = root / "index.html"
    if root_index.is_file() and not root_index.is_symlink():
        candidates.append(root)
    for name in STATIC_PUBLIC_ROOT_NAMES:
        candidate = root / name
        index = candidate / "index.html"
        if candidate.is_dir() and not candidate.is_symlink() and index.is_file() and not index.is_symlink():
            candidates.append(candidate)
    if not candidates:
        return {
            "status": "not-discovered",
            "reason": "No unambiguous static public root with index.html was found; dynamic and source-router routes are intentionally not inferred.",
            "public_root": None,
            "routes": [],
        }
    if len(candidates) != 1:
        return {
            "status": "not-discovered",
            "reason": "More than one plausible static public root was found; route coverage is not bound without an unambiguous output boundary.",
            "public_root": None,
            "routes": [],
        }

    public_root = candidates[0]
    routes: set[str] = set()
    inspected = 0
    saw_link = False
    try:
        for directory, directories, files in os.walk(public_root, followlinks=False):
            current = Path(directory)
            kept_directories: list[str] = []
            for name in directories:
                child = current / name
                if name in STATIC_ROUTE_SKIP_DIRS or name.startswith("."):
                    continue
                if child.is_symlink():
                    saw_link = True
                    continue
                kept_directories.append(name)
            directories[:] = kept_directories
            for name in files:
                if not name.lower().endswith(".html") or name.lower() in STATIC_ROUTE_SKIP_FILENAMES:
                    continue
                inspected += 1
                if inspected > MAX_STATIC_ROUTE_FILES:
                    return {
                        "status": "not-discovered",
                        "reason": f"Static route scan exceeded the bounded {MAX_STATIC_ROUTE_FILES}-file limit; route coverage is not inferred.",
                        "public_root": None,
                        "routes": [],
                    }
                file_path = current / name
                if file_path.is_symlink():
                    saw_link = True
                    continue
                relative = file_path.relative_to(public_root).as_posix()
                if relative == "index.html":
                    route = "/"
                elif relative.endswith("/index.html"):
                    route = "/" + relative[: -len("index.html")]
                else:
                    route = "/" + relative
                routes.add(route)
    except OSError as exc:
        return {
            "status": "not-discovered",
            "reason": f"Static route discovery could not safely read the public root: {exc}",
            "public_root": None,
            "routes": [],
        }
    if saw_link:
        return {
            "status": "not-discovered",
            "reason": "Static public output includes symbolic links; route coverage is not inferred through linked content.",
            "public_root": None,
            "routes": [],
        }
    return {
        "status": "discovered",
        "reason": "Routes were derived only from ordinary HTML files under one unambiguous static public root.",
        "public_root": "." if public_root == root else public_root.relative_to(root).as_posix(),
        "routes": sorted(routes),
    }


class EvidenceBudget:
    def __init__(self) -> None:
        self.bytes = 0
        self.paths: set[str] = set()

    def add(self, path: str, size: int) -> None:
        if size > MAX_EVIDENCE_BYTES:
            raise AuditError("evidence-file-too-large", f"{path} exceeds the per-file evidence limit.")
        if self.bytes + size > MAX_TOTAL_EVIDENCE_BYTES:
            raise AuditError("evidence-total-too-large", "Evidence exceeds the cumulative audit byte limit.")
        self.bytes += size
        self.paths.add(path)


def stable_read(path: Path, label: str) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise AuditError("evidence-missing", f"{label} is not an ordinary file.")
    before = path.stat()
    if before.st_size > MAX_EVIDENCE_BYTES:
        raise AuditError("evidence-file-too-large", f"{label} exceeds the per-file evidence limit.")
    payload = path.read_bytes()
    after = path.stat()
    if (
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or len(payload) != before.st_size
    ):
        raise AuditError("unstable-evidence", f"{label} changed while it was read.")
    return payload


def image_dimensions(payload: bytes, media: str, label: str) -> tuple[int, int]:
    """Read dimensions from a bounded raster header without a decoder dependency."""

    try:
        if media == "png":
            if len(payload) < 24 or payload[12:16] != b"IHDR":
                raise ValueError("missing IHDR")
            width = int.from_bytes(payload[16:20], "big")
            height = int.from_bytes(payload[20:24], "big")
        elif media == "jpeg":
            index = 2
            width = height = 0
            while index + 9 <= len(payload):
                if payload[index] != 0xFF:
                    index += 1
                    continue
                while index < len(payload) and payload[index] == 0xFF:
                    index += 1
                if index >= len(payload):
                    break
                marker = payload[index]
                index += 1
                if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
                    continue
                if index + 2 > len(payload):
                    break
                segment_length = int.from_bytes(payload[index:index + 2], "big")
                if segment_length < 2 or index + segment_length > len(payload):
                    break
                if marker in {
                    0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                    0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
                }:
                    height = int.from_bytes(payload[index + 3:index + 5], "big")
                    width = int.from_bytes(payload[index + 5:index + 7], "big")
                    break
                index += segment_length
        elif media == "webp":
            if len(payload) < 30:
                raise ValueError("short WebP header")
            chunk = payload[12:16]
            start = 20
            if chunk == b"VP8X":
                width = int.from_bytes(payload[start + 4:start + 7], "little") + 1
                height = int.from_bytes(payload[start + 7:start + 10], "little") + 1
            elif chunk == b"VP8 ":
                if payload[start + 3:start + 6] != b"\x9d\x01\x2a":
                    raise ValueError("invalid VP8 signature")
                width = int.from_bytes(payload[start + 6:start + 8], "little") & 0x3FFF
                height = int.from_bytes(payload[start + 8:start + 10], "little") & 0x3FFF
            elif chunk == b"VP8L":
                if payload[start] != 0x2F:
                    raise ValueError("invalid VP8L signature")
                bits = int.from_bytes(payload[start + 1:start + 5], "little")
                width = (bits & 0x3FFF) + 1
                height = ((bits >> 14) & 0x3FFF) + 1
            else:
                raise ValueError("unsupported WebP chunk")
        else:
            raise ValueError("unsupported media type")
    except (IndexError, ValueError) as exc:
        raise AuditError("capture-dimensions-invalid", f"{label} does not expose a readable {media} dimension header.") from exc
    if not (1 <= width <= 32_768 and 1 <= height <= 32_768):
        raise AuditError("capture-dimensions-invalid", f"{label} has unsupported image dimensions.")
    return width, height


def verify_file_reference(
    root: Path, reference: object, label: str, budget: EvidenceBudget, *, capture: bool = False,
) -> dict[str, object]:
    if not isinstance(reference, dict):
        raise AuditError("invalid-file-reference", f"{label} is not a file reference.")
    relative = portable_path(reference.get("path"), f"{label}.path")
    expected = reference.get("sha256")
    if not isinstance(expected, str) or SHA256_PATTERN.fullmatch(expected) is None:
        raise AuditError("invalid-file-reference", f"{label}.sha256 is invalid.")
    path = project_file(root, relative, f"{label}.path")
    payload = stable_read(path, label)
    budget.add(relative, len(payload))
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise AuditError("evidence-hash-mismatch", f"{label} does not match its declared SHA-256.")
    media: str | None = None
    width: int | None = None
    height: int | None = None
    if capture:
        suffix = path.suffix.casefold()
        if payload.startswith(b"\x89PNG\r\n\x1a\n") and suffix == ".png":
            media = "png"
        elif payload.startswith(b"\xff\xd8\xff") and suffix in {".jpg", ".jpeg"}:
            media = "jpeg"
        elif len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP" and suffix == ".webp":
            media = "webp"
        else:
            raise AuditError("capture-media-invalid", f"{label} must be a PNG, JPEG, or WebP capture with a matching extension.")
        width, height = image_dimensions(payload, media, label)
    result: dict[str, object] = {
        "path": relative,
        "sha256": actual,
        "bytes": len(payload),
        "media_type": media,
    }
    if width is not None and height is not None:
        result["width"] = width
        result["height"] = height
    return result


def parse_zoned_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def finding(code: str, message: str, *, blocking: bool = False) -> dict[str, object]:
    return {"code": code, "message": message, "blocking": blocking}


def add_gap(gaps: list[dict[str, str]], code: str, message: str) -> None:
    gaps.append({"code": code, "message": message})


def finalize_report(report: dict[str, object]) -> dict[str, object]:
    """Expose the readiness decision separately from qualitative judgment."""

    findings = report.get("findings")
    gaps = report.get("gaps")
    blocking = sum(
        1
        for entry in findings if isinstance(entry, dict) and entry.get("blocking") is True
    ) if isinstance(findings, list) else 0
    gap_count = len(gaps) if isinstance(gaps, list) else 0
    structural_valid = report.get("structural_valid") is True
    ready = structural_valid and blocking == 0 and gap_count == 0
    report["ready"] = ready
    report["readiness"] = {
        "status": "ready" if ready else ("invalid" if not structural_valid or blocking else "incomplete"),
        "structural_contract_valid": structural_valid,
        "blocking_findings": blocking,
        "open_gaps": gap_count,
        "default_cli_exit_code": 0 if ready else 1,
        "meaning": "Evidence and declared review gates only; never an automatic aesthetic or authorship judgment.",
    }
    return report


def render_review_marker_relative_path(report_relative: str) -> str:
    """Return the renderer marker beside a portable report path."""

    parent = PurePosixPath(report_relative).parent
    marker = parent / RENDER_REVIEW_MARKER_NAME
    normalized = marker.as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return portable_path(normalized, "rendered-review marker path")


def parse_bound_json(
    root: Path,
    relative: str,
    expected_sha256: str,
    label: str,
) -> tuple[Path, bytes, dict[str, Any]]:
    """Read a just-verified JSON artifact again and reject a between-read swap."""

    path = project_file(root, relative, f"{label}.path")
    payload = stable_read(path, label)
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise AuditError(
            "unstable-evidence",
            f"{label} changed after its hash-bound evidence check.",
        )
    try:
        parsed = json.loads(payload.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except UnicodeDecodeError as exc:
        raise AuditError("render-review-invalid-json", f"{label} is not valid UTF-8 JSON.") from exc
    except json.JSONDecodeError as exc:
        raise AuditError("render-review-invalid-json", f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise AuditError("render-review-invalid-root", f"{label} must contain a JSON object.")
    return path, payload, parsed


def exact_mapping(value: object, expected: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == expected


def rendered_output_path_sha256(path: Path) -> str:
    """Mirror the renderer's path-bound marker normalization on this host."""

    normalized = str(path.resolve())
    if os.name == "nt":
        normalized = normalized.casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def rendered_capture_route_path(value: object) -> str | None:
    """Return the final rendered path without treating a full URL as a route."""

    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if not parsed.scheme or not parsed.netloc or parsed.query or parsed.fragment:
        return None
    route = parsed.path or "/"
    return route if valid_rendered_project_route(route) else None


def rendered_capture_origin(value: object) -> tuple[str, str, int] | None:
    """Return a normalized HTTP(S) origin for a schema-3 final URL.

    A route path alone is not enough to bind a rendered local build: an owned
    report could otherwise point a capture at an unrelated origin with the same
    path. Normalize default ports so the comparison is semantic rather than a
    formatting accident.
    """

    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    scheme = parsed.scheme.casefold()
    hostname = parsed.hostname.casefold() if parsed.hostname else None
    if (
        scheme not in {"http", "https"}
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    if port is None:
        port = 80 if scheme == "http" else 443
    return scheme, hostname, port


def is_loopback_render_origin(origin: tuple[str, str, int] | None) -> bool:
    """Whether a schema-3 local build capture stayed on a local loopback host."""

    return origin is not None and origin[1] in {"127.0.0.1", "::1", "localhost"}


def valid_rendered_project_route(value: str) -> bool:
    """Mirror the Project Contrast route boundary without producing errors."""

    return (
        value.startswith("/")
        and not any(token in value for token in ("?", "#", "\\", "\x00"))
        and "//" not in value
        and "/./" not in value
        and "/../" not in value
        and not value.endswith("/..")
        and not any(
            not segment or segment in {".", ".."}
            for segment in value.split("/")[1:-1]
        )
        and not any(ord(character) < 0x20 for character in value)
    )


def source_manifest_digest(files: list[dict[str, Any]]) -> str:
    """Mirror the renderer's ordered source-manifest digest."""

    canonical = [
        {"path": entry["path"], "bytes": entry["bytes"], "sha256": entry["sha256"]}
        for entry in files
    ]
    serialized = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_local_source_snapshot(report: dict[str, Any], label: str) -> str | None:
    """Require local schema-3 reviews to retain their frozen source boundary.

    Project Contrast does not claim that an owned report prevents a later
    rewrite. It does require that local rendered evidence exposes the same
    renderer-produced source snapshot that Direction Challenge requires, so a
    null or malformed snapshot cannot masquerade as a build-bound review.
    Remote reviews intentionally retain the renderer's null snapshot policy.
    """

    build = report.get("build")
    if not isinstance(build, dict):
        raise AuditError("render-review-source-snapshot-invalid", f"{label} has no schema-3 build record.")
    target_kind = build.get("target_kind")
    snapshot = report.get("source_snapshot")
    if target_kind == "remote-url":
        if snapshot is not None:
            raise AuditError(
                "render-review-source-snapshot-invalid",
                f"{label} is a remote schema-3 review and must retain the renderer's null source snapshot.",
            )
        return None
    if target_kind not in {"local-directory", "local-file"}:
        raise AuditError("render-review-source-snapshot-invalid", f"{label} has an unsupported local source target kind.")
    if not isinstance(snapshot, dict) or set(snapshot) != {
        "policy", "root_kind", "entry_path", "drift_check", "manifest",
    }:
        raise AuditError(
            "render-review-source-snapshot-invalid",
            f"{label} must expose a complete frozen source snapshot for its local rendered build.",
        )
    if (
        snapshot.get("policy") != SOURCE_SNAPSHOT_POLICY
        or snapshot.get("drift_check") != SOURCE_SNAPSHOT_DRIFT_CHECK
        or snapshot.get("root_kind") not in SOURCE_SNAPSHOT_ROOT_KINDS
    ):
        raise AuditError(
            "render-review-source-snapshot-invalid",
            f"{label} has an unsupported schema-3 frozen-source policy, root kind, or drift check.",
        )
    entry_path = snapshot.get("entry_path")
    entry_parts = PurePosixPath(entry_path).parts if isinstance(entry_path, str) else ()
    if (
        not isinstance(entry_path, str)
        or not entry_path
        or entry_path.startswith("/")
        or "\\" in entry_path
        or "//" in entry_path
        or PurePosixPath(entry_path).as_posix() != entry_path
        or any(part in {"", ".", ".."} for part in entry_parts)
    ):
        raise AuditError("render-review-source-snapshot-invalid", f"{label} has an invalid frozen-source entry path.")
    manifest = snapshot.get("manifest")
    if not isinstance(manifest, dict) or set(manifest) != {
        "algorithm", "manifest_sha256", "file_count", "total_bytes", "files", "excluded_counts",
    }:
        raise AuditError("render-review-source-snapshot-invalid", f"{label} has an incomplete frozen-source manifest.")
    manifest_digest = manifest.get("manifest_sha256")
    files = manifest.get("files")
    if (
        manifest.get("algorithm") != "sha256"
        or not isinstance(manifest_digest, str)
        or SHA256_PATTERN.fullmatch(manifest_digest) is None
        or not isinstance(files, list)
        or not files
    ):
        raise AuditError("render-review-source-snapshot-invalid", f"{label} has an invalid frozen-source manifest identity.")
    file_paths: set[str] = set()
    total_bytes = 0
    normalized_files: list[dict[str, Any]] = []
    for index, entry in enumerate(files):
        if not isinstance(entry, dict) or set(entry) != {"path", "bytes", "sha256"}:
            raise AuditError("render-review-source-snapshot-invalid", f"{label} source manifest entry {index} is incomplete.")
        path = entry.get("path")
        byte_count = entry.get("bytes")
        digest = entry.get("sha256")
        parts = PurePosixPath(path).parts if isinstance(path, str) else ()
        if (
            not isinstance(path, str)
            or not path
            or path.startswith("/")
            or "\\" in path
            or "//" in path
            or PurePosixPath(path).as_posix() != path
            or any(part in {"", ".", ".."} for part in parts)
            or not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
            or not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
            or path in file_paths
        ):
            raise AuditError("render-review-source-snapshot-invalid", f"{label} source manifest entry {index} is invalid.")
        file_paths.add(path)
        total_bytes += byte_count
        normalized_files.append({"path": path, "bytes": byte_count, "sha256": digest})
    if (
        entry_path not in file_paths
        or manifest.get("file_count") != len(normalized_files)
        or manifest.get("total_bytes") != total_bytes
        or source_manifest_digest(normalized_files) != manifest_digest
    ):
        raise AuditError("render-review-source-snapshot-invalid", f"{label} frozen-source manifest does not bind its entries.")
    excluded_counts = manifest.get("excluded_counts")
    if not isinstance(excluded_counts, dict) or set(excluded_counts) != {
        "hidden_or_source_only_path", "sensitive_or_source_config", "extension_not_public_allowlist",
    } or any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in excluded_counts.values()
    ):
        raise AuditError("render-review-source-snapshot-invalid", f"{label} has invalid frozen-source exclusion counts.")
    return manifest_digest


def load_schema3_render_review(
    root: Path,
    reference: object,
    label: str,
    budget: EvidenceBudget,
) -> dict[str, object]:
    """Verify the portable identity boundary needed for Project Contrast links.

    This is intentionally a focused adapter, not a replacement JSON Schema
    engine or a claim that an attacker cannot rewrite an owned report and its
    marker. It verifies the schema-3/tool identity, path-bound output marker,
    successful manual-review-required run, and the exact renderer capture
    records that Project Contrast later links to.
    """

    result = verify_file_reference(root, reference, label, budget)
    relative = result["path"]
    if not isinstance(relative, str) or PurePosixPath(relative).name != RENDER_REVIEW_REPORT_NAME:
        raise AuditError(
            "render-review-path-invalid",
            f"{label} must bind {RENDER_REVIEW_REPORT_NAME}.",
        )
    expected_sha256 = result.get("sha256")
    if not isinstance(expected_sha256, str):
        raise AuditError("render-review-identity-invalid", f"{label} has no verified report hash.")
    report_path, report_payload, report = parse_bound_json(
        root,
        relative,
        expected_sha256,
        label,
    )
    if set(report) != RENDER_REVIEW_TOP_LEVEL_FIELDS:
        raise AuditError(
            "render-review-schema-invalid",
            f"{label} does not expose the exact schema-3 rendered-review top-level contract.",
        )
    if (
        report.get("schema_version") != RENDER_REVIEW_SCHEMA_VERSION
        or report.get("tool") != RENDER_REVIEW_TOOL
        or report.get("execution_ok") is not True
        or report.get("review_required") is not True
        or report.get("automatic_visual_quality_pass") is not False
        or report.get("quality_status") != "manual-review-required"
    ):
        raise AuditError(
            "render-review-schema-invalid",
            f"{label} must be a successful schema-3 rendered-review artifact that still requires manual review.",
        )
    output_identity = report.get("output_identity")
    if (
        not exact_mapping(output_identity, {"id", "path_sha256"})
        or not isinstance(output_identity.get("id"), str)
        or SHA256_PATTERN.fullmatch(output_identity["id"]) is None
        or not isinstance(output_identity.get("path_sha256"), str)
        or SHA256_PATTERN.fullmatch(output_identity["path_sha256"]) is None
    ):
        raise AuditError("render-review-identity-invalid", f"{label} has an invalid schema-3 output identity.")
    build = report.get("build")
    if (
        not exact_mapping(build, {"id", "target_input", "target_kind"})
        or not text_ok(build.get("id"), maximum=256)
    ):
        raise AuditError("render-review-schema-invalid", f"{label} must contain a schema-3 build identity.")
    target_kind = build.get("target_kind")
    target_input = build.get("target_input")
    if target_kind not in {"local-directory", "local-file", "remote-url"}:
        raise AuditError("render-review-schema-invalid", f"{label} has an unsupported schema-3 build target kind.")
    source_snapshot_manifest_sha256 = validate_local_source_snapshot(report, label)
    expected_remote_origin: tuple[str, str, int] | None = None
    if target_kind == "remote-url":
        expected_remote_origin = rendered_capture_origin(target_input)
        if expected_remote_origin is None:
            raise AuditError(
                "render-review-origin-invalid",
                f"{label} remote target must expose a canonical credential-free HTTP(S) origin.",
            )
    capture_contract = report.get("capture_contract")
    if (
        not isinstance(capture_contract, dict)
        or not isinstance(capture_contract.get("profiles"), list)
        or not capture_contract["profiles"]
        or not isinstance(capture_contract.get("scenarios"), list)
        or not capture_contract["scenarios"]
    ):
        raise AuditError("render-review-schema-invalid", f"{label} must contain nonempty schema-3 profiles and scenarios.")
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, dict):
        raise AuditError("render-review-schema-invalid", f"{label} must contain schema-3 artifact records.")
    report_artifact = artifacts.get("report")
    marker_artifact = artifacts.get("marker")
    contact_sheet = artifacts.get("contact_sheet")
    if (
        not exact_mapping(report_artifact, {"path", "bytes"})
        or report_artifact.get("path") != RENDER_REVIEW_REPORT_NAME
        or report_artifact.get("bytes") != len(report_payload)
        or not exact_mapping(marker_artifact, {"path", "bytes"})
        or marker_artifact.get("path") != RENDER_REVIEW_MARKER_NAME
        or not exact_mapping(contact_sheet, {"path", "sha256", "media_type", "bytes"})
        or contact_sheet.get("media_type") != "text/html"
        or not isinstance(contact_sheet.get("path"), str)
        or not isinstance(contact_sheet.get("sha256"), str)
        or SHA256_PATTERN.fullmatch(contact_sheet["sha256"]) is None
        or not isinstance(contact_sheet.get("bytes"), int)
    ):
        raise AuditError("render-review-schema-invalid", f"{label} has inconsistent schema-3 report or marker metadata.")
    contact_relative = (
        PurePosixPath(relative).parent / PurePosixPath(contact_sheet["path"])
    ).as_posix()
    if contact_relative.startswith("./"):
        contact_relative = contact_relative[2:]
    try:
        contact_relative = portable_path(contact_relative, f"{label}.contact-sheet.path")
        contact_path = project_file(root, contact_relative, f"{label}.contact-sheet.path")
        contact_payload = stable_read(contact_path, f"{label}.contact-sheet")
        budget.add(contact_relative, len(contact_payload))
    except AuditError as exc:
        raise AuditError("render-review-contact-sheet-invalid", exc.message) from exc
    if (
        len(contact_payload) != contact_sheet["bytes"]
        or hashlib.sha256(contact_payload).hexdigest() != contact_sheet["sha256"]
    ):
        raise AuditError("render-review-contact-sheet-invalid", f"{label} contact-sheet metadata does not match its rendered-review artifact.")

    marker_relative = render_review_marker_relative_path(relative)
    marker_path = project_file(root, marker_relative, f"{label}.marker.path")
    marker_payload = stable_read(marker_path, f"{label}.marker")
    budget.add(marker_relative, len(marker_payload))
    try:
        marker = json.loads(marker_payload.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except UnicodeDecodeError as exc:
        raise AuditError("render-review-marker-invalid", f"{label} marker is not valid UTF-8 JSON.") from exc
    except json.JSONDecodeError as exc:
        raise AuditError("render-review-marker-invalid", f"{label} marker is not valid JSON: {exc}") from exc
    marker_expected_fields = {
        "schema_version", "marker_type", "tool", "output_identity", "report",
        "created_at", "build_id_sha256",
    }
    marker_report = marker.get("report") if isinstance(marker, dict) else None
    marker_identity = marker.get("output_identity") if isinstance(marker, dict) else None
    marker_tool = marker.get("tool") if isinstance(marker, dict) else None
    if (
        not isinstance(marker, dict)
        or set(marker) != marker_expected_fields
        or marker.get("schema_version") != RENDER_REVIEW_SCHEMA_VERSION
        or marker.get("marker_type") != RENDER_REVIEW_MARKER_TYPE
        or marker_tool != {"name": RENDER_REVIEW_TOOL["name"], "version": RENDER_REVIEW_TOOL["version"]}
        or not exact_mapping(marker_identity, {"id", "path_sha256"})
        or not exact_mapping(marker_report, {"path", "sha256", "bytes"})
        or marker_report.get("path") != RENDER_REVIEW_REPORT_NAME
        or marker_report.get("sha256") != expected_sha256
        or marker_report.get("bytes") != len(report_payload)
        or marker_artifact.get("bytes") != len(marker_payload)
        or parse_zoned_datetime(marker.get("created_at")) is None
        or not isinstance(marker.get("build_id_sha256"), str)
        or SHA256_PATTERN.fullmatch(marker["build_id_sha256"]) is None
    ):
        raise AuditError("render-review-marker-invalid", f"{label} has no valid path-bound schema-3 output marker.")
    if (
        marker_identity != output_identity
        or marker_identity.get("path_sha256") != rendered_output_path_sha256(report_path.parent)
        or marker.get("build_id_sha256")
        != hashlib.sha256(str(build["id"]).encode("utf-8")).hexdigest()
    ):
        raise AuditError("render-review-identity-mismatch", f"{label} and its schema-3 output marker do not bind the same output identity and build.")

    routes = report.get("routes")
    if not isinstance(routes, list) or not routes:
        raise AuditError("render-review-schema-invalid", f"{label} must contain reviewed routes.")
    routes_by_id: dict[str, dict[str, Any]] = {}
    for index, route in enumerate(routes):
        if not isinstance(route, dict):
            raise AuditError("render-review-schema-invalid", f"{label}.routes[{index}] is not a schema-3 route object.")
        route_id = route.get("id")
        requested = route.get("requested")
        if (
            not isinstance(route_id, str)
            or not RENDER_REVIEW_CAPTURE_ID_PATTERN.fullmatch(route_id)
            or not text_ok(requested, maximum=1000)
            or route_id in routes_by_id
        ):
            raise AuditError("render-review-schema-invalid", f"{label}.routes[{index}] has an invalid or duplicate route identity.")
        routes_by_id[route_id] = route

    captures = report.get("captures")
    if not isinstance(captures, list) or not captures:
        raise AuditError("render-review-schema-invalid", f"{label} must contain reviewed captures.")
    captures_by_id: dict[str, dict[str, Any]] = {}
    capture_origins: set[tuple[str, str, int]] = set()
    for index, rendered_capture in enumerate(captures):
        capture_label = f"{label}.captures[{index}]"
        if not isinstance(rendered_capture, dict):
            raise AuditError("render-review-capture-invalid", f"{capture_label} is not a schema-3 capture object.")
        capture_id = rendered_capture.get("id")
        route_id = rendered_capture.get("route_id")
        viewport = rendered_capture.get("viewport")
        screenshot = rendered_capture.get("screenshot")
        interaction = rendered_capture.get("interaction")
        final_route = rendered_capture.get("final_url")
        final_origin = rendered_capture_origin(final_route)
        if (
            not isinstance(capture_id, str)
            or RENDER_REVIEW_CAPTURE_ID_PATTERN.fullmatch(capture_id) is None
            or capture_id in captures_by_id
            or not isinstance(route_id, str)
            or route_id not in routes_by_id
            or rendered_capture.get("capture_status") != "complete"
            or not exact_mapping(viewport, {"width", "height", "device_scale_factor"})
            or not isinstance(viewport.get("width"), int)
            or not isinstance(viewport.get("height"), int)
            or not isinstance(viewport.get("device_scale_factor"), (int, float))
            or isinstance(viewport.get("device_scale_factor"), bool)
            or not exact_mapping(screenshot, {"path", "sha256", "media_type", "bytes", "pixel_width", "pixel_height"})
            or screenshot.get("media_type") != "image/png"
            or not isinstance(screenshot.get("path"), str)
            or not isinstance(screenshot.get("sha256"), str)
            or SHA256_PATTERN.fullmatch(screenshot["sha256"]) is None
            or not isinstance(screenshot.get("pixel_width"), int)
            or not isinstance(screenshot.get("pixel_height"), int)
            or not isinstance(interaction, dict)
            or rendered_capture_route_path(final_route) is None
            or final_origin is None
        ):
            raise AuditError("render-review-capture-invalid", f"{capture_label} does not expose a complete schema-3 rendered PNG capture.")
        if target_kind in {"local-directory", "local-file"} and not is_loopback_render_origin(final_origin):
            raise AuditError(
                "render-review-origin-mismatch",
                f"{capture_label} claims a local rendered build but its final URL is not a loopback origin.",
            )
        if target_kind == "remote-url" and final_origin != expected_remote_origin:
            raise AuditError(
                "render-review-origin-mismatch",
                f"{capture_label} final URL origin does not match the schema-3 remote target origin; rerender against the canonical destination rather than binding a redirected or unrelated origin.",
            )
        capture_origins.add(final_origin)
        if (
            viewport["width"] < MIN_RENDERED_PROOF_VIEWPORT_WIDTH
            or viewport["height"] < MIN_RENDERED_PROOF_VIEWPORT_HEIGHT
        ):
            raise AuditError(
                "render-review-capture-viewport-too-small",
                f"{capture_label} viewport is too small to act as wide/narrow rendered evidence; it must be at least {MIN_RENDERED_PROOF_VIEWPORT_WIDTH} by {MIN_RENDERED_PROOF_VIEWPORT_HEIGHT} CSS pixels.",
            )
        try:
            portable_path(screenshot["path"], f"{capture_label}.screenshot.path")
        except AuditError as exc:
            raise AuditError("render-review-capture-invalid", exc.message) from exc
        if (
            screenshot["pixel_width"] < viewport["width"]
            or screenshot["pixel_height"] < viewport["height"]
        ):
            raise AuditError(
                "render-review-capture-dimensions-invalid",
                f"{capture_label} must be a full-page PNG no smaller than its browser viewport; interaction state does not turn it into a viewport-only image.",
            )
        captures_by_id[capture_id] = rendered_capture
    if len(capture_origins) != 1:
        raise AuditError(
            "render-review-origin-mismatch",
            f"{label} capture set spans multiple final URL origins; render one exact destination rather than assembling evidence across origins.",
        )
    return {
        "verification": result,
        "report_path": report_path,
        "report_relative_path": relative,
        "report": report,
        "build_id": build["id"],
        "source_snapshot_manifest_sha256": source_snapshot_manifest_sha256,
        "routes_by_id": routes_by_id,
        "captures_by_id": captures_by_id,
    }


def audit_payload(root: Path, payload: dict[str, Any]) -> dict[str, object]:
    """Check declared artifacts and readiness without making an aesthetic judgment."""

    structural_errors, _ = validate_contract_payload(payload)
    report: dict[str, object] = {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "automatic_aesthetic_pass": False,
        "structural_valid": not structural_errors,
        "structural_errors": structural_errors,
        "findings": [],
        "gaps": [],
        "evidence": {"verified": [], "bytes": 0, "capture_coverage": {}},
        "lifecycle": {
            "status": payload.get("record_status"),
            "required_status_for_ready": "reviewed",
            "meaning": "The lifecycle records the evidence stage; it does not certify visual quality or prescribe a style.",
        },
        "ready": False,
        "limitations": [
            "This audit verifies stated evidence, artifact integrity, and review boundaries; it does not score uniqueness, detect AI use, or decide visual quality.",
            "Signature axes are project-selected qualitative evidence, not a font, palette, shape, layout, or motion quota.",
            "Route discovery only binds plainly static output where one public root is unambiguous; it does not infer dynamic, redirected, or source-router routes.",
            "An abstract comparator can be retained when an owner authorizes it; the audit verifies its declared file binding, not the truth of the abstract's interpretation.",
            "Schema-3 rendered-review links verify the installed tool identity, path-bound output marker, declared capture metadata, and exact screenshot hashes. They do not rerun a browser, provide a cryptographic signature against an actor who can rewrite both owned files, or replace human rendered review.",
        ],
    }
    if structural_errors:
        return finalize_report(report)

    findings: list[dict[str, object]] = report["findings"]  # type: ignore[assignment]
    gaps: list[dict[str, str]] = report["gaps"]  # type: ignore[assignment]
    record_status = payload["record_status"]
    if record_status == "draft":
        add_gap(gaps, "project-contrast-draft", "Project Contrast is an intentionally unresolved draft; record the brief-derived direction before requesting proof or readiness.")
        return finalize_report(report)
    if record_status == "direction-ready":
        add_gap(gaps, "project-contrast-direction-ready", "Project Contrast direction is recorded, but a rendered proof and review are still required before readiness.")
        return finalize_report(report)

    budget = EvidenceBudget()
    verified: list[dict[str, object]] = []

    def verify(reference: object, label: str, *, capture: bool = False) -> dict[str, object] | None:
        try:
            result = verify_file_reference(root, reference, label, budget, capture=capture)
            result["label"] = label
            verified.append(result)
            return result
        except AuditError as exc:
            findings.append(finding(exc.code, exc.message, blocking=True))
            return None

    scope = payload["scope"]
    comparison = payload["comparison"]
    evidence = payload["evidence"]
    review = payload["review"]
    signature = payload["design_signature"]
    triggers = set(scope["trigger"])
    recurrence_required = TRIGGER_OWNER_RECURRENCE in triggers
    authority_status = scope["comparison_authority"]["status"]
    scope_routes = set(scope["surface_scope"])
    route_coverage = scope["route_coverage"]
    comparators: list[dict[str, Any]] = comparison["comparators"]
    captures: list[dict[str, Any]] = evidence["captures"]
    route_discovery = discover_static_public_routes(root)

    if record_status == "proof-ready":
        add_gap(gaps, "project-contrast-proof-ready", "Project Contrast proof is recorded, but a reviewed lifecycle state is still required before readiness.")

    candidate_build = evidence["candidate_build"]
    candidate_build_id: str | None = None
    if candidate_build is None:
        add_gap(gaps, "candidate-build-missing", "Candidate-build identity is still unresolved.")
    else:
        candidate_build_id = candidate_build["id"]
        verify(candidate_build["file"], "evidence.candidate_build.file")
    render_review_results: dict[str, dict[str, object]] = {}
    for index, reference in enumerate(evidence["render_reviews"]):
        report_label = f"evidence.render_reviews[{index}]"
        try:
            result = load_schema3_render_review(
                root,
                reference["file"],
                f"{report_label}.file",
                budget,
            )
            verification = result.get("verification")
            if isinstance(verification, dict):
                verification["label"] = f"{report_label}.file"
                verified.append(verification)
            render_review_results[reference["id"]] = result
            if (
                candidate_build_id is not None
                and result.get("build_id") != candidate_build_id
            ):
                findings.append(finding(
                    "render-review-build-mismatch",
                    f"{report_label} is bound to build {result.get('build_id')!r}, not the declared candidate build {candidate_build_id!r}.",
                    blocking=True,
                ))
        except AuditError as exc:
            findings.append(finding(exc.code, exc.message, blocking=True))

    capture_results: dict[str, dict[str, object]] = {}
    captures_by_route_and_class: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for index, capture in enumerate(captures):
        label = f"evidence.captures[{index}]"
        route = capture["route"]
        if route not in scope_routes:
            findings.append(finding("capture-route-out-of-scope", f"{label}.route is not declared in scope.surface_scope.", blocking=True))
        if candidate_build_id is not None and capture["candidate_build_id"] != candidate_build_id:
            findings.append(finding("capture-build-link-mismatch", f"{label} is bound to {capture['candidate_build_id']!r}, not the declared candidate build {candidate_build_id!r}.", blocking=True))
        result = verify(capture["file"], f"{label}.file", capture=True)
        if result is not None:
            capture_results[capture["id"]] = result
            render_binding = capture["render_review"]
            render_report_id = render_binding["report_id"]
            render_capture_id = render_binding["capture_id"]
            render_result = render_review_results.get(render_report_id)
            if render_result is None:
                findings.append(finding(
                    "capture-render-review-unknown",
                    f"{label} names rendered-review report {render_report_id!r}, which did not verify.",
                    blocking=True,
                ))
            else:
                render_captures = render_result.get("captures_by_id")
                render_routes = render_result.get("routes_by_id")
                if not isinstance(render_captures, dict) or not isinstance(render_routes, dict):
                    findings.append(finding(
                        "capture-render-review-invalid",
                        f"{label} cannot inspect the named schema-3 rendered-review capture.",
                        blocking=True,
                    ))
                else:
                    rendered_capture = render_captures.get(render_capture_id)
                    if not isinstance(rendered_capture, dict):
                        findings.append(finding(
                            "capture-render-review-capture-unknown",
                            f"{label} names rendered-review capture {render_capture_id!r}, which is not present in report {render_report_id!r}.",
                            blocking=True,
                        ))
                    else:
                        rendered_route = render_routes.get(rendered_capture.get("route_id"))
                        rendered_final_route = rendered_capture_route_path(
                            rendered_capture.get("final_url")
                        )
                        if (
                            not isinstance(rendered_route, dict)
                            or rendered_final_route != route
                        ):
                            findings.append(finding(
                                "capture-render-route-mismatch",
                                f"{label} route {route!r} does not match the final route bound by rendered-review capture {render_capture_id!r}.",
                                blocking=True,
                            ))
                        rendered_viewport = rendered_capture.get("viewport")
                        viewport = capture["viewport"]
                        if (
                            not isinstance(rendered_viewport, dict)
                            or rendered_viewport.get("width") != viewport["width"]
                            or rendered_viewport.get("height") != viewport["height"]
                        ):
                            findings.append(finding(
                                "capture-render-viewport-mismatch",
                                f"{label} browser viewport does not match its bound schema-3 rendered-review capture.",
                                blocking=True,
                            ))
                        rendered_interaction = rendered_capture.get("interaction")
                        state = capture["capture_state"]
                        if not isinstance(rendered_interaction, dict):
                            findings.append(finding(
                                "capture-render-state-mismatch",
                                f"{label} cannot verify its declared {state!r} state from the schema-3 rendered-review capture.",
                                blocking=True,
                            ))
                        else:
                            requested_steps = rendered_interaction.get("requested_steps")
                            completed_steps = rendered_interaction.get("completed_steps")
                            interaction_status = rendered_interaction.get("status")
                            state_matches = (
                                state == "default"
                                and interaction_status == "not-requested"
                                and requested_steps == 0
                                and completed_steps == 0
                            ) or (
                                state == "interaction"
                                and interaction_status == "complete"
                                and isinstance(requested_steps, int)
                                and requested_steps > 0
                                and completed_steps == requested_steps
                            )
                            if not state_matches:
                                findings.append(finding(
                                    "capture-render-state-mismatch",
                                    f"{label} declares {state!r} but its bound schema-3 interaction evidence does not establish that state.",
                                    blocking=True,
                                ))
                        rendered_screenshot = rendered_capture.get("screenshot")
                        report_relative = render_result.get("report_relative_path")
                        if not isinstance(rendered_screenshot, dict) or not isinstance(report_relative, str):
                            findings.append(finding(
                                "capture-render-screenshot-mismatch",
                                f"{label} has no usable schema-3 rendered screenshot binding.",
                                blocking=True,
                            ))
                        else:
                            expected_path = (
                                PurePosixPath(report_relative).parent
                                / PurePosixPath(str(rendered_screenshot.get("path", "")))
                            ).as_posix()
                            if expected_path.startswith("./"):
                                expected_path = expected_path[2:]
                            try:
                                expected_path = portable_path(
                                    expected_path,
                                    f"{label}.render_review.screenshot.path",
                                )
                            except AuditError as exc:
                                findings.append(finding(exc.code, exc.message, blocking=True))
                                expected_path = None
                            dimensions_match = (
                                result.get("width") == rendered_screenshot.get("pixel_width")
                                and result.get("height") == rendered_screenshot.get("pixel_height")
                            )
                            if (
                                expected_path is None
                                or capture["file"]["path"] != expected_path
                                or capture["file"]["sha256"] != rendered_screenshot.get("sha256")
                                or result.get("sha256") != rendered_screenshot.get("sha256")
                                or not dimensions_match
                            ):
                                findings.append(finding(
                                    "capture-render-screenshot-mismatch",
                                    f"{label} file and pixel dimensions do not match the exact screenshot emitted by rendered-review capture {render_capture_id!r}.",
                                    blocking=True,
                                ))
        key = (route, capture["viewport"]["viewport_class"])
        captures_by_route_and_class.setdefault(key, []).append(capture)

    if not captures:
        add_gap(gaps, "captures-missing", "No project capture evidence is declared.")
    else:
        for route in sorted(scope_routes):
            wide = captures_by_route_and_class.get((route, "wide"), [])
            narrow = captures_by_route_and_class.get((route, "narrow"), [])
            if not wide:
                add_gap(gaps, "wide-capture-missing", f"Scope route {route} lacks a declared wide capture.")
            if not narrow:
                add_gap(gaps, "narrow-capture-missing", f"Scope route {route} lacks a declared narrow capture.")
            if wide and narrow:
                distinct_pair = any(
                    wide_capture["file"]["sha256"] != narrow_capture["file"]["sha256"]
                    and (
                        wide_capture["viewport"]["width"], wide_capture["viewport"]["height"]
                    ) != (
                        narrow_capture["viewport"]["width"], narrow_capture["viewport"]["height"]
                    )
                    for wide_capture in wide
                    for narrow_capture in narrow
                )
                if not distinct_pair:
                    findings.append(finding("wide-narrow-captures-not-distinct", f"Scope route {route} does not have distinct hash-bound wide and narrow capture evidence.", blocking=True))
                ordered_pair = any(
                    wide_capture["viewport"]["width"]
                    > narrow_capture["viewport"]["width"]
                    for wide_capture in wide
                    for narrow_capture in narrow
                )
                if not ordered_pair:
                    findings.append(finding(
                        "wide-narrow-viewport-order-invalid",
                        f"Scope route {route} labels captures wide and narrow, but no verified wide viewport is actually wider than its narrow companion.",
                        blocking=True,
                    ))

    def route_has_verified_wide_narrow_pair(route: str) -> bool:
        """Whether a route has a genuinely reviewed wide/narrow capture pair."""

        wide = captures_by_route_and_class.get((route, "wide"), [])
        narrow = captures_by_route_and_class.get((route, "narrow"), [])
        return any(
            wide_capture.get("id") in capture_results
            and narrow_capture.get("id") in capture_results
            and wide_capture["file"]["sha256"] != narrow_capture["file"]["sha256"]
            and wide_capture["viewport"]["width"] > narrow_capture["viewport"]["width"]
            for wide_capture in wide
            for narrow_capture in narrow
        )

    discovered_routes = set(route_discovery["routes"])
    if route_discovery["status"] == "discovered":
        covered_discovered_routes = scope_routes & discovered_routes
        missing_discovered_routes = discovered_routes - scope_routes
        coverage_mode = route_coverage["mode"]
        if coverage_mode == "all-discovered-public-routes" and missing_discovered_routes:
            add_gap(
                gaps,
                "route-coverage-missing-discovered-routes",
                "all-discovered-public-routes omits static public routes: " + ", ".join(sorted(missing_discovered_routes)),
            )
        elif coverage_mode in {"representative", "sampled-with-rationale"}:
            has_explicit_route_map = isinstance(
                route_coverage.get("discovered_route_map"), list
            ) and bool(route_coverage.get("discovered_route_map"))
            if (
                len(discovered_routes) > 1
                and len(covered_discovered_routes) < 2
                and not has_explicit_route_map
            ):
                add_gap(
                    gaps,
                    "route-coverage-representative-too-narrow",
                    "The static output exposes multiple public routes, but the declared representative/sample scope covers fewer than two of them. Expand the review scope or record all discovered public routes.",
                )
            if not covered_discovered_routes:
                add_gap(
                    gaps,
                    "route-coverage-no-discovered-route",
                    "The declared representative/sample scope does not include any discovered static public route.",
                )
        # Static discovery allows a stronger, honest sample boundary than an
        # arbitrary pair of routes: every discovered route must either be
        # directly captured or name one directly captured representative with
        # a disclosed job/system-equivalence rationale. This does not infer
        # route jobs from file names or turn coverage into a page-count rule.
        if record_status == "reviewed":
            raw_route_map = route_coverage.get("discovered_route_map")
            route_map: dict[str, dict[str, Any]] = {}
            if not isinstance(raw_route_map, list):
                raw_route_map = []
            for entry in raw_route_map:
                if isinstance(entry, dict) and isinstance(entry.get("route"), str):
                    route_map[entry["route"]] = entry
            missing_map_routes = discovered_routes - set(route_map)
            if missing_map_routes:
                add_gap(
                    gaps,
                    "route-coverage-map-missing-discovered-routes",
                    "Every safely discovered static public route needs a captured or reviewed-representative mapping: " + ", ".join(sorted(missing_map_routes)),
                )
            extra_map_routes = set(route_map) - discovered_routes
            if extra_map_routes:
                findings.append(finding(
                    "route-coverage-map-route-not-discovered",
                    "Route coverage mappings name routes outside the safely discovered static public output: " + ", ".join(sorted(extra_map_routes)),
                    blocking=True,
                ))
            for route in sorted(discovered_routes & set(route_map)):
                entry = route_map[route]
                coverage = entry.get("coverage")
                representative = entry.get("representative_route")
                rationale = entry.get("equivalence_rationale")
                if coverage == "captured":
                    if route not in scope_routes or not route_has_verified_wide_narrow_pair(route):
                        add_gap(
                            gaps,
                            "route-coverage-captured-route-unreviewed",
                            f"Discovered route {route} is marked captured but lacks a directly bound verified wide/narrow review pair.",
                        )
                    if representative is not None:
                        findings.append(finding(
                            "route-coverage-captured-route-has-representative",
                            f"Discovered route {route} is marked captured and cannot also point to a representative route.",
                            blocking=True,
                        ))
                elif coverage == "represented":
                    if not isinstance(representative, str) or representative == route:
                        add_gap(
                            gaps,
                            "route-coverage-representative-missing",
                            f"Discovered route {route} must name a different directly reviewed representative route.",
                        )
                        continue
                    representative_entry = route_map.get(representative)
                    representative_captured = (
                        isinstance(representative_entry, dict)
                        and representative_entry.get("coverage") == "captured"
                        and representative in scope_routes
                        and route_has_verified_wide_narrow_pair(representative)
                    )
                    if not representative_captured:
                        add_gap(
                            gaps,
                            "route-coverage-representative-unreviewed",
                            f"Discovered route {route} names {representative!r} as its representative, but that route is not directly reviewed with a verified wide/narrow pair.",
                        )
                    if not text_ok(rationale):
                        add_gap(
                            gaps,
                            "route-coverage-equivalence-rationale-missing",
                            f"Discovered route {route} needs a project-specific job/system-equivalence rationale for using representative {representative!r}.",
                        )
                else:
                    add_gap(
                        gaps,
                        "route-coverage-map-unresolved",
                        f"Discovered route {route} has no captured or represented coverage decision.",
                    )
            if coverage_mode == "all-discovered-public-routes":
                represented_routes = [
                    route
                    for route, entry in route_map.items()
                    if isinstance(entry, dict) and entry.get("coverage") == "represented"
                ]
                if represented_routes:
                    add_gap(
                        gaps,
                        "route-coverage-all-routes-represented",
                        "all-discovered-public-routes cannot clear a route through a representative mapping: " + ", ".join(sorted(represented_routes)),
                    )

    if authority_status == "not-authorized" and comparators:
        findings.append(finding("unauthorized-comparator", "The contract declares comparators despite not-authorized comparison status.", blocking=True))
    if authority_status in {"not-applicable", "not-authorized"} and comparison["contrast_claims"]:
        findings.append(finding("comparison-without-authority", "Contrast claims require an owner-authorized or inherited-system comparison boundary.", blocking=True))
    if authority_status in {"authorized", "inherited-system"} and not comparators:
        add_gap(gaps, "comparators-missing", "An authorized comparison boundary needs at least one declared comparator.")
    verified_comparator_ids: set[str] = set()
    # Keep verified artifact identity, not merely comparator IDs. A claim that
    # calls two rendered surfaces `different` cannot use literal candidate
    # pixels as the comparator image. This is a provenance check, not a visual
    # similarity score: near matches still require the documented review.
    verified_comparator_results: dict[str, dict[str, object]] = {}
    comparator_image_source_ready: dict[str, bool] = {}
    verified_comparator_source_build_hashes: dict[str, str] = {}
    for index, comparator in enumerate(comparators):
        comparator_evidence = comparator["evidence"]
        if comparator_evidence is not None:
            result = verify(
                comparator_evidence["file"],
                f"comparison.comparators[{index}].evidence.file",
                capture=comparator_evidence["kind"] == "image",
            )
            if result is not None:
                verified_comparator_ids.add(comparator["id"])
                verified_comparator_results[comparator["id"]] = {
                    "kind": comparator_evidence["kind"],
                    "result": result,
                }
                if comparator_evidence["kind"] == "image":
                    image_source = comparator_evidence.get("image_source")
                    image_source_ok = False
                    if not isinstance(image_source, dict):
                        if record_status == "reviewed":
                            add_gap(
                                gaps,
                                "comparator-image-source-metadata-missing",
                                f"Image comparator {comparator['id']!r} needs hash-bound source build, route, state, viewport, and full-page extent metadata before it can support a reviewed public comparison.",
                            )
                    else:
                        source_build = image_source.get("source_build")
                        source_build_ok = False
                        if isinstance(source_build, dict):
                            source_result = verify(
                                source_build.get("file"),
                                f"comparison.comparators[{index}].evidence.image_source.source_build.file",
                            )
                            source_build_ok = source_result is not None
                            if (
                                source_result is not None
                                and isinstance(source_result.get("sha256"), str)
                            ):
                                verified_comparator_source_build_hashes[
                                    comparator["id"]
                                ] = source_result["sha256"]
                        extent = image_source.get("extent")
                        viewport = image_source.get("viewport")
                        dimensions_match = (
                            isinstance(extent, dict)
                            and result.get("width") == extent.get("pixel_width")
                            and result.get("height") == extent.get("pixel_height")
                        )
                        extent_covers_viewport = (
                            isinstance(extent, dict)
                            and isinstance(viewport, dict)
                            and isinstance(extent.get("pixel_width"), int)
                            and isinstance(extent.get("pixel_height"), int)
                            and isinstance(viewport.get("width"), int)
                            and isinstance(viewport.get("height"), int)
                            and extent["pixel_width"] >= viewport["width"]
                            and extent["pixel_height"] >= viewport["height"]
                        )
                        if not dimensions_match:
                            findings.append(finding(
                                "comparator-image-extent-mismatch",
                                f"Image comparator {comparator['id']!r} does not match its declared full-page pixel extent.",
                                blocking=True,
                            ))
                        if not extent_covers_viewport:
                            findings.append(finding(
                                "comparator-image-extent-too-small",
                                f"Image comparator {comparator['id']!r} cannot use an extent smaller than its declared browser viewport as whole-route evidence.",
                                blocking=True,
                            ))
                        image_source_ok = (
                            source_build_ok
                            and dimensions_match
                            and extent_covers_viewport
                            and isinstance(image_source.get("route"), str)
                            and isinstance(image_source.get("capture_state"), str)
                        )
                    comparator_image_source_ready[comparator["id"]] = image_source_ok
        elif authority_status in {"authorized", "inherited-system"}:
            add_gap(gaps, "comparator-evidence-missing", f"Comparator {comparator['id']} lacks an authorized hash-bound image or structural abstract.")

    closest_sibling_ids = {
        comparator["id"]
        for comparator in comparators
        if comparator["relationship"] == "closest-sibling"
    }
    verified_closest_sibling_ids = closest_sibling_ids & verified_comparator_ids
    candidate_project_id = scope.get("project_id")
    cross_project_closest_sibling_ids = {
        comparator["id"]
        for comparator in comparators
        if comparator["relationship"] == "closest-sibling"
        and isinstance(comparator.get("project_id"), str)
        and comparator.get("project_id") != candidate_project_id
    }
    verified_cross_project_closest_sibling_ids = (
        cross_project_closest_sibling_ids & verified_comparator_ids
    )

    # A different project_id is necessary but not sufficient evidence of a
    # different prior build. Reject alias/fork laundering when a declared
    # closest sibling reuses the exact bound comparator artifact or the exact
    # bound source-build identity of a comparator attributed to another
    # project. This is provenance integrity, not pixel-similarity scoring.
    comparator_by_id = {
        comparator["id"]: comparator
        for comparator in comparators
        if isinstance(comparator.get("id"), str)
    }

    def comparator_artifact_hash(comparator_id: str) -> str | None:
        entry = verified_comparator_results.get(comparator_id)
        result = entry.get("result") if isinstance(entry, dict) else None
        value = result.get("sha256") if isinstance(result, dict) else None
        return value if isinstance(value, str) else None

    reported_identity_collisions: set[tuple[str, str]] = set()
    for sibling_id in sorted(verified_cross_project_closest_sibling_ids):
        sibling = comparator_by_id.get(sibling_id, {})
        sibling_project = sibling.get("project_id")
        sibling_artifact_hash = comparator_artifact_hash(sibling_id)
        sibling_source_hash = verified_comparator_source_build_hashes.get(sibling_id)
        for other_id in sorted(verified_comparator_ids - {sibling_id}):
            other = comparator_by_id.get(other_id, {})
            other_project = other.get("project_id")
            if (
                not isinstance(sibling_project, str)
                or not isinstance(other_project, str)
                or sibling_project == other_project
            ):
                continue
            same_artifact = (
                isinstance(sibling_artifact_hash, str)
                and sibling_artifact_hash == comparator_artifact_hash(other_id)
            )
            same_source_build = (
                isinstance(sibling_source_hash, str)
                and sibling_source_hash
                == verified_comparator_source_build_hashes.get(other_id)
            )
            if not (same_artifact or same_source_build):
                continue
            pair = tuple(sorted((sibling_id, other_id)))
            if pair in reported_identity_collisions:
                continue
            reported_identity_collisions.add(pair)
            collision_basis = (
                "the exact comparator artifact and source build"
                if same_artifact and same_source_build
                else "the exact comparator artifact"
                if same_artifact
                else "the exact source build"
            )
            findings.append(finding(
                "closest-sibling-artifact-identity-collision",
                f"Closest sibling {sibling_id!r} and comparator {other_id!r} name different projects but reuse {collision_basis}; a renamed, forked, or aliased artifact cannot establish cross-project recurrence evidence.",
                blocking=True,
            ))
    closest_selection = comparison.get("closest_sibling_selection")
    closest_selection_complete = False
    selection_required = (
        record_status == "reviewed"
        and authority_status in {"authorized", "inherited-system"}
        and bool(closest_sibling_ids)
    )
    if selection_required:
        if not isinstance(closest_selection, dict) or closest_selection.get("status") != "selected":
            add_gap(
                gaps,
                "closest-sibling-selection-missing",
                "A reviewed closest-sibling comparison needs a selected owner-authorized ledger snapshot or explicit selection record; a relationship label alone does not establish nearest lineage.",
            )
        else:
            selection_file = closest_selection.get("evidence")
            selection_file_ok = (
                selection_file is not None
                and verify(selection_file, "comparison.closest_sibling_selection.evidence") is not None
            )
            source_kind = closest_selection.get("source_kind")
            selection_ids_raw = closest_selection.get("comparator_ids")
            selection_ids = (
                set(selection_ids_raw)
                if isinstance(selection_ids_raw, list)
                and all(isinstance(entry, str) for entry in selection_ids_raw)
                else set()
            )
            selection_text_ok = (
                text_ok(closest_selection.get("owner_authorization"))
                and text_ok(closest_selection.get("selection_reason"))
            )
            if source_kind not in CLOSEST_SIBLING_SELECTION_SOURCE_KINDS or not selection_text_ok:
                add_gap(
                    gaps,
                    "closest-sibling-selection-unresolved",
                    "The closest-sibling selection must name its owner-authorized ledger/selection source and why that comparator is nearest for this project.",
                )
            if not selection_file_ok:
                add_gap(
                    gaps,
                    "closest-sibling-selection-evidence-unverified",
                    "The closest-sibling selection needs a hash-bound owner-authorized ledger snapshot or explicit selection record.",
                )
            if selection_ids != closest_sibling_ids:
                add_gap(
                    gaps,
                    "closest-sibling-selection-mismatch",
                    "The hash-bound selection record must name exactly the comparator IDs marked closest-sibling; do not substitute a convenient secondary comparator.",
                )
            if not selection_ids.issubset(verified_closest_sibling_ids):
                add_gap(
                    gaps,
                    "closest-sibling-selection-evidence-unverified",
                    "The selected closest-sibling record must bind only comparators whose authorized evidence verified.",
                )
            if selection_file_ok and source_kind in CLOSEST_SIBLING_SELECTION_SOURCE_KINDS and selection_text_ok and selection_ids == closest_sibling_ids and selection_ids.issubset(verified_closest_sibling_ids):
                closest_selection_complete = True

    claims: list[dict[str, Any]] = comparison["contrast_claims"]
    if authority_status in {"authorized", "inherited-system"} and not claims:
        add_gap(gaps, "contrast-claims-missing", "An authorized comparison boundary needs at least one qualitative contrast or justified-reuse claim.")
    accepted_structural_difference = False
    counterfactual = comparison["counterfactual_swap_test"]
    if counterfactual["result"] == "still-too-close":
        add_gap(gaps, "counterfactual-still-too-close", "The qualitative counterfactual review still finds the candidate too interchangeable; reopen the organizing cause.")

    selected_signature_axis_ids = sorted(selected_signature_axes(signature))
    selected_encounter_axes = sorted(
        selected_signature_axes_for_group(signature, "encounter")
    )
    selected_surface_axes = sorted(
        selected_signature_axes_for_group(signature, "surface-language")
    )
    if signature["selection_status"] == "selected" and not selected_signature_axis_ids:
        add_gap(gaps, "signature-axes-unresolved", "The selected project signature has no selected qualitative axis.")

    declared_capture_ids = {capture["id"] for capture in captures}
    declared_captures_by_id = {
        capture["id"]: capture
        for capture in captures
        if isinstance(capture.get("id"), str)
    }
    declared_comparator_ids = {comparator["id"] for comparator in comparators}
    required_review_capture_ids = {
        capture["id"]
        for capture in captures
        if capture.get("route") in scope_routes
        and isinstance(capture.get("viewport"), dict)
        and capture["viewport"].get("viewport_class") in {"wide", "narrow"}
    }
    verified_candidate_capture_hashes = {
        result.get("sha256")
        for result in capture_results.values()
        if isinstance(result.get("sha256"), str)
    }

    def bound_observation_evidence(
        binding: object,
        label: str,
        *,
        require_capture: bool,
        require_comparator: bool,
        require_viewport_class: str | None = None,
        relationship: str | None = None,
        require_full_route_pairs: bool = False,
        require_image_comparator: bool = False,
    ) -> bool:
        """Verify that a qualitative observation names real bound artifacts."""

        if not isinstance(binding, dict):
            add_gap(gaps, "public-grammar-evidence-missing", f"{label} has no evidence binding.")
            return False
        capture_ids = binding.get("capture_ids")
        comparator_ids = binding.get("comparator_ids")
        if not isinstance(capture_ids, list) or not isinstance(comparator_ids, list):
            return False
        if require_capture and not capture_ids:
            add_gap(gaps, "public-grammar-candidate-capture-missing", f"{label} needs at least one hash-bound candidate capture.")
            return False
        if require_comparator and not comparator_ids:
            add_gap(gaps, "public-grammar-comparator-evidence-missing", f"{label} needs at least one authorized comparator reference for this comparison relationship.")
            return False
        valid = True
        matching_viewport_capture = False
        captures_by_route: dict[str, set[str]] = {}
        for capture_id in capture_ids:
            if capture_id not in declared_capture_ids:
                findings.append(finding("public-grammar-capture-id-unknown", f"{label} references unknown capture ID {capture_id!r}.", blocking=True))
                valid = False
            elif capture_id not in capture_results:
                findings.append(finding("public-grammar-capture-unverified", f"{label} references capture ID {capture_id!r} whose file did not verify.", blocking=True))
                valid = False
            elif require_viewport_class is not None:
                declared_capture = declared_captures_by_id.get(capture_id)
                viewport = declared_capture.get("viewport") if isinstance(declared_capture, dict) else None
                if isinstance(viewport, dict) and viewport.get("viewport_class") == require_viewport_class:
                    matching_viewport_capture = True
            declared_capture = declared_captures_by_id.get(capture_id)
            if isinstance(declared_capture, dict):
                route = declared_capture.get("route")
                viewport = declared_capture.get("viewport")
                viewport_class = viewport.get("viewport_class") if isinstance(viewport, dict) else None
                if isinstance(route, str) and isinstance(viewport_class, str):
                    captures_by_route.setdefault(route, set()).add(viewport_class)
        for comparator_id in comparator_ids:
            if comparator_id not in declared_comparator_ids:
                findings.append(finding("public-grammar-comparator-id-unknown", f"{label} references unknown comparator ID {comparator_id!r}.", blocking=True))
                valid = False
            elif comparator_id not in verified_comparator_ids:
                findings.append(finding("public-grammar-comparator-unverified", f"{label} references comparator ID {comparator_id!r} whose evidence did not verify.", blocking=True))
                valid = False
            elif relationship == "different":
                comparator_result = verified_comparator_results.get(comparator_id)
                comparator_file = (
                    comparator_result.get("result")
                    if isinstance(comparator_result, dict)
                    else None
                )
                comparator_sha = (
                    comparator_file.get("sha256")
                    if isinstance(comparator_file, dict)
                    else None
                )
                if (
                    isinstance(comparator_result, dict)
                    and comparator_result.get("kind") == "image"
                    and isinstance(comparator_sha, str)
                    and comparator_sha in verified_candidate_capture_hashes
                ):
                    findings.append(finding(
                        "comparison-different-reuses-candidate-pixels",
                        f"{label} calls comparator {comparator_id!r} different, but its image bytes duplicate a verified candidate capture.",
                        blocking=True,
                    ))
                    valid = False
            comparator_result = verified_comparator_results.get(comparator_id)
            comparator_kind = (
                comparator_result.get("kind")
                if isinstance(comparator_result, dict)
                else None
            )
            if require_image_comparator and comparator_kind != "image":
                findings.append(finding(
                    "structural-abstract-cannot-support-surface-difference",
                    f"{label} is a visible surface/public-shell different claim and cannot use structural abstract {comparator_id!r} as its comparator evidence.",
                    blocking=True,
                ))
                valid = False
            if comparator_kind == "image" and not comparator_image_source_ready.get(comparator_id, False):
                add_gap(
                    gaps,
                    "comparator-image-source-metadata-unverified",
                    f"{label} references image comparator {comparator_id!r} without verified source build, route, state, viewport, and full-page extent metadata.",
                )
                valid = False
        if require_viewport_class is not None and not matching_viewport_capture:
            add_gap(
                gaps,
                "public-grammar-required-viewport-missing",
                f"{label} must bind at least one verified {require_viewport_class} candidate capture for this claimed encounter.",
            )
            valid = False
        if require_full_route_pairs:
            missing_pair_routes = sorted(
                route
                for route, classes in captures_by_route.items()
                if not {"wide", "narrow"}.issubset(classes)
            )
            if not captures_by_route or missing_pair_routes:
                add_gap(
                    gaps,
                    "claim-wide-narrow-evidence-missing",
                    f"{label} needs the complete declared wide/narrow capture pair for every route it uses as reviewed comparison evidence"
                    + (": " + ", ".join(missing_pair_routes) if missing_pair_routes else "."),
                )
                valid = False
        return valid

    def binds_verified_closest_sibling(binding: object) -> bool:
        """Return whether this observation actually exposes the closest sibling.

        Owner recurrence is a claim about the nearest authorized prior answer,
        not merely any safely retained comparator. Other authorized comparators
        may still enrich a review, but cannot substitute for that boundary. A
        same-project rejected candidate is valuable rejection evidence, but it
        cannot by itself test cross-project recurrence.
        """

        required_ids = (
            verified_cross_project_closest_sibling_ids
            if recurrence_required
            else verified_closest_sibling_ids
        )
        return (
            isinstance(binding, dict)
            and isinstance(binding.get("comparator_ids"), list)
            and bool(set(binding["comparator_ids"]) & required_ids)
        )

    structural_against_closest_sibling = False
    for claim_index, claim in enumerate(claims):
        if not (
            claim["relationship"] == "different"
            and claim["status"] == "accepted"
            and claim["level"] in STRUCTURAL_LEVELS
        ):
            continue
        level = claim["level"]
        evidence_ok = bound_observation_evidence(
            claim["evidence"],
            f"comparison.contrast_claims[{claim_index}].evidence",
            require_capture=True,
            require_comparator=True,
            require_viewport_class="narrow" if level == "mobile-encounter" else None,
            relationship=claim["relationship"],
            require_full_route_pairs=True,
        )
        if evidence_ok:
            accepted_structural_difference = True
            if binds_verified_closest_sibling(claim["evidence"]):
                structural_against_closest_sibling = True
        elif recurrence_required:
            add_gap(
                gaps,
                "structural-claim-evidence-missing",
                "An accepted structural contrast claim needs verified schema-3 candidate capture evidence and an authorized comparator artifact; mobile-encounter claims also need narrow evidence.",
            )

    shared_public_shell = comparison["shared_public_shell"]
    shell_classification = shared_public_shell["classification"]
    shared_shell_evidence_ok = False
    shared_shell_against_closest_sibling = False
    approved_public_system_complete = False
    if shell_classification in {"approved-public-system", "candidate-public-shell"}:
        shell_requires_comparator = shell_classification == "candidate-public-shell"
        shared_shell_evidence_ok = bound_observation_evidence(
            shared_public_shell["evidence"],
            "comparison.shared_public_shell",
            require_capture=True,
            require_comparator=shell_requires_comparator,
            relationship="different" if shell_requires_comparator else None,
            require_full_route_pairs=True,
            require_image_comparator=shell_requires_comparator,
        )
        shared_shell_against_closest_sibling = (
            shared_shell_evidence_ok
            and binds_verified_closest_sibling(shared_public_shell["evidence"])
        )
    if shell_classification == "approved-public-system" and record_status == "reviewed":
        approval = shared_public_shell.get("approval")
        if not isinstance(approval, dict) or approval.get("status") != "owner-approved":
            add_gap(
                gaps,
                "approved-public-system-owner-approval-missing",
                "Visible public chrome cannot be treated as an approved public system without a scoped owner-approved, hash-bound approval record; otherwise review it as candidate-public-shell.",
            )
        else:
            approval_scope_ok = text_ok(approval.get("scope"))
            approval_evidence = approval.get("evidence")
            approval_file_ok = (
                approval_evidence is not None
                and verify(approval_evidence, "comparison.shared_public_shell.approval.evidence") is not None
            )
            if not approval_scope_ok:
                add_gap(
                    gaps,
                    "approved-public-system-approval-scope-missing",
                    "An approved public-system record needs a bounded scope so visible shell approval does not silently pre-approve unrelated project encounters.",
                )
            if not approval_file_ok:
                add_gap(
                    gaps,
                    "approved-public-system-approval-evidence-unverified",
                    "An approved public-system record needs hash-bound owner approval evidence.",
                )
            approved_public_system_complete = (
                approval_scope_ok and approval_file_ok and shared_shell_evidence_ok
            )

    surface_observations: list[dict[str, Any]] = comparison["surface_grammar_observations"]
    observed_surface_axes: set[str] = set()
    if authority_status in {"not-authorized", "not-applicable"}:
        if any(observation["relationship"] != "not-comparable" for observation in surface_observations):
            findings.append(finding("surface-comparison-without-authority", "Surface-grammar comparison claims require an owner-authorized or inherited-system comparison boundary.", blocking=True))
    for index, observation in enumerate(surface_observations):
        label = f"comparison.surface_grammar_observations[{index}]"
        status = observation["status"]
        relationship = observation["relationship"]
        active = status in SURFACE_OBSERVATION_READY_STATUSES
        requires_comparator = relationship in {"different", "shared-with-reason"}
        evidence_ok = bound_observation_evidence(
            observation["evidence"],
            label,
            require_capture=active,
            require_comparator=active and requires_comparator,
            relationship=relationship,
            require_full_route_pairs=active,
            require_image_comparator=active and relationship == "different",
        )
        referenced_axes = set(observation["selected_signature_axis_refs"])
        unselected_axes = referenced_axes - set(selected_surface_axes)
        if unselected_axes:
            findings.append(finding(
                "surface-grammar-axis-not-selected",
                f"{label} references a surface signature axis that is not selected for this project: " + ", ".join(sorted(unselected_axes)),
                blocking=True,
            ))
        # `not-comparable` may honestly preserve a candidate-only observation,
        # but it cannot establish a selected surface axis for an owner
        # recurrence claim. That gate needs a real comparison relationship and
        # a verified authorized comparator, not merely a hash-bound sentence.
        if (
            active
            and requires_comparator
            and evidence_ok
            and (
                not recurrence_required
                or binds_verified_closest_sibling(observation["evidence"])
            )
        ):
            observed_surface_axes.update(referenced_axes & set(selected_surface_axes))

    def verify_review_capture_ids(phase: str, phase_record: dict[str, Any]) -> bool:
        """Bind a reviewer exposure to already verified schema-3 candidate captures."""

        reviewed_capture_ids = phase_record.get("reviewed_capture_ids")
        if not isinstance(reviewed_capture_ids, list) or not reviewed_capture_ids:
            findings.append(finding(
                "review-candidate-captures-missing",
                f"{phase} review is complete without nonempty candidate capture exposure.",
                blocking=True,
            ))
            return False
        valid = True
        for capture_id in reviewed_capture_ids:
            if capture_id not in declared_capture_ids:
                findings.append(finding(
                    "review-candidate-capture-id-unknown",
                    f"{phase} review names unknown candidate capture ID {capture_id!r}.",
                    blocking=True,
                ))
                valid = False
            elif capture_id not in capture_results:
                findings.append(finding(
                    "review-candidate-capture-unverified",
                    f"{phase} review names candidate capture ID {capture_id!r} whose schema-3 evidence did not verify.",
                    blocking=True,
                ))
                valid = False
        missing_required_capture_ids = required_review_capture_ids - set(reviewed_capture_ids)
        if missing_required_capture_ids:
            findings.append(finding(
                "review-wide-narrow-exposure-incomplete",
                f"{phase} review does not expose the complete declared wide/narrow candidate evidence: " + ", ".join(sorted(missing_required_capture_ids)),
                blocking=True,
            ))
            valid = False
        return valid

    def verify_review_comparator_ids(phase: str, phase_record: dict[str, Any]) -> bool:
        """Bind a paired reviewer exposure to authorized comparison artifacts."""

        reviewed_comparator_ids = phase_record.get("reviewed_comparator_ids")
        if not isinstance(reviewed_comparator_ids, list) or not reviewed_comparator_ids:
            findings.append(finding(
                "review-comparator-evidence-missing",
                f"{phase} review is complete without an authorized comparator exposure.",
                blocking=True,
            ))
            return False
        valid = True
        for comparator_id in reviewed_comparator_ids:
            if comparator_id not in declared_comparator_ids:
                findings.append(finding(
                    "review-comparator-id-unknown",
                    f"{phase} review names unknown comparator ID {comparator_id!r}.",
                    blocking=True,
                ))
                valid = False
            elif comparator_id not in verified_comparator_ids:
                findings.append(finding(
                    "review-comparator-unverified",
                    f"{phase} review names comparator ID {comparator_id!r} whose authorized evidence did not verify.",
                    blocking=True,
                ))
                valid = False
        return valid

    def check_review(phase: str) -> tuple[bool, bool, datetime | None, datetime | None]:
        """Return (artifact_complete, independently_unprimed, observed, frozen).

        A self-review can be retained as a truthful diagnostic record, but it
        never closes the independent unprimed-review gate. Exposure IDs bind
        the review to the actual candidate/comparator artifacts instead of a
        bare opaque reviewer file.
        """

        phase_record = review[phase]
        status = phase_record["status"]
        frozen = parse_zoned_datetime(phase_record["frozen_at"])
        observed = parse_zoned_datetime(phase_record["observed_at"])
        if status == "complete":
            relationship = phase_record.get("relationship")
            exposure = phase_record.get("exposure")
            complete = True
            if (
                not phase_record["reviewer_id"]
                or relationship not in REVIEW_RELATIONSHIPS
                or observed is None
                or frozen is None
                or phase_record["evidence"] is None
            ):
                findings.append(finding(
                    "review-metadata-incomplete",
                    f"{phase} review is marked complete without reviewer, relationship, zoned times, and evidence.",
                    blocking=True,
                ))
                complete = False
            if frozen is not None and observed is not None and frozen < observed:
                findings.append(finding("review-freeze-before-observation", f"{phase} review froze before observation.", blocking=True))
                complete = False
            if phase == "unprimed":
                if exposure != UNPRIMED_EXPOSURE:
                    findings.append(finding(
                        "unprimed-review-exposure-invalid",
                        "An unprimed review may expose only neutral-label candidate captures, not comparator material.",
                        blocking=True,
                    ))
                    complete = False
                if phase_record.get("reviewed_comparator_ids"):
                    findings.append(finding(
                        "unprimed-review-comparator-exposure",
                        "An unprimed review cannot name comparator artifacts.",
                        blocking=True,
                    ))
                    complete = False
                if not text_ok(phase_record.get("first_observation")):
                    findings.append(finding(
                        "unprimed-first-observation-missing",
                        "An unprimed review must preserve a nonempty first observation before comparison vocabulary.",
                        blocking=True,
                    ))
                    complete = False
            elif phase == "paired":
                if exposure != PAIRED_EXPOSURE:
                    findings.append(finding(
                        "paired-review-exposure-invalid",
                        "A paired review must declare candidate capture and authorized comparator exposure.",
                        blocking=True,
                    ))
                    complete = False
                if not verify_review_comparator_ids(phase, phase_record):
                    complete = False
            if not verify_review_capture_ids(phase, phase_record):
                complete = False
            if phase_record["evidence"] is not None and verify(phase_record["evidence"], f"review.{phase}.evidence") is None:
                complete = False
            independently_unprimed = (
                phase == "unprimed"
                and complete
                and relationship in INDEPENDENT_UNPRIMED_RELATIONSHIPS
            )
            return complete, independently_unprimed, observed, frozen
        if (
            phase_record["evidence"] is not None
            or phase_record.get("reviewed_capture_ids")
            or phase_record.get("reviewed_comparator_ids")
        ):
            findings.append(finding(
                "unsettled-review-has-evidence",
                f"{phase} review is not complete but declares an evidence artifact or reviewed evidence IDs.",
                blocking=True,
            ))
        return False, False, observed, frozen

    unprimed_artifact_complete, unprimed_complete, _unprimed_observed, unprimed_frozen = check_review("unprimed")
    paired_complete, _paired_independent, paired_observed, paired_frozen = check_review("paired")
    if unprimed_artifact_complete and not unprimed_complete:
        add_gap(
            gaps,
            "unprimed-review-not-independent",
            "A self-review may be retained as a diagnostic record, but it cannot satisfy the independent unprimed-review gate.",
        )
    if review["paired"]["status"] == "complete" and unprimed_artifact_complete and paired_observed is not None and unprimed_frozen is not None and paired_observed <= unprimed_frozen:
        findings.append(finding("paired-observation-before-unprimed-freeze", "Paired review observation must occur after the unprimed observation was frozen; equal timestamps do not establish that order.", blocking=True))

    paired_outcome = review.get("paired_outcome")
    paired_outcome_result: str | None = None
    if paired_complete:
        if not isinstance(paired_outcome, dict) or paired_outcome.get("result") not in PAIRED_OUTCOME_RESULTS:
            add_gap(
                gaps,
                "paired-review-outcome-missing",
                "A complete paired review needs a structured not-interchangeable, still-too-close, or inconclusive outcome before it can support a contrast disposition.",
            )
        else:
            paired_outcome_result = paired_outcome["result"]
            if not text_ok(paired_outcome.get("basis")):
                add_gap(
                    gaps,
                    "paired-review-outcome-basis-missing",
                    "A structured paired result needs a project-specific basis tied to the exposed candidate and comparator evidence.",
                )
            if not text_ok(paired_outcome.get("earliest_reopen_decision")):
                add_gap(
                    gaps,
                    "paired-review-outcome-reopen-decision-missing",
                    "A structured paired result needs the earliest decision to reopen if the comparison does not hold.",
                )
            if paired_outcome_result == "still-too-close":
                add_gap(
                    gaps,
                    "paired-review-still-too-close",
                    "The paired review still finds the candidate too close; reopen the earliest shared organizing decision and rerender before readiness.",
                )
            elif paired_outcome_result == "inconclusive":
                add_gap(
                    gaps,
                    "paired-review-inconclusive",
                    "The paired review is inconclusive and cannot clear a Project Contrast disposition without additional bounded evidence.",
                )

    owner_review = review["owner_review"]
    owner_status = owner_review["status"]
    owner_relationship = owner_review["relationship"]
    owner_complete = False
    owner_observed: datetime | None = None
    if owner_status in {"accepted", "rejected"}:
        owner_observed = parse_zoned_datetime(owner_review["observed_at"])
        if not owner_review["reviewer_id"] or owner_observed is None or owner_review["evidence"] is None:
            findings.append(finding("owner-review-metadata-incomplete", "A recorded owner review needs reviewer identity, zoned observation time, and hash-bound evidence.", blocking=True))
        else:
            owner_complete = verify(owner_review["evidence"], "review.owner_review.evidence") is not None
        if owner_status == "accepted" and owner_relationship not in OWNER_ACCEPTANCE_RELATIONSHIPS:
            findings.append(finding("owner-review-relationship-invalid", "An accepted owner review must identify an accountable owner or owner-authorized human relationship.", blocking=True))
        if owner_status == "accepted":
            owner_build_id = owner_review.get("candidate_build_id")
            owner_capture_ids = owner_review.get("reviewed_capture_ids")
            owner_binding_valid = True
            if not isinstance(owner_build_id, str) or owner_build_id != candidate_build_id:
                findings.append(finding(
                    "owner-acceptance-candidate-build-unbound",
                    "Owner acceptance must bind the exact reviewed candidate build rather than a generic project state.",
                    blocking=True,
                ))
                owner_binding_valid = False
            if not isinstance(owner_capture_ids, list) or not owner_capture_ids:
                findings.append(finding(
                    "owner-acceptance-captures-missing",
                    "Owner acceptance must name the reviewed candidate capture IDs.",
                    blocking=True,
                ))
                owner_binding_valid = False
            else:
                unknown_owner_capture_ids = {
                    capture_id
                    for capture_id in owner_capture_ids
                    if capture_id not in declared_capture_ids or capture_id not in capture_results
                }
                missing_owner_capture_ids = required_review_capture_ids - set(owner_capture_ids)
                if unknown_owner_capture_ids:
                    findings.append(finding(
                        "owner-acceptance-capture-unverified",
                        "Owner acceptance names unknown or unverified candidate capture IDs: " + ", ".join(sorted(str(entry) for entry in unknown_owner_capture_ids)),
                        blocking=True,
                    ))
                    owner_binding_valid = False
                if missing_owner_capture_ids:
                    findings.append(finding(
                        "owner-acceptance-wide-narrow-exposure-incomplete",
                        "Owner acceptance must bind the complete declared wide/narrow candidate capture set: " + ", ".join(sorted(missing_owner_capture_ids)),
                        blocking=True,
                    ))
                    owner_binding_valid = False
            owner_complete = owner_complete and owner_binding_valid
        if owner_status == "rejected":
            findings.append(finding("owner-review-rejected", "The accountable owner rejected the Project Contrast review; reopen the identified design work before readiness.", blocking=True))
    elif owner_review["evidence"] is not None:
        findings.append(finding("unsettled-owner-review-has-evidence", "A pending or not-requested owner review must not be represented as completed evidence.", blocking=True))

    if not unprimed_complete:
        add_gap(gaps, "unprimed-review-incomplete", "A complete unprimed perception review is required before project-contrast readiness.")
    if authority_status in {"authorized", "inherited-system"} and not paired_complete:
        add_gap(gaps, "paired-review-incomplete", "An authorized comparison boundary requires a complete paired review or an explicit blocked disposition.")
    if authority_status == "not-authorized" and review["paired"]["status"] != "not-available":
        add_gap(gaps, "paired-review-authority-unresolved", "Without comparison authority, the paired review must be honestly marked not-available.")

    if review["disposition"] != "accepted":
        add_gap(gaps, "contrast-disposition-incomplete", "Project Contrast remains pending, rework, or blocked.")
    if any(prediction["status"] == "planned" for prediction in payload["selected_direction"]["observable_predictions"]):
        add_gap(gaps, "observable-prediction-unverified", "At least one declared observable prediction remains planned.")

    if recurrence_required:
        if authority_status != "authorized":
            add_gap(gaps, "owner-recurrence-authority-missing", "owner-recurrence-requirement needs an explicit authorized comparison boundary.")
        if not comparators:
            add_gap(gaps, "closest-sibling-missing", "owner-recurrence-requirement needs at least one authorized comparator.")
        elif not any(comparator["relationship"] == "closest-sibling" for comparator in comparators):
            add_gap(gaps, "closest-sibling-missing", "At least one comparator must be marked closest-sibling.")
        elif not cross_project_closest_sibling_ids:
            add_gap(
                gaps,
                "closest-sibling-cross-project-missing",
                "owner-recurrence-requirement is a cross-project claim: at least one closest-sibling comparator must name a different project_id. Keep same-project rejected candidates as separate diagnostic evidence.",
            )
        elif not verified_cross_project_closest_sibling_ids:
            add_gap(gaps, "closest-sibling-evidence-unverified", "owner-recurrence-requirement names a closest sibling whose authorized evidence did not verify.")
        if not accepted_structural_difference:
            add_gap(gaps, "structural-contrast-unproven", "owner-recurrence-requirement needs an accepted contrast claim at encounter, opening, body, or content-unit level.")
        elif not structural_against_closest_sibling:
            add_gap(gaps, "closest-sibling-structural-evidence-missing", "owner-recurrence-requirement needs an accepted structural claim that binds the verified closest-sibling comparator, not only another authorized comparator.")
        if counterfactual["result"] != "not-interchangeable":
            add_gap(gaps, "counterfactual-contrast-unproven", "owner-recurrence-requirement needs a reviewed not-interchangeable counterfactual result.")
        if signature["selection_status"] != "selected" or not selected_encounter_axes:
            add_gap(gaps, "signature-encounter-axes-required", "owner-recurrence-requirement needs a nonempty project-selected encounter-axis set; it does not prescribe a visual style.")
        if signature["selection_status"] != "selected" or not selected_surface_axes:
            add_gap(gaps, "signature-surface-axes-required", "owner-recurrence-requirement needs a nonempty project-selected surface-language axis set; it is not a font, palette, shape, or effect rule.")
        else:
            missing_surface_evidence = set(selected_surface_axes) - observed_surface_axes
            if missing_surface_evidence:
                add_gap(
                    gaps,
                    "surface-grammar-evidence-missing",
                    "owner-recurrence-requirement needs an observed or revised, hash-bound project-defined surface-grammar comparison for selected axes: " + ", ".join(sorted(missing_surface_evidence)),
                )
        paired_comparator_ids = review["paired"].get("reviewed_comparator_ids")
        if (
            not isinstance(paired_comparator_ids, list)
            or not (set(paired_comparator_ids) & verified_cross_project_closest_sibling_ids)
        ):
            add_gap(gaps, "closest-sibling-paired-review-missing", "owner-recurrence-requirement needs the paired review to expose the verified cross-project closest-sibling comparator, not only a same-project rejection or another authorized comparator.")
        if shell_classification == "candidate-public-shell":
            shell_collision_observed = False
            for claim_index, claim in enumerate(claims):
                if (
                    claim["level"] != "public-shell"
                    or claim["status"] not in SURFACE_OBSERVATION_READY_STATUSES
                    or claim["relationship"] not in {"different", "shared-with-reason"}
                    or not isinstance(claim["evidence"], dict)
                ):
                    continue
                claim_evidence_ok = bound_observation_evidence(
                    claim["evidence"],
                    f"comparison.contrast_claims[{claim_index}].evidence",
                    require_capture=True,
                    require_comparator=True,
                    relationship=claim["relationship"],
                    require_full_route_pairs=True,
                    require_image_comparator=claim["relationship"] == "different",
                )
                if (
                    shared_shell_evidence_ok
                    and shared_shell_against_closest_sibling
                    and claim_evidence_ok
                    and binds_verified_closest_sibling(claim["evidence"])
                ):
                    shell_collision_observed = True
                    break
            if not shell_collision_observed:
                add_gap(
                    gaps,
                    "public-shell-collision-unresolved",
                    "A candidate public shell needs an observed or revised public-shell claim with a different or shared-with-reason relationship plus hash-bound candidate and closest-sibling comparator evidence; technical foundations, another comparator, and not-comparable prose cannot bypass this recurrence review.",
                )
        if (
            owner_status == "accepted"
            and owner_observed is not None
            and (paired_frozen is None or owner_observed <= paired_frozen)
        ):
            findings.append(finding(
                "owner-acceptance-before-paired-freeze",
                "Owner acceptance must be observed after the paired review was frozen; equal or earlier timestamps do not establish informed acceptance.",
                blocking=True,
            ))

    owner_timing_valid = (
        not recurrence_required
        or (
            owner_observed is not None
            and paired_frozen is not None
            and owner_observed > paired_frozen
        )
    )
    owner_acceptance_complete = (
        owner_status == "accepted"
        and owner_complete
        and owner_relationship in OWNER_ACCEPTANCE_RELATIONSHIPS
        and owner_timing_valid
    )
    unsettled_owner_evidence = (
        owner_status not in {"accepted", "rejected"}
        and owner_review.get("evidence") is not None
    )
    report["owner_acceptance"] = {
        "status": owner_status,
        "complete": owner_acceptance_complete,
        "required_for": [
            "owner-approved or owner-accepted claim",
            "publication, portfolio, or release approval when project policy requires it",
        ],
        "blocks_candidate_readiness": (
            owner_status == "rejected"
            or (owner_status == "accepted" and not owner_acceptance_complete)
            or unsettled_owner_evidence
        ),
        "meaning": (
            "Owner acceptance is separate from candidate evidence readiness. "
            "Pending or not-requested acceptance does not stop a validated "
            "candidate; rejection or a malformed acceptance claim does."
        ),
    }

    report["evidence"] = {
        "verified": verified,
        "bytes": budget.bytes,
        "capture_coverage": {
            "scope_routes": sorted(scope_routes),
            "declared_mode": route_coverage["mode"],
            "declared_rationale": route_coverage["rationale"],
            "static_discovery": route_discovery,
            "capture_ids_with_verified_files": sorted(capture_results),
            "required_viewport_classes": ["wide", "narrow"],
            "candidate_build_id": candidate_build_id,
        },
    }
    report["comparison"] = {
        "authority_status": authority_status,
        "triggered_by_owner_recurrence_requirement": recurrence_required,
        "comparator_ids": [comparator["id"] for comparator in comparators],
        "closest_sibling_ids": sorted(closest_sibling_ids),
        "verified_closest_sibling_ids": sorted(verified_closest_sibling_ids),
        "cross_project_closest_sibling_ids": sorted(cross_project_closest_sibling_ids),
        "verified_cross_project_closest_sibling_ids": sorted(verified_cross_project_closest_sibling_ids),
        "closest_sibling_selection_complete": closest_selection_complete,
        "comparator_evidence_kinds": [
            comparator["evidence"]["kind"]
            for comparator in comparators
            if comparator["evidence"] is not None
        ],
        "accepted_structural_difference": accepted_structural_difference,
        "structural_difference_against_closest_sibling": structural_against_closest_sibling,
        "counterfactual_result": counterfactual["result"],
        "paired_outcome_result": paired_outcome_result,
        "shared_public_shell_classification": shell_classification,
        "approved_public_system_complete": approved_public_system_complete,
        "surface_grammar_observation_ids": [observation["id"] for observation in surface_observations],
        "observed_surface_axes": sorted(observed_surface_axes),
    }
    report["design_signature"] = {
        "selection_status": signature["selection_status"],
        "selected_axes": selected_signature_axis_ids,
        "selected_encounter_axes": selected_encounter_axes,
        "selected_surface_axes": selected_surface_axes,
        "observed_surface_axes": sorted(observed_surface_axes),
        "not_a_style_quota": True,
    }
    return finalize_report(report)


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuditError("duplicate-json-key", f"Contract has a duplicate key: {key!r}.")
        result[key] = value
    return result


def load_contract(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise AuditError("contract-missing", "Project Contrast contract is not an ordinary file.")
    payload = stable_read(path, "contract")
    if len(payload) > MAX_CONTRACT_BYTES:
        raise AuditError("contract-too-large", "Project Contrast contract exceeds the byte limit.")
    try:
        decoded = json.loads(payload.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError("contract-invalid-json", "Project Contrast contract is not valid UTF-8 JSON.") from exc
    if not isinstance(decoded, dict):
        raise AuditError("contract-invalid-root", "Project Contrast contract root must be an object.")
    return decoded


def resolve_contract(root: Path, contract: str) -> Path:
    return project_file(root, portable_path(contract, "contract"), "contract")


def output_path(root: Path, output: str) -> Path:
    return project_file(root, portable_path(output, "output"), "output")


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_symlink():
        raise AuditError("linked-output-refused", "Refusing to replace a symbolic-link output.")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise AuditError("output-write-failed", str(exc)) from exc
    finally:
        if os.path.exists(temporary):
            try:
                os.unlink(temporary)
            except OSError:
                pass


def run(project: Path, contract_arg: str) -> tuple[dict[str, object], int]:
    try:
        root = project.resolve(strict=True)
    except OSError as exc:
        raise AuditError("project-not-found", "Project root does not exist.") from exc
    if not root.is_dir():
        raise AuditError("project-not-found", "Project root does not exist or is not a directory.")
    contract_path = resolve_contract(root, contract_arg)
    payload = load_contract(contract_path)
    report = audit_payload(root, payload)
    report["project_root"] = str(root)
    report["contract"] = {
        "path": portable_path(contract_arg, "contract"),
        "sha256": hashlib.sha256(stable_read(contract_path, "contract")).hexdigest(),
    }
    # This is intentionally strict: a valid but incomplete record is not a
    # passing readiness result. Callers gathering a work-in-progress report
    # must opt into a non-failing diagnostic mode.
    return report, 0 if report.get("ready") is True else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Project root containing the project-local contract.")
    parser.add_argument("--contract", default=DEFAULT_CONTRACT, help=f"Portable project-relative contract path (default: {DEFAULT_CONTRACT}).")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"Portable project-relative report path (default: {DEFAULT_OUTPUT}).")
    completion_mode = parser.add_mutually_exclusive_group()
    completion_mode.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Write a diagnostic report and exit zero when the record is incomplete; unreadable contracts still fail.",
    )
    completion_mode.add_argument(
        "--report-only",
        action="store_true",
        help="Alias for --allow-incomplete when collecting a report rather than asserting readiness.",
    )
    completion_mode.add_argument(
        "--require-ready",
        action="store_true",
        help="Deprecated compatibility flag; readiness is required by default.",
    )
    parser.add_argument("--stdout", action="store_true", help="Also print the report JSON to stdout.")
    args = parser.parse_args()
    try:
        report, code = run(args.project, args.contract)
        try:
            root = args.project.resolve(strict=True)
        except OSError as exc:
            raise AuditError("project-not-found", "Project root does not exist.") from exc
        target = output_path(root, args.output)
        write_json(target, report)
        if args.stdout:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(f"{('OK' if report['ready'] else 'INCOMPLETE')}: {target}")
        if (args.allow_incomplete or args.report_only) and report.get("structural_valid") is True:
            return 0
        return code
    except AuditError as exc:
        error = {
            "artifact_type": ARTIFACT_TYPE,
            "schema_version": SCHEMA_VERSION,
            "tool_version": TOOL_VERSION,
            "automatic_aesthetic_pass": False,
            "ready": False,
            "error": {"code": exc.code, "message": exc.message},
        }
        if args.stdout:
            print(json.dumps(error, indent=2, sort_keys=True))
        else:
            print(f"FAIL: {exc.code}: {exc.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
