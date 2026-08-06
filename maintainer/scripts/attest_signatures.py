#!/usr/bin/env python3
"""Verify detached release signatures and emit hash-bound evidence.

The trusted primary fingerprint is deliberately supplied outside the release
bundle. This tool never generates a key, signs an artifact, downloads a key, or
turns an unsigned package into a signed one.
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
import re
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from jsonschema import Draft202012Validator

from common import (
    ToolFailure,
    absolute,
    assert_no_reparse_path,
    emit,
    load_json,
    strict_format_checker,
)


FINGERPRINT = re.compile(r"^(?:[0-9A-F]{40}|[0-9A-F]{64})$")
KEY_ID = re.compile(r"^(?:[0-9A-F]{8}|[0-9A-F]{16})$")
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,240}$")
ARCHIVE_NAME = re.compile(
    r"^design-dna-[0-9A-Za-z.+-]+-[0-9a-f]{12}\.zip$"
)
GPG_VERSION = re.compile(
    r"^gpg \(GnuPG\) "
    r"(?P<version>[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:[-+._0-9A-Za-z]*)?)$"
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_CHECKSUM_BYTES = 4096
MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_SIGNATURE_BYTES = 1024 * 1024
MAX_GPG_EXECUTABLE_BYTES = 256 * 1024 * 1024
GPG_TIMEOUT_SECONDS = 120
ALLOWED_STATUS_KEYWORDS = {
    "NEWSIG",
    "KEY_CONSIDERED",
    "SIG_ID",
    "GOODSIG",
    "VALIDSIG",
    "TRUST_UNDEFINED",
    "TRUST_NEVER",
    "TRUST_MARGINAL",
    "TRUST_FULLY",
    "TRUST_ULTIMATE",
}
FAILURE_STATUS_KEYWORDS = {
    "BADSIG",
    "ERRSIG",
    "EXPSIG",
    "EXPKEYSIG",
    "REVKEYSIG",
    "NO_PUBKEY",
    "NODATA",
    "FAILURE",
    "ERROR",
}
GpgRunner = Callable[..., subprocess.CompletedProcess[str]]


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def timestamp(value: str, *, field: str) -> datetime:
    if not re.fullmatch(r"[0-9]{1,20}", value):
        raise ToolFailure(
            "release-signature-status-invalid",
            f"GPG {field} is not an integer timestamp.",
        )
    try:
        return datetime.fromtimestamp(int(value), timezone.utc)
    except (OSError, OverflowError, ValueError) as exc:
        raise ToolFailure(
            "release-signature-status-invalid",
            f"GPG {field} is outside the supported time range.",
        ) from exc


def rfc3339(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_fingerprint(value: str) -> str:
    normalized = value.strip().upper()
    if not FINGERPRINT.fullmatch(normalized):
        raise ToolFailure(
            "release-signature-fingerprint-invalid",
            (
                "Supply the owner's independently established full 40- or "
                "64-hex primary fingerprint; short key IDs are refused."
            ),
        )
    return normalized


def file_identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return (
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_size),
        int(info.st_mtime_ns),
    )


def stable_copy_and_digest(
    source: Path,
    destination: Path,
    *,
    maximum_bytes: int,
) -> tuple[str, int]:
    assert_no_reparse_path(source)
    try:
        before = source.stat()
        if not stat.S_ISREG(before.st_mode):
            raise ToolFailure(
                "release-signature-input-not-regular",
                "Signed inputs must be ordinary files.",
                source,
            )
        if before.st_size < 1 or before.st_size > maximum_bytes:
            raise ToolFailure(
                "release-signature-input-size-invalid",
                f"Input size must be between 1 and {maximum_bytes} bytes.",
                source,
            )
        digest = hashlib.sha256()
        copied = 0
        with source.open("rb") as source_stream, destination.open("xb") as output:
            opened_before = os.fstat(source_stream.fileno())
            if file_identity(before) != file_identity(opened_before):
                raise ToolFailure(
                    "release-signature-input-unstable",
                    "Input changed before verification staging began.",
                    source,
                )
            while chunk := source_stream.read(1024 * 1024):
                copied += len(chunk)
                if copied > maximum_bytes:
                    raise ToolFailure(
                        "release-signature-input-size-invalid",
                        f"Input exceeds {maximum_bytes} bytes.",
                        source,
                    )
                digest.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
            opened_after = os.fstat(source_stream.fileno())
        after = source.stat()
    except ToolFailure:
        raise
    except OSError as exc:
        raise ToolFailure(
            "release-signature-input-unreadable",
            str(exc),
            source,
        ) from exc
    if (
        copied != before.st_size
        or file_identity(before)
        != file_identity(opened_before)
        or file_identity(before)
        != file_identity(opened_after)
        or file_identity(before) != file_identity(after)
    ):
        raise ToolFailure(
            "release-signature-input-unstable",
            "Input changed while it was staged for verification.",
            source,
        )
    return digest.hexdigest(), copied


def stable_digest(path: Path, *, maximum_bytes: int) -> tuple[str, int]:
    with tempfile.TemporaryDirectory(
        prefix="design-dna-signature-digest-"
    ) as temporary:
        return stable_copy_and_digest(
            path,
            Path(temporary) / "input",
            maximum_bytes=maximum_bytes,
        )


def stable_bytes(path: Path, *, maximum_bytes: int) -> bytes:
    with tempfile.TemporaryDirectory(
        prefix="design-dna-signature-read-"
    ) as temporary:
        staged = Path(temporary) / "input"
        stable_copy_and_digest(
            path,
            staged,
            maximum_bytes=maximum_bytes,
        )
        try:
            return staged.read_bytes()
        except OSError as exc:
            raise ToolFailure(
                "release-signature-input-unreadable",
                str(exc),
                path,
            ) from exc


def strict_json(data: bytes, *, path: Path) -> object:
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
            "release-signature-package-record-invalid",
            "release-package.json is not strict UTF-8 JSON.",
            path,
        ) from exc


def validate_schema(payload: object, schema_path: Path, *, code: str) -> None:
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
            code,
            "; ".join(
                f"{'/'.join(map(str, error.path)) or '<root>'}: "
                f"{error.message}"
                for error in errors
            ),
            schema_path,
        )


def externally_supplied_gpg(
    plugin_root: Path,
    bundle_dir: Path,
    executable: str,
) -> tuple[Path, str, int]:
    candidate = Path(executable).expanduser()
    if not candidate.is_absolute():
        raise ToolFailure(
            "release-signature-gpg-path-not-absolute",
            (
                "Supply the independently installed GnuPG executable by "
                "absolute path; PATH lookup is not accepted for release proof."
            ),
        )
    candidate = absolute(candidate)
    if not candidate.is_file():
        raise ToolFailure(
            "release-signature-gpg-unavailable",
            "The selected GnuPG executable is not a regular file.",
            candidate,
        )
    assert_no_reparse_path(candidate)
    for forbidden in (plugin_root, bundle_dir):
        try:
            candidate.relative_to(forbidden)
        except ValueError:
            continue
        raise ToolFailure(
            "release-signature-gpg-inside-release",
            "The verifier executable must be supplied outside the release tree.",
            candidate,
        )
    if os.name != "nt" and not os.access(candidate, os.X_OK):
        raise ToolFailure(
            "release-signature-gpg-not-executable",
            "The selected GnuPG file is not executable.",
            candidate,
        )
    digest, size = stable_digest(
        candidate,
        maximum_bytes=MAX_GPG_EXECUTABLE_BYTES,
    )
    return candidate, digest, size


def gpg_version(
    executable: str,
    *,
    runner: GpgRunner = subprocess.run,
) -> str:
    try:
        result = runner(
            [executable, "--version"],
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="strict",
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
        raise ToolFailure(
            "release-signature-gpg-unavailable",
            "GnuPG is unavailable or did not return bounded UTF-8 output.",
        ) from exc
    first = result.stdout.splitlines()[0] if result.stdout else ""
    match = GPG_VERSION.fullmatch(first.strip())
    if result.returncode != 0 or match is None:
        raise ToolFailure(
            "release-signature-gpg-version-invalid",
            "The configured verifier did not identify itself as GnuPG.",
        )
    return match.group("version")


def parse_gpg_status(
    output: str,
    expected_primary_fingerprint: str,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    expected = normalize_fingerprint(expected_primary_fingerprint)
    records: dict[str, list[list[str]]] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not line.startswith("[GNUPG:] "):
            raise ToolFailure(
                "release-signature-status-invalid",
                "GPG status output contained a non-status record.",
            )
        parts = line[len("[GNUPG:] "):].split()
        if not parts:
            raise ToolFailure(
                "release-signature-status-invalid",
                "GPG emitted an empty status record.",
            )
        keyword = parts[0]
        if keyword in FAILURE_STATUS_KEYWORDS:
            raise ToolFailure(
                "release-signature-invalid",
                f"GPG rejected the detached signature ({keyword}).",
            )
        if keyword not in ALLOWED_STATUS_KEYWORDS:
            raise ToolFailure(
                "release-signature-status-unsupported",
                f"Unsupported GPG status record: {keyword}.",
            )
        records.setdefault(keyword, []).append(parts[1:])
    if (
        len(records.get("NEWSIG", [])) != 1
        or len(records.get("GOODSIG", [])) != 1
        or len(records.get("VALIDSIG", [])) != 1
    ):
        raise ToolFailure(
            "release-signature-status-invalid",
            "Expected exactly one NEWSIG, GOODSIG, and VALIDSIG record.",
        )
    good = records["GOODSIG"][0]
    valid = records["VALIDSIG"][0]
    if len(good) < 1 or len(valid) not in {9, 10}:
        raise ToolFailure(
            "release-signature-status-invalid",
            "GPG signature status fields are incomplete.",
        )
    key_id = good[0].upper()
    signing_fingerprint = valid[0].upper()
    primary_fingerprint = (
        valid[9].upper() if len(valid) == 10 else signing_fingerprint
    )
    if (
        not KEY_ID.fullmatch(key_id)
        or not FINGERPRINT.fullmatch(signing_fingerprint)
        or not FINGERPRINT.fullmatch(primary_fingerprint)
        or not signing_fingerprint.endswith(key_id)
    ):
        raise ToolFailure(
            "release-signature-status-invalid",
            "GPG key identifiers and fingerprints are inconsistent.",
        )
    if primary_fingerprint != expected:
        raise ToolFailure(
            "release-signature-fingerprint-mismatch",
            (
                "The valid signature does not chain to the independently "
                "established primary fingerprint."
            ),
        )
    try:
        public_key_algorithm = int(valid[6])
        hash_algorithm = int(valid[7])
    except (TypeError, ValueError) as exc:
        raise ToolFailure(
            "release-signature-status-invalid",
            "GPG algorithm identifiers are invalid.",
        ) from exc
    if public_key_algorithm not in {1, 3, 19, 22}:
        raise ToolFailure(
            "release-signature-public-key-algorithm-refused",
            "The signature uses a disallowed public-key algorithm.",
        )
    if hash_algorithm not in {8, 9, 10}:
        raise ToolFailure(
            "release-signature-hash-algorithm-refused",
            "The signature must use SHA-256, SHA-384, or SHA-512.",
        )
    if valid[8] != "00":
        raise ToolFailure(
            "release-signature-class-refused",
            "Only detached binary-document signatures are accepted.",
        )
    created = timestamp(valid[2], field="creation time")
    expires = (
        None
        if valid[3] == "0"
        else timestamp(valid[3], field="expiration time")
    )
    current = now or datetime.now(timezone.utc)
    if created > current + timedelta(minutes=5):
        raise ToolFailure(
            "release-signature-time-invalid",
            "The signature creation time is unreasonably in the future.",
        )
    if expires is not None and expires <= current:
        raise ToolFailure(
            "release-signature-expired",
            "The detached signature has expired.",
        )
    return {
        "status": "valid",
        "signing_fingerprint": signing_fingerprint,
        "primary_fingerprint": primary_fingerprint,
        "key_id": key_id,
        "signature_created_at": rfc3339(created),
        "signature_expires_at": (
            rfc3339(expires) if expires is not None else None
        ),
        "public_key_algorithm": public_key_algorithm,
        "hash_algorithm": hash_algorithm,
        "signature_class": valid[8],
        "gpg_status_sha256": hashlib.sha256(
            output.encode("utf-8")
        ).hexdigest(),
    }


def verify_detached(
    executable: str,
    signature: Path,
    artifact: Path,
    expected_primary_fingerprint: str,
    *,
    homedir: Path | None = None,
    runner: GpgRunner = subprocess.run,
) -> dict[str, object]:
    command = [
        executable,
        "--no-options",
        "--batch",
        "--no-tty",
        "--no-auto-key-retrieve",
        "--status-fd=1",
    ]
    if homedir is not None:
        command.extend(["--homedir", str(homedir)])
    command.extend(["--verify", str(signature), str(artifact)])
    try:
        result = runner(
            command,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="strict",
            capture_output=True,
            timeout=GPG_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
        raise ToolFailure(
            "release-signature-gpg-unavailable",
            "GnuPG could not complete detached-signature verification.",
        ) from exc
    if result.returncode != 0:
        # Parse status first so a precise, bounded failure code is retained.
        parse_gpg_status(result.stdout, expected_primary_fingerprint)
        raise ToolFailure(
            "release-signature-invalid",
            "GnuPG rejected the detached signature.",
        )
    return parse_gpg_status(
        result.stdout,
        expected_primary_fingerprint,
    )


def atomic_write_json(path: Path, payload: object) -> None:
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise ToolFailure(
            "release-signature-attestation-write-failed",
            str(exc),
            path,
        ) from exc
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def create_attestation(
    plugin_root: Path,
    bundle_dir: Path,
    trusted_fingerprint: str,
    *,
    gpg_executable: str,
    homedir: Path | None = None,
    runner: GpgRunner = subprocess.run,
) -> dict[str, object]:
    plugin_root = absolute(plugin_root)
    bundle_dir = absolute(bundle_dir)
    expected_fingerprint = normalize_fingerprint(trusted_fingerprint)
    if not bundle_dir.is_dir() or not SAFE_NAME.fullmatch(bundle_dir.name):
        raise ToolFailure(
            "release-signature-bundle-invalid",
            "Bundle directory is missing or has an unsafe name.",
            bundle_dir,
        )
    assert_no_reparse_path(bundle_dir)
    if homedir is not None:
        homedir = absolute(homedir)
        if not homedir.is_dir():
            raise ToolFailure(
                "release-signature-homedir-invalid",
                "The selected GnuPG home directory does not exist.",
                homedir,
            )
        assert_no_reparse_path(homedir)
        for forbidden in (plugin_root, bundle_dir):
            try:
                homedir.relative_to(forbidden)
            except ValueError:
                continue
            raise ToolFailure(
                "release-signature-homedir-inside-release",
                (
                    "The GnuPG home must be supplied independently outside "
                    "the repository and release bundle."
                ),
                homedir,
            )
    gpg_path, gpg_sha256, gpg_bytes = externally_supplied_gpg(
        plugin_root,
        bundle_dir,
        gpg_executable,
    )
    record_path = bundle_dir / "release-package.json"
    record_bytes = stable_bytes(
        record_path,
        maximum_bytes=MAX_RECORD_BYTES,
    )
    record = strict_json(record_bytes, path=record_path)
    validate_schema(
        record,
        plugin_root / "maintainer" / "schemas" / "release-package.schema.json",
        code="release-signature-package-record-invalid",
    )
    if not isinstance(record, dict):
        raise ToolFailure(
            "release-signature-package-record-invalid",
            "release-package.json must be an object.",
            record_path,
        )
    archive_record = record.get("archive")
    checksum_record = record.get("checksum_file")
    if not isinstance(archive_record, dict) or not isinstance(
        checksum_record,
        dict,
    ):
        raise ToolFailure(
            "release-signature-package-record-invalid",
            "Package record lacks archive or checksum metadata.",
            record_path,
        )
    archive_name = archive_record.get("name")
    checksum_name = checksum_record.get("name")
    if (
        not isinstance(archive_name, str)
        or not ARCHIVE_NAME.fullmatch(archive_name)
        or not isinstance(checksum_name, str)
        or checksum_name != f"{archive_name}.sha256"
        or bundle_dir.name != archive_name[:-4]
    ):
        raise ToolFailure(
            "release-signature-package-binding-invalid",
            "Bundle, archive, and checksum names do not identify one release.",
            record_path,
        )
    expected_signatures = [
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
            "name": f"{checksum_name}.asc",
        },
    ]
    if (
        record.get("signature_policy") != "external-detached-required"
        or record.get("required_signatures") != expected_signatures
    ):
        raise ToolFailure(
            "release-signature-policy-binding-invalid",
            (
                "The signed descriptor must name the exact three detached "
                "signature files required for this bundle."
            ),
            record_path,
        )
    archive_path = bundle_dir / archive_name
    checksum_path = bundle_dir / checksum_name
    artifact_inputs = (
        ("release-package", record_path, MAX_RECORD_BYTES),
        ("archive", archive_path, MAX_ARCHIVE_BYTES),
        ("checksum", checksum_path, MAX_CHECKSUM_BYTES),
    )
    version = gpg_version(str(gpg_path), runner=runner)
    verifications: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(
        prefix="design-dna-signature-verify-"
    ) as temporary:
        staging = Path(temporary)
        staged_records: list[
            tuple[str, Path, Path, str, int, str, int]
        ] = []
        for role, artifact_path, limit in artifact_inputs:
            signature_path = bundle_dir / f"{artifact_path.name}.asc"
            if not signature_path.is_file():
                raise ToolFailure(
                    "release-signature-file-missing",
                    (
                        "Detached signatures over release-package.json, the "
                        "archive, and the checksum are all required."
                    ),
                    signature_path,
                )
            staged_artifact = staging / artifact_path.name
            staged_signature = staging / signature_path.name
            artifact_hash, artifact_bytes = stable_copy_and_digest(
                artifact_path,
                staged_artifact,
                maximum_bytes=limit,
            )
            signature_hash, signature_bytes = stable_copy_and_digest(
                signature_path,
                staged_signature,
                maximum_bytes=MAX_SIGNATURE_BYTES,
            )
            staged_records.append((
                role,
                artifact_path,
                signature_path,
                artifact_hash,
                artifact_bytes,
                signature_hash,
                signature_bytes,
            ))
            verification = verify_detached(
                str(gpg_path),
                staged_signature,
                staged_artifact,
                expected_fingerprint,
                homedir=homedir,
                runner=runner,
            )
            verifications.append({
                "role": role,
                "artifact": {
                    "name": artifact_path.name,
                    "sha256": artifact_hash,
                    "bytes": artifact_bytes,
                },
                "signature": {
                    "name": signature_path.name,
                    "sha256": signature_hash,
                    "bytes": signature_bytes,
                },
                "verification": verification,
            })
        for (
            role,
            artifact_path,
            signature_path,
            artifact_hash,
            artifact_bytes,
            signature_hash,
            signature_bytes,
        ) in staged_records:
            artifact_limit = {
                "release-package": MAX_RECORD_BYTES,
                "archive": MAX_ARCHIVE_BYTES,
                "checksum": MAX_CHECKSUM_BYTES,
            }[role]
            if stable_digest(
                artifact_path,
                maximum_bytes=artifact_limit,
            ) != (artifact_hash, artifact_bytes):
                raise ToolFailure(
                    "release-signature-input-unstable",
                    "Artifact changed during signature verification.",
                    artifact_path,
                )
            if stable_digest(
                signature_path,
                maximum_bytes=MAX_SIGNATURE_BYTES,
            ) != (signature_hash, signature_bytes):
                raise ToolFailure(
                    "release-signature-input-unstable",
                    "Detached signature changed during verification.",
                    signature_path,
                )
    if stable_digest(
        gpg_path,
        maximum_bytes=MAX_GPG_EXECUTABLE_BYTES,
    ) != (gpg_sha256, gpg_bytes):
        raise ToolFailure(
            "release-signature-gpg-unstable",
            "The verifier executable changed during verification.",
            gpg_path,
        )
    verification_by_role = {
        item["role"]: item
        for item in verifications
    }
    package_artifact = verification_by_role["release-package"]["artifact"]
    archive = verification_by_role["archive"]["artifact"]
    if (
        package_artifact["sha256"]
        != hashlib.sha256(record_bytes).hexdigest()
        or package_artifact["bytes"] != len(record_bytes)
    ):
        raise ToolFailure(
            "release-signature-package-record-unstable",
            (
                "release-package.json changed between metadata parsing and "
                "detached-signature verification."
            ),
            record_path,
        )
    checksum_bytes = stable_bytes(
        checksum_path,
        maximum_bytes=MAX_CHECKSUM_BYTES,
    )
    checksum_artifact = verification_by_role["checksum"]["artifact"]
    if (
        checksum_artifact["sha256"]
        != hashlib.sha256(checksum_bytes).hexdigest()
        or checksum_artifact["bytes"] != len(checksum_bytes)
    ):
        raise ToolFailure(
            "release-signature-checksum-unstable",
            "Checksum content changed after detached-signature verification.",
            checksum_path,
        )
    expected_checksum = (
        f"{archive['sha256']}  {archive_name}\n".encode("utf-8")
    )
    if checksum_bytes != expected_checksum:
        raise ToolFailure(
            "release-signature-checksum-mismatch",
            "Checksum file does not exactly bind the verified archive.",
            checksum_path,
        )
    if (
        archive_record.get("sha256") != archive["sha256"]
        or archive_record.get("bytes") != archive["bytes"]
    ):
        raise ToolFailure(
            "release-signature-package-binding-invalid",
            "Package record does not bind the exact verified archive.",
            record_path,
        )
    attestation = {
        "schema_version": 1,
        "record_type": "design-dna-release-signature-attestation",
        "created_at": utc_now(),
        "package": "design-dna",
        "version": record["version"],
        "ref": record["ref"],
        "commit": record["commit"],
        "release_identity_sha256": record["release_identity_sha256"],
        "bundle_name": bundle_dir.name,
        "release_package": {
            "name": record_path.name,
            "sha256": package_artifact["sha256"],
            "bytes": package_artifact["bytes"],
        },
        "trust_basis": {
            "kind": "operator-supplied-established-primary-fingerprint",
            "primary_fingerprint": expected_fingerprint,
            "fingerprint_source": "external-to-release-bundle",
        },
        "verifier": {
            "implementation": "GnuPG",
            "version": version,
            "executable": gpg_path.name,
            "executable_sha256": gpg_sha256,
            "executable_bytes": gpg_bytes,
            "path_source": (
                "operator-supplied-absolute-path-outside-release"
            ),
            "isolated_status_channel": True,
            "automatic_key_retrieval": False,
        },
        "artifacts": verifications,
        "outcome": {
            "verified": True,
            "archive_checksum_match": True,
            "detached_signatures_valid": True,
        },
    }
    validate_schema(
        attestation,
        plugin_root
        / "maintainer"
        / "schemas"
        / "release-signature-attestation.schema.json",
        code="release-signature-attestation-invalid",
    )
    return attestation


def comparable(payload: dict[str, object]) -> dict[str, object]:
    result = json.loads(json.dumps(payload))
    result.pop("created_at", None)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    plugin_default = Path(__file__).resolve().parents[2]
    parser.add_argument("--plugin-root", type=Path, default=plugin_default)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--trusted-fingerprint", required=True)
    parser.add_argument(
        "--gpg",
        required=True,
        help=(
            "Absolute path to an independently installed GnuPG executable "
            "outside the release tree."
        ),
    )
    parser.add_argument("--gpg-homedir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        bundle_dir = absolute(args.bundle_dir)
        output = absolute(
            args.output
            if args.output is not None
            else bundle_dir / "release-signature-attestation.json"
        )
        if (
            output.parent != bundle_dir
            or output.name != "release-signature-attestation.json"
        ):
            raise ToolFailure(
                "release-signature-output-unsafe",
                "Attestation output must use its exact name inside the bundle.",
                output,
            )
        live = create_attestation(
            args.plugin_root,
            bundle_dir,
            args.trusted_fingerprint,
            gpg_executable=args.gpg,
            homedir=args.gpg_homedir,
        )
        if args.check:
            if not output.is_file():
                raise ToolFailure(
                    "release-signature-attestation-missing",
                    "The detached-signature attestation does not exist.",
                    output,
                )
            recorded = load_json(output)
            validate_schema(
                recorded,
                absolute(args.plugin_root)
                / "maintainer"
                / "schemas"
                / "release-signature-attestation.schema.json",
                code="release-signature-attestation-invalid",
            )
            if not isinstance(recorded, dict) or comparable(recorded) != comparable(live):
                raise ToolFailure(
                    "release-signature-attestation-drift",
                    "Recorded signature evidence differs from live verification.",
                    output,
                )
        else:
            if output.exists():
                raise ToolFailure(
                    "release-signature-attestation-exists",
                    "Attestations are immutable; use --check or a new bundle.",
                    output,
                )
            atomic_write_json(output, live)
        emit({
            "ok": True,
            "check": args.check,
            "attestation": str(output),
            "bundle": str(bundle_dir),
            "trusted_primary_fingerprint": normalize_fingerprint(
                args.trusted_fingerprint
            ),
            "verified_artifacts": [
                "release-package",
                "archive",
                "checksum",
            ],
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
                "code": "release-signature-unexpected-error",
                "message": str(exc),
                "severity": "error",
            }
        )
        emit({"ok": False, "failures": [failure]})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
