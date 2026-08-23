#!/usr/bin/env python3
"""Run the exact release unittest suite and atomically attest its result."""

from __future__ import annotations

# A Python ``sitecustomize`` hook runs before ordinary script code.  If this
# attester were launched normally, such a hook could replace subprocess,
# hashing, or unittest parsing before this module could inspect it.  The
# authoritative CLI therefore accepts only a startup-isolated interpreter.
# This has to happen before cache preflight and every non-stdlib import; a
# post-startup scan would be too late to establish trust.
import sys as _startup_sys

_ISOLATED_BOOTSTRAP = (
    bool(_startup_sys.flags.isolated)
    and bool(_startup_sys.flags.no_site)
    and bool(_startup_sys.flags.dont_write_bytecode)
)
# Only the direct attester command owns its import bootstrap.  The isolated
# release runner deliberately makes the package root importable while it
# discovers tests; an attester imported by one of those tests is a library and
# must retain that already-controlled context.  Keep this separate from the
# main gate below: importing a module never authorizes an attestation write.
_DIRECT_CLI_BOOTSTRAP = __name__ == "__main__"
if _DIRECT_CLI_BOOTSTRAP and not _ISOLATED_BOOTSTRAP:
    _startup_sys.stdout.write(
        "{\"ok\": false, \"failures\": [{\"code\": "
        "\"test-attestation-isolation-required\", \"message\": "
        "\"Launch with python -I -S -B so startup hooks and inherited "
        "Python paths cannot alter attestation.\"}]}\n"
    )
    raise SystemExit(2)
del _startup_sys

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
import sysconfig
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Callable


def _is_within_interpreter_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _interpreter_owned_roots() -> tuple[Path, ...]:
    """Find only paths owned by the executing interpreter or its venv.

    Python versions before 3.14 can expose the base prefix under ``-S`` even
    when the executable belongs to a virtual environment.  The executable and
    its adjacent ``pyvenv.cfg`` are canonical interpreter facts; inherited
    environment variables and caller import paths are intentionally ignored.
    """

    candidates = [Path(sys.prefix), Path(sys.base_prefix)]
    executable = Path(sys.executable)
    try:
        if not executable.is_absolute():
            executable = executable.absolute()
        if not executable.is_file():
            raise OSError("Python executable is not a regular file")
    except OSError as exc:
        raise RuntimeError(
            "The isolated test attester cannot resolve its Python executable."
        ) from exc
    for candidate in (executable.parent, executable.parent.parent):
        try:
            if (candidate / "pyvenv.cfg").is_file():
                candidates.append(candidate)
        except OSError as exc:
            raise RuntimeError(
                "The isolated test attester cannot inspect its virtual environment."
            ) from exc
    roots: list[Path] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise RuntimeError(
                "The isolated test attester has an unreadable interpreter root."
            ) from exc
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def _canonical_site_packages(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    """Return existing interpreter-owned dependency directories only."""

    # A selected venv is the dependency boundary. Do not fall through to
    # arbitrary base-interpreter site packages merely because they are owned
    # by the executable's underlying Python installation.
    venv_roots = tuple(
        root for root in roots if (root / "pyvenv.cfg").is_file()
    )
    dependency_roots = venv_roots or (Path(sys.prefix).resolve(),)
    candidates: list[Path] = []
    for key in ("purelib", "platlib"):
        value = sysconfig.get_path(key)
        if value:
            candidates.append(Path(value))
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    for root in dependency_roots:
        candidates.extend((
            root / "Lib" / "site-packages",
            root / "lib" / version / "site-packages",
            root / "lib64" / version / "site-packages",
        ))
    approved: list[Path] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            exists = resolved.is_dir()
        except OSError as exc:
            raise RuntimeError(
                "The isolated test attester cannot inspect a dependency path."
            ) from exc
        if not exists or not any(
            _is_within_interpreter_root(resolved, root)
            for root in dependency_roots
        ):
            continue
        if resolved not in approved:
            approved.append(resolved)
    return tuple(approved)


def _install_isolated_import_paths() -> None:
    """Install only canonical maintainer modules and pinned dependencies.

    ``-I -S`` leaves the standard library available but does not process site
    packages.  Add the script directory and interpreter-owned package roots
    directly, after preflight, without honoring ``.pth`` files or any inherited
    Python path.  Ordinary module imports keep their existing behavior when
    this file is imported by the unit suite rather than executed as the CLI.
    """

    if not (_DIRECT_CLI_BOOTSTRAP and _ISOLATED_BOOTSTRAP):
        return
    if any(name in sys.modules for name in ("site", "sitecustomize", "usercustomize")):
        raise RuntimeError("The isolated test attester detected site initialization.")
    roots = _interpreter_owned_roots()
    interpreter_paths: list[str] = []
    for entry in sys.path:
        if not entry:
            raise RuntimeError("The isolated test attester received an empty import path.")
        try:
            resolved = Path(entry).resolve()
        except OSError as exc:
            raise RuntimeError(
                "The isolated test attester cannot resolve an interpreter path."
            ) from exc
        if not any(_is_within_interpreter_root(resolved, root) for root in roots):
            raise RuntimeError(
                "The isolated test attester received a non-canonical import path."
            )
        interpreter_paths.append(str(resolved))
    script_directory = Path(__file__).resolve().parent
    sys.path[:] = [
        *dict.fromkeys(interpreter_paths),
        str(script_directory),
        *(str(path) for path in _canonical_site_packages(roots)),
    ]
    sys.path_importer_cache.clear()


_install_isolated_import_paths()

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


RELEASE_TEST_RUNNER = "maintainer/scripts/run_release_tests.py"
# ``-I`` stops environment-derived path/startup configuration before Python
# initializes, while ``-S`` suppresses site and therefore sitecustomize and
# usercustomize.  The runner restores only canonical dependency directories
# after its cache preflight.  Keep these flags in the attested record: a pass
# from a normal interpreter is not an equivalent execution.
UNITTEST_ARGUMENTS = ("-I", "-S", "-B", RELEASE_TEST_RUNNER)

# ``tests_sha256`` predates the full execution-input contract and remains its
# schema-stable field name.  It is now the digest of this *bounded* manifest.
# Each entry is ``(label, package-relative path, expected kind)``.  The labels
# make the hash construction auditable without inventing a new record shape.
#
# This is intentionally not a whole-worktree hash: a scratch file, local
# environment, or generated proof must not become an implicit test input.
# Conversely, every non-generated canonical source surface intentionally read
# by the two release-test roots belongs here.  Keep derived release outputs out
# of this list: SBOMs, attestations, release manifests, and evaluation results
# are outputs that would make a test attestation circular.
TEST_EXECUTION_INPUT_MANIFEST = (
    # Exact executable suite and the runtime it exercises.
    ("runtime_skill", "skills/design-dna", "directory"),
    ("maintainer_test_tree", "maintainer/tests", "directory"),
    ("maintainer_scripts", "maintainer/scripts", "directory"),
    ("maintainer_schemas", "maintainer/schemas", "directory"),
    ("release_runner", RELEASE_TEST_RUNNER, "file"),
    ("attester", "maintainer/scripts/attest_tests.py", "file"),
    (
        "attestation_schema",
        "maintainer/schemas/test-attestation.schema.json",
        "file",
    ),
    # Test-environment declarations and package-manager configuration.
    ("python_requirements", "maintainer/requirements-dev.txt", "file"),
    ("python_requirements_lock", "maintainer/requirements-dev.lock", "file"),
    ("node_package_manifest", "maintainer/package.json", "file"),
    ("node_package_lock", "maintainer/package-lock.json", "file"),
    # Host package entry points are directly asserted by release tests.
    ("codex_plugin_manifest", ".codex-plugin/plugin.json", "file"),
    ("claude_plugin_manifest", ".claude-plugin/plugin.json", "file"),
    # The published contract is asserted, not merely shipped alongside tests.
    ("git_attributes", ".gitattributes", "file"),
    ("git_ignore", ".gitignore", "file"),
    ("readme", "README.md", "file"),
    ("changelog", "CHANGELOG.md", "file"),
    ("contributing", "CONTRIBUTING.md", "file"),
    ("data_handling", "DATA_HANDLING.md", "file"),
    ("license", "LICENSE", "file"),
    ("security", "SECURITY.md", "file"),
    ("support", "SUPPORT.md", "file"),
    ("third_party_notices", "THIRD_PARTY_NOTICES.md", "file"),
    ("documentation", "docs", "directory"),
    # ``ci.yml`` is parsed by the release-proof suite.  Other repository
    # configuration remains outside the bounded contract unless a release test
    # starts reading it and this manifest is deliberately extended.
    ("ci_workflow", ".github/workflows/ci.yml", "file"),
    # Evaluation contract and fixed fixture corpus, excluding derived outcomes.
    ("eval_readme", "maintainer/evals/README.md", "file"),
    ("eval_rubric", "maintainer/evals/review-rubric.md", "file"),
    ("eval_schema", "maintainer/evals/schema.json", "file"),
    ("eval_fixtures", "maintainer/evals/fixtures", "directory"),
    # Compatibility and trust policy are parsed by release proof/audit tests.
    ("compatibility_matrix", "maintainer/compatibility/matrix.yml", "file"),
    (
        "compatibility_host_adapters",
        "maintainer/compatibility/trusted-host-adapters.yml",
        "file",
    ),
    (
        "codex_validator_trust",
        "maintainer/trust/codex-plugin-validator.json",
        "file",
    ),
    # Curated evidence is a source registry validated by the release suite.
    ("evidence_registry", "maintainer/evidence", "directory"),
)

# Explicitly guard the contract against a future accidental circular input.
# These paths are release products or retained evaluation outcomes, not source
# surfaces used to define the suite that attests them.
DERIVED_EXECUTION_OUTPUT_PATHS = (
    "maintainer/sbom.spdx.json",
    "maintainer/release-manifest.json",
    "maintainer/attestations",
    "maintainer/evals/results",
    "maintainer/evals/reviews",
    "maintainer/evals/artifacts",
    "maintainer/evals/archive",
    "maintainer/compatibility/archive/ci-runs",
)
ATTESTED_INPUTS = {
    "runtime_sha256": ("skills/design-dna",),
    # The schema-compatible tests_sha256 value is calculated from
    # TEST_EXECUTION_INPUT_MANIFEST rather than this tuple.
    "tests_sha256": tuple(
        path for _label, path, _kind in TEST_EXECUTION_INPUT_MANIFEST
    ),
    "tooling_sha256": ("maintainer/scripts",),
    "schemas_sha256": ("maintainer/schemas",),
    "requirements_sha256": ("maintainer/requirements-dev.txt",),
    "requirements_lock_sha256": ("maintainer/requirements-dev.lock",),
}
PIN = re.compile(
    r"(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)=="
    r"(?P<version>[A-Za-z0-9][A-Za-z0-9_.+!-]*)"
)
SUPPORTED_PYTHON_VERSIONS = ("3.10", "3.11", "3.12", "3.13", "3.14")
SUMMARY = re.compile(r"(?m)^Ran\s+(?P<count>[0-9]+)\s+tests?\s+in\s+")
STATUS = re.compile(r"(?m)^(?P<status>OK|FAILED)(?:\s+\((?P<counts>[^)]*)\))?\s*$")
SKIPPED_TEST = re.compile(
    r"(?m)^[^\r\n]*\((?P<id>[A-Za-z0-9_.]+)\)\s+\.\.\.\s+skipped\b"
)
UNSAFE_PORTABLE_PATH = re.compile(
    r"(?:^[/\\]|^[A-Za-z]:|\\|//|(?:^|/)\.{1,2}(?:/|$)|"
    r"[\x00-\x1f\x7f])"
)
MAX_SKIP_WAIVER_LIFETIME = timedelta(days=90)
COUNT_KEYS = {
    "failures": "failures",
    "errors": "errors",
    "skipped": "skipped",
    "expected failures": "expected_failures",
    "unexpected successes": "unexpected_successes",
}
Runner = Callable[[Path, list[str]], subprocess.CompletedProcess[bytes]]
PYTHON_EXECUTABLE_TOKEN = "python-current-environment"
# The full suite launches real browsers and interrupted-filesystem lifecycle
# subprocesses. Keep a hard ceiling, but allow enough time for supported slower
# Windows and synchronized-folder environments to complete deterministically.
TEST_SUITE_TIMEOUT_SECONDS = 3600


def require_authoritative_isolation() -> None:
    """Reject an attestation CLI path that was not isolated at interpreter start.

    This check intentionally belongs in main as well as the early direct
    script guard. A normal-started startup hook can import this module under a
    non-main name and invoke main(); that must never reach subprocess execution
    or an attestation write. The external -I -S -B invocation remains the
    actual pre-startup defense. Once arbitrary startup code has run, Python
    code cannot attest that the interpreter process itself was not modified.
    """

    if not _ISOLATED_BOOTSTRAP:
        raise ToolFailure(
            "test-attestation-isolation-required",
            (
                "Launch with python -I -S -B so startup hooks and inherited "
                "Python paths cannot alter attestation."
            ),
        )


def isolated_subprocess_environment() -> dict[str, str]:
    """Drop inherited Python controls before launching the release runner.

    ``-I -S`` protects the runner's startup, but environment variables remain
    visible to its test subprocesses.  Preserve ordinary OS configuration while
    removing every Python-specific override and virtual-environment selector;
    the explicit executable and the runner's controlled import bootstrap are
    the only Python execution inputs.
    """

    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("PYTHON")
        and key.upper() not in {"VIRTUAL_ENV", "VIRTUAL_ENV_PROMPT"}
    }
    # Child Python processes launched by release tests inherit this explicit
    # guard even when a test omits ``-B`` itself.
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def current_python_executable_sha256() -> str:
    try:
        executable = Path(sys.executable).resolve(strict=True)
        if not executable.is_file():
            raise OSError("resolved Python executable is not a regular file")
        before = executable.stat()
        digest = hashlib.sha256()
        with executable.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        after = executable.stat()
    except OSError as exc:
        raise ToolFailure(
            "test-attestation-python-identity-unavailable",
            str(exc),
        ) from exc
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
    ):
        raise ToolFailure(
            "test-attestation-python-identity-unstable",
            "The Python executable changed while its identity was calculated.",
        )
    return digest.hexdigest()


def redact_known_local_paths(text: str, plugin_root: Path) -> str:
    """Remove machine-local roots while retaining useful unittest evidence."""

    candidates = (
        ("<PYTHON_EXECUTABLE>", Path(sys.executable)),
        ("<PLUGIN_ROOT>", plugin_root),
        ("<HOME>", Path.home()),
        ("<PYTHON_PREFIX>", Path(sys.prefix)),
        ("<TEMP>", Path(tempfile.gettempdir())),
    )
    replacements: dict[str, str] = {}
    for token, path in candidates:
        for value in {str(path), path.as_posix()}:
            if value and len(value) > 1:
                replacements[value] = token
    redacted = text
    flags = re.IGNORECASE if os.name == "nt" else 0
    for value in sorted(replacements, key=len, reverse=True):
        redacted = re.sub(
            re.escape(value),
            replacements[value],
            redacted,
            flags=flags,
        )
    return redacted


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
                "Install maintainer/requirements-dev.lock with --require-hashes; packaging is "
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


def _execution_input_paths_overlap(first: str, second: str) -> bool:
    """Return whether two portable package-relative paths overlap."""

    return (
        first == second
        or first.startswith(second + "/")
        or second.startswith(first + "/")
    )


def validated_test_execution_inputs(
    plugin_root: Path,
) -> tuple[tuple[str, str, str, Path], ...]:
    """Validate and resolve the fixed, non-circular release-test inputs.

    ``identity_group_sha256`` intentionally represents an absent path so that
    generic release identities can compare incomplete trees.  Test attestation
    cannot do that: every declared release-test source must exist with its
    expected kind before a pass can be recorded or replayed.
    """

    labels: set[str] = set()
    relatives: set[str] = set()
    resolved: list[tuple[str, str, str, Path]] = []
    for label, relative, expected_kind in TEST_EXECUTION_INPUT_MANIFEST:
        if (
            not label
            or not label.isascii()
            or not re.fullmatch(r"[a-z][a-z0-9_]*", label)
            or label in labels
        ):
            raise ToolFailure(
                "test-attestation-input-contract-invalid",
                "Execution-input labels must be unique lowercase ASCII identifiers.",
                plugin_root,
            )
        if (
            not relative
            or UNSAFE_PORTABLE_PATH.search(relative)
            or PurePosixPath(relative).as_posix() != relative
            or relative in relatives
        ):
            raise ToolFailure(
                "test-attestation-input-contract-invalid",
                "Execution-input paths must be unique safe portable paths.",
                plugin_root,
            )
        if expected_kind not in {"file", "directory"}:
            raise ToolFailure(
                "test-attestation-input-contract-invalid",
                "Execution-input kinds must be file or directory.",
                plugin_root / relative,
            )
        if any(
            _execution_input_paths_overlap(relative, derived)
            for derived in DERIVED_EXECUTION_OUTPUT_PATHS
        ):
            raise ToolFailure(
                "test-attestation-input-contract-invalid",
                "Execution inputs must not overlap generated release outputs.",
                plugin_root / relative,
            )
        path = plugin_root / relative
        assert_no_reparse_path(path, stop=plugin_root)
        if not path.exists():
            raise ToolFailure(
                "test-attestation-input-missing",
                f"Required test-execution input {label!r} is missing.",
                path,
            )
        if expected_kind == "file" and not path.is_file():
            raise ToolFailure(
                "test-attestation-input-kind-invalid",
                f"Test-execution input {label!r} must be a regular file.",
                path,
            )
        if expected_kind == "directory" and not path.is_dir():
            raise ToolFailure(
                "test-attestation-input-kind-invalid",
                f"Test-execution input {label!r} must be a directory.",
                path,
            )
        labels.add(label)
        relatives.add(relative)
        resolved.append((label, relative, expected_kind, path))
    return tuple(resolved)


def test_execution_input_sha256(plugin_root: Path) -> str:
    """Hash the labeled deterministic source manifest for the release suite."""

    digest = hashlib.sha256()
    for label, relative, _expected_kind, _path in (
        validated_test_execution_inputs(plugin_root)
    ):
        item_digest = identity_group_sha256(plugin_root, (relative,))
        digest.update(label.encode("ascii"))
        digest.update(b"\0")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(item_digest.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def attested_input_hashes(plugin_root: Path) -> dict[str, str]:
    # Resolve every declared surface before calculating any hash.  A record
    # must never certify a suite whose source contract is partially absent.
    validated_test_execution_inputs(plugin_root)
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
    reject_compiled_python_residue(
        (plugin_root / "skills" / "design-dna",),
        code="test-attestation-compiled-python-residue",
        message=(
            "Compiled Python residue is excluded from the runtime identity; "
            "remove it before creating or validating a test attestation."
        ),
    )
    return {
        name: (
            test_execution_input_sha256(plugin_root)
            if name == "tests_sha256"
            else identity_group_sha256(plugin_root, paths)
        )
        for name, paths in ATTESTED_INPUTS.items()
    }


def parse_unittest_result(
    result: subprocess.CompletedProcess[bytes],
) -> tuple[dict[str, object], str, str, str]:
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
            "The exact release suite ran no tests.",
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
    skipped_test_ids = sorted({
        match.group("id")
        for match in SKIPPED_TEST.finditer(combined)
    })
    if counts["skipped"] != len(skipped_test_ids):
        raise ToolFailure(
            "test-attestation-skip-identity-incomplete",
            (
                "Unittest skipped count does not match the exact skipped test "
                "identities parsed from verbose output."
            ),
        )
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
    payload: dict[str, object] = {
        "status": "passed" if passed else "failed",
        "return_code": result.returncode,
        "tests_run": tests_run,
        "skipped_test_ids": skipped_test_ids,
        **counts,
    }
    output_digest = hashlib.sha256(
        ("stdout\0" + stdout + "\0stderr\0" + stderr).encode("utf-8")
    ).hexdigest()
    return payload, stdout, stderr, output_digest


def portable_relative_path(value: object) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 512
        or UNSAFE_PORTABLE_PATH.search(value)
        or PurePosixPath(value).as_posix() != value
    ):
        raise ToolFailure(
            "test-skip-waiver-path-invalid",
            "Waiver paths must be safe portable package-relative paths.",
        )
    return PurePosixPath(value)


def parse_aware_time(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ToolFailure(
            "test-skip-waiver-time-invalid",
            f"{field} must be an RFC 3339 date-time.",
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ToolFailure(
            "test-skip-waiver-time-invalid",
            f"{field} is invalid.",
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ToolFailure(
            "test-skip-waiver-time-invalid",
            f"{field} must include a UTC offset.",
        )
    return parsed.astimezone(timezone.utc)


def current_waiver_environment() -> dict[str, str]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine_architecture": platform.machine(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
    }


def validate_skip_waiver_schema(
    payload: object,
    schema_path: Path,
) -> None:
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
            "test-skip-waiver-schema-invalid",
            message,
            schema_path,
        )


def verified_skip_waiver_payload(
    plugin_root: Path,
    waiver_path: Path,
    inputs: dict[str, str],
    skipped_test_ids: list[str],
) -> tuple[dict[str, object], list[dict[str, str]], str]:
    plugin_root = absolute(plugin_root)
    waiver_path = absolute(waiver_path)
    waiver_root = plugin_root / "maintainer" / "attestations" / "skip-waivers"
    if not is_within(waiver_path, waiver_root):
        raise ToolFailure(
            "test-skip-waiver-source-outside-policy",
            "Skip waiver files must be retained below maintainer/attestations/skip-waivers.",
            waiver_path,
        )
    assert_no_reparse_path(waiver_path, stop=plugin_root)
    if not waiver_path.is_file():
        raise ToolFailure(
            "test-skip-waiver-source-missing",
            "Skip waiver file is missing.",
            waiver_path,
        )
    try:
        source_before = waiver_path.read_bytes()
        payload = load_json(waiver_path)
        source_after = waiver_path.read_bytes()
    except OSError as exc:
        raise ToolFailure(
            "test-skip-waiver-source-unreadable",
            str(exc),
            waiver_path,
        ) from exc
    if source_before != source_after:
        raise ToolFailure(
            "test-skip-waiver-source-unstable",
            "Skip waiver source changed while it was being verified.",
            waiver_path,
        )
    validate_skip_waiver_schema(
        payload,
        plugin_root
        / "maintainer"
        / "schemas"
        / "test-skip-waivers.schema.json",
    )
    if not isinstance(payload, dict):
        raise ToolFailure(
            "test-skip-waiver-invalid",
            "Skip waiver payload must be an object.",
            waiver_path,
        )
    now = datetime.now(timezone.utc)
    approved = parse_aware_time(payload.get("approved_at"), "approved_at")
    expires = parse_aware_time(payload.get("expires_at"), "expires_at")
    if approved > now + timedelta(minutes=5):
        raise ToolFailure(
            "test-skip-waiver-time-invalid",
            "approved_at may not be in the future.",
            waiver_path,
        )
    if expires <= now:
        raise ToolFailure(
            "test-skip-waiver-expired",
            "The skip waiver has expired.",
            waiver_path,
        )
    if expires - approved > MAX_SKIP_WAIVER_LIFETIME:
        raise ToolFailure(
            "test-skip-waiver-lifetime-invalid",
            "A skip waiver may remain valid for at most 90 days.",
            waiver_path,
        )
    if payload.get("applicability") != current_waiver_environment():
        raise ToolFailure(
            "test-skip-waiver-environment-mismatch",
            "The waiver does not match the exact current test environment.",
            waiver_path,
        )
    if payload.get("inputs") != inputs:
        raise ToolFailure(
            "test-skip-waiver-input-drift",
            "The waiver is not bound to the exact current attested inputs.",
            waiver_path,
        )
    waivers = payload.get("waivers")
    waiver_ids = sorted(
        str(item.get("test_id"))
        for item in waivers
        if isinstance(item, dict)
    ) if isinstance(waivers, list) else []
    if waiver_ids != sorted(skipped_test_ids):
        raise ToolFailure(
            "test-skip-waiver-coverage-mismatch",
            "Waivers must exactly match every skipped test and no others.",
            waiver_path,
        )
    evidence_records: dict[str, str] = {}
    for waiver in waivers if isinstance(waivers, list) else []:
        if not isinstance(waiver, dict):
            continue
        evidence = waiver.get("compensating_evidence")
        for record in evidence if isinstance(evidence, list) else []:
            if not isinstance(record, dict):
                continue
            relative = portable_relative_path(record.get("path"))
            if (
                len(relative.parts) < 4
                or relative.parts[:3]
                != ("maintainer", "attestations", "skip-evidence")
            ):
                raise ToolFailure(
                    "test-skip-waiver-evidence-outside-policy",
                    (
                        "Compensating evidence must be retained below "
                        "maintainer/attestations/skip-evidence."
                    ),
                    waiver_path,
                )
            candidate = absolute(plugin_root.joinpath(*relative.parts))
            assert_no_reparse_path(candidate, stop=plugin_root)
            if not candidate.is_file():
                raise ToolFailure(
                    "test-skip-waiver-evidence-missing",
                    "Compensating evidence file is missing.",
                    candidate,
                )
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            if record.get("sha256") != digest:
                raise ToolFailure(
                    "test-skip-waiver-evidence-drift",
                    "Compensating evidence hash does not match.",
                    candidate,
                )
            previous = evidence_records.get(relative.as_posix())
            if previous is not None and previous != digest:
                raise ToolFailure(
                    "test-skip-waiver-evidence-conflict",
                    "The same evidence path is recorded with conflicting hashes.",
                    candidate,
                )
            evidence_records[relative.as_posix()] = digest
    return payload, [
        {"path": path, "sha256": digest}
        for path, digest in sorted(evidence_records.items())
    ], hashlib.sha256(source_before).hexdigest()


def create_skip_waiver_record(
    plugin_root: Path,
    waiver_path: Path | None,
    inputs: dict[str, str],
    result: dict[str, object],
) -> dict[str, object] | None:
    skipped = result.get("skipped")
    skipped_ids = result.get("skipped_test_ids")
    if not isinstance(skipped, int) or not isinstance(skipped_ids, list):
        raise ToolFailure(
            "test-skip-waiver-result-invalid",
            "Parsed unittest skip evidence is incomplete.",
        )
    if skipped == 0:
        if waiver_path is not None:
            raise ToolFailure(
                "test-skip-waiver-stale",
                "A waiver file was supplied but the suite skipped no tests.",
                waiver_path,
            )
        return None
    if waiver_path is None:
        return None
    _payload, evidence, source_digest = verified_skip_waiver_payload(
        plugin_root,
        waiver_path,
        inputs,
        [str(value) for value in skipped_ids],
    )
    relative = waiver_path.relative_to(plugin_root).as_posix()
    return {
        "source_path": relative,
        "source_sha256": source_digest,
        "matched_test_ids": sorted(str(value) for value in skipped_ids),
        "evidence": evidence,
    }


def verify_skip_waiver_record(
    plugin_root: Path,
    record: object,
    inputs: dict[str, str],
    result: dict[str, object],
) -> None:
    skipped = result.get("skipped")
    skipped_ids = result.get("skipped_test_ids")
    if (
        not isinstance(skipped, int)
        or skipped < 0
        or not isinstance(skipped_ids, list)
        or skipped != len(skipped_ids)
        or len({str(value) for value in skipped_ids}) != len(skipped_ids)
        or [str(value) for value in skipped_ids]
        != sorted(str(value) for value in skipped_ids)
    ):
        raise ToolFailure(
            "test-skip-waiver-result-invalid",
            "Attested skip count and exact test identities disagree.",
        )
    if skipped == 0:
        if record is not None:
            raise ToolFailure(
                "test-skip-waiver-stale",
                "The attestation retains a waiver although no test was skipped.",
            )
        return
    if not isinstance(record, dict):
        raise ToolFailure(
            "test-skip-waiver-missing",
            "Every skipped release test requires an exact current waiver.",
        )
    relative = portable_relative_path(record.get("source_path"))
    source_path = absolute(plugin_root.joinpath(*relative.parts))
    payload, evidence, source_digest = verified_skip_waiver_payload(
        plugin_root,
        source_path,
        inputs,
        [str(value) for value in skipped_ids],
    )
    del payload
    if (
        record.get("source_sha256") != source_digest
        or record.get("matched_test_ids")
        != sorted(str(value) for value in skipped_ids)
        or record.get("evidence") != evidence
    ):
        raise ToolFailure(
            "test-skip-waiver-attestation-drift",
            "Embedded waiver identity differs from the current verified source.",
            source_path,
        )


def run_exact_suite(
    plugin_root: Path,
    command: list[str],
) -> subprocess.CompletedProcess[bytes]:
    environment = isolated_subprocess_environment()
    try:
        return subprocess.run(
            command,
            cwd=plugin_root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=TEST_SUITE_TIMEOUT_SECONDS,
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
    skip_waiver_path: Path | None = None,
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
    parsed, raw_stdout, raw_stderr, _raw_output_digest = parse_unittest_result(
        result
    )
    stdout = redact_known_local_paths(raw_stdout, plugin_root)
    stderr = redact_known_local_paths(raw_stderr, plugin_root)
    output_digest = hashlib.sha256(
        ("stdout\0" + stdout + "\0stderr\0" + stderr).encode("utf-8")
    ).hexdigest()
    after = attested_input_hashes(plugin_root)
    dependencies_after = pinned_dependencies(plugin_root)
    if before != after or dependencies != dependencies_after:
        raise ToolFailure(
            "test-attestation-input-unstable",
            "Attested inputs or pinned dependencies changed during the suite.",
            plugin_root / "maintainer",
        )
    skip_waiver = create_skip_waiver_record(
        plugin_root,
        absolute(skip_waiver_path) if skip_waiver_path is not None else None,
        before,
        parsed,
    )
    return {
        "schema_version": 3,
        "record_type": "design-dna-test-attestation",
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": duration,
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable": PYTHON_EXECUTABLE_TOKEN,
            "executable_sha256": current_python_executable_sha256(),
        },
        "dependencies": dependencies,
        "command": [PYTHON_EXECUTABLE_TOKEN, *UNITTEST_ARGUMENTS],
        "inputs": before,
        "result": parsed,
        "skip_waiver": skip_waiver,
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
    try:
        require_authoritative_isolation()
    except ToolFailure as exc:
        emit({"ok": False, "failures": [exc.issue.as_dict()]})
        return 2

    parser = argparse.ArgumentParser(description=__doc__)
    default_plugin = Path(__file__).resolve().parents[2]
    parser.add_argument("--plugin-root", type=Path, default=default_plugin)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--skip-waiver-file",
        type=Path,
        help=(
            "Current hash-bound waiver record for exact skipped tests. "
            "Release audit rejects unwaived skips."
        ),
    )
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
        protected = validated_test_execution_inputs(plugin_root)
        if any(
            output == path
            or (expected_kind == "directory" and is_within(output, path))
            for _label, _relative, expected_kind, path in protected
        ):
            raise ToolFailure(
                "test-attestation-output-overlaps-input",
                "The attestation output must be outside its hashed inputs.",
                output,
            )
        record = create_attestation(
            plugin_root,
            skip_waiver_path=args.skip_waiver_file,
        )
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
