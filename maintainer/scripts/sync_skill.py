#!/usr/bin/env python3
"""Transactionally synchronize the canonical runtime skill to one explicit host target."""

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
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from common import (
    ToolFailure, absolute, assert_contained, assert_no_reparse_path,
    content_manifest, emit, entry_exists, is_reparse, is_within, walk_entries, walk_files,
)
from detect_routes import discover


def unique_backup(target: Path, backup_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    for number in range(1, 10_000):
        suffix = "" if number == 1 else f"-{number}"
        path = backup_root / f"{target.name}.backup-{stamp}{suffix}"
        if not entry_exists(path):
            return path
    raise ToolFailure("backup-name-exhausted", "Unable to choose a backup name.", backup_root)


def unique_quarantine(target: Path, backup_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    for number in range(1, 10_000):
        suffix = "" if number == 1 else f"-{number}"
        path = backup_root / f"{target.name}.failed-{stamp}{suffix}"
        if not entry_exists(path):
            return path
    raise ToolFailure(
        "quarantine-name-exhausted",
        "Unable to choose a failed-install quarantine name.",
        backup_root,
    )


def copy_exact(source: Path, destination: Path) -> None:
    destination.mkdir()
    for source_entry in walk_entries(source):
        relative = source_entry.relative_to(source)
        target_entry = destination / relative
        if source_entry.is_dir():
            target_entry.mkdir(exist_ok=True)
        else:
            target_entry.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_entry, target_entry, follow_symlinks=False)


def compare(source: Path, target: Path) -> tuple[bool, dict[str, object]]:
    source_files, source_hash = content_manifest(source)
    target_files, target_hash = content_manifest(target)
    return source_files == target_files, {
        "source_sha256": source_hash,
        "target_sha256": target_hash,
        "source_files": len(source_files),
        "target_files": len(target_files),
    }


def cleanup_stage_parent(
    stage_parent: Path,
    discovery: Path,
    *,
    simulate_failure: bool = False,
) -> dict[str, str] | None:
    """Remove transaction residue without ever masking the install outcome."""
    if not entry_exists(stage_parent):
        return None
    try:
        assert_no_reparse_path(stage_parent, stop=discovery)
        if simulate_failure:
            raise OSError("simulated cleanup failure")
        shutil.rmtree(stage_parent)
        return None
    except (OSError, ToolFailure) as exc:
        return {
            "code": "staging-cleanup-incomplete",
            "path": str(stage_parent),
            "message": (
                "The install outcome is recorded below, but temporary staging "
                f"residue could not be removed: {exc}"
            ),
        }


def assert_single_discovery_route(
    discovery: Path,
    target: Path,
    *,
    require_target: bool,
) -> list[dict[str, str]]:
    routes, warnings = discover(discovery)
    unexpected = [route for route in routes if route != target]
    if unexpected:
        rendered = ", ".join(str(path) for path in unexpected)
        raise ToolFailure(
            "duplicate-active-route",
            f"Discovery root contains another Design DNA route: {rendered}",
            discovery,
        )
    if require_target and routes != [target]:
        raise ToolFailure(
            "expected-route-not-discoverable",
            "The exact installed target is not the sole discoverable Design DNA route.",
            target,
        )
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2] / "skills" / "design-dna")
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--discovery-root", type=Path, required=True, help="Exact host skills directory that must contain the target.")
    parser.add_argument("--backup-root", type=Path, required=True, help="Existing directory outside discovery-root.")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--simulate-final-move-failure", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--simulate-installed-parity-failure", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--simulate-cleanup-failure", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        source, target = absolute(args.source), absolute(args.target)
        discovery, backups = absolute(args.discovery_root), absolute(args.backup_root)
        for path in (source, discovery, backups):
            if not path.is_dir():
                raise ToolFailure("directory-not-found", "Required directory does not exist.", path)
            assert_no_reparse_path(path)
        list(walk_files(source))
        assert_no_reparse_path(target, stop=discovery)
        if target.name != "design-dna":
            raise ToolFailure("invalid-target-name", "Target folder must be named design-dna.", target)
        if target.parent != discovery:
            raise ToolFailure(
                "target-must-be-direct-child",
                "Target must be the direct design-dna child of the discovery root.",
                target,
            )
        assert_contained(target, discovery)
        if is_within(backups, discovery) or is_within(discovery, backups):
            raise ToolFailure("unsafe-backup-root", "Backup root must be outside and separate from discovery.", backups)
        if target == source or is_within(target, source) or is_within(source, target):
            raise ToolFailure("overlapping-source-target", "Source and target must not overlap.", target)
        discovery_warnings = assert_single_discovery_route(
            discovery,
            target,
            require_target=args.check,
        )
        if args.check:
            if not target.is_dir():
                raise ToolFailure("target-not-found", "Target does not exist.", target)
            matched, details = compare(source, target)
            emit({
                "ok": matched,
                "action": "check",
                "source": str(source),
                "target": str(target),
                "warnings": discovery_warnings,
                **details,
            })
            return 0 if matched else 1
        if entry_exists(target) and not args.replace:
            raise ToolFailure("replace-required", "Target exists; pass --replace to create a recoverable backup.", target)
        backup = unique_backup(target, backups) if entry_exists(target) else None
        if args.dry_run:
            emit({
                "ok": True,
                "action": "dry-run",
                "source": str(source),
                "target": str(target),
                "backup": str(backup) if backup else None,
                "warnings": discovery_warnings,
            })
            return 0

        stage_parent = Path(tempfile.mkdtemp(prefix=".design-dna-sync-", dir=discovery))
        staged = stage_parent / target.name
        moved_old = False
        installed_new = False
        quarantine: Path | None = None
        success_payload: dict[str, object] | None = None
        operation_failure: ToolFailure | None = None
        cleanup_warning: dict[str, str] | None = None
        try:
            try:
                assert_contained(stage_parent, discovery)
                copy_exact(source, staged)
                matched, details = compare(source, staged)
                if not matched:
                    raise ToolFailure("staging-parity-failed", "Staged tree differs from source.", staged)
                assert_no_reparse_path(target, stop=discovery)
                if backup:
                    assert_no_reparse_path(backup, stop=backups)
                    assert_contained(backup, backups)
                    target.rename(backup)
                    moved_old = True
                try:
                    if args.simulate_final_move_failure:
                        raise OSError("simulated final move failure")
                    staged.rename(target)
                    installed_new = True
                except Exception:
                    if moved_old and backup and not entry_exists(target):
                        backup.rename(target)
                        moved_old = False
                    raise
                matched, details = compare(source, target)
                if args.simulate_installed_parity_failure:
                    matched = False
                if not matched:
                    raise ToolFailure("installed-parity-failed", "Installed tree differs from source.", target)
                post_warnings = assert_single_discovery_route(
                    discovery,
                    target,
                    require_target=True,
                )
                combined_warnings = {
                    (item["code"], item["path"], item["message"]): item
                    for item in discovery_warnings + post_warnings
                }
                success_payload = {
                    "ok": True,
                    "action": "sync",
                    "installed": True,
                    "source": str(source),
                    "target": str(target),
                    "backup": str(backup) if backup else None,
                    "warnings": list(combined_warnings.values()),
                    **details,
                }
            except Exception as exc:
                if installed_new and entry_exists(target):
                    try:
                        quarantine = unique_quarantine(target, backups)
                        assert_contained(quarantine, backups)
                        target.rename(quarantine)
                        installed_new = False
                    except (OSError, ToolFailure) as quarantine_error:
                        operation_failure = ToolFailure(
                            "rollback-failed",
                            f"{exc}; failed install could not be quarantined ({quarantine_error})."
                            f" Prior backup remains at {backup}.",
                            target,
                        )
                if operation_failure is None and moved_old and backup:
                    try:
                        backup.rename(target)
                        moved_old = False
                    except OSError as restore:
                        operation_failure = ToolFailure(
                            "rollback-failed",
                            f"{exc}; restore failed: {restore}. Prior backup remains at {backup};"
                            f" failed candidate is at {quarantine}.",
                            target,
                        )
                if operation_failure is None:
                    if isinstance(exc, ToolFailure):
                        operation_failure = ToolFailure(
                            exc.issue.code,
                            f"{exc}. Rollback completed."
                            + (f" Failed candidate preserved at {quarantine}." if quarantine else ""),
                            target,
                        )
                    else:
                        operation_failure = ToolFailure(
                            "sync-failed",
                            f"{exc}. Rollback completed."
                            + (f" Failed candidate preserved at {quarantine}." if quarantine else ""),
                            target,
                        )
        finally:
            cleanup_warning = cleanup_stage_parent(
                stage_parent,
                discovery,
                simulate_failure=args.simulate_cleanup_failure,
            )

        if operation_failure is not None:
            failure = operation_failure.issue.as_dict()
            if cleanup_warning is not None:
                failure["message"] += (
                    " Temporary staging residue was preserved at "
                    f"{cleanup_warning['path']}: {cleanup_warning['message']}"
                )
            emit({
                "ok": False,
                "installed": False,
                "failures": [failure],
            })
            return 2

        if success_payload is None:
            raise ToolFailure(
                "sync-outcome-missing",
                "Synchronization ended without a recorded success or failure.",
                target,
            )
        if cleanup_warning is not None:
            warnings = success_payload.setdefault("warnings", [])
            if isinstance(warnings, list):
                warnings.append(cleanup_warning)
            success_payload["staging_path"] = cleanup_warning["path"]
        emit(success_payload)
        return 0
    except ToolFailure as exc:
        emit({"ok": False, "failures": [exc.issue.as_dict()]})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
