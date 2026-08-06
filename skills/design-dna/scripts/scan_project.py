#!/usr/bin/env python3
"""Python 3.10+ source scanner for design-review candidates and gate-safe defects."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import html
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional


MINIMUM_PYTHON = (3, 10)
if sys.version_info < MINIMUM_PYTHON:  # pragma: no cover - requires an old interpreter
    print(
        json.dumps({
            "schema_version": 1,
            "artifact_type": "design-dna-source-scan",
            "ok": False,
            "execution_ok": False,
            "execution": {"status": "failed", "ok": False},
            "error": {
                "code": "python-version-unsupported",
                "message": "scan_project.py requires Python 3.10 or newer.",
                "required": ">=3.10",
                "current": ".".join(str(part) for part in sys.version_info[:3]),
            },
        }),
        file=sys.stderr,
    )
    raise SystemExit(2)


TEXT_SUFFIXES = {
    ".astro", ".cjs", ".cshtml", ".css", ".ejs", ".erb", ".gohtml",
    ".handlebars", ".hbs", ".html", ".htm", ".j2", ".jinja", ".jinja2",
    ".js", ".jsx", ".less", ".liquid", ".md", ".mdx", ".mjs",
    ".mustache", ".njk", ".php", ".pug", ".razor", ".scss", ".styl",
    ".stylus", ".svelte", ".svg", ".tmpl", ".tpl", ".ts", ".tsx",
    ".twig", ".vue",
}
STRUCTURED_CONTENT_SUFFIXES = {".json", ".yaml", ".yml"}
SENSITIVE_STRUCTURED_PART = re.compile(
    r"(?:^|[-_.])(?:auth|configs?|credentials?|keys?|passwords?|private|"
    r"secrets?|tokens?)"
    r"(?:$|[-_.])",
    re.I,
)
SENSITIVE_STRUCTURED_DIRS = {
    ".github", ".well-known", "config", "configuration", "infra",
    "infrastructure", "secrets",
}
SENSITIVE_STRUCTURED_DIRS_CASEFOLD = {
    name.casefold() for name in SENSITIVE_STRUCTURED_DIRS
}
PROMINENT_MARKUP_SUFFIXES = {
    ".astro", ".cshtml", ".ejs", ".erb", ".gohtml", ".handlebars", ".hbs",
    ".html", ".htm", ".j2", ".jinja", ".jinja2", ".jsx", ".liquid",
    ".mdx", ".mustache", ".njk", ".php", ".razor", ".svelte", ".svg",
    ".tmpl", ".tpl", ".tsx", ".twig", ".vue",
}
STATIC_MARKUP_SUFFIXES = {
    ".astro", ".ejs", ".gohtml", ".handlebars", ".hbs", ".html", ".htm",
    ".j2", ".jinja", ".jinja2", ".jsx", ".liquid", ".mdx", ".mustache",
    ".njk", ".svelte", ".svg", ".tmpl", ".tpl", ".tsx", ".twig", ".vue",
}
HTML_VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
ALWAYS_IGNORED_DIRS = {
    ".design-dna", ".git", "coverage", "node_modules", "vendor",
}
INITIALIZER_EVIDENCE_DIR_PATTERN = re.compile(
    r"^\.design-dna\.(?:backup|failed)-"
    r"\d{8}-\d{6}-\d{6}"
    r"(?:-(?:[2-9]|[1-9]\d+))?$",
    re.I,
)
INITIALIZER_EVIDENCE_DIR_LABELS = {
    ".design-dna.backup-YYYYMMDD-HHMMSS-ffffff[-N]",
    ".design-dna.failed-YYYYMMDD-HHMMSS-ffffff[-N]",
}
BUILT_OUTPUT_DIRS = {
    ".next", ".nuxt", ".output", ".svelte-kit", "build", "dist",
}
IGNORED_DIRS = ALWAYS_IGNORED_DIRS | BUILT_OUTPUT_DIRS
DEPENDENCY_VENDOR_DIRS = {"node_modules", "vendor"}
DEFAULT_CONTENT_EXCLUDED_DIRS = {
    ".storybook", "__fixtures__", "__tests__", "docs", "documentation",
    "fixtures", "reference", "references", "stories", "storybook", "test",
    "tests",
}
DEFAULT_CONTENT_EXCLUDED_DIRS_CASEFOLD = {
    name.casefold() for name in DEFAULT_CONTENT_EXCLUDED_DIRS
}
DOCUMENTATION_CONTENT_DIRS = {
    "docs", "documentation", "reference", "references",
}
DOCUMENTATION_CONTENT_DIRS_CASEFOLD = {
    name.casefold() for name in DOCUMENTATION_CONTENT_DIRS
}
NON_DOCUMENTATION_CONTENT_EXCLUDED_DIRS_CASEFOLD = (
    DEFAULT_CONTENT_EXCLUDED_DIRS_CASEFOLD
    - DOCUMENTATION_CONTENT_DIRS_CASEFOLD
)
DEFAULT_CONTENT_EXCLUDED_FILES = {
    "changelog.md", "contributing.md", "license.md", "readme.md",
}
DEFAULT_CONTENT_EXCLUDED_FILE_PATTERNS = (
    "*.fixture.*", "*.spec.*", "*.stories.*", "*.story.*", "*.test.*",
)
NON_OVERRIDABLE_RULES = frozenset()
EXAMPLE_ALLOWLIST_LIFETIME_DAYS = 30
MAX_ALLOWLIST_FUTURE_DAYS = 90
FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ISO_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
OWNER_POLICY_DEFAULT_ID = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
OWNER_POLICY_DEFAULT_VALUES = {
    "require",
    "require-review",
    "investigate",
    "allow",
    "ask",
    "prohibit",
    "opt-in",
    "off",
    "on",
}
MAX_TEXT_FILE_BYTES = 5 * 1024 * 1024
SCAN_RESULT_SCHEMA_VERSION = 2
SCAN_RESULT_ARTIFACT_TYPE = "design-dna-source-scan"
PROMINENT_CLASS = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z0-9]+[-_])*"
    r"(?:hero|headline|tagline|poster|wordmark|display)"
    r"(?:[-_][A-Za-z0-9]+)*(?![A-Za-z0-9])|signal-board__message",
    re.I,
)
SEMANTIC_FRAGMENT = re.compile(
    r"(?<![A-Za-z0-9])(?:status|state|badge|chip|tag|severity|priority|success|error|"
    r"warning|danger|active|inactive|open|closed|pending|approved|denied|"
    r"available|unavailable|online|offline|price|amount|metric|data|quote|link)"
    r"(?![A-Za-z0-9])",
    re.I,
)
SEMANTIC_STATUS_TEXT = {
    "active", "approved", "available", "blocked", "closed", "danger", "denied",
    "error", "failed", "inactive", "offline", "online", "open", "pending",
    "success", "unavailable", "warning",
}
TAILWIND_FOREGROUND = re.compile(
    r"(?:^|\s)(?:[a-z0-9_-]+:)*text-(?:"
    r"(?:purple|violet|indigo|blue|emerald|amber|rose|red|green|cyan|teal|"
    r"lime|orange|yellow|pink|fuchsia|sky)(?:-[0-9]{2,3})?(?:/[0-9]{1,3})?"
    r"|\[(?:#[0-9a-fA-F]{3,8}|(?:rgb|hsl|oklch|lab|color|var)[^\]]*)\]"
    r")(?=\s|$|[\"'`}]|:)",
    re.I,
)
FOREGROUND_DECLARATION = re.compile(
    r"(?:^|[;{]\s*)(?:color|-webkit-text-fill-color)\s*:",
    re.I,
)
NEGATIVE_OR_EXAMPLE_CONTEXT = re.compile(
    r"\b(?:do\s+not|don['’]t|must\s+not|never|avoid|remove|reject|forbid(?:den)?|"
    r"anti[- ]?pattern|bad\s+example|negative\s+example|placeholder|sample\s+of|"
    r"example\s+of|should\s+not|cannot\s+claim)\b",
    re.I,
)
FILLER_NEGATIVE_CONTEXT = re.compile(
    r"\b(?:do\s+not|don['’]t|must\s+not|never|avoid|remove|reject|"
    r"forbid(?:den)?|should\s+not)\b",
    re.I,
)
VISIBLE_FILLER = re.compile(r"\blorem(?:[\s\u00a0]+)ipsum\b", re.I)
RAW_FILLER = re.compile(
    r"\blorem(?:[\s\u00a0]|&(?:nbsp|#160|#x0*a0);)+ipsum\b",
    re.I,
)
QUANTITATIVE_CLAIM = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"\$\s*\d[\d,.]*(?:\s*(?:to|[-–—])\s*\$?\s*\d[\d,.]*)?"
    r"|"
    r"\d+(?:\.\d+)?(?:\s*(?:to|[-–—])\s*\d+(?:\.\d+)?)?\s*"
    r"(?:%|A\b|AWG\b|V\b|kW\b|kWh\b|miles?\b|mi\b|feet\b|ft\b|"
    r"minutes?\b|mins?\b|hours?\b|days?\b|weeks?\b|months?\b|"
    r"years?\b|year\b|in(?:ch(?:es)?)?\b|per\s+(?:hour|day|month|year)\b)"
    r")",
    re.I,
)
GENERATED_MEDIA_MARKER = re.compile(
    r"\b(?:AI[- ]generated|generated\s+(?:image|imagery|photo|photography)|"
    r"synthetic\s+(?:image|imagery|photo|photography)|"
    r"(?:image|imagery|photo|photography)\s+is\s+"
    r"(?:AI[- ]generated|generated|synthetic))\b",
    re.I,
)
PUBLIC_META_COPY_MARKER = re.compile(
    r"\b(?:design\s+(?:test|proof|direction)|"
    r"(?:(?:client|owner|project)\s+)?"
    r"(?:assets?|brand\s+materials?|approved\s+copy|client\s+details?)\s+"
    r"(?:are\s+|remain\s+)?"
    r"(?:missing|unavailable|not\s+(?:supplied|connected|approved))|"
    r"inspect\s+the\s+proposed|choose\s+(?:a|the)\s+(?:page\s+)?route|"
    r"route\s+study|truth\s+(?:list|before\s+theater))\b",
    re.I,
)
CSS_DECLARATION_BLOCK = re.compile(r"(?P<header>[^{}]*)\{(?P<body>[^{}]*)\}", re.S)


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    pattern: Optional[re.Pattern[str]]
    rationale: str
    suggestion: str
    min_occurrences: int = 1
    classification: str = "advisory"


# Keep automatic rules evidence-bound. Aesthetic ingredients belong in
# rendered, project-specific review and must not re-enter this table as
# portable name or count heuristics.
RULES = (
    Rule(
        "deferred-content-visibility",
        "medium",
        re.compile(
            r"\.(?:reveal|fade(?:-?in)?|animate-in)[^{]{0,120}\{[^}]{0,300}"
            r"(?:opacity\s*:\s*0(?:\s*!important)?\s*(?:;|})|"
            r"visibility\s*:\s*hidden(?:\s*!important)?\s*(?:;|}))",
            re.I,
        ),
        "Entrance styling that hides content by default can fail closed when JavaScript, observation, reduced-motion handling, or full-page capture does not reveal every target.",
        "Keep essential content visible by default, opt into animation only after capability initialization, and verify JavaScript-disabled, reduced-motion, and no-pre-scroll captures.",
    ),
    Rule(
        "placeholder-proof",
        "high",
        RAW_FILLER,
        "Visible filler text is definite unfinished residue.",
        "Replace it with approved content, an honest project-specific pending state, or omit the section.",
        classification="gate",
    ),
    Rule(
        "claim-needs-provenance",
        "medium",
        re.compile(
            r"\b(?:10,?000\+|trusted by thousands|industry[- ]leading|"
            r"five[- ]star rated|#1\s+(?:platform|choice))\b",
            re.I,
        ),
        "Broad proof-shaped marketing language needs an accountable source; source text alone cannot establish that it is false.",
        "Trace the claim to approved evidence, qualify it precisely, label it as illustrative, or remove it.",
    ),
)


def is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise RuntimeError(f"path-inspection-failed: {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    if not attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        return False
    tag = getattr(info, "st_reparse_tag", 0)
    if tag:
        return bool(tag & 0x20000000) or tag in {0xA0000003, 0xA000000C}
    return True


def is_ignored_directory(name: str, ignored_names: set[str]) -> bool:
    return (
        name.casefold() in ignored_names
        or INITIALIZER_EVIDENCE_DIR_PATTERN.fullmatch(name) is not None
    )


def iter_files(
    root: Path,
    suffixes: set[str],
    *,
    include_built_output: bool = False,
):
    def fail_walk(error: OSError) -> None:
        raise RuntimeError(
            f"tree-enumeration-failed: {error.filename or root}: {error}"
        ) from error

    for current, dirs, files in os.walk(
        root,
        topdown=True,
        followlinks=False,
        onerror=fail_walk,
    ):
        current_path = Path(current)
        ignored = {
            name.casefold()
            for name in (
                ALWAYS_IGNORED_DIRS
                if include_built_output
                else IGNORED_DIRS
            )
        }
        dirs[:] = [
            name
            for name in dirs
            if not is_ignored_directory(name, ignored)
        ]
        unsafe = [name for name in dirs if is_reparse(current_path / name)]
        if unsafe:
            raise RuntimeError(f"reparse-point-refused: {current_path / unsafe[0]}")
        for name in files:
            path = current_path / name
            if is_reparse(path):
                raise RuntimeError(f"reparse-point-refused: {path}")
            if path.suffix.lower() in suffixes:
                yield path


def strict_json(text: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)


def assert_no_reparse_path(path: Path, *, stop: Path) -> None:
    candidate = Path(os.path.abspath(os.fspath(path)))
    stop = Path(os.path.abspath(os.fspath(stop)))
    try:
        candidate.relative_to(stop)
    except ValueError as exc:
        raise ValueError(f"path is outside the project: {candidate}") from exc
    while True:
        if is_reparse(candidate):
            raise RuntimeError(f"reparse-point-refused: {candidate}")
        if candidate == stop:
            return
        candidate = candidate.parent


def report_input_label(
    path: Path,
    *,
    project: Path,
    skill_root: Path,
    role: str,
) -> str:
    """Return useful provenance without embedding a machine-local path."""

    absolute = Path(os.path.abspath(os.fspath(path)))
    for prefix, root in (("project", project), ("skill", skill_root)):
        try:
            relative = absolute.relative_to(root)
        except ValueError:
            continue
        suffix = relative.as_posix()
        return f"{prefix}:/{suffix}" if suffix else f"{prefix}:/"
    try:
        digest = hashlib.sha256(absolute.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(
            f"unable to identify external {role} input"
        ) from exc
    return f"external:{role}:sha256:{digest}"


def exact_iso_date(value: object, *, label: str) -> date:
    if (
        not isinstance(value, str)
        or not ISO_DATE_PATTERN.fullmatch(value)
    ):
        raise ValueError(
            f"{label} must be a YYYY-MM-DD string: {value!r}"
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid {label}: {value!r}") from exc


def is_project_relative_glob(
    value: object,
    *,
    forward_slash_only: bool = False,
) -> bool:
    """Validate path-glob syntax consistently across host operating systems."""
    if not isinstance(value, str) or not value.strip():
        return False
    if value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
        return False
    if forward_slash_only and "\\" in value:
        return False
    if ".." in value.replace("\\", "/").split("/"):
        return False
    return not Path(value).is_absolute()


def load_allowlist(
    path: Optional[Path],
    *,
    project: Path,
    known_rules: set[str],
    non_overridable_rules: frozenset[str],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    if path is None:
        return [], [], [], []
    assert_no_reparse_path(path, stop=project)
    if not path.is_file():
        raise ValueError(f"allowlist does not exist: {path}")
    payload = strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("allowlist must be an object with schema_version: 1")
    required_top_level = {"schema_version", "allow"}
    allowed_top_level = required_top_level | {"acknowledge_skipped"}
    if required_top_level - set(payload) or set(payload) - allowed_top_level:
        raise ValueError("allowlist contains unsupported top-level fields")
    entries = payload.get("allow", [])
    if not isinstance(entries, list):
        raise ValueError("allow must be a list")
    active: list[dict[str, object]] = []
    expired: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("each allowlist entry must be an object")
        required = {
            "rule", "path", "fingerprint", "reason", "owner", "expires",
        }
        allowed_fields = required | {"line"}
        if set(entry) - allowed_fields or required - set(entry):
            raise ValueError(
                "each allowlist entry needs only rule, path, fingerprint, "
                "reason, owner, expires, and optional line"
            )
        rule = entry.get("rule")
        pattern = entry.get("path")
        fingerprint = entry.get("fingerprint")
        reason = entry.get("reason")
        owner = entry.get("owner")
        expires = entry.get("expires")
        if rule == "*":
            raise ValueError(
                "global allowlist rule '*' is prohibited; name each reviewed rule explicitly"
            )
        if not isinstance(rule, str) or rule not in known_rules:
            raise ValueError(f"unknown allowlist rule: {rule!r}")
        if rule in non_overridable_rules:
            raise ValueError(
                f"allowlist cannot suppress non-overridable truth rule: {rule}"
            )
        if not is_project_relative_glob(pattern):
            raise ValueError("allowlist path must be a nonempty project-relative glob")
        if (
            not isinstance(fingerprint, str)
            or not FINGERPRINT_PATTERN.fullmatch(fingerprint)
        ):
            raise ValueError(
                "allowlist fingerprint must be a lowercase SHA-256 finding fingerprint"
            )
        if not isinstance(reason, str) or len(reason.strip()) < 5:
            raise ValueError("allowlist reason must contain at least five characters")
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("allowlist owner must be nonempty")
        if "line" in entry and (
            not isinstance(entry["line"], int)
            or isinstance(entry["line"], bool)
            or entry["line"] < 1
        ):
            raise ValueError("allowlist line must be a positive integer")
        expiry = exact_iso_date(expires, label="allowlist expiry")
        if expiry > date.today() + timedelta(days=MAX_ALLOWLIST_FUTURE_DAYS):
            raise ValueError(
                "allowlist expiry must be no more than 90 days in the future"
            )
        identity = (rule, pattern, entry.get("line"))
        if identity in seen:
            raise ValueError(f"duplicate allowlist entry: {identity}")
        seen.add(identity)
        if expiry < date.today():
            expired.append(entry)
        else:
            active.append(entry)

    acknowledgement_entries = payload.get("acknowledge_skipped", [])
    if not isinstance(acknowledgement_entries, list):
        raise ValueError("acknowledge_skipped must be a list")
    active_acknowledgements: list[dict[str, object]] = []
    expired_acknowledgements: list[dict[str, object]] = []
    acknowledgement_seen: set[tuple[object, ...]] = set()
    for entry in acknowledgement_entries:
        if not isinstance(entry, dict):
            raise ValueError("each skipped-source acknowledgement must be an object")
        required = {
            "path", "sha256", "size_bytes", "reason", "owner", "expires",
        }
        if set(entry) != required:
            raise ValueError(
                "each skipped-source acknowledgement needs only path, sha256, "
                "size_bytes, reason, owner, and expires"
            )
        pattern = entry.get("path")
        digest = entry.get("sha256")
        size_bytes = entry.get("size_bytes")
        reason = entry.get("reason")
        owner = entry.get("owner")
        expires = entry.get("expires")
        if not is_project_relative_glob(
            pattern,
            forward_slash_only=True,
        ):
            raise ValueError(
                "skipped-source acknowledgement path must be a nonempty "
                "project-relative forward-slash glob"
            )
        if (
            not isinstance(digest, str)
            or not FINGERPRINT_PATTERN.fullmatch(digest)
        ):
            raise ValueError(
                "skipped-source acknowledgement sha256 must be a lowercase "
                "SHA-256 source digest"
            )
        if (
            not isinstance(size_bytes, int)
            or isinstance(size_bytes, bool)
            or size_bytes < 0
        ):
            raise ValueError(
                "skipped-source acknowledgement size_bytes must be a "
                "nonnegative integer"
            )
        if not isinstance(reason, str) or len(reason.strip()) < 5:
            raise ValueError(
                "skipped-source acknowledgement reason must contain at least "
                "five characters"
            )
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError(
                "skipped-source acknowledgement owner must be nonempty"
            )
        expiry = exact_iso_date(
            expires,
            label="skipped-source acknowledgement expiry",
        )
        if expiry > date.today() + timedelta(days=MAX_ALLOWLIST_FUTURE_DAYS):
            raise ValueError(
                "skipped-source acknowledgement expiry must be no more than "
                "90 days in the future"
            )
        identity = (pattern,)
        if identity in acknowledgement_seen:
            raise ValueError(
                f"duplicate skipped-source acknowledgement: {identity}"
            )
        acknowledgement_seen.add(identity)
        if expiry < date.today():
            expired_acknowledgements.append(entry)
        else:
            active_acknowledgements.append(entry)
    return (
        active,
        expired,
        active_acknowledgements,
        expired_acknowledgements,
    )


def without_comments(text: str) -> str:
    preserve_lines = lambda match: "\n" * match.group(0).count("\n")
    text = re.sub(r"<!--.*?-->", preserve_lines, text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", preserve_lines, text, flags=re.S)
    text = re.sub(
        r"(?m)^(\s*)//.*$",
        lambda match: match.group(1),
        text,
    )
    return text


def owner_policy_scalar(raw: str, *, line: int) -> object:
    value = raw.strip()
    if not value:
        raise ValueError(f"owner-policy scalar is empty at line {line}")
    if value[0] in {"\"", "'"}:
        if len(value) < 2 or value[-1] != value[0]:
            raise ValueError(f"owner-policy quote is unterminated at line {line}")
        return value[1:-1]
    if value in {"true", "false"}:
        return value == "true"
    if re.fullmatch(r"[0-9]+", value):
        return int(value)
    if "#" in value or any(character in value for character in "{}[]"):
        raise ValueError(f"ambiguous owner-policy scalar at line {line}")
    return value


def load_owner_policy(path: Path) -> dict[str, str]:
    """Validate the complete bounded owner-policy contract."""
    if not path.is_file():
        raise ValueError(f"owner policy does not exist: {path}")
    if is_reparse(path):
        raise RuntimeError(f"reparse-point-refused: {path}")
    top_level: dict[str, object] = {}
    defaults: dict[str, object] = {}
    lists: dict[str, list[str]] = {"interpretation": []}
    section: str | None = None
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "\t" in line:
            raise ValueError(f"owner policy cannot contain tabs at line {number}")
        if not line.startswith(" "):
            match = re.fullmatch(
                r"([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?",
                line,
            )
            if not match:
                raise ValueError(f"unsupported owner-policy YAML at line {number}")
            key, raw = match.group(1), match.group(2) or ""
            if key in top_level:
                raise ValueError(f"duplicate owner-policy key: {key}")
            if raw:
                top_level[key] = owner_policy_scalar(raw, line=number)
                section = None
            else:
                top_level[key] = None
                section = key
            continue
        if not line.startswith("  ") or line.startswith("   "):
            raise ValueError(f"unsupported owner-policy YAML at line {number}")
        if section == "defaults":
            match = re.fullmatch(
                r"  ([A-Za-z_][A-Za-z0-9_-]*):\s*(.+)",
                line,
            )
            if not match:
                raise ValueError(
                    f"unsupported owner-policy default at line {number}"
                )
            key = match.group(1)
            if key in defaults:
                raise ValueError(f"duplicate owner-policy default: {key}")
            defaults[key] = owner_policy_scalar(
                match.group(2),
                line=number,
            )
        elif section in lists:
            match = re.fullmatch(r"  -\s+(.+)", line)
            if not match:
                raise ValueError(
                    f"unsupported owner-policy list item at line {number}"
                )
            value = owner_policy_scalar(match.group(1), line=number)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"owner-policy list item must be text at line {number}"
                )
            lists[section].append(value)
        else:
            raise ValueError(
                f"unsupported owner-policy section at line {number}"
            )

    required = {
        "schema_version",
        "owner",
        "scope",
        "status",
        "defaults",
        "interpretation",
    }
    if set(top_level) != required:
        missing = sorted(required - set(top_level))
        unknown = sorted(set(top_level) - required)
        raise ValueError(
            "owner-policy top-level contract mismatch; "
            f"missing={missing}, unknown={unknown}"
        )
    if top_level["schema_version"] != 2:
        raise ValueError("owner-policy schema_version must be 2")
    for field in ("owner", "scope"):
        if (
            not isinstance(top_level[field], str)
            or not str(top_level[field]).strip()
        ):
            raise ValueError(f"owner-policy {field} must be nonempty text")
    if top_level["status"] != "active":
        raise ValueError("owner-policy status must be active")
    if not 1 <= len(defaults) <= 64:
        raise ValueError(
            "owner-policy defaults must contain 1 through 64 scoped concerns"
        )
    for field, value in defaults.items():
        if OWNER_POLICY_DEFAULT_ID.fullmatch(field) is None:
            raise ValueError(
                f"owner-policy default {field!r} is not a portable concern ID"
            )
        if not isinstance(value, str) or value not in OWNER_POLICY_DEFAULT_VALUES:
            raise ValueError(
                f"owner-policy default {field} must be one of "
                f"{sorted(OWNER_POLICY_DEFAULT_VALUES)}"
            )
    for section_name, values in lists.items():
        if not values:
            raise ValueError(
                f"owner-policy {section_name} must contain reviewed text"
            )
        if any(len(value) < 5 for value in values):
            raise ValueError(
                f"owner-policy {section_name} items must contain at least "
                "five characters"
            )
        if len(values) != len(set(values)):
            raise ValueError(
                f"owner-policy {section_name} items must be unique"
            )
    return {
        key: (
            str(value).lower()
            if isinstance(value, bool)
            else str(value)
        )
        for key, value in defaults.items()
    }


def finding_fingerprint(finding: dict[str, object]) -> str:
    """Bind an exception to the exact observed rule, location, and signal."""
    identity = {
        key: finding.get(key)
        for key in (
            "rule",
            "severity",
            "classification",
            "file",
            "line",
            "excerpt",
            "matched_signal",
            "matched_signals",
        )
    }
    encoded = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def bind_finding(finding: dict[str, object]) -> dict[str, object]:
    finding["fingerprint"] = finding_fingerprint(finding)
    return finding


def allowlist_entry(
    finding: dict[str, object],
    entries: list[dict[str, object]],
) -> Optional[dict[str, object]]:
    rule = str(finding["rule"])
    relative = str(finding["file"])
    line = int(finding["line"])
    fingerprint = str(finding["fingerprint"])
    for entry in entries:
        if entry["rule"] != rule:
            continue
        if not fnmatch.fnmatch(relative, str(entry["path"])):
            continue
        if (
            entry["fingerprint"] == fingerprint
            and ("line" not in entry or entry["line"] == line)
        ):
            return entry
    return None


def skipped_acknowledgement(
    relative: str,
    sha256: str,
    size_bytes: int,
    entries: list[dict[str, object]],
) -> Optional[dict[str, object]]:
    for entry in entries:
        if (
            fnmatch.fnmatchcase(relative, str(entry["path"]))
            and entry["sha256"] == sha256
            and entry["size_bytes"] == size_bytes
        ):
            return entry
    return None


def file_sha256_and_size(path: Path) -> tuple[str, int]:
    """Hash the exact bytes used to bind a skipped-source acknowledgement."""
    digest = hashlib.sha256()
    size_bytes = 0
    try:
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
                size_bytes += len(chunk)
    except OSError as exc:
        raise RuntimeError(f"file-read-failed: {path}: {exc}") from exc
    return digest.hexdigest(), size_bytes


def suppressed_finding(
    finding: dict[str, object],
    entry: dict[str, object],
) -> dict[str, object]:
    return {
        **finding,
        "suppression": {
            "source": "allowlist",
            "rule": entry["rule"],
            "path": entry["path"],
            "line": entry.get("line"),
            "fingerprint": entry["fingerprint"],
            "reason": entry["reason"],
            "owner": entry["owner"],
            "expires": entry["expires"],
        },
    }


def validate_include_patterns(patterns: list[str]) -> list[str]:
    validated: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        if (
            not pattern
            or pattern != pattern.strip()
            or "\\" in pattern
            or pattern.startswith("/")
            or re.match(r"^[A-Za-z]:", pattern)
            or ".." in pattern.split("/")
        ):
            raise ValueError(
                "--include values must be nonempty project-relative forward-slash globs"
            )
        if pattern not in seen:
            validated.append(pattern)
            seen.add(pattern)
    return validated


def matches_include(relative: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(relative, pattern) for pattern in patterns)


def default_content_excluded(
    relative: str,
    *,
    content_site: bool = False,
) -> bool:
    path = Path(relative)
    if any(
        part.casefold() in NON_DOCUMENTATION_CONTENT_EXCLUDED_DIRS_CASEFOLD
        for part in path.parts[:-1]
    ):
        return True
    if content_site:
        return any(
            fnmatch.fnmatchcase(path.name.casefold(), pattern)
            for pattern in DEFAULT_CONTENT_EXCLUDED_FILE_PATTERNS
        )
    if any(
        part.casefold() in DOCUMENTATION_CONTENT_DIRS_CASEFOLD
        for part in path.parts[:-1]
    ):
        return True
    if path.suffix.lower() in {".md", ".mdx"}:
        return True
    name = path.name.casefold()
    if name in DEFAULT_CONTENT_EXCLUDED_FILES:
        return True
    return any(
        fnmatch.fnmatchcase(name, pattern)
        for pattern in DEFAULT_CONTENT_EXCLUDED_FILE_PATTERNS
    )


def sensitive_structured_content(relative: str) -> bool:
    path = Path(relative)
    return (
        any(
            part.casefold() in SENSITIVE_STRUCTURED_DIRS_CASEFOLD
            for part in path.parts[:-1]
        )
        or bool(SENSITIVE_STRUCTURED_PART.search(path.name))
    )


def context_is_negative_or_example(text: str, start: int, end: int) -> bool:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    context = text[max(line_start, start - 180):min(line_end, end + 120)]
    return bool(NEGATIVE_OR_EXAMPLE_CONTEXT.search(context))


def skip_quoted_source(text: str, start: int) -> int:
    quote = text[start]
    index = start + 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == quote:
            return index + 1
        index += 1
    return len(text)


def skip_js_expression(text: str, start: int) -> int:
    depth = 0
    index = start
    while index < len(text):
        if text[index] in "\"'`":
            index = skip_quoted_source(text, index)
            continue
        if text.startswith("//", index):
            newline = text.find("\n", index + 2)
            index = len(text) if newline < 0 else newline + 1
            continue
        if text.startswith("/*", index):
            close = text.find("*/", index + 2)
            index = len(text) if close < 0 else close + 2
            continue
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return len(text)


def parse_markup_tag(
    text: str,
    start: int,
) -> Optional[tuple[int, str, str, bool]]:
    if text.startswith("</>", start):
        return start + 3, "close", "#fragment", False
    if text.startswith("<>", start):
        return start + 2, "open", "#fragment", False
    match = re.match(
        r"<\s*(?P<closing>/)?\s*(?P<name>[A-Za-z][A-Za-z0-9:._-]*)",
        text[start:],
    )
    if not match:
        return None
    kind = "close" if match.group("closing") else "open"
    name = match.group("name").casefold()
    index = start + match.end()
    while index < len(text):
        if text[index] in "\"'`":
            index = skip_quoted_source(text, index)
            continue
        if text[index] == "{":
            index = skip_js_expression(text, index)
            continue
        if text[index] == "<":
            return None
        if text[index] == ">":
            prefix = text[start:index].rstrip()
            self_closing = (
                kind == "open"
                and (prefix.endswith("/") or name in HTML_VOID_ELEMENTS)
            )
            return index + 1, kind, name, self_closing
        index += 1
    return None


def has_static_closing_tag(text: str, start: int, name: str) -> bool:
    if name == "#fragment":
        return text.find("</>", start) >= 0
    return bool(
        re.search(
            rf"</\s*{re.escape(name)}\s*>",
            text[start:],
            re.I,
        )
    )


def static_markup_text_records(
    text: str,
) -> list[tuple[int, int, tuple[str, ...]]]:
    records: list[tuple[int, int, tuple[str, ...]]] = []
    stack: list[str] = []
    index = 0
    while index < len(text):
        if stack:
            if stack[-1] in {"script", "style"}:
                close = re.search(
                    rf"</\s*{re.escape(stack[-1])}\s*>",
                    text[index:],
                    re.I,
                )
                if not close:
                    break
                if close.start() > 0:
                    index += close.start()
                    continue
            if text[index] == "<":
                tag = parse_markup_tag(text, index)
                if not tag:
                    index += 1
                    continue
                end, kind, name, self_closing = tag
                if kind == "open" and not self_closing:
                    stack.append(name)
                elif kind == "close":
                    for stack_index in range(len(stack) - 1, -1, -1):
                        if stack[stack_index] == name:
                            del stack[stack_index:]
                            break
                index = end
                continue
            if text[index] == "{":
                index = skip_js_expression(text, index)
                continue
            node_start = index
            while index < len(text) and text[index] not in "<{":
                index += 1
            if index > node_start:
                records.append((node_start, index, tuple(stack)))
            continue

        if text[index] in "\"'`":
            index = skip_quoted_source(text, index)
            continue
        if text.startswith("//", index):
            newline = text.find("\n", index + 2)
            index = len(text) if newline < 0 else newline + 1
            continue
        if text.startswith("/*", index):
            close = text.find("*/", index + 2)
            index = len(text) if close < 0 else close + 2
            continue
        if text[index] == "<":
            tag = parse_markup_tag(text, index)
            if tag:
                end, kind, name, self_closing = tag
                if (
                    kind == "open"
                    and not self_closing
                    and has_static_closing_tag(text, end, name)
                ):
                    stack.append(name)
                    index = end
                    continue
                if self_closing:
                    index = end
                    continue
        index += 1
    return records


def static_markup_text_nodes(text: str) -> list[tuple[int, int]]:
    return [
        (start, end)
        for start, end, _ in static_markup_text_records(text)
    ]


def static_container_ranges(
    text: str,
    container_name: str,
) -> list[tuple[int, int]]:
    """Return balanced literal container ranges without evaluating templates."""
    starts: list[int] = []
    ranges: list[tuple[int, int]] = []
    index = 0
    wanted = container_name.casefold()
    while index < len(text):
        start = text.find("<", index)
        if start < 0:
            break
        parsed = parse_markup_tag(text, start)
        if not parsed:
            index = start + 1
            continue
        end, kind, name, self_closing = parsed
        index = end
        if name != wanted:
            continue
        if kind == "open" and not self_closing:
            starts.append(start)
        elif kind == "close" and starts:
            ranges.append((starts.pop(), end))
    return sorted(ranges)


def section_index(
    ranges: list[tuple[int, int]],
    position: int,
) -> Optional[int]:
    containing = [
        (end - start, index)
        for index, (start, end) in enumerate(ranges)
        if start <= position < end
    ]
    return min(containing)[1] if containing else None


def static_markup_text_node(
    path: Path,
    text: str,
    start: int,
    end: int,
) -> Optional[tuple[int, int]]:
    if path.suffix.lower() not in STATIC_MARKUP_SUFFIXES:
        return None
    for node_start, node_end in static_markup_text_nodes(text):
        if node_start <= start and end <= node_end:
            return node_start, node_end
    return None


def sentence_is_negative(
    value: str,
    start: int,
    end: int,
    *,
    context_pattern: re.Pattern[str] = NEGATIVE_OR_EXAMPLE_CONTEXT,
) -> bool:
    sentence_start = 0
    for boundary in re.finditer(r"[.!?;]+[\"'”’)\]]*\s*", value[:start]):
        sentence_start = boundary.end()
    boundary = re.search(r"[.!?;]+", value[end:])
    sentence_end = len(value) if not boundary else end + boundary.end()
    sentence = html.unescape(value[sentence_start:sentence_end])
    return bool(context_pattern.search(sentence))


def enclosing_source_literal(
    text: str,
    start: int,
    end: int,
) -> Optional[tuple[int, int]]:
    for quote in ("\"", "'", "`"):
        search_start = 0 if quote == "`" else text.rfind("\n", 0, start) + 1
        search_end = len(text) if quote == "`" else text.find("\n", end)
        if search_end < 0:
            search_end = len(text)
        positions = []
        index = search_start
        while index < search_end:
            if text[index] == "\\":
                index += 2
                continue
            if text[index] == quote:
                positions.append(index)
            index += 1
        before = [position for position in positions if position < start]
        after = [position for position in positions if position >= end]
        if len(before) % 2 == 1 and after:
            return before[-1] + 1, after[0]
    return None


def classify_placeholder_proof(
    path: Path,
    text: str,
    start: int,
    end: int,
    matched_text: str,
) -> Optional[tuple[str, dict[str, object]]]:
    node = static_markup_text_node(path, text, start, end)
    if node:
        node_start, node_end = node
        if sentence_is_negative(
            text[node_start:node_end],
            start - node_start,
            end - node_start,
            context_pattern=FILLER_NEGATIVE_CONTEXT,
        ):
            return None
        return "gate", {
            "match": matched_text,
            "basis": "literal text in a supported renderable markup text node",
        }

    literal = enclosing_source_literal(text, start, end)
    if literal:
        literal_start, literal_end = literal
        if sentence_is_negative(
            text[literal_start:literal_end],
            start - literal_start,
            end - literal_start,
            context_pattern=FILLER_NEGATIVE_CONTEXT,
        ):
            return None
    return "advisory", {
        "match": matched_text,
        "basis": (
            "source occurrence is not a confirmed literal text node in a "
            "supported renderable markup format"
        ),
    }


def html_unescape_with_raw_offsets(
    value: str,
) -> tuple[str, list[int]]:
    """Decode semicolon-terminated entities while retaining raw source offsets."""
    decoded: list[str] = []
    raw_offsets: list[int] = []
    entity = re.compile(r"&(?:#[0-9]+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]+);")
    cursor = 0
    for match in entity.finditer(value):
        prefix = value[cursor:match.start()]
        decoded.append(prefix)
        raw_offsets.extend(range(cursor, match.start()))
        token = match.group(0)
        replacement = html.unescape(token)
        if replacement == token:
            decoded.append(token)
            raw_offsets.extend(range(match.start(), match.end()))
        else:
            decoded.append(replacement)
            raw_offsets.extend([match.start()] * len(replacement))
        cursor = match.end()
    suffix = value[cursor:]
    decoded.append(suffix)
    raw_offsets.extend(range(cursor, len(value)))
    return "".join(decoded), raw_offsets


def placeholder_proof_candidates(
    path: Path,
    relative: str,
    text: str,
    rule: Rule,
    owner_policy: Optional[str],
) -> list[dict[str, object]]:
    """Classify filler after decoding visible text, without trusting labels."""
    findings: list[dict[str, object]] = []
    node_ranges = (
        static_markup_text_records(text)
        if path.suffix.lower() in STATIC_MARKUP_SUFFIXES
        else []
    )
    for node_start, node_end, _stack in node_ranges:
        raw_node = text[node_start:node_end]
        decoded_node, offsets = html_unescape_with_raw_offsets(raw_node)
        for match in VISIBLE_FILLER.finditer(decoded_node):
            if sentence_is_negative(
                decoded_node,
                match.start(),
                match.end(),
                context_pattern=FILLER_NEGATIVE_CONTEXT,
            ):
                continue
            raw_start = (
                node_start + offsets[match.start()]
                if offsets and match.start() < len(offsets)
                else node_start
            )
            findings.append(bind_finding({
                "rule": rule.id,
                "severity": rule.severity,
                "classification": "gate",
                "file": relative,
                "line": line_number(text, raw_start),
                "excerpt": " ".join(match.group(0).split())[:160],
                "matched_signal": {
                    "match": match.group(0),
                    "basis": (
                        "HTML-decoded literal text in a supported renderable "
                        "markup text node"
                    ),
                },
                "rationale": rule.rationale,
                "suggestion": rule.suggestion,
                "owner_policy": owner_policy,
            }))

    for match in RAW_FILLER.finditer(text):
        if any(
            node_start <= match.start() and match.end() <= node_end
            for node_start, node_end, _stack in node_ranges
        ):
            continue
        classification = classify_placeholder_proof(
            path,
            text,
            match.start(),
            match.end(),
            html.unescape(match.group(0)),
        )
        if classification is None:
            continue
        finding_classification, matched_signal = classification
        findings.append(bind_finding({
            "rule": rule.id,
            "severity": rule.severity,
            "classification": finding_classification,
            "file": relative,
            "line": line_number(text, match.start()),
            "excerpt": " ".join(html.unescape(match.group(0)).split())[:160],
            "matched_signal": matched_signal,
            "rationale": rule.rationale,
            "suggestion": rule.suggestion,
            "owner_policy": owner_policy,
        }))
    return findings


def strip_markup(value: str) -> str:
    return " ".join(
        html.unescape(re.sub(r"<[^>]+>", " ", value)).split()
    )


def fragment_words(value: str) -> list[str]:
    return re.findall(r"[^\W_]+(?:['’\-][^\W_]+)*", value, flags=re.UNICODE)


def semantic_fragment(attrs: str, text: str, body_prefix: str) -> bool:
    normalized = " ".join(text.casefold().split())
    if normalized in SEMANTIC_STATUS_TEXT:
        return True
    if SEMANTIC_FRAGMENT.search(attrs):
        return True
    if re.search(r"\b(?:role|data-[A-Za-z0-9_-]*status)\s*=", attrs, re.I):
        return True
    return body_prefix.lower().rfind("<a") > body_prefix.lower().rfind("</a")


def line_number(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def foreground_css_classes(
    records: list[tuple[Path, str, str]],
) -> dict[str, list[dict[str, object]]]:
    classes: dict[str, list[dict[str, object]]] = {}
    rule_pattern = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)
    for path, relative, text in records:
        if path.suffix.lower() not in {".css", ".scss"}:
            continue
        for match in rule_pattern.finditer(text):
            selector, declarations = match.group(1), match.group(2)
            if not FOREGROUND_DECLARATION.search(";" + declarations):
                continue
            for class_name in set(
                re.findall(r"\.([A-Za-z_][A-Za-z0-9_-]*)", selector)
            ):
                classes.setdefault(class_name, []).append({
                    "file": relative,
                    "directory": path.parent,
                    "line": line_number(text, match.start()),
                    "signal": (
                        f".{class_name} resolves to a foreground color declaration "
                        f"in {relative}"
                    ),
                })
    return classes


def react_style_objects(
    records: list[tuple[Path, str, str]],
) -> dict[Path, dict[str, str]]:
    by_file: dict[Path, dict[str, str]] = {}
    outer = re.compile(
        r"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*"
        r"\{((?:[^{}]|\{[^{}]*\}){0,3000})\}",
        re.S,
    )
    inner = re.compile(
        r"([A-Za-z_$][A-Za-z0-9_$]*)\s*:\s*\{([^{}]*)\}",
        re.S,
    )
    color = re.compile(r"\b(?:color|WebkitTextFillColor)\s*:", re.I)
    for path, relative, text in records:
        if path.suffix.lower() not in {".astro", ".js", ".jsx", ".svelte", ".ts", ".tsx", ".vue"}:
            continue
        objects: dict[str, str] = {}
        for match in outer.finditer(text):
            name, body = match.group(1), match.group(2)
            if color.search(body) and not inner.search(body):
                objects[name] = f"{name} defines a foreground color in {relative}"
            for nested in inner.finditer(body):
                if color.search(nested.group(2)):
                    reference = f"{name}.{nested.group(1)}"
                    objects[reference] = (
                        f"{reference} defines a foreground color in {relative}"
                    )
        by_file[path] = objects
    return by_file


def literal_class_values(attrs: str) -> list[str]:
    values = [
        match.group(2)
        for match in re.finditer(
            r"\b(?:class|className)\s*=\s*([\"'`])([^\"'`]*?)\1",
            attrs,
            re.S,
        )
    ]
    values.extend(
        match.group(2)
        for match in re.finditer(
            r"\bclassName\s*=\s*\{\s*([\"'`])([^\"'`]*?)\1\s*\}",
            attrs,
            re.S,
        )
    )
    return values


def visible_prose_records(
    path: Path,
    text: str,
) -> list[dict[str, object]]:
    if path.suffix.lower() not in STATIC_MARKUP_SUFFIXES:
        return []
    excluded_ancestors = {"code", "head", "nav", "pre", "script", "style"}
    sections = static_container_ranges(text, "section")
    records: list[dict[str, object]] = []
    for start, end, ancestors in static_markup_text_records(text):
        if excluded_ancestors.intersection(ancestors):
            continue
        value = " ".join(html.unescape(text[start:end]).split())
        if not value:
            continue
        records.append({
            "start": start,
            "end": end,
            "line": line_number(text, start),
            "section": section_index(sections, start),
            "text": value,
        })
    return records


def quantitative_claim_candidates(
    records: list[tuple[Path, str, str]],
) -> list[dict[str, object]]:
    manual_review: list[dict[str, object]] = []
    for path, relative, text in records:
        prose = visible_prose_records(path, text)
        claims: list[dict[str, object]] = []
        for node in prose:
            for match in QUANTITATIVE_CLAIM.finditer(str(node["text"])):
                claims.append({
                    "line": node["line"],
                    "section": node["section"],
                    "value": match.group(0),
                })
        section_ids = {
            int(item["section"])
            for item in claims
            if item["section"] is not None
        }
        if len(claims) < 8 or len(section_ids) < 3:
            continue
        manual_review.append({
            "file": relative,
            "line": claims[0]["line"],
            "check": "quantitative-claim-density",
            "severity": "medium",
            "reason": (
                "Visible marketing copy contains a dense cluster of exact "
                "figures across multiple sections. Source scanning cannot "
                "establish whether those figures are approved facts."
            ),
            "evidence": {
                "claim_count": len(claims),
                "section_count": len(section_ids),
                "claims": claims[:16],
            },
            "suggestion": (
                "Trace each figure to approved project evidence, label it as "
                "illustrative, qualify it precisely, or remove it."
            ),
            "owner_policy": None,
        })
    return manual_review


def material_media_candidates(
    records: list[tuple[Path, str, str]],
) -> list[dict[str, object]]:
    manual_review: list[dict[str, object]] = []
    tag_pattern = re.compile(
        r"<(?P<tag>img|source|video|image)\b(?P<attrs>[^>]*)>",
        re.I | re.S,
    )
    reference_pattern = re.compile(
        r"\b(?:src|srcset|poster)\s*=\s*[\"'](?P<value>[^\"']+)",
        re.I,
    )
    for path, relative, text in records:
        references: list[dict[str, object]] = []
        if path.suffix.lower() in PROMINENT_MARKUP_SUFFIXES:
            for match in tag_pattern.finditer(text):
                attrs = match.group("attrs")
                if re.search(
                    r"\b(?:role\s*=\s*[\"']presentation[\"']|"
                    r"aria-hidden\s*=\s*[\"']true[\"']|alt\s*=\s*[\"']\s*[\"'])",
                    attrs,
                    re.I,
                ):
                    continue
                if re.search(r"\b(?:icon|logo|sprite)\b", attrs, re.I):
                    continue
                values = [
                    item.group("value")
                    for item in reference_pattern.finditer(attrs)
                ]
                if (
                    not values
                    and re.search(
                        r"\b(?:src|srcset|poster)\s*=",
                        attrs,
                        re.I,
                    )
                ):
                    values = ["<runtime-computed-media-reference>"]
                if not values:
                    continue
                references.append({
                    "line": line_number(text, match.start()),
                    "tag": match.group("tag").casefold(),
                    "references": values[:4],
                })
        elif path.suffix.lower() in {".css", ".scss"}:
            for match in re.finditer(
                r"background(?:-image)?\s*:[^;{}]{0,240}"
                r"url\(\s*[\"']?(?P<value>[^)\"']+)",
                text,
                re.I,
            ):
                value = match.group("value").strip()
                if value.casefold().startswith("data:"):
                    continue
                references.append({
                    "line": line_number(text, match.start()),
                    "tag": "css-background",
                    "references": [value],
                })
        if not references:
            continue
        generated = bool(GENERATED_MEDIA_MARKER.search(text))
        manual_review.append({
            "file": relative,
            "line": references[0]["line"],
            "check": (
                "generated-media-authenticity"
                if generated
                else "media-authenticity-and-provenance"
            ),
            "severity": "medium" if generated else "low",
            "reason": (
                "The source references content-bearing media"
                + (
                    " and explicitly identifies generated or synthetic media."
                    if generated
                    else "."
                )
                + " Static source scanning did not inspect the image pixels."
            ),
            "evidence": {
                "reference_count": len(references),
                "generated_or_synthetic_marker": generated,
                "references": references[:12],
            },
            "suggestion": (
                "Verify authorization, creator/source, license, consent where "
                "relevant, crop, caption, alt treatment, and factual context. "
                "Inspect rendered assets at full size for documentary detail, "
                "geometry, text, logos, hands, reflections, shadows, repeated "
                "artifacts, and over-uniform lighting, grading, palette, or framing."
            ),
            "owner_policy": None,
        })
    return manual_review


def typography_compression_candidates(
    records: list[tuple[Path, str, str]],
) -> list[dict[str, object]]:
    """Find clustered or severe legibility-reducing typography controls."""
    manual_review: list[dict[str, object]] = []
    display_selector = re.compile(
        r"(?:\bh[1-6]\b|(?:^|[-_.#\s])(?:display|headline|hero|poster|"
        r"title)(?:$|[-_:\s>+~.#]))",
        re.I,
    )
    reading_selector = re.compile(
        r"(?:\b(?:body|p|li|dd|dt|blockquote|article)\b|"
        r"(?:^|[-_.#\s])(?:body|copy|prose|paragraph|description|summary|"
        r"lede|intro)(?:$|[-_:\s>+~.#]))",
        re.I,
    )
    excluded_selector = re.compile(
        r"(?:sr[-_]?only|visually[-_]?hidden|screen[-_]?reader)",
        re.I,
    )
    letter_spacing = re.compile(
        r"\b(?:letter-spacing|letterSpacing)\s*:\s*[\"']?\s*"
        r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
        r"(?P<unit>em|rem|px)?\b",
        re.I,
    )
    line_height = re.compile(
        r"\b(?:line-height|lineHeight)\s*:\s*[\"']?\s*"
        r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
        r"(?P<unit>em|rem)?\b",
        re.I,
    )
    font_stretch = re.compile(
        r"\b(?:font-stretch|fontStretch)\s*:\s*[\"']?\s*"
        r"(?P<value>(?:\d+(?:\.\d*)?|\.\d+))%",
        re.I,
    )
    width_axis = re.compile(
        r"\b(?:font-variation-settings|fontVariationSettings)\s*:"
        r"[^;{}]{0,240}"
        r"[\"']wdth[\"']\s+"
        r"(?P<value>(?:\d+(?:\.\d*)?|\.\d+))",
        re.I,
    )
    horizontal_scale = re.compile(
        r"\bscaleX\s*\(\s*"
        r"(?P<value>(?:\d+(?:\.\d*)?|\.\d+))"
        r"(?P<unit>%?)\s*\)",
        re.I,
    )
    utility_tracking = re.compile(
        r"\btracking-\[\s*"
        r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
        r"(?P<unit>em|rem|px)\s*\]",
        re.I,
    )
    utility_leading = re.compile(
        r"\bleading-\[\s*"
        r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
        r"(?P<unit>em|rem)?\s*\]",
        re.I,
    )
    utility_stretch = re.compile(
        r"\[\s*font-stretch\s*:\s*"
        r"(?P<value>(?:\d+(?:\.\d*)?|\.\d+))%\s*\]",
        re.I,
    )
    utility_width_axis = re.compile(
        r"\[\s*font-variation-settings\s*:[^\]]{0,180}?"
        r"[\"']?wdth[\"']?(?:_|[\s:])+"
        r"(?P<value>(?:\d+(?:\.\d*)?|\.\d+))[^\]]*\]",
        re.I,
    )
    utility_scale = re.compile(
        r"\bscale-x-(?:\[\s*)?"
        r"(?P<value>(?:\d+(?:\.\d*)?|\.\d+))"
        r"(?P<closing>\s*\])?",
        re.I,
    )

    def signals_for(source: str, role: str) -> list[dict[str, object]]:
        signals: list[dict[str, object]] = []
        reading = role == "reading"

        spacing = letter_spacing.search(source) or utility_tracking.search(source)
        if spacing:
            value = float(spacing.group("value"))
            unit = (spacing.group("unit") or "").casefold()
            threshold = -0.02 if reading else -0.03
            pixel_threshold = -0.35 if reading else -0.5
            if (
                unit in {"em", "rem"} and value <= threshold
            ) or (
                unit == "px" and value <= pixel_threshold
            ):
                extreme = (
                    value <= (-0.04 if reading else -0.07)
                    if unit in {"em", "rem"}
                    else value <= (-0.75 if reading else -1.0)
                )
                signals.append({
                    "property": "letter-spacing",
                    "value": f"{value:g}{unit}",
                    "extreme": extreme,
                })

        leading = line_height.search(source) or utility_leading.search(source)
        if leading:
            value = float(leading.group("value"))
            unit = (leading.group("unit") or "").casefold()
            threshold = 1.35 if reading else 0.95
            if unit in {"", "em"} and value < threshold:
                signals.append({
                    "property": "line-height",
                    "value": f"{value:g}{unit}",
                    "extreme": value < (1.2 if reading else 0.8),
                })

        stretch = font_stretch.search(source) or utility_stretch.search(source)
        if stretch:
            value = float(stretch.group("value"))
            if value < 90:
                signals.append({
                    "property": "font-stretch",
                    "value": f"{value:g}%",
                    "extreme": value <= (80 if reading else 75),
                })

        width = width_axis.search(source) or utility_width_axis.search(source)
        if width:
            value = float(width.group("value"))
            if value < 90:
                signals.append({
                    "property": "wdth-axis",
                    "value": f"{value:g}",
                    "extreme": value <= (80 if reading else 75),
                })

        scale = horizontal_scale.search(source) or utility_scale.search(source)
        if scale:
            value = float(scale.group("value"))
            unit = (
                (scale.groupdict().get("unit") or "")
                if "unit" in scale.groupdict()
                else ""
            )
            if utility_scale.fullmatch(scale.group(0)) or "scale-x-" in scale.group(0):
                normalized = value / 100 if value > 2 else value
            else:
                normalized = value / 100 if unit == "%" else value
            if normalized < 0.9:
                signals.append({
                    "property": "horizontal-scale",
                    "value": f"{normalized:g}",
                    "extreme": normalized <= (0.8 if reading else 0.75),
                })
        return signals

    def append_review(
        *,
        relative: str,
        line: int,
        subject: str,
        role: str,
        signals: list[dict[str, object]],
    ) -> None:
        severe = any(bool(item.get("extreme")) for item in signals)
        compound_display = role == "display" and len(signals) >= 2
        compound_reading = role == "reading" and len(signals) >= 2
        if not (severe or compound_display or compound_reading):
            return
        check = (
            "compound-display-compression"
            if compound_display
            else "severe-typography-compression"
        )
        reason = (
            "A prominent text treatment stacks at least two compression "
            "controls. Tight tracking, narrow width, horizontal scaling, and "
            "short leading can crowd real headings."
            if compound_display
            else (
                "Reading text combines multiple crowding controls or uses an "
                "extreme single control. Body copy, labels, and controls need "
                "a larger comfort margin than a limited display treatment."
                if role == "reading"
                else (
                    "A prominent text treatment uses an extreme single "
                    "compression control. Even without a second trigger, this "
                    "can make words touch or become difficult to parse."
                )
            )
        )
        manual_review.append({
            "file": relative,
            "line": line,
            "check": check,
            "severity": "medium",
            "reason": reason,
            "evidence": {
                "subject": subject[:240],
                "role": role,
                "signals": signals,
                "basis": (
                    "display review triggers: tracking <= -0.03em or -0.5px, "
                    "line-height < 0.95, stretch or wdth < 90; severe single "
                    "triggers: tracking <= -0.07em, line-height < 0.8, "
                    "stretch or wdth <= 75, or horizontal scale <= 0.75; "
                    "reading roles use stricter comfort thresholds"
                ),
            },
            "suggestion": (
                "Proof the actual words at narrow, intermediate, and wide "
                "sizes. Adjust the combination that causes crowding; compressed "
                "display typography remains available when the actual words stay "
                "legible, intentional, and resilient under content and viewport change."
            ),
            "owner_policy": None,
        })

    for path, relative, text in records:
        suffix = path.suffix.lower()
        if suffix not in {".css", ".less", ".scss"}:
            continue
        for block in CSS_DECLARATION_BLOCK.finditer(text):
            selector = " ".join(block.group("header").split())
            body = block.group("body")
            if (
                not selector
                or selector.startswith("@")
                or excluded_selector.search(selector)
            ):
                continue
            role = (
                "display"
                if display_selector.search(selector)
                else "reading"
                if reading_selector.search(selector)
                else ""
            )
            if not role:
                continue
            append_review(
                relative=relative,
                line=line_number(text, block.start()),
                subject=selector,
                role=role,
                signals=signals_for(body, role),
            )

    element = re.compile(
        r"<(?P<tag>body|article|blockquote|dd|div|dt|h[1-6]|li|p|section|"
        r"span)\b(?P<attrs>[^>]*)>",
        re.I | re.S,
    )
    for path, relative, text in records:
        if path.suffix.lower() not in PROMINENT_MARKUP_SUFFIXES:
            continue
        for match in element.finditer(text):
            attrs = match.group("attrs")
            if excluded_selector.search(attrs):
                continue
            tag = match.group("tag").casefold()
            role = (
                "display"
                if tag in {f"h{level}" for level in range(1, 7)}
                or display_selector.search(attrs)
                else "reading"
                if tag in {
                    "body", "article", "blockquote", "dd", "dt", "li", "p",
                }
                or reading_selector.search(attrs)
                else ""
            )
            if not role:
                continue
            signals = signals_for(attrs, role)
            if not signals:
                continue
            append_review(
                relative=relative,
                line=line_number(text, match.start()),
                subject=f"<{tag}> inline or utility treatment",
                role=role,
                signals=signals,
            )
    return manual_review


def public_meta_copy_candidates(
    records: list[tuple[Path, str, str]],
) -> list[dict[str, object]]:
    """Surface explicit internal-method language in public prose for review."""
    manual_review: list[dict[str, object]] = []
    for path, relative, text in records:
        prose = visible_prose_records(path, text)
        if not prose:
            continue
        matches: list[dict[str, object]] = []
        for node in prose:
            for match in PUBLIC_META_COPY_MARKER.finditer(str(node["text"])):
                matches.append({
                    "line": node["line"],
                    "section": node["section"],
                    "value": match.group(0),
                })
        sections = {
            item["section"]
            for item in matches
            if item["section"] is not None
        }
        if not matches:
            continue
        manual_review.append({
            "file": relative,
            "line": matches[0]["line"],
            "check": "public-meta-copy-contamination",
            "severity": "medium",
            "reason": (
                "Public-facing prose contains language that appears to describe "
                "an internal design method, unresolved input, or production "
                "state. Static source scanning cannot decide whether the "
                "project intentionally exposes that information."
            ),
            "evidence": {
                "match_count": len(matches),
                "section_count": len(sections),
                "examples": matches[:12],
            },
            "suggestion": (
                "Review the phrase against the project's public-copy boundary. "
                "Keep every disclosure or limitation the audience actually "
                "needs; move internal methodology and unresolved-input logs to "
                "project records. Do not target a universal disclosure count."
            ),
            "owner_policy": None,
        })
    return manual_review


def nonfunctional_concept_affordance_candidates(
    records: list[tuple[Path, str, str]],
) -> list[dict[str, object]]:
    manual_review: list[dict[str, object]] = []
    button = re.compile(
        r"<button\b(?P<attrs>[^>]*)>(?P<body>.*?)</button>",
        re.I | re.S,
    )
    for path, relative, text in records:
        if path.suffix.lower() not in STATIC_MARKUP_SUFFIXES:
            continue
        candidates: list[dict[str, object]] = []
        for match in button.finditer(text):
            if not re.search(r"\bdisabled\b", match.group("attrs"), re.I):
                continue
            label = " ".join(
                re.sub(r"<[^>]+>", " ", match.group("body")).split()
            )
            if not re.search(
                r"\b(?:concept|demo|not\s+connected|unavailable|"
                r"not\s+available|coming\s+soon)\b",
                label,
                re.I,
            ):
                continue
            candidates.append({
                "line": line_number(text, match.start()),
                "label": label[:160],
            })
        if not candidates:
            continue
        manual_review.append({
            "file": relative,
            "line": candidates[0]["line"],
            "check": "nonfunctional-concept-affordance",
            "severity": "medium",
            "reason": (
                "The public route presents a disabled concept or unavailable "
                "control. Honesty prevents a false action, but the affordance "
                "may still advertise a feature the visitor cannot use."
            ),
            "evidence": {"controls": candidates[:12]},
            "suggestion": (
                "Remove the control unless its unavailable state is necessary "
                "to the real task; otherwise replace it with a meaningful "
                "working route or plain explanatory text."
            ),
            "owner_policy": None,
        })
    return manual_review


def resolve_css_class(
    class_name: str,
    path: Path,
    classes: dict[str, list[dict[str, object]]],
) -> Optional[str]:
    candidates = classes.get(class_name, [])
    local = [
        item for item in candidates
        if item.get("directory") == path.parent
    ]
    selected = local if local else candidates if len(candidates) == 1 else []
    if not selected:
        return None
    return str(selected[0]["signal"])


def fragment_style_signal(
    attrs: str,
    path: Path,
    css_classes: dict[str, list[dict[str, object]]],
    style_objects: dict[Path, dict[str, str]],
) -> tuple[Optional[str], bool]:
    if re.search(
        r"\bstyle\s*=\s*(?:[\"'][^\"']*(?:color|-webkit-text-fill-color)\s*:|"
        r"\{\{[^{}]*(?:color|WebkitTextFillColor)\s*:)",
        attrs,
        re.I | re.S,
    ):
        return "inline foreground-color declaration", False

    class_values = literal_class_values(attrs)
    for value in class_values:
        tailwind = TAILWIND_FOREGROUND.search(" " + value)
        if tailwind:
            return f"Tailwind foreground utility {tailwind.group(0).strip()}", False
        for token in value.split():
            bare = token.rsplit(":", 1)[-1]
            resolved = resolve_css_class(bare, path, css_classes)
            if resolved:
                return resolved, False

    module_refs = re.findall(
        r"\bclassName\s*=\s*\{[^{}]{0,300}?"
        r"([A-Za-z_$][A-Za-z0-9_$]*)\.([A-Za-z_$][A-Za-z0-9_$]*)",
        attrs,
        re.S,
    )
    for _namespace, class_name in module_refs:
        resolved = resolve_css_class(class_name, path, css_classes)
        if resolved:
            return f"CSS Module reference resolves indirectly: {resolved}", False

    direct_tailwind = TAILWIND_FOREGROUND.search(" " + attrs)
    if direct_tailwind:
        return f"Tailwind foreground utility {direct_tailwind.group(0).strip()}", False

    style_reference = re.search(
        r"\bstyle\s*=\s*\{\s*([A-Za-z_$][A-Za-z0-9_$]*"
        r"(?:\.[A-Za-z_$][A-Za-z0-9_$]*)?)\s*\}",
        attrs,
    )
    if style_reference:
        reference = style_reference.group(1)
        signal = style_objects.get(path, {}).get(reference)
        if signal:
            return f"React style reference resolves indirectly: {signal}", False

    dynamic = bool(
        re.search(r"\b(?:className|style)\s*=\s*\{", attrs)
    )
    return None, dynamic


def prominent_fragment_candidates(
    records: list[tuple[Path, str, str]],
    css_classes: dict[str, list[dict[str, object]]],
    style_objects: dict[Path, dict[str, str]],
) -> list[dict[str, object]]:
    """Surface prominent styled fragments without treating them as defects."""
    manual_review: list[dict[str, object]] = []
    block_pattern = re.compile(
        r"<(?P<tag>h[1-6]|div|p|strong)\b(?P<attrs>[^>]*)>"
        r"(?P<body>.*?)</(?P=tag)\s*>",
        re.I | re.S,
    )
    fragment_pattern = re.compile(
        r"<(?P<tag>span|em)\b(?P<attrs>[^>]*)>"
        r"(?P<body>.*?)</(?P=tag)\s*>",
        re.I | re.S,
    )
    for path, relative, text in records:
        if path.suffix.lower() not in PROMINENT_MARKUP_SUFFIXES:
            continue
        for block in block_pattern.finditer(text):
            tag = block.group("tag").casefold()
            if not tag.startswith("h") and not PROMINENT_CLASS.search(
                block.group("attrs")
            ):
                continue
            body = block.group("body")
            for fragment in fragment_pattern.finditer(body):
                plain = strip_markup(fragment.group("body"))
                words = fragment_words(plain)
                if not words or len(words) > 2:
                    continue
                prefix = body[:fragment.start()]
                attrs = fragment.group("attrs")
                if semantic_fragment(attrs, plain, prefix):
                    continue
                signal, unresolved = fragment_style_signal(
                    attrs, path, css_classes, style_objects
                )
                absolute_start = block.start("body") + fragment.start()
                line = line_number(text, absolute_start)
                if signal:
                    manual_review.append({
                        "file": relative,
                        "line": line,
                        "check": "prominent-fragment-context",
                        "severity": "low",
                        "fragment": plain[:80],
                        "evidence": {
                            "element": tag,
                            "style_signal": signal,
                            "basis": (
                                "static source identifies a foreground-style "
                                "change inside prominent copy"
                            ),
                        },
                        "reason": (
                            "A styled prominent fragment is a neutral expressive "
                            "ingredient. Its presence, repetition, and word count "
                            "do not establish visual harm or generated authorship."
                        ),
                        "suggestion": (
                            "Review the rendered meaning, hierarchy, legibility, "
                            "and declared project concerns. Keep it when it serves "
                            "the composition; do not revise it because of a count."
                        ),
                        "owner_policy": None,
                    })
                elif unresolved:
                    manual_review.append({
                        "file": relative,
                        "line": line,
                        "check": "prominent-fragment-dynamic-style",
                        "severity": "low",
                        "fragment": plain[:80],
                        "reason": (
                            "A prominent fragment uses a runtime-computed class or "
                            "style that static scanning cannot resolve. The source "
                            "does not establish visual harm."
                        ),
                        "suggestion": (
                            "Inspect the rendered fragment only if it intersects a "
                            "declared project concern; never infer a defect from its "
                            "presence or frequency alone."
                        ),
                        "owner_policy": None,
                    })

    selector_rule = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)
    for path, relative, text in records:
        if path.suffix.lower() not in {".css", ".scss"}:
            continue
        for match in selector_rule.finditer(text):
            selector, declarations = match.group(1), match.group(2)
            if (
                not PROMINENT_CLASS.search(selector)
                or not re.search(r"(?:span|em|:nth-child\()", selector, re.I)
                or SEMANTIC_FRAGMENT.search(selector)
                or not FOREGROUND_DECLARATION.search(";" + declarations)
            ):
                continue
            manual_review.append({
                "file": relative,
                "line": line_number(text, match.start()),
                "check": "prominent-fragment-selector-context",
                "severity": "low",
                "selector": " ".join(selector.split())[:160],
                "reason": (
                    "A prominent descendant selector changes foreground color, "
                    "but source alone cannot establish fragment length, frequency, "
                    "meaning, or visual harm."
                ),
                "suggestion": (
                    "Review the rendered selector only in project context; do not "
                    "treat its presence or count as an automatic finding."
                ),
                "owner_policy": None,
            })
    return manual_review


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Runtime requirement: Python 3.10+. By default, docs, references, tests, "
            "stories, and fixture sources are omitted; use --include to opt specific "
            "paths in or --content-site to scan documentation content. "
            "High gate findings fail by default; use --advisory-exit-zero or "
            "--fail-on none only when a zero-exit advisory run is intentional. "
            "--fail-on applies only to conservative gate findings, never advisories. "
            "If a relevant source cannot be decoded or exceeds 5 MiB, --fail-on "
            "fails closed; an owner acknowledgement records separate review but "
            "never turns incomplete source coverage into a pass. "
            "Coverage is bounded to the listed common web-source suffixes; "
            "runtime-generated or dynamically rendered output still needs manual review."
        ),
    )
    parser.add_argument("project", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument(
        "--allowlist",
        type=Path,
        help=(
            "JSON allowlist; defaults to .design-dna/scan-allowlist.json when "
            "present. Rule suppressions require an exact rule, path, finding "
            "fingerprint, reason, owner, and expiry. The same file can explicitly "
            "acknowledge skipped source paths using the exact SHA-256 digest and size."
        ),
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="GLOB",
        help=(
            "Override default content exclusions for a project-relative "
            "forward-slash glob (repeatable); normal source remains included."
        ),
    )
    parser.add_argument(
        "--content-site",
        "--scan-documentation",
        dest="content_site",
        action="store_true",
        help=(
            "Scan documentation/content sources such as README, Markdown, MDX, "
            "docs, documentation, and reference trees. Tests, stories, fixtures, "
            "dependencies, generated output, and vendor trees remain excluded "
            "unless an existing --include override applies where supported."
        ),
    )
    parser.add_argument(
        "--built-output",
        action="store_true",
        help=(
            "Include recognized build-output trees (.next, .nuxt, .output, "
            ".svelte-kit, build, and dist) in addition to normal source. "
            "Dependency, vendor, coverage, metadata, and VCS trees remain excluded."
        ),
    )
    parser.add_argument(
        "--structured-content",
        action="store_true",
        help=(
            "Opt in JSON, YAML, and YML content. Sensitive config/credential "
            "names remain excluded unless a reviewed --include glob selects them; "
            "dependency and vendor trees are never scanned."
        ),
    )
    parser.add_argument(
        "--print-allowlist-example",
        action="store_true",
        help=(
            "Print a non-usable template plus the exact fingerprint workflow and "
            f"a fresh expiry {EXAMPLE_ALLOWLIST_LIFETIME_DAYS} days from today."
        ),
    )
    parser.add_argument(
        "--emit-allowlist-entry",
        metavar="FINGERPRINT",
        help=(
            "Emit a schema-valid allowlist document for one actual overridable "
            "finding fingerprint."
        ),
    )
    parser.add_argument("--allowlist-entry-owner")
    parser.add_argument("--allowlist-entry-reason")
    parser.add_argument(
        "--allowlist-entry-days",
        type=int,
        default=EXAMPLE_ALLOWLIST_LIFETIME_DAYS,
        help="Exception lifetime from 1 through 90 days (default: 30).",
    )
    parser.add_argument(
        "--owner-policy",
        type=Path,
        help=(
            "Owner policy; defaults to PROJECT/.design-dna/owner-policy.yml "
            "when present, otherwise the publisher policy bundled with this skill."
        ),
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--fail-on",
        choices=("none", "high", "medium", "low"),
        default=None,
        help=(
            "Exit 1 only for gate-safe findings at or above this severity; "
            "advisory candidates never fail the command (default: high)."
        ),
    )
    parser.add_argument(
        "--advisory-exit-zero",
        action="store_true",
        help=(
            "Explicitly keep exit 0 for quality findings; equivalent to "
            "--fail-on none, while JSON still reports quality failure."
        ),
    )
    args = parser.parse_args()
    if args.advisory_exit_zero and args.fail_on is not None:
        parser.error("--advisory-exit-zero and --fail-on are mutually exclusive")
    requested_fail_on = args.fail_on
    args.fail_on = (
        args.fail_on
        if args.fail_on is not None
        else "none"
        if args.advisory_exit_zero
        else "high"
    )
    if args.print_allowlist_example:
        template = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "scan-allowlist.example.json"
        )
        try:
            payload = strict_json(template.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("allowlist example must be a JSON object")
            fresh_expiry = (
                date.today() + timedelta(days=EXAMPLE_ALLOWLIST_LIFETIME_DAYS)
            ).isoformat()
            for collection in ("allow", "acknowledge_skipped"):
                entries = payload.get(collection)
                if not isinstance(entries, list):
                    raise ValueError(
                        f"allowlist example {collection} must be a list"
                    )
                for entry in entries:
                    if not isinstance(entry, dict):
                        raise ValueError(
                            f"allowlist example {collection} entry must be an object"
                        )
                    entry["expires"] = fresh_expiry
            allow_entries = payload.get("allow")
            if isinstance(allow_entries, list):
                for entry in allow_entries:
                    if isinstance(entry, dict):
                        entry["fingerprint"] = (
                            "REPLACE_WITH_FINGERPRINT_FROM_SCANNER_OUTPUT"
                        )
            printed = {
                "usable": False,
                "workflow": [
                    "Run scan_project.py PROJECT --json and inspect an overridable finding.",
                    (
                        "Pass its fingerprint to --emit-allowlist-entry with "
                        "--allowlist-entry-owner and --allowlist-entry-reason."
                    ),
                    "Review the emitted scoped entry before merging it into the project allowlist.",
                ],
                "template": payload,
            }
            print(json.dumps(printed, indent=2, ensure_ascii=False))
            return 0
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(
                json.dumps({
                    "ok": False,
                    "error": {
                        "code": "allowlist-example-unavailable",
                        "message": str(exc),
                    },
                }),
                file=sys.stderr,
            )
            return 2
    root = Path(os.path.abspath(os.fspath(args.project.expanduser())))
    try:
        if not root.is_dir() or is_reparse(root):
            print(json.dumps({
                "schema_version": SCAN_RESULT_SCHEMA_VERSION,
                "artifact_type": SCAN_RESULT_ARTIFACT_TYPE,
                "ok": False,
                "execution_ok": False,
                "execution": {"status": "failed", "ok": False},
                "error": {"code": "unsafe-project", "path": str(root)},
            }), file=sys.stderr)
            return 2
        if args.emit_allowlist_entry:
            if not FINGERPRINT_PATTERN.fullmatch(args.emit_allowlist_entry):
                raise ValueError(
                    "--emit-allowlist-entry requires a lowercase SHA-256 fingerprint"
                )
            if (
                not isinstance(args.allowlist_entry_owner, str)
                or not args.allowlist_entry_owner.strip()
            ):
                raise ValueError(
                    "--emit-allowlist-entry requires --allowlist-entry-owner"
                )
            if (
                not isinstance(args.allowlist_entry_reason, str)
                or len(args.allowlist_entry_reason.strip()) < 5
            ):
                raise ValueError(
                    "--emit-allowlist-entry requires "
                    "--allowlist-entry-reason with at least five characters"
                )
        elif (
            args.allowlist_entry_owner is not None
            or args.allowlist_entry_reason is not None
        ):
            raise ValueError(
                "allowlist entry owner/reason require --emit-allowlist-entry"
            )
        if not 1 <= args.allowlist_entry_days <= 90:
            raise ValueError("--allowlist-entry-days must be from 1 through 90")
        include_patterns = validate_include_patterns(args.include)
        allowlist_path = args.allowlist or (
            root / ".design-dna" / "scan-allowlist.json"
        )
        if not allowlist_path.is_absolute():
            allowlist_path = root / allowlist_path
        skill_root = Path(__file__).resolve().parents[1]
        rules = RULES
        (
            entries,
            expired_entries,
            skipped_acknowledgements,
            expired_skipped_acknowledgements,
        ) = load_allowlist(
            allowlist_path if args.allowlist or allowlist_path.is_file() else None,
            project=root,
            known_rules={rule.id for rule in rules},
            non_overridable_rules=NON_OVERRIDABLE_RULES,
        )
        project_owner_policy = root / ".design-dna" / "owner-policy.yml"
        owner_policy_path = args.owner_policy or (
            project_owner_policy
            if project_owner_policy.is_file()
            else (
                Path(__file__).resolve().parents[1]
                / "policy"
                / "owner-defaults.yml"
            )
        )
        if not owner_policy_path.is_absolute() and args.owner_policy is not None:
            owner_policy_path = root / owner_policy_path
        owner_policy_path = Path(
            os.path.abspath(os.fspath(owner_policy_path.expanduser()))
        )
        policy = load_owner_policy(owner_policy_path)
        rule_policy_key = {
            "deferred-content-visibility": "semantic_implementation",
            "placeholder-proof": "release_residue",
            "claim-needs-provenance": "truth_and_claims",
            "quantitative-claim-density": "truth_and_claims",
            "generated-media-authenticity": "generated_concept_media",
            "media-authenticity-and-provenance": "truth_and_claims",
            "compound-display-compression": "typography_comfort",
            "severe-typography-compression": "typography_comfort",
            "public-meta-copy-contamination": "public_copy_boundary",
            "nonfunctional-concept-affordance": "working_controls",
            "prominent-fragment-context": "content_hierarchy",
            "prominent-fragment-dynamic-style": "content_hierarchy",
            "prominent-fragment-selector-context": "content_hierarchy",
        }
        findings: list[dict[str, object]] = []
        suppressed_findings: list[dict[str, object]] = []
        pending: dict[str, list[dict[str, object]]] = {rule.id: [] for rule in rules}
        placeholder_rule = next(
            rule for rule in rules if rule.id == "placeholder-proof"
        )
        records: list[tuple[Path, str, str]] = []
        skipped_files: list[str] = []
        skipped_oversized_files: list[str] = []
        skipped_sources: list[dict[str, object]] = []
        excluded_default_files: list[str] = []
        excluded_sensitive_structured_files: list[str] = []
        eligible_file_count = 0
        scan_suffixes = set(TEXT_SUFFIXES)
        if args.structured_content:
            scan_suffixes.update(STRUCTURED_CONTENT_SUFFIXES)
        for path in iter_files(
            root,
            scan_suffixes,
            include_built_output=args.built_output,
        ):
            eligible_file_count += 1
            relative = path.relative_to(root).as_posix()
            if (
                path.suffix.lower() in STRUCTURED_CONTENT_SUFFIXES
                and sensitive_structured_content(relative)
                and not matches_include(relative, include_patterns)
            ):
                excluded_sensitive_structured_files.append(relative)
                continue
            if (
                default_content_excluded(
                    relative,
                    content_site=args.content_site,
                )
                and not matches_include(relative, include_patterns)
            ):
                excluded_default_files.append(relative)
                continue
            try:
                measured_size = path.stat().st_size
                if measured_size > MAX_TEXT_FILE_BYTES:
                    source_sha256, source_size = file_sha256_and_size(path)
                    skipped_oversized_files.append(relative)
                    acknowledgement = skipped_acknowledgement(
                        relative,
                        source_sha256,
                        source_size,
                        skipped_acknowledgements,
                    )
                    skipped_sources.append({
                        "file": relative,
                        "reason": "source exceeds the 5 MiB scanner limit",
                        "sha256": source_sha256,
                        "size_bytes": source_size,
                        "acknowledged": acknowledgement is not None,
                        "acknowledgement": acknowledgement,
                    })
                    continue
                source_bytes = path.read_bytes()
                if len(source_bytes) > MAX_TEXT_FILE_BYTES:
                    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
                    source_size = len(source_bytes)
                    skipped_oversized_files.append(relative)
                    acknowledgement = skipped_acknowledgement(
                        relative,
                        source_sha256,
                        source_size,
                        skipped_acknowledgements,
                    )
                    skipped_sources.append({
                        "file": relative,
                        "reason": "source exceeds the 5 MiB scanner limit",
                        "sha256": source_sha256,
                        "size_bytes": source_size,
                        "acknowledged": acknowledgement is not None,
                        "acknowledgement": acknowledgement,
                    })
                    continue
                text = source_bytes.decode("utf-8")
            except UnicodeError:
                source_sha256 = hashlib.sha256(source_bytes).hexdigest()
                source_size = len(source_bytes)
                skipped_files.append(relative)
                acknowledgement = skipped_acknowledgement(
                    relative,
                    source_sha256,
                    source_size,
                    skipped_acknowledgements,
                )
                skipped_sources.append({
                    "file": relative,
                    "reason": "source is not valid UTF-8",
                    "sha256": source_sha256,
                    "size_bytes": source_size,
                    "acknowledged": acknowledgement is not None,
                    "acknowledgement": acknowledgement,
                })
                continue
            except OSError as exc:
                raise RuntimeError(f"file-read-failed: {path}: {exc}") from exc
            scan_text = without_comments(text)
            records.append((path, relative, scan_text))
            pending[placeholder_rule.id].extend(
                placeholder_proof_candidates(
                    path,
                    relative,
                    scan_text,
                    placeholder_rule,
                    policy.get(
                        rule_policy_key.get(placeholder_rule.id, ""),
                        "",
                    ) or None,
                )
            )
            for rule in rules:
                if rule.pattern is None or rule.id == placeholder_rule.id:
                    continue
                for match in rule.pattern.finditer(scan_text):
                    line = line_number(scan_text, match.start())
                    policy_value = policy.get(rule_policy_key.get(rule.id, ""), "")
                    excerpt = " ".join(match.group(0).split())[:160]
                    classification = rule.classification
                    matched_signal: object = match.group(0)
                    finding = bind_finding({
                        "rule": rule.id,
                        "severity": rule.severity,
                        "classification": classification,
                        "file": relative,
                        "line": line,
                        "excerpt": excerpt,
                        "matched_signal": matched_signal,
                        "rationale": rule.rationale,
                        "suggestion": rule.suggestion,
                        "owner_policy": policy_value or None,
                    })
                    pending[rule.id].append(finding)
        for rule in rules:
            matches = pending[rule.id]
            eligible_matches = (
                matches
                if len(matches) >= rule.min_occurrences
                else []
            )
            for finding in eligible_matches:
                suppression = allowlist_entry(finding, entries)
                if suppression:
                    suppressed_findings.append(
                        suppressed_finding(finding, suppression)
                    )
                    continue
                findings.append(finding)
        css_classes = foreground_css_classes(records)
        style_objects = react_style_objects(records)
        manual_review = prominent_fragment_candidates(
            records, css_classes, style_objects
        )
        quantitative_review = quantitative_claim_candidates(records)
        media_review = material_media_candidates(records)
        compression_review = typography_compression_candidates(records)
        manual_review.extend(quantitative_review)
        manual_review.extend(media_review)
        manual_review.extend(compression_review)
        manual_review.extend(public_meta_copy_candidates(records))
        manual_review.extend(
            nonfunctional_concept_affordance_candidates(records)
        )
        for item in manual_review:
            check = str(item.get("check", ""))
            policy_value = policy.get(rule_policy_key.get(check, ""), "")
            if policy_value:
                item["owner_policy"] = policy_value
        manual_review.sort(
            key=lambda item: (
                str(item["file"]),
                int(item["line"]),
                str(item["check"]),
            )
        )
        findings.sort(key=lambda item: (str(item["file"]), int(item["line"]), str(item["rule"])))
        suppressed_findings.sort(
            key=lambda item: (
                str(item["file"]),
                int(item["line"]),
                str(item["rule"]),
            )
        )
        if args.emit_allowlist_entry:
            matched = [
                finding
                for finding in findings
                if finding.get("fingerprint") == args.emit_allowlist_entry
            ]
            if len(matched) != 1:
                raise ValueError(
                    "--emit-allowlist-entry fingerprint must match exactly one "
                    "current unsuppressed finding"
                )
            target = matched[0]
            if target.get("rule") in NON_OVERRIDABLE_RULES:
                raise ValueError(
                    "cannot emit an exception for a non-overridable truth rule"
                )
            emitted_entry = {
                "rule": target["rule"],
                "path": target["file"],
                "line": target["line"],
                "fingerprint": target["fingerprint"],
                "reason": args.allowlist_entry_reason.strip(),
                "owner": args.allowlist_entry_owner.strip(),
                "expires": (
                    date.today() + timedelta(days=args.allowlist_entry_days)
                ).isoformat(),
            }
            print(json.dumps({
                "schema_version": 1,
                "allow": [emitted_entry],
                "acknowledge_skipped": [],
            }, indent=2, ensure_ascii=False))
            return 0
        unacknowledged_skipped_files = [
            str(item["file"])
            for item in skipped_sources
            if not item["acknowledged"]
        ]
        acknowledged_skipped_files = [
            str(item["file"])
            for item in skipped_sources
            if item["acknowledged"]
        ]
        allowlist_suppression_counts = []
        for entry in entries:
            count = sum(
                item["suppression"]["rule"] == entry["rule"]
                and item["suppression"]["path"] == entry["path"]
                and item["suppression"]["line"] == entry.get("line")
                and item["suppression"]["fingerprint"] == entry["fingerprint"]
                and item["suppression"]["owner"] == entry["owner"]
                and item["suppression"]["expires"] == entry["expires"]
                for item in suppressed_findings
            )
            allowlist_suppression_counts.append({
                "entry": entry,
                "suppressed_count": count,
            })
        levels = ("high", "medium", "low")
        counts = {
            level: sum(item["severity"] == level for item in findings)
            for level in levels
        }
        gate_counts = {
            level: sum(
                item["severity"] == level
                and item.get("classification") == "gate"
                for item in findings
            )
            for level in levels
        }
        advisory_counts = {
            level: sum(
                item["severity"] == level
                and item.get("classification") == "advisory"
                for item in findings
            )
            for level in levels
        }
        unresolved_advisory_count = sum(advisory_counts.values())
        review_required = bool(
            unresolved_advisory_count or manual_review
        )
        design_review_status = (
            "pending" if review_required else "not-triggered-by-source"
        )
        threshold = {"none": 99, "high": 3, "medium": 2, "low": 1}[args.fail_on]
        ranking = {"high": 3, "medium": 2, "low": 1}
        gate_enforced = args.fail_on != "none"
        policy_gate_failure = any(
            item.get("classification") == "gate"
            for item in findings
        )
        exit_gate_finding_failure = gate_enforced and any(
            item.get("classification") == "gate"
            and ranking[str(item["severity"])] >= threshold
            for item in findings
        )
        scope_excluded_count = (
            len(excluded_default_files)
            + len(excluded_sensitive_structured_files)
        )
        selected_file_count = eligible_file_count - scope_excluded_count
        no_eligible_sources = eligible_file_count == 0
        no_selected_sources = selected_file_count == 0
        no_scanned_sources = len(records) == 0
        incomplete_failure = bool(skipped_sources) or no_scanned_sources
        quality_passed = not policy_gate_failure and not incomplete_failure
        quality_status = (
            "failed"
            if policy_gate_failure
            else "no-eligible-sources"
            if no_eligible_sources
            else "no-selected-sources"
            if no_selected_sources
            else "incomplete"
            if unacknowledged_skipped_files
            else "acknowledged-incomplete"
            if skipped_sources
            else "no-scanned-sources"
            if no_scanned_sources
            else "passed"
        )
        scope_status = (
            quality_status
            if no_eligible_sources or no_selected_sources
            else "incomplete"
            if skipped_sources
            else "no-scanned-sources"
            if no_scanned_sources
            else "scope-limited"
            if scope_excluded_count
            else "complete"
        )
        selected_scope_complete = not skipped_sources and not no_scanned_sources
        scan_scope_complete = selected_scope_complete and scope_excluded_count == 0
        exit_policy_triggered = gate_enforced and (
            exit_gate_finding_failure or incomplete_failure
        )
        command_exit_code = 1 if exit_policy_triggered else 0
        result = {
            "schema_version": SCAN_RESULT_SCHEMA_VERSION,
            "artifact_type": SCAN_RESULT_ARTIFACT_TYPE,
            "ok": quality_passed,
            "execution_ok": True,
            "execution": {
                "status": "succeeded",
                "ok": True,
            },
            "runtime_requirement": "Python >=3.10",
            "disclaimer": (
                "Advisories are review prompts; gate findings are conservative "
                "source defects. Neither establishes AI authorship or requires "
                "mechanical removal."
            ),
            "project": "project:/",
            "include_patterns": include_patterns,
            "documentation_mode": args.content_site,
            "structured_content_mode": args.structured_content,
            "built_output_mode": args.built_output,
            "gate_enforced": gate_enforced,
            "gate_threshold": args.fail_on,
            "gate_passed": quality_passed,
            "source_gate_passed": quality_passed,
            "quality_passed": quality_passed,
            "quality_status": quality_status,
            "review_required": review_required,
            "design_review_status": design_review_status,
            "unresolved_advisory_count": unresolved_advisory_count,
            "manual_review_count": len(manual_review),
            "review": {
                "required": review_required,
                "status": design_review_status,
                "unresolved_advisory_count": unresolved_advisory_count,
                "manual_review_count": len(manual_review),
                "note": (
                    "A source gate pass does not resolve design advisories or "
                    "manual rendered-review prompts."
                ),
            },
            "exit_code": command_exit_code,
            "exit_policy": {
                "fail_on": args.fail_on,
                "default_fail_on": "high",
                "enforced": gate_enforced,
                "explicit_advisory_exit_zero": args.advisory_exit_zero,
                "explicit_fail_on_none": requested_fail_on == "none",
                "triggered": exit_policy_triggered,
                "gate_finding_failure": exit_gate_finding_failure,
                "incomplete_source_failure": (
                    gate_enforced and incomplete_failure
                ),
                "exit_code": command_exit_code,
            },
            "quality": {
                "status": quality_status,
                "passed": quality_passed,
                "confirmed_gate_finding_count": sum(gate_counts.values()),
                "unacknowledged_skipped_source_count": len(
                    unacknowledged_skipped_files
                ),
                "skipped_source_count": len(skipped_sources),
                "empty_source_failure": no_scanned_sources,
                "scope_basis": (
                    "complete-eligible-source-scope"
                    if scan_scope_complete
                    else "selected-scanned-scope-only"
                ),
            },
            "default_content_exclusions": (
                "tests, stories, fixtures, and test/story/fixture filename patterns"
                if args.content_site
                else (
                    "docs, references, tests, stories, fixtures, and conventional "
                    "documentation files"
                )
            ),
            "source_coverage": {
                "bounded": True,
                "suffixes": sorted(scan_suffixes),
                "documentation_mode": args.content_site,
                "structured_content_mode": args.structured_content,
                "built_output_mode": args.built_output,
                "built_output_directories": sorted(BUILT_OUTPUT_DIRS),
                "always_excluded_directories": sorted(
                    ALWAYS_IGNORED_DIRS | INITIALIZER_EVIDENCE_DIR_LABELS
                ),
                "dependency_vendor_exclusions": sorted(DEPENDENCY_VENDOR_DIRS),
                "note": (
                    "Only listed text web-source suffixes are scanned. Runtime-generated "
                    "markup, dynamically rendered output, and unsupported languages "
                    "require manual review."
                ),
            },
            "allowlist": (
                report_input_label(
                    allowlist_path,
                    project=root,
                    skill_root=skill_root,
                    role="allowlist",
                )
                if allowlist_path.is_file()
                else None
            ),
            "owner_policy": (
                report_input_label(
                    owner_policy_path,
                    project=root,
                    skill_root=skill_root,
                    role="owner-policy",
                )
                if owner_policy_path.is_file()
                else None
            ),
            "active_allowlist_entries": entries,
            "expired_allowlist_entries": expired_entries,
            "allowlist_suppression_counts": allowlist_suppression_counts,
            "active_skipped_source_acknowledgements": skipped_acknowledgements,
            "expired_skipped_source_acknowledgements": (
                expired_skipped_acknowledgements
            ),
            "suppressed_count": len(suppressed_findings),
            "suppressed_findings": suppressed_findings,
            "excluded_default_files": sorted(excluded_default_files),
            "excluded_sensitive_structured_files": sorted(
                excluded_sensitive_structured_files
            ),
            "skipped_non_utf8_files": skipped_files,
            "skipped_oversized_files": skipped_oversized_files,
            "scan_status": scope_status,
            "scan_complete": scan_scope_complete,
            "selected_scope_complete": selected_scope_complete,
            "scan_scope": {
                "status": scope_status,
                "complete": scan_scope_complete,
                "selected_scope_complete": selected_scope_complete,
                "mode": (
                    "documentation-content-site"
                    if args.content_site
                    else "application-source"
                ),
                "eligible_file_count": eligible_file_count,
                "selected_file_count": (
                    selected_file_count
                ),
                "scanned_file_count": len(records),
                "excluded_eligible_file_count": scope_excluded_count,
                "skipped_selected_file_count": len(skipped_sources),
            },
            "gate_status": quality_status,
            "skipped_sources": skipped_sources,
            "unacknowledged_skipped_files": unacknowledged_skipped_files,
            "acknowledged_skipped_files": acknowledged_skipped_files,
            "limitations": [
                (
                    "Static scanning cannot prove runtime-computed class/style values, "
                    "component-rendered markup, semantic intent, or rendered prominence."
                ),
                (
                    "Unresolved prominent-fragment cases are listed under manual_review "
                    "and never promoted to gate failures automatically."
                ),
                (
                    "Media-reference prompts do not inspect image pixels; rendered "
                    "assets still require direct visual and provenance review."
                ),
                (
                    "Copy, structure, and comment clusters are heuristic review "
                    "prompts, not AI-authorship evidence."
                ),
            ],
            "manual_review": manual_review,
            "counts": counts,
            "gate_counts": gate_counts,
            "advisory_counts": advisory_counts,
            "findings": findings,
        }
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=True))
        else:
            print(result["disclaimer"])
            print(
                "Bounded source coverage: "
                + ", ".join(result["source_coverage"]["suffixes"])
                + ". Runtime-generated and dynamically rendered output requires "
                "manual review."
            )
            for finding in findings:
                print(
                    f"{str(finding['classification']).upper()} "
                    f"{finding['severity'].upper()} {finding['rule']} "
                    f"{finding['file']}:{finding['line']} - {finding['rationale']}"
                )
            for item in manual_review:
                print(
                    f"MANUAL {item['check']} {item['file']}:{item['line']} "
                    f"- {item['reason']}"
                )
            for item in allowlist_suppression_counts:
                entry = item["entry"]
                print(
                    f"ALLOWLIST-ACTIVE rule={entry['rule']}; "
                    f"path={entry['path']}; owner={entry['owner']}; "
                    f"fingerprint={entry['fingerprint']}; "
                    f"expires={entry['expires']}; "
                    f"matches={item['suppressed_count']}; "
                    f"reason={entry['reason']}"
                )
            for item in suppressed_findings:
                suppression = item["suppression"]
                print(
                    f"ALLOWLIST-SUPPRESSED {item['severity'].upper()} "
                    f"{item['rule']} {item['file']}:{item['line']} - "
                    f"owner={suppression['owner']}; "
                    f"fingerprint={suppression['fingerprint']}; "
                    f"expires={suppression['expires']}; "
                    f"reason={suppression['reason']}"
                )
            for acknowledgement in skipped_acknowledgements:
                print(
                    f"SKIP-ACK-ACTIVE path={acknowledgement['path']}; "
                    f"sha256={acknowledgement['sha256']}; "
                    f"size_bytes={acknowledgement['size_bytes']}; "
                    f"owner={acknowledgement['owner']}; "
                    f"expires={acknowledgement['expires']}; "
                    f"reason={acknowledgement['reason']}"
                )
            for item in skipped_sources:
                acknowledgement = item["acknowledgement"]
                if acknowledgement:
                    print(
                        f"SKIPPED-ACKNOWLEDGED {item['file']} - "
                        f"{item['reason']}; sha256={item['sha256']}; "
                        f"size_bytes={item['size_bytes']}; "
                        f"owner={acknowledgement['owner']}; "
                        f"expires={acknowledgement['expires']}; "
                        f"acknowledgement={acknowledgement['reason']}"
                    )
                else:
                    print(
                        f"SKIPPED-UNACKNOWLEDGED {item['file']} - "
                        f"{item['reason']}; sha256={item['sha256']}; "
                        f"size_bytes={item['size_bytes']}"
                    )
            if skipped_sources:
                print(
                    f"INCOMPLETE scan: {len(skipped_sources)} relevant source "
                    f"file(s) skipped; {len(unacknowledged_skipped_files)} "
                    "unacknowledged."
                )
            if no_scanned_sources:
                print(
                    "INCOMPLETE scan: no eligible selected source was scanned "
                    f"(status={quality_status})."
                )
            if scope_excluded_count:
                print(
                    f"SCOPE STATUS: LIMITED; {scope_excluded_count} "
                    "eligible file(s) were excluded by the selected scan mode. "
                    "Use --content-site for documentation content or --include "
                    "for a reviewed path override."
                )
            print(
                f"QUALITY/POLICY STATUS: {quality_status.upper()} "
                f"({sum(gate_counts.values())} confirmed gate finding(s); "
                f"scope={result['quality']['scope_basis']})."
            )
            print(
                "DESIGN REVIEW: "
                + (
                    "REQUIRED "
                    f"({unresolved_advisory_count} unresolved advisory "
                    f"finding(s); {len(manual_review)} manual-review item(s))."
                    if review_required
                    else "NOT TRIGGERED BY SOURCE SIGNALS."
                )
            )
            if gate_enforced:
                print(
                    f"EXIT POLICY: "
                    f"{'TRIGGERED' if exit_policy_triggered else 'NOT TRIGGERED'} "
                    f"(--fail-on {args.fail_on}; exit {command_exit_code})."
                )
            else:
                print(
                    "EXIT POLICY: NOT ENFORCED (--fail-on none; exit 0). "
                    "Confirmed gate findings still fail quality policy."
                )
            print(
                f"Found {len(findings)} findings: "
                f"{sum(gate_counts.values())} gate, "
                f"{sum(advisory_counts.values())} advisory; "
                f"{len(manual_review)} manual-review item(s); "
                f"{len(suppressed_findings)} allowlist suppression(s)."
            )
        return command_exit_code
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(json.dumps({
            "schema_version": SCAN_RESULT_SCHEMA_VERSION,
            "artifact_type": SCAN_RESULT_ARTIFACT_TYPE,
            "ok": False,
            "execution_ok": False,
            "execution": {"status": "failed", "ok": False},
            "error": {"code": "scan-failed", "message": str(exc)},
        }), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
