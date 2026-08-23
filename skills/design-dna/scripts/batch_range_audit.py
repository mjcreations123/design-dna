#!/usr/bin/env python3
"""Verify evidence coverage for a controlled batch of unrelated websites.

The tool checks portable paths, exact evidence bytes, build isolation, route and
viewport coverage, and review-protocol records. It never scores aesthetics,
detects authorship, or automatically approves visual quality.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import io
import json
import math
import os
import posixpath
import re
import struct
import sys
import tempfile
import unicodedata
import warnings
import zlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit


SCHEMA_VERSION = 1
TOOL_VERSION = "1.2.0"
ARTIFACT_TYPE = "design-dna-batch-range-audit"
DEFAULT_CONTRACT = ".design-dna/batch-range.json"
DEFAULT_OUTPUT = ".design-dna/batch-range-audit.json"
MAX_CONTRACT_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_EVIDENCE_BYTES = 1024 * 1024 * 1024
MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_ATLAS_IMAGES = 200
MAX_PUBLIC_BUILD_FILES = 4096
MAX_PUBLIC_BUILD_BYTES = 256 * 1024 * 1024
MAX_PUBLIC_BUILD_FILE_BYTES = 128 * 1024 * 1024
ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PUBLIC_EXTENSIONS = {
    ".avif", ".css", ".gif", ".htm", ".html", ".ico", ".jpeg",
    ".jpg", ".js", ".json", ".mjs", ".mp4", ".otf", ".pdf", ".png",
    ".svg", ".ttf", ".txt", ".wasm", ".webm", ".webmanifest", ".webp",
    ".woff", ".woff2", ".xml",
}
DENIED_PUBLIC_SEGMENTS = {
    ".design-dna", ".git", ".github", ".hg", ".svn", "config",
    "maintainer", "node_modules", "private", "scripts", "secrets", "source",
    "src", "test", "tests",
}
DENIED_PUBLIC_FILENAMES = {
    ".env", ".npmrc", ".pypirc", "composer.json", "composer.lock",
    "credentials.json", "package-lock.json", "package.json", "pnpm-lock.yaml",
    "pyproject.toml", "requirements.txt", "secrets.json", "tsconfig.json",
    "yarn.lock",
}
HUMAN_CONTEXTUAL_DISPOSITION_STATUSES = {
    "pending",
    "no-material-cluster-observed",
    "revisions-required",
    "accepted-contextual-risk",
    "blocked",
}
CONTEXTUAL_FINDING_SEVERITIES = {"low", "medium", "high", "critical"}
CONTEXTUAL_FINDING_IMPACTS = {
    "informational",
    "bounded",
    "material",
    "release-blocking",
}


class AuditError(RuntimeError):
    """A fatal contract, integrity, or safety failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class EvidenceBudget:
    def __init__(self) -> None:
        self.files = 0
        self.bytes = 0
        self.paths: set[str] = set()

    def add(self, size: int) -> None:
        if size > MAX_EVIDENCE_BYTES:
            raise AuditError(
                "evidence-file-too-large",
                f"An evidence file exceeds {MAX_EVIDENCE_BYTES} bytes.",
            )
        if self.bytes + size > MAX_TOTAL_EVIDENCE_BYTES:
            raise AuditError(
                "evidence-total-too-large",
                "Evidence inputs exceed the cumulative audit byte limit.",
            )
        self.files += 1
        self.bytes += size


def require_object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AuditError("invalid-contract", f"{label} must be a JSON object.")
    return value


def require_array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise AuditError("invalid-contract", f"{label} must be a JSON array.")
    return value


def require_string(
    value: object,
    label: str,
    *,
    minimum: int = 1,
    maximum: int = 4000,
) -> str:
    if not isinstance(value, str) or not (minimum <= len(value) <= maximum):
        raise AuditError(
            "invalid-contract",
            f"{label} must contain {minimum} to {maximum} characters.",
        )
    if any(ord(character) < 0x20 and character not in "\t\n\r" for character in value):
        raise AuditError("invalid-contract", f"{label} contains a control character.")
    return value


def require_bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise AuditError("invalid-contract", f"{label} must be a boolean.")
    return value


def require_id(value: object, label: str) -> str:
    identifier = require_string(value, label, maximum=64)
    if ID_PATTERN.fullmatch(identifier) is None:
        raise AuditError(
            "invalid-contract",
            f"{label} must match {ID_PATTERN.pattern}.",
        )
    return identifier


def reject_extra(value: dict[str, Any], allowed: set[str], label: str) -> None:
    extras = sorted(set(value) - allowed)
    if extras:
        raise AuditError(
            "invalid-contract",
            f"{label} contains unsupported properties: {', '.join(extras)}.",
        )


def require_datetime(value: object, label: str) -> str:
    text = require_string(value, label, maximum=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuditError("invalid-contract", f"{label} is not an ISO date-time.") from exc
    if parsed.tzinfo is None:
        raise AuditError("invalid-contract", f"{label} must include a time zone.")
    return text


def utc_datetime(value: str) -> datetime:
    """Parse an already validated zoned ISO timestamp into one UTC instant."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def portable_path(value: object, label: str) -> str:
    text = require_string(value, label, maximum=1000)
    if "\\" in text or "\x00" in text or ":" in text:
        raise AuditError(
            "invalid-portable-path",
            f"{label} must use a portable project-relative POSIX path.",
        )
    path = PurePosixPath(text)
    if path.is_absolute() or not path.parts:
        raise AuditError("invalid-portable-path", f"{label} must be relative.")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise AuditError(
            "invalid-portable-path",
            f"{label} cannot contain empty, dot, or parent segments.",
        )
    normalized = path.as_posix()
    if normalized != text:
        raise AuditError(
            "invalid-portable-path",
            f"{label} must already be normalized as {normalized!r}.",
        )
    return normalized


def portable_key(value: str) -> str:
    """Return a cross-platform collision key for a portable persisted path."""

    return unicodedata.normalize("NFC", value).casefold()


def project_path(root: Path, relative: str, label: str) -> Path:
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise AuditError(
            "path-outside-project",
            f"{label} resolves outside the project root.",
        ) from exc
    current = candidate
    while current != root:
        if current.exists() and current.is_symlink():
            raise AuditError(
                "linked-path-refused",
                f"{label} crosses a symbolic link.",
            )
        current = current.parent
    return candidate


def stable_read(path: Path, maximum: int, label: str) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise AuditError("evidence-missing", f"{label} is not an ordinary file.")
    before = path.stat()
    if before.st_size > maximum:
        raise AuditError("evidence-file-too-large", f"{label} exceeds {maximum} bytes.")
    payload = path.read_bytes()
    after = path.stat()
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    if identity_before != identity_after or len(payload) != before.st_size:
        raise AuditError("unstable-evidence", f"{label} changed while it was read.")
    return payload


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify_file_ref(
    value: object,
    root: Path,
    budget: EvidenceBudget,
    label: str,
    *,
    capture: bool = False,
    require_non_empty: bool = False,
) -> tuple[dict[str, object], Path, bytes, dict[str, object] | None]:
    item = require_object(value, label)
    reject_extra(item, {"path", "sha256"}, label)
    relative = portable_path(item.get("path"), f"{label}.path")
    expected = require_string(item.get("sha256"), f"{label}.sha256", maximum=64)
    if SHA256_PATTERN.fullmatch(expected) is None:
        raise AuditError(
            "invalid-contract",
            f"{label}.sha256 must be an exact lowercase SHA-256 digest.",
        )
    path = project_path(root, relative, f"{label}.path")
    payload = stable_read(path, MAX_EVIDENCE_BYTES, label)
    if require_non_empty and not payload:
        raise AuditError(
            "review-evidence-empty",
            f"{label} must contain recorded review observations.",
        )
    budget.add(len(payload))
    budget.paths.add(portable_key(relative))
    actual = sha256(payload)
    if actual != expected:
        code = "capture-hash-mismatch" if capture else "evidence-hash-mismatch"
        raise AuditError(code, f"{label} does not match its declared SHA-256.")
    media = validate_capture_media(path, payload, label) if capture else None
    return {
        "path": relative,
        "sha256": actual,
        "bytes": len(payload),
        "verified": True,
    }, path, payload, media


def validate_capture_media(path: Path, payload: bytes, label: str) -> dict[str, object]:
    suffix = path.suffix.casefold()
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        kind = "png"
    elif payload.startswith(b"\xff\xd8\xff"):
        kind = "jpeg"
    elif len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
        kind = "webp"
    else:
        raise AuditError(
            "capture-media-invalid",
            f"{label} is not a PNG, JPEG, or WebP image.",
        )
    allowed = {
        "png": {".png"},
        "jpeg": {".jpg", ".jpeg"},
        "webp": {".webp"},
    }
    if suffix not in allowed[kind]:
        raise AuditError(
            "capture-media-mismatch",
            f"{label} has a {kind} signature but a mismatched extension.",
        )
    if kind == "png":
        width, height = decode_png(payload, label)
    else:
        width, height = decode_with_pillow(payload, label, kind)
    return {"media_type": kind, "width": width, "height": height}


def decode_png(payload: bytes, label: str) -> tuple[int, int]:
    """Boundedly decode the exact hashed PNG bytes without a third-party runtime."""
    offset = 8
    width = height = bit_depth = color_type = None
    compressed_parts: list[memoryview] = []
    compressed_bytes = 0
    seen_ihdr = seen_idat = seen_iend = seen_plte = False
    idat_ended = False
    while offset < len(payload):
        if offset + 12 > len(payload):
            raise AuditError("capture-media-unreadable", f"{label} has a truncated PNG chunk header.")
        length = struct.unpack(">I", payload[offset:offset + 4])[0]
        chunk_type = payload[offset + 4:offset + 8]
        chunk_end = offset + 12 + length
        if chunk_end > len(payload):
            raise AuditError("capture-media-unreadable", f"{label} has truncated PNG chunk data.")
        # Keep views into the already bounded payload instead of duplicating
        # every IDAT chunk in a second study-sized bytearray.
        chunk_data = memoryview(payload)[offset + 8:offset + 8 + length]
        recorded_crc = struct.unpack(">I", payload[offset + 8 + length:chunk_end])[0]
        actual_crc = binascii.crc32(chunk_type)
        actual_crc = binascii.crc32(chunk_data, actual_crc) & 0xFFFFFFFF
        if actual_crc != recorded_crc:
            raise AuditError("capture-media-unreadable", f"{label} has an invalid PNG chunk checksum.")

        if chunk_type == b"IHDR":
            if seen_ihdr or offset != 8 or length != 13:
                raise AuditError("capture-media-unreadable", f"{label} must begin with one valid PNG IHDR.")
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", chunk_data
            )
            valid_depths = {
                0: {1, 2, 4, 8, 16},
                2: {8, 16},
                3: {1, 2, 4, 8},
                4: {8, 16},
                6: {8, 16},
            }
            if (
                width < 1
                or height < 1
                or width > 32768
                or height > 131072
                or width * height > 64_000_000
                or compression != 0
                or filtering != 0
                or interlace != 0
                or color_type not in valid_depths
                or bit_depth not in valid_depths[color_type]
            ):
                raise AuditError("capture-media-unreadable", f"{label} has unsupported PNG dimensions or format.")
            seen_ihdr = True
        elif chunk_type == b"PLTE":
            if not seen_ihdr or seen_idat or not 1 <= length <= 768 or length % 3:
                raise AuditError("capture-media-unreadable", f"{label} has an invalid PNG palette.")
            seen_plte = True
        elif chunk_type == b"IDAT":
            if not seen_ihdr or seen_iend or idat_ended:
                raise AuditError("capture-media-unreadable", f"{label} has out-of-order PNG image data.")
            seen_idat = True
            compressed_parts.append(chunk_data)
            compressed_bytes += length
            if compressed_bytes > MAX_EVIDENCE_BYTES:
                raise AuditError("capture-media-unreadable", f"{label} exceeds the PNG compressed-data limit.")
        elif chunk_type == b"IEND":
            if not seen_idat or seen_iend or length:
                raise AuditError("capture-media-unreadable", f"{label} has an invalid PNG ending.")
            seen_iend = True
            offset = chunk_end
            break
        else:
            if seen_idat:
                idat_ended = True
            if chunk_type[:1].isupper():
                raise AuditError("capture-media-unreadable", f"{label} contains an unsupported critical PNG chunk.")
        offset = chunk_end

    if (
        not seen_ihdr
        or not seen_idat
        or not seen_iend
        or offset != len(payload)
        or (color_type == 3 and not seen_plte)
    ):
        raise AuditError("capture-media-unreadable", f"{label} is an incomplete PNG image.")
    assert isinstance(width, int) and isinstance(height, int)
    assert isinstance(bit_depth, int) and isinstance(color_type, int)
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    row_bytes = math.ceil(width * channels * bit_depth / 8)
    expected_bytes = height * (row_bytes + 1)
    if expected_bytes > MAX_EVIDENCE_BYTES:
        raise AuditError("capture-media-unreadable", f"{label} exceeds the PNG decoded-data limit.")
    try:
        decoder = zlib.decompressobj()
        decoded = bytearray()
        for part in compressed_parts:
            pending: bytes | memoryview = part
            while pending:
                remaining = expected_bytes + 1 - len(decoded)
                if remaining <= 0:
                    break
                decoded.extend(decoder.decompress(pending, remaining))
                pending = decoder.unconsumed_tail
            if len(decoded) > expected_bytes:
                break
        decoded.extend(decoder.flush(max(1, expected_bytes + 1 - len(decoded))))
    except zlib.error as exc:
        raise AuditError("capture-media-unreadable", f"{label} PNG pixels cannot be decoded: {exc}.") from exc
    if (
        len(decoded) != expected_bytes
        or not decoder.eof
        or decoder.unused_data
        or decoder.unconsumed_tail
    ):
        raise AuditError("capture-media-unreadable", f"{label} PNG pixels do not match its dimensions.")
    for row in range(height):
        if decoded[row * (row_bytes + 1)] > 4:
            raise AuditError("capture-media-unreadable", f"{label} has an invalid PNG row filter.")
    return width, height


def decode_with_pillow(payload: bytes, label: str, kind: str) -> tuple[int, int]:
    """Decode non-PNG capture bytes when the optional image runtime is present."""
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise AuditError(
            "capture-decoder-unavailable",
            f"{label} is {kind}; full JPEG/WebP verification requires Pillow.",
        ) from exc
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(payload)) as opened:
                opened.verify()
            with Image.open(io.BytesIO(payload)) as opened:
                width, height = opened.size
                if width < 1 or height < 1 or width * height > 64_000_000:
                    raise AuditError("capture-media-unreadable", f"{label} has unsupported image dimensions.")
                opened.load()
    except AuditError:
        raise
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise AuditError("capture-media-unreadable", f"{label} cannot be decoded as {kind}.") from exc
    return width, height


def canonical_sha256(value: object) -> str:
    """Hash compact UTF-8 JSON using the renderer's stable field order."""

    return sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def public_snapshot_path_allowed(relative: str, *, directory: bool) -> bool:
    parts = [part for part in PurePosixPath(relative).parts if part]
    folded = [part.casefold() for part in parts]
    if not parts or any(
        part.startswith(".") or part in DENIED_PUBLIC_SEGMENTS for part in folded
    ):
        return False
    if directory:
        return True
    name = folded[-1]
    suffix = PurePosixPath(name).suffix
    if (
        name in DENIED_PUBLIC_FILENAMES
        or name.startswith(".env")
        or name.endswith(".map")
        or re.search(
            r"(?:^|[-_.])(credential|private[-_]?key|secret|token)(?:[-_.]|$)",
            name,
        )
        or re.search(
            r"(?:^|\.)(?:babel|eslint|next|nuxt|postcss|prettier|rollup|tailwind|vite|webpack)\.config\.",
            name,
        )
    ):
        return False
    return suffix in PUBLIC_EXTENSIONS


def enumerate_public_snapshot(root: Path, label: str) -> list[str]:
    """Mirror the renderer's deny-by-default public-file enumeration."""

    results: list[str] = []
    total_bytes = 0
    stack: list[tuple[Path, str]] = [(root, "")]
    is_junction = getattr(os.path, "isjunction", lambda _path: False)
    while stack:
        directory, relative_directory = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name.casefold())
        except OSError as exc:
            raise AuditError(
                "render-public-root-unreadable",
                f"{label} could not enumerate its public root.",
            ) from exc
        for entry in entries:
            relative = (
                f"{relative_directory}/{entry.name}"
                if relative_directory
                else entry.name
            ).replace("\\", "/")
            try:
                linked = entry.is_symlink() or bool(is_junction(entry.path))
                directory_entry = entry.is_dir(follow_symlinks=False)
                file_entry = entry.is_file(follow_symlinks=False)
            except OSError as exc:
                raise AuditError(
                    "render-public-root-unreadable",
                    f"{label} changed while it was enumerated.",
                ) from exc
            if linked:
                raise AuditError(
                    "render-public-root-linked-path",
                    f"{label} contains a symbolic link or junction at {relative}.",
                )
            if directory_entry:
                if public_snapshot_path_allowed(relative, directory=True):
                    stack.append((Path(entry.path), relative))
                continue
            if not file_entry or not public_snapshot_path_allowed(relative, directory=False):
                continue
            size = entry.stat(follow_symlinks=False).st_size
            if size > MAX_PUBLIC_BUILD_FILE_BYTES:
                raise AuditError(
                    "render-public-file-too-large",
                    f"{label} contains an oversized public file at {relative}.",
                )
            total_bytes += size
            results.append(relative)
            if len(results) > MAX_PUBLIC_BUILD_FILES or total_bytes > MAX_PUBLIC_BUILD_BYTES:
                raise AuditError(
                    "render-public-root-too-large",
                    f"{label} exceeds the bounded public-build verification limits.",
                )
    return sorted(results)


def validate_render_report(
    value: object,
    root: Path,
    public_root: Path,
    budget: EvidenceBudget,
    label: str,
) -> tuple[dict[str, object], Path, dict[str, dict[str, Any]]]:
    """Bind Batch captures to one renderer report and its frozen public build."""

    evidence, report_path, payload, _ = verify_file_ref(
        value,
        root,
        budget,
        label,
        require_non_empty=True,
    )
    try:
        report = require_object(json.loads(payload.decode("utf-8")), label)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError(
            "render-report-invalid",
            f"{label} is not valid UTF-8 JSON.",
        ) from exc
    if report.get("schema_version") != 3 or report.get("execution_ok") is not True:
        raise AuditError(
            "render-report-invalid",
            f"{label} must be a successful rendered-review schema 3 report.",
        )
    build = require_object(report.get("build"), f"{label}.build")
    build_id = require_string(build.get("id"), f"{label}.build.id", maximum=300)
    source_snapshot = require_object(
        report.get("source_snapshot"),
        f"{label}.source_snapshot",
    )
    manifest = require_object(
        source_snapshot.get("manifest"),
        f"{label}.source_snapshot.manifest",
    )
    if manifest.get("algorithm") != "sha256":
        raise AuditError(
            "render-report-invalid",
            f"{label}.source_snapshot.manifest must use SHA-256.",
        )
    raw_files = require_array(
        manifest.get("files"),
        f"{label}.source_snapshot.manifest.files",
    )
    if not raw_files or len(raw_files) > MAX_PUBLIC_BUILD_FILES:
        raise AuditError(
            "render-report-invalid",
            f"{label} has an empty or oversized public-build manifest.",
        )
    manifest_files: list[dict[str, object]] = []
    manifest_paths: set[str] = set()
    total_bytes = 0
    for index, raw_file in enumerate(raw_files):
        file_label = f"{label}.source_snapshot.manifest.files[{index}]"
        item = require_object(raw_file, file_label)
        reject_extra(item, {"path", "bytes", "sha256"}, file_label)
        relative = portable_path(item.get("path"), f"{file_label}.path")
        unique_or_error(
            portable_key(relative),
            manifest_paths,
            "render-manifest-duplicate-path",
            f"{file_label}.path",
        )
        if not public_snapshot_path_allowed(relative, directory=False):
            raise AuditError(
                "render-report-invalid",
                f"{file_label}.path is not eligible public-build content.",
            )
        byte_count = item.get("bytes")
        if (
            not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
            or byte_count > MAX_PUBLIC_BUILD_FILE_BYTES
        ):
            raise AuditError("render-report-invalid", f"{file_label}.bytes is invalid.")
        expected = require_string(item.get("sha256"), f"{file_label}.sha256", maximum=64)
        if SHA256_PATTERN.fullmatch(expected) is None:
            raise AuditError("render-report-invalid", f"{file_label}.sha256 is invalid.")
        public_file = project_path(public_root, relative, f"{file_label}.path")
        file_payload = stable_read(
            public_file,
            MAX_PUBLIC_BUILD_FILE_BYTES,
            f"{file_label}.path",
        )
        if len(file_payload) != byte_count or sha256(file_payload) != expected:
            raise AuditError(
                "render-build-drift",
                f"{file_label}.path no longer matches the rendered public build.",
            )
        total_bytes += byte_count
        if total_bytes > MAX_PUBLIC_BUILD_BYTES:
            raise AuditError(
                "render-public-root-too-large",
                f"{label} exceeds the public-build verification byte limit.",
            )
        manifest_files.append({"path": relative, "bytes": byte_count, "sha256": expected})
    declared_paths = [str(item["path"]) for item in manifest_files]
    actual_paths = enumerate_public_snapshot(public_root, label)
    if sorted(declared_paths) != actual_paths:
        raise AuditError(
            "render-build-drift",
            f"{label} public files no longer match the renderer manifest.",
        )
    manifest_sha = require_string(
        manifest.get("manifest_sha256"),
        f"{label}.source_snapshot.manifest.manifest_sha256",
        maximum=64,
    )
    if canonical_sha256(manifest_files) != manifest_sha:
        raise AuditError(
            "render-report-invalid",
            f"{label} has an invalid source manifest digest.",
        )
    if manifest.get("file_count") != len(manifest_files) or manifest.get("total_bytes") != total_bytes:
        raise AuditError(
            "render-report-invalid",
            f"{label} has inconsistent source manifest counts.",
        )
    raw_captures = require_array(report.get("captures"), f"{label}.captures")
    captures: dict[str, dict[str, Any]] = {}
    for index, raw_capture in enumerate(raw_captures):
        capture_label = f"{label}.captures[{index}]"
        capture = require_object(raw_capture, capture_label)
        identifier = require_string(capture.get("id"), f"{capture_label}.id", maximum=200)
        unique_or_error(
            identifier,
            set(captures),
            "render-report-duplicate-capture-id",
            f"{capture_label}.id",
        )
        captures[identifier] = capture
    return {
        "evidence": evidence,
        "build_id": build_id,
        "source_manifest_sha256": manifest_sha,
        "source_file_count": len(manifest_files),
        "source_total_bytes": total_bytes,
    }, report_path, captures


def normalized_route(value: object, label: str) -> tuple[str, str]:
    route = require_string(value, label, maximum=1000)
    if "\\" in route or any(ord(character) < 0x20 for character in route):
        raise AuditError("invalid-page-route", f"{label} is not a portable route path.")
    parsed = urlsplit(route)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise AuditError(
            "invalid-page-route",
            f"{label} must be a direct path without a host, query, or fragment.",
        )
    if not parsed.path.startswith("/") or parsed.path.startswith("//"):
        raise AuditError("invalid-page-route", f"{label} must start with one slash.")
    decoded = unicodedata.normalize("NFC", unquote(parsed.path))
    if any(character in "?#\\" or ord(character) < 0x20 for character in decoded):
        raise AuditError(
            "invalid-page-route",
            f"{label} decodes to a path containing a reserved or control character.",
        )
    segments = decoded.split("/")[1:]
    if any(segment in {".", ".."} for segment in segments):
        raise AuditError("invalid-page-route", f"{label} cannot contain dot segments.")
    if any(segment == "" for segment in segments[:-1]):
        raise AuditError("invalid-page-route", f"{label} contains an empty segment.")
    canonical = posixpath.normpath(decoded)
    if not canonical.startswith("/"):
        canonical = "/" + canonical
    if canonical != "/":
        canonical = canonical.rstrip("/")
    return route, canonical


def unique_or_error(value: str, observed: set[str], code: str, label: str) -> None:
    if value in observed:
        raise AuditError(code, f"{label} is duplicated: {value!r}.")
    observed.add(value)


def validate_viewports(study: dict[str, Any]) -> tuple[list[dict[str, object]], dict[str, dict[str, object]], list[dict[str, str]]]:
    raw = require_array(study.get("viewport_classes"), "study.viewport_classes")
    if len(raw) < 2:
        raise AuditError(
            "invalid-contract",
            "study.viewport_classes must declare at least wide and narrow roles.",
        )
    classes: list[dict[str, object]] = []
    by_id: dict[str, dict[str, object]] = {}
    viewport_ids: set[str] = set()
    role_counts = {"wide": 0, "narrow": 0}
    gaps: list[dict[str, str]] = []
    for index, raw_item in enumerate(raw):
        label = f"study.viewport_classes[{index}]"
        item = require_object(raw_item, label)
        reject_extra(item, {"id", "role", "width", "height", "basis", "required"}, label)
        identifier = require_id(item.get("id"), f"{label}.id")
        unique_or_error(identifier, viewport_ids, "duplicate-viewport-class", f"{label}.id")
        role = require_string(item.get("role"), f"{label}.role", maximum=20)
        if role not in {"wide", "narrow", "additional"}:
            raise AuditError("invalid-contract", f"{label}.role is unsupported.")
        if role in role_counts:
            role_counts[role] += 1
        required = require_bool(item.get("required"), f"{label}.required")
        if role in {"wide", "narrow"} and not required:
            raise AuditError(
                "invalid-contract",
                f"{label} is a core matched viewport and must be required.",
            )
        width = item.get("width")
        height = item.get("height")
        for dimension, value in (("width", width), ("height", height)):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 1
            ):
                raise AuditError(
                    "invalid-contract",
                    f"{label}.{dimension} must be a positive integer or null.",
                )
        if width is None or height is None:
            gaps.append({
                "code": "viewport-dimensions-unresolved",
                "scope": identifier,
                "message": "Replace the template viewport dimensions with project-derived capture dimensions.",
            })
        basis = require_string(item.get("basis"), f"{label}.basis", minimum=10)
        record = {
            "id": identifier,
            "role": role,
            "width": width,
            "height": height,
            "basis": basis,
            "required": required,
        }
        classes.append(record)
        by_id[identifier] = record
    if role_counts["wide"] != 1 or role_counts["narrow"] != 1:
        raise AuditError(
            "invalid-contract",
            "Declare exactly one wide role and one narrow role; additional classes use the additional role.",
        )
    return classes, by_id, gaps


def validate_review(
    value: object,
    root: Path,
    budget: EvidenceBudget,
    label: str,
    *,
    site_status: str,
    study_frozen_at: datetime,
    expected_capture_set_sha256: str,
) -> tuple[dict[str, object], list[dict[str, str]]]:
    review = require_object(value, label)
    reject_extra(
        review,
        {
            "status",
            "reviewer_id",
            "sibling_output_seen_before_observation",
            "diagnostic_material_seen_before_observation",
            "observed_at",
            "frozen_at",
            "capture_set_sha256",
            "evidence",
        },
        label,
    )
    status = require_string(review.get("status"), f"{label}.status", maximum=20)
    if status not in {"complete", "pending", "not-run"}:
        raise AuditError("invalid-contract", f"{label}.status is unsupported.")
    reviewer = review.get("reviewer_id")
    if reviewer is not None:
        reviewer = require_string(reviewer, f"{label}.reviewer_id", maximum=200)
    primed = review.get("diagnostic_material_seen_before_observation")
    if primed is not None:
        primed = require_bool(primed, f"{label}.diagnostic_material_seen_before_observation")
    sibling_seen = review.get("sibling_output_seen_before_observation")
    if sibling_seen is not None:
        sibling_seen = require_bool(
            sibling_seen,
            f"{label}.sibling_output_seen_before_observation",
        )
    observed_value = review.get("observed_at")
    observed_at = (
        None
        if observed_value is None
        else require_datetime(observed_value, f"{label}.observed_at")
    )
    frozen_value = review.get("frozen_at")
    frozen_at = (
        None
        if frozen_value is None
        else require_datetime(frozen_value, f"{label}.frozen_at")
    )
    capture_set_value = review.get("capture_set_sha256")
    capture_set_sha256 = (
        None
        if capture_set_value is None
        else require_string(
            capture_set_value,
            f"{label}.capture_set_sha256",
            maximum=64,
        )
    )
    if capture_set_sha256 is not None and SHA256_PATTERN.fullmatch(capture_set_sha256) is None:
        raise AuditError(
            "invalid-contract",
            f"{label}.capture_set_sha256 must be a lowercase SHA-256 digest.",
        )
    evidence_value = review.get("evidence")
    if site_status == "planned" and (
        status not in {"pending", "not-run"}
        or reviewer is not None
        or sibling_seen is not None
        or primed is not None
        or observed_at is not None
        or frozen_at is not None
        or capture_set_sha256 is not None
        or evidence_value is not None
    ):
        raise AuditError(
            "invalid-contract",
            f"{label} must be pending or not-run with null reviewer, exposure, times, capture binding, and evidence for a planned site.",
        )
    if site_status == "correctly_blocked" and (
        status != "not-run"
        or reviewer is not None
        or sibling_seen is not None
        or primed is not None
        or observed_at is not None
        or frozen_at is not None
        or capture_set_sha256 is not None
        or evidence_value is not None
    ):
        raise AuditError(
            "invalid-contract",
            f"{label} must be not-run with null reviewer, exposure, times, capture binding, and evidence for a correctly blocked case.",
        )
    evidence = None
    if evidence_value is not None:
        evidence, _, _, _ = verify_file_ref(
            evidence_value,
            root,
            budget,
            f"{label}.evidence",
            require_non_empty=True,
        )
    gaps: list[dict[str, str]] = []
    if site_status == "built":
        chronology_valid = False
        if observed_at is not None and frozen_at is not None:
            observed_instant = utc_datetime(observed_at)
            frozen_instant = utc_datetime(frozen_at)
            now_limit = datetime.now(timezone.utc) + timedelta(minutes=5)
            if observed_instant > now_limit or frozen_instant > now_limit:
                raise AuditError(
                    "site-review-in-future",
                    f"{label} contains a review time beyond the allowed clock tolerance.",
                )
            if observed_instant < study_frozen_at:
                raise AuditError(
                    "site-review-before-study-freeze",
                    f"{label}.observed_at precedes study.frozen_at.",
                )
            if frozen_instant < observed_instant:
                raise AuditError(
                    "site-review-chronology-invalid",
                    f"{label}.frozen_at precedes its observation time.",
                )
            chronology_valid = True
        if (
            status != "complete"
            or reviewer is None
            or sibling_seen is not False
            or primed is not False
            or not chronology_valid
            or capture_set_sha256 != expected_capture_set_sha256
            or evidence is None
        ):
            gaps.append({
                "code": "unprimed-review-incomplete",
                "scope": label,
                "message": "A built site needs a capture-bound, evidenced observation frozen before sibling output or diagnostic material was seen.",
            })
    return {
        "status": status,
        "reviewer_id": reviewer,
        "sibling_output_seen_before_observation": sibling_seen,
        "diagnostic_material_seen_before_observation": primed,
        "observed_at": observed_at,
        "frozen_at": frozen_at,
        "capture_set_sha256": capture_set_sha256,
        "evidence": evidence,
    }, gaps


def optional_string(
    value: object,
    label: str,
    *,
    minimum: int = 1,
    maximum: int = 4000,
) -> str | None:
    if value is None:
        return None
    return require_string(value, label, minimum=minimum, maximum=maximum)


def contextual_finding_is_material(finding: dict[str, object]) -> bool:
    """Return the declared materiality without inferring aesthetic quality.

    A finding becomes material when either the recorded severity is medium or
    stronger, or its declared user/release impact is material or
    release-blocking.  The test deliberately uses only the structured fields
    the reviewer supplied; it never derives a taste score from screenshots,
    prose, or repeated ingredients.
    """

    return (
        finding.get("severity") in {"medium", "high", "critical"}
        or finding.get("impact") in {"material", "release-blocking"}
    )


def validate_human_contextual_disposition(
    value: object,
    root: Path,
    budget: EvidenceBudget,
    *,
    expected_capture_set_sha256: str,
    study_frozen_at: datetime,
    whole_review_frozen_at: str | None,
    finding_records: list[dict[str, object]],
    reserved_evidence_paths: set[str],
    reserved_evidence_hashes: set[str],
) -> dict[str, object] | None:
    """Validate a separate capture-set-bound human decision record.

    Absence is intentionally not a malformed contract: older or still-planned
    studies need an honest pending state.  The readiness evaluator records
    that absence as a human-decision gap without changing mechanically
    verifiable protocol coverage.
    """

    if value is None:
        return None

    label = "human_contextual_disposition"
    record = require_object(value, label)
    reject_extra(
        record,
        {
            "status",
            "reviewer_id",
            "decided_at",
            "capture_set_sha256",
            "evidence",
            "rationale",
            "finding_ids",
        },
        label,
    )
    status = require_string(record.get("status"), f"{label}.status", maximum=40)
    if status not in HUMAN_CONTEXTUAL_DISPOSITION_STATUSES:
        raise AuditError("invalid-contract", f"{label}.status is unsupported.")

    reviewer = optional_string(record.get("reviewer_id"), f"{label}.reviewer_id", maximum=200)
    decided_value = record.get("decided_at")
    decided_at = (
        None
        if decided_value is None
        else require_datetime(decided_value, f"{label}.decided_at")
    )
    capture_value = record.get("capture_set_sha256")
    capture_set_sha256 = (
        None
        if capture_value is None
        else require_string(capture_value, f"{label}.capture_set_sha256", maximum=64)
    )
    if capture_set_sha256 is not None and SHA256_PATTERN.fullmatch(capture_set_sha256) is None:
        raise AuditError(
            "invalid-contract",
            f"{label}.capture_set_sha256 must be a lowercase SHA-256 digest.",
        )
    rationale = optional_string(record.get("rationale"), f"{label}.rationale", minimum=20)
    finding_ids_raw = require_array(record.get("finding_ids"), f"{label}.finding_ids")
    known_finding_ids = {str(finding["id"]) for finding in finding_records}
    finding_ids: list[str] = []
    for index, raw_id in enumerate(finding_ids_raw):
        finding_id = require_id(raw_id, f"{label}.finding_ids[{index}]")
        if finding_id not in known_finding_ids:
            raise AuditError(
                "unknown-human-disposition-finding",
                f"{label}.finding_ids[{index}] does not name a contextual finding.",
            )
        if finding_id in finding_ids:
            raise AuditError(
                "invalid-contract",
                f"{label}.finding_ids contains a duplicate.",
            )
        finding_ids.append(finding_id)

    evidence_value = record.get("evidence")
    if status == "pending":
        if (
            reviewer is not None
            or decided_at is not None
            or capture_set_sha256 is not None
            or evidence_value is not None
            or rationale is not None
            or finding_ids
        ):
            raise AuditError(
                "invalid-contract",
                f"{label} must keep reviewer, time, capture binding, evidence, rationale, and finding IDs null or empty while pending.",
            )
        return {
            "status": status,
            "reviewer_id": None,
            "decided_at": None,
            "capture_set_sha256": None,
            "evidence": None,
            "rationale": None,
            "finding_ids": [],
        }

    if (
        reviewer is None
        or decided_at is None
        or capture_set_sha256 is None
        or evidence_value is None
        or rationale is None
    ):
        raise AuditError(
            "invalid-contract",
            f"{label} requires reviewer, decided_at, capture_set_sha256, evidence, and rationale once decided.",
        )
    if capture_set_sha256 != expected_capture_set_sha256:
        raise AuditError(
            "human-disposition-capture-set-mismatch",
            f"{label}.capture_set_sha256 must bind the exact whole-study capture set.",
        )
    if whole_review_frozen_at is None:
        raise AuditError(
            "human-disposition-before-whole-review",
            f"{label} cannot be finalized before the whole-system review is frozen.",
        )
    decided_instant = utc_datetime(decided_at)
    whole_frozen_instant = utc_datetime(whole_review_frozen_at)
    now_limit = datetime.now(timezone.utc) + timedelta(minutes=5)
    if decided_instant > now_limit:
        raise AuditError(
            "human-disposition-in-future",
            f"{label}.decided_at is beyond the allowed clock tolerance.",
        )
    if decided_instant < study_frozen_at or decided_instant < whole_frozen_instant:
        raise AuditError(
            "human-disposition-chronology-invalid",
            f"{label}.decided_at must follow the study freeze and frozen whole-system observation.",
        )
    evidence, _, _, _ = verify_file_ref(
        evidence_value,
        root,
        budget,
        f"{label}.evidence",
        require_non_empty=True,
    )
    evidence_path = portable_key(str(evidence["path"]))
    evidence_sha256 = str(evidence["sha256"])
    if (
        evidence_path in reserved_evidence_paths
        or evidence_sha256 in reserved_evidence_hashes
    ):
        raise AuditError(
            "human-disposition-evidence-not-separate",
            f"{label}.evidence must be a distinct frozen decision artifact, not a capture, review, finding, brief, source packet, render report, or blocker artifact already in the study.",
        )
    if status in {"revisions-required", "accepted-contextual-risk"} and not finding_ids:
        raise AuditError(
            "invalid-contract",
            f"{label}.finding_ids must name the material finding(s) addressed by {status}.",
        )
    if status == "no-material-cluster-observed" and finding_ids:
        raise AuditError(
            "invalid-contract",
            f"{label}.finding_ids must be empty for no-material-cluster-observed.",
        )
    return {
        "status": status,
        "reviewer_id": reviewer,
        "decided_at": decided_at,
        "capture_set_sha256": capture_set_sha256,
        "evidence": evidence,
        "rationale": rationale,
        "finding_ids": finding_ids,
    }


def assess_human_contextual_readiness(
    disposition: dict[str, object] | None,
    finding_records: list[dict[str, object]],
) -> tuple[bool, list[dict[str, str]]]:
    """Separate declared human closure from protocol-coverage readiness."""

    gaps: list[dict[str, str]] = []
    material_findings = [
        finding for finding in finding_records if contextual_finding_is_material(finding)
    ]
    open_material = [
        finding for finding in material_findings if finding.get("disposition") == "open"
    ]
    accepted_material = [
        finding
        for finding in material_findings
        if finding.get("disposition") == "accepted-contextual-risk"
    ]
    unresolved_release_blocking = [
        finding
        for finding in material_findings
        if (
            finding.get("impact") == "release-blocking"
            and finding.get("disposition") != "resolved"
        )
    ]
    if disposition is None:
        gaps.append({
            "code": "human-contextual-disposition-missing",
            "scope": "study",
            "message": "Record a capture-set-bound human contextual disposition after the whole-system review is frozen.",
        })
        return False, gaps

    status = str(disposition["status"])
    if status == "pending":
        gaps.append({
            "code": "human-contextual-disposition-pending",
            "scope": "study",
            "message": "The Batch Study has no finalized capture-set-bound human contextual disposition yet.",
        })
        return False, gaps
    if status == "blocked":
        gaps.append({
            "code": "human-contextual-disposition-blocked",
            "scope": "study",
            "message": "The human contextual disposition is blocked; satisfy the recorded unblock condition before final readiness.",
        })
        return False, gaps
    if status == "revisions-required":
        gaps.append({
            "code": "human-contextual-revisions-required",
            "scope": "study",
            "message": "The human contextual disposition requires revisions and a refreshed capture-set-bound decision.",
        })
        return False, gaps

    if open_material:
        identifiers = ", ".join(str(finding["id"]) for finding in open_material)
        gaps.append({
            "code": "material-contextual-findings-open",
            "scope": "study",
            "message": f"Material contextual finding(s) remain open: {identifiers}.",
        })

    if unresolved_release_blocking:
        identifiers = ", ".join(
            str(finding["id"]) for finding in unresolved_release_blocking
        )
        gaps.append({
            "code": "release-blocking-contextual-findings-unresolved",
            "scope": "study",
            "message": f"Release-blocking contextual finding(s) cannot be closed as accepted risk: {identifiers}.",
        })

    accepted_ids = {str(finding["id"]) for finding in accepted_material}
    recorded_ids = set(disposition["finding_ids"])
    if status == "accepted-contextual-risk":
        if not accepted_ids:
            gaps.append({
                "code": "accepted-contextual-risk-without-finding",
                "scope": "study",
                "message": "accepted-contextual-risk requires at least one material finding with the same disposition.",
            })
        if recorded_ids != accepted_ids:
            gaps.append({
                "code": "accepted-contextual-risk-finding-mismatch",
                "scope": "study",
                "message": "The human accepted-risk record must name exactly the material findings accepted as contextual risk.",
            })
    elif status == "no-material-cluster-observed" and accepted_ids:
        gaps.append({
            "code": "no-material-disposition-conflicts-with-accepted-risk",
            "scope": "study",
            "message": "A no-material-cluster disposition cannot close a capture set that still records accepted material contextual risk.",
        })

    return not gaps, gaps


def batch_decision_status(
    *,
    comparison_ready: bool,
    human_contextual_ready: bool,
    disposition: dict[str, object] | None,
) -> str:
    """Name the current boundary without turning it into an aesthetic pass."""

    if comparison_ready and human_contextual_ready:
        return "final-human-contextual-disposition-recorded"
    if not comparison_ready:
        return "protocol-coverage-incomplete"
    if disposition is None:
        return "human-contextual-disposition-required"
    status = str(disposition["status"])
    if status == "pending":
        return "human-contextual-disposition-pending"
    if status in {"revisions-required", "blocked"}:
        return status
    return "human-contextual-disposition-incomplete"


def batch_readiness_fields(
    *,
    comparison_ready: bool,
    human_contextual_ready: bool,
    disposition: dict[str, object] | None,
) -> dict[str, object]:
    """Build the explicit protocol/human readiness boundary in one place."""

    return {
        "coverage_status": "complete" if comparison_ready else "incomplete",
        "comparison_ready": comparison_ready,
        "human_contextual_ready": human_contextual_ready,
        "final_ready": comparison_ready and human_contextual_ready,
        # This remains false even after a human disposition: the artifact can
        # bind a declared contextual decision, never manufacture an aesthetic
        # verdict from bytes or fields.
        "automatic_aesthetic_pass": False,
        "decision_status": batch_decision_status(
            comparison_ready=comparison_ready,
            human_contextual_ready=human_contextual_ready,
            disposition=disposition,
        ),
    }


def require_date(value: object, label: str) -> str:
    text = require_string(value, label, maximum=10)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise AuditError("invalid-contract", f"{label} is not an ISO date.") from exc
    return text


def validate_authorization(value: object, label: str) -> dict[str, object]:
    authorization = require_object(value, label)
    reject_extra(authorization, {"status", "basis"}, label)
    status = require_string(authorization.get("status"), f"{label}.status", maximum=20)
    if status not in {"pending", "authorized", "not-applicable"}:
        raise AuditError("invalid-contract", f"{label}.status is unsupported.")
    basis = optional_string(authorization.get("basis"), f"{label}.basis", minimum=20)
    if status == "pending" and basis is not None:
        raise AuditError("invalid-contract", f"{label}.basis must be null while pending.")
    if status != "pending" and basis is None:
        raise AuditError("invalid-contract", f"{label}.basis is required once decided.")
    return {"status": status, "basis": basis}


def validate_data_handling(value: object) -> dict[str, object]:
    label = "data_handling"
    record = require_object(value, label)
    reject_extra(
        record,
        {
            "status",
            "capture_authorization",
            "contact_sheet_authorization",
            "classification",
            "recipients",
            "access_scope",
            "retention",
            "transformations",
        },
        label,
    )
    status = require_string(record.get("status"), f"{label}.status", maximum=20)
    if status not in {"pending", "resolved"}:
        raise AuditError("invalid-contract", f"{label}.status is unsupported.")
    capture_authorization = validate_authorization(
        record.get("capture_authorization"),
        f"{label}.capture_authorization",
    )
    contact_sheet_authorization = validate_authorization(
        record.get("contact_sheet_authorization"),
        f"{label}.contact_sheet_authorization",
    )
    classification = require_string(
        record.get("classification"),
        f"{label}.classification",
        maximum=20,
    )
    if classification not in {"internal", "confidential", "public"}:
        raise AuditError("invalid-contract", f"{label}.classification is unsupported.")
    recipients_raw = require_array(record.get("recipients"), f"{label}.recipients")
    recipients: list[str] = []
    recipient_keys: set[str] = set()
    for index, raw_recipient in enumerate(recipients_raw):
        recipient = require_string(
            raw_recipient,
            f"{label}.recipients[{index}]",
            maximum=200,
        )
        unique_or_error(
            recipient.casefold(),
            recipient_keys,
            "duplicate-data-recipient",
            f"{label}.recipients[{index}]",
        )
        recipients.append(recipient)
    access_scope = optional_string(
        record.get("access_scope"),
        f"{label}.access_scope",
        minimum=20,
    )

    retention_raw = require_object(record.get("retention"), f"{label}.retention")
    reject_extra(
        retention_raw,
        {"mode", "owner", "delete_or_review_on", "reason"},
        f"{label}.retention",
    )
    retention_mode = require_string(
        retention_raw.get("mode"),
        f"{label}.retention.mode",
        maximum=20,
    )
    if retention_mode not in {"pending", "dated", "public", "not-applicable"}:
        raise AuditError("invalid-contract", f"{label}.retention.mode is unsupported.")
    retention_owner = optional_string(
        retention_raw.get("owner"),
        f"{label}.retention.owner",
        maximum=200,
    )
    retention_date_value = retention_raw.get("delete_or_review_on")
    retention_date = (
        None
        if retention_date_value is None
        else require_date(retention_date_value, f"{label}.retention.delete_or_review_on")
    )
    retention_reason = optional_string(
        retention_raw.get("reason"),
        f"{label}.retention.reason",
        minimum=20,
    )
    retention_expired = (
        retention_mode == "dated"
        and retention_date is not None
        and date.fromisoformat(retention_date) < date.today()
    )
    if retention_mode == "pending" and (
        retention_owner is not None
        or retention_date is not None
        or retention_reason is None
    ):
        raise AuditError(
            "invalid-contract",
            f"{label}.retention pending requires null owner/date and a reason.",
        )
    if retention_mode == "dated" and (
        retention_owner is None or retention_date is None
    ):
        raise AuditError(
            "invalid-contract",
            f"{label}.retention dated requires an owner and delete-or-review date.",
        )
    if retention_mode in {"public", "not-applicable"} and (
        retention_owner is not None
        or retention_date is not None
        or retention_reason is None
    ):
        raise AuditError(
            "invalid-contract",
            f"{label}.retention {retention_mode} requires null owner/date and a reason.",
        )

    transformations_raw = require_array(
        record.get("transformations"),
        f"{label}.transformations",
    )
    transformations: list[dict[str, str]] = []
    transformation_ids: set[str] = set()
    for index, raw_transformation in enumerate(transformations_raw):
        transformation_label = f"{label}.transformations[{index}]"
        transformation = require_object(raw_transformation, transformation_label)
        reject_extra(
            transformation,
            {"id", "kind", "scope", "description", "coverage_impact"},
            transformation_label,
        )
        identifier = require_id(
            transformation.get("id"),
            f"{transformation_label}.id",
        )
        unique_or_error(
            identifier,
            transformation_ids,
            "duplicate-data-transformation",
            f"{transformation_label}.id",
        )
        kind = require_string(
            transformation.get("kind"),
            f"{transformation_label}.kind",
            maximum=20,
        )
        if kind not in {"crop", "redaction", "exclusion"}:
            raise AuditError(
                "invalid-contract",
                f"{transformation_label}.kind is unsupported.",
            )
        transformations.append({
            "id": identifier,
            "kind": kind,
            "scope": require_string(
                transformation.get("scope"),
                f"{transformation_label}.scope",
                maximum=1000,
            ),
            "description": require_string(
                transformation.get("description"),
                f"{transformation_label}.description",
                minimum=20,
            ),
            "coverage_impact": require_string(
                transformation.get("coverage_impact"),
                f"{transformation_label}.coverage_impact",
                minimum=20,
            ),
        })

    if status == "resolved":
        if (
            capture_authorization["status"] == "pending"
            or contact_sheet_authorization["status"] == "pending"
            or access_scope is None
            or retention_mode == "pending"
        ):
            raise AuditError(
                "invalid-contract",
                "Resolved data_handling cannot contain pending authorization, access, or retention fields.",
            )
        if classification != "public" and not recipients:
            raise AuditError(
                "invalid-contract",
                "Resolved non-public data_handling must name at least one recipient.",
            )
    return {
        "status": status,
        "capture_authorization": capture_authorization,
        "contact_sheet_authorization": contact_sheet_authorization,
        "classification": classification,
        "recipients": recipients,
        "access_scope": access_scope,
        "retention": {
            "mode": retention_mode,
            "owner": retention_owner,
            "delete_or_review_on": retention_date,
            "reason": retention_reason,
            "expired": retention_expired,
        },
        "transformations": transformations,
    }


def validate_implementation_isolation(
    value: object,
    root: Path,
    budget: EvidenceBudget,
    label: str,
    *,
    site_status: str,
    study_frozen_at: datetime,
) -> tuple[dict[str, object], list[dict[str, str]]]:
    record = require_object(value, label)
    reject_extra(
        record,
        {
            "status",
            "source_packet",
            "producer_context_id",
            "sibling_output_exposure",
            "allowed_shared_tooling",
            "shared_artifacts_or_exceptions",
            "attested_by",
            "attested_at",
        },
        label,
    )
    status = require_string(record.get("status"), f"{label}.status", maximum=20)
    if status not in {"pending", "attested"}:
        raise AuditError("invalid-contract", f"{label}.status is unsupported.")
    source_packet, _, _, _ = verify_file_ref(
        record.get("source_packet"),
        root,
        budget,
        f"{label}.source_packet",
    )
    producer_context_id = require_string(
        record.get("producer_context_id"),
        f"{label}.producer_context_id",
        minimum=8,
        maximum=200,
    )

    exposure_raw = require_object(
        record.get("sibling_output_exposure"),
        f"{label}.sibling_output_exposure",
    )
    reject_extra(
        exposure_raw,
        {"state", "timing", "details"},
        f"{label}.sibling_output_exposure",
    )
    exposure_state = require_string(
        exposure_raw.get("state"),
        f"{label}.sibling_output_exposure.state",
        maximum=20,
    )
    exposure_timing = require_string(
        exposure_raw.get("timing"),
        f"{label}.sibling_output_exposure.timing",
        maximum=40,
    )
    allowed_exposure = {
        "not-started": {"not-applicable"},
        "not-exposed": {"through-unprimed-review"},
        "exposed": {"before-unprimed-review", "after-unprimed-review", "mixed"},
        "unknown": {"unknown"},
    }
    if (
        exposure_state not in allowed_exposure
        or exposure_timing not in allowed_exposure[exposure_state]
    ):
        raise AuditError(
            "invalid-contract",
            f"{label}.sibling_output_exposure has an incompatible state and timing.",
        )
    exposure_details = require_string(
        exposure_raw.get("details"),
        f"{label}.sibling_output_exposure.details",
        minimum=20,
    )

    tooling_records: list[dict[str, str]] = []
    tooling_names: set[str] = set()
    for index, raw_tool in enumerate(
        require_array(record.get("allowed_shared_tooling"), f"{label}.allowed_shared_tooling")
    ):
        tool_label = f"{label}.allowed_shared_tooling[{index}]"
        tool = require_object(raw_tool, tool_label)
        reject_extra(tool, {"name", "purpose", "constraint"}, tool_label)
        name = require_string(tool.get("name"), f"{tool_label}.name", maximum=200)
        unique_or_error(
            name.casefold(),
            tooling_names,
            "duplicate-shared-tooling",
            f"{tool_label}.name",
        )
        tooling_records.append({
            "name": name,
            "purpose": require_string(
                tool.get("purpose"),
                f"{tool_label}.purpose",
                minimum=20,
            ),
            "constraint": require_string(
                tool.get("constraint"),
                f"{tool_label}.constraint",
                minimum=20,
            ),
        })

    exception_records: list[dict[str, str]] = []
    exception_names: set[str] = set()
    for index, raw_exception in enumerate(
        require_array(
            record.get("shared_artifacts_or_exceptions"),
            f"{label}.shared_artifacts_or_exceptions",
        )
    ):
        exception_label = f"{label}.shared_artifacts_or_exceptions[{index}]"
        exception = require_object(raw_exception, exception_label)
        reject_extra(
            exception,
            {"name", "basis", "isolation_impact"},
            exception_label,
        )
        name = require_string(
            exception.get("name"),
            f"{exception_label}.name",
            maximum=200,
        )
        unique_or_error(
            name.casefold(),
            exception_names,
            "duplicate-shared-exception",
            f"{exception_label}.name",
        )
        exception_records.append({
            "name": name,
            "basis": require_string(
                exception.get("basis"),
                f"{exception_label}.basis",
                minimum=20,
            ),
            "isolation_impact": require_string(
                exception.get("isolation_impact"),
                f"{exception_label}.isolation_impact",
                minimum=20,
            ),
        })

    attested_by = optional_string(
        record.get("attested_by"),
        f"{label}.attested_by",
        maximum=200,
    )
    attested_at_value = record.get("attested_at")
    attested_at = (
        None
        if attested_at_value is None
        else require_datetime(attested_at_value, f"{label}.attested_at")
    )
    if status == "pending" and (attested_by is not None or attested_at is not None):
        raise AuditError(
            "invalid-contract",
            f"{label} pending requires null attester and attestation time.",
        )
    if status == "attested" and (
        attested_by is None
        or attested_at is None
        or exposure_state == "not-started"
        or "replace-with" in producer_context_id.casefold()
    ):
        raise AuditError(
            "invalid-contract",
            f"{label} attested requires a real context ID, attester, time, and observed exposure state.",
        )
    if attested_at is not None:
        attested_instant = utc_datetime(attested_at)
        if attested_instant > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise AuditError(
                "isolation-attestation-in-future",
                f"{label}.attested_at is beyond the allowed clock tolerance.",
            )
        if attested_instant < study_frozen_at:
            raise AuditError(
                "isolation-attestation-before-freeze",
                f"{label}.attested_at precedes study.frozen_at.",
            )

    gaps: list[dict[str, str]] = []
    if site_status == "built" and status != "attested":
        gaps.append({
            "code": "implementation-isolation-pending",
            "scope": label,
            "message": "A built case needs a completed implementation-isolation attestation before comparison.",
        })
    if site_status == "built" and status == "attested" and (
        exposure_state == "unknown"
        or exposure_timing in {"before-unprimed-review", "mixed"}
    ):
        gaps.append({
            "code": "implementation-isolation-compromised",
            "scope": label,
            "message": "Sibling-output exposure was unknown or occurred before the unprimed observation; record the limitation and resolve the study design before comparison.",
        })
    return {
        "status": status,
        "source_packet": source_packet,
        "producer_context_id": producer_context_id,
        "sibling_output_exposure": {
            "state": exposure_state,
            "timing": exposure_timing,
            "details": exposure_details,
        },
        "allowed_shared_tooling": tooling_records,
        "shared_artifacts_or_exceptions": exception_records,
        "attested_by": attested_by,
        "attested_at": attested_at,
    }, gaps


def independence_basis_is_boilerplate(value: str, site_id: str) -> bool:
    folded = unicodedata.normalize("NFKC", value).casefold()
    if any(marker in folded for marker in ("replace with", "explain why", "todo", "tbd")):
        return True
    letters = [character for character in folded if character.isalpha()]
    latin_letters = [
        character
        for character in letters
        if "LATIN" in unicodedata.name(character, "")
    ]
    if letters and len(latin_letters) / len(letters) < 0.8:
        # Semantic substance in non-Latin or materially mixed-script prose is a
        # human-review question; an English stopword/count gate cannot judge it.
        return False
    identifier_tokens = set(re.findall(r"[^\W_]+", site_id.casefold()))
    ignored = {
        "a", "an", "and", "are", "as", "be", "because", "brief", "case",
        "different", "from", "independent", "independently", "is", "it",
        "of", "other", "separate", "site", "study", "the", "this", "to",
        "was", "were",
    }
    meaningful = {
        token
        for token in re.findall(r"[^\W_]+", folded)
        if token not in ignored and token not in identifier_tokens
    }
    return len(meaningful) < 6


def roots_overlap(left: str, right: str) -> bool:
    left_parts = tuple(part.casefold() for part in PurePosixPath(left).parts)
    right_parts = tuple(part.casefold() for part in PurePosixPath(right).parts)
    minimum = min(len(left_parts), len(right_parts))
    return left_parts[:minimum] == right_parts[:minimum]


def validate_contract(
    contract: dict[str, Any],
    root: Path,
    budget: EvidenceBudget,
    *,
    atlas_requested: bool,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    reject_extra(
        contract,
        {
            "schema_version",
            "classification",
            "study",
            "data_handling",
            "sites",
            "whole_system_review",
            "contextual_findings",
            "human_contextual_disposition",
        },
        "contract",
    )
    if contract.get("schema_version") != SCHEMA_VERSION:
        raise AuditError(
            "unsupported-schema-version",
            f"schema_version must equal {SCHEMA_VERSION}.",
        )
    classification = require_string(contract.get("classification"), "classification", maximum=20)
    if classification not in {"internal", "confidential"}:
        raise AuditError("invalid-contract", "classification must be internal or confidential.")

    study = require_object(contract.get("study"), "study")
    reject_extra(study, {"id", "title", "frozen_at", "viewport_classes", "review_protocol"}, "study")
    study_id = require_id(study.get("id"), "study.id")
    study_title = require_string(study.get("title"), "study.title", maximum=300)
    frozen_at = require_datetime(study.get("frozen_at"), "study.frozen_at")
    frozen_instant = utc_datetime(frozen_at)
    if frozen_instant > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise AuditError(
            "study-freeze-in-future",
            "study.frozen_at is beyond the allowed clock tolerance.",
        )
    viewport_classes, viewport_by_id, gaps = validate_viewports(study)
    protocol = require_object(study.get("review_protocol"), "study.review_protocol")
    reject_extra(
        protocol,
        {"site_observation", "whole_system_comparison", "automatic_aesthetic_pass"},
        "study.review_protocol",
    )
    if protocol.get("site_observation") != "unprimed-before-diagnostics":
        raise AuditError("invalid-contract", "site_observation must preserve the unprimed protocol.")
    if protocol.get("whole_system_comparison") != "masked":
        raise AuditError("invalid-contract", "whole_system_comparison must be masked.")
    if protocol.get("automatic_aesthetic_pass") is not False:
        raise AuditError("invalid-contract", "automatic_aesthetic_pass must remain false.")
    data_handling = validate_data_handling(contract.get("data_handling"))

    sites_raw = require_array(contract.get("sites"), "sites")
    if len(sites_raw) < 3:
        raise AuditError("too-few-study-sites", "A Batch Study requires at least three sites.")
    site_ids: set[str] = set()
    site_masks: set[str] = set()
    brief_paths: set[str] = set()
    brief_hashes: set[str] = set()
    source_packet_paths: set[str] = set()
    producer_context_ids: set[str] = set()
    public_roots: set[str] = set()
    render_report_paths: set[str] = set()
    render_report_hashes: set[str] = set()
    render_capture_ids: set[str] = set()
    capture_paths: set[str] = set()
    review_paths: set[str] = set()
    review_hashes: set[str] = set()
    # A contextual disposition is a new human decision record.  It may cite
    # the frozen capture-set digest, but its evidence bytes must not be any
    # previously-declared study artifact.  Keeping a single registry lets the
    # final check reject a screenshot, review, finding attachment, brief,
    # source packet, render report, or blocker file being relabelled as that
    # decision.
    disposition_reserved_paths: set[str] = set()
    disposition_reserved_hashes: set[str] = set()

    def reserve_disposition_evidence(evidence: dict[str, object]) -> None:
        disposition_reserved_paths.add(portable_key(str(evidence["path"])))
        disposition_reserved_hashes.add(str(evidence["sha256"]))
    build_roots: list[str] = []
    route_index: dict[str, set[str]] = {}
    built_sites: list[dict[str, object]] = []
    planned_sites: list[dict[str, object]] = []
    blocked_sites: list[dict[str, object]] = []
    # Capture bytes are validated in place and then released.  When an atlas is
    # requested, retain only immutable identity/path metadata; make_atlas()
    # re-reads, re-hashes, and decodes one capture at a time.  This avoids a
    # study-sized in-memory byte cache while preserving exact-byte binding.
    atlas_inputs: list[dict[str, object]] = []
    required_viewports = {
        identifier
        for identifier, record in viewport_by_id.items()
        if record["required"] is True
    }

    for site_index, raw_site in enumerate(sites_raw):
        label = f"sites[{site_index}]"
        site = require_object(raw_site, label)
        reject_extra(
            site,
            {
                "id",
                "mask_label",
                "status",
                "independence_basis",
                "brief",
                "implementation_isolation",
                "build_root",
                "public_root",
                "render_report",
                "pages",
                "unprimed_review",
                "blocker",
            },
            label,
        )
        site_id = require_id(site.get("id"), f"{label}.id")
        unique_or_error(site_id, site_ids, "duplicate-site-id", f"{label}.id")
        mask_label = require_string(site.get("mask_label"), f"{label}.mask_label", maximum=100)
        unique_or_error(mask_label.casefold(), site_masks, "duplicate-mask-label", f"{label}.mask_label")
        status = require_string(site.get("status"), f"{label}.status", maximum=24)
        if status not in {"planned", "built", "correctly_blocked"}:
            raise AuditError("invalid-contract", f"{label}.status is unsupported.")
        independence_basis = require_string(
            site.get("independence_basis"),
            f"{label}.independence_basis",
            minimum=40,
        )
        if independence_basis_is_boilerplate(independence_basis, site_id):
            raise AuditError(
                "independence-basis-boilerplate",
                f"{label}.independence_basis must explain substantive contextual differences, not only assert independence or repeat IDs.",
            )
        brief, _, _, _ = verify_file_ref(site.get("brief"), root, budget, f"{label}.brief")
        reserve_disposition_evidence(brief)
        unique_or_error(portable_key(str(brief["path"])), brief_paths, "duplicate-brief-path", f"{label}.brief.path")
        unique_or_error(str(brief["sha256"]), brief_hashes, "duplicate-brief-bytes", f"{label}.brief.sha256")
        implementation_isolation, isolation_gaps = validate_implementation_isolation(
            site.get("implementation_isolation"),
            root,
            budget,
            f"{label}.implementation_isolation",
            site_status=status,
            study_frozen_at=frozen_instant,
        )
        reserve_disposition_evidence(
            require_object(
                implementation_isolation["source_packet"],
                f"{label}.implementation_isolation.source_packet",
            )
        )
        unique_or_error(
            portable_key(str(implementation_isolation["source_packet"]["path"])),
            source_packet_paths,
            "duplicate-source-packet-path",
            f"{label}.implementation_isolation.source_packet.path",
        )
        unique_or_error(
            str(implementation_isolation["producer_context_id"]).casefold(),
            producer_context_ids,
            "duplicate-producer-context-id",
            f"{label}.implementation_isolation.producer_context_id",
        )
        for gap in isolation_gaps:
            gap["scope"] = site_id
        gaps.extend(isolation_gaps)

        build_root_value = site.get("build_root")
        build_root = None
        build_path = None
        if build_root_value is not None:
            build_root = portable_path(build_root_value, f"{label}.build_root")
            if status == "built":
                build_path = project_path(root, build_root, f"{label}.build_root")
                if not build_path.is_dir() or build_path.is_symlink():
                    raise AuditError("build-root-missing", f"{label}.build_root is not an ordinary directory.")
            if any(roots_overlap(build_root, other) for other in build_roots):
                raise AuditError(
                    "build-roots-overlap",
                    f"{label}.build_root is the same as or nested with another build root.",
                )
            build_roots.append(build_root)

        public_root_value = site.get("public_root")
        render_report_value = site.get("render_report")
        public_root = None
        public_path = None
        render_report = None
        render_report_path = None
        render_captures: dict[str, dict[str, Any]] = {}
        if status == "built":
            if build_root is None or build_path is None:
                raise AuditError("build-root-missing", f"{label}.build_root is required for a built site.")
            public_root = portable_path(public_root_value, f"{label}.public_root")
            public_parts = tuple(PurePosixPath(public_root).parts)
            build_parts = tuple(PurePosixPath(build_root).parts)
            if public_parts[: len(build_parts)] != build_parts:
                raise AuditError(
                    "render-public-root-outside-build",
                    f"{label}.public_root must be the build root or one of its descendants.",
                )
            unique_or_error(
                portable_key(public_root),
                public_roots,
                "duplicate-public-root",
                f"{label}.public_root",
            )
            public_path = project_path(root, public_root, f"{label}.public_root")
            if not public_path.is_dir() or public_path.is_symlink():
                raise AuditError(
                    "render-public-root-missing",
                    f"{label}.public_root is not an ordinary directory.",
                )
            render_report, render_report_path, render_captures = validate_render_report(
                render_report_value,
                root,
                public_path,
                budget,
                f"{label}.render_report",
            )
            render_evidence = require_object(
                render_report["evidence"],
                f"{label}.render_report.evidence",
            )
            reserve_disposition_evidence(render_evidence)
            unique_or_error(
                portable_key(str(render_evidence["path"])),
                render_report_paths,
                "duplicate-render-report-path",
                f"{label}.render_report.path",
            )
            unique_or_error(
                str(render_evidence["sha256"]),
                render_report_hashes,
                "duplicate-render-report-bytes",
                f"{label}.render_report.sha256",
            )
        elif public_root_value is not None or render_report_value is not None:
            raise AuditError(
                "invalid-contract",
                f"{label}.public_root and render_report must be null until the site is built.",
            )

        page_ids: set[str] = set()
        page_masks: set[str] = set()
        routes: set[str] = set()
        page_records: list[dict[str, object]] = []
        pages = require_array(site.get("pages"), f"{label}.pages")
        if not pages:
            raise AuditError("invalid-contract", f"{label}.pages must not be empty.")
        for page_index, raw_page in enumerate(pages):
            page_label = f"{label}.pages[{page_index}]"
            page = require_object(raw_page, page_label)
            reject_extra(page, {"id", "mask_label", "route", "captures"}, page_label)
            page_id = require_id(page.get("id"), f"{page_label}.id")
            unique_or_error(page_id, page_ids, "duplicate-page-id", f"{page_label}.id")
            page_mask = require_string(page.get("mask_label"), f"{page_label}.mask_label", maximum=100)
            unique_or_error(page_mask.casefold(), page_masks, "duplicate-page-mask-label", f"{page_label}.mask_label")
            route, route_key = normalized_route(page.get("route"), f"{page_label}.route")
            unique_or_error(route_key, routes, "duplicate-page-route", f"{page_label}.route")
            captures_raw = require_array(page.get("captures"), f"{page_label}.captures")
            if status in {"planned", "correctly_blocked"} and captures_raw:
                lifecycle = "planned" if status == "planned" else "blocked"
                raise AuditError(
                    f"{lifecycle}-case-has-captures",
                    f"{page_label}.captures must be empty so {lifecycle} cases are not counted as built evidence.",
                )
            capture_classes: set[str] = set()
            capture_records: list[dict[str, object]] = []
            for capture_index, raw_capture in enumerate(captures_raw):
                capture_label = f"{page_label}.captures[{capture_index}]"
                capture = require_object(raw_capture, capture_label)
                reject_extra(
                    capture,
                    {
                        "viewport_class",
                        "capture_mode",
                        "render_capture_id",
                        "render_scenario_id",
                        "render_profile_id",
                        "path",
                        "sha256",
                    },
                    capture_label,
                )
                viewport_class = require_id(capture.get("viewport_class"), f"{capture_label}.viewport_class")
                if viewport_class not in viewport_by_id:
                    raise AuditError(
                        "undeclared-viewport-class",
                        f"{capture_label}.viewport_class is not declared by the study.",
                    )
                unique_or_error(
                    viewport_class,
                    capture_classes,
                    "duplicate-page-viewport-capture",
                    f"{capture_label}.viewport_class",
                )
                evidence, capture_path, capture_payload, media = verify_file_ref(
                    {"path": capture.get("path"), "sha256": capture.get("sha256")},
                    root,
                    budget,
                    capture_label,
                    capture=True,
                )
                reserve_disposition_evidence(evidence)
                unique_or_error(
                    portable_key(str(evidence["path"])),
                    capture_paths,
                    "duplicate-capture-path",
                    f"{capture_label}.path",
                )
                assert media is not None
                capture_mode = require_string(
                    capture.get("capture_mode"),
                    f"{capture_label}.capture_mode",
                    maximum=20,
                )
                if capture_mode not in {"viewport", "full-page"}:
                    raise AuditError(
                        "invalid-contract",
                        f"{capture_label}.capture_mode must be viewport or full-page.",
                    )
                render_capture_id = require_string(
                    capture.get("render_capture_id"),
                    f"{capture_label}.render_capture_id",
                    maximum=200,
                )
                render_scenario_id = require_id(
                    capture.get("render_scenario_id"),
                    f"{capture_label}.render_scenario_id",
                )
                render_profile_id = require_id(
                    capture.get("render_profile_id"),
                    f"{capture_label}.render_profile_id",
                )
                unique_or_error(
                    f"{site_id}:{render_capture_id}",
                    render_capture_ids,
                    "duplicate-render-capture-binding",
                    f"{capture_label}.render_capture_id",
                )
                rendered = render_captures.get(render_capture_id)
                if rendered is None:
                    raise AuditError(
                        "render-capture-missing",
                        f"{capture_label} is not present in the bound render report.",
                    )
                if (
                    rendered.get("capture_status") != "complete"
                    or rendered.get("scenario_id") != render_scenario_id
                    or rendered.get("profile_id") != render_profile_id
                    or rendered.get("route_label") != route
                    or not isinstance(rendered.get("http_status"), int)
                    or not 200 <= rendered["http_status"] < 300
                ):
                    raise AuditError(
                        "render-capture-binding-mismatch",
                        f"{capture_label} does not match its completed route/scenario/profile render record.",
                    )
                for url_field in ("requested_url", "final_url"):
                    rendered_url = require_string(
                        rendered.get(url_field),
                        f"{capture_label}.{url_field}",
                        maximum=2000,
                    )
                    rendered_path = urlsplit(rendered_url).path or "/"
                    _, rendered_route_key = normalized_route(
                        rendered_path,
                        f"{capture_label}.{url_field}",
                    )
                    if rendered_route_key != route_key:
                        raise AuditError(
                            "render-capture-route-mismatch",
                            f"{capture_label} was rendered from another route.",
                        )
                rendered_viewport = require_object(
                    rendered.get("viewport"),
                    f"{capture_label}.rendered_viewport",
                )
                expected_viewport = viewport_by_id[viewport_class]
                expected_width = expected_viewport["width"]
                expected_height = expected_viewport["height"]
                if expected_width is None or expected_height is None:
                    raise AuditError(
                        "capture-viewport-dimensions-unresolved",
                        f"{capture_label} cannot be verified until {viewport_class} has concrete dimensions.",
                    )
                if (
                    rendered_viewport.get("width") != expected_width
                    or rendered_viewport.get("height") != expected_height
                ):
                    raise AuditError(
                        "render-capture-viewport-mismatch",
                        f"{capture_label} renderer viewport does not match {viewport_class}.",
                    )
                device_scale_factor = rendered_viewport.get("device_scale_factor")
                if (
                    not isinstance(device_scale_factor, (int, float))
                    or isinstance(device_scale_factor, bool)
                    or not math.isfinite(device_scale_factor)
                    or device_scale_factor <= 0
                    or device_scale_factor > 4
                ):
                    raise AuditError(
                        "render-report-invalid",
                        f"{capture_label} has an invalid device scale factor.",
                    )
                rendered_screenshot = require_object(
                    rendered.get("screenshot"),
                    f"{capture_label}.screenshot",
                )
                screenshot_relative = portable_path(
                    rendered_screenshot.get("path"),
                    f"{capture_label}.screenshot.path",
                )
                assert render_report_path is not None
                screenshot_path = project_path(
                    render_report_path.parent,
                    screenshot_relative,
                    f"{capture_label}.screenshot.path",
                )
                if screenshot_path.resolve(strict=False) != capture_path.resolve(strict=False):
                    raise AuditError(
                        "render-capture-path-mismatch",
                        f"{capture_label} path is not the renderer's screenshot artifact.",
                    )
                if (
                    rendered_screenshot.get("sha256") != evidence["sha256"]
                    or rendered_screenshot.get("pixel_width") != media["width"]
                    or rendered_screenshot.get("pixel_height") != media["height"]
                ):
                    raise AuditError(
                        "render-capture-binding-mismatch",
                        f"{capture_label} bytes or pixel dimensions do not match the renderer record.",
                    )
                expected_pixel_width = round(expected_width * device_scale_factor)
                expected_pixel_height = round(expected_height * device_scale_factor)
                if (
                        media["width"] != expected_pixel_width
                        or (
                            capture_mode == "viewport"
                            and media["height"] != expected_pixel_height
                        )
                        or (
                            capture_mode == "full-page"
                            and media["height"] < expected_pixel_height
                        )
                ):
                    raise AuditError(
                        "capture-dimensions-mismatch",
                        f"{capture_label} decodes to {media['width']}x{media['height']} but its "
                        f"{capture_mode} profile requires width {expected_pixel_width} and "
                        f"{'height ' + str(expected_pixel_height) if capture_mode == 'viewport' else 'height at least ' + str(expected_pixel_height)}.",
                    )
                capture_record = {
                    "viewport_class": viewport_class,
                    "capture_mode": capture_mode,
                    "render_capture_id": render_capture_id,
                    "render_scenario_id": render_scenario_id,
                    "render_profile_id": render_profile_id,
                    "media_type": media["media_type"],
                    "width": media["width"],
                    "height": media["height"],
                    "evidence": evidence,
                }
                capture_records.append(capture_record)
                if atlas_requested:
                    if len(atlas_inputs) >= MAX_ATLAS_IMAGES:
                        raise AuditError(
                            "atlas-image-limit-exceeded",
                            f"Atlas input exceeds {MAX_ATLAS_IMAGES} verified captures.",
                        )
                    atlas_inputs.append({
                        "site_mask": mask_label,
                        "page_mask": page_mask,
                        "viewport_class": viewport_class,
                        "capture_mode": capture_mode,
                        "source": capture_path,
                        "path": evidence["path"],
                        "sha256": evidence["sha256"],
                        "media_type": media["media_type"],
                        "width": media["width"],
                        "height": media["height"],
                    })
                # Do not retain a study-wide capture byte cache.  The local
                # payload falls out of scope after this iteration.
                del capture_payload
            missing = sorted(required_viewports - capture_classes)
            if status == "planned":
                page_status = "planned"
            elif status == "correctly_blocked":
                page_status = "correctly-blocked"
            else:
                page_status = "matched" if not missing else "incomplete"
            if status == "built" and missing:
                gaps.append({
                    "code": "required-capture-missing",
                    "scope": f"{site_id}:{route}",
                    "message": "Missing required viewport classes: " + ", ".join(missing) + ".",
                })
            page_records.append({
                "id": page_id,
                "mask_label": page_mask,
                "route": route,
                "normalized_route": route_key,
                "status": page_status,
                "captures": capture_records,
                "missing_required_viewports": missing,
            })
        route_index[site_id] = routes

        site_capture_set_sha256 = canonical_sha256([
            {
                "page_id": page["id"],
                "route": page["normalized_route"],
                "captures": [
                    {
                        "viewport_class": capture["viewport_class"],
                        "capture_mode": capture["capture_mode"],
                        "render_capture_id": capture["render_capture_id"],
                        "render_scenario_id": capture["render_scenario_id"],
                        "render_profile_id": capture["render_profile_id"],
                        "path": capture["evidence"]["path"],
                        "sha256": capture["evidence"]["sha256"],
                    }
                    for capture in page["captures"]
                ],
            }
            for page in page_records
        ])

        review, review_gaps = validate_review(
            site.get("unprimed_review"),
            root,
            budget,
            f"{label}.unprimed_review",
            site_status=status,
            study_frozen_at=frozen_instant,
            expected_capture_set_sha256=site_capture_set_sha256,
        )
        for gap in review_gaps:
            gap["scope"] = site_id
        gaps.extend(review_gaps)
        if status == "built" and review["evidence"] is not None:
            review_evidence = require_object(
                review["evidence"],
                f"{label}.unprimed_review.evidence",
            )
            reserve_disposition_evidence(review_evidence)
            unique_or_error(
                portable_key(str(review_evidence["path"])),
                review_paths,
                "duplicate-review-evidence-path",
                f"{label}.unprimed_review.evidence.path",
            )
            unique_or_error(
                str(review_evidence["sha256"]),
                review_hashes,
                "duplicate-review-evidence-bytes",
                f"{label}.unprimed_review.evidence.sha256",
            )

        if status == "built":
            if build_root is None:
                raise AuditError("build-root-missing", f"{label}.build_root is required for a built site.")
            if site.get("blocker") is not None:
                raise AuditError("invalid-contract", f"{label}.blocker must be null for a built site.")
            built_sites.append({
                "id": site_id,
                "mask_label": mask_label,
                "independence_basis": independence_basis,
                "brief": brief,
                "implementation_isolation": implementation_isolation,
                "build_root": build_root,
                "public_root": public_root,
                "render_report": render_report,
                "capture_set_sha256": site_capture_set_sha256,
                "pages": page_records,
                "unprimed_review": review,
            })
        elif status == "planned":
            if build_root is None:
                raise AuditError(
                    "build-root-missing",
                    f"{label}.build_root must declare the isolated future root for a planned site.",
                )
            if site.get("blocker") is not None:
                raise AuditError(
                    "invalid-contract",
                    f"{label}.blocker must be null for a planned site.",
                )
            planned_sites.append({
                "id": site_id,
                "mask_label": mask_label,
                "status": "planned",
                "independence_basis": independence_basis,
                "brief": brief,
                "implementation_isolation": implementation_isolation,
                "build_root": build_root,
                "public_root": None,
                "render_report": None,
                "capture_set_sha256": site_capture_set_sha256,
                "pages": page_records,
                "unprimed_review": review,
            })
            gaps.append({
                "code": "site-planned",
                "scope": site_id,
                "message": "This frozen case is planned; build it, capture every required viewport class, and complete its unprimed review before comparison.",
            })
        else:
            if build_root is not None:
                raise AuditError(
                    "invalid-contract",
                    f"{label}.build_root must be null for a correctly blocked case.",
                )
            blocker = require_object(site.get("blocker"), f"{label}.blocker")
            reject_extra(blocker, {"code", "summary", "unblock_condition", "evidence"}, f"{label}.blocker")
            blocker_code = require_id(blocker.get("code"), f"{label}.blocker.code")
            blocker_summary = require_string(blocker.get("summary"), f"{label}.blocker.summary", minimum=20)
            unblock = require_string(blocker.get("unblock_condition"), f"{label}.blocker.unblock_condition", minimum=20)
            blocker_evidence_raw = require_array(blocker.get("evidence"), f"{label}.blocker.evidence")
            if not blocker_evidence_raw:
                raise AuditError("invalid-contract", f"{label}.blocker.evidence must not be empty.")
            blocker_evidence = [
                verify_file_ref(item, root, budget, f"{label}.blocker.evidence[{index}]")[0]
                for index, item in enumerate(blocker_evidence_raw)
            ]
            for evidence in blocker_evidence:
                reserve_disposition_evidence(evidence)
            blocked_sites.append({
                "id": site_id,
                "mask_label": mask_label,
                "independence_basis": independence_basis,
                "brief": brief,
                "implementation_isolation": implementation_isolation,
                "public_root": None,
                "render_report": None,
                "capture_set_sha256": site_capture_set_sha256,
                "pages": page_records,
                "unprimed_review": review,
                "blocker": {
                    "code": blocker_code,
                    "summary": blocker_summary,
                    "unblock_condition": unblock,
                    "evidence": blocker_evidence,
                    "classification": "declared-correctly-blocked",
                },
            })

    if len(built_sites) < 3:
        gaps.append({
            "code": "fewer-than-three-built-sites",
            "scope": "study",
            "message": "At least three built sites are required for a whole-system Batch Study comparison.",
        })
    if built_sites and data_handling["status"] != "resolved":
        gaps.append({
            "code": "data-handling-unresolved",
            "scope": "study",
            "message": "Built captures require resolved authorization, access, retention, and transformation handling before comparison.",
        })
    elif (
        built_sites
        and data_handling["capture_authorization"]["status"] != "authorized"
    ):
        gaps.append({
            "code": "capture-authorization-unresolved",
            "scope": "study",
            "message": "Built capture evidence requires an explicit authorized capture basis before comparison.",
        })
    if built_sites and data_handling["retention"]["expired"] is True:
        gaps.append({
            "code": "retention-review-expired",
            "scope": "study",
            "message": "The dated retention review has passed; delete the evidence or record a new accountable review date before comparison or contact-sheet creation.",
        })

    whole_capture_set_sha256 = canonical_sha256([
        {
            "site_id": site["id"],
            "capture_set_sha256": site["capture_set_sha256"],
        }
        for site in built_sites
    ])
    site_review_freezes = [
        utc_datetime(str(site["unprimed_review"]["frozen_at"]))
        for site in built_sites
        if site["unprimed_review"]["frozen_at"] is not None
    ]

    whole = require_object(contract.get("whole_system_review"), "whole_system_review")
    reject_extra(
        whole,
        {
            "status",
            "masked",
            "reviewer_id",
            "site_identity_revealed_before_observation",
            "diagnostic_material_seen_before_observation",
            "observed_at",
            "frozen_at",
            "capture_set_sha256",
            "evidence",
        },
        "whole_system_review",
    )
    whole_status = require_string(whole.get("status"), "whole_system_review.status", maximum=20)
    if whole_status not in {"complete", "pending", "not-run"}:
        raise AuditError("invalid-contract", "whole_system_review.status is unsupported.")
    masked = require_bool(whole.get("masked"), "whole_system_review.masked")
    identity_revealed = require_bool(
        whole.get("site_identity_revealed_before_observation"),
        "whole_system_review.site_identity_revealed_before_observation",
    )
    whole_primed = require_bool(
        whole.get("diagnostic_material_seen_before_observation"),
        "whole_system_review.diagnostic_material_seen_before_observation",
    )
    whole_reviewer = whole.get("reviewer_id")
    if whole_reviewer is not None:
        whole_reviewer = require_string(whole_reviewer, "whole_system_review.reviewer_id", maximum=200)
    whole_observed_value = whole.get("observed_at")
    whole_observed_at = (
        None
        if whole_observed_value is None
        else require_datetime(whole_observed_value, "whole_system_review.observed_at")
    )
    whole_frozen_value = whole.get("frozen_at")
    whole_frozen_at = (
        None
        if whole_frozen_value is None
        else require_datetime(whole_frozen_value, "whole_system_review.frozen_at")
    )
    whole_capture_value = whole.get("capture_set_sha256")
    whole_capture_sha256 = (
        None
        if whole_capture_value is None
        else require_string(
            whole_capture_value,
            "whole_system_review.capture_set_sha256",
            maximum=64,
        )
    )
    if whole_capture_sha256 is not None and SHA256_PATTERN.fullmatch(whole_capture_sha256) is None:
        raise AuditError(
            "invalid-contract",
            "whole_system_review.capture_set_sha256 must be a lowercase SHA-256 digest.",
        )
    whole_chronology_valid = False
    if whole_observed_at is not None and whole_frozen_at is not None:
        whole_observed_instant = utc_datetime(whole_observed_at)
        whole_frozen_instant = utc_datetime(whole_frozen_at)
        now_limit = datetime.now(timezone.utc) + timedelta(minutes=5)
        if whole_observed_instant > now_limit or whole_frozen_instant > now_limit:
            raise AuditError(
                "whole-review-in-future",
                "whole_system_review contains a review time beyond the allowed clock tolerance.",
            )
        if whole_observed_instant < frozen_instant:
            raise AuditError(
                "whole-review-before-study-freeze",
                "whole_system_review.observed_at precedes study.frozen_at.",
            )
        if whole_frozen_instant < whole_observed_instant:
            raise AuditError(
                "whole-review-chronology-invalid",
                "whole_system_review.frozen_at precedes its observation time.",
            )
        if site_review_freezes and whole_observed_instant < max(site_review_freezes):
            raise AuditError(
                "whole-review-before-site-reviews-frozen",
                "whole_system_review began before every built site's unprimed review was frozen.",
            )
        whole_chronology_valid = True
    whole_evidence = None
    if whole.get("evidence") is not None:
        whole_evidence, _, _, _ = verify_file_ref(
            whole.get("evidence"),
            root,
            budget,
            "whole_system_review.evidence",
            require_non_empty=True,
        )
        reserve_disposition_evidence(whole_evidence)
        unique_or_error(
            portable_key(str(whole_evidence["path"])),
            review_paths,
            "duplicate-review-evidence-path",
            "whole_system_review.evidence.path",
        )
        unique_or_error(
            str(whole_evidence["sha256"]),
            review_hashes,
            "duplicate-review-evidence-bytes",
            "whole_system_review.evidence.sha256",
        )
    if (
        whole_status != "complete"
        or masked is not True
        or identity_revealed is not False
        or whole_primed is not False
        or whole_reviewer is None
        or not whole_chronology_valid
        or whole_capture_sha256 != whole_capture_set_sha256
        or whole_evidence is None
    ):
        gaps.append({
            "code": "masked-whole-system-review-incomplete",
            "scope": "study",
            "message": "Complete a non-empty neutral-label comparison observation before site identities or diagnostic material are revealed.",
        })
    whole_record = {
        "status": whole_status,
        "masked": masked,
        "reviewer_id": whole_reviewer,
        "site_identity_revealed_before_observation": identity_revealed,
        "diagnostic_material_seen_before_observation": whole_primed,
        "observed_at": whole_observed_at,
        "frozen_at": whole_frozen_at,
        "capture_set_sha256": whole_capture_sha256,
        "evidence": whole_evidence,
    }

    findings_raw = require_array(contract.get("contextual_findings"), "contextual_findings")
    finding_ids: set[str] = set()
    finding_records: list[dict[str, object]] = []
    for finding_index, raw_finding in enumerate(findings_raw):
        label = f"contextual_findings[{finding_index}]"
        finding = require_object(raw_finding, label)
        reject_extra(
            finding,
            {
                "id",
                "site_ids",
                "routes",
                "context",
                "observation",
                "evidence",
                "severity",
                "impact",
                "disposition",
            },
            label,
        )
        finding_id = require_id(finding.get("id"), f"{label}.id")
        unique_or_error(finding_id, finding_ids, "duplicate-finding-id", f"{label}.id")
        scoped_sites_raw = require_array(finding.get("site_ids"), f"{label}.site_ids")
        if not scoped_sites_raw:
            raise AuditError(
                "context-free-finding",
                f"{label}.site_ids must name at least one study site.",
            )
        scoped_sites: list[str] = []
        for index, raw_site_id in enumerate(scoped_sites_raw):
            scoped_site = require_id(raw_site_id, f"{label}.site_ids[{index}]")
            if scoped_site not in site_ids:
                raise AuditError("unknown-finding-site", f"{label} names an unknown site.")
            if scoped_site in scoped_sites:
                raise AuditError("invalid-contract", f"{label}.site_ids contains a duplicate.")
            scoped_sites.append(scoped_site)
        route_records: list[dict[str, str]] = []
        for index, raw_route_ref in enumerate(require_array(finding.get("routes"), f"{label}.routes")):
            route_label = f"{label}.routes[{index}]"
            route_ref = require_object(raw_route_ref, route_label)
            reject_extra(route_ref, {"site_id", "route"}, route_label)
            route_site = require_id(route_ref.get("site_id"), f"{route_label}.site_id")
            if route_site not in scoped_sites:
                raise AuditError(
                    "context-free-finding",
                    f"{route_label}.site_id must also appear in the finding's site_ids.",
                )
            route, route_key = normalized_route(route_ref.get("route"), f"{route_label}.route")
            if route_key not in route_index[route_site]:
                raise AuditError("unknown-finding-route", f"{route_label} names an undeclared page route.")
            route_records.append({"site_id": route_site, "route": route})
        context = require_string(finding.get("context"), f"{label}.context", minimum=20)
        observation = require_string(finding.get("observation"), f"{label}.observation", minimum=20)
        evidence_raw = require_array(finding.get("evidence"), f"{label}.evidence")
        if not evidence_raw:
            raise AuditError("context-free-finding", f"{label}.evidence must not be empty.")
        evidence = [
            verify_file_ref(item, root, budget, f"{label}.evidence[{index}]")[0]
            for index, item in enumerate(evidence_raw)
        ]
        for evidence_ref in evidence:
            reserve_disposition_evidence(evidence_ref)
        severity = require_string(finding.get("severity"), f"{label}.severity", maximum=20)
        if severity not in CONTEXTUAL_FINDING_SEVERITIES:
            raise AuditError("invalid-contract", f"{label}.severity is unsupported.")
        impact = require_string(finding.get("impact"), f"{label}.impact", maximum=30)
        if impact not in CONTEXTUAL_FINDING_IMPACTS:
            raise AuditError("invalid-contract", f"{label}.impact is unsupported.")
        disposition = require_string(finding.get("disposition"), f"{label}.disposition", maximum=40)
        if disposition not in {"open", "resolved", "accepted-contextual-risk"}:
            raise AuditError("invalid-contract", f"{label}.disposition is unsupported.")
        finding_records.append({
            "id": finding_id,
            "site_ids": scoped_sites,
            "routes": route_records,
            "context": context,
            "observation": observation,
            "evidence": evidence,
            "severity": severity,
            "impact": impact,
            "disposition": disposition,
        })

    comparison_ready = not gaps
    human_disposition = validate_human_contextual_disposition(
        contract.get("human_contextual_disposition"),
        root,
        budget,
        expected_capture_set_sha256=whole_capture_set_sha256,
        study_frozen_at=frozen_instant,
        whole_review_frozen_at=whole_frozen_at,
        finding_records=finding_records,
        reserved_evidence_paths=disposition_reserved_paths,
        reserved_evidence_hashes=disposition_reserved_hashes,
    )
    human_contextual_ready, human_contextual_gaps = assess_human_contextual_readiness(
        human_disposition,
        finding_records,
    )
    readiness = batch_readiness_fields(
        comparison_ready=comparison_ready,
        human_contextual_ready=human_contextual_ready,
        disposition=human_disposition,
    )
    result = {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": "batch_range_audit.py", "version": TOOL_VERSION},
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "classification": classification,
        "study": {"id": study_id, "title": study_title, "frozen_at": frozen_at},
        "capture_set_sha256": whole_capture_set_sha256,
        "viewport_classes": viewport_classes,
        "data_handling": data_handling,
        **readiness,
        "summary": {
            "declared_site_count": len(sites_raw),
            "planned_site_count": len(planned_sites),
            "built_site_count": len(built_sites),
            "correctly_blocked_site_count": len(blocked_sites),
            "built_page_count": sum(len(site["pages"]) for site in built_sites),
            "verified_capture_count": sum(
                len(page["captures"])
                for site in built_sites
                for page in site["pages"]
            ),
            "contextual_finding_count": len(finding_records),
            "material_contextual_finding_count": sum(
                1 for finding in finding_records if contextual_finding_is_material(finding)
            ),
            "open_material_contextual_finding_count": sum(
                1
                for finding in finding_records
                if contextual_finding_is_material(finding)
                and finding["disposition"] == "open"
            ),
        },
        "built_sites": built_sites,
        "planned_sites": planned_sites,
        "correctly_blocked": blocked_sites,
        "whole_system_review": whole_record,
        "contextual_findings": finding_records,
        "human_contextual_disposition": human_disposition,
        "gaps": gaps,
        "human_contextual_gaps": human_contextual_gaps,
        "limitations": [
            "Hash and coverage verification cannot prove that briefs are substantively unrelated.",
            "Evidence hashes prove frozen bytes, not that the stated review protocol was honestly followed.",
            "Non-empty distinct review files prove separable bytes exist, not that their observations are substantive or independently authored.",
            "Implementation-isolation attestations are inspectable human evidence; unique files, hashes, or context IDs do not automatically prove independent production.",
            "Renderer-report, route, viewport, screenshot, and public-manifest bindings prove which frozen build bytes produced each declared capture; they do not prove the page was representative of every possible runtime state.",
            "Neutral labels reduce identity priming but cannot conceal subject matter visible inside a capture.",
            "The optional atlas copies verified screenshot pixels without redacting names, logos, copy, people, URLs, media, or private state.",
            "Recorded crop, redaction, and exclusion transformations are declarations with coverage impact; this auditor does not inspect pixels or verify that redaction occurred.",
            "The tool does not detect AI use, score authorship, or approve aesthetic quality.",
            "Contextual findings require human interpretation before changing the skill or a site.",
            "A capture-set-bound human disposition records a declared decision and evidence; it does not authenticate reviewer identity or prove substantive judgment.",
        ],
    }
    return result, atlas_inputs


def atomic_write(path: Path, payload: bytes) -> None:
    """Replace one output through an exclusive random same-directory file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def make_atlas(
    target: Path,
    target_relative: str,
    inputs: list[dict[str, object]],
) -> dict[str, object]:
    if len(inputs) > MAX_ATLAS_IMAGES:
        raise AuditError(
            "atlas-image-limit-exceeded",
            f"Atlas input exceeds {MAX_ATLAS_IMAGES} verified captures.",
        )
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError
    except ImportError:
        return {
            "requested": True,
            "status": "pillow-unavailable",
            "path": None,
            "sha256": None,
            "width": None,
            "height": None,
            "image_count": 0,
        }
    if not inputs:
        return {
            "requested": True,
            "status": "no-built-captures",
            "path": None,
            "sha256": None,
            "width": None,
            "height": None,
            "image_count": 0,
        }
    if target.suffix.casefold() != ".png":
        raise AuditError("invalid-atlas-path", "The atlas output path must end in .png.")

    cell_width = 520
    image_height = 320
    label_height = 44
    padding = 18
    columns = min(3, len(inputs))
    rows = (len(inputs) + columns - 1) // columns
    width = padding + columns * (cell_width + padding)
    height = padding + rows * (image_height + label_height + padding)
    canvas = Image.new("RGB", (width, height), "#f4f1ea")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    resampling = getattr(Image, "Resampling", Image).LANCZOS
    for index, metadata in enumerate(inputs):
        column = index % columns
        row = index // columns
        x = padding + column * (cell_width + padding)
        y = padding + row * (image_height + label_height + padding)
        source = metadata["source"]
        assert isinstance(source, Path)
        payload = stable_read(
            source,
            MAX_EVIDENCE_BYTES,
            f"atlas capture {metadata['path']}",
        )
        if sha256(payload) != metadata["sha256"]:
            raise AuditError(
                "capture-changed-before-atlas",
                f"Capture {metadata['path']} changed after contract verification.",
            )
        media = validate_capture_media(
            source,
            payload,
            f"atlas capture {metadata['path']}",
        )
        if any(
            media[key] != metadata[key]
            for key in ("media_type", "width", "height")
        ):
            raise AuditError(
                "capture-changed-before-atlas",
                f"Capture {metadata['path']} no longer matches its verified media identity.",
            )
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(payload)) as opened:
                    opened.verify()
                with Image.open(io.BytesIO(payload)) as opened:
                    image = ImageOps.exif_transpose(opened).convert("RGB")
                    image.thumbnail((cell_width, image_height), resampling)
                    image_copy = image.copy()
        except (
            OSError,
            UnidentifiedImageError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as exc:
            raise AuditError("atlas-image-unreadable", "Pillow could not decode a verified capture.") from exc
        tile_x = x + (cell_width - image_copy.width) // 2
        tile_y = y + (image_height - image_copy.height) // 2
        canvas.paste(image_copy, (tile_x, tile_y))
        label = (
            f"{metadata['site_mask']} | {metadata['page_mask']} | "
            f"{metadata['viewport_class']} | {metadata['capture_mode']}"
        )
        draw.text((x, y + image_height + 12), label, fill="#181818", font=font)
    encoded = io.BytesIO()
    canvas.save(encoded, format="PNG", optimize=True)
    atlas_payload = encoded.getvalue()
    if len(atlas_payload) > MAX_EVIDENCE_BYTES:
        raise AuditError("atlas-image-too-large", "The encoded atlas exceeds the evidence-file limit.")
    atomic_write(target, atlas_payload)
    payload = stable_read(target, MAX_EVIDENCE_BYTES, "atlas output")
    return {
        "requested": True,
        "status": "created",
        "path": target_relative,
        "sha256": sha256(payload),
        "width": width,
        "height": height,
        "image_count": len(inputs),
    }


def write_json(path: Path, value: dict[str, object]) -> bytes:
    payload = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if len(payload) > MAX_REPORT_BYTES:
        raise AuditError("report-too-large", f"The audit report exceeds {MAX_REPORT_BYTES} bytes.")
    atomic_write(path, payload)
    return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify a project-local Batch Study record. Coverage is reported; "
            "aesthetic approval always remains human and contextual."
        )
    )
    parser.add_argument("project_root", help="Project root containing the batch evidence")
    parser.add_argument("--contract", default=DEFAULT_CONTRACT, help="Project-relative contract path")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Project-relative report path")
    parser.add_argument(
        "--atlas",
        help=(
            "Optional project-relative neutral-label PNG atlas path; screenshot "
            "pixels are copied without redaction"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        root = Path(args.project_root).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise AuditError("project-root-invalid", "The project root is not a directory.")
        contract_relative = portable_path(args.contract, "--contract")
        output_relative = portable_path(args.output, "--output")
        if portable_key(contract_relative) == portable_key(output_relative):
            raise AuditError("output-conflict", "The report cannot overwrite the contract.")
        atlas_relative = None
        if args.atlas is not None:
            atlas_relative = portable_path(args.atlas, "--atlas")
            if portable_key(atlas_relative) in {
                portable_key(contract_relative),
                portable_key(output_relative),
            }:
                raise AuditError("output-conflict", "The atlas path conflicts with another audit artifact.")
        contract_path = project_path(root, contract_relative, "--contract")
        raw = stable_read(contract_path, MAX_CONTRACT_BYTES, "Batch Study contract")
        try:
            contract = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuditError("contract-json-invalid", "The contract is not valid UTF-8 JSON.") from exc
        budget = EvidenceBudget()
        report, atlas_inputs = validate_contract(
            require_object(contract, "contract"),
            root,
            budget,
            atlas_requested=atlas_relative is not None,
        )
        if portable_key(output_relative) in budget.paths:
            raise AuditError(
                "output-conflict",
                "The report path conflicts with a declared evidence file.",
            )
        if atlas_relative is not None and portable_key(atlas_relative) in budget.paths:
            raise AuditError(
                "output-conflict",
                "The atlas path conflicts with a declared evidence file.",
            )
        report["contract"] = {
            "path": contract_relative,
            "sha256": sha256(raw),
            "bytes": len(raw),
            "verified": True,
        }
        if atlas_relative is None:
            report["atlas"] = {
                "requested": False,
                "status": "not-requested",
                "path": None,
                "sha256": None,
                "width": None,
                "height": None,
                "image_count": 0,
            }
        elif (
            report["data_handling"]["status"] != "resolved"
            or report["data_handling"]["contact_sheet_authorization"]["status"]
            != "authorized"
            or report["data_handling"]["retention"]["expired"] is True
        ):
            if report["data_handling"]["retention"]["expired"] is True:
                gap = {
                    "code": "contact-sheet-retention-expired",
                    "scope": "study",
                    "message": "The requested contact sheet was not created because the dated retention review has expired.",
                }
            else:
                gap = {
                    "code": "contact-sheet-authorization-unresolved",
                    "scope": "study",
                    "message": "The requested contact sheet was not created because its authorization and data-handling record are unresolved.",
                }
            if gap["code"] not in {item["code"] for item in report["gaps"]}:
                report["gaps"].append(gap)
            report.update(batch_readiness_fields(
                comparison_ready=False,
                human_contextual_ready=bool(report["human_contextual_ready"]),
                disposition=report["human_contextual_disposition"],
            ))
            report["atlas"] = {
                "requested": True,
                "status": "authorization-unavailable",
                "path": None,
                "sha256": None,
                "width": None,
                "height": None,
                "image_count": 0,
            }
        else:
            atlas_path = project_path(root, atlas_relative, "--atlas")
            report["atlas"] = make_atlas(atlas_path, atlas_relative, atlas_inputs)
        report["resource_usage"] = {
            "evidence_files_verified": budget.files,
            "evidence_bytes_verified": budget.bytes,
            "limits": {
                "contract_bytes": MAX_CONTRACT_BYTES,
                "evidence_file_bytes": MAX_EVIDENCE_BYTES,
                "evidence_total_bytes": MAX_TOTAL_EVIDENCE_BYTES,
                "report_bytes": MAX_REPORT_BYTES,
                "atlas_images": MAX_ATLAS_IMAGES,
            },
        }
        output_path = project_path(root, output_relative, "--output")
        payload = write_json(output_path, report)
        summary = {
            "execution_ok": True,
            "coverage_status": report["coverage_status"],
            "comparison_ready": report["comparison_ready"],
            "human_contextual_ready": report["human_contextual_ready"],
            "final_ready": report["final_ready"],
            "automatic_aesthetic_pass": False,
            "decision_status": report["decision_status"],
            "report": {
                "path": output_relative,
                "sha256": sha256(payload),
                "bytes": len(payload),
            },
        }
        print(json.dumps(summary, separators=(",", ":")))
        # A process may inspect comparison coverage separately in the emitted
        # JSON, but a successful command must never be mistaken for completed
        # Batch readiness while the required human contextual disposition is
        # absent, blocked, or contradicted by an open release boundary.
        return 0 if report["final_ready"] else 1
    except (AuditError, FileNotFoundError, OSError) as exc:
        if isinstance(exc, AuditError):
            code = exc.code
            message = exc.message
        elif isinstance(exc, FileNotFoundError):
            code = "project-root-invalid"
            message = "The project root does not exist."
        else:
            code = "filesystem-error"
            message = str(exc)
        failure = {
            "execution_ok": False,
            "comparison_ready": False,
            "human_contextual_ready": False,
            "final_ready": False,
            "automatic_aesthetic_pass": False,
            "decision_status": "audit-execution-failed",
            "error": {"code": code, "message": message},
        }
        print(json.dumps(failure, separators=(",", ":")), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
