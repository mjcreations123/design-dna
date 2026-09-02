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
    "| Discovery source | Retrieval date | Access status | Capture path and SHA-256 "
    "| Signature (what a stranger would name) | Brief relevance | Design to copy "
    "| Rights boundary |"
)
STRONG_SEPARATOR = (
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
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

# Six references spread over three sources so the default body satisfies the
# spread floor while no source supplies more than half of the rows.
DEFAULT_SOURCES = (
    "awwwards",
    "awwwards",
    "siteinspire",
    "siteinspire",
    "lapa-ninja",
    "typewolf",
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

    def capture_cell(self, name: str) -> str:
        path = self.captures / f"{name}.png"
        if not path.is_file():
            write_png(path)
        return f".design-dna/references/{name}.png plus sha256:{sha256_of(path)}"

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
    ) -> str:
        url_host = host or f"reference-{rank}.example.test"
        return (
            f"| {rank} | Reference {rank} | https://{url_host}/entry | {source} | "
            f"2026-09-01 | {access} | {capture or self.capture_cell(f'strong-{rank}')} | "
            "The product images slide sideways under a pinned heading as the "
            "page is scrolled, which is what anyone would describe first. | "
            "Supports the visitor decision and category story for this exact "
            "project. | A clear hierarchy, media relationship, and direct entry "
            "condition. | Do not reproduce its brand assets, writing, source code, "
            "or full page. |"
        )

    def negative_row(self, index: int, *, source: str = "siteinspire") -> str:
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
            "Real product photography at full-bleed scale on every route, which "
            "none of the selected references attempt; the brief supplies the assets."
        ),
    ) -> str:
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
            f"- Elevation beyond the references (what this build does that none of them do): {elevation}",
            "- Direction record path and status: .design-dna/direction.md; draft "
            "selection is ready to bind before broad implementation.",
            "",
            SYNTHESIS_HEADER,
            SYNTHESIS_SEPARATOR,
            *synthesis_rows,
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

            eight_sources = (*DEFAULT_SOURCES, "css-nectar", "websitevice")
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

            lopsided_sources = ("awwwards",) * 4 + ("siteinspire", "typewolf")
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

            # Ranks 1, 2, 5, 6 span awwwards, lapa-ninja, and typewolf; ranks 1-4
            # under a two-source layout collapse to one source.
            single_source_sources = ("awwwards",) * 3 + ("siteinspire",) * 2 + ("typewolf",)
            rows = [
                fixture.strong_row(rank, source=single_source_sources[rank - 1])
                for rank in range(1, 7)
            ]
            failures = fixture.failures(
                fixture.body(strong_rows=rows, selected="1, 2, 3, 4")
            )
            # 1, 2, 3 are awwwards and 4 is siteinspire: two sources, so this passes.
            self.assertEqual([], failures)

            only_awwwards = [
                fixture.strong_row(rank, source=("awwwards",) * 3 + ("siteinspire", "lapa-ninja", "typewolf"))
                if False else fixture.strong_row(
                    rank,
                    source=(("awwwards",) * 3 + ("siteinspire", "lapa-ninja", "typewolf"))[rank - 1],
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

    def test_elevation_and_ledger_check_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = DossierProject(temporary)
            failures = fixture.failures(fixture.body(elevation=""))
            self.assertTrue(
                any("Elevation beyond the references" in item for item in failures),
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
            self.assertIn("Elevation beyond the references", dossier)
            direction = (state / "direction.md").read_text(encoding="utf-8")
            visual = (state / "visual-review.md").read_text(encoding="utf-8")
            self.assertIn(
                "## Reference-led direction (required for public candidates)",
                direction,
            )
            self.assertIn("Elevation beyond the references", direction)
            self.assertIn(
                "## Reference-led direction closure (required for public candidates)",
                visual,
            )
            self.assertIn("Elevation result", visual)

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
            "Elevation result": "Full-bleed real product photography at a scale no selected reference attempts.",
            "Reference-led direction disposition": "keep",
        }
        values.update(overrides)
        return "\n".join(f"- {label}: {value}" for label, value in values.items())

    def test_complete_closure_passes(self) -> None:
        self.assertEqual(
            [], INITIALIZER.reference_led_closure_label_failures(self.closure())
        )

    def test_elevation_result_is_required(self) -> None:
        for value in ("", "n/a", "see above"):
            with self.subTest(value=value):
                failures = INITIALIZER.reference_led_closure_label_failures(
                    self.closure(**{"Elevation result": value})
                )
                self.assertTrue(
                    any("'Elevation result'" in item for item in failures),
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


if __name__ == "__main__":
    unittest.main()
