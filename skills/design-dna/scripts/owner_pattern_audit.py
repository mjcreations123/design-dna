#!/usr/bin/env python3
"""Audit an active owner-scoped visual default-failure contract.

The contract names failed relationships, not forbidden ingredients. A project
review must control every named failure before broad implementation and bind
wide plus narrow rendered evidence showing every failure absent before release.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import struct
import sys
import tempfile
import zlib
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import NoReturn


MINIMUM_PYTHON = (3, 10)
if sys.version_info < MINIMUM_PYTHON:  # pragma: no cover - old interpreter only
    print(
        json.dumps({
            "ok": False,
            "error": {
                "code": "python-version-unsupported",
                "message": "owner_pattern_audit.py requires Python 3.10 or newer.",
            },
        }),
        file=sys.stderr,
    )
    raise SystemExit(2)


SCHEMA_VERSION = 1
ARTIFACT_TYPE = "design-dna-owner-pattern-review-audit"
REVIEW_ARTIFACT_TYPE = "design-dna-owner-pattern-review"
REVIEW_RELATIVE_PATH = PurePosixPath(".design-dna/owner-pattern-review.json")
CANONICAL_CONTRACT_RELATIVE_PATH = PurePosixPath(
    ".design-dna/owner-pattern-contract.json"
)
CONTRACT_ENV = "DESIGN_DNA_OWNER_PATTERN_CONTRACT"
ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,79}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DATE_TIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[Tt]\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2}))?$"
)
PLACEHOLDER_PATTERN = re.compile(
    r"(?:__REPLACE|\bTBD\b|\bTODO\b|\bplaceholder\b)", re.I
)
CONTRACT_KEYS = {
    "schema_version",
    "contract_id",
    "status",
    "owner",
    "scope",
    "authority",
    "semantics",
    "signals",
    "release_policy",
}
REVIEW_KEYS = {
    "schema_version",
    "artifact_type",
    "created_with",
    "status",
    "contract_binding",
    "project",
    "direction",
    "final",
}


class AuditError(RuntimeError):
    """A stable execution or contract error."""

    def __init__(self, code: str, message: str, *, path: Path | None = None):
        super().__init__(message)
        self.code = code
        self.path = path


def error_payload(error: AuditError) -> dict[str, object]:
    payload: dict[str, object] = {
        "code": error.code,
        "message": str(error),
    }
    if error.path is not None:
        payload["path"] = str(error.path)
    return payload


def fail(error: AuditError) -> NoReturn:
    print(json.dumps({"ok": False, "error": error_payload(error)}), file=sys.stderr)
    raise SystemExit(2)


def is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def strict_json(raw: bytes, *, path: Path) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise AuditError(
                    "duplicate-json-key",
                    f"Duplicate JSON key: {key}",
                    path=path,
                )
            result[key] = value
        return result

    try:
        text = raw.decode("utf-8")
        return json.loads(text, object_pairs_hook=reject_duplicates)
    except UnicodeError as exc:
        raise AuditError(
            "invalid-utf8",
            "The JSON file must be UTF-8.",
            path=path,
        ) from exc
    except json.JSONDecodeError as exc:
        raise AuditError(
            "invalid-json",
            f"Invalid JSON: {exc}",
            path=path,
        ) from exc


def read_ordinary_bytes(path: Path, *, label: str) -> bytes:
    if not path.is_file() or is_reparse(path):
        raise AuditError(
            f"{label}-missing-or-redirected",
            f"{label.replace('-', ' ').title()} must be an ordinary file.",
            path=path,
        )
    try:
        return path.read_bytes()
    except OSError as exc:
        raise AuditError(
            f"{label}-read-failed",
            str(exc),
            path=path,
        ) from exc


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def useful_text(value: object, *, minimum: int = 8) -> bool:
    return (
        isinstance(value, str)
        and len(value.strip()) >= minimum
        and PLACEHOLDER_PATTERN.search(value) is None
    )


def exact_keys(value: object, expected: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == expected


def valid_iso_date_or_datetime(value: object) -> bool:
    if not isinstance(value, str) or DATE_TIME_PATTERN.fullmatch(value) is None:
        return False
    try:
        if len(value) == 10:
            date.fromisoformat(value)
        else:
            datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_contract(payload: object, *, path: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []

    def add(code: str, message: str) -> None:
        findings.append({"code": code, "message": message, "path": str(path)})

    if not isinstance(payload, dict):
        add("contract-not-object", "The owner pattern contract must be a JSON object.")
        return findings
    if set(payload) != CONTRACT_KEYS:
        add(
            "contract-key-mismatch",
            "The owner pattern contract has missing or unsupported top-level keys.",
        )
    if payload.get("schema_version") != SCHEMA_VERSION:
        add("contract-schema-version", "Unsupported owner pattern contract schema.")
    if ID_PATTERN.fullmatch(str(payload.get("contract_id", ""))) is None:
        add("contract-id", "contract_id must be a portable lowercase identifier.")
    if payload.get("status") != "active":
        add("contract-inactive", "The selected owner pattern contract is not active.")

    owner = payload.get("owner")
    if not exact_keys(owner, {"id", "display_name"}):
        add("contract-owner-shape", "owner must contain only id and display_name.")
    elif (
        ID_PATTERN.fullmatch(str(owner.get("id", ""))) is None
        or not useful_text(owner.get("display_name"), minimum=2)
    ):
        add("contract-owner", "The accountable owner identity is incomplete.")
    if not useful_text(payload.get("scope"), minimum=12):
        add("contract-scope", "The owner contract scope must be explicit.")

    authority = payload.get("authority")
    authority_keys = {
        "adopted_at",
        "source_kind",
        "source_url",
        "source_author",
        "owner_instruction",
    }
    if not exact_keys(authority, authority_keys):
        add("contract-authority-shape", "authority has missing or unsupported fields.")
    else:
        adopted_at = authority.get("adopted_at")
        if not valid_iso_date_or_datetime(adopted_at):
            add("contract-authority-date", "authority.adopted_at must be an ISO date or datetime.")
        for field in ("source_kind", "source_author", "owner_instruction"):
            if not useful_text(authority.get(field), minimum=8):
                add("contract-authority-text", f"authority.{field} is incomplete.")
        source_url = authority.get("source_url")
        if not isinstance(source_url, str) or not source_url.startswith("https://"):
            add("contract-authority-url", "authority.source_url must be an HTTPS URL.")

    semantics = payload.get("semantics")
    if not exact_keys(
        semantics,
        {"unit", "authorship_boundary", "ingredient_boundary"},
    ):
        add("contract-semantics-shape", "semantics has missing or unsupported fields.")
    elif semantics.get("unit") != "failed-relationship":
        add(
            "contract-semantics-unit",
            "The contract must define failed relationships, not ingredient names.",
        )
    elif not all(useful_text(semantics.get(field), minimum=12) for field in (
        "authorship_boundary", "ingredient_boundary"
    )):
        add("contract-semantics-text", "The contract boundaries are incomplete.")

    signals = payload.get("signals")
    signal_keys = {
        "id",
        "label",
        "failure_definition",
        "direction_requirement",
        "final_requirement",
    }
    if not isinstance(signals, list) or not 1 <= len(signals) <= 64:
        add("contract-signals", "signals must contain between 1 and 64 items.")
    else:
        observed_ids: list[str] = []
        for index, signal in enumerate(signals):
            if not exact_keys(signal, signal_keys):
                add(
                    "contract-signal-shape",
                    f"signals[{index}] has missing or unsupported fields.",
                )
                continue
            signal_id = signal.get("id")
            if not isinstance(signal_id, str) or ID_PATTERN.fullmatch(signal_id) is None:
                add("contract-signal-id", f"signals[{index}].id is invalid.")
            else:
                observed_ids.append(signal_id)
            for field in signal_keys - {"id"}:
                if not useful_text(signal.get(field), minimum=12):
                    add(
                        "contract-signal-text",
                        f"signals[{index}].{field} is incomplete.",
                    )
        if len(observed_ids) != len(set(observed_ids)):
            add("contract-signal-duplicate", "Signal IDs must be unique.")

    policy = payload.get("release_policy")
    policy_keys = {
        "direction_disposition",
        "final_disposition",
        "require_wide_and_narrow_rendered_evidence",
        "wide_min_css_width",
        "narrow_max_css_width",
        "unresolved_blocks",
        "exception_model",
        "required_capture_mode",
    }
    if not exact_keys(policy, policy_keys):
        add("contract-policy-shape", "release_policy has missing or unsupported fields.")
    else:
        if policy.get("direction_disposition") != "controlled":
            add("contract-direction-policy", "direction_disposition must be controlled.")
        if policy.get("final_disposition") != "absent":
            add("contract-final-policy", "final_disposition must be absent.")
        if policy.get("require_wide_and_narrow_rendered_evidence") is not True:
            add("contract-render-policy", "Wide and narrow rendered evidence must be required.")
        if policy.get("unresolved_blocks") is not True:
            add("contract-block-policy", "Unresolved signals must block.")
        wide = policy.get("wide_min_css_width")
        narrow = policy.get("narrow_max_css_width")
        if not isinstance(wide, int) or isinstance(wide, bool) or wide < 800:
            add("contract-wide-width", "wide_min_css_width must be at least 800.")
        if not isinstance(narrow, int) or isinstance(narrow, bool) or not 240 <= narrow <= 640:
            add("contract-narrow-width", "narrow_max_css_width must be from 240 through 640.")
        if isinstance(wide, int) and isinstance(narrow, int) and wide <= narrow:
            add("contract-width-order", "Wide evidence must be wider than narrow evidence.")
        if policy.get("exception_model") != "none-failure-states-only":
            add(
                "contract-exception-model",
                "The contract must close failure states instead of allowing ingredient exceptions.",
            )
        if policy.get("required_capture_mode") != "full-page":
            add(
                "contract-capture-mode",
                "required_capture_mode must be full-page for route-level closure.",
            )
    return findings


def contract_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return Path(os.path.abspath(os.fspath(explicit.expanduser())))
    configured = os.environ.get(CONTRACT_ENV)
    if configured:
        return Path(os.path.abspath(os.fspath(Path(configured).expanduser())))
    return Path.home() / Path(CANONICAL_CONTRACT_RELATIVE_PATH)


def project_path(path: Path) -> Path:
    root = Path(os.path.abspath(os.fspath(path.expanduser())))
    if not root.is_dir() or is_reparse(root):
        raise AuditError(
            "unsafe-project",
            "The project root must be an ordinary directory.",
            path=root,
        )
    return root


def project_relative_path(value: object) -> PurePosixPath | None:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        return None
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        return None
    if any(ord(character) < 32 for character in value):
        return None
    return candidate


def contained_file(project: Path, value: object, *, label: str) -> Path:
    relative = project_relative_path(value)
    if relative is None:
        raise AuditError(
            "invalid-evidence-path",
            f"{label} must use a safe project-relative forward-slash path.",
        )
    candidate = project.joinpath(*relative.parts)
    cursor = candidate
    while True:
        if cursor.exists() and is_reparse(cursor):
            raise AuditError(
                "evidence-reparse-refused",
                f"{label} crosses a link or reparse point.",
                path=cursor,
            )
        if cursor == project:
            break
        cursor = cursor.parent
    if not candidate.is_file() or is_reparse(candidate):
        raise AuditError(
            "evidence-missing",
            f"{label} does not resolve to an ordinary project file.",
            path=candidate,
        )
    return candidate


def verify_file_ref(
    project: Path,
    value: object,
    *,
    label: str,
) -> tuple[Path | None, list[dict[str, object]]]:
    findings: list[dict[str, object]] = []
    if not exact_keys(value, {"path", "sha256"}):
        return None, [{
            "code": "evidence-shape",
            "message": f"{label} must contain only path and sha256.",
        }]
    digest = value.get("sha256")
    if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
        return None, [{
            "code": "evidence-digest",
            "message": f"{label}.sha256 must be a lowercase SHA-256 digest.",
        }]
    try:
        path = contained_file(project, value.get("path"), label=label)
        raw = read_ordinary_bytes(path, label="evidence")
    except AuditError as exc:
        return None, [error_payload(exc)]
    observed = sha256_bytes(raw)
    if observed != digest:
        findings.append({
            "code": "evidence-digest-mismatch",
            "message": f"{label} digest does not match its current bytes.",
            "path": str(path),
        })
    return path, findings


def png_dimensions(path: Path) -> tuple[int, int]:
    raw = read_ordinary_bytes(path, label="rendered-evidence")
    if len(raw) < 45 or raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise AuditError(
            "rendered-evidence-not-png",
            "Rendered owner-pattern evidence must be a complete PNG.",
            path=path,
        )

    offset = 8
    chunks: list[tuple[bytes, bytes]] = []
    while offset < len(raw):
        if offset + 12 > len(raw):
            raise AuditError(
                "rendered-evidence-png-truncated",
                "Rendered evidence ends inside a PNG chunk.",
                path=path,
            )
        length = struct.unpack(">I", raw[offset:offset + 4])[0]
        kind = raw[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(raw):
            raise AuditError(
                "rendered-evidence-png-truncated",
                "Rendered evidence declares a PNG chunk beyond the file boundary.",
                path=path,
            )
        data = raw[offset + 8:offset + 8 + length]
        expected_crc = struct.unpack(">I", raw[offset + 8 + length:end])[0]
        observed_crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        if observed_crc != expected_crc:
            raise AuditError(
                "rendered-evidence-png-crc",
                "Rendered evidence has a PNG chunk checksum mismatch.",
                path=path,
            )
        chunks.append((kind, data))
        offset = end
        if kind == b"IEND":
            break

    if offset != len(raw) or not chunks or chunks[0][0] != b"IHDR":
        raise AuditError(
            "rendered-evidence-png-structure",
            "Rendered evidence has an invalid PNG chunk sequence.",
            path=path,
        )
    ihdr = chunks[0][1]
    if len(ihdr) != 13 or chunks[-1] != (b"IEND", b""):
        raise AuditError(
            "rendered-evidence-png-structure",
            "Rendered evidence needs one valid IHDR and a terminal empty IEND.",
            path=path,
        )
    if sum(1 for kind, _ in chunks if kind == b"IHDR") != 1:
        raise AuditError(
            "rendered-evidence-png-structure",
            "Rendered evidence must contain exactly one PNG IHDR.",
            path=path,
        )

    width, height, bit_depth, color_type, compression, filtering, interlace = (
        struct.unpack(">IIBBBBB", ihdr)
    )
    if width < 1 or height < 1 or width > 32768 or height > 131072:
        raise AuditError(
            "rendered-evidence-dimensions",
            "Rendered evidence has invalid or unsupported screenshot dimensions.",
            path=path,
        )
    allowed_depths = {
        0: {1, 2, 4, 8, 16},
        2: {8, 16},
        3: {1, 2, 4, 8},
        4: {8, 16},
        6: {8, 16},
    }
    if (
        color_type not in allowed_depths
        or bit_depth not in allowed_depths[color_type]
        or compression != 0
        or filtering != 0
        or interlace != 0
    ):
        raise AuditError(
            "rendered-evidence-png-format",
            "Rendered evidence must be a non-interlaced standard screenshot PNG.",
            path=path,
        )
    idat_parts = [data for kind, data in chunks if kind == b"IDAT"]
    if not idat_parts:
        raise AuditError(
            "rendered-evidence-png-idat",
            "Rendered evidence has no PNG image-data stream.",
            path=path,
        )
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    row_bytes = (width * channels * bit_depth + 7) // 8
    expected_decoded = (row_bytes + 1) * height
    if expected_decoded > 268_435_456:
        raise AuditError(
            "rendered-evidence-png-too-large",
            "Rendered evidence exceeds the bounded PNG verification budget.",
            path=path,
        )
    compressed = b"".join(idat_parts)
    try:
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(compressed, expected_decoded + 1)
        if decoder.unconsumed_tail:
            raise zlib.error("decoded data exceeds the expected screenshot size")
        decoded += decoder.flush()
    except zlib.error as exc:
        raise AuditError(
            "rendered-evidence-png-decode",
            f"Rendered evidence PNG image data does not decode: {exc}",
            path=path,
        ) from exc
    if not decoder.eof or decoder.unused_data or len(decoded) != expected_decoded:
        raise AuditError(
            "rendered-evidence-png-decode",
            "Rendered evidence PNG image data does not match its declared dimensions.",
            path=path,
        )
    stride = row_bytes + 1
    if any(decoded[offset] > 4 for offset in range(0, len(decoded), stride)):
        raise AuditError(
            "rendered-evidence-png-filter",
            "Rendered evidence PNG image data uses an invalid row filter.",
            path=path,
        )
    return width, height


def validate_capture(
    project: Path,
    value: object,
    *,
    label: str,
    policy: dict[str, object],
    expected_build_id: object,
) -> tuple[str | None, list[dict[str, object]]]:
    findings: list[dict[str, object]] = []
    expected = {
        "path",
        "sha256",
        "viewport",
        "css_width",
        "route_or_state",
        "build_id",
        "capture_mode",
    }
    if not exact_keys(value, expected):
        return None, [{
            "code": "capture-shape",
            "message": f"{label} has missing or unsupported fields.",
        }]
    viewport = value.get("viewport")
    if viewport not in {"wide", "narrow"}:
        findings.append({
            "code": "capture-viewport",
            "message": f"{label}.viewport must be wide or narrow.",
        })
    css_width = value.get("css_width")
    if not isinstance(css_width, int) or isinstance(css_width, bool) or css_width < 1:
        findings.append({
            "code": "capture-css-width",
            "message": f"{label}.css_width must be a positive integer.",
        })
    elif viewport == "wide" and css_width < int(policy["wide_min_css_width"]):
        findings.append({
            "code": "capture-not-wide",
            "message": f"{label} does not meet the owner contract's wide condition.",
        })
    elif viewport == "narrow" and css_width > int(policy["narrow_max_css_width"]):
        findings.append({
            "code": "capture-not-narrow",
            "message": f"{label} does not meet the owner contract's narrow condition.",
        })
    if not useful_text(value.get("route_or_state"), minimum=2):
        findings.append({
            "code": "capture-route-state",
            "message": f"{label}.route_or_state must identify what was rendered.",
        })
    if value.get("build_id") != expected_build_id:
        findings.append({
            "code": "capture-build-drift",
            "message": f"{label}.build_id does not match the final reviewed build.",
        })
    if value.get("capture_mode") != policy["required_capture_mode"]:
        findings.append({
            "code": "capture-mode",
            "message": f"{label}.capture_mode must be full-page.",
        })
    path, ref_findings = verify_file_ref(project, {
        "path": value.get("path"),
        "sha256": value.get("sha256"),
    }, label=label)
    findings.extend(ref_findings)
    if path is not None and not ref_findings:
        try:
            pixel_width, _ = png_dimensions(path)
            if isinstance(css_width, int) and pixel_width < css_width:
                findings.append({
                    "code": "capture-width-contradiction",
                    "message": f"{label} PNG width is smaller than its declared CSS width.",
                    "path": str(path),
                })
        except AuditError as exc:
            findings.append(error_payload(exc))
    return viewport if isinstance(viewport, str) else None, findings


def signal_ids(contract: dict[str, object]) -> list[str]:
    return [
        str(signal["id"])
        for signal in contract["signals"]
        if isinstance(signal, dict) and isinstance(signal.get("id"), str)
    ]


def initialized_review(contract: dict[str, object], digest: str) -> dict[str, object]:
    ids = signal_ids(contract)
    owner = contract["owner"]
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": REVIEW_ARTIFACT_TYPE,
        "created_with": "design-dna owner_pattern_audit.py",
        "status": "draft",
        "contract_binding": {
            "contract_id": contract["contract_id"],
            "sha256": digest,
            "owner_id": owner["id"],
            "scope": contract["scope"],
        },
        "project": {"id": None, "scope": None},
        "direction": {
            "status": "draft",
            "reviewed_at": None,
            "reviewer": None,
            "evidence": None,
            "signals": [
                {
                    "id": signal_id,
                    "disposition": "pending",
                    "decision": None,
                    "failure_prevention": None,
                    "project_basis": None,
                }
                for signal_id in ids
            ],
        },
        "final": {
            "status": "pending",
            "reviewed_at": None,
            "reviewer": None,
            "build_id": None,
            "visual_review": None,
            "signals": [
                {
                    "id": signal_id,
                    "disposition": "pending",
                    "observation": None,
                    "evidence": [],
                }
                for signal_id in ids
            ],
        },
    }


def review_path(project: Path) -> Path:
    return project.joinpath(*REVIEW_RELATIVE_PATH.parts)


def initialize_review(project: Path, contract_file: Path) -> dict[str, object]:
    root = project_path(project)
    raw = read_ordinary_bytes(contract_file, label="owner-pattern-contract")
    contract = strict_json(raw, path=contract_file)
    findings = validate_contract(contract, path=contract_file)
    if findings:
        raise AuditError(
            "owner-pattern-contract-invalid",
            " | ".join(str(item["message"]) for item in findings),
            path=contract_file,
        )
    assert isinstance(contract, dict)
    target = review_path(root)
    state_root = target.parent
    if state_root.exists() and (not state_root.is_dir() or is_reparse(state_root)):
        raise AuditError(
            "unsafe-state-root",
            ".design-dna must be an ordinary project directory.",
            path=state_root,
        )
    state_root.mkdir(exist_ok=True)
    if target.exists():
        raise AuditError(
            "review-already-exists",
            "Refusing to overwrite the existing owner pattern review.",
            path=target,
        )
    payload = initialized_review(contract, sha256_bytes(raw))
    encoded = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".owner-pattern-review-",
        suffix=".tmp",
        dir=state_root,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise AuditError(
            "review-write-failed",
            str(exc),
            path=target,
        ) from exc
    return {
        "ok": True,
        "action": "initialized",
        "path": str(target),
        "contract_id": contract["contract_id"],
        "contract_sha256": sha256_bytes(raw),
        "signal_count": len(signal_ids(contract)),
    }


def validate_signal_identity(
    values: object,
    ids: list[str],
    *,
    lane: str,
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    if not isinstance(values, list):
        return [{"code": f"{lane}-signals", "message": f"{lane}.signals must be a list."}]
    observed = [
        value.get("id") if isinstance(value, dict) else None
        for value in values
    ]
    if observed != ids:
        findings.append({
            "code": f"{lane}-signal-set",
            "message": (
                f"{lane}.signals must contain every contract signal exactly once "
                "in contract order."
            ),
        })
    return findings


def parse_visual_review_build(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    match = re.search(r"(?mi)^-\s*Build or artifact ID:\s*(.+?)\s*$", text)
    if match is None:
        return None
    value = match.group(1).strip()
    return value if useful_text(value, minimum=2) else None


def audit_project(
    project: Path,
    *,
    phase: str,
    contract_file: Path | None = None,
) -> dict[str, object]:
    if phase not in {"state", "prebuild", "ready"}:
        raise ValueError("phase must be state, prebuild, or ready")
    root = project_path(project)
    selected_contract = contract_path(contract_file)
    findings: list[dict[str, object]] = []
    gaps: list[dict[str, object]] = []
    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": ARTIFACT_TYPE,
        "automatic_aesthetic_pass": False,
        "phase": phase,
        "contract_active": False,
        "structural_valid": False,
        "ready": False,
        "findings": findings,
        "gaps": gaps,
    }
    if not selected_contract.is_file() or is_reparse(selected_contract):
        gaps.append({
            "code": "owner-pattern-contract-missing",
            "message": (
                "The owner-pattern-contract trigger is active, but no ordinary "
                f"contract exists at {selected_contract}."
            ),
        })
        return result

    raw_contract = read_ordinary_bytes(
        selected_contract,
        label="owner-pattern-contract",
    )
    contract = strict_json(raw_contract, path=selected_contract)
    findings.extend(validate_contract(contract, path=selected_contract))
    if findings or not isinstance(contract, dict):
        return result
    result["contract_active"] = True
    digest = sha256_bytes(raw_contract)
    ids = signal_ids(contract)
    result["contract"] = {
        "id": contract["contract_id"],
        "sha256": digest,
        "signal_count": len(ids),
    }

    target = review_path(root)
    if not target.is_file() or is_reparse(target):
        gaps.append({
            "code": "owner-pattern-review-missing",
            "message": (
                "Create the project review with owner_pattern_audit.py "
                "--init-review before continuing."
            ),
            "path": str(target),
        })
        return result
    raw_review = read_ordinary_bytes(target, label="owner-pattern-review")
    review = strict_json(raw_review, path=target)
    if not isinstance(review, dict):
        findings.append({
            "code": "review-not-object",
            "message": "The owner pattern review must be a JSON object.",
        })
        return result
    if set(review) != REVIEW_KEYS:
        findings.append({
            "code": "review-key-mismatch",
            "message": "The owner pattern review has missing or unsupported top-level keys.",
        })
    if review.get("schema_version") != SCHEMA_VERSION:
        findings.append({"code": "review-schema", "message": "Unsupported review schema."})
    if review.get("artifact_type") != REVIEW_ARTIFACT_TYPE:
        findings.append({"code": "review-artifact", "message": "Unexpected review artifact_type."})
    if not useful_text(review.get("created_with"), minimum=4):
        findings.append({"code": "review-created-with", "message": "created_with is incomplete."})
    if review.get("status") not in {"draft", "direction-ready", "reviewed", "blocked"}:
        findings.append({"code": "review-status", "message": "Unsupported review status."})

    binding = review.get("contract_binding")
    binding_keys = {"contract_id", "sha256", "owner_id", "scope"}
    owner = contract["owner"]
    if not exact_keys(binding, binding_keys):
        findings.append({"code": "review-binding-shape", "message": "contract_binding is malformed."})
    elif (
        binding.get("contract_id") != contract["contract_id"]
        or binding.get("sha256") != digest
        or binding.get("owner_id") != owner["id"]
        or binding.get("scope") != contract["scope"]
    ):
        findings.append({
            "code": "review-contract-drift",
            "message": "The project review is not bound to the current owner contract bytes.",
        })

    project_record = review.get("project")
    if not exact_keys(project_record, {"id", "scope"}):
        findings.append({"code": "review-project-shape", "message": "project is malformed."})

    direction = review.get("direction")
    direction_keys = {"status", "reviewed_at", "reviewer", "evidence", "signals"}
    if not exact_keys(direction, direction_keys):
        findings.append({"code": "direction-shape", "message": "direction is malformed."})
        direction = None
    else:
        if direction.get("status") not in {"draft", "passed", "blocked"}:
            findings.append({"code": "direction-status", "message": "Unsupported direction status."})
        findings.extend(validate_signal_identity(direction.get("signals"), ids, lane="direction"))
        for index, item in enumerate(direction.get("signals", [])):
            expected = {"id", "disposition", "decision", "failure_prevention", "project_basis"}
            if not exact_keys(item, expected):
                findings.append({
                    "code": "direction-signal-shape",
                    "message": f"direction.signals[{index}] is malformed.",
                })
            elif item.get("disposition") not in {"pending", "controlled", "blocked"}:
                findings.append({
                    "code": "direction-disposition",
                    "message": f"direction.signals[{index}] has an unsupported disposition.",
                })

    final = review.get("final")
    final_keys = {"status", "reviewed_at", "reviewer", "build_id", "visual_review", "signals"}
    if not exact_keys(final, final_keys):
        findings.append({"code": "final-shape", "message": "final is malformed."})
        final = None
    else:
        if final.get("status") not in {"pending", "passed", "blocked"}:
            findings.append({"code": "final-status", "message": "Unsupported final status."})
        findings.extend(validate_signal_identity(final.get("signals"), ids, lane="final"))
        for index, item in enumerate(final.get("signals", [])):
            expected = {"id", "disposition", "observation", "evidence"}
            if not exact_keys(item, expected):
                findings.append({
                    "code": "final-signal-shape",
                    "message": f"final.signals[{index}] is malformed.",
                })
            elif item.get("disposition") not in {"pending", "absent", "blocked"}:
                findings.append({
                    "code": "final-disposition",
                    "message": f"final.signals[{index}] has an unsupported disposition.",
                })
            if isinstance(item, dict) and not isinstance(item.get("evidence"), list):
                findings.append({
                    "code": "final-evidence-list",
                    "message": f"final.signals[{index}].evidence must be a list.",
                })

    if findings:
        return result
    result["structural_valid"] = True
    if phase == "state":
        result["ready"] = True
        return result

    assert isinstance(project_record, dict)
    assert isinstance(direction, dict)
    if not useful_text(project_record.get("id"), minimum=2) or not useful_text(
        project_record.get("scope"), minimum=12
    ):
        gaps.append({
            "code": "project-identity-pending",
            "message": "Project id and exact review scope must be completed.",
        })
    if review.get("status") not in {"direction-ready", "reviewed"}:
        gaps.append({
            "code": "direction-review-not-ready",
            "message": "Top-level review status must be direction-ready or reviewed.",
        })
    if direction.get("status") != "passed":
        gaps.append({
            "code": "direction-lane-not-passed",
            "message": "The direction lane must pass before broad implementation.",
        })
    if not useful_text(direction.get("reviewer"), minimum=2) or not valid_iso_date_or_datetime(
        direction.get("reviewed_at")
    ):
        gaps.append({
            "code": "direction-review-identity",
            "message": "Direction review needs a reviewer and ISO date or datetime.",
        })
    _, direction_evidence_findings = verify_file_ref(
        root,
        direction.get("evidence"),
        label="direction.evidence",
    )
    gaps.extend(direction_evidence_findings)
    for index, item in enumerate(direction["signals"]):
        if item.get("disposition") != contract["release_policy"]["direction_disposition"]:
            gaps.append({
                "code": "direction-signal-unresolved",
                "message": f"Direction signal {item.get('id', index)} is not controlled.",
            })
        for field in ("decision", "failure_prevention", "project_basis"):
            if not useful_text(item.get(field), minimum=12):
                gaps.append({
                    "code": "direction-signal-incomplete",
                    "message": f"Direction signal {item.get('id', index)} needs {field}.",
                })
    if gaps or phase == "prebuild":
        result["ready"] = not gaps
        return result

    assert isinstance(final, dict)
    if review.get("status") != "reviewed":
        gaps.append({
            "code": "final-review-not-reviewed",
            "message": "Top-level review status must be reviewed for readiness.",
        })
    if final.get("status") != "passed":
        gaps.append({
            "code": "final-lane-not-passed",
            "message": "The final owner-pattern lane must pass.",
        })
    if not useful_text(final.get("reviewer"), minimum=2) or not valid_iso_date_or_datetime(
        final.get("reviewed_at")
    ):
        gaps.append({
            "code": "final-review-identity",
            "message": "Final review needs a reviewer and ISO date or datetime.",
        })
    build_id = final.get("build_id")
    if not useful_text(build_id, minimum=2):
        gaps.append({"code": "final-build-id", "message": "Final build_id is incomplete."})
    visual_review_path, visual_review_findings = verify_file_ref(
        root,
        final.get("visual_review"),
        label="final.visual_review",
    )
    gaps.extend(visual_review_findings)
    if visual_review_path is not None and not visual_review_findings:
        visual_build = parse_visual_review_build(visual_review_path)
        if visual_build is None:
            gaps.append({
                "code": "visual-review-build-missing",
                "message": "The bound visual review has no completed Build or artifact ID.",
            })
        elif visual_build != build_id:
            gaps.append({
                "code": "visual-review-build-drift",
                "message": "Owner-pattern review and visual-review.md name different builds.",
            })

    policy = contract["release_policy"]
    for index, item in enumerate(final["signals"]):
        signal_id = item.get("id", index)
        if item.get("disposition") != policy["final_disposition"]:
            gaps.append({
                "code": "final-signal-unresolved",
                "message": f"Final signal {signal_id} is not proven absent.",
            })
        if not useful_text(item.get("observation"), minimum=12):
            gaps.append({
                "code": "final-signal-observation",
                "message": f"Final signal {signal_id} needs a rendered observation.",
            })
        viewports: set[str] = set()
        viewport_identities: dict[str, tuple[object, object]] = {}
        evidence = item.get("evidence")
        if isinstance(evidence, list):
            if len(evidence) != 2:
                gaps.append({
                    "code": "final-signal-evidence-cardinality",
                    "message": (
                        f"Final signal {signal_id} must bind exactly one wide and "
                        "one narrow full-page capture."
                    ),
                })
            for evidence_index, capture in enumerate(evidence):
                viewport, capture_findings = validate_capture(
                    root,
                    capture,
                    label=f"final.signals[{index}].evidence[{evidence_index}]",
                    policy=policy,
                    expected_build_id=build_id,
                )
                if viewport is not None:
                    viewports.add(viewport)
                    if isinstance(capture, dict):
                        viewport_identities[viewport] = (
                            capture.get("path"),
                            capture.get("sha256"),
                        )
                gaps.extend(capture_findings)
        if viewports != {"wide", "narrow"}:
            gaps.append({
                "code": "final-signal-render-coverage",
                "message": f"Final signal {signal_id} needs both wide and narrow PNG evidence.",
            })
        else:
            wide_identity = viewport_identities.get("wide")
            narrow_identity = viewport_identities.get("narrow")
            if (
                wide_identity is not None
                and narrow_identity is not None
                and (
                    wide_identity[0] == narrow_identity[0]
                    or wide_identity[1] == narrow_identity[1]
                )
            ):
                gaps.append({
                    "code": "final-signal-render-reuse",
                    "message": (
                        f"Final signal {signal_id} must bind distinct wide and "
                        "narrow capture paths and bytes."
                    ),
                })

    result["ready"] = not gaps
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument(
        "--phase",
        choices=("state", "prebuild", "ready"),
        default="ready",
    )
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--init-review", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        selected_contract = contract_path(args.contract)
        if args.init_review:
            result = initialize_review(args.project, selected_contract)
            print(json.dumps(result, indent=2) if args.json else (
                f"Initialized {result['path']} with {result['signal_count']} "
                "owner-pattern failure states."
            ))
            return 0
        result = audit_project(
            args.project,
            phase=args.phase,
            contract_file=selected_contract,
        )
    except AuditError as exc:
        fail(exc)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        messages = [
            *(f"FINDING {item.get('code')}: {item.get('message')}" for item in result["findings"]),
            *(f"GAP {item.get('code')}: {item.get('message')}" for item in result["gaps"]),
        ]
        print("\n".join(messages) if messages else (
            f"OK: Owner-pattern {args.phase} review is structurally and evidentially complete."
        ))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
