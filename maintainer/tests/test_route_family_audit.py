from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
AUDIT = (
    PACKAGE_ROOT
    / "skills"
    / "design-dna"
    / "scripts"
    / "route_family_audit.py"
)
INITIALIZER = (
    PACKAGE_ROOT
    / "skills"
    / "design-dna"
    / "scripts"
    / "init_project_state.py"
)
CONTRACT_SCHEMA = (
    PACKAGE_ROOT / "maintainer" / "schemas" / "route-family.schema.json"
)
AUDIT_SCHEMA = (
    PACKAGE_ROOT
    / "maintainer"
    / "schemas"
    / "route-family-audit.schema.json"
)
RENDER_SCHEMA = (
    PACKAGE_ROOT / "maintainer" / "schemas" / "render-review.schema.json"
)
RUNTIME_RENDER_SCHEMA = (
    PACKAGE_ROOT / "skills" / "design-dna" / "schemas" / "render-review.schema.json"
)
STATE_SCHEMA = (
    PACKAGE_ROOT / "maintainer" / "schemas" / "project-state.schema.json"
)
TEMPLATE = (
    PACKAGE_ROOT
    / "skills"
    / "design-dna"
    / "templates"
    / "route-family-template.json"
)
SAFE_PATHS_FIXTURE = (
    PACKAGE_ROOT
    / "maintainer"
    / "evals"
    / "fixtures"
    / "inputs"
    / "route-family-safe-paths-positive"
)
RENDER_REPORT_TEMPLATE = (
    PACKAGE_ROOT
    / "maintainer"
    / "tests"
    / "fixtures"
    / "render-review-schema3-template.json"
)
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="
)


def validator(path: Path) -> Draft202012Validator:
    document = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(document)
    return Draft202012Validator(
        document,
        format_checker=FormatChecker(),
    )


CONTRACT_VALIDATOR = validator(CONTRACT_SCHEMA)
AUDIT_VALIDATOR = validator(AUDIT_SCHEMA)
RENDER_VALIDATOR = validator(RENDER_SCHEMA)
STATE_VALIDATOR = validator(STATE_SCHEMA)

def load_audit_package_module():
    """Load release-only checks only when a release-gate test needs them."""
    sys.path.insert(0, str(PACKAGE_ROOT / "maintainer" / "scripts"))
    try:
        import audit_package

        return audit_package
    finally:
        sys.path.pop(0)


def run_tool(
    project: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(AUDIT), str(project), *arguments],
        cwd=PACKAGE_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        timeout=120,
        check=False,
    )


def parse_result(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    raw = result.stdout if result.stdout.strip() else result.stderr
    payload = json.loads(raw)
    assert isinstance(payload, dict)
    AUDIT_VALIDATOR.validate(payload)
    return payload


def load_initializer_module():
    specification = importlib.util.spec_from_file_location(
        "design_dna_route_family_initializer_tests",
        INITIALIZER,
    )
    if specification is None or specification.loader is None:
        raise AssertionError("Could not load the project-state initializer.")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def contract(route_paths: list[str]) -> dict[str, object]:
    routes: list[dict[str, object]] = []
    ids: list[str] = []
    for index, path in enumerate(route_paths, start=1):
        candidate = (
            "home"
            if path == "/"
            else path.strip("/").replace("/", "-").replace("_", "-")
        )
        ids.append(
            candidate
            if re.fullmatch(r"[a-z][a-z0-9-]{0,47}", candidate)
            else f"route-{index:02d}"
        )
    for index, (route_id, path) in enumerate(zip(ids, route_paths)):
        sibling = ids[(index + 1) % len(ids)]
        routes.append(
            {
                "id": route_id,
                "path": path,
                "title": f"Route {index + 1}",
                "user_job": "Understand this route's distinct information job.",
                "creative_logic": "A project-specific route body chosen for this information job.",
                "observable_decisions": [
                    {
                        "decision": "The content order and rendered body follow this route's user job.",
                        "reason": "It distinguishes purpose without requiring a fixed aesthetic dimension.",
                        "evidence": "Fixture source and matched rendered captures.",
                        "status": "provisional",
                    }
                ],
                "responsive_result": "The composition adapts around reading priority.",
                "reduced_motion_result": "All meaning remains in a still presentation.",
                "no_javascript_result": "The full route and navigation remain available.",
                "closest_sibling": sibling,
                "deliberate_differences": [
                    "The opening and information order answer a different user need.",
                ],
                "capture_requirements": {
                    "viewports": [
                        {"id": "desktop", "width": 1440},
                        {"id": "mobile", "width": 390},
                    ]
                },
                "review_status": "implemented",
            }
        )
    return {
        "schema_version": 2,
        "created_with": "design-dna 4.0.0",
        "classification": "internal",
        "study": {
            "id": "fixture-range-study",
            "title": "Fixture Range Study",
            "requested_route_count": len(routes),
        },
        "shared_contract": {
            "identity": "A quiet shared identity without repeated page composition.",
            "navigation": "The same semantic route order is available on every page.",
            "truth": "Claims and source status remain explicit and current.",
            "accessibility": "Keyboard, focus, reflow, and reduced motion remain invariant.",
            "voice": "Language stays specific, direct, and audience appropriate.",
            "performance": "Each route keeps a bounded media and script budget.",
        },
        "routes": routes,
        "review": {
            "direct_entry": "pending",
            "link_integrity": "pending",
            "route_count": "pending",
            "body_comparison": "pending",
            "atlas_artifact": "pending",
            "cultural_acceptance": {
                "required": False,
                "status": "not-required",
                "reviewer_id": None,
                "relationship": "not-reviewed",
                "independent_of_producer": False,
                "reviewed_at": None,
                "notes": None,
            },
        },
    }


def write_contract(project: Path, payload: dict[str, object]) -> Path:
    state = project / ".design-dna"
    state.mkdir(parents=True, exist_ok=True)
    path = state / "route-family.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def write_static_route(
    project: Path,
    route_path: str,
    links: list[tuple[str, str]],
    *,
    redirect: str | None = None,
) -> None:
    target = (
        project / "index.html"
        if route_path == "/"
        else project / route_path.strip("/") / "index.html"
        if route_path.endswith("/")
        else project / route_path.lstrip("/")
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    navigation = "".join(
        f'<a href="{href}">{label}</a>' for href, label in links
    )
    redirect_tag = (
        f'<meta http-equiv="refresh" content="0;url={redirect}">'
        if redirect
        else ""
    )
    target.write_text(
        "<!doctype html><html lang=\"en\"><head>"
        f"{redirect_tag}<title>Fixture</title></head><body>"
        f"<nav>{navigation}</nav><main><section><h1>{route_path}</h1>"
        "<p>Distinct route content.</p></section><article><h2>Evidence</h2>"
        "<p>Bound evidence.</p></article></main></body></html>",
        encoding="utf-8",
    )


def silhouette_region(
    order: int,
    tag: str,
    heading: str,
    selector: str,
    *,
    normalized_y: float,
    normalized_height: float,
    role: str | None = None,
    media_count: int = 0,
    control_count: int = 0,
    columns: int = 1,
) -> dict[str, object]:
    width = 1440.0
    height = normalized_height * 900.0
    top = normalized_y * 900.0
    return {
        "order": order,
        "tag": tag,
        "role": role,
        "heading": heading,
        "label": "",
        "selector": selector,
        "rect": {
            "x": 0.0,
            "y": top,
            "width": width,
            "height": height,
            "right": width,
            "bottom": top + height,
        },
        "normalized_rect": {
            "x": 0.0,
            "y": normalized_y,
            "width": 1.0,
            "height": normalized_height,
        },
        "display": "grid" if columns > 1 else "block",
        "position": "static",
        "grid_column_count": columns if columns > 1 else 0,
        "flex_direction": None,
        "visual_column_count": columns,
        "direct_visible_child_count": max(columns, 1),
        "text_length": 240,
        "media_count": media_count,
        "control_count": control_count,
        "sticky_or_fixed": False,
        "dominant_media_area_ratio": 0.45 if media_count else 0.0,
        "heading_rect": {
            "x": 80.0,
            "y": top + 40.0,
            "width": 720.0,
            "height": 80.0,
            "right": 800.0,
            "bottom": top + 120.0,
        }
        if heading
        else None,
        "heading_font_size_px": 64.0 if heading else None,
        "heading_font_weight": "700" if heading else None,
        "heading_text_align": "start" if heading else None,
    }


def write_render_report(
    project: Path,
    route_paths: list[str],
    *,
    batch_name: str = "render",
    route_index_offset: int = 0,
) -> Path:
    output = project / ".design-dna" / batch_name
    captures_dir = output / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)
    report = json.loads(RENDER_REPORT_TEMPLATE.read_text(encoding="utf-8"))
    blueprints = {
        int(capture["viewport"]["width"]): capture
        for capture in report["captures"]
    }
    captures: list[dict[str, object]] = []
    routes: list[dict[str, object]] = []
    for route_index, route_path in enumerate(route_paths, start=1):
        route_id = f"route-{route_index + route_index_offset:02d}"
        routes.append(
            {
                "id": route_id,
                "requested": route_path,
                "url": f"http://127.0.0.1:4173{route_path}",
            }
        )
        for viewport_id, width in (("desktop", 1440), ("mobile", 390)):
            filename = f"{route_id}-{viewport_id}.png"
            screenshot_path = captures_dir / filename
            screenshot_path.write_bytes(PNG_1X1)
            digest = hashlib.sha256(PNG_1X1).hexdigest()
            capture = copy.deepcopy(blueprints[width])
            capture["id"] = f"capture-{route_index + route_index_offset:02d}-{viewport_id}"
            capture["route_id"] = route_id
            capture["route_label"] = route_path
            capture["requested_url"] = f"http://127.0.0.1:4173{route_path}"
            capture["final_url"] = f"http://127.0.0.1:4173{route_path}"
            capture["http_status"] = 200
            capture["screenshot"] = {
                "path": f"captures/{filename}",
                "sha256": digest,
                "media_type": "image/png",
                "bytes": len(PNG_1X1),
                "pixel_width": 1,
                "pixel_height": 1,
            }
            capture["document"]["route_silhouette"] = [
                silhouette_region(
                    1,
                    "section",
                    "Opening",
                    "main > section",
                    normalized_y=0.0,
                    normalized_height=0.4,
                    media_count=1,
                    control_count=1,
                    columns=2,
                ),
                silhouette_region(
                    2,
                    "article",
                    "Evidence",
                    "main > article",
                    normalized_y=0.4,
                    normalized_height=0.5,
                ),
                silhouette_region(
                    3,
                    "aside",
                    "Sources",
                    "main > aside.shared-source-strip",
                    normalized_y=0.9,
                    normalized_height=0.05,
                ),
                silhouette_region(
                    4,
                    "footer",
                    "",
                    "main > footer",
                    normalized_y=0.95,
                    normalized_height=0.05,
                    role="contentinfo",
                ),
            ]
            captures.append(capture)
    report["routes"] = routes
    report["captures"] = captures
    RENDER_VALIDATOR.validate(report)
    path = output / "render-review.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


class RouteFamilyContractTests(unittest.TestCase):
    def test_runtime_render_schema_is_the_exact_maintained_contract(self) -> None:
        self.assertEqual(
            RUNTIME_RENDER_SCHEMA.read_bytes(),
            RENDER_SCHEMA.read_bytes(),
        )

    def test_packaged_template_validates_after_version_substitution(self) -> None:
        payload = json.loads(
            TEMPLATE.read_text(encoding="utf-8").replace(
                "__DESIGN_DNA_VERSION__",
                "design-dna 4.0.0",
            )
        )
        CONTRACT_VALIDATOR.validate(payload)
        for route in payload["routes"]:
            self.assertEqual(route["review_status"], "planned")
            self.assertTrue(
                all(
                    viewport["width"] is None
                    for viewport in route["capture_requirements"]["viewports"]
                )
            )

    def test_unresolved_width_is_valid_only_for_a_planned_route(self) -> None:
        payload = json.loads(
            TEMPLATE.read_text(encoding="utf-8").replace(
                "__DESIGN_DNA_VERSION__",
                "design-dna 4.0.0",
            )
        )
        CONTRACT_VALIDATOR.validate(payload)
        payload["routes"][0]["review_status"] = "implemented"
        errors = sorted(
            CONTRACT_VALIDATOR.iter_errors(payload),
            key=lambda error: list(error.absolute_path),
        )
        self.assertTrue(errors)
        self.assertTrue(
            any(list(error.absolute_path)[-1:] == ["width"] for error in errors)
        )

    def test_planned_template_audit_reports_unresolved_widths_without_crashing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            payload = json.loads(
                TEMPLATE.read_text(encoding="utf-8").replace(
                    "__DESIGN_DNA_VERSION__",
                    "design-dna 4.0.0",
                )
            )
            write_contract(project, payload)
            result = run_tool(project, "--no-atlas")
            self.assertEqual(result.returncode, 1, result.stderr)
            report = parse_result(result)
            self.assertEqual(report["contract"]["status"], "loaded")
            self.assertFalse(report["rendered_coverage"]["complete"])
            self.assertTrue(
                all(
                    route["captures"] == []
                    for route in report["rendered_coverage"]["routes"]
                )
            )
            self.assertTrue(
                any(
                    "unresolved project-derived capture widths" in limitation
                    for limitation in report["rendered_coverage"]["limitations"]
                )
            )

    def test_hash_and_query_paths_fail_closed_without_authorship_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            payload = contract(["/", "/second/"])
            payload["routes"][1]["path"] = "/second/?view=alternate#panel"
            write_contract(project, payload)
            result = run_tool(project)
            self.assertEqual(result.returncode, 1, result.stderr)
            report = parse_result(result)
            self.assertTrue(report["execution_ok"])
            self.assertEqual(report["audit_status"], "contract-invalid")
            self.assertFalse(report["automatic_aesthetic_pass"])
            self.assertEqual(report["authorship_classification"], "not-performed")
            codes = {
                item["code"] for item in report["contract"]["errors"]
            }
            self.assertIn("invalid-route-path", codes)

    def test_unsafe_route_path_forms_fail_closed(self) -> None:
        unsafe_paths = (
            "/second/#panel",
            "/../secret/",
            "/safe/%2e%2e/",
            "/bad\\path/",
            "/bad\u0001path/",
            "/encoded%2Fseparator/",
            "//example.invalid/path/",
            "/double//segment/",
        )
        for unsafe_path in unsafe_paths:
            with self.subTest(path=unsafe_path), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                payload = contract(["/", "/second/"])
                payload["routes"][1]["path"] = unsafe_path
                write_contract(project, payload)
                result = run_tool(project)
                self.assertEqual(result.returncode, 1, result.stderr)
                report = parse_result(result)
                self.assertEqual(report["audit_status"], "contract-invalid")
                self.assertIn(
                    "invalid-route-path",
                    {item["code"] for item in report["contract"]["errors"]},
                )

    def test_open_creative_logic_honest_reuse_and_project_viewports_validate(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            payload = contract(["/", "/second/"])
            payload["routes"][0]["creative_logic"] = {
                "project_statement": "The route follows the supplied material.",
                "unfixed_concerns": {
                    "density": "Chosen from the actual reading task.",
                    "media": ["Owner-supplied evidence", "No decorative quota"],
                },
            }
            payload["routes"][0]["deliberate_differences"] = []
            for route in payload["routes"]:
                route["capture_requirements"]["viewports"] = [
                    {"id": "reading-narrow", "width": 768},
                    {"id": "reading-wide", "width": 1366},
                ]
            CONTRACT_VALIDATOR.validate(payload)
            write_contract(project, payload)
            write_static_route(project, "/", [("/second/", "Second")])
            write_static_route(project, "/second/", [("/", "Home")])
            result = run_tool(project, "--no-atlas")
            self.assertEqual(result.returncode, 1, result.stderr)
            report = parse_result(result)
            self.assertEqual(report["contract"]["status"], "loaded")
            self.assertNotEqual(report["audit_status"], "contract-invalid")

    def test_required_cultural_acceptance_still_needs_independent_authority(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            payload = contract(["/", "/second/"])
            payload["review"]["cultural_acceptance"] = {
                "required": True,
                "status": "accepted",
                "reviewer_id": "producer",
                "relationship": "owner-authorized-cultural-reviewer",
                "independent_of_producer": False,
                "reviewed_at": "2026-08-02T12:00:00Z",
                "notes": "Producer review cannot count as independent acceptance.",
            }
            write_contract(project, payload)
            result = run_tool(project)
            self.assertEqual(result.returncode, 1, result.stderr)
            report = parse_result(result)
            self.assertIn(
                "cultural-acceptance-not-independent",
                {item["code"] for item in report["contract"]["errors"]},
            )

    def test_missing_contract_is_a_schema_valid_execution_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = run_tool(Path(temporary))
            self.assertEqual(result.returncode, 2)
            report = parse_result(result)
            self.assertFalse(report["execution_ok"])
            self.assertEqual(
                report["error"]["code"],
                "route-family-contract-missing",
            )


class RouteFamilyStructuralAuditTests(unittest.TestCase):
    def test_render_report_ingestion_fails_closed_on_nested_schema_drift(self) -> None:
        mutations = {
            "missing typography sampling": lambda payload: payload["captures"][0][
                "document"
            ].pop("typography_sampling"),
            "unexpected viewport field": lambda payload: payload["captures"][0][
                "viewport"
            ].update({"invented_width_mode": True}),
            "invalid manual review state": lambda payload: payload[
                "manual_review"
            ].update({"status": "machine-approved"}),
            "malformed bracketed uri": lambda payload: payload["captures"][0].update(
                {"requested_url": "http://[malformed"}
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                routes = ["/", "/second/"]
                write_contract(project, contract(routes))
                write_static_route(project, "/", [("/second/", "Second")])
                write_static_route(project, "/second/", [("/", "Home")])
                rendered = write_render_report(project, routes)
                payload = json.loads(rendered.read_text(encoding="utf-8"))
                mutate(payload)
                rendered.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                result = run_tool(
                    project,
                    "--render-review",
                    str(rendered),
                    "--no-atlas",
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                report = parse_result(result)
                self.assertFalse(report["execution_ok"])
                self.assertEqual(
                    report["error"]["code"],
                    "render-report-contract-invalid",
                )
                self.assertIn("complete bundled schema-3 contract", report["error"]["message"])

    def test_static_routes_links_redirects_and_orphans_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            write_contract(project, contract(["/", "/second/", "/alias/"]))
            write_static_route(
                project,
                "/",
                [("/second/", "Second"), ("/missing/", "Missing")],
            )
            write_static_route(project, "/second/", [("/", "Home")])
            write_static_route(
                project,
                "/alias/",
                [("/", "Home")],
                redirect="/second/",
            )
            result = run_tool(project, "--no-atlas")
            self.assertEqual(result.returncode, 1, result.stderr)
            report = parse_result(result)
            statuses = {
                route["id"]: route["status"]
                for route in report["route_resolution"]["routes"]
            }
            self.assertEqual(statuses["alias"], "redirect")
            finding_codes = {item["code"] for item in report["findings"]}
            self.assertIn("declared-route-is-redirect", finding_codes)
            self.assertIn("broken-local-link", finding_codes)
            self.assertIn("orphan-route", finding_codes)
            self.assertIn("rendered-route-coverage-incomplete", finding_codes)

    def test_rendered_coverage_clusters_and_optional_atlas_are_machine_readable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            routes = ["/", "/second/"]
            write_contract(project, contract(routes))
            write_static_route(project, "/", [("/second/", "Second")])
            write_static_route(project, "/second/", [("/", "Home")])
            rendered = write_render_report(project, routes)
            result = run_tool(
                project,
                "--render-review",
                str(rendered),
                "--output",
                ".design-dna/route-family-audit.json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = parse_result(result)
            self.assertEqual(report["audit_status"], "manual-review-required")
            self.assertTrue(report["rendered_coverage"]["complete"])
            self.assertEqual(
                report["rendered_coverage"]["matched_route_count"],
                2,
            )
            self.assertEqual(
                report["silhouette_analysis"]["clusters"][0]["route_ids"],
                ["home", "second"],
            )
            self.assertTrue(
                all(
                    len(route["signature"]) == 12
                    for route in report["silhouette_analysis"]["routes"]
                )
            )
            self.assertEqual(
                {cluster["viewport_width"] for cluster in report["silhouette_analysis"]["clusters"]},
                {390, 1440},
            )
            self.assertTrue(
                all(
                    len(viewport["signature"]) == 6
                    for route in report["silhouette_analysis"]["routes"]
                    for viewport in route["viewport_signatures"]
                )
            )
            self.assertEqual(report["route_atlas"]["status"], "created")
            self.assertEqual(
                report["route_atlas"]["media_type"],
                "text/html",
            )
            atlas_path = project / ".design-dna" / "route-atlas.html"
            self.assertTrue(atlas_path.is_file())
            atlas_html = atlas_path.read_text(encoding="utf-8")
            self.assertIn("Content-Security-Policy", atlas_html)
            self.assertIn("captures/route-01-desktop.png", atlas_html)
            written = json.loads(
                (
                    project
                    / ".design-dna"
                    / "route-family-audit.json"
                ).read_text(encoding="utf-8")
            )
            AUDIT_VALIDATOR.validate(written)

    def test_cosmetic_reskin_with_different_tags_and_copy_still_clusters(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            routes = ["/", "/second/"]
            write_contract(project, contract(routes))
            write_static_route(project, "/", [("/second/", "Second")])
            write_static_route(project, "/second/", [("/", "Home")])
            rendered = write_render_report(project, routes)
            payload = json.loads(rendered.read_text(encoding="utf-8"))
            for capture in payload["captures"]:
                if capture["requested_url"].endswith("/second/"):
                    body = capture["document"]["route_silhouette"]
                    body[0]["tag"] = "div"
                    body[0]["heading"] = "Entirely different words"
                    body[0]["selector"] = "main > div:nth-of-type(1)"
                    body[1]["tag"] = "figure"
                    body[1]["heading"] = "Another label"
                    body[1]["selector"] = "main > figure"
            rendered.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            result = run_tool(project, "--render-review", str(rendered), "--no-atlas")
            self.assertEqual(result.returncode, 0, result.stderr)
            report = parse_result(result)
            self.assertEqual(
                report["silhouette_analysis"]["clusters"][0]["route_ids"],
                ["home", "second"],
            )
            normalization = report["silhouette_analysis"]["normalization"]
            self.assertIn("font-family", normalization)
            self.assertIn("element-names", normalization)

    def test_same_semantic_tags_with_different_rendered_geometry_do_not_cluster(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            routes = ["/", "/second/"]
            write_contract(project, contract(routes))
            write_static_route(project, "/", [("/second/", "Second")])
            write_static_route(project, "/second/", [("/", "Home")])
            rendered = write_render_report(project, routes)
            payload = json.loads(rendered.read_text(encoding="utf-8"))
            for capture in payload["captures"]:
                if capture["requested_url"].endswith("/second/"):
                    body = capture["document"]["route_silhouette"]
                    body[0]["normalized_rect"] = {
                        "x": 0.18,
                        "y": 0.0,
                        "width": 0.64,
                        "height": 0.15,
                    }
                    body[1]["normalized_rect"] = {
                        "x": 0.05,
                        "y": 0.62,
                        "width": 0.9,
                        "height": 0.18,
                    }
            rendered.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            result = run_tool(project, "--render-review", str(rendered), "--no-atlas")
            self.assertEqual(result.returncode, 0, result.stderr)
            report = parse_result(result)
            self.assertEqual(report["silhouette_analysis"]["clusters"], [])

    def test_mobile_only_repeated_skeleton_is_not_hidden_by_desktop_difference(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            routes = ["/", "/second/"]
            write_contract(project, contract(routes))
            write_static_route(project, "/", [("/second/", "Second")])
            write_static_route(project, "/second/", [("/", "Home")])
            rendered = write_render_report(project, routes)
            payload = json.loads(rendered.read_text(encoding="utf-8"))
            for capture in payload["captures"]:
                if (
                    capture["requested_url"].endswith("/second/")
                    and capture["viewport"]["width"] == 1440
                ):
                    body = capture["document"]["route_silhouette"]
                    body[0]["normalized_rect"] = {
                        "x": 0.18,
                        "y": 0.0,
                        "width": 0.64,
                        "height": 0.15,
                    }
                    body[1]["normalized_rect"] = {
                        "x": 0.05,
                        "y": 0.62,
                        "width": 0.9,
                        "height": 0.18,
                    }
            rendered.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            result = run_tool(project, "--render-review", str(rendered), "--no-atlas")
            self.assertEqual(result.returncode, 0, result.stderr)
            report = parse_result(result)
            self.assertEqual(
                [cluster["viewport_width"] for cluster in report["silhouette_analysis"]["clusters"]],
                [390],
            )

    def test_thirteen_route_batches_reconcile_without_a_family_count_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            routes = ["/"] + [f"/route-{index:02d}/" for index in range(2, 14)]
            write_contract(project, contract(routes))
            links = [(path, f"Route {index + 1}") for index, path in enumerate(routes)]
            for route_path in routes:
                write_static_route(project, route_path, links)
            reports: list[Path] = []
            for index, route_path in enumerate(routes, start=1):
                reports.append(
                    write_render_report(
                        project,
                        [route_path],
                        batch_name=f"render-batch-{index:02d}",
                        route_index_offset=index - 1,
                    )
                )
            arguments: list[str] = []
            for rendered in reports:
                arguments.extend(("--render-review", str(rendered)))
            arguments.append("--no-atlas")
            result = run_tool(project, *arguments)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = parse_result(result)
            self.assertEqual(report["contract"]["declared_route_count"], 13)
            self.assertEqual(report["rendered_coverage"]["matched_route_count"], 13)
            self.assertTrue(report["rendered_coverage"]["complete"])
            self.assertEqual(report["resource_usage"]["render_reports_read"], 13)
            last_route = next(
                route
                for route in report["silhouette_analysis"]["routes"]
                if route["path"] == "/route-13/"
            )
            self.assertEqual(len(last_route["viewport_signatures"]), 2)
            self.assertTrue(
                all(
                    "render-batch-13/render-review.json"
                    in viewport["report_evidence"]["path"]
                    for viewport in last_route["viewport_signatures"]
                )
            )

    def test_permanent_safe_path_fixture_resolves_without_rewriting_paths(self) -> None:
        result = run_tool(SAFE_PATHS_FIXTURE, "--no-atlas")
        self.assertEqual(result.returncode, 1, result.stderr)
        report = parse_result(result)
        self.assertEqual(report["contract"]["status"], "loaded")
        expected = {"/", "/Lakewood/", "/תורה/", "/made_here/", "/about.html"}
        self.assertEqual(
            {route["path"] for route in report["route_resolution"]["routes"]},
            expected,
        )
        self.assertTrue(
            all(route["status"] == "resolved" for route in report["route_resolution"]["routes"])
        )
        self.assertEqual(report["link_graph"]["broken_links"], [])
        self.assertEqual(report["link_graph"]["orphaned_routes"], [])


class RouteFamilyInitializerTests(unittest.TestCase):
    def test_readiness_uses_the_contract_body_comparison_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            payload = contract(["/", "/second/"])
            payload["review"].update(
                {
                    "direct_entry": "passed",
                    "link_integrity": "passed",
                    "route_count": "passed",
                    "body_comparison": "reviewed",
                    "atlas_artifact": "reviewed",
                }
            )
            for route in payload["routes"]:
                route["review_status"] = "accepted"
            write_contract(project, payload)
            (project / ".design-dna" / "state.json").write_text(
                json.dumps(
                    {
                        "assurance_profiles": ["standard", "range-study"],
                        "records": ["route-family"],
                    }
                ),
                encoding="utf-8",
            )
            initializer = load_initializer_module()
            self.assertEqual(initializer.readiness_failures(project), [])

            payload["review"]["body_comparison"] = "manual-review-required"
            write_contract(project, payload)
            self.assertIn(
                "Listed route-family body comparison remains unreviewed.",
                initializer.readiness_failures(project),
            )

    def test_range_study_profile_initializes_optional_record_and_blocks_readiness(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [
                    sys.executable,
                    str(INITIALIZER),
                    "--project",
                    str(project),
                    "--profile",
                    "range-study",
                    "--json",
                ],
                cwd=PACKAGE_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                timeout=120,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads(
                (project / ".design-dna" / "state.json").read_text(
                    encoding="utf-8"
                )
            )
            STATE_VALIDATOR.validate(state)
            self.assertIn("route-family", state["records"])
            self.assertEqual(
                state["assurance_profiles"],
                ["standard", "range-study"],
            )
            route_family = json.loads(
                (project / ".design-dna" / "route-family.json").read_text(
                    encoding="utf-8"
                )
            )
            CONTRACT_VALIDATOR.validate(route_family)
            self.assertTrue(
                all(
                    viewport["width"] is None
                    for route in route_family["routes"]
                    for viewport in route["capture_requirements"]["viewports"]
                )
            )
            ready = subprocess.run(
                [
                    sys.executable,
                    str(INITIALIZER),
                    "--project",
                    str(project),
                    "--check-ready",
                    "--json",
                ],
                cwd=PACKAGE_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                timeout=120,
                check=False,
            )
            self.assertEqual(ready.returncode, 1)
            ready_payload = json.loads(ready.stdout or ready.stderr)
            self.assertIn("route-family", json.dumps(ready_payload))
            self.assertIn(
                "project-derived integer",
                json.dumps(ready_payload),
            )


class RouteFamilyReleaseGateTests(unittest.TestCase):
    def test_route_family_gate_requires_complete_passing_analysis(self) -> None:
        audit_package = load_audit_package_module()
        contract_record = {
            "release_coverage": {"route_family_showcase_gate": True}
        }
        payload = {
            "reviewer": {"lens": "perception"},
            "route_family_analysis": {
                "declared_route_count": 2,
                "verified_route_count": 2,
                "routes": [
                    {
                        "id": "home",
                        "direct_entry_status": "passed",
                        "capture_status": "matched",
                    },
                    {
                        "id": "second",
                        "direct_entry_status": "passed",
                        "capture_status": "matched",
                    },
                ],
                "repeated_clusters": [],
                "conclusion": {
                    "unique_direct_routes": True,
                    "matched_capture_coverage": True,
                    "unresolved_repeated_skeleton": False,
                    "decision": "pass",
                },
            },
        }
        self.assertEqual(
            audit_package.route_family_showcase_gate_failures(
                payload,
                contract_record,
                "fixture",
            ),
            [],
        )
        payload["route_family_analysis"]["routes"][1][
            "capture_status"
        ] = "incomplete"
        codes = {
            item["code"]
            for item in audit_package.route_family_showcase_gate_failures(
                payload,
                contract_record,
                "fixture",
            )
        }
        self.assertIn("release-route-family-route-evidence-incomplete", codes)

    def test_cultural_gate_rejects_pending_or_producer_review(self) -> None:
        audit_package = load_audit_package_module()
        contract_record = {
            "release_coverage": {"cultural_context_gate": True}
        }
        payload = {
            "reviewer": {"lens": "perception"},
            "cultural_context_review": {
                "status": "accepted",
                "authority": {
                    "reviewer_id": "community-reviewer",
                    "relationship": "owner-authorized-cultural-reviewer",
                    "independent_of_producer": True,
                    "reviewed_at": "2026-07-30T15:00:00Z",
                    "evidence": [{"path": "evidence/review.md", "sha256": "a" * 64}],
                },
                "open_questions": [],
            },
        }
        self.assertEqual(
            audit_package.cultural_context_gate_failures(
                payload,
                contract_record,
                "fixture",
            ),
            [],
        )
        payload["cultural_context_review"]["authority"][
            "independent_of_producer"
        ] = False
        codes = {
            item["code"]
            for item in audit_package.cultural_context_gate_failures(
                payload,
                contract_record,
                "fixture",
            )
        }
        self.assertIn("release-cultural-context-authority-ineligible", codes)


if __name__ == "__main__":
    unittest.main()
