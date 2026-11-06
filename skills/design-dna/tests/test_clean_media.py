"""clean_media.mjs: screenshots and recordings go once the design is approved.

Owner directive, Motty, 2026-11-02. The text records stay so the design is
traceable; nothing is removed from a design that is unapproved or in progress.
"""
import hashlib
import json
import os
import subprocess
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "clean_media.mjs"
APPROVED_ON = "2026-01-15"
APPROVED_AT = datetime(2026, 1, 15, 12, 0, 0).timestamp()
LATER = datetime(2026, 1, 20, 12, 0, 0).timestamp()

TEXT = [
    "plan.json",
    "review.md",
    "references/ref-a/study.json",
    "references/ref-a/sheet.md",
    "check/latest.json",
    "check/runs/2026-01-15T10-00-00/check.json",
    "fonts/face.woff2",
    "notes.md",
]
MEDIA = [
    "candidates.png",
    "references/ref-a/wide-home-contact-sheet.png",
    "references/ref-a/frames/wide-first-screen.png",
    "references/ref-a/frames/wide-t00000s.png",
    "references/ref-a/videos/wide.webm",
    "check/runs/2026-01-15T10-00-00/frames/route1-wide-t000.0s.png",
    "check/runs/2026-01-15T10-00-00/videos/route1-wide.webm",
    "check/review-1-home.png",
    "evidence/capture.JPG",
]
PROFILE = "proofs/shots/_p9451"
PROFILE_FILES = [
    "Local State",
    "Default/Preferences",
    "Default/Network/Cookies",
    "Default/optimization_guide_model_store/40/model.tflite",
]


class CleanMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dna-clean-media-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.project = Path(self.temp.name) / "project"
        self.root = self.project / ".design-dna"

    def write(self, rel, content=None):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if content is not None else f"bytes of {rel}".encode("utf-8"))
        return path

    def build(self, plan=None, stamp=APPROVED_AT):
        plan = {"references": [{"id": "ref-a"}], "approval": {"by": "Motty", "date": APPROVED_ON}} if plan is None else plan
        if plan is not False:
            self.write("plan.json", json.dumps(plan).encode("utf-8"))
        for rel in TEXT[1:]:
            self.write(rel)
        for rel in MEDIA:
            self.write(rel)
        for rel in PROFILE_FILES:
            self.write(f"{PROFILE}/{rel}")
        self.age(stamp)

    def age(self, stamp):
        for path in self.root.rglob("*"):
            if path.is_file():
                os.utime(path, (stamp, stamp))

    def run_tool(self, *args):
        env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home))
        result = subprocess.run(
            ["node", str(SCRIPT), "--project", str(self.project), *args],
            capture_output=True, text=True, encoding="utf-8", env=env, timeout=120,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(f"not JSON (exit {result.returncode}): {result.stdout!r} {result.stderr!r}")
        return result.returncode, payload

    def assert_untouched(self):
        for rel in TEXT + MEDIA:
            if rel == "plan.json" and not (self.root / rel).exists():
                continue
            self.assertTrue((self.root / rel).is_file(), rel)
        self.assertTrue((self.root / PROFILE / "Local State").is_file())
        self.assertFalse((self.root / "retention.json").exists())

    def codes(self, payload):
        return [item["code"] for item in payload.get("refused", [])]

    def test_report_is_the_default_and_removes_nothing(self):
        self.build()
        code, payload = self.run_tool()
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["mode"], "report")
        self.assertEqual(payload["totals"]["media_files"], len(MEDIA))
        self.assertEqual(payload["totals"]["profiles"], 1)
        self.assertEqual(payload["profiles"][0]["dir"], PROFILE)
        self.assertEqual(payload["profiles"][0]["files"], len(PROFILE_FILES))
        self.assertEqual(payload["approval"]["source"], "plan.json")
        self.assert_untouched()
        code, payload = self.run_tool("--dry-run")
        self.assertEqual(code, 0, payload)
        self.assert_untouched()

    def test_apply_removes_media_and_profiles_and_keeps_text_records(self):
        self.build()
        hashes = {rel: hashlib.sha256((self.root / rel).read_bytes()).hexdigest() for rel in MEDIA}
        code, payload = self.run_tool("--apply")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["mode"], "applied")
        for rel in TEXT:
            self.assertTrue((self.root / rel).is_file(), rel)
        for rel in MEDIA:
            self.assertFalse((self.root / rel).exists(), rel)
        self.assertFalse((self.root / PROFILE).exists())
        self.assertFalse((self.root / "references/ref-a/frames").exists(), "emptied frame folder is left behind")
        self.assertFalse((self.root / "check/runs/2026-01-15T10-00-00/videos").exists())
        ledger = json.loads((self.root / "retention.json").read_text(encoding="utf-8"))
        run = ledger["runs"][-1]
        self.assertEqual(run["status"], "complete")
        self.assertEqual(run["approval"]["by"], "Motty")
        self.assertEqual({item["file"]: item["sha256"] for item in run["files"]}, hashes)
        self.assertEqual(run["profiles"][0]["dir"], PROFILE)
        # A second pass finds nothing and does not mistake its own deletions for new work.
        code, payload = self.run_tool("--apply")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["totals"]["media_files"], 0)

    def test_unapproved_plan_is_refused_even_with_apply(self):
        self.build(plan={"references": [{"id": "ref-a"}]})
        code, payload = self.run_tool("--apply")
        self.assertEqual(code, 2, payload)
        self.assertIn("not-approved", self.codes(payload))
        self.assertEqual(payload["removed"], "nothing")
        self.assert_untouched()

    def test_approval_needs_both_name_and_date(self):
        self.build(plan={"approval": {"by": "Motty"}})
        code, payload = self.run_tool("--apply")
        self.assertEqual(code, 2, payload)
        self.assertIn("not-approved", self.codes(payload))
        self.assert_untouched()

    def test_project_without_plan_needs_the_explicit_statement(self):
        self.build(plan=False)
        code, payload = self.run_tool("--apply")
        self.assertEqual(code, 2, payload)
        self.assertIn("not-approved", self.codes(payload))
        self.assert_untouched()
        code, payload = self.run_tool("--apply", "--approved")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["approval"]["source"], "--approved")
        for rel in MEDIA:
            self.assertFalse((self.root / rel).exists(), rel)

    def test_unfinished_plan_is_refused(self):
        self.build(plan={"approval": {"by": "Motty", "date": APPROVED_ON}, "ground": {"color": "TODO"}})
        code, payload = self.run_tool("--apply", "--approved")
        self.assertEqual(code, 2, payload)
        self.assertIn("plan-unfinished", self.codes(payload))
        self.assert_untouched()

    def test_recent_writes_are_refused_even_with_the_statement(self):
        self.build()
        now = time.time()
        os.utime(self.root / "references/ref-a/frames/wide-t00000s.png", (now, now))
        code, payload = self.run_tool("--apply", "--approved")
        self.assertEqual(code, 2, payload)
        self.assertIn("recent-activity", self.codes(payload))
        self.assert_untouched()

    def test_work_after_the_approval_date_is_refused_until_confirmed(self):
        self.build()
        os.utime(self.root / "check/runs/2026-01-15T10-00-00/check.json", (LATER, LATER))
        code, payload = self.run_tool("--apply")
        self.assertEqual(code, 2, payload)
        self.assertIn("work-after-approval", self.codes(payload))
        self.assert_untouched()
        code, payload = self.run_tool("--apply", "--approved")
        self.assertEqual(code, 0, payload)

    def test_active_legacy_lock_is_refused(self):
        self.build()
        record = json.dumps({"schema_version": 1, "record_type": "design-dna-project-state-lock", "status": "active", "owner_token": "x"})
        (self.project / ".design-dna.lock").write_bytes(b"\0" + record.encode("utf-8"))
        code, payload = self.run_tool("--apply")
        self.assertEqual(code, 2, payload)
        self.assertIn("project-lock", self.codes(payload))
        self.assert_untouched()
        released = record.replace('"active"', '"released"')
        (self.project / ".design-dna.lock").write_bytes(b"\0" + released.encode("utf-8"))
        code, payload = self.run_tool("--apply")
        self.assertEqual(code, 0, payload)

    def test_keep_protects_listed_material(self):
        self.build()
        self.write("client-designs/logo.png")
        self.age(APPROVED_AT)
        code, payload = self.run_tool("--apply", "--keep", "client-designs", "--keep", "candidates.png")
        self.assertEqual(code, 0, payload)
        self.assertTrue((self.root / "client-designs/logo.png").is_file())
        self.assertTrue((self.root / "candidates.png").is_file())
        self.assertFalse((self.root / "references/ref-a/videos/wide.webm").exists())
        self.assertIn("client-designs/logo.png", payload["kept_by_request"])

    def test_owner_record_is_never_cleaned(self):
        self.project = self.home
        self.root = self.home / ".design-dna"
        self.build()
        code, payload = self.run_tool("--apply", "--approved")
        self.assertEqual(code, 2, payload)
        self.assertIn("owner-record", self.codes(payload))
        self.assert_untouched()

    def test_conflicting_modes_and_missing_folder_are_refused(self):
        self.build()
        code, payload = self.run_tool("--apply", "--dry-run")
        self.assertEqual(code, 2, payload)
        self.assert_untouched()
        self.project = Path(self.temp.name) / "elsewhere"
        self.project.mkdir()
        code, payload = self.run_tool("--apply", "--approved")
        self.assertEqual(code, 2, payload)
        self.assertIn("no-design-dna", self.codes(payload))


if __name__ == "__main__":
    unittest.main()
