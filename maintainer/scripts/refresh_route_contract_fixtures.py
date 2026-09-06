#!/usr/bin/env python3
"""Refresh only four explicitly synthetic .invalid route-contract fixture pins.

This does not observe a website or create source-study, recording, browser,
controller, review, or release evidence. Real public observations are refused.
"""
from __future__ import annotations

_CACHE_PREFLIGHT_PATH = __file__.replace("\\", "/").rsplit("/", 1)[0] + "/cache_preflight.py"
with open(_CACHE_PREFLIGHT_PATH, "rb") as _cache_preflight_stream:
    _CACHE_PREFLIGHT_SOURCE = _cache_preflight_stream.read()
exec(compile(_CACHE_PREFLIGHT_SOURCE, _CACHE_PREFLIGHT_PATH, "exec"), {
    "__file__": _CACHE_PREFLIGHT_PATH, "__name__": "_design_dna_cache_preflight",
})
del _CACHE_PREFLIGHT_PATH, _CACHE_PREFLIGHT_SOURCE, _cache_preflight_stream

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from common import ToolFailure, absolute, assert_no_reparse_path, walk_entries


FIXTURE_NAMES = (
    "route-family-anthology-positive", "route-family-broken-orphan-negative",
    "route-family-recolor-negative", "route-family-safe-paths-positive",
)
INPUTS = Path("maintainer/evals/fixtures/inputs")
OBSERVATION = ".design-dna/references/strong-1-observation.json"
DEPENDENCIES = (
    "observe_reference.mjs", "structure_probe.mjs", "browser_evidence.mjs",
    "playwright_resolver.mjs", "source_surface_watch.mjs", "source_study_controller.mjs",
)
SYNTHETIC_SCOPE = {
    "kind": "synthetic-route-contract-unit-fixture",
    "generated_observation": False,
    "eligible_for_source_selection": False,
    "browser_or_recording_evidence": False,
    "purpose": "Minimal route-contract parser and source-hash regression input; never public-reference qualification.",
}
LEGACY_KEYS = {"tool", "schema_version", "producer_script_sha256", "runtime_identity", "id", "url", "states_by_viewport"}


def encoded(payload):
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_ordinary(path, root):
    assert_no_reparse_path(path, stop=root)
    if not path.is_file() or path.stat().st_nlink != 1:
        raise ToolFailure("fixture-file-unsafe", "Fixture inputs must be independent ordinary files.", path)
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_nlink) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_nlink):
        raise ToolFailure("fixture-input-drift", "Input changed while being read.", path)
    return data


def parse(data, path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        payload = json.loads(data.decode("utf-8"), object_pairs_hook=unique)
    except (ValueError, UnicodeError) as exc:
        raise ToolFailure("fixture-json-invalid", str(exc), path) from exc
    if not isinstance(payload, dict):
        raise ToolFailure("fixture-json-invalid", "Expected a fixture object.", path)
    return payload


def validate_observation(payload, path):
    keys = set(payload)
    if (keys not in (LEGACY_KEYS, LEGACY_KEYS | {"source_kind", "fixture_scope"})
        or payload.get("tool") != "observe_reference.mjs" or payload.get("schema_version") != 5
        or payload.get("id") != "strong-1" or payload.get("url") != "https://fixture-reference.invalid/"
        or payload.get("states_by_viewport") != {profile: {"rest": {"id": "rest"}} for profile in ("wide", "narrow")}
        or not isinstance(payload.get("runtime_identity"), dict)
        or set(payload["runtime_identity"]) not in (set(DEPENDENCIES[:4]), set(DEPENDENCIES))):
        raise ToolFailure("fixture-scope-refused", "Only the exact minimal .invalid route-contract stubs are refreshable; real or expanded observation evidence is never rewritten.", path)
    if keys != LEGACY_KEYS and (payload.get("source_kind") != "synthetic-contract-fixture" or payload.get("fixture_scope") != SYNTHETIC_SCOPE):
        raise ToolFailure("fixture-scope-refused", "The fixture must remain explicitly synthetic and nonpublic.", path)
    pins = [payload.get("producer_script_sha256"), *payload["runtime_identity"].values()]
    if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in pins):
        raise ToolFailure("fixture-pin-invalid", "Existing fixture code pins must be SHA-256 digests.", path)


def refresh_plan(plugin_root):
    """Read and validate every target before producing any writable plan."""
    root = absolute(plugin_root)
    assert_no_reparse_path(root)
    package = root / ".codex-plugin/plugin.json"
    if parse(read_ordinary(package, root), package).get("name") != "design-dna":
        raise ToolFailure("fixture-package-refused", "The explicit root must be the Design DNA package.", root)
    input_root = root / INPUTS
    expected_observations = {input_root / name / OBSERVATION for name in FIXTURE_NAMES}
    discovered = {file for file in walk_entries(input_root) if file.is_file() and file.name.endswith("-observation.json")}
    if discovered != expected_observations:
        raise ToolFailure("fixture-tree-refused", "The route-contract updater requires exactly its four explicit observation paths; an unknown/missing observation requires separate review.", input_root)
    runtime_inputs = {}
    runtime_identity = {}
    for name in DEPENDENCIES:
        path = root / "skills/design-dna/scripts" / name
        runtime_inputs[path] = read_ordinary(path, root)
        runtime_identity[name] = digest(runtime_inputs[path])
    replacements = []
    for name in FIXTURE_NAMES:
        fixture = input_root / name
        observation = fixture / OBSERVATION
        original = read_ordinary(observation, root)
        payload = parse(original, observation)
        validate_observation(payload, observation)
        refreshed = deepcopy(payload)
        refreshed.update(source_kind="synthetic-contract-fixture", fixture_scope=deepcopy(SYNTHETIC_SCOPE),
            producer_script_sha256=runtime_identity["observe_reference.mjs"], runtime_identity=deepcopy(runtime_identity))
        new_observation = encoded(refreshed)
        new_hash = digest(new_observation)
        replacements.append((observation, original, new_observation))
        manifest_path = fixture / ".design-dna/route-manifest.json"
        manifest_bytes = read_ordinary(manifest_path, root)
        manifest = parse(manifest_bytes, manifest_path)
        routes = manifest.get("routes")
        if manifest.get("schema_version") != 2 or not isinstance(routes, list) or not routes:
            raise ToolFailure("fixture-route-contract-invalid", "The scoped route manifest is invalid.", manifest_path)
        # These known synthetic stubs may already have stale dependent hashes.
        # Reconcile their one coherent prior binding; do not guess among
        # conflicting consumers or repair deliberately corrupted negatives.
        old_hash = routes[0].get("mapped_reference_sha256") if isinstance(routes[0], dict) else None
        if not isinstance(old_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", old_hash) or len(set(old_hash)) == 1:
            raise ToolFailure("fixture-route-contract-invalid", "The prior synthetic reference hash must be a real SHA-256-shaped fixture binding.", manifest_path)
        for route in routes:
            if (not isinstance(route, dict) or route.get("mapped_reference_observation") != OBSERVATION
                or route.get("mapped_reference_id") != "strong-1" or route.get("mapped_reference_rank") != 1
                or route.get("mapped_reference_sha256") != old_hash
                or not isinstance(route.get("url"), str) or not route["url"].startswith("http://127.0.0.1:4173/")):
                raise ToolFailure("fixture-route-contract-invalid", "A manifest must retain its exact local fixture URL and original synthetic source binding.", manifest_path)
            route["mapped_reference_sha256"] = new_hash
        replacements.append((manifest_path, manifest_bytes, encoded(manifest)))
        family_path = fixture / ".design-dna/route-family.json"
        family_bytes = read_ordinary(family_path, root)
        family = parse(family_bytes, family_path)
        family_routes = family.get("routes")
        if family.get("schema_version") != 3 or not isinstance(family_routes, list) or not family_routes:
            raise ToolFailure("fixture-route-contract-invalid", "The scoped route-family record is invalid.", family_path)
        for route in family_routes:
            mapping = route.get("source_mapping") if isinstance(route, dict) else None
            if (not isinstance(mapping, dict) or mapping.get("observation") != OBSERVATION
                or mapping.get("id") != "strong-1" or mapping.get("rank") != 1 or mapping.get("sha256") != old_hash):
                raise ToolFailure("fixture-route-contract-invalid", "Route-family mapping is not the exact original synthetic source binding.", family_path)
            mapping["sha256"] = new_hash
            for field in ("observable_decisions", "component_sources"):
                if not isinstance(route.get(field), list) or not route[field]:
                    raise ToolFailure("fixture-route-contract-invalid", "Route-family source consumers are missing.", family_path)
                for consumer in route[field]:
                    if (not isinstance(consumer, dict) or consumer.get("source_observation") != OBSERVATION
                        or consumer.get("source_id") != "strong-1" or consumer.get("source_rank") != 1
                        or consumer.get("source_sha256") != old_hash):
                        raise ToolFailure("fixture-route-contract-invalid", "A source consumer is not bound to the exact original synthetic fixture.", family_path)
                    consumer["source_sha256"] = new_hash
        replacements.append((family_path, family_bytes, encoded(family)))
    return root, runtime_inputs, replacements


def _stage(path, data):
    descriptor, temporary = tempfile.mkstemp(prefix=".route-contract-refresh-", suffix=".tmp", dir=path.parent)
    file = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        file.unlink(missing_ok=True)
        raise
    return file


def refresh(plugin_root, *, write=False):
    root, runtime_inputs, replacements = refresh_plan(plugin_root)
    changes = [row for row in replacements if row[1] != row[2]]
    if write and changes:
        for path, original in [*runtime_inputs.items(), *((path, old) for path, old, _new in replacements)]:
            if read_ordinary(path, root) != original:
                raise ToolFailure("fixture-input-drift", "An input changed before the transaction; nothing was written.", path)
        staged = []
        committed = []
        try:
            for path, old, new in changes:
                staged.append((path, old, new, _stage(path, new)))
            for path, old, new, temporary in staged:
                if read_ordinary(path, root) != old:
                    raise ToolFailure("fixture-input-drift", "A target changed before replacement.", path)
                os.replace(temporary, path)
                committed.append((path, old, new))
            for path, original in runtime_inputs.items():
                if read_ordinary(path, root) != original:
                    raise ToolFailure("fixture-runtime-drift", "Runtime changed during refresh; synthetic fixture changes are rolled back.", path)
        except BaseException:
            for path, old, new in reversed(committed):
                if read_ordinary(path, root) != new:
                    raise ToolFailure("fixture-rollback-conflict", "Concurrent edits prevent rollback; preserve the named file and inspect the partial refresh.", path)
                rollback = _stage(path, old)
                try:
                    os.replace(rollback, path)
                finally:
                    rollback.unlink(missing_ok=True)
            raise
        finally:
            for _path, _old, _new, temporary in staged:
                temporary.unlink(missing_ok=True)
    return {"ok": write or not changes, "action": "refreshed-synthetic-route-contracts" if write else "checked-synthetic-route-contracts",
            "synthetic_only": True, "public_evidence_generated": False,
            "changed": [path.relative_to(root).as_posix() for path, _old, _new in changes]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", type=Path, default=Path("."))
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        report = refresh(args.plugin_root, write=args.write)
    except (ToolFailure, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": exc.issue.as_dict() if isinstance(exc, ToolFailure) else str(exc), "public_evidence_generated": False}))
        return 1
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
