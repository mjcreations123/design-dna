#!/usr/bin/env python3
"""Detect Design DNA filesystem discovery candidates and collision risks."""

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

from jsonschema import Draft202012Validator, FormatChecker

from common import (
    ToolFailure,
    MAX_DISCOVERY_ENTRIES,
    absolute,
    assert_no_reparse_path,
    content_manifest,
    emit,
    is_reparse,
    is_within,
    load_json,
    skill_frontmatter,
    strict_format_checker,
)


def scan_scope() -> dict[str, object]:
    """Describe the bounded evidence produced by this filesystem scan."""
    return {
        "basis": "explicit-filesystem-root-scan",
        "root_scope": "explicit-roots-only",
        "activation_state": "not-verified",
        "project_admin_session_routes": "not-inspected",
        "limitations": [
            (
                "A discovered SKILL.md is a filesystem discovery candidate, "
                "not proof that a host activated it."
            ),
            (
                "Roots not passed with --root, including project-local, "
                "administrator-managed, and session-specific routes, were not scanned."
            ),
        ],
    }


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


def portable_home_path(path: Path, home: Path) -> str:
    path = absolute(path)
    home = absolute(home)
    if not is_within(path, home) or path == home:
        raise ToolFailure(
            "route-verification-path-not-home-relative",
            "Stored discovery and installed routes must be below the selected home.",
            path,
        )
    return "~/" + path.relative_to(home).as_posix()


def portable_canonical_path(path: Path) -> str:
    path = absolute(path)
    if (
        path.name != "design-dna"
        or path.parent.name != "skills"
    ):
        raise ToolFailure(
            "route-verification-canonical-not-package-relative",
            "Stored canonical identity requires the package route skills/design-dna.",
            path,
        )
    return "skills/design-dna"


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
    seen = 0
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
            seen += 1
            if seen > MAX_DISCOVERY_ENTRIES:
                raise ToolFailure(
                    "discovery-limit-exceeded",
                    "Discovery root exceeds the bounded scan limit.",
                    root,
                )
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
            seen += 1
            if seen > MAX_DISCOVERY_ENTRIES:
                raise ToolFailure(
                    "discovery-limit-exceeded",
                    "Discovery root exceeds the bounded scan limit.",
                    root,
                )
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
    parser.add_argument(
        "--root",
        action="append",
        type=Path,
        default=[],
        help="Filesystem discovery root to inspect; repeatable. Activation is not inferred.",
    )
    parser.add_argument(
        "--expected",
        action="append",
        type=Path,
        default=[],
        help="Expected managed filesystem candidate; repeatable.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Atomically write a successful machine-readable verification record.",
    )
    parser.add_argument(
        "--home",
        type=Path,
        help=(
            "Home root used to encode stored discovery and route paths as "
            "portable ~/ labels; required with --output."
        ),
    )
    args = parser.parse_args()
    try:
        canonical = absolute(args.canonical)
        roots = sorted({absolute(path) for path in args.root})
        expected = {absolute(path) for path in args.expected}
        if not roots:
            raise ToolFailure(
                "discovery-roots-required",
                (
                    "Pass every configured filesystem discovery root to include "
                    "in this bounded candidate scan."
                ),
            )
        if not expected:
            raise ToolFailure(
                "expected-routes-required",
                (
                    "Pass the complete intended managed candidate set for the "
                    "supplied filesystem discovery roots."
                ),
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
            assert_no_reparse_path(root)
            if not root.exists():
                warnings.append(
                    {
                        "code": "optional-discovery-root-absent",
                        "path": str(root),
                        "message": (
                            "Discovery root is absent and therefore contains "
                            "no Design DNA filesystem discovery candidate."
                        ),
                    }
                )
                continue
            if not root.is_dir():
                failures.append(
                    {
                        "code": "discovery-root-invalid",
                        "path": str(root),
                        "message": "Discovery root exists but is not a directory.",
                    }
                )
                continue
            discovered, root_warnings = discover(root)
            found.extend(discovered)
            warnings.extend(root_warnings)
        found = sorted(set(found))
        unexpected = [path for path in found if path not in expected]
        for path in unexpected:
            failures.append({
                "code": "unexpected-discovery-candidate",
                "path": str(path),
                "message": (
                    "Unexpected Design DNA filesystem discovery candidate. "
                    "Activation is not inferred; treat it as a fail-closed "
                    "collision risk."
                ),
            })
        missing = sorted(expected - set(found))
        for path in missing:
            failures.append(
                {
                    "code": "expected-route-missing",
                    "path": str(path),
                    "message": "Expected managed filesystem candidate was not discovered.",
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
            if args.home is None:
                raise ToolFailure(
                    "route-verification-home-required",
                    "--home is required when writing a portable verification record.",
                )
            home = absolute(args.home)
            assert_no_reparse_path(home)
            if not home.is_dir():
                raise ToolFailure(
                    "route-verification-home-invalid",
                    "The selected home root must be an existing directory.",
                    home,
                )
            canonical_label = portable_canonical_path(canonical)
            root_labels = [
                portable_home_path(path, home)
                for path in roots
            ]
            expected_labels = [
                portable_home_path(path, home)
                for path in sorted(expected)
            ]
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
                        "Filesystem discovery candidate changed during verification.",
                        route_path,
                    )
                stable_routes.append({
                    "path": portable_home_path(route_path, home),
                    "content_sha256": digest,
                    "matches_canonical": digest == canonical_hash,
                })
            record = {
                "schema_version": 3,
                "record_type": "design-dna-route-verification",
                "status": "passed",
                "verified_at": datetime.now(timezone.utc).isoformat().replace(
                    "+00:00",
                    "Z",
                ),
                "canonical": canonical_label,
                "scan_scope": scan_scope(),
                "roots": root_labels,
                "expected": expected_labels,
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
            "scan_scope": scan_scope(),
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
