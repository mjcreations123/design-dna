#!/usr/bin/env python3
"""Regression coverage for public-reference direction records.

The dossier is research evidence, so every row must bind a capture the
producer actually looked at. These tests hold that line: a dossier of
plausible names with no captures is rejected, the count is a floor tied to
source spread rather than a quota, and selection must fit the exact brief.
"""

from __future__ import annotations

import concurrent.futures
import importlib.util
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
INITIALIZER_PATH = SKILL / "scripts" / "init_project_state.py"


def load_initializer():
    specification = importlib.util.spec_from_file_location(
        "design_dna_reference_dossier",
        INITIALIZER_PATH,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


INITIALIZER = load_initializer()

# Schema-4 fixtures intentionally contain the full 90s x 15fps wide/narrow
# frame ledger. Most frames are hard links because a settled test page can
# render identical pixels. Cache only by the filesystem's content identity;
# size/mtime changes invalidate the entry, so negative drift tests retain the
# exact production semantics without hashing and decoding one inode 1,200
# times per profile.
_ORIGINAL_FILE_SHA256 = INITIALIZER.file_sha256
_ORIGINAL_VERIFY_PNG = INITIALIZER.verify_png_artifact
_ORIGINAL_RECORDING_FAILURES = INITIALIZER.reference_recording_failures
_SHA_CACHE: dict[tuple[int, int, int, int], tuple[int, str]] = {}
_PNG_CACHE: dict[tuple[int, int, int, int], tuple[int, int]] = {}


def _artifact_identity(path: Path) -> tuple[int, int, int, int]:
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)


def _cached_file_sha256(path: Path) -> tuple[int, str]:
    key = _artifact_identity(path)
    if key not in _SHA_CACHE:
        _SHA_CACHE[key] = _ORIGINAL_FILE_SHA256(path)
    return _SHA_CACHE[key]


def _cached_verify_png(path: Path) -> tuple[int, int]:
    key = _artifact_identity(path)
    if key not in _PNG_CACHE:
        _PNG_CACHE[key] = _ORIGINAL_VERIFY_PNG(path)
    return _PNG_CACHE[key]


INITIALIZER.file_sha256 = _cached_file_sha256
INITIALIZER.verify_png_artifact = _cached_verify_png

_RECORDING_VALIDATION_CACHE: dict[
    tuple[str, str, str, str], tuple[tuple[str, ...], frozenset[tuple[str, int]]]
] = {}


def _cached_recording_failures(
    payload: object,
    *,
    recording: Path,
    ledger_payload: object,
    ledger: Path,
    state_contract: Path,
    state_contract_sha256: str,
    expected_reference_id: str,
) -> tuple[list[str], set[tuple[str, int]]]:
    # The complete immutable ledger is validated once for each byte-identical
    # fixture. Cache hits are hard-link clones of those same generated files;
    # malformed schema/tool/duration/event variants have distinct record or
    # ledger hashes and therefore still execute the production validator.
    key = (
        expected_reference_id,
        _ORIGINAL_FILE_SHA256(recording)[1],
        _ORIGINAL_FILE_SHA256(ledger)[1],
        _ORIGINAL_FILE_SHA256(state_contract)[1],
    )
    cached = _RECORDING_VALIDATION_CACHE.get(key)
    if cached is not None:
        return list(cached[0]), set(cached[1])
    failures, events = _ORIGINAL_RECORDING_FAILURES(
        payload,
        recording=recording,
        ledger_payload=ledger_payload,
        ledger=ledger,
        state_contract=state_contract,
        state_contract_sha256=state_contract_sha256,
        expected_reference_id=expected_reference_id,
    )
    _RECORDING_VALIDATION_CACHE[key] = (tuple(failures), frozenset(events))
    return failures, events


INITIALIZER.reference_recording_failures = _cached_recording_failures

_RECORDING_CACHE_TEMP = tempfile.TemporaryDirectory(prefix="design-dna-recording-fixtures-")
_RECORDING_CACHE_ROOT = Path(_RECORDING_CACHE_TEMP.name)
_RECORDING_CACHE: dict[tuple[object, ...], Path] = {}

STRONG_HEADER = (
    "| Rank | Reference title or visible entry | Public URL or gallery-entry URL "
    "| Discovery source and accolade | Retrieval date | Access status "
    "| Wide capture path and SHA-256 | Narrow capture path and SHA-256 "
    "| Pages, progression, and states studied | Observed evidence | Measured styles "
    "| Signature (motion or static; what a stranger would name) "
    "| Brief relevance | Design to copy | Rights boundary |"
)
STRONG_SEPARATOR = (
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
)
CANDIDATE_HEADER = "| " + " | ".join(INITIALIZER.REFERENCE_DOSSIER_CANDIDATE_HEADERS) + " |"
CANDIDATE_SEPARATOR = "| " + " | ".join("---" for _ in INITIALIZER.REFERENCE_DOSSIER_CANDIDATE_HEADERS) + " |"
NEGATIVE_HEADER = (
    "| Reference title or visible entry | Public URL or gallery-entry URL "
    "| Discovery source and accolade | Retrieval date | Access status | Capture path and SHA-256 "
    "| Observed mismatch or weak relationship | What this project must avoid |"
)
NEGATIVE_SEPARATOR = "| --- | --- | --- | --- | --- | --- | --- | --- |"
SYNTHESIS_HEADER = (
    "| Selected rank(s) | Design copied and destination | Project-specific adaptation "
    "| Boundary or verification |"
)
SYNTHESIS_SEPARATOR = "| --- | --- | --- | --- |"
COMPONENT_HEADER = (
    "| Component | Source rank | Frame that shows it "
    "| Structure taken | Recorded values reproduced | Where it is used |"
)
COMPONENT_HEADER_LEGACY = (
    "| Component | Source rank or owner approval | Frame that shows it "
    "| Structure taken | Recorded values reproduced | Where it is used |"
)
COMPONENT_SEPARATOR = "| --- | --- | --- | --- | --- | --- |"
TRANSFER_HEADER = (
    "| Rank | Signature, copied from the strong row "
    "| The build part that carries it | Recorded proof "
    "| What a stranger would lose if this reference were cut |"
)
TRANSFER_SEPARATOR = "| --- | --- | --- | --- | --- |"
INTERACTION_HEADER = "| " + " | ".join(INITIALIZER.REFERENCE_INTERACTION_CENSUS_HEADERS) + " |"
INTERACTION_SEPARATOR = "| " + " | ".join("---" for _ in INITIALIZER.REFERENCE_INTERACTION_CENSUS_HEADERS) + " |"
# a verbatim slice of the fixture signature, long enough to clear the floor
TRANSFER_SIGNATURE = (
    "motion: The product images slide sideways under a pinned heading as the "
    "page is scrolled"
)
TRANSFER_LOSS = (
    "the first screen would stop holding its heading while the product rail "
    "travels through it, and that arrangement would go with it"
)
FRAME_CELL = "strong-1-frames/strong-1-001-rest.png"
# a rest frame cannot show a first screen arriving, a nav responding, a button
# under the pointer, a scroll or a hover; those rows cite a recording sheet
SHEET_FRAME_CELL = "strong-1-wide-events/e0004-click.png"
EVENT_FRAME_CELL = SHEET_FRAME_CELL
BEHAVIOUR_COMPONENTS = (
    "first screen", "navigation", "buttons", "scroll behavior", "hover behavior",
)
SEQUENCE_LINE = (
    "the cursor lands on the top-left photograph and the cell grows to half "
    "the viewport while a label decodes beside the pointer"
)
INVENTORY_ROW = (
    "| hover a nav cell | the cell | grows to half the viewport and pushes its "
    "neighbours | 5x over 0.6s | s004, s005 |"
)

def frame_for(name: str) -> str:
    """A rest frame cannot show what a behaviour-bearing component does."""
    return SHEET_FRAME_CELL if name in BEHAVIOUR_COMPONENTS else FRAME_CELL

REQUIRED_COMPONENTS = (
    "first screen", "layout grid", "display typeface", "text typeface",
    "color behavior", "section rhythm", "navigation", "buttons",
    "rows or lists", "footer", "scroll behavior", "hover behavior",
)
STRUCTURE_CELL = (
    "a full-bleed photograph fills the first screen with the wordmark broken "
    "into the four corners"
)
VALUES_CELL = (
    "pinned stage held for 2400px while its content swapped 3 times, hover "
    "transition 450ms"
)
# The numbers the fixture's measured-style records contain, so the default body
# passes the value cross-check.
MEASURED_NUMBERS = [
    1, 1.1, 1.25, 1.4, 2, 3, 12, 14, 16, 20, 24, 26, 30, 36, 40, 44, 48, 60,
    100, 108, 120, 122, 240, 300, 400, 450, 500, 650, 900, 999, 2400, 3014,
]

# Six references spread over three sources so the default body satisfies the
# spread floor while no source supplies more than half of the rows.
# Every default source is award or curated; a submission feed cannot supply a
# selected reference in 7.0.0.
DEFAULT_SOURCES = (
    "awwwards; Site of the Day 2026-08-14",
    "awwwards; Site of the Month, July 2026",
    "godly; editor's pick, 2026-08-02",
    "godly; editor's pick, 2026-07-19",
    "typewolf; Site of the Day 2026-06-30",
    "site-of-sites; editor's pick, 2026-05-11",
)


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def write_png(
    path: Path,
    width: int = 8,
    height: int = 8,
    rgb: tuple[int, int, int] = (0x22, 0x66, 0xAA),
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = b"\x00" + (bytes(rgb) * width)
    raw = row * height
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw, 9))
        + png_chunk(b"IEND", b"")
    )
    path.write_bytes(payload)


def sha256_of(path: Path) -> str:
    return INITIALIZER.file_sha256(path)[1]


def runtime_evidence(tool: str, **values: object) -> dict[str, object]:
    script = SKILL / "scripts" / tool
    digest = sha256_of(script)
    return {
        "tool": tool,
        "schema_version": INITIALIZER.packaged_script_schema_version(script),
        "producer_script_sha256": digest,
        "runtime_identity": {tool: digest},
        **values,
    }


def clone_fixture_tree(source: Path, destination: Path) -> None:
    if os.name == "nt" and shutil.which("robocopy"):
        destination.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            [
                "robocopy", str(source), str(destination), "/E", "/MT:32",
                "/NFL", "/NDL", "/NJH", "/NJS", "/NC", "/NS", "/NP",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode < 8:
            return
    files = [item for item in source.rglob("*") if item.is_file()]
    for directory in {
        (destination / item.relative_to(source)).parent for item in files
    }:
        directory.mkdir(parents=True, exist_ok=True)

    def clone(item: Path) -> None:
        target = destination / item.relative_to(source)
        if target.exists():
            target.unlink()
        if item.suffix.casefold() == ".png":
            try:
                os.link(item, target)
                return
            except OSError:
                pass
        shutil.copyfile(item, target)

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        list(executor.map(clone, files))


def cache_recording_tree(
    source_root: Path,
    cache_root: Path,
    ledger_payload: dict[str, object],
    ledger_path: Path,
) -> None:
    if cache_root.exists():
        shutil.rmtree(cache_root)
    cache_root.mkdir(parents=True)
    relatives = [
        str(entry["file"])
        for entry in ledger_payload["artifacts"]
        if isinstance(entry, dict) and isinstance(entry.get("file"), str)
    ] + [ledger_path.name]
    for relative in relatives:
        source = source_root / relative
        target = cache_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.casefold() == ".png":
            try:
                os.link(source, target)
                continue
            except OSError:
                pass
        shutil.copyfile(source, target)


class DossierProject:
    """A temporary project with real reference captures on disk."""

    def __init__(self, temporary: str) -> None:
        self.project = Path(temporary)
        self.state = self.project / ".design-dna"
        self.state.mkdir()
        self.record_path = self.state / "reference-dossier.md"
        self.record_path.write_text("placeholder\n", encoding="utf-8")
        self.captures = self.state / "references"
        # Real frames on disk, because the frame column is checked by opening it.
        for rank in range(1, 7):
            write_png(self.captures / f"strong-{rank}-frames" / f"strong-{rank}-001-rest.png")

    def styles_cell(
        self,
        name: str,
        *,
        numbers=None,
        tool: str = "extract_reference_styles.mjs",
        url: str | None = None,
    ) -> str:
        """A machine extraction of the reference's live CSS."""
        path = self.captures / f"{name}-styles.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        observed_url = url or f"https://{name}.example.test/"
        observation = self.captures / f"{name}-observation.json"
        path.write_text(json.dumps({
            "tool": tool,
            "schema_version": 3,
            "producer_script_sha256": sha256_of(
                SKILL / "scripts" / "extract_reference_styles.mjs"
            ),
            "runtime_identity": {
                "extract_reference_styles.mjs": sha256_of(
                    SKILL / "scripts" / "extract_reference_styles.mjs"
                )
            },
            "id": name,
            "url": observed_url,
            "source_observation": ({
                "id": name, "url": observed_url,
                "file": observation.name, "sha256": sha256_of(observation),
            } if observation.is_file() else None),
            "viewports_measured": [
                {"name": "wide", "width": 1440, "height": 900},
                {"name": "narrow", "width": 390, "height": 844},
            ],
            "inspection": {
                "complete": True, "pseudo_elements": 0,
                "open_shadow_roots": 0, "captured_closed_shadow_roots": 0,
                "same_origin_iframes": 0, "canvases": 0, "uninspectable": [],
            },
            "numbers": MEASURED_NUMBERS if numbers is None else numbers,
            "type": [], "controls": [], "transitions": [], "colors": [],
        }), encoding="utf-8")
        return (f".design-dna/references/{name}-styles.json plus sha256:"
                + sha256_of(path))

    def census_cell(
        self,
        names: list[str] | None = None,
        *,
        selected_rank: int = 1,
    ) -> str:
        """A scan_build_components.mjs record naming what the build renders."""
        if names is None:
            names = list(REQUIRED_COMPONENTS)
        path = self.state / "evidence" / "component-census.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        build_url = "http://127.0.0.1:4960/"
        reference_id = f"strong-{selected_rank}"
        observation_relative = f".design-dna/references/{reference_id}-observation.json"
        observation_path = self.captures / f"{reference_id}-observation.json"
        if not observation_path.is_file():
            self.observation_cell(
                reference_id,
                url=f"https://reference-{selected_rank}.example.test/entry",
            )
        observation_sha = sha256_of(observation_path)
        viewports = [
            {"name": "wide", "width": 1440, "height": 900},
            {"name": "narrow", "width": 390, "height": 844},
        ]
        states = [{
            "id": "rest", "kind": "rest",
            "trigger": {"type": "none", "target": "document", "value": None},
            "expectation": "initial settled route",
            "mapped_reference_state_id": "rest",
        }, {
            "id": "primary-hover", "kind": "interactive",
            "trigger": {"type": "hover", "target": ".primary-control", "value": None},
            "expectation": "Primary control changes under pointer hover.",
            "mapped_reference_state_id": "primary-hover",
        }, {
            "id": "primary-focus", "kind": "interactive",
            "trigger": {"type": "focus", "target": ".primary-control", "value": None},
            "expectation": "Primary control exposes keyboard focus.",
            "mapped_reference_state_id": "primary-focus",
        }]
        manifest_path = self.state / "route-manifest.json"
        if not manifest_path.is_file():
            _manifest_binding, proof_build_id = self.route_manifest_cell(
                selected_rank=selected_rank
            )
        else:
            proof_build_id = "fixture-proof-build-0001"
        decision_manifest_path = self.state / "visible-decision-sources.json"
        if not decision_manifest_path.is_file():
            default_selected_ranks = [1, 2, 3, 4]
            for rank in default_selected_ranks:
                candidate_observation = (
                    self.captures / f"strong-{rank}-observation.json"
                )
                if not candidate_observation.is_file():
                    self.observation_cell(
                        f"strong-{rank}",
                        url=f"https://reference-{rank}.example.test/entry",
                    )
            self.visible_decision_manifest_cell(
                proof_build_id=proof_build_id,
                selected_ranks=default_selected_ranks,
            )
        decision_manifest = json.loads(
            decision_manifest_path.read_text(encoding="utf-8")
        )
        decisions = decision_manifest["decisions"]
        resources = [{
            "url": build_url,
            "status": 200,
            "sha256": "d" * 64,
            "bytes": 128,
        }]
        served_probes = []
        for profile in ("narrow", "wide"):
            projection = {
                "requested_url": build_url,
                "final_url": build_url,
                "status": 200,
                "document_sha256": "d" * 64,
                "resources": resources,
            }
            served_probes.append({
                "route_key": "home",
                "viewport": profile,
                **projection,
                "sha256": INITIALIZER.canonical_json_sha256(projection),
            })
        served_identity = {
            "algorithm": "sha256-response-bodies-v1",
            "probes": served_probes,
            "reload_counts": {"home/narrow": 2, "home/wide": 2},
            "inconsistent_reloads": [],
            "sha256": INITIALIZER.canonical_json_sha256([{
                "route_key": probe["route_key"],
                "viewport": probe["viewport"],
                "sha256": probe["sha256"],
            } for probe in served_probes]),
            "complete": True,
        }
        interaction_dir_name = "component-census-interaction-frames"
        interaction_dir = path.parent / interaction_dir_name
        interaction_dir.mkdir(parents=True, exist_ok=True)
        target_censuses: list[dict[str, object]] = []
        checks: list[dict[str, object]] = []
        scopes: list[dict[str, object]] = []
        inventories: list[dict[str, object]] = []
        interaction_cells: list[dict[str, object]] = []
        experience_paths: list[dict[str, object]] = []
        qa_cells: list[dict[str, object]] = []
        for viewport in viewports:
            profile = viewport["name"]
            evidence: dict[str, dict[str, object]] = {}
            for offset, moment in enumerate(("before", "after", "settled"), start=1):
                evidence_path = interaction_dir / f"{profile}-{moment}.png"
                write_png(
                    evidence_path,
                    width=viewport["width"],
                    height=viewport["height"],
                    rgb=(30 + offset * 20, 60 + offset * 10, 100 + offset * 5),
                )
                evidence[moment] = {
                    "file": f"{interaction_dir_name}/{evidence_path.name}",
                    "bytes": evidence_path.stat().st_size,
                    "sha256": sha256_of(evidence_path),
                }
            census = self.interaction_census(reference_id, build_url, profile, evidence)
            first_page = census["pages"][0]
            target = first_page["targets"][0]
            target["repeat_index"] = 1
            target["repeat_count"] = 1
            census["pages"] = [first_page]
            first_page["dom_code_inventory"]["routes_discovered"] = [build_url]
            census["repeat_classes"][0]["target_ids"] = [target["target_id"]]
            census["blocked_side_effects"] = [
                item for item in census["blocked_side_effects"]
                if item["target_id"] == target["target_id"]
            ]
            census["totals"] = {
                "targets_discovered": 1, "inputs_discovered": 6,
                "inputs_exercised": 5, "inputs_blocked": 1,
            }
            target_censuses.append({**census, "route_key": "home", "viewport": profile})
            experience_path = {
                "route_key": "home",
                "viewport": profile,
                "target_id": target["target_id"],
                "kind": target["kind"],
                "actions": [{
                    "input_kind": item["input_kind"],
                    "status": item["status"],
                    "resolution": (
                        "manifested-state" if item["source_state_id"] else
                        "blocked-handoff" if item["status"] == "blocked" else None
                    ),
                    "manifested_state_id": item["source_state_id"],
                    "final_url": None,
                    "evidence": item["evidence"],
                } for item in target["inputs"]],
                "missing": [],
                "complete": True,
            }
            experience_paths.append(experience_path)
            control_visibility = [{
                "key": "component:primary-control",
                "semantic_key": "button|primary",
                "text": "Primary",
                "role": "button",
                "visible": True,
                "focusable": True,
                "aria_hidden": None,
                "tag": "button",
                "display": "inline-block",
                "visibility": "visible",
                "opacity": 1.0,
                "rendered_box": True,
                "tab_index": 0,
            }]
            overlay_summary = {
                "records": [],
                "inert_background": True,
                "closed_descendants_inert": True,
                "stacking": True,
                "initial_focus": True,
                "background_focus_blocked": True,
                "focus_trap": True,
                "focus_return": True,
            }
            state_semantics = {
                "required": False,
                "complete": True,
                "target": None,
                "attributes": None,
            }
            public_copy = {
                "visible_text": [{"parent": "main", "text": "Primary"}],
                "findings": [],
                "contextual_review": [],
                "truncated": False,
                "complete": True,
                "evidence": evidence["settled"],
            }
            accessibility = {
                "headings": [{"key": "h1", "level": 1, "text": "Primary"}],
                "landmarks": [{
                    "key": "main", "tag": "main", "role": None,
                    "label": None, "visible": True,
                }],
                "focus_indicators": [{
                    "target": "component:primary-control",
                    "active": True,
                    "visible_indicator": True,
                    "before": {"outline_style": "none"},
                    "after": {"outline_style": "solid"},
                    "evidence": {
                        "before": evidence["before"],
                        "after": evidence["after"],
                    },
                    "complete": True,
                }],
                "missing": [],
                "truncated": False,
                "complete": True,
            }
            reduced_motion = {
                "active_animations": [],
                "violations": [],
                "complete": True,
                "evidence": evidence["settled"],
            }
            for manifested_state in states:
                changed = manifested_state["id"] != "rest"
                trigger_evidence = {
                    "type": manifested_state["trigger"]["type"],
                    "target": manifested_state["trigger"]["target"],
                    "before_sha256": "1" * 64,
                    "after_sha256": ("2" * 64 if changed else "1" * 64),
                    "settled_sha256": ("2" * 64 if changed else "1" * 64),
                    "settled": True,
                    "change_classification": {
                        "cosmetic": ([{"property": "background_color"}] if changed else []),
                        "structural_semantic": ([{"property": "transform"}] if changed else []),
                        "diagnostic": [],
                    },
                }
                application = {
                    "state_id": manifested_state["id"], "applied": True,
                    "target_count": 1, "navigation": None,
                    "trigger_evidence": trigger_evidence,
                }
                source_semantics = ["button|primary"]
                responsive_parity = {
                    "source_profile": profile,
                    "mapped_reference_state_id": manifested_state["mapped_reference_state_id"],
                    "source_current_semantic_keys": source_semantics,
                    "source_opposite_semantic_keys": source_semantics,
                    "source_authorized_omissions": [],
                    "build_visible_semantic_keys": source_semantics,
                    "findings": [],
                    "complete": True,
                }
                short_height = min(viewport["height"], 568)
                short_qa = {
                    "profile": f"{profile}-short",
                    "width": viewport["width"],
                    "height": short_height,
                    "clipping": [],
                    "collisions": [],
                    "fixed_rail_overlaps": [],
                    "control_visibility": control_visibility,
                    "overlays": overlay_summary,
                    "state_semantics": state_semantics,
                    "public_copy": public_copy,
                    "accessibility": accessibility,
                    "viewport": {"width": viewport["width"], "height": short_height},
                    "truncated": False,
                    "reduced_motion": reduced_motion,
                }
                qa_cell = {
                    "route_key": "home",
                    "viewport": profile,
                    "state_id": manifested_state["id"],
                    "clipping": [],
                    "collisions": [],
                    "fixed_rail_overlaps": [],
                    "control_visibility": control_visibility,
                    "responsive_control_parity": responsive_parity,
                    "hidden_controls": [],
                    "dead_controls": [],
                    "blocked_handoffs": [],
                    "overlays": overlay_summary,
                    "keyboard": {"complete": True, "missing": []},
                    "reduced_motion": reduced_motion,
                    "deep_link": {
                        "complete": True,
                        "requested_url": build_url,
                        "final_urls": [build_url],
                    },
                    "reload": {
                        "complete": True,
                        "count": 2,
                        "served_content_sha256": served_identity["sha256"],
                    },
                    "dead_ends": [],
                    "semantic_equivalence": {"complete": True, "mismatches": []},
                    "state_semantics": state_semantics,
                    "public_copy": public_copy,
                    "accessibility": accessibility,
                    "experience_paths": [experience_path],
                    "short_height": short_qa,
                    "missing": [],
                    "truncated": False,
                    "complete": True,
                }
                qa_cells.append(qa_cell)
                applicable_decisions = sorted(
                    row["decision_id"] for row in decisions
                    if "home" in row["route_keys"]
                    and manifested_state["id"] in row["state_ids"]
                )
                checks.append({
                    "route_key": "home", "url": build_url,
                    "mapped_reference_rank": selected_rank,
                    "mapped_reference_id": reference_id,
                    "mapped_reference_observation": observation_relative,
                    "mapped_reference_sha256": observation_sha,
                    "viewport": profile, "width": viewport["width"],
                    "height": viewport["height"], "state_id": manifested_state["id"],
                    "state_kind": manifested_state["kind"],
                    "state_trigger": manifested_state["trigger"],
                    "mapped_reference_state_id": manifested_state["mapped_reference_state_id"],
                    "attempted": 1, "covered": 1,
                    "state_application": application,
                    "scroll_traversal": {"complete": True, "surfaces": [{
                        "id": "document", "kind": "document", "complete": True
                    }]},
                    "components": [{"name": n, "count": 1, "area": 0.1} for n in sorted(names)],
                    "visible_decision_ids": applicable_decisions,
                    "unsourced_visible_parts": [],
                    "links": [build_url], "inspection": [{"complete": True}],
                    "implementation_scope": {
                        "document_height": 1800, "viewport_height": viewport["height"],
                        "substantial_regions": [{
                            "top": 0, "bottom": 900, "tag": "main",
                            "component_identity": "tag:main",
                        }],
                        "beyond_first_screen_regions": [],
                    },
                    "first_screen_scope_pass": False,
                    "rendered_qa": qa_cell,
                    "pass": True,
                })
                interaction_cells.append({
                    "route_key": "home", "viewport": profile,
                    "state_id": manifested_state["id"],
                    "mapped_reference_state_id": manifested_state["mapped_reference_state_id"],
                    "source_mapping": {
                        "rank": selected_rank, "id": reference_id,
                        "observation": observation_relative, "sha256": observation_sha,
                        "state_id": manifested_state["mapped_reference_state_id"],
                    },
                    "trigger": manifested_state["trigger"], "complete": True,
                    "target_components_present": True,
                    "target_components": sorted(names),
                    "trigger_evidence": trigger_evidence,
                })
            scopes.append({
                "route_key": "home", "viewport": profile,
                "document_height": 1800, "viewport_height": viewport["height"],
                "substantial_regions": [{
                    "top": 0, "bottom": 900, "tag": "main",
                    "component_identity": "tag:main",
                }],
                "beyond_first_screen_regions": [],
                "first_screen_scope_pass": False,
            })
            inventory = {
                "route_key": "home", "viewport": profile,
                "discovery_scroll": {"complete": True, "surfaces": []},
                "inferred": [{
                    "key": "1:focusable", "element_key": "1",
                    "signal": "focusable", "kind": "interactive",
                    "required_trigger": ["focus"], "declared_state_id": None,
                    "tag": "button", "text": "Primary",
                    "reconciled_state_ids": ["primary-focus"],
                }, {
                    "key": "1:hover-candidate", "element_key": "1",
                    "signal": "hover-candidate", "kind": "interactive",
                    "required_trigger": ["hover"], "declared_state_id": None,
                    "tag": "button", "text": "Primary",
                    "actual_style_response": True,
                    "reconciled_state_ids": ["primary-hover"],
                }],
                "unreconciled": [], "complete": True,
            }
            inventories.append(inventory)
        experience_summary = {
            "complete": True,
            "missing": [],
            "truncated": False,
            "totals": {
                "targets": len(experience_paths),
                "resolved": len(experience_paths),
                "blocked_handoffs": sum(
                    any(action["resolution"] == "blocked-handoff"
                        for action in row["actions"])
                    for row in experience_paths
                ),
            },
            "paths": experience_paths,
        }
        rendered_qa = {
            "schema_version": 1,
            "complete": True,
            "missing": [],
            "truncated": False,
            "cells": qa_cells,
            "presentation_ready": True,
            "presentation_blocker": None,
            "experience_paths": experience_summary,
        }
        implemented_decision_ids = sorted({
            decision_id
            for check in checks
            for decision_id in check["visible_decision_ids"]
        })
        visible_reconciliation = {
            "manifest_path": ".design-dna/visible-decision-sources.json",
            "manifest_sha256": sha256_of(decision_manifest_path),
            "implemented_decision_ids": implemented_decision_ids,
            "missing_decision_ids": [],
            "unsourced_visible_decisions": [],
            "scaffold_findings": [],
            "fallback_findings": [],
            "placeholder_findings": [],
            "complete": True,
        }
        route_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload = {
            "tool": "scan_build_components.mjs",
            "schema_version": 3,
            "producer_script_sha256": sha256_of(
                SKILL / "scripts" / "scan_build_components.mjs"
            ),
            "runtime_identity": {
                "scan_build_components.mjs": sha256_of(
                    SKILL / "scripts" / "scan_build_components.mjs"
                )
            },
            "scanned_at": "2026-09-04T13:00:00Z",
            "pass": True,
            "build_id": "fixture-final-build-0001",
            "run_id": "fixture-run-0001",
            "manifest_id": route_manifest["manifest_id"],
            "manifest_sha256": sha256_of(manifest_path),
            "route_filter": ["home"],
            "first_screen_only": False,
            "viewports": viewports,
            "state_ids": sorted(state["id"] for state in states),
            "routes": [{"key": "home", "url": build_url, "components": []}],
            "checks": checks,
            "navigations": [],
            "served_content": served_identity,
            "served_content_identity": served_identity,
            "unexpected_urls": [],
            "failed_states": [],
            "implementation_scope": scopes,
            "state_inventories": inventories,
            "interaction_frame_directory": interaction_dir_name,
            "interaction_inventory": {
                "complete": True, "missing": [],
                "cells": interaction_cells,
                "responsive_transformations": [{
                    "route_key": "home", "state_id": state_id, "complete": True,
                    "wide": {"trigger_evidence": next(
                        item["trigger_evidence"] for item in interaction_cells
                        if item["viewport"] == "wide" and item["state_id"] == state_id
                    )},
                    "narrow": {"trigger_evidence": next(
                        item["trigger_evidence"] for item in interaction_cells
                        if item["viewport"] == "narrow" and item["state_id"] == state_id
                    )},
                } for state_id in ("rest", "primary-hover", "primary-focus")],
                "inferred_components": inventories,
                "target_censuses": target_censuses,
            },
            "rendered_qa": rendered_qa,
            "visible_decision_reconciliation": visible_reconciliation,
            "names": sorted(names),
            "census": [{"name": n, "count": 1, "area": 0.1} for n in sorted(names)],
            "discovered_urls": [build_url],
            "verdict": "Scanned six exact route, viewport, and state cells.",
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        return (".design-dna/evidence/component-census.json plus sha256:"
                + sha256_of(path))

    def proof_cell(self) -> str:
        """A check_signature_transfer.mjs record for the transfer rows to bind."""
        path = self.state / "evidence" / "signature-transfer.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "tool": "check_signature_transfer.mjs",
            "schema_version": 3,
            "producer_script_sha256": sha256_of(
                SKILL / "scripts" / "check_signature_transfer.mjs"
            ),
            "runtime_identity": {
                "check_signature_transfer.mjs": sha256_of(
                    SKILL / "scripts" / "check_signature_transfer.mjs"
                )
            },
            "pass": True,
            "verdicts": [],
        }), encoding="utf-8")
        return (".design-dna/evidence/signature-transfer.json plus sha256:"
                + sha256_of(path))

    def capture_cell(self, name: str, *, width: int = 8, height: int = 8) -> str:
        path = self.captures / f"{name}.png"
        if not path.is_file():
            write_png(path, width=width, height=height)
        return f".design-dna/references/{name}.png plus sha256:{sha256_of(path)}"

    @staticmethod
    def navigation(url: str) -> dict[str, object]:
        chain = [{
            "index": 0, "method": "GET", "requested_url": url,
            "normalized_url": url, "status": 200, "status_text": "OK",
            "response_url": url,
        }]
        return {
            "requested_url": url,
            "requested_normalized_url": url,
            "response_final_url": url,
            "response_final_normalized_url": url,
            "final_url": url,
            "final_normalized_url": url,
            "final_status": 200,
            "redirect_count": 0,
            "redirect_chain": chain,
            "redirect_chain_sha256": hashlib.sha256(
                json.dumps(chain, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        }

    def state_contract(self, name: str, url: str) -> tuple[Path, dict[str, object]]:
        path = self.captures / f"{name}-state-contract.json"
        payload = {
            "schema_version": 1,
            "reference_id": name,
            "states": [{
                "id": "rest",
                "url": url,
                "kind": "rest",
                "trigger": {"type": "none", "target": "document", "value": None},
                "expectation": "Initial settled source route before any visitor input.",
            }, {
                "id": "primary-hover", "url": url, "kind": "interactive",
                "trigger": {"type": "hover", "target": ".primary-control", "value": None},
                "expectation": "Primary control visibly changes under a safe pointer hover.",
            }, {
                "id": "primary-focus", "url": url, "kind": "interactive",
                "trigger": {"type": "focus", "target": ".primary-control", "value": None},
                "expectation": "Primary control exposes its visible keyboard focus treatment.",
            }],
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path, payload

    def interaction_census(
        self,
        name: str,
        url: str,
        profile: str,
        evidence_frames: dict[str, dict[str, object]],
    ) -> dict[str, object]:
        inner = url.rstrip("/") + "/inner"
        pages: list[dict[str, object]] = []
        repeat_ids: list[str] = []
        for page_index, page_url in enumerate((url, inner), start=1):
            target_id = hashlib.sha256(
                f"{name}:{profile}:{page_url}:primary-control".encode("utf-8")
            ).hexdigest()[:24]
            repeat_ids.append(target_id)
            before = "1" * 64
            after = ("2" if profile == "wide" else "3") * 64
            evidence = {
                "before": evidence_frames["before"],
                "after": evidence_frames["after"],
                "settled": evidence_frames["settled"],
            }
            def exercised(kind, value=None, source_state_id=None):
                changes = [{
                    "component_key": "component:primary-control",
                    "property": "background_color",
                    "before": "rgb(0, 0, 0)",
                    "after": "rgb(255, 255, 255)",
                }, {
                    "component_key": "component:primary-control",
                    "property": "transform",
                    "before": "none",
                    "after": "matrix(1, 0, 0, 1, 8, 0)",
                }]
                return {
                    "input_kind": kind,
                    "input_value": value,
                    "safety": "safe",
                    "status": "exercised",
                    "source_state_id": source_state_id,
                    "before_sha256": before,
                    "after_sha256": after,
                    "settled_sha256": after,
                    "changed_properties": changes,
                    "change_classification": {
                        "cosmetic": [changes[0]],
                        "structural_semantic": [changes[1]],
                        "diagnostic": [],
                    },
                    "behavior": f"{kind} changes the control ground and preserves its geometry",
                    "evidence": evidence,
                    "disposition": "sourceable-observed-behavior",
                }
            inputs = [
                exercised("hover", source_state_id="primary-hover" if page_index == 1 else None),
                exercised("focus", source_state_id="primary-focus" if page_index == 1 else None),
                exercised("focus-traversal", "Tab"),
                exercised("keyboard", "Enter"),
                exercised("keyboard", "Space"),
                {
                    "input_kind": "click",
                    "input_value": None,
                    "safety": "blocked-side-effect",
                    "status": "blocked",
                    "source_state_id": None,
                    "before_sha256": None,
                    "after_sha256": None,
                    "settled_sha256": None,
                    "changed_properties": [],
                    "change_classification": {
                        "cosmetic": [], "structural_semantic": [],
                        "diagnostic": [],
                    },
                    "behavior": "click is not observed because it may change external state",
                    "evidence": None,
                    "disposition": "blocked-requires-safe-owner-handoff",
                },
            ]
            pages.append({
                "url": page_url,
                "targets": [{
                    "target_id": target_id,
                    "page_url": page_url,
                    "selector": f'[data-dna-interaction-id="{page_index}"]',
                    "tag": "button",
                    "role": "button",
                    "text": "Primary",
                    "semantic_key": "button|primary",
                    "class_signature": ["primary-control"],
                    "repeat_class": "button|button|primary-control",
                    "repeat_index": page_index,
                    "repeat_count": 2,
                    "kind": "control",
                    "semantic_state": {
                        "aria_expanded": None, "aria_pressed": None,
                        "aria_controls": None, "aria_haspopup": None,
                        "disabled": False,
                    },
                    "source_state_ids": (
                        ["primary-focus", "primary-hover"] if page_index == 1 else []
                    ),
                    "inputs": inputs,
                }],
                "dom_code_inventory": {
                    "routes_discovered": sorted({url, inner}),
                    "controls_discovered": [target_id],
                    "state_hooks": [],
                    "animation_hooks": [{
                        "target_id": target_id,
                        "transition_property": "background-color",
                        "transition_duration": "0.45s",
                        "animation_name": "none",
                        "active_animations": 0,
                    }],
                    "assets": [f"https://assets.example.test/{name}-hero.webp"],
                    "scripts": [{
                        "src": f"https://assets.example.test/{name}.js",
                        "type": "module", "bytes": None, "inline_sha256": None,
                    }],
                    "inline_handlers": [],
                    "live_target_ids": [target_id],
                    "live_source_state_ids": (
                        ["primary-focus", "primary-hover", "rest"]
                        if page_index == 1 else []
                    ),
                    "unreconciled_controls": [],
                    "complete": True,
                },
            })
        page_state = {
            "source_state_id": "rest",
            "kind": "rest",
            "trigger": {"type": "none", "target": "document", "value": None},
            "page_url": url,
            "disposition": "observed-rest",
            "trigger_evidence": {
                "before_sha256": "1" * 64,
                "after_sha256": "1" * 64,
                "settled_sha256": "1" * 64,
                "changed_properties": [],
                "change_classification": {
                    "cosmetic": [], "structural_semantic": [],
                    "diagnostic": [],
                },
                "behavior": "settled rest state",
            },
            "evidence": {
                "before": evidence_frames["before"],
                "after": evidence_frames["after"],
                "settled": evidence_frames["settled"],
            },
        }
        return {
            "profile": profile,
            "pages": pages,
            "page_states": [page_state],
            "repeat_classes": [{
                "repeat_class": "button|button|primary-control",
                "target_ids": repeat_ids,
                "input_kinds": [
                    "click", "focus", "focus-traversal", "hover", "keyboard"
                ],
                "equivalent": True,
                "behavior_signatures": [
                    "focus:focus changes the control ground and preserves its geometry",
                    "focus-traversal:focus-traversal changes the control ground and preserves its geometry",
                    "hover:hover changes the control ground and preserves its geometry",
                    "keyboard:keyboard changes the control ground and preserves its geometry",
                ],
                "evidence": [evidence_frames["before"], evidence_frames["after"]],
            }],
            "pointer_follow": [],
            "blocked_side_effects": [{
                "target_id": target_id,
                "input_kind": "click",
                "reason": "potential external state-changing side effect",
                "handoff": "Use an owner-authorized disposable session and bind generated evidence.",
            } for target_id in repeat_ids],
            "totals": {
                "targets_discovered": 2,
                "inputs_discovered": 12,
                "inputs_exercised": 10,
                "inputs_blocked": 2,
            },
            "truncated": False,
            "missing": [],
            "complete": True,
        }

    def rendered_qa(
        self,
        url: str,
        profile: str,
        evidence_frames: dict[str, dict[str, object]],
        *,
        name: str = "strong-1",
        include_inner: bool = True,
    ) -> dict[str, object]:
        urls = [url, url.rstrip("/") + "/inner"] if include_inner else [url]
        pages = []
        for page_url in urls:
            target_id = hashlib.sha256(
                f"{name}:{profile}:{page_url}:primary-control".encode("utf-8")
            ).hexdigest()[:24]
            pages.append({
                "url": page_url,
                "evidence": evidence_frames["settled"],
                "clipping": [],
                "collisions": [],
                "fixed_rail_overlaps": [],
                "hidden_controls": [],
                "control_visibility": [{
                    "selector": '[data-dna-interaction-id="1"]',
                    "semantic_key": "button|primary",
                    "text": "Primary",
                    "role": "button",
                    "tag": "button",
                    "visible": True,
                    "focusable": True,
                    "aria_hidden": None,
                }],
                "dead_controls": [],
                "semantic_issues": [],
                "overlays": [],
                "keyboard_paths": [{
                    "target_id": target_id,
                    "inputs": [{
                        "input_kind": "keyboard", "status": "exercised",
                        "behavior": "focus advances through the visible control",
                        "evidence": {
                            "before": evidence_frames["before"],
                            "after": evidence_frames["after"],
                            "settled": evidence_frames["settled"],
                        },
                    }],
                    "complete": True,
                }],
                "keyboard": {"complete": True, "missing": []},
                "semantic_equivalence": {"complete": True, "mismatches": []},
                "state_semantics": {
                    "required": False,
                    "complete": True,
                    "target": None,
                    "attributes": None,
                },
                "reduced_motion": {
                    "navigation": self.navigation(page_url),
                    "animations": [],
                    "evidence": evidence_frames["settled"],
                    "honors_preference": True,
                    "complete": True,
                },
                "deep_link": {
                    "navigation": self.navigation(page_url),
                    "evidence": evidence_frames["before"],
                    "complete": True,
                },
                "reload": {
                    "navigation": self.navigation(page_url),
                    "before": evidence_frames["before"],
                    "after": evidence_frames["after"],
                    "stable_pixels": True,
                    "complete": True,
                },
                "dead_end": {
                    "same_origin_destinations": urls,
                    "is_dead_end": False,
                    "terminal_signal": False,
                    "problem": False,
                },
            })
        return {
            "profile": profile,
            "pages": pages,
            "totals": {"pages": len(pages), "issues": 0, "controls": len(pages), "overlays": 0},
            "truncated": False,
            "missing": [],
            "complete": True,
        }

    def observation_cell(
        self,
        name: str,
        *,
        kind: str = "motion",
        url: str = "https://reference.example.test/entry",
        motion: bool = True,
        holds: int = 3,
        hovers: int = 2,
        tool: str = "observe_reference.mjs",
        schema: int = 5,
        structure: bool = True,
        distinct: int | None = None,
        coverage: float | None = None,
        sheet: bool = True,
        inner: bool = True,
    ) -> str:
        path = self.captures / f"{name}-observation.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        contract_path, contract = self.state_contract(name, url)
        mechanisms = (
            [
                {"type": "pinned", "tag": "section", "cls": "stage", "held_px": 2400,
                 "swaps_while_held": 3, "detail": "held while its content changed"},
                {"type": "parallax", "tag": "img", "cls": "", "rate": 0.4},
                {"type": "reveal", "tag": "h2", "cls": "", "opacity_from": 0, "opacity_to": 1},
                {"type": "hover-transition", "ms": 450},
            ]
            if motion
            else []
        )
        score_payload = {
            "distinct_mechanisms": (
                distinct if distinct is not None else (4 if motion else 0)
            ),
            "scroll_coverage": (
                coverage if coverage is not None else (0.8 if motion else 0.0)
            ),
            "scroll_windows_active": 8,
            "scroll_windows": 10,
            "elements_with_mechanism": 3,
            "document_scrolls": True,
            "type_instances": {item["type"]: 1 for item in mechanisms},
            "scroller": "document",
            "scroll_consumed_px": 2400,
        }
        wide_path = self.captures / f"{name}-wide.png"
        narrow_path = self.captures / f"{name}-narrow.png"
        write_png(wide_path, width=900, height=600, rgb=(32, 64, 96))
        write_png(narrow_path, width=390, height=700, rgb=(48, 72, 104))

        def frame_meta(frame_path: Path, *, seq: int, kind_name: str) -> dict[str, object]:
            return {
                "seq": seq,
                "kind": kind_name,
                "file": frame_path.relative_to(self.captures).as_posix(),
                "bytes": frame_path.stat().st_size,
                "sha256": sha256_of(frame_path),
                "note": f"generated {kind_name} fixture evidence",
            }

        evidence_by_profile: dict[str, dict[str, dict[str, object]]] = {}
        frames: list[dict[str, object]] = [
            frame_meta(wide_path, seq=1, kind_name="wide-rest"),
            frame_meta(narrow_path, seq=2, kind_name="narrow-rest"),
        ]
        seq = 2
        for profile, width in (("wide", 900), ("narrow", 390)):
            evidence_by_profile[profile] = {}
            for offset, moment in enumerate(("before", "after", "settled"), start=1):
                seq += 1
                frame = self.captures / f"{name}-frames" / f"{name}-{profile}-{moment}.png"
                write_png(
                    frame,
                    width=width,
                    height=600,
                    rgb=(40 + offset * 20, 70 + offset * 10, 110 + offset * 5),
                )
                meta = frame_meta(frame, seq=seq, kind_name=f"{profile}-{moment}")
                frames.append(meta)
                evidence_by_profile[profile][moment] = {
                    "file": meta["file"], "bytes": meta["bytes"], "sha256": meta["sha256"]
                }
        payload = {
            "schema_version": schema,
            "tool": tool,
            "producer_script_sha256": sha256_of(
                SKILL / "scripts" / "observe_reference.mjs"
            ),
            "runtime_identity": {
                "observe_reference.mjs": sha256_of(
                    SKILL / "scripts" / "observe_reference.mjs"
                )
            },
            "id": name,
            "url": url,
            "requested_url": url,
            "final_url": url,
            "observed_at": "2026-09-02T00:00:00Z",
            "interactions": ([{
                "type": "transition",
                "attempted": True,
                "url": url.rstrip("/") + "/inner",
                "moved": motion,
            }] if inner else []),
            "coverage": {"rest": True, "scroll_holds": holds, "hovers": hovers, "transition": True},
            "motion": {
                "observed": motion,
                "at_rest": False,
                "on_scroll_holds": holds if motion else 0,
                "on_hover": hovers if motion else 0,
                "on_transition": motion,
            },
            "frame_dir": ".",
            "frames": frames,
            "captures_by_viewport": {
                "wide": {
                    "file": wide_path.name,
                    "bytes": wide_path.stat().st_size,
                    "sha256": sha256_of(wide_path),
                },
                "narrow": {
                    "file": narrow_path.name,
                    "bytes": narrow_path.stat().st_size,
                    "sha256": sha256_of(narrow_path),
                },
            },
            "state_contract": {
                "file": contract_path.name,
                "sha256": sha256_of(contract_path),
            },
            "navigations": [self.navigation(url)],
        }
        if structure:
            wide_structure = {
                "viewport": {"w": 1440, "h": 900},
                "grid": [[2] * 24 for _ in range(16)],
                "shares": {"media": 0.8, "text": 0.1, "box": 0.0, "empty": 0.1},
                "dominant": {"tag": "img", "kind": "media", "area_share": 0.82, "cls": "hero"},
                "edges": {"top": ["text"], "right": ["text"], "bottom": ["text"], "left": ["text"]},
                "corners": [1, 1, 1, 1],
                "type": {
                    "display": {"family": "Dia", "size": 40, "weight": "400",
                                "tracking": "normal", "transform": "uppercase",
                                "leading": 1.1, "x_ratio": 0.72, "advance": 7.4},
                    "body": {"family": "Dia", "size": 16, "weight": "400",
                             "leading": 1.4, "x_ratio": 0.72, "advance": 7.4},
                    "scale": 2.5,
                    "families": ["Dia"],
                },
            }
            narrow_structure = json.loads(json.dumps(wide_structure))
            narrow_structure["viewport"] = {"w": 390, "h": 844}
            payload["first_screen"] = wide_structure
            payload["first_screens"] = {
                "wide": wide_structure,
                "narrow": narrow_structure,
            }
        if sheet:
            payload["mechanisms"] = mechanisms
            payload["score"] = score_payload
            payload["mechanisms_by_viewport"] = {
                "wide": {"mechanisms": mechanisms, "score": score_payload},
                "narrow": {"mechanisms": mechanisms, "score": score_payload},
            }
            payload["first_screen_mechanisms_by_viewport"] = {
                "wide": {"mechanisms": mechanisms, "score": score_payload},
                "narrow": {"mechanisms": mechanisms, "score": score_payload},
            }
        if structure and sheet:
            states: dict[str, dict[str, object]] = {}
            traversal_census_by_profile: dict[str, dict[str, object]] = {}
            traversal_qa_by_profile: dict[str, dict[str, object]] = {}
            for profile, structure_payload in (
                ("wide", payload["first_screens"]["wide"]),
                ("narrow", payload["first_screens"]["narrow"]),
            ):
                evidence = evidence_by_profile[profile]
                census = self.interaction_census(name, url, profile, evidence)
                if not inner:
                    first_page = census["pages"][0]
                    first_target = first_page["targets"][0]
                    first_target["repeat_index"] = 1
                    first_target["repeat_count"] = 1
                    census["pages"] = [first_page]
                    first_page["dom_code_inventory"]["routes_discovered"] = [url]
                    census["repeat_classes"][0]["target_ids"] = [first_target["target_id"]]
                    census["blocked_side_effects"] = [
                        row for row in census["blocked_side_effects"]
                        if row["target_id"] == first_target["target_id"]
                    ]
                    census["totals"] = {
                        "targets_discovered": 1, "inputs_discovered": 6,
                        "inputs_exercised": 5, "inputs_blocked": 1,
                    }
                traversal_rendered_qa = self.rendered_qa(
                    url, profile, evidence, name=name, include_inner=inner
                )
                traversal_census_by_profile[profile] = census
                traversal_qa_by_profile[profile] = traversal_rendered_qa
                states[profile] = {}
                for source_state in contract["states"]:
                    state_census = json.loads(json.dumps(census))
                    state_page = state_census["pages"][0]
                    state_target = state_page["targets"][0]
                    state_target["repeat_index"] = 1
                    state_target["repeat_count"] = 1
                    state_census["pages"] = [state_page]
                    state_census["repeat_classes"][0]["target_ids"] = [
                        state_target["target_id"]
                    ]
                    state_census["blocked_side_effects"] = [
                        row for row in state_census["blocked_side_effects"]
                        if row["target_id"] == state_target["target_id"]
                    ]
                    state_census["totals"] = {
                        "targets_discovered": 1,
                        "inputs_discovered": 6,
                        "inputs_exercised": 5,
                        "inputs_blocked": 1,
                    }
                    state_rendered_qa = self.rendered_qa(
                        url, profile, evidence, name=name, include_inner=False
                    )
                    changed = source_state["id"] != "rest"
                    changed_properties = ([{
                        "component_key": "component:primary-control",
                        "property": "background_color",
                        "before": "rgb(0, 0, 0)",
                        "after": "rgb(255, 255, 255)",
                    }, {
                        "component_key": "component:primary-control",
                        "property": "transform",
                        "before": "none",
                        "after": "matrix(1, 0, 0, 1, 8, 0)",
                    }] if changed else [])
                    mechanism = ({
                        "type": (
                            "hover-transition"
                            if source_state["trigger"]["type"] == "hover"
                            else "state-transition"
                        ),
                        "trigger_type": source_state["trigger"]["type"],
                        "changed_properties": len(changed_properties),
                    } if changed else None)
                    trigger_evidence = {
                        "type": source_state["trigger"]["type"],
                        "target": source_state["trigger"]["target"],
                        "target_component_keys": ["component:primary-control"],
                        "before_sha256": "1" * 64,
                        "after_sha256": ("2" * 64 if changed else "1" * 64),
                        "settled_sha256": ("2" * 64 if changed else "1" * 64),
                        "changed_properties": changed_properties,
                        "change_classification": {
                            "cosmetic": ([changed_properties[0]] if changed else []),
                            "structural_semantic": ([changed_properties[1]] if changed else []),
                            "diagnostic": [],
                        },
                        "duration_ms": 450 if changed else 0,
                        "settled": True,
                        "mechanism": mechanism,
                        "mechanism_count": 1 if changed else 0,
                    }
                    state_mechanisms = [*mechanisms]
                    if mechanism and not any(
                        item.get("type") == mechanism["type"]
                        for item in state_mechanisms
                    ):
                        state_mechanisms.append(mechanism)
                    state_score = json.loads(json.dumps(score_payload))
                    if mechanism:
                        state_score["type_instances"][mechanism["type"]] = 1
                        state_score["distinct_mechanisms"] = len({
                            item["type"] for item in state_mechanisms
                        })
                    states[profile][source_state["id"]] = {
                        "id": source_state["id"], "url": url,
                        "kind": source_state["kind"],
                        "trigger": source_state["trigger"],
                        "expectation": source_state["expectation"],
                        "navigation": self.navigation(url),
                        "trigger_application": {
                            "state_id": source_state["id"], "applied": True,
                            "target_count": 1, "navigation": None,
                            "trigger_evidence": trigger_evidence,
                        },
                        "trigger_evidence": trigger_evidence,
                        "evidence_frames": evidence,
                        "interaction_census": state_census,
                        "rendered_qa": state_rendered_qa,
                        "structure": structure_payload,
                        "mechanisms": state_mechanisms,
                        "score": state_score,
                        "scroll_traversal": {"complete": True, "surfaces": [{
                            "id": "document", "kind": "document", "complete": True
                        }]},
                    }
            payload["states_by_viewport"] = states
            inner_url = url.rstrip("/") + "/inner"
            study_urls = sorted({url, inner_url}) if inner else [url]
            payload["site_traversal_by_viewport"] = {
                profile: {
                    "profile": profile,
                    "origin": f"https://{url.split('/')[2]}",
                    "discovered_urls": study_urls,
                    "visited_urls": study_urls,
                    "missing_urls": [],
                    "complete": True,
                    "pages": [{
                        "url": page_url,
                        "navigation": self.navigation(page_url),
                        "structure": payload["first_screens"][profile],
                        "mechanisms": mechanisms,
                        "score": score_payload,
                        "state_inventory": {"inferred": [], "unreconciled": [], "complete": True},
                        "scroll_traversal": {"complete": True, "surfaces": [{
                            "id": "document", "kind": "document", "complete": True
                        }]},
                        "discovered_links": study_urls,
                    } for page_url in study_urls],
                    "interaction_census": traversal_census_by_profile[profile],
                    "rendered_qa": traversal_qa_by_profile[profile],
                    "sheet": {"mechanisms": mechanisms, "score": score_payload},
                }
                for profile in ("wide", "narrow")
            }
            payload["interaction_census_by_viewport"] = {
                profile: payload["site_traversal_by_viewport"][profile]["interaction_census"]
                for profile in ("wide", "narrow")
            }
            payload["rendered_qa_by_viewport"] = {
                profile: payload["site_traversal_by_viewport"][profile]["rendered_qa"]
                for profile in ("wide", "narrow")
            }
            payload["discovery_metadata"] = {
                profile: {
                    "discovered_urls": study_urls,
                    "visited_urls": study_urls,
                    "source_state_ids": ["primary-focus", "primary-hover", "rest"],
                }
                for profile in ("wide", "narrow")
            }
            payload["quality_observations"] = [
                {
                    "category": "responsive-first-screen",
                    "wide_dominant": payload["first_screens"]["wide"]["dominant"],
                    "narrow_dominant": payload["first_screens"]["narrow"]["dominant"],
                },
                {
                    "category": "experience-coverage",
                    "wide_pages": len(study_urls),
                    "narrow_pages": len(study_urls), "authored_state_cells": 6,
                },
                {
                    "category": "behavior",
                    "distinct_mechanisms": score_payload["distinct_mechanisms"],
                    "mechanisms": [item["type"] for item in mechanisms],
                    "responsive_state_results": [
                        {"profile": profile, "state_id": state_id}
                        for profile in ("wide", "narrow")
                        for state_id in ("rest", "primary-hover", "primary-focus")
                    ],
                },
            ]
            payload["defect_observations"] = []
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return (
            f"{kind}; .design-dna/references/{name}-observation.json "
            f"plus sha256:{sha256_of(path)}"
        )

    def sequence_block(
        self,
        rank: int,
        *,
        sheets: int = 24,
        duration: float = 96.0,
        tool: str = "record_reference.mjs",
        omit: tuple[int, ...] = (),
        short: tuple[int, ...] = (),
        static_all: bool = False,
        inventory_rows: int = 8,
        signature_sheets: str = "s004, s005",
        schema: int = 4,
        events: int = 24,
        signature_events: str = "wide/e0004, narrow/e0005",
        fps: int = 15,
    ) -> str:
        """Write a recording record, its sheets or events, and a sequence read."""
        name = f"strong-{rank}"
        if schema >= 2:
            return self._event_block(
                rank, events=events, duration=duration, tool=tool, omit=omit,
                short=short, static_all=static_all, inventory_rows=inventory_rows,
                signature_events=signature_events, schema=schema, fps=fps,
            )
        # the validator counts sheets against the read; it does not open every
        # sheet, and writing 96 PNGs per body() made the suite take ten minutes
        recording = {
            "tool": tool,
            "schema_version": 1,
            "id": name,
            "url": f"https://reference-{rank}.example.test/entry",
            "duration_s": duration,
            "fps": 15,
            "frames": sheets * 4,
            "frames_per_sheet": 4,
            "sheet_seconds": 0.4,
            "sheets": sheets,
            "sheet_files": [
                {"id": f"s{n:03d}", "file": f"{name}-sheets/s{n:03d}.png"}
                for n in range(1, sheets + 1)
            ],
            "video": {"file": f"{name}-recording.webm", "sha256": "0" * 64},
            "pages_visited": [f"https://reference-{rank}.example.test/entry"],
            "cursor_path": [],
        }
        recording_path = self.project / ".design-dna" / "references" / f"{name}-recording.json"
        recording_path.write_text(json.dumps(recording, indent=1), encoding="utf-8")
        lines = []
        for n in range(1, sheets + 1):
            if n in omit:
                continue
            if n in short:
                lines.append(f"- s{n:03d} (x): idle.")
            elif static_all:
                lines.append(f"- s{n:03d} ({(n - 1) * 0.4:.1f}): static, nothing changes, the cursor is still.")
            else:
                lines.append(f"- s{n:03d} ({(n - 1) * 0.4:.1f}): {SEQUENCE_LINE}.")
        inventory = [
            "## Behaviour inventory",
            "",
            "| # | Trigger | Element | Effect | Magnitude | Sheets |",
            "| --- | --- | --- | --- | --- | --- |",
            *[f"| {i} " + INVENTORY_ROW for i in range(1, inventory_rows + 1)],
        ]
        read_path = self.project / ".design-dna" / "references" / f"{name}-sequence-read.md"
        read_path.write_text(
            "\n".join([f"# Sequence read: {name}", "", "## Sheets", "", *lines, "", *inventory, ""]),
            encoding="utf-8",
        )
        return "\n".join((
            f"### {name}",
            f"- Recording: .design-dna/references/{name}-recording.json plus sha256:{sha256_of(recording_path)}",
            f"- Read: .design-dna/references/{name}-sequence-read.md plus sha256:{sha256_of(read_path)}",
            f"- Signature sheets: {signature_sheets}",
        ))

    def _event_block(
        self,
        rank: int,
        *,
        events: int,
        duration: float,
        tool: str,
        omit: tuple[int, ...],
        short: tuple[int, ...],
        static_all: bool,
        inventory_rows: int,
        signature_events: str,
        schema: int,
        fps: int,
    ) -> str:
        """A current recording counts events and binds complete traversal."""
        name = f"strong-{rank}"
        source_url = f"https://reference-{rank}.example.test/entry"
        inner_url = source_url + "/inner"
        contract_path, contract = self.state_contract(name, source_url)
        recorder_sha = sha256_of(SKILL / "scripts" / "record_reference.mjs")
        state_ids = [state["id"] for state in contract["states"]]
        kinds = ("load", "hover", "scroll", "travel", "click", "spontaneous")
        cache_key = (rank, events, duration, tool, schema, fps, recorder_sha)

        def finish_block(recording_path: Path, ledger_path: Path) -> str:
            lines: list[str] = []
            for profile in ("wide", "narrow"):
                for number in range(1, events + 1):
                    if profile == "wide" and number in omit:
                        continue
                    if profile == "wide" and number in short:
                        lines.append(f"- {profile}/e{number:04d} (x): idle.")
                    elif static_all:
                        lines.append(
                            f"- {profile}/e{number:04d} ({number * 2.1:.1f}s, hover): "
                            "static, nothing changes, the cursor is still."
                        )
                    else:
                        lines.append(
                            f"- {profile}/e{number:04d} ({number * 2.1:.1f}s, hover): "
                            f"{SEQUENCE_LINE}."
                        )
            inventory = [
                "## Behaviour inventory", "",
                "| # | Trigger | Element | Effect | Magnitude | Events |",
                "| --- | --- | --- | --- | --- | --- |",
                *[
                    f"| {index} "
                    + INVENTORY_ROW.replace(
                        "s004, s005", "wide/e0004, narrow/e0005"
                    )
                    for index in range(1, inventory_rows + 1)
                ],
            ]
            read_path = self.captures / f"{name}-sequence-read.md"
            read_path.write_text(
                "\n".join([
                    f"# Sequence read: {name}", "", "## Events", "",
                    *lines, "", *inventory, "",
                ]),
                encoding="utf-8",
            )
            return "\n".join((
                f"### {name}",
                f"- State contract: .design-dna/references/{contract_path.name} plus sha256:{sha256_of(contract_path)}",
                f"- Recording: .design-dna/references/{name}-recording.json plus sha256:{sha256_of(recording_path)}",
                f"- Recording artifact ledger: .design-dna/references/{name}-artifacts.json plus sha256:{sha256_of(ledger_path)}",
                f"- Read: .design-dna/references/{name}-sequence-read.md plus sha256:{sha256_of(read_path)}",
                f"- Signature events: {signature_events}",
            ))

        cached = _RECORDING_CACHE.get(cache_key)
        if cached is not None and cached.is_dir():
            clone_fixture_tree(cached, self.captures)
            return finish_block(
                self.captures / f"{name}-recording.json",
                self.captures / f"{name}-artifacts.json",
            )

        def artifact(relative: str, kind: str, profile: str | None) -> dict[str, object]:
            path = self.captures / relative
            return {
                "kind": kind,
                "profile": profile,
                "file": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_of(path),
            }

        profiles: dict[str, dict[str, object]] = {}
        all_artifacts: list[dict[str, object]] = []
        interaction_by_profile: dict[str, dict[str, object]] = {}
        captures: dict[str, dict[str, object]] = {}
        discovery: dict[str, dict[str, object]] = {}
        quality: list[dict[str, object]] = []
        frame_count = max(1, int(duration * fps * 0.9))
        for profile, width, height in (("wide", 1440, 900), ("narrow", 390, 844)):
            prefix = f"{name}-{profile}"
            frame_dir = self.captures / f"{prefix}-frames"
            frame_dir.mkdir(parents=True, exist_ok=True)
            frame_files: list[dict[str, object]] = []
            group_source: Path | None = None
            for number in range(1, frame_count + 1):
                frame = frame_dir / f"f{number:05d}.png"
                if number == 1 or (number - 1) % 500 == 0:
                    write_png(frame, rgb=(34, 72, 112))
                    group_source = frame
                else:
                    assert group_source is not None
                    try:
                        os.link(group_source, frame)
                    except OSError:
                        frame.write_bytes(group_source.read_bytes())
                frame_files.append(artifact(
                    frame.relative_to(self.captures).as_posix(), "frame", profile
                ))

            video_path = self.captures / f"{prefix}-recording.webm"
            video_path.write_bytes(b"fixture webm bytes\n")
            video = artifact(video_path.name, "video", profile)
            cursor_path = self.captures / f"{prefix}-cursor-path.json"
            cursor_path.write_text(json.dumps({"profile": profile, "actions": []}), encoding="utf-8")
            cursor = artifact(cursor_path.name, "cursor-path", profile)
            diff_path = self.captures / f"{prefix}-difference-signal.json"
            diff_path.write_text(json.dumps({"profile": profile, "fps": fps, "pct": [0, 1]}), encoding="utf-8")
            difference = artifact(diff_path.name, "difference-signal", profile)

            event_dir = self.captures / f"{prefix}-events"
            event_dir.mkdir(parents=True, exist_ok=True)
            event_files: list[dict[str, object]] = []
            for number in range(1, events + 1):
                kind = kinds[number % len(kinds)]
                event_path = event_dir / f"e{number:04d}-{kind}.png"
                write_png(event_path, width=16, height=16, rgb=(70, 90, 130))
                meta = artifact(
                    event_path.relative_to(self.captures).as_posix(),
                    "event-sheet", profile,
                )
                event_files.append({
                    "id": f"e{number:04d}", "file": meta["file"],
                    "bytes": meta["bytes"], "sha256": meta["sha256"],
                    "kind": kind, "target": "primary control",
                    "t": round(number * 2.1, 1), "frames_s": [1, 2, 3, 4],
                    "magnitude_pct": 4.2, "changed_area_pct": 31.0,
                    "region": "a large area at top left (31% of pixels)",
                    "settle_s": 0.6,
                })
                all_artifacts.append(meta)
            event_index_path = self.captures / f"{prefix}-events.md"
            event_index_path.write_text(f"# {name} {profile} events\n", encoding="utf-8")
            event_index = artifact(event_index_path.name, "events-index", profile)

            evidence: dict[str, dict[str, object]] = {}
            for moment, color in (("before", (30, 60, 90)), ("after", (60, 90, 120)), ("settled", (60, 90, 120))):
                evidence_path = self.captures / f"{prefix}-interaction-evidence" / f"00001-control-{moment}.png"
                write_png(evidence_path, width=width, height=height, rgb=color)
                meta = artifact(
                    evidence_path.relative_to(self.captures).as_posix(),
                    "interaction-frame", profile,
                )
                all_artifacts.append(meta)
                evidence[moment] = {
                    "file": meta["file"], "bytes": meta["bytes"],
                    "sha256": meta["sha256"],
                }
            interaction = self.interaction_census(name, source_url, profile, evidence)
            interaction_by_profile[profile] = interaction
            rendered_qa = self.rendered_qa(source_url, profile, evidence, name=name)
            urls = sorted({source_url, inner_url})
            coverage_payload = {
                "interactive_targets_discovered": 2,
                "interactive_targets_hovered": 2,
                "missing_interactive_targets": [],
                "hover_failures": {},
                "internal_pages_discovered": 2,
                "internal_pages_visited": 2,
                "internal_pages_discovered_urls": urls,
                "internal_pages_visited_urls": urls,
                "missing_internal_pages": [],
                "states_required": state_ids,
                "states_visited": state_ids,
                "missing_states": [],
                "incomplete_scroll_traversals": [],
                "state_inventories": [
                    {"url": page_url, "inferred": [], "unreconciled": [], "complete": True}
                    for page_url in urls
                ],
                "unreconciled_states": [],
                "duration_floor_met": duration >= 90,
                "complete": duration >= 90 and fps >= 15,
            }
            profiles[profile] = {
                "profile": profile,
                "viewport": {"name": profile, "width": width, "height": height},
                "duration_s": duration,
                "fps": fps,
                "video": video,
                "frames": {"count": frame_count, "directory": f"{prefix}-frames", "files": frame_files},
                "events": {"count": events, "directory": f"{prefix}-events", "files": event_files,
                           "index": event_index, "quiet": []},
                "cursor_path": cursor,
                "difference_signal": difference,
                "video_elements": [],
                "navigations": [self.navigation(source_url), self.navigation(inner_url)],
                "scroll_traversals": [
                    {"url": page_url, "complete": True, "surfaces": [{
                        "id": "document", "kind": "document", "complete": True
                    }]}
                    for page_url in urls
                ],
                "interaction_census": interaction,
                "rendered_qa": rendered_qa,
                "coverage": coverage_payload,
            }
            first = frame_files[0]
            captures[profile] = {
                "file": first["file"], "bytes": first["bytes"],
                "sha256": first["sha256"],
            }
            discovery[profile] = {
                "discovered_urls": urls, "visited_urls": urls,
                "states_required": state_ids, "states_visited": state_ids,
            }
            quality.append({
                "profile": profile, "pages_observed": 2, "states_observed": len(state_ids),
                "hover_targets_observed": 2, "event_sheets": events,
                "video_elements": 0,
            })
            all_artifacts.extend([video, *frame_files, cursor, difference, event_index])

        recording = {
            "tool": tool,
            "schema_version": schema,
            "producer_script_sha256": recorder_sha,
            "runtime_identity": {"record_reference.mjs": recorder_sha},
            "dependencies": {},
            "id": name,
            "url": source_url,
            "requested_url": source_url,
            "final_urls": {"wide": source_url, "narrow": source_url},
            "recorded_at": "2026-09-02T00:00:00Z",
            "minimum_duration_per_profile_s": duration,
            "fps": fps,
            "state_contract": {"file": contract_path.name, "sha256": sha256_of(contract_path)},
            "captures_by_viewport": captures,
            "discovery_metadata": discovery,
            "quality_observations": quality,
            "defect_observations": [],
            "interaction_census_by_viewport": interaction_by_profile,
            "rendered_qa_by_viewport": {
                profile: profiles[profile]["rendered_qa"]
                for profile in ("wide", "narrow")
            },
            "profiles": profiles,
            "coverage": {
                "wide_complete": duration >= 90 and fps >= 15,
                "narrow_complete": duration >= 90 and fps >= 15,
                "complete": duration >= 90 and fps >= 15,
            },
        }
        recording_path = self.project / ".design-dna" / "references" / f"{name}-recording.json"
        recording_path.write_text(json.dumps(recording, indent=1) + "\n", encoding="utf-8")
        all_artifacts.append({
            "kind": "recording", "profile": None,
            "file": recording_path.name, "bytes": recording_path.stat().st_size,
            "sha256": sha256_of(recording_path),
        })
        all_artifacts.sort(key=lambda item: str(item["file"]))
        ledger_core = {
            "schema_version": 1, "algorithm": "sha256",
            "recording": recording_path.name, "artifacts": all_artifacts,
        }
        ledger_payload = {
            **ledger_core,
            "sha256": INITIALIZER.canonical_json_sha256(ledger_core),
        }
        ledger_path = self.captures / f"{name}-artifacts.json"
        ledger_path.write_text(json.dumps(ledger_payload, indent=2) + "\n", encoding="utf-8")
        cache_root = _RECORDING_CACHE_ROOT / hashlib.sha256(
            repr(cache_key).encode("utf-8")
        ).hexdigest()
        cache_recording_tree(
            self.captures, cache_root, ledger_payload, ledger_path
        )
        _RECORDING_CACHE[cache_key] = cache_root
        return finish_block(recording_path, ledger_path)

    def interaction_block(self, rank: int) -> str:
        name = f"strong-{rank}"
        observation_path = self.captures / f"{name}-observation.json"
        recording_path = self.captures / f"{name}-recording.json"
        ledger_path = self.captures / f"{name}-artifacts.json"
        if not recording_path.is_file() or not ledger_path.is_file():
            self._event_block(
                rank, events=24, duration=96.0, tool="record_reference.mjs",
                omit=(), short=(), static_all=False, inventory_rows=8,
                signature_events="wide/e0004, narrow/e0005", schema=4, fps=15,
            )
        observed = json.loads(observation_path.read_text(encoding="utf-8"))
        recorded = json.loads(recording_path.read_text(encoding="utf-8"))
        ledger_cell = (
            f".design-dna/references/{name}-artifacts.json plus sha256:"
            f"{sha256_of(ledger_path)}"
        )

        def flatten(value: dict[str, object]) -> dict[tuple[str, str, str, str, str, int], dict[str, object]]:
            rows: dict[tuple[str, str, str, str, str, int], dict[str, object]] = {}
            occurrences: dict[tuple[str, str, str, str, str], int] = {}
            for profile in ("wide", "narrow"):
                census = value.get(profile)
                if not isinstance(census, dict):
                    continue
                for page in census["pages"]:
                    for target in page["targets"]:
                        for input_record in target["inputs"]:
                            state_id = input_record["source_state_id"] or "none"
                            base = (profile, page["url"], target["target_id"], input_record["input_kind"], state_id)
                            occurrence = occurrences.get(base, 0) + 1
                            occurrences[base] = occurrence
                            disposition = (
                                "exercised" if input_record["disposition"] == "sourceable-observed-behavior"
                                else "quiet" if input_record["disposition"] == "observed-quiet"
                                else "blocked hand-off"
                            )
                            rows[(*base, occurrence)] = {
                                "kind": target["kind"], "repeat_class": target["repeat_class"],
                                "repeat_index": target["repeat_index"], "repeat_count": target["repeat_count"],
                                "before": input_record["before_sha256"], "after": input_record["after_sha256"],
                                "settled": input_record["settled_sha256"], "behavior": input_record["behavior"],
                                "evidence": input_record["evidence"], "disposition": disposition,
                            }
                for state in census["page_states"]:
                    state_id = state["source_state_id"]
                    target_id = "page-state-" + hashlib.sha256(
                        f"{profile}\0{state['page_url']}\0{state_id}".encode("utf-8")
                    ).hexdigest()[:16]
                    base = (profile, state["page_url"], target_id, state["trigger"]["type"], state_id)
                    occurrence = occurrences.get(base, 0) + 1
                    occurrences[base] = occurrence
                    trigger = state["trigger_evidence"]
                    rows[(*base, occurrence)] = {
                        "kind": f"{state['kind']}-page-state",
                        "repeat_class": "page-state", "repeat_index": 1,
                        "repeat_count": 1, "before": trigger["before_sha256"],
                        "after": trigger["after_sha256"], "settled": trigger["settled_sha256"],
                        "behavior": trigger["behavior"], "evidence": state["evidence"],
                        "disposition": "quiet" if not trigger["changed_properties"] else "exercised",
                    }
            return rows

        observer_rows = flatten(observed.get("interaction_census_by_viewport", {}))
        recorder_rows = flatten(recorded.get("interaction_census_by_viewport", {}))

        def binding(meta: dict[str, object]) -> str:
            return (
                f".design-dna/references/{meta['file']} plus sha256:{meta['sha256']}"
            )

        table_rows: list[str] = []
        for key in sorted(set(observer_rows) & set(recorder_rows)):
            profile, page, target_id, input_kind, state_id, occurrence = key
            observer = observer_rows[key]
            recorder = recorder_rows[key]
            kind = (
                f"kind={observer['kind']}; repeat_class_sha256="
                f"{hashlib.sha256(str(observer['repeat_class']).encode('utf-8')).hexdigest()}; "
                f"repeat_index={observer['repeat_index']}; repeat_count={observer['repeat_count']}"
            )
            before = (
                f"observer_sha256={observer['before'] or 'null'}; "
                f"recorder_sha256={recorder['before'] or 'null'}"
            )
            after = (
                f"observer_after_sha256={observer['after'] or 'null'}; "
                f"observer_settled_sha256={observer['settled'] or 'null'}; "
                f"recorder_after_sha256={recorder['after'] or 'null'}; "
                f"recorder_settled_sha256={recorder['settled'] or 'null'}; "
                f"observer_behavior={observer['behavior']}; "
                f"recorder_behavior={recorder['behavior']}"
            )
            if observer["disposition"] == "blocked hand-off":
                evidence = f"observer=blocked; recorder=blocked; ledger={ledger_cell}"
            else:
                evidence = "; ".join([
                    f"observer_before={binding(observer['evidence']['before'])}",
                    f"observer_after={binding(observer['evidence']['after'])}",
                    f"observer_settled={binding(observer['evidence']['settled'])}",
                    f"recorder_before={binding(recorder['evidence']['before'])}",
                    f"recorder_after={binding(recorder['evidence']['after'])}",
                    f"recorder_settled={binding(recorder['evidence']['settled'])}",
                    f"ledger={ledger_cell}",
                ])
            table_rows.append(
                f"| target_id={target_id}; profile={profile}; page={page}; occurrence={occurrence} "
                f"| {kind} | input={input_kind}; source_state_id={state_id} | {before} | "
                f"{after} | {evidence} | {observer['disposition']} |"
            )
        observation_cell = (
            f".design-dna/references/{name}-observation.json plus sha256:"
            f"{sha256_of(observation_path)}"
        )
        recording_cell = (
            f".design-dna/references/{name}-recording.json plus sha256:"
            f"{sha256_of(recording_path)}"
        )
        return "\n".join((
            f"### {name} interaction census",
            f"- Observation: {observation_cell}",
            f"- Recording: {recording_cell}",
            f"- Recording artifact ledger: {ledger_cell}",
            "",
            INTERACTION_HEADER,
            INTERACTION_SEPARATOR,
            *table_rows,
        ))

    def static_sequence_block(self, rank: int) -> str:
        name = f"strong-{rank}"
        wide = self.capture_cell(f"{name}-wide", width=900)
        narrow = self.capture_cell(f"{name}-narrow", width=390)
        observation = self.observation_cell(
            name,
            kind="static",
            motion=False,
            url=f"https://reference-{rank}.example.test/entry",
        ).partition(";")[2].strip()
        styles = self.styles_cell(
            name, url=f"https://reference-{rank}.example.test/entry"
        )
        return "\n".join((
            f"### {name} static evidence",
            f"- Wide capture: {wide}",
            f"- Narrow capture: {narrow}",
            f"- Measured styles: {styles}",
            f"- Structure observation: {observation}",
            "- Dominant static relationship: A full-width typographic composition "
            "aligns the display line against the image grid and keeps the media, "
            "negative space, and edge hierarchy visibly locked at wide and narrow widths.",
        ))

    def failures(self, body: str) -> list[str]:
        return INITIALIZER.reference_dossier_failures(
            body,
            project=self.project,
            record_path=self.record_path,
        )

    def strong_row(
        self,
        rank: int,
        *,
        source: str,
        access: str = "public-gallery-entry",
        host: str | None = None,
        capture: str | None = None,
        narrow_capture: str | None = None,
        observation: str | None = None,
        signature: str = (
            "motion: The product images slide sideways under a pinned heading as the "
            "page is scrolled, which is what anyone would describe first."
        ),
        styles: str | None = None,
    ) -> str:
        url_host = host or f"reference-{rank}.example.test"
        observed = observation or self.observation_cell(
            f"strong-{rank}", url=f"https://{url_host}/entry"
        )
        return (
            f"| {rank} | Reference {rank} | https://{url_host}/entry | {source} | "
            f"2026-09-01 | {access} | "
            f"{capture or self.capture_cell(f'strong-{rank}-wide', width=900)} | "
            f"{narrow_capture or self.capture_cell(f'strong-{rank}-narrow', width=390)} | "
            "Studied the entry page, two inner pages, complete scroll progression, "
            "navigation, hover and click states, ending state, and narrow mobile recomposition. | "
            f"{observed} | "
            f"{styles or self.styles_cell(f'strong-{rank}', url=f'https://{url_host}/entry')} | "
            f"{signature} | "
            "Its truthful content model maps to the visitor task and audience; its "
            "brand and operating reality support the route progression, while its "
            "responsive narrow behavior and public rights/access boundary are "
            "compatible with this exact project. | A clear hierarchy, media relationship, and direct entry "
            "condition. | Do not reproduce its brand assets, writing, source code, "
            "or full page. |"
        )

    def candidate_row(
        self,
        index: int,
        *,
        source: str,
        selected: bool,
        host: str | None = None,
    ) -> str:
        url_host = host or f"reference-{index}.example.test"
        candidate_url = f"https://{url_host}/entry"
        observation_path = self.captures / f"strong-{index}-observation.json"
        if observation_path.is_file():
            observed = json.loads(observation_path.read_text(encoding="utf-8"))
            candidate_url = str(observed.get("url") or candidate_url)
            observation = (
                f".design-dna/references/{observation_path.name} plus sha256:"
                f"{sha256_of(observation_path)}"
            )
        else:
            observation = self.observation_cell(
                f"strong-{index}", url=candidate_url
            ).partition(";")[2].strip()
        source_id = source.split(";", 1)[0].strip().casefold()
        registry, _active, _failures = INITIALIZER.load_reference_source_registry()
        source_record = next(
            item for item in registry["sources"] if item.get("id") == source_id
        )
        source_history = (
            f"source={source_id}; discovery_path={source_record['url']}; "
            "filter=content model, visitor task, route states, responsive behavior, "
            "brand authority, and material evidence for the exact brief; "
            f"retrieval={source_record['retrieval']}; retrieved=2026-09-01; "
            "reuse_basis=fresh"
        )
        study = (
            f"evidence={observation}; wide_pages=2; narrow_pages=2; "
            "states=primary-focus, primary-hover, rest; "
            "progression=entry page through inner route, navigation, complete scroll "
            "progression, authored state, and ending condition"
        )
        brief_status = "pass" if selected else "fail"
        quality_status = "pass" if selected else "fail"
        brief = "; ".join([
            f"content_model={brief_status}",
            f"organization_context={brief_status}",
            "visitor_task=pass", "audience=pass",
            "brand_authority=pass", "operating_reality=pass",
            "route_responsive=pass", "rights_access=pass",
            f"evidence={observation}",
        ])
        quality = "; ".join([
            f"composition={quality_status}", "typography=pass", "media=pass",
            "responsive=pass", "interaction=pass", "finish=pass",
            "defects=none", f"evidence={observation}",
        ])
        disposition = (
            "brief_fit=pass; quality_execution=pass; disposition=selected; "
            "reason=generated captures and interaction sequence prove the exact "
            "content, visitor, route, responsive, and quality criteria"
            if selected
            else "brief_fit=fail; quality_execution=fail; disposition=rejected; "
            "reason=generated page evidence shows an incompatible content model "
            "and composition for the visitor task despite complete state review"
        )
        return (
            f"| Candidate {index} {candidate_url} | {source_history} | "
            f"{self.capture_cell(f'strong-{index}-wide', width=900)} | "
            f"{self.capture_cell(f'strong-{index}-narrow', width=390)} | "
            f"{study} | {brief} | {quality} | {disposition} |"
        )

    def route_manifest_cell(self, *, selected_rank: int = 1) -> tuple[str, str]:
        proof_build_id = "fixture-proof-build-0001"
        path = self.state / "route-manifest.json"
        reference_id = f"strong-{selected_rank}"
        observation = self.captures / f"{reference_id}-observation.json"
        path.write_text(json.dumps({
            "schema_version": 2,
            "manifest_id": "fixture-manifest-0001",
            "viewports": [
                {"name": "wide", "width": 1440, "height": 900},
                {"name": "narrow", "width": 390, "height": 844},
            ],
            "routes": [{
                "key": "home",
                "url": "http://127.0.0.1:4960/",
                "mapped_reference_rank": selected_rank,
                "mapped_reference_id": reference_id,
                "mapped_reference_observation": (
                    f".design-dna/references/{reference_id}-observation.json"
                ),
                "mapped_reference_sha256": sha256_of(observation),
                "states": [{
                    "id": "rest",
                    "kind": "rest",
                    "trigger": {"type": "none", "target": "document", "value": None},
                    "expectation": "initial settled route",
                    "mapped_reference_state_id": "rest",
                }, {
                    "id": "primary-hover", "kind": "interactive",
                    "trigger": {"type": "hover", "target": ".primary-control", "value": None},
                    "expectation": "Primary control changes under pointer hover.",
                    "mapped_reference_state_id": "primary-hover",
                }, {
                    "id": "primary-focus", "kind": "interactive",
                    "trigger": {"type": "focus", "target": ".primary-control", "value": None},
                    "expectation": "Primary control exposes keyboard focus.",
                    "mapped_reference_state_id": "primary-focus",
                }],
            }],
        }, indent=2) + "\n", encoding="utf-8")
        return (
            ".design-dna/route-manifest.json plus sha256:" + sha256_of(path),
            proof_build_id,
        )

    def visible_decision_manifest_cell(
        self,
        *,
        proof_build_id: str,
        selected_ranks: list[int],
    ) -> str:
        manifest_path = self.state / "route-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source_rows = []
        source_evidence: dict[str, dict[str, str]] = {}
        for rank in selected_ranks:
            observation = self.captures / f"strong-{rank}-observation.json"
            observed = json.loads(observation.read_text(encoding="utf-8"))
            capture = observed["captures_by_viewport"]["wide"]
            source_id = f"strong-{rank}"
            source_rows.append({
                "id": source_id,
                "path": f".design-dna/references/strong-{rank}-observation.json",
                "sha256": sha256_of(observation),
            })
            source_evidence[source_id] = {
                "path": f".design-dna/references/{capture['file']}",
                "sha256": capture["sha256"],
            }
        categories = list(INITIALIZER.VISIBLE_DECISION_CATEGORIES)
        decisions = []
        for index, category in enumerate(categories):
            state_id = "primary-hover" if category in {"control", "transition", "effect"} else "rest"
            source = source_rows[index % len(source_rows)]
            decisions.append({
                "decision_id": f"home-{state_id}-{category}",
                "category": category,
                "planned_surface": (
                    f"Primary home {category} relationship rendered in the exact {state_id} state"
                ),
                "route_keys": ["home"],
                "state_ids": [state_id],
                "source_reference_id": source["id"],
                "source_component_or_behavior": (
                    f"Measured {category} component and behavior from {source['id']}"
                ),
                "evidence": source_evidence[source["id"]],
                "disposition": "required",
            })
        payload = {
            "schema_version": 1,
            "record_type": "design-dna-visible-decision-source-manifest",
            "created_at": "2026-09-04T09:00:00-04:00",
            "proof_build_id": proof_build_id,
            "route_manifest": {
                "manifest_id": manifest["manifest_id"],
                "path": ".design-dna/route-manifest.json",
                "sha256": sha256_of(manifest_path),
            },
            "source_observations": source_rows,
            "planned_decision_ids": [row["decision_id"] for row in decisions],
            "decisions": decisions,
            "completeness": {
                "required_categories": categories,
                "covered_categories": categories,
                "placeholders_allowed": False,
                "generic_scaffold_allowed": False,
                "fallback_design_allowed": False,
                "unsourced_decisions": [],
            },
        }
        path = self.state / "visible-decision-sources.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return (
            ".design-dna/visible-decision-sources.json plus sha256:"
            + sha256_of(path)
        )

    def negative_row(
        self, index: int, *, source: str = "httpster; public listing reviewed"
    ) -> str:
        return (
            f"| Weak example {index} | https://weak-{index}.example.test/ | {source} | "
            f"2026-09-01 | public-gallery-entry | {self.capture_cell(f'weak-{index}')} | "
            "Its visible hierarchy turns a real visitor task into generic "
            "spectacle. | Keep task hierarchy and truthful content ahead of "
            "decorative treatment. |"
        )

    def body(
        self,
        *,
        candidate_rows: list[str] | None = None,
        strong_rows: list[str] | None = None,
        negative_rows: list[str] | None = None,
        selected: str = "1, 2, 3, 4",
        synthesis_rows: list[str] | None = None,
        ledger_check: str = "none",
        combination: str = (
            "strong-2 supplies the held screen and its type scale, strong-5 "
            "supplies the staggered index and its captions, and strong-1 "
            "supplies the control geometry; no single one of them carries all "
            "three, which is what makes this build its own."
        ),
        component_rows: list[str] | None = None,
        census: str | None = None,
        transfer_rows: list[str] | None = None,
        transfer_signatures: dict[int, str] | None = None,
        sequence_blocks: list[str] | None = None,
        interaction_blocks: list[str] | None = None,
    ) -> str:
        claimed = transfer_signatures or {}
        selected_list = [
            int(part.strip()) for part in selected.split(",") if part.strip().isdigit()
        ]
        if strong_rows is None:
            strong_rows = [
                self.strong_row(rank, source=DEFAULT_SOURCES[rank - 1])
                for rank in range(1, 7)
            ]
        if sequence_blocks is None:
            sequence_blocks = [self.sequence_block(rank) for rank in selected_list]
        if interaction_blocks is None:
            interaction_blocks = [self.interaction_block(rank) for rank in selected_list]
        if transfer_rows is None:
            proof = self.proof_cell()
            carriers = (
                "first screen", "layout grid", "display typeface", "color behavior",
            )
            transfer_rows = [
                f"| {rank} | {claimed.get(rank, TRANSFER_SIGNATURE)} | the "
                f"{carriers[index]} on the primary route | {proof} | the "
                f"{carriers[index]} would lose its pinned, travelling composition "
                "and the route hierarchy would no longer carry that arrangement |"
                for index, rank in enumerate([
                    int(part.strip()) for part in selected.split(",")
                    if part.strip().isdigit()
                ])
            ]
        # the sheet the behaviour rows cite has to exist for every body
        sheet_fixture = self.project / ".design-dna" / "references" / SHEET_FRAME_CELL
        if not sheet_fixture.is_file():
            write_png(sheet_fixture)
        if component_rows is None:
            carrier_rank = {
                "first screen": 1,
                "layout grid": 2,
                "display typeface": 3,
                "color behavior": 4,
            }
            component_rows = [
                f"| {name} | {carrier_rank.get(name, 1)} | "
                f"{SHEET_FRAME_CELL if name in BEHAVIOUR_COMPONENTS else f'strong-{carrier_rank.get(name, 1)}-frames/strong-{carrier_rank.get(name, 1)}-001-rest.png'} "
                f"| {STRUCTURE_CELL} | {VALUES_CELL} | the primary route |"
                for name in REQUIRED_COMPONENTS
            ]

        if candidate_rows is None:
            candidate_rows = [
                self.candidate_row(
                    rank,
                    source=DEFAULT_SOURCES[rank - 1],
                    selected=True,
                )
                for rank in range(1, 7)
            ] + [
                self.candidate_row(
                    7,
                    source="typewolf; Site of the Day 2026-06-29",
                    selected=False,
                    host="rejected-7.example.test",
                ),
                self.candidate_row(
                    8,
                    source="site-of-sites; editor's pick 2026-05-10",
                    selected=False,
                    host="rejected-8.example.test",
                ),
            ]
        if negative_rows is None:
            negative_rows = [self.negative_row(index) for index in range(1, 4)]
        if synthesis_rows is None:
            synthesis_rows = [
                f"| {selected} | Opening, product detail, navigation, and mobile "
                "reading | Adapt each relationship to the actual content model and "
                "visitor task. | Render wide and narrow candidates, then verify "
                "direct entry and non-copying boundaries. |"
            ]
        manifest_cell, manifest_build_id = self.route_manifest_cell(
            selected_rank=selected_list[0] if selected_list else 1
        )
        visible_decisions = self.visible_decision_manifest_cell(
            proof_build_id=manifest_build_id,
            selected_ranks=selected_list or [1],
        )
        if census is None:
            census = self.census_cell(
                selected_rank=selected_list[0] if selected_list else 1
            )
        return "\n".join((
            "## Research frame",
            "- Reference-selection brief (audience and arrival; visitor tasks; "
            "truthful content model, routes, and states; brand; operating reality; "
            "material/media; accessibility/performance/maintenance; rights/access): "
            "Families arrive from search and need to compare truthful products, "
            "understand evidence, and choose a safe next action across the home and "
            "detail routes using approved brand material and accessible controls.",
            "- Brief and priority-source rationale: The brief needs credible product "
            "orientation, material evidence, and a direct shopping path.",
            "- Current active registry audit date and limitations: 2026-09-01; public "
            "source entries only, with unavailable sources skipped.",
            "- Authorized-account basis, if any; otherwise `none`: none",
            "- Public-access disposition for blocked or unavailable sources: Those "
            "sources were excluded from the selected reference set.",
            "- Source-specific filters, sorts, categories, tags, and queries used "
            "with brief reason: Filtered each gallery by ecommerce and product "
            "categories and by recent entries, because the brief turns on a "
            "product-decision encounter; the default feed was not accepted.",
            "- Plausible alternate discovery paths checked alongside any "
            "status-based route: Typography and editorial tags were searched "
            "beside the award-tier listing so a status filter could not discard "
            "a better-fitting source.",
            f"- Ledger check (prior references reused, with the brief-specific reason, or `none`): {ledger_check}",
            "- Planned route/state coverage for `.design-dna/route-manifest.json`: "
            "Home and detail direct-entry routes at rest, hover, and focus across "
            "wide and narrow viewports.",
            "",
            "## Candidate comparison",
            CANDIDATE_HEADER,
            CANDIDATE_SEPARATOR,
            *candidate_rows,
            "",
            "## Strong references",
            STRONG_HEADER,
            STRONG_SEPARATOR,
            *strong_rows,
            "",
            "## Negative counterexamples",
            NEGATIVE_HEADER,
            NEGATIVE_SEPARATOR,
            *negative_rows,
            "",
            "## Selected synthesis",
            f"- Selected positive ranks (at least four distinct ranks, from at least two sources): {selected}",
            "- Project-specific organizing synthesis: The selected direction makes "
            "the product, evidence, and next decision visible in one coherent retail "
            "encounter rather than rotating unrelated treatments.",
            f"- Dominant visual grammar by route (one selected rank per route): "
            f"home uses rank {selected_list[0] if selected_list else 1} for its "
            "opening hierarchy, progression, control language, and narrow transformation.",
            "- Interaction or motion copied and where it is rendered, or static posture with evidence: The pinned heading with a "
            "sideways product rail from rank 1, rebuilt on the comparison route and "
            "confirmed in its rendered scroll sequence.",
            "- Negative-counterevidence result: The final direction retains visible "
            "task hierarchy and product specificity instead of decorative spectacle.",
            f"- Combination of references (which reference supplies which part, and why no single one of them is this build): {combination}",
            "- Execution improvements only (content, access, responsive resilience, "
            "performance, maintainability, or finish; no unsourced design): More "
            "complete truthful product detail, resilient focus behavior, and faster "
            "media delivery preserve the sourced visual relationships.",
            "- Direction record path and status: .design-dna/direction.md; draft "
            "selection is ready to bind before broad implementation.",
            "",
            SYNTHESIS_HEADER,
            SYNTHESIS_SEPARATOR,
            *synthesis_rows,
            "",
            "## Route manifest",
            f"- Route manifest: {manifest_cell}",
            "- First-screen gate: .design-dna/evidence/prebuild-runs/"
            "0123456789abcdef0123456789abcdef/first-screen-gate.json plus sha256:"
            + "a" * 64,
            f"- First-screen proof build ID and primary route key: build_id={manifest_build_id}; route_key=home",
            "- Final build ID used for the final gate: fixture-final-build-0001",
            "",
            "## Preimplementation visible decisions",
            f"- Visible decision source manifest: {visible_decisions}",
            "",
            "## Interaction census",
            *interaction_blocks,
            "",
            "## Sequence reads",
            *sequence_blocks,
            "",
            "## Signature transfer",
            TRANSFER_HEADER,
            TRANSFER_SEPARATOR,
            *transfer_rows,
            "",
            "## Component sources",
            f"- Component census: {census}",
            "",
            COMPONENT_HEADER,
            COMPONENT_SEPARATOR,
            *component_rows,
        ))


def registry_source(**overrides: object) -> dict[str, object]:
    source: dict[str, object] = {
        "id": "public-source",
        "name": "Public source",
        "url": "https://example.test/public",
        "status": "active",
        "access": "public",
        "retrieval": "fetch",
        "scope": "Design examples.",
        "notes": "Public examples are visible without an account.",
        "curation": "curated",
        "curation_note": "Every entry is chosen by a named editor.",
    }
    source.update(overrides)
    return source


def registry_payload(*sources: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "audited_on": "2026-09-01",
        "policy": "Public-only inspiration sources; do not bypass access controls.",
        "sources": list(sources),
    }


class ReferenceRegistryTests(unittest.TestCase):
    def test_bundled_registry_is_valid_and_excludes_restricted_sources(self) -> None:
        payload, active_sources, failures = INITIALIZER.load_reference_source_registry()
        self.assertEqual([], failures)
        self.assertEqual(1, payload["schema_version"])
        self.assertIn("awwwards", active_sources)
        self.assertNotIn("land-book", active_sources)
        for source in payload["sources"]:
            with self.subTest(source=source["id"]):
                self.assertIn(source["retrieval"], {"fetch", "browser", "none"})
                if source["status"] == "active":
                    self.assertIn(source["retrieval"], {"fetch", "browser"})

    def test_restricted_access_never_counts_as_active(self) -> None:
        for access in (
            "login-required",
            "paywalled",
            "security-blocked",
            "unavailable-current",
        ):
            with self.subTest(access=access):
                restricted = registry_payload(registry_source(
                    id="restricted-source",
                    access=access,
                    retrieval="none",
                    notes="Useful entries need restricted or unavailable access.",
                ))
                failures = INITIALIZER.reference_source_registry_failures(restricted)
                self.assertTrue(
                    any("does not have usable public access" in item for item in failures),
                    failures,
                )

        temporary = registry_payload(
            registry_source(),
            registry_source(
                id="temporarily-unavailable",
                url="https://example.test/",
                status="inactive",
                access="unavailable-current",
                retrieval="none",
                notes="A later public audit may reactivate this source.",
            ),
        )
        self.assertEqual([], INITIALIZER.reference_source_registry_failures(temporary))

    def test_active_sources_must_declare_a_real_retrieval_mode(self) -> None:
        missing = registry_payload(registry_source())
        del missing["sources"][0]["retrieval"]
        failures = INITIALIZER.reference_source_registry_failures(missing)
        self.assertTrue(
            any("unsupported shape" in item for item in failures),
            failures,
        )

        for retrieval in ("none", "scrape", ""):
            with self.subTest(retrieval=retrieval):
                wrong = registry_payload(registry_source(retrieval=retrieval))
                failures = INITIALIZER.reference_source_registry_failures(wrong)
                self.assertTrue(
                    any("retrieval" in item for item in failures),
                    failures,
                )


class ReferenceDossierTests(unittest.TestCase):
    def test_captured_spread_dossier_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            self.assertEqual([], fixture.failures(fixture.body()))

    def test_invented_references_without_captures_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            fabricated = [
                fixture.strong_row(
                    rank,
                    source=DEFAULT_SOURCES[rank - 1],
                    capture=(
                        f".design-dna/references/strong-{rank}.png plus "
                        "sha256:" + "0" * 64
                    ),
                )
                for rank in range(1, 7)
            ]
            failures = fixture.failures(fixture.body(strong_rows=fabricated))
            self.assertTrue(
                any("capture" in item and "is invalid" in item for item in failures),
                failures,
            )

    def test_capture_hash_must_match_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            body = fixture.body()
            real = fixture.capture_cell("strong-1-wide", width=900)
            wrong = real[: -64] + "f" * 64
            failures = fixture.failures(body.replace(real, wrong, 1))
            self.assertTrue(
                any("SHA-256 does not match" in item for item in failures),
                failures,
            )

    def test_capture_must_be_a_png_under_the_references_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            stray = fixture.project / "notes.png"
            write_png(stray)
            outside = f"notes.png plus sha256:{sha256_of(stray)}"
            rows = [
                fixture.strong_row(1, source="awwwards", capture=outside),
                *[
                    fixture.strong_row(rank, source=DEFAULT_SOURCES[rank - 1])
                    for rank in range(2, 7)
                ],
            ]
            failures = fixture.failures(fixture.body(strong_rows=rows))
            self.assertTrue(
                any(".design-dna/references/" in item for item in failures),
                failures,
            )

            fake_png = fixture.captures / "strong-9.png"
            fake_png.parent.mkdir(parents=True, exist_ok=True)
            fake_png.write_bytes(b"not a png at all, just bytes " * 4)
            not_png = f".design-dna/references/strong-9.png plus sha256:{sha256_of(fake_png)}"
            rows = [
                fixture.strong_row(1, source="awwwards", capture=not_png),
                *[
                    fixture.strong_row(rank, source=DEFAULT_SOURCES[rank - 1])
                    for rank in range(2, 7)
                ],
            ]
            failures = fixture.failures(fixture.body(strong_rows=rows))
            self.assertTrue(
                any("not a PNG" in item for item in failures),
                failures,
            )

    def test_count_is_a_floor_with_contiguous_ranks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            five = [
                fixture.strong_row(rank, source=DEFAULT_SOURCES[rank - 1])
                for rank in range(1, 6)
            ]
            failures = fixture.failures(fixture.body(strong_rows=five))
            self.assertTrue(
                any("at least six strong-reference rows" in item for item in failures),
                failures,
            )

            eight_sources = (*DEFAULT_SOURCES, "site-of-sites; editor's pick, 2026-04-02",
                             "typewolf; Site of the Day 2026-03-11")
            eight = [
                fixture.strong_row(rank, source=eight_sources[rank - 1])
                for rank in range(1, 9)
            ]
            compared = [
                fixture.candidate_row(
                    rank,
                    source=eight_sources[rank - 1],
                    selected=True,
                )
                for rank in range(1, 9)
            ] + [
                fixture.candidate_row(
                    9,
                    source="typewolf; Site of the Day 2026-03-10",
                    selected=False,
                    host="rejected-9.example.test",
                ),
                fixture.candidate_row(
                    10,
                    source="site-of-sites; editor's pick 2026-03-09",
                    selected=False,
                    host="rejected-10.example.test",
                ),
            ]
            self.assertEqual([], fixture.failures(fixture.body(
                strong_rows=eight,
                candidate_rows=compared,
            )))

            gapped = [row for row in eight if not row.startswith("| 4 |")]
            failures = fixture.failures(fixture.body(strong_rows=gapped))
            self.assertTrue(
                any("1 through" in item and "exactly once" in item for item in failures),
                failures,
            )

    def test_references_must_spread_across_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            one_source = [
                fixture.strong_row(rank, source="awwwards") for rank in range(1, 7)
            ]
            failures = fixture.failures(fixture.body(strong_rows=one_source))
            self.assertTrue(
                any("at least three distinct active public sources" in item for item in failures),
                failures,
            )

            lopsided_sources = ("awwwards; Site of the Day 2026-08-14",) * 4 + (
                "godly; editor's pick, 2026-08-02", "typewolf; Site of the Day 2026-06-30")
            lopsided = [
                fixture.strong_row(rank, source=lopsided_sources[rank - 1])
                for rank in range(1, 7)
            ]
            failures = fixture.failures(fixture.body(strong_rows=lopsided))
            self.assertTrue(
                any("more than half" in item for item in failures),
                failures,
            )

    def test_live_references_cannot_all_come_from_one_host(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            same_host = [
                fixture.strong_row(
                    rank,
                    source=DEFAULT_SOURCES[rank - 1],
                    access="public-live",
                    host="one-site.example.test",
                )
                for rank in range(1, 7)
            ]
            failures = fixture.failures(fixture.body(strong_rows=same_host))
            self.assertTrue(
                any("same host" in item for item in failures),
                failures,
            )

    def test_blocked_source_and_paywalled_entry_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            rows = [
                fixture.strong_row(rank, source=DEFAULT_SOURCES[rank - 1])
                for rank in range(1, 6)
            ]
            rows.append(
                fixture.strong_row(6, source="land-book", access="paywalled")
            )
            failures = fixture.failures(fixture.body(strong_rows=rows))
            self.assertTrue(
                any("active public source ID" in item for item in failures),
                failures,
            )
            self.assertTrue(
                any("blocked or paywalled entries cannot qualify" in item for item in failures),
                failures,
            )

    def test_negative_counterexamples_need_three_captured_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            two = [fixture.negative_row(index) for index in range(1, 3)]
            failures = fixture.failures(fixture.body(negative_rows=two))
            self.assertTrue(
                any("at least three negative counterexample rows" in item for item in failures),
                failures,
            )

    def test_synthesis_needs_four_references_from_two_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            failures = fixture.failures(fixture.body(selected="1, 2, 3"))
            self.assertTrue(
                any("at least four distinct positive ranks" in item for item in failures),
                failures,
            )

            # Ranks 1, 2, 5, 6 span awwwards, godly, and typewolf; ranks 1-4
            # under a two-source layout collapse to one source.
            single_source_sources = ("awwwards; Site of the Day 2026-08-14",) * 3 + (
                "godly; editor's pick, 2026-08-02",) * 2 + ("typewolf; Site of the Day 2026-06-30",)
            rows = [
                fixture.strong_row(rank, source=single_source_sources[rank - 1])
                for rank in range(1, 7)
            ]
            failures = fixture.failures(
                fixture.body(strong_rows=rows, selected="1, 2, 3, 4")
            )
            # 1, 2, 3 are awwwards and 4 is godly: two sources, so this passes.
            self.assertEqual([], failures)

            only_awwwards = [
                fixture.strong_row(rank, source=("awwwards; Site of the Day 2026-08-14",) * 3 + (
                    "godly; editor's pick, 2026-08-02", "site-of-sites; editor's pick, 2026-05-11",
                    "typewolf; Site of the Day 2026-06-30"))
                if False else fixture.strong_row(
                    rank,
                    source=(("awwwards; Site of the Day 2026-08-14",) * 3 + (
                        "godly; editor's pick, 2026-08-02",
                        "site-of-sites; editor's pick, 2026-05-11",
                        "typewolf; Site of the Day 2026-06-30"))[rank - 1],
                )
                for rank in range(1, 7)
            ]
            failures = fixture.failures(
                fixture.body(strong_rows=only_awwwards, selected="1, 2, 3, 3")
            )
            self.assertTrue(
                any("at least four distinct positive ranks" in item for item in failures),
                failures,
            )

    def test_synthesis_rows_may_only_name_selected_ranks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            rows = [
                "| 1, 2, 6 | Opening and product detail | Adapted to the content "
                "model. | Render and verify. |",
            ]
            failures = fixture.failures(
                fixture.body(selected="1, 2, 3, 4", synthesis_rows=rows)
            )
        self.assertTrue(
            any("must name only selected positive ranks" in item for item in failures),
            failures,
        )


class ReferenceSelectionQualificationTests(unittest.TestCase):
    def test_reused_source_requires_fresh_bound_revalidation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            rows = [
                fixture.candidate_row(
                    index,
                    source=DEFAULT_SOURCES[(index - 1) % len(DEFAULT_SOURCES)].split(";", 1)[0],
                    selected=index <= 6,
                )
                for index in range(1, 9)
            ]
            rows[0] = rows[0].replace("reuse_basis=fresh", "reuse_basis=revalidated-reuse")
            failures = fixture.failures(fixture.body(candidate_rows=rows))
            self.assertTrue(any("source history must use the exact" in item for item in failures), failures)
            self.assertTrue(any("reused candidate has no bound prior evidence" in item for item in failures), failures)

    """A reference set is compared for this brief, never filled at random."""

    def test_first_six_convenient_results_are_not_a_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            candidates = [
                project.candidate_row(
                    rank, source=DEFAULT_SOURCES[rank - 1], selected=True
                )
                for rank in range(1, 7)
            ]
            failures = project.failures(project.body(candidate_rows=candidates))
        self.assertTrue(any("at least eight" in item for item in failures), failures)

    def test_award_label_cannot_replace_exact_brief_fit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            candidates = [
                project.candidate_row(
                    rank, source=DEFAULT_SOURCES[rank - 1], selected=True
                )
                for rank in range(1, 7)
            ] + [
                project.candidate_row(
                    7, source="typewolf; Site of the Day 2026-03-10",
                    selected=False, host="rejected-7.example.test",
                ),
                project.candidate_row(
                    8, source="site-of-sites; editor's pick 2026-03-09",
                    selected=False, host="rejected-8.example.test",
                ),
            ]
            cells = candidates[0].split("|")
            cells[6] = " It won an award and looks cool. "
            candidates[0] = "|".join(cells)
            failures = project.failures(project.body(candidate_rows=candidates))
        self.assertTrue(any("brief-fit" in item for item in failures), failures)

    def test_audience_and_task_cannot_replace_organization_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            body = project.body().replace(
                "organization_context=pass; ", "", 1
            )
            failures = project.failures(body)
        self.assertTrue(
            any("brief-fit gate must name every exact criterion" in item for item in failures),
            failures,
        )

    def test_one_capture_cannot_pose_as_wide_and_narrow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            candidates = [
                project.candidate_row(
                    rank, source=DEFAULT_SOURCES[rank - 1], selected=True
                )
                for rank in range(1, 7)
            ] + [
                project.candidate_row(
                    7, source="typewolf; Site of the Day 2026-03-10",
                    selected=False, host="rejected-7.example.test",
                ),
                project.candidate_row(
                    8, source="site-of-sites; editor's pick 2026-03-09",
                    selected=False, host="rejected-8.example.test",
                ),
            ]
            cells = candidates[0].split("|")
            cells[4] = cells[3]
            candidates[0] = "|".join(cells)
            failures = project.failures(project.body(candidate_rows=candidates))
        self.assertTrue(
            any("distinct wide and narrow" in item for item in failures), failures
        )

    def test_candidate_set_needs_real_rejections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            sources = (*DEFAULT_SOURCES, DEFAULT_SOURCES[4], DEFAULT_SOURCES[5])
            candidates = [
                project.candidate_row(rank, source=sources[rank - 1], selected=True)
                for rank in range(1, 9)
            ]
            failures = project.failures(project.body(candidate_rows=candidates))
        self.assertTrue(any("at least two" in item for item in failures), failures)

    def test_route_manifest_rejects_the_obsolete_mutable_build_id(self) -> None:
        payload = {
            "schema_version": 2,
            "manifest_id": "fixture-manifest-0001",
            "viewports": [
                {"name": "wide", "width": 1440, "height": 900},
                {"name": "narrow", "width": 390, "height": 844},
            ],
            "routes": [{
                "key": "home",
                "url": "http://127.0.0.1:4960/",
                "mapped_reference_rank": 1,
                "mapped_reference_id": "strong-1",
                "mapped_reference_observation": ".design-dna/references/strong-1-observation.json",
                "mapped_reference_sha256": "a" * 64,
                "states": [{
                    "id": "rest",
                    "kind": "rest",
                    "trigger": {"type": "none", "target": "document", "value": None},
                    "expectation": "initial settled route",
                    "mapped_reference_state_id": "rest",
                }],
            }],
            "build_id": "obsolete-mutable-build-id",
        }
        failures = INITIALIZER.route_manifest_payload_failures(payload)
        self.assertTrue(any("exact versioned object shape" in item for item in failures), failures)

    def test_preimplementation_visible_decisions_cannot_omit_or_placeholder_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            body = project.body()
            manifest_path = project.state / "visible-decision-sources.json"
            old_binding = (
                ".design-dna/visible-decision-sources.json plus sha256:"
                + sha256_of(manifest_path)
            )
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["decisions"] = payload["decisions"][1:]
            payload["decisions"][0]["planned_surface"] = "TODO placeholder"
            payload["completeness"]["generic_scaffold_allowed"] = True
            manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            body = body.replace(
                old_binding,
                ".design-dna/visible-decision-sources.json plus sha256:"
                + sha256_of(manifest_path),
            )
            failures = project.failures(body)
        joined = "\n".join(failures)
        self.assertIn("planned IDs do not equal", joined)
        self.assertIn("no scaffold/fallback/placeholder escape", joined)
        self.assertIn("contains placeholder or fallback", joined)

    def test_visible_decision_cannot_bind_a_hand_written_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            body = project.body()
            manifest_path = project.state / "visible-decision-sources.json"
            old_binding = (
                ".design-dna/visible-decision-sources.json plus sha256:"
                + sha256_of(manifest_path)
            )
            fake = project.captures / "producer-note.txt"
            fake.write_text("I saw something like this and chose it myself.\n", encoding="utf-8")
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["decisions"][0]["evidence"] = {
                "path": ".design-dna/references/producer-note.txt",
                "sha256": sha256_of(fake),
            }
            manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            body = body.replace(
                old_binding,
                ".design-dna/visible-decision-sources.json plus sha256:"
                + sha256_of(manifest_path),
            )
            failures = project.failures(body)
        self.assertTrue(
            any("not an immutable generated artifact" in item for item in failures),
            failures,
        )

    def test_visible_decision_rejects_a_forged_file_pair_inside_observation_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            project.body()
            observation_path = project.captures / "strong-1-observation.json"
            fake = project.captures / "producer-note.txt"
            fake.write_text("Hand-written design justification.\n", encoding="utf-8")
            observation = json.loads(observation_path.read_text(encoding="utf-8"))
            observation["forged_evidence"] = {
                "file": fake.name,
                "sha256": sha256_of(fake),
            }
            observation_path.write_text(
                json.dumps(observation, indent=2) + "\n", encoding="utf-8"
            )
            manifest_path = project.state / "route-manifest.json"
            route_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            route_manifest["routes"][0]["mapped_reference_sha256"] = sha256_of(
                observation_path
            )
            manifest_path.write_text(
                json.dumps(route_manifest, indent=2) + "\n", encoding="utf-8"
            )
            source_manifest_path = project.state / "visible-decision-sources.json"
            source_manifest = json.loads(
                source_manifest_path.read_text(encoding="utf-8")
            )
            for row in source_manifest["source_observations"]:
                if row["id"] == "strong-1":
                    row["sha256"] = sha256_of(observation_path)
            source_manifest["route_manifest"]["sha256"] = sha256_of(manifest_path)
            source_manifest["decisions"][0]["source_reference_id"] = "strong-1"
            source_manifest["decisions"][0]["evidence"] = {
                "path": ".design-dna/references/producer-note.txt",
                "sha256": sha256_of(fake),
            }
            failures = INITIALIZER.visible_decision_source_manifest_failures(
                source_manifest,
                project=project.project,
                route_manifest=route_manifest,
                route_manifest_path=manifest_path,
                proof_identity="build_id=fixture-proof-build-0001; route_key=home",
            )
        self.assertTrue(
            any("not an immutable generated artifact" in item for item in failures),
            failures,
        )

    def test_combination_and_ledger_check_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            failures = fixture.failures(fixture.body(combination=""))
            self.assertTrue(
                any("Combination of references" in item for item in failures),
                failures,
            )
            failures = fixture.failures(fixture.body(ledger_check=""))
            self.assertTrue(
                any("Ledger check" in item for item in failures),
                failures,
            )
            self.assertEqual([], fixture.failures(fixture.body(ledger_check="none")))


class ReferenceDossierGateTests(unittest.TestCase):
    def test_enterprise_profile_initializes_the_reference_dossier_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / ".design-dna"
            INITIALIZER.render_new_state(
                SKILL,
                state,
                "test-fixture",
                INITIALIZER.PROFILES["enterprise-candidate"],
                ("standard", "enterprise-candidate"),
            )
            payload = json.loads((state / "state.json").read_text(encoding="utf-8"))
            self.assertIn("reference-dossier", payload["records"])
            self.assertIn(
                "reference-led-direction",
                payload["evidence_contract"]["applicable_capabilities"],
            )
            dossier = (state / "reference-dossier.md").read_text(encoding="utf-8")
            self.assertIn("## Strong references", dossier)
            self.assertIn("Capture path and SHA-256", dossier)
            self.assertIn("Combination of references", dossier)
            direction = (state / "direction.md").read_text(encoding="utf-8")
            visual = (state / "visual-review.md").read_text(encoding="utf-8")
            self.assertIn(
                "## Reference-led direction (required for public candidates)",
                direction,
            )
            self.assertIn("Combination of references", direction)
            self.assertIn(
                "## Reference-led direction closure (required for public candidates)",
                visual,
            )
            self.assertIn("Combination result", visual)

    def test_prebuild_blocks_an_enterprise_candidate_with_a_draft_dossier(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            INITIALIZER.render_new_state(
                SKILL,
                state,
                "test-fixture",
                INITIALIZER.PROFILES["enterprise-candidate"],
                ("standard", "enterprise-candidate"),
            )
            failures = INITIALIZER.prebuild_failures(project)
            self.assertTrue(
                any("reference-dossier.md remains draft" in item for item in failures),
                failures,
            )

    def test_prebuild_warns_when_a_standard_state_has_no_dossier(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            INITIALIZER.render_new_state(
                SKILL,
                state,
                "test-fixture",
                INITIALIZER.PROFILES["standard"],
                ("standard",),
            )
            warnings = INITIALIZER.prebuild_warnings(project)
            self.assertTrue(
                any(
                    "reference-dossier" in item and "enterprise-candidate" in item
                    for item in warnings
                ),
                warnings,
            )

            state_quick = Path(temporary) / "quick" / ".design-dna"
            state_quick.parent.mkdir()
            INITIALIZER.render_new_state(
                SKILL,
                state_quick,
                "test-fixture",
                INITIALIZER.PROFILES["quick"],
                ("quick",),
            )
            self.assertEqual([], INITIALIZER.prebuild_warnings(state_quick.parent))

    def test_migration_reopens_missing_enterprise_reference_dossier(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / ".design-dna"
            INITIALIZER.render_new_state(
                SKILL,
                state,
                "test-fixture",
                INITIALIZER.PROFILES["enterprise-candidate"],
                ("standard", "enterprise-candidate"),
            )
            state_path = state / "state.json"
            legacy = json.loads(state_path.read_text(encoding="utf-8"))
            legacy["schema_version"] = 1
            legacy["records"].remove("reference-dossier")
            legacy["evidence_contract"]["applicable_capabilities"].remove(
                "reference-led-direction"
            )
            state_path.write_text(
                json.dumps(legacy, indent=2) + "\n",
                encoding="utf-8",
            )
            (state / "reference-dossier.md").unlink()

            updated = INITIALIZER.migrate_staged_state(state, "test-fixture")

            migrated = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIn("reference-dossier", updated)
            self.assertIn("reference-dossier", migrated["records"])
            self.assertIn(
                "reference-led-direction",
                migrated["evidence_contract"]["applicable_capabilities"],
            )
            self.assertEqual(
                "draft",
                INITIALIZER.parse_frontmatter(state / "reference-dossier.md")[
                    "record_status"
                ],
            )


class ReferenceLedClosureTests(unittest.TestCase):
    def closure(self, **overrides: str) -> str:
        values = {
            "Dossier result": ".design-dna/reference-dossier.md complete; public-gallery entries only; ranks 1, 2, 4, 6",
            "Candidate selection result": "Eight complete candidates were compared; six were selected and two rejected for concrete brief-fit failures.",
            "Complete-study result": "Entry, inner pages, full progression, interaction states, ending, and wide/narrow behavior were reviewed.",
            "Brief-fit result": "Content model, visitor task, audience, brand, operating reality, route, responsive, rights, and access fit were verified.",
            "Positive synthesis": "One product-led opening and a comparison rail adapted from ranks 1, 2, and 6.",
            "Negative counterevidence": "The spectacle-first openings named in the counterexamples were avoided.",
            "Rights boundary": "No brand identifiers, copy, media, code, or whole pages were reproduced.",
            "Lineage result": "Wide and narrow renders beside the selected captures show the lineage in the first screen, type scale, and media treatment.",
            "Rendered result": "Wide and narrow renders confirm the synthesis on every affected route.",
            "Dominant grammar result": "Home maps to rank 1 and the detail route maps to rank 2; supporting sources retain the same hierarchy and controls.",
            "Combination result": "Rank 1 supplies the opening and rank 2 supplies the comparison rail within one sourced grammar.",
            "Route manifest": ".design-dna/route-manifest.json plus sha256:" + "0" * 64 + "; build fixture-build-0001",
            "Gate result": ".design-dna/evidence/gate.json plus sha256:" + "0" * 64,
            "Mechanism diff": ".design-dna/evidence/mechanism-diff.json plus sha256:" + "0" * 64,
            "Structure diff": ".design-dna/evidence/structure-diff.json plus sha256:" + "0" * 64,
            "Reference-led direction disposition": "keep",
        }
        values.update(overrides)
        return "\n".join(f"- {label}: {value}" for label, value in values.items())

    def test_complete_closure_passes(self) -> None:
        self.assertEqual(
            [], INITIALIZER.reference_led_closure_label_failures(self.closure())
        )

    def test_combination_result_is_required(self) -> None:
        for value in ("", "n/a", "see above"):
            with self.subTest(value=value):
                failures = INITIALIZER.reference_led_closure_label_failures(
                    self.closure(**{"Combination result": value})
                )
                self.assertTrue(
                    any("'Combination result'" in item for item in failures),
                    failures,
                )

    def test_untouched_template_tokens_do_not_pass(self) -> None:
        template = (SKILL / "templates" / "visual-review-template.md").read_text(
            encoding="utf-8"
        )
        section = template.split(
            "## Reference-led direction closure (required for public candidates)", 1
        )[1].split("## Connected public experience closure", 1)[0]
        self.assertIn("__REPLACE_WITH_", section)
        # the record-level validator rejects unresolved tokens; the label
        # check must also refuse the disposition placeholder
        failures = INITIALIZER.reference_led_closure_label_failures(section)
        self.assertTrue(
            any("disposition must be" in item for item in failures),
            failures,
        )

    def test_disposition_must_be_one_of_the_named_values(self) -> None:
        for value in ("maybe", "keep / revise", "approved"):
            with self.subTest(value=value):
                failures = INITIALIZER.reference_led_closure_label_failures(
                    self.closure(**{"Reference-led direction disposition": value})
                )
                self.assertTrue(
                    any("disposition must be" in item for item in failures),
                    failures,
                )
        for value in ("keep", "Reopen direction", "BLOCKED"):
            with self.subTest(value=value):
                self.assertEqual(
                    [],
                    INITIALIZER.reference_led_closure_label_failures(
                        self.closure(**{"Reference-led direction disposition": value})
                    ),
                )


class ObservationGateTests(unittest.TestCase):
    """The observation gate exists because prose did not bind the producer.

    Told to watch a reference scroll, a producer teleported the scroll
    position, screenshotted the resting state and reported motion it had never
    seen. Each case below is that failure in one of its forms.
    """

    def run_with(self, **observation):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = []
            sequence_blocks = []
            transfer_signatures: dict[int, str] = {}
            for rank in range(1, 7):
                kwargs = dict(observation) if rank == 1 else {}
                host = f"reference-{rank}.example.test"
                kind = str(kwargs.get("kind", "motion"))
                cell = project.observation_cell(
                    f"strong-{rank}",
                    url=kwargs.pop("url", f"https://{host}/entry"),
                    **kwargs,
                )
                signature = (
                    "static: A full-width typographic composition aligns the display "
                    "line against the image grid and preserves the media, negative "
                    "space, and edge hierarchy at wide and narrow widths."
                    if kind == "static"
                    else None
                )
                rows.append(
                    project.strong_row(
                        rank,
                        source=DEFAULT_SOURCES[rank - 1],
                        observation=cell,
                        **({"signature": signature} if signature else {}),
                    )
                )
                if rank <= 4:
                    sequence_blocks.append(
                        project.static_sequence_block(rank)
                        if kind == "static"
                        else project.sequence_block(rank)
                    )
                    if signature:
                        transfer_signatures[rank] = signature
            return project.failures(project.body(
                strong_rows=rows,
                sequence_blocks=sequence_blocks,
                transfer_signatures=transfer_signatures or None,
            ))

    def test_watched_motion_passes(self) -> None:
        self.assertEqual([], self.run_with())

    def test_static_signature_without_motion_passes(self) -> None:
        self.assertEqual([], self.run_with(kind="static", motion=False))

    def test_motion_claim_without_observed_motion_is_rejected(self) -> None:
        failures = self.run_with(kind="motion", motion=False)
        self.assertTrue(
            any("claims a motion signature" in item for item in failures), failures
        )

    def test_ad_hoc_capture_script_is_rejected(self) -> None:
        failures = self.run_with(tool="my-own-capture.js")
        self.assertTrue(
            any("packaged" in item and "observe_reference.mjs" in item for item in failures),
            failures,
        )

    def test_teleported_single_hold_is_rejected(self) -> None:
        failures = self.run_with(holds=1)
        self.assertTrue(
            any("scroll positions" in item for item in failures), failures
        )

    def test_session_without_hover_is_rejected(self) -> None:
        failures = self.run_with(hovers=0)
        self.assertTrue(any("hover" in item for item in failures), failures)

    def test_observation_of_a_different_site_is_rejected(self) -> None:
        failures = self.run_with(url="https://somewhere-else.example.test/")
        self.assertTrue(
            any("is not the site this row names" in item for item in failures), failures
        )

    def test_missing_kind_prefix_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            cell = project.observation_cell("strong-1")
            bare = cell.split("; ", 1)[1]
            rows = [
                project.strong_row(1, source=DEFAULT_SOURCES[0], observation=bare)
            ] + [
                project.strong_row(rank, source=DEFAULT_SOURCES[rank - 1])
                for rank in range(2, 7)
            ]
            failures = project.failures(project.body(strong_rows=rows))
        self.assertTrue(
            any("must begin with the signature kind" in item for item in failures),
            failures,
        )


class MechanismGateTests(unittest.TestCase):
    """6.7.0. Each case is a build the owner rejected, in the form it took."""

    def rows_with_first(self, project, **first):
        rows = []
        for rank in range(1, 7):
            host = f"reference-{rank}.example.test"
            kwargs = dict(first) if rank == 1 else {}
            signature = kwargs.pop("signature", None)
            cell = project.observation_cell(
                f"strong-{rank}", url=kwargs.pop("url", f"https://{host}/entry"), **kwargs
            )
            extra = {"signature": signature} if signature else {}
            rows.append(project.strong_row(
                rank, source=DEFAULT_SOURCES[rank - 1], observation=cell, **extra
            ))
        return rows

    def run_with(self, **first):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            # the transfer row copies the signature, so an overridden signature
            # has to travel with it
            return project.failures(project.body(
                strong_rows=self.rows_with_first(project, **first),
                transfer_signatures={1: first["signature"]} if "signature" in first else None,
            ))

    def test_rich_site_passes(self) -> None:
        self.assertEqual([], self.run_with())

    def test_an_older_schema_session_is_rejected(self) -> None:
        failures = self.run_with(schema=2)
        self.assertTrue(any("schema_version 5" in item for item in failures), failures)

    def test_session_without_mechanism_sheet_is_rejected(self) -> None:
        failures = self.run_with(sheet=False)
        self.assertTrue(any("mechanism sheet" in item for item in failures), failures)

    def test_thin_site_with_one_mechanism_is_rejected(self) -> None:
        # bodeyco.com: one picture at a time and a clock; the owner called it crap on sight
        failures = self.run_with(distinct=1)
        self.assertTrue(any("thin site" in item and "distinct" in item for item in failures), failures)

    def test_one_animated_hero_over_a_static_page_is_rejected(self) -> None:
        failures = self.run_with(coverage=0.2)
        self.assertTrue(any("thin site" in item and "depth" in item for item in failures), failures)

    def test_signature_that_names_a_subject_is_rejected(self) -> None:
        # the sidewalk crack, verbatim from the rejected dossiers
        for sidewalk in (
            "motion: Warm domestic object people buy for their home, photography led, with an appealing atmosphere.",
            "motion: Pure black page with a large opening paragraph and a fashionable visual mood throughout.",
            "motion: Stark white, product alone, hairline sans, and a premium feeling across the entire experience.",
        ):
            with self.subTest(signature=sidewalk):
                failures = self.run_with(signature=sidewalk)
                self.assertTrue(
                    any("motion signature" in item for item in failures), failures
                )

    def test_signature_that_names_a_mechanism_passes(self) -> None:
        self.assertEqual([], self.run_with(
            signature="motion: Content holds in the center of the screen while the next thing travels into it and settles against the frame."
        ))

    def test_selected_set_may_be_static_when_static_evidence_is_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = []
            for rank in range(1, 7):
                host = f"reference-{rank}.example.test"
                still = rank <= 4
                cell = project.observation_cell(
                    f"strong-{rank}", url=f"https://{host}/entry",
                    kind="static" if still else "motion", motion=not still,
                )
                rows.append(project.strong_row(
                    rank, source=DEFAULT_SOURCES[rank - 1], observation=cell,
                    signature=(
                        "static: A full-width typographic composition aligns one display "
                        "line against the image grid and preserves the negative-space hierarchy."
                        if still else
                        "motion: A pinned composition holds the heading while the image "
                        "rail travels across it and settles into the next route state."
                    ),
                ))
            blocks = [project.static_sequence_block(rank) for rank in range(1, 5)]
            transfer_signatures = {
                rank: (
                    "static: A full-width typographic composition aligns one display "
                    "line against the image grid and preserves the negative-space hierarchy."
                )
                for rank in range(1, 5)
            }
            failures = project.failures(project.body(
                strong_rows=rows,
                sequence_blocks=blocks,
                transfer_signatures=transfer_signatures,
            ))
        self.assertEqual([], failures)

    def test_component_table_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            body = project.body().split("## Component sources", 1)[0]
            failures = project.failures(body)
        self.assertTrue(any("Component sources" in item for item in failures), failures)

    def test_every_shipping_component_needs_a_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = [
                f"| navigation | 1 | {SHEET_FRAME_CELL} | {STRUCTURE_CELL} | 16px, weight "
                "400, sentence case, hover border .45s | rail |",
            ]
            failures = project.failures(project.body(component_rows=rows))
        self.assertTrue(any("must cover" in item and "buttons" in item for item in failures), failures)

    def test_component_from_an_unselected_rank_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = [
                f"| {name} | 6 | strong-6-frames/strong-6-001-rest.png | "
                f"{STRUCTURE_CELL} | {VALUES_CELL} | route |"
                for name in REQUIRED_COMPONENTS
            ]
            failures = project.failures(project.body(component_rows=rows))
        self.assertTrue(any("selected reference rank" in item for item in failures), failures)

    def test_paraphrased_values_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = [
                f"| {name} | 1 | {frame_for(name)} | {STRUCTURE_CELL} | big type | route |"
                for name in REQUIRED_COMPONENTS
            ]
            failures = project.failures(project.body(component_rows=rows))
        self.assertTrue(any("recorded values" in item for item in failures), failures)

    def test_owner_approved_own_design_is_rejected_even_with_quoted_words(self) -> None:
        # 10.0.0: the owner's standing order removed the owner-approved path.
        # The producer's own footer does not ship, with or without words.
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = [
                f"| {name} | 1 | {frame_for(name)} | {STRUCTURE_CELL} | {VALUES_CELL} | route |"
                for name in REQUIRED_COMPONENTS if name != "footer"
            ] + [
                "| footer | owner-approved: \"do the footer your own way, keep it plain\" "
                "| owner-approved | three columns stacked against the bottom edge | "
                "owner's words above; three columns, 16px, no rules | every route |",
            ]
            failures = project.failures(project.body(component_rows=rows))
        self.assertTrue(any("producer's own design" in item for item in failures), failures)
        self.assertTrue(any("standing order" in item for item in failures), failures)

    def test_owner_approval_without_words_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = [
                f"| {name} | owner-approved: yes | owner-approved | {STRUCTURE_CELL} "
                "| some values reproduced here for the row | route |"
                for name in REQUIRED_COMPONENTS
                if name not in ("display typeface", "text typeface")
            ]
            failures = project.failures(project.body(component_rows=rows))
        self.assertTrue(any("producer's own design" in item for item in failures), failures)

    def test_the_legacy_header_still_parses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = [
                f"| {name} | 1 | {frame_for(name)} | {STRUCTURE_CELL} | {VALUES_CELL} | route |"
                for name in REQUIRED_COMPONENTS
            ]
            body = project.body(component_rows=rows).replace(COMPONENT_HEADER, COMPONENT_HEADER_LEGACY, 1)
            failures = project.failures(body)
        self.assertEqual([], [i for i in failures if "Component sources table" in i], failures)


class MechanismDiffTests(unittest.TestCase):
    """The finished build is read by the same harness as its references."""

    def diff(self, temporary: str, payload: dict) -> tuple[Path, Path, str]:
        project = Path(temporary)
        state = project / ".design-dna"
        (state / "evidence").mkdir(parents=True)
        record = state / "visual-review.md"
        record.write_text("placeholder\n", encoding="utf-8")
        artifact = state / "evidence" / "mechanism-diff.json"
        artifact.write_text(json.dumps(payload), encoding="utf-8")
        cell = f".design-dna/evidence/mechanism-diff.json plus sha256:{sha256_of(artifact)}"
        return project, record, f"- Mechanism diff: {cell}\n"

    def test_passing_diff_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project, record, section = self.diff(temporary, runtime_evidence(
                "compare_mechanisms.mjs", pass_=True, verdict="carried",
            ))
            # `pass` cannot be a Python keyword in the helper call.
            payload = json.loads((project / ".design-dna/evidence/mechanism-diff.json").read_text(encoding="utf-8"))
            payload["pass"] = payload.pop("pass_")
            artifact = project / ".design-dna/evidence/mechanism-diff.json"
            artifact.write_text(json.dumps(payload), encoding="utf-8")
            section = f"- Mechanism diff: .design-dna/evidence/mechanism-diff.json plus sha256:{sha256_of(artifact)}\n"
            failures = INITIALIZER.mechanism_diff_failures(
                section, project=project, record_path=record
            )
        self.assertEqual([], failures)

    def test_skeleton_build_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload = runtime_evidence(
                "compare_mechanisms.mjs",
                verdict="the references carry scroll choreography and the build carries none",
            )
            payload["pass"] = False
            project, record, section = self.diff(temporary, payload)
            failures = INITIALIZER.mechanism_diff_failures(
                section, project=project, record_path=record
            )
        self.assertTrue(
            any(
                "compare_mechanisms.mjs" in item and "did not pass" in item
                for item in failures
            ),
            failures,
        )

    def test_hand_written_diff_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project, record, section = self.diff(temporary, {"tool": "mine", "pass": True})
            failures = INITIALIZER.mechanism_diff_failures(
                section, project=project, record_path=record
            )
        self.assertTrue(any("compare_mechanisms.mjs" in item for item in failures), failures)

    def test_missing_binding_is_rejected(self) -> None:
        failures = INITIALIZER.mechanism_diff_failures(
            "- Mechanism diff: __REPLACE_WITH_THE_DIFF__\n",
            project=Path("."), record_path=Path("visual-review.md"),
        )
        self.assertTrue(any("must bind" in item for item in failures), failures)

class StructureGateTests(unittest.TestCase):
    """6.8.0. The build that researched six sites and shipped one button."""

    def rows_with_first(self, project, **first):
        rows = []
        for rank in range(1, 7):
            host = f"reference-{rank}.example.test"
            kwargs = dict(first) if rank == 1 else {}
            cell = project.observation_cell(
                f"strong-{rank}", url=f"https://{host}/entry", **kwargs
            )
            rows.append(project.strong_row(
                rank, source=DEFAULT_SOURCES[rank - 1], observation=cell
            ))
        return rows

    def test_observation_without_first_screen_structure_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            failures = project.failures(project.body(
                strong_rows=self.rows_with_first(project, structure=False)))
        self.assertTrue(
            any("first-screen structure" in i for i in failures), failures
        )

    def test_a_property_in_the_structure_column_is_rejected(self) -> None:
        # exactly what the failing build recorded: sizes, not arrangement
        for propertyish in (
            "48px display at 1.0 line height",
            "13px weight 700 at 3px tracking",
            "115 by 115, radius 100, 1px border",
        ):
            with self.subTest(cell=propertyish):
                with tempfile.TemporaryDirectory() as temporary:
                    project = DossierProject(temporary)
                    rows = [
                        f"| {name} | 1 | {frame_for(name)} | {propertyish} | {VALUES_CELL} | route |"
                        for name in REQUIRED_COMPONENTS
                    ]
                    failures = project.failures(project.body(component_rows=rows))
                self.assertTrue(
                    any("how the part is arranged" in i for i in failures), failures
                )

    def test_layout_and_first_screen_now_need_a_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = [
                f"| {name} | 1 | {frame_for(name)} | {STRUCTURE_CELL} | {VALUES_CELL} | route |"
                for name in REQUIRED_COMPONENTS
                if name not in ("first screen", "layout grid")
            ]
            failures = project.failures(project.body(component_rows=rows))
        joined = " ".join(failures)
        self.assertIn("first screen", joined)
        self.assertIn("layout grid", joined)

    def test_a_typeface_chosen_by_the_producer_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = []
            for name in REQUIRED_COMPONENTS:
                if name in ("display typeface", "text typeface"):
                    rows.append(
                        f'| {name} | owner-approved: "use whatever looks good" | '
                        f"owner-approved | {STRUCTURE_CELL} | {VALUES_CELL} | every route |"
                    )
                else:
                    rows.append(
                        f"| {name} | 1 | {frame_for(name)} | {STRUCTURE_CELL} | "
                        f"{VALUES_CELL} | route |")
            failures = project.failures(project.body(component_rows=rows))
        self.assertTrue(
            any("producer's own design" in i for i in failures), failures
        )


class StructureDiffTests(unittest.TestCase):
    """The finished first screen is compared to the reference it names."""

    def bind(self, temporary, payload):
        project = Path(temporary)
        state = project / ".design-dna"
        (state / "evidence").mkdir(parents=True)
        record = state / "visual-review.md"
        record.write_text("placeholder\n", encoding="utf-8")
        artifact = state / "evidence" / "structure-diff.json"
        artifact.write_text(json.dumps(payload), encoding="utf-8")
        cell = (".design-dna/evidence/structure-diff.json plus sha256:"
                + sha256_of(artifact))
        return project, record, f"- Structure diff: {cell}\n"

    def test_resembling_build_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload = runtime_evidence(
                "compare_structure.mjs", census_sha256="b" * 64,
                routes_compared=2,
                verdict="All 2 route(s) are built like a reference page.",
            )
            payload["pass"] = True
            project, record, section = self.bind(temporary, payload)
            self.assertEqual([], INITIALIZER.structure_diff_failures(
                section, project=project, record_path=record))

    def test_own_layout_with_borrowed_sizes_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload = runtime_evidence(
                "compare_structure.mjs", census_sha256="b" * 64,
                routes_compared=2,
                verdict=("the largest thing on the first screen is text "
                         "(<h1>), the reference's is media (<img>)"),
            )
            payload["pass"] = False
            project, record, section = self.bind(temporary, payload)
            failures = INITIALIZER.structure_diff_failures(
                section, project=project, record_path=record)
        self.assertTrue(
            any(
                "compare_structure.mjs" in item and "did not pass" in item
                for item in failures
            ),
            failures,
        )

    def test_hand_written_diff_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project, record, section = self.bind(temporary, {"tool": "by-hand", "pass": True})
            failures = INITIALIZER.structure_diff_failures(
                section, project=project, record_path=record)
        self.assertTrue(any("compare_structure.mjs" in i for i in failures), failures)

    def test_unbound_diff_is_rejected(self) -> None:
        failures = INITIALIZER.structure_diff_failures(
            "- Structure diff: __REPLACE_WITH_THE_DIFF__\n",
            project=Path("."), record_path=Path("visual-review.md"))
        self.assertTrue(any("must bind" in i for i in failures), failures)

class SourceLineEvidenceTests(unittest.TestCase):
    """6.9.0. The build that cited a footer it had never opened."""

    def rows(self, frame=FRAME_CELL, source="1"):
        return [
            f"| {name} | {source} | {frame_for(name) if frame == FRAME_CELL else frame} | {STRUCTURE_CELL} | {VALUES_CELL} | route |"
            for name in REQUIRED_COMPONENTS
        ]

    def test_a_frame_that_does_not_exist_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = self.rows(frame="strong-1-frames/strong-1-999-footer.png")
            failures = project.failures(project.body(component_rows=rows))
        self.assertTrue(any("does not exist" in i for i in failures), failures)

    def test_a_frame_belonging_to_another_reference_is_rejected(self) -> None:
        # the row cites reference 1 and shows a frame of reference 3
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = self.rows(frame="strong-3-frames/strong-3-001-rest.png", source="1")
            failures = project.failures(project.body(component_rows=rows))
        self.assertTrue(
            any("does not belong to the reference" in i for i in failures), failures
        )

    def test_an_empty_frame_column_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = [
                f"| {name} | 1 |  | {STRUCTURE_CELL} | {VALUES_CELL} | route |"
                for name in REQUIRED_COMPONENTS
            ]
            failures = project.failures(project.body(component_rows=rows))
        self.assertTrue(any("incomplete" in i or "SHOWS" in i for i in failures), failures)

    def test_an_owner_approved_row_with_a_frame_is_still_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = [
                f"| {name} | 1 | {frame_for(name)} | {STRUCTURE_CELL} | {VALUES_CELL} | route |"
                for name in REQUIRED_COMPONENTS if name != "footer"
            ] + [
                '| footer | owner-approved: "do the footer plain, your call" | '
                f"{FRAME_CELL} | three columns at the bottom edge | 16px, no rules "
                "| every route |"
            ]
            failures = project.failures(project.body(component_rows=rows))
        self.assertTrue(any("producer's own design" in i for i in failures), failures)

    def test_a_sourced_row_with_a_real_frame_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            failures = project.failures(project.body(component_rows=self.rows()))
        self.assertEqual([], [i for i in failures if "frame" in i.casefold()], failures)


class ComponentCensusTests(unittest.TestCase):
    """The twelve required rows were a floor, and the build shipped twenty-five."""

    def test_a_component_the_build_renders_with_no_row_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            # exactly what the failing build rendered and never listed
            census = project.census_cell(
                list(REQUIRED_COMPONENTS) + ["lede", "plate", "steps", "ask", "form"]
            )
            failures = project.failures(project.body(census=census))
        joined = " ".join(failures)
        self.assertIn("no source row", joined)
        for invented in ("lede", "plate", "steps", "ask", "form"):
            self.assertIn(invented, joined)

    def test_an_unsourced_public_brand_mark_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            census = project.census_cell(list(REQUIRED_COMPONENTS) + ["class:brand-mark"])
            failures = project.failures(project.body(census=census))
        joined = " ".join(failures)
        self.assertIn("no source row", joined)
        self.assertIn("class:brand-mark", joined)

    def test_a_row_naming_the_component_satisfies_the_census(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            census = project.census_cell(list(REQUIRED_COMPONENTS) + ["lede"])
            rows = [
                f"| {name} | 1 | {frame_for(name)} | {STRUCTURE_CELL} | {VALUES_CELL} | route |"
                for name in REQUIRED_COMPONENTS
            ] + [
                f"| lede | 1 | {FRAME_CELL} | a statement block at one third down "
                f"the screen beside a hairline rule | {VALUES_CELL} | inner routes |"
            ]
            failures = project.failures(
                project.body(component_rows=rows, census=census))
        self.assertEqual(
            [], [i for i in failures if "no source row" in i], failures
        )

    def test_an_unbound_census_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            failures = project.failures(
                project.body(census="__REPLACE_WITH_THE_CENSUS__"))
        self.assertTrue(any("scan_build_components.mjs" in i for i in failures), failures)


class InnerPageObservationTests(unittest.TestCase):
    """A producer holding only home-page captures invents every inner page."""

    def home_only_rows(self, project):
        rows = []
        for rank in range(1, 7):
            cell = project.observation_cell(
                f"strong-{rank}",
                url=f"https://reference-{rank}.example.test/",
                inner=False,
            )
            rows.append(project.strong_row(
                rank, source=DEFAULT_SOURCES[rank - 1], observation=cell,
            ))
        return rows

    def test_home_pages_only_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            failures = project.failures(project.body(
                strong_rows=self.home_only_rows(project)))
        self.assertTrue(any("INNER pages" in i for i in failures), failures)

    def test_observing_inner_pages_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            failures = project.failures(project.body())
        self.assertEqual([], [i for i in failures if "INNER pages" in i], failures)


class StructureDiffRouteCoverageTests(unittest.TestCase):
    """The diff's routes come from the census, not from the producer."""

    def bind(self, temporary, payload):
        project = Path(temporary)
        state = project / ".design-dna"
        (state / "evidence").mkdir(parents=True)
        record = state / "visual-review.md"
        record.write_text("placeholder\n", encoding="utf-8")
        artifact = state / "evidence" / "structure-diff.json"
        artifact.write_text(json.dumps(payload), encoding="utf-8")
        cell = (".design-dna/evidence/structure-diff.json plus sha256:"
                + sha256_of(artifact))
        return project, record, f"- Structure diff: {cell}\n"

    def test_a_diff_whose_routes_the_producer_chose_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload = runtime_evidence(
                "compare_structure.mjs", routes_compared=1,
                census_sha256=None,
                verdict="All 1 route(s) are built like a reference page.",
            )
            payload["pass"] = True
            project, record, section = self.bind(temporary, payload)
            failures = INITIALIZER.structure_diff_failures(
                section, project=project, record_path=record)
        self.assertTrue(any("component census" in i for i in failures), failures)

    def test_a_census_driven_diff_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload = runtime_evidence(
                "compare_structure.mjs", routes_compared=3,
                census_sha256="a" * 64,
                verdict="All 3 route(s) are built like a reference page.",
            )
            payload["pass"] = True
            project, record, section = self.bind(temporary, payload)
            self.assertEqual([], INITIALIZER.structure_diff_failures(
                section, project=project, record_path=record))

class MeasuredValueTests(unittest.TestCase):
    """7.0.0. Never build off a screenshot."""

    def rows_with_values(self, values):
        return [
            f"| {name} | 1 | {frame_for(name)} | {STRUCTURE_CELL} | {values} | route |"
            for name in REQUIRED_COMPONENTS
        ]

    def test_a_value_the_reference_does_not_compute_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            invented = "held for 7777px, radius 4321, transition 8888ms, tracking 6.66em"
            failures = project.failures(
                project.body(component_rows=self.rows_with_values(invented)))
        self.assertTrue(
            any("does not compute" in i for i in failures), failures
        )

    def test_values_read_off_the_live_page_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            real = "held 2400px, 450ms, 36px display at leading 1.25, radius 999"
            failures = project.failures(
                project.body(component_rows=self.rows_with_values(real)))
        self.assertEqual(
            [], [i for i in failures if "does not compute" in i], failures
        )

    def test_a_row_carrying_no_numbers_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            prose = "a generous serif at a comfortable size with a soft easing"
            failures = project.failures(
                project.body(component_rows=self.rows_with_values(prose)))
        self.assertTrue(
            any("paraphrase of a picture" in i for i in failures), failures
        )

    def test_styles_read_off_a_picture_instead_of_the_page_are_rejected(self) -> None:
        # the honest description of what the rejected build actually did
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = [
                project.strong_row(
                    rank, source=DEFAULT_SOURCES[rank - 1],
                    styles="measured by eye from the capture at 1440 by 900")
                for rank in range(1, 7)
            ]
            failures = project.failures(project.body(strong_rows=rows))
        self.assertTrue(
            any("plus sha256" in i for i in failures),
            failures,
        )

    def test_a_hand_written_style_record_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rows = [
                project.strong_row(
                    rank, source=DEFAULT_SOURCES[rank - 1],
                    styles=project.styles_cell(f"strong-{rank}", tool="by-hand"))
                for rank in range(1, 7)
            ]
            failures = project.failures(project.body(strong_rows=rows))
        self.assertTrue(
            any("Evidence tool must be extract_reference_styles.mjs" in i for i in failures),
            failures,
        )


class CuratedSourceTests(unittest.TestCase):
    """7.0.0. Never take the lazy pool."""

    def test_a_submission_feed_cannot_supply_a_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            sources = list(DEFAULT_SOURCES)
            sources[5] = "httpster; it was on the photographic tag"
            rows = [
                project.strong_row(rank, source=sources[rank - 1])
                for rank in range(1, 7)
            ]
            failures = project.failures(project.body(strong_rows=rows))
        self.assertTrue(
            any("open submission feed" in i for i in failures), failures
        )

    def test_a_reference_without_an_accolade_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            sources = list(DEFAULT_SOURCES)
            sources[0] = "awwwards"
            rows = [
                project.strong_row(rank, source=sources[rank - 1])
                for rank in range(1, 7)
            ]
            failures = project.failures(project.body(strong_rows=rows))
        self.assertTrue(
            any("what this site won" in i for i in failures), failures
        )


class CombinationTests(unittest.TestCase):
    """7.0.0. Never add your own design."""

    def test_an_invented_decision_is_rejected(self) -> None:
        # the exact shape of the sentence the producer wrote about its own idea
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            failures = project.failures(project.body(combination=(
                "The first screen gives half its width to the upkeep instead of "
                "the building, which none of them attempt; it is our own "
                "decision and the strongest thing here."
            )))
        self.assertTrue(
            any("something the producer invented" in i for i in failures), failures
        )

    def test_a_combination_naming_two_references_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            failures = project.failures(project.body())
        self.assertEqual(
            [], [i for i in failures if "Combination of references" in i], failures
        )

    def test_a_combination_naming_no_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            failures = project.failures(project.body(combination=(
                "The build combines a held screen, a staggered index and a "
                "control set into one coherent whole across four routes."
            )))
        self.assertTrue(
            any("must name at least two selected references" in i for i in failures),
            failures,
        )


class SignatureTransferTests(unittest.TestCase):
    """7.1.0. Which PART of the reference arrived.

    Six references were researched, watched, measured and cited for one build,
    every gate passed, and two of them reached the page as a background colour
    and a set of control dimensions. The owner: "you still took the crack in
    the sidewalk instead of the waterfall." Nothing in the record asked which
    part arrived, so nothing refused the smallest possible answer.
    """

    def rows(self, project, **overrides):
        proof = overrides.pop("proof", None) or project.proof_cell()
        signature = overrides.pop("signature", TRANSFER_SIGNATURE)
        carrier_override = overrides.pop("carrier", None)
        loss_override = overrides.pop("loss", None)
        ranks = overrides.pop("ranks", [1, 2, 3, 4])
        carriers = {
            1: "first screen",
            2: "layout grid",
            3: "display typeface",
            4: "color behavior",
        }
        return [
            f"| {rank} | {signature} | "
            f"{carrier_override or ('the ' + carriers.get(rank, 'first screen') + ' on the primary route')} "
            f"| {proof} | "
            f"{loss_override or ('the ' + carriers.get(rank, 'first screen') + ' would lose its pinned travelling arrangement and route hierarchy')} |"
            for rank in ranks
        ]

    def test_a_missing_transfer_table_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            body = project.body().replace("## Signature transfer", "## Notes")
            failures = project.failures(body)
        self.assertTrue(
            any("Signature transfer needs a table" in item for item in failures),
            failures,
        )

    def test_a_rewritten_signature_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            failures = project.failures(project.body(transfer_rows=self.rows(
                project,
                signature=(
                    "The controls fill with their own colour when the pointer "
                    "crosses them, which is a real thing it does."
                ),
            )))
        self.assertTrue(
            any("is not the one strong row" in item for item in failures),
            failures,
        )

    def test_a_summary_of_the_signature_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            failures = project.failures(project.body(transfer_rows=self.rows(
                project, signature="It slides.",
            )))
        self.assertTrue(
            any("characters of the" in item for item in failures), failures
        )

    def test_a_loss_that_is_only_a_surface_property_is_rejected(self) -> None:
        """The exact cell the failed build would have written."""
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            failures = project.failures(project.body(transfer_rows=self.rows(
                project,
                loss=(
                    "the first screen would lose its warm ground, its 12px "
                    "corners and the 130 by 40 control size"
                ),
            )))
        self.assertTrue(
            any("surface property" in item for item in failures), failures
        )

    def test_a_loss_naming_no_shipped_component_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            failures = project.failures(project.body(transfer_rows=self.rows(
                project,
                loss="something would travel differently and the page would settle less well",
            )))
        self.assertTrue(
            any("would be GONE" in item for item in failures), failures
        )

    def test_a_carrier_naming_no_shipped_component_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            failures = project.failures(project.body(transfer_rows=self.rows(
                project, carrier="somewhere near the top of the page",
            )))
        self.assertTrue(
            any("part that carries this signature" in item for item in failures),
            failures,
        )

    def test_a_selected_rank_with_no_row_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            failures = project.failures(project.body(
                transfer_rows=self.rows(project, ranks=[1, 2, 3])
            ))
        self.assertTrue(
            any("no row for selected rank" in item for item in failures), failures
        )

    def test_an_unbound_proof_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            failures = project.failures(project.body(transfer_rows=self.rows(
                project, proof="we checked it and it is there",
            )))
        self.assertTrue(
            any("recorded proof" in item for item in failures), failures
        )

    def test_a_complete_transfer_table_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            self.assertEqual([], project.failures(
                project.body(transfer_rows=self.rows(project))
            ))





class SequenceReadTests(unittest.TestCase):
    """9.0.0: the watching is enforced by count."""

    def test_default_body_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            self.assertEqual(project.failures(project.body()), [])

    def test_missing_section_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            body = project.body().replace("## Sequence reads", "## Notes")
            failures = project.failures(body)
        self.assertTrue(any("Sequence reads is missing" in f for f in failures), failures)

    def test_a_sheet_without_a_line_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, omit=(7, 19))] + [
                project.sequence_block(rank) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("no line for wide/e0007, wide/e0019" in f for f in failures), failures)

    def test_a_line_that_says_nothing_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, short=(3,))] + [
                project.sequence_block(rank) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("under 40 characters" in f and "wide/e0003" in f for f in failures), failures)

    def test_a_read_that_calls_everything_static_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, static_all=True)] + [
                project.sequence_block(rank) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("events static" in f for f in failures), failures)

    def test_a_thin_inventory_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, inventory_rows=3)] + [
                project.sequence_block(rank) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("Behaviour inventory" in f and "it has 3" in f for f in failures), failures)

    def test_a_signature_not_located_on_a_sheet_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, signature_events="none")] + [
                project.sequence_block(rank) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("Signature events" in f for f in failures), failures)

    def test_a_short_recording_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, events=5)] + [
                project.sequence_block(rank) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("has 10 events" in f for f in failures), failures)

    def test_a_thirty_second_low_fps_shortcut_cannot_qualify(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, duration=30, fps=6)] + [
                project.sequence_block(rank) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("minimum duration" in f and "90-second" in f for f in failures), failures)
        self.assertTrue(any("sampling rate" in f and "15-FPS" in f for f in failures), failures)

    def test_a_hand_made_recording_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, tool="by-hand")] + [
                project.sequence_block(rank) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("Evidence tool must be record_reference.mjs" in f for f in failures), failures)

    def test_an_event_recording_passes(self):
        """9.1.0: the recorder keeps the moments the screen changed; a line per event."""
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(rank, schema=4) for rank in (1, 2, 3, 4)]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertEqual(failures, [])

    def test_an_event_without_a_line_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, schema=4, omit=(3,))] + [
                project.sequence_block(rank, schema=4) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("no line for wide/e0003" in f and "Every event gets a line" in f for f in failures), failures)

    def test_a_recording_with_too_few_events_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, schema=4, events=5)] + [
                project.sequence_block(rank, schema=4) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("has 10 events" in f for f in failures), failures)

    def test_a_signature_not_located_on_an_event_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, schema=4, signature_events="none")] + [
                project.sequence_block(rank, schema=4) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("Signature events" in f for f in failures), failures)

    def test_a_behaviour_component_citing_an_event_sheet_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            write_png(project.project / ".design-dna" / "references" / EVENT_FRAME_CELL)
            carrier_rank = {
                "first screen": 1,
                "layout grid": 2,
                "display typeface": 3,
                "color behavior": 4,
            }
            rows = [
                f"| {name} | {carrier_rank.get(name, 1)} | "
                f"{EVENT_FRAME_CELL if name in BEHAVIOUR_COMPONENTS else f'strong-{carrier_rank.get(name, 1)}-frames/strong-{carrier_rank.get(name, 1)}-001-rest.png'} "
                f"| {STRUCTURE_CELL} | {VALUES_CELL} | the primary route |"
                for name in REQUIRED_COMPONENTS
            ]
            failures = project.failures(project.body(component_rows=rows))
        self.assertEqual(failures, [])

    def test_a_behaviour_component_citing_a_rest_frame_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            rest = FRAME_CELL  # deliberately the still, for every row
            rows = [
                f"| {name} | 1 | {rest} | {STRUCTURE_CELL} | {VALUES_CELL} "
                "| the primary route |"
                for name in REQUIRED_COMPONENTS
            ]
            failures = project.failures(project.body(component_rows=rows))
        self.assertTrue(
            any("'hover behavior' must cite a recording sheet" in f for f in failures), failures
        )


class RuntimeContractAdversarialTests(unittest.TestCase):
    def test_selection_and_interaction_rows_cannot_be_retrofit_or_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            body = fixture.body()
            body = body.replace(
                "filter=content model, visitor task, route states, responsive behavior, "
                "brand authority, and material evidence for the exact brief",
                "filter=modern ecommerce",
                1,
            ).replace(
                "composition=pass; typography=pass",
                "composition=fail; typography=pass",
                1,
            )
            lines = body.splitlines()
            block = next(
                index
                for index, line in enumerate(lines)
                if line.strip().casefold() == "### strong-1 interaction census"
            )
            omitted = next(
                index
                for index in range(block, len(lines))
                if lines[index].startswith("| target_id=")
            )
            del lines[omitted]
            failures = fixture.failures("\n".join(lines))
        joined = "\n".join(failures)
        self.assertIn("category/tag or quota", joined)
        self.assertIn("cannot be selected unless both independent gates pass", joined)
        self.assertIn("table omits or adds generated target/page/input rows", joined)


if __name__ == "__main__":
    unittest.main()
