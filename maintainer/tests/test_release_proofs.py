from __future__ import annotations

import copy
import contextlib
import hashlib
import io
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import yaml
from jsonschema import Draft202012Validator, FormatChecker


PLUGIN = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN / "maintainer" / "scripts"
SCHEMAS = PLUGIN / "maintainer" / "schemas"
sys.path.insert(0, str(SCRIPTS))
try:
    import attest_codex_plugin
    import attest_tests
    import attest_install_lifecycle
    import audit_package
finally:
    sys.path.remove(str(SCRIPTS))


def make_attestation_fixture(root: Path) -> Path:
    plugin = root / "plugin"
    maintainer = plugin / "maintainer"
    runtime = plugin / "skills" / "design-dna"
    runtime.mkdir(parents=True)
    (runtime / "SKILL.md").write_text(
        "---\n"
        "name: design-dna\n"
        "description: Attestation fixture.\n"
        "---\n\n"
        "# Design DNA\n",
        encoding="utf-8",
    )
    for name in ("tests", "scripts"):
        directory = runtime / name
        directory.mkdir()
        (directory / f"{name}.txt").write_text(
            f"stable runtime {name}\n",
            encoding="utf-8",
        )
    for name in ("tests", "scripts", "schemas"):
        directory = maintainer / name
        directory.mkdir(parents=True)
        (directory / f"{name}.txt").write_text(
            f"stable {name}\n",
            encoding="utf-8",
        )
    for name in (
        "cache_preflight.py",
        "run_release_tests.py",
        "attest_tests.py",
        "build_manifest.py",
        "common.py",
    ):
        shutil.copy2(SCRIPTS / name, maintainer / "scripts" / name)
    shutil.copy2(
        SCHEMAS / "test-attestation.schema.json",
        maintainer / "schemas" / "test-attestation.schema.json",
    )
    shutil.copy2(
        PLUGIN / "maintainer" / "requirements-dev.txt",
        maintainer / "requirements-dev.txt",
    )
    shutil.copy2(
        PLUGIN / "maintainer" / "requirements-dev.lock",
        maintainer / "requirements-dev.lock",
    )
    for name in ("package.json", "package-lock.json"):
        shutil.copy2(PLUGIN / "maintainer" / name, maintainer / name)
    for directory in (".codex-plugin", ".claude-plugin"):
        manifest = plugin / directory / "plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            json.dumps({"name": f"attestation-{directory}"}) + "\n",
            encoding="utf-8",
        )
    for name in (
        ".gitattributes",
        ".gitignore",
        "README.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "DATA_HANDLING.md",
        "LICENSE",
        "SECURITY.md",
        "SUPPORT.md",
        "THIRD_PARTY_NOTICES.md",
    ):
        (plugin / name).write_text(
            f"attestation fixture source: {name}\n",
            encoding="utf-8",
        )
    docs = plugin / "docs"
    docs.mkdir()
    (docs / "QUICK_START.md").write_text(
        "attestation fixture documentation\n",
        encoding="utf-8",
    )
    workflow = plugin / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "name: attestation-fixture\n"
        "on: [push]\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps: []\n",
        encoding="utf-8",
    )
    evals = maintainer / "evals"
    fixtures = evals / "fixtures"
    fixtures.mkdir(parents=True)
    (evals / "README.md").write_text(
        "attestation fixture evaluation contract\n",
        encoding="utf-8",
    )
    (evals / "review-rubric.md").write_text(
        "attestation fixture evaluation rubric\n",
        encoding="utf-8",
    )
    (evals / "schema.json").write_text("{}\n", encoding="utf-8")
    (fixtures / "behavioral-cases.json").write_text(
        "[]\n",
        encoding="utf-8",
    )
    compatibility = maintainer / "compatibility"
    compatibility.mkdir()
    (compatibility / "matrix.yml").write_text(
        "environments: []\n",
        encoding="utf-8",
    )
    (compatibility / "trusted-host-adapters.yml").write_text(
        "hosts: {}\n",
        encoding="utf-8",
    )
    trust = maintainer / "trust"
    trust.mkdir()
    (trust / "codex-plugin-validator.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    evidence = maintainer / "evidence"
    evidence.mkdir()
    (evidence / "index.yml").write_text(
        "entries: []\n",
        encoding="utf-8",
    )
    return plugin


def fake_unittest_result(
    command: list[str],
    *,
    passed: bool = True,
    skipped: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    if passed:
        if skipped:
            stderr = (
                "test_one (suite.Case.test_one) ... ok\n"
                "test_two (suite.Case.test_two) ... skipped 'fixture'\n"
                "\n"
                "----------------------------------------------------------------------\n"
                "Ran 2 tests in 0.010s\n"
                "\n"
                "OK (skipped=1)\n"
            ).encode("utf-8")
        else:
            stderr = (
                "test_one (suite.Case.test_one) ... ok\n"
                "test_two (suite.Case.test_two) ... ok\n"
                "\n"
                "----------------------------------------------------------------------\n"
                "Ran 2 tests in 0.010s\n"
                "\n"
                "OK\n"
            ).encode("utf-8")
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=stderr)
    stderr = (
        "test_one (suite.Case.test_one) ... FAIL\n"
        "\n"
        "----------------------------------------------------------------------\n"
        "Ran 1 test in 0.010s\n"
        "\n"
        "FAILED (failures=1)\n"
    ).encode("utf-8")
    return subprocess.CompletedProcess(command, 1, stdout=b"", stderr=stderr)


def make_release_runner_fixture(
    root: Path,
    test_source: str,
    *,
    test_name: str = "test_release_runner_fixture.py",
    runtime_test_source: str | None = None,
    runtime_test_name: str = "test_runtime_release_runner_fixture.py",
    include_attester: bool = False,
) -> Path:
    plugin = root / "plugin"
    runtime = plugin / "skills" / "design-dna"
    scripts = plugin / "maintainer" / "scripts"
    tests = plugin / "maintainer" / "tests"
    runtime_tests = runtime / "tests"
    runtime.mkdir(parents=True)
    scripts.mkdir(parents=True)
    tests.mkdir(parents=True)
    runtime_tests.mkdir(parents=True)
    script_names = ["cache_preflight.py", "run_release_tests.py"]
    if include_attester:
        # Importing the attester as a release test library exercises the
        # runner's real import context rather than a mock of it.
        script_names.extend(("attest_tests.py", "build_manifest.py", "common.py"))
    for name in script_names:
        shutil.copy2(SCRIPTS / name, scripts / name)
    (tests / test_name).write_text(
        test_source,
        encoding="utf-8",
    )
    (runtime_tests / runtime_test_name).write_text(
        runtime_test_source
        or (
            "import unittest\n\n"
            "class RuntimePassing(unittest.TestCase):\n"
            "    def test_runtime_ok(self):\n"
            "        self.assertTrue(True)\n"
        ),
        encoding="utf-8",
    )
    return plugin


def run_release_runner(
    plugin: Path,
    *,
    inherit_bytecode_guard: bool = True,
    environment_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    if inherit_bytecode_guard:
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
    else:
        environment.pop("PYTHONDONTWRITEBYTECODE", None)
    environment["PYTHONUTF8"] = "1"
    if environment_overrides:
        environment.update(environment_overrides)
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            str(plugin / "maintainer" / "scripts" / "run_release_tests.py"),
        ],
        cwd=plugin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        timeout=30,
        check=False,
    )


def run_attestation_cli(
    plugin: Path,
    output: Path,
    *,
    isolated: bool,
    environment_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the copied attester through its real process boundary."""

    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    if environment_overrides:
        environment.update(environment_overrides)
    command = [sys.executable]
    if isolated:
        command.extend(("-I", "-S"))
    command.extend((
        "-B",
        str(plugin / "maintainer" / "scripts" / "attest_tests.py"),
        "--plugin-root",
        ".",
        "--output",
        str(output),
    ))
    return subprocess.run(
        command,
        cwd=plugin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        timeout=60,
        check=False,
    )


def write_skill(path: Path, marker: str = "same") -> None:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(
        "---\n"
        "name: design-dna\n"
        "description: Route proof fixture.\n"
        "---\n\n"
        f"# Design DNA\n\n{marker}\n",
        encoding="utf-8",
    )


def after_timestamp(value: str, *, hours: int = 0, seconds: int = 0) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (
        parsed + timedelta(hours=hours, seconds=seconds)
    ).isoformat().replace("+00:00", "Z")


def make_ci_import_fixture(
    root: Path,
) -> tuple[Path, dict[str, object], dict[str, str], Path]:
    plugin = make_attestation_fixture(root)
    shutil.copy2(
        SCHEMAS / "ci-run-import.schema.json",
        plugin / "maintainer" / "schemas" / "ci-run-import.schema.json",
    )
    workflow = plugin / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    python_version = ".".join(platform.python_version().split(".")[:2])
    workflow.write_text(
        "jobs:\n"
        "  test:\n"
        '    name: "${{ matrix.os }} / Python ${{ matrix.python }}"\n'
        "    strategy:\n"
        "      matrix:\n"
        "        os:\n"
        "          - ubuntu-latest\n"
        "        python:\n"
        f'          - "{python_version}"\n',
        encoding="utf-8",
    )

    def runner(
        _selected_plugin: Path,
        command: list[str],
    ) -> subprocess.CompletedProcess[bytes]:
        return fake_unittest_result(command)

    attestation = attest_tests.create_attestation(plugin, runner=runner)
    job_started = after_timestamp(attestation["started_at"], seconds=-1)
    job_completed = after_timestamp(attestation["completed_at"], seconds=1)
    imported_at = after_timestamp(job_completed, seconds=1)
    manifest = {
        "generated_at": after_timestamp(imported_at, seconds=1),
    }
    environment_id = (
        f"ci-ubuntu-python-{python_version.replace('.', '-')}"
    )
    archive_root = (
        plugin
        / "maintainer"
        / "compatibility"
        / "archive"
        / "ci-runs"
        / environment_id
    )
    archive_root.mkdir(parents=True)
    test_bytes = (
        json.dumps(attestation, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    audit_bytes = (
        json.dumps(
            {
                "ok": True,
                "failures": [],
                "warnings": [],
                "details": {},
            },
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    test_path = archive_root / "design-dna-test-attestation.json"
    audit_path = archive_root / "design-dna-package-audit.json"
    test_path.write_bytes(test_bytes)
    audit_path.write_bytes(audit_bytes)
    artifact_path = archive_root / "artifact.zip"
    with zipfile.ZipFile(
        artifact_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            "design-dna-test-attestation.json",
            test_bytes,
        )
        archive.writestr(
            "design-dna-package-audit.json",
            audit_bytes,
        )
    artifact_bytes = artifact_path.read_bytes()
    artifact_digest = hashlib.sha256(artifact_bytes).hexdigest()
    relative_root = (
        "maintainer/compatibility/archive/ci-runs/"
        + environment_id
    )
    import_relative = f"{relative_root}/import.json"
    artifact_relative = f"{relative_root}/artifact.zip"
    test_relative = (
        f"{relative_root}/design-dna-test-attestation.json"
    )
    audit_relative = (
        f"{relative_root}/design-dna-package-audit.json"
    )
    import_payload = {
        "schema_version": 1,
        "record_type": "design-dna-ci-run-import",
        "environment_id": environment_id,
        "imported_at": imported_at,
        "imported_by": "release-reviewer",
        "source": {
            "provider": "github-actions",
            "repository": "example/design-dna",
            "workflow_path": ".github/workflows/ci.yml",
            "workflow_sha256": hashlib.sha256(
                workflow.read_bytes()
            ).hexdigest(),
            "run_id": "123456",
            "run_attempt": 1,
            "commit_sha": "a" * 40,
            "job_name": (
                f"ubuntu-latest / Python {python_version}"
            ),
            "matrix": {
                "os": "ubuntu-latest",
                "python": python_version,
                "node": None,
            },
            "started_at": job_started,
            "completed_at": job_completed,
            "conclusion": "success",
        },
        "artifact": {
            "id": "987654",
            "name": (
                f"test-attestation-ubuntu-latest-py{python_version}"
            ),
            "authenticated_download": True,
            "service_digest": f"sha256:{artifact_digest}",
            "path": artifact_relative,
            "sha256": artifact_digest,
            "size_bytes": len(artifact_bytes),
        },
        "passed_checks": ["package_audit", "unit_tests"],
        "evidence": {
            "package_audit": {
                "path": audit_relative,
                "archive_member": "design-dna-package-audit.json",
                "sha256": hashlib.sha256(audit_bytes).hexdigest(),
                "size_bytes": len(audit_bytes),
            },
            "unit_tests": {
                "path": test_relative,
                "archive_member": "design-dna-test-attestation.json",
                "sha256": hashlib.sha256(test_bytes).hexdigest(),
                "size_bytes": len(test_bytes),
            },
        },
    }
    import_path = archive_root / "import.json"
    import_path.write_text(
        json.dumps(import_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    compatibility = {
        "ci_release_contract": {
            "workflow_path": ".github/workflows/ci.yml",
            "test_job": "test",
            "required_checks": ["package_audit", "unit_tests"],
            "import_schema": (
                "maintainer/schemas/ci-run-import.schema.json"
            ),
            "import_root": (
                "maintainer/compatibility/archive/ci-runs"
            ),
        },
        "environments": [
            {
                "id": environment_id,
                "scope": "ci_contract",
                "os": "ubuntu-latest",
                "architecture": "runner-defined",
                "python": python_version,
                "node": None,
                "host": None,
                "host_version": None,
                "checked_at": imported_at,
                "checks": {
                    "package_audit": "passed",
                    "unit_tests": "passed",
                    "installer_lifecycle": "declared_not_observed",
                    "host_discovery": "not_applicable",
                    "behavioral_eval": "not_applicable",
                    "rendered_review": "not_applicable",
                },
                "evidence": [
                    ".github/workflows/ci.yml",
                    import_relative,
                    artifact_relative,
                    test_relative,
                    audit_relative,
                ],
                "notes": ["Imported fixture CI run."],
            }
        ],
    }
    return plugin, compatibility, manifest, audit_path


def remove_test_tree(path: Path) -> None:
    """Remove a known temporary fixture tree even when copied files are read-only."""

    if path.name != "attestations" or path.parent.name != "maintainer":
        raise AssertionError(f"unexpected test cleanup target: {path}")

    def clear_readonly_and_retry(operation, target: str, _error) -> None:
        os.chmod(target, os.stat(target).st_mode | stat.S_IWRITE)
        operation(target)

    shutil.rmtree(path, onerror=clear_readonly_and_retry)


def run_detect(
    canonical: Path,
    roots: list[Path],
    expected: list[Path],
    output: Path,
    home: Path | None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-B",
        str(SCRIPTS / "detect_routes.py"),
        "--canonical",
        str(canonical),
    ]
    for root in roots:
        command.extend(("--root", str(root)))
    for route in expected:
        command.extend(("--expected", str(route)))
    if home is not None:
        command.extend(("--home", str(home)))
    command.extend(("--output", str(output)))
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=environment,
        timeout=120,
    )


def make_fake_codex_validator(base: Path) -> Path:
    path = (
        base
        / "skills"
        / ".system"
        / "plugin-creator"
        / "scripts"
        / "validate_plugin.py"
    )
    path.parent.mkdir(parents=True)
    path.write_text(
        '"""plugin ingestion contract"""\n'
        "import sys\n"
        "from pathlib import Path\n"
        "def validate_plugin(plugin_root): return []\n"
        "if __name__ == '__main__':\n"
        "    print(f'Plugin validation passed: {Path(sys.argv[1]).resolve()}')\n"
        "    raise SystemExit(0)\n"
        "# .codex-plugin\n",
        encoding="utf-8",
    )
    return path


def make_codex_plugin_fixture(
    base: Path,
    validator_path: Path,
    *,
    reviewed_at: datetime | None = None,
    review_due: datetime | None = None,
) -> Path:
    plugin = base / "plugin"
    manifest = plugin / ".codex-plugin" / "plugin.json"
    skill = plugin / "skills" / "design-dna" / "SKILL.md"
    manifest.parent.mkdir(parents=True)
    skill.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({
            "name": "design-dna",
            "version": "3.0.0",
            "description": "Proof fixture.",
            "author": {"name": "Design DNA tests"},
            "license": "Proprietary",
            "skills": "./skills/",
            "interface": {
                "displayName": "Design DNA",
                "shortDescription": "Proof fixture.",
                "longDescription": "Proof fixture for release validation.",
                "developerName": "Design DNA tests",
                "category": "Productivity",
                "capabilities": ["Write"],
                "defaultPrompt": ["Use Design DNA."],
                "brandColor": "#164E63",
            },
        }, indent=2)
        + "\n",
        encoding="utf-8",
    )
    skill.write_text(
        "---\n"
        "name: design-dna\n"
        "description: Isolated release proof fixture.\n"
        "---\n\n"
        "# Design DNA\n",
        encoding="utf-8",
    )
    for relative in (
        "maintainer/scripts/attest_codex_plugin.py",
        "maintainer/scripts/cache_preflight.py",
        "maintainer/scripts/common.py",
        (
            "maintainer/schemas/"
            "codex-plugin-validation-attestation.schema.json"
        ),
        "maintainer/schemas/codex-validator-trust.schema.json",
    ):
        source = PLUGIN / relative
        target = plugin / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    validator_data = validator_path.read_bytes()
    today = datetime.now(timezone.utc).date()
    reviewed_date = reviewed_at.date() if reviewed_at else today
    due_date = (
        review_due.date()
        if review_due
        else today + timedelta(days=90)
    )
    trust = {
        "schema_version": 1,
        "record_type": "design-dna-codex-validator-trust-pin",
        "logical_id": "plugin-creator/validate_plugin.py",
        "path_suffix": (
            "/skills/.system/plugin-creator/scripts/validate_plugin.py"
        ),
        "sha256": hashlib.sha256(validator_data).hexdigest(),
        "bytes": len(validator_data),
        "reviewed_at": reviewed_date.isoformat(),
        "review_due": due_date.isoformat(),
        "review_basis": (
            "Reviewed test-only validator bytes for release-proof coverage."
        ),
        "trust_boundary": (
            "Test-only publisher pin; not a vendor signature or production proof."
        ),
    }
    trust_path = (
        plugin
        / "maintainer"
        / "trust"
        / "codex-plugin-validator.json"
    )
    trust_path.parent.mkdir(parents=True)
    trust_path.write_text(
        json.dumps(trust, indent=2) + "\n",
        encoding="utf-8",
    )
    return plugin


class CandidateMetadataTests(unittest.TestCase):
    """Keep the unreleased candidate's public contract coherent with runtime."""

    def test_v520_docs_and_manifests_describe_opt_in_cpe_standard_first(self) -> None:
        documents = {
            "CHANGELOG.md": PLUGIN / "CHANGELOG.md",
            "README.md": PLUGIN / "README.md",
            "docs/QUICK_START.md": PLUGIN / "docs" / "QUICK_START.md",
            "docs/RELEASE.md": PLUGIN / "docs" / "RELEASE.md",
        }
        texts = {
            name: path.read_text(encoding="utf-8")
            for name, path in documents.items()
        }
        for name, content in texts.items():
            with self.subTest(document=name):
                self.assertIn("Connected Public Experience", content)

        quick_start = texts["docs/QUICK_START.md"]
        self.assertIn("begins at Standard", quick_start)
        self.assertNotIn("normally selects Showcase", quick_start)
        self.assertIn(
            "public status,\nvisibility, and route count alone do not select it",
            quick_start,
        )
        for name in ("README.md", "docs/QUICK_START.md"):
            with self.subTest(showcase_selector_document=name):
                content = texts[name]
                self.assertIn("High visibility or owner sensitivity alone does not select it", content)
                self.assertIn("premium, showcase, high-ambition", content)
                self.assertIn("direction recovery", content)
        self.assertIn("remains Standard", texts["README.md"])
        self.assertIn("Intensify Standard's rendered first-impression", quick_start)
        self.assertIn(
            "CPE closure does not prove owner acceptance",
            texts["CHANGELOG.md"],
        )
        self.assertIn(
            "It does not prove\n  owner acceptance",
            texts["docs/RELEASE.md"],
        )

        manifests = {
            ".codex-plugin/plugin.json": PLUGIN / ".codex-plugin" / "plugin.json",
            ".claude-plugin/plugin.json": PLUGIN / ".claude-plugin" / "plugin.json",
        }
        release_version = json.loads(
            (PLUGIN / "skills" / "design-dna" / "release.json").read_text(
                encoding="utf-8"
            )
        )["version"]
        for name, path in manifests.items():
            with self.subTest(manifest=name):
                manifest = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(manifest["version"], release_version)
                self.assertIn("connected-public-experience", manifest["keywords"])
                self.assertIn("connected public", manifest["description"].casefold())

        matrix = yaml.safe_load(
            (PLUGIN / "maintainer" / "compatibility" / "matrix.yml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(matrix["package_version"], release_version)
        self.assertTrue(
            any(
                item.startswith(
                    "Connected Public Experience records, when selected, "
                    "are project-level evidence only"
                )
                for item in matrix["release_limitations"]
            )
        )


class TestAttestationTests(unittest.TestCase):
    def test_release_runner_emits_docstring_skip_on_one_parseable_line(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_release_runner_fixture(
                Path(temporary),
                "import unittest\n\n"
                "class DocstringBearingSkip(unittest.TestCase):\n"
                "    @unittest.skip('fixture')\n"
                "    def test_platform_branch(self):\n"
                "        '''This docstring must not break the skip identity.'''\n"
                "\n",
            )
            completed = run_release_runner(plugin)
            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )
            test_id = (
                "test_release_runner_fixture.DocstringBearingSkip."
                "test_platform_branch"
            )
            self.assertIn(
                f"test_platform_branch ({test_id}) ... skipped 'fixture'",
                completed.stderr,
            )
            self.assertNotIn(
                "This docstring must not break the skip identity.",
                completed.stderr,
            )
            parsed, _stdout, _stderr, _digest = (
                attest_tests.parse_unittest_result(
                    subprocess.CompletedProcess(
                        [sys.executable, "-B", "runner.py"],
                        completed.returncode,
                        completed.stdout.encode("utf-8"),
                        completed.stderr.encode("utf-8"),
                    )
                )
            )
            self.assertEqual(parsed["skipped_test_ids"], [test_id])

    def test_release_runner_keeps_maintainer_package_importable(self) -> None:
        """Absolute-script execution must retain the documented CLI context."""

        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_release_runner_fixture(
                Path(temporary),
                "from maintainer.tests.runner_import_support import MARKER\n"
                "import unittest\n\n"
                "class PackageImport(unittest.TestCase):\n"
                "    def test_package_import(self):\n"
                "        self.assertEqual(MARKER, 'available')\n",
            )
            support = (
                plugin
                / "maintainer"
                / "tests"
                / "runner_import_support.py"
            )
            support.write_text("MARKER = 'available'\n", encoding="utf-8")

            completed = run_release_runner(plugin)

            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )
            self.assertIn(
                "test_package_import (test_release_runner_fixture."
                "PackageImport.test_package_import) ... ok",
                completed.stderr,
            )
            self.assertNotIn("ModuleNotFoundError", completed.stderr)

    def test_release_runner_allows_attester_library_import_under_isolation(
        self,
    ) -> None:
        """The runner's controlled package root remains usable by test imports."""

        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_release_runner_fixture(
                Path(temporary),
                "import attest_tests\n"
                "import unittest\n\n"
                "class AttesterLibraryImport(unittest.TestCase):\n"
                "    def test_runner_context_is_retained(self):\n"
                "        self.assertTrue(callable(attest_tests.main))\n"
                "        self.assertFalse(attest_tests._DIRECT_CLI_BOOTSTRAP)\n",
                include_attester=True,
            )

            completed = run_release_runner(plugin)

            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )
            self.assertIn(
                "test_runner_context_is_retained (test_release_runner_fixture."
                "AttesterLibraryImport.test_runner_context_is_retained) ... ok",
                completed.stderr,
            )
            self.assertIn("Ran 2 tests", completed.stderr)
            self.assertNotIn(
                "non-canonical import path",
                completed.stdout + completed.stderr,
            )

    def test_release_runner_executes_runtime_cpe_tests_without_name_shadowing(
        self,
    ) -> None:
        """Both roots count even when their CPE modules share a bare name."""

        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_release_runner_fixture(
                Path(temporary),
                "import unittest\n\n"
                "class MaintainerCPE(unittest.TestCase):\n"
                "    def test_maintainer_coverage(self):\n"
                "        self.assertTrue(True)\n",
                test_name="test_connected_public_experience.py",
                runtime_test_name="test_connected_public_experience.py",
                runtime_test_source=(
                    "import unittest\n\n"
                    "class RuntimeCPE(unittest.TestCase):\n"
                    "    def test_runtime_coverage(self):\n"
                    "        self.assertTrue(True)\n"
                ),
            )

            completed = run_release_runner(plugin)

            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )
            self.assertIn(
                "test_maintainer_coverage (test_connected_public_experience."
                "MaintainerCPE.test_maintainer_coverage) ... ok",
                completed.stderr,
            )
            self.assertIn(
                "test_runtime_coverage (test_connected_public_experience."
                "RuntimeCPE.test_runtime_coverage) ... ok",
                completed.stderr,
            )
            parsed, _stdout, _stderr, _digest = (
                attest_tests.parse_unittest_result(
                    subprocess.CompletedProcess(
                        [sys.executable, "-B", "runner.py"],
                        completed.returncode,
                        completed.stdout.encode("utf-8"),
                        completed.stderr.encode("utf-8"),
                    )
                )
            )
            self.assertEqual(parsed["tests_run"], 2)

    def test_release_runner_isolates_duplicate_module_fixtures_by_root(
        self,
    ) -> None:
        """A later duplicate module must not replace an earlier setUpModule."""

        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_release_runner_fixture(
                Path(temporary),
                "import unittest\n\n"
                "def setUpModule():\n"
                "    raise RuntimeError('maintainer fixture must run')\n\n"
                "class MaintainerCollision(unittest.TestCase):\n"
                "    def test_hidden_by_bad_discovery(self):\n"
                "        self.fail('setUpModule should have stopped this test')\n",
                test_name="test_collision.py",
                runtime_test_name="test_collision.py",
                runtime_test_source=(
                    "import unittest\n\n"
                    "class RuntimeCollision(unittest.TestCase):\n"
                    "    def test_runtime_still_runs(self):\n"
                    "        self.assertTrue(True)\n"
                ),
            )

            completed = run_release_runner(plugin)

            self.assertEqual(completed.returncode, 1, completed.stderr)
            self.assertIn(
                "=== Design DNA release test root: maintainer/tests ===",
                completed.stderr,
            )
            self.assertIn(
                "maintainer fixture must run",
                completed.stderr,
            )
            self.assertIn("setUpModule (test_collision)", completed.stderr)
            self.assertIn(
                "=== Design DNA release test root: skills/design-dna/tests ===",
                completed.stderr,
            )
            self.assertIn(
                "test_runtime_still_runs (test_collision.RuntimeCollision."
                "test_runtime_still_runs) ... ok",
                completed.stderr,
            )
            parsed, _stdout, _stderr, _digest = (
                attest_tests.parse_unittest_result(
                    subprocess.CompletedProcess(
                        [sys.executable, "-B", "runner.py"],
                        completed.returncode,
                        completed.stdout.encode("utf-8"),
                        completed.stderr.encode("utf-8"),
                    )
                )
            )
            self.assertEqual(parsed["status"], "failed")
            self.assertEqual(parsed["errors"], 1)
            self.assertEqual(parsed["tests_run"], 1)

    def test_release_runner_preserves_cache_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_release_runner_fixture(
                Path(temporary),
                "import unittest\n\n"
                "class Passing(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertTrue(True)\n",
            )
            residue = plugin / "maintainer" / "tests" / "__pycache__"
            residue.mkdir()
            (residue / "fixture.pyc").write_bytes(b"compiled")
            completed = run_release_runner(plugin)
            self.assertEqual(completed.returncode, 2, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                "maintainer-cache-residue",
                {finding["code"] for finding in payload["failures"]},
            )

    def test_release_runner_refuses_a_nonisolated_bootstrap(self) -> None:
        """A direct runner invocation cannot silently skip startup isolation."""

        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_release_runner_fixture(
                Path(temporary),
                "import unittest\n\n"
                "class Passing(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertTrue(True)\n",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(plugin / "maintainer" / "scripts" / "run_release_tests.py"),
                ],
                cwd=plugin,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(
                payload["failures"][0]["code"],
                "release-test-runner-isolation-required",
            )

    def test_release_runner_main_refuses_nonisolated_dynamic_import(
        self,
    ) -> None:
        """A startup hook cannot call an imported runner main to reach discovery."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = make_release_runner_fixture(
                root,
                "import unittest\n\n"
                "class Passing(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertTrue(True)\n",
            )
            injected = root / "external-pythonpath"
            injected.mkdir()
            marker = root / "runner-imported-main.txt"
            runner = plugin / "maintainer" / "scripts" / "run_release_tests.py"
            (injected / "sitecustomize.py").write_text(
                "import builtins\n"
                "import importlib.util\n"
                "import os\n"
                "import sys\n"
                "import unittest\n"
                "from pathlib import Path\n"
                f"MARKER = Path({json.dumps(str(marker))})\n"
                f"SCRIPT = {json.dumps(str(runner))}\n"
                "unittest.TestLoader.discover = (\n"
                "    lambda self, *args, **kwargs: unittest.TestSuite()\n"
                ")\n"
                "sys.path.insert(0, str(Path(SCRIPT).parent))\n"
                "spec = importlib.util.spec_from_file_location(\n"
                "    'startup_imported_release_runner', SCRIPT\n"
                ")\n"
                "module = importlib.util.module_from_spec(spec)\n"
                "sys.modules[spec.name] = module\n"
                "spec.loader.exec_module(module)\n"
                "builtins.design_dna_startup_imported_runner = module\n"
                "MARKER.write_text('hook-imported', encoding='utf-8')\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    (
                        "import builtins; "
                        f"open({str(marker)!r}, 'w', encoding='utf-8').write('main-invoked'); "
                        "raise SystemExit("
                        "builtins.design_dna_startup_imported_runner.main())"
                    ),
                ],
                cwd=plugin,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={
                    **os.environ,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(injected),
                },
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8"), "main-invoked")
            payload = json.loads(completed.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(
                payload["failures"][0]["code"],
                "release-test-runner-isolation-required",
            )

    def test_attester_main_refuses_nonisolated_dynamic_import(
        self,
    ) -> None:
        """A startup hook cannot forge an attestation by importing main."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = make_attestation_fixture(root)
            injected = root / "external-pythonpath"
            injected.mkdir()
            marker = root / "attester-imported-main.txt"
            output = root / "forged-attestation.json"
            attester = plugin / "maintainer" / "scripts" / "attest_tests.py"
            (injected / "sitecustomize.py").write_text(
                "import builtins\n"
                "import importlib.util\n"
                "import os\n"
                "import subprocess\n"
                "import sys\n"
                "from pathlib import Path\n"
                f"MARKER = Path({json.dumps(str(marker))})\n"
                f"SCRIPT = {json.dumps(str(attester))}\n"
                f"PLUGIN = {json.dumps(str(plugin))}\n"
                f"OUTPUT = {json.dumps(str(output))}\n"
                "sys.path.insert(0, str(Path(SCRIPT).parent))\n"
                "spec = importlib.util.spec_from_file_location(\n"
                "    'startup_imported_attester', SCRIPT\n"
                ")\n"
                "module = importlib.util.module_from_spec(spec)\n"
                "sys.modules[spec.name] = module\n"
                "spec.loader.exec_module(module)\n"
                "subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(\n"
                "    args[0], 0, b'', b'Ran 733 tests in 0.001s\\n\\nOK\\n'\n"
                ")\n"
                "builtins.design_dna_startup_imported_attester = module\n"
                "MARKER.write_text('hook-imported', encoding='utf-8')\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    (
                        "import builtins, sys; "
                        f"sys.argv = [{str(attester)!r}, '--plugin-root', {str(plugin)!r}, '--output', {str(output)!r}]; "
                        f"open({str(marker)!r}, 'w', encoding='utf-8').write('main-invoked'); "
                        "raise SystemExit("
                        "builtins.design_dna_startup_imported_attester.main())"
                    ),
                ],
                cwd=plugin,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={
                    **os.environ,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(injected),
                },
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8"), "main-invoked")
            self.assertFalse(output.exists())
            payload = json.loads(completed.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(
                payload["failures"][0]["code"],
                "test-attestation-isolation-required",
            )

    def test_attester_direct_isolated_cli_runs_the_real_two_root_suite(
        self,
    ) -> None:
        """The direct ``-I -S -B`` CLI keeps its own controlled bootstrap."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = make_attestation_fixture(root)
            (plugin / "maintainer" / "tests" / "test_real_maintainer.py").write_text(
                "import unittest\n\n"
                "class RealMaintainer(unittest.TestCase):\n"
                "    def test_real_maintainer_case(self):\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            (plugin / "skills" / "design-dna" / "tests" / "test_real_runtime.py").write_text(
                "import unittest\n\n"
                "class RealRuntime(unittest.TestCase):\n"
                "    def test_real_runtime_case(self):\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            output = root / "isolated-attestation.json"

            completed = run_attestation_cli(plugin, output, isolated=True)

            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(record["result"]["tests_run"], 2)
            self.assertEqual(
                record["command"],
                [
                    attest_tests.PYTHON_EXECUTABLE_TOKEN,
                    "-I",
                    "-S",
                    "-B",
                    attest_tests.RELEASE_TEST_RUNNER,
                ],
            )

    def test_attester_ignores_external_sitecustomize_only_when_isolated(
        self,
    ) -> None:
        """A startup hook cannot turn an injected empty suite into a pass."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = make_attestation_fixture(root)
            (plugin / "maintainer" / "tests" / "test_real_maintainer.py").write_text(
                "import os\n"
                "import unittest\n\n"
                "class RealMaintainer(unittest.TestCase):\n"
                "    def test_real_maintainer_case(self):\n"
                "        self.assertNotIn('PYTHONPATH', os.environ)\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            (plugin / "skills" / "design-dna" / "tests" / "test_real_runtime.py").write_text(
                "import unittest\n\n"
                "class RealRuntime(unittest.TestCase):\n"
                "    def test_real_runtime_case(self):\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            injected = root / "external-pythonpath"
            injected.mkdir()
            marker = root / "sitecustomize-load-count.txt"
            (injected / "sitecustomize.py").write_text(
                "from pathlib import Path\n"
                "import os\n"
                "import unittest\n"
                "marker = Path(os.environ['DESIGN_DNA_HOOK_MARKER'])\n"
                "count = int(marker.read_text(encoding='utf-8')) if marker.exists() else 0\n"
                "marker.write_text(str(count + 1), encoding='utf-8')\n"
                "unittest.TestLoader.discover = lambda self, *args, **kwargs: unittest.TestSuite()\n",
                encoding="utf-8",
            )
            hook_environment = {
                "PYTHONPATH": str(injected),
                "DESIGN_DNA_HOOK_MARKER": str(marker),
            }
            rejected_output = root / "nonisolated-attestation.json"
            rejected = run_attestation_cli(
                plugin,
                rejected_output,
                isolated=False,
                environment_overrides=hook_environment,
            )
            self.assertEqual(rejected.returncode, 2, rejected.stderr)
            self.assertTrue(marker.is_file())
            self.assertEqual(marker.read_text(encoding="utf-8"), "1")
            self.assertFalse(rejected_output.exists())
            rejected_payload = json.loads(rejected.stdout)
            self.assertFalse(rejected_payload["ok"])
            self.assertEqual(
                rejected_payload["failures"][0]["code"],
                "test-attestation-isolation-required",
            )

            output = root / "isolated-attestation.json"
            accepted = run_attestation_cli(
                plugin,
                output,
                isolated=True,
                environment_overrides=hook_environment,
            )
            self.assertEqual(
                accepted.returncode,
                0,
                accepted.stdout + accepted.stderr,
            )
            # ``-I -S`` prevents the external hook from running in both the
            # attester and its release-runner child.  It cannot replace real
            # discovery with its injected empty suite.
            self.assertEqual(marker.read_text(encoding="utf-8"), "1")
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(record["result"]["tests_run"], 2)
            self.assertEqual(
                record["command"],
                [
                    attest_tests.PYTHON_EXECUTABLE_TOKEN,
                    "-I",
                    "-S",
                    "-B",
                    attest_tests.RELEASE_TEST_RUNNER,
                ],
            )

    def test_release_runner_prevents_child_python_bytecode_residue(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_release_runner_fixture(
                Path(temporary),
                "import subprocess\n"
                "import sys\n"
                "import unittest\n"
                "from pathlib import Path\n\n"
                "class ChildPython(unittest.TestCase):\n"
                "    def test_child_process(self):\n"
                "        completed = subprocess.run(\n"
                "            [sys.executable, '-c', 'import child_target'],\n"
                "            cwd=Path(__file__).parent,\n"
                "            capture_output=True,\n"
                "            text=True,\n"
                "            check=False,\n"
                "        )\n"
                "        self.assertEqual(completed.returncode, 0, completed.stderr)\n",
            )
            child = (
                plugin
                / "maintainer"
                / "tests"
                / "child_target.py"
            )
            child.write_text("MARKER = 'child'\n", encoding="utf-8")
            completed = run_release_runner(
                plugin,
                inherit_bytecode_guard=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )
            self.assertFalse(
                (plugin / "maintainer" / "tests" / "__pycache__").exists()
            )

    def test_release_runner_returns_nonzero_for_unsuccessful_suite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_release_runner_fixture(
                Path(temporary),
                "import unittest\n\n"
                "class Failing(unittest.TestCase):\n"
                "    def test_failure(self):\n"
                "        self.fail('intentional release runner failure')\n",
            )
            completed = run_release_runner(plugin)
            self.assertEqual(completed.returncode, 1, completed.stderr)
            self.assertIn("FAILED (failures=1)", completed.stderr)

    def test_parser_rejects_docstring_bearing_skip_output(self) -> None:
        result = subprocess.CompletedProcess(
            [sys.executable, "-B", "runner.py"],
            0,
            stdout=b"",
            stderr=(
                "test_two (suite.Case.test_two)\n"
                "A docstring separates the identity and result. ... skipped 'fixture'\n"
                "\n"
                "----------------------------------------------------------------------\n"
                "Ran 1 test in 0.010s\n"
                "\n"
                "OK (skipped=1)\n"
            ).encode("utf-8"),
        )
        with self.assertRaises(attest_tests.ToolFailure) as raised:
            attest_tests.parse_unittest_result(result)
        self.assertEqual(
            raised.exception.issue.code,
            "test-attestation-skip-identity-incomplete",
        )

    def test_release_skip_requires_exact_environment_and_evidence_waiver(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))
            shutil.copy2(
                SCHEMAS / "test-skip-waivers.schema.json",
                plugin
                / "maintainer"
                / "schemas"
                / "test-skip-waivers.schema.json",
            )
            evidence = (
                plugin
                / "maintainer"
                / "attestations"
                / "skip-evidence"
                / "junction-check.txt"
            )
            evidence.parent.mkdir(parents=True)
            evidence.write_text(
                "Independent platform-specific branch evidence.\n",
                encoding="utf-8",
            )
            waiver = (
                plugin
                / "maintainer"
                / "attestations"
                / "skip-waivers"
                / "windows-junction.json"
            )
            waiver.parent.mkdir(parents=True)
            now = datetime.now(timezone.utc)
            waiver_payload = {
                "schema_version": 1,
                "record_type": "design-dna-test-skip-waivers",
                "approved_at": (now - timedelta(minutes=1)).isoformat(),
                "expires_at": (now + timedelta(days=1)).isoformat(),
                "owner": "release-reviewer",
                "applicability": (
                    attest_tests.current_waiver_environment()
                ),
                "inputs": attest_tests.attested_input_hashes(plugin),
                "waivers": [
                    {
                        "test_id": "suite.Case.test_two",
                        "reason": (
                            "This exact environment cannot exercise the "
                            "platform branch directly."
                        ),
                        "compensating_evidence": [
                            {
                                "path": (
                                    "maintainer/attestations/skip-evidence/"
                                    "junction-check.txt"
                                ),
                                "sha256": hashlib.sha256(
                                    evidence.read_bytes()
                                ).hexdigest(),
                            }
                        ],
                    }
                ],
            }
            waiver.write_text(
                json.dumps(waiver_payload, indent=2) + "\n",
                encoding="utf-8",
            )

            def skipped_runner(
                _selected_plugin: Path,
                command: list[str],
            ) -> subprocess.CompletedProcess[bytes]:
                return fake_unittest_result(command, skipped=True)

            unwaived = attest_tests.create_attestation(
                plugin,
                runner=skipped_runner,
            )
            unwaived_manifest = {
                "generated_at": after_timestamp(
                    unwaived["completed_at"],
                    seconds=1,
                )
            }
            self.assertIn(
                "release-test-skip-waiver-missing",
                {
                    item["code"]
                    for item in audit_package.test_attestation_failures(
                        unwaived,
                        plugin,
                        SCHEMAS / "test-attestation.schema.json",
                        unwaived_manifest,
                    )
                },
            )

            waived = attest_tests.create_attestation(
                plugin,
                runner=skipped_runner,
                skip_waiver_path=waiver,
            )
            manifest = {
                "generated_at": after_timestamp(
                    waived["completed_at"],
                    seconds=1,
                )
            }
            self.assertEqual(
                audit_package.test_attestation_failures(
                    waived,
                    plugin,
                    SCHEMAS / "test-attestation.schema.json",
                    manifest,
                ),
                [],
            )
            evidence.write_text("drifted evidence\n", encoding="utf-8")
            self.assertIn(
                "release-test-skip-waiver-evidence-drift",
                {
                    item["code"]
                    for item in audit_package.test_attestation_failures(
                        waived,
                        plugin,
                        SCHEMAS / "test-attestation.schema.json",
                        manifest,
                    )
                },
            )

    def test_attestation_hashes_exclude_but_reject_compiled_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))
            baseline = attest_tests.attested_input_hashes(plugin)
            scripts = plugin / "maintainer" / "scripts"
            tests = plugin / "maintainer" / "tests"
            cache = scripts / "__pycache__"
            cache.mkdir()
            (cache / "tool.pyc").write_bytes(b"tool")
            loose = tests / "suite.pyo"
            loose.write_bytes(b"suite")

            self.assertEqual(
                attest_tests.identity_group_sha256(
                    plugin,
                    ("maintainer/scripts",),
                ),
                baseline["tooling_sha256"],
            )
            self.assertEqual(
                attest_tests.test_execution_input_sha256(plugin),
                baseline["tests_sha256"],
            )
            with self.assertRaises(attest_tests.ToolFailure) as raised:
                attest_tests.attested_input_hashes(plugin)
            self.assertEqual(
                raised.exception.issue.code,
                "test-attestation-compiled-python-residue",
            )
            self.assertEqual(Path(raised.exception.issue.path), cache)

    def test_attestation_binds_the_runtime_under_test(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))
            before = attest_tests.attested_input_hashes(plugin)
            runtime = plugin / "skills" / "design-dna" / "SKILL.md"
            runtime.write_text(
                runtime.read_text(encoding="utf-8") + "\nRuntime drift.\n",
                encoding="utf-8",
            )
            after = attest_tests.attested_input_hashes(plugin)
            self.assertNotEqual(
                before["runtime_sha256"],
                after["runtime_sha256"],
            )
            self.assertEqual(
                {
                    key for key in before if before[key] != after[key]
                },
                {"runtime_sha256", "tests_sha256"},
            )

    def test_attestation_binds_executed_runtime_tests_and_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))
            before = attest_tests.attested_input_hashes(plugin)
            runtime_test = (
                plugin
                / "skills"
                / "design-dna"
                / "tests"
                / "test_connected_public_experience.py"
            )
            runtime_test.write_text(
                "# exact runtime CPE execution coverage\n",
                encoding="utf-8",
            )
            after_test = attest_tests.attested_input_hashes(plugin)
            self.assertEqual(
                {
                    key for key in before if before[key] != after_test[key]
                },
                {"runtime_sha256", "tests_sha256"},
            )

            runtime_script = (
                plugin
                / "skills"
                / "design-dna"
                / "scripts"
                / "connected_public_experience_audit.py"
            )
            runtime_script.write_text(
                "# exact runtime CPE script execution coverage\n",
                encoding="utf-8",
            )
            after_script = attest_tests.attested_input_hashes(plugin)
            self.assertEqual(
                {
                    key for key in after_test if after_test[key] != after_script[key]
                },
                {"runtime_sha256", "tests_sha256"},
            )

    def test_attestation_binds_nonruntime_execution_surfaces_and_detects_drift(
        self,
    ) -> None:
        cases = (
            ("Codex plugin manifest", ".codex-plugin/plugin.json"),
            ("top-level README", "README.md"),
            ("documentation tree", "docs/QUICK_START.md"),
            ("CI workflow", ".github/workflows/ci.yml"),
            (
                "validator trust policy",
                "maintainer/trust/codex-plugin-validator.json",
            ),
            (
                "evaluation fixture",
                "maintainer/evals/fixtures/behavioral-cases.json",
            ),
            (
                "compatibility matrix",
                "maintainer/compatibility/matrix.yml",
            ),
        )

        def runner(
            _selected_plugin: Path,
            command: list[str],
        ) -> subprocess.CompletedProcess[bytes]:
            return fake_unittest_result(command)

        for label, relative in cases:
            with self.subTest(surface=label), tempfile.TemporaryDirectory() as temporary:
                plugin = make_attestation_fixture(Path(temporary))
                record = attest_tests.create_attestation(plugin, runner=runner)
                before = dict(record["inputs"])
                target = plugin / relative
                original = target.read_text(encoding="utf-8")
                # Preserve JSON validity while still changing its exact bytes.
                suffix = "\n" if target.suffix == ".json" else "\n# source drift\n"
                target.write_text(original + suffix, encoding="utf-8")
                after = attest_tests.attested_input_hashes(plugin)
                self.assertEqual(
                    {
                        key for key in before if before[key] != after[key]
                    },
                    {"tests_sha256"},
                )
                manifest = {
                    "generated_at": after_timestamp(
                        record["completed_at"],
                        seconds=1,
                    )
                }
                failures = audit_package.test_attestation_failures(
                    record,
                    plugin,
                    SCHEMAS / "test-attestation.schema.json",
                    manifest,
                )
                self.assertIn(
                    "release-test-attestation-input-drift",
                    {item["code"] for item in failures},
                )

    def test_attestation_missing_declared_execution_surfaces_fail_closed(
        self,
    ) -> None:
        cases = (
            ".codex-plugin/plugin.json",
            "README.md",
            "docs",
            ".github/workflows/ci.yml",
            "maintainer/trust/codex-plugin-validator.json",
            "maintainer/evals/fixtures",
            "maintainer/compatibility/matrix.yml",
        )
        for relative in cases:
            with self.subTest(surface=relative), tempfile.TemporaryDirectory() as temporary:
                plugin = make_attestation_fixture(Path(temporary))
                target = plugin / relative
                if target.is_dir():
                    for child in target.iterdir():
                        child.unlink()
                    target.rmdir()
                else:
                    target.unlink()
                with self.assertRaises(attest_tests.ToolFailure) as raised:
                    attest_tests.attested_input_hashes(plugin)
                self.assertEqual(
                    raised.exception.issue.code,
                    "test-attestation-input-missing",
                )

    def test_attestation_execution_manifest_is_bounded_and_non_circular(
        self,
    ) -> None:
        manifest_paths = {
            relative
            for _label, relative, _kind
            in attest_tests.TEST_EXECUTION_INPUT_MANIFEST
        }
        self.assertIn(".codex-plugin/plugin.json", manifest_paths)
        self.assertIn("README.md", manifest_paths)
        self.assertIn("docs", manifest_paths)
        self.assertIn(".github/workflows/ci.yml", manifest_paths)
        self.assertIn("maintainer/trust/codex-plugin-validator.json", manifest_paths)
        self.assertIn("maintainer/evals/fixtures", manifest_paths)
        self.assertIn("maintainer/compatibility/matrix.yml", manifest_paths)
        for path in manifest_paths:
            self.assertFalse(
                any(
                    attest_tests._execution_input_paths_overlap(path, derived)
                    for derived in attest_tests.DERIVED_EXECUTION_OUTPUT_PATHS
                ),
                path,
            )

        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))
            before = attest_tests.attested_input_hashes(plugin)
            (plugin / "local-scratch-not-a-release-input.txt").write_text(
                "untracked local scratch\n",
                encoding="utf-8",
            )
            self.assertEqual(
                attest_tests.attested_input_hashes(plugin),
                before,
            )

    def test_dependency_attestation_rejects_an_incomplete_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))
            requirements = (
                plugin / "maintainer" / "requirements-dev.txt"
            )
            requirements.write_text(
                "\n".join(
                    line
                    for line in requirements.read_text(
                        encoding="utf-8"
                    ).splitlines()
                    if not line.casefold().startswith("attrs==")
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaises(attest_tests.ToolFailure) as raised:
                attest_tests.pinned_dependencies(plugin)
            self.assertEqual(
                raised.exception.issue.code,
                "test-attestation-dependency-closure-incomplete",
            )

    def test_records_exact_suite_environment_counts_output_and_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))

            def runner(
                selected_plugin: Path,
                command: list[str],
            ) -> subprocess.CompletedProcess[bytes]:
                self.assertEqual(selected_plugin, plugin)
                self.assertEqual(
                    command[1:],
                    list(attest_tests.UNITTEST_ARGUMENTS),
                )
                return fake_unittest_result(command, skipped=True)

            record = attest_tests.create_attestation(plugin, runner=runner)
            self.assertEqual(
                record["command"][0],
                attest_tests.PYTHON_EXECUTABLE_TOKEN,
            )
            self.assertEqual(
                record["command"],
                [
                    attest_tests.PYTHON_EXECUTABLE_TOKEN,
                    *attest_tests.UNITTEST_ARGUMENTS,
                ],
            )
            self.assertEqual(
                record["python"]["executable"],
                attest_tests.PYTHON_EXECUTABLE_TOKEN,
            )
            self.assertEqual(
                record["python"]["executable_sha256"],
                attest_tests.current_python_executable_sha256(),
            )
            schema = json.loads(
                (
                    SCHEMAS / "test-attestation.schema.json"
                ).read_text(encoding="utf-8")
            )
            errors = list(
                Draft202012Validator(
                    schema,
                    format_checker=FormatChecker(),
                ).iter_errors(record)
            )
            self.assertEqual(errors, [])
            self.assertEqual(record["result"]["status"], "passed")
            self.assertEqual(record["result"]["tests_run"], 2)
            self.assertEqual(record["result"]["skipped"], 1)
            self.assertEqual(
                record["result"]["skipped_test_ids"],
                ["suite.Case.test_two"],
            )
            self.assertIsNone(record["skip_waiver"])
            self.assertEqual(
                record["inputs"],
                attest_tests.attested_input_hashes(plugin),
            )
            self.assertEqual(
                record["dependencies"],
                attest_tests.pinned_dependencies(plugin),
            )

    def test_exact_suite_uses_the_bounded_one_hour_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = Path(temporary).resolve()
            command = [sys.executable, *attest_tests.UNITTEST_ARGUMENTS]
            completed = subprocess.CompletedProcess(
                command,
                returncode=0,
                stdout=b"",
                stderr=b"Ran 1 test in 0.001s\n\nOK\n",
            )
            with patch.object(
                attest_tests.subprocess,
                "run",
                return_value=completed,
            ) as mocked_run:
                observed = attest_tests.run_exact_suite(plugin, command)
            self.assertIs(observed, completed)
            self.assertEqual(
                mocked_run.call_args.kwargs["timeout"],
                attest_tests.TEST_SUITE_TIMEOUT_SECONDS,
            )
            self.assertEqual(
                attest_tests.TEST_SUITE_TIMEOUT_SECONDS,
                3600,
            )
            environment = mocked_run.call_args.kwargs["env"]
            self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")
            self.assertNotIn("PYTHONPATH", environment)
            self.assertNotIn("PYTHONHOME", environment)
            self.assertNotIn("VIRTUAL_ENV", environment)

    def test_attestation_redacts_local_roots_and_binds_python_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))

            def path_reporting_runner(
                _selected_plugin: Path,
                command: list[str],
            ) -> subprocess.CompletedProcess[bytes]:
                result = fake_unittest_result(command)
                disclosure = (
                    f"plugin={plugin}\n"
                    f"home={Path.home()}\n"
                    f"python={sys.executable}\n"
                    "reference=https://example.test/home/example\n"
                ).encode("utf-8")
                return subprocess.CompletedProcess(
                    command,
                    result.returncode,
                    stdout=disclosure,
                    stderr=result.stderr,
                )

            record = attest_tests.create_attestation(
                plugin,
                runner=path_reporting_runner,
            )
            serialized = json.dumps(record, sort_keys=True)
            self.assertNotIn(str(plugin), serialized)
            self.assertNotIn(str(Path.home()), serialized)
            self.assertNotIn(sys.executable, serialized)
            self.assertNotIn(Path.home().name.casefold(), serialized.casefold())
            self.assertIn("<PLUGIN_ROOT>", record["output"]["stdout"])
            self.assertIn("<HOME>", record["output"]["stdout"])
            self.assertIn(
                "https://example.test/home/example",
                record["output"]["stdout"],
            )

            manifest = {
                "generated_at": after_timestamp(
                    record["completed_at"],
                    seconds=1,
                )
            }
            tampered = copy.deepcopy(record)
            tampered["python"]["executable_sha256"] = "0" * 64
            failures = audit_package.test_attestation_failures(
                tampered,
                plugin,
                SCHEMAS / "test-attestation.schema.json",
                manifest,
            )
            self.assertIn(
                "release-test-attestation-python-mismatch",
                {item["code"] for item in failures},
            )

    def test_release_attestation_path_gate_ignores_http_urls(self) -> None:
        self.assertEqual(
            audit_package.distributed_record_local_path_failures(
                {
                    "reference": (
                        "https://example.test/C:/Users/example/"
                        "and/https://example.test/home/example"
                    )
                },
                "fixture.json",
            ),
            [],
        )
        failures = audit_package.distributed_record_local_path_failures(
            {"captured": r"C:\Users\example\private.txt"},
            "fixture.json",
        )
        self.assertEqual(
            {item["code"] for item in failures},
            {"release-attestation-local-path"},
        )

    def test_unstable_inputs_never_replace_an_existing_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))
            output = Path(temporary) / "attestation.json"
            output.write_text('{"previous":"record"}\n', encoding="utf-8")

            def mutating_runner(
                selected_plugin: Path,
                command: list[str],
            ) -> subprocess.CompletedProcess[bytes]:
                test_input = (
                    selected_plugin
                    / "maintainer"
                    / "tests"
                    / "tests.txt"
                )
                test_input.write_text("changed during run\n", encoding="utf-8")
                return fake_unittest_result(command)

            with self.assertRaises(attest_tests.ToolFailure) as raised:
                record = attest_tests.create_attestation(
                    plugin,
                    runner=mutating_runner,
                )
                attest_tests.atomic_write_json(output, record)
            self.assertEqual(
                raised.exception.issue.code,
                "test-attestation-input-unstable",
            )
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                '{"previous":"record"}\n',
            )

    def test_release_semantics_reject_failure_drift_dependency_and_staleness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))

            def failed_runner(
                _selected_plugin: Path,
                command: list[str],
            ) -> subprocess.CompletedProcess[bytes]:
                return fake_unittest_result(command, passed=False)

            failed = attest_tests.create_attestation(
                plugin,
                runner=failed_runner,
            )
            manifest = {
                "generated_at": after_timestamp(
                    failed["completed_at"],
                    seconds=1,
                )
            }
            failures = audit_package.test_attestation_failures(
                failed,
                plugin,
                SCHEMAS / "test-attestation.schema.json",
                manifest,
            )
            self.assertIn(
                "release-test-attestation-failed",
                {item["code"] for item in failures},
            )

            def passed_runner(
                _selected_plugin: Path,
                command: list[str],
            ) -> subprocess.CompletedProcess[bytes]:
                return fake_unittest_result(command)

            valid = attest_tests.create_attestation(
                plugin,
                runner=passed_runner,
            )
            manifest = {
                "generated_at": after_timestamp(
                    valid["completed_at"],
                    seconds=1,
                )
            }
            self.assertEqual(
                audit_package.test_attestation_failures(
                    valid,
                    plugin,
                    SCHEMAS / "test-attestation.schema.json",
                    manifest,
                ),
                [],
            )
            drifted = copy.deepcopy(valid)
            drifted["inputs"]["tests_sha256"] = "0" * 64
            drifted["dependencies"][0]["installed"] = "0.0.0"
            drifted["output"]["sha256"] = "f" * 64
            failures = audit_package.test_attestation_failures(
                drifted,
                plugin,
                SCHEMAS / "test-attestation.schema.json",
                {
                    "generated_at": after_timestamp(
                        valid["completed_at"],
                        hours=25,
                    )
                },
            )
            codes = {item["code"] for item in failures}
            self.assertIn("release-test-attestation-input-drift", codes)
            self.assertIn(
                "release-test-attestation-dependency-mismatch",
                codes,
            )
            self.assertIn("release-test-attestation-output-drift", codes)
            self.assertIn("release-test-attestation-stale", codes)


class CodexPluginValidationProofTests(unittest.TestCase):
    def test_atomic_attestation_write_creates_missing_output_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = (
                Path(temporary)
                / "plugin"
                / "maintainer"
                / "attestations"
                / "codex-plugin-validation.json"
            )
            payload = {"status": "fixture"}

            attest_codex_plugin.atomic_write_json(output, payload)

            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), payload)
            self.assertTrue(output.parent.is_dir())

    def test_release_proof_replays_exact_external_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validator_path = make_fake_codex_validator(root / "external")
            plugin = make_codex_plugin_fixture(root, validator_path)
            record = attest_codex_plugin.create_attestation(
                plugin,
                validator_path,
            )
            manifest = {
                "generated_at": after_timestamp(
                    record["created_at"],
                    seconds=1,
                )
            }
            failures = audit_package.codex_plugin_attestation_failures(
                record,
                plugin,
                SCHEMAS
                / "codex-plugin-validation-attestation.schema.json",
                manifest,
                {"version": "3.0.0"},
                validator_path=validator_path,
            )
        self.assertEqual(failures, [])

    def test_strict_audit_accepts_truthful_codex_pass_with_live_validator(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validator_path = make_fake_codex_validator(root / "external")
            trust_fixture = make_codex_plugin_fixture(
                root / "trust-fixture",
                validator_path,
            )
            copied = root / "candidate"
            shutil.copytree(
                PLUGIN,
                copied,
                copy_function=shutil.copyfile,
                ignore=shutil.ignore_patterns(
                    ".git",
                    "__pycache__",
                    "*.pyc",
                    "*.pyo",
                ),
            )
            trust_relative = Path(
                "maintainer/trust/codex-plugin-validator.json"
            )
            shutil.copy2(
                trust_fixture / trust_relative,
                copied / trust_relative,
            )

            attestation = attest_codex_plugin.create_attestation(
                copied,
                validator_path,
            )
            attestation_path = (
                copied
                / "maintainer"
                / "attestations"
                / "codex-plugin-validation.json"
            )
            attest_codex_plugin.atomic_write_json(
                attestation_path,
                attestation,
            )

            matrix_path = (
                copied / "maintainer" / "compatibility" / "matrix.yml"
            )
            matrix = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
            matrix["hosts"]["codex"]["static_validation"] = "passed"
            matrix_path.write_text(
                yaml.safe_dump(matrix, sort_keys=False),
                encoding="utf-8",
            )

            manifest = audit_package.package_manifest(
                copied / "skills" / "design-dna"
            )
            manifest_path = copied / "maintainer" / "release-manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            captured = io.StringIO()
            arguments = [
                "audit_package.py",
                "--plugin-root",
                str(copied),
                "--home",
                str(root),
                "--codex-validator",
                str(validator_path),
                "--release",
            ]
            with patch.object(sys, "argv", arguments):
                with contextlib.redirect_stdout(captured):
                    status = audit_package.main()

            self.assertEqual(status, 1)
            payload = json.loads(captured.getvalue())
            codes = {
                finding["code"]
                for finding in payload["failures"]
                if isinstance(finding, dict) and "code" in finding
            }
            self.assertNotIn(
                "release-codex-validator-live-path-required",
                codes,
            )
            self.assertFalse(
                any(code.startswith("release-codex-plugin-") for code in codes),
                codes,
            )

    def test_release_proof_rejects_tampered_output_and_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validator_path = make_fake_codex_validator(root / "external")
            plugin = make_codex_plugin_fixture(root, validator_path)
            record = attest_codex_plugin.create_attestation(
                plugin,
                validator_path,
            )
            manifest = {
                "generated_at": after_timestamp(
                    record["created_at"],
                    seconds=1,
                )
            }
            tampered = copy.deepcopy(record)
            tampered["output"]["exact_success_line_observed"] = False
            tampered["inputs"]["skills_tree"]["sha256"] = "0" * 64
            tampered["validator"]["trust_policy_sha256"] = "0" * 64
            failures = audit_package.codex_plugin_attestation_failures(
                tampered,
                plugin,
                SCHEMAS
                / "codex-plugin-validation-attestation.schema.json",
                manifest,
                {"version": "3.0.0"},
                validator_path=validator_path,
            )
        codes = {item["code"] for item in failures}
        self.assertIn(
            "release-codex-plugin-attestation-input-drift",
            codes,
        )
        self.assertIn(
            "release-codex-plugin-attestation-output-invalid",
            codes,
        )
        self.assertIn(
            "release-codex-plugin-attestation-trust-drift",
            codes,
        )
        self.assertIn(
            "release-codex-plugin-attestation-live-drift",
            codes,
        )

    def test_current_audit_rejects_backdated_record_under_expired_pin(
        self,
    ) -> None:
        now = datetime.now(timezone.utc)
        reviewed = now - timedelta(days=30)
        due = now - timedelta(days=1)
        created = after_timestamp(
            reviewed.isoformat().replace("+00:00", "Z"),
            seconds=1,
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validator_path = make_fake_codex_validator(root / "external")
            plugin = make_codex_plugin_fixture(
                root,
                validator_path,
                reviewed_at=reviewed,
                review_due=due,
            )
            record = attest_codex_plugin.create_attestation(
                plugin,
                validator_path,
                created_at=created,
                require_current_trust=False,
            )
            failures = audit_package.codex_plugin_attestation_failures(
                record,
                plugin,
                SCHEMAS
                / "codex-plugin-validation-attestation.schema.json",
                {
                    "generated_at": after_timestamp(
                        record["created_at"],
                        seconds=1,
                    )
                },
                {"version": "3.0.0"},
            )
        self.assertIn(
            "release-codex-plugin-validator-trust-overdue",
            {item["code"] for item in failures},
        )


class RouteVerificationProofTests(unittest.TestCase):
    def test_atomic_route_record_matches_schema_and_live_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = root / "plugin"
            canonical = plugin / "skills" / "design-dna"
            roots = [root / "codex-skills", root / "claude-skills"]
            expected = [
                roots[0] / "design-dna",
                roots[1] / "design-dna",
            ]
            write_skill(canonical)
            for route in expected:
                write_skill(route)
            output = (
                plugin
                / "maintainer"
                / "attestations"
                / "route-verification.json"
            )
            missing_home = run_detect(
                canonical,
                roots,
                expected,
                output,
                None,
            )
            self.assertEqual(
                missing_home.returncode,
                2,
                missing_home.stdout + missing_home.stderr,
            )
            self.assertEqual(
                json.loads(missing_home.stdout)["failures"][0]["code"],
                "route-verification-home-required",
            )
            self.assertFalse(output.exists())
            result = run_detect(canonical, roots, expected, output, root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            record = json.loads(output.read_text(encoding="utf-8"))
            schema = json.loads(
                (
                    SCHEMAS / "route-verification.schema.json"
                ).read_text(encoding="utf-8")
            )
            errors = list(
                Draft202012Validator(
                    schema,
                    format_checker=FormatChecker(),
                ).iter_errors(record)
            )
            self.assertEqual(errors, [])
            serialized = json.dumps(record, sort_keys=True)
            self.assertEqual(record["canonical"], "skills/design-dna")
            self.assertTrue(
                all(path.startswith("~/") for path in record["roots"])
            )
            self.assertTrue(
                all(path.startswith("~/") for path in record["expected"])
            )
            self.assertTrue(
                all(
                    route["path"].startswith("~/")
                    for route in record["routes"]
                )
            )
            self.assertNotIn(str(root), serialized)
            self.assertNotIn(Path.home().name.casefold(), serialized.casefold())
            compatibility = {
                "discovery_roots": [str(path) for path in roots],
                "hosts": {
                    "codex": {
                        "designed": True,
                        "discovery_route": str(expected[0]),
                    },
                    "claude_code": {
                        "designed": True,
                        "discovery_route": str(expected[1]),
                    },
                }
            }
            failures = audit_package.route_verification_failures(
                record,
                plugin,
                SCHEMAS / "route-verification.schema.json",
                {
                    "generated_at": after_timestamp(
                        record["verified_at"],
                        seconds=1,
                    )
                },
                compatibility,
                home=root,
            )
            self.assertEqual(failures, [])
            tampered = copy.deepcopy(record)
            tampered["roots"][0] = "~/tampered-route-root"
            failures = audit_package.route_verification_failures(
                tampered,
                plugin,
                SCHEMAS / "route-verification.schema.json",
                {
                    "generated_at": after_timestamp(
                        record["verified_at"],
                        seconds=1,
                    )
                },
                compatibility,
                home=root,
            )
            self.assertIn(
                "release-route-roots-mismatch",
                {item["code"] for item in failures},
            )

            schema_invalid = copy.deepcopy(record)
            schema_invalid["roots"][0] = str(roots[0])
            self.assertFalse(
                Draft202012Validator(schema).is_valid(schema_invalid)
            )

    def test_scan_only_discovery_root_still_catches_an_unexpected_route(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = root / "plugin"
            canonical = plugin / "skills" / "design-dna"
            installed_root = root / "installed-skills"
            scan_only_root = root / "plugin-cache"
            expected = installed_root / "design-dna"
            output = (
                plugin
                / "maintainer"
                / "attestations"
                / "route-verification.json"
            )
            write_skill(canonical)
            write_skill(expected)
            scan_only_root.mkdir()
            generated = run_detect(
                canonical,
                [installed_root, scan_only_root],
                [expected],
                output,
                root,
            )
            self.assertEqual(
                generated.returncode,
                0,
                generated.stdout + generated.stderr,
            )
            record = json.loads(output.read_text(encoding="utf-8"))
            write_skill(scan_only_root / "cached-copy")
            compatibility = {
                "discovery_roots": [
                    str(installed_root),
                    str(scan_only_root),
                ],
                "hosts": {
                    "codex": {
                        "designed": True,
                        "discovery_route": str(expected),
                    }
                },
            }
            failures = audit_package.route_verification_failures(
                record,
                plugin,
                SCHEMAS / "route-verification.schema.json",
                {
                    "generated_at": after_timestamp(
                        record["verified_at"],
                        seconds=1,
                    )
                },
                compatibility,
                home=root,
            )
            self.assertIn(
                "release-duplicate-route-state",
                {item["code"] for item in failures},
            )

    def test_route_proof_rejects_duplicate_deleted_drifted_and_stale_state(self) -> None:
        for mutation in ("duplicate", "deleted", "drifted", "stale"):
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                plugin = root / "plugin"
                canonical = plugin / "skills" / "design-dna"
                discovery = root / "skills"
                expected = discovery / "design-dna"
                write_skill(canonical)
                write_skill(expected)
                output = (
                    plugin
                    / "maintainer"
                    / "attestations"
                    / "route-verification.json"
                )
                generated = run_detect(
                    canonical,
                    [discovery],
                    [expected],
                    output,
                    root,
                )
                self.assertEqual(
                    generated.returncode,
                    0,
                    generated.stdout + generated.stderr,
                )
                record = json.loads(output.read_text(encoding="utf-8"))
                compatibility = {
                    "discovery_roots": [str(discovery)],
                    "hosts": {
                        "codex": {
                            "designed": True,
                            "discovery_route": str(expected),
                        }
                    }
                }
                manifest = {
                    "generated_at": after_timestamp(
                        record["verified_at"],
                        seconds=1,
                    )
                }
                expected_code = ""
                if mutation == "duplicate":
                    write_skill(discovery / "old-copy")
                    expected_code = "release-duplicate-route-state"
                elif mutation == "deleted":
                    shutil.rmtree(expected)
                    expected_code = "release-route-deleted"
                elif mutation == "drifted":
                    (expected / "SKILL.md").write_text(
                        (
                            expected / "SKILL.md"
                        ).read_text(encoding="utf-8")
                        + "\ndrift\n",
                        encoding="utf-8",
                    )
                    expected_code = "release-installed-route-drift"
                else:
                    manifest = {
                        "generated_at": after_timestamp(
                            record["verified_at"],
                            hours=25,
                        )
                    }
                    expected_code = "release-route-verification-stale"
                failures = audit_package.route_verification_failures(
                    record,
                    plugin,
                    SCHEMAS / "route-verification.schema.json",
                    manifest,
                    compatibility,
                    home=root,
                )
                self.assertIn(
                    expected_code,
                    {item["code"] for item in failures},
                )

    def test_failed_route_scan_does_not_replace_prior_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical"
            discovery = root / "skills"
            expected = discovery / "design-dna"
            duplicate = discovery / "duplicate"
            output = root / "route-verification.json"
            write_skill(canonical)
            write_skill(expected)
            write_skill(duplicate)
            output.write_text('{"previous":"record"}\n', encoding="utf-8")
            result = run_detect(
                canonical,
                [discovery],
                [expected],
                output,
                root,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                '{"previous":"record"}\n',
            )


class AuditProofModeTests(unittest.TestCase):
    def test_install_lifecycle_release_gate_binds_live_inputs(self) -> None:
        record = attest_install_lifecycle.create_attestation(PLUGIN)
        manifest = {
            "generated_at": after_timestamp(
                record["created_at"],
                seconds=1,
            )
        }
        release = json.loads(
            (
                PLUGIN / "skills" / "design-dna" / "release.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            audit_package.install_lifecycle_attestation_failures(
                record,
                PLUGIN,
                SCHEMAS / "install-lifecycle-attestation.schema.json",
                manifest,
                release,
            ),
            [],
        )
        drifted = copy.deepcopy(record)
        drifted["inputs"]["runtime"]["sha256"] = "0" * 64
        self.assertIn(
            "release-install-lifecycle-input-drift",
            {
                finding["code"]
                for finding in (
                    audit_package.install_lifecycle_attestation_failures(
                        drifted,
                        PLUGIN,
                        SCHEMAS
                        / "install-lifecycle-attestation.schema.json",
                        manifest,
                        release,
                    )
                )
            },
        )

    def test_absolute_compatibility_routes_are_never_release_portable(self) -> None:
        compatibility = yaml.safe_load(
            (
                PLUGIN
                / "maintainer"
                / "compatibility"
                / "matrix.yml"
            ).read_text(encoding="utf-8")
        )
        compatibility["discovery_roots"][0] = r"C:\isolated\skills"
        compatibility["hosts"]["codex"]["discovery_route"] = (
            r"C:\isolated\skills\design-dna"
        )
        failures = audit_package.compatibility_environment_failures(
            compatibility,
            PLUGIN,
        )
        self.assertEqual(
            sum(
                finding["code"] == "compatibility-route-not-portable"
                for finding in failures
            ),
            2,
        )

    def test_ci_pass_schema_requires_a_canonical_import_record(self) -> None:
        compatibility = yaml.safe_load(
            (
                PLUGIN
                / "maintainer"
                / "compatibility"
                / "matrix.yml"
            ).read_text(encoding="utf-8")
        )
        schema = json.loads(
            (
                SCHEMAS / "compatibility.schema.json"
            ).read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        )
        self.assertEqual(list(validator.iter_errors(compatibility)), [])
        ci_record = next(
            record
            for record in compatibility["environments"]
            if record["id"] == "ci-ubuntu-python-3-10"
        )
        ci_record["checks"]["unit_tests"] = "passed"
        errors = list(validator.iter_errors(compatibility))
        self.assertTrue(
            any(
                list(error.path)[-1:] == ["evidence"]
                and "does not contain items matching" in error.message
                for error in errors
            ),
            errors,
        )
        semantic_codes = {
            finding["code"]
            for finding in audit_package.compatibility_environment_failures(
                compatibility,
                PLUGIN,
            )
        }
        self.assertIn(
            "compatibility-ci-pass-without-run-record",
            semantic_codes,
        )

    def test_local_unit_pass_requires_exact_current_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))
            schema_path = (
                plugin
                / "maintainer"
                / "schemas"
                / "test-attestation.schema.json"
            )
            shutil.copy2(
                SCHEMAS / "test-attestation.schema.json",
                schema_path,
            )

            def runner(
                _selected_plugin: Path,
                command: list[str],
            ) -> subprocess.CompletedProcess[bytes]:
                return fake_unittest_result(command)

            attestation = attest_tests.create_attestation(
                plugin,
                runner=runner,
            )
            attestation_path = (
                plugin
                / "maintainer"
                / "attestations"
                / "test-attestation.json"
            )
            attestation_path.parent.mkdir(parents=True)
            attestation_path.write_text(
                json.dumps(attestation, indent=2) + "\n",
                encoding="utf-8",
            )
            (plugin / "maintainer" / "release-manifest.json").write_text(
                json.dumps({
                    "generated_at": after_timestamp(
                        attestation["completed_at"],
                        seconds=1,
                    ),
                })
                + "\n",
                encoding="utf-8",
            )
            local = {
                "id": "local-fixture",
                "scope": "local_toolchain",
                "python": attestation["python"]["version"],
                "checks": {
                    "package_audit": "pending",
                    "unit_tests": "passed",
                    "installer_lifecycle": "pending",
                    "host_discovery": "not_applicable",
                    "behavioral_eval": "not_applicable",
                    "rendered_review": "pending",
                },
                "evidence": [
                    "maintainer/attestations/test-attestation.json",
                ],
            }
            compatibility = {"environments": [local]}
            codes = {
                finding["code"]
                for finding in audit_package.compatibility_environment_failures(
                    compatibility,
                    plugin,
                )
            }
            self.assertNotIn(
                "compatibility-unit-tests-pass-unbound",
                codes,
            )
            self.assertNotIn(
                "compatibility-unit-tests-pass-invalid",
                codes,
            )

            local["evidence"] = []
            codes = {
                finding["code"]
                for finding in audit_package.compatibility_environment_failures(
                    compatibility,
                    plugin,
                )
            }
            self.assertIn(
                "compatibility-unit-tests-pass-unbound",
                codes,
            )

            local["evidence"] = [
                "maintainer/attestations/test-attestation.json",
            ]
            (
                plugin
                / "skills"
                / "design-dna"
                / "SKILL.md"
            ).write_text(
                "---\n"
                "name: design-dna\n"
                "description: Drifted fixture.\n"
                "---\n\n"
                "# Design DNA\n",
                encoding="utf-8",
            )
            codes = {
                finding["code"]
                for finding in audit_package.compatibility_environment_failures(
                    compatibility,
                    plugin,
                )
            }
            self.assertIn(
                "compatibility-unit-tests-pass-invalid",
                codes,
            )

    def test_local_package_audit_pass_needs_record_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))
            arbitrary_audit = (
                plugin
                / "maintainer"
                / "attestations"
                / "package-audit.json"
            )
            arbitrary_audit.parent.mkdir(parents=True)
            arbitrary_audit.write_text(
                json.dumps({
                    "ok": True,
                    "failures": [],
                    "warnings": [],
                    "details": {},
                })
                + "\n",
                encoding="utf-8",
            )
            compatibility = {
                "environments": [{
                    "id": "local-fixture",
                    "scope": "local_toolchain",
                    "python": platform.python_version(),
                    "checks": {
                        "package_audit": "passed",
                        "unit_tests": "pending",
                        "installer_lifecycle": "pending",
                        "host_discovery": "not_applicable",
                        "behavioral_eval": "not_applicable",
                        "rendered_review": "pending",
                    },
                    "evidence": [
                        "maintainer/attestations/package-audit.json",
                    ],
                }],
            }
            codes = {
                finding["code"]
                for finding in audit_package.compatibility_environment_failures(
                    compatibility,
                    plugin,
                )
            }
            self.assertIn(
                "compatibility-package-audit-pass-unbound",
                codes,
            )

    def test_local_unit_pass_schema_requires_canonical_citation(self) -> None:
        compatibility = yaml.safe_load(
            (
                PLUGIN
                / "maintainer"
                / "compatibility"
                / "matrix.yml"
            ).read_text(encoding="utf-8")
        )
        local = next(
            record
            for record in compatibility["environments"]
            if record["scope"] == "local_toolchain"
        )
        local["checks"]["unit_tests"] = "passed"
        local["checks"]["package_audit"] = "pending"
        local["evidence"].remove(
            "maintainer/attestations/test-attestation.json"
        )
        schema = json.loads(
            (
                SCHEMAS / "compatibility.schema.json"
            ).read_text(encoding="utf-8")
        )
        errors = list(
            Draft202012Validator(
                schema,
                format_checker=FormatChecker(),
            ).iter_errors(compatibility)
        )
        self.assertTrue(
            any(
                list(error.path)[-1:] == ["evidence"]
                and "does not contain items matching" in error.message
                for error in errors
            ),
            errors,
        )

    def test_current_unobserved_ci_matrix_blocks_strict_release(self) -> None:
        compatibility = yaml.safe_load(
            (
                PLUGIN
                / "maintainer"
                / "compatibility"
                / "matrix.yml"
            ).read_text(encoding="utf-8")
        )
        development_failures, development_details = (
            audit_package.ci_contract_failures(
                compatibility,
                PLUGIN,
                SCHEMAS / "ci-run-import.schema.json",
                SCHEMAS / "test-attestation.schema.json",
                {},
                release_mode=False,
            )
        )
        self.assertEqual(development_failures, [])
        self.assertEqual(development_details["required_entries"], 9)
        self.assertEqual(development_details["passed_entries"], 0)
        release_failures, release_details = (
            audit_package.ci_contract_failures(
                compatibility,
                PLUGIN,
                SCHEMAS / "ci-run-import.schema.json",
                SCHEMAS / "test-attestation.schema.json",
                {},
                release_mode=True,
            )
        )
        self.assertEqual(
            sum(
                finding["code"]
                == "release-ci-matrix-entry-unobserved"
                for finding in release_failures
            ),
            9,
        )
        self.assertEqual(release_details["passed_entries"], 0)

    def test_ci_import_binds_provider_artifact_and_extracted_proofs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            (
                plugin,
                compatibility,
                manifest,
                audit_path,
            ) = make_ci_import_fixture(Path(temporary))
            failures, details = audit_package.ci_contract_failures(
                compatibility,
                plugin,
                SCHEMAS / "ci-run-import.schema.json",
                SCHEMAS / "test-attestation.schema.json",
                manifest,
                release_mode=True,
            )
            self.assertEqual(failures, [])
            self.assertEqual(details["required_entries"], 1)
            self.assertEqual(details["passed_entries"], 1)
            self.assertEqual(details["verified_imports"], 1)

            audit_path.write_text(
                audit_path.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            tampered, _details = audit_package.ci_contract_failures(
                compatibility,
                plugin,
                SCHEMAS / "ci-run-import.schema.json",
                SCHEMAS / "test-attestation.schema.json",
                manifest,
                release_mode=True,
            )
            self.assertIn(
                "ci-import-extracted-evidence-mismatch",
                {finding["code"] for finding in tampered},
            )

    def test_proofs_created_before_manifest_are_accepted_after_manifest_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            copied = root / "plugin"
            shutil.copytree(
                PLUGIN,
                copied,
                copy_function=shutil.copyfile,
            )
            attestations = copied / "maintainer" / "attestations"
            if attestations.exists():
                remove_test_tree(attestations)
            attestations.mkdir()

            canonical = copied / "skills" / "design-dna"
            codex_root = root / "codex-skills"
            claude_root = root / "claude-skills"
            scan_only_root = root / "scan-only-cache"
            codex_route = codex_root / "design-dna"
            claude_route = claude_root / "design-dna"
            shutil.copytree(canonical, codex_route)
            shutil.copytree(canonical, claude_route)
            scan_only_root.mkdir()

            matrix_path = copied / "maintainer" / "compatibility" / "matrix.yml"
            matrix = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
            matrix["discovery_roots"] = [
                str(codex_root),
                str(claude_root),
                str(scan_only_root),
            ]
            matrix["hosts"]["codex"]["discovery_route"] = str(codex_route)
            matrix["hosts"]["claude_code"]["discovery_route"] = str(
                claude_route
            )
            matrix_path.write_text(
                yaml.safe_dump(matrix, sort_keys=False),
                encoding="utf-8",
            )

            def runner(
                _selected_plugin: Path,
                command: list[str],
            ) -> subprocess.CompletedProcess[bytes]:
                return fake_unittest_result(command)

            test_record = attest_tests.create_attestation(
                copied,
                runner=runner,
            )
            test_path = attestations / "test-attestation.json"
            attest_tests.atomic_write_json(test_path, test_record)

            route_path = attestations / "route-verification.json"
            routed = run_detect(
                canonical,
                [codex_root, claude_root, scan_only_root],
                [codex_route, claude_route],
                route_path,
                root,
            )
            self.assertEqual(
                routed.returncode,
                0,
                routed.stdout + routed.stderr,
            )
            route_record = json.loads(route_path.read_text(encoding="utf-8"))

            manifest_path = copied / "maintainer" / "release-manifest.json"
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment["PYTHONUTF8"] = "1"
            built = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPTS / "build_manifest.py"),
                    "--skill-root",
                    str(canonical),
                    "--output",
                    str(manifest_path),
                ],
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=environment,
                timeout=120,
            )
            self.assertEqual(
                built.returncode,
                0,
                built.stdout + built.stderr,
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                audit_package.test_attestation_failures(
                    test_record,
                    copied,
                    copied
                    / "maintainer"
                    / "schemas"
                    / "test-attestation.schema.json",
                    manifest,
                ),
                [],
            )
            self.assertEqual(
                audit_package.route_verification_failures(
                    route_record,
                    copied,
                    copied
                    / "maintainer"
                    / "schemas"
                    / "route-verification.schema.json",
                    manifest,
                    matrix,
                    home=root,
                ),
                [],
            )

            manifest["generated_at"] = after_timestamp(
                route_record["verified_at"],
                hours=25,
            )
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            base_audit = [
                sys.executable,
                "-B",
                str(SCRIPTS / "audit_package.py"),
                "--plugin-root",
                str(copied),
                "--home",
                str(root),
            ]
            dev = subprocess.run(
                base_audit,
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=environment,
                timeout=120,
            )
            dev_payload = json.loads(dev.stdout)
            stale_codes = {
                "release-test-attestation-stale",
                "release-route-verification-stale",
            }
            self.assertTrue(
                stale_codes
                <= {item["code"] for item in dev_payload["warnings"]}
            )
            self.assertTrue(
                stale_codes.isdisjoint(
                    {item["code"] for item in dev_payload["failures"]}
                )
            )
            release = subprocess.run(
                [*base_audit, "--release"],
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=environment,
                timeout=120,
            )
            release_payload = json.loads(release.stdout)
            self.assertTrue(
                stale_codes
                <= {item["code"] for item in release_payload["failures"]}
            )

    def test_missing_proofs_warn_in_dev_and_fail_in_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "plugin"
            shutil.copytree(
                PLUGIN,
                copied,
                copy_function=shutil.copyfile,
            )
            attestations = copied / "maintainer" / "attestations"
            if attestations.exists():
                remove_test_tree(attestations)
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment["PYTHONUTF8"] = "1"
            base = [
                sys.executable,
                "-B",
                str(SCRIPTS / "audit_package.py"),
                "--plugin-root",
                str(copied),
            ]
            dev = subprocess.run(
                base,
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=environment,
                timeout=120,
            )
            dev_payload = json.loads(dev.stdout)
            missing = {
                "release-test-attestation-missing",
                "release-route-verification-missing",
            }
            self.assertTrue(
                missing
                <= {item["code"] for item in dev_payload["warnings"]},
                dev_payload,
            )
            self.assertTrue(
                missing.isdisjoint(
                    {item["code"] for item in dev_payload["failures"]}
                )
            )

            release = subprocess.run(
                [*base, "--release"],
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=environment,
                timeout=120,
            )
            release_payload = json.loads(release.stdout)
            self.assertTrue(
                missing
                <= {item["code"] for item in release_payload["failures"]}
            )


if __name__ == "__main__":
    unittest.main()
