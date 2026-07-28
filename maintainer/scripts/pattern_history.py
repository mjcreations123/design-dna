#!/usr/bin/env python3
"""Manage an explicitly opted-in, user-certified private pattern registry."""

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
import os
import re
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from common import (
    ToolFailure,
    absolute,
    assert_no_reparse_path,
    emit,
    entry_exists,
    is_reparse,
    load_json,
    strict_format_checker,
)


ACK = (
    "I understand this registry is private, user-certified, "
    "and may still contain sensitive data."
)
SENSITIVE_ACK = (
    "I reviewed the warnings and authorize storing this minimized signature."
)
FORBIDDEN_KEYS = {
    "client",
    "client_name",
    "company",
    "copy",
    "content",
    "email",
    "name",
    "phone",
    "source_copy",
    "testimonial",
    "url",
    "user",
    "user_data",
}
SENSITIVE_PATTERNS = {
    "email-like text": re.compile(
        r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9.-])"
    ),
    "URL-like text": re.compile(r"\b(?:https?://|www\.)\S+", re.I),
    "phone-like text": re.compile(
        r"(?<!\d)(?:\+?\d[\d .()/-]{7,}\d)(?!\d)"
    ),
    "source-content cue": re.compile(
        r"\b(?:testimonial|customer quote|client quote|founder portrait|"
        r"real customer|full name|street address)\b",
        re.I,
    ),
}


def signature_schema(registry_schema: dict[str, object]) -> dict[str, object]:
    definition = dict(registry_schema["$defs"]["signature"])
    properties = dict(definition["properties"])
    properties.pop("id", None)
    definition["properties"] = properties
    definition["additionalProperties"] = False
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": {"signature": definition},
        "$ref": "#/$defs/signature",
    }


def walk_values(value: object, path: str = "<root>"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield ("key", child_path, str(key))
            yield from walk_values(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_values(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield ("value", path, value)


def validate_signature(
    payload: object,
    schema: dict[str, object],
) -> tuple[list[str], list[str]]:
    errors = [
        error.message
        for error in Draft202012Validator(
            signature_schema(schema),
            format_checker=strict_format_checker(),
        ).iter_errors(payload)
    ]
    warnings: set[str] = set()
    for kind, path, value in walk_values(payload):
        if kind == "key" and value.casefold() in FORBIDDEN_KEYS:
            errors.append(f"forbidden source/client-data key at {path}")
        if kind == "value":
            for label, pattern in SENSITIVE_PATTERNS.items():
                if (
                    label == "phone-like text"
                    and path == "<root>.date"
                    and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                ):
                    continue
                if pattern.search(value):
                    warnings.add(f"{label} at {path}")
    if isinstance(payload, dict):
        try:
            recorded = date.fromisoformat(str(payload.get("date", "")))
            if recorded > date.today():
                errors.append("signature date may not be in the future")
        except ValueError:
            pass
    return errors, sorted(warnings)


def signature_id(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def validate_registry_semantics(
    payload: dict[str, object],
    path: Path,
) -> None:
    entries = payload.get("entries", [])
    assert isinstance(entries, list)
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        stored_id = str(entry.get("id", ""))
        signature = {key: value for key, value in entry.items() if key != "id"}
        calculated = signature_id(signature)
        if stored_id != calculated:
            raise ToolFailure(
                "history-entry-id-mismatch",
                f"Entry {index} stores {stored_id!r}; expected {calculated!r}.",
                path,
            )
        if stored_id in seen:
            raise ToolFailure(
                "duplicate-history-entry-id",
                f"Duplicate entry id {stored_id}.",
                path,
            )
        seen.add(stored_id)


def load_registry(
    path: Path,
    schema: dict[str, object],
) -> dict[str, object]:
    if not entry_exists(path):
        return {"schema_version": 2, "entries": []}
    assert_no_reparse_path(path)
    payload = load_json(path)
    validate_registry_payload(payload, schema, path)
    assert isinstance(payload, dict)
    return payload


def validate_registry_payload(
    payload: object,
    schema: dict[str, object],
    path: Path,
) -> None:
    errors = list(
        Draft202012Validator(
            schema,
            format_checker=strict_format_checker(),
        ).iter_errors(payload)
    )
    if errors:
        raise ToolFailure(
            "invalid-history-registry",
            "; ".join(error.message for error in errors),
            path,
        )
    assert isinstance(payload, dict)
    validate_registry_semantics(payload, path)


def atomic_write(path: Path, payload: dict[str, object]) -> None:
    if not path.parent.is_dir():
        raise ToolFailure(
            "history-parent-missing",
            "Registry parent must already exist.",
            path.parent,
        )
    assert_no_reparse_path(path.parent)
    if entry_exists(path):
        assert_no_reparse_path(path)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


@contextmanager
def registry_lock(registry: Path, timeout_seconds: float = 5.0):
    lock = registry.with_name(f".{registry.name}.lock")
    assert_no_reparse_path(lock, stop=registry.parent)
    token = f"{os.getpid()}-{uuid.uuid4().hex}"
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            with lock.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(token + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            break
        except FileExistsError:
            if is_reparse(lock):
                raise ToolFailure(
                    "history-lock-unsafe",
                    "Registry lock is a link or reparse point.",
                    lock,
                )
            if time.monotonic() >= deadline:
                raise ToolFailure(
                    "history-lock-timeout",
                    "Another writer still owns the registry lock.",
                    lock,
                )
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            if (
                not is_reparse(lock)
                and lock.read_text(encoding="utf-8").strip() == token
            ):
                lock.unlink()
        except (FileNotFoundError, OSError, UnicodeError):
            pass


def tokens(signature: dict[str, object]) -> set[str]:
    values: set[str] = set()
    palette = signature.get("palette", {})
    if isinstance(palette, dict):
        values.add(f"palette:{str(palette.get('archetype', '')).casefold()}")
        for role in palette.get("roles", []):
            if isinstance(role, dict):
                values.add(
                    "color:"
                    f"{str(role.get('role', '')).casefold()}="
                    f"{str(role.get('hex', '')).casefold()}"
                )
    for item in signature.get("type_roles", []):
        if isinstance(item, dict):
            values.add(
                "type:"
                f"{str(item.get('role', '')).casefold()}="
                f"{str(item.get('family', '')).casefold()}"
            )
    for field in (
        "composition",
        "icon_concepts",
        "imagery_concepts",
        "motion_concepts",
    ):
        for value in signature.get(field, []):
            values.add(f"{field}:{str(value).casefold()}")
    return {value for value in values if not value.endswith(":")}


def similarity(
    left: dict[str, object],
    right: dict[str, object],
) -> tuple[float, list[str]]:
    left_tokens = tokens(left)
    right_tokens = tokens(right)
    shared = sorted(left_tokens & right_tokens)
    union = left_tokens | right_tokens
    return (len(shared) / len(union) if union else 0.0), shared


def entry_summary(entry: dict[str, object]) -> dict[str, object]:
    return {
        "id": entry.get("id"),
        "project_pseudonym": entry.get("project_pseudonym"),
        "scope_category": entry.get("scope_category"),
        "date": entry.get("date"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        required=True,
        help="Explicit private registry path; never auto-discovered.",
    )
    parser.add_argument(
        "--acknowledge",
        help=f"Required exact text for add: {ACK}",
    )
    parser.add_argument(
        "--acknowledge-sensitive",
        help=f"Required when heuristic warnings remain: {SENSITIVE_ACK}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    add = subparsers.add_parser("add")
    add.add_argument("--signature", type=Path, required=True)
    listing = subparsers.add_parser("list")
    listing.add_argument("--include-details", action="store_true")
    check = subparsers.add_parser("check")
    check.add_argument("--signature", type=Path, required=True)
    check.add_argument("--threshold", type=float, default=0.45)
    args = parser.parse_args()
    try:
        registry_path = absolute(args.registry)
        if not registry_path.parent.is_dir():
            raise ToolFailure(
                "history-parent-missing",
                "Registry parent must already exist.",
                registry_path.parent,
            )
        assert_no_reparse_path(registry_path.parent)
        schema = load_json(
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "pattern-history.schema.json"
        )
        assert isinstance(schema, dict)

        if args.command == "list":
            registry = load_registry(registry_path, schema)
            entries = registry["entries"]
            assert isinstance(entries, list)
            include_details = bool(args.include_details)
            if include_details and args.acknowledge != ACK:
                raise ToolFailure(
                    "explicit-detail-access-required",
                    f"Pass --acknowledge {ACK!r} to list full private entries.",
                    registry_path,
                )
            result_entries = (
                entries
                if include_details
                else [
                    entry_summary(entry)
                    for entry in entries
                    if isinstance(entry, dict)
                ]
            )
            emit({
                "ok": True,
                "private": True,
                "user_certified": True,
                "investigate_only": True,
                "details_included": include_details,
                "registry": str(registry_path),
                "entries": result_entries,
            })
            return 0

        signature_path = absolute(args.signature)
        assert_no_reparse_path(signature_path)
        signature = load_json(signature_path)
        problems, sensitive_warnings = validate_signature(signature, schema)
        if problems:
            raise ToolFailure(
                "invalid-minimized-signature",
                "; ".join(problems),
                signature_path,
            )
        assert isinstance(signature, dict)

        if args.command == "add":
            if args.acknowledge != ACK:
                raise ToolFailure(
                    "explicit-opt-in-required",
                    f"Pass --acknowledge {ACK!r}.",
                    registry_path,
                )
            if sensitive_warnings and args.acknowledge_sensitive != SENSITIVE_ACK:
                raise ToolFailure(
                    "sensitive-signature-review-required",
                    "Heuristic warnings: "
                    + "; ".join(sensitive_warnings)
                    + f". Pass --acknowledge-sensitive {SENSITIVE_ACK!r} only after minimizing the data.",
                    signature_path,
                )
            entry = {"id": signature_id(signature), **signature}
            with registry_lock(registry_path):
                registry = load_registry(registry_path, schema)
                entries = registry["entries"]
                assert isinstance(entries, list)
                if any(
                    item.get("id") == entry["id"]
                    for item in entries
                    if isinstance(item, dict)
                ):
                    raise ToolFailure(
                        "duplicate-history-entry",
                        "This exact minimized signature is already stored.",
                        registry_path,
                    )
                entries.append(entry)
                validate_registry_payload(registry, schema, registry_path)
                atomic_write(registry_path, registry)
            emit({
                "ok": True,
                "action": "added",
                "private": True,
                "user_certified": True,
                "investigate_only": True,
                "registry": str(registry_path),
                "id": entry["id"],
                "sensitive_warnings_acknowledged": bool(sensitive_warnings),
            })
            return 0

        if not 0 <= args.threshold <= 1:
            raise ToolFailure(
                "invalid-threshold",
                "Threshold must be from 0 through 1.",
            )
        registry = load_registry(registry_path, schema)
        entries = registry["entries"]
        assert isinstance(entries, list)
        matches = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            score, shared = similarity(signature, entry)
            if score >= args.threshold:
                matches.append({
                    "id": entry["id"],
                    "project_pseudonym": entry["project_pseudonym"],
                    "score": round(score, 4),
                    "shared_signals": shared,
                })
        matches.sort(key=lambda item: (-item["score"], item["id"]))
        emit({
            "ok": True,
            "action": "check",
            "private": True,
            "user_certified": True,
            "investigate_only": True,
            "message": (
                "Matches prompt rationale review; they never prove sameness "
                "or AI authorship."
            ),
            "registry": str(registry_path),
            "signature_warnings": sensitive_warnings,
            "matches": matches,
        })
        return 0
    except ToolFailure as exc:
        emit({"ok": False, "failures": [exc.issue.as_dict()]})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
