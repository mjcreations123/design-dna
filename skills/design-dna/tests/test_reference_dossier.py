#!/usr/bin/env python3
"""Regression coverage for public-reference direction records.

The dossier is research evidence, so every row must bind a capture the
producer actually looked at. These tests hold that line: a dossier of
plausible names with no captures is rejected, the count is a floor tied to
source spread rather than a quota, and the synthesis must go beyond its set.
"""

from __future__ import annotations

import importlib.util
import json
import struct
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

STRONG_HEADER = (
    "| Rank | Reference title or visible entry | Public URL or gallery-entry URL "
    "| Discovery source and accolade | Retrieval date | Access status | Capture path and SHA-256 "
    "| Observed evidence | Measured styles | Signature (what a stranger would name) "
    "| Brief relevance | Design to copy | Rights boundary |"
)
STRONG_SEPARATOR = (
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
)
NEGATIVE_HEADER = (
    "| Reference title or visible entry | Public URL or gallery-entry URL "
    "| Discovery source | Retrieval date | Access status | Capture path and SHA-256 "
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
# a verbatim slice of the fixture signature, long enough to clear the floor
TRANSFER_SIGNATURE = (
    "The product images slide sideways under a pinned heading as the "
    "page is scrolled"
)
TRANSFER_LOSS = (
    "the first screen would stop holding its heading while the product rail "
    "travels through it, and that arrangement would go with it"
)
FRAME_CELL = "strong-1-frames/strong-1-001-rest.png"
# a rest frame cannot show a first screen arriving, a nav responding, a button
# under the pointer, a scroll or a hover; those rows cite a recording sheet
SHEET_FRAME_CELL = "strong-1-sheets/s004.png"
EVENT_FRAME_CELL = "strong-1-events/e004-hover-work.png"
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


def write_png(path: Path, width: int = 8, height: int = 8) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = b"\x00" + (b"\x22\x66\xaa" * width)
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

    def styles_cell(self, name: str, *, numbers=None, tool: str = "extract_reference_styles.mjs") -> str:
        """A machine extraction of the reference's live CSS."""
        path = self.captures / f"{name}-styles.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "tool": tool,
            "schema_version": 1,
            "id": name,
            "url": f"https://{name}.example.test/",
            "numbers": MEASURED_NUMBERS if numbers is None else numbers,
            "type": [], "controls": [], "transitions": [], "colors": [],
        }), encoding="utf-8")
        return (f".design-dna/references/{name}-styles.json plus sha256:"
                + sha256_of(path))

    def census_cell(self, names: list[str] | None = None) -> str:
        """A scan_build_components.mjs record naming what the build renders."""
        if names is None:
            names = list(REQUIRED_COMPONENTS)
        path = self.state / "evidence" / "component-census.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "tool": "scan_build_components.mjs",
            "schema_version": 1,
            "routes": [{"url": "http://127.0.0.1:4960/", "components": []}],
            "names": sorted(names),
            "census": [{"name": n, "count": 1, "area": 0.1} for n in sorted(names)],
        }), encoding="utf-8")
        return (".design-dna/evidence/component-census.json plus sha256:"
                + sha256_of(path))

    def proof_cell(self) -> str:
        """A check_signature_transfer.mjs record for the transfer rows to bind."""
        path = self.state / "evidence" / "signature-transfer.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "tool": "check_signature_transfer.mjs",
            "schema_version": 1,
            "pass": True,
            "verdicts": [],
        }), encoding="utf-8")
        return (".design-dna/evidence/signature-transfer.json plus sha256:"
                + sha256_of(path))

    def capture_cell(self, name: str) -> str:
        path = self.captures / f"{name}.png"
        if not path.is_file():
            write_png(path)
        return f".design-dna/references/{name}.png plus sha256:{sha256_of(path)}"

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
        schema: int = 3,
        structure: bool = True,
        distinct: int | None = None,
        coverage: float | None = None,
        sheet: bool = True,
    ) -> str:
        path = self.captures / f"{name}-observation.json"
        path.parent.mkdir(parents=True, exist_ok=True)
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
        payload = {
            "schema_version": schema,
            "tool": tool,
            "id": name,
            "url": url,
            "observed_at": "2026-09-02T00:00:00Z",
            "coverage": {"rest": True, "scroll_holds": holds, "hovers": hovers, "transition": True},
            "motion": {
                "observed": motion,
                "at_rest": False,
                "on_scroll_holds": holds if motion else 0,
                "on_hover": hovers if motion else 0,
                "on_transition": motion,
            },
        }
        if structure:
            payload["first_screen"] = {
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
        if sheet:
            payload["mechanisms"] = mechanisms
            payload["score"] = {
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
                "scroller": "document",
            }
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
        duration: float = 62.0,
        tool: str = "record_reference.mjs",
        omit: tuple[int, ...] = (),
        short: tuple[int, ...] = (),
        static_all: bool = False,
        inventory_rows: int = 8,
        signature_sheets: str = "s004, s005",
        schema: int = 1,
        events: int = 24,
        signature_events: str = "e004, e005",
    ) -> str:
        """Write a recording record, its sheets or events, and a sequence read."""
        name = f"strong-{rank}"
        if schema == 2:
            return self._event_block(
                rank, events=events, duration=duration, tool=tool, omit=omit,
                short=short, static_all=static_all, inventory_rows=inventory_rows,
                signature_events=signature_events,
            )
        # the validator counts sheets against the read; it does not open every
        # sheet, and writing 96 PNGs per body() made the suite take ten minutes
        recording = {
            "tool": tool,
            "schema_version": 1,
            "id": name,
            "url": f"https://reference-{rank}.example.test/entry",
            "duration_s": duration,
            "fps": 10,
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
    ) -> str:
        """9.1.0: a schema-2 recording counts events, and the read has a line per event."""
        name = f"strong-{rank}"
        kinds = ("load", "hover", "scroll", "travel", "click", "spontaneous")
        recording = {
            "tool": tool,
            "schema_version": 2,
            "id": name,
            "url": f"https://reference-{rank}.example.test/entry",
            "duration_s": duration,
            "fps": 10,
            "frames": int(duration * 10),
            "frames_dir": f"{name}-frames",
            "events": events,
            "event_files": [
                {
                    "id": f"e{n:03d}",
                    "file": f"{name}-events/e{n:03d}-{kinds[n % len(kinds)]}.png",
                    "kind": kinds[n % len(kinds)],
                    "t": round(n * 2.1, 1),
                    "magnitude_pct": 4.2,
                    "region": "a large area at top left (31% of pixels)",
                    "settle_s": 0.6,
                }
                for n in range(1, events + 1)
            ],
            "quiet": [],
            "video": {"file": f"{name}-recording.webm", "sha256": "0" * 64},
            "pages_visited": [f"https://reference-{rank}.example.test/entry"],
            "cursor_path": [],
        }
        recording_path = self.project / ".design-dna" / "references" / f"{name}-recording.json"
        recording_path.write_text(json.dumps(recording, indent=1), encoding="utf-8")
        lines = []
        for n in range(1, events + 1):
            if n in omit:
                continue
            if n in short:
                lines.append(f"- e{n:03d} (x): idle.")
            elif static_all:
                lines.append(f"- e{n:03d} ({n * 2.1:.1f}s, hover): static, nothing changes, the cursor is still.")
            else:
                lines.append(f"- e{n:03d} ({n * 2.1:.1f}s, hover): {SEQUENCE_LINE}.")
        inventory = [
            "## Behaviour inventory",
            "",
            "| # | Trigger | Element | Effect | Magnitude | Events |",
            "| --- | --- | --- | --- | --- | --- |",
            *[f"| {i} " + INVENTORY_ROW.replace("s004, s005", "e004, e005") for i in range(1, inventory_rows + 1)],
        ]
        read_path = self.project / ".design-dna" / "references" / f"{name}-sequence-read.md"
        read_path.write_text(
            "\n".join([f"# Sequence read: {name}", "", "## Events", "", *lines, "", *inventory, ""]),
            encoding="utf-8",
        )
        return "\n".join((
            f"### {name}",
            f"- Recording: .design-dna/references/{name}-recording.json plus sha256:{sha256_of(recording_path)}",
            f"- Read: .design-dna/references/{name}-sequence-read.md plus sha256:{sha256_of(read_path)}",
            f"- Signature events: {signature_events}",
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
        observation: str | None = None,
        signature: str = (
            "The product images slide sideways under a pinned heading as the "
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
            f"2026-09-01 | {access} | {capture or self.capture_cell(f'strong-{rank}')} | "
            f"{observed} | "
            f"{styles or self.styles_cell(f'strong-{rank}')} | "
            f"{signature} | "
            "Supports the visitor decision and category story for this exact "
            "project. | A clear hierarchy, media relationship, and direct entry "
            "condition. | Do not reproduce its brand assets, writing, source code, "
            "or full page. |"
        )

    def negative_row(self, index: int, *, source: str = "httpster") -> str:
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
        strong_rows: list[str] | None = None,
        negative_rows: list[str] | None = None,
        selected: str = "1, 2, 3, 4",
        synthesis_rows: list[str] | None = None,
        ledger_check: str = "none",
        elevation: str = (
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
    ) -> str:
        claimed = transfer_signatures or {}
        selected_list = [
            int(part.strip()) for part in selected.split(",") if part.strip().isdigit()
        ]
        if sequence_blocks is None:
            sequence_blocks = [self.sequence_block(rank) for rank in selected_list]
        if transfer_rows is None:
            proof = self.proof_cell()
            transfer_rows = [
                f"| {rank} | {claimed.get(rank, TRANSFER_SIGNATURE)} | the first "
                f"screen on the primary route | {proof} | {TRANSFER_LOSS} |"
                for rank in [
                    int(part.strip()) for part in selected.split(",")
                    if part.strip().isdigit()
                ]
            ]
        # the sheet the behaviour rows cite has to exist for every body
        write_png(self.project / ".design-dna" / "references" / SHEET_FRAME_CELL)
        if component_rows is None:
            component_rows = [
                f"| {name} | 1 | "
                f"{SHEET_FRAME_CELL if name in BEHAVIOUR_COMPONENTS else FRAME_CELL} "
                f"| {STRUCTURE_CELL} | {VALUES_CELL} | the primary route |"
                for name in REQUIRED_COMPONENTS
            ]

        if census is None:
            census = self.census_cell()
        if strong_rows is None:
            strong_rows = [
                self.strong_row(rank, source=DEFAULT_SOURCES[rank - 1])
                for rank in range(1, 7)
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
        return "\n".join((
            "## Research frame",
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
            "- Behavior copied and where it is rendered: The pinned heading with a "
            "sideways product rail from rank 1, rebuilt on the comparison route and "
            "confirmed in its rendered scroll sequence.",
            "- Negative-counterevidence result: The final direction retains visible "
            "task hierarchy and product specificity instead of decorative spectacle.",
            f"- Combination of references (which reference supplies which part, and why no single one of them is this build): {elevation}",
            "- Direction record path and status: .design-dna/direction.md; draft "
            "selection is ready to bind before broad implementation.",
            "",
            SYNTHESIS_HEADER,
            SYNTHESIS_SEPARATOR,
            *synthesis_rows,
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
            real = fixture.capture_cell("strong-1")
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
            self.assertEqual([], fixture.failures(fixture.body(strong_rows=eight)))

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

    def test_combination_and_ledger_check_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            failures = fixture.failures(fixture.body(elevation=""))
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
            "Positive synthesis": "One product-led opening and a comparison rail adapted from ranks 1, 2, and 6.",
            "Negative counterevidence": "The spectacle-first openings named in the counterexamples were avoided.",
            "Rights boundary": "No brand identifiers, copy, media, code, or whole pages were reproduced.",
            "Lineage result": "Wide and narrow renders beside the selected captures show the lineage in the first screen, type scale, and media treatment.",
            "Rendered result": "Wide and narrow renders confirm the synthesis on every affected route.",
            "Combination result": "Full-bleed real product photography at a scale no selected reference attempts.",
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
            for rank in range(1, 7):
                kwargs = dict(observation) if rank == 1 else {}
                host = f"reference-{rank}.example.test"
                cell = project.observation_cell(
                    f"strong-{rank}",
                    url=kwargs.pop("url", f"https://{host}/entry"),
                    **kwargs,
                )
                rows.append(
                    project.strong_row(
                        rank, source=DEFAULT_SOURCES[rank - 1], observation=cell
                    )
                )
            return project.failures(project.body(strong_rows=rows))

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
        self.assertTrue(any("schema_version 3" in item for item in failures), failures)

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
            "Warm domestic object people buy for their home, photography led.",
            "Pure black page with a large opening paragraph.",
            "Stark white, product alone, hairline sans.",
        ):
            with self.subTest(signature=sidewalk):
                failures = self.run_with(signature=sidewalk)
                self.assertTrue(
                    any("not a mechanism" in item for item in failures), failures
                )

    def test_signature_that_names_a_mechanism_passes(self) -> None:
        self.assertEqual([], self.run_with(
            signature="Content holds in the center of the screen while the next thing travels into it."
        ))

    def test_selected_set_must_mostly_move(self) -> None:
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
                    signature="A typographic composition that holds one line at full width.",
                ))
            failures = project.failures(project.body(strong_rows=rows))
        self.assertTrue(any("recorded motion" in item for item in failures), failures)

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
            project, record, section = self.diff(temporary, {
                "tool": "compare_mechanisms.mjs", "pass": True, "verdict": "carried",
            })
            failures = INITIALIZER.mechanism_diff_failures(
                section, project=project, record_path=record
            )
        self.assertEqual([], failures)

    def test_skeleton_build_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project, record, section = self.diff(temporary, {
                "tool": "compare_mechanisms.mjs", "pass": False,
                "verdict": "the references carry scroll choreography and the build carries none",
            })
            failures = INITIALIZER.mechanism_diff_failures(
                section, project=project, record_path=record
            )
        self.assertTrue(any("carries none" in item for item in failures), failures)

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
            project, record, section = self.bind(temporary, {
                "tool": "compare_structure.mjs", "pass": True,
                "census_sha256": "b" * 64, "routes_compared": 2,
                "verdict": "All 2 route(s) are built like a reference page.",
            })
            self.assertEqual([], INITIALIZER.structure_diff_failures(
                section, project=project, record_path=record))

    def test_own_layout_with_borrowed_sizes_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project, record, section = self.bind(temporary, {
                "tool": "compare_structure.mjs", "pass": False,
                "census_sha256": "b" * 64, "routes_compared": 2,
                "verdict": ("the largest thing on the first screen is text "
                            "(<h1>), the reference's is media (<img>)"),
            })
            failures = INITIALIZER.structure_diff_failures(
                section, project=project, record_path=record)
        self.assertTrue(any("largest thing" in i for i in failures), failures)

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
                f"strong-{rank}", url=f"https://reference-{rank}.example.test/"
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
            project, record, section = self.bind(temporary, {
                "tool": "compare_structure.mjs", "pass": True,
                "routes_compared": 1, "census_sha256": None,
                "verdict": "All 1 route(s) are built like a reference page.",
            })
            failures = INITIALIZER.structure_diff_failures(
                section, project=project, record_path=record)
        self.assertTrue(any("component census" in i for i in failures), failures)

    def test_a_census_driven_diff_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project, record, section = self.bind(temporary, {
                "tool": "compare_structure.mjs", "pass": True,
                "routes_compared": 3, "census_sha256": "a" * 64,
                "verdict": "All 3 route(s) are built like a reference page.",
            })
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
            any("must be emitted by extract_reference_styles.mjs" in i for i in failures),
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
            failures = project.failures(project.body(elevation=(
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
            failures = project.failures(project.body(elevation=(
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
        carrier = overrides.pop("carrier", "the first screen on the primary route")
        loss = overrides.pop("loss", TRANSFER_LOSS)
        ranks = overrides.pop("ranks", [1, 2, 3, 4])
        return [
            f"| {rank} | {signature} | {carrier} | {proof} | {loss} |"
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
        self.assertTrue(any("no line for s007, s019" in f for f in failures), failures)

    def test_a_line_that_says_nothing_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, short=(3,))] + [
                project.sequence_block(rank) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("under 40 characters" in f and "s003" in f for f in failures), failures)

    def test_a_read_that_calls_everything_static_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, static_all=True)] + [
                project.sequence_block(rank) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("sheets static" in f for f in failures), failures)

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
            blocks = [project.sequence_block(1, signature_sheets="none")] + [
                project.sequence_block(rank) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("Signature sheets" in f for f in failures), failures)

    def test_a_short_recording_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, sheets=6)] + [
                project.sequence_block(rank) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("has 6 sheets" in f for f in failures), failures)

    def test_a_hand_made_recording_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, tool="by-hand")] + [
                project.sequence_block(rank) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("must be emitted by the packaged record_reference.mjs" in f for f in failures), failures)

    def test_an_event_recording_passes(self):
        """9.1.0: the recorder keeps the moments the screen changed; a line per event."""
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(rank, schema=2) for rank in (1, 2, 3, 4)]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertEqual(failures, [])

    def test_an_event_without_a_line_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, schema=2, omit=(3,))] + [
                project.sequence_block(rank, schema=2) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("no line for e003" in f and "Every event gets a line" in f for f in failures), failures)

    def test_a_recording_with_too_few_events_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, schema=2, events=5)] + [
                project.sequence_block(rank, schema=2) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("has 5 events" in f for f in failures), failures)

    def test_a_signature_not_located_on_an_event_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            blocks = [project.sequence_block(1, schema=2, signature_events="none")] + [
                project.sequence_block(rank, schema=2) for rank in (2, 3, 4)
            ]
            failures = project.failures(project.body(sequence_blocks=blocks))
        self.assertTrue(any("Signature events" in f for f in failures), failures)

    def test_a_behaviour_component_citing_an_event_sheet_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = DossierProject(temporary)
            write_png(project.project / ".design-dna" / "references" / EVENT_FRAME_CELL)
            rows = [
                f"| {name} | 1 | {EVENT_FRAME_CELL if name in BEHAVIOUR_COMPONENTS else FRAME_CELL} "
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


if __name__ == "__main__":
    unittest.main()
