#!/usr/bin/env python3
"""Safely create or validate project-local Design DNA state.

Runtime guarantees:
- requires Python 3.10 or newer and otherwise has no third-party dependencies;
- standard-library only; an installed Git CLI is queried read-only when
  restricted research state exists, with an explicit warning when unverified;
- never follows a symlink, junction, or other reparse point;
- stages the complete state before replacing anything;
- restores the prior state automatically if the final replacement fails;
- emits machine-readable errors on stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import NoReturn


STATE_SCHEMA_VERSION = 1
SEMVER = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
RECORD_TEMPLATES = {
    "direction": ("direction.md", "direction-template.md"),
    "direction-proof": ("direction-proof.md", "direction-proof-template.md"),
    "visual-review": ("visual-review.md", "visual-review-template.md"),
    "claims": ("claims.md", "claim-ledger-template.md"),
    "assets": ("assets.yml", "asset-manifest.yml"),
    "user-validation": ("user-validation.md", "user-validation-template.md"),
}
PROFILES = {
    "substantial": ("direction", "visual-review"),
    "greenfield": ("direction", "direction-proof", "visual-review"),
    "validation": ("user-validation",),
    "asset-led": ("assets",),
    "full": tuple(RECORD_TEMPLATES),
}
FRONTMATTER_FILES = {
    "claims.md", "direction.md", "direction-proof.md", "visual-review.md",
    "user-validation.md",
}
CLASSIFICATIONS = {"internal", "public", "confidential", "restricted-research"}
USER_VALIDATION_FRONTMATTER_FIELDS = {
    "research_data_owner",
    "collection_basis",
    "access_scope",
    "storage_location",
    "retention_rule",
    "deletion_owner",
    "deletion_status",
}
USER_VALIDATION_DELETION_STATUSES = {
    "pending",
    "scheduled",
    "completed",
    "de-identified",
    "not-applicable",
}
STATE_PRIVACY_IGNORE_LINES = (
    "# Design DNA privacy safeguards",
    "/user-validation.md",
    "/evidence/research/",
    "/*.[Rr][Ee][Ss][Tt][Rr][Ii][Cc][Tt][Ee][Dd].*",
)
BACKUP_PRIVACY_IGNORE_BLOCK = (
    "# BEGIN DESIGN DNA RECOVERY PRIVACY GUARD\n"
    "*\n"
    "!.gitignore\n"
    "# END DESIGN DNA RECOVERY PRIVACY GUARD\n"
)


class StateError(RuntimeError):
    """A stable, structured runtime failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        path: Path | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.details = details or {}


def error_record(error: StateError) -> dict[str, object]:
    result: dict[str, object] = {"code": error.code, "message": str(error)}
    if error.path is not None:
        result["path"] = str(error.path)
    if error.details:
        result["details"] = error.details
    return result


def emit_error(error: StateError) -> NoReturn:
    payload = {"ok": False, "error": error_record(error)}
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(2)


def entry_exists(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise StateError("path-inspection-failed", str(exc), path=path) from exc


def is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise StateError("path-inspection-failed", str(exc), path=path) from exc
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    if not attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        return False
    tag = getattr(info, "st_reparse_tag", 0)
    if tag:
        return bool(tag & 0x20000000) or tag in {0xA0000003, 0xA000000C}
    return True


def lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def assert_no_reparse_ancestors(path: Path, *, stop: Path | None = None) -> None:
    """Reject any existing path entry from path through stop, without following it."""
    candidate = lexical_absolute(path)
    stop = lexical_absolute(stop) if stop else None
    while True:
        if entry_exists(candidate) and is_reparse(candidate):
            raise StateError(
                "reparse-point-refused",
                "Symlinks, junctions, and reparse points are not accepted in a state path.",
                path=candidate,
            )
        if stop is not None and candidate == stop:
            return
        if candidate.parent == candidate:
            return
        candidate = candidate.parent


def assert_safe_tree(root: Path) -> None:
    """Inspect a tree without recursing through link-like entries."""
    if not entry_exists(root):
        return
    if is_reparse(root):
        raise StateError("reparse-point-refused", "Unsafe state directory.", path=root)
    def fail_walk(error: OSError) -> None:
        raise StateError(
            "tree-enumeration-failed",
            str(error),
            path=Path(error.filename) if error.filename else root,
        ) from error

    for current, directories, files in os.walk(
        root,
        topdown=True,
        followlinks=False,
        onerror=fail_walk,
    ):
        current_path = Path(current)
        for name in list(directories) + files:
            child = current_path / name
            if is_reparse(child):
                raise StateError(
                    "reparse-point-refused",
                    "State contains a symlink, junction, or reparse point.",
                    path=child,
                )


def assert_contained(path: Path, root: Path) -> None:
    lexical_path = lexical_absolute(path)
    lexical_root = lexical_absolute(root)
    if not is_within(lexical_path, lexical_root):
        raise StateError("path-escape", "Path escapes the selected project.", path=lexical_path)
    resolved_root = lexical_root.resolve(strict=True)
    resolved_parent = lexical_path.parent.resolve(strict=True)
    if not is_within(resolved_parent, resolved_root):
        raise StateError(
            "resolved-path-escape",
            "Resolved destination parent escapes the selected project.",
            path=lexical_path,
        )


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def unique_peer(path: Path, label: str) -> Path:
    for number in range(1, 10_000):
        suffix = "" if number == 1 else f"-{number}"
        candidate = path.with_name(f"{path.name}.{label}-{utc_stamp()}{suffix}")
        if not entry_exists(candidate):
            return candidate
    raise StateError("name-exhausted", "Unable to reserve a unique peer path.", path=path.parent)


def strict_json(text: str, *, path: Path) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise StateError(
                    "duplicate-json-key",
                    f"Duplicate JSON key {key!r}.",
                    path=path,
                )
            result[key] = value
        return result

    try:
        return json.loads(text, object_pairs_hook=reject_duplicates)
    except StateError:
        raise
    except json.JSONDecodeError as exc:
        raise StateError("invalid-json", str(exc), path=path) from exc


def read_json(path: Path) -> object:
    try:
        return strict_json(path.read_text(encoding="utf-8"), path=path)
    except StateError:
        raise
    except (OSError, UnicodeError) as exc:
        raise StateError("state-read-failed", str(exc), path=path) from exc


def release_version(skill_root: Path) -> str:
    release_path = skill_root / "release.json"
    try:
        payload = strict_json(
            release_path.read_text(encoding="utf-8"),
            path=release_path,
        )
        if not isinstance(payload, dict):
            raise StateError(
                "invalid-package-release",
                "release.json must contain a JSON object.",
                path=release_path,
            )
        if set(payload) != {"package", "version", "state_schema_version"}:
            raise StateError(
                "invalid-package-release",
                "release.json has an unsupported shape.",
                path=release_path,
            )
        if (
            payload.get("package") != "design-dna"
            or payload.get("state_schema_version") != STATE_SCHEMA_VERSION
        ):
            raise StateError(
                "invalid-package-release",
                "release.json package or state schema identity is invalid.",
                path=release_path,
            )
        version = payload.get("version")
        if not isinstance(version, str) or not SEMVER.fullmatch(version):
            raise StateError(
                "invalid-package-release",
                "release.json must contain a valid SemVer version.",
                path=release_path,
            )
        return version
    except (OSError, UnicodeError, StateError) as exc:
        detail = (
            error_record(exc)
            if isinstance(exc, StateError)
            else {
                "code": "package-release-read-failed",
                "message": str(exc),
                "path": str(release_path),
            }
        )
        raise StateError(
            "package-release-unavailable",
            "The packaged skill release metadata is missing or invalid.",
            path=release_path,
            details={"cause": detail},
        ) from exc


def state_manifest(version: str, records: tuple[str, ...]) -> str:
    return json.dumps(
        {
            "schema_version": STATE_SCHEMA_VERSION,
            "created_with": f"design-dna {version}",
            "created": date.today().isoformat(),
            "classification": "internal",
            "records": list(records),
        },
        indent=2,
    ) + "\n"


def template_text(template_root: Path, filename: str, version: str) -> str:
    path = template_root / filename
    assert_safe_tree(template_root)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StateError("template-read-failed", str(exc), path=path) from exc
    rendered = text.replace("__DESIGN_DNA_VERSION__", f"design-dna {version}")
    if "__DESIGN_DNA_VERSION__" in rendered:
        raise StateError("unresolved-template-token", "Template token was not resolved.", path=path)
    return rendered


def strict_scalar(value: str, *, field: str, path: Path) -> str:
    value = value.strip()
    if not value:
        raise StateError("invalid-yaml", f"{field} has an empty value.", path=path)
    if value[0] in {'"', "'"}:
        if len(value) < 2 or value[-1] != value[0]:
            raise StateError("invalid-yaml", f"{field} has an unterminated quote.", path=path)
        unquoted = value[1:-1]
        if not unquoted.strip():
            raise StateError("invalid-yaml", f"{field} has an empty value.", path=path)
        return unquoted
    if any(token in value for token in ("[", "]", "{", "}")):
        raise StateError("invalid-yaml", f"{field} must be a scalar.", path=path)
    return value


def parse_flat_yaml(text: str, *, path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[:1].isspace() or ":" not in line:
            raise StateError("invalid-yaml", f"Unsupported YAML at line {number}.", path=path)
        key, value = line.split(":", 1)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            raise StateError("invalid-yaml", f"Invalid key at line {number}.", path=path)
        if key in result:
            raise StateError("duplicate-yaml-key", f"Duplicate key {key!r}.", path=path)
        result[key] = strict_scalar(value, field=key, path=path)
    return result


def parse_yaml_scalar(value: str, *, line: int, path: Path) -> object:
    """Parse the deliberately small scalar subset used by assets.yml."""
    value = value.strip()
    if not value:
        raise StateError(
            "invalid-yaml",
            f"Missing scalar value at line {line}.",
            path=path,
        )
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if value in {"true", "false"}:
        return value == "true"
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)", value):
        return int(value)
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise StateError(
                "invalid-yaml",
                f"Invalid double-quoted string at line {line}: {exc}",
                path=path,
            ) from exc
        if not isinstance(parsed, str):
            raise StateError(
                "invalid-yaml",
                f"Only quoted strings are supported at line {line}.",
                path=path,
            )
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise StateError(
                "invalid-yaml",
                f"Unterminated single-quoted string at line {line}.",
                path=path,
            )
        return value[1:-1].replace("''", "'")
    if value[0] in "-?:,[]{}#&*!|>@`" or " #" in value:
        raise StateError(
            "invalid-yaml",
            f"Unsupported plain scalar at line {line}; quote this value.",
            path=path,
        )
    return value


def parse_strict_yaml_subset(text: str, *, path: Path) -> object:
    """Parse block maps/lists without tags, aliases, merging, or implicit coercions.

    This is intentionally not a general YAML parser. It accepts the block-style,
    two-space-indented subset emitted by the bundled asset template and rejects
    syntax whose meaning would require YAML's complex type system.
    """
    tokens: list[tuple[int, int, str]] = []
    for number, raw_line in enumerate(text.splitlines(), 1):
        if "\t" in raw_line:
            raise StateError(
                "invalid-yaml",
                f"Tabs are not allowed at line {number}.",
                path=path,
            )
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indentation = len(raw_line) - len(raw_line.lstrip(" "))
        if indentation % 2:
            raise StateError(
                "invalid-yaml",
                f"Indentation must use two-space steps at line {number}.",
                path=path,
            )
        content = raw_line[indentation:]
        if content in {"---", "..."}:
            raise StateError(
                "invalid-yaml",
                f"YAML document markers are not supported at line {number}.",
                path=path,
            )
        tokens.append((number, indentation, content))
    if not tokens:
        raise StateError("invalid-yaml", "YAML document is empty.", path=path)

    index = 0

    def split_mapping(content: str, number: int) -> tuple[str, str]:
        if ":" not in content:
            raise StateError(
                "invalid-yaml",
                f"Expected a mapping entry at line {number}.",
                path=path,
            )
        key, value = content.split(":", 1)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            raise StateError(
                "invalid-yaml",
                f"Invalid mapping key at line {number}.",
                path=path,
            )
        return key, value.strip()

    def parse_mapping(
        indentation: int,
        seed: tuple[str, object] | None = None,
    ) -> dict[str, object]:
        nonlocal index
        result: dict[str, object] = {}
        if seed is not None:
            result[seed[0]] = seed[1]
        while index < len(tokens):
            number, current_indent, content = tokens[index]
            if current_indent < indentation:
                break
            if current_indent > indentation:
                raise StateError(
                    "invalid-yaml",
                    f"Unexpected indentation at line {number}.",
                    path=path,
                )
            if content == "-" or content.startswith("- "):
                break
            key, raw_value = split_mapping(content, number)
            if key in result:
                raise StateError(
                    "duplicate-yaml-key",
                    f"Duplicate key {key!r} at line {number}.",
                    path=path,
                )
            index += 1
            if raw_value:
                result[key] = parse_yaml_scalar(
                    raw_value,
                    line=number,
                    path=path,
                )
                continue
            if index >= len(tokens) or tokens[index][1] <= indentation:
                raise StateError(
                    "invalid-yaml",
                    f"Key {key!r} has no nested value at line {number}.",
                    path=path,
                )
            if tokens[index][1] != indentation + 2:
                raise StateError(
                    "invalid-yaml",
                    f"Nested value for {key!r} must indent two spaces at line {tokens[index][0]}.",
                    path=path,
                )
            result[key] = parse_block(indentation + 2)
        return result

    def parse_list(indentation: int) -> list[object]:
        nonlocal index
        result: list[object] = []
        while index < len(tokens):
            number, current_indent, content = tokens[index]
            if current_indent < indentation:
                break
            if current_indent > indentation:
                raise StateError(
                    "invalid-yaml",
                    f"Unexpected list indentation at line {number}.",
                    path=path,
                )
            if content != "-" and not content.startswith("- "):
                break
            remainder = content[1:].strip()
            index += 1
            if not remainder:
                if index >= len(tokens) or tokens[index][1] != indentation + 2:
                    raise StateError(
                        "invalid-yaml",
                        f"List item at line {number} has no nested value.",
                        path=path,
                    )
                result.append(parse_block(indentation + 2))
                continue
            if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*:", remainder):
                key, raw_value = split_mapping(remainder, number)
                if not raw_value:
                    raise StateError(
                        "invalid-yaml",
                        f"An inline list mapping needs a scalar value at line {number}.",
                        path=path,
                    )
                first_value = parse_yaml_scalar(
                    raw_value,
                    line=number,
                    path=path,
                )
                if index < len(tokens) and tokens[index][1] == indentation + 2:
                    result.append(
                        parse_mapping(
                            indentation + 2,
                            seed=(key, first_value),
                        )
                    )
                else:
                    result.append({key: first_value})
                continue
            result.append(parse_yaml_scalar(remainder, line=number, path=path))
        return result

    def parse_block(indentation: int) -> object:
        if index >= len(tokens):
            raise StateError("invalid-yaml", "Unexpected end of YAML.", path=path)
        number, current_indent, content = tokens[index]
        if current_indent != indentation:
            raise StateError(
                "invalid-yaml",
                f"Unexpected indentation at line {number}.",
                path=path,
            )
        if content == "-" or content.startswith("- "):
            return parse_list(indentation)
        return parse_mapping(indentation)

    parsed = parse_block(tokens[0][1])
    if tokens[0][1] != 0:
        raise StateError(
            "invalid-yaml",
            "The top-level mapping must not be indented.",
            path=path,
        )
    if index != len(tokens):
        number = tokens[index][0]
        raise StateError(
            "invalid-yaml",
            f"Unsupported YAML structure at line {number}.",
            path=path,
        )
    return parsed


ASSET_FIELDS = {
    "id",
    "usage_locations",
    "content_job",
    "source_url",
    "source_path",
    "creator",
    "origin",
    "obtained_date",
    "license_or_terms",
    "attribution_required",
    "attribution_text",
    "modification_limits",
    "modifications",
    "factual_status",
    "depicts_or_claim",
    "privacy_review",
    "owner_approval",
    "generated",
    "art_direction",
    "delivery",
    "accessibility",
    "replacement",
}
ASSET_OPTIONAL_FIELDS = {
    "privacy_review_owner",
    "privacy_review_date",
    "privacy_review_reason",
    "owner_approval_owner",
    "owner_approval_date",
    "owner_approval_reason",
    "generated_media_provenance",
}
ASSET_NESTED_FIELDS = {
    "generated": {
        "used",
        "tool_or_model",
        "source_inputs",
        "disclosure_required",
        "disclosure_text",
    },
    "generated_media_provenance": {
        "applicability",
        "jurisdiction",
        "roles",
        "transformation_chain",
        "credential_detected",
        "credential_validated",
        "credential_preserved",
        "visible_disclosure_basis",
        "visible_disclosure_text",
        "legal_review_status",
        "legal_review_owner",
        "legal_review_date",
        "legal_review_reason",
    },
    "art_direction": {
        "subject",
        "crop_or_safe_zone",
        "lighting_palette_perspective",
        "set_consistency_notes",
    },
    "delivery": {
        "source_dimensions",
        "output_dimensions",
        "formats",
        "responsive_behavior",
        "intrinsic_dimensions_reserved",
    },
    "accessibility": {
        "treatment",
        "alt_text",
        "caption_or_transcript",
    },
    "replacement": {
        "status",
        "owner",
        "due_date",
    },
}
ASSET_LIST_FIELDS = {
    "usage_locations",
    "generated.source_inputs",
    "generated_media_provenance.roles",
    "generated_media_provenance.transformation_chain",
    "delivery.output_dimensions",
    "delivery.formats",
}
ASSET_BOOLEAN_FIELDS = {
    "attribution_required",
    "generated.used",
    "generated.disclosure_required",
    "delivery.intrinsic_dimensions_reserved",
}
ASSET_ORIGINS = {
    "owner-supplied",
    "first-party",
    "licensed",
    "generated",
    "other",
}
ASSET_FACTUAL_STATUSES = {
    "pending",
    "approved",
    "concept",
    "placeholder",
    "prohibited",
}
ASSET_PRIVACY_STATUSES = {
    "pending",
    "not-required",
    "approved",
    "rejected",
}
ASSET_OWNER_APPROVAL_STATUSES = {
    "pending",
    "approved",
    "rejected",
}
ASSET_ACCESSIBILITY_TREATMENTS = {
    "pending",
    "decorative",
    "informative",
    "functional",
    "complex",
    "not-applicable",
}
ASSET_REPLACEMENT_STATUSES = {
    "not-needed",
    "pending",
    "required",
    "scheduled",
    "replaced",
}
ASSET_GENERATED_MEDIA_APPLICABILITY = {
    "pending",
    "applicable",
    "not-applicable",
    "uncertain",
}
ASSET_GENERATED_MEDIA_ROLES = {
    "provider",
    "deployer",
    "publisher",
}
ASSET_CREDENTIAL_DETECTED_STATUSES = {
    "pending",
    "detected",
    "not-detected",
    "unknown",
    "not-applicable",
}
ASSET_CREDENTIAL_VALIDATED_STATUSES = {
    "pending",
    "validated",
    "invalid",
    "unverifiable",
    "not-applicable",
}
ASSET_CREDENTIAL_PRESERVED_STATUSES = {
    "pending",
    "preserved",
    "not-preserved",
    "unknown",
    "not-applicable",
}
ASSET_GENERATED_MEDIA_LEGAL_STATUSES = {
    "pending",
    "not-required",
    "approved",
    "changes-required",
    "rejected",
}


def require_exact_keys(
    value: object,
    expected: set[str],
    *,
    label: str,
    path: Path,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise StateError(
            "invalid-asset-manifest",
            f"{label} must be a mapping.",
            path=path,
        )
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing or unknown:
        messages = []
        if missing:
            messages.append("missing " + ", ".join(missing))
        if unknown:
            messages.append("unknown " + ", ".join(unknown))
        raise StateError(
            "invalid-asset-manifest",
            f"{label} has " + "; ".join(messages) + ".",
            path=path,
        )
    return value


def require_required_and_optional_keys(
    value: object,
    required: set[str],
    optional: set[str],
    *,
    label: str,
    path: Path,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise StateError(
            "invalid-asset-manifest",
            f"{label} must be a mapping.",
            path=path,
        )
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required - optional)
    if missing or unknown:
        messages = []
        if missing:
            messages.append("missing " + ", ".join(missing))
        if unknown:
            messages.append("unknown " + ", ".join(unknown))
        raise StateError(
            "invalid-asset-manifest",
            f"{label} has " + "; ".join(messages) + ".",
            path=path,
        )
    return value


def validate_asset_manifest(
    path: Path,
    current_version: str,
) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise StateError("state-read-failed", str(exc), path=path) from exc
    if "__DESIGN_DNA_VERSION__" in text:
        raise StateError(
            "unresolved-template-token",
            "assets.yml contains an unresolved template token.",
            path=path,
        )
    payload = require_exact_keys(
        parse_strict_yaml_subset(text, path=path),
        {"schema_version", "created_with", "classification", "assets"},
        label="assets.yml",
        path=path,
    )
    if type(payload["schema_version"]) is not int or payload["schema_version"] != STATE_SCHEMA_VERSION:
        raise StateError(
            "invalid-asset-manifest",
            "assets.yml schema_version must be integer 1.",
            path=path,
        )
    created_with = payload["created_with"]
    if (
        not isinstance(created_with, str)
        or not created_with.startswith("design-dna ")
        or not SEMVER.fullmatch(created_with.removeprefix("design-dna "))
    ):
        raise StateError(
            "invalid-asset-manifest",
            "assets.yml created_with must contain a valid Design DNA version.",
            path=path,
        )
    if payload["classification"] not in CLASSIFICATIONS:
        raise StateError(
            "invalid-asset-manifest",
            "assets.yml has an invalid classification.",
            path=path,
        )
    assets = payload["assets"]
    if not isinstance(assets, list):
        raise StateError(
            "invalid-asset-manifest",
            "assets.yml assets must be a list.",
            path=path,
        )
    seen_ids: set[str] = set()
    string_fields = (ASSET_FIELDS | ASSET_OPTIONAL_FIELDS) - set(ASSET_NESTED_FIELDS) - {
        "usage_locations",
        "attribution_required",
    }
    for asset_index, raw_asset in enumerate(assets):
        label = f"assets[{asset_index}]"
        asset = require_required_and_optional_keys(
            raw_asset,
            ASSET_FIELDS,
            ASSET_OPTIONAL_FIELDS,
            label=label,
            path=path,
        )
        for field in string_fields:
            if field in asset and not isinstance(asset[field], str):
                raise StateError(
                    "invalid-asset-manifest",
                    f"{label}.{field} must be a string.",
                    path=path,
                )
        asset_id = asset["id"]
        if not re.fullmatch(r"ASSET-[0-9]{3,}", asset_id):
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.id must match ASSET- followed by at least three digits.",
                path=path,
            )
        if asset_id in seen_ids:
            raise StateError(
                "invalid-asset-manifest",
                f"Duplicate asset id {asset_id}.",
                path=path,
            )
        seen_ids.add(asset_id)
        if asset["origin"] not in ASSET_ORIGINS:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.origin has an unsupported value.",
                path=path,
            )
        if asset["factual_status"] not in ASSET_FACTUAL_STATUSES:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.factual_status has an unsupported value.",
                path=path,
            )
        privacy_status = asset["privacy_review"]
        if privacy_status not in ASSET_PRIVACY_STATUSES:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.privacy_review has an unsupported value.",
                path=path,
            )
        if privacy_status != "pending":
            missing_review_context = [
                field
                for field in (
                    "privacy_review_owner",
                    "privacy_review_date",
                    "privacy_review_reason",
                )
                if not str(asset.get(field, "")).strip()
            ]
            if missing_review_context:
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.privacy_review {privacy_status!r} requires "
                        + ", ".join(missing_review_context)
                        + "."
                    ),
                    path=path,
                )
        owner_approval = asset["owner_approval"]
        if owner_approval not in ASSET_OWNER_APPROVAL_STATUSES:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.owner_approval has an unsupported value.",
                path=path,
            )
        if owner_approval != "pending":
            missing_approval_context = [
                field
                for field in (
                    "owner_approval_owner",
                    "owner_approval_date",
                    "owner_approval_reason",
                )
                if not str(asset.get(field, "")).strip()
            ]
            if missing_approval_context:
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.owner_approval {owner_approval!r} requires "
                        + ", ".join(missing_approval_context)
                        + "."
                    ),
                    path=path,
                )
        for date_field in (
            "obtained_date",
            "privacy_review_date",
            "owner_approval_date",
        ):
            date_value = asset.get(date_field, "")
            if date_value:
                try:
                    parsed_date = date.fromisoformat(date_value)
                    if parsed_date > date.today():
                        raise ValueError("date is in the future")
                except ValueError as exc:
                    raise StateError(
                        "invalid-asset-manifest",
                        (
                            f"{label}.{date_field} must be a non-future ISO "
                            "date or empty."
                        ),
                        path=path,
                    ) from exc
        for nested_name, nested_fields in ASSET_NESTED_FIELDS.items():
            if nested_name not in asset:
                continue
            nested = require_exact_keys(
                asset[nested_name],
                nested_fields,
                label=f"{label}.{nested_name}",
                path=path,
            )
            for field, value in nested.items():
                dotted = f"{nested_name}.{field}"
                if dotted in ASSET_BOOLEAN_FIELDS:
                    if type(value) is not bool:
                        raise StateError(
                            "invalid-asset-manifest",
                            f"{label}.{dotted} must be a boolean.",
                            path=path,
                        )
                elif dotted in ASSET_LIST_FIELDS:
                    if not isinstance(value, list) or not all(
                        isinstance(item, str) for item in value
                    ):
                        raise StateError(
                            "invalid-asset-manifest",
                            f"{label}.{dotted} must be a list of strings.",
                            path=path,
                        )
                    if (
                        any(not item.strip() for item in value)
                        or len(value) != len(set(value))
                    ):
                        raise StateError(
                            "invalid-asset-manifest",
                            (
                                f"{label}.{dotted} must contain unique, "
                                "nonempty strings."
                            ),
                            path=path,
                        )
                elif not isinstance(value, str):
                    raise StateError(
                        "invalid-asset-manifest",
                        f"{label}.{dotted} must be a string.",
                        path=path,
                    )
        generated = asset["generated"]
        if generated["used"]:
            missing_generated_context = []
            if not generated["tool_or_model"].strip():
                missing_generated_context.append("tool_or_model")
            if not generated["source_inputs"]:
                missing_generated_context.append("source_inputs")
            if missing_generated_context:
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated.used requires "
                        + ", ".join(missing_generated_context)
                        + "."
                    ),
                    path=path,
                )
        elif (
            generated["tool_or_model"].strip()
            or generated["source_inputs"]
            or generated["disclosure_required"]
            or generated["disclosure_text"].strip()
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.generated fields record generation while "
                    "generated.used is false."
                ),
                path=path,
            )
        if (
            generated["disclosure_required"]
            and not generated["disclosure_text"].strip()
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.generated.disclosure_required requires "
                    "generated.disclosure_text."
                ),
                path=path,
            )
        if asset["origin"] == "generated" and not generated["used"]:
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.origin 'generated' requires generated.used true."
                ),
                path=path,
            )
        generated_media = asset.get("generated_media_provenance")
        if (
            payload["classification"] == "public"
            and generated["used"]
            and not isinstance(generated_media, dict)
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label} is public generated media and requires "
                    "generated_media_provenance."
                ),
                path=path,
            )
        if isinstance(generated_media, dict):
            applicability = generated_media["applicability"]
            if applicability not in ASSET_GENERATED_MEDIA_APPLICABILITY:
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance.applicability "
                        "has an unsupported value."
                    ),
                    path=path,
                )
            roles = generated_media["roles"]
            if len(set(roles)) != len(roles) or any(
                role not in ASSET_GENERATED_MEDIA_ROLES for role in roles
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance.roles must contain "
                        "unique provider, deployer, or publisher values."
                    ),
                    path=path,
                )
            if applicability == "applicable":
                if not generated["used"]:
                    raise StateError(
                        "invalid-asset-manifest",
                        (
                            f"{label}.generated_media_provenance.applicability "
                            "'applicable' requires generated.used true."
                        ),
                        path=path,
                    )
                missing_applicability_context = []
                if not generated_media["jurisdiction"].strip():
                    missing_applicability_context.append("jurisdiction")
                if not roles:
                    missing_applicability_context.append("roles")
                if missing_applicability_context:
                    raise StateError(
                        "invalid-asset-manifest",
                        (
                            f"{label}.generated_media_provenance.applicability "
                            "'applicable' requires "
                            + ", ".join(missing_applicability_context)
                            + "."
                        ),
                        path=path,
                    )
            transformation_chain = generated_media["transformation_chain"]
            if any(not step.strip() for step in transformation_chain):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance.transformation_chain "
                        "must not contain empty steps."
                    ),
                    path=path,
                )
            credential_states = (
                (
                    "credential_detected",
                    ASSET_CREDENTIAL_DETECTED_STATUSES,
                ),
                (
                    "credential_validated",
                    ASSET_CREDENTIAL_VALIDATED_STATUSES,
                ),
                (
                    "credential_preserved",
                    ASSET_CREDENTIAL_PRESERVED_STATUSES,
                ),
            )
            for credential_field, allowed in credential_states:
                if generated_media[credential_field] not in allowed:
                    raise StateError(
                        "invalid-asset-manifest",
                        (
                            f"{label}.generated_media_provenance."
                            f"{credential_field} has an unsupported value."
                        ),
                        path=path,
                    )
            disclosure_basis = generated_media[
                "visible_disclosure_basis"
            ].strip()
            disclosure_text = generated_media[
                "visible_disclosure_text"
            ].strip()
            if disclosure_text and not disclosure_basis:
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance."
                        "visible_disclosure_text requires "
                        "visible_disclosure_basis."
                    ),
                    path=path,
                )
            if asset["generated"]["disclosure_required"] and (
                not disclosure_basis or not disclosure_text
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated.disclosure_required requires "
                        "generated_media_provenance visible disclosure "
                        "basis and text when that optional record is present."
                    ),
                    path=path,
                )
            base_disclosure_text = generated["disclosure_text"].strip()
            if (
                base_disclosure_text
                and disclosure_text
                and base_disclosure_text != disclosure_text
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated.disclosure_text and "
                        "generated_media_provenance.visible_disclosure_text "
                        "must match when both are recorded."
                    ),
                    path=path,
                )
            legal_status = generated_media["legal_review_status"]
            if legal_status not in ASSET_GENERATED_MEDIA_LEGAL_STATUSES:
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance."
                        "legal_review_status has an unsupported value."
                    ),
                    path=path,
                )
            if legal_status != "pending":
                missing_legal_context = [
                    field
                    for field in (
                        "legal_review_owner",
                        "legal_review_date",
                        "legal_review_reason",
                    )
                    if not generated_media[field].strip()
                ]
                if missing_legal_context:
                    raise StateError(
                        "invalid-asset-manifest",
                        (
                            f"{label}.generated_media_provenance."
                            f"legal_review_status {legal_status!r} requires "
                            + ", ".join(missing_legal_context)
                            + "."
                        ),
                        path=path,
                    )
            legal_review_date = generated_media["legal_review_date"]
            if legal_review_date:
                try:
                    parsed_legal_date = date.fromisoformat(legal_review_date)
                    if parsed_legal_date > date.today():
                        raise ValueError("date is in the future")
                except ValueError as exc:
                    raise StateError(
                        "invalid-asset-manifest",
                        (
                            f"{label}.generated_media_provenance."
                            "legal_review_date must be a non-future ISO date "
                            "or empty."
                        ),
                        path=path,
                    ) from exc
            if payload["classification"] == "public" and generated["used"]:
                incomplete_public_review = []
                if applicability not in {"applicable", "not-applicable"}:
                    incomplete_public_review.append(
                        "a resolved applicability decision"
                    )
                if not generated_media["jurisdiction"].strip():
                    incomplete_public_review.append("jurisdiction")
                if not transformation_chain:
                    incomplete_public_review.append("transformation_chain")
                for credential_field, _ in credential_states:
                    if generated_media[credential_field] == "pending":
                        incomplete_public_review.append(credential_field)
                if legal_status == "pending":
                    incomplete_public_review.append("legal_review_status")
                if incomplete_public_review:
                    raise StateError(
                        "invalid-asset-manifest",
                        (
                            f"{label} public generated media requires "
                            "completed provenance decisions for "
                            + ", ".join(incomplete_public_review)
                            + "."
                        ),
                        path=path,
                    )
            detected = generated_media["credential_detected"]
            validated = generated_media["credential_validated"]
            preserved = generated_media["credential_preserved"]
            if validated == "validated" and detected != "detected":
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance "
                        "credential_validated 'validated' requires "
                        "credential_detected 'detected'."
                    ),
                    path=path,
                )
            if preserved == "preserved" and (
                detected != "detected" or validated != "validated"
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance "
                        "credential_preserved 'preserved' requires detected "
                        "and validated credentials."
                    ),
                    path=path,
                )
            if detected == "not-detected" and (
                validated != "not-applicable"
                or preserved != "not-applicable"
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance credentials "
                        "marked not-detected require validation and "
                        "preservation to be not-applicable."
                    ),
                    path=path,
                )
        if type(asset["attribution_required"]) is not bool:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.attribution_required must be a boolean.",
                path=path,
            )
        if asset["attribution_required"] and not asset["attribution_text"].strip():
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.attribution_required requires "
                    "attribution_text."
                ),
                path=path,
            )
        if asset["origin"] == "licensed" and not asset["license_or_terms"].strip():
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.origin 'licensed' requires license_or_terms."
                ),
                path=path,
            )
        usage_locations = asset["usage_locations"]
        if not isinstance(usage_locations, list) or not all(
            isinstance(item, str) for item in usage_locations
        ):
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.usage_locations must be a list of strings.",
                path=path,
            )
        if (
            any(not item.strip() for item in usage_locations)
            or len(usage_locations) != len(set(usage_locations))
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.usage_locations must contain unique, "
                    "nonempty strings."
                ),
                path=path,
            )
        accessibility = asset["accessibility"]
        treatment = accessibility["treatment"]
        if treatment not in ASSET_ACCESSIBILITY_TREATMENTS:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.accessibility.treatment has an unsupported value.",
                path=path,
            )
        alt_text = accessibility["alt_text"].strip()
        transcript = accessibility["caption_or_transcript"].strip()
        if treatment in {"informative", "functional"} and not alt_text:
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.accessibility.treatment {treatment!r} "
                    "requires alt_text."
                ),
                path=path,
            )
        if treatment == "complex" and (not alt_text or not transcript):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.accessibility.treatment 'complex' requires "
                    "alt_text and caption_or_transcript."
                ),
                path=path,
            )
        if treatment == "decorative" and alt_text:
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.accessibility.treatment 'decorative' requires "
                    "empty alt_text."
                ),
                path=path,
            )
        replacement = asset["replacement"]
        replacement_status = replacement["status"]
        if replacement_status not in ASSET_REPLACEMENT_STATUSES:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.replacement.status has an unsupported value.",
                path=path,
            )
        if replacement_status in {"required", "scheduled"} and (
            not replacement["owner"].strip()
            or not replacement["due_date"].strip()
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.replacement.status {replacement_status!r} "
                    "requires owner and due_date."
                ),
                path=path,
            )
        if replacement_status == "replaced" and not replacement["owner"].strip():
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.replacement.status 'replaced' requires owner."
                ),
                path=path,
            )
        due_date = asset["replacement"]["due_date"]
        if due_date:
            try:
                date.fromisoformat(due_date)
            except ValueError as exc:
                raise StateError(
                    "invalid-asset-manifest",
                    f"{label}.replacement.due_date must be an ISO date or empty.",
                    path=path,
                ) from exc
    warnings: list[str] = []
    expected = f"design-dna {current_version}"
    if created_with != expected:
        warnings.append(
            f"assets.yml was created with {created_with}; current package is {expected}."
        )
    return warnings


def parse_frontmatter(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise StateError("state-read-failed", str(exc), path=path) from exc
    if not text.startswith("---\n"):
        raise StateError("invalid-frontmatter", "Markdown must begin with frontmatter.", path=path)
    end = text.find("\n---\n", 4)
    if end < 0:
        raise StateError("invalid-frontmatter", "Frontmatter is not closed.", path=path)
    return parse_flat_yaml(text[4:end], path=path)


def restricted_git_tracking(
    project: Path,
    state_root: Path,
) -> tuple[list[str], str | None]:
    """Return tracked restricted records and an explicit verification warning."""
    environment = os.environ.copy()
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    ):
        environment.pop(name, None)
    environment["GIT_OPTIONAL_LOCKS"] = "0"

    try:
        probe = subprocess.run(
            ["git", "-C", str(project), "rev-parse", "--show-toplevel"],
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=10,
            env=environment,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], (
            "Git tracking for restricted research could not be verified: "
            f"{exc}. Recheck before collecting participant data."
        )
    if probe.returncode != 0:
        return [], (
            "Git tracking for restricted research was not verified because "
            "the project is not confirmed to be inside a Git worktree. "
            "Recheck after Git initialization and before collecting "
            "participant data."
        )

    raw_root = probe.stdout.strip()
    if not raw_root:
        return [], (
            "Git tracking for restricted research could not be verified "
            "because Git returned no worktree root. Recheck before collecting "
            "participant data."
        )
    repository_root = lexical_absolute(Path(raw_root))
    if not is_within(state_root, repository_root):
        return [], (
            "Git tracking for restricted research could not be verified "
            "because the reported worktree does not contain .design-dna. "
            "Recheck before collecting participant data."
        )
    state_relative = state_root.relative_to(repository_root).as_posix()

    try:
        listed = subprocess.run(
            [
                "git",
                "-C",
                str(repository_root),
                "ls-files",
                "-z",
                "--full-name",
                "--",
                state_relative,
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=10,
            env=environment,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], (
            "Git tracking for restricted research could not be verified: "
            f"{exc}. Recheck before collecting participant data."
        )
    if listed.returncode != 0:
        return [], (
            "Git tracking for restricted research could not be verified "
            "because Git could not enumerate tracked .design-dna files. "
            "Recheck before collecting participant data."
        )

    prefix = state_relative.rstrip("/")
    user_validation = f"{prefix}/user-validation.md"
    research_prefix = f"{prefix}/evidence/research/"
    prefix_key = prefix.casefold()
    user_validation_key = user_validation.casefold()
    research_prefix_key = research_prefix.casefold()
    tracked: list[str] = []
    for raw_name in listed.stdout.split(b"\0"):
        if not raw_name:
            continue
        name = raw_name.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        name_key = name.casefold()
        path = PurePosixPath(name)
        restricted_at_root = (
            path.parent.as_posix().casefold() == prefix_key
            and ".restricted." in path.name.casefold()
        )
        if (
            name_key == user_validation_key
            or name_key.startswith(research_prefix_key)
            or restricted_at_root
        ):
            tracked.append(name)
    return sorted(set(tracked)), None


def validate_state(project: Path, current_version: str) -> tuple[list[str], list[str]]:
    state_root = project / ".design-dna"
    assert_no_reparse_ancestors(state_root, stop=project)
    assert_safe_tree(state_root)
    failures: list[str] = []
    warnings: list[str] = []
    if not state_root.is_dir():
        return ([f"Missing project state directory: {state_root}"], warnings)
    manifest_path = state_root / "state.json"
    if not manifest_path.is_file():
        failures.append(f"Missing state file: {manifest_path}")
        return failures, warnings
    records: list[str] = []
    try:
        state = read_json(manifest_path)
        if not isinstance(state, dict) or set(state) != {
            "schema_version", "created_with", "created", "classification", "records"
        }:
            failures.append("state.json has an unsupported shape.")
            state = {}
        if state.get("schema_version") != STATE_SCHEMA_VERSION:
            failures.append("state.json has an unsupported schema_version.")
        if state.get("classification") != "internal":
            failures.append("state.json classification must be internal.")
        created_with = state.get("created_with")
        if (
            not isinstance(created_with, str)
            or not created_with.startswith("design-dna ")
            or not SEMVER.fullmatch(created_with.removeprefix("design-dna "))
        ):
            failures.append("state.json has an invalid created_with value.")
        created = date.fromisoformat(str(state.get("created", "")))
        if created > date.today():
            failures.append("state.json created date may not be in the future.")
        raw_records = state.get("records")
        if (
            not isinstance(raw_records, list)
            or not all(isinstance(item, str) for item in raw_records)
            or len(raw_records) != len(set(raw_records))
        ):
            failures.append("state.json records must be a unique list of strings.")
        else:
            records = raw_records
        unknown = set(records) - set(RECORD_TEMPLATES)
        if unknown:
            failures.append(f"state.json lists unknown records: {', '.join(sorted(unknown))}.")
        for record in records:
            if record not in RECORD_TEMPLATES:
                continue
            filename = RECORD_TEMPLATES[record][0]
            if not (state_root / filename).is_file():
                failures.append(f"Missing selected record: {state_root / filename}")
        expected = f"design-dna {current_version}"
        if state.get("created_with") != expected:
            warnings.append(f"State was created with {state.get('created_with', 'unknown')}; current package is {expected}.")
    except (StateError, ValueError) as exc:
        failures.append(f"Invalid state.json: {exc}")

    listed_files = {
        RECORD_TEMPLATES[record][0]
        for record in records
        if record in RECORD_TEMPLATES
    }
    for record, (filename, _) in RECORD_TEMPLATES.items():
        if (state_root / filename).is_file() and filename not in listed_files:
            failures.append(
                f"Packaged record {filename} exists but state.json does not list {record}."
            )

    for filename in FRONTMATTER_FILES:
        path = state_root / filename
        if not path.is_file():
            continue
        try:
            meta = parse_frontmatter(path)
            required = {"schema_version", "created_with", "classification"}
            missing = sorted(required - set(meta))
            if missing:
                failures.append(f"{filename} is missing frontmatter fields: {', '.join(missing)}.")
            if meta.get("schema_version") != str(STATE_SCHEMA_VERSION):
                failures.append(f"{filename} has an unsupported schema_version.")
            if meta.get("classification") not in CLASSIFICATIONS:
                failures.append(f"{filename} has an invalid classification.")
            created_with = meta.get("created_with", "")
            if (
                not created_with.startswith("design-dna ")
                or not SEMVER.fullmatch(created_with.removeprefix("design-dna "))
            ):
                failures.append(f"{filename} has an invalid created_with value.")
            if "__DESIGN_DNA_VERSION__" in path.read_text(encoding="utf-8"):
                failures.append(f"{filename} contains an unresolved template token.")
            if filename == "user-validation.md":
                missing_research_fields = sorted(
                    USER_VALIDATION_FRONTMATTER_FIELDS - set(meta)
                )
                if missing_research_fields:
                    failures.append(
                        "user-validation.md is missing privacy-control "
                        "frontmatter fields: "
                        + ", ".join(missing_research_fields)
                        + "."
                    )
                empty_research_fields = sorted(
                    field
                    for field in USER_VALIDATION_FRONTMATTER_FIELDS & set(meta)
                    if not meta.get(field, "").strip()
                )
                if empty_research_fields:
                    failures.append(
                        "user-validation.md has empty privacy-control "
                        "frontmatter fields: "
                        + ", ".join(empty_research_fields)
                        + "."
                    )
                if meta.get("classification") != "restricted-research":
                    failures.append(
                        "user-validation.md classification must be "
                        "restricted-research."
                    )
                deletion_status = meta.get("deletion_status")
                if (
                    deletion_status is not None
                    and deletion_status
                    not in USER_VALIDATION_DELETION_STATUSES
                ):
                    failures.append(
                        "user-validation.md has an invalid deletion_status."
                    )
                pending_controls = sorted(
                    field
                    for field in USER_VALIDATION_FRONTMATTER_FIELDS
                    if meta.get(field, "").strip().lower() == "pending"
                )
                if pending_controls:
                    warnings.append(
                        "user-validation.md privacy controls remain pending: "
                        + ", ".join(pending_controls)
                        + ". Complete them before collecting participant data."
                    )
        except StateError as exc:
            failures.append(str(exc))

    user_validation_path = state_root / "user-validation.md"
    if user_validation_path.is_file():
        ignore_path = state_root / ".gitignore"
        if not ignore_path.is_file():
            failures.append(
                ".design-dna/.gitignore is required to protect "
                "user-validation.md from accidental commits."
            )
        else:
            try:
                ignore_text = ignore_path.read_text(encoding="utf-8")
                required_ignore_block = (
                    "\n".join(STATE_PRIVACY_IGNORE_LINES) + "\n"
                )
                if not ignore_text.endswith(required_ignore_block):
                    failures.append(
                        ".design-dna/.gitignore must end with the packaged "
                        "privacy-safeguard block so later negations cannot "
                        "re-enable restricted research files."
                    )
            except (OSError, UnicodeError) as exc:
                failures.append(
                    f"Unable to validate .design-dna/.gitignore: {exc}"
                )
        tracked_restricted, tracking_warning = restricted_git_tracking(
            project,
            state_root,
        )
        if tracked_restricted:
            failures.append(
                "Restricted Design DNA research is already tracked by Git: "
                + ", ".join(tracked_restricted)
                + ". Remove it from the Git index before collecting or "
                "retaining participant data; .gitignore cannot protect "
                "files that are already tracked."
            )
        if tracking_warning:
            warnings.append(tracking_warning)

    assets_path = state_root / "assets.yml"
    if assets_path.is_file():
        try:
            warnings.extend(validate_asset_manifest(assets_path, current_version))
        except StateError as exc:
            failures.append(f"Invalid assets.yml: {exc}")
    for legacy in ("state.yml", "continuity-note.yml", "ledger-entry.yml"):
        if (state_root / legacy).exists():
            warnings.append(f"Legacy record preserved at {state_root / legacy}; migrate it manually if its history is still useful.")
    return failures, warnings


def append_required_ignore_lines(
    root: Path,
    required_lines: tuple[str, ...],
) -> None:
    ignore_path = root / ".gitignore"
    existing = ""
    if ignore_path.is_file():
        try:
            existing = ignore_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise StateError(
                "privacy-ignore-read-failed",
                str(exc),
                path=ignore_path,
            ) from exc
    required_block = "\n".join(required_lines) + "\n"
    if existing.endswith(required_block):
        return
    existing = existing.replace(required_block, "")
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    try:
        with ignore_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(existing + prefix + required_block)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise StateError(
            "privacy-ignore-write-failed",
            str(exc),
            path=ignore_path,
        ) from exc


def install_backup_privacy_guard(root: Path) -> bool:
    """Ignore recovery contents without losing the prior ignore file on rollback."""
    ignore_path = root / ".gitignore"
    existed = ignore_path.is_file()
    existing = ""
    if existed:
        try:
            existing = ignore_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise StateError(
                "privacy-ignore-read-failed",
                str(exc),
                path=ignore_path,
            ) from exc
    if BACKUP_PRIVACY_IGNORE_BLOCK in existing:
        raise StateError(
            "privacy-ignore-conflict",
            "The recovery privacy-guard marker already exists.",
            path=ignore_path,
        )
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    try:
        ignore_path.write_text(
            existing + prefix + BACKUP_PRIVACY_IGNORE_BLOCK,
            encoding="utf-8",
            newline="\n",
        )
    except OSError as exc:
        raise StateError(
            "privacy-ignore-write-failed",
            str(exc),
            path=ignore_path,
        ) from exc
    return existed


def remove_backup_privacy_guard(root: Path, original_existed: bool) -> None:
    ignore_path = root / ".gitignore"
    try:
        guarded = ignore_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise StateError(
            "privacy-ignore-read-failed",
            str(exc),
            path=ignore_path,
        ) from exc
    if BACKUP_PRIVACY_IGNORE_BLOCK not in guarded:
        raise StateError(
            "privacy-ignore-guard-missing",
            "The recovery privacy guard is missing.",
            path=ignore_path,
        )
    restored = guarded.replace(BACKUP_PRIVACY_IGNORE_BLOCK, "", 1)
    try:
        if original_existed:
            ignore_path.write_text(
                restored,
                encoding="utf-8",
                newline="\n",
            )
        else:
            ignore_path.unlink()
    except OSError as exc:
        raise StateError(
            "privacy-ignore-restore-failed",
            str(exc),
            path=ignore_path,
        ) from exc


def render_new_state(skill_root: Path, destination: Path, version: str, records: tuple[str, ...]) -> None:
    template_root = skill_root / "templates"
    contents = {
        RECORD_TEMPLATES[record][0]: template_text(template_root, RECORD_TEMPLATES[record][1], version)
        for record in records
    }
    contents["state.json"] = state_manifest(version, records)
    destination.mkdir()
    for filename, content in contents.items():
        target = destination / filename
        assert_contained(target, destination)
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    (destination / "evidence").mkdir()
    append_required_ignore_lines(destination, STATE_PRIVACY_IGNORE_LINES)


def merge_existing(
    existing: Path,
    staged: Path,
    *,
    force: bool,
    selected: tuple[str, ...],
    version: str,
) -> None:
    if not entry_exists(existing):
        return
    assert_safe_tree(existing)
    if not existing.is_dir():
        raise StateError("invalid-state-entry", ".design-dna exists but is not a directory.", path=existing)
    existing_manifest = existing / "state.json"
    previous_records: list[str] = []
    if existing_manifest.is_file():
        try:
            payload = read_json(existing_manifest)
            raw_records = payload.get("records") if isinstance(payload, dict) else None
            if (
                not isinstance(raw_records, list)
                or not all(isinstance(record, str) for record in raw_records)
                or len(raw_records) != len(set(raw_records))
                or any(record not in RECORD_TEMPLATES for record in raw_records)
            ):
                raise StateError(
                    "invalid-existing-state",
                    "Existing state.json has invalid records.",
                    path=existing_manifest,
                )
            previous_records = raw_records
        except StateError:
            if not force:
                raise
    elif not force:
        raise StateError(
            "invalid-existing-state",
            "Existing .design-dna directory has no state.json; pass --force to rebuild packaged metadata while preserving custom files.",
            path=existing_manifest,
        )
    def fail_walk(error: OSError) -> None:
        raise StateError(
            "state-enumeration-failed",
            str(error),
            path=Path(error.filename) if error.filename else existing,
        ) from error

    for current, directories, files in os.walk(
        existing,
        topdown=True,
        followlinks=False,
        onerror=fail_walk,
    ):
        relative = Path(current).relative_to(existing)
        target_dir = staged / relative
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in files:
            if relative == Path(".") and name == "state.json":
                continue
            source = Path(current) / name
            target = target_dir / name
            if is_reparse(source):
                raise StateError(
                    "reparse-point-refused",
                    "State changed to contain a link during initialization.",
                    path=source,
                )
            if target.exists() and force:
                continue
            if target.exists():
                target.unlink()
            shutil.copy2(source, target, follow_symlinks=False)
    inferred_records = [
        record
        for record, (filename, _) in RECORD_TEMPLATES.items()
        if (staged / filename).is_file()
    ]
    merged_records = tuple(
        dict.fromkeys([*previous_records, *selected, *inferred_records])
    )
    manifest_path = staged / "state.json"
    manifest_path.write_text(
        state_manifest(version, merged_records),
        encoding="utf-8",
        newline="\n",
    )
    append_required_ignore_lines(staged, STATE_PRIVACY_IGNORE_LINES)


def as_state_error(
    error: Exception,
    *,
    code: str,
    path: Path,
) -> StateError:
    if isinstance(error, StateError):
        return error
    return StateError(code, str(error), path=path)


def rollback_transaction(
    state_root: Path,
    staged: Path,
    backup: Path | None,
    project: Path,
    *,
    candidate_installed: bool,
    backup_ignore_existed: bool,
    backup_guard_installed: bool,
) -> tuple[Path | None, list[StateError]]:
    """Best-effort quarantine and restore without destroying diagnostic evidence."""
    failed: Path | None = None
    errors: list[StateError] = []
    candidate = state_root if candidate_installed else staged
    try:
        if entry_exists(candidate):
            failed = unique_peer(state_root, "failed")
            assert_contained(failed, project)
            candidate.rename(failed)
    except Exception as exc:
        errors.append(
            as_state_error(
                exc,
                code="failed-candidate-quarantine-failed",
                path=candidate,
            )
        )
    if backup is not None:
        try:
            if not entry_exists(backup):
                if not candidate_installed and entry_exists(state_root):
                    assert_safe_tree(state_root)
                    return failed, errors
                raise StateError(
                    "rollback-backup-missing",
                    "The prior-state backup is no longer available.",
                    path=backup,
                )
            if entry_exists(state_root):
                raise StateError(
                    "rollback-target-occupied",
                    "The state path is occupied, so the prior state cannot be restored safely.",
                    path=state_root,
                )
            if backup_guard_installed:
                remove_backup_privacy_guard(
                    backup,
                    backup_ignore_existed,
                )
            backup.rename(state_root)
            assert_safe_tree(state_root)
        except Exception as exc:
            errors.append(
                as_state_error(
                    exc,
                    code="prior-state-restore-failed",
                    path=backup,
                )
            )
    return failed, errors


def cleanup_stage_parent(
    stage_parent: Path | None,
    project: Path,
) -> StateError | None:
    if stage_parent is None:
        return None
    try:
        if entry_exists(stage_parent):
            assert_no_reparse_ancestors(stage_parent, stop=project)
            assert_contained(stage_parent, project)
            assert_safe_tree(stage_parent)
            shutil.rmtree(stage_parent)
    except Exception as exc:
        return as_state_error(
            exc,
            code="staging-cleanup-failed",
            path=stage_parent,
        )
    return None


def install_transaction(
    project: Path,
    skill_root: Path,
    records: tuple[str, ...],
    *,
    force: bool,
    dry_run: bool,
    version: str | None = None,
) -> list[dict[str, str]]:
    state_root = project / ".design-dna"
    assert_no_reparse_ancestors(state_root, stop=project)
    assert_safe_tree(state_root)
    version = release_version(skill_root) if version is None else version
    if dry_run:
        action = "replace" if entry_exists(state_root) and force else "merge"
        return [{"action": f"would-{action}", "path": str(state_root), "records": ",".join(records)}]

    stage_parent: Path | None = None
    staged = project / ".design-dna.unallocated-stage"
    backup: Path | None = None
    backup_ignore_existed = False
    backup_guard_installed = False
    moved_existing = False
    transition_started = False
    candidate_installed = False
    primary_error: StateError | None = None
    rollback_errors: list[StateError] = []
    failed_candidate: Path | None = None
    actions: list[dict[str, str]] = []
    try:
        stage_parent = Path(tempfile.mkdtemp(prefix=".design-dna-stage-", dir=project))
        staged = stage_parent / ".design-dna"
        assert_no_reparse_ancestors(stage_parent, stop=project)
        assert_contained(stage_parent, project)
        render_new_state(skill_root, staged, version, records)
        merge_existing(
            state_root,
            staged,
            force=force,
            selected=records,
            version=version,
        )
        assert_safe_tree(staged)

        failures, _ = validate_state_in_place(staged, version)
        if failures:
            raise StateError("staged-state-invalid", "; ".join(failures), path=staged)

        # Race-resistant recheck immediately before rename transitions.
        assert_no_reparse_ancestors(state_root, stop=project)
        assert_contained(state_root, project)
        if entry_exists(state_root):
            backup = unique_peer(state_root, "backup")
            assert_contained(backup, project)
            transition_started = True
            state_root.rename(backup)
            backup_ignore_existed = install_backup_privacy_guard(backup)
            backup_guard_installed = True
            moved_existing = True
        else:
            transition_started = True
        staged.rename(state_root)
        candidate_installed = True
        installed_failures, _ = validate_state(project, version)
        if installed_failures:
            raise StateError(
                "installed-state-invalid",
                "Post-install validation failed.",
                path=state_root,
                details={"validation_failures": installed_failures},
            )
        actions.append({"action": "installed", "path": str(state_root)})
        if moved_existing and backup is not None:
            if force:
                actions.append({
                    "action": "backup-preserved",
                    "path": str(backup),
                    "reason": "Forced refresh keeps the prior state recoverable.",
                })
                moved_existing = False
            else:
                try:
                    assert_contained(backup, project)
                    assert_safe_tree(backup)
                    shutil.rmtree(backup)
                except Exception as cleanup_error:
                    structured_cleanup = as_state_error(
                        cleanup_error,
                        code="backup-cleanup-failed",
                        path=backup,
                    )
                    actions.append({
                        "action": "backup-preserved",
                        "path": str(backup),
                        "reason": json.dumps(
                            error_record(structured_cleanup),
                            ensure_ascii=False,
                        ),
                    })
                moved_existing = False
    except Exception as exc:
        primary_error = as_state_error(
            exc,
            code="initialization-failed",
            path=state_root,
        )
        if transition_started:
            failed_candidate, rollback_errors = rollback_transaction(
                state_root,
                staged,
                backup,
                project,
                candidate_installed=candidate_installed,
                backup_ignore_existed=backup_ignore_existed,
                backup_guard_installed=backup_guard_installed,
            )
            if not rollback_errors:
                moved_existing = False

    cleanup_error = cleanup_stage_parent(stage_parent, project)
    if primary_error is not None:
        recovery: dict[str, object] = {
            "status": (
                "not-needed"
                if not transition_started
                else ("incomplete" if rollback_errors else "completed")
            ),
            "backup": str(backup) if backup is not None else None,
            "failed_candidate": (
                str(failed_candidate) if failed_candidate is not None else None
            ),
        }
        if rollback_errors:
            recovery["errors"] = [
                error_record(error) for error in rollback_errors
            ]
        details = dict(primary_error.details)
        details["rollback"] = recovery
        if cleanup_error is not None:
            details["cleanup"] = error_record(cleanup_error)
        if rollback_errors:
            raise StateError(
                "rollback-failed",
                "Initialization failed and automatic rollback was incomplete.",
                path=state_root,
                details={
                    "primary": error_record(primary_error),
                    **details,
                },
            ) from primary_error
        raise StateError(
            primary_error.code,
            str(primary_error),
            path=primary_error.path,
            details=details,
        ) from primary_error
    if cleanup_error is not None:
        actions.append({
            "action": "staging-cleanup-preserved",
            "path": str(stage_parent),
            "reason": json.dumps(error_record(cleanup_error), ensure_ascii=False),
        })
    return actions


def validate_state_in_place(state_root: Path, current_version: str) -> tuple[list[str], list[str]]:
    """Validate a staged state by presenting its parent as the project."""
    return validate_state(state_root.parent, current_version)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--force", action="store_true", help="Replace packaged template files; preserve other project records.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check-state", action="store_true")
    parser.add_argument(
        "--profile", choices=tuple(PROFILES), default="substantial",
        help="Record set to initialize when --record is not supplied (default: substantial).",
    )
    parser.add_argument(
        "--record", action="append", choices=tuple(RECORD_TEMPLATES),
        help="Create only this useful record; repeat to select more. Overrides --profile.",
    )
    parser.add_argument("--json", action="store_true", help="Emit a JSON success result as well as structured errors.")
    args = parser.parse_args()
    try:
        project = lexical_absolute(args.project)
        if not project.is_dir():
            raise StateError("project-not-found", "Project directory does not exist.", path=project)
        assert_no_reparse_ancestors(project)
        skill_root = Path(__file__).resolve().parents[1]
        plugin_root = skill_root.parents[1]
        protected = plugin_root if (plugin_root / ".codex-plugin" / "plugin.json").is_file() else skill_root
        if project == protected or is_within(project, protected) or is_within(protected, project):
            raise StateError(
                "protected-destination",
                "Refusing to create state in or around the packaged skill/plugin.",
                path=project,
            )
        version = release_version(skill_root)
        if args.check_state:
            failures, warnings = validate_state(project, version)
            result = {"ok": not failures, "project": str(project), "version": version, "failures": failures, "warnings": warnings}
            print(json.dumps(result, indent=2) if args.json else "\n".join(
                [*(f"FAIL: {item}" for item in failures), *(f"WARN: {item}" for item in warnings)]
                or [f"OK: Design DNA state schema {STATE_SCHEMA_VERSION} is current."]
            ))
            return 1 if failures else 0
        selected = tuple(dict.fromkeys(args.record or PROFILES[args.profile]))
        actions = install_transaction(
            project,
            skill_root,
            selected,
            force=args.force,
            dry_run=args.dry_run,
            version=version,
        )
        result = {"ok": True, "project": str(project), "version": version, "records": selected, "actions": actions}
        print(json.dumps(result, indent=2) if args.json else "\n".join(
            f"{item['action']}: {item['path']}" for item in actions
        ))
        return 0
    except StateError as exc:
        emit_error(exc)


if __name__ == "__main__":
    raise SystemExit(main())
