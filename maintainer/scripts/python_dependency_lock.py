#!/usr/bin/env python3
"""Validate retained PyPI metadata and reproduce the single-pin Python lock.

This command is offline. The metadata records primary PyPI release responses
and their artifact hashes; it is publisher-retained evidence, not a signature.
It never resolves to newer packages or adds interpreter-conditional pins.
"""
from __future__ import annotations

_CACHE_PREFLIGHT_PATH = (
    __file__.replace("\\", "/").rsplit("/", 1)[0] + "/cache_preflight.py"
)
with open(_CACHE_PREFLIGHT_PATH, "rb") as _cache_preflight_stream:
    _CACHE_PREFLIGHT_SOURCE = _cache_preflight_stream.read()
exec(compile(_CACHE_PREFLIGHT_SOURCE, _CACHE_PREFLIGHT_PATH, "exec"),
     {"__file__": _CACHE_PREFLIGHT_PATH, "__name__": "_design_dna_cache_preflight"})
del _CACHE_PREFLIGHT_PATH, _CACHE_PREFLIGHT_SOURCE, _cache_preflight_stream

import argparse
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import InvalidSdistFilename, InvalidWheelFilename, parse_sdist_filename, parse_wheel_filename
from packaging.version import InvalidVersion, Version

from common import assert_no_reparse_path


PYTHON_FLOOR = "3.10"
SUPPORTED_PYTHON_MINORS = ("3.10", "3.11", "3.12", "3.13", "3.14")
PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9][A-Za-z0-9_.+!-]*)")
SHA256 = re.compile(r"[0-9a-f]{64}")


def normalized_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def parse_pins(text: str) -> dict[str, str]:
    pins: dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN.fullmatch(line)
        if match is None:
            raise ValueError(f"requirements line {number} must be one unconditional exact pin")
        name, version = normalized_name(match[1]), match[2]
        Version(version)
        if name in pins:
            raise ValueError(f"duplicate Python pin: {name}")
        pins[name] = version
    if not pins:
        raise ValueError("the dependency closure is empty")
    return pins


def marker_environments(version: str):
    for os_name, system, machine, sys_platform in (
        ("nt", "Windows", "AMD64", "win32"),
        ("posix", "Linux", "x86_64", "linux"),
        ("posix", "Darwin", "x86_64", "darwin"),
        ("posix", "Darwin", "arm64", "darwin"),
    ):
        yield {"implementation_name": "cpython", "implementation_version": version + ".0",
               "os_name": os_name, "platform_machine": machine, "platform_release": "",
               "platform_system": system, "platform_version": "", "python_full_version": version + ".0",
               "platform_python_implementation": "CPython", "python_version": version,
               "sys_platform": sys_platform, "extra": ""}


def validate_metadata(pins: dict[str, str], payload: object) -> list[str]:
    issues: list[str] = []
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version", "python_floor", "supported_python_minors", "retrieved_at", "authority", "packages"
    }:
        return ["Python release metadata has an unsupported shape"]
    if payload["schema_version"] != 1 or payload["python_floor"] != PYTHON_FLOOR or payload["supported_python_minors"] != list(SUPPORTED_PYTHON_MINORS):
        issues.append("Python release metadata must retain the declared 3.10 floor and supported interpreter matrix")
    try:
        stamp = datetime.fromisoformat(str(payload["retrieved_at"]).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("missing timezone")
    except ValueError:
        issues.append("Python release metadata needs a timezone-aware retrieval date")
    if not isinstance(payload["packages"], list):
        return issues + ["Python release metadata packages must be a list"]
    seen: set[str] = set()
    for package in payload["packages"]:
        if not isinstance(package, dict) or set(package) != {
            "name", "version", "source_url", "source_response_sha256", "requires_python", "requires_dist", "artifacts"
        }:
            issues.append("a Python package metadata record has an unsupported shape")
            continue
        if not isinstance(package["name"], str) or not isinstance(package["version"], str):
            issues.append("Python metadata name/version must be strings")
            continue
        name, version = normalized_name(package["name"]), package["version"]
        if name in seen or pins.get(name) != version:
            issues.append(f"{name} metadata is duplicate or differs from the exact pin")
        seen.add(name)
        expected_url = f"https://pypi.org/pypi/{package['name']}/{version}/json"
        if package["source_url"] != expected_url or not isinstance(package["source_response_sha256"], str) or SHA256.fullmatch(package["source_response_sha256"]) is None:
            issues.append(f"{name} lacks its exact primary PyPI response identity")
        try:
            if not isinstance(package["requires_python"], str) or not package["requires_python"].strip():
                raise InvalidSpecifier("missing Requires-Python")
            requires_python = SpecifierSet(package["requires_python"])
            for python in SUPPORTED_PYTHON_MINORS:
                if Version(python + ".0") not in requires_python:
                    issues.append(f"{name}=={version} Requires-Python {requires_python} excludes supported Python {python}")
        except InvalidSpecifier as error:
            issues.append(f"{name} has invalid Requires-Python: {error}")
        requirements = package["requires_dist"]
        if not isinstance(requirements, list) or any(not isinstance(item, str) for item in requirements):
            issues.append(f"{name} has invalid Requires-Dist metadata")
        else:
            for text in requirements:
                try:
                    required = Requirement(text)
                    dependency = normalized_name(required.name)
                    for python in SUPPORTED_PYTHON_MINORS:
                        if not any(required.marker is None or required.marker.evaluate(environment) for environment in marker_environments(python)):
                            continue
                        if required.url or required.extras or dependency not in pins or Version(pins[dependency]) not in required.specifier:
                            issues.append(f"{name}=={version} needs {text!r} on Python {python}; the pinned closure does not satisfy it")
                except (InvalidRequirement, InvalidVersion) as error:
                    issues.append(f"{name} has invalid dependency metadata: {error}")
        artifacts = package["artifacts"]
        if not isinstance(artifacts, list) or not artifacts:
            issues.append(f"{name} has no retained release artifacts")
            continue
        filenames: set[str] = set()
        for artifact in artifacts:
            if not isinstance(artifact, dict) or set(artifact) != {
                "filename", "url", "sha256", "requires_python", "yanked", "size", "packagetype", "python_version"
            }:
                issues.append(f"{name} has an invalid artifact record")
                continue
            filename = artifact["filename"]
            if not isinstance(filename, str) or not filename or filename in filenames:
                issues.append(f"{name} has an invalid/duplicate artifact filename")
                continue
            filenames.add(filename)
            try:
                distribution_name, distribution_version = (
                    parse_wheel_filename(filename)[:2] if artifact["packagetype"] == "bdist_wheel"
                    else parse_sdist_filename(filename)
                )
                if normalized_name(distribution_name) != name or distribution_version != Version(version):
                    issues.append(f"{name} artifact {filename} belongs to a different exact distribution")
            except (InvalidSdistFilename, InvalidWheelFilename, InvalidVersion):
                issues.append(f"{name} artifact {filename} has an invalid distribution filename")
            source = urlsplit(artifact["url"]) if isinstance(artifact["url"], str) else None
            if (source is None or source.scheme != "https" or source.netloc != "files.pythonhosted.org"
                or not source.path.startswith("/packages/") or unquote(source.path.rsplit("/", 1)[-1]) != filename
                or not isinstance(artifact["sha256"], str) or SHA256.fullmatch(artifact["sha256"]) is None
                or artifact["yanked"] is not False or type(artifact["size"]) is not int or artifact["size"] <= 0
                or artifact["packagetype"] not in {"sdist", "bdist_wheel"}):
                issues.append(f"{name} artifact {filename} has invalid, yanked, or untrusted release metadata")
            if artifact["requires_python"] is not None:
                try:
                    SpecifierSet(artifact["requires_python"])
                except (InvalidSpecifier, TypeError):
                    issues.append(f"{name} artifact {filename} has invalid Requires-Python")
    if seen != set(pins):
        issues.append("retained PyPI metadata and requirements must contain the same complete pin set")
    return sorted(set(issues))


def render_lock(pins: dict[str, str], metadata: dict) -> str:
    issues = validate_metadata(pins, metadata)
    if issues:
        raise ValueError("; ".join(issues))
    packages = {normalized_name(package["name"]): package for package in metadata["packages"]}
    lines: list[str] = []
    for name, version in sorted(pins.items()):
        hashes = sorted({artifact["sha256"] for artifact in packages[name]["artifacts"]})
        lines.append(f"{name}=={version} \\")
        lines.extend(f"    --hash=sha256:{digest}" + (" \\" if index < len(hashes) - 1 else "") for index, digest in enumerate(hashes))
    return "\n".join(lines) + "\n"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", type=Path, default=root / "requirements-dev.txt")
    parser.add_argument("--metadata", type=Path, default=root / "dependencies/python-release-metadata.json")
    parser.add_argument("--lock", type=Path, default=root / "requirements-dev.lock")
    parser.add_argument("--write", action="store_true", help="Atomically regenerate the hash lock from validated retained metadata")
    args = parser.parse_args()
    for file in (args.requirements, args.metadata, args.lock):
        assert_no_reparse_path(file)
    try:
        pins = parse_pins(args.requirements.read_text(encoding="utf-8"))
        metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
        generated = render_lock(pins, metadata)
        if args.write:
            descriptor, temporary = tempfile.mkstemp(prefix=".python-lock-", dir=args.lock.parent)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
                    output.write(generated)
                os.replace(temporary, args.lock)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        elif args.lock.read_text(encoding="utf-8").replace("\r\n", "\n") != generated:
            raise ValueError("hash lock differs from the complete exact artifact set in retained PyPI metadata")
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return 1
    print(json.dumps({"ok": True, "python_floor": PYTHON_FLOOR, "supported_python_minors": SUPPORTED_PYTHON_MINORS,
                      "packages": len(pins), "network_used": False, "written": args.write}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
