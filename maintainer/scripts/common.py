"""Shared, defensive filesystem and result helpers for Design DNA maintenance."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlsplit

import yaml


PYTHON_CACHE_NAMES = {"__pycache__"}
PYTHON_CACHE_NAMES_CASEFOLD = {
    name.casefold() for name in PYTHON_CACHE_NAMES
}
COMPILED_PYTHON_SUFFIXES = {".pyc", ".pyo"}
MAX_DISCOVERY_ENTRIES = 100_000
EXCLUDED_NAMES = {
    *PYTHON_CACHE_NAMES,
    ".DS_Store",
    "Thumbs.db",
}
EXCLUDED_NAMES_CASEFOLD = {name.casefold() for name in EXCLUDED_NAMES}
EXCLUDED_SUFFIXES = COMPILED_PYTHON_SUFFIXES
LOCAL_TOOL_DIRECTORY_NAMES = frozenset({
    ".git",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "node_modules",
    "venv",
})
RFC3339_DATE_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
URI_WITH_SCHEME = re.compile(
    r"^[A-Za-z][A-Za-z0-9+.-]*:[^\s\x00-\x1f\x7f]+$"
)


@dataclass(frozen=True)
class ToolIssue:
    code: str
    message: str
    path: str | None = None
    severity: str = "error"

    def as_dict(self) -> dict[str, str]:
        result = {"code": self.code, "message": self.message, "severity": self.severity}
        if self.path:
            result["path"] = self.path
        return result


class ToolFailure(RuntimeError):
    def __init__(self, code: str, message: str, path: Path | None = None) -> None:
        super().__init__(message)
        self.issue = ToolIssue(code, message, str(path) if path else None)


class NoDuplicateYamlLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate keys at every mapping depth."""


def _strict_yaml_mapping(loader, node, deep=False):
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


NoDuplicateYamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _strict_yaml_mapping,
)


def skill_frontmatter(path: Path) -> dict[object, object]:
    """Load one skill entry's complete, duplicate-free YAML frontmatter."""

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
        metadata = yaml.load(match.group(1), Loader=NoDuplicateYamlLoader)
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


def strict_format_checker():
    """Return deterministic date, date-time, and URI validation.

    jsonschema intentionally treats formats as annotations when an optional
    validator is absent. Release validation must not silently become weaker
    because an extra package was not installed.
    """
    from jsonschema import FormatChecker

    checker = FormatChecker()

    def valid_date(value: object) -> bool:
        if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}",
            value,
        ):
            return False
        try:
            date.fromisoformat(value)
        except ValueError:
            return False
        return True

    def valid_date_time(value: object) -> bool:
        if not isinstance(value, str) or not RFC3339_DATE_TIME.fullmatch(value):
            return False
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        return parsed.tzinfo is not None and parsed.utcoffset() is not None

    def valid_uri(value: object) -> bool:
        if not isinstance(value, str) or not URI_WITH_SCHEME.fullmatch(value):
            return False
        try:
            parsed = urlsplit(value)
            if not parsed.scheme:
                return False
            if parsed.scheme.casefold() in {"http", "https"}:
                if not parsed.netloc or parsed.hostname is None:
                    return False
                _ = parsed.port
        except ValueError:
            return False
        return True

    checker.checks("date")(valid_date)
    checker.checks("date-time")(valid_date_time)
    checker.checks("uri")(valid_uri)
    return checker


def entry_exists(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ToolFailure("path-inspection-failed", str(exc), path) from exc


def is_reparse(path: Path) -> bool:
    """Return True only for path-redirection reparse points.

    Windows also marks hydrated/cloud-managed entries as reparse points. Those are data
    virtualization metadata, not name-surrogate redirects. Junctions, symlinks, and any
    other name-surrogate tag remain forbidden.
    """
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ToolFailure("path-inspection-failed", str(exc), path) from exc
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    if not attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        return False
    tag = getattr(info, "st_reparse_tag", 0)
    if tag:
        return bool(tag & 0x20000000) or tag in {0xA0000003, 0xA000000C}
    # Older runtimes that expose the attribute but not the tag cannot distinguish
    # virtualization metadata safely, so fail closed.
    return True


def absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def assert_contained(path: Path, root: Path, *, parent_must_exist: bool = True) -> None:
    path, root = absolute(path), absolute(root)
    if not is_within(path, root):
        raise ToolFailure("path-escape", "Path is outside the allowed root.", path)
    if parent_must_exist:
        resolved_root = root.resolve(strict=True)
        resolved_parent = path.parent.resolve(strict=True)
        if not is_within(resolved_parent, resolved_root):
            raise ToolFailure("resolved-path-escape", "Resolved path leaves the allowed root.", path)


def assert_no_reparse_path(path: Path, stop: Path | None = None) -> None:
    candidate = absolute(path)
    stop = absolute(stop) if stop else None
    while True:
        if entry_exists(candidate) and is_reparse(candidate):
            raise ToolFailure("reparse-point-refused", "Path contains a link, junction, or reparse point.", candidate)
        if candidate == stop or candidate.parent == candidate:
            return
        candidate = candidate.parent


def include(relative: Path) -> bool:
    return (
        not any(part.casefold() in EXCLUDED_NAMES_CASEFOLD for part in relative.parts)
        and relative.suffix.lower() not in EXCLUDED_SUFFIXES
    )


def walk_entries(
    root: Path,
    *,
    ignored_directory_names: set[str] | frozenset[str] | None = None,
) -> Iterable[Path]:
    root = absolute(root)
    if not root.is_dir():
        raise ToolFailure("root-not-found", "Directory does not exist.", root)
    assert_no_reparse_path(root)
    def fail_walk(error: OSError) -> None:
        raise ToolFailure(
            "tree-enumeration-failed",
            str(error),
            Path(error.filename) if error.filename else root,
        ) from error

    ignored = {
        name.casefold()
        for name in (ignored_directory_names or ())
    }
    for current, directories, files in os.walk(
        root,
        topdown=True,
        followlinks=False,
        onerror=fail_walk,
    ):
        current_path = Path(current)
        for name in list(directories):
            child = current_path / name
            if name.casefold() in ignored:
                directories.remove(name)
                continue
            if is_reparse(child):
                raise ToolFailure("reparse-point-refused", "Tree contains a link, junction, or reparse point.", child)
            if not include(child.relative_to(root)):
                directories.remove(name)
            else:
                yield child
        for name in files:
            child = current_path / name
            if is_reparse(child):
                raise ToolFailure("reparse-point-refused", "Tree contains a link, junction, or reparse point.", child)
            if include(child.relative_to(root)):
                yield child


def walk_eval_entries(root: Path) -> Iterable[Path]:
    """Walk every evaluation entry without release-manifest exclusions.

    Evaluation inputs, workspaces, and retained artifacts are evidence. Transient
    names such as ``__pycache__`` and compiled Python files must therefore remain
    observable even though they are intentionally omitted from runtime release
    identities.
    """
    root = absolute(root)
    if not root.is_dir():
        raise ToolFailure("root-not-found", "Directory does not exist.", root)
    assert_no_reparse_path(root)

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
        current_path = Path(current)
        for name in directories:
            child = current_path / name
            if is_reparse(child):
                raise ToolFailure(
                    "reparse-point-refused",
                    "Evaluation tree contains a link, junction, or reparse point.",
                    child,
                )
            yield child
        for name in files:
            child = current_path / name
            if is_reparse(child):
                raise ToolFailure(
                    "reparse-point-refused",
                    "Evaluation tree contains a link, junction, or reparse point.",
                    child,
                )
            yield child


def compiled_python_residue_paths(root: Path) -> list[Path]:
    """Return cache directories and standalone compiled Python files.

    Release identities intentionally omit these generated entries. Executable
    trees must inspect them separately so an unhashed bytecode artifact cannot
    be present during audit, test attestation, or manifest construction.
    A cache directory represents the compiled files beneath it, avoiding a
    duplicate failure for every file in one cache.
    """
    root = absolute(root)
    residue: list[Path] = []
    for path in walk_eval_entries(root):
        relative = path.relative_to(root)
        if (
            path.is_dir()
            and path.name.casefold() in PYTHON_CACHE_NAMES_CASEFOLD
        ):
            residue.append(path)
            continue
        if (
            path.is_file()
            and path.suffix.casefold() in COMPILED_PYTHON_SUFFIXES
            and not any(
                part.casefold() in PYTHON_CACHE_NAMES_CASEFOLD
                for part in relative.parts[:-1]
            )
        ):
            residue.append(path)
    return sorted(
        residue,
        key=lambda path: path.relative_to(root).as_posix().casefold(),
    )


def reject_compiled_python_residue(
    roots: Iterable[Path],
    *,
    code: str,
    message: str,
) -> None:
    """Fail on the first unhashed compiled artifact in executable roots."""
    for root in roots:
        residue = compiled_python_residue_paths(root)
        if residue:
            raise ToolFailure(code, message, residue[0])


def walk_files(
    root: Path,
    *,
    ignored_directory_names: set[str] | frozenset[str] | None = None,
) -> Iterable[Path]:
    for path in walk_entries(
        root,
        ignored_directory_names=ignored_directory_names,
    ):
        if path.is_file():
            yield path


def walk_eval_files(root: Path) -> Iterable[Path]:
    for path in walk_eval_entries(root):
        if path.is_file():
            yield path


def entry_record(path: Path, root: Path) -> dict[str, object]:
    try:
        if path.is_dir():
            return {
                "path": path.relative_to(root).as_posix(),
                "type": "directory",
                "size": 0,
                "sha256": None,
            }
        data = path.read_bytes()
        return {
            "path": path.relative_to(root).as_posix(),
            "type": "file",
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    except (OSError, UnicodeError) as exc:
        raise ToolFailure("tree-entry-read-failed", str(exc), path) from exc


def _content_manifest(
    root: Path,
    walker: Callable[[Path], Iterable[Path]],
) -> tuple[list[dict[str, object]], str]:
    root = absolute(root)
    records = [entry_record(path, root) for path in walker(root)]
    records.sort(key=lambda item: str(item["path"]))
    verification = [entry_record(path, root) for path in walker(root)]
    verification.sort(key=lambda item: str(item["path"]))
    if records != verification:
        raise ToolFailure(
            "unstable-tree",
            "Directory content changed while its identity was being calculated.",
            root,
        )
    digest = hashlib.sha256()
    for record in records:
        digest.update(str(record["path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(record["type"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(record["size"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(record["sha256"] or "").encode("ascii"))
        digest.update(b"\0")
    return records, digest.hexdigest()


def content_manifest(root: Path) -> tuple[list[dict[str, object]], str]:
    """Hash runtime content while omitting known generated cache residue."""
    return _content_manifest(root, walk_entries)


def eval_content_manifest(root: Path) -> tuple[list[dict[str, object]], str]:
    """Hash every evaluation entry, including caches and empty directories."""
    return _content_manifest(root, walk_eval_entries)


def load_json(path: Path) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ToolFailure("invalid-json", str(exc), path) from exc


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))
