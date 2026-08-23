#!/usr/bin/env python3
"""Audit a Design DNA Direction Challenge record.

The capability binds a brief-native decision process to inspectable evidence.
It deliberately does not calculate an aesthetic or authorship score, select a
style, or ban a font, palette, geometry, component, or motif.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
TOOL_VERSION = "1.2.0"
ARTIFACT_TYPE = "design-dna-direction-challenge-audit"
DEFAULT_CONTRACT = ".design-dna/direction-challenge.json"
DEFAULT_OUTPUT = ".design-dna/direction-challenge-audit.json"
MAX_CONTRACT_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_EVIDENCE_BYTES = 256 * 1024 * 1024
MAX_CREATED_WITH_LENGTH = 200
MAX_TEXT_LENGTH = 8000
# Match the schema-3 renderer's profile floor. This rejects an adapter-only
# proof shape that the shipped renderer cannot produce.
MIN_RENDERED_PROOF_VIEWPORT_WIDTH = 240
MIN_RENDERED_PROOF_VIEWPORT_HEIGHT = 240
MAX_FILE_REF_PATH_LENGTH = 1000
MIN_SEQUENCE = 1
MAX_SEQUENCE = 1000
MAX_REFERENCE_EVENTS = 128
MAX_ROOTS = 8
MAX_CHALLENGE_MATRIX_ENTRIES = 28
MIN_MATRIX_INCOMPATIBILITIES = 2
MAX_MATRIX_INCOMPATIBILITIES = 5
MAX_PROOF_SLICES = 16
ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
UNRESOLVED_TEMPLATE_MARKERS = (
    re.compile(r"__[A-Za-z][A-Za-z0-9_-]{1,126}__"),
    re.compile(r"\{\{[A-Za-z][^{}\r\n]{0,126}\}\}"),
)
RENDER_CAPTURE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,47}$")
ROOT_FIELDS = (
    "organizing_logic",
    "entry_encounter",
    "content_operation",
    "body_progression",
    "visitor_agency",
)
LIFECYCLE = {"draft", "roots-ready", "proof-ready", "reviewed"}
LIFECYCLE_ORDER = {
    "draft": 0,
    "roots-ready": 1,
    "proof-ready": 2,
    "reviewed": 3,
}
ROOT_FIELDS_SET = set(ROOT_FIELDS)
EVENT_KINDS = {
    "supplied-brand-material",
    "supplied-source-material",
    "root-recorded",
    "polished-example",
    "reference-decomposition",
    "other",
}
UNPRIMED_RELATIONSHIPS = {
    "independent-human",
    "independent-agent",
    "owner-authorized-independent",
}
UNPRIMED_EXPOSURE = "unprimed-proof-slices-only"
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
SOURCE_SNAPSHOT_POLICY = "frozen-deny-by-default-public-root"
SOURCE_SNAPSHOT_DRIFT_CHECK = "passed-source-and-frozen-snapshot-before-report-and-commit"
CONTRACT_ROOT_FIELDS = {
    "schema_version",
    "created_with",
    "record_status",
    "classification",
    "scope",
    "reference_order",
    "roots",
    "challenge_matrix",
    "proof_slices",
    "selection",
    "implementation_boundary",
    "review",
}


class AuditError(RuntimeError):
    """A safe, user-readable evidence failure."""


def load_render_review_adapter() -> Any:
    """Load the packaged schema-3 verifier without trusting bare image files.

    Direction Challenge uses the same path-bound rendered-review contract as
    Project Contrast. Loading the sibling module by path also works when this
    auditor itself is loaded through ``importlib`` by the initializer or tests.
    """

    module_name = "_design_dna_schema3_render_review_adapter"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    adapter_path = Path(__file__).with_name("project_contrast_audit.py")
    if not adapter_path.is_file() or adapter_path.is_symlink():
        raise AuditError("The packaged schema-3 rendered-review verifier is unavailable.")
    specification = importlib.util.spec_from_file_location(module_name, adapter_path)
    if specification is None or specification.loader is None:
        raise AuditError("The packaged schema-3 rendered-review verifier could not be loaded.")
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    try:
        specification.loader.exec_module(module)
    except (OSError, TypeError, ValueError, ImportError) as exc:
        sys.modules.pop(module_name, None)
        raise AuditError(f"The packaged schema-3 rendered-review verifier could not initialize: {exc}") from exc
    return module


def item(path: str, code: str, message: str) -> dict[str, str]:
    return {"path": path, "code": code, "message": message}


def finding(code: str, message: str, *, blocking: bool = False) -> dict[str, object]:
    return {"code": code, "message": message, "blocking": blocking}


def add_gap(gaps: list[dict[str, str]], code: str, message: str) -> None:
    gaps.append({"code": code, "message": message})


def text_ok(
    value: object,
    *,
    minimum: int = 1,
    maximum: int = MAX_TEXT_LENGTH,
) -> bool:
    return isinstance(value, str) and minimum <= len(value.strip()) <= maximum


def unresolved_template_markers(payload: object, path: str = "$") -> list[dict[str, str]]:
    """Reject explicit unresolved template syntax at every lifecycle stage."""

    errors: list[dict[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            errors.extend(unresolved_template_markers(value, f"{path}.{key}"))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            errors.extend(unresolved_template_markers(value, f"{path}[{index}]"))
    elif isinstance(payload, str) and any(marker.search(payload) for marker in UNRESOLVED_TEMPLATE_MARKERS):
        errors.append(item(
            path,
            "unresolved-template-marker",
            "Replace explicit template-marker syntax before structural or readiness review.",
        ))
    return errors


def exact_object(
    errors: list[dict[str, str]],
    value: object,
    path: str,
    fields: set[str],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(item(path, "invalid-object", "Expected an object."))
        return None
    actual = set(value)
    missing = sorted(fields - actual)
    extra = sorted(actual - fields)
    if missing:
        errors.append(item(path, "missing-properties", "Missing properties: " + ", ".join(missing) + "."))
    if extra:
        errors.append(item(path, "invalid-properties", "Unsupported properties: " + ", ".join(extra) + "."))
    return value


def valid_id(errors: list[dict[str, str]], value: object, path: str) -> bool:
    if not isinstance(value, str) or ID_PATTERN.fullmatch(value) is None:
        errors.append(item(path, "invalid-id", "Use a lowercase project-safe identifier."))
        return False
    return True


def valid_draftable_id(errors: list[dict[str, str]], value: object, path: str) -> bool:
    if value is None:
        return True
    return valid_id(errors, value, path)


def valid_draftable_text(errors: list[dict[str, str]], value: object, path: str) -> bool:
    if value is None:
        return True
    if not text_ok(value):
        errors.append(item(path, "invalid-text", "Expected nonempty project language or null while draft."))
        return False
    return True


def valid_unique_ids(
    errors: list[dict[str, str]], value: object, path: str,
) -> list[str]:
    if not isinstance(value, list):
        errors.append(item(path, "invalid-list", "Expected a list."))
        return []
    valid: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(value):
        entry_path = f"{path}[{index}]"
        if valid_id(errors, entry, entry_path) and isinstance(entry, str):
            if entry in seen:
                errors.append(item(entry_path, "duplicate-id", "IDs must be unique."))
            else:
                seen.add(entry)
                valid.append(entry)
    return valid


def valid_file_ref(
    errors: list[dict[str, str]], value: object, path: str,
) -> dict[str, Any] | None:
    data = exact_object(errors, value, path, {"path", "sha256"})
    if data is None:
        return None
    raw_path = data.get("path")
    if (
        not isinstance(raw_path, str)
        or not raw_path.strip()
        or len(raw_path) > MAX_FILE_REF_PATH_LENGTH
    ):
        errors.append(item(f"{path}.path", "invalid-path", "Expected a nonempty relative evidence path."))
    raw_hash = data.get("sha256")
    if not isinstance(raw_hash, str) or SHA256_PATTERN.fullmatch(raw_hash) is None:
        errors.append(item(f"{path}.sha256", "invalid-sha256", "Expected a lowercase SHA-256 digest."))
    return data


def valid_datetime(errors: list[dict[str, str]], value: object, path: str) -> bool:
    if parse_zoned_datetime(value) is not None:
        return True
    errors.append(item(path, "invalid-datetime", "Expected an ISO date-time with timezone."))
    return False


def parse_zoned_datetime(value: object) -> datetime | None:
    """Return a timezone-aware record timestamp without trusting local time."""

    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def runtime_schema_errors() -> list[dict[str, str]]:
    """Detect an accidental schema/runtime mismatch without a third-party validator."""

    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "direction-challenge.schema.json"
    try:
        raw = schema_path.read_bytes()
        if len(raw) > MAX_CONTRACT_BYTES:
            return [item("$schema", "runtime-schema-drift", "The packaged Direction Challenge schema is unexpectedly large.")]
        schema = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [item("$schema", "runtime-schema-drift", f"The packaged Direction Challenge schema cannot be read: {exc}")]
    if not isinstance(schema, dict):
        return [item("$schema", "runtime-schema-drift", "The packaged Direction Challenge schema root must be an object.")]
    errors: list[dict[str, str]] = []
    if set(schema.get("required", [])) != CONTRACT_ROOT_FIELDS:
        errors.append(item("$schema.required", "runtime-schema-drift", "The packaged schema root fields do not match the runtime contract validator."))
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        errors.append(item("$schema.properties", "runtime-schema-drift", "The packaged schema properties are missing."))
    elif set(properties) != CONTRACT_ROOT_FIELDS:
        errors.append(item("$schema.properties", "runtime-schema-drift", "The packaged schema properties do not match the runtime contract validator."))
    lifecycle = properties.get("record_status") if isinstance(properties, dict) else None
    if not isinstance(lifecycle, dict) or set(lifecycle.get("enum", [])) != LIFECYCLE:
        errors.append(item("$schema.properties.record_status", "runtime-schema-drift", "The packaged schema lifecycle does not match the runtime validator."))
    expected_root_limits = {
        "roots": MAX_ROOTS,
        "challenge_matrix": MAX_CHALLENGE_MATRIX_ENTRIES,
        "proof_slices": MAX_PROOF_SLICES,
    }
    if isinstance(properties, dict):
        for field, expected_maximum in expected_root_limits.items():
            definition = properties.get(field)
            if (
                not isinstance(definition, dict)
                or definition.get("maxItems") != expected_maximum
            ):
                errors.append(
                    item(
                        f"$schema.properties.{field}.maxItems",
                        "runtime-schema-drift",
                        f"The packaged schema {field} limit does not match the runtime validator.",
                    )
                )
        created_with = properties.get("created_with")
        if (
            not isinstance(created_with, dict)
            or created_with.get("minLength") != 1
            or created_with.get("maxLength") != MAX_CREATED_WITH_LENGTH
            or created_with.get("pattern") != ".*\\S.*"
        ):
            errors.append(
                item(
                    "$schema.properties.created_with",
                    "runtime-schema-drift",
                    "The packaged schema created_with length does not match the runtime validator.",
                )
            )
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        errors.append(item("$schema.$defs", "runtime-schema-drift", "The packaged schema definitions are missing."))
        return errors

    def definition_limits_match(
        definition_name: str,
        property_name: str,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> bool:
        definition = definitions.get(definition_name)
        definition_properties = definition.get("properties") if isinstance(definition, dict) else None
        target = definition_properties.get(property_name) if isinstance(definition_properties, dict) else None
        if not isinstance(target, dict):
            return False
        return (
            (minimum is None or target.get("minItems", target.get("minimum")) == minimum)
            and (maximum is None or target.get("maxItems", target.get("maximum")) == maximum)
        )

    for definition_name, property_name, maximum in (
        ("referenceOrder", "events", MAX_REFERENCE_EVENTS),
        ("matrixEntry", "incompatibilities", MAX_MATRIX_INCOMPATIBILITIES),
    ):
        minimum = MIN_MATRIX_INCOMPATIBILITIES if definition_name == "matrixEntry" else None
        if not definition_limits_match(
            definition_name,
            property_name,
            minimum=minimum,
            maximum=maximum,
        ):
            errors.append(
                item(
                    f"$schema.$defs.{definition_name}.properties.{property_name}",
                    "runtime-schema-drift",
                    f"The packaged schema {definition_name}.{property_name} limits do not match the runtime validator.",
                )
            )
    if not definition_limits_match(
        "referenceEvent",
        "sequence",
        minimum=MIN_SEQUENCE,
        maximum=MAX_SEQUENCE,
    ):
        errors.append(
            item(
                "$schema.$defs.referenceEvent.properties.sequence",
                "runtime-schema-drift",
                "The packaged schema reference-event sequence limit does not match the runtime validator.",
            )
        )
    nonempty = definitions.get("nonEmptyString")
    if (
        not isinstance(nonempty, dict)
        or nonempty.get("minLength") != 1
        or nonempty.get("maxLength") != MAX_TEXT_LENGTH
        or nonempty.get("pattern") != ".*\\S.*"
    ):
        errors.append(
            item(
                "$schema.$defs.nonEmptyString",
                "runtime-schema-drift",
        "The packaged schema text length limits do not match the runtime validator.",
            )
        )
    file_ref = definitions.get("fileRef")
    file_ref_properties = file_ref.get("properties") if isinstance(file_ref, dict) else None
    file_path = (
        file_ref_properties.get("path")
        if isinstance(file_ref_properties, dict)
        else None
    )
    if (
        not isinstance(file_path, dict)
        or file_path.get("minLength") != 1
        or file_path.get("maxLength") != MAX_FILE_REF_PATH_LENGTH
    ):
        errors.append(
            item(
                "$schema.$defs.fileRef.properties.path",
                "runtime-schema-drift",
                "The packaged schema file-reference path limit does not match the runtime validator.",
            )
        )
    proof_slice = definitions.get("proofSlice")
    expected_proof_fields = {
        "id", "root_id", "build_id", "purpose", "render_review",
        "source_snapshot_manifest_sha256", "route", "wide_capture_id",
        "narrow_capture_id",
    }
    if (
        not isinstance(proof_slice, dict)
        or set(proof_slice.get("required", [])) != expected_proof_fields
    ):
        errors.append(
            item(
                "$schema.$defs.proofSlice",
                "runtime-schema-drift",
                "The packaged schema proof slice must bind a schema-3 rendered-review report, local source snapshot, route, and exact wide/narrow capture IDs.",
            )
        )
    render_reference = definitions.get("renderReviewReference")
    if (
        not isinstance(render_reference, dict)
        or set(render_reference.get("required", [])) != {"file"}
    ):
        errors.append(
            item(
                "$schema.$defs.renderReviewReference",
                "runtime-schema-drift",
                "The packaged schema must define hash-bound schema-3 rendered-review references.",
            )
        )
    selection = definitions.get("selection")
    expected_selection_required_fields = {
        "chosen_root_id", "rejected_root_id", "selection_reason",
        "rejection_reason",
    }
    expected_selection_properties = {
        "chosen_root_id", "rejected_root_id", "selection_reason",
        "rejection_reason", "rationale_recorded_at",
    }
    if (
        not isinstance(selection, dict)
        or set(selection.get("required", [])) != expected_selection_required_fields
        or set(selection.get("properties", [])) != expected_selection_properties
    ):
        errors.append(
            item(
                "$schema.$defs.selection",
                "runtime-schema-drift",
                "The packaged schema selection must declare when its selected and rejected rationale was recorded.",
            )
        )
    unprimed_review = definitions.get("unprimedReview")
    expected_unprimed_review_required_fields = {
        "status", "reviewer_id", "relationship", "observed_at", "evidence",
        "reviewed_proof_slices", "first_observation", "limitations",
    }
    expected_unprimed_review_properties = {
        "status", "reviewer_id", "relationship", "exposure", "observed_at",
        "frozen_at", "evidence", "reviewed_proof_slices",
        "first_observation", "limitations",
    }
    if (
        not isinstance(unprimed_review, dict)
        or set(unprimed_review.get("required", [])) != expected_unprimed_review_required_fields
        or set(unprimed_review.get("properties", [])) != expected_unprimed_review_properties
    ):
        errors.append(
            item(
                "$schema.$defs.unprimedReview",
                "runtime-schema-drift",
                "The packaged schema unprimed review must bind its declared exposure, observed time, freeze time, and proof-slice coverage.",
            )
        )
    return errors


def validate_scope(errors: list[dict[str, str]], value: object) -> dict[str, Any] | None:
    scope = exact_object(errors, value, "$.scope", {"project_id", "surface_scope", "trigger", "activation_basis"})
    if scope is None:
        return None
    valid_draftable_id(errors, scope.get("project_id"), "$.scope.project_id")
    surfaces = scope.get("surface_scope")
    if not isinstance(surfaces, list) or not all(text_ok(entry) for entry in surfaces) or len(surfaces) != len(set(surfaces)):
        errors.append(item("$.scope.surface_scope", "invalid-surface-scope", "surface_scope must be a unique list of nonempty project surfaces."))
    valid_unique_ids(errors, scope.get("trigger"), "$.scope.trigger")
    valid_draftable_text(errors, scope.get("activation_basis"), "$.scope.activation_basis")
    return scope


def validate_reference_order(errors: list[dict[str, str]], value: object) -> list[dict[str, Any]]:
    record = exact_object(errors, value, "$.reference_order", {"events"})
    if record is None:
        return []
    events = record.get("events")
    if not isinstance(events, list):
        errors.append(item("$.reference_order.events", "invalid-list", "events must be a list."))
        return []
    if len(events) > MAX_REFERENCE_EVENTS:
        errors.append(
            item(
                "$.reference_order.events",
                "too-many-reference-events",
                f"reference_order.events may contain at most {MAX_REFERENCE_EVENTS} events.",
            )
        )
    output: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(events):
        path = f"$.reference_order.events[{index}]"
        event = exact_object(errors, raw, path, {"id", "sequence", "kind", "source", "root_ids", "note"})
        if event is None:
            continue
        raw_id = event.get("id")
        if valid_id(errors, raw_id, f"{path}.id") and isinstance(raw_id, str):
            if raw_id in seen_ids:
                errors.append(item(f"{path}.id", "duplicate-id", "Reference event IDs must be unique."))
            seen_ids.add(raw_id)
        sequence = event.get("sequence")
        if (
            not isinstance(sequence, int)
            or isinstance(sequence, bool)
            or not MIN_SEQUENCE <= sequence <= MAX_SEQUENCE
        ):
            errors.append(item(f"{path}.sequence", "invalid-sequence", "sequence must be a positive integer."))
        kind = event.get("kind")
        if kind not in EVENT_KINDS:
            errors.append(item(f"{path}.kind", "invalid-reference-kind", "Unsupported reference-order event kind."))
        if not text_ok(event.get("source")):
            errors.append(item(f"{path}.source", "invalid-text", "source must identify the material or action."))
        valid_unique_ids(errors, event.get("root_ids"), f"{path}.root_ids")
        if not text_ok(event.get("note")):
            errors.append(item(f"{path}.note", "invalid-text", "note must record the relevant order boundary."))
        output.append(event)
    return output


def validate_roots(errors: list[dict[str, str]], value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        errors.append(item("$.roots", "invalid-list", "roots must be a list."))
        return []
    if len(value) > MAX_ROOTS:
        errors.append(
            item(
                "$.roots",
                "too-many-roots",
                f"roots may contain at most {MAX_ROOTS} brief-native concept roots.",
            )
        )
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    fields = {"id", "brief_anchor", *ROOT_FIELDS, "surface_consequence"}
    for index, raw in enumerate(value):
        path = f"$.roots[{index}]"
        root = exact_object(errors, raw, path, fields)
        if root is None:
            continue
        root_id = root.get("id")
        if valid_id(errors, root_id, f"{path}.id") and isinstance(root_id, str):
            if root_id in seen:
                errors.append(item(f"{path}.id", "duplicate-id", "Root IDs must be unique."))
            seen.add(root_id)
        for field in ("brief_anchor", *ROOT_FIELDS, "surface_consequence"):
            if not text_ok(root.get(field)):
                errors.append(item(f"{path}.{field}", "invalid-text", "Root fields must use nonempty brief-native project language."))
        output.append(root)
    return output


def validate_matrix(errors: list[dict[str, str]], value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        errors.append(item("$.challenge_matrix", "invalid-list", "challenge_matrix must be a list."))
        return []
    if len(value) > MAX_CHALLENGE_MATRIX_ENTRIES:
        errors.append(
            item(
                "$.challenge_matrix",
                "too-many-challenge-matrix-entries",
                f"challenge_matrix may contain at most {MAX_CHALLENGE_MATRIX_ENTRIES} root-pair entries.",
            )
        )
    output: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        path = f"$.challenge_matrix[{index}]"
        entry = exact_object(errors, raw, path, {"root_a", "root_b", "incompatibilities"})
        if entry is None:
            continue
        valid_id(errors, entry.get("root_a"), f"{path}.root_a")
        valid_id(errors, entry.get("root_b"), f"{path}.root_b")
        incompatibilities = entry.get("incompatibilities")
        if not isinstance(incompatibilities, list):
            errors.append(item(f"{path}.incompatibilities", "invalid-list", "incompatibilities must be a list."))
            output.append(entry)
            continue
        if not (
            MIN_MATRIX_INCOMPATIBILITIES
            <= len(incompatibilities)
            <= MAX_MATRIX_INCOMPATIBILITIES
        ):
            errors.append(
                item(
                    f"{path}.incompatibilities",
                    "invalid-matrix-incompatibility-count",
                    (
                        "Each matrix pair must contain "
                        f"{MIN_MATRIX_INCOMPATIBILITIES} through "
                        f"{MAX_MATRIX_INCOMPATIBILITIES} incompatibility rows."
                    ),
                )
            )
        seen_fields: set[str] = set()
        for row_index, raw_row in enumerate(incompatibilities):
            row_path = f"{path}.incompatibilities[{row_index}]"
            row = exact_object(errors, raw_row, row_path, {"field", "root_a_position", "root_b_position", "why_not_combined"})
            if row is None:
                continue
            field = row.get("field")
            if field not in ROOT_FIELDS_SET:
                errors.append(item(f"{row_path}.field", "invalid-root-field", "Only encounter and content-operation root fields can prove incompatibility."))
            elif field in seen_fields:
                errors.append(item(f"{row_path}.field", "duplicate-root-field", "Each matrix pair must name each structural field once."))
            else:
                seen_fields.add(field)
            for text_field in ("root_a_position", "root_b_position", "why_not_combined"):
                if not text_ok(row.get(text_field)):
                    errors.append(item(f"{row_path}.{text_field}", "invalid-text", "Matrix rows require nonempty project-language positions and rationale."))
        output.append(entry)
    return output


def valid_project_route(errors: list[dict[str, str]], value: object, path: str) -> bool:
    if not isinstance(value, str) or not value.startswith("/"):
        errors.append(item(path, "invalid-route", "A proof slice must name a normalized direct project route beginning with '/'."))
        return False
    if any(token in value for token in ("?", "#", "\\", "\x00")):
        errors.append(item(path, "invalid-route", "Proof routes may not use query strings, fragments, backslashes, or NUL bytes."))
        return False
    if "//" in value or "/./" in value or "/../" in value or value.endswith("/.."):
        errors.append(item(path, "invalid-route", "Proof routes must be normalized project paths."))
        return False
    if any(not segment or segment in {".", ".."} for segment in value.split("/")[1:-1]):
        errors.append(item(path, "invalid-route", "Proof routes must not contain empty or traversal segments."))
        return False
    return True


def validate_render_review_reference(
    errors: list[dict[str, str]], value: object, path: str,
) -> dict[str, Any] | None:
    reference = exact_object(errors, value, path, {"file"})
    if reference is None:
        return None
    valid_file_ref(errors, reference.get("file"), f"{path}.file")
    return reference


def validate_proof_slices(errors: list[dict[str, str]], value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        errors.append(item("$.proof_slices", "invalid-list", "proof_slices must be a list."))
        return []
    if len(value) > MAX_PROOF_SLICES:
        errors.append(
            item(
                "$.proof_slices",
                "too-many-proof-slices",
                f"proof_slices may contain at most {MAX_PROOF_SLICES} rendered proof slices.",
            )
        )
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        path = f"$.proof_slices[{index}]"
        proof = exact_object(
            errors,
            raw,
            path,
            {
                "id", "root_id", "build_id", "purpose", "render_review",
                "source_snapshot_manifest_sha256", "route", "wide_capture_id",
                "narrow_capture_id",
            },
        )
        if proof is None:
            continue
        proof_id = proof.get("id")
        if valid_id(errors, proof_id, f"{path}.id") and isinstance(proof_id, str):
            if proof_id in seen:
                errors.append(item(f"{path}.id", "duplicate-id", "Proof-slice IDs must be unique."))
            seen.add(proof_id)
        valid_id(errors, proof.get("root_id"), f"{path}.root_id")
        valid_id(errors, proof.get("build_id"), f"{path}.build_id")
        if not text_ok(proof.get("purpose")):
            errors.append(item(f"{path}.purpose", "invalid-text", "proof purpose must state what uncertainty the slice settles."))
        validate_render_review_reference(errors, proof.get("render_review"), f"{path}.render_review")
        snapshot_hash = proof.get("source_snapshot_manifest_sha256")
        if not isinstance(snapshot_hash, str) or SHA256_PATTERN.fullmatch(snapshot_hash) is None:
            errors.append(item(f"{path}.source_snapshot_manifest_sha256", "invalid-sha256", "Proof slices must bind the rendered review's frozen source manifest SHA-256."))
        valid_project_route(errors, proof.get("route"), f"{path}.route")
        for capture_field in ("wide_capture_id", "narrow_capture_id"):
            capture_id = proof.get(capture_field)
            if not isinstance(capture_id, str) or RENDER_CAPTURE_ID_PATTERN.fullmatch(capture_id) is None:
                errors.append(item(f"{path}.{capture_field}", "invalid-render-capture-id", "Proof slices must name a schema-3 rendered-review capture ID."))
        if proof.get("wide_capture_id") == proof.get("narrow_capture_id"):
            errors.append(item(path, "proof-captures-not-distinct", "Wide and narrow proof references must name different schema-3 captures."))
        output.append(proof)
    return output


def validate_selection(
    errors: list[dict[str, str]],
    value: object,
    *,
    allow_legacy_draft: bool,
) -> dict[str, Any] | None:
    fields = {
        "chosen_root_id", "rejected_root_id", "selection_reason",
        "rejection_reason", "rationale_recorded_at",
    }
    if (
        allow_legacy_draft
        and isinstance(value, dict)
        and "rationale_recorded_at" not in value
    ):
        fields.remove("rationale_recorded_at")
    selection = exact_object(
        errors,
        value,
        "$.selection",
        fields,
    )
    if selection is None:
        return None
    valid_draftable_id(errors, selection.get("chosen_root_id"), "$.selection.chosen_root_id")
    valid_draftable_id(errors, selection.get("rejected_root_id"), "$.selection.rejected_root_id")
    valid_draftable_text(errors, selection.get("selection_reason"), "$.selection.selection_reason")
    valid_draftable_text(errors, selection.get("rejection_reason"), "$.selection.rejection_reason")
    rationale_recorded_at = selection.get("rationale_recorded_at")
    if rationale_recorded_at is not None:
        valid_datetime(errors, rationale_recorded_at, "$.selection.rationale_recorded_at")
    return selection


def validate_boundary(errors: list[dict[str, str]], value: object) -> dict[str, Any] | None:
    boundary = exact_object(errors, value, "$.implementation_boundary", {"status", "evidence"})
    if boundary is None:
        return None
    if boundary.get("status") not in {"roots-only", "proof-slices", "broad-implementation"}:
        errors.append(item("$.implementation_boundary.status", "invalid-boundary-status", "Use roots-only, proof-slices, or broad-implementation."))
    valid_draftable_text(errors, boundary.get("evidence"), "$.implementation_boundary.evidence")
    return boundary


def validate_review(
    errors: list[dict[str, str]],
    value: object,
    *,
    allow_legacy_draft: bool,
) -> dict[str, Any] | None:
    review = exact_object(errors, value, "$.review", {"unprimed"})
    if review is None:
        return None
    unprimed_fields = {
        "status", "reviewer_id", "relationship", "exposure", "observed_at",
        "frozen_at", "evidence", "reviewed_proof_slices", "first_observation",
        "limitations",
    }
    if (
        allow_legacy_draft
        and isinstance(review.get("unprimed"), dict)
        and "exposure" not in review["unprimed"]
        and "frozen_at" not in review["unprimed"]
    ):
        unprimed_fields.difference_update({"exposure", "frozen_at"})
    unprimed = exact_object(
        errors,
        review.get("unprimed"),
        "$.review.unprimed",
        unprimed_fields,
    )
    if unprimed is None:
        return review
    if unprimed.get("status") not in {"draft", "complete"}:
        errors.append(item("$.review.unprimed.status", "invalid-review-status", "Use draft or complete."))
    reviewer = unprimed.get("reviewer_id")
    if reviewer is not None and not text_ok(reviewer):
        errors.append(item("$.review.unprimed.reviewer_id", "invalid-text", "reviewer_id must identify an independent reviewer or be null while draft."))
    relationship = unprimed.get("relationship")
    if relationship is not None and relationship not in UNPRIMED_RELATIONSHIPS:
        errors.append(item("$.review.unprimed.relationship", "invalid-reviewer-relationship", "Review must state an independent relationship or remain null while draft."))
    exposure = unprimed.get("exposure")
    if exposure is not None and exposure != UNPRIMED_EXPOSURE:
        errors.append(item("$.review.unprimed.exposure", "invalid-unprimed-exposure", "Use unprimed-proof-slices-only or null while draft."))
    observed_at = unprimed.get("observed_at")
    if observed_at is not None:
        valid_datetime(errors, observed_at, "$.review.unprimed.observed_at")
    frozen_at = unprimed.get("frozen_at")
    if frozen_at is not None:
        valid_datetime(errors, frozen_at, "$.review.unprimed.frozen_at")
    evidence = unprimed.get("evidence")
    if evidence is not None:
        valid_file_ref(errors, evidence, "$.review.unprimed.evidence")
    valid_unique_ids(errors, unprimed.get("reviewed_proof_slices"), "$.review.unprimed.reviewed_proof_slices")
    valid_draftable_text(errors, unprimed.get("first_observation"), "$.review.unprimed.first_observation")
    valid_draftable_text(errors, unprimed.get("limitations"), "$.review.unprimed.limitations")
    return review


def selected_root_map(roots: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        root["id"]: root
        for root in roots
        if isinstance(root.get("id"), str) and ID_PATTERN.fullmatch(root["id"])
    }


def lifecycle_errors(
    payload: dict[str, Any],
    errors: list[dict[str, str]],
    *,
    scope: dict[str, Any] | None,
    events: list[dict[str, Any]],
    roots: list[dict[str, Any]],
    matrix: list[dict[str, Any]],
    proofs: list[dict[str, Any]],
    selection: dict[str, Any] | None,
    boundary: dict[str, Any] | None,
    review: dict[str, Any] | None,
) -> None:
    status = payload.get("record_status")
    if status not in LIFECYCLE_ORDER:
        return
    stage = LIFECYCLE_ORDER[status]
    if stage == LIFECYCLE_ORDER["draft"]:
        return
    if scope is None:
        return
    if not isinstance(scope.get("project_id"), str) or ID_PATTERN.fullmatch(scope["project_id"]) is None:
        errors.append(item("$.scope.project_id", "lifecycle-project-id-missing", f"{status} requires a project-safe identifier."))
    surfaces = scope.get("surface_scope")
    if not isinstance(surfaces, list) or not surfaces:
        errors.append(item("$.scope.surface_scope", "lifecycle-scope-missing", f"{status} requires a relevant surface scope."))
    if not text_ok(scope.get("activation_basis")):
        errors.append(item("$.scope.activation_basis", "lifecycle-activation-missing", f"{status} requires the explicit owner or project basis for this challenge."))
    if len(roots) < 3:
        errors.append(item("$.roots", "lifecycle-roots-missing", "roots-ready requires at least three brief-native concept roots."))
        return
    roots_by_id = selected_root_map(roots)
    if len(roots_by_id) < 3:
        errors.append(item("$.roots", "lifecycle-roots-invalid", "roots-ready requires three valid, distinct root identifiers."))
        return
    validate_reference_order_lifecycle(errors, events, set(roots_by_id))
    validate_matrix_lifecycle(errors, matrix, roots_by_id)
    for root_a, root_b in pairwise_roots(roots_by_id):
        if all(normalized(root_a[field]) == normalized(root_b[field]) for field in ROOT_FIELDS):
            errors.append(item("$.roots", "cosmetic-only-root-difference", "Two roots change only surface consequence or labels; their organizing encounter and body operation remain the same."))
    if boundary is not None and boundary.get("status") == "broad-implementation" and stage < LIFECYCLE_ORDER["proof-ready"]:
        errors.append(item("$.implementation_boundary.status", "broad-implementation-before-proof", "Broad implementation cannot begin until at least two rendered proof slices are hash-bound."))
    if stage < LIFECYCLE_ORDER["proof-ready"]:
        return
    validate_proof_lifecycle(errors, proofs, roots_by_id, selection)
    if boundary is not None and boundary.get("status") == "roots-only":
        errors.append(item("$.implementation_boundary.status", "lifecycle-proof-boundary-unresolved", "proof-ready requires a truthful proof-slices or broad-implementation boundary."))
    if stage < LIFECYCLE_ORDER["reviewed"]:
        return
    validate_review_lifecycle(errors, proofs, selection, review)


def normalized(value: object) -> str:
    return " ".join(str(value).split()).casefold()


def pairwise_roots(roots_by_id: dict[str, dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    ids = sorted(roots_by_id)
    return [(roots_by_id[left], roots_by_id[right]) for index, left in enumerate(ids) for right in ids[index + 1:]]


def pair_key(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def validate_reference_order_lifecycle(errors: list[dict[str, str]], events: list[dict[str, Any]], root_ids: set[str]) -> None:
    if not events:
        errors.append(item("$.reference_order.events", "lifecycle-reference-order-missing", "roots-ready requires an exact root and reference order."))
        return
    sequences = [event.get("sequence") for event in events]
    if any(not isinstance(value, int) for value in sequences) or sorted(sequences) != list(range(1, len(events) + 1)):
        errors.append(item("$.reference_order.events", "reference-order-not-exact", "Reference-event sequence values must be the exact contiguous order beginning at 1."))
        return
    ordered = sorted(events, key=lambda event: event["sequence"])
    seen_roots: set[str] = set()
    roots_completed = False
    for event in ordered:
        kind = event.get("kind")
        event_roots = set(event.get("root_ids", [])) if isinstance(event.get("root_ids"), list) else set()
        if kind == "root-recorded":
            unknown = event_roots - root_ids
            if unknown:
                errors.append(item("$.reference_order.events", "reference-order-unknown-root", "A root-recorded event names a root not in roots."))
            seen_roots.update(event_roots & root_ids)
            roots_completed = seen_roots == root_ids
            continue
        if not roots_completed and kind not in {"supplied-brand-material", "supplied-source-material"}:
            errors.append(item("$.reference_order.events", "reference-before-roots", "Only supplied brand or source material may precede recording every root; polished examples and other reference material must follow roots."))
    if seen_roots != root_ids:
        errors.append(item("$.reference_order.events", "reference-order-roots-unbound", "Every root must appear in a root-recorded event."))


def validate_matrix_lifecycle(
    errors: list[dict[str, str]], matrix: list[dict[str, Any]], roots_by_id: dict[str, dict[str, Any]],
) -> None:
    expected = {pair_key(left, right) for left, right in pairwise_roots(roots_by_id) for left, right in [(left["id"], right["id"])]}
    observed: set[tuple[str, str]] = set()
    for index, entry in enumerate(matrix):
        root_a = entry.get("root_a")
        root_b = entry.get("root_b")
        path = f"$.challenge_matrix[{index}]"
        if root_a not in roots_by_id or root_b not in roots_by_id or root_a == root_b:
            errors.append(item(path, "matrix-root-mismatch", "Each matrix row must compare two distinct declared roots."))
            continue
        key = pair_key(root_a, root_b)
        if key in observed:
            errors.append(item(path, "duplicate-matrix-pair", "Each root pair may appear once in the exact challenge matrix."))
        observed.add(key)
        incompatibilities = entry.get("incompatibilities")
        if (
            not isinstance(incompatibilities, list)
            or len(incompatibilities) < MIN_MATRIX_INCOMPATIBILITIES
        ):
            errors.append(
                item(
                    f"{path}.incompatibilities",
                    "matrix-incompatibilities-missing",
                    "Every root pair needs at least "
                    f"{MIN_MATRIX_INCOMPATIBILITIES} incompatible encounter or "
                    "content-operation decisions.",
                )
            )
            continue
        fields: set[str] = set()
        for row_index, row in enumerate(incompatibilities):
            if not isinstance(row, dict):
                continue
            field = row.get("field")
            row_path = f"{path}.incompatibilities[{row_index}]"
            if field not in ROOT_FIELDS_SET:
                continue
            fields.add(field)
            if normalized(row.get("root_a_position")) != normalized(roots_by_id[root_a].get(field)):
                errors.append(item(f"{row_path}.root_a_position", "matrix-position-mismatch", "root_a_position must exactly bind to the declared root field."))
            if normalized(row.get("root_b_position")) != normalized(roots_by_id[root_b].get(field)):
                errors.append(item(f"{row_path}.root_b_position", "matrix-position-mismatch", "root_b_position must exactly bind to the declared root field."))
            if normalized(row.get("root_a_position")) == normalized(row.get("root_b_position")):
                errors.append(item(row_path, "cosmetic-only-matrix-row", "A matrix row must name incompatible root positions, not a shared or cosmetic-only decision."))
        if len(fields) < MIN_MATRIX_INCOMPATIBILITIES:
            errors.append(
                item(
                    f"{path}.incompatibilities",
                    "matrix-structural-difference-missing",
                    "Each pair needs at least "
                    f"{MIN_MATRIX_INCOMPATIBILITIES} distinct encounter or "
                    "content-operation fields, not cosmetic substitutions.",
                )
            )
    if observed != expected:
        errors.append(item("$.challenge_matrix", "challenge-matrix-incomplete", "The matrix must contain exactly one evidence row for every unordered root pair."))


def validate_proof_lifecycle(
    errors: list[dict[str, str]], proofs: list[dict[str, Any]], roots_by_id: dict[str, dict[str, Any]], selection: dict[str, Any] | None,
) -> None:
    if len(proofs) < 2:
        errors.append(item("$.proof_slices", "lifecycle-proof-slices-missing", "proof-ready requires at least two hash-bound rendered proof slices."))
        return
    proof_ids: set[str] = set()
    proof_roots: set[str] = set()
    for index, proof in enumerate(proofs):
        path = f"$.proof_slices[{index}]"
        proof_id = proof.get("id")
        root_id = proof.get("root_id")
        if not isinstance(proof_id, str) or proof_id in proof_ids:
            errors.append(item(f"{path}.id", "proof-id-invalid", "Each proof slice needs a unique valid ID."))
        else:
            proof_ids.add(proof_id)
        if root_id not in roots_by_id:
            errors.append(item(f"{path}.root_id", "proof-root-missing", "Every proof slice must belong to a declared root."))
        else:
            proof_roots.add(root_id)
        wide_capture_id = proof.get("wide_capture_id")
        narrow_capture_id = proof.get("narrow_capture_id")
        if wide_capture_id == narrow_capture_id:
            errors.append(item(path, "proof-captures-not-distinct", "A proof slice must bind different schema-3 wide and narrow capture IDs."))
    if len(proof_roots) < 2:
        errors.append(item("$.proof_slices", "proof-root-range-missing", "At least two different roots need rendered proof; alternate roots cannot remain text-only."))
    if selection is None:
        return
    chosen = selection.get("chosen_root_id")
    rejected = selection.get("rejected_root_id")
    if chosen not in roots_by_id or rejected not in roots_by_id or chosen == rejected:
        errors.append(item("$.selection", "selection-root-invalid", "proof-ready requires distinct chosen and explicitly rejected declared roots."))
    else:
        if chosen not in proof_roots or rejected not in proof_roots:
            errors.append(item("$.selection", "selection-proof-missing", "The chosen root and explicit rejected root must both have rendered proof slices."))
    for field in ("selection_reason", "rejection_reason"):
        if not text_ok(selection.get(field)):
            errors.append(item(f"$.selection.{field}", "selection-rationale-missing", "proof-ready requires an explicit selection and rejection rationale."))
    if parse_zoned_datetime(selection.get("rationale_recorded_at")) is None:
        errors.append(item("$.selection.rationale_recorded_at", "selection-rationale-time-missing", "proof-ready requires a zoned time for the selected and rejected rationale record."))


def validate_review_lifecycle(
    errors: list[dict[str, str]],
    proofs: list[dict[str, Any]],
    selection: dict[str, Any] | None,
    review: dict[str, Any] | None,
) -> None:
    unprimed = review.get("unprimed") if isinstance(review, dict) else None
    if not isinstance(unprimed, dict):
        errors.append(item("$.review.unprimed", "unprimed-review-missing", "reviewed requires an independent unprimed review record."))
        return
    if unprimed.get("status") != "complete":
        errors.append(item("$.review.unprimed.status", "unprimed-review-incomplete", "reviewed requires a completed independent unprimed review."))
    if not text_ok(unprimed.get("reviewer_id")) or unprimed.get("relationship") not in UNPRIMED_RELATIONSHIPS:
        errors.append(item("$.review.unprimed", "unprimed-reviewer-independence-missing", "reviewed requires an identified independent reviewer relationship."))
    observed_at = parse_zoned_datetime(unprimed.get("observed_at"))
    frozen_at = parse_zoned_datetime(unprimed.get("frozen_at"))
    if observed_at is None:
        errors.append(item("$.review.unprimed.observed_at", "unprimed-review-time-missing", "reviewed requires an observed-at time with timezone."))
    if frozen_at is None:
        errors.append(item("$.review.unprimed.frozen_at", "unprimed-review-freeze-time-missing", "reviewed requires a review freeze time with timezone alongside its hash-bound evidence artifact."))
    if observed_at is not None and frozen_at is not None and frozen_at < observed_at:
        errors.append(item("$.review.unprimed.frozen_at", "unprimed-review-freeze-before-observation", "The unprimed review must freeze at or after its recorded observation."))
    if unprimed.get("exposure") != UNPRIMED_EXPOSURE:
        errors.append(item("$.review.unprimed.exposure", "unprimed-review-exposure-invalid", "reviewed requires the explicit unprimed-proof-slices-only exposure declaration; do not infer it from review prose."))
    if not isinstance(unprimed.get("evidence"), dict):
        errors.append(item("$.review.unprimed.evidence", "unprimed-review-evidence-missing", "reviewed requires a hash-bound unprimed review artifact."))
    proof_ids = {proof.get("id") for proof in proofs if isinstance(proof.get("id"), str)}
    reviewed_ids = set(unprimed.get("reviewed_proof_slices", [])) if isinstance(unprimed.get("reviewed_proof_slices"), list) else set()
    if reviewed_ids != proof_ids:
        errors.append(item("$.review.unprimed.reviewed_proof_slices", "unprimed-review-coverage-incomplete", "The unprimed review must cover every declared proof slice before selection claims are ready."))
    if not text_ok(unprimed.get("first_observation")):
        errors.append(item("$.review.unprimed.first_observation", "unprimed-first-observation-missing", "reviewed requires the independent reviewer’s first observation."))
    rationale_recorded_at = (
        parse_zoned_datetime(selection.get("rationale_recorded_at"))
        if isinstance(selection, dict)
        else None
    )
    if rationale_recorded_at is None:
        errors.append(item("$.selection.rationale_recorded_at", "unprimed-review-selection-order-unbound", "reviewed requires a zoned selection-rationale record time so the unprimed freeze can be ordered against it."))
    elif frozen_at is not None and frozen_at >= rationale_recorded_at:
        errors.append(item("$.review.unprimed.frozen_at", "unprimed-review-freeze-after-selection-rationale", "Freeze the unprimed review before recording selected or rejected rationale; equal timestamps do not establish that order."))


def validate_contract_payload(payload: object) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    """Validate the portable planning record without reading project evidence."""

    errors = runtime_schema_errors()
    root = exact_object(errors, payload, "$", CONTRACT_ROOT_FIELDS)
    if root is None:
        return errors, None
    errors.extend(unresolved_template_markers(payload))
    if root.get("schema_version") != SCHEMA_VERSION:
        errors.append(item("$.schema_version", "unsupported-version", "schema_version must equal 1."))
    if not text_ok(root.get("created_with"), maximum=MAX_CREATED_WITH_LENGTH):
        errors.append(item("$.created_with", "invalid-created-with", "created_with must identify the packaged Design DNA version."))
    if root.get("record_status") not in LIFECYCLE:
        errors.append(item("$.record_status", "invalid-lifecycle", "Use draft, roots-ready, proof-ready, or reviewed."))
    if root.get("classification") not in {"internal", "confidential"}:
        errors.append(item("$.classification", "invalid-classification", "classification must be internal or confidential."))
    scope = validate_scope(errors, root.get("scope"))
    events = validate_reference_order(errors, root.get("reference_order"))
    roots = validate_roots(errors, root.get("roots"))
    matrix = validate_matrix(errors, root.get("challenge_matrix"))
    proofs = validate_proof_slices(errors, root.get("proof_slices"))
    allow_legacy_draft = root.get("record_status") == "draft"
    selection = validate_selection(
        errors,
        root.get("selection"),
        allow_legacy_draft=allow_legacy_draft,
    )
    boundary = validate_boundary(errors, root.get("implementation_boundary"))
    review = validate_review(
        errors,
        root.get("review"),
        allow_legacy_draft=allow_legacy_draft,
    )
    lifecycle_errors(
        root,
        errors,
        scope=scope,
        events=events,
        roots=roots,
        matrix=matrix,
        proofs=proofs,
        selection=selection,
        boundary=boundary,
        review=review,
    )
    return errors, root


def is_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(reparse and attributes & reparse)


def portable_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuditError(f"{label} needs a nonempty relative path.")
    normalized_path = value.replace("\\", "/")
    parsed = PurePosixPath(normalized_path)
    if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
        raise AuditError(f"{label} must be a safe relative path.")
    return parsed.as_posix()


def project_file(root: Path, relative: object, label: str) -> Path:
    safe = portable_path(relative, label)
    root = root.resolve(strict=True)
    candidate = root.joinpath(*PurePosixPath(safe).parts)
    current = root
    for part in PurePosixPath(safe).parts:
        current = current / part
        if is_reparse(current):
            raise AuditError(f"{label} may not traverse a symlink or reparse point.")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise AuditError(f"Unable to resolve {label}: {exc}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise AuditError(f"{label} escapes the project root.") from exc
    if not resolved.is_file():
        raise AuditError(f"{label} is not a regular file.")
    return resolved


def stable_read(path: Path, label: str, budget: list[int]) -> bytes:
    if is_reparse(path):
        raise AuditError(f"{label} is a symlink or reparse point.")
    try:
        before = path.stat()
    except OSError as exc:
        raise AuditError(f"Unable to inspect {label}: {exc}") from exc
    if not stat.S_ISREG(before.st_mode):
        raise AuditError(f"{label} is not a regular file.")
    if before.st_size > MAX_EVIDENCE_BYTES:
        raise AuditError(f"{label} exceeds the evidence-file size limit.")
    if budget[0] + before.st_size > MAX_TOTAL_EVIDENCE_BYTES:
        raise AuditError("Direction Challenge evidence exceeds the total evidence budget.")
    try:
        payload = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        raise AuditError(f"Unable to read {label}: {exc}") from exc
    if len(payload) != before.st_size or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise AuditError(f"{label} changed while it was being read.")
    budget[0] += len(payload)
    return payload


def verify_file_reference(root: Path, reference: object, label: str, budget: list[int]) -> tuple[Path, bytes]:
    if not isinstance(reference, dict):
        raise AuditError(f"{label} is missing a file reference.")
    path = project_file(root, reference.get("path"), label)
    payload = stable_read(path, label, budget)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != reference.get("sha256"):
        raise AuditError(f"{label} SHA-256 does not match its recorded evidence.")
    return path, payload


def source_manifest_digest(files: list[dict[str, Any]]) -> str:
    """Mirror the renderer's ordered JSON.stringify manifest hash."""

    canonical = [
        {"path": entry["path"], "bytes": entry["bytes"], "sha256": entry["sha256"]}
        for entry in files
    ]
    serialized = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_source_snapshot(
    render_report: dict[str, Any],
    expected_manifest_sha256: object,
    label: str,
) -> str:
    """Require an authentic local frozen-source boundary for a proof slice."""

    build = render_report.get("build")
    if not isinstance(build, dict) or build.get("target_kind") not in {"local-directory", "local-file"}:
        raise AuditError(f"{label} must be a local schema-3 render review with a frozen source snapshot.")
    snapshot = render_report.get("source_snapshot")
    if not isinstance(snapshot, dict) or set(snapshot) != {"policy", "root_kind", "entry_path", "drift_check", "manifest"}:
        raise AuditError(f"{label} has no complete frozen source snapshot.")
    if snapshot.get("policy") != SOURCE_SNAPSHOT_POLICY or snapshot.get("drift_check") != SOURCE_SNAPSHOT_DRIFT_CHECK:
        raise AuditError(f"{label} does not expose the renderer's frozen-source policy and drift check.")
    if snapshot.get("root_kind") not in SOURCE_SNAPSHOT_ROOT_KINDS:
        raise AuditError(f"{label} has an unsupported frozen-source root kind.")
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
        raise AuditError(f"{label} has an invalid frozen-source entry path.")
    manifest = snapshot.get("manifest")
    if not isinstance(manifest, dict) or set(manifest) != {
        "algorithm", "manifest_sha256", "file_count", "total_bytes", "files", "excluded_counts",
    }:
        raise AuditError(f"{label} has an incomplete frozen-source manifest.")
    if manifest.get("algorithm") != "sha256":
        raise AuditError(f"{label} must use the schema-3 SHA-256 source manifest.")
    manifest_digest = manifest.get("manifest_sha256")
    if not isinstance(manifest_digest, str) or SHA256_PATTERN.fullmatch(manifest_digest) is None:
        raise AuditError(f"{label} has an invalid frozen-source manifest digest.")
    if manifest_digest != expected_manifest_sha256:
        raise AuditError(f"{label} manifest digest does not match the proof slice's source_snapshot_manifest_sha256.")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise AuditError(f"{label} has no frozen source files.")
    file_paths: set[str] = set()
    total_bytes = 0
    normalized_files: list[dict[str, Any]] = []
    for index, entry in enumerate(files):
        if not isinstance(entry, dict) or set(entry) != {"path", "bytes", "sha256"}:
            raise AuditError(f"{label} source file {index} has an invalid manifest entry.")
        path = entry.get("path")
        byte_count = entry.get("bytes")
        digest = entry.get("sha256")
        parsed_path = PurePosixPath(path) if isinstance(path, str) else None
        if (
            not isinstance(path, str)
            or not path
            or path.startswith("/")
            or "\\" in path
            or "//" in path
            or parsed_path is None
            or parsed_path.as_posix() != path
            or any(part in {"", ".", ".."} for part in parsed_path.parts)
            or not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
            or not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
            or path in file_paths
        ):
            raise AuditError(f"{label} source file {index} is not a safe, unique SHA-256 manifest entry.")
        file_paths.add(path)
        total_bytes += byte_count
        normalized_files.append({"path": path, "bytes": byte_count, "sha256": digest})
    if entry_path not in file_paths:
        raise AuditError(f"{label} frozen-source entry path is absent from its manifest.")
    if manifest.get("file_count") != len(normalized_files) or manifest.get("total_bytes") != total_bytes:
        raise AuditError(f"{label} frozen-source manifest counts do not match its file entries.")
    if source_manifest_digest(normalized_files) != manifest_digest:
        raise AuditError(f"{label} frozen-source manifest digest does not match its ordered file entries.")
    excluded_counts = manifest.get("excluded_counts")
    if not isinstance(excluded_counts, dict) or set(excluded_counts) != {
        "hidden_or_source_only_path", "sensitive_or_source_config", "extension_not_public_allowlist",
    } or any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in excluded_counts.values()
    ):
        raise AuditError(f"{label} frozen-source exclusion counts are invalid.")
    return manifest_digest


def rendered_capture_path(render_adapter: Any, report_relative_path: object, screenshot_path: object, label: str) -> str:
    if not isinstance(report_relative_path, str) or not isinstance(screenshot_path, str):
        raise AuditError(f"{label} has no portable rendered screenshot path.")
    relative = (
        PurePosixPath(report_relative_path).parent / PurePosixPath(screenshot_path)
    ).as_posix()
    if relative.startswith("./"):
        relative = relative[2:]
    try:
        return render_adapter.portable_path(relative, f"{label}.screenshot.path")
    except Exception as exc:
        raise AuditError(f"{label} has an invalid rendered screenshot path: {exc}") from exc


def verify_proof_slice(
    root: Path,
    proof: dict[str, Any],
    render_adapter: Any,
    render_budget: Any,
    cache: dict[tuple[str, str], dict[str, Any]],
    seen_capture_bindings: set[tuple[str, str]],
    capture_hash_roots: dict[str, set[str]],
) -> list[dict[str, Any]]:
    """Resolve a Direction Challenge slice to exact schema-3 pixels and source."""

    proof_id = proof.get("id", "unknown")
    label = f"proof slice {proof_id}"
    render_reference = proof.get("render_review")
    if not isinstance(render_reference, dict):
        raise AuditError(f"{label} is missing a schema-3 rendered-review reference.")
    render_file = render_reference.get("file")
    if not isinstance(render_file, dict):
        raise AuditError(f"{label} is missing its rendered-review file reference.")
    reference_path = render_file.get("path")
    reference_sha = render_file.get("sha256")
    if not isinstance(reference_path, str) or not isinstance(reference_sha, str):
        raise AuditError(f"{label} has an invalid rendered-review file reference.")
    cache_key = (reference_path, reference_sha)
    if cache_key not in cache:
        try:
            cache[cache_key] = render_adapter.load_schema3_render_review(
                root,
                render_file,
                f"{label}.render_review.file",
                render_budget,
            )
        except Exception as exc:
            raise AuditError(f"{label} does not bind a valid path-bound schema-3 rendered-review package: {exc}") from exc
    result = cache[cache_key]
    report = result.get("report")
    if not isinstance(report, dict):
        raise AuditError(f"{label} cannot inspect its schema-3 rendered-review report.")
    if result.get("build_id") != proof.get("build_id"):
        raise AuditError(f"{label} build_id does not match the bound schema-3 rendered-review build.")
    manifest_digest = validate_source_snapshot(
        report,
        proof.get("source_snapshot_manifest_sha256"),
        f"{label}.render_review.source_snapshot",
    )
    captures_by_id = result.get("captures_by_id")
    if not isinstance(captures_by_id, dict):
        raise AuditError(f"{label} cannot inspect schema-3 rendered captures.")
    report_relative_path = result.get("report_relative_path")
    capture_records: list[dict[str, Any]] = []
    width_by_class: dict[str, int] = {}
    hashes: set[str] = set()
    root_id = proof.get("root_id")
    if not isinstance(root_id, str):
        raise AuditError(f"{label} has no valid declared root identity.")
    for capture_class, field in (("wide", "wide_capture_id"), ("narrow", "narrow_capture_id")):
        capture_id = proof.get(field)
        if not isinstance(capture_id, str):
            raise AuditError(f"{label} has no {capture_class} schema-3 capture ID.")
        binding_key = (reference_path, capture_id)
        if binding_key in seen_capture_bindings:
            raise AuditError(f"{label} reuses schema-3 capture {capture_id!r} from another proof slice instead of preserving independent proof evidence.")
        rendered_capture = captures_by_id.get(capture_id)
        if not isinstance(rendered_capture, dict):
            raise AuditError(f"{label} names unknown schema-3 capture {capture_id!r}.")
        final_route = render_adapter.rendered_capture_route_path(rendered_capture.get("final_url"))
        if final_route != proof.get("route"):
            raise AuditError(f"{label} {capture_class} capture route {final_route!r} does not match declared route {proof.get('route')!r}.")
        viewport = rendered_capture.get("viewport")
        screenshot = rendered_capture.get("screenshot")
        if (
            not isinstance(viewport, dict)
            or not isinstance(viewport.get("width"), int)
            or not isinstance(viewport.get("height"), int)
            or not isinstance(screenshot, dict)
            or not isinstance(screenshot.get("sha256"), str)
            or not isinstance(screenshot.get("pixel_width"), int)
            or not isinstance(screenshot.get("pixel_height"), int)
        ):
            raise AuditError(f"{label} {capture_class} capture has incomplete schema-3 viewport or screenshot metadata.")
        if (
            viewport["width"] < MIN_RENDERED_PROOF_VIEWPORT_WIDTH
            or viewport["height"] < MIN_RENDERED_PROOF_VIEWPORT_HEIGHT
        ):
            raise AuditError(
                f"{label} {capture_class} viewport is too small to act as a rendered proof slice; it must be at least {MIN_RENDERED_PROOF_VIEWPORT_WIDTH} by {MIN_RENDERED_PROOF_VIEWPORT_HEIGHT} CSS pixels.",
            )
        screenshot_relative = rendered_capture_path(
            render_adapter,
            report_relative_path,
            screenshot.get("path"),
            f"{label}.{capture_class}",
        )
        screenshot_reference = {"path": screenshot_relative, "sha256": screenshot["sha256"]}
        try:
            verification = render_adapter.verify_file_reference(
                root,
                screenshot_reference,
                f"{label}.{capture_class}.screenshot",
                render_budget,
                capture=True,
            )
        except Exception as exc:
            raise AuditError(f"{label} {capture_class} screenshot is not the exact schema-3 PNG artifact: {exc}") from exc
        if (
            verification.get("width") != screenshot.get("pixel_width")
            or verification.get("height") != screenshot.get("pixel_height")
            or verification.get("sha256") != screenshot.get("sha256")
        ):
            raise AuditError(f"{label} {capture_class} screenshot metadata does not match its exact PNG artifact.")
        screenshot_hash = verification.get("sha256")
        if not isinstance(screenshot_hash, str):
            raise AuditError(f"{label} {capture_class} screenshot has no verified SHA-256 identity.")
        prior_roots = capture_hash_roots.get(screenshot_hash, set())
        other_roots = prior_roots - {root_id}
        if other_roots:
            raise AuditError(
                f"{label} {capture_class} screenshot reuses identical pixels from Direction Challenge root(s) {', '.join(sorted(other_roots))}; independently rendered roots cannot share proof-image bytes.",
            )
        capture_hash_roots.setdefault(screenshot_hash, set()).add(root_id)
        seen_capture_bindings.add(binding_key)
        width_by_class[capture_class] = viewport["width"]
        hashes.add(screenshot_hash)
        capture_records.append({
            "kind": "proof-capture",
            "proof_slice_id": proof_id,
            "capture_class": capture_class,
            "capture_id": capture_id,
            "route": proof.get("route"),
            "path": verification.get("path"),
            "sha256": verification.get("sha256"),
            "viewport": [viewport.get("width"), viewport.get("height")],
            "pixel_dimensions": [verification.get("width"), verification.get("height")],
        })
    if width_by_class.get("wide", 0) <= width_by_class.get("narrow", 0):
        raise AuditError(f"{label} wide capture is not wider than its narrow schema-3 companion.")
    if len(hashes) != 2:
        raise AuditError(f"{label} wide and narrow captures resolve to the same screenshot hash.")
    report_verification = result.get("verification")
    if isinstance(report_verification, dict):
        capture_records.insert(0, {
            "kind": "schema-3-render-review",
            "proof_slice_id": proof_id,
            "path": report_verification.get("path"),
            "sha256": report_verification.get("sha256"),
            "build_id": proof.get("build_id"),
            "source_snapshot_manifest_sha256": manifest_digest,
        })
    return capture_records


def finalize_report(report: dict[str, Any]) -> dict[str, Any]:
    report["ready"] = bool(
        report.get("structural_valid")
        and not report.get("gaps")
        and not any(entry.get("blocking") for entry in report.get("findings", []))
    )
    return report


def audit_payload(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    errors, contract = validate_contract_payload(payload)
    report: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "tool_version": TOOL_VERSION,
        "automatic_aesthetic_pass": False,
        "structural_valid": not errors,
        "ready": False,
        "findings": [],
        "gaps": [],
        "lifecycle": {
            "status": payload.get("record_status") if isinstance(payload, dict) else None,
            "required_status_for_ready": "reviewed",
            "meaning": "The lifecycle binds evidence stages; it does not certify visual quality, originality, or human authorship.",
        },
        "evidence": {"verified": [], "bytes": 0},
        "limitations": [
            "This audit verifies the declared roots, frozen schema-3 render evidence, local source-manifest binding, and review boundary; it does not score visual quality, originality, or authorship.",
            "The path-bound output marker resists accidental output copying and stale standalone screenshots, but is not a cryptographic signature against an actor able to rewrite every owned artifact.",
        ],
    }
    findings: list[dict[str, object]] = report["findings"]
    gaps: list[dict[str, str]] = report["gaps"]
    if errors or contract is None:
        for error in errors:
            findings.append(finding(error["code"], f"{error['path']}: {error['message']}", blocking=True))
        return finalize_report(report)
    status = contract["record_status"]
    if status == "draft":
        add_gap(gaps, "direction-challenge-draft", "Direction Challenge is an intentionally unresolved draft; record the brief-native roots before requesting readiness.")
        return finalize_report(report)
    if status == "roots-ready":
        add_gap(gaps, "direction-challenge-roots-ready", "Roots are recorded, but two rendered proof slices and an explicit selection remain required before readiness.")
        return finalize_report(report)
    if status == "proof-ready":
        add_gap(gaps, "direction-challenge-proof-ready", "Proof slices are recorded, but an independent unprimed review remains required before readiness.")
    try:
        render_adapter = load_render_review_adapter()
        render_budget = render_adapter.EvidenceBudget()
    except AuditError as exc:
        findings.append(finding("schema3-render-review-verifier-unavailable", str(exc), blocking=True))
        render_adapter = None
        render_budget = None
    review_budget = [0]
    proof_slices = contract["proof_slices"]
    render_cache: dict[tuple[str, str], dict[str, Any]] = {}
    seen_capture_bindings: set[tuple[str, str]] = set()
    capture_hash_roots: dict[str, set[str]] = {}
    for proof in proof_slices:
        if not isinstance(proof, dict):
            continue
        if render_adapter is None or render_budget is None:
            break
        try:
            report["evidence"]["verified"].extend(
                verify_proof_slice(
                    root,
                    proof,
                    render_adapter,
                    render_budget,
                    render_cache,
                    seen_capture_bindings,
                    capture_hash_roots,
                )
            )
        except AuditError as exc:
            findings.append(finding("invalid-proof-slice-evidence", str(exc), blocking=True))
    unprimed = contract.get("review", {}).get("unprimed") if isinstance(contract.get("review"), dict) else None
    if isinstance(unprimed, dict) and isinstance(unprimed.get("evidence"), dict):
        try:
            path, data = verify_file_reference(root, unprimed["evidence"], "unprimed review evidence", review_budget)
            report["evidence"]["verified"].append({"kind": "unprimed-review", "path": str(path.relative_to(root)), "sha256": hashlib.sha256(data).hexdigest()})
        except AuditError as exc:
            findings.append(finding("invalid-unprimed-review-evidence", str(exc), blocking=True))
    render_bytes = render_budget.bytes if render_budget is not None else 0
    total_evidence_bytes = render_bytes + review_budget[0]
    if total_evidence_bytes > MAX_TOTAL_EVIDENCE_BYTES:
        findings.append(finding("evidence-total-too-large", "Direction Challenge evidence exceeds the cumulative audit byte limit.", blocking=True))
    report["evidence"]["bytes"] = total_evidence_bytes
    return finalize_report(report)


def load_contract(path: Path) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise AuditError(f"Unable to read contract: {exc}") from exc
    if len(payload) > MAX_CONTRACT_BYTES:
        raise AuditError("Direction Challenge contract exceeds the safe size limit.")
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"Direction Challenge contract is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise AuditError("Direction Challenge contract root must be an object.")
    return parsed


def resolve_contract(project: Path, contract: str) -> Path:
    return project_file(project, contract, "Direction Challenge contract")


def output_path(project: Path, output: str) -> Path:
    relative = portable_path(output, "audit output")
    target = project.joinpath(*PurePosixPath(relative).parts)
    parent = target.parent
    if not parent.is_dir() or is_reparse(parent):
        raise AuditError("Audit output parent must be an existing regular project directory.")
    try:
        parent.resolve(strict=True).relative_to(project.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise AuditError("Audit output must remain inside the project root.") from exc
    if target.exists() and is_reparse(target):
        raise AuditError("Audit output may not replace a symlink or reparse point.")
    return target


def write_json(path: Path, payload: dict[str, Any]) -> None:
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except UnboundLocalError:
            pass
        raise AuditError(f"Unable to write audit report: {exc}") from exc


def run(project: Path, contract_arg: str) -> tuple[dict[str, Any], int]:
    project = project.resolve(strict=True)
    contract_path = resolve_contract(project, contract_arg)
    contract = load_contract(contract_path)
    report = audit_payload(project, contract)
    report["project"] = str(project)
    report["contract"] = str(contract_path.relative_to(project))
    return report, 0 if report["ready"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, nargs="?", default=Path.cwd())
    parser.add_argument("--contract", default=DEFAULT_CONTRACT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-ready", action="store_true", help="Return nonzero unless the evidence record is ready (the default behavior).")
    parser.add_argument("--allow-incomplete", action="store_true", help="Write and return a provisional diagnostic report even when evidence is incomplete.")
    parser.add_argument("--stdout", action="store_true", help="Also print the JSON report to stdout.")
    args = parser.parse_args()
    if args.require_ready and args.allow_incomplete:
        parser.error("--require-ready and --allow-incomplete cannot be combined")
    try:
        report, readiness_code = run(args.project, args.contract)
        path = output_path(args.project.resolve(strict=True), args.output)
        write_json(path, report)
        if args.stdout:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if args.allow_incomplete else readiness_code
    except AuditError as exc:
        error = {"artifact_type": ARTIFACT_TYPE, "ok": False, "error": str(exc)}
        if args.stdout:
            print(json.dumps(error, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(error, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
