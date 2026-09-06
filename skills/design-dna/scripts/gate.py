#!/usr/bin/env python3
"""Run the complete Design DNA provenance gate and emit one verdict.

The route manifest is the authority. A passing run has one immutable build
identity, an exact route set, an explicit reference mapping for every route,
and both wide and narrow rendered coverage. Evidence is always regenerated;
there is deliberately no stale-record reuse mode.

Usage:
  python gate.py --project DIR --build-id BUILD_ID \
      --route-manifest .design-dna/route-manifest.json \
      [--phase first-screen --route-key home | --phase final] \
      [--substitute "Reference Face=Matched Face"] [--match FILE] \
      [--browser-executable FILE] [--dry-run]

  python gate.py --project DIR --build-id PROOF_BUILD_ID \
      --phase proof-slice --proof-slice .design-dna/proof-slice.json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

TOOL_NAME = "gate.py"
SCHEMA_VERSION = 2
MANIFEST_SCHEMA_VERSION = 2
SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_identity() -> dict[str, str]:
    files = [*sorted(SCRIPTS.glob("*.py")), *sorted(SCRIPTS.glob("*.mjs"))]
    return {file.name: sha256_of(file) for file in files}


def normalized_url(value: str) -> str:
    parsed = urlsplit(str(value).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("route URLs must be absolute http(s) URLs")
    route_path = re.sub(r"/{2,}", "/", parsed.path or "/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), route_path, parsed.query, ""))


def route_slug(url: str) -> str:
    """Return a collision-resistant label for an absolute URL."""
    canonical = normalized_url(url)
    parsed = urlsplit(canonical)
    human = f"{parsed.netloc}{parsed.path}"
    if parsed.query:
        human += "-" + parsed.query
    human = re.sub(r"\.html?$", "", human, flags=re.I)
    human = re.sub(r"[^a-z0-9]+", "-", human.lower()).strip("-") or "index"
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return f"{human[:64].rstrip('-')}--{digest}"


def selected_ranks(dossier: Path) -> list[int]:
    if not dossier.is_file():
        return []
    text = dossier.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^-\s+Selected positive ranks[^:]*:\s*([\d,\s]+)$", text, re.M)
    if not match:
        return []
    return sorted({int(item.strip()) for item in match.group(1).split(",") if item.strip().isdigit()})


def strong_ranks(references: Path) -> list[int]:
    ranks: set[int] = set()
    for file in references.glob("strong-*-observation.json"):
        match = re.match(r"strong-(\d+)-observation\.json$", file.name)
        if match:
            ranks.add(int(match.group(1)))
    return sorted(ranks)


def tree_identity(root: Path) -> str:
    """Use the state runtime's one canonical project-tree identity contract."""
    validator = load_validator()
    if validator is None or not hasattr(validator, "project_tree_identity"):
        raise RuntimeError("the packaged project-tree identity helper could not be loaded")
    return validator.project_tree_identity(root)


def resolve_project_path(project: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate.resolve() if candidate.is_absolute() else (project / candidate).resolve()


def load_route_manifest(path: Path, selected: list[int], project: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"route manifest is unreadable JSON: {exc}") from exc
    validator = load_validator()
    if validator is None or not hasattr(validator, "route_manifest_payload_failures"):
        raise ValueError("the packaged route-manifest validator could not be loaded")
    failures = validator.route_manifest_payload_failures(
        payload, selected_ranks=set(selected) if selected else None
    )
    if not failures and hasattr(validator, "route_manifest_reference_failures"):
        failures.extend(
            validator.route_manifest_reference_failures(payload, project=project)
        )
    if failures:
        raise ValueError(" | ".join(failures))
    return payload


def load_visible_decision_source_manifest(
    *,
    validator,
    project: Path,
    dossier: Path,
    route_manifest: dict,
    route_manifest_path: Path,
    phase: str,
    build_id: str,
    route_key: str | None,
) -> tuple[list[str], dict | None, Path, str | None]:
    """Load the dossier-bound preimplementation visible-decision record."""

    expected = (project / ".design-dna" / "visible-decision-sources.json").resolve()
    failures: list[str] = []
    if validator is None or not all(
        hasattr(validator, name)
        for name in (
            "markdown_sections", "markdown_label_value", "bound_artifact",
            "visible_decision_source_manifest_failures",
        )
    ):
        return ["the packaged visible-decision source validator is unavailable"], None, expected, None
    if not dossier.is_file():
        return ["the dossier required to bind visible decisions is missing"], None, expected, None
    body = dossier.read_text(encoding="utf-8", errors="strict")
    sections = validator.markdown_sections(body)
    visible_cell = validator.markdown_label_value(
        sections.get("Preimplementation visible decisions", ""),
        "Visible decision source manifest",
    )
    proof_identity = validator.markdown_label_value(
        sections.get("Route manifest", ""),
        "First-screen proof build ID and primary route key",
    )
    artifact, binding_failures = validator.bound_artifact(
        (visible_cell or "").strip(),
        project=project,
        record_path=dossier,
        label="Visible decision source manifest",
    )
    failures.extend(binding_failures)
    if artifact is None or artifact.resolve() != expected:
        failures.append("visible decisions must bind .design-dna/visible-decision-sources.json")
        return failures, None, expected, None
    try:
        payload = json.loads(expected.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        failures.append(f"visible decision source manifest is unreadable: {exc}")
        return failures, None, expected, None
    failures.extend(
        validator.visible_decision_source_manifest_failures(
            payload,
            project=project,
            route_manifest=route_manifest,
            route_manifest_path=route_manifest_path,
            proof_identity=proof_identity or "",
            require_construction_v2=True,
        )
    )
    proof_fields = validator.semicolon_fields(proof_identity or "")
    if phase == "first-screen" and (
        payload.get("proof_build_id") != build_id
        or proof_fields.get("build_id") != build_id
        or proof_fields.get("route_key") != route_key
    ):
        failures.append("first-screen CLI build/route identity differs from the preimplementation source manifest")
    return failures, payload, expected, sha256_of(expected)


def run_node(script: Path, args: list[str], cwd: Path) -> tuple[int, str, str]:
    env = dict(os.environ)
    env.setdefault("MSYS_NO_PATHCONV", "1")
    proc = subprocess.run(
        ["node", str(script), *args], cwd=str(cwd), env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def packaged_schema_version(producer: Path) -> int | None:
    body = producer.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"\bSCHEMA_VERSION\s*=\s*(\d+)",
        body,
    )
    if match:
        return int(match.group(1))
    if "PRODUCER_OUTPUT_SCHEMA_VERSION" in body:
        contract = producer.parent / "provenance_contract.mjs"
        contract_match = re.search(
            r"\bPRODUCER_OUTPUT_SCHEMA_VERSION\s*=\s*(\d+)",
            contract.read_text(encoding="utf-8", errors="replace"),
        )
        if contract_match:
            return int(contract_match.group(1))
    return None


def record_identity_ok(
    record: Path,
    producer: Path,
    build_id: str,
    run_id: str,
    manifest_id: str,
    manifest_sha256: str,
    expected_routes: list[dict],
    expected_viewports: list[dict],
    expected_first_screen: bool | None = None,
) -> tuple[bool, str]:
    try:
        payload = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return False, f"record unreadable: {exc}"
    expected = sha256_of(producer)
    if payload.get("tool") != producer.name:
        return False, f"tool identity mismatch for {producer.name}"
    schema = packaged_schema_version(producer)
    if schema is None or payload.get("schema_version") != schema:
        return False, f"schema identity mismatch for {producer.name}"
    if payload.get("producer_script_sha256") != expected:
        return False, f"producer identity mismatch for {producer.name}"
    if payload.get("build_id") != build_id:
        return False, f"record build_id is {payload.get('build_id')!r}, expected {build_id!r}"
    if payload.get("run_id") != run_id:
        return False, "record was not created by this gate invocation"
    if payload.get("manifest_id") != manifest_id or payload.get("manifest_sha256") != manifest_sha256:
        return False, "record was not created from the current route manifest"
    validator = load_validator()
    if validator is None or not hasattr(validator, "served_content_identity_failures"):
        return False, "served-content identity validator unavailable"
    served_failures = validator.served_content_identity_failures(
        payload.get("served_content_identity"),
        expected_routes=expected_routes,
        expected_viewports=expected_viewports,
    )
    if served_failures:
        return False, " | ".join(served_failures)
    if producer.name == "scan_build_components.mjs":
        if not hasattr(validator, "census_runtime_failures"):
            return False, "component census runtime validator unavailable"
        census_failures = validator.census_runtime_failures(
            payload,
            expected_routes=expected_routes,
            expected_viewports=expected_viewports,
            first_screen=bool(expected_first_screen),
            record_path=record,
        )
        if census_failures:
            return False, " | ".join(census_failures)
    return True, "producer and build identity verified"


def last_json(text: str) -> dict | None:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        pass
    start = text.rfind("\n{")
    if start == -1:
        start = text.find("{")
    if start == -1:
        return None
    try:
        return json.loads(text[start:].strip())
    except ValueError:
        return None


BINDING = re.compile(r"(?P<path>\.design-dna/[^\s|`]+?)(?P<sep>\s+(?:plus\s+)?sha256:)(?P<hex>[0-9a-f]{64})", re.I)


def rebind_dossier(text: str, digests: dict[str, str]) -> tuple[str, list[str]]:
    rebound: list[str] = []

    def swap(match: re.Match) -> str:
        artifact = match.group("path").replace("\\", "/")
        digest = digests.get(artifact)
        if not digest or digest == match.group("hex"):
            return match.group(0)
        rebound.append(artifact)
        return f"{match.group('path')}{match.group('sep')}{digest}"

    return BINDING.sub(swap, text), rebound


def load_validator():
    spec = importlib.util.spec_from_file_location("design_dna_gate_validator", SCRIPTS / "init_project_state.py")
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def authorization_filename(checked_at: str, authorization_id: str) -> str:
    stamp = re.sub(r"[^0-9]", "", checked_at)[:20]
    return f"{stamp}-{authorization_id}.json"


def validate_prebuild_authorization(
    *,
    validator,
    project: Path,
    authorization_path: Path,
    manifest: dict,
    manifest_sha256: str,
    dossier: Path,
    final_build_id: str,
    final_tree_sha256: str,
) -> tuple[list[str], dict | None, str | None]:
    if validator is None or not hasattr(validator, "load_prebuild_authorization"):
        return ["the packaged prebuild-authorization validator could not be loaded"], None, None
    failures, authorization, authorization_sha = validator.load_prebuild_authorization(
        project, authorization_path
    )
    if not isinstance(authorization, dict):
        return failures, None, authorization_sha
    if authorization.get("manifest_id") != manifest.get("manifest_id"):
        failures.append("prebuild authorization belongs to another manifest_id")
    if authorization.get("manifest_sha256") != manifest_sha256:
        failures.append("prebuild authorization manifest bytes have drifted")
    if authorization.get("proof_build_id") == final_build_id:
        failures.append("proof and final build IDs must be distinct")
    if authorization.get("proof_tree_sha256") == final_tree_sha256:
        failures.append("proof and final tree identities must be distinct")
    try:
        authorized_at = datetime.fromisoformat(str(authorization.get("authorized_at", "")).replace("Z", "+00:00"))
    except ValueError:
        authorized_at = None
        failures.append("prebuild authorization has an invalid timestamp")
    if authorized_at is not None and authorized_at >= datetime.now(timezone.utc):
        failures.append("prebuild authorization does not precede the final gate run")
    if dossier.is_file() and authorization.get("dossier_core_sha256") != validator.dossier_core_sha256(dossier):
        failures.append("dossier research changed after first-screen authorization")
    visible_binding = authorization.get("visible_decision_source_manifest")
    current_visible = project / ".design-dna" / "visible-decision-sources.json"
    if (
        not isinstance(visible_binding, dict)
        or set(visible_binding) != {"path", "sha256"}
        or visible_binding.get("path") != ".design-dna/visible-decision-sources.json"
        or not current_visible.is_file()
        or visible_binding.get("sha256") != sha256_of(current_visible)
    ):
        failures.append("visible-decision source manifest changed after first-screen authorization")
    visible_snapshot = authorization.get("visible_decision_snapshot")
    visible_snapshot_path = (
        resolve_project_path(project, str(visible_snapshot.get("path") or ""))
        if isinstance(visible_snapshot, dict)
        else Path()
    )
    if (
        not isinstance(visible_snapshot, dict)
        or set(visible_snapshot) != {"path", "sha256"}
        or not visible_snapshot_path.is_file()
        or visible_snapshot.get("sha256") != sha256_of(visible_snapshot_path)
        or visible_snapshot.get("sha256") != (
            visible_binding.get("sha256") if isinstance(visible_binding, dict) else None
        )
    ):
        failures.append("prebuild authorization visible-decision snapshot is missing or drifted")
    gate_binding = authorization.get("first_screen_gate")
    try:
        first_gate_path = resolve_project_path(
            project,
            str(gate_binding.get("path") if isinstance(gate_binding, dict) else ""),
        )
    except ValueError:
        first_gate_path = Path()
    if not isinstance(gate_binding, dict) or not first_gate_path.is_file():
        failures.append("prebuild authorization has no current first-screen gate")
        return failures, authorization, authorization_sha
    if gate_binding.get("sha256") != sha256_of(first_gate_path):
        failures.append("first-screen gate bytes no longer match the authorization")
        return failures, authorization, authorization_sha
    try:
        first_gate = json.loads(first_gate_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        failures.append(f"first-screen gate is unreadable: {exc}")
        return failures, authorization, authorization_sha
    expected = {
        "authorization_id": authorization.get("authorization_id"),
        "build_id": authorization.get("proof_build_id"),
        "route_key": authorization.get("route_key"),
        "build_tree_sha256_before": authorization.get("proof_tree_sha256"),
        "build_tree_sha256_after": authorization.get("proof_tree_sha256"),
        "dossier_core_sha256": authorization.get("dossier_core_sha256"),
        "route_manifest_sha256": authorization.get("manifest_sha256"),
        "visible_decision_source_manifest": visible_binding,
        "visible_decision_snapshot": visible_snapshot,
    }
    for field, value in expected.items():
        if first_gate.get(field) != value:
            failures.append(f"first-screen gate {field} differs from its authorization")
    if (
        first_gate.get("phase") != "first-screen"
        or first_gate.get("pass") is not True
        or first_gate.get("project") != str(project.resolve())
        or first_gate.get("runtime_identity") != runtime_identity()
    ):
        failures.append("first-screen gate is not a current passing project/runtime predecessor")
    latest_alias = project / ".design-dna" / "evidence" / "first-screen-gate.json"
    if not latest_alias.is_file() or sha256_of(latest_alias) != gate_binding.get("sha256"):
        failures.append("latest first-screen gate alias differs from the selected immutable predecessor")
    return failures, authorization, authorization_sha


def write_prebuild_authorization(
    *,
    validator,
    project: Path,
    path: Path,
    authorization_id: str,
    checked_at: str,
    gate_file: Path,
    manifest: dict,
    manifest_sha256: str,
    route_key: str,
    build_id: str,
    tree_sha256: str,
    dossier_core_sha256: str,
    visible_decision_sha256: str,
    visible_decision_snapshot: Path,
) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = sorted(path.parent.glob("*.json"), key=lambda item: item.name)
    previous = None
    if existing:
        if validator is None or not hasattr(validator, "prebuild_authorization_chain"):
            raise RuntimeError("the packaged authorization-chain validator could not be loaded")
        failures, records = validator.prebuild_authorization_chain(project)
        if failures:
            raise RuntimeError(" | ".join(failures))
        prior_path, _prior_payload, prior_sha = records[-1]
        previous = {
            "path": prior_path.relative_to(project).as_posix(),
            "sha256": prior_sha,
        }
    payload = {
        "schema_version": 1,
        "record_type": "design-dna-prebuild-authorization",
        "authorization_id": authorization_id,
        "authorized_at": checked_at,
        "project": str(project.resolve()),
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": manifest_sha256,
        "route_key": route_key,
        "proof_build_id": build_id,
        "proof_tree_sha256": tree_sha256,
        "dossier_core_sha256": dossier_core_sha256,
        "visible_decision_source_manifest": {
            "path": ".design-dna/visible-decision-sources.json",
            "sha256": visible_decision_sha256,
        },
        "visible_decision_snapshot": {
            "path": visible_decision_snapshot.relative_to(project).as_posix(),
            "sha256": sha256_of(visible_decision_snapshot),
        },
        "first_screen_gate": {
            "path": gate_file.relative_to(project).as_posix(),
            "sha256": sha256_of(gate_file),
        },
        "previous_authorization": previous,
        "producer_script_sha256": sha256_of(Path(__file__).resolve()),
        "runtime_identity": runtime_identity(),
    }
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    return payload


def run_proof_slice_gate(args: argparse.Namespace) -> int:
    """Validate one non-public source-faithful proof slice without authorization.

    This intentionally does not load a public route manifest, dossier,
    construction journal, or standard first-screen predecessor.  A passing
    record is evidence of a bounded internal specimen only, never permission
    to build another section, release a site, or enter public synthesis.
    """

    project = Path(args.project).resolve()
    validator = load_validator()
    checked_at = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    run_id = secrets.token_hex(16)
    proof_path = resolve_project_path(project, str(args.proof_slice or ""))
    failures: list[str] = []
    payload: dict | None = None
    if validator is None or not hasattr(validator, "proof_slice_manifest_failures"):
        failures.append("the packaged proof-slice validator is unavailable")
    elif not proof_path.is_relative_to(project) or not proof_path.is_file():
        failures.append("proof-slice manifest is missing or outside the project")
    else:
        try:
            candidate = json.loads(proof_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            failures.append(f"proof-slice manifest is unreadable: {exc}")
            candidate = None
        if not isinstance(candidate, dict):
            failures.append("proof-slice manifest must be a JSON object")
        else:
            payload = candidate
            failures.extend(validator.proof_slice_manifest_failures(project, payload, build_id=args.build_id))

    implementation = payload.get("implementation") if isinstance(payload, dict) else None
    built = False
    if isinstance(implementation, dict):
        relative = implementation.get("source_file")
        candidate = resolve_project_path(project, str(relative or ""))
        try:
            built = (
                candidate.is_file()
                and candidate.is_relative_to(project)
                and isinstance(implementation.get("source_file_sha256"), str)
                and sha256_of(candidate) == implementation["source_file_sha256"]
            )
        except OSError:
            built = False
    static_source_valid = not failures
    statuses = {
        "proof_slice_built": "unverified",
        "proof_slice_render": "did-not-run",
        "proof_slice_gate": "did-not-run",
        "standard_first_screen_gate": "did-not-run",
        "final_site": "not-applicable",
        "public_eligibility": "ineligible",
    }
    rendered_record: Path | None = None
    rendered_payload: dict | None = None
    build_record: Path | None = None
    build_payload: dict | None = None
    if not failures and not args.dry_run and isinstance(implementation, dict):
        proof_id = payload.get("proof_slice_id") if isinstance(payload, dict) else "invalid-proof-slice"
        safe_proof_id = proof_id if isinstance(proof_id, str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", proof_id) else "invalid-proof-slice"
        output = project / ".design-dna" / "evidence" / "proof-slice-runs" / safe_proof_id
        output.mkdir(parents=True, exist_ok=True)
        source_path = resolve_project_path(project, implementation["source_file"])
        output_path = resolve_project_path(project, implementation["build_output_path"])
        build_record = output / f"{args.build_id}-{run_id}-build.json"
        if not output_path.is_relative_to(project) or output_path == source_path:
            failures.append("proof-slice controlled build output is unsafe or aliases its source file")
        else:
            build_code, build_stdout, build_stderr = run_node(
                SCRIPTS / "build_proof_slice.mjs",
                ["--manifest", str(proof_path), "--source", str(source_path), "--output", str(output_path), "--record", str(build_record)],
                project,
            )
            build_payload = last_json(build_stdout)
            expected_source = {"path": str(source_path.resolve()), "sha256": implementation["source_file_sha256"]}
            expected_component_text = sorted(
                [
                    {"component_id": component.get("component_id"), "text_sha256": component.get("content", {}).get("build_text_sha256")}
                    for component in payload.get("visible_components", []) if isinstance(component, dict)
                ],
                key=lambda item: str(item["component_id"]),
            )
            if (
                build_code != 0
                or not build_record.is_file()
                or not isinstance(build_payload, dict)
                or build_payload.get("tool") != "build_proof_slice.mjs"
                or build_payload.get("schema_version") != 1
                or build_payload.get("producer_script_sha256") != sha256_of(SCRIPTS / "build_proof_slice.mjs")
                or build_payload.get("source") != expected_source
                or build_payload.get("components") != expected_component_text
                or not isinstance(build_payload.get("output"), dict)
                or build_payload["output"].get("path") != str(output_path.resolve())
                or not output_path.is_file()
                or build_payload["output"].get("bytes") != output_path.stat().st_size
                or build_payload["output"].get("sha256") != sha256_of(output_path)
            ):
                failures.append("proof-slice controlled build did not emit an exact current source-to-output artifact: " + (build_stderr or build_stdout).strip())
            else:
                statuses["proof_slice_built"] = "built"
        rendered_record = output / f"{args.build_id}-{run_id}-render.json"
        if not failures:
            command = [
                "--url", implementation["proof_url"], "--manifest", str(proof_path),
                "--build-record", str(build_record), "--out", str(rendered_record),
            ]
            if args.browser_executable:
                command.extend(["--browser-executable", args.browser_executable])
            code, stdout, stderr = run_node(SCRIPTS / "scan_proof_slice.mjs", command, project)
            rendered_payload = last_json(stdout)
            if (
                code != 0
                or not rendered_record.is_file()
                or not isinstance(rendered_payload, dict)
                or rendered_payload.get("pass") is not True
                or not isinstance(rendered_payload.get("checks"), list)
                or len(rendered_payload["checks"]) != 2
            ):
                statuses["proof_slice_render"] = "fail"
                failures.append(
                    "proof-slice rendered wide/narrow scan failed: "
                    + (json.dumps(rendered_payload.get("checks"), ensure_ascii=False) if isinstance(rendered_payload, dict) else (stderr or stdout).strip())
                )
            else:
                statuses["proof_slice_render"] = "pass"
    elif args.dry_run:
        failures.append("proof-slice rendered wide/narrow scan did not run in --dry-run; static source facts are unverified and nonadvance.")
    if statuses["proof_slice_render"] == "pass" and not failures:
        statuses["proof_slice_gate"] = "pass"
    elif statuses["proof_slice_render"] == "did-not-run" and args.dry_run:
        statuses["proof_slice_gate"] = "unverified"
    else:
        statuses["proof_slice_gate"] = "fail"
    verdict = (
        "PROOF-SLICE GATE PASS: one rendered wide+narrow internal-unverified source-faithful first-screen specimen is bounded; standard first-screen and final site gates did not run."
        if statuses["proof_slice_gate"] == "pass" else "PROOF-SLICE GATE FAIL: " + " || ".join(failures)
    )
    record = {
        "tool": TOOL_NAME,
        "schema_version": 1,
        "record_type": "design-dna-proof-slice-gate",
        "producer_script_sha256": sha256_of(Path(__file__).resolve()),
        "runtime_identity": runtime_identity(),
        "checked_at": checked_at,
        "project": str(project),
        "build_id": args.build_id,
        "run_id": run_id,
        "phase": "proof-slice",
        "proof_slice_manifest": (
            {"path": proof_path.relative_to(project).as_posix(), "sha256": sha256_of(proof_path)}
            if proof_path.is_file() and proof_path.is_relative_to(project) else None
        ),
        "rendered_proof": (
            {"path": rendered_record.relative_to(project).as_posix(), "sha256": sha256_of(rendered_record)}
            if rendered_record is not None and rendered_record.is_file() else None
        ),
        "controlled_build": (
            {"path": build_record.relative_to(project).as_posix(), "sha256": sha256_of(build_record)}
            if build_record is not None and build_record.is_file() else None
        ),
        "statuses": statuses,
        "failures": failures,
        "pass": statuses["proof_slice_gate"] == "pass",
        "verdict": verdict,
        "owner_order": "Internal proof only: no public selection, standard first-screen authorization, final-site authorization, release, sync, or push follows from this record.",
    }
    if args.dry_run:
        print(json.dumps(record, indent=2))
        return 0 if record["pass"] else 1
    proof_id = payload.get("proof_slice_id") if isinstance(payload, dict) else "invalid-proof-slice"
    safe_proof_id = proof_id if isinstance(proof_id, str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", proof_id) else "invalid-proof-slice"
    output = project / ".design-dna" / "evidence" / "proof-slice-runs" / safe_proof_id
    output.mkdir(parents=True, exist_ok=True)
    gate_file = output / f"{args.build_id}-{run_id}.json"
    with gate_file.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, indent=2)
        handle.write("\n")
    print(json.dumps({**record, "record": gate_file.relative_to(project).as_posix()}, indent=2))
    return 0 if record["pass"] else 1


def run_with_project_lock(args: argparse.Namespace, action) -> int:
    """Serialize evidence writers without treating lock metadata as site code."""
    if args.dry_run:
        return action()
    project = Path(args.project).absolute()
    validator = load_validator()
    if validator is None:
        print("GATE FAIL project-lock: packaged lock validator unavailable")
        return 1
    try:
        if not project.is_dir():
            raise ValueError("project root does not exist")
        validator.assert_no_reparse_ancestors(project)
        with validator.ProjectMutationLock(project, f"gate-{args.phase}"):
            return action()
    except (validator.StateError, OSError, ValueError) as exc:
        print(f"GATE FAIL gate-operation: {getattr(exc, 'code', type(exc).__name__)}: {exc}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="gate.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--project", default=".", help="project root holding .design-dna/")
    parser.add_argument("--build-id", required=True, help="immutable ID for the exact build under test")
    parser.add_argument("--route-manifest", default=None, help="authoritative JSON route/reference/state/viewport manifest")
    parser.add_argument("--phase", choices=("proof-slice", "first-screen", "final", "maintenance"), default="final",
                        help="proof-slice is a separate internal specimen gate; first-screen writes standard prebuild authorization; final checks the complete site")
    parser.add_argument("--proof-slice", default=None,
                        help="typed internal .design-dna/proof-slice.json required only by --phase proof-slice")
    parser.add_argument("--route-key", default=None, help="manifest route key required by --phase first-screen")
    parser.add_argument("--prebuild-authorization", default=None,
                        help="latest append-only first-screen authorization; required by --phase final")
    parser.add_argument("--substitute", action="append", default=[], help="FROM=TO, a declared rank-one typeface substitute")
    parser.add_argument("--match", default=None, help="typeface-match.json from match_typeface.mjs")
    parser.add_argument("--browser-executable", default=None)
    parser.add_argument("--dry-run", action="store_true", help="validate inputs and print the exact matrix without opening a browser")
    args = parser.parse_args()
    run_id = secrets.token_hex(16)
    authorization_id = secrets.token_hex(16) if args.phase == "first-screen" else None
    checked_at = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", args.build_id):
        parser.error("--build-id must be an immutable 8-128 character identifier")
    if args.phase == "proof-slice":
        if not args.proof_slice:
            parser.error("--phase proof-slice requires --proof-slice")
        if args.route_manifest or args.route_key or args.prebuild_authorization or args.substitute or args.match:
            parser.error("--phase proof-slice is separate from route-manifest, standard first-screen authorization, substitutions, and final-site inputs")
        return run_with_project_lock(args, lambda: run_proof_slice_gate(args))
    if not args.route_manifest:
        parser.error("--route-manifest is required by standard first-screen and final gates")
    if args.proof_slice:
        parser.error("--proof-slice is valid only with --phase proof-slice")
    if args.phase == "final" and not args.prebuild_authorization:
        parser.error("--phase final requires --prebuild-authorization")
    if args.phase in {"first-screen", "maintenance"} and args.prebuild_authorization:
        parser.error("--prebuild-authorization is valid only with --phase final")

    return run_with_project_lock(args, lambda: run_standard_gate(args, run_id, authorization_id, checked_at))


def run_standard_gate(args, run_id, authorization_id, checked_at) -> int:
    project = Path(args.project).resolve()
    dna = project / ".design-dna"
    references = dna / "references"
    evidence = dna / "evidence"
    dossier = dna / "reference-dossier.md"
    manifest_path = resolve_project_path(project, args.route_manifest)
    runtime_before = runtime_identity()
    validator_module = load_validator()

    steps: list[dict] = []
    reasons: list[str] = []
    evidence_hashes: list[dict] = []
    aggregate_served_identities: list[tuple[str, dict]] = []

    def step(name: str, ok: bool, verdict: str, command: list[str] | None = None,
             record: Path | None = None, **meta) -> None:
        entry = {"name": name, "pass": bool(ok), "verdict": verdict, **meta}
        if command:
            entry["command"] = " ".join(command)
        if record and record.is_file():
            try:
                record_name = str(record.relative_to(project)).replace(os.sep, "/")
            except ValueError:
                record_name = str(record)
            digest = sha256_of(record)
            entry.update({"record": record_name, "sha256": digest})
            evidence_hashes.append({"kind": name.split(":", 1)[0], "path": record_name, "sha256": digest, **meta})
        steps.append(entry)
        if not ok:
            reasons.append(f"{name}: {verdict}")

    def bind_generated_interaction_frames(
        record_path: Path,
        payload: dict,
        *,
        kind: str,
    ) -> tuple[bool, str]:
        if validator_module is None or not hasattr(
            validator_module, "generated_interaction_frame_bindings"
        ):
            return False, "interaction-frame validator unavailable"
        frame_failures, bindings = validator_module.generated_interaction_frame_bindings(
            payload, record_path=record_path
        )
        if frame_failures:
            return False, " | ".join(frame_failures)
        existing = {entry.get("path") for entry in evidence_hashes}
        for binding in bindings:
            frame = binding["file"]
            relative = frame.relative_to(project).as_posix()
            if relative in existing:
                return False, f"duplicate interaction-frame ledger path: {relative}"
            existing.add(relative)
            evidence_hashes.append(
                {
                    "kind": kind,
                    "path": relative,
                    "sha256": binding["sha256"],
                    "bytes": binding["bytes"],
                }
            )
        return True, f"{len(bindings)} generated interaction frames hash-bound"

    if validator_module is None:
        step("direction-prerequisites", False, "packaged direction prerequisite validator unavailable")
    else:
        prerequisite_failures = validator_module.prebuild_failures(
            # Final construction has a different tree from its first screen;
            # validate that immutable predecessor in the authorization branch.
            project, require_first_screen=False, require_construction=False,
        )
        prerequisite_failures.extend(validator_module.owner_recurrence_integration_failures(
            project / ".design-dna", require_resolved=True,
        ))
        prerequisite_failures.extend(validator_module.owner_pattern_contract_failures(project, phase="prebuild"))
        step("direction-prerequisites", not prerequisite_failures,
             "all applicable direction, contrast, challenge, connected-experience and owner-pattern prerequisites are resolved"
             if not prerequisite_failures else " | ".join(prerequisite_failures), failures=prerequisite_failures)

    ranks_all = strong_ranks(references)
    ranks = selected_ranks(dossier) or ranks_all
    if not ranks_all:
        step("references", False, "no strong-N-observation.json exists; there is nothing to trace to")
    else:
        missing_styles = []
        stale_styles = []
        for rank in ranks:
            style_file = references / f"strong-{rank}-styles.json"
            if not style_file.is_file():
                missing_styles.append(rank)
                continue
            try:
                style_payload = json.loads(style_file.read_text(encoding="utf-8"))
                measured = style_payload.get("viewports_measured") or []
                if (style_payload.get("schema_version", 0) < 2 or
                    not any(isinstance(view, dict) and view.get("width", 0) >= 1280 for view in measured) or
                    not any(isinstance(view, dict) and view.get("width", 9999) <= 430 for view in measured)):
                    stale_styles.append(rank)
            except (OSError, ValueError):
                stale_styles.append(rank)
        step("references", not missing_styles and not stale_styles,
             f"strong ranks {ranks_all}; selected {ranks}" if not missing_styles else
             "selected ranks without measured styles: " + ", ".join(map(str, missing_styles))
             if missing_styles else "selected ranks with stale style schema: " + ", ".join(map(str, stale_styles)))
    if not dossier.is_file():
        step("dossier-present", False, "no .design-dna/reference-dossier.md")

    manifest = None
    manifest_sha256 = sha256_of(manifest_path) if manifest_path.is_file() else None
    visible_decision_payload: dict | None = None
    visible_decision_path = (project / ".design-dna" / "visible-decision-sources.json").resolve()
    visible_decision_sha256: str | None = None
    active_routes: list[dict] = []
    try:
        manifest = load_route_manifest(manifest_path, ranks, project)
        mapped_missing = sorted({r["mapped_reference_rank"] for r in manifest["routes"]} - set(ranks_all))
        if mapped_missing:
            raise ValueError("mapped reference observations are missing for ranks " + ", ".join(map(str, mapped_missing)))
        if args.phase == "first-screen":
            if not args.route_key:
                raise ValueError("--phase first-screen requires --route-key")
            active_routes = [route for route in manifest["routes"] if route["key"] == args.route_key]
            if len(active_routes) != 1:
                raise ValueError(f"--route-key {args.route_key!r} is not a unique manifest route")
        else:
            if args.route_key:
                raise ValueError("--route-key is only valid with --phase first-screen")
            active_routes = list(manifest["routes"])
        step("route-manifest", True,
             f"{len(manifest['routes'])} exact route(s), {len(manifest['viewports'])} viewport(s)",
             record=manifest_path if args.phase in {"final", "maintenance"} else None)
    except ValueError as exc:
        step("route-manifest", False, str(exc), record=manifest_path if manifest_path.is_file() else None)

    if manifest is not None:
        (
            visible_failures,
            visible_decision_payload,
            visible_decision_path,
            visible_decision_sha256,
        ) = load_visible_decision_source_manifest(
            validator=validator_module,
            project=project,
            dossier=dossier,
            route_manifest=manifest,
            route_manifest_path=manifest_path,
            phase=args.phase,
            build_id=args.build_id,
            route_key=args.route_key,
        )
        step(
            "visible-decision-source-manifest",
            not visible_failures,
            "preimplementation visible decisions bind exact source evidence"
            if not visible_failures else " | ".join(visible_failures),
            record=visible_decision_path if visible_decision_path.is_file() else None,
        )
        if args.phase == "first-screen" and isinstance(visible_decision_payload, dict):
            try:
                phase_module = validator_module.load_bundled_source_module("_design_dna_construction_phase", SCRIPTS / "construction_phase.py")
                active_routes = phase_module.derive_first_screen_routes(manifest, visible_decision_payload, [args.route_key])
                step("first-screen-phase-plan", True, "active states derive only from the immutable pre-code proof decision subset; full planned routes remain bound")
            except (AttributeError, ValueError, TypeError, KeyError) as exc:
                step("first-screen-phase-plan", False, str(exc))
        construction_failures: list[str] = []
        construction_entry: Path | None = None
        if (
            isinstance(visible_decision_payload, dict)
            and validator_module is not None
            and hasattr(validator_module, "construction_authorization_failures")
        ):
            construction_failures = validator_module.construction_authorization_failures(
                project,
                visible_decision_payload,
                route_manifest_path=manifest_path,
                dossier_path=dossier,
            )
            auth = visible_decision_payload.get("construction_authorization")
            if isinstance(auth, dict) and isinstance(auth.get("entry_path"), str):
                construction_entry = resolve_project_path(project, auth["entry_path"])
        else:
            construction_failures = [
                "the packaged construction-binding journal validator is unavailable"
            ]
        step(
            "construction-authorization",
            not construction_failures,
            "pre-code source bindings and append-only journal match current project"
            if not construction_failures else " | ".join(construction_failures),
            record=construction_entry if construction_entry is not None and construction_entry.is_file() else None,
        )
        if isinstance(visible_decision_payload, dict) and validator_module is not None:
            controls = validator_module.load_bundled_source_module("_design_dna_implementation_control", SCRIPTS / "implementation_control.py")
            prohibited_changes = controls.prohibition_failures(project, visible_decision_payload, validator_module)
            step("implementation-prohibition", not prohibited_changes,
                 "no broad source changes after a failed first-screen gate" if not prohibited_changes else " | ".join(prohibited_changes),
                 failures=prohibited_changes)
        if args.phase == "first-screen":
            isolation_failures: list[str] = []
            if (
                isinstance(visible_decision_payload, dict)
                and validator_module is not None
                and hasattr(validator_module, "first_screen_construction_isolation_failures")
            ):
                isolation_failures = validator_module.first_screen_construction_isolation_failures(
                    project,
                    visible_decision_payload,
                    route_manifest=manifest,
                    route_key=str(args.route_key or ""),
                )
            else:
                isolation_failures = ["the packaged first-screen source-tree isolation validator is unavailable"]
            step(
                "proof-isolation",
                not isolation_failures,
                "only declared primary proof source/region changes exist"
                if not isolation_failures else " | ".join(isolation_failures),
            )

    if args.substitute and not args.match:
        default_match = evidence / "typeface-match.json"
        if default_match.is_file():
            args.match = str(default_match)
        else:
            step("typeface-match", False, "--substitute requires a verified match_typeface.mjs record; the producer does not choose faces")

    build_before = tree_identity(project)
    dossier_core = None
    if dossier.is_file() and validator_module is not None and hasattr(validator_module, "dossier_core_sha256"):
        dossier_core = validator_module.dossier_core_sha256(dossier)
    step(
        "dossier-core",
        isinstance(dossier_core, str) and re.fullmatch(r"[0-9a-f]{64}", dossier_core) is not None,
        "normalized dossier core identity bound" if dossier_core else "normalized dossier core identity unavailable",
    )
    authorization_path: Path | None = None
    authorization_payload: dict | None = None
    authorization_sha256: str | None = None
    if not reasons and manifest is not None:
        if args.phase == "first-screen":
            authorization_path = (
                evidence
                / "prebuild-authorizations"
                / authorization_filename(checked_at, authorization_id)
            )
            existing_auth = sorted(authorization_path.parent.glob("*.json")) if authorization_path.parent.is_dir() else []
            auth_failures: list[str] = []
            if existing_auth:
                if validator_module is None or not hasattr(validator_module, "prebuild_authorization_chain"):
                    auth_failures.append("the packaged authorization-chain validator could not be loaded")
                else:
                    auth_failures, _records = validator_module.prebuild_authorization_chain(project)
            step(
                "authorization-chain",
                not auth_failures,
                "append-only predecessor chain ready" if not auth_failures else " | ".join(auth_failures),
            )
        elif args.phase == "maintenance":
            workflow = validator_module.load_bundled_source_module("_design_dna_maintenance_workflow", SCRIPTS / "maintenance_workflow.py")
            maintenance_failures = workflow.check(project, visible_decision_payload, validator_module)
            step("maintenance-baseline", not maintenance_failures,
                 "audited existing baseline and frozen change scope verified" if not maintenance_failures else " | ".join(maintenance_failures),
                 failures=maintenance_failures)
        else:
            authorization_path = resolve_project_path(project, args.prebuild_authorization)
            auth_failures, authorization_payload, authorization_sha256 = validate_prebuild_authorization(
                validator=validator_module,
                project=project,
                authorization_path=authorization_path,
                manifest=manifest,
                manifest_sha256=manifest_sha256,
                dossier=dossier,
                final_build_id=args.build_id,
                final_tree_sha256=build_before,
            )
            step(
                "prebuild-authorization",
                not auth_failures,
                "validated exact latest first-screen predecessor" if not auth_failures else " | ".join(auth_failures),
                record=authorization_path if authorization_path.is_file() else None,
            )
    if args.dry_run:
        print(json.dumps({
            "tool": TOOL_NAME, "schema_version": SCHEMA_VERSION, "project": str(project),
            "build_id": args.build_id, "build_tree_sha256": build_before,
            "run_id": run_id,
            "route_manifest": str(manifest_path), "manifest": manifest,
            "phase": args.phase, "route_key": args.route_key, "active_routes": active_routes,
            "prebuild_authorization": str(authorization_path) if authorization_path else None,
            "visible_decision_source_manifest": (
                {"path": ".design-dna/visible-decision-sources.json", "sha256": visible_decision_sha256}
                if visible_decision_sha256 else None
            ),
            "steps_so_far": steps, "pass": not reasons,
        }, indent=2))
        return 0 if not reasons else 1

    evidence.mkdir(parents=True, exist_ok=True)
    phase_evidence = evidence
    manifest_snapshot: Path | None = None
    dossier_snapshot: Path | None = None
    visible_decision_snapshot: Path | None = None
    if args.phase == "first-screen":
        phase_evidence = evidence / "prebuild-runs" / str(authorization_id)
        phase_evidence.mkdir(parents=True, exist_ok=False)
        if manifest_path.is_file():
            manifest_snapshot = phase_evidence / "route-manifest.json"
            shutil.copyfile(manifest_path, manifest_snapshot)
            step(
                "route-manifest-snapshot",
                sha256_of(manifest_snapshot) == manifest_sha256,
                "immutable manifest bytes captured before browser evidence",
                record=manifest_snapshot,
            )
        if dossier.is_file():
            dossier_snapshot = phase_evidence / "reference-dossier.md"
            shutil.copyfile(dossier, dossier_snapshot)
            step(
                "dossier-snapshot",
                (
                    validator_module is not None
                    and hasattr(validator_module, "dossier_core_sha256")
                    and validator_module.dossier_core_sha256(dossier_snapshot)
                    == dossier_core
                ),
                "immutable dossier core captured before browser evidence",
                record=dossier_snapshot,
            )
        if visible_decision_path.is_file():
            visible_decision_snapshot = phase_evidence / "visible-decision-sources.json"
            shutil.copyfile(visible_decision_path, visible_decision_snapshot)
            step(
                "visible-decision-source-snapshot",
                sha256_of(visible_decision_snapshot) == visible_decision_sha256,
                "immutable visible-decision source bytes captured before browser evidence",
                record=visible_decision_snapshot,
            )

    browser = ["--browser-executable", args.browser_executable] if args.browser_executable else []
    manifest_binding_args = ["--manifest", str(manifest_path)] if manifest is not None else []
    build_styles: list[Path] = []
    prefix = "first-screen-" if args.phase == "first-screen" else ""
    census = phase_evidence / f"{prefix}component-census.json"
    structure = phase_evidence / f"{prefix}structure-diff.json"
    mechanisms = phase_evidence / f"{prefix}mechanism-diff.json"
    provenance = phase_evidence / f"{prefix}style-provenance.json"
    signature = phase_evidence / f"{prefix}signature-transfer.json"
    rebound: list[str] = []
    candidate_dossier: str | None = None

    if not reasons and manifest is not None:
        font_record = phase_evidence / f"{prefix}font-delivery.json"
        font_command = [sys.executable, "-I", "-S", "-B", str(SCRIPTS / "font_audit.py"), str(project)]
        try:
            font_run = subprocess.run(font_command, cwd=str(project), capture_output=True,
                                      text=True, encoding="utf-8", errors="replace", timeout=90)
            font_payload = json.loads(font_run.stdout)
            font_record.write_text(json.dumps(font_payload, indent=2) + "\n", encoding="utf-8")
            font_findings = [item for item in font_payload.get("findings", [])
                             if item.get("severity") in {"high", "medium"}]
            font_ok = (font_run.returncode == 0 and font_payload.get("source_integrity_complete") is True and not font_findings)
            step("font-delivery", font_ok, "font inventory, delivery and bound provenance contain no unresolved errors"
                 if font_ok else json.dumps(font_findings or font_payload, ensure_ascii=False), font_command,
                 font_record, findings=font_findings)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            step("font-delivery", False, f"font delivery audit failed: {exc}", font_command)

    if not reasons and manifest is not None:
        cmd = ["--manifest", str(manifest_path), "--build-id", args.build_id, "--run-id", run_id, "--out", str(census)]
        for route in active_routes:
            cmd += ["--route-key", route["key"]]
        cmd += browser
        if args.phase == "first-screen":
            cmd += ["--first-screen"]
        code, so, se = run_node(SCRIPTS / "scan_build_components.mjs", cmd, project)
        payload = last_json(so) or {}
        if census.is_file():
            try:
                aggregate_served_identities.append(("census", json.loads(census.read_text(encoding="utf-8")).get("served_content_identity")))
            except (OSError, ValueError):
                pass
        identity_ok, identity_note = record_identity_ok(
            census,
            SCRIPTS / "scan_build_components.mjs",
            args.build_id,
            run_id,
            manifest["manifest_id"],
            manifest_sha256,
            active_routes,
            manifest["viewports"],
            expected_first_screen=args.phase == "first-screen",
        )
        frames_ok, frames_note = (
            bind_generated_interaction_frames(census, payload, kind="census-interaction-frame")
            if census.is_file() and isinstance(payload, dict)
            else (False, "census interaction frames unavailable")
        )
        ok = code == 0 and census.is_file() and bool(payload.get("ok", True)) and identity_ok and frames_ok
        step("census", ok, str(payload.get("verdict") or (so or se).strip()[-400:] or f"exit {code}"),
             ["node", "scan_build_components.mjs", *cmd], census, identity=identity_note,
             interaction_frames=frames_note)
        if census.is_file() and isinstance(visible_decision_payload, dict):
            content_module = validator_module.load_bundled_source_module("_design_dna_content_transfer", SCRIPTS / "content_transfer.py")
            content_failures = content_module.content_transfer_failures(project, visible_decision_payload,
                json.loads(census.read_text(encoding="utf-8")))
            step("content-transfer", not content_failures, "rendered project copy, source roles, line rhythm and section connections match pre-code authority"
                 if not content_failures else " | ".join(content_failures), failures=content_failures,
                 record=resolve_project_path(project, visible_decision_payload["content_transfer"]["path"])
                 if isinstance(visible_decision_payload.get("content_transfer"), dict) else None)

        for route in active_routes:
            for viewport in manifest["viewports"]:
                record_id = f"build-{prefix}{route['key']}-{viewport['name']}"
                out = phase_evidence / f"{record_id}-styles.json"
                cmd = [
                    "--url", route["url"], "--id", record_id, "--out", str(phase_evidence),
                    "--width", str(viewport["width"]), "--height", str(viewport["height"]),
                    "--route-key", route["key"], "--viewport", viewport["name"],
                    "--build-id", args.build_id,
                    "--run-id", run_id,
                    *manifest_binding_args,
                ]
                if args.phase == "first-screen":
                    cmd += ["--holds", "0", "--first-screen"]
                cmd += browser
                code, so, se = run_node(SCRIPTS / "extract_reference_styles.mjs", cmd, project)
                payload = last_json(so) or {}
                identity_ok, identity_note = record_identity_ok(out, SCRIPTS / "extract_reference_styles.mjs", args.build_id, run_id, manifest["manifest_id"], manifest_sha256, [route], [viewport])
                ok = code == 0 and out.is_file() and identity_ok
                step(f"extract:{route['key']}:{viewport['name']}", ok,
                     str(payload.get("verdict") or (so or se).strip()[-400:] or f"exit {code}"),
                     ["node", "extract_reference_styles.mjs", *cmd], out,
                     route_key=route["key"], viewport=viewport["name"], identity=identity_note)
                if ok:
                    build_styles.append(out)

    if not reasons and manifest is not None:
        cmd: list[str] = []
        for file in build_styles:
            cmd += ["--build", str(file)]
        trace_ranks = sorted({route["mapped_reference_rank"] for route in active_routes}) if args.phase == "first-screen" else ranks
        for rank in trace_ranks:
            cmd += ["--reference", str(references / f"strong-{rank}-styles.json")]
        for substitute in args.substitute:
            cmd += ["--substitute", substitute]
        if args.match:
            cmd += ["--match", args.match]
        for route in active_routes:
            cmd += ["--route-key", route["key"]]
        if args.phase == "first-screen":
            cmd += ["--first-screen"]
        cmd += ["--build-id", args.build_id, "--run-id", run_id, *manifest_binding_args, "--out", str(provenance)]
        code, so, se = run_node(SCRIPTS / "check_style_provenance.mjs", cmd, project)
        payload = last_json(so) or {}
        if provenance.is_file():
            try:
                aggregate_served_identities.append(("provenance", json.loads(provenance.read_text(encoding="utf-8")).get("served_content_identity")))
            except (OSError, ValueError):
                pass
        identity_ok, identity_note = record_identity_ok(provenance, SCRIPTS / "check_style_provenance.mjs", args.build_id, run_id, manifest["manifest_id"], manifest_sha256, active_routes, manifest["viewports"])
        ok = bool(payload.get("ok")) and code == 0 and identity_ok
        step("provenance", ok, str(payload.get("verdict") or (payload.get("error") or {}).get("message") or se[-400:] or f"exit {code}"),
             ["node", "check_style_provenance.mjs", *cmd], provenance, identity=identity_note)

        cmd = ["--manifest", str(manifest_path), "--census", str(census)]
        for route in active_routes:
            cmd += ["--route-key", route["key"]]
        for rank in ranks:
            for suffix in ("", "-inner"):
                observation = references / f"strong-{rank}{suffix}-observation.json"
                if observation.is_file():
                    cmd += ["--reference", str(observation)]
        cmd += ["--build-id", args.build_id, "--run-id", run_id, "--out", str(structure), *browser]
        code, so, se = run_node(SCRIPTS / "compare_structure.mjs", cmd, project)
        payload = last_json(so) or {}
        if structure.is_file():
            try:
                aggregate_served_identities.append(("structure", json.loads(structure.read_text(encoding="utf-8")).get("served_content_identity")))
            except (OSError, ValueError):
                pass
        identity_ok, identity_note = record_identity_ok(structure, SCRIPTS / "compare_structure.mjs", args.build_id, run_id, manifest["manifest_id"], manifest_sha256, active_routes, manifest["viewports"])
        ok = bool(payload.get("pass")) and code == 0 and identity_ok
        step("structure", ok, str(payload.get("verdict") or (payload.get("error") or {}).get("message") or se[-400:] or f"exit {code}"),
             ["node", "compare_structure.mjs", *cmd], structure, identity=identity_note)

        cmd = ["--manifest", str(manifest_path)]
        for route in active_routes:
            cmd += ["--route-key", route["key"]]
        if args.phase == "first-screen":
            cmd += ["--first-screen"]
        for rank in ranks:
            cmd += ["--source", str(references / f"strong-{rank}-observation.json")]
        cmd += ["--build-id", args.build_id, "--run-id", run_id, "--out", str(mechanisms), *browser]
        code, so, se = run_node(SCRIPTS / "compare_mechanisms.mjs", cmd, project)
        payload = last_json(so) or {}
        if mechanisms.is_file():
            try:
                aggregate_served_identities.append(("mechanisms", json.loads(mechanisms.read_text(encoding="utf-8")).get("served_content_identity")))
            except (OSError, ValueError):
                pass
        identity_ok, identity_note = record_identity_ok(mechanisms, SCRIPTS / "compare_mechanisms.mjs", args.build_id, run_id, manifest["manifest_id"], manifest_sha256, active_routes, manifest["viewports"])
        frames_ok, frames_note = (
            bind_generated_interaction_frames(mechanisms, payload, kind="mechanism-interaction-frame")
            if mechanisms.is_file() and isinstance(payload, dict)
            else (False, "mechanism interaction frames unavailable")
        )
        transfer_failures = (
            validator_module.mechanism_interaction_transfer_failures(
                payload,
                project=project,
                expected_routes=active_routes,
                expected_viewports=manifest["viewports"],
                first_screen=args.phase == "first-screen",
                record_path=mechanisms,
            )
            if validator_module is not None
            and hasattr(validator_module, "mechanism_interaction_transfer_failures")
            and mechanisms.is_file()
            else ["mechanism interaction-transfer validator unavailable"]
        )
        ok = (
            bool(payload.get("pass"))
            and code == 0
            and identity_ok
            and frames_ok
            and not transfer_failures
        )
        mechanism_verdict = (
            " | ".join(transfer_failures[:6])
            if transfer_failures
            else str(payload.get("verdict") or (payload.get("error") or {}).get("message") or se[-400:] or f"exit {code}")
        )
        step("mechanisms", ok, mechanism_verdict,
             ["node", "compare_mechanisms.mjs", *cmd], mechanisms, identity=identity_note,
             interaction_frames=frames_note,
             interaction_transfer=("complete" if not transfer_failures else " | ".join(transfer_failures[:4])))

        cmd = [
            "--dossier", str(dossier), "--mechanism-diff", str(mechanisms),
            "--structure-diff", str(structure), "--style-provenance", str(provenance),
            "--census", str(census), "--build-id", args.build_id,
            "--run-id", run_id,
            *manifest_binding_args,
        ]
        if args.phase == "first-screen":
            cmd += ["--only-rank", str(active_routes[0]["mapped_reference_rank"])]
        for rank in ranks_all:
            cmd += ["--observation", str(references / f"strong-{rank}-observation.json")]
        cmd += ["--out", str(signature)]
        code, so, se = run_node(SCRIPTS / "check_signature_transfer.mjs", cmd, project)
        payload = last_json(so) or {}
        if signature.is_file():
            try:
                aggregate_served_identities.append(("signature-transfer", json.loads(signature.read_text(encoding="utf-8")).get("served_content_identity")))
            except (OSError, ValueError):
                pass
        identity_ok, identity_note = record_identity_ok(signature, SCRIPTS / "check_signature_transfer.mjs", args.build_id, run_id, manifest["manifest_id"], manifest_sha256, active_routes, manifest["viewports"])
        ok = bool(payload.get("pass")) and code == 0 and identity_ok
        step("signature-transfer", ok, str(payload.get("verdict") or (payload.get("error") or {}).get("message") or se[-400:] or f"exit {code}"),
             ["node", "check_signature_transfer.mjs", *cmd], signature, identity=identity_note)

        served_hashes = {
            identity.get("sha256")
            for _name, identity in aggregate_served_identities
            if isinstance(identity, dict)
        }
        step(
            "served-content-consensus",
            len(aggregate_served_identities) == 5 and len(served_hashes) == 1,
            "all direct aggregate checks bind one served-content identity"
            if len(aggregate_served_identities) == 5 and len(served_hashes) == 1
            else "direct aggregate checks disagree on served response bytes",
        )

        if args.phase in {"final", "maintenance"}:
            digests = {entry["path"]: entry["sha256"] for entry in evidence_hashes if entry["path"].startswith(".design-dna/")}
            body = dossier.read_text(encoding="utf-8", errors="replace")
            candidate_dossier, rebound = rebind_dossier(body, digests)
            validator = load_validator()
            if validator is None or not hasattr(validator, "reference_dossier_failures"):
                step("dossier", False, "the packaged validator could not be loaded")
            else:
                failures = validator.reference_dossier_failures(candidate_dossier, project=project, record_path=dossier)
                step("dossier", not failures,
                     "0 failures" if not failures else f"{len(failures)} failure(s): " + " | ".join(failures), failures=failures)
        else:
            step("dossier-binding", dossier.is_file(),
                 "normalized dossier core bound for prebuild; circular gate line excluded")

    if args.phase == "maintenance" and validator_module is not None and isinstance(visible_decision_payload, dict):
        workflow = validator_module.load_bundled_source_module("_design_dna_maintenance_workflow", SCRIPTS / "maintenance_workflow.py")
        maintenance_failures = workflow.check(project, visible_decision_payload, validator_module, current_scan=census, final=True)
        step("maintenance-complete-delta", not maintenance_failures,
             "the exact scoped delta and its new full census are verified" if not maintenance_failures else " | ".join(maintenance_failures),
             failures=maintenance_failures)
    build_after = tree_identity(project)
    build_stable = build_before == build_after
    step("build-stability", build_stable,
         "build input tree stayed byte-identical" if build_stable else
         "build input tree changed while the gate was running; evidence spans different builds")
    runtime_after = runtime_identity()
    step(
        "runtime-stability",
        runtime_before == runtime_after,
        "packaged runtime stayed byte-identical" if runtime_before == runtime_after else
        "packaged runtime changed while the gate was running",
    )

    passed = not reasons
    if passed and candidate_dossier is not None and candidate_dossier != dossier.read_text(encoding="utf-8", errors="replace"):
        dossier.write_text(candidate_dossier, encoding="utf-8")

    coverage_matrix = []
    if manifest:
        for route in active_routes:
            for viewport in manifest["viewports"]:
                coverage_matrix.append({
                    "route_key": route["key"], "url": route["url"],
                    "mapped_reference_rank": route["mapped_reference_rank"],
                    "mapped_reference_id": route["mapped_reference_id"],
                    "mapped_reference_observation": route["mapped_reference_observation"],
                    "mapped_reference_sha256": route["mapped_reference_sha256"],
                    "viewport": viewport["name"], "width": viewport["width"], "height": viewport["height"],
                    "states": route["states"],
                })
    verdict = (
        f"GATE PASS: {args.phase} {len(steps)} checks passed for build {args.build_id} across {len(coverage_matrix)} route/viewport cells."
        if passed else "GATE FAIL: " + " || ".join(reasons)
    )
    served_content_identity = next(
        (
            identity
            for name, identity in reversed(aggregate_served_identities)
            if name == "signature-transfer" and isinstance(identity, dict)
        ),
        None,
    )
    record = {
        "tool": TOOL_NAME,
        "schema_version": SCHEMA_VERSION,
        "producer_script_sha256": sha256_of(Path(__file__).resolve()),
        "runtime_identity": runtime_after,
        "checked_at": checked_at,
        "project": str(project),
        "project_identity": {"root": str(project)},
        "build_id": args.build_id,
        "run_id": run_id,
        "phase": args.phase,
        "route_key": args.route_key,
        "build_tree_sha256_before": build_before,
        "build_tree_sha256_after": build_after,
        "build_stable": build_stable,
        "route_manifest": str(manifest_path),
        "route_manifest_sha256": sha256_of(manifest_path) if manifest_path.is_file() else None,
        "manifest_snapshot": (
            {
                "path": manifest_snapshot.relative_to(project).as_posix(),
                "sha256": sha256_of(manifest_snapshot),
            }
            if manifest_snapshot is not None
            else None
        ),
        "manifest_id": manifest.get("manifest_id") if manifest else None,
        "visible_decision_source_manifest": (
            {
                "path": ".design-dna/visible-decision-sources.json",
                "sha256": visible_decision_sha256,
            }
            if visible_decision_sha256
            else None
        ),
        "construction_authorization": (
            visible_decision_payload.get("construction_authorization")
            if isinstance(visible_decision_payload, dict)
            else None
        ),
        "visible_decision_snapshot": (
            {
                "path": visible_decision_snapshot.relative_to(project).as_posix(),
                "sha256": sha256_of(visible_decision_snapshot),
            }
            if visible_decision_snapshot is not None
            else None
        ),
        "dossier": str(dossier),
        "dossier_sha256": sha256_of(dossier) if dossier.is_file() else None,
        "dossier_core_sha256": dossier_core,
        "dossier_snapshot": (
            {
                "path": dossier_snapshot.relative_to(project).as_posix(),
                "sha256": sha256_of(dossier_snapshot),
            }
            if dossier_snapshot is not None
            else None
        ),
        "authorization_id": authorization_id,
        "authorization_path": (
            str(authorization_path.relative_to(project)).replace(os.sep, "/")
            if authorization_path and authorization_path.is_relative_to(project)
            else str(authorization_path) if authorization_path else None
        ),
        "prebuild_authorization": (
            {
                "path": str(authorization_path.relative_to(project)).replace(os.sep, "/"),
                "sha256": authorization_sha256,
                "authorization_id": authorization_payload.get("authorization_id"),
                "proof_build_id": authorization_payload.get("proof_build_id"),
                "proof_tree_sha256": authorization_payload.get("proof_tree_sha256"),
                "authorized_at": authorization_payload.get("authorized_at"),
            }
            if authorization_path and authorization_payload and authorization_sha256
            else None
        ),
        "routes": active_routes,
        "planned_routes": manifest["routes"] if manifest else [],
        "viewports_checked": manifest["viewports"] if manifest else [],
        "states_checked": sorted({state["id"] for route in active_routes for state in route["states"]}),
        "coverage_matrix": coverage_matrix,
        "served_content_identity": served_content_identity,
        "evidence_hashes": evidence_hashes,
        "substitutes": args.substitute,
        "match": args.match,
        "rebound": sorted(set(rebound)) if passed else [],
        "steps": steps,
        "failures": list(reasons),
        "delivery_status": "gate-passed" if passed else "blocked",
        "scoped_change_verified": passed and args.phase == "maintenance",
        "new_site_approval": False,
        "deliverable_link_allowed": passed and args.phase == "final",
        "pass": passed,
        "verdict": verdict,
        "owner_order": "The producer's own design is forbidden in every part. A build without this exact passing gate record is not delivered.",
    }
    gate_file = evidence / ("first-screen-gate.json" if args.phase == "first-screen" else "maintenance-gate.json" if args.phase == "maintenance" else "gate.json")
    immutable_gate_file = (
        phase_evidence / "gate.json"
        if args.phase == "first-screen"
        else evidence / "gate-runs" / run_id / "gate.json"
    )
    immutable_gate_file.parent.mkdir(parents=True, exist_ok=True)
    gate_bytes = json.dumps(record, indent=2) + "\n"
    with immutable_gate_file.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(gate_bytes)
    gate_file.write_text(gate_bytes, encoding="utf-8")
    if passed and args.phase == "first-screen":
        try:
            write_prebuild_authorization(
                validator=validator_module,
                project=project,
                path=authorization_path,
                authorization_id=authorization_id,
                checked_at=checked_at,
                gate_file=immutable_gate_file,
                manifest=manifest,
                manifest_sha256=manifest_sha256,
                route_key=args.route_key,
                build_id=args.build_id,
                tree_sha256=build_after,
                dossier_core_sha256=dossier_core,
                visible_decision_sha256=visible_decision_sha256,
                visible_decision_snapshot=visible_decision_snapshot,
            )
        except Exception as exc:
            passed = False
            failure = f"authorization-write: {exc}"
            reasons.append(failure)
            record["pass"] = False
            record["verdict"] = "GATE FAIL: " + " || ".join(reasons)
            record["steps"].append({"name": "authorization-write", "pass": False, "verdict": str(exc)})
            gate_bytes = json.dumps(record, indent=2) + "\n"
            immutable_gate_file.write_text(gate_bytes, encoding="utf-8")
            gate_file.write_text(gate_bytes, encoding="utf-8")
    if passed and args.phase != "maintenance" and isinstance(visible_decision_payload, dict):
        try:
            if validator_module is None or not hasattr(validator_module, "append_construction_journal_entry"):
                raise RuntimeError("the packaged construction journal appender is unavailable")
            journal_action = validator_module.append_construction_journal_entry(
                project,
                entry_kind=("first-screen-authorized" if args.phase == "first-screen" else "final-freeze"),
                manifest_path=manifest_path,
                dossier_path=dossier,
                visible_payload=visible_decision_payload,
            )
        except Exception as exc:
            passed = False
            failure = f"construction-journal-write: {exc}"
            reasons.append(failure)
            record["pass"] = False
            record["verdict"] = "GATE FAIL: " + " || ".join(reasons)
            gate_bytes = json.dumps(record, indent=2) + "\n"
            immutable_gate_file.write_text(gate_bytes, encoding="utf-8")
            gate_file.write_text(gate_bytes, encoding="utf-8")
    record["failures"] = list(reasons)
    record["delivery_status"] = "gate-passed" if passed else "blocked"
    record["deliverable_link_allowed"] = passed and args.phase == "final"
    record["scoped_change_verified"] = passed and args.phase == "maintenance"
    if not passed and validator_module is not None:
        # Keep the final failure disposition and its inventory immutable.
        gate_bytes = json.dumps(record, indent=2) + "\n"
        immutable_gate_file.write_text(gate_bytes, encoding="utf-8")
        gate_file.write_text(gate_bytes, encoding="utf-8")
        try:
            controls = validator_module.load_bundled_source_module("_design_dna_implementation_control", SCRIPTS / "implementation_control.py")
            controls.write_prohibition(project, immutable_gate_file, record, validator_module)
        except Exception as exc:
            print(f"implementation-prohibition-write failed; build remains blocked: {exc}", file=sys.stderr)
    print(record["verdict"])
    print(f"record: {gate_file.relative_to(project)} sha256:{sha256_of(gate_file)}")
    if passed and args.phase == "first-screen":
        print(f"immutable gate: {immutable_gate_file.relative_to(project)} sha256:{sha256_of(immutable_gate_file)}")
        print(f"authorization: {authorization_path.relative_to(project)} sha256:{sha256_of(authorization_path)}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
