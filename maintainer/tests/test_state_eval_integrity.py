from __future__ import annotations

import binascii
import hashlib
import importlib
import importlib.util
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator


PLUGIN = Path(__file__).resolve().parents[2]
INIT = PLUGIN / "skills" / "design-dna" / "scripts" / "init_project_state.py"
RUN_EVALS = PLUGIN / "maintainer" / "scripts" / "run_evals.py"
SCRIPTS = PLUGIN / "maintainer" / "scripts"
SCHEMAS = PLUGIN / "maintainer" / "schemas"


def run_python(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", str(script), *arguments],
        cwd=PLUGIN,
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=environment,
        timeout=120,
    )


def write_png(path: Path, width: int, height: int) -> str:
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = binascii.crc32(kind)
        checksum = binascii.crc32(data, checksum) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    row = b"\x00" + (b"\x24\x68\xac" * width)
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def schema3_adapter() -> object:
    """Load the shipped verifier used by Standard+ completion validation."""

    initializer = load_initializer_module()
    adapter, failure = initializer.load_schema3_render_review_adapter()
    if adapter is None:
        raise AssertionError(
            "The state-eval fixture could not load the shipped schema-3 "
            f"rendered-review adapter: {failure}"
        )
    return adapter


def schema3_source_snapshot(
    adapter: object,
    files: dict[str, bytes],
    *,
    entry_path: str,
) -> tuple[dict[str, object], str]:
    """Build the immutable local-source shape checked by the shipped adapter."""

    manifest_files = [
        {
            "path": path,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for path, payload in sorted(files.items())
    ]
    manifest_sha256 = adapter.source_manifest_digest(manifest_files)
    return (
        {
            "policy": "frozen-deny-by-default-public-root",
            "root_kind": "explicit-build-root",
            "entry_path": entry_path,
            "drift_check": (
                "passed-source-and-frozen-snapshot-before-report-and-commit"
            ),
            "manifest": {
                "algorithm": "sha256",
                "manifest_sha256": manifest_sha256,
                "file_count": len(manifest_files),
                "total_bytes": sum(
                    entry["bytes"] for entry in manifest_files
                ),
                "files": manifest_files,
                "excluded_counts": {
                    "hidden_or_source_only_path": 0,
                    "sensitive_or_source_config": 0,
                    "extension_not_public_allowlist": 0,
                },
            },
        },
        manifest_sha256,
    )


def write_bound_schema3_render_review(project: Path) -> dict[str, str]:
    """Write a complete hash- and marker-bound Standard+ review fixture.

    This intentionally uses the same narrow schema-3 verifier that production
    completion invokes.  A hand-written JSON note with merely familiar fields
    is not sufficient: the test golden path must include real wide/narrow PNGs,
    an immutable source snapshot, a report-byte record, and the adjacent output
    marker.
    """

    adapter = schema3_adapter()
    review_dir = project / "evidence" / "render-review"
    review_dir.mkdir(parents=True, exist_ok=True)
    wide_path = review_dir / "wide.png"
    narrow_path = review_dir / "narrow.png"
    wide_digest = write_png(wide_path, 1280, 1600)
    narrow_digest = write_png(narrow_path, 390, 1200)
    contact_path = review_dir / "contact-sheet.html"
    contact_payload = b"<!doctype html><title>Schema-3 review fixture</title>\n"
    contact_path.write_bytes(contact_payload)
    contact_digest = hashlib.sha256(contact_payload).hexdigest()

    source_snapshot, source_digest = schema3_source_snapshot(
        adapter,
        {"index.html": b"<!doctype html><title>fixture build</title>\n"},
        entry_path="index.html",
    )
    output_identity = {
        "id": "a" * 64,
        "path_sha256": adapter.rendered_output_path_sha256(review_dir),
    }
    report_path = review_dir / "render-review.json"
    marker_path = review_dir / ".design-dna-render-review.json"

    def capture(
        capture_id: str,
        screenshot_path: str,
        screenshot_digest: str,
        *,
        viewport_width: int,
        viewport_height: int,
        pixel_width: int,
        pixel_height: int,
    ) -> dict[str, object]:
        return {
            "id": capture_id,
            "route_id": "route-01",
            "capture_status": "complete",
            "final_url": "http://127.0.0.1/menu",
            "viewport": {
                "width": viewport_width,
                "height": viewport_height,
                "device_scale_factor": 1,
            },
            "interaction": {
                "requested_steps": 0,
                "completed_steps": 0,
                "status": "not-requested",
            },
            "screenshot": {
                "path": screenshot_path,
                "sha256": screenshot_digest,
                "media_type": "image/png",
                "bytes": (review_dir / screenshot_path).stat().st_size,
                "pixel_width": pixel_width,
                "pixel_height": pixel_height,
            },
        }

    report: dict[str, object] = {
        "schema_version": 3,
        "tool": {
            "name": "design-dna-rendered-review",
            "version": "3.0.0",
            "report_schema": "render-review.schema.json",
        },
        "output_identity": output_identity,
        "execution_ok": True,
        "review_required": True,
        "automatic_visual_quality_pass": False,
        "quality_status": "manual-review-required",
        "execution": {},
        "privacy": {},
        "build": {
            "id": "build-42",
            "target_input": "fixture",
            "target_kind": "local-directory",
        },
        "source_snapshot": source_snapshot,
        "capture_contract": {
            "contract_mode": "capture-manifest-v1",
            "profiles": [{"id": "wide"}, {"id": "narrow"}],
            "scenarios": [{"id": "menu-default"}],
        },
        "routes": [
            {
                "id": "route-01",
                "requested": "/menu",
                "url": "http://127.0.0.1/menu",
            }
        ],
        "captures": [
            capture(
                "menu-wide",
                "wide.png",
                wide_digest,
                viewport_width=1280,
                viewport_height=900,
                pixel_width=1280,
                pixel_height=1600,
            ),
            capture(
                "menu-narrow",
                "narrow.png",
                narrow_digest,
                viewport_width=390,
                viewport_height=844,
                pixel_width=390,
                pixel_height=1200,
            ),
        ],
        "artifacts": {
            "contact_sheet": {
                "path": "contact-sheet.html",
                "sha256": contact_digest,
                "media_type": "text/html",
                "bytes": len(contact_payload),
            },
            "report": {"path": "render-review.json", "bytes": 0},
            "marker": {
                "path": ".design-dna-render-review.json",
                "bytes": 0,
            },
            "capture_bytes": wide_path.stat().st_size + narrow_path.stat().st_size,
            "total_bytes": 0,
        },
        "manual_review": {},
    }

    marker_bytes = 0
    report_payload = b""
    marker: dict[str, object] = {}
    for _ in range(8):
        artifacts = report["artifacts"]
        assert isinstance(artifacts, dict)
        artifacts["marker"] = {
            "path": ".design-dna-render-review.json",
            "bytes": marker_bytes,
        }
        report_payload = (json.dumps(report, indent=2) + "\n").encode("utf-8")
        artifacts["report"] = {
            "path": "render-review.json",
            "bytes": len(report_payload),
        }
        report_payload = (json.dumps(report, indent=2) + "\n").encode("utf-8")
        marker = {
            "schema_version": 3,
            "marker_type": "design-dna-render-review-output",
            "tool": {
                "name": "design-dna-rendered-review",
                "version": "3.0.0",
            },
            "output_identity": output_identity,
            "report": {
                "path": "render-review.json",
                "sha256": hashlib.sha256(report_payload).hexdigest(),
                "bytes": len(report_payload),
            },
            "created_at": "2026-08-12T12:00:00+00:00",
            "build_id_sha256": hashlib.sha256(b"build-42").hexdigest(),
        }
        marker_payload = (json.dumps(marker, indent=2) + "\n").encode("utf-8")
        if len(marker_payload) == marker_bytes:
            break
        marker_bytes = len(marker_payload)
    else:
        raise AssertionError("schema-3 fixture marker byte count did not stabilize")

    artifacts = report["artifacts"]
    assert isinstance(artifacts, dict)
    artifacts["marker"] = {
        "path": ".design-dna-render-review.json",
        "bytes": marker_bytes,
    }
    report_payload = (json.dumps(report, indent=2) + "\n").encode("utf-8")
    marker["report"] = {
        "path": "render-review.json",
        "sha256": hashlib.sha256(report_payload).hexdigest(),
        "bytes": len(report_payload),
    }
    marker_payload = (json.dumps(marker, indent=2) + "\n").encode("utf-8")
    if len(marker_payload) != marker_bytes:
        raise AssertionError("schema-3 fixture marker size changed after rebinding")
    report_path.write_bytes(report_payload)
    marker_path.write_bytes(marker_payload)
    return {
        "report_digest": hashlib.sha256(report_payload).hexdigest(),
        "source_digest": source_digest,
        "contact_digest": contact_digest,
        "wide_digest": wide_digest,
        "narrow_digest": narrow_digest,
    }


def complete_visual_review() -> str:
    template = (
        PLUGIN
        / "skills"
        / "design-dna"
        / "templates"
        / "visual-review-template.md"
    ).read_text(encoding="utf-8")
    return fill_substantive_template("visual-review", template)


def markdown_cells(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def filled_cell(
    header: str,
    existing: str,
    row_number: int,
) -> str:
    values = {
        "Requirement or open field": "Owner-approved task and content boundary",
        "Class": "open",
        "Class/status": "open; approved",
        "Authority and evidence": "Accountable owner, reviewed 2026-07-29",
        "Candidate consequence": "Keep this decision local and reversible.",
        "Source and retrieval date": f"Project source {row_number + 1}, 2026-07-29",
        "Relevance": "Direct evidence for the project decision.",
        "Transferable relationship": "Preserve the task relationship, not its styling.",
        "Limit or do-not-copy boundary": "Project-specific; no visual copying.",
        "Limits, authority, and do-not-copy boundary": "Project-specific and owner-bounded.",
        "Candidate ID": f"C-{row_number + 1:02d}",
        "`creative_logic.statement`": "Arrange approved evidence around the visitor decision.",
        "Consequential observable decisions": "Decision-first hierarchy and evidence adjacency.",
        "Assumptions and limits": "Applies only to the approved content and tested route.",
        "Directly reviewable proof": f"candidate-{row_number + 1:02d} rendered artifact",
        "Artifact path and SHA-256": (
            "evidence/menu-review.png plus sha256:" + ("0" * 64)
        ),
        "Candidate/build and source identity": "build-42; source-packet-7",
        "Route/state/viewport/preferences": "/menu; default; 390x844; reduced motion",
        "Reviewer and exposure": "reviewer-7; unbriefed; 2026-07-29",
        "Relevant observations": "The task relationship remained legible and specific.",
        "Constraint ID": f"CON-{row_number + 1:02d}",
        "Requirement or open question": "Use owner-approved content without invented claims.",
        "Scope": "Reviewed candidate only.",
        "Status and owner": "approved; reviewer-7",
        "Route, flow, or component": "/menu",
        "Visitor or editorial job": "Choose a service and understand its constraints.",
        "Source/readiness": "approved",
        "Relevant states and conditions": "Default, error, narrow, zoomed, and reduced motion.",
        "Evidence or owner": "Owner-approved service catalog; reviewer-7",
        "Content, claim, proof, integration, or asset": "Owner-approved service catalog",
        "Status": "approved",
        "Source/owner and date": "Content owner, reviewed 2026-07-28",
        "Scope or expiry": "Candidate build-42; recheck on content change.",
        "Public treatment": "show",
        "Decision ID": f"DEC-{row_number + 1:02d}",
        "Concern": "composition",
        "Decision": "Lead with the approved visitor choice and adjacent proof.",
        "Project reason or source": (
            "The approved service packet binds each choice to its eligibility constraint."
        ),
        "Observable consequence": (
            "Each choice remains adjacent to its constraint in the rendered sequence."
        ),
        "Verification": (
            "Inspect the sequence with long approved copy at narrow and wide widths."
        ),
        "Reason and evidence": "The source packet makes this the primary task.",
        "What should be observable": "The next action is clear before supporting detail.",
        "Adaptation or limit": "Recompose at narrow widths without changing priority.",
        "Constraint or assumption": "Approved copy remains available.",
        "Proof treatment": "Render the real copy in the representative route.",
        "Consequential decision": "Keep the primary choice ahead of supporting evidence.",
        "Expected observable result": "A reviewer identifies the next action without briefing.",
        "Proof region or behavior": "Opening and first task transition.",
        "Relevant adaptation or failure condition": "Long copy, narrow width, and reduced motion.",
        "Route or flow": "/menu",
        "Route/state": "/menu; default",
        "Viewport/context": "390x844; keyboard; reduced motion",
        "Rendered PNG path and SHA-256": (
            "evidence/menu-review.png plus sha256:" + ("0" * 64)
        ),
        "Observation": "The primary task remained clear and usable.",
        "State/content/data": "Long approved content",
        "Viewport/container": "390 x 844 at 200 percent zoom",
        "Browser/input/language/preferences/runtime": "Chromium; keyboard; English; reduced motion",
        "Expected observation": "The visitor choice remains primary.",
        "Actual rendered or behavioral observation": "The choice remained primary at the tested width.",
        "Exact evidence": "build-42; /menu; 390x844; opening region",
        "Disposition and owner": "keep; reviewer-7",
        "Severity": "high",
        "Confidence": "high",
        "Evidence": "evidence/menu-review.png on build-42",
        "User/release impact": "Primary navigation was clipped at narrow width.",
        "Cause": "Navigation did not recompose at the intermediate breakpoint.",
        "Fix or disposition": "Reworked navigation into the tested compact pattern.",
        "Rerun verification": "Rechecked build-42 at 390 x 844; no clipping observed.",
        "Owner": "reviewer-7",
        "ID": f"CLM-{row_number + 1:03d}",
        "Exact claim or output": "Service consultation takes 30 minutes.",
        "Type": "duration",
        "Route/component": "/booking",
        "Source and accountable owner": "Owner schedule policy, reviewer-7",
        "Scope, locale, jurisdiction, and assumptions": "US English booking flow",
        "Reviewed / expires": "Reviewed 2026-07-28; recheck before policy change",
        "Output": "Displayed estimate",
        "Inputs": "Approved duration",
        "Formula or rule": "Show the approved duration without calculation.",
        "Source of each input": "Owner schedule policy",
        "Bounds and failure behavior": "Omit when the approved value is unavailable.",
        "Maintenance owner": "reviewer-7",
    }
    if header == "Status":
        folded = existing.casefold()
        if "fixed-unverified" in folded or "not-applicable" in folded:
            return "verified"
        if "provisional" in folded or "revised" in folded:
            return "accepted"
        return values["Status"]
    return values.get(
        header,
        existing or f"Recorded evidence for {header.lower()}.",
    )


def fill_substantive_template(record: str, text: str) -> str:
    text = text.replace("__DESIGN_DNA_VERSION__", "design-dna 4.0.0")
    lines = text.splitlines()
    rendered: list[str] = []
    index = 0
    while index < len(lines):
        cells = markdown_cells(lines[index])
        next_cells = (
            markdown_cells(lines[index + 1])
            if index + 1 < len(lines)
            else []
        )
        if (
            cells
            and len(cells) == len(next_cells)
            and all(
                cell.replace(":", "").replace("-", "") == ""
                for cell in next_cells
            )
        ):
            rendered.extend((lines[index], lines[index + 1]))
            index += 2
            row_number = 0
            table_rows: list[str] = []
            while index < len(lines):
                row = markdown_cells(lines[index])
                if not row:
                    break
                if len(row) != len(cells):
                    raise AssertionError(
                        f"Template table width mismatch for {record}: {row}"
                    )
                filled = [
                    filled_cell(header, value, row_number)
                    for header, value in zip(cells, row)
                ]
                if record == "exploration" and "Artifact path and SHA-256" in cells:
                    artifact_index = cells.index("Artifact path and SHA-256")
                    filled[artifact_index] = (
                        f"evidence/candidate-{row_number + 1:02d}.png plus sha256:"
                        + ("0" * 64)
                    )
                if cells == [
                    "Severity",
                    "Confidence",
                    "Evidence",
                    "User/release impact",
                    "Cause",
                    "Fix or disposition",
                    "Rerun verification",
                    "Status",
                    "Owner",
                ]:
                    filled[7] = "verified"
                table_rows.append("| " + " | ".join(filled) + " |")
                row_number += 1
                index += 1
            minimum_rows = 1
            while len(table_rows) < minimum_rows:
                filled = [
                    filled_cell(header, "", len(table_rows))
                    for header in cells
                ]
                if record == "exploration" and "Artifact path and SHA-256" in cells:
                    artifact_index = cells.index("Artifact path and SHA-256")
                    filled[artifact_index] = (
                        f"evidence/candidate-{len(table_rows) + 1:02d}.png plus sha256:"
                        + ("0" * 64)
                    )
                table_rows.append("| " + " | ".join(filled) + " |")
            rendered.extend(table_rows)
            continue
        rendered.append(lines[index])
        index += 1

    lines = rendered
    rendered = []
    index = 0
    explicit_values = {
        "Assurance profile and why it fits": "standard; proportionate to the build risk",
        "Assurance profile and rationale": "standard; proportionate to the build risk",
        "Source/workspace identity and SHA-256": (
            "project snapshot plus sha256:" + ("b" * 64)
        ),
        "Rendered-review report path, hash, contract, and execution result": (
            "evidence/render-review/render-review.json plus sha256:"
            + ("0" * 64)
            + "; build=build-42; source_snapshot_sha256="
            + ("b" * 64)
            + "; contract_mode=deterministic-default-v1; execution_ok=true"
        ),
        (
            "Cross-build comparison identity, compatibility, changed captures, "
            "reviewer, and result, or `not performed`"
        ): (
            "not performed; rationale=no accepted comparison baseline was "
            "designated for build-42"
        ),
        "Coverage contact sheet or artifact index": (
            "evidence/render-review/contact-sheet.html plus sha256:"
            + ("0" * 64)
        ),
        "Release intent": "staging",
        "Build, commit, or artifact ID": "build-42",
        "Candidate/build ID and reversible checkpoint": (
            "build-42; checkpoint=direction-proof-42"
        ),
        "Current decision": "proceed",
        "Comparison performed, partially performed, or not performed": (
            "performed; one project-specific candidate proof was reviewed"
        ),
        "Selected candidate ID and `creative_logic`": "C-01; logic_id=logic-1",
        "Selected proof identity and artifact": (
            "C-01; evidence/candidate-01.png plus sha256:" + ("0" * 64)
        ),
        "`logic_id`": "logic-1",
        "`statement`": "Arrange approved evidence around the visitor decision.",
        "`evidence`": "Owner-approved source packet and rendered candidate proof.",
        "`limits`": "Applies only to the reviewed content, route, and conditions.",
        "`status`": "accepted",
        "`extensions`": "none",
        "Candidate and `creative_logic.logic_id`": "C-01; logic-1",
        "Reviewer, relationship, prior exposure, and date": (
            "reviewer-7; relationship=producer-self; exposure=unbriefed; "
            "date=2026-07-29"
        ),
        "Perceptual status": "self-reviewed candidate",
        "Accountable-owner rendered acceptance": "pending for build-42",
        "Owner decision claim scope": "standard",
        "Owner ID, exact candidate/build ID, review date, and evidence path/hash": (
            "owner_id=not-reviewed; candidate=build-42; "
            "reviewed_date=not-reviewed; evidence=none"
        ),
        "Date and final implementation round reviewed": (
            "date=2026-07-29; final_round=yes"
        ),
        "Reviewers, relationship, and lens": (
            "reviewer-7; relationship=producer-self; lens=perception+implementation"
        ),
        "Cross-build decision": (
            "not performed; no accepted comparison baseline was designated "
            "for build-42"
        ),
        (
            "Accountable-owner disposition, scope, ID, date, candidate/build, "
            "and evidence"
        ): (
            "status=pending; scope=standard; owner_id=not-reviewed; "
            "reviewed_date=not-reviewed; candidate=build-42; evidence=none"
        ),
        (
            "Remaining limitations, open high/medium findings, owners, and "
            "release blockers"
        ): "none within the reviewed design scope",
        "Reviewer conclusion": "self-reviewed candidate",
        "Build or artifact ID": "build-42",
        "Final implementation reviewed": "yes",
        "Reviewer relationship": "producer-self",
        "Owner disposition": "pending",
        "Release blockers": "none within the reviewed scope",
        "Status": "not-required",
        "Claims still pending or prohibited": "none",
        "Scenario values visibly labeled": "yes; no scenario values are public",
        "Categorical words reviewed (`all`, `every`, `always`, `never`, `best`, `only`)": "yes; none remain unsupported",
        "Public copy checked against this ledger": "yes on build-42",
        "Owner approval and date": "reviewer-7, 2026-07-28",
    }
    initializer = load_initializer_module()
    known_prompts = set(explicit_values)
    known_prompts.update(initializer.REQUIRED_RECORD_LABELS.get(record, ()))
    for profile_labels in initializer.PROFILE_REQUIRED_LABELS.get(
        record,
        {},
    ).values():
        known_prompts.update(profile_labels)
    ordered_prompts = sorted(known_prompts, key=len, reverse=True)
    while index < len(lines):
        match = re.match(r"^(\s*)-\s+(.+)$", lines[index])
        if not match:
            rendered.append(lines[index])
            index += 1
            continue
        block = [match.group(2).strip()]
        cursor = index + 1
        while cursor < len(lines):
            continuation = lines[cursor]
            if (
                not continuation.startswith("  ")
                or re.match(r"^\s*-\s+", continuation)
                or not continuation.strip()
            ):
                break
            block.append(continuation.strip())
            cursor += 1
        combined = " ".join(block)
        if ":" not in combined:
            rendered.extend(lines[index:cursor])
            index = cursor
            continue
        prompt = next(
            (
                candidate
                for candidate in ordered_prompts
                if combined.startswith(candidate)
                and combined[len(candidate):len(candidate) + 1]
                in {"", ":", ",", " ", "("}
            ),
            None,
        )
        if prompt is None:
            prompt, _old_value = combined.split(":", 1)
        value = explicit_values.get(
            prompt,
            f"Recorded project evidence for {prompt.lower()} on build-42.",
        )
        rendered.append(f"{match.group(1)}- {prompt}: {value}")
        index = cursor
    result = "\n".join(rendered) + "\n"
    return re.sub(
        r"__[A-Z0-9_]+__",
        "Recorded project-specific evidence for this required proof anchor.",
        result,
    )


def materialize_exploration_evidence(project: Path, text: str) -> str:
    evidence = project / "evidence"
    evidence.mkdir(exist_ok=True)
    rendered = text
    for number in (1,):
        relative = f"evidence/candidate-{number:02d}.png"
        artifact = project / relative
        artifact.write_bytes(
            b"\x89PNG\r\n\x1a\n" + f"candidate-{number}".encode("ascii")
        )
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        rendered = rendered.replace(
            relative + " plus sha256:" + ("0" * 64),
            relative + " plus sha256:" + digest,
        )
    return rendered


def materialize_visual_review_evidence(
    project: Path,
    text: str,
    *,
    include_extended: bool = True,
) -> str:
    bound = write_bound_schema3_render_review(project)
    report_reference = (
        "evidence/render-review/render-review.json plus sha256:"
        f"{bound['report_digest']}"
    )
    contact_reference = (
        "evidence/render-review/contact-sheet.html plus sha256:"
        f"{bound['contact_digest']}"
    )
    wide_reference = (
        "evidence/render-review/wide.png plus sha256:"
        f"{bound['wide_digest']}"
    )
    narrow_reference = (
        "evidence/render-review/narrow.png plus sha256:"
        f"{bound['narrow_digest']}"
    )
    rendered = text.replace(
        "evidence/menu-review.png plus sha256:" + ("0" * 64),
        narrow_reference,
    )

    scope_row = (
        "| Recorded evidence for route/state or reviewed body. | "
        "Recorded evidence for material review risk or not-applicable reason. | "
        "Recorded evidence for wide capture id. | "
        "Recorded evidence for narrow capture id. | "
        "applicable / not-applicable / blocked |"
    )
    if scope_row not in rendered:
        raise AssertionError("visual-review scope fixture row was not found")
    rendered = rendered.replace(
        scope_row,
        "| /menu; default | The primary action and compact navigation need "
        "a real wide/narrow final encounter comparison. | menu-wide | "
        "menu-narrow | applicable |",
    )
    surface_row = (
        "| First impression and surface fidelity | "
        "applicable / not-applicable / blocked | "
        f"{narrow_reference} | Recorded evidence for observation or limitation. |"
    )
    if surface_row not in rendered:
        raise AssertionError("visual-review surface fixture row was not found")
    rendered = rendered.replace(
        surface_row,
        "| First impression and surface fidelity | applicable | "
        f"{wide_reference} | The opening hierarchy stays specific to the "
        "reviewed visitor task without losing its first action. |",
    )
    adversarial_row = (
        "| Adversarial specificity review | applicable / not-applicable / blocked | "
        f"{narrow_reference} | Recorded evidence for result or limitation. |"
    )
    preship_row = (
        "| Preship gate | applicable / not-applicable / blocked | "
        f"{narrow_reference} | Recorded evidence for result or limitation. |"
    )
    if adversarial_row not in rendered or preship_row not in rendered:
        raise AssertionError("visual-review preship fixture rows were not found")
    rendered = rendered.replace(
        adversarial_row,
        "| Adversarial specificity review | applicable | "
        f"{narrow_reference} | The narrow capture keeps the task hierarchy "
        "legible without template-like fallback composition. |",
    ).replace(
        preship_row,
        "| Preship gate | applicable | "
        f"{wide_reference} | The reviewed build has explicit evidence for "
        "the final opening, hierarchy, and responsive surface. |",
    )

    evidence_block = (
        "- Source/workspace identity and SHA-256: fixture source snapshot plus "
        f"sha256:{bound['source_digest']}\n"
        "- Rendered-review report path, hash, contract, and execution result: "
        f"{report_reference}; build=build-42; source_snapshot_sha256="
        f"{bound['source_digest']}; contract_mode=capture-manifest-v1; "
        "execution_ok=true\n"
        "- Coverage contact sheet or artifact index: "
        f"{contact_reference}\n"
    )
    reviewer_anchor = "- Reviewer relationship: producer-self\n"
    if reviewer_anchor not in rendered:
        raise AssertionError("visual-review reviewer fixture anchor was not found")
    rendered = rendered.replace(
        reviewer_anchor,
        reviewer_anchor + "\n" + evidence_block,
        1,
    )
    if include_extended:
        rendered += (
            "\n- Cross-build comparison identity, compatibility, changed captures, "
            "reviewer, and result, or `not performed`: not performed; "
            "rationale=no accepted comparison baseline was designated for build-42\n"
            "- Cross-build decision: not performed; no accepted comparison "
            "baseline was designated for build-42\n"
        )
    return rendered


def render_comparison_payload(
    *,
    candidate_build_id: str = "build-42",
) -> dict[str, object]:
    environment = {
        "report.tool.version": "2.0.0",
        "execution.node_version": "v22.0.0",
        "execution.platform": "win32",
        "execution.architecture": "x64",
        "execution.playwright_version": "1.58.2",
        "execution.browser.engine": "chromium",
        "execution.browser.product_hint": "chrome",
        "execution.browser.version": "140.0.0",
        "execution.browser.executable_source": "system-discovery",
        "execution.browser.executable_name": "chrome.exe",
    }

    def compared_input(role: str, build_id: str) -> dict[str, object]:
        return {
            "role": role,
            "report_sha256": "1" * 64,
            "report_bytes": 4096,
            "render_report_schema_sha256": "2" * 64,
            "output_identity": {
                "id": "3" * 64,
                "path_sha256": "4" * 64,
            },
            "build": {
                "id": build_id,
                "id_sha256": hashlib.sha256(
                    build_id.encode("utf-8")
                ).hexdigest(),
                "target_kind": "local-directory",
                "source_manifest_sha256": "5" * 64,
            },
            "captured_at": "2026-07-29T11:00:00Z",
            "marker_created_at": "2026-07-29T11:01:00Z",
            "execution_environment": environment,
        }

    def png(path: str, digest: str) -> dict[str, object]:
        return {
            "path": path,
            "sha256": digest * 64,
            "media_type": "image/png",
            "bytes": 100,
            "pixel_width": 10,
            "pixel_height": 10,
        }

    capture_id = "route-01--default--mobile-390"
    return {
        "schema_version": 1,
        "tool": {
            "name": "design-dna-render-comparison",
            "version": "1.0.0",
            "report_schema": "render-comparison.schema.json",
        },
        "comparison_id": "build-41-to-build-42",
        "created_at": "2026-07-29T12:00:00Z",
        "output_identity": {
            "id": "6" * 64,
            "path_sha256": "7" * 64,
        },
        "execution_ok": True,
        "review_required": True,
        "automatic_visual_approval": False,
        "decision_status": "human-accept-reject-required",
        "execution": {
            "node_version": "v22.0.0",
            "platform": "win32",
            "architecture": "x64",
            "playwright_version": "1.58.2",
            "playwright_source": "normal-node-resolution",
            "browser": {
                "engine": "chromium",
                "product_hint": "chrome",
                "version": "140.0.0",
                "executable_source": "system-discovery",
                "executable_name": "chrome.exe",
            },
            "network_policy": (
                "offline-about-blank-data-png-decode-all-routed-requests-blocked"
            ),
        },
        "privacy": {
            "classification": (
                "potentially-sensitive-rendered-comparison-evidence"
            ),
            "visual_content_not_redacted": True,
            "absolute_paths_persisted": False,
            "retention_notice": (
                "This local evidence remains at the selected path until the "
                "operator deliberately removes it."
            ),
            "limitations": [
                (
                    "Rendered pixels can contain confidential or personal "
                    "content and are deliberately not redacted."
                ),
                (
                    "Build identifiers and hashes can remain sensitive when "
                    "correlated with private project records."
                ),
            ],
        },
        "mask_policy": {
            "supported": False,
            "mode": "none",
            "declaration": "operator-explicit",
            "regions_applied": 0,
        },
        "inputs": {
            "baseline": compared_input("baseline", "build-41"),
            "candidate": compared_input(
                "candidate",
                candidate_build_id,
            ),
        },
        "compatibility": {
            "status": "compatible",
            "capture_count": 1,
            "capture_contract_sha256": "8" * 64,
            "route_contract_sha256": "9" * 64,
            "capture_identity_sha256": "a" * 64,
            "environment_differences": [],
            "warnings": [],
        },
        "baseline_freshness": {
            "status": "current",
            "threshold_days": 30,
            "age_days": 1,
            "warnings": [],
        },
        "comparisons": [
            {
                "capture_id": capture_id,
                "identity": {
                    "id": capture_id,
                    "route_id": "route-01",
                    "scenario_id": "default",
                    "profile_id": "mobile-390",
                    "route_label": "Menu",
                    "state_label": "Default",
                    "viewport": {
                        "width": 390,
                        "height": 844,
                        "device_scale_factor": 1,
                    },
                    "preferences": {"reduced_motion": "reduce"},
                    "review_mode": {"kind": "default"},
                    "interaction": {"kind": "none"},
                },
                "artifacts": {
                    "baseline": png("captures/baseline.png", "b"),
                    "actual": png("captures/actual.png", "c"),
                    "diff": png("captures/diff.png", "d"),
                },
                "metrics": {
                    "algorithm": "exact-decoded-rgba-v1",
                    "total_pixels": 100,
                    "mismatch_pixels": 1,
                    "mismatch_pixel_ratio": 0.01,
                },
                "review_status": "human-accept-reject-required",
            }
        ],
        "summary": {
            "capture_count": 1,
            "changed_capture_count": 1,
            "total_pixels": 100,
            "mismatch_pixels": 1,
            "mismatch_pixel_ratio": 0.01,
        },
        "artifacts": {
            "contact_sheet": {
                "path": "comparison.html",
                "sha256": "e" * 64,
                "media_type": "text/html",
                "bytes": 1024,
            },
            "comparison_bytes": 4096,
        },
        "manual_review": {
            "status": "required",
            "required_actions": [
                (
                    "Inspect every baseline, actual, and pixel-diff triplet "
                    "in context."
                ),
                (
                    "Review baseline freshness and every pinned execution "
                    "environment difference."
                ),
                (
                    "Record a human accept or reject decision outside this "
                    "immutable evidence report."
                ),
            ],
            "limitations": [
                (
                    "Exact pixel equality does not establish perceptual "
                    "equivalence, usability, accessibility, or design quality."
                ),
                (
                    "Still captures do not prove interactions, motion, content "
                    "truth, performance, or unrecorded behavior."
                ),
                (
                    "No threshold or region mask is applied and the comparator "
                    "never updates or approves the baseline."
                ),
                (
                    "Path-bound hashes detect ordinary drift but are not "
                    "signatures against an attacker rewriting all evidence."
                ),
            ],
        },
    }


def materialize_render_comparison_evidence(
    project: Path,
    text: str,
    *,
    payload: dict[str, object] | None = None,
) -> str:
    comparison = payload or render_comparison_payload()
    report_dir = project / "evidence" / "render-comparison"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "render-comparison.json"
    report_path.write_text(
        json.dumps(comparison, indent=2) + "\n",
        encoding="utf-8",
    )
    report_digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    rendered = text.replace(
        (
            "- Cross-build comparison identity, compatibility, changed "
            "captures, reviewer, and result, or `not performed`: not "
            "performed; rationale=no accepted comparison baseline was "
            "designated for build-42"
        ),
        (
            "- Cross-build comparison identity, compatibility, changed "
            "captures, reviewer, and result, or `not performed`: "
            "report=evidence/render-comparison/"
            f"render-comparison.json plus sha256:{report_digest}; "
            "baseline=build-41; candidate=build-42; "
            "capture_count=1; compatibility=compatible; "
            "changed_capture_count=1; reviewer_relationship=producer-self"
        ),
    )
    return rendered.replace(
        (
            "- Cross-build decision: not performed; no accepted "
            "comparison baseline was designated for build-42"
        ),
        (
            "- Cross-build decision: accept candidate; reviewer-7 "
            "inspected the baseline, actual, and pixel-diff triplet and "
            "confirmed the intended navigation correction"
        ),
    )


def with_quality_assurance_profile(record: str, text: str) -> str:
    if record == "direction":
        return text.replace(
            "- Assurance profile and why it fits: standard; proportionate to the build risk",
            "- Assurance profile and why it fits: showcase + high-risk; proportionate to the build risk",
        )
    if record == "visual-review":
        return text.replace(
            "- Assurance profile and rationale: standard; proportionate to the build risk",
            "- Assurance profile and rationale: showcase; proportionate to the build risk",
        )
    return text


def persist_quality_assurance_profiles(
    project: Path,
    record: str,
) -> None:
    """Keep the fixture body and persisted cumulative capabilities identical."""

    profiles_by_record = {
        "direction": ["standard"],
        "visual-review": ["standard"],
    }
    profiles = profiles_by_record.get(record)
    if profiles is None:
        return
    state_path = project / ".design-dna" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["assurance_profiles"] = profiles
    state["evidence_contract"]["applicable_capabilities"] = [
        capability
        for capability in ("range-study", "high-risk", "asset-led")
        if capability in profiles
    ]
    state_path.write_text(
        json.dumps(state, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


NEW_QUALITY_COMPLETION_LABELS = {
    "direction": (),
    "direction-proof": (
        "Reviewer relationship",
        "Current decision",
    ),
    "visual-review": (
        "Build or artifact ID",
        "Final implementation reviewed",
        "Reviewer relationship",
        "Reviewer conclusion",
        "Release blockers",
    ),
}

NEW_QUALITY_COMPLETION_SECTIONS = {
    "direction": (
        "Identity and intent",
        "Truth and provenance",
        "Responsive, accessible, and functional behavior",
        "Owner and release state",
    ),
    "visual-review": ("Rendered review", "Owner and release state"),
}


def without_markdown_prompt(text: str, label: str) -> str:
    lines = text.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        match = re.match(r"^\s*-\s+(.+)$", line)
        if (
            match
            and match.group(1).strip().casefold().startswith(
                label.casefold()
            )
        ):
            if start is not None:
                raise AssertionError(f"duplicate prompt for {label!r}")
            start = index
    if start is None:
        raise AssertionError(f"prompt not found for {label!r}")
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if (
            not line.startswith((" ", "\t"))
            or re.match(r"^\s*-\s+", line)
            or not line.strip()
        ):
            break
        end += 1
    return "\n".join(lines[:start] + lines[end:]) + "\n"


def without_markdown_section(text: str, heading: str) -> str:
    return re.sub(
        rf"(?ms)^##\s+{re.escape(heading)}\s*\n.*?(?=^##\s+|\Z)",
        "",
        text,
        count=1,
    )


def write_eval_suite(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "suite": "model-context",
                "skill_instructions": {
                    "codex": "Use $design-dna and follow its required verification.",
                    "claude_code": "Use /design-dna and follow its required verification.",
                },
                "cases": [
                    {
                        "id": "small-site",
                        "task": "Create a tiny local evaluation artifact.",
                        "review_requirements": [
                            "Inspect the exact retained artifact."
                        ],
                        "expected": {
                            "exit_codes": [0],
                            "files_exist": ["index.html"],
                        },
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def run_eval(
    root: Path,
    *extra: str,
    baseline: bool = True,
) -> subprocess.CompletedProcess[str]:
    fixture = root / "suite.json"
    write_eval_suite(fixture)
    work = root / "work"
    results = root / "results"
    work.mkdir()
    results.mkdir()
    code = (
        "from pathlib import Path;"
        "Path('index.html').write_text('<main>ok</main>', encoding='utf-8')"
    )
    arguments = [
        str(fixture),
        "--host",
        "codex",
        "--driver",
        sys.executable,
        "--driver-arg=-c",
        f"--driver-arg={code}",
        "--work-root",
        str(work),
        "--results-dir",
        str(results),
    ]
    if baseline:
        arguments.extend(
            [
                "--baseline-driver",
                sys.executable,
                "--baseline-arg=-c",
                f"--baseline-arg={code}",
            ]
        )
    arguments.extend(extra)
    return run_python(RUN_EVALS, *arguments)


def only_result(results: Path) -> dict[str, object]:
    paths = list(results.glob("*.json"))
    if len(paths) != 1:
        raise AssertionError(f"expected one result, found {paths}")
    return json.loads(paths[0].read_text(encoding="utf-8"))


def load_initializer_module():
    specification = importlib.util.spec_from_file_location(
        "design_dna_state_integrity_initializer",
        INIT,
    )
    if specification is None or specification.loader is None:
        raise AssertionError("could not load project-state initializer")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def lock_record(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    if not raw.startswith(b"\0"):
        raise AssertionError("lock file does not contain its fixed lock byte")
    return json.loads(raw[1:].decode("utf-8"))


class ProjectRecordIntegrityTests(unittest.TestCase):
    def test_every_substantive_template_has_a_golden_completion_path(
        self,
    ) -> None:
        for record_name, filename in (
            ("exploration", "exploration.md"),
            ("direction", "direction.md"),
            ("direction-proof", "direction-proof.md"),
            ("visual-review", "visual-review.md"),
            ("claims", "claims.md"),
            ("user-validation", "user-validation.md"),
            ("handoff", "handoff.md"),
        ):
            with self.subTest(record=record_name):
                with tempfile.TemporaryDirectory() as temporary:
                    project = Path(temporary) / "project"
                    project.mkdir()
                    initialized = run_python(
                        INIT,
                        "--project",
                        str(project),
                        "--record",
                        record_name,
                        "--json",
                    )
                    self.assertEqual(
                        initialized.returncode,
                        0,
                        initialized.stdout + initialized.stderr,
                    )
                    path = project / ".design-dna" / filename
                    scaffold = path.read_text(encoding="utf-8")
                    filled = fill_substantive_template(
                        record_name,
                        scaffold,
                    )
                    if record_name == "exploration":
                        filled = materialize_exploration_evidence(
                            project,
                            filled,
                        )
                    if record_name == "visual-review":
                        filled = materialize_visual_review_evidence(
                            project,
                            filled,
                            include_extended=False,
                        )
                    scaffold_headings = re.findall(
                        r"(?m)^##\s+.+$",
                        scaffold,
                    )
                    self.assertEqual(
                        scaffold_headings,
                        re.findall(r"(?m)^##\s+.+$", filled),
                        "The golden record must fill the documented template, not replace it.",
                    )
                    path.write_text(
                        filled,
                        encoding="utf-8",
                        newline="\n",
                    )
                    artifact = project / "binding.txt"
                    artifact.write_text(
                        f"exact {record_name} build\n",
                        encoding="utf-8",
                    )
                    completed = run_python(
                        INIT,
                        "--project",
                        str(project),
                        "--mark-complete",
                        record_name,
                        "--binding-kind",
                        "artifact",
                        "--binding-id",
                        f"{record_name}-build-42",
                        "--binding-path",
                        "binding.txt",
                        "--completion-owner",
                        "reviewer-7",
                        "--limitations",
                        "No known limitations within the recorded scope.",
                        "--json",
                    )
                    self.assertEqual(
                        completed.returncode,
                        0,
                        completed.stdout + completed.stderr,
                    )
                    checked = run_python(
                        INIT,
                        "--project",
                        str(project),
                        "--check-state",
                        "--json",
                    )
                    self.assertEqual(
                        checked.returncode,
                        0,
                        checked.stdout + checked.stderr,
                    )

    def test_new_quality_fields_are_required_for_record_completion(
        self,
    ) -> None:
        module = load_initializer_module()
        for record_name, labels in NEW_QUALITY_COMPLETION_LABELS.items():
            with self.subTest(record=record_name, case="positive"):
                with tempfile.TemporaryDirectory() as temporary:
                    project = Path(temporary) / "project"
                    project.mkdir()
                    initialized = run_python(
                        INIT,
                        "--project",
                        str(project),
                        "--record",
                        record_name,
                        "--json",
                    )
                    self.assertEqual(
                        initialized.returncode,
                        0,
                        initialized.stdout + initialized.stderr,
                    )
                    persist_quality_assurance_profiles(
                        project,
                        record_name,
                    )
                    filename = module.RECORD_TEMPLATES[record_name][0]
                    path = project / ".design-dna" / filename
                    filled = fill_substantive_template(
                        record_name,
                        path.read_text(encoding="utf-8"),
                    )
                    filled = with_quality_assurance_profile(
                        record_name,
                        filled,
                    )
                    if record_name == "visual-review":
                        filled = materialize_visual_review_evidence(
                            project,
                            filled,
                        )
                    path.write_text(
                        filled,
                        encoding="utf-8",
                        newline="\n",
                    )
                    artifact = project / "quality-binding.txt"
                    artifact.write_text(
                        f"exact {record_name} quality build\n",
                        encoding="utf-8",
                    )
                    completed = run_python(
                        INIT,
                        "--project",
                        str(project),
                        "--mark-complete",
                        record_name,
                        "--binding-kind",
                        "artifact",
                        "--binding-id",
                        f"{record_name}-quality-build",
                        "--binding-path",
                        "quality-binding.txt",
                        "--completion-owner",
                        "reviewer-7",
                        "--limitations",
                        "No known limitations within the recorded scope.",
                        "--json",
                    )
                    self.assertEqual(
                        completed.returncode,
                        0,
                        completed.stdout + completed.stderr,
                    )

            self.assertTrue(
                set(labels).issubset(
                    set(module.REQUIRED_RECORD_LABELS[record_name])
                    | {
                        label
                        for profile_labels in (
                            module.PROFILE_REQUIRED_LABELS
                            .get(record_name, {})
                            .values()
                        )
                        for label in profile_labels
                    }
                ),
                f"{record_name} completion labels drifted from the template",
            )
            for label in labels:
                with self.subTest(
                    record=record_name,
                    case="deleted",
                    label=label,
                ):
                    with tempfile.TemporaryDirectory() as temporary:
                        project = Path(temporary) / "project"
                        project.mkdir()
                        initialized = run_python(
                            INIT,
                            "--project",
                            str(project),
                            "--record",
                            record_name,
                            "--json",
                        )
                        self.assertEqual(
                            initialized.returncode,
                            0,
                            initialized.stdout + initialized.stderr,
                        )
                        persist_quality_assurance_profiles(
                            project,
                            record_name,
                        )
                        filename = module.RECORD_TEMPLATES[record_name][0]
                        path = project / ".design-dna" / filename
                        filled = fill_substantive_template(
                            record_name,
                            path.read_text(encoding="utf-8"),
                        )
                        filled = with_quality_assurance_profile(
                            record_name,
                            filled,
                        )
                        path.write_text(
                            without_markdown_prompt(filled, label),
                            encoding="utf-8",
                            newline="\n",
                        )
                        (project / "quality-binding.txt").write_text(
                            f"exact {record_name} quality build\n",
                            encoding="utf-8",
                        )
                        completed = run_python(
                            INIT,
                            "--project",
                            str(project),
                            "--mark-complete",
                            record_name,
                            "--binding-kind",
                            "artifact",
                            "--binding-id",
                            f"{record_name}-quality-build",
                            "--binding-path",
                            "quality-binding.txt",
                            "--completion-owner",
                            "reviewer-7",
                            "--limitations",
                            "No known limitations within the recorded scope.",
                            "--json",
                        )
                        self.assertEqual(
                            completed.returncode,
                            2,
                            completed.stdout + completed.stderr,
                        )
                        self.assertIn(label, completed.stderr)
                        self.assertIn(
                            "is missing or still scaffold text",
                            completed.stderr,
                        )

    def test_showcase_uses_the_same_open_creative_contract(self) -> None:
        module = load_initializer_module()
        template = (
            PLUGIN
            / "skills"
            / "design-dna"
            / "templates"
            / "direction-template.md"
        ).read_text(encoding="utf-8")
        filled = fill_substantive_template("direction", template).replace(
            "Assurance profile and why it fits: standard;",
            "Assurance profile and why it fits: showcase;",
        )
        body = module.split_frontmatter_text(
            filled,
            path=Path("direction.md"),
        )[2]
        standard = module.required_labels_for_record(
            "direction",
            body,
            {"standard"},
        )
        showcase = module.required_labels_for_record(
            "direction",
            body,
            {"showcase"},
        )
        self.assertEqual(showcase, standard)
        self.assertEqual(module.PROFILE_REQUIRED_LABELS, {})
        initializer_source = INIT.read_text(encoding="utf-8").casefold()
        for banned_recipe in (
            "hero-as-thesis",
            "high-energy moment",
            "quiet counterpoint",
            "signature relationship",
        ):
            self.assertNotIn(banned_recipe, initializer_source)

    def test_quick_direction_does_not_force_showcase_fields(
        self,
    ) -> None:
        module = load_initializer_module()
        template = (
            PLUGIN
            / "skills"
            / "design-dna"
            / "templates"
            / "direction-template.md"
        ).read_text(encoding="utf-8")
        filled = fill_substantive_template("direction", template).replace(
            "Assurance profile and why it fits: standard;",
            "Assurance profile and why it fits: quick;",
        )
        body = module.split_frontmatter_text(
            filled,
            path=Path("direction.md"),
        )[2]
        self.assertEqual(
            module.substantive_body_failures(
                "direction",
                body,
                required_assurance_profiles={"quick"},
            ),
            [],
        )
        self.assertNotIn("Creative logic", module.REQUIRED_RECORD_SECTIONS["direction"])
        self.assertNotIn("Assurance profile and why it fits", body)

    def test_exploration_completion_rejects_stale_candidate_hash(
        self,
    ) -> None:
        module = load_initializer_module()
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            initialized = run_python(
                INIT,
                "--project",
                str(project),
                "--record",
                "exploration",
                "--json",
            )
            self.assertEqual(
                initialized.returncode,
                0,
                initialized.stdout + initialized.stderr,
            )
            path = project / ".design-dna" / "exploration.md"
            evidence = project / "evidence"
            evidence.mkdir()
            artifact = evidence / "candidate-01.png"
            artifact.write_bytes(b"changed candidate proof")
            _artifact, failures = module.bound_artifact(
                "evidence/candidate-01.png plus sha256:" + ("0" * 64),
                project=project,
                record_path=path,
                label="Exploration candidate",
            )
            self.assertTrue(
                any(
                    "SHA-256 does not match" in failure
                    for failure in failures
                ),
                failures,
            )

    def test_exploration_allows_one_proportionate_candidate_and_proof(
        self,
    ) -> None:
        module = load_initializer_module()
        template = (
            PLUGIN
            / "skills"
            / "design-dna"
            / "templates"
            / "exploration-template.md"
        ).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            record_path = project / ".design-dna" / "exploration.md"
            record_path.parent.mkdir()
            filled = materialize_exploration_evidence(
                project,
                fill_substantive_template("exploration", template),
            )
            body = module.split_frontmatter_text(
                filled,
                path=record_path,
            )[2]
            sections = module.markdown_sections(body)
            self.assertEqual(
                set(module.REQUIRED_RECORD_SECTIONS["exploration"]),
                {
                    "Exploration intent",
                    "Evidence and candidate reasoning",
                    "Decision and limits",
                },
            )
            self.assertNotIn("Candidate field", sections)
            self.assertEqual(
                module.substantive_body_failures(
                    "exploration",
                    body,
                    project=project,
                    record_path=record_path,
                ),
                [],
            )

    def test_new_quality_sections_are_required_for_record_completion(
        self,
    ) -> None:
        module = load_initializer_module()
        skill = PLUGIN / "skills" / "design-dna"
        for record_name, headings in NEW_QUALITY_COMPLETION_SECTIONS.items():
            self.assertTrue(
                set(headings).issubset(
                    module.REQUIRED_RECORD_SECTIONS[record_name]
                ),
                f"{record_name} required-section contract drifted",
            )
            template_path = (
                skill
                / "templates"
                / module.RECORD_TEMPLATES[record_name][1]
            )
            filled = fill_substantive_template(
                record_name,
                template_path.read_text(encoding="utf-8"),
            )
            body = module.split_frontmatter_text(
                filled,
                path=template_path,
            )[2]
            for heading in headings:
                with self.subTest(record=record_name, heading=heading):
                    failures = module.substantive_body_failures(
                        record_name,
                        without_markdown_section(body, heading),
                    )
                    self.assertIn(
                        f"missing required sections: {heading}",
                        failures,
                    )

    def test_self_review_cannot_claim_owner_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            initialized = run_python(
                INIT,
                "--project",
                str(project),
                "--record",
                "direction-proof",
            )
            self.assertEqual(
                initialized.returncode,
                0,
                initialized.stdout + initialized.stderr,
            )
            record = project / ".design-dna" / "direction-proof.md"
            filled = fill_substantive_template(
                "direction-proof",
                record.read_text(encoding="utf-8"),
            ).replace(
                "Owner disposition: pending",
                "Owner disposition: accepted",
            )
            record.write_text(filled, encoding="utf-8", newline="\n")
            (project / "binding.txt").write_text(
                "exact direction proof\n",
                encoding="utf-8",
            )
            completed = run_python(
                INIT,
                "--project",
                str(project),
                "--mark-complete",
                "direction-proof",
                "--binding-kind",
                "artifact",
                "--binding-id",
                "direction-proof-build-42",
                "--binding-path",
                "binding.txt",
                "--completion-owner",
                "producer-1",
                "--limitations",
                "Owner acceptance remains pending.",
                "--json",
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn(
                "Accepted owner disposition requires an accountable-owner",
                completed.stderr,
            )

    def test_markdown_owner_decision_binds_candidate_date_and_evidence(
        self,
    ) -> None:
        module = load_initializer_module()
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            record_path = project / ".design-dna" / "visual-review.md"
            record_path.parent.mkdir(parents=True)
            evidence = project / "evidence" / "owner-decision.txt"
            evidence.parent.mkdir()
            evidence.write_text(
                (
                    "status: accepted\n"
                    "owner: owner-alex-morgan\n"
                    "candidate: build-42\n"
                    "reviewed: 2026-07-26\n"
                ),
                encoding="utf-8",
            )
            digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
            body = module.split_frontmatter_text(
                materialize_visual_review_evidence(
                    project,
                    complete_visual_review(),
                ),
                path=record_path,
            )[2]
            pending_disposition = (
                "Owner disposition: pending"
            )
            accepted_disposition = (
                "Owner disposition: accepted; "
                "scope=standard; owner_id=owner-alex-morgan; "
                "reviewed_date=2026-07-26; candidate=build-42; "
                f"evidence=evidence/owner-decision.txt | sha256:{digest}"
            )
            replacements = {
                "Reviewer relationship: producer-self":
                    "Reviewer relationship: accountable-owner",
                pending_disposition: accepted_disposition,
                "Reviewer conclusion: self-reviewed candidate":
                    "Reviewer conclusion: owner accepted",
            }
            for old, new in replacements.items():
                body = body.replace(old, new)
            self.assertEqual(
                module.substantive_body_failures(
                    "visual-review",
                    body,
                    project=project,
                    record_path=record_path,
                ),
                [],
            )

            wrong_candidate = body.replace(
                "candidate=build-42; evidence=evidence/owner-decision.txt",
                "candidate=build-41; evidence=evidence/owner-decision.txt",
            )
            self.assertIn(
                "Owner disposition candidate must match Build or artifact ID",
                "\n".join(module.substantive_body_failures(
                    "visual-review",
                    wrong_candidate,
                    project=project,
                    record_path=record_path,
                )),
            )

            wrong_hash = body.replace(
                f"evidence/owner-decision.txt | sha256:{digest}",
                "evidence/owner-decision.txt | sha256:" + ("f" * 64),
            )
            self.assertIn(
                "Owner disposition evidence sha256 does not match",
                "\n".join(module.substantive_body_failures(
                    "visual-review",
                    wrong_hash,
                    project=project,
                    record_path=record_path,
                )),
            )

    def test_cross_build_comparison_is_optional_but_explicit(self) -> None:
        module = load_initializer_module()
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            record_path = project / ".design-dna" / "visual-review.md"
            record_path.parent.mkdir(parents=True)
            body = module.split_frontmatter_text(
                materialize_visual_review_evidence(
                    project,
                    complete_visual_review(),
                ),
                path=record_path,
            )[2]
            self.assertEqual(
                module.substantive_body_failures(
                    "visual-review",
                    body,
                    project=project,
                    record_path=record_path,
                ),
                [],
            )
            required = module.required_labels_for_record(
                "visual-review",
                body,
            )
            self.assertNotIn(
                (
                    "Cross-build comparison identity, compatibility, changed "
                    "captures, reviewer, and result, or `not performed`"
                ),
                required,
            )
            self.assertNotIn(
                "Cross-build decision",
                required,
            )
            self.assertIn("Cross-build decision: not performed", body)

    def test_rendered_review_requires_schema_three_tool_identity(self) -> None:
        module = load_initializer_module()
        mutations = (
            ("schema_version", 2),
            ("tool.version", "2.0.0"),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as temporary:
                    project = Path(temporary) / "project"
                    record_path = project / ".design-dna" / "visual-review.md"
                    record_path.parent.mkdir(parents=True)
                    text = materialize_visual_review_evidence(
                        project,
                        complete_visual_review(),
                    )
                    report_path = (
                        project
                        / "evidence"
                        / "render-review"
                        / "render-review.json"
                    )
                    old_digest = hashlib.sha256(
                        report_path.read_bytes()
                    ).hexdigest()
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                    if field == "schema_version":
                        report["schema_version"] = value
                    else:
                        report["tool"]["version"] = value
                    report_path.write_text(
                        json.dumps(report, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    new_digest = hashlib.sha256(
                        report_path.read_bytes()
                    ).hexdigest()
                    text = text.replace(old_digest, new_digest)
                    body = module.split_frontmatter_text(
                        text,
                        path=record_path,
                    )[2]
                    self.assertIn(
                        "schema-3, tool-3.0.0 identity",
                        "\n".join(
                            module.substantive_body_failures(
                                "visual-review",
                                body,
                                project=project,
                                record_path=record_path,
                            )
                        ),
                    )

    def test_declared_cross_build_comparison_binds_schema_and_review(
        self,
    ) -> None:
        module = load_initializer_module()
        schema = json.loads(
            (
                SCHEMAS / "render-comparison.schema.json"
            ).read_text(encoding="utf-8")
        )
        payload = render_comparison_payload()
        self.assertEqual(
            list(Draft202012Validator(schema).iter_errors(payload)),
            [],
        )
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            record_path = project / ".design-dna" / "visual-review.md"
            record_path.parent.mkdir(parents=True)
            text = materialize_visual_review_evidence(
                project,
                complete_visual_review(),
            )
            text = materialize_render_comparison_evidence(
                project,
                text,
                payload=payload,
            )
            body = module.split_frontmatter_text(
                text,
                path=record_path,
            )[2]
            self.assertEqual(
                module.substantive_body_failures(
                    "visual-review",
                    body,
                    project=project,
                    record_path=record_path,
                ),
                [],
            )

            report_path = (
                project
                / "evidence"
                / "render-comparison"
                / "render-comparison.json"
            )
            report_digest = hashlib.sha256(
                report_path.read_bytes()
            ).hexdigest()
            stale_binding = body.replace(
                f"render-comparison.json plus sha256:{report_digest}",
                "render-comparison.json plus sha256:" + ("0" * 64),
            )
            self.assertIn(
                "Cross-build comparison report binding SHA-256 does not match its artifact",
                module.substantive_body_failures(
                    "visual-review",
                    stale_binding,
                    project=project,
                    record_path=record_path,
                ),
            )

            no_decision = body.replace(
                (
                    "Cross-build decision: accept candidate; "
                    "reviewer-7 inspected"
                ),
                (
                    "Cross-build decision: not performed; "
                    "reviewer-7 did not inspect"
                ),
            )
            self.assertTrue(
                any(
                    "declared cross-build comparison report requires"
                    in item
                    for item in module.substantive_body_failures(
                        "visual-review",
                        no_decision,
                        project=project,
                        record_path=record_path,
                    )
                )
            )

    def test_cross_build_report_cannot_self_approve_or_drop_manual_review(
        self,
    ) -> None:
        module = load_initializer_module()
        cases = []
        machine_approved = render_comparison_payload()
        machine_approved["automatic_visual_approval"] = True
        cases.append(
            (
                machine_approved,
                "automatic_visual_approval=false",
            )
        )
        missing_review = render_comparison_payload()
        missing_review["manual_review"] = {
            "status": "complete",
            "required_actions": [],
            "limitations": [],
        }
        cases.append(
            (
                missing_review,
                "manual-review actions and limitations",
            )
        )
        wrong_candidate = render_comparison_payload(
            candidate_build_id="build-43",
        )
        cases.append(
            (
                wrong_candidate,
                "candidate build ID must match",
            )
        )
        for payload, expected in cases:
            with self.subTest(expected=expected):
                with tempfile.TemporaryDirectory() as temporary:
                    project = Path(temporary) / "project"
                    record_path = (
                        project / ".design-dna" / "visual-review.md"
                    )
                    record_path.parent.mkdir(parents=True)
                    text = materialize_visual_review_evidence(
                        project,
                        complete_visual_review(),
                    )
                    text = materialize_render_comparison_evidence(
                        project,
                        text,
                        payload=payload,
                    )
                    body = module.split_frontmatter_text(
                        text,
                        path=record_path,
                    )[2]
                    self.assertIn(
                        expected,
                        "\n".join(
                            module.substantive_body_failures(
                                "visual-review",
                                body,
                                project=project,
                                record_path=record_path,
                            )
                        ),
                    )

    def test_visual_review_owner_disposition_is_executable(self) -> None:
        pending_disposition = "Owner disposition: pending"
        cases = (
            (
                {
                    pending_disposition: "Owner disposition: accepted",
                    "Reviewer conclusion: self-reviewed candidate":
                        "Reviewer conclusion: owner accepted",
                },
                "A producer-self visual review cannot claim independent, "
                "target-user, or owner acceptance",
            ),
            (
                {
                    pending_disposition: "Owner disposition: rejected",
                },
                "Rejected owner disposition requires Reviewer conclusion blocked",
            ),
            (
                {
                    "Reviewer conclusion: self-reviewed candidate":
                        "Reviewer conclusion: blocked",
                },
                "Reviewer conclusion blocked requires an explicit unresolved release blocker",
            ),
        )
        for replacements, expected_message in cases:
            with self.subTest(expected_message=expected_message):
                with tempfile.TemporaryDirectory() as temporary:
                    project = Path(temporary) / "project"
                    project.mkdir()
                    initialized = run_python(
                        INIT,
                        "--project",
                        str(project),
                        "--record",
                        "visual-review",
                    )
                    self.assertEqual(
                        initialized.returncode,
                        0,
                        initialized.stdout + initialized.stderr,
                    )
                    text = complete_visual_review()
                    for old, new in replacements.items():
                        text = text.replace(old, new)
                    text = materialize_visual_review_evidence(project, text)
                    record = project / ".design-dna" / "visual-review.md"
                    record.write_text(text, encoding="utf-8", newline="\n")
                    (project / "binding.txt").write_text(
                        "exact visual review build\n",
                        encoding="utf-8",
                    )
                    completed = run_python(
                        INIT,
                        "--project",
                        str(project),
                        "--mark-complete",
                        "visual-review",
                        "--binding-kind",
                        "artifact",
                        "--binding-id",
                        "visual-review-build-42",
                        "--binding-path",
                        "binding.txt",
                        "--completion-owner",
                        "reviewer-7",
                        "--limitations",
                        "Owner disposition is recorded in the review.",
                        "--json",
                    )
                    self.assertEqual(completed.returncode, 2)
                    self.assertIn(expected_message, completed.stderr)

    def test_completed_record_binds_body_and_artifact_and_can_return_to_draft(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            initialized = run_python(
                INIT,
                "--project",
                str(project),
                "--record",
                "visual-review",
            )
            self.assertEqual(
                initialized.returncode,
                0,
                initialized.stdout + initialized.stderr,
            )
            record = project / ".design-dna" / "visual-review.md"
            record.write_text(
                materialize_visual_review_evidence(
                    project,
                    complete_visual_review(),
                ),
                encoding="utf-8",
                newline="\n",
            )
            artifact = project / "review-artifact.txt"
            artifact.write_text("exact reviewed build\n", encoding="utf-8")
            completed = run_python(
                INIT,
                "--project",
                str(project),
                "--mark-complete",
                "visual-review",
                "--binding-kind",
                "build",
                "--binding-id",
                "build-42",
                "--binding-path",
                "review-artifact.txt",
                "--completion-owner",
                "reviewer-7",
                "--limitations",
                "No known limitations within the recorded design scope.",
                "--json",
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )
            self.assertEqual(
                list(project.glob(".design-dna.backup-*")),
                [],
                "a verified completion marker must not retain a full state copy",
            )
            check = run_python(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

            artifact.write_text("changed build\n", encoding="utf-8")
            stale_artifact = run_python(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(stale_artifact.returncode, 1)
            self.assertIn("binding_sha256", stale_artifact.stdout)
            artifact.write_text(
                "exact reviewed build\n",
                encoding="utf-8",
            )

            record.write_text(
                record.read_text(encoding="utf-8") + "\nchanged\n",
                encoding="utf-8",
            )
            stale_body = run_python(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(stale_body.returncode, 1)
            self.assertIn("record_body_sha256", stale_body.stdout)

            drafted = run_python(
                INIT,
                "--project",
                str(project),
                "--mark-draft",
                "visual-review",
            )
            self.assertEqual(
                drafted.returncode,
                0,
                drafted.stdout + drafted.stderr,
            )
            self.assertEqual(
                list(project.glob(".design-dna.backup-*")),
                [],
                "returning a record to draft must not retain a full state copy",
            )
            draft_text = record.read_text(encoding="utf-8")
            self.assertIn('record_status: "draft"', draft_text)
            self.assertNotIn("binding_sha256:", draft_text)
            draft_check = run_python(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(
                draft_check.returncode,
                0,
                draft_check.stdout + draft_check.stderr,
            )

    def test_blank_template_cannot_be_marked_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            initialized = run_python(
                INIT,
                "--project",
                str(project),
                "--record",
                "direction",
            )
            self.assertEqual(initialized.returncode, 0)
            (project / "proof.txt").write_text("proof\n", encoding="utf-8")
            completed = run_python(
                INIT,
                "--project",
                str(project),
                "--mark-complete",
                "direction",
                "--binding-kind",
                "artifact",
                "--binding-id",
                "direction-proof-1",
                "--binding-path",
                "proof.txt",
                "--completion-owner",
                "reviewer-7",
                "--limitations",
                "No known limitations within the direction-decision scope.",
                "--json",
            )
            self.assertEqual(completed.returncode, 2)
            error = json.loads(completed.stderr)
            self.assertEqual(error["error"]["code"], "record-not-substantive")
            self.assertFalse(
                list(project.glob(".design-dna.backup-*")),
                "pre-validation failures must not move the live state",
            )

    def test_unresolved_high_or_medium_finding_blocks_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            self.assertEqual(
                run_python(
                    INIT,
                    "--project",
                    str(project),
                    "--record",
                    "visual-review",
                ).returncode,
                0,
            )
            record = project / ".design-dna" / "visual-review.md"
            record.write_text(
                complete_visual_review().replace(
                    "| verified | reviewer-7 |",
                    "| deferred | reviewer-7 |",
                ),
                encoding="utf-8",
                newline="\n",
            )
            (project / "proof.txt").write_text("proof\n", encoding="utf-8")
            completed = run_python(
                INIT,
                "--project",
                str(project),
                "--mark-complete",
                "visual-review",
                "--binding-kind",
                "artifact",
                "--binding-id",
                "review-42",
                "--binding-path",
                "proof.txt",
                "--completion-owner",
                "reviewer-7",
                "--limitations",
                "No known limitations within the recorded design scope.",
                "--json",
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn(
                "complete records require verified or not-applicable closure",
                completed.stderr,
            )

    def test_visual_review_requires_a_real_finding_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            self.assertEqual(
                run_python(
                    INIT,
                    "--project",
                    str(project),
                    "--record",
                    "visual-review",
                ).returncode,
                0,
            )
            record = project / ".design-dna" / "visual-review.md"
            record.write_text(
                complete_visual_review().replace(
                    "| verified | reviewer-7 |",
                    "| verified | not-recorded (legacy schema-1) |",
                ),
                encoding="utf-8",
                newline="\n",
            )
            (project / "proof.txt").write_text("proof\n", encoding="utf-8")
            completed = run_python(
                INIT,
                "--project",
                str(project),
                "--mark-complete",
                "visual-review",
                "--binding-kind",
                "artifact",
                "--binding-id",
                "review-43",
                "--binding-path",
                "proof.txt",
                "--completion-owner",
                "reviewer-7",
                "--limitations",
                "No known limitations within the recorded design scope.",
                "--json",
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn(
                "Findings requires an explicit owner cell",
                completed.stderr,
            )

    def test_current_state_migration_is_idempotent_and_leaves_no_recovery_debris(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            initialized = run_python(
                INIT,
                "--project",
                str(project),
                "--record",
                "direction",
                "--json",
            )
            self.assertEqual(
                initialized.returncode,
                0,
                initialized.stdout + initialized.stderr,
            )
            state_root = project / ".design-dna"
            before = {
                path.relative_to(state_root).as_posix(): path.read_bytes()
                for path in state_root.rglob("*")
                if path.is_file()
            }

            for _attempt in range(2):
                migrated = run_python(
                    INIT,
                    "--project",
                    str(project),
                    "--migrate",
                    "--json",
                )
                self.assertEqual(
                    migrated.returncode,
                    0,
                    migrated.stdout + migrated.stderr,
                )
                payload = json.loads(migrated.stdout)
                self.assertEqual(
                    [item["action"] for item in payload["actions"]],
                    ["migration-not-needed"],
                )
                self.assertEqual(
                    list(project.glob(".design-dna.backup-*")),
                    [],
                )
                self.assertEqual(
                    list(project.glob(".design-dna-migrate-*")),
                    [],
                )
                self.assertFalse((state_root / "migration-report.json").exists())
                after = {
                    path.relative_to(state_root).as_posix(): path.read_bytes()
                    for path in state_root.rglob("*")
                    if path.is_file()
                }
                self.assertEqual(after, before)

    def test_migration_is_dry_runnable_preserves_history_and_hash_binds_legacy(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            self.assertEqual(
                run_python(
                    INIT,
                    "--project",
                    str(project),
                    "--record",
                    "direction",
                ).returncode,
                0,
            )
            record = project / ".design-dna" / "direction.md"
            original = record.read_text(encoding="utf-8").replace(
                'record_status: "draft"\n',
                "",
                1,
            )
            record.write_text(original, encoding="utf-8", newline="\n")
            legacy = project / ".design-dna" / "state.yml"
            legacy.write_text("legacy: exact-history\n", encoding="utf-8")
            legacy_hash = hashlib.sha256(legacy.read_bytes()).hexdigest()

            dry_run = run_python(
                INIT,
                "--project",
                str(project),
                "--migrate",
                "--dry-run",
                "--json",
            )
            self.assertEqual(
                dry_run.returncode,
                0,
                dry_run.stdout + dry_run.stderr,
            )
            self.assertNotIn(
                "record_status:",
                record.read_text(encoding="utf-8"),
            )
            self.assertFalse(
                (project / ".design-dna" / "migration-report.json").exists()
            )

            migrated = run_python(
                INIT,
                "--project",
                str(project),
                "--migrate",
                "--json",
            )
            self.assertEqual(
                migrated.returncode,
                0,
                migrated.stdout + migrated.stderr,
            )
            self.assertIn(
                'record_status: "draft"',
                record.read_text(encoding="utf-8"),
            )
            report = json.loads(
                (
                    project
                    / ".design-dna"
                    / "migration-report.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(report["record_updates"], ["direction"])
            self.assertEqual(
                report["legacy_files"][0]["sha256"],
                legacy_hash,
            )
            self.assertTrue(list(project.glob(".design-dna.backup-*")))
            check = run_python(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

            legacy.write_text("changed\n", encoding="utf-8")
            changed = run_python(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(changed.returncode, 1)
            self.assertIn("hash changed", changed.stdout)

    def test_schema_one_visual_reviews_migrate_losslessly_to_exact_contract(
        self,
    ) -> None:
        contracts = (
            (
                "six-column-completed-finding",
                "legacy-schema-1-six-column",
                "| Severity | Evidence | Cause | Fix | Verification | Status |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| High | evidence/legacy.png | Navigation clipped | Reworked navigation | Rechecked at 390 pixels | fixed |",
            ),
            (
                "six-column-untouched-scaffold",
                "legacy-schema-1-six-column",
                "| Severity | Evidence | Cause | Fix | Verification | Status |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "|  |  |  |  |  | fixed, accepted, deferred, or blocked |",
            ),
            (
                "eight-column-completed-finding",
                "design-dna-2.2-eight-column",
                "| Severity | Confidence | Evidence | User/release impact | Cause | Fix | Rerun verification | Status/owner |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| High | high | evidence/legacy.png | Navigation was unusable | Navigation clipped | Reworked navigation | Rechecked at 390 pixels | fixed / reviewer-7 |",
            ),
            (
                "eight-column-untouched-scaffold",
                "design-dna-2.2-eight-column",
                "| Severity | Confidence | Evidence | User/release impact | Cause | Fix | Rerun verification | Status/owner |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| critical / high / medium / low / note | high / medium / low |  |  |  |  |  | fixed / accepted / deferred / blocked |",
            ),
        )
        for case_name, expected_contract, legacy_table in contracts:
            with self.subTest(case=case_name, contract=expected_contract):
                with tempfile.TemporaryDirectory() as temporary:
                    project = Path(temporary) / "project"
                    project.mkdir()
                    initialized = run_python(
                        INIT,
                        "--project",
                        str(project),
                        "--record",
                        "visual-review",
                    )
                    self.assertEqual(
                        initialized.returncode,
                        0,
                        initialized.stdout + initialized.stderr,
                    )
                    record = project / ".design-dna" / "visual-review.md"
                    text = record.read_text(encoding="utf-8")
                    text = text.replace(
                        'findings_contract: "visual-review-findings-v2"\n',
                        "",
                        1,
                    )
                    findings_start = text.index(
                        "| Severity | Confidence | Evidence |"
                    )
                    findings_end = text.index(
                        "\n\n## Owner and release state",
                        findings_start,
                    )
                    source_text = (
                        text[:findings_start]
                        + legacy_table
                        + text[findings_end:]
                    )
                    record.write_text(
                        source_text,
                        encoding="utf-8",
                        newline="\n",
                    )

                    migrated = run_python(
                        INIT,
                        "--project",
                        str(project),
                        "--migrate",
                        "--json",
                    )
                    self.assertEqual(
                        migrated.returncode,
                        0,
                        migrated.stdout + migrated.stderr,
                    )
                    current = record.read_text(encoding="utf-8")
                    self.assertIn(
                        'findings_contract: "visual-review-findings-v2"',
                        current,
                    )
                    self.assertIn('record_status: "draft"', current)
                    self.assertIn(
                        "| Severity | Confidence | Evidence | "
                        "User/release impact | Cause | Fix or disposition | "
                        "Rerun verification | Status | Owner |",
                        current,
                    )
                    report = json.loads(
                        (
                            project
                            / ".design-dna"
                            / "migration-report.json"
                        ).read_text(encoding="utf-8")
                    )
                    entry = report["visual_review_migrations"][-1]
                    self.assertEqual(
                        expected_contract,
                        entry["source_contract"],
                    )
                    self.assertEqual(legacy_table, entry["source_table"])
                    self.assertEqual(
                        hashlib.sha256(
                            legacy_table.encode("utf-8")
                        ).hexdigest(),
                        entry["source_table_sha256"],
                    )
                    self.assertIn(
                        "visual-review",
                        report["record_updates"],
                    )
                    schema = json.loads(
                        (
                            SCHEMAS
                            / "project-state-migration.schema.json"
                        ).read_text(encoding="utf-8")
                    )
                    Draft202012Validator(schema).validate(report)
                    backups = list(
                        project.glob(".design-dna.backup-*")
                    )
                    self.assertEqual(len(backups), 1)
                    self.assertEqual(
                        source_text,
                        (backups[0] / "visual-review.md").read_text(
                            encoding="utf-8"
                        ),
                    )
                    checked = run_python(
                        INIT,
                        "--project",
                        str(project),
                        "--check-state",
                        "--json",
                    )
                    self.assertEqual(
                        checked.returncode,
                        0,
                        checked.stdout + checked.stderr,
                    )


class ProjectStateConcurrencyTests(unittest.TestCase):
    HOLDER = r"""
import importlib.util
import os
import sys
import time
from pathlib import Path

script, project, ready, behavior = map(Path, sys.argv[1:5])
specification = importlib.util.spec_from_file_location(
    "design_dna_lock_holder",
    script,
)
module = importlib.util.module_from_spec(specification)
specification.loader.exec_module(module)
lock = module.ProjectMutationLock(project, "concurrency-holder", timeout=1.0)
lock.acquire()
ready.write_text("ready", encoding="utf-8")
if str(behavior) == "crash":
    os._exit(0)
time.sleep(float(str(behavior)))
failure = lock.release()
if failure is not None:
    raise failure
"""

    def wait_ready(
        self,
        process: subprocess.Popen[str],
        ready: Path,
    ) -> None:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if ready.is_file():
                return
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                self.fail(
                    "Lock holder exited before readiness.\n"
                    f"stdout={stdout}\nstderr={stderr}"
                )
            time.sleep(0.02)
        process.kill()
        stdout, stderr = process.communicate()
        self.fail(
            "Timed out waiting for lock holder.\n"
            f"stdout={stdout}\nstderr={stderr}"
        )

    def start_holder(
        self,
        project: Path,
        ready: Path,
        behavior: str,
    ) -> subprocess.Popen[str]:
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-c",
                self.HOLDER,
                str(INIT),
                str(project),
                str(ready),
                behavior,
            ],
            cwd=PLUGIN,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
        self.wait_ready(process, ready)
        return process

    def run_with_timeout(
        self,
        project: Path,
        *arguments: str,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["DESIGN_DNA_LOCK_TIMEOUT_SECONDS"] = "0.15"
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(INIT),
                "--project",
                str(project),
                *arguments,
            ],
            cwd=PLUGIN,
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=environment,
            timeout=30,
        )

    def test_two_processes_never_promote_under_the_same_project_lock(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            ready = Path(temporary) / "ready"
            # Leave ample room for a cold Windows interpreter startup so this
            # tests lock exclusion rather than scheduler timing.
            holder = self.start_holder(project, ready, "2.0")
            contender = self.run_with_timeout(project, "--json")
            self.assertEqual(contender.returncode, 2)
            error = json.loads(contender.stderr)["error"]
            self.assertEqual("project-state-locked", error["code"])
            self.assertFalse((project / ".design-dna").exists())
            stdout, stderr = holder.communicate(timeout=10)
            self.assertEqual(
                holder.returncode,
                0,
                stdout + stderr,
            )

            initialized = self.run_with_timeout(project, "--json")
            self.assertEqual(
                initialized.returncode,
                0,
                initialized.stdout + initialized.stderr,
            )
            self.assertTrue((project / ".design-dna").is_dir())
            lock_path = project / ".design-dna.lock"
            self.assertTrue(lock_path.is_file())
            record = lock_record(lock_path)
            self.assertEqual("released", record["status"])
            self.assertIsNotNone(record["released_at"])

    def test_stale_owner_metadata_is_preserved_and_os_lock_is_reused(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            ready = Path(temporary) / "ready"
            crashed = self.start_holder(project, ready, "crash")
            stdout, stderr = crashed.communicate(timeout=10)
            self.assertEqual(crashed.returncode, 0, stdout + stderr)
            stale = lock_record(project / ".design-dna.lock")
            self.assertEqual("active", stale["status"])

            initialized = self.run_with_timeout(project, "--json")
            self.assertEqual(
                initialized.returncode,
                0,
                initialized.stdout + initialized.stderr,
            )
            actions = json.loads(initialized.stdout)["actions"]
            self.assertTrue(
                any(
                    item["action"] == "stale-lock-recovered"
                    for item in actions
                )
            )
            current = lock_record(project / ".design-dna.lock")
            self.assertEqual("released", current["status"])
            predecessor = current["stale_predecessor"]
            self.assertEqual(stale["owner_token"], predecessor["owner_token"])
            self.assertRegex(
                predecessor["record_sha256"],
                r"^[0-9a-f]{64}$",
            )

    def test_stage_cleanup_requires_exact_owner_and_refuses_reparse(
        self,
    ) -> None:
        initializer = load_initializer_module()
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            stage = project / ".design-dna-stage-owned"
            stage.mkdir()
            marker = stage / initializer.STAGE_OWNER_RECORD
            marker.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "record_type": "design-dna-state-stage-owner",
                        "owner_token": "other-owner",
                        "created_at": "2026-07-28T12:00:00+00:00",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            payload = stage / "payload.txt"
            payload.write_text("preserve me\n", encoding="utf-8")
            mismatch = initializer.cleanup_stage_parent(
                stage,
                project,
                "current-owner",
            )
            self.assertIsNotNone(mismatch)
            self.assertEqual("stage-owner-mismatch", mismatch.code)
            self.assertTrue(payload.is_file())

            marker.write_text(
                marker.read_text(encoding="utf-8").replace(
                    "other-owner",
                    "current-owner",
                ),
                encoding="utf-8",
            )
            real_is_reparse = initializer.is_reparse

            def simulated_reparse(path: Path) -> bool:
                if path == payload:
                    return True
                return real_is_reparse(path)

            with patch.object(
                initializer,
                "is_reparse",
                side_effect=simulated_reparse,
            ):
                refused = initializer.cleanup_stage_parent(
                    stage,
                    project,
                    "current-owner",
                )
            self.assertIsNotNone(refused)
            self.assertEqual("reparse-point-refused", refused.code)
            self.assertTrue(payload.is_file())

    def test_invalid_migration_candidate_cleans_owned_stage_and_preserves_live_state(
        self,
    ) -> None:
        initializer = load_initializer_module()
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            initialized = run_python(
                INIT,
                "--project",
                str(project),
                "--json",
            )
            self.assertEqual(
                initialized.returncode,
                0,
                initialized.stdout + initialized.stderr,
            )
            state_root = project / ".design-dna"
            before = initializer.state_tree_identity(state_root)

            def invalidate_candidate(staged: Path) -> None:
                (staged / "direction.md").unlink()

            with self.assertRaises(initializer.StateError) as raised:
                initializer.mutate_state_transaction(
                    project,
                    initializer.release_version(INIT.parents[1]),
                    action="migrated",
                    dry_run=False,
                    mutator=invalidate_candidate,
                )

            self.assertEqual("staged-state-invalid", raised.exception.code)
            self.assertEqual(
                initializer.state_tree_identity(state_root),
                before,
            )
            self.assertEqual(list(project.glob(".design-dna-migrate-*")), [])
            self.assertEqual(list(project.glob(".design-dna.backup-*")), [])

    def test_live_state_drift_before_promotion_is_preserved_and_refused(
        self,
    ) -> None:
        initializer = load_initializer_module()
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            first = run_python(
                INIT,
                "--project",
                str(project),
                "--json",
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            state = project / ".design-dna"
            drift = state / "concurrent-owner-note.txt"
            original_validate = initializer.validate_state_in_place

            def mutate_live_then_validate(
                staged: Path,
                staged_project: Path,
                version: str,
            ) -> tuple[list[str], list[str]]:
                result = original_validate(
                    staged,
                    staged_project,
                    version,
                )
                drift.write_text(
                    "another writer's exact work\n",
                    encoding="utf-8",
                )
                return result

            with patch.object(
                initializer,
                "validate_state_in_place",
                side_effect=mutate_live_then_validate,
            ):
                with self.assertRaises(initializer.StateError) as raised:
                    initializer.install_transaction(
                        project,
                        INIT.parents[1],
                        ("direction", "visual-review"),
                        force=False,
                        dry_run=False,
                        version=initializer.release_version(
                            INIT.parents[1]
                        ),
                    )
            self.assertEqual("source-state-changed", raised.exception.code)
            self.assertEqual(
                "another writer's exact work\n",
                drift.read_text(encoding="utf-8"),
            )
            self.assertFalse(
                list(project.glob(".design-dna.failed-*"))
            )


class EvaluationModelContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPTS))
        cls.audit = importlib.import_module("audit_package")
        sys.path.pop(0)

    def test_runner_records_declared_context_and_inherits_control_baseline(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = run_eval(
                root,
                "--skill-provider",
                "openai",
                "--skill-model",
                "gpt-test",
                "--skill-model-version",
                "2026-07-28",
                "--skill-reasoning-effort",
                "high",
                "--skill-generation-config",
                "temperature=0.2",
                "--skill-generation-config",
                "seed=42",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = only_result(root / "results")
            skill = payload["drivers"]["skill"]["model_context"]
            baseline = payload["drivers"]["baseline"]["model_context"]
            self.assertEqual(skill["declaration_status"], "declared")
            self.assertEqual(skill["provider"], "openai")
            self.assertEqual(
                skill["generation_config"],
                {"seed": 42, "temperature": 0.2},
            )
            skill_core = {
                key: value
                for key, value in skill.items()
                if key != "sha256"
            }
            self.assertEqual(
                skill["sha256"],
                hashlib.sha256(
                    json.dumps(
                        skill_core,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
            )
            self.assertEqual(
                baseline["declaration_source"],
                "inherited-from-skill",
            )
            self.assertEqual(baseline["model"], skill["model"])

    def test_runner_records_unreported_context_without_inventing_identity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = run_eval(root, baseline=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            context = only_result(root / "results")["drivers"]["skill"][
                "model_context"
            ]
            self.assertEqual(context["declaration_status"], "unreported")
            self.assertIsNone(context["provider"])
            self.assertEqual(context["generation_config"], {})

    def test_partial_or_secret_model_metadata_fails_before_result_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first"
            first.mkdir()
            partial = run_eval(
                first,
                "--skill-provider",
                "openai",
                baseline=False,
            )
            self.assertEqual(partial.returncode, 2)
            self.assertIn("incomplete-model-context", partial.stdout)
            self.assertEqual(list((first / "results").glob("*.json")), [])

            second = Path(temporary) / "second"
            second.mkdir()
            secret = run_eval(
                second,
                "--skill-provider",
                "openai",
                "--skill-model",
                "gpt-test",
                "--skill-model-version",
                "2026-07-28",
                "--skill-reasoning-effort",
                "high",
                "--skill-generation-config",
                "tool_choice=Bearer secret-value",
                baseline=False,
            )
            self.assertEqual(secret.returncode, 2)
            self.assertIn(
                "sensitive-generation-config-refused",
                secret.stdout,
            )
            self.assertEqual(list((second / "results").glob("*.json")), [])

    def test_release_audit_rejects_unreported_drifted_or_unfair_context(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = run_eval(
                root,
                "--skill-provider",
                "openai",
                "--skill-model",
                "gpt-test",
                "--skill-model-version",
                "2026-07-28",
                "--skill-reasoning-effort",
                "high",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result_path = next((root / "results").glob("*.json"))
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            catalog, catalog_failures = self.audit.fixture_catalog(root)
            self.assertEqual(catalog_failures, [])

            def codes(candidate: dict[str, object]) -> set[str]:
                return {
                    item["code"]
                    for item in self.audit.eval_semantic_failures(
                        candidate,
                        catalog,
                        "result.json",
                        harness_path=RUN_EVALS,
                        suite_schema_path=PLUGIN
                        / "maintainer"
                        / "evals"
                        / "schema.json",
                        result_schema_path=SCHEMAS
                        / "eval-result.schema.json",
                        result_path=result_path,
                        release_mode=True,
                        trusted_adapters=set(),
                    )
                }

            self.assertNotIn(
                "release-model-context-unreported",
                codes(payload),
            )
            unreported = json.loads(json.dumps(payload))
            unreported_context = {
                "declaration_status": "unreported",
                "provider": None,
                "model": None,
                "model_version": None,
                "reasoning_effort": None,
                "generation_config": {},
                "declaration_source": "not-provided",
            }
            unreported_context["sha256"] = hashlib.sha256(
                json.dumps(
                    unreported_context,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            unreported["drivers"]["skill"]["model_context"] = (
                unreported_context
            )
            self.assertIn(
                "release-model-context-unreported",
                codes(unreported),
            )

            drifted = json.loads(json.dumps(payload))
            drifted["drivers"]["skill"]["model_context"]["sha256"] = "0" * 64
            self.assertIn(
                "eval-model-context-hash-mismatch",
                codes(drifted),
            )

            unfair = json.loads(json.dumps(payload))
            baseline_context = unfair["drivers"]["baseline"]["model_context"]
            baseline_context["model"] = "different-model"
            baseline_core = {
                key: value
                for key, value in baseline_context.items()
                if key != "sha256"
            }
            baseline_context["sha256"] = hashlib.sha256(
                json.dumps(
                    baseline_core,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            self.assertIn(
                "eval-model-context-comparison-mismatch",
                codes(unfair),
            )

    def test_review_binding_verifies_result_run_artifact_and_model(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = Path(temporary) / "plugin"
            result_path = (
                plugin
                / "maintainer"
                / "evals"
                / "results"
                / "bound.json"
            )
            result_path.parent.mkdir(parents=True)
            model_context = {
                "declaration_status": "declared",
                "provider": "openai",
                "model": "gpt-test",
                "model_version": "2026-07-28",
                "reasoning_effort": "high",
                "generation_config": {},
                "declaration_source": "maintainer-cli",
            }
            model_context["sha256"] = hashlib.sha256(
                json.dumps(
                    model_context,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            run_id = "model-context:codex:small-site:skill:1"
            result_payload = {
                "host": "codex",
                "package": {
                    "version": "3.0.0",
                    "content_sha256": "1" * 64,
                },
                "drivers": {
                    "skill": {"model_context": model_context},
                    "baseline": None,
                },
                "runs": [
                    {
                        "run_id": run_id,
                        "case": "small-site",
                        "variant": "skill",
                        "passed": True,
                        "artifact_bundle": {"sha256": "2" * 64},
                    }
                ],
            }
            result_path.write_text(
                json.dumps(result_payload, indent=2) + "\n",
                encoding="utf-8",
            )
            result_hash = hashlib.sha256(result_path.read_bytes()).hexdigest()
            review = {
                "case_id": "small-site",
                "run_id": run_id,
                "build": {
                    "host": "codex",
                    "skill_version": "3.0.0",
                    "content_sha256": "1" * 64,
                },
                "evaluation_binding": {
                    "result_path": "maintainer/evals/results/bound.json",
                    "result_sha256": result_hash,
                    "run_id": run_id,
                    "artifact_sha256": "2" * 64,
                    "model_context_sha256": model_context["sha256"],
                },
            }
            failures = self.audit.review_evaluation_binding_failures(
                review,
                plugin,
                "review.json",
                {result_path.resolve(): result_payload},
                release_mode=True,
            )
            self.assertEqual(failures, [])

            drifted = json.loads(json.dumps(review))
            drifted["evaluation_binding"]["artifact_sha256"] = "3" * 64
            self.assertIn(
                "review-evaluation-artifact-mismatch",
                {
                    item["code"]
                    for item in self.audit.review_evaluation_binding_failures(
                        drifted,
                        plugin,
                        "review.json",
                        {result_path.resolve(): result_payload},
                        release_mode=True,
                    )
                },
            )


class RepeatedEvaluationEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPTS))
        cls.module = importlib.import_module("validate_evidence")
        sys.path.pop(0)

    def make_result(
        self,
        root: Path,
        *,
        name: str,
        host: str,
        case: str,
        declared: bool = True,
    ) -> tuple[str, str]:
        relative = f"maintainer/evals/results/{name}.json"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        model_context = {
            "declaration_status": (
                "declared" if declared else "unreported"
            )
        }
        model_context["sha256"] = hashlib.sha256(
            json.dumps(
                model_context,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        result = {
            "host": host,
            "suite": "evidence-suite",
            "drivers": {
                "skill": {
                    "model_context": model_context
                }
            },
            "runs": [
                {
                    "run_id": f"evidence-suite:{host}:{case}:skill:1",
                    "case": case,
                    "variant": "skill",
                    "host": host,
                    "passed": True,
                    "invocation_mode": "explicit",
                    "artifact_bundle": {},
                }
            ],
        }
        data = (json.dumps(result, indent=2) + "\n").encode("utf-8")
        path.write_bytes(data)
        return relative, hashlib.sha256(data).hexdigest()

    def test_claims_are_derived_from_hash_bound_validated_results(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            schema_root = root / "maintainer" / "schemas"
            schema_root.mkdir(parents=True)
            (
                schema_root / "evaluation-evidence-bundle.schema.json"
            ).write_bytes(
                (
                    SCHEMAS / "evaluation-evidence-bundle.schema.json"
                ).read_bytes()
            )
            (schema_root / "eval-result.schema.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            first = self.make_result(
                root,
                name="codex-a",
                host="codex",
                case="project-a",
            )
            second = self.make_result(
                root,
                name="claude-b",
                host="claude_code",
                case="project-b",
            )
            bundle = root / "maintainer" / "evidence-bundle.json"
            bundle.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "record_type": (
                            "design-dna-repeated-evaluation-evidence"
                        ),
                        "created_at": "2026-07-28T12:00:00+00:00",
                        "owner": "reviewer-7",
                        "scope_note": (
                            "Two distinct project cases on two declared hosts."
                        ),
                        "result_files": [
                            {"path": first[0], "sha256": first[1]},
                            {"path": second[0], "sha256": second[1]},
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            hosts, projects, failures = (
                self.module.derive_repeated_evaluation_claims(root, bundle)
            )
            self.assertEqual(failures, [])
            self.assertEqual(hosts, {"codex", "claude_code"})
            self.assertEqual(
                projects,
                {
                    "evidence-suite/project-a",
                    "evidence-suite/project-b",
                },
            )

            unreported = self.make_result(
                root,
                name="unreported",
                host="codex",
                case="project-c",
                declared=False,
            )
            payload = json.loads(bundle.read_text(encoding="utf-8"))
            payload["result_files"][0] = {
                "path": unreported[0],
                "sha256": unreported[1],
            }
            bundle.write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
            )
            _, _, rejected = self.module.derive_repeated_evaluation_claims(
                root,
                bundle,
            )
            self.assertTrue(
                any(
                    item["code"] == "evaluation-model-unreported"
                    for item in rejected
                )
            )


if __name__ == "__main__":
    unittest.main()
