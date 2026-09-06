"""Bounded, privately spooled test execution; incomplete output never attests a pass."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

from common import ToolFailure
from run_evals import _WindowsProcessJob, terminate_process_tree


MAX_SPOOLED_OUTPUT_BYTES = 20 * 1024 * 1024


class SuiteRunUnavailable(ToolFailure):
    def __init__(self, message, diagnostic=None):
        super().__init__("test-attestation-suite-unavailable", message)
        self.diagnostic = diagnostic


def current_process_image():
    """Use the actual Windows interpreter, not a venv forwarding launcher."""
    if os.name != "nt":
        return str(Path(sys.executable).resolve(strict=True))
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    kernel.GetModuleFileNameW.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    count = kernel.GetModuleFileNameW(None, buffer, len(buffer))
    if not count or count >= len(buffer):
        raise OSError("The intrinsically running Python image could not be resolved.")
    return str(Path(buffer.value).resolve(strict=True))


def _retain(spool, command, status, reason, timeout, elapsed, cleanup, redact, *, writers_settled):
    bindings = {}
    for stream in ("stdout", "stderr"):
        raw_path = spool / (stream + ".raw.log")
        raw = raw_path.read_bytes() if raw_path.is_file() else b""
        retained = redact(raw.decode("utf-8", errors="replace")).encode("utf-8")
        target = spool / (stream + ".redacted.log")
        with target.open("xb") as output:
            output.write(retained)
        bindings[stream] = {"path": target.name, "bytes": len(retained), "sha256": hashlib.sha256(retained).hexdigest()}
        if not writers_settled and raw_path.exists():
            # An incomplete snapshot may be retained, but an unverified
            # writer must not lose its still-open private output file.
            bindings[stream]["private_raw_retained_unverified_writers"] = raw_path.name
            bindings[stream]["snapshot_may_have_continued"] = True
        else:
            try:
                raw_path.unlink(missing_ok=True)
            except OSError:
                bindings[stream]["private_raw_cleanup_failed"] = True
    record = {"schema_version": 1, "record_type": "design-dna-incomplete-test-diagnostic",
        "status": status, "suite_complete": False, "release_eligible": False, "tests_run": None,
        "captured_at": datetime.now(timezone.utc).isoformat(), "timeout_seconds": timeout,
        "elapsed_seconds": round(elapsed, 3), "reason": redact(reason), "cleanup": cleanup,
        "command_sha256": hashlib.sha256(json.dumps(command, separators=(",", ":")).encode()).hexdigest(),
        "output": bindings, "scope": "Partial private diagnostics only; not a test attestation or native platform coverage."}
    path = spool / "diagnostic.json"
    data = (json.dumps(record, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as output:
        output.write(data)
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "status": status, "release_eligible": False}


def run_spooled_suite(command, *, cwd, environment, timeout, redact, announce=True):
    """Return only completed output; retain failed-only diagnostics otherwise.

    Windows uses the already-audited ready-event job protocol. Its supervisor
    is the actual current process image and uses -I -S -B, so a venv launcher
    cannot spawn an unassigned child before the job becomes active. The test
    command itself is unchanged. POSIX cleanup covers the owned process group;
    deliberately escaped descendant sessions are outside that boundary.
    """
    spool = Path(tempfile.mkdtemp(prefix="design-dna-test-run-")).resolve(strict=True)
    if spool.is_relative_to(Path(cwd).resolve()):
        spool.rmdir()
        raise SuiteRunUnavailable("The private test spool must be outside the package inputs.")
    stdout_path, stderr_path = spool / "stdout.raw.log", spool / "stderr.raw.log"
    process = None
    job = None
    job_assigned = False
    cleanup = {"attempted": False, "verified": False, "boundary": "windows-job" if os.name == "nt" else "posix-process-group"}
    reason, status, output = None, None, None
    started = time.monotonic()
    try:
        options = {}
        launched = list(command)
        if os.name == "nt":
            job = _WindowsProcessJob()
            launched = job.wrapped_command(command)
            launched[0] = current_process_image()
            launched.insert(2, "-S")
            options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        else:
            options["start_new_session"] = True
        with stdout_path.open("xb") as stdout_handle, stderr_path.open("xb") as stderr_handle:
            if announce:
                print("Design DNA live private test logs: " + str(stdout_path) + " ; " + str(stderr_path), file=sys.stderr, flush=True)
            process = subprocess.Popen(launched, cwd=cwd, env=environment, stdout=stdout_handle,
                                       stderr=stderr_handle, shell=False, **options)
            if job is not None:
                job.assign(process)
                job_assigned = True
                job.release_driver()
            deadline = started + timeout
            while True:
                if stdout_path.stat().st_size + stderr_path.stat().st_size > MAX_SPOOLED_OUTPUT_BYTES:
                    status, reason = "output-limit", "Test output exceeded the bounded private spool; captured output is retained as incomplete."
                    break
                code = process.poll()
                if code is not None:
                    if job is not None and not job.wait_empty(1000):
                        cleanup["attempted"] = True
                        cleanup = {"attempted": True, "boundary": "windows-job", **terminate_process_tree(process, job)}
                        cleanup["verified"] = cleanup.get("verified_empty") is True
                    elif job is None:
                        # A finished parent may still have writers in its
                        # owned POSIX group. Settle that group before reading
                        # or deleting the exact output spool.
                        cleanup["attempted"] = True
                        cleanup = {"attempted": True, "boundary": "posix-process-group", **terminate_process_tree(process)}
                        cleanup["verified"] = cleanup.get("verified_empty") is True
                    output = subprocess.CompletedProcess(command, code, b"", b"")
                    break
                if time.monotonic() >= deadline:
                    status, reason = "timed-out", f"The exact test suite exceeded its {timeout}-second ceiling."
                    break
                time.sleep(0.05)
            if reason:
                cleanup["attempted"] = True
                cleanup = {"attempted": True, "boundary": cleanup["boundary"], **terminate_process_tree(process, job)}
                cleanup["verified"] = cleanup.get("verified_empty") is True
    except BaseException as exc:
        primary = f"{type(exc).__name__}: {exc}"
        reason = (reason + " Cleanup/retention failure: " + primary) if reason else primary
        status = status or "execution-unavailable"
        if process is not None and (process.poll() is None or job is not None):
            try:
                if job is not None and not job_assigned:
                    # The base-interpreter bootstrap is still behind its
                    # unreleased event and has spawned no test driver. An
                    # empty unassigned job does not prove this root exited.
                    process.kill()
                    process.wait(timeout=5)
                    cleanup = {"attempted": True, "boundary": "unreleased-supervisor", "verified": process.poll() is not None}
                else:
                    cleanup["attempted"] = True
                    cleanup = {"attempted": True, "boundary": cleanup["boundary"], **terminate_process_tree(process, job)}
                    cleanup["verified"] = cleanup.get("verified_empty") is True and process.poll() is not None
            except BaseException as secondary:
                cleanup["error"] = f"{type(secondary).__name__}: {secondary}"
    finally:
        if job is not None:
            job.close()
    if reason:
        try:
            diagnostic = _retain(spool, command, status, reason, timeout, time.monotonic() - started, cleanup, redact,
                                 writers_settled=process is None or cleanup.get("verified") is True)
        except BaseException as exc:
            raise SuiteRunUnavailable(redact(reason) + f" Diagnostic retention also failed ({type(exc).__name__}); private spool: {spool}") from exc
        raise SuiteRunUnavailable(redact(reason) + " Incomplete diagnostic: " + diagnostic["path"], diagnostic)
    assert output is not None
    output.stdout = stdout_path.read_bytes()
    output.stderr = stderr_path.read_bytes()
    stdout_path.unlink()
    stderr_path.unlink()
    spool.rmdir()
    return output
