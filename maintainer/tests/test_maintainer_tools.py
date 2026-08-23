from __future__ import annotations

import json
import hashlib
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN / "maintainer" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from common import (  # noqa: E402
    LOCAL_TOOL_DIRECTORY_NAMES,
    ToolFailure,
    compiled_python_residue_paths,
    content_manifest,
    eval_content_manifest,
    is_reparse,
    load_json,
    walk_files,
)


def run_script(
    name: str,
    *arguments: str,
    environment_overrides: dict[str, str] | None = None,
    timeout: float = 120,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    if environment_overrides:
        environment.update(environment_overrides)
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPTS / name), *arguments],
        text=True, encoding="utf-8", capture_output=True, env=environment,
        timeout=timeout,
    )


def make_directory_link(link: Path, target: Path) -> bool:
    try:
        os.symlink(target, link, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        if os.name != "nt":
            return False
        completed = subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(link), str(target)],
            text=True, capture_output=True,
        )
        return completed.returncode == 0


def minimal_skill_text(text: str = "canonical") -> str:
    return (
        "---\n"
        "name: design-dna\n"
        f"description: {json.dumps(text)}\n"
        "---\n\n"
        f"{text}\n"
    )


def minimal_skill(root: Path, text: str = "canonical") -> None:
    root.mkdir()
    (root / "SKILL.md").write_text(minimal_skill_text(text), encoding="utf-8")
    (root / "release.json").write_text('{"package":"design-dna","version":"2.0.0","state_schema_version":1}\n', encoding="utf-8")
    (root / "nested").mkdir()
    (root / "nested" / "file.txt").write_text("same\n", encoding="utf-8")


def compile_sourceless_module(
    source: Path,
    bytecode: Path,
    code: str,
) -> None:
    source.write_text(code, encoding="utf-8")
    py_compile.compile(
        str(source),
        cfile=str(bytecode),
        doraise=True,
    )
    source.unlink()


def write_eval_suite(
    root: Path,
    *,
    suite: str = "runner-smoke",
    case_id: str = "writes-artifact",
    task: str = "Create the requested test artifact in the isolated workspace.",
    timeout_seconds: int = 30,
    input_dir: str | None = None,
    expected: dict[str, object] | None = None,
) -> Path:
    case: dict[str, object] = {
        "id": case_id,
        "task": task,
        "timeout_seconds": timeout_seconds,
        "review_requirements": [
            "Confirm the requested behavior from the exact captured build."
        ],
    }
    if input_dir is not None:
        case["input_dir"] = input_dir
    if expected is not None:
        case["expected"] = expected
    fixture = root / "suite.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "suite": suite,
                "skill_instructions": {
                    "codex": (
                        "Use $design-dna for this task and follow its required verification."
                    ),
                    "claude_code": (
                        "Use /design-dna for this task and follow its required verification."
                    ),
                },
                "cases": [case],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return fixture


def run_eval(
    root: Path,
    fixture: Path,
    code: str,
    *,
    host: str = "codex",
    baseline_code: str | None = None,
    runs: int = 1,
    monitor_roots: tuple[Path, ...] = (),
    keep_workspaces: bool = False,
    require_driver_report: bool = False,
    environment_overrides: dict[str, str] | None = None,
    pass_env: tuple[str, ...] = (),
    work_root: Path | None = None,
    results_dir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    work = work_root or root / "work"
    results = results_dir or root / "results"
    work.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    arguments = [
        str(fixture),
        "--host",
        host,
        "--driver",
        sys.executable,
        "--driver-arg=-c",
        f"--driver-arg={code}",
        "--runs",
        str(runs),
        "--work-root",
        str(work),
        "--results-dir",
        str(results),
    ]
    if baseline_code is not None:
        arguments.extend(
            [
                "--baseline-driver",
                sys.executable,
                "--baseline-arg=-c",
                f"--baseline-arg={baseline_code}",
            ]
        )
    for monitor in monitor_roots:
        arguments.extend(["--monitor-root", str(monitor)])
    if keep_workspaces:
        arguments.append("--keep-workspaces")
    if require_driver_report:
        arguments.append("--require-driver-report")
    for name in pass_env:
        arguments.extend(["--pass-env", name])
    return run_script(
        "run_evals.py",
        *arguments,
        environment_overrides=environment_overrides,
    )


def load_only_result(results: Path) -> tuple[dict[str, object], Path]:
    paths = list(results.glob("*.json"))
    if len(paths) != 1:
        raise AssertionError(f"expected one result document, found {paths}")
    return json.loads(paths[0].read_text(encoding="utf-8")), paths[0]


class ManifestTests(unittest.TestCase):
    def test_published_codex_metadata_and_long_reference_navigation_are_current(
        self,
    ) -> None:
        manifest = json.loads(
            (PLUGIN / ".codex-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            manifest["interface"]["capabilities"],
            ["Read", "Write"],
        )

        asset_reference = (
            PLUGIN
            / "skills"
            / "design-dna"
            / "references"
            / "quality"
            / "asset-integrity.md"
        ).read_text(encoding="utf-8")
        self.assertGreater(len(asset_reference.splitlines()), 100)
        self.assertIn("## Contents", asset_reference)
        for anchor in (
            "#record-provenance",
            "#generated-and-synthetic-material",
            "#preserve-truth",
            "#direct-and-implement",
            "#release-gate",
        ):
            self.assertIn(f"]({anchor})", asset_reference)

    def test_release_route_proof_declares_custom_claude_config_boundary(
        self,
    ) -> None:
        release_guide = (PLUGIN / "docs" / "RELEASE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("CLAUDE_CONFIG_DIR", release_guide)
        self.assertIn(
            "do not let the release command silently verify",
            release_guide,
        )
        self.assertIn(
            "Do not overwrite the\n"
            "distributed route attestation with that diagnostic",
            release_guide,
        )
        sync = release_guide.index(
            "manage_install.py sync --host all"
        )
        doctor = release_guide.index(
            "manage_install.py doctor --host all",
            sync,
        )
        route_proof = release_guide.index(
            "detect_routes.py --canonical",
            doctor,
        )
        self.assertLess(sync, doctor)
        self.assertLess(doctor, route_proof)

    def test_worktree_walk_can_prune_local_tool_environments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            kept = root / "docs" / "guide.md"
            ignored = root / ".venv" / "Lib" / "package.md"
            kept.parent.mkdir()
            ignored.parent.mkdir(parents=True)
            kept.write_text("kept\n", encoding="utf-8")
            ignored.write_text("ignored local environment file\n", encoding="utf-8")
            selected = {
                path.relative_to(root).as_posix()
                for path in walk_files(
                    root,
                    ignored_directory_names=LOCAL_TOOL_DIRECTORY_NAMES,
                )
            }
            self.assertEqual(selected, {"docs/guide.md"})

    def test_windows_cloud_tag_is_allowed_but_name_surrogate_is_refused(self) -> None:
        directory_mode = 0o040755
        with patch.object(Path, "lstat", return_value=SimpleNamespace(
            st_mode=directory_mode, st_file_attributes=0x400, st_reparse_tag=0x9000001A
        )):
            self.assertFalse(is_reparse(Path("cloud-entry")))
        with patch.object(Path, "lstat", return_value=SimpleNamespace(
            st_mode=directory_mode, st_file_attributes=0x400, st_reparse_tag=0xA0000003
        )):
            self.assertTrue(is_reparse(Path("junction")))

    def test_duplicate_json_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "duplicate.json"
            path.write_text('{"version":"1.0.0","version":"2.0.0"}', encoding="utf-8")
            with self.assertRaises(ToolFailure):
                load_json(path)

    def test_hash_is_path_and_content_exact_but_ignores_runtime_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            one, two = Path(temporary) / "one", Path(temporary) / "two"
            minimal_skill(one)
            minimal_skill(two)
            (two / "__pycache__").mkdir()
            (two / "__pycache__" / "noise.pyc").write_bytes(b"noise")
            self.assertEqual(content_manifest(one), content_manifest(two))
            (two / "meaningful-empty-directory").mkdir()
            self.assertNotEqual(content_manifest(one), content_manifest(two))
            (two / "meaningful-empty-directory").rmdir()
            (two / "nested" / "file.txt").write_text("changed\n", encoding="utf-8")
            self.assertNotEqual(content_manifest(one), content_manifest(two))

    def test_distribution_manifest_omits_untracked_empty_directories(self) -> None:
        from build_manifest import distribution_manifest

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "plugin"
            retained = root / "maintainer" / "evals" / "archive" / "proof.json"
            retained.parent.mkdir(parents=True)
            retained.write_text("{}\n", encoding="utf-8")
            (root / "maintainer" / "evals" / "results").mkdir(parents=True)
            records, _digest = distribution_manifest(root)
            paths = {str(item["path"]) for item in records}

            self.assertIn("maintainer/evals/archive/proof.json", paths)
            self.assertIn("maintainer/evals/archive", paths)
            self.assertNotIn("maintainer/evals/results", paths)

    def test_compiled_residue_enumerator_reports_cache_once_and_loose_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested_cache = root / "nested" / "__PyCache__"
            nested_cache.mkdir(parents=True)
            (nested_cache / "one.pyc").write_bytes(b"one")
            loose = root / "tool.PYO"
            loose.write_bytes(b"two")
            self.assertEqual(
                {
                    path.relative_to(root).as_posix()
                    for path in compiled_python_residue_paths(root)
                },
                {"nested/__PyCache__", "tool.PYO"},
            )

    def test_markdown_link_anchor_reference_and_image_checks(self) -> None:
        from check_links import check

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "target.md").write_text("# Existing heading\n", encoding="utf-8")
            (root / "page.md").write_text(
                "[good](target.md#existing-heading)\n"
                "[bad](target.md#missing)\n"
                "![missing image][hero]\n"
                "[hero]: missing.png\n",
                encoding="utf-8",
            )
            failures, warnings = check(root, online=False, timeout=1)
            self.assertTrue(
                any(
                    item["code"] == "unverified-renderer-anchor"
                    for item in warnings
                )
            )
            self.assertTrue(any(item["code"] == "missing-image" for item in failures))

    def test_link_check_skips_intentionally_broken_behavioral_fixture_inputs(
        self,
    ) -> None:
        from check_links import check

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = (
                root
                / "maintainer"
                / "evals"
                / "fixtures"
                / "inputs"
                / "broken-route-case"
            )
            fixture.mkdir(parents=True)
            (fixture / "index.html").write_text(
                '<a href="/deliberately-missing/">Missing fixture route</a>',
                encoding="utf-8",
            )
            (root / "ordinary.md").write_text(
                "[Missing package link](missing.md)\n",
                encoding="utf-8",
            )

            failures, _warnings = check(root, online=False, timeout=1)
            self.assertEqual(
                [
                    item
                    for item in failures
                    if item["path"] == "ordinary.md"
                    and item["code"] == "missing-link"
                ],
                [{
                    "code": "missing-link",
                    "path": "ordinary.md",
                    "message": "missing.md",
                }],
            )
            self.assertFalse(
                any(
                    "broken-route-case" in item["path"]
                    for item in failures
                )
            )

    def test_online_link_probe_is_allowlisted_pinned_and_redacted(self) -> None:
        import check_links

        public_answer = [
            (
                2,
                1,
                6,
                "",
                ("93.184.216.34", 443),
            )
        ]
        with patch.object(
            check_links.socket,
            "getaddrinfo",
            return_value=public_answer,
        ) as resolver:
            safe, reason, host, port, addresses = (
                check_links.resolve_external_target(
                    "https://example.test/reference",
                    set(),
                    {"example.test"},
                )
            )
        self.assertTrue(safe, reason)
        self.assertEqual(host, "example.test")
        self.assertEqual(port, 443)
        self.assertEqual(addresses, ("93.184.216.34",))
        resolver.assert_called_once()

        with patch.object(
            check_links,
            "resolve_external_target",
            return_value=(
                True,
                "public",
                "example.test",
                443,
                ("93.184.216.34",),
            ),
        ), patch.object(
            check_links,
            "pinned_head",
            return_value=(204, None),
        ) as pinned:
            healthy, status = check_links.external_status(
                "https://example.test/reference",
                1,
                allowed_online_hosts={"example.test"},
            )
        self.assertTrue(healthy)
        self.assertEqual(status, "204")
        self.assertEqual(
            pinned.call_args.kwargs["addresses"],
            ("93.184.216.34",),
        )

        unsafe, message = check_links.validate_external_target(
            "https://user:secret@example.test/path?token=secret",
            set(),
            {"example.test"},
        )
        self.assertFalse(unsafe)
        self.assertNotIn("secret", message)
        label = check_links.safe_url_label(
            "https://user:secret@example.test/path/token-value?token=secret"
        )
        self.assertNotIn("secret", label)
        self.assertNotIn("token-value", label)
        self.assertIn("path-redacted", label)

        with patch.object(check_links.socket, "getaddrinfo") as resolver:
            unsafe, message = check_links.validate_external_target(
                "https://not-approved.example/reference",
                set(),
                {"example.test"},
            )
        self.assertFalse(unsafe)
        self.assertEqual(message, "online host is not allowlisted")
        resolver.assert_not_called()

    def test_online_probe_allows_only_canonical_youtube_video_query(self) -> None:
        import check_links

        public_answer = [(2, 1, 6, "", ("142.250.72.206", 443))]
        with patch.object(
            check_links.socket,
            "getaddrinfo",
            return_value=public_answer,
        ):
            safe, reason, host, port, addresses = check_links.resolve_external_target(
                "https://www.youtube.com/watch?v=DNSXlBmukck",
                set(),
                {"www.youtube.com"},
            )
        self.assertTrue(safe, reason)
        self.assertEqual(host, "www.youtube.com")
        self.assertEqual(port, 443)
        self.assertEqual(addresses, ("142.250.72.206",))

        rejected = (
            "https://www.youtube.com/watch?v=too-short",
            "https://www.youtube.com/watch?v=DNSXlBmukck&token=secret",
            "https://www.youtube.com/watch?token=DNSXlBmukck",
            "https://example.test/path?value=DNSXlBmukck",
        )
        for url in rejected:
            with self.subTest(url=url):
                safe, reason = check_links.validate_external_target(
                    url,
                    set(),
                    {"www.youtube.com", "example.test"},
                )
                self.assertFalse(safe)
                self.assertEqual(reason, "query-bearing URL refused")

        class _Transport:
            def settimeout(self, _timeout: float) -> None:
                pass

            def sendall(self, payload: bytes) -> None:
                self.payload = payload

            def close(self) -> None:
                pass

        transport = _Transport()
        with patch.object(
            check_links.socket,
            "create_connection",
            return_value=transport,
        ), patch.object(
            check_links.ssl,
            "create_default_context",
        ) as context, patch.object(
            check_links.http.client,
            "HTTPResponse",
        ) as response:
            context.return_value.wrap_socket.return_value = transport
            response.return_value.getheader.return_value = None
            response.return_value.status = 204
            status, _ = check_links.pinned_head(
                "https://www.youtube.com/watch?v=DNSXlBmukck",
                hostname="www.youtube.com",
                port=443,
                addresses=("142.250.72.206",),
                timeout=1,
            )
        self.assertEqual(status, 204)
        self.assertIn(b"HEAD /watch?v=DNSXlBmukck HTTP/1.1", transport.payload)


class CachePreflightTests(unittest.TestCase):
    ENTRYPOINTS = (
        "audit_package.py",
        "attest_tests.py",
        "build_manifest.py",
        "build_sbom.py",
        "check_links.py",
        "detect_routes.py",
        "manage_install.py",
        "package_release.py",
        "run_evals.py",
        "sync_skill.py",
        "validate_evidence.py",
    )

    def test_every_entrypoint_source_preflight_blocks_local_bytecode_and_shadows(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            copied_plugin = root / "plugin"
            shutil.copytree(PLUGIN, copied_plugin)
            scripts = copied_plugin / "maintainer" / "scripts"
            common_marker = root / "common-imported.txt"
            json_marker = root / "json-imported.txt"
            pathlib_marker = root / "pathlib-imported.txt"
            argparse_marker = root / "argparse-imported.txt"

            common_source = root / "compiled-common.py"
            compile_sourceless_module(
                common_source,
                scripts / "common.pyc",
                (
                    f"open({str(common_marker)!r}, 'w', encoding='utf-8')"
                    ".write('executed')\n"
                    "raise RuntimeError('sourceless common.pyc executed')\n"
                ),
            )
            (scripts / "common.py").unlink()
            json_source = root / "compiled-json.py"
            compile_sourceless_module(
                json_source,
                scripts / "json.pyc",
                (
                    f"open({str(json_marker)!r}, 'w', encoding='utf-8')"
                    ".write('executed')\n"
                    "raise RuntimeError('local json.pyc executed')\n"
                ),
            )
            (copied_plugin / "pathlib.py").write_text(
                (
                    f"open({str(pathlib_marker)!r}, 'w', encoding='utf-8')"
                    ".write('executed')\n"
                    "raise RuntimeError('PYTHONPATH pathlib.py executed')\n"
                ),
                encoding="utf-8",
            )
            (copied_plugin / "argparse.py").write_text(
                (
                    f"open({str(argparse_marker)!r}, 'w', encoding='utf-8')"
                    ".write('executed')\n"
                    "raise RuntimeError('PYTHONPATH argparse.py executed')\n"
                ),
                encoding="utf-8",
            )

            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment["PYTHONPATH"] = "."
            for name in self.ENTRYPOINTS:
                with self.subTest(entrypoint=name):
                    flags = ["-B"]
                    if name == "attest_tests.py":
                        flags = ["-I", "-S", "-B"]
                    result = subprocess.run(
                        [
                            sys.executable,
                            *flags,
                            f"maintainer/scripts/{name}",
                        ],
                        cwd=copied_plugin,
                        text=True,
                        encoding="utf-8",
                        capture_output=True,
                        env=environment,
                        timeout=120,
                    )
                    self.assertEqual(
                        result.returncode,
                        2,
                        result.stdout + result.stderr,
                    )
                    payload = json.loads(result.stdout)
                    self.assertEqual(payload["ok"], False)
                    paths = {
                        item["path"]
                        for item in payload["failures"]
                    }
                    self.assertIn("maintainer/scripts/common.pyc", paths)
                    self.assertIn("maintainer/scripts/json.pyc", paths)
                    self.assertIn("argparse.py", paths)
                    self.assertIn("pathlib.py", paths)
                    self.assertFalse(common_marker.exists())
                    self.assertFalse(json_marker.exists())
                    self.assertFalse(pathlib_marker.exists())
                    self.assertFalse(argparse_marker.exists())

            import_probe = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    (
                        "import sys;"
                        f"sys.path.insert(0, {str(scripts)!r});"
                        "import common"
                    ),
                ],
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=environment,
                timeout=120,
            )
            self.assertNotEqual(import_probe.returncode, 0)
            self.assertTrue(
                common_marker.is_file(),
                import_probe.stdout + import_probe.stderr,
            )

    def test_every_entrypoint_rejects_untrusted_import_archives(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            copied_plugin = root / "plugin"
            shutil.copytree(PLUGIN, copied_plugin)
            archive = root / "untrusted-imports.zip"
            marker = root / "archive-imported.txt"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr(
                    "argparse.py",
                    (
                        f"open({str(marker)!r}, 'w', encoding='utf-8')"
                        ".write('executed')\n"
                        "raise RuntimeError('archive argparse.py executed')\n"
                    ),
                )

            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment["PYTHONPATH"] = str(archive)
            for name in self.ENTRYPOINTS:
                with self.subTest(entrypoint=name):
                    flags = ["-B"]
                    command_suffix: list[str] = []
                    if name == "attest_tests.py":
                        flags = ["-I", "-S", "-B"]
                        command_suffix = ["--help"]
                    result = subprocess.run(
                        [
                            sys.executable,
                            *flags,
                            f"maintainer/scripts/{name}",
                            *command_suffix,
                        ],
                        cwd=copied_plugin,
                        text=True,
                        encoding="utf-8",
                        capture_output=True,
                        env=environment,
                        timeout=120,
                    )
                    if name == "attest_tests.py":
                        # Startup isolation ignores the archive entirely; it
                        # need not discover an untrusted path after Python has
                        # already excluded it from import initialization.
                        self.assertEqual(
                            result.returncode,
                            0,
                            result.stdout + result.stderr,
                        )
                    else:
                        self.assertEqual(
                            result.returncode,
                            2,
                            result.stdout + result.stderr,
                        )
                        payload = json.loads(result.stdout)
                        self.assertTrue(
                            any(
                                item["code"] == "untrusted-import-path"
                                and Path(item["path"]) == archive
                                for item in payload["failures"]
                            ),
                            payload,
                        )
                    self.assertFalse(marker.exists())

    def test_nonimportable_name_prefixes_do_not_trigger_shadow_guard(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            copied_plugin = root / "plugin"
            shutil.copytree(PLUGIN, copied_plugin)
            (copied_plugin / "argparse.fixture.py").write_text(
                "raise RuntimeError('not importable as argparse')\n",
                encoding="utf-8",
            )
            (copied_plugin / "argparse").mkdir()

            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment["PYTHONPATH"] = "."
            for name in self.ENTRYPOINTS:
                with self.subTest(entrypoint=name):
                    flags = ["-B"]
                    if name == "attest_tests.py":
                        flags = ["-I", "-S", "-B"]
                    result = subprocess.run(
                        [
                            sys.executable,
                            *flags,
                            f"maintainer/scripts/{name}",
                            "--help",
                        ],
                        cwd=copied_plugin,
                        text=True,
                        encoding="utf-8",
                        capture_output=True,
                        env=environment,
                        timeout=120,
                    )
                    self.assertEqual(
                        result.returncode,
                        0,
                        result.stdout + result.stderr,
                    )


class SyncTests(unittest.TestCase):
    def test_sync_parity_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, discovery, backups = root / "source", root / "skills", root / "backups"
            minimal_skill(source)
            discovery.mkdir()
            backups.mkdir()
            target = discovery / "design-dna"
            minimal_skill(target, "old")
            failed = run_script(
                "sync_skill.py", "--source", str(source), "--target", str(target),
                "--discovery-root", str(discovery), "--backup-root", str(backups),
                "--replace", "--simulate-final-move-failure",
            )
            self.assertEqual(failed.returncode, 2, failed.stdout + failed.stderr)
            self.assertEqual(
                (target / "SKILL.md").read_text(encoding="utf-8"),
                minimal_skill_text("old"),
            )
            success = run_script(
                "sync_skill.py", "--source", str(source), "--target", str(target),
                "--discovery-root", str(discovery), "--backup-root", str(backups), "--replace",
            )
            self.assertEqual(success.returncode, 0, success.stdout + success.stderr)
            check = run_script(
                "sync_skill.py", "--source", str(source), "--target", str(target),
                "--discovery-root", str(discovery), "--backup-root", str(backups), "--check",
            )
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            self.assertTrue(json.loads(check.stdout)["ok"])

    def test_cleanup_failure_after_success_emits_one_truthful_document(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            discovery = root / "skills"
            backups = root / "backups"
            minimal_skill(source)
            discovery.mkdir()
            backups.mkdir()
            target = discovery / "design-dna"
            result = run_script(
                "sync_skill.py",
                "--source",
                str(source),
                "--target",
                str(target),
                "--discovery-root",
                str(discovery),
                "--backup-root",
                str(backups),
                "--simulate-cleanup-failure",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["installed"])
            self.assertTrue(target.is_dir())
            self.assertIn(
                "staging-cleanup-incomplete",
                {item["code"] for item in payload["warnings"]},
            )
            self.assertNotIn("Traceback", result.stderr)
            self.assertTrue(Path(payload["staging_path"]).is_dir())

    def test_cleanup_failure_after_primary_failure_preserves_one_error_document(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            discovery = root / "skills"
            backups = root / "backups"
            minimal_skill(source)
            discovery.mkdir()
            backups.mkdir()
            target = discovery / "design-dna"
            minimal_skill(target, "old")
            result = run_script(
                "sync_skill.py",
                "--source",
                str(source),
                "--target",
                str(target),
                "--discovery-root",
                str(discovery),
                "--backup-root",
                str(backups),
                "--replace",
                "--simulate-final-move-failure",
                "--simulate-cleanup-failure",
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertFalse(payload["installed"])
            self.assertIn("staging residue", payload["failures"][0]["message"])
            self.assertEqual(
                (target / "SKILL.md").read_text(encoding="utf-8"),
                minimal_skill_text("old"),
            )
            self.assertNotIn("Traceback", result.stderr)

    def test_internal_link_attack_is_rejected_when_links_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, discovery, backups, outside = root / "source", root / "skills", root / "backups", root / "outside"
            minimal_skill(source)
            discovery.mkdir()
            backups.mkdir()
            outside.mkdir()
            (outside / "secret.txt").write_text("secret", encoding="utf-8")
            link = source / "escape"
            if not make_directory_link(link, outside):
                self.skipTest("directory symlink/junction unavailable")
            try:
                result = run_script(
                    "sync_skill.py", "--source", str(source), "--target", str(discovery / "design-dna"),
                    "--discovery-root", str(discovery), "--backup-root", str(backups),
                )
                self.assertEqual(result.returncode, 2)
                self.assertFalse((discovery / "design-dna").exists())
            finally:
                if link.exists():
                    os.rmdir(link)


@unittest.skipUnless(
    __import__("importlib").util.find_spec("yaml") and __import__("importlib").util.find_spec("jsonschema"),
    "maintainer dependencies are not installed",
)
class AuditMutationTests(unittest.TestCase):
    def test_plugin_exposes_exactly_one_design_dna_skill(self) -> None:
        from audit_package import plugin_skill_surface_failures

        self.assertEqual(plugin_skill_surface_failures(PLUGIN), [])
        with tempfile.TemporaryDirectory() as temporary:
            copied_plugin = Path(temporary) / "plugin"
            shutil.copytree(PLUGIN, copied_plugin)
            extra = copied_plugin / "skills" / "design-dna-copy"
            extra.mkdir()
            (extra / "SKILL.md").write_text(
                "---\n"
                "name: design-dna-copy\n"
                "description: Test-only accidental second skill.\n"
                "---\n",
                encoding="utf-8",
            )
            failures = plugin_skill_surface_failures(copied_plugin)
            self.assertEqual(
                ["plugin-skill-surface-invalid"],
                [item["code"] for item in failures],
            )
            self.assertIn(
                "skills/design-dna-copy/SKILL.md",
                failures[0]["message"],
            )

    def test_runtime_references_are_directly_reachable_from_router(self) -> None:
        from audit_package import runtime_reference_reachability_failures

        source_skill = PLUGIN / "skills" / "design-dna"
        self.assertEqual(
            runtime_reference_reachability_failures(
                source_skill,
                label_root=PLUGIN,
            ),
            [],
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied_skill = Path(temporary) / "design-dna"
            shutil.copytree(source_skill, copied_skill)
            orphan = copied_skill / "references" / "orphan.md"
            orphan.write_text("# Orphan\n", encoding="utf-8")
            failures = runtime_reference_reachability_failures(copied_skill)
            self.assertEqual(len(failures), 1)
            self.assertEqual(
                failures[0]["code"],
                "runtime-reference-unreachable",
            )
            self.assertTrue(failures[0]["path"].endswith("orphan.md"))

    def test_stale_package_identity_does_not_hide_later_release_diagnostics(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            copied_plugin = root / "plugin"
            shutil.copytree(PLUGIN, copied_plugin)
            skill_path = copied_plugin / "skills" / "design-dna" / "SKILL.md"
            skill_path.write_text(
                skill_path.read_text(encoding="utf-8")
                + "\n<!-- test-only package identity drift -->\n",
                encoding="utf-8",
            )
            test_attestation = (
                copied_plugin
                / "maintainer"
                / "attestations"
                / "test-attestation.json"
            )
            if test_attestation.exists():
                test_attestation.unlink()

            result = run_script(
                "audit_package.py",
                "--plugin-root",
                str(copied_plugin),
                "--home",
                str(root),
                "--release",
            )
            self.assertEqual(
                result.returncode,
                1,
                result.stdout + result.stderr,
            )
            self.assertTrue(result.stdout, result.stderr)
            payload = json.loads(result.stdout)
            codes = {item["code"] for item in payload["failures"]}
            self.assertTrue(
                {"sbom-runtime-identity-mismatch", "sbom-drift"} & codes,
                codes,
            )
            self.assertIn("release-manifest-identity-unavailable", codes)
            self.assertIn("release-test-attestation-missing", codes)

    def test_missing_release_manifest_reports_recorded_identity_gap(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            copied_plugin = root / "plugin"
            shutil.copytree(
                PLUGIN,
                copied_plugin,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
            sbom_path = copied_plugin / "maintainer" / "sbom.spdx.json"
            generated_sbom = run_script(
                "build_sbom.py",
                "--plugin-root",
                str(copied_plugin),
                "--output",
                str(sbom_path),
            )
            self.assertEqual(
                generated_sbom.returncode,
                0,
                generated_sbom.stdout + generated_sbom.stderr,
            )
            manifest_path = copied_plugin / "maintainer" / "release-manifest.json"
            generated = run_script(
                "build_manifest.py",
                "--skill-root",
                str(copied_plugin / "skills" / "design-dna"),
                "--output",
                str(manifest_path),
            )
            self.assertEqual(
                generated.returncode,
                0,
                generated.stdout + generated.stderr,
            )
            self.assertTrue(manifest_path.is_file())
            manifest_path.unlink()

            common_args = (
                "audit_package.py",
                "--plugin-root",
                str(copied_plugin),
                "--home",
                str(root),
            )
            development = run_script(*common_args)
            development_payload = json.loads(development.stdout)
            expected = {
                "release-manifest-missing",
                "release-manifest-identity-unavailable",
            }
            self.assertTrue(
                expected
                <= {item["code"] for item in development_payload["warnings"]},
                development_payload,
            )

            release = run_script(*common_args, "--release")
            self.assertNotEqual(release.returncode, 0, release.stdout + release.stderr)
            release_payload = json.loads(release.stdout)
            self.assertTrue(
                expected
                <= {item["code"] for item in release_payload["failures"]},
                release_payload,
            )

    def test_owner_policy_example_matches_active_policy_schema(self) -> None:
        from audit_package import owner_policy_example_failures

        example = (
            PLUGIN
            / "skills"
            / "design-dna"
            / "templates"
            / "owner-policy.example.yml"
        )
        schema = PLUGIN / "maintainer" / "schemas" / "owner-policy.schema.json"
        self.assertEqual(owner_policy_example_failures(example, schema), [])
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "owner-policy.example.yml"
            text = example.read_text(encoding="utf-8").replace(
                '  visible_ambition: "require-review"\n',
                '  visible_ambition: "bananas"\n',
                1,
            )
            mutated.write_text(text, encoding="utf-8")
            failures = owner_policy_example_failures(mutated, schema)
            self.assertIn(
                "schema-invalid",
                {item["code"] for item in failures},
            )

    def test_release_identity_excludes_but_rejects_executable_bytecode(self) -> None:
        from audit_package import (
            maintainer_cache_failures,
            runtime_cache_failures,
        )
        from build_manifest import (
            identity_group_sha256,
            package_manifest,
        )

        with tempfile.TemporaryDirectory() as temporary:
            copied_plugin = Path(temporary) / "plugin"
            shutil.copytree(PLUGIN, copied_plugin)
            skill_root = copied_plugin / "skills" / "design-dna"
            scripts_root = copied_plugin / "maintainer" / "scripts"
            tests_root = copied_plugin / "maintainer" / "tests"
            baseline_manifest = package_manifest(skill_root)
            baseline_runtime = content_manifest(skill_root)
            baseline_tooling = identity_group_sha256(
                copied_plugin,
                ("maintainer/scripts",),
            )
            baseline_tests = identity_group_sha256(
                copied_plugin,
                ("maintainer/tests",),
            )

            runtime_cache = skill_root / "scripts" / "__pycache__"
            runtime_cache.mkdir()
            (runtime_cache / "runtime.pyc").write_bytes(b"runtime")
            tooling_cache = scripts_root / "__pycache__"
            tooling_cache.mkdir()
            (tooling_cache / "tooling.pyc").write_bytes(b"tooling")
            test_bytecode = tests_root / "unhashed-test.pyo"
            test_bytecode.write_bytes(b"tests")

            self.assertEqual(content_manifest(skill_root), baseline_runtime)
            self.assertEqual(
                identity_group_sha256(
                    copied_plugin,
                    ("maintainer/scripts",),
                ),
                baseline_tooling,
            )
            self.assertEqual(
                identity_group_sha256(
                    copied_plugin,
                    ("maintainer/tests",),
                ),
                baseline_tests,
            )
            self.assertEqual(
                {
                    item["path"]
                    for item in runtime_cache_failures(
                        skill_root,
                        label_root=copied_plugin,
                    )
                },
                {"skills/design-dna/scripts/__pycache__"},
            )
            self.assertEqual(
                {
                    item["path"]
                    for item in maintainer_cache_failures(copied_plugin)
                },
                {
                    "maintainer/scripts/__pycache__",
                    "maintainer/tests/unhashed-test.pyo",
                },
            )

            direct_audit = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(scripts_root / "audit_package.py"),
                    "--plugin-root",
                    str(copied_plugin),
                ],
                text=True,
                encoding="utf-8",
                capture_output=True,
                env={
                    **os.environ,
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                timeout=120,
            )
            self.assertEqual(
                direct_audit.returncode,
                2,
                direct_audit.stdout + direct_audit.stderr,
            )
            audit_failures = json.loads(direct_audit.stdout)["failures"]
            self.assertEqual(
                {
                    item["path"]
                    for item in audit_failures
                },
                {
                    "skills/design-dna/scripts/__pycache__",
                    "maintainer/scripts/__pycache__",
                    "maintainer/tests/unhashed-test.pyo",
                },
            )
            self.assertEqual(
                {item["code"] for item in audit_failures},
                {
                    "runtime-cache-residue",
                    "maintainer-cache-residue",
                },
            )

            with self.assertRaises(ToolFailure) as runtime_rejected:
                package_manifest(skill_root)
            self.assertEqual(
                runtime_rejected.exception.issue.code,
                "release-compiled-python-residue",
            )
            self.assertEqual(
                Path(runtime_rejected.exception.issue.path),
                runtime_cache,
            )
            shutil.rmtree(runtime_cache)

            with self.assertRaises(ToolFailure) as tooling_rejected:
                package_manifest(skill_root)
            self.assertEqual(
                Path(tooling_rejected.exception.issue.path),
                tooling_cache,
            )
            shutil.rmtree(tooling_cache)

            with self.assertRaises(ToolFailure) as tests_rejected:
                package_manifest(skill_root)
            self.assertEqual(
                Path(tests_rejected.exception.issue.path),
                test_bytecode,
            )
            test_bytecode.unlink()
            self.assertEqual(
                package_manifest(skill_root)["release_sha256"],
                baseline_manifest["release_sha256"],
            )

    def test_every_release_proof_component_changes_release_identity(self) -> None:
        from build_manifest import package_manifest

        with tempfile.TemporaryDirectory() as temporary:
            copied_plugin = Path(temporary) / "plugin"
            def ignore_derived_archives(
                directory: str,
                _names: list[str],
            ) -> set[str]:
                relative = Path(directory).resolve().relative_to(
                    PLUGIN.resolve()
                ).as_posix()
                if relative in {
                    "maintainer/evals",
                    "maintainer/compatibility",
                }:
                    return {"archive"}
                return set()

            shutil.copytree(
                PLUGIN,
                copied_plugin,
                ignore=ignore_derived_archives,
            )
            skill_root = copied_plugin / "skills" / "design-dna"
            # Release identity deliberately retains archival evaluation and
            # compatibility outcomes, while test attestation deliberately
            # excludes those generated outputs to avoid a circular record.
            # Synthesize the two archive probes in this isolated fixture so
            # this release-identity unit test does not make current archived
            # outcomes an implicit input to the combined release test suite.
            archived_eval = (
                copied_plugin
                / "maintainer"
                / "evals"
                / "archive"
                / "codex-coffee-regression-20260726"
                / "README.md"
            )
            self.assertFalse(archived_eval.parent.exists())
            archived_eval.parent.mkdir(parents=True, exist_ok=True)
            archived_eval.write_text(
                "synthetic retained evaluation outcome\n",
                encoding="utf-8",
            )
            archived_compatibility = (
                copied_plugin
                / "maintainer"
                / "compatibility"
                / "archive"
                / "verification-2026-07-26.md"
            )
            self.assertFalse(archived_compatibility.parent.exists())
            archived_compatibility.parent.mkdir(parents=True, exist_ok=True)
            archived_compatibility.write_text(
                "synthetic retained compatibility outcome\n",
                encoding="utf-8",
            )
            baseline = package_manifest(skill_root)
            mutations = {
                "maintainer_tooling": "maintainer/scripts/audit_package.py",
                "schemas": "maintainer/schemas/manifest.schema.json",
                "tests": "maintainer/tests/test_regression_edges.py",
                "eval_contract": "maintainer/evals/fixtures/behavioral-cases.json",
                "evidence": "maintainer/evidence/index.yml",
                "eval_proof": (
                    "maintainer/evals/archive/"
                    "codex-coffee-regression-20260726/README.md"
                ),
                "compatibility_verification": (
                    "maintainer/compatibility/archive/verification-2026-07-26.md"
                ),
                "distribution_docs": "README.md",
            }
            for component, relative in mutations.items():
                target = copied_plugin / relative
                original = target.read_bytes()
                try:
                    target.write_bytes(original + b"\nrelease identity mutation\n")
                    changed = package_manifest(skill_root)
                    self.assertNotEqual(
                        changed["release_sha256"],
                        baseline["release_sha256"],
                        relative,
                    )
                    self.assertNotEqual(
                        changed["components"][component],
                        baseline["components"][component],
                        relative,
                    )
                finally:
                    target.write_bytes(original)
            generated_proof = (
                copied_plugin
                / "maintainer"
                / "evals"
                / "results"
                / "compiled-proof"
                / "__pycache__"
                / "evidence.pyc"
            )
            generated_proof.parent.mkdir(parents=True)
            generated_proof.write_bytes(b"retained evaluation evidence")
            compiled = package_manifest(skill_root)
            self.assertNotEqual(
                compiled["components"]["eval_proof"],
                baseline["components"]["eval_proof"],
            )
            self.assertNotEqual(
                compiled["release_sha256"],
                baseline["release_sha256"],
            )

    def test_unclassified_top_level_file_is_bound_by_distribution_identity(
        self,
    ) -> None:
        from build_manifest import package_manifest

        with tempfile.TemporaryDirectory() as temporary:
            copied_plugin = Path(temporary) / "plugin"
            shutil.copytree(PLUGIN, copied_plugin)
            skill_root = copied_plugin / "skills" / "design-dna"
            baseline = package_manifest(skill_root)
            added = copied_plugin / "UNCLASSIFIED-DELIVERY-NOTE.txt"
            added.write_text(
                "This file must not fall outside release identity.\n",
                encoding="utf-8",
            )
            changed = package_manifest(skill_root)
            self.assertNotEqual(
                changed["components"]["distribution_tree"],
                baseline["components"]["distribution_tree"],
            )
            self.assertNotEqual(
                changed["release_sha256"],
                baseline["release_sha256"],
            )
            self.assertIn(
                "UNCLASSIFIED-DELIVERY-NOTE.txt",
                {
                    item["path"]
                    for item in changed["distribution_files"]
                    if item["type"] == "file"
                },
            )

    def test_trusted_adapter_registry_edit_invalidates_release_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied_plugin = Path(temporary) / "plugin"
            shutil.copytree(PLUGIN, copied_plugin)
            skill_root = copied_plugin / "skills" / "design-dna"
            manifest_path = copied_plugin / "maintainer" / "release-manifest.json"
            generated = run_script(
                "build_manifest.py",
                "--skill-root",
                str(skill_root),
                "--output",
                str(manifest_path),
            )
            self.assertEqual(
                generated.returncode,
                0,
                generated.stdout + generated.stderr,
            )
            registry = (
                copied_plugin
                / "maintainer"
                / "compatibility"
                / "trusted-host-adapters.yml"
            )
            registry.write_text(
                registry.read_text(encoding="utf-8") + "\n# owner review marker\n",
                encoding="utf-8",
            )
            checked = run_script(
                "build_manifest.py",
                "--skill-root",
                str(skill_root),
                "--output",
                str(manifest_path),
                "--check",
            )
            self.assertEqual(
                checked.returncode,
                1,
                checked.stdout + checked.stderr,
            )
            codes = {
                item["code"]
                for item in json.loads(checked.stdout)["failures"]
            }
            self.assertIn("manifest-drift", codes)

    def test_fixture_schema_accepts_complete_case_and_rejects_unknown_fields(self) -> None:
        from jsonschema import Draft202012Validator

        schema = json.loads(
            (PLUGIN / "maintainer" / "evals" / "schema.json").read_text(
                encoding="utf-8"
            )
        )
        valid = {
            "schema_version": 3,
            "suite": "schema-contract",
            "skill_instructions": {
                "codex": (
                    "Use $design-dna for this task and follow its required verification."
                ),
                "claude_code": (
                    "Use /design-dna for this task and follow its required verification."
                ),
            },
            "cases": [{
                "id": "coffee-specificity",
                "installation_mode": "direct-skill",
                "task": (
                    "Create a current, specific coffee-shop website from the supplied facts."
                ),
                "timeout_seconds": 300,
                "tags": ["persuade", "hospitality"],
                "capability_contract": {
                    "image_generation": "required-when-host-declared-available"
                },
                "release_coverage": {
                    "high_value": True,
                    "representative": True,
                    "primary_mode": "persuade",
                    "scope": "new-build",
                    "project_stratum": "static-site",
                    "expressive_perception_gate": True,
                },
                "review_requirements": [
                    "Review the rendered result at all declared viewports."
                ],
                "expected": {"exit_codes": [0], "files_exist": ["index.html"]},
            }],
        }
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(valid)), [])
        invalid = json.loads(json.dumps(valid))
        invalid["cases"][0]["unknown"] = True
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(invalid)))
        invalid_suite = json.loads(json.dumps(valid))
        invalid_suite["suite"] = "../escaped"
        self.assertTrue(
            list(Draft202012Validator(schema).iter_errors(invalid_suite)),
            "suite identifiers must be safe filename slugs",
        )
        missing_host = json.loads(json.dumps(valid))
        del missing_host["skill_instructions"]["claude_code"]
        self.assertTrue(
            list(Draft202012Validator(schema).iter_errors(missing_host)),
            "every supported host needs an explicit invocation instruction",
        )
        swapped_syntax = json.loads(json.dumps(valid))
        swapped_syntax["skill_instructions"]["claude_code"] = (
            "Use $design-dna for this Claude Code task."
        )
        self.assertTrue(
            list(Draft202012Validator(schema).iter_errors(swapped_syntax)),
            "Claude Code fixtures must use the documented slash invocation",
        )
        invalid_installation = json.loads(json.dumps(valid))
        invalid_installation["cases"][0]["installation_mode"] = "plugin-ish"
        self.assertTrue(
            list(
                Draft202012Validator(schema).iter_errors(
                    invalid_installation
                )
            ),
            "installation mode must distinguish the two declared route types",
        )
        invalid_gate = json.loads(json.dumps(valid))
        invalid_gate["cases"][0]["release_coverage"][
            "expressive_perception_gate"
        ] = False
        self.assertTrue(
            list(Draft202012Validator(schema).iter_errors(invalid_gate)),
            "the opt-in expressive release marker cannot be weakened to false",
        )
        conflicting_quiet = json.loads(json.dumps(valid))
        conflicting_quiet["cases"][0]["release_coverage"][
            "quiet_perception_gate"
        ] = True
        self.assertTrue(
            list(Draft202012Validator(schema).iter_errors(conflicting_quiet)),
            "quiet-specific and expressive score gates must not be conflated",
        )
        generated_gate = json.loads(json.dumps(valid))
        generated_gate["cases"][0]["release_coverage"][
            "generated_media_capability_gate"
        ] = True
        self.assertEqual(
            list(Draft202012Validator(schema).iter_errors(generated_gate)),
            [],
        )
        del generated_gate["cases"][0]["capability_contract"]
        self.assertTrue(
            list(Draft202012Validator(schema).iter_errors(generated_gate)),
            "a generated-media release gate needs a conditional capability contract",
        )

    def test_duplicate_fixture_ids_fail(self) -> None:
        from audit_package import validate_fixtures

        with tempfile.TemporaryDirectory() as temporary:
            fixture_dir = Path(temporary)
            payload = {
                "schema_version": 3,
                "suite": "duplicate-test",
                "skill_instructions": {
                    "codex": (
                        "Use $design-dna for this task and follow its required verification."
                    ),
                    "claude_code": (
                        "Use /design-dna for this task and follow its required verification."
                    ),
                },
                "cases": [{
                    "id": "same-case",
                    "task": "Create a deliberately specific interface for this evaluation.",
                    "review_requirements": [
                        "Inspect the exact rendered output before recording a conclusion."
                    ],
                }],
            }
            (fixture_dir / "one.json").write_text(json.dumps(payload), encoding="utf-8")
            (fixture_dir / "two.json").write_text(json.dumps(payload), encoding="utf-8")
            failures, count = validate_fixtures(
                fixture_dir, PLUGIN / "maintainer" / "evals" / "schema.json"
            )
            self.assertEqual(count, 2)
            self.assertTrue(
                any(item["code"] == "duplicate-fixture-id" for item in failures)
            )

    def test_retired_evidence_cannot_authorize_a_risk(self) -> None:
        from validate_evidence import validate

        with tempfile.TemporaryDirectory() as temporary:
            plugin = Path(temporary)
            evidence = plugin / "maintainer" / "evidence" / "cards"
            evidence.mkdir(parents=True)
            (plugin / "maintainer" / "evidence" / "index.yml").write_text(
                "schema_version: 2\nowner: Motty\nlast_reviewed: '2026-07-20'\n"
                "next_review: '2026-10-20'\nrisks:\n  RISK-TEST-1:\n"
                "    status: active\n    evidence: [EVD-001]\nrejected_hypotheses: {}\n",
                encoding="utf-8",
            )
            body = "\n".join(f"## {heading}\nRISK-TEST-1\n" for heading in (
                "Claim", "Observation", "Scope and limitations", "Counterexamples",
                "Positive action", "Supports", "Validation", "Retention",
            ))
            (evidence / "EVD-001.md").write_text(
                "---\nschema_version: 2\nid: EVD-001\nstatus: retired\nclassification: public\n"
                "source_type: research\nowner: Motty\npublisher: Example Research\n"
                "created: 2026-01-01\nlast_reviewed: 2026-07-20\n"
                "next_review: 2026-10-20\nretrieved: 2026-07-20\nurl: https://example.com\n"
                "locator: section 1\nconfidence: high\n---\n" + body,
                encoding="utf-8",
            )
            failures, _, _ = validate(
                plugin, PLUGIN / "maintainer" / "schemas" / "evidence-frontmatter.schema.json",
                online=False, strict_due=False,
            )
            self.assertTrue(
                any(
                    item["code"] == "inactive-evidence-authorizes-risk"
                    for item in failures
                )
            )

    def test_evidence_review_interval_has_no_universal_day_ceiling(self) -> None:
        from validate_evidence import validate

        with tempfile.TemporaryDirectory() as temporary:
            plugin = Path(temporary)
            evidence = plugin / "maintainer" / "evidence" / "cards"
            evidence.mkdir(parents=True)
            (plugin / "maintainer" / "evidence" / "index.yml").write_text(
                "schema_version: 2\nowner: Motty\nlast_reviewed: '2026-07-20'\n"
                "next_review: '2028-07-20'\nrisks:\n  RISK-TEST-1:\n"
                "    status: active\n    evidence: [EVD-001]\nrejected_hypotheses: {}\n",
                encoding="utf-8",
            )
            body = "\n".join(
                f"## {heading}\nRISK-TEST-1 remains project-specific.\n"
                for heading in (
                    "Claim",
                    "Observation",
                    "Scope and limitations",
                    "Counterexamples",
                    "Positive action",
                    "Supports",
                    "Validation",
                    "Retention",
                )
            )
            (evidence / "EVD-001.md").write_text(
                "---\nschema_version: 2\nid: EVD-001\nstatus: active\nclassification: public\n"
                "source_type: research\nowner: Motty\npublisher: Example Research\n"
                "created: 2026-01-01\nlast_reviewed: 2026-07-20\n"
                "next_review: 2028-07-20\nretrieved: 2026-07-20\nurl: https://example.com\n"
                "locator: section 1\nconfidence: high\n---\n" + body,
                encoding="utf-8",
            )
            failures, _, _ = validate(
                plugin,
                PLUGIN
                / "maintainer"
                / "schemas"
                / "evidence-frontmatter.schema.json",
                online=False,
                strict_due=False,
            )
            self.assertFalse(
                any(
                    item["code"]
                    in {"invalid-index-review-interval", "invalid-review-interval"}
                    for item in failures
                ),
                failures,
            )

@unittest.skipUnless(
    __import__("importlib").util.find_spec("jsonschema"),
    "maintainer dependencies are not installed",
)
class EvalRunnerV3Tests(unittest.TestCase):
    def test_exact_skill_staging_baseline_isolation_and_semantic_result(self) -> None:
        from audit_package import eval_semantic_failures, fixture_catalog
        from jsonschema import Draft202012Validator, FormatChecker

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = "Create a deterministic artifact while checking the isolated host route."
            fixture = write_eval_suite(
                root,
                suite="staging-contract",
                task=task,
                expected={
                    "exit_codes": [0],
                    "stdout_contains": ["route-ok"],
                    "files_exist": ["artifact.txt"],
                },
            )
            code = "\n".join([
                "import json, os",
                "from pathlib import Path",
                "request = json.loads(Path(os.environ['DESIGN_DNA_EVAL_REQUEST']).read_text(encoding='utf-8'))",
                "home = Path(request['home'])",
                "route = home / '.agents' / 'skills' / 'design-dna'",
                "assert Path.cwd() == Path(request['workspace'])",
                "assert os.environ['HOME'] == str(home)",
                "assert os.environ['USERPROFILE'] == str(home)",
                "if request['variant'] == 'skill':",
                "    assert Path(request['skill_root']) == route",
                "    assert os.environ['DESIGN_DNA_SKILL_ROOT'] == str(route)",
                "    assert os.environ['DESIGN_DNA_SKILL_ENABLED'] == '1'",
                "    assert request['skill_content_sha256']",
                "    assert (route / 'SKILL.md').is_file()",
                "else:",
                "    assert request['skill_root'] is None",
                "    assert os.environ['DESIGN_DNA_SKILL_ROOT'] == ''",
                "    assert os.environ['DESIGN_DNA_SKILL_ENABLED'] == '0'",
                "    assert not route.exists()",
                "attestation = {",
                "    'schema_version': 1,",
                "    'host': request['host'],",
                "    'case': request['case'],",
                "    'variant': request['variant'],",
                "    'run': request['run'],",
                "    'skill_loaded': request['variant'] == 'skill',",
                "    'skill_content_sha256': request['skill_content_sha256'],",
                "    'driver_name': 'test-driver',",
                "    'driver_version': '1.0.0',",
                "}",
                "Path(os.environ['DESIGN_DNA_DRIVER_REPORT']).write_text(json.dumps(attestation), encoding='utf-8')",
                "Path('artifact.txt').write_text(request['variant'], encoding='utf-8')",
                "print('route-ok')",
            ])
            result = run_eval(
                root,
                fixture,
                code,
                baseline_code=code,
                require_driver_report=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload, result_path = load_only_result(root / "results")

            result_schema = json.loads(
                (PLUGIN / "maintainer" / "schemas" / "eval-result.schema.json")
                .read_text(encoding="utf-8")
            )
            errors = list(
                Draft202012Validator(
                    result_schema, format_checker=FormatChecker()
                ).iter_errors(payload)
            )
            self.assertEqual(errors, [], [error.message for error in errors])

            runs = payload["runs"]
            self.assertEqual(len(runs), 2)
            passed = sum(bool(run["passed"]) for run in runs)
            self.assertEqual(payload["summary"]["total"], len(runs))
            self.assertEqual(payload["summary"]["passed"], passed)
            self.assertEqual(payload["summary"]["failed"], len(runs) - passed)
            expected_task_hash = hashlib.sha256(task.encode("utf-8")).hexdigest()
            by_variant = {run["variant"]: run for run in runs}
            self.assertEqual(
                {run["task_sha256"] for run in runs}, {expected_task_hash}
            )
            self.assertTrue(by_variant["skill"]["skill_staged"])
            self.assertFalse(by_variant["baseline"]["skill_staged"])
            self.assertEqual(
                {
                    run["driver_report_status"]
                    for run in runs
                },
                {"driver_reported"},
            )
            self.assertIsNone(by_variant["baseline"]["skill_content_sha256"])
            _, canonical_hash = content_manifest(
                PLUGIN / "skills" / "design-dna"
            )
            self.assertEqual(payload["package"]["content_sha256"], canonical_hash)
            self.assertEqual(
                by_variant["skill"]["skill_content_sha256"], canonical_hash
            )
            self.assertNotEqual(
                by_variant["skill"]["prompt_sha256"],
                by_variant["baseline"]["prompt_sha256"],
            )
            self.assertEqual(
                payload["summary"]["by_variant"],
                {
                    "skill": {"total": 1, "passed": 1, "failed": 0},
                    "baseline": {"total": 1, "passed": 1, "failed": 0},
                },
            )

            catalog, catalog_failures = fixture_catalog(root)
            self.assertEqual(catalog_failures, [])
            semantic_arguments = {
                "harness_path": SCRIPTS / "run_evals.py",
                "suite_schema_path": (
                    PLUGIN / "maintainer" / "evals" / "schema.json"
                ),
                "result_schema_path": (
                    PLUGIN
                    / "maintainer"
                    / "schemas"
                    / "eval-result.schema.json"
                ),
                "result_path": result_path,
            }
            self.assertEqual(
                eval_semantic_failures(
                    payload,
                    catalog,
                    "generated-result",
                    **semantic_arguments,
                ),
                [],
            )
            semantic_mutations = {
                "eval-summary-inconsistent": lambda item: item["summary"].update(
                    {"total": item["summary"]["total"] + 1}
                ),
                "eval-execution-order-inconsistent": lambda item: item[
                    "provenance"
                ].update({
                    "execution_order": list(
                        reversed(item["provenance"]["execution_order"])
                    )
                }),
                "eval-task-hash-inconsistent": lambda item: item["runs"][0].update(
                    {"task_sha256": "0" * 64}
                ),
                "eval-duplicate-run-identity": lambda item: item["runs"][1].update({
                    "case": item["runs"][0]["case"],
                    "variant": item["runs"][0]["variant"],
                    "run": item["runs"][0]["run"],
                }),
                "eval-workspace-entry-count-inconsistent": lambda item: item[
                    "runs"
                ][0].update({
                    "workspace_entry_count": (
                        item["runs"][0]["workspace_entry_count"] + 1
                    )
                }),
                "eval-input-snapshot-limit-inconsistent": lambda item: list(
                    item["provenance"]["input_snapshots"].values()
                )[0].update({
                    "entry_count": (
                        item["provenance"]["workspace_limits"]["max_entries"]
                        + 1
                    )
                }),
            }
            for expected_code, mutate in semantic_mutations.items():
                with self.subTest(semantic_mutation=expected_code):
                    mutated = json.loads(json.dumps(payload))
                    mutate(mutated)
                    codes = {
                        failure["code"]
                        for failure in eval_semantic_failures(
                            mutated,
                            catalog,
                            "mutated-result",
                            **semantic_arguments,
                        )
                    }
                    self.assertIn(expected_code, codes)

            unsafe_result = json.loads(json.dumps(payload))
            unsafe_result["suite"] = "../escaped"
            self.assertTrue(
                list(
                    Draft202012Validator(
                        result_schema, format_checker=FormatChecker()
                    ).iter_errors(unsafe_result)
                ),
                "persisted result suite identifiers must remain safe filename slugs",
            )
            inconsistent_pass = json.loads(json.dumps(payload))
            inconsistent_pass["runs"][0]["problems"] = ["hidden failure"]
            self.assertTrue(
                list(
                    Draft202012Validator(
                        result_schema, format_checker=FormatChecker()
                    ).iter_errors(inconsistent_pass)
                ),
                "a passing result cannot contain a hidden run problem",
            )
            inconsistent_staging = json.loads(json.dumps(payload))
            baseline = next(
                run
                for run in inconsistent_staging["runs"]
                if run["variant"] == "baseline"
            )
            baseline["skill_staged"] = True
            self.assertTrue(
                list(
                    Draft202012Validator(
                        result_schema, format_checker=FormatChecker()
                    ).iter_errors(inconsistent_staging)
                ),
                "baseline results cannot claim that the skill was staged",
            )

    def test_claude_host_stages_only_the_claude_discovery_route(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = write_eval_suite(root, suite="claude-route")
            code = "\n".join([
                "import json, os",
                "from pathlib import Path",
                "request = json.loads(Path(os.environ['DESIGN_DNA_EVAL_REQUEST']).read_text(encoding='utf-8'))",
                "home = Path(request['home'])",
                "expected = home / '.claude' / 'skills' / 'design-dna'",
                "duplicate = home / '.agents' / 'skills' / 'design-dna'",
                "assert request['host'] == 'claude_code'",
                "assert Path(request['skill_root']) == expected",
                "assert expected.joinpath('SKILL.md').is_file()",
                "assert not duplicate.exists()",
            ])
            result = run_eval(root, fixture, code, host="claude_code")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload, _ = load_only_result(root / "results")
            self.assertEqual(payload["host"], "claude_code")
            self.assertTrue(payload["runs"][0]["skill_route_verified_after"])

    def test_minimal_environment_does_not_inherit_secret_canary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canary_name = "DESIGN_DNA_PARENT_SECRET_CANARY"
            canary_value = "never-copy-this-secret-7fe92d"
            fixture = write_eval_suite(
                root,
                suite="environment-isolation",
                expected={
                    "exit_codes": [0],
                    "stdout_contains": ["environment-clean"],
                },
            )
            code = "\n".join([
                "import os",
                f"assert {canary_name!r} not in os.environ",
                "print('environment-clean')",
            ])
            result = run_eval(
                root,
                fixture,
                code,
                environment_overrides={canary_name: canary_value},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload, result_path = load_only_result(root / "results")
            self.assertEqual(
                payload["provenance"]["passed_environment_names"], []
            )
            self.assertNotIn(
                canary_value, result_path.read_text(encoding="utf-8")
            )

    def test_passed_environment_leak_blocks_promotion_and_retention(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work = root / "work"
            canary_name = "DESIGN_DNA_EVAL_TEST_CREDENTIAL"
            canary_value = "eval-secret-canary-bf1d7a6219"
            fixture = write_eval_suite(
                root,
                suite="passed-environment-leak",
                expected={
                    "exit_codes": [0],
                    "files_exist": ["leaked.txt"],
                },
            )
            code = "\n".join([
                "import os",
                "from pathlib import Path",
                f"value = os.environ[{canary_name!r}]",
                "Path('leaked.txt').write_text(value, encoding='utf-8')",
                "print(value)",
            ])
            result = run_eval(
                root,
                fixture,
                code,
                keep_workspaces=True,
                pass_env=(canary_name,),
                environment_overrides={canary_name: canary_value},
                work_root=work,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload, result_path = load_only_result(root / "results")
            run = payload["runs"][0]
            scan = run["sensitive_artifact_scan"]
            self.assertTrue(scan["performed"])
            self.assertTrue(scan["complete"])
            self.assertTrue(scan["detected"])
            self.assertGreaterEqual(scan["finding_count"], 1)
            self.assertIsNone(run["artifact_bundle"])
            self.assertIsNone(run["workspace"])
            self.assertNotIn(
                canary_value,
                result_path.read_text(encoding="utf-8"),
            )
            self.assertFalse(
                any(path.is_file() for path in work.rglob("*")),
                "unsafe temporary files must not survive --keep-workspaces",
            )

    def test_passed_environment_values_too_short_for_reliable_scan_are_refused(
        self,
    ) -> None:
        import run_evals

        with patch.dict(
            os.environ,
            {"DESIGN_DNA_SHORT_VALUE": "tiny"},
            clear=False,
        ):
            with self.assertRaises(ToolFailure) as raised:
                run_evals.explicit_environment(
                    ["DESIGN_DNA_SHORT_VALUE"]
                )
        self.assertEqual(
            raised.exception.issue.code,
            "unsafe-short-pass-env",
        )

    def test_input_snapshot_is_exact_and_source_is_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = root / "inputs" / "seed"
            inputs.mkdir(parents=True)
            source = inputs / "seed.txt"
            source.write_bytes(b"source bytes\n")
            cache = inputs / "__pycache__"
            cache.mkdir()
            compiled = cache / "seed.pyc"
            compiled.write_bytes(b"compiled input")
            (inputs / "bounded-empty-directory").mkdir()
            expected_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            fixture = write_eval_suite(
                root,
                suite="input-snapshot",
                input_dir="inputs/seed",
                expected={
                    "exit_codes": [0],
                    "files_exist": [
                        "seed.txt",
                        "__pycache__/seed.pyc",
                        "generated.txt",
                    ],
                    "files_unchanged": [
                        "seed.txt",
                        "__pycache__/seed.pyc",
                    ],
                    "changed_files_only": ["generated.txt"],
                    "max_changed_input_files": 0,
                },
            )
            code = "\n".join([
                "from pathlib import Path",
                "assert Path('seed.txt').read_bytes() == b'source bytes\\n'",
                "assert Path('__pycache__/seed.pyc').read_bytes() == b'compiled input'",
                "assert Path('bounded-empty-directory').is_dir()",
                "Path('generated.txt').write_text('new\\n', encoding='utf-8')",
            ])
            result = run_eval(root, fixture, code)
            payload, _ = load_only_result(root / "results")
            run = payload["runs"][0]
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr + repr(run["problems"]),
            )
            files = {item["path"]: item for item in run["files"]}
            self.assertEqual(files["seed.txt"]["sha256"], expected_hash)
            self.assertEqual(files["__pycache__"]["type"], "directory")
            self.assertEqual(files["__pycache__/seed.pyc"]["type"], "file")
            self.assertEqual(
                files["bounded-empty-directory"]["type"],
                "directory",
            )
            self.assertEqual(run["changed_paths"], ["generated.txt"])
            snapshot = payload["provenance"]["input_snapshots"]["writes-artifact"]
            self.assertEqual(snapshot["entry_count"], 4)
            bundle = root / "results" / run["artifact_bundle"]["path"]
            bundle_records, bundle_hash = eval_content_manifest(bundle)
            self.assertEqual(bundle_records, run["files"])
            self.assertEqual(bundle_hash, run["workspace_sha256"])
            self.assertEqual(source.read_text(encoding="utf-8"), "source bytes\n")

    def test_workspace_cache_artifact_cannot_hide_from_change_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = write_eval_suite(
                root,
                suite="cache-artifact-contract",
                expected={
                    "exit_codes": [0],
                    "changed_files_only": [],
                },
            )
            code = "\n".join([
                "from pathlib import Path",
                "cache = Path('__pycache__')",
                "cache.mkdir()",
                "(cache / 'stealth.pyc').write_bytes(b'stealth')",
            ])
            result = run_eval(root, fixture, code)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload, _ = load_only_result(root / "results")
            run = payload["runs"][0]
            self.assertFalse(run["passed"])
            self.assertEqual(
                run["changed_paths"],
                ["__pycache__", "__pycache__/stealth.pyc"],
            )
            self.assertTrue(
                any(
                    "__pycache__/stealth.pyc" in problem
                    for problem in run["problems"]
                ),
                run["problems"],
            )
            self.assertEqual(run["workspace_entry_count"], 2)
            self.assertEqual(run["workspace_file_count"], 1)
            self.assertEqual(run["workspace_bytes"], len(b"stealth"))
            files = {item["path"]: item for item in run["files"]}
            self.assertEqual(files["__pycache__"]["type"], "directory")
            self.assertEqual(files["__pycache__/stealth.pyc"]["type"], "file")
            bundle = root / "results" / run["artifact_bundle"]["path"]
            bundle_records, bundle_hash = eval_content_manifest(bundle)
            self.assertEqual(bundle_records, run["files"])
            self.assertEqual(bundle_hash, run["workspace_sha256"])
            self.assertTrue((bundle / "__pycache__" / "stealth.pyc").is_file())

    def test_workspace_entry_limit_counts_empty_directories(self) -> None:
        import run_evals

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            for index in range(3):
                (source / f"empty-{index}").mkdir()
            with patch.object(run_evals, "MAX_WORKSPACE_ENTRIES", 2):
                with self.assertRaises(ToolFailure) as raised:
                    run_evals.workspace_inventory(source)
                with self.assertRaises(ToolFailure) as copy_raised:
                    run_evals.copy_eval_tree(source, root / "copy")
            self.assertEqual(raised.exception.issue.code, "workspace-entry-limit")
            self.assertEqual(
                copy_raised.exception.issue.code,
                "workspace-entry-limit",
            )
            self.assertFalse((root / "copy").exists())

    def test_supplied_work_root_is_retained_but_each_run_is_cleaned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work = root / "supplied-work"
            fixture = write_eval_suite(root, suite="cleanup-contract")
            code = (
                "from pathlib import Path; "
                "Path('artifact.txt').write_text('ok', encoding='utf-8')"
            )
            result = run_eval(root, fixture, code, work_root=work)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(work.is_dir())
            self.assertEqual(list(work.iterdir()), [])
            payload, _ = load_only_result(root / "results")
            run = payload["runs"][0]
            self.assertIsNone(run["workspace"])
            bundle = run["artifact_bundle"]
            self.assertIsInstance(bundle, dict)
            bundle_path = root / "results" / bundle["path"]
            self.assertTrue(bundle_path.is_dir())
            bundle_files, bundle_hash = eval_content_manifest(bundle_path)
            self.assertEqual(bundle_hash, run["workspace_sha256"])
            self.assertEqual(bundle_files, run["files"])

    def test_full_stream_expectation_survives_bounded_capture_and_literal_braces(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = write_eval_suite(
                root,
                suite="capture-contract",
                expected={
                    "exit_codes": [0],
                    "stdout_contains": ["TAIL_ASSERTION"],
                },
            )
            code = "\n".join([
                "payload = {'literal': {'nested': True}}",
                "print('x' * 125050 + 'TAIL_ASSERTION' + 'y' * 125050)",
                "assert payload == {'literal': {'nested': True}}",
            ])
            result = run_eval(root, fixture, code)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload, _ = load_only_result(root / "results")
            run = payload["runs"][0]
            self.assertTrue(run["stdout_truncated"])
            self.assertNotIn("TAIL_ASSERTION", run["stdout"])
            self.assertEqual(run["problems"], [])

    def test_unsafe_suite_slug_is_rejected_before_any_result_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = write_eval_suite(root, suite="../escaped")
            result = run_eval(root, fixture, "print('should-not-run')")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            failure = json.loads(result.stdout)["failures"][0]
            self.assertEqual(failure["code"], "invalid-eval-suite")
            self.assertEqual(list((root / "results").glob("*.json")), [])
            self.assertEqual(list(root.glob("escaped-*.json")), [])

    def test_missing_monitor_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = write_eval_suite(root, suite="missing-monitor")
            missing = root / "does-not-exist"
            result = run_eval(
                root,
                fixture,
                "print('should-not-run')",
                monitor_roots=(missing,),
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            failure = json.loads(result.stdout)["failures"][0]
            self.assertEqual(failure["code"], "monitor-root-missing")
            self.assertEqual(list((root / "results").glob("*.json")), [])

    def test_monitor_root_deletion_is_attributed_to_the_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            monitor = root / "monitor"
            monitor.mkdir()
            (monitor / "before.txt").write_text("before", encoding="utf-8")
            fixture = write_eval_suite(root, suite="monitor-deletion")
            code = f"import shutil; shutil.rmtree({str(monitor)!r})"
            result = run_eval(
                root, fixture, code, monitor_roots=(monitor,)
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload, _ = load_only_result(root / "results")
            self.assertFalse(payload["runs"][0]["passed"])
            self.assertTrue(
                any(
                    "monitored external root changed during this run" in problem
                    for problem in payload["runs"][0]["problems"]
                )
            )

    def test_monitor_includes_pycache_and_changes_are_per_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            monitor = root / "monitor"
            monitor.mkdir()
            fixture = write_eval_suite(root, suite="monitor-attribution")
            code = "\n".join([
                "import json, os",
                "from pathlib import Path",
                "request = json.loads(Path(os.environ['DESIGN_DNA_EVAL_REQUEST']).read_text(encoding='utf-8'))",
                "if request['run'] == 1:",
                f"    cache = Path({str(monitor)!r}) / '__pycache__'",
                "    cache.mkdir()",
                "    (cache / 'transient.pyc').write_bytes(b'changed')",
            ])
            result = run_eval(
                root,
                fixture,
                code,
                runs=2,
                monitor_roots=(monitor,),
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload, _ = load_only_result(root / "results")
            by_number = {run["run"]: run for run in payload["runs"]}
            self.assertFalse(by_number[1]["passed"])
            self.assertTrue(by_number[2]["passed"])
            self.assertEqual(by_number[2]["problems"], [])
            self.assertEqual(
                payload["summary"],
                {
                    "total": 2,
                    "passed": 1,
                    "failed": 1,
                    "by_variant": {
                        "skill": {"total": 2, "passed": 1, "failed": 1}
                    },
                },
            )

    def test_monitor_overlap_with_work_or_results_is_rejected(self) -> None:
        for protected_name in ("work", "results"):
            with self.subTest(protected_name=protected_name):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    work = root / "work"
                    results = root / "results"
                    work.mkdir()
                    results.mkdir()
                    fixture = write_eval_suite(
                        root, suite=f"overlap-{protected_name}"
                    )
                    monitor = work if protected_name == "work" else results
                    result = run_eval(
                        root,
                        fixture,
                        "print('should-not-run')",
                        monitor_roots=(monitor,),
                        work_root=work,
                        results_dir=results,
                    )
                    self.assertEqual(
                        result.returncode, 2, result.stdout + result.stderr
                    )
                    failure = json.loads(result.stdout)["failures"][0]
                    self.assertEqual(failure["code"], "monitor-root-overlap")

    def test_timeout_terminates_descendant_process_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sentinel = root / "descendant-survived.txt"
            fixture = write_eval_suite(
                root,
                suite="timeout-tree",
                timeout_seconds=1,
            )
            child = (
                "import time; from pathlib import Path; "
                f"time.sleep(2); Path({str(sentinel)!r}).write_text('alive', encoding='utf-8')"
            )
            code = "\n".join([
                "import subprocess, sys, time",
                f"subprocess.Popen([sys.executable, '-c', {child!r}])",
                "time.sleep(30)",
            ])
            result = run_eval(root, fixture, code)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload, _ = load_only_result(root / "results")
            self.assertTrue(payload["runs"][0]["timed_out"])
            self.assertIn("driver timed out", payload["runs"][0]["problems"])
            time.sleep(2.25)
            self.assertFalse(
                sentinel.exists(),
                "a timed-out driver's descendant continued running",
            )

    @unittest.skipUnless(os.name == "nt", "Windows job containment only")
    def test_windows_job_termination_is_verified_without_taskkill(self) -> None:
        import run_evals

        class FakeProcess:
            pid = 41001

            def poll(self):
                return None

            def wait(self, timeout=None):
                return 1

        class FakeJob:
            def __init__(self):
                self.terminate_calls = 0
                self.wait_calls = []

            def terminate(self):
                self.terminate_calls += 1

            def wait_empty(self, milliseconds):
                self.wait_calls.append(milliseconds)
                return True

        process = FakeProcess()
        job = FakeJob()
        with patch.object(run_evals, "_taskkill_process_tree") as taskkill:
            evidence = run_evals.terminate_process_tree(process, job)
        self.assertEqual(evidence["method"], "windows-job")
        self.assertTrue(evidence["verified_empty"])
        self.assertEqual(job.terminate_calls, 1)
        self.assertEqual(job.wait_calls, [15000])
        taskkill.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows job containment only")
    def test_windows_job_termination_fallback_is_measured_and_verified(
        self,
    ) -> None:
        import run_evals

        class FakeProcess:
            pid = 41002

            def poll(self):
                return None

            def wait(self, timeout=None):
                return 1

        class FakeJob:
            def __init__(self):
                self.wait_results = iter((False, True))

            def terminate(self):
                raise OSError(5, "job termination denied")

            def wait_empty(self, milliseconds):
                return next(self.wait_results)

        taskkill_result = {
            "attempted": True,
            "returncode": 0,
            "stdout": "SUCCESS: terminated process tree",
            "stderr": "",
            "error": None,
        }
        with patch.object(
            run_evals,
            "_taskkill_process_tree",
            return_value=taskkill_result,
        ) as taskkill:
            evidence = run_evals.terminate_process_tree(
                FakeProcess(),
                FakeJob(),
            )
        self.assertEqual(evidence["method"], "taskkill-fallback")
        self.assertTrue(evidence["verified_empty"])
        self.assertFalse(evidence["job_termination"]["succeeded"])
        self.assertEqual(evidence["taskkill"], taskkill_result)
        taskkill.assert_called_once_with(41002)

    @unittest.skipUnless(os.name == "nt", "Windows job containment only")
    def test_windows_unverified_tree_termination_fails_with_exact_evidence(
        self,
    ) -> None:
        import run_evals

        class FakeProcess:
            pid = 41003

            def __init__(self):
                self.killed = False

            def poll(self):
                return None

            def kill(self):
                self.killed = True

            def wait(self, timeout=None):
                return 1

        class FakeJob:
            def terminate(self):
                raise OSError(5, "job termination denied")

            def wait_empty(self, milliseconds):
                return False

        process = FakeProcess()
        taskkill_result = {
            "attempted": True,
            "returncode": 128,
            "stdout": "",
            "stderr": "ERROR: process tree could not be terminated",
            "error": None,
        }
        with patch.object(
            run_evals,
            "_taskkill_process_tree",
            return_value=taskkill_result,
        ):
            with self.assertRaises(ToolFailure) as raised:
                run_evals.terminate_process_tree(process, FakeJob())
        self.assertEqual(
            raised.exception.issue.code,
            "process-tree-termination-failed",
        )
        self.assertIn('"returncode": 128', str(raised.exception))
        self.assertIn(
            "ERROR: process tree could not be terminated",
            str(raised.exception),
        )
        self.assertIn('"verified_empty": false', str(raised.exception))
        self.assertTrue(process.killed)

    @unittest.skipUnless(os.name == "nt", "Windows job containment only")
    def test_windows_assignment_failure_never_releases_driver(self) -> None:
        import run_evals

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sentinel = root / "driver-was-released.txt"
            command = [
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; "
                    f"Path({str(sentinel)!r}).write_text('unsafe', encoding='utf-8')"
                ),
            ]
            with patch.object(
                run_evals._WindowsProcessJob,
                "assign",
                side_effect=OSError(5, "job assignment denied"),
            ):
                with self.assertRaises(ToolFailure) as raised:
                    run_evals.run_driver(
                        command,
                        cwd=root,
                        environment=os.environ.copy(),
                        timeout=5,
                        stdout_path=root / "stdout.bin",
                        stderr_path=root / "stderr.bin",
                    )
            self.assertEqual(
                raised.exception.issue.code,
                "process-containment-assignment-failed",
            )
            time.sleep(0.25)
            self.assertFalse(sentinel.exists())

    def test_unsafe_workspace_symlink_is_a_recorded_run_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside"
            outside.mkdir()
            probe = root / "probe-link"
            if not make_directory_link(probe, outside):
                self.skipTest("directory links/junctions are unavailable")
            os.rmdir(probe)

            fixture = write_eval_suite(root, suite="unsafe-workspace")
            if os.name == "nt":
                code = "\n".join([
                    "import os, subprocess",
                    "from pathlib import Path",
                    "subprocess.run([os.environ['COMSPEC'], '/c', 'mklink', '/J', str(Path.cwd() / 'escape'), "
                    + f"{str(outside)!r}], check=True, capture_output=True)",
                ])
            else:
                code = "\n".join([
                    "import os",
                    f"os.symlink({str(outside)!r}, 'escape', target_is_directory=True)",
                ])
            result = run_eval(root, fixture, code)
            self.assertEqual(
                result.returncode,
                1,
                "an unsafe artifact must fail one run and still persist evidence\n"
                + result.stdout
                + result.stderr,
            )
            payload, _ = load_only_result(root / "results")
            run = payload["runs"][0]
            self.assertFalse(run["passed"])
            self.assertTrue(
                any(
                    "unsafe workspace artifact prevented manifesting" in problem
                    for problem in run["problems"]
                )
            )
            self.assertIsNone(run["workspace_sha256"])
            self.assertEqual(run["files"], [])

            workspace_path = Path(str(run["workspace"]))
            link = workspace_path / "escape"
            if is_reparse(link):
                os.rmdir(link)
            shutil.rmtree(workspace_path.parent, ignore_errors=False)

    def test_post_run_staged_skill_mutation_fails_parity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = write_eval_suite(root, suite="staging-tamper")
            code = "\n".join([
                "import os",
                "from pathlib import Path",
                "route = Path(os.environ['DESIGN_DNA_SKILL_ROOT'])",
                "(route / 'SKILL.md').write_text('tampered', encoding='utf-8')",
            ])
            result = run_eval(root, fixture, code)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload, _ = load_only_result(root / "results")
            run = payload["runs"][0]
            self.assertFalse(run["passed"])
            self.assertFalse(run["skill_route_verified_after"])
            self.assertTrue(
                any(
                    "staged skill changed" in problem.casefold()
                    for problem in run["problems"]
                )
            )


if __name__ == "__main__":
    unittest.main()
