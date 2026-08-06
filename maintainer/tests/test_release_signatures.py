from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError


PLUGIN = Path(__file__).resolve().parents[2]
SCRIPT = PLUGIN / "maintainer" / "scripts" / "attest_signatures.py"
SCHEMA = (
    PLUGIN
    / "maintainer"
    / "schemas"
    / "release-signature-attestation.schema.json"
)
PACKAGE_SCHEMA = (
    PLUGIN / "maintainer" / "schemas" / "release-package.schema.json"
)
PRIMARY = "B" * 40
SIGNING = "A" * 40
KEY_ID = "A" * 16


def load_module():
    scripts = str(SCRIPT.parent)
    sys.path.insert(0, scripts)
    try:
        specification = importlib.util.spec_from_file_location(
            "design_dna_signature_attestation_test_module",
            SCRIPT,
        )
        assert specification is not None
        assert specification.loader is not None
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


MODULE = load_module()
SCHEMA_DOCUMENT = json.loads(SCHEMA.read_text(encoding="utf-8"))
Draft202012Validator.check_schema(SCHEMA_DOCUMENT)
VALIDATOR = Draft202012Validator(
    SCHEMA_DOCUMENT,
    format_checker=FormatChecker(),
)


def valid_status(
    *,
    signing: str = SIGNING,
    primary: str = PRIMARY,
    hash_algorithm: int = 10,
    public_key_algorithm: int = 1,
    signature_class: str = "00",
) -> str:
    created = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
    key_id = signing[-16:]
    return (
        "[GNUPG:] NEWSIG\n"
        f"[GNUPG:] KEY_CONSIDERED {primary} 0\n"
        f"[GNUPG:] GOODSIG {key_id} Test Release Key\n"
        f"[GNUPG:] VALIDSIG {signing} 2026-01-01 {created} 0 "
        f"4 0 {public_key_algorithm} {hash_algorithm} "
        f"{signature_class} {primary}\n"
        "[GNUPG:] TRUST_UNDEFINED 0 pgp\n"
    )


class FakeGpg:
    def __init__(
        self,
        *,
        status: str | None = None,
        verify_returncode: int = 0,
    ) -> None:
        self.status = status or valid_status()
        self.verify_returncode = verify_returncode
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], **_kwargs):
        self.commands.append(command)
        if command[-1] == "--version":
            return subprocess.CompletedProcess(
                command,
                0,
                "gpg (GnuPG) 2.4.7\n",
                "",
            )
        return subprocess.CompletedProcess(
            command,
            self.verify_returncode,
            self.status,
            "",
        )


class DigestCheckingGpg(FakeGpg):
    def __init__(self, expected_record_sha256: str) -> None:
        super().__init__()
        self.expected_record_sha256 = expected_record_sha256

    def __call__(self, command: list[str], **kwargs):
        if command[-1] == "--version":
            return super().__call__(command, **kwargs)
        artifact = Path(command[-1])
        if (
            artifact.name == "release-package.json"
            and hashlib.sha256(artifact.read_bytes()).hexdigest()
            != self.expected_record_sha256
        ):
            self.commands.append(command)
            return subprocess.CompletedProcess(
                command,
                1,
                f"[GNUPG:] NEWSIG\n[GNUPG:] BADSIG {KEY_ID} Test Key\n",
                "",
            )
        return super().__call__(command, **kwargs)


def make_bundle(root: Path) -> tuple[Path, dict[str, object]]:
    bundle_name = "design-dna-1.2.3-abcdef123456"
    bundle = root / bundle_name
    bundle.mkdir()
    archive_name = f"{bundle_name}.zip"
    archive = bundle / archive_name
    archive.write_bytes(b"deterministic release archive")
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = bundle / f"{archive_name}.sha256"
    checksum.write_text(
        f"{archive_hash}  {archive_name}\n",
        encoding="utf-8",
        newline="\n",
    )
    record: dict[str, object] = {
        "schema_version": 1,
        "record_type": "design-dna-release-package",
        "package": "design-dna",
        "version": "1.2.3",
        "ref": "v1.2.3",
        "commit": "abcdef123456" + ("0" * 28),
        "commit_time": "2026-01-01T00:00:00Z",
        "release_identity_sha256": "1" * 64,
        "release_manifest_sha256": "2" * 64,
        "sbom_sha256": "3" * 64,
        "archive": {
            "name": archive_name,
            "sha256": archive_hash,
            "bytes": archive.stat().st_size,
            "format": "zip",
            "prefix": "design-dna-1.2.3/",
        },
        "checksum_file": {
            "name": checksum.name,
            "format": "sha256sum",
        },
        "signature_policy": "external-detached-required",
        "required_signatures": [
            {
                "role": "release-package",
                "name": "release-package.json.asc",
            },
            {
                "role": "archive",
                "name": f"{archive_name}.asc",
            },
            {
                "role": "checksum",
                "name": f"{checksum.name}.asc",
            },
        ],
        "signature_limitation": (
            "External detached signatures require verification against the "
            "owner's independently established release fingerprint."
        ),
    }
    Draft202012Validator(
        json.loads(PACKAGE_SCHEMA.read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    ).validate(record)
    (bundle / "release-package.json").write_text(
        json.dumps(record, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (bundle / "release-package.json.asc").write_text(
        "armored release-package signature\n",
        encoding="utf-8",
    )
    (bundle / f"{archive_name}.asc").write_text(
        "armored archive signature\n",
        encoding="utf-8",
    )
    (bundle / f"{checksum.name}.asc").write_text(
        "armored checksum signature\n",
        encoding="utf-8",
    )
    return bundle, record


class ReleaseSignatureTests(unittest.TestCase):
    @staticmethod
    def fake_gpg(root: Path) -> Path:
        executable = root / ("gpg.exe" if sys.platform == "win32" else "gpg")
        executable.write_bytes(b"test-only fake executable identity")
        if sys.platform != "win32":
            executable.chmod(0o700)
        return executable

    def test_three_detached_signatures_bind_record_archive_checksum_and_key(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, record = make_bundle(root)
            fake = FakeGpg()
            attestation = MODULE.create_attestation(
                PLUGIN,
                bundle,
                PRIMARY.lower(),
                gpg_executable=str(self.fake_gpg(root)),
                runner=fake,
            )
            VALIDATOR.validate(attestation)
            self.assertEqual(
                [item["role"] for item in attestation["artifacts"]],
                ["release-package", "archive", "checksum"],
            )
            self.assertEqual(
                attestation["trust_basis"]["primary_fingerprint"],
                PRIMARY,
            )
            self.assertTrue(
                all(
                    item["verification"]["primary_fingerprint"] == PRIMARY
                    and item["verification"]["signing_fingerprint"] == SIGNING
                    for item in attestation["artifacts"]
                )
            )
            archive = attestation["artifacts"][1]["artifact"]
            self.assertEqual(
                archive["sha256"],
                record["archive"]["sha256"],
            )
            self.assertEqual(len(fake.commands), 4)
            for command in fake.commands[1:]:
                self.assertIn("--no-options", command)
                self.assertIn("--no-auto-key-retrieve", command)
                self.assertIn("--status-fd=1", command)
                self.assertNotIn("--recv-keys", command)

    def test_checksum_or_signature_absence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle, _record = make_bundle(Path(temporary))
            gpg = self.fake_gpg(Path(temporary))
            checksum = next(bundle.glob("*.zip.sha256"))
            checksum.write_text(
                ("0" * 64) + f"  {next(bundle.glob('*.zip')).name}\n",
                encoding="utf-8",
            )
            with self.assertRaises(MODULE.ToolFailure) as raised:
                MODULE.create_attestation(
                    PLUGIN,
                    bundle,
                    PRIMARY,
                    gpg_executable=str(gpg),
                    runner=FakeGpg(),
                )
            self.assertEqual(
                raised.exception.issue.code,
                "release-signature-checksum-mismatch",
            )

        with tempfile.TemporaryDirectory() as temporary:
            bundle, _record = make_bundle(Path(temporary))
            gpg = self.fake_gpg(Path(temporary))
            next(bundle.glob("*.zip.asc")).unlink()
            with self.assertRaises(MODULE.ToolFailure) as raised:
                MODULE.create_attestation(
                    PLUGIN,
                    bundle,
                    PRIMARY,
                    gpg_executable=str(gpg),
                    runner=FakeGpg(),
                )
            self.assertEqual(
                raised.exception.issue.code,
                "release-signature-file-missing",
            )

    def test_status_parser_rejects_wrong_key_failure_weak_hash_and_noise(
        self,
    ) -> None:
        with self.assertRaises(MODULE.ToolFailure) as raised:
            MODULE.parse_gpg_status(valid_status(), "C" * 40)
        self.assertEqual(
            raised.exception.issue.code,
            "release-signature-fingerprint-mismatch",
        )

        with self.assertRaises(MODULE.ToolFailure) as raised:
            MODULE.parse_gpg_status(
                valid_status(hash_algorithm=2),
                PRIMARY,
            )
        self.assertEqual(
            raised.exception.issue.code,
            "release-signature-hash-algorithm-refused",
        )

        with self.assertRaises(MODULE.ToolFailure) as raised:
            MODULE.parse_gpg_status(
                "[GNUPG:] NEWSIG\n"
                f"[GNUPG:] BADSIG {KEY_ID} Bad Key\n",
                PRIMARY,
            )
        self.assertEqual(
            raised.exception.issue.code,
            "release-signature-invalid",
        )

        with self.assertRaises(MODULE.ToolFailure) as raised:
            MODULE.parse_gpg_status(
                valid_status() + "unstructured success text\n",
                PRIMARY,
            )
        self.assertEqual(
            raised.exception.issue.code,
            "release-signature-status-invalid",
        )

    def test_full_fingerprint_is_mandatory_and_schema_is_strict(self) -> None:
        for value in ("A" * 8, "A" * 16, "not-a-fingerprint"):
            with self.subTest(value=value):
                with self.assertRaises(MODULE.ToolFailure):
                    MODULE.normalize_fingerprint(value)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, _record = make_bundle(root)
            attestation = MODULE.create_attestation(
                PLUGIN,
                bundle,
                PRIMARY,
                gpg_executable=str(self.fake_gpg(root)),
                runner=FakeGpg(),
            )
            mutated = json.loads(json.dumps(attestation))
            mutated["trust_basis"]["fingerprint_source"] = (
                "declared-by-release-bundle"
            )
            with self.assertRaises(ValidationError):
                VALIDATOR.validate(mutated)
            mutated = json.loads(json.dumps(attestation))
            mutated["artifacts"][0]["verification"]["unexpected"] = True
            with self.assertRaises(ValidationError):
                VALIDATOR.validate(mutated)

    def test_record_tamper_cannot_reuse_detached_signature(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, record = make_bundle(root)
            original_record_hash = hashlib.sha256(
                (bundle / "release-package.json").read_bytes()
            ).hexdigest()
            record["version"] = "9.9.9"
            record["ref"] = "v9.9.9"
            record["commit"] = "f" * 40
            record["release_identity_sha256"] = "e" * 64
            (bundle / "release-package.json").write_text(
                json.dumps(record, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaises(MODULE.ToolFailure) as raised:
                MODULE.create_attestation(
                    PLUGIN,
                    bundle,
                    PRIMARY,
                    gpg_executable=str(self.fake_gpg(root)),
                    runner=DigestCheckingGpg(original_record_hash),
                )
            self.assertEqual(
                raised.exception.issue.code,
                "release-signature-invalid",
            )

    def test_gpg_must_be_absolute_external_and_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, _record = make_bundle(root)
            with self.assertRaises(MODULE.ToolFailure) as raised:
                MODULE.create_attestation(
                    PLUGIN,
                    bundle,
                    PRIMARY,
                    gpg_executable="gpg",
                    runner=FakeGpg(),
                )
            self.assertEqual(
                raised.exception.issue.code,
                "release-signature-gpg-path-not-absolute",
            )
            inside = bundle / "gpg.exe"
            inside.write_bytes(b"fake")
            with self.assertRaises(MODULE.ToolFailure) as raised:
                MODULE.create_attestation(
                    PLUGIN,
                    bundle,
                    PRIMARY,
                    gpg_executable=str(inside),
                    runner=FakeGpg(),
                )
            self.assertEqual(
                raised.exception.issue.code,
                "release-signature-gpg-inside-release",
            )


if __name__ == "__main__":
    unittest.main()
