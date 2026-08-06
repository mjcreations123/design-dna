#!/usr/bin/env python3
"""Safely manage personal Design DNA installs for Codex and Claude."""

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
import secrets
import shutil
import stat
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Callable, Iterable, Iterator

from jsonschema import Draft202012Validator, FormatChecker

_SCRIPT_DIRECTORY = str(Path(__file__).resolve().parent)
if _SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, _SCRIPT_DIRECTORY)
from common import MAX_DISCOVERY_ENTRIES, ToolFailure, skill_frontmatter


sys.dont_write_bytecode = True

OPERATION_SCHEMA_VERSION = 2
BACKUP_SCHEMA_VERSION = 1
RECORD_TYPE = "design-dna-install-operation"
BACKUP_RECORD_TYPE = "design-dna-install-backup"
INSTALL_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "install-operation.schema.json"
)
INSTALL_FORMAT_CHECKER = FormatChecker()


@INSTALL_FORMAT_CHECKER.checks("date-time")
def valid_rfc3339_datetime(value: object) -> bool:
    if not isinstance(value, str) or not value or " " in value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None
MAX_SKILL_ENTRIES = 25_000
IGNORED_NAMES = {"__pycache__", ".DS_Store", "Thumbs.db"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
BACKUP_ID_PATTERN = re.compile(r"^[0-9]{8}T[0-9]{6}\.[0-9]{6}Z-[a-f0-9]{12}$")
HARD_EXIT_POINTS = (
    "install-after-new-target",
    "update-before-new-target",
    "update-after-new-target",
    "uninstall-after-target",
    "rollback-after-restored-target",
)
HARD_EXIT_CODE = 86


def visibility_scope() -> dict[str, object]:
    """Describe exactly what host route discovery can and cannot establish."""
    return {
        "basis": "configured-filesystem-scan",
        "root_scope": "configured-global-roots-only",
        "activation_state": "not-verified",
        "project_admin_session_routes": "not-inspected",
        "limitations": [
            (
                "A discovered SKILL.md is a filesystem discovery candidate, "
                "not proof that the host activated it."
            ),
            (
                "Only the configured global roots were scanned; project-local, "
                "administrator-managed, and current-session visibility are "
                "outside this result."
            ),
        ],
    }


class ManagerError(RuntimeError):
    """One stable, machine-readable manager failure."""

    def __init__(
        self,
        code: str,
        message: str,
        path: Path | None = None,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = str(path) if path is not None else None
        self.details = details

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "code": self.code,
            "message": self.message,
        }
        if self.path is not None:
            result["path"] = self.path
        if self.details:
            result["details"] = self.details
        return result


class JsonArgumentParser(argparse.ArgumentParser):
    """Keep command-line failures on the same JSON contract as runtime failures."""

    def error(self, message: str) -> None:
        raise ManagerError("invalid-arguments", message)


@dataclass(frozen=True)
class HostConfig:
    host: str
    safety_root: Path
    target: Path
    discovery_roots: tuple[Path, ...]
    backup_root: Path


@dataclass(frozen=True)
class TreeIdentity:
    records: tuple[tuple[str, str, int, str], ...]
    sha256: str
    entries: int
    files: int
    bytes: int

    def as_dict(self, path: Path) -> dict[str, object]:
        return {
            "path": str(path),
            "sha256": self.sha256,
            "entry_count": self.entries,
            "file_count": self.files,
            "byte_count": self.bytes,
        }


@dataclass(frozen=True)
class Backup:
    backup_id: str
    path: Path
    skill: Path
    metadata: dict[str, object]
    identity: TreeIdentity | None


@dataclass
class AppliedChange:
    payload: dict[str, object]
    undo: Callable[[], None]


@dataclass(frozen=True)
class RecoveryStep:
    action: str
    path: Path
    destination: Path | None = None
    backup_id: str | None = None


@dataclass(frozen=True)
class RecoveryPlan:
    config: HostConfig
    steps: tuple[RecoveryStep, ...]
    projected_target: TreeIdentity | None


def absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def entry_exists(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ManagerError("path-inspection-failed", str(exc), path) from exc


def is_reparse(path: Path) -> bool:
    """Identify path-redirection reparse points without rejecting cloud files."""

    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ManagerError("path-inspection-failed", str(exc), path) from exc
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    if not attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        return False
    tag = getattr(info, "st_reparse_tag", 0)
    if tag:
        return bool(tag & 0x20000000) or tag in {0xA0000003, 0xA000000C}
    return True


def is_within(path: Path, root: Path) -> bool:
    path_value = path_key(path)
    root_value = path_key(root)
    try:
        return os.path.commonpath([path_value, root_value]) == root_value
    except ValueError:
        return False


def paths_overlap(first: Path, second: Path) -> bool:
    return is_within(first, second) or is_within(second, first)


def assert_contained(path: Path, root: Path, *, allow_equal: bool = False) -> None:
    if not is_within(path, root) or (not allow_equal and path_key(path) == path_key(root)):
        raise ManagerError(
            "unsafe-containment",
            "The path is outside its allowed root.",
            path,
            details={"allowed_root": str(root)},
        )


def assert_no_reparse_path(path: Path, *, stop: Path | None = None) -> None:
    candidate = absolute(path)
    stopping = absolute(stop) if stop is not None else None
    if stopping is not None and not is_within(candidate, stopping):
        raise ManagerError("unsafe-containment", "The checked path is outside its safety root.", candidate)
    while True:
        if entry_exists(candidate) and is_reparse(candidate):
            raise ManagerError(
                "reparse-point-refused",
                "Links, junctions, and path-redirection reparse points are not allowed.",
                candidate,
            )
        if candidate == stopping or candidate.parent == candidate:
            return
        candidate = candidate.parent


def same_volume(first: Path, second: Path) -> bool:
    first_drive = os.path.splitdrive(str(first))[0].casefold()
    second_drive = os.path.splitdrive(str(second))[0].casefold()
    if first_drive or second_drive:
        return first_drive == second_drive

    def existing_ancestor(path: Path) -> Path:
        candidate = path
        while not entry_exists(candidate) and candidate.parent != candidate:
            candidate = candidate.parent
        return candidate

    try:
        return existing_ancestor(first).stat().st_dev == existing_ancestor(second).stat().st_dev
    except OSError as exc:
        raise ManagerError("volume-inspection-failed", str(exc)) from exc


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def new_backup_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return f"{stamp}-{secrets.token_hex(6)}"


def maybe_hard_exit(selected: str | None, point: str) -> None:
    """Terminate without unwinding so subprocess tests exercise real residue."""

    if selected == point:
        os._exit(HARD_EXIT_CODE)


def ignored(relative: Path) -> bool:
    return (
        any(part in IGNORED_NAMES for part in relative.parts)
        or relative.suffix.casefold() in IGNORED_SUFFIXES
    )


def scan_tree(root: Path) -> tuple[tuple[str, str, int, str], ...]:
    root = absolute(root)
    if not root.is_dir():
        raise ManagerError("skill-directory-not-found", "Skill directory does not exist.", root)
    assert_no_reparse_path(root)
    records: list[tuple[str, str, int, str]] = []
    seen = 0

    def walk_error(error: OSError) -> None:
        raise ManagerError(
            "tree-enumeration-failed",
            str(error),
            Path(error.filename) if error.filename else root,
        ) from error

    for current, directories, files in os.walk(
        root,
        topdown=True,
        followlinks=False,
        onerror=walk_error,
    ):
        current_path = Path(current)
        directories.sort(key=str.casefold)
        files.sort(key=str.casefold)
        for name in list(directories):
            child = current_path / name
            relative = child.relative_to(root)
            seen += 1
            if seen > MAX_SKILL_ENTRIES:
                raise ManagerError("skill-tree-too-large", "Skill tree exceeds the safety entry limit.", root)
            if is_reparse(child):
                raise ManagerError("reparse-point-refused", "Skill tree contains a redirected directory.", child)
            if name == "__pycache__":
                raise ManagerError(
                    "compiled-python-residue",
                    "Compiled Python cache directories are forbidden in managed skill trees.",
                    child,
                )
            if ignored(relative):
                directories.remove(name)
                continue
            records.append((relative.as_posix(), "directory", 0, ""))
        for name in files:
            child = current_path / name
            relative = child.relative_to(root)
            seen += 1
            if seen > MAX_SKILL_ENTRIES:
                raise ManagerError("skill-tree-too-large", "Skill tree exceeds the safety entry limit.", root)
            if is_reparse(child):
                raise ManagerError("reparse-point-refused", "Skill tree contains a redirected file.", child)
            if child.suffix.casefold() in IGNORED_SUFFIXES:
                raise ManagerError(
                    "compiled-python-residue",
                    "Compiled Python files are forbidden in managed skill trees.",
                    child,
                )
            if ignored(relative):
                continue
            try:
                info = child.stat()
                if not stat.S_ISREG(info.st_mode):
                    raise ManagerError(
                        "unsupported-tree-entry",
                        "Only regular files and directories are allowed in managed skills.",
                        child,
                    )
                data = child.read_bytes()
            except ManagerError:
                raise
            except OSError as exc:
                raise ManagerError("tree-entry-read-failed", str(exc), child) from exc
            records.append(
                (
                    relative.as_posix(),
                    "file",
                    len(data),
                    hashlib.sha256(data).hexdigest(),
                )
            )
    records.sort(key=lambda item: item[0])
    return tuple(records)


def tree_identity(root: Path) -> TreeIdentity:
    first = scan_tree(root)
    second = scan_tree(root)
    if first != second:
        raise ManagerError(
            "unstable-tree",
            "Directory content changed while its identity was being calculated.",
            root,
        )
    digest = hashlib.sha256()
    file_count = 0
    byte_count = 0
    for relative, kind, size, file_hash in first:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(kind.encode("ascii"))
        digest.update(b"\0")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\0")
        if kind == "file":
            file_count += 1
            byte_count += size
    return TreeIdentity(
        records=first,
        sha256=digest.hexdigest(),
        entries=len(first),
        files=file_count,
        bytes=byte_count,
    )


def parse_skill_name(skill_file: Path) -> str:
    try:
        metadata = skill_frontmatter(skill_file)
    except ToolFailure as exc:
        issue = exc.issue
        raise ManagerError(
            issue.code,
            issue.message,
            Path(issue.path) if issue.path is not None else skill_file,
        ) from exc
    return str(metadata["name"])


def validate_design_dna_tree(path: Path) -> TreeIdentity:
    skill_file = path / "SKILL.md"
    if not skill_file.is_file():
        raise ManagerError("skill-entry-missing", "Managed skill must contain SKILL.md.", skill_file)
    if parse_skill_name(skill_file) != "design-dna":
        raise ManagerError(
            "wrong-skill-name",
            "Managed SKILL.md must declare the exact name design-dna.",
            skill_file,
        )
    return tree_identity(path)


def copy_exact(source: Path, destination: Path) -> None:
    if entry_exists(destination):
        raise ManagerError("staging-path-exists", "Staging destination already exists.", destination)
    destination.mkdir()
    for relative, kind, _size, _file_hash in tree_identity(source).records:
        source_entry = source / Path(relative)
        target_entry = destination / Path(relative)
        if kind == "directory":
            target_entry.mkdir(exist_ok=False)
        else:
            target_entry.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(source_entry, target_entry, follow_symlinks=False)
            except OSError as exc:
                raise ManagerError("staging-copy-failed", str(exc), source_entry) from exc


def atomic_write_json(path: Path, payload: object) -> None:
    assert_no_reparse_path(path, stop=path.parent)
    temporary = path.parent / f".{path.name}.tmp-{secrets.token_hex(6)}"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise ManagerError("json-write-failed", str(exc), path) from exc
    finally:
        if entry_exists(temporary):
            try:
                temporary.unlink()
            except OSError:
                pass


def emit(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def acquire_file_lock(stream: BinaryIO) -> None:
    stream.seek(0, os.SEEK_END)
    if stream.tell() == 0:
        stream.write(b"\0")
        stream.flush()
        os.fsync(stream.fileno())
    stream.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError) as exc:
        raise ManagerError(
            "operation-locked",
            "Another Design DNA installation transaction is active.",
        ) from exc


def release_file_lock(stream: BinaryIO) -> None:
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def operation_lock(backup_base: Path, home: Path) -> Iterator[None]:
    assert_contained(backup_base, home)
    assert_no_reparse_path(backup_base, stop=home)
    try:
        backup_base.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ManagerError(
            "lock-directory-create-failed",
            str(exc),
            backup_base,
        ) from exc
    assert_no_reparse_path(backup_base, stop=home)
    lock_path = backup_base / ".install-operation.lock"
    assert_contained(lock_path, backup_base)
    assert_no_reparse_path(lock_path, stop=backup_base)
    try:
        stream = lock_path.open("a+b")
    except OSError as exc:
        raise ManagerError("operation-lock-unavailable", str(exc), lock_path) from exc
    try:
        acquire_file_lock(stream)
        yield
    finally:
        try:
            release_file_lock(stream)
        except OSError:
            pass
        stream.close()


def host_configs(
    home: Path,
    backup_base: Path,
    claude_config_dir: Path | None = None,
) -> dict[str, HostConfig]:
    default_claude_root = home / ".claude"
    claude_root = (
        absolute(claude_config_dir)
        if claude_config_dir is not None
        else default_claude_root
    )
    claude_backup_root = (
        backup_base / "claude"
        if path_key(claude_root) == path_key(default_claude_root)
        else (
            backup_base
            / "claude-configs"
            / hashlib.sha256(
                path_key(claude_root).encode("utf-8")
            ).hexdigest()[:16]
        )
    )
    return {
        "codex": HostConfig(
            host="codex",
            safety_root=home,
            target=home / ".agents" / "skills" / "design-dna",
            discovery_roots=(
                home / ".agents" / "skills",
                home / ".codex" / "skills",
                home / ".codex" / "plugins" / "cache",
            ),
            backup_root=backup_base / "codex",
        ),
        "claude": HostConfig(
            host="claude",
            safety_root=claude_root,
            target=claude_root / "skills" / "design-dna",
            discovery_roots=(
                claude_root / "skills",
                claude_root / "plugins" / "cache",
            ),
            backup_root=claude_backup_root,
        ),
    }


def assert_layout_safe(
    home: Path,
    source: Path,
    backup_base: Path,
    configs: Iterable[HostConfig],
) -> None:
    if not home.is_dir():
        raise ManagerError("home-not-found", "The selected home directory does not exist.", home)
    assert_no_reparse_path(home)
    assert_contained(backup_base, home)
    assert_no_reparse_path(backup_base, stop=home)
    for config in configs:
        if config.safety_root.parent == config.safety_root:
            raise ManagerError(
                "unsafe-config-root",
                "A host configuration root cannot be a filesystem root.",
                config.safety_root,
            )
        assert_no_reparse_path(config.safety_root)
        assert_contained(config.target, config.safety_root)
        if config.target.name != "design-dna" or config.target.parent not in config.discovery_roots:
            raise ManagerError("unsafe-target-layout", "Managed target is not an exact supported route.", config.target)
        assert_no_reparse_path(config.target, stop=config.safety_root)
        assert_contained(config.backup_root, home)
        assert_no_reparse_path(config.backup_root, stop=home)
        if not same_volume(config.target, config.backup_root):
            raise ManagerError(
                "cross-volume-transaction-refused",
                "Target and backup roots must share a volume for atomic renames.",
                config.backup_root,
            )
        for root in config.discovery_roots:
            assert_contained(root, config.safety_root)
            assert_no_reparse_path(root, stop=config.safety_root)
            if paths_overlap(backup_base, root):
                raise ManagerError(
                    "unsafe-backup-root",
                    "Backup storage must be outside every host discovery root.",
                    backup_base,
                    details={"discovery_root": str(root)},
                )
            if paths_overlap(source, root):
                raise ManagerError(
                    "overlapping-source-discovery",
                    "Canonical source must be outside every installed-skill discovery root.",
                    source,
                    details={"discovery_root": str(root)},
                )
    if paths_overlap(source, backup_base):
        raise ManagerError(
            "overlapping-source-backups",
            "Canonical source and backup storage must not overlap.",
            backup_base,
        )


def discover(root: Path) -> list[Path]:
    root = absolute(root)
    if not entry_exists(root):
        return []
    if not root.is_dir():
        raise ManagerError("invalid-discovery-root", "Discovery root is not a directory.", root)
    assert_no_reparse_path(root)
    routes: list[Path] = []
    safe_alias_targets: dict[str, Path] = {}
    visited: set[str] = set()
    seen = 0

    def walk_error(error: OSError) -> None:
        raise ManagerError(
            "discovery-failed",
            str(error),
            Path(error.filename) if error.filename else root,
        ) from error

    for current, directories, files in os.walk(
        root,
        topdown=True,
        followlinks=False,
        onerror=walk_error,
    ):
        current_path = Path(current)
        visited.add(path_key(current_path))
        directories.sort(key=str.casefold)
        files.sort(key=str.casefold)
        for name in list(directories):
            seen += 1
            child = current_path / name
            if seen > MAX_DISCOVERY_ENTRIES:
                raise ManagerError(
                    "discovery-limit-exceeded",
                    "Discovery root exceeds the bounded scan limit.",
                    root,
                )
            if is_reparse(child):
                directories.remove(name)
                if name.casefold() == "design-dna":
                    raise ManagerError(
                        "reparse-point-refused",
                        "A discoverable Design DNA route may not be a link or junction.",
                        child,
                    )
                resolved = absolute(Path(os.path.realpath(child)))
                if not is_within(resolved, root) or not resolved.is_dir():
                    raise ManagerError(
                        "unsafe-discovery-alias",
                        "A skipped discovery alias must resolve to an ordinary directory inside the same root.",
                        child,
                        details={"resolved_path": str(resolved)},
                    )
                assert_no_reparse_path(resolved, stop=root)
                safe_alias_targets[path_key(resolved)] = resolved
        for name in files:
            seen += 1
            path = current_path / name
            if seen > MAX_DISCOVERY_ENTRIES:
                raise ManagerError(
                    "discovery-limit-exceeded",
                    "Discovery root exceeds the bounded scan limit.",
                    root,
                )
            if is_reparse(path):
                if name.casefold() == "skill.md":
                    raise ManagerError(
                        "reparse-point-refused",
                        "A discoverable SKILL.md may not be a link.",
                        path,
                    )
                continue
            if name.casefold() != "skill.md":
                continue
            try:
                declared_name = parse_skill_name(path)
            except ManagerError:
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    text = ""
                if path.parent.name.casefold() == "design-dna" or re.search(
                    r"(?i)(?<![A-Za-z0-9-])design-dna(?![A-Za-z0-9-])",
                    text[:16_384],
                ):
                    raise
                continue
            if declared_name == "design-dna":
                routes.append(absolute(path.parent))
    unvisited_alias_targets = [
        str(path)
        for key, path in sorted(safe_alias_targets.items())
        if key not in visited
    ]
    if unvisited_alias_targets:
        raise ManagerError(
            "unverified-discovery-alias",
            "A skipped discovery alias did not have an independently scanned in-root target.",
            root,
            details={"targets": unvisited_alias_targets},
        )
    unique = {path_key(path): path for path in routes}
    return [unique[key] for key in sorted(unique)]


def route_record(
    path: Path,
    expected: Path,
    canonical: TreeIdentity,
) -> dict[str, object]:
    identity = validate_design_dna_tree(path)
    return {
        "path": str(path),
        "expected": path_key(path) == path_key(expected),
        "candidate_kind": (
            "managed-direct-target"
            if path_key(path) == path_key(expected)
            else "unmanaged-filesystem-candidate"
        ),
        "sha256": identity.sha256,
        "parity": identity.records == canonical.records,
        "entry_count": identity.entries,
        "file_count": identity.files,
        "byte_count": identity.bytes,
    }


def load_json(path: Path) -> object:
    def no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ManagerError("invalid-backup-record", str(exc), path) from exc


def validate_install_record(payload: object, path: Path) -> None:
    try:
        schema = load_json(INSTALL_SCHEMA_PATH)
        errors = sorted(
            Draft202012Validator(
                schema,
                format_checker=INSTALL_FORMAT_CHECKER,
            ).iter_errors(payload),
            key=lambda item: tuple(str(part) for part in item.absolute_path),
        )
    except ManagerError:
        raise
    except Exception as exc:
        raise ManagerError(
            "install-schema-unavailable",
            str(exc),
            INSTALL_SCHEMA_PATH,
        ) from exc
    if errors:
        details = "; ".join(
            (
                f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: "
                f"{error.message}"
            )
            for error in errors[:12]
        )
        raise ManagerError(
            "invalid-backup-record",
            details,
            path,
        )


def backup_metadata(
    *,
    backup_id: str,
    host: str,
    target: Path,
    reason: str,
    skill_identity: TreeIdentity,
    canonical_sha256: str,
    status: str = "available",
) -> dict[str, object]:
    return {
        "schema_version": BACKUP_SCHEMA_VERSION,
        "record_type": BACKUP_RECORD_TYPE,
        "backup_id": backup_id,
        "host": host,
        "created_at": utc_now(),
        "reason": reason,
        "status": status,
        "target": str(target),
        "canonical_sha256": canonical_sha256,
        "skill_sha256": skill_identity.sha256,
        "entry_count": skill_identity.entries,
        "file_count": skill_identity.files,
        "byte_count": skill_identity.bytes,
    }


def validate_backup(config: HostConfig, path: Path) -> Backup:
    assert_contained(path, config.backup_root)
    assert_no_reparse_path(path, stop=config.backup_root)
    if not path.is_dir() or not BACKUP_ID_PATTERN.fullmatch(path.name):
        raise ManagerError("invalid-backup-entry", "Backup entry has an unsafe name or type.", path)
    metadata_path = path / "operation.json"
    payload = load_json(metadata_path)
    if not isinstance(payload, dict):
        raise ManagerError("invalid-backup-record", "Backup metadata must be a JSON object.", metadata_path)
    validate_install_record(payload, metadata_path)
    required = {
        "schema_version": int,
        "record_type": str,
        "backup_id": str,
        "host": str,
        "created_at": str,
        "reason": str,
        "status": str,
        "target": str,
        "canonical_sha256": str,
        "skill_sha256": str,
        "entry_count": int,
        "file_count": int,
        "byte_count": int,
    }
    for key, expected_type in required.items():
        if key not in payload or type(payload[key]) is not expected_type:
            raise ManagerError(
                "invalid-backup-record",
                f"Backup metadata field {key!r} is missing or has the wrong type.",
                metadata_path,
            )
    if (
        payload["schema_version"] != BACKUP_SCHEMA_VERSION
        or payload["record_type"] != BACKUP_RECORD_TYPE
        or payload["backup_id"] != path.name
        or payload["host"] != config.host
        or path_key(Path(str(payload["target"]))) != path_key(config.target)
        or not re.fullmatch(r"[a-f0-9]{64}", str(payload["canonical_sha256"]))
        or not re.fullmatch(r"[a-f0-9]{64}", str(payload["skill_sha256"]))
        or payload["status"] not in {"available", "restored", "failed", "transaction-rolled-back"}
    ):
        raise ManagerError("invalid-backup-record", "Backup metadata violates route or identity invariants.", metadata_path)
    skill = path / "skill"
    status = str(payload["status"])
    identity: TreeIdentity | None = None
    if status in {"available", "failed"}:
        if not skill.is_dir():
            raise ManagerError("backup-payload-missing", "Recoverable backup is missing its skill tree.", skill)
        identity = validate_design_dna_tree(skill)
        if (
            identity.sha256 != payload["skill_sha256"]
            or identity.entries != payload["entry_count"]
            or identity.files != payload["file_count"]
            or identity.bytes != payload["byte_count"]
        ):
            raise ManagerError(
                "backup-parity-mismatch",
                "Backup content no longer matches its recorded identity.",
                skill,
            )
    elif entry_exists(skill):
        raise ManagerError(
            "invalid-backup-record",
            "A consumed backup record unexpectedly still contains a skill payload.",
            skill,
        )
    return Backup(
        backup_id=path.name,
        path=path,
        skill=skill,
        metadata=payload,
        identity=identity,
    )


def list_backups(config: HostConfig) -> list[Backup]:
    if not entry_exists(config.backup_root):
        return []
    if not config.backup_root.is_dir():
        raise ManagerError("invalid-backup-root", "Backup root is not a directory.", config.backup_root)
    assert_no_reparse_path(config.backup_root)
    backups: list[Backup] = []
    for entry in sorted(config.backup_root.iterdir(), key=lambda item: item.name.casefold()):
        if is_reparse(entry):
            raise ManagerError("reparse-point-refused", "Backup storage contains a redirected entry.", entry)
        if entry.name == ".install-operation.lock":
            if not entry.is_file():
                raise ManagerError(
                    "invalid-operation-lock",
                    "The installation lock path is not an ordinary file.",
                    entry,
                )
            continue
        if entry.name.startswith((".stage-", ".pending-")):
            raise ManagerError(
                "incomplete-transaction",
                "Backup storage contains unresolved transaction residue.",
                entry,
            )
        backups.append(validate_backup(config, entry))
    return backups


def inspect_host(config: HostConfig, canonical: TreeIdentity) -> dict[str, object]:
    discovered: dict[str, Path] = {}
    for root in config.discovery_roots:
        for route in discover(root):
            discovered[path_key(route)] = route
    candidates = [
        route_record(discovered[key], config.target, canonical)
        for key in sorted(discovered)
    ]
    unexpected = [
        record
        for record in candidates
        if not bool(record["expected"])
    ]
    collision_candidates = (
        [str(record["path"]) for record in candidates]
        if len(candidates) > 1
        else []
    )
    target_exists = entry_exists(config.target)
    target_record = next(
        (record for record in candidates if bool(record["expected"])),
        None,
    )
    if target_exists and target_record is None:
        raise ManagerError(
            "occupied-invalid-target",
            "The supported route exists but is not a valid Design DNA skill.",
            config.target,
        )
    backups = list_backups(config)
    available = [
        {
            "backup_id": backup.backup_id,
            "path": str(backup.path),
            "created_at": backup.metadata["created_at"],
            "reason": backup.metadata["reason"],
            "sha256": backup.metadata["skill_sha256"],
        }
        for backup in backups
        if backup.metadata["status"] == "available"
    ]
    if collision_candidates:
        status = "candidate-collision"
        recommendation = (
            "The configured filesystem roots contain multiple Design DNA "
            "discovery candidates. Confirm host plugin state, then remove or "
            "relocate every unintended candidate before rerunning doctor."
        )
    elif unexpected:
        if bool(unexpected[0]["parity"]):
            status = "external-candidate-current"
            recommendation = (
                "One current packaged or externally managed filesystem candidate "
                "is present. Activation was not verified; inspect the host plugin "
                "manager before updating or removing it. Direct install remains "
                "blocked fail-closed."
            )
        else:
            status = "external-candidate-stale"
            recommendation = (
                "One stale packaged or externally managed filesystem candidate "
                "is present. Activation was not verified; inspect the host plugin "
                "manager before updating or removing it. Direct install remains "
                "blocked fail-closed."
            )
    elif not target_exists:
        status = "install-needed"
        recommendation = f"Run install for host {config.host}."
    elif target_record and bool(target_record["parity"]):
        status = "healthy"
        recommendation = "No action required."
    else:
        status = "update-needed"
        recommendation = f"Run update for host {config.host}; the prior tree will be backed up."
    return {
        "host": config.host,
        "expected_route": str(config.target),
        "discovery_roots": [str(path) for path in config.discovery_roots],
        "visibility_scope": visibility_scope(),
        "backup_root": str(config.backup_root),
        "discovery_candidates": candidates,
        "collision_candidates": collision_candidates,
        "target": {
            "exists": target_exists,
            "sha256": target_record["sha256"] if target_record else None,
            "parity": bool(target_record["parity"]) if target_record else False,
        },
        "available_backups": available,
        "status": status,
        "recommendation": recommendation,
    }


def ensure_mutation_directories(config: HostConfig, home: Path) -> None:
    assert_no_reparse_path(config.target.parent, stop=config.safety_root)
    assert_no_reparse_path(config.backup_root, stop=home)
    try:
        config.target.parent.mkdir(parents=True, exist_ok=True)
        config.backup_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ManagerError("directory-create-failed", str(exc), config.target.parent) from exc
    assert_no_reparse_path(config.target.parent, stop=config.safety_root)
    assert_no_reparse_path(config.backup_root, stop=home)


def safe_remove_stage(path: Path, backup_root: Path) -> None:
    if not entry_exists(path):
        return
    assert_contained(path, backup_root)
    if not path.name.startswith((".stage-", ".pending-")):
        raise ManagerError("broad-deletion-refused", "Only exact transaction staging paths may be removed.", path)
    assert_no_reparse_path(path, stop=backup_root)
    try:
        shutil.rmtree(path)
    except OSError as exc:
        raise ManagerError("staging-cleanup-failed", str(exc), path) from exc


def validate_backup_metadata(
    config: HostConfig,
    path: Path,
    *,
    backup_id: str,
) -> dict[str, object]:
    metadata_path = path / "operation.json"
    payload = load_json(metadata_path)
    if not isinstance(payload, dict):
        raise ManagerError(
            "invalid-backup-record",
            "Backup metadata must be a JSON object.",
            metadata_path,
        )
    validate_install_record(payload, metadata_path)
    required = {
        "schema_version": int,
        "record_type": str,
        "backup_id": str,
        "host": str,
        "created_at": str,
        "reason": str,
        "status": str,
        "target": str,
        "canonical_sha256": str,
        "skill_sha256": str,
        "entry_count": int,
        "file_count": int,
        "byte_count": int,
    }
    for key, expected_type in required.items():
        if key not in payload or type(payload[key]) is not expected_type:
            raise ManagerError(
                "invalid-backup-record",
                f"Backup metadata field {key!r} is missing or has the wrong type.",
                metadata_path,
            )
    if (
        payload["schema_version"] != BACKUP_SCHEMA_VERSION
        or payload["record_type"] != BACKUP_RECORD_TYPE
        or payload["backup_id"] != backup_id
        or payload["host"] != config.host
        or path_key(Path(str(payload["target"]))) != path_key(config.target)
        or not re.fullmatch(r"[a-f0-9]{64}", str(payload["canonical_sha256"]))
        or not re.fullmatch(r"[a-f0-9]{64}", str(payload["skill_sha256"]))
        or payload["status"]
        not in {"available", "restored", "failed", "transaction-rolled-back"}
    ):
        raise ManagerError(
            "invalid-backup-record",
            "Backup metadata violates route or identity invariants.",
            metadata_path,
        )
    return payload


def identity_matches_metadata(
    identity: TreeIdentity,
    metadata: dict[str, object],
) -> bool:
    return (
        identity.sha256 == metadata["skill_sha256"]
        and identity.entries == metadata["entry_count"]
        and identity.files == metadata["file_count"]
        and identity.bytes == metadata["byte_count"]
    )


def validate_pending_backup(config: HostConfig, path: Path) -> Backup:
    assert_contained(path, config.backup_root)
    assert_no_reparse_path(path, stop=config.backup_root)
    if not path.is_dir() or not path.name.startswith(".pending-"):
        raise ManagerError(
            "invalid-recovery-residue",
            "Pending recovery entry has an unsafe name or type.",
            path,
        )
    backup_id = path.name.removeprefix(".pending-")
    if not BACKUP_ID_PATTERN.fullmatch(backup_id):
        raise ManagerError(
            "invalid-recovery-residue",
            "Pending recovery entry has an invalid backup identifier.",
            path,
        )
    try:
        entries = sorted(path.iterdir(), key=lambda item: item.name.casefold())
    except OSError as exc:
        raise ManagerError("tree-enumeration-failed", str(exc), path) from exc
    if any(is_reparse(entry) for entry in entries):
        raise ManagerError(
            "reparse-point-refused",
            "Pending recovery entry contains a redirected path.",
            path,
        )
    names = {entry.name for entry in entries}
    if not names.issubset({"operation.json", "skill"}) or "operation.json" not in names:
        raise ManagerError(
            "invalid-recovery-residue",
            "Pending recovery entry contains unexpected or incomplete content.",
            path,
        )
    metadata = validate_backup_metadata(config, path, backup_id=backup_id)
    if metadata["status"] not in {"available", "failed"}:
        raise ManagerError(
            "invalid-recovery-residue",
            "Pending metadata has a status that cannot belong to an interrupted transaction.",
            path / "operation.json",
        )
    skill = path / "skill"
    identity: TreeIdentity | None = None
    if entry_exists(skill):
        if not skill.is_dir():
            raise ManagerError(
                "invalid-recovery-residue",
                "Pending skill payload is not a directory.",
                skill,
            )
        identity = validate_design_dna_tree(skill)
        if not identity_matches_metadata(identity, metadata):
            raise ManagerError(
                "backup-parity-mismatch",
                "Pending backup content does not match its recorded identity.",
                skill,
            )
    return Backup(
        backup_id=backup_id,
        path=path,
        skill=skill,
        metadata=metadata,
        identity=identity,
    )


def validate_stage(
    config: HostConfig,
    path: Path,
    canonical: TreeIdentity,
) -> TreeIdentity | None:
    assert_contained(path, config.backup_root)
    assert_no_reparse_path(path, stop=config.backup_root)
    if not path.is_dir() or not path.name.startswith(".stage-"):
        raise ManagerError(
            "invalid-recovery-residue",
            "Staging recovery entry has an unsafe name or type.",
            path,
        )
    stage_id = path.name.removeprefix(".stage-")
    if not BACKUP_ID_PATTERN.fullmatch(stage_id):
        raise ManagerError(
            "invalid-recovery-residue",
            "Staging recovery entry has an invalid transaction identifier.",
            path,
        )
    try:
        entries = list(path.iterdir())
    except OSError as exc:
        raise ManagerError("tree-enumeration-failed", str(exc), path) from exc
    if not entries:
        return None
    if (
        len(entries) != 1
        or entries[0].name != "skill"
        or not entries[0].is_dir()
        or is_reparse(entries[0])
    ):
        raise ManagerError(
            "invalid-recovery-residue",
            "Staging recovery entry is not an empty container or one complete skill copy.",
            path,
        )
    identity = validate_design_dna_tree(entries[0])
    if identity.records != canonical.records:
        raise ManagerError(
            "staging-parity-mismatch",
            "Interrupted staging content does not exactly match canonical source.",
            entries[0],
        )
    return identity


def plan_recovery(
    config: HostConfig,
    canonical: TreeIdentity,
) -> RecoveryPlan:
    if not entry_exists(config.backup_root):
        target = (
            validate_design_dna_tree(config.target)
            if entry_exists(config.target)
            else None
        )
        return RecoveryPlan(config=config, steps=(), projected_target=target)
    if not config.backup_root.is_dir():
        raise ManagerError(
            "invalid-backup-root",
            "Backup root is not a directory.",
            config.backup_root,
        )
    assert_no_reparse_path(config.backup_root)
    target = (
        validate_design_dna_tree(config.target)
        if entry_exists(config.target)
        else None
    )
    stages: list[tuple[Path, TreeIdentity | None]] = []
    pending: list[Backup] = []
    consumed: list[Backup] = []
    for entry in sorted(
        config.backup_root.iterdir(),
        key=lambda item: item.name.casefold(),
    ):
        if is_reparse(entry):
            raise ManagerError(
                "reparse-point-refused",
                "Backup storage contains a redirected entry.",
                entry,
            )
        if entry.name == ".install-operation.lock":
            if not entry.is_file():
                raise ManagerError(
                    "invalid-operation-lock",
                    "The installation lock path is not an ordinary file.",
                    entry,
                )
            continue
        if entry.name.startswith(".stage-"):
            stages.append((entry, validate_stage(config, entry, canonical)))
            continue
        if entry.name.startswith(".pending-"):
            pending.append(validate_pending_backup(config, entry))
            continue
        try:
            validate_backup(config, entry)
        except ManagerError as exc:
            if exc.code != "backup-payload-missing":
                raise
            backup_id = entry.name
            if not BACKUP_ID_PATTERN.fullmatch(backup_id):
                raise
            metadata = validate_backup_metadata(
                config,
                entry,
                backup_id=backup_id,
            )
            if (
                target is None
                or metadata["status"] not in {"available", "failed"}
                or not identity_matches_metadata(target, metadata)
            ):
                raise ManagerError(
                    "consumed-backup-unproven",
                    "A backup payload is missing and the exact target identity does not prove where it moved.",
                    entry,
                ) from exc
            consumed.append(
                Backup(
                    backup_id=backup_id,
                    path=entry,
                    skill=entry / "skill",
                    metadata=metadata,
                    identity=None,
                )
            )
    if len(pending) > 1:
        raise ManagerError(
            "ambiguous-recovery",
            "More than one pending transaction exists for this host.",
            config.backup_root,
            details={"paths": [str(item.path) for item in pending]},
        )

    steps: list[RecoveryStep] = []
    projected_target = target
    if pending:
        item = pending[0]
        final = config.backup_root / item.backup_id
        if entry_exists(final):
            raise ManagerError(
                "recovery-backup-collision",
                "Pending recovery cannot be finalized over an existing backup.",
                final,
            )
        if target is None:
            if item.identity is None:
                raise ManagerError(
                    "pending-payload-missing",
                    "The target and pending payload are both absent; recovery cannot prove a safe state.",
                    item.path,
                )
            steps.append(
                RecoveryStep(
                    action="restored-pending-target",
                    path=item.path,
                    destination=config.target,
                    backup_id=item.backup_id,
                )
            )
            projected_target = item.identity
        elif item.identity is not None:
            steps.append(
                RecoveryStep(
                    action="finalized-pending-backup",
                    path=item.path,
                    destination=final,
                    backup_id=item.backup_id,
                )
            )
        elif identity_matches_metadata(target, item.metadata):
            steps.append(
                RecoveryStep(
                    action="removed-consumed-pending",
                    path=item.path,
                    backup_id=item.backup_id,
                )
            )
        else:
            raise ManagerError(
                "pending-payload-unproven",
                "Pending metadata has no payload and does not identify the current target.",
                item.path,
            )

    populated_stages = [
        (path, identity)
        for path, identity in stages
        if identity is not None
    ]
    if projected_target is None and populated_stages:
        selected_path, selected_identity = populated_stages[0]
        steps.append(
            RecoveryStep(
                action="installed-staged-target",
                path=selected_path,
                destination=config.target,
            )
        )
        projected_target = selected_identity
    for stage, stage_identity in stages:
        if any(
            step.action == "installed-staged-target"
            and path_key(step.path) == path_key(stage)
            for step in steps
        ):
            continue
        steps.append(
            RecoveryStep(
                action=(
                    "removed-empty-stage"
                    if stage_identity is None
                    else "removed-stage"
                ),
                path=stage,
            )
        )
    for backup in consumed:
        steps.append(
            RecoveryStep(
                action="repaired-consumed-backup",
                path=backup.path,
                backup_id=backup.backup_id,
            )
        )
    return RecoveryPlan(
        config=config,
        steps=tuple(steps),
        projected_target=projected_target,
    )


def execute_recovery(
    plan: RecoveryPlan,
    canonical: TreeIdentity,
) -> dict[str, object] | None:
    if not plan.steps:
        return None
    resolved: list[str] = []
    actions: list[str] = []
    backup_ids: list[str] = []
    for step in plan.steps:
        config = plan.config
        if step.action == "restored-pending-target":
            pending = validate_pending_backup(config, step.path)
            if pending.identity is None or entry_exists(config.target):
                raise ManagerError(
                    "recovery-state-changed",
                    "Pending restoration preconditions changed after recovery planning.",
                    step.path,
                )
            pending.skill.rename(config.target)
            restored = validate_design_dna_tree(config.target)
            if restored.records != pending.identity.records:
                raise ManagerError(
                    "recovery-parity-mismatch",
                    "Restored target differs from the pending payload identity.",
                    config.target,
                )
            safe_remove_stage(step.path, config.backup_root)
        elif step.action == "finalized-pending-backup":
            pending = validate_pending_backup(config, step.path)
            if pending.identity is None or step.destination is None:
                raise ManagerError(
                    "recovery-state-changed",
                    "Pending backup can no longer be finalized safely.",
                    step.path,
                )
            finalize_pending(step.path, step.destination)
            validate_backup(config, step.destination)
        elif step.action == "removed-consumed-pending":
            pending = validate_pending_backup(config, step.path)
            current = validate_design_dna_tree(config.target)
            if pending.identity is not None or not identity_matches_metadata(
                current,
                pending.metadata,
            ):
                raise ManagerError(
                    "recovery-state-changed",
                    "Consumed pending metadata no longer matches the exact target.",
                    step.path,
                )
            safe_remove_stage(step.path, config.backup_root)
        elif step.action == "installed-staged-target":
            staged = validate_stage(config, step.path, canonical)
            if staged is None or entry_exists(config.target):
                raise ManagerError(
                    "recovery-state-changed",
                    "Staged installation can no longer be promoted safely.",
                    step.path,
                )
            (step.path / "skill").rename(config.target)
            installed = validate_design_dna_tree(config.target)
            if installed.records != staged.records:
                raise ManagerError(
                    "recovery-parity-mismatch",
                    "Promoted target differs from canonical staging content.",
                    config.target,
                )
            safe_remove_stage(step.path, config.backup_root)
        elif step.action == "removed-stage":
            validate_stage(config, step.path, canonical)
            if not entry_exists(config.target):
                raise ManagerError(
                    "recovery-runtime-missing",
                    "A staging copy will not be removed without another valid target.",
                    step.path,
                )
            validate_design_dna_tree(config.target)
            safe_remove_stage(step.path, config.backup_root)
        elif step.action == "removed-empty-stage":
            staged = validate_stage(config, step.path, canonical)
            if staged is not None:
                raise ManagerError(
                    "recovery-state-changed",
                    "An empty staging container gained content after recovery planning.",
                    step.path,
                )
            safe_remove_stage(step.path, config.backup_root)
        elif step.action == "repaired-consumed-backup":
            current = validate_design_dna_tree(config.target)
            metadata = validate_backup_metadata(
                config,
                step.path,
                backup_id=str(step.backup_id),
            )
            if (
                entry_exists(step.path / "skill")
                or metadata["status"] not in {"available", "failed"}
                or not identity_matches_metadata(current, metadata)
            ):
                raise ManagerError(
                    "consumed-backup-unproven",
                    "Consumed backup metadata cannot be repaired from the exact current target.",
                    step.path,
                )
            backup = Backup(
                backup_id=str(step.backup_id),
                path=step.path,
                skill=step.path / "skill",
                metadata=metadata,
                identity=None,
            )
            mark_backup(backup, "restored", restored_at=utc_now())
            validate_backup(config, step.path)
        else:
            raise ManagerError(
                "invalid-recovery-step",
                f"Unsupported recovery step: {step.action}",
                step.path,
            )
        actions.append(step.action)
        resolved.append(str(step.path))
        if step.backup_id is not None:
            backup_ids.append(step.backup_id)
    installed = (
        validate_design_dna_tree(plan.config.target)
        if entry_exists(plan.config.target)
        else None
    )
    return {
        "host": plan.config.host,
        "action": "recovered",
        "target": str(plan.config.target),
        "backup_id": None,
        "installed_sha256": installed.sha256 if installed is not None else None,
        "recovery_actions": actions,
        "resolved_paths": resolved,
        "recovered_backup_ids": list(dict.fromkeys(backup_ids)),
        "executed": True,
    }


def planned_recovery_change(plan: RecoveryPlan) -> dict[str, object] | None:
    if not plan.steps:
        return None
    return {
        "host": plan.config.host,
        "action": "recover",
        "target": str(plan.config.target),
        "backup_id": None,
        "installed_sha256": (
            plan.projected_target.sha256
            if plan.projected_target is not None
            else None
        ),
        "recovery_actions": [step.action for step in plan.steps],
        "resolved_paths": [str(step.path) for step in plan.steps],
        "recovered_backup_ids": list(
            dict.fromkeys(
                step.backup_id
                for step in plan.steps
                if step.backup_id is not None
            )
        ),
        "executed": False,
    }


def create_stage(config: HostConfig, source: Path, canonical: TreeIdentity) -> tuple[Path, Path]:
    container = config.backup_root / f".stage-{new_backup_id()}"
    assert_contained(container, config.backup_root)
    try:
        container.mkdir()
        skill = container / "skill"
        copy_exact(source, skill)
        staged = validate_design_dna_tree(skill)
        if staged.records != canonical.records:
            raise ManagerError("staging-parity-mismatch", "Staged copy differs from canonical source.", skill)
        return container, skill
    except Exception:
        if entry_exists(container):
            safe_remove_stage(container, config.backup_root)
        raise


def create_pending_backup(
    config: HostConfig,
    identity: TreeIdentity,
    canonical: TreeIdentity,
    reason: str,
) -> tuple[str, Path, Path, dict[str, object]]:
    backup_id = new_backup_id()
    final = config.backup_root / backup_id
    pending = config.backup_root / f".pending-{backup_id}"
    assert_contained(final, config.backup_root)
    assert_contained(pending, config.backup_root)
    if entry_exists(final) or entry_exists(pending):
        raise ManagerError("backup-id-collision", "Generated backup identifier already exists.", final)
    try:
        pending.mkdir()
        metadata = backup_metadata(
            backup_id=backup_id,
            host=config.host,
            target=config.target,
            reason=reason,
            skill_identity=identity,
            canonical_sha256=canonical.sha256,
        )
        atomic_write_json(pending / "operation.json", metadata)
        return backup_id, pending, final, metadata
    except Exception:
        if entry_exists(pending):
            safe_remove_stage(pending, config.backup_root)
        raise


def finalize_pending(pending: Path, final: Path) -> None:
    try:
        pending.rename(final)
    except OSError as exc:
        raise ManagerError("backup-finalize-failed", str(exc), final) from exc


def preserve_active_as_failed(
    config: HostConfig,
    canonical: TreeIdentity,
    *,
    reason: str,
) -> Path:
    identity = validate_design_dna_tree(config.target)
    _backup_id, pending, final, metadata = create_pending_backup(
        config,
        identity,
        canonical,
        reason,
    )
    metadata["status"] = "failed"
    atomic_write_json(pending / "operation.json", metadata)
    try:
        config.target.rename(pending / "skill")
        finalize_pending(pending, final)
    except Exception as exc:
        raise ManagerError(
            "quarantine-failed",
            f"Could not move the active tree to recoverable failure storage: {exc}",
            config.target,
        ) from exc
    return final


def mark_backup(backup: Backup, status: str, **fields: object) -> None:
    payload = dict(backup.metadata)
    payload["status"] = status
    payload.update(fields)
    atomic_write_json(backup.path / "operation.json", payload)


def install_host(
    config: HostConfig,
    source: Path,
    canonical: TreeIdentity,
    *,
    simulate_commit_failure: bool,
    hard_exit_at: str | None,
) -> AppliedChange:
    stage, staged_skill = create_stage(config, source, canonical)
    installed = False
    try:
        if simulate_commit_failure:
            raise OSError("simulated install commit failure")
        staged_skill.rename(config.target)
        maybe_hard_exit(hard_exit_at, "install-after-new-target")
        installed = True
        installed_identity = validate_design_dna_tree(config.target)
        if installed_identity.records != canonical.records:
            raise ManagerError(
                "installed-parity-mismatch",
                "Installed tree differs from canonical source.",
                config.target,
            )
        safe_remove_stage(stage, config.backup_root)
    except Exception as exc:
        if installed and entry_exists(config.target):
            preserve_active_as_failed(config, canonical, reason="failed-install")
        if entry_exists(stage):
            safe_remove_stage(stage, config.backup_root)
        if isinstance(exc, ManagerError):
            raise
        raise ManagerError("install-commit-failed", str(exc), config.target) from exc

    def undo() -> None:
        if entry_exists(config.target):
            preserve_active_as_failed(config, canonical, reason="multi-host-transaction-rollback")

    return AppliedChange(
        payload={
            "host": config.host,
            "action": "installed",
            "target": str(config.target),
            "backup_id": None,
            "installed_sha256": canonical.sha256,
            "previous_sha256": None,
            "executed": True,
        },
        undo=undo,
    )


def update_host(
    config: HostConfig,
    source: Path,
    canonical: TreeIdentity,
    previous: TreeIdentity,
    *,
    simulate_commit_failure: bool,
    hard_exit_at: str | None,
) -> AppliedChange:
    stage, staged_skill = create_stage(config, source, canonical)
    try:
        backup_id, pending, final, metadata = create_pending_backup(
            config,
            previous,
            canonical,
            "update",
        )
    except Exception:
        if entry_exists(stage):
            safe_remove_stage(stage, config.backup_root)
        raise
    old_moved = False
    new_installed = False
    finalized = False
    try:
        config.target.rename(pending / "skill")
        maybe_hard_exit(hard_exit_at, "update-before-new-target")
        old_moved = True
        if simulate_commit_failure:
            raise OSError("simulated update commit failure")
        staged_skill.rename(config.target)
        maybe_hard_exit(hard_exit_at, "update-after-new-target")
        new_installed = True
        installed = validate_design_dna_tree(config.target)
        if installed.records != canonical.records:
            raise ManagerError(
                "installed-parity-mismatch",
                "Updated tree differs from canonical source.",
                config.target,
            )
        finalize_pending(pending, final)
        finalized = True
        safe_remove_stage(stage, config.backup_root)
    except Exception as exc:
        rollback_errors: list[str] = []
        if new_installed and entry_exists(config.target):
            try:
                preserve_active_as_failed(config, canonical, reason="failed-update")
            except ManagerError as rollback_error:
                rollback_errors.append(str(rollback_error))
        old_location = final / "skill" if finalized else pending / "skill"
        if old_moved and entry_exists(old_location) and not entry_exists(config.target):
            try:
                old_location.rename(config.target)
                restored = validate_design_dna_tree(config.target)
                if restored.records != previous.records:
                    raise ManagerError(
                        "rollback-parity-mismatch",
                        "Restored tree differs from the pre-update tree.",
                        config.target,
                    )
            except Exception as rollback_error:
                rollback_errors.append(str(rollback_error))
        if entry_exists(stage):
            try:
                safe_remove_stage(stage, config.backup_root)
            except ManagerError as cleanup_error:
                rollback_errors.append(str(cleanup_error))
        if not finalized and entry_exists(pending) and not entry_exists(pending / "skill"):
            try:
                safe_remove_stage(pending, config.backup_root)
            except ManagerError as cleanup_error:
                rollback_errors.append(str(cleanup_error))
        if finalized and entry_exists(final) and not entry_exists(final / "skill"):
            consumed = Backup(backup_id, final, final / "skill", metadata, None)
            try:
                mark_backup(consumed, "transaction-rolled-back", rolled_back_at=utc_now())
            except ManagerError as metadata_error:
                rollback_errors.append(str(metadata_error))
        if rollback_errors:
            raise ManagerError(
                "rollback-failed",
                "Update failed and the prior install could not be restored cleanly.",
                config.target,
                details={"original_error": str(exc), "rollback_errors": rollback_errors},
            ) from exc
        if isinstance(exc, ManagerError):
            raise
        raise ManagerError("update-commit-failed", str(exc), config.target) from exc

    backup = Backup(backup_id, final, final / "skill", metadata, previous)

    def undo() -> None:
        if entry_exists(config.target):
            preserve_active_as_failed(config, canonical, reason="multi-host-transaction-rollback")
        if not entry_exists(backup.skill):
            raise ManagerError("rollback-payload-missing", "Prior update backup is unavailable.", backup.skill)
        backup.skill.rename(config.target)
        restored = validate_design_dna_tree(config.target)
        if restored.records != previous.records:
            raise ManagerError("rollback-parity-mismatch", "Could not restore prior update tree.", config.target)
        mark_backup(backup, "transaction-rolled-back", rolled_back_at=utc_now())

    return AppliedChange(
        payload={
            "host": config.host,
            "action": "updated",
            "target": str(config.target),
            "backup_id": backup_id,
            "installed_sha256": canonical.sha256,
            "previous_sha256": previous.sha256,
            "executed": True,
        },
        undo=undo,
    )


def uninstall_host(
    config: HostConfig,
    canonical: TreeIdentity,
    previous: TreeIdentity,
    *,
    hard_exit_at: str | None,
) -> AppliedChange:
    backup_id, pending, final, metadata = create_pending_backup(
        config,
        previous,
        canonical,
        "uninstall",
    )
    moved = False
    finalized = False
    try:
        config.target.rename(pending / "skill")
        maybe_hard_exit(hard_exit_at, "uninstall-after-target")
        moved = True
        stored = validate_design_dna_tree(pending / "skill")
        if stored.records != previous.records:
            raise ManagerError("backup-parity-mismatch", "Uninstall backup differs from installed tree.", pending / "skill")
        finalize_pending(pending, final)
        finalized = True
    except Exception as exc:
        old_location = final / "skill" if finalized else pending / "skill"
        if moved and entry_exists(old_location) and not entry_exists(config.target):
            try:
                old_location.rename(config.target)
            except OSError as rollback_error:
                raise ManagerError(
                    "rollback-failed",
                    "Uninstall failed and the installed tree could not be restored.",
                    config.target,
                    details={"original_error": str(exc), "rollback_error": str(rollback_error)},
                ) from exc
        if not finalized and entry_exists(pending) and not entry_exists(pending / "skill"):
            safe_remove_stage(pending, config.backup_root)
        if isinstance(exc, ManagerError):
            raise
        raise ManagerError("uninstall-commit-failed", str(exc), config.target) from exc

    backup = Backup(backup_id, final, final / "skill", metadata, previous)

    def undo() -> None:
        if entry_exists(config.target):
            raise ManagerError("rollback-target-occupied", "Cannot restore an uninstalled tree over an occupied target.", config.target)
        backup.skill.rename(config.target)
        restored = validate_design_dna_tree(config.target)
        if restored.records != previous.records:
            raise ManagerError("rollback-parity-mismatch", "Could not restore uninstalled tree.", config.target)
        mark_backup(backup, "transaction-rolled-back", rolled_back_at=utc_now())

    return AppliedChange(
        payload={
            "host": config.host,
            "action": "uninstalled",
            "target": str(config.target),
            "backup_id": backup_id,
            "installed_sha256": None,
            "previous_sha256": previous.sha256,
            "executed": True,
        },
        undo=undo,
    )


def choose_rollback_backup(config: HostConfig, requested: str | None) -> Backup:
    available = [
        backup
        for backup in list_backups(config)
        if backup.metadata["status"] == "available"
    ]
    if requested is not None:
        if not BACKUP_ID_PATTERN.fullmatch(requested):
            raise ManagerError("invalid-backup-id", "Rollback backup ID has an unsafe format.")
        matches = [backup for backup in available if backup.backup_id == requested]
        if not matches:
            raise ManagerError(
                "rollback-backup-not-found",
                "Requested recoverable backup is unavailable.",
                config.backup_root / requested,
            )
        return matches[0]
    if not available:
        raise ManagerError("rollback-backup-not-found", "No recoverable backup is available.", config.backup_root)
    if len(available) != 1:
        raise ManagerError(
            "ambiguous-rollback",
            "Multiple recoverable backups exist; choose one with --backup-id.",
            config.backup_root,
            details={"backup_ids": [backup.backup_id for backup in available]},
        )
    return available[0]


def rollback_host(
    config: HostConfig,
    canonical: TreeIdentity,
    selected: Backup,
    current: TreeIdentity | None,
    *,
    hard_exit_at: str | None,
) -> AppliedChange:
    if selected.identity is None:
        raise ManagerError("rollback-backup-not-found", "Selected backup has no recoverable payload.", selected.path)
    current_backup: Backup | None = None
    current_pending: Path | None = None
    current_final: Path | None = None
    current_metadata: dict[str, object] | None = None
    current_moved = False
    restored_moved = False
    selected_marked = False
    try:
        if current is not None:
            current_id, current_pending, current_final, current_metadata = create_pending_backup(
                config,
                current,
                canonical,
                "rollback-replaced-current",
            )
            config.target.rename(current_pending / "skill")
            current_moved = True
            current_backup = Backup(
                current_id,
                current_final,
                current_final / "skill",
                current_metadata,
                current,
            )
        selected.skill.rename(config.target)
        maybe_hard_exit(hard_exit_at, "rollback-after-restored-target")
        restored_moved = True
        restored = validate_design_dna_tree(config.target)
        if restored.records != selected.identity.records:
            raise ManagerError("rollback-parity-mismatch", "Restored tree differs from selected backup.", config.target)
        mark_backup(selected, "restored", restored_at=utc_now())
        selected_marked = True
        if current_pending is not None and current_final is not None:
            finalize_pending(current_pending, current_final)
    except Exception as exc:
        rollback_errors: list[str] = []
        if restored_moved and entry_exists(config.target) and not entry_exists(selected.skill):
            try:
                config.target.rename(selected.skill)
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        if selected_marked:
            try:
                mark_backup(selected, "available", restored_at=None)
            except ManagerError as rollback_error:
                rollback_errors.append(str(rollback_error))
        current_location = None
        if current_final is not None and entry_exists(current_final / "skill"):
            current_location = current_final / "skill"
        elif current_pending is not None and entry_exists(current_pending / "skill"):
            current_location = current_pending / "skill"
        if current_moved and current_location is not None and not entry_exists(config.target):
            try:
                current_location.rename(config.target)
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        if current_pending is not None and entry_exists(current_pending) and not entry_exists(current_pending / "skill"):
            try:
                safe_remove_stage(current_pending, config.backup_root)
            except ManagerError as rollback_error:
                rollback_errors.append(str(rollback_error))
        if rollback_errors:
            raise ManagerError(
                "rollback-failed",
                "Rollback operation failed and its original state could not be reconstructed cleanly.",
                config.target,
                details={"original_error": str(exc), "rollback_errors": rollback_errors},
            ) from exc
        if isinstance(exc, ManagerError):
            raise
        raise ManagerError("rollback-commit-failed", str(exc), config.target) from exc

    def undo() -> None:
        if not entry_exists(config.target):
            raise ManagerError("rollback-target-missing", "Restored target disappeared before transaction reversal.", config.target)
        config.target.rename(selected.skill)
        mark_backup(selected, "available", restored_at=None)
        if current_backup is not None:
            if not entry_exists(current_backup.skill):
                raise ManagerError("rollback-payload-missing", "Replaced-current backup is unavailable.", current_backup.skill)
            current_backup.skill.rename(config.target)
            mark_backup(current_backup, "transaction-rolled-back", rolled_back_at=utc_now())

    restored_identity = selected.identity
    return AppliedChange(
        payload={
            "host": config.host,
            "action": "rolled-back",
            "target": str(config.target),
            "backup_id": selected.backup_id,
            "replacement_backup_id": current_backup.backup_id if current_backup else None,
            "installed_sha256": restored_identity.sha256,
            "previous_sha256": current.sha256 if current else None,
            "canonical_parity": restored_identity.records == canonical.records,
            "executed": True,
        },
        undo=undo,
    )


def planned_change(
    command: str,
    config: HostConfig,
    snapshot: dict[str, object],
    backup: Backup | None,
) -> dict[str, object]:
    if command == "sync":
        if not snapshot["target"]["exists"]:
            action = "install"
        elif snapshot["target"]["parity"]:
            action = "no-op"
        else:
            action = "update"
    else:
        action = {
            "install": "install",
            "update": "no-op" if snapshot["target"]["parity"] else "update",
            "uninstall": "uninstall",
            "rollback": "rollback",
        }[command]
    return {
        "host": config.host,
        "action": action,
        "target": str(config.target),
        "backup_id": backup.backup_id if backup else None,
        "executed": False,
    }


def assert_operation_preconditions(
    command: str,
    config: HostConfig,
    snapshot: dict[str, object],
    backup_id: str | None,
) -> Backup | None:
    collision_candidates = list(snapshot["collision_candidates"])
    if collision_candidates and command != "uninstall":
        raise ManagerError(
            "discovery-candidate-collision",
            (
                "A mutating operation is refused while multiple Design DNA "
                "filesystem discovery candidates exist."
            ),
            config.discovery_roots[0],
            details={
                "candidates": collision_candidates,
                "activation_state": "not-verified",
            },
        )
    exists = bool(snapshot["target"]["exists"])
    external_candidates = [
        route
        for route in snapshot["discovery_candidates"]
        if not bool(route["expected"])
    ]
    if external_candidates and command in {"install", "update", "sync", "rollback"}:
        raise ManagerError(
            "external-discovery-candidate",
            (
                "A packaged or externally managed filesystem discovery candidate "
                "exists. Activation was not verified; inspect the host plugin "
                "manager instead of creating a direct route."
            ),
            Path(str(external_candidates[0]["path"])),
            details={"activation_state": "not-verified"},
        )
    if command == "uninstall" and collision_candidates and not exists:
        raise ManagerError(
            "uninstall-target-missing",
            (
                "The managed direct route is absent. Inspect the host plugin "
                "manager and remove only a confirmed packaged installation."
            ),
            config.target,
        )
    if command == "install" and exists:
        raise ManagerError(
            "install-target-exists",
            "Install requires an absent target; use update for an existing installation.",
            config.target,
        )
    if command == "update" and not exists:
        raise ManagerError(
            "update-target-missing",
            "Update requires an existing installation; use install first.",
            config.target,
        )
    if command == "uninstall" and not exists:
        raise ManagerError("uninstall-target-missing", "No installed target exists to uninstall.", config.target)
    if command == "rollback":
        return choose_rollback_backup(config, backup_id)
    if command == "sync" and backup_id is not None:
        raise ManagerError("backup-id-not-applicable", "--backup-id is only valid with rollback.")
    if backup_id is not None:
        raise ManagerError("backup-id-not-applicable", "--backup-id is only valid with rollback.")
    return None


def operation_result(
    *,
    operation: str,
    dry_run: bool,
    home: Path,
    source: Path,
    canonical: TreeIdentity | None,
    hosts: list[dict[str, object]],
    changes: list[dict[str, object]],
    errors: list[dict[str, object]],
    ok: bool,
) -> dict[str, object]:
    return {
        "schema_version": OPERATION_SCHEMA_VERSION,
        "record_type": RECORD_TYPE,
        "operation": operation,
        "ok": ok,
        "dry_run": dry_run,
        "home": str(home),
        "source": (
            canonical.as_dict(source)
            if canonical is not None
            else {
                "path": str(source),
                "sha256": None,
                "entry_count": None,
                "file_count": None,
                "byte_count": None,
            }
        ),
        "hosts": hosts,
        "changes": changes,
        "errors": errors,
    }


def reverse_applied_changes(applied: list[AppliedChange], original: Exception) -> None:
    """Reverse already-committed hosts or raise one explicit rollback failure."""

    undo_errors: list[str] = []
    for change in reversed(applied):
        try:
            change.undo()
        except Exception as undo_error:
            undo_errors.append(str(undo_error))
    if undo_errors:
        raise ManagerError(
            "multi-host-rollback-failed",
            "A host operation failed and earlier host changes could not all be reversed.",
            details={"original_error": str(original), "rollback_errors": undo_errors},
        ) from original


def validate_final_operation_state(
    command: str,
    snapshots: list[dict[str, object]],
) -> None:
    for snapshot in snapshots:
        if snapshot["collision_candidates"]:
            raise ManagerError(
                "discovery-candidate-collision",
                (
                    "Multiple Design DNA filesystem discovery candidates appeared "
                    "before final verification completed."
                ),
                details={
                    "candidates": list(snapshot["collision_candidates"]),
                    "activation_state": "not-verified",
                },
            )
        target = snapshot["target"]
        if command in {"install", "update", "sync"} and (
            not bool(target["exists"]) or not bool(target["parity"])
        ):
            raise ManagerError(
                "final-parity-mismatch",
                "The final installed route does not exactly match canonical source.",
                Path(str(snapshot["expected_route"])),
            )
        if command == "uninstall" and bool(target["exists"]):
            raise ManagerError(
                "final-uninstall-verification-failed",
                "The exact managed route still exists after uninstall.",
                Path(str(snapshot["expected_route"])),
            )
        if command == "rollback" and not bool(target["exists"]):
            raise ManagerError(
                "final-rollback-verification-failed",
                "Rollback did not leave a valid Design DNA route installed.",
                Path(str(snapshot["expected_route"])),
            )


def run(
    *,
    command: str,
    host: str,
    home: Path,
    source: Path,
    backup_base: Path,
    claude_config_dir: Path | None = None,
    backup_id: str | None = None,
    dry_run: bool = False,
    simulate_commit_failure: bool = False,
    hard_exit_at: str | None = None,
    lock_held: bool = False,
) -> tuple[dict[str, object], int]:
    home = absolute(home)
    source = absolute(source)
    backup_base = absolute(backup_base)
    configs_by_name = host_configs(home, backup_base, claude_config_dir)
    selected_names = ["codex", "claude"] if host == "all" else [host]
    configs = [configs_by_name[name] for name in selected_names]
    canonical: TreeIdentity | None = None
    try:
        assert_layout_safe(home, source, backup_base, configs)
        if backup_id is not None and command == "recover":
            raise ManagerError(
                "backup-id-not-applicable",
                "--backup-id is only valid with rollback.",
            )
        if simulate_commit_failure and command == "recover":
            raise ManagerError(
                "test-hook-not-applicable",
                "The commit-failure test hook does not apply to recovery.",
            )
        if hard_exit_at is not None:
            allowed_commands = {
                "install-after-new-target": {"install", "sync"},
                "update-before-new-target": {"update", "sync"},
                "update-after-new-target": {"update", "sync"},
                "uninstall-after-target": {"uninstall"},
                "rollback-after-restored-target": {"rollback"},
            }[hard_exit_at]
            if command not in allowed_commands:
                raise ManagerError(
                    "test-hook-not-applicable",
                    "The selected hard-exit test hook does not apply to this operation.",
                )
        if command != "doctor" and not dry_run and not lock_held:
            with operation_lock(backup_base, home):
                return run(
                    command=command,
                    host=host,
                    home=home,
                    source=source,
                    backup_base=backup_base,
                    claude_config_dir=claude_config_dir,
                    backup_id=backup_id,
                    dry_run=dry_run,
                    simulate_commit_failure=simulate_commit_failure,
                    hard_exit_at=hard_exit_at,
                    lock_held=True,
                )
        canonical = validate_design_dna_tree(source)
        if command == "recover":
            plans = [plan_recovery(config, canonical) for config in configs]
            if dry_run:
                planned = [
                    change
                    for change in (
                        planned_recovery_change(plan)
                        for plan in plans
                    )
                    if change is not None
                ]
                stable_source = validate_design_dna_tree(source)
                if stable_source.records != canonical.records:
                    raise ManagerError(
                        "source-changed-during-operation",
                        "Canonical source changed while recovery was being planned.",
                        source,
                    )
                return (
                    operation_result(
                        operation=command,
                        dry_run=True,
                        home=home,
                        source=source,
                        canonical=canonical,
                        hosts=[],
                        changes=planned,
                        errors=[],
                        ok=True,
                    ),
                    0,
                )
            recovered = [
                change
                for change in (
                    execute_recovery(plan, canonical)
                    for plan in plans
                )
                if change is not None
            ]
            stable_source = validate_design_dna_tree(source)
            if stable_source.records != canonical.records:
                raise ManagerError(
                    "source-changed-during-operation",
                    "Canonical source changed before recovery verification completed.",
                    source,
                )
            final_hosts = [inspect_host(config, canonical) for config in configs]
            return (
                operation_result(
                    operation=command,
                    dry_run=False,
                    home=home,
                    source=source,
                    canonical=canonical,
                    hosts=final_hosts,
                    changes=recovered,
                    errors=[],
                    ok=True,
                ),
                0,
            )
        snapshots = [inspect_host(config, canonical) for config in configs]
        if command == "doctor":
            stable_source = validate_design_dna_tree(source)
            if stable_source.records != canonical.records:
                raise ManagerError(
                    "source-changed-during-operation",
                    "Canonical source changed while doctor was inspecting host routes.",
                    source,
                )
            healthy = all(snapshot["status"] == "healthy" for snapshot in snapshots)
            return (
                operation_result(
                    operation=command,
                    dry_run=dry_run,
                    home=home,
                    source=source,
                    canonical=canonical,
                    hosts=snapshots,
                    changes=[],
                    errors=[],
                    ok=healthy,
                ),
                0 if healthy else 1,
            )

        selected_backups = [
            assert_operation_preconditions(command, config, snapshot, backup_id)
            for config, snapshot in zip(configs, snapshots)
        ]
        if dry_run:
            changes = [
                planned_change(command, config, snapshot, selected)
                for config, snapshot, selected in zip(configs, snapshots, selected_backups)
            ]
            return (
                operation_result(
                    operation=command,
                    dry_run=True,
                    home=home,
                    source=source,
                    canonical=canonical,
                    hosts=snapshots,
                    changes=changes,
                    errors=[],
                    ok=True,
                ),
                0,
            )

        for config in configs:
            ensure_mutation_directories(config, home)
        applied: list[AppliedChange] = []
        try:
            for index, (config, snapshot, selected) in enumerate(
                zip(configs, snapshots, selected_backups)
            ):
                inject = simulate_commit_failure and index == len(configs) - 1
                target_identity = (
                    validate_design_dna_tree(config.target)
                    if bool(snapshot["target"]["exists"])
                    else None
                )
                effective_command = command
                if command == "sync":
                    if not bool(snapshot["target"]["exists"]):
                        effective_command = "install"
                    elif bool(snapshot["target"]["parity"]):
                        effective_command = "current"
                    else:
                        effective_command = "update"
                if effective_command == "install":
                    change = install_host(
                        config,
                        source,
                        canonical,
                        simulate_commit_failure=inject,
                        hard_exit_at=hard_exit_at,
                    )
                elif effective_command == "update":
                    if bool(snapshot["target"]["parity"]):
                        change = AppliedChange(
                            payload={
                                "host": config.host,
                                "action": "already-current",
                                "target": str(config.target),
                                "backup_id": None,
                                "installed_sha256": canonical.sha256,
                                "previous_sha256": canonical.sha256,
                                "executed": False,
                            },
                            undo=lambda: None,
                        )
                    else:
                        if target_identity is None:
                            raise ManagerError("update-target-missing", "Update target disappeared.", config.target)
                        change = update_host(
                            config,
                            source,
                            canonical,
                            target_identity,
                            simulate_commit_failure=inject,
                            hard_exit_at=hard_exit_at,
                        )
                elif effective_command == "current":
                    change = AppliedChange(
                        payload={
                            "host": config.host,
                            "action": "already-current",
                            "target": str(config.target),
                            "backup_id": None,
                            "installed_sha256": canonical.sha256,
                            "previous_sha256": canonical.sha256,
                            "executed": False,
                        },
                        undo=lambda: None,
                    )
                elif effective_command == "uninstall":
                    if target_identity is None:
                        raise ManagerError("uninstall-target-missing", "Uninstall target disappeared.", config.target)
                    change = uninstall_host(
                        config,
                        canonical,
                        target_identity,
                        hard_exit_at=hard_exit_at,
                    )
                elif effective_command == "rollback":
                    if selected is None:
                        raise ManagerError("rollback-backup-not-found", "No rollback backup was selected.")
                    change = rollback_host(
                        config,
                        canonical,
                        selected,
                        target_identity,
                        hard_exit_at=hard_exit_at,
                    )
                else:
                    raise ManagerError("invalid-operation", f"Unsupported operation: {command}")
                applied.append(change)
        except Exception as exc:
            reverse_applied_changes(applied, exc)
            raise

        try:
            stable_source = validate_design_dna_tree(source)
            if stable_source.records != canonical.records:
                raise ManagerError(
                    "source-changed-during-operation",
                    "Canonical source changed before final verification completed.",
                    source,
                )
            final_hosts = [inspect_host(config, canonical) for config in configs]
            validate_final_operation_state(command, final_hosts)
        except Exception as exc:
            reverse_applied_changes(applied, exc)
            raise
        return (
            operation_result(
                operation=command,
                dry_run=False,
                home=home,
                source=source,
                canonical=canonical,
                hosts=final_hosts,
                changes=[change.payload for change in applied],
                errors=[],
                ok=True,
            ),
            0,
        )
    except ManagerError as exc:
        return (
            operation_result(
                operation=command,
                dry_run=dry_run,
                home=home,
                source=source,
                canonical=canonical,
                hosts=[],
                changes=[],
                errors=[exc.as_dict()],
                ok=False,
            ),
            2,
        )
    except (OSError, UnicodeError) as exc:
        failure = ManagerError("filesystem-operation-failed", str(exc))
        return (
            operation_result(
                operation=command,
                dry_run=dry_run,
                home=home,
                source=source,
                canonical=canonical,
                hosts=[],
                changes=[],
                errors=[failure.as_dict()],
                ok=False,
            ),
            2,
        )
    except Exception as exc:
        failure = ManagerError(
            "unexpected-manager-failure",
            f"{type(exc).__name__}: {exc}",
        )
        return (
            operation_result(
                operation=command,
                dry_run=dry_run,
                home=home,
                source=source,
                canonical=canonical,
                hosts=[],
                changes=[],
                errors=[failure.as_dict()],
                ok=False,
            ),
            2,
        )


def build_parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "doctor",
            "sync",
            "install",
            "update",
            "uninstall",
            "rollback",
            "recover",
        ),
    )
    parser.add_argument("--host", choices=("codex", "claude", "all"), default="all")
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "skills" / "design-dna",
    )
    parser.add_argument(
        "--backup-root",
        type=Path,
        help="Backup base under HOME; host-specific subdirectories are created below it.",
    )
    parser.add_argument("--backup-id", help="Exact recoverable backup ID for rollback.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--simulate-commit-failure", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--simulate-hard-exit-at",
        choices=HARD_EXIT_POINTS,
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        parser = build_parser()
        args = parser.parse_args(argv)
        home = absolute(args.home)
        backup_base = absolute(args.backup_root) if args.backup_root else home / ".design-dna" / "backups"
        claude_config_value = os.environ.get("CLAUDE_CONFIG_DIR")
        if (
            args.host in {"claude", "all"}
            and claude_config_value is not None
            and not claude_config_value.strip()
        ):
            raise ManagerError(
                "invalid-claude-config-dir",
                "CLAUDE_CONFIG_DIR must be a non-empty path when it is set.",
            )
        claude_config_dir = (
            absolute(Path(claude_config_value))
            if (
                args.host in {"claude", "all"}
                and claude_config_value is not None
            )
            else None
        )
        payload, exit_code = run(
            command=args.command,
            host=args.host,
            home=home,
            source=args.source,
            backup_base=backup_base,
            claude_config_dir=claude_config_dir,
            backup_id=args.backup_id,
            dry_run=args.dry_run,
            simulate_commit_failure=args.simulate_commit_failure,
            hard_exit_at=args.simulate_hard_exit_at,
        )
    except ManagerError as exc:
        fallback_home = absolute(Path.home())
        fallback_source = absolute(Path(__file__).resolve().parents[2] / "skills" / "design-dna")
        payload = operation_result(
            operation="invalid",
            dry_run=False,
            home=fallback_home,
            source=fallback_source,
            canonical=None,
            hosts=[],
            changes=[],
            errors=[exc.as_dict()],
            ok=False,
        )
        exit_code = 2
    except Exception as exc:
        fallback_home = absolute(Path.home())
        fallback_source = absolute(Path(__file__).resolve().parents[2] / "skills" / "design-dna")
        failure = ManagerError(
            "unexpected-manager-failure",
            f"{type(exc).__name__}: {exc}",
        )
        payload = operation_result(
            operation="invalid",
            dry_run=False,
            home=fallback_home,
            source=fallback_source,
            canonical=None,
            hosts=[],
            changes=[],
            errors=[failure.as_dict()],
            ok=False,
        )
        exit_code = 2
    emit(payload)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
