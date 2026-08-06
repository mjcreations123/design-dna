#!/usr/bin/env python3
"""Replay and attest the direct installer lifecycle in a fresh isolated home.

This is a behavioral proof for the repository's direct Codex and Claude Code
filesystem routes. It does not modify the current user's installation, prove
marketplace plugin activation or current-session visibility, or make the
installer crash-durable.
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
import json
import os
import platform
import re
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

import manage_install
from common import (
    ToolFailure,
    absolute,
    assert_no_reparse_path,
    emit,
    load_json,
    strict_format_checker,
)


sys.dont_write_bytecode = True

SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
MAX_TOOL_BYTES = 16 * 1024 * 1024
MAX_OPERATION_BYTES = 4 * 1024 * 1024
MANAGER_TIMEOUT_SECONDS = 120
PRIOR_MARKER_NAME = ".lifecycle-attestation-prior"
PRIOR_MARKER_BYTES = (
    b"Design DNA lifecycle attestation prior-runtime fixture.\n"
)
INPUT_PATHS = {
    "attestor": "maintainer/scripts/attest_install_lifecycle.py",
    "manager": "maintainer/scripts/manage_install.py",
    "cache_preflight": "maintainer/scripts/cache_preflight.py",
    "common": "maintainer/scripts/common.py",
    "operation_schema": "maintainer/schemas/install-operation.schema.json",
    "attestation_schema": (
        "maintainer/schemas/install-lifecycle-attestation.schema.json"
    ),
    "release_schema": "maintainer/schemas/release.schema.json",
}
STAGE_SPECS = (
    {
        "name": "install-prior",
        "command": "install",
        "source_role": "prior-fixture",
        "action": "installed",
        "installed": "prior",
        "previous": None,
        "backup_id": False,
        "replacement_backup_id": False,
        "canonical_parity": None,
        "post": "prior",
    },
    {
        "name": "update-current",
        "command": "update",
        "source_role": "release-runtime",
        "action": "updated",
        "installed": "runtime",
        "previous": "prior",
        "backup_id": True,
        "replacement_backup_id": False,
        "canonical_parity": None,
        "post": "runtime",
    },
    {
        "name": "rollback-prior",
        "command": "rollback",
        "source_role": "release-runtime",
        "action": "rolled-back",
        "installed": "prior",
        "previous": "runtime",
        "backup_id": True,
        "replacement_backup_id": True,
        "canonical_parity": False,
        "post": "prior",
    },
    {
        "name": "uninstall-prior",
        "command": "uninstall",
        "source_role": "release-runtime",
        "action": "uninstalled",
        "installed": None,
        "previous": "prior",
        "backup_id": True,
        "replacement_backup_id": False,
        "canonical_parity": None,
        "post": None,
    },
)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def strict_json_bytes(data: bytes, path: Path) -> object:
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
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ToolFailure(
            "install-lifecycle-json-invalid",
            str(exc),
            path,
        ) from exc


def stable_file(
    path: Path,
    *,
    maximum_bytes: int = MAX_TOOL_BYTES,
) -> tuple[bytes, str]:
    path = absolute(path)
    assert_no_reparse_path(path)
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise ToolFailure(
                "install-lifecycle-input-not-file",
                "Attested input must be a regular file.",
                path,
            )
        if info.st_size <= 0 or info.st_size > maximum_bytes:
            raise ToolFailure(
                "install-lifecycle-input-size-invalid",
                "Attested input has an invalid or unbounded size.",
                path,
            )
        first = path.read_bytes()
        second = path.read_bytes()
    except ToolFailure:
        raise
    except OSError as exc:
        raise ToolFailure(
            "install-lifecycle-input-read-failed",
            str(exc),
            path,
        ) from exc
    if first != second or len(first) != info.st_size:
        raise ToolFailure(
            "install-lifecycle-input-unstable",
            "Attested input changed while it was read.",
            path,
        )
    return first, hashlib.sha256(first).hexdigest()


def schema_validator(path: Path) -> Draft202012Validator:
    schema = load_json(path)
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise ToolFailure(
            "install-lifecycle-schema-invalid",
            str(exc),
            path,
        ) from exc
    return Draft202012Validator(
        schema,
        format_checker=strict_format_checker(),
    )


def validate(
    validator: Draft202012Validator,
    payload: object,
    *,
    path: Path,
    code: str,
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
        raise ToolFailure(code, message, path)


def identity_record(
    identity: manage_install.TreeIdentity,
) -> dict[str, object]:
    return {
        "sha256": identity.sha256,
        "entry_count": identity.entries,
        "file_count": identity.files,
        "byte_count": identity.bytes,
    }


def expected_hash(
    role: str | None,
    *,
    runtime: manage_install.TreeIdentity,
    prior: manage_install.TreeIdentity,
) -> str | None:
    if role is None:
        return None
    return runtime.sha256 if role == "runtime" else prior.sha256


def operation_record(
    plugin_root: Path,
    command: str,
    home: Path,
    source: Path,
    backup_root: Path,
) -> tuple[dict[str, object], bytes]:
    arguments = [
        sys.executable,
        "-B",
        str(plugin_root / "maintainer" / "scripts" / "manage_install.py"),
        command,
        "--host",
        "all",
        "--home",
        str(home),
        "--source",
        str(source),
        "--backup-root",
        str(backup_root),
    ]
    environment = dict(os.environ)
    for name in (
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "PYTHONINSPECT",
    ):
        environment.pop(name, None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    try:
        completed = subprocess.run(
            arguments,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            cwd=plugin_root,
            env=environment,
            timeout=MANAGER_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolFailure(
            "install-lifecycle-manager-unavailable",
            f"{command} could not complete: {exc}",
        ) from exc
    if len(completed.stdout) > MAX_OPERATION_BYTES:
        raise ToolFailure(
            "install-lifecycle-operation-unbounded",
            f"{command} emitted oversized output.",
        )
    if completed.stderr:
        raise ToolFailure(
            "install-lifecycle-manager-stderr",
            f"{command} emitted unexpected stderr.",
        )
    if completed.returncode != 0:
        raise ToolFailure(
            "install-lifecycle-operation-failed",
            f"{command} exited with status {completed.returncode}.",
        )
    if not completed.stdout.endswith(b"\n") or len(
        completed.stdout.splitlines()
    ) != 1:
        raise ToolFailure(
            "install-lifecycle-operation-output-invalid",
            f"{command} did not emit exactly one JSON line.",
        )
    payload = strict_json_bytes(
        completed.stdout,
        plugin_root / "maintainer" / "scripts" / "manage_install.py",
    )
    if not isinstance(payload, dict):
        raise ToolFailure(
            "install-lifecycle-operation-output-invalid",
            f"{command} output must be a JSON object.",
        )
    return payload, completed.stdout


def summarize_stage(
    payload: dict[str, object],
    raw: bytes,
    spec: dict[str, object],
    *,
    source: Path,
    source_identity: manage_install.TreeIdentity,
    runtime: manage_install.TreeIdentity,
    prior: manage_install.TreeIdentity,
    operation_validator: Draft202012Validator,
    operation_schema: Path,
) -> dict[str, object]:
    validate(
        operation_validator,
        payload,
        path=operation_schema,
        code="install-lifecycle-operation-schema-invalid",
    )
    command = str(spec["command"])
    if (
        payload.get("record_type") != "design-dna-install-operation"
        or payload.get("operation") != command
        or payload.get("ok") is not True
        or payload.get("dry_run") is not False
        or payload.get("errors") != []
    ):
        raise ToolFailure(
            "install-lifecycle-operation-semantic-invalid",
            f"{command} contradicted the successful operation contract.",
        )
    source_record = payload.get("source")
    expected_source = source_identity.as_dict(absolute(source))
    if source_record != expected_source:
        raise ToolFailure(
            "install-lifecycle-source-identity-mismatch",
            f"{command} did not bind the exact selected source tree.",
        )
    hosts = payload.get("hosts")
    changes = payload.get("changes")
    if (
        not isinstance(hosts, list)
        or not isinstance(changes, list)
        or [item.get("host") for item in hosts if isinstance(item, dict)]
        != ["codex", "claude"]
        or [item.get("host") for item in changes if isinstance(item, dict)]
        != ["codex", "claude"]
        or len(hosts) != 2
        or len(changes) != 2
    ):
        raise ToolFailure(
            "install-lifecycle-host-set-invalid",
            f"{command} did not operate on exactly Codex and Claude.",
        )
    installed = expected_hash(
        spec["installed"],
        runtime=runtime,
        prior=prior,
    )
    previous = expected_hash(
        spec["previous"],
        runtime=runtime,
        prior=prior,
    )
    change_summaries: list[dict[str, object]] = []
    for host_name, change in zip(("codex", "claude"), changes):
        if not isinstance(change, dict):
            raise ToolFailure(
                "install-lifecycle-change-invalid",
                f"{command} emitted a non-object change.",
            )
        backup_present = change.get("backup_id") is not None
        replacement_present = (
            change.get("replacement_backup_id") is not None
        )
        canonical = change.get("canonical_parity")
        if (
            change.get("host") != host_name
            or change.get("action") != spec["action"]
            or change.get("executed") is not True
            or change.get("installed_sha256") != installed
            or change.get("previous_sha256") != previous
            or backup_present is not spec["backup_id"]
            or replacement_present is not spec["replacement_backup_id"]
            or canonical != spec["canonical_parity"]
        ):
            raise ToolFailure(
                "install-lifecycle-change-invalid",
                f"{command} change semantics do not match the lifecycle.",
            )
        change_summaries.append({
            "host": host_name,
            "action": str(change["action"]),
            "executed": True,
            "installed_sha256": installed,
            "previous_sha256": previous,
            "backup_id_present": backup_present,
            "replacement_backup_created": replacement_present,
            "canonical_parity": canonical,
        })
    post_summaries: list[dict[str, object]] = []
    post_hash = expected_hash(
        spec["post"],
        runtime=runtime,
        prior=prior,
    )
    for host_name, host in zip(("codex", "claude"), hosts):
        if not isinstance(host, dict) or not isinstance(
            host.get("target"),
            dict,
        ):
            raise ToolFailure(
                "install-lifecycle-post-state-invalid",
                f"{command} host state is incomplete.",
            )
        target = host["target"]
        exists = post_hash is not None
        if (
            target.get("exists") is not exists
            or target.get("sha256") != post_hash
            or host.get("collision_candidates") != []
        ):
            raise ToolFailure(
                "install-lifecycle-post-state-invalid",
                (
                    f"{command} left an unexpected filesystem discovery "
                    "candidate state."
                ),
            )
        post_summaries.append({
            "host": host_name,
            "exists": exists,
            "sha256": post_hash,
            "release_runtime_parity": (
                None if not exists else post_hash == runtime.sha256
            ),
        })
    summary = {
        "command": command,
        "ok": True,
        "dry_run": False,
        "host_count": 2,
        "errors_count": 0,
        "changes": change_summaries,
    }
    return {
        "name": str(spec["name"]),
        "command": command,
        "source_role": str(spec["source_role"]),
        "source_sha256": source_identity.sha256,
        "operation_record_sha256": hashlib.sha256(raw).hexdigest(),
        "semantic_record_sha256": hashlib.sha256(
            canonical_json(summary)
        ).hexdigest(),
        "operation_schema_valid": True,
        "operation": summary,
        "post_state": post_summaries,
    }


def final_host_record(
    host: str,
    config: manage_install.HostConfig,
    *,
    runtime: manage_install.TreeIdentity,
    prior: manage_install.TreeIdentity,
    operation_validator: Draft202012Validator,
    operation_schema: Path,
) -> dict[str, object]:
    if manage_install.entry_exists(config.target):
        raise ToolFailure(
            "install-lifecycle-uninstall-incomplete",
            f"The isolated {host} route remains after uninstall.",
            config.target,
        )
    backups = manage_install.list_backups(config)
    records: list[dict[str, object]] = []
    for backup in backups:
        validate(
            operation_validator,
            backup.metadata,
            path=operation_schema,
            code="install-lifecycle-backup-schema-invalid",
        )
        records.append({
            "reason": backup.metadata["reason"],
            "status": backup.metadata["status"],
            "skill_sha256": backup.metadata["skill_sha256"],
            "payload_present": backup.identity is not None,
        })
    records.sort(key=lambda item: str(item["reason"]))
    expected = [
        {
            "reason": "rollback-replaced-current",
            "status": "available",
            "skill_sha256": runtime.sha256,
            "payload_present": True,
        },
        {
            "reason": "uninstall",
            "status": "available",
            "skill_sha256": prior.sha256,
            "payload_present": True,
        },
        {
            "reason": "update",
            "status": "restored",
            "skill_sha256": prior.sha256,
            "payload_present": False,
        },
    ]
    if records != expected:
        raise ToolFailure(
            "install-lifecycle-backup-state-invalid",
            f"The isolated {host} backup history is not the expected lifecycle.",
            config.backup_root,
        )
    counts = {
        status: sum(
            item["status"] == status
            for item in records
        )
        for status in (
            "available",
            "restored",
            "failed",
            "transaction-rolled-back",
        )
    }
    return {
        "host": host,
        "route_exists": False,
        "backup_record_count": len(records),
        "available_count": counts["available"],
        "restored_count": counts["restored"],
        "failed_count": counts["failed"],
        "transaction_rolled_back_count": counts[
            "transaction-rolled-back"
        ],
        "records": records,
    }


def release_version(
    plugin_root: Path,
    release_validator: Draft202012Validator,
) -> str:
    path = plugin_root / "skills" / "design-dna" / "release.json"
    data, _digest = stable_file(path)
    payload = strict_json_bytes(data, path)
    validate(
        release_validator,
        payload,
        path=path,
        code="install-lifecycle-release-record-invalid",
    )
    if not isinstance(payload, dict):
        raise ToolFailure(
            "install-lifecycle-release-record-invalid",
            "release.json must be an object.",
            path,
        )
    version = payload.get("version")
    if (
        payload.get("package") != "design-dna"
        or not isinstance(version, str)
        or SEMVER.fullmatch(version) is None
    ):
        raise ToolFailure(
            "install-lifecycle-release-record-invalid",
            "release.json does not identify a Design DNA SemVer release.",
            path,
        )
    return version


def input_records(plugin_root: Path) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for key, relative in INPUT_PATHS.items():
        data, digest = stable_file(plugin_root / relative)
        records[key] = {
            "path": relative,
            "sha256": digest,
            "bytes": len(data),
        }
    return records


def create_attestation(plugin_root: Path) -> dict[str, object]:
    plugin_root = absolute(plugin_root)
    runtime_source = plugin_root / "skills" / "design-dna"
    operation_schema = (
        plugin_root
        / "maintainer"
        / "schemas"
        / "install-operation.schema.json"
    )
    attestation_schema = (
        plugin_root
        / "maintainer"
        / "schemas"
        / "install-lifecycle-attestation.schema.json"
    )
    release_schema = (
        plugin_root / "maintainer" / "schemas" / "release.schema.json"
    )
    operation_validator = schema_validator(operation_schema)
    attestation_validator = schema_validator(attestation_schema)
    release_validator = schema_validator(release_schema)
    version = release_version(plugin_root, release_validator)
    runtime = manage_install.validate_design_dna_tree(runtime_source)
    files = input_records(plugin_root)
    with tempfile.TemporaryDirectory(
        prefix="design-dna-lifecycle-attestation-"
    ) as temporary:
        isolation = Path(temporary)
        home = isolation / "home"
        sources = isolation / "sources"
        backup_root = home / ".design-dna" / "backups"
        home.mkdir()
        sources.mkdir()
        current_source = sources / "current"
        prior_source = sources / "prior"
        manage_install.copy_exact(runtime_source, current_source)
        manage_install.copy_exact(runtime_source, prior_source)
        marker = prior_source / PRIOR_MARKER_NAME
        marker.write_bytes(PRIOR_MARKER_BYTES)
        current = manage_install.validate_design_dna_tree(current_source)
        prior = manage_install.validate_design_dna_tree(prior_source)
        if current.records != runtime.records or prior.records == runtime.records:
            raise ToolFailure(
                "install-lifecycle-fixture-identity-invalid",
                "Lifecycle sources were not derived from the exact runtime.",
            )
        stages: list[dict[str, object]] = []
        for spec in STAGE_SPECS:
            source = (
                prior_source
                if spec["source_role"] == "prior-fixture"
                else current_source
            )
            source_identity = (
                prior
                if spec["source_role"] == "prior-fixture"
                else current
            )
            payload, raw = operation_record(
                plugin_root,
                str(spec["command"]),
                home,
                source,
                backup_root,
            )
            stages.append(
                summarize_stage(
                    payload,
                    raw,
                    spec,
                    source=source,
                    source_identity=source_identity,
                    runtime=runtime,
                    prior=prior,
                    operation_validator=operation_validator,
                    operation_schema=operation_schema,
                )
            )
        configs = manage_install.host_configs(home, backup_root)
        final_hosts = [
            final_host_record(
                host,
                configs[host],
                runtime=runtime,
                prior=prior,
                operation_validator=operation_validator,
                operation_schema=operation_schema,
            )
            for host in ("codex", "claude")
        ]
        if (
            manage_install.validate_design_dna_tree(runtime_source).records
            != runtime.records
        ):
            raise ToolFailure(
                "install-lifecycle-runtime-unstable",
                "The release runtime changed during lifecycle replay.",
                runtime_source,
            )
        if input_records(plugin_root) != files:
            raise ToolFailure(
                "install-lifecycle-tooling-unstable",
                "Attested lifecycle tooling changed during replay.",
                plugin_root / "maintainer",
            )
        attestation = {
            "schema_version": 1,
            "record_type": (
                "design-dna-install-lifecycle-attestation"
            ),
            "created_at": utc_now(),
            "package": "design-dna",
            "release_version": version,
            "inputs": {
                "runtime_source": "skills/design-dna",
                "runtime": identity_record(runtime),
                "files": files,
            },
            "environment": {
                "isolated_home": True,
                "manager_invocation": "fresh-subprocess-per-stage",
                "hosts": ["codex", "claude"],
                "python": {
                    "implementation": platform.python_implementation(),
                    "version": platform.python_version(),
                },
                "platform": {
                    "system": platform.system() or "unknown",
                    "machine": platform.machine() or "unknown",
                },
            },
            "prior_fixture": {
                "derivation": "canonical-runtime-plus-test-marker",
                "marker_file": PRIOR_MARKER_NAME,
                "marker_sha256": hashlib.sha256(
                    PRIOR_MARKER_BYTES
                ).hexdigest(),
                "identity": identity_record(prior),
                "differs_from_runtime": True,
            },
            "stages": stages,
            "final_state": {
                "routes_absent": True,
                "backup_records_schema_valid": True,
                "hosts": final_hosts,
            },
            "outcome": {
                "passed": True,
                "operations_schema_valid": True,
                "backup_records_schema_valid": True,
                "runtime_identity_observed": True,
                "fresh_lifecycle_replay_required_on_check": True,
            },
        }
        validate(
            attestation_validator,
            attestation,
            path=attestation_schema,
            code="install-lifecycle-attestation-invalid",
        )
        return attestation


def comparable(payload: dict[str, object]) -> dict[str, object]:
    copy = json.loads(json.dumps(payload))
    copy.pop("created_at", None)
    for stage in copy.get("stages", []):
        if isinstance(stage, dict):
            # Raw manager records contain isolated paths, backup IDs, and
            # timestamps. Their exact hashes are creation-time evidence. A
            # check proves behavior by replaying every stage and comparing the
            # stable semantic commitment instead.
            stage.pop("operation_record_sha256", None)
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
            "install-lifecycle-attestation-write-failed",
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
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        plugin_root = absolute(args.plugin_root)
        expected_output = (
            plugin_root
            / "maintainer"
            / "attestations"
            / "install-lifecycle.json"
        )
        output = absolute(args.output or expected_output)
        if output != expected_output:
            raise ToolFailure(
                "install-lifecycle-output-unsafe",
                "Use the exact maintainer lifecycle-attestation path.",
                output,
            )
        if not output.parent.is_dir():
            raise ToolFailure(
                "install-lifecycle-output-parent-missing",
                "The attestation directory does not exist.",
                output.parent,
            )
        live = create_attestation(plugin_root)
        validator = schema_validator(
            plugin_root
            / "maintainer"
            / "schemas"
            / "install-lifecycle-attestation.schema.json"
        )
        if args.check:
            if not output.is_file():
                raise ToolFailure(
                    "install-lifecycle-attestation-missing",
                    "The lifecycle attestation does not exist.",
                    output,
                )
            recorded = load_json(output)
            validate(
                validator,
                recorded,
                path=output,
                code="install-lifecycle-attestation-invalid",
            )
            if (
                not isinstance(recorded, dict)
                or comparable(recorded) != comparable(live)
            ):
                raise ToolFailure(
                    "install-lifecycle-attestation-drift",
                    (
                        "Recorded lifecycle evidence differs from a fresh "
                        "isolated replay."
                    ),
                    output,
                )
        else:
            if output.exists():
                raise ToolFailure(
                    "install-lifecycle-attestation-exists",
                    "Attestations are immutable; use --check or remove it deliberately.",
                    output,
                )
            atomic_write_json(output, live)
        emit({
            "ok": True,
            "check": bool(args.check),
            "attestation": str(output),
            "release_version": live["release_version"],
            "hosts": ["codex", "claude"],
            "lifecycle": [
                "install",
                "update",
                "rollback",
                "uninstall",
            ],
        })
        return 0
    except (
        ToolFailure,
        manage_install.ManagerError,
        OSError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        if isinstance(exc, ToolFailure):
            failure = exc.issue.as_dict()
        elif isinstance(exc, manage_install.ManagerError):
            failure = exc.as_dict()
        else:
            failure = {
                "code": "install-lifecycle-unexpected-error",
                "message": str(exc),
                "severity": "error",
            }
        emit({"ok": False, "failures": [failure]})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
