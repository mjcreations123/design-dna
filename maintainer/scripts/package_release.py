#!/usr/bin/env python3
"""Build or verify a deterministic release archive from one exact Git commit."""

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
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from pathlib import PurePosixPath

from jsonschema import Draft202012Validator

from common import (
    ToolFailure,
    absolute,
    assert_no_reparse_path,
    emit,
    is_within,
    load_json,
    strict_format_checker,
)


SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,200}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_GIT_MODES = {"100644", "100755"}
MAX_ARCHIVE_ENTRIES = 50_000
MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024


def stable_bytes(path: Path) -> bytes:
    assert_no_reparse_path(path)
    try:
        first = path.read_bytes()
        second = path.read_bytes()
    except OSError as exc:
        raise ToolFailure("release-package-input-unreadable", str(exc), path) from exc
    if first != second:
        raise ToolFailure(
            "release-package-input-unstable",
            "Input changed while it was read.",
            path,
        )
    return first


def sha256_file(path: Path) -> str:
    return hashlib.sha256(stable_bytes(path)).hexdigest()


def git_command(
    plugin_root: Path,
    *arguments: str,
    timeout: int = 120,
) -> str:
    command = [
        "git",
        "-c",
        f"safe.directory={plugin_root.as_posix()}",
        "-C",
        str(plugin_root),
        *arguments,
    ]
    try:
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolFailure(
            "release-package-git-unavailable",
            str(exc),
            plugin_root,
        ) from exc
    if result.returncode != 0:
        raise ToolFailure(
            "release-package-git-failed",
            (result.stderr or result.stdout or "Git command failed.").strip(),
            plugin_root,
        )
    return result.stdout.strip()


def git_command_bytes(
    plugin_root: Path,
    *arguments: str,
    timeout: int = 120,
) -> bytes:
    command = [
        "git",
        "-c",
        f"safe.directory={plugin_root.as_posix()}",
        "-C",
        str(plugin_root),
        *arguments,
    ]
    try:
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolFailure(
            "release-package-git-unavailable",
            str(exc),
            plugin_root,
        ) from exc
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ToolFailure(
            "release-package-git-failed",
            message or "Git command failed.",
            plugin_root,
        )
    return result.stdout


def git_tree_records(
    plugin_root: Path,
    ref: str,
) -> dict[str, tuple[str, str]]:
    """Return safe regular-file paths bound to their exact Git blob IDs."""
    output = git_command_bytes(
        plugin_root,
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        ref,
    )
    records: dict[str, tuple[str, str]] = {}
    casefolded: dict[str, str] = {}
    for raw_record in output.split(b"\0"):
        if not raw_record:
            continue
        try:
            metadata, raw_path = raw_record.split(b"\t", 1)
            mode, object_type, object_id = metadata.decode("ascii").split()
            path = raw_path.decode("utf-8")
        except (UnicodeDecodeError, ValueError) as exc:
            raise ToolFailure(
                "release-package-git-tree-invalid",
                "Git tree contains an unsupported record or non-UTF-8 path.",
                plugin_root,
            ) from exc
        normalized = PurePosixPath(path)
        if (
            normalized.as_posix() != path
            or normalized.is_absolute()
            or ".." in normalized.parts
            or "\\" in path
            or any(ord(character) < 32 or ord(character) == 127 for character in path)
        ):
            raise ToolFailure(
                "release-package-git-path-unsafe",
                "Git tree contains an unsafe archive path.",
                plugin_root,
            )
        if object_type != "blob" or mode not in SAFE_GIT_MODES:
            raise ToolFailure(
                "release-package-git-mode-unsafe",
                (
                    f"Only ordinary 100644/100755 files may ship; "
                    f"{path!r} is {mode} {object_type}."
                ),
                plugin_root,
            )
        key = path.casefold()
        if key in casefolded:
            raise ToolFailure(
                "release-package-case-collision",
                (
                    f"Git paths {casefolded[key]!r} and {path!r} collide "
                    "on case-insensitive filesystems."
                ),
                plugin_root,
            )
        casefolded[key] = path
        records[path] = (mode, object_id)
    if not records:
        raise ToolFailure(
            "release-package-git-tree-empty",
            "Release ref contains no ordinary files.",
            plugin_root,
        )
    if len(records) > MAX_ARCHIVE_ENTRIES:
        raise ToolFailure(
            "release-package-entry-limit",
            "Release ref exceeds the archive entry limit.",
            plugin_root,
        )
    return records


def validate_archive_against_git(
    plugin_root: Path,
    ref: str,
    archive_path: Path,
    prefix: str,
) -> None:
    """Prove every archived file is one exact safe blob from the selected ref."""
    records = git_tree_records(plugin_root, ref)
    expected = {f"{prefix}/{path}": record for path, record in records.items()}
    observed: set[str] = set()
    observed_casefolded: set[str] = set()
    total_bytes = 0
    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_ENTRIES + 1:
                raise ToolFailure(
                    "release-package-entry-limit",
                    "Release archive exceeds the entry limit.",
                    archive_path,
                )
            for info in infos:
                name = info.filename
                normalized = PurePosixPath(name.rstrip("/"))
                if (
                    not name
                    or "\\" in name
                    or normalized.is_absolute()
                    or ".." in normalized.parts
                    or normalized.as_posix() != name.rstrip("/")
                    or any(
                        ord(character) < 32 or ord(character) == 127
                        for character in name
                    )
                ):
                    raise ToolFailure(
                        "release-package-archive-path-unsafe",
                        "Archive contains an unsafe path.",
                        archive_path,
                    )
                key = name.casefold()
                if key in observed_casefolded:
                    raise ToolFailure(
                        "release-package-archive-path-duplicate",
                        "Archive contains duplicate or case-colliding paths.",
                        archive_path,
                    )
                observed_casefolded.add(key)
                if info.flag_bits & 0x1:
                    raise ToolFailure(
                        "release-package-archive-encrypted",
                        "Encrypted release entries are not permitted.",
                        archive_path,
                    )
                unix_type = (info.external_attr >> 16) & 0o170000
                if info.is_dir():
                    if name == f"{prefix}/":
                        continue
                    if not name.startswith(f"{prefix}/"):
                        raise ToolFailure(
                            "release-package-archive-prefix-invalid",
                            "Archive directory escapes the exact release prefix.",
                            archive_path,
                        )
                    continue
                if unix_type not in {0, 0o100000}:
                    raise ToolFailure(
                        "release-package-archive-mode-unsafe",
                        "Archive contains a non-regular entry.",
                        archive_path,
                    )
                if name not in expected:
                    raise ToolFailure(
                        "release-package-archive-extra",
                        "Archive contains a file not present in the selected Git ref.",
                        archive_path,
                    )
                total_bytes += info.file_size
                if total_bytes > MAX_ARCHIVE_BYTES:
                    raise ToolFailure(
                        "release-package-byte-limit",
                        "Release archive exceeds the uncompressed byte limit.",
                        archive_path,
                    )
                _mode, object_id = expected[name]
                blob = git_command_bytes(
                    plugin_root,
                    "cat-file",
                    "blob",
                    object_id,
                )
                archived = archive.read(info)
                if len(blob) != info.file_size or archived != blob:
                    raise ToolFailure(
                        "release-package-archive-content-mismatch",
                        (
                            "Archive bytes differ from the selected Git blob "
                            f"(archive={len(archived)} bytes/"
                            f"{hashlib.sha256(archived).hexdigest()}, "
                            f"blob={len(blob)} bytes/"
                            f"{hashlib.sha256(blob).hexdigest()})."
                        ),
                        archive_path,
                    )
                observed.add(name)
    except zipfile.BadZipFile as exc:
        raise ToolFailure(
            "release-package-archive-invalid",
            str(exc),
            archive_path,
        ) from exc
    missing = sorted(set(expected) - observed)
    if missing:
        raise ToolFailure(
            "release-package-archive-missing",
            (
                f"Archive omitted {len(missing)} tracked file(s); first "
                f"missing path: {missing[0]!r}."
            ),
            archive_path,
        )


def validate_ref(value: str) -> str:
    if (
        not SAFE_REF.fullmatch(value)
        or ".." in value
        or "//" in value
        or value.endswith("/")
        or "@{" in value
    ):
        raise ToolFailure(
            "release-package-ref-invalid",
            "Ref must be one safe explicit branch, tag, or commit name.",
        )
    return value


def ensure_clean_worktree(plugin_root: Path) -> None:
    status = git_command(
        plugin_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    if status:
        raise ToolFailure(
            "release-package-worktree-dirty",
            "Commit every package change before building a release archive.",
            plugin_root,
        )


def ensure_worktree_bytes_match_ref(plugin_root: Path, ref: str) -> None:
    """Reject checkout filters or line-ending drift hidden by Git status.

    ``git status`` compares normalized content, so a file declared ``eol=lf``
    can contain CRLF bytes in the worktree while still appearing clean. The
    release manifest is assembled from worktree bytes but the archive is
    assembled from Git blobs; those two identities must be byte-for-byte
    identical before packaging.
    """
    for relative, (_mode, object_id) in sorted(git_tree_records(plugin_root, ref).items()):
        path = plugin_root.joinpath(*PurePosixPath(relative).parts)
        if not path.is_file():
            raise ToolFailure(
                "release-package-worktree-file-missing",
                "A tracked release file is missing from the worktree.",
                path,
            )
        worktree = stable_bytes(path)
        blob = git_command_bytes(plugin_root, "cat-file", "blob", object_id)
        if worktree != blob:
            raise ToolFailure(
                "release-package-worktree-byte-drift",
                (
                    "A tracked file appears clean after Git normalization but "
                    "its worktree bytes differ from the selected Git blob "
                    f"(worktree={len(worktree)} bytes/"
                    f"{hashlib.sha256(worktree).hexdigest()}, blob={len(blob)} "
                    f"bytes/{hashlib.sha256(blob).hexdigest()}). Normalize the "
                    "file bytes before regenerating release metadata."
                ),
                path,
            )


def resolved_commit(plugin_root: Path, ref: str) -> str:
    commit = git_command(
        plugin_root,
        "rev-parse",
        "--verify",
        f"{ref}^{{commit}}",
    )
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise ToolFailure(
            "release-package-commit-invalid",
            "Git did not resolve one full commit identity.",
            plugin_root,
        )
    return commit


def validate_release_ref(
    plugin_root: Path,
    ref: str,
    version: str,
    commit: str,
) -> None:
    if ref != f"v{version}":
        raise ToolFailure(
            "release-package-tag-version-mismatch",
            f"Release mode requires exact annotated tag v{version}.",
            plugin_root,
        )
    tag_type = git_command(
        plugin_root,
        "cat-file",
        "-t",
        ref,
    )
    if tag_type != "tag":
        raise ToolFailure(
            "release-package-tag-not-annotated",
            "Release packaging requires an annotated tag object.",
            plugin_root,
        )
    head = resolved_commit(plugin_root, "HEAD")
    if head != commit:
        raise ToolFailure(
            "release-package-tag-not-head",
            "The release tag must identify the current clean HEAD.",
            plugin_root,
        )


def validate_ref_matches_head(
    plugin_root: Path,
    ref: str,
    commit: str,
) -> None:
    head = resolved_commit(plugin_root, "HEAD")
    if commit != head:
        raise ToolFailure(
            "release-package-ref-not-head",
            (
                f"Ref {ref!r} does not identify the current clean HEAD. "
                "Package metadata is read from the worktree, so divergent refs "
                "are refused."
            ),
            plugin_root,
        )


def validated_codex_validator(
    plugin_root: Path,
    selected: Path | None,
    *,
    release: bool,
) -> Path | None:
    """Resolve the external validator required by the strict release audit."""

    if selected is None:
        if release:
            raise ToolFailure(
                "release-package-codex-validator-required",
                (
                    "--release requires the absolute external Plugin Creator "
                    "validate_plugin.py path so strict audit can replay the "
                    "publisher-reviewed validator."
                ),
                plugin_root,
            )
        return None
    if not selected.is_absolute():
        raise ToolFailure(
            "release-package-codex-validator-path-not-absolute",
            "--codex-validator must be an absolute external path.",
            selected,
        )
    validator = absolute(selected)
    assert_no_reparse_path(validator)
    if not validator.is_file():
        raise ToolFailure(
            "release-package-codex-validator-unavailable",
            "The selected Codex Plugin Creator validator is not an ordinary file.",
            validator,
        )
    if is_within(validator, plugin_root):
        raise ToolFailure(
            "release-package-codex-validator-not-external",
            "The Codex validator must remain outside the package it validates.",
            validator,
        )
    return validator


def run_validation(
    plugin_root: Path,
    *,
    release: bool,
    previous_manifest: Path | None,
    home: Path,
    codex_validator: Path | None,
) -> None:
    if release and codex_validator is None:
        raise ToolFailure(
            "release-package-codex-validator-required",
            "Strict release validation requires the external Codex validator.",
            plugin_root,
        )
    manifest_command = [
        sys.executable,
        "-B",
        str(plugin_root / "maintainer" / "scripts" / "build_manifest.py"),
        "--skill-root",
        str(plugin_root / "skills" / "design-dna"),
        "--output",
        str(plugin_root / "maintainer" / "release-manifest.json"),
        "--check",
    ]
    if previous_manifest is not None:
        manifest_command.extend(["--previous", str(previous_manifest)])
    audit_command = [
        sys.executable,
        "-B",
        str(plugin_root / "maintainer" / "scripts" / "audit_package.py"),
        "--plugin-root",
        str(plugin_root),
        "--home",
        str(home),
    ]
    if codex_validator is not None:
        audit_command.extend([
            "--codex-validator",
            str(codex_validator),
        ])
    if release:
        audit_command.append("--release")
    commands = (
        [
            sys.executable,
            "-B",
            str(plugin_root / "maintainer" / "scripts" / "build_sbom.py"),
            "--plugin-root",
            str(plugin_root),
            "--output",
            str(plugin_root / "maintainer" / "sbom.spdx.json"),
            "--check",
        ],
        manifest_command,
        audit_command,
    )
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for command in commands:
        try:
            result = subprocess.run(
                command,
                cwd=plugin_root,
                env=environment,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=300,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ToolFailure(
                "release-package-validation-unavailable",
                str(exc),
                Path(command[2]),
            ) from exc
        if result.returncode != 0:
            raise ToolFailure(
                "release-package-validation-failed",
                (result.stdout + result.stderr).strip(),
                Path(command[2]),
            )


def git_archive(
    plugin_root: Path,
    ref: str,
    destination: Path,
    prefix: str,
) -> None:
    try:
        result = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={plugin_root.as_posix()}",
                "-c",
                "core.autocrlf=false",
                "-c",
                "core.eol=lf",
                "-C",
                str(plugin_root),
                "archive",
                "--format=zip",
                f"--prefix={prefix}/",
                f"--output={destination}",
                ref,
            ],
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolFailure(
            "release-package-archive-unavailable",
            str(exc),
            plugin_root,
        ) from exc
    if result.returncode != 0 or not destination.is_file():
        raise ToolFailure(
            "release-package-archive-failed",
            (result.stderr or result.stdout or "Git archive failed.").strip(),
            destination,
        )
    validate_archive_against_git(
        plugin_root,
        ref,
        destination,
        prefix,
    )


def validate_record(payload: object, schema_path: Path) -> None:
    schema = load_json(schema_path)
    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=strict_format_checker(),
        ).iter_errors(payload),
        key=lambda item: tuple(str(part) for part in item.path),
    )
    if errors:
        raise ToolFailure(
            "release-package-record-invalid",
            "; ".join(
                f"{'/'.join(map(str, error.path)) or '<root>'}: "
                f"{error.message}"
                for error in errors
            ),
            schema_path,
        )


def atomic_write(path: Path, data: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def package_record(
    plugin_root: Path,
    ref: str,
    commit: str,
    archive_name: str,
    archive_sha256: str,
    archive_bytes: int,
) -> dict[str, object]:
    release_manifest_path = plugin_root / "maintainer" / "release-manifest.json"
    sbom_path = plugin_root / "maintainer" / "sbom.spdx.json"
    release_manifest = load_json(release_manifest_path)
    release = load_json(plugin_root / "skills" / "design-dna" / "release.json")
    if not isinstance(release_manifest, dict) or not isinstance(release, dict):
        raise ToolFailure(
            "release-package-metadata-invalid",
            "Release metadata must be JSON objects.",
            plugin_root,
        )
    version = release.get("version")
    release_identity = release_manifest.get("release_sha256")
    if (
        not isinstance(version, str)
        or not isinstance(release_identity, str)
        or not SHA256.fullmatch(release_identity)
    ):
        raise ToolFailure(
            "release-package-metadata-invalid",
            "Version or release identity is missing.",
            release_manifest_path,
        )
    commit_time = git_command(
        plugin_root,
        "show",
        "-s",
        "--format=%cI",
        commit,
    )
    return {
        "schema_version": 1,
        "record_type": "design-dna-release-package",
        "package": "design-dna",
        "version": version,
        "ref": ref,
        "commit": commit,
        "commit_time": commit_time,
        "release_identity_sha256": release_identity,
        "release_manifest_sha256": sha256_file(release_manifest_path),
        "sbom_sha256": sha256_file(sbom_path),
        "archive": {
            "name": archive_name,
            "sha256": archive_sha256,
            "bytes": archive_bytes,
            "format": "zip",
            "prefix": f"design-dna-{version}/",
        },
        "checksum_file": {
            "name": f"{archive_name}.sha256",
            "format": "sha256sum",
        },
        "signature_policy": "external-detached-required",
        "required_signatures": [
            {
                "role": "release-package",
                "name": "release-package.json.asc",
            },
            {
                "role": "archive",
                "name": f"{archive_name}.asc",
            },
            {
                "role": "checksum",
                "name": f"{archive_name}.sha256.asc",
            },
        ],
        "signature_limitation": (
            "The builder produces unsigned candidate bytes. Make and verify "
            "the three required detached signatures with the owner's "
            "established release key before representing the package as "
            "authenticated; signed-tag verification is a separate gate."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_plugin = Path(__file__).resolve().parents[2]
    parser.add_argument("--plugin-root", type=Path, default=default_plugin)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument(
        "--home",
        type=Path,
        default=Path.home(),
        help="Explicit home root used to replay portable installed-route evidence.",
    )
    parser.add_argument(
        "--codex-validator",
        type=Path,
        help=(
            "Absolute external Plugin Creator validate_plugin.py path; "
            "required with --release."
        ),
    )
    parser.add_argument(
        "--previous-manifest",
        type=Path,
        help=(
            "Preserved prior-version manifest identity. Required with "
            "--release so version reuse cannot silently bypass comparison."
        ),
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Require a clean HEAD and exact annotated vVERSION tag.",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        plugin_root = absolute(args.plugin_root)
        output_dir = absolute(args.output_dir)
        home = absolute(args.home)
        ref = validate_ref(args.ref)
        assert_no_reparse_path(plugin_root)
        if not (plugin_root / ".git").is_dir():
            raise ToolFailure(
                "release-package-git-root-invalid",
                "Plugin root must be a Git worktree root.",
                plugin_root,
            )
        if (
            not output_dir.is_dir()
            or is_within(output_dir, plugin_root)
            or output_dir == Path(output_dir.anchor)
            or output_dir == absolute(Path.home())
        ):
            raise ToolFailure(
                "release-package-output-unsafe",
                "Output must be an existing ordinary directory outside the package, home, and filesystem root.",
                output_dir,
            )
        assert_no_reparse_path(output_dir)
        assert_no_reparse_path(home)
        if not home.is_dir():
            raise ToolFailure(
                "release-package-home-invalid",
                "--home must identify an existing ordinary directory.",
                home,
            )
        codex_validator = validated_codex_validator(
            plugin_root,
            args.codex_validator,
            release=args.release,
        )
        ensure_clean_worktree(plugin_root)
        commit = resolved_commit(plugin_root, ref)
        validate_ref_matches_head(plugin_root, ref, commit)
        ensure_worktree_bytes_match_ref(plugin_root, ref)
        release = load_json(plugin_root / "skills" / "design-dna" / "release.json")
        version = release.get("version") if isinstance(release, dict) else None
        if not isinstance(version, str):
            raise ToolFailure(
                "release-package-version-invalid",
                "Runtime release version is missing.",
                plugin_root / "skills" / "design-dna" / "release.json",
            )
        if args.release:
            if args.previous_manifest is None:
                raise ToolFailure(
                    "release-package-previous-manifest-required",
                    "--release requires --previous-manifest.",
                    plugin_root,
                )
            validate_release_ref(plugin_root, ref, version, commit)
        previous_manifest = (
            absolute(args.previous_manifest)
            if args.previous_manifest is not None
            else None
        )
        if previous_manifest is not None:
            expected_history = plugin_root / "maintainer" / "releases"
            if not is_within(previous_manifest, expected_history):
                raise ToolFailure(
                    "release-package-previous-manifest-unsafe",
                    "Previous manifest must be a preserved file under maintainer/releases.",
                    previous_manifest,
                )
            assert_no_reparse_path(previous_manifest, stop=expected_history)
            if not previous_manifest.is_file():
                raise ToolFailure(
                    "release-package-previous-manifest-missing",
                    "Previous manifest does not exist.",
                    previous_manifest,
                )
        run_validation(
            plugin_root,
            release=args.release,
            previous_manifest=previous_manifest,
            home=home,
            codex_validator=codex_validator,
        )
        bundle_name = f"design-dna-{version}-{commit[:12]}"
        bundle_dir = output_dir / bundle_name
        archive_name = f"{bundle_name}.zip"
        archive_path = bundle_dir / archive_name
        checksum_path = bundle_dir / f"{archive_name}.sha256"
        record_path = bundle_dir / "release-package.json"
        destinations = (archive_path, checksum_path, record_path)
        if args.check:
            assert_no_reparse_path(bundle_dir, stop=output_dir)
            if not bundle_dir.is_dir() or not all(
                path.is_file() for path in destinations
            ):
                raise ToolFailure(
                    "release-package-output-missing",
                    "Archive, checksum, and release-package record must all exist.",
                    bundle_dir,
                )
        elif bundle_dir.exists():
            raise ToolFailure(
                "release-package-output-exists",
                (
                    "Release bundles are immutable. Use --check for this ref "
                    "or a new output parent for a new build."
                ),
                bundle_dir,
            )

        staging = Path(
            tempfile.mkdtemp(prefix=f".{bundle_name}-stage-", dir=output_dir)
        )
        staging_archive = staging / archive_name
        try:
            git_archive(
                plugin_root,
                ref,
                staging_archive,
                f"design-dna-{version}",
            )
            archive_data = stable_bytes(staging_archive)
            archive_hash = hashlib.sha256(archive_data).hexdigest()
            record = package_record(
                plugin_root,
                ref,
                commit,
                archive_name,
                archive_hash,
                len(archive_data),
            )
            validate_record(
                record,
                plugin_root
                / "maintainer"
                / "schemas"
                / "release-package.schema.json",
            )
            checksum_data = f"{archive_hash}  {archive_name}\n".encode("utf-8")
            record_data = (
                json.dumps(record, indent=2, ensure_ascii=False) + "\n"
            ).encode("utf-8")
            atomic_write(staging / f"{archive_name}.sha256", checksum_data)
            atomic_write(staging / "release-package.json", record_data)
            if args.check:
                if (
                    stable_bytes(archive_path) != archive_data
                    or stable_bytes(checksum_path) != checksum_data
                    or stable_bytes(record_path) != record_data
                ):
                    raise ToolFailure(
                        "release-package-drift",
                        (
                            "Published package artifacts differ from the "
                            "exact current ref."
                        ),
                        bundle_dir,
                    )
            else:
                assert_no_reparse_path(bundle_dir, stop=output_dir)
                staging.rename(bundle_dir)
                staging = bundle_dir
        finally:
            if (
                staging.exists()
                and staging != bundle_dir
                and is_within(staging, output_dir)
                and staging.name.startswith(f".{bundle_name}-stage-")
            ):
                shutil.rmtree(staging)
        emit({
            "ok": True,
            "check": args.check,
            "archive": str(archive_path),
            "sha256": archive_hash,
            "commit": commit,
            "ref": ref,
            "record": str(record_path),
            "signature_policy": "external-detached-required",
        })
        return 0
    except (ToolFailure, OSError, UnicodeError, ValueError) as exc:
        failure = (
            exc.issue.as_dict()
            if isinstance(exc, ToolFailure)
            else {"code": "release-package-unexpected-error", "message": str(exc)}
        )
        emit({"ok": False, "failures": [failure]})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
