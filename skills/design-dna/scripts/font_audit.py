#!/usr/bin/env python3
"""Deterministic local font inventory and source-contract audit.

This tool reports bounded source evidence. It does not classify fonts as
"AI fonts", detect authorship, or replace rendered typography review.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import html
import json
import os
import re
import stat
import sys
import time
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import parse_qs, unquote, unquote_to_bytes, urlsplit, urlunsplit


MINIMUM_PYTHON = (3, 10)
SCHEMA_VERSION = 2
ARTIFACT_TYPE = "design-dna-font-audit"
MAX_SOURCE_BYTES = 5 * 1024 * 1024
MAX_FONT_BYTES = 100 * 1024 * 1024
MAX_TOTAL_ENTRIES = 50_000
MAX_TOTAL_SOURCE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_FONT_BYTES = 512 * 1024 * 1024
MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_DATA_URI_HASH_BYTES = 2 * 1024 * 1024
MAX_AUDIT_SECONDS = 30.0
SOURCE_SUFFIXES = {
    ".astro", ".cjs", ".css", ".ejs", ".erb", ".gohtml", ".handlebars",
    ".hbs", ".htm", ".html", ".j2", ".jinja", ".jinja2", ".js", ".jsx",
    ".less", ".liquid", ".mdx", ".mjs", ".mustache", ".njk", ".php",
    ".razor", ".sass", ".scss", ".styl", ".stylus", ".svelte", ".svg",
    ".tmpl", ".tpl", ".ts", ".tsx", ".twig", ".vue",
}
CSS_SUFFIXES = {".css", ".less", ".sass", ".scss", ".styl", ".stylus"}
SCRIPT_SUFFIXES = {".cjs", ".js", ".jsx", ".mjs", ".ts", ".tsx"}
MARKUP_SUFFIXES = SOURCE_SUFFIXES - CSS_SUFFIXES - SCRIPT_SUFFIXES
LINK_SUFFIXES = MARKUP_SUFFIXES | {".jsx", ".tsx"}
FONT_SUFFIXES = {".eot", ".otf", ".ttf", ".woff", ".woff2"}
IGNORED_DIRS = {
    ".design-dna", ".design-dna.unallocated-stage", ".git", ".next",
    ".nuxt", ".output", ".svelte-kit", ".vinext", "coverage", "dist",
    "node_modules", "vendor",
}
IGNORED_DIR_PREFIXES = (
    ".design-dna.backup-",
    ".design-dna.failed-",
    ".design-dna-migrate-",
    ".design-dna-stage-",
)
LICENSE_NAME = re.compile(
    r"^(?:.*[._-])?(?:copying|fontlog|license|licence|notice|ofl)"
    r"(?:[._-].*)?$",
    re.I,
)
LICENSE_TEXT = re.compile(
    r"\b(?:SIL\s+Open\s+Font\s+License|Open\s+Font\s+License|"
    r"font\s+license|licensed\s+font|typeface\s+license|Apache\s+License|"
    r"MIT\s+License|GNU\s+(?:Lesser\s+)?General\s+Public\s+License|"
    r"Ubuntu\s+Font\s+Licen[cs]e|Creative\s+Commons|public\s+domain|"
    r"End\s+User\s+License\s+Agreement|EULA|licensed\s+under|"
    r"permission\s+is\s+hereby\s+granted|copyright)\b",
    re.I,
)
FONT_FACE_START = re.compile(r"@font-face\s*\{", re.I)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
URL_CALL = re.compile(
    r"\b(?P<name>url|local)\s*\(\s*"
    r"(?P<value>\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|[^)]*?)\s*\)",
    re.I | re.S,
)
FORMAT_CALL = re.compile(
    r"^\s*format\s*\(\s*"
    r"(?P<value>\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|[^)]*?)\s*\)",
    re.I | re.S,
)
HTML_TAG = re.compile(r"<link\b(?P<attrs>[^>]*)>", re.I | re.S)
HTML_STYLE_ATTR = re.compile(
    r"\bstyle\s*=\s*(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
    re.I | re.S,
)
HTML_STYLE_BLOCK = re.compile(
    r"<style\b[^>]*>(?P<value>.*?)</style\s*>",
    re.I | re.S,
)
STYLESHEET_LINK = re.compile(r"<link\b(?P<attrs>[^>]*)>", re.I | re.S)
CSS_IMPORT = re.compile(
    r"@import\s+(?:url\s*\(\s*)?"
    r"(?P<value>\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|[^\s;)]+)"
    r"\s*\)?[^;]*;",
    re.I | re.S,
)
NEXT_FONT_IMPORT = re.compile(
    r"import\s+(?P<binding>\{[^}]+\}|[A-Za-z_$][A-Za-z0-9_$]*)\s+"
    r"from\s+[\"']next/font/(?P<kind>google|local)[\"']",
    re.I,
)
FONTSOURCE_IMPORT = re.compile(
    r"(?:import\s*(?:\([^)]*\)\s*)?|@import\s+)"
    r"[\"'](?P<package>@fontsource(?:-variable)?/"
    r"(?P<family>[a-z0-9-]+)(?:/(?P<variant>[^\"']+))?)[\"']",
    re.I,
)
DYNAMIC_LOCATOR = re.compile(
    r"\$\{|#\{|\{\{|\{%|<%|"
    r"\$[A-Za-z_][A-Za-z0-9_-]*|"
    r"\b(?:var|env)\s*\(|"
    r"`|"
    r"\{[A-Za-z_$][^{}\r\n]{0,200}\}",
    re.I,
)
ATTR = re.compile(
    r"(?P<name>[A-Za-z_:][A-Za-z0-9:._-]*)"
    r"(?:\s*=\s*(?:"
    r"(?P<quote>[\"'])(?P<quoted>.*?)(?P=quote)"
    r"|(?P<unquoted>[^\s\"'=<>`]+)"
    r"))?",
    re.S,
)
CSS_BLOCK = re.compile(r"(?P<header>[^{}]+)\{(?P<body>[^{}]*)\}", re.S)
CSS_DECLARATION = re.compile(
    r"(?P<name>--[A-Za-z0-9_-]+|[A-Za-z-]+)\s*:\s*(?P<value>.*)",
    re.S,
)
WEIGHT_NUMBER = re.compile(r"^(?:[1-9][0-9]{0,2}|1000)$")
VARIABLE_WEIGHT = re.compile(
    r"^\s*(?P<minimum>(?:[1-9][0-9]{0,2}|1000))\s+"
    r"(?P<maximum>(?:[1-9][0-9]{0,2}|1000))\s*$"
)
GENERIC_FAMILIES = {
    "cursive", "emoji", "fangsong", "fantasy", "math", "monospace",
    "sans-serif", "serif", "system-ui", "ui-monospace", "ui-rounded",
    "ui-sans-serif", "ui-serif",
}


class AuditError(RuntimeError):
    """A safety, integrity, or input-contract failure."""


class ResourceBudget:
    def __init__(self) -> None:
        self.started = time.monotonic()
        self.entries = 0
        self.source_bytes_observed = 0
        self.source_bytes_read = 0
        self.font_bytes_observed = 0
        self.font_bytes_read = 0
        self.exceeded: set[str] = set()

    def check_time(self) -> None:
        if time.monotonic() - self.started > MAX_AUDIT_SECONDS:
            raise AuditError(
                f"audit-time-limit-exceeded: {MAX_AUDIT_SECONDS} seconds"
            )

    def add_entry(self) -> None:
        self.entries += 1
        if self.entries > MAX_TOTAL_ENTRIES:
            raise AuditError(
                f"project-entry-limit-exceeded: {MAX_TOTAL_ENTRIES}"
            )
        self.check_time()

    def reserve_source(self, size_bytes: int) -> bool:
        self.source_bytes_observed += size_bytes
        if (
            size_bytes > MAX_SOURCE_BYTES
            or self.source_bytes_read + size_bytes > MAX_TOTAL_SOURCE_BYTES
        ):
            self.exceeded.add(
                "source-file-bytes"
                if size_bytes > MAX_SOURCE_BYTES
                else "total-source-bytes"
            )
            return False
        self.source_bytes_read += size_bytes
        self.check_time()
        return True

    def reserve_font(self, size_bytes: int) -> bool:
        self.font_bytes_observed += size_bytes
        if (
            size_bytes > MAX_FONT_BYTES
            or self.font_bytes_read + size_bytes > MAX_TOTAL_FONT_BYTES
        ):
            self.exceeded.add(
                "font-file-bytes"
                if size_bytes > MAX_FONT_BYTES
                else "total-font-bytes"
            )
            return False
        self.font_bytes_read += size_bytes
        self.check_time()
        return True

    def limits(self) -> dict[str, object]:
        return {
            "max_entries": MAX_TOTAL_ENTRIES,
            "max_source_file_bytes": MAX_SOURCE_BYTES,
            "max_total_source_bytes": MAX_TOTAL_SOURCE_BYTES,
            "max_font_file_bytes": MAX_FONT_BYTES,
            "max_total_font_bytes": MAX_TOTAL_FONT_BYTES,
            "max_report_bytes": MAX_REPORT_BYTES,
            "max_data_uri_hash_bytes": MAX_DATA_URI_HASH_BYTES,
            "max_audit_seconds": MAX_AUDIT_SECONDS,
        }

    def usage(self) -> dict[str, object]:
        return {
            "entries": self.entries,
            "source_bytes_observed": self.source_bytes_observed,
            "source_bytes_read": self.source_bytes_read,
            "font_bytes_observed": self.font_bytes_observed,
            "font_bytes_read": self.font_bytes_read,
            "report_bytes": 0,
            "elapsed_milliseconds": round(
                (time.monotonic() - self.started) * 1000,
                3,
            ),
            "exceeded": sorted(self.exceeded),
        }


def failure(code: str, message: str, *, path: Optional[str] = None) -> int:
    error: dict[str, object] = {"code": code, "message": message}
    if path is not None:
        error["path"] = path
    print(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "artifact_type": ARTIFACT_TYPE,
        "ok": False,
        "execution_ok": False,
        "execution": {"status": "failed", "ok": False},
        "error": error,
    }, indent=2, ensure_ascii=True), file=sys.stderr)
    return 2


def is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise AuditError(f"path-inspection-failed: {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    if not attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        return False
    tag = getattr(info, "st_reparse_tag", 0)
    if tag:
        return bool(tag & 0x20000000) or tag in {0xA0000003, 0xA000000C}
    return True


def stable_identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return (
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_size),
        int(info.st_mtime_ns),
    )


def stable_read_bytes(
    path: Path,
    *,
    maximum: int,
    expected_identity: Optional[tuple[int, int, int, int]] = None,
) -> bytes:
    if is_reparse(path):
        raise AuditError(f"reparse-point-refused: {path}")
    before = path.stat()
    if (
        expected_identity is not None
        and stable_identity(before) != expected_identity
    ):
        raise AuditError(f"unstable-read-refused: {path}")
    if before.st_size > maximum:
        raise AuditError(
            f"file-size-limit-exceeded: {path}: {before.st_size} > {maximum}"
        )
    with path.open("rb") as source:
        opened_before = os.fstat(source.fileno())
        if stable_identity(before) != stable_identity(opened_before):
            raise AuditError(f"unstable-read-refused: {path}")
        payload = source.read(maximum + 1)
        opened_after = os.fstat(source.fileno())
    after = path.stat()
    if len(payload) > maximum:
        raise AuditError(f"file-size-limit-exceeded: {path}")
    if not (
        stable_identity(before)
        == stable_identity(opened_before)
        == stable_identity(opened_after)
        == stable_identity(after)
    ):
        raise AuditError(f"unstable-read-refused: {path}")
    return payload


def stable_font_digest(
    path: Path,
    *,
    expected_identity: Optional[tuple[int, int, int, int]] = None,
) -> tuple[str, int, bytes]:
    if is_reparse(path):
        raise AuditError(f"reparse-point-refused: {path}")
    before = path.stat()
    if (
        expected_identity is not None
        and stable_identity(before) != expected_identity
    ):
        raise AuditError(f"unstable-read-refused: {path}")
    if before.st_size > MAX_FONT_BYTES:
        raise AuditError(
            f"font-size-limit-exceeded: {path}: "
            f"{before.st_size} > {MAX_FONT_BYTES}"
        )
    digest = hashlib.sha256()
    prefix = b""
    size = 0
    with path.open("rb") as source:
        opened_before = os.fstat(source.fileno())
        if stable_identity(before) != stable_identity(opened_before):
            raise AuditError(f"unstable-read-refused: {path}")
        while chunk := source.read(1024 * 1024):
            if len(prefix) < 16:
                prefix += chunk[:16 - len(prefix)]
            size += len(chunk)
            if size > MAX_FONT_BYTES:
                raise AuditError(f"font-size-limit-exceeded: {path}")
            digest.update(chunk)
        opened_after = os.fstat(source.fileno())
    after = path.stat()
    if not (
        stable_identity(before)
        == stable_identity(opened_before)
        == stable_identity(opened_after)
        == stable_identity(after)
    ) or size != before.st_size:
        raise AuditError(f"unstable-read-refused: {path}")
    return digest.hexdigest(), size, prefix


def read_text(path: Path) -> str:
    payload = stable_read_bytes(path, maximum=MAX_SOURCE_BYTES)
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AuditError(f"non-utf8-source-refused: {path}") from exc


def stable_metadata(path: Path) -> os.stat_result:
    if is_reparse(path):
        raise AuditError(f"reparse-point-refused: {path}")
    before = path.stat()
    after = path.stat()
    if stable_identity(before) != stable_identity(after):
        raise AuditError(f"unstable-read-refused: {path}")
    return before


def read_eligible_source(
    path: Path,
    *,
    root: Path,
    budget: ResourceBudget,
) -> tuple[Optional[str], Optional[dict[str, object]]]:
    metadata = stable_metadata(path)
    size_bytes = int(metadata.st_size)
    if not budget.reserve_source(size_bytes):
        reason = (
            "source-exceeds-per-file-byte-limit"
            if size_bytes > MAX_SOURCE_BYTES
            else "total-source-byte-budget-exceeded"
        )
        return None, {
            "path": relative_path(path, root),
            "reason": reason,
            "size_bytes": size_bytes,
            "sha256": None,
        }
    payload = stable_read_bytes(
        path,
        maximum=MAX_SOURCE_BYTES,
        expected_identity=stable_identity(metadata),
    )
    try:
        return payload.decode("utf-8-sig"), None
    except UnicodeDecodeError:
        return None, {
            "path": relative_path(path, root),
            "reason": "source-is-not-valid-utf8",
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise AuditError(f"path-escaped-project: {path}") from exc


def assert_safe_project_path(path: Path, *, root: Path) -> None:
    absolute = Path(os.path.abspath(os.fspath(path)))
    root_absolute = Path(os.path.abspath(os.fspath(root)))
    try:
        relative = absolute.relative_to(root_absolute)
    except ValueError as exc:
        raise AuditError(f"path-escaped-project: {absolute}") from exc
    current = root_absolute
    if is_reparse(current):
        raise AuditError(f"reparse-point-refused: {current}")
    for part in relative.parts:
        current = current / part
        if is_reparse(current):
            raise AuditError(f"reparse-point-refused: {current}")


def assert_no_reparse_ancestors(path: Path) -> None:
    current = Path(os.path.abspath(os.fspath(path)))
    while True:
        if is_reparse(current):
            raise AuditError(f"reparse-point-refused: {current}")
        if current.parent == current:
            return
        current = current.parent


def is_ignored_directory_name(name: str) -> bool:
    """Match packaged exclusions without touching the candidate directory."""

    folded = name.casefold()
    return folded in IGNORED_DIRS or any(
        folded.startswith(prefix) for prefix in IGNORED_DIR_PREFIXES
    )


def enumerate_project(
    root: Path,
    budget: ResourceBudget,
) -> tuple[list[Path], list[Path], list[Path]]:
    source_files: list[Path] = []
    font_files: list[Path] = []
    evidence_files: list[Path] = []

    def walk_failure(error: OSError) -> None:
        raise AuditError(
            f"tree-enumeration-failed: {error.filename or root}: {error}"
        ) from error

    for current, dirs, files in os.walk(
        root,
        topdown=True,
        followlinks=False,
        onerror=walk_failure,
    ):
        current_path = Path(current)
        retained: list[str] = []
        for name in sorted(dirs, key=str.casefold):
            budget.add_entry()
            # Prune internal/build roots before lstat or the next os.walk
            # descent. Design DNA backups can intentionally retain stricter
            # ACLs than the current process, and excluded output should never
            # make an otherwise auditable project fail enumeration.
            if is_ignored_directory_name(name):
                continue
            candidate = current_path / name
            if is_reparse(candidate):
                raise AuditError(f"reparse-point-refused: {candidate}")
            retained.append(name)
        dirs[:] = retained
        for name in sorted(files, key=str.casefold):
            budget.add_entry()
            path = current_path / name
            if is_reparse(path):
                raise AuditError(f"reparse-point-refused: {path}")
            suffix = path.suffix.casefold()
            if suffix in SOURCE_SUFFIXES:
                source_files.append(path)
            if suffix in FONT_SUFFIXES:
                font_files.append(path)
            if LICENSE_NAME.fullmatch(path.name):
                evidence_files.append(path)
    return source_files, font_files, evidence_files


def without_comments(text: str) -> str:
    preserve = lambda match: "\n" * match.group(0).count("\n")
    text = CSS_COMMENT.sub(preserve, text)
    return HTML_COMMENT.sub(preserve, text)


def comment_license_evidence(
    path: Path,
    root: Path,
    text: str,
) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    for pattern, kind in (
        (CSS_COMMENT, "css-license-comment"),
        (HTML_COMMENT, "html-license-comment"),
    ):
        for match in pattern.finditer(text):
            if not LICENSE_TEXT.search(match.group(0)):
                continue
            evidence.append({
                "path": relative_path(path, root),
                "kind": kind,
                "line": line_number(text, match.start()),
                "sha256": hashlib.sha256(
                    match.group(0).encode("utf-8")
                ).hexdigest(),
                "applies_to_font_paths": [],
                "applies_to_families": [],
                "_binding_text": match.group(0),
            })
    return evidence


def split_top_level(value: str, delimiter: str = ",") -> list[str]:
    items: list[str] = []
    start = 0
    depth = 0
    quote: Optional[str] = None
    escaped = False
    for index, character in enumerate(value):
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in "\"'":
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")" and depth:
            depth -= 1
        elif character == delimiter and depth == 0:
            items.append(value[start:index].strip())
            start = index + 1
    items.append(value[start:].strip())
    return [item for item in items if item]


def split_declarations(body: str) -> list[tuple[str, str, int]]:
    declarations: list[tuple[str, str, int]] = []
    start = 0
    depth = 0
    quote: Optional[str] = None
    escaped = False
    segments: list[tuple[str, int]] = []
    for index, character in enumerate(body):
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in "\"'":
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")" and depth:
            depth -= 1
        elif character == ";" and depth == 0:
            segments.append((body[start:index], start))
            start = index + 1
    segments.append((body[start:], start))
    for segment, offset in segments:
        match = CSS_DECLARATION.fullmatch(segment.strip())
        if match:
            leading = len(segment) - len(segment.lstrip())
            declarations.append((
                match.group("name").casefold(),
                match.group("value").strip(),
                offset + leading,
            ))
    return declarations


def css_unquote(value: str) -> str:
    value = value.strip()
    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in "\"'"
    ):
        value = value[1:-1]
    return re.sub(r"\\([\\\"'])", r"\1", value)


def normalize_family(value: str) -> str:
    return " ".join(css_unquote(value).split())


def family_list(value: str) -> list[str]:
    return [
        normalize_family(item)
        for item in split_top_level(value)
        if normalize_family(item)
    ]


def weight_contract(raw: Optional[str]) -> dict[str, object]:
    value = "normal" if raw is None or not raw.strip() else raw.strip().casefold()
    aliases = {"normal": 400, "bold": 700}
    if value in aliases:
        number = aliases[value]
        return {
            "raw": raw or "normal",
            "minimum": number,
            "maximum": number,
            "variable": False,
            "valid": True,
        }
    if WEIGHT_NUMBER.fullmatch(value):
        number = int(value)
        return {
            "raw": raw or value,
            "minimum": number,
            "maximum": number,
            "variable": False,
            "valid": True,
        }
    variable = VARIABLE_WEIGHT.fullmatch(value)
    if variable and int(variable.group("minimum")) <= int(variable.group("maximum")):
        return {
            "raw": raw or value,
            "minimum": int(variable.group("minimum")),
            "maximum": int(variable.group("maximum")),
            "variable": True,
            "valid": True,
        }
    return {
        "raw": raw or value,
        "minimum": None,
        "maximum": None,
        "variable": False,
        "valid": False,
    }


def normalized_usage_weight(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return 400
    contract = weight_contract(raw)
    minimum = contract["minimum"]
    maximum = contract["maximum"]
    return (
        int(minimum)
        if contract["valid"] and minimum == maximum
        else None
    )


def extract_font_face_blocks(text: str) -> Iterable[tuple[int, int, str]]:
    for match in FONT_FACE_START.finditer(text):
        start = match.end()
        depth = 1
        quote: Optional[str] = None
        escaped = False
        index = start
        while index < len(text):
            character = text[index]
            if quote:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = None
            elif character in "\"'":
                quote = character
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    yield match.start(), index + 1, text[start:index]
                    break
            index += 1
        else:
            raise AuditError("unterminated-@font-face-block")


def locator_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sanitized_remote_url(value: str) -> str:
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parsed.port is not None:
        host += f":{parsed.port}"
    if value.startswith("//"):
        return urlunsplit(("", host, parsed.path, "", ""))
    return urlunsplit((parsed.scheme.casefold(), host, parsed.path, "", ""))


def data_uri_summary(value: str) -> dict[str, object]:
    header, separator, encoded = value.partition(",")
    metadata = header[5:] if header.casefold().startswith("data:") else ""
    parts = metadata.split(";") if metadata else []
    media_type = (
        parts[0].casefold()
        if parts and "/" in parts[0]
        else "text/plain"
    )
    is_base64 = any(part.casefold() == "base64" for part in parts[1:])
    if not separator:
        return {
            "media_type": media_type,
            "encoding": "base64" if is_base64 else "percent",
            "decoded_length": None,
            "sha256": None,
            "hashed_within_limit": False,
        }
    if is_base64:
        compact = re.sub(r"\s+", "", encoded)
        padding = len(compact) - len(compact.rstrip("="))
        estimated = max(0, (len(compact) * 3) // 4 - padding)
        if estimated > MAX_DATA_URI_HASH_BYTES:
            return {
                "media_type": media_type,
                "encoding": "base64",
                "decoded_length": estimated,
                "sha256": None,
                "hashed_within_limit": False,
            }
        try:
            decoded = base64.b64decode(compact, validate=True)
        except (ValueError, binascii.Error):
            decoded = b""
            return {
                "media_type": media_type,
                "encoding": "base64",
                "decoded_length": None,
                "sha256": None,
                "hashed_within_limit": False,
            }
    else:
        if len(encoded) > MAX_DATA_URI_HASH_BYTES * 3:
            return {
                "media_type": media_type,
                "encoding": "percent",
                "decoded_length": None,
                "sha256": None,
                "hashed_within_limit": False,
            }
        decoded = unquote_to_bytes(encoded)
        if len(decoded) > MAX_DATA_URI_HASH_BYTES:
            return {
                "media_type": media_type,
                "encoding": "percent",
                "decoded_length": len(decoded),
                "sha256": None,
                "hashed_within_limit": False,
            }
    return {
        "media_type": media_type,
        "encoding": "base64" if is_base64 else "percent",
        "decoded_length": len(decoded),
        "sha256": hashlib.sha256(decoded).hexdigest(),
        "hashed_within_limit": True,
    }


def safe_local_candidates(
    raw_value: str,
    *,
    source_file: Path,
    root: Path,
) -> tuple[str, list[Path]]:
    value = unquote(css_unquote(raw_value).strip())
    if not value:
        return "unsafe-local-path", []
    if value.startswith(("@fontsource/", "@fontsource-variable/", "~")):
        return "package-import", []
    if "\\" in value or re.match(r"^[A-Za-z]:", value):
        return "unsafe-local-path", []
    parsed = urlsplit(value)
    scheme = parsed.scheme.casefold()
    if scheme in {"http", "https"} or value.startswith("//"):
        return "remote-url", []
    if scheme == "data":
        return "data-url", []
    if scheme:
        return "unsupported-url-scheme", []
    clean_path = parsed.path
    if not clean_path:
        return "unsafe-local-path", []
    if clean_path.startswith("/"):
        stripped = clean_path.lstrip("/")
        root_absolute = Path(os.path.abspath(os.fspath(root)))
        source_absolute = Path(os.path.abspath(os.fspath(source_file)))
        try:
            source_relative = source_absolute.relative_to(root_absolute)
        except ValueError:
            source_relative = None

        # A directory literally named ``site`` is a common static public root.
        # When the source document is inside it, a root-relative browser URL is
        # rooted there, not at the repository root. Do not fall back to another
        # candidate in that case: doing so would hide a genuinely missing
        # public asset if an unrelated repository-level file happens to exist.
        if (
            source_relative is not None
            and source_relative.parts
            and source_relative.parts[0].casefold() == "site"
        ):
            candidates = [root_absolute / source_relative.parts[0] / stripped]
        else:
            candidates = [root_absolute / stripped, root_absolute / "public" / stripped]
    else:
        candidates = [source_file.parent / clean_path]
    safe: list[Path] = []
    root_absolute = Path(os.path.abspath(os.fspath(root)))
    for candidate in candidates:
        absolute = Path(os.path.abspath(os.fspath(candidate)))
        try:
            absolute.relative_to(root_absolute)
        except ValueError:
            return "unsafe-local-path", []
        assert_safe_project_path(absolute, root=root_absolute)
        safe.append(absolute)
    return "local-file", safe


def resolve_local_source(
    raw_value: str,
    *,
    source_file: Path,
    root: Path,
) -> dict[str, object]:
    exact_value = css_unquote(raw_value)
    kind, candidates = safe_local_candidates(
        exact_value,
        source_file=source_file,
        root=root,
    )
    parsed = urlsplit(exact_value)
    common = {
        "locator_sha256": locator_hash(exact_value),
        "data_summary": None,
    }
    if kind == "remote-url":
        return {
            "kind": kind,
            "value": sanitized_remote_url(exact_value),
            "resolved_path": None,
            "exists": None,
            **common,
        }
    if kind == "data-url":
        summary = data_uri_summary(exact_value)
        value = f"data:{summary['media_type']}"
        if summary["encoding"] == "base64":
            value += ";base64"
        return {
            "kind": kind,
            "value": value,
            "resolved_path": None,
            "exists": None,
            "locator_sha256": locator_hash(exact_value),
            "data_summary": summary,
        }
    if kind != "local-file":
        return {
            "kind": kind,
            "value": (
                f"{parsed.scheme.casefold()}:"
                if parsed.scheme
                else parsed.path
            ),
            "resolved_path": None,
            "exists": None,
            **common,
        }
    existing = next((candidate for candidate in candidates if candidate.is_file()), None)
    selected = existing or candidates[0]
    if existing and is_reparse(existing):
        raise AuditError(f"reparse-point-refused: {existing}")
    return {
        "kind": "local-file",
        "value": parsed.path,
        "resolved_path": relative_path(selected, root),
        "exists": existing is not None,
        **common,
    }


def font_sources(
    value: Optional[str],
    *,
    source_file: Path,
    root: Path,
) -> list[dict[str, object]]:
    if value is None:
        return []
    sources: list[dict[str, object]] = []
    for part in split_top_level(value):
        call = URL_CALL.search(part)
        if not call:
            continue
        called = call.group("name").casefold()
        raw = call.group("value")
        if called == "local":
            item: dict[str, object] = {
                "kind": "local-name",
                "value": css_unquote(raw),
                "resolved_path": None,
                "exists": None,
                "locator_sha256": None,
                "data_summary": None,
            }
        else:
            item = resolve_local_source(
                raw,
                source_file=source_file,
                root=root,
            )
        remainder = part[call.end():]
        format_match = FORMAT_CALL.match(remainder)
        item["format"] = (
            css_unquote(format_match.group("value"))
            if format_match
            else None
        )
        sources.append(item)
    return sources


def parse_font_faces(
    path: Path,
    root: Path,
    text: str,
) -> list[dict[str, object]]:
    faces: list[dict[str, object]] = []
    clean = without_comments(text)
    for start, _end, body in extract_font_face_blocks(clean):
        declarations = {
            name: value
            for name, value, _offset in split_declarations(body)
        }
        family_raw = declarations.get("font-family")
        family = normalize_family(family_raw) if family_raw else None
        sources = font_sources(
            declarations.get("src"),
            source_file=path,
            root=root,
        )
        faces.append({
            "file": relative_path(path, root),
            "line": line_number(clean, start),
            "family": family,
            "sources": sources,
            "weight": weight_contract(declarations.get("font-weight")),
            "style": declarations.get("font-style", "normal").strip(),
            "display": (
                declarations.get("font-display", "").strip() or None
            ),
            "unicode_range": (
                declarations.get("unicode-range", "").strip() or None
            ),
            "provenance": {
                "status": "unresolved",
                "evidence_paths": [],
                "font_paths": [],
            },
        })
    return faces


def parse_font_shorthand(
    value: str,
) -> tuple[list[str], Optional[str], Optional[str]]:
    size = re.search(
        r"(?:^|\s)(?:\d*\.?\d+(?:px|pt|pc|em|rem|ex|ch|vw|vh|vmin|vmax|%)"
        r"|xx-small|x-small|small|medium|large|x-large|xx-large|smaller|larger)"
        r"(?:\s*/\s*[^\s]+)?\s+",
        value,
        re.I,
    )
    if not size:
        return [], None, None
    prefix = value[:size.start()].strip().casefold()
    families = family_list(value[size.end():])
    weight = next(
        (
            token
            for token in re.split(r"\s+", prefix)
            if token in {"normal", "bold"} or WEIGHT_NUMBER.fullmatch(token)
        ),
        None,
    )
    style = next(
        (
            token
            for token in re.split(r"\s+", prefix)
            if token in {"normal", "italic", "oblique"}
        ),
        None,
    )
    return families, weight, style


def resolve_css_variables(
    value: str,
    custom_properties: dict[str, str],
) -> str:
    pattern = re.compile(
        r"var\(\s*(?P<name>--[A-Za-z0-9_-]+)"
        r"(?:\s*,\s*(?P<fallback>[^()]*))?\s*\)",
        re.I,
    )
    resolved = value
    for _depth in range(8):
        changed = False

        def replace(match: re.Match[str]) -> str:
            nonlocal changed
            replacement = custom_properties.get(
                match.group("name").casefold()
            )
            if replacement is None:
                replacement = match.group("fallback")
            if replacement is None:
                return match.group(0)
            changed = True
            return replacement.strip()

        updated = pattern.sub(replace, resolved)
        resolved = updated
        if not changed:
            break
    return resolved


def usage_from_declarations(
    declarations: list[tuple[str, str, int]],
    *,
    file: str,
    line: int,
    context: str,
    source_kind: str,
    custom_properties: Optional[dict[str, str]] = None,
) -> Optional[dict[str, object]]:
    values = {name: value for name, value, _offset in declarations}
    custom_properties = custom_properties or {}
    families: list[str] = []
    weight = values.get("font-weight")
    style = values.get("font-style")
    if "font-family" in values:
        families = family_list(resolve_css_variables(
            values["font-family"],
            custom_properties,
        ))
    elif "font" in values:
        families, shorthand_weight, shorthand_style = parse_font_shorthand(
            resolve_css_variables(values["font"], custom_properties)
        )
        weight = weight or shorthand_weight
        style = style or shorthand_style
    if not families and weight is None and style is None:
        return None
    return {
        "file": file,
        "line": line,
        "context": " ".join(context.split())[:160],
        "source_kind": source_kind,
        "raw_stack": (
            values.get("font-family")
            or values.get("font")
            or None
        ),
        "families": families,
        "weight": weight,
        "normalized_weight": normalized_usage_weight(weight),
        "style": style,
    }


def custom_properties_from_source(
    path: Path,
    text: str,
) -> dict[str, set[str]]:
    """Collect static CSS custom-property candidates without treating them as use."""

    clean = without_comments(text)
    css_regions: list[str] = []
    if path.suffix.casefold() in CSS_SUFFIXES:
        css_regions.append(clean)
    elif path.suffix.casefold() not in SCRIPT_SUFFIXES:
        css_regions.extend(
            match.group("value") for match in HTML_STYLE_BLOCK.finditer(clean)
        )
    candidates: dict[str, set[str]] = {}
    for css in css_regions:
        for block in CSS_BLOCK.finditer(css):
            if block.group("header").strip().casefold().endswith("@font-face"):
                continue
            for name, value, _offset in split_declarations(
                block.group("body")
            ):
                if name.startswith("--"):
                    candidates.setdefault(name.casefold(), set()).add(value)
    return candidates


def parse_usages(
    path: Path,
    root: Path,
    text: str,
    *,
    shared_custom_properties: Optional[dict[str, str]] = None,
) -> list[dict[str, object]]:
    usages: list[dict[str, object]] = []
    clean = without_comments(text)
    relative = relative_path(path, root)
    css_regions: list[tuple[int, str]] = []
    inline_declarations: list[
        tuple[int, list[tuple[str, str, int]]]
    ] = []
    if path.suffix.casefold() in CSS_SUFFIXES:
        css_regions.append((0, clean))
    elif path.suffix.casefold() in SCRIPT_SUFFIXES:
        for offset, raw, _complete in theme_font_family_values(clean):
            families = configuration_families(raw)
            if not families:
                continue
            usages.append({
                "file": relative,
                "line": line_number(clean, offset),
                "context": "fontFamily theme/config declaration",
                "source_kind": "js-theme-font-family",
                "raw_stack": None,
                "families": families,
                "weight": None,
                "normalized_weight": 400,
                "style": None,
            })
    else:
        for match in HTML_STYLE_BLOCK.finditer(clean):
            css_regions.append((match.start("value"), match.group("value")))
        for match in HTML_STYLE_ATTR.finditer(clean):
            declarations = split_declarations(html.unescape(
                match.group("value")
            ))
            inline_declarations.append((match.start(), declarations))
    custom_properties = dict(shared_custom_properties or {})
    for _base_offset, css in css_regions:
        for block in CSS_BLOCK.finditer(css):
            for name, value, _offset in split_declarations(
                block.group("body")
            ):
                if name.startswith("--"):
                    custom_properties[name.casefold()] = value
    for offset, declarations in inline_declarations:
        usage = usage_from_declarations(
            declarations,
            file=relative,
            line=line_number(clean, offset),
            context="inline style",
            source_kind="html-inline-style",
            custom_properties=custom_properties,
        )
        if usage:
            usages.append(usage)
    for base_offset, css in css_regions:
        for block in CSS_BLOCK.finditer(css):
            if block.group("header").strip().casefold().endswith("@font-face"):
                continue
            usage = usage_from_declarations(
                split_declarations(block.group("body")),
                file=relative,
                line=line_number(clean, base_offset + block.start()),
                context=block.group("header"),
                source_kind="css-declaration",
                custom_properties=custom_properties,
            )
            if usage:
                usages.append(usage)
    return usages


def parse_attributes(raw: str) -> dict[str, Optional[str]]:
    attributes: dict[str, Optional[str]] = {}
    for match in ATTR.finditer(raw):
        name = match.group("name").casefold()
        value = (
            match.group("quoted")
            if match.group("quoted") is not None
            else match.group("unquoted")
        )
        attributes[name] = html.unescape(value) if value is not None else None
    return attributes


def parse_preloads(
    path: Path,
    root: Path,
    text: str,
) -> list[dict[str, object]]:
    preloads: list[dict[str, object]] = []
    clean = without_comments(text)
    if path.suffix.casefold() not in LINK_SUFFIXES:
        return preloads
    for match in HTML_TAG.finditer(clean):
        attrs = parse_attributes(match.group("attrs"))
        rel = (attrs.get("rel") or "").casefold().split()
        if "preload" not in rel or (attrs.get("as") or "").casefold() != "font":
            continue
        href = attrs.get("href")
        source = (
            resolve_local_source(href, source_file=path, root=root)
            if href is not None
            else {
                "kind": "missing-href",
                "value": "",
                "resolved_path": None,
                "exists": None,
                "locator_sha256": None,
                "data_summary": None,
            }
        )
        preloads.append({
            "file": relative_path(path, root),
            "line": line_number(clean, match.start()),
            "href": source["value"] if href is not None else None,
            "source": source,
            "type": attrs.get("type"),
            "crossorigin": (
                "crossorigin" in attrs or "crossorigin" in {
                    key.replace("-", "") for key in attrs
                }
            ),
        })
    return preloads


def google_families_from_url(value: str) -> list[str]:
    parsed = urlsplit(value)
    if (parsed.hostname or "").casefold() not in {
        "fonts.googleapis.com",
        "fonts.gstatic.com",
    }:
        return []
    families: list[str] = []
    for item in parse_qs(parsed.query).get("family", []):
        for segment in item.split("|"):
            family = (
                unquote(segment.split(":", 1)[0])
                .replace("+", " ")
                .strip()
            )
            if family:
                families.append(family)
    return sorted(set(families), key=str.casefold)


def quoted_values(value: str) -> list[str]:
    return [
        css_unquote(match.group(0))
        for match in re.finditer(
            r"\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'",
            value,
        )
    ]


def theme_font_family_values(
    text: str,
) -> Iterable[tuple[int, str, bool]]:
    """Yield bounded fontFamily configuration values and parse completeness."""
    for match in re.finditer(r"\bfontFamily\s*:", text, re.I):
        start = match.end()
        while start < len(text) and text[start].isspace():
            start += 1
        if start >= len(text):
            yield match.start(), "", False
            continue
        opener = text[start]
        if opener not in "[{":
            end = start
            quote: Optional[str] = None
            escaped = False
            while end < len(text) and end - start < 16_384:
                character = text[end]
                if quote:
                    if escaped:
                        escaped = False
                    elif character == "\\":
                        escaped = True
                    elif character == quote:
                        quote = None
                elif character in "\"'`":
                    quote = character
                elif character in ",\r\n}":
                    break
                end += 1
            yield (
                match.start(),
                text[start:end].strip(),
                quote is None and end - start < 16_384,
            )
            continue
        closing = {"]": "[", "}": "{"}
        stack: list[str] = []
        quote = None
        escaped = False
        end = start
        complete = False
        limit = min(len(text), start + 16_384)
        while end < limit:
            character = text[end]
            if quote:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = None
            elif character in "\"'`":
                quote = character
            elif character in "[{":
                stack.append(character)
            elif character in "]}":
                if not stack or stack[-1] != closing[character]:
                    break
                stack.pop()
                if not stack:
                    end += 1
                    complete = True
                    break
            end += 1
        yield match.start(), text[start:end].strip(), complete


def configuration_families(value: str) -> list[str]:
    without_quoted_keys = re.sub(
        r"(?:\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*')\s*:",
        "",
        value,
    )
    return quoted_values(without_quoted_keys)


def dynamic_configuration(value: str, *, structurally_complete: bool) -> bool:
    if (
        not structurally_complete
        or not value
        or re.search(
            r"\$\{|#\{|\{\{|\{%|<%|\.\.\.|`|\b(?:var|env|theme)\s*\(",
            value,
            re.I,
        )
    ):
        return True
    without_strings = re.sub(
        r"\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'",
        '""',
        value,
    )
    return bool(re.search(
        r"(?:^|[:,\[])\s*"
        r"(?!(?:true|false|null)\b)"
        r"[A-Za-z_$][A-Za-z0-9_$]*"
        r"(?:\s*(?:[,}\]]|\.|\(|$))",
        without_strings,
    ))


def dynamic_locator(value: str) -> bool:
    return bool(DYNAMIC_LOCATOR.search(value))


def static_call_object(
    text: str,
    binding: str,
) -> Optional[tuple[int, str]]:
    start_match = re.search(
        rf"\b{re.escape(binding)}\s*\(\s*\{{",
        text,
    )
    if not start_match:
        return None
    object_start = text.find("{", start_match.start())
    depth = 0
    quote: Optional[str] = None
    escaped = False
    for index in range(object_start, len(text)):
        character = text[index]
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in "\"'`":
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return start_match.start(), text[object_start + 1:index]
    return None


def parse_delivery_contracts(
    path: Path,
    root: Path,
    text: str,
) -> list[dict[str, object]]:
    contracts: list[dict[str, object]] = []
    clean = without_comments(text)
    relative = relative_path(path, root)

    def add(
        kind: str,
        offset: int,
        *,
        family: Optional[str] = None,
        static: bool = True,
        complete: bool = True,
        sources: Optional[list[dict[str, object]]] = None,
        details: Optional[dict[str, object]] = None,
    ) -> None:
        contracts.append({
            "kind": kind,
            "file": relative,
            "line": line_number(clean, offset),
            "family": family,
            "static": static,
            "complete": complete,
            "sources": sources or [],
            "details": details or {},
        })

    if path.suffix.casefold() in SCRIPT_SUFFIXES:
        for match in NEXT_FONT_IMPORT.finditer(clean):
            kind = match.group("kind").casefold()
            binding = match.group("binding").strip()
            if kind == "google":
                names = (
                    [
                        (
                            part.strip().split(" as ")[0].strip(),
                            part.strip().split(" as ")[-1].strip(),
                        )
                        for part in binding.strip("{}").split(",")
                        if part.strip()
                    ]
                    if binding.startswith("{")
                    else [(binding, binding)]
                )
                for imported_name, local_binding in names:
                    add(
                        "next-font-google",
                        match.start(),
                        family=imported_name.replace("_", " "),
                        details={
                            "binding": local_binding,
                            "imported_name": imported_name,
                        },
                    )
            else:
                local_binding = binding
                call = static_call_object(clean, local_binding)
                if not call:
                    add(
                        "next-font-local",
                        match.start(),
                        static=False,
                        complete=False,
                        details={"binding": local_binding},
                    )
                    continue
                _call_start, body = call
                source_values = [
                    value
                    for source_match in re.finditer(
                        r"\b(?:src|path)\s*:\s*"
                        r"(?P<value>\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*')",
                        body,
                        re.I,
                    )
                    for value in [source_match.group("value")]
                ]
                sources = [
                    {
                        **resolve_local_source(
                            value,
                            source_file=path,
                            root=root,
                        ),
                        "format": None,
                    }
                    for value in source_values
                ]
                dynamic = (
                    not source_values
                    or dynamic_configuration(
                        body,
                        structurally_complete=True,
                    )
                )
                add(
                    "next-font-local",
                    match.start(),
                    static=not dynamic,
                    complete=not dynamic,
                    sources=sources,
                    details={
                        "binding": local_binding,
                        "declared_weights": re.findall(
                            r"\bweight\s*:\s*[\"']([^\"']+)[\"']",
                            body,
                            re.I,
                        ),
                        "declared_styles": re.findall(
                            r"\bstyle\s*:\s*[\"']([^\"']+)[\"']",
                            body,
                            re.I,
                        ),
                    },
                )
        for offset, raw, structurally_complete in theme_font_family_values(
            clean
        ):
            values = configuration_families(raw)
            dynamic = dynamic_configuration(
                raw,
                structurally_complete=structurally_complete,
            )
            add(
                "theme-font-family",
                offset,
                family=values[0] if values else None,
                static=not dynamic,
                complete=not dynamic,
                details={"families": values},
            )

    for match in FONTSOURCE_IMPORT.finditer(clean):
        add(
            "fontsource-import",
            match.start(),
            family=match.group("family").replace("-", " "),
            details={
                "package": match.group("package"),
                "variant": match.group("variant"),
            },
        )

    if path.suffix.casefold() in CSS_SUFFIXES:
        for match in CSS_IMPORT.finditer(clean):
            exact = css_unquote(match.group("value"))
            dynamic = dynamic_locator(exact)
            sources = [] if dynamic else [{
                **resolve_local_source(
                    exact,
                    source_file=path,
                    root=root,
                ),
                "format": None,
            }]
            google_families = google_families_from_url(exact)
            add(
                (
                    "google-fonts-stylesheet"
                    if google_families
                    else "css-import"
                ),
                match.start(),
                family=google_families[0] if len(google_families) == 1 else None,
                static=not dynamic,
                complete=not dynamic,
                sources=sources,
                details={"families": google_families},
            )

    if path.suffix.casefold() in LINK_SUFFIXES:
        for match in STYLESHEET_LINK.finditer(clean):
            attrs = parse_attributes(match.group("attrs"))
            if "stylesheet" not in (attrs.get("rel") or "").casefold().split():
                continue
            href = attrs.get("href")
            if href is None:
                add(
                    "remote-stylesheet",
                    match.start(),
                    static=False,
                    complete=False,
                )
                continue
            dynamic = dynamic_locator(href)
            source = {
                **resolve_local_source(
                    href,
                    source_file=path,
                    root=root,
                ),
                "format": None,
            }
            google_families = google_families_from_url(href)
            add(
                (
                    "google-fonts-stylesheet"
                    if google_families
                    else "remote-stylesheet"
                    if source["kind"] == "remote-url"
                    else "stylesheet-link"
                ),
                match.start(),
                family=google_families[0] if len(google_families) == 1 else None,
                static=not dynamic,
                complete=not dynamic,
                sources=[source],
                details={"families": google_families},
            )
    return contracts


def signature_for(extension: str, prefix: bytes) -> dict[str, object]:
    raw = prefix[:4]
    signatures = {
        b"wOFF": "woff",
        b"wOF2": "woff2",
        b"OTTO": "opentype-cff",
        b"\x00\x01\x00\x00": "truetype-sfnt",
        b"true": "truetype-sfnt",
        b"typ1": "opentype-type1",
    }
    detected = signatures.get(raw, "embedded-opentype" if extension == ".eot" else "unknown")
    expected = {
        ".woff": {"woff"},
        ".woff2": {"woff2"},
        ".otf": {"opentype-cff", "truetype-sfnt", "opentype-type1"},
        ".ttf": {"truetype-sfnt"},
        ".eot": {"embedded-opentype"},
    }[extension]
    return {
        "first_four_bytes_hex": raw.hex(),
        "first_four_bytes_ascii": "".join(
            chr(byte) if 32 <= byte <= 126 else "."
            for byte in raw
        ),
        "detected": detected,
        "expected_for_extension": sorted(expected),
        "matches_extension": detected in expected,
    }


def inventory_font(
    path: Path,
    root: Path,
    budget: ResourceBudget,
) -> tuple[Optional[dict[str, object]], Optional[dict[str, object]]]:
    metadata = stable_metadata(path)
    size_bytes = int(metadata.st_size)
    if not budget.reserve_font(size_bytes):
        reason = (
            "font-exceeds-per-file-byte-limit"
            if size_bytes > MAX_FONT_BYTES
            else "total-font-byte-budget-exceeded"
        )
        return None, {
            "path": relative_path(path, root),
            "reason": reason,
            "size_bytes": size_bytes,
            "sha256": None,
        }
    digest, size, prefix = stable_font_digest(
        path,
        expected_identity=stable_identity(metadata),
    )
    extension = path.suffix.casefold()
    return {
        "path": relative_path(path, root),
        "sha256": digest,
        "size_bytes": size,
        "extension": extension,
        "container_signature": signature_for(extension, prefix),
        "provenance": {
            "status": "unresolved",
            "evidence_paths": [],
            "families": [],
        },
    }, None


def finding(
    finding_id: str,
    severity: str,
    confidence: str,
    file: str,
    line: int,
    message: str,
    suggestion: str,
    evidence: dict[str, object],
) -> dict[str, object]:
    return {
        "id": finding_id,
        "severity": severity,
        "confidence": confidence,
        "file": file,
        "line": line,
        "message": message,
        "suggestion": suggestion,
        "evidence": evidence,
    }


def collect_findings(
    *,
    binaries: list[dict[str, object]],
    faces: list[dict[str, object]],
    preloads: list[dict[str, object]],
    usages: list[dict[str, object]],
    delivery_contracts: list[dict[str, object]],
    unresolved_font_paths: list[str],
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for binary in binaries:
        signature = binary["container_signature"]
        if not signature["matches_extension"]:
            findings.append(finding(
                "font-container-signature-mismatch",
                "high",
                "exact-bytes",
                str(binary["path"]),
                1,
                "The font file signature does not match its filename extension.",
                "Replace the file, correct the extension, or verify the build artifact.",
                {"container_signature": signature},
            ))
    seen_faces: dict[tuple[object, ...], dict[str, object]] = {}
    for face in faces:
        if not face["family"]:
            findings.append(finding(
                "font-face-missing-family",
                "high",
                "exact-source",
                str(face["file"]),
                int(face["line"]),
                "@font-face has no usable font-family declaration.",
                "Declare the intended family explicitly.",
                {},
            ))
        if not face["sources"]:
            findings.append(finding(
                "font-face-missing-source",
                "high",
                "exact-source",
                str(face["file"]),
                int(face["line"]),
                "@font-face has no parseable src contract.",
                "Declare at least one intentional local, remote, or local-name source.",
                {},
            ))
        for source in face["sources"]:
            if source["kind"] == "local-file" and source["exists"] is False:
                findings.append(finding(
                    "missing-local-font-file",
                    "high",
                    "resolved-path",
                    str(face["file"]),
                    int(face["line"]),
                    "A local @font-face source does not exist in the project.",
                    "Add the referenced file or correct the URL.",
                    {"source": source},
                ))
            elif source["kind"] in {
                "unsafe-local-path", "unsupported-url-scheme",
            }:
                findings.append(finding(
                    "unsafe-font-source-reference",
                    "high",
                    "exact-source",
                    str(face["file"]),
                    int(face["line"]),
                    "A font source cannot be safely resolved within the project.",
                    "Use a project-contained relative or web-root URL.",
                    {"source": source},
                ))
        key = (
            str(face["family"]).casefold(),
            json.dumps(face["sources"], sort_keys=True),
            json.dumps(face["weight"], sort_keys=True),
            str(face["style"]).casefold(),
            face["unicode_range"],
        )
        if key in seen_faces:
            prior = seen_faces[key]
            findings.append(finding(
                "duplicate-font-face",
                "medium",
                "exact-source-contract",
                str(face["file"]),
                int(face["line"]),
                "This @font-face duplicates an earlier family/source contract.",
                "Remove the duplicate or differentiate its range, style, or source.",
                {
                    "first_file": prior["file"],
                    "first_line": prior["line"],
                    "family": face["family"],
                },
            ))
        else:
            seen_faces[key] = face

    for preload in preloads:
        source = preload["source"]
        if source["kind"] == "local-file" and source["exists"] is False:
            findings.append(finding(
                "missing-preloaded-font-file",
                "high",
                "resolved-path",
                str(preload["file"]),
                int(preload["line"]),
                "A font preload points to a missing local file.",
                "Correct or remove the preload.",
                {"source": source},
            ))
        elif source["kind"] in {
            "unsafe-local-path", "unsupported-url-scheme", "missing-href",
        }:
            findings.append(finding(
                "unsafe-font-preload",
                "high",
                "exact-source",
                str(preload["file"]),
                int(preload["line"]),
                "A font preload has no safely resolvable href.",
                "Use an existing project-contained path or an intentional HTTPS URL.",
                {"source": source},
            ))

    for contract in delivery_contracts:
        if not contract["complete"]:
            findings.append(finding(
                "dynamic-or-incomplete-font-contract",
                "medium",
                "exact-source",
                str(contract["file"]),
                int(contract["line"]),
                "A font delivery contract is dynamic or incomplete and was not resolved.",
                "Review the runtime configuration and rendered network/font selection.",
                {
                    "kind": contract["kind"],
                    "family": contract["family"],
                },
            ))
        for source in contract["sources"]:
            if source["kind"] == "local-file" and source["exists"] is False:
                findings.append(finding(
                    "missing-delivery-contract-font-file",
                    "high",
                    "resolved-path",
                    str(contract["file"]),
                    int(contract["line"]),
                    "A static font delivery contract references a missing local file.",
                    "Add the referenced file or correct the static configuration.",
                    {"kind": contract["kind"], "source": source},
                ))
            elif source["kind"] in {
                "unsafe-local-path", "unsupported-url-scheme",
            }:
                findings.append(finding(
                    "unsafe-delivery-contract-reference",
                    "high",
                    "exact-source",
                    str(contract["file"]),
                    int(contract["line"]),
                    "A delivery contract contains an unsafe font locator.",
                    "Use a contained local path or an intentional HTTPS endpoint.",
                    {"kind": contract["kind"], "source": source},
                ))

    faces_by_family: dict[str, list[dict[str, object]]] = {}
    for face in faces:
        if face["family"]:
            faces_by_family.setdefault(
                str(face["family"]).casefold(),
                [],
            ).append(face)
    referenced_families: set[str] = set()
    for usage in usages:
        families = [
            family
            for family in usage["families"]
            if family.casefold() not in GENERIC_FAMILIES
        ]
        referenced_families.update(family.casefold() for family in families)
        if not families:
            continue
        primary = families[0].casefold()
        contracts = faces_by_family.get(primary)
        if not contracts:
            continue
        weight = usage["normalized_weight"]
        if weight is not None and not any(
            contract["weight"]["valid"]
            and int(contract["weight"]["minimum"]) <= int(weight)
            <= int(contract["weight"]["maximum"])
            for contract in contracts
        ):
            findings.append(finding(
                "undeclared-font-weight",
                "medium",
                "paired-static-declaration",
                str(usage["file"]),
                int(usage["line"]),
                "A paired family/weight usage is outside every declared @font-face weight.",
                "Add the intended face, use a covered variable range, or correct the usage.",
                {
                    "family": families[0],
                    "weight": weight,
                    "declared_ranges": [
                        contract["weight"] for contract in contracts
                    ],
                },
            ))
        style = str(usage["style"] or "normal").casefold()
        if style in {"italic", "oblique"} and not any(
            str(contract["style"]).casefold().startswith(style)
            for contract in contracts
        ):
            findings.append(finding(
                "undeclared-font-style",
                "medium",
                "paired-static-declaration",
                str(usage["file"]),
                int(usage["line"]),
                "A paired family/style usage has no matching @font-face style.",
                "Add the intended style face or correct the declaration.",
                {
                    "family": families[0],
                    "style": style,
                    "declared_styles": [
                        contract["style"] for contract in contracts
                    ],
                },
            ))
    for family, contracts in faces_by_family.items():
        if family in referenced_families:
            continue
        first = contracts[0]
        findings.append(finding(
            "likely-unused-font-family",
            "low",
            "bounded-static-inventory",
            str(first["file"]),
            int(first["line"]),
            "The declared family is not referenced by any scanned font stack.",
            "Confirm runtime or canvas use; otherwise remove unused font loading.",
            {"family": first["family"], "face_count": len(contracts)},
        ))
    for unresolved_path in unresolved_font_paths:
        findings.append(finding(
            "missing-font-license-provenance-evidence",
            "medium",
            "bounded-project-inventory",
            unresolved_path,
            1,
            "This local font binary has no explicitly bound license or provenance evidence.",
            "Bind its source, license, redistribution terms, and approval to this exact font.",
            {"font_path": unresolved_path},
        ))
    return sorted(
        findings,
        key=lambda item: (
            str(item["file"]),
            int(item["line"]),
            str(item["id"]),
        ),
    )


def source_summary(
    faces: list[dict[str, object]],
    preloads: list[dict[str, object]],
    delivery_contracts: list[dict[str, object]],
) -> dict[str, int]:
    counts = {
        "local_file": 0,
        "remote_url": 0,
        "data_url": 0,
        "local_name": 0,
        "missing_local_file": 0,
        "unsafe_reference": 0,
    }
    sources = [
        source
        for face in faces
        for source in face["sources"]
    ] + [preload["source"] for preload in preloads] + [
        source
        for contract in delivery_contracts
        for source in contract["sources"]
    ]
    for source in sources:
        kind = str(source["kind"]).replace("-", "_")
        if kind in counts:
            counts[kind] += 1
        if source["kind"] == "local-file" and source["exists"] is False:
            counts["missing_local_file"] += 1
        if source["kind"] in {
            "unsafe-local-path", "unsupported-url-scheme", "missing-href",
        }:
            counts["unsafe_reference"] += 1
    return counts


def encode_bounded_report(
    result: dict[str, object],
    *,
    budget: ResourceBudget,
) -> bytes:
    budget.check_time()
    encoded = b""
    for _attempt in range(4):
        encoded = json.dumps(
            result,
            indent=2,
            ensure_ascii=True,
        ).encode("utf-8")
        resource_usage = result.get("resource_usage")
        if isinstance(resource_usage, dict):
            resource_usage["report_bytes"] = len(encoded)
    encoded = json.dumps(
        result,
        indent=2,
        ensure_ascii=True,
    ).encode("utf-8")
    if len(encoded) > MAX_REPORT_BYTES:
        raise AuditError(
            f"report-size-limit-exceeded: {len(encoded)} > {MAX_REPORT_BYTES}"
        )
    return encoded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if sys.version_info < MINIMUM_PYTHON:
        return failure(
            "python-version-unsupported",
            "font_audit.py requires Python 3.10 or newer.",
        )
    root = Path(os.path.abspath(os.fspath(args.project.expanduser())))
    try:
        if not root.is_dir():
            return failure(
                "unsafe-project",
                "Project root is not an existing directory.",
                path=str(root),
            )
        if is_reparse(root):
            return failure(
                "unsafe-project",
                "Project root is a reparse point.",
                path=str(root),
            )
        budget = ResourceBudget()
        source_files, font_files, evidence_candidates = enumerate_project(
            root,
            budget,
        )
        binaries: list[dict[str, object]] = []
        skipped_fonts: list[dict[str, object]] = []
        for path in font_files:
            inventory, skipped = inventory_font(path, root, budget)
            if inventory is not None:
                binaries.append(inventory)
            if skipped is not None:
                skipped_fonts.append(skipped)
        faces: list[dict[str, object]] = []
        preloads: list[dict[str, object]] = []
        usages: list[dict[str, object]] = []
        delivery_contracts: list[dict[str, object]] = []
        license_evidence: list[dict[str, object]] = []
        skipped_sources: list[dict[str, object]] = []
        read_cache: dict[
            Path,
            tuple[Optional[str], Optional[dict[str, object]]],
        ] = {}
        custom_property_candidates: dict[str, set[str]] = {}
        scanned_source_file_count = 0
        skipped_source_file_count = 0
        for path in source_files:
            text, skipped = read_eligible_source(
                path,
                root=root,
                budget=budget,
            )
            read_cache[path] = (text, skipped)
            if skipped is not None:
                if skipped not in skipped_sources:
                    skipped_sources.append(skipped)
                skipped_source_file_count += 1
                continue
            assert text is not None
            scanned_source_file_count += 1
            license_evidence.extend(
                comment_license_evidence(path, root, text)
            )
            faces.extend(parse_font_faces(path, root, text))
            preloads.extend(parse_preloads(path, root, text))
            for name, values in custom_properties_from_source(
                path,
                text,
            ).items():
                custom_property_candidates.setdefault(name, set()).update(
                    values
                )
            delivery_contracts.extend(
                parse_delivery_contracts(path, root, text)
            )

        # Resolve only globally unambiguous static values. Merely defining a
        # font-valued token never counts as family use; a scanned font or
        # shorthand declaration must actually reference it. File-local values
        # still override this shared project evidence in parse_usages().
        shared_custom_properties = {
            name: next(iter(values))
            for name, values in custom_property_candidates.items()
            if len(values) == 1
        }
        for path in source_files:
            text, skipped = read_cache[path]
            if skipped is not None or text is None:
                continue
            usages.extend(parse_usages(
                path,
                root,
                text,
                shared_custom_properties=shared_custom_properties,
            ))

        binary_paths = {
            str(binary["path"]): binary
            for binary in binaries
        }
        known_families = sorted({
            str(face["family"])
            for face in faces
            if face["family"]
        }, key=str.casefold)
        family_to_font_paths: dict[str, set[str]] = {}
        for face in faces:
            if not face["family"]:
                continue
            family_key = str(face["family"]).casefold()
            for source in face["sources"]:
                resolved = source.get("resolved_path")
                if (
                    source["kind"] == "local-file"
                    and source["exists"] is True
                    and resolved in binary_paths
                ):
                    family_to_font_paths.setdefault(
                        family_key,
                        set(),
                    ).add(str(resolved))
        binary_name_counts: dict[str, int] = {}
        for binary_path in binary_paths:
            name = Path(binary_path).name.casefold()
            binary_name_counts[name] = binary_name_counts.get(name, 0) + 1

        def contains_token(haystack: str, needle: str) -> bool:
            return bool(re.search(
                rf"(?<![A-Za-z0-9_.-]){re.escape(needle)}"
                rf"(?![A-Za-z0-9_.-])",
                haystack,
                re.I,
            ))

        def named_font_paths(
            binding_text: str,
            *,
            evidence_path: Optional[Path] = None,
        ) -> set[str]:
            normalized = binding_text.replace("\\", "/")
            matches: set[str] = set()
            for binary_path in binary_paths:
                name = Path(binary_path).name
                binary_file = root / binary_path
                if contains_token(normalized, binary_path):
                    matches.add(binary_path)
                    continue
                basename_is_unambiguous = (
                    binary_name_counts[name.casefold()] == 1
                )
                same_directory = (
                    evidence_path is not None
                    and binary_file.parent == evidence_path.parent
                )
                if (
                    (basename_is_unambiguous or same_directory)
                    and contains_token(normalized, name)
                ):
                    matches.add(binary_path)
                    continue
                if (
                    same_directory
                    and re.search(
                        rf"(?:^|[._-]){re.escape(binary_file.stem)}"
                        rf"(?:[._-]|$)",
                        evidence_path.name,
                        re.I,
                    )
                ):
                    matches.add(binary_path)
            return matches

        def named_font_families(binding_text: str) -> set[str]:
            return {
                family
                for family in known_families
                if contains_token(binding_text, family)
            }

        for evidence in license_evidence:
            binding_text = str(evidence.pop("_binding_text", ""))
            matching_faces = [
                face
                for face in faces
                if face["file"] == evidence["path"]
            ]
            local_paths = {
                str(source["resolved_path"])
                for face in matching_faces
                for source in face["sources"]
                if (
                    source["kind"] == "local-file"
                    and source["exists"] is True
                    and source["resolved_path"] in binary_paths
                )
            }
            local_families = {
                str(face["family"])
                for face in matching_faces
                if face["family"]
            }
            explicit_families = named_font_families(binding_text)
            explicit_paths = named_font_paths(binding_text)
            explicit_paths.update(
                binary_path
                for family in explicit_families
                for binary_path in family_to_font_paths.get(
                    family.casefold(),
                    set(),
                )
            )
            has_named_binding = bool(explicit_paths or explicit_families)
            if not explicit_paths and len(local_paths) == 1:
                explicit_paths.update(local_paths)
            if (
                not has_named_binding
                and not explicit_families
                and len(local_families) == 1
            ):
                explicit_families.update(local_families)
            evidence["applies_to_font_paths"] = sorted(explicit_paths)
            evidence["applies_to_families"] = sorted(
                explicit_families,
                key=str.casefold,
            )

        for path in evidence_candidates:
            text, skipped = read_cache.get(path, (None, None))
            if path not in read_cache:
                text, skipped = read_eligible_source(
                    path,
                    root=root,
                    budget=budget,
                )
                read_cache[path] = (text, skipped)
            if skipped is not None:
                if skipped not in skipped_sources:
                    skipped_sources.append(skipped)
                continue
            assert text is not None
            if not LICENSE_TEXT.search(text):
                continue
            payload = text.encode("utf-8")
            same_directory_paths = sorted(
                str(binary["path"])
                for binary in binaries
                if (root / str(binary["path"])).parent == path.parent
            )
            binding_text = f"{path.name}\n{text}"
            named_paths = named_font_paths(
                binding_text,
                evidence_path=path,
            )
            named_families = named_font_families(binding_text)
            named_paths.update(
                binary_path
                for family in named_families
                for binary_path in family_to_font_paths.get(
                    family.casefold(),
                    set(),
                )
            )
            if not named_paths and len(same_directory_paths) == 1:
                named_paths.add(same_directory_paths[0])
            applies_to_paths = sorted(named_paths)
            if not applies_to_paths and not named_families:
                continue
            license_evidence.append({
                "path": relative_path(path, root),
                "kind": (
                    "font-license-file"
                    if same_directory_paths
                    else "license-file"
                ),
                "line": 1,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "applies_to_font_paths": applies_to_paths,
                "applies_to_families": sorted(
                    named_families,
                    key=str.casefold,
                ),
            })
        asset_manifest = root / ".design-dna" / "assets.yml"
        if asset_manifest.is_file():
            if is_reparse(asset_manifest):
                raise AuditError(f"reparse-point-refused: {asset_manifest}")
            manifest_text, skipped = read_cache.get(
                asset_manifest,
                (None, None),
            )
            if asset_manifest not in read_cache:
                manifest_text, skipped = read_eligible_source(
                    asset_manifest,
                    root=root,
                    budget=budget,
                )
                read_cache[asset_manifest] = (manifest_text, skipped)
            if skipped is not None:
                if skipped not in skipped_sources:
                    skipped_sources.append(skipped)
            elif (
                manifest_text is not None
                and re.search(
                    r"(?im)\b(?:license|licence|provenance|source|rights)\b",
                    manifest_text,
                )
            ):
                manifest_paths = named_font_paths(manifest_text)
                manifest_families = named_font_families(manifest_text)
                manifest_paths.update(
                    binary_path
                    for family in manifest_families
                    for binary_path in family_to_font_paths.get(
                        family.casefold(),
                        set(),
                    )
                )
                if manifest_paths or manifest_families:
                    payload = manifest_text.encode("utf-8")
                    license_evidence.append({
                        "path": ".design-dna/assets.yml",
                        "kind": "asset-provenance-manifest",
                        "line": 1,
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "applies_to_font_paths": sorted(manifest_paths),
                        "applies_to_families": sorted(
                            manifest_families,
                            key=str.casefold,
                        ),
                    })
        license_evidence = sorted(
            {
                (
                    str(item["path"]),
                    str(item["kind"]),
                    int(item["line"]),
                    str(item["sha256"]),
                    tuple(item["applies_to_font_paths"]),
                    tuple(item["applies_to_families"]),
                ): item
                for item in license_evidence
            }.values(),
            key=lambda item: (
                str(item["path"]),
                int(item["line"]),
                str(item["kind"]),
            ),
        )
        evidence_by_font: dict[str, list[str]] = {
            path: [] for path in binary_paths
        }
        evidence_by_family: dict[str, list[str]] = {}
        for evidence in license_evidence:
            evidence_path = str(evidence["path"])
            for binary_path in evidence["applies_to_font_paths"]:
                if binary_path in evidence_by_font:
                    evidence_by_font[binary_path].append(evidence_path)
            for family in evidence["applies_to_families"]:
                evidence_by_family.setdefault(
                    str(family).casefold(),
                    [],
                ).append(evidence_path)
        for binary in binaries:
            path = str(binary["path"])
            bound = sorted(set(evidence_by_font.get(path, [])))
            binary["provenance"] = {
                "status": "resolved" if bound else "unresolved",
                "evidence_paths": bound,
                "families": sorted({
                    str(face["family"])
                    for face in faces
                    if face["family"] and any(
                        source["resolved_path"] == path
                        for source in face["sources"]
                        if source["kind"] == "local-file"
                    )
                }, key=str.casefold),
            }
        for face in faces:
            local_paths = sorted({
                str(source["resolved_path"])
                for source in face["sources"]
                if (
                    source["kind"] == "local-file"
                    and source["resolved_path"] is not None
                )
            })
            evidence_paths = sorted({
                evidence_path
                for path in local_paths
                for evidence_path in evidence_by_font.get(path, [])
            } | set(
                evidence_by_family.get(
                    str(face["family"] or "").casefold(),
                    [],
                )
            ))
            face["provenance"] = {
                "status": "resolved" if evidence_paths else "unresolved",
                "evidence_paths": evidence_paths,
                "font_paths": local_paths,
            }
        unresolved_font_paths = sorted(
            path
            for path, binary in binary_paths.items()
            if binary["provenance"]["status"] == "unresolved"
        )
        findings = collect_findings(
            binaries=binaries,
            faces=faces,
            preloads=preloads,
            usages=usages,
            delivery_contracts=delivery_contracts,
            unresolved_font_paths=unresolved_font_paths,
        )
        for skipped in skipped_sources:
            findings.append(finding(
                "font-audit-source-unscanned",
                "high",
                "exact-source",
                str(skipped["path"]),
                1,
                "An eligible font-contract or provenance source was not scanned.",
                "Reduce or convert the source, or review it separately before relying on this audit.",
                {"skipped_source": skipped},
            ))
        for skipped in skipped_fonts:
            findings.append(finding(
                "font-binary-unscanned",
                "high",
                "exact-source",
                str(skipped["path"]),
                1,
                "An eligible local font binary was not inventoried.",
                "Reduce the artifact or review its integrity and provenance separately.",
                {"skipped_font": skipped},
            ))
        findings.sort(
            key=lambda item: (
                str(item["file"]),
                int(item["line"]),
                str(item["id"]),
            )
        )
        severity_counts = {
            severity: sum(
                finding_["severity"] == severity
                for finding_ in findings
            )
            for severity in ("high", "medium", "low")
        }
        dynamic_contract_count = sum(
            not contract["complete"]
            for contract in delivery_contracts
        )
        incomplete = bool(
            skipped_sources
            or skipped_fonts
            or dynamic_contract_count
            or budget.exceeded
        )
        review_required = bool(findings) or incomplete
        evidence_count = (
            len(binaries)
            + len(faces)
            + len(preloads)
            + len(usages)
            + len(delivery_contracts)
        )
        audit_status = (
            "incomplete"
            if incomplete
            else "review-required"
            if review_required
            else "no-font-evidence"
            if evidence_count == 0
            else "complete"
        )
        declared_stacks = [
            {
                "file": usage["file"],
                "line": usage["line"],
                "context": usage["context"],
                "source_kind": usage["source_kind"],
                "raw": usage["raw_stack"],
                "families": usage["families"],
            }
            for usage in usages
            if usage["families"]
        ]
        declared_weights = [
            {
                "file": usage["file"],
                "line": usage["line"],
                "context": usage["context"],
                "source_kind": usage["source_kind"],
                "raw": usage["weight"],
                "normalized": usage["normalized_weight"],
                "paired_families": usage["families"],
                "style": usage["style"],
            }
            for usage in usages
            if usage["weight"] is not None or usage["style"] is not None
        ]
        result = {
            "schema_version": SCHEMA_VERSION,
            "artifact_type": ARTIFACT_TYPE,
            "ok": not incomplete,
            "execution_ok": True,
            "execution": {"status": "succeeded", "ok": True},
            "project": "project:/",
            "disclaimer": (
                "This is a bounded local source and file-integrity audit. It "
                "does not identify an AI font, infer authorship, or prove "
                "rendered typography quality, licensing rights, or browser use."
            ),
            "audit_status": audit_status,
            "source_integrity_complete": not incomplete,
            "exit_code": 1 if incomplete else 0,
            "scan_scope": {
                "source_suffixes": sorted(SOURCE_SUFFIXES),
                "font_suffixes": sorted(FONT_SUFFIXES),
                "ignored_directories": sorted(
                    [
                        *IGNORED_DIRS,
                        *(f"{prefix}*" for prefix in IGNORED_DIR_PREFIXES),
                    ]
                ),
                "source_file_count": len(source_files),
                "scanned_source_file_count": scanned_source_file_count,
                "skipped_source_file_count": skipped_source_file_count,
                "font_binary_count": len(binaries),
                "skipped_font_binary_count": len(skipped_fonts),
                "eligible_file_count": len(source_files) + len(font_files),
            },
            "completeness": {
                "complete": not incomplete,
                "status": "incomplete" if incomplete else "complete",
                "skipped_source_count": len(skipped_sources),
                "skipped_font_count": len(skipped_fonts),
                "dynamic_contract_count": dynamic_contract_count,
                "budget_exceeded": sorted(budget.exceeded),
            },
            "resource_limits": budget.limits(),
            "resource_usage": budget.usage(),
            "font_binaries": binaries,
            "skipped_sources": skipped_sources,
            "skipped_font_binaries": skipped_fonts,
            "font_faces": faces,
            "preloads": preloads,
            "delivery_contracts": delivery_contracts,
            "declared_stacks": declared_stacks,
            "declared_weights": declared_weights,
            "source_summary": source_summary(
                faces,
                preloads,
                delivery_contracts,
            ),
            "license_provenance": {
                "explicit_evidence_found": bool(license_evidence),
                "resolved_font_paths": sorted(
                    set(binary_paths) - set(unresolved_font_paths)
                ),
                "unresolved_font_paths": unresolved_font_paths,
                "evidence": license_evidence,
            },
            "findings": findings,
            "counts": severity_counts,
            "review_required": review_required,
            "review": {
                "required": review_required,
                "status": "pending" if review_required else "not-triggered",
                "finding_count": len(findings),
            },
            "limitations": [
                (
                    "Static source parsing cannot prove computed styles, "
                    "runtime-generated family names, canvas text, or actual "
                    "network and browser font selection."
                ),
                (
                    "Container signatures and file hashes do not validate all "
                    "font tables, glyph coverage, visual quality, or legal rights."
                ),
                (
                    "Unused and mismatch findings are bounded to explicit "
                    "scanned declarations and require human confirmation."
                ),
            ],
        }
        encoded = encode_bounded_report(result, budget=budget)
        sys.stdout.buffer.write(encoded + b"\n")
        return 1 if incomplete else 0
    except (AuditError, OSError, ValueError) as exc:
        return failure("font-audit-failed", str(exc), path=str(root))


if __name__ == "__main__":
    raise SystemExit(main())
