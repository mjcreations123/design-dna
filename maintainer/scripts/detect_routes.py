#!/usr/bin/env python3
"""Detect duplicate active Design DNA discovery routes and stale nested copies."""

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
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from common import (
    ToolFailure,
    absolute,
    assert_no_reparse_path,
    content_manifest,
    emit,
    is_reparse,
    is_within,
    load_json,
    strict_format_checker,
)


def atomic_write_json(path: Path, payload: object) -> None:
    path = absolute(path)
    assert_no_reparse_path(path)
    assert_no_reparse_path(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    assert_no_reparse_path(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        assert_no_reparse_path(temporary, stop=path.parent)
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def validate_verification_record(payload: object) -> None:
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "schemas"
        / "route-verification.schema.json"
    )
    schema = load_json(schema_path)
    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=strict_format_checker(),
        ).iter_errors(payload),
        key=lambda item: tuple(str(part) for part in item.path),
    )
    if errors:
        message = "; ".join(
            f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ToolFailure(
            "route-verification-schema-invalid",
            message,
            schema_path,
        )


class NoDuplicateLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate keys at every mapping depth."""


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "mapping",
                node.start_mark,
                "unhashable mapping key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise yaml.constructor.ConstructorError(
                "mapping",
                node.start_mark,
                f"duplicate key: {key}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


NoDuplicateLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _mapping,
)


def skill_frontmatter(path: Path) -> dict[object, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ToolFailure("skill-route-read-failed", str(exc), path) from exc
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.S)
    if not match:
        raise ToolFailure(
            "invalid-skill-frontmatter",
            "SKILL.md must start with complete YAML frontmatter.",
            path,
        )
    try:
        metadata = yaml.load(match.group(1), Loader=NoDuplicateLoader)
    except yaml.YAMLError as exc:
        raise ToolFailure(
            "invalid-skill-frontmatter",
            str(exc),
            path,
        ) from exc
    if not isinstance(metadata, dict):
        raise ToolFailure(
            "invalid-skill-frontmatter",
            "SKILL.md frontmatter must be a mapping.",
            path,
        )
    name = metadata.get("name")
    if type(name) is not str:
        raise ToolFailure(
            "invalid-skill-name",
            "SKILL.md frontmatter name must be a string scalar.",
            path,
        )
    return metadata


def declares_design_dna(path: Path) -> bool:
    return skill_frontmatter(path).get("name") == "design-dna"


def plausibly_design_dna(path: Path) -> bool:
    """Fail closed only when an invalid entry could be this skill's route."""
    if path.parent.name.casefold() == "design-dna":
        return True
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ToolFailure("skill-route-read-failed", str(exc), path) from exc
    frontmatter = text
    if text.startswith("---"):
        closing = re.search(r"\r?\n---(?:\r?\n|\Z)", text[3:])
        if closing is not None:
            frontmatter = text[: closing.end() + 3]
    declared_names = re.findall(
        r"(?mi)^[ \t]*name[ \t]*:[ \t]*(.*?)[ \t]*$",
        frontmatter,
    )
    if len(declared_names) == 1:
        raw_name = declared_names[0].split(" #", 1)[0].strip()
        unquoted = raw_name.strip("\"'")
        if re.fullmatch(r"[A-Za-z0-9._-]+", unquoted):
            return unquoted.casefold() == "design-dna"
        return re.search(
            r"(?i)(?<![A-Za-z0-9-])design-dna(?![A-Za-z0-9-])",
            raw_name,
        ) is not None
    return any(
        re.search(
            r"(?i)(?<![A-Za-z0-9-])design-dna(?![A-Za-z0-9-])",
            raw_name,
        )
        is not None
        for raw_name in declared_names
    )


def discover(root: Path) -> tuple[list[Path], list[dict[str, str]]]:
    results: list[Path] = []
    warnings: list[dict[str, str]] = []
    safe_alias_targets: set[Path] = set()
    visited: set[Path] = set()
    if not root.exists():
        return results, warnings

    def fail_walk(error: OSError) -> None:
        raise ToolFailure(
            "tree-enumeration-failed",
            str(error),
            Path(error.filename) if error.filename else root,
        ) from error

    for current, directories, files in os.walk(
        root,
        topdown=True,
        followlinks=False,
        onerror=fail_walk,
    ):
        current_path = absolute(Path(current))
        visited.add(current_path)
        for name in list(directories):
            child = current_path / name
            if not is_reparse(child):
                continue
            directories.remove(name)
            if name.casefold() == "design-dna":
                raise ToolFailure(
                    "reparse-design-dna-route",
                    "A discoverable Design DNA route must not be a link or junction.",
                    child,
                )
            resolved = absolute(Path(os.path.realpath(child)))
            if not is_within(resolved, root) or not resolved.is_dir():
                raise ToolFailure(
                    "unsafe-reparse-discovery-subtree",
                    "A discovery-root alias resolves outside the scanned root or to a missing directory.",
                    child,
                )
            assert_no_reparse_path(resolved, stop=root)
            safe_alias_targets.add(resolved)
            warnings.append(
                {
                    "code": "reparse-alias-skipped",
                    "path": str(child),
                    "message": f"Skipped alias; its in-root target is scanned directly at {resolved}.",
                }
            )
        for name in files:
            path = current_path / name
            if is_reparse(path):
                if name.casefold() == "skill.md":
                    raise ToolFailure(
                        "reparse-skill-entry",
                        "A discoverable SKILL.md must not be a link.",
                        path,
                    )
                continue
            if name.casefold() == "skill.md":
                try:
                    is_design_dna = declares_design_dna(path)
                except ToolFailure as exc:
                    if (
                        exc.issue.code
                        not in {
                            "invalid-skill-frontmatter",
                            "invalid-skill-name",
                        }
                        or plausibly_design_dna(path)
                    ):
                        raise
                    warnings.append({
                        "code": "unrelated-invalid-skill-entry",
                        "path": str(path),
                        "message": (
                            "Skipped an invalid unrelated skill entry while "
                            f"checking Design DNA routes: {exc}"
                        ),
                    })
                    continue
                if is_design_dna:
                    results.append(path.parent)
    for target in sorted(safe_alias_targets):
        if target not in visited:
            raise ToolFailure(
                "reparse-target-not-scanned",
                "A skipped discovery alias did not have a separately scanned in-root target.",
                target,
            )
    return sorted(set(results)), warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--root", action="append", type=Path, default=[], help="Discovery root to inspect; repeatable.")
    parser.add_argument("--expected", action="append", type=Path, default=[], help="Allowed installed route; repeatable.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Atomically write a successful machine-readable verification record.",
    )
    args = parser.parse_args()
    try:
        canonical = absolute(args.canonical)
        roots = sorted({absolute(path) for path in args.root})
        expected = {absolute(path) for path in args.expected}
        if not roots:
            raise ToolFailure(
                "discovery-roots-required",
                "Pass every host discovery root that must contain exactly one Design DNA route.",
            )
        if not expected:
            raise ToolFailure(
                "expected-routes-required",
                "Pass the complete intended set of Design DNA routes for the supplied discovery roots.",
            )
        if not canonical.is_dir():
            raise ToolFailure(
                "canonical-route-missing",
                "Canonical Design DNA runtime directory does not exist.",
                canonical,
            )
        assert_no_reparse_path(canonical)
        canonical_entry = canonical / "SKILL.md"
        assert_no_reparse_path(canonical_entry, stop=canonical)
        if not canonical_entry.is_file():
            raise ToolFailure(
                "canonical-skill-entry-missing",
                "Canonical Design DNA runtime must contain SKILL.md.",
                canonical_entry,
            )
        if not declares_design_dna(canonical_entry):
            raise ToolFailure(
                "canonical-skill-identity-invalid",
                "Canonical SKILL.md must declare the exact scalar name design-dna.",
                canonical_entry,
            )

        for route in expected:
            containing = [
                root
                for root in roots
                if is_within(route, root)
            ]
            if not containing:
                raise ToolFailure(
                    "expected-route-outside-discovery-root",
                    "Each expected route must be contained by a supplied discovery root.",
                    route,
                )
            if route.name.casefold() != "design-dna":
                raise ToolFailure(
                    "invalid-expected-route-name",
                    "Each expected route must be named design-dna.",
                    route,
                )

        found: list[Path] = []
        failures: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        for root in roots:
            if not root.is_dir():
                failures.append(
                    {
                        "code": "discovery-root-missing",
                        "path": str(root),
                        "message": "Discovery root does not exist.",
                    }
                )
                continue
            assert_no_reparse_path(root)
            discovered, root_warnings = discover(root)
            found.extend(discovered)
            warnings.extend(root_warnings)
        found = sorted(set(found))
        unexpected = [path for path in found if path not in expected]
        for path in unexpected:
            failures.append({"code": "duplicate-active-route", "path": str(path), "message": "Unexpected discoverable design-dna skill."})
        missing = sorted(expected - set(found))
        for path in missing:
            failures.append(
                {
                    "code": "expected-route-missing",
                    "path": str(path),
                    "message": "Expected installed route was not discovered.",
                }
            )

        canonical_records, canonical_hash = content_manifest(canonical)
        routes = []
        for path in sorted(set(found)):
            if not path.is_dir():
                continue
            records, digest = content_manifest(path)
            matches = records == canonical_records
            routes.append({"path": str(path), "content_sha256": digest, "matches_canonical": matches})
            if path in expected and not matches:
                failures.append({"code": "installed-route-drift", "path": str(path), "message": f"{digest} != {canonical_hash}"})
        verification_output: str | None = None
        if args.output is not None and not failures:
            output = absolute(args.output)
            if is_within(output, canonical) or any(
                is_within(output, root)
                for root in roots
            ):
                raise ToolFailure(
                    "route-verification-output-overlaps-input",
                    "Verification output must be outside canonical and discovery roots.",
                    output,
                )
            stable_records, stable_hash = content_manifest(canonical)
            if (
                stable_records != canonical_records
                or stable_hash != canonical_hash
            ):
                raise ToolFailure(
                    "unstable-route-verification-input",
                    "Canonical content changed during route verification.",
                    canonical,
                )
            stable_routes = []
            for route in routes:
                route_path = absolute(Path(str(route["path"])))
                _records, digest = content_manifest(route_path)
                if digest != route["content_sha256"]:
                    raise ToolFailure(
                        "unstable-route-verification-input",
                        "Installed route changed during route verification.",
                        route_path,
                    )
                stable_routes.append({
                    "path": str(route_path),
                    "content_sha256": digest,
                    "matches_canonical": digest == canonical_hash,
                })
            record = {
                "schema_version": 1,
                "record_type": "design-dna-route-verification",
                "status": "passed",
                "verified_at": datetime.now(timezone.utc).isoformat().replace(
                    "+00:00",
                    "Z",
                ),
                "canonical": str(canonical),
                "roots": [str(path) for path in roots],
                "expected": [str(path) for path in sorted(expected)],
                "canonical_sha256": canonical_hash,
                "routes": stable_routes,
            }
            validate_verification_record(record)
            atomic_write_json(output, record)
            verification_output = str(output)
        emit({
            "ok": not failures,
            "canonical": str(canonical),
            "canonical_sha256": canonical_hash,
            "routes": routes,
            "failures": failures,
            "warnings": warnings,
            "verification_record": verification_output,
        })
        return 1 if failures else 0
    except ToolFailure as exc:
        emit({"ok": False, "failures": [exc.issue.as_dict()]})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
