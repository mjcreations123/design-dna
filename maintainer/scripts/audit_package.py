#!/usr/bin/env python3
"""Run strict schema, content, link, evidence, fixture, and release checks."""

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
import binascii
import hashlib
import io
import json
import math
import os
import platform
import re
import struct
import sys
import zipfile
import zlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

BOOTSTRAP_FAILURES: list[str] = []
try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised without dev dependencies
    yaml = None  # type: ignore[assignment]
    BOOTSTRAP_FAILURES.append(f"PyYAML: {exc}")

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:  # pragma: no cover - exercised without dev dependencies
    Draft202012Validator = None  # type: ignore[assignment]
    FormatChecker = None  # type: ignore[assignment]
    BOOTSTRAP_FAILURES.append(f"jsonschema: {exc}")

from build_manifest import (
    EXECUTABLE_MAINTAINER_TREES,
    comparable,
    manifest_semantic_failures,
    package_manifest,
)
from check_links import check as check_links
from common import (
    ToolFailure,
    LOCAL_TOOL_DIRECTORY_NAMES,
    absolute,
    assert_no_reparse_path,
    compiled_python_residue_paths,
    content_manifest,
    eval_content_manifest,
    emit,
    is_within,
    load_json,
    strict_format_checker,
    walk_files,
)


TODO = re.compile(r"\[TODO(?::|\])|\bTODO:\s*", re.I)
UNSUPPORTED_PROMISE = re.compile(r"\b(?:guarantee(?:d|s)?\s+(?:not|never)|undetectable\s+as\s+AI|proves?\s+human[- ]made)\b", re.I)
UNSAFE_PORTABLE_PATH = re.compile(
    r"(?:^[/\\]|^[A-Za-z]:|\\|//|(?:^|/)\.{1,2}(?:/|$)|[\x00-\x1f\x7f])"
)
NON_RELEASE_EVIDENCE_ID = re.compile(
    r"(?:^|[._:-])(?:demo|example|fake|fixture|mock|sample|test)(?:$|[._:-])",
    re.I,
)
RELEASE_PROOF_MAX_AGE = timedelta(hours=24)
RELEASE_PROOF_CLOCK_SKEW = timedelta(minutes=5)
HOST_EVIDENCE_CLOCK_SKEW = timedelta(seconds=5)
REVIEW_EVIDENCE_CLOCK_SKEW = timedelta(minutes=5)
CI_IMPORT_ROOT = "maintainer/compatibility/archive/ci-runs"
CI_IMPORT_RECORD_NAME = "import.json"
CI_ARTIFACT_MAX_BYTES = 64 * 1024 * 1024
CI_EVIDENCE_MAX_BYTES = 16 * 1024 * 1024
CI_VERIFIABLE_CHECKS = frozenset({"package_audit", "unit_tests"})
LOCAL_UNIT_TEST_ATTESTATION = (
    "maintainer/attestations/test-attestation.json"
)
LOCAL_UNIT_TEST_SCHEMA = (
    "maintainer/schemas/test-attestation.schema.json"
)
LOCAL_RELEASE_MANIFEST = "maintainer/release-manifest.json"
HTTP_URL = re.compile(r"https?://[^\s\"'<>]+", re.I)
WINDOWS_ABSOLUTE_PATH = re.compile(r"(?i)(?:^|[^A-Za-z0-9])(?:[A-Z]:[\\/])")
UNC_ABSOLUTE_PATH = re.compile(r"(?:^|[\s\"'(=])\\\\[^\\\s]+\\")
EMBEDDED_POSIX_LOCAL_PATH = re.compile(
    r"(?:^|[\s\"'(=])/(?:Users|home|tmp|private|var/folders|workspace|workspaces|mnt|opt|usr)(?:/|$)"
)


def issue(code: str, path: str | Path, message: str) -> dict[str, str]:
    return {"code": code, "path": str(path), "message": message}


def distributed_record_local_path_failures(
    payload: object,
    label: str,
) -> list[dict[str, str]]:
    """Reject machine-local paths while leaving ordinary HTTP(S) URLs alone."""

    failures: list[dict[str, str]] = []

    def inspect(value: object, pointer: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                inspect(item, f"{pointer}/{key}")
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                inspect(item, f"{pointer}/{index}")
            return
        if not isinstance(value, str):
            return
        without_urls = HTTP_URL.sub("", value)
        local = (
            WINDOWS_ABSOLUTE_PATH.search(without_urls) is not None
            or UNC_ABSOLUTE_PATH.search(without_urls) is not None
            or without_urls.startswith("/")
            or EMBEDDED_POSIX_LOCAL_PATH.search(without_urls) is not None
        )
        if local:
            failures.append(issue(
                "release-attestation-local-path",
                label,
                (
                    "Distributed evidence contains a machine-local absolute "
                    f"path at {pointer or '<root>'}."
                ),
            ))

    inspect(payload, "")
    return failures


def compiled_python_residue_failures(
    root: Path,
    *,
    residue_code: str,
    inspection_code: str,
    message: str,
    label_root: Path | None = None,
) -> list[dict[str, str]]:
    """Report generated bytecode that content identities intentionally omit."""
    label_root = label_root or root

    def label(path: Path) -> str:
        try:
            return path.relative_to(label_root).as_posix()
        except ValueError:
            return str(path)

    try:
        residue = compiled_python_residue_paths(root)
    except ToolFailure as exc:
        return [issue(
            inspection_code,
            exc.issue.path or root,
            exc.issue.message,
        )]
    return [
        issue(residue_code, label(path), message)
        for path in residue
    ]


def runtime_cache_failures(
    skill: Path,
    *,
    label_root: Path | None = None,
) -> list[dict[str, str]]:
    """Find runtime residue that release manifests intentionally omit."""
    return compiled_python_residue_failures(
        skill,
        residue_code="runtime-cache-residue",
        inspection_code="runtime-cache-inspection-failed",
        message=(
            "Remove compiled Python residue from the runtime skill before "
            "audit or release."
        ),
        label_root=label_root,
    )


def maintainer_cache_failures(
    plugin: Path,
) -> list[dict[str, str]]:
    """Find unhashed bytecode in every executable maintainer tree."""
    failures: list[dict[str, str]] = []
    for relative in EXECUTABLE_MAINTAINER_TREES:
        failures.extend(compiled_python_residue_failures(
            plugin / relative,
            residue_code="maintainer-cache-residue",
            inspection_code="maintainer-cache-inspection-failed",
            message=(
                "Remove compiled Python residue from executable maintainer "
                "trees before audit or release."
            ),
            label_root=plugin,
        ))
    return failures


def plugin_skill_surface_failures(plugin: Path) -> list[dict[str, str]]:
    """Require the distributable plugin to expose exactly one skill entry."""

    expected = ["skills/design-dna/SKILL.md"]
    try:
        discovered = sorted(
            path.relative_to(plugin).as_posix()
            for path in walk_files(plugin / "skills")
            if path.name.casefold() == "skill.md"
        )
    except ToolFailure as exc:
        return [issue(
            "plugin-skill-surface-inspection-failed",
            exc.issue.path or plugin / "skills",
            exc.issue.message,
        )]
    if discovered == expected:
        return []
    return [issue(
        "plugin-skill-surface-invalid",
        "skills",
        (
            "The package must expose exactly one host-discoverable skill entry: "
            f"{expected}. Found: {discovered}."
        ),
    )]


def schema_validate(instance: object, schema_path: Path, label: str) -> list[dict[str, str]]:
    if Draft202012Validator is None or FormatChecker is None:
        return [issue(
            "dependency-missing",
            label,
            "Install maintainer/requirements-dev.lock with --require-hashes (jsonschema is required).",
        )]
    schema = load_json(schema_path)
    errors = Draft202012Validator(
        schema,
        format_checker=strict_format_checker(),
    ).iter_errors(instance)
    return [
        {"code": "schema-invalid", "path": label, "message": f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"}
        for error in sorted(
            errors,
            key=lambda item: tuple(str(part) for part in item.path),
        )
    ]


def aware_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def import_local_script(name: str):
    scripts = str(Path(__file__).resolve().parent)
    added = scripts not in sys.path
    if added:
        sys.path.insert(0, scripts)
    try:
        return __import__(name)
    finally:
        if added:
            sys.path.remove(scripts)


def test_attestation_failures(
    payload: object,
    plugin: Path,
    schema_path: Path,
    release_manifest: object,
    *,
    label: str = "maintainer/attestations/test-attestation.json",
    expected_python: str | None = None,
    require_zero_skips: bool = False,
) -> list[dict[str, str]]:
    failures = schema_validate(payload, schema_path, label)
    failures.extend(distributed_record_local_path_failures(payload, label))
    if not isinstance(payload, dict):
        return failures
    try:
        attestation_tool = import_local_script("attest_tests")
    except ImportError as exc:
        failures.append(issue(
            "release-test-attestation-tool-unavailable",
            label,
            str(exc),
        ))
        return failures

    current_inputs: dict[str, str] | None = None
    try:
        current_inputs = attestation_tool.attested_input_hashes(plugin)
        if payload.get("inputs") != current_inputs:
            failures.append(issue(
                "release-test-attestation-input-drift",
                label,
                "Tests, tooling, schemas, or requirements differ from the attested inputs.",
            ))
    except ToolFailure as exc:
        failures.append(issue(
            "release-test-attestation-input-unavailable",
            label,
            str(exc),
        ))

    try:
        current_dependencies = attestation_tool.pinned_dependencies(plugin)
        if payload.get("dependencies") != current_dependencies:
            failures.append(issue(
                "release-test-attestation-dependency-mismatch",
                label,
                "Pinned or installed dependency versions differ from the attestation.",
            ))
    except ToolFailure as exc:
        failures.append(issue(
            "release-test-attestation-dependency-mismatch",
            label,
            str(exc),
        ))

    python_record = payload.get("python")
    if expected_python is None:
        python_matches = isinstance(python_record, dict) and (
            python_record.get("implementation")
            == platform.python_implementation()
            and python_record.get("version") == platform.python_version()
            and python_record.get("executable")
            == attestation_tool.PYTHON_EXECUTABLE_TOKEN
            and python_record.get("executable_sha256")
            == attestation_tool.current_python_executable_sha256()
        )
    else:
        version = (
            python_record.get("version")
            if isinstance(python_record, dict)
            else None
        )
        executable_sha256 = (
            python_record.get("executable_sha256")
            if isinstance(python_record, dict)
            else None
        )
        python_matches = (
            re.fullmatch(r"[0-9]+\.[0-9]+", expected_python) is not None
            and isinstance(python_record, dict)
            and python_record.get("implementation") == "CPython"
            and isinstance(version, str)
            and re.fullmatch(
                re.escape(expected_python) + r"\.[0-9]+",
                version,
            )
            is not None
            and python_record.get("executable")
            == attestation_tool.PYTHON_EXECUTABLE_TOKEN
            and isinstance(executable_sha256, str)
            and re.fullmatch(r"[0-9a-f]{64}", executable_sha256) is not None
        )
    if not python_matches:
        failures.append(issue(
            "release-test-attestation-python-mismatch",
            label,
            (
                "The expected Python implementation, version, executable "
                "token, or executable-byte identity differs from the "
                "attestation."
            ),
        ))
    command = payload.get("command")
    if (
        not isinstance(command, list)
        or command
        != [
            attestation_tool.PYTHON_EXECUTABLE_TOKEN,
            *attestation_tool.UNITTEST_ARGUMENTS,
        ]
    ):
        failures.append(issue(
            "release-test-attestation-command-mismatch",
            label,
            "The attestation must identify the exact maintainer unittest command.",
        ))

    result = payload.get("result")
    tests_run = result.get("tests_run") if isinstance(result, dict) else None
    if not isinstance(result, dict) or (
        result.get("status") != "passed"
        or result.get("return_code") != 0
        or not isinstance(tests_run, int)
        or tests_run <= 0
        or result.get("failures") != 0
        or result.get("errors") != 0
        or result.get("unexpected_successes") != 0
    ):
        failures.append(issue(
            "release-test-attestation-failed",
            label,
            "The exact maintainer unittest suite is not recorded as passed.",
        ))
    if (
        require_zero_skips
        and isinstance(result, dict)
        and (
            result.get("skipped") != 0
            or result.get("skipped_test_ids") != []
            or payload.get("skip_waiver") is not None
        )
    ):
        failures.append(issue(
            "release-test-attestation-remote-skip",
            label,
            (
                "Imported CI matrix evidence must record zero skips; exact "
                "remote waiver applicability cannot be replayed locally."
            ),
        ))
    elif isinstance(result, dict) and current_inputs is not None:
        try:
            attestation_tool.verify_skip_waiver_record(
                plugin,
                payload.get("skip_waiver"),
                current_inputs,
                result,
            )
        except ToolFailure as exc:
            failures.append(issue(
                f"release-{exc.issue.code}",
                label,
                str(exc),
            ))

    output = payload.get("output")
    if isinstance(output, dict):
        stdout = output.get("stdout")
        stderr = output.get("stderr")
        if isinstance(stdout, str) and isinstance(stderr, str):
            digest = hashlib.sha256(
                ("stdout\0" + stdout + "\0stderr\0" + stderr).encode("utf-8")
            ).hexdigest()
            if (
                output.get("sha256") != digest
                or output.get("stdout_bytes") != len(stdout.encode("utf-8"))
                or output.get("stderr_bytes") != len(stderr.encode("utf-8"))
            ):
                failures.append(issue(
                    "release-test-attestation-output-drift",
                    label,
                    "Captured unittest output does not match its digest or byte counts.",
                ))

    try:
        started = aware_timestamp(payload.get("started_at"))
        completed = aware_timestamp(payload.get("completed_at"))
        if started > completed:
            raise ValueError("started_at follows completed_at")
        if completed > datetime.now(timezone.utc) + RELEASE_PROOF_CLOCK_SKEW:
            raise ValueError("completed_at is in the future")
        manifest_generated = (
            aware_timestamp(release_manifest.get("generated_at"))
            if isinstance(release_manifest, dict)
            else None
        )
        if manifest_generated is None:
            raise ValueError("current release manifest has no valid generated_at")
        if completed > manifest_generated + RELEASE_PROOF_CLOCK_SKEW:
            failures.append(issue(
                "release-test-attestation-after-manifest",
                label,
                "The test attestation was created after the manifest that must hash it.",
            ))
        elif manifest_generated - completed > RELEASE_PROOF_MAX_AGE:
            failures.append(issue(
                "release-test-attestation-stale",
                label,
                "The test attestation is more than 24 hours older than the release manifest.",
            ))
    except ValueError as exc:
        failures.append(issue(
            "release-test-attestation-time-invalid",
            label,
            str(exc),
        ))
    return failures


def codex_plugin_attestation_failures(
    payload: object,
    plugin: Path,
    schema_path: Path,
    release_manifest: object,
    release: object,
    *,
    validator_path: Path | None = None,
    label: str = "maintainer/attestations/codex-plugin-validation.json",
) -> list[dict[str, str]]:
    failures = schema_validate(payload, schema_path, label)
    failures.extend(distributed_record_local_path_failures(payload, label))
    if not isinstance(payload, dict):
        return failures
    try:
        tool = import_local_script("attest_codex_plugin")
        expected_inputs = tool.input_records(plugin)
        expected_dependencies = tool.dependency_records()
        expected_python_sha256 = tool.current_python_sha256()
        trust_policy, trust_policy_sha256 = tool.load_trust_policy(plugin)
    except Exception as exc:
        failures.append(issue(
            "release-codex-plugin-attestation-input-unavailable",
            label,
            str(exc),
        ))
        return failures
    if payload.get("inputs") != expected_inputs:
        failures.append(issue(
            "release-codex-plugin-attestation-input-drift",
            label,
            (
                "Codex plugin manifest, runtime skills, attestor, or schema "
                "differ from the static-validation evidence."
            ),
        ))
    if payload.get("dependencies") != expected_dependencies:
        failures.append(issue(
            "release-codex-plugin-attestation-dependency-drift",
            label,
            (
                "The validator dependency version or pure-Python source "
                "identity differs from the attestation."
            ),
        ))
    python_record = payload.get("python")
    if not isinstance(python_record, dict) or (
        python_record.get("implementation")
        != platform.python_implementation()
        or python_record.get("version") != platform.python_version()
        or python_record.get("executable") != tool.PYTHON_TOKEN
        or python_record.get("executable_sha256")
        != expected_python_sha256
    ):
        failures.append(issue(
            "release-codex-plugin-attestation-python-drift",
            label,
            (
                "Current Python implementation, version, token, or "
                "executable-byte identity differs from the attestation."
            ),
        ))
    if payload.get("command") != tool.ABSTRACT_COMMAND:
        failures.append(issue(
            "release-codex-plugin-attestation-command-drift",
            label,
            "The record does not identify the exact portable validator command.",
        ))
    validator_record = payload.get("validator")
    trust_input = (
        expected_inputs.get("files", {}).get("trust_policy")
        if isinstance(expected_inputs.get("files"), dict)
        else None
    )
    if (
        not isinstance(validator_record, dict)
        or validator_record.get("logical_id")
        != trust_policy.get("logical_id")
        or validator_record.get("sha256")
        != trust_policy.get("sha256")
        or validator_record.get("bytes") != trust_policy.get("bytes")
        or validator_record.get("trust_policy_sha256")
        != trust_policy_sha256
        or not isinstance(trust_input, dict)
        or trust_input.get("sha256") != trust_policy_sha256
    ):
        failures.append(issue(
            "release-codex-plugin-attestation-trust-drift",
            label,
            (
                "Validator identity and trust-policy hashes are not "
                "semantically consistent with the bound current policy."
            ),
        ))
    current_version = (
        release.get("version")
        if isinstance(release, dict)
        else None
    )
    if payload.get("release_version") != current_version:
        failures.append(issue(
            "release-codex-plugin-attestation-version-mismatch",
            label,
            f"{payload.get('release_version')} != {current_version}",
        ))
    result = payload.get("result")
    if (
        not isinstance(result, dict)
        or result.get("status") != "passed"
        or result.get("return_code") != 0
    ):
        failures.append(issue(
            "release-codex-plugin-attestation-not-passed",
            label,
            "The external Plugin Creator validator is not recorded as passed.",
        ))
    output = payload.get("output")
    if not isinstance(output, dict) or (
        output.get("success_marker_observed") is not True
        or output.get("exact_success_line_observed") is not True
        or output.get("stderr_empty") is not True
        or output.get("content_persisted") is not False
    ):
        failures.append(issue(
            "release-codex-plugin-attestation-output-invalid",
            label,
            (
                "Validator output evidence must record one exact success "
                "line, empty stderr, and no persisted output content."
            ),
        ))
    if validator_path is not None:
        try:
            fresh = tool.create_attestation(
                plugin,
                validator_path,
                created_at=payload.get("created_at"),
                require_current_trust=True,
            )
            if tool.comparable(payload) != tool.comparable(fresh):
                failures.append(issue(
                    "release-codex-plugin-attestation-live-drift",
                    label,
                    (
                        "Recorded validation differs from a fresh run of the "
                        "supplied external Plugin Creator validator."
                    ),
                ))
        except Exception as exc:
            failures.append(issue(
                "release-codex-plugin-attestation-live-check-failed",
                label,
                str(exc),
            ))
    try:
        created = aware_timestamp(payload.get("created_at"))
        try:
            tool.ensure_trust_policy_date(
                trust_policy,
                created.astimezone(timezone.utc).date(),
                require_current=True,
            )
        except ToolFailure as exc:
            failures.append(issue(
                f"release-{exc.issue.code}",
                label,
                str(exc),
            ))
        if created > datetime.now(timezone.utc) + RELEASE_PROOF_CLOCK_SKEW:
            raise ValueError("created_at is in the future")
        manifest_generated = (
            aware_timestamp(release_manifest.get("generated_at"))
            if isinstance(release_manifest, dict)
            else None
        )
        if manifest_generated is None:
            raise ValueError(
                "current release manifest has no valid generated_at"
            )
        if created > manifest_generated + RELEASE_PROOF_CLOCK_SKEW:
            failures.append(issue(
                "release-codex-plugin-attestation-after-manifest",
                label,
                (
                    "Plugin validation was created after the manifest that "
                    "must hash it."
                ),
            ))
        elif manifest_generated - created > RELEASE_PROOF_MAX_AGE:
            failures.append(issue(
                "release-codex-plugin-attestation-stale",
                label,
                "Plugin validation evidence is more than 24 hours old.",
            ))
    except ValueError as exc:
        failures.append(issue(
            "release-codex-plugin-attestation-time-invalid",
            label,
            str(exc),
        ))
    return failures


def install_lifecycle_attestation_failures(
    payload: object,
    plugin: Path,
    schema_path: Path,
    release_manifest: object,
    release: object,
    *,
    label: str = "maintainer/attestations/install-lifecycle.json",
) -> list[dict[str, str]]:
    failures = schema_validate(payload, schema_path, label)
    failures.extend(distributed_record_local_path_failures(payload, label))
    if not isinstance(payload, dict):
        return failures
    try:
        tool = import_local_script("attest_install_lifecycle")
        runtime = tool.manage_install.validate_design_dna_tree(
            plugin / "skills" / "design-dna"
        )
        expected_runtime = tool.identity_record(runtime)
        expected_files = tool.input_records(plugin)
    except Exception as exc:
        failures.append(issue(
            "release-install-lifecycle-input-unavailable",
            label,
            str(exc),
        ))
        return failures

    inputs = payload.get("inputs")
    if (
        not isinstance(inputs, dict)
        or inputs.get("runtime_source") != "skills/design-dna"
        or inputs.get("runtime") != expected_runtime
        or inputs.get("files") != expected_files
    ):
        failures.append(issue(
            "release-install-lifecycle-input-drift",
            label,
            (
                "Runtime, installer, attestor, or schema inputs differ from "
                "the isolated lifecycle evidence."
            ),
        ))
    current_version = (
        release.get("version")
        if isinstance(release, dict)
        else None
    )
    if payload.get("release_version") != current_version:
        failures.append(issue(
            "release-install-lifecycle-version-mismatch",
            label,
            f"{payload.get('release_version')} != {current_version}",
        ))
    outcome = payload.get("outcome")
    if not isinstance(outcome, dict) or any(
        outcome.get(field) is not True
        for field in (
            "passed",
            "operations_schema_valid",
            "backup_records_schema_valid",
            "runtime_identity_observed",
            "fresh_lifecycle_replay_required_on_check",
        )
    ):
        failures.append(issue(
            "release-install-lifecycle-not-passed",
            label,
            "The complete dual-host install, update, rollback, and uninstall lifecycle is not recorded as passed.",
        ))
    try:
        created = aware_timestamp(payload.get("created_at"))
        if created > datetime.now(timezone.utc) + RELEASE_PROOF_CLOCK_SKEW:
            raise ValueError("created_at is in the future")
        manifest_generated = (
            aware_timestamp(release_manifest.get("generated_at"))
            if isinstance(release_manifest, dict)
            else None
        )
        if manifest_generated is None:
            raise ValueError("current release manifest has no valid generated_at")
        if created > manifest_generated + RELEASE_PROOF_CLOCK_SKEW:
            failures.append(issue(
                "release-install-lifecycle-after-manifest",
                label,
                "Lifecycle evidence was created after the manifest that must hash it.",
            ))
        elif manifest_generated - created > RELEASE_PROOF_MAX_AGE:
            failures.append(issue(
                "release-install-lifecycle-stale",
                label,
                "Lifecycle evidence is more than 24 hours older than the release manifest.",
            ))
    except ValueError as exc:
        failures.append(issue(
            "release-install-lifecycle-time-invalid",
            label,
            str(exc),
        ))
    return failures


def expected_compatibility_routes(
    compatibility: object,
    home: Path | None = None,
) -> tuple[list[Path], list[Path]]:
    home = absolute(home or Path.home())

    def configured_path(value: str) -> Path:
        if value.startswith("~/"):
            return absolute(home.joinpath(*PurePosixPath(value[2:]).parts))
        return absolute(Path(value).expanduser())

    roots: set[Path] = set()
    expected: set[Path] = set()
    if isinstance(compatibility, dict):
        configured_roots = compatibility.get("discovery_roots")
        if isinstance(configured_roots, list):
            for root in configured_roots:
                if isinstance(root, str) and root.strip():
                    roots.add(configured_path(root))
        hosts = compatibility.get("hosts")
        if isinstance(hosts, dict):
            for host in hosts.values():
                if not isinstance(host, dict) or host.get("designed") is not True:
                    continue
                route = host.get("discovery_route")
                if isinstance(route, str) and route.strip():
                    expected.add(configured_path(route))
    return sorted(roots), sorted(expected)


def portable_home_identity(path: Path, home: Path) -> str | None:
    path = absolute(path)
    home = absolute(home)
    if not is_within(path, home) or path == home:
        return None
    return "~/" + path.relative_to(home).as_posix()


def route_verification_failures(
    payload: object,
    plugin: Path,
    schema_path: Path,
    release_manifest: object,
    compatibility: object,
    *,
    label: str = "maintainer/attestations/route-verification.json",
    home: Path | None = None,
) -> list[dict[str, str]]:
    failures = schema_validate(payload, schema_path, label)
    failures.extend(distributed_record_local_path_failures(payload, label))
    if not isinstance(payload, dict):
        return failures
    home = absolute(home or Path.home())
    canonical = absolute(plugin / "skills" / "design-dna")
    configured_roots, configured_expected = expected_compatibility_routes(
        compatibility,
        home,
    )
    if not configured_roots:
        failures.append(issue(
            "release-route-contract-invalid",
            label,
            "Compatibility must declare every discovery root.",
        ))
    for expected_route in configured_expected:
        if not any(
            is_within(expected_route, root)
            for root in configured_roots
        ):
            failures.append(issue(
                "release-route-contract-invalid",
                expected_route,
                "An expected route is outside the declared discovery roots.",
            ))
    root_labels = [
        portable_home_identity(path, home)
        for path in configured_roots
    ]
    expected_labels = [
        portable_home_identity(path, home)
        for path in configured_expected
    ]
    if any(value is None for value in [*root_labels, *expected_labels]):
        failures.append(issue(
            "release-route-contract-not-home-relative",
            label,
            "Compatibility discovery and installed routes must be below the selected home.",
        ))
    if payload.get("canonical") != "skills/design-dna":
        failures.append(issue(
            "release-route-canonical-mismatch",
            label,
            "Route verification does not identify the current canonical skill.",
        ))
    if payload.get("roots") != root_labels:
        failures.append(issue(
            "release-route-roots-mismatch",
            label,
            "Verified discovery roots differ from the compatibility contract.",
        ))
    if payload.get("expected") != expected_labels:
        failures.append(issue(
            "release-route-expected-mismatch",
            label,
            "Verified installed routes differ from the compatibility contract.",
        ))

    try:
        _canonical_records, canonical_hash = content_manifest(canonical)
    except ToolFailure as exc:
        failures.append(issue(
            "release-route-canonical-unavailable",
            label,
            str(exc),
        ))
        return failures
    if payload.get("canonical_sha256") != canonical_hash:
        failures.append(issue(
            "release-route-canonical-drift",
            label,
            "Canonical runtime content differs from the route verification.",
        ))

    try:
        route_tool = import_local_script("detect_routes")
    except ImportError as exc:
        failures.append(issue(
            "release-route-verifier-unavailable",
            label,
            str(exc),
        ))
        return failures

    found_all: list[Path] = []
    for root in configured_roots:
        try:
            assert_no_reparse_path(root)
        except ToolFailure as exc:
            failures.append(issue(
                "release-route-live-verification-failed",
                root,
                str(exc),
            ))
            continue
        if not root.exists():
            continue
        if not root.is_dir():
            failures.append(issue(
                "release-route-root-invalid",
                root,
                "A discovery root exists but is not a directory.",
            ))
            continue
        try:
            discovered, _warnings = route_tool.discover(root)
            found_all.extend(discovered)
        except ToolFailure as exc:
            failures.append(issue(
                "release-route-live-verification-failed",
                root,
                str(exc),
            ))
    found = sorted(set(found_all))
    missing = sorted(set(configured_expected) - set(found))
    unexpected = sorted(set(found) - set(configured_expected))
    for path in missing:
        failures.append(issue(
            "release-route-deleted",
            path,
            "An expected installed route is missing.",
        ))
    for path in unexpected:
        failures.append(issue(
            "release-duplicate-route-state",
            path,
            (
                "An unexpected Design DNA filesystem discovery candidate "
                "exists; activation is not inferred."
            ),
        ))
    if len(found_all) != len(found):
        failures.append(issue(
            "release-route-overlapping-roots",
            label,
            "The configured discovery roots report the same route more than once.",
        ))

    live_routes: list[dict[str, object]] = []
    for path in found:
        try:
            _records, digest = content_manifest(path)
        except ToolFailure as exc:
            failures.append(issue(
                "release-route-content-unavailable",
                path,
                str(exc),
            ))
            continue
        matches = digest == canonical_hash
        portable_path = portable_home_identity(path, home)
        if portable_path is None:
            failures.append(issue(
                "release-route-live-path-not-home-relative",
                path,
                "A live discoverable route is outside the selected home.",
            ))
            continue
        live_routes.append({
            "path": portable_path,
            "content_sha256": digest,
            "matches_canonical": matches,
        })
        if path in configured_expected and not matches:
            failures.append(issue(
                "release-installed-route-drift",
                path,
                f"{digest} != {canonical_hash}",
            ))
    if payload.get("routes") != live_routes:
        failures.append(issue(
            "release-route-record-drift",
            label,
            "Recorded route paths or hashes differ from the live discovery state.",
        ))

    try:
        verified = aware_timestamp(payload.get("verified_at"))
        if verified > datetime.now(timezone.utc) + RELEASE_PROOF_CLOCK_SKEW:
            raise ValueError("verified_at is in the future")
        manifest_generated = (
            aware_timestamp(release_manifest.get("generated_at"))
            if isinstance(release_manifest, dict)
            else None
        )
        if manifest_generated is None:
            raise ValueError("current release manifest has no valid generated_at")
        if verified > manifest_generated + RELEASE_PROOF_CLOCK_SKEW:
            failures.append(issue(
                "release-route-verification-after-manifest",
                label,
                "Route verification was created after the manifest that must hash it.",
            ))
        elif manifest_generated - verified > RELEASE_PROOF_MAX_AGE:
            failures.append(issue(
                "release-route-verification-stale",
                label,
                "Route verification is more than 24 hours older than the release manifest.",
            ))
    except ValueError as exc:
        failures.append(issue(
            "release-route-verification-time-invalid",
            label,
            str(exc),
        ))
    return failures


if yaml is not None:
    class NoDuplicateLoader(yaml.SafeLoader):
        pass


    def no_duplicate_mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in result:
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
        no_duplicate_mapping,
    )
else:
    NoDuplicateLoader = object  # type: ignore[assignment,misc]


def strict_yaml_text(text: str) -> object:
    if yaml is None:
        raise ToolFailure(
            "dependency-missing",
            "Install maintainer/requirements-dev.lock with --require-hashes (PyYAML is required).",
        )
    return yaml.load(text, Loader=NoDuplicateLoader)


def strict_yaml(path: Path) -> object:
    return strict_yaml_text(path.read_text(encoding="utf-8"))


def frontmatter(path: Path) -> tuple[object, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not match:
        raise ValueError("missing or unclosed frontmatter")
    return strict_yaml_text(match.group(1)), text[match.end():]


def runtime_reference_reachability_failures(
    skill: Path,
    *,
    label_root: Path | None = None,
) -> list[dict[str, str]]:
    """Require every runtime reference to be directly reachable from SKILL.md."""
    label_root = label_root or skill
    skill_path = skill / "SKILL.md"
    try:
        text = skill_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [issue(
            "runtime-reference-router-unreadable",
            skill_path,
            str(exc),
        )]
    linked = {
        PurePosixPath(match.group(1)).as_posix()
        for match in re.finditer(
            r"\]\((references/[^)#?\s]+\.md)(?:#[^)]*)?\)",
            text,
        )
    }
    failures: list[dict[str, str]] = []
    references_root = skill / "references"
    for path in sorted(references_root.rglob("*.md")):
        relative_to_skill = path.relative_to(skill).as_posix()
        if relative_to_skill in linked:
            continue
        try:
            label = path.relative_to(label_root).as_posix()
        except ValueError:
            label = str(path)
        failures.append(issue(
            "runtime-reference-unreachable",
            label,
            (
                "Every runtime reference must be linked directly from "
                "SKILL.md so progressive disclosure never depends on "
                "multi-hop reference discovery."
            ),
        ))
    return failures


def owner_policy_example_failures(
    example_path: Path,
    schema_path: Path,
    *,
    label: str = "skills/design-dna/templates/owner-policy.example.yml",
) -> list[dict[str, str]]:
    """Validate the draft example after safe in-memory activation."""
    try:
        payload = strict_yaml(example_path)
    except (OSError, UnicodeError, yaml.YAMLError, ToolFailure) as exc:
        return [issue("owner-policy-example-invalid", label, str(exc))]
    if not isinstance(payload, dict):
        return [issue(
            "owner-policy-example-invalid",
            label,
            "The owner-policy example must be a mapping.",
        )]
    failures: list[dict[str, str]] = []
    if payload.get("status") != "draft":
        failures.append(issue(
            "owner-policy-example-not-draft",
            label,
            "The distributed example must remain draft until an owner approves it.",
        ))
    for field in ("owner", "scope"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.startswith("REPLACE_"):
            failures.append(issue(
                "owner-policy-example-placeholder-missing",
                label,
                f"{field} must retain an explicit REPLACE_ placeholder.",
            ))
    activated = json.loads(json.dumps(payload))
    activated["owner"] = "example-validation-owner"
    activated["scope"] = "example-validation-scope"
    activated["status"] = "active"
    failures.extend(schema_validate(activated, schema_path, label))
    return failures


def validate_fixtures(fixtures_dir: Path, schema_path: Path) -> tuple[list[dict[str, str]], int]:
    failures: list[dict[str, str]] = []
    seen: dict[str, str] = {}
    seen_suites: dict[str, str] = {}
    expressive_case_ids: set[str] = set()
    quiet_case_ids: set[str] = set()
    generated_media_case_ids: set[str] = set()
    route_family_case_ids: set[str] = set()
    cultural_context_case_ids: set[str] = set()
    count = 0
    if not fixtures_dir.is_dir():
        return failures, count
    for path in sorted(fixtures_dir.glob("*.json")):
        try:
            suite = load_json(path)
        except ToolFailure as exc:
            failures.append(exc.issue.as_dict())
            continue
        failures.extend(schema_validate(suite, schema_path, str(path)))
        if not isinstance(suite, dict) or not isinstance(suite.get("cases"), list):
            continue
        suite_name = suite.get("suite")
        if isinstance(suite_name, str):
            if suite_name in seen_suites:
                failures.append(issue(
                    "duplicate-fixture-suite",
                    path,
                    f"{suite_name} also appears in {seen_suites[suite_name]}",
                ))
            seen_suites[suite_name] = str(path)
        for case in suite["cases"]:
            if not isinstance(case, dict) or not isinstance(case.get("id"), str):
                continue
            count += 1
            case_id = case["id"]
            if case_id in seen:
                failures.append({"code": "duplicate-fixture-id", "path": str(path), "message": f"{case_id} also appears in {seen[case_id]}"})
            seen[case_id] = str(path)
            coverage = case.get("release_coverage")
            if (
                isinstance(coverage, dict)
                and coverage.get("expressive_perception_gate") is True
            ):
                expressive_case_ids.add(case_id)
            if (
                isinstance(coverage, dict)
                and coverage.get("quiet_perception_gate") is True
            ):
                quiet_case_ids.add(case_id)
            if (
                isinstance(coverage, dict)
                and coverage.get("generated_media_capability_gate") is True
            ):
                generated_media_case_ids.add(case_id)
            if (
                isinstance(coverage, dict)
                and coverage.get("route_family_showcase_gate") is True
            ):
                route_family_case_ids.add(case_id)
            if (
                isinstance(coverage, dict)
                and coverage.get("cultural_context_gate") is True
            ):
                cultural_context_case_ids.add(case_id)
            capability = case.get("capability_contract")
            if isinstance(capability, dict):
                image_policy = capability.get("image_generation")
                requirements = " ".join(
                    str(value)
                    for value in case.get("review_requirements", [])
                ).casefold()
                if image_policy == "required-when-host-declared-available":
                    missing_terms = [
                        term
                        for term in (
                            "actual decodable local",
                            "provenance",
                            "contact sheet",
                            "responsive crop",
                            "unavailable",
                        )
                        if term not in requirements
                    ]
                    if missing_terms:
                        failures.append(issue(
                            "fixture-image-capability-review-incomplete",
                            path,
                            (
                                f"{case_id} must review both real generated "
                                "artifacts and the explicit unavailable branch; "
                                "missing: " + ", ".join(missing_terms)
                            ),
                        ))
            if (
                isinstance(coverage, dict)
                and coverage.get("generated_media_capability_gate") is True
                and not (
                    isinstance(capability, dict)
                    and capability.get("image_generation")
                    == "required-when-host-declared-available"
                )
            ):
                failures.append(issue(
                    "fixture-generated-media-capability-contract-missing",
                    path,
                    (
                        f"{case_id} is release-counted for generated media but "
                        "does not require the honest available/unavailable "
                        "image-generation capability contract."
                    ),
                ))
            input_dir = case.get("input_dir")
            if input_dir:
                candidate = absolute(path.parent / str(input_dir))
                try:
                    if not is_within(candidate, fixtures_dir):
                        raise ValueError
                    assert_no_reparse_path(candidate, stop=fixtures_dir)
                    if not candidate.is_dir():
                        failures.append({
                            "code": "fixture-input-missing",
                            "path": str(path),
                            "message": str(input_dir),
                        })
                except (ValueError, ToolFailure):
                    failures.append({"code": "fixture-input-escape", "path": str(path), "message": str(input_dir)})
    if len(expressive_case_ids) < MIN_EXPRESSIVE_RELEASE_CASES:
        failures.append(issue(
            "fixture-expressive-release-coverage-incomplete",
            fixtures_dir,
            (
                "The behavioral catalog needs at least "
                f"{MIN_EXPRESSIVE_RELEASE_CASES} distinct cases marked with "
                "release_coverage.expressive_perception_gate; found: "
                f"{len(expressive_case_ids)}."
            ),
        ))
    if len(quiet_case_ids) < MIN_QUIET_RELEASE_CASES:
        failures.append(issue(
            "fixture-quiet-release-coverage-incomplete",
            fixtures_dir,
            (
                "The behavioral catalog needs at least "
                f"{MIN_QUIET_RELEASE_CASES} distinct case marked with "
                "release_coverage.quiet_perception_gate; found: "
                f"{len(quiet_case_ids)}."
            ),
        ))
    if len(generated_media_case_ids) < MIN_GENERATED_MEDIA_RELEASE_CASES:
        failures.append(issue(
            "fixture-generated-media-release-coverage-incomplete",
            fixtures_dir,
            (
                "The behavioral catalog needs at least "
                f"{MIN_GENERATED_MEDIA_RELEASE_CASES} conditionally "
                "release-countable case marked with "
                "release_coverage.generated_media_capability_gate; found: "
                f"{len(generated_media_case_ids)}."
            ),
        ))
    if len(route_family_case_ids) < MIN_ROUTE_FAMILY_RELEASE_CASES:
        failures.append(issue(
            "fixture-route-family-release-coverage-incomplete",
            fixtures_dir,
            (
                "The behavioral catalog needs at least "
                f"{MIN_ROUTE_FAMILY_RELEASE_CASES} release-countable case "
                "marked with release_coverage.route_family_showcase_gate; "
                f"found: {len(route_family_case_ids)}."
            ),
        ))
    if len(cultural_context_case_ids) < MIN_CULTURAL_CONTEXT_RELEASE_CASES:
        failures.append(issue(
            "fixture-cultural-context-release-coverage-incomplete",
            fixtures_dir,
            (
                "The behavioral catalog needs at least "
                f"{MIN_CULTURAL_CONTEXT_RELEASE_CASES} release-countable case "
                "marked with release_coverage.cultural_context_gate; "
                f"found: {len(cultural_context_case_ids)}."
            ),
        ))
    return failures, count


def file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ToolFailure("file-read-failed", str(exc), path) from exc


def verify_png(path: Path) -> tuple[int, int]:
    """Validate a bounded, non-interlaced PNG and return decoded dimensions."""
    try:
        size = path.stat().st_size
        if size < 45 or size > 128 * 1024 * 1024:
            raise ToolFailure(
                "render-png-size-invalid",
                "Rendered PNG must be from 45 bytes through 128 MiB.",
                path,
            )
        data = path.read_bytes()
    except OSError as exc:
        raise ToolFailure("render-png-read-failed", str(exc), path) from exc
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ToolFailure(
            "render-png-signature-invalid",
            "Rendered evidence is not a PNG.",
            path,
        )
    offset = 8
    width = height = bit_depth = color_type = None
    interlace = None
    compressed = bytearray()
    seen_ihdr = False
    seen_idat = False
    seen_iend = False
    seen_plte = False
    idat_ended = False
    while offset < len(data):
        if offset + 12 > len(data):
            raise ToolFailure(
                "render-png-truncated",
                "PNG chunk header is truncated.",
                path,
            )
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            raise ToolFailure(
                "render-png-truncated",
                "PNG chunk data is truncated.",
                path,
            )
        chunk_data = data[offset + 8:offset + 8 + length]
        recorded_crc = struct.unpack(
            ">I",
            data[offset + 8 + length:chunk_end],
        )[0]
        actual_crc = binascii.crc32(chunk_type)
        actual_crc = binascii.crc32(chunk_data, actual_crc) & 0xFFFFFFFF
        if recorded_crc != actual_crc:
            raise ToolFailure(
                "render-png-crc-invalid",
                f"PNG chunk {chunk_type!r} has an invalid checksum.",
                path,
            )
        if chunk_type == b"IHDR":
            if seen_ihdr or offset != 8 or length != 13:
                raise ToolFailure(
                    "render-png-structure-invalid",
                    "PNG must begin with exactly one valid IHDR chunk.",
                    path,
                )
            (
                width,
                height,
                bit_depth,
                color_type,
                compression,
                filtering,
                interlace,
            ) = struct.unpack(">IIBBBBB", chunk_data)
            if (
                width < 1
                or height < 1
                or width > 32768
                or height > 131072
                or width * height > 64_000_000
                or compression != 0
                or filtering != 0
                or interlace != 0
            ):
                raise ToolFailure(
                    "render-png-header-invalid",
                    "PNG dimensions, compression, filtering, or interlace are unsupported.",
                    path,
                )
            valid_depths = {
                0: {1, 2, 4, 8, 16},
                2: {8, 16},
                3: {1, 2, 4, 8},
                4: {8, 16},
                6: {8, 16},
            }
            if color_type not in valid_depths or bit_depth not in valid_depths[color_type]:
                raise ToolFailure(
                    "render-png-header-invalid",
                    "PNG color type and bit depth are incompatible.",
                    path,
                )
            seen_ihdr = True
        elif chunk_type == b"PLTE":
            if not seen_ihdr or seen_idat or not 1 <= length <= 768 or length % 3:
                raise ToolFailure(
                    "render-png-structure-invalid",
                    "PNG palette placement or length is invalid.",
                    path,
                )
            seen_plte = True
        elif chunk_type == b"IDAT":
            if not seen_ihdr or seen_iend or idat_ended:
                raise ToolFailure(
                    "render-png-structure-invalid",
                    "PNG IDAT chunks are out of order.",
                    path,
                )
            seen_idat = True
            compressed.extend(chunk_data)
            if len(compressed) > 128 * 1024 * 1024:
                raise ToolFailure(
                    "render-png-compressed-limit",
                    "PNG compressed payload exceeds the audit limit.",
                    path,
                )
        elif chunk_type == b"IEND":
            if not seen_idat or seen_iend or length:
                raise ToolFailure(
                    "render-png-structure-invalid",
                    "PNG IEND is missing, duplicated, or malformed.",
                    path,
                )
            seen_iend = True
            offset = chunk_end
            break
        else:
            if seen_idat:
                idat_ended = True
            if chunk_type[:1].isupper():
                raise ToolFailure(
                    "render-png-critical-chunk-unknown",
                    f"Unsupported critical PNG chunk {chunk_type!r}.",
                    path,
                )
        offset = chunk_end
    if (
        not seen_ihdr
        or not seen_idat
        or not seen_iend
        or offset != len(data)
        or (color_type == 3 and not seen_plte)
    ):
        raise ToolFailure(
            "render-png-structure-invalid",
            "PNG is incomplete or has trailing data.",
            path,
        )
    assert (
        isinstance(width, int)
        and isinstance(height, int)
        and isinstance(bit_depth, int)
        and isinstance(color_type, int)
        and interlace == 0
    )
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    row_bytes = math.ceil(width * channels * bit_depth / 8)
    expected_bytes = height * (row_bytes + 1)
    if expected_bytes > 128 * 1024 * 1024:
        raise ToolFailure(
            "render-png-decoded-limit",
            "PNG decoded payload exceeds the audit limit.",
            path,
        )
    try:
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(bytes(compressed), expected_bytes + 1)
        decoded += decoder.flush(max(1, expected_bytes + 1 - len(decoded)))
    except zlib.error as exc:
        raise ToolFailure(
            "render-png-decode-failed",
            str(exc),
            path,
        ) from exc
    if (
        len(decoded) != expected_bytes
        or not decoder.eof
        or decoder.unused_data
        or decoder.unconsumed_tail
    ):
        raise ToolFailure(
            "render-png-decode-failed",
            "PNG pixel stream does not match its declared dimensions.",
            path,
        )
    for row in range(height):
        if decoded[row * (row_bytes + 1)] > 4:
            raise ToolFailure(
                "render-png-filter-invalid",
                f"PNG row {row} has an invalid filter.",
                path,
            )
    return width, height


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def case_review_contract(case: dict[str, object]) -> dict[str, object]:
    """Recompute the immutable review contract emitted by run_evals.py."""
    requirement_records: list[dict[str, str]] = []
    for index, raw in enumerate(case.get("review_requirements", []), start=1):
        text = str(raw)
        text_digest = text_sha256(text)
        requirement_records.append({
            "id": f"requirement-{index:02d}-{text_digest[:16]}",
            "text": text,
            "sha256": text_digest,
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


def portable_relative(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if (
        not value
        or value != value.strip()
        or value.endswith("/")
        or len(value) > 512
        or UNSAFE_PORTABLE_PATH.search(value)
    ):
        return None
    if PurePosixPath(value).as_posix() != value:
        return None
    return value


def validate_evidence_paths(
    values: object,
    plugin: Path,
    label: str,
    *,
    require_file: bool = True,
) -> tuple[list[dict[str, str]], set[str]]:
    failures: list[dict[str, str]] = []
    valid: set[str] = set()
    seen: dict[str, str] = {}
    if not isinstance(values, list):
        return failures, valid
    for index, raw in enumerate(values):
        relative = portable_relative(raw)
        if relative is None:
            failures.append(issue(
                "unsafe-evidence-path",
                label,
                f"Entry {index} is not a safe portable relative path: {raw!r}.",
            ))
            continue
        key = relative.casefold()
        if key in seen:
            failures.append(issue(
                "duplicate-evidence-path",
                label,
                f"{relative!r} conflicts with {seen[key]!r}.",
            ))
            continue
        seen[key] = relative
        candidate = absolute(plugin.joinpath(*relative.split("/")))
        try:
            if not is_within(candidate, plugin):
                raise ToolFailure("path-escape", "Evidence path leaves the package.", candidate)
            assert_no_reparse_path(candidate, stop=plugin)
            exists = candidate.is_file() if require_file else candidate.exists()
        except (OSError, ToolFailure) as exc:
            failures.append(issue(
                "unsafe-evidence-path",
                label,
                f"{relative}: {exc}",
            ))
            continue
        if not exists:
            failures.append(issue(
                "evidence-path-missing",
                label,
                relative,
            ))
            continue
        valid.add(key)
    return failures, valid


def stable_bounded_file_bytes(
    path: Path,
    *,
    maximum_bytes: int,
) -> bytes:
    """Read a regular file once and reject size or identity changes."""

    try:
        before = path.stat()
        if (
            not path.is_file()
            or before.st_size < 1
            or before.st_size > maximum_bytes
        ):
            raise ToolFailure(
                "ci-import-file-size-invalid",
                f"File must contain 1 through {maximum_bytes} bytes.",
                path,
            )
        data = path.read_bytes()
        after = path.stat()
    except ToolFailure:
        raise
    except OSError as exc:
        raise ToolFailure("ci-import-file-unreadable", str(exc), path) from exc
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) or len(data) != before.st_size:
        raise ToolFailure(
            "ci-import-file-unstable",
            "File changed while its retained identity was verified.",
            path,
        )
    return data


def expected_ci_test_matrix(
    workflow: object,
    *,
    job_name: str,
) -> set[tuple[str, str]] | None:
    if not isinstance(workflow, dict):
        return None
    jobs = workflow.get("jobs")
    job = jobs.get(job_name) if isinstance(jobs, dict) else None
    strategy = job.get("strategy") if isinstance(job, dict) else None
    matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
    operating_systems = matrix.get("os") if isinstance(matrix, dict) else None
    pythons = matrix.get("python") if isinstance(matrix, dict) else None
    if (
        not isinstance(job, dict)
        or job.get("name")
        != "${{ matrix.os }} / Python ${{ matrix.python }}"
        or not isinstance(operating_systems, list)
        or not operating_systems
        or not all(isinstance(value, str) for value in operating_systems)
        or len(set(operating_systems)) != len(operating_systems)
        or not isinstance(pythons, list)
        or not pythons
        or not all(isinstance(value, str) for value in pythons)
        or len(set(pythons)) != len(pythons)
        or set(matrix) != {"os", "python"}
    ):
        return None
    return {
        (operating_system, python)
        for operating_system in operating_systems
        for python in pythons
    }


def ci_import_record_failures(
    payload: object,
    environment: dict[str, object],
    plugin: Path,
    import_schema_path: Path,
    test_schema_path: Path,
    release_manifest: object,
    evidence_keys: set[str],
    *,
    label: str,
    workflow_path: str,
) -> list[dict[str, str]]:
    """Verify one retained CI artifact and its extracted proof bytes."""

    failures = schema_validate(payload, import_schema_path, label)
    failures.extend(distributed_record_local_path_failures(payload, label))
    if not isinstance(payload, dict):
        return failures

    identifier = environment.get("id")
    expected_root = f"{CI_IMPORT_ROOT}/{identifier}"
    checks = environment.get("checks")
    passed = {
        str(name)
        for name, status in checks.items()
        if status == "passed"
    } if isinstance(checks, dict) else set()
    claimed_raw = payload.get("passed_checks")
    claimed = (
        {str(value) for value in claimed_raw}
        if isinstance(claimed_raw, list)
        else set()
    )
    unsupported = sorted(passed - CI_VERIFIABLE_CHECKS)
    if unsupported:
        failures.append(issue(
            "ci-import-check-not-verifiable",
            label,
            (
                "This import contract cannot promote these checks: "
                + ", ".join(unsupported)
            ),
        ))
    if claimed != passed:
        failures.append(issue(
            "ci-import-check-claim-mismatch",
            label,
            (
                f"Import claims {sorted(claimed)!r}, but the compatibility "
                f"record marks {sorted(passed)!r} passed."
            ),
        ))

    source = payload.get("source")
    source_matrix = source.get("matrix") if isinstance(source, dict) else None
    expected_matrix = {
        "os": environment.get("os"),
        "python": environment.get("python"),
        "node": environment.get("node"),
    }
    if payload.get("environment_id") != identifier:
        failures.append(issue(
            "ci-import-environment-mismatch",
            label,
            f"{payload.get('environment_id')!r} != {identifier!r}.",
        ))
    if not isinstance(source, dict) or (
        source.get("workflow_path") != workflow_path
        or source_matrix != expected_matrix
        or source.get("job_name")
        != (
            f"{environment.get('os')} / Python "
            f"{environment.get('python')}"
        )
    ):
        failures.append(issue(
            "ci-import-source-mismatch",
            label,
            (
                "Workflow path, expanded job name, or OS/Python/Node matrix "
                "identity does not match."
            ),
        ))

    workflow_candidate = absolute(
        plugin.joinpath(*workflow_path.split("/"))
    )
    try:
        assert_no_reparse_path(workflow_candidate, stop=plugin)
        workflow_digest = file_sha256(workflow_candidate)
        if (
            not isinstance(source, dict)
            or source.get("workflow_sha256") != workflow_digest
        ):
            failures.append(issue(
                "ci-import-workflow-drift",
                label,
                "The imported run names different workflow bytes.",
            ))
    except ToolFailure as exc:
        failures.append(exc.issue.as_dict())

    try:
        imported = aware_timestamp(payload.get("imported_at"))
        checked = aware_timestamp(environment.get("checked_at"))
        source_started = aware_timestamp(
            source.get("started_at") if isinstance(source, dict) else None
        )
        source_completed = aware_timestamp(
            source.get("completed_at") if isinstance(source, dict) else None
        )
        if source_started > source_completed:
            raise ValueError("source.started_at follows source.completed_at")
        if source_completed > imported:
            raise ValueError("imported_at precedes the completed CI job")
        if imported != checked:
            raise ValueError(
                "environment.checked_at must equal the import timestamp"
            )
        if imported > datetime.now(timezone.utc) + RELEASE_PROOF_CLOCK_SKEW:
            raise ValueError("imported_at is in the future")
    except ValueError as exc:
        failures.append(issue(
            "ci-import-time-invalid",
            label,
            str(exc),
        ))
        source_started = None
        source_completed = None

    artifact = payload.get("artifact")
    evidence = payload.get("evidence")
    if not isinstance(artifact, dict) or not isinstance(evidence, dict):
        return failures
    artifact_relative = portable_relative(artifact.get("path"))
    evidence_records = {
        name: record
        for name, record in evidence.items()
        if isinstance(name, str) and isinstance(record, dict)
    }
    referenced = {
        value.casefold()
        for value in (
            artifact_relative,
            *(
                portable_relative(record.get("path"))
                for record in evidence_records.values()
            ),
        )
        if isinstance(value, str)
    }
    required_bindings = referenced | {workflow_path.casefold()}
    missing_references = sorted(required_bindings - evidence_keys)
    if missing_references:
        failures.append(issue(
            "ci-import-evidence-unbound",
            label,
            (
                "Compatibility evidence must cite the workflow, retained "
                "artifact, and every extracted proof: "
                + ", ".join(missing_references)
            ),
        ))

    all_relatives = [
        artifact_relative,
        *(
            portable_relative(record.get("path"))
            for record in evidence_records.values()
        ),
    ]
    if any(
        relative is None
        or not relative.startswith(expected_root + "/")
        for relative in all_relatives
    ):
        failures.append(issue(
            "ci-import-path-noncanonical",
            label,
            f"All retained files must be below {expected_root}/.",
        ))
        return failures
    assert artifact_relative is not None
    artifact_path = absolute(
        plugin.joinpath(*artifact_relative.split("/"))
    )
    try:
        assert_no_reparse_path(artifact_path, stop=plugin)
        artifact_bytes = stable_bounded_file_bytes(
            artifact_path,
            maximum_bytes=CI_ARTIFACT_MAX_BYTES,
        )
    except ToolFailure as exc:
        failures.append(exc.issue.as_dict())
        return failures
    artifact_digest = hashlib.sha256(artifact_bytes).hexdigest()
    if (
        artifact.get("size_bytes") != len(artifact_bytes)
        or artifact.get("sha256") != artifact_digest
        or artifact.get("service_digest") != f"sha256:{artifact_digest}"
    ):
        failures.append(issue(
            "ci-import-artifact-digest-mismatch",
            label,
            "Retained artifact bytes do not match its size and provider digest.",
        ))

    expected_artifact_name = (
        f"test-attestation-{environment.get('os')}-"
        f"py{environment.get('python')}"
    )
    if artifact.get("name") != expected_artifact_name:
        failures.append(issue(
            "ci-import-artifact-name-mismatch",
            label,
            f"{artifact.get('name')!r} != {expected_artifact_name!r}.",
        ))

    members = {
        str(record.get("archive_member")): (name, record)
        for name, record in evidence_records.items()
    }
    if len(members) != len(evidence_records) or any(
        portable_relative(member) != member
        for member in members
    ):
        failures.append(issue(
            "ci-import-artifact-member-invalid",
            label,
            "Artifact member names must be unique portable relative paths.",
        ))
        return failures
    evidence_bytes: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(artifact_bytes), "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if (
                len(names) != len(set(names))
                or set(names) != set(members)
            ):
                failures.append(issue(
                    "ci-import-artifact-members-mismatch",
                    label,
                    "Artifact members differ from the exact imported evidence set.",
                ))
                return failures
            for info in infos:
                check_name, record = members[info.filename]
                mode = (info.external_attr >> 16) & 0o170000
                if (
                    info.is_dir()
                    or info.flag_bits & 0x1
                    or mode == 0o120000
                    or info.file_size < 1
                    or info.file_size > CI_EVIDENCE_MAX_BYTES
                    or record.get("size_bytes") != info.file_size
                ):
                    failures.append(issue(
                        "ci-import-artifact-member-invalid",
                        label,
                        f"Unsafe or incorrectly sized member: {info.filename}.",
                    ))
                    continue
                member_bytes = archive.read(info)
                member_digest = hashlib.sha256(member_bytes).hexdigest()
                if record.get("sha256") != member_digest:
                    failures.append(issue(
                        "ci-import-evidence-digest-mismatch",
                        label,
                        f"Digest mismatch for {info.filename}.",
                    ))
                evidence_relative = portable_relative(record.get("path"))
                assert evidence_relative is not None
                evidence_path = absolute(
                    plugin.joinpath(*evidence_relative.split("/"))
                )
                assert_no_reparse_path(evidence_path, stop=plugin)
                retained_bytes = stable_bounded_file_bytes(
                    evidence_path,
                    maximum_bytes=CI_EVIDENCE_MAX_BYTES,
                )
                if retained_bytes != member_bytes:
                    failures.append(issue(
                        "ci-import-extracted-evidence-mismatch",
                        label,
                        (
                            f"{evidence_relative} is not byte-identical to "
                            f"artifact member {info.filename}."
                        ),
                    ))
                evidence_bytes[check_name] = retained_bytes
    except (
        OSError,
        RuntimeError,
        ValueError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as exc:
        failures.append(issue(
            "ci-import-artifact-invalid",
            label,
            str(exc),
        ))
        return failures
    except ToolFailure as exc:
        failures.append(exc.issue.as_dict())
        return failures

    for check_name in claimed:
        record = evidence_records.get(check_name)
        if record is None or check_name not in evidence_bytes:
            failures.append(issue(
                "ci-import-check-evidence-missing",
                label,
                f"No verified retained evidence exists for {check_name}.",
            ))
            continue
        relative = portable_relative(record.get("path"))
        assert relative is not None
        evidence_path = absolute(plugin.joinpath(*relative.split("/")))
        try:
            evidence_payload = load_json(evidence_path)
        except ToolFailure as exc:
            failures.append(exc.issue.as_dict())
            continue
        if check_name == "package_audit":
            failures.extend(distributed_record_local_path_failures(
                evidence_payload,
                relative,
            ))
            if not isinstance(evidence_payload, dict) or (
                evidence_payload.get("ok") is not True
                or evidence_payload.get("failures") != []
                or not isinstance(evidence_payload.get("warnings"), list)
                or not isinstance(evidence_payload.get("details"), dict)
            ):
                failures.append(issue(
                    "ci-import-package-audit-not-passed",
                    relative,
                    "Retained development package audit is not a clean pass.",
                ))
        elif check_name == "unit_tests":
            failures.extend(test_attestation_failures(
                evidence_payload,
                plugin,
                test_schema_path,
                release_manifest,
                label=relative,
                expected_python=str(environment.get("python")),
                require_zero_skips=True,
            ))
            if isinstance(evidence_payload, dict):
                try:
                    attested_started = aware_timestamp(
                        evidence_payload.get("started_at")
                    )
                    attested_completed = aware_timestamp(
                        evidence_payload.get("completed_at")
                    )
                    if (
                        source_started is None
                        or source_completed is None
                        or attested_started < source_started
                        or attested_completed > source_completed
                    ):
                        raise ValueError(
                            "test attestation falls outside the CI job window"
                        )
                except ValueError as exc:
                    failures.append(issue(
                        "ci-import-attestation-time-invalid",
                        relative,
                        str(exc),
                    ))
    return failures


def ci_contract_failures(
    compatibility: object,
    plugin: Path,
    import_schema_path: Path,
    test_schema_path: Path,
    release_manifest: object,
    *,
    release_mode: bool,
) -> tuple[list[dict[str, str]], dict[str, object]]:
    """Bind promoted CI checks and enforce the full release matrix."""

    failures: list[dict[str, str]] = []
    details: dict[str, object] = {
        "required_entries": 0,
        "status_passed_entries": 0,
        "passed_entries": 0,
        "verified_imports": 0,
    }
    verified_identifiers: set[str] = set()
    if not isinstance(compatibility, dict):
        return failures, details
    contract = compatibility.get("ci_release_contract")
    if not isinstance(contract, dict):
        return failures, details
    workflow_path = portable_relative(contract.get("workflow_path"))
    job_name = contract.get("test_job")
    required_raw = contract.get("required_checks")
    required_checks = (
        tuple(str(value) for value in required_raw)
        if isinstance(required_raw, list)
        else ()
    )
    if (
        workflow_path is None
        or not isinstance(job_name, str)
        or not required_checks
    ):
        return failures, details
    workflow_candidate = absolute(
        plugin.joinpath(*workflow_path.split("/"))
    )
    try:
        assert_no_reparse_path(workflow_candidate, stop=plugin)
        workflow = strict_yaml(workflow_candidate)
    except (OSError, UnicodeError, ToolFailure, ValueError) as exc:
        failures.append(issue(
            "ci-contract-workflow-invalid",
            workflow_path,
            str(exc),
        ))
        return failures, details
    expected_pairs = expected_ci_test_matrix(
        workflow,
        job_name=job_name,
    )
    if expected_pairs is None:
        failures.append(issue(
            "ci-contract-workflow-matrix-invalid",
            workflow_path,
            "The release test job needs a simple unique OS/Python matrix.",
        ))
        return failures, details

    environments = compatibility.get("environments")
    if not isinstance(environments, list):
        return failures, details
    python_records = [
        record
        for record in environments
        if isinstance(record, dict)
        and record.get("scope") == "ci_contract"
        and record.get("node") is None
        and isinstance(record.get("python"), str)
    ]
    records_by_pair: defaultdict[
        tuple[str, str],
        list[dict[str, object]],
    ] = defaultdict(list)
    for record in python_records:
        records_by_pair[
            (str(record.get("os")), str(record.get("python")))
        ].append(record)
    declared_pairs = set(records_by_pair)
    if declared_pairs != expected_pairs or any(
        len(records) != 1 for records in records_by_pair.values()
    ):
        failures.append(issue(
            "ci-contract-matrix-drift",
            "maintainer/compatibility/matrix.yml:environments",
            (
                "Compatibility CI entries must match the workflow OS/Python "
                "Cartesian matrix exactly once."
            ),
        ))
    details["required_entries"] = len(expected_pairs)

    for record in environments:
        if not isinstance(record, dict) or record.get("scope") != "ci_contract":
            continue
        identifier = str(record.get("id", ""))
        label = f"maintainer/compatibility/matrix.yml:{identifier}"
        checks = record.get("checks")
        passed = {
            str(name)
            for name, status in checks.items()
            if status == "passed"
        } if isinstance(checks, dict) else set()
        if not passed:
            continue
        evidence_failures, evidence_keys = validate_evidence_paths(
            record.get("evidence"),
            plugin,
            label,
        )
        failures.extend(evidence_failures)
        canonical_import = (
            f"{CI_IMPORT_ROOT}/{identifier}/{CI_IMPORT_RECORD_NAME}"
        )
        import_paths = [
            value
            for value in record.get("evidence", [])
            if isinstance(value, str)
            and value.casefold() == canonical_import.casefold()
        ] if isinstance(record.get("evidence"), list) else []
        if len(import_paths) != 1 or canonical_import.casefold() not in evidence_keys:
            failures.append(issue(
                "ci-import-record-missing",
                label,
                (
                    "A promoted CI pass needs exactly one canonical retained "
                    f"record at {canonical_import}."
                ),
            ))
            continue
        import_path = absolute(
            plugin.joinpath(*canonical_import.split("/"))
        )
        try:
            import_payload = load_json(import_path)
        except ToolFailure as exc:
            failures.append(exc.issue.as_dict())
            continue
        import_failures = ci_import_record_failures(
            import_payload,
            record,
            plugin,
            import_schema_path,
            test_schema_path,
            release_manifest,
            evidence_keys,
            label=canonical_import,
            workflow_path=workflow_path,
        )
        failures.extend(import_failures)
        if not import_failures:
            verified_identifiers.add(identifier)
            details["verified_imports"] = (
                int(details["verified_imports"]) + 1
            )

    for pair in sorted(expected_pairs):
        records = records_by_pair.get(pair, [])
        if len(records) != 1:
            if release_mode:
                failures.append(issue(
                    "release-ci-matrix-entry-missing",
                    "maintainer/compatibility/matrix.yml:environments",
                    f"No unique compatibility entry exists for {pair[0]} / Python {pair[1]}.",
                ))
            continue
        record = records[0]
        checks = record.get("checks")
        missing = [
            check
            for check in required_checks
            if not isinstance(checks, dict) or checks.get(check) != "passed"
        ]
        if not missing:
            details["status_passed_entries"] = (
                int(details["status_passed_entries"]) + 1
            )
            if str(record.get("id", "")) in verified_identifiers:
                details["passed_entries"] = (
                    int(details["passed_entries"]) + 1
                )
        elif release_mode:
            failures.append(issue(
                "release-ci-matrix-entry-unobserved",
                f"maintainer/compatibility/matrix.yml:{record.get('id')}",
                (
                    "Strict release requires retained, verified passes for "
                    + ", ".join(missing)
                    + "."
                ),
            ))
    return failures, details


def compatibility_environment_failures(
    compatibility: object,
    plugin: Path,
) -> list[dict[str, str]]:
    """Validate each environment claim instead of trusting host aggregates."""
    failures: list[dict[str, str]] = []
    if not isinstance(compatibility, dict):
        return failures
    discovery_roots = compatibility.get("discovery_roots")
    if isinstance(discovery_roots, list):
        for index, value in enumerate(discovery_roots):
            if isinstance(value, str) and not value.startswith("~/"):
                failures.append(issue(
                    "compatibility-route-not-portable",
                    (
                        "maintainer/compatibility/matrix.yml:"
                        f"discovery_roots[{index}]"
                    ),
                    (
                        "Distributed compatibility routes must use a ~/ "
                        "home-relative identity; absolute routes are accepted "
                        "only in isolated test fixtures."
                    ),
                ))
    hosts = compatibility.get("hosts")
    if isinstance(hosts, dict):
        for host_name, record in hosts.items():
            route = (
                record.get("discovery_route")
                if isinstance(record, dict)
                else None
            )
            if isinstance(route, str) and not route.startswith("~/"):
                failures.append(issue(
                    "compatibility-route-not-portable",
                    (
                        "maintainer/compatibility/matrix.yml:"
                        f"hosts.{host_name}.discovery_route"
                    ),
                    (
                        "Distributed host routes must use a ~/ home-relative "
                        "identity; absolute routes are accepted only in "
                        "isolated test fixtures."
                    ),
                ))
    environments = compatibility.get("environments")
    if not isinstance(environments, list):
        return failures
    identifiers: set[str] = set()
    for index, record in enumerate(environments):
        label = f"maintainer/compatibility/matrix.yml:environments[{index}]"
        if not isinstance(record, dict):
            continue
        identifier = str(record.get("id", ""))
        if identifier in identifiers:
            failures.append(issue(
                "duplicate-compatibility-environment",
                label,
                identifier,
            ))
        identifiers.add(identifier)
        path_failures, normalized = validate_evidence_paths(
            record.get("evidence"),
            plugin,
            label,
        )
        failures.extend(path_failures)
        checks = record.get("checks")
        if not isinstance(checks, dict):
            continue
        passed = sorted(
            str(name)
            for name, status in checks.items()
            if status == "passed"
        )
        if passed and not normalized:
            failures.append(issue(
                "compatibility-environment-pass-unbound",
                label,
                "Passed checks need attributable package evidence.",
            ))
        if record.get("scope") == "ci_contract" and passed:
            canonical_import = (
                f"{CI_IMPORT_ROOT}/{identifier}/{CI_IMPORT_RECORD_NAME}"
            ).casefold()
            if canonical_import not in normalized:
                failures.append(issue(
                    "compatibility-ci-pass-without-run-record",
                    label,
                    (
                        "A workflow declaration is not a successful CI run "
                        "record; a passed check must cite its canonical "
                        "retained import."
                    ),
                ))
        if (
            record.get("scope") == "local_toolchain"
            and checks.get("unit_tests") == "passed"
        ):
            attestation_key = LOCAL_UNIT_TEST_ATTESTATION.casefold()
            if attestation_key not in normalized:
                failures.append(issue(
                    "compatibility-unit-tests-pass-unbound",
                    label,
                    (
                        "A local unit-test pass must cite the canonical "
                        f"{LOCAL_UNIT_TEST_ATTESTATION} record."
                    ),
                ))
            else:
                try:
                    attestation = load_json(
                        plugin / LOCAL_UNIT_TEST_ATTESTATION
                    )
                    release_manifest = load_json(
                        plugin / LOCAL_RELEASE_MANIFEST
                    )
                    attestation_failures = test_attestation_failures(
                        attestation,
                        plugin,
                        plugin / LOCAL_UNIT_TEST_SCHEMA,
                        release_manifest,
                    )
                    attested_python = (
                        attestation.get("python", {}).get("version")
                        if isinstance(attestation, dict)
                        and isinstance(attestation.get("python"), dict)
                        else None
                    )
                    if (
                        not isinstance(record.get("python"), str)
                        or record.get("python") != attested_python
                    ):
                        attestation_failures.append(issue(
                            "compatibility-unit-tests-python-mismatch",
                            LOCAL_UNIT_TEST_ATTESTATION,
                            (
                                "The local compatibility Python version does "
                                "not equal the attested Python version."
                            ),
                        ))
                except (OSError, ToolFailure) as exc:
                    attestation_failures = [issue(
                        "compatibility-unit-tests-evidence-unreadable",
                        LOCAL_UNIT_TEST_ATTESTATION,
                        str(exc),
                    )]
                if attestation_failures:
                    failure_codes = sorted({
                        finding["code"]
                        for finding in attestation_failures
                        if isinstance(finding, dict)
                        and isinstance(finding.get("code"), str)
                    })
                    failures.append(issue(
                        "compatibility-unit-tests-pass-invalid",
                        label,
                        (
                            "The cited local unit-test attestation is not a "
                            "current valid pass: "
                            + ", ".join(failure_codes)
                            + "."
                        ),
                    ))
        if (
            record.get("scope") == "local_toolchain"
            and checks.get("package_audit") == "passed"
        ):
            failures.append(issue(
                "compatibility-package-audit-pass-unbound",
                label,
                (
                    "No retained schema-valid current local package-audit "
                    "record contract is distributed. Keep package_audit "
                    "non-passed until such a record is implemented and cited; "
                    "a rerunnable command or shared evidence list is not a "
                    "per-check attestation."
                ),
            ))
        if (
            checks.get("installer_lifecycle") == "passed"
            and (
                "maintainer/attestations/install-lifecycle.json"
                not in normalized
            )
        ):
            failures.append(issue(
                "compatibility-installer-pass-unbound",
                label,
                (
                    "Installer lifecycle pass must cite the isolated "
                    "install-lifecycle attestation."
                ),
            ))
        if (
            checks.get("behavioral_eval") == "passed"
            and not any(
                path.startswith("maintainer/evals/results/")
                for path in normalized
            )
        ):
            failures.append(issue(
                "compatibility-behavior-pass-unbound",
                label,
                "Behavioral pass must cite an evaluation result.",
            ))
        if (
            checks.get("host_discovery") == "passed"
            and not any(
                path.startswith("maintainer/evals/results/")
                for path in normalized
            )
        ):
            failures.append(issue(
                "compatibility-host-discovery-pass-unbound",
                label,
                (
                    "Host discovery means the host actually loaded the skill; "
                    "filesystem route evidence alone is insufficient, so a "
                    "host-native evaluation result must be cited."
                ),
            ))
        if (
            checks.get("rendered_review") == "passed"
            and not any(
                path.startswith("maintainer/evals/reviews/")
                for path in normalized
            )
        ):
            failures.append(issue(
                "compatibility-render-pass-unbound",
                label,
                "Rendered-review pass must cite a review record.",
            ))
    return failures


def fixture_catalog(
    fixtures_dir: Path,
) -> tuple[dict[str, dict[str, object]], list[dict[str, str]]]:
    catalog: dict[str, dict[str, object]] = {}
    failures: list[dict[str, str]] = []
    for path in sorted(fixtures_dir.glob("*.json")):
        try:
            payload = load_json(path)
            digest = file_sha256(path)
        except ToolFailure as exc:
            failures.append(exc.issue.as_dict())
            continue
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("suite"), str)
            or not isinstance(payload.get("cases"), list)
        ):
            continue
        cases = {
            case["id"]: case
            for case in payload["cases"]
            if isinstance(case, dict) and isinstance(case.get("id"), str)
        }
        input_records: dict[str, dict[str, object]] = {}
        for case_id, case in cases.items():
            input_dir = case.get("input_dir")
            if isinstance(input_dir, str):
                relative = portable_relative(input_dir)
                candidate = (
                    absolute(path.parent.joinpath(*relative.split("/")))
                    if relative is not None
                    else None
                )
                try:
                    if (
                        candidate is None
                        or not is_within(candidate, fixtures_dir)
                        or not candidate.is_dir()
                    ):
                        raise ToolFailure(
                            "fixture-input-invalid",
                            "Fixture input directory is unsafe or missing.",
                            candidate or path,
                        )
                    records, snapshot_hash = eval_content_manifest(candidate)
                except ToolFailure as exc:
                    failures.append(exc.issue.as_dict())
                    continue
            else:
                records, snapshot_hash = [], hashlib.sha256().hexdigest()
            input_records[case_id] = {
                "sha256": snapshot_hash,
                "entry_count": len(records),
                "file_count": sum(item["type"] == "file" for item in records),
                "bytes": sum(
                    int(item["size"])
                    for item in records
                    if item["type"] == "file"
                ),
            }
        suite_name = payload["suite"]
        if suite_name in catalog:
            continue
        catalog[suite_name] = {
            "path": path,
            "sha256": digest,
            "skill_instructions": payload.get("skill_instructions"),
            "cases": cases,
            "input_snapshots": input_records,
        }
    return catalog, failures


def record_tree_failures(
    files: object,
    expected_hash: object,
    label: str,
) -> list[dict[str, str]]:
    if expected_hash is None and files == []:
        return []
    surrogate = {
        "files": files,
        "content_sha256": expected_hash,
        "distribution_files": files,
        "distribution_sha256": expected_hash,
        "codex_plugin_manifest_sha256": None,
        "claude_plugin_manifest_sha256": None,
        "sbom_sha256": None,
        "compatibility_matrix_sha256": None,
        "trusted_adapters_sha256": None,
    }
    return [
        issue(f"eval-{item['code']}", label, item["message"])
        for item in manifest_semantic_failures(surrogate, label)
    ]


def result_evidence_path(
    result_path: Path,
    value: object,
    label: str,
) -> tuple[Path | None, list[dict[str, str]]]:
    relative = portable_relative(value)
    if relative is None:
        return None, [issue(
            "eval-evidence-path-unsafe",
            label,
            "Result evidence must use a safe path relative to the result directory.",
        )]
    root = absolute(result_path.parent)
    candidate = absolute(root.joinpath(*relative.split("/")))
    try:
        if not is_within(candidate, root):
            raise ToolFailure(
                "eval-evidence-path-escape",
                "Result evidence leaves its result directory.",
                candidate,
            )
        assert_no_reparse_path(candidate, stop=root)
    except ToolFailure as exc:
        return None, [issue(
            "eval-evidence-path-unsafe",
            label,
            str(exc),
        )]
    return candidate, []


def trusted_adapter_failures(
    payload: object,
    plugin: Path,
    label: str,
) -> tuple[list[dict[str, str]], set[tuple[str, str, str, str]]]:
    failures: list[dict[str, str]] = []
    trusted: set[tuple[str, str, str, str]] = set()
    if not isinstance(payload, dict):
        return [issue(
            "trusted-adapter-registry-invalid",
            label,
            "Trusted adapter registry must be an object.",
        )], trusted
    adapters = payload.get("adapters")
    if not isinstance(adapters, dict):
        return failures, trusted
    for adapter_id, record in adapters.items():
        record_label = f"{label}:{adapter_id}"
        if not isinstance(record, dict):
            continue
        source_id = record.get("source_id")
        if (
            isinstance(source_id, str)
            and NON_RELEASE_EVIDENCE_ID.search(source_id)
        ):
            failures.append(issue(
                "trusted-adapter-test-identity",
                record_label,
                "Mock, test, fixture, demo, and sample identities cannot be trusted.",
            ))
            continue
        relative = portable_relative(record.get("implementation_path"))
        if relative is None:
            failures.append(issue(
                "trusted-adapter-path-unsafe",
                record_label,
                "implementation_path must be a safe package-relative file.",
            ))
            continue
        implementation = absolute(plugin.joinpath(*relative.split("/")))
        try:
            if not is_within(implementation, plugin):
                raise ToolFailure(
                    "trusted-adapter-path-escape",
                    "Adapter implementation leaves the package.",
                    implementation,
                )
            assert_no_reparse_path(implementation, stop=plugin)
            digest = file_sha256(implementation)
        except ToolFailure as exc:
            failures.append(issue(
                "trusted-adapter-implementation-invalid",
                record_label,
                str(exc),
            ))
            continue
        if digest != record.get("implementation_sha256"):
            failures.append(issue(
                "trusted-adapter-implementation-drift",
                record_label,
                "Adapter implementation does not match its owner-approved hash.",
            ))
            continue
        values = (
            record.get("host"),
            source_id,
            record.get("source_version"),
            record.get("method"),
        )
        if all(isinstance(value, str) for value in values):
            trusted.add(values)  # type: ignore[arg-type]
    return failures, trusted


def eval_artifact_bundle_failures(
    run: dict[str, object],
    run_label: str,
    *,
    result_path: Path | None,
    release_required: bool,
) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    bundle = run.get("artifact_bundle")
    if not isinstance(bundle, dict):
        if release_required:
            failures.append(issue(
                "release-artifact-bundle-missing",
                run_label,
                (
                    "A passed release run needs a retained, inspectable artifact "
                    "bundle; hashes without files are insufficient."
                ),
            ))
        return failures
    for field, expected in (
        ("sha256", run.get("workspace_sha256")),
        ("entry_count", run.get("workspace_entry_count")),
        ("file_count", run.get("workspace_file_count")),
        ("bytes", run.get("workspace_bytes")),
    ):
        if bundle.get(field) != expected:
            failures.append(issue(
                "eval-artifact-bundle-metadata-mismatch",
                run_label,
                f"artifact_bundle.{field} does not match the captured workspace.",
            ))
    if result_path is None:
        if release_required:
            failures.append(issue(
                "release-artifact-bundle-uninspectable",
                run_label,
                "The audit cannot resolve artifact evidence without its result path.",
            ))
        return failures
    candidate, path_failures = result_evidence_path(
        result_path,
        bundle.get("path"),
        run_label,
    )
    failures.extend(path_failures)
    if candidate is None:
        return failures
    if not candidate.is_dir():
        failures.append(issue(
            "eval-artifact-bundle-missing",
            run_label,
            f"Retained artifact bundle is not a directory: {bundle.get('path')}",
        ))
        return failures
    try:
        records, content_hash = eval_content_manifest(candidate)
    except ToolFailure as exc:
        failures.append(issue(
            "eval-artifact-bundle-invalid",
            run_label,
            str(exc),
        ))
        return failures
    if records != run.get("files") or content_hash != run.get("workspace_sha256"):
        failures.append(issue(
            "eval-artifact-bundle-parity-failed",
            run_label,
            "Retained artifact contents do not match the run manifest and hash.",
        ))
    return failures


def parse_aware_eval_time(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def eval_host_native_evidence_failures(
    run: dict[str, object],
    run_label: str,
    *,
    session_nonce: object,
    result_path: Path | None,
    required: bool,
    release_mode: bool = False,
    trusted_adapters: set[tuple[str, str, str, str]] | None = None,
) -> list[dict[str, str]]:
    """Verify retained challenge/response bytes, run binding, and event time."""
    failures: list[dict[str, str]] = []
    status = run.get("host_native_evidence_status")
    challenge_record = run.get("host_native_challenge")
    evidence_record = run.get("host_native_evidence")
    run_started = parse_aware_eval_time(run.get("started_at"))
    run_finished = parse_aware_eval_time(run.get("finished_at"))

    challenge_payload: dict[str, object] | None = None
    challenge_digest: str | None = None
    if isinstance(challenge_record, dict):
        if result_path is None:
            failures.append(issue(
                "eval-host-native-challenge-uninspectable",
                run_label,
                "The audit cannot resolve the retained challenge without its result path.",
            ))
        else:
            candidate, path_failures = result_evidence_path(
                result_path,
                challenge_record.get("path"),
                run_label,
            )
            failures.extend(path_failures)
            if candidate is not None:
                if not candidate.is_file():
                    failures.append(issue(
                        "eval-host-native-challenge-missing",
                        run_label,
                        (
                            "Retained host-native challenge file is missing: "
                            f"{challenge_record.get('path')}"
                        ),
                    ))
                else:
                    try:
                        challenge_digest = file_sha256(candidate)
                        loaded = load_json(candidate)
                    except ToolFailure as exc:
                        failures.append(issue(
                            "eval-host-native-challenge-invalid",
                            run_label,
                            str(exc),
                        ))
                    else:
                        if (
                            challenge_digest != challenge_record.get("sha256")
                            or not isinstance(loaded, dict)
                        ):
                            failures.append(issue(
                                "eval-host-native-challenge-hash-mismatch",
                                run_label,
                                "Challenge metadata does not bind the retained JSON bytes.",
                            ))
                        elif isinstance(loaded, dict):
                            challenge_payload = loaded

        expected_challenge = {
            "schema_version": 2,
            "challenge_id": challenge_record.get("challenge_id"),
            "session_nonce": session_nonce,
            "run_nonce": challenge_record.get("run_nonce"),
            "issued_at": run.get("started_at"),
            "host": run.get("host"),
            "case": run.get("case"),
            "variant": run.get("variant"),
            "run": run.get("run"),
            "run_id": run.get("run_id"),
            "skill_loaded": run.get("variant") == "skill",
            "skill_content_sha256": run.get("skill_content_sha256"),
        }
        if challenge_payload is not None:
            if set(challenge_payload) != set(expected_challenge):
                failures.append(issue(
                    "eval-host-native-challenge-shape-invalid",
                    run_label,
                    "Host-native challenge has missing or unknown fields.",
                ))
            for field, expected_value in expected_challenge.items():
                if challenge_payload.get(field) != expected_value:
                    failures.append(issue(
                        "eval-host-native-challenge-parity-failed",
                        run_label,
                        f"{field} differs from the run-bound challenge metadata.",
                    ))
        for field in ("session_nonce", "issued_at"):
            if challenge_record.get(field) != expected_challenge[field]:
                failures.append(issue(
                    "eval-host-native-challenge-parity-failed",
                    run_label,
                    f"Challenge record {field} differs from the result run.",
                ))
        nonce = challenge_record.get("run_nonce")
        run_id = run.get("run_id")
        if all(isinstance(value, str) for value in (session_nonce, nonce, run_id)):
            expected_id = hashlib.sha256(
                f"{session_nonce}\0{nonce}\0{run_id}".encode("utf-8")
            ).hexdigest()
            if challenge_record.get("challenge_id") != expected_id:
                failures.append(issue(
                    "eval-host-native-challenge-id-invalid",
                    run_label,
                    "challenge_id is not derived from this session, run nonce, and run ID.",
                ))

        issued = parse_aware_eval_time(challenge_record.get("issued_at"))
        if issued is None:
            failures.append(issue(
                "eval-host-native-challenge-time-invalid",
                run_label,
                "Challenge issued_at must be a timezone-aware date-time.",
            ))
        elif run_started is not None and run_finished is not None and (
            issued < run_started - HOST_EVIDENCE_CLOCK_SKEW
            or issued > run_finished + HOST_EVIDENCE_CLOCK_SKEW
        ):
            failures.append(issue(
                "eval-host-native-challenge-time-outside-run",
                run_label,
                "Challenge issued_at falls outside this run's bounded time window.",
            ))
    elif status == "bound":
        failures.append(issue(
            "eval-host-native-challenge-inconsistent",
            run_label,
            "bound status requires a retained per-run challenge.",
        ))

    if status != "bound":
        if required:
            failures.append(issue(
                "release-host-native-evidence-missing",
                run_label,
                (
                    "A driver report is self-reported. This run needs separately "
                    "bound host-native adapter or telemetry evidence."
                ),
            ))
        return failures
    if not isinstance(evidence_record, dict):
        failures.append(issue(
            "eval-host-native-evidence-inconsistent",
            run_label,
            "bound status requires a host-native evidence record.",
        ))
        return failures
    if challenge_payload is None or challenge_digest is None:
        failures.append(issue(
            "eval-host-native-challenge-unverified",
            run_label,
            "Bound evidence requires a valid retained challenge.",
        ))
        return failures
    if result_path is None:
        failures.append(issue(
            "eval-host-native-evidence-uninspectable",
            run_label,
            "The audit cannot resolve host-native evidence without its result path.",
        ))
        return failures

    candidate, path_failures = result_evidence_path(
        result_path,
        evidence_record.get("path"),
        run_label,
    )
    failures.extend(path_failures)
    if candidate is None:
        return failures
    if not candidate.is_file():
        failures.append(issue(
            "eval-host-native-evidence-missing",
            run_label,
            f"Host-native evidence file is missing: {evidence_record.get('path')}",
        ))
        return failures
    try:
        evidence_digest = file_sha256(candidate)
        payload = load_json(candidate)
    except ToolFailure as exc:
        failures.append(issue(
            "eval-host-native-evidence-invalid",
            run_label,
            str(exc),
        ))
        return failures
    if (
        evidence_digest != evidence_record.get("sha256")
        or not isinstance(payload, dict)
    ):
        failures.append(issue(
            "eval-host-native-evidence-hash-mismatch",
            run_label,
            "Host-native evidence is not a hash-bound JSON object.",
        ))
        return failures

    expected = {
        "schema_version": 2,
        "challenge_id": challenge_payload.get("challenge_id"),
        "challenge_sha256": challenge_digest,
        "session_nonce": session_nonce,
        "run_nonce": challenge_payload.get("run_nonce"),
        "host": run.get("host"),
        "case": run.get("case"),
        "variant": run.get("variant"),
        "run": run.get("run"),
        "run_id": run.get("run_id"),
        "skill_loaded": run.get("variant") == "skill",
        "skill_content_sha256": run.get("skill_content_sha256"),
        "method": evidence_record.get("method"),
        "source_id": evidence_record.get("source_id"),
        "source_version": evidence_record.get("source_version"),
        "observed_at": evidence_record.get("observed_at"),
    }
    if set(payload) != set(expected):
        failures.append(issue(
            "eval-host-native-evidence-shape-invalid",
            run_label,
            "Host-native evidence has missing or unknown fields.",
        ))
    for field, expected_value in expected.items():
        if payload.get(field) != expected_value:
            failures.append(issue(
                "eval-host-native-evidence-parity-failed",
                run_label,
                f"{field} differs from the run, challenge, or evidence metadata.",
            ))
    for field in (
        "challenge_id",
        "challenge_sha256",
        "session_nonce",
        "run_nonce",
    ):
        if evidence_record.get(field) != expected[field]:
            failures.append(issue(
                "eval-host-native-evidence-parity-failed",
                run_label,
                f"Evidence record {field} differs from the retained challenge.",
            ))

    observed = parse_aware_eval_time(evidence_record.get("observed_at"))
    captured = parse_aware_eval_time(evidence_record.get("captured_at"))
    for field, moment in (("observed_at", observed), ("captured_at", captured)):
        if moment is None:
            failures.append(issue(
                "eval-host-native-evidence-time-invalid",
                run_label,
                f"{field} must be a timezone-aware date-time.",
            ))
        elif run_started is not None and run_finished is not None:
            if moment < run_started - HOST_EVIDENCE_CLOCK_SKEW:
                failures.append(issue(
                    "eval-host-native-evidence-stale",
                    run_label,
                    f"{field} predates this run's bounded time window.",
                ))
            if moment > run_finished + HOST_EVIDENCE_CLOCK_SKEW:
                failures.append(issue(
                    "eval-host-native-evidence-future",
                    run_label,
                    f"{field} follows this run's bounded time window.",
                ))
    if (
        observed is not None
        and captured is not None
        and captured < observed - HOST_EVIDENCE_CLOCK_SKEW
    ):
        failures.append(issue(
            "eval-host-native-evidence-time-order-invalid",
            run_label,
            "captured_at materially predates observed_at.",
        ))

    if evidence_record.get("method") not in {
        "host-adapter-event",
        "host-api-telemetry",
        "host-runtime-log",
    }:
        failures.append(issue(
            "eval-host-native-method-invalid",
            run_label,
            "Evidence method is not host-native adapter or telemetry output.",
        ))
    if release_mode:
        source_id = evidence_record.get("source_id")
        identity = (
            str(run.get("host")),
            str(source_id),
            str(evidence_record.get("source_version")),
            str(evidence_record.get("method")),
        )
        if (
            not isinstance(source_id, str)
            or NON_RELEASE_EVIDENCE_ID.search(source_id)
        ):
            failures.append(issue(
                "release-host-native-test-identity",
                run_label,
                "Mock, test, fixture, demo, and sample evidence cannot qualify a release.",
            ))
        elif trusted_adapters is None or identity not in trusted_adapters:
            failures.append(issue(
                "release-host-native-adapter-untrusted",
                run_label,
                (
                    "Host-native evidence source, version, host, and method must "
                    "match the owner-controlled trusted-adapter registry."
                ),
            ))
    return failures


def eval_semantic_failures(
    payload: object,
    catalog: dict[str, dict[str, object]],
    label: str,
    *,
    harness_path: Path,
    suite_schema_path: Path,
    result_schema_path: Path,
    result_path: Path | None = None,
    release_mode: bool = False,
    trusted_adapters: set[tuple[str, str, str, str]] | None = None,
) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    if not isinstance(payload, dict):
        return [issue("eval-result-not-object", label, "Result must be an object.")]
    suite_name = payload.get("suite")
    suite_record = catalog.get(str(suite_name))
    if suite_record is None:
        failures.append(issue(
            "eval-suite-not-found",
            label,
            f"No fixture suite named {suite_name!r} exists.",
        ))
        return failures
    cases = suite_record.get("cases")
    expected_input_snapshots = suite_record.get("input_snapshots")
    if not isinstance(cases, dict):
        return failures

    host = payload.get("host")
    session_nonce = payload.get("session_nonce")
    result_started = parse_aware_eval_time(payload.get("started_at"))
    result_finished = parse_aware_eval_time(payload.get("finished_at"))
    if result_started is None or result_finished is None:
        failures.append(issue(
            "eval-time-zone-invalid",
            label,
            "started_at and finished_at must be timezone-aware date-times.",
        ))
    elif result_started > result_finished:
        failures.append(issue(
            "eval-time-order-invalid",
            label,
            "started_at follows finished_at.",
        ))
    package = payload.get("package")
    package_hash = package.get("content_sha256") if isinstance(package, dict) else None
    prompt_contract = payload.get("prompt_contract")
    fixture_instructions = suite_record.get("skill_instructions")
    fixture_instruction = (
        fixture_instructions.get(host)
        if isinstance(fixture_instructions, dict)
        and isinstance(host, str)
        else None
    )
    if (
        isinstance(prompt_contract, dict)
        and prompt_contract.get("skill_instruction") != fixture_instruction
    ):
        failures.append(issue(
            "eval-prompt-contract-drift",
            label,
            "Recorded skill instruction differs from the fixture.",
        ))
    recorded_invocation_modes = (
        prompt_contract.get("invocation_modes")
        if isinstance(prompt_contract, dict)
        and isinstance(prompt_contract.get("invocation_modes"), dict)
        else {}
    )
    recorded_installation_modes = (
        prompt_contract.get("installation_modes")
        if isinstance(prompt_contract, dict)
        and isinstance(prompt_contract.get("installation_modes"), dict)
        else {}
    )

    provenance = payload.get("provenance")
    selected_cases: list[str] = []
    expected_runs = None
    input_snapshots: dict[str, object] = {}
    execution_order: list[str] = []
    monitor_roots: list[str] = []
    driver_report_required = False
    host_native_evidence_required = False
    host_native_evidence_source_configured = False
    workspace_limits: dict[str, object] = {}
    if isinstance(provenance, dict):
        expected_hashes = {
            "fixture_sha256": suite_record.get("sha256"),
            "harness_sha256": file_sha256(harness_path),
            "suite_schema_sha256": file_sha256(suite_schema_path),
            "result_schema_sha256": file_sha256(result_schema_path),
        }
        for field, expected in expected_hashes.items():
            if provenance.get(field) != expected:
                failures.append(issue(
                    "eval-provenance-drift",
                    label,
                    f"{field} does not match the current recorded source.",
                ))
        if isinstance(provenance.get("selected_cases"), list):
            selected_cases = [
                value for value in provenance["selected_cases"] if isinstance(value, str)
            ]
        expected_runs = provenance.get("runs_per_case")
        if isinstance(provenance.get("input_snapshots"), dict):
            input_snapshots = provenance["input_snapshots"]
        if isinstance(provenance.get("execution_order"), list):
            execution_order = [
                value for value in provenance["execution_order"] if isinstance(value, str)
            ]
        if isinstance(provenance.get("monitor_roots"), list):
            monitor_roots = [
                value for value in provenance["monitor_roots"] if isinstance(value, str)
            ]
        driver_report_required = bool(provenance.get("driver_report_required"))
        host_native_evidence_required = bool(
            provenance.get("host_native_evidence_required")
        )
        host_native_evidence_source_configured = bool(
            provenance.get("host_native_evidence_source_configured")
        )
        if isinstance(provenance.get("workspace_limits"), dict):
            workspace_limits = provenance["workspace_limits"]
        if len(selected_cases) != len(set(selected_cases)):
            failures.append(issue(
                "eval-selected-cases-duplicate",
                label,
                "selected_cases must be unique.",
            ))
        unknown = sorted(set(selected_cases) - set(cases))
        if unknown:
            failures.append(issue(
                "eval-selected-case-unknown",
                label,
                ", ".join(unknown),
            ))
        if set(input_snapshots) != set(selected_cases):
            failures.append(issue(
                "eval-input-snapshot-coverage",
                label,
                "input_snapshots keys must exactly equal selected_cases.",
            ))
        if isinstance(expected_input_snapshots, dict):
            for case_id in selected_cases:
                if input_snapshots.get(case_id) != expected_input_snapshots.get(case_id):
                    failures.append(issue(
                        "eval-input-snapshot-source-drift",
                        label,
                        f"{case_id} does not match its current fixture input snapshot.",
                    ))
        max_entries = workspace_limits.get("max_entries")
        max_files = workspace_limits.get("max_files")
        max_bytes = workspace_limits.get("max_bytes")
        for case_id, snapshot in input_snapshots.items():
            if not isinstance(snapshot, dict):
                continue
            exceeds_limit = (
                isinstance(max_entries, int)
                and isinstance(snapshot.get("entry_count"), int)
                and snapshot["entry_count"] > max_entries
            ) or (
                isinstance(max_files, int)
                and isinstance(snapshot.get("file_count"), int)
                and snapshot["file_count"] > max_files
            ) or (
                isinstance(max_bytes, int)
                and isinstance(snapshot.get("bytes"), int)
                and snapshot["bytes"] > max_bytes
            )
            if exceeds_limit:
                failures.append(issue(
                    "eval-input-snapshot-limit-inconsistent",
                    label,
                    f"{case_id} exceeds the evaluator's declared workspace limits.",
                ))
        cleanup_problem = provenance.get("cleanup_problem")
        retained_session = provenance.get("retained_session")
        if cleanup_problem is not None and retained_session is None:
            failures.append(issue(
                "eval-cleanup-provenance-incomplete",
                label,
                "A cleanup failure must record the retained session path.",
            ))

    runs = payload.get("runs")
    if not isinstance(runs, list):
        return failures
    run_ids: list[str] = []
    identities: set[tuple[object, object, object]] = set()
    observed_counts: Counter[tuple[str, str]] = Counter()
    observed_variants: set[str] = set()
    summary_counts: Counter[str] = Counter()
    runs_by_case_variant: defaultdict[tuple[str, str], list[int]] = defaultdict(list)
    artifact_paths: set[str] = set()
    challenge_paths: set[str] = set()
    challenge_ids: set[str] = set()
    run_nonces: set[str] = set()
    host_native_paths: set[str] = set()
    host_native_digests: set[str] = set()
    for index, run in enumerate(runs):
        run_label = f"{label}#runs/{index}"
        if not isinstance(run, dict):
            continue
        case_id = run.get("case")
        variant = run.get("variant")
        run_number = run.get("run")
        run_id = run.get("run_id")
        identity = (case_id, variant, run_number)
        if identity in identities:
            failures.append(issue(
                "eval-duplicate-run-identity",
                run_label,
                repr(identity),
            ))
        identities.add(identity)
        if isinstance(run_id, str):
            run_ids.append(run_id)
        expected_run_id = f"{suite_name}:{host}:{case_id}:{variant}:{run_number}"
        if run_id != expected_run_id:
            failures.append(issue(
                "eval-run-id-inconsistent",
                run_label,
                f"{run_id!r} != {expected_run_id!r}",
            ))
        if run.get("host") != host:
            failures.append(issue(
                "eval-run-host-inconsistent",
                run_label,
                f"{run.get('host')!r} != {host!r}",
            ))
        run_started = parse_aware_eval_time(run.get("started_at"))
        run_finished = parse_aware_eval_time(run.get("finished_at"))
        if run_started is None or run_finished is None:
            failures.append(issue(
                "eval-run-time-zone-invalid",
                run_label,
                "Run started_at and finished_at must be timezone-aware date-times.",
            ))
        elif run_started > run_finished:
            failures.append(issue(
                "eval-run-time-order-invalid",
                run_label,
                "Run started_at follows run finished_at.",
            ))
        elif (
            result_started is not None
            and result_finished is not None
            and (
                run_started < result_started - HOST_EVIDENCE_CLOCK_SKEW
                or run_finished > result_finished + HOST_EVIDENCE_CLOCK_SKEW
            )
        ):
            failures.append(issue(
                "eval-run-time-outside-result",
                run_label,
                "Run timestamps fall outside the result's bounded session window.",
            ))
        case = cases.get(case_id) if isinstance(case_id, str) else None
        if not isinstance(case, dict):
            failures.append(issue(
                "eval-run-case-unknown",
                run_label,
                str(case_id),
            ))
            continue
        if case_id not in selected_cases:
            failures.append(issue(
                "eval-run-case-not-selected",
                run_label,
                str(case_id),
            ))
        task = str(case.get("task", "")).strip()
        invocation_mode = str(case.get("invocation_mode", "explicit"))
        installation_mode = str(
            case.get("installation_mode", "direct-skill")
        )
        if run.get("invocation_mode") != invocation_mode:
            failures.append(issue(
                "eval-invocation-mode-drift",
                run_label,
                (
                    f"{run.get('invocation_mode')!r} does not match fixture "
                    f"mode {invocation_mode!r}."
                ),
            ))
        if recorded_invocation_modes.get(str(case_id)) != invocation_mode:
            failures.append(issue(
                "eval-invocation-provenance-drift",
                run_label,
                "Prompt provenance does not record the resolved fixture mode.",
            ))
        if run.get("installation_mode") != installation_mode:
            failures.append(issue(
                "eval-installation-mode-drift",
                run_label,
                (
                    f"{run.get('installation_mode')!r} does not match fixture "
                    f"mode {installation_mode!r}."
                ),
            ))
        if (
            recorded_installation_modes.get(str(case_id))
            != installation_mode
        ):
            failures.append(issue(
                "eval-installation-provenance-drift",
                run_label,
                (
                    "Prompt provenance does not record the resolved "
                    "installation mode."
                ),
            ))
        if installation_mode != "direct-skill":
            failures.append(issue(
                "eval-installation-mode-unsupported",
                run_label,
                (
                    "The current evaluator cannot substantiate packaged-plugin "
                    "installation or namespaced invocation."
                ),
            ))
        if run.get("task_sha256") != text_sha256(task):
            failures.append(issue(
                "eval-task-hash-inconsistent",
                run_label,
                "task_sha256 does not match the fixture task.",
            ))
        instruction = str(fixture_instruction).strip()
        prompt = f"Task: {task}"
        if variant == "skill" and invocation_mode == "explicit":
            prompt = f"{instruction}\n\n{prompt}"
        if run.get("prompt_sha256") != text_sha256(prompt):
            failures.append(issue(
                "eval-prompt-hash-inconsistent",
                run_label,
                "prompt_sha256 does not match the controlled prompt contract.",
            ))
        for field, expected in (
            ("review_requirements", case.get("review_requirements")),
            ("tags", case.get("tags", [])),
            ("adversarial", bool(case.get("adversarial", False))),
        ):
            if run.get(field) != expected:
                failures.append(issue(
                    "eval-case-metadata-drift",
                    run_label,
                    f"{field} differs from the fixture.",
                ))
        expected_review_contract = case_review_contract(case)
        if run.get("review_contract") != expected_review_contract:
            failures.append(issue(
                "eval-review-contract-drift",
                run_label,
                (
                    "The run's structured review contract does not match the "
                    "fixture requirements, adversarial gate, or release coverage."
                ),
            ))
        snapshot = input_snapshots.get(case_id)
        if (
            isinstance(snapshot, dict)
            and run.get("input_snapshot_sha256") != snapshot.get("sha256")
        ):
            failures.append(issue(
                "eval-input-snapshot-inconsistent",
                run_label,
                "Run input hash differs from provenance.",
            ))

        problems = run.get("problems")
        passed = run.get("passed")
        timed_out = bool(run.get("timed_out"))
        output_limited = bool(run.get("output_limit_exceeded"))
        duration = run.get("duration_seconds")
        if (
            not isinstance(duration, (int, float))
            or isinstance(duration, bool)
            or not math.isfinite(duration)
            or duration < 0
        ):
            failures.append(issue(
                "eval-duration-invalid",
                run_label,
                repr(duration),
            ))
        if passed is True and (
            not isinstance(problems, list)
            or problems
            or timed_out
            or output_limited
            or run.get("skill_route_verified_before") is not True
            or run.get("skill_route_verified_after") is not True
        ):
            failures.append(issue(
                "eval-false-pass",
                run_label,
                "A passed run has a recorded problem, timeout, limit, or route-integrity failure.",
            ))
        if passed is False and isinstance(problems, list) and not problems:
            failures.append(issue(
                "eval-unexplained-failure",
                run_label,
                "A failed run needs at least one recorded problem.",
            ))
        if passed is True:
            summary_counts["passed"] += 1
        else:
            summary_counts["failed"] += 1

        if variant == "skill":
            if (
                run.get("skill_staged") is not True
                or run.get("skill_content_sha256") != package_hash
            ):
                failures.append(issue(
                    "eval-skill-identity-inconsistent",
                    run_label,
                    "Skill run does not carry the result package hash.",
                ))
        elif variant == "baseline":
            if (
                run.get("skill_staged") is not False
                or run.get("skill_content_sha256") is not None
            ):
                failures.append(issue(
                    "eval-baseline-contaminated",
                    run_label,
                    "Baseline records a staged skill or skill hash.",
                ))

        driver_report_status = run.get("driver_report_status")
        driver_report = run.get("driver_report")
        if (
            driver_report_required
            and passed is True
            and driver_report_status != "driver_reported"
        ):
            failures.append(issue(
                "eval-required-driver-report-missing",
                run_label,
                str(driver_report_status),
            ))
        if (
            driver_report_status == "driver_reported"
            and isinstance(driver_report, dict)
        ):
            expected_driver_report = {
                "host": host,
                "case": case_id,
                "variant": variant,
                "run": run_number,
                "skill_loaded": variant == "skill",
                "skill_content_sha256": (
                    package_hash if variant == "skill" else None
                ),
            }
            for field, expected in expected_driver_report.items():
                if driver_report.get(field) != expected:
                    failures.append(issue(
                        "eval-driver-report-inconsistent",
                        run_label,
                        f"{field} differs from the run.",
                    ))
        elif driver_report_status == "driver_reported":
            failures.append(issue(
                "eval-driver-report-inconsistent",
                run_label,
                "driver_reported status requires a driver report object.",
            ))
        if passed is True and driver_report_status in {"missing", "invalid"}:
            failures.append(issue(
                "eval-false-pass",
                run_label,
                f"Passed run has {driver_report_status} driver report.",
            ))

        monitors = run.get("monitors")
        if isinstance(monitors, list):
            roots = [
                item.get("root")
                for item in monitors
                if isinstance(item, dict)
            ]
            if roots != monitor_roots:
                failures.append(issue(
                    "eval-monitor-coverage-inconsistent",
                    run_label,
                    "Run monitor roots differ from provenance.",
                ))
            for monitor in monitors:
                if not isinstance(monitor, dict):
                    continue
                changed = bool(monitor.get("changed"))
                changed_entries = monitor.get("changed_entries")
                if not changed and (
                    monitor.get("before_sha256") != monitor.get("after_sha256")
                    or (isinstance(changed_entries, list) and changed_entries)
                    or monitor.get("error") is not None
                ):
                    failures.append(issue(
                        "eval-monitor-state-inconsistent",
                        run_label,
                        f"{monitor.get('root')}: unchanged record has differing evidence.",
                    ))
                if changed and passed is True:
                    failures.append(issue(
                        "eval-false-pass",
                        run_label,
                        f"Monitor {monitor.get('root')} changed.",
                    ))

        stdout_bytes = run.get("stdout_bytes")
        stderr_bytes = run.get("stderr_bytes")
        max_output = workspace_limits.get("max_output_bytes")
        if all(isinstance(value, int) for value in (stdout_bytes, stderr_bytes, max_output)):
            if stdout_bytes + stderr_bytes > max_output and not output_limited:
                failures.append(issue(
                    "eval-output-limit-inconsistent",
                    run_label,
                    "Captured byte count exceeds the declared limit without a limit failure.",
                ))
        files = run.get("files")
        workspace_hash = run.get("workspace_sha256")
        failures.extend(record_tree_failures(files, workspace_hash, run_label))
        bundle = run.get("artifact_bundle")
        if isinstance(bundle, dict) and isinstance(bundle.get("path"), str):
            bundle_key = bundle["path"].casefold()
            if bundle_key in artifact_paths:
                failures.append(issue(
                    "eval-artifact-bundle-reused",
                    run_label,
                    "Each run must retain its own artifact bundle.",
                ))
            artifact_paths.add(bundle_key)
        failures.extend(eval_artifact_bundle_failures(
            run,
            run_label,
            result_path=result_path,
            release_required=release_mode and passed is True,
        ))
        challenge_record = run.get("host_native_challenge")
        if isinstance(challenge_record, dict):
            if not host_native_evidence_source_configured:
                failures.append(issue(
                    "eval-host-native-challenge-source-inconsistent",
                    run_label,
                    "A challenge was retained although no evidence source was configured.",
                ))
            for field, seen, code in (
                (
                    "path",
                    challenge_paths,
                    "eval-host-native-challenge-path-reused",
                ),
                (
                    "challenge_id",
                    challenge_ids,
                    "eval-host-native-challenge-reused",
                ),
                (
                    "run_nonce",
                    run_nonces,
                    "eval-host-native-run-nonce-reused",
                ),
            ):
                value = challenge_record.get(field)
                if not isinstance(value, str):
                    continue
                key = value.casefold()
                if key in seen:
                    failures.append(issue(
                        code,
                        run_label,
                        f"Each run needs a unique host-native {field}.",
                    ))
                seen.add(key)
        elif (
            host_native_evidence_source_configured
            and passed is True
        ):
            failures.append(issue(
                "eval-host-native-challenge-missing",
                run_label,
                "A passed run with a configured evidence source needs its challenge.",
            ))
        native_record = run.get("host_native_evidence")
        if (
            isinstance(native_record, dict)
            and isinstance(native_record.get("path"), str)
        ):
            native_key = native_record["path"].casefold()
            if native_key in host_native_paths:
                failures.append(issue(
                    "eval-host-native-evidence-reused",
                    run_label,
                    "Each run needs its own host-native evidence record.",
                ))
            host_native_paths.add(native_key)
            native_digest = native_record.get("sha256")
            if isinstance(native_digest, str):
                if native_digest in host_native_digests:
                    failures.append(issue(
                        "eval-host-native-evidence-digest-reused",
                        run_label,
                        "Each run needs unique challenge-bound evidence bytes.",
                    ))
                host_native_digests.add(native_digest)
        native_required = passed is True and (
            host_native_evidence_required
            or (
                variant == "skill"
                and (release_mode or invocation_mode == "implicit")
            )
        )
        failures.extend(eval_host_native_evidence_failures(
            run,
            run_label,
            session_nonce=session_nonce,
            result_path=result_path,
            required=native_required,
            release_mode=release_mode,
            trusted_adapters=trusted_adapters,
        ))
        if isinstance(files, list) and isinstance(workspace_hash, str):
            entry_count = len(files)
            file_count = sum(
                isinstance(item, dict) and item.get("type") == "file"
                for item in files
            )
            total_bytes = sum(
                int(item.get("size", 0))
                for item in files
                if isinstance(item, dict) and item.get("type") == "file"
            )
            if run.get("workspace_entry_count") != entry_count:
                failures.append(issue(
                    "eval-workspace-entry-count-inconsistent",
                    run_label,
                    f"{run.get('workspace_entry_count')} != {entry_count}",
                ))
            if run.get("workspace_file_count") != file_count:
                failures.append(issue(
                    "eval-workspace-count-inconsistent",
                    run_label,
                    f"{run.get('workspace_file_count')} != {file_count}",
                ))
            if run.get("workspace_bytes") != total_bytes:
                failures.append(issue(
                    "eval-workspace-bytes-inconsistent",
                    run_label,
                    f"{run.get('workspace_bytes')} != {total_bytes}",
                ))
            max_entries = workspace_limits.get("max_entries")
            max_files = workspace_limits.get("max_files")
            max_bytes = workspace_limits.get("max_bytes")
            if (
                isinstance(max_entries, int)
                and entry_count > max_entries
            ) or (
                isinstance(max_files, int)
                and file_count > max_files
            ) or (
                isinstance(max_bytes, int)
                and total_bytes > max_bytes
            ):
                failures.append(issue(
                    "eval-workspace-limit-inconsistent",
                    run_label,
                    "Recorded workspace exceeds the declared evaluator limit.",
                ))
        changed_paths = run.get("changed_paths")
        if isinstance(changed_paths, list):
            seen_changed: set[str] = set()
            for raw in changed_paths:
                relative = portable_relative(raw)
                if relative is None:
                    failures.append(issue(
                        "eval-unsafe-changed-path",
                        run_label,
                        repr(raw),
                    ))
                elif relative.casefold() in seen_changed:
                    failures.append(issue(
                        "eval-duplicate-changed-path",
                        run_label,
                        relative,
                    ))
                else:
                    seen_changed.add(relative.casefold())

        if isinstance(case_id, str) and isinstance(variant, str):
            observed_counts[(case_id, variant)] += 1
            observed_variants.add(variant)
            if isinstance(run_number, int):
                runs_by_case_variant[(case_id, variant)].append(run_number)

    if execution_order != run_ids:
        failures.append(issue(
            "eval-execution-order-inconsistent",
            label,
            "provenance.execution_order must exactly match runs order.",
        ))
    if set(selected_cases) != {
        case for case, _variant in observed_counts
    }:
        failures.append(issue(
            "eval-selected-case-coverage",
            label,
            "selected_cases must exactly equal the cases represented by runs.",
        ))
    if isinstance(expected_runs, int):
        for key, numbers in runs_by_case_variant.items():
            if sorted(numbers) != list(range(1, expected_runs + 1)):
                failures.append(issue(
                    "eval-run-sequence-inconsistent",
                    label,
                    f"{key} has run numbers {sorted(numbers)}; expected 1..{expected_runs}.",
                ))
        for case_id in selected_cases:
            if observed_counts[(case_id, "skill")] != expected_runs:
                failures.append(issue(
                    "eval-skill-run-coverage",
                    label,
                    f"{case_id} has {observed_counts[(case_id, 'skill')]} skill runs; expected {expected_runs}.",
                ))

    drivers = payload.get("drivers")
    if isinstance(drivers, dict):
        verified_model_contexts: dict[str, dict[str, object]] = {}
        for variant in ("skill", "baseline"):
            driver = drivers.get(variant)
            if driver is None and variant == "baseline":
                continue
            if not isinstance(driver, dict):
                continue
            context = driver.get("model_context")
            context_label = f"{label}#drivers/{variant}/model_context"
            if not isinstance(context, dict):
                continue
            core = {
                key: value
                for key, value in context.items()
                if key != "sha256"
            }
            expected_context_hash = hashlib.sha256(
                json.dumps(
                    core,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
            if context.get("sha256") != expected_context_hash:
                failures.append(issue(
                    "eval-model-context-hash-mismatch",
                    context_label,
                    "model_context.sha256 does not bind the recorded context.",
                ))
            else:
                verified_model_contexts[variant] = context
            if (
                release_mode
                and context.get("declaration_status") != "declared"
            ):
                failures.append(issue(
                    "release-model-context-unreported",
                    context_label,
                    (
                        "Promoted release evidence requires a declared provider, "
                        "model, concrete model version, reasoning effort, and "
                        "safe generation configuration."
                    ),
                ))

        baseline_driver = drivers.get("baseline")
        if ("baseline" in observed_variants) != (baseline_driver is not None):
            failures.append(issue(
                "eval-baseline-driver-inconsistent",
                label,
                "Baseline driver provenance must match baseline run presence.",
            ))
        skill_context = verified_model_contexts.get("skill")
        baseline_context = verified_model_contexts.get("baseline")
        if skill_context is not None and baseline_context is not None:
            comparison_fields = (
                "declaration_status",
                "provider",
                "model",
                "model_version",
                "reasoning_effort",
                "generation_config",
            )
            if any(
                skill_context.get(field) != baseline_context.get(field)
                for field in comparison_fields
            ):
                failures.append(issue(
                    "eval-model-context-comparison-mismatch",
                    label,
                    (
                        "Skill and baseline runs must use the same declared model "
                        "context; only declaration_source and its derived hash may "
                        "differ."
                    ),
                ))

    summary = payload.get("summary")
    if isinstance(summary, dict):
        expected_summary = {
            "total": len(runs),
            "passed": summary_counts["passed"],
            "failed": summary_counts["failed"],
        }
        for field, expected in expected_summary.items():
            if summary.get(field) != expected:
                failures.append(issue(
                    "eval-summary-inconsistent",
                    label,
                    f"summary.{field}={summary.get(field)!r}; expected {expected}.",
                ))
        by_variant = summary.get("by_variant")
        expected_variants: dict[str, dict[str, int]] = {}
        for variant in sorted(observed_variants):
            selected = [
                run
                for run in runs
                if isinstance(run, dict) and run.get("variant") == variant
            ]
            variant_passed = sum(run.get("passed") is True for run in selected)
            expected_variants[variant] = {
                "total": len(selected),
                "passed": variant_passed,
                "failed": len(selected) - variant_passed,
            }
        if by_variant != expected_variants:
            failures.append(issue(
                "eval-variant-summary-inconsistent",
                label,
                f"{by_variant!r} != {expected_variants!r}",
            ))

    return failures


def eval_replay_failures(
    eval_payloads: list[tuple[Path, dict[str, object]]],
) -> list[dict[str, str]]:
    """Reject challenge material reused by different retained result files."""
    failures: list[dict[str, str]] = []
    seen: dict[tuple[str, str], str] = {}

    def register(
        kind: str,
        value: object,
        result_label: str,
        run_label: str,
        code: str,
    ) -> None:
        if not isinstance(value, str):
            return
        key = (kind, value.casefold())
        previous = seen.get(key)
        if previous is not None and previous != result_label:
            failures.append(issue(
                code,
                run_label,
                f"Replay detected across result files; first retained by {previous}.",
            ))
        else:
            seen[key] = result_label

    for result_path, payload in eval_payloads:
        result_label = str(result_path)
        register(
            "session_nonce",
            payload.get("session_nonce"),
            result_label,
            result_label,
            "eval-session-nonce-replayed",
        )
        runs = payload.get("runs")
        if not isinstance(runs, list):
            continue
        for index, run in enumerate(runs):
            if not isinstance(run, dict):
                continue
            run_label = f"{result_label}#runs/{index}"
            challenge = run.get("host_native_challenge")
            if isinstance(challenge, dict):
                register(
                    "challenge_id",
                    challenge.get("challenge_id"),
                    result_label,
                    run_label,
                    "eval-host-native-challenge-cross-result-replay",
                )
                register(
                    "run_nonce",
                    challenge.get("run_nonce"),
                    result_label,
                    run_label,
                    "eval-host-native-run-nonce-cross-result-replay",
                )
                register(
                    "challenge_sha256",
                    challenge.get("sha256"),
                    result_label,
                    run_label,
                    "eval-host-native-challenge-digest-cross-result-replay",
                )
            evidence = run.get("host_native_evidence")
            if isinstance(evidence, dict):
                register(
                    "evidence_sha256",
                    evidence.get("sha256"),
                    result_label,
                    run_label,
                    "eval-host-native-evidence-cross-result-replay",
                )
    return failures


def score_value(value: object) -> int | None:
    if not isinstance(value, dict):
        return None
    score = value.get("value")
    return score if isinstance(score, int) and not isinstance(score, bool) else None


REQUIRED_RUBRIC_BY_LENS = {
    "perception": {
        "project_specificity",
        "direction",
        "task_hierarchy",
        "contemporary_fit",
        "typography",
        "composition_density",
        "media_icons",
        "copy_ia",
        "distinctiveness_without_novelty_tax",
    },
    "implementation": {
        "functional_completeness",
        "responsive_adaptation",
        "accessibility_baseline",
        "truth_provenance",
        "system_code",
        "performance_resilience",
        "residue",
    },
}
GENERIC_REVIEW_IDENTITIES = {
    "agent",
    "ai",
    "assistant",
    "claude",
    "codex",
    "independent",
    "model",
    "review",
    "reviewer",
    "self",
    "unknown",
    "tbd",
}
GENERIC_OWNER_IDENTITIES = GENERIC_REVIEW_IDENTITIES | {
    "accountable-owner",
    "approver",
    "client",
    "client-owner",
    "decision-owner",
    "human",
    "owner",
    "stakeholder",
}
OWNER_DECISION_EVIDENCE_EXTENSIONS = {".json", ".log", ".md", ".txt"}
OWNER_DECISION_EVIDENCE_MAX_BYTES = 2 * 1024 * 1024
REQUIRED_IMPLEMENTATION_CHECKS = {
    "keyboard-navigation",
    "focus-visible",
    "screen-reader",
    "contrast",
    "reflow-zoom",
    "text-spacing",
    "reduced-motion",
    "forced-colors",
}


def verify_review_render_evidence(
    payload: dict[str, object],
    plugin: Path,
    label: str,
    evidence_keys: set[str],
    *,
    release_mode: bool,
) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    failures: list[dict[str, str]] = []
    verified: list[dict[str, object]] = []
    contexts = payload.get("contexts")
    if not isinstance(contexts, list):
        return failures, verified
    seen_paths: set[str] = set()
    for index, context in enumerate(contexts):
        context_label = f"{label}#contexts/{index}"
        if not isinstance(context, dict):
            continue
        render = context.get("render_evidence")
        if not isinstance(render, dict):
            if release_mode:
                failures.append(issue(
                    "release-render-context-unbound",
                    context_label,
                    "Every release context needs hash-bound PNG evidence.",
                ))
            continue
        relative = portable_relative(render.get("path"))
        if relative is None or relative.casefold() not in evidence_keys:
            failures.append(issue(
                "review-render-evidence-unbound",
                context_label,
                "render_evidence.path must be safe, present, and listed in evidence_paths.",
            ))
            continue
        path_key = relative.casefold()
        if path_key in seen_paths:
            failures.append(issue(
                "review-render-evidence-reused",
                context_label,
                "Each declared viewport needs its own rendered image.",
            ))
            continue
        seen_paths.add(path_key)
        candidate = absolute(plugin.joinpath(*relative.split("/")))
        if candidate.suffix.casefold() != ".png" or render.get("media_type") != "image/png":
            failures.append(issue(
                "review-render-format-invalid",
                context_label,
                "Release render evidence must be a PNG that the audit can decode.",
            ))
            continue
        try:
            width, height = verify_png(candidate)
            digest = file_sha256(candidate)
        except ToolFailure as exc:
            failures.append(issue(
                "review-render-image-invalid",
                context_label,
                str(exc),
            ))
            continue
        if render.get("sha256") != digest:
            failures.append(issue(
                "review-render-hash-mismatch",
                context_label,
                f"{relative} does not match its declared sha256.",
            ))
            continue
        if (
            render.get("pixel_width") != width
            or render.get("pixel_height") != height
        ):
            failures.append(issue(
                "review-render-dimensions-mismatch",
                context_label,
                f"Declared pixels do not match decoded {width}x{height}.",
            ))
            continue
        viewport = context.get("viewport")
        if not isinstance(viewport, dict):
            continue
        viewport_width = viewport.get("width")
        viewport_height = viewport.get("height")
        dpr = viewport.get("device_pixel_ratio")
        if (
            not isinstance(viewport_width, int)
            or isinstance(viewport_width, bool)
            or not isinstance(viewport_height, int)
            or isinstance(viewport_height, bool)
            or not isinstance(dpr, (int, float))
            or isinstance(dpr, bool)
            or dpr <= 0
        ):
            continue
        expected_width = round(viewport_width * dpr)
        minimum_height = round(viewport_height * dpr)
        if width != expected_width or height < minimum_height:
            failures.append(issue(
                "review-render-viewport-mismatch",
                context_label,
                (
                    f"Decoded {width}x{height} does not substantiate viewport "
                    f"{viewport_width}x{viewport_height} at DPR {dpr}."
                ),
            ))
            continue
        kind = (
            "mobile"
            if viewport_width <= 480
            else ("desktop" if viewport_width >= 1024 else "intermediate")
        )
        verified.append({
            "path": relative,
            "sha256": digest,
            "kind": kind,
            "viewport_width": viewport_width,
            "pixel_width": width,
            "pixel_height": height,
        })
    if release_mode and not verified:
        failures.append(issue(
            "release-rendered-evidence-missing",
            label,
            "Release review needs at least one decodable, hash-bound PNG context.",
        ))
    return failures, verified


def review_context_check_failures(
    payload: dict[str, object],
    plugin: Path,
    label: str,
    evidence_keys: set[str],
    *,
    release_mode: bool,
    qualified_reduced_contexts_out: set[int] | None = None,
) -> list[dict[str, str]]:
    """Bind each claimed check to hashed evidence and required test conditions."""
    failures: list[dict[str, str]] = []
    reviewer = payload.get("reviewer")
    lens = reviewer.get("lens") if isinstance(reviewer, dict) else None
    contexts = payload.get("contexts")
    if not isinstance(contexts, list):
        return failures
    qualified_implementation: set[str] = set()
    for context_index, context in enumerate(contexts):
        context_label = f"{label}#contexts/{context_index}"
        if not isinstance(context, dict):
            continue
        environment = context.get("environment")
        checks = context.get("checks")
        render = context.get("render_evidence")
        render_path = (
            portable_relative(render.get("path"))
            if isinstance(render, dict)
            else None
        )
        if not isinstance(checks, list):
            continue
        seen_ids: set[str] = set()
        visual_bound = False
        for check_index, check in enumerate(checks):
            check_label = f"{context_label}/checks/{check_index}"
            if not isinstance(check, dict):
                continue
            check_id = check.get("id")
            if not isinstance(check_id, str):
                continue
            if check_id in seen_ids:
                failures.append(issue(
                    "review-context-check-duplicate",
                    check_label,
                    f"Check {check_id!r} is duplicated in one context.",
                ))
            seen_ids.add(check_id)
            status = check.get("status")
            method = check.get("method")
            evidence = check.get("evidence")
            bound_paths: set[str] = set()
            structured_records = 0
            if isinstance(evidence, list):
                for evidence_index, evidence_record in enumerate(evidence):
                    evidence_label = f"{check_label}/evidence/{evidence_index}"
                    if not isinstance(evidence_record, dict):
                        continue
                    relative = portable_relative(evidence_record.get("path"))
                    if (
                        relative is None
                        or relative.casefold() not in evidence_keys
                    ):
                        failures.append(issue(
                            "review-check-evidence-unbound",
                            evidence_label,
                            (
                                "Check evidence must be safe, present, and listed "
                                "in the review evidence_paths."
                            ),
                        ))
                        continue
                    path_key = relative.casefold()
                    if path_key in bound_paths:
                        failures.append(issue(
                            "review-check-evidence-duplicate",
                            evidence_label,
                            "A check cannot cite the same evidence twice.",
                        ))
                        continue
                    bound_paths.add(path_key)
                    candidate = absolute(
                        plugin.joinpath(*relative.split("/"))
                    )
                    try:
                        digest = file_sha256(candidate)
                    except ToolFailure as exc:
                        failures.append(issue(
                            "review-check-evidence-invalid",
                            evidence_label,
                            str(exc),
                        ))
                        continue
                    if digest != evidence_record.get("sha256"):
                        failures.append(issue(
                            "review-check-evidence-hash-mismatch",
                            evidence_label,
                            f"{relative} does not match its declared sha256.",
                        ))
                        continue
                    if candidate.suffix.casefold() != ".json":
                        continue
                    try:
                        check_payload = load_json(candidate)
                    except ToolFailure as exc:
                        failures.append(issue(
                            "review-check-record-invalid",
                            evidence_label,
                            str(exc),
                        ))
                        continue
                    expected_keys = {
                        "schema_version",
                        "check_id",
                        "route",
                        "state",
                        "method",
                        "result",
                        "observed_at",
                        "executor_id",
                        "observations",
                    }
                    if (
                        not isinstance(check_payload, dict)
                        or set(check_payload) != expected_keys
                        or check_payload.get("schema_version") != 1
                        or check_payload.get("check_id") != check_id
                        or check_payload.get("route") != context.get("route")
                        or check_payload.get("state") != context.get("state")
                        or check_payload.get("method") != method
                        or check_payload.get("result") != status
                        or not isinstance(check_payload.get("executor_id"), str)
                        or check_payload["executor_id"].casefold()
                        in GENERIC_REVIEW_IDENTITIES
                        or not isinstance(check_payload.get("observations"), list)
                        or not check_payload["observations"]
                        or not all(
                            isinstance(value, str) and value.strip()
                            for value in check_payload["observations"]
                        )
                    ):
                        failures.append(issue(
                            "review-check-record-unattributed",
                            evidence_label,
                            (
                                "Structured check evidence must exactly identify "
                                "the context, method, result, executor, and observations."
                            ),
                        ))
                        continue
                    try:
                        observed = datetime.fromisoformat(
                            str(check_payload.get("observed_at")).replace(
                                "Z", "+00:00"
                            )
                        )
                        if observed.tzinfo is None:
                            raise ValueError("timezone missing")
                    except ValueError:
                        failures.append(issue(
                            "review-check-record-time-invalid",
                            evidence_label,
                            "observed_at must be a timezone-aware date-time.",
                        ))
                        continue
                    structured_records += 1

            if (
                check_id == "reduced-motion"
                and status == "passed"
                and structured_records
                and isinstance(environment, dict)
                and environment.get("reduced_motion") == "reduce"
                and qualified_reduced_contexts_out is not None
            ):
                qualified_reduced_contexts_out.add(context_index)
            if (
                check_id == "visual-layout"
                and status == "passed"
                and render_path is not None
                and render_path.casefold() in bound_paths
            ):
                visual_bound = True
            if (
                lens == "implementation"
                and check_id in REQUIRED_IMPLEMENTATION_CHECKS
                and status == "passed"
                and structured_records
            ):
                environment_matches = isinstance(environment, dict)
                if check_id in {"keyboard-navigation", "focus-visible"}:
                    environment_matches = (
                        environment_matches
                        and "keyboard" in environment.get("input_modalities", [])
                    )
                elif check_id == "screen-reader":
                    environment_matches = (
                        environment_matches
                        and "screen-reader"
                        in environment.get("input_modalities", [])
                    )
                elif check_id == "reflow-zoom":
                    environment_matches = (
                        environment_matches
                        and environment.get("zoom_percent", 0) >= 200
                        and environment.get("text_scale_percent", 0) >= 200
                    )
                elif check_id == "reduced-motion":
                    environment_matches = (
                        environment_matches
                        and environment.get("reduced_motion") == "reduce"
                    )
                elif check_id == "forced-colors":
                    environment_matches = (
                        environment_matches
                        and environment.get("forced_colors") == "active"
                    )
                if environment_matches:
                    qualified_implementation.add(check_id)
                elif release_mode:
                    failures.append(issue(
                        "release-check-environment-mismatch",
                        check_label,
                        (
                            f"{check_id} evidence was not captured under the "
                            "required input or display condition."
                        ),
                    ))
        if release_mode and lens == "perception" and not visual_bound:
            failures.append(issue(
                "release-visual-check-evidence-missing",
                context_label,
                (
                    "Each perception context needs a passed visual-layout check "
                    "bound to that context's rendered PNG."
                ),
            ))
    if release_mode and lens == "implementation":
        missing = sorted(
            REQUIRED_IMPLEMENTATION_CHECKS - qualified_implementation
        )
        if missing:
            failures.append(issue(
                "release-accessibility-evidence-incomplete",
                label,
                (
                    "Implementation accessibility scores need passed, hashed, "
                    "structured check evidence for: " + ", ".join(missing)
                ),
            ))
    return failures


TEMPORAL_MEDIA_SUFFIXES = {
    "video/webm": {".webm"},
    "video/mp4": {".mp4"},
    "application/json": {".json"},
}


def motion_context_key(
    context: dict[str, object],
) -> tuple[str, str, int, int, float] | None:
    """Return the route/state/viewport identity used for matched motion runs."""
    route = context.get("route")
    state = context.get("state")
    viewport = context.get("viewport")
    if (
        not isinstance(route, str)
        or not isinstance(state, str)
        or not isinstance(viewport, dict)
    ):
        return None
    width = viewport.get("width")
    height = viewport.get("height")
    dpr = viewport.get("device_pixel_ratio")
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or not isinstance(height, int)
        or isinstance(height, bool)
        or not isinstance(dpr, (int, float))
        or isinstance(dpr, bool)
        or not math.isfinite(float(dpr))
        or dpr <= 0
    ):
        return None
    return route, state, width, height, float(dpr)


def review_temporal_evidence_failures(
    payload: dict[str, object],
    plugin: Path,
    label: str,
    evidence_keys: set[str],
    *,
    release_mode: bool,
    qualified_reduced_contexts: set[int],
) -> list[dict[str, str]]:
    """Validate temporal records and the matched significant-motion contract."""
    failures: list[dict[str, str]] = []
    contexts = payload.get("contexts")
    if not isinstance(contexts, list):
        contexts = []
    seen_paths: dict[str, str] = {}
    valid_contexts: dict[int, tuple[str, str, int, int, float]] = {}
    now = datetime.now(timezone.utc)

    for index, context in enumerate(contexts):
        context_label = f"{label}#contexts/{index}"
        if not isinstance(context, dict):
            continue
        temporal = context.get("temporal_evidence")
        if temporal is None:
            continue
        if not isinstance(temporal, dict):
            failures.append(issue(
                "review-temporal-evidence-invalid",
                context_label,
                "temporal_evidence must be an object.",
            ))
            continue

        record_valid = True
        relative = portable_relative(temporal.get("path"))
        if relative is None or relative.casefold() not in evidence_keys:
            failures.append(issue(
                "review-temporal-evidence-unbound",
                context_label,
                (
                    "temporal_evidence.path must be safe, present, and listed "
                    "in evidence_paths."
                ),
            ))
            record_valid = False
        else:
            path_key = relative.casefold()
            if path_key in seen_paths:
                failures.append(issue(
                    "review-temporal-evidence-reused",
                    context_label,
                    (
                        f"{relative!r} is already bound to "
                        f"{seen_paths[path_key]}; matched motion contexts need "
                        "distinct recordings or traces."
                    ),
                ))
                record_valid = False
            else:
                seen_paths[path_key] = context_label

            media_type = temporal.get("media_type")
            suffixes = TEMPORAL_MEDIA_SUFFIXES.get(str(media_type))
            if (
                suffixes is None
                or PurePosixPath(relative).suffix.casefold() not in suffixes
            ):
                failures.append(issue(
                    "review-temporal-format-invalid",
                    context_label,
                    (
                        "Temporal evidence extension must match its declared "
                        "video/webm, video/mp4, or application/json media type."
                    ),
                ))
                record_valid = False

            candidate = absolute(plugin.joinpath(*relative.split("/")))
            try:
                digest = file_sha256(candidate)
            except ToolFailure as exc:
                failures.append(issue(
                    "review-temporal-evidence-invalid",
                    context_label,
                    str(exc),
                ))
                record_valid = False
            else:
                if digest != temporal.get("sha256"):
                    failures.append(issue(
                        "review-temporal-hash-mismatch",
                        context_label,
                        f"{relative} does not match its declared sha256.",
                    ))
                    record_valid = False

        try:
            captured = aware_timestamp(temporal.get("captured_at"))
        except (TypeError, ValueError):
            failures.append(issue(
                "review-temporal-time-invalid",
                context_label,
                "captured_at must be a timezone-aware date-time.",
            ))
            record_valid = False
        else:
            if captured > now + REVIEW_EVIDENCE_CLOCK_SKEW:
                failures.append(issue(
                    "review-temporal-evidence-future",
                    context_label,
                    "captured_at is implausibly far in the future.",
                ))
                record_valid = False

        context_key = motion_context_key(context)
        if record_valid and context_key is not None:
            valid_contexts[index] = context_key

    motion = payload.get("motion_assessment")
    if release_mode and not isinstance(motion, dict):
        failures.append(issue(
            "release-motion-assessment-missing",
            label,
            (
                "Release review must explicitly classify motion as none, "
                "minor, or significant; omission cannot stand in for none."
            ),
        ))
        return failures
    classification = (
        motion.get("classification")
        if isinstance(motion, dict)
        else None
    )
    if not release_mode or classification != "significant":
        return failures

    normal_by_key: dict[
        tuple[str, str, int, int, float], list[int]
    ] = defaultdict(list)
    reduced_by_key: dict[
        tuple[str, str, int, int, float], list[int]
    ] = defaultdict(list)
    for index, key in valid_contexts.items():
        context = contexts[index]
        if not isinstance(context, dict):
            continue
        environment = context.get("environment")
        reduced_motion = (
            environment.get("reduced_motion")
            if isinstance(environment, dict)
            else None
        )
        if reduced_motion == "no-preference":
            normal_by_key[key].append(index)
        elif reduced_motion == "reduce":
            reduced_by_key[key].append(index)

    if not normal_by_key:
        failures.append(issue(
            "release-significant-motion-normal-evidence-missing",
            label,
            (
                "Significant motion needs hash-bound temporal evidence from a "
                "normal-motion context."
            ),
        ))
    if not reduced_by_key:
        failures.append(issue(
            "release-significant-motion-reduced-evidence-missing",
            label,
            (
                "Significant motion needs hash-bound temporal evidence from a "
                "reduced-motion context."
            ),
        ))
    matched_keys = set(normal_by_key) & set(reduced_by_key)
    if normal_by_key and reduced_by_key and not matched_keys:
        failures.append(issue(
            "release-significant-motion-context-unmatched",
            label,
            (
                "Normal-motion and reduced-motion temporal evidence must use "
                "the same route, state, and viewport."
            ),
        ))
    if matched_keys and not any(
        reduced_index in qualified_reduced_contexts
        for key in matched_keys
        for reduced_index in reduced_by_key[key]
    ):
        failures.append(issue(
            "release-significant-motion-reduced-check-missing",
            label,
            (
                "A matched reduced-motion context needs a passed, hash-bound "
                "structured reduced-motion check."
            ),
        ))
    return failures


def review_evidence_reference_failures(
    values: object,
    plugin: Path,
    label: str,
    evidence_keys: set[str],
    *,
    code_prefix: str = "review-closure-evidence",
) -> list[dict[str, str]]:
    """Verify that review evidence references are listed, present, and hash-bound."""
    failures: list[dict[str, str]] = []
    if not isinstance(values, list):
        return failures
    seen: set[str] = set()
    for index, record in enumerate(values):
        record_label = f"{label}/{index}"
        if not isinstance(record, dict):
            continue
        relative = portable_relative(record.get("path"))
        if relative is None or relative.casefold() not in evidence_keys:
            failures.append(issue(
                f"{code_prefix}-unbound",
                record_label,
                (
                    "Review evidence must be safe, present, and listed in "
                    "the review evidence_paths."
                ),
            ))
            continue
        key = relative.casefold()
        if key in seen:
            failures.append(issue(
                f"{code_prefix}-duplicate",
                record_label,
                "A review record cannot cite the same evidence twice.",
            ))
            continue
        seen.add(key)
        candidate = absolute(plugin.joinpath(*relative.split("/")))
        try:
            digest = file_sha256(candidate)
        except ToolFailure as exc:
            failures.append(issue(
                f"{code_prefix}-invalid",
                record_label,
                str(exc),
            ))
            continue
        if digest != record.get("sha256"):
            failures.append(issue(
                f"{code_prefix}-hash-mismatch",
                record_label,
                f"{relative} does not match its declared sha256.",
            ))
    return failures


GENERATED_IMAGE_SUFFIXES = {".avif", ".jpeg", ".jpg", ".png", ".webp"}


def review_capability_disposition_failures(
    payload: dict[str, object],
    plugin: Path,
    label: str,
    evidence_keys: set[str],
) -> list[dict[str, str]]:
    """Hash-bind image-generation availability, artifacts, and inspection."""
    disposition = payload.get("capability_disposition")
    if not isinstance(disposition, dict):
        return []
    image_generation = disposition.get("image_generation")
    if not isinstance(image_generation, dict):
        return []
    failures: list[dict[str, str]] = []
    for field in (
        "availability_evidence",
        "generated_artifacts",
        "inspection_evidence",
    ):
        failures.extend(review_evidence_reference_failures(
            image_generation.get(field),
            plugin,
            f"{label}#capability_disposition/image_generation/{field}",
            evidence_keys,
            code_prefix=f"review-image-generation-{field.replace('_', '-')}",
        ))
    if image_generation.get("status") == "available":
        artifacts = image_generation.get("generated_artifacts")
        if isinstance(artifacts, list):
            for index, record in enumerate(artifacts):
                relative = (
                    portable_relative(record.get("path"))
                    if isinstance(record, dict)
                    else None
                )
                if (
                    relative is not None
                    and PurePosixPath(relative).suffix.casefold()
                    not in GENERATED_IMAGE_SUFFIXES
                ):
                    failures.append(issue(
                        "review-generated-media-artifact-format-invalid",
                        (
                            f"{label}#capability_disposition/image_generation/"
                            f"generated_artifacts/{index}"
                        ),
                        (
                            "Generated artifact evidence must reference a local "
                            "PNG, JPEG, WebP, or AVIF image file."
                        ),
                    ))
    return failures


def review_owner_disposition_failures(
    payload: dict[str, object],
    plugin: Path,
    label: str,
    evidence_keys: set[str],
    *,
    release_mode: bool,
) -> list[dict[str, str]]:
    """Validate the accountable owner's decision against the exact reviewed build."""
    failures: list[dict[str, str]] = []
    disposition = payload.get("owner_disposition")
    if not isinstance(disposition, dict):
        if release_mode:
            failures.append(issue(
                "release-owner-disposition-missing",
                label,
                (
                    "Release reviews require a structured owner_disposition "
                    "for the exact candidate build."
                ),
            ))
        return failures

    owner_id = disposition.get("decision_owner_id")
    if (
        not isinstance(owner_id, str)
        or owner_id.casefold() in GENERIC_OWNER_IDENTITIES
    ):
        failures.append(issue(
            "review-owner-identity-invalid",
            f"{label}#owner_disposition/decision_owner_id",
            "Use the stable identity of the accountable decision owner.",
        ))

    build = payload.get("build")
    build_identity = build.get("identity") if isinstance(build, dict) else None
    if (
        not isinstance(build_identity, str)
        or disposition.get("candidate_id") != build_identity
    ):
        failures.append(issue(
            "review-owner-candidate-mismatch",
            f"{label}#owner_disposition/candidate_id",
            (
                "owner_disposition.candidate_id must equal build.identity so "
                "the decision cannot float to a different build."
            ),
        ))

    status = disposition.get("status")
    claim_scope = disposition.get("claim_scope")
    evidence = disposition.get("evidence")
    decision_statuses = {"accepted", "rejected", "not-required"}
    if status in decision_statuses and (
        not isinstance(evidence, list) or not evidence
    ):
        failures.append(issue(
            "review-owner-evidence-missing",
            f"{label}#owner_disposition/evidence",
            (
                "Accepted, rejected, and not-required owner decisions require "
                "hash-bound decision evidence."
            ),
        ))
    failures.extend(review_evidence_reference_failures(
        evidence,
        plugin,
        f"{label}#owner_disposition/evidence",
        evidence_keys,
        code_prefix="review-owner-evidence",
    ))
    if status in decision_statuses and isinstance(evidence, list):
        required_evidence_tokens = {
            "status": status,
            "decision_owner_id": owner_id,
            "candidate_id": disposition.get("candidate_id"),
            "reviewed_at": disposition.get("reviewed_at"),
        }
        for index, evidence_record in enumerate(evidence):
            evidence_label = f"{label}#owner_disposition/evidence/{index}"
            if not isinstance(evidence_record, dict):
                continue
            relative = portable_relative(evidence_record.get("path"))
            if (
                relative is None
                or relative.casefold() not in evidence_keys
            ):
                continue
            candidate = absolute(plugin.joinpath(*relative.split("/")))
            if (
                candidate.suffix.casefold()
                not in OWNER_DECISION_EVIDENCE_EXTENSIONS
            ):
                failures.append(issue(
                    "review-owner-evidence-format-invalid",
                    evidence_label,
                    (
                        "Owner decision evidence must be UTF-8 JSON, Markdown, "
                        "text, or log content that attributes the decision."
                    ),
                ))
                continue
            try:
                before = candidate.stat()
                if (
                    not candidate.is_file()
                    or before.st_size < 1
                    or before.st_size > OWNER_DECISION_EVIDENCE_MAX_BYTES
                ):
                    raise OSError(
                        "owner decision evidence must contain 1 byte through "
                        f"{OWNER_DECISION_EVIDENCE_MAX_BYTES} bytes"
                    )
                evidence_bytes = candidate.read_bytes()
                after = candidate.stat()
                if (
                    before.st_dev != after.st_dev
                    or before.st_ino != after.st_ino
                    or before.st_size != after.st_size
                    or before.st_mtime_ns != after.st_mtime_ns
                    or len(evidence_bytes) != before.st_size
                ):
                    raise OSError(
                        "owner decision evidence changed while it was read"
                    )
                if (
                    hashlib.sha256(evidence_bytes).hexdigest()
                    != evidence_record.get("sha256")
                ):
                    raise OSError(
                        "owner decision evidence no longer matches its "
                        "declared sha256"
                    )
                evidence_text = evidence_bytes.decode("utf-8")
            except (OSError, UnicodeError) as exc:
                failures.append(issue(
                    "review-owner-evidence-content-invalid",
                    evidence_label,
                    str(exc),
                ))
                continue
            normalized_evidence = evidence_text.casefold()
            missing_tokens = sorted(
                field
                for field, value in required_evidence_tokens.items()
                if (
                    not isinstance(value, str)
                    or value.casefold() not in normalized_evidence
                )
            )
            if missing_tokens:
                failures.append(issue(
                    "review-owner-evidence-unattributed",
                    evidence_label,
                    (
                        "Owner decision evidence must name the exact "
                        + ", ".join(missing_tokens)
                        + "."
                    ),
                ))

    reviewed_at_value = disposition.get("reviewed_at")
    if status in decision_statuses:
        try:
            reviewed_at = aware_timestamp(reviewed_at_value)
            captured_at = (
                aware_timestamp(build.get("captured_at"))
                if isinstance(build, dict)
                else None
            )
            if captured_at is None:
                raise ValueError("build.captured_at is missing")
        except ValueError as exc:
            failures.append(issue(
                "review-owner-time-invalid",
                f"{label}#owner_disposition/reviewed_at",
                str(exc),
            ))
        else:
            if reviewed_at < captured_at:
                failures.append(issue(
                    "review-owner-review-before-build",
                    f"{label}#owner_disposition/reviewed_at",
                    (
                        "The owner decision cannot predate the exact reviewed "
                        "build's captured_at timestamp."
                    ),
                ))
            if (
                reviewed_at
                > datetime.now(timezone.utc) + REVIEW_EVIDENCE_CLOCK_SKEW
            ):
                failures.append(issue(
                    "review-owner-review-in-future",
                    f"{label}#owner_disposition/reviewed_at",
                    "The owner decision timestamp is in the future.",
                ))

    conclusion = payload.get("conclusion")
    decision = (
        conclusion.get("decision")
        if isinstance(conclusion, dict)
        else None
    )
    if status == "rejected" and decision not in {"revise", "block"}:
        failures.append(issue(
            "review-owner-rejection-false-pass",
            label,
            (
                "An owner rejection forces revise or block; it can never be "
                "reported as pass or pass-with-limitations."
            ),
        ))
    if (
        release_mode
        and status == "not-required"
        and claim_scope != "standard"
    ):
        failures.append(issue(
            "release-owner-not-required-ineligible",
            label,
            (
                "not-required is allowed only for a declared standard claim "
                "scope; premium, showcase, sale-readiness, and owner-sensitive "
                "visual claims require accountable human acceptance."
            ),
        ))
    if release_mode and status == "pending":
        failures.append(issue(
            "release-owner-disposition-pending",
            label,
            (
                "A pending owner decision cannot close a release review; "
                "record accepted, rejected, or an accountable not-required "
                "decision."
            ),
        ))
    return failures


def review_semantic_failures(
    payload: object,
    plugin: Path,
    label: str,
    *,
    release_mode: bool,
    verified_contexts_out: list[dict[str, object]] | None = None,
) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    if not isinstance(payload, dict):
        return [issue("design-review-not-object", label, "Review must be an object.")]
    if release_mode and payload.get("schema_version") != 3:
        failures.append(issue(
            "release-review-schema-outdated",
            label,
            (
                "Release reviews must use schema_version 3 so every finding "
                "has an explicit resolution and verification lifecycle."
            ),
        ))
    evidence_failures, evidence_keys = validate_evidence_paths(
        payload.get("evidence_paths"),
        plugin,
        label,
    )
    failures.extend(evidence_failures)
    rubric_records = payload.get("rubric")
    if isinstance(rubric_records, dict):
        for dimension, score_record in rubric_records.items():
            if not isinstance(score_record, dict):
                continue
            failures.extend(review_evidence_reference_failures(
                score_record.get("evidence"),
                plugin,
                f"{label}#rubric/{dimension}/evidence",
                evidence_keys,
            ))
    failures.extend(review_owner_disposition_failures(
        payload,
        plugin,
        label,
        evidence_keys,
        release_mode=release_mode,
    ))
    failures.extend(review_capability_disposition_failures(
        payload,
        plugin,
        label,
        evidence_keys,
    ))
    review_relative = portable_relative(label)
    if (
        review_relative is not None
        and review_relative.casefold() in evidence_keys
    ):
        failures.append(issue(
            "review-self-evidence",
            label,
            "A review cannot use its own JSON record as rendered evidence.",
        ))
    render_failures, verified_contexts = verify_review_render_evidence(
        payload,
        plugin,
        label,
        evidence_keys,
        release_mode=release_mode,
    )
    failures.extend(render_failures)
    qualified_reduced_contexts: set[int] = set()
    failures.extend(review_context_check_failures(
        payload,
        plugin,
        label,
        evidence_keys,
        release_mode=release_mode,
        qualified_reduced_contexts_out=qualified_reduced_contexts,
    ))
    failures.extend(review_temporal_evidence_failures(
        payload,
        plugin,
        label,
        evidence_keys,
        release_mode=release_mode,
        qualified_reduced_contexts=qualified_reduced_contexts,
    ))
    if verified_contexts_out is not None:
        verified_contexts_out.extend(verified_contexts)
    reviewer = payload.get("reviewer")
    build = payload.get("build")
    if isinstance(reviewer, dict):
        reviewer_id = reviewer.get("id")
        process = reviewer.get("process")
        if (
            not isinstance(reviewer_id, str)
            or reviewer_id.casefold() in GENERIC_REVIEW_IDENTITIES
        ):
            failures.append(issue(
                "reviewer-identity-invalid",
                label,
                "Use a stable, non-generic reviewer identity.",
            ))
        if (
            reviewer.get("independent") is True
            and isinstance(build, dict)
            and reviewer_id == build.get("producer_id")
        ):
            failures.append(issue(
                "review-independence-conflict",
                label,
                "The declared independent reviewer is also the recorded build producer.",
            ))
        if isinstance(process, dict):
            process_id = process.get("id")
            process_path = portable_relative(process.get("evidence_path"))
            if (
                not isinstance(process_id, str)
                or process_id.casefold() in GENERIC_REVIEW_IDENTITIES
            ):
                failures.append(issue(
                    "review-process-identity-invalid",
                    label,
                    "Use a stable, non-generic review-process identity.",
                ))
            if (
                process_path is None
                or process_path.casefold() not in evidence_keys
            ):
                failures.append(issue(
                    "review-process-evidence-unbound",
                    label,
                    "Review process evidence must be safe, present, and listed.",
                ))
            elif PurePosixPath(process_path).suffix.casefold() not in {
                ".json",
                ".md",
                ".txt",
                ".log",
            }:
                failures.append(issue(
                    "review-process-evidence-format-invalid",
                    label,
                    "Review process evidence must be a JSON, Markdown, text, or log record.",
                ))
            else:
                process_file = absolute(
                    plugin.joinpath(*process_path.split("/"))
                )
                try:
                    if process_file.stat().st_size > 2 * 1024 * 1024:
                        raise OSError("process evidence exceeds 2 MiB")
                    process_text = process_file.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    failures.append(issue(
                        "review-process-evidence-invalid",
                        label,
                        str(exc),
                    ))
                else:
                    required_tokens = [
                        str(reviewer_id),
                        str(process_id),
                        str(process.get("method")),
                    ]
                    if not process_text.strip() or any(
                        token not in process_text for token in required_tokens
                    ):
                        failures.append(issue(
                            "review-process-evidence-unattributed",
                            label,
                            "Process evidence must name the reviewer, process, and method.",
                        ))
        elif release_mode:
            failures.append(issue(
                "review-process-missing",
                label,
                "Release reviews require attributable process metadata.",
            ))
    findings = payload.get("findings")
    unresolved_severities: list[str] = []
    unresolved_statuses: list[str] = []
    finding_ids: set[str] = set()
    if isinstance(findings, list):
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                continue
            finding_label = f"{label}#findings/{index}"
            finding_id = finding.get("id")
            if isinstance(finding_id, str):
                if finding_id in finding_ids:
                    failures.append(issue(
                        "review-finding-id-duplicate",
                        finding_label,
                        f"Finding ID {finding_id!r} is duplicated.",
                    ))
                finding_ids.add(finding_id)
            status = finding.get("status")
            if not isinstance(status, str):
                status = "open"
            severity = finding.get("severity")
            if (
                isinstance(severity, str)
                and status not in {"verified", "not-applicable"}
            ):
                unresolved_severities.append(severity)
                unresolved_statuses.append(status)
            finding_path = finding.get("evidence_path")
            if finding_path is None:
                if release_mode:
                    failures.append(issue(
                        "release-finding-evidence-missing",
                        finding_label,
                        "Release findings require an evidence_path.",
                    ))
            else:
                relative = portable_relative(finding_path)
                if relative is None or relative.casefold() not in evidence_keys:
                    failures.append(issue(
                        "review-finding-evidence-unbound",
                        finding_label,
                        (
                            "Finding evidence_path must be safe, present, and "
                            "listed in evidence_paths."
                        ),
                    ))
            for lifecycle_field in ("resolution", "verification"):
                lifecycle = finding.get(lifecycle_field)
                if isinstance(lifecycle, dict):
                    failures.extend(review_evidence_reference_failures(
                        lifecycle.get("evidence"),
                        plugin,
                        f"{finding_label}/{lifecycle_field}/evidence",
                        evidence_keys,
                    ))

    closure = payload.get("requirement_closure")
    closure_blocked = False
    if isinstance(closure, dict):
        closure_requirements = closure.get("requirements")
        seen_requirement_ids: set[str] = set()
        if isinstance(closure_requirements, list):
            for index, record in enumerate(closure_requirements):
                closure_label = f"{label}#requirement_closure/requirements/{index}"
                if not isinstance(record, dict):
                    continue
                requirement_id = record.get("id")
                if isinstance(requirement_id, str):
                    if requirement_id in seen_requirement_ids:
                        failures.append(issue(
                            "review-requirement-closure-duplicate",
                            closure_label,
                            f"Requirement {requirement_id!r} is closed more than once.",
                        ))
                    seen_requirement_ids.add(requirement_id)
                if record.get("status") == "blocked":
                    closure_blocked = True
                referenced_findings = record.get("finding_ids")
                if isinstance(referenced_findings, list):
                    unknown_findings = sorted(
                        str(value)
                        for value in referenced_findings
                        if value not in finding_ids
                    )
                    if unknown_findings:
                        failures.append(issue(
                            "review-requirement-finding-unbound",
                            closure_label,
                            (
                                "Requirement closure cites unknown finding IDs: "
                                + ", ".join(unknown_findings)
                            ),
                        ))
                failures.extend(review_evidence_reference_failures(
                    record.get("evidence"),
                    plugin,
                    f"{closure_label}/evidence",
                    evidence_keys,
                ))
    comparison = payload.get("comparative_analysis")
    if isinstance(comparison, dict):
        failures.extend(review_evidence_reference_failures(
            comparison.get("evidence"),
            plugin,
            f"{label}#comparative_analysis/evidence",
            evidence_keys,
        ))
        criteria = comparison.get("criteria")
        if isinstance(criteria, list):
            for index, record in enumerate(criteria):
                if not isinstance(record, dict):
                    continue
                failures.extend(review_evidence_reference_failures(
                    record.get("evidence"),
                    plugin,
                    (
                        f"{label}#comparative_analysis/criteria/"
                        f"{index}/evidence"
                    ),
                    evidence_keys,
                ))
        convergence = comparison.get("convergence")
        observations = (
            convergence.get("run_observations")
            if isinstance(convergence, dict)
            else None
        )
        if isinstance(observations, list):
            for index, record in enumerate(observations):
                if not isinstance(record, dict):
                    continue
                observation_label = (
                    f"{label}#comparative_analysis/convergence/"
                    f"run_observations/{index}"
                )
                references = record.get("evidence")
                failures.extend(review_evidence_reference_failures(
                    references,
                    plugin,
                    f"{observation_label}/evidence",
                    evidence_keys,
                ))
                if record.get("basis") != "rendered":
                    continue
                if not isinstance(references, list):
                    continue
                for evidence_index, evidence_record in enumerate(references):
                    if not isinstance(evidence_record, dict):
                        continue
                    relative = portable_relative(evidence_record.get("path"))
                    if (
                        relative is None
                        or relative.casefold() not in evidence_keys
                    ):
                        continue
                    evidence_label = (
                        f"{observation_label}/evidence/{evidence_index}"
                    )
                    candidate = absolute(
                        plugin.joinpath(*relative.split("/"))
                    )
                    if candidate.suffix.casefold() != ".png":
                        failures.append(issue(
                            "release-comparison-render-format-invalid",
                            evidence_label,
                            (
                                "A rendered run observation must cite a "
                                "decodable PNG; use source-only for nonvisual "
                                "evidence."
                            ),
                        ))
                        continue
                    try:
                        verify_png(candidate)
                    except ToolFailure as exc:
                        failures.append(issue(
                            "release-comparison-render-invalid",
                            evidence_label,
                            str(exc),
                        ))
    cross_case = payload.get("cross_case_analysis")
    if isinstance(cross_case, dict):
        failures.extend(review_evidence_reference_failures(
            cross_case.get("evidence"),
            plugin,
            f"{label}#cross_case_analysis/evidence",
            evidence_keys,
        ))
        blinded_comparison = cross_case.get("identity_blinded_comparison")
        if isinstance(blinded_comparison, dict):
            failures.extend(review_evidence_reference_failures(
                blinded_comparison.get("evidence"),
                plugin,
                (
                    f"{label}#cross_case_analysis/"
                    "identity_blinded_comparison/evidence"
                ),
                evidence_keys,
            ))
            for collection in ("coverage", "observations"):
                records = blinded_comparison.get(collection)
                if not isinstance(records, list):
                    continue
                for index, record in enumerate(records):
                    if not isinstance(record, dict):
                        continue
                    record_label = (
                        f"{label}#cross_case_analysis/"
                        "identity_blinded_comparison/"
                        f"{collection}/{index}"
                    )
                    failures.extend(review_evidence_reference_failures(
                        record.get("evidence"),
                        plugin,
                        f"{record_label}/evidence",
                        evidence_keys,
                    ))
                    if collection != "coverage":
                        continue
                    source_hashes = record.get("source_render_sha256s")
                    source_hash_set = (
                        set(source_hashes)
                        if isinstance(source_hashes, list)
                        else set()
                    )
                    references = record.get("evidence")
                    if not isinstance(references, list):
                        continue
                    for evidence_index, evidence_record in enumerate(references):
                        if (
                            not isinstance(evidence_record, dict)
                            or evidence_record.get("sha256") not in source_hash_set
                        ):
                            continue
                        relative = portable_relative(evidence_record.get("path"))
                        if (
                            relative is None
                            or relative.casefold() not in evidence_keys
                        ):
                            continue
                        evidence_label = (
                            f"{record_label}/evidence/{evidence_index}"
                        )
                        candidate = absolute(
                            plugin.joinpath(*relative.split("/"))
                        )
                        if candidate.suffix.casefold() != ".png":
                            failures.append(issue(
                                "release-cross-case-source-render-format-invalid",
                                evidence_label,
                                (
                                    "An identity-blinded comparison source "
                                    "render must cite a "
                                    "decodable PNG."
                                ),
                            ))
                            continue
                        try:
                            verify_png(candidate)
                        except ToolFailure as exc:
                            failures.append(issue(
                                "release-cross-case-source-render-invalid",
                                evidence_label,
                                str(exc),
                            ))
            transformation = blinded_comparison.get("pixel_transformation")
            if isinstance(transformation, dict):
                authorization = transformation.get("authorization")
                if isinstance(authorization, dict):
                    failures.extend(review_evidence_reference_failures(
                        authorization.get("evidence"),
                        plugin,
                        (
                            f"{label}#cross_case_analysis/"
                            "identity_blinded_comparison/pixel_transformation/"
                            "authorization/evidence"
                        ),
                        evidence_keys,
                    ))
                artifacts = transformation.get("artifacts")
                if isinstance(artifacts, list):
                    for index, artifact in enumerate(artifacts):
                        if not isinstance(artifact, dict):
                            continue
                        artifact_label = (
                            f"{label}#cross_case_analysis/"
                            "identity_blinded_comparison/pixel_transformation/"
                            f"artifacts/{index}"
                        )
                        for evidence_field in (
                            "source_evidence",
                            "transformed_evidence",
                        ):
                            reference = artifact.get(evidence_field)
                            failures.extend(review_evidence_reference_failures(
                                [reference] if isinstance(reference, dict) else reference,
                                plugin,
                                f"{artifact_label}/{evidence_field}",
                                evidence_keys,
                            ))
                            if not isinstance(reference, dict):
                                continue
                            relative = portable_relative(reference.get("path"))
                            if (
                                relative is None
                                or relative.casefold() not in evidence_keys
                            ):
                                continue
                            candidate = absolute(
                                plugin.joinpath(*relative.split("/"))
                            )
                            if candidate.suffix.casefold() != ".png":
                                failures.append(issue(
                                    "release-cross-case-transformed-render-format-invalid",
                                    f"{artifact_label}/{evidence_field}",
                                    (
                                        "Pixel-transformation source and output "
                                        "artifacts must cite decodable PNGs."
                                    ),
                                ))
                                continue
                            try:
                                verify_png(candidate)
                            except ToolFailure as exc:
                                failures.append(issue(
                                    "release-cross-case-transformed-render-invalid",
                                    f"{artifact_label}/{evidence_field}",
                                    str(exc),
                                ))
        for collection in ("dimensions", "repeated_clusters"):
            records = cross_case.get(collection)
            if not isinstance(records, list):
                continue
            for index, record in enumerate(records):
                if not isinstance(record, dict):
                    continue
                failures.extend(review_evidence_reference_failures(
                    record.get("evidence"),
                    plugin,
                    (
                        f"{label}#cross_case_analysis/{collection}/"
                        f"{index}/evidence"
                    ),
                    evidence_keys,
                ))
                if collection == "repeated_clusters":
                    for lifecycle_field in ("resolution", "verification"):
                        lifecycle = record.get(lifecycle_field)
                        if not isinstance(lifecycle, dict):
                            continue
                        failures.extend(review_evidence_reference_failures(
                            lifecycle.get("evidence"),
                            plugin,
                            (
                                f"{label}#cross_case_analysis/"
                                f"{collection}/{index}/{lifecycle_field}/"
                                "evidence"
                            ),
                            evidence_keys,
                        ))
    rubric = payload.get("rubric")
    scores = (
        [score_value(value) for value in rubric.values()]
        if isinstance(rubric, dict)
        else []
    )
    numeric_scores = [value for value in scores if value is not None]
    blockers = payload.get("critical_blockers")
    blockers_present = isinstance(blockers, list) and bool(blockers)
    checks = payload.get("checks")
    unperformed = (
        checks.get("unperformed")
        if isinstance(checks, dict) and isinstance(checks.get("unperformed"), list)
        else []
    )
    conclusion = payload.get("conclusion")
    decision = conclusion.get("decision") if isinstance(conclusion, dict) else None
    limitations = (
        conclusion.get("limitations")
        if isinstance(conclusion, dict) and isinstance(conclusion.get("limitations"), list)
        else []
    )
    if (
        blockers_present
        or "critical" in unresolved_severities
        or closure_blocked
        or any(value == 0 for value in numeric_scores)
    ) and decision != "block":
        failures.append(issue(
            "review-false-pass",
            label,
            (
                "Critical blocker, unresolved critical finding, blocked review "
                "requirement, or score 0 requires a block conclusion."
            ),
        ))
    if (
        any(
            severity in {"high", "medium"}
            for severity in unresolved_severities
        )
        or any(
            status in {"open", "fixed-unverified", "deferred", "blocked"}
            for status in unresolved_statuses
        )
        or any(value == 1 for value in numeric_scores)
    ) and decision in {"pass", "pass-with-limitations"}:
        failures.append(issue(
            "review-false-pass",
            label,
            (
                "Unresolved medium/high findings, unverified or deferred work, "
                "and score 1 require revise or block."
            ),
        ))
    if decision == "pass" and unresolved_severities:
        failures.append(issue(
            "review-false-pass",
            label,
            (
                "A clean pass cannot retain unresolved low-severity or note "
                "findings; close them or use an explicit limitation."
            ),
        ))
    if decision == "pass" and unperformed:
        failures.append(issue(
            "review-unperformed-checks-undisclosed",
            label,
            "A pass with unperformed checks must be pass-with-limitations.",
        ))
    if decision == "pass-with-limitations" and not limitations:
        failures.append(issue(
            "review-limitations-missing",
            label,
            "pass-with-limitations requires explicit limitations.",
        ))
    if release_mode and isinstance(reviewer, dict) and isinstance(rubric, dict):
        lens = reviewer.get("lens")
        required_dimensions = REQUIRED_RUBRIC_BY_LENS.get(str(lens), set())
        missing_scores = sorted(
            dimension
            for dimension in required_dimensions
            if score_value(rubric.get(dimension)) is None
        )
        if missing_scores:
            failures.append(issue(
                "release-required-rubric-not-scored",
                label,
                (
                    f"{lens} review requires numeric scores for: "
                    + ", ".join(missing_scores)
                ),
            ))
    return failures


def review_evaluation_binding_failures(
    payload: dict[str, object],
    plugin: Path,
    label: str,
    eval_payloads: dict[Path, dict[str, object]],
    *,
    release_mode: bool,
) -> list[dict[str, str]]:
    """Bind a promoted review to one exact evaluated run and model context."""
    failures: list[dict[str, str]] = []
    binding = payload.get("evaluation_binding")
    if not isinstance(binding, dict):
        if release_mode:
            failures.append(issue(
                "release-review-evaluation-binding-missing",
                label,
                (
                    "A promoted review must bind the exact evaluation result, "
                    "run artifact, and declared model context."
                ),
            ))
        return failures

    relative = portable_relative(binding.get("result_path"))
    relative_path = PurePosixPath(relative) if relative is not None else None
    if (
        relative_path is None
        or relative_path.suffix.casefold() != ".json"
        or relative_path.parent.as_posix() != "maintainer/evals/results"
    ):
        return [issue(
            "review-evaluation-result-path-invalid",
            label,
            "evaluation_binding.result_path must name one retained result JSON.",
        )]
    result_path = absolute(plugin.joinpath(*relative_path.parts))
    if not is_within(result_path, plugin):
        return [issue(
            "review-evaluation-result-path-invalid",
            label,
            "The bound evaluation result must stay inside the package.",
        )]
    try:
        assert_no_reparse_path(result_path, stop=plugin)
        if not result_path.is_file():
            raise ToolFailure(
                "review-evaluation-result-missing",
                "The bound evaluation result is missing.",
                result_path,
            )
        result_digest = file_sha256(result_path)
    except (OSError, ToolFailure) as exc:
        return [issue(
            "review-evaluation-result-unavailable",
            label,
            str(exc),
        )]
    if binding.get("result_sha256") != result_digest:
        failures.append(issue(
            "review-evaluation-result-hash-mismatch",
            label,
            "evaluation_binding.result_sha256 does not match the result file.",
        ))

    result = eval_payloads.get(result_path)
    if not isinstance(result, dict):
        failures.append(issue(
            "review-evaluation-result-unregistered",
            label,
            "The bound result was not accepted into the current evaluation set.",
        ))
        return failures
    run_id = binding.get("run_id")
    matches = [
        run
        for run in result.get("runs", [])
        if isinstance(run, dict) and run.get("run_id") == run_id
    ] if isinstance(result.get("runs"), list) else []
    if len(matches) != 1:
        failures.append(issue(
            "review-evaluation-run-unresolved",
            label,
            "evaluation_binding.run_id must identify exactly one retained run.",
        ))
        return failures
    run = matches[0]
    if payload.get("run_id") != run_id or payload.get("case_id") != run.get("case"):
        failures.append(issue(
            "review-evaluation-run-identity-mismatch",
            label,
            "Review case_id and run_id must match the bound evaluation run.",
        ))
    if run.get("passed") is not True:
        failures.append(issue(
            "review-evaluation-run-not-passed",
            label,
            "A promoted review cannot bind a failed evaluation run.",
        ))
    artifact = run.get("artifact_bundle")
    if (
        not isinstance(artifact, dict)
        or binding.get("artifact_sha256") != artifact.get("sha256")
    ):
        failures.append(issue(
            "review-evaluation-artifact-mismatch",
            label,
            "evaluation_binding.artifact_sha256 must match the run bundle.",
        ))
    variant = run.get("variant")
    drivers = result.get("drivers")
    driver = (
        drivers.get(variant)
        if isinstance(drivers, dict) and isinstance(variant, str)
        else None
    )
    context = driver.get("model_context") if isinstance(driver, dict) else None
    if (
        not isinstance(context, dict)
        or binding.get("model_context_sha256") != context.get("sha256")
    ):
        failures.append(issue(
            "review-evaluation-model-context-mismatch",
            label,
            "The review must bind the selected run's exact model context.",
        ))
    if release_mode and (
        not isinstance(context, dict)
        or context.get("declaration_status") != "declared"
    ):
        failures.append(issue(
            "release-review-model-context-unreported",
            label,
            "A promoted review must bind declared model identity metadata.",
        ))
    build = payload.get("build")
    package = result.get("package")
    if isinstance(build, dict) and isinstance(package, dict):
        if (
            build.get("host") != result.get("host")
            or build.get("skill_version") != package.get("version")
            or build.get("content_sha256") != package.get("content_sha256")
        ):
            failures.append(issue(
                "review-evaluation-build-identity-mismatch",
                label,
                "Review build identity differs from the bound evaluation result.",
            ))
    return failures


def release_host_completion_failures(
    host_name: str,
    host: dict[str, object],
) -> list[dict[str, str]]:
    """Require every claimed host's release checks to be complete."""
    failures: list[dict[str, str]] = []
    checks = {
        "static_validation": "release-host-static-incomplete",
        "installed_sync": "release-host-sync-incomplete",
        "isolated_behavioral_eval": "release-host-eval-incomplete",
        "rendered_eval": "release-host-eval-incomplete",
    }
    for check, code in checks.items():
        status = host.get(check)
        if status == "passed":
            continue
        message = str(status)
        if check in {"isolated_behavioral_eval", "rendered_eval"}:
            message += (
                "; a release limitation cannot replace completed behavioral "
                "or rendered evidence."
            )
        failures.append(issue(
            code,
            f"maintainer/compatibility/matrix.yml:{host_name}.{check}",
            message,
        ))
    return failures


def release_host_discovery_failures(
    host_name: str,
    compatibility: dict[str, object],
) -> list[dict[str, str]]:
    """Require a host-native load observation, not merely an installed route."""
    environments = compatibility.get("environments")
    records = environments if isinstance(environments, list) else []
    matching = [
        record
        for record in records
        if (
            isinstance(record, dict)
            and record.get("scope") == "host_runtime"
            and record.get("host") == host_name
        )
    ]
    if any(
        isinstance(record.get("checks"), dict)
        and record["checks"].get("host_discovery") == "passed"
        for record in matching
    ):
        return []
    statuses = sorted({
        str(record.get("checks", {}).get("host_discovery"))
        for record in matching
        if isinstance(record.get("checks"), dict)
    })
    return [issue(
        "release-host-discovery-incomplete",
        f"maintainer/compatibility/matrix.yml:{host_name}.host_discovery",
        (
            "No host-runtime environment records a passed, evidence-bound "
            "skill load observation"
            + (f"; recorded statuses: {', '.join(statuses)}" if statuses else "")
            + "."
        ),
    )]


INDEPENDENT_REVIEW_METHODS = {
    "separate-person",
    "separate-agent",
    "blinded-panel",
    "independent-specialist",
}
MIN_RELEASE_REPRESENTATIVE_CASES = 4
MIN_RELEASE_REPETITIONS_PER_VARIANT = 3
MIN_EXPRESSIVE_RELEASE_CASES = 2
MIN_QUIET_RELEASE_CASES = 1
MIN_GENERATED_MEDIA_RELEASE_CASES = 1
MIN_ROUTE_FAMILY_RELEASE_CASES = 1
MIN_CULTURAL_CONTEXT_RELEASE_CASES = 1
REQUIRED_RELEASE_MODES = {"persuade", "experience", "operate", "read"}
EXPRESSIVE_PERCEPTION_FLOORS = {
    "direction": 3,
    "distinctiveness_without_novelty_tax": 3,
}
QUIET_PERCEPTION_FLOORS = {
    "direction": 3,
    "project_specificity": 3,
    "distinctiveness_without_novelty_tax": 3,
}


def expressive_perception_gate_failures(
    payload: dict[str, object],
    expected_contract: object,
    label: str,
) -> list[dict[str, str]]:
    """Apply the opt-in absolute quality floor to counted perception reviews."""
    if not isinstance(expected_contract, dict):
        return []
    coverage = expected_contract.get("release_coverage")
    reviewer = payload.get("reviewer")
    if not (
        isinstance(coverage, dict)
        and coverage.get("expressive_perception_gate") is True
        and isinstance(reviewer, dict)
        and reviewer.get("lens") == "perception"
    ):
        return []
    rubric = payload.get("rubric")
    failures: list[dict[str, str]] = []
    for dimension, minimum in EXPRESSIVE_PERCEPTION_FLOORS.items():
        observed = (
            score_value(rubric.get(dimension))
            if isinstance(rubric, dict)
            else None
        )
        if observed != minimum:
            failures.append(issue(
                "release-expressive-perception-floor-unmet",
                f"{label}:rubric.{dimension}",
                (
                    "A release-counted Showcase or expressive case requires "
                    f"a numeric {minimum} for {dimension}; observed "
                    f"{observed!r}. This opt-in gate does not apply to "
                    "unmarked cases."
                ),
            ))
    return failures


def quiet_perception_gate_failures(
    payload: dict[str, object],
    expected_contract: object,
    label: str,
) -> list[dict[str, str]]:
    """Apply a quiet-specific quality floor without requiring visual volume."""
    if not isinstance(expected_contract, dict):
        return []
    coverage = expected_contract.get("release_coverage")
    reviewer = payload.get("reviewer")
    if not (
        isinstance(coverage, dict)
        and coverage.get("quiet_perception_gate") is True
        and isinstance(reviewer, dict)
        and reviewer.get("lens") == "perception"
    ):
        return []
    rubric = payload.get("rubric")
    failures: list[dict[str, str]] = []
    for dimension, minimum in QUIET_PERCEPTION_FLOORS.items():
        observed = (
            score_value(rubric.get(dimension))
            if isinstance(rubric, dict)
            else None
        )
        if observed != minimum:
            failures.append(issue(
                "release-quiet-perception-floor-unmet",
                f"{label}:rubric.{dimension}",
                (
                    "A release-counted quiet-specific case requires "
                    f"a numeric {minimum} for {dimension}; observed "
                    f"{observed!r}. This is a specificity and direction floor, "
                    "not a requirement for louder styling."
                ),
            ))
    return failures


def image_generation_disposition_status(
    payload: dict[str, object],
) -> str | None:
    disposition = payload.get("capability_disposition")
    image_generation = (
        disposition.get("image_generation")
        if isinstance(disposition, dict)
        else None
    )
    status = (
        image_generation.get("status")
        if isinstance(image_generation, dict)
        else None
    )
    return status if status in {"available", "unavailable"} else None


def generated_media_capability_gate_failures(
    payload: dict[str, object],
    expected_contract: object,
    label: str,
) -> list[dict[str, str]]:
    """Require an honest capability branch on marked perception reviews."""
    if not isinstance(expected_contract, dict):
        return []
    coverage = expected_contract.get("release_coverage")
    reviewer = payload.get("reviewer")
    if not (
        isinstance(coverage, dict)
        and coverage.get("generated_media_capability_gate") is True
        and isinstance(reviewer, dict)
        and reviewer.get("lens") == "perception"
    ):
        return []
    disposition = payload.get("capability_disposition")
    image_generation = (
        disposition.get("image_generation")
        if isinstance(disposition, dict)
        else None
    )
    status = image_generation_disposition_status(payload)
    if not isinstance(image_generation, dict) or status is None:
        return [issue(
            "release-generated-media-capability-disposition-missing",
            label,
            (
                "A release-counted generated-media case must record image "
                "generation as available or unavailable with bound host "
                "evidence; absence cannot select the fallback branch."
            ),
        )]
    availability_evidence = image_generation.get("availability_evidence")
    generated_artifacts = image_generation.get("generated_artifacts")
    inspection_evidence = image_generation.get("inspection_evidence")
    failures: list[dict[str, str]] = []
    if not isinstance(availability_evidence, list) or not availability_evidence:
        failures.append(issue(
            "release-generated-media-capability-evidence-missing",
            label,
            "The image-generation availability disposition needs bound evidence.",
        ))
    if status == "available" and not (
        isinstance(generated_artifacts, list)
        and generated_artifacts
        and isinstance(inspection_evidence, list)
        and inspection_evidence
    ):
        failures.append(issue(
            "release-generated-media-artifact-evidence-missing",
            label,
            (
                "An available image-generation capability requires real "
                "generated artifact references and bound inspection evidence."
            ),
        ))
    if status == "unavailable" and (
        (isinstance(generated_artifacts, list) and generated_artifacts)
        or (isinstance(inspection_evidence, list) and inspection_evidence)
    ):
        failures.append(issue(
            "release-generated-media-unavailable-branch-contradiction",
            label,
            (
                "The unavailable branch cannot cite generated artifacts or "
                "claim generated-media inspection."
            ),
        ))
    return failures


def route_family_showcase_gate_failures(
    payload: dict[str, object],
    expected_contract: object,
    label: str,
) -> list[dict[str, str]]:
    """Require passing direct-route and rendered-family evidence when marked."""
    if not isinstance(expected_contract, dict):
        return []
    coverage = expected_contract.get("release_coverage")
    reviewer = payload.get("reviewer")
    if not (
        isinstance(coverage, dict)
        and coverage.get("route_family_showcase_gate") is True
        and isinstance(reviewer, dict)
        and reviewer.get("lens") == "perception"
    ):
        return []
    analysis = payload.get("route_family_analysis")
    if not isinstance(analysis, dict):
        return [issue(
            "release-route-family-analysis-missing",
            label,
            (
                "A release-counted Range Study requires structured "
                "route_family_analysis; a screenshot sample or machine "
                "similarity result alone cannot close this gate."
            ),
        )]
    failures: list[dict[str, str]] = []
    declared = analysis.get("declared_route_count")
    verified = analysis.get("verified_route_count")
    routes = analysis.get("routes")
    conclusion = analysis.get("conclusion")
    repeated = analysis.get("repeated_clusters")
    if not (
        isinstance(declared, int)
        and not isinstance(declared, bool)
        and declared >= 2
        and verified == declared
        and isinstance(routes, list)
        and len(routes) == declared
    ):
        failures.append(issue(
            "release-route-family-route-coverage-incomplete",
            label,
            (
                "Every declared route must be independently verified and "
                "represented exactly once in route_family_analysis.routes."
            ),
        ))
    elif any(
        not isinstance(route, dict)
        or route.get("direct_entry_status") != "passed"
        or route.get("capture_status") != "matched"
        for route in routes
    ):
        failures.append(issue(
            "release-route-family-route-evidence-incomplete",
            label,
            (
                "Every counted route must pass direct entry and have matched "
                "rendered capture coverage."
            ),
        ))
    unresolved_clusters = (
        [
            cluster
            for cluster in repeated
            if isinstance(cluster, dict)
            and cluster.get("status") == "unresolved"
        ]
        if isinstance(repeated, list)
        else [None]
    )
    if unresolved_clusters:
        failures.append(issue(
            "release-route-family-repeated-skeleton-unresolved",
            label,
            (
                "A release-counted Range Study cannot retain an unresolved "
                "repeated-skeleton cluster."
            ),
        ))
    if not (
        isinstance(conclusion, dict)
        and conclusion.get("unique_direct_routes") is True
        and conclusion.get("matched_capture_coverage") is True
        and conclusion.get("unresolved_repeated_skeleton") is False
        and conclusion.get("decision") == "pass"
    ):
        failures.append(issue(
            "release-route-family-conclusion-not-passing",
            label,
            (
                "The route-family conclusion must pass with unique direct "
                "routes, matched capture coverage, and no unresolved repeated "
                "skeleton."
            ),
        ))
    return failures


def cultural_context_gate_failures(
    payload: dict[str, object],
    expected_contract: object,
    label: str,
) -> list[dict[str, str]]:
    """Require accepted representation review by a named non-producer."""
    if not isinstance(expected_contract, dict):
        return []
    coverage = expected_contract.get("release_coverage")
    reviewer = payload.get("reviewer")
    if not (
        isinstance(coverage, dict)
        and coverage.get("cultural_context_gate") is True
        and isinstance(reviewer, dict)
        and reviewer.get("lens") == "perception"
    ):
        return []
    cultural = payload.get("cultural_context_review")
    if not isinstance(cultural, dict):
        return [issue(
            "release-cultural-context-review-missing",
            label,
            (
                "A release-counted culturally central case requires structured "
                "cultural_context_review from an accountable non-producer."
            ),
        )]
    authority = cultural.get("authority")
    failures: list[dict[str, str]] = []
    if cultural.get("status") != "accepted":
        failures.append(issue(
            "release-cultural-context-review-not-accepted",
            label,
            (
                "Pending or rejected cultural review blocks release counting; "
                "technical or producer self-review cannot substitute."
            ),
        ))
    if not (
        isinstance(authority, dict)
        and isinstance(authority.get("reviewer_id"), str)
        and authority["reviewer_id"].strip()
        and authority.get("relationship")
        in {
            "accountable-community-authority",
            "owner-authorized-cultural-reviewer",
        }
        and authority.get("independent_of_producer") is True
        and isinstance(authority.get("reviewed_at"), str)
        and authority["reviewed_at"].strip()
        and isinstance(authority.get("evidence"), list)
        and authority["evidence"]
    ):
        failures.append(issue(
            "release-cultural-context-authority-ineligible",
            label,
            (
                "Accepted cultural review requires a named, dated, "
                "evidence-bound authority who is independent of the producer."
            ),
        ))
    open_questions = cultural.get("open_questions")
    if not isinstance(open_questions, list) or open_questions:
        failures.append(issue(
            "release-cultural-context-open-questions",
            label,
            (
                "Accepted release evidence must close cultural-context open "
                "questions rather than carrying them into the release claim."
            ),
        ))
    return failures


def review_contract_closure_failures(
    payload: dict[str, object],
    expected_contract: object,
    label: str,
) -> tuple[list[dict[str, str]], bool]:
    """Verify that a review closes the exact run-bound requirement contract."""
    failures: list[dict[str, str]] = []
    closure = payload.get("requirement_closure")
    if not isinstance(expected_contract, dict):
        return failures, False
    expected_requirements = expected_contract.get("requirements")
    reviewer = payload.get("reviewer")
    is_perception = (
        isinstance(reviewer, dict)
        and reviewer.get("lens") == "perception"
    )
    failures.extend(
        expressive_perception_gate_failures(
            payload,
            expected_contract,
            label,
        )
    )
    failures.extend(
        quiet_perception_gate_failures(
            payload,
            expected_contract,
            label,
        )
    )
    failures.extend(
        generated_media_capability_gate_failures(
            payload,
            expected_contract,
            label,
        )
    )
    failures.extend(
        route_family_showcase_gate_failures(
            payload,
            expected_contract,
            label,
        )
    )
    failures.extend(
        cultural_context_gate_failures(
            payload,
            expected_contract,
            label,
        )
    )
    if (
        is_perception
        and isinstance(expected_requirements, list)
        and expected_requirements
        and not isinstance(closure, dict)
    ):
        failures.append(issue(
            "release-review-requirement-closure-missing",
            label,
            (
                "Perception review must close the exact run-bound review "
                "requirements; absence is not evidence of completion."
            ),
        ))
        return failures, False
    if not isinstance(closure, dict):
        return failures, False
    if closure.get("contract_sha256") != expected_contract.get("sha256"):
        failures.append(issue(
            "release-review-contract-unbound",
            label,
            "Requirement closure does not bind the exact run review contract.",
        ))
    expected_adversarial = bool(expected_contract.get("adversarial_required"))
    if closure.get("adversarial") is not expected_adversarial:
        failures.append(issue(
            "release-review-adversarial-state-mismatch",
            label,
            "Requirement closure adversarial state differs from the run contract.",
        ))
    expected_ids = (
        {
            item.get("id")
            for item in expected_requirements
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        if isinstance(expected_requirements, list)
        else set()
    )
    closure_requirements = closure.get("requirements")
    closure_ids = (
        [
            item.get("id")
            for item in closure_requirements
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        if isinstance(closure_requirements, list)
        else []
    )
    if (
        len(closure_ids) != len(set(closure_ids))
        or set(closure_ids) != expected_ids
    ):
        failures.append(issue(
            "release-review-requirement-coverage-incomplete",
            label,
            (
                "Requirement closure must cover every run-bound requirement "
                "exactly once and cannot add unrelated requirements."
            ),
        ))
    elif any(
        not isinstance(record, dict)
        or record.get("status") != "verified"
        for record in closure_requirements
    ) if isinstance(closure_requirements, list) else True:
        failures.append(issue(
            "release-review-requirement-unverified",
            label,
            (
                "Every release-counted review requirement must be verified; "
                "not-applicable, blocked, or unresolved records do not close it."
            ),
        ))
    all_closed = (
        bool(closure_ids)
        and isinstance(closure_requirements, list)
        and all(
            isinstance(record, dict)
            and record.get("status") == "verified"
            and isinstance(record.get("evidence"), list)
            and bool(record["evidence"])
            for record in closure_requirements
        )
    )
    conclusion = payload.get("conclusion")
    perception_pass = (
        isinstance(reviewer, dict)
        and reviewer.get("lens") == "perception"
        and isinstance(conclusion, dict)
        and conclusion.get("decision") in {"pass", "pass-with-limitations"}
    )
    qualified = not failures and all_closed and perception_pass
    return failures, qualified


def release_behavioral_coverage_failures(
    host_name: str,
    host_runs: list[tuple[Path, dict[str, object]]],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    """Require diverse, repeated, non-cherry-picked representative cases."""
    failures: list[dict[str, str]] = []
    label = f"maintainer/compatibility/matrix.yml:{host_name}"
    grouped: defaultdict[
        tuple[str, str],
        dict[str, dict[str, object]],
    ] = defaultdict(dict)
    contracts: dict[str, dict[str, object]] = {}
    for _path, run in host_runs:
        case_id = run.get("case")
        variant = run.get("variant")
        run_id = run.get("run_id")
        if not all(isinstance(value, str) for value in (case_id, variant, run_id)):
            continue
        grouped[(case_id, variant)][run_id] = run
        contract = run.get("review_contract")
        if isinstance(contract, dict):
            contracts[case_id] = contract

    case_matrix: dict[str, dict[str, object]] = {}
    qualified_cases: set[str] = set()
    for case_id, contract in sorted(contracts.items()):
        coverage = contract.get("release_coverage")
        if not (
            isinstance(coverage, dict)
            and coverage.get("high_value") is True
            and coverage.get("representative") is True
        ):
            continue
        skill_runs = list(grouped[(case_id, "skill")].values())
        baseline_runs = list(grouped[(case_id, "baseline")].values())
        skill_passed = sum(run.get("passed") is True for run in skill_runs)
        baseline_passed = sum(run.get("passed") is True for run in baseline_runs)
        skill_artifacts = [
            {
                "run_id": run.get("run_id"),
                "workspace_sha256": run.get("workspace_sha256"),
            }
            for run in sorted(
                skill_runs,
                key=lambda item: str(item.get("run_id")),
            )
        ]
        baseline_artifacts = [
            {
                "run_id": run.get("run_id"),
                "workspace_sha256": run.get("workspace_sha256"),
            }
            for run in sorted(
                baseline_runs,
                key=lambda item: str(item.get("run_id")),
            )
        ]
        artifact_references_valid = all(
            isinstance(record["run_id"], str)
            and isinstance(record["workspace_sha256"], str)
            for record in [*skill_artifacts, *baseline_artifacts]
        )
        skill_distinct_artifacts = {
            str(record["workspace_sha256"])
            for record in skill_artifacts
            if isinstance(record["workspace_sha256"], str)
        }
        repeated = (
            len(skill_runs) >= MIN_RELEASE_REPETITIONS_PER_VARIANT
            and len(baseline_runs) >= MIN_RELEASE_REPETITIONS_PER_VARIANT
            and skill_passed == len(skill_runs)
            and baseline_passed == len(baseline_runs)
            and artifact_references_valid
        )
        artifact_identity = (
            "identical"
            if len(skill_distinct_artifacts) == 1
            else "distinct"
            if len(skill_distinct_artifacts) == len(skill_artifacts)
            else "mixed"
        )
        case_matrix[case_id] = {
            "primary_mode": coverage.get("primary_mode"),
            "scope": coverage.get("scope"),
            "project_stratum": coverage.get("project_stratum"),
            "expressive_perception_gate": (
                coverage.get("expressive_perception_gate") is True
            ),
            "quiet_perception_gate": (
                coverage.get("quiet_perception_gate") is True
            ),
            "generated_media_capability_gate": (
                coverage.get("generated_media_capability_gate") is True
            ),
            "route_family_showcase_gate": (
                coverage.get("route_family_showcase_gate") is True
            ),
            "cultural_context_gate": (
                coverage.get("cultural_context_gate") is True
            ),
            "adversarial": bool(contract.get("adversarial_required")),
            "implicit": any(
                run.get("invocation_mode") == "implicit"
                and run.get("host_native_evidence_status") == "bound"
                for run in skill_runs
            ),
            "skill_runs": len(skill_runs),
            "skill_passed": skill_passed,
            "baseline_runs": len(baseline_runs),
            "baseline_passed": baseline_passed,
            "skill_distinct_artifacts": len(skill_distinct_artifacts),
            "skill_artifact_identity": artifact_identity,
            "skill_run_artifacts": skill_artifacts,
            "baseline_run_artifacts": baseline_artifacts,
            "qualified": repeated,
        }
        if repeated:
            qualified_cases.add(case_id)

    modes = {
        str(case_matrix[case_id]["primary_mode"])
        for case_id in qualified_cases
    }
    scopes = {
        str(case_matrix[case_id]["scope"])
        for case_id in qualified_cases
    }
    project_strata = {
        str(case_matrix[case_id]["project_stratum"])
        for case_id in qualified_cases
    }
    adversarial_cases = {
        case_id
        for case_id in qualified_cases
        if case_matrix[case_id]["adversarial"] is True
    }
    implicit_cases = {
        case_id
        for case_id in qualified_cases
        if case_matrix[case_id]["implicit"] is True
    }
    expressive_cases = {
        case_id
        for case_id in qualified_cases
        if case_matrix[case_id]["expressive_perception_gate"] is True
    }
    quiet_cases = {
        case_id
        for case_id in qualified_cases
        if case_matrix[case_id]["quiet_perception_gate"] is True
    }
    generated_media_cases = {
        case_id
        for case_id in qualified_cases
        if case_matrix[case_id]["generated_media_capability_gate"] is True
    }
    route_family_cases = {
        case_id
        for case_id in qualified_cases
        if case_matrix[case_id]["route_family_showcase_gate"] is True
    }
    cultural_context_cases = {
        case_id
        for case_id in qualified_cases
        if case_matrix[case_id]["cultural_context_gate"] is True
    }
    if len(qualified_cases) < MIN_RELEASE_REPRESENTATIVE_CASES:
        failures.append(issue(
            "release-behavioral-case-coverage-incomplete",
            label,
            (
                f"Behavioral pass needs at least {MIN_RELEASE_REPRESENTATIVE_CASES} "
                "distinct representative high-value cases, each with at least "
                f"{MIN_RELEASE_REPETITIONS_PER_VARIANT} passed skill and baseline "
                f"runs; qualified: {len(qualified_cases)}."
            ),
        ))
    if not REQUIRED_RELEASE_MODES <= modes:
        missing_modes = sorted(REQUIRED_RELEASE_MODES - modes)
        failures.append(issue(
            "release-behavioral-mode-coverage-incomplete",
            label,
            (
                "Representative behavioral coverage must include Persuade, "
                "Experience, Operate, and Read; missing: "
                + ", ".join(missing_modes)
            ),
        ))
    if len(scopes) < 2:
        failures.append(issue(
            "release-behavioral-scope-coverage-incomplete",
            label,
            "Representative behavioral coverage must span at least two scopes.",
        ))
    if not adversarial_cases:
        failures.append(issue(
            "release-behavioral-adversarial-coverage-missing",
            label,
            "Representative behavioral coverage needs at least one adversarial case.",
        ))
    if not implicit_cases:
        failures.append(issue(
            "release-implicit-discovery-coverage-missing",
            label,
            (
                "Behavioral pass needs a representative implicit-discovery case "
                "with bound host-native evidence; explicit invocation cannot prove "
                "automatic discovery."
            ),
        ))
    if "framework-application-data" not in project_strata:
        failures.append(issue(
            "release-framework-application-coverage-missing",
            label,
            (
                "Representative behavioral coverage needs an established "
                "framework application with local data, state, assets, and "
                "scope-control constraints."
            ),
        ))
    if len(expressive_cases) < MIN_EXPRESSIVE_RELEASE_CASES:
        failures.append(issue(
            "release-expressive-behavioral-coverage-incomplete",
            label,
            (
                "Representative behavioral coverage needs at least "
                f"{MIN_EXPRESSIVE_RELEASE_CASES} distinct cases marked with "
                "release_coverage.expressive_perception_gate; qualified: "
                f"{len(expressive_cases)}."
            ),
        ))
    if len(quiet_cases) < MIN_QUIET_RELEASE_CASES:
        failures.append(issue(
            "release-quiet-behavioral-coverage-incomplete",
            label,
            (
                "Representative behavioral coverage needs at least "
                f"{MIN_QUIET_RELEASE_CASES} distinct case marked with "
                "release_coverage.quiet_perception_gate; qualified: "
                f"{len(quiet_cases)}."
            ),
        ))
    if len(route_family_cases) < MIN_ROUTE_FAMILY_RELEASE_CASES:
        failures.append(issue(
            "release-route-family-behavioral-coverage-incomplete",
            label,
            (
                "Representative behavioral coverage needs at least "
                f"{MIN_ROUTE_FAMILY_RELEASE_CASES} distinct case marked with "
                "release_coverage.route_family_showcase_gate; qualified: "
                f"{len(route_family_cases)}."
            ),
        ))
    if len(cultural_context_cases) < MIN_CULTURAL_CONTEXT_RELEASE_CASES:
        failures.append(issue(
            "release-cultural-context-behavioral-coverage-incomplete",
            label,
            (
                "Representative behavioral coverage needs at least "
                f"{MIN_CULTURAL_CONTEXT_RELEASE_CASES} distinct case marked "
                "with release_coverage.cultural_context_gate; qualified: "
                f"{len(cultural_context_cases)}."
            ),
        ))
    details: dict[str, object] = {
        "minimum_cases": MIN_RELEASE_REPRESENTATIVE_CASES,
        "minimum_runs_per_variant": MIN_RELEASE_REPETITIONS_PER_VARIANT,
        "qualified_cases": sorted(qualified_cases),
        "modes": sorted(modes),
        "scopes": sorted(scopes),
        "project_strata": sorted(project_strata),
        "adversarial_cases": sorted(adversarial_cases),
        "implicit_discovery_cases": sorted(implicit_cases),
        "expressive_perception_cases": sorted(expressive_cases),
        "quiet_perception_cases": sorted(quiet_cases),
        "generated_media_capability_cases": sorted(generated_media_cases),
        "route_family_showcase_cases": sorted(route_family_cases),
        "cultural_context_cases": sorted(cultural_context_cases),
        "cases": case_matrix,
    }
    return failures, details


REQUIRED_COMPARATIVE_DIMENSIONS = {
    "project_specificity",
    "distinctiveness_without_novelty_tax",
}


def representative_comparison_failures(
    payload: dict[str, object],
    case_metadata: dict[str, object],
    label: str,
) -> list[dict[str, str]]:
    """Bind comparative claims to every counted run and its exact artifact."""
    failures: list[dict[str, str]] = []
    comparison = payload.get("comparative_analysis")
    if not isinstance(comparison, dict):
        return [issue(
            "release-comparative-analysis-missing",
            label,
            (
                "Representative perception review needs structured skill-versus-"
                "baseline and repeated-run analysis."
            ),
        )]

    expected_by_variant = {
        "skill": case_metadata.get("skill_run_artifacts"),
        "baseline": case_metadata.get("baseline_run_artifacts"),
    }
    expected_observations: dict[tuple[str, str], str] = {}
    for variant, expected_values in expected_by_variant.items():
        actual_values = comparison.get(f"{variant}_runs")
        expected = {
            (
                str(record.get("run_id")),
                str(record.get("workspace_sha256")),
            )
            for record in expected_values
            if isinstance(record, dict)
        } if isinstance(expected_values, list) else set()
        actual_pairs = [
            (
                str(record.get("run_id")),
                str(record.get("workspace_sha256")),
            )
            for record in actual_values
            if isinstance(record, dict)
        ] if isinstance(actual_values, list) else []
        if len(actual_pairs) != len(set(actual_pairs)) or set(actual_pairs) != expected:
            failures.append(issue(
                "release-comparative-run-binding-mismatch",
                label,
                (
                    f"comparative_analysis.{variant}_runs must bind every "
                    "counted run ID to its exact workspace SHA-256 once."
                ),
            ))
        expected_observations.update({
            (variant, run_id): workspace_sha256
            for run_id, workspace_sha256 in expected
        })

    convergence = comparison.get("convergence")
    observations = (
        convergence.get("run_observations")
        if isinstance(convergence, dict)
        else None
    )
    actual_observations = [
        (str(record.get("variant")), str(record.get("run_id")))
        for record in observations
        if isinstance(record, dict)
    ] if isinstance(observations, list) else []
    if (
        len(actual_observations) != len(set(actual_observations))
        or set(actual_observations) != set(expected_observations)
    ):
        failures.append(issue(
            "release-convergence-run-coverage-incomplete",
            label,
            (
                "Convergence observations must cover every counted skill and "
                "baseline run exactly once."
            ),
        ))
    observation_workspace_mismatches: list[str] = []
    evidence_path_workspaces: defaultdict[str, set[str]] = defaultdict(set)
    evidence_digest_workspaces: defaultdict[str, set[str]] = defaultdict(set)
    if isinstance(observations, list):
        for record in observations:
            if not isinstance(record, dict):
                continue
            key = (
                str(record.get("variant")),
                str(record.get("run_id")),
            )
            expected_workspace = expected_observations.get(key)
            if (
                expected_workspace is None
                or record.get("workspace_sha256") != expected_workspace
            ):
                observation_workspace_mismatches.append(key[1])
                continue
            if record.get("basis") != "rendered":
                continue
            references = record.get("evidence")
            if not isinstance(references, list):
                continue
            for evidence_record in references:
                if not isinstance(evidence_record, dict):
                    continue
                evidence_path = portable_relative(evidence_record.get("path"))
                evidence_digest = evidence_record.get("sha256")
                if evidence_path is not None:
                    evidence_path_workspaces[
                        evidence_path.casefold()
                    ].add(expected_workspace)
                if isinstance(evidence_digest, str):
                    evidence_digest_workspaces[
                        evidence_digest
                    ].add(expected_workspace)
    if observation_workspace_mismatches:
        failures.append(issue(
            "release-comparison-observation-workspace-mismatch",
            label,
            (
                "Each run observation must bind its run ID to the exact "
                "counted workspace SHA-256: "
                + ", ".join(sorted(observation_workspace_mismatches))
            ),
        ))
    reused_paths = sorted(
        path
        for path, workspaces in evidence_path_workspaces.items()
        if len(workspaces) > 1
    )
    reused_digests = sorted(
        digest
        for digest, workspaces in evidence_digest_workspaces.items()
        if len(workspaces) > 1
    )
    if reused_paths or reused_digests:
        failures.append(issue(
            "release-comparison-render-reused-across-workspaces",
            label,
            (
                "A render path or digest may be reused only for observations "
                "whose counted workspace SHA-256 is identical; conflicting "
                f"paths: {len(reused_paths)}, digests: {len(reused_digests)}."
            ),
        ))
    source_only_observations = [
        run_id
        for record in observations
        if isinstance(record, dict)
        and record.get("basis") == "source-only"
        for run_id in [str(record.get("run_id"))]
    ] if isinstance(observations, list) else []
    observations_without_evidence = [
        str(record.get("run_id"))
        for record in observations
        if isinstance(record, dict)
        and (
            record.get("basis") not in {"rendered", "source-only"}
            or not isinstance(record.get("evidence"), list)
            or not record["evidence"]
        )
    ] if isinstance(observations, list) else []
    if observations_without_evidence:
        failures.append(issue(
            "release-comparison-run-evidence-missing",
            label,
            (
                "Every counted skill and baseline run observation needs an "
                "explicit basis and hash-bound evidence: "
                + ", ".join(sorted(observations_without_evidence))
            ),
        ))
    if source_only_observations:
        failures.append(issue(
            "release-comparative-visual-basis-incomplete",
            label,
            (
                "Source-only observations are explicitly segregated and "
                "cannot satisfy representative visual comparison claims: "
                + ", ".join(sorted(source_only_observations))
            ),
        ))
    if (
        isinstance(convergence, dict)
        and convergence.get("quality_consistency") == "inconsistent"
    ):
        failures.append(issue(
            "release-convergence-inconsistent",
            label,
            "An inconsistent repeated-run result cannot support a release pass.",
        ))
    expected_artifact_identity = case_metadata.get("skill_artifact_identity")
    if (
        not isinstance(convergence, dict)
        or convergence.get("artifact_identity") != expected_artifact_identity
    ):
        failures.append(issue(
            "release-convergence-artifact-identity-mismatch",
            label,
            (
                "The convergence record must classify the counted skill "
                "artifact hashes exactly; identical output is contextual "
                "evidence, not an automatic failure or proof of quality."
            ),
        ))
    if (
        not isinstance(convergence, dict)
        or not isinstance(
            convergence.get("artifact_identity_interpretation"),
            str,
        )
        or len(convergence["artifact_identity_interpretation"].strip()) < 24
    ):
        failures.append(issue(
            "release-convergence-artifact-context-missing",
            label,
            (
                "Explain what identical, mixed, or distinct artifact hashes "
                "mean in the observed task context."
            ),
        ))

    criteria = comparison.get("criteria")
    dimension_records = {
        str(record.get("dimension")): record
        for record in criteria
        if isinstance(record, dict)
    } if isinstance(criteria, list) else {}
    dimensions = set(dimension_records)
    if not REQUIRED_COMPARATIVE_DIMENSIONS <= dimensions:
        failures.append(issue(
            "release-comparative-dimensions-incomplete",
            label,
            (
                "Comparative analysis must explicitly assess project specificity "
                "and distinctiveness without novelty tax."
            ),
        ))
    if isinstance(criteria, list) and len(dimensions) != len(criteria):
        failures.append(issue(
            "release-comparative-dimension-duplicate",
            label,
            "Each comparative dimension must be assessed exactly once.",
        ))
    baseline_stronger_core = sorted(
        dimension
        for dimension in REQUIRED_COMPARATIVE_DIMENSIONS
        if isinstance(dimension_records.get(dimension), dict)
        and dimension_records[dimension].get("outcome") == "baseline-stronger"
    )
    if baseline_stronger_core:
        failures.append(issue(
            "release-core-comparison-regression",
            label,
            (
                "A release-counted case cannot be baseline-stronger on core "
                "Design DNA outcomes: "
                + ", ".join(baseline_stronger_core)
            ),
        ))
    conclusive = any(
        isinstance(record, dict)
        and record.get("outcome") != "inconclusive"
        for record in criteria
    ) if isinstance(criteria, list) else False
    if not conclusive:
        failures.append(issue(
            "release-comparative-analysis-inconclusive",
            label,
            "At least one comparative criterion needs a supported conclusion.",
        ))
    return failures


REQUIRED_CROSS_CASE_DIMENSIONS = {"rendered_geometry"}


def cross_case_analysis_failures(
    payload: dict[str, object],
    qualified_families: dict[str, dict[str, object]],
    case_metadata: dict[str, object],
    label: str,
) -> list[dict[str, str]]:
    """Verify cross-project house-style review against exact counted renders."""
    failures: list[dict[str, str]] = []
    analysis = payload.get("cross_case_analysis")
    if not isinstance(analysis, dict):
        return [issue(
            "release-cross-case-analysis-missing",
            label,
            (
                "Release coverage needs a structured cross-case house-style "
                "analysis over counted representative renders."
            ),
        )]
    builds = analysis.get("builds")
    build_records = [
        record for record in builds if isinstance(record, dict)
    ] if isinstance(builds, list) else []
    case_ids = [str(record.get("case_id")) for record in build_records]
    expected_case_ids = set(qualified_families)
    if (
        len(case_ids) != len(set(case_ids))
        or set(case_ids) != expected_case_ids
    ):
        failures.append(issue(
            "release-cross-case-build-coverage-incomplete",
            label,
            (
                "Cross-case analysis must bind the exact full set of counted "
                "representative case/build families."
            ),
        ))
    for index, record in enumerate(build_records):
        case_id = str(record.get("case_id"))
        expected = qualified_families.get(case_id)
        actual_hashes = record.get("render_sha256s")
        if (
            not isinstance(expected, dict)
            or record.get("run_id") != expected.get("run_id")
            or record.get("build_identity") != expected.get("build_identity")
            or not isinstance(actual_hashes, list)
            or set(actual_hashes) != set(expected.get("render_sha256s", []))
            or len(actual_hashes) != len(set(actual_hashes))
        ):
            failures.append(issue(
                "release-cross-case-build-binding-mismatch",
                f"{label}#cross_case_analysis/builds/{index}",
                (
                    "Each analyzed case must bind the exact counted run, build "
                    "identity, and verified responsive render hashes."
                ),
            ))

    blinded_comparison = analysis.get("identity_blinded_comparison")
    blinded_risk_cluster_ids: set[str] = set()
    if not isinstance(blinded_comparison, dict):
        failures.append(issue(
            "release-cross-case-identity-blinded-comparison-missing",
            label,
            (
                "Cross-case release review needs a hash-bound comparison "
                "performed under neutral labels before the identity map or "
                "diagnostic material is revealed."
            ),
        ))
    else:
        method = blinded_comparison.get("method")
        protocol = blinded_comparison.get("neutral_label_protocol")
        hidden_identities = (
            protocol.get("identities_hidden")
            if isinstance(protocol, dict)
            else None
        )
        allowed_hidden_identities = {
            "case-identity",
            "model",
            "host",
            "variant",
            "producer",
        }
        if (
            not isinstance(method, str)
            or len(method.strip()) < 24
            or not isinstance(protocol, dict)
            or not isinstance(protocol.get("assignment_method"), str)
            or len(protocol["assignment_method"].strip()) < 24
            or not isinstance(hidden_identities, list)
            or not hidden_identities
            or any(not isinstance(value, str) for value in hidden_identities)
            or len(hidden_identities) != len(set(hidden_identities))
            or set(hidden_identities) != allowed_hidden_identities
            or protocol.get("identity_revealed_before_observation") is not False
            or protocol.get("diagnostic_material_seen_before_observation") is not False
        ):
            failures.append(issue(
                "release-cross-case-identity-blinding-incomplete",
                f"{label}#cross_case_analysis/identity_blinded_comparison",
                (
                    "Record neutral-label assignment, which identities were "
                    "hidden, and a first observation frozen before identity "
                    "or diagnostic reveal."
                ),
            ))
        if blinded_comparison.get("authorship_inference") != "not-performed":
            failures.append(issue(
                "release-cross-case-authorship-inference-prohibited",
                f"{label}#cross_case_analysis/identity_blinded_comparison",
                (
                    "The blinded comparison may assess structural range only; "
                    "it cannot infer human or AI authorship."
                ),
            ))
        limitations = blinded_comparison.get("limitations")
        if (
            not isinstance(limitations, list)
            or not limitations
            or any(
                not isinstance(value, str) or len(value.strip()) < 12
                for value in limitations
            )
        ):
            failures.append(issue(
                "release-cross-case-identity-blinded-limitations-missing",
                f"{label}#cross_case_analysis/identity_blinded_comparison",
                (
                    "State at least one substantive limitation of the "
                    "identity-blinded comparison."
                ),
            ))
        top_evidence = blinded_comparison.get("evidence")
        if not isinstance(top_evidence, list) or not top_evidence:
            failures.append(issue(
                "release-cross-case-identity-blinded-evidence-missing",
                f"{label}#cross_case_analysis/identity_blinded_comparison",
                "The identity-blinded comparison needs hash-bound evidence.",
            ))

        coverage = blinded_comparison.get("coverage")
        coverage_records = [
            record for record in coverage if isinstance(record, dict)
        ] if isinstance(coverage, list) else []
        blinded_case_ids = [
            str(record.get("case_id")) for record in coverage_records
        ]
        neutral_labels = [record.get("neutral_label") for record in coverage_records]
        if (
            len(blinded_case_ids) != len(set(blinded_case_ids))
            or set(blinded_case_ids) != expected_case_ids
            or any(
                not isinstance(value, str) or not value.strip()
                for value in neutral_labels
            )
            or len(neutral_labels) != len(set(neutral_labels))
        ):
            failures.append(issue(
                "release-cross-case-identity-blinded-coverage-incomplete",
                f"{label}#cross_case_analysis/identity_blinded_comparison/coverage",
                (
                    "Identity-blinded coverage must bind the exact full set "
                    "of counted case/build families under unique neutral labels."
                ),
            ))
        for index, record in enumerate(coverage_records):
            coverage_label = (
                f"{label}#cross_case_analysis/identity_blinded_comparison/"
                f"coverage/{index}"
            )
            case_id = str(record.get("case_id"))
            expected = qualified_families.get(case_id)
            source_hashes = record.get("source_render_sha256s")
            references = record.get("evidence")
            reference_hashes = {
                str(reference.get("sha256"))
                for reference in references
                if isinstance(reference, dict)
                and isinstance(reference.get("sha256"), str)
            } if isinstance(references, list) else set()
            if (
                not isinstance(expected, dict)
                or record.get("run_id") != expected.get("run_id")
                or record.get("build_identity") != expected.get("build_identity")
                or not isinstance(source_hashes, list)
                or any(not isinstance(value, str) for value in source_hashes)
                or set(source_hashes) != set(expected.get("render_sha256s", []))
                or len(source_hashes) != len(set(source_hashes))
            ):
                failures.append(issue(
                    "release-cross-case-identity-blinded-build-binding-mismatch",
                    coverage_label,
                    (
                        "Each identity-blinded comparison entry must bind the exact "
                        "counted run, build, and source render hashes."
                    ),
                ))
            if (
                not isinstance(source_hashes, list)
                or not source_hashes
                or not set(source_hashes) <= reference_hashes
            ):
                failures.append(issue(
                    "release-cross-case-source-render-evidence-incomplete",
                    coverage_label,
                    (
                        "Provide hash-bound original evidence for every counted "
                        "responsive render; identity blinding does not replace pixels."
                    ),
                ))

        transformation = blinded_comparison.get("pixel_transformation")
        if transformation is not None:
            authorization = (
                transformation.get("authorization")
                if isinstance(transformation, dict)
                else None
            )
            artifacts = (
                transformation.get("artifacts")
                if isinstance(transformation, dict)
                else None
            )
            all_source_hashes = {
                str(value)
                for record in coverage_records
                for value in (
                    record.get("source_render_sha256s")
                    if isinstance(record.get("source_render_sha256s"), list)
                    else []
                )
            }
            transformation_invalid = (
                not isinstance(transformation, dict)
                or transformation.get("purpose")
                not in {"hypothesis-test", "privacy-minimization"}
                or not isinstance(transformation.get("justification"), str)
                or len(transformation["justification"].strip()) < 24
                or not isinstance(transformation.get("method"), str)
                or len(transformation["method"].strip()) < 24
                or not isinstance(transformation.get("coverage_impact"), str)
                or len(transformation["coverage_impact"].strip()) < 24
                or not isinstance(authorization, dict)
                or authorization.get("status") != "authorized"
                or not isinstance(authorization.get("authority_id"), str)
                or not isinstance(authorization.get("basis"), str)
                or len(authorization["basis"].strip()) < 16
                or not isinstance(authorization.get("evidence"), list)
                or not authorization["evidence"]
                or not isinstance(artifacts, list)
                or not artifacts
            )
            if not transformation_invalid:
                for artifact in artifacts:
                    if not isinstance(artifact, dict):
                        transformation_invalid = True
                        continue
                    source_hash = artifact.get("source_render_sha256")
                    transformed_hash = artifact.get("transformed_render_sha256")
                    source_evidence = artifact.get("source_evidence")
                    transformed_evidence = artifact.get("transformed_evidence")
                    if (
                        source_hash not in all_source_hashes
                        or not isinstance(transformed_hash, str)
                        or transformed_hash == source_hash
                        or not isinstance(source_evidence, dict)
                        or source_evidence.get("sha256") != source_hash
                        or not isinstance(transformed_evidence, dict)
                        or transformed_evidence.get("sha256") != transformed_hash
                    ):
                        transformation_invalid = True
            if transformation_invalid:
                failures.append(issue(
                    "release-cross-case-pixel-transformation-incomplete",
                    (
                        f"{label}#cross_case_analysis/"
                        "identity_blinded_comparison/pixel_transformation"
                    ),
                    (
                        "An optional pixel transformation needs a stated "
                        "hypothesis or privacy purpose, authorization, method, "
                        "original/transformed hash pairs, and coverage impact."
                    ),
                ))

        observations = blinded_comparison.get("observations")
        observation_records = [
            record for record in observations if isinstance(record, dict)
        ] if isinstance(observations, list) else []
        observed_case_ids: set[str] = set()
        observation_invalid = not observation_records
        for record in observation_records:
            observation_case_ids = record.get("case_ids")
            selected = {
                str(case_id) for case_id in observation_case_ids
            } if isinstance(observation_case_ids, list) else set()
            outcome = record.get("outcome")
            assessment = record.get("assessment")
            references = record.get("evidence")
            cluster_id = record.get("cluster_id")
            if (
                len(selected) < 2
                or not selected <= expected_case_ids
                or outcome not in {
                    "meaningful-structural-difference",
                    "benign-overlap",
                    "repeated-reskin-risk",
                }
                or not isinstance(assessment, str)
                or len(assessment.strip()) < 24
                or not isinstance(references, list)
                or not references
                or (
                    outcome == "repeated-reskin-risk"
                    and not isinstance(cluster_id, str)
                )
                or (
                    outcome != "repeated-reskin-risk"
                    and cluster_id is not None
                )
            ):
                observation_invalid = True
                continue
            observed_case_ids.update(selected)
            if outcome == "repeated-reskin-risk":
                blinded_risk_cluster_ids.add(cluster_id)
        if observation_invalid or observed_case_ids != expected_case_ids:
            failures.append(issue(
                "release-cross-case-identity-blinded-observations-incomplete",
                f"{label}#cross_case_analysis/identity_blinded_comparison/observations",
                (
                    "Hash-bound blinded observations must compare every counted "
                    "case and record a structural outcome without an authorship claim."
                ),
            ))

    selected_metadata = [
        case_metadata.get(case_id)
        for case_id in set(case_ids)
        if isinstance(case_metadata.get(case_id), dict)
    ]
    selected_modes = {
        str(record.get("primary_mode"))
        for record in selected_metadata
        if isinstance(record, dict)
    }
    selected_scopes = {
        str(record.get("scope"))
        for record in selected_metadata
        if isinstance(record, dict)
    }
    selected_strata = {
        str(record.get("project_stratum"))
        for record in selected_metadata
        if isinstance(record, dict)
    }
    if (
        not REQUIRED_RELEASE_MODES <= selected_modes
        or len(selected_scopes) < 2
        or "framework-application-data" not in selected_strata
    ):
        failures.append(issue(
            "release-cross-case-diversity-incomplete",
            label,
            (
                "Cross-case analysis must compare the same counted set spanning "
                "all four modes, two scopes, and a framework application."
            ),
        ))

    dimensions = analysis.get("dimensions")
    dimension_ids = [
        str(record.get("dimension"))
        for record in dimensions
        if isinstance(record, dict)
    ] if isinstance(dimensions, list) else []
    dimension_records = {
        str(record.get("dimension")): record
        for record in dimensions
        if isinstance(record, dict)
        and isinstance(record.get("dimension"), str)
    } if isinstance(dimensions, list) else {}
    if (
        len(dimension_ids) != len(set(dimension_ids))
        or not REQUIRED_CROSS_CASE_DIMENSIONS <= set(dimension_ids)
        or any(
            dimension_records.get(dimension, {}).get("applicability")
            != "applicable"
            for dimension in REQUIRED_CROSS_CASE_DIMENSIONS
        )
    ):
        failures.append(issue(
            "release-cross-case-dimensions-incomplete",
            label,
            (
                "Cross-case analysis needs unique project-relevant lenses and "
                "must include rendered_geometry. Record an inapplicable lens only "
                "when its absence matters to the comparison; do not manufacture "
                "a fixed aesthetic checklist."
            ),
        ))
    risk_dimensions = {
        str(record.get("dimension"))
        for record in dimensions
        if isinstance(record, dict)
        and record.get("outcome") == "repeated-cluster-risk"
    } if isinstance(dimensions, list) else set()
    clusters = analysis.get("repeated_clusters")
    cluster_records = [
        record for record in clusters if isinstance(record, dict)
    ] if isinstance(clusters, list) else []
    cluster_dimensions = {
        str(dimension)
        for record in cluster_records
        for dimension in record.get("dimensions", [])
    }
    cluster_ids = {
        str(record.get("id"))
        for record in cluster_records
        if isinstance(record.get("id"), str)
    }
    if not cluster_dimensions <= set(dimension_ids):
        failures.append(issue(
            "release-cross-case-cluster-dimension-undeclared",
            label,
            (
                "Every repeated-cluster dimension must be declared among the "
                "project-relevant comparison lenses."
            ),
        ))
    if not blinded_risk_cluster_ids <= cluster_ids:
        failures.append(issue(
            "release-cross-case-identity-blinded-risk-untracked",
            label,
            (
                "Every repeated reskin risk from the blinded comparison needs "
                "an explicit repeated-cluster record and disposition."
            ),
        ))
    if not risk_dimensions <= cluster_dimensions:
        failures.append(issue(
            "release-cross-case-risk-untracked",
            label,
            (
                "Every repeated-cluster-risk dimension needs an explicit "
                "cluster record and disposition."
            ),
        ))
    unresolved_resolution_records = [
        str(record.get("id"))
        for record in cluster_records
        if record.get("status") == "resolved"
        and (
            not isinstance(record.get("resolution"), dict)
            or not isinstance(
                record["resolution"].get("cause_addressed"),
                str,
            )
            or len(record["resolution"]["cause_addressed"].strip()) < 24
            or not isinstance(record["resolution"].get("evidence"), list)
            or not record["resolution"]["evidence"]
            or not isinstance(record.get("verification"), dict)
            or not isinstance(record["verification"].get("evidence"), list)
            or not record["verification"]["evidence"]
        )
    ]
    if unresolved_resolution_records:
        failures.append(issue(
            "release-cross-case-resolution-unverified",
            label,
            (
                "A resolved repeated cluster needs cause-level resolution and "
                "hash-bound verification: "
                + ", ".join(unresolved_resolution_records)
            ),
        ))
    unresolved_clusters = [
        str(record.get("id"))
        for record in cluster_records
        if record.get("status") == "unresolved"
    ]
    conclusion = analysis.get("conclusion")
    declared_unresolved = (
        conclusion.get("unresolved_repeated_cluster")
        if isinstance(conclusion, dict)
        else None
    )
    if unresolved_clusters or declared_unresolved is True:
        failures.append(issue(
            "release-cross-case-house-style-unresolved",
            label,
            (
                "An unresolved repeated house-style cluster prevents release: "
                + ", ".join(unresolved_clusters or ["declared cluster"])
            ),
        ))
    if declared_unresolved is not bool(unresolved_clusters):
        failures.append(issue(
            "release-cross-case-conclusion-mismatch",
            label,
            (
                "Cross-case conclusion must agree with the recorded repeated "
                "cluster dispositions."
            ),
        ))
    return failures


def release_representative_review_failures(
    host_name: str,
    behavioral_coverage: dict[str, object],
    matched: list[tuple[Path, dict[str, object]]],
    review_render_contexts: dict[Path, list[dict[str, object]]],
    closure_qualified_paths: set[Path],
    evidence_keys: set[str],
    plugin: Path,
) -> tuple[list[dict[str, str]], dict[str, object]]:
    """Bind both review lenses and responsive evidence to each counted build."""
    failures: list[dict[str, str]] = []
    label = f"maintainer/compatibility/matrix.yml:{host_name}"
    behavioral_cases = {
        str(value)
        for value in behavioral_coverage.get("qualified_cases", [])
    }
    case_metadata = behavioral_coverage.get("cases")
    if not isinstance(case_metadata, dict):
        case_metadata = {}
    families: defaultdict[
        tuple[str, str, str],
        list[tuple[Path, dict[str, object]]],
    ] = defaultdict(list)
    for path, review in matched:
        build = review.get("build")
        if not isinstance(build, dict):
            continue
        key = (
            str(review.get("case_id")),
            str(review.get("run_id")),
            str(build.get("identity")),
        )
        families[key].append((path, review))

    qualified_families: dict[str, list[str]] = {}
    qualified_family_records: dict[str, dict[str, object]] = {}
    qualified_perception_paths: set[Path] = set()
    skill_benefit_cases: set[str] = set()
    adversarial_closed_cases: set[str] = set()
    generated_media_review_cases: set[str] = set()
    route_family_review_cases: set[str] = set()
    cultural_context_review_cases: set[str] = set()
    image_generation_available_claimed = any(
        image_generation_disposition_status(review) == "available"
        for _path, review in matched
    )
    unqualified_families: dict[str, list[str]] = {}
    for (case_id, run_id, build_identity), family_reviews in families.items():
        if case_id not in behavioral_cases:
            continue
        perception = [
            (path, review)
            for path, review in family_reviews
            if isinstance(review.get("reviewer"), dict)
            and review["reviewer"].get("lens") == "perception"
        ]
        implementation = [
            (path, review)
            for path, review in family_reviews
            if isinstance(review.get("reviewer"), dict)
            and review["reviewer"].get("lens") == "implementation"
        ]
        if not perception or not implementation:
            unqualified_families[case_id] = [
                "missing same-build perception or implementation review"
            ]
            continue
        metadata = case_metadata.get(case_id)
        if not isinstance(metadata, dict):
            continue
        qualified_pair = False
        selected_perception_path: Path | None = None
        selected_perception_review: dict[str, object] | None = None
        family_reasons: set[str] = set()
        for perception_path, perception_review in perception:
            perception_reviewer = perception_review.get("reviewer")
            perception_conclusion = perception_review.get("conclusion")
            process = (
                perception_reviewer.get("process")
                if isinstance(perception_reviewer, dict)
                else None
            )
            independent = (
                isinstance(perception_reviewer, dict)
                and perception_reviewer.get("independent") is True
                and isinstance(process, dict)
                and process.get("method") in INDEPENDENT_REVIEW_METHODS
            )
            kinds = {
                record.get("kind")
                for record in review_render_contexts.get(perception_path, [])
            }
            perception_bound = (
                perception_path.relative_to(plugin).as_posix().casefold()
                in evidence_keys
            )
            perception_passed = (
                isinstance(perception_conclusion, dict)
                and perception_conclusion.get("decision")
                in {"pass", "pass-with-limitations"}
            )
            comparison_failures = representative_comparison_failures(
                perception_review,
                metadata,
                str(perception_path.relative_to(plugin)),
            )
            expressive_failures = expressive_perception_gate_failures(
                perception_review,
                {
                    "release_coverage": {
                        "expressive_perception_gate": metadata.get(
                            "expressive_perception_gate"
                        )
                    }
                },
                str(perception_path.relative_to(plugin)),
            )
            quiet_failures = quiet_perception_gate_failures(
                perception_review,
                {
                    "release_coverage": {
                        "quiet_perception_gate": metadata.get(
                            "quiet_perception_gate"
                        )
                    }
                },
                str(perception_path.relative_to(plugin)),
            )
            generated_media_failures = generated_media_capability_gate_failures(
                perception_review,
                {
                    "release_coverage": {
                        "generated_media_capability_gate": metadata.get(
                            "generated_media_capability_gate"
                        )
                    }
                },
                str(perception_path.relative_to(plugin)),
            )
            route_family_failures = route_family_showcase_gate_failures(
                perception_review,
                {
                    "release_coverage": {
                        "route_family_showcase_gate": metadata.get(
                            "route_family_showcase_gate"
                        )
                    }
                },
                str(perception_path.relative_to(plugin)),
            )
            cultural_context_failures = cultural_context_gate_failures(
                perception_review,
                {
                    "release_coverage": {
                        "cultural_context_gate": metadata.get(
                            "cultural_context_gate"
                        )
                    }
                },
                str(perception_path.relative_to(plugin)),
            )
            if comparison_failures:
                family_reasons.update(
                    str(failure["code"]) for failure in comparison_failures
                )
            if expressive_failures:
                family_reasons.update(
                    str(failure["code"]) for failure in expressive_failures
                )
            if quiet_failures:
                family_reasons.update(
                    str(failure["code"]) for failure in quiet_failures
                )
            if generated_media_failures:
                family_reasons.update(
                    str(failure["code"]) for failure in generated_media_failures
                )
            if route_family_failures:
                family_reasons.update(
                    str(failure["code"]) for failure in route_family_failures
                )
            if cultural_context_failures:
                family_reasons.update(
                    str(failure["code"]) for failure in cultural_context_failures
                )
            if not (
                independent
                and {"mobile", "desktop"} <= kinds
                and perception_bound
                and perception_passed
                and perception_path in closure_qualified_paths
                and not comparison_failures
                and not expressive_failures
                and not quiet_failures
                and not generated_media_failures
                and not route_family_failures
                and not cultural_context_failures
            ):
                continue
            for implementation_path, implementation_review in implementation:
                implementation_reviewer = implementation_review.get("reviewer")
                implementation_conclusion = implementation_review.get("conclusion")
                implementation_process = (
                    implementation_reviewer.get("process")
                    if isinstance(implementation_reviewer, dict)
                    else None
                )
                implementation_bound = (
                    implementation_path.relative_to(plugin).as_posix().casefold()
                    in evidence_keys
                )
                implementation_passed = (
                    isinstance(implementation_conclusion, dict)
                    and implementation_conclusion.get("decision")
                    in {"pass", "pass-with-limitations"}
                )
                processes_distinct = (
                    isinstance(process, dict)
                    and isinstance(implementation_process, dict)
                    and process.get("id") != implementation_process.get("id")
                    and process.get("evidence_path")
                    != implementation_process.get("evidence_path")
                )
                if (
                    implementation_bound
                    and implementation_passed
                    and processes_distinct
                ):
                    qualified_pair = True
                    selected_perception_path = perception_path
                    selected_perception_review = perception_review
                    break
            if qualified_pair:
                break
        if not qualified_pair:
            family_reasons.add(
                "missing one perception review that independently combines "
                "responsive evidence, exact closure, and bound comparison with "
                "a distinct passing implementation review"
            )
            unqualified_families[case_id] = sorted(family_reasons)
            continue
        if (
            selected_perception_path is None
            or selected_perception_review is None
        ):
            continue
        render_sha256s = sorted({
            str(record.get("sha256"))
            for record in review_render_contexts.get(
                selected_perception_path,
                [],
            )
            if isinstance(record.get("sha256"), str)
        })
        qualified_families[case_id] = [run_id, build_identity]
        qualified_family_records[case_id] = {
            "run_id": run_id,
            "build_identity": build_identity,
            "render_sha256s": render_sha256s,
        }
        qualified_perception_paths.add(selected_perception_path)
        selected_comparison = selected_perception_review.get(
            "comparative_analysis"
        )
        selected_criteria = (
            selected_comparison.get("criteria")
            if isinstance(selected_comparison, dict)
            else []
        )
        if any(
            isinstance(record, dict)
            and record.get("dimension") in REQUIRED_COMPARATIVE_DIMENSIONS
            and record.get("outcome") == "skill-stronger"
            for record in selected_criteria
        ):
            skill_benefit_cases.add(case_id)
        if (
            metadata.get("adversarial") is True
            and selected_perception_path in closure_qualified_paths
        ):
            adversarial_closed_cases.add(case_id)
        if (
            metadata.get("generated_media_capability_gate") is True
            and image_generation_disposition_status(
                selected_perception_review
            ) == "available"
        ):
            generated_media_review_cases.add(case_id)
        if metadata.get("route_family_showcase_gate") is True:
            route_family_review_cases.add(case_id)
        if metadata.get("cultural_context_gate") is True:
            cultural_context_review_cases.add(case_id)

    if len(qualified_families) < MIN_RELEASE_REPRESENTATIVE_CASES:
        failures.append(issue(
            "release-rendered-case-coverage-incomplete",
            label,
            (
                f"Rendered pass needs perception and implementation reviews on "
                f"the same build for at least {MIN_RELEASE_REPRESENTATIVE_CASES} "
                "behaviorally qualified representative cases, with independent "
                "perception, responsive evidence, exact requirement closure, "
                "and structured skill-versus-baseline convergence analysis for "
                "each."
            ),
        ))
    if not adversarial_closed_cases:
        failures.append(issue(
            "release-adversarial-closure-missing",
            label,
            (
                "At least one same-build representative adversarial perception "
                "review must close every run-bound requirement with hashed evidence."
            ),
        ))
    if not skill_benefit_cases:
        failures.append(issue(
            "release-skill-benefit-unproven",
            label,
            (
                "At least one representative case must show a supported "
                "skill-stronger result on project specificity or "
                "distinctiveness without novelty tax."
            ),
        ))
    expressive_review_cases = {
        case_id
        for case_id in qualified_families
        if isinstance(case_metadata.get(case_id), dict)
        and case_metadata[case_id].get("expressive_perception_gate") is True
    }
    quiet_review_cases = {
        case_id
        for case_id in qualified_families
        if isinstance(case_metadata.get(case_id), dict)
        and case_metadata[case_id].get("quiet_perception_gate") is True
    }
    if len(expressive_review_cases) < MIN_EXPRESSIVE_RELEASE_CASES:
        failures.append(issue(
            "release-expressive-rendered-coverage-incomplete",
            label,
            (
                "Rendered release evidence needs at least "
                f"{MIN_EXPRESSIVE_RELEASE_CASES} distinct marked Showcase or "
                "expressive cases whose counted perception reviews meet both "
                "absolute score floors; qualified: "
                f"{len(expressive_review_cases)}."
            ),
        ))
    if len(quiet_review_cases) < MIN_QUIET_RELEASE_CASES:
        failures.append(issue(
            "release-quiet-rendered-coverage-incomplete",
            label,
            (
                "Rendered release evidence needs at least "
                f"{MIN_QUIET_RELEASE_CASES} marked quiet-specific case whose "
                "counted perception review meets the direction, project "
                "specificity, and distinctiveness score floors without a "
                "visual-volume requirement; qualified: "
                f"{len(quiet_review_cases)}."
            ),
        ))
    if (
        image_generation_available_claimed
        and len(generated_media_review_cases)
        < MIN_GENERATED_MEDIA_RELEASE_CASES
    ):
        failures.append(issue(
            "release-generated-media-capability-coverage-missing",
            label,
            (
                "Image generation is declared available in this host's bound "
                "review evidence, so release evidence needs at least "
                f"{MIN_GENERATED_MEDIA_RELEASE_CASES} behaviorally qualified "
                "case marked generated_media_capability_gate with real "
                "generated artifacts and inspection evidence. An honest "
                "unavailable disposition does not trigger this gate."
            ),
        ))
    if len(route_family_review_cases) < MIN_ROUTE_FAMILY_RELEASE_CASES:
        failures.append(issue(
            "release-route-family-review-coverage-missing",
            label,
            (
                "Rendered release evidence needs at least "
                f"{MIN_ROUTE_FAMILY_RELEASE_CASES} behaviorally qualified "
                "Range Study with passing route-family analysis."
            ),
        ))
    if len(cultural_context_review_cases) < MIN_CULTURAL_CONTEXT_RELEASE_CASES:
        failures.append(issue(
            "release-cultural-context-review-coverage-missing",
            label,
            (
                "Rendered release evidence needs at least "
                f"{MIN_CULTURAL_CONTEXT_RELEASE_CASES} behaviorally qualified "
                "culturally central case accepted by a non-producer authority."
            ),
        ))

    cross_case_candidates = [
        (path, payload)
        for path, payload in matched
        if path in qualified_perception_paths
        and isinstance(payload.get("cross_case_analysis"), dict)
    ]
    cross_case_qualified = False
    cross_case_diagnostics: list[dict[str, str]] = []
    cross_case_path: str | None = None
    for path, payload in cross_case_candidates:
        candidate_failures = cross_case_analysis_failures(
            payload,
            qualified_family_records,
            case_metadata,
            str(path.relative_to(plugin)),
        )
        if not candidate_failures:
            cross_case_qualified = True
            cross_case_path = path.relative_to(plugin).as_posix()
            break
        if not cross_case_diagnostics:
            cross_case_diagnostics = candidate_failures
    if not cross_case_qualified:
        if cross_case_diagnostics:
            failures.extend(cross_case_diagnostics)
        else:
            failures.append(issue(
                "release-cross-case-analysis-missing",
                label,
                (
                    "A qualified independent perception review must include "
                    "cross-case house-style analysis bound to counted renders."
                ),
            ))
    details: dict[str, object] = {
        "qualified_case_build_families": qualified_families,
        "unqualified_case_build_families": unqualified_families,
        "adversarial_closed_cases": sorted(adversarial_closed_cases),
        "skill_benefit_cases": sorted(skill_benefit_cases),
        "expressive_perception_cases": sorted(expressive_review_cases),
        "quiet_perception_cases": sorted(quiet_review_cases),
        "image_generation_available_claimed": (
            image_generation_available_claimed
        ),
        "generated_media_capability_cases": sorted(
            generated_media_review_cases
        ),
        "route_family_showcase_cases": sorted(route_family_review_cases),
        "cultural_context_cases": sorted(cultural_context_review_cases),
        "cross_case_analysis": {
            "qualified": cross_case_qualified,
            "path": cross_case_path,
        },
    }
    return failures, details


def release_rendered_review_failures(
    host_name: str,
    matched: list[tuple[Path, dict[str, object]]],
    review_render_contexts: dict[Path, list[dict[str, object]]],
    host_review_paths: set[str],
    evidence_keys: set[str],
) -> list[dict[str, str]]:
    """Require attributable, separate review lenses and real responsive renders."""
    failures: list[dict[str, str]] = []
    label = f"maintainer/compatibility/matrix.yml:{host_name}"
    if not host_review_paths:
        failures.append(issue(
            "release-host-rendered-review-missing",
            label,
            "Rendered pass needs a current review matched to an eval run.",
        ))
    elif not (host_review_paths & evidence_keys):
        failures.append(issue(
            "release-host-review-evidence-unbound",
            label,
            "Rendered pass must cite a matched current review JSON.",
        ))

    perception_reviews = [
        (path, payload)
        for path, payload in matched
        if isinstance(payload.get("reviewer"), dict)
        and payload["reviewer"].get("lens") == "perception"
    ]
    implementation_reviews = [
        (path, payload)
        for path, payload in matched
        if isinstance(payload.get("reviewer"), dict)
        and payload["reviewer"].get("lens") == "implementation"
    ]
    if not perception_reviews:
        failures.append(issue(
            "release-perception-review-missing",
            label,
            "Rendered pass needs a current, attributable perception review.",
        ))
    if not implementation_reviews:
        failures.append(issue(
            "release-implementation-review-missing",
            label,
            (
                "Rendered pass needs a distinct implementation review with "
                "numeric accessibility coverage."
            ),
        ))

    qualified_independent = False
    for _path, payload in perception_reviews:
        reviewer = payload.get("reviewer")
        build = payload.get("build")
        if not isinstance(reviewer, dict) or not isinstance(build, dict):
            continue
        process = reviewer.get("process")
        if (
            reviewer.get("independent") is True
            and reviewer.get("id") != build.get("producer_id")
            and isinstance(process, dict)
            and process.get("method") in INDEPENDENT_REVIEW_METHODS
            and isinstance(process.get("id"), str)
        ):
            qualified_independent = True
            break
    if not qualified_independent:
        failures.append(issue(
            "release-independent-review-missing",
            label,
            (
                "Perception coverage needs a distinct reviewer and attributable "
                "independent process, not only a boolean."
            ),
        ))

    distinct_lens_processes = any(
        perception_path != implementation_path
        and isinstance(perception_payload.get("reviewer"), dict)
        and isinstance(implementation_payload.get("reviewer"), dict)
        and isinstance(perception_payload["reviewer"].get("process"), dict)
        and isinstance(implementation_payload["reviewer"].get("process"), dict)
        and perception_payload["reviewer"]["process"].get("id")
        != implementation_payload["reviewer"]["process"].get("id")
        and perception_payload["reviewer"]["process"].get("evidence_path")
        != implementation_payload["reviewer"]["process"].get("evidence_path")
        for perception_path, perception_payload in perception_reviews
        for implementation_path, implementation_payload in implementation_reviews
    )
    if (
        perception_reviews
        and implementation_reviews
        and not distinct_lens_processes
    ):
        failures.append(issue(
            "release-review-processes-not-distinct",
            label,
            (
                "Perception and implementation coverage need distinct review "
                "records, process IDs, and process evidence."
            ),
        ))

    verified_renders = [
        record
        for review_path, _payload in perception_reviews
        for record in review_render_contexts.get(review_path, [])
    ]
    mobile_paths = {
        str(record["path"]).casefold()
        for record in verified_renders
        if record.get("kind") == "mobile"
    }
    desktop_paths = {
        str(record["path"]).casefold()
        for record in verified_renders
        if record.get("kind") == "desktop"
    }
    if not mobile_paths or not desktop_paths or mobile_paths & desktop_paths:
        failures.append(issue(
            "release-responsive-review-coverage",
            label,
            (
                "Perception review needs distinct, decoded, hash-bound mobile "
                "and desktop PNG evidence."
            ),
        ))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    plugin_default = Path(__file__).resolve().parents[2]
    parser.add_argument("--plugin-root", type=Path, default=plugin_default)
    parser.add_argument(
        "--home",
        type=Path,
        default=Path.home(),
        help="Home root used to rehydrate portable ~/ route evidence.",
    )
    parser.add_argument(
        "--codex-validator",
        type=Path,
        help=(
            "Absolute external Plugin Creator validate_plugin.py path used "
            "to replay the recorded Codex static validation."
        ),
    )
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--allow-overdue", action="store_true")
    parser.add_argument(
        "--release",
        action="store_true",
        help="Require frozen identity and completed, attributable release evidence.",
    )
    args = parser.parse_args()
    if BOOTSTRAP_FAILURES:
        emit({
            "ok": False,
            "failures": [{
                "code": "dependency-missing",
                "path": str(Path(__file__).resolve()),
                "message": (
                    "Install maintainer/requirements-dev.lock with --require-hashes. Missing: "
                    + "; ".join(BOOTSTRAP_FAILURES)
                ),
            }],
            "warnings": [],
            "details": {},
        })
        return 2
    try:
        from validate_evidence import validate as validate_evidence
    except ImportError as exc:
        emit({
            "ok": False,
            "failures": [issue(
                "dependency-missing",
                Path(__file__).resolve(),
                f"Install maintainer/requirements-dev.lock with --require-hashes: {exc}",
            )],
            "warnings": [],
            "details": {},
        })
        return 2
    try:
        plugin = absolute(args.plugin_root)
        if (
            args.codex_validator is not None
            and not args.codex_validator.is_absolute()
        ):
            raise ToolFailure(
                "codex-plugin-validator-path-not-absolute",
                "--codex-validator must be an absolute external path.",
                args.codex_validator,
            )
        skill = plugin / "skills" / "design-dna"
        maintainer = plugin / "maintainer"
        schemas = maintainer / "schemas"
        failures: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        details: dict[str, object] = {}
        failures.extend(plugin_skill_surface_failures(plugin))
        failures.extend(runtime_cache_failures(skill, label_root=plugin))
        failures.extend(maintainer_cache_failures(plugin))

        for schema_path in sorted(schemas.glob("*.json")):
            try:
                Draft202012Validator.check_schema(load_json(schema_path))
            except Exception as exc:
                failures.append({"code": "invalid-schema-document", "path": schema_path.relative_to(plugin).as_posix(), "message": str(exc)})

        release = load_json(skill / "release.json")
        manifest = load_json(plugin / ".codex-plugin" / "plugin.json")
        claude_manifest = load_json(plugin / ".claude-plugin" / "plugin.json")
        failures += schema_validate(release, schemas / "release.schema.json", "skills/design-dna/release.json")
        failures += schema_validate(manifest, schemas / "plugin.schema.json", ".codex-plugin/plugin.json")
        failures += schema_validate(
            claude_manifest,
            schemas / "claude-plugin.schema.json",
            ".claude-plugin/plugin.json",
        )
        if isinstance(release, dict) and isinstance(manifest, dict) and release.get("version") != manifest.get("version"):
            failures.append({"code": "version-mismatch", "path": ".codex-plugin/plugin.json", "message": f"{manifest.get('version')} != {release.get('version')}"})
        if (
            isinstance(release, dict)
            and isinstance(claude_manifest, dict)
            and release.get("version") != claude_manifest.get("version")
        ):
            failures.append({
                "code": "version-mismatch",
                "path": ".claude-plugin/plugin.json",
                "message": (
                    f"{claude_manifest.get('version')} != "
                    f"{release.get('version')}"
                ),
            })

        sbom_path = maintainer / "sbom.spdx.json"
        try:
            sbom_payload = load_json(sbom_path)
            failures += schema_validate(
                sbom_payload,
                schemas / "sbom.schema.json",
                "maintainer/sbom.spdx.json",
            )
            sbom_tool = import_local_script("build_sbom")
            sbom_tool.validate_sbom(sbom_payload, plugin)
            creation_info = (
                sbom_payload.get("creationInfo")
                if isinstance(sbom_payload, dict)
                else None
            )
            created_at = (
                creation_info.get("created")
                if isinstance(creation_info, dict)
                else None
            )
            if not isinstance(created_at, str):
                raise ToolFailure(
                    "sbom-created-at-invalid",
                    "SBOM creationInfo.created is missing.",
                    sbom_path,
                )
            if (
                sbom_tool.generate_sbom(plugin, created_at=created_at)
                != sbom_payload
            ):
                failures.append(issue(
                    "sbom-drift",
                    "maintainer/sbom.spdx.json",
                    (
                        "SBOM differs from the current runtime, manifests, "
                        "license, or dependency locks."
                    ),
                ))
            elif isinstance(sbom_payload, dict):
                details["sbom_packages"] = len(
                    sbom_payload.get("packages", [])
                )
        except (OSError, UnicodeError, ValueError, ToolFailure) as exc:
            failures.append(issue(
                "sbom-invalid",
                "maintainer/sbom.spdx.json",
                str(exc),
            ))

        compatibility_path = maintainer / "compatibility" / "matrix.yml"
        compatibility: object = {}
        try:
            compatibility = strict_yaml(compatibility_path)
            failures += schema_validate(
                compatibility,
                schemas / "compatibility.schema.json",
                "maintainer/compatibility/matrix.yml",
            )
            environment_claim_issues = compatibility_environment_failures(
                compatibility,
                plugin,
            )
            (failures if args.release else warnings).extend(
                environment_claim_issues
            )
            if (
                isinstance(compatibility, dict)
                and isinstance(release, dict)
                and compatibility.get("package_version") != release.get("version")
            ):
                failures.append({
                    "code": "compatibility-version-mismatch",
                    "path": "maintainer/compatibility/matrix.yml",
                    "message": f"{compatibility.get('package_version')} != {release.get('version')}",
                })
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            failures.append({
                "code": "invalid-compatibility-matrix",
                "path": "maintainer/compatibility/matrix.yml",
                "message": str(exc),
            })

        try:
            agent = strict_yaml(skill / "agents" / "openai.yaml")
            failures += schema_validate(agent, schemas / "agent.schema.json", "skills/design-dna/agents/openai.yaml")
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            failures.append({"code": "invalid-yaml", "path": "skills/design-dna/agents/openai.yaml", "message": str(exc)})

        owner_policy_path = skill / "policy" / "owner-defaults.yml"
        owner_policy: object = {}
        if owner_policy_path.is_file():
            try:
                owner_policy = strict_yaml(owner_policy_path)
                failures += schema_validate(owner_policy, schemas / "owner-policy.schema.json", "skills/design-dna/policy/owner-defaults.yml")
            except (OSError, UnicodeError, yaml.YAMLError) as exc:
                failures.append({"code": "invalid-yaml", "path": "skills/design-dna/policy/owner-defaults.yml", "message": str(exc)})
        else:
            failures.append({
                "code": "owner-policy-missing",
                "path": "skills/design-dna/policy/owner-defaults.yml",
                "message": "Evidence bases and runtime defaults require the owner policy.",
            })
        failures.extend(owner_policy_example_failures(
            skill / "templates" / "owner-policy.example.yml",
            schemas / "owner-policy.schema.json",
        ))

        try:
            skill_meta, _ = frontmatter(skill / "SKILL.md")
            if not isinstance(skill_meta, dict) or set(skill_meta) != {"name", "description"} or skill_meta.get("name") != "design-dna":
                failures.append({"code": "invalid-skill-frontmatter", "path": "skills/design-dna/SKILL.md", "message": "Only name and description are allowed; name must be design-dna."})
        except (OSError, UnicodeError, yaml.YAMLError, ValueError) as exc:
            failures.append({"code": "invalid-skill-frontmatter", "path": "skills/design-dna/SKILL.md", "message": str(exc)})
        failures.extend(runtime_reference_reachability_failures(
            skill,
            label_root=plugin,
        ))

        legacy_font_policy = skill / "policy" / "type-convergence-watch.yml"
        if legacy_font_policy.exists():
            failures.append({
                "code": "legacy-font-selection-runtime",
                "path": legacy_font_policy.relative_to(plugin).as_posix(),
                "message": (
                    "Named-family convergence policy is maintainer research, "
                    "not an installed runtime constraint."
                ),
            })

        legacy_font_runtime_tokens = (
            "type-convergence-watch",
            "--type-watch",
            "type_watch",
        )
        text_count = 0
        for path in walk_files(
            plugin,
            ignored_directory_names=LOCAL_TOOL_DIRECTORY_NAMES,
        ):
            if path.suffix.lower() not in {".md", ".json", ".yaml", ".yml", ".py", ".txt"}:
                continue
            text_count += 1
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeError as exc:
                failures.append({"code": "invalid-utf8", "path": path.relative_to(plugin).as_posix(), "message": str(exc)})
                continue
            if TODO.search(text):
                failures.append({"code": "placeholder-todo", "path": path.relative_to(plugin).as_posix(), "message": "Unresolved TODO marker."})
            if (
                UNSUPPORTED_PROMISE.search(text)
                and (
                    is_within(path, skill)
                    or path == plugin / ".codex-plugin" / "plugin.json"
                )
            ):
                failures.append({"code": "unsupported-authorship-promise", "path": path.relative_to(plugin).as_posix(), "message": "Do not promise undetectability or human authorship."})
            relative = path.relative_to(plugin)
            if is_within(path, skill):
                found_legacy_tokens = [
                    token
                    for token in legacy_font_runtime_tokens
                    if token in text
                ]
                if found_legacy_tokens:
                    failures.append({
                        "code": "legacy-font-selection-runtime",
                        "path": relative.as_posix(),
                        "message": (
                            "Installed runtime still contains removed named-family "
                            "selection contract(s): "
                            + ", ".join(found_legacy_tokens)
                        ),
                    })
            if "__DESIGN_DNA_VERSION__" in text:
                if not (
                    path.suffix.lower() == ".py"
                    or (
                        is_within(path, skill / "templates")
                        and path.suffix.lower()
                        in {".json", ".md", ".yml", ".yaml"}
                    )
                ):
                    failures.append({
                        "code": "unresolved-template-token",
                        "path": relative.as_posix(),
                        "message": "Template token is allowed only in runtime templates.",
                    })
            if (
                is_within(path, skill)
                and path.suffix.lower() == ".md"
                and len(text.splitlines()) > 100
                and not re.search(
                    r"(?mi)^##\s+(?:contents|table of contents|runtime map)\s*$",
                    text,
                )
            ):
                failures.append({
                    "code": "long-markdown-without-toc",
                    "path": relative.as_posix(),
                    "message": "Runtime Markdown over 100 lines needs a concise contents map.",
                })
        details["text_files"] = text_count

        forbidden_runtime_names = {
            "readme.md",
            "install.md",
            "installation.md",
            "changelog.md",
        }
        for path in walk_files(skill):
            if path.name.casefold() in forbidden_runtime_names:
                failures.append({
                    "code": "runtime-maintainer-document",
                    "path": path.relative_to(plugin).as_posix(),
                    "message": "Installation, changelog, and general README material stays outside the runtime skill.",
                })
        link_failures, link_warnings = check_links(plugin, online=args.online, timeout=10)
        failures.extend(link_failures)
        warnings.extend(link_warnings)

        evidence_failures, evidence_warnings, evidence_details = validate_evidence(
            plugin, schemas / "evidence-frontmatter.schema.json",
            online=args.online,
            strict_due=(args.release or not args.allow_overdue),
            release_mode=args.release,
        )
        failures.extend(evidence_failures)
        warnings.extend(evidence_warnings)
        details["evidence"] = evidence_details

        fixtures_dir = maintainer / "evals" / "fixtures"
        suite_schema_path = maintainer / "evals" / "schema.json"
        result_schema_path = schemas / "eval-result.schema.json"
        harness_path = maintainer / "scripts" / "run_evals.py"
        trusted_adapters: set[tuple[str, str, str, str]] = set()
        trusted_adapter_path = (
            maintainer / "compatibility" / "trusted-host-adapters.yml"
        )
        try:
            trusted_adapter_payload = strict_yaml(trusted_adapter_path)
            trusted_adapter_label = (
                "maintainer/compatibility/trusted-host-adapters.yml"
            )
            failures += schema_validate(
                trusted_adapter_payload,
                schemas / "trusted-host-adapters.schema.json",
                trusted_adapter_label,
            )
            adapter_failures, trusted_adapters = trusted_adapter_failures(
                trusted_adapter_payload,
                plugin,
                trusted_adapter_label,
            )
            failures.extend(adapter_failures)
        except (OSError, UnicodeError, yaml.YAMLError, ValueError) as exc:
            failures.append(issue(
                "invalid-trusted-adapter-registry",
                "maintainer/compatibility/trusted-host-adapters.yml",
                str(exc),
            ))
        fixture_failures, fixture_count = validate_fixtures(
            fixtures_dir, suite_schema_path
        )
        failures.extend(fixture_failures)
        fixture_suites, catalog_failures = fixture_catalog(fixtures_dir)
        failures.extend(catalog_failures)
        details["eval_cases"] = fixture_count

        result_count = 0
        eval_payloads: list[tuple[Path, dict[str, object]]] = []
        for result_path in sorted((maintainer / "evals" / "results").glob("*.json")):
            result_count += 1
            try:
                assert_no_reparse_path(result_path, stop=plugin)
                result_payload = load_json(result_path)
                result_label = str(result_path.relative_to(plugin))
                failures += schema_validate(
                    result_payload,
                    result_schema_path,
                    result_label,
                )
                if isinstance(result_payload, dict):
                    failures += eval_semantic_failures(
                        result_payload,
                        fixture_suites,
                        result_label,
                        harness_path=harness_path,
                        suite_schema_path=suite_schema_path,
                        result_schema_path=result_schema_path,
                        result_path=result_path,
                        release_mode=args.release,
                        trusted_adapters=trusted_adapters,
                    )
                    eval_payloads.append((result_path, result_payload))
            except ToolFailure as exc:
                failures.append(exc.issue.as_dict())
        failures.extend(eval_replay_failures(eval_payloads))
        eval_payload_by_path = {
            absolute(path): payload
            for path, payload in eval_payloads
        }
        details["eval_results"] = result_count

        review_count = 0
        review_payloads: list[tuple[Path, dict[str, object]]] = []
        review_render_contexts: dict[Path, list[dict[str, object]]] = {}
        for review_path in sorted((maintainer / "evals" / "reviews").glob("*.json")):
            review_count += 1
            try:
                assert_no_reparse_path(review_path, stop=plugin)
                review_payload = load_json(review_path)
                review_label = str(review_path.relative_to(plugin))
                failures += schema_validate(
                    review_payload,
                    schemas / "design-review.schema.json",
                    review_label,
                )
                if isinstance(review_payload, dict):
                    verified_contexts: list[dict[str, object]] = []
                    failures += review_semantic_failures(
                        review_payload,
                        plugin,
                        review_label,
                        release_mode=args.release,
                        verified_contexts_out=verified_contexts,
                    )
                    failures += review_evaluation_binding_failures(
                        review_payload,
                        plugin,
                        review_label,
                        eval_payload_by_path,
                        release_mode=args.release,
                    )
                    review_render_contexts[review_path] = verified_contexts
                    review_payloads.append((review_path, review_payload))
            except ToolFailure as exc:
                failures.append(exc.issue.as_dict())
        details["design_reviews"] = review_count

        release_manifest = maintainer / "release-manifest.json"
        current_identity: dict[str, object] | None
        try:
            current_identity = package_manifest(skill)
        except ToolFailure as exc:
            failures.append(exc.issue.as_dict())
            current_identity = None
        recorded_release_manifest: object = {}
        if release_manifest.is_file():
            assert_no_reparse_path(release_manifest, stop=plugin)
            expected = load_json(release_manifest)
            recorded_release_manifest = expected
            failures += schema_validate(
                expected,
                schemas / "manifest.schema.json",
                "maintainer/release-manifest.json",
            )
            failures += manifest_semantic_failures(
                expected,
                "maintainer/release-manifest.json",
            )
            if (
                current_identity is not None
                and (
                    not isinstance(expected, dict)
                    or comparable(expected) != comparable(current_identity)
                )
            ):
                failures.append(issue(
                    "release-manifest-drift",
                    "maintainer/release-manifest.json",
                    "Package inputs differ from the recorded checksummed release identity.",
                ))
            elif current_identity is None:
                failures.append(issue(
                    "release-manifest-identity-unavailable",
                    "maintainer/release-manifest.json",
                    (
                        "The current package identity could not be generated; "
                        "the recorded release manifest cannot be confirmed."
                    ),
                ))
        else:
            target = failures if args.release else warnings
            target.extend((
                issue(
                    "release-manifest-missing",
                    "maintainer/release-manifest.json",
                    "Generate the release manifest before release.",
                ),
                issue(
                    "release-manifest-identity-unavailable",
                    "maintainer/release-manifest.json",
                    (
                        "No recorded checksummed release identity is "
                        "available to compare with the current package."
                    ),
                ),
            ))

        ci_failures, ci_details = ci_contract_failures(
            compatibility,
            plugin,
            schemas / "ci-run-import.schema.json",
            schemas / "test-attestation.schema.json",
            recorded_release_manifest,
            release_mode=args.release,
        )
        failures.extend(ci_failures)
        details["ci_release_contract"] = ci_details

        proof_target = failures if args.release else warnings
        attestation_root = maintainer / "attestations"
        test_attestation_path = attestation_root / "test-attestation.json"
        route_verification_path = attestation_root / "route-verification.json"
        install_lifecycle_path = attestation_root / "install-lifecycle.json"
        codex_plugin_validation_path = (
            attestation_root / "codex-plugin-validation.json"
        )
        assert_no_reparse_path(test_attestation_path, stop=plugin)
        assert_no_reparse_path(route_verification_path, stop=plugin)
        assert_no_reparse_path(install_lifecycle_path, stop=plugin)
        assert_no_reparse_path(codex_plugin_validation_path, stop=plugin)
        if test_attestation_path.is_file():
            try:
                assert_no_reparse_path(test_attestation_path, stop=plugin)
                test_attestation = load_json(test_attestation_path)
                proof_target.extend(test_attestation_failures(
                    test_attestation,
                    plugin,
                    schemas / "test-attestation.schema.json",
                    recorded_release_manifest,
                ))
            except ToolFailure as exc:
                proof_target.append(exc.issue.as_dict())
        else:
            proof_target.append(issue(
                "release-test-attestation-missing",
                "maintainer/attestations/test-attestation.json",
                "After source freeze, run attest_tests.py before generating the final release manifest.",
            ))
        if route_verification_path.is_file():
            try:
                assert_no_reparse_path(route_verification_path, stop=plugin)
                route_verification = load_json(route_verification_path)
                proof_target.extend(route_verification_failures(
                    route_verification,
                    plugin,
                    schemas / "route-verification.schema.json",
                    recorded_release_manifest,
                    compatibility,
                    home=absolute(args.home),
                ))
            except ToolFailure as exc:
                proof_target.append(exc.issue.as_dict())
        else:
            proof_target.append(issue(
                "release-route-verification-missing",
                "maintainer/attestations/route-verification.json",
                (
                    "After syncing, run detect_routes.py with explicit --home "
                    "and --output before generating the final release manifest."
                ),
            ))
        if install_lifecycle_path.is_file():
            try:
                install_lifecycle = load_json(install_lifecycle_path)
                proof_target.extend(install_lifecycle_attestation_failures(
                    install_lifecycle,
                    plugin,
                    schemas
                    / "install-lifecycle-attestation.schema.json",
                    recorded_release_manifest,
                    release,
                ))
            except ToolFailure as exc:
                proof_target.append(exc.issue.as_dict())
        else:
            proof_target.append(issue(
                "release-install-lifecycle-missing",
                "maintainer/attestations/install-lifecycle.json",
                (
                    "After source freeze, run "
                    "attest_install_lifecycle.py before generating the final "
                    "release manifest."
                ),
            ))
        if codex_plugin_validation_path.is_file():
            try:
                codex_plugin_validation = load_json(
                    codex_plugin_validation_path
                )
                proof_target.extend(codex_plugin_attestation_failures(
                    codex_plugin_validation,
                    plugin,
                    schemas
                    / "codex-plugin-validation-attestation.schema.json",
                    recorded_release_manifest,
                    release,
                    validator_path=(
                        absolute(args.codex_validator)
                        if args.codex_validator is not None
                        else None
                    ),
                ))
            except ToolFailure as exc:
                proof_target.append(exc.issue.as_dict())
        else:
            proof_target.append(issue(
                "release-codex-plugin-attestation-missing",
                "maintainer/attestations/codex-plugin-validation.json",
                (
                    "After source freeze, run attest_codex_plugin.py with "
                    "the external Plugin Creator validator before generating "
                    "the final release manifest."
                ),
            ))
        codex_host = (
            compatibility.get("hosts", {}).get("codex", {})
            if isinstance(compatibility, dict)
            and isinstance(compatibility.get("hosts"), dict)
            else {}
        )
        if (
            args.release
            and isinstance(codex_host, dict)
            and codex_host.get("static_validation") == "passed"
            and args.codex_validator is None
        ):
            failures.append(issue(
                "release-codex-validator-live-path-required",
                "maintainer/compatibility/matrix.yml:hosts.codex",
                (
                    "A Codex static-validation pass requires "
                    "--codex-validator so strict audit can replay the exact "
                    "external Plugin Creator validator."
                ),
            ))
        details["release_proofs"] = {
            "test_attestation": test_attestation_path.is_file(),
            "route_verification": route_verification_path.is_file(),
            "install_lifecycle": install_lifecycle_path.is_file(),
            "codex_plugin_validation": (
                codex_plugin_validation_path.is_file()
            ),
        }

        if args.release:
            if result_count == 0:
                failures.append({
                    "code": "release-eval-result-missing",
                    "path": "maintainer/evals/results",
                    "message": "A release needs at least one attributable controlled evaluation result.",
                })
            if review_count == 0:
                failures.append({
                    "code": "release-design-review-missing",
                    "path": "maintainer/evals/reviews",
                    "message": "A release needs at least one rubric-backed rendered review.",
                })
            current_hash = (
                current_identity.get("content_sha256")
                if isinstance(current_identity, dict)
                else None
            )
            current_version = (
                current_identity.get("version")
                if isinstance(current_identity, dict)
                else None
            )
            current_evals: list[tuple[Path, dict[str, object]]] = []
            current_reviews: list[tuple[Path, dict[str, object]]] = []
            for result_path, payload in eval_payloads:
                package_record = payload.get("package", {})
                if (
                    isinstance(package_record, dict)
                    and (
                        package_record.get("content_sha256") != current_hash
                        or package_record.get("version") != current_version
                    )
                ):
                    failures.append({
                        "code": "stale-eval-result",
                        "path": str(result_path.relative_to(plugin)),
                        "message": f"{package_record.get('content_sha256')} is not the current runtime identity.",
                    })
                else:
                    current_evals.append((result_path, payload))
            for review_path, payload in review_payloads:
                build = payload.get("build", {})
                conclusion = payload.get("conclusion", {})
                if (
                    isinstance(build, dict)
                    and (
                        build.get("content_sha256") != current_hash
                        or build.get("skill_version") != current_version
                    )
                ):
                    failures.append({
                        "code": "stale-design-review",
                        "path": str(review_path.relative_to(plugin)),
                        "message": f"{build.get('content_sha256')} is not the current runtime identity.",
                    })
                else:
                    current_reviews.append((review_path, payload))
                if (
                    isinstance(conclusion, dict)
                    and conclusion.get("decision") not in {"pass", "pass-with-limitations"}
                ):
                    failures.append({
                        "code": "release-review-not-passed",
                        "path": str(review_path.relative_to(plugin)),
                        "message": str(conclusion.get("decision")),
                    })

            current_run_index: defaultdict[
                tuple[object, object, object, object],
                list[tuple[Path, dict[str, object]]],
            ] = defaultdict(list)
            current_skill_runs_by_host: defaultdict[
                str,
                list[tuple[Path, dict[str, object]]],
            ] = defaultdict(list)
            for result_path, payload in current_evals:
                for run in payload.get("runs", []):
                    if not isinstance(run, dict):
                        continue
                    build_identity = run.get("workspace_sha256")
                    key = (
                        run.get("case"),
                        run.get("run_id"),
                        run.get("host"),
                        build_identity,
                    )
                    current_run_index[key].append((result_path, run))
                    if run.get("variant") == "skill":
                        current_skill_runs_by_host[str(run.get("host"))].append(
                            (result_path, run)
                        )
                        if run.get("passed") is not True:
                            failures.append(issue(
                                "release-skill-run-failed",
                                result_path.relative_to(plugin),
                                str(run.get("run_id")),
                            ))

            matched_reviews_by_host: defaultdict[
                str,
                list[tuple[Path, dict[str, object]]],
            ] = defaultdict(list)
            closure_qualified_by_host: defaultdict[str, set[Path]] = defaultdict(
                set
            )
            for review_path, payload in current_reviews:
                build = payload.get("build")
                if not isinstance(build, dict):
                    continue
                key = (
                    payload.get("case_id"),
                    payload.get("run_id"),
                    build.get("host"),
                    build.get("identity"),
                )
                candidates = [
                    pair
                    for pair in current_run_index.get(key, [])
                    if pair[1].get("variant") == "skill"
                    and pair[1].get("passed") is True
                ]
                if len(candidates) != 1:
                    failures.append(issue(
                        "release-review-run-unattributed",
                        review_path.relative_to(plugin),
                        (
                            "Review must match exactly one current passed skill run "
                            "by case_id, run_id, host, and build identity."
                        ),
                    ))
                    continue
                host_key = str(build.get("host"))
                closure_failures, closure_qualified = (
                    review_contract_closure_failures(
                        payload,
                        candidates[0][1].get("review_contract"),
                        str(review_path.relative_to(plugin)),
                    )
                )
                failures.extend(closure_failures)
                if closure_qualified:
                    closure_qualified_by_host[host_key].add(review_path)
                matched_reviews_by_host[host_key].append(
                    (review_path, payload)
                )

            if isinstance(compatibility, dict):
                hosts = compatibility.get("hosts", {})
                release_coverage_details: dict[str, object] = {}
                for host_name in ("codex", "claude_code"):
                    host = hosts.get(host_name, {}) if isinstance(hosts, dict) else {}
                    if not isinstance(host, dict):
                        continue
                    failures.extend(
                        release_host_completion_failures(host_name, host)
                    )
                    failures.extend(
                        release_host_discovery_failures(
                            host_name,
                            compatibility,
                        )
                    )
                    evidence_paths = host.get("evidence", [])
                    if not evidence_paths:
                        failures.append({
                            "code": "release-host-evidence-missing",
                            "path": f"maintainer/compatibility/matrix.yml:{host_name}",
                            "message": "Host checks need attributable evidence paths.",
                        })
                    path_failures, evidence_keys = validate_evidence_paths(
                        evidence_paths,
                        plugin,
                        f"maintainer/compatibility/matrix.yml:{host_name}",
                    )
                    failures.extend(path_failures)
                    if (
                        host_name == "codex"
                        and host.get("static_validation") == "passed"
                        and (
                            "maintainer/attestations/"
                            "codex-plugin-validation.json"
                        ) not in evidence_keys
                    ):
                        failures.append(issue(
                            "release-codex-static-validation-unbound",
                            (
                                "maintainer/compatibility/matrix.yml:"
                                "hosts.codex"
                            ),
                            (
                                "Codex static validation must cite the "
                                "current external Plugin Creator attestation."
                            ),
                        ))

                    host_result_paths = {
                        result_path.relative_to(plugin).as_posix().casefold()
                        for result_path, _payload in current_evals
                        if _payload.get("host") == host_name
                    }
                    host_review_paths = {
                        review_path.relative_to(plugin).as_posix().casefold()
                        for review_path, _payload in matched_reviews_by_host[host_name]
                    }
                    behavioral_status = host.get("isolated_behavioral_eval")
                    behavioral_coverage: dict[str, object] = {
                        "qualified_cases": [],
                        "cases": {},
                    }
                    if behavioral_status == "passed":
                        if not (host_result_paths & evidence_keys):
                            failures.append(issue(
                                "release-host-eval-evidence-unbound",
                                f"maintainer/compatibility/matrix.yml:{host_name}",
                                "Behavioral pass must cite a current result JSON for this host.",
                            ))
                        host_skill_runs = current_skill_runs_by_host[host_name]
                        if not any(run.get("passed") is True for _path, run in host_skill_runs):
                            failures.append(issue(
                                "release-host-passed-run-missing",
                                f"maintainer/compatibility/matrix.yml:{host_name}",
                                "Behavioral pass needs a current passed skill run.",
                            ))
                        unbound_passed = [
                            run
                            for _path, run in host_skill_runs
                            if run.get("passed") is True
                            and run.get("host_native_evidence_status") != "bound"
                        ]
                        bound = any(
                            run.get("passed") is True
                            and run.get("host_native_evidence_status") == "bound"
                            for _path, run in host_skill_runs
                        )
                        if not bound or unbound_passed:
                            failures.append(issue(
                                "release-host-native-evidence-missing",
                                f"maintainer/compatibility/matrix.yml:{host_name}",
                                (
                                    "Behavioral pass needs separately bound host-native "
                                    "adapter or telemetry evidence for every passed skill "
                                    "run; driver reports and limitations cannot substitute."
                                ),
                            ))
                        host_runs = [
                            (result_path, run)
                            for result_path, result_payload in current_evals
                            if result_payload.get("host") == host_name
                            for run in result_payload.get("runs", [])
                            if isinstance(run, dict)
                        ]
                        (
                            coverage_failures,
                            behavioral_coverage,
                        ) = release_behavioral_coverage_failures(
                            host_name,
                            host_runs,
                        )
                        failures.extend(coverage_failures)

                    if host.get("rendered_eval") == "passed":
                        failures.extend(release_rendered_review_failures(
                            host_name,
                            matched_reviews_by_host[host_name],
                            review_render_contexts,
                            host_review_paths,
                            evidence_keys,
                        ))
                        (
                            representative_failures,
                            rendered_coverage,
                        ) = release_representative_review_failures(
                            host_name,
                            behavioral_coverage,
                            matched_reviews_by_host[host_name],
                            review_render_contexts,
                            closure_qualified_by_host[host_name],
                            evidence_keys,
                            plugin,
                        )
                        failures.extend(representative_failures)
                    else:
                        rendered_coverage = {
                            "qualified_case_build_families": {},
                            "adversarial_closed_cases": [],
                        }
                    release_coverage_details[host_name] = {
                        "behavioral": behavioral_coverage,
                        "rendered": rendered_coverage,
                        "status": {
                            "isolated_behavioral_eval": behavioral_status,
                            "rendered_eval": host.get("rendered_eval"),
                        },
                    }
                details["release_coverage"] = release_coverage_details

        emit({"ok": not failures, "failures": failures, "warnings": warnings, "details": details})
        return 1 if failures else 0
    except ToolFailure as exc:
        emit({"ok": False, "failures": [exc.issue.as_dict()], "warnings": []})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
