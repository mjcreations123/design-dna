"""Validate supplementary generated gate artifacts without widening evidence paths."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys


def content_artifact_path(mapping: object) -> str | None:
    binding = mapping.get("content_transfer") if isinstance(mapping, dict) else None
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
        return None
    path, digest = binding.get("path"), binding.get("sha256")
    if (isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)
        and path in {".design-dna/content-transfer.json", f".design-dna/content-transfers/{digest}.json"}):
        return path
    return None


def font_report_failures(payload: object, *, project: Path | None = None, rerun_current: bool = False) -> list[str]:
    """Validate the actual font audit shape and, for current builds, rerun it."""
    if not isinstance(payload, dict):
        return ["Font delivery artifact must contain the complete packaged audit."]
    findings = payload.get("findings")
    completeness = payload.get("completeness")
    scope = payload.get("scan_scope")
    failures = []
    if (payload.get("schema_version") != 2 or payload.get("artifact_type") != "design-dna-font-audit"
        or payload.get("ok") is not True or payload.get("execution_ok") is not True
        or payload.get("execution") != {"status": "succeeded", "ok": True}
        or payload.get("source_integrity_complete") is not True or payload.get("exit_code") != 0
        or not isinstance(completeness, dict) or completeness.get("complete") is not True
        or completeness.get("status") != "complete" or completeness.get("budget_exceeded") != []
        or completeness.get("skipped_source_count") != 0 or completeness.get("skipped_font_count") != 0
        or payload.get("skipped_sources") != [] or payload.get("skipped_font_binaries") != []
        or not isinstance(scope, dict) or not isinstance(findings, list)):
        failures.append("Font delivery artifact is malformed, incomplete or did not finish the packaged source audit.")
    if isinstance(scope, dict):
        counts = ("source_file_count", "scanned_source_file_count", "skipped_source_file_count", "font_binary_count", "skipped_font_binary_count", "eligible_file_count")
        if any(type(scope.get(key)) is not int or scope[key] < 0 for key in counts):
            failures.append("Font delivery scan counts are missing or malformed.")
        elif (scope["source_file_count"] != scope["scanned_source_file_count"] or scope["skipped_source_file_count"]
              or scope["skipped_font_binary_count"] or scope["eligible_file_count"] != scope["source_file_count"] + scope["font_binary_count"]):
            failures.append("Font delivery scan counts hide unscanned sources or font files.")
    for key in ("font_binaries", "font_faces", "preloads", "delivery_contracts", "declared_stacks", "declared_weights"):
        if not isinstance(payload.get(key), list):
            failures.append(f"Font delivery artifact omits its actual {key} inventory.")
    if isinstance(findings, list):
        if any(not isinstance(row, dict) or row.get("severity") not in {"high", "medium", "low", "info"} for row in findings):
            failures.append("Font delivery findings are malformed.")
        if any(isinstance(row, dict) and row.get("severity") in {"high", "medium"} for row in findings):
            failures.append("Font delivery has unresolved source, licensing, or delivery findings.")
    if rerun_current and not failures:
        if project is None:
            return ["Current font verification requires the exact project root."]
        try:
            run = subprocess.run([sys.executable, "-I", "-S", "-B", str(Path(__file__).with_name("font_audit.py")), str(project)],
                capture_output=True, text=True, encoding="utf-8", errors="strict", timeout=90)
            current = json.loads(run.stdout)
            if run.returncode != 0:
                failures.append("Current font audit no longer succeeds.")
            # Elapsed runtime is observational, not part of the source result.
            stable = lambda value: {key: item for key, item in value.items() if key != "resource_usage"}
            if not isinstance(current, dict) or stable(current) != stable(payload):
                failures.append("Font delivery artifact differs from a fresh audit of the exact current project.")
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            failures.append("Current font audit could not be revalidated: " + str(exc))
    return failures


def rendered_font_failures(payload: object) -> list[str]:
    """Require typed per-component glyph evidence, not truthy pass markers."""
    if not isinstance(payload, dict) or set(payload) != {"complete", "findings", "records"} or payload.get("complete") is not True or payload.get("findings") != [] or not isinstance(payload.get("records"), list):
        return ["Rendered font evidence is missing, malformed, or incomplete."]
    failures = []
    normalize = lambda value: " ".join(value.casefold().strip().split())
    generic = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-serif", "ui-sans-serif", "ui-monospace", "ui-rounded", "-apple-system", "blinkmacsystemfont"}
    fields = {"component_id", "selector", "declared_primary_family", "resolved_alias_families", "fonts", "has_text", "pass"}
    for index, row in enumerate(payload["records"], 1):
        if (not isinstance(row, dict) or set(row) != fields
            or any(not isinstance(row.get(key), str) or not row[key].strip() for key in ("component_id", "selector", "declared_primary_family"))
            or type(row.get("has_text")) is not bool or row.get("pass") is not True
            or not isinstance(row.get("resolved_alias_families"), list)
            or any(not isinstance(item, str) or not item.strip() for item in row.get("resolved_alias_families", []))
            or not isinstance(row.get("fonts"), list)):
            failures.append(f"Rendered font row {index} lacks exact typed component and glyph evidence.")
            continue
        if row["has_text"] and not row["fonts"]:
            failures.append(f"Rendered font row {index} has text but no actual glyph font.")
        for font in row["fonts"]:
            if (not isinstance(font, dict) or not {"familyName", "postScriptName", "isCustomFont", "glyphCount"}.issubset(font)
                or not isinstance(font.get("familyName"), str) or not font["familyName"].strip()
                or not isinstance(font.get("postScriptName"), str) or not font["postScriptName"].strip()
                or type(font.get("isCustomFont")) is not bool or type(font.get("glyphCount")) is not int or font["glyphCount"] <= 0):
                failures.append(f"Rendered font row {index} contains malformed platform glyph data.")
        actual = {normalize(font[key]) for font in row["fonts"] if isinstance(font, dict)
                  for key in ("familyName", "postScriptName") if isinstance(font.get(key), str)}
        declared = normalize(row["declared_primary_family"])
        permitted = {declared, *(normalize(item) for item in row["resolved_alias_families"])}
        if row["has_text"] and declared not in generic and not actual.intersection(permitted):
            failures.append(f"Rendered font row {index} declares a family that none of its actual glyph-font evidence uses.")
    return failures
