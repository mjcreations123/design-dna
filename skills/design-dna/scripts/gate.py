#!/usr/bin/env python3
"""gate.py: every gate, one command, one verdict.

Why this exists. The gates were all here, and a build shipped without any of
them because running five scripts and writing a dossier felt too slow for
"just a quick test". The result carried the producer's own nav, typefaces,
palette, cards and accordion. The owner's words that day (2026-09-03):

    "Your own designs is absolutely forbidden ... There is absolutely no using
    your design. You must only use the designs from the websites you are
    copying from. And this includes designs, layouts, fonts, and everything
    else."

A gate the producer can skip is a suggestion. This script makes the whole
gate one command whose verdict line the final report to the owner must quote
verbatim, so that skipping it becomes a stated falsehood rather than a quiet
omission.

It runs, in order, against the running build:
  1. extract_reference_styles.mjs on every route   -> evidence/build-<route>-styles.json
  2. scan_build_components.mjs on every route       -> evidence/component-census.json
  3. check_style_provenance.mjs                     -> evidence/style-provenance.json
  4. compare_structure.mjs                          -> evidence/structure-diff.json
  5. compare_mechanisms.mjs on the first route      -> evidence/mechanism-diff.json
  6. check_signature_transfer.mjs                   -> evidence/signature-transfer.json
  7. the reference-dossier validator (init_project_state.reference_dossier_failures)
and writes evidence/gate.json with one verdict.

Usage:
  python gate.py --url http://127.0.0.1:4830/ --url http://127.0.0.1:4830/shop.html \
      [--substitute "Louize Display=Cormorant Garamond"]... \
      [--match .design-dna/evidence/typeface-match.json] \
      [--browser-executable FILE] [--project DIR] [--skip-extract] [--dry-run]

Requires Python 3.10+, node on PATH, and the skill's Playwright setup
(DESIGN_DNA_PLAYWRIGHT_MODULE_DIR) for the browser-driven steps.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOL_NAME = "gate.py"
SCHEMA_VERSION = 1
SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def route_slug(url: str) -> str:
    tail = re.sub(r"[?#].*$", "", url).rstrip("/").split("/")[-1]
    tail = re.sub(r"\.html?$", "", tail) or "index"
    tail = re.sub(r"[^a-z0-9]+", "-", tail.lower()).strip("-") or "index"
    return tail


def selected_ranks(dossier: Path) -> list[int]:
    """The ranks the dossier selects; every strong rank when it does not say."""
    if not dossier.is_file():
        return []
    text = dossier.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^-\s+Selected positive ranks[^:]*:\s*([\d,\s]+)$", text, re.M)
    if not match:
        return []
    ranks = []
    for item in match.group(1).split(","):
        item = item.strip()
        if item.isdigit():
            ranks.append(int(item))
    return sorted(set(ranks))


def strong_ranks(references: Path) -> list[int]:
    ranks = set()
    for file in references.glob("strong-*-observation.json"):
        match = re.match(r"strong-(\d+)-observation\.json$", file.name)
        if match:
            ranks.add(int(match.group(1)))
    return sorted(ranks)


def run_node(script: Path, args: list[str], cwd: Path) -> tuple[int, str, str]:
    env = dict(os.environ)
    env.setdefault("MSYS_NO_PATHCONV", "1")
    proc = subprocess.run(
        ["node", str(script), *args],
        cwd=str(cwd), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def last_json(text: str) -> dict | None:
    """The scripts print one JSON object last; find it."""
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


BINDING = re.compile(r"(?P<path>\.design-dna/[^\s|`]+?)(?P<sep>\s+(?:plus\s+)?sha256:)(?P<hex>[0-9a-f]{64})", re.IGNORECASE)


def rebind_dossier(text: str, digests: dict[str, str]) -> tuple[str, list[str]]:
    """Refresh the SHA-256 the dossier binds for records the gate just wrote.

    A dossier binds the exact bytes of each evidence record, and every gate
    run rewrites those records (they carry timestamps), so the run that
    produces the final records is also the run that has to rebind them. Only
    a path the dossier already binds AND the gate just produced is touched;
    nothing is added, and a record the gate did not write is left alone.
    """
    rebound: list[str] = []

    def swap(match: re.Match) -> str:
        path = match.group("path").replace("\\", "/")
        digest = digests.get(path)
        if not digest or digest == match.group("hex"):
            return match.group(0)
        rebound.append(path)
        return f"{match.group('path')}{match.group('sep')}{digest}"

    return BINDING.sub(swap, text), rebound


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "design_dna_gate_validator", SCRIPTS / "init_project_state.py"
    )
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(prog="gate.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--url", action="append", default=[], help="a route of the running build; repeat per route")
    parser.add_argument("--substitute", action="append", default=[], help="FROM=TO, a declared typeface substitute (needs --match)")
    parser.add_argument("--match", default=None, help="typeface-match.json from match_typeface.mjs")
    parser.add_argument("--browser-executable", default=None)
    parser.add_argument("--project", default=".", help="project root holding .design-dna/")
    parser.add_argument("--skip-extract", action="store_true", help="reuse existing build-*-styles.json and component-census.json")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and the inputs found, run nothing")
    parser.add_argument("--no-rebind", action="store_true", help="do not refresh the dossier's SHA-256 bindings for the records this run wrote")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    dna = project / ".design-dna"
    references = dna / "references"
    evidence = dna / "evidence"
    dossier = dna / "reference-dossier.md"
    evidence.mkdir(parents=True, exist_ok=True)

    steps: list[dict] = []
    reasons: list[str] = []

    def step(name: str, ok: bool, verdict: str, command: list[str] | None = None, record: Path | None = None) -> None:
        entry = {"name": name, "pass": bool(ok), "verdict": verdict}
        if command:
            entry["command"] = " ".join(command)
        if record and record.is_file():
            entry["record"] = str(record.relative_to(project)).replace(os.sep, "/")
            entry["sha256"] = sha256_of(record)
        steps.append(entry)
        if not ok:
            reasons.append(f"{name}: {verdict}")

    ranks_all = strong_ranks(references)
    ranks = selected_ranks(dossier) or ranks_all
    if not ranks_all:
        step("references", False, "no strong-N-observation.json under .design-dna/references; nothing to trace to. Record the references first.")
    else:
        missing_styles = [r for r in ranks if not (references / f"strong-{r}-styles.json").is_file()]
        if missing_styles:
            step("references", False, "selected rank(s) without a measured styles record (extract_reference_styles.mjs): " + ", ".join(f"strong-{r}" for r in missing_styles))
        else:
            step("references", True, f"strong ranks {ranks_all}; selected {ranks}")
    if not dossier.is_file():
        step("dossier-present", False, "no .design-dna/reference-dossier.md; a build with no dossier has no sources.")

    if args.substitute and not args.match:
        default_match = evidence / "typeface-match.json"
        if default_match.is_file():
            args.match = str(default_match)
        else:
            step("typeface-match", False, "--substitute given without a match_typeface.mjs record; the producer does not choose faces. Run match_typeface.mjs and pass --match.")

    if not args.url and not args.dry_run:
        step("routes", False, "no --url; pass every route of the running build.")

    if args.dry_run:
        plan = {
            "project": str(project), "routes": args.url, "ranks": ranks, "ranks_all": ranks_all,
            "dossier": dossier.is_file(), "substitutes": args.substitute, "match": args.match,
            "steps_so_far": steps,
        }
        print(json.dumps(plan, indent=2))
        return 0 if not reasons else 1

    browser = ["--browser-executable", args.browser_executable] if args.browser_executable else []
    rebound: list[str] = []
    build_styles: list[Path] = []
    census = evidence / "component-census.json"

    if not reasons:
        # 1. build styles per route
        for url in args.url:
            slug = route_slug(url)
            out = evidence / f"build-{slug}-styles.json"
            if args.skip_extract and out.is_file():
                build_styles.append(out)
                step(f"extract:{slug}", True, "reused the existing record (--skip-extract)", record=out)
                continue
            cmd = ["--url", url, "--id", f"build-{slug}", "--out", str(evidence), *browser]
            code, so, se = run_node(SCRIPTS / "extract_reference_styles.mjs", cmd, project)
            ok = code == 0 and out.is_file()
            step(f"extract:{slug}", ok, (so.strip().splitlines() or [se.strip()[-300:]])[-1] if (so or se) else f"exit {code}", ["node", "extract_reference_styles.mjs", *cmd], out)
            if ok:
                build_styles.append(out)

        # 2. census
        if args.skip_extract and census.is_file():
            step("census", True, "reused the existing census (--skip-extract)", record=census)
        else:
            cmd = [*sum([["--url", u] for u in args.url], []), "--out", str(census), *browser]
            code, so, se = run_node(SCRIPTS / "scan_build_components.mjs", cmd, project)
            step("census", code == 0 and census.is_file(), (so.strip().splitlines() or [se.strip()[-300:]])[-1] if (so or se) else f"exit {code}", ["node", "scan_build_components.mjs", *cmd], census)

    if not reasons:
        # 3. provenance
        out = evidence / "style-provenance.json"
        cmd = []
        for b in build_styles:
            cmd += ["--build", str(b)]
        for r in ranks:
            cmd += ["--reference", str(references / f"strong-{r}-styles.json")]
        for s in args.substitute:
            cmd += ["--substitute", s]
        if args.match:
            cmd += ["--match", args.match]
        cmd += ["--out", str(out)]
        code, so, se = run_node(SCRIPTS / "check_style_provenance.mjs", cmd, project)
        payload = last_json(so) or {}
        ok = bool(payload.get("ok")) and code == 0
        verdict = payload.get("verdict") or (payload.get("error") or {}).get("message") or se.strip()[-300:] or f"exit {code}"
        step("provenance", ok, str(verdict), ["node", "check_style_provenance.mjs", *cmd], out)

        # 4. structure
        out = evidence / "structure-diff.json"
        cmd = ["--census", str(census)]
        for r in ranks:
            for suffix in ("", "-inner"):
                obs = references / f"strong-{r}{suffix}-observation.json"
                if obs.is_file():
                    cmd += ["--reference", str(obs)]
        cmd += ["--out", str(out), *browser]
        code, so, se = run_node(SCRIPTS / "compare_structure.mjs", cmd, project)
        payload = last_json(so) or {}
        ok = bool(payload.get("pass")) and code == 0
        step("structure", ok, str(payload.get("verdict") or (payload.get("error") or {}).get("message") or se.strip()[-300:] or f"exit {code}"), ["node", "compare_structure.mjs", *cmd], out)

        # 5. mechanisms, on the first route
        out = evidence / "mechanism-diff.json"
        cmd = ["--url", args.url[0]]
        for r in ranks:
            cmd += ["--source", str(references / f"strong-{r}-observation.json")]
        cmd += ["--out", str(out), *browser]
        code, so, se = run_node(SCRIPTS / "compare_mechanisms.mjs", cmd, project)
        payload = last_json(so) or {}
        ok = bool(payload.get("pass")) and code == 0
        step("mechanisms", ok, str(payload.get("verdict") or (payload.get("error") or {}).get("message") or se.strip()[-300:] or f"exit {code}"), ["node", "compare_mechanisms.mjs", *cmd], out)

        # 6. signature transfer
        out = evidence / "signature-transfer.json"
        cmd = ["--dossier", str(dossier)]
        for r in ranks_all:
            cmd += ["--observation", str(references / f"strong-{r}-observation.json")]
        cmd += ["--out", str(out)]
        code, so, se = run_node(SCRIPTS / "check_signature_transfer.mjs", cmd, project)
        payload = last_json(so) or {}
        ok = bool(payload.get("pass")) and code == 0
        step("signature-transfer", ok, str(payload.get("verdict") or (payload.get("error") or {}).get("message") or se.strip()[-300:] or f"exit {code}"), ["node", "check_signature_transfer.mjs", *cmd], out)

        # 7. the dossier itself, rebound to the records this run wrote
        rebound: list[str] = []
        if not args.no_rebind and dossier.is_file():
            digests = {}
            for entry in steps:
                if entry.get("record") and entry.get("sha256"):
                    digests[entry["record"]] = entry["sha256"]
            body = dossier.read_text(encoding="utf-8", errors="replace")
            new_body, rebound = rebind_dossier(body, digests)
            if rebound:
                dossier.write_text(new_body, encoding="utf-8")
            rebound = sorted(set(rebound))
        validator = load_validator()
        if validator is None or not hasattr(validator, "reference_dossier_failures"):
            step("dossier", False, "the packaged validator could not be loaded")
        else:
            body = dossier.read_text(encoding="utf-8", errors="replace")
            failures = validator.reference_dossier_failures(body, project=project, record_path=dossier)
            note = f"rebound {len(rebound)} record binding(s); " if rebound else ""
            step("dossier", not failures, note + ("0 failures" if not failures else f"{len(failures)} failure(s): " + " | ".join(failures[:6])), record=dossier)

    passed = not reasons
    verdict = (
        f"GATE PASS: {len(steps)} checks passed on {len(args.url)} route(s) against ranks {ranks}."
        if passed
        else "GATE FAIL: " + " || ".join(reasons[:8])
    )
    record = {
        "tool": TOOL_NAME,
        "schema_version": SCHEMA_VERSION,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "project": str(project),
        "routes": args.url,
        "ranks": ranks,
        "substitutes": args.substitute,
        "match": args.match,
        "rebound": rebound,
        "steps": steps,
        "pass": passed,
        "verdict": verdict,
        "owner_order": "The producer's own design is forbidden in every part (Motty, 2026-09-03). A build without a passing gate record is not this skill's output and is not delivered.",
    }
    gate_file = evidence / "gate.json"
    gate_file.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(verdict)
    print(f"record: {gate_file.relative_to(project)} sha256:{sha256_of(gate_file)}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
