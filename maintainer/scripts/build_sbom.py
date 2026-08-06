#!/usr/bin/env python3
"""Generate or verify the deterministic SPDX 2.3 package inventory."""

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
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from jsonschema import Draft202012Validator

from common import (
    ToolFailure,
    absolute,
    assert_no_reparse_path,
    content_manifest,
    emit,
    is_within,
    load_json,
    strict_format_checker,
)


PIN = re.compile(
    r"(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)=="
    r"(?P<version>[A-Za-z0-9][A-Za-z0-9_.+!-]*)"
)
SPDX_ID_SAFE = re.compile(r"[^A-Za-z0-9.-]+")
SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-(?:(?:0|[1-9][0-9]*)|(?:[0-9]*[A-Za-z-][0-9A-Za-z-]*))"
    r"(?:\.(?:(?:0|[1-9][0-9]*)|(?:[0-9]*[A-Za-z-]"
    r"[0-9A-Za-z-]*)))*)?(?:\+[0-9A-Za-z-]+"
    r"(?:\.[0-9A-Za-z-]+)*)?$"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def file_sha256(path: Path) -> str:
    assert_no_reparse_path(path)
    try:
        before = path.read_bytes()
        after = path.read_bytes()
    except OSError as exc:
        raise ToolFailure("sbom-input-unreadable", str(exc), path) from exc
    if before != after:
        raise ToolFailure(
            "sbom-input-unstable",
            "Input changed while it was read.",
            path,
        )
    return hashlib.sha256(before).hexdigest()


def normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).casefold()


def spdx_id(ecosystem: str, name: str, version: str) -> str:
    stem = SPDX_ID_SAFE.sub("-", f"{ecosystem}-{name}-{version}").strip("-.")
    suffix = hashlib.sha256(
        f"{ecosystem}\0{name}\0{version}".encode("utf-8")
    ).hexdigest()[:12]
    return f"SPDXRef-Package-{stem[:120]}-{suffix}"


def python_lock_hashes(
    lock_path: Path,
) -> dict[tuple[str, str], list[str]]:
    assert_no_reparse_path(lock_path)
    try:
        first = lock_path.read_text(encoding="utf-8")
        second = lock_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ToolFailure("sbom-python-lock-unreadable", str(exc), lock_path) from exc
    if first != second:
        raise ToolFailure(
            "sbom-input-unstable",
            "requirements-dev.lock changed while it was read.",
            lock_path,
        )
    logical = first.replace("\\\r\n", " ").replace("\\\n", " ")
    records: dict[tuple[str, str], list[str]] = {}
    for number, raw in enumerate(logical.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        pin = PIN.match(line)
        if pin is None:
            raise ToolFailure(
                "sbom-python-lock-invalid",
                f"Logical line {number} does not start with an exact pin.",
                lock_path,
            )
        hashes = re.findall(r"--hash=sha256:([0-9a-f]{64})(?:\s|$)", line)
        remainder = PIN.sub("", line, count=1)
        remainder = re.sub(
            r"\s*--hash=sha256:[0-9a-f]{64}",
            "",
            remainder,
        ).strip()
        if not hashes or remainder:
            raise ToolFailure(
                "sbom-python-lock-invalid",
                (
                    f"Logical line {number} must contain only one exact pin "
                    "and one or more SHA-256 artifact hashes."
                ),
                lock_path,
            )
        key = (
            normalized_name(pin.group("name")),
            pin.group("version"),
        )
        if key in records:
            raise ToolFailure(
                "sbom-python-lock-duplicate",
                f"Duplicate locked Python dependency: {key[0]}=={key[1]}.",
                lock_path,
            )
        records[key] = sorted(set(hashes))
    if not records:
        raise ToolFailure(
            "sbom-python-lock-empty",
            "The Python artifact lock must contain at least one dependency.",
            lock_path,
        )
    return records


def python_dependencies(
    requirements_path: Path,
    lock_path: Path,
) -> list[dict[str, object]]:
    assert_no_reparse_path(requirements_path)
    try:
        first = requirements_path.read_text(encoding="utf-8")
        second = requirements_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ToolFailure("sbom-requirements-unreadable", str(exc), requirements_path) from exc
    if first != second:
        raise ToolFailure(
            "sbom-input-unstable",
            "requirements-dev.txt changed while it was read.",
            requirements_path,
        )
    locked = python_lock_hashes(lock_path)
    dependencies: dict[tuple[str, str], dict[str, object]] = {}
    for number, raw in enumerate(first.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN.fullmatch(line)
        if not match:
            raise ToolFailure(
                "sbom-requirement-not-pinned",
                f"Line {number} is not an exact name==version pin.",
                requirements_path,
            )
        name = normalized_name(match.group("name"))
        version = match.group("version")
        key = (name, version)
        if key in dependencies:
            raise ToolFailure(
                "sbom-dependency-duplicate",
                f"Duplicate Python dependency: {name}=={version}.",
                requirements_path,
            )
        dependencies[key] = {
            "ecosystem": "pypi",
            "name": name,
            "version": version,
            "purl": f"pkg:pypi/{quote(name, safe='')}@{quote(version, safe='')}",
            "sha256": locked.get(key, []),
        }
    if not dependencies:
        raise ToolFailure(
            "sbom-requirements-empty",
            "At least one pinned maintainer dependency is required.",
            requirements_path,
        )
    if set(dependencies) != set(locked):
        raise ToolFailure(
            "sbom-python-lock-pin-mismatch",
            (
                "requirements-dev.txt and requirements-dev.lock must contain "
                "the same normalized name/version pins."
            ),
            lock_path,
        )
    return [dependencies[key] for key in sorted(dependencies)]


def npm_dependencies(lock_path: Path) -> list[dict[str, str]]:
    if not lock_path.exists():
        return []
    assert_no_reparse_path(lock_path)
    payload = load_json(lock_path)
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("lockfileVersion"), int)
        or not isinstance(payload.get("packages"), dict)
    ):
        raise ToolFailure(
            "sbom-package-lock-invalid",
            "package-lock.json must expose lockfileVersion and packages.",
            lock_path,
        )
    dependencies: dict[tuple[str, str], dict[str, str]] = {}
    for package_path, record in payload["packages"].items():
        if not package_path or not isinstance(record, dict):
            continue
        marker = "node_modules/"
        if marker not in str(package_path):
            continue
        name = str(package_path).rsplit(marker, 1)[-1]
        version = record.get("version")
        if (
            not name
            or not isinstance(version, str)
            or not version
            or any(character.isspace() for character in name + version)
        ):
            raise ToolFailure(
                "sbom-package-lock-entry-invalid",
                f"Invalid locked package entry: {package_path!r}.",
                lock_path,
            )
        key = (name.casefold(), version)
        dependencies[key] = {
            "ecosystem": "npm",
            "name": name,
            "version": version,
            "purl": f"pkg:npm/{quote(name, safe='@/')}@{quote(version, safe='')}",
        }
    return [dependencies[key] for key in sorted(dependencies)]


def package_record(
    dependency: dict[str, object],
) -> dict[str, object]:
    identifier = spdx_id(
        str(dependency["ecosystem"]),
        str(dependency["name"]),
        str(dependency["version"]),
    )
    record: dict[str, object] = {
        "SPDXID": identifier,
        "name": str(dependency["name"]),
        "versionInfo": str(dependency["version"]),
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "NOASSERTION",
        "copyrightText": "NOASSERTION",
        "externalRefs": [
            {
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": str(dependency["purl"]),
            }
        ],
        "primaryPackagePurpose": "LIBRARY",
        "supplier": "NOASSERTION",
    }
    checksums = dependency.get("sha256")
    if isinstance(checksums, list) and checksums:
        record["checksums"] = [
            {"algorithm": "SHA256", "checksumValue": str(value)}
            for value in checksums
        ]
    return record


def generate_sbom(
    plugin_root: Path,
    *,
    created_at: str,
) -> dict[str, object]:
    plugin_root = absolute(plugin_root)
    assert_no_reparse_path(plugin_root)
    skill_root = plugin_root / "skills" / "design-dna"
    runtime_files, runtime_hash = content_manifest(skill_root)
    del runtime_files
    release = load_json(skill_root / "release.json")
    codex_manifest = load_json(plugin_root / ".codex-plugin" / "plugin.json")
    claude_manifest = load_json(plugin_root / ".claude-plugin" / "plugin.json")
    if (
        not isinstance(release, dict)
        or not isinstance(codex_manifest, dict)
        or not isinstance(claude_manifest, dict)
    ):
        raise ToolFailure(
            "sbom-release-metadata-invalid",
            "Release and host plugin manifests must be JSON objects.",
            plugin_root,
        )
    version = release.get("version")
    if (
        not isinstance(version, str)
        or not SEMVER.fullmatch(version)
        or codex_manifest.get("version") != version
        or claude_manifest.get("version") != version
    ):
        raise ToolFailure(
            "sbom-version-mismatch",
            "Runtime and both host plugin versions must be one exact SemVer.",
            plugin_root,
        )
    author = codex_manifest.get("author")
    author_name = author.get("name") if isinstance(author, dict) else None
    if not isinstance(author_name, str) or not author_name.strip():
        raise ToolFailure(
            "sbom-author-missing",
            "Codex plugin metadata must identify the package author.",
            plugin_root / ".codex-plugin" / "plugin.json",
        )
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    if created.tzinfo is None or created.utcoffset() is None:
        raise ToolFailure(
            "sbom-created-at-invalid",
            "created_at must include a UTC offset.",
        )
    created_at = created.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    requirements = plugin_root / "maintainer" / "requirements-dev.txt"
    requirements_lock = plugin_root / "maintainer" / "requirements-dev.lock"
    lock_path = plugin_root / "maintainer" / "package-lock.json"
    dependencies = [
        *python_dependencies(requirements, requirements_lock),
        *npm_dependencies(lock_path),
    ]
    dependency_packages = [package_record(item) for item in dependencies]
    root_id = "SPDXRef-Package-design-dna"
    namespace_uuid = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"design-dna:{version}:{runtime_hash}",
    )
    license_text = (
        plugin_root / "LICENSE"
    ).read_text(encoding="utf-8")
    root_package = {
        "SPDXID": root_id,
        "name": "design-dna",
        "versionInfo": version,
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": "LicenseRef-DesignDNA-Proprietary",
        "licenseDeclared": "LicenseRef-DesignDNA-Proprietary",
        "copyrightText": f"Copyright (c) 2026 {author_name}. All rights reserved.",
        "primaryPackagePurpose": "LIBRARY",
        "supplier": f"Person: {author_name}",
        "sourceInfo": (
            "Runtime tree canonical content SHA-256: "
            f"{runtime_hash}. Maintainer dependencies are inventory only and "
            "are not bundled in the runtime skill. Python artifacts are "
            "SHA-256 locked; npm artifacts are integrity-locked by package-lock.json."
        ),
        "externalRefs": [
            {
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": (
                    f"pkg:generic/design-dna@{quote(version, safe='')}"
                ),
            }
        ],
    }
    relationships = [
        {
            "spdxElementId": root_id,
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": package["SPDXID"],
        }
        for package in dependency_packages
    ]
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"design-dna-{version}-{runtime_hash[:12]}",
        "documentNamespace": f"urn:uuid:{namespace_uuid}",
        "creationInfo": {
            "created": created_at,
            "creators": [
                "Tool: design-dna-build-sbom-1.0.0",
                f"Person: {author_name}",
            ],
            "licenseListVersion": "3.27",
        },
        "documentDescribes": [root_id],
        "packages": [root_package, *dependency_packages],
        "relationships": relationships,
        "hasExtractedLicensingInfos": [
            {
                "licenseId": "LicenseRef-DesignDNA-Proprietary",
                "extractedText": license_text,
                "name": "Design DNA Proprietary Rights Notice",
            }
        ],
    }


def validate_sbom(
    payload: object,
    plugin_root: Path,
) -> None:
    schema_path = plugin_root / "maintainer" / "schemas" / "sbom.schema.json"
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
            "sbom-schema-invalid",
            "; ".join(
                f"{'/'.join(map(str, error.path)) or '<root>'}: "
                f"{error.message}"
                for error in errors
            ),
            schema_path,
        )
    if not isinstance(payload, dict):
        raise ToolFailure("sbom-invalid", "SBOM must be an object.", schema_path)
    packages = payload.get("packages")
    relationships = payload.get("relationships")
    if not isinstance(packages, list) or not isinstance(relationships, list):
        raise ToolFailure("sbom-invalid", "SBOM package inventory is incomplete.", schema_path)
    package_ids = [
        package.get("SPDXID")
        for package in packages
        if isinstance(package, dict)
    ]
    if len(package_ids) != len(set(package_ids)):
        raise ToolFailure("sbom-package-id-duplicate", "SPDX package IDs must be unique.", schema_path)
    expected_related = set(package_ids) - {"SPDXRef-Package-design-dna"}
    observed_related = {
        relationship.get("relatedSpdxElement")
        for relationship in relationships
        if isinstance(relationship, dict)
        and relationship.get("spdxElementId") == "SPDXRef-Package-design-dna"
        and relationship.get("relationshipType") == "DEPENDS_ON"
    }
    if observed_related != expected_related:
        raise ToolFailure(
            "sbom-relationship-coverage",
            "The root package must depend on every inventoried maintainer package exactly once.",
            schema_path,
        )


def atomic_write(path: Path, payload: object) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_plugin = Path(__file__).resolve().parents[2]
    parser.add_argument("--plugin-root", type=Path, default=default_plugin)
    parser.add_argument(
        "--output",
        type=Path,
        default=default_plugin / "maintainer" / "sbom.spdx.json",
    )
    parser.add_argument("--created-at")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        plugin_root = absolute(args.plugin_root)
        output = absolute(args.output)
        assert_no_reparse_path(plugin_root)
        if not plugin_root.is_dir():
            raise ToolFailure("sbom-plugin-root-missing", "Plugin root is missing.", plugin_root)
        if not is_within(output, plugin_root):
            raise ToolFailure(
                "sbom-output-outside-package",
                "The canonical SBOM must remain inside the package.",
                output,
            )
        protected = (
            plugin_root / "skills",
            plugin_root / "maintainer" / "scripts",
            plugin_root / "maintainer" / "schemas",
            plugin_root / "maintainer" / "tests",
        )
        if any(output == path or is_within(output, path) for path in protected):
            raise ToolFailure(
                "sbom-output-overlaps-input",
                "SBOM output cannot overlap runtime, tooling, schemas, or tests.",
                output,
            )
        if not output.parent.is_dir():
            raise ToolFailure(
                "sbom-output-parent-missing",
                "Create the exact output parent first.",
                output.parent,
            )
        assert_no_reparse_path(output.parent, stop=plugin_root)
        existing: object | None = None
        if args.check:
            if not output.is_file():
                raise ToolFailure("sbom-missing", "Generate the SBOM before checking it.", output)
            existing = load_json(output)
            validate_sbom(existing, plugin_root)
            creation_info = (
                existing.get("creationInfo")
                if isinstance(existing, dict)
                else None
            )
            created_at = (
                creation_info.get("created")
                if isinstance(creation_info, dict)
                else None
            )
            if not isinstance(created_at, str):
                raise ToolFailure("sbom-created-at-invalid", "Existing SBOM has no created time.", output)
        else:
            created_at = args.created_at or utc_now()
        generated = generate_sbom(plugin_root, created_at=created_at)
        validate_sbom(generated, plugin_root)
        if args.check:
            if existing != generated:
                raise ToolFailure(
                    "sbom-drift",
                    "SBOM differs from current package inputs.",
                    output,
                )
        else:
            atomic_write(output, generated)
        emit({
            "ok": True,
            "output": str(output),
            "check": args.check,
            "sha256": (
                file_sha256(output)
                if output.is_file()
                else hashlib.sha256(
                    (json.dumps(generated, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
                ).hexdigest()
            ),
            "packages": len(generated["packages"]),
        })
        return 0
    except (ToolFailure, OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, ToolFailure):
            failure = exc.issue.as_dict()
        else:
            failure = {
                "code": "sbom-unexpected-error",
                "message": str(exc),
            }
        emit({"ok": False, "failures": [failure]})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
