#!/usr/bin/env python3
"""Run the exact maintainer unittest suite and atomically attest its result."""

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
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from jsonschema import Draft202012Validator, FormatChecker
try:
    from packaging.markers import default_environment
    from packaging.requirements import InvalidRequirement, Requirement
except ImportError as exc:  # pragma: no cover - exercised without dev dependencies
    default_environment = None  # type: ignore[assignment]
    InvalidRequirement = ValueError  # type: ignore[assignment,misc]
    Requirement = None  # type: ignore[assignment,misc]
    PACKAGING_IMPORT_ERROR: str | None = str(exc)
else:
    PACKAGING_IMPORT_ERROR = None

from build_manifest import (
    EXECUTABLE_MAINTAINER_TREES,
    identity_group_sha256,
)
from common import (
    ToolFailure,
    absolute,
    assert_no_reparse_path,
    emit,
    is_within,
    load_json,
    reject_compiled_python_residue,
    strict_format_checker,
)


UNITTEST_ARGUMENTS = (
    "-B",
    "-m",
    "unittest",
    "discover",
    "-s",
    "maintainer/tests",
    "-p",
    "test_*.py",
    "-v",
)
ATTESTED_INPUTS = {
    "tests_sha256": ("maintainer/tests",),
    "tooling_sha256": ("maintainer/scripts",),
    "schemas_sha256": ("maintainer/schemas",),
    "requirements_sha256": ("maintainer/requirements-dev.txt",),
}
PIN = re.compile(
    r"(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)=="
    r"(?P<version>[A-Za-z0-9][A-Za-z0-9_.+!-]*)"
)
SUPPORTED_PYTHON_VERSIONS = ("3.10", "3.11", "3.12", "3.13", "3.14")
SUMMARY = re.compile(r"(?m)^Ran\s+(?P<count>[0-9]+)\s+tests?\s+in\s+")
STATUS = re.compile(r"(?m)^(?P<status>OK|FAILED)(?:\s+\((?P<counts>[^)]*)\))?\s*$")
COUNT_KEYS = {
    "failures": "failures",
    "errors": "errors",
    "skipped": "skipped",
    "expected failures": "expected_failures",
    "unexpected successes": "unexpected_successes",
}
Runner = Callable[[Path, list[str]], subprocess.CompletedProcess[bytes]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalized_distribution(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).casefold()


def applies_to_supported_python(requirement: Requirement) -> bool:
    if default_environment is None:
        return False
    if requirement.marker is None:
        return True
    for version in SUPPORTED_PYTHON_VERSIONS:
        environment = default_environment()
        environment.update({
            "extra": "",
            "python_version": version,
            "python_full_version": version + ".0",
        })
        if requirement.marker.evaluate(environment):
            return True
    return False


def pinned_dependencies(plugin_root: Path) -> list[dict[str, str]]:
    requirements = plugin_root / "maintainer" / "requirements-dev.txt"
    if Requirement is None:
        raise ToolFailure(
            "test-attestation-dependency-parser-missing",
            (
                "Install maintainer/requirements-dev.txt; packaging is "
                f"required to verify the dependency closure: "
                f"{PACKAGING_IMPORT_ERROR}"
            ),
            requirements,
        )
    assert_no_reparse_path(requirements, stop=plugin_root)
    try:
        first = requirements.read_text(encoding="utf-8")
        second = requirements.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ToolFailure(
            "test-attestation-requirements-unreadable",
            str(exc),
            requirements,
        ) from exc
    if first != second:
        raise ToolFailure(
            "test-attestation-input-unstable",
            "requirements-dev.txt changed while it was read.",
            requirements,
        )
    pins: dict[str, tuple[str, str]] = {}
    for number, raw_line in enumerate(first.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN.fullmatch(line)
        if not match:
            raise ToolFailure(
                "test-attestation-requirement-not-pinned",
                f"Line {number} must use an exact name==version pin.",
                requirements,
            )
        display_name = match.group("name")
        normalized = normalized_distribution(display_name)
        if normalized in pins:
            raise ToolFailure(
                "test-attestation-requirement-duplicate",
                f"Duplicate dependency pin: {display_name}.",
                requirements,
            )
        pins[normalized] = (display_name, match.group("version"))
    if not pins:
        raise ToolFailure(
            "test-attestation-requirements-empty",
            "At least one pinned maintainer dependency is required.",
            requirements,
        )
    records: list[dict[str, str]] = []
    for normalized, (display_name, pinned) in sorted(pins.items()):
        try:
            installed = importlib.metadata.version(display_name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise ToolFailure(
                "test-attestation-dependency-missing",
                f"{display_name}=={pinned} is not installed.",
                requirements,
            ) from exc
        if installed != pinned:
            raise ToolFailure(
                "test-attestation-dependency-mismatch",
                f"{display_name} {installed} != pinned {pinned}.",
                requirements,
            )
        records.append({
            "name": normalized,
            "pinned": pinned,
            "installed": installed,
        })
    for _normalized, (display_name, _pinned) in sorted(pins.items()):
        for raw_requirement in importlib.metadata.requires(display_name) or []:
            try:
                requirement = Requirement(raw_requirement)
            except InvalidRequirement as exc:
                raise ToolFailure(
                    "test-attestation-dependency-metadata-invalid",
                    (
                        f"{display_name} exposes an unreadable dependency "
                        f"requirement: {raw_requirement!r}."
                    ),
                    requirements,
                ) from exc
            if not applies_to_supported_python(requirement):
                continue
            dependency = normalized_distribution(requirement.name)
            if dependency not in pins:
                raise ToolFailure(
                    "test-attestation-dependency-closure-incomplete",
                    (
                        f"{display_name} requires {requirement.name}, which "
                        "is not pinned in requirements-dev.txt."
                    ),
                    requirements,
                )
            installed = importlib.metadata.version(requirement.name)
            if requirement.specifier and installed not in requirement.specifier:
                raise ToolFailure(
                    "test-attestation-dependency-closure-incompatible",
                    (
                        f"{display_name} requires {requirement}; installed "
                        f"{requirement.name} is {installed}."
                    ),
                    requirements,
                )
    return records


def attested_input_hashes(plugin_root: Path) -> dict[str, str]:
    required_directories = (
        plugin_root / "maintainer" / "tests",
        plugin_root / "maintainer" / "scripts",
        plugin_root / "maintainer" / "schemas",
    )
    for path in required_directories:
        assert_no_reparse_path(path, stop=plugin_root)
        if not path.is_dir():
            raise ToolFailure(
                "test-attestation-input-missing",
                "Required attestation input directory is missing.",
                path,
            )
    requirements = plugin_root / "maintainer" / "requirements-dev.txt"
    assert_no_reparse_path(requirements, stop=plugin_root)
    if not requirements.is_file():
        raise ToolFailure(
            "test-attestation-input-missing",
            "Pinned maintainer requirements are missing.",
            requirements,
        )
    reject_compiled_python_residue(
        (
            plugin_root / relative
            for relative in EXECUTABLE_MAINTAINER_TREES
        ),
        code="test-attestation-compiled-python-residue",
        message=(
            "Compiled Python residue is excluded from attested input hashes; "
            "remove it before creating or validating a test attestation."
        ),
    )
    return {
        name: identity_group_sha256(plugin_root, paths)
        for name, paths in ATTESTED_INPUTS.items()
    }


def parse_unittest_result(
    result: subprocess.CompletedProcess[bytes],
) -> tuple[dict[str, int | str], str, str, str]:
    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")
    combined = stdout + "\n" + stderr
    ran = list(SUMMARY.finditer(combined))
    statuses = list(STATUS.finditer(combined))
    if not ran or not statuses:
        raise ToolFailure(
            "test-attestation-output-incomplete",
            "Unittest output did not contain a complete run summary and status.",
        )
    tests_run = int(ran[-1].group("count"))
    if tests_run <= 0:
        raise ToolFailure(
            "test-attestation-suite-empty",
            "The exact maintainer suite ran no tests.",
        )
    counts = {
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "expected_failures": 0,
        "unexpected_successes": 0,
    }
    status_match = statuses[-1]
    for part in (status_match.group("counts") or "").split(","):
        if not part.strip():
            continue
        key, separator, raw_value = part.strip().rpartition("=")
        normalized = key.strip().casefold()
        if not separator or normalized not in COUNT_KEYS or not raw_value.isdigit():
            raise ToolFailure(
                "test-attestation-output-incomplete",
                f"Unsupported unittest result count: {part.strip()!r}.",
            )
        counts[COUNT_KEYS[normalized]] = int(raw_value)
    passed = (
        result.returncode == 0
        and status_match.group("status") == "OK"
        and counts["failures"] == 0
        and counts["errors"] == 0
        and counts["unexpected_successes"] == 0
    )
    if (result.returncode == 0) != passed:
        raise ToolFailure(
            "test-attestation-result-inconsistent",
            "Unittest exit status and parsed result disagree.",
        )
    payload: dict[str, int | str] = {
        "status": "passed" if passed else "failed",
        "return_code": result.returncode,
        "tests_run": tests_run,
        **counts,
    }
    output_digest = hashlib.sha256(
        ("stdout\0" + stdout + "\0stderr\0" + stderr).encode("utf-8")
    ).hexdigest()
    return payload, stdout, stderr, output_digest


def run_exact_suite(
    plugin_root: Path,
    command: list[str],
) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    try:
        return subprocess.run(
            command,
            cwd=plugin_root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=1800,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolFailure(
            "test-attestation-suite-unavailable",
            str(exc),
            plugin_root / "maintainer" / "tests",
        ) from exc


def create_attestation(
    plugin_root: Path,
    *,
    runner: Runner = run_exact_suite,
) -> dict[str, object]:
    plugin_root = absolute(plugin_root)
    assert_no_reparse_path(plugin_root)
    if not plugin_root.is_dir():
        raise ToolFailure(
            "test-attestation-plugin-missing",
            "Plugin root does not exist.",
            plugin_root,
        )
    before = attested_input_hashes(plugin_root)
    dependencies = pinned_dependencies(plugin_root)
    command = [sys.executable, *UNITTEST_ARGUMENTS]
    started_at = utc_now()
    started = time.monotonic()
    result = runner(plugin_root, command)
    duration = round(time.monotonic() - started, 6)
    completed_at = utc_now()
    parsed, stdout, stderr, output_digest = parse_unittest_result(result)
    after = attested_input_hashes(plugin_root)
    dependencies_after = pinned_dependencies(plugin_root)
    if before != after or dependencies != dependencies_after:
        raise ToolFailure(
            "test-attestation-input-unstable",
            "Attested inputs or pinned dependencies changed during the suite.",
            plugin_root / "maintainer",
        )
    return {
        "schema_version": 1,
        "record_type": "design-dna-test-attestation",
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": duration,
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable": sys.executable,
        },
        "dependencies": dependencies,
        "command": command,
        "inputs": before,
        "result": parsed,
        "output": {
            "stdout": stdout,
            "stderr": stderr,
            "sha256": output_digest,
            "stdout_bytes": len(stdout.encode("utf-8")),
            "stderr_bytes": len(stderr.encode("utf-8")),
        },
    }


def validate_record(record: object, schema_path: Path) -> None:
    schema = load_json(schema_path)
    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=strict_format_checker(),
        ).iter_errors(record),
        key=lambda item: tuple(str(part) for part in item.path),
    )
    if errors:
        message = "; ".join(
            f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ToolFailure(
            "test-attestation-schema-invalid",
            message,
            schema_path,
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_plugin = Path(__file__).resolve().parents[2]
    parser.add_argument("--plugin-root", type=Path, default=default_plugin)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        plugin_root = absolute(args.plugin_root)
        output = absolute(
            args.output
            or (
                plugin_root
                / "maintainer"
                / "attestations"
                / "test-attestation.json"
            )
        )
        protected = (
            plugin_root / "maintainer" / "tests",
            plugin_root / "maintainer" / "scripts",
            plugin_root / "maintainer" / "schemas",
            plugin_root / "maintainer" / "requirements-dev.txt",
        )
        if any(output == path or is_within(output, path) for path in protected):
            raise ToolFailure(
                "test-attestation-output-overlaps-input",
                "The attestation output must be outside its hashed inputs.",
                output,
            )
        record = create_attestation(plugin_root)
        validate_record(
            record,
            plugin_root
            / "maintainer"
            / "schemas"
            / "test-attestation.schema.json",
        )
        if (
            record["inputs"] != attested_input_hashes(plugin_root)
            or record["dependencies"] != pinned_dependencies(plugin_root)
        ):
            raise ToolFailure(
                "test-attestation-input-unstable",
                "Attested inputs changed before the record could be written.",
                plugin_root / "maintainer",
            )
        atomic_write_json(output, record)
        emit({
            "ok": record["result"]["status"] == "passed",
            "output": str(output),
            "record": record,
        })
        return 0 if record["result"]["status"] == "passed" else 1
    except ToolFailure as exc:
        emit({"ok": False, "failures": [exc.issue.as_dict()]})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
