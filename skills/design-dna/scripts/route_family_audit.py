#!/usr/bin/env python3
"""Audit a project-local Design DNA route-family contract.

The audit proves bounded structural facts about declared routes, literal link
targets, rendered-review coverage, and aggregate main-content silhouettes. It
does not score authorship, detect AI use, or automatically pass aesthetics.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import html
import json
import math
import os
import re
import stat
import sys
import tempfile
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import unquote, unquote_to_bytes, urljoin, urlsplit


MINIMUM_PYTHON = (3, 10)
SCHEMA_VERSION = 3
TOOL_VERSION = "3.0.0"
ARTIFACT_TYPE = "design-dna-route-family-audit"
DEFAULT_CONTRACT = Path(".design-dna") / "route-family.json"
DEFAULT_ATLAS = Path(".design-dna") / "route-atlas.html"
MAX_ENTRIES = 50_000
MAX_SOURCE_FILE_BYTES = 5 * 1024 * 1024
MAX_SOURCE_TOTAL_BYTES = 64 * 1024 * 1024
MAX_RENDER_REPORT_BYTES = 8 * 1024 * 1024
MAX_RENDER_REPORT_TOTAL_BYTES = 64 * 1024 * 1024
MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_FINDINGS = 1_000
MAX_CONTRACT_ERRORS = 200
MAX_RENDER_SCHEMA_ERRORS = 50
RUNTIME_RENDER_SCHEMA = (
    Path(__file__).resolve().parents[1] / "schemas" / "render-review.schema.json"
)
IGNORED_DIRS = {
    ".design-dna",
    ".git",
    ".next",
    ".nuxt",
    ".output",
    ".svelte-kit",
    ".vercel",
    "coverage",
    "node_modules",
    "vendor",
}
SOURCE_SUFFIXES = {
    ".astro",
    ".htm",
    ".html",
    ".js",
    ".jsx",
    ".mdx",
    ".mjs",
    ".svelte",
    ".ts",
    ".tsx",
    ".vue",
}
HTML_SUFFIXES = {".htm", ".html"}
FRAMEWORK_EXTENSIONS = (".astro", ".js", ".jsx", ".mdx", ".mjs", ".ts", ".tsx", ".svelte", ".vue")
ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,47}$")
MANIFEST_STATE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
MANIFEST_STATE_KINDS = {"rest", "interactive", "system", "data"}
MANIFEST_TRIGGER_TYPES = {
    "none", "hover", "focus", "click", "keyboard", "input", "url",
    "programmatic",
}
INVALID_PERCENT_PATTERN = re.compile(r"%(?![0-9A-Fa-f]{2})")
SEMVER_PATTERN = re.compile(
    r"^design-dna "
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-(?:(?:0|[1-9][0-9]*)|(?:[0-9]*[A-Za-z-][0-9A-Za-z-]*))"
    r"(?:\.(?:(?:0|[1-9][0-9]*)|(?:[0-9]*[A-Za-z-][0-9A-Za-z-]*)))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
HREF_PATTERN = re.compile(
    r"\b(?:href|to)\s*=\s*(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
    re.I | re.S,
)
META_REFRESH_PATTERN = re.compile(
    r"<meta\b(?=[^>]*\bhttp-equiv\s*=\s*[\"']?\s*refresh\b)"
    r"(?=[^>]*\bcontent\s*=\s*(?P<quote>[\"'])(?P<content>.*?)(?P=quote))[^>]*>",
    re.I | re.S,
)
CODE_REDIRECT_PATTERN = re.compile(
    r"\b(?:redirect|permanentRedirect|location\.(?:replace|assign))\s*\(\s*"
    r"(?P<quote>[\"'])(?P<target>/[^\"']*)(?P=quote)",
    re.I,
)
LOCATION_ASSIGNMENT_PATTERN = re.compile(
    r"\b(?:window\.)?location(?:\.href)?\s*=\s*"
    r"(?P<quote>[\"'])(?P<target>/[^\"']*)(?P=quote)",
    re.I,
)
DYNAMIC_LINK_PATTERN = re.compile(r"\{\{|{%|<%|\$\{|[`{}]")


class AuditError(RuntimeError):
    """A safety, integrity, resource, or input failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _json_type_matches(value: object, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
    if expected == "integer":
        return (
            isinstance(value, int)
            and not isinstance(value, bool)
        ) or (
            isinstance(value, float)
            and math.isfinite(value)
            and value.is_integer()
        )
    return False


def _json_equal(left: object, right: object) -> bool:
    if (
        isinstance(left, (int, float))
        and not isinstance(left, bool)
        and isinstance(right, (int, float))
        and not isinstance(right, bool)
    ):
        return math.isfinite(left) and math.isfinite(right) and left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(
            _json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _json_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return left == right


def _schema_pointer(root: dict[str, object], reference: str) -> object:
    if reference == "#":
        return root
    if not reference.startswith("#/"):
        raise AuditError(
            "render-report-schema-invalid",
            "The bundled rendered-review schema contains a non-local reference.",
        )
    current: object = root
    for raw_token in reference[2:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise AuditError(
                "render-report-schema-invalid",
                "The bundled rendered-review schema contains an unresolved reference.",
            )
        current = current[token]
    return current


def _schema_format_valid(value: str, format_name: str) -> bool:
    if format_name == "date-time":
        if not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:"
            r"[0-9]{2}(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})",
            value,
        ):
            return False
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        return parsed.tzinfo is not None
    if format_name == "uri":
        if any(character.isspace() or ord(character) <= 0x1F for character in value):
            return False
        try:
            parsed = urlsplit(value)
        except ValueError:
            return False
        return bool(parsed.scheme)
    return True


def _schema_instance_errors(
    value: object,
    schema: object,
    root: dict[str, object],
    *,
    path: str = "$",
    limit: int = MAX_RENDER_SCHEMA_ERRORS,
) -> list[str]:
    errors: list[str] = []

    def add(location: str, message: str) -> None:
        if len(errors) < limit:
            errors.append(f"{location}: {message}")

    def valid(candidate: object, rule: object) -> bool:
        return not _schema_instance_errors(
            candidate,
            rule,
            root,
            path=path,
            limit=1,
        )

    def visit(candidate: object, rule: object, location: str) -> None:
        if len(errors) >= limit:
            return
        if rule is True:
            return
        if rule is False:
            add(location, "the schema rejects this value")
            return
        if not isinstance(rule, dict):
            raise AuditError(
                "render-report-schema-invalid",
                "The bundled rendered-review schema contains a non-object rule.",
            )
        reference = rule.get("$ref")
        if isinstance(reference, str):
            visit(candidate, _schema_pointer(root, reference), location)
            if len(errors) >= limit:
                return
        for subrule in rule.get("allOf", []):
            visit(candidate, subrule, location)
        any_of = rule.get("anyOf")
        if isinstance(any_of, list) and not any(valid(candidate, item) for item in any_of):
            add(location, "does not satisfy any allowed schema branch")
        one_of = rule.get("oneOf")
        if isinstance(one_of, list):
            matches = sum(valid(candidate, item) for item in one_of)
            if matches != 1:
                add(location, f"satisfies {matches} oneOf branches; expected exactly one")
        if "not" in rule and valid(candidate, rule["not"]):
            add(location, "matches a prohibited schema branch")
        conditional = rule.get("if")
        if isinstance(conditional, (dict, bool)):
            branch = rule.get("then") if valid(candidate, conditional) else rule.get("else")
            if branch is not None:
                visit(candidate, branch, location)

        expected_type = rule.get("type")
        if isinstance(expected_type, str):
            expected_types = [expected_type]
        elif isinstance(expected_type, list) and all(
            isinstance(item, str) for item in expected_type
        ):
            expected_types = expected_type
        else:
            expected_types = []
        if expected_types and not any(
            _json_type_matches(candidate, item) for item in expected_types
        ):
            add(location, "has the wrong JSON type")
            return
        if "const" in rule and not _json_equal(candidate, rule["const"]):
            add(location, "does not match the required constant")
        enum = rule.get("enum")
        if isinstance(enum, list) and not any(
            _json_equal(candidate, option) for option in enum
        ):
            add(location, "is not an allowed enum value")

        if isinstance(candidate, str):
            minimum_length = rule.get("minLength")
            maximum_length = rule.get("maxLength")
            if isinstance(minimum_length, int) and len(candidate) < minimum_length:
                add(location, f"is shorter than {minimum_length} characters")
            if isinstance(maximum_length, int) and len(candidate) > maximum_length:
                add(location, f"is longer than {maximum_length} characters")
            pattern = rule.get("pattern")
            if isinstance(pattern, str) and re.search(pattern, candidate) is None:
                add(location, "does not match the required pattern")
            format_name = rule.get("format")
            if isinstance(format_name, str) and not _schema_format_valid(
                candidate,
                format_name,
            ):
                add(location, f"is not a valid {format_name}")

        if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
            minimum = rule.get("minimum")
            maximum = rule.get("maximum")
            if isinstance(minimum, (int, float)) and candidate < minimum:
                add(location, f"is less than {minimum}")
            if isinstance(maximum, (int, float)) and candidate > maximum:
                add(location, f"is greater than {maximum}")

        if isinstance(candidate, list):
            minimum_items = rule.get("minItems")
            maximum_items = rule.get("maxItems")
            if isinstance(minimum_items, int) and len(candidate) < minimum_items:
                add(location, f"contains fewer than {minimum_items} items")
            if isinstance(maximum_items, int) and len(candidate) > maximum_items:
                add(location, f"contains more than {maximum_items} items")
            if rule.get("uniqueItems") is True:
                for index, item in enumerate(candidate):
                    if any(_json_equal(item, earlier) for earlier in candidate[:index]):
                        add(f"{location}[{index}]", "duplicates an earlier array item")
                        break
            prefix_items = rule.get("prefixItems")
            prefix_count = 0
            if isinstance(prefix_items, list):
                prefix_count = len(prefix_items)
                for index, subrule in enumerate(prefix_items[: len(candidate)]):
                    visit(candidate[index], subrule, f"{location}[{index}]")
            item_rule = rule.get("items")
            if isinstance(item_rule, (dict, bool)):
                for index in range(prefix_count, len(candidate)):
                    visit(candidate[index], item_rule, f"{location}[{index}]")
            contains_rule = rule.get("contains")
            if isinstance(contains_rule, (dict, bool)):
                matches = sum(valid(item, contains_rule) for item in candidate)
                minimum_contains = rule.get("minContains", 1)
                if isinstance(minimum_contains, int) and matches < minimum_contains:
                    add(location, f"contains only {matches} matching items")

        if isinstance(candidate, dict):
            required = rule.get("required")
            if isinstance(required, list):
                for key in required:
                    if isinstance(key, str) and key not in candidate:
                        add(location, f"is missing required property {key!r}")
            minimum_properties = rule.get("minProperties")
            maximum_properties = rule.get("maxProperties")
            if isinstance(minimum_properties, int) and len(candidate) < minimum_properties:
                add(location, f"contains fewer than {minimum_properties} properties")
            if isinstance(maximum_properties, int) and len(candidate) > maximum_properties:
                add(location, f"contains more than {maximum_properties} properties")
            properties = rule.get("properties")
            property_rules = properties if isinstance(properties, dict) else {}
            for key, subrule in property_rules.items():
                if key in candidate:
                    visit(candidate[key], subrule, f"{location}.{key}")
            additional = rule.get("additionalProperties", True)
            for key in candidate.keys() - property_rules.keys():
                child_path = f"{location}.{key}"
                if additional is False:
                    add(child_path, "is an unexpected property")
                elif isinstance(additional, dict):
                    visit(candidate[key], additional, child_path)

    visit(value, schema, path)
    return errors


def load_render_report_schema() -> dict[str, object]:
    path = RUNTIME_RENDER_SCHEMA
    if not path.is_file() or is_reparse(path):
        raise AuditError(
            "render-report-schema-unavailable",
            "The bundled rendered-review schema is missing or unsafe.",
        )
    raw = stable_bytes(path, MAX_RENDER_REPORT_BYTES)
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError(
            "render-report-schema-invalid",
            "The bundled rendered-review schema is not valid UTF-8 JSON.",
        ) from exc
    if not isinstance(payload, dict) or payload.get("$id") != (
        "https://design-dna.local/schemas/render-review.schema.json"
    ):
        raise AuditError(
            "render-report-schema-invalid",
            "The bundled rendered-review schema has the wrong identity.",
        )
    return payload


class Budget:
    def __init__(self) -> None:
        self.started = time.monotonic()
        self.entries_observed = 0
        self.source_files_read = 0
        self.source_bytes_read = 0
        self.render_reports_read = 0
        self.render_report_bytes_read = 0
        self.report_bytes = 1

    def entry(self) -> None:
        self.entries_observed += 1
        if self.entries_observed > MAX_ENTRIES:
            raise AuditError(
                "project-entry-limit-exceeded",
                f"Project traversal exceeded {MAX_ENTRIES} entries.",
            )

    def source(self, size: int) -> None:
        if size > MAX_SOURCE_FILE_BYTES:
            raise AuditError(
                "source-file-limit-exceeded",
                f"A required source file exceeds {MAX_SOURCE_FILE_BYTES} bytes.",
            )
        if self.source_bytes_read + size > MAX_SOURCE_TOTAL_BYTES:
            raise AuditError(
                "source-total-limit-exceeded",
                f"Required source reads exceed {MAX_SOURCE_TOTAL_BYTES} bytes.",
            )
        self.source_files_read += 1
        self.source_bytes_read += size

    def render_report(self, size: int) -> None:
        if size > MAX_RENDER_REPORT_BYTES:
            raise AuditError(
                "render-report-size-limit-exceeded",
                f"A rendered-review report exceeds {MAX_RENDER_REPORT_BYTES} bytes.",
            )
        if self.render_report_bytes_read + size > MAX_RENDER_REPORT_TOTAL_BYTES:
            raise AuditError(
                "render-report-total-limit-exceeded",
                "Rendered-review report inputs exceed the cumulative "
                f"{MAX_RENDER_REPORT_TOTAL_BYTES}-byte audit limit.",
            )
        self.render_reports_read += 1
        self.render_report_bytes_read += size

    def record(self) -> dict[str, object]:
        return {
            "entries_observed": self.entries_observed,
            "source_files_read": self.source_files_read,
            "source_bytes_read": self.source_bytes_read,
            "render_reports_read": self.render_reports_read,
            "render_report_bytes_read": self.render_report_bytes_read,
            "report_bytes": self.report_bytes,
            "elapsed_milliseconds": round(
                (time.monotonic() - self.started) * 1000,
                3,
            ),
            "limits": {
                "entries": MAX_ENTRIES,
                "source_file_bytes": MAX_SOURCE_FILE_BYTES,
                "source_total_bytes": MAX_SOURCE_TOTAL_BYTES,
                "render_report_bytes": MAX_RENDER_REPORT_BYTES,
                "render_report_total_bytes": MAX_RENDER_REPORT_TOTAL_BYTES,
                "report_bytes": MAX_REPORT_BYTES,
            },
        }


def is_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = getattr(metadata, "st_file_attributes", 0)
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & marker)


def canonical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def contained(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def ensure_no_reparse_ancestors(path: Path, root: Path) -> None:
    candidate = canonical(path)
    if not contained(candidate, root):
        raise AuditError(
            "path-outside-project",
            "A project-local path resolves outside the project root.",
        )
    current = candidate
    while True:
        if current.exists() and is_reparse(current):
            raise AuditError(
                "reparse-point-refused",
                "A project-local path crosses a symlink, junction, or reparse point.",
            )
        if current == root:
            break
        current = current.parent


def portable_project_path(path: Path, root: Path) -> str:
    candidate = canonical(path)
    if not contained(candidate, root):
        raise AuditError(
            "path-outside-project",
            "A persisted project path resolves outside the project root.",
        )
    relative = candidate.relative_to(root).as_posix()
    if not relative or relative == ".":
        raise AuditError(
            "invalid-portable-path",
            "A persisted artifact path cannot be the project root.",
        )
    return relative


def stable_bytes(path: Path, maximum: int) -> bytes:
    if not path.is_file() or is_reparse(path):
        raise AuditError(
            "unsafe-file",
            "A required input is not an ordinary, non-linked file.",
        )
    before = path.stat()
    if before.st_size > maximum:
        raise AuditError(
            "input-size-limit-exceeded",
            f"A required input exceeds {maximum} bytes.",
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AuditError("input-read-failed", str(exc)) from exc
    after = path.stat()
    if (
        len(raw) != before.st_size
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        raise AuditError(
            "input-changed-during-read",
            "A required input changed while it was being read.",
        )
    return raw


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path, maximum: int = MAX_RENDER_REPORT_BYTES) -> str:
    return sha256_bytes(stable_bytes(path, maximum))


def error_item(path: str, code: str, message: str) -> dict[str, str]:
    return {"path": path, "code": code, "message": message}


def exact_keys(
    value: object,
    path: str,
    required: set[str],
    errors: list[dict[str, str]],
) -> Optional[dict[str, object]]:
    if not isinstance(value, dict):
        errors.append(error_item(path, "wrong-type", "Expected an object."))
        return None
    observed = set(value)
    missing = sorted(required - observed)
    extra = sorted(observed - required)
    if missing:
        errors.append(
            error_item(
                path,
                "missing-properties",
                "Missing required properties: " + ", ".join(missing) + ".",
            )
        )
    if extra:
        errors.append(
            error_item(
                path,
                "unknown-properties",
                "Unknown properties: " + ", ".join(extra) + ".",
            )
        )
    return value


def string_field(
    value: object,
    path: str,
    errors: list[dict[str, str]],
    *,
    maximum: int = 1200,
) -> bool:
    valid = isinstance(value, str) and bool(value.strip()) and len(value) <= maximum
    if not valid:
        errors.append(
            error_item(
                path,
                "invalid-string",
                f"Expected a nonempty string no longer than {maximum} characters.",
            )
        )
    return valid


def source_mapping_field(
    value: object,
    path_label: str,
    errors: list[dict[str, str]],
) -> Optional[dict[str, object]]:
    mapping = exact_keys(
        value,
        path_label,
        {"rank", "id", "observation", "sha256"},
        errors,
    )
    if mapping is None:
        return None
    rank = mapping.get("rank")
    source_id = mapping.get("id")
    observation = mapping.get("observation")
    digest = mapping.get("sha256")
    if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
        errors.append(error_item(f"{path_label}.rank", "invalid-source-rank", "Expected a positive selected-reference rank."))
    if not isinstance(source_id, str) or re.fullmatch(r"strong-[1-9][0-9]*", source_id) is None:
        errors.append(error_item(f"{path_label}.id", "invalid-source-id", "Expected a strong-N observation identity."))
    expected_observation = (
        f".design-dna/references/{source_id}-observation.json"
        if isinstance(source_id, str)
        else None
    )
    if observation != expected_observation:
        errors.append(error_item(f"{path_label}.observation", "invalid-source-observation", "Expected an exact project-relative reference observation path."))
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        errors.append(error_item(f"{path_label}.sha256", "invalid-source-sha256", "Expected the exact observation SHA-256."))
    if isinstance(source_id, str) and isinstance(rank, int):
        match = re.match(r"strong-([1-9][0-9]*)", source_id)
        if match is None or int(match.group(1)) != rank:
            errors.append(error_item(path_label, "source-rank-id-mismatch", "Source rank must equal the strong-N identity."))
    return mapping


def validate_contract_payload(
    payload: object,
) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    """Validate the schema-3 reference-bound contract without JSON Schema."""
    errors: list[dict[str, str]] = []
    routes_out: list[dict[str, object]] = []
    root_keys = {
        "schema_version",
        "created_with",
        "classification",
        "study",
        "shared_contract",
        "routes",
        "review",
    }
    root = exact_keys(payload, "$", root_keys, errors)
    if root is None:
        return errors[:MAX_CONTRACT_ERRORS], routes_out
    if root.get("schema_version") != 3:
        errors.append(
            error_item("$.schema_version", "unsupported-schema", "Expected integer 3.")
        )
    created_with = root.get("created_with")
    if not isinstance(created_with, str) or not SEMVER_PATTERN.fullmatch(created_with):
        errors.append(
            error_item(
                "$.created_with",
                "invalid-created-with",
                "Expected a concrete design-dna semantic version.",
            )
        )
    if root.get("classification") != "internal":
        errors.append(
            error_item(
                "$.classification",
                "invalid-classification",
                "Route-family contracts must be classified internal.",
            )
        )

    study = exact_keys(
        root.get("study"),
        "$.study",
        {"id", "title", "requested_route_count"},
        errors,
    )
    requested_count: Optional[int] = None
    if study is not None:
        study_id = study.get("id")
        if not isinstance(study_id, str) or not ID_PATTERN.fullmatch(study_id):
            errors.append(
                error_item("$.study.id", "invalid-id", "Expected a lowercase slug ID.")
            )
        string_field(study.get("title"), "$.study.title", errors, maximum=160)
        observed_count = study.get("requested_route_count")
        if (
            isinstance(observed_count, int)
            and not isinstance(observed_count, bool)
            and observed_count >= 2
        ):
            requested_count = observed_count
        else:
            errors.append(
                error_item(
                    "$.study.requested_route_count",
                    "invalid-route-count",
                    "Expected an integer of at least 2.",
                )
            )

    shared = exact_keys(
        root.get("shared_contract"),
        "$.shared_contract",
        {"identity", "navigation", "truth", "accessibility", "voice", "performance"},
        errors,
    )
    if shared is not None:
        for key in (
            "identity",
            "navigation",
            "truth",
            "accessibility",
            "voice",
            "performance",
        ):
            string_field(shared.get(key), f"$.shared_contract.{key}", errors)

    routes = root.get("routes")
    if not isinstance(routes, list) or len(routes) < 2:
        errors.append(
            error_item(
                "$.routes",
                "invalid-routes",
                "Expected an array containing at least 2 routes.",
            )
        )
        routes = []
    if requested_count is not None and requested_count != len(routes):
        errors.append(
            error_item(
                "$.study.requested_route_count",
                "route-count-mismatch",
                "requested_route_count must equal the number of declared routes.",
            )
        )
    route_keys = {
        "id",
        "path",
        "title",
        "user_job",
        "source_mapping",
        "component_sources",
        "observable_decisions",
        "responsive_result",
        "reduced_motion_result",
        "no_javascript_result",
        "closest_sibling",
        "deliberate_differences",
        "capture_requirements",
        "review_status",
    }
    ids: list[str] = []
    paths: list[str] = []
    route_records: list[tuple[int, dict[str, object]]] = []
    for index, item in enumerate(routes):
        base = f"$.routes[{index}]"
        route = exact_keys(item, base, route_keys, errors)
        if route is None:
            continue
        route_id = route.get("id")
        route_path = route.get("path")
        normalized_route_path = (
            normalize_route_path(route_path)
            if isinstance(route_path, str)
            else None
        )
        if not isinstance(route_id, str) or not ID_PATTERN.fullmatch(route_id):
            errors.append(error_item(f"{base}.id", "invalid-id", "Expected a slug ID."))
        else:
            ids.append(route_id)
        if normalized_route_path is None:
            errors.append(
                error_item(
                    f"{base}.path",
                    "invalid-route-path",
                    "Expected a safe absolute route path without a query, fragment, traversal, controls, whitespace, backslashes, or encoded separators.",
                )
            )
        else:
            paths.append(normalized_route_path)
        for key in (
            "title",
            "user_job",
            "responsive_result",
            "reduced_motion_result",
            "no_javascript_result",
        ):
            string_field(
                route.get(key),
                f"{base}.{key}",
                errors,
                maximum=160 if key == "title" else 1200,
            )
        source_mapping = source_mapping_field(route.get("source_mapping"), f"{base}.source_mapping", errors)
        component_sources = route.get("component_sources")
        if not isinstance(component_sources, list) or not 1 <= len(component_sources) <= 512:
            errors.append(error_item(f"{base}.component_sources", "invalid-component-sources", "Expected 1 through 512 exact census-component source mappings."))
        else:
            component_names: list[str] = []
            for component_index, component_item in enumerate(component_sources):
                component_base = f"{base}.component_sources[{component_index}]"
                component = exact_keys(
                    component_item,
                    component_base,
                    {"component", "source_rank", "source_id", "source_observation", "source_sha256", "source_state_id", "transfer"},
                    errors,
                )
                if component is None:
                    continue
                for key in ("component", "source_state_id", "transfer"):
                    string_field(component.get(key), f"{component_base}.{key}", errors)
                component_names.append(str(component.get("component") or ""))
                component_mapping = {
                    "rank": component.get("source_rank"),
                    "id": component.get("source_id"),
                    "observation": component.get("source_observation"),
                    "sha256": component.get("source_sha256"),
                }
                source_mapping_field(component_mapping, component_base, errors)
                if source_mapping is not None and component_mapping != source_mapping:
                    errors.append(error_item(component_base, "component-source-route-mismatch", "Every route component must bind the route's exact selected observation; producer-authored connective design is forbidden."))
            if len(component_names) != len(set(component_names)):
                errors.append(error_item(f"{base}.component_sources", "duplicate-component-source", "Component source keys must be unique within a route."))
        decisions = route.get("observable_decisions")
        if not isinstance(decisions, list) or not 1 <= len(decisions) <= 24:
            errors.append(
                error_item(
                    f"{base}.observable_decisions",
                    "invalid-observable-decisions",
                    "Expected 1 through 24 project-specific decision records.",
                )
            )
        else:
            for decision_index, decision_item in enumerate(decisions):
                decision_base = f"{base}.observable_decisions[{decision_index}]"
                decision = exact_keys(
                    decision_item,
                    decision_base,
                    {"decision", "reason", "evidence", "source_rank", "source_id", "source_observation", "source_sha256", "source_state_id", "status"},
                    errors,
                )
                if decision is None:
                    continue
                for key in ("decision", "reason", "evidence"):
                    string_field(
                        decision.get(key),
                        f"{decision_base}.{key}",
                        errors,
                    )
                decision_mapping = {
                    "rank": decision.get("source_rank"),
                    "id": decision.get("source_id"),
                    "observation": decision.get("source_observation"),
                    "sha256": decision.get("source_sha256"),
                }
                source_mapping_field(decision_mapping, decision_base, errors)
                if source_mapping is not None and decision_mapping != source_mapping:
                    errors.append(error_item(decision_base, "decision-source-route-mismatch", "Every visible decision must bind the route's exact selected observation."))
                string_field(decision.get("source_state_id"), f"{decision_base}.source_state_id", errors, maximum=64)
                if decision.get("status") not in {
                    "provisional",
                    "accepted",
                    "revised",
                    "rejected",
                }:
                    errors.append(
                        error_item(
                            f"{decision_base}.status",
                            "invalid-decision-status",
                            "Expected provisional, accepted, revised, or rejected.",
                        )
                    )
        closest = route.get("closest_sibling")
        if closest is not None and (
            not isinstance(closest, str) or not ID_PATTERN.fullmatch(closest)
        ):
            errors.append(
                error_item(
                    f"{base}.closest_sibling",
                    "invalid-closest-sibling",
                    "Expected a route ID or null.",
                )
            )
        differences = route.get("deliberate_differences")
        if not (
            isinstance(differences, list)
            and len(differences) <= 12
            and len(differences) == len(set(differences))
            and all(
                isinstance(value, str) and value.strip() and len(value) <= 1200
                for value in differences
            )
        ):
            errors.append(
                error_item(
                    f"{base}.deliberate_differences",
                    "invalid-deliberate-differences",
                    "Expected 0 through 12 unique, nonempty difference statements; an empty list records honest reuse.",
                )
            )
        route_status = route.get("review_status")
        capture = exact_keys(
            route.get("capture_requirements"),
            f"{base}.capture_requirements",
            {"viewports"},
            errors,
        )
        viewports_out: list[dict[str, object]] = []
        if capture is not None:
            viewports = capture.get("viewports")
            if not isinstance(viewports, list) or not 2 <= len(viewports) <= 6:
                errors.append(
                    error_item(
                        f"{base}.capture_requirements.viewports",
                        "invalid-viewports",
                        "Expected 2 through 6 viewport requirements.",
                    )
                )
                viewports = []
            viewport_ids: list[str] = []
            widths: list[int] = []
            for viewport_index, viewport_item in enumerate(viewports):
                viewport_base = (
                    f"{base}.capture_requirements.viewports[{viewport_index}]"
                )
                viewport = exact_keys(
                    viewport_item,
                    viewport_base,
                    {"id", "width"},
                    errors,
                )
                if viewport is None:
                    continue
                viewport_id = viewport.get("id")
                width = viewport.get("width")
                if not isinstance(viewport_id, str) or not ID_PATTERN.fullmatch(
                    viewport_id
                ):
                    errors.append(
                        error_item(
                            f"{viewport_base}.id",
                            "invalid-viewport-id",
                            "Expected a lowercase slug ID.",
                        )
                    )
                else:
                    viewport_ids.append(viewport_id)
                unresolved_planned_width = (
                    width is None and route_status == "planned"
                )
                if not unresolved_planned_width and (
                    not isinstance(width, int)
                    or isinstance(width, bool)
                    or not 240 <= width <= 3840
                ):
                    errors.append(
                        error_item(
                            f"{viewport_base}.width",
                            "invalid-viewport-width",
                            "Expected an integer width from 240 through 3840; null is allowed only while the route remains planned.",
                        )
                    )
                elif (
                    isinstance(width, int)
                    and not isinstance(width, bool)
                    and 240 <= width <= 3840
                ):
                    widths.append(width)
                if (
                    isinstance(viewport_id, str)
                    and ID_PATTERN.fullmatch(viewport_id)
                    and isinstance(width, int)
                    and not isinstance(width, bool)
                    and 240 <= width <= 3840
                ):
                    viewports_out.append({"id": viewport_id, "width": width})
            if len(viewport_ids) != len(set(viewport_ids)):
                errors.append(
                    error_item(
                        f"{base}.capture_requirements.viewports",
                        "duplicate-viewport-id",
                        "Viewport IDs must be unique within a route.",
                    )
                )
            if len(widths) != len(set(widths)):
                errors.append(
                    error_item(
                        f"{base}.capture_requirements.viewports",
                        "duplicate-viewport-width",
                        "Viewport widths must be unique within a route so each declared comparison is unambiguous.",
                    )
                )
        if route_status not in {
            "planned",
            "implemented",
            "audited",
            "accepted",
        }:
            errors.append(
                error_item(
                    f"{base}.review_status",
                    "invalid-review-status",
                    "Expected planned, implemented, audited, or accepted.",
                )
            )
        route_records.append((index, route))
        if (
            isinstance(route_id, str)
            and ID_PATTERN.fullmatch(route_id)
            and normalized_route_path is not None
        ):
            routes_out.append(
                {
                    "id": route_id,
                    "path": normalized_route_path,
                    "title": route.get("title"),
                    "source_mapping": route.get("source_mapping"),
                    "component_sources": route.get("component_sources"),
                    "observable_decisions": route.get("observable_decisions"),
                    "capture_requirements": {"viewports": viewports_out},
                }
            )
    duplicate_ids = sorted({value for value in ids if ids.count(value) > 1})
    duplicate_paths = sorted({value for value in paths if paths.count(value) > 1})
    if duplicate_ids:
        errors.append(
            error_item(
                "$.routes",
                "duplicate-route-ids",
                "Route IDs must be unique: " + ", ".join(duplicate_ids) + ".",
            )
        )
    if duplicate_paths:
        errors.append(
            error_item(
                "$.routes",
                "duplicate-route-paths",
                "Normalized route paths must be unique: "
                + ", ".join(duplicate_paths)
                + ".",
            )
        )
    id_set = set(ids)
    for index, route in route_records:
        closest = route.get("closest_sibling")
        route_id = route.get("id")
        if closest is None:
            continue
        if closest == route_id:
            errors.append(
                error_item(
                    f"$.routes[{index}].closest_sibling",
                    "self-closest-sibling",
                    "A route cannot name itself as its closest sibling.",
                )
            )
        elif isinstance(closest, str) and closest not in id_set:
            errors.append(
                error_item(
                    f"$.routes[{index}].closest_sibling",
                    "unknown-closest-sibling",
                    "closest_sibling must identify another declared route.",
                )
            )

    review = exact_keys(
        root.get("review"),
        "$.review",
        {
            "direct_entry",
            "link_integrity",
            "route_count",
            "body_comparison",
            "atlas_artifact",
            "cultural_acceptance",
        },
        errors,
    )
    if review is not None:
        for key in ("direct_entry", "link_integrity", "route_count"):
            if review.get(key) not in {"pending", "passed", "failed"}:
                errors.append(
                    error_item(
                        f"$.review.{key}",
                        "invalid-review-value",
                        "Expected pending, passed, or failed.",
                    )
                )
        if review.get("body_comparison") not in {
            "pending",
            "manual-review-required",
            "reviewed",
        }:
            errors.append(
                error_item(
                    "$.review.body_comparison",
                    "invalid-review-value",
                    "Expected pending, manual-review-required, or reviewed.",
                )
            )
        if review.get("atlas_artifact") not in {
            "pending",
            "not-available",
            "produced",
            "reviewed",
        }:
            errors.append(
                error_item(
                    "$.review.atlas_artifact",
                    "invalid-review-value",
                    "Expected pending, not-available, produced, or reviewed.",
                )
            )
        cultural = exact_keys(
            review.get("cultural_acceptance"),
            "$.review.cultural_acceptance",
            {
                "required",
                "status",
                "reviewer_id",
                "relationship",
                "independent_of_producer",
                "reviewed_at",
                "notes",
            },
            errors,
        )
        if cultural is not None:
            required = cultural.get("required")
            status_value = cultural.get("status")
            reviewer_id = cultural.get("reviewer_id")
            relationship = cultural.get("relationship")
            independent = cultural.get("independent_of_producer")
            reviewed_at = cultural.get("reviewed_at")
            notes = cultural.get("notes")
            if not isinstance(required, bool):
                errors.append(
                    error_item(
                        "$.review.cultural_acceptance.required",
                        "invalid-required",
                        "Expected a boolean.",
                    )
                )
            if status_value not in {"not-required", "pending", "accepted", "rejected"}:
                errors.append(
                    error_item(
                        "$.review.cultural_acceptance.status",
                        "invalid-cultural-status",
                        "Expected not-required, pending, accepted, or rejected.",
                    )
                )
            if reviewer_id is not None and not (
                isinstance(reviewer_id, str)
                and reviewer_id.strip()
                and len(reviewer_id) <= 160
            ):
                errors.append(
                    error_item(
                        "$.review.cultural_acceptance.reviewer_id",
                        "invalid-reviewer-id",
                        "Expected a nonempty reviewer ID or null.",
                    )
                )
            if relationship not in {
                "accountable-community-authority",
                "owner-authorized-cultural-reviewer",
                "not-reviewed",
            }:
                errors.append(
                    error_item(
                        "$.review.cultural_acceptance.relationship",
                        "invalid-cultural-relationship",
                        "Expected a supported cultural-review relationship.",
                    )
                )
            if not isinstance(independent, bool):
                errors.append(
                    error_item(
                        "$.review.cultural_acceptance.independent_of_producer",
                        "invalid-independent-state",
                        "Expected a boolean.",
                    )
                )
            if reviewed_at is not None and not isinstance(reviewed_at, str):
                errors.append(
                    error_item(
                        "$.review.cultural_acceptance.reviewed_at",
                        "invalid-reviewed-at",
                        "Expected a date-time string or null.",
                    )
                )
            if notes is not None and not (
                isinstance(notes, str) and notes.strip() and len(notes) <= 2000
            ):
                errors.append(
                    error_item(
                        "$.review.cultural_acceptance.notes",
                        "invalid-notes",
                        "Expected nonempty notes no longer than 2000 characters or null.",
                    )
                )
            if required is False and not (
                status_value == "not-required"
                and reviewer_id is None
                and relationship == "not-reviewed"
                and independent is False
                and reviewed_at is None
            ):
                errors.append(
                    error_item(
                        "$.review.cultural_acceptance",
                        "not-required-contradiction",
                        "A non-required review must use the complete not-reviewed state.",
                    )
                )
            if required is True and status_value == "not-required":
                errors.append(
                    error_item(
                        "$.review.cultural_acceptance.status",
                        "required-review-not-performed",
                        "A required cultural review cannot be marked not-required.",
                    )
                )
            if status_value == "accepted" and not (
                required is True
                and isinstance(reviewer_id, str)
                and reviewer_id.strip()
                and relationship
                in {
                    "accountable-community-authority",
                    "owner-authorized-cultural-reviewer",
                }
                and independent is True
                and isinstance(reviewed_at, str)
                and reviewed_at.strip()
            ):
                errors.append(
                    error_item(
                        "$.review.cultural_acceptance",
                        "cultural-acceptance-not-independent",
                        "Accepted cultural review requires a named, non-producer cultural authority and review date.",
                    )
                )
            if status_value == "pending" and not (
                reviewer_id is None
                and relationship == "not-reviewed"
                and reviewed_at is None
            ):
                errors.append(
                    error_item(
                        "$.review.cultural_acceptance",
                        "pending-cultural-review-contradiction",
                        "A pending cultural review cannot claim reviewer or completion evidence.",
                    )
                )
    return errors[:MAX_CONTRACT_ERRORS], routes_out


def reference_binding_errors(
    root: Path,
    routes: list[dict[str, object]],
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    observed: dict[str, dict[str, object]] = {}
    manifest_path = canonical(root / ".design-dna" / "route-manifest.json")
    manifest_routes: dict[str, dict[str, object]] = {}
    manifest_state_ids: dict[str, set[str]] = {}
    try:
        ensure_no_reparse_ancestors(manifest_path, root)
        if not contained(manifest_path, root) or not manifest_path.is_file() or is_reparse(manifest_path):
            raise AuditError("route-manifest-missing", "The authoritative .design-dna/route-manifest.json file is missing.")
        manifest_raw = stable_bytes(manifest_path, MAX_SOURCE_FILE_BYTES)
        manifest = json.loads(manifest_raw.decode("utf-8"))
        if (
            not isinstance(manifest, dict)
            or set(manifest) != {"schema_version", "manifest_id", "viewports", "routes"}
            or manifest.get("schema_version") != 2
            or not isinstance(manifest.get("manifest_id"), str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", manifest["manifest_id"]) is None
            or not isinstance(manifest.get("routes"), list)
            or not manifest["routes"]
        ):
            raise AuditError("route-manifest-invalid", "The authoritative route manifest does not use the exact current schema-2 identity and route shape.")
        viewport_names: set[str] = set()
        valid_viewports: list[tuple[int, int]] = []
        if not isinstance(manifest.get("viewports"), list) or not manifest["viewports"]:
            raise AuditError("route-manifest-invalid", "The authoritative route manifest needs a nonempty viewport matrix.")
        for viewport_index, viewport in enumerate(manifest["viewports"]):
            if (
                not isinstance(viewport, dict)
                or set(viewport) != {"name", "width", "height"}
                or not isinstance(viewport.get("name"), str)
                or re.fullmatch(r"[a-z][a-z0-9-]{0,31}", viewport["name"]) is None
                or viewport["name"] in viewport_names
                or type(viewport.get("width")) is not int
                or type(viewport.get("height")) is not int
                or not 280 <= viewport["width"] <= 3840
                or not 480 <= viewport["height"] <= 4320
            ):
                raise AuditError(
                    "route-manifest-invalid",
                    f"Authoritative viewport row {viewport_index + 1} is invalid or duplicated.",
                )
            viewport_names.add(viewport["name"])
            valid_viewports.append((viewport["width"], viewport["height"]))
        if not any(width >= 1280 for width, _height in valid_viewports) or not any(
            width <= 430 for width, _height in valid_viewports
        ):
            raise AuditError("route-manifest-invalid", "The authoritative route manifest must include wide and narrow viewports.")

        manifest_urls: set[tuple[tuple[str, str, int], str]] = set()
        manifest_origins: set[tuple[str, str, int]] = set()
        for manifest_index, manifest_route in enumerate(manifest["routes"]):
            parsed_url = urlsplit(str(manifest_route.get("url") or "")) if isinstance(manifest_route, dict) else None
            normalized_path = normalize_route_path(parsed_url.path or "/") if parsed_url is not None else None
            normalized_origin = (
                (
                    parsed_url.scheme.casefold(),
                    parsed_url.hostname.casefold(),
                    parsed_url.port or (80 if parsed_url.scheme.casefold() == "http" else 443),
                )
                if parsed_url is not None and parsed_url.hostname
                else None
            )
            if (
                not isinstance(manifest_route, dict)
                or set(manifest_route) != {
                    "key", "url", "mapped_reference_rank", "mapped_reference_id",
                    "mapped_reference_observation", "mapped_reference_sha256", "states",
                }
                or not isinstance(manifest_route.get("key"), str)
                or ID_PATTERN.fullmatch(manifest_route["key"]) is None
                or manifest_route["key"] in manifest_routes
                or not isinstance(manifest_route.get("url"), str)
                or parsed_url is None
                or parsed_url.scheme not in {"http", "https"}
                or not parsed_url.hostname
                or parsed_url.username is not None
                or parsed_url.password is not None
                or bool(parsed_url.query)
                or bool(parsed_url.fragment)
                or normalized_path is None
                or normalized_origin is None
                or (normalized_origin, normalized_path) in manifest_urls
            ):
                raise AuditError(
                    "route-manifest-invalid",
                    f"Authoritative route-manifest row {manifest_index + 1} is invalid or duplicated.",
                )
            source_errors: list[dict[str, str]] = []
            source_mapping_field(
                {
                    "rank": manifest_route.get("mapped_reference_rank"),
                    "id": manifest_route.get("mapped_reference_id"),
                    "observation": manifest_route.get("mapped_reference_observation"),
                    "sha256": manifest_route.get("mapped_reference_sha256"),
                },
                f"$.route_manifest.routes[{manifest_index}].source_mapping",
                source_errors,
            )
            if source_errors:
                raise AuditError("route-manifest-invalid", source_errors[0]["message"])
            states = manifest_route.get("states")
            if not isinstance(states, list) or not states:
                raise AuditError("route-manifest-invalid", f"Authoritative route {manifest_route['key']!r} has no source-mapped states.")
            state_ids: set[str] = set()
            mapped_state_ids: set[str] = set()
            for state_index, state in enumerate(states):
                if (
                    not isinstance(state, dict)
                    or set(state) != {"id", "kind", "trigger", "expectation", "mapped_reference_state_id"}
                    or not isinstance(state.get("id"), str)
                    or ID_PATTERN.fullmatch(state["id"]) is None
                    or state["id"] in state_ids
                    or state.get("kind") not in MANIFEST_STATE_KINDS
                    or not isinstance(state.get("trigger"), dict)
                    or set(state["trigger"]) != {"type", "target", "value"}
                    or state["trigger"].get("type") not in MANIFEST_TRIGGER_TYPES
                    or not isinstance(state["trigger"].get("target"), str)
                    or not state["trigger"]["target"].strip()
                    or not (state["trigger"].get("value") is None or isinstance(state["trigger"].get("value"), str))
                    or not isinstance(state.get("expectation"), str)
                    or len(state["expectation"].strip()) < 12
                    or not isinstance(state.get("mapped_reference_state_id"), str)
                    or MANIFEST_STATE_ID_PATTERN.fullmatch(state["mapped_reference_state_id"]) is None
                    or (state["id"] != "rest" and state.get("kind") == "rest")
                ):
                    raise AuditError(
                        "route-manifest-invalid",
                        f"Authoritative route {manifest_route['key']!r} state row {state_index + 1} is invalid, duplicated, or underspecified.",
                    )
                state_ids.add(state["id"])
                mapped_state_ids.add(state["mapped_reference_state_id"])
            if states[0] != {
                "id": "rest",
                "kind": "rest",
                "trigger": {"type": "none", "target": "document", "value": None},
                "expectation": "initial settled route",
                "mapped_reference_state_id": "rest",
            }:
                raise AuditError("route-manifest-invalid", f"Authoritative route {manifest_route['key']!r} must begin with the exact canonical rest state.")
            manifest_routes[manifest_route["key"]] = manifest_route
            manifest_state_ids[manifest_route["key"]] = mapped_state_ids
            manifest_urls.add((normalized_origin, normalized_path))
            manifest_origins.add(normalized_origin)
        if len(manifest_origins) != 1:
            raise AuditError("route-manifest-invalid", "Every authoritative route must share one exact build origin.")
    except (AuditError, OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        code = exc.code if isinstance(exc, AuditError) else "route-manifest-unreadable"
        errors.append(error_item("$.route_manifest", code, str(exc)))

    contract_routes = {
        str(route.get("id")): route
        for route in routes
        if isinstance(route.get("id"), str)
    }
    if manifest_routes and set(contract_routes) != set(manifest_routes):
        errors.append(error_item(
            "$.routes",
            "route-manifest-coverage-mismatch",
            "Route-family routes must equal every authoritative route-manifest key; sampled or producer-selected coverage is forbidden.",
        ))

    observer_path = Path(__file__).with_name("observe_reference.mjs")
    try:
        observer_sha256 = sha256_bytes(stable_bytes(observer_path, MAX_SOURCE_FILE_BYTES))
        structure_sha256 = sha256_bytes(stable_bytes(Path(__file__).with_name("structure_probe.mjs"), MAX_SOURCE_FILE_BYTES))
        browser_evidence_sha256 = sha256_bytes(stable_bytes(Path(__file__).with_name("browser_evidence.mjs"), MAX_SOURCE_FILE_BYTES))
        resolver_sha256 = sha256_bytes(stable_bytes(Path(__file__).with_name("playwright_resolver.mjs"), MAX_SOURCE_FILE_BYTES))
    except OSError as exc:
        errors.append(error_item("$.routes", "observer-runtime-unreadable", str(exc)))
        observer_sha256 = None
        structure_sha256 = None
        browser_evidence_sha256 = None
        resolver_sha256 = None

    for index, route in enumerate(routes):
        mapping = route.get("source_mapping")
        if not isinstance(mapping, dict):
            continue
        route_id = route.get("id")
        manifested = manifest_routes.get(str(route_id))
        if isinstance(manifested, dict):
            raw_expected_path = urlsplit(str(manifested.get("url") or "")).path or "/"
            expected_path = normalize_route_path(raw_expected_path)
            expected_mapping = {
                "rank": manifested.get("mapped_reference_rank"),
                "id": manifested.get("mapped_reference_id"),
                "observation": manifested.get("mapped_reference_observation"),
                "sha256": manifested.get("mapped_reference_sha256"),
            }
            if expected_path is None or route.get("path") != expected_path or mapping != expected_mapping:
                errors.append(error_item(
                    f"$.routes[{index}]",
                    "route-manifest-binding-mismatch",
                    "Route path and selected observation must exactly equal the authoritative manifest row.",
                ))
        relative = mapping.get("observation")
        digest = mapping.get("sha256")
        if not isinstance(relative, str) or not isinstance(digest, str):
            continue
        candidate = canonical(root.joinpath(*relative.split("/")))
        label = f"$.routes[{index}].source_mapping"
        try:
            ensure_no_reparse_ancestors(candidate, root)
            if not contained(candidate, root) or not candidate.is_file() or is_reparse(candidate):
                raise AuditError("reference-observation-missing", "Mapped reference observation is not an ordinary in-project file.")
            raw = stable_bytes(candidate, MAX_SOURCE_FILE_BYTES)
            if sha256_bytes(raw) != digest:
                raise AuditError("reference-observation-drift", "Mapped reference observation bytes do not match source_sha256.")
            payload = json.loads(raw.decode("utf-8"))
            if (
                not isinstance(payload, dict)
                or payload.get("tool") != "observe_reference.mjs"
                or type(payload.get("schema_version")) is not int
                or payload["schema_version"] < 5
                or observer_sha256 is None
                or payload.get("producer_script_sha256") != observer_sha256
                or structure_sha256 is None
                or browser_evidence_sha256 is None
                or resolver_sha256 is None
                or not isinstance(payload.get("runtime_identity"), dict)
                or payload["runtime_identity"].get("observe_reference.mjs") != observer_sha256
                or payload["runtime_identity"].get("structure_probe.mjs") != structure_sha256
                or payload["runtime_identity"].get("browser_evidence.mjs") != browser_evidence_sha256
                or payload["runtime_identity"].get("playwright_resolver.mjs") != resolver_sha256
            ):
                raise AuditError("reference-observation-invalid", "Mapped reference observation is not a current observer record.")
            if payload.get("id") != mapping.get("id"):
                raise AuditError("reference-observation-id-mismatch", "Mapped reference id does not equal the observation payload id.")
            match = re.match(r"strong-([1-9][0-9]*)", str(payload.get("id") or ""))
            if match is None or int(match.group(1)) != mapping.get("rank"):
                raise AuditError("reference-observation-rank-mismatch", "Mapped rank does not equal the observation payload identity.")
            observed[digest] = payload
        except (AuditError, OSError, UnicodeError, json.JSONDecodeError) as exc:
            code = exc.code if isinstance(exc, AuditError) else "reference-observation-unreadable"
            errors.append(error_item(label, code, str(exc)))
            continue
        for component_index, component in enumerate(route.get("component_sources") or []):
            if not isinstance(component, dict):
                continue
            state_id = component.get("source_state_id")
            states = payload.get("states_by_viewport")
            if state_id not in manifest_state_ids.get(str(route_id), set()):
                errors.append(error_item(
                    f"$.routes[{index}].component_sources[{component_index}].source_state_id",
                    "unmanifested-reference-state",
                    "Every component must bind a source state explicitly mapped by this authoritative route.",
                ))
            elif not isinstance(states, dict) or any(
                not isinstance(states.get(profile), dict) or state_id not in states[profile]
                for profile in ("wide", "narrow")
            ):
                errors.append(error_item(
                    f"$.routes[{index}].component_sources[{component_index}].source_state_id",
                    "reference-state-missing",
                    "Every component source state must exist in both wide and narrow observation evidence.",
                ))
        for decision_index, decision in enumerate(route.get("observable_decisions") or []):
            if not isinstance(decision, dict):
                continue
            state_id = decision.get("source_state_id")
            states = payload.get("states_by_viewport")
            if state_id not in manifest_state_ids.get(str(route_id), set()):
                errors.append(error_item(
                    f"$.routes[{index}].observable_decisions[{decision_index}].source_state_id",
                    "unmanifested-reference-state",
                    "Every visible decision must bind a source state explicitly mapped by this authoritative route.",
                ))
            elif not isinstance(states, dict) or any(
                not isinstance(states.get(profile), dict) or state_id not in states[profile]
                for profile in ("wide", "narrow")
            ):
                errors.append(error_item(
                    f"$.routes[{index}].observable_decisions[{decision_index}].source_state_id",
                    "reference-state-missing",
                    "Every visible decision source state must exist in both wide and narrow observation evidence.",
                ))
    return errors


def normalize_route_path(value: str) -> Optional[str]:
    """Return a safe comparison path without changing route semantics.

    Case, Unicode, underscores, filename extensions, and the declared trailing
    slash are significant. Percent-encoded UTF-8 is decoded only so equivalent
    capture URLs and declared IRIs compare consistently. Encoded separators,
    queries, fragments, traversal, controls, and whitespace fail closed.
    """

    if not isinstance(value, str) or not value or len(value) > 2048:
        return None
    if INVALID_PERCENT_PATTERN.search(value):
        return None
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        return None
    raw_path = parsed.path
    if not raw_path.startswith("/") or "//" in raw_path:
        return None
    decoded_segments: list[str] = []
    for raw_segment in raw_path.split("/"):
        try:
            decoded = unquote_to_bytes(raw_segment).decode("utf-8", "strict")
        except UnicodeDecodeError:
            return None
        decoded = unicodedata.normalize("NFC", decoded)
        if decoded in {".", ".."}:
            return None
        if any(
            character in "/\\?#"
            or ord(character) <= 0x1F
            or ord(character) == 0x7F
            or character.isspace()
            for character in decoded
        ):
            return None
        decoded_segments.append(decoded)
    normalized = "/".join(decoded_segments)
    if not normalized.startswith("/") or "//" in normalized:
        return None
    return normalized


def filesystem_key(value: str) -> str:
    """Match the audited host filesystem without rewriting reported routes."""

    return os.path.normcase(value.replace("\\", "/"))


def route_segments(route_path: str) -> tuple[str, ...]:
    return tuple(part for part in route_path.strip("/").split("/") if part)


def candidate_paths(route_path: str) -> list[tuple[int, str, str]]:
    segments = route_segments(route_path)
    joined = "/".join(segments)
    candidates: list[tuple[int, str, str]] = []
    for base in ("src/pages",):
        if not segments:
            candidates.append((10, "astro", f"{base}/index.astro"))
        else:
            candidates.extend(
                [
                    (10, "astro", f"{base}/{joined}.astro"),
                    (10, "astro", f"{base}/{joined}/index.astro"),
                ]
            )
    for base in ("app", "src/app"):
        page = "/".join((*segments, "page")) if segments else "page"
        for extension in (".js", ".jsx", ".mdx", ".ts", ".tsx"):
            candidates.append((10, "next-app", f"{base}/{page}{extension}"))
    for base in ("pages", "src/pages"):
        stem = f"{joined}/index" if segments else "index"
        alternate = joined if segments else None
        for extension in (".js", ".jsx", ".mdx", ".ts", ".tsx"):
            candidates.append((10, "next-pages", f"{base}/{stem}{extension}"))
            if alternate:
                candidates.append(
                    (10, "next-pages", f"{base}/{alternate}{extension}")
                )
    page = "/".join((*segments, "+page.svelte")) if segments else "+page.svelte"
    candidates.append((10, "sveltekit", f"src/routes/{page}"))
    for base in ("pages",):
        stem = f"{joined}/index" if segments else "index"
        alternate = joined if segments else None
        candidates.append((10, "nuxt", f"{base}/{stem}.vue"))
        if alternate:
            candidates.append((10, "nuxt", f"{base}/{alternate}.vue"))
    remix_stem = ".".join(segments) if segments else "_index"
    for extension in (".js", ".jsx", ".ts", ".tsx"):
        candidates.append((10, "remix", f"app/routes/{remix_stem}{extension}"))
        if segments:
            candidates.append(
                (10, "remix", f"app/routes/{remix_stem}._index{extension}")
            )
    static_roots = (
        (20, ""),
        (20, "site"),
        (30, "public"),
        (40, "dist"),
        (40, "build"),
        (40, "out"),
    )
    for priority, base in static_roots:
        prefix = f"{base}/" if base else ""
        if segments:
            if route_path.endswith("/"):
                candidates.extend(
                    (priority, "static-html", f"{prefix}{joined}/{index_name}")
                    for index_name in ("index.html", "index.htm")
                )
            elif Path(joined).suffix.casefold() in HTML_SUFFIXES:
                candidates.append((priority, "static-html", f"{prefix}{joined}"))
        else:
            candidates.extend(
                (priority, "static-html", f"{prefix}{index_name}")
                for index_name in ("index.html", "index.htm")
            )
    unique: dict[tuple[str, str], tuple[int, str, str]] = {}
    for record in candidates:
        key = (record[1], filesystem_key(record[2]))
        unique.setdefault(key, record)
    return list(unique.values())


def enumerate_source_files(
    root: Path,
    budget: Budget,
) -> dict[str, Path]:
    files: dict[str, Path] = {}

    def on_error(error: OSError) -> None:
        raise AuditError("project-enumeration-failed", str(error))

    for current, directories, names in os.walk(
        root,
        topdown=True,
        followlinks=False,
        onerror=on_error,
    ):
        current_path = Path(current)
        filtered: list[str] = []
        for name in sorted(directories):
            budget.entry()
            child = current_path / name
            if name in IGNORED_DIRS or is_reparse(child):
                continue
            filtered.append(name)
        directories[:] = filtered
        for name in sorted(names):
            budget.entry()
            path = current_path / name
            if path.suffix.casefold() not in SOURCE_SUFFIXES:
                continue
            if is_reparse(path) or not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            files[filesystem_key(relative)] = path
    return files


def source_text(
    path: Path,
    root: Path,
    budget: Budget,
    cache: dict[Path, str],
) -> str:
    if path in cache:
        return cache[path]
    ensure_no_reparse_ancestors(path, root)
    size = path.stat().st_size
    budget.source(size)
    raw = stable_bytes(path, MAX_SOURCE_FILE_BYTES)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditError(
            "source-not-utf8",
            "A required route source file is not valid UTF-8.",
        ) from exc
    cache[path] = text
    return text


def route_from_static(relative: str, base: str) -> Optional[str]:
    prefix = f"{base}/" if base else ""
    if not relative.casefold().startswith(prefix.casefold()):
        return None
    local = relative[len(prefix) :]
    if Path(local).suffix.casefold() not in HTML_SUFFIXES:
        return None
    if local.casefold() in {"404.htm", "404.html"}:
        return None
    if local.casefold().endswith(("/index.html", "/index.htm")):
        local = local[: local.rfind("/") + 1]
    elif local.casefold() in {"index.htm", "index.html"}:
        local = ""
    return normalize_route_path("/" + local)


def static_route_from_parts(parts: tuple[str, ...]) -> Optional[str]:
    if any(
        not part
        or part.startswith(("[", "$", "_"))
        or "[" in part
        or "]" in part
        for part in parts
    ):
        return None
    return normalize_route_path("/" + "/".join(parts) + "/")


def discover_routes(files: dict[str, Path], root: Path) -> tuple[set[str], set[str], list[str]]:
    discovered: set[str] = set()
    stacks: set[str] = set()
    limitations: set[str] = set()
    for path in files.values():
        relative = path.relative_to(root).as_posix()
        lower = relative.casefold()
        for base in ("", "site", "public", "dist", "build", "out"):
            route = route_from_static(relative, base)
            if route is not None:
                discovered.add(route)
                stacks.add("static-html")
                break
        parts = tuple(Path(relative).parts)
        if lower.startswith("src/pages/") and lower.endswith(".astro"):
            local = list(parts[2:])
            local[-1] = Path(local[-1]).stem
            if local[-1] == "index":
                local.pop()
            route = static_route_from_parts(tuple(local))
            if route:
                discovered.add(route)
                stacks.add("astro")
            else:
                limitations.add(
                    "Dynamic Astro route parameters are not expanded into invented concrete paths."
                )
        for base_parts, stack, page_name in (
            (("app",), "next-app", "page"),
            (("src", "app"), "next-app", "page"),
            (("src", "routes"), "sveltekit", "+page"),
        ):
            if parts[: len(base_parts)] != base_parts:
                continue
            if Path(parts[-1]).stem != page_name:
                continue
            local = parts[len(base_parts) : -1]
            route = static_route_from_parts(tuple(local))
            if route:
                discovered.add(route)
                stacks.add(stack)
            else:
                limitations.add(
                    f"Dynamic {stack} route parameters are not expanded into invented concrete paths."
                )
        for base_parts, stack in (
            (("pages",), "next-pages"),
            (("src", "pages"), "next-pages"),
        ):
            if parts[: len(base_parts)] != base_parts:
                continue
            if Path(parts[-1]).suffix.casefold() not in {
                ".js",
                ".jsx",
                ".mdx",
                ".ts",
                ".tsx",
            }:
                continue
            local = list(parts[len(base_parts) :])
            local[-1] = Path(local[-1]).stem
            if local[-1] == "index":
                local.pop()
            route = static_route_from_parts(tuple(local))
            if route:
                discovered.add(route)
                stacks.add(stack)
        if parts[:1] == ("pages",) and lower.endswith(".vue"):
            local = list(parts[1:])
            local[-1] = Path(local[-1]).stem
            if local[-1] == "index":
                local.pop()
            route = static_route_from_parts(tuple(local))
            if route:
                discovered.add(route)
                stacks.add("nuxt")
        if parts[:2] == ("app", "routes") and Path(parts[-1]).suffix.casefold() in {
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
        }:
            stem = Path(parts[-1]).stem
            if stem == "_index":
                local_parts: tuple[str, ...] = ()
            else:
                local_parts = tuple(
                    part for part in stem.removesuffix("._index").split(".") if part
                )
            route = static_route_from_parts(local_parts)
            if route:
                discovered.add(route)
                stacks.add("remix")
    return discovered, stacks, sorted(limitations)


def detect_redirect(text: str) -> Optional[str]:
    for match in META_REFRESH_PATTERN.finditer(text):
        content = html.unescape(match.group("content"))
        target_match = re.search(r"(?:^|;)\s*url\s*=\s*(.+?)\s*$", content, re.I)
        if target_match:
            target = target_match.group(1).strip(" \"'")
            normalized = normalize_route_path(target)
            if normalized:
                return normalized
    for pattern in (CODE_REDIRECT_PATTERN, LOCATION_ASSIGNMENT_PATTERN):
        match = pattern.search(text)
        if match:
            normalized = normalize_route_path(html.unescape(match.group("target")))
            if normalized:
                return normalized
    return None


def resolve_routes(
    root: Path,
    contract_routes: list[dict[str, object]],
    files: dict[str, Path],
    discovered: set[str],
    stacks: set[str],
    discovery_limitations: list[str],
    budget: Budget,
    cache: dict[Path, str],
) -> dict[str, object]:
    records: list[dict[str, object]] = []
    chosen_by_file: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    chosen_file_labels: dict[str, str] = {}
    for route in contract_routes:
        route_id = str(route["id"])
        path = str(route["path"])
        matches: list[tuple[int, str, Path]] = []
        for priority, kind, relative in candidate_paths(path):
            candidate = files.get(filesystem_key(relative))
            if candidate is not None:
                matches.append((priority, kind, candidate))
        if not matches:
            records.append(
                {
                    "id": route_id,
                    "path": path,
                    "status": "missing",
                    "resolution_kind": "unknown",
                    "source_path": None,
                    "alternative_paths": [],
                    "redirect_target": None,
                    "discovered": path in discovered,
                }
            )
            continue
        minimum = min(record[0] for record in matches)
        preferred = [record for record in matches if record[0] == minimum]
        preferred.sort(key=lambda item: item[2].relative_to(root).as_posix().casefold())
        chosen = preferred[0]
        alternatives = [
            portable_project_path(item[2], root) for item in preferred[1:]
        ]
        source_path = portable_project_path(chosen[2], root)
        redirect_target = detect_redirect(
            source_text(chosen[2], root, budget, cache)
        )
        status = (
            "redirect"
            if redirect_target is not None
            else "ambiguous"
            if alternatives
            else "resolved"
        )
        record = {
            "id": route_id,
            "path": path,
            "status": status,
            "resolution_kind": chosen[1],
            "source_path": source_path,
            "alternative_paths": alternatives,
            "redirect_target": redirect_target,
            "discovered": path in discovered,
        }
        records.append(record)
        destination_key = filesystem_key(source_path)
        chosen_by_file[destination_key].append(record)
        chosen_file_labels.setdefault(destination_key, source_path)
    duplicates: list[dict[str, object]] = []
    for destination, members in sorted(chosen_by_file.items()):
        if len(members) < 2:
            continue
        duplicates.append(
            {
                "destination": chosen_file_labels[destination],
                "route_ids": sorted(str(item["id"]) for item in members),
                "paths": sorted(str(item["path"]) for item in members),
            }
        )
    declared_paths = {str(route["path"]) for route in contract_routes}
    return {
        "detected_stacks": sorted(stacks),
        "declared_count": len(contract_routes),
        "discovered_count": len(discovered),
        "routes": records,
        "discovered_paths": sorted(discovered),
        "undeclared_paths": sorted(discovered - declared_paths),
        "duplicate_destinations": duplicates,
        "limitations": discovery_limitations
        + [
            "Resolution recognizes conventional static, Astro, Next, SvelteKit, Nuxt, and Remix file routes; custom routers require manual verification.",
            "A source route and its built output are treated as one route by precedence rather than as duplicate destinations.",
        ],
    }


def route_asset_exists(
    target_path: str,
    source_file: Path,
    root: Path,
) -> bool:
    parsed = urlsplit(target_path)
    raw = unquote(parsed.path)
    candidates: list[Path] = []
    if raw.startswith("/"):
        stripped = raw.lstrip("/")
        for base in (root, root / "public", root / "site"):
            candidates.append(base / stripped)
    else:
        candidates.append(source_file.parent / raw)
    for candidate in candidates:
        resolved = canonical(candidate)
        if contained(resolved, root) and resolved.is_file() and not is_reparse(resolved):
            return True
    return False


def normalized_link_target(source_route: str, href: str) -> Optional[str]:
    joined = urljoin(f"https://design-dna.invalid{source_route}", href)
    parsed = urlsplit(joined)
    return normalize_route_path(parsed.path)


def build_link_graph(
    root: Path,
    contract_routes: list[dict[str, object]],
    resolution: dict[str, object],
    discovered_paths: set[str],
    budget: Budget,
    cache: dict[Path, str],
) -> dict[str, object]:
    declared_paths = {str(item["path"]): str(item["id"]) for item in contract_routes}
    edges: list[dict[str, object]] = []
    broken: list[dict[str, object]] = []
    external_links = 0
    dynamic_links = 0
    resolved_records = resolution.get("routes", [])
    static_only = bool(resolved_records) and all(
        isinstance(item, dict)
        and item.get("resolution_kind") == "static-html"
        and item.get("status") in {"resolved", "redirect"}
        for item in resolved_records
    )
    for record in resolved_records:
        if not isinstance(record, dict):
            continue
        source_path = record.get("source_path")
        route_id = record.get("id")
        route_path = record.get("path")
        if not all(isinstance(value, str) for value in (source_path, route_id, route_path)):
            continue
        source_file = root / source_path
        text = source_text(source_file, root, budget, cache)
        for match in HREF_PATTERN.finditer(text):
            href = html.unescape(match.group("value")).strip()
            if not href or href.startswith("#"):
                continue
            if DYNAMIC_LINK_PATTERN.search(href):
                dynamic_links += 1
                continue
            parsed = urlsplit(href)
            if parsed.scheme in {"http", "https"} or parsed.netloc:
                external_links += 1
                continue
            if parsed.scheme in {"mailto", "tel", "sms"}:
                external_links += 1
                continue
            if parsed.scheme:
                dynamic_links += 1
                continue
            raw_path = unquote(parsed.path)
            suffix = Path(raw_path).suffix.casefold()
            if suffix and suffix not in {".html", ".htm"}:
                if not route_asset_exists(href, source_file, root):
                    broken.append(
                        {
                            "source_route_id": route_id,
                            "href": href[:2000],
                            "target_path": route_path,
                            "evidence": source_path,
                        }
                    )
                continue
            target = normalized_link_target(route_path, href)
            if target is None:
                dynamic_links += 1
                continue
            edge = {
                "source_route_id": route_id,
                "target_path": target,
                "href": href[:2000],
                "evidence": source_path,
            }
            if edge not in edges:
                edges.append(edge)
            if target not in declared_paths and target not in discovered_paths:
                broken.append(
                    {
                        "source_route_id": route_id,
                        "href": href[:2000],
                        "target_path": target,
                        "evidence": source_path,
                    }
                )
    incoming: defaultdict[str, set[str]] = defaultdict(set)
    for edge in edges:
        target_id = declared_paths.get(str(edge["target_path"]))
        if target_id and target_id != edge["source_route_id"]:
            incoming[target_id].add(str(edge["source_route_id"]))
    orphans = [
        {
            "route_id": str(route["id"]),
            "path": str(route["path"]),
            "evidence_status": (
                "confirmed-static-markup"
                if static_only
                else "candidate-framework-source"
            ),
        }
        for route in contract_routes
        if route["path"] != "/" and not incoming.get(str(route["id"]))
    ]
    basis = (
        "not-available"
        if not any(
            isinstance(item, dict) and item.get("source_path")
            for item in resolved_records
        )
        else "resolved-static-source"
        if static_only
        else "mixed-source-advisory"
    )
    limitations = [
        "Only literal href and to attributes in resolved route files are evaluated; runtime-generated links remain manual evidence.",
        "Framework layout and component composition can make orphan findings advisory even when a shared navigator exists at runtime.",
    ]
    return {
        "basis": basis,
        "edges": sorted(
            edges,
            key=lambda item: (
                str(item["source_route_id"]),
                str(item["target_path"]),
                str(item["href"]),
            ),
        ),
        "broken_links": sorted(
            broken,
            key=lambda item: (
                str(item["source_route_id"]),
                str(item["href"]),
            ),
        ),
        "orphaned_routes": orphans,
        "external_links": external_links,
        "dynamic_links_skipped": dynamic_links,
        "limitations": limitations,
    }


def external_evidence_path(path: Path, digest: str) -> str:
    suffix = path.suffix.casefold().lstrip(".") or "bin"
    return f"external/{path.stem[:32]}-{digest[:16]}.{suffix}"


def evidence_path(path: Path, root: Path, digest: str) -> str:
    candidate = canonical(path)
    if contained(candidate, root):
        return portable_project_path(candidate, root)
    return external_evidence_path(candidate, digest)


def safe_render_screenshot(
    report_path: Path,
    screenshot: object,
    root: Path,
) -> tuple[Optional[Path], Optional[dict[str, str]]]:
    if not isinstance(screenshot, dict):
        return None, None
    relative = screenshot.get("path")
    expected = screenshot.get("sha256")
    if not isinstance(relative, str) or not isinstance(expected, str):
        return None, None
    pure = Path(relative)
    if pure.is_absolute() or ".." in pure.parts or "\\" in relative:
        return None, None
    candidate = canonical(report_path.parent / pure)
    report_root = canonical(report_path.parent)
    if not contained(candidate, report_root):
        return None, None
    try:
        raw = stable_bytes(candidate, 25_165_824)
    except AuditError:
        return None, None
    actual = sha256_bytes(raw)
    if actual != expected:
        return None, None
    return candidate, {
        "path": evidence_path(candidate, root, actual),
        "sha256": actual,
    }


def load_render_reports(
    paths: list[Path],
    root: Path,
    budget: Budget,
) -> tuple[list[dict[str, object]], list[dict[str, str]], list[str]]:
    reports: list[dict[str, object]] = []
    evidence: list[dict[str, str]] = []
    limitations: list[str] = []
    seen: set[Path] = set()
    render_schema = load_render_report_schema()
    for raw_path in paths:
        path = canonical(raw_path)
        if path in seen:
            continue
        seen.add(path)
        if not path.is_file() or is_reparse(path):
            raise AuditError(
                "render-report-missing",
                "A rendered-review report is missing or not an ordinary file.",
            )
        size = path.stat().st_size
        budget.render_report(size)
        raw = stable_bytes(path, MAX_RENDER_REPORT_BYTES)
        digest = sha256_bytes(raw)
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuditError(
                "render-report-invalid-json",
                "A rendered-review report is not valid UTF-8 JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise AuditError(
                "render-report-invalid",
                "A rendered-review report must contain an object.",
            )
        contract_errors = _schema_instance_errors(
            payload,
            render_schema,
            render_schema,
        )
        if contract_errors:
            raise AuditError(
                "render-report-contract-invalid",
                "A rendered-review report failed the complete bundled schema-3 "
                "contract: " + "; ".join(contract_errors[:3]) + ".",
            )
        evidence_record = {
            "path": evidence_path(path, root, digest),
            "sha256": digest,
        }
        evidence.append(evidence_record)
        reports.append(
            {
                "path": path,
                "evidence": evidence_record,
                "payload": payload,
            }
        )
    if not reports:
        limitations.append(
            "No rendered-review report was supplied, so viewport coverage and silhouette aggregation are unavailable."
        )
    return reports, evidence, limitations


def capture_route_path(capture: dict[str, object]) -> Optional[str]:
    for field in ("final_url", "requested_url"):
        value = capture.get(field)
        if isinstance(value, str):
            parsed = urlsplit(value)
            normalized = normalize_route_path(parsed.path)
            if normalized is not None:
                return normalized
    return None


def build_rendered_coverage(
    root: Path,
    contract_routes: list[dict[str, object]],
    reports: list[dict[str, object]],
    report_evidence: list[dict[str, str]],
    base_limitations: list[str],
) -> tuple[
    dict[str, object],
    dict[tuple[str, str], Path],
    dict[str, dict[int, dict[str, object]]],
]:
    captures_by_path_width: defaultdict[
        tuple[str, int],
        list[tuple[dict[str, object], dict[str, object], Path]],
    ] = defaultdict(list)
    for report in reports:
        payload = report["payload"]
        assert isinstance(payload, dict)
        report_path = report["path"]
        assert isinstance(report_path, Path)
        for raw_capture in payload.get("captures", []):
            if not isinstance(raw_capture, dict):
                continue
            route_path = capture_route_path(raw_capture)
            viewport = raw_capture.get("viewport")
            width = viewport.get("width") if isinstance(viewport, dict) else None
            if route_path is None or not isinstance(width, int):
                continue
            captures_by_path_width[(route_path, width)].append(
                (raw_capture, report, report_path)
            )
    requirements: list[dict[str, object]] = []
    route_records: list[dict[str, object]] = []
    atlas_images: dict[tuple[str, str], Path] = {}
    representative_captures: dict[str, dict[int, dict[str, object]]] = {}
    matched_routes = 0
    for route in contract_routes:
        route_id = str(route["id"])
        route_path = str(route["path"])
        capture_records: list[dict[str, object]] = []
        viewports = route.get("capture_requirements", {}).get("viewports", [])
        if not isinstance(viewports, list):
            viewports = []
        for viewport in viewports:
            if not isinstance(viewport, dict):
                continue
            viewport_id = str(viewport["id"])
            width = int(viewport["width"])
            requirements.append(
                {
                    "route_id": route_id,
                    "viewport_id": viewport_id,
                    "width": width,
                }
            )
            candidates = captures_by_path_width.get((route_path, width), [])
            matched: Optional[
                tuple[dict[str, object], dict[str, object], Path, dict[str, str]]
            ] = None
            incomplete = bool(candidates)
            for capture, report, report_path in candidates:
                screenshot_path, screenshot_evidence = safe_render_screenshot(
                    report_path,
                    capture.get("screenshot"),
                    root,
                )
                http_status = capture.get("http_status")
                if (
                    capture.get("capture_status") == "complete"
                    and isinstance(http_status, int)
                    and 200 <= http_status < 400
                    and screenshot_path is not None
                    and screenshot_evidence is not None
                ):
                    matched = (
                        capture,
                        report,
                        screenshot_path,
                        screenshot_evidence,
                    )
                    break
            if matched is None:
                capture_records.append(
                    {
                        "viewport_id": viewport_id,
                        "width": width,
                        "status": "incomplete" if incomplete else "missing",
                        "report": (
                            candidates[0][1]["evidence"] if candidates else None
                        ),
                        "screenshot": None,
                    }
                )
                continue
            capture, report, screenshot_path, screenshot_evidence = matched
            capture_records.append(
                {
                    "viewport_id": viewport_id,
                    "width": width,
                    "status": "matched",
                    "report": report["evidence"],
                    "screenshot": screenshot_evidence,
                }
            )
            atlas_images[(route_id, viewport_id)] = screenshot_path
            representative_captures.setdefault(route_id, {})[width] = {
                "viewport_id": viewport_id,
                "width": width,
                "capture": capture,
                "report_evidence": report["evidence"],
                "screenshot_evidence": screenshot_evidence,
            }
        statuses = {str(record["status"]) for record in capture_records}
        route_status = (
            "matched"
            if capture_records and statuses == {"matched"}
            else "incomplete"
            if "matched" in statuses or "incomplete" in statuses
            else "missing"
        )
        if route_status == "matched":
            matched_routes += 1
        route_records.append(
            {
                "route_id": route_id,
                "path": route_path,
                "status": route_status,
                "captures": capture_records,
            }
        )
    complete = bool(route_records) and matched_routes == len(route_records)
    limitations = list(base_limitations)
    if any(
        not route.get("capture_requirements", {}).get("viewports")
        for route in contract_routes
    ):
        limitations.append(
            "At least one planned route still has unresolved project-derived capture widths, so no capture requirement was inferred for that route."
        )
    limitations.append(
        "Coverage matches declared URL paths and exact viewport widths; it does not infer equivalence from nearby widths."
    )
    return (
        {
            "reports": report_evidence,
            "requirements": requirements,
            "routes": route_records,
            "matched_route_count": matched_routes,
            "complete": complete,
            "limitations": limitations,
        },
        atlas_images,
        representative_captures,
    )


def _number_bucket(value: object, step: float, *, floor: float = 0.0) -> str:
    try:
        number = max(float(value), floor)
    except (TypeError, ValueError):
        return "unknown"
    return str(int(round(number / step)))


def _count_bucket(value: object) -> str:
    try:
        count = max(int(value), 0)
    except (TypeError, ValueError):
        return "unknown"
    if count <= 2:
        return str(count)
    if count <= 4:
        return "3-4"
    if count <= 8:
        return "5-8"
    return "9+"


def _safe_count(value: object) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _display_family(value: object) -> str:
    display = str(value or "").casefold()
    if "grid" in display:
        return "grid"
    if "flex" in display:
        return "flex"
    if display in {"block", "flow-root", "list-item", "table"}:
        return "flow"
    return display or "unknown"


def normalized_silhouette(capture: dict[str, object]) -> list[str]:
    document = capture.get("document")
    raw = document.get("route_silhouette") if isinstance(document, dict) else None
    if not isinstance(raw, list):
        return []
    signature: list[str] = []
    for region, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        tag = str(item.get("tag") or "").casefold()
        role = str(item.get("role") or "").casefold()
        selector = str(item.get("selector") or "").casefold()
        shared_strip = re.search(
            (
                r"(?:^|[ >.#:\[])"
                r"(?:shared[-_])?(?:legal|sources?|credits?|attribution)"
                r"[-_](?:strip|bar|footer)"
                r"(?:$|[ >.#:\[\]])"
                r"|(?:^|[ >.#:\[])site-credits(?:$|[ >.#:\[\]])"
            ),
            selector,
        )
        if (
            tag in {"nav", "footer", "script", "style", "template"}
            or role in {"navigation", "contentinfo"}
            or re.search(r"(?:^|[ >.#])(nav|footer)(?:$|[ >.#:[\]])", selector)
            or shared_strip
        ):
            continue
        heading = "heading" if str(item.get("heading") or "").strip() else "no-heading"
        normalized_rect = item.get("normalized_rect")
        if isinstance(normalized_rect, dict):
            geometry = ":".join(
                [
                    _number_bucket(normalized_rect.get("x"), 0.1),
                    _number_bucket(normalized_rect.get("y"), 0.05),
                    _number_bucket(normalized_rect.get("width"), 0.1),
                    _number_bucket(normalized_rect.get("height"), 0.05),
                ]
            )
            display = _display_family(item.get("display"))
            columns = max(
                _safe_count(item.get("grid_column_count")),
                _safe_count(item.get("visual_column_count")),
            )
            flex_direction = (
                str(item.get("flex_direction") or "none").casefold()
                if display == "flex"
                else "none"
            )
            position = str(item.get("position") or "static").casefold()
            if position not in {"absolute", "fixed", "sticky"}:
                position = "flow"
            dominant_media = _number_bucket(
                item.get("dominant_media_area_ratio"),
                0.15,
            )
            signature.extend(
                [
                    f"r{region}:geometry:{geometry}",
                    (
                        f"r{region}:layout:{display}:columns-{_count_bucket(columns)}:"
                        f"children-{_count_bucket(item.get('direct_visible_child_count'))}:"
                        f"direction-{flex_direction}:position-{position}"
                    ),
                    (
                        f"r{region}:topology:{heading}:"
                        f"media-{_count_bucket(item.get('media_count'))}:"
                        f"controls-{_count_bucket(item.get('control_count'))}:"
                        f"dominant-media-{dominant_media}"
                    ),
                ]
            )
            continue
        signature.append(
            f"legacy:{tag or 'unknown'}|{role or 'none'}|{heading}"
        )
    return signature


def silhouette_clusters(
    contract_routes: list[dict[str, object]],
    representative: dict[str, dict[int, dict[str, object]]],
) -> dict[str, object]:
    route_records: list[dict[str, object]] = []
    signatures_by_width: defaultdict[int, dict[str, list[str]]] = defaultdict(dict)
    viewport_ids_by_width: defaultdict[int, set[str]] = defaultdict(set)
    has_signatures = False
    for route in contract_routes:
        route_id = str(route["id"])
        viewport_signatures: list[dict[str, object]] = []
        combined_signature: list[str] = []
        for width, record in sorted(representative.get(route_id, {}).items()):
            capture = record.get("capture")
            signature = normalized_silhouette(capture) if isinstance(capture, dict) else []
            if not signature:
                continue
            has_signatures = True
            viewport_id = str(record.get("viewport_id"))
            signatures_by_width[width][route_id] = signature
            viewport_ids_by_width[width].add(viewport_id)
            combined_signature.extend(
                f"w{width}:{token}" for token in signature
            )
            viewport_signatures.append(
                {
                    "viewport_id": viewport_id,
                    "width": width,
                    "report_evidence": record.get("report_evidence"),
                    "screenshot_evidence": record.get("screenshot_evidence"),
                    "signature": signature,
                }
            )
        route_records.append(
            {
                "route_id": route_id,
                "path": str(route["path"]),
                "signature": combined_signature,
                "viewport_signatures": viewport_signatures,
            }
        )
    route_ids = [str(route["id"]) for route in contract_routes]
    clusters: list[dict[str, object]] = []
    for width in sorted(signatures_by_width):
        signatures = signatures_by_width[width]
        graph: defaultdict[str, set[str]] = defaultdict(set)
        comparable_route_ids = [route_id for route_id in route_ids if route_id in signatures]
        for index, left_id in enumerate(comparable_route_ids):
            left = signatures[left_id]
            if len(left) < 2:
                continue
            for right_id in comparable_route_ids[index + 1 :]:
                right = signatures[right_id]
                if len(right) < 2:
                    continue
                ratio = difflib.SequenceMatcher(
                    a=left,
                    b=right,
                    autojunk=False,
                ).ratio()
                if ratio >= 0.82:
                    graph[left_id].add(right_id)
                    graph[right_id].add(left_id)
        observed: set[str] = set()
        for route_id in comparable_route_ids:
            if route_id in observed or route_id not in graph:
                continue
            stack = [route_id]
            group: set[str] = set()
            while stack:
                current = stack.pop()
                if current in group:
                    continue
                group.add(current)
                stack.extend(sorted(graph[current] - group))
            observed.update(group)
            ordered_group = [value for value in route_ids if value in group]
            if len(ordered_group) < 2:
                continue
            unique_signatures: list[list[str]] = []
            for member_id in ordered_group:
                signature = signatures[member_id]
                if signature not in unique_signatures:
                    unique_signatures.append(signature)
            clusters.append(
                {
                    "id": f"cluster-{len(clusters) + 1:02d}",
                    "classification": "repeated-skeleton-candidate",
                    "advisory_only": True,
                    "viewport_width": width,
                    "viewport_ids": sorted(viewport_ids_by_width[width]),
                    "route_ids": ordered_group,
                    "signatures": unique_signatures,
                }
            )
    return {
        "basis": "rendered-review" if has_signatures else "not-available",
        "normalization": (
            "visible-direct-main-children-excluding-navigation-contentinfo-"
            "and-shared-legal-source-strips; "
            "copy-font-family-palette-element-names-and-media-identity-excluded; "
            "computed-geometry-layout-topology-and-media-control-density-bucketed"
        ),
        "routes": route_records,
        "clusters": clusters,
        "manual_review_required": True,
        "limitations": [
            "A similar computed structure can be task-appropriate; every cluster is an advisory candidate requiring masked rendered comparison.",
            "Buckets intentionally ignore copy, font family, palette, media identity, and DOM tag names so cosmetic reskins remain comparable.",
            "Silhouettes are compared only at exact declared widths; a repeated narrow-screen skeleton cannot be canceled out by a different wide-screen result.",
            "The analysis cannot judge art direction, interaction quality, cultural fit, or whether deliberate similarity is useful to the audience.",
        ],
    }


def safe_output_path(raw: Path, root: Path) -> Path:
    target = canonical(raw if raw.is_absolute() else root / raw)
    if not contained(target, root):
        raise AuditError(
            "output-outside-project",
            "Output artifacts must remain inside the audited project.",
        )
    current = target.parent
    while current != root:
        if current.exists() and is_reparse(current):
            raise AuditError(
                "reparse-point-refused",
                "An output parent is a symlink, junction, or reparse point.",
            )
        current = current.parent
    if target.exists() and (not target.is_file() or is_reparse(target)):
        raise AuditError(
            "unsafe-output",
            "An output target exists but is not an ordinary, non-linked file.",
        )
    return target


def atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor: Optional[int] = None
    temporary: Optional[Path] = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.design-dna-",
            dir=path.parent,
        )
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise AuditError("output-write-failed", str(exc)) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None and temporary.exists() and not is_reparse(temporary):
            temporary.unlink()


def build_atlas(
    root: Path,
    target: Optional[Path],
    disabled: bool,
    reports_supplied: bool,
    contract_routes: list[dict[str, object]],
    atlas_images: dict[tuple[str, str], Path],
) -> dict[str, object]:
    missing = [
        f"{route['id']}:{viewport['id']}"
        for route in contract_routes
        for viewport in route.get("capture_requirements", {}).get("viewports", [])
        if (str(route["id"]), str(viewport["id"])) not in atlas_images
    ]
    base: dict[str, object] = {
        "status": "not-requested",
        "path": None,
        "sha256": None,
        "media_type": None,
        "dimensions": None,
        "image_count": 0,
        "missing": missing,
        "limitations": [],
    }
    if disabled or not reports_supplied:
        return base
    if not atlas_images:
        base["status"] = "no-eligible-screenshots"
        base["limitations"] = [
            "No hash-verified screenshot satisfied the declared route and viewport requirements."
        ]
        return base
    assert target is not None
    target = safe_output_path(target, root)
    if target.suffix.casefold() in {".htm", ".html"}:
        viewport_ids: list[str] = []
        for route in contract_routes:
            for viewport in route.get("capture_requirements", {}).get(
                "viewports",
                [],
            ):
                viewport_id = str(viewport["id"])
                if viewport_id not in viewport_ids:
                    viewport_ids.append(viewport_id)
        cells: list[str] = []
        image_count = 0
        html_missing = list(missing)
        for route in contract_routes:
            route_id = str(route["id"])
            route_title = str(route.get("title") or route_id)
            for viewport_id in viewport_ids:
                source = atlas_images.get((route_id, viewport_id))
                image_markup = (
                    '<div class="missing" role="img" '
                    'aria-label="Capture unavailable">Capture unavailable</div>'
                )
                if source is not None and contained(source, root):
                    relative_source = os.path.relpath(
                        source,
                        target.parent,
                    ).replace("\\", "/")
                    image_markup = (
                        f'<img src="{html.escape(relative_source, quote=True)}" '
                        f'alt="{html.escape(route_title, quote=True)}, '
                        f'{html.escape(viewport_id, quote=True)} capture">'
                    )
                    image_count += 1
                elif source is not None:
                    marker = f"{route_id}:{viewport_id}:outside-project"
                    if marker not in html_missing:
                        html_missing.append(marker)
                cells.append(
                    "<figure>"
                    f"{image_markup}"
                    "<figcaption>"
                    f"<strong>{html.escape(route_id)}</strong>"
                    f"<span>{html.escape(viewport_id)}</span>"
                    f"<small>{html.escape(route_title)}</small>"
                    "</figcaption>"
                    "</figure>"
                )
        document = (
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" '
            'content="default-src \'none\'; img-src \'self\'; '
            'style-src \'unsafe-inline\'; base-uri \'none\'; '
            'form-action \'none\'">'
            "<title>Design DNA route atlas</title><style>"
            ":root{color-scheme:light;font:16px/1.45 system-ui,sans-serif;"
            "background:#eeeae1;color:#171714}"
            "*{box-sizing:border-box}body{margin:0;padding:24px}"
            "header{max-width:78rem;margin:0 auto 24px}"
            "h1{margin:0 0 6px;font-size:clamp(1.75rem,4vw,3rem)}"
            "p{margin:0;max-width:70ch}"
            ".atlas{display:grid;grid-template-columns:"
            f"repeat({max(1, len(viewport_ids))},minmax(0,1fr));"
            "gap:18px;max-width:100rem;margin:auto}"
            "figure{margin:0;min-width:0;background:#fff;border:1px solid #aaa;"
            "box-shadow:0 8px 24px #0002}"
            "img,.missing{display:block;width:100%;height:280px;"
            "object-fit:contain;background:#d9d3c7}"
            ".missing{display:grid;place-items:center;color:#544f47}"
            "figcaption{display:grid;grid-template-columns:1fr auto;gap:2px 12px;"
            "padding:10px 12px;border-top:1px solid #bbb}"
            "figcaption span{font-variant-numeric:tabular-nums}"
            "figcaption small{grid-column:1/-1;color:#57534d}"
            "@media(max-width:760px){body{padding:12px}.atlas{grid-template-columns:1fr}"
            "img,.missing{height:auto;min-height:180px}}"
            "</style></head><body><header><h1>Route atlas</h1>"
            "<p>Matched route captures for comparative human review. "
            "Open the original screenshots for full-resolution evidence.</p>"
            "</header><main class=\"atlas\">"
            + "".join(cells)
            + "</main></body></html>"
        ).encode("utf-8")
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(target, document)
        digest = sha256_file(target, 50 * 1024 * 1024)
        return {
            "status": "created" if not html_missing else "incomplete",
            "path": portable_project_path(target, root),
            "sha256": digest,
            "media_type": "text/html",
            "dimensions": None,
            "image_count": image_count,
            "missing": sorted(html_missing),
            "limitations": [
                "The atlas is an orientation aid; full-resolution screenshots remain the review evidence.",
                "The HTML atlas uses only project-relative, hash-verified screenshot references.",
            ],
        }
    if target.suffix.casefold() != ".png":
        raise AuditError(
            "atlas-output-type-invalid",
            "The route atlas output must use .html, .htm, or .png.",
        )
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps  # type: ignore
    except ImportError:
        base["status"] = "pillow-unavailable"
        base["limitations"] = [
            "Pillow is optional and unavailable; screenshot coverage remains recorded but no PNG contact sheet was created."
        ]
        return base
    cell_width = 380
    cell_height = 300
    label_height = 48
    margin = 24
    viewport_ids: list[str] = []
    for route in contract_routes:
        for viewport in route.get("capture_requirements", {}).get("viewports", []):
            viewport_id = str(viewport["id"])
            if viewport_id not in viewport_ids:
                viewport_ids.append(viewport_id)
    rows = len(contract_routes)
    columns = max(1, len(viewport_ids))
    width = margin * 2 + columns * cell_width
    height = margin * 2 + rows * (cell_height + label_height)
    canvas = Image.new("RGB", (width, height), "#f2efe7")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    image_count = 0
    for row, route in enumerate(contract_routes):
        route_id = str(route["id"])
        route_title = str(route.get("title") or route_id)
        y = margin + row * (cell_height + label_height)
        for column, viewport_id in enumerate(viewport_ids):
            x = margin + column * cell_width
            draw.rectangle(
                (x, y, x + cell_width - 8, y + cell_height - 8),
                fill="#d8d2c5",
            )
            source = atlas_images.get((route_id, viewport_id))
            if source is not None:
                try:
                    with Image.open(source) as opened:
                        opened.load()
                        rendered = ImageOps.contain(
                            opened.convert("RGB"),
                            (cell_width - 20, cell_height - 20),
                        )
                except Exception:
                    rendered = None
                if rendered is not None:
                    offset_x = x + (cell_width - 8 - rendered.width) // 2
                    offset_y = y + (cell_height - 8 - rendered.height) // 2
                    canvas.paste(rendered, (offset_x, offset_y))
                    image_count += 1
            label = f"{route_id} | {viewport_id}"
            title = route_title[:54]
            draw.text((x, y + cell_height), label, fill="#191815", font=font)
            draw.text((x, y + cell_height + 16), title, fill="#514b41", font=font)
    descriptor: Optional[int] = None
    temporary: Optional[Path] = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.design-dna-",
            suffix=".png",
            dir=target.parent,
        )
        os.close(descriptor)
        descriptor = None
        temporary = Path(temporary_name)
        canvas.save(temporary, format="PNG", optimize=True)
        os.replace(temporary, target)
        temporary = None
    except OSError as exc:
        raise AuditError("atlas-write-failed", str(exc)) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None and temporary.exists() and not is_reparse(temporary):
            temporary.unlink()
    digest = sha256_file(target, 50 * 1024 * 1024)
    return {
        "status": "created" if not missing else "incomplete",
        "path": portable_project_path(target, root),
        "sha256": digest,
        "media_type": "image/png",
        "dimensions": {"width": width, "height": height},
        "image_count": image_count,
        "missing": missing,
        "limitations": [
            "The atlas is an orientation aid; full-resolution screenshots remain the review evidence."
        ],
    }


def finding(
    code: str,
    severity: str,
    blocking: bool,
    category: str,
    message: str,
    *,
    route_ids: Iterable[str] = (),
    paths: Iterable[str] = (),
    evidence: Iterable[str] = (),
) -> dict[str, object]:
    return {
        "code": code,
        "severity": severity,
        "blocking": blocking,
        "category": category,
        "route_ids": sorted(set(route_ids)),
        "paths": sorted(set(paths)),
        "message": message,
        "evidence": sorted(set(evidence)),
    }


def collect_findings(
    contract: dict[str, object],
    resolution: dict[str, object],
    links: dict[str, object],
    silhouettes: dict[str, object],
    coverage: dict[str, object],
    atlas: dict[str, object],
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    requested = contract.get("requested_route_count")
    declared = contract.get("declared_route_count")
    if requested != declared:
        findings.append(
            finding(
                "route-count-mismatch",
                "high",
                True,
                "contract",
                "The requested and declared route counts do not match.",
                paths=[str(contract["path"])],
            )
        )
    for route in resolution.get("routes", []):
        if not isinstance(route, dict):
            continue
        status = route.get("status")
        route_id = str(route.get("id"))
        route_path = str(route.get("path"))
        if status == "missing":
            findings.append(
                finding(
                    "declared-route-missing",
                    "high",
                    True,
                    "routes",
                    "A declared route has no conservative local source resolution.",
                    route_ids=[route_id],
                    paths=[route_path],
                )
            )
        elif status == "ambiguous":
            findings.append(
                finding(
                    "declared-route-ambiguous",
                    "high",
                    True,
                    "routes",
                    "Multiple same-precedence source files appear to own one route.",
                    route_ids=[route_id],
                    paths=[
                        value
                        for value in [
                            route.get("source_path"),
                            *route.get("alternative_paths", []),
                        ]
                        if isinstance(value, str)
                    ],
                )
            )
        elif status == "redirect":
            findings.append(
                finding(
                    "declared-route-is-redirect",
                    "high",
                    True,
                    "routes",
                    "A redirect cannot count as a distinct route-family page.",
                    route_ids=[route_id],
                    paths=[route_path, str(route.get("redirect_target"))],
                )
            )
    for duplicate in resolution.get("duplicate_destinations", []):
        if isinstance(duplicate, dict):
            findings.append(
                finding(
                    "duplicate-route-destination",
                    "high",
                    True,
                    "routes",
                    "Multiple declared routes resolve to the same source destination.",
                    route_ids=[str(value) for value in duplicate.get("route_ids", [])],
                    paths=[str(value) for value in duplicate.get("paths", [])],
                    evidence=[str(duplicate.get("destination"))],
                )
            )
    undeclared = resolution.get("undeclared_paths", [])
    if isinstance(undeclared, list) and undeclared:
        findings.append(
            finding(
                "undeclared-route-files",
                "medium",
                True,
                "routes",
                "Conservatively discovered route files are absent from the route-family contract.",
                paths=[str(value) for value in undeclared],
            )
        )
    for broken in links.get("broken_links", []):
        if isinstance(broken, dict):
            findings.append(
                finding(
                    "broken-local-link",
                    "high",
                    True,
                    "links",
                    "A literal local link does not resolve to a declared or discovered route/file.",
                    route_ids=[str(broken.get("source_route_id"))],
                    paths=[str(broken.get("target_path"))],
                    evidence=[str(broken.get("evidence")), str(broken.get("href"))],
                )
            )
    for orphan in links.get("orphaned_routes", []):
        if not isinstance(orphan, dict):
            continue
        confirmed = orphan.get("evidence_status") == "confirmed-static-markup"
        findings.append(
            finding(
                "orphan-route" if confirmed else "orphan-route-candidate",
                "medium" if confirmed else "low",
                confirmed,
                "links",
                (
                    "A declared route has no incoming literal link from another route."
                    if confirmed
                    else "No incoming link was found in resolved route sources; framework composition requires manual confirmation."
                ),
                route_ids=[str(orphan.get("route_id"))],
                paths=[str(orphan.get("path"))],
            )
        )
    for cluster in silhouettes.get("clusters", []):
        if isinstance(cluster, dict):
            findings.append(
                finding(
                    "repeated-route-skeleton-candidate",
                    "low",
                    False,
                    "silhouettes",
                    "Rendered main-content sequences are materially similar; compare the actual routes before deciding whether the overlap is task-derived.",
                    route_ids=[str(value) for value in cluster.get("route_ids", [])],
                    evidence=[
                        str(cluster.get("id")),
                        f"viewport-width:{cluster.get('viewport_width')}",
                    ],
                )
            )
    for route in coverage.get("routes", []):
        if not isinstance(route, dict) or route.get("status") == "matched":
            continue
        findings.append(
            finding(
                "rendered-route-coverage-incomplete",
                "medium",
                True,
                "rendered",
                "A declared route lacks one or more exact-width, complete, hash-verified rendered captures.",
                route_ids=[str(route.get("route_id"))],
                paths=[str(route.get("path"))],
                evidence=[
                    f"{capture.get('viewport_id')}:{capture.get('status')}"
                    for capture in route.get("captures", [])
                    if isinstance(capture, dict)
                    and capture.get("status") != "matched"
                ],
            )
        )
    if atlas.get("status") in {
        "pillow-unavailable",
        "no-eligible-screenshots",
        "incomplete",
    }:
        findings.append(
            finding(
                "route-atlas-incomplete",
                "low",
                False,
                "atlas",
                "A complete route atlas was not available; inspect individual screenshots and the recorded evidence status.",
                paths=[str(atlas["path"])] if atlas.get("path") else [],
                evidence=[str(atlas.get("status"))],
            )
        )
    return findings[:MAX_FINDINGS]


def empty_sections() -> dict[str, object]:
    return {
        "contract": {
            "status": "missing",
            "path": DEFAULT_CONTRACT.as_posix(),
            "sha256": None,
            "requested_route_count": None,
            "declared_route_count": 0,
            "routes": [],
            "errors": [],
        },
        "route_resolution": {
            "detected_stacks": [],
            "declared_count": 0,
            "discovered_count": 0,
            "routes": [],
            "discovered_paths": [],
            "undeclared_paths": [],
            "duplicate_destinations": [],
            "limitations": [],
        },
        "link_graph": {
            "basis": "not-available",
            "edges": [],
            "broken_links": [],
            "orphaned_routes": [],
            "external_links": 0,
            "dynamic_links_skipped": 0,
            "limitations": [],
        },
        "silhouette_analysis": {
            "basis": "not-available",
            "normalization": (
                "visible-direct-main-children-excluding-navigation-contentinfo-"
                "and-shared-legal-source-strips; "
                "copy-font-family-palette-element-names-and-media-identity-excluded; "
                "computed-geometry-layout-topology-and-media-control-density-bucketed"
            ),
            "routes": [],
            "clusters": [],
            "manual_review_required": True,
            "limitations": [],
        },
        "rendered_coverage": {
            "reports": [],
            "requirements": [],
            "routes": [],
            "matched_route_count": 0,
            "complete": False,
            "limitations": [],
        },
        "route_atlas": {
            "status": "not-requested",
            "path": None,
            "sha256": None,
            "media_type": None,
            "dimensions": None,
            "image_count": 0,
            "missing": [],
            "limitations": [],
        },
    }


def base_report(
    budget: Budget,
    *,
    execution_ok: bool,
    audit_status: str,
    error: Optional[dict[str, str]],
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": ARTIFACT_TYPE,
        "tool": {
            "name": ARTIFACT_TYPE,
            "version": TOOL_VERSION,
            "report_schema": "route-family-audit.schema.json",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execution_ok": execution_ok,
        "review_required": True,
        "automatic_aesthetic_pass": False,
        "authorship_classification": "not-performed",
        "audit_status": audit_status,
        "project": "project:/",
        **empty_sections(),
        "findings": [],
        "limitations": [
            "This deterministic audit does not detect AI use, attribute authorship, or assign an aesthetic quality score.",
            "A route can be structurally distinct and still be weak, culturally wrong, inaccessible, or visually repetitive.",
            "Literal source inspection cannot prove runtime behavior produced by custom routers, servers, data, or client-side code.",
            "Human review of full-resolution desktop and mobile renders remains required before any quality or release claim.",
        ],
        "resource_usage": budget.record(),
        "error": error,
    }


def encode_report(report: dict[str, object], budget: Budget) -> bytes:
    for _ in range(5):
        report["resource_usage"] = budget.record()
        encoded = json.dumps(report, indent=2, ensure_ascii=True).encode("utf-8")
        budget.report_bytes = len(encoded)
    encoded = json.dumps(report, indent=2, ensure_ascii=True).encode("utf-8")
    if len(encoded) > MAX_REPORT_BYTES:
        raise AuditError(
            "report-size-limit-exceeded",
            f"Audit report exceeds {MAX_REPORT_BYTES} bytes.",
        )
    return encoded


def write_optional_report(
    report: dict[str, object],
    budget: Budget,
    output: Optional[Path],
    root: Path,
) -> bytes:
    encoded = encode_report(report, budget)
    if output is not None:
        target = safe_output_path(output, root)
        atomic_write(target, encoded + b"\n")
    return encoded


def run(args: argparse.Namespace) -> tuple[dict[str, object], int, Path, Budget]:
    budget = Budget()
    root = canonical(args.project)
    if not root.is_dir() or is_reparse(root):
        report = base_report(
            budget,
            execution_ok=False,
            audit_status="execution-incomplete",
            error={
                "code": "unsafe-project",
                "message": "Project root must be an existing, ordinary directory.",
            },
        )
        return report, 2, root, budget
    contract_input = args.contract or DEFAULT_CONTRACT
    contract_path = canonical(
        contract_input if contract_input.is_absolute() else root / contract_input
    )
    try:
        ensure_no_reparse_ancestors(contract_path, root)
        contract_label = portable_project_path(contract_path, root)
        if not contract_path.is_file() or is_reparse(contract_path):
            report = base_report(
                budget,
                execution_ok=False,
                audit_status="execution-incomplete",
                error={
                    "code": "route-family-contract-missing",
                    "message": "The project has no ordinary route-family contract at the requested path.",
                },
            )
            report["contract"]["path"] = contract_label
            return report, 2, root, budget
        contract_raw = stable_bytes(contract_path, MAX_SOURCE_FILE_BYTES)
        contract_digest = sha256_bytes(contract_raw)
        try:
            contract_payload = json.loads(contract_raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            report = base_report(
                budget,
                execution_ok=True,
                audit_status="contract-invalid",
                error=None,
            )
            report["contract"] = {
                "status": "invalid",
                "path": contract_label,
                "sha256": contract_digest,
                "requested_route_count": None,
                "declared_route_count": 0,
                "routes": [],
                "errors": [
                    error_item("$", "invalid-json", f"Invalid UTF-8 JSON: {exc}.")
                ],
            }
            report["findings"] = [
                finding(
                    "route-family-contract-invalid",
                    "high",
                    True,
                    "contract",
                    "The route-family contract is not valid JSON.",
                    paths=[contract_label],
                )
            ]
            return report, 1, root, budget
        errors, contract_routes = validate_contract_payload(contract_payload)
        if not errors:
            errors.extend(reference_binding_errors(root, contract_routes))
        study = (
            contract_payload.get("study")
            if isinstance(contract_payload, dict)
            else None
        )
        requested = (
            study.get("requested_route_count") if isinstance(study, dict) else None
        )
        contract_record = {
            "status": "invalid" if errors else "loaded",
            "path": contract_label,
            "sha256": contract_digest,
            "requested_route_count": (
                requested
                if isinstance(requested, int)
                and not isinstance(requested, bool)
                and requested >= 2
                else None
            ),
            "declared_route_count": len(contract_routes),
            "routes": [
                {"id": str(route["id"]), "path": str(route["path"])}
                for route in contract_routes
            ],
            "errors": errors,
        }
        if errors:
            report = base_report(
                budget,
                execution_ok=True,
                audit_status="contract-invalid",
                error=None,
            )
            report["contract"] = contract_record
            report["findings"] = [
                finding(
                    "route-family-contract-invalid",
                    "high",
                    True,
                    "contract",
                    "The route-family contract failed its schema-3 structural or reference-binding validation.",
                    paths=[contract_label],
                    evidence=[f"{item['path']}: {item['code']}" for item in errors],
                )
            ]
            return report, 1, root, budget

        files = enumerate_source_files(root, budget)
        discovered, stacks, discovery_limitations = discover_routes(files, root)
        cache: dict[Path, str] = {}
        resolution = resolve_routes(
            root,
            contract_routes,
            files,
            discovered,
            stacks,
            discovery_limitations,
            budget,
            cache,
        )
        links = build_link_graph(
            root,
            contract_routes,
            resolution,
            discovered,
            budget,
            cache,
        )
        report_paths = [canonical(path) for path in args.render_review]
        render_reports, render_evidence, render_limitations = load_render_reports(
            report_paths,
            root,
            budget,
        )
        coverage, atlas_images, representative = build_rendered_coverage(
            root,
            contract_routes,
            render_reports,
            render_evidence,
            render_limitations,
        )
        silhouettes = silhouette_clusters(
            contract_routes,
            representative,
        )
        atlas_target = (
            None
            if args.no_atlas or not render_reports
            else canonical(args.atlas)
            if args.atlas is not None and args.atlas.is_absolute()
            else root / (args.atlas or DEFAULT_ATLAS)
        )
        atlas = build_atlas(
            root,
            atlas_target,
            args.no_atlas,
            bool(render_reports),
            contract_routes,
            atlas_images,
        )
        findings = collect_findings(
            contract_record,
            resolution,
            links,
            silhouettes,
            coverage,
            atlas,
        )
        blocking = any(item.get("blocking") is True for item in findings)
        report = base_report(
            budget,
            execution_ok=True,
            audit_status=(
                "structural-findings" if blocking else "manual-review-required"
            ),
            error=None,
        )
        report["contract"] = contract_record
        report["route_resolution"] = resolution
        report["link_graph"] = links
        report["silhouette_analysis"] = silhouettes
        report["rendered_coverage"] = coverage
        report["route_atlas"] = atlas
        report["findings"] = findings
        return report, 1 if blocking else 0, root, budget
    except AuditError as exc:
        report = base_report(
            budget,
            execution_ok=False,
            audit_status="execution-incomplete",
            error={"code": exc.code, "message": exc.message},
        )
        return report, 2, root, budget


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument(
        "--contract",
        type=Path,
        help="Project-local route-family contract (default: .design-dna/route-family.json).",
    )
    parser.add_argument(
        "--render-review",
        action="append",
        type=Path,
        default=[],
        help="Schema-3 rendered-review report; repeat for multiple reports.",
    )
    atlas_group = parser.add_mutually_exclusive_group()
    atlas_group.add_argument(
        "--atlas",
        type=Path,
        help="Project-local HTML or PNG atlas path (default with rendered evidence: .design-dna/route-atlas.html).",
    )
    atlas_group.add_argument(
        "--no-atlas",
        action="store_true",
        help="Do not attempt the optional Pillow contact sheet.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Also write the JSON report to this project-local path.",
    )
    args = parser.parse_args()
    if sys.version_info < MINIMUM_PYTHON:
        budget = Budget()
        report = base_report(
            budget,
            execution_ok=False,
            audit_status="execution-incomplete",
            error={
                "code": "python-version-unsupported",
                "message": "route_family_audit.py requires Python 3.10 or newer.",
            },
        )
        print(encode_report(report, budget).decode("utf-8"), file=sys.stderr)
        return 2
    report, returncode, root, budget = run(args)
    try:
        encoded = write_optional_report(report, budget, args.output, root)
    except AuditError as exc:
        failure = base_report(
            budget,
            execution_ok=False,
            audit_status="execution-incomplete",
            error={"code": exc.code, "message": exc.message},
        )
        encoded = encode_report(failure, budget)
        returncode = 2
    stream = sys.stdout if report.get("execution_ok") is True else sys.stderr
    print(encoded.decode("utf-8"), file=stream)
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
