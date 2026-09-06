"""Failure-only, redacted export of exact completed or incomplete test output."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone

from common import ToolFailure, absolute, assert_no_reparse_path, is_within
from suite_process import SuiteRunUnavailable


MAX_DIAGNOSTIC_STREAM_BYTES = 20 * 1024 * 1024
SECRET_NAME = re.compile(r"(?i)(?:token|secret|password|passwd|credential|api[_-]?key|private[_-]?key|authorization)")
SECRET_ASSIGNMENT = re.compile(
    r"(?im)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|secret|authorization)\b\s*[=:]\s*)[^\r\n]+"
)
PATH_PLACEHOLDER = re.compile(
    r"<(?:PYTHON_EXECUTABLE|PLUGIN_ROOT|HOME|PYTHON_PREFIX|TEMP|LOCAL_PATH|REDACTED_PRIVATE_KEY)>"
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_private_bytes(path: Path, maximum: int) -> bytes:
    assert_no_reparse_path(path)
    before = path.stat()
    if not path.is_file() or before.st_nlink != 1 or not 0 <= before.st_size <= maximum:
        raise ToolFailure("test-diagnostic-source-unsafe", "Diagnostic source must be one bounded ordinary file.")
    data = path.read_bytes()
    after = path.stat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
    if any(getattr(before, key) != getattr(after, key) for key in fields) or len(data) != before.st_size:
        raise ToolFailure("test-diagnostic-source-unstable", "Diagnostic source changed during export.")
    return data


class TestRunCapture:
    """Keep a completed result alive through every later rejection.

    Diagnostics have no attestation authority. Exact bytes remain in memory;
    only redacted copies are exported, outside all attested source inputs.
    """

    def __init__(self, plugin_root, *, redact_paths, protected, output=None, attestation_output=None):
        self.plugin_root = plugin_root
        self.redact_paths = redact_paths
        self.protected = protected
        self.output = absolute(output) if output is not None else None
        self.attestation_output = absolute(attestation_output) if attestation_output is not None else None
        self.result = None
        self.diagnostic = None
        self.inputs_before = None
        self.dependencies_before = None
        self.secrets = set()
        for name, value in os.environ.items():
            if SECRET_NAME.search(name) and value:
                self.secrets.update((value, json.dumps(value)[1:-1], base64.b64encode(value.encode()).decode()))
        self.placeholder = self._safe_placeholder()
        self.secret_pattern = (
            re.compile("|".join(re.escape(value) for value in sorted(self.secrets, key=len, reverse=True)))
            if self.secrets else None
        )
        self.local_path = re.compile(
            r"(?<![A-Za-z0-9:/>" + re.escape(self.placeholder[-1])
            + r"])(?:[A-Za-z]:[\\/]|/(?!/))[^\r\n\"'<>]*"
        )
        if self.output is not None:
            self._validate_output(self.output)

    def _safe_placeholder(self):
        # A marker must neither contain a configured secret nor be contained
        # in one. Otherwise replacement text could itself disclose a value or
        # become another match on a repeated redaction pass.
        for marker in ("<REDACTED_SECRET>", "<MASKED>", "[HIDDEN]"):
            if all(value not in marker and marker not in value for value in self.secrets):
                return marker
        for codepoint in range(0xE000, 0xF900):
            marker = chr(codepoint)
            if all(marker not in value for value in self.secrets):
                return marker
        raise ToolFailure("test-diagnostic-redaction-unavailable", "No collision-free bounded redaction marker is available.")

    def _validate_output(self, path):
        assert_no_reparse_path(path)
        assert_no_reparse_path(path.parent)
        if path == self.attestation_output or any(
            path == protected_path
            or (kind == "directory" and is_within(path, protected_path))
            for _label, _relative, kind, protected_path in self.protected
        ):
            raise ToolFailure("test-diagnostic-output-overlaps-input", "Diagnostic output must not overlap attested inputs or the attestation output.")
        if not path.parent.is_dir() or os.path.lexists(path):
            raise ToolFailure("test-diagnostic-output-unavailable", "Diagnostic output requires an existing safe parent and a new filename.")

    def capture(self, runner, plugin_root, command):
        self.result = runner(plugin_root, command)
        return self.result

    def bind_inputs(self, inputs, dependencies):
        # These are the exact pre-launch bindings, not a claim that later
        # validation succeeded or that mutable source stayed unchanged.
        self.inputs_before = json.loads(json.dumps(inputs))
        self.dependencies_before = json.loads(json.dumps(dependencies))

    def redact(self, value):
        if not isinstance(value, str):
            return value
        result = value
        result = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----", lambda _match: self.placeholder, result)
        result = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*", lambda _match: "Bearer " + self.placeholder, result)
        result = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]{16,}|sk-[A-Za-z0-9_-]{16,})\b", lambda _match: self.placeholder, result)
        result = SECRET_ASSIGNMENT.sub(lambda match: match.group(1) + self.placeholder, result)
        result = self.redact_paths(result)
        result = self.local_path.sub(lambda _match: self.placeholder, result)
        result = PATH_PLACEHOLDER.sub(lambda _match: self.placeholder, result)
        if self.secret_pattern is not None:
            result = self.secret_pattern.sub(lambda _match: self.placeholder, result)
        return result

    def _redact_content(self, value):
        """Sanitize untrusted content values, never producer-owned field names."""
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, list):
            return [self._redact_content(item) for item in value]
        if isinstance(value, dict):
            return {key: self._redact_content(item) for key, item in value.items()}
        return value

    def redact_issue(self, issue):
        # Codes and field names are producer identities. Only the message and
        # optional path can carry child output or machine-local information.
        return {
            key: self.redact(value) if key in {"message", "path"} else value
            for key, value in issue.items()
        }

    def retain(self, error):
        if self.diagnostic is not None:
            return self.diagnostic
        execution_completed = self.result is not None
        cleanup = None
        source = getattr(error, "diagnostic", None)
        if execution_completed:
            raw_stdout, raw_stderr = self.result.stdout, self.result.stderr
            command = self.result.args
            return_code = self.result.returncode
        elif isinstance(error, SuiteRunUnavailable) and isinstance(source, dict) and isinstance(source.get("path"), str):
            # Export only exact, verified redacted private files. Never copy a
            # spool directory or include still-open/raw filenames in CI output.
            path = absolute(Path(source["path"]))
            if (
                path.name != "diagnostic.json"
                or not path.parent.name.startswith("design-dna-test-run-")
                or path.parent.parent != Path(tempfile.gettempdir()).resolve(strict=True)
            ):
                raise ToolFailure("test-diagnostic-source-unsafe", "The private source must be an owned test spool diagnostic.")
            data = _stable_private_bytes(path, 1024 * 1024)
            if _sha(data) != source.get("sha256"):
                raise ToolFailure("test-diagnostic-source-drift", "Private diagnostic digest changed before export.")
            record = json.loads(data)
            if (
                not isinstance(record, dict)
                or record.get("record_type") != "design-dna-incomplete-test-diagnostic"
                or record.get("release_eligible") is not False
                or record.get("suite_complete") is not False
            ):
                raise ToolFailure("test-diagnostic-source-unsafe", "The private source is not an incomplete non-release test diagnostic.")
            streams = []
            for name in ("stdout", "stderr"):
                binding = record["output"][name]
                if binding.get("path") != name + ".redacted.log":
                    raise ToolFailure("test-diagnostic-source-unsafe", "Only the canonical redacted private streams may be exported.")
                stream = _stable_private_bytes(path.parent / binding["path"], MAX_DIAGNOSTIC_STREAM_BYTES)
                if len(stream) != binding.get("bytes") or _sha(stream) != binding.get("sha256"):
                    raise ToolFailure("test-diagnostic-source-drift", "Private diagnostic stream changed before export.")
                streams.append(stream)
            raw_stdout, raw_stderr = streams
            command = None
            return_code = None
            cleanup = record.get("cleanup")
        else:
            return None
        if not isinstance(raw_stdout, bytes) or not isinstance(raw_stderr, bytes):
            raise ToolFailure("test-diagnostic-stream-invalid", "The exact captured test streams must be bytes.")
        if len(raw_stdout) + len(raw_stderr) > MAX_DIAGNOSTIC_STREAM_BYTES:
            raise ToolFailure("test-diagnostic-stream-limit", "The bounded diagnostic export limit was exceeded; no partial export is certified.")
        stdout = self.redact(raw_stdout.decode("utf-8", errors="replace"))
        stderr = self.redact(raw_stderr.decode("utf-8", errors="replace"))
        payload = {
            "schema_version": 1,
            "record_type": "design-dna-test-rejection-diagnostic",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "status": "rejected",
            "execution_completed": execution_completed,
            "attestation_validated": False,
            "release_eligible": False,
            "tests_run": None,
            "return_code": return_code,
            "source_inputs_before": self.inputs_before,
            "dependencies_before": self.dependencies_before,
            "failure_code": getattr(getattr(error, "issue", None), "code", type(error).__name__),
            "reason": self.redact(str(error)),
            "command_sha256": _sha(json.dumps(command, separators=(",", ":")).encode()) if command is not None else None,
            "cleanup": self._redact_content(cleanup),
            "output": {"stdout": stdout, "stderr": stderr},
            "scope": "Redacted failure diagnostics only; never test attestation, native coverage, or release evidence.",
        }
        # Bind exactly the exported, redacted streams, not a parsed summary.
        output = payload["output"]
        output["stdout_bytes"] = len(output["stdout"].encode())
        output["stderr_bytes"] = len(output["stderr"].encode())
        output["sha256"] = _sha(("stdout\0" + output["stdout"] + "\0stderr\0" + output["stderr"]).encode())
        if self.output is None:
            directory = Path(tempfile.mkdtemp(prefix="design-dna-test-rejection-")).resolve(strict=True)
            self.output = directory / "diagnostic.json"
        self._validate_output(self.output)
        data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.output, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if _stable_private_bytes(self.output, len(data)) != data:
            raise ToolFailure("test-diagnostic-output-unstable", "The immutable exported diagnostic failed its exact byte check.")
        self.diagnostic = {"path": str(self.output), "sha256": _sha(data), "status": "rejected", "release_eligible": False}
        return self.diagnostic
