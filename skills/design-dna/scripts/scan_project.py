#!/usr/bin/env python3
"""Python 3.10+ source scanner for design-review candidates and gate-safe defects."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import html
import json
import math
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
            "ok": False,
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
    ".astro", ".cjs", ".cshtml", ".css", ".erb", ".handlebars", ".hbs",
    ".html", ".htm", ".js", ".jsx", ".liquid", ".md", ".mdx", ".mjs",
    ".mustache", ".njk", ".php", ".pug", ".razor", ".scss", ".svelte",
    ".svg", ".ts", ".tsx", ".twig", ".vue",
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
    ".astro", ".cshtml", ".erb", ".handlebars", ".hbs", ".html", ".htm",
    ".jsx", ".liquid", ".mdx", ".mustache", ".njk", ".php", ".razor",
    ".svelte", ".svg", ".tsx", ".twig", ".vue",
}
STATIC_MARKUP_SUFFIXES = {
    ".astro", ".handlebars", ".hbs", ".html", ".htm", ".jsx", ".liquid",
    ".mdx", ".mustache", ".njk", ".svelte", ".svg", ".tsx", ".twig",
    ".vue",
}
STATIC_ROUTE_SUFFIXES = {
    ".cshtml", ".erb", ".handlebars", ".hbs", ".html", ".htm", ".liquid",
    ".mustache", ".njk", ".php", ".razor", ".twig",
}
HTML_VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
IGNORED_DIRS = {
    ".design-dna", ".git", ".next", ".nuxt", ".output", ".svelte-kit", "build", "coverage",
    "dist", "node_modules", "vendor",
}
IGNORED_DIRS_CASEFOLD = {name.casefold() for name in IGNORED_DIRS}
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
OWNER_POLICY_DEFAULT_KEYS = {
    "current_unless_brief_says_otherwise",
    "infer_vintage_from_category",
    "arbitrary_headline_fragment_emphasis",
    "arbitrary_prominent_copy_fragment_emphasis",
    "gradient_headline_text_without_semantic_or_brand_reason",
    "unexamined_generator_default_typography",
    "hierarchy_follows_content_and_task",
    "semantic_maintainable_implementation",
    "motion_has_user_or_experience_purpose",
    "release_residue",
    "fabricated_proof_or_business_facts",
    "visibly_unfinished_controls",
    "cross_project_pattern_history",
    "representation_and_cultural_context",
}
OWNER_POLICY_DEFAULT_ENUMS = {
    "arbitrary_headline_fragment_emphasis": {
        "avoid", "investigate", "allow",
    },
    "arbitrary_prominent_copy_fragment_emphasis": {
        "avoid", "investigate", "allow",
    },
    "gradient_headline_text_without_semantic_or_brand_reason": {
        "avoid", "investigate", "allow",
    },
    "unexamined_generator_default_typography": {
        "avoid", "investigate", "allow",
    },
    "hierarchy_follows_content_and_task": {
        "require", "investigate", "allow",
    },
    "semantic_maintainable_implementation": {
        "require", "investigate", "allow",
    },
    "motion_has_user_or_experience_purpose": {
        "require", "investigate", "allow",
    },
    "release_residue": {"prohibit", "investigate", "allow"},
    "fabricated_proof_or_business_facts": {
        "prohibit", "investigate", "allow",
    },
    "visibly_unfinished_controls": {
        "prohibit", "investigate", "allow",
    },
    "cross_project_pattern_history": {"opt-in", "off", "on"},
    "representation_and_cultural_context": {
        "require-review", "investigate", "allow",
    },
}
MAX_TEXT_FILE_BYTES = 5 * 1024 * 1024
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
DECORATIVE_SECTION_LABEL_CLASS = re.compile(
    r"(?:^|[-_])(?:eyebrow|kicker|overline)(?:$|[-_])|"
    r"(?:^|[-_])section[-_]label(?:$|[-_])|^sectionLabel$",
    re.I,
)
SEMANTIC_SECTION_LABEL_CLASS = re.compile(
    r"(?:^|[-_])(?:status|state|badge|chip|tag|taxonomy|category|breadcrumb|"
    r"step|phase|severity|priority|success|error|warning|danger|price|amount|"
    r"metric|data|availability|field|form|input|control|legend|caption|"
    r"sr[-_]?only|visually[-_]?hidden)(?:$|[-_])",
    re.I,
)
SEMANTIC_SECTION_LABEL_TEXT = re.compile(
    r"^(?:status|state|priority|severity|availability|category|tag|"
    r"step(?:\s+\d+(?:\s+of\s+\d+)?)?|"
    r"phase(?:\s+\d+(?:\s+of\s+\d+)?)?)$",
    re.I,
)
SEMANTIC_SECTION_LABEL_ATTR = re.compile(
    r"\b(?:role\s*=\s*[\"'](?:status|alert|meter|progressbar)[\"']|"
    r"aria-live\s*=|data-(?:status|state|severity|priority)\s*=)",
    re.I,
)
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
RHETORICAL_LABEL_TEXT = re.compile(
    r"^(?:"
    r"question\s+(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
    r"|the\s+(?:arithmetic|awkward\s+question|cheap\s+move|"
    r"part\s+nobody\s+explains|bottom\s+line|catch)"
    r"|(?:last|next|final)\s+step"
    r")$",
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
CONTRAST_COPY_FORMULA = re.compile(
    r"(?:"
    r"\bnot\b[^.!?]{0,120}\b(?:but|instead|it\s+is|it['’]s|that\s+is)\b"
    r"|\bthe\s+(?:cheapest|fastest|easiest|hardest|best|worst|biggest|"
    r"smallest)\b[^.!?]{0,140}\bis\b"
    r"|\balmost\s+every\b[^.!?]{0,140}\balmost\s+none\b"
    r")",
    re.I,
)
PARALLEL_LIST_SENTENCE = re.compile(
    r"\b[^.!?\n,]{2,60},\s+[^.!?\n,]{2,60},\s+"
    r"(?:and|or)\s+[^.!?\n]{2,80}[.!?]?",
    re.I,
)
SCENE_COMMENT_MARKER = re.compile(
    r"\b(?:ACT|SCENE|CHAPTER|BEAT)\s+\d+\b|\bSIGNATURE\s+MOMENT\b",
    re.I,
)
COMMENT_RATIONALE_MARKER = re.compile(
    r"\b(?:on\s+purpose|reads?\s+as|felt,?\s+not|rather\s+than|"
    r"one\s+[^.\n]{1,80}\s+per\s+role|one\s+hue|signature\s+moment)\b",
    re.I,
)
GENERATED_MEDIA_MARKER = re.compile(
    r"\b(?:AI[- ]generated|generated\s+(?:image|imagery|photo|photography)|"
    r"synthetic\s+(?:image|imagery|photo|photography))\b",
    re.I,
)
CONCEPT_MARKER = re.compile(
    r"\b(?:sample\s+(?:site|website|concept)|demo\s+(?:site|form|concept)|"
    r"not\s+a\s+real\s+(?:company|business)|concept\s+(?:site|website))\b",
    re.I,
)
MISSING_IDENTITY_SIGNALS = (
    ("example-contact", re.compile(r"\b[A-Z0-9._%+-]+@example\.com\b", re.I)),
    ("zero-phone", re.compile(r"\(\s*000\s*\)\s*000[-\s]0000")),
    ("service-area-placeholder", re.compile(r"\byour\s+service\s+area\b", re.I)),
    (
        "licence-placeholder",
        re.compile(r"\b(?:electrical\s+)?licen[cs]e\s+number\b", re.I),
    ),
    ("placeholder-language", re.compile(r"\bplaceholders?\b", re.I)),
)
CSS_DECLARATION_BLOCK = re.compile(r"(?P<header>[^{}]*)\{(?P<body>[^{}]*)\}", re.S)
OKLCH_COMPONENT = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:%)?"
OKLCH_VALUE = re.compile(
    rf"^\s*(?P<lightness>{OKLCH_COMPONENT})\s+"
    rf"(?P<chroma>{OKLCH_COMPONENT})\s+"
    rf"(?P<hue>{OKLCH_COMPONENT})"
    rf"(?:\s*/\s*(?P<alpha>{OKLCH_COMPONENT}))?\s*$",
    re.I,
)
SHADCN_OKLCH_DECLARATION = re.compile(
    r"--(?P<token>"
    r"background|foreground|card|card-foreground|popover|popover-foreground|"
    r"primary|primary-foreground|secondary|secondary-foreground|muted|"
    r"muted-foreground|accent|accent-foreground|destructive|border|input|ring"
    r")\s*:\s*oklch\((?P<value>[^)]+)\)",
    re.I,
)
SHADCN_CURRENT_OKLCH_DEFAULTS = {
    "light": {
        "background": (1.0, 0.0, 0.0, None),
        "foreground": (0.145, 0.0, 0.0, None),
        "card": (1.0, 0.0, 0.0, None),
        "card-foreground": (0.145, 0.0, 0.0, None),
        "popover": (1.0, 0.0, 0.0, None),
        "popover-foreground": (0.145, 0.0, 0.0, None),
        "primary": (0.205, 0.0, 0.0, None),
        "primary-foreground": (0.985, 0.0, 0.0, None),
        "secondary": (0.97, 0.0, 0.0, None),
        "secondary-foreground": (0.205, 0.0, 0.0, None),
        "muted": (0.97, 0.0, 0.0, None),
        "muted-foreground": (0.556, 0.0, 0.0, None),
        "accent": (0.97, 0.0, 0.0, None),
        "accent-foreground": (0.205, 0.0, 0.0, None),
        "destructive": (0.577, 0.245, 27.325, None),
        "border": (0.922, 0.0, 0.0, None),
        "input": (0.922, 0.0, 0.0, None),
        "ring": (0.708, 0.0, 0.0, None),
    },
    "dark": {
        "background": (0.145, 0.0, 0.0, None),
        "foreground": (0.985, 0.0, 0.0, None),
        "card": (0.205, 0.0, 0.0, None),
        "card-foreground": (0.985, 0.0, 0.0, None),
        "popover": (0.205, 0.0, 0.0, None),
        "popover-foreground": (0.985, 0.0, 0.0, None),
        "primary": (0.922, 0.0, 0.0, None),
        "primary-foreground": (0.205, 0.0, 0.0, None),
        "secondary": (0.269, 0.0, 0.0, None),
        "secondary-foreground": (0.985, 0.0, 0.0, None),
        "muted": (0.269, 0.0, 0.0, None),
        "muted-foreground": (0.708, 0.0, 0.0, None),
        "accent": (0.269, 0.0, 0.0, None),
        "accent-foreground": (0.985, 0.0, 0.0, None),
        "destructive": (0.704, 0.191, 22.216, None),
        "border": (1.0, 0.0, 0.0, 0.1),
        "input": (1.0, 0.0, 0.0, 0.15),
        "ring": (0.556, 0.0, 0.0, None),
    },
}
# Require at least five-sixths of the 18-token core scaffold in one block.
SHADCN_CURRENT_OKLCH_MIN_MATCHES = 15


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    pattern: Optional[re.Pattern[str]]
    rationale: str
    suggestion: str
    min_occurrences: int = 1
    classification: str = "advisory"


RULES = (
    Rule("generic-gradient-text", "medium", re.compile(r"(?:bg-clip-text|background-clip\s*:\s*text).{0,160}(?:gradient|linear-gradient)|(?:gradient|linear-gradient).{0,160}(?:bg-clip-text|background-clip\s*:\s*text)", re.I), "Gradient headline treatment can become a repeated default when it has no semantic or brand role.", "Confirm a project-specific role or use a coherent foreground color."),
    Rule("uniform-pill-language", "low", re.compile(r"\brounded-full\b|border-radius\s*:\s*(?:9999|999|100)%?px?", re.I), "Frequent pill geometry can flatten hierarchy.", "Count occurrences in context and reserve pills for controls or semantic tokens that benefit from the shape.", 4),
    Rule("stock-fade-up", "medium", re.compile(r"\b(?:fade[-_ ]?up|animate-in|slide-in-from-bottom)\b", re.I), "Repeated entrance animation often adds motion without explaining state or continuity.", "Review motion purpose, choreography, interruption, and reduced-motion behavior.", 3),
    Rule("generic-hover-lift", "low", re.compile(r"(?:hover:(?:-translate-y|scale-|shadow-)|:hover[^{]*\{[^}]*(?:transform|box-shadow))", re.I), "Uniform hover lift or glow can make unrelated components behave identically.", "Tie feedback to affordance and component semantics.", 3),
    Rule(
        "repeated-decorative-section-label",
        "low",
        None,
        "Repeated eyebrow, kicker, overline, or section-label treatment can flatten hierarchy when every section receives the same garnish.",
        "Keep labels that communicate taxonomy, sequence, or state; otherwise let the heading and content establish hierarchy.",
        4,
    ),
    Rule(
        "rhetorical-label-cluster",
        "low",
        None,
        "Repeated rhetorical section labels can make unrelated sections inherit one presentation formula.",
        "Keep only labels that orient the reader; vary section structure according to the information job rather than rotating stock narrative phrases.",
    ),
    Rule("decorative-headline-span", "medium", None, "A short differently colored headline fragment can look ornamental when it has no semantic or brand meaning.", "Use one coherent headline color unless the fragment carries documented meaning."),
    Rule(
        "decorative-display-fragment",
        "medium",
        None,
        "A one- or two-word color change in prominent display copy can be the same arbitrary emphasis shortcut even when it is not an HTML heading.",
        "Use one coherent treatment or document the complete semantic, approved brand, status, data, quotation, or editorial reason.",
    ),
    Rule("emoji-as-interface-icon", "medium", re.compile(r"(?:<button|<a|<li|<div)[^>]*>[^<]{0,80}[\U0001F300-\U0001FAFF]"), "Emoji used as interface icons vary by platform and often signal placeholder iconography.", "Use text or an intentional accessible icon system."),
    Rule(
        "placeholder-proof",
        "high",
        re.compile(r"\blorem ipsum\b", re.I),
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
    Rule("generic-cta-copy", "low", re.compile(r">\s*(?:Get Started|Learn More|Start Today|Explore More|Transform Your [^<]{1,40})\s*<", re.I), "Interchangeable calls to action hide the actual next step.", "Name the action and expected outcome."),
    Rule("untouched-shadcn-token", "low", re.compile(r"--(?:background|foreground|primary|secondary|muted|accent):\s*\d+(?:\.\d+)?\s+\d+(?:\.\d+)?%\s+\d+(?:\.\d+)?%"), "An unmodified component-library token set may carry a recognizable default visual system.", "Verify tokens against real brand and product requirements rather than changing them mechanically.", 6),
    Rule("repeated-sparkle-icon", "low", re.compile(r"\b(?:Sparkles|WandSparkles|Rocket|Zap)\b"), "Decorative magic and launch icons recur in generated first drafts.", "Use only when the metaphor is accurate and the icon family is deliberately art-directed.", 3),
    Rule("hardcoded-large-section-gap", "low", re.compile(r"\b(?:py-(?:20|24|28|32)|padding-block\s*:\s*(?:8|10|12)rem)\b"), "Uniform oversized section spacing can reduce useful density.", "Review rhythm with real content across intermediate viewport sizes.", 4),
    Rule(
        "presentation-script-comment-cluster",
        "low",
        None,
        "A production source tree organized as numbered acts or creative-brief beats can retain presentation-script residue that is not useful maintainer documentation.",
        "Keep comments that explain durable constraints or non-obvious behavior; condense staging narration that merely restates the visual treatment.",
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


def iter_files(root: Path, suffixes: set[str]):
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
        dirs[:] = [
            name for name in dirs
            if name.casefold() not in IGNORED_DIRS_CASEFOLD
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
        required = {"path", "reason", "owner", "expires"}
        if set(entry) != required:
            raise ValueError(
                "each skipped-source acknowledgement needs only path, reason, "
                "owner, and expires"
            )
        pattern = entry.get("path")
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


def load_type_watch(path: Path) -> tuple[Rule, dict[str, object]]:
    if is_reparse(path) or not path.is_file():
        raise ValueError(f"type-convergence policy is unavailable or unsafe: {path}")
    text = path.read_text(encoding="utf-8")
    due_matches = re.findall(r'(?m)^review_due:\s*["\']?([0-9]{4}-[0-9]{2}-[0-9]{2})["\']?\s*$', text)
    if len(due_matches) != 1:
        raise ValueError("type-convergence policy must contain exactly one review_due date")
    review_due = date.fromisoformat(due_matches[0])
    section = re.search(
        r"(?ms)^documented_first_or_default:\s*\n(.*?)(?=^[A-Za-z_][A-Za-z0-9_-]*:\s*(?:\n|$)|\Z)",
        text,
    )
    if not section:
        raise ValueError("type-convergence policy is missing documented_first_or_default")
    families = re.findall(
        r'(?m)^\s*-\s+family:\s*["\']([^"\']+)["\']\s*$',
        section.group(1),
    )
    if not families or len(families) != len(set(name.casefold() for name in families)):
        raise ValueError("type-convergence policy needs unique documented default families")
    family_pattern = "|".join(
        re.escape(name).replace(r"\ ", r"(?:\s|\+)+")
        for name in sorted(families, key=len, reverse=True)
    )
    rule = Rule(
        "unexamined-default-font",
        "low",
        re.compile(
            rf"(?:font-family|fontFamily|--[A-Za-z0-9_-]*font[A-Za-z0-9_-]*|family=)"
            rf"[^\n]{{0,160}}(?:{family_pattern})\b|"
            rf"\b(?:{family_pattern})\b[^\n]{{0,100}}"
            rf"(?:next/font|fontFamily|font-family)|"
            rf"(?:^|[;{{])\s*font\s*:[^;\n{{}}]{{0,160}}"
            rf"(?:{family_pattern})\b",
            re.I,
        ),
        "A documented builder-default family is worth checking when it supplies identity by itself.",
        "Keep it when project fit, language coverage, metrics, and the existing system justify it; otherwise compare real-copy alternatives.",
    )
    return rule, {
        "path": str(path),
        "review_due": review_due.isoformat(),
        "expired": review_due < date.today(),
        "families": families,
    }


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


def source_comments(path: Path, text: str) -> list[dict[str, object]]:
    """Extract comments for a dedicated residue review without scanning strings."""
    comments: list[dict[str, object]] = []
    code_comment_suffixes = {
        ".astro", ".cjs", ".css", ".js", ".jsx", ".mjs", ".scss",
        ".svelte", ".ts", ".tsx", ".vue",
    }
    index = 0
    while index < len(text):
        if text.startswith("<!--", index):
            close = text.find("-->", index + 4)
            end = len(text) if close < 0 else close + 3
            comments.append({
                "line": line_number(text, index),
                "text": text[index + 4:close if close >= 0 else len(text)],
            })
            index = end
            continue
        if path.suffix.lower() not in code_comment_suffixes:
            index += 1
            continue
        if text[index] in "\"'`":
            index = skip_quoted_source(text, index)
            continue
        if text.startswith("/*", index):
            close = text.find("*/", index + 2)
            end = len(text) if close < 0 else close + 2
            comments.append({
                "line": line_number(text, index),
                "text": text[index + 2:close if close >= 0 else len(text)],
            })
            index = end
            continue
        if text.startswith("//", index):
            close = text.find("\n", index + 2)
            end = len(text) if close < 0 else close
            comments.append({
                "line": line_number(text, index),
                "text": text[index + 2:end],
            })
            index = end
            continue
        index += 1
    return comments


def presentation_script_comment_candidates(
    raw_records: list[tuple[Path, str, str]],
) -> list[dict[str, object]]:
    scene_evidence: list[dict[str, object]] = []
    rationale_evidence: list[dict[str, object]] = []
    scene_by_file: dict[str, int] = {}
    for path, relative, text in raw_records:
        for comment in source_comments(path, text):
            value = " ".join(str(comment["text"]).split())
            if not value:
                continue
            if SCENE_COMMENT_MARKER.search(value):
                scene_by_file[relative] = scene_by_file.get(relative, 0) + 1
                scene_evidence.append({
                    "file": relative,
                    "line": comment["line"],
                    "excerpt": value[:160],
                })
            if COMMENT_RATIONALE_MARKER.search(value):
                rationale_evidence.append({
                    "file": relative,
                    "line": comment["line"],
                    "excerpt": value[:160],
                })
    concentrated = any(count >= 4 for count in scene_by_file.values())
    distributed = len(scene_evidence) >= 6 and len(rationale_evidence) >= 2
    if not concentrated and not distributed:
        return []
    first = scene_evidence[0]
    rule = next(
        item
        for item in RULES
        if item.id == "presentation-script-comment-cluster"
    )
    return [{
        "rule": rule.id,
        "severity": rule.severity,
        "classification": rule.classification,
        "file": first["file"],
        "line": first["line"],
        "excerpt": (
            f"{len(scene_evidence)} scene/beat marker(s) and "
            f"{len(rationale_evidence)} creative-rationale marker(s)"
        ),
        "matched_signal": {
            "scene_marker_count": len(scene_evidence),
            "rationale_marker_count": len(rationale_evidence),
            "scene_markers_by_file": dict(sorted(scene_by_file.items())),
            "examples": (scene_evidence + rationale_evidence)[:8],
            "basis": "dedicated production-source comment review",
        },
        "rationale": rule.rationale,
        "suggestion": rule.suggestion,
        "owner_policy": None,
    }]


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
    lists: dict[str, list[str]] = {
        "headline_fragment_exceptions": [],
        "interpretation": [],
    }
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
        "headline_fragment_exceptions",
        "interpretation",
    }
    if set(top_level) != required:
        missing = sorted(required - set(top_level))
        unknown = sorted(set(top_level) - required)
        raise ValueError(
            "owner-policy top-level contract mismatch; "
            f"missing={missing}, unknown={unknown}"
        )
    if top_level["schema_version"] != 1:
        raise ValueError("owner-policy schema_version must be 1")
    for field in ("owner", "scope"):
        if (
            not isinstance(top_level[field], str)
            or not str(top_level[field]).strip()
        ):
            raise ValueError(f"owner-policy {field} must be nonempty text")
    if top_level["status"] != "active":
        raise ValueError("owner-policy status must be active")
    if set(defaults) != OWNER_POLICY_DEFAULT_KEYS:
        missing = sorted(OWNER_POLICY_DEFAULT_KEYS - set(defaults))
        unknown = sorted(set(defaults) - OWNER_POLICY_DEFAULT_KEYS)
        raise ValueError(
            "owner-policy defaults contract mismatch; "
            f"missing={missing}, unknown={unknown}"
        )
    for field in (
        "current_unless_brief_says_otherwise",
        "infer_vintage_from_category",
    ):
        if not isinstance(defaults[field], bool):
            raise ValueError(f"owner-policy default {field} must be boolean")
    for field, allowed_values in OWNER_POLICY_DEFAULT_ENUMS.items():
        value = defaults[field]
        if not isinstance(value, str) or value not in allowed_values:
            raise ValueError(
                f"owner-policy default {field} must be one of "
                f"{sorted(allowed_values)}"
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
    entries: list[dict[str, object]],
) -> Optional[dict[str, object]]:
    for entry in entries:
        if fnmatch.fnmatchcase(relative, str(entry["path"])):
            return entry
    return None


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
) -> bool:
    sentence_start = 0
    for boundary in re.finditer(r"[.!?;]+[\"'”’)\]]*\s*", value[:start]):
        sentence_start = boundary.end()
    boundary = re.search(r"[.!?;]+", value[end:])
    sentence_end = len(value) if not boundary else end + boundary.end()
    sentence = html.unescape(value[sentence_start:sentence_end])
    return bool(NEGATIVE_OR_EXAMPLE_CONTEXT.search(sentence))


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
        ):
            return None
    return "advisory", {
        "match": matched_text,
        "basis": (
            "source occurrence is not a confirmed literal text node in a "
            "supported renderable markup format"
        ),
    }


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


def oklch_signature(
    value: str,
) -> Optional[tuple[float, float, float, Optional[float]]]:
    match = OKLCH_VALUE.fullmatch(value)
    if not match:
        return None

    def component(name: str, *, percent_allowed: bool) -> Optional[float]:
        raw = match.group(name)
        if raw is None:
            return None
        is_percent = raw.endswith("%")
        if is_percent and not percent_allowed:
            raise ValueError
        number = float(raw[:-1] if is_percent else raw)
        if is_percent:
            number /= 100
        return round(number, 6)

    try:
        lightness = component("lightness", percent_allowed=True)
        chroma = component("chroma", percent_allowed=False)
        hue = component("hue", percent_allowed=False)
        alpha = component("alpha", percent_allowed=True)
    except ValueError:
        return None
    if lightness is None or chroma is None or hue is None:
        return None
    return lightness, chroma, hue, alpha


def current_shadcn_oklch_candidates(
    records: list[tuple[Path, str, str]],
    rule: Rule,
) -> list[dict[str, object]]:
    """Find a near-complete current default in one CSS declaration block."""
    findings: list[dict[str, object]] = []
    for _path, relative, text in records:
        for block in CSS_DECLARATION_BLOCK.finditer(text):
            declarations: dict[
                str,
                tuple[
                    tuple[float, float, float, Optional[float]],
                    int,
                ],
            ] = {}
            body = block.group("body")
            for declaration in SHADCN_OKLCH_DECLARATION.finditer(body):
                signature = oklch_signature(declaration.group("value"))
                if signature is None:
                    continue
                declarations[declaration.group("token").casefold()] = (
                    signature,
                    declaration.start(),
                )
            if len(declarations) < SHADCN_CURRENT_OKLCH_MIN_MATCHES:
                continue

            candidates = []
            for profile, expected in SHADCN_CURRENT_OKLCH_DEFAULTS.items():
                matching_tokens = sorted(
                    token
                    for token, (signature, _position) in declarations.items()
                    if expected.get(token) == signature
                )
                if len(matching_tokens) >= SHADCN_CURRENT_OKLCH_MIN_MATCHES:
                    candidates.append(
                        (len(matching_tokens), profile, matching_tokens)
                    )
            if not candidates:
                continue

            matched_count, profile, matching_tokens = max(candidates)
            first_position = min(
                declarations[token][1] for token in matching_tokens
            )
            findings.append({
                "rule": rule.id,
                "severity": rule.severity,
                "classification": rule.classification,
                "file": relative,
                "line": line_number(
                    text,
                    block.start("body") + first_position,
                ),
                "excerpt": (
                    f"{matched_count}/{len(SHADCN_CURRENT_OKLCH_DEFAULTS[profile])} "
                    f"current shadcn neutral {profile} OKLCH tokens match "
                    "within one declaration block"
                ),
                "matched_signal": {
                    "profile": profile,
                    "matched_count": matched_count,
                    "expected_count": len(
                        SHADCN_CURRENT_OKLCH_DEFAULTS[profile]
                    ),
                    "matched_tokens": matching_tokens,
                    "basis": "same CSS declaration block",
                },
                "rationale": rule.rationale,
                "suggestion": rule.suggestion,
                "owner_policy": None,
            })
    return findings


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


def decorative_section_label_instances(
    records: list[tuple[Path, str, str]],
) -> list[dict[str, object]]:
    instances: list[dict[str, object]] = []
    tag_pattern = re.compile(
        r"<(?P<tag>h[1-6]|div|p|span|small)\b(?P<attrs>[^>]*)>"
        r"(?P<direct_text>[^<]{0,160})",
        re.I | re.S,
    )
    for path, relative, text in records:
        if path.suffix.lower() not in PROMINENT_MARKUP_SUFFIXES:
            continue
        for match in tag_pattern.finditer(text):
            if context_is_negative_or_example(
                text,
                match.start(),
                match.end(),
            ):
                continue
            attrs = match.group("attrs")
            class_tokens = [
                token.rsplit(":", 1)[-1]
                for value in literal_class_values(attrs)
                for token in value.split()
            ]
            matched_classes = sorted({
                token
                for token in class_tokens
                if DECORATIVE_SECTION_LABEL_CLASS.search(token)
            })
            if not matched_classes:
                continue
            if any(
                SEMANTIC_SECTION_LABEL_CLASS.search(token)
                for token in class_tokens
            ):
                continue
            if SEMANTIC_SECTION_LABEL_ATTR.search(attrs):
                continue
            direct_text = " ".join(match.group("direct_text").split())
            normalized_text = direct_text.casefold()
            if (
                normalized_text in SEMANTIC_STATUS_TEXT
                or SEMANTIC_SECTION_LABEL_TEXT.fullmatch(direct_text)
            ):
                continue
            instances.append({
                "file": relative,
                "line": line_number(text, match.start()),
                "position": match.start(),
                "excerpt": " ".join(match.group(0).split())[:160],
                "matched_signal": {
                    "classes": matched_classes,
                    "direct_text": direct_text or None,
                    "basis": "literal class on a content element",
                },
            })
    return instances


def aggregate_label_candidates(
    instances: list[dict[str, object]],
    rule: Rule,
) -> list[dict[str, object]]:
    by_file: dict[str, list[dict[str, object]]] = {}
    for instance in instances:
        by_file.setdefault(str(instance["file"]), []).append(instance)
    findings: list[dict[str, object]] = []
    for relative in sorted(by_file):
        matched = sorted(
            by_file[relative],
            key=lambda item: (int(item["line"]), int(item["position"])),
        )
        if len(matched) < rule.min_occurrences:
            continue
        labels = [
            {
                "line": item["line"],
                "classes": item["matched_signal"]["classes"],
                "text": item["matched_signal"]["direct_text"],
            }
            for item in matched
        ]
        findings.append({
            "rule": rule.id,
            "severity": rule.severity,
            "classification": rule.classification,
            "file": relative,
            "line": matched[0]["line"],
            "excerpt": (
                f"{len(matched)} decorative section-label treatments "
                "in one renderable source"
            ),
            "matched_signal": {
                "count": len(matched),
                "labels": labels[:12],
                "basis": "route-scoped literal section-label cluster",
            },
            "rationale": rule.rationale,
            "suggestion": rule.suggestion,
            "owner_policy": None,
        })
    return findings


def rhetorical_label_candidates(
    instances: list[dict[str, object]],
) -> list[dict[str, object]]:
    rule = next(
        item for item in RULES if item.id == "rhetorical-label-cluster"
    )
    by_file: dict[str, list[dict[str, object]]] = {}
    for instance in instances:
        by_file.setdefault(str(instance["file"]), []).append(instance)
    findings: list[dict[str, object]] = []
    for relative in sorted(by_file):
        all_labels = by_file[relative]
        rhetorical = [
            item
            for item in all_labels
            if RHETORICAL_LABEL_TEXT.fullmatch(
                str(item["matched_signal"]["direct_text"] or "").strip()
            )
        ]
        if len(all_labels) < 4 or len(rhetorical) < 3:
            continue
        rhetorical.sort(
            key=lambda item: (int(item["line"]), int(item["position"]))
        )
        findings.append({
            "rule": rule.id,
            "severity": rule.severity,
            "classification": rule.classification,
            "file": relative,
            "line": rhetorical[0]["line"],
            "excerpt": (
                f"{len(rhetorical)} rhetorical labels among "
                f"{len(all_labels)} decorative labels"
            ),
            "matched_signal": {
                "rhetorical_count": len(rhetorical),
                "decorative_label_count": len(all_labels),
                "labels": [
                    {
                        "line": item["line"],
                        "text": item["matched_signal"]["direct_text"],
                    }
                    for item in rhetorical[:12]
                ],
                "basis": "route-scoped literal rhetorical-label cluster",
            },
            "rationale": rule.rationale,
            "suggestion": rule.suggestion,
            "owner_policy": None,
        })
    return findings


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
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    manual_review: list[dict[str, object]] = []
    evidence_by_file: dict[str, dict[str, object]] = {}
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
        evidence_by_file[relative] = {
            "claim_count": len(claims),
            "section_count": len(section_ids),
            "claims": claims,
            "word_count": sum(
                len(fragment_words(str(node["text"])))
                for node in prose
            ),
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
    return manual_review, evidence_by_file


def copy_uniformity_candidates(
    records: list[tuple[Path, str, str]],
    label_instances: list[dict[str, object]],
    quantitative_evidence: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    labels_by_file: dict[str, list[dict[str, object]]] = {}
    for instance in label_instances:
        labels_by_file.setdefault(str(instance["file"]), []).append(instance)
    manual_review: list[dict[str, object]] = []
    for path, relative, text in records:
        quantitative = quantitative_evidence.get(relative, {})
        if int(quantitative.get("word_count", 0)) < 400:
            continue
        sections = static_container_ranges(text, "section")
        route_labels = labels_by_file.get(relative, [])
        rhetorical_count = sum(
            bool(
                RHETORICAL_LABEL_TEXT.fullmatch(
                    str(item["matched_signal"]["direct_text"] or "").strip()
                )
            )
            for item in route_labels
        )
        contrast: list[dict[str, object]] = []
        parallel: list[dict[str, object]] = []
        for node in visible_prose_records(path, text):
            for pattern, target in (
                (CONTRAST_COPY_FORMULA, contrast),
                (PARALLEL_LIST_SENTENCE, parallel),
            ):
                for match in pattern.finditer(str(node["text"])):
                    target.append({
                        "line": node["line"],
                        "section": node["section"],
                        "excerpt": match.group(0)[:160],
                    })
        contrast_sections = {
            item["section"]
            for item in contrast
            if item["section"] is not None
        }
        parallel_sections = {
            item["section"]
            for item in parallel
            if item["section"] is not None
        }
        cadence_count = 0
        for start, end in sections:
            section_source = text[start:end]
            if (
                any(
                    start <= int(item["position"]) < end
                    for item in route_labels
                )
                and re.search(r"<h[1-6]\b", section_source, re.I)
                and re.search(r"<p\b", section_source, re.I)
            ):
                cadence_count += 1
        signals: list[dict[str, object]] = []
        if rhetorical_count >= 4:
            signals.append({
                "signal": "rhetorical-labels",
                "count": rhetorical_count,
            })
        if (
            int(quantitative.get("claim_count", 0)) >= 8
            and int(quantitative.get("section_count", 0)) >= 3
        ):
            signals.append({
                "signal": "quantitative-specificity",
                "count": quantitative["claim_count"],
            })
        if len(contrast) >= 4 and len(contrast_sections) >= 3:
            signals.append({
                "signal": "contrast-reversal-formulas",
                "count": len(contrast),
                "examples": contrast[:5],
            })
        if len(parallel) >= 5 and len(parallel_sections) >= 3:
            signals.append({
                "signal": "parallel-list-cadence",
                "count": len(parallel),
                "examples": parallel[:5],
            })
        if cadence_count >= 4:
            signals.append({
                "signal": "repeated-label-heading-explanation-cadence",
                "count": cadence_count,
            })
        if len(signals) < 3:
            continue
        first_line = min(
            [int(item["line"]) for item in route_labels] or [1]
        )
        manual_review.append({
            "file": relative,
            "line": first_line,
            "check": "copy-uniformity-cluster",
            "severity": "low",
            "reason": (
                "At least three independent copy-form signals repeat across "
                "this route. Accumulation can make the voice feel generated "
                "or over-directed even though no individual construction "
                "establishes authorship."
            ),
            "evidence": {
                "word_count": quantitative.get("word_count", 0),
                "signals": signals,
            },
            "suggestion": (
                "Vary rhetorical mode by content job, retain concrete approved "
                "facts, and let section structure follow the reader's decision "
                "rather than one repeated explanatory cadence."
            ),
            "owner_policy": None,
        })
    return manual_review


def section_primary_role(section_source: str) -> str:
    if re.search(r"<form\b", section_source, re.I):
        return "form"
    if re.search(r"<h1\b", section_source, re.I):
        return "hero"
    if (
        re.search(
            r"<(?:button|input|select|output|meter)\b",
            section_source,
            re.I,
        )
        and re.search(r"<(?:figure|svg|dl|table)\b", section_source, re.I)
    ):
        return "estimator"
    if re.search(r"<ol\b", section_source, re.I):
        return "process"
    if (
        re.search(r"<(?:table|dl)\b", section_source, re.I)
        or len(re.findall(r"<h3\b", section_source, re.I)) >= 3
    ):
        return "comparison"
    if re.search(r"<(?:figure|img|svg|picture|video)\b", section_source, re.I):
        return "media"
    return "content"


def route_role_signature(text: str) -> tuple[list[str], int]:
    main_ranges = static_container_ranges(text, "main")
    if not main_ranges:
        return [], 0
    main_start, main_end = main_ranges[0]
    section_ranges = [
        (start, end)
        for start, end in static_container_ranges(text, "section")
        if main_start <= start and end <= main_end
    ]
    roles = [
        section_primary_role(text[start:end])
        for start, end in section_ranges
    ]
    compressed: list[str] = []
    for role in roles:
        if not compressed or compressed[-1] != role:
            compressed.append(role)
    return compressed, len(section_ranges)


def shared_role_sequence(
    first: list[str],
    second: list[str],
) -> list[str]:
    table = [
        [0] * (len(second) + 1)
        for _ in range(len(first) + 1)
    ]
    for left in range(len(first) - 1, -1, -1):
        for right in range(len(second) - 1, -1, -1):
            table[left][right] = (
                1 + table[left + 1][right + 1]
                if first[left] == second[right]
                else max(table[left + 1][right], table[left][right + 1])
            )
    shared: list[str] = []
    left = right = 0
    while left < len(first) and right < len(second):
        if first[left] == second[right]:
            shared.append(first[left])
            left += 1
            right += 1
        elif table[left + 1][right] >= table[left][right + 1]:
            left += 1
        else:
            right += 1
    return shared


def parallel_route_skeleton_candidates(
    records: list[tuple[Path, str, str]],
) -> list[dict[str, object]]:
    routes: list[dict[str, object]] = []
    for path, relative, text in records:
        if path.suffix.lower() not in STATIC_ROUTE_SUFFIXES:
            continue
        signature, section_count = route_role_signature(text)
        if section_count >= 4 and len(signature) >= 4:
            routes.append({
                "file": relative,
                "signature": signature,
                "section_count": section_count,
            })
    manual_review: list[dict[str, object]] = []
    for index, first in enumerate(routes):
        for second in routes[index + 1:]:
            shared = shared_role_sequence(
                list(first["signature"]),
                list(second["signature"]),
            )
            denominator = max(
                len(first["signature"]),
                len(second["signature"]),
            )
            similarity = len(shared) / denominator
            if len(shared) < 4 or similarity < 0.75:
                continue
            manual_review.append({
                "file": first["file"],
                "line": 1,
                "check": "parallel-route-skeleton",
                "severity": "low",
                "reason": (
                    "Two substantial routes share a close sequence of main "
                    "content roles after shared page chrome is excluded."
                ),
                "evidence": {
                    "routes": [first["file"], second["file"]],
                    "section_counts": [
                        first["section_count"],
                        second["section_count"],
                    ],
                    "signatures": [
                        first["signature"],
                        second["signature"],
                    ],
                    "shared_sequence": shared,
                    "similarity": round(similarity, 3),
                },
                "suggestion": (
                    "Confirm that both routes genuinely follow the same user "
                    "decision sequence; otherwise restructure each around its "
                    "own questions, proof, and action."
                ),
                "owner_policy": None,
            })
    return manual_review


def material_media_candidates(
    records: list[tuple[Path, str, str]],
) -> tuple[list[dict[str, object]], dict[str, int]]:
    manual_review: list[dict[str, object]] = []
    count_by_file: dict[str, int] = {}
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
        count_by_file[relative] = len(references)
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
                "Inspect the rendered assets at full size for factual role, "
                "provenance, documentary detail, geometry, text, logos, hands, "
                "reflections, shadows, repeated artifacts, and over-uniform "
                "lighting, grading, palette, or framing."
            ),
            "owner_policy": None,
        })
    return manual_review, count_by_file


def concept_material_balance_candidates(
    records: list[tuple[Path, str, str]],
    media_count_by_file: dict[str, int],
) -> list[dict[str, object]]:
    manual_review: list[dict[str, object]] = []
    for path, relative, text in records:
        if path.suffix.lower() not in PROMINENT_MARKUP_SUFFIXES:
            continue
        sections = static_container_ranges(text, "section")
        if len(sections) < 5:
            continue
        visible_text = " ".join(
            str(item["text"])
            for item in visible_prose_records(path, text)
        )
        if not CONCEPT_MARKER.search(visible_text):
            continue
        missing = [
            name
            for name, pattern in MISSING_IDENTITY_SIGNALS
            if pattern.search(visible_text)
        ]
        if len(missing) < 3:
            continue
        features: list[str] = []
        if re.search(r"<form\b", text, re.I):
            features.append("form")
        if re.search(r"<(?:svg|canvas)\b", text, re.I):
            features.append("dynamic-or-diagrammatic-visual")
        if (
            re.search(r"<(?:input|select|output|meter)\b", text, re.I)
            and re.search(r"<(?:figure|svg|dl|table)\b", text, re.I)
        ):
            features.append("estimator-or-calculator")
        if media_count_by_file.get(relative, 0) >= 3:
            features.append("multi-image-art-direction")
        if len(features) < 2:
            continue
        manual_review.append({
            "file": relative,
            "line": 1,
            "check": "concept-material-balance",
            "severity": "low",
            "reason": (
                "A clearly labeled concept combines a substantial presentation "
                "system with several missing identity inputs. The disclosure is "
                "honest; the remaining question is whether design sophistication "
                "has outrun approved project material."
            ),
            "evidence": {
                "section_count": len(sections),
                "showcase_features": features,
                "missing_identity_signals": missing,
            },
            "suggestion": (
                "Ground conspicuous copy, scenes, interactions, and figures in "
                "real client material where available; keep the concept more "
                "restrained where that material is still missing."
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
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    findings: list[dict[str, object]] = []
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
                    rule_id = (
                        "decorative-headline-span"
                        if tag.startswith("h")
                        else "decorative-display-fragment"
                    )
                    rule = next(item for item in RULES if item.id == rule_id)
                    findings.append({
                        "rule": rule_id,
                        "severity": rule.severity,
                        "classification": "advisory",
                        "file": relative,
                        "line": line,
                        "excerpt": plain[:160],
                        "matched_signal": signal,
                        "rationale": rule.rationale,
                        "suggestion": rule.suggestion,
                        "owner_policy": None,
                    })
                elif unresolved:
                    manual_review.append({
                        "file": relative,
                        "line": line,
                        "check": "prominent-fragment-dynamic-style",
                        "fragment": plain[:80],
                        "reason": (
                            "Prominent one- or two-word fragment uses a runtime-computed "
                            "class/style that static scanning cannot resolve."
                        ),
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
            rule = next(
                item for item in RULES
                if item.id == "decorative-display-fragment"
            )
            findings.append({
                "rule": rule.id,
                "severity": rule.severity,
                "classification": "advisory",
                "file": relative,
                "line": line_number(text, match.start()),
                "excerpt": " ".join(selector.split())[:160],
                "matched_signal": "prominent descendant selector sets a foreground color",
                "confidence": "selector-only; confirm fragment length and meaning in rendered use",
                "rationale": rule.rationale,
                "suggestion": rule.suggestion,
                "owner_policy": None,
            })
    return findings, manual_review


def hex_rgb(value: str) -> Optional[tuple[float, float, float]]:
    raw = value.lstrip("#")
    if len(raw) in {3, 4}:
        raw = "".join(character * 2 for character in raw[:3])
    elif len(raw) in {6, 8}:
        raw = raw[:6]
    else:
        return None
    try:
        channels = tuple(int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4))
    except ValueError:
        return None
    return channels


def srgb_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def oklch_from_hex(value: str) -> Optional[tuple[float, float, float]]:
    rgb = hex_rgb(value)
    if rgb is None:
        return None
    red, green, blue = (srgb_linear(channel) for channel in rgb)
    x = 0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue
    y = 0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue
    z = 0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue
    x_root, y_root, z_root = (
        math.copysign(abs(value_) ** (1 / 3), value_)
        for value_ in (x, y, z)
    )
    lightness = 0.2104542553 * x_root + 0.7936177850 * y_root - 0.0040720468 * z_root
    a_axis = 1.9779984951 * x_root - 2.4285922050 * y_root + 0.4505937099 * z_root
    b_axis = 0.0259040371 * x_root + 0.7827717662 * y_root - 0.8086757660 * z_root
    chroma = math.hypot(a_axis, b_axis)
    hue = math.degrees(math.atan2(b_axis, a_axis)) % 360
    return lightness, chroma, hue


def raw_palette_signals(corpus: str) -> dict[str, list[dict[str, object]]]:
    signals: dict[str, list[dict[str, object]]] = {"cream": [], "sage": []}
    seen: set[str] = set()
    for match in re.finditer(r"(?<![0-9A-Fa-f])#[0-9A-Fa-f]{3,8}\b", corpus):
        raw = match.group(0)
        canonical = raw.casefold()
        if canonical in seen:
            continue
        seen.add(canonical)
        converted = oklch_from_hex(raw)
        if converted is None:
            continue
        lightness, chroma, hue = converted
        detail = {
            "value": raw,
            "oklch": {
                "l": round(lightness, 4),
                "c": round(chroma, 4),
                "h": round(hue, 2),
            },
        }
        if lightness >= 0.88 and 0.012 <= chroma <= 0.09 and 55 <= hue <= 115:
            signals["cream"].append({"signal": "cream-color", **detail})
        if 0.25 <= lightness <= 0.78 and 0.025 <= chroma <= 0.16 and 115 <= hue <= 170:
            signals["sage"].append({"signal": "muted-green-color", **detail})
    cream_keyword = re.search(
        r"\b(?:cream|warm[-_ ]?(?:white|neutral)|beige)\b", corpus, re.I
    )
    sage_keyword = re.search(r"\b(?:sage|forest[-_ ]?green)\b", corpus, re.I)
    if cream_keyword:
        signals["cream"].append({
            "signal": "cream-keyword",
            "value": cream_keyword.group(0),
        })
    if sage_keyword:
        signals["sage"].append({
            "signal": "sage-keyword",
            "value": sage_keyword.group(0),
        })
    return signals


def markup_serif_utility_role(path: Path, text: str) -> Optional[str]:
    """Return a literal heading utility role, excluding source-code strings."""
    if path.suffix.lower() not in STATIC_MARKUP_SUFFIXES:
        return None
    index = 0
    while index < len(text):
        start = text.find("<", index)
        if start < 0:
            return None
        parsed = parse_markup_tag(text, start)
        if not parsed:
            index = start + 1
            continue
        end, kind, name, _ = parsed
        index = end
        if (
            kind != "open"
            or name not in {"h1", "h2", "h3"}
            or enclosing_source_literal(text, start, start + 1)
        ):
            continue
        tag = text[start:end]
        for class_match in re.finditer(
            r"\b(?:class|className)\s*=\s*(?:"
            r"(?P<quote>[\"'])(?P<quoted>[^\"']*)(?P=quote)"
            r"|(?P<unquoted>[^\s>{}]+))",
            tag,
            re.I,
        ):
            classes = (
                class_match.group("quoted")
                if class_match.group("quoted") is not None
                else class_match.group("unquoted")
            )
            if any(
                token.strip("!").casefold().split(":")[-1] == "font-serif"
                for token in classes.split()
            ):
                return " ".join(tag.split())[:160]
    return None


def compound_candidates(
    root: Path,
    groups: dict[Path, list[tuple[Path, str]]],
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    display_serif_role = re.compile(
        r"(?:"
        r"--[A-Za-z0-9_-]*(?:display|heading|headline|hero|editorial)"
        r"[A-Za-z0-9_-]*\s*:\s*[^;\n]{0,180}\bserif\b"
        r"|"
        r"(?:h[1-3]|[.#][A-Za-z0-9_-]*(?:display|heading|headline|hero|editorial)"
        r"[A-Za-z0-9_-]*)[^{]{0,100}\{[^}]{0,280}"
        r"(?:font-family|font)\s*:[^;}]{0,180}\bserif\b"
        r")",
        re.I,
    )
    saas_patterns = (
        ("features", re.compile(r"\bfeatures?\b", re.I)),
        ("testimonials", re.compile(r"\btestimonials?\b", re.I)),
        ("faq", re.compile(r"\bfaq\b|frequently asked", re.I)),
        ("generic-cta", re.compile(r"\bget started\b|\bstart (?:today|now)\b", re.I)),
    )
    for group in sorted(groups, key=lambda item: item.as_posix()):
        sources = sorted(
            groups[group],
            key=lambda item: item[0].relative_to(root).as_posix(),
        )
        corpus = "\n".join(text for _, text in sources)
        relative_group = group.relative_to(root).as_posix() or "."
        palette = raw_palette_signals(corpus)
        serif_roles = []
        for path, text in sources:
            css_role = display_serif_role.search(text)
            markup_role = markup_serif_utility_role(path, text)
            if css_role:
                serif_roles.append((
                    path,
                    " ".join(css_role.group(0).split())[:160],
                ))
            if markup_role:
                serif_roles.append((path, markup_role))
        serif_role = serif_roles[0] if serif_roles else None
        matched_signals: list[dict[str, object]] = []
        if palette["cream"]:
            matched_signals.append(palette["cream"][0])
        if serif_role:
            matched_signals.append({
                "signal": "display-serif-role",
                "value": serif_role[1],
            })
        if palette["sage"]:
            matched_signals.append(palette["sage"][0])
        if len(matched_signals) == 3:
            locations = sorted({
                path.relative_to(root).as_posix()
                for path, text in sources
                if (
                    display_serif_role.search(text)
                    or markup_serif_utility_role(path, text)
                    or raw_palette_signals(text)["cream"]
                    or raw_palette_signals(text)["sage"]
                )
            })
            findings.append({
                "rule": "cream-serif-sage-cluster",
                "severity": "medium",
                "classification": "advisory",
                "file": relative_group,
                "line": 1,
                "excerpt": (
                    "3/3 independently evaluated palette/type signals; files: "
                    + ", ".join(locations[:6])
                ),
                "matched_signals": matched_signals,
                "rationale": (
                    "Cream, display serif, and a muted green together are a "
                    "fashionable combination worth testing for project specificity."
                ),
                "suggestion": (
                    "Retain the combination only when real material and the intended "
                    "time register support it; do not swap motifs mechanically."
                ),
                "owner_policy": None,
            })

        saas_signals: list[dict[str, object]] = []
        for signal_name, pattern in saas_patterns:
            for match in pattern.finditer(corpus):
                if context_is_negative_or_example(corpus, match.start(), match.end()):
                    continue
                saas_signals.append({
                    "signal": signal_name,
                    "value": match.group(0),
                })
                break
        if len(saas_signals) >= 3:
            findings.append({
                "rule": "generic-saas-section-cluster",
                "severity": "medium",
                "classification": "advisory",
                "file": relative_group,
                "line": 1,
                "excerpt": (
                    f"{len(saas_signals)}/{len(saas_patterns)} non-negated "
                    "section signals in one route/component directory"
                ),
                "matched_signals": saas_signals,
                "rationale": (
                    "A feature/testimonial/FAQ/generic-CTA cluster can indicate an "
                    "information architecture inherited from a starter."
                ),
                "suggestion": (
                    "Derive section order from actual decisions, objections, proof, "
                    "and task sequence."
                ),
                "owner_policy": None,
            })
    return findings


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
            "fails closed unless an active owner acknowledgement covers that path. "
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
            "acknowledge skipped source paths."
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
        help="Owner policy; defaults to the policy bundled with this skill.",
    )
    parser.add_argument(
        "--type-watch",
        type=Path,
        help="Dated type-convergence policy; defaults to the policy bundled with this skill.",
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
            / "scan-allowlist.json"
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
            print(json.dumps({"ok": False, "error": {"code": "unsafe-project", "path": str(root)}}), file=sys.stderr)
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
        bundled_policy = Path(__file__).resolve().parents[1] / "policy"
        type_watch_path = args.type_watch or (bundled_policy / "type-convergence-watch.yml")
        type_rule, type_watch = load_type_watch(type_watch_path)
        rules = (*RULES, type_rule)
        compound_rule_ids = {"cream-serif-sage-cluster", "generic-saas-section-cluster"}
        (
            entries,
            expired_entries,
            skipped_acknowledgements,
            expired_skipped_acknowledgements,
        ) = load_allowlist(
            allowlist_path if args.allowlist or allowlist_path.is_file() else None,
            project=root,
            known_rules={rule.id for rule in rules} | compound_rule_ids,
            non_overridable_rules=NON_OVERRIDABLE_RULES,
        )
        owner_policy_path = args.owner_policy or (
            Path(__file__).resolve().parents[1]
            / "policy"
            / "owner-defaults.yml"
        )
        if not owner_policy_path.is_absolute() and args.owner_policy is not None:
            owner_policy_path = root / owner_policy_path
        owner_policy_path = Path(
            os.path.abspath(os.fspath(owner_policy_path.expanduser()))
        )
        policy = load_owner_policy(owner_policy_path)
        rule_policy_key = {
            "generic-gradient-text": "gradient_headline_text_without_semantic_or_brand_reason",
            "uniform-pill-language": "hierarchy_follows_content_and_task",
            "stock-fade-up": "motion_has_user_or_experience_purpose",
            "generic-hover-lift": "motion_has_user_or_experience_purpose",
            "repeated-decorative-section-label": "hierarchy_follows_content_and_task",
            "rhetorical-label-cluster": "hierarchy_follows_content_and_task",
            "decorative-headline-span": "arbitrary_headline_fragment_emphasis",
            "decorative-display-fragment": "arbitrary_prominent_copy_fragment_emphasis",
            "emoji-as-interface-icon": "semantic_maintainable_implementation",
            "placeholder-proof": "release_residue",
            "claim-needs-provenance": "fabricated_proof_or_business_facts",
            "generic-cta-copy": "hierarchy_follows_content_and_task",
            "repeated-sparkle-icon": "hierarchy_follows_content_and_task",
            "hardcoded-large-section-gap": "hierarchy_follows_content_and_task",
            "generic-saas-section-cluster": "hierarchy_follows_content_and_task",
            "presentation-script-comment-cluster": "release_residue",
            "quantitative-claim-density": "fabricated_proof_or_business_facts",
            "copy-uniformity-cluster": "hierarchy_follows_content_and_task",
            "parallel-route-skeleton": "hierarchy_follows_content_and_task",
            "material-media-review": "representation_and_cultural_context",
            "generated-media-authenticity": "representation_and_cultural_context",
            "media-authenticity-and-provenance": "representation_and_cultural_context",
            "concept-material-balance": "hierarchy_follows_content_and_task",
            "unexamined-default-font": "unexamined_generator_default_typography",
        }
        findings: list[dict[str, object]] = []
        suppressed_findings: list[dict[str, object]] = []
        pending: dict[str, list[dict[str, object]]] = {rule.id: [] for rule in rules}
        compound_groups: dict[Path, list[tuple[Path, str]]] = {}
        records: list[tuple[Path, str, str]] = []
        raw_records: list[tuple[Path, str, str]] = []
        skipped_files: list[str] = []
        skipped_oversized_files: list[str] = []
        skipped_sources: list[dict[str, object]] = []
        excluded_default_files: list[str] = []
        excluded_sensitive_structured_files: list[str] = []
        eligible_file_count = 0
        scan_suffixes = set(TEXT_SUFFIXES)
        if args.structured_content:
            scan_suffixes.update(STRUCTURED_CONTENT_SUFFIXES)
        for path in iter_files(root, scan_suffixes):
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
                if path.stat().st_size > MAX_TEXT_FILE_BYTES:
                    skipped_oversized_files.append(relative)
                    acknowledgement = skipped_acknowledgement(
                        relative, skipped_acknowledgements
                    )
                    skipped_sources.append({
                        "file": relative,
                        "reason": "source exceeds the 5 MiB scanner limit",
                        "acknowledged": acknowledgement is not None,
                        "acknowledgement": acknowledgement,
                    })
                    continue
                text = path.read_text(encoding="utf-8")
            except UnicodeError:
                skipped_files.append(relative)
                acknowledgement = skipped_acknowledgement(
                    relative, skipped_acknowledgements
                )
                skipped_sources.append({
                    "file": relative,
                    "reason": "source is not valid UTF-8",
                    "acknowledged": acknowledgement is not None,
                    "acknowledgement": acknowledgement,
                })
                continue
            except OSError as exc:
                raise RuntimeError(f"file-read-failed: {path}: {exc}") from exc
            raw_records.append((path, relative, text))
            scan_text = without_comments(text)
            records.append((path, relative, scan_text))
            if path.suffix.lower() != ".md":
                compound_groups.setdefault(path.parent, []).append((path, scan_text))
            for rule in rules:
                if rule.pattern is None:
                    continue
                for match in rule.pattern.finditer(scan_text):
                    proof_classification = None
                    if rule.id == "placeholder-proof":
                        proof_classification = classify_placeholder_proof(
                            path,
                            scan_text,
                            match.start(),
                            match.end(),
                            match.group(0),
                        )
                        if proof_classification is None:
                            continue
                    line = line_number(scan_text, match.start())
                    policy_value = policy.get(rule_policy_key.get(rule.id, ""), "")
                    excerpt = " ".join(match.group(0).split())[:160]
                    classification = rule.classification
                    matched_signal: object = match.group(0)
                    if rule.id == "placeholder-proof":
                        assert proof_classification is not None
                        classification, matched_signal = proof_classification
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
            if len(matches) < rule.min_occurrences:
                continue
            for finding in matches:
                suppression = allowlist_entry(finding, entries)
                if suppression:
                    suppressed_findings.append(
                        suppressed_finding(finding, suppression)
                    )
                    continue
                findings.append(finding)
        section_label_rule = next(
            rule
            for rule in rules
            if rule.id == "repeated-decorative-section-label"
        )
        section_label_instances = decorative_section_label_instances(records)
        section_label_findings = aggregate_label_candidates(
            section_label_instances,
            section_label_rule,
        )
        rhetorical_findings = rhetorical_label_candidates(
            section_label_instances
        )
        comment_findings = presentation_script_comment_candidates(raw_records)
        for raw_finding in (
            section_label_findings
            + rhetorical_findings
            + comment_findings
        ):
            finding = bind_finding(raw_finding)
            policy_value = policy.get(
                rule_policy_key.get(str(finding["rule"]), ""),
                "",
            )
            finding["owner_policy"] = policy_value or None
            suppression = allowlist_entry(finding, entries)
            if suppression:
                suppressed_findings.append(
                    suppressed_finding(finding, suppression)
                )
                continue
            findings.append(finding)
        shadcn_rule = next(
            rule for rule in rules if rule.id == "untouched-shadcn-token"
        )
        for raw_finding in current_shadcn_oklch_candidates(records, shadcn_rule):
            finding = bind_finding(raw_finding)
            suppression = allowlist_entry(finding, entries)
            if suppression:
                suppressed_findings.append(
                    suppressed_finding(finding, suppression)
                )
                continue
            findings.append(finding)
        css_classes = foreground_css_classes(records)
        style_objects = react_style_objects(records)
        fragment_findings, manual_review = prominent_fragment_candidates(
            records, css_classes, style_objects
        )
        for raw_finding in fragment_findings:
            finding = bind_finding(raw_finding)
            rule_id = str(finding["rule"])
            suppression = allowlist_entry(finding, entries)
            if suppression:
                suppressed_findings.append(
                    suppressed_finding(finding, suppression)
                )
                continue
            policy_value = policy.get(rule_policy_key.get(rule_id, ""), "")
            finding["owner_policy"] = policy_value or None
            findings.append(finding)
        quantitative_review, quantitative_evidence = (
            quantitative_claim_candidates(records)
        )
        media_review, media_count_by_file = material_media_candidates(records)
        manual_review.extend(quantitative_review)
        manual_review.extend(
            copy_uniformity_candidates(
                records,
                section_label_instances,
                quantitative_evidence,
            )
        )
        manual_review.extend(parallel_route_skeleton_candidates(records))
        manual_review.extend(media_review)
        manual_review.extend(
            concept_material_balance_candidates(
                records,
                media_count_by_file,
            )
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
        for raw_finding in compound_candidates(root, compound_groups):
            finding = bind_finding(raw_finding)
            policy_value = policy.get(
                rule_policy_key.get(str(finding["rule"]), ""),
                "",
            )
            finding["owner_policy"] = policy_value or None
            suppression = allowlist_entry(finding, entries)
            if suppression:
                suppressed_findings.append(
                    suppressed_finding(finding, suppression)
                )
                continue
            findings.append(finding)
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
        incomplete_failure = bool(unacknowledged_skipped_files)
        quality_passed = not policy_gate_failure and not incomplete_failure
        quality_status = (
            "failed"
            if policy_gate_failure
            else "incomplete"
            if incomplete_failure
            else "acknowledged-incomplete"
            if skipped_sources
            else "passed"
        )
        scope_excluded_count = (
            len(excluded_default_files)
            + len(excluded_sensitive_structured_files)
        )
        scope_status = (
            "incomplete"
            if skipped_sources
            else "scope-limited"
            if scope_excluded_count
            else "complete"
        )
        scan_scope_complete = not skipped_sources and scope_excluded_count == 0
        selected_scope_complete = not skipped_sources
        exit_policy_triggered = gate_enforced and (
            exit_gate_finding_failure or incomplete_failure
        )
        command_exit_code = 1 if exit_policy_triggered else 0
        result = {
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
            "project": str(root),
            "include_patterns": include_patterns,
            "documentation_mode": args.content_site,
            "structured_content_mode": args.structured_content,
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
                "dependency_vendor_exclusions": sorted(IGNORED_DIRS),
                "note": (
                    "Only listed text web-source suffixes are scanned. Runtime-generated "
                    "markup, dynamically rendered output, and unsupported languages "
                    "require manual review."
                ),
            },
            "allowlist": str(allowlist_path) if allowlist_path.is_file() else None,
            "owner_policy": str(owner_policy_path) if owner_policy_path.is_file() else None,
            "type_watch": type_watch,
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
                    eligible_file_count - scope_excluded_count
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
            print(json.dumps(result, indent=2, ensure_ascii=False))
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
                    f"owner={acknowledgement['owner']}; "
                    f"expires={acknowledgement['expires']}; "
                    f"reason={acknowledgement['reason']}"
                )
            for item in skipped_sources:
                acknowledgement = item["acknowledgement"]
                if acknowledgement:
                    print(
                        f"SKIPPED-ACKNOWLEDGED {item['file']} - "
                        f"{item['reason']}; owner={acknowledgement['owner']}; "
                        f"expires={acknowledgement['expires']}; "
                        f"acknowledgement={acknowledgement['reason']}"
                    )
                else:
                    print(
                        f"SKIPPED-UNACKNOWLEDGED {item['file']} - "
                        f"{item['reason']}"
                    )
            if skipped_sources:
                print(
                    f"INCOMPLETE scan: {len(skipped_sources)} relevant source "
                    f"file(s) skipped; {len(unacknowledged_skipped_files)} "
                    "unacknowledged."
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
            "ok": False,
            "execution_ok": False,
            "execution": {"status": "failed", "ok": False},
            "error": {"code": "scan-failed", "message": str(exc)},
        }), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
