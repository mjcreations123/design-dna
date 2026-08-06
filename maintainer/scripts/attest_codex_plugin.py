#!/usr/bin/env python3
"""Run and attest the external Codex Plugin Creator validator.

The record binds the exact validator bytes, interpreter bytes, dependency
version, plugin inputs, and sanitized output. It does not prove Codex host
discovery or model behavior.
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
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import stat
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

from common import (
    ToolFailure,
    absolute,
    assert_no_reparse_path,
    eval_content_manifest,
    emit,
    is_within,
    load_json,
    strict_format_checker,
)


sys.dont_write_bytecode = True

PYTHON_TOKEN = "python-current-environment"
VALIDATOR_TOKEN = "external-plugin-creator-validator"
PLUGIN_TOKEN = "plugin-root"
VALIDATOR_LOGICAL_ID = "plugin-creator/validate_plugin.py"
TRUST_POLICY_RELATIVE = (
    "maintainer/trust/codex-plugin-validator.json"
)
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
VALIDATION_TIMEOUT_SECONDS = 120
ATTESTATION_CLOCK_SKEW = timedelta(minutes=5)
ABSTRACT_COMMAND = [
    PYTHON_TOKEN,
    "-I",
    "-B",
    "-X",
    "utf8",
    "attested-validator-wrapper",
    VALIDATOR_TOKEN,
    PLUGIN_TOKEN,
    "pinned-pyyaml-snapshot",
]
VALIDATOR_WRAPPER = r"""
import pathlib
import sys

dependency_root = pathlib.Path(sys.argv[1]).resolve()
plugin_root = pathlib.Path(sys.argv[2]).resolve()
expected_yaml_root = (dependency_root / "yaml").resolve()
sys.path.insert(0, str(dependency_root))
sys.modules["_yaml"] = None
import yaml
if pathlib.Path(yaml.__file__).resolve().parent != expected_yaml_root:
    raise SystemExit("isolated PyYAML snapshot was not loaded")
validator_source = sys.stdin.buffer.read()
sys.argv = ["external-plugin-creator-validator", str(plugin_root)]
namespace = {
    "__name__": "__main__",
    "__file__": "external-plugin-creator-validator",
}
exec(
    compile(
        validator_source,
        "external-plugin-creator-validator",
        "exec",
    ),
    namespace,
    namespace,
)
""".strip()
INPUT_FILES = {
    "attestor": "maintainer/scripts/attest_codex_plugin.py",
    "cache_preflight": "maintainer/scripts/cache_preflight.py",
    "common": "maintainer/scripts/common.py",
    "attestation_schema": (
        "maintainer/schemas/"
        "codex-plugin-validation-attestation.schema.json"
    ),
    "trust_schema": (
        "maintainer/schemas/codex-validator-trust.schema.json"
    ),
    "trust_policy": TRUST_POLICY_RELATIVE,
}
SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def stable_file(
    path: Path,
    *,
    maximum_bytes: int = MAX_FILE_BYTES,
) -> tuple[bytes, str]:
    path = absolute(path)
    assert_no_reparse_path(path)
    try:
        before = path.stat()
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size <= 0
            or before.st_size > maximum_bytes
        ):
            raise ToolFailure(
                "codex-plugin-attestation-input-size-invalid",
                "Attested input must be a nonempty bounded regular file.",
                path,
            )
        first = path.read_bytes()
        second = path.read_bytes()
        after = path.stat()
    except ToolFailure:
        raise
    except OSError as exc:
        raise ToolFailure(
            "codex-plugin-attestation-input-read-failed",
            str(exc),
            path,
        ) from exc
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    if (
        first != second
        or len(first) != before.st_size
        or before_identity != after_identity
    ):
        raise ToolFailure(
            "codex-plugin-attestation-input-unstable",
            "Attested input changed while it was read.",
            path,
        )
    return first, hashlib.sha256(first).hexdigest()


def current_python_sha256() -> str:
    _data, digest = stable_file(Path(sys.executable))
    return digest


def source_tree_record(
    root: Path,
    *,
    copy_to: Path | None = None,
) -> dict[str, object]:
    root = absolute(root)
    assert_no_reparse_path(root)
    if not root.is_dir():
        raise ToolFailure(
            "codex-plugin-attestation-dependency-source-missing",
            "The resolved PyYAML source package is missing.",
            root,
        )
    files: list[tuple[str, bytes, str]] = []
    for path in sorted(
        root.rglob("*.py"),
        key=lambda candidate: candidate.relative_to(root).as_posix(),
    ):
        assert_no_reparse_path(path, stop=root)
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        data, digest = stable_file(path)
        files.append((relative, data, digest))
    if not files:
        raise ToolFailure(
            "codex-plugin-attestation-dependency-source-empty",
            "The resolved PyYAML package contains no Python source.",
            root,
        )
    digest = hashlib.sha256()
    byte_count = 0
    for relative, data, file_digest in files:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(data)).encode("ascii"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\0")
        byte_count += len(data)
        if copy_to is not None:
            target = copy_to / "yaml" / Path(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
    return {
        "module": "yaml",
        "source_format": "pure-python-snapshot",
        "source_sha256": digest.hexdigest(),
        "file_count": len(files),
        "byte_count": byte_count,
    }


def pyyaml_source_root() -> Path:
    try:
        distribution = importlib.metadata.distribution("PyYAML")
    except importlib.metadata.PackageNotFoundError as exc:
        raise ToolFailure(
            "codex-plugin-attestation-dependency-missing",
            "PyYAML is required by the Plugin Creator validator.",
        ) from exc
    root = absolute(Path(distribution.locate_file("yaml")))
    assert_no_reparse_path(root)
    return root


def dependency_records() -> list[dict[str, object]]:
    try:
        version = importlib.metadata.version("PyYAML")
    except importlib.metadata.PackageNotFoundError as exc:
        raise ToolFailure(
            "codex-plugin-attestation-dependency-missing",
            "PyYAML is required by the Plugin Creator validator.",
        ) from exc
    return [{
        "name": "PyYAML",
        "version": version,
        **source_tree_record(pyyaml_source_root()),
    }]


def file_binding(plugin_root: Path, relative: str) -> dict[str, object]:
    data, digest = stable_file(plugin_root / relative)
    return {
        "path": relative,
        "sha256": digest,
        "bytes": len(data),
    }


def tree_binding(plugin_root: Path, relative: str) -> dict[str, object]:
    records, digest = eval_content_manifest(plugin_root / relative)
    return {
        "path": relative,
        "sha256": digest,
        "entry_count": len(records),
        "file_count": sum(record.get("type") == "file" for record in records),
        "byte_count": sum(
            int(record.get("size", 0))
            for record in records
            if record.get("type") == "file"
        ),
    }


def input_records(plugin_root: Path) -> dict[str, object]:
    return {
        "plugin_manifest_tree": tree_binding(plugin_root, ".codex-plugin"),
        "skills_tree": tree_binding(plugin_root, "skills"),
        "files": {
            key: file_binding(plugin_root, relative)
            for key, relative in INPUT_FILES.items()
        },
    }


def snapshot_tree(
    source_root: Path,
    destination_root: Path,
    *,
    expected: dict[str, object],
) -> None:
    records, digest = eval_content_manifest(source_root)
    observed = {
        "path": expected["path"],
        "sha256": digest,
        "entry_count": len(records),
        "file_count": sum(
            record.get("type") == "file" for record in records
        ),
        "byte_count": sum(
            int(record.get("size", 0))
            for record in records
            if record.get("type") == "file"
        ),
    }
    if observed != expected:
        raise ToolFailure(
            "codex-plugin-attestation-input-unstable",
            "Plugin inputs changed before their private snapshot was captured.",
            source_root,
        )
    destination_root.mkdir(parents=True)
    for record in records:
        relative = Path(str(record["path"]))
        target = destination_root / relative
        if record["type"] == "directory":
            target.mkdir(parents=True, exist_ok=True)
            continue
        source = source_root / relative
        data, file_digest = stable_file(source)
        if (
            len(data) != record["size"]
            or file_digest != record["sha256"]
        ):
            raise ToolFailure(
                "codex-plugin-attestation-input-unstable",
                "Plugin input changed while its snapshot was captured.",
                source,
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    snapshot_records, snapshot_digest = eval_content_manifest(
        destination_root
    )
    if (
        snapshot_digest != expected["sha256"]
        or len(snapshot_records) != expected["entry_count"]
    ):
        raise ToolFailure(
            "codex-plugin-attestation-snapshot-drift",
            "Private plugin snapshot does not match its bound input identity.",
            destination_root,
        )


def assert_supported_validator_surface(plugin_root: Path) -> None:
    payload = load_json(
        plugin_root / ".codex-plugin" / "plugin.json"
    )
    if not isinstance(payload, dict):
        raise ToolFailure(
            "codex-plugin-attestation-manifest-invalid",
            "The Codex plugin manifest must be an object.",
        )
    interface = payload.get("interface")
    root_assets: list[object] = []
    if isinstance(interface, dict):
        root_assets.extend(
            interface.get(key)
            for key in ("composerIcon", "logo", "logoDark")
        )
        screenshots = interface.get("screenshots")
        if isinstance(screenshots, list):
            root_assets.extend(screenshots)
    if (
        payload.get("apps") is not None
        or isinstance(payload.get("mcpServers"), str)
        or any(value is not None for value in root_assets)
    ):
        raise ToolFailure(
            "codex-plugin-attestation-surface-unsupported",
            (
                "This attestor binds .codex-plugin and skills only. Add and "
                "bind companion manifests or root assets before using them."
            ),
        )


def release_version(plugin_root: Path) -> str:
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    payload = load_json(manifest_path)
    version = payload.get("version") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("name") != "design-dna"
        or not isinstance(version, str)
        or SEMVER.fullmatch(version) is None
    ):
        raise ToolFailure(
            "codex-plugin-attestation-manifest-invalid",
            "The Codex manifest must identify a SemVer Design DNA package.",
            manifest_path,
        )
    return version


def trusted_validator(
    validator_path: Path,
    trust_policy: dict[str, object],
    trust_policy_sha256: str,
) -> tuple[dict[str, object], bytes]:
    suffix = trust_policy.get("path_suffix")
    if not isinstance(suffix, str):
        raise ToolFailure(
            "codex-plugin-validator-trust-invalid",
            "The validator trust policy has no valid path suffix.",
        )
    if not validator_path.as_posix().casefold().endswith(
        suffix.casefold()
    ):
        raise ToolFailure(
            "codex-plugin-validator-route-invalid",
            (
                "The validator must be the Plugin Creator system-skill "
                "validate_plugin.py route."
            ),
            validator_path,
        )
    data, digest = stable_file(validator_path)
    try:
        source = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ToolFailure(
            "codex-plugin-validator-source-invalid",
            "The Plugin Creator validator must be UTF-8 Python source.",
            validator_path,
        ) from exc
    if (
        trust_policy.get("logical_id") != VALIDATOR_LOGICAL_ID
        or trust_policy.get("sha256") != digest
        or trust_policy.get("bytes") != len(data)
    ):
        raise ToolFailure(
            "codex-plugin-validator-trust-mismatch",
            (
                "The external validator bytes do not match the "
                "publisher-reviewed trust pin."
            ),
            validator_path,
        )
    return (
        {
            "logical_id": VALIDATOR_LOGICAL_ID,
            "sha256": digest,
            "bytes": len(data),
            "trust_policy_path": TRUST_POLICY_RELATIVE,
            "trust_policy_sha256": trust_policy_sha256,
        },
        data,
    )


def validator_record(
    validator_path: Path,
    trust_policy: dict[str, object],
    trust_policy_sha256: str,
) -> dict[str, object]:
    record, _source = trusted_validator(
        validator_path,
        trust_policy,
        trust_policy_sha256,
    )
    return record


def run_validator(
    plugin_root: Path,
    validator_path: Path,
    validator_source: bytes,
    inputs: dict[str, object],
    dependencies: list[dict[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    environment = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    for key in ("SYSTEMROOT", "WINDIR"):
        value = os.environ.get(key)
        if value:
            environment[key] = value
    with tempfile.TemporaryDirectory(
        prefix="design-dna-codex-validation-"
    ) as temporary:
        snapshot_root = Path(temporary)
        snapshot_plugin = snapshot_root / "plugin"
        snapshot_dependency = snapshot_root / "dependencies"
        snapshot_plugin.mkdir()
        snapshot_dependency.mkdir()
        assert_supported_validator_surface(plugin_root)
        snapshot_tree(
            plugin_root / ".codex-plugin",
            snapshot_plugin / ".codex-plugin",
            expected=inputs["plugin_manifest_tree"],
        )
        snapshot_tree(
            plugin_root / "skills",
            snapshot_plugin / "skills",
            expected=inputs["skills_tree"],
        )
        captured_dependency = {
            "name": "PyYAML",
            "version": importlib.metadata.version("PyYAML"),
            **source_tree_record(
                pyyaml_source_root(),
                copy_to=snapshot_dependency,
            ),
        }
        if dependencies != [captured_dependency]:
            raise ToolFailure(
                "codex-plugin-attestation-dependency-unstable",
                (
                    "PyYAML source changed before its private snapshot "
                    "was captured."
                ),
            )
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    "-X",
                    "utf8",
                    "-c",
                    VALIDATOR_WRAPPER,
                    str(snapshot_dependency),
                    str(snapshot_plugin),
                ],
                cwd=snapshot_root,
                env=environment,
                input=validator_source,
                capture_output=True,
                timeout=VALIDATION_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ToolFailure(
                "codex-plugin-validator-execution-failed",
                str(exc),
                validator_path,
            ) from exc
        if (
            tree_binding(snapshot_plugin, ".codex-plugin")
            != inputs["plugin_manifest_tree"]
            or tree_binding(snapshot_plugin, "skills")
            != inputs["skills_tree"]
            or {
                "name": "PyYAML",
                "version": importlib.metadata.version("PyYAML"),
                **source_tree_record(snapshot_dependency / "yaml"),
            }
            != dependencies[0]
        ):
            raise ToolFailure(
                "codex-plugin-attestation-snapshot-drift",
                (
                    "A private validator input snapshot changed during "
                    "validation."
                ),
            )
    if (
        len(completed.stdout) > MAX_OUTPUT_BYTES
        or len(completed.stderr) > MAX_OUTPUT_BYTES
    ):
        raise ToolFailure(
            "codex-plugin-validator-output-too-large",
            "Validator output exceeded the bounded attestation limit.",
            validator_path,
        )
    if completed.returncode != 0:
        raise ToolFailure(
            "codex-plugin-validation-failed",
            (
                f"Pinned validator returned {completed.returncode}; "
                "its output content was withheld."
            ),
            validator_path,
        )
    normalized_stdout = completed.stdout.replace(b"\r\n", b"\n")
    expected_stdout = (
        f"Plugin validation passed: {snapshot_plugin.resolve()}\n"
    ).encode("utf-8")
    success_marker_observed = (
        normalized_stdout == expected_stdout
        and b"\r" not in normalized_stdout
        and completed.stderr == b""
    )
    if not success_marker_observed:
        raise ToolFailure(
            "codex-plugin-validator-output-contract-failed",
            (
                "Validator exited zero without exactly one expected success "
                "line and empty stderr; output content was withheld."
            ),
            validator_path,
        )
    return (
        {"status": "passed", "return_code": 0},
        {
            "success_marker_observed": True,
            "exact_success_line_observed": True,
            "stderr_empty": True,
            "content_persisted": False,
        },
    )


def schema_validator(schema_path: Path) -> Draft202012Validator:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(
        schema,
        format_checker=strict_format_checker(),
    )


def validate_record(
    validator: Draft202012Validator,
    payload: object,
    path: Path,
) -> None:
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if errors:
        message = "; ".join(
            f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ToolFailure(
            "codex-plugin-attestation-schema-invalid",
            message,
            path,
        )


def load_trust_policy(
    plugin_root: Path,
) -> tuple[dict[str, object], str]:
    policy_path = plugin_root / TRUST_POLICY_RELATIVE
    schema_path = (
        plugin_root
        / "maintainer"
        / "schemas"
        / "codex-validator-trust.schema.json"
    )
    data, digest = stable_file(policy_path)
    def reject_duplicates(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        payload = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ToolFailure(
            "codex-plugin-validator-trust-invalid",
            str(exc),
            policy_path,
        ) from exc
    validator = schema_validator(schema_path)
    validate_record(validator, payload, policy_path)
    if not isinstance(payload, dict):
        raise ToolFailure(
            "codex-plugin-validator-trust-invalid",
            "Validator trust policy must be an object.",
            policy_path,
        )
    try:
        reviewed_at = date.fromisoformat(str(payload["reviewed_at"]))
        review_due = date.fromisoformat(str(payload["review_due"]))
    except (KeyError, ValueError) as exc:
        raise ToolFailure(
            "codex-plugin-validator-trust-date-invalid",
            "Validator trust review dates are invalid.",
            policy_path,
        ) from exc
    if review_due < reviewed_at or (
        review_due - reviewed_at > timedelta(days=180)
    ):
        raise ToolFailure(
            "codex-plugin-validator-trust-date-invalid",
            "Validator trust dates must be ordered and span at most 180 days.",
            policy_path,
        )
    return payload, digest


def ensure_trust_policy_date(
    trust_policy: dict[str, object],
    observed: date,
    *,
    require_current: bool,
) -> None:
    try:
        reviewed_at = date.fromisoformat(str(trust_policy["reviewed_at"]))
        review_due = date.fromisoformat(str(trust_policy["review_due"]))
    except (KeyError, ValueError) as exc:
        raise ToolFailure(
            "codex-plugin-validator-trust-date-invalid",
            "Validator trust review dates are invalid.",
        ) from exc
    if observed < reviewed_at or observed > review_due:
        code = (
            "codex-plugin-validator-trust-overdue"
            if observed > review_due
            else "codex-plugin-validator-trust-not-yet-valid"
        )
        raise ToolFailure(
            code,
            "Attestation time falls outside the trust pin review window.",
        )
    if require_current:
        today = datetime.now(timezone.utc).date()
        if today < reviewed_at:
            raise ToolFailure(
                "codex-plugin-validator-trust-not-yet-valid",
                "Validator trust review date is in the future.",
            )
        if today > review_due:
            raise ToolFailure(
                "codex-plugin-validator-trust-overdue",
                "Validator trust pin review is overdue for new evidence.",
            )


def timestamp_value(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ToolFailure(
            "codex-plugin-attestation-time-invalid",
            "Attestation created_at must be an RFC 3339 timestamp.",
        ) from exc
    if parsed.tzinfo is None:
        raise ToolFailure(
            "codex-plugin-attestation-time-invalid",
            "Attestation created_at must include a timezone.",
        )
    return parsed.astimezone(timezone.utc)


def timestamp_date(value: str) -> date:
    return timestamp_value(value).date()


def create_attestation(
    plugin_root: Path,
    validator_path: Path,
    *,
    created_at: str | None = None,
    require_current_trust: bool = True,
) -> dict[str, object]:
    plugin_root = absolute(plugin_root)
    validator_path = absolute(validator_path)
    if is_within(validator_path, plugin_root):
        raise ToolFailure(
            "codex-plugin-validator-not-external",
            "The official validator must be supplied from outside the package.",
            validator_path,
        )
    schema_path = (
        plugin_root
        / "maintainer"
        / "schemas"
        / "codex-plugin-validation-attestation.schema.json"
    )
    validator = schema_validator(schema_path)
    trust_policy, trust_policy_sha256 = load_trust_policy(plugin_root)
    record_created_at = created_at or utc_now()
    if timestamp_value(record_created_at) > (
        datetime.now(timezone.utc) + ATTESTATION_CLOCK_SKEW
    ):
        raise ToolFailure(
            "codex-plugin-attestation-time-invalid",
            "Attestation created_at is in the future.",
        )
    ensure_trust_policy_date(
        trust_policy,
        timestamp_date(record_created_at),
        require_current=require_current_trust,
    )
    before_inputs = input_records(plugin_root)
    before_validator, validator_source = trusted_validator(
        validator_path,
        trust_policy,
        trust_policy_sha256,
    )
    before_python_sha256 = current_python_sha256()
    before_dependencies = dependency_records()
    result, output = run_validator(
        plugin_root,
        validator_path,
        validator_source,
        before_inputs,
        before_dependencies,
    )
    after_inputs = input_records(plugin_root)
    after_trust_policy, after_trust_policy_sha256 = load_trust_policy(
        plugin_root
    )
    after_validator = validator_record(
        validator_path,
        after_trust_policy,
        after_trust_policy_sha256,
    )
    after_python_sha256 = current_python_sha256()
    after_dependencies = dependency_records()
    if (
        before_inputs != after_inputs
        or before_validator != after_validator
        or trust_policy != after_trust_policy
        or trust_policy_sha256 != after_trust_policy_sha256
        or before_python_sha256 != after_python_sha256
        or before_dependencies != after_dependencies
    ):
        raise ToolFailure(
            "codex-plugin-attestation-input-unstable",
            "Plugin or validator inputs changed during validation.",
        )
    record = {
        "schema_version": 1,
        "record_type": (
            "design-dna-codex-plugin-validation-attestation"
        ),
        "created_at": record_created_at,
        "package": "design-dna",
        "release_version": release_version(plugin_root),
        "validator": before_validator,
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable": PYTHON_TOKEN,
            "executable_sha256": before_python_sha256,
        },
        "dependencies": before_dependencies,
        "command": ABSTRACT_COMMAND,
        "inputs": before_inputs,
        "result": result,
        "output": output,
    }
    validate_record(validator, record, schema_path)
    return record


def comparable(payload: dict[str, object]) -> dict[str, object]:
    copy = json.loads(json.dumps(payload))
    copy.pop("created_at", None)
    return copy


def atomic_write_json(path: Path, payload: object) -> None:
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise ToolFailure(
            "codex-plugin-attestation-write-failed",
            str(exc),
            path,
        ) from exc
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    plugin_default = Path(__file__).resolve().parents[2]
    parser.add_argument("--plugin-root", type=Path, default=plugin_default)
    parser.add_argument(
        "--validator",
        type=Path,
        required=True,
        help="Absolute external Plugin Creator validate_plugin.py path.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if not args.validator.is_absolute():
            raise ToolFailure(
                "codex-plugin-validator-path-not-absolute",
                "--validator must be an absolute external path.",
                args.validator,
            )
        plugin_root = absolute(args.plugin_root)
        output = absolute(
            args.output
            or (
                plugin_root
                / "maintainer"
                / "attestations"
                / "codex-plugin-validation.json"
            )
        )
        expected_output = (
            plugin_root
            / "maintainer"
            / "attestations"
            / "codex-plugin-validation.json"
        )
        if output != expected_output:
            raise ToolFailure(
                "codex-plugin-attestation-output-unsafe",
                "Use the exact Codex plugin-validation attestation path.",
                output,
            )
        assert_no_reparse_path(output, stop=plugin_root)
        validator = schema_validator(
            plugin_root
            / "maintainer"
            / "schemas"
            / "codex-plugin-validation-attestation.schema.json"
        )
        if args.check:
            if not output.is_file():
                raise ToolFailure(
                    "codex-plugin-attestation-missing",
                    "The Codex plugin-validation attestation is missing.",
                    output,
                )
            recorded = load_json(output)
            validate_record(validator, recorded, output)
            if not isinstance(recorded, dict):
                raise ToolFailure(
                    "codex-plugin-attestation-schema-invalid",
                    "Recorded attestation must be an object.",
                    output,
                )
            live = create_attestation(
                plugin_root,
                args.validator,
                created_at=recorded.get("created_at"),
                require_current_trust=False,
            )
            if (
                comparable(recorded) != comparable(live)
            ):
                raise ToolFailure(
                    "codex-plugin-attestation-drift",
                    (
                        "Recorded Codex plugin-validation evidence differs "
                        "from a fresh official-validator run."
                    ),
                    output,
                )
        else:
            if output.exists():
                raise ToolFailure(
                    "codex-plugin-attestation-exists",
                    "Attestations are immutable; use --check or deliberately remove it.",
                    output,
                )
            live = create_attestation(plugin_root, args.validator)
            atomic_write_json(output, live)
        emit({
            "ok": True,
            "check": bool(args.check),
            "attestation": str(output),
            "validator_sha256": live["validator"]["sha256"],
            "release_version": live["release_version"],
        })
        return 0
    except (
        ToolFailure,
        OSError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        failure = (
            exc.issue.as_dict()
            if isinstance(exc, ToolFailure)
            else {
                "code": "codex-plugin-attestation-unexpected-error",
                "message": str(exc),
                "severity": "error",
            }
        )
        emit({"ok": False, "failures": [failure]})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
