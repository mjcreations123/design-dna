#!/usr/bin/env python3
"""Run controlled Design DNA skill-versus-baseline evaluations.

This harness creates a new workspace and fake home for every run, stages the
exact runtime skill only for the skill variant, and keeps the task text
identical between variants. It provides controlled process isolation, not an
operating-system security sandbox; only trusted drivers are appropriate.
"""

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
import base64
import hashlib
import json
import math
import os
import re
import secrets
import signal
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from common import (
    ToolFailure,
    absolute,
    assert_contained,
    assert_no_reparse_path,
    content_manifest,
    eval_content_manifest,
    emit,
    entry_exists,
    is_reparse,
    is_within,
    load_json,
    strict_format_checker,
    walk_entries,
    walk_eval_entries,
)


MAX_CAPTURE_CHARS = 250_000
MAX_OUTPUT_BYTES = 20 * 1024 * 1024
MAX_WORKSPACE_FILES = 20_000
MAX_WORKSPACE_ENTRIES = 40_000
MAX_WORKSPACE_BYTES = 500 * 1024 * 1024
MAX_INSPECT_TEXT_BYTES = 5 * 1024 * 1024
DEFAULT_HOST_EVIDENCE_WAIT_SECONDS = 5.0
MAX_HOST_EVIDENCE_WAIT_SECONDS = 60.0
HOST_EVIDENCE_CLOCK_SKEW_SECONDS = 5.0
MIN_PASSED_ENV_VALUE_LENGTH = 8
MAX_SENSITIVE_SCAN_ENTRIES = 50_000
MAX_SENSITIVE_SCAN_BYTES = 750 * 1024 * 1024
NONCE_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
MODEL_COMPONENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]*$")
PROVIDER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
REASONING_EFFORT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
GENERATION_CONFIG_KEYS = {
    "temperature",
    "top_p",
    "top_k",
    "seed",
    "max_output_tokens",
    "max_tokens",
    "reasoning_budget",
    "thinking_budget",
    "response_format",
    "tool_choice",
    "parallel_tool_calls",
}
SENSITIVE_TEXT = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|authorization|bearer\s|"
    r"password|private[_-]?key|secret|(?:^|[^a-z0-9])sk-[A-Za-z0-9])"
)


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def digest_file(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while block := handle.read(1024 * 1024):
                digest.update(block)
        return digest.hexdigest()
    except OSError as exc:
        raise ToolFailure("file-hash-failed", str(exc), path) from exc


def digest_mapping(value: dict[str, str]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_generation_config(
    values: list[str],
    *,
    label: str,
) -> dict[str, object]:
    result: dict[str, object] = {}
    for raw in values:
        if "=" not in raw:
            raise ToolFailure(
                "invalid-generation-config",
                f"{label} entries must use KEY=VALUE.",
            )
        key, encoded = raw.split("=", 1)
        key = key.strip()
        encoded = encoded.strip()
        if key not in GENERATION_CONFIG_KEYS:
            raise ToolFailure(
                "invalid-generation-config-key",
                (
                    f"{label} key {key!r} is not an approved non-secret "
                    "generation setting."
                ),
            )
        if key in result:
            raise ToolFailure(
                "duplicate-generation-config-key",
                f"{label} repeats {key!r}.",
            )
        if not encoded:
            raise ToolFailure(
                "invalid-generation-config",
                f"{label} value for {key!r} is empty.",
            )
        try:
            parsed = json.loads(encoded)
        except json.JSONDecodeError:
            parsed = encoded
        if (
            parsed is None
            or isinstance(parsed, (list, dict))
            or not isinstance(parsed, (str, int, float, bool))
        ):
            raise ToolFailure(
                "invalid-generation-config-value",
                (
                    f"{label} value for {key!r} must be a short JSON scalar "
                    "or plain string."
                ),
            )
        if isinstance(parsed, float) and not math.isfinite(parsed):
            raise ToolFailure(
                "invalid-generation-config-value",
                f"{label} value for {key!r} must be finite.",
            )
        if isinstance(parsed, str):
            if len(parsed) > 64:
                raise ToolFailure(
                    "generation-config-value-too-long",
                    f"{label} value for {key!r} exceeds 64 characters.",
                )
            if SENSITIVE_TEXT.search(parsed):
                raise ToolFailure(
                    "sensitive-generation-config-refused",
                    (
                        f"{label} value for {key!r} resembles a secret. "
                        "Evaluation metadata must never store credentials."
                    ),
                )
        result[key] = parsed
    return dict(sorted(result.items()))


def finalize_model_context(payload: dict[str, object]) -> dict[str, object]:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return {**payload, "sha256": digest_text(encoded)}


def model_context(
    *,
    provider: str | None,
    model: str | None,
    model_version: str | None,
    reasoning_effort: str | None,
    generation_config: list[str],
    label: str,
    inherited: dict[str, object] | None = None,
) -> dict[str, object]:
    raw_values = (provider, model, model_version, reasoning_effort)
    any_declared = any(value is not None for value in raw_values) or bool(
        generation_config
    )
    if not any_declared and inherited is not None:
        inherited_core = {
            key: value
            for key, value in inherited.items()
            if key != "sha256"
        }
        inherited_core["declaration_source"] = "inherited-from-skill"
        return finalize_model_context(inherited_core)
    if not any_declared:
        return finalize_model_context({
            "declaration_status": "unreported",
            "provider": None,
            "model": None,
            "model_version": None,
            "reasoning_effort": None,
            "generation_config": {},
            "declaration_source": "not-provided",
        })
    fields = {
        "provider": provider,
        "model": model,
        "model_version": model_version,
        "reasoning_effort": reasoning_effort,
    }
    missing = [name for name, value in fields.items() if value is None]
    if missing:
        raise ToolFailure(
            "incomplete-model-context",
            f"{label} is missing: {', '.join(missing)}.",
        )
    assert provider is not None
    assert model is not None
    assert model_version is not None
    assert reasoning_effort is not None
    for field_name, value in (
        ("provider", provider),
        ("model", model),
        ("model_version", model_version),
        ("reasoning_effort", reasoning_effort),
    ):
        if SENSITIVE_TEXT.search(value):
            raise ToolFailure(
                "sensitive-model-context-refused",
                (
                    f"{label} {field_name} resembles a secret. Evaluation "
                    "metadata must never store credentials."
                ),
            )
    if (
        len(provider) > 64
        or len(provider) < 2
        or not PROVIDER_PATTERN.fullmatch(provider)
    ):
        raise ToolFailure(
            "invalid-model-provider",
            f"{label} provider has an unsupported format.",
        )
    for field_name, value in (
        ("model", model),
        ("model_version", model_version),
    ):
        if (
            len(value) > 256
            or not MODEL_COMPONENT_PATTERN.fullmatch(value)
        ):
            raise ToolFailure(
                "invalid-model-identity",
                f"{label} {field_name} has an unsupported format.",
            )
    if model_version.casefold() in {
        "latest",
        "current",
        "default",
        "unknown",
        "unreported",
    }:
        raise ToolFailure(
            "nonreproducible-model-version",
            (
                f"{label} model_version must be a concrete provider revision "
                "or observed version, not a moving alias."
            ),
        )
    if (
        len(reasoning_effort) > 64
        or not REASONING_EFFORT_PATTERN.fullmatch(reasoning_effort)
    ):
        raise ToolFailure(
            "invalid-reasoning-effort",
            f"{label} reasoning effort has an unsupported format.",
        )
    return finalize_model_context({
        "declaration_status": "declared",
        "provider": provider,
        "model": model,
        "model_version": model_version,
        "reasoning_effort": reasoning_effort,
        "generation_config": parse_generation_config(
            generation_config,
            label=label,
        ),
        "declaration_source": "maintainer-cli",
    })


def case_review_contract(case: dict[str, object]) -> dict[str, object]:
    """Create the immutable post-run review contract recorded with every run."""
    requirement_records: list[dict[str, str]] = []
    for index, raw in enumerate(case.get("review_requirements", []), start=1):
        text = str(raw)
        text_sha256 = digest_text(text)
        requirement_records.append({
            "id": f"requirement-{index:02d}-{text_sha256[:16]}",
            "text": text,
            "sha256": text_sha256,
        })
    coverage = case.get("release_coverage")
    core: dict[str, object] = {
        "schema_version": 1,
        "adversarial_required": bool(case.get("adversarial", False)),
        "requirements": requirement_records,
        "release_coverage": (
            dict(coverage) if isinstance(coverage, dict) else None
        ),
    }
    encoded = json.dumps(
        core,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return {
        **core,
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def snapshot(root: Path) -> dict[str, str]:
    if not entry_exists(root):
        return {}
    records, _ = eval_content_manifest(root)
    return {
        str(item["path"]): (
            str(item["sha256"])
            if item["type"] == "file"
            else "<directory>"
        )
        for item in records
    }


def monitor_snapshot(root: Path) -> dict[str, str]:
    """Hash every entry, including transient names excluded from release manifests."""
    root = absolute(root)
    if not entry_exists(root):
        return {"<root>": "missing"}
    assert_no_reparse_path(root)
    if not root.is_dir():
        raise ToolFailure(
            "monitor-root-not-directory",
            "Monitor roots must be directories.",
            root,
        )
    records: dict[str, str] = {"<root>": "directory"}

    def fail_walk(error: OSError) -> None:
        raise ToolFailure(
            "monitor-enumeration-failed",
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
                    "monitor-reparse-refused",
                    "Monitor contains a link or reparse point.",
                    child,
                )
            records[f"d:{child.relative_to(root).as_posix()}"] = "directory"
        for name in files:
            child = current_path / name
            if is_reparse(child):
                raise ToolFailure(
                    "monitor-reparse-refused",
                    "Monitor contains a link or reparse point.",
                    child,
                )
            try:
                data = child.read_bytes()
            except OSError as exc:
                raise ToolFailure(
                    "monitor-read-failed",
                    str(exc),
                    child,
                ) from exc
            records[f"f:{child.relative_to(root).as_posix()}"] = hashlib.sha256(
                data
            ).hexdigest()
    return records


def snapshot_diff(
    before: dict[str, str],
    after: dict[str, str],
    *,
    maximum: int = 500,
) -> tuple[list[str], bool]:
    paths = sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    )
    return paths[:maximum], len(paths) > maximum


def copy_tree(source: Path, destination: Path) -> None:
    destination.mkdir()
    for source_entry in walk_entries(source):
        relative = source_entry.relative_to(source)
        target = destination / relative
        if source_entry.is_dir():
            target.mkdir(exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_entry, target, follow_symlinks=False)


def copy_eval_tree(
    source: Path,
    destination: Path,
    *,
    destination_exists: bool = False,
) -> None:
    """Copy every evidence entry, including caches and empty directories."""
    source_inventory = workspace_inventory(source)
    if destination_exists:
        if not destination.is_dir():
            raise ToolFailure(
                "eval-copy-destination-missing",
                "Existing evaluation copy destination is not a directory.",
                destination,
            )
    else:
        destination.mkdir()
    for source_entry in walk_eval_entries(source):
        relative = source_entry.relative_to(source)
        target = destination / relative
        if source_entry.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_entry, target, follow_symlinks=False)
    copied_inventory = workspace_inventory(destination)
    if copied_inventory != source_inventory:
        raise ToolFailure(
            "eval-copy-inventory-parity-failed",
            "Evaluation copy entry, file, or byte counts differ from its source.",
            destination,
        )


def promote_artifact_bundle(
    workspace: Path,
    results_dir: Path,
    session_key: str,
    run_id: str,
    expected_records: list[dict[str, object]],
    expected_hash: str,
) -> dict[str, object]:
    """Copy a completed workspace into stable, hash-verified result evidence."""
    run_key = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:24]
    relative = Path("artifacts") / session_key / run_key
    destination = absolute(results_dir / relative)
    assert_contained(destination, results_dir, parent_must_exist=False)
    if entry_exists(destination):
        raise ToolFailure(
            "artifact-bundle-collision",
            "Refusing to replace an existing evaluation artifact bundle.",
            destination,
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    assert_contained(destination, results_dir)
    assert_no_reparse_path(destination.parent, stop=results_dir)
    staging_parent = Path(
        tempfile.mkdtemp(prefix=f".{run_key}-stage-", dir=destination.parent)
    )
    staging = staging_parent / "bundle"
    try:
        copy_eval_tree(workspace, staging)
        records, content_hash = eval_content_manifest(staging)
        if records != expected_records or content_hash != expected_hash:
            raise ToolFailure(
                "artifact-bundle-parity-failed",
                "Promoted artifact does not match the captured workspace manifest.",
                staging,
            )
        staging.rename(destination)
        staging_parent.rmdir()
    except Exception:
        try:
            if entry_exists(staging_parent):
                assert_contained(staging_parent, results_dir)
                assert_no_reparse_path(staging_parent, stop=results_dir)
                shutil.rmtree(staging_parent)
        except (ToolFailure, OSError):
            pass
        raise
    file_count = sum(item.get("type") == "file" for item in expected_records)
    entry_count = len(expected_records)
    total_bytes = sum(
        int(item.get("size", 0))
        for item in expected_records
        if item.get("type") == "file"
    )
    return {
        "path": relative.as_posix(),
        "sha256": expected_hash,
        "entry_count": entry_count,
        "file_count": file_count,
        "bytes": total_bytes,
        "source": "promoted-workspace",
    }


def copy_inputs(source: Path, destination: Path, fixture_root: Path) -> dict[str, str]:
    source = absolute(source)
    if not is_within(source, fixture_root):
        raise ToolFailure(
            "fixture-input-escape",
            "input_dir must stay within the fixture directory.",
            source,
        )
    assert_no_reparse_path(source, stop=fixture_root)
    if not source.is_dir():
        raise ToolFailure("fixture-input-missing", "input_dir does not exist.", source)
    copy_eval_tree(source, destination, destination_exists=True)
    return snapshot(destination)


def render_args(parts: list[str], values: dict[str, str]) -> list[str]:
    rendered: list[str] = []
    for part in parts:
        value = part
        for key, replacement in values.items():
            value = value.replace("{" + key + "}", replacement)
        rendered.append(value)
    return rendered


def safe_workspace_path(workspace: Path, relative: object) -> Path:
    text = str(relative)
    raw = Path(text)
    if raw.is_absolute() or ".." in raw.parts:
        raise ToolFailure(
            "expectation-path-escape",
            "Expectation paths must be project-relative.",
            raw,
        )
    candidate = absolute(workspace / raw)
    if not is_within(candidate, workspace):
        raise ToolFailure(
            "expectation-path-escape",
            "Expectation path leaves the workspace.",
            candidate,
        )
    assert_no_reparse_path(candidate, stop=workspace)
    return candidate


def current_file_hashes(workspace: Path) -> dict[str, str]:
    return snapshot(workspace)


def changed_paths(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    )


def workspace_inventory(root: Path) -> tuple[int, int, int]:
    entry_count = 0
    file_count = 0
    total_bytes = 0
    for path in walk_eval_entries(root):
        entry_count += 1
        if entry_count > MAX_WORKSPACE_ENTRIES:
            raise ToolFailure(
                "workspace-entry-limit",
                f"Workspace exceeds {MAX_WORKSPACE_ENTRIES} entries.",
                root,
            )
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise ToolFailure("workspace-stat-failed", str(exc), path) from exc
        file_count += 1
        total_bytes += size
        if file_count > MAX_WORKSPACE_FILES:
            raise ToolFailure(
                "workspace-file-limit",
                f"Workspace exceeds {MAX_WORKSPACE_FILES} files.",
                root,
            )
        if total_bytes > MAX_WORKSPACE_BYTES:
            raise ToolFailure(
                "workspace-byte-limit",
                f"Workspace exceeds {MAX_WORKSPACE_BYTES} bytes.",
                root,
            )
    return entry_count, file_count, total_bytes


def stream_contains(path: Path, needle: str) -> bool:
    target = needle.encode("utf-8")
    if not target:
        return True
    overlap = max(len(target) - 1, 0)
    tail = b""
    with path.open("rb") as handle:
        while True:
            block = handle.read(64 * 1024)
            if not block:
                return False
            data = tail + block
            if target in data:
                return True
            tail = data[-overlap:] if overlap else b""


def evaluate_expectations(
    case: dict[str, object],
    returncode: int,
    stdout: str,
    stderr: str,
    stdout_path: Path,
    stderr_path: Path,
    workspace: Path,
    input_hashes: dict[str, str],
) -> tuple[list[str], list[str]]:
    expected = case.get("expected") if isinstance(case.get("expected"), dict) else {}
    problems: list[str] = []
    allowed_codes = expected.get("exit_codes", [0])
    if returncode not in allowed_codes:
        problems.append(f"exit code {returncode} not in {allowed_codes}")
    for needle in expected.get("stdout_contains", []):
        if not stream_contains(stdout_path, str(needle)):
            problems.append(f"stdout missing {needle!r}")
    for needle in expected.get("stderr_contains", []):
        if not stream_contains(stderr_path, str(needle)):
            problems.append(f"stderr missing {needle!r}")

    for relative in expected.get("files_exist", []):
        try:
            candidate = safe_workspace_path(workspace, relative)
            if not candidate.is_file():
                problems.append(f"required file missing: {relative}")
        except ToolFailure as exc:
            problems.append(f"unsafe required-file expectation {relative!r}: {exc}")
    for relative in expected.get("files_absent", []):
        try:
            candidate = safe_workspace_path(workspace, relative)
            if entry_exists(candidate):
                problems.append(f"forbidden file present: {relative}")
        except ToolFailure as exc:
            problems.append(f"unsafe forbidden-file expectation {relative!r}: {exc}")

    after_hashes = current_file_hashes(workspace)
    changes = changed_paths(input_hashes, after_hashes)
    for relative in expected.get("files_unchanged", []):
        text = Path(str(relative)).as_posix()
        if text not in input_hashes:
            problems.append(f"unchanged-file assertion has no input file: {relative}")
        elif after_hashes.get(text) != input_hashes[text]:
            problems.append(f"input file changed: {relative}")
    allowed_changes = expected.get("changed_files_only")
    if isinstance(allowed_changes, list):
        allowed_set = {Path(str(item)).as_posix() for item in allowed_changes}
        unexpected = sorted(set(changes) - allowed_set)
        if unexpected:
            problems.append(f"changes outside allowed paths: {', '.join(unexpected)}")
    maximum = expected.get("max_changed_input_files")
    if isinstance(maximum, int):
        changed_inputs = [path for path in changes if path in input_hashes]
        if len(changed_inputs) > maximum:
            problems.append(
                f"{len(changed_inputs)} input files changed; maximum is {maximum}"
            )

    for field, should_contain in (
        ("file_contains", True),
        ("file_not_contains", False),
    ):
        checks = expected.get(field, {})
        if not isinstance(checks, dict):
            continue
        for relative, needles in checks.items():
            try:
                candidate = safe_workspace_path(workspace, relative)
                if candidate.stat().st_size > MAX_INSPECT_TEXT_BYTES:
                    raise ToolFailure(
                        "inspection-file-limit",
                        f"Text expectation file exceeds {MAX_INSPECT_TEXT_BYTES} bytes.",
                        candidate,
                    )
                text = candidate.read_text(encoding="utf-8")
            except (ToolFailure, OSError, UnicodeError) as exc:
                problems.append(f"cannot inspect {relative}: {exc}")
                continue
            for needle in needles:
                found = str(needle) in text
                if found != should_contain:
                    relation = "missing" if should_contain else "contains forbidden"
                    problems.append(f"{relative} {relation} text {needle!r}")
    return problems, changes


def read_capture(path: Path) -> tuple[str, bool, int, str]:
    size = path.stat().st_size
    digest = digest_file(path)
    with path.open("rb") as handle:
        if size <= MAX_CAPTURE_CHARS:
            data = handle.read()
            truncated = False
        else:
            marker = (
                b"\n\n[... output truncated; full stream matched separately ...]\n\n"
            )
            retained = MAX_CAPTURE_CHARS - len(marker)
            head_size = retained // 2
            tail_size = retained - head_size
            head = handle.read(head_size)
            handle.seek(max(size - tail_size, 0))
            tail = handle.read(tail_size)
            data = head + marker + tail
            truncated = True
    return data.decode("utf-8", errors="replace"), truncated, size, digest


def redact_text(value: str, secrets: dict[str, str]) -> str:
    result = value
    for name, secret in sorted(
        secrets.items(),
        key=lambda item: len(item[1]),
        reverse=True,
    ):
        if secret:
            result = result.replace(secret, f"[REDACTED:{name}]")
    return result


def redact_json_value(
    value: object,
    secrets: dict[str, str],
) -> object:
    """Redact explicitly passed values from externally supplied JSON records."""
    if isinstance(value, str):
        return redact_text(value, secrets)
    if isinstance(value, list):
        return [redact_json_value(item, secrets) for item in value]
    if isinstance(value, dict):
        return {
            str(key): redact_json_value(item, secrets)
            for key, item in value.items()
        }
    return value


def secret_byte_patterns(secrets: dict[str, str]) -> tuple[bytes, ...]:
    patterns: set[bytes] = set()
    for secret in secrets.values():
        utf8 = secret.encode("utf-8")
        candidates = (
            utf8,
            secret.encode("utf-16-le"),
            secret.encode("utf-16-be"),
            base64.b64encode(utf8),
            base64.urlsafe_b64encode(utf8),
        )
        patterns.update(candidate for candidate in candidates if candidate)
    return tuple(sorted(patterns, key=len, reverse=True))


def sensitive_artifact_scan(
    root: Path,
    secrets: dict[str, str],
    *,
    maximum_findings: int = 100,
) -> dict[str, object]:
    """Scan a temporary run tree without persisting secret values or paths."""
    if not secrets:
        return {
            "performed": False,
            "complete": True,
            "detected": False,
            "finding_count": 0,
            "path_sha256": [],
            "findings_truncated": False,
        }
    patterns = secret_byte_patterns(secrets)
    path_hashes: list[str] = []
    finding_count = 0
    entries = 0
    inspected_bytes = 0
    for entry in walk_eval_entries(root):
        entries += 1
        if entries > MAX_SENSITIVE_SCAN_ENTRIES:
            raise ToolFailure(
                "sensitive-scan-entry-limit",
                "Sensitive-artifact scan exceeded its entry limit.",
                root,
            )
        relative = entry.relative_to(root).as_posix()
        encoded_path = relative.encode("utf-8", errors="surrogatepass")
        contaminated = any(pattern in encoded_path for pattern in patterns)
        if entry.is_file():
            try:
                size = entry.stat().st_size
            except OSError as exc:
                raise ToolFailure(
                    "sensitive-scan-stat-failed",
                    str(exc),
                    entry,
                ) from exc
            inspected_bytes += size
            if inspected_bytes > MAX_SENSITIVE_SCAN_BYTES:
                raise ToolFailure(
                    "sensitive-scan-byte-limit",
                    "Sensitive-artifact scan exceeded its byte limit.",
                    root,
                )
            if not contaminated:
                longest = max(len(pattern) for pattern in patterns)
                overlap = max(longest - 1, 0)
                tail = b""
                try:
                    with entry.open("rb") as handle:
                        while block := handle.read(1024 * 1024):
                            combined = tail + block
                            if any(
                                pattern in combined for pattern in patterns
                            ):
                                contaminated = True
                                break
                            tail = combined[-overlap:] if overlap else b""
                except OSError as exc:
                    raise ToolFailure(
                        "sensitive-scan-read-failed",
                        str(exc),
                        entry,
                    ) from exc
        if contaminated:
            finding_count += 1
            if len(path_hashes) < maximum_findings:
                path_hashes.append(
                    hashlib.sha256(encoded_path).hexdigest()
                )
    return {
        "performed": True,
        "complete": True,
        "detected": finding_count > 0,
        "finding_count": finding_count,
        "path_sha256": path_hashes,
        "findings_truncated": finding_count > maximum_findings,
    }


def cap_stored_text(value: str) -> tuple[str, bool]:
    if len(value) <= MAX_CAPTURE_CHARS:
        return value, False
    marker = "\n\n[... stored output truncated after redaction ...]\n\n"
    retained = MAX_CAPTURE_CHARS - len(marker)
    head_size = retained // 2
    tail_size = retained - head_size
    return value[:head_size] + marker + value[-tail_size:], True


def minimal_environment(run_root: Path, fake_home: Path) -> dict[str, str]:
    allowed = {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "OS",
        "PROCESSOR_ARCHITECTURE",
        "NUMBER_OF_PROCESSORS",
    }
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in allowed
    }
    temp_root = run_root / "tmp"
    appdata = fake_home / "AppData" / "Roaming"
    local_appdata = fake_home / "AppData" / "Local"
    xdg_config = fake_home / ".config"
    xdg_cache = fake_home / ".cache"
    xdg_data = fake_home / ".local" / "share"
    for path in (
        temp_root,
        appdata,
        local_appdata,
        xdg_config,
        xdg_cache,
        xdg_data,
    ):
        path.mkdir(parents=True)
    environment.update({
        "HOME": str(fake_home),
        "USERPROFILE": str(fake_home),
        "APPDATA": str(appdata),
        "LOCALAPPDATA": str(local_appdata),
        "TEMP": str(temp_root),
        "TMP": str(temp_root),
        "CODEX_HOME": str(fake_home / ".codex"),
        "CLAUDE_CONFIG_DIR": str(fake_home / ".claude"),
        "XDG_CONFIG_HOME": str(xdg_config),
        "XDG_CACHE_HOME": str(xdg_cache),
        "XDG_DATA_HOME": str(xdg_data),
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    return environment


def explicit_environment(names: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    reserved = {
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "TEMP",
        "TMP",
        "CODEX_HOME",
        "CLAUDE_CONFIG_DIR",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
        "DESIGN_DNA_EVAL_REQUEST",
        "DESIGN_DNA_EVAL_VARIANT",
        "DESIGN_DNA_EVAL_HOST",
        "DESIGN_DNA_SKILL_ENABLED",
        "DESIGN_DNA_SKILL_ROOT",
        "DESIGN_DNA_DRIVER_REPORT",
        # Reserved legacy name: never allow caller injection to masquerade as proof.
        "DESIGN_DNA_HOST_ATTESTATION",
    }
    for name in names:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ToolFailure(
                "invalid-pass-env",
                f"Invalid environment variable name: {name!r}",
            )
        canonical = name.upper()
        if canonical in reserved:
            raise ToolFailure(
                "reserved-pass-env",
                f"The runner controls environment variable {name!r}.",
            )
        if canonical in result:
            raise ToolFailure(
                "duplicate-pass-env",
                f"Environment variable requested more than once: {name!r}.",
            )
        match = next(
            (key for key in os.environ if key.upper() == canonical),
            None,
        )
        if match is None:
            raise ToolFailure(
                "missing-pass-env",
                f"Requested environment variable is not set: {name!r}.",
            )
        value = os.environ[match]
        if len(value) < MIN_PASSED_ENV_VALUE_LENGTH:
            raise ToolFailure(
                "unsafe-short-pass-env",
                (
                    f"Environment variable {name!r} is too short to pass "
                    "without unreliable artifact-leak detection."
                ),
            )
        result[canonical] = value
    return result


def driver_identity(executable: str, environment: dict[str, str]) -> dict[str, object]:
    resolved = shutil.which(executable, path=environment.get("PATH"))
    if resolved is None:
        raw = Path(executable)
        if raw.is_absolute() and raw.is_file():
            resolved = str(raw)
    if resolved is None:
        raise ToolFailure(
            "driver-not-found",
            f"Driver executable was not found: {executable!r}.",
        )
    path = absolute(Path(resolved))
    assert_no_reparse_path(path)
    if not path.is_file():
        raise ToolFailure("driver-not-file", "Driver must resolve to a file.", path)
    return {
        "requested": executable,
        "resolved": str(path),
        "sha256": digest_file(path),
    }


def terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        system_root = Path(
            os.environ.get("SystemRoot", r"C:\Windows")
        )
        taskkill = system_root / "System32" / "taskkill.exe"
        try:
            subprocess.run(
                [
                    str(taskkill),
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                ],
                capture_output=True,
                timeout=15,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run_driver(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout: int,
    stdout_path: Path,
    stderr_path: Path,
) -> tuple[int, bool, bool, float]:
    creationflags = 0
    popen_options: dict[str, object] = {}
    if os.name == "nt":
        creationflags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        popen_options["start_new_session"] = True
    start = time.monotonic()
    with stdout_path.open("wb") as stdout_handle, stderr_path.open(
        "wb"
    ) as stderr_handle:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdout=stdout_handle,
            stderr=stderr_handle,
            shell=False,
            creationflags=creationflags,
            **popen_options,
        )
        timed_out = False
        output_limit_exceeded = False
        deadline = start + timeout
        while True:
            try:
                output_bytes = stdout_path.stat().st_size + stderr_path.stat().st_size
            except OSError as exc:
                terminate_process_tree(process)
                raise ToolFailure(
                    "output-inspection-failed",
                    str(exc),
                    stdout_path.parent,
                ) from exc
            if output_bytes > MAX_OUTPUT_BYTES:
                output_limit_exceeded = True
                terminate_process_tree(process)
                returncode = -1
                break
            observed = process.poll()
            if observed is not None:
                returncode = observed
                break
            if time.monotonic() >= deadline:
                timed_out = True
                terminate_process_tree(process)
                returncode = -1
                break
            time.sleep(0.05)
    return (
        returncode,
        timed_out,
        output_limit_exceeded,
        round(time.monotonic() - start, 3),
    )


def atomic_result(path: Path, payload: dict[str, object]) -> None:
    if not path.parent.is_dir():
        raise ToolFailure(
            "results-directory-missing",
            "Create the results directory before running evaluations.",
            path.parent,
        )
    assert_no_reparse_path(path, stop=path.parent)
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


def host_route(
    fake_home: Path,
    host: str,
    installation_mode: str,
) -> Path:
    if installation_mode != "direct-skill":
        raise ToolFailure(
            "unsupported-eval-installation-mode",
            (
                "The evaluation runner can stage only direct-skill installs. "
                "It does not simulate a packaged plugin as a direct skill."
            ),
        )
    if host == "codex":
        return fake_home / ".agents" / "skills" / "design-dna"
    return fake_home / ".claude" / "skills" / "design-dna"


def install_exact_skill(
    skill_root: Path,
    fake_home: Path,
    host: str,
    installation_mode: str,
    expected_records: list[dict[str, object]],
) -> tuple[Path, str]:
    route = host_route(fake_home, host, installation_mode)
    route.parent.mkdir(parents=True)
    copy_tree(skill_root, route)
    installed_records, installed_hash = content_manifest(route)
    if installed_records != expected_records:
        raise ToolFailure(
            "eval-skill-parity-failed",
            "Fake-home skill differs from the selected canonical runtime.",
            route,
        )
    return route, installed_hash


def copy_snapshot(
    source: Path,
    destination: Path,
    expected_records: list[dict[str, object]],
    expected_hash: str,
) -> dict[str, str]:
    records, current_hash = eval_content_manifest(source)
    if records != expected_records or current_hash != expected_hash:
        raise ToolFailure(
            "input-snapshot-mutated",
            "The frozen case input changed during evaluation.",
            source,
        )
    copy_eval_tree(source, destination, destination_exists=True)
    copied_records, copied_hash = eval_content_manifest(destination)
    if copied_records != expected_records or copied_hash != expected_hash:
        raise ToolFailure(
            "input-copy-parity-failed",
            "Run input differs from the frozen case snapshot.",
            destination,
        )
    return {
        str(item["path"]): (
            str(item["sha256"])
            if item["type"] == "file"
            else "<directory>"
        )
        for item in copied_records
    }


def safe_monitor_after(
    roots: list[Path],
    before: dict[str, dict[str, str]],
    problems: list[str],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for root in roots:
        key = str(root)
        after: dict[str, str]
        snapshot_error: str | None = None
        try:
            after = monitor_snapshot(root)
        except ToolFailure as exc:
            after = {"<snapshot>": "failed"}
            snapshot_error = str(exc)
            problems.append(f"monitor snapshot failed for {root}: {exc}")
        differences, differences_truncated = snapshot_diff(before[key], after)
        changed = bool(differences) or snapshot_error is not None
        if changed and snapshot_error is None:
            problems.append(f"monitored external root changed during this run: {root}")
        record: dict[str, object] = {
            "root": key,
            "before_sha256": digest_mapping(before[key]),
            "after_sha256": digest_mapping(after),
            "changed": changed,
            "changed_entries": differences,
            "changed_entries_truncated": differences_truncated,
        }
        if snapshot_error is not None:
            record["error"] = snapshot_error
        records.append(record)
    return records


def validate_driver_report(
    path: Path,
    *,
    required: bool,
    host: str,
    case_id: str,
    variant: str,
    run_number: int,
    expected_skill_hash: str | None,
) -> tuple[str, dict[str, object] | None, list[str]]:
    if not entry_exists(path):
        if required:
            return "missing", None, ["required driver report is missing"]
        return "not_requested", None, []
    try:
        payload = load_json(path)
    except ToolFailure as exc:
        return "invalid", None, [f"driver report is invalid: {exc}"]
    if not isinstance(payload, dict):
        return "invalid", None, ["driver report must be a JSON object"]
    expected = {
        "schema_version": 1,
        "host": host,
        "case": case_id,
        "variant": variant,
        "run": run_number,
        "skill_loaded": variant == "skill",
        "skill_content_sha256": expected_skill_hash,
    }
    errors: list[str] = []
    allowed = set(expected) | {"driver_name", "driver_version", "evidence"}
    extras = sorted(set(payload) - allowed)
    if extras:
        errors.append(
            "driver report has unknown fields: " + ", ".join(extras)
        )
    for key, value in expected.items():
        if payload.get(key) != value:
            errors.append(
                f"driver report {key!r} does not match the expected value"
            )
    if not isinstance(payload.get("driver_name"), str) or not payload[
        "driver_name"
    ].strip():
        errors.append("driver report driver_name must be a nonempty string")
    if not isinstance(payload.get("driver_version"), str) or not payload[
        "driver_version"
    ].strip():
        errors.append("driver report driver_version must be a nonempty string")
    if "evidence" in payload and (
        not isinstance(payload["evidence"], str)
        or not payload["evidence"].strip()
    ):
        errors.append("driver report evidence must be a nonempty string")
    if errors:
        return "invalid", payload, errors
    return "driver_reported", payload, []


HOST_NATIVE_METHODS = {
    "host-adapter-event",
    "host-api-telemetry",
    "host-runtime-log",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_aware_datetime(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone missing")
    return parsed.astimezone(timezone.utc)


def serialized_json(payload: dict[str, object]) -> bytes:
    return (
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def write_new_bytes(path: Path, data: bytes) -> None:
    """Atomically publish a new file without intentionally replacing evidence."""
    if not path.parent.is_dir():
        raise ToolFailure(
            "evidence-parent-missing",
            "Evidence parent directory does not exist.",
            path.parent,
        )
    assert_no_reparse_path(path, stop=path.parent)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".staging",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, path)
        except FileExistsError as exc:
            raise ToolFailure(
                "evidence-collision",
                "Refusing to replace existing evidence.",
                path,
            ) from exc
        except OSError as exc:
            raise ToolFailure(
                "evidence-publish-failed",
                "Could not atomically publish new evidence.",
                path,
            ) from exc
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def prepare_host_native_challenge(
    source_root: Path | None,
    results_dir: Path,
    session_key: str,
    *,
    session_nonce: str,
    issued_at: str,
    host: str,
    case_id: str,
    variant: str,
    run_number: int,
    run_id: str,
    expected_skill_hash: str | None,
) -> tuple[
    dict[str, object] | None,
    dict[str, object] | None,
    list[str],
]:
    """Publish an unpredictable per-run challenge for an independent adapter."""
    if source_root is None:
        return None, None, []
    try:
        if not NONCE_PATTERN.fullmatch(session_nonce):
            raise ToolFailure(
                "host-challenge-session-nonce-invalid",
                "Session nonce must be 256 bits encoded as lowercase hex.",
            )
        challenges = absolute(source_root / "challenges")
        responses = absolute(source_root / "responses")
        for directory in (challenges, responses):
            assert_contained(directory, source_root, parent_must_exist=False)
            directory.mkdir(exist_ok=True)
            assert_contained(directory, source_root)
            assert_no_reparse_path(directory, stop=source_root)

        run_nonce = ""
        challenge_id = ""
        source_challenge = challenges / "unallocated.json"
        source_response = responses / "unallocated.json"
        for _ in range(100):
            run_nonce = secrets.token_hex(32)
            challenge_id = hashlib.sha256(
                (
                    f"{session_nonce}\0{run_nonce}\0{run_id}"
                ).encode("utf-8")
            ).hexdigest()
            source_challenge = absolute(challenges / f"{challenge_id}.json")
            source_response = absolute(responses / f"{challenge_id}.json")
            if not entry_exists(source_challenge) and not entry_exists(
                source_response
            ):
                break
        else:
            raise ToolFailure(
                "host-challenge-name-exhausted",
                "Unable to reserve a unique host-evidence challenge.",
                source_root,
            )

        challenge_payload: dict[str, object] = {
            "schema_version": 2,
            "challenge_id": challenge_id,
            "session_nonce": session_nonce,
            "run_nonce": run_nonce,
            "issued_at": issued_at,
            "host": host,
            "case": case_id,
            "variant": variant,
            "run": run_number,
            "run_id": run_id,
            "skill_loaded": variant == "skill",
            "skill_content_sha256": expected_skill_hash,
        }
        challenge_bytes = serialized_json(challenge_payload)
        challenge_sha256 = hashlib.sha256(challenge_bytes).hexdigest()
        write_new_bytes(source_challenge, challenge_bytes)

        relative = (
            Path("host-evidence")
            / session_key
            / f"{challenge_id}.challenge.json"
        )
        destination = absolute(results_dir / relative)
        assert_contained(destination, results_dir, parent_must_exist=False)
        destination.parent.mkdir(parents=True, exist_ok=True)
        assert_contained(destination, results_dir)
        assert_no_reparse_path(destination.parent, stop=results_dir)
        write_new_bytes(destination, challenge_bytes)
        challenge_record: dict[str, object] = {
            "path": relative.as_posix(),
            "sha256": challenge_sha256,
            "challenge_id": challenge_id,
            "session_nonce": session_nonce,
            "run_nonce": run_nonce,
            "issued_at": issued_at,
        }
        return {
            "source_challenge": source_challenge,
            "source_response": source_response,
            "challenge_payload": challenge_payload,
            "challenge_sha256": challenge_sha256,
            "challenge_record": challenge_record,
        }, challenge_record, []
    except (OSError, ToolFailure) as exc:
        return None, None, [
            f"host-native evidence challenge creation failed: {exc}"
        ]


def capture_host_native_evidence(
    challenge: dict[str, object] | None,
    results_dir: Path,
    session_key: str,
    *,
    required: bool,
    run_started_at: str,
    wait_seconds: float,
) -> tuple[str, dict[str, object] | None, list[str]]:
    """Capture a challenge-bound response produced during this exact run."""
    if challenge is None:
        if required:
            return "missing", None, [
                "required host-native adapter or telemetry evidence was not configured"
            ]
        return "not_requested", None, []

    source = challenge.get("source_response")
    source_challenge = challenge.get("source_challenge")
    challenge_payload = challenge.get("challenge_payload")
    challenge_sha256 = challenge.get("challenge_sha256")
    if (
        not isinstance(source, Path)
        or not isinstance(source_challenge, Path)
        or not isinstance(challenge_payload, dict)
        or not isinstance(challenge_sha256, str)
    ):
        return "invalid", None, [
            "host-native evidence challenge state is incomplete"
        ]
    challenge_id = str(challenge_payload.get("challenge_id", ""))
    deadline = time.monotonic() + (wait_seconds if required else 0.0)
    while not entry_exists(source) and time.monotonic() < deadline:
        time.sleep(0.05)
    try:
        assert_no_reparse_path(source)
    except ToolFailure as exc:
        return "invalid", None, [f"host-native evidence path is unsafe: {exc}"]
    if not source.is_file():
        message = (
            "host-native evidence is missing: expected challenge response "
            f"{challenge_id}.json"
        )
        return "missing", None, [message] if required else []
    try:
        if digest_file(source_challenge) != challenge_sha256:
            raise ToolFailure(
                "host-challenge-mutated",
                "Published host-evidence challenge changed before capture.",
                source_challenge,
            )
        before_hash = digest_file(source)
        payload = load_json(source)
        if digest_file(source) != before_hash:
            raise ToolFailure(
                "host-evidence-mutated",
                "Host-native evidence changed while it was being validated.",
                source,
            )
    except ToolFailure as exc:
        return "invalid", None, [f"host-native evidence is invalid: {exc}"]
    if not isinstance(payload, dict):
        return "invalid", None, ["host-native evidence must be a JSON object"]
    expected = {
        "schema_version": 2,
        "challenge_id": challenge_id,
        "challenge_sha256": challenge_sha256,
        "session_nonce": challenge_payload.get("session_nonce"),
        "run_nonce": challenge_payload.get("run_nonce"),
        "host": challenge_payload.get("host"),
        "case": challenge_payload.get("case"),
        "variant": challenge_payload.get("variant"),
        "run": challenge_payload.get("run"),
        "run_id": challenge_payload.get("run_id"),
        "skill_loaded": challenge_payload.get("skill_loaded"),
        "skill_content_sha256": challenge_payload.get(
            "skill_content_sha256"
        ),
    }
    allowed = set(expected) | {
        "method",
        "source_id",
        "source_version",
        "observed_at",
    }
    errors: list[str] = []
    extras = sorted(set(payload) - allowed)
    if extras:
        errors.append(
            "host-native evidence has unknown fields: " + ", ".join(extras)
        )
    for key, value in expected.items():
        if payload.get(key) != value:
            errors.append(
                f"host-native evidence {key!r} does not match the run"
            )
    method = payload.get("method")
    if method not in HOST_NATIVE_METHODS:
        errors.append(
            "host-native evidence method must identify adapter, API, or runtime telemetry"
        )
    for field in ("source_id", "source_version"):
        value = payload.get(field)
        if not isinstance(value, str) or len(value.strip()) < 3:
            errors.append(
                f"host-native evidence {field} must be an attributable identity"
            )
    observed_at = payload.get("observed_at")
    try:
        parsed_at = parse_aware_datetime(observed_at)
        run_started = parse_aware_datetime(run_started_at)
        now = utc_now()
        skew = HOST_EVIDENCE_CLOCK_SKEW_SECONDS
        if parsed_at.timestamp() < run_started.timestamp() - skew:
            errors.append(
                "host-native evidence observed_at predates this run"
            )
        if parsed_at.timestamp() > now.timestamp() + skew:
            errors.append(
                "host-native evidence observed_at is in the future"
            )
    except ValueError:
        errors.append("host-native evidence observed_at must be a timezone-aware date-time")
    if errors:
        return "invalid", None, errors

    relative = (
        Path("host-evidence")
        / session_key
        / f"{challenge_id}.response.json"
    )
    destination = absolute(results_dir / relative)
    try:
        assert_contained(destination, results_dir, parent_must_exist=False)
        destination.parent.mkdir(parents=True, exist_ok=True)
        assert_contained(destination, results_dir)
        assert_no_reparse_path(destination.parent, stop=results_dir)
        source_bytes = source.read_bytes()
        copied_hash = hashlib.sha256(source_bytes).hexdigest()
        after_hash = digest_file(source)
        if before_hash != copied_hash or before_hash != after_hash:
            raise ToolFailure(
                "host-evidence-parity-failed",
                "Host-native evidence changed while it was being captured.",
                source,
            )
        write_new_bytes(destination, source_bytes)
        if digest_file(destination) != before_hash:
            raise ToolFailure(
                "host-evidence-retained-hash-failed",
                "Retained host-native evidence differs from its source bytes.",
                destination,
            )
    except (OSError, ToolFailure) as exc:
        return "invalid", None, [f"host-native evidence capture failed: {exc}"]
    return "bound", {
        "path": relative.as_posix(),
        "sha256": before_hash,
        "challenge_id": challenge_id,
        "challenge_sha256": challenge_sha256,
        "session_nonce": challenge_payload["session_nonce"],
        "run_nonce": challenge_payload["run_nonce"],
        "method": method,
        "source_id": payload["source_id"],
        "source_version": payload["source_version"],
        "observed_at": observed_at,
        "captured_at": utc_now().isoformat(),
    }, []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--host", choices=("codex", "claude_code"), required=True)
    parser.add_argument(
        "--skill-root",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "skills" / "design-dna",
    )
    parser.add_argument(
        "--driver",
        required=True,
        help="Executable path or command name; no shell is used.",
    )
    parser.add_argument(
        "--driver-arg",
        action="append",
        default=[],
        help="Repeatable argument with documented placeholders.",
    )
    parser.add_argument("--baseline-driver")
    parser.add_argument("--baseline-arg", action="append", default=[])
    parser.add_argument("--skill-provider")
    parser.add_argument("--skill-model")
    parser.add_argument("--skill-model-version")
    parser.add_argument("--skill-reasoning-effort")
    parser.add_argument(
        "--skill-generation-config",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Record one approved non-secret generation setting; repeatable. "
            "This metadata does not alter the driver command."
        ),
    )
    parser.add_argument("--baseline-provider")
    parser.add_argument("--baseline-model")
    parser.add_argument("--baseline-model-version")
    parser.add_argument("--baseline-reasoning-effort")
    parser.add_argument(
        "--baseline-generation-config",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Record one baseline generation setting. When omitted, a declared "
            "skill model context is inherited for a controlled comparison."
        ),
    )
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--work-root", type=Path)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evals" / "results",
    )
    parser.add_argument("--monitor-root", action="append", type=Path, default=[])
    parser.add_argument(
        "--pass-env",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "Explicitly pass one environment variable to the trusted driver. "
            "Names are recorded and values are redacted from captured output."
        ),
    )
    parser.add_argument(
        "--require-driver-report",
        "--require-host-attestation",
        dest="require_driver_report",
        action="store_true",
        help=(
            "Require the driver to write its self-reported load record. This "
            "does not prove host-native loading."
        ),
    )
    parser.add_argument(
        "--host-native-evidence-dir",
        type=Path,
        help=(
            "Independent adapter mailbox. The runner publishes unpredictable "
            "per-run challenges below challenges/ and reads matching responses "
            "from responses/."
        ),
    )
    parser.add_argument(
        "--host-native-evidence-timeout",
        type=float,
        default=DEFAULT_HOST_EVIDENCE_WAIT_SECONDS,
        help=(
            "Seconds to wait for a required challenge response "
            f"(default: {DEFAULT_HOST_EVIDENCE_WAIT_SECONDS:g}, "
            f"maximum: {MAX_HOST_EVIDENCE_WAIT_SECONDS:g})."
        ),
    )
    parser.add_argument(
        "--require-host-native-evidence",
        action="store_true",
        help="Fail runs that lack separately produced host-native evidence.",
    )
    parser.add_argument("--keep-workspaces", action="store_true")
    args = parser.parse_args()

    work_root: Path | None = None
    session_root: Path | None = None
    created_work_root = False
    try:
        if args.runs < 1 or args.runs > 20:
            raise ToolFailure("invalid-run-count", "--runs must be from 1 through 20.")
        skill_model_context = model_context(
            provider=args.skill_provider,
            model=args.skill_model,
            model_version=args.skill_model_version,
            reasoning_effort=args.skill_reasoning_effort,
            generation_config=args.skill_generation_config,
            label="skill model context",
        )
        baseline_model_arguments = (
            args.baseline_provider,
            args.baseline_model,
            args.baseline_model_version,
            args.baseline_reasoning_effort,
            *args.baseline_generation_config,
        )
        if not args.baseline_driver and any(
            value is not None and value != ""
            for value in baseline_model_arguments
        ):
            raise ToolFailure(
                "baseline-model-without-driver",
                "Baseline model metadata requires --baseline-driver.",
            )
        baseline_model_context: dict[str, object] | None = None
        if args.baseline_driver:
            inherited = (
                skill_model_context
                if skill_model_context["declaration_status"] == "declared"
                else None
            )
            baseline_model_context = model_context(
                provider=args.baseline_provider,
                model=args.baseline_model,
                model_version=args.baseline_model_version,
                reasoning_effort=args.baseline_reasoning_effort,
                generation_config=args.baseline_generation_config,
                label="baseline model context",
                inherited=inherited,
            )
        if (
            args.host_native_evidence_timeout < 0
            or args.host_native_evidence_timeout
            > MAX_HOST_EVIDENCE_WAIT_SECONDS
        ):
            raise ToolFailure(
                "invalid-host-evidence-timeout",
                "--host-native-evidence-timeout must be from 0 through "
                f"{MAX_HOST_EVIDENCE_WAIT_SECONDS:g} seconds.",
            )
        fixture_path = absolute(args.fixture)
        fixture_root = fixture_path.parent
        assert_no_reparse_path(fixture_path, stop=fixture_root)
        suite = load_json(fixture_path)
        harness_path = Path(__file__).resolve()
        suite_schema_path = harness_path.parents[1] / "evals" / "schema.json"
        result_schema_path = (
            harness_path.parents[1] / "schemas" / "eval-result.schema.json"
        )
        schema = load_json(suite_schema_path)
        try:
            from jsonschema import Draft202012Validator, FormatChecker
        except ImportError as exc:
            raise ToolFailure(
                "dependency-missing",
                "Install maintainer/requirements-dev.lock with --require-hashes.",
                None,
            ) from exc
        schema_errors = list(
            Draft202012Validator(
                schema,
                format_checker=strict_format_checker(),
            ).iter_errors(suite)
        )
        if schema_errors:
            raise ToolFailure(
                "invalid-eval-suite",
                "; ".join(error.message for error in schema_errors),
                fixture_path,
            )
        assert isinstance(suite, dict)
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(suite["suite"])):
            raise ToolFailure(
                "invalid-suite-slug",
                "Suite must be a lowercase hyphenated slug.",
                fixture_path,
            )
        skill_instructions = suite["skill_instructions"]
        assert isinstance(skill_instructions, dict)
        resolved_skill_instruction = str(
            skill_instructions[args.host]
        ).strip()
        all_cases = suite["cases"]
        case_ids = [case["id"] for case in all_cases]
        if len(case_ids) != len(set(case_ids)):
            raise ToolFailure(
                "duplicate-eval-case",
                "Case IDs must be unique within a suite.",
                fixture_path,
            )
        cases = [
            case
            for case in all_cases
            if not args.case or case["id"] in args.case
        ]
        missing_cases = set(args.case) - {case["id"] for case in cases}
        if missing_cases:
            raise ToolFailure(
                "unknown-eval-case",
                ", ".join(sorted(missing_cases)),
                fixture_path,
            )
        unsupported_installation_cases = [
            str(case["id"])
            for case in cases
            if str(case.get("installation_mode", "direct-skill"))
            != "direct-skill"
        ]
        if unsupported_installation_cases:
            raise ToolFailure(
                "unsupported-eval-installation-mode",
                (
                    "The current runner stages only direct-skill routes. "
                    "Claude Code direct-skill runs use "
                    "<fake-home>/.claude/skills/design-dna with /design-dna. "
                    "It cannot produce packaged-plugin evidence for a "
                    ".claude/plugins/cache installation invoked as "
                    "/design-dna:design-dna. Unsupported cases: "
                    + ", ".join(unsupported_installation_cases)
                ),
                fixture_path,
            )

        skill_root = absolute(args.skill_root)
        skill_records, skill_hash = content_manifest(skill_root)
        release = load_json(skill_root / "release.json")
        if (
            not isinstance(release, dict)
            or not isinstance(release.get("version"), str)
            or not SEMVER_PATTERN.fullmatch(release["version"])
        ):
            raise ToolFailure(
                "invalid-skill-release",
                "Skill release metadata is invalid.",
                skill_root / "release.json",
            )
        package = {
            "name": "design-dna",
            "version": release["version"],
            "content_sha256": skill_hash,
            "skill_root": str(skill_root),
        }
        package_root = skill_root.parents[1]
        passed_environment = explicit_environment(args.pass_env)

        if args.work_root:
            work_root = absolute(args.work_root)
            if not work_root.exists():
                if not work_root.parent.is_dir():
                    raise ToolFailure(
                        "work-root-parent-missing",
                        "The work-root parent must already exist.",
                        work_root.parent,
                    )
                work_root.mkdir()
            assert_no_reparse_path(work_root)
        else:
            work_root = Path(tempfile.mkdtemp(prefix="design-dna-evals-"))
            created_work_root = True
        if not work_root.is_dir():
            raise ToolFailure(
                "invalid-work-root",
                "Work root must be a directory.",
                work_root,
            )
        if (
            is_within(work_root, package_root)
            or is_within(package_root, work_root)
        ):
            raise ToolFailure(
                "work-root-overlaps-package",
                "Evaluation work must stay outside the selected package.",
                work_root,
            )

        results_dir = absolute(args.results_dir)
        if not results_dir.is_dir():
            raise ToolFailure(
                "results-directory-missing",
                "Results directory does not exist.",
                results_dir,
            )
        assert_no_reparse_path(results_dir)
        if is_within(results_dir, skill_root) or is_within(skill_root, results_dir):
            raise ToolFailure(
                "results-overlap-runtime",
                "Evaluation results must stay outside the installed runtime skill.",
                results_dir,
            )
        if (
            is_within(results_dir, work_root)
            or is_within(work_root, results_dir)
        ):
            raise ToolFailure(
                "results-overlap-work-root",
                "Results and temporary work roots must be separate.",
                results_dir,
            )
        host_native_evidence_root: Path | None = None
        if args.host_native_evidence_dir is not None:
            host_native_evidence_root = absolute(args.host_native_evidence_dir)
            if not host_native_evidence_root.is_dir():
                raise ToolFailure(
                    "host-evidence-directory-missing",
                    "Host-native evidence directory does not exist.",
                    host_native_evidence_root,
                )
            assert_no_reparse_path(host_native_evidence_root)
            for protected in (work_root, results_dir, skill_root):
                if (
                    is_within(host_native_evidence_root, protected)
                    or is_within(protected, host_native_evidence_root)
                ):
                    raise ToolFailure(
                        "host-evidence-directory-overlap",
                        (
                            "Host-native evidence must come from a separate "
                            "adapter or telemetry directory."
                        ),
                        host_native_evidence_root,
                    )
        elif args.require_host_native_evidence:
            raise ToolFailure(
                "host-evidence-directory-required",
                "--require-host-native-evidence needs --host-native-evidence-dir.",
            )
        monitor_roots = [absolute(path) for path in args.monitor_root]
        if len(monitor_roots) != len(set(monitor_roots)):
            raise ToolFailure(
                "duplicate-monitor-root",
                "Monitor roots must be unique.",
                None,
            )
        for index, monitor in enumerate(monitor_roots):
            if not monitor.is_dir():
                raise ToolFailure(
                    "monitor-root-missing",
                    "Monitor roots must already exist as directories.",
                    monitor,
                )
            assert_no_reparse_path(monitor)
            for protected in (work_root, results_dir):
                if (
                    is_within(monitor, protected)
                    or is_within(protected, monitor)
                ):
                    raise ToolFailure(
                        "monitor-root-overlap",
                        "Monitor roots must not contain runner work or result paths.",
                        monitor,
                    )
            for other in monitor_roots[index + 1:]:
                if is_within(monitor, other) or is_within(other, monitor):
                    raise ToolFailure(
                        "nested-monitor-roots",
                        "Monitor roots must not overlap each other.",
                        monitor,
                    )
            monitor_snapshot(monitor)
        session_root = Path(
            tempfile.mkdtemp(prefix="design-dna-session-", dir=work_root)
        )
        session_key = session_root.name
        session_nonce = secrets.token_hex(32)
        input_snapshot_root = session_root / "input-snapshots"
        input_snapshot_root.mkdir()
        input_snapshots: dict[str, dict[str, object]] = {}
        input_provenance: dict[str, dict[str, object]] = {}
        for case in cases:
            case_id = str(case["id"])
            case_snapshot = input_snapshot_root / case_id
            case_snapshot.mkdir()
            input_dir = case.get("input_dir")
            if input_dir:
                copy_inputs(
                    fixture_root / str(input_dir),
                    case_snapshot,
                    fixture_root,
                )
            snapshot_records, snapshot_hash = eval_content_manifest(
                case_snapshot
            )
            input_snapshots[case_id] = {
                "root": case_snapshot,
                "records": snapshot_records,
                "sha256": snapshot_hash,
            }
            input_provenance[case_id] = {
                "sha256": snapshot_hash,
                "entry_count": len(snapshot_records),
                "file_count": sum(
                    item["type"] == "file" for item in snapshot_records
                ),
                "bytes": sum(
                    int(item["size"])
                    for item in snapshot_records
                    if item["type"] == "file"
                ),
            }

        started = utc_now().isoformat()
        run_results: list[dict[str, object]] = []
        execution_order: list[str] = []
        drivers: list[tuple[str, str, list[str]]] = [
            ("skill", args.driver, args.driver_arg)
        ]
        if args.baseline_driver:
            drivers.append(("baseline", args.baseline_driver, args.baseline_arg))
        identity_environment = minimal_environment(
            session_root / "identity",
            session_root / "identity" / "home",
        )
        driver_provenance: dict[str, dict[str, object] | None] = {
            "skill": {
                **driver_identity(args.driver, identity_environment),
                "argument_template_sha256": digest_text(
                    json.dumps(args.driver_arg, separators=(",", ":"))
                ),
                "argument_count": len(args.driver_arg),
                "model_context": skill_model_context,
            },
            "baseline": None,
        }
        if args.baseline_driver:
            driver_provenance["baseline"] = {
                **driver_identity(args.baseline_driver, identity_environment),
                "argument_template_sha256": digest_text(
                    json.dumps(args.baseline_arg, separators=(",", ":"))
                ),
                "argument_count": len(args.baseline_arg),
                "model_context": baseline_model_context,
            }

        for case in cases:
            case_id = str(case["id"])
            task = str(case["task"]).strip()
            invocation_mode = str(case.get("invocation_mode", "explicit"))
            installation_mode = str(
                case.get("installation_mode", "direct-skill")
            )
            frozen = input_snapshots[case_id]
            for run_number in range(1, args.runs + 1):
                ordered_drivers = (
                    drivers if run_number % 2 else list(reversed(drivers))
                )
                for variant, executable, driver_args in ordered_drivers:
                    run_id = (
                        f"{suite['suite']}:{args.host}:{case_id}:"
                        f"{variant}:{run_number}"
                    )
                    execution_order.append(run_id)
                    run_root = Path(
                        tempfile.mkdtemp(
                            prefix=f"{case_id}-{variant}-{run_number}-",
                            dir=session_root,
                        )
                    )
                    workspace = run_root / "workspace"
                    fake_home = run_root / "home"
                    workspace.mkdir()
                    fake_home.mkdir()
                    input_hashes = copy_snapshot(
                        frozen["root"],
                        workspace,
                        frozen["records"],
                        str(frozen["sha256"]),
                    )
                    staged_route: Path | None = None
                    staged_hash: str | None = None
                    skill_route_verified_before = True
                    if variant == "skill":
                        staged_route, staged_hash = install_exact_skill(
                            skill_root,
                            fake_home,
                            args.host,
                            installation_mode,
                            skill_records,
                        )
                    elif entry_exists(
                        host_route(
                            fake_home,
                            args.host,
                            installation_mode,
                        )
                    ):
                        raise ToolFailure(
                            "baseline-skill-present",
                            "Baseline fake home unexpectedly contains Design DNA.",
                            host_route(
                                fake_home,
                                args.host,
                                installation_mode,
                            ),
                        )

                    run_started_at = utc_now().isoformat()
                    host_evidence_required = (
                        args.require_host_native_evidence
                        or (
                            variant == "skill"
                            and invocation_mode == "implicit"
                        )
                    )
                    (
                        host_native_challenge_state,
                        host_native_challenge,
                        host_native_challenge_problems,
                    ) = prepare_host_native_challenge(
                        host_native_evidence_root,
                        results_dir,
                        session_key,
                        session_nonce=session_nonce,
                        issued_at=run_started_at,
                        host=args.host,
                        case_id=case_id,
                        variant=variant,
                        run_number=run_number,
                        run_id=run_id,
                        expected_skill_hash=staged_hash,
                    )
                    problems: list[str] = list(
                        host_native_challenge_problems
                    )
                    prompt = f"Task: {task}"
                    if variant == "skill" and invocation_mode == "explicit":
                        prompt = (
                            f"{resolved_skill_instruction}\n\n{prompt}"
                        )
                    prompt_file = run_root / "prompt.txt"
                    prompt_file.write_text(prompt, encoding="utf-8", newline="\n")
                    driver_report_json = run_root / "driver-report.json"
                    request = {
                        "schema_version": 3,
                        "run_id": run_id,
                        "suite": suite["suite"],
                        "case": case_id,
                        "variant": variant,
                        "host": args.host,
                        "run": run_number,
                        "invocation_mode": invocation_mode,
                        "installation_mode": installation_mode,
                        "prompt_file": str(prompt_file),
                        "workspace": str(workspace),
                        "home": str(fake_home),
                        "skill_root": str(staged_route) if staged_route else None,
                        "skill_content_sha256": staged_hash,
                        "driver_report_file": str(driver_report_json),
                    }
                    request_json = run_root / "request.json"
                    request_json.write_text(
                        json.dumps(request, indent=2),
                        encoding="utf-8",
                        newline="\n",
                    )
                    values = {
                        key: str(value)
                        for key, value in {
                            "workspace": workspace,
                            "home": fake_home,
                            "prompt_file": prompt_file,
                            "request_json": request_json,
                            "driver_report_json": driver_report_json,
                            "variant": variant,
                            "case_id": case_id,
                            "skill_root": staged_route or "",
                            "host": args.host,
                        }.items()
                    }
                    command = [executable, *render_args(driver_args, values)]
                    environment = minimal_environment(run_root, fake_home)
                    environment.update(passed_environment)
                    environment.update({
                        "DESIGN_DNA_EVAL_REQUEST": str(request_json),
                        "DESIGN_DNA_EVAL_VARIANT": variant,
                        "DESIGN_DNA_EVAL_HOST": args.host,
                        "DESIGN_DNA_SKILL_ENABLED": "1" if variant == "skill" else "0",
                        "DESIGN_DNA_SKILL_ROOT": str(staged_route or ""),
                        "DESIGN_DNA_DRIVER_REPORT": str(driver_report_json),
                    })
                    run_monitor_before: dict[str, dict[str, str]] = {}
                    for monitor in monitor_roots:
                        try:
                            run_monitor_before[str(monitor)] = monitor_snapshot(
                                monitor
                            )
                        except ToolFailure as exc:
                            run_monitor_before[str(monitor)] = {
                                "<snapshot>": "failed"
                            }
                            problems.append(
                                f"monitor snapshot failed before run for {monitor}: {exc}"
                            )
                    stdout_path = run_root / "stdout.bin"
                    stderr_path = run_root / "stderr.bin"
                    (
                        returncode,
                        timed_out,
                        output_limit_exceeded,
                        duration,
                    ) = run_driver(
                        command,
                        cwd=workspace,
                        environment=environment,
                        timeout=int(case.get("timeout_seconds", 300)),
                        stdout_path=stdout_path,
                        stderr_path=stderr_path,
                    )
                    (
                        stdout,
                        stdout_truncated,
                        stdout_bytes,
                        stdout_sha256,
                    ) = read_capture(stdout_path)
                    (
                        stderr,
                        stderr_truncated,
                        stderr_bytes,
                        stderr_sha256,
                    ) = read_capture(stderr_path)
                    stdout = redact_text(stdout, passed_environment)
                    stderr = redact_text(stderr, passed_environment)
                    stdout, redacted_stdout_truncated = cap_stored_text(stdout)
                    stderr, redacted_stderr_truncated = cap_stored_text(stderr)
                    stdout_truncated = (
                        stdout_truncated or redacted_stdout_truncated
                    )
                    stderr_truncated = (
                        stderr_truncated or redacted_stderr_truncated
                    )
                    if timed_out:
                        problems.append("driver timed out")
                    if output_limit_exceeded:
                        problems.append(
                            f"driver output exceeded {MAX_OUTPUT_BYTES} bytes"
                        )
                    changes: list[str] = []
                    if not timed_out and not output_limit_exceeded:
                        try:
                            expectation_problems, changes = evaluate_expectations(
                                case,
                                returncode,
                                stdout,
                                stderr,
                                stdout_path,
                                stderr_path,
                                workspace,
                                input_hashes,
                            )
                            problems.extend(expectation_problems)
                        except (ToolFailure, OSError, UnicodeError) as exc:
                            problems.append(
                                f"unsafe workspace prevented expectation checks: {exc}"
                            )

                    skill_route_verified_after = True
                    route = host_route(
                        fake_home,
                        args.host,
                        installation_mode,
                    )
                    try:
                        if variant == "skill":
                            route_records, route_hash = content_manifest(route)
                            if (
                                route_records != skill_records
                                or route_hash != skill_hash
                            ):
                                skill_route_verified_after = False
                                problems.append(
                                    "staged skill changed during driver execution"
                                )
                        elif entry_exists(route):
                            skill_route_verified_after = False
                            problems.append(
                                "baseline driver introduced a Design DNA skill route"
                            )
                    except ToolFailure as exc:
                        skill_route_verified_after = False
                        problems.append(
                            f"could not verify staged skill route after execution: {exc}"
                        )

                    try:
                        frozen_records, frozen_hash = eval_content_manifest(
                            frozen["root"]
                        )
                        if (
                            frozen_records != frozen["records"]
                            or frozen_hash != frozen["sha256"]
                        ):
                            problems.append(
                                "frozen input snapshot changed during driver execution"
                            )
                    except ToolFailure as exc:
                        problems.append(
                            f"could not verify frozen input snapshot: {exc}"
                        )

                    (
                        driver_report_status,
                        driver_report,
                        driver_report_problems,
                    ) = validate_driver_report(
                        driver_report_json,
                        required=args.require_driver_report,
                        host=args.host,
                        case_id=case_id,
                        variant=variant,
                        run_number=run_number,
                        expected_skill_hash=staged_hash,
                    )
                    problems.extend(driver_report_problems)
                    if driver_report is not None:
                        driver_report = redact_json_value(
                            driver_report,
                            passed_environment,
                        )
                    (
                        host_native_evidence_status,
                        host_native_evidence,
                        host_native_evidence_problems,
                    ) = capture_host_native_evidence(
                        host_native_challenge_state,
                        results_dir,
                        session_key,
                        required=host_evidence_required,
                        run_started_at=run_started_at,
                        wait_seconds=args.host_native_evidence_timeout,
                    )
                    problems.extend(host_native_evidence_problems)
                    if host_native_evidence is not None:
                        host_native_evidence = redact_json_value(
                            host_native_evidence,
                            passed_environment,
                        )
                    run_finished_at = utc_now().isoformat()
                    monitor_records = safe_monitor_after(
                        monitor_roots,
                        run_monitor_before,
                        problems,
                    )
                    workspace_file_count = 0
                    workspace_entry_count = 0
                    workspace_bytes = 0
                    retention_safe = True
                    try:
                        sensitive_scan = sensitive_artifact_scan(
                            run_root,
                            passed_environment,
                        )
                        if sensitive_scan["detected"]:
                            retention_safe = False
                            problems.append(
                                "passed environment value detected in "
                                "temporary run artifacts; promotion and "
                                "retention were refused"
                            )
                    except ToolFailure as exc:
                        retention_safe = False
                        sensitive_scan = {
                            "performed": bool(passed_environment),
                            "complete": False,
                            "detected": False,
                            "finding_count": 0,
                            "path_sha256": [],
                            "findings_truncated": False,
                        }
                        problems.append(
                            "sensitive-artifact scan could not complete; "
                            f"promotion and retention were refused: {exc}"
                        )
                    try:
                        (
                            workspace_entry_count,
                            workspace_file_count,
                            workspace_bytes,
                        ) = workspace_inventory(workspace)
                        files, workspace_hash = eval_content_manifest(
                            workspace
                        )
                    except ToolFailure as exc:
                        problems.append(
                            f"unsafe workspace artifact prevented manifesting: {exc}"
                        )
                        files, workspace_hash = [], None
                    artifact_bundle: dict[str, object] | None = None
                    if isinstance(workspace_hash, str) and retention_safe:
                        try:
                            artifact_bundle = promote_artifact_bundle(
                                workspace,
                                results_dir,
                                session_key,
                                run_id,
                                files,
                                workspace_hash,
                            )
                        except (ToolFailure, OSError) as exc:
                            problems.append(
                                f"artifact bundle promotion failed: {exc}"
                            )
                    result_record: dict[str, object] = {
                        "run_id": run_id,
                        "case": case_id,
                        "variant": variant,
                        "host": args.host,
                        "run": run_number,
                        "started_at": run_started_at,
                        "finished_at": run_finished_at,
                        "invocation_mode": invocation_mode,
                        "installation_mode": installation_mode,
                        "passed": not problems,
                        "problems": problems,
                        "returncode": returncode,
                        "timed_out": timed_out,
                        "output_limit_exceeded": output_limit_exceeded,
                        "duration_seconds": duration,
                        "stdout": stdout,
                        "stderr": stderr,
                        "stdout_sha256": stdout_sha256,
                        "stderr_sha256": stderr_sha256,
                        "stdout_bytes": stdout_bytes,
                        "stderr_bytes": stderr_bytes,
                        "stdout_truncated": stdout_truncated,
                        "stderr_truncated": stderr_truncated,
                        "task_sha256": digest_text(task),
                        "prompt_sha256": digest_text(prompt),
                        "input_snapshot_sha256": frozen["sha256"],
                        "review_requirements": case["review_requirements"],
                        "review_contract": case_review_contract(case),
                        "tags": case.get("tags", []),
                        "adversarial": bool(case.get("adversarial", False)),
                        "skill_staged": variant == "skill",
                        "skill_content_sha256": staged_hash,
                        "skill_route_verified_before": skill_route_verified_before,
                        "skill_route_verified_after": skill_route_verified_after,
                        "driver_report_status": driver_report_status,
                        "driver_report": driver_report,
                        "host_native_challenge": host_native_challenge,
                        "host_native_evidence_status": host_native_evidence_status,
                        "host_native_evidence": host_native_evidence,
                        "monitors": monitor_records,
                        "workspace_sha256": workspace_hash,
                        "workspace_entry_count": workspace_entry_count,
                        "workspace_file_count": workspace_file_count,
                        "workspace_bytes": workspace_bytes,
                        "files": files,
                        "changed_paths": changes,
                        "sensitive_artifact_scan": sensitive_scan,
                        "artifact_bundle": artifact_bundle,
                        "workspace": (
                            str(workspace)
                            if args.keep_workspaces and retention_safe
                            else None
                        ),
                    }
                    if not args.keep_workspaces or not retention_safe:
                        try:
                            assert_contained(run_root, session_root)
                            list(walk_eval_entries(run_root))
                            shutil.rmtree(run_root)
                        except (ToolFailure, OSError) as cleanup_error:
                            problems.append(
                                "run workspace cleanup failed; preserved at "
                                f"{run_root}: {cleanup_error}"
                            )
                            result_record["passed"] = False
                            result_record["workspace"] = str(workspace)
                    run_results.append(result_record)

        cleanup_problem: str | None = None
        if not args.keep_workspaces and session_root is not None:
            try:
                assert_contained(session_root, work_root)
                list(walk_eval_entries(session_root))
                shutil.rmtree(session_root)
                session_root = None
                if created_work_root:
                    work_root.rmdir()
                    work_root = None
            except (ToolFailure, OSError) as cleanup_error:
                cleanup_problem = (
                    "evaluation session cleanup failed; temporary data was preserved: "
                    f"{cleanup_error}"
                )
                for result in run_results:
                    result["problems"].append(cleanup_problem)
                    result["passed"] = False

        passed = sum(bool(result["passed"]) for result in run_results)
        by_variant: dict[str, dict[str, int]] = {}
        for variant in ("skill", "baseline"):
            selected = [
                result for result in run_results if result["variant"] == variant
            ]
            if selected:
                variant_passed = sum(bool(result["passed"]) for result in selected)
                by_variant[variant] = {
                    "total": len(selected),
                    "passed": variant_passed,
                    "failed": len(selected) - variant_passed,
                }
        finished = utc_now().isoformat()
        payload = {
            "schema_version": 3,
            "suite": suite["suite"],
            "session_nonce": session_nonce,
            "started_at": started,
            "finished_at": finished,
            "host": args.host,
            "package": package,
            "drivers": driver_provenance,
            "provenance": {
                "fixture_sha256": digest_file(fixture_path),
                "harness_sha256": digest_file(harness_path),
                "suite_schema_sha256": digest_file(suite_schema_path),
                "result_schema_sha256": digest_file(result_schema_path),
                "selected_cases": [str(case["id"]) for case in cases],
                "runs_per_case": args.runs,
                "input_snapshots": input_provenance,
                "monitor_roots": [str(path) for path in monitor_roots],
                "passed_environment_names": sorted(passed_environment),
                "driver_report_required": args.require_driver_report,
                "host_native_evidence_required": (
                    args.require_host_native_evidence
                ),
                "host_native_evidence_source_configured": (
                    host_native_evidence_root is not None
                ),
                "host_native_evidence_timeout_seconds": (
                    args.host_native_evidence_timeout
                ),
                "execution_order": execution_order,
                "workspace_limits": {
                    "max_entries": MAX_WORKSPACE_ENTRIES,
                    "max_files": MAX_WORKSPACE_FILES,
                    "max_bytes": MAX_WORKSPACE_BYTES,
                    "max_output_bytes": MAX_OUTPUT_BYTES,
                    "max_inspect_text_bytes": MAX_INSPECT_TEXT_BYTES,
                },
                "cleanup_problem": cleanup_problem,
                "retained_session": (
                    str(session_root)
                    if session_root is not None
                    else None
                ),
            },
            "prompt_contract": {
                "skill_instruction": resolved_skill_instruction,
                "baseline_instruction": None,
                "task_text_identical": True,
                "implicit_uses_natural_task_only": True,
                "invocation_modes": {
                    str(case["id"]): str(
                        case.get("invocation_mode", "explicit")
                    )
                    for case in cases
                },
                "installation_modes": {
                    str(case["id"]): str(
                        case.get("installation_mode", "direct-skill")
                    )
                    for case in cases
                },
            },
            "runs": run_results,
            "summary": {
                "total": len(run_results),
                "passed": passed,
                "failed": len(run_results) - passed,
                "by_variant": by_variant,
            },
        }
        result_name = (
            f"{suite['suite']}-{args.host}-"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')}.json"
        )
        result_path = results_dir / result_name
        assert_contained(result_path, results_dir)
        result_schema = load_json(result_schema_path)
        result_errors = sorted(
            Draft202012Validator(
                result_schema,
                format_checker=strict_format_checker(),
            ).iter_errors(payload),
            key=lambda error: list(error.absolute_path),
        )
        if result_errors:
            raise ToolFailure(
                "invalid-eval-result",
                "; ".join(
                    f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: "
                    f"{error.message}"
                    for error in result_errors
                ),
                result_schema_path,
            )
        atomic_result(result_path, payload)
        emit({
            "ok": passed == len(run_results),
            "result": str(result_path),
            "summary": payload["summary"],
        })
        return 0 if passed == len(run_results) else 1
    except (ToolFailure, OSError, json.JSONDecodeError, ValueError) as exc:
        issue = (
            exc.issue.as_dict()
            if isinstance(exc, ToolFailure)
            else {"code": "eval-failed", "message": str(exc)}
        )
        emit({"ok": False, "failures": [issue]})
        return 2
    finally:
        if (
            work_root is not None
            and not args.keep_workspaces
            and created_work_root
            and entry_exists(work_root)
        ):
            try:
                assert_no_reparse_path(work_root)
                list(walk_eval_entries(work_root))
                shutil.rmtree(work_root)
            except (ToolFailure, OSError):
                # A trusted-driver harness should never reach this path. Fail closed:
                # leave the exact temporary tree for manual recovery rather than
                # traversing an entry whose identity changed during execution.
                pass


if __name__ == "__main__":
    raise SystemExit(main())
