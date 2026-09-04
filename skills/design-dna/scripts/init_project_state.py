#!/usr/bin/env python3
"""Safely create or validate project-local Design DNA state.

Runtime guarantees:
- requires Python 3.10 or newer and otherwise has no third-party dependencies;
- standard-library only; an installed Git CLI is queried read-only when
  restricted research state exists, with an explicit warning when unverified;
- never follows a symlink, junction, or other reparse point;
- stages the complete state before replacing anything;
- restores the prior state automatically if the final replacement fails;
- emits machine-readable errors on stderr.
"""

from __future__ import annotations

import argparse
import binascii
import errno
import hashlib
import importlib.util
import json
import math
import os
import re
import secrets
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
import unicodedata
import zlib
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import NoReturn
from urllib.parse import quote, unquote_to_bytes, urlsplit, urlunsplit


STATE_SCHEMA_VERSION = 2
RECORD_SCHEMA_VERSION = 1
ASSET_SCHEMA_VERSION = 2
EVIDENCE_CONTRACT_VERSION = 3
PROPORTIONAL_EVIDENCE_CONTRACT = "proportional-evidence-v1"
DIRECTION_CONTRACT_REFERENCE_SOURCED = "reference-sourced-organizing-logic-v1"
DIRECTION_CONTRACT_QUICK_EXEMPT = "quick-repair-exempt"
REFERENCE_SOURCE_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1]
    / "references"
    / "quality"
    / "public-reference-sources.json"
)
UNIVERSAL_EVIDENCE_ANCHORS = (
    "identity-intent",
    "truth-provenance",
    "responsive-accessibility-function",
    "rendered-review",
    "owner-release-state",
)
CORE_EVIDENCE_CAPABILITIES = {
    "asset-led",
    "batch-study",
    "connected-public-experience",
    "cultural-context",
    "direction-challenge",
    "enterprise-candidate",
    "high-risk",
    "numeric-rhetoric-integrity",
    "public-copy-integrity",
    "project-contrast",
    "range-study",
    "reference-led-direction",
}
CAPABILITY_PROFILE_COMMANDS = {
    "project-contrast": "--profile project-contrast",
    "direction-challenge": "--profile direction-challenge",
    "enterprise-candidate": "--profile enterprise-candidate",
    "high-risk": "--profile high-risk",
    "numeric-rhetoric-integrity": "--profile enterprise-candidate",
    "public-copy-integrity": "--profile enterprise-candidate",
    "reference-led-direction": "--profile enterprise-candidate",
}
EVIDENCE_CAPABILITY_PATTERN = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?"
)
EVIDENCE_EXTENSION_ID_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}"
)
EVIDENCE_EXTENSION_STATUSES = {"draft", "complete", "not-applicable"}
OWNER_RECURRENCE_TRIGGER = "owner-recurrence-requirement"
OWNER_PATTERN_TRIGGER = "owner-pattern-contract"
OWNER_RECURRENCE_RECORDS = ("project-contrast", "direction-challenge")
OWNER_RECURRENCE_CAPABILITIES = frozenset(OWNER_RECURRENCE_RECORDS)
INITIALIZATION_TRIGGERS = {OWNER_RECURRENCE_TRIGGER, OWNER_PATTERN_TRIGGER}
TRIGGER_EVIDENCE_CAPABILITIES = {
    OWNER_RECURRENCE_TRIGGER: (
        "project-contrast",
        "direction-challenge",
    ),
    OWNER_PATTERN_TRIGGER: (
        "project-contrast",
        "direction-challenge",
    ),
}
TRIGGER_RECORDS = {
    OWNER_RECURRENCE_TRIGGER: (
        "project-contrast",
        "direction-challenge",
    ),
    OWNER_PATTERN_TRIGGER: (
        "project-contrast",
        "direction-challenge",
    ),
}
VISUAL_FINDINGS_CONTRACT = "visual-review-findings-v2"
VISUAL_FINDINGS_HEADERS = (
    "Severity",
    "Confidence",
    "Evidence",
    "User/release impact",
    "Cause",
    "Fix or disposition",
    "Rerun verification",
    "Status",
    "Owner",
)
LEGACY_VISUAL_FINDINGS_HEADERS = (
    "Severity",
    "Evidence",
    "Cause",
    "Fix",
    "Verification",
    "Status",
)
DESIGN_DNA_22_VISUAL_FINDINGS_HEADERS = (
    "Severity",
    "Confidence",
    "Evidence",
    "User/release impact",
    "Cause",
    "Fix",
    "Rerun verification",
    "Status/owner",
)
VISUAL_SEVERITIES = {"critical", "high", "medium", "low", "note"}
VISUAL_CONFIDENCES = {"high", "medium", "low"}
VISUAL_FINDING_STATUSES = {
    "open",
    "fixed-unverified",
    "verified",
    "accepted-risk",
    "deferred",
    "blocked",
    "not-applicable",
}
UNRESOLVED_VISUAL_STATUSES = {"open", "fixed-unverified", "blocked"}
LOCK_FILE_NAME = ".design-dna.lock"
LOCK_RECORD_LIMIT = 32_768
DEFAULT_LOCK_TIMEOUT_SECONDS = 3.0
MAX_LOCK_TIMEOUT_SECONDS = 30.0
STAGE_OWNER_RECORD = ".design-dna-stage-owner.json"
MAX_STATE_IDENTITY_ENTRIES = 100_000
SEMVER = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
RECORD_TEMPLATES = {
    "exploration": ("exploration.md", "exploration-template.md"),
    "taste-calibration": (
        "taste-calibration.md", "taste-calibration-template.md",
    ),
    "reference-dossier": (
        "reference-dossier.md", "reference-dossier-template.md",
    ),
    "route-manifest": (
        "route-manifest.json", "route-manifest-template.json",
    ),
    "direction": ("direction.md", "direction-template.md"),
    "direction-proof": ("direction-proof.md", "direction-proof-template.md"),
    "route-family": ("route-family.json", "route-family-template.json"),
    "batch-range": ("batch-range.json", "batch-range-template.json"),
    "project-contrast": (
        "project-contrast.json", "project-contrast-template.json",
    ),
    "direction-challenge": (
        "direction-challenge.json", "direction-challenge-template.json",
    ),
    "connected-public-experience": (
        "connected-public-experience.json",
        "connected-public-experience-template.json",
    ),
    "visual-review": ("visual-review.md", "visual-review-template.md"),
    "claims": ("claims.md", "claim-ledger-template.md"),
    "assets": ("assets.yml", "asset-manifest.yml"),
    "user-validation": ("user-validation.md", "user-validation-template.md"),
    "handoff": ("handoff.md", "handoff-template.md"),
}
PROFILES = {
    "quick": ("direction", "visual-review"),
    "substantial": ("direction", "visual-review"),
    "greenfield": ("direction", "visual-review"),
    "standard": ("direction", "visual-review"),
    "enterprise-candidate": (
        "direction", "reference-dossier", "route-manifest", "visual-review",
    ),
    "connected-public-experience": (
        "direction",
        "connected-public-experience",
        "visual-review",
    ),
    "showcase": (
        "exploration",
        "taste-calibration",
        "direction",
        "reference-dossier",
        "route-manifest",
        "direction-proof",
        "visual-review",
    ),
    "project-contrast": (
        "direction",
        "reference-dossier",
        "route-manifest",
        "project-contrast",
        "visual-review",
    ),
    "direction-challenge": (
        "exploration",
        "taste-calibration",
        "direction",
        "reference-dossier",
        "route-manifest",
        "direction-challenge",
        "direction-proof",
        "visual-review",
    ),
    "range-study": (
        "exploration",
        "direction",
        "direction-proof",
        "route-family",
        "visual-review",
    ),
    "batch-study": (
        "exploration",
        "direction",
        "direction-proof",
        "batch-range",
        "visual-review",
    ),
    "high-risk": (
        "direction", "visual-review", "claims", "user-validation",
    ),
    "validation": ("user-validation",),
    "asset-led": ("assets",),
    "full": tuple(RECORD_TEMPLATES),
}
PERSISTED_PROFILES = {*PROFILES, "custom"}
CANONICAL_ASSURANCE_PROFILES = {
    "quick",
    "standard",
    "enterprise-candidate",
    "showcase",
    "connected-public-experience",
    "direction-challenge",
    "project-contrast",
    "range-study",
    "batch-study",
    "high-risk",
    "asset-led",
}
ASSURANCE_PROFILE_ORDER = (
    "quick",
    "standard",
    "enterprise-candidate",
    "showcase",
    "connected-public-experience",
    "direction-challenge",
    "project-contrast",
    "range-study",
    "batch-study",
    "high-risk",
    "asset-led",
)
REQUEST_PROFILE_ASSURANCE = {
    "quick": ("quick",),
    "substantial": ("standard",),
    "standard": ("standard",),
    "enterprise-candidate": ("standard", "enterprise-candidate"),
    "greenfield": ("standard",),
    # A Showcase or multi-root public direction is an addition to the fresh
    # public-site baseline, never a way to drop it.  Persist the cumulative
    # profiles explicitly so downstream tools and humans can see that the
    # reference dossier, public-copy review, and Enterprise Candidate closure
    # still apply.
    "showcase": ("standard", "enterprise-candidate", "showcase"),
    "connected-public-experience": (
        "standard", "connected-public-experience",
    ),
    "direction-challenge": (
        "standard", "enterprise-candidate", "showcase", "direction-challenge",
    ),
    "project-contrast": (
        "standard", "enterprise-candidate", "project-contrast",
    ),
    "range-study": ("standard", "range-study"),
    "batch-study": ("standard", "batch-study"),
    "high-risk": ("standard", "high-risk"),
    # The compatibility validation preset selects one supplemental research
    # record.  It is not a declaration that the project is High-risk.
    "validation": ("standard",),
    "asset-led": ("asset-led",),
    "full": (
        "showcase", "enterprise-candidate", "connected-public-experience", "direction-challenge",
        "project-contrast", "range-study", "batch-study", "high-risk",
        "asset-led",
    ),
}


def normalize_assurance_profiles(
    profiles: list[str] | tuple[str, ...] | set[str],
) -> tuple[str, ...]:
    if not all(isinstance(profile, str) for profile in profiles):
        raise StateError(
            "invalid-assurance-profiles",
            "Assurance profiles must be strings.",
        )
    observed = set(profiles)
    unknown = observed - CANONICAL_ASSURANCE_PROFILES
    if unknown:
        raise StateError(
            "invalid-assurance-profiles",
            "Unsupported assurance profiles: "
            + ", ".join(sorted(unknown))
            + ".",
        )
    # Profiles are cumulative contracts.  Normalize both new requests and
    # persisted legacy state toward the complete prerequisite set so an old
    # `showcase` or `direction-challenge` label cannot silently waive the
    # reference-led public-site baseline on migration or readiness checks.
    if "direction-challenge" in observed:
        observed.update({"showcase", "enterprise-candidate", "standard"})
    if "showcase" in observed:
        observed.update({"enterprise-candidate", "standard"})
    if "project-contrast" in observed:
        observed.update({"enterprise-candidate", "standard"})
    if "enterprise-candidate" in observed:
        observed.add("standard")
    if observed & {
        "connected-public-experience", "range-study", "batch-study", "high-risk"
    }:
        observed.add("standard")
    if observed - {"quick"}:
        observed.discard("quick")
    if not observed:
        observed.add("standard")
    return tuple(
        profile
        for profile in ASSURANCE_PROFILE_ORDER
        if profile in observed
    )


def infer_assurance_profiles(
    records: list[str] | tuple[str, ...],
) -> tuple[str, ...]:
    observed = set(records)
    profiles: set[str] = set()
    if observed & {"exploration", "direction-proof"}:
        profiles.add("standard")
    if "connected-public-experience" in observed:
        profiles.update({"standard", "connected-public-experience"})
    if "route-family" in observed:
        profiles.update({"standard", "range-study"})
    if "batch-range" in observed:
        profiles.update({"standard", "batch-study"})
    if "project-contrast" in observed:
        profiles.update({"standard", "project-contrast"})
    if "direction-challenge" in observed:
        profiles.update({"standard", "direction-challenge"})
    # Claim and user-validation records can be useful on an otherwise ordinary
    # project. Their presence (individually or together) is not a risk
    # classification. Only an explicit --profile high-risk declaration, or an
    # already-persisted High-risk state retained during merge/migration, creates
    # the High-risk capability and its complete companion-record obligations.
    if "assets" in observed:
        profiles.add("asset-led")
    if observed & {"direction", "visual-review", "handoff"}:
        profiles.add("standard")
    if not profiles:
        profiles.add("standard")
    return normalize_assurance_profiles(profiles)


def assurance_profiles_for_request(
    requested: str,
    records: tuple[str, ...],
) -> tuple[str, ...]:
    if requested == "custom":
        return infer_assurance_profiles(records)
    if requested not in REQUEST_PROFILE_ASSURANCE:
        raise StateError(
            "invalid-assurance-profile",
            f"Unsupported assurance profile: {requested}.",
        )
    return normalize_assurance_profiles(
        list(REQUEST_PROFILE_ASSURANCE[requested])
    )


def merged_assurance_profiles(
    existing: list[str] | tuple[str, ...],
    requested: list[str] | tuple[str, ...],
    records: list[str] | tuple[str, ...],
) -> tuple[str, ...]:
    return normalize_assurance_profiles(
        [
            *existing,
            *requested,
            *infer_assurance_profiles(records),
        ]
    )


def contract_declares_capability(payload: object, capability: str) -> bool:
    """Read a legacy capability declaration without treating records as intent.

    This deliberately answers only whether the persisted contract named a
    capability.  It does not try to reverse-engineer intent from a partial
    inventory of supplemental records, because that guess could silently lower
    a consequential assurance declaration during migration.
    """

    return (
        isinstance(payload, dict)
        and isinstance(payload.get("applicable_capabilities"), list)
        and capability in payload["applicable_capabilities"]
    )


def require_capability_profile_consistency(
    capabilities: tuple[str, ...] | list[str] | set[str],
    assurance_profiles: tuple[str, ...] | list[str] | set[str],
) -> None:
    """Keep a High-risk evidence gate bound to its explicit assurance profile."""

    normalized_profiles = set(normalize_assurance_profiles(assurance_profiles))
    if "high-risk" in set(capabilities) and "high-risk" not in normalized_profiles:
        raise StateError(
            "high-risk-profile-required",
            (
                "High-risk evidence requires the high-risk assurance profile. "
                "Use --profile high-risk; it initializes direction, visual-review, "
                "claims, and user-validation together."
            ),
        )


def inferred_evidence_capabilities(
    assurance_profiles: tuple[str, ...] | list[str] | set[str],
) -> tuple[str, ...]:
    """Map assurance profiles to evidence gates without prescribing design."""

    observed = set(assurance_profiles)
    capabilities = [
        capability
        for capability in (
            "project-contrast", "direction-challenge",
            "enterprise-candidate",
            "connected-public-experience", "range-study", "batch-study",
            "high-risk", "asset-led",
        )
        if capability in observed
    ]
    if "enterprise-candidate" in observed:
        capabilities.append("public-copy-integrity")
        capabilities.append("numeric-rhetoric-integrity")
        capabilities.append("reference-led-direction")
    return tuple(capabilities)


def normalize_evidence_capabilities(
    capabilities: tuple[str, ...] | list[str] | set[str],
) -> tuple[str, ...]:
    if not all(isinstance(item, str) for item in capabilities):
        raise StateError(
            "invalid-evidence-capabilities",
            "Evidence capabilities must be lowercase slug strings.",
        )
    normalized = tuple(dict.fromkeys(capabilities))
    invalid = [
        item
        for item in normalized
        if not EVIDENCE_CAPABILITY_PATTERN.fullmatch(item)
    ]
    if invalid:
        raise StateError(
            "invalid-evidence-capabilities",
            "Invalid evidence capabilities: " + ", ".join(sorted(invalid)) + ".",
        )
    return normalized


def expand_enterprise_candidate_requirements(
    capabilities: tuple[str, ...] | list[str] | set[str],
) -> tuple[str, ...]:
    """Keep public candidate evidence gates coupled to enterprise review."""

    expanded = list(dict.fromkeys(capabilities))
    if "enterprise-candidate" in expanded:
        for capability in (
            "public-copy-integrity",
            "numeric-rhetoric-integrity",
            "reference-led-direction",
        ):
            if capability not in expanded:
                expanded.append(capability)
    return tuple(expanded)


def missing_capability_records(
    capability: str,
    records: tuple[str, ...] | list[str] | set[str],
) -> tuple[str, ...]:
    """Return canonical records a selected capability still lacks."""

    return tuple(
        sorted(CAPABILITY_REQUIRED_RECORDS.get(capability, set()) - set(records))
    )


def require_capability_record_selection(
    capabilities: tuple[str, ...] | list[str] | set[str],
    records: tuple[str, ...] | list[str] | set[str],
) -> None:
    """Reject capability-only selections that could create broken state."""

    for capability in capabilities:
        profile_command = CAPABILITY_PROFILE_COMMANDS.get(capability)
        if capability == "high-risk":
            raise StateError(
                "high-risk-profile-required",
                (
                    "High-risk evidence is selected only by "
                    f"{profile_command}; "
                    "that preset initializes direction, visual-review, claims, "
                    "and user-validation together."
                ),
            )
        if profile_command is None or not missing_capability_records(capability, records):
            continue
        raise StateError(
            "evidence-capability-record-required",
            (
                f"Evidence capability {capability} requires its canonical record. "
                f"Use {profile_command} instead of --evidence-capability "
                f"{capability}."
            ),
        )


def evidence_contract_payload(
    assurance_profiles: tuple[str, ...],
    requested_capabilities: tuple[str, ...] | list[str] = (),
    extension_records: tuple[dict[str, object], ...] | list[dict[str, object]] = (),
) -> dict[str, object]:
    canonical_profiles = normalize_assurance_profiles(assurance_profiles)
    capabilities = normalize_evidence_capabilities(
        expand_enterprise_candidate_requirements([
            *inferred_evidence_capabilities(canonical_profiles),
            *requested_capabilities,
        ])
    )
    require_capability_profile_consistency(capabilities, canonical_profiles)
    return {
        "version": EVIDENCE_CONTRACT_VERSION,
        "universal_anchors": list(UNIVERSAL_EVIDENCE_ANCHORS),
        "direction_contract": (
            DIRECTION_CONTRACT_QUICK_EXEMPT
            if canonical_profiles == ("quick",)
            else DIRECTION_CONTRACT_REFERENCE_SOURCED
        ),
        "applicable_capabilities": list(capabilities),
        "extension_records": list(extension_records),
    }


def validate_evidence_contract(
    payload: object,
    assurance_profiles: tuple[str, ...],
) -> tuple[tuple[str, ...], list[dict[str, object]]]:
    """Validate the proportional contract and return capabilities/extensions."""

    if not isinstance(payload, dict) or set(payload) != {
        "version",
        "universal_anchors",
        "direction_contract",
        "applicable_capabilities",
        "extension_records",
    }:
        raise StateError(
            "invalid-evidence-contract",
            "evidence_contract must use the versioned proportional shape.",
        )
    if payload.get("version") != EVIDENCE_CONTRACT_VERSION:
        raise StateError(
            "invalid-evidence-contract",
            "evidence_contract has an unsupported version.",
        )
    anchors = payload.get("universal_anchors")
    if anchors != list(UNIVERSAL_EVIDENCE_ANCHORS):
        raise StateError(
            "invalid-evidence-contract",
            "evidence_contract must retain the five universal evidence anchors.",
        )
    expected_direction_contract = (
        DIRECTION_CONTRACT_QUICK_EXEMPT
        if normalize_assurance_profiles(assurance_profiles) == ("quick",)
        else DIRECTION_CONTRACT_REFERENCE_SOURCED
    )
    if payload.get("direction_contract") != expected_direction_contract:
        raise StateError(
            "invalid-evidence-contract",
            "evidence_contract direction_contract does not match the "
            "assurance profiles.",
        )
    raw_capabilities = payload.get("applicable_capabilities")
    if (
        not isinstance(raw_capabilities, list)
        or len(raw_capabilities) != len(set(raw_capabilities))
    ):
        raise StateError(
            "invalid-evidence-contract",
            "applicable_capabilities must be a unique list.",
        )
    capabilities = normalize_evidence_capabilities(raw_capabilities)
    if (
        "enterprise-candidate" in capabilities
        and "public-copy-integrity" not in capabilities
    ):
        raise StateError(
            "invalid-evidence-contract",
            "enterprise-candidate requires public-copy-integrity.",
        )
    if (
        "enterprise-candidate" in capabilities
        and "numeric-rhetoric-integrity" not in capabilities
    ):
        raise StateError(
            "invalid-evidence-contract",
            "enterprise-candidate requires numeric-rhetoric-integrity.",
        )
    if (
        "enterprise-candidate" in capabilities
        and "reference-led-direction" not in capabilities
    ):
        raise StateError(
            "invalid-evidence-contract",
            "enterprise-candidate requires reference-led-direction.",
        )
    require_capability_profile_consistency(capabilities, assurance_profiles)
    implied = set(inferred_evidence_capabilities(assurance_profiles))
    if not implied.issubset(capabilities):
        raise StateError(
            "invalid-evidence-contract",
            "evidence_contract omits capabilities implied by assurance_profiles.",
        )
    raw_extensions = payload.get("extension_records")
    if not isinstance(raw_extensions, list):
        raise StateError(
            "invalid-evidence-contract",
            "extension_records must be a list.",
        )
    extensions: list[dict[str, object]] = []
    observed_ids: set[str] = set()
    for index, extension in enumerate(raw_extensions):
        label = f"extension_records[{index}]"
        if not isinstance(extension, dict) or set(extension) != {
            "id",
            "purpose",
            "applies_to",
            "status",
            "owner",
            "evidence",
        }:
            raise StateError(
                "invalid-evidence-extension",
                f"{label} has an unsupported shape.",
            )
        extension_id = extension.get("id")
        if (
            not isinstance(extension_id, str)
            or not EVIDENCE_EXTENSION_ID_PATTERN.fullmatch(extension_id)
            or extension_id in observed_ids
        ):
            raise StateError(
                "invalid-evidence-extension",
                f"{label}.id must be a unique stable ID.",
            )
        observed_ids.add(extension_id)
        purpose = extension.get("purpose")
        owner = extension.get("owner")
        status = extension.get("status")
        applies_to = extension.get("applies_to")
        evidence = extension.get("evidence")
        if not isinstance(purpose, str) or len(purpose.strip()) < 12:
            raise StateError(
                "invalid-evidence-extension",
                f"{label}.purpose must explain the project-specific need.",
            )
        if not isinstance(owner, str) or not non_placeholder(owner):
            raise StateError(
                "invalid-evidence-extension",
                f"{label}.owner must identify an accountable owner.",
            )
        if status not in EVIDENCE_EXTENSION_STATUSES:
            raise StateError(
                "invalid-evidence-extension",
                f"{label}.status is unsupported.",
            )
        if (
            not isinstance(applies_to, list)
            or not applies_to
            or not all(
                isinstance(item, str)
                and EVIDENCE_CAPABILITY_PATTERN.fullmatch(item)
                for item in applies_to
            )
            or len(applies_to) != len(set(applies_to))
        ):
            raise StateError(
                "invalid-evidence-extension",
                f"{label}.applies_to must be a unique nonempty slug list.",
            )
        if (
            not isinstance(evidence, list)
            or not all(isinstance(item, str) and item.strip() for item in evidence)
        ):
            raise StateError(
                "invalid-evidence-extension",
                f"{label}.evidence must be a list of nonempty references.",
            )
        if status == "complete" and not evidence:
            raise StateError(
                "invalid-evidence-extension",
                f"{label} cannot be complete without evidence.",
            )
        extensions.append(extension)
    return capabilities, extensions


def migrate_evidence_contract(
    payload: object,
    assurance_profiles: tuple[str, ...],
) -> tuple[tuple[str, ...], list[dict[str, object]]]:
    """Upgrade the exact prior proportional state contract without data loss."""

    prior_keys = {
        "version",
        "universal_anchors",
        "applicable_capabilities",
        "extension_records",
    }
    if (
        isinstance(payload, dict)
        and set(payload) == prior_keys
        and payload.get("version") == 1
    ):
        upgraded = dict(payload)
        upgraded["version"] = EVIDENCE_CONTRACT_VERSION
        upgraded["direction_contract"] = (
            DIRECTION_CONTRACT_QUICK_EXEMPT
            if normalize_assurance_profiles(assurance_profiles) == ("quick",)
            else DIRECTION_CONTRACT_REFERENCE_SOURCED
        )
    elif isinstance(payload, dict):
        upgraded = dict(payload)
        if upgraded.get("version") == 2:
            upgraded["version"] = EVIDENCE_CONTRACT_VERSION
            upgraded["direction_contract"] = (
                DIRECTION_CONTRACT_QUICK_EXEMPT
                if normalize_assurance_profiles(assurance_profiles) == ("quick",)
                else DIRECTION_CONTRACT_REFERENCE_SOURCED
            )
    else:
        return validate_evidence_contract(payload, assurance_profiles)

    # A persisted assurance profile is authoritative.  Bring an older contract
    # forward by adding its implied gates, never by dropping that profile when
    # a historical inventory is incomplete.
    raw_capabilities = upgraded.get("applicable_capabilities")
    if isinstance(raw_capabilities, list):
        upgraded["applicable_capabilities"] = list(
            dict.fromkeys(
                [
                    *raw_capabilities,
                    *inferred_evidence_capabilities(assurance_profiles),
                ]
            )
        )
    return validate_evidence_contract(upgraded, assurance_profiles)
FRONTMATTER_FILES = {
    "claims.md", "direction.md", "direction-proof.md", "exploration.md",
    "taste-calibration.md", "reference-dossier.md",
    "visual-review.md", "user-validation.md", "handoff.md",
}
SUBSTANTIVE_RECORDS = {
    "exploration.md": "exploration",
    "taste-calibration.md": "taste-calibration",
    "reference-dossier.md": "reference-dossier",
    "claims.md": "claims",
    "direction.md": "direction",
    "direction-proof.md": "direction-proof",
    "visual-review.md": "visual-review",
    "user-validation.md": "user-validation",
    "handoff.md": "handoff",
}
SUBSTANTIVE_TEMPLATE_FILES = {
    "exploration-template.md",
    "taste-calibration-template.md",
    "reference-dossier-template.md",
    "claim-ledger-template.md",
    "direction-template.md",
    "direction-proof-template.md",
    "visual-review-template.md",
    "user-validation-template.md",
    "handoff-template.md",
}
RECORD_STATUSES = {"draft", "complete"}
COMPLETE_RECORD_FIELDS = {
    "record_body_sha256",
    "binding_kind",
    "binding_id",
    "binding_path",
    "binding_sha256",
    "completion_owner",
    "completed_at",
    "unresolved_high",
    "unresolved_medium",
    "limitations",
}
GENERIC_METADATA_VALUES = {
    "",
    "pending",
    "placeholder",
    "tbd",
    "todo",
    "unknown",
    "owner",
    "reviewer",
    "maintainer",
    "n/a",
}
LEGACY_REQUIRED_RECORD_SECTIONS = {
    "exploration": {
        "Decision bounds",
        "Subject and reference evidence",
        "Candidate field",
        "Proof comparison",
        "Selection",
    },
    "taste-calibration": {
        "Record lifecycle and evidence boundary",
        "Public encounter and project read",
        "Reference dossier",
        "Direction proof",
        "First-impression and surface-fidelity response",
        "Disposition",
    },
    "reference-dossier": {
        "Research frame",
        "Candidate comparison",
        "Strong references",
        "Negative counterexamples",
        "Selected synthesis",
        "Route manifest",
        "Sequence reads",
        "Signature transfer",
        "Component sources",
    },
    "direction": {
        "Identity and outcome",
        "Constraint ledger",
        "Routes, flows, and states",
        "Evidence, content, and authority",
        "Research and exploration",
        "Source mappings and observable decisions",
        "System and implementation",
        "Quality and specialist contracts",
        "Acceptance",
    },
    "direction-proof": {
        "Identity",
        "Constraints and assumptions",
        "Reference mappings under test",
        "Proof evidence",
        "Perception and decision test",
        "Outcome",
    },
    "visual-review": {
        "Build identity",
        "Coverage matrix",
        "Perception review",
        "Implementation review",
        "Temporal evidence",
        "Truth, assets, and cultural context",
        "Performance",
        "Findings",
        "Completion",
    },
    "claims": {
        "Claims",
        "Calculators and derived outputs",
        "Closure",
    },
    "user-validation": {
        "Study",
        "Measures and method",
        "Participants",
        "Tasks and observations",
        "Findings and decisions",
        "Limits",
        "Completion",
    },
    "handoff": {
        "Identity and scope",
        "Sources of truth and authority",
        "Source mappings and design decisions",
        "System lifecycle",
        "Operations",
        "Verification",
        "Open decisions",
    },
}
LEGACY_REQUIRED_RECORD_LABELS = {
    "exploration": (
        "Project, source-packet version, and date",
        "Audience, situation, and primary task or invitation",
        "Consequential question this exploration must expose",
        "Project-specific success and failure conditions",
        "Owner preferences, rejections, and exact scope",
        "Representative content, route/flow/state, and evidence",
        "Exploration depth and why it is proportionate",
        (
            "Real content, language, objects, people, behavior, place, data, "
            "rituals, materials, or other project evidence"
        ),
        (
            "Cultural, rights, access, technical, production, and maintenance "
            "boundaries"
        ),
        "Research or evidence not available",
        "Why the field is sufficient to challenge the first default",
        (
            "Which candidates are materially different answers rather than "
            "surface substitutions"
        ),
        "Comparison performed, partially performed, or not performed",
        "Conditions held constant and conditions intentionally different",
        (
            "Project-specific perception, task, visual, cultural, accessibility, "
            "performance, or maintenance observations"
        ),
        "Unproven behavior or missing evidence",
        "Decision",
        "Selected candidate ID and source mapping",
        "Why it best fits the actual brief and constraints",
        "Why alternatives lost without creating global bans",
        "Accountable-owner disposition",
        "Reversible checkpoint",
        "Selected proof identity and artifact",
        "Fatal assumption, unresolved owner decision, or release block",
    ),
    "taste-calibration": (),
    "reference-dossier": (),
    "direction": (
        "Project, candidate/build, and date",
        "Accountable owner and decision scope",
        "Audience and situation",
        "Primary task, invitation, or editorial outcome",
        "Project-specific success conditions",
        "Requested visual or experiential qualities in the owner's language",
        "Known owner preferences, rejections, and their exact scope",
        "Critical unknowns or risks",
        "Release intent",
        "Assurance profile and why it fits",
        "Approved identity and recognition assets",
        "Existing system and repository decisions to preserve",
        (
            "Subject material: language, behavior, objects, people, place, data, "
            "rituals, textures, constraints, or other project evidence"
        ),
        (
            "Media approach, rights, provenance, generated status, and "
            "unresolved needs"
        ),
        "Claim-ledger scope",
        "Open assumptions and reversible treatment",
        "Content and maintenance owners",
        "Consequential design question",
        "Exploration depth and why it was sufficient for uncertainty and stakes",
        "Candidate identities and directly reviewable proof",
        "What the comparison changed",
        "Research or proof not performed and why",
        "`source_mapping_id`",
        "`mapped_relationship`",
        "`source_evidence`",
        "`limits`",
        "`status`",
        "`extensions`",
        (
            "Sources of truth for facts, identity, design, components, behavior, "
            "and release state"
        ),
        "Reusable foundations and decisions",
        "Route-, component-, campaign-, or content-local decisions",
        "Intentional one-offs and optical exceptions",
        (
            "Type files, rights, script coverage, fallbacks, loading, and "
            "rendered specimen evidence relevant to this project"
        ),
        "Protected facts, files, components, assets, tokens, and integrations",
        "Public disclosure and internal-record boundary",
        "Maintenance, migration, and regression expectations",
        (
            "Accessibility target, applicable conditions, evidence, and "
            "specialist owner"
        ),
        (
            "Performance objectives, production-like context, evidence, and "
            "lifecycle owner"
        ),
        "Browser, device, input, locale, directionality, and content constraints",
        "Privacy, security, legal, data, analytics, embeds, and deployment authority",
        "Required specialist gates and dimensions still unverified",
        "Conflict arbitration among design and specialist requirements",
        "Versioned checkpoint and rollback boundary",
        "Exact candidate/build under review",
        (
            "Required route, state, content, viewport, input, language, "
            "preference, and failure coverage"
        ),
        (
            "Functional, visual, content, accessibility, performance, "
            "engineering, cultural, and operational checks that actually apply"
        ),
        "Observable-decision results and unresolved deviations",
        "Accountable-owner visual disposition, date, scope, and evidence",
        "Open high/medium findings, owners, and release blockers",
        "Honest final readiness statement",
    ),
    "direction-proof": (
        "Candidate and source mapping ID",
        "Direction/exploration record and source-packet identity",
        "Candidate/build ID and reversible checkpoint",
        "Route, flow, state, and purpose of this proof",
        "Exact decision this artifact must settle",
        "Accountable owner and decision scope",
        "Reviewer, relationship, prior exposure, and date",
        "`mapped_relationship`",
        "`source_evidence`",
        "`limits`",
        "`extensions`",
        "Real content and representative data/media used",
        "Labeled placeholders and unresolved dependencies",
        "Rendered artifacts, route/state, viewport, preference, path, and SHA-256",
        (
            "Source/content/media/font identity needed to reproduce the artifact"
        ),
        (
            "Relevant accessibility, performance, responsive, input, "
            "localization, reduced, unsupported, loading, and failure evidence"
        ),
        "Previous accepted baseline or compared candidate and exact difference",
        "Intended project-specific success conditions",
        "What the reviewer understood or expected",
        "Which observable decisions succeeded or failed",
        "Project or owner preference evidence",
        "Truth, rights, access, feasibility, and maintenance result",
        "Conditions not tested and why",
        "Decision",
        "Evidence and rationale",
        "Comparable candidates reviewed, or why one direction was sufficient",
        "Required revisions and exact rerender",
        "Decisions protected for implementation",
        "Proof-to-build delta ledger required",
        "Perceptual status",
        "Accountable-owner rendered acceptance",
        "Owner decision claim scope",
        "Owner ID, exact candidate/build ID, review date, and evidence path/hash",
    ),
    "visual-review": (
        "Build, commit, or artifact ID",
        "Assurance profile and rationale",
        "Source/workspace identity and SHA-256",
        "Route or preview URL",
        "Date and final implementation round reviewed",
        "Reviewers, relationship, and lens",
        "Rendered-review report path, hash, contract, and execution result",
        (
            "Cross-build comparison identity, compatibility, changed captures, "
            "reviewer, and result, or `not performed`"
        ),
        "Coverage contact sheet or artifact index",
        "Bound direction, exploration, source mappings, and proof-to-build records",
        "Review order and any unavoidable exposure to the brief, rationale, scanner",
        "Project-specific success conditions and owner anti-traits",
        "What an unbriefed reviewer understands or expects",
        "What feels specific, convincing, beautiful, useful, or worth protecting",
        "What feels generic, confusing, excessive, unfinished, wrong, or too restrained",
        "Project material and owner-preference evidence",
        "Comparison with selected candidate/proof or previous accepted baseline",
        "Source-of-truth and design/code mapping confidence",
        "Claim-ledger coverage",
        (
            "Asset manifest, source, rights, attribution, edits, generated "
            "status, disclosure, privacy, approval, and expiry"
        ),
        "Documentary versus illustrative status and visible artifacts",
        "Demo, concept, placeholder, scenario, or unavailable capability treatment",
        "Third parties, integrations, tracking, consent, and embeds",
        (
            "Security, privacy, legal, data, deployment, and operational "
            "specialist checks or explicit unverified blocks"
        ),
        "Objectives and production-like context",
        "Unmeasured items",
        "Commands and automated checks",
        (
            "Visual/interaction baseline, changed captures, reviewed differences, "
            "and persistent checks"
        ),
        "Cross-build decision",
        "Adversarial specificity closure and reviewer relationship",
        "Accountable-owner disposition, scope, ID, date, candidate/build, and evidence",
        "Cultural disposition and producer-independence result",
        "Remaining limitations, open high/medium findings, owners, and release blockers",
        "Reviewer conclusion",
    ),
    "claims": (
        "Claims still pending or prohibited",
        "Scenario values visibly labeled",
        "Categorical words reviewed (`all`, `every`, `always`, `never`, `best`, `only`)",
        "Public copy checked against this ledger",
        "Owner approval and date",
    ),
    "user-validation": (
        "Decision this study can change",
        "Audience and critical task",
        "Hypothesis and highest-risk unknown",
        "Prototype/build ID",
        "Environment and date",
        "Validation not performed and why",
        "Chosen method and why it can answer the riskiest unknown",
        "Method limits",
        "Production measurement integrity, when applicable",
        "Experiment or causal-claim specialist boundary and unverified items",
        "Audience or conditions not represented",
        "Accessibility or assistive technology not covered",
        "Sample-size and generalization limits",
        "Research, legal, privacy, or specialist follow-up",
        "Changes implemented",
        "Re-test result",
        "Post-launch learning owner, first review date, and evidence source",
        "Escalation, rollback, or further-research trigger",
        "Remaining risk",
        "Owner/research approval",
        "Retention/de-identification action completed",
        "Deletion verified by/date",
    ),
    "handoff": (
        "Product, release, and exact build identity",
        "Handoff owner and receiving owner",
        "Routes, flows, components, content, and environments in scope",
        "Explicitly excluded, provisional, or unverified scope",
        "Facts, content, policy, claims, and localization source",
        "Identity, design, component, behavior, and asset source",
        "Repository, release, deployment, and environment source",
        "Rights, provenance, privacy, generated-media, and cultural authority",
        "Mapping confidence, known drift, and reconciliation owner",
        "Selected reference mapping",
        "Protected recognition and comprehension decisions",
        "Unresolved source mappings that block future visible changes",
        "Decisions intentionally local and not to be generalized",
        "Proof-to-build deviations and owner dispositions",
        "Component, token, content, asset, and dependency lifecycle states",
        "Deprecated paths, migration plan, affected consumers, and deadline",
        "Compatibility, versioning, rollback, failure, and recovery contract",
        "Visual and interaction regression evidence and update trigger",
        "Content, asset, data, integration, access, and cultural-review owners",
        "Monitoring, support, privacy, retention, security, and incident path",
        "Performance, accessibility, browser, rights, and lower-impact review cadence",
        "Documentation location, update trigger, and expiry schedule",
        "Accepted baseline and candidate/build comparison",
        (
            "Functional, content, state, accessibility, performance, visual, "
            "cultural, and operational evidence actually completed"
        ),
        "Known defects, accepted risks, pending decisions, and accountable owners",
        "Staging, deployment, live, and post-launch verification status",
        "Remaining decision, owner, due date, and safe interim behavior",
        "Escalation, rollback, revision, or removal trigger",
        "Final receiving-owner acknowledgement and date",
    ),
}

# The current contract names only evidence anchors, never aesthetic recipes.
# Existing schema-2 records without the proportional marker continue through
# the legacy validator so already-complete evidence is not reinterpreted.
REQUIRED_RECORD_SECTIONS = {
    "exploration": {
        "Exploration intent",
        "Evidence and candidate reasoning",
        "Decision and limits",
    },
    "taste-calibration": {
        "Record lifecycle and evidence boundary",
        "Public encounter and project read",
        "Reference dossier",
        "Direction proof",
        "First-impression and surface-fidelity response",
        "Disposition",
    },
    "reference-dossier": {
        "Research frame",
        "Strong references",
        "Negative counterexamples",
        "Selected synthesis",
        "Component sources",
    },
    "direction": {
        "Identity and intent",
        "Truth and provenance",
        "Responsive, accessible, and functional behavior",
        "Owner and release state",
    },
    "direction-proof": {
        "Proof identity and intent",
        "Truth and provenance",
        "Responsive, accessible, and functional behavior",
        "Rendered proof",
        "Owner and release state",
    },
    "visual-review": {
        "Rendered review",
        "Findings",
        "Owner and release state",
    },
    "claims": {"Claims", "Closure"},
    "user-validation": {
        "Study",
        "Findings and decisions",
        "Limits",
        "Completion",
    },
    "handoff": {
        "Identity and scope",
        "Sources of truth and authority",
        "Verification",
        "Open decisions",
    },
}
STANDARD_VISUAL_REVIEW_SECTIONS = {
    "Review scope and capture rationale",
    "First-impression and surface-fidelity review",
    "Artifact credibility and cumulative-pattern review",
    "Preship and specificity closure",
}
QUICK_VISUAL_REVIEW_SECTIONS = {
    "Mechanical repair invariance",
}
REVIEW_SCOPE_CAPTURE_HEADERS = (
    "Route/state or reviewed body",
    "Material review risk or not-applicable reason",
    "Wide capture ID",
    "Narrow capture ID",
    "Disposition",
)
SURFACE_FIDELITY_HEADERS = (
    "Review focus",
    "Applicability or disposition",
    "Rendered PNG path and SHA-256",
    "Observation or limitation",
)
PRESHIP_SPECIFICITY_HEADERS = (
    "Closure",
    "Applicability or disposition",
    "Rendered PNG path and SHA-256",
    "Result or limitation",
)
REFERENCE_LED_DIRECTION_CLOSURE_HEADERS = (
    "Review focus",
    "Applicability or disposition",
    "Rendered PNG path and SHA-256",
    "Reference synthesis, counterevidence, and rendered result",
)
ARTIFACT_CREDIBILITY_LABELS = (
    "Artifact-only reviewer relationship and prior exposure",
    "Credible public-surface result",
    "Dominant recurring device or relationship cluster",
    "Cumulative intensity and ordinary-work result",
    "Business/category completeness result",
    "Media credibility and synthetic-pattern result",
    "Portfolio/process-language result",
    "Cross-project visual-grammar result or no-comparator limitation",
    "Container/backplate result",
    "Link/button/underline affordance result",
    "Artifact credibility disposition",
)
REVIEW_CLOSURE_DISPOSITIONS = {
    "applicable",
    "not-applicable",
    "blocked",
}
REFERENCE_SOURCED_DIRECTION_SECTIONS = {
    "Reference-sourced organizing logic",
    "Observable consequential design decisions",
    "Material, media, and public-copy boundary",
}
PREBUILD_SUBSTANTIVE_RECORDS = (
    "exploration",
    "taste-calibration",
    "reference-dossier",
    "direction",
    "direction-proof",
    "claims",
)
REQUIRED_RECORD_LABELS = {
    "exploration": (),
    "taste-calibration": (),
    "reference-dossier": (),
    "direction": (),
    "direction-proof": (
        "Reviewer relationship",
        "Current decision",
    ),
    "visual-review": (
        "Build or artifact ID",
        "Final implementation reviewed",
        "Reviewer relationship",
        "Reviewer conclusion",
        "Release blockers",
    ),
    "claims": (
        "Claims still pending or prohibited",
        "Owner approval and date",
    ),
    "user-validation": (
        "Decision this study can change",
        "Owner/research approval",
        "Remaining risk",
    ),
    "handoff": (
        "Product, release, and exact build identity",
        "Handoff owner and receiving owner",
        "Known defects, accepted risks, pending decisions, and accountable owners",
        "Final receiving-owner acknowledgement and date",
    ),
}
CAPABILITY_REQUIRED_SECTIONS = {
    "enterprise-candidate": {
        "visual-review": {"Enterprise Candidate closure (when selected)"},
    },
    "public-copy-integrity": {
        "visual-review": {
            "Public copy integrity closure (required for public candidates)"
        },
    },
    "numeric-rhetoric-integrity": {
        "visual-review": {
            "Numeric rhetoric integrity closure (required for public candidates)"
        },
    },
    "reference-led-direction": {
        "direction": {
            "Reference-led direction (required for public candidates)"
        },
        "visual-review": {
            "Reference-led direction closure (required for public candidates)"
        },
    },
    "connected-public-experience": {
        "direction": {"Connected public experience (when selected)"},
        "visual-review": {
            "Connected public experience closure (when selected)"
        },
    },
    "range-study": {
        "direction": {"Range-study contract"},
        "visual-review": {"Range-study review"},
    },
    "batch-study": {
        "direction": {"Batch Study protocol"},
        "visual-review": {"Batch Study review"},
    },
    "cultural-context": {
        "direction": {"Cultural context and authority"},
        "visual-review": {"Cultural review"},
    },
    "high-risk": {
        "direction": {"Risk and specialist authority"},
        "visual-review": {"Risk closure"},
    },
    "asset-led": {
        "direction": {"Asset provenance plan"},
        "visual-review": {"Asset review"},
    },
}
CAPABILITY_REQUIRED_RECORDS = {
    "enterprise-candidate": {"direction", "route-manifest", "visual-review"},
    "numeric-rhetoric-integrity": {"direction", "visual-review"},
    "public-copy-integrity": {"direction", "visual-review"},
    "reference-led-direction": {
        "direction", "reference-dossier", "route-manifest", "visual-review"
    },
    "connected-public-experience": {"connected-public-experience"},
    "project-contrast": {"project-contrast"},
    "direction-challenge": {"direction-challenge"},
    "range-study": {"route-family"},
    "batch-study": {"batch-range"},
    "cultural-context": {"direction", "visual-review"},
    "high-risk": {"direction", "visual-review", "claims", "user-validation"},
    "asset-led": {"assets"},
}

PROFILE_REQUIRED_LABELS: dict[str, dict[str, tuple[str, ...]]] = {}
LEGACY_RECORD_FILES = ("state.yml", "continuity-note.yml", "ledger-entry.yml")
MIGRATION_REPORT = "migration-report.json"
CLASSIFICATIONS = {"internal", "public", "confidential", "restricted-research"}
USER_VALIDATION_FRONTMATTER_FIELDS = {
    "research_data_owner",
    "collection_basis",
    "access_scope",
    "storage_location",
    "retention_rule",
    "deletion_owner",
    "deletion_status",
}
USER_VALIDATION_DELETION_STATUSES = {
    "pending",
    "scheduled",
    "completed",
    "de-identified",
    "not-applicable",
}
STATE_PRIVACY_IGNORE_LINES = (
    "# Design DNA privacy safeguards",
    "/user-validation.md",
    "/evidence/research/",
    "/*.[Rr][Ee][Ss][Tt][Rr][Ii][Cc][Tt][Ee][Dd].*",
)
BACKUP_PRIVACY_IGNORE_BLOCK = (
    "# BEGIN DESIGN DNA RECOVERY PRIVACY GUARD\n"
    "*\n"
    "!.gitignore\n"
    "# END DESIGN DNA RECOVERY PRIVACY GUARD\n"
)


class StateError(RuntimeError):
    """A stable, structured runtime failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        path: Path | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.details = details or {}


def error_record(error: StateError) -> dict[str, object]:
    result: dict[str, object] = {"code": error.code, "message": str(error)}
    if error.path is not None:
        result["path"] = str(error.path)
    if error.details:
        result["details"] = error.details
    return result


def emit_error(error: StateError) -> NoReturn:
    payload = {"ok": False, "error": error_record(error)}
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(2)


def lock_timeout_seconds() -> float:
    raw = os.environ.get(
        "DESIGN_DNA_LOCK_TIMEOUT_SECONDS",
        str(DEFAULT_LOCK_TIMEOUT_SECONDS),
    )
    try:
        value = float(raw)
    except ValueError as exc:
        raise StateError(
            "invalid-lock-timeout",
            "DESIGN_DNA_LOCK_TIMEOUT_SECONDS must be numeric.",
        ) from exc
    if not 0.05 <= value <= MAX_LOCK_TIMEOUT_SECONDS:
        raise StateError(
            "invalid-lock-timeout",
            (
                "DESIGN_DNA_LOCK_TIMEOUT_SECONDS must be between 0.05 and "
                f"{MAX_LOCK_TIMEOUT_SECONDS:g} seconds."
            ),
        )
    return value


def secure_open_lock(path: Path) -> object:
    """Open one ordinary peer lock file without following a redirected path."""

    flags = os.O_RDWR
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    created = False
    try:
        descriptor = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
    except FileExistsError:
        if is_reparse(path):
            raise StateError(
                "reparse-point-refused",
                "The project-state lock must not be a link or reparse point.",
                path=path,
            )
        try:
            info = path.lstat()
        except OSError as exc:
            raise StateError(
                "project-lock-inspection-failed",
                str(exc),
                path=path,
            ) from exc
        if not stat.S_ISREG(info.st_mode):
            raise StateError(
                "invalid-project-lock",
                "The project-state lock path must be an ordinary file.",
                path=path,
            )
        try:
            descriptor = os.open(
                path,
                flags | getattr(os, "O_NOFOLLOW", 0),
            )
        except OSError as exc:
            raise StateError(
                "project-lock-open-failed",
                str(exc),
                path=path,
            ) from exc
    except OSError as exc:
        raise StateError(
            "project-lock-open-failed",
            str(exc),
            path=path,
        ) from exc

    try:
        opened = os.fstat(descriptor)
        observed = path.lstat()
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != observed.st_dev
            or opened.st_ino != observed.st_ino
            or is_reparse(path)
        ):
            raise StateError(
                "project-lock-race-refused",
                "The project-state lock changed while it was being opened.",
                path=path,
            )
        if created or opened.st_size == 0:
            os.lseek(descriptor, 0, os.SEEK_SET)
            os.write(descriptor, b"\0")
            os.fsync(descriptor)
        return os.fdopen(descriptor, "r+b", buffering=0)
    except Exception:
        os.close(descriptor)
        raise


def try_platform_lock(stream: object) -> bool:
    descriptor = stream.fileno()
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            return True
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                return False
            raise
    import fcntl

    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


def release_platform_lock(stream: object) -> None:
    descriptor = stream.fileno()
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(descriptor, fcntl.LOCK_UN)


class ProjectMutationLock:
    """Bounded cross-process lock with persistent owner-token evidence."""

    def __init__(
        self,
        project: Path,
        operation: str,
        *,
        timeout: float | None = None,
    ) -> None:
        self.project = lexical_absolute(project)
        self.path = self.project / LOCK_FILE_NAME
        self.operation = operation
        self.timeout = lock_timeout_seconds() if timeout is None else timeout
        self.owner_token = secrets.token_hex(24)
        self.stream: object | None = None
        self.record: dict[str, object] | None = None
        self.stale_predecessor: dict[str, object] | None = None

    def _read_record(self) -> dict[str, object] | None:
        if self.stream is None:
            raise StateError(
                "project-lock-not-held",
                "The project-state lock is not open.",
                path=self.path,
            )
        self.stream.seek(1)
        raw = self.stream.read(LOCK_RECORD_LIMIT + 1)
        if len(raw) > LOCK_RECORD_LIMIT:
            raise StateError(
                "invalid-project-lock",
                "The project-state lock record exceeds its bounded size.",
                path=self.path,
            )
        if not raw:
            return None
        try:
            text = raw.decode("utf-8")
            payload = strict_json(text, path=self.path)
        except (UnicodeError, StateError) as exc:
            raise StateError(
                "invalid-project-lock",
                "The unlocked project-state lock contains invalid metadata.",
                path=self.path,
                details={"cause": str(exc)},
            ) from exc
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != 1
            or payload.get("record_type") != "design-dna-project-state-lock"
            or payload.get("status") not in {"active", "released"}
            or not isinstance(payload.get("owner_token"), str)
        ):
            raise StateError(
                "invalid-project-lock",
                "The unlocked project-state lock has an unsupported contract.",
                path=self.path,
            )
        return payload

    def _write_record(self, payload: dict[str, object]) -> None:
        if self.stream is None:
            raise StateError(
                "project-lock-not-held",
                "The project-state lock is not open.",
                path=self.path,
            )
        encoded = (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        if len(encoded) > LOCK_RECORD_LIMIT:
            raise StateError(
                "project-lock-record-too-large",
                "The project-state lock record exceeds its bounded size.",
                path=self.path,
            )
        try:
            self.stream.seek(1)
            self.stream.write(encoded)
            self.stream.truncate(1 + len(encoded))
            self.stream.flush()
            os.fsync(self.stream.fileno())
        except OSError as exc:
            raise StateError(
                "project-lock-write-failed",
                str(exc),
                path=self.path,
            ) from exc

    def acquire(self) -> "ProjectMutationLock":
        assert_contained(self.path, self.project)
        assert_no_reparse_ancestors(self.path, stop=self.project)
        self.stream = secure_open_lock(self.path)
        deadline = time.monotonic() + self.timeout
        try:
            while True:
                try:
                    if try_platform_lock(self.stream):
                        break
                except OSError as exc:
                    raise StateError(
                        "project-lock-acquire-failed",
                        str(exc),
                        path=self.path,
                    ) from exc
                if time.monotonic() >= deadline:
                    raise StateError(
                        "project-state-locked",
                        "Another process owns the project-state mutation lock.",
                        path=self.path,
                        details={"waited_seconds": self.timeout},
                    )
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

            predecessor = self._read_record()
            if predecessor and predecessor.get("status") == "active":
                predecessor_bytes = json.dumps(
                    predecessor,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                self.stale_predecessor = {
                    "owner_token": predecessor.get("owner_token"),
                    "pid": predecessor.get("pid"),
                    "operation": predecessor.get("operation"),
                    "acquired_at": predecessor.get("acquired_at"),
                    "record_sha256": hashlib.sha256(
                        predecessor_bytes
                    ).hexdigest(),
                }
            self.record = {
                "schema_version": 1,
                "record_type": "design-dna-project-state-lock",
                "status": "active",
                "owner_token": self.owner_token,
                "pid": os.getpid(),
                "operation": self.operation,
                "acquired_at": datetime.now(timezone.utc).isoformat(),
                "released_at": None,
                "stale_predecessor": self.stale_predecessor,
            }
            self._write_record(self.record)
            self.assert_owned()
            return self
        except Exception:
            if self.stream is not None:
                try:
                    release_platform_lock(self.stream)
                except OSError:
                    pass
                self.stream.close()
                self.stream = None
            raise

    def assert_owned(self) -> None:
        payload = self._read_record()
        if (
            payload is None
            or payload.get("status") != "active"
            or payload.get("owner_token") != self.owner_token
        ):
            raise StateError(
                "project-lock-ownership-lost",
                "The mutation lock owner token changed during the operation.",
                path=self.path,
            )

    def recovery_actions(self) -> list[dict[str, str]]:
        if self.stale_predecessor is None:
            return []
        return [
            {
                "action": "stale-lock-recovered",
                "path": str(self.path),
                "reason": (
                    "The operating-system lock was free, so stale owner "
                    "metadata was preserved in the new owner record."
                ),
            }
        ]

    def release(self) -> StateError | None:
        if self.stream is None:
            return None
        failure: StateError | None = None
        try:
            self.assert_owned()
            if self.record is None:
                raise StateError(
                    "project-lock-record-missing",
                    "The active project-state lock has no owner record.",
                    path=self.path,
                )
            released = dict(self.record)
            released["status"] = "released"
            released["released_at"] = datetime.now(timezone.utc).isoformat()
            self._write_record(released)
        except Exception as exc:
            failure = as_state_error(
                exc,
                code="project-lock-release-failed",
                path=self.path,
            )
        finally:
            try:
                release_platform_lock(self.stream)
            except OSError as exc:
                if failure is None:
                    failure = StateError(
                        "project-lock-release-failed",
                        str(exc),
                        path=self.path,
                    )
            self.stream.close()
            self.stream = None
        return failure

    def __enter__(self) -> "ProjectMutationLock":
        return self.acquire()

    def __exit__(self, exc_type, exc, traceback) -> bool:
        failure = self.release()
        if failure is not None and exc is None:
            raise failure
        return False


def entry_exists(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise StateError("path-inspection-failed", str(exc), path=path) from exc


def is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise StateError("path-inspection-failed", str(exc), path=path) from exc
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    if not attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        return False
    tag = getattr(info, "st_reparse_tag", 0)
    if tag:
        return bool(tag & 0x20000000) or tag in {0xA0000003, 0xA000000C}
    return True


def lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def assert_no_reparse_ancestors(path: Path, *, stop: Path | None = None) -> None:
    """Reject any existing path entry from path through stop, without following it."""
    candidate = lexical_absolute(path)
    stop = lexical_absolute(stop) if stop else None
    while True:
        if entry_exists(candidate) and is_reparse(candidate):
            raise StateError(
                "reparse-point-refused",
                "Symlinks, junctions, and reparse points are not accepted in a state path.",
                path=candidate,
            )
        if stop is not None and candidate == stop:
            return
        if candidate.parent == candidate:
            return
        candidate = candidate.parent


def assert_safe_tree(root: Path) -> None:
    """Inspect a tree without recursing through link-like entries."""
    if not entry_exists(root):
        return
    if is_reparse(root):
        raise StateError("reparse-point-refused", "Unsafe state directory.", path=root)
    def fail_walk(error: OSError) -> None:
        error_path = Path(error.filename) if error.filename else root
        if isinstance(error, PermissionError) or error.errno in {
            errno.EACCES,
            errno.EPERM,
        }:
            raise access_denied_state_error(error, error_path) from error
        raise StateError(
            "tree-enumeration-failed",
            str(error),
            path=error_path,
        ) from error

    for current, directories, files in os.walk(
        root,
        topdown=True,
        followlinks=False,
        onerror=fail_walk,
    ):
        current_path = Path(current)
        for name in list(directories) + files:
            child = current_path / name
            if is_reparse(child):
                raise StateError(
                    "reparse-point-refused",
                    "State contains a symlink, junction, or reparse point.",
                    path=child,
                )


def file_sha256(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                digest.update(chunk)
    except OSError as exc:
        raise StateError(
            "state-identity-read-failed",
            str(exc),
            path=path,
        ) from exc
    return size, digest.hexdigest()


def verify_png_artifact(path: Path) -> tuple[int, int]:
    """Decode a bounded PNG with the standard library and return dimensions."""

    try:
        size = path.stat().st_size
        if size < 45 or size > 128 * 1024 * 1024:
            raise StateError(
                "render-evidence-image-invalid",
                "Rendered PNG must be from 45 bytes through 128 MiB.",
                path=path,
            )
        data = path.read_bytes()
    except OSError as exc:
        raise StateError(
            "render-evidence-image-invalid",
            str(exc),
            path=path,
        ) from exc
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise StateError(
            "render-evidence-image-invalid",
            "Rendered evidence is not a PNG.",
            path=path,
        )

    offset = 8
    width = height = bit_depth = color_type = interlace = None
    compressed = bytearray()
    seen_ihdr = seen_idat = seen_iend = seen_plte = False
    idat_ended = False
    while offset < len(data):
        if offset + 12 > len(data):
            raise StateError(
                "render-evidence-image-invalid",
                "PNG chunk header is truncated.",
                path=path,
            )
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            raise StateError(
                "render-evidence-image-invalid",
                "PNG chunk data is truncated.",
                path=path,
            )
        chunk_data = data[offset + 8:offset + 8 + length]
        recorded_crc = struct.unpack(
            ">I", data[offset + 8 + length:chunk_end]
        )[0]
        actual_crc = binascii.crc32(chunk_type)
        actual_crc = binascii.crc32(chunk_data, actual_crc) & 0xFFFFFFFF
        if actual_crc != recorded_crc:
            raise StateError(
                "render-evidence-image-invalid",
                "PNG chunk checksum is invalid.",
                path=path,
            )

        if chunk_type == b"IHDR":
            if seen_ihdr or offset != 8 or length != 13:
                raise StateError(
                    "render-evidence-image-invalid",
                    "PNG must begin with exactly one valid IHDR chunk.",
                    path=path,
                )
            (
                width,
                height,
                bit_depth,
                color_type,
                compression,
                filtering,
                interlace,
            ) = struct.unpack(">IIBBBBB", chunk_data)
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
                raise StateError(
                    "render-evidence-image-invalid",
                    "PNG header, dimensions, or color format is unsupported.",
                    path=path,
                )
            seen_ihdr = True
        elif chunk_type == b"PLTE":
            if not seen_ihdr or seen_idat or not 1 <= length <= 768 or length % 3:
                raise StateError(
                    "render-evidence-image-invalid",
                    "PNG palette placement or length is invalid.",
                    path=path,
                )
            seen_plte = True
        elif chunk_type == b"IDAT":
            if not seen_ihdr or seen_iend or idat_ended:
                raise StateError(
                    "render-evidence-image-invalid",
                    "PNG IDAT chunks are out of order.",
                    path=path,
                )
            seen_idat = True
            compressed.extend(chunk_data)
            if len(compressed) > 128 * 1024 * 1024:
                raise StateError(
                    "render-evidence-image-invalid",
                    "PNG compressed payload exceeds the audit limit.",
                    path=path,
                )
        elif chunk_type == b"IEND":
            if not seen_idat or seen_iend or length:
                raise StateError(
                    "render-evidence-image-invalid",
                    "PNG IEND is missing, duplicated, or malformed.",
                    path=path,
                )
            seen_iend = True
            offset = chunk_end
            break
        else:
            if seen_idat:
                idat_ended = True
            if chunk_type[:1].isupper():
                raise StateError(
                    "render-evidence-image-invalid",
                    "PNG contains an unsupported critical chunk.",
                    path=path,
                )
        offset = chunk_end

    if (
        not seen_ihdr
        or not seen_idat
        or not seen_iend
        or offset != len(data)
        or (color_type == 3 and not seen_plte)
    ):
        raise StateError(
            "render-evidence-image-invalid",
            "PNG is incomplete or has trailing data.",
            path=path,
        )
    assert (
        isinstance(width, int)
        and isinstance(height, int)
        and isinstance(bit_depth, int)
        and isinstance(color_type, int)
        and interlace == 0
    )
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    row_bytes = math.ceil(width * channels * bit_depth / 8)
    expected_bytes = height * (row_bytes + 1)
    if expected_bytes > 128 * 1024 * 1024:
        raise StateError(
            "render-evidence-image-invalid",
            "PNG decoded payload exceeds the audit limit.",
            path=path,
        )
    try:
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(bytes(compressed), expected_bytes + 1)
        decoded += decoder.flush(max(1, expected_bytes + 1 - len(decoded)))
    except zlib.error as exc:
        raise StateError(
            "render-evidence-image-invalid",
            f"PNG pixel stream cannot be decoded: {exc}",
            path=path,
        ) from exc
    if (
        len(decoded) != expected_bytes
        or not decoder.eof
        or decoder.unused_data
        or decoder.unconsumed_tail
    ):
        raise StateError(
            "render-evidence-image-invalid",
            "PNG pixel stream does not match its declared dimensions.",
            path=path,
        )
    for row in range(height):
        if decoded[row * (row_bytes + 1)] > 4:
            raise StateError(
                "render-evidence-image-invalid",
                f"PNG row {row} has an invalid filter.",
                path=path,
            )
    return width, height


def decoded_png_rgba(path: Path) -> tuple[int, int, bytes]:
    """Decode ordinary non-interlaced 8-bit PNG pixels for exact comparison."""

    width, height = verify_png_artifact(path)
    data = path.read_bytes()
    offset = 8
    bit_depth = color_type = None
    compressed = bytearray()
    palette = b""
    transparency = b""
    while offset < len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        chunk = data[offset + 8:offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            _w, _h, bit_depth, color_type, _compression, _filtering, _interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
        elif chunk_type == b"PLTE":
            palette = chunk
        elif chunk_type == b"tRNS":
            transparency = chunk
        elif chunk_type == b"IDAT":
            compressed.extend(chunk)
        elif chunk_type == b"IEND":
            break
    if bit_depth != 8 or color_type not in {0, 2, 3, 4, 6}:
        raise StateError(
            "render-comparison-png-unsupported",
            "Quick exact invariance requires non-interlaced 8-bit gray, RGB, indexed, gray-alpha, or RGBA PNGs.",
            path=path,
        )
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    row_bytes = width * channels
    raw = zlib.decompress(bytes(compressed))
    if len(raw) != height * (row_bytes + 1):
        raise StateError(
            "render-comparison-png-invalid",
            "PNG decoded bytes do not match dimensions.",
            path=path,
        )

    def paeth(a: int, b: int, c: int) -> int:
        estimate = a + b - c
        da, db, dc = abs(estimate - a), abs(estimate - b), abs(estimate - c)
        return a if da <= db and da <= dc else b if db <= dc else c

    rows: list[bytes] = []
    previous = bytearray(row_bytes)
    stride = row_bytes + 1
    for row_index in range(height):
        start = row_index * stride
        filter_type = raw[start]
        filtered = raw[start + 1:start + stride]
        current = bytearray(row_bytes)
        for index, byte in enumerate(filtered):
            left = current[index - channels] if index >= channels else 0
            up = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 0:
                value = byte
            elif filter_type == 1:
                value = byte + left
            elif filter_type == 2:
                value = byte + up
            elif filter_type == 3:
                value = byte + ((left + up) // 2)
            elif filter_type == 4:
                value = byte + paeth(left, up, upper_left)
            else:
                raise StateError(
                    "render-comparison-png-invalid",
                    f"PNG row {row_index} has an invalid filter.",
                    path=path,
                )
            current[index] = value & 0xFF
        rows.append(bytes(current))
        previous = current
    rgba = bytearray(width * height * 4)
    output = 0
    for row in rows:
        for index in range(0, len(row), channels):
            if color_type == 6:
                red, green, blue, alpha = row[index:index + 4]
            elif color_type == 2:
                red, green, blue = row[index:index + 3]
                alpha = 255
            elif color_type == 4:
                red = green = blue = row[index]
                alpha = row[index + 1]
            elif color_type == 0:
                red = green = blue = row[index]
                alpha = 255
            else:
                palette_index = row[index]
                palette_offset = palette_index * 3
                if palette_offset + 3 > len(palette):
                    raise StateError(
                        "render-comparison-png-invalid",
                        "PNG palette index is out of range.",
                        path=path,
                    )
                red, green, blue = palette[palette_offset:palette_offset + 3]
                alpha = transparency[palette_index] if palette_index < len(transparency) else 255
            rgba[output:output + 4] = bytes((red, green, blue, alpha))
            output += 4
    return width, height, bytes(rgba)


def state_tree_records(root: Path) -> tuple[tuple[str, str, int, str], ...]:
    if not root.is_dir():
        raise StateError(
            "state-identity-root-missing",
            "State identity requires an ordinary directory.",
            path=root,
        )
    assert_safe_tree(root)
    records: list[tuple[str, str, int, str]] = []
    count = 0

    def fail_walk(error: OSError) -> None:
        raise StateError(
            "state-identity-enumeration-failed",
            str(error),
            path=Path(error.filename) if error.filename else root,
        ) from error

    for current, directories, files in os.walk(
        root,
        topdown=True,
        followlinks=False,
        onerror=fail_walk,
    ):
        current_path = Path(current)
        directories.sort(key=str.casefold)
        files.sort(key=str.casefold)
        for name in directories:
            child = current_path / name
            count += 1
            if count > MAX_STATE_IDENTITY_ENTRIES:
                raise StateError(
                    "state-identity-limit-exceeded",
                    "State tree exceeds the bounded identity entry limit.",
                    path=root,
                )
            if is_reparse(child):
                raise StateError(
                    "reparse-point-refused",
                    "State identity refuses redirected directories.",
                    path=child,
                )
            records.append(
                (child.relative_to(root).as_posix(), "directory", 0, "")
            )
        for name in files:
            child = current_path / name
            count += 1
            if count > MAX_STATE_IDENTITY_ENTRIES:
                raise StateError(
                    "state-identity-limit-exceeded",
                    "State tree exceeds the bounded identity entry limit.",
                    path=root,
                )
            if is_reparse(child):
                raise StateError(
                    "reparse-point-refused",
                    "State identity refuses redirected files.",
                    path=child,
                )
            try:
                mode = child.stat().st_mode
            except OSError as exc:
                raise StateError(
                    "state-identity-inspection-failed",
                    str(exc),
                    path=child,
                ) from exc
            if not stat.S_ISREG(mode):
                raise StateError(
                    "unsupported-state-entry",
                    "State trees may contain only directories and regular files.",
                    path=child,
                )
            size, digest = file_sha256(child)
            records.append(
                (child.relative_to(root).as_posix(), "file", size, digest)
            )
    records.sort(key=lambda item: item[0])
    return tuple(records)


def state_tree_identity(root: Path) -> str:
    first = state_tree_records(root)
    second = state_tree_records(root)
    if first != second:
        raise StateError(
            "unstable-state-tree",
            "State content changed while its exact identity was calculated.",
            path=root,
        )
    digest = hashlib.sha256()
    for relative, kind, size, content_hash in first:
        for value in (relative, kind, str(size), content_hash):
            digest.update(value.encode("utf-8"))
            digest.update(b"\0")
    return digest.hexdigest()


def captured_state_identity(path: Path) -> str | None:
    if not entry_exists(path):
        return None
    if not path.is_dir():
        raise StateError(
            "invalid-state-entry",
            ".design-dna exists but is not an ordinary directory.",
            path=path,
        )
    return state_tree_identity(path)


def require_state_identity(
    path: Path,
    expected: str | None,
    *,
    code: str,
    message: str,
) -> None:
    observed = captured_state_identity(path)
    if observed != expected:
        raise StateError(
            code,
            message,
            path=path,
            details={
                "expected_sha256": expected,
                "observed_sha256": observed,
            },
        )


def assert_contained(path: Path, root: Path) -> None:
    lexical_path = lexical_absolute(path)
    lexical_root = lexical_absolute(root)
    if not is_within(lexical_path, lexical_root):
        raise StateError("path-escape", "Path escapes the selected project.", path=lexical_path)
    resolved_root = lexical_root.resolve(strict=True)
    resolved_parent = lexical_path.parent.resolve(strict=True)
    if not is_within(resolved_parent, resolved_root):
        raise StateError(
            "resolved-path-escape",
            "Resolved destination parent escapes the selected project.",
            path=lexical_path,
        )


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def unique_peer(path: Path, label: str) -> Path:
    for number in range(1, 10_000):
        suffix = "" if number == 1 else f"-{number}"
        candidate = path.with_name(f"{path.name}.{label}-{utc_stamp()}{suffix}")
        if not entry_exists(candidate):
            return candidate
    raise StateError("name-exhausted", "Unable to reserve a unique peer path.", path=path.parent)


def create_transaction_stage_parent(
    project: Path,
    prefix: str,
    *,
    platform_name: str | None = None,
) -> Path:
    """Create a private stage without promoting a foreign Windows-only ACL."""

    platform_name = os.name if platform_name is None else platform_name
    if platform_name != "nt":
        return Path(tempfile.mkdtemp(prefix=prefix, dir=project))
    # Python's Windows 0o700 handling can grant access only to the process
    # identity. A renamed stage keeps that DACL, which is unsafe when an agent
    # process and the interactive project owner use different SIDs. mkdir's
    # ordinary mode inherits the project directory's access rules instead.
    for _attempt in range(128):
        candidate = project / f"{prefix}{secrets.token_hex(12)}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
        except OSError as exc:
            raise StateError(
                "stage-create-failed",
                str(exc),
                path=candidate,
            ) from exc
    raise StateError(
        "name-exhausted",
        "Unable to reserve a unique transaction staging directory.",
        path=project,
    )


def access_denied_state_error(error: OSError, path: Path) -> StateError:
    return StateError(
        "state-access-denied",
        (
            "The Design DNA state is not readable by the current process. On "
            "Windows, a state promoted by an older private temporary-directory "
            "transaction may retain another process identity's ACL. Do not "
            "delete or overwrite it; have the project owner restore inherited "
            "permissions or recover the latest readable backup, then rerun the "
            "operation under the owner's Windows account."
        ),
        path=path,
        details={"cause": str(error)},
    )


def strict_json(text: str, *, path: Path) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise StateError(
                    "duplicate-json-key",
                    f"Duplicate JSON key {key!r}.",
                    path=path,
                )
            result[key] = value
        return result

    try:
        return json.loads(text, object_pairs_hook=reject_duplicates)
    except StateError:
        raise
    except json.JSONDecodeError as exc:
        raise StateError("invalid-json", str(exc), path=path) from exc


def read_json(path: Path) -> object:
    try:
        return strict_json(path.read_text(encoding="utf-8"), path=path)
    except StateError:
        raise
    except (OSError, UnicodeError) as exc:
        raise StateError("state-read-failed", str(exc), path=path) from exc


_MISSING_BUNDLED_MODULE = object()


def load_bundled_source_module(
    module_name: str,
    path: Path,
    *,
    retain: bool = False,
) -> object:
    """Execute one bundled Python source file without creating bytecode.

    The state initializer is also imported by hosts and tests that do not use
    Python's ``-B`` flag.  A normal file-loader import can therefore write an
    executable ``__pycache__`` into the installed runtime; the release
    preflight correctly refuses that residue.  Compile the already-selected
    sibling source bytes directly, while still providing ordinary module
    metadata and a temporary ``sys.modules`` entry for code that needs it.
    """

    source = path.read_bytes()
    specification = importlib.util.spec_from_loader(
        module_name,
        loader=None,
        origin=str(path),
    )
    if specification is None:
        raise ImportError(f"Could not create a module specification for {path}.")
    module = importlib.util.module_from_spec(specification)
    module.__file__ = str(path)
    previous = sys.modules.get(module_name, _MISSING_BUNDLED_MODULE)
    sys.modules[module_name] = module
    try:
        code = compile(source, str(path), "exec", dont_inherit=True)
        exec(code, module.__dict__)
    except BaseException:
        if previous is _MISSING_BUNDLED_MODULE:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
    if not retain:
        if previous is _MISSING_BUNDLED_MODULE:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
    return module


def validate_route_family_record(
    path: Path,
) -> tuple[object, list[dict[str, str]]]:
    """Use the bundled dependency-free validator for the optional JSON record."""

    payload = read_json(path)
    validator_path = Path(__file__).with_name("route_family_audit.py")
    if not validator_path.is_file() or is_reparse(validator_path):
        raise StateError(
            "route-family-validator-missing",
            "The bundled route-family validator is missing or redirected.",
            path=validator_path,
        )
    try:
        module = load_bundled_source_module(
            "_design_dna_route_family_audit",
            validator_path,
        )
        validator = getattr(module, "validate_contract_payload")
        errors, _routes = validator(payload)
    except (AttributeError, ImportError, OSError, TypeError, ValueError) as exc:
        raise StateError(
            "route-family-validator-failed",
            str(exc),
            path=validator_path,
        ) from exc
    if not isinstance(errors, list) or not all(
        isinstance(item, dict)
        and set(item) == {"path", "code", "message"}
        and all(isinstance(item[key], str) for key in item)
        for item in errors
    ):
        raise StateError(
            "route-family-validator-invalid-output",
            "The bundled route-family validator returned an unsupported result.",
            path=validator_path,
        )
    return payload, errors


def validate_batch_range_record(
    path: Path,
) -> tuple[object, list[dict[str, str]]]:
    """Validate the planning-safe shape of the optional batch record.

    The initialized template intentionally contains unresolved paths, hashes,
    and viewport dimensions. Exact evidence is therefore verified only by the
    readiness audit after the project replaces those placeholders.
    """

    payload = read_json(path)
    errors: list[dict[str, str]] = []

    def add(location: str, code: str, message: str) -> None:
        errors.append({"path": location, "code": code, "message": message})

    expected_root = {
        "schema_version",
        "classification",
        "study",
        "data_handling",
        "sites",
        "whole_system_review",
        "contextual_findings",
    }
    optional_root = {"human_contextual_disposition"}
    if not isinstance(payload, dict):
        add("$", "invalid-root", "The record must be a JSON object.")
        return payload, errors
    if (
        not expected_root.issubset(set(payload))
        or not set(payload).issubset(expected_root | optional_root)
    ):
        add("$", "invalid-properties", "The record has missing or unsupported root properties.")
    if payload.get("schema_version") != 1:
        add("$.schema_version", "unsupported-version", "schema_version must equal 1.")
    if payload.get("classification") not in {"internal", "confidential"}:
        add("$.classification", "invalid-classification", "Use internal or confidential.")

    study = payload.get("study")
    viewport_ids: set[str] = set()
    roles: list[str] = []
    if not isinstance(study, dict):
        add("$.study", "invalid-study", "study must be an object.")
    else:
        required_study = {
            "id", "title", "frozen_at", "viewport_classes", "review_protocol",
        }
        if set(study) != required_study:
            add("$.study", "invalid-properties", "study has missing or unsupported properties.")
        viewports = study.get("viewport_classes")
        if not isinstance(viewports, list) or len(viewports) < 2:
            add("$.study.viewport_classes", "invalid-viewports", "Declare at least wide and narrow classes.")
        else:
            for index, viewport in enumerate(viewports):
                location = f"$.study.viewport_classes[{index}]"
                if not isinstance(viewport, dict) or set(viewport) != {
                    "id", "role", "width", "height", "basis", "required",
                }:
                    add(location, "invalid-viewport", "Viewport class has an unsupported shape.")
                    continue
                identifier = viewport.get("id")
                role = viewport.get("role")
                if not isinstance(identifier, str) or not EVIDENCE_CAPABILITY_PATTERN.fullmatch(identifier):
                    add(f"{location}.id", "invalid-id", "Viewport ID must be a lowercase slug.")
                elif identifier in viewport_ids:
                    add(f"{location}.id", "duplicate-id", "Viewport IDs must be unique.")
                else:
                    viewport_ids.add(identifier)
                if role not in {"wide", "narrow", "additional"}:
                    add(f"{location}.role", "invalid-role", "Viewport role is unsupported.")
                else:
                    roles.append(role)
        if roles.count("wide") != 1 or roles.count("narrow") != 1:
            add("$.study.viewport_classes", "invalid-core-viewports", "Declare exactly one wide and one narrow role.")
        protocol = study.get("review_protocol")
        if not isinstance(protocol, dict) or protocol != {
            "site_observation": "unprimed-before-diagnostics",
            "whole_system_comparison": "masked",
            "automatic_aesthetic_pass": False,
        }:
            add("$.study.review_protocol", "invalid-review-protocol", "The unprimed, masked, no-auto-pass protocol is required.")

    data_handling = payload.get("data_handling")
    required_data_handling = {
        "status", "capture_authorization", "contact_sheet_authorization",
        "classification", "recipients", "access_scope", "retention",
        "transformations",
    }
    if (
        not isinstance(data_handling, dict)
        or set(data_handling) != required_data_handling
    ):
        add(
            "$.data_handling",
            "invalid-data-handling",
            "data_handling has missing or unsupported properties.",
        )
    else:
        if data_handling.get("status") not in {"pending", "resolved"}:
            add(
                "$.data_handling.status",
                "invalid-status",
                "Data handling must be pending or resolved.",
            )
        for name in ("capture_authorization", "contact_sheet_authorization"):
            authorization = data_handling.get(name)
            if (
                not isinstance(authorization, dict)
                or set(authorization) != {"status", "basis"}
                or authorization.get("status")
                not in {"pending", "authorized", "not-applicable"}
            ):
                add(
                    f"$.data_handling.{name}",
                    "invalid-authorization",
                    "Authorization must declare a supported status and basis.",
                )
        if not isinstance(data_handling.get("recipients"), list):
            add(
                "$.data_handling.recipients",
                "invalid-recipients",
                "Data recipients must be an array.",
            )
        if not isinstance(data_handling.get("transformations"), list):
            add(
                "$.data_handling.transformations",
                "invalid-transformations",
                "Data transformations must be an array.",
            )
        retention = data_handling.get("retention")
        if (
            not isinstance(retention, dict)
            or set(retention)
            != {"mode", "owner", "delete_or_review_on", "reason"}
            or retention.get("mode")
            not in {"pending", "dated", "public", "not-applicable"}
        ):
            add(
                "$.data_handling.retention",
                "invalid-retention",
                "Retention must declare a supported disposition and lifecycle fields.",
            )

    sites = payload.get("sites")
    site_ids: set[str] = set()
    if not isinstance(sites, list) or len(sites) < 3:
        add("$.sites", "too-few-sites", "A Batch Study record requires at least three sites.")
    else:
        required_site = {
            "id", "mask_label", "status", "independence_basis", "brief",
            "implementation_isolation", "build_root", "public_root",
            "render_report", "pages",
            "unprimed_review", "blocker",
        }
        for index, site in enumerate(sites):
            location = f"$.sites[{index}]"
            if not isinstance(site, dict) or set(site) != required_site:
                add(location, "invalid-site", "Site case has an unsupported shape.")
                continue
            site_id = site.get("id")
            if not isinstance(site_id, str) or not EVIDENCE_CAPABILITY_PATTERN.fullmatch(site_id):
                add(f"{location}.id", "invalid-id", "Site ID must be a lowercase slug.")
            elif site_id in site_ids:
                add(f"{location}.id", "duplicate-id", "Site IDs must be unique.")
            else:
                site_ids.add(site_id)
            status = site.get("status")
            if status not in {"planned", "built", "correctly_blocked"}:
                add(f"{location}.status", "invalid-status", "Site status is unsupported.")
            pages = site.get("pages")
            if not isinstance(pages, list) or not pages:
                add(f"{location}.pages", "invalid-pages", "Each site must declare at least one page.")
            isolation = site.get("implementation_isolation")
            required_isolation = {
                "status", "source_packet", "producer_context_id",
                "sibling_output_exposure", "allowed_shared_tooling",
                "shared_artifacts_or_exceptions", "attested_by", "attested_at",
            }
            if (
                not isinstance(isolation, dict)
                or set(isolation) != required_isolation
            ):
                add(
                    f"{location}.implementation_isolation",
                    "invalid-isolation-attestation",
                    "Implementation isolation has missing or unsupported properties.",
                )
            else:
                if isolation.get("status") not in {"pending", "attested"}:
                    add(
                        f"{location}.implementation_isolation.status",
                        "invalid-status",
                        "Implementation isolation must be pending or attested.",
                    )
                source_packet = isolation.get("source_packet")
                if (
                    not isinstance(source_packet, dict)
                    or set(source_packet) != {"path", "sha256"}
                ):
                    add(
                        f"{location}.implementation_isolation.source_packet",
                        "invalid-source-packet",
                        "The frozen source packet must be a path and SHA-256 reference.",
                    )
                if not isinstance(isolation.get("producer_context_id"), str):
                    add(
                        f"{location}.implementation_isolation.producer_context_id",
                        "invalid-producer-context",
                        "A producer/build context identifier is required.",
                    )
                if not isinstance(isolation.get("allowed_shared_tooling"), list):
                    add(
                        f"{location}.implementation_isolation.allowed_shared_tooling",
                        "invalid-shared-tooling",
                        "Allowed shared tooling must be an array.",
                    )
                if not isinstance(
                    isolation.get("shared_artifacts_or_exceptions"),
                    list,
                ):
                    add(
                        f"{location}.implementation_isolation.shared_artifacts_or_exceptions",
                        "invalid-shared-exceptions",
                        "Shared artifacts or exceptions must be an array.",
                    )
            if status == "planned":
                if (
                    not isinstance(site.get("build_root"), str)
                    or not site["build_root"].strip()
                ):
                    add(
                        f"{location}.build_root",
                        "planned-build-root-missing",
                        "A planned site must declare its isolated future build root.",
                    )
                if site.get("blocker") is not None:
                    add(
                        f"{location}.blocker",
                        "planned-blocker-forbidden",
                        "A planned site is not correctly blocked and must use a null blocker.",
                    )
                if site.get("public_root") is not None or site.get("render_report") is not None:
                    add(
                        location,
                        "planned-render-evidence-forbidden",
                        "A planned site must keep public_root and render_report null until a build has been captured.",
                    )
                if isinstance(pages, list):
                    for page_index, page in enumerate(pages):
                        captures = (
                            page.get("captures")
                            if isinstance(page, dict)
                            else None
                        )
                        if captures != []:
                            add(
                                f"{location}.pages[{page_index}].captures",
                                "planned-captures-forbidden",
                                "A planned page must keep captures empty until it is built.",
                            )
                review = site.get("unprimed_review")
                if (
                    not isinstance(review, dict)
                    or review.get("status") not in {"pending", "not-run"}
                    or review.get("reviewer_id") is not None
                    or review.get("sibling_output_seen_before_observation") is not None
                    or review.get("diagnostic_material_seen_before_observation") is not None
                    or review.get("observed_at") is not None
                    or review.get("frozen_at") is not None
                    or review.get("capture_set_sha256") is not None
                    or review.get("evidence") is not None
                ):
                    add(
                        f"{location}.unprimed_review",
                        "planned-review-invalid",
                        "A planned site's review must be pending or not-run with null reviewer, exposure, times, capture binding, and evidence.",
                    )
                if (
                    isinstance(isolation, dict)
                    and isolation.get("status") != "pending"
                ):
                    add(
                        f"{location}.implementation_isolation.status",
                        "planned-isolation-invalid",
                        "A planned site cannot claim a completed implementation attestation.",
                    )

    whole_review = payload.get("whole_system_review")
    required_whole_review = {
        "status", "masked", "reviewer_id",
        "site_identity_revealed_before_observation",
        "diagnostic_material_seen_before_observation", "observed_at", "frozen_at",
        "capture_set_sha256", "evidence",
    }
    if (
        not isinstance(whole_review, dict)
        or set(whole_review) != required_whole_review
    ):
        add(
            "$.whole_system_review",
            "invalid-review",
            "whole_system_review has missing or unsupported protocol fields.",
        )
    if not isinstance(payload.get("contextual_findings"), list):
        add("$.contextual_findings", "invalid-findings", "contextual_findings must be an array.")

    # Batch protocol coverage and a human contextual disposition deliberately
    # remain separate.  Older/planned records may omit the latter, but when it
    # is present it must have the bounded shape the exact-evidence auditor
    # understands.  The auditor owns byte, chronology, and finding-state
    # checks; this lightweight pass keeps an unsupported object from being
    # treated as a future-compatible readiness record.
    human_disposition = payload.get("human_contextual_disposition")
    if human_disposition is not None:
        required_disposition = {
            "status", "reviewer_id", "decided_at", "capture_set_sha256",
            "evidence", "rationale", "finding_ids",
        }
        if (
            not isinstance(human_disposition, dict)
            or set(human_disposition) != required_disposition
        ):
            add(
                "$.human_contextual_disposition",
                "invalid-human-contextual-disposition",
                "The human contextual disposition has missing or unsupported fields.",
            )
        else:
            status = human_disposition.get("status")
            supported_statuses = {
                "pending", "no-material-cluster-observed", "revisions-required",
                "accepted-contextual-risk", "blocked",
            }
            if status not in supported_statuses:
                add(
                    "$.human_contextual_disposition.status",
                    "invalid-human-contextual-status",
                    "Use pending, no-material-cluster-observed, revisions-required, accepted-contextual-risk, or blocked.",
                )
            finding_ids = human_disposition.get("finding_ids")
            if (
                not isinstance(finding_ids, list)
                or any(
                    not isinstance(value, str) or not value.strip()
                    for value in finding_ids
                )
            ):
                add(
                    "$.human_contextual_disposition.finding_ids",
                    "invalid-human-contextual-finding-ids",
                    "finding_ids must be an array of non-empty finding identifiers.",
                )
            if status == "pending" and (
                human_disposition.get("reviewer_id") is not None
                or human_disposition.get("decided_at") is not None
                or human_disposition.get("capture_set_sha256") is not None
                or human_disposition.get("evidence") is not None
                or human_disposition.get("rationale") is not None
                or finding_ids != []
            ):
                add(
                    "$.human_contextual_disposition",
                    "pending-human-contextual-disposition-invalid",
                    "A pending human contextual disposition must keep reviewer, decision, capture, evidence, rationale null and finding_ids empty.",
                )
    return payload, errors


def run_batch_range_readiness_audit(path: Path, project: Path) -> dict[str, object]:
    """Run the bundled exact-evidence audit without creating an atlas/report."""

    payload, structural_errors = validate_batch_range_record(path)
    if structural_errors:
        raise StateError(
            "batch-range-validator-failed",
            structural_errors[0]["message"],
            path=path,
        )
    validator_path = Path(__file__).with_name("batch_range_audit.py")
    if not validator_path.is_file() or is_reparse(validator_path):
        raise StateError(
            "batch-range-validator-missing",
            "The bundled batch-range auditor is missing or redirected.",
            path=validator_path,
        )
    try:
        module = load_bundled_source_module(
            "_design_dna_batch_range_audit",
            validator_path,
        )
    except (AttributeError, ImportError, OSError, TypeError, ValueError) as exc:
        raise StateError(
            "batch-range-validator-load-failed",
            str(exc),
            path=validator_path,
        ) from exc
    audit_error = getattr(module, "AuditError", None)
    evidence_budget = getattr(module, "EvidenceBudget", None)
    validate_contract = getattr(module, "validate_contract", None)
    if (
        not isinstance(audit_error, type)
        or not issubclass(audit_error, Exception)
        or not callable(evidence_budget)
        or not callable(validate_contract)
    ):
        raise StateError(
            "batch-range-validator-invalid-interface",
            "The bundled batch-range auditor has an unsupported interface.",
            path=validator_path,
        )
    try:
        report, _atlas_inputs = validate_contract(
            payload,
            project,
            evidence_budget(),
            atlas_requested=False,
        )
    except audit_error as exc:
        raise StateError(
            "batch-range-validator-failed",
            f"{exc.code}: {exc.message}",
            path=validator_path,
        ) from exc
    except (AttributeError, OSError, TypeError, UnicodeError, ValueError) as exc:
        raise StateError(
            "batch-range-validator-failed",
            str(exc),
            path=validator_path,
        ) from exc
    if not isinstance(report, dict):
        raise StateError(
            "batch-range-validator-invalid-output",
            "The bundled batch-range auditor returned an unsupported result.",
            path=validator_path,
        )
    return report


def validate_project_contrast_record(
    path: Path,
) -> tuple[object, list[dict[str, str]]]:
    """Validate the planning-safe Project Contrast JSON record.

    Exact capture and review bytes remain an audit/readiness concern so a
    freshly initialized record can truthfully remain planned.
    """

    payload = read_json(path)
    validator_path = Path(__file__).with_name("project_contrast_audit.py")
    if not validator_path.is_file() or is_reparse(validator_path):
        raise StateError(
            "project-contrast-validator-missing",
            "The bundled Project Contrast validator is missing or redirected.",
            path=validator_path,
        )
    try:
        module = load_bundled_source_module(
            "_design_dna_project_contrast_audit",
            validator_path,
        )
        validator = getattr(module, "validate_contract_payload")
        errors, _contract = validator(payload)
    except (AttributeError, ImportError, OSError, TypeError, ValueError) as exc:
        raise StateError(
            "project-contrast-validator-failed",
            str(exc),
            path=validator_path,
        ) from exc
    if not isinstance(errors, list) or not all(
        isinstance(entry, dict)
        and set(entry) == {"path", "code", "message"}
        and all(isinstance(entry[key], str) for key in entry)
        for entry in errors
    ):
        raise StateError(
            "project-contrast-validator-invalid-output",
            "The bundled Project Contrast validator returned an unsupported result.",
            path=validator_path,
        )
    return payload, errors


def run_project_contrast_readiness_audit(
    path: Path,
    project: Path,
) -> dict[str, object]:
    """Run the bundled Project Contrast evidence audit without writing a report."""

    payload, structural_errors = validate_project_contrast_record(path)
    if structural_errors:
        raise StateError(
            "project-contrast-validator-failed",
            structural_errors[0]["message"],
            path=path,
        )
    validator_path = Path(__file__).with_name("project_contrast_audit.py")
    try:
        module = load_bundled_source_module(
            "_design_dna_project_contrast_readiness_audit",
            validator_path,
        )
        audit = getattr(module, "audit_payload")
        report = audit(project.resolve(strict=True), payload)
    except (AttributeError, OSError, TypeError, UnicodeError, ValueError) as exc:
        raise StateError(
            "project-contrast-validator-failed",
            str(exc),
            path=validator_path,
        ) from exc
    if (
        not isinstance(report, dict)
        or report.get("automatic_aesthetic_pass") is not False
        or not isinstance(report.get("ready"), bool)
        or not isinstance(report.get("gaps"), list)
        or not isinstance(report.get("findings"), list)
    ):
        raise StateError(
            "project-contrast-validator-invalid-output",
            "The bundled Project Contrast auditor returned an unsupported result.",
            path=validator_path,
        )
    return report


def validate_direction_challenge_record(
    path: Path,
) -> tuple[object, list[dict[str, str]]]:
    """Validate the planning-safe Direction Challenge JSON record.

    Schema-3 render package integrity, source snapshots, and exact capture
    bindings remain an audit/readiness concern so initialization can create an
    honest draft without manufacturing proof.
    """

    payload = read_json(path)
    validator_path = Path(__file__).with_name("direction_challenge_audit.py")
    if not validator_path.is_file() or is_reparse(validator_path):
        raise StateError(
            "direction-challenge-validator-missing",
            "The bundled Direction Challenge validator is missing or redirected.",
            path=validator_path,
        )
    try:
        module = load_bundled_source_module(
            "_design_dna_direction_challenge_audit",
            validator_path,
        )
        validator = getattr(module, "validate_contract_payload")
        errors, _contract = validator(payload)
    except (AttributeError, ImportError, OSError, TypeError, ValueError) as exc:
        raise StateError(
            "direction-challenge-validator-failed",
            str(exc),
            path=validator_path,
        ) from exc
    if not isinstance(errors, list) or not all(
        isinstance(entry, dict)
        and set(entry) == {"path", "code", "message"}
        and all(isinstance(entry[key], str) for key in entry)
        for entry in errors
    ):
        raise StateError(
            "direction-challenge-validator-invalid-output",
            "The bundled Direction Challenge validator returned an unsupported result.",
            path=validator_path,
        )
    return payload, errors


def run_direction_challenge_readiness_audit(
    path: Path,
    project: Path,
) -> dict[str, object]:
    """Run the bundled Direction Challenge audit without writing a report."""

    payload, structural_errors = validate_direction_challenge_record(path)
    if structural_errors:
        raise StateError(
            "direction-challenge-validator-failed",
            structural_errors[0]["message"],
            path=path,
        )
    validator_path = Path(__file__).with_name("direction_challenge_audit.py")
    try:
        module = load_bundled_source_module(
            "_design_dna_direction_challenge_readiness_audit",
            validator_path,
        )
        audit = getattr(module, "audit_payload")
        report = audit(project.resolve(strict=True), payload)
    except (AttributeError, OSError, TypeError, UnicodeError, ValueError) as exc:
        raise StateError(
            "direction-challenge-validator-failed",
            str(exc),
            path=validator_path,
        ) from exc
    if (
        not isinstance(report, dict)
        or report.get("automatic_aesthetic_pass") is not False
        or not isinstance(report.get("ready"), bool)
        or not isinstance(report.get("gaps"), list)
        or not isinstance(report.get("findings"), list)
    ):
        raise StateError(
            "direction-challenge-validator-invalid-output",
            "The bundled Direction Challenge auditor returned an unsupported result.",
            path=validator_path,
        )
    return report


def validate_connected_public_experience_record(
    path: Path,
) -> tuple[object, list[dict[str, str]]]:
    """Validate the planning-safe opt-in continuity record.

    The selected capability can remain an intentional draft while direction is
    still open. Exact final captures and functional-path results are evaluated
    only by its readiness audit.
    """

    payload = read_json(path)
    validator_path = Path(__file__).with_name(
        "connected_public_experience_audit.py"
    )
    if not validator_path.is_file() or is_reparse(validator_path):
        raise StateError(
            "connected-public-experience-validator-missing",
            "The bundled Connected Public Experience validator is missing or redirected.",
            path=validator_path,
        )
    try:
        module = load_bundled_source_module(
            "_design_dna_connected_public_experience_audit",
            validator_path,
        )
        validator = getattr(module, "validate_contract_payload")
        errors, _contract = validator(payload)
    except (AttributeError, ImportError, OSError, TypeError, ValueError) as exc:
        raise StateError(
            "connected-public-experience-validator-failed",
            str(exc),
            path=validator_path,
        ) from exc
    if not isinstance(errors, list) or not all(
        isinstance(entry, dict)
        and set(entry) == {"path", "code", "message"}
        and all(isinstance(entry[key], str) for key in entry)
        for entry in errors
    ):
        raise StateError(
            "connected-public-experience-validator-invalid-output",
            "The bundled Connected Public Experience validator returned an unsupported result.",
            path=validator_path,
        )
    return payload, errors


def run_connected_public_experience_readiness_audit(
    path: Path,
    project: Path,
    evidence_capabilities: tuple[str, ...] | list[str] | set[str],
) -> dict[str, object]:
    """Run the opt-in continuity readiness audit without writing a report."""

    payload, structural_errors = validate_connected_public_experience_record(
        path,
    )
    if structural_errors:
        raise StateError(
            "connected-public-experience-validator-failed",
            structural_errors[0]["message"],
            path=path,
        )
    validator_path = Path(__file__).with_name(
        "connected_public_experience_audit.py"
    )
    try:
        module = load_bundled_source_module(
            "_design_dna_connected_public_experience_readiness_audit",
            validator_path,
        )
        audit = getattr(module, "audit_payload")
        report = audit(
            project.resolve(strict=True),
            payload,
            set(evidence_capabilities),
        )
    except (AttributeError, OSError, TypeError, UnicodeError, ValueError) as exc:
        raise StateError(
            "connected-public-experience-validator-failed",
            str(exc),
            path=validator_path,
        ) from exc
    if (
        not isinstance(report, dict)
        or report.get("automatic_aesthetic_pass") is not False
        or not isinstance(report.get("ready"), bool)
        or not isinstance(report.get("gaps"), list)
        or not isinstance(report.get("findings"), list)
    ):
        raise StateError(
            "connected-public-experience-validator-invalid-output",
            "The bundled Connected Public Experience auditor returned an unsupported result.",
            path=validator_path,
        )
    return report


def run_connected_public_experience_prebuild_audit(
    path: Path,
    project: Path,
    evidence_capabilities: tuple[str, ...] | list[str] | set[str],
) -> dict[str, object]:
    """Run the continuity direction-stage gate without demanding final closure."""

    payload, structural_errors = validate_connected_public_experience_record(path)
    if structural_errors:
        raise StateError(
            "connected-public-experience-validator-failed",
            structural_errors[0]["message"],
            path=path,
        )
    validator_path = Path(__file__).with_name(
        "connected_public_experience_audit.py"
    )
    try:
        module = load_bundled_source_module(
            "_design_dna_connected_public_experience_prebuild_audit",
            validator_path,
        )
        audit = getattr(module, "audit_prebuild_payload")
        report = audit(
            project.resolve(strict=True),
            payload,
            set(evidence_capabilities),
            capability_context="state",
        )
    except (AttributeError, OSError, TypeError, UnicodeError, ValueError) as exc:
        raise StateError(
            "connected-public-experience-validator-failed",
            str(exc),
            path=validator_path,
        ) from exc
    if (
        not isinstance(report, dict)
        or report.get("automatic_aesthetic_pass") is not False
        or report.get("phase") != "prebuild"
        or not isinstance(report.get("ready"), bool)
        or not isinstance(report.get("implementation_authorized"), bool)
        or not isinstance(report.get("gaps"), list)
        or not isinstance(report.get("findings"), list)
    ):
        raise StateError(
            "connected-public-experience-validator-invalid-output",
            "The bundled Connected Public Experience prebuild auditor returned an unsupported result.",
            path=validator_path,
        )
    return report


def run_owner_rejection_audit(path: Path, project: Path) -> dict[str, object]:
    """Validate and byte-verify one optional scoped owner rejection record."""

    try:
        payload = read_json(path)
    except StateError as exc:
        raise StateError(
            "owner-rejection-invalid",
            str(exc),
            path=path,
        ) from exc
    validator_path = Path(__file__).with_name("owner_rejection_audit.py")
    if not validator_path.is_file() or is_reparse(validator_path):
        raise StateError(
            "owner-rejection-validator-missing",
            "The bundled owner-rejection validator is missing or redirected.",
            path=validator_path,
        )
    try:
        module = load_bundled_source_module(
            "_design_dna_owner_rejection_audit",
            validator_path,
        )
        audit = getattr(module, "audit_payload")
        report = audit(project.resolve(strict=True), payload)
    except (AttributeError, OSError, TypeError, UnicodeError, ValueError) as exc:
        raise StateError(
            "owner-rejection-validator-failed",
            str(exc),
            path=validator_path,
        ) from exc
    if (
        not isinstance(report, dict)
        or not isinstance(report.get("structural_valid"), bool)
        or not isinstance(report.get("ready"), bool)
        or not isinstance(report.get("findings"), list)
        or not isinstance(report.get("gaps"), list)
        or not isinstance(report.get("lifecycle"), dict)
    ):
        raise StateError(
            "owner-rejection-validator-invalid-output",
            "The bundled owner-rejection auditor returned an unsupported result.",
            path=validator_path,
        )
    return report


def write_stage_owner(stage_parent: Path, lock: ProjectMutationLock) -> None:
    lock.assert_owned()
    marker = stage_parent / STAGE_OWNER_RECORD
    payload = {
        "schema_version": 1,
        "record_type": "design-dna-state-stage-owner",
        "owner_token": lock.owner_token,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with marker.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(
                payload,
                stream,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        try:
            stage_parent.rmdir()
        except OSError:
            pass
        raise StateError(
            "stage-owner-write-failed",
            str(exc),
            path=marker,
        ) from exc


def verify_stage_owner(stage_parent: Path, owner_token: str) -> None:
    marker = stage_parent / STAGE_OWNER_RECORD
    if not marker.is_file() or is_reparse(marker):
        raise StateError(
            "stage-owner-missing",
            "Refusing to remove a staging directory without its ordinary owner record.",
            path=marker,
        )
    payload = read_json(marker)
    if (
        not isinstance(payload, dict)
        or set(payload)
        != {
            "schema_version",
            "record_type",
            "owner_token",
            "created_at",
        }
        or payload.get("schema_version") != 1
        or payload.get("record_type") != "design-dna-state-stage-owner"
        or payload.get("owner_token") != owner_token
    ):
        raise StateError(
            "stage-owner-mismatch",
            "Refusing to remove a staging directory owned by another token.",
            path=marker,
        )


def release_version(skill_root: Path) -> str:
    release_path = skill_root / "release.json"
    try:
        payload = strict_json(
            release_path.read_text(encoding="utf-8"),
            path=release_path,
        )
        if not isinstance(payload, dict):
            raise StateError(
                "invalid-package-release",
                "release.json must contain a JSON object.",
                path=release_path,
            )
        if set(payload) != {"package", "version", "state_schema_version"}:
            raise StateError(
                "invalid-package-release",
                "release.json has an unsupported shape.",
                path=release_path,
            )
        if (
            payload.get("package") != "design-dna"
            or payload.get("state_schema_version") != STATE_SCHEMA_VERSION
        ):
            raise StateError(
                "invalid-package-release",
                "release.json package or state schema identity is invalid.",
                path=release_path,
            )
        version = payload.get("version")
        if not isinstance(version, str) or not SEMVER.fullmatch(version):
            raise StateError(
                "invalid-package-release",
                "release.json must contain a valid SemVer version.",
                path=release_path,
            )
        return version
    except (OSError, UnicodeError, StateError) as exc:
        detail = (
            error_record(exc)
            if isinstance(exc, StateError)
            else {
                "code": "package-release-read-failed",
                "message": str(exc),
                "path": str(release_path),
            }
        )
        raise StateError(
            "package-release-unavailable",
            "The packaged skill release metadata is missing or invalid.",
            path=release_path,
            details={"cause": detail},
        ) from exc


def state_manifest(
    version: str,
    records: tuple[str, ...],
    assurance_profiles: tuple[str, ...],
    evidence_capabilities: tuple[str, ...] | list[str] = (),
    extension_records: tuple[dict[str, object], ...] | list[dict[str, object]] = (),
) -> str:
    return json.dumps(
        {
            "schema_version": STATE_SCHEMA_VERSION,
            "created_with": f"design-dna {version}",
            "created": date.today().isoformat(),
            "classification": "internal",
            "assurance_profiles": list(assurance_profiles),
            "records": list(records),
            "evidence_contract": evidence_contract_payload(
                assurance_profiles,
                evidence_capabilities,
                extension_records,
            ),
        },
        indent=2,
    ) + "\n"


def remove_markdown_sections(text: str, headings: set[str]) -> str:
    """Remove complete level-two sections without interpreting their contents."""
    if not headings:
        return text
    escaped = "|".join(re.escape(heading) for heading in sorted(headings))
    pattern = re.compile(
        rf"(?ms)^## (?:{escaped})[ \t]*\r?\n.*?(?=^## |\Z)"
    )
    return pattern.sub("", text)


def template_text(
    template_root: Path,
    filename: str,
    version: str,
    assurance_profiles: tuple[str, ...] = ("standard",),
) -> str:
    path = template_root / filename
    assert_safe_tree(template_root)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StateError("template-read-failed", str(exc), path=path) from exc
    rendered = text.replace("__DESIGN_DNA_VERSION__", f"design-dna {version}")
    if (
        filename == "direction-template.md"
        and set(assurance_profiles) == {"quick"}
    ):
        rendered = remove_markdown_sections(
            rendered,
            REFERENCE_SOURCED_DIRECTION_SECTIONS,
        )
    if "__DESIGN_DNA_VERSION__" in rendered:
        raise StateError("unresolved-template-token", "Template token was not resolved.", path=path)
    if filename in SUBSTANTIVE_TEMPLATE_FILES:
        rendered = update_frontmatter_text(
            rendered,
            path=path,
            updates={"record_status": "draft"},
        )
    return rendered


CAPABILITY_SECTION_PROMPTS = {
    ("range-study", "direction"): (
        "Range-study contract",
        "Name the shared identity, navigation, truth, accessibility, and "
        "release rules; reference the route-family record; then describe only "
        "the deliberate differences that matter for this project.",
    ),
    ("range-study", "visual-review"): (
        "Range-study review",
        "Reference the route atlas and direct-entry, link, and silhouette "
        "results. Record repeated structures that need revision without "
        "inventing an authorship score.",
    ),
    ("batch-study", "direction"): (
        "Batch Study protocol",
        "Reference the frozen independent briefs, frozen source packets, and "
        "batch-range record. Name the producer contexts, sibling-output "
        "exposure timing, allowed shared tooling or exceptions, isolated build "
        "roots, project-derived viewport classes, neutral-label review, unprimed "
        "review boundary, evidence-based block criteria, and capture/contact-sheet "
        "authorization, access, retention, and transformation handling. Treat "
        "implementation isolation as human-auditable evidence rather than "
        "automatic proof. Do not prescribe visual difference or a novelty quota.",
    ),
    ("batch-study", "visual-review"): (
        "Batch Study review",
        "Reference the batch-range audit path and hash, built and correctly "
        "blocked cases, unprimed site observations, neutral-label whole-system "
        "evidence, resolved data handling, implementation-isolation attestations, "
        "and contextual findings. State explicitly that evidence coverage is not "
        "an automatic aesthetic pass, that attestations are not automated proof, "
        "and that recorded transformations do not establish pixel redaction.",
    ),
    ("cultural-context", "direction"): (
        "Cultural context and authority",
        "Record terminology, representation boundaries, source authority, "
        "unresolved questions, and the accountable or independent review that "
        "is required. Producer self-review cannot certify acceptance.",
    ),
    ("cultural-context", "visual-review"): (
        "Cultural review",
        "Record the reviewer relationship, exact scope, evidence, disposition, "
        "and remaining representational limits. Leave release blocked while "
        "required authority is missing.",
    ),
    ("high-risk", "direction"): (
        "Risk and specialist authority",
        "Identify only the consequential legal, privacy, security, data, claim, "
        "research, or operational risks that apply, with authority and owner.",
    ),
    ("high-risk", "visual-review"): (
        "Risk closure",
        "Bind each applicable specialist result or explicit unverified block to "
        "the reviewed build. Do not convert missing specialist evidence into a "
        "design approval.",
    ),
    ("asset-led", "direction"): (
        "Asset provenance plan",
        "Reference the asset manifest and record only the rights, source, crop, "
        "generation, disclosure, privacy, and expiry decisions that apply.",
    ),
    ("asset-led", "visual-review"): (
        "Asset review",
        "Reference rendered asset evidence and unresolved rights, provenance, "
        "artifact, crop, loading, disclosure, or approval issues.",
    ),
}


def capability_sections_text(
    record: str,
    capabilities: tuple[str, ...],
) -> str:
    sections = [
        (
            f"## {heading}\n\n{prompt}\n\n"
            "__REPLACE_WITH_APPLICABLE_EVIDENCE_OR_EXPLICIT_BLOCK__\n"
        )
        for capability in capabilities
        for (heading, prompt) in [
            CAPABILITY_SECTION_PROMPTS.get((capability, record), ("", ""))
        ]
        if heading
    ]
    return ("\n" + "\n".join(sections)) if sections else ""


def strict_scalar(value: str, *, field: str, path: Path) -> str:
    value = value.strip()
    if not value:
        raise StateError("invalid-yaml", f"{field} has an empty value.", path=path)
    if value[0] in {'"', "'"}:
        if len(value) < 2 or value[-1] != value[0]:
            raise StateError("invalid-yaml", f"{field} has an unterminated quote.", path=path)
        if value[0] == '"':
            try:
                unquoted = json.loads(value)
            except json.JSONDecodeError as exc:
                raise StateError(
                    "invalid-yaml",
                    f"{field} has an invalid quoted scalar.",
                    path=path,
                ) from exc
            if not isinstance(unquoted, str):
                raise StateError(
                    "invalid-yaml",
                    f"{field} must be a string scalar.",
                    path=path,
                )
        else:
            unquoted = value[1:-1].replace("''", "'")
        if not unquoted.strip():
            raise StateError("invalid-yaml", f"{field} has an empty value.", path=path)
        return unquoted
    if any(token in value for token in ("[", "]", "{", "}")):
        raise StateError("invalid-yaml", f"{field} must be a scalar.", path=path)
    return value


def parse_flat_yaml(text: str, *, path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[:1].isspace() or ":" not in line:
            raise StateError("invalid-yaml", f"Unsupported YAML at line {number}.", path=path)
        key, value = line.split(":", 1)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            raise StateError("invalid-yaml", f"Invalid key at line {number}.", path=path)
        if key in result:
            raise StateError("duplicate-yaml-key", f"Duplicate key {key!r}.", path=path)
        result[key] = strict_scalar(value, field=key, path=path)
    return result


def parse_yaml_scalar(value: str, *, line: int, path: Path) -> object:
    """Parse the deliberately small scalar subset used by assets.yml."""
    value = value.strip()
    if not value:
        raise StateError(
            "invalid-yaml",
            f"Missing scalar value at line {line}.",
            path=path,
        )
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if value in {"true", "false"}:
        return value == "true"
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)", value):
        return int(value)
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise StateError(
                "invalid-yaml",
                f"Invalid double-quoted string at line {line}: {exc}",
                path=path,
            ) from exc
        if not isinstance(parsed, str):
            raise StateError(
                "invalid-yaml",
                f"Only quoted strings are supported at line {line}.",
                path=path,
            )
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise StateError(
                "invalid-yaml",
                f"Unterminated single-quoted string at line {line}.",
                path=path,
            )
        return value[1:-1].replace("''", "'")
    if value[0] in "-?:,[]{}#&*!|>@`" or " #" in value:
        raise StateError(
            "invalid-yaml",
            f"Unsupported plain scalar at line {line}; quote this value.",
            path=path,
        )
    return value


def parse_strict_yaml_subset(text: str, *, path: Path) -> object:
    """Parse block maps/lists without tags, aliases, merging, or implicit coercions.

    This is intentionally not a general YAML parser. It accepts the block-style,
    two-space-indented subset emitted by the bundled asset template and rejects
    syntax whose meaning would require YAML's complex type system.
    """
    tokens: list[tuple[int, int, str]] = []
    for number, raw_line in enumerate(text.splitlines(), 1):
        if "\t" in raw_line:
            raise StateError(
                "invalid-yaml",
                f"Tabs are not allowed at line {number}.",
                path=path,
            )
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indentation = len(raw_line) - len(raw_line.lstrip(" "))
        if indentation % 2:
            raise StateError(
                "invalid-yaml",
                f"Indentation must use two-space steps at line {number}.",
                path=path,
            )
        content = raw_line[indentation:]
        if content in {"---", "..."}:
            raise StateError(
                "invalid-yaml",
                f"YAML document markers are not supported at line {number}.",
                path=path,
            )
        tokens.append((number, indentation, content))
    if not tokens:
        raise StateError("invalid-yaml", "YAML document is empty.", path=path)

    index = 0

    def split_mapping(content: str, number: int) -> tuple[str, str]:
        if ":" not in content:
            raise StateError(
                "invalid-yaml",
                f"Expected a mapping entry at line {number}.",
                path=path,
            )
        key, value = content.split(":", 1)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            raise StateError(
                "invalid-yaml",
                f"Invalid mapping key at line {number}.",
                path=path,
            )
        return key, value.strip()

    def parse_mapping(
        indentation: int,
        seed: tuple[str, object] | None = None,
    ) -> dict[str, object]:
        nonlocal index
        result: dict[str, object] = {}
        if seed is not None:
            result[seed[0]] = seed[1]
        while index < len(tokens):
            number, current_indent, content = tokens[index]
            if current_indent < indentation:
                break
            if current_indent > indentation:
                raise StateError(
                    "invalid-yaml",
                    f"Unexpected indentation at line {number}.",
                    path=path,
                )
            if content == "-" or content.startswith("- "):
                break
            key, raw_value = split_mapping(content, number)
            if key in result:
                raise StateError(
                    "duplicate-yaml-key",
                    f"Duplicate key {key!r} at line {number}.",
                    path=path,
                )
            index += 1
            if raw_value:
                result[key] = parse_yaml_scalar(
                    raw_value,
                    line=number,
                    path=path,
                )
                continue
            if index >= len(tokens) or tokens[index][1] <= indentation:
                raise StateError(
                    "invalid-yaml",
                    f"Key {key!r} has no nested value at line {number}.",
                    path=path,
                )
            if tokens[index][1] != indentation + 2:
                raise StateError(
                    "invalid-yaml",
                    f"Nested value for {key!r} must indent two spaces at line {tokens[index][0]}.",
                    path=path,
                )
            result[key] = parse_block(indentation + 2)
        return result

    def parse_list(indentation: int) -> list[object]:
        nonlocal index
        result: list[object] = []
        while index < len(tokens):
            number, current_indent, content = tokens[index]
            if current_indent < indentation:
                break
            if current_indent > indentation:
                raise StateError(
                    "invalid-yaml",
                    f"Unexpected list indentation at line {number}.",
                    path=path,
                )
            if content != "-" and not content.startswith("- "):
                break
            remainder = content[1:].strip()
            index += 1
            if not remainder:
                if index >= len(tokens) or tokens[index][1] != indentation + 2:
                    raise StateError(
                        "invalid-yaml",
                        f"List item at line {number} has no nested value.",
                        path=path,
                    )
                result.append(parse_block(indentation + 2))
                continue
            if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*:", remainder):
                key, raw_value = split_mapping(remainder, number)
                if not raw_value:
                    raise StateError(
                        "invalid-yaml",
                        f"An inline list mapping needs a scalar value at line {number}.",
                        path=path,
                    )
                first_value = parse_yaml_scalar(
                    raw_value,
                    line=number,
                    path=path,
                )
                if index < len(tokens) and tokens[index][1] == indentation + 2:
                    result.append(
                        parse_mapping(
                            indentation + 2,
                            seed=(key, first_value),
                        )
                    )
                else:
                    result.append({key: first_value})
                continue
            result.append(parse_yaml_scalar(remainder, line=number, path=path))
        return result

    def parse_block(indentation: int) -> object:
        if index >= len(tokens):
            raise StateError("invalid-yaml", "Unexpected end of YAML.", path=path)
        number, current_indent, content = tokens[index]
        if current_indent != indentation:
            raise StateError(
                "invalid-yaml",
                f"Unexpected indentation at line {number}.",
                path=path,
            )
        if content == "-" or content.startswith("- "):
            return parse_list(indentation)
        return parse_mapping(indentation)

    parsed = parse_block(tokens[0][1])
    if tokens[0][1] != 0:
        raise StateError(
            "invalid-yaml",
            "The top-level mapping must not be indented.",
            path=path,
        )
    if index != len(tokens):
        number = tokens[index][0]
        raise StateError(
            "invalid-yaml",
            f"Unsupported YAML structure at line {number}.",
            path=path,
        )
    return parsed


def dump_strict_yaml_subset(value: object, indentation: int = 0) -> str:
    """Serialize the exact safe subset accepted by parse_strict_yaml_subset."""

    prefix = " " * indentation
    lines: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(
                    dump_strict_yaml_subset(item, indentation + 2)
                )
            elif isinstance(item, list):
                if not item:
                    lines.append(f"{prefix}{key}: []")
                else:
                    lines.append(f"{prefix}{key}:")
                    lines.append(
                        dump_strict_yaml_subset(item, indentation + 2)
                    )
            else:
                lines.append(
                    f"{prefix}{key}: {yaml_subset_scalar(item)}"
                )
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(
                    dump_strict_yaml_subset(item, indentation + 2)
                )
            else:
                lines.append(f"{prefix}- {yaml_subset_scalar(item)}")
    else:
        raise StateError(
            "invalid-yaml-serialization",
            "The YAML root must be a mapping or list.",
        )
    return "\n".join(lines)


def yaml_subset_scalar(value: object) -> str:
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise StateError(
        "invalid-yaml-serialization",
        f"Unsupported YAML scalar type: {type(value).__name__}.",
    )


ASSET_FIELDS = {
    "id",
    "asset_type",
    "usage_locations",
    "content_job",
    "publication_status",
    "source_url",
    "source_path",
    "source_sha256",
    "creator",
    "origin",
    "obtained_date",
    "license_or_terms",
    "attribution_required",
    "attribution_text",
    "modification_limits",
    "modifications",
    "factual_status",
    "depicts_or_claim",
    "privacy_review",
    "owner_approval",
    "concept_disclosure",
    "migration_review",
    "generated",
    "delivery",
    "accessibility",
    "replacement",
}
ASSET_OPTIONAL_FIELDS = {
    "privacy_review_owner",
    "privacy_review_date",
    "privacy_review_reason",
    "owner_approval_owner",
    "owner_approval_date",
    "owner_approval_reason",
    "generated_media_provenance",
    "source_mapping",
}
ASSET_NESTED_FIELDS = {
    "generated": {
        "used",
        "authorization_basis",
        "tool_or_model",
        "prompt_or_digest",
        "generated_at",
        "source_inputs",
        "rejected_outputs",
        "contact_sheet_path",
        "contact_sheet_sha256",
        "artifact_inspection",
        "responsive_crop_evidence",
    },
    "concept_disclosure": {
        "decision",
        "reason",
        "text",
    },
    "migration_review": {
        "required",
        "source_schema_version",
        "reason",
        "unresolved_fields",
    },
    "generated_media_provenance": {
        "applicability",
        "jurisdiction",
        "roles",
        "transformation_chain",
        "credential_detected",
        "credential_validated",
        "credential_preserved",
        "visible_disclosure_basis",
        "visible_disclosure_text",
        "legal_review_status",
        "legal_review_owner",
        "legal_review_date",
        "legal_review_reason",
    },
    "delivery": {
        "source_dimensions",
        "output_dimensions",
        "formats",
        "responsive_behavior",
        "intrinsic_dimensions_reserved",
    },
    "accessibility": {
        "treatment",
        "alt_text",
        "caption_or_transcript",
    },
    "replacement": {
        "status",
        "owner",
        "due_date",
    },
    "source_mapping": {
        "source_rank",
        "source_id",
        "observation",
        "observation_sha256",
        "source_state_id",
        "source_component_or_behavior",
        "measured_transfer",
        "evidence_path",
        "evidence_sha256",
    },
}
ASSET_LIST_FIELDS = {
    "usage_locations",
    "generated.source_inputs",
    "generated.rejected_outputs",
    "generated.responsive_crop_evidence",
    "migration_review.unresolved_fields",
    "generated_media_provenance.roles",
    "generated_media_provenance.transformation_chain",
    "delivery.output_dimensions",
    "delivery.formats",
}
ASSET_BOOLEAN_FIELDS = {
    "attribution_required",
    "generated.used",
    "migration_review.required",
    "delivery.intrinsic_dimensions_reserved",
}
ASSET_TYPES = {
    "image",
    "video",
    "audio",
    "font",
    "document",
    "map",
    "embed",
    "other",
}
ASSET_DISCLOSURE_DECISIONS = {
    "pending",
    "required",
    "not-required",
}
ASSET_ORIGINS = {
    "owner-supplied",
    "first-party",
    "licensed",
    "generated",
    "other",
}
ASSET_PUBLICATION_STATUSES = {
    "internal-only",
    "planned-public",
    "public",
    "prohibited",
}
ASSET_FACTUAL_STATUSES = {
    "pending",
    "approved",
    "concept",
    "placeholder",
    "prohibited",
}
ASSET_PRIVACY_STATUSES = {
    "pending",
    "not-required",
    "approved",
    "rejected",
}
ASSET_OWNER_APPROVAL_STATUSES = {
    "pending",
    "approved",
    "rejected",
}
ASSET_ACCESSIBILITY_TREATMENTS = {
    "pending",
    "decorative",
    "informative",
    "functional",
    "complex",
    "not-applicable",
}
ASSET_REPLACEMENT_STATUSES = {
    "not-needed",
    "pending",
    "required",
    "scheduled",
    "replaced",
}
ASSET_GENERATED_MEDIA_APPLICABILITY = {
    "pending",
    "applicable",
    "not-applicable",
    "uncertain",
}
ASSET_GENERATED_MEDIA_ROLES = {
    "provider",
    "deployer",
    "publisher",
}
ASSET_CREDENTIAL_DETECTED_STATUSES = {
    "pending",
    "detected",
    "not-detected",
    "unknown",
    "not-applicable",
}
ASSET_CREDENTIAL_VALIDATED_STATUSES = {
    "pending",
    "validated",
    "invalid",
    "unverifiable",
    "not-applicable",
}
ASSET_CREDENTIAL_PRESERVED_STATUSES = {
    "pending",
    "preserved",
    "not-preserved",
    "unknown",
    "not-applicable",
}
ASSET_GENERATED_MEDIA_LEGAL_STATUSES = {
    "pending",
    "not-required",
    "approved",
    "changes-required",
    "rejected",
}


def require_exact_keys(
    value: object,
    expected: set[str],
    *,
    label: str,
    path: Path,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise StateError(
            "invalid-asset-manifest",
            f"{label} must be a mapping.",
            path=path,
        )
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing or unknown:
        messages = []
        if missing:
            messages.append("missing " + ", ".join(missing))
        if unknown:
            messages.append("unknown " + ", ".join(unknown))
        raise StateError(
            "invalid-asset-manifest",
            f"{label} has " + "; ".join(messages) + ".",
            path=path,
        )
    return value


def require_required_and_optional_keys(
    value: object,
    required: set[str],
    optional: set[str],
    *,
    label: str,
    path: Path,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise StateError(
            "invalid-asset-manifest",
            f"{label} must be a mapping.",
            path=path,
        )
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required - optional)
    if missing or unknown:
        messages = []
        if missing:
            messages.append("missing " + ", ".join(missing))
        if unknown:
            messages.append("unknown " + ", ".join(unknown))
        raise StateError(
            "invalid-asset-manifest",
            f"{label} has " + "; ".join(messages) + ".",
            path=path,
        )
    return value


def validate_asset_manifest(
    path: Path,
    current_version: str,
    project_root: Path,
) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise StateError("state-read-failed", str(exc), path=path) from exc
    if "__DESIGN_DNA_VERSION__" in text:
        raise StateError(
            "unresolved-template-token",
            "assets.yml contains an unresolved template token.",
            path=path,
        )
    payload = require_exact_keys(
        parse_strict_yaml_subset(text, path=path),
        {"schema_version", "created_with", "classification", "assets"},
        label="assets.yml",
        path=path,
    )
    if (
        type(payload["schema_version"]) is not int
        or payload["schema_version"] != ASSET_SCHEMA_VERSION
    ):
        raise StateError(
            "invalid-asset-manifest",
            (
                "assets.yml schema_version must be integer "
                f"{ASSET_SCHEMA_VERSION}; run --migrate for schema 1."
            ),
            path=path,
        )
    created_with = payload["created_with"]
    if (
        not isinstance(created_with, str)
        or not created_with.startswith("design-dna ")
        or not SEMVER.fullmatch(created_with.removeprefix("design-dna "))
    ):
        raise StateError(
            "invalid-asset-manifest",
            "assets.yml created_with must contain a valid Design DNA version.",
            path=path,
        )
    if payload["classification"] not in CLASSIFICATIONS:
        raise StateError(
            "invalid-asset-manifest",
            "assets.yml has an invalid classification.",
            path=path,
        )
    assets = payload["assets"]
    if not isinstance(assets, list):
        raise StateError(
            "invalid-asset-manifest",
            "assets.yml assets must be a list.",
            path=path,
        )
    seen_ids: set[str] = set()
    string_fields = (
        (ASSET_FIELDS | ASSET_OPTIONAL_FIELDS)
        - set(ASSET_NESTED_FIELDS)
        - {
            "usage_locations",
            "attribution_required",
        }
    )
    for asset_index, raw_asset in enumerate(assets):
        label = f"assets[{asset_index}]"
        asset = require_required_and_optional_keys(
            raw_asset,
            ASSET_FIELDS,
            ASSET_OPTIONAL_FIELDS,
            label=label,
            path=path,
        )
        for field in string_fields:
            if field in asset and not isinstance(asset[field], str):
                raise StateError(
                    "invalid-asset-manifest",
                    f"{label}.{field} must be a string.",
                    path=path,
                )
        asset_id = asset["id"]
        if not re.fullmatch(r"ASSET-[0-9]{3,}", asset_id):
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.id must match ASSET- followed by at least three digits.",
                path=path,
            )
        if asset_id in seen_ids:
            raise StateError(
                "invalid-asset-manifest",
                f"Duplicate asset id {asset_id}.",
                path=path,
            )
        seen_ids.add(asset_id)
        missing_core_evidence = [
            field
            for field in (
                "content_job",
                "creator",
                "obtained_date",
                "depicts_or_claim",
            )
            if not non_placeholder(asset[field])
        ]
        if missing_core_evidence:
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label} is a real asset row and requires evidence in "
                    + ", ".join(missing_core_evidence)
                    + ". Use assets: [] when no assets are recorded."
                ),
                path=path,
            )
        if asset["origin"] not in ASSET_ORIGINS:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.origin has an unsupported value.",
                path=path,
            )
        if asset["asset_type"] not in ASSET_TYPES:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.asset_type has an unsupported value.",
                path=path,
            )
        if asset["publication_status"] not in ASSET_PUBLICATION_STATUSES:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.publication_status has an unsupported value.",
                path=path,
            )
        if asset["factual_status"] not in ASSET_FACTUAL_STATUSES:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.factual_status has an unsupported value.",
                path=path,
            )
        privacy_status = asset["privacy_review"]
        if privacy_status not in ASSET_PRIVACY_STATUSES:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.privacy_review has an unsupported value.",
                path=path,
            )
        if privacy_status != "pending":
            missing_review_context = [
                field
                for field in (
                    "privacy_review_owner",
                    "privacy_review_date",
                    "privacy_review_reason",
                )
                if not non_placeholder(str(asset.get(field, "")))
            ]
            if missing_review_context:
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.privacy_review {privacy_status!r} requires "
                        + ", ".join(missing_review_context)
                        + "."
                    ),
                    path=path,
                )
        owner_approval = asset["owner_approval"]
        if owner_approval not in ASSET_OWNER_APPROVAL_STATUSES:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.owner_approval has an unsupported value.",
                path=path,
            )
        if owner_approval != "pending":
            missing_approval_context = [
                field
                for field in (
                    "owner_approval_owner",
                    "owner_approval_date",
                    "owner_approval_reason",
                )
                if not non_placeholder(str(asset.get(field, "")))
            ]
            if missing_approval_context:
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.owner_approval {owner_approval!r} requires "
                        + ", ".join(missing_approval_context)
                        + "."
                    ),
                    path=path,
                )
        for date_field in (
            "obtained_date",
            "privacy_review_date",
            "owner_approval_date",
        ):
            date_value = asset.get(date_field, "")
            if date_value:
                try:
                    parsed_date = date.fromisoformat(date_value)
                    if parsed_date > date.today():
                        raise ValueError("date is in the future")
                except ValueError as exc:
                    raise StateError(
                        "invalid-asset-manifest",
                        (
                            f"{label}.{date_field} must be a non-future ISO "
                            "date or empty."
                        ),
                        path=path,
                    ) from exc
        for nested_name, nested_fields in ASSET_NESTED_FIELDS.items():
            if nested_name not in asset:
                continue
            nested = require_exact_keys(
                asset[nested_name],
                nested_fields,
                label=f"{label}.{nested_name}",
                path=path,
            )
            if nested_name == "source_mapping":
                continue
            for field, value in nested.items():
                dotted = f"{nested_name}.{field}"
                if dotted in ASSET_BOOLEAN_FIELDS:
                    if type(value) is not bool:
                        raise StateError(
                            "invalid-asset-manifest",
                            f"{label}.{dotted} must be a boolean.",
                            path=path,
                        )
                elif dotted in ASSET_LIST_FIELDS:
                    if not isinstance(value, list) or not all(
                        isinstance(item, str) for item in value
                    ):
                        raise StateError(
                            "invalid-asset-manifest",
                            f"{label}.{dotted} must be a list of strings.",
                            path=path,
                        )
                    if (
                        any(not item.strip() for item in value)
                        or len(value) != len(set(value))
                    ):
                        raise StateError(
                            "invalid-asset-manifest",
                            (
                                f"{label}.{dotted} must contain unique, "
                                "nonempty strings."
                            ),
                            path=path,
                        )
                elif not isinstance(value, str):
                    raise StateError(
                        "invalid-asset-manifest",
                        f"{label}.{dotted} must be a string.",
                        path=path,
                    )
        source_mapping = asset.get("source_mapping")
        if source_mapping is not None:
            if not isinstance(source_mapping, dict):
                raise StateError(
                    "invalid-asset-manifest",
                    f"{label}.source_mapping must be an exact selected-source binding object.",
                    path=path,
                )
            source_rank = source_mapping.get("source_rank")
            source_id = source_mapping.get("source_id")
            observation_relative = source_mapping.get("observation")
            evidence_relative = source_mapping.get("evidence_path")
            expected_source_id = f"strong-{source_rank}"
            expected_observation = (
                f".design-dna/references/{expected_source_id}-observation.json"
            )
            string_mapping_fields = (
                "source_id", "observation", "observation_sha256",
                "source_state_id", "source_component_or_behavior",
                "measured_transfer", "evidence_path", "evidence_sha256",
            )
            if (
                type(source_rank) is not int
                or source_rank < 1
                or source_id != expected_source_id
                or observation_relative != expected_observation
                or any(
                    not isinstance(source_mapping.get(field), str)
                    or not source_mapping[field].strip()
                    for field in string_mapping_fields
                )
                or SHA256_HEX.fullmatch(
                    str(source_mapping.get("observation_sha256") or "")
                ) is None
                or SHA256_HEX.fullmatch(
                    str(source_mapping.get("evidence_sha256") or "")
                ) is None
                or len(str(source_mapping.get("measured_transfer") or "").strip()) < 24
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.source_mapping must bind one exact strong-N observation/state/component, "
                        "a measured transfer, and generated evidence bytes."
                    ),
                    path=path,
                )
            observation_path = lexical_absolute(
                project_root / PurePosixPath(str(observation_relative))
            )
            evidence_path = lexical_absolute(
                project_root / PurePosixPath(str(evidence_relative))
            )
            try:
                assert_no_reparse_ancestors(
                    observation_path, stop=project_root
                )
                assert_no_reparse_ancestors(evidence_path, stop=project_root)
            except StateError as exc:
                raise StateError(
                    "invalid-asset-manifest",
                    f"{label}.source_mapping refuses linked/reparse evidence: {exc}",
                    path=path,
                ) from exc
            if (
                not is_within(observation_path, project_root.resolve())
                or not observation_path.is_file()
                or file_sha256(observation_path)[1]
                != source_mapping["observation_sha256"]
                or not is_within(evidence_path, project_root.resolve())
                or not evidence_path.is_file()
                or file_sha256(evidence_path)[1]
                != source_mapping["evidence_sha256"]
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    f"{label}.source_mapping observation/evidence bytes are missing or drifted.",
                    path=path,
                )
            try:
                source_observation = json.loads(
                    observation_path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError) as exc:
                raise StateError(
                    "invalid-asset-manifest",
                    f"{label}.source_mapping observation is unreadable: {exc}",
                    path=path,
                ) from exc
            source_state_id = source_mapping["source_state_id"]
            observer_script = Path(__file__).resolve().parent / "observe_reference.mjs"
            structure_script = Path(__file__).resolve().parent / "structure_probe.mjs"
            browser_script = Path(__file__).resolve().parent / "browser_evidence.mjs"
            resolver_script = Path(__file__).resolve().parent / "playwright_resolver.mjs"
            source_runtime = (
                source_observation.get("runtime_identity")
                if isinstance(source_observation, dict)
                else None
            )
            if (
                not isinstance(source_observation, dict)
                or source_observation.get("tool") != "observe_reference.mjs"
                or source_observation.get("schema_version")
                != REFERENCE_OBSERVATION_SCHEMA
                or source_observation.get("producer_script_sha256")
                != file_sha256(observer_script)[1]
                or source_observation.get("id") != source_id
                or packaged_runtime_record_failures(
                    source_observation, tool="observe_reference.mjs"
                )
                or not isinstance(source_runtime, dict)
                or source_runtime.get("observe_reference.mjs")
                != file_sha256(observer_script)[1]
                or source_runtime.get("structure_probe.mjs")
                != file_sha256(structure_script)[1]
                or source_runtime.get("browser_evidence.mjs")
                != file_sha256(browser_script)[1]
                or source_runtime.get("playwright_resolver.mjs")
                != file_sha256(resolver_script)[1]
                or any(
                    source_state_id
                    not in source_observation.get("states_by_viewport", {}).get(
                        profile, {}
                    )
                    for profile in ("wide", "narrow")
                )
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    f"{label}.source_mapping state is not proven at wide and narrow in the bound source.",
                    path=path,
                )
            evidence_key = (
                PurePosixPath(str(evidence_relative)).as_posix(),
                source_mapping["evidence_sha256"],
            )
            observation_artifacts: set[tuple[str, str]] = set()
            frame_dir = source_observation.get("frame_dir")
            frames = source_observation.get("frames")
            if isinstance(frame_dir, str) and isinstance(frames, list):
                for frame in frames:
                    if (
                        not isinstance(frame, dict)
                        or not isinstance(frame.get("file"), str)
                        or type(frame.get("bytes")) is not int
                        or not isinstance(frame.get("sha256"), str)
                    ):
                        continue
                    relative_frame = (
                        PurePosixPath(".design-dna/references")
                        / PurePosixPath(frame_dir)
                        / PurePosixPath(frame["file"])
                    )
                    generated_frame = lexical_absolute(
                        project_root / relative_frame
                    )
                    try:
                        assert_no_reparse_ancestors(
                            generated_frame, stop=project_root
                        )
                    except StateError:
                        continue
                    if (
                        is_within(generated_frame, project_root.resolve())
                        and generated_frame.is_file()
                        and generated_frame.stat().st_size == frame["bytes"]
                        and file_sha256(generated_frame)[1] == frame["sha256"]
                    ):
                        try:
                            verify_png_artifact(generated_frame)
                        except StateError:
                            continue
                        observation_artifacts.add(
                            (relative_frame.as_posix(), frame["sha256"])
                        )
            if evidence_key not in observation_artifacts:
                raise StateError(
                    "invalid-asset-manifest",
                    f"{label}.source_mapping evidence is not in the bound observation artifact ledger.",
                    path=path,
                )
        migration_review = asset["migration_review"]
        migration_required = migration_review["required"]
        if migration_review["source_schema_version"] not in {"1", "2"}:
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.migration_review.source_schema_version must "
                    "be '1' or '2'."
                ),
                path=path,
            )
        if migration_required:
            if (
                migration_review["source_schema_version"] != "1"
                or not non_placeholder(migration_review["reason"])
                or not migration_review["unresolved_fields"]
                or asset["publication_status"] != "internal-only"
                or asset["factual_status"] not in {"pending", "placeholder"}
                or asset["owner_approval"] != "pending"
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.migration_review required must identify "
                        "schema 1, substantive unresolved fields, "
                        "internal-only publication, pending/placeholder facts, "
                        "and pending owner approval."
                    ),
                    path=path,
                )
        elif (
            migration_review["source_schema_version"] != "2"
            or migration_review["reason"].strip()
            or migration_review["unresolved_fields"]
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.migration_review false requires source schema "
                    "2 with empty reason and unresolved_fields."
                ),
                path=path,
            )

        generated = asset["generated"]
        public_generated_evidence_required = (
            generated["used"]
            and asset["publication_status"] in {"planned-public", "public"}
        )
        if generated["used"]:
            missing_generated_context = [
                field
                for field in (
                    "authorization_basis",
                    "tool_or_model",
                    "prompt_or_digest",
                    "generated_at",
                    "artifact_inspection",
                )
                if not non_placeholder(generated[field])
            ]
            if public_generated_evidence_required:
                for field in (
                    "contact_sheet_path",
                    "contact_sheet_sha256",
                ):
                    if not non_placeholder(generated[field]):
                        missing_generated_context.append(field)
            if (
                public_generated_evidence_required
                and asset["asset_type"] in {"image", "video"}
                and (
                    not generated["responsive_crop_evidence"]
                    or any(
                        not non_placeholder(item)
                        for item in generated["responsive_crop_evidence"]
                    )
                )
            ):
                missing_generated_context.append(
                    "responsive_crop_evidence"
                )
            if missing_generated_context and not migration_required:
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated.used requires "
                        + ", ".join(missing_generated_context)
                        + "."
                    ),
                    path=path,
                )
        elif (
            generated["authorization_basis"].strip()
            or generated["tool_or_model"].strip()
            or generated["prompt_or_digest"].strip()
            or generated["generated_at"].strip()
            or generated["source_inputs"]
            or generated["rejected_outputs"]
            or generated["contact_sheet_path"].strip()
            or generated["contact_sheet_sha256"].strip()
            or generated["artifact_inspection"].strip()
            or generated["responsive_crop_evidence"]
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.generated fields record generation while "
                    "generated.used is false."
                ),
                path=path,
            )
        prompt_or_digest = generated["prompt_or_digest"].strip()
        prompt_digest_valid = bool(
            re.fullmatch(r"sha256:[0-9a-f]{64}", prompt_or_digest)
        )
        if (
            prompt_or_digest.casefold().startswith("sha256:")
            and not prompt_digest_valid
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.generated.prompt_or_digest uses sha256: but "
                    "does not contain 64 lowercase hexadecimal characters."
                ),
                path=path,
            )
        if (
            generated["used"]
            and not migration_required
            and not prompt_digest_valid
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.generated.prompt_or_digest must be a "
                    "sha256: digest with 64 lowercase hexadecimal "
                    "characters; raw prompts do not satisfy the binding."
                ),
                path=path,
            )
        if asset["origin"] == "generated" and not generated["used"]:
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.origin 'generated' requires generated.used true."
                ),
                path=path,
            )
        if (
            non_placeholder(asset["source_path"])
            and asset["source_sha256"].strip()
        ):
            source_binding = (
                asset["source_path"].strip()
                + " plus sha256:"
                + asset["source_sha256"].strip()
            )
            _source, source_failures = bound_artifact(
                source_binding,
                project=project_root,
                record_path=path,
                label=f"{label}.source_path/source_sha256",
            )
            if source_failures:
                raise StateError(
                    "invalid-asset-manifest",
                    source_failures[0],
                    path=path,
                )
        elif asset["source_sha256"].strip():
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.source_sha256 requires source_path.",
                path=path,
            )
        elif non_placeholder(asset["source_path"]) and not migration_required:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.source_path requires source_sha256.",
                path=path,
            )
        if (
            generated["used"]
            and not non_placeholder(asset["source_path"])
            and not migration_required
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.generated.used requires the selected final "
                    "output in source_path with source_sha256."
                ),
                path=path,
            )
        raw_source_url = asset["source_url"]
        source_url = raw_source_url.strip()
        if source_url:
            try:
                parsed_source_url = urlsplit(source_url)
                hostname = parsed_source_url.hostname
                # Accessing port performs validation that urlsplit otherwise
                # defers (for example, ``:not-a-port``).
                _port = parsed_source_url.port
            except ValueError:
                parsed_source_url = None
                hostname = None
            if (
                parsed_source_url is None
                or raw_source_url != source_url
                or any(character.isspace() for character in source_url)
                or "\\" in source_url
                or parsed_source_url.scheme not in {"https", "http"}
                or not hostname
                or parsed_source_url.username is not None
                or parsed_source_url.password is not None
                or parsed_source_url.fragment
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.source_url must be an absolute HTTP(S) URL "
                        "without credentials, whitespace, a backslash, an "
                        "invalid port, or a fragment."
                    ),
                    path=path,
                )
        if generated["used"] and not migration_required:
            try:
                generated_at = datetime.fromisoformat(
                    generated["generated_at"].replace("Z", "+00:00")
                )
                if generated_at.tzinfo is None:
                    raise ValueError("timezone missing")
                if generated_at.astimezone(timezone.utc) > datetime.now(
                    timezone.utc
                ):
                    raise ValueError("future time")
            except ValueError as exc:
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated.generated_at must be a non-future "
                        "ISO date-time with timezone."
                    ),
                    path=path,
                ) from exc
            contact_path = generated["contact_sheet_path"].strip()
            contact_sha256 = generated["contact_sheet_sha256"].strip()
            if bool(contact_path) != bool(contact_sha256):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated contact sheet requires both "
                        "contact_sheet_path and contact_sheet_sha256."
                    ),
                    path=path,
                )
            if contact_path and contact_sha256:
                contact_binding = (
                    contact_path + " plus sha256:" + contact_sha256
                )
                _contact, contact_failures = bound_artifact(
                    contact_binding,
                    project=project_root,
                    record_path=path,
                    label=f"{label}.generated contact sheet",
                )
                if contact_failures:
                    raise StateError(
                        "invalid-asset-manifest",
                        contact_failures[0],
                        path=path,
                    )
            for crop_index, crop_binding in enumerate(
                generated["responsive_crop_evidence"]
            ):
                _crop, crop_failures = bound_artifact(
                    crop_binding,
                    project=project_root,
                    record_path=path,
                    label=(
                        f"{label}.generated.responsive_crop_evidence"
                        f"[{crop_index}]"
                    ),
                )
                if crop_failures:
                    raise StateError(
                        "invalid-asset-manifest",
                        crop_failures[0],
                        path=path,
                    )
            for rejected_index, rejected_output in enumerate(
                generated["rejected_outputs"]
            ):
                if not non_placeholder(rejected_output):
                    raise StateError(
                        "invalid-asset-manifest",
                        (
                            f"{label}.generated.rejected_outputs"
                            f"[{rejected_index}] is empty or instructional."
                        ),
                        path=path,
                    )
            for input_index, source_input in enumerate(
                generated["source_inputs"]
            ):
                if source_input.casefold().startswith("text:"):
                    if not non_placeholder(source_input.split(":", 1)[1]):
                        raise StateError(
                            "invalid-asset-manifest",
                            (
                                f"{label}.generated.source_inputs"
                                f"[{input_index}] has empty text evidence."
                            ),
                            path=path,
                        )
                    continue
                _source_input, input_failures = bound_artifact(
                    source_input,
                    project=project_root,
                    record_path=path,
                    label=(
                        f"{label}.generated.source_inputs[{input_index}]"
                    ),
                )
                if input_failures:
                    raise StateError(
                        "invalid-asset-manifest",
                        input_failures[0],
                        path=path,
                    )
        if (
            not non_placeholder(asset["source_url"])
            and not non_placeholder(asset["source_path"])
            and not (
                generated["used"]
                and generated["source_inputs"]
                and all(
                    non_placeholder(item)
                    for item in generated["source_inputs"]
                )
            )
            and asset["factual_status"] != "placeholder"
            and not migration_required
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label} requires source_url, source_path, or recorded "
                    "generated.source_inputs as provenance evidence."
                ),
                path=path,
            )
        generated_media = asset.get("generated_media_provenance")
        disclosure = asset["concept_disclosure"]
        disclosure_decision = disclosure["decision"]
        if disclosure_decision not in ASSET_DISCLOSURE_DECISIONS:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.concept_disclosure.decision is unsupported.",
                path=path,
            )
        disclosure_reason = disclosure["reason"].strip()
        concept_disclosure_text = disclosure["text"].strip()
        if disclosure_decision == "pending" and (
            disclosure_reason or concept_disclosure_text
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.concept_disclosure pending must not contain "
                    "a reason or public text."
                ),
                path=path,
            )
        if (
            disclosure_decision in {"required", "not-required"}
            and not non_placeholder(disclosure_reason)
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.concept_disclosure {disclosure_decision!r} "
                    "requires a reason."
                ),
                path=path,
            )
        if (
            disclosure_decision == "required"
            and not non_placeholder(concept_disclosure_text)
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.concept_disclosure 'required' requires text."
                ),
                path=path,
            )
        if (
            disclosure_decision == "not-required"
            and concept_disclosure_text
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.concept_disclosure 'not-required' requires "
                    "empty public text."
                ),
                path=path,
            )
        if (
            asset["publication_status"] in {"planned-public", "public"}
            and generated["used"]
            and not isinstance(generated_media, dict)
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label} is planned/public generated media and requires "
                    "generated_media_provenance."
                ),
                path=path,
            )
        if isinstance(generated_media, dict):
            applicability = generated_media["applicability"]
            if applicability not in ASSET_GENERATED_MEDIA_APPLICABILITY:
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance.applicability "
                        "has an unsupported value."
                    ),
                    path=path,
                )
            roles = generated_media["roles"]
            if len(set(roles)) != len(roles) or any(
                role not in ASSET_GENERATED_MEDIA_ROLES for role in roles
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance.roles must contain "
                        "unique provider, deployer, or publisher values."
                    ),
                    path=path,
                )
            if applicability == "applicable":
                if not generated["used"]:
                    raise StateError(
                        "invalid-asset-manifest",
                        (
                            f"{label}.generated_media_provenance.applicability "
                            "'applicable' requires generated.used true."
                        ),
                        path=path,
                    )
                missing_applicability_context = []
                if not generated_media["jurisdiction"].strip():
                    missing_applicability_context.append("jurisdiction")
                if not roles:
                    missing_applicability_context.append("roles")
                if missing_applicability_context:
                    raise StateError(
                        "invalid-asset-manifest",
                        (
                            f"{label}.generated_media_provenance.applicability "
                            "'applicable' requires "
                            + ", ".join(missing_applicability_context)
                            + "."
                        ),
                        path=path,
                    )
            transformation_chain = generated_media["transformation_chain"]
            if any(not step.strip() for step in transformation_chain):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance.transformation_chain "
                        "must not contain empty steps."
                    ),
                    path=path,
                )
            credential_states = (
                (
                    "credential_detected",
                    ASSET_CREDENTIAL_DETECTED_STATUSES,
                ),
                (
                    "credential_validated",
                    ASSET_CREDENTIAL_VALIDATED_STATUSES,
                ),
                (
                    "credential_preserved",
                    ASSET_CREDENTIAL_PRESERVED_STATUSES,
                ),
            )
            for credential_field, allowed in credential_states:
                if generated_media[credential_field] not in allowed:
                    raise StateError(
                        "invalid-asset-manifest",
                        (
                            f"{label}.generated_media_provenance."
                            f"{credential_field} has an unsupported value."
                        ),
                        path=path,
                    )
            disclosure_basis = generated_media[
                "visible_disclosure_basis"
            ].strip()
            provenance_disclosure_text = generated_media[
                "visible_disclosure_text"
            ].strip()
            if (
                provenance_disclosure_text
                and not non_placeholder(disclosure_basis)
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance."
                        "visible_disclosure_text requires "
                        "visible_disclosure_basis."
                    ),
                    path=path,
                )
            if disclosure_decision == "required" and (
                not non_placeholder(disclosure_basis)
                or not non_placeholder(provenance_disclosure_text)
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.concept_disclosure 'required' requires "
                        "generated_media_provenance visible disclosure "
                        "basis and text when that optional record is present."
                    ),
                    path=path,
                )
            if (
                concept_disclosure_text
                and provenance_disclosure_text
                and concept_disclosure_text
                != provenance_disclosure_text
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.concept_disclosure.text and "
                        "generated_media_provenance.visible_disclosure_text "
                        "must match when both are recorded."
                    ),
                    path=path,
                )
            legal_status = generated_media["legal_review_status"]
            if legal_status not in ASSET_GENERATED_MEDIA_LEGAL_STATUSES:
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance."
                        "legal_review_status has an unsupported value."
                    ),
                    path=path,
                )
            if legal_status != "pending":
                missing_legal_context = [
                    field
                    for field in (
                        "legal_review_owner",
                        "legal_review_date",
                        "legal_review_reason",
                    )
                    if not non_placeholder(generated_media[field])
                ]
                if missing_legal_context:
                    raise StateError(
                        "invalid-asset-manifest",
                        (
                            f"{label}.generated_media_provenance."
                            f"legal_review_status {legal_status!r} requires "
                            + ", ".join(missing_legal_context)
                            + "."
                        ),
                        path=path,
                    )
            legal_review_date = generated_media["legal_review_date"]
            if legal_review_date:
                try:
                    parsed_legal_date = date.fromisoformat(legal_review_date)
                    if parsed_legal_date > date.today():
                        raise ValueError("date is in the future")
                except ValueError as exc:
                    raise StateError(
                        "invalid-asset-manifest",
                        (
                            f"{label}.generated_media_provenance."
                            "legal_review_date must be a non-future ISO date "
                            "or empty."
                        ),
                        path=path,
                    ) from exc
            if (
                asset["publication_status"] in {
                    "planned-public",
                    "public",
                }
                and generated["used"]
            ):
                incomplete_public_review = []
                if applicability not in {"applicable", "not-applicable"}:
                    incomplete_public_review.append(
                        "a resolved applicability decision"
                    )
                if not generated_media["jurisdiction"].strip():
                    incomplete_public_review.append("jurisdiction")
                if not transformation_chain:
                    incomplete_public_review.append("transformation_chain")
                for credential_field, _ in credential_states:
                    if generated_media[credential_field] == "pending":
                        incomplete_public_review.append(credential_field)
                if legal_status not in {"approved", "not-required"}:
                    incomplete_public_review.append("legal_review_status")
                if incomplete_public_review:
                    raise StateError(
                        "invalid-asset-manifest",
                        (
                            f"{label} planned/public generated media requires "
                            "completed provenance decisions for "
                            + ", ".join(incomplete_public_review)
                            + "."
                        ),
                        path=path,
                    )
            detected = generated_media["credential_detected"]
            validated = generated_media["credential_validated"]
            preserved = generated_media["credential_preserved"]
            if validated == "validated" and detected != "detected":
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance "
                        "credential_validated 'validated' requires "
                        "credential_detected 'detected'."
                    ),
                    path=path,
                )
            if validated in {"invalid", "unverifiable"} and detected != "detected":
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance "
                        f"credential_validated {validated!r} requires "
                        "credential_detected 'detected'."
                    ),
                    path=path,
                )
            if (
                detected == "detected"
                and validated == "not-applicable"
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance detected "
                        "credentials require a validation outcome rather "
                        "than 'not-applicable'."
                    ),
                    path=path,
                )
            if preserved == "preserved" and (
                detected != "detected" or validated != "validated"
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance "
                        "credential_preserved 'preserved' requires detected "
                        "and validated credentials."
                    ),
                    path=path,
                )
            if detected == "not-detected" and (
                validated != "not-applicable"
                or preserved != "not-applicable"
            ):
                raise StateError(
                    "invalid-asset-manifest",
                    (
                        f"{label}.generated_media_provenance credentials "
                        "marked not-detected require validation and "
                        "preservation to be not-applicable."
                    ),
                    path=path,
                )
        if type(asset["attribution_required"]) is not bool:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.attribution_required must be a boolean.",
                path=path,
            )
        if asset["attribution_required"] and not asset["attribution_text"].strip():
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.attribution_required requires "
                    "attribution_text."
                ),
                path=path,
            )
        if asset["origin"] == "licensed" and not asset["license_or_terms"].strip():
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.origin 'licensed' requires license_or_terms."
                ),
                path=path,
            )
        usage_locations = asset["usage_locations"]
        if not isinstance(usage_locations, list) or not all(
            isinstance(item, str) for item in usage_locations
        ):
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.usage_locations must be a list of strings.",
                path=path,
            )
        if (
            not usage_locations
            or any(
                not non_placeholder(item)
                for item in usage_locations
            )
            or len(usage_locations) != len(set(usage_locations))
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.usage_locations must contain at least one "
                    "unique, nonempty project location."
                ),
                path=path,
            )
        accessibility = asset["accessibility"]
        treatment = accessibility["treatment"]
        if treatment not in ASSET_ACCESSIBILITY_TREATMENTS:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.accessibility.treatment has an unsupported value.",
                path=path,
            )
        alt_text = accessibility["alt_text"].strip()
        transcript = accessibility["caption_or_transcript"].strip()
        if treatment in {"informative", "functional"} and not alt_text:
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.accessibility.treatment {treatment!r} "
                    "requires alt_text."
                ),
                path=path,
            )
        if treatment == "complex" and (not alt_text or not transcript):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.accessibility.treatment 'complex' requires "
                    "alt_text and caption_or_transcript."
                ),
                path=path,
            )
        if treatment == "decorative" and alt_text:
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.accessibility.treatment 'decorative' requires "
                    "empty alt_text."
                ),
                path=path,
            )
        replacement = asset["replacement"]
        replacement_status = replacement["status"]
        if replacement_status not in ASSET_REPLACEMENT_STATUSES:
            raise StateError(
                "invalid-asset-manifest",
                f"{label}.replacement.status has an unsupported value.",
                path=path,
            )
        if replacement_status in {"required", "scheduled"} and (
            not replacement["owner"].strip()
            or not replacement["due_date"].strip()
        ):
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.replacement.status {replacement_status!r} "
                    "requires owner and due_date."
                ),
                path=path,
            )
        if replacement_status == "replaced" and not replacement["owner"].strip():
            raise StateError(
                "invalid-asset-manifest",
                (
                    f"{label}.replacement.status 'replaced' requires owner."
                ),
                path=path,
            )
        due_date = asset["replacement"]["due_date"]
        if due_date:
            try:
                date.fromisoformat(due_date)
            except ValueError as exc:
                raise StateError(
                    "invalid-asset-manifest",
                    f"{label}.replacement.due_date must be an ISO date or empty.",
                    path=path,
                ) from exc
    warnings: list[str] = []
    expected = f"design-dna {current_version}"
    if created_with != expected:
        warnings.append(
            f"assets.yml was created with {created_with}; current package is {expected}."
        )
    return warnings


def asset_readiness_failures(path: Path) -> list[str]:
    """Return release-readiness gaps after structural validation has passed."""

    payload = parse_strict_yaml_subset(
        path.read_text(encoding="utf-8"),
        path=path,
    )
    assets = payload["assets"]
    if not assets:
        return [
            "Listed asset record contains no assets; add each material "
            "asset or remove the asset-led readiness claim."
        ]
    failures: list[str] = []
    for index, asset in enumerate(assets):
        asset_id = asset["id"]
        label = f"{asset_id} (assets[{index}])"
        if asset["publication_status"] == "prohibited":
            failures.append(
                f"{label} is prohibited and cannot support readiness."
            )
        if asset["migration_review"]["required"]:
            failures.append(
                f"{label} still requires schema-1 migration review: "
                + ", ".join(asset["migration_review"]["unresolved_fields"])
                + "."
            )
        if asset["factual_status"] not in {"approved", "concept"}:
            failures.append(
                f"{label} factual_status must be approved or concept."
            )
        if asset["privacy_review"] not in {"approved", "not-required"}:
            failures.append(
                f"{label} privacy_review must be approved or not-required."
            )
        if asset["owner_approval"] != "approved":
            failures.append(
                f"{label} owner_approval must be approved."
            )
        if asset["accessibility"]["treatment"] == "pending":
            failures.append(
                f"{label} accessibility treatment remains pending."
            )
        asset_type = asset["asset_type"]
        delivery = asset["delivery"]
        missing_delivery: list[str] = []
        if asset_type in {"image", "video"}:
            if not non_placeholder(delivery["source_dimensions"]):
                missing_delivery.append("source dimensions")
            if not delivery["output_dimensions"]:
                missing_delivery.append("output dimensions")
            if not delivery["formats"]:
                missing_delivery.append("formats")
            if not non_placeholder(delivery["responsive_behavior"]):
                missing_delivery.append("responsive/fallback behavior")
            if not delivery["intrinsic_dimensions_reserved"]:
                missing_delivery.append("reserved intrinsic dimensions")
        elif asset_type in {"audio", "document", "other"}:
            if not non_placeholder(delivery["source_dimensions"]):
                missing_delivery.append("type-relevant source characteristics")
            if not delivery["formats"]:
                missing_delivery.append("formats")
            if not non_placeholder(delivery["responsive_behavior"]):
                missing_delivery.append("loading/fallback behavior")
        elif asset_type in {"map", "embed"}:
            if not non_placeholder(delivery["responsive_behavior"]):
                missing_delivery.append(
                    "responsive, privacy, and failure fallback behavior"
                )
        elif asset_type == "font":
            if not non_placeholder(asset["license_or_terms"]):
                missing_delivery.append("license terms")
            if not non_placeholder(asset["source_path"]):
                missing_delivery.append("bound local font binary")
            if not non_placeholder(delivery["source_dimensions"]):
                missing_delivery.append("axes/subset characteristics")
            if not delivery["formats"]:
                missing_delivery.append("formats")
            if not non_placeholder(delivery["responsive_behavior"]):
                missing_delivery.append("loading/fallback behavior")
        if missing_delivery:
            failures.append(
                f"{label} {asset_type} readiness requires "
                + ", ".join(missing_delivery)
                + "."
            )
        if asset["replacement"]["status"] not in {
            "not-needed",
            "replaced",
        }:
            failures.append(
                f"{label} replacement status must be not-needed or replaced."
            )
        if (
            asset["publication_status"] in {"planned-public", "public"}
            and not non_placeholder(asset["license_or_terms"])
        ):
            failures.append(
                f"{label} planned/public use requires recorded rights or "
                "license_or_terms."
            )
        if (
            asset["publication_status"] in {"planned-public", "public"}
            and asset["factual_status"] == "concept"
            and asset["concept_disclosure"]["decision"] == "pending"
        ):
            failures.append(
                f"{label} public concept media requires an attributable "
                "required/not-required disclosure decision."
            )
        if (
            asset["publication_status"] in {"planned-public", "public"}
            and asset["generated"]["used"]
            and asset["factual_status"] != "concept"
        ):
            failures.append(
                f"{label} public generated media must use factual_status "
                "concept rather than documentary approval."
            )
    return failures


def split_frontmatter_text(
    text: str,
    *,
    path: Path,
) -> tuple[dict[str, str], str, str]:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise StateError(
            "invalid-frontmatter",
            "Markdown must begin with frontmatter.",
            path=path,
        )
    end = normalized.find("\n---\n", 4)
    if end < 0:
        raise StateError(
            "invalid-frontmatter",
            "Frontmatter is not closed.",
            path=path,
        )
    frontmatter = normalized[4:end]
    body = normalized[end + len("\n---\n"):]
    return parse_flat_yaml(frontmatter, path=path), frontmatter, body


def read_frontmatter_document(path: Path) -> tuple[dict[str, str], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise StateError("state-read-failed", str(exc), path=path) from exc
    metadata, _, body = split_frontmatter_text(text, path=path)
    return metadata, body


def parse_frontmatter(path: Path) -> dict[str, str]:
    metadata, _ = read_frontmatter_document(path)
    return metadata


def yaml_quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def update_frontmatter_text(
    text: str,
    *,
    path: Path,
    updates: dict[str, str],
    removals: set[str] | None = None,
) -> str:
    _, frontmatter, body = split_frontmatter_text(text, path=path)
    removals = removals or set()
    emitted: set[str] = set()
    lines: list[str] = []
    for number, line in enumerate(frontmatter.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            lines.append(line)
            continue
        if line[:1].isspace() or ":" not in line:
            raise StateError(
                "invalid-frontmatter",
                f"Unsupported frontmatter at line {number}.",
                path=path,
            )
        key = line.split(":", 1)[0]
        if key in removals:
            continue
        if key in updates:
            lines.append(f"{key}: {yaml_quoted(updates[key])}")
            emitted.add(key)
        else:
            lines.append(line)
    for key, value in updates.items():
        if key not in emitted:
            lines.append(f"{key}: {yaml_quoted(value)}")
    return "---\n" + "\n".join(lines) + "\n---\n" + body


def write_frontmatter_update(
    path: Path,
    *,
    updates: dict[str, str],
    removals: set[str] | None = None,
) -> None:
    try:
        text = path.read_text(encoding="utf-8")
        rendered = update_frontmatter_text(
            text,
            path=path,
            updates=updates,
            removals=removals,
        )
        path.write_text(rendered, encoding="utf-8", newline="\n")
    except StateError:
        raise
    except (OSError, UnicodeError) as exc:
        raise StateError(
            "record-metadata-update-failed",
            str(exc),
            path=path,
        ) from exc


def body_sha256(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def markdown_sections(body: str) -> dict[str, str]:
    headings = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", body))
    result: dict[str, str] = {}
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        result[match.group(1).strip()] = body[match.end():end].strip()
    return result


def markdown_label_value(body: str, label: str) -> str | None:
    lines = body.splitlines()
    expected = label.casefold()
    for index, line in enumerate(lines):
        match = re.match(r"^\s*-\s+(.+)$", line)
        if not match:
            continue
        content = match.group(1).strip()
        if not content.casefold().startswith(expected):
            continue
        boundary = content[len(label):len(label) + 1]
        if boundary and boundary not in {":", ",", " ", "("}:
            continue
        cursor = index + 1
        while ":" not in content and cursor < len(lines):
            continuation = lines[cursor]
            if re.match(r"^\s*(?:-\s+|#{1,6}\s+|\|)", continuation):
                break
            if not continuation.strip():
                break
            content += " " + continuation.strip()
            cursor += 1
        if ":" not in content:
            return None
        _prompt, value = content.split(":", 1)
        return value.strip()
    return None


def markdown_table_rows(section: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [cell.strip() for cell in line[1:-1].split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    if rows:
        rows = rows[1:]
    return [row for row in rows if any(cell for cell in row)]


def markdown_first_table(
    section: str,
) -> tuple[tuple[str, ...], list[list[str]]]:
    lines = section.splitlines()
    for index in range(len(lines) - 1):
        header_line = lines[index].strip()
        separator_line = lines[index + 1].strip()
        if not (
            header_line.startswith("|")
            and header_line.endswith("|")
            and separator_line.startswith("|")
            and separator_line.endswith("|")
        ):
            continue
        headers = tuple(
            cell.strip() for cell in header_line[1:-1].split("|")
        )
        separators = [
            cell.strip() for cell in separator_line[1:-1].split("|")
        ]
        if (
            len(headers) != len(separators)
            or not all(
                re.fullmatch(r":?-{3,}:?", cell)
                for cell in separators
            )
        ):
            continue
        rows: list[list[str]] = []
        for raw_line in lines[index + 2:]:
            line = raw_line.strip()
            if not line.startswith("|") or not line.endswith("|"):
                break
            rows.append(
                [cell.strip() for cell in line[1:-1].split("|")]
            )
        return headers, rows
    return (), []


def non_placeholder(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().casefold()
    if normalized in GENERIC_METADATA_VALUES:
        return False
    if normalized == "not-recorded" or normalized.startswith(
        ("not-recorded (", "not recorded (")
    ):
        return False
    if normalized in {
        "yes / no",
        "proceed, revise, compare again, or reject",
        "concept, demo, staging, or production",
    }:
        return False
    return bool(normalized)


REFERENCE_SOURCE_REQUIRED_KEYS = {
    "id",
    "name",
    "url",
    "status",
    "access",
    "retrieval",
    "scope",
    "notes",
    "curation",
    "curation_note",
}
REFERENCE_SOURCE_STATUSES = {"active", "inactive"}
REFERENCE_SOURCE_RETRIEVAL = {"fetch", "browser", "none"}
ACTIVE_REFERENCE_SOURCE_RETRIEVAL = {"fetch", "browser"}
ACTIVE_REFERENCE_SOURCE_ACCESS = {"public", "public-limited"}
REFERENCE_ENTRY_ACCESS = {
    "public-live",
    "public-gallery-entry",
    "authorized-account",
}
# The reference count is a floor with a reason, not a quota: enough
# independent sources that no single site becomes the template.
REFERENCE_MINIMUM_STRONG = 6
REFERENCE_MINIMUM_CANDIDATES = 8
REFERENCE_MINIMUM_REJECTED_CANDIDATES = 2
REFERENCE_MINIMUM_SOURCES = 3
REFERENCE_MINIMUM_NEGATIVE = 3
REFERENCE_MINIMUM_SELECTED = 4
REFERENCE_MINIMUM_SELECTED_SOURCES = 2
REFERENCE_CAPTURE_PREFIX = ".design-dna/references/"
# Two held scroll positions is the floor at which a producer can tell an
# animated arrival from a static one; one hold proves nothing.
REFERENCE_OBSERVATION_MIN_HOLDS = 2
REFERENCE_OBSERVATION_SCHEMA = 5
# A site earns a motion row on its own numbers: at least three distinct
# mechanisms, with scroll choreography active on at least half of its depth.
# Below that it is a thin site, and a thin reference teaches a thin design.
REFERENCE_MECHANISM_MIN_DISTINCT = 3
REFERENCE_MECHANISM_MIN_COVERAGE = 0.5
# Most of the selected set has to do something; a build cannot take its
# behavior from references that have none.
REFERENCE_MINIMUM_SELECTED_MOTION = 0
# A signature is what a site does. A cell with none of these is describing a
# subject, a palette or a mood, which is the sidewalk and not the falls.
REFERENCE_SIGNATURE_VERBS = re.compile(
    r"\b(hold|holds|held|pin|pins|pinned|stick|sticks|stuck|travel|travels|"
    r"swap|swaps|crossfade|crossfades|fade|fades|reveal|reveals|slide|slides|"
    r"scroll|scrolls|parallax|follow|follows|track|tracks|morph|morphs|"
    r"expand|expands|grow|grows|shrink|shrinks|snap|snaps|animate|animates|"
    r"transition|transitions|wipe|wipes|mask|masks|split|splits|assemble|"
    r"assembles|write|writes|light|lights|move|moves|moving|enter|enters|"
    r"arrive|arrives|drift|drifts|plays|loop|loops|respond|responds|react|reacts)\b",
    re.IGNORECASE,
)
REFERENCE_STATIC_SIGNATURE_TERMS = re.compile(
    r"\b(composition|typograph|grid|photograph|image|object|media|color|colour|"
    r"contrast|hierarchy|alignment|crop|frame|density|negative space|scale|"
    r"edge|corner|column|row|field|ground|surface)\w*\b",
    re.IGNORECASE,
)
REFERENCE_STATIC_RELATIONSHIP_TERMS = re.compile(
    r"\b(align|aligned|against|beside|between|spans?|across|over|under|behind|"
    r"inside|outside|fills?|frames?|anchors?|balances?|offset|overlap|grid|"
    r"column|row|edge|corner|hierarchy|negative space)\w*\b",
    re.IGNORECASE,
)
REFERENCE_DOSSIER_COMPONENT_HEADERS = (
    "Component",
    "Source rank or owner approval",
    "Frame that shows it",
    "Structure taken",
    "Recorded values reproduced",
    "Where it is used",
)
# A source line is prose, and prose is free. A producer wrote
# `footer <- index-space.org: a plain block, no rules` for a footer it had
# never opened, because the table demanded a source and it could supply the
# shape of one from memory. The frame column is the fix: name the capture that
# shows this part, and the validator opens it. A part nobody looked at cannot
# be cited, because the picture of it does not exist.
REFERENCE_DOSSIER_COMPONENT_HEADERS_LEGACY = REFERENCE_DOSSIER_COMPONENT_HEADERS
REFERENCE_DOSSIER_COMPONENT_HEADERS = (
    "Component",
    "Source rank",
    "Frame that shows it",
    "Structure taken",
    "Recorded values reproduced",
    "Where it is used",
)
REFERENCE_DOSSIER_COMPONENT_HEADER_VARIANTS = (
    REFERENCE_DOSSIER_COMPONENT_HEADERS,
    REFERENCE_DOSSIER_COMPONENT_HEADERS_LEGACY,
)
# The owner's standing order, 2026-09-03, after a "quick test" build shipped
# the producer's nav, typefaces, palette, cards and accordion: "There is
# absolutely no using your design. You must only use the designs from the
# websites you are copying from. And this includes designs, layouts, fonts,
# and everything else." There is no owner-approved path for a producer's own
# part any more. The phrase is refused wherever it appears in the table.
PRODUCER_DESIGN_ORDER = (
    "The owner's standing order (2026-09-03) forbids the producer's own design "
    "in every part: \"There is absolutely no using your design. You must only "
    "use the designs from the websites you are copying from. And this includes "
    "designs, layouts, fonts, and everything else.\" Observe a reference that "
    "shows this part and cite its frame, or cut the part."
)
PRODUCER_DESIGN_MARKER = re.compile(r"owner[- ]approved", re.IGNORECASE)
# A producer cannot build from a picture. Given a screenshot it reports what a
# screenshot carries, guesses the rest, and believes it is copying. Every
# number a row claims has to be one the reference actually computes.
REFERENCE_STYLE_TOOL = "extract_reference_styles.mjs"
REFERENCE_VALUE_MINIMUM = 3
REFERENCE_VALUE_MATCH_FLOOR = 0.6
# Quality is the first filter and register the second. A bulk submission feed
# filtered by register produces register-matched mediocrity: six faithful
# copies of forgettable sites make a forgettable site.
REFERENCE_CURATION_ALLOWED = ("award", "curated")
# The build is a combination of what the references do. It is never a new idea
# the producer had. A field that asked for one got one, and the owner had to
# say so.
COMBINATION_INVENTION_WORDS = re.compile(
    r"\b(invent|invented|invention|our own|my own|producer's own|new idea|"
    r"came up with|dreamed up|original(?:ly)? (?:idea|concept)|added by us|"
    r"beyond every reference|none of them attempt|no reference does)\b",
    re.IGNORECASE,
)
COMBINATION_SOURCE_PATTERN = re.compile(r"\bstrong-\d+\b|\brank\s*\d+\b", re.IGNORECASE)
# Every real site has more than one page. A producer that only ever observes
# home pages can only ever copy a home page, and will design every inner page
# itself while believing it is still copying.
REFERENCE_INNER_PAGE_MINIMUM = 2
# A property is a font size. A structure is where the thing sits, what it is
# next to, and what fills the screen. The producer that shipped its own layout
# with borrowed font sizes could satisfy a property column every time, so the
# structure column has to carry a word about arrangement.
COMPONENT_STRUCTURE_WORDS = re.compile(
    r"\b(full[- ]?bleed|edge|edges|corner|corners|column|columns|grid|split|half|"
    r"third|quarter|centre|center|centred|centered|left|right|top|bottom|"
    r"stack|stacked|beside|above|below|behind|over|under|inset|margin|"
    r"span|spans|fills|occupies|holds|pinned|sticky|offset|overlap|"
    r"row|rows|band|panel|frame|stage|first screen|viewport)\b",
    re.IGNORECASE,
)
# The parts of a page that decide what it looks like. Every one needs a
# source; a build whose layout, first screen and typefaces are the producer's
# own is the producer's design however many references it researched.
REFERENCE_DOSSIER_REQUIRED_COMPONENTS = (
    "first screen",
    "layout grid",
    "display typeface",
    "text typeface",
    "color behavior",
    "section rhythm",
    "navigation",
    "buttons",
    "rows or lists",
    "footer",
    "scroll behavior",
    "hover behavior",
)
# A typeface is taken from a reference or it is the producer's taste. Taste is
# how nine builds got Newsreader and Instrument Sans when not one reference
# used anything like them.
TYPEFACE_COMPONENTS = ("display typeface", "text typeface")
# Six references were researched, watched, and measured, every gate passed, and
# two of them reached the build as a background colour and a set of control
# dimensions. The owner's words: "you still took the crack in the sidewalk
# instead of the waterfall." A source line cannot tell which part of a
# reference arrived, so the transfer table asks the one question a producer
# cannot answer from the numbers: cut this reference out, and what does a
# stranger notice is gone?
# 9.0.0: the sequence read. A reference is watched as a RECORDING cut into
# sheets, and the dossier is not valid until every sheet has a line written
# about it. Three generations of instrument let a producer satisfy "watch the
# site" without looking: stills called a sequence, computed styles called a
# copy, and finally a harness whose mechanism numbers were read while one rest
# frame out of forty-one was opened. The owner's own sixty-second recording,
# walked at ten frames a second, held nineteen behaviours the build had never
# seen. A script cannot make a producer understand what it sees; it can make
# sure the producer saw all of it.
REFERENCE_SEQUENCE_SECTION = "Sequence reads"
REFERENCE_RECORDING_TOOL = "record_reference.mjs"
# Current recordings bind the exact packaged producer and complete discovery
# coverage. Older sheet/event manifests do not prove either and cannot close a
# new no-producer-design dossier.
REFERENCE_RECORDING_SCHEMAS = (4,)
REFERENCE_RECORDING_MINIMUM_EVENTS = 12
REFERENCE_EVENT_LINE = re.compile(
    r"^-\s+(wide|narrow)/e(\d{4})\s*\(", re.MULTILINE
)
REFERENCE_EVENT_ID = re.compile(r"\b(wide|narrow)/e(\d{4})\b")
REFERENCE_EVENT_FRAME = re.compile(
    r"strong-\d+-(?:wide|narrow)-events/e\d{4}[^\s|]*\.png\b"
)
REFERENCE_RECORDING_MINIMUM_SHEETS = 20
REFERENCE_RECORDING_MINIMUM_SECONDS = 90
REFERENCE_RECORDING_MINIMUM_FPS = 15
REFERENCE_SEQUENCE_LINE_MINIMUM = 40
REFERENCE_SEQUENCE_LINE = re.compile(r"^-\s+s(\d{3})\s*\(", re.MULTILINE)
REFERENCE_SEQUENCE_STATIC = re.compile(
    r"\b(static|nothing (?:changes|moves|happens)|no change|unchanged|holds)\b",
    re.IGNORECASE,
)
REFERENCE_SEQUENCE_STATIC_CEILING = 0.75
REFERENCE_SEQUENCE_INVENTORY_MINIMUM = 8
REFERENCE_SEQUENCE_SHEET_ID = re.compile(r"\bs(\d{3})\b")
REFERENCE_SHEET_FRAME = re.compile(r"-sheets/s\d{3}\.png\b")
# a rest frame cannot show these; their source line has to point at a sheet
REFERENCE_BEHAVIOUR_COMPONENTS = (
    "first screen", "navigation", "buttons", "scroll behavior", "hover behavior",
)

REFERENCE_DOSSIER_TRANSFER_HEADERS = (
    "Rank",
    "Signature, copied from the strong row",
    "The build part that carries it",
    "Recorded proof",
    "What a stranger would lose if this reference were cut",
)
REFERENCE_INTERACTION_CENSUS_HEADERS = (
    "Target ID and page/route",
    "Target kind and repeat/equivalence class",
    "Input tested",
    "Before state",
    "After/settled state and changed property or behavior",
    "Wide/narrow evidence frames or event artifacts with SHA-256",
    "Disposition",
)
# The loss has to be a thing, not a property of a thing. "The warm ground" and
# "the 12px corners" are what a producer writes when nothing would actually go.
REFERENCE_TRANSFER_SUBSTANCE = re.compile(
    r"\b(composition|arrangement|layout|grid|stack|stacked|split|band|bands|"
    r"panel|panels|rail|plate|sequence|rhythm|screen|screens|edge|edges|"
    r"full[- ]?bleed|overlap|overlaps|overlapping|break|breaks|breaking|crop|"
    r"frame|framing|index|drawer|drawers|tab|tabs|column|columns|row|rows|"
    r"choreography|entrance|opening|closing|route|routes|page|pages|structure|"
    r"order|hierarchy|"
    r"hold|holds|held|pin|pins|pinned|travel|travels|swap|swaps|reveal|reveals|"
    r"slide|slides|scroll|scrolls|parallax|follow|follows|drift|drifts|"
    r"transition|transitions|change|changes|move|moves|arrive|arrives|"
    r"settle|settles|rise|rises|fill|fills)\b",
    re.IGNORECASE,
)
REFERENCE_TRANSFER_SIGNATURE_MINIMUM = 40

REFERENCE_DOSSIER_STRONG_HEADERS = (
    "Rank",
    "Reference title or visible entry",
    "Public URL or gallery-entry URL",
    "Discovery source and accolade",
    "Retrieval date",
    "Access status",
    "Wide capture path and SHA-256",
    "Narrow capture path and SHA-256",
    "Pages, progression, and states studied",
    "Observed evidence",
    "Measured styles",
    "Signature (motion or static; what a stranger would name)",
    "Brief relevance",
    "Design to copy",
    "Rights boundary",
)
REFERENCE_DOSSIER_CANDIDATE_HEADERS = (
    "Candidate title and URL",
    "Registry source, exact discovery path/filter, retrieval date, and fresh/reuse basis",
    "Wide capture path and SHA-256",
    "Narrow capture path and SHA-256",
    "Complete live pages, progression, and states studied",
    "Brief-fit gate: organization/audience/task criteria passed/failed and bound evidence",
    "Quality/execution gate: criteria passed/failed and bound capture/sequence evidence",
    "Conjunctive disposition and concrete rejection reason",
)
REFERENCE_DOSSIER_NEGATIVE_HEADERS = (
    "Reference title or visible entry",
    "Public URL or gallery-entry URL",
    "Discovery source and accolade",
    "Retrieval date",
    "Access status",
    "Capture path and SHA-256",
    "Observed mismatch or weak relationship",
    "What this project must avoid",
)
REFERENCE_DOSSIER_SYNTHESIS_HEADERS = (
    "Selected rank(s)",
    "Design copied and destination",
    "Project-specific adaptation",
    "Boundary or verification",
)

VISIBLE_DECISION_SOURCE_SCHEMA = 1
VISIBLE_DECISION_SOURCE_RECORD = "design-dna-visible-decision-source-manifest"
VISIBLE_DECISION_CATEGORIES = (
    "layout", "typeface", "color", "control", "transition",
    "content-pattern", "effect",
)


def visible_decision_source_manifest_failures(
    payload: object,
    *,
    project: Path,
    route_manifest: dict[str, object],
    route_manifest_path: Path,
    proof_identity: str,
) -> list[str]:
    """Prove planned visible decisions were sourced before broad build work."""

    failures: list[str] = []
    expected_top = {
        "schema_version", "record_type", "created_at", "proof_build_id",
        "route_manifest", "source_observations", "planned_decision_ids",
        "decisions", "completeness",
    }
    if not isinstance(payload, dict) or set(payload) != expected_top:
        return ["Visible decision source manifest has an unsupported shape."]
    if (
        payload.get("schema_version") != VISIBLE_DECISION_SOURCE_SCHEMA
        or payload.get("record_type") != VISIBLE_DECISION_SOURCE_RECORD
    ):
        failures.append("Visible decision source manifest has an unsupported identity.")
    try:
        created = datetime.fromisoformat(
            str(payload.get("created_at") or "").replace("Z", "+00:00")
        )
    except ValueError:
        created = None
    if created is None or created.tzinfo is None:
        failures.append("Visible decision source manifest needs a timezone-bound created_at.")
    proof_fields = semicolon_fields(proof_identity)
    proof_build_id = proof_fields.get("build_id", "")
    if (
        set(proof_fields) != {"build_id", "route_key"}
        or payload.get("proof_build_id") != proof_build_id
        or not isinstance(proof_build_id, str)
        or ROUTE_MANIFEST_ID.fullmatch(proof_build_id) is None
    ):
        failures.append("Visible decision source manifest does not bind the exact first-screen proof build ID.")
    manifest_binding = payload.get("route_manifest")
    if (
        not isinstance(manifest_binding, dict)
        or set(manifest_binding) != {"manifest_id", "path", "sha256"}
        or manifest_binding.get("manifest_id") != route_manifest.get("manifest_id")
        or manifest_binding.get("path") != ".design-dna/route-manifest.json"
        or manifest_binding.get("sha256") != file_sha256(route_manifest_path)[1]
    ):
        failures.append("Visible decision source manifest does not bind the exact route manifest bytes.")
    routes = {
        str(route.get("key")): route
        for route in route_manifest.get("routes", [])
        if isinstance(route, dict)
    }
    route_states = {
        key: {
            str(state.get("id")) for state in route.get("states", [])
            if isinstance(state, dict)
        }
        for key, route in routes.items()
    }
    source_rows = payload.get("source_observations")
    source_ids: set[str] = set()
    allowed_source_evidence: dict[str, set[tuple[str, str]]] = {}
    if not isinstance(source_rows, list) or not source_rows:
        failures.append("Visible decision source manifest has no source observations.")
        source_rows = []
    for index, row in enumerate(source_rows, start=1):
        if not isinstance(row, dict) or set(row) != {"id", "path", "sha256"}:
            failures.append(f"Visible decision source observation {index} has an unsupported shape.")
            continue
        source_id = row.get("id")
        relative = row.get("path")
        expected_relative = f".design-dna/references/{source_id}-observation.json"
        if (
            not isinstance(source_id, str)
            or ROUTE_REFERENCE_ID.fullmatch(source_id) is None
            or source_id in source_ids
            or relative != expected_relative
        ):
            failures.append(f"Visible decision source observation {index} has invalid identity/path.")
            continue
        source_ids.add(source_id)
        artifact = (project / PurePosixPath(relative)).resolve()
        if (
            not is_within(artifact, project.resolve())
            or not artifact.is_file()
            or not isinstance(row.get("sha256"), str)
            or file_sha256(artifact)[1] != row["sha256"]
        ):
            failures.append(f"Visible decision source observation {index} bytes are missing or drifted.")
        else:
            # The observation record proves producer identity, but a design
            # decision must cite one of the immutable artifacts it records.
            # Treating the JSON envelope itself as visual/behavioral proof
            # would let a hand-authored record stand in for captured source
            # pixels or state evidence.
            allowed: set[tuple[str, str]] = set()
            try:
                observed_payload = json.loads(artifact.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                failures.append(f"Visible decision source observation {index} is unreadable.")
            else:
                identity = packaged_runtime_record_failures(
                    observed_payload, tool="observe_reference.mjs"
                )
                failures.extend(
                    f"Visible decision source observation {index}: {problem}"
                    for problem in identity
                )

                # Only the observer's canonical frame inventory can supply
                # decision proof. Do not recursively trust an arbitrary
                # ``file``/``sha256`` pair inserted into otherwise plausible
                # JSON; it must be a ledgered captured PNG with exact bytes.
                frame_dir = observed_payload.get("frame_dir")
                frames = observed_payload.get("frames")
                if not isinstance(frame_dir, str) or not isinstance(frames, list):
                    failures.append(
                        f"Visible decision source observation {index} has no canonical frame inventory."
                    )
                else:
                    for frame in frames:
                        if (
                            not isinstance(frame, dict)
                            or not isinstance(frame.get("file"), str)
                            or not frame["file"].casefold().endswith(".png")
                            or type(frame.get("bytes")) is not int
                            or frame["bytes"] < 1
                            or not isinstance(frame.get("sha256"), str)
                            or SHA256_HEX.fullmatch(frame["sha256"]) is None
                        ):
                            continue
                        relative_frame = (
                            PurePosixPath(frame_dir) / PurePosixPath(frame["file"])
                        )
                        generated = (artifact.parent / relative_frame).resolve()
                        if (
                            not relative_frame.is_absolute()
                            and ".." not in relative_frame.parts
                            and is_within(generated, artifact.parent.resolve())
                            and generated.is_file()
                            and generated.stat().st_size == frame["bytes"]
                            and file_sha256(generated)[1] == frame["sha256"]
                        ):
                            try:
                                verify_png_artifact(generated)
                            except StateError:
                                continue
                            allowed.add((
                                generated.relative_to(project).as_posix(),
                                frame["sha256"],
                            ))
            allowed_source_evidence[str(source_id)] = allowed
    planned = payload.get("planned_decision_ids")
    decisions = payload.get("decisions")
    if (
        not isinstance(planned, list)
        or len(planned) != len(set(planned))
        or not isinstance(decisions, list)
        or not decisions
    ):
        failures.append("Visible decision source manifest needs unique planned decisions and decision rows.")
        planned = []
        decisions = []
    observed_ids: set[str] = set()
    observed_categories: set[str] = set()
    for index, decision in enumerate(decisions, start=1):
        label = f"Visible decision source row {index}"
        if not isinstance(decision, dict) or set(decision) != {
            "decision_id", "category", "planned_surface", "route_keys",
            "state_ids", "source_reference_id", "source_component_or_behavior",
            "evidence", "disposition",
        }:
            failures.append(f"{label} has an unsupported shape.")
            continue
        decision_id = decision.get("decision_id")
        category = decision.get("category")
        if (
            not isinstance(decision_id, str)
            or re.fullmatch(r"[a-z][a-z0-9-]{2,63}", decision_id) is None
            or decision_id in observed_ids
        ):
            failures.append(f"{label} needs a unique stable decision ID.")
        else:
            observed_ids.add(decision_id)
        if category not in VISIBLE_DECISION_CATEGORIES:
            failures.append(f"{label} has an unsupported visible-decision category.")
        else:
            observed_categories.add(str(category))
        if (
            not isinstance(decision.get("planned_surface"), str)
            or len(decision["planned_surface"].strip()) < 24
            or not isinstance(decision.get("source_component_or_behavior"), str)
            or len(decision["source_component_or_behavior"].strip()) < 24
            or decision.get("disposition") != "required"
        ):
            failures.append(f"{label} does not concretely bind the planned surface and source behavior.")
        decision_routes = decision.get("route_keys")
        decision_states = decision.get("state_ids")
        if (
            not isinstance(decision_routes, list)
            or not decision_routes
            or not set(decision_routes).issubset(routes)
            or not isinstance(decision_states, list)
            or not decision_states
            or any(
                state_id not in route_states.get(route_key, set())
                for route_key in decision_routes
                for state_id in decision_states
            )
        ):
            failures.append(f"{label} does not bind exact manifested routes/states.")
        if decision.get("source_reference_id") not in source_ids:
            failures.append(f"{label} cites no bound source observation.")
        evidence = decision.get("evidence")
        if not isinstance(evidence, dict) or set(evidence) != {"path", "sha256"}:
            failures.append(f"{label} has invalid source evidence.")
        else:
            evidence_path = (project / PurePosixPath(str(evidence.get("path") or ""))).resolve()
            if (
                not is_within(evidence_path, project.resolve())
                or not evidence_path.is_file()
                or not isinstance(evidence.get("sha256"), str)
                or file_sha256(evidence_path)[1] != evidence["sha256"]
            ):
                failures.append(f"{label} source evidence bytes are missing or drifted.")
            elif (
                str(evidence.get("path")), str(evidence.get("sha256"))
            ) not in allowed_source_evidence.get(
                str(decision.get("source_reference_id")), set()
            ):
                failures.append(
                    f"{label} evidence is not an immutable generated artifact of its cited source observation."
                )
    if set(planned) != observed_ids:
        failures.append("Visible decision planned IDs do not equal the exact sourced decision rows.")
    completeness = payload.get("completeness")
    expected_categories = list(VISIBLE_DECISION_CATEGORIES)
    if (
        not isinstance(completeness, dict)
        or set(completeness) != {
            "required_categories", "covered_categories", "placeholders_allowed",
            "generic_scaffold_allowed", "fallback_design_allowed",
            "unsourced_decisions",
        }
        or completeness.get("required_categories") != expected_categories
        or completeness.get("covered_categories") != expected_categories
        or observed_categories != set(expected_categories)
        or completeness.get("placeholders_allowed") is not False
        or completeness.get("generic_scaffold_allowed") is not False
        or completeness.get("fallback_design_allowed") is not False
        or completeness.get("unsourced_decisions") != []
    ):
        failures.append("Visible decision completeness does not prove every category sourced with no scaffold/fallback/placeholder escape.")
    # Inspect authored string values, not schema keys such as
    # ``placeholders_allowed`` which deliberately name the forbidden escape.
    authored_strings: list[str] = []

    def collect_authored_strings(value: object) -> None:
        if isinstance(value, str):
            authored_strings.append(value)
        elif isinstance(value, dict):
            for child in value.values():
                collect_authored_strings(child)
        elif isinstance(value, list):
            for child in value:
                collect_authored_strings(child)

    collect_authored_strings(payload)
    serialized = "\n".join(authored_strings).casefold()
    if re.search(r"__replace_with|\btodo\b|lorem ipsum|coming soon|\bplaceholder\b", serialized):
        failures.append("Visible decision source manifest contains placeholder or fallback content.")
    return failures


def reference_source_registry_failures(payload: object) -> list[str]:
    """Validate the maintained public-only inspiration source registry."""

    failures: list[str] = []
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version", "audited_on", "policy", "sources"
    }:
        return ["Reference source registry must use the versioned public-source shape."]
    if payload.get("schema_version") != 1:
        failures.append("Reference source registry has an unsupported schema version.")
    audited_on = payload.get("audited_on")
    if not isinstance(audited_on, str):
        failures.append("Reference source registry must declare an ISO audit date.")
    else:
        try:
            if date.fromisoformat(audited_on) > datetime.now(timezone.utc).date():
                failures.append("Reference source registry audit date may not be in the future.")
        except ValueError:
            failures.append("Reference source registry audit date must be ISO YYYY-MM-DD.")
    if not non_placeholder(str(payload.get("policy", ""))):
        failures.append("Reference source registry needs a substantive access policy.")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        return [*failures, "Reference source registry needs a nonempty source list."]
    seen_ids: set[str] = set()
    active_count = 0
    for index, source in enumerate(sources, start=1):
        label = f"Reference source registry row {index}"
        if not isinstance(source, dict) or set(source) != REFERENCE_SOURCE_REQUIRED_KEYS:
            failures.append(f"{label} has an unsupported shape.")
            continue
        if source.get("curation") not in ("award", "curated", "submission"):
            failures.append(
                f"{label} must declare curation as award, curated or "
                "submission, so selection can put quality before register."
            )
        source_id = source.get("id")
        if (
            not isinstance(source_id, str)
            or not EVIDENCE_CAPABILITY_PATTERN.fullmatch(source_id)
            or source_id in seen_ids
        ):
            failures.append(f"{label} needs a unique lowercase source id.")
        else:
            seen_ids.add(source_id)
        for key in ("name", "scope", "notes"):
            if not isinstance(source.get(key), str) or not non_placeholder(source[key]):
                failures.append(f"{label} needs a substantive {key!r} value.")
        raw_url = source.get("url")
        parsed = urlsplit(raw_url) if isinstance(raw_url, str) else None
        if (
            parsed is None
            or parsed.scheme != "https"
            or not parsed.netloc
        ):
            failures.append(f"{label} needs an absolute HTTPS source URL.")
        status = source.get("status")
        access = source.get("access")
        if status not in REFERENCE_SOURCE_STATUSES:
            failures.append(f"{label} must be active or inactive.")
        if not isinstance(access, str) or not non_placeholder(access):
            failures.append(f"{label} needs an access disposition.")
        if status == "active":
            active_count += 1
            if access not in ACTIVE_REFERENCE_SOURCE_ACCESS:
                failures.append(
                    f"{label} is active but does not have usable public access."
                )
        retrieval = source.get("retrieval")
        if retrieval not in REFERENCE_SOURCE_RETRIEVAL:
            failures.append(
                f"{label} needs a retrieval mode of fetch, browser, or none."
            )
        elif status == "active" and retrieval not in ACTIVE_REFERENCE_SOURCE_RETRIEVAL:
            failures.append(
                f"{label} is active but declares no usable retrieval mode; "
                "an active source must be fetch or browser."
            )
    if not active_count:
        failures.append("Reference source registry needs at least one active public source.")
    return failures


def load_reference_source_registry() -> tuple[dict[str, object], set[str], list[str]]:
    """Load the bundled source registry and return active discovery IDs."""

    try:
        payload = json.loads(REFERENCE_SOURCE_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, set(), [f"Reference source registry is unreadable: {exc}"]
    failures = reference_source_registry_failures(payload)
    if not isinstance(payload, dict):
        return {}, set(), failures
    sources = payload.get("sources")
    active_ids = {
        source["id"]
        for source in sources
        if (
            isinstance(source, dict)
            and source.get("status") == "active"
            and source.get("access") in ACTIVE_REFERENCE_SOURCE_ACCESS
            and isinstance(source.get("id"), str)
        )
    } if isinstance(sources, list) else set()
    return payload, active_ids, failures


def reference_source_curation() -> dict[str, str]:
    """Which sources publish only work that a jury or an editor chose.

    A bulk submission feed is fine to browse. It cannot supply a selected
    reference, because filtering a bulk feed by register yields
    register-matched mediocrity, and six faithful copies of forgettable sites
    make a forgettable site.
    """
    try:
        payload = json.loads(REFERENCE_SOURCE_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    sources = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(sources, list):
        return {}
    return {
        source["id"]: str(source.get("curation", "submission"))
        for source in sources
        if isinstance(source, dict) and isinstance(source.get("id"), str)
    }


def reference_dossier_date_failures(value: str, label: str) -> list[str]:
    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", value)
    if not dates:
        return [f"{label} must include a retrieval date (YYYY-MM-DD)."]
    try:
        if date.fromisoformat(dates[-1]) > datetime.now(timezone.utc).date():
            return [f"{label} retrieval date may not be in the future."]
    except ValueError:
        return [f"{label} has an invalid retrieval date."]
    return []


def reference_entry_url_failures(value: str, label: str) -> list[str]:
    match = re.search(r"https://[^\s)]+", value)
    if match is None:
        return [f"{label} needs a public HTTPS URL or gallery-entry URL."]
    parsed = urlsplit(match.group(0))
    if not parsed.netloc:
        return [f"{label} has an invalid HTTPS URL."]
    return []


def reference_entry_access_failures(
    value: str,
    label: str,
    authorized_basis: str | None,
) -> list[str]:
    access = value.split(";", 1)[0].strip().casefold()
    if access not in REFERENCE_ENTRY_ACCESS:
        return [
            f"{label} must be public-live, public-gallery-entry, or "
            "authorized-account; blocked or paywalled entries cannot qualify."
        ]
    if access == "authorized-account" and (
        authorized_basis is None
        or len(authorized_basis.strip()) < 18
        or authorized_basis.strip().casefold() == "none"
    ):
        return [
            f"{label} uses authorized-account and needs a non-sensitive "
            "authorized-account basis."
        ]
    return []


def reference_rank_values(
    value: str,
    *,
    maximum: int = REFERENCE_MINIMUM_STRONG,
) -> set[int] | None:
    values = [item.strip() for item in value.split(",") if item.strip()]
    if not values or any(not item.isdigit() for item in values):
        return None
    ranks = {int(item) for item in values}
    if len(ranks) != len(values) or any(
        rank < 1 or rank > maximum for rank in ranks
    ):
        return None
    return ranks


ROUTE_MANIFEST_SCHEMA_VERSION = 2
ROUTE_MANIFEST_STATE_KINDS = {"rest", "interactive", "system", "data"}
ROUTE_MANIFEST_TRIGGER_TYPES = {
    "none", "hover", "focus", "click", "keyboard", "input", "url", "programmatic"
}
ROUTE_MANIFEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}")
ROUTE_REFERENCE_ID = re.compile(r"strong-(\d+)(?:-[a-z][a-z0-9-]{0,47})?")
GATE_IGNORED_TREE_PARTS = {
    ".design-dna",
    ".git",
    "node_modules",
    "coverage",
    "__pycache__",
    ".pytest_cache",
    ".turbo",
}


def project_tree_identity(root: Path) -> str:
    """Hash the exact project tree that a gate build identity represents."""

    digest = hashlib.sha256()
    files = (path for path in root.rglob("*") if path.is_file())
    for file in sorted(files, key=lambda item: item.as_posix().casefold()):
        relative = file.relative_to(root)
        if any(part in GATE_IGNORED_TREE_PARTS for part in relative.parts):
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        with file.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def canonical_route_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("route URL must be absolute HTTP(S)")
    normalized_path = quote(
        re.sub(r"/{2,}", "/", parsed.path or "/"),
        safe="/%:@!$&'()*+,;=-._~",
    )
    normalized_query = quote(
        parsed.query,
        safe="!$&'()*+,-./:;=?@_%~",
    )
    return urlunsplit(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            normalized_path,
            normalized_query,
            "",
        )
    )


INVALID_ROUTE_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")


def normalize_safe_route_path(value: str) -> str | None:
    """Decode UTF-8 route IRIs while rejecting semantic/path escapes.

    This mirrors route_family_audit.normalize_route_path: case, Unicode NFC,
    underscores, extensions, and trailing slash stay significant; encoded
    separators, traversal, controls, whitespace, query, and fragment fail.
    """

    if not isinstance(value, str) or not value or len(value) > 2048:
        return None
    if INVALID_ROUTE_PERCENT.search(value):
        return None
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        return None
    raw_path = parsed.path
    if not raw_path.startswith("/") or "//" in raw_path:
        return None
    decoded_segments: list[str] = []
    for raw_segment in raw_path.split("/"):
        try:
            decoded = unquote_to_bytes(raw_segment).decode("utf-8", "strict")
        except UnicodeDecodeError:
            return None
        decoded = unicodedata.normalize("NFC", decoded)
        if decoded in {".", ".."}:
            return None
        if any(
            character in "/\\?#"
            or ord(character) <= 0x1F
            or ord(character) == 0x7F
            or character.isspace()
            for character in decoded
        ):
            return None
        decoded_segments.append(decoded)
    normalized = "/".join(decoded_segments)
    if not normalized.startswith("/") or "//" in normalized:
        return None
    return normalized


def reference_state_contract_failures(
    payload: object,
    *,
    expected_reference_id: str,
    expected_primary_url: str | None = None,
) -> tuple[list[str], set[str]]:
    """Validate the source-authored state authority shared by recorder/observer.

    Source states deliberately have no guessed vocabulary beyond `rest`.
    Stable project-local IDs name interactive, system, and data states and each
    carries an executable trigger.  Both browser producers consume these same
    bytes, so validating the contract here closes the hand-written JSON gap.
    """

    failures: list[str] = []
    ids: set[str] = set()
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "reference_id", "states"}
        or payload.get("schema_version") != 1
        or payload.get("reference_id") != expected_reference_id
        or not isinstance(payload.get("states"), list)
        or not payload["states"]
    ):
        return [
            "Source-state contract must use exact schema 1 and bind the expected reference ID."
        ], ids
    origins: set[tuple[str, str]] = set()
    canonical_primary: str | None = None
    if expected_primary_url:
        try:
            canonical_primary = canonical_route_url(expected_primary_url)
        except ValueError:
            failures.append("Source-state contract expected primary URL is invalid.")
    rest_urls: list[str] = []
    for index, state in enumerate(payload["states"], start=1):
        label = f"Source-state contract state {index}"
        if not isinstance(state, dict) or set(state) != {
            "id", "url", "kind", "trigger", "expectation"
        }:
            failures.append(f"{label} has an unsupported shape.")
            continue
        state_id = state.get("id")
        kind = state.get("kind")
        trigger = state.get("trigger")
        expectation = state.get("expectation")
        if (
            not isinstance(state_id, str)
            or re.fullmatch(r"[a-z][a-z0-9-]{0,47}", state_id) is None
            or state_id in ids
        ):
            failures.append(f"{label} needs a unique stable lowercase state ID.")
        else:
            ids.add(state_id)
        if kind not in ROUTE_MANIFEST_STATE_KINDS:
            failures.append(f"{label} has an unsupported state kind.")
        if (
            not isinstance(trigger, dict)
            or set(trigger) != {"type", "target", "value"}
        ):
            failures.append(f"{label} needs the exact executable trigger shape.")
            trigger = {}
        trigger_type = trigger.get("type")
        if trigger_type not in ROUTE_MANIFEST_TRIGGER_TYPES:
            failures.append(f"{label} has an unsupported trigger type.")
        if not isinstance(trigger.get("target"), str) or not trigger["target"].strip():
            failures.append(f"{label} trigger target must be explicit.")
        if trigger.get("value") is not None and not isinstance(trigger.get("value"), str):
            failures.append(f"{label} trigger value must be a string or null.")
        if not isinstance(expectation, str) or len(expectation.strip()) < 12:
            failures.append(f"{label} needs a substantive expectation.")
        if kind == "rest" and (
            state_id != "rest"
            or trigger_type != "none"
            or trigger.get("target") != "document"
            or trigger.get("value") is not None
        ):
            failures.append(
                f"{label} rest must use id rest and the canonical none/document/null trigger."
            )
        if kind != "rest" and trigger_type == "none":
            failures.append(f"{label} only rest may use a none trigger.")
        raw_url = state.get("url")
        try:
            normalized_url = canonical_route_url(raw_url) if isinstance(raw_url, str) else ""
        except ValueError:
            normalized_url = ""
        if (
            not normalized_url
            or normalized_url != raw_url
            or str(raw_url).startswith("__REPLACE_WITH")
        ):
            failures.append(f"{label} needs an exact canonical HTTP(S) URL.")
        else:
            parsed = urlsplit(normalized_url)
            origins.add((parsed.scheme, parsed.netloc))
            if state_id == "rest":
                rest_urls.append(normalized_url)
    if len(origins) != 1:
        failures.append("Every source-state URL must share one reference origin.")
    if rest_urls != ([canonical_primary] if canonical_primary else rest_urls[:1]):
        failures.append(
            "Source-state contract must contain exactly one canonical rest state at the primary URL."
        )
    if len(rest_urls) != 1:
        failures.append("Source-state contract must contain exactly one rest state.")
    return failures, ids


def interaction_census_failures(
    census: object,
    *,
    expected_profile: str,
    expected_state_ids: set[str],
    expected_urls: set[str] | None = None,
    artifact_root: Path | None = None,
    allowed_artifacts: set[tuple[str, int, str]] | None = None,
) -> list[str]:
    """Validate an uncapped live DOM/code-to-interaction reconciliation."""

    failures: list[str] = []
    expected_keys = {
        "profile", "pages", "page_states", "repeat_classes", "pointer_follow",
        "blocked_side_effects", "totals", "truncated", "missing", "complete",
    }
    if (
        not isinstance(census, dict)
        or set(census) != expected_keys
        or census.get("profile") != expected_profile
        or census.get("truncated") is not False
        or census.get("missing") != []
        or census.get("complete") is not True
    ):
        return [
            f"{expected_profile} interaction census is partial, capped, or has an unsupported shape."
        ]
    pages = census.get("pages")
    if not isinstance(pages, list) or not pages:
        return [f"{expected_profile} interaction census contains no live pages."]
    urls: set[str] = set()
    target_ids: set[str] = set()
    source_state_ids: set[str] = set()
    repeat_members: dict[str, set[str]] = {}
    repeat_inputs: dict[str, set[str]] = {}
    blocked_inputs: set[tuple[str, str]] = set()
    input_rows = exercised_rows = blocked_rows = 0

    def evidence_failures(value: object, label: str) -> list[str]:
        local: list[str] = []
        if not isinstance(value, dict) or not {"before", "after", "settled"}.issubset(value):
            return [f"{label} lacks before/after/settled generated artifacts."]
        for phase in ("before", "after", "settled"):
            item = value.get(phase)
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("file"), str)
                or type(item.get("bytes")) is not int
                or not isinstance(item.get("sha256"), str)
                or SHA256_HEX.fullmatch(item["sha256"]) is None
            ):
                local.append(f"{label} {phase} artifact metadata is invalid.")
                continue
            if artifact_root is not None:
                evidence_path = (
                    artifact_root / PurePosixPath(item["file"])
                ).resolve()
                if (
                    not is_within(evidence_path, artifact_root.resolve())
                    or not evidence_path.is_file()
                    or evidence_path.stat().st_size != item["bytes"]
                    or file_sha256(evidence_path)[1] != item["sha256"]
                ):
                    local.append(f"{label} {phase} artifact bytes are missing or drifted.")
                else:
                    try:
                        verify_png_artifact(evidence_path)
                    except StateError as exc:
                        local.append(f"{label} {phase} artifact is not a valid PNG: {exc}")
            if (
                allowed_artifacts is not None
                and (item["file"], item["bytes"], item["sha256"])
                not in allowed_artifacts
            ):
                local.append(f"{label} {phase} artifact is absent from the immutable ledger.")
            # Recorder evidence additionally maps the exact video instant to
            # an extracted full frame and source video. Timestamp-only rows
            # are deliberately insufficient.
            if "video_t_s" in item:
                for derived_name in ("frame", "video"):
                    derived = item.get(derived_name)
                    if (
                        not isinstance(derived, dict)
                        or not isinstance(derived.get("file"), str)
                        or type(derived.get("bytes")) is not int
                        or not isinstance(derived.get("sha256"), str)
                        or (
                            allowed_artifacts is not None
                            and (
                                derived["file"], derived["bytes"], derived["sha256"]
                            ) not in allowed_artifacts
                        )
                    ):
                        local.append(
                            f"{label} {phase} recorder evidence is timestamp-only or unledgered."
                        )
        navigation = value.get("navigation")
        if navigation is not None and (
            not isinstance(navigation, dict)
            or navigation.get("requested_normalized_url")
            != navigation.get("final_normalized_url")
            or navigation.get("redirect_count") != 0
            or type(navigation.get("final_status")) is not int
            or not 200 <= navigation["final_status"] < 300
        ):
            local.append(f"{label} navigation evidence is not an exact 2xx route binding.")
        return local
    for page_index, page in enumerate(pages, start=1):
        if not isinstance(page, dict) or set(page) != {
            "url", "targets", "dom_code_inventory"
        }:
            failures.append(f"{expected_profile} interaction page {page_index} has an unsupported shape.")
            continue
        url = page.get("url")
        try:
            canonical = canonical_route_url(str(url or ""))
        except ValueError:
            canonical = ""
        if not canonical or canonical != url or canonical in urls:
            failures.append(f"{expected_profile} interaction page {page_index} URL is invalid or duplicate.")
        else:
            urls.add(canonical)
        targets = page.get("targets")
        if not isinstance(targets, list):
            failures.append(f"{expected_profile} interaction page {page_index} targets are invalid.")
            continue
        page_target_ids: list[str] = []
        for target_index, target in enumerate(targets, start=1):
            if not isinstance(target, dict) or set(target) != {
                "target_id", "page_url", "selector", "tag", "role", "text", "semantic_key",
                "class_signature", "repeat_class", "repeat_index",
                "repeat_count", "kind", "semantic_state", "source_state_ids", "inputs",
            }:
                failures.append(
                    f"{expected_profile} interaction target {page_index}/{target_index} has an unsupported shape."
                )
                continue
            target_id = target.get("target_id")
            if (
                not isinstance(target_id, str)
                or re.fullmatch(r"[0-9a-f]{24}", target_id) is None
                or target_id in target_ids
                or target.get("page_url") != url
                or not isinstance(target.get("selector"), str)
                or not target["selector"].startswith('[data-dna-interaction-id="')
                or not isinstance(target.get("class_signature"), list)
                or not isinstance(target.get("text"), str)
                or not isinstance(target.get("semantic_key"), str)
                or not target.get("semantic_key")
                or not isinstance(target.get("semantic_state"), dict)
                or set(target.get("semantic_state", {})) != {
                    "aria_expanded", "aria_pressed", "aria_controls",
                    "aria_haspopup", "disabled",
                }
                or type(target.get("semantic_state", {}).get("disabled")) is not bool
                or type(target.get("repeat_index")) is not int
                or type(target.get("repeat_count")) is not int
                or target.get("repeat_index", 0) < 1
                or target.get("repeat_count", 0) < target.get("repeat_index", 0)
            ):
                failures.append(
                    f"{expected_profile} interaction target {page_index}/{target_index} identity is invalid."
                )
                continue
            target_ids.add(target_id)
            page_target_ids.append(target_id)
            state_ids = target.get("source_state_ids")
            if (
                not isinstance(state_ids, list)
                or len(state_ids) != len(set(state_ids))
                or not set(state_ids).issubset(expected_state_ids)
            ):
                failures.append(f"{expected_profile} interaction target {target_id} has invalid source states.")
            else:
                source_state_ids.update(state_ids)
            repeat_class = target.get("repeat_class")
            if not isinstance(repeat_class, str) or not repeat_class:
                failures.append(f"{expected_profile} interaction target {target_id} has no repeat class.")
            else:
                repeat_members.setdefault(repeat_class, set()).add(target_id)
            inputs = target.get("inputs")
            if not isinstance(inputs, list) or not inputs:
                failures.append(f"{expected_profile} DOM-discovered target {target_id} has no input coverage.")
                continue
            if isinstance(repeat_class, str) and repeat_class:
                repeat_inputs.setdefault(repeat_class, set()).update(
                    str(item.get("input_kind"))
                    for item in inputs
                    if isinstance(item, dict) and item.get("input_kind")
                )
            safe_exercised = False
            active_behavior = False
            blocked_target = False
            exercised_input_kinds: set[str] = set()
            for input_record in inputs:
                input_rows += 1
                if not isinstance(input_record, dict) or set(input_record) != {
                    "input_kind", "input_value", "safety", "status",
                    "source_state_id", "before_sha256", "after_sha256",
                    "settled_sha256", "changed_properties", "change_classification", "behavior",
                    "evidence", "disposition",
                }:
                    failures.append(f"{expected_profile} target {target_id} input has an unsupported shape.")
                    continue
                state_id = input_record.get("source_state_id")
                if state_id is not None and state_id not in expected_state_ids:
                    failures.append(f"{expected_profile} target {target_id} input maps an unknown source state.")
                status = input_record.get("status")
                classification = input_record.get("change_classification")
                if (
                    not isinstance(classification, dict)
                    or set(classification) != {
                        "cosmetic", "structural_semantic", "diagnostic"
                    }
                    or any(
                        not isinstance(classification.get(field), list)
                        for field in ("cosmetic", "structural_semantic", "diagnostic")
                    )
                ):
                    failures.append(
                        f"{expected_profile} target {target_id} input lacks exact semantic/cosmetic/diagnostic classification."
                    )
                    classification = {
                        "cosmetic": [], "structural_semantic": [], "diagnostic": []
                    }
                if status == "exercised":
                    exercised_rows += 1
                    safe_exercised = True
                    exercised_input_kinds.add(str(input_record.get("input_kind")))
                    if (
                        input_record.get("safety") != "safe"
                        or input_record.get("disposition")
                        not in {"sourceable-observed-behavior", "observed-quiet"}
                        or not isinstance(input_record.get("changed_properties"), list)
                        or not isinstance(input_record.get("behavior"), str)
                        or not input_record["behavior"]
                        or not isinstance(input_record.get("evidence"), dict)
                        or any(
                            not isinstance(input_record.get(field), str)
                            or SHA256_HEX.fullmatch(input_record[field]) is None
                            for field in ("before_sha256", "after_sha256", "settled_sha256")
                        )
                    ):
                        failures.append(f"{expected_profile} target {target_id} exercised input lacks generated evidence.")
                    else:
                        meaningful_changes = classification["structural_semantic"]
                        changed = input_record.get("changed_properties", [])
                        classified = (
                            classification["cosmetic"]
                            + classification["structural_semantic"]
                        )
                        canonical_rows = lambda rows: sorted(
                            json.dumps(
                                row,
                                sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=False,
                            )
                            for row in rows
                        )
                        if canonical_rows(classified) != canonical_rows(changed):
                            failures.append(
                                f"{expected_profile} target {target_id} classification does not partition its measured changes."
                            )
                        if any(
                            isinstance(change, dict)
                            and change.get("property")
                            in {
                                "hovered", "transition_duration", "transition_delay",
                                "transition_property", "transition_timing",
                            }
                            for change in classified
                        ):
                            failures.append(
                                f"{expected_profile} target {target_id} promotes diagnostic hover/transition bookkeeping to visible behavior."
                            )
                        if (
                            input_record.get("disposition")
                            == "sourceable-observed-behavior"
                            and (
                                bool(meaningful_changes)
                            )
                        ):
                            active_behavior = True
                        failures.extend(
                            evidence_failures(
                                input_record.get("evidence"),
                                f"{expected_profile} target {target_id} input",
                            )
                        )
                elif status == "blocked":
                    blocked_rows += 1
                    blocked_target = True
                    blocked_inputs.add((target_id, str(input_record.get("input_kind"))))
                    if (
                        input_record.get("safety") != "blocked-side-effect"
                        or input_record.get("disposition") != "blocked-requires-safe-owner-handoff"
                        or input_record.get("evidence") is not None
                        or classification != {
                            "cosmetic": [], "structural_semantic": [], "diagnostic": []
                        }
                        or any(input_record.get(field) is not None for field in (
                            "before_sha256", "after_sha256", "settled_sha256"
                        ))
                    ):
                        failures.append(f"{expected_profile} target {target_id} blocked input is misrepresented as observed.")
                else:
                    failures.append(f"{expected_profile} target {target_id} input is neither exercised nor safely blocked.")
            if (
                target.get("kind")
                in {"control", "open-close", "input-control", "media"}
                and safe_exercised
                and not active_behavior
                and not blocked_target
            ):
                failures.append(
                    f"{expected_profile} DOM control {target_id} is exercised but visually/semantically dead."
                )
            if (
                target.get("kind")
                in {"route-link", "control", "open-close", "input-control"}
                and target.get("semantic_state", {}).get("disabled") is not True
                and not exercised_input_kinds.intersection({"focus", "keyboard"})
            ):
                failures.append(
                    f"{expected_profile} DOM control {target_id} has no generated keyboard/focus coverage."
                )
        dom = page.get("dom_code_inventory")
        if not isinstance(dom, dict) or set(dom) != {
            "routes_discovered", "controls_discovered", "state_hooks",
            "animation_hooks", "assets", "scripts", "inline_handlers",
            "live_target_ids", "live_source_state_ids",
            "unreconciled_controls", "complete",
        }:
            failures.append(f"{expected_profile} interaction page {page_index} DOM/code inventory is invalid.")
        elif (
            dom.get("complete") is not True
            or dom.get("unreconciled_controls") != []
            or dom.get("controls_discovered") != page_target_ids
            or dom.get("live_target_ids") != page_target_ids
            or not isinstance(dom.get("routes_discovered"), list)
            or not isinstance(dom.get("assets"), list)
            or not isinstance(dom.get("scripts"), list)
            or not set(dom.get("live_source_state_ids", [])).issubset(expected_state_ids)
        ):
            failures.append(
                f"{expected_profile} interaction page {page_index} omits DOM/code-discovered routes, controls, hooks, or assets."
            )
    if expected_urls is not None and urls != expected_urls:
        failures.append(f"{expected_profile} interaction census pages differ from full discovery coverage.")
    page_states = census.get("page_states")
    if not isinstance(page_states, list):
        failures.append(f"{expected_profile} interaction census page-state ledger is invalid.")
    else:
        for state in page_states:
            if (
                not isinstance(state, dict)
                or set(state) != {
                    "source_state_id", "kind", "trigger", "page_url",
                    "disposition", "trigger_evidence", "evidence",
                }
                or state.get("source_state_id") not in expected_state_ids
                or state.get("disposition")
                not in {"observed-rest", "covered-by-state-ledger"}
                or not isinstance(state.get("trigger_evidence"), dict)
                or set(state["trigger_evidence"]) != {
                    "before_sha256", "after_sha256", "settled_sha256",
                    "changed_properties", "change_classification", "behavior",
                }
                or any(
                    not isinstance(state["trigger_evidence"].get(field), str)
                    or SHA256_HEX.fullmatch(state["trigger_evidence"][field]) is None
                    for field in ("before_sha256", "after_sha256", "settled_sha256")
                )
                or not isinstance(state["trigger_evidence"].get("changed_properties"), list)
                or not isinstance(state["trigger_evidence"].get("change_classification"), dict)
                or set(state["trigger_evidence"].get("change_classification", {}))
                != {"cosmetic", "structural_semantic", "diagnostic"}
                or any(
                    not isinstance(
                        state["trigger_evidence"]["change_classification"].get(field),
                        list,
                    )
                    for field in ("cosmetic", "structural_semantic", "diagnostic")
                )
                or not isinstance(state["trigger_evidence"].get("behavior"), str)
            ):
                failures.append(f"{expected_profile} interaction census has an invalid page state.")
                continue
            source_state_ids.add(str(state["source_state_id"]))
            failures.extend(
                evidence_failures(
                    state.get("evidence"),
                    f"{expected_profile} page state {state.get('source_state_id')}",
                )
            )
    if source_state_ids != expected_state_ids:
        failures.append(f"{expected_profile} interaction census does not bind every authored source state.")
    repeats = census.get("repeat_classes")
    repeat_rows: dict[str, set[str]] = {}
    repeat_invalid = False
    for row in repeats or []:
        if (
            not isinstance(row, dict)
            or set(row) != {
                "repeat_class", "target_ids", "input_kinds", "equivalent",
                "behavior_signatures", "evidence",
            }
            or not isinstance(row.get("repeat_class"), str)
            or row.get("repeat_class") in repeat_rows
            or not isinstance(row.get("target_ids"), list)
            or len(row.get("target_ids", [])) != len(set(row.get("target_ids", [])))
            or not isinstance(row.get("input_kinds"), list)
            or set(row.get("input_kinds", [])) != repeat_inputs.get(str(row.get("repeat_class")), set())
            or row.get("equivalent") is not True
            or not isinstance(row.get("behavior_signatures"), list)
            or not isinstance(row.get("evidence"), list)
        ):
            repeat_invalid = True
            continue
        repeat_rows[str(row["repeat_class"])] = set(row["target_ids"])
    if not isinstance(repeats, list) or repeat_invalid or repeat_rows != repeat_members:
        failures.append(f"{expected_profile} repeated-control census is incomplete or gameable.")
    blocked = census.get("blocked_side_effects")
    blocked_ledger = {
        (str(item.get("target_id")), str(item.get("input_kind")))
        for item in blocked or []
        if isinstance(item, dict)
        and isinstance(item.get("reason"), str)
        and isinstance(item.get("handoff"), str)
        and item.get("handoff")
    }
    if not isinstance(blocked, list) or blocked_ledger != blocked_inputs:
        failures.append(f"{expected_profile} blocked side-effect ledger does not reconcile inputs.")
    totals = census.get("totals")
    if (
        not isinstance(totals, dict)
        or set(totals) != {
            "targets_discovered", "inputs_discovered", "inputs_exercised",
            "inputs_blocked",
        }
        or any(type(value) is not int or value < 0 for value in totals.values())
        or totals.get("inputs_discovered")
        != totals.get("inputs_exercised", 0) + totals.get("inputs_blocked", 0)
        or totals.get("targets_discovered", 0) < len(target_ids)
        or totals.get("inputs_discovered", 0) < input_rows
        or totals.get("inputs_exercised", 0) < exercised_rows
        or totals.get("inputs_blocked", 0) < blocked_rows
    ):
        failures.append(f"{expected_profile} interaction census totals do not reconcile uncapped coverage.")
    pointer_follow = census.get("pointer_follow")
    if not isinstance(pointer_follow, list) or any(
        not isinstance(item, dict)
        or item.get("distinct_from_hover") is not True
        or not isinstance(item.get("evidence"), dict)
        for item in pointer_follow
    ):
        failures.append(f"{expected_profile} pointer-follow census is invalid.")
    else:
        for pointer in pointer_follow:
            failures.extend(
                evidence_failures(
                    pointer.get("evidence"),
                    f"{expected_profile} pointer-follow {pointer.get('target_id')}",
                )
            )
    return failures


SOURCE_RENDERED_QA_TOP_KEYS = {
    "profile", "pages", "totals", "truncated", "missing", "complete",
}
SOURCE_RENDERED_QA_PAGE_KEYS = {
    "url", "evidence", "clipping", "collisions", "fixed_rail_overlaps",
    "hidden_controls", "control_visibility", "dead_controls",
    "semantic_issues", "overlays", "keyboard_paths", "keyboard",
    "semantic_equivalence", "state_semantics",
    "reduced_motion", "deep_link", "reload", "dead_end",
}


def source_rendered_qa_failures(
    payload: object,
    *,
    expected_profile: str,
    expected_urls: set[str],
    artifact_root: Path,
    allowed_artifacts: set[tuple[str, int, str]],
    interaction_census: object | None = None,
) -> list[str]:
    """Validate generated source rendered-QA bytes and live invariants."""

    failures: list[str] = []
    if (
        not isinstance(payload, dict)
        or set(payload) != SOURCE_RENDERED_QA_TOP_KEYS
        or payload.get("profile") != expected_profile
        or payload.get("truncated") is not False
        or payload.get("missing") != []
        or payload.get("complete") is not True
    ):
        return [
            f"{expected_profile} source rendered QA is partial, capped, or has an unsupported shape."
        ]

    root = artifact_root.resolve()

    def artifact_failures(value: object, label: str) -> list[str]:
        local: list[str] = []
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("file"), str)
            or type(value.get("bytes")) is not int
            or value.get("bytes", -1) < 1
            or not isinstance(value.get("sha256"), str)
            or SHA256_HEX.fullmatch(value["sha256"]) is None
        ):
            return [f"{label} lacks a generated file/bytes/SHA-256 binding."]
        relative = PurePosixPath(value["file"])
        candidate = (root / relative).resolve()
        try:
            relative_to_root = candidate.relative_to(root)
        except ValueError:
            relative_to_root = None
        ancestors = [root]
        if relative_to_root is not None:
            cursor = root
            for part in relative_to_root.parts:
                cursor = cursor / part
                ancestors.append(cursor)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative_to_root is None
            or any(is_reparse(item) for item in ancestors if item.exists())
            or not candidate.is_file()
            or candidate.stat().st_size != value["bytes"]
            or file_sha256(candidate)[1] != value["sha256"]
            or (value["file"], value["bytes"], value["sha256"])
            not in allowed_artifacts
        ):
            local.append(f"{label} artifact is outside the generated ledger or its bytes drifted.")
        else:
            try:
                verify_png_artifact(candidate)
            except StateError as exc:
                local.append(f"{label} is not a valid generated PNG: {exc}")
        if "video_t_s" in value:
            for derived_name in ("frame", "video"):
                derived = value.get(derived_name)
                if (
                    not isinstance(derived, dict)
                    or not isinstance(derived.get("file"), str)
                    or type(derived.get("bytes")) is not int
                    or not isinstance(derived.get("sha256"), str)
                    or (
                        derived["file"], derived["bytes"], derived["sha256"]
                    ) not in allowed_artifacts
                ):
                    local.append(
                        f"{label} recorder evidence is timestamp-only or lacks its frame/video ledger binding."
                    )
        return local

    def navigation_failures(value: object, url: str, label: str) -> list[str]:
        if (
            not isinstance(value, dict)
            or value.get("requested_normalized_url") != url
            or value.get("final_normalized_url") != url
            or value.get("response_final_normalized_url") != url
            or value.get("redirect_count") != 0
            or type(value.get("final_status")) is not int
            or not 200 <= value["final_status"] < 300
        ):
            return [f"{label} is not an exact nonredirecting 2xx navigation."]
        return []

    census_targets: dict[str, dict[str, object]] = {}
    if isinstance(interaction_census, dict):
        for page in interaction_census.get("pages", []):
            if not isinstance(page, dict):
                continue
            for target in page.get("targets", []):
                if isinstance(target, dict) and isinstance(target.get("target_id"), str):
                    census_targets[target["target_id"]] = target

    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        return [*failures, f"{expected_profile} source rendered QA contains no pages."]
    observed_urls: set[str] = set()
    overlay_total = 0
    issue_total = 0
    for index, page in enumerate(pages, start=1):
        label = f"{expected_profile} source rendered QA page {index}"
        if not isinstance(page, dict) or set(page) != SOURCE_RENDERED_QA_PAGE_KEYS:
            failures.append(f"{label} has an unsupported shape.")
            continue
        url = page.get("url")
        try:
            canonical = canonical_route_url(str(url or ""))
        except ValueError:
            canonical = ""
        if not canonical or canonical != url or canonical in observed_urls:
            failures.append(f"{label} URL is invalid or duplicate.")
            continue
        observed_urls.add(canonical)
        failures.extend(artifact_failures(page.get("evidence"), f"{label} rest evidence"))
        for field in (
            "clipping", "collisions", "fixed_rail_overlaps", "dead_controls",
            "semantic_issues",
        ):
            if page.get(field) != []:
                failures.append(f"{label} reports generated {field.replace('_', '-')} defects.")
        hidden = page.get("hidden_controls")
        if not isinstance(hidden, list) or any(
            not isinstance(item, dict) or item.get("focusable_while_hidden") is True
            for item in hidden or []
        ):
            failures.append(f"{label} has a visually hidden control that remains keyboard-operable.")
        controls = page.get("control_visibility")
        if not isinstance(controls, list) or any(
            not isinstance(item, dict)
            or set(item) != {
                "selector", "semantic_key", "text", "role", "tag", "visible",
                "focusable", "aria_hidden",
            }
            or not isinstance(item.get("semantic_key"), str)
            or not item["semantic_key"]
            or type(item.get("visible")) is not bool
            or type(item.get("focusable")) is not bool
            for item in controls or []
        ):
            failures.append(f"{label} control-visibility census is invalid.")
        state_semantics = page.get("state_semantics")
        if (
            not isinstance(state_semantics, dict)
            or set(state_semantics) not in (
                {"required", "complete", "target", "attributes"},
                {"required", "complete", "target", "attributes", "controlled_visible"},
            )
            or type(state_semantics.get("required")) is not bool
            or state_semantics.get("complete") is not True
            or (
                state_semantics.get("required") is True
                and not isinstance(state_semantics.get("attributes"), dict)
            )
        ):
            failures.append(f"{label} disclosure/toggle semantics are incomplete.")
        overlays = page.get("overlays")
        if not isinstance(overlays, list):
            failures.append(f"{label} overlay inventory is invalid.")
            overlays = []
        overlay_total += len(overlays)
        for overlay_index, overlay in enumerate(overlays, start=1):
            overlay_label = f"{label} overlay {overlay_index}"
            required_overlay_fields = {
                "selector", "key", "open", "aria_modal", "initial_focus_inside",
                "inert_background", "closed_descendants_inert",
                "stacking_above_background_controls", "focusable_count",
                "background_control_selectors", "descendant_selectors",
                "opener_selector", "hit_tests", "initial_focus",
                "background_focus_blocked", "focus_trap", "focus_return",
                "escape_closes", "evidence", "complete",
            }
            if (
                not isinstance(overlay, dict)
                or set(overlay) != required_overlay_fields
                or overlay.get("complete") is not True
                or overlay.get("inert_background") is not True
                or overlay.get("closed_descendants_inert") is not True
                or overlay.get("stacking_above_background_controls") is not True
                or overlay.get("initial_focus") is not True
                or overlay.get("background_focus_blocked") is not True
                or overlay.get("focus_trap") is not True
                or overlay.get("focus_return") is not True
                or overlay.get("escape_closes") is not True
                or not isinstance(overlay.get("background_control_selectors"), list)
                or not isinstance(overlay.get("descendant_selectors"), list)
                or not isinstance(overlay.get("hit_tests"), list)
            ):
                failures.append(f"{overlay_label} inert/focus/stacking behavior is incomplete.")
                continue
            evidence = overlay.get("evidence")
            if not isinstance(evidence, dict) or set(evidence) != {"before", "after", "settled"}:
                failures.append(f"{overlay_label} lacks before/after/settled evidence.")
            else:
                for phase in ("before", "after", "settled"):
                    failures.extend(artifact_failures(evidence[phase], f"{overlay_label} {phase}"))
        keyboard = page.get("keyboard_paths")
        keyboard_by_id = {
            row.get("target_id"): row
            for row in keyboard or []
            if isinstance(row, dict) and isinstance(row.get("target_id"), str)
        } if isinstance(keyboard, list) else {}
        if not isinstance(keyboard, list) or len(keyboard_by_id) != len(keyboard):
            failures.append(f"{label} keyboard-path inventory is invalid or duplicate.")
        for target_id, target in census_targets.items():
            if target.get("page_url") != url or target.get("semantic_state", {}).get("disabled") is True:
                continue
            if target.get("kind") not in {"route-link", "control", "open-close", "input-control"}:
                continue
            row = keyboard_by_id.get(target_id)
            inputs = row.get("inputs") if isinstance(row, dict) else None
            if (
                not isinstance(row, dict)
                or set(row) != {"target_id", "inputs", "complete"}
                or row.get("complete") is not True
                or not isinstance(inputs, list)
                or not any(
                    isinstance(item, dict)
                    and item.get("input_kind") in {"focus", "keyboard"}
                    and item.get("status") == "exercised"
                    and isinstance(item.get("evidence"), dict)
                    for item in inputs
                )
            ):
                failures.append(f"{label} target {target_id} has no generated keyboard/focus path.")
        keyboard_summary = page.get("keyboard")
        if keyboard_summary != {"complete": True, "missing": []}:
            failures.append(f"{label} keyboard summary is incomplete.")
        semantic_equivalence = page.get("semantic_equivalence")
        if semantic_equivalence != {"complete": True, "mismatches": []}:
            failures.append(f"{label} repeated controls are not semantically equivalent.")
        reduced = page.get("reduced_motion")
        if (
            not isinstance(reduced, dict)
            or set(reduced) != {"navigation", "animations", "evidence", "honors_preference", "complete"}
            or reduced.get("honors_preference") is not True
            or reduced.get("complete") is not True
            or not isinstance(reduced.get("animations"), list)
        ):
            failures.append(f"{label} reduced-motion evidence is incomplete.")
        else:
            failures.extend(navigation_failures(reduced["navigation"], url, f"{label} reduced-motion navigation"))
            failures.extend(artifact_failures(reduced["evidence"], f"{label} reduced-motion evidence"))
        deep_link = page.get("deep_link")
        if not isinstance(deep_link, dict) or set(deep_link) != {"navigation", "evidence", "complete"} or deep_link.get("complete") is not True:
            failures.append(f"{label} deep-link evidence is incomplete.")
        else:
            failures.extend(navigation_failures(deep_link["navigation"], url, f"{label} deep-link navigation"))
            failures.extend(artifact_failures(deep_link["evidence"], f"{label} deep-link evidence"))
        reload = page.get("reload")
        if (
            not isinstance(reload, dict)
            or set(reload) != {"navigation", "before", "after", "stable_pixels", "complete"}
            or reload.get("complete") is not True
            or type(reload.get("stable_pixels")) is not bool
        ):
            failures.append(f"{label} reload evidence is incomplete.")
        else:
            failures.extend(navigation_failures(reload["navigation"], url, f"{label} reload navigation"))
            failures.extend(artifact_failures(reload["before"], f"{label} reload before"))
            failures.extend(artifact_failures(reload["after"], f"{label} reload after"))
        dead_end = page.get("dead_end")
        if (
            not isinstance(dead_end, dict)
            or set(dead_end) != {"same_origin_destinations", "is_dead_end", "terminal_signal", "problem"}
            or not isinstance(dead_end.get("same_origin_destinations"), list)
            or type(dead_end.get("is_dead_end")) is not bool
            or type(dead_end.get("terminal_signal")) is not bool
            or dead_end.get("problem") is not False
        ):
            failures.append(f"{label} is a generated dead-end experience path.")
        page_issues = sum(
            len(page.get(field) or [])
            for field in (
                "clipping", "collisions", "fixed_rail_overlaps", "dead_controls",
                "semantic_issues",
            )
        ) + len([
            item for item in hidden or []
            if isinstance(item, dict) and item.get("focusable_while_hidden") is True
        ]) + len([
            item for item in overlays
            if isinstance(item, dict) and item.get("complete") is not True
        ]) + (0 if isinstance(state_semantics, dict) and state_semantics.get("complete") is True else 1) + (
            len(keyboard_summary.get("missing", []))
            if isinstance(keyboard_summary, dict)
            and isinstance(keyboard_summary.get("missing"), list)
            else 1
        ) + (
            len(semantic_equivalence.get("mismatches", []))
            if isinstance(semantic_equivalence, dict)
            and isinstance(semantic_equivalence.get("mismatches"), list)
            else 1
        ) + (
            0 if isinstance(reduced, dict) and reduced.get("honors_preference") is True else 1
        ) + (0 if isinstance(dead_end, dict) and dead_end.get("problem") is False else 1)
        issue_total += page_issues
    if observed_urls != expected_urls:
        failures.append(f"{expected_profile} source rendered QA pages differ from complete live traversal.")
    totals = payload.get("totals")
    if (
        not isinstance(totals, dict)
        or set(totals) != {"pages", "issues", "controls", "overlays"}
        or totals.get("pages") != len(pages)
        or totals.get("issues") != issue_total
        or type(totals.get("overlays")) is not int
        or totals.get("overlays", -1) < overlay_total
        or type(totals.get("controls")) is not int
        or totals.get("controls", -1) < len(census_targets)
    ):
        failures.append(f"{expected_profile} source rendered QA totals do not reconcile generated findings.")
    return failures


SHA256_HEX = re.compile(r"[0-9a-f]{64}")
PREBUILD_AUTHORIZATION_SCHEMA_VERSION = 1
PREBUILD_AUTHORIZATION_RECORD_TYPE = "design-dna-prebuild-authorization"
PREBUILD_AUTHORIZATION_RELATIVE_DIR = PurePosixPath(
    ".design-dna/evidence/prebuild-authorizations"
)
FIRST_SCREEN_GATE_LINE = re.compile(
    r"(?m)^-\s*First-screen gate:\s*.*$",
    re.IGNORECASE,
)


def dossier_core_sha256(path: Path) -> str:
    """Hash a dossier while excluding only its circular gate binding value."""

    text = path.read_text(encoding="utf-8", errors="strict").replace("\r\n", "\n")
    normalized = FIRST_SCREEN_GATE_LINE.sub(
        "- First-screen gate: <excluded-from-dossier-core-hash>", text
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def packaged_gate_runtime_identity() -> dict[str, str]:
    scripts = Path(__file__).resolve().parent
    gate = scripts / "gate.py"
    files = [gate, Path(__file__).resolve(), *sorted(scripts.glob("*.mjs"), key=lambda item: item.name)]
    return {path.name: file_sha256(path)[1] for path in files}


def prebuild_authorization_chain(
    project: Path,
) -> tuple[list[str], list[tuple[Path, dict[str, object], str]]]:
    """Validate the append-only predecessor chain and return its records."""

    failures: list[str] = []
    root = project / PREBUILD_AUTHORIZATION_RELATIVE_DIR
    if not root.is_dir():
        return (["Prebuild authorization directory is missing."], [])
    files = sorted(root.glob("*.json"), key=lambda item: item.name)
    if not files:
        return (["Prebuild authorization chain is empty."], [])
    expected_runtime = packaged_gate_runtime_identity()
    expected_gate_sha = expected_runtime.get("gate.py")
    previous_path: Path | None = None
    previous_sha: str | None = None
    previous_time: datetime | None = None
    records: list[tuple[Path, dict[str, object], str]] = []
    expected_keys = {
        "schema_version", "record_type", "authorization_id", "authorized_at",
        "project", "manifest_id", "manifest_sha256", "route_key",
        "proof_build_id", "proof_tree_sha256", "dossier_core_sha256",
        "visible_decision_source_manifest", "visible_decision_snapshot",
        "first_screen_gate", "previous_authorization",
        "producer_script_sha256", "runtime_identity",
    }
    for index, file in enumerate(files):
        if file.is_symlink() or not file.is_file():
            failures.append(f"Prebuild authorization entry is not a regular file: {file.name}.")
            continue
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            failures.append(f"Prebuild authorization {file.name} is unreadable: {exc}")
            continue
        digest = file_sha256(file)[1]
        if not isinstance(payload, dict) or set(payload) != expected_keys:
            failures.append(f"Prebuild authorization {file.name} has an unsupported shape.")
            continue
        if (
            payload.get("schema_version") != PREBUILD_AUTHORIZATION_SCHEMA_VERSION
            or payload.get("record_type") != PREBUILD_AUTHORIZATION_RECORD_TYPE
            or not isinstance(payload.get("authorization_id"), str)
            or re.fullmatch(r"[0-9a-f]{32}", payload["authorization_id"]) is None
        ):
            failures.append(f"Prebuild authorization {file.name} has invalid identity.")
        try:
            authorized_at = datetime.fromisoformat(
                str(payload.get("authorized_at", "")).replace("Z", "+00:00")
            )
        except ValueError:
            authorized_at = None
            failures.append(f"Prebuild authorization {file.name} has invalid authorized_at.")
        if authorized_at is not None and previous_time is not None and authorized_at <= previous_time:
            failures.append("Prebuild authorization timestamps are not strictly increasing.")
        if authorized_at is not None:
            previous_time = authorized_at
        if Path(str(payload.get("project") or "")).resolve() != project.resolve():
            failures.append(f"Prebuild authorization {file.name} belongs to another project.")
        for field in ("manifest_sha256", "proof_tree_sha256", "dossier_core_sha256"):
            if not isinstance(payload.get(field), str) or SHA256_HEX.fullmatch(payload[field]) is None:
                failures.append(f"Prebuild authorization {file.name} has invalid {field}.")
        if (
            not isinstance(payload.get("manifest_id"), str)
            or ROUTE_MANIFEST_ID.fullmatch(payload["manifest_id"]) is None
            or not isinstance(payload.get("proof_build_id"), str)
            or ROUTE_MANIFEST_ID.fullmatch(payload["proof_build_id"]) is None
            or not isinstance(payload.get("route_key"), str)
            or re.fullmatch(r"[a-z][a-z0-9-]{0,47}", payload["route_key"]) is None
        ):
            failures.append(f"Prebuild authorization {file.name} has invalid manifest/build/route fields.")
        if payload.get("producer_script_sha256") != expected_gate_sha:
            failures.append(f"Prebuild authorization {file.name} uses stale gate.py bytes.")
        if payload.get("runtime_identity") != expected_runtime:
            failures.append(f"Prebuild authorization {file.name} uses stale runtime bytes.")
        visible_binding = payload.get("visible_decision_source_manifest")
        current_visible = project / ".design-dna" / "visible-decision-sources.json"
        if (
            not isinstance(visible_binding, dict)
            or set(visible_binding) != {"path", "sha256"}
            or visible_binding.get("path")
            != ".design-dna/visible-decision-sources.json"
            or not current_visible.is_file()
            or visible_binding.get("sha256") != file_sha256(current_visible)[1]
        ):
            failures.append(
                f"Prebuild authorization {file.name} visible-decision source bytes are missing or drifted."
            )
        gate_binding = payload.get("first_screen_gate")
        if (
            not isinstance(gate_binding, dict)
            or set(gate_binding) != {"path", "sha256"}
            or gate_binding.get("path")
            != (
                PREBUILD_AUTHORIZATION_RELATIVE_DIR.parent
                / "prebuild-runs"
                / str(payload.get("authorization_id") or "")
                / "gate.json"
            ).as_posix()
            or not isinstance(gate_binding.get("sha256"), str)
            or SHA256_HEX.fullmatch(gate_binding["sha256"]) is None
        ):
            failures.append(f"Prebuild authorization {file.name} has invalid gate binding.")
        else:
            immutable_gate = (
                project / PurePosixPath(gate_binding["path"])
            ).resolve()
            if (
                not is_within(immutable_gate, project.resolve())
                or not immutable_gate.is_file()
                or file_sha256(immutable_gate)[1] != gate_binding["sha256"]
            ):
                failures.append(
                    f"Prebuild authorization {file.name} immutable gate bytes are missing or drifted."
                )
            else:
                try:
                    immutable_record = json.loads(
                        immutable_gate.read_text(encoding="utf-8")
                    )
                except (OSError, ValueError) as exc:
                    failures.append(
                        f"Prebuild authorization {file.name} immutable gate is unreadable: {exc}"
                    )
                    immutable_record = None
                if not isinstance(immutable_record, dict) or any(
                    immutable_record.get(gate_field) != expected_value
                    for gate_field, expected_value in {
                        "tool": "gate.py",
                        "schema_version": 2,
                        "phase": "first-screen",
                        "pass": True,
                        "project": str(project.resolve()),
                        "authorization_id": payload.get("authorization_id"),
                        "route_key": payload.get("route_key"),
                        "build_id": payload.get("proof_build_id"),
                        "build_tree_sha256_before": payload.get("proof_tree_sha256"),
                        "build_tree_sha256_after": payload.get("proof_tree_sha256"),
                        "manifest_id": payload.get("manifest_id"),
                        "route_manifest_sha256": payload.get("manifest_sha256"),
                        "dossier_core_sha256": payload.get("dossier_core_sha256"),
                        "visible_decision_source_manifest": payload.get(
                            "visible_decision_source_manifest"
                        ),
                        "visible_decision_snapshot": payload.get(
                            "visible_decision_snapshot"
                        ),
                        "producer_script_sha256": payload.get("producer_script_sha256"),
                        "runtime_identity": payload.get("runtime_identity"),
                    }.items()
                ):
                    failures.append(
                        f"Prebuild authorization {file.name} immutable gate fields do not match its authorization."
                    )
                elif immutable_record.get("build_stable") is not True:
                    failures.append(
                        f"Prebuild authorization {file.name} immutable gate did not prove a stable tree."
                    )
                else:
                    for snapshot_field, expected_digest, core_only in (
                        ("manifest_snapshot", payload.get("manifest_sha256"), False),
                        ("dossier_snapshot", payload.get("dossier_core_sha256"), True),
                        (
                            "visible_decision_snapshot",
                            (
                                visible_binding.get("sha256")
                                if isinstance(visible_binding, dict)
                                else None
                            ),
                            False,
                        ),
                    ):
                        snapshot = immutable_record.get(snapshot_field)
                        snapshot_path = (
                            project / PurePosixPath(str(snapshot.get("path") or ""))
                        ).resolve() if isinstance(snapshot, dict) else Path()
                        snapshot_digest = (
                            dossier_core_sha256(snapshot_path)
                            if core_only and snapshot_path.is_file()
                            else file_sha256(snapshot_path)[1]
                            if snapshot_path.is_file()
                            else None
                        )
                        if (
                            not isinstance(snapshot, dict)
                            or set(snapshot) != {"path", "sha256"}
                            or snapshot_digest != expected_digest
                            or file_sha256(snapshot_path)[1] != snapshot.get("sha256")
                        ):
                            failures.append(
                                f"Prebuild authorization {file.name} {snapshot_field} bytes are missing or drifted."
                            )
                    evidence_ledger = immutable_record.get("evidence_hashes")
                    ledger_paths: set[str] = set()
                    if not isinstance(evidence_ledger, list):
                        failures.append(
                            f"Prebuild authorization {file.name} immutable gate has no evidence ledger."
                        )
                    else:
                        for evidence_entry in evidence_ledger:
                            relative = (
                                evidence_entry.get("path")
                                if isinstance(evidence_entry, dict)
                                else None
                            )
                            evidence_path = (
                                project / PurePosixPath(str(relative or ""))
                            ).resolve()
                            if (
                                not isinstance(relative, str)
                                or relative in ledger_paths
                                or not is_within(evidence_path, project.resolve())
                                or not evidence_path.is_file()
                                or file_sha256(evidence_path)[1]
                                != evidence_entry.get("sha256")
                            ):
                                failures.append(
                                    f"Prebuild authorization {file.name} immutable evidence ledger is missing or drifted."
                                )
                                break
                            ledger_paths.add(relative)
        predecessor = payload.get("previous_authorization")
        if index == 0:
            if predecessor is not None:
                failures.append("The first prebuild authorization must have no predecessor.")
        else:
            expected_relative = previous_path.relative_to(project).as_posix() if previous_path else ""
            if (
                not isinstance(predecessor, dict)
                or set(predecessor) != {"path", "sha256"}
                or predecessor.get("path") != expected_relative
                or predecessor.get("sha256") != previous_sha
            ):
                failures.append(f"Prebuild authorization {file.name} breaks the append-only predecessor chain.")
        previous_path, previous_sha = file, digest
        records.append((file, payload, digest))
    return failures, records


def load_prebuild_authorization(
    project: Path, authorization_path: Path
) -> tuple[list[str], dict[str, object] | None, str | None]:
    failures, records = prebuild_authorization_chain(project)
    resolved = authorization_path.resolve()
    match = next(
        ((payload, digest) for path, payload, digest in records if path.resolve() == resolved),
        None,
    )
    if match is None:
        failures.append("Selected prebuild authorization is not in the validated append-only chain.")
        return failures, None, None
    if records and records[-1][0].resolve() != resolved:
        failures.append("Final gate must cite the latest prebuild authorization predecessor.")
    return failures, match[0], match[1]


def canonical_json_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def served_content_identity_failures(
    identity: object,
    *,
    expected_routes: list[dict[str, object]],
    expected_viewports: list[dict[str, object]],
) -> list[str]:
    failures: list[str] = []
    if not isinstance(identity, dict) or set(identity) != {
        "algorithm",
        "probes",
        "reload_counts",
        "inconsistent_reloads",
        "sha256",
        "complete",
    }:
        return ["Served-content identity has an unsupported shape."]
    if identity.get("algorithm") != "sha256-response-bodies-v1":
        failures.append("Served-content identity uses an unsupported algorithm.")
    probes = identity.get("probes")
    if not isinstance(probes, list):
        return [*failures, "Served-content identity probes must be a list."]
    expected_cells = {
        (str(route.get("key")), str(viewport.get("name")))
        for route in expected_routes
        for viewport in expected_viewports
    }
    observed_cells: set[tuple[str, str]] = set()
    top_projection: list[dict[str, object]] = []
    canonical_probe_order = sorted(
        probes,
        key=lambda probe: (
            str(probe.get("route_key", "")) if isinstance(probe, dict) else "",
            str(probe.get("viewport", "")) if isinstance(probe, dict) else "",
        ),
    )
    if probes != canonical_probe_order:
        failures.append("Served-content probes are not canonically ordered.")
    for index, probe in enumerate(probes, start=1):
        label = f"Served-content probe {index}"
        if not isinstance(probe, dict) or set(probe) != {
            "route_key", "viewport", "requested_url", "final_url", "status",
            "document_sha256", "resources", "sha256",
        }:
            failures.append(f"{label} has an unsupported shape.")
            continue
        cell = (str(probe.get("route_key")), str(probe.get("viewport")))
        if cell in observed_cells:
            failures.append(f"{label} duplicates route/profile {cell[0]}/{cell[1]}.")
        observed_cells.add(cell)
        matching_route = next(
            (route for route in expected_routes if route.get("key") == cell[0]),
            None,
        )
        requested = probe.get("requested_url")
        final = probe.get("final_url")
        status = probe.get("status")
        if (
            matching_route is None
            or requested != matching_route.get("url")
            or final != requested
            or type(status) is not int
            or not 200 <= status < 300
        ):
            failures.append(
                f"{label} must bind the exact manifested URL with a 2xx non-redirect response."
            )
        if (
            not isinstance(probe.get("document_sha256"), str)
            or SHA256_HEX.fullmatch(probe["document_sha256"]) is None
        ):
            failures.append(f"{label} has invalid document_sha256.")
        resources = probe.get("resources")
        if not isinstance(resources, list):
            failures.append(f"{label} resources must be a list.")
            continue
        expected_order = sorted(
            resources,
            key=lambda item: (
                str(item.get("url", "")) if isinstance(item, dict) else "",
                item.get("status", -1) if isinstance(item, dict) else -1,
                str(item.get("sha256", "")) if isinstance(item, dict) else "",
                item.get("bytes", -1) if isinstance(item, dict) else -1,
            ),
        )
        if resources != expected_order:
            failures.append(f"{label} resources are not canonically sorted.")
        for resource in resources:
            if (
                not isinstance(resource, dict)
                or set(resource) != {"url", "status", "sha256", "bytes"}
                or not isinstance(resource.get("url"), str)
                or type(resource.get("status")) is not int
                or not 200 <= resource["status"] < 300
                or not isinstance(resource.get("sha256"), str)
                or SHA256_HEX.fullmatch(resource["sha256"]) is None
                or type(resource.get("bytes")) is not int
                or resource["bytes"] < 0
            ):
                failures.append(f"{label} contains an invalid or unreadable resource binding.")
                break
        projection = {
            "requested_url": requested,
            "final_url": final,
            "status": status,
            "document_sha256": probe.get("document_sha256"),
            "resources": resources,
        }
        if probe.get("sha256") != canonical_json_sha256(projection):
            failures.append(f"{label} hash does not match its canonical response-body projection.")
        top_projection.append(
            {"route_key": cell[0], "viewport": cell[1], "sha256": probe.get("sha256")}
        )
    if observed_cells != expected_cells:
        failures.append(
            "Served-content identity does not cover the exact active route/profile matrix."
        )
    reload_counts = identity.get("reload_counts")
    expected_reload_keys = {
        f"{route_key}/{viewport}" for route_key, viewport in expected_cells
    }
    if (
        not isinstance(reload_counts, dict)
        or set(reload_counts) != expected_reload_keys
        or any(type(count) is not int or count < 2 for count in reload_counts.values())
    ):
        failures.append(
            "Served-content reload_counts must prove at least two byte-identical "
            "loads for every active route/profile cell."
        )
    if identity.get("inconsistent_reloads") != [] or identity.get("complete") is not True:
        failures.append(
            "Served-content identity reports inconsistent response bytes across reloads."
        )
    top_projection.sort(key=lambda item: (str(item["route_key"]), str(item["viewport"])))
    if identity.get("sha256") != canonical_json_sha256(top_projection):
        failures.append("Served-content top hash does not match its canonical probes.")
    return failures


def census_runtime_failures(
    payload: object,
    *,
    expected_routes: list[dict[str, object]],
    expected_viewports: list[dict[str, object]],
    first_screen: bool,
    record_path: Path | None = None,
    project: Path | None = None,
) -> list[str]:
    """Reconcile build scope, inferred states, and interaction transfer cells."""

    failures: list[str] = []
    if not isinstance(payload, dict):
        return ["Component census must contain an object."]
    if project is None and record_path is not None:
        for ancestor in record_path.resolve().parents:
            if ancestor.name == ".design-dna":
                project = ancestor.parent
                break
    route_by_key = {
        str(route.get("key")): route
        for route in expected_routes
        if isinstance(route, dict)
    }
    viewport_by_name = {
        str(viewport.get("name")): viewport
        for viewport in expected_viewports
        if isinstance(viewport, dict)
    }
    expected_route_keys = list(route_by_key)
    if payload.get("route_filter") != expected_route_keys:
        failures.append("Component census route_filter is not the exact active manifest order.")
    if payload.get("first_screen_only") is not first_screen:
        failures.append("Component census phase/scope flag does not match the gate phase.")
    if payload.get("viewports") != expected_viewports:
        failures.append("Component census viewport definitions differ from the manifest.")
    expected_state_ids = sorted(
        {
            str(state.get("id"))
            for route in expected_routes
            for state in route.get("states", [])
            if isinstance(state, dict)
        }
    )
    if payload.get("state_ids") != expected_state_ids:
        failures.append("Component census state_ids differ from the manifest.")
    if payload.get("pass") is not True:
        failures.append("Component census did not pass.")
    if payload.get("unexpected_urls") != [] or payload.get("failed_states") != []:
        failures.append("Component census reports unmanifested routes or failed states.")

    expected_cells = {
        (route_key, viewport_name, str(state.get("id")))
        for route_key, route in route_by_key.items()
        for viewport_name in viewport_by_name
        for state in route.get("states", [])
        if isinstance(state, dict)
    }
    checks = payload.get("checks")
    check_by_cell: dict[tuple[str, str, str], dict[str, object]] = {}
    if not isinstance(checks, list):
        failures.append("Component census checks must be a list.")
        checks = []
    for index, check in enumerate(checks, start=1):
        if not isinstance(check, dict):
            failures.append(f"Component census check {index} is invalid.")
            continue
        cell = (
            str(check.get("route_key")),
            str(check.get("viewport")),
            str(check.get("state_id")),
        )
        if cell in check_by_cell:
            failures.append(f"Component census check {index} duplicates a route/profile/state cell.")
            continue
        check_by_cell[cell] = check
        route = route_by_key.get(cell[0])
        viewport = viewport_by_name.get(cell[1])
        state = next(
            (
                item for item in route.get("states", [])
                if isinstance(item, dict) and item.get("id") == cell[2]
            ),
            None,
        ) if isinstance(route, dict) else None
        if (
            route is None
            or viewport is None
            or state is None
            or check.get("url") != route.get("url")
            or check.get("mapped_reference_rank") != route.get("mapped_reference_rank")
            or check.get("mapped_reference_id") != route.get("mapped_reference_id")
            or check.get("mapped_reference_observation") != route.get("mapped_reference_observation")
            or check.get("mapped_reference_sha256") != route.get("mapped_reference_sha256")
            or check.get("width") != viewport.get("width")
            or check.get("height") != viewport.get("height")
            or check.get("state_kind") != state.get("kind")
            or check.get("state_trigger") != state.get("trigger")
            or check.get("mapped_reference_state_id")
            != state.get("mapped_reference_state_id")
        ):
            failures.append(f"Component census check {index} is not the exact manifested cell.")
        if (
            check.get("pass") is not True
            or type(check.get("attempted")) is not int
            or check.get("attempted", 0) < 1
            or check.get("covered") != check.get("attempted")
            or not isinstance(check.get("state_application"), dict)
            or check["state_application"].get("applied") is not True
            or not isinstance(check.get("scroll_traversal"), dict)
            or check["scroll_traversal"].get("complete") is not True
            or not isinstance(check.get("inspection"), list)
            or not check.get("inspection")
            or any(
                not isinstance(item, dict) or item.get("complete") is not True
                for item in check.get("inspection", [])
            )
        ):
            failures.append(f"Component census check {index} has incomplete state/scroll/DOM evidence.")
        decision_ids = check.get("visible_decision_ids")
        if (
            not isinstance(decision_ids, list)
            or decision_ids != sorted(set(decision_ids))
            or not all(isinstance(item, str) and item for item in decision_ids)
            or check.get("unsourced_visible_parts") != []
        ):
            failures.append(
                f"Component census check {index} has unsourced or invalid visible-decision coverage."
            )
    if set(check_by_cell) != expected_cells:
        failures.append("Component census does not cover the exact route/profile/state matrix.")

    scopes = payload.get("implementation_scope")
    expected_scope_cells = {
        (route_key, viewport_name)
        for route_key in route_by_key
        for viewport_name in viewport_by_name
    }
    observed_scope_cells: set[tuple[str, str]] = set()
    if not isinstance(scopes, list):
        failures.append("Component census implementation_scope must be a list.")
        scopes = []
    for index, scope in enumerate(scopes, start=1):
        if not isinstance(scope, dict):
            failures.append(f"Component census implementation scope {index} is invalid.")
            continue
        cell = (str(scope.get("route_key")), str(scope.get("viewport")))
        if cell in observed_scope_cells:
            failures.append(f"Component census implementation scope {index} duplicates a cell.")
        observed_scope_cells.add(cell)
        substantial = scope.get("substantial_regions")
        beyond = scope.get("beyond_first_screen_regions")
        if (
            cell not in expected_scope_cells
            or type(scope.get("document_height")) is not int
            or type(scope.get("viewport_height")) is not int
            or not isinstance(substantial, list)
            or not isinstance(beyond, list)
        ):
            failures.append(f"Component census implementation scope {index} is incomplete.")
            continue
        if first_screen and (
            scope.get("first_screen_scope_pass") is not True
            or scope["document_height"] > scope["viewport_height"]
            or len(substantial) != 1
            or beyond != []
        ):
            failures.append(
                f"Component census implementation scope {index} proves broad implementation existed before authorization."
            )
    if observed_scope_cells != expected_scope_cells:
        failures.append("Component census implementation scope misses active route/profile cells.")

    state_inventories = payload.get("state_inventories")
    inventory_cells: set[tuple[str, str]] = set()
    if not isinstance(state_inventories, list):
        failures.append("Component census inferred state inventories must be a list.")
        state_inventories = []
    for inventory in state_inventories:
        if not isinstance(inventory, dict):
            failures.append("Component census has an invalid inferred state inventory.")
            continue
        cell = (str(inventory.get("route_key")), str(inventory.get("viewport")))
        inventory_cells.add(cell)
        inferred = inventory.get("inferred")
        if (
            cell not in expected_scope_cells
            or inventory.get("complete") is not True
            or inventory.get("unreconciled") != []
            or not isinstance(inventory.get("discovery_scroll"), dict)
            or inventory["discovery_scroll"].get("complete") is not True
            or not isinstance(inferred, list)
            or any(
                not isinstance(item, dict)
                or not isinstance(item.get("reconciled_state_ids"), list)
                or not item.get("reconciled_state_ids")
                for item in inferred
            )
        ):
            failures.append(f"Component census inferred states do not reconcile for {cell[0]}/{cell[1]}.")
    if inventory_cells != expected_scope_cells:
        failures.append("Component census inferred state inventories miss active route/profile cells.")

    interaction = payload.get("interaction_inventory")
    if (
        not isinstance(interaction, dict)
        or set(interaction) != {
            "complete", "missing", "cells", "responsive_transformations",
            "inferred_components", "target_censuses",
        }
        or interaction.get("complete") is not True
        or interaction.get("missing") != []
        or interaction.get("inferred_components") != state_inventories
    ):
        failures.append("Component census interaction inventory is incomplete or detached from inferred states.")
        return failures
    frame_artifacts: set[tuple[str, int, str]] | None = None
    if record_path is not None:
        frame_failures, frame_bindings = generated_interaction_frame_bindings(
            payload, record_path=record_path
        )
        failures.extend(frame_failures)
        frame_artifacts = {
            (str(binding["relative"]), int(binding["bytes"]), str(binding["sha256"]))
            for binding in frame_bindings
        }
    target_censuses = interaction.get("target_censuses")
    target_census_cells: set[tuple[str, str]] = set()
    if not isinstance(target_censuses, list):
        failures.append("Component census generated target censuses must be a list.")
        target_censuses = []
    census_keys = {
        "profile", "pages", "page_states", "repeat_classes", "pointer_follow",
        "blocked_side_effects", "totals", "truncated", "missing", "complete",
    }
    for index, target_census in enumerate(target_censuses, start=1):
        if not isinstance(target_census, dict) or set(target_census) != {
            *census_keys, "route_key", "viewport"
        }:
            failures.append(f"Component target census {index} has an unsupported shape.")
            continue
        route_key = str(target_census.get("route_key"))
        viewport_name = str(target_census.get("viewport"))
        cell = (route_key, viewport_name)
        if cell in target_census_cells:
            failures.append(f"Component target census {index} duplicates a route/profile.")
        target_census_cells.add(cell)
        route = route_by_key.get(route_key)
        if route is None or viewport_name not in viewport_by_name:
            failures.append(f"Component target census {index} is not an active manifest cell.")
            continue
        core = {key: target_census.get(key) for key in census_keys}
        failures.extend(
            f"Component target census {index}: {failure}"
            for failure in interaction_census_failures(
                core,
                expected_profile=viewport_name,
                expected_state_ids={
                    str(state.get("id"))
                    for state in route.get("states", [])
                    if isinstance(state, dict)
                },
                expected_urls={str(route.get("url"))},
                artifact_root=record_path.parent if record_path is not None else None,
                allowed_artifacts=frame_artifacts,
            )
        )
    if target_census_cells != expected_scope_cells:
        failures.append("Component target censuses miss active route/profile cells.")
    interaction_cells = interaction.get("cells")
    interaction_by_cell: dict[tuple[str, str, str], dict[str, object]] = {}
    if not isinstance(interaction_cells, list):
        failures.append("Component census interaction cells must be a list.")
        interaction_cells = []
    for index, cell_record in enumerate(interaction_cells, start=1):
        if not isinstance(cell_record, dict):
            failures.append(f"Component census interaction cell {index} is invalid.")
            continue
        cell = (
            str(cell_record.get("route_key")),
            str(cell_record.get("viewport")),
            str(cell_record.get("state_id")),
        )
        if cell in interaction_by_cell:
            failures.append(f"Component census interaction cell {index} is duplicate.")
            continue
        interaction_by_cell[cell] = cell_record
        check = check_by_cell.get(cell)
        route = route_by_key.get(cell[0])
        state = next(
            (item for item in route.get("states", []) if isinstance(item, dict) and item.get("id") == cell[2]),
            None,
        ) if isinstance(route, dict) else None
        expected_mapping = {
            "rank": route.get("mapped_reference_rank") if isinstance(route, dict) else None,
            "id": route.get("mapped_reference_id") if isinstance(route, dict) else None,
            "observation": route.get("mapped_reference_observation") if isinstance(route, dict) else None,
            "sha256": route.get("mapped_reference_sha256") if isinstance(route, dict) else None,
            "state_id": state.get("mapped_reference_state_id") if isinstance(state, dict) else None,
        }
        evidence = cell_record.get("trigger_evidence")
        if (
            check is None
            or state is None
            or cell_record.get("mapped_reference_state_id")
            != state.get("mapped_reference_state_id")
            or cell_record.get("source_mapping") != expected_mapping
            or cell_record.get("trigger") != state.get("trigger")
            or cell_record.get("complete") is not True
            or cell_record.get("target_components_present") is not True
            or not isinstance(cell_record.get("target_components"), list)
            or not cell_record.get("target_components")
            or not isinstance(evidence, dict)
            or any(
                not isinstance(evidence.get(field), str)
                or SHA256_HEX.fullmatch(evidence[field]) is None
                for field in ("before_sha256", "after_sha256", "settled_sha256")
            )
            or evidence.get("type") != state.get("trigger", {}).get("type")
            or evidence.get("settled") is not True
        ):
            failures.append(
                f"Component census interaction cell {index} lacks exact mapped trigger/source/render evidence."
            )
    if set(interaction_by_cell) != expected_cells:
        failures.append("Component census interaction inventory misses route/profile/state cells.")
    transformations = interaction.get("responsive_transformations")
    expected_transformations = {
        (route_key, str(state.get("id")))
        for route_key, route in route_by_key.items()
        for state in route.get("states", [])
        if isinstance(state, dict)
    }
    observed_transformations: set[tuple[str, str]] = set()
    if not isinstance(transformations, list):
        failures.append("Component census responsive interaction transformations must be a list.")
        transformations = []
    for transformation in transformations:
        if not isinstance(transformation, dict):
            continue
        key = (str(transformation.get("route_key")), str(transformation.get("state_id")))
        observed_transformations.add(key)
        if (
            transformation.get("complete") is not True
            or not isinstance(transformation.get("wide"), dict)
            or not isinstance(transformation.get("narrow"), dict)
        ):
            failures.append(
                f"Component census responsive interaction {key[0]}/{key[1]} is incomplete."
            )
    if observed_transformations != expected_transformations:
        failures.append("Component census responsive interactions miss manifested route/state pairs.")

    rendered_qa = payload.get("rendered_qa")
    expected_qa_top = {
        "schema_version", "complete", "missing", "truncated", "cells",
        "presentation_ready", "presentation_blocker", "experience_paths",
    }
    if (
        not isinstance(rendered_qa, dict)
        or set(rendered_qa) != expected_qa_top
        or rendered_qa.get("schema_version") != 1
        or rendered_qa.get("complete") is not True
        or rendered_qa.get("missing") != []
        or rendered_qa.get("truncated") is not False
        or rendered_qa.get("presentation_ready") is not (not first_screen)
    ):
        failures.append("Component census rendered_qa is incomplete, truncated, or has the wrong phase readiness.")
        return failures
    if first_screen:
        if rendered_qa.get("presentation_ready") is not False or rendered_qa.get(
            "presentation_blocker"
        ) != "first-screen authorization is not post-build multi-route/site QA":
            failures.append("First-screen rendered QA must retain its explicit presentation blocker.")
    elif rendered_qa.get("presentation_ready") is not True or rendered_qa.get(
        "presentation_blocker"
    ) is not None:
        failures.append("Final rendered QA is not presentation-ready.")
    qa_cells = rendered_qa.get("cells")
    qa_by_cell: dict[tuple[str, str, str], dict[str, object]] = {}
    if not isinstance(qa_cells, list):
        failures.append("Component rendered QA cells must be a list.")
        qa_cells = []
    expected_qa_cell_keys = {
        "route_key", "viewport", "state_id", "clipping", "collisions",
        "fixed_rail_overlaps", "control_visibility",
        "responsive_control_parity", "hidden_controls", "dead_controls",
        "blocked_handoffs", "overlays", "keyboard", "reduced_motion",
        "deep_link", "reload", "dead_ends", "semantic_equivalence",
        "state_semantics", "public_copy", "accessibility", "experience_paths",
        "short_height", "missing", "truncated", "complete",
    }
    served = payload.get("served_content_identity")
    served_sha = served.get("sha256") if isinstance(served, dict) else None
    source_observations: dict[str, dict[str, object]] = {}
    if project is not None:
        for route_key, route in route_by_key.items():
            relative = route.get("mapped_reference_observation")
            if not isinstance(relative, str):
                failures.append(f"Component rendered QA route {route_key} has no source observation path.")
                continue
            observation_path = lexical_absolute(project / PurePosixPath(relative))
            if not is_within(observation_path, project.resolve()):
                failures.append(f"Component rendered QA route {route_key} source observation escapes the project.")
                continue
            try:
                assert_no_reparse_ancestors(observation_path, stop=project)
            except StateError as exc:
                failures.append(f"Component rendered QA route {route_key} source observation is linked/reparse: {exc}")
                continue
            try:
                observation = json.loads(observation_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                failures.append(f"Component rendered QA route {route_key} source observation is unreadable: {exc}")
                continue
            if (
                file_sha256(observation_path)[1]
                != route.get("mapped_reference_sha256")
                or not isinstance(observation, dict)
            ):
                failures.append(f"Component rendered QA route {route_key} source observation bytes drifted.")
                continue
            source_observations[route_key] = observation

    def source_semantic_keys(
        route_key: str, profile: str, mapped_state_id: str
    ) -> set[str]:
        observation = source_observations.get(route_key, {})
        census = observation.get("interaction_census_by_viewport", {}).get(profile)
        result: set[str] = set()
        if not isinstance(census, dict):
            return result
        for page in census.get("pages", []):
            if not isinstance(page, dict):
                continue
            for target in page.get("targets", []):
                if not isinstance(target, dict):
                    continue
                semantic_key = target.get("semantic_key")
                source_state_ids = target.get("source_state_ids")
                if (
                    isinstance(semantic_key, str)
                    and semantic_key
                    and isinstance(source_state_ids, list)
                    and (
                        not source_state_ids
                        or mapped_state_id in source_state_ids
                    )
                ):
                    result.add(semantic_key)
        return result

    def surface_qa_failures(surface: object, label: str) -> list[str]:
        local: list[str] = []
        if not isinstance(surface, dict):
            return [f"{label} is not an object."]
        state_semantics = surface.get("state_semantics")
        if (
            not isinstance(state_semantics, dict)
            or set(state_semantics) != {"required", "complete", "target", "attributes"}
            or type(state_semantics.get("required")) is not bool
            or state_semantics.get("complete") is not True
            or (
                state_semantics.get("required") is True
                and not isinstance(state_semantics.get("attributes"), dict)
            )
        ):
            local.append(f"{label} disclosure/toggle ARIA state semantics are incomplete.")
        public_copy = surface.get("public_copy")
        if (
            not isinstance(public_copy, dict)
            or set(public_copy) != {
                "visible_text", "findings", "contextual_review", "truncated",
                "complete", "evidence",
            }
            or not isinstance(public_copy.get("visible_text"), list)
            or public_copy.get("findings") != []
            or not isinstance(public_copy.get("contextual_review"), list)
            or public_copy.get("truncated") is not False
            or public_copy.get("complete") is not True
            or not isinstance(public_copy.get("evidence"), dict)
        ):
            local.append(f"{label} contains scaffold, prototype, fallback, or builder-facing public copy.")
        accessibility = surface.get("accessibility")
        if (
            not isinstance(accessibility, dict)
            or set(accessibility) != {
                "headings", "landmarks", "focus_indicators", "missing",
                "truncated", "complete",
            }
            or accessibility.get("missing") != []
            or accessibility.get("truncated") is not False
            or accessibility.get("complete") is not True
            or not isinstance(accessibility.get("headings"), list)
            or not any(
                isinstance(heading, dict) and heading.get("level") == 1
                for heading in accessibility.get("headings", [])
            )
            or not isinstance(accessibility.get("landmarks"), list)
            or len([
                landmark for landmark in accessibility.get("landmarks", [])
                if isinstance(landmark, dict) and landmark.get("visible") is True
                and (landmark.get("tag") == "main" or landmark.get("role") == "main")
            ]) != 1
            or not isinstance(accessibility.get("focus_indicators"), list)
            or any(
                not isinstance(indicator, dict)
                or indicator.get("complete") is not True
                or indicator.get("active") is not True
                or indicator.get("visible_indicator") is not True
                or not isinstance(indicator.get("evidence"), dict)
                for indicator in accessibility.get("focus_indicators", [])
            )
        ):
            local.append(f"{label} heading/landmark/visible-focus accessibility evidence is incomplete.")
        return local

    for index, qa_cell in enumerate(qa_cells, start=1):
        if not isinstance(qa_cell, dict) or set(qa_cell) != expected_qa_cell_keys:
            failures.append(f"Component rendered QA cell {index} has an unsupported shape.")
            continue
        cell = (
            str(qa_cell.get("route_key")),
            str(qa_cell.get("viewport")),
            str(qa_cell.get("state_id")),
        )
        if cell in qa_by_cell:
            failures.append(f"Component rendered QA cell {index} duplicates a manifest cell.")
            continue
        qa_by_cell[cell] = qa_cell
        route = route_by_key.get(cell[0])
        control_visibility = qa_cell.get("control_visibility")
        if (
            not isinstance(control_visibility, list)
            or any(
                not isinstance(control, dict)
                or set(control) != {
                    "key", "semantic_key", "text", "role", "visible",
                    "focusable", "aria_hidden", "tag", "display",
                    "visibility", "opacity", "rendered_box", "tab_index",
                }
                or not isinstance(control.get("key"), str)
                or not control["key"]
                or not isinstance(control.get("semantic_key"), str)
                or not control["semantic_key"]
                or type(control.get("visible")) is not bool
                or type(control.get("focusable")) is not bool
                or type(control.get("rendered_box")) is not bool
                or type(control.get("tab_index")) is not int
                for control in control_visibility or []
            )
        ):
            failures.append(
                f"Component rendered QA cell {index} has an invalid generated control-visibility inventory."
            )
        if (
            cell not in expected_cells
            or check_by_cell.get(cell, {}).get("rendered_qa") != qa_cell
            or any(
                qa_cell.get(field) != []
                for field in (
                    "clipping", "collisions", "fixed_rail_overlaps",
                    "hidden_controls", "dead_controls", "blocked_handoffs",
                    "dead_ends", "missing",
                )
            )
            or qa_cell.get("truncated") is not False
            or qa_cell.get("complete") is not True
        ):
            failures.append(
                f"Component rendered QA cell {index} contains clipping, overlap, hidden/dead control, blocked path, or dead-end findings."
            )
        failures.extend(surface_qa_failures(qa_cell, f"Component rendered QA cell {index}"))
        overlays = qa_cell.get("overlays")
        if (
            not isinstance(overlays, dict)
            or set(overlays) != {
                "records", "inert_background", "closed_descendants_inert",
                "stacking", "initial_focus", "background_focus_blocked",
                "focus_trap", "focus_return"
            }
            or overlays.get("inert_background") is not True
            or overlays.get("closed_descendants_inert") is not True
            or overlays.get("stacking") is not True
            or overlays.get("initial_focus") is not True
            or overlays.get("background_focus_blocked") is not True
            or overlays.get("focus_trap") is not True
            or overlays.get("focus_return") is not True
            or not isinstance(overlays.get("records"), list)
            or any(
                not isinstance(row, dict)
                or row.get("inert_background") is not True
                or row.get("closed_descendants_inert") is not True
                or row.get("stacking_above_background_controls") is not True
                or row.get("initial_focus") is not True
                or row.get("background_focus_blocked") is not True
                or row.get("focus_trap") is not True
                or row.get("focus_return") is not True
                or row.get("escape_closes") is not True
                or not isinstance(row.get("evidence"), dict)
                for row in overlays.get("records", [])
            )
        ):
            failures.append(f"Component rendered QA cell {index} overlay inert/focus/escape evidence failed.")
        keyboard = qa_cell.get("keyboard")
        semantic = qa_cell.get("semantic_equivalence")
        if keyboard != {"complete": True, "missing": []}:
            failures.append(f"Component rendered QA cell {index} keyboard paths are incomplete.")
        if semantic != {"complete": True, "mismatches": []}:
            failures.append(f"Component rendered QA cell {index} repeated controls are not semantically equivalent.")
        reduced = qa_cell.get("reduced_motion")
        if (
            not isinstance(reduced, dict)
            or reduced.get("complete") is not True
            or reduced.get("violations") != []
            or not isinstance(reduced.get("evidence"), dict)
        ):
            failures.append(f"Component rendered QA cell {index} reduced-motion evidence is incomplete.")
        deep = qa_cell.get("deep_link")
        reload = qa_cell.get("reload")
        if (
            not isinstance(deep, dict)
            or deep.get("complete") is not True
            or not isinstance(route, dict)
            or deep.get("requested_url") != route.get("url")
            or deep.get("final_urls") != [route.get("url")]
        ):
            failures.append(f"Component rendered QA cell {index} deep-link evidence is incomplete.")
        if (
            not isinstance(reload, dict)
            or reload.get("complete") is not True
            or type(reload.get("count")) is not int
            or reload.get("count", 0) < 2
            or reload.get("served_content_sha256") != served_sha
        ):
            failures.append(f"Component rendered QA cell {index} reload evidence is incomplete.")
        short = qa_cell.get("short_height")
        expected_short_keys = {
            "profile", "width", "height", "clipping", "collisions",
            "fixed_rail_overlaps", "control_visibility", "overlays",
            "state_semantics", "public_copy", "accessibility", "viewport",
            "truncated", "reduced_motion",
        }
        expected_short_height = min(int(viewport_by_name.get(cell[1], {}).get("height") or 0), 568)
        if (
            not isinstance(short, dict)
            or set(short) != expected_short_keys
            or short.get("profile") != f"{cell[1]}-short"
            or short.get("width") != viewport_by_name.get(cell[1], {}).get("width")
            or short.get("height") != expected_short_height
            or short.get("viewport") != {
                "width": viewport_by_name.get(cell[1], {}).get("width"),
                "height": expected_short_height,
            }
            or short.get("clipping") != []
            or short.get("collisions") != []
            or short.get("fixed_rail_overlaps") != []
            or short.get("truncated") is not False
            or not isinstance(short.get("control_visibility"), list)
        ):
            failures.append(
                f"Component rendered QA cell {index} short-height geometry/control evidence is incomplete."
            )
        else:
            failures.extend(
                surface_qa_failures(
                    short, f"Component rendered QA cell {index} short-height"
                )
            )
            short_overlays = short.get("overlays")
            if (
                not isinstance(short_overlays, dict)
                or set(short_overlays) != {
                    "records", "inert_background", "closed_descendants_inert",
                    "stacking", "initial_focus", "background_focus_blocked",
                    "focus_trap", "focus_return",
                }
                or any(
                    short_overlays.get(field) is not True
                    for field in (
                        "inert_background", "closed_descendants_inert", "stacking",
                        "initial_focus", "background_focus_blocked",
                        "focus_trap", "focus_return",
                    )
                )
                or not isinstance(short_overlays.get("records"), list)
                or any(
                    not isinstance(row, dict)
                    or row.get("inert_background") is not True
                    or row.get("closed_descendants_inert") is not True
                    or row.get("stacking_above_background_controls") is not True
                    or row.get("initial_focus") is not True
                    or row.get("background_focus_blocked") is not True
                    or row.get("focus_trap") is not True
                    or row.get("focus_return") is not True
                    or row.get("escape_closes") is not True
                    or not isinstance(row.get("evidence"), dict)
                    for row in short_overlays.get("records", [])
                )
            ):
                failures.append(
                    f"Component rendered QA cell {index} short-height overlay inert/focus evidence failed."
                )
            short_reduced = short.get("reduced_motion")
            if (
                not isinstance(short_reduced, dict)
                or short_reduced.get("complete") is not True
                or short_reduced.get("violations") != []
                or not isinstance(short_reduced.get("evidence"), dict)
            ):
                failures.append(
                    f"Component rendered QA cell {index} short-height reduced-motion evidence is incomplete."
                )
    controls_by_route_state: dict[tuple[str, str], dict[str, dict[str, object]]] = {}
    for (route_key, _viewport_name, state_id), qa_cell in qa_by_cell.items():
        records = controls_by_route_state.setdefault((route_key, state_id), {})
        for control in qa_cell.get("control_visibility", []):
            if not isinstance(control, dict) or not isinstance(control.get("key"), str):
                continue
            prior = records.get(control["key"])
            if prior is not None and prior.get("semantic_key") != control.get("semantic_key"):
                failures.append(
                    f"Component rendered QA control {control['key']} changes semantic identity across profiles."
                )
            records[control["key"]] = control
    for cell, qa_cell in qa_by_cell.items():
        route_key, viewport_name, state_id = cell
        route = route_by_key.get(route_key, {})
        viewport = viewport_by_name.get(viewport_name, {})
        state = next(
            (
                item for item in route.get("states", [])
                if isinstance(item, dict) and item.get("id") == state_id
            ),
            {},
        ) if isinstance(route, dict) else {}
        mapped_state_id = str(state.get("mapped_reference_state_id") or "")
        source_profile = "narrow" if int(viewport.get("width") or 0) <= 430 else "wide"
        opposite_profile = "wide" if source_profile == "narrow" else "narrow"
        current_controls = [
            control for control in qa_cell.get("control_visibility", [])
            if isinstance(control, dict)
        ]
        current_by_key = {
            str(control.get("key")): control for control in current_controls
        }
        visible_keys = {
            str(control.get("key")) for control in current_controls
            if control.get("visible") is True
        }
        visible_semantics = {
            str(control.get("semantic_key")) for control in current_controls
            if control.get("visible") is True
        }
        cross_profile_hidden: list[dict[str, object]] = []
        for control in controls_by_route_state.get((route_key, state_id), {}).values():
            key = str(control.get("key"))
            semantic_key = str(control.get("semantic_key") or "")
            if key in visible_keys or semantic_key in visible_semantics:
                continue
            cross_profile_hidden.append({
                "target": key,
                "semantic_key": semantic_key,
                "reason": (
                    "control-hidden-in-every-declared-state-for-required-profile"
                    if key in current_by_key
                    else "control-absent-without-responsive-equivalent"
                ),
            })
        source_current = source_semantic_keys(
            route_key, source_profile, mapped_state_id
        )
        source_opposite = source_semantic_keys(
            route_key, opposite_profile, mapped_state_id
        )
        authorized = source_opposite - source_current
        expected_findings = [
            {
                **candidate,
                "source_profile": source_profile,
                "mapped_reference_state_id": mapped_state_id,
                "source_authorized_omission": False,
            }
            for candidate in cross_profile_hidden
            if candidate["semantic_key"] not in authorized
        ]
        parity = qa_cell.get("responsive_control_parity")
        expected_parity = {
            "source_profile": source_profile,
            "mapped_reference_state_id": mapped_state_id,
            "source_current_semantic_keys": sorted(source_current),
            "source_opposite_semantic_keys": sorted(source_opposite),
            "source_authorized_omissions": sorted(authorized),
            "build_visible_semantic_keys": sorted(visible_semantics),
            "findings": expected_findings,
            "complete": not expected_findings,
        }
        if parity != expected_parity or expected_findings:
            failures.append(
                f"Component rendered QA {route_key}/{viewport_name}/{state_id} does not preserve exact source-bound responsive control parity."
            )
    experience_summary = rendered_qa.get("experience_paths")
    expected_experience_keys: set[tuple[str, str, str]] = set()
    for target_census in target_censuses:
        if not isinstance(target_census, dict):
            continue
        route_key = str(target_census.get("route_key"))
        viewport_name = str(target_census.get("viewport"))
        for page in target_census.get("pages", []):
            if not isinstance(page, dict):
                continue
            for target in page.get("targets", []):
                if isinstance(target, dict) and isinstance(target.get("target_id"), str):
                    expected_experience_keys.add(
                        (route_key, viewport_name, target["target_id"])
                    )
    experience_by_key: dict[tuple[str, str, str], dict[str, object]] = {}
    if (
        not isinstance(experience_summary, dict)
        or set(experience_summary) != {
            "complete", "missing", "truncated", "totals", "paths"
        }
        or experience_summary.get("complete") is not True
        or experience_summary.get("missing") != []
        or experience_summary.get("truncated") is not False
        or not isinstance(experience_summary.get("paths"), list)
    ):
        failures.append("Component rendered QA experience-path ledger is incomplete or unsupported.")
    else:
        for path_index, path_record in enumerate(
            experience_summary.get("paths", []), start=1
        ):
            if (
                not isinstance(path_record, dict)
                or set(path_record) != {
                    "route_key", "viewport", "target_id", "kind", "actions",
                    "missing", "complete",
                }
            ):
                failures.append(f"Component experience path {path_index} has an unsupported shape.")
                continue
            key = (
                str(path_record.get("route_key")),
                str(path_record.get("viewport")),
                str(path_record.get("target_id")),
            )
            if key in experience_by_key:
                failures.append(f"Component experience path {path_index} duplicates a target/profile.")
                continue
            experience_by_key[key] = path_record
            actions = path_record.get("actions")
            if (
                path_record.get("complete") is not True
                or path_record.get("missing") != []
                or not isinstance(actions, list)
                or not actions
                or any(
                    not isinstance(action, dict)
                    or set(action) != {
                        "input_kind", "status", "resolution",
                        "manifested_state_id", "final_url", "evidence",
                    }
                    for action in actions or []
                )
                or not any(
                    isinstance(action, dict)
                    and action.get("resolution")
                    in {"manifested-route", "manifested-state", "blocked-handoff"}
                    for action in actions or []
                )
            ):
                failures.append(f"Component experience path {path_index} has no resolved generated action.")
                continue
            route = route_by_key.get(key[0], {})
            route_urls = {
                str(item.get("url")) for item in route_by_key.values()
                if isinstance(item, dict)
            }
            route_states = {
                str(item.get("id")) for item in route.get("states", [])
                if isinstance(item, dict)
            } if isinstance(route, dict) else set()
            for action in actions:
                if action.get("resolution") == "manifested-route" and action.get("final_url") not in route_urls:
                    failures.append(f"Component experience path {path_index} resolves to an unmanifested route.")
                if action.get("resolution") == "manifested-state" and action.get("manifested_state_id") not in route_states:
                    failures.append(f"Component experience path {path_index} resolves to an unmanifested state.")
                if action.get("resolution") == "blocked-handoff" and action.get("status") != "blocked":
                    failures.append(f"Component experience path {path_index} mislabels an exercised action as blocked.")
        if set(experience_by_key) != expected_experience_keys:
            failures.append("Component experience paths do not cover every discovered target/profile.")
        totals = experience_summary.get("totals")
        if (
            not isinstance(totals, dict)
            or set(totals) != {"targets", "resolved", "blocked_handoffs"}
            or totals.get("targets") != len(experience_by_key)
            or totals.get("resolved") != len(experience_by_key)
            or totals.get("blocked_handoffs") != len([
                record for record in experience_by_key.values()
                if any(
                    isinstance(action, dict)
                    and action.get("resolution") == "blocked-handoff"
                    for action in record.get("actions", [])
                )
            ])
        ):
            failures.append("Component experience-path totals do not reconcile its exact ledger.")
        for cell, qa_cell in qa_by_cell.items():
            expected_paths = [
                record for key, record in experience_by_key.items()
                if key[:2] == cell[:2]
            ]
            if qa_cell.get("experience_paths") != expected_paths:
                failures.append(
                    f"Component rendered QA {cell[0]}/{cell[1]}/{cell[2]} detaches its target experience paths."
                )
    if set(qa_by_cell) != expected_cells:
        failures.append("Component rendered QA does not cover the exact route/profile/state matrix.")
    reconciliation = payload.get("visible_decision_reconciliation")
    decision_manifest_path = (
        project / ".design-dna" / "visible-decision-sources.json"
        if project is not None
        else None
    )
    decision_manifest: object = None
    decision_manifest_sha: str | None = None
    if decision_manifest_path is not None:
        try:
            decision_manifest = json.loads(
                decision_manifest_path.read_text(encoding="utf-8")
            )
            decision_manifest_sha = file_sha256(decision_manifest_path)[1]
        except (OSError, ValueError) as exc:
            failures.append(
                f"Component census visible-decision source manifest is unreadable: {exc}"
            )
    expected_reconciliation_keys = {
        "manifest_path", "manifest_sha256", "implemented_decision_ids",
        "missing_decision_ids", "unsourced_visible_decisions",
        "scaffold_findings", "fallback_findings", "placeholder_findings",
        "complete",
    }
    if (
        not isinstance(reconciliation, dict)
        or set(reconciliation) != expected_reconciliation_keys
        or reconciliation.get("manifest_path")
        != ".design-dna/visible-decision-sources.json"
        or reconciliation.get("manifest_sha256") != decision_manifest_sha
        or reconciliation.get("missing_decision_ids") != []
        or reconciliation.get("unsourced_visible_decisions") != []
        or reconciliation.get("scaffold_findings") != []
        or reconciliation.get("fallback_findings") != []
        or reconciliation.get("placeholder_findings") != []
        or reconciliation.get("complete") is not True
    ):
        failures.append(
            "Component census visible-decision reconciliation is incomplete, stale, or contains scaffold/fallback/placeholder output."
        )
    if isinstance(decision_manifest, dict):
        planned_ids = decision_manifest.get("planned_decision_ids")
        decisions = decision_manifest.get("decisions")
        implemented = sorted({
            decision_id
            for check in check_by_cell.values()
            for decision_id in check.get("visible_decision_ids", [])
            if isinstance(decision_id, str)
        })
        if (
            not isinstance(planned_ids, list)
            or not isinstance(decisions, list)
            or reconciliation.get("implemented_decision_ids") != implemented
            or any(decision_id not in planned_ids for decision_id in implemented)
        ):
            failures.append(
                "Component census implemented decision IDs do not reconcile the bound source manifest."
            )
        else:
            for decision in decisions:
                if not isinstance(decision, dict):
                    failures.append("Component census source decision row is invalid.")
                    continue
                decision_id = decision.get("decision_id")
                route_keys = decision.get("route_keys")
                state_ids = decision.get("state_ids")
                if (
                    not isinstance(decision_id, str)
                    or not isinstance(route_keys, list)
                    or not isinstance(state_ids, list)
                ):
                    failures.append("Component census source decision mapping is invalid.")
                    continue
                for cell, check in check_by_cell.items():
                    if cell[0] in route_keys and cell[2] in state_ids and decision_id not in check.get("visible_decision_ids", []):
                        failures.append(
                            f"Component census {cell[0]}/{cell[1]}/{cell[2]} omits planned visible decision {decision_id}."
                        )
    return failures


def generated_interaction_frame_bindings(
    payload: object,
    *,
    record_path: Path,
) -> tuple[list[str], list[dict[str, object]]]:
    """Reconcile every persisted interaction PNG with generated JSON metadata."""

    if not isinstance(payload, dict):
        return ["Interaction-frame record must contain an object."], []
    relative_root = payload.get("interaction_frame_directory")
    expected_root_name = f"{record_path.stem}-interaction-frames"
    if (
        not isinstance(relative_root, str)
        or relative_root != expected_root_name
        or PurePosixPath(relative_root).is_absolute()
        or ".." in PurePosixPath(relative_root).parts
    ):
        return ["Interaction-frame directory is missing or not derived from the canonical record path."], []
    root = lexical_absolute(record_path.parent / PurePosixPath(relative_root))
    try:
        assert_no_reparse_ancestors(root, stop=record_path.parent)
        assert_safe_tree(root)
    except StateError as exc:
        return [f"Interaction-frame directory contains a link/reparse point: {exc}"], []
    if (
        not is_within(root, lexical_absolute(record_path.parent))
        or not root.is_dir()
        or is_reparse(root)
    ):
        return ["Interaction-frame directory is missing, linked, or escapes the evidence root."], []
    referenced: dict[str, tuple[int, str]] = {}
    failures: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            relative = value.get("file")
            if (
                isinstance(relative, str)
                and relative.startswith(relative_root + "/")
            ):
                size = value.get("bytes")
                digest = value.get("sha256")
                if (
                    type(size) is not int
                    or size < 1
                    or not isinstance(digest, str)
                    or SHA256_HEX.fullmatch(digest) is None
                ):
                    failures.append(f"Interaction frame metadata is invalid: {relative}.")
                elif relative in referenced and referenced[relative] != (size, digest):
                    failures.append(f"Interaction frame has conflicting metadata: {relative}.")
                else:
                    referenced[relative] = (size, digest)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    actual_files = sorted(
        (
            file
            for file in root.rglob("*")
            if file.is_file() and not is_reparse(file)
        ),
        key=lambda file: file.as_posix(),
    )
    actual_relatives = {
        file.relative_to(record_path.parent).as_posix() for file in actual_files
    }
    if not referenced:
        failures.append("Interaction record references no persisted before/after/settled frames.")
    if actual_relatives != set(referenced):
        failures.append("Interaction-frame directory is not the exact referenced PNG set.")
    bindings: list[dict[str, object]] = []
    for file in actual_files:
        relative = file.relative_to(record_path.parent).as_posix()
        expected = referenced.get(relative)
        if (
            file.suffix.casefold() != ".png"
            or expected is None
            or file.stat().st_size != expected[0]
            or file_sha256(file)[1] != expected[1]
        ):
            failures.append(f"Interaction frame bytes are invalid or drifted: {relative}.")
            continue
        try:
            verify_png_artifact(file)
        except StateError as exc:
            failures.append(f"Interaction frame is not a valid PNG ({relative}): {exc}")
            continue
        bindings.append({"file": file, "relative": relative, "bytes": expected[0], "sha256": expected[1]})
    return failures, bindings


def recompute_interaction_transfer(
    build: object,
    source: object,
    states: list[dict[str, object]],
) -> dict[str, object]:
    """Python mirror of compare_mechanisms.diffInteractionCensus."""

    failures: list[str] = []
    if any(
        not isinstance(census, dict)
        or census.get("complete") is not True
        or census.get("truncated") is not False
        or census.get("missing") != []
        for census in (build, source)
    ):
        return {
            "pass": False,
            "failures": [
                "build/source interaction census is incomplete, truncated, or has missing targets"
            ],
            "target_transfers": [],
        }
    assert isinstance(build, dict) and isinstance(source, dict)
    source_to_build = {
        str(state.get("mapped_reference_state_id")): state.get("id")
        for state in states
    }

    def flatten(census: dict[str, object], source_side: bool) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for page in census.get("pages", []):
            if not isinstance(page, dict):
                continue
            for target in page.get("targets", []):
                if not isinstance(target, dict):
                    continue
                for input_record in target.get("inputs", []):
                    if (
                        not isinstance(input_record, dict)
                        or input_record.get("status") != "exercised"
                    ):
                        continue
                    state_id = input_record.get("source_state_id")
                    mapped_state = (
                        source_to_build.get(str(state_id), f"unmapped:{state_id}")
                        if source_side and state_id is not None
                        else state_id
                    )
                    signature = {
                        "input_kind": input_record.get("input_kind"),
                        "input_value": (
                            None
                            if mapped_state is not None
                            or input_record.get("input_kind") == "navigation"
                            else input_record.get("input_value")
                        ),
                        "state_id": mapped_state,
                        "changed_properties": [
                            {
                                "property": change.get("property"),
                                "before": change.get("before"),
                                "after": change.get("after"),
                            }
                            for change in input_record.get("changed_properties", [])
                            if isinstance(change, dict)
                        ],
                        "changed": input_record.get("before_sha256")
                        != input_record.get("settled_sha256"),
                        "disposition": input_record.get("disposition"),
                    }
                    component_keys = sorted([
                        *[
                            "class:" + quote(str(value), safe="-_.!~*'()")
                            for value in target.get("class_signature", [])
                        ],
                        *(
                            ["tag:" + str(target.get("tag"))]
                            if target.get("tag")
                            else []
                        ),
                        *(
                            [
                                "role:"
                                + quote(
                                    str(target.get("role")).casefold(),
                                    safe="-_.!~*'()",
                                )
                            ]
                            if target.get("role")
                            else []
                        ),
                    ])
                    canonical = json.dumps(
                        signature,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    )
                    rows.append(
                        {
                            "target_id": target.get("target_id"),
                            "repeat_class": target.get("repeat_class"),
                            "component_keys": component_keys,
                            "repeat_index": target.get("repeat_index"),
                            "signature": signature,
                            "canonical": canonical,
                        }
                    )
        rows.sort(key=lambda row: (str(row["canonical"]), str(row["target_id"])))
        return rows

    build_rows = flatten(build, False)
    source_rows = flatten(source, True)
    build_targets = int(build.get("totals", {}).get("targets_discovered", 0))
    source_targets = int(source.get("totals", {}).get("targets_discovered", 0))
    if build_targets != source_targets:
        failures.append(
            f"interaction target count {build_targets} vs source {source_targets}"
        )
    if len(build_rows) != len(source_rows):
        failures.append(
            f"exercised input count {len(build_rows)} vs source {len(source_rows)}"
        )
    transfers: list[dict[str, object]] = []
    for index in range(max(len(build_rows), len(source_rows))):
        build_row = build_rows[index] if index < len(build_rows) else None
        source_row = source_rows[index] if index < len(source_rows) else None
        if (
            build_row is None
            or source_row is None
            or build_row["canonical"] != source_row["canonical"]
        ):
            failures.append(
                f"interaction behavior row {index + 1} does not exactly match its source trigger/state/property sequence"
            )
            continue
        transfers.append(
            {
                "source_target_id": source_row["target_id"],
                "build_target_id": build_row["target_id"],
                "source_component_keys": source_row["component_keys"],
                "build_component_keys": build_row["component_keys"],
                "input_kind": build_row["signature"]["input_kind"],
                "build_state_id": build_row["signature"]["state_id"],
                "behavior_signature": build_row["signature"],
                "complete": True,
            }
        )
    source_pointers = source.get("pointer_follow", [])
    build_pointers = build.get("pointer_follow", [])
    if len(source_pointers) != len(build_pointers):
        failures.append(
            f"pointer-follow target count {len(build_pointers)} vs source {len(source_pointers)}"
        )
    for index, (build_pointer, source_pointer) in enumerate(
        zip(build_pointers, source_pointers),
        start=1,
    ):
        def relative_delta(left: object, right: object) -> float:
            return abs(float(left or 0) - float(right or 0)) / max(
                abs(float(right or 0)), 1
            )

        if (
            not isinstance(build_pointer, dict)
            or not isinstance(source_pointer, dict)
            or build_pointer.get("distinct_from_hover") is not True
            or source_pointer.get("distinct_from_hover") is not True
            or relative_delta(
                build_pointer.get("moved_px"), source_pointer.get("moved_px")
            ) > 0.25
            or float(build_pointer.get("return_error_px") or 0)
            > max(8, float(build_pointer.get("moved_px") or 0) * 0.3)
        ):
            failures.append(
                f"pointer-follow row {index} is hover-like or differs in movement/return magnitude"
            )
    return {
        "pass": not failures,
        "failures": failures,
        "build_targets": build_targets,
        "source_targets": source_targets,
        "target_transfers": transfers,
        "verdict": (
            "; ".join(failures)
            if failures
            else "Every live interaction target/input/state/frame sequence matches the exact source interaction census."
        ),
    }


def mechanism_interaction_transfer_failures(
    payload: object,
    *,
    project: Path,
    expected_routes: list[dict[str, object]],
    expected_viewports: list[dict[str, object]],
    first_screen: bool,
    record_path: Path,
) -> list[str]:
    """Validate exact source-to-build interaction transfer for every cell."""

    failures: list[str] = []
    if not isinstance(payload, dict):
        return ["Mechanism transfer record must contain an object."]
    route_by_key = {
        str(route.get("key")): route for route in expected_routes
        if isinstance(route, dict)
    }
    viewport_by_name = {
        str(viewport.get("name")): viewport for viewport in expected_viewports
        if isinstance(viewport, dict)
    }
    if payload.get("route_filter") != list(route_by_key):
        failures.append("Mechanism route_filter is not the exact active manifest order.")
    if payload.get("first_screen_only") is not first_screen:
        failures.append("Mechanism first-screen scope differs from the gate phase.")
    frame_failures, frame_bindings = generated_interaction_frame_bindings(
        payload, record_path=record_path
    )
    failures.extend(frame_failures)
    frame_artifacts = {
        (str(binding["relative"]), int(binding["bytes"]), str(binding["sha256"]))
        for binding in frame_bindings
    }
    expected_cells = {
        (route_key, viewport_name, str(state.get("id")))
        for route_key, route in route_by_key.items()
        for viewport_name in viewport_by_name
        for state in route.get("states", [])
        if isinstance(state, dict)
    }
    checks = payload.get("checks")
    transfer = payload.get("interaction_transfer")
    if (
        not isinstance(transfer, dict)
        or set(transfer) != {
            "complete", "missing", "cells", "responsive_transformations"
        }
        or transfer.get("complete") is not True
        or transfer.get("missing") != []
        or transfer.get("cells") != checks
    ):
        failures.append("Mechanism interaction_transfer is incomplete or detached from checks.")
        return failures
    observed_cells: set[tuple[str, str, str]] = set()
    if not isinstance(checks, list):
        failures.append("Mechanism checks must be a list.")
        checks = []
    observation_cache: dict[str, dict[str, object]] = {}
    for index, check in enumerate(checks, start=1):
        if not isinstance(check, dict):
            failures.append(f"Mechanism interaction check {index} is invalid.")
            continue
        cell = (
            str(check.get("route_key")),
            str(check.get("viewport")),
            str(check.get("state_id")),
        )
        if cell in observed_cells:
            failures.append(f"Mechanism interaction check {index} duplicates a cell.")
        observed_cells.add(cell)
        route = route_by_key.get(cell[0])
        viewport = viewport_by_name.get(cell[1])
        state = next(
            (item for item in route.get("states", []) if isinstance(item, dict) and item.get("id") == cell[2]),
            None,
        ) if isinstance(route, dict) else None
        expected_mapping = {
            "rank": route.get("mapped_reference_rank") if isinstance(route, dict) else None,
            "id": route.get("mapped_reference_id") if isinstance(route, dict) else None,
            "observation": route.get("mapped_reference_observation") if isinstance(route, dict) else None,
            "sha256": route.get("mapped_reference_sha256") if isinstance(route, dict) else None,
            "state_id": state.get("mapped_reference_state_id") if isinstance(state, dict) else None,
        }
        if (
            route is None
            or viewport is None
            or state is None
            or check.get("url") != route.get("url")
            or check.get("width") != viewport.get("width")
            or check.get("height") != viewport.get("height")
            or check.get("state_kind") != state.get("kind")
            or check.get("state_trigger") != state.get("trigger")
            or check.get("state_expectation") != state.get("expectation")
            or check.get("mapped_reference_state_id")
            != state.get("mapped_reference_state_id")
            or check.get("source_mapping") != expected_mapping
            or check.get("mapped_reference") != {
                "rank": expected_mapping["rank"],
                "id": expected_mapping["id"],
                "observation": expected_mapping["observation"],
                "sha256": expected_mapping["sha256"],
                "url": check.get("mapped_reference", {}).get("url")
                if isinstance(check.get("mapped_reference"), dict) else None,
            }
            or check.get("pass") is not True
            or check.get("state_contract_match") is not True
            or not isinstance(check.get("trigger_diff"), dict)
            or check["trigger_diff"].get("pass") is not True
            or not isinstance(check.get("interaction_diff"), dict)
            or check["interaction_diff"].get("pass") is not True
            or check["interaction_diff"].get("failures") != []
        ):
            failures.append(f"Mechanism interaction check {index} is not an exact passing mapped cell.")
        build_census = check.get("build_interaction_census")
        failures.extend(
            f"Mechanism interaction check {index}: {failure}"
            for failure in interaction_census_failures(
                build_census,
                expected_profile=cell[1],
                expected_state_ids={
                    str(item.get("id"))
                    for item in route.get("states", [])
                    if isinstance(item, dict)
                } if isinstance(route, dict) else set(),
                expected_urls={str(route.get("url"))} if isinstance(route, dict) else set(),
                artifact_root=record_path.parent,
                allowed_artifacts=frame_artifacts,
            )
        )
        if check.get("build_interaction_census_sha256") != canonical_json_sha256(
            build_census
        ):
            failures.append(
                f"Mechanism interaction check {index} build-census hash differs from its embedded evidence."
            )
        if isinstance(route, dict) and isinstance(state, dict):
            relative_observation = str(route.get("mapped_reference_observation") or "")
            observation = observation_cache.get(relative_observation)
            if observation is None:
                observation_path = (project / PurePosixPath(relative_observation)).resolve()
                try:
                    loaded = json.loads(observation_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    loaded = {}
                observation = loaded if isinstance(loaded, dict) else {}
                observation_cache[relative_observation] = observation
            profile = "narrow" if int(viewport.get("width", 0)) <= 430 else "wide"
            source_census = (
                observation.get("states_by_viewport", {})
                .get(profile, {})
                .get(state.get("mapped_reference_state_id"), {})
                .get("interaction_census")
                if isinstance(observation, dict)
                else None
            )
            if check.get("source_interaction_census_sha256") != canonical_json_sha256(
                source_census
            ):
                failures.append(
                    f"Mechanism interaction check {index} source-census hash differs from its mapped observation state."
                )
            recomputed = recompute_interaction_transfer(
                build_census,
                source_census,
                [
                    item for item in route.get("states", [])
                    if isinstance(item, dict)
                ],
            )
            if recomputed.get("pass") is not True:
                failures.append(
                    f"Mechanism interaction check {index} independently recomputed a source/build mismatch: "
                    + "; ".join(str(item) for item in recomputed.get("failures", []))
                )
            if check.get("interaction_diff") != recomputed:
                failures.append(
                    f"Mechanism interaction check {index} embedded interaction_diff differs from independent recomputation."
                )
            mapped_reference = check.get("mapped_reference")
            if (
                not isinstance(mapped_reference, dict)
                or mapped_reference.get("url") != observation.get("url")
            ):
                failures.append(
                    f"Mechanism interaction check {index} source URL differs from its mapped observation."
                )
    if observed_cells != expected_cells:
        failures.append("Mechanism interaction checks miss route/profile/state cells.")
    transformations = transfer.get("responsive_transformations")
    expected_pairs = {
        (route_key, str(state.get("id")))
        for route_key, route in route_by_key.items()
        for state in route.get("states", [])
        if isinstance(state, dict)
    }
    observed_pairs: set[tuple[str, str]] = set()
    if not isinstance(transformations, list):
        failures.append("Mechanism responsive interaction transformations must be a list.")
        transformations = []
    for transformation in transformations:
        if not isinstance(transformation, dict):
            continue
        pair = (str(transformation.get("route_key")), str(transformation.get("state_id")))
        observed_pairs.add(pair)
        if (
            transformation.get("complete") is not True
            or not isinstance(transformation.get("wide_cell"), str)
            or not isinstance(transformation.get("narrow_cell"), str)
        ):
            failures.append(f"Mechanism responsive interaction {pair[0]}/{pair[1]} is incomplete.")
    if observed_pairs != expected_pairs:
        failures.append("Mechanism responsive interactions miss manifested route/state pairs.")
    return failures


def route_manifest_payload_failures(
    payload: object,
    *,
    selected_ranks: set[int] | None = None,
    expected_manifest_id: str | None = None,
) -> list[str]:
    """Validate the one route/reference/state/viewport authority."""

    if not isinstance(payload, dict) or set(payload) != {
        "schema_version", "manifest_id", "viewports", "routes"
    }:
        return ["Route manifest must use the exact versioned object shape."]
    failures: list[str] = []
    if payload.get("schema_version") != ROUTE_MANIFEST_SCHEMA_VERSION:
        failures.append(
            f"Route manifest schema_version must be {ROUTE_MANIFEST_SCHEMA_VERSION}."
        )
    manifest_id = payload.get("manifest_id")
    if (
        not isinstance(manifest_id, str)
        or ROUTE_MANIFEST_ID.fullmatch(manifest_id) is None
        or manifest_id.startswith("__REPLACE_WITH")
    ):
        failures.append("Route manifest needs an immutable 8-128 character manifest_id.")
    elif expected_manifest_id is not None and manifest_id != expected_manifest_id:
        failures.append(
            f"Route manifest manifest_id {manifest_id!r} does not match "
            f"{expected_manifest_id!r}."
        )

    viewports = payload.get("viewports")
    viewport_names: set[str] = set()
    valid_viewports: list[tuple[str, int, int]] = []
    if not isinstance(viewports, list) or not viewports:
        failures.append("Route manifest needs a nonempty viewport list.")
    else:
        for index, viewport in enumerate(viewports, start=1):
            label = f"Route manifest viewport {index}"
            if not isinstance(viewport, dict) or set(viewport) != {
                "name", "width", "height"
            }:
                failures.append(f"{label} has an unsupported shape.")
                continue
            name = viewport.get("name")
            width = viewport.get("width")
            height = viewport.get("height")
            if (
                not isinstance(name, str)
                or not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", name)
                or name in viewport_names
            ):
                failures.append(f"{label} needs a unique lowercase slug name.")
                continue
            viewport_names.add(name)
            if (
                type(width) is not int
                or type(height) is not int
                or width < 280
                or width > 3840
                or height < 480
                or height > 4320
            ):
                failures.append(f"{label} dimensions are outside supported bounds.")
                continue
            valid_viewports.append((name, width, height))
        if not any(width >= 1280 for _name, width, _height in valid_viewports):
            failures.append("Route manifest needs at least one wide viewport (1280px+).")
        if not any(width <= 430 for _name, width, _height in valid_viewports):
            failures.append("Route manifest needs at least one narrow viewport (430px or less).")

    routes = payload.get("routes")
    keys: set[str] = set()
    urls: set[str] = set()
    origins: set[tuple[str, str]] = set()
    if not isinstance(routes, list) or not routes:
        failures.append("Route manifest needs at least one route.")
    else:
        for index, route in enumerate(routes, start=1):
            label = f"Route manifest route {index}"
            if not isinstance(route, dict) or set(route) != {
                "key",
                "url",
                "mapped_reference_rank",
                "mapped_reference_id",
                "mapped_reference_observation",
                "mapped_reference_sha256",
                "states",
            }:
                failures.append(f"{label} has an unsupported shape.")
                continue
            key = route.get("key")
            if (
                not isinstance(key, str)
                or not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", key)
                or key in keys
            ):
                failures.append(f"{label} needs a unique lowercase slug key.")
            else:
                keys.add(key)
            raw_url = route.get("url")
            try:
                normalized_url = (
                    canonical_route_url(raw_url)
                    if isinstance(raw_url, str)
                    else ""
                )
            except ValueError:
                normalized_url = ""
            if not normalized_url or str(raw_url).startswith("__REPLACE_WITH"):
                failures.append(f"{label} needs an absolute HTTP(S) URL.")
            elif normalized_url != raw_url:
                failures.append(
                    f"{label} URL must already be canonical and fragment-free: "
                    f"{normalized_url}."
                )
            else:
                if normalized_url in urls:
                    failures.append(f"{label} duplicates another normalized URL.")
                urls.add(normalized_url)
                parsed = urlsplit(normalized_url)
                origins.add((parsed.scheme, parsed.netloc))
                if normalize_safe_route_path(parsed.path or "/") is None:
                    failures.append(
                        f"{label} URL path contains invalid UTF-8, encoded separators, traversal, controls, or whitespace."
                    )
            rank = route.get("mapped_reference_rank")
            if type(rank) is not int or rank < 1:
                failures.append(f"{label} needs a positive mapped_reference_rank.")
            elif selected_ranks is not None and rank not in selected_ranks:
                failures.append(
                    f"{label} maps to rank {rank}, which is not a selected reference."
                )
            reference_id = route.get("mapped_reference_id")
            id_match = (
                ROUTE_REFERENCE_ID.fullmatch(reference_id)
                if isinstance(reference_id, str)
                else None
            )
            if id_match is None:
                failures.append(f"{label} needs a strong-N mapped_reference_id.")
            elif type(rank) is int and int(id_match.group(1)) != rank:
                failures.append(
                    f"{label} mapped reference ID does not belong to rank {rank}."
                )
            observation = route.get("mapped_reference_observation")
            expected_observation = (
                f".design-dna/references/{reference_id}-observation.json"
                if isinstance(reference_id, str)
                else ""
            )
            if (
                not isinstance(observation, str)
                or observation.replace("\\", "/") != expected_observation
                or ".." in PurePosixPath(observation).parts
            ):
                failures.append(
                    f"{label} mapped_reference_observation must be "
                    f"{expected_observation or 'the canonical strong-N observation path'}."
                )
            reference_sha = route.get("mapped_reference_sha256")
            if (
                not isinstance(reference_sha, str)
                or re.fullmatch(r"[0-9a-f]{64}", reference_sha) is None
            ):
                failures.append(
                    f"{label} needs a lowercase mapped_reference_sha256."
                )
            states = route.get("states")
            state_ids: set[str] = set()
            if not isinstance(states, list) or not states:
                failures.append(f"{label} needs a nonempty typed states list.")
            else:
                for state_index, state in enumerate(states, start=1):
                    state_label = f"{label} state {state_index}"
                    if not isinstance(state, dict) or set(state) != {
                        "id", "kind", "trigger", "expectation",
                        "mapped_reference_state_id",
                    }:
                        failures.append(f"{state_label} has an unsupported shape.")
                        continue
                    state_id = state.get("id")
                    kind = state.get("kind")
                    trigger = state.get("trigger")
                    expectation = state.get("expectation")
                    mapped_state_id = state.get("mapped_reference_state_id")
                    if (
                        not isinstance(state_id, str)
                        or re.fullmatch(r"[a-z][a-z0-9-]{0,47}", state_id) is None
                        or state_id in state_ids
                    ):
                        failures.append(f"{state_label} needs a unique lowercase slug id.")
                    else:
                        state_ids.add(state_id)
                    if kind not in ROUTE_MANIFEST_STATE_KINDS:
                        failures.append(f"{state_label} has an unsupported kind.")
                    if not isinstance(trigger, dict) or set(trigger) != {
                        "type", "target", "value"
                    }:
                        failures.append(f"{state_label} trigger has an unsupported shape.")
                        continue
                    trigger_type = trigger.get("type")
                    if trigger_type not in ROUTE_MANIFEST_TRIGGER_TYPES:
                        failures.append(f"{state_label} has an unsupported trigger type.")
                    if not isinstance(trigger.get("target"), str) or not trigger["target"].strip():
                        failures.append(f"{state_label} trigger target must be explicit.")
                    if trigger.get("value") is not None and not isinstance(trigger.get("value"), str):
                        failures.append(f"{state_label} trigger value must be a string or null.")
                    if not isinstance(expectation, str) or len(expectation.strip()) < 12:
                        failures.append(f"{state_label} needs a substantive expectation.")
                    if (
                        not isinstance(mapped_state_id, str)
                        or re.fullmatch(r"[a-z][a-z0-9-]{0,63}", mapped_state_id) is None
                    ):
                        failures.append(
                            f"{state_label} needs a stable mapped_reference_state_id."
                        )
                    if state_id == "rest" and (
                        kind != "rest"
                        or trigger_type != "none"
                        or trigger.get("target") != "document"
                        or trigger.get("value") is not None
                        or expectation != "initial settled route"
                        or mapped_state_id != "rest"
                    ):
                        failures.append(
                            f"{state_label} rest must use the exact canonical rest contract and mapped source rest state."
                        )
                    if state_id != "rest" and kind == "rest":
                        failures.append(f"{state_label} only the rest state may use kind rest.")
                if "rest" not in state_ids:
                    failures.append(f"{label} states must include the canonical `rest` state.")
    if len(origins) > 1:
        failures.append("Every route in the manifest must share one build origin.")
    return failures


def route_manifest_reference_failures(
    payload: dict[str, object], *, project: Path
) -> list[str]:
    failures: list[str] = []
    observer = Path(__file__).resolve().parent / "observe_reference.mjs"
    expected_observer_sha = file_sha256(observer)[1]
    for index, route in enumerate(payload.get("routes", []), start=1):
        if not isinstance(route, dict):
            continue
        relative = str(route.get("mapped_reference_observation") or "")
        observation = (project / PurePosixPath(relative)).resolve()
        reference_sha = str(route.get("mapped_reference_sha256") or "")
        label = f"Route manifest route {index} mapped reference"
        if not is_within(observation, project.resolve()) or not observation.is_file():
            failures.append(f"{label} observation is missing or escapes the project.")
            continue
        if file_sha256(observation)[1] != reference_sha:
            failures.append(f"{label} observation SHA-256 has drifted.")
            continue
        try:
            observed = json.loads(observation.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            failures.append(f"{label} observation is unreadable: {exc}")
            continue
        if (
            not isinstance(observed, dict)
            or observed.get("tool") != "observe_reference.mjs"
            or observed.get("schema_version") != REFERENCE_OBSERVATION_SCHEMA
            or observed.get("producer_script_sha256") != expected_observer_sha
            or observed.get("id") != route.get("mapped_reference_id")
        ):
            failures.append(
                f"{label} does not bind the current observer schema, producer, and ID."
            )
            continue
        failures.extend(
            f"{label}: {failure}"
            for failure in packaged_runtime_record_failures(
                observed, tool="observe_reference.mjs"
            )
        )
        state_contract = observed.get("state_contract")
        contract_ids: set[str] = set()
        if (
            not isinstance(state_contract, dict)
            or set(state_contract) != {"file", "sha256"}
            or not isinstance(state_contract.get("file"), str)
            or not isinstance(state_contract.get("sha256"), str)
            or SHA256_HEX.fullmatch(state_contract["sha256"]) is None
        ):
            failures.append(f"{label} has no valid source-state contract binding.")
        else:
            contract_path = (
                observation.parent / PurePosixPath(state_contract["file"])
            ).resolve()
            expected_contract = (
                project
                / ".design-dna"
                / "references"
                / f"{route.get('mapped_reference_id')}-state-contract.json"
            ).resolve()
            if (
                contract_path != expected_contract
                or not is_within(contract_path, project.resolve())
                or not contract_path.is_file()
                or file_sha256(contract_path)[1] != state_contract["sha256"]
            ):
                failures.append(f"{label} source-state contract bytes are missing or drifted.")
            else:
                try:
                    contract_payload = json.loads(
                        contract_path.read_text(encoding="utf-8")
                    )
                except (OSError, ValueError) as exc:
                    failures.append(f"{label} source-state contract is unreadable: {exc}")
                else:
                    contract_problems, contract_ids = reference_state_contract_failures(
                        contract_payload,
                        expected_reference_id=str(route.get("mapped_reference_id")),
                        expected_primary_url=(
                            observed.get("url")
                            if isinstance(observed.get("url"), str)
                            else None
                        ),
                    )
                    failures.extend(f"{label}: {problem}" for problem in contract_problems)
        states_by_viewport = observed.get("states_by_viewport")
        mapped_state_ids = {
            str(state.get("mapped_reference_state_id"))
            for state in route.get("states", [])
            if isinstance(state, dict)
        }
        if (
            not isinstance(states_by_viewport, dict)
            or set(states_by_viewport) != {"wide", "narrow"}
            or any(
                not isinstance(states_by_viewport.get(viewport), dict)
                or not mapped_state_ids.issubset(set(states_by_viewport[viewport]))
                or (contract_ids and set(states_by_viewport[viewport]) != contract_ids)
                for viewport in ("wide", "narrow")
            )
        ):
            failures.append(
                f"{label} does not contain every mapped reference state at wide and narrow viewports."
            )
        discovery = observed.get("discovery_metadata")
        interaction = observed.get("interaction_census_by_viewport")
        rendered_qa = observed.get("rendered_qa_by_viewport")
        frame_dir = observed.get("frame_dir")
        observer_artifacts = {
            (
                (PurePosixPath(frame_dir) / PurePosixPath(frame.get("file"))).as_posix(),
                frame.get("bytes"),
                frame.get("sha256"),
            )
            for frame in observed.get("frames", [])
            if isinstance(frame, dict)
            and isinstance(frame_dir, str)
            and isinstance(frame.get("file"), str)
            and type(frame.get("bytes")) is int
            and isinstance(frame.get("sha256"), str)
        }
        if (
            not isinstance(discovery, dict)
            or set(discovery) != {"wide", "narrow"}
            or not isinstance(interaction, dict)
            or set(interaction) != {"wide", "narrow"}
            or not isinstance(rendered_qa, dict)
            or set(rendered_qa) != {"wide", "narrow"}
        ):
            failures.append(f"{label} has no generated wide/narrow discovery, interaction census, and rendered QA.")
        else:
            for viewport in ("wide", "narrow"):
                discovery_entry = discovery.get(viewport)
                if not isinstance(discovery_entry, dict):
                    failures.append(f"{label} {viewport} discovery metadata is invalid.")
                    continue
                discovered_urls = discovery_entry.get("discovered_urls")
                visited_urls = discovery_entry.get("visited_urls")
                source_state_ids = discovery_entry.get("source_state_ids")
                if (
                    not isinstance(discovered_urls, list)
                    or not discovered_urls
                    or discovered_urls != visited_urls
                    or not isinstance(source_state_ids, list)
                    or set(source_state_ids) != contract_ids
                ):
                    failures.append(f"{label} {viewport} source discovery/state coverage is incomplete.")
                    continue
                failures.extend(
                    f"{label}: {failure}"
                    for failure in interaction_census_failures(
                        interaction.get(viewport),
                        expected_profile=viewport,
                        expected_state_ids=contract_ids,
                        expected_urls=set(visited_urls),
                        artifact_root=observation.parent,
                        allowed_artifacts=observer_artifacts,
                    )
                )
                failures.extend(
                    f"{label}: {failure}"
                    for failure in source_rendered_qa_failures(
                        rendered_qa.get(viewport),
                        expected_profile=viewport,
                        expected_urls=set(visited_urls),
                        artifact_root=observation.parent,
                        allowed_artifacts=observer_artifacts,
                        interaction_census=interaction.get(viewport),
                    )
                )
    return failures


def bound_route_manifest_failures(
    cell: str,
    *,
    project: Path,
    record_path: Path,
    selected_ranks: set[int] | None = None,
    expected_manifest_id: str | None = None,
) -> tuple[list[str], dict[str, object] | None, Path | None]:
    artifact, failures = bound_artifact(
        cell,
        project=project,
        record_path=record_path,
        label="Route manifest",
    )
    if failures or artifact is None:
        return failures, None, artifact
    expected = (project / ".design-dna" / "route-manifest.json").resolve()
    if artifact.resolve() != expected:
        return (["Route manifest binding must name .design-dna/route-manifest.json."], None, artifact)
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ([f"Route manifest is not readable JSON: {exc}"], None, artifact)
    payload_failures = route_manifest_payload_failures(
        payload,
        selected_ranks=selected_ranks,
        expected_manifest_id=expected_manifest_id,
    )
    if isinstance(payload, dict) and not payload_failures:
        payload_failures.extend(
            route_manifest_reference_failures(payload, project=project)
        )
    return payload_failures, payload if isinstance(payload, dict) else None, artifact


def reference_dossier_failures(
    body: str,
    *,
    project: Path,
    record_path: Path,
) -> list[str]:
    """Validate captured, source-spread, brief-fit reference research.

    The count is a floor tied to source spread, not a quota: enough
    independent sites that none becomes the template. Every row binds a
    capture the producer looked at, because a reference nobody opened is a
    plausible name, not research.
    """

    failures: list[str] = []
    registry, active_source_ids, registry_failures = load_reference_source_registry()
    failures.extend(registry_failures)
    registry_sources = {
        source.get("id"): source
        for source in (
            registry.get("sources", []) if isinstance(registry, dict) else []
        )
        if isinstance(source, dict) and isinstance(source.get("id"), str)
    }
    sections = markdown_sections(body)
    frame = sections.get("Research frame", "")
    for label in (
        "Reference-selection brief",
        "Brief and priority-source rationale",
        "Current active registry audit date and limitations",
        "Public-access disposition for blocked or unavailable sources",
        "Source-specific filters",
        "Plausible alternate discovery paths",
        "Ledger check",
        "Planned route/state coverage",
    ):
        if not non_placeholder(markdown_label_value(frame, label)):
            failures.append(f"Reference dossier {label!r} is missing or still scaffold text.")
    authorized_basis = markdown_label_value(frame, "Authorized-account basis")
    if authorized_basis is None:
        failures.append("Reference dossier needs an authorized-account basis or `none`.")

    def capture_failures(cell: str, label: str) -> list[str]:
        capture_label = f"{label} capture"
        match = ARTIFACT_BINDING_PATTERN.fullmatch(cell.strip())
        if match is not None and not match.group(1).strip().startswith(
            REFERENCE_CAPTURE_PREFIX
        ):
            return [
                f"{capture_label} must live under {REFERENCE_CAPTURE_PREFIX} "
                "so research evidence stays out of the public root."
            ]
        artifact, artifact_failures = bound_artifact(
            cell,
            project=project,
            record_path=record_path,
            label=capture_label,
        )
        if artifact_failures or artifact is None:
            return artifact_failures
        try:
            verify_png_artifact(artifact)
        except StateError as exc:
            return [f"{capture_label} is not usable evidence: {exc}"]
        return []

    def capture_pair_failures(
        wide_cell: str, narrow_cell: str, label: str
    ) -> list[str]:
        """Require two real, distinct viewport captures for every candidate."""

        problems = [
            *capture_failures(wide_cell, f"{label} wide"),
            *capture_failures(narrow_cell, f"{label} narrow"),
        ]
        if problems:
            return problems
        wide, wide_problems = bound_artifact(
            wide_cell,
            project=project,
            record_path=record_path,
            label=f"{label} wide capture",
        )
        narrow, narrow_problems = bound_artifact(
            narrow_cell,
            project=project,
            record_path=record_path,
            label=f"{label} narrow capture",
        )
        problems.extend(wide_problems)
        problems.extend(narrow_problems)
        if wide is None or narrow is None:
            return problems
        if (
            wide.resolve() == narrow.resolve()
            or file_sha256(wide)[1] == file_sha256(narrow)[1]
        ):
            problems.append(
                f"{label} must bind distinct wide and narrow capture pixels; "
                "one screenshot cannot prove responsive transformation."
            )
            return problems
        try:
            wide_width, _wide_height = verify_png_artifact(wide)
            narrow_width, _narrow_height = verify_png_artifact(narrow)
        except StateError as exc:
            return [*problems, f"{label} capture pair is not usable: {exc}"]
        if wide_width < 900 or narrow_width > 600 or wide_width <= narrow_width:
            problems.append(
                f"{label} capture widths do not prove wide/narrow review "
                f"({wide_width}px versus {narrow_width}px)."
            )
        return problems

    def study_scope_failures(value: str, label: str) -> list[str]:
        normalized = " ".join(value.casefold().split())
        concepts = (
            "page", "inner", "progression", "navigation", "scroll", "hover",
            "click", "state", "ending", "reset", "narrow", "mobile",
        )
        hits = sum(1 for concept in concepts if concept in normalized)
        if len(normalized) < 80 or hits < 4:
            return [
                f"{label} must name the accessible pages, full progression, "
                "meaningful states/interactions, and narrow behavior actually studied."
            ]
        return []

    def brief_fit_failures(value: str, label: str) -> list[str]:
        normalized = " ".join(value.casefold().split())
        dimensions = (
            ("content", "content model"),
            ("task", "visitor job"),
            ("audience",),
            ("brand", "identity"),
            ("operat", "service reality"),
            ("route", "progression"),
            ("responsive", "mobile", "narrow"),
            ("right", "access", "license"),
        )
        hits = sum(
            1 for aliases in dimensions
            if any(alias in normalized for alias in aliases)
        )
        if len(normalized) < 120 or hits < 6:
            return [
                f"{label} must compare content model, visitor task, audience, "
                "brand/operating reality, route progression, responsive fit, "
                "and rights/access instead of relying on an award, tag, or mood."
            ]
        return []

    def candidate_observation_context(
        binding: str,
        *,
        candidate_url: str,
        wide_capture: str,
        narrow_capture: str,
        label: str,
    ) -> tuple[list[str], dict[str, object] | None, Path | None]:
        """Load generated candidate-study evidence, never prose-as-proof."""

        problems: list[str] = []
        artifact, binding_problems = bound_artifact(
            binding,
            project=project,
            record_path=record_path,
            label=f"{label} generated study evidence",
        )
        problems.extend(binding_problems)
        if artifact is None or binding_problems:
            return problems, None, artifact
        if (
            artifact.parent.resolve()
            != (project / ".design-dna" / "references").resolve()
        ):
            return [
                *problems,
                f"{label} generated study evidence must live directly in .design-dna/references.",
            ], None, artifact
        try:
            observed = json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return [*problems, f"{label} generated study evidence is unreadable: {exc}"], None, artifact
        identity = packaged_runtime_record_failures(
            observed, tool="observe_reference.mjs"
        )
        problems.extend(f"{label}: {failure}" for failure in identity)
        if not isinstance(observed, dict):
            return [*problems, f"{label} generated study evidence is not an object."], None, artifact
        try:
            exact_candidate_url = canonical_route_url(candidate_url)
            exact_observed_url = canonical_route_url(str(observed.get("url") or ""))
        except ValueError:
            exact_candidate_url = exact_observed_url = ""
        if (
            not exact_candidate_url
            or exact_candidate_url != candidate_url
            or exact_observed_url != exact_candidate_url
            or observed.get("url") != exact_observed_url
            or observed.get("requested_url") != exact_observed_url
            or observed.get("final_url") != exact_observed_url
        ):
            problems.append(f"{label} generated study does not bind the candidate's exact non-redirect URL.")

        captures = observed.get("captures_by_viewport")
        if not isinstance(captures, dict) or set(captures) != {"wide", "narrow"}:
            problems.append(f"{label} generated study lacks wide/narrow capture bindings.")
        else:
            for viewport, declared in (
                ("wide", wide_capture),
                ("narrow", narrow_capture),
            ):
                capture = captures.get(viewport)
                declared_path, declared_problems = bound_artifact(
                    declared,
                    project=project,
                    record_path=record_path,
                    label=f"{label} {viewport} capture",
                )
                problems.extend(declared_problems)
                generated_path = (
                    artifact.parent / PurePosixPath(str(capture.get("file") or ""))
                ).resolve() if isinstance(capture, dict) else Path()
                if (
                    not isinstance(capture, dict)
                    or set(capture) != {"file", "bytes", "sha256"}
                    or declared_path is None
                    or generated_path != declared_path.resolve()
                    or not is_within(generated_path, artifact.parent.resolve())
                    or not generated_path.is_file()
                    or type(capture.get("bytes")) is not int
                    or generated_path.stat().st_size != capture.get("bytes")
                    or not isinstance(capture.get("sha256"), str)
                    or file_sha256(generated_path)[1] != capture.get("sha256")
                ):
                    problems.append(
                        f"{label} {viewport} capture is not the exact generated observation capture."
                    )
                else:
                    try:
                        verify_png_artifact(generated_path)
                    except StateError as exc:
                        problems.append(f"{label} {viewport} generated capture is invalid: {exc}")

        discovery = observed.get("discovery_metadata")
        discovery_context: dict[str, dict[str, object]] = {}
        if not isinstance(discovery, dict) or set(discovery) != {"wide", "narrow"}:
            problems.append(f"{label} generated study lacks wide/narrow discovery metadata.")
        else:
            for viewport in ("wide", "narrow"):
                entry = discovery.get(viewport)
                if not isinstance(entry, dict) or set(entry) != {
                    "discovered_urls", "visited_urls", "source_state_ids"
                }:
                    problems.append(f"{label} {viewport} discovery metadata has an unsupported shape.")
                    continue
                discovered = entry.get("discovered_urls")
                visited = entry.get("visited_urls")
                state_ids = entry.get("source_state_ids")
                if (
                    not isinstance(discovered, list)
                    or not discovered
                    or discovered != sorted(set(discovered))
                    or visited != discovered
                    or not isinstance(state_ids, list)
                    or not state_ids
                    or len(state_ids) != len(set(state_ids))
                    or "rest" not in state_ids
                ):
                    problems.append(
                        f"{label} {viewport} did not completely visit every discovered page and authored state."
                    )
                else:
                    discovery_context[viewport] = entry
        if (
            set(discovery_context) == {"wide", "narrow"}
            and set(discovery_context["wide"]["source_state_ids"])
            != set(discovery_context["narrow"]["source_state_ids"])
        ):
            problems.append(f"{label} wide/narrow source-state coverage differs.")
        interaction_census = observed.get("interaction_census_by_viewport")
        observer_frame_dir = observed.get("frame_dir")
        observer_artifacts = {
            (
                (PurePosixPath(observer_frame_dir) / PurePosixPath(frame.get("file"))).as_posix(),
                frame.get("bytes"),
                frame.get("sha256"),
            )
            for frame in observed.get("frames", [])
            if isinstance(frame, dict)
            and isinstance(observer_frame_dir, str)
            and isinstance(frame.get("file"), str)
            and type(frame.get("bytes")) is int
            and isinstance(frame.get("sha256"), str)
        }
        if (
            not isinstance(interaction_census, dict)
            or set(interaction_census) != {"wide", "narrow"}
        ):
            problems.append(f"{label} generated study lacks a wide/narrow interaction census.")
        else:
            for viewport in ("wide", "narrow"):
                discovery_entry = discovery_context.get(viewport, {})
                problems.extend(
                    f"{label}: {problem}"
                    for problem in interaction_census_failures(
                        interaction_census.get(viewport),
                        expected_profile=viewport,
                        expected_state_ids=set(
                            discovery_entry.get("source_state_ids", [])
                        ),
                        expected_urls=set(
                            discovery_entry.get("visited_urls", [])
                        ),
                        artifact_root=artifact.parent,
                        allowed_artifacts=observer_artifacts,
                    )
                )

        quality = observed.get("quality_observations")
        categories = {
            row.get("category"): row
            for row in quality or []
            if isinstance(row, dict)
        }
        if (
            not isinstance(quality, list)
            or len(categories) != len(quality)
            or set(categories)
            != {"responsive-first-screen", "experience-coverage", "behavior"}
            or not categories.get("responsive-first-screen", {}).get("wide_dominant")
            or not categories.get("responsive-first-screen", {}).get("narrow_dominant")
            or type(categories.get("experience-coverage", {}).get("wide_pages")) is not int
            or type(categories.get("experience-coverage", {}).get("narrow_pages")) is not int
            or categories.get("experience-coverage", {}).get("wide_pages", 0) < 1
            or categories.get("experience-coverage", {}).get("narrow_pages", 0) < 1
            or type(categories.get("experience-coverage", {}).get("authored_state_cells")) is not int
            or categories.get("experience-coverage", {}).get("authored_state_cells", 0) < 2
            or not isinstance(categories.get("behavior", {}).get("mechanisms"), list)
            or not isinstance(categories.get("behavior", {}).get("responsive_state_results"), list)
        ):
            problems.append(f"{label} generated quality observations are incomplete.")
        defects = observed.get("defect_observations")
        if not isinstance(defects, list) or any(not isinstance(item, dict) for item in defects):
            problems.append(f"{label} generated defect observations are invalid.")

        return problems, {
            "record": observed,
            "discovery": discovery_context,
            "defects": defects if isinstance(defects, list) else [],
            "quality": categories,
        }, artifact

    observed_inner_urls: list[str] = []

    candidate_headers, candidate_rows = markdown_first_table(
        sections.get("Candidate comparison", "")
    )
    selected_candidate_urls: set[str] = set()
    candidate_capture_bindings: set[str] = set()
    rejected_candidates = 0
    if (
        candidate_headers != REFERENCE_DOSSIER_CANDIDATE_HEADERS
        or len(candidate_rows) < REFERENCE_MINIMUM_CANDIDATES
    ):
        failures.append(
            "Reference dossier needs at least eight serious candidate-comparison "
            "rows using the exact contract, including concrete rejections; "
            "selection cannot begin from the first convenient gallery results."
        )
    else:
        curation_by_source = reference_source_curation()
        brief_criteria = (
            "content_model", "organization_context", "visitor_task", "audience", "brand_authority",
            "operating_reality", "route_responsive", "rights_access",
        )
        quality_criteria = (
            "composition", "typography", "media", "responsive",
            "interaction", "finish",
        )
        generic_only = re.compile(
            r"\b(?:beautiful|cool|clean|modern|premium|polished|stunning|"
            r"interesting|nice|strong|good|great|on[- ]brand|fits? the vibe)\b",
            re.IGNORECASE,
        )
        quota_padding = re.compile(
            r"\b(?:quota|padding|fill(?:ing)? (?:the )?(?:list|count)|"
            r"needed (?:one|another|more)|make up the numbers)\b",
            re.IGNORECASE,
        )
        for row_number, row in enumerate(candidate_rows, start=1):
            label = f"Reference dossier candidate row {row_number}"
            if len(row) != len(REFERENCE_DOSSIER_CANDIDATE_HEADERS) or any(
                not non_placeholder(cell) for cell in row
            ):
                failures.append(f"{label} is incomplete.")
                continue
            failures.extend(reference_entry_url_failures(row[0], f"{label} URL"))
            url_match = re.search(r"https://[^\s)]+", row[0])
            candidate_url = url_match.group(0).rstrip(".,;|") if url_match else ""
            source_fields = semicolon_fields(row[1])
            required_source_fields = {
                "source", "discovery_path", "filter", "retrieval", "retrieved",
                "reuse_basis",
            }
            source_id = source_fields.get("source", "").casefold()
            allowed_source_fields = set(required_source_fields)
            if source_fields.get("reuse_basis", "").casefold() == "revalidated-reuse":
                allowed_source_fields.update({"prior_evidence", "revalidated"})
            if set(source_fields) != allowed_source_fields:
                failures.append(
                    f"{label} source history must use the exact discovery/retrieval/reuse fields."
                )
            if source_id not in active_source_ids:
                failures.append(
                    f"{label} discovery source must be an active, legitimately "
                    "accessible public source."
                )
            source_record = registry_sources.get(source_id, {})
            discovery_path = source_fields.get("discovery_path", "")
            try:
                source_host = urlsplit(str(source_record.get("url") or "")).netloc.casefold().removeprefix("www.")
                discovery_host = urlsplit(discovery_path).netloc.casefold().removeprefix("www.")
                canonical_discovery = canonical_route_url(discovery_path)
            except ValueError:
                source_host = discovery_host = canonical_discovery = ""
            if (
                not source_host
                or discovery_host != source_host
                or canonical_discovery != discovery_path
            ):
                failures.append(
                    f"{label} discovery_path must be the exact canonical listing/filter URL on its registry source."
                )
            if source_fields.get("retrieval") != source_record.get("retrieval"):
                failures.append(
                    f"{label} retrieval method must match the registry source contract."
                )
            failures.extend(
                reference_dossier_date_failures(
                    source_fields.get("retrieved", ""), f"{label} source retrieval"
                )
            )
            filter_value = source_fields.get("filter", "")
            filter_dimensions = sum(
                1
                for aliases in (
                    ("content", "editorial", "catalog"),
                    ("visitor", "task", "conversion", "reading"),
                    ("route", "page", "state", "flow"),
                    ("responsive", "mobile", "narrow"),
                    ("brand", "authority", "business"),
                    ("material", "cultural", "time", "place"),
                )
                if any(alias in filter_value.casefold() for alias in aliases)
            )
            if (
                len(" ".join(filter_value.split())) < 60
                or filter_dimensions < 3
                or quota_padding.search(filter_value)
            ):
                failures.append(
                    f"{label} filter must bind at least three brief dimensions; a category/tag or quota need is not selection logic."
                )
            reuse_basis = source_fields.get("reuse_basis", "").casefold()
            if reuse_basis not in {"fresh", "revalidated-reuse"}:
                failures.append(f"{label} reuse_basis must be fresh or revalidated-reuse.")
            elif reuse_basis == "revalidated-reuse":
                prior, prior_failures = bound_artifact(
                    source_fields.get("prior_evidence", ""),
                    project=project,
                    record_path=record_path,
                    label=f"{label} prior reuse evidence",
                )
                failures.extend(prior_failures)
                if prior is None:
                    failures.append(f"{label} reused candidate has no bound prior evidence.")
                failures.extend(
                    reference_dossier_date_failures(
                        source_fields.get("revalidated", ""), f"{label} reuse revalidation"
                    )
                )
            pair_problems = capture_pair_failures(row[2], row[3], label)
            failures.extend(pair_problems)
            for binding in (row[2].strip(), row[3].strip()):
                if binding in candidate_capture_bindings:
                    failures.append(
                        f"{label} reuses another candidate's capture binding; "
                        "each website must be inspected on its own pixels."
                    )
                candidate_capture_bindings.add(binding)
            study_fields = semicolon_fields(row[4])
            if set(study_fields) != {
                "evidence", "wide_pages", "narrow_pages", "states", "progression"
            }:
                failures.append(f"{label} complete-study cell has an unsupported shape.")
            study_problems, study_context, study_artifact = candidate_observation_context(
                study_fields.get("evidence", ""),
                candidate_url=candidate_url,
                wide_capture=row[2],
                narrow_capture=row[3],
                label=label,
            )
            failures.extend(study_problems)
            if study_context is not None:
                discovery = study_context.get("discovery", {})
                wide_discovery = discovery.get("wide", {}) if isinstance(discovery, dict) else {}
                narrow_discovery = discovery.get("narrow", {}) if isinstance(discovery, dict) else {}
                try:
                    declared_wide_pages = int(study_fields.get("wide_pages", ""))
                    declared_narrow_pages = int(study_fields.get("narrow_pages", ""))
                except ValueError:
                    declared_wide_pages = declared_narrow_pages = -1
                exact_states = set(wide_discovery.get("source_state_ids", []))
                declared_states = {
                    item.strip() for item in study_fields.get("states", "").split(",")
                    if item.strip()
                }
                if (
                    declared_wide_pages != len(wide_discovery.get("visited_urls", []))
                    or declared_narrow_pages != len(narrow_discovery.get("visited_urls", []))
                    or declared_states != exact_states
                    or declared_states
                    != set(narrow_discovery.get("source_state_ids", []))
                    or len(study_fields.get("progression", "").strip()) < 60
                    or sum(
                        term in study_fields.get("progression", "").casefold()
                        for term in ("page", "route", "scroll", "state", "navigation", "ending")
                    ) < 3
                ):
                    failures.append(
                        f"{label} complete-study declaration does not match generated wide/narrow pages, states, and progression."
                    )

            brief_fields = semicolon_fields(row[5])
            if set(brief_fields) != {*brief_criteria, "evidence"}:
                failures.append(f"{label} brief-fit gate must name every exact criterion and evidence.")
            brief_statuses = [brief_fields.get(criterion) for criterion in brief_criteria]
            if any(status not in {"pass", "fail"} for status in brief_statuses):
                failures.append(f"{label} brief-fit criteria must each be pass or fail.")
            brief_evidence, brief_evidence_failures = bound_artifact(
                brief_fields.get("evidence", ""),
                project=project,
                record_path=record_path,
                label=f"{label} brief-fit evidence",
            )
            failures.extend(brief_evidence_failures)
            if brief_evidence is not None and brief_evidence.resolve() == record_path.resolve():
                failures.append(f"{label} brief-fit evidence cannot circularly bind this dossier.")
            brief_pass = bool(brief_statuses) and all(status == "pass" for status in brief_statuses)

            quality_fields = semicolon_fields(row[6])
            if set(quality_fields) != {*quality_criteria, "defects", "evidence"}:
                failures.append(f"{label} quality/execution gate must name every exact criterion, defects, and evidence.")
            quality_statuses = [quality_fields.get(criterion) for criterion in quality_criteria]
            if any(status not in {"pass", "fail"} for status in quality_statuses):
                failures.append(f"{label} quality/execution criteria must each be pass or fail.")
            quality_evidence, quality_evidence_failures = bound_artifact(
                quality_fields.get("evidence", ""),
                project=project,
                record_path=record_path,
                label=f"{label} quality/execution evidence",
            )
            failures.extend(quality_evidence_failures)
            if (
                study_artifact is not None
                and quality_evidence is not None
                and quality_evidence.resolve() != study_artifact.resolve()
            ):
                failures.append(
                    f"{label} quality/execution gate must bind the same packaged observer record as complete study."
                )
            defects = (
                study_context.get("defects", [])
                if isinstance(study_context, dict)
                else []
            )
            defect_names = {
                str(defect.get("category") or defect.get("kind") or "")
                for defect in defects
                if isinstance(defect, dict)
            } - {""}
            declared_defects = quality_fields.get("defects", "")
            if defect_names:
                if declared_defects.casefold() == "none" or any(
                    name.casefold() not in declared_defects.casefold()
                    for name in defect_names
                ):
                    failures.append(f"{label} hides generated negative defect observations.")
            elif declared_defects.casefold() != "none":
                failures.append(f"{label} defects must be exactly none when the generated ledger is empty.")
            quality_pass = (
                bool(quality_statuses)
                and all(status == "pass" for status in quality_statuses)
                and not defect_names
            )

            disposition_fields = semicolon_fields(row[7])
            if set(disposition_fields) != {
                "brief_fit", "quality_execution", "disposition", "reason"
            }:
                failures.append(f"{label} conjunctive disposition has an unsupported shape.")
            declared_brief = disposition_fields.get("brief_fit")
            declared_quality = disposition_fields.get("quality_execution")
            disposition = disposition_fields.get("disposition", "").casefold()
            reason = disposition_fields.get("reason", "")
            if declared_brief != ("pass" if brief_pass else "fail"):
                failures.append(f"{label} disposition misstates its brief-fit gate result.")
            if declared_quality != ("pass" if quality_pass else "fail"):
                failures.append(f"{label} disposition misstates its quality/execution gate result.")
            if (
                len(" ".join(reason.split())) < 45
                or quota_padding.search(reason)
                or (
                    generic_only.search(reason)
                    and not re.search(
                        r"\b(?:composition|type|media|responsive|interaction|"
                        r"finish|content|visitor|audience|brand|route|rights|"
                        r"defect|page|state|capture|sequence)\b",
                        reason,
                        re.IGNORECASE,
                    )
                )
            ):
                failures.append(
                    f"{label} disposition reason must name concrete evidence/criteria, not generic praise or quota padding."
                )
            if disposition == "selected":
                if not brief_pass or not quality_pass:
                    failures.append(
                        f"{label} cannot be selected unless both independent gates pass and generated defects are empty."
                    )
                if curation_by_source.get(source_id, "submission") not in REFERENCE_CURATION_ALLOWED:
                    failures.append(
                        f"{label} selects an entry from a submission feed; "
                        "only award or editorially curated sources establish "
                        "the required quality basis."
                    )
                if candidate_url:
                    selected_candidate_urls.add(candidate_url)
            elif disposition == "rejected":
                rejected_candidates += 1
            else:
                failures.append(
                    f"{label} disposition must be selected or rejected."
                )
        if rejected_candidates < REFERENCE_MINIMUM_REJECTED_CANDIDATES:
            failures.append(
                "Reference dossier candidate comparison must record at least two "
                "serious rejected alternatives with concrete reasons."
            )

    def observation_failures(
        cell: str,
        label: str,
        row_url: str,
        expected_reference_id: str,
    ) -> list[str]:
        """A strong row binds a session emitted by observe_reference.mjs.

        The cell reads `<motion|static>; <path> plus sha256:<hex>`. The kind is
        the producer's claim about the signature; the session is the evidence.
        A motion claim without observed motion is the exact failure this gate
        exists to stop: a producer who only ever saw stills cannot know whether
        a site moves, and will report the parts that survive a photograph.
        """
        observation_label = f"{label} observed evidence"
        raw = cell.strip()
        kind, separator, binding = raw.partition(";")
        kind = kind.strip().casefold()
        if not separator or kind not in {"motion", "static"}:
            return [
                f"{observation_label} must begin with the signature kind "
                "`motion` or `static`, then `; ` and the bound observation "
                "session, e.g. `motion; .design-dna/references/strong-1-observation.json plus sha256:<hex>`."
            ]
        binding = binding.strip()
        match = ARTIFACT_BINDING_PATTERN.fullmatch(binding)
        if match is not None and not match.group(1).strip().startswith(
            REFERENCE_CAPTURE_PREFIX
        ):
            return [
                f"{observation_label} must live under {REFERENCE_CAPTURE_PREFIX} "
                "so research evidence stays out of the public root."
            ]
        artifact, artifact_failures = bound_artifact(
            binding,
            project=project,
            record_path=record_path,
            label=observation_label,
        )
        if artifact_failures or artifact is None:
            return artifact_failures
        try:
            payload = json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return [f"{observation_label} is not readable JSON: {exc}"]
        if not isinstance(payload, dict):
            return [f"{observation_label} must be an observation object."]
        problems: list[str] = []
        if payload.get("tool") != "observe_reference.mjs":
            problems.append(
                f"{observation_label} must be emitted by the packaged "
                "observe_reference.mjs harness; a hand-written or ad-hoc "
                "capture cannot establish what was watched."
            )
        observer_path = Path(__file__).resolve().parent / "observe_reference.mjs"
        expected_observer_sha = file_sha256(observer_path)[1]
        if payload.get("producer_script_sha256") != expected_observer_sha:
            problems.append(
                f"{observation_label} does not bind the current packaged "
                "observe_reference.mjs bytes; a tool-name string alone is not provenance."
            )
        if payload.get("schema_version") != REFERENCE_OBSERVATION_SCHEMA:
            problems.append(
                f"{observation_label} must use observation schema_version "
                f"{REFERENCE_OBSERVATION_SCHEMA}; an older session has no mechanism "
                "sheet and cannot say what the site does."
            )
        if payload.get("id") != expected_reference_id:
            problems.append(
                f"{observation_label} reference ID must be {expected_reference_id!r}."
            )
        problems.extend(
            f"{observation_label}: {failure}"
            for failure in packaged_runtime_record_failures(
                payload, tool="observe_reference.mjs"
            )
        )
        frames = payload.get("frames")
        frame_dir = payload.get("frame_dir")
        if not isinstance(frames, list) or not frames or not isinstance(frame_dir, str):
            problems.append(f"{observation_label} must bind its captured frame artifacts.")
        else:
            for frame_index, frame in enumerate(frames, start=1):
                if (
                    not isinstance(frame, dict)
                    or not isinstance(frame.get("file"), str)
                    or not isinstance(frame.get("sha256"), str)
                    or SHA256_HEX.fullmatch(frame["sha256"]) is None
                ):
                    problems.append(f"{observation_label} frame {frame_index} metadata is invalid.")
                    continue
                frame_path = artifact.parent / frame_dir / frame["file"]
                try:
                    if file_sha256(frame_path)[1] != frame["sha256"]:
                        problems.append(f"{observation_label} frame {frame_index} SHA-256 drifted.")
                    verify_png_artifact(frame_path)
                except (OSError, StateError) as exc:
                    problems.append(f"{observation_label} frame {frame_index} is invalid: {exc}")
        observed_url = payload.get("url")
        if not isinstance(observed_url, str) or not observed_url:
            problems.append(f"{observation_label} must record the observed URL.")
        else:
            row_host = urlsplit(row_url.strip()).netloc.casefold().removeprefix("www.")
            obs_host = urlsplit(observed_url).netloc.casefold().removeprefix("www.")
            search = re.search(r"https?://[^\s)]+", row_url)
            if not row_host and search is not None:
                row_host = urlsplit(search.group(0)).netloc.casefold().removeprefix("www.")
            if row_host and obs_host and row_host != obs_host:
                problems.append(
                    f"{observation_label} observed {obs_host}, which is not the "
                    "site this row names."
                )
        interactions = payload.get("interactions")
        if isinstance(interactions, list):
            for interaction in interactions:
                if not isinstance(interaction, dict):
                    continue
                inner_url = interaction.get("url")
                if (
                    interaction.get("type") == "transition"
                    and isinstance(inner_url, str)
                    and inner_url
                ):
                    observed_inner_urls.append(inner_url)
        coverage = payload.get("coverage")
        if not isinstance(coverage, dict):
            problems.append(f"{observation_label} must record what the session covered.")
        else:
            if not coverage.get("rest"):
                problems.append(f"{observation_label} must include an at-rest observation.")
            holds = coverage.get("scroll_holds")
            if not isinstance(holds, int) or holds < REFERENCE_OBSERVATION_MIN_HOLDS:
                problems.append(
                    f"{observation_label} must hold the page still at at least "
                    f"{REFERENCE_OBSERVATION_MIN_HOLDS} scroll positions; a teleported "
                    "screenshot cannot show what animates into place."
                )
            hovers = coverage.get("hovers")
            if not isinstance(hovers, int) or hovers < 1:
                problems.append(
                    f"{observation_label} must hover at least one interactive "
                    "element; hover state is invisible in a still."
                )
        motion = payload.get("motion")
        if not isinstance(motion, dict) or not isinstance(motion.get("observed"), bool):
            problems.append(f"{observation_label} must record whether motion was observed.")
        elif kind == "motion" and not motion.get("observed"):
            problems.append(
                f"{label} claims a motion signature, but its observation session "
                "recorded no motion at rest, on any scroll hold, on hover, or on "
                "transition. Record what was actually seen instead of the motion "
                "the site was assumed to have."
            )
        first_screens = payload.get("first_screens")
        if (
            not isinstance(first_screens, dict)
            or set(first_screens) != {"wide", "narrow"}
            or any(
                not isinstance(first_screens.get(viewport), dict)
                or not isinstance(first_screens[viewport].get("grid"), list)
                for viewport in ("wide", "narrow")
            )
        ):
            problems.append(
                f"{observation_label} must carry distinct wide and narrow "
                "first-screen structures; a desktop-only observation cannot "
                "source the mobile design."
            )
        else:
            wide_viewport = first_screens["wide"].get("viewport", {})
            narrow_viewport = first_screens["narrow"].get("viewport", {})
            if (
                not isinstance(wide_viewport, dict)
                or not isinstance(narrow_viewport, dict)
                or not isinstance(wide_viewport.get("w"), (int, float))
                or not isinstance(narrow_viewport.get("w"), (int, float))
                or wide_viewport["w"] < 900
                or narrow_viewport["w"] > 600
                or wide_viewport["w"] <= narrow_viewport["w"]
            ):
                problems.append(
                    f"{observation_label} first-screen structures do not prove "
                    "distinct wide and narrow viewport observations."
                )
        mechanisms = payload.get("mechanisms")
        score = payload.get("score")
        mechanisms_by_viewport = payload.get("mechanisms_by_viewport")
        if (
            not isinstance(mechanisms_by_viewport, dict)
            or set(mechanisms_by_viewport) != {"wide", "narrow"}
            or any(
                not isinstance(mechanisms_by_viewport.get(viewport), dict)
                or not isinstance(
                    mechanisms_by_viewport[viewport].get("mechanisms"), list
                )
                or not isinstance(mechanisms_by_viewport[viewport].get("score"), dict)
                for viewport in ("wide", "narrow")
            )
        ):
            problems.append(
                f"{observation_label} must carry wide and narrow mechanism reads."
            )
        first_screen_mechanisms = payload.get("first_screen_mechanisms_by_viewport")
        states_by_viewport = payload.get("states_by_viewport")
        if (
            not isinstance(first_screen_mechanisms, dict)
            or set(first_screen_mechanisms) != {"wide", "narrow"}
            or any(
                not isinstance(first_screen_mechanisms.get(viewport), dict)
                or not isinstance(first_screen_mechanisms[viewport].get("mechanisms"), list)
                or not isinstance(first_screen_mechanisms[viewport].get("score"), dict)
                for viewport in ("wide", "narrow")
            )
        ):
            problems.append(
                f"{observation_label} must carry wide and narrow first-screen mechanism reads."
            )
        if (
            not isinstance(states_by_viewport, dict)
            or set(states_by_viewport) != {"wide", "narrow"}
            or any(
                not isinstance(states_by_viewport.get(viewport), dict)
                or "rest" not in states_by_viewport[viewport]
                for viewport in ("wide", "narrow")
            )
        ):
            problems.append(
                f"{observation_label} must carry explicit source-state evidence at wide and narrow viewports."
            )
        state_contract = payload.get("state_contract")
        contract_payload: object = None
        contract_ids: set[str] = set()
        if (
            not isinstance(state_contract, dict)
            or set(state_contract) != {"file", "sha256"}
            or not isinstance(state_contract.get("file"), str)
            or not isinstance(state_contract.get("sha256"), str)
            or SHA256_HEX.fullmatch(state_contract["sha256"]) is None
        ):
            problems.append(f"{observation_label} must bind its explicit source-state contract.")
        else:
            # Browser producers intentionally store the sibling filename so a
            # private evidence directory can move as one immutable unit.
            contract_path = (
                artifact.parent / PurePosixPath(state_contract["file"])
            ).resolve()
            expected_contract = (
                project
                / ".design-dna"
                / "references"
                / f"{expected_reference_id}-state-contract.json"
            ).resolve()
            if (
                not is_within(contract_path, project.resolve())
                or contract_path != expected_contract
                or not contract_path.is_file()
                or file_sha256(contract_path)[1] != state_contract["sha256"]
            ):
                problems.append(f"{observation_label} source-state contract bytes are missing or drifted.")
            else:
                try:
                    contract_payload = json.loads(
                        contract_path.read_text(encoding="utf-8")
                    )
                except (OSError, ValueError) as exc:
                    problems.append(
                        f"{observation_label} source-state contract is unreadable: {exc}"
                    )
                else:
                    contract_problems, contract_ids = reference_state_contract_failures(
                        contract_payload,
                        expected_reference_id=expected_reference_id,
                        expected_primary_url=(
                            observed_url if isinstance(observed_url, str) else None
                        ),
                    )
                    problems.extend(
                        f"{observation_label}: {problem}"
                        for problem in contract_problems
                    )
        if contract_ids and isinstance(states_by_viewport, dict):
            contract_states = {
                state.get("id"): state
                for state in (
                    contract_payload.get("states", [])
                    if isinstance(contract_payload, dict)
                    else []
                )
                if isinstance(state, dict)
            }
            for viewport in ("wide", "narrow"):
                state_map = states_by_viewport.get(viewport)
                if not isinstance(state_map, dict) or set(state_map) != contract_ids:
                    problems.append(
                        f"{observation_label} {viewport} states are not the exact source-state contract."
                    )
                    continue
                for state_id, state_evidence in state_map.items():
                    source_state = contract_states.get(state_id)
                    if (
                        not isinstance(state_evidence, dict)
                        or not isinstance(source_state, dict)
                        or any(
                            state_evidence.get(field) != source_state.get(field)
                            for field in ("id", "url", "kind", "trigger", "expectation")
                        )
                        or not isinstance(state_evidence.get("trigger_application"), dict)
                        or state_evidence["trigger_application"].get("applied") is not True
                        or not isinstance(state_evidence.get("trigger_evidence"), dict)
                        or not isinstance(state_evidence.get("evidence_frames"), dict)
                        or set(state_evidence.get("evidence_frames", {}))
                        != {"before", "after", "settled"}
                        or any(
                            not isinstance(frame, dict)
                            or not isinstance(frame.get("file"), str)
                            or type(frame.get("bytes")) is not int
                            or not isinstance(frame.get("sha256"), str)
                            for frame in state_evidence.get("evidence_frames", {}).values()
                        )
                        or not isinstance(state_evidence.get("interaction_census"), dict)
                        or state_evidence["interaction_census"].get("complete") is not True
                        or state_evidence["interaction_census"].get("truncated") is not False
                        or not isinstance(state_evidence.get("structure"), dict)
                        or not isinstance(state_evidence.get("mechanisms"), list)
                        or not isinstance(state_evidence.get("score"), dict)
                        or not isinstance(state_evidence.get("scroll_traversal"), dict)
                        or state_evidence["scroll_traversal"].get("complete") is not True
                    ):
                        problems.append(
                            f"{observation_label} {viewport}/{state_id} did not execute and capture its exact source state."
                        )
        navigations = payload.get("navigations")
        if not isinstance(navigations, list) or not navigations:
            problems.append(f"{observation_label} must carry exact navigation evidence.")
        else:
            for navigation in navigations:
                if (
                    not isinstance(navigation, dict)
                    or navigation.get("requested_normalized_url")
                    != navigation.get("final_normalized_url")
                    or navigation.get("response_final_normalized_url")
                    != navigation.get("final_normalized_url")
                    or type(navigation.get("final_status")) is not int
                    or not 200 <= navigation["final_status"] < 300
                    or navigation.get("redirect_count") != 0
                ):
                    problems.append(
                        f"{observation_label} navigation ledger contains a redirect, rewrite, or failed response."
                    )
                    break
        traversals = payload.get("site_traversal_by_viewport")
        traversal_urls: dict[str, set[str]] = {}
        if (
            not isinstance(traversals, dict)
            or set(traversals) != {"wide", "narrow"}
        ):
            problems.append(
                f"{observation_label} must recursively traverse the source at wide and narrow widths."
            )
        else:
            for viewport in ("wide", "narrow"):
                traversal = traversals.get(viewport)
                if not isinstance(traversal, dict):
                    problems.append(f"{observation_label} {viewport} traversal is invalid.")
                    continue
                discovered = traversal.get("discovered_urls")
                visited = traversal.get("visited_urls")
                pages = traversal.get("pages")
                if (
                    traversal.get("profile") != viewport
                    or traversal.get("complete") is not True
                    or traversal.get("missing_urls") != []
                    or not isinstance(discovered, list)
                    or not isinstance(visited, list)
                    or discovered != visited
                    or len(discovered) != len(set(discovered))
                    or not isinstance(pages, list)
                    or len(pages) != len(visited)
                ):
                    problems.append(
                        f"{observation_label} {viewport} recursive page coverage does not reconcile."
                    )
                    continue
                observed_inner_urls.extend(
                    url for url in visited if isinstance(url, str)
                )
                traversal_urls[viewport] = {
                    url for url in visited if isinstance(url, str)
                }
                for page_record in pages:
                    if (
                        not isinstance(page_record, dict)
                        or page_record.get("url") not in visited
                        or not isinstance(page_record.get("state_inventory"), dict)
                        or page_record["state_inventory"].get("complete") is not True
                        or page_record["state_inventory"].get("unreconciled") != []
                        or not isinstance(page_record.get("scroll_traversal"), dict)
                        or page_record["scroll_traversal"].get("complete") is not True
                    ):
                        problems.append(
                            f"{observation_label} {viewport} page traversal has unreconciled state or scroll evidence."
                        )
                        break
        interaction_census = payload.get("interaction_census_by_viewport")
        interaction_frame_dir = payload.get("frame_dir")
        interaction_artifacts = {
            (
                (PurePosixPath(interaction_frame_dir) / PurePosixPath(frame.get("file"))).as_posix(),
                frame.get("bytes"),
                frame.get("sha256"),
            )
            for frame in payload.get("frames", [])
            if isinstance(frame, dict)
            and isinstance(interaction_frame_dir, str)
            and isinstance(frame.get("file"), str)
            and type(frame.get("bytes")) is int
            and isinstance(frame.get("sha256"), str)
        }
        if (
            not isinstance(interaction_census, dict)
            or set(interaction_census) != {"wide", "narrow"}
        ):
            problems.append(
                f"{observation_label} must carry a generated wide/narrow interaction census."
            )
        else:
            for viewport in ("wide", "narrow"):
                problems.extend(
                    f"{observation_label}: {problem}"
                    for problem in interaction_census_failures(
                        interaction_census.get(viewport),
                        expected_profile=viewport,
                        expected_state_ids=contract_ids,
                        expected_urls=traversal_urls.get(viewport),
                        artifact_root=artifact.parent,
                        allowed_artifacts=interaction_artifacts,
                    )
                )
        rendered_qa_by_viewport = payload.get("rendered_qa_by_viewport")
        if (
            not isinstance(rendered_qa_by_viewport, dict)
            or set(rendered_qa_by_viewport) != {"wide", "narrow"}
        ):
            problems.append(
                f"{observation_label} must carry generated wide/narrow rendered QA."
            )
        else:
            for viewport in ("wide", "narrow"):
                viewport_interaction = (
                    interaction_census.get(viewport)
                    if isinstance(interaction_census, dict)
                    else None
                )
                problems.extend(
                    f"{observation_label}: {problem}"
                    for problem in source_rendered_qa_failures(
                        rendered_qa_by_viewport.get(viewport),
                        expected_profile=viewport,
                        expected_urls=traversal_urls.get(viewport, set()),
                        artifact_root=artifact.parent,
                        allowed_artifacts=interaction_artifacts,
                        interaction_census=viewport_interaction,
                    )
                )
                state_map = (
                    states_by_viewport.get(viewport)
                    if isinstance(states_by_viewport, dict)
                    else None
                )
                if isinstance(state_map, dict):
                    for source_state_id, state_evidence in state_map.items():
                        if not isinstance(state_evidence, dict):
                            continue
                        state_url = state_evidence.get("url")
                        state_interaction = state_evidence.get("interaction_census")
                        problems.extend(
                            f"{observation_label} {viewport}/{source_state_id}: {problem}"
                            for problem in source_rendered_qa_failures(
                                state_evidence.get("rendered_qa"),
                                expected_profile=viewport,
                                expected_urls={str(state_url)} if isinstance(state_url, str) else set(),
                                artifact_root=artifact.parent,
                                allowed_artifacts=interaction_artifacts,
                                interaction_census=state_interaction,
                            )
                        )
        if not isinstance(mechanisms, list) or not isinstance(score, dict):
            problems.append(
                f"{observation_label} must carry a mechanism sheet and a score; "
                "a session without them only proves that something moved."
            )
        elif kind == "motion":
            distinct = score.get("distinct_mechanisms")
            coverage = score.get("scroll_coverage")
            if not isinstance(distinct, int) or distinct < REFERENCE_MECHANISM_MIN_DISTINCT:
                problems.append(
                    f"{label} is a thin site: its session recorded "
                    f"{distinct if isinstance(distinct, int) else 0} distinct "
                    f"mechanism(s) and the floor is {REFERENCE_MECHANISM_MIN_DISTINCT}. "
                    "A site that does one thing, or nothing, is not a reference "
                    "for behavior; drop it and keep looking."
                )
            if (
                not isinstance(coverage, (int, float))
                or coverage < REFERENCE_MECHANISM_MIN_COVERAGE
            ):
                problems.append(
                    f"{label} is a thin site: scroll choreography was active on "
                    f"{coverage if isinstance(coverage, (int, float)) else 0} of "
                    f"its depth and the floor is {REFERENCE_MECHANISM_MIN_COVERAGE}. "
                    "One animated hero over a static page is the generic shape."
                )
        return problems

    def signature_failures(cell: str, label: str, observed_kind: str) -> list[str]:
        """Require an honest motion or static signature, never forced motion."""

        normalized = " ".join(cell.strip().split())
        kind, separator, claim = normalized.partition(":")
        kind = kind.casefold()
        if not separator or kind not in {"motion", "static"}:
            return [f"{label} signature must begin with `motion:` or `static:`."]
        problems: list[str] = []
        if observed_kind in {"motion", "static"} and kind != observed_kind:
            problems.append(
                f"{label} signature is {kind}, but its observed-evidence lane is "
                f"{observed_kind}; the evidence type and claim must agree."
            )
        if len(claim.strip()) < 60:
            problems.append(
                f"{label} signature must name the dominant element, relationship, "
                "trigger where applicable, and visible result in concrete detail."
            )
        if kind == "motion" and REFERENCE_SIGNATURE_VERBS.search(claim) is None:
            problems.append(
                f"{label} motion signature must name the actual interaction or "
                "sequence the observation recorded."
            )
        if kind == "static":
            if (
                REFERENCE_STATIC_SIGNATURE_TERMS.search(claim) is None
                or REFERENCE_STATIC_RELATIONSHIP_TERMS.search(claim) is None
            ):
                problems.append(
                    f"{label} static signature must name a concrete composition, "
                    "type, media, color, hierarchy, and spatial relationship; "
                    "a subject, palette, or mood is not a signature."
                )
        return problems

    strong_headers, strong_rows = markdown_first_table(
        sections.get("Strong references", "")
    )
    source_by_rank: dict[int, str] = {}
    kind_by_rank: dict[str, str] = {}
    measured_by_rank: dict[int, set[float]] = {}
    signature_by_rank: dict[int, str] = {}
    wide_capture_by_rank: dict[int, str] = {}
    narrow_capture_by_rank: dict[int, str] = {}
    styles_by_rank: dict[int, str] = {}
    observation_by_rank: dict[int, str] = {}
    strong_urls: set[str] = set()
    curation_by_source = reference_source_curation()
    strong_count = max(len(strong_rows), REFERENCE_MINIMUM_STRONG)
    if (
        strong_headers != REFERENCE_DOSSIER_STRONG_HEADERS
        or len(strong_rows) < REFERENCE_MINIMUM_STRONG
    ):
        failures.append(
            "Reference dossier needs at least six strong-reference rows using "
            "the public-reference table contract; the floor keeps any single "
            "site from becoming the template."
        )
    else:
        ranks: list[int] = []
        sources: list[str] = []
        live_hosts: dict[str, int] = {}
        for row_number, row in enumerate(strong_rows, start=1):
            label = f"Reference dossier strong row {row_number}"
            if len(row) != len(REFERENCE_DOSSIER_STRONG_HEADERS) or any(
                not non_placeholder(cell) for cell in row
            ):
                failures.append(f"{label} is incomplete.")
                continue
            source_cell = row[3].strip()
            source_id = source_cell.split(";", 1)[0].strip().casefold()
            accolade = source_cell.split(";", 1)[1].strip() if ";" in source_cell else ""
            sources.append(source_id)
            curation = curation_by_source.get(source_id, "submission")
            if curation not in REFERENCE_CURATION_ALLOWED:
                failures.append(
                    f"{label} takes its reference from {source_id!r}, an open "
                    "submission feed. A listing there means somebody sent it "
                    "in, not that it is good. Select from an award or curated "
                    "source; quality is the first filter and register the "
                    "second."
                )
            if len(accolade) < 8:
                failures.append(
                    f"{label} must record what this site won or why the "
                    "source's editor chose it, after a semicolon, e.g. "
                    "`awwwards; Site of the Day 2026-08-14`."
                )
            if not row[0].isdigit():
                failures.append(
                    f"{label} rank must be an integer from 1 through {len(strong_rows)}."
                )
            else:
                rank = int(row[0])
                ranks.append(rank)
                source_by_rank[rank] = source_id
            failures.extend(reference_entry_url_failures(row[2], f"{label} URL"))
            if source_id not in active_source_ids:
                failures.append(
                    f"{label} discovery source must be an active public source ID."
                )
            failures.extend(reference_dossier_date_failures(row[4], label))
            failures.extend(
                reference_entry_access_failures(row[5], label, authorized_basis)
            )
            failures.extend(capture_pair_failures(row[6], row[7], label))
            failures.extend(study_scope_failures(row[8], f"{label} study scope"))
            failures.extend(
                observation_failures(
                    row[9],
                    label,
                    row[2],
                    f"strong-{row[0]}" if row[0].isdigit() else "",
                )
            )
            style_problems, style_numbers = measured_styles_failures(
                row[10], label=label, project=project, record_path=record_path
            )
            failures.extend(style_problems)
            if row[0].isdigit():
                measured_by_rank[int(row[0])] = style_numbers
                wide_capture_by_rank[int(row[0])] = row[6].strip()
                narrow_capture_by_rank[int(row[0])] = row[7].strip()
                styles_by_rank[int(row[0])] = row[10].strip()
                observation_by_rank[int(row[0])] = row[9].partition(";")[2].strip()
            observed_kind = row[9].split(";", 1)[0].strip().casefold()
            failures.extend(signature_failures(row[11], label, observed_kind))
            failures.extend(brief_fit_failures(row[12], f"{label} brief relevance"))
            if row[0].isdigit():
                signature_by_rank[int(row[0])] = row[11]
            kind_by_rank[row[0]] = observed_kind
            access = row[5].split(";", 1)[0].strip().casefold()
            url_match = re.search(r"https://[^\s)]+", row[2])
            if access == "public-live" and url_match is not None:
                host = urlsplit(url_match.group(0)).netloc.casefold()
                if host in live_hosts:
                    failures.append(
                        f"{label} points at the same host as strong row "
                        f"{live_hosts[host]}; one live site cannot fill "
                        "several rows."
                    )
                else:
                    live_hosts[host] = row_number
            if url_match is not None:
                strong_url = url_match.group(0).rstrip(".,;|")
                strong_urls.add(strong_url)
                if strong_url not in selected_candidate_urls:
                    failures.append(
                        f"{label} was not selected in Candidate comparison. "
                        "A strong row cannot bypass the compared finalist set."
                    )
        if sorted(ranks) != list(range(1, len(strong_rows) + 1)):
            failures.append(
                "Reference dossier strong rows must contain each rank from 1 "
                f"through {len(strong_rows)} exactly once."
            )
        active_used = {source for source in sources if source in active_source_ids}
        if len(active_used) < REFERENCE_MINIMUM_SOURCES:
            failures.append(
                "Reference dossier strong rows must come from at least three "
                "distinct active public sources."
            )
        counts: dict[str, int] = {}
        for source in sources:
            counts[source] = counts.get(source, 0) + 1
        for source, count in counts.items():
            if count * 2 > len(strong_rows):
                failures.append(
                    f"Reference dossier source {source!r} supplies more than "
                    "half of the strong rows; spread the set so no single "
                    "source is the template."
                )

    negative_headers, negative_rows = markdown_first_table(
        sections.get("Negative counterexamples", "")
    )
    if (
        negative_headers != REFERENCE_DOSSIER_NEGATIVE_HEADERS
        or len(negative_rows) < REFERENCE_MINIMUM_NEGATIVE
    ):
        failures.append(
            "Reference dossier needs at least three negative counterexample rows "
            "using the public-reference table contract."
        )
    else:
        for row_number, row in enumerate(negative_rows, start=1):
            label = f"Reference dossier negative row {row_number}"
            if len(row) != len(REFERENCE_DOSSIER_NEGATIVE_HEADERS) or any(
                not non_placeholder(cell) for cell in row
            ):
                failures.append(f"{label} is incomplete.")
                continue
            failures.extend(reference_entry_url_failures(row[1], f"{label} URL"))
            negative_source = row[2].split(";", 1)[0].strip().casefold()
            if negative_source not in active_source_ids:
                failures.append(
                    f"{label} discovery source must be an active public source ID."
                )
            failures.extend(reference_dossier_date_failures(row[3], label))
            failures.extend(
                reference_entry_access_failures(row[4], label, authorized_basis)
            )
            failures.extend(capture_failures(row[5], label))

    synthesis = sections.get("Selected synthesis", "")
    selected_value = markdown_label_value(synthesis, "Selected positive ranks")
    selected_ranks = reference_rank_values(
        selected_value or "", maximum=strong_count
    )
    if selected_ranks is None or len(selected_ranks) < REFERENCE_MINIMUM_SELECTED:
        failures.append(
            "Reference dossier must select at least four distinct positive ranks "
            "so the synthesis merges several sites rather than copying one."
        )
        selected_ranks = set()
    elif source_by_rank:
        selected_sources = {
            source_by_rank[rank] for rank in selected_ranks if rank in source_by_rank
        }
        if len(selected_sources) < REFERENCE_MINIMUM_SELECTED_SOURCES:
            failures.append(
                "Reference dossier selected references must come from at least "
                "two distinct sources."
            )
    for label in (
        "Project-specific organizing synthesis",
        "Dominant visual grammar by route",
        "Interaction or motion copied and where it is rendered, or static posture with evidence",
        "Negative-counterevidence result",
        "Combination of references",
        "Execution improvements only",
        "Direction record path and status",
    ):
        value = markdown_label_value(synthesis, label)
        if not non_placeholder(value):
            failures.append(f"Reference dossier {label!r} is missing or still scaffold text.")
        elif label == "Combination of references":
            failures.extend(
                combination_failures(value, f"Reference dossier {label!r}")
            )
    synthesis_headers, synthesis_rows = markdown_first_table(synthesis)
    if synthesis_headers != REFERENCE_DOSSIER_SYNTHESIS_HEADERS or not synthesis_rows:
        failures.append(
            "Reference dossier needs a selected-synthesis decision map using the exact table contract."
        )
    else:
        mapped_ranks: set[int] = set()
        for row_number, row in enumerate(synthesis_rows, start=1):
            label = f"Reference dossier synthesis row {row_number}"
            if len(row) != len(REFERENCE_DOSSIER_SYNTHESIS_HEADERS) or any(
                not non_placeholder(cell) for cell in row
            ):
                failures.append(f"{label} is incomplete.")
                continue
            row_ranks = reference_rank_values(row[0], maximum=strong_count)
            if row_ranks is None or not row_ranks.issubset(selected_ranks):
                failures.append(
                    f"{label} must name only selected positive ranks."
                )
            else:
                mapped_ranks.update(row_ranks)
        missing_mapped = sorted(selected_ranks - mapped_ranks)
        if missing_mapped:
            failures.append(
                "Reference dossier selected ranks need a mapped project decision: "
                + ", ".join(str(rank) for rank in missing_mapped)
            )

    route_manifest_section = sections.get("Route manifest", "")
    route_manifest_cell = markdown_label_value(
        route_manifest_section, "Route manifest"
    )
    route_proof_identity = markdown_label_value(
        route_manifest_section, "First-screen proof build ID and primary route key"
    )
    route_payload: dict[str, object] | None = None
    route_path: Path | None = None
    if not non_placeholder(route_manifest_cell):
        failures.append(
            "Reference dossier Route manifest must bind "
            ".design-dna/route-manifest.json plus its SHA-256."
        )
    elif not non_placeholder(route_proof_identity):
        failures.append(
            "Reference dossier needs the first-screen proof build ID and primary route key."
        )
    else:
        route_failures, route_payload, route_path = bound_route_manifest_failures(
            route_manifest_cell or "",
            project=project,
            record_path=record_path,
            selected_ranks=selected_ranks,
        )
        failures.extend(route_failures)
    visible_section = sections.get("Preimplementation visible decisions", "")
    visible_cell = markdown_label_value(
        visible_section, "Visible decision source manifest"
    )
    if not non_placeholder(visible_cell):
        failures.append(
            "Reference dossier must bind the preimplementation Visible decision source manifest."
        )
    elif isinstance(route_payload, dict) and route_path is not None:
        visible_artifact, visible_binding_failures = bound_artifact(
            visible_cell or "",
            project=project,
            record_path=record_path,
            label="Visible decision source manifest",
        )
        failures.extend(visible_binding_failures)
        expected_visible = (project / ".design-dna" / "visible-decision-sources.json").resolve()
        if visible_artifact is not None:
            if visible_artifact.resolve() != expected_visible:
                failures.append(
                    "Visible decision source manifest must use .design-dna/visible-decision-sources.json."
                )
            else:
                try:
                    visible_payload = json.loads(
                        visible_artifact.read_text(encoding="utf-8")
                    )
                except (OSError, ValueError) as exc:
                    failures.append(
                        f"Visible decision source manifest is unreadable: {exc}"
                    )
                else:
                    failures.extend(
                        visible_decision_source_manifest_failures(
                            visible_payload,
                            project=project,
                            route_manifest=route_payload,
                            route_manifest_path=route_path,
                            proof_identity=route_proof_identity or "",
                        )
                    )
    dominant_grammar = markdown_label_value(
        synthesis, "Dominant visual grammar by route"
    ) or ""
    if isinstance(route_payload, dict) and isinstance(route_payload.get("routes"), list):
        for route in route_payload["routes"]:
            if not isinstance(route, dict):
                continue
            key = str(route.get("key") or "")
            rank = route.get("mapped_reference_rank")
            if key and (
                re.search(rf"\b{re.escape(key)}\b", dominant_grammar, re.I) is None
                or re.search(rf"\b(?:rank\s*)?{rank}\b", dominant_grammar, re.I) is None
            ):
                failures.append(
                    f"Reference dossier dominant grammar must name route {key!r} "
                    f"and its mapped selected rank {rank}."
                )

    # Every component that ships has a source line. A component with none is
    # the producer's own design, and that needs the owner's words, quoted.
    component_section = sections.get("Component sources", "")
    component_headers, component_rows = markdown_first_table(component_section)
    component_ranks: dict[str, set[int]] = {}
    if PRODUCER_DESIGN_MARKER.search(component_section or ""):
        failures.append(
            "Reference dossier Component sources names an owner-approved part. "
            + PRODUCER_DESIGN_ORDER
        )
    if tuple(component_headers) not in REFERENCE_DOSSIER_COMPONENT_HEADER_VARIANTS or not component_rows:
        failures.append(
            "Reference dossier needs a Component sources table using the exact "
            "contract; a build whose parts have no source is the producer's own "
            "design."
        )
    else:
        covered: set[str] = set()
        for row_number, row in enumerate(component_rows, start=1):
            label = f"Reference dossier component row {row_number}"
            if len(row) != len(REFERENCE_DOSSIER_COMPONENT_HEADERS) or any(
                not non_placeholder(cell) for cell in row
            ):
                failures.append(f"{label} is incomplete.")
                continue
            component = row[0].strip().casefold()
            covered.add(component)
            source = row[1].strip()
            frame_cell = row[2].strip()
            structure = row[3].strip()
            if COMPONENT_STRUCTURE_WORDS.search(structure) is None:
                failures.append(
                    f"{label} structure column must say how the part is "
                    "arranged (what fills the screen, what sits at which edge, "
                    "how the space is divided), not what size it is. A build "
                    "can reproduce every font size and still be the producer's "
                    "own layout."
                )
            if PRODUCER_DESIGN_MARKER.search(source) or PRODUCER_DESIGN_MARKER.search(frame_cell):
                failures.append(
                    f"{label} ({row[0].strip()}) is the producer's own design. "
                    + PRODUCER_DESIGN_ORDER
                )
                continue
            failures.extend(
                component_frame_failures(
                    frame_cell,
                    label=label,
                    source=source,
                    project=project,
                    selected_ranks=selected_ranks,
                    strong_count=strong_count,
                )
            )
            row_ranks = reference_rank_values(source, maximum=strong_count)
            if row_ranks:
                component_ranks[component] = set(row_ranks)
            if row_ranks is None or not row_ranks.issubset(selected_ranks):
                failures.append(
                    f"{label} must name a selected reference rank as its "
                    "source. There is no other kind of source: a part no "
                    "reference shows is a part to observe on one, or to cut."
                )
            failures.extend(
                component_value_failures(
                    row[4],
                    label=label,
                    ranks=(row_ranks or set()),
                    measured=measured_by_rank,
                )
            )
            if len(row[4].strip()) < 24:
                failures.append(
                    f"{label} must reproduce the recorded values it takes "
                    "(sizes, distances, durations, easings, counts), not a "
                    "paraphrase of the reference."
                )
        missing_components = [
            name for name in REFERENCE_DOSSIER_REQUIRED_COMPONENTS if name not in covered
        ]
        if missing_components:
            failures.append(
                "Reference dossier Component sources must cover: "
                + ", ".join(missing_components)
                + ". A part with no source line does not ship."
            )
        failures.extend(
            component_census_failures(
                component_section,
                project=project,
                record_path=record_path,
                covered=covered,
            )
        )

    # Every gate above proves the producer looked, measured, and cited. None of
    # them asks which PART of each reference arrived, which is how two of six
    # references reached a shipped build as a background colour and a set of
    # control dimensions.
    failures.extend(
        signature_transfer_failures(
            sections.get("Signature transfer", ""),
            project=project,
            record_path=record_path,
            selected_ranks=selected_ranks or set(),
            signature_by_rank=signature_by_rank,
            census_names=census_component_names(
                sections.get("Component sources", ""),
                project=project,
                record_path=record_path,
            ),
            component_ranks=component_ranks,
        )
    )

    # The recording is the watching, and the watching is enforced by count:
    # a line per sheet, an inventory of what the site does, and a signature
    # located on sheets that exist.
    failures.extend(
        sequence_read_failures(
            sections.get(REFERENCE_SEQUENCE_SECTION, ""),
            sections.get("Component sources", ""),
            project=project,
            record_path=record_path,
            selected_ranks=selected_ranks or set(),
            kind_by_rank=kind_by_rank,
            wide_capture_by_rank=wide_capture_by_rank,
            narrow_capture_by_rank=narrow_capture_by_rank,
            styles_by_rank=styles_by_rank,
            observation_by_rank=observation_by_rank,
        )
    )
    failures.extend(
        interaction_census_section_failures(
            sections.get("Interaction census", ""),
            project=project,
            record_path=record_path,
            selected_ranks=selected_ranks or set(),
            observation_by_rank=observation_by_rank,
        )
    )

    # A producer that only ever watched home pages has no evidence for an
    # inner page, and will design one while believing it is still copying.
    inner = {
        url for url in observed_inner_urls
        if urlsplit(url).path.strip("/") not in {"", "index.html", "index.php"}
    }
    if len(inner) < REFERENCE_INNER_PAGE_MINIMUM:
        failures.append(
            "Reference dossier must observe at least "
            f"{REFERENCE_INNER_PAGE_MINIMUM} INNER pages across its selected "
            f"references; it observed {len(inner)}. Every real site has more "
            "than one page, and a producer holding only home-page captures "
            "will invent every inner page it builds."
        )
    return failures


def packaged_runtime_record_failures(
    payload: object,
    *,
    tool: str,
    require_pass: bool = False,
) -> list[str]:
    if not isinstance(payload, dict):
        return [f"Evidence must contain a {tool} object."]
    script = Path(__file__).resolve().parent / tool
    if not script.is_file():
        return [f"Packaged producer is missing: {tool}."]
    schema = packaged_script_schema_version(script)
    failures: list[str] = []
    if payload.get("tool") != tool:
        failures.append(f"Evidence tool must be {tool}.")
    if schema is None or payload.get("schema_version") != schema:
        failures.append(f"Evidence schema must match current {tool} schema {schema}.")
    if payload.get("producer_script_sha256") != file_sha256(script)[1]:
        failures.append(f"Evidence does not bind current {tool} bytes.")
    runtime = payload.get("runtime_identity")
    if not isinstance(runtime, dict) or runtime.get(tool) != file_sha256(script)[1]:
        failures.append(f"Evidence runtime_identity does not include current {tool}.")
    else:
        scripts = Path(__file__).resolve().parent
        dependencies = payload.get("dependencies")
        for name, digest in runtime.items():
            dependency = scripts / str(name)
            if dependency.is_file():
                if (
                    not isinstance(digest, str)
                    or file_sha256(dependency)[1] != digest
                ):
                    failures.append(f"Evidence runtime dependency drifted: {name}.")
                continue
            external: object = None
            if isinstance(dependencies, dict) and name == "playwright-entry":
                external = dependencies.get("playwright")
            elif isinstance(dependencies, dict) and name == "browser-executable":
                external = dependencies.get("browser_executable")
            if not isinstance(external, dict):
                failures.append(f"Evidence runtime dependency is unrecognized: {name}.")
                continue
            external_file = external.get("resolved_file") or external.get("file")
            external_digest = external.get("sha256") or external.get(
                "resolved_file_sha256"
            )
            try:
                external_path = Path(str(external_file)).resolve()
            except (OSError, ValueError):
                external_path = Path()
            if (
                not isinstance(digest, str)
                or digest != external_digest
                or SHA256_HEX.fullmatch(digest) is None
                or not external_path.is_file()
                or file_sha256(external_path)[1] != digest
            ):
                failures.append(f"Evidence runtime dependency drifted: {name}.")
    if require_pass and not (
        payload.get("pass") is True or payload.get("ok") is True
    ):
        failures.append(f"Evidence from {tool} did not pass.")
    return failures


def measured_styles_failures(
    cell: str, *, label: str, project: Path, record_path: Path
) -> tuple[list[str], set[float]]:
    """A reference binds a machine extraction of its live CSS.

    This is the answer to "never build off a screenshot". A still carries
    caption alignment, a radius and a colour impression; everything else the
    producer fills in from memory while believing it is copying. The numbers a
    build claims to reproduce are checked against this record.
    """
    value = cell.strip()
    if not non_placeholder(value):
        return ([
            f"{label} must bind the {REFERENCE_STYLE_TOOL} record for this "
            "reference, read from the live page. A build made from a "
            "screenshot reproduces what a screenshot carries and invents the "
            "rest."
        ], set())
    artifact, artifact_failures = bound_artifact(
        value, project=project, record_path=record_path, label=label
    )
    if artifact_failures or artifact is None:
        return (artifact_failures, set())
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ([f"{label} measured styles are not readable JSON: {exc}"], set())
    identity_failures = packaged_runtime_record_failures(
        payload, tool=REFERENCE_STYLE_TOOL
    )
    if identity_failures:
        return ([f"{label}: {failure}" for failure in identity_failures], set())
    measured_viewports = payload.get("viewports_measured")
    if (
        not isinstance(measured_viewports, list)
        or not any(isinstance(item, dict) and item.get("width", 0) >= 1280 for item in measured_viewports)
        or not any(isinstance(item, dict) and item.get("width", 9999) <= 430 for item in measured_viewports)
    ):
        return ([f"{label} measured styles must cover wide and narrow reference viewports."], set())
    numbers = payload.get("numbers")
    if not isinstance(numbers, list) or len(numbers) < 20:
        return ([
            f"{label} measured styles carry no usable values; the extraction "
            "did not read the page."
        ], set())
    return ([], {float(n) for n in numbers if isinstance(n, (int, float))})


def component_value_failures(
    cell: str, *, label: str, ranks: set[int], measured: dict[int, set[float]]
) -> list[str]:
    """Every number a row claims has to be one the reference actually computes.

    This is what stops a value being invented. A producer can write "16px by
    30px padding, radius 999, 650ms" from memory all day; it cannot write
    numbers the live stylesheet does not contain.
    """
    claimed = {
        float(m) for m in re.findall(r"-?\d*\.?\d+", cell)
    }
    claimed = {c for c in claimed if c != 0}
    if len(claimed) < REFERENCE_VALUE_MINIMUM:
        return [
            f"{label} must reproduce at least {REFERENCE_VALUE_MINIMUM} measured "
            "values (sizes, distances, durations, counts, weights). A row with "
            "no numbers in it is a paraphrase of a picture."
        ]
    pool: set[float] = set()
    for rank in ranks:
        pool |= measured.get(rank, set())
    if not pool:
        return []
    unmatched = sorted(
        c for c in claimed
        if not any(abs(c - p) <= max(0.5, abs(c) * 0.02) for p in pool)
    )
    matched = len(claimed) - len(unmatched)
    if matched / len(claimed) < REFERENCE_VALUE_MATCH_FLOOR:
        return [
            f"{label} claims values the reference does not compute: "
            + ", ".join(str(u) for u in unmatched[:8])
            + ". Read them off the live page with "
            f"{REFERENCE_STYLE_TOOL} instead of writing down what the "
            "screenshot looked like."
        ]
    return []


def component_frame_failures(
    cell: str,
    *,
    label: str,
    source: str,
    project: Path,
    selected_ranks: set[int],
    strong_count: int,
) -> list[str]:
    """The frame column has to open.

    A citation nobody can follow is not a citation. This resolves the named
    frame against the reference captures on disk and requires it to belong to
    the reference the row names, which is why a producer cannot write a source
    line for a page it never looked at.
    """
    value = cell.strip()
    if not non_placeholder(value):
        return [
            f"{label} must name the capture frame that SHOWS this part, "
            "relative to the reference captures directory, e.g. "
            "`strong-4-frames/strong-4-006-scroll-settle.png`. A source line "
            "nobody can open is the producer's own design with a citation "
            "typed over it."
        ]
    relative = PurePosixPath(value.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        return [f"{label} frame must stay inside the reference captures directory."]
    root = (project / REFERENCE_CAPTURE_PREFIX).resolve()
    resolved = (root / relative).resolve()
    if root not in resolved.parents and resolved != root:
        return [f"{label} frame must stay inside {REFERENCE_CAPTURE_PREFIX}."]
    if not resolved.is_file():
        return [
            f"{label} frame {value!r} does not exist. Observe the page that "
            "shows this part and cite the frame the harness wrote, or cut the "
            "component."
        ]
    try:
        verify_png_artifact(resolved)
    except StateError as exc:
        return [f"{label} frame {value!r} is not a valid PNG: {exc}"]
    ranks = reference_rank_values(source, maximum=strong_count)
    if ranks:
        owners = {f"strong-{rank}" for rank in ranks}
        if not any(part.startswith(tuple(owners)) for part in relative.parts):
            return [
                f"{label} frame {value!r} does not belong to the reference "
                "this row names. Cite a frame of the site the part came from."
            ]
    return []


def census_component_names(
    section: str, *, project: Path, record_path: Path
) -> set[str]:
    """The component stems the finished build actually renders, or an empty set.

    Returned empty when the census is missing or unreadable; the census gate
    reports that separately and the transfer table should not fail twice for
    one cause.
    """
    value = (markdown_label_value(section, "Component census") or "").strip()
    if not non_placeholder(value) or value.startswith("__REPLACE_WITH"):
        return set()
    artifact, problems = bound_artifact(
        value, project=project, record_path=record_path, label="Component census"
    )
    if problems or artifact is None:
        return set()
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    names = payload.get("names") if isinstance(payload, dict) else None
    if not isinstance(names, list):
        return set()
    return {str(name).strip() for name in names if str(name).strip()}


def signature_transfer_failures(
    section: str,
    *,
    project: Path,
    record_path: Path,
    selected_ranks: set[int],
    signature_by_rank: dict[int, str],
    census_names: set[str],
    component_ranks: dict[str, set[int]],
) -> list[str]:
    """Every selected reference has to have brought its signature with it.

    The gates before this one prove that the producer looked, measured, and
    cited. None of them asks WHICH PART arrived. A reference can clear all of
    them and contribute a background colour and a control size, because those
    are the parts a producer is most comfortable rebuilding, and the source
    line records only that the reference was used.

    So this table asks the deletion question, one row per selected reference:
    cut it out of the set, and what does a stranger notice is gone? The answer
    has to name a component the build actually ships, because a loss that
    cannot be pointed at is not a loss.
    """
    label = "Reference dossier Signature transfer"
    headers, rows = markdown_first_table(section)
    if headers != REFERENCE_DOSSIER_TRANSFER_HEADERS or not rows:
        return [
            f"{label} needs a table using the exact contract, one row per "
            "selected reference. Without it nothing in the record says which "
            "PART of each reference arrived, and a reference that reached the "
            "build as a background colour and a control size satisfies every "
            "other gate."
        ]
    failures: list[str] = []
    seen: set[int] = set()
    for row_number, row in enumerate(rows, start=1):
        row_label = f"{label} row {row_number}"
        if len(row) != len(REFERENCE_DOSSIER_TRANSFER_HEADERS) or any(
            not non_placeholder(cell) for cell in row
        ):
            failures.append(f"{row_label} is incomplete.")
            continue
        row_ranks = reference_rank_values(row[0], maximum=max(selected_ranks or {1}))
        if row_ranks is None or len(row_ranks) != 1 or not row_ranks <= selected_ranks:
            failures.append(f"{row_label} must name exactly one selected rank.")
            continue
        rank = next(iter(row_ranks))
        if rank in seen:
            failures.append(f"{row_label} repeats rank {rank}.")
            continue
        seen.add(rank)

        # the signature cannot be quietly rewritten into something the build
        # happens to have done
        claimed = " ".join(row[1].split()).casefold()
        recorded = " ".join(signature_by_rank.get(rank, "").split()).casefold()
        if len(claimed) < REFERENCE_TRANSFER_SIGNATURE_MINIMUM:
            failures.append(
                f"{row_label} must copy at least "
                f"{REFERENCE_TRANSFER_SIGNATURE_MINIMUM} characters of the "
                "signature recorded in the strong row, not a summary of it."
            )
        elif recorded and claimed not in recorded:
            failures.append(
                f"{row_label} signature is not the one strong row {rank} "
                "records. Copy it, or fix the strong row; a signature that "
                "changes on its way down the record is a signature being "
                "fitted to what got built."
            )

        carrier = row[2]
        carrier_components = {
            name for name in census_names
            if re.search(rf"\b{re.escape(name)}\b", carrier, re.IGNORECASE)
        }
        if census_names and not carrier_components:
            failures.append(
                f"{row_label} must name a component the build actually renders "
                "as the part that carries this signature."
            )
        elif carrier_components and not any(
            rank in component_ranks.get(name.casefold(), set())
            for name in carrier_components
        ):
            failures.append(
                f"{row_label} claims rank {rank} is carried by "
                + ", ".join(sorted(carrier_components))
                + ", but those component source rows do not cite that rank."
            )

        failures.extend(
            bound_artifact(
                row[3], project=project, record_path=record_path,
                label=f"{row_label} recorded proof",
            )[1]
        )

        loss = row[4]
        residue = loss
        named_component = False
        for name in census_names:
            pattern = rf"\b{re.escape(name)}\b"
            if re.search(pattern, loss, re.IGNORECASE):
                named_component = True
                # the component's own name is not evidence that anything about
                # it would change: "the first screen would lose its warm ground"
                # borrows `screen` from the census and still describes a colour
                residue = re.sub(pattern, " ", residue, flags=re.IGNORECASE)
        if census_names and not named_component:
            failures.append(
                f"{row_label} must name a component that would be GONE without "
                "this reference. A loss nobody can point at is what a producer "
                "writes when the reference contributed a colour value."
            )
        if REFERENCE_TRANSFER_SUBSTANCE.search(residue) is None:
            failures.append(
                f"{row_label} describes the loss as a surface property. A "
                "ground, a radius, a size or a control dimension is what "
                "survives when the reference was sampled instead of copied; "
                "name the arrangement or the behaviour that would go with it."
            )

    missing = sorted(selected_ranks - seen)
    if missing:
        failures.append(
            f"{label} has no row for selected rank(s) "
            + ", ".join(str(rank) for rank in missing)
            + ". A selected reference with nothing to lose was not selected, "
            "it was listed."
        )
    return failures


def _recording_artifact_projection(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    required = ("kind", "profile", "file", "bytes", "sha256")
    if any(key not in value for key in required):
        return None
    return {key: value.get(key) for key in required}


def reference_recording_failures(
    payload: object,
    *,
    recording: Path,
    ledger_payload: object,
    ledger: Path,
    state_contract: Path,
    state_contract_sha256: str,
    expected_reference_id: str,
) -> tuple[list[str], set[tuple[str, int]]]:
    """Validate schema-4 recorder output and its non-circular artifact ledger."""

    failures: list[str] = []
    event_ids: set[tuple[str, int]] = set()
    expected_top = {
        "tool", "schema_version", "producer_script_sha256", "runtime_identity",
        "dependencies", "id", "url", "requested_url", "final_urls",
        "recorded_at", "minimum_duration_per_profile_s", "fps",
        "state_contract", "captures_by_viewport", "discovery_metadata",
        "quality_observations", "defect_observations",
        "interaction_census_by_viewport", "rendered_qa_by_viewport",
        "profiles", "coverage",
    }
    if not isinstance(payload, dict) or set(payload) != expected_top:
        return ["Recording must use the exact schema-4 object shape."], event_ids
    failures.extend(
        packaged_runtime_record_failures(
            payload, tool=REFERENCE_RECORDING_TOOL
        )
    )
    if payload.get("id") != expected_reference_id:
        failures.append("Recording reference ID does not match its dossier block.")
    try:
        requested_url = canonical_route_url(str(payload.get("requested_url") or ""))
        source_url = canonical_route_url(str(payload.get("url") or ""))
    except ValueError:
        requested_url = source_url = ""
        failures.append("Recording source URL is not canonical HTTP(S).")
    if (
        not requested_url
        or payload.get("requested_url") != requested_url
        or payload.get("url") != source_url
        or requested_url != source_url
    ):
        failures.append("Recording must bind one exact canonical source URL.")
    minimum_duration = payload.get("minimum_duration_per_profile_s")
    fps = payload.get("fps")
    if (
        not isinstance(minimum_duration, (int, float))
        or minimum_duration < REFERENCE_RECORDING_MINIMUM_SECONDS
    ):
        failures.append("Recording minimum duration is below the 90-second per-profile floor.")
    if not isinstance(fps, (int, float)) or fps < REFERENCE_RECORDING_MINIMUM_FPS:
        failures.append("Recording sampling rate is below the 15-FPS floor.")

    try:
        contract_payload = json.loads(state_contract.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        contract_payload = None
        failures.append(f"Recording source-state contract is unreadable: {exc}")
    contract_failures, contract_ids = reference_state_contract_failures(
        contract_payload,
        expected_reference_id=expected_reference_id,
        expected_primary_url=source_url or None,
    )
    failures.extend(contract_failures)
    state_binding = payload.get("state_contract")
    if (
        not isinstance(state_binding, dict)
        or set(state_binding) != {"file", "sha256"}
        or state_binding.get("file") != state_contract.name
        or state_binding.get("sha256") != state_contract_sha256
        or file_sha256(state_contract)[1] != state_contract_sha256
    ):
        failures.append("Recording does not bind the exact dossier source-state contract bytes.")

    expected_artifacts: list[dict[str, object]] = []
    recording_size = recording.stat().st_size
    expected_artifacts.append(
        {
            "kind": "recording",
            "profile": None,
            "file": recording.name,
            "bytes": recording_size,
            "sha256": file_sha256(recording)[1],
        }
    )
    profiles = payload.get("profiles")
    expected_dimensions = {
        "wide": (1440, 900),
        "narrow": (390, 844),
    }
    if not isinstance(profiles, dict) or set(profiles) != set(expected_dimensions):
        failures.append("Recording must contain exact wide and narrow profile records.")
        profiles = {}
    final_urls = payload.get("final_urls")
    if not isinstance(final_urls, dict) or set(final_urls) != set(expected_dimensions):
        failures.append("Recording final_urls must contain exact wide and narrow entries.")
        final_urls = {}

    def add_artifact(value: object, label: str) -> None:
        projection = _recording_artifact_projection(value)
        if projection is None:
            failures.append(f"{label} artifact metadata is incomplete.")
            return
        expected_artifacts.append(projection)

    for profile_name, dimensions in expected_dimensions.items():
        profile = profiles.get(profile_name)
        expected_profile_keys = {
            "profile", "viewport", "duration_s", "fps", "video", "frames",
            "events", "cursor_path", "difference_signal", "video_elements",
            "navigations", "scroll_traversals", "interaction_census",
            "rendered_qa", "coverage",
        }
        if not isinstance(profile, dict) or set(profile) != expected_profile_keys:
            failures.append(f"Recording {profile_name} profile has an unsupported shape.")
            continue
        if profile.get("profile") != profile_name:
            failures.append(f"Recording {profile_name} profile identity is wrong.")
        viewport = profile.get("viewport")
        if viewport != {
            "name": profile_name,
            "width": dimensions[0],
            "height": dimensions[1],
        }:
            failures.append(f"Recording {profile_name} viewport is not the packaged profile.")
        if (
            not isinstance(profile.get("duration_s"), (int, float))
            or profile["duration_s"] < REFERENCE_RECORDING_MINIMUM_SECONDS
            or (
                isinstance(minimum_duration, (int, float))
                and profile["duration_s"] < minimum_duration
            )
        ):
            failures.append(f"Recording {profile_name} did not meet its duration floor.")
        if profile.get("fps") != fps:
            failures.append(f"Recording {profile_name} FPS differs from the record.")
        try:
            final_url = canonical_route_url(str(final_urls.get(profile_name) or ""))
        except ValueError:
            final_url = ""
        if final_url != source_url or final_urls.get(profile_name) != final_url:
            failures.append(f"Recording {profile_name} did not settle on the exact source URL.")

        coverage = profile.get("coverage")
        expected_coverage_keys = {
            "interactive_targets_discovered", "interactive_targets_hovered",
            "missing_interactive_targets", "hover_failures",
            "internal_pages_discovered", "internal_pages_visited",
            "internal_pages_discovered_urls", "internal_pages_visited_urls",
            "missing_internal_pages", "states_required", "states_visited",
            "missing_states", "incomplete_scroll_traversals",
            "state_inventories", "unreconciled_states",
            "duration_floor_met", "complete",
        }
        if not isinstance(coverage, dict) or set(coverage) != expected_coverage_keys:
            failures.append(f"Recording {profile_name} coverage has an unsupported shape.")
        else:
            discovered = coverage.get("interactive_targets_discovered")
            hovered = coverage.get("interactive_targets_hovered")
            pages_discovered = coverage.get("internal_pages_discovered")
            pages_visited = coverage.get("internal_pages_visited")
            if (
                type(discovered) is not int
                or type(hovered) is not int
                or discovered != hovered
                or type(pages_discovered) is not int
                or type(pages_visited) is not int
                or pages_discovered != pages_visited
                or pages_discovered < 1
                or not isinstance(coverage.get("internal_pages_discovered_urls"), list)
                or coverage.get("internal_pages_discovered_urls")
                != sorted(set(coverage.get("internal_pages_discovered_urls", [])))
                or coverage.get("internal_pages_visited_urls")
                != coverage.get("internal_pages_discovered_urls")
                or len(coverage.get("internal_pages_discovered_urls", []))
                != pages_discovered
                or coverage.get("missing_interactive_targets") != []
                or coverage.get("hover_failures") != {}
                or coverage.get("missing_internal_pages") != []
                or set(coverage.get("states_required") or []) != contract_ids
                or set(coverage.get("states_visited") or []) != contract_ids
                or coverage.get("missing_states") != []
                or coverage.get("incomplete_scroll_traversals") != []
                or coverage.get("unreconciled_states") != []
                or coverage.get("duration_floor_met") is not True
                or coverage.get("complete") is not True
            ):
                failures.append(
                    f"Recording {profile_name} coverage does not reconcile every target/page/state/surface."
                )
            inventories = coverage.get("state_inventories")
            if (
                not isinstance(inventories, list)
                or len(inventories) != pages_discovered
                or any(
                    not isinstance(inventory, dict)
                    or inventory.get("url")
                    not in coverage.get("internal_pages_discovered_urls", [])
                    or inventory.get("complete") is not True
                    or inventory.get("unreconciled") != []
                    for inventory in inventories
                )
            ):
                failures.append(
                    f"Recording {profile_name} inferred state inventory is incomplete."
                )

        navigations = profile.get("navigations")
        if not isinstance(navigations, list) or not navigations:
            failures.append(f"Recording {profile_name} has no exact navigation ledger.")
        else:
            for navigation in navigations:
                if (
                    not isinstance(navigation, dict)
                    or navigation.get("requested_normalized_url")
                    != navigation.get("final_normalized_url")
                    or navigation.get("response_final_normalized_url")
                    != navigation.get("final_normalized_url")
                    or type(navigation.get("final_status")) is not int
                    or not 200 <= navigation["final_status"] < 300
                    or navigation.get("redirect_count") != 0
                ):
                    failures.append(
                        f"Recording {profile_name} contains a redirect, rewrite, or failed navigation."
                    )
                    break
        scrolls = profile.get("scroll_traversals")
        if (
            not isinstance(scrolls, list)
            or not scrolls
            or any(
                not isinstance(item, dict)
                or item.get("complete") is not True
                or not isinstance(item.get("surfaces"), list)
                or any(
                    not isinstance(surface, dict)
                    or surface.get("complete") is not True
                    for surface in item.get("surfaces", [])
                )
                for item in scrolls
            )
        ):
            failures.append(f"Recording {profile_name} has incomplete scroll-surface traversal.")
        if not isinstance(profile.get("video_elements"), list):
            failures.append(f"Recording {profile_name} ambient-video inventory is missing.")

        add_artifact(profile.get("video"), f"Recording {profile_name} video")
        add_artifact(profile.get("cursor_path"), f"Recording {profile_name} cursor path")
        add_artifact(
            profile.get("difference_signal"),
            f"Recording {profile_name} difference signal",
        )
        frames = profile.get("frames")
        if (
            not isinstance(frames, dict)
            or set(frames) != {"count", "directory", "files"}
            or type(frames.get("count")) is not int
            or not isinstance(frames.get("files"), list)
            or frames.get("count") != len(frames.get("files", []))
            or frames.get("count", 0)
            < math.floor(float(profile.get("duration_s") or 0) * float(fps or 0) * 0.9)
        ):
            failures.append(f"Recording {profile_name} frame inventory is incomplete.")
        else:
            for frame in frames["files"]:
                add_artifact(frame, f"Recording {profile_name} frame")
        events = profile.get("events")
        if (
            not isinstance(events, dict)
            or set(events) != {"count", "directory", "files", "index", "quiet"}
            or type(events.get("count")) is not int
            or not isinstance(events.get("files"), list)
            or events.get("count") != len(events.get("files", []))
            or not isinstance(events.get("quiet"), list)
        ):
            failures.append(f"Recording {profile_name} event inventory is incomplete.")
        else:
            for event_index, event in enumerate(events["files"], start=1):
                if (
                    not isinstance(event, dict)
                    or event.get("id") != f"e{event_index:04d}"
                ):
                    failures.append(f"Recording {profile_name} event IDs are not contiguous.")
                else:
                    event_ids.add((profile_name, event_index))
                if (
                    not isinstance(event, dict)
                    or not isinstance(event.get("file"), str)
                    or type(event.get("bytes")) is not int
                    or not isinstance(event.get("sha256"), str)
                ):
                    failures.append(f"Recording {profile_name} event artifact is incomplete.")
                else:
                    expected_artifacts.append(
                        {
                            "kind": "event-sheet",
                            "profile": profile_name,
                            "file": event["file"],
                            "bytes": event["bytes"],
                            "sha256": event["sha256"],
                        }
                    )
            add_artifact(events.get("index"), f"Recording {profile_name} event index")

    captures_by_viewport = payload.get("captures_by_viewport")
    discovery_metadata = payload.get("discovery_metadata")
    quality_observations = payload.get("quality_observations")
    interaction_census_by_viewport = payload.get("interaction_census_by_viewport")
    rendered_qa_by_viewport = payload.get("rendered_qa_by_viewport")
    ledger_allowed_artifacts = {
        (entry.get("file"), entry.get("bytes"), entry.get("sha256"))
        for entry in (
            ledger_payload.get("artifacts", [])
            if isinstance(ledger_payload, dict)
            else []
        )
        if isinstance(entry, dict)
        and isinstance(entry.get("file"), str)
        and type(entry.get("bytes")) is int
        and isinstance(entry.get("sha256"), str)
    }
    if (
        not isinstance(captures_by_viewport, dict)
        or set(captures_by_viewport) != set(expected_dimensions)
        or not isinstance(discovery_metadata, dict)
        or set(discovery_metadata) != set(expected_dimensions)
        or not isinstance(quality_observations, list)
        or len(quality_observations) != 2
        or not isinstance(interaction_census_by_viewport, dict)
        or set(interaction_census_by_viewport) != set(expected_dimensions)
        or not isinstance(rendered_qa_by_viewport, dict)
        or set(rendered_qa_by_viewport) != set(expected_dimensions)
    ):
        failures.append("Recording generated selection observations are incomplete.")
    else:
        for profile_name in expected_dimensions:
            profile = profiles.get(profile_name)
            if not isinstance(profile, dict):
                continue
            profile_coverage = profile.get("coverage", {})
            frames = profile.get("frames", {})
            first_frame = (
                frames.get("files", [None])[0]
                if isinstance(frames, dict) and frames.get("files")
                else None
            )
            expected_capture = (
                {
                    "file": first_frame.get("file"),
                    "bytes": first_frame.get("bytes"),
                    "sha256": first_frame.get("sha256"),
                }
                if isinstance(first_frame, dict)
                else None
            )
            if captures_by_viewport.get(profile_name) != expected_capture:
                failures.append(
                    f"Recording {profile_name} generated capture does not bind its first frame."
                )
            discovery = discovery_metadata.get(profile_name)
            if discovery != {
                "discovered_urls": profile_coverage.get("internal_pages_discovered_urls"),
                "visited_urls": profile_coverage.get("internal_pages_visited_urls"),
                "states_required": profile_coverage.get("states_required"),
                "states_visited": profile_coverage.get("states_visited"),
            }:
                failures.append(
                    f"Recording {profile_name} generated discovery metadata differs from coverage."
                )
            expected_quality = {
                "profile": profile_name,
                "pages_observed": profile_coverage.get("internal_pages_visited"),
                "states_observed": len(profile_coverage.get("states_visited", [])),
                "hover_targets_observed": profile_coverage.get("interactive_targets_hovered"),
                "event_sheets": profile.get("events", {}).get("count")
                if isinstance(profile.get("events"), dict) else None,
                "video_elements": len(profile.get("video_elements", []))
                if isinstance(profile.get("video_elements"), list) else None,
            }
            matches = [
                row for row in quality_observations
                if isinstance(row, dict) and row.get("profile") == profile_name
            ]
            if matches != [expected_quality]:
                failures.append(
                    f"Recording {profile_name} generated quality observations differ from captured coverage."
                )
            interaction = interaction_census_by_viewport.get(profile_name)
            if profile.get("interaction_census") != interaction:
                failures.append(
                    f"Recording {profile_name} interaction census differs from its top-level binding."
                )
            failures.extend(
                f"Recording {problem}"
                for problem in interaction_census_failures(
                    interaction,
                    expected_profile=profile_name,
                    expected_state_ids=contract_ids,
                    expected_urls=set(
                        profile_coverage.get("internal_pages_visited_urls", [])
                    ),
                    artifact_root=ledger.parent,
                    allowed_artifacts=ledger_allowed_artifacts,
                )
            )
            rendered_qa = rendered_qa_by_viewport.get(profile_name)
            if profile.get("rendered_qa") != rendered_qa:
                failures.append(
                    f"Recording {profile_name} rendered QA differs from its top-level binding."
                )
            failures.extend(
                f"Recording {problem}"
                for problem in source_rendered_qa_failures(
                    rendered_qa,
                    expected_profile=profile_name,
                    expected_urls=set(
                        profile_coverage.get("internal_pages_visited_urls", [])
                    ),
                    artifact_root=ledger.parent,
                    allowed_artifacts=ledger_allowed_artifacts,
                    interaction_census=interaction,
                )
            )
    if payload.get("defect_observations") != []:
        failures.append(
            "A completed recording cannot hide or carry unresolved generated coverage defects."
        )
    referenced_interaction_artifacts: set[tuple[str, int, str]] = set()

    def collect_interaction_artifacts(value: object) -> None:
        if isinstance(value, dict):
            if (
                isinstance(value.get("file"), str)
                and "-interaction-evidence/" in value["file"]
                and type(value.get("bytes")) is int
                and isinstance(value.get("sha256"), str)
            ):
                referenced_interaction_artifacts.add(
                    (value["file"], value["bytes"], value["sha256"])
                )
            for child in value.values():
                collect_interaction_artifacts(child)
        elif isinstance(value, list):
            for child in value:
                collect_interaction_artifacts(child)

    collect_interaction_artifacts(interaction_census_by_viewport)
    collect_interaction_artifacts(rendered_qa_by_viewport)
    ledger_interaction = [
        dict(entry)
        for entry in (
            ledger_payload.get("artifacts", [])
            if isinstance(ledger_payload, dict)
            else []
        )
        if isinstance(entry, dict) and entry.get("kind") == "interaction-frame"
    ]
    ledger_interaction_keys = {
        (entry.get("file"), entry.get("bytes"), entry.get("sha256"))
        for entry in ledger_interaction
    }
    if ledger_interaction_keys != referenced_interaction_artifacts:
        failures.append(
            "Recording interaction-frame ledger does not equal every generated census evidence frame."
        )
    expected_artifacts.extend(ledger_interaction)

    outer_coverage = payload.get("coverage")
    if outer_coverage != {
        "wide_complete": True,
        "narrow_complete": True,
        "complete": True,
    }:
        failures.append("Recording top-level coverage does not prove both profiles complete.")
    if len(event_ids) < REFERENCE_RECORDING_MINIMUM_EVENTS:
        failures.append(
            f"Recording has {len(event_ids)} events; at least "
            f"{REFERENCE_RECORDING_MINIMUM_EVENTS} observed changes are required for a motion signature."
        )

    expected_ledger_keys = {
        "schema_version", "algorithm", "recording", "artifacts", "sha256"
    }
    if (
        not isinstance(ledger_payload, dict)
        or set(ledger_payload) != expected_ledger_keys
        or ledger_payload.get("schema_version") != 1
        or ledger_payload.get("algorithm") != "sha256"
        or ledger_payload.get("recording") != recording.name
        or not isinstance(ledger_payload.get("artifacts"), list)
    ):
        failures.append("Recording artifact ledger has an unsupported schema.")
        return failures, event_ids
    ledger_core = {
        "schema_version": 1,
        "algorithm": "sha256",
        "recording": recording.name,
        "artifacts": ledger_payload["artifacts"],
    }
    if ledger_payload.get("sha256") != canonical_json_sha256(ledger_core):
        failures.append("Recording artifact ledger canonical hash is invalid.")
    actual_artifacts: list[dict[str, object]] = []
    seen_files: set[str] = set()
    for index, entry in enumerate(ledger_payload["artifacts"], start=1):
        if (
            not isinstance(entry, dict)
            or set(entry) != {"kind", "profile", "file", "bytes", "sha256"}
        ):
            failures.append(f"Recording artifact ledger row {index} has an unsupported shape.")
            continue
        relative = entry.get("file")
        if not isinstance(relative, str) or relative in seen_files:
            failures.append(f"Recording artifact ledger row {index} has a duplicate/invalid path.")
            continue
        seen_files.add(relative)
        parts = PurePosixPath(relative)
        artifact = (ledger.parent / parts).resolve()
        if (
            parts.is_absolute()
            or ".." in parts.parts
            or not is_within(artifact, ledger.parent.resolve())
            or not artifact.is_file()
            or type(entry.get("bytes")) is not int
            or artifact.stat().st_size != entry.get("bytes")
            or not isinstance(entry.get("sha256"), str)
            or SHA256_HEX.fullmatch(entry["sha256"]) is None
            or file_sha256(artifact)[1] != entry.get("sha256")
        ):
            failures.append(f"Recording artifact ledger row {index} bytes are missing or drifted.")
        if parts.suffix.casefold() == ".png":
            try:
                verify_png_artifact(artifact)
            except StateError as exc:
                failures.append(f"Recording artifact ledger row {index} PNG is invalid: {exc}")
        actual_artifacts.append(dict(entry))
    expected_artifacts.sort(key=lambda entry: str(entry.get("file")))
    if actual_artifacts != expected_artifacts:
        failures.append(
            "Recording artifact ledger is not the exact recording/video/frame/event/cursor/difference artifact set."
        )
    return failures, event_ids


def interaction_census_section_failures(
    section: str,
    *,
    project: Path,
    record_path: Path,
    selected_ranks: set[int],
    observation_by_rank: dict[int, str],
) -> list[str]:
    """Bind every human interaction row to observer and recorder pixels."""

    failures: list[str] = []
    if not non_placeholder(section):
        return [
            "Reference dossier Interaction census is missing; selected references need generated target/input evidence."
        ]
    blocks: dict[int, str] = {}
    for match in re.finditer(
        r"^###\s+strong-(\d+)\s+interaction census\s*$",
        section,
        re.MULTILINE | re.IGNORECASE,
    ):
        start = match.end()
        nxt = re.search(r"^###\s+", section[start:], re.MULTILINE)
        end = start + nxt.start() if nxt else len(section)
        rank = int(match.group(1))
        if rank in blocks:
            failures.append(f"Interaction census repeats strong-{rank}.")
        blocks[rank] = section[start:end]
    if set(blocks) != selected_ranks:
        missing = sorted(selected_ranks - set(blocks))
        extra = sorted(set(blocks) - selected_ranks)
        if missing:
            failures.append(
                "Interaction census is missing selected rank(s): "
                + ", ".join(str(rank) for rank in missing)
            )
        if extra:
            failures.append(
                "Interaction census contains unselected rank(s): "
                + ", ".join(str(rank) for rank in extra)
            )

    def flatten(value: object) -> dict[tuple[str, str, str, str, str, int], dict[str, object]]:
        rows: dict[tuple[str, str, str, str, str, int], dict[str, object]] = {}
        if not isinstance(value, dict):
            return rows
        occurrences: dict[tuple[str, str, str, str, str], int] = {}

        def add(
            *,
            profile: str,
            page: str,
            target_id: str,
            kind: str,
            repeat_class: str,
            repeat_index: int,
            repeat_count: int,
            input_kind: str,
            source_state_id: str | None,
            before: object,
            after: object,
            settled: object,
            behavior: str,
            evidence: object,
            disposition: str,
        ) -> None:
            base = (profile, page, target_id, input_kind, source_state_id or "none")
            occurrence = occurrences.get(base, 0) + 1
            occurrences[base] = occurrence
            rows[(*base, occurrence)] = {
                "profile": profile,
                "page": page,
                "target_id": target_id,
                "kind": kind,
                "repeat_class": repeat_class,
                "repeat_index": repeat_index,
                "repeat_count": repeat_count,
                "input": input_kind,
                "source_state_id": source_state_id,
                "before": before,
                "after": after,
                "settled": settled,
                "behavior": behavior,
                "evidence": evidence,
                "disposition": disposition,
                "occurrence": occurrence,
            }

        for profile in ("wide", "narrow"):
            census = value.get(profile)
            if not isinstance(census, dict):
                continue
            for page in census.get("pages", []):
                if not isinstance(page, dict):
                    continue
                page_url = str(page.get("url") or "")
                for target in page.get("targets", []):
                    if not isinstance(target, dict):
                        continue
                    for input_record in target.get("inputs", []):
                        if not isinstance(input_record, dict):
                            continue
                        raw_disposition = input_record.get("disposition")
                        disposition = (
                            "exercised"
                            if raw_disposition == "sourceable-observed-behavior"
                            else "quiet"
                            if raw_disposition == "observed-quiet"
                            else "blocked hand-off"
                        )
                        add(
                            profile=profile,
                            page=page_url,
                            target_id=str(target.get("target_id") or ""),
                            kind=str(target.get("kind") or ""),
                            repeat_class=str(target.get("repeat_class") or ""),
                            repeat_index=int(target.get("repeat_index") or 0),
                            repeat_count=int(target.get("repeat_count") or 0),
                            input_kind=str(input_record.get("input_kind") or ""),
                            source_state_id=(
                                str(input_record["source_state_id"])
                                if input_record.get("source_state_id") is not None
                                else None
                            ),
                            before=input_record.get("before_sha256"),
                            after=input_record.get("after_sha256"),
                            settled=input_record.get("settled_sha256"),
                            behavior=str(input_record.get("behavior") or ""),
                            evidence=input_record.get("evidence"),
                            disposition=disposition,
                        )
            for state in census.get("page_states", []):
                if not isinstance(state, dict):
                    continue
                state_id = str(state.get("source_state_id") or "")
                trigger = state.get("trigger")
                trigger_evidence = state.get("trigger_evidence")
                if not isinstance(trigger, dict) or not isinstance(trigger_evidence, dict):
                    continue
                changed = trigger_evidence.get("changed_properties")
                disposition = "quiet" if not changed else "exercised"
                add(
                    profile=profile,
                    page=str(state.get("page_url") or ""),
                    target_id="page-state-" + hashlib.sha256(
                        f"{profile}\0{state.get('page_url')}\0{state_id}".encode("utf-8")
                    ).hexdigest()[:16],
                    kind=str(state.get("kind") or "") + "-page-state",
                    repeat_class="page-state",
                    repeat_index=1,
                    repeat_count=1,
                    input_kind=str(trigger.get("type") or ""),
                    source_state_id=state_id,
                    before=trigger_evidence.get("before_sha256"),
                    after=trigger_evidence.get("after_sha256"),
                    settled=trigger_evidence.get("settled_sha256"),
                    behavior=str(trigger_evidence.get("behavior") or ""),
                    evidence=state.get("evidence"),
                    disposition=disposition,
                )
            for pointer in census.get("pointer_follow", []):
                if not isinstance(pointer, dict) or not isinstance(pointer.get("evidence"), dict):
                    continue
                evidence = pointer["evidence"]
                add(
                    profile=profile,
                    page=str(pointer.get("page_url") or ""),
                    target_id=str(pointer.get("target_id") or ""),
                    kind="pointer-follow",
                    repeat_class="pointer-follow",
                    repeat_index=1,
                    repeat_count=1,
                    input_kind="pointer-follow",
                    source_state_id=None,
                    before=(evidence.get("before") or {}).get("sha256")
                    if isinstance(evidence.get("before"), dict) else None,
                    after=(evidence.get("after") or {}).get("sha256")
                    if isinstance(evidence.get("after"), dict) else None,
                    settled=(evidence.get("settled") or {}).get("sha256")
                    if isinstance(evidence.get("settled"), dict) else None,
                    behavior=(
                        f"moved_px={pointer.get('moved_px')}, "
                        f"return_error_px={pointer.get('return_error_px')}, "
                        f"pointer_correlation={pointer.get('pointer_correlation')}"
                    ),
                    evidence=evidence,
                    disposition="exercised",
                )
        return rows

    def evidence_binding_matches(
        binding: str,
        metadata: object,
        *,
        root: Path,
        label: str,
    ) -> list[str]:
        artifact, binding_failures = bound_artifact(
            binding,
            project=project,
            record_path=record_path,
            label=label,
        )
        local = list(binding_failures)
        if not isinstance(metadata, dict) or artifact is None:
            return [*local, f"{label} does not map generated artifact metadata."]
        expected = (root / PurePosixPath(str(metadata.get("file") or ""))).resolve()
        if (
            artifact.resolve() != expected
            or type(metadata.get("bytes")) is not int
            or not expected.is_file()
            or expected.stat().st_size != metadata.get("bytes")
            or file_sha256(expected)[1] != metadata.get("sha256")
        ):
            local.append(f"{label} bytes do not match generated census evidence.")
        return local

    for rank in sorted(selected_ranks):
        block = blocks.get(rank)
        if block is None:
            continue
        block_label = f"Reference dossier Interaction census strong-{rank}"
        observation_cell = (markdown_label_value(block, "Observation") or "").strip()
        recording_cell = (markdown_label_value(block, "Recording") or "").strip()
        ledger_cell = (
            markdown_label_value(block, "Recording artifact ledger") or ""
        ).strip()
        if observation_cell != observation_by_rank.get(rank, ""):
            failures.append(
                f"{block_label} Observation must copy the exact strong-row observation binding."
            )
        observation, observation_binding_failures = bound_artifact(
            observation_cell,
            project=project,
            record_path=record_path,
            label=f"{block_label} observation",
        )
        recording, recording_binding_failures = bound_artifact(
            recording_cell,
            project=project,
            record_path=record_path,
            label=f"{block_label} recording",
        )
        ledger, ledger_binding_failures = bound_artifact(
            ledger_cell,
            project=project,
            record_path=record_path,
            label=f"{block_label} recording artifact ledger",
        )
        failures.extend(observation_binding_failures)
        failures.extend(recording_binding_failures)
        failures.extend(ledger_binding_failures)
        if observation is None or recording is None or ledger is None:
            continue
        expected_id = f"strong-{rank}"
        if (
            recording.resolve()
            != (project / ".design-dna" / "references" / f"{expected_id}-recording.json").resolve()
            or ledger.resolve()
            != (project / ".design-dna" / "references" / f"{expected_id}-artifacts.json").resolve()
        ):
            failures.append(f"{block_label} recording/ledger paths are not canonical.")
        try:
            observed = json.loads(observation.read_text(encoding="utf-8"))
            recorded = json.loads(recording.read_text(encoding="utf-8"))
            ledger_payload = json.loads(ledger.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            failures.append(f"{block_label} generated evidence is unreadable: {exc}")
            continue
        state_binding = recorded.get("state_contract") if isinstance(recorded, dict) else None
        state_contract = (
            recording.parent / PurePosixPath(str(state_binding.get("file") or ""))
        ).resolve() if isinstance(state_binding, dict) else Path()
        recording_problems, _events = reference_recording_failures(
            recorded,
            recording=recording,
            ledger_payload=ledger_payload,
            ledger=ledger,
            state_contract=state_contract,
            state_contract_sha256=(
                str(state_binding.get("sha256")) if isinstance(state_binding, dict) else ""
            ),
            expected_reference_id=expected_id,
        )
        failures.extend(f"{block_label}: {problem}" for problem in recording_problems)
        if (
            not isinstance(observed, dict)
            or observed.get("id") != expected_id
            or recorded.get("id") != expected_id
            or observed.get("url") != recorded.get("url")
            or observed.get("state_contract") != recorded.get("state_contract")
        ):
            failures.append(f"{block_label} observer and recorder reference bindings differ.")
            continue
        observer_rows = flatten(observed.get("interaction_census_by_viewport"))
        recorder_rows = flatten(recorded.get("interaction_census_by_viewport"))
        if set(observer_rows) != set(recorder_rows):
            failures.append(
                f"{block_label} observer and recorder target/page/input inventories differ."
            )
        expected_keys = set(observer_rows) & set(recorder_rows)
        headers, table_rows = markdown_first_table(block)
        if headers != REFERENCE_INTERACTION_CENSUS_HEADERS or not table_rows:
            failures.append(f"{block_label} needs the exact generated-interaction table.")
            continue
        seen: set[tuple[str, str, str, str, str, int]] = set()
        for row_number, row in enumerate(table_rows, start=1):
            row_label = f"{block_label} row {row_number}"
            if len(row) != len(REFERENCE_INTERACTION_CENSUS_HEADERS) or any(
                not non_placeholder(cell) for cell in row
            ):
                failures.append(f"{row_label} is incomplete.")
                continue
            identity_fields = semicolon_fields(row[0])
            kind_fields = semicolon_fields(row[1])
            input_fields = semicolon_fields(row[2])
            before_fields = semicolon_fields(row[3])
            after_fields = semicolon_fields(row[4])
            evidence_fields = semicolon_fields(row[5])
            if set(identity_fields) != {"target_id", "profile", "page", "occurrence"}:
                failures.append(f"{row_label} target identity has an unsupported shape.")
                continue
            try:
                occurrence = int(identity_fields.get("occurrence", ""))
            except ValueError:
                occurrence = 0
            key = (
                identity_fields.get("profile", ""),
                identity_fields.get("page", ""),
                identity_fields.get("target_id", ""),
                input_fields.get("input", ""),
                input_fields.get("source_state_id", "none"),
                occurrence,
            )
            if key not in expected_keys or key in seen:
                failures.append(f"{row_label} does not name one unique generated target/input occurrence.")
                continue
            seen.add(key)
            observer_row = observer_rows[key]
            recorder_row = recorder_rows[key]
            expected_kind = {
                "kind": observer_row["kind"],
                "repeat_class_sha256": hashlib.sha256(
                    str(observer_row["repeat_class"]).encode("utf-8")
                ).hexdigest(),
                "repeat_index": str(observer_row["repeat_index"]),
                "repeat_count": str(observer_row["repeat_count"]),
            }
            if kind_fields != expected_kind:
                failures.append(f"{row_label} kind/repeat identity differs from generated census.")
            if input_fields != {
                "input": observer_row["input"],
                "source_state_id": observer_row["source_state_id"] or "none",
            }:
                failures.append(f"{row_label} input/source-state differs from generated census.")
            expected_before = {
                "observer_sha256": str(observer_row["before"] or "null"),
                "recorder_sha256": str(recorder_row["before"] or "null"),
            }
            if before_fields != expected_before:
                failures.append(f"{row_label} before hashes differ from generated census.")
            expected_after = {
                "observer_after_sha256": str(observer_row["after"] or "null"),
                "observer_settled_sha256": str(observer_row["settled"] or "null"),
                "recorder_after_sha256": str(recorder_row["after"] or "null"),
                "recorder_settled_sha256": str(recorder_row["settled"] or "null"),
                "observer_behavior": str(observer_row["behavior"]),
                "recorder_behavior": str(recorder_row["behavior"]),
            }
            if after_fields != expected_after:
                failures.append(f"{row_label} after/settled behavior differs from generated census.")
            if row[6].strip().casefold() != observer_row["disposition"] or (
                recorder_row["disposition"] != observer_row["disposition"]
            ):
                failures.append(f"{row_label} disposition differs between generated runs.")
            if observer_row["disposition"] == "blocked hand-off":
                if evidence_fields != {
                    "observer": "blocked",
                    "recorder": "blocked",
                    "ledger": ledger_cell,
                }:
                    failures.append(f"{row_label} blocked evidence/handoff binding is invalid.")
            else:
                if set(evidence_fields) != {
                    "observer_before", "observer_after", "observer_settled",
                    "recorder_before", "recorder_after", "recorder_settled",
                    "ledger",
                }:
                    failures.append(f"{row_label} evidence bindings have an unsupported shape.")
                else:
                    observer_evidence = observer_row.get("evidence")
                    recorder_evidence = recorder_row.get("evidence")
                    for phase in ("before", "after", "settled"):
                        failures.extend(
                            evidence_binding_matches(
                                evidence_fields[f"observer_{phase}"],
                                observer_evidence.get(phase)
                                if isinstance(observer_evidence, dict) else None,
                                root=observation.parent,
                                label=f"{row_label} observer {phase}",
                            )
                        )
                        failures.extend(
                            evidence_binding_matches(
                                evidence_fields[f"recorder_{phase}"],
                                recorder_evidence.get(phase)
                                if isinstance(recorder_evidence, dict) else None,
                                root=recording.parent,
                                label=f"{row_label} recorder {phase}",
                            )
                        )
                    if evidence_fields.get("ledger") != ledger_cell:
                        failures.append(f"{row_label} does not bind the exact recording artifact ledger.")
        if seen != expected_keys:
            failures.append(
                f"{block_label} table omits or adds generated target/page/input rows."
            )
    return failures


def sequence_read_failures(
    section: str,
    component_section: str,
    *,
    project: Path,
    record_path: Path,
    selected_ranks: set[int],
    kind_by_rank: dict[str, str],
    wide_capture_by_rank: dict[int, str],
    narrow_capture_by_rank: dict[int, str],
    styles_by_rank: dict[int, str],
    observation_by_rank: dict[int, str],
) -> list[str]:
    """Require complete motion reads or explicit static-evidence blocks.

    The watching is the gate. It is enforced by count: the recording says how
    many sheets it produced, and the read has to carry a line for each one.
    A line has to be long enough to have said something, most of the lines
    have to describe change, the read has to end in an inventory of what the
    site DOES with magnitudes, and the strong row's signature has to be
    located on sheets that exist. None of that proves understanding. It proves
    the producer looked at all of it, which is the part that was skipped.
    """
    label = f"Reference dossier {REFERENCE_SEQUENCE_SECTION}"
    failures: list[str] = []
    if not non_placeholder(section):
        return [
            f"{label} is missing. Record every selected reference with "
            "scripts/record_reference.mjs and narrate every sheet before the "
            "strong row is written; a reference that was measured and not "
            "watched reaches the build as a still."
        ]
    blocks: dict[int, tuple[str, str]] = {}
    for match in re.finditer(
        r"^###\s+strong-(\d+)(?:\s+(static evidence))?\s*$",
        section,
        re.MULTILINE,
    ):
        start = match.end()
        nxt = re.search(r"^###\s+", section[start:], re.MULTILINE)
        end = start + nxt.start() if nxt else len(section)
        blocks[int(match.group(1))] = (
            "static" if match.group(2) else "motion",
            section[start:end],
        )

    for rank in sorted(selected_ranks):
        block_label = f"{label} strong-{rank}"
        block_entry = blocks.get(rank)
        expected_kind = kind_by_rank.get(str(rank), "")
        if block_entry is None:
            suffix = " static evidence" if expected_kind == "static" else ""
            failures.append(
                f"{block_label} has no `### strong-{rank}{suffix}` block."
            )
            continue
        block_kind, block = block_entry
        if block_kind != expected_kind:
            failures.append(
                f"{block_label} uses a {block_kind} block but the strong row "
                f"declares {expected_kind or 'no valid'} evidence."
            )
            continue
        if expected_kind == "static":
            required_static = {
                "Wide capture": wide_capture_by_rank.get(rank, ""),
                "Narrow capture": narrow_capture_by_rank.get(rank, ""),
                "Measured styles": styles_by_rank.get(rank, ""),
                "Structure observation": observation_by_rank.get(rank, ""),
            }
            for field, expected in required_static.items():
                actual = (markdown_label_value(block, field) or "").strip()
                if not non_placeholder(actual) or actual != expected:
                    failures.append(
                        f"{block_label} {field!r} must copy the exact bound "
                        "artifact from its strong row."
                    )
            relationship = markdown_label_value(
                block, "Dominant static relationship"
            ) or ""
            if (
                len(" ".join(relationship.split())) < 80
                or REFERENCE_STATIC_SIGNATURE_TERMS.search(relationship) is None
            ):
                failures.append(
                    f"{block_label} must explain the dominant static composition, "
                    "type, media, color, hierarchy, or spatial relationship."
                )
            continue
        state_contract_cell = markdown_label_value(block, "State contract")
        recording_cell = markdown_label_value(block, "Recording")
        ledger_cell = markdown_label_value(block, "Recording artifact ledger")
        read_cell = markdown_label_value(block, "Read")
        sheets_cell = markdown_label_value(block, "Signature events") or markdown_label_value(
            block, "Signature sheets"
        )
        if (
            not non_placeholder(state_contract_cell)
            or not non_placeholder(recording_cell)
            or not non_placeholder(ledger_cell)
            or not non_placeholder(read_cell)
        ):
            failures.append(
                f"{block_label} must hash-bind `State contract`, `Recording`, "
                "`Recording artifact ledger`, and `Read`."
            )
            continue
        state_contract, state_contract_failures = bound_artifact(
            state_contract_cell,
            project=project,
            record_path=record_path,
            label=f"{block_label} state contract",
        )
        recording, recording_failures = bound_artifact(
            recording_cell, project=project, record_path=record_path,
            label=f"{block_label} recording",
        )
        ledger, ledger_failures = bound_artifact(
            ledger_cell,
            project=project,
            record_path=record_path,
            label=f"{block_label} recording artifact ledger",
        )
        read, read_failures = bound_artifact(
            read_cell, project=project, record_path=record_path,
            label=f"{block_label} read",
        )
        failures.extend(state_contract_failures)
        failures.extend(recording_failures)
        failures.extend(ledger_failures)
        failures.extend(read_failures)
        if state_contract is None or recording is None or ledger is None or read is None:
            continue
        expected_reference_id = f"strong-{rank}"
        expected_paths = {
            "state contract": project / ".design-dna" / "references" / f"{expected_reference_id}-state-contract.json",
            "recording": project / ".design-dna" / "references" / f"{expected_reference_id}-recording.json",
            "recording artifact ledger": project / ".design-dna" / "references" / f"{expected_reference_id}-artifacts.json",
        }
        for artifact_label, (artifact, expected_path) in {
            "state contract": (state_contract, expected_paths["state contract"]),
            "recording": (recording, expected_paths["recording"]),
            "recording artifact ledger": (ledger, expected_paths["recording artifact ledger"]),
        }.items():
            if artifact.resolve() != expected_path.resolve():
                failures.append(
                    f"{block_label} {artifact_label} must use the canonical "
                    f".design-dna/references/{expected_path.name} path."
                )
        try:
            payload = json.loads(recording.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            failures.append(f"{block_label} recording is not readable JSON: {exc}")
            continue
        try:
            ledger_payload = json.loads(ledger.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            failures.append(f"{block_label} recording artifact ledger is not readable JSON: {exc}")
            continue
        recording_problems, event_ids = reference_recording_failures(
            payload,
            recording=recording,
            ledger_payload=ledger_payload,
            ledger=ledger,
            state_contract=state_contract,
            state_contract_sha256=file_sha256(state_contract)[1],
            expected_reference_id=expected_reference_id,
        )
        failures.extend(f"{block_label}: {problem}" for problem in recording_problems)
        observation_binding = observation_by_rank.get(rank, "")
        observation, observation_failures = bound_artifact(
            observation_binding,
            project=project,
            record_path=record_path,
            label=f"{block_label} observation",
        )
        failures.extend(observation_failures)
        if observation is not None:
            try:
                observation_payload = json.loads(observation.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                observation_payload = None
            observation_state = (
                observation_payload.get("state_contract")
                if isinstance(observation_payload, dict)
                else None
            )
            if (
                not isinstance(observation_state, dict)
                or observation_state.get("file") != state_contract.name
                or observation_state.get("sha256") != file_sha256(state_contract)[1]
                or observation_payload.get("id") != expected_reference_id
                or observation_payload.get("url") != payload.get("url")
            ):
                failures.append(
                    f"{block_label} observer and recorder do not bind the same reference URL/state-contract bytes."
                )

        try:
            text = read.read_text(encoding="utf-8")
        except OSError as exc:
            failures.append(f"{block_label} read is not readable: {exc}")
            continue
        line_matches = list(REFERENCE_EVENT_LINE.finditer(text))
        lines = {
            (m.group(1), int(m.group(2))): line
            for m, line in (
                (m, text[m.start():text.find("\n", m.start()) if text.find("\n", m.start()) != -1 else len(text)])
                for m in line_matches
            )
        }
        if len(lines) != len(line_matches):
            failures.append(f"{block_label} read repeats a profile-qualified event ID.")
        missing = sorted(event_ids - set(lines))
        unexpected = sorted(set(lines) - event_ids)
        if missing:
            shown = ", ".join(f"{profile}/e{number:04d}" for profile, number in missing[:8])
            more = f" and {len(missing) - 8} more" if len(missing) > 8 else ""
            failures.append(
                f"{block_label} read has no line for {shown}{more} "
                f"({len(missing)} event(s)). Every event gets a line: "
                "what the cursor did, what scrolled, what changed."
            )
        if unexpected:
            failures.append(
                f"{block_label} read names event IDs absent from the recording artifact ledger."
            )
        short = [event for event, line in lines.items() if len(line.strip()) < REFERENCE_SEQUENCE_LINE_MINIMUM]
        if short:
            failures.append(
                f"{block_label} read has {len(short)} line(s) under "
                f"{REFERENCE_SEQUENCE_LINE_MINIMUM} characters (first: "
                f"{min(short)[0]}/e{min(short)[1]:04d}); an event id with nothing after it is not a "
                "reading."
            )
        if lines:
            static = sum(1 for line in lines.values() if REFERENCE_SEQUENCE_STATIC.search(line))
            if static / len(lines) > REFERENCE_SEQUENCE_STATIC_CEILING:
                failures.append(
                    f"{block_label} read calls {static} of {len(lines)} events "
                    "static. A recording that hovers, scrolls and follows a link "
                    "does not stand still that long; the cursor is being "
                    "described instead of the page."
                )
        inventory = markdown_sections(text).get("Behaviour inventory", "")
        _headers, rows = markdown_first_table(inventory)
        if len(rows) < REFERENCE_SEQUENCE_INVENTORY_MINIMUM:
            failures.append(
                f"{block_label} read needs a `## Behaviour inventory` table with "
                f"at least {REFERENCE_SEQUENCE_INVENTORY_MINIMUM} rows (trigger, "
                f"element, effect, magnitude, events); it has {len(rows)}. The "
                "inventory is what the build reproduces."
            )
        cited = {
            (profile, int(number))
            for profile, number in REFERENCE_EVENT_ID.findall(sheets_cell or "")
        }
        valid = cited & event_ids & set(lines)
        if not valid:
            failures.append(
                f"{block_label} must name `- Signature events:` as profile-qualified "
                "event ids that exist in the read (e.g. `wide/e0004, narrow/e0005`), so the signature "
                "in the strong row is something that was WATCHED happening, "
                "not something remembered from a still."
            )

    # a rest frame cannot show a first screen arriving, a nav responding, a
    # button under the pointer, a scroll or a hover; those rows cite a sheet
    _headers, component_rows = markdown_first_table(component_section)
    for row in component_rows:
        if len(row) < 3:
            continue
        name = " ".join(row[0].split()).casefold()
        if name in REFERENCE_BEHAVIOUR_COMPONENTS and not (
            REFERENCE_SHEET_FRAME.search(row[2]) or REFERENCE_EVENT_FRAME.search(row[2])
        ):
            failures.append(
                f"Reference dossier Component sources row {row[0]!r} must cite "
                "a recording sheet (`strong-N-wide-events/eNNNN-kind.png` or "
                "`strong-N-narrow-events/eNNNN-kind.png`, or "
                "`strong-N-sheets/sNNN.png` from a schema-1 recording) in `Frame "
                "that shows it`; a rest frame cannot show what this component does."
            )
    return failures


def component_census_failures(
    section: str, *, project: Path, record_path: Path, covered: set[str]
) -> list[str]:
    """Every component the build renders needs a row.

    The table's required rows were a fixed list, so a build could satisfy all
    twelve and still ship a lede block, a photo plate, a numbered steps list, a
    form and a footer that came from nowhere. This counts what the build
    actually renders, and a component with no row is a part of the design the
    producer invented.
    """
    label = "Reference dossier Component census"
    value = (markdown_label_value(section, "Component census") or "").strip()
    if not non_placeholder(value) or value.startswith("__REPLACE_WITH"):
        return [
            f"{label} must bind the scan_build_components.mjs record for the "
            "finished build, so the sources table is checked against what the "
            "build renders instead of against a fixed list."
        ]
    artifact, artifact_failures = bound_artifact(
        value, project=project, record_path=record_path, label=label
    )
    if artifact_failures or artifact is None:
        return artifact_failures
    expected = (project / ".design-dna" / "evidence" / "component-census.json").resolve()
    if artifact.resolve() != expected:
        return [f"{label} must bind .design-dna/evidence/component-census.json."]
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{label} is not readable JSON: {exc}"]
    identity_failures = packaged_runtime_record_failures(
        payload, tool="scan_build_components.mjs", require_pass=True
    )
    if identity_failures:
        return [f"{label}: {failure}" for failure in identity_failures]
    manifest_path = project / ".design-dna" / "route-manifest.json"
    try:
        manifest = read_json(manifest_path)
    except StateError as exc:
        return [f"{label} cannot validate the authoritative route manifest: {exc}"]
    if not isinstance(manifest, dict):
        return [f"{label} route manifest must contain an object."]
    runtime_failures = census_runtime_failures(
        payload,
        expected_routes=[
            route for route in manifest.get("routes", []) if isinstance(route, dict)
        ],
        expected_viewports=[
            viewport for viewport in manifest.get("viewports", [])
            if isinstance(viewport, dict)
        ],
        first_screen=False,
        record_path=artifact,
        project=project,
    )
    if runtime_failures:
        return [f"{label}: {failure}" for failure in runtime_failures]
    names = payload.get("names")
    if not isinstance(names, list) or not names:
        return [f"{label} recorded no components; the scan did not read the build."]
    normalized_covered = {" ".join(entry.casefold().split()) for entry in covered}
    unsourced = sorted(
        str(name) for name in names
        if " ".join(str(name).casefold().split()) not in normalized_covered
    )
    if unsourced:
        return [
            f"{label} found components in the build with no source row: "
            + ", ".join(unsourced)
            + ". Every one of those is a part of the design that came from "
            "nowhere. Observe a reference page that shows it and cite the "
            "frame, or cut the component."
        ]
    return []

ASSURANCE_PROFILE_ALIASES = {
    "quick": "quick",
    "standard": "standard",
    "substantial": "standard",
    "showcase": "showcase",
    "greenfield": "standard",
    "connected-public-experience": "connected-public-experience",
    "range-study": "range-study",
    "high-risk": "high-risk",
}
PROFILE_REQUIREMENT_INHERITANCE = {
    "quick": ("quick",),
    "standard": ("standard",),
    "showcase": ("standard", "showcase"),
    "connected-public-experience": ("standard",),
    "high-risk": ("standard", "high-risk"),
}

REQUIRED_LABEL_ALIASES: dict[tuple[str, str], tuple[str, ...]] = {}


def assurance_profiles(body: str) -> set[str]:
    value = (
        markdown_label_value(body, "Assurance profile and rationale")
        or markdown_label_value(body, "Assurance profile and why it fits")
        or markdown_label_value(body, "Assurance profile")
        or ""
    ).casefold()
    observed = {
        canonical
        for name, canonical in ASSURANCE_PROFILE_ALIASES.items()
        if re.search(rf"\b{re.escape(name)}\b", value)
    }
    return observed


def required_labels_for_record(
    record: str,
    body: str,
    required_assurance_profiles: tuple[str, ...] | set[str] | None = None,
    *,
    evidence_contract: str | None = None,
) -> tuple[str, ...]:
    contract_labels = (
        REQUIRED_RECORD_LABELS
        if (
            evidence_contract == PROPORTIONAL_EVIDENCE_CONTRACT
            or PROPORTIONAL_EVIDENCE_CONTRACT in body
        )
        else LEGACY_REQUIRED_RECORD_LABELS
    )
    labels = list(contract_labels[record])
    by_profile = PROFILE_REQUIRED_LABELS.get(record, {})
    selected_profiles = (
        set(required_assurance_profiles)
        & {"quick", "standard", "showcase", "high-risk"}
        if required_assurance_profiles is not None
        else assurance_profiles(body)
    )
    applied_profiles: list[str] = []
    for profile in sorted(selected_profiles):
        applied_profiles.extend(
            PROFILE_REQUIREMENT_INHERITANCE.get(profile, (profile,))
        )
    for profile in dict.fromkeys(applied_profiles):
        labels.extend(by_profile.get(profile, ()))
    return tuple(dict.fromkeys(labels))


def required_label_value(
    record: str,
    body: str,
    label: str,
) -> str | None:
    for candidate in (
        label,
        *REQUIRED_LABEL_ALIASES.get((record, label), ()),
    ):
        value = markdown_label_value(body, candidate)
        if non_placeholder(value):
            return value
    return None


OWNER_DECISION_STATUSES = {
    "accepted",
    "rejected",
    "pending",
    "not-required",
}
OWNER_DECISION_CLAIM_SCOPES = {
    "standard",
    "premium-showcase-sale-readiness",
    "accountable-owner-sensitive",
}
GENERIC_OWNER_DECISION_IDS = {
    "accountable-owner",
    "approver",
    "client",
    "client-owner",
    "decision-owner",
    "human",
    "owner",
    "stakeholder",
    "unknown",
    "tbd",
}
OWNER_DECISION_EVIDENCE_PATTERN = re.compile(
    r"^([^|]+?)\s*\|\s*sha256:([0-9a-f]{64})$"
)
ARTIFACT_BINDING_PATTERN = re.compile(
    r"^(.+?)\s+(?:plus\s+)?sha256:([0-9a-f]{64})$",
    re.I,
)
OWNER_DECISION_EVIDENCE_EXTENSIONS = {".json", ".log", ".md", ".txt"}
OWNER_DECISION_EVIDENCE_MAX_BYTES = 2 * 1024 * 1024
COMPARISON_REPORT_MAX_BYTES = 8 * 1024 * 1024
COMPARISON_DECISION_STATUSES = (
    "accept candidate",
    "revise candidate",
    "reject candidate",
    "insufficient evidence",
    "not performed",
)


def semicolon_fields(value: str) -> dict[str, str]:
    """Parse a compact human-readable key=value record without fixing its order."""

    fields: dict[str, str] = {}
    for segment in value.split(";"):
        if "=" not in segment:
            continue
        key, field_value = segment.split("=", 1)
        normalized_key = re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
        if normalized_key and normalized_key not in fields:
            fields[normalized_key] = field_value.strip()
    return fields


def proportional_owner_disposition_failures(
    body: str,
    *,
    project: Path | None,
    record_path: Path | None,
) -> list[str]:
    """Bind consequential owner decisions without burdening pending drafts."""

    failures: list[str] = []
    value = markdown_label_value(body, "Owner disposition") or ""
    status_match = re.match(
        r"(?i)^(accepted|rejected|pending|not[ -]required)\b",
        value,
    )
    status = (
        status_match.group(1).casefold().replace(" ", "-")
        if status_match
        else ""
    )
    if status not in OWNER_DECISION_STATUSES:
        return [
            "Owner disposition must begin with accepted, rejected, pending, "
            "or not-required"
        ]
    if status == "pending":
        return []
    fields = semicolon_fields(value)
    owner_id = fields.get("owner_id", "")
    reviewed_date = fields.get("reviewed_date", "")
    candidate_id = fields.get("candidate", "")
    evidence_value = fields.get("evidence", "")
    if (
        not non_placeholder(owner_id)
        or owner_id.casefold() in GENERIC_OWNER_DECISION_IDS
    ):
        failures.append(
            "Owner disposition owner_id must be a stable person/account identity"
        )
    try:
        reviewed = date.fromisoformat(reviewed_date)
        if reviewed > datetime.now(timezone.utc).date():
            failures.append("Owner disposition reviewed_date may not be in the future")
    except ValueError:
        failures.append(
            "Owner disposition reviewed_date must be an ISO date (YYYY-MM-DD)"
        )
    if not non_placeholder(candidate_id):
        failures.append("Owner disposition must name the exact candidate")
    build_value = markdown_label_value(body, "Build or artifact ID")
    if build_value and candidate_id != build_value.strip():
        failures.append(
            "Owner disposition candidate must match Build or artifact ID"
        )
    evidence_match = OWNER_DECISION_EVIDENCE_PATTERN.fullmatch(evidence_value)
    if evidence_match is None:
        failures.append(
            "Owner disposition evidence must use "
            "'project/relative/path.ext | sha256:<64 lowercase hex>'"
        )
        return failures
    if project is None or record_path is None:
        return failures
    relative, expected_digest = evidence_match.groups()
    try:
        evidence_path = safe_binding_path(
            project,
            relative,
            record_path=record_path,
        )
        size, actual_digest = file_sha256(evidence_path)
        if size < 1 or size > OWNER_DECISION_EVIDENCE_MAX_BYTES:
            failures.append(
                "Owner disposition evidence has an unsupported size"
            )
        if actual_digest != expected_digest:
            failures.append(
                "Owner disposition evidence sha256 does not match the exact file"
            )
        evidence_text = evidence_path.read_text(encoding="utf-8").casefold()
        for label, token in {
            "status": status,
            "owner ID": owner_id,
            "candidate": candidate_id,
            "reviewed date": reviewed_date,
        }.items():
            if token.casefold() not in evidence_text:
                failures.append(
                    f"Owner disposition evidence must name the exact {label}"
                )
    except (OSError, UnicodeError, StateError) as exc:
        failures.append(f"Owner disposition evidence is invalid: {exc}")
    return failures


def owner_disposition_body_failures(
    record: str,
    body: str,
    *,
    project: Path | None,
    record_path: Path | None,
) -> list[str]:
    if record not in {"direction-proof", "visual-review"}:
        return []
    if PROPORTIONAL_EVIDENCE_CONTRACT in body:
        return proportional_owner_disposition_failures(
            body,
            project=project,
            record_path=record_path,
        )
    failures: list[str] = []
    if record == "direction-proof":
        raw_status = markdown_label_value(
            body,
            "Accountable-owner rendered acceptance",
        ) or ""
        claim_scope = (
            markdown_label_value(body, "Owner decision claim scope") or ""
        ).casefold()
        combined_owner_record = markdown_label_value(
            body,
            "Owner ID, exact candidate/build ID, review date, and evidence path/hash",
        ) or ""
        build_value = markdown_label_value(
            body,
            "Candidate/build ID and reversible checkpoint",
        ) or ""
    else:
        combined_owner_record = markdown_label_value(
            body,
            (
                "Accountable-owner disposition, scope, ID, date, "
                "candidate/build, and evidence"
            ),
        ) or ""
        disposition_fields = semicolon_fields(combined_owner_record)
        raw_status = disposition_fields.get("status", "")
        claim_scope = disposition_fields.get("scope", "").casefold()
        build_value = markdown_label_value(
            body,
            "Build, commit, or artifact ID",
        ) or ""
    owner_fields = semicolon_fields(combined_owner_record)
    status_match = re.match(
        r"(?i)^(accepted|rejected|pending|not[ -]required)\b",
        raw_status,
    )
    status = (
        status_match.group(1).casefold().replace(" ", "-")
        if status_match
        else ""
    )
    if status not in OWNER_DECISION_STATUSES:
        failures.append(
            "Accountable-owner rendered acceptance must begin with accepted, "
            "rejected, pending, or not-required"
        )

    if claim_scope not in OWNER_DECISION_CLAIM_SCOPES:
        failures.append(
            "Owner decision claim scope must be standard, "
            "premium-showcase-sale-readiness, or accountable-owner-sensitive"
        )
    if status == "not-required" and claim_scope != "standard":
        failures.append(
            "not-required owner disposition is allowed only for standard "
            "claim scope"
        )

    owner_id = owner_fields.get("owner_id", "")
    candidate_id = owner_fields.get("candidate", "")
    reviewed_date = owner_fields.get("reviewed_date", "")
    evidence_value = owner_fields.get("evidence", "")
    build_label = (
        "Candidate/build ID and reversible checkpoint"
        if record == "direction-proof"
        else "Build, commit, or artifact ID"
    )
    build_id = build_value.split(";", 1)[0].strip()
    if candidate_id != build_id:
        failures.append(
            "Owner decision candidate/build ID must exactly match "
            f"{build_label}"
        )

    pending_evidence_marker = evidence_value.casefold() in {
        "none",
        "pending",
        "not-reviewed",
    } or evidence_value.casefold().startswith(
        ("none ", "pending ", "not-reviewed ")
    )
    if status == "pending":
        if (
            owner_id != "not-reviewed"
            and owner_id.casefold() in GENERIC_OWNER_DECISION_IDS
        ):
            failures.append(
                "Pending owner decision owner ID must be not-reviewed or a "
                "stable person/account identity"
            )
        if reviewed_date != "not-reviewed":
            failures.append(
                "Pending owner decision reviewed date must be not-reviewed"
            )
    else:
        if (
            not non_placeholder(owner_id)
            or owner_id.casefold() in GENERIC_OWNER_DECISION_IDS
        ):
            failures.append(
                "Owner decision owner ID must be a stable person/account "
                "identity, not a role"
            )
        try:
            parsed_date = date.fromisoformat(reviewed_date)
            if parsed_date > datetime.now(timezone.utc).date():
                failures.append(
                    "Owner decision reviewed date may not be in the future"
                )
        except ValueError:
            failures.append(
                "Owner decision reviewed date must be an ISO date (YYYY-MM-DD)"
            )
        if pending_evidence_marker:
            failures.append(
                "Accepted, rejected, and not-required owner dispositions "
                "require hash-bound decision evidence"
            )

    if pending_evidence_marker and status == "pending":
        return failures
    evidence_match = OWNER_DECISION_EVIDENCE_PATTERN.fullmatch(evidence_value)
    if not evidence_match:
        failures.append(
            "Owner decision evidence must use "
            "'project/relative/path.ext | sha256:<64 lowercase hex>'"
        )
        return failures
    relative, expected_digest = evidence_match.groups()
    if project is None or record_path is None:
        return failures
    try:
        evidence_path = safe_binding_path(
            project,
            relative,
            record_path=record_path,
        )
    except StateError as exc:
        failures.append(f"Owner decision evidence is invalid: {exc}")
        return failures
    if evidence_path.suffix.casefold() not in OWNER_DECISION_EVIDENCE_EXTENSIONS:
        failures.append(
            "Owner decision evidence must be UTF-8 JSON, Markdown, text, or log"
        )
        return failures
    size, actual_digest = file_sha256(evidence_path)
    if size < 1 or size > OWNER_DECISION_EVIDENCE_MAX_BYTES:
        failures.append(
            "Owner decision evidence must contain 1 byte through "
            f"{OWNER_DECISION_EVIDENCE_MAX_BYTES} bytes"
        )
        return failures
    if actual_digest != expected_digest:
        failures.append(
            "Owner decision evidence sha256 does not match the exact file"
        )
        return failures
    try:
        evidence_text = evidence_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        failures.append("Owner decision evidence must be valid UTF-8 text")
        return failures
    normalized_evidence = evidence_text.casefold()
    required_tokens = {
        "status": status,
        "owner ID": owner_id,
        "candidate/build ID": candidate_id,
    }
    if status != "pending":
        required_tokens["reviewed date"] = reviewed_date
    missing = sorted(
        label
        for label, value in required_tokens.items()
        if value.casefold() not in normalized_evidence
    )
    if missing:
        failures.append(
            "Owner decision evidence must name the exact "
            + ", ".join(missing)
        )
    return failures


def bound_artifact(
    value: str,
    *,
    project: Path,
    record_path: Path,
    label: str,
) -> tuple[Path | None, list[str]]:
    match = ARTIFACT_BINDING_PATTERN.fullmatch(value.strip())
    if match is None:
        return None, [
            f"{label} must use project/relative/path plus "
            "sha256:<64 lowercase hex>"
        ]
    relative_path, recorded_hash = match.groups()
    try:
        artifact = safe_binding_path(
            project,
            relative_path.strip(),
            record_path=record_path,
        )
        _size, actual_hash = file_sha256(artifact)
    except (OSError, StateError) as exc:
        return None, [f"{label} is invalid: {exc}"]
    if recorded_hash != actual_hash:
        return artifact, [f"{label} SHA-256 does not match its artifact"]
    return artifact, []


def load_schema3_render_review_adapter() -> tuple[object | None, str | None]:
    """Load the shipped schema-3 verifier without duplicating its contract.

    Project Contrast already owns the narrow parser for renderer output.  The
    state gate uses that verifier only for evidence integrity; it does not
    import its comparison judgments or turn a renderer run into an aesthetic
    pass.
    """

    adapter_path = Path(__file__).with_name("project_contrast_audit.py")
    module_name = "design_dna_schema3_render_review_adapter"
    try:
        module = load_bundled_source_module(
            module_name,
            adapter_path,
            retain=True,
        )
    except Exception as exc:  # pragma: no cover - defensive package boundary
        sys.modules.pop(module_name, None)
        return None, f"the packaged schema-3 rendered-review verifier could not load: {exc}"
    return module, None


def schema3_rendered_review_context(
    body: str,
    *,
    project: Path,
    record_path: Path,
) -> tuple[dict[str, object] | None, list[str]]:
    """Resolve one final visual-review report to its exact schema-3 captures."""

    failures: list[str] = []
    report_record = (
        markdown_label_value(
            body,
            "Rendered-review report path, hash, contract, and execution result",
        )
        or ""
    )
    report_value = report_record.split(";", 1)[0].strip()
    if not report_value:
        return None, [
            "Standard+ visual review must bind a schema-3 rendered-review report"
        ]
    report_path, report_failures = bound_artifact(
        report_value,
        project=project,
        record_path=record_path,
        label="Rendered-review report binding",
    )
    failures.extend(report_failures)
    if report_path is None or report_failures:
        return None, failures
    if report_path.name != "render-review.json":
        return None, [
            *failures,
            "Rendered-review report must bind render-review.json",
        ]
    try:
        relative_report = report_path.relative_to(project).as_posix()
    except ValueError:
        return None, [
            *failures,
            "Rendered-review report must remain inside the selected project",
        ]
    _size, report_digest = file_sha256(report_path)
    adapter, adapter_failure = load_schema3_render_review_adapter()
    if adapter is None:
        return None, [*failures, str(adapter_failure)]
    try:
        budget = getattr(adapter, "EvidenceBudget")()
        context = getattr(adapter, "load_schema3_render_review")(
            project,
            {"path": relative_report, "sha256": report_digest},
            "visual-review.rendered-review",
            budget,
        )
    except Exception as exc:
        message = getattr(exc, "message", str(exc))
        return None, [
            *failures,
            "Standard+ visual review requires a valid path-bound schema-3 "
            f"renderer report: {message}",
        ]
    if not isinstance(context, dict):
        return None, [
            *failures,
            "Standard+ visual review could not resolve schema-3 renderer context",
        ]
    build_id = context.get("build_id")
    source_sha = context.get("source_snapshot_manifest_sha256")
    report = context.get("report")
    if not isinstance(build_id, str) or not isinstance(source_sha, str):
        return None, [
            *failures,
            "Schema-3 rendered-review context has no exact build/source identity",
        ]
    record_build = markdown_label_value(body, "Build or artifact ID") or ""
    if build_id != record_build:
        failures.append(
            "Rendered-review build ID must match the visual-review build ID"
        )
    source_identity = (
        markdown_label_value(body, "Source/workspace identity and SHA-256")
        or ""
    ).casefold()
    if source_sha.casefold() not in source_identity:
        failures.append(
            "Source/workspace identity must name the exact schema-3 source-snapshot SHA-256"
        )
    contract_value = report_record.casefold()
    required_tokens = (
        build_id.casefold(),
        source_sha.casefold(),
        "execution_ok=true",
    )
    if any(token not in contract_value for token in required_tokens):
        failures.append(
            "Rendered-review binding must name the exact build ID, "
            "source-snapshot SHA-256, and execution_ok=true"
        )
    if isinstance(report, dict):
        contract = report.get("capture_contract")
        mode = contract.get("contract_mode") if isinstance(contract, dict) else None
        if not isinstance(mode, str) or mode.casefold() not in contract_value:
            failures.append(
                "Rendered-review binding must name the exact schema-3 capture mode"
            )
        contact = report.get("artifacts")
        contact = contact.get("contact_sheet") if isinstance(contact, dict) else None
        contact_value = (
            markdown_label_value(body, "Coverage contact sheet or artifact index")
            or ""
        )
        contact_path, contact_failures = bound_artifact(
            contact_value,
            project=project,
            record_path=record_path,
            label="Coverage contact sheet or artifact index",
        )
        failures.extend(contact_failures)
        if not isinstance(contact, dict) or contact_path is None:
            failures.append(
                "Rendered-review report must bind its contact-sheet artifact"
            )
        else:
            raw_contact_path = contact.get("path")
            raw_contact_hash = contact.get("sha256")
            if not isinstance(raw_contact_path, str) or not isinstance(raw_contact_hash, str):
                failures.append(
                    "Rendered-review contact-sheet metadata is incomplete"
                )
            else:
                expected_contact = lexical_absolute(
                    report_path.parent.joinpath(*PurePosixPath(raw_contact_path).parts)
                )
                _contact_size, actual_contact_hash = file_sha256(contact_path)
                if (
                    contact_path != expected_contact
                    or actual_contact_hash != raw_contact_hash
                ):
                    failures.append(
                        "Coverage contact-sheet binding must match the schema-3 "
                        "render-review artifact"
                    )
    else:
        failures.append("Schema-3 rendered-review context has no report object")
    return context, failures


def review_disposition(value: str) -> str:
    """Return a normalized review applicability decision, or an empty string."""

    normalized = value.strip().casefold().replace("not applicable", "not-applicable")
    for status in REVIEW_CLOSURE_DISPOSITIONS:
        if normalized == status or normalized.startswith(status + ";") or normalized.startswith(status + ":"):
            return status
    return ""


def route_from_review_scope(value: str) -> str:
    """Take the route token before a human-readable state/body annotation."""

    return value.split(";", 1)[0].strip().split(maxsplit=1)[0]


def schema3_capture_path(
    report_path: Path,
    capture: object,
) -> tuple[Path | None, str | None]:
    if not isinstance(capture, dict):
        return None, None
    screenshot = capture.get("screenshot")
    if not isinstance(screenshot, dict):
        return None, None
    path = screenshot.get("path")
    digest = screenshot.get("sha256")
    if not isinstance(path, str) or not isinstance(digest, str):
        return None, None
    return (
        lexical_absolute(report_path.parent.joinpath(*PurePosixPath(path).parts)),
        digest,
    )


def schema3_capture_route(capture: object) -> str | None:
    if not isinstance(capture, dict):
        return None
    final_url = capture.get("final_url")
    if not isinstance(final_url, str):
        return None
    return urlsplit(final_url).path or "/"


def visual_review_schema3_capture_matrix_failures(
    body: str,
    *,
    project: Path,
    record_path: Path,
    context: dict[str, object],
    required_evidence_capabilities: tuple[str, ...] | set[str] = (),
) -> list[str]:
    """Bind final review coverage to real schema-3 wide/narrow captures."""

    failures: list[str] = []
    sections = markdown_sections(body)
    captures_by_id = context.get("captures_by_id")
    report_path = context.get("report_path")
    if not isinstance(captures_by_id, dict) or not isinstance(report_path, Path):
        return ["Schema-3 rendered-review context has no capture index"]

    capture_paths: dict[tuple[Path, str], str] = {}
    capture_routes: dict[str, str] = {}
    for capture_id, capture in captures_by_id.items():
        if not isinstance(capture_id, str):
            continue
        path, digest = schema3_capture_path(report_path, capture)
        route = schema3_capture_route(capture)
        if path is not None and digest is not None:
            capture_paths[(path, digest)] = capture_id
        if route is not None:
            capture_routes[capture_id] = route

    review_headers, review_rows = markdown_first_table(
        sections.get("Rendered review", "")
    )
    if review_headers == (
        "Route/state",
        "Viewport/context",
        "Rendered PNG path and SHA-256",
        "Observation",
    ):
        artifact_index = review_headers.index("Rendered PNG path and SHA-256")
        for row_number, row in enumerate(review_rows, start=1):
            if len(row) != len(review_headers):
                continue
            artifact, artifact_failures = bound_artifact(
                row[artifact_index],
                project=project,
                record_path=record_path,
                label=f"Rendered review row {row_number} artifact",
            )
            if artifact_failures or artifact is None:
                continue
            _size, digest = file_sha256(artifact)
            capture_id = capture_paths.get((artifact, digest))
            if capture_id is None:
                failures.append(
                    "Rendered review row "
                    f"{row_number} must be the exact PNG emitted by a bound "
                    "schema-3 renderer capture"
                )
                continue
            expected_route = capture_routes.get(capture_id)
            observed_route = route_from_review_scope(row[0])
            if expected_route is not None and observed_route != expected_route:
                failures.append(
                    "Rendered review row "
                    f"{row_number} route/state does not match its bound schema-3 capture"
                )

    scope_headers, scope_rows = markdown_first_table(
        sections.get("Review scope and capture rationale", "")
    )
    if scope_headers != REVIEW_SCOPE_CAPTURE_HEADERS or not scope_rows:
        return [
            *failures,
            "Review scope and capture rationale needs the exact route/body, "
            "risk, wide, narrow, and disposition table",
        ]
    report_routes = set(capture_routes.values())
    declared_routes: set[str] = set()
    applicable_count = 0
    reviewed_capture_ids: set[str] = set()
    for row_number, row in enumerate(scope_rows, start=1):
        if len(row) != len(REVIEW_SCOPE_CAPTURE_HEADERS) or any(
            not non_placeholder(cell) for cell in row
        ):
            failures.append(
                f"Review scope row {row_number} is incomplete"
            )
            continue
        route = route_from_review_scope(row[0])
        declared_routes.add(route)
        reason = row[1]
        wide_id = row[2]
        narrow_id = row[3]
        disposition = review_disposition(row[4])
        if route not in report_routes:
            failures.append(
                f"Review scope row {row_number} route/body is not represented "
                "by the schema-3 report"
            )
        if not disposition:
            failures.append(
                f"Review scope row {row_number} must declare applicable, "
                "not-applicable, or blocked"
            )
            continue
        if len(reason.strip()) < 24:
            failures.append(
                f"Review scope row {row_number} needs a substantive project "
                "risk or not-applicable reason"
            )
        if disposition != "applicable":
            if wide_id.casefold() not in {"not-applicable", "not applicable", "n/a", "none"} or narrow_id.casefold() not in {"not-applicable", "not applicable", "n/a", "none"}:
                failures.append(
                    f"Review scope row {row_number} must not name wide/narrow "
                    "capture IDs when its body is not applicable or blocked"
                )
            continue
        applicable_count += 1
        wide = captures_by_id.get(wide_id)
        narrow = captures_by_id.get(narrow_id)
        if not isinstance(wide, dict) or not isinstance(narrow, dict):
            failures.append(
                f"Review scope row {row_number} must name exact schema-3 wide "
                "and narrow capture IDs"
            )
            continue
        if wide_id == narrow_id:
            failures.append(
                f"Review scope row {row_number} wide and narrow capture IDs "
                "must be different"
            )
        if capture_routes.get(wide_id) != route or capture_routes.get(narrow_id) != route:
            failures.append(
                f"Review scope row {row_number} capture IDs must belong to its "
                "declared route/body"
            )
        wide_viewport = wide.get("viewport")
        narrow_viewport = narrow.get("viewport")
        wide_path, wide_hash = schema3_capture_path(report_path, wide)
        narrow_path, narrow_hash = schema3_capture_path(report_path, narrow)
        if (
            not isinstance(wide_viewport, dict)
            or not isinstance(narrow_viewport, dict)
            or not isinstance(wide_viewport.get("width"), int)
            or not isinstance(narrow_viewport.get("width"), int)
            or wide_viewport["width"] <= narrow_viewport["width"]
            or wide_hash == narrow_hash
            or wide_path is None
            or narrow_path is None
        ):
            failures.append(
                f"Review scope row {row_number} must bind distinct meaningful "
                "wide and narrow schema-3 evidence"
            )
        reviewed_capture_ids.update({wide_id, narrow_id})
    if not applicable_count:
        failures.append(
            "Review scope must include at least one applicable final rendered body"
        )
    missing_routes = sorted(report_routes - declared_routes)
    if missing_routes:
        failures.append(
            "Review scope must explicitly disposition every route represented "
            "by the schema-3 report: " + ", ".join(missing_routes)
        )

    def closure_table_failures(
        section_name: str,
        expected_headers: tuple[str, ...],
        required_focuses: set[str],
    ) -> list[str]:
        local: list[str] = []
        headers, rows = markdown_first_table(sections.get(section_name, ""))
        if headers != expected_headers or not rows:
            return [
                f"{section_name} needs its exact applicability, rendered "
                "evidence, and result table"
            ]
        found: set[str] = set()
        for row_number, row in enumerate(rows, start=1):
            if len(row) != len(expected_headers) or any(
                not non_placeholder(cell) for cell in row
            ):
                local.append(f"{section_name} row {row_number} is incomplete")
                continue
            focus = row[0].casefold()
            if focus in required_focuses:
                found.add(focus)
            disposition = review_disposition(row[1])
            if not disposition:
                local.append(
                    f"{section_name} row {row_number} must declare applicable, "
                    "not-applicable, or blocked"
                )
            artifact, artifact_failures = bound_artifact(
                row[2],
                project=project,
                record_path=record_path,
                label=f"{section_name} row {row_number} rendered evidence",
            )
            local.extend(artifact_failures)
            if artifact is not None and not artifact_failures:
                _size, digest = file_sha256(artifact)
                if (artifact, digest) not in capture_paths:
                    local.append(
                        f"{section_name} row {row_number} must bind an exact "
                        "schema-3 rendered PNG capture"
                    )
            if len(row[3].strip()) < 24:
                local.append(
                    f"{section_name} row {row_number} needs a substantive "
                    "result or limitation"
                )
        missing = sorted(required_focuses - found)
        if missing:
            local.append(
                f"{section_name} is missing required closure rows: "
                + ", ".join(missing)
            )
        return local

    failures.extend(
        closure_table_failures(
            "First-impression and surface-fidelity review",
            SURFACE_FIDELITY_HEADERS,
            {"first impression and surface fidelity"},
        )
    )
    credibility_section = sections.get(
        "Artifact credibility and cumulative-pattern review",
        "",
    )
    for label in ARTIFACT_CREDIBILITY_LABELS:
        value = markdown_label_value(credibility_section, label)
        if value is None or not non_placeholder(value):
            failures.append(
                "Artifact credibility and cumulative-pattern review needs a "
                f"substantive {label!r} value"
            )
    credibility_disposition = (
        markdown_label_value(
            credibility_section,
            "Artifact credibility disposition",
        )
        or ""
    ).strip().casefold()
    if credibility_disposition not in {
        "keep",
        "revise",
        "reopen direction",
        "reject",
        "blocked",
    }:
        failures.append(
            "Artifact credibility disposition must be keep, revise, reopen "
            "direction, reject, or blocked"
        )
    failures.extend(
        closure_table_failures(
            "Preship and specificity closure",
            PRESHIP_SPECIFICITY_HEADERS,
            {
                "adversarial specificity review",
                "artifact credibility and cumulative pattern",
                "preship gate",
            },
        )
    )
    if "reference-led-direction" in set(required_evidence_capabilities):
        failures.extend(
            final_source_fidelity_section_failures(
                body, project=project, record_path=record_path
            )
        )
        closure_section = sections.get(
            "Reference-led direction closure (required for public candidates)",
            "",
        )
        failures.extend(reference_led_closure_label_failures(closure_section))
        failures.extend(
            mechanism_diff_failures(
                closure_section, project=project, record_path=record_path
            )
        )
        failures.extend(
            structure_diff_failures(
                closure_section, project=project, record_path=record_path
            )
        )
        final_build_id = (
            markdown_label_value(body, "Build or artifact ID") or ""
        ).strip()
        if not non_placeholder(final_build_id):
            failures.append(
                "Reference-led direction closure needs the canonical final build ID."
            )
        else:
            failures.extend(
                final_gate_failures(
                    closure_section,
                    project=project,
                    record_path=record_path,
                    expected_build_id=final_build_id,
                )
            )
        failures.extend(
            closure_table_failures(
                "Reference-led direction closure (required for public candidates)",
                REFERENCE_LED_DIRECTION_CLOSURE_HEADERS,
                {"reference-led direction"},
            )
        )
    return failures


REFERENCE_LED_CLOSURE_LABELS = (
    "Dossier result",
    "Candidate selection result",
    "Complete-study result",
    "Brief-fit result",
    "Positive synthesis",
    "Negative counterevidence",
    "Rights boundary",
    "Lineage result",
    "Rendered result",
    "Dominant grammar result",
    "Combination result",
    "Route manifest",
    "Gate result",
    "Mechanism diff",
    "Structure diff",
)
REFERENCE_LED_CLOSURE_DISPOSITIONS = {
    "keep",
    "revise",
    "reopen direction",
    "reject",
    "blocked",
}
FINAL_SOURCE_FIDELITY_LABELS = (
    "Route manifest ID and binding",
    "Final build ID and tree SHA-256",
    "First-screen authorization binding",
    "Final gate binding",
    "Gate run ID and runtime identity SHA-256",
    "Exact coverage matrix result",
    "Verdict",
)


def final_source_fidelity_section_failures(
    body: str,
    *,
    project: Path,
    record_path: Path,
) -> list[str]:
    failures: list[str] = []
    section = markdown_sections(body).get("Final source-fidelity gate", "")
    if not section:
        return ["Reference-led final review is missing `Final source-fidelity gate`."]
    values: dict[str, str] = {}
    for label in FINAL_SOURCE_FIDELITY_LABELS:
        value = (markdown_label_value(section, label) or "").strip()
        values[label] = value
        if not non_placeholder(value):
            failures.append(f"Final source-fidelity gate needs {label!r}.")
    gate_value = values["Final gate binding"]
    gate_path, gate_failures = bound_artifact(
        gate_value,
        project=project,
        record_path=record_path,
        label="Final source-fidelity gate binding",
    )
    failures.extend(gate_failures)
    expected_gate = (project / ".design-dna" / "evidence" / "gate.json").resolve()
    if gate_path is None or gate_failures:
        return failures
    if gate_path.resolve() != expected_gate:
        return [*failures, "Final source-fidelity gate must bind .design-dna/evidence/gate.json."]
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [*failures, f"Final source-fidelity gate record is unreadable: {exc}"]
    if not isinstance(gate, dict):
        return [*failures, "Final source-fidelity gate record must be an object."]
    manifest_path = project / ".design-dna" / "route-manifest.json"
    manifest_value = values["Route manifest ID and binding"]
    if (
        not manifest_path.is_file()
        or str(gate.get("manifest_id")) not in manifest_value
        or str(gate.get("route_manifest_sha256")) not in manifest_value
    ):
        failures.append("Final source-fidelity manifest summary does not match gate.json.")
    build_value = values["Final build ID and tree SHA-256"]
    if (
        str(gate.get("build_id")) not in build_value
        or str(gate.get("build_tree_sha256_before")) not in build_value
    ):
        failures.append("Final source-fidelity build/tree summary does not match gate.json.")
    predecessor = gate.get("prebuild_authorization")
    predecessor_value = values["First-screen authorization binding"]
    if (
        not isinstance(predecessor, dict)
        or str(predecessor.get("path")) not in predecessor_value
        or str(predecessor.get("sha256")) not in predecessor_value
    ):
        failures.append("Final source-fidelity predecessor summary does not match gate.json.")
    runtime_value = values["Gate run ID and runtime identity SHA-256"]
    runtime_sha = canonical_json_sha256(gate.get("runtime_identity"))
    if str(gate.get("run_id")) not in runtime_value or runtime_sha not in runtime_value:
        failures.append("Final source-fidelity run/runtime summary does not match gate.json.")
    coverage_value = values["Exact coverage matrix result"]
    expected_count = len(gate.get("coverage_matrix", [])) if isinstance(gate.get("coverage_matrix"), list) else -1
    served = gate.get("served_content_identity")
    served_sha = served.get("sha256") if isinstance(served, dict) else None
    if str(expected_count) not in coverage_value or not served_sha or served_sha not in coverage_value:
        failures.append("Final source-fidelity coverage summary does not match gate.json.")
    if values["Verdict"] != gate.get("verdict") or not values["Verdict"].startswith("GATE PASS: final"):
        failures.append("Final source-fidelity verdict must exactly equal the final gate verdict.")
    return failures


def mechanism_diff_failures(
    section: str, *, project: Path, record_path: Path
) -> list[str]:
    """The finished build is read by the same harness as its references.

    The closure binds the compare_mechanisms.mjs record for the final build,
    and it must pass: the references' scroll and pointer mechanisms arrived,
    no single device is overused, and the page is not a skeleton. A build
    reviewed only by eye passes on color and type every time; this is the
    check that asks whether the falls came with it.
    """
    label = "Reference-led direction closure Mechanism diff"
    value = (markdown_label_value(section, "Mechanism diff") or "").strip()
    if not non_placeholder(value) or value.startswith("__REPLACE_WITH"):
        return [f"{label} must bind the compare_mechanisms.mjs record for the final build."]
    artifact, artifact_failures = bound_artifact(
        value, project=project, record_path=record_path, label=label
    )
    if artifact_failures or artifact is None:
        return artifact_failures
    expected = (project / ".design-dna" / "evidence" / "mechanism-diff.json").resolve()
    if artifact.resolve() != expected:
        return [f"{label} must bind .design-dna/evidence/mechanism-diff.json."]
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{label} is not readable JSON: {exc}"]
    identity_failures = packaged_runtime_record_failures(
        payload, tool="compare_mechanisms.mjs", require_pass=True
    )
    if identity_failures:
        return [f"{label}: {failure}" for failure in identity_failures]
    if payload.get("pass") is not True:
        return [
            f"{label} did not pass: "
            + str(payload.get("verdict") or "the build does not carry the references' mechanisms")
            + ". Return to the transfer map; a build that lost the mechanisms is a skeleton."
        ]
    return []


def structure_diff_failures(
    section: str, *, project: Path, record_path: Path
) -> list[str]:
    """Does the finished first screen look like the reference it names?

    Every other gate proves the producer looked. This one compares what it
    built to what it looked at: which kind of thing fills the first screen,
    where the ink sits, what is against the edges and in the corners, and the
    proportions of the type. It is the check that would have caught a build
    whose research produced six references and whose page reproduced one
    button.
    """
    label = "Reference-led direction closure Structure diff"
    value = (markdown_label_value(section, "Structure diff") or "").strip()
    if not non_placeholder(value) or value.startswith("__REPLACE_WITH"):
        return [
            f"{label} must bind the compare_structure.mjs record for the final "
            "build's first screen."
        ]
    artifact, artifact_failures = bound_artifact(
        value, project=project, record_path=record_path, label=label
    )
    if artifact_failures or artifact is None:
        return artifact_failures
    expected = (project / ".design-dna" / "evidence" / "structure-diff.json").resolve()
    if artifact.resolve() != expected:
        return [f"{label} must bind .design-dna/evidence/structure-diff.json."]
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{label} is not readable JSON: {exc}"]
    identity_failures = packaged_runtime_record_failures(
        payload, tool="compare_structure.mjs", require_pass=True
    )
    if identity_failures:
        return [f"{label}: {failure}" for failure in identity_failures]
    if not payload.get("census_sha256"):
        return [
            f"{label} must take its route list from the component census "
            "(--census), so that every route the build renders is compared. A "
            "run whose routes the producer chose compares the screen it "
            "copied and skips the pages it invented."
        ]
    if payload.get("pass") is not True:
        return [
            f"{label} did not pass: "
            + str(payload.get("verdict") or "the first screen does not resemble any selected reference")
            + ". Rebuild the first screen from the reference's own screen, not "
            "from a description of it."
        ]
    return []


def packaged_script_schema_version(path: Path) -> int | None:
    body = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"\bSCHEMA_VERSION\s*=\s*(\d+)",
        body,
    )
    if match:
        return int(match.group(1))
    if "PRODUCER_OUTPUT_SCHEMA_VERSION" in body:
        contract = path.parent / "provenance_contract.mjs"
        contract_match = re.search(
            r"\bPRODUCER_OUTPUT_SCHEMA_VERSION\s*=\s*(\d+)",
            contract.read_text(encoding="utf-8", errors="replace"),
        )
        if contract_match:
            return int(contract_match.group(1))
    return None


def expected_gate_coverage(
    routes: list[dict[str, object]], viewports: list[dict[str, object]]
) -> list[dict[str, object]]:
    return [
        {
            "route_key": route["key"],
            "url": route["url"],
            "mapped_reference_rank": route["mapped_reference_rank"],
            "mapped_reference_id": route["mapped_reference_id"],
            "mapped_reference_observation": route["mapped_reference_observation"],
            "mapped_reference_sha256": route["mapped_reference_sha256"],
            "viewport": viewport["name"],
            "width": viewport["width"],
            "height": viewport["height"],
            "states": route["states"],
        }
        for route in routes
        for viewport in viewports
    ]


def gate_runtime_evidence_failures(
    gate: dict[str, object],
    *,
    project: Path,
    manifest: dict[str, object],
    phase: str,
    require_current_tree: bool,
) -> list[str]:
    """Independently validate a gate and every canonical direct artifact."""

    failures: list[str] = []
    scripts = Path(__file__).resolve().parent
    gate_script = scripts / "gate.py"
    expected_runtime = packaged_gate_runtime_identity()
    if gate.get("tool") != "gate.py" or gate.get("schema_version") != 2:
        failures.append("Gate record must use gate.py schema_version 2.")
    if gate.get("producer_script_sha256") != expected_runtime.get("gate.py"):
        failures.append("Gate record does not bind current gate.py bytes.")
    if gate.get("runtime_identity") != expected_runtime:
        failures.append("Gate record runtime identity is stale or incomplete.")
    if gate.get("phase") != phase:
        failures.append(f"Gate record phase must be {phase}.")
    run_id = gate.get("run_id")
    build_id = gate.get("build_id")
    if not isinstance(run_id, str) or re.fullmatch(r"[0-9a-f]{32}", run_id) is None:
        failures.append("Gate record run_id is invalid.")
    if not isinstance(build_id, str) or ROUTE_MANIFEST_ID.fullmatch(build_id) is None:
        failures.append("Gate record build_id is invalid.")
    if gate.get("project") != str(project.resolve()) or gate.get("project_identity") != {
        "root": str(project.resolve())
    }:
        failures.append("Gate record belongs to another project root.")
    manifest_path = project / ".design-dna" / "route-manifest.json"
    manifest_sha = file_sha256(manifest_path)[1] if manifest_path.is_file() else None
    if (
        gate.get("manifest_id") != manifest.get("manifest_id")
        or gate.get("route_manifest_sha256") != manifest_sha
    ):
        failures.append("Gate record does not bind the current manifest ID and bytes.")
    visible_path = project / ".design-dna" / "visible-decision-sources.json"
    visible_sha = file_sha256(visible_path)[1] if visible_path.is_file() else None
    if gate.get("visible_decision_source_manifest") != {
        "path": ".design-dna/visible-decision-sources.json",
        "sha256": visible_sha,
    }:
        failures.append("Gate record does not bind the current preimplementation visible-decision source bytes.")
    dossier_path = project / ".design-dna" / "reference-dossier.md"
    if (
        gate.get("dossier") != str(dossier_path.resolve())
        or not dossier_path.is_file()
        or gate.get("dossier_core_sha256") != dossier_core_sha256(dossier_path)
        or (
            phase == "final"
            and gate.get("dossier_sha256") != file_sha256(dossier_path)[1]
        )
    ):
        failures.append("Gate record does not bind the current dossier identity.")
    before = gate.get("build_tree_sha256_before")
    after = gate.get("build_tree_sha256_after")
    if (
        not isinstance(before, str)
        or SHA256_HEX.fullmatch(before) is None
        or after != before
        or gate.get("build_stable") is not True
    ):
        failures.append("Gate record does not prove one byte-stable project tree.")
    if require_current_tree and before != project_tree_identity(project):
        failures.append("Gate project tree has changed since the recorded run.")

    planned_routes = manifest.get("routes")
    viewports = manifest.get("viewports")
    if not isinstance(planned_routes, list) or not isinstance(viewports, list):
        return [*failures, "Current route manifest has invalid routes/viewports."]
    if gate.get("planned_routes") != planned_routes or gate.get("viewports_checked") != viewports:
        failures.append("Gate planned route or viewport set differs from the manifest.")
    active_routes: list[dict[str, object]]
    if phase == "final":
        active_routes = planned_routes
        if gate.get("route_key") is not None or gate.get("routes") != planned_routes:
            failures.append("Final gate must cover the complete manifest route set.")
    else:
        route_key = gate.get("route_key")
        active_routes = [
            route for route in planned_routes
            if isinstance(route, dict) and route.get("key") == route_key
        ]
        if len(active_routes) != 1 or gate.get("routes") != active_routes:
            failures.append("First-screen gate route object is not the exact manifested route.")
    expected_coverage = expected_gate_coverage(active_routes, viewports)
    if gate.get("coverage_matrix") != expected_coverage:
        failures.append("Gate coverage matrix is not the exact unique route/profile/state matrix.")
    expected_states = sorted(
        {
            str(state.get("id"))
            for route in active_routes
            for state in route.get("states", [])
            if isinstance(state, dict)
        }
    )
    if gate.get("states_checked") != expected_states:
        failures.append("Gate states_checked differs from the manifested state IDs.")
    served_failures = served_content_identity_failures(
        gate.get("served_content_identity"),
        expected_routes=active_routes,
        expected_viewports=viewports,
    )
    failures.extend(f"Gate {failure}" for failure in served_failures)

    prefix = "first-screen-" if phase == "first-screen" else ""
    artifact_root = ".design-dna/evidence"
    if phase == "first-screen":
        authorization_id = gate.get("authorization_id")
        if not isinstance(authorization_id, str) or re.fullmatch(
            r"[0-9a-f]{32}", authorization_id
        ) is None:
            failures.append("First-screen gate authorization_id is invalid.")
            authorization_id = "invalid"
        artifact_root += f"/prebuild-runs/{authorization_id}"
        expected_manifest_snapshot = {
            "path": f"{artifact_root}/route-manifest.json",
            "sha256": manifest_sha,
        }
        dossier_snapshot_path = project / PurePosixPath(
            f"{artifact_root}/reference-dossier.md"
        )
        expected_dossier_snapshot = {
            "path": f"{artifact_root}/reference-dossier.md",
            "sha256": (
                file_sha256(dossier_snapshot_path)[1]
                if dossier_snapshot_path.is_file()
                else None
            ),
        }
        expected_visible_snapshot = {
            "path": f"{artifact_root}/visible-decision-sources.json",
            "sha256": visible_sha,
        }
        if gate.get("manifest_snapshot") != expected_manifest_snapshot:
            failures.append("First-screen gate immutable manifest snapshot binding is invalid.")
        if gate.get("dossier_snapshot") != expected_dossier_snapshot:
            failures.append("First-screen gate immutable dossier snapshot binding is invalid.")
        if gate.get("visible_decision_snapshot") != expected_visible_snapshot:
            failures.append("First-screen gate immutable visible-decision snapshot binding is invalid.")
    elif (
        gate.get("manifest_snapshot") is not None
        or gate.get("dossier_snapshot") is not None
        or gate.get("visible_decision_snapshot") is not None
    ):
        failures.append("Final gate must not masquerade as an immutable first-screen snapshot.")
    expected_artifacts: dict[str, str | None] = {
        ".design-dna/visible-decision-sources.json": None,
        (
            f"{artifact_root}/route-manifest.json"
            if phase == "first-screen"
            else ".design-dna/route-manifest.json"
        ): None,
        f"{artifact_root}/{prefix}component-census.json": "scan_build_components.mjs",
        f"{artifact_root}/{prefix}style-provenance.json": "check_style_provenance.mjs",
        f"{artifact_root}/{prefix}structure-diff.json": "compare_structure.mjs",
        f"{artifact_root}/{prefix}mechanism-diff.json": "compare_mechanisms.mjs",
        f"{artifact_root}/{prefix}signature-transfer.json": "check_signature_transfer.mjs",
    }
    if phase == "first-screen":
        expected_artifacts[f"{artifact_root}/reference-dossier.md"] = None
        expected_artifacts[f"{artifact_root}/visible-decision-sources.json"] = None
    for route in active_routes:
        for viewport in viewports:
            expected_artifacts[
                f"{artifact_root}/build-{prefix}{route['key']}-{viewport['name']}-styles.json"
            ] = "extract_reference_styles.mjs"
    if phase != "first-screen":
        predecessor = gate.get("prebuild_authorization")
        if isinstance(predecessor, dict) and isinstance(predecessor.get("path"), str):
            expected_artifacts[predecessor["path"]] = None
        else:
            failures.append("Final gate has no prebuild authorization binding.")

    expected_frame_bytes: dict[str, int] = {}
    for frame_record_relative in (
        f"{artifact_root}/{prefix}component-census.json",
        f"{artifact_root}/{prefix}mechanism-diff.json",
    ):
        frame_record_path = (project / PurePosixPath(frame_record_relative)).resolve()
        if not frame_record_path.is_file():
            continue
        try:
            frame_payload = json.loads(frame_record_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        frame_failures, frame_bindings = generated_interaction_frame_bindings(
            frame_payload, record_path=frame_record_path
        )
        failures.extend(
            f"Gate artifact {frame_record_relative}: {failure}"
            for failure in frame_failures
        )
        for binding in frame_bindings:
            relative_frame = binding["file"].relative_to(project).as_posix()
            expected_artifacts[relative_frame] = None
            expected_frame_bytes[relative_frame] = int(binding["bytes"])

    ledger = gate.get("evidence_hashes")
    ledger_by_path: dict[str, dict[str, object]] = {}
    if not isinstance(ledger, list):
        failures.append("Gate evidence ledger must be a list.")
        ledger = []
    for index, entry in enumerate(ledger, start=1):
        if not isinstance(entry, dict):
            failures.append(f"Gate evidence entry {index} is not an object.")
            continue
        relative = entry.get("path")
        digest = entry.get("sha256")
        if (
            not isinstance(relative, str)
            or relative in ledger_by_path
            or not isinstance(digest, str)
            or SHA256_HEX.fullmatch(digest) is None
        ):
            failures.append(f"Gate evidence entry {index} is duplicate or invalid.")
            continue
        ledger_by_path[relative] = entry
    if set(ledger_by_path) != set(expected_artifacts):
        failures.append("Gate evidence ledger does not contain the exact canonical artifact set.")

    aggregate_served_hashes: set[str] = set()
    payloads: dict[str, dict[str, object]] = {}
    for relative, tool in expected_artifacts.items():
        artifact = (project / PurePosixPath(relative)).resolve()
        entry = ledger_by_path.get(relative)
        if (
            not is_within(artifact, project.resolve())
            or not artifact.is_file()
            or entry is None
            or file_sha256(artifact)[1] != entry.get("sha256")
        ):
            failures.append(f"Gate artifact is missing or drifted: {relative}.")
            continue
        if (
            relative in expected_frame_bytes
            and entry.get("bytes") != expected_frame_bytes[relative]
        ):
            failures.append(f"Gate interaction-frame byte count drifted: {relative}.")
        if tool is None:
            continue
        try:
            payload = json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            failures.append(f"Gate artifact {relative} is unreadable: {exc}")
            continue
        producer = scripts / tool
        schema = packaged_script_schema_version(producer)
        if (
            not isinstance(payload, dict)
            or payload.get("tool") != tool
            or payload.get("schema_version") != schema
            or payload.get("producer_script_sha256") != file_sha256(producer)[1]
            or payload.get("build_id") != build_id
            or payload.get("run_id") != run_id
            or payload.get("manifest_id") != manifest.get("manifest_id")
            or payload.get("manifest_sha256") != manifest_sha
            or not (payload.get("pass") is True or payload.get("ok") is True)
        ):
            failures.append(f"Gate artifact {relative} has invalid runtime/build/run/manifest identity.")
            continue
        runtime_failures = packaged_runtime_record_failures(
            payload, tool=tool, require_pass=True
        )
        if runtime_failures:
            failures.extend(
                f"Gate artifact {relative}: {failure}"
                for failure in runtime_failures
            )
            continue
        artifact_routes = active_routes
        artifact_viewports = viewports
        if tool == "extract_reference_styles.mjs":
            route_key = str(payload.get("route_key") or "")
            viewport_name = str(payload.get("viewport_name") or payload.get("viewport") or "")
            artifact_routes = [route for route in active_routes if route.get("key") == route_key]
            artifact_viewports = [viewport for viewport in viewports if viewport.get("name") == viewport_name]
            if len(artifact_routes) != 1 or len(artifact_viewports) != 1:
                failures.append(f"Gate extractor artifact {relative} has wrong route/profile identity.")
                continue
        identity_failures = served_content_identity_failures(
            payload.get("served_content_identity"),
            expected_routes=artifact_routes,
            expected_viewports=artifact_viewports,
        )
        failures.extend(f"Gate artifact {relative}: {failure}" for failure in identity_failures)
        if tool == "scan_build_components.mjs":
            census_failures = census_runtime_failures(
                payload,
                expected_routes=active_routes,
                expected_viewports=viewports,
                first_screen=phase == "first-screen",
                record_path=artifact,
                project=project,
            )
            failures.extend(
                f"Gate artifact {relative}: {failure}"
                for failure in census_failures
            )
        if tool == "compare_mechanisms.mjs":
            mechanism_failures = mechanism_interaction_transfer_failures(
                payload,
                project=project,
                expected_routes=active_routes,
                expected_viewports=viewports,
                first_screen=phase == "first-screen",
                record_path=artifact,
            )
            failures.extend(
                f"Gate artifact {relative}: {failure}"
                for failure in mechanism_failures
            )
        identity = payload.get("served_content_identity")
        if tool != "extract_reference_styles.mjs" and isinstance(identity, dict):
            aggregate_served_hashes.add(str(identity.get("sha256")))
        payloads[tool] = payload
    gate_served = gate.get("served_content_identity")
    gate_served_sha = gate_served.get("sha256") if isinstance(gate_served, dict) else None
    if len(aggregate_served_hashes) != 1 or gate_served_sha not in aggregate_served_hashes:
        failures.append("Gate aggregate artifacts do not agree on one served-content identity.")

    census_path = f"{artifact_root}/{prefix}component-census.json"
    structure_payload = payloads.get("compare_structure.mjs")
    if isinstance(structure_payload, dict) and structure_payload.get("census_sha256") != ledger_by_path.get(census_path, {}).get("sha256"):
        failures.append("Structure evidence does not bind the gate census bytes.")
    signature_payload = payloads.get("check_signature_transfer.mjs")
    if isinstance(signature_payload, dict):
        expected_hashes = {
            "mechanism_diff": ledger_by_path.get(f"{artifact_root}/{prefix}mechanism-diff.json", {}).get("sha256"),
            "structure_diff": ledger_by_path.get(f"{artifact_root}/{prefix}structure-diff.json", {}).get("sha256"),
            "style_provenance": ledger_by_path.get(f"{artifact_root}/{prefix}style-provenance.json", {}).get("sha256"),
            "census": ledger_by_path.get(census_path, {}).get("sha256"),
        }
        if signature_payload.get("evidence_hashes") != expected_hashes:
            failures.append("Signature-transfer evidence does not bind the gate direct artifacts.")
    return failures


def final_prebuild_predecessor_failures(
    gate: dict[str, object],
    *,
    project: Path,
    manifest: dict[str, object],
) -> list[str]:
    failures: list[str] = []
    binding = gate.get("prebuild_authorization")
    if not isinstance(binding, dict) or set(binding) != {
        "path", "sha256", "authorization_id", "proof_build_id",
        "proof_tree_sha256", "authorized_at",
    }:
        return ["Final gate has an invalid first-screen predecessor binding."]
    relative = binding.get("path")
    if not isinstance(relative, str):
        return ["Final gate predecessor path is invalid."]
    authorization_path = (project / PurePosixPath(relative)).resolve()
    chain_failures, authorization, digest = load_prebuild_authorization(
        project, authorization_path
    )
    failures.extend(chain_failures)
    if not isinstance(authorization, dict):
        return failures
    if digest != binding.get("sha256"):
        failures.append("Final gate predecessor SHA-256 differs from the authorization file.")
    for field in (
        "authorization_id", "proof_build_id", "proof_tree_sha256", "authorized_at"
    ):
        if binding.get(field) != authorization.get(field):
            failures.append(f"Final gate predecessor {field} does not match its authorization.")
    manifest_path = project / ".design-dna" / "route-manifest.json"
    if (
        authorization.get("manifest_id") != manifest.get("manifest_id")
        or authorization.get("manifest_sha256") != file_sha256(manifest_path)[1]
    ):
        failures.append("Final gate predecessor belongs to another route manifest.")
    dossier = project / ".design-dna" / "reference-dossier.md"
    if not dossier.is_file() or authorization.get("dossier_core_sha256") != dossier_core_sha256(dossier):
        failures.append("Final gate predecessor does not bind the current normalized dossier core.")
    if (
        authorization.get("proof_build_id") == gate.get("build_id")
        or authorization.get("proof_tree_sha256") == gate.get("build_tree_sha256_before")
    ):
        failures.append("Final build/tree identity must differ from its first-screen predecessor.")
    try:
        authorized_at = datetime.fromisoformat(
            str(authorization.get("authorized_at", "")).replace("Z", "+00:00")
        )
        final_at = datetime.fromisoformat(
            str(gate.get("checked_at", "")).replace("Z", "+00:00")
        )
        if authorized_at >= final_at:
            failures.append("First-screen authorization does not precede the final gate.")
    except ValueError:
        failures.append("Gate chronology timestamps are invalid.")
    first_binding = authorization.get("first_screen_gate")
    first_path = (
        project / PurePosixPath(str(first_binding.get("path") or ""))
    ).resolve() if isinstance(first_binding, dict) else Path()
    if (
        not isinstance(first_binding, dict)
        or not is_within(first_path, project.resolve())
        or not first_path.is_file()
        or first_binding.get("sha256") != file_sha256(first_path)[1]
    ):
        failures.append("First-screen gate bytes do not match the authorization predecessor.")
        return failures
    try:
        first_gate = json.loads(first_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        failures.append(f"First-screen predecessor is unreadable: {exc}")
        return failures
    if not isinstance(first_gate, dict):
        failures.append("First-screen predecessor must be an object.")
        return failures
    failures.extend(
        "First-screen predecessor: " + failure
        for failure in gate_runtime_evidence_failures(
            first_gate,
            project=project,
            manifest=manifest,
            phase="first-screen",
            require_current_tree=False,
        )
    )
    if (
        first_gate.get("authorization_id") != authorization.get("authorization_id")
        or first_gate.get("build_id") != authorization.get("proof_build_id")
        or first_gate.get("build_tree_sha256_before") != authorization.get("proof_tree_sha256")
        or first_gate.get("dossier_core_sha256") != authorization.get("dossier_core_sha256")
    ):
        failures.append("First-screen predecessor fields differ from the authorization.")
    return failures


def final_gate_failures(
    section: str,
    *,
    project: Path,
    record_path: Path,
    expected_build_id: str,
) -> list[str]:
    """Bind readiness to the exact passing all-route, all-viewport gate."""

    failures: list[str] = []
    manifest_cell = (markdown_label_value(section, "Route manifest") or "").strip()
    manifest_failures, manifest, manifest_path = bound_route_manifest_failures(
        manifest_cell,
        project=project,
        record_path=record_path,
    )
    failures.extend(manifest_failures)

    gate_cell = (markdown_label_value(section, "Gate result") or "").strip()
    gate_path, gate_binding_failures = bound_artifact(
        gate_cell,
        project=project,
        record_path=record_path,
        label="Reference-led direction closure Gate result",
    )
    failures.extend(gate_binding_failures)
    if gate_path is None:
        return failures
    expected_gate_path = (project / ".design-dna" / "evidence" / "gate.json").resolve()
    if gate_path.resolve() != expected_gate_path:
        failures.append(
            "Reference-led direction closure Gate result must bind "
            ".design-dna/evidence/gate.json."
        )
        return failures
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [*failures, f"Gate result is not readable JSON: {exc}"]
    if not isinstance(gate, dict):
        return [*failures, "Gate result must be an object."]
    if gate.get("tool") != "gate.py" or gate.get("schema_version") != 2:
        failures.append("Gate result must come from gate.py schema_version 2.")
    gate_script = Path(__file__).resolve().parent / "gate.py"
    if gate.get("producer_script_sha256") != file_sha256(gate_script)[1]:
        failures.append("Gate result does not bind the current packaged gate.py bytes.")
    expected_runtime = {
        path.name: file_sha256(path)[1]
        for path in [
            gate_script,
            Path(__file__).resolve(),
            *sorted(gate_script.parent.glob("*.mjs"), key=lambda item: item.name),
        ]
    }
    if gate.get("runtime_identity") != expected_runtime:
        failures.append("Gate result runtime identity differs from the packaged checks.")
    if gate.get("phase") != "final" or gate.get("route_key") is not None:
        failures.append("Final readiness requires a `--phase final` gate result.")
    if gate.get("pass") is not True or gate.get("build_stable") is not True:
        failures.append(
            "Gate result did not pass on one byte-stable build: "
            + str(gate.get("verdict") or "no passing verdict")
        )
    if gate.get("build_id") != expected_build_id:
        failures.append(
            "Gate result build_id does not match visual-review.md's canonical build."
        )
    try:
        gate_project = Path(str(gate.get("project") or "")).resolve()
    except (OSError, ValueError):
        gate_project = Path()
    if gate_project != project.resolve():
        failures.append("Gate result belongs to a different project root.")
    if manifest_path is not None:
        if gate.get("route_manifest_sha256") != file_sha256(manifest_path)[1]:
            failures.append("Gate result does not bind the current route manifest bytes.")
    if isinstance(manifest, dict):
        if (
            gate.get("routes") != manifest.get("routes")
            or gate.get("planned_routes") != manifest.get("routes")
        ):
            failures.append("Gate result route set differs from the route manifest.")
        if gate.get("viewports_checked") != manifest.get("viewports"):
            failures.append("Gate result viewport set differs from the route manifest.")
        expected_cells = len(manifest.get("routes", [])) * len(
            manifest.get("viewports", [])
        )
        coverage = gate.get("coverage_matrix")
        if not isinstance(coverage, list) or len(coverage) != expected_cells:
            failures.append(
                "Gate result does not cover every route/viewport cell in the manifest."
            )
    dossier_path = project / ".design-dna" / "reference-dossier.md"
    if dossier_path.is_file() and gate.get("dossier_sha256") != file_sha256(dossier_path)[1]:
        failures.append("Gate result does not bind the current completed dossier bytes.")
    if isinstance(manifest, dict):
        failures.extend(
            gate_runtime_evidence_failures(
                gate,
                project=project,
                manifest=manifest,
                phase="final",
                require_current_tree=True,
            )
        )
        failures.extend(
            final_prebuild_predecessor_failures(
                gate, project=project, manifest=manifest
            )
        )
    steps = gate.get("steps")
    if (
        not isinstance(steps, list)
        or not steps
        or any(not isinstance(step, dict) or step.get("pass") is not True for step in steps)
    ):
        failures.append("Gate result contains a missing or failed packaged check.")
    else:
        step_names = {str(step.get("name")) for step in steps}
        required_steps = {
            "route-manifest", "census", "provenance", "structure", "mechanisms",
            "signature-transfer", "dossier", "dossier-core", "build-stability",
            "runtime-stability", "served-content-consensus", "prebuild-authorization",
            "visible-decision-source-manifest",
        }
        if (
            not required_steps.issubset(step_names)
            or not any(name.startswith("extract:") for name in step_names)
        ):
            failures.append(
                "Gate result omits a required route, viewport, provenance, "
                "structure, mechanism, signature, census, or dossier check."
            )
    if not str(gate.get("verdict") or "").startswith("GATE PASS:"):
        failures.append("Gate result has no canonical GATE PASS verdict line.")

    evidence = gate.get("evidence_hashes")
    if not isinstance(evidence, list) or not evidence:
        failures.append("Gate result carries no evidence hash ledger.")
    else:
        seen: set[str] = set()
        for index, entry in enumerate(evidence, start=1):
            if not isinstance(entry, dict):
                failures.append(f"Gate evidence entry {index} is not an object.")
                continue
            relative = entry.get("path")
            digest = entry.get("sha256")
            if (
                not isinstance(relative, str)
                or not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            ):
                failures.append(f"Gate evidence entry {index} has an invalid binding.")
                continue
            if relative in {
                ".design-dna/route-manifest.json",
                ".design-dna/visible-decision-sources.json",
            }:
                canonical_path = project / PurePosixPath(relative)
                if not canonical_path.is_file() or file_sha256(canonical_path)[1] != digest:
                    failures.append(f"Gate evidence ledger canonical binding drifted: {relative}.")
                continue
            if not relative.startswith(".design-dna/evidence/"):
                failures.append(f"Gate evidence entry {index} is outside the evidence root.")
                continue
            if relative in seen:
                # Repeated route/viewport metadata may point at one aggregate
                # file only when its bytes are identical; a second conflicting
                # digest is refused below by the file comparison.
                continue
            seen.add(relative)
            evidence_path = (project / PurePosixPath(relative)).resolve()
            evidence_root = (project / ".design-dna" / "evidence").resolve()
            if evidence_root not in evidence_path.parents:
                failures.append(f"Gate evidence entry {index} escapes the evidence root.")
            elif not evidence_path.is_file() or file_sha256(evidence_path)[1] != digest:
                failures.append(
                    f"Gate evidence entry {index} is missing or has changed: {relative}."
                )
    return failures


def first_screen_gate_failures(
    dossier_body: str,
    *,
    project: Path,
    record_path: Path,
) -> list[str]:
    """Prove source fidelity was checked before broad implementation."""

    sections = markdown_sections(dossier_body)
    route_section = sections.get("Route manifest", "")
    manifest_cell = (markdown_label_value(route_section, "Route manifest") or "").strip()
    proof_identity = semicolon_fields(
        (markdown_label_value(
            route_section, "First-screen proof build ID and primary route key"
        ) or "").strip()
    )
    build_id = proof_identity.get("build_id", "")
    expected_route_key = proof_identity.get("route_key", "")
    manifest_failures, manifest, manifest_path = bound_route_manifest_failures(
        manifest_cell,
        project=project,
        record_path=record_path,
    )
    failures = list(manifest_failures)
    gate_cell = (
        markdown_label_value(route_section, "First-screen gate") or ""
    ).strip()
    gate_path, binding_failures = bound_artifact(
        gate_cell,
        project=project,
        record_path=record_path,
        label="Reference dossier First-screen gate",
    )
    failures.extend(binding_failures)
    if gate_path is None:
        return failures
    expected_path = (
        project / ".design-dna" / "evidence" / "first-screen-gate.json"
    ).resolve()
    if gate_path.resolve() != expected_path:
        failures.append(
            "Reference dossier First-screen gate must bind "
            ".design-dna/evidence/first-screen-gate.json."
        )
        return failures
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [*failures, f"First-screen gate is not readable JSON: {exc}"]
    if not isinstance(gate, dict):
        return [*failures, "First-screen gate must contain an object."]
    gate_script = Path(__file__).resolve().parent / "gate.py"
    if (
        gate.get("tool") != "gate.py"
        or gate.get("schema_version") != 2
        or gate.get("producer_script_sha256") != file_sha256(gate_script)[1]
    ):
        failures.append(
            "First-screen gate does not bind the current packaged gate.py identity."
        )
    expected_runtime = {
        path.name: file_sha256(path)[1]
        for path in [
            gate_script,
            Path(__file__).resolve(),
            *sorted(gate_script.parent.glob("*.mjs"), key=lambda item: item.name),
        ]
    }
    if gate.get("runtime_identity") != expected_runtime:
        failures.append(
            "First-screen gate runtime identity differs from the current packaged checks."
        )
    if gate.get("phase") != "first-screen" or not gate.get("route_key"):
        failures.append(
            "First-screen gate must be a `--phase first-screen --route-key` run."
        )
    if gate.get("route_key") != expected_route_key:
        failures.append("First-screen gate route_key differs from the dossier proof identity.")
    if gate.get("pass") is not True or gate.get("build_stable") is not True:
        failures.append(
            "First-screen source-fidelity gate did not pass on one byte-stable proof build."
        )
    if gate.get("build_id") != build_id:
        failures.append("First-screen gate build_id differs from the bound route manifest.")
    if manifest_path is not None and gate.get("route_manifest_sha256") != file_sha256(manifest_path)[1]:
        failures.append("First-screen gate does not bind the current planned route manifest.")
    if isinstance(manifest, dict):
        if gate.get("planned_routes") != manifest.get("routes"):
            failures.append("First-screen gate did not bind the full planned route set.")
        active_routes = gate.get("routes")
        route_key = gate.get("route_key")
        if (
            not isinstance(active_routes, list)
            or len(active_routes) != 1
            or not isinstance(active_routes[0], dict)
            or active_routes[0].get("key") != route_key
        ):
            failures.append("First-screen gate must inspect exactly its declared route key.")
        viewports = manifest.get("viewports")
        coverage = gate.get("coverage_matrix")
        if (
            not isinstance(viewports, list)
            or not isinstance(coverage, list)
            or len(coverage) != len(viewports)
        ):
            failures.append(
                "First-screen gate must inspect the selected route at every manifest viewport."
            )
    required_steps = {
        "route-manifest", "census", "provenance", "structure", "mechanisms",
        "signature-transfer", "dossier-binding", "dossier-core", "build-stability",
        "runtime-stability", "served-content-consensus", "authorization-chain",
        "route-manifest-snapshot", "dossier-snapshot",
        "visible-decision-source-manifest", "visible-decision-source-snapshot",
    }
    steps = gate.get("steps")
    step_names = {
        str(step.get("name"))
        for step in steps or []
        if isinstance(step, dict)
    }
    if (
        not isinstance(steps, list)
        or any(not isinstance(step, dict) or step.get("pass") is not True for step in steps)
        or not required_steps.issubset(step_names)
        or not any(name.startswith("extract:") for name in step_names)
    ):
        failures.append(
            "First-screen gate is missing a passing provenance, structure, "
            "mechanism, signature, census, or viewport extraction step."
        )
    if not str(gate.get("verdict") or "").startswith("GATE PASS: first-screen"):
        failures.append("First-screen gate has no canonical first-screen PASS verdict.")
    if isinstance(manifest, dict):
        failures.extend(
            gate_runtime_evidence_failures(
                gate,
                project=project,
                manifest=manifest,
                phase="first-screen",
                require_current_tree=True,
            )
        )
    if gate.get("dossier_core_sha256") != dossier_core_sha256(record_path):
        failures.append("First-screen gate does not bind the current normalized dossier core.")
    authorization_id = gate.get("authorization_id")
    authorization_relative = gate.get("authorization_path")
    current_manifest_id = manifest.get("manifest_id") if isinstance(manifest, dict) else None
    if (
        not isinstance(authorization_id, str)
        or re.fullmatch(r"[0-9a-f]{32}", authorization_id) is None
        or not isinstance(authorization_relative, str)
    ):
        failures.append("First-screen gate has no generated authorization identity/path.")
    else:
        authorization_path = (project / PurePosixPath(authorization_relative)).resolve()
        chain_failures, authorization, _authorization_sha = load_prebuild_authorization(
            project, authorization_path
        )
        failures.extend(chain_failures)
        if isinstance(authorization, dict):
            gate_binding = authorization.get("first_screen_gate")
            if (
                authorization.get("authorization_id") != authorization_id
                or authorization.get("proof_build_id") != gate.get("build_id")
                or authorization.get("proof_tree_sha256") != gate.get("build_tree_sha256_before")
                or authorization.get("manifest_id") != current_manifest_id
                or authorization.get("manifest_sha256") != gate.get("route_manifest_sha256")
                or authorization.get("dossier_core_sha256") != gate.get("dossier_core_sha256")
                or not isinstance(gate_binding, dict)
                or gate_binding.get("sha256") != file_sha256(gate_path)[1]
            ):
                failures.append("First-screen authorization does not bind the exact gate/project/dossier/manifest proof.")
    return failures


def combination_failures(value: str, label: str) -> list[str]:
    """The combination names references, not ideas.

    The producer must say which reference supplies which part and why no
    single one of them is this build. If it reads as something the producer
    thought of, it is the producer's design and it does not ship.
    """
    problems: list[str] = []
    if COMBINATION_INVENTION_WORDS.search(value):
        problems.append(
            f"{label} describes something the producer invented. The build is a "
            "combination of what the selected references already do; say which "
            "reference supplies which part. A build's distinctiveness comes "
            "from the combination, never from a new idea the producer had."
        )
    if len(COMBINATION_SOURCE_PATTERN.findall(value)) < 2:
        problems.append(
            f"{label} must name at least two selected references and what each "
            "one supplies, e.g. `strong-2 supplies the held screen, strong-5 "
            "the index`."
        )
    return problems


def reference_led_closure_label_failures(section: str) -> list[str]:
    """Require the closure to say what the render showed, including the
    combination the build is made of, and to declare one disposition."""

    failures: list[str] = []
    for label in REFERENCE_LED_CLOSURE_LABELS:
        value = markdown_label_value(section, label)
        if value is None or not non_placeholder(value) or len(value.strip()) < 24:
            failures.append(
                "Reference-led direction closure needs a substantive "
                f"{label!r} value"
            )
    disposition = (
        markdown_label_value(section, "Reference-led direction disposition") or ""
    ).strip().casefold()
    if disposition not in REFERENCE_LED_CLOSURE_DISPOSITIONS:
        failures.append(
            "Reference-led direction disposition must be keep, revise, reopen "
            "direction, reject, or blocked"
        )
    return failures


def showcase_taste_calibration_failures(
    body: str,
    *,
    project: Path | None,
    record_path: Path | None,
    required_assurance_profiles: tuple[str, ...] | set[str] | None,
) -> list[str]:
    """Validate calibration as evidence, without turning it into a taste score."""

    failures: list[str] = []
    sections = markdown_sections(body)
    lifecycle = (markdown_label_value(body, "Current status") or "").strip().casefold()
    if lifecycle not in {"draft", "proof-ready", "reviewed", "reopened", "blocked"}:
        failures.append(
            "Taste calibration Current status must be draft, proof-ready, "
            "reviewed, reopened, or blocked"
        )
    for label in (
        "Activation basis and applicable scope",
        "Candidate/build under review",
        "Reviewer relationship and date",
        "Direct reviewable artifacts currently bound",
        "Selected reference ranks and mapped organizing relationships being tested",
        "Missing evidence, explicit inability, and next decision",
    ):
        if required_label_value("taste-calibration", body, label) is None:
            failures.append(f"Taste calibration {label!r} is missing or still scaffold text")

    disposition = (markdown_label_value(body, "Current disposition") or "").strip().casefold()
    if not any(
        disposition == status or disposition.startswith(status + ";")
        for status in {"keep", "revise", "reopen direction", "reject", "blocked"}
    ):
        failures.append(
            "Taste calibration Current disposition must be keep, revise, "
            "reopen direction, reject, or blocked"
        )

    profiles = set(required_assurance_profiles or ())
    if "showcase" not in profiles:
        return failures

    reference_headers, reference_rows = markdown_first_table(
        sections.get("Reference dossier", "")
    )
    expected_reference_headers = (
        "Selected rank, source, and retrieval date",
        "Exact observation path and SHA-256",
        "Brief-fit viewer role",
        "Measured transferable relationship",
        "Non-copying boundary",
    )
    if reference_headers != expected_reference_headers or not reference_rows:
        failures.append(
            "Showcase taste calibration needs at least one retrieval-dated "
            "reference dossier row"
        )
    else:
        for row_number, row in enumerate(reference_rows, start=1):
            if len(row) != len(expected_reference_headers) or any(
                not non_placeholder(cell) for cell in row
            ):
                failures.append(
                    f"Taste calibration reference dossier row {row_number} is incomplete"
                )
                continue
            dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", row[0])
            if not dates:
                failures.append(
                    f"Taste calibration reference dossier row {row_number} "
                    "must include a retrieval date (YYYY-MM-DD)"
                )
            else:
                try:
                    if date.fromisoformat(dates[-1]) > datetime.now(timezone.utc).date():
                        failures.append(
                            f"Taste calibration reference dossier row {row_number} "
                            "retrieval date may not be in the future"
                        )
                except ValueError:
                    failures.append(
                        f"Taste calibration reference dossier row {row_number} "
                        "has an invalid retrieval date"
                    )

    for label in (
        "Selected-direction proof evidence",
        "Counter-direction proof evidence",
    ):
        value = markdown_label_value(body, label) or ""
        if project is None or record_path is None:
            if ARTIFACT_BINDING_PATTERN.fullmatch(value.strip()) is None:
                failures.append(
                    f"Showcase taste calibration {label} must bind a "
                    "project-relative direct-reviewable artifact plus SHA-256"
                )
            continue
        _artifact, artifact_failures = bound_artifact(
            value,
            project=project,
            record_path=record_path,
            label=f"Showcase taste calibration {label}",
        )
        failures.extend(artifact_failures)

    recurrence = (
        markdown_label_value(body, "Recurrence-risk disposition") or ""
    ).strip()
    recurrence_normalized = recurrence.casefold().replace(
        "not applicable",
        "not-applicable",
    )
    recurrence_status = next(
        (
            status
            for status in ("active", "not-applicable", "blocked")
            if recurrence_normalized == status
            or recurrence_normalized.startswith(status + ";")
            or recurrence_normalized.startswith(status + ":")
        ),
        "",
    )
    if not recurrence_status:
        failures.append(
            "Showcase taste calibration must explicitly disposition recurrence "
            "risk as active, not-applicable, or blocked"
        )
        return failures
    recurrence_fields = semicolon_fields(recurrence)
    if recurrence_status in {"not-applicable", "blocked"}:
        reason = recurrence_fields.get("reason", "")
        if len(reason.strip()) < 24:
            failures.append(
                "Showcase taste calibration recurrence risk marked "
                f"{recurrence_status} needs a substantive reason="
            )
        return failures

    contrast_record = (
        markdown_label_value(
            body,
            "Authoritative Project Contrast record path and current status, if active",
        )
        or ""
    )
    if ".design-dna/project-contrast.json" not in contrast_record.replace("\\", "/"):
        failures.append(
            "Active Showcase recurrence risk requires the authoritative "
            ".design-dna/project-contrast.json record path"
        )
    if project is not None:
        state_path = project / ".design-dna" / "state.json"
        contrast_path = project / ".design-dna" / "project-contrast.json"
        if not contrast_path.is_file():
            failures.append(
                "Active Showcase recurrence risk requires the selected "
                "Project Contrast record file"
            )
        try:
            state = read_json(state_path)
            records = state.get("records") if isinstance(state, dict) else None
            if not isinstance(records, list) or "project-contrast" not in records:
                failures.append(
                    "Active Showcase recurrence risk requires Project Contrast "
                    "to be selected in state.json"
                )
        except StateError:
            failures.append(
                "Active Showcase recurrence risk cannot verify Project Contrast "
                "without a readable project state"
            )
    return failures


def rendered_review_body_failures(
    body: str,
    *,
    project: Path,
    record_path: Path,
) -> list[str]:
    failures: list[str] = []
    report_record = (
        markdown_label_value(
            body,
            "Rendered-review report path, hash, contract, and execution result",
        )
        or ""
    )
    report_value = report_record.split(";", 1)[0].strip()
    report_path, report_failures = bound_artifact(
        report_value,
        project=project,
        record_path=record_path,
        label="Rendered-review report binding",
    )
    failures.extend(report_failures)
    contact_value = (
        markdown_label_value(
            body,
            "Coverage contact sheet or artifact index",
        )
        or ""
    )
    contact_path, contact_failures = bound_artifact(
        contact_value,
        project=project,
        record_path=record_path,
        label="Coverage contact sheet or artifact index",
    )
    failures.extend(contact_failures)
    if report_path is None or report_failures:
        return failures
    if report_path.name != "render-review.json":
        failures.append(
            "Rendered-review report must bind render-review.json"
        )
        return failures
    try:
        report = read_json(report_path)
    except StateError as exc:
        failures.append(f"Rendered-review report is invalid JSON: {exc}")
        return failures
    if not isinstance(report, dict):
        failures.append("Rendered-review report must contain an object")
        return failures
    tool = report.get("tool")
    build = report.get("build")
    snapshot = report.get("source_snapshot")
    contract = report.get("capture_contract")
    routes = report.get("routes")
    captures = report.get("captures")
    artifacts = report.get("artifacts")
    if (
        report.get("schema_version") != 3
        or tool != {
            "name": "design-dna-rendered-review",
            "version": "3.0.0",
            "report_schema": "render-review.schema.json",
        }
    ):
        failures.append(
            "Rendered-review report must use the packaged schema-3, tool-3.0.0 "
            "identity"
        )
    if (
        report.get("execution_ok") is not True
        or report.get("review_required") is not True
        or report.get("automatic_visual_quality_pass") is not False
    ):
        failures.append(
            "Rendered-review report must record successful execution while "
            "retaining manual review"
        )
    build_id = (
        build.get("id")
        if isinstance(build, dict)
        else None
    )
    # The proportional visual-review template deliberately uses the plainer
    # ``Build or artifact ID`` label.  Older migrated records used the longer
    # label below; accept it as a compatibility fallback rather than making a
    # valid new template impossible to close.
    record_build_id = (
        markdown_label_value(body, "Build or artifact ID")
        or markdown_label_value(body, "Build, commit, or artifact ID")
    )
    if not build_id or build_id != record_build_id:
        failures.append(
            "Rendered-review build ID must match the visual-review build ID"
        )
    source_sha = None
    if isinstance(snapshot, dict):
        manifest = snapshot.get("manifest")
        if isinstance(manifest, dict):
            source_sha = manifest.get("manifest_sha256")
    if not isinstance(source_sha, str) or not re.fullmatch(
        r"[0-9a-f]{64}",
        source_sha,
    ):
        failures.append(
            "Rendered-review report must bind a local source-snapshot "
            "manifest SHA-256"
        )
    if (
        not isinstance(contract, dict)
        or contract.get("contract_mode")
        not in {"deterministic-default-v1", "capture-manifest-v1"}
        or not isinstance(contract.get("profiles"), list)
        or not contract.get("profiles")
        or not isinstance(contract.get("scenarios"), list)
        or not contract.get("scenarios")
    ):
        failures.append(
            "Rendered-review report must identify non-empty profiles and "
            "scenarios"
        )
    if not isinstance(routes, list) or not routes:
        failures.append("Rendered-review report must contain reviewed routes")
    if not isinstance(captures, list) or not captures:
        failures.append(
            "Rendered-review report must contain reviewed captures"
        )
    report_contact = (
        artifacts.get("contact_sheet")
        if isinstance(artifacts, dict)
        else None
    )
    if isinstance(report_contact, dict) and contact_path is not None:
        report_contact_path = report_path.parent / str(
            report_contact.get("path", "")
        )
        try:
            report_contact_path = lexical_absolute(report_contact_path)
        except StateError:
            report_contact_path = Path("")
        if report_contact_path != contact_path:
            failures.append(
                "Coverage contact-sheet binding must match the rendered "
                "review report"
            )
        if report_contact.get("sha256") != hashlib.sha256(
            contact_path.read_bytes()
        ).hexdigest():
            failures.append(
                "Rendered-review contact-sheet SHA-256 is inconsistent"
            )
    else:
        failures.append(
            "Rendered-review report must bind its contact-sheet artifact"
        )

    contract_value = report_record.casefold()
    contract_tokens = [
        str(build_id or "").casefold(),
        str(source_sha or "").casefold(),
        str(
            contract.get("contract_mode", "")
            if isinstance(contract, dict)
            else ""
        ).casefold(),
        "execution_ok=true",
    ]
    if any(token not in contract_value for token in contract_tokens):
        failures.append(
            "Rendered-review binding must name the exact build ID, "
            "source-snapshot SHA-256, capture mode, and execution_ok=true"
        )
    return failures


def comparison_decision(value: str) -> tuple[str, str] | None:
    normalized = value.strip().replace("`", "")
    folded = normalized.casefold().replace("not-performed", "not performed")
    for status in COMPARISON_DECISION_STATUSES:
        if not folded.startswith(status):
            continue
        boundary = folded[len(status):len(status) + 1]
        if boundary and boundary not in {" ", ":", ";", ",", ".", "-", "—"}:
            continue
        rationale = normalized[len(status):].lstrip(" \t:;,.—-")
        return status, rationale
    return None


def render_comparison_body_failures(
    body: str,
    *,
    project: Path,
    record_path: Path,
) -> list[str]:
    """Validate an optional, reviewer-decided cross-build comparison.

    This enforces the project-state-relevant subset of
    maintainer/schemas/render-comparison.schema.json with the standard
    library so the installed skill retains its dependency-free runtime.
    The immutable machine report remains evidence, never visual acceptance.
    """

    failures: list[str] = []
    comparison_record = markdown_label_value(
        body,
        (
            "Cross-build comparison identity, compatibility, changed captures, "
            "reviewer, and result, or `not performed`"
        ),
    )
    decision_value = markdown_label_value(
        body,
        "Cross-build decision",
    )
    if comparison_record is None and decision_value is None:
        return failures

    report_declaration = (comparison_record or "").strip().replace("`", "")
    report_not_performed = (
        report_declaration.casefold().replace("-", " ").startswith(
            "not performed"
        )
    )
    parsed_decision = comparison_decision(decision_value or "")
    if parsed_decision is None:
        failures.append(
            "Cross-build comparison decision must begin with accept "
            "candidate, revise candidate, reject candidate, insufficient "
            "evidence, or not performed"
        )
        return failures
    decision_status, decision_rationale = parsed_decision
    if not non_placeholder(decision_rationale) or len(decision_rationale) < 12:
        failures.append(
            "Cross-build comparison decision must include a substantive "
            "reviewer rationale after its status"
        )

    if report_not_performed:
        if decision_status != "not performed":
            failures.append(
                "A not-performed cross-build comparison report declaration "
                "requires a not performed comparison decision"
            )
        return failures
    if decision_status == "not performed":
        failures.append(
            "A declared cross-build comparison report requires an accept, "
            "revise, reject, or insufficient-evidence reviewer decision"
        )

    comparison_fields = semicolon_fields(report_declaration)
    report_value = comparison_fields.get("report", "")
    if not report_value and ";" in report_declaration:
        first_segment = report_declaration.split(";", 1)[0].strip()
        if "sha256:" in first_segment.casefold():
            report_value = first_segment

    report_path, report_failures = bound_artifact(
        report_value,
        project=project,
        record_path=record_path,
        label="Cross-build comparison report binding",
    )
    failures.extend(report_failures)
    if report_path is None or report_failures:
        return failures
    if report_path.name != "render-comparison.json":
        failures.append(
            "Cross-build comparison report must bind render-comparison.json"
        )
        return failures
    try:
        report_size = report_path.stat().st_size
    except OSError as exc:
        failures.append(f"Cross-build comparison report is unreadable: {exc}")
        return failures
    if report_size < 1 or report_size > COMPARISON_REPORT_MAX_BYTES:
        failures.append(
            "Cross-build comparison report must contain 1 byte through "
            f"{COMPARISON_REPORT_MAX_BYTES} bytes"
        )
        return failures
    try:
        report = read_json(report_path)
    except StateError as exc:
        failures.append(
            f"Cross-build comparison report is invalid JSON: {exc}"
        )
        return failures
    if not isinstance(report, dict):
        failures.append("Cross-build comparison report must contain an object")
        return failures

    required_top_level = {
        "schema_version",
        "tool",
        "producer_script_sha256",
        "runtime_identity",
        "comparison_id",
        "created_at",
        "output_identity",
        "execution_ok",
        "review_required",
        "automatic_visual_approval",
        "decision_status",
        "execution",
        "privacy",
        "mask_policy",
        "inputs",
        "compatibility",
        "baseline_freshness",
        "comparisons",
        "summary",
        "artifacts",
        "manual_review",
    }
    if set(report) != required_top_level:
        failures.append(
            "Cross-build comparison report must use the exact packaged "
            "schema-2 top-level shape"
        )

    tool = report.get("tool")
    if (
        report.get("schema_version") != 2
        or not isinstance(tool, dict)
        or tool != {
            "name": "design-dna-render-comparison",
            "version": "2.0.0",
            "report_schema": "render-comparison.schema.json",
        }
    ):
        failures.append(
            "Cross-build comparison report must use the packaged schema-2 "
            "tool identity"
        )
    compare_script = Path(__file__).resolve().parent / "compare_render_reviews.mjs"
    resolver_script = Path(__file__).resolve().parent / "playwright_resolver.mjs"
    render_schema = Path(__file__).resolve().parents[1] / "schemas" / "render-review.schema.json"
    expected_comparison_runtime = {
        "compare_render_reviews.mjs": file_sha256(compare_script)[1],
        "playwright_resolver.mjs": file_sha256(resolver_script)[1],
        "render-review.schema.json": file_sha256(render_schema)[1],
    }
    if report.get("producer_script_sha256") != expected_comparison_runtime["compare_render_reviews.mjs"]:
        failures.append("Cross-build comparison report does not bind current comparator bytes.")
    if report.get("runtime_identity") != expected_comparison_runtime:
        failures.append("Cross-build comparison report runtime identity is stale.")
    if (
        report.get("execution_ok") is not True
        or report.get("review_required") is not True
        or report.get("automatic_visual_approval") is not False
        or report.get("decision_status")
        != "human-accept-reject-required"
    ):
        failures.append(
            "Cross-build comparison report must record successful execution, "
            "automatic_visual_approval=false, and a required human accept or "
            "reject decision"
        )

    inputs = report.get("inputs")
    baseline = (
        inputs.get("baseline")
        if isinstance(inputs, dict)
        else None
    )
    candidate = (
        inputs.get("candidate")
        if isinstance(inputs, dict)
        else None
    )
    if not isinstance(baseline, dict) or baseline.get("role") != "baseline":
        failures.append(
            "Cross-build comparison report must identify its baseline input"
        )
    if not isinstance(candidate, dict) or candidate.get("role") != "candidate":
        failures.append(
            "Cross-build comparison report must identify its candidate input"
        )
    baseline_build = (
        baseline.get("build")
        if isinstance(baseline, dict)
        else None
    )
    candidate_build = (
        candidate.get("build")
        if isinstance(candidate, dict)
        else None
    )
    baseline_id = (
        baseline_build.get("id")
        if isinstance(baseline_build, dict)
        else None
    )
    candidate_id = (
        candidate_build.get("id")
        if isinstance(candidate_build, dict)
        else None
    )
    if not isinstance(baseline_id, str) or not baseline_id:
        failures.append(
            "Cross-build comparison baseline must have a build ID"
        )
    if not isinstance(candidate_id, str) or not candidate_id:
        failures.append(
            "Cross-build comparison candidate must have a build ID"
        )
    record_build_id = (
        markdown_label_value(body, "Build or artifact ID")
        or markdown_label_value(body, "Build, commit, or artifact ID")
    )
    if candidate_id and candidate_id != record_build_id:
        failures.append(
            "Cross-build comparison candidate build ID must match the "
            "visual-review build ID"
        )

    compatibility = report.get("compatibility")
    summary = report.get("summary")
    comparisons = report.get("comparisons")
    compatibility_status = (
        compatibility.get("status")
        if isinstance(compatibility, dict)
        else None
    )
    compatibility_count = (
        compatibility.get("capture_count")
        if isinstance(compatibility, dict)
        else None
    )
    capture_count = (
        summary.get("capture_count")
        if isinstance(summary, dict)
        else None
    )
    changed_count = (
        summary.get("changed_capture_count")
        if isinstance(summary, dict)
        else None
    )
    if compatibility_status != "compatible":
        failures.append(
            "Cross-build comparison report must record compatible capture "
            "contracts"
        )
    if (
        type(capture_count) is not int
        or capture_count < 1
        or type(changed_count) is not int
        or changed_count < 0
        or changed_count > capture_count
        or compatibility_count != capture_count
        or not isinstance(comparisons, list)
        or len(comparisons) != capture_count
    ):
        failures.append(
            "Cross-build comparison report has inconsistent capture and "
            "changed-capture counts"
        )
    elif any(
        not isinstance(item, dict)
        or item.get("review_status")
        != "human-accept-reject-required"
        for item in comparisons
    ):
        failures.append(
            "Every cross-build capture comparison must retain required human "
            "accept-or-reject review status"
        )

    manual_review = report.get("manual_review")
    required_actions = (
        manual_review.get("required_actions")
        if isinstance(manual_review, dict)
        else None
    )
    limitations = (
        manual_review.get("limitations")
        if isinstance(manual_review, dict)
        else None
    )
    if (
        not isinstance(manual_review, dict)
        or set(manual_review)
        != {"status", "required_actions", "limitations"}
        or manual_review.get("status") != "required"
        or not isinstance(required_actions, list)
        or len(required_actions) < 3
        or any(
            not isinstance(item, str) or len(item.strip()) < 30
            for item in required_actions
        )
        or not isinstance(limitations, list)
        or len(limitations) < 4
        or any(
            not isinstance(item, str) or len(item.strip()) < 40
            for item in limitations
        )
    ):
        failures.append(
            "Cross-build comparison report must preserve the packaged "
            "manual-review actions and limitations contract"
        )

    artifact_rows: list[dict[str, object]] = []
    artifact_paths: dict[tuple[int, str], Path] = {}
    report_artifacts = report.get("artifacts")
    contact = (
        report_artifacts.get("contact_sheet")
        if isinstance(report_artifacts, dict)
        else None
    )
    records_to_validate: list[tuple[int, str, object]] = [(-1, "contact_sheet", contact)]
    if isinstance(comparisons, list):
        for comparison_index, comparison in enumerate(comparisons):
            artifacts = comparison.get("artifacts") if isinstance(comparison, dict) else None
            for role in ("baseline", "actual", "diff"):
                records_to_validate.append(
                    (
                        comparison_index,
                        role,
                        artifacts.get(role) if isinstance(artifacts, dict) else None,
                    )
                )
    for comparison_index, role, artifact_record in records_to_validate:
        if (
            not isinstance(artifact_record, dict)
            or not isinstance(artifact_record.get("path"), str)
            or not isinstance(artifact_record.get("sha256"), str)
            or SHA256_HEX.fullmatch(artifact_record["sha256"]) is None
            or type(artifact_record.get("bytes")) is not int
        ):
            failures.append(f"Cross-build comparison {role} artifact metadata is invalid.")
            continue
        artifact_path = (
            report_path.parent / PurePosixPath(artifact_record["path"])
        ).resolve()
        if not is_within(artifact_path, report_path.parent.resolve()) or not artifact_path.is_file():
            failures.append(f"Cross-build comparison {role} artifact is missing or escapes output.")
            continue
        size, digest = file_sha256(artifact_path)
        if size != artifact_record["bytes"] or digest != artifact_record["sha256"]:
            failures.append(f"Cross-build comparison {role} artifact bytes have drifted.")
            continue
        artifact_rows.append(
            {"path": artifact_record["path"], "bytes": size, "sha256": digest}
        )
        artifact_paths[(comparison_index, role)] = artifact_path
        if role != "contact_sheet":
            try:
                width, height = verify_png_artifact(artifact_path)
            except StateError as exc:
                failures.append(f"Cross-build comparison {role} PNG is invalid: {exc}")
                continue
            if (
                artifact_record.get("pixel_width") != width
                or artifact_record.get("pixel_height") != height
            ):
                failures.append(f"Cross-build comparison {role} PNG dimensions drifted.")

    artifact_rows.sort(key=lambda item: str(item["path"]))
    manifest_record = (
        report_artifacts.get("manifest")
        if isinstance(report_artifacts, dict)
        else None
    )
    expected_artifact_manifest = {
        "algorithm": "sha256-canonical-artifact-list-v1",
        "sha256": canonical_json_sha256(artifact_rows),
        "count": len(artifact_rows),
        "bytes": sum(int(item["bytes"]) for item in artifact_rows),
    }
    if manifest_record != expected_artifact_manifest:
        failures.append("Cross-build comparison artifact manifest does not match output files.")
    if not isinstance(report_artifacts, dict) or report_artifacts.get("comparison_bytes") != expected_artifact_manifest["bytes"]:
        failures.append("Cross-build comparison byte count does not match artifact manifest.")

    recomputed_mismatches = 0
    recomputed_pixels = 0
    if isinstance(comparisons, list):
        for index, comparison in enumerate(comparisons):
            baseline_path = artifact_paths.get((index, "baseline"))
            actual_path = artifact_paths.get((index, "actual"))
            if baseline_path is None or actual_path is None or not isinstance(comparison, dict):
                continue
            try:
                width, height, baseline_rgba = decoded_png_rgba(baseline_path)
                actual_width, actual_height, actual_rgba = decoded_png_rgba(actual_path)
            except StateError as exc:
                failures.append(f"Cross-build comparison decoded PNG failed: {exc}")
                continue
            if (width, height) != (actual_width, actual_height):
                failures.append("Cross-build comparison baseline/actual dimensions differ.")
                continue
            mismatch = sum(
                1
                for pixel in range(width * height)
                if baseline_rgba[pixel * 4:pixel * 4 + 4]
                != actual_rgba[pixel * 4:pixel * 4 + 4]
            )
            metrics = comparison.get("metrics")
            expected_metrics = {
                "algorithm": "exact-decoded-rgba-v1",
                "total_pixels": width * height,
                "mismatch_pixels": mismatch,
                "mismatch_pixel_ratio": mismatch / (width * height),
            }
            if metrics != expected_metrics:
                failures.append(f"Cross-build comparison capture {index + 1} metrics do not match decoded pixels.")
            recomputed_mismatches += mismatch
            recomputed_pixels += width * height
    expected_summary = {
        "capture_count": len(comparisons) if isinstance(comparisons, list) else 0,
        "changed_capture_count": sum(
            1
            for comparison in comparisons or []
            if isinstance(comparison, dict)
            and isinstance(comparison.get("metrics"), dict)
            and comparison["metrics"].get("mismatch_pixels", 0) > 0
        ),
        "total_pixels": recomputed_pixels,
        "mismatch_pixels": recomputed_mismatches,
        "mismatch_pixel_ratio": (
            recomputed_mismatches / recomputed_pixels if recomputed_pixels else 0
        ),
    }
    if summary != expected_summary:
        failures.append("Cross-build comparison summary does not match decoded captures.")

    marker_path = report_path.parent / ".design-dna-render-comparison.json"
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        marker = None
        failures.append(f"Cross-build comparison output marker is missing or invalid: {exc}")
    if isinstance(marker, dict):
        marker_report = marker.get("report")
        if (
            marker.get("schema_version") != 2
            or marker.get("marker_type") != "design-dna-render-comparison-output"
            or marker.get("producer_script_sha256") != expected_comparison_runtime["compare_render_reviews.mjs"]
            or marker.get("runtime_identity") != expected_comparison_runtime
            or marker.get("output_identity") != report.get("output_identity")
            or marker.get("artifact_manifest") != expected_artifact_manifest
            or not isinstance(marker_report, dict)
            or marker_report.get("path") != "render-comparison.json"
            or marker_report.get("sha256") != file_sha256(report_path)[1]
            or marker_report.get("bytes") != report_size
            or marker.get("comparison_id_sha256")
            != hashlib.sha256(str(report.get("comparison_id", "")).encode("utf-8")).hexdigest()
        ):
            failures.append("Cross-build comparison output marker does not bind report/runtime/artifacts.")

    comparison_context = report_declaration.casefold()
    reviewer_relationship = comparison_fields.get(
        "reviewer_relationship",
        "",
    ).casefold()
    expected_context = {
        f"baseline={baseline_id}",
        f"candidate={candidate_id}",
        f"capture_count={capture_count}",
        f"compatibility={compatibility_status}",
        f"changed_capture_count={changed_count}",
        f"reviewer_relationship={reviewer_relationship}",
    }
    missing_context = sorted(
        item for item in expected_context if item not in comparison_context
    )
    if missing_context:
        failures.append(
            "Compared-build context must name the report's exact baseline, "
            "candidate, capture count, compatibility, changed-capture count, "
            "and visual-review reviewer relationship"
        )
    return failures


QUICK_VISUAL_SOURCE_EXTENSIONS = {
    ".css", ".scss", ".sass", ".less", ".html", ".htm", ".svg", ".png",
    ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".ico", ".woff", ".woff2",
    ".ttf", ".otf", ".eot", ".jsx", ".tsx", ".vue", ".svelte",
}


def quick_impact_manifest_failures(
    body: str,
    *,
    project: Path,
    record_path: Path,
    comparison_report: dict[str, object],
) -> list[str]:
    failures: list[str] = []
    value = (
        markdown_label_value(body, "Authoritative Quick impact manifest") or ""
    ).strip()
    impact_path, binding_failures = bound_artifact(
        value,
        project=project,
        record_path=record_path,
        label="Authoritative Quick impact manifest",
    )
    failures.extend(binding_failures)
    if impact_path is None or binding_failures:
        return failures
    expected_impact = (project / ".design-dna" / "quick-impact.json").resolve()
    if impact_path.resolve() != expected_impact:
        return [*failures, "Quick impact manifest must be .design-dna/quick-impact.json."]
    try:
        impact = json.loads(impact_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [*failures, f"Quick impact manifest is unreadable: {exc}"]
    expected_keys = {
        "schema_version", "record_type", "baseline_render_report",
        "candidate_render_report", "changed_files", "authoritative_capture_ids",
    }
    if (
        not isinstance(impact, dict)
        or set(impact) != expected_keys
        or impact.get("schema_version") != 1
        or impact.get("record_type") != "design-dna-quick-impact"
    ):
        return [*failures, "Quick impact manifest has an unsupported schema."]

    adapter, adapter_failure = load_schema3_render_review_adapter()
    if adapter is None:
        return [*failures, str(adapter_failure)]
    contexts: dict[str, dict[str, object]] = {}
    for role in ("baseline", "candidate"):
        binding = impact.get(f"{role}_render_report")
        if (
            not isinstance(binding, dict)
            or set(binding) != {"path", "sha256"}
            or not isinstance(binding.get("path"), str)
            or not isinstance(binding.get("sha256"), str)
            or SHA256_HEX.fullmatch(binding["sha256"]) is None
        ):
            failures.append(f"Quick impact {role} render-report binding is invalid.")
            continue
        report_path = (project / PurePosixPath(binding["path"])).resolve()
        if (
            not is_within(report_path, project.resolve())
            or not report_path.is_file()
            or file_sha256(report_path)[1] != binding["sha256"]
        ):
            failures.append(f"Quick impact {role} render-report bytes are missing or drifted.")
            continue
        try:
            budget = getattr(adapter, "EvidenceBudget")()
            context = getattr(adapter, "load_schema3_render_review")(
                project,
                {"path": binding["path"], "sha256": binding["sha256"]},
                f"quick-impact.{role}",
                budget,
            )
        except Exception as exc:
            failures.append(f"Quick impact {role} renderer evidence is invalid: {getattr(exc, 'message', str(exc))}")
            continue
        if isinstance(context, dict):
            contexts[role] = context
        else:
            failures.append(f"Quick impact {role} renderer context is invalid.")
    if set(contexts) != {"baseline", "candidate"}:
        return failures

    comparison_inputs = comparison_report.get("inputs")
    for role in ("baseline", "candidate"):
        context = contexts[role]
        binding = impact[f"{role}_render_report"]
        compared = comparison_inputs.get(role) if isinstance(comparison_inputs, dict) else None
        source_report = context.get("report")
        source_manifest = (
            source_report.get("source_snapshot", {}).get("manifest")
            if isinstance(source_report, dict)
            and isinstance(source_report.get("source_snapshot"), dict)
            else None
        )
        if (
            not isinstance(compared, dict)
            or compared.get("report_sha256") != binding["sha256"]
            or compared.get("build", {}).get("id") != context.get("build_id")
            or not isinstance(source_manifest, dict)
            or compared.get("build", {}).get("source_manifest_sha256")
            != source_manifest.get("manifest_sha256")
        ):
            failures.append(f"Quick comparison {role} input does not bind the selected renderer report/build/source manifest.")

    baseline_report = contexts["baseline"].get("report")
    candidate_report = contexts["candidate"].get("report")
    baseline_files = (
        baseline_report.get("source_snapshot", {}).get("manifest", {}).get("files")
        if isinstance(baseline_report, dict)
        else None
    )
    candidate_files = (
        candidate_report.get("source_snapshot", {}).get("manifest", {}).get("files")
        if isinstance(candidate_report, dict)
        else None
    )
    if not isinstance(baseline_files, list) or not isinstance(candidate_files, list):
        return [*failures, "Quick renderer reports must carry frozen source-file manifests."]
    baseline_by_path = {
        item["path"]: item for item in baseline_files
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    candidate_by_path = {
        item["path"]: item for item in candidate_files
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    actual_changes: list[dict[str, object]] = []
    for path_value in sorted(set(baseline_by_path) | set(candidate_by_path)):
        before = baseline_by_path.get(path_value)
        after = candidate_by_path.get(path_value)
        before_sha = before.get("sha256") if before else None
        after_sha = after.get("sha256") if after else None
        if before_sha == after_sha:
            continue
        change = "added" if before is None else "deleted" if after is None else "modified"
        actual_changes.append(
            {
                "path": path_value,
                "change": change,
                "baseline_sha256": before_sha,
                "candidate_sha256": after_sha,
            }
        )
    declared_changes = impact.get("changed_files")
    if not isinstance(declared_changes, list) or not declared_changes:
        failures.append("Quick impact manifest must declare at least one real changed file.")
    else:
        declared_projection = []
        for index, item in enumerate(declared_changes, start=1):
            if not isinstance(item, dict) or set(item) != {
                "path", "change", "baseline_sha256", "candidate_sha256",
                "mechanical_reason",
            }:
                failures.append(f"Quick changed-file row {index} has an unsupported shape.")
                continue
            if not isinstance(item.get("mechanical_reason"), str) or len(item["mechanical_reason"].strip()) < 20:
                failures.append(f"Quick changed-file row {index} needs a substantive mechanical reason.")
            suffix = PurePosixPath(str(item.get("path") or "")).suffix.casefold()
            if suffix in QUICK_VISUAL_SOURCE_EXTENSIONS:
                failures.append(
                    f"Quick cannot modify visible-surface source or asset file {item.get('path')!r}; use Standard."
                )
            declared_projection.append({key: item.get(key) for key in (
                "path", "change", "baseline_sha256", "candidate_sha256"
            )})
        if declared_projection != actual_changes:
            failures.append("Quick changed_files is not the exact baseline/candidate source-manifest diff.")

    def capture_ids(report: object) -> set[str]:
        captures = report.get("captures") if isinstance(report, dict) else None
        return {
            str(capture.get("id"))
            for capture in captures or []
            if isinstance(capture, dict) and isinstance(capture.get("id"), str)
        }

    baseline_capture_ids = capture_ids(baseline_report)
    candidate_capture_ids = capture_ids(candidate_report)
    comparison_capture_ids = {
        str(item.get("capture_id"))
        for item in comparison_report.get("comparisons", [])
        if isinstance(item, dict) and isinstance(item.get("capture_id"), str)
    }
    declared_capture_ids = impact.get("authoritative_capture_ids")
    if (
        not isinstance(declared_capture_ids, list)
        or len(declared_capture_ids) != len(set(declared_capture_ids))
        or set(declared_capture_ids) != baseline_capture_ids
        or set(declared_capture_ids) != candidate_capture_ids
        or set(declared_capture_ids) != comparison_capture_ids
    ):
        failures.append(
            "Quick authoritative_capture_ids must equal every baseline, candidate, and comparison capture."
        )
    return failures


def quick_visual_invariance_failures(
    body: str,
    *,
    project: Path | None,
    record_path: Path | None,
) -> list[str]:
    """Require exact before/after visual equality for the legacy quick profile.

    `quick` is not a lower-quality website mode.  It is retained only for a
    strictly nonvisual mechanical repair, so a completed record must bind a
    fresh packaged comparison covering wide and narrow states with zero changed
    pixels.  Anything else must use Standard and the reference-led gates.
    """

    failures: list[str] = []
    scope = (
        markdown_label_value(body, "Repair scope and affected routes/states")
        or ""
    ).strip()
    purpose = (
        markdown_label_value(body, "Changed files and mechanical purpose")
        or ""
    ).strip()
    assertion = (
        markdown_label_value(body, "Strictly nonvisual repair") or ""
    ).strip().casefold()
    if not non_placeholder(scope) or len(scope) < 12:
        failures.append(
            "Quick mechanical repair must name every affected route/state"
        )
    if not non_placeholder(purpose) or len(purpose) < 12:
        failures.append(
            "Quick mechanical repair must name the changed files and mechanical purpose"
        )
    if assertion != "yes":
        failures.append(
            "Quick is allowed only when Strictly nonvisual repair is exactly yes"
        )

    comparison_record = markdown_label_value(
        body,
        (
            "Cross-build comparison identity, compatibility, changed captures, "
            "reviewer, and result, or `not performed`"
        ),
    )
    decision_value = markdown_label_value(body, "Cross-build decision")
    if not comparison_record or comparison_record.strip().casefold().replace(
        "-", " "
    ).startswith("not performed"):
        failures.append(
            "Quick mechanical repair requires a performed packaged before/after render comparison"
        )
        return failures
    parsed_decision = comparison_decision(decision_value or "")
    if parsed_decision is None or parsed_decision[0] != "accept candidate":
        failures.append(
            "Quick mechanical repair requires an accept candidate cross-build decision after human review"
        )

    if project is None or record_path is None:
        failures.append(
            "Quick mechanical repair requires a project-local comparison report binding"
        )
        return failures
    fields = semicolon_fields(comparison_record.strip().replace("`", ""))
    report_value = fields.get("report", "")
    if not report_value and ";" in comparison_record:
        first_segment = comparison_record.split(";", 1)[0].strip()
        if "sha256:" in first_segment.casefold():
            report_value = first_segment
    report_path, binding_failures = bound_artifact(
        report_value,
        project=project,
        record_path=record_path,
        label="Quick visual-invariance comparison report binding",
    )
    if binding_failures or report_path is None:
        failures.extend(binding_failures)
        return failures
    try:
        report = read_json(report_path)
    except StateError as exc:
        failures.append(f"Quick visual-invariance report is invalid JSON: {exc}")
        return failures
    if not isinstance(report, dict):
        return [*failures, "Quick visual-invariance report must contain an object"]
    failures.extend(
        quick_impact_manifest_failures(
            body,
            project=project,
            record_path=record_path,
            comparison_report=report,
        )
    )

    inputs = report.get("inputs")
    baseline = inputs.get("baseline") if isinstance(inputs, dict) else None
    candidate = inputs.get("candidate") if isinstance(inputs, dict) else None
    baseline_build = (
        baseline.get("build") if isinstance(baseline, dict) else None
    )
    candidate_build = (
        candidate.get("build") if isinstance(candidate, dict) else None
    )
    baseline_id = (
        baseline_build.get("id") if isinstance(baseline_build, dict) else None
    )
    candidate_id = (
        candidate_build.get("id") if isinstance(candidate_build, dict) else None
    )
    if not baseline_id or not candidate_id or baseline_id == candidate_id:
        failures.append(
            "Quick visual invariance requires distinct baseline and candidate build IDs"
        )

    freshness = report.get("baseline_freshness")
    if not isinstance(freshness, dict) or freshness.get("status") != "current":
        failures.append("Quick visual invariance requires a current baseline")

    summary = report.get("summary")
    comparisons = report.get("comparisons")
    if (
        not isinstance(summary, dict)
        or summary.get("changed_capture_count") != 0
        or summary.get("mismatch_pixels") != 0
        or summary.get("mismatch_pixel_ratio") != 0
    ):
        failures.append(
            "Quick visual invariance requires zero changed captures and zero mismatched pixels"
        )
    if not isinstance(comparisons, list) or not comparisons:
        failures.append("Quick visual invariance requires compared captures")
        return failures

    capture_widths: dict[tuple[str, str], set[int]] = {}
    scope_folded = scope.casefold()
    for comparison in comparisons:
        if not isinstance(comparison, dict):
            failures.append("Quick visual invariance contains an invalid comparison")
            continue
        metrics = comparison.get("metrics")
        if (
            not isinstance(metrics, dict)
            or metrics.get("mismatch_pixels") != 0
            or metrics.get("mismatch_pixel_ratio") != 0
        ):
            failures.append(
                "Every Quick comparison capture must have zero pixel mismatch"
            )
        identity = comparison.get("identity")
        if not isinstance(identity, dict):
            failures.append("Quick visual invariance comparison lacks capture identity")
            continue
        route_id = identity.get("route_id")
        scenario_id = identity.get("scenario_id")
        viewport = identity.get("viewport")
        width = viewport.get("width") if isinstance(viewport, dict) else None
        if not isinstance(route_id, str) or not isinstance(scenario_id, str) or type(width) is not int:
            failures.append("Quick visual invariance comparison has an invalid route/state viewport")
            continue
        capture_widths.setdefault((route_id, scenario_id), set()).add(width)
        for visible_name in (identity.get("route_label"), identity.get("state_label")):
            if isinstance(visible_name, str) and visible_name.strip() and visible_name.casefold() not in scope_folded:
                failures.append(
                    "Quick repair scope must name every compared route and state label"
                )
                break
    for route_state, widths in capture_widths.items():
        if not any(width <= 600 for width in widths) or not any(
            width >= 900 for width in widths
        ):
            failures.append(
                "Quick visual invariance requires wide and narrow captures for "
                f"{route_state[0]}/{route_state[1]}"
            )
    return failures


def direction_material_boundary_failures(
    body: str,
    *,
    required_evidence_capabilities: tuple[str, ...] | set[str] | None,
    project: Path | None = None,
    record_path: Path | None = None,
) -> list[str]:
    """Validate the prebuild material decision without prescribing a style.

    This contract exists because a physical subject or an explicit request for
    photography can otherwise disappear between the brief and implementation.
    It deliberately records roles, truth, and a media-light exception instead
    of imposing an image count, genre, palette, or layout.
    """

    failures: list[str] = []
    labels = (
        "Physical or sensory subject",
        "Explicit owner request for photos or rich media",
        "Material and media posture",
        "Project-specific basis",
        "Media roles and truth boundary",
        "Asset manifest and readiness",
        "Deliberately media-light rationale",
        "Media-light exception basis",
        "Media-light exception approval",
        "Media-light exception evidence",
        "Owner-rejection disposition",
        "Protected facts and functions",
        "Public-copy boundary",
    )
    values: dict[str, str] = {}
    for label in labels:
        value = (markdown_label_value(body, label) or "").strip()
        values[label] = value
        if not non_placeholder(value):
            failures.append(
                f"Material/media direction {label!r} is missing or still scaffold text"
            )

    physical = values["Physical or sensory subject"].casefold()
    requested = values[
        "Explicit owner request for photos or rich media"
    ].casefold()
    posture = values["Material and media posture"].casefold()
    for label, value in (
        ("Physical or sensory subject", physical),
        ("Explicit owner request for photos or rich media", requested),
    ):
        if value not in {"yes", "no"}:
            failures.append(f"Material/media direction {label!r} must be yes or no")
    if posture not in {
        "asset-led",
        "deliberately-media-light",
        "inherited-system",
    }:
        failures.append(
            "Material and media posture must be asset-led, deliberately-media-light, "
            "or inherited-system"
        )

    capabilities = set(required_evidence_capabilities or ())
    if posture == "asset-led":
        if "asset-led" not in capabilities:
            failures.append(
                "Asset-led material posture requires the asset-led evidence "
                "capability and its assets.yml record before broad implementation"
            )
        manifest = values["Asset manifest and readiness"].replace("\\", "/")
        if ".design-dna/assets.yml" not in manifest:
            failures.append(
                "Asset-led material posture must name .design-dna/assets.yml and "
                "its honest current readiness"
            )
    if requested == "yes" and posture != "asset-led":
        failures.append(
            "An explicit owner request for photos or rich media requires an "
            "asset-led direction; a media-light exception cannot override the brief"
        )
    if physical == "yes" and posture == "deliberately-media-light":
        rationale = values["Deliberately media-light rationale"]
        raw_basis = values["Media-light exception basis"]
        approval = values["Media-light exception approval"]
        evidence = values["Media-light exception evidence"]
        if not non_placeholder(rationale):
            failures.append(
                "A physical or sensory subject may be deliberately media-light "
                "only with a project-specific reason that explains the visitor "
                "or truth benefit"
            )
        if re.search(
            r"(?:no|without|missing).{0,32}(?:photos?|images?|assets?).{0,32}"
            r"(?:supplied|provided|available)",
            rationale,
            re.I,
        ):
            failures.append(
                "Missing supplied media is not a project-specific reason for a "
                "photo-free physical or sensory direction"
            )
        allowed_bases = {
            "truth-risk",
            "rights-restriction",
            "privacy-consent",
            "accessibility-comprehension",
            "visitor-task-fit",
            "documentary-ethics",
            "performance-budget",
        }
        bases = {
            item.strip().casefold()
            for item in re.split(r"[,;]", raw_basis)
            if item.strip()
        }
        if not bases or not bases.issubset(allowed_bases):
            failures.append(
                "Media-light exception basis must use one or more language-neutral "
                "values: truth-risk, rights-restriction, privacy-consent, "
                "accessibility-comprehension, visitor-task-fit, documentary-ethics, "
                "or performance-budget"
            )
        if not re.search(r"^approved\b", approval, re.I):
            failures.append(
                "A physical or sensory media-light exception requires explicit "
                "owner/client approval beginning with 'approved'"
            )
        if not re.search(r"\bby\s+\S+", approval, re.I) or not re.search(
            r"\b20[0-9]{2}-[01][0-9]-[0-3][0-9]\b",
            approval,
        ):
            failures.append(
                "A physical or sensory media-light exception approval must name "
                "the approving owner/client and an ISO date"
            )
        if project is None or record_path is None:
            failures.append(
                "A physical or sensory media-light exception must be validated "
                "with project-relative owner/client evidence"
            )
        else:
            artifact, artifact_failures = bound_artifact(
                evidence,
                project=project,
                record_path=record_path,
                label="Media-light exception evidence",
            )
            failures.extend(artifact_failures)
            if artifact is not None and not artifact_failures:
                try:
                    evidence_text = artifact.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    failures.append(
                        "Media-light exception evidence must be readable UTF-8 "
                        f"owner/client decision text: {exc}"
                    )
                else:
                    normalized_evidence = evidence_text.casefold()
                    if (
                        approval.casefold() not in normalized_evidence
                        or "decision: approved" not in normalized_evidence
                        or not re.search(
                            r"(?m)^authority:\s*(?:owner|client)\b",
                            normalized_evidence,
                        )
                    ):
                        failures.append(
                            "Media-light exception evidence must contain the exact "
                            "approval line plus 'decision: approved' and an "
                            "owner/client authority declaration"
                        )

    rejection = values["Owner-rejection disposition"]
    normalized_rejection = rejection.casefold()
    if normalized_rejection.startswith("active"):
        rejection_reason = rejection[len("active"):].lstrip(" :;,-")
    elif normalized_rejection.startswith("not-applicable"):
        rejection_reason = rejection[len("not-applicable"):].lstrip(" :;,-")
    else:
        rejection_reason = ""
        failures.append(
            "Owner-rejection disposition must begin with active or not-applicable"
        )
    if len(rejection_reason) < 12:
        failures.append(
            "Owner-rejection disposition must record the scoped rejected cluster "
            "or a project-specific not-applicable reason"
        )
    if (
        posture == "deliberately-media-light"
        and normalized_rejection.startswith("active")
        and re.search(
            r"photo[- ]free|no (?:photos?|photography)|media absence|"
            r"without (?:photos?|photography)|asset[- ]free",
            rejection_reason,
            re.I,
        )
    ):
        failures.append(
            "A deliberately media-light direction contradicts the active owner "
            "rejection of a photo-free or media-absent candidate"
        )
    if project is not None:
        rejection_root = project / ".design-dna" / "rejections"
        if rejection_root.is_dir():
            for rejection_path in sorted(rejection_root.glob("*.json")):
                try:
                    rejection_payload = read_json(rejection_path)
                except StateError as exc:
                    failures.append(
                        "Owner rejection evidence is invalid and therefore "
                        f"fails closed: {exc}"
                    )
                    break
                constraints = (
                    rejection_payload.get("replacement_constraints")
                    if isinstance(rejection_payload, dict)
                    else None
                )
                if (
                    isinstance(rejection_payload, dict)
                    and rejection_payload.get("status") == "active-reopen"
                    and isinstance(constraints, dict)
                    and constraints.get("asset_led_required") is True
                    and posture != "asset-led"
                ):
                    failures.append(
                        "The selected non-asset-led direction contradicts the "
                        "project's structured active owner rejection requiring an "
                        f"asset-led rebuild: {rejection_path.relative_to(project).as_posix()}"
                    )
                    break
    return failures


def substantive_body_failures(
    record: str,
    body: str,
    *,
    project: Path | None = None,
    record_path: Path | None = None,
    required_assurance_profiles: tuple[str, ...] | set[str] | None = None,
    required_evidence_capabilities: tuple[str, ...] | set[str] | None = None,
    evidence_contract: str | None = None,
    enforce_final_visual_binding: bool = False,
) -> list[str]:
    failures: list[str] = []
    sections = markdown_sections(body)
    proportional = (
        evidence_contract == PROPORTIONAL_EVIDENCE_CONTRACT
        or PROPORTIONAL_EVIDENCE_CONTRACT in body
    )
    required_sections = (
        REQUIRED_RECORD_SECTIONS[record]
        if proportional
        else LEGACY_REQUIRED_RECORD_SECTIONS[record]
    )
    capabilities = set(required_evidence_capabilities or ())
    standard_or_stronger = bool(
        set(required_assurance_profiles or {"standard"}) - {"quick"}
    )
    quick_only = set(required_assurance_profiles or ()) == {"quick"}
    if proportional:
        for capability in capabilities:
            required_sections = {
                *required_sections,
                *CAPABILITY_REQUIRED_SECTIONS.get(capability, {}).get(
                    record,
                    set(),
                ),
            }
        if (
            record == "direction"
            and standard_or_stronger
        ):
            required_sections = {
                *required_sections,
                *REFERENCE_SOURCED_DIRECTION_SECTIONS,
            }
        if (
            record == "visual-review"
            and standard_or_stronger
            and enforce_final_visual_binding
        ):
            required_sections = {
                *required_sections,
                *STANDARD_VISUAL_REVIEW_SECTIONS,
            }
        if record == "visual-review" and quick_only:
            required_sections = {
                *required_sections,
                *QUICK_VISUAL_REVIEW_SECTIONS,
            }
    missing_sections = sorted(required_sections - set(sections))
    if missing_sections:
        failures.append(
            "missing required sections: " + ", ".join(missing_sections)
        )
    for heading in sorted(required_sections & set(sections)):
        minimum_length = 24 if proportional else 8
        if len(sections[heading].strip()) < minimum_length:
            failures.append(f"{heading!r} is empty or non-substantive")
    if re.search(r"__[A-Z0-9_]+__", body):
        failures.append("contains an unresolved template token")
    if re.search(r"(?m)^\|\s*(?:\|\s*)+\|?\s*$", body):
        failures.append("contains an unfilled table row")
    for label in required_labels_for_record(
        record,
        body,
        required_assurance_profiles,
        evidence_contract=(
            PROPORTIONAL_EVIDENCE_CONTRACT
            if proportional
            else evidence_contract
        ),
    ):
        if required_label_value(record, body, label) is None:
            failures.append(f"{label!r} is missing or still scaffold text")

    if record == "taste-calibration":
        failures.extend(
            showcase_taste_calibration_failures(
                body,
                project=project,
                record_path=record_path,
                required_assurance_profiles=required_assurance_profiles,
            )
        )

    if record == "reference-dossier":
        failures.extend(
            reference_dossier_failures(
                body,
                project=project,
                record_path=record_path,
            )
        )

    if (
        record == "direction"
        and proportional
        and standard_or_stronger
    ):
        project_evidence = (
            markdown_label_value(body, "Project evidence") or ""
        ).strip()
        organizing_logic = (
            markdown_label_value(body, "Organizing logic") or ""
        ).strip()
        if not non_placeholder(project_evidence):
            failures.append(
                "Reference-sourced organizing logic must bind non-placeholder "
                "project evidence or authority"
            )
        if not non_placeholder(organizing_logic):
            failures.append(
                "Reference-sourced organizing logic must state the selected "
                "reference ranks and mapped relationship, sequence, or behavior"
            )
        if (
            non_placeholder(project_evidence)
            and non_placeholder(organizing_logic)
            and re.sub(r"\W+", " ", project_evidence.casefold()).strip()
            == re.sub(r"\W+", " ", organizing_logic.casefold()).strip()
        ):
            failures.append(
                "Project evidence and organizing logic cannot repeat the same "
                "generic boilerplate"
            )
        failures.extend(
            direction_material_boundary_failures(
                body,
                required_evidence_capabilities=required_evidence_capabilities,
                project=project,
                record_path=record_path,
            )
        )
        decision_headers, decision_rows = markdown_first_table(
            sections.get("Observable consequential design decisions", "")
        )
        expected_decision_headers = (
            "Decision",
            "Selected source rank and project-fit reason",
            "Observable consequence",
            "Verification",
        )
        if decision_headers != expected_decision_headers or not decision_rows:
            failures.append(
                "Observable consequential design decisions need at least one "
                "row using the decision, project reason, observable "
                "consequence, and verification evidence contract"
            )
        else:
            for row_number, row in enumerate(decision_rows, start=1):
                if len(row) != len(expected_decision_headers) or any(
                    not non_placeholder(cell) for cell in row
                ):
                    failures.append(
                        "Observable consequential design decision row "
                        f"{row_number} is incomplete or still scaffold text"
                    )
                    continue
                normalized_cells = {
                    re.sub(r"\W+", " ", cell.casefold()).strip()
                    for cell in row
                }
                if len(normalized_cells) != len(row):
                    failures.append(
                        "Observable consequential design decision row "
                        f"{row_number} repeats generic boilerplate instead of "
                        "binding reason, consequence, and verification"
                    )

    if record == "exploration" and not proportional:
        table_contracts = (
            ("Decision bounds", 4, 1),
            ("Subject and reference evidence", 4, 1),
            ("Candidate field", 7, 1),
            ("Proof comparison", 6, 1),
        )
        exploration_tables: dict[str, list[list[str]]] = {}
        for heading, width, minimum_rows in table_contracts:
            rows = markdown_table_rows(sections.get(heading, ""))
            exploration_tables[heading] = rows
            if len(rows) < minimum_rows:
                failures.append(
                    f"{heading!r} needs at least {minimum_rows} substantive "
                    "rows"
                )
            elif any(
                len(row) != width or any(not non_placeholder(cell) for cell in row)
                for row in rows
            ):
                failures.append(
                    f"{heading!r} contains an incomplete or malformed row"
                )
        constraint_rows = exploration_tables.get("Decision bounds", [])
        allowed_constraint_classes = {
            "non-negotiable",
            "inherited",
            "negotiated",
            "open",
        }
        for row_number, row in enumerate(constraint_rows, start=1):
            if len(row) == 4 and row[1].strip().casefold() not in (
                allowed_constraint_classes
            ):
                failures.append(
                    "Decision bounds row "
                    f"{row_number} must classify its field as non-negotiable, "
                    "inherited, negotiated, or open"
                )

        candidate_rows = exploration_tables.get("Candidate field", [])
        candidate_ids = [
            row[0].strip()
            for row in candidate_rows
            if len(row) == 7
        ]
        if len(candidate_ids) != len(set(candidate_ids)):
            failures.append("Candidate field IDs must be unique")
        invalid_candidate_ids = sorted({
            candidate_id
            for candidate_id in candidate_ids
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", candidate_id)
        })
        if invalid_candidate_ids:
            failures.append(
                "Candidate field IDs are invalid: "
                + ", ".join(invalid_candidate_ids)
            )
        allowed_candidate_statuses = {
            "provisional",
            "revised",
            "rejected",
            "accepted",
            "blocked",
        }
        for row_number, row in enumerate(candidate_rows, start=1):
            if len(row) == 7 and row[6].strip().casefold() not in (
                allowed_candidate_statuses
            ):
                failures.append(
                    f"Candidate field row {row_number} has an unsupported status"
                )

        comparison_status = (
            markdown_label_value(
                body,
                "Comparison performed, partially performed, or not performed",
            )
            or ""
        ).strip().casefold()
        if not comparison_status.startswith(
            ("performed", "partially performed", "not performed")
        ):
            failures.append(
                "Proof comparison status must begin with performed, partially "
                "performed, or not performed"
            )
        proof_rows = exploration_tables.get("Proof comparison", [])
        proof_ids = [
            row[0].strip()
            for row in proof_rows
            if len(row) == 6
        ]
        if len(proof_ids) != len(set(proof_ids)):
            failures.append("Proof comparison candidate IDs must be unique")
        unknown_proof_ids = sorted(set(proof_ids) - set(candidate_ids))
        if unknown_proof_ids:
            failures.append(
                "Proof comparison candidate IDs must belong to Candidate "
                "field entries: "
                + ", ".join(unknown_proof_ids)
            )

        selected_value = (
            markdown_label_value(
                body,
                "Selected candidate ID and source mapping",
            )
            or ""
        ).strip()
        selected_id = selected_value.split(";", 1)[0].strip()
        if selected_id and selected_id not in candidate_ids:
            failures.append(
                "Selected candidate ID must exist in Candidate field"
            )
        if selected_id and selected_id not in proof_ids:
            failures.append(
                "Selected candidate ID must have a Proof comparison row"
            )
        selected_proof_value = (
            markdown_label_value(body, "Selected proof identity and artifact")
            or ""
        ).strip()
        selected_proof_parts = [
            part.strip()
            for part in selected_proof_value.split(";", 1)
        ]
        selected_proof_id = selected_proof_parts[0] if selected_proof_parts else ""
        selected_proof_binding = (
            selected_proof_parts[1]
            if len(selected_proof_parts) == 2
            else ""
        )
        if selected_id and selected_proof_id != selected_id:
            failures.append(
                "Selected proof identity must match the selected candidate ID"
            )

        proof_binding_by_id = {
            row[0].strip(): row[2].strip()
            for row in proof_rows
            if len(row) == 6
        }
        if (
            selected_proof_id
            and proof_binding_by_id.get(selected_proof_id)
            != selected_proof_binding
        ):
            failures.append(
                "Selected proof artifact binding must exactly match its "
                "Proof comparison row"
            )

        for row_number, row in enumerate(proof_rows, start=1):
            if len(row) != 6:
                continue
            artifact_match = ARTIFACT_BINDING_PATTERN.fullmatch(
                row[2].strip()
            )
            if artifact_match is None:
                failures.append(
                    "Proof comparison row "
                    f"{row_number} must bind a project-relative artifact path "
                    "and lowercase SHA-256"
                )
                continue
            relative_path, recorded_hash = artifact_match.groups()
            try:
                artifact = safe_binding_path(
                    project if project is not None else Path.cwd(),
                    relative_path.strip(),
                    record_path=record_path or Path("exploration.md"),
                )
                actual_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
                if recorded_hash != actual_hash:
                    failures.append(
                        "Proof comparison row "
                        f"{row_number} SHA-256 does not match its artifact"
                    )
            except (OSError, StateError) as exc:
                failures.append(
                    f"Proof comparison row {row_number} is invalid: {exc}"
                )

    if record == "direction" and not proportional:
        named_profiles = assurance_profiles(body)
        if not named_profiles:
            failures.append(
                "Assurance profile must name quick, standard, showcase, "
                "high-risk, or an explicit combination"
            )
        elif named_profiles == {
            "quick", "standard", "showcase", "high-risk",
        }:
            failures.append(
                "Assurance profile must select a profile rather than repeat "
                "the template choices"
            )
        expected_profiles = (
            set(required_assurance_profiles)
            & {"quick", "standard", "showcase", "high-risk"}
            if required_assurance_profiles is not None
            else None
        )
        if (
            expected_profiles is not None
            and named_profiles != expected_profiles
        ):
            failures.append(
                "Assurance profile must match the profiles persisted in "
                "state.json"
            )
        for heading, minimum_cells in (
            ("Constraint ledger", 6),
            ("Routes, flows, and states", 5),
            ("Evidence, content, and authority", 5),
            ("Research and exploration", 4),
            ("Source mappings and observable decisions", 7),
        ):
            _headers, rows = markdown_first_table(
                sections.get(heading, "")
            )
            if not rows:
                failures.append(f"{heading!r} needs at least one evidence row")
            elif any(
                len(row) != minimum_cells or any(not cell for cell in row)
                for row in rows
            ):
                failures.append(
                    f"{heading!r} contains an incomplete evidence row"
                )
        constraint_headers, constraint_rows = markdown_first_table(
            sections.get("Constraint ledger", "")
        )
        class_index = (
            constraint_headers.index("Class")
            if "Class" in constraint_headers
            else -1
        )
        allowed_constraint_classes = {
            "non-negotiable",
            "inherited",
            "negotiated",
            "open",
        }
        if class_index >= 0:
            for row_number, row in enumerate(constraint_rows, start=1):
                if (
                    len(row) <= class_index
                    or row[class_index].strip().casefold()
                    not in allowed_constraint_classes
                ):
                    failures.append(
                        "Constraint ledger row "
                        f"{row_number} must use non-negotiable, inherited, "
                        "negotiated, or open"
                    )

        logic_status = (
            markdown_label_value(body, "`status`") or ""
        ).strip().casefold()
        if logic_status not in {
            "provisional",
            "accepted",
            "revised",
            "rejected",
            "blocked",
        }:
            failures.append(
                "Source-mapping status must be provisional, accepted, revised, "
                "rejected, or blocked"
            )
        _decision_headers, decision_rows = markdown_first_table(
            sections.get("Source mappings and observable decisions", "")
        )
        decision_ids = [
            row[0].strip()
            for row in decision_rows
            if len(row) == 7
        ]
        if len(decision_ids) != len(set(decision_ids)):
            failures.append("Observable design decision IDs must be unique")
        if any(
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", decision_id)
            for decision_id in decision_ids
        ):
            failures.append("Observable design decision IDs must be stable IDs")

    if record == "direction-proof" and proportional:
        decision = (
            markdown_label_value(body, "Current decision") or ""
        ).strip().casefold()
        if decision not in {
            "proceed",
            "revise",
            "compare again",
            "reject",
            "blocked",
        }:
            failures.append(
                "Current decision must be proceed, revise, compare again, reject, or blocked"
            )
        reviewer_relationship = (
            markdown_label_value(body, "Reviewer relationship") or ""
        ).strip().casefold()
        allowed_relationships = {
            "producer-self",
            "independent-agent",
            "independent-human",
            "accountable-owner",
            "owner-authorized-human",
        }
        if reviewer_relationship not in allowed_relationships:
            failures.append(
                "Reviewer relationship must identify producer-self, "
                "independent-agent, independent-human, accountable-owner, or "
                "owner-authorized-human"
            )
        owner_disposition = (
            markdown_label_value(body, "Owner disposition") or ""
        ).strip().casefold()
        owner_match = re.match(
            r"^(accepted|rejected|pending|not[ -]required)\b",
            owner_disposition,
        )
        owner_status = (
            owner_match.group(1).replace(" ", "-") if owner_match else ""
        )
        if not owner_status:
            failures.append(
                "Owner disposition must begin with accepted, rejected, pending, "
                "or not-required"
            )
        if owner_status == "accepted" and reviewer_relationship not in {
            "accountable-owner",
            "owner-authorized-human",
        }:
            failures.append(
                "Accepted owner disposition requires an accountable-owner or "
                "owner-authorized-human reviewer relationship"
            )
        if owner_status == "rejected" and decision not in {"revise", "reject"}:
            failures.append(
                "Rejected owner disposition requires Current decision revise or reject"
            )

    if record == "direction-proof" and not proportional:
        decision = markdown_label_value(body, "Decision")
        if decision and decision.casefold() not in {
            "proceed",
            "revise",
            "compare again",
            "reject",
            "blocked",
        }:
            failures.append(
                "Decision must be proceed, revise, compare again, reject, or blocked"
            )
        reviewer_record = markdown_label_value(
            body,
            "Reviewer, relationship, prior exposure, and date",
        ) or ""
        reviewer_relationship_match = re.search(
            r"(?i)(?:^|;)\s*relationship\s*=\s*([^;]+)",
            reviewer_record,
        )
        reviewer_relationship = (
            reviewer_relationship_match.group(1).strip()
            if reviewer_relationship_match
            else ""
        )
        allowed_relationships = {
            "producer-self",
            "independent-agent",
            "independent-human",
            "accountable-owner",
            "owner-authorized-human",
        }
        if (
            reviewer_relationship
            and reviewer_relationship.casefold() not in allowed_relationships
        ):
            failures.append(
                "Reviewer relationship must be producer-self, "
                "independent-agent, independent-human, accountable-owner, or "
                "owner-authorized-human"
            )
        perceptual_status = markdown_label_value(body, "Perceptual status")
        allowed_statuses = {
            "self-reviewed candidate",
            "independently reviewed",
            "owner accepted",
            "rejected",
            "pending",
        }
        if (
            perceptual_status
            and perceptual_status.casefold() not in allowed_statuses
        ):
            failures.append(
                "Perceptual status must be self-reviewed candidate, "
                "independently reviewed, owner accepted, rejected, or pending"
            )
        if (
            perceptual_status
            and perceptual_status.casefold() == "owner accepted"
            and reviewer_relationship
            and reviewer_relationship.casefold()
            not in {"accountable-owner", "owner-authorized-human"}
        ):
            failures.append(
                "Owner accepted requires an accountable-owner or "
                "owner-authorized-human reviewer relationship"
            )
        owner_acceptance = markdown_label_value(
            body,
            "Accountable-owner rendered acceptance",
        )
        owner_acceptance_match = re.match(
            r"(?i)^(accepted|rejected|pending|not[ -]required)\b",
            owner_acceptance or "",
        )
        owner_acceptance_status = (
            owner_acceptance_match.group(1).casefold().replace(" ", "-")
            if owner_acceptance_match
            else ""
        )
        perceptual = (
            perceptual_status.casefold() if perceptual_status else ""
        )
        if perceptual == "owner accepted" and owner_acceptance_status != "accepted":
            failures.append(
                "Perceptual status owner accepted requires accountable-owner "
                "rendered acceptance to begin with accepted"
            )
        if owner_acceptance_status == "accepted" and perceptual != "owner accepted":
            failures.append(
                "Accepted accountable-owner rendered acceptance requires "
                "Perceptual status owner accepted"
            )
        if owner_acceptance_status == "rejected":
            if perceptual != "rejected":
                failures.append(
                    "Rejected accountable-owner rendered acceptance requires "
                    "Perceptual status rejected"
                )
            if decision and decision.casefold() not in {"revise", "reject"}:
                failures.append(
                    "Rejected accountable-owner rendered acceptance requires "
                    "Decision revise or reject"
                )

    if record == "visual-review" and proportional:
        schema3_context: dict[str, object] | None = None
        if standard_or_stronger and enforce_final_visual_binding:
            if project is None or record_path is None:
                failures.append(
                    "Standard+ visual review needs a project-local schema-3 "
                    "rendered-review binding before completion"
                )
            else:
                failures.extend(
                    rendered_review_body_failures(
                        body,
                        project=project,
                        record_path=record_path,
                    )
                )
                schema3_context, schema3_failures = schema3_rendered_review_context(
                    body,
                    project=project,
                    record_path=record_path,
                )
                failures.extend(schema3_failures)
                if schema3_context is not None:
                    failures.extend(
                        visual_review_schema3_capture_matrix_failures(
                            body,
                            project=project,
                            record_path=record_path,
                            context=schema3_context,
                            required_evidence_capabilities=capabilities,
                        )
                    )
        elif markdown_label_value(
            body,
            "Rendered-review report path, hash, contract, and execution result",
        ) and project is not None and record_path is not None:
            failures.extend(
                rendered_review_body_failures(
                    body,
                    project=project,
                    record_path=record_path,
                )
            )
        if markdown_label_value(
            body,
            (
                "Cross-build comparison identity, compatibility, changed "
                "captures, reviewer, and result, or `not performed`"
            ),
        ):
            if project is not None and record_path is not None:
                failures.extend(
                    render_comparison_body_failures(
                        body,
                        project=project,
                        record_path=record_path,
                    )
                )
        if quick_only:
            failures.extend(
                quick_visual_invariance_failures(
                    body,
                    project=project,
                    record_path=record_path,
                )
            )
        review_headers, review_rows = markdown_first_table(
            sections.get("Rendered review", "")
        )
        expected_review_headers = (
            "Route/state",
            "Viewport/context",
            "Rendered PNG path and SHA-256",
            "Observation",
        )
        if review_headers != expected_review_headers or not review_rows:
            failures.append(
                "Rendered review needs at least one row using the compact "
                "route/state, viewport/context, evidence, and observation contract"
            )
        else:
            artifact_index = review_headers.index(
                "Rendered PNG path and SHA-256"
            )
            for row_number, row in enumerate(review_rows, start=1):
                if len(row) != len(expected_review_headers) or any(
                    not non_placeholder(cell) for cell in row
                ):
                    failures.append(
                        f"Rendered review row {row_number} is incomplete"
                    )
                    continue
                if project is not None and record_path is not None:
                    artifact, artifact_failures = bound_artifact(
                        row[artifact_index],
                        project=project,
                        record_path=record_path,
                        label=f"Rendered review row {row_number} artifact",
                    )
                    failures.extend(artifact_failures)
                    if artifact is not None and not artifact_failures:
                        if artifact.suffix.casefold() != ".png":
                            failures.append(
                                "Rendered review row "
                                f"{row_number} evidence must use a .png "
                                "extension that matches its declared type"
                            )
                        else:
                            try:
                                verify_png_artifact(artifact)
                            except StateError as exc:
                                failures.append(
                                    "Rendered review row "
                                    f"{row_number} evidence is not a decodable "
                                    f"PNG: {exc}"
                                )
        final_reviewed = (
            markdown_label_value(body, "Final implementation reviewed") or ""
        ).strip().casefold()
        if final_reviewed not in {"yes", "true"}:
            failures.append(
                "Final implementation reviewed must be yes before completion"
            )
        relationship = (
            markdown_label_value(body, "Reviewer relationship") or ""
        ).strip().casefold()
        allowed_relationships = {
            "producer-self",
            "independent-agent",
            "independent-human",
            "accountable-owner",
            "owner-authorized-human",
            "target-user",
        }
        if relationship not in allowed_relationships:
            failures.append("Reviewer relationship is unsupported")
        conclusion = (
            markdown_label_value(body, "Reviewer conclusion") or ""
        ).strip().casefold()
        allowed_conclusions = {
            "self-reviewed candidate",
            "independently reviewed",
            "target-user reviewed",
            "owner accepted",
            "blocked",
        }
        if conclusion not in allowed_conclusions:
            failures.append("Reviewer conclusion is unsupported")
        owner_disposition = (
            markdown_label_value(body, "Owner disposition") or ""
        ).strip().casefold()
        owner_match = re.match(
            r"^(accepted|rejected|pending|not[ -]required)\b",
            owner_disposition,
        )
        owner_status = (
            owner_match.group(1).replace(" ", "-") if owner_match else ""
        )
        if not owner_status:
            failures.append(
                "Owner disposition must begin with accepted, rejected, pending, "
                "or not-required"
            )
        if relationship == "producer-self" and conclusion in {
            "independently reviewed",
            "target-user reviewed",
            "owner accepted",
        }:
            failures.append(
                "A producer-self visual review cannot claim independent, target-"
                "user, or owner acceptance"
            )
        if conclusion == "owner accepted" and (
            owner_status != "accepted"
            or relationship
            not in {"accountable-owner", "owner-authorized-human"}
        ):
            failures.append(
                "Reviewer conclusion owner accepted requires accepted owner "
                "disposition and accountable-owner or owner-authorized-human review"
            )
        if owner_status == "accepted" and conclusion != "owner accepted":
            failures.append(
                "Accepted owner disposition requires Reviewer conclusion owner accepted"
            )
        if owner_status == "rejected" and conclusion != "blocked":
            failures.append(
                "Rejected owner disposition requires Reviewer conclusion blocked"
            )
        findings_headers, finding_rows = markdown_first_table(
            sections.get("Findings", "")
        )
        if findings_headers != VISUAL_FINDINGS_HEADERS:
            failures.append(
                "Findings must use the exact "
                f"{VISUAL_FINDINGS_CONTRACT} nine-column contract"
            )
        if not finding_rows:
            failures.append(
                "Findings needs at least one reviewed finding or explicit "
                "not-applicable row"
            )
        for row in finding_rows:
            if len(row) != len(VISUAL_FINDINGS_HEADERS) or any(
                not cell for cell in row
            ):
                failures.append("Findings contains an incomplete row")
                continue
            severity = row[0].casefold()
            confidence = row[1].casefold()
            verification = row[6]
            status = row[7].casefold()
            owner = row[8]
            if severity not in VISUAL_SEVERITIES:
                failures.append(f"Findings uses unknown severity {row[0]!r}")
            if confidence not in VISUAL_CONFIDENCES:
                failures.append(
                    f"Findings uses unknown confidence {row[1]!r}"
                )
            if status not in VISUAL_FINDING_STATUSES:
                failures.append(f"Findings uses unknown status {row[7]!r}")
            if not non_placeholder(owner):
                failures.append("Findings requires an explicit owner cell")
            if status == "verified" and not non_placeholder(verification):
                failures.append(
                    "Findings status verified requires exact rerun evidence"
                )
            if status in UNRESOLVED_VISUAL_STATUSES:
                failures.append(
                    f"{row[0]} finding remains {row[7]}; complete records "
                    "require a resolved lifecycle status"
                )
            if severity in {"critical", "high", "medium"} and status not in {
                "verified",
                "not-applicable",
            }:
                failures.append(
                    f"{row[0]} finding remains {row[7]}; complete records "
                    "require verified or not-applicable closure"
                )
        release_blockers = (
            markdown_label_value(body, "Release blockers") or ""
        ).strip()
        resolved = bool(
            re.match(
                r"(?i)^(?:none|no\b|resolved\b|not applicable\b)",
                release_blockers,
            )
        )
        if conclusion != "blocked" and not resolved:
            failures.append(
                "Release blockers must be resolved or explicitly recorded as none"
            )
        if conclusion == "blocked" and resolved:
            failures.append(
                "Reviewer conclusion blocked requires an explicit unresolved "
                "release blocker"
            )

    if record == "visual-review" and not proportional:
        named_profiles = assurance_profiles(body)
        if not named_profiles:
            failures.append(
                "Assurance profile must name quick, standard, showcase, "
                "high-risk, or an explicit combination"
            )
        elif named_profiles == {
            "quick", "standard", "showcase", "high-risk",
        }:
            failures.append(
                "Assurance profile must select a profile rather than repeat "
                "the template choices"
            )
        expected_profiles = (
            set(required_assurance_profiles)
            & {"quick", "standard", "showcase", "high-risk"}
            if required_assurance_profiles is not None
            else None
        )
        if (
            expected_profiles is not None
            and named_profiles != expected_profiles
        ):
            failures.append(
                "Assurance profile must match the profiles persisted in "
                "state.json"
            )
        effective_profiles = (
            expected_profiles
            if expected_profiles is not None
            else named_profiles
        )
        if (
            effective_profiles
            & {"standard", "showcase", "high-risk"}
            and project is not None
            and record_path is not None
        ):
            failures.extend(
                rendered_review_body_failures(
                    body,
                    project=project,
                    record_path=record_path,
                )
            )
            coverage_headers, coverage_rows = markdown_first_table(
                sections.get("Coverage matrix", "")
            )
            artifact_header = "Artifact path and SHA-256"
            if artifact_header not in coverage_headers:
                failures.append(
                    "Coverage matrix must use Artifact path and SHA-256"
                )
            else:
                artifact_index = coverage_headers.index(artifact_header)
                for row_number, row in enumerate(
                    coverage_rows,
                    start=1,
                ):
                    if len(row) <= artifact_index:
                        continue
                    artifact, artifact_failures = bound_artifact(
                        row[artifact_index],
                        project=project,
                        record_path=record_path,
                        label=(
                            "Coverage matrix row "
                            f"{row_number} artifact"
                        ),
                    )
                    failures.extend(artifact_failures)
                    if artifact is not None and not artifact_failures:
                        if artifact.suffix.casefold() != ".png":
                            failures.append(
                                "Coverage matrix row "
                                f"{row_number} rendered evidence must use a "
                                ".png extension that matches its type"
                            )
                        else:
                            try:
                                verify_png_artifact(artifact)
                            except StateError as exc:
                                failures.append(
                                    "Coverage matrix row "
                                    f"{row_number} rendered evidence is not a "
                                    f"decodable PNG: {exc}"
                                )
        if project is not None and record_path is not None:
            failures.extend(
                render_comparison_body_failures(
                    body,
                    project=project,
                    record_path=record_path,
                )
            )
        reviewer_record = markdown_label_value(
            body,
            "Reviewers, relationship, and lens",
        ) or ""
        reviewer_relationship = semicolon_fields(reviewer_record).get(
            "relationship",
            "",
        )
        allowed_reviewer_relationships = {
            "producer-self",
            "independent-agent",
            "independent-human",
            "accountable-owner",
            "owner-authorized-human",
            "target-user",
        }
        if (
            reviewer_relationship
            and reviewer_relationship.casefold()
            not in allowed_reviewer_relationships
        ):
            failures.append(
                "Reviewer relationship must be producer-self, "
                "independent-agent, independent-human, accountable-owner, "
                "owner-authorized-human, or target-user"
            )
        owner_record = markdown_label_value(
            body,
            (
                "Accountable-owner disposition, scope, ID, date, "
                "candidate/build, and evidence"
            ),
        ) or ""
        owner_acceptance = semicolon_fields(owner_record).get("status", "")
        owner_acceptance_match = re.match(
            r"(?i)^(accepted|rejected|pending|not[ -]required)\b",
            owner_acceptance or "",
        )
        owner_acceptance_status = (
            owner_acceptance_match.group(1).casefold().replace(" ", "-")
            if owner_acceptance_match
            else ""
        )
        if owner_acceptance and not owner_acceptance_status:
            failures.append(
                "Accountable-owner rendered acceptance must begin with "
                "accepted, rejected, pending, or not-required"
            )
        reviewer_conclusion = markdown_label_value(
            body,
            "Reviewer conclusion",
        )
        allowed_reviewer_conclusions = {
            "self-reviewed candidate",
            "independently reviewed",
            "target-user reviewed",
            "owner accepted",
            "blocked",
        }
        if (
            reviewer_conclusion
            and reviewer_conclusion.casefold()
            not in allowed_reviewer_conclusions
        ):
            failures.append(
                "Reviewer conclusion must be self-reviewed candidate, "
                "independently reviewed, target-user reviewed, owner accepted, "
                "or blocked"
            )
        conclusion = reviewer_conclusion.casefold() if reviewer_conclusion else ""
        relationship = (
            reviewer_relationship.casefold() if reviewer_relationship else ""
        )
        if relationship == "producer-self" and conclusion in {
            "independently reviewed",
            "target-user reviewed",
            "owner accepted",
        }:
            failures.append(
                "A producer-self visual review can only conclude "
                "self-reviewed candidate or blocked"
            )
        if conclusion == "owner accepted":
            if owner_acceptance_status != "accepted":
                failures.append(
                    "Reviewer conclusion owner accepted requires accountable-"
                    "owner rendered acceptance to begin with accepted"
                )
            if relationship not in {
                "accountable-owner",
                "owner-authorized-human",
            }:
                failures.append(
                    "Reviewer conclusion owner accepted requires an "
                    "accountable-owner or owner-authorized-human reviewer "
                    "relationship"
                )
        if owner_acceptance_status == "rejected" and conclusion != "blocked":
            failures.append(
                "Accountable-owner rejection requires Reviewer conclusion "
                "blocked"
            )
        if owner_acceptance_status == "accepted" and conclusion != "owner accepted":
            failures.append(
                "Accepted accountable-owner rendered acceptance requires "
                "Reviewer conclusion owner accepted"
            )
        final_round_record = markdown_label_value(
            body,
            "Date and final implementation round reviewed",
        ) or ""
        final_round_fields = semicolon_fields(final_round_record)
        final_round = final_round_fields.get("final_round", "")
        if not final_round:
            trailing_match = re.search(r"(?i)(?:^|[;,:])\s*(yes|no)\s*$", final_round_record)
            final_round = trailing_match.group(1) if trailing_match else ""
        if final_round.casefold() != "yes":
            failures.append(
                "a complete visual review must cover the final implementation round"
            )
        coverage = markdown_table_rows(sections.get("Coverage matrix", ""))
        if not coverage:
            failures.append(
                "Coverage matrix needs at least one tested route/state/context row"
            )
        elif any(len(row) != 5 or any(not cell for cell in row) for row in coverage):
            failures.append("Coverage matrix contains an incomplete row")
        findings_headers, finding_rows = markdown_first_table(
            sections.get("Findings", "")
        )
        if findings_headers != VISUAL_FINDINGS_HEADERS:
            failures.append(
                "Findings must use the exact "
                f"{VISUAL_FINDINGS_CONTRACT} nine-column contract"
            )
        if not finding_rows:
            failures.append(
                "Findings needs at least one reviewed finding or explicit "
                "not-applicable row"
            )
        for row in finding_rows:
            if len(row) != len(VISUAL_FINDINGS_HEADERS) or any(
                not cell for cell in row
            ):
                failures.append("Findings contains an incomplete row")
                continue
            severity = row[0].casefold()
            confidence = row[1].casefold()
            verification = row[6]
            status = row[7].casefold()
            owner = row[8]
            if severity not in VISUAL_SEVERITIES:
                failures.append(f"Findings uses unknown severity {row[0]!r}")
            if confidence not in VISUAL_CONFIDENCES:
                failures.append(
                    f"Findings uses unknown confidence {row[1]!r}"
                )
            if status not in VISUAL_FINDING_STATUSES:
                failures.append(f"Findings uses unknown status {row[7]!r}")
            if not non_placeholder(owner):
                failures.append("Findings requires an explicit owner cell")
            if status == "verified" and not non_placeholder(verification):
                failures.append(
                    "Findings status verified requires exact rerun evidence"
                )
            if status in UNRESOLVED_VISUAL_STATUSES:
                failures.append(
                    f"{row[0]} finding remains {row[7]}; complete records "
                    "require a resolved lifecycle status"
                )
            if severity in {"critical", "high", "medium"} and status not in {
                "verified",
                "not-applicable",
            }:
                failures.append(
                    f"{row[0]} finding remains {row[7]}; complete records "
                    "require verified or not-applicable closure"
                )
        release_blockers = markdown_label_value(
            body,
            (
                "Remaining limitations, open high/medium findings, owners, "
                "and release blockers"
            ),
        )
        if (
            release_blockers
            and conclusion != "blocked"
            and not re.match(
                r"(?i)^(?:none|no\b|resolved\b|not applicable\b)",
                release_blockers,
            )
        ):
            failures.append(
                "Release blockers must be resolved or explicitly recorded as none"
            )
        if conclusion == "blocked" and release_blockers and re.match(
            r"(?i)^(?:none|no\b|resolved\b|not applicable\b)",
            release_blockers,
        ):
            failures.append(
                "Reviewer conclusion blocked requires an explicit unresolved "
                "release blocker"
            )

    if record == "claims":
        claim_rows = markdown_table_rows(sections.get("Claims", ""))
        if not claim_rows:
            failures.append("Claims needs at least one reviewed claim row")
        for row in claim_rows:
            if len(row) != 9 or any(not cell for cell in row):
                failures.append("Claims contains an incomplete row")
                continue
            status = row[4].casefold()
            treatment = row[8].casefold()
            if status not in {"approved", "scenario", "pending", "prohibited"}:
                failures.append(f"Claims uses unknown status {row[4]!r}")
            if treatment not in {
                "show",
                "qualify",
                "label",
                "replace",
                "defer",
                "omit",
            }:
                failures.append(
                    f"Claims uses unknown public treatment {row[8]!r}"
                )
            if status in {"pending", "prohibited"} and treatment not in {
                "defer",
                "omit",
            }:
                failures.append(
                    f"{row[0]} is {row[4]} but is not deferred or omitted"
                )
            if status == "scenario" and treatment not in {"qualify", "label"}:
                failures.append(
                    f"{row[0]} is a scenario but is not qualified or labeled"
                )
    failures.extend(owner_disposition_body_failures(
        record,
        body,
        project=project,
        record_path=record_path,
    ))
    return failures


def safe_binding_path(project: Path, relative: str, *, record_path: Path) -> Path:
    if (
        not relative
        or "\\" in relative
        or relative.startswith("/")
        or re.match(r"^[A-Za-z]:", relative)
    ):
        raise StateError(
            "invalid-record-binding",
            "binding_path must be a safe project-relative POSIX file path.",
            path=record_path,
        )
    pure = PurePosixPath(relative)
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise StateError(
            "invalid-record-binding",
            "binding_path must not contain empty, dot, or parent segments.",
            path=record_path,
        )
    candidate = lexical_absolute(project.joinpath(*pure.parts))
    if not is_within(candidate, project):
        raise StateError(
            "invalid-record-binding",
            "binding_path escapes the selected project.",
            path=record_path,
        )
    assert_no_reparse_ancestors(candidate, stop=project)
    if not candidate.is_file():
        raise StateError(
            "record-binding-missing",
            "The bound build or artifact file does not exist.",
            path=candidate,
        )
    if candidate == record_path:
        raise StateError(
            "invalid-record-binding",
            "A record cannot use itself as its independent build/artifact binding.",
            path=record_path,
        )
    return candidate


def completed_record_failures(
    project: Path,
    path: Path,
    record: str,
    metadata: dict[str, str],
    body: str,
    *,
    required_assurance_profiles: tuple[str, ...] | set[str] | None = None,
    required_evidence_capabilities: tuple[str, ...] | set[str] | None = None,
) -> list[str]:
    failures = substantive_body_failures(
        record,
        body,
        project=project,
        record_path=path,
        required_assurance_profiles=required_assurance_profiles,
        required_evidence_capabilities=required_evidence_capabilities,
        evidence_contract=metadata.get("evidence_contract"),
        enforce_final_visual_binding=True,
    )
    missing = sorted(COMPLETE_RECORD_FIELDS - set(metadata))
    if missing:
        failures.append(
            "complete metadata is missing: " + ", ".join(missing)
        )
        return failures
    actual_body_hash = body_sha256(body)
    if metadata.get("record_body_sha256") != actual_body_hash:
        failures.append(
            "record_body_sha256 does not match the exact current Markdown body"
        )
    if metadata.get("binding_kind") not in {"build", "artifact"}:
        failures.append("binding_kind must be build or artifact")
    for field in ("binding_id", "completion_owner", "limitations"):
        if not non_placeholder(metadata.get(field)):
            failures.append(f"{field} must be an explicit non-placeholder value")
    if metadata.get("unresolved_high") != "0":
        failures.append("unresolved_high must be 0 before status can be complete")
    if metadata.get("unresolved_medium") != "0":
        failures.append("unresolved_medium must be 0 before status can be complete")
    try:
        completed = datetime.fromisoformat(
            metadata.get("completed_at", "").replace("Z", "+00:00")
        )
        if completed.tzinfo is None:
            raise ValueError("timezone missing")
        if completed.astimezone(timezone.utc) > datetime.now(timezone.utc):
            failures.append("completed_at may not be in the future")
    except ValueError:
        failures.append("completed_at must be an ISO date-time with timezone")
    try:
        binding = safe_binding_path(
            project,
            metadata.get("binding_path", ""),
            record_path=path,
        )
        actual_binding_hash = hashlib.sha256(binding.read_bytes()).hexdigest()
        if metadata.get("binding_sha256") != actual_binding_hash:
            failures.append(
                "binding_sha256 does not match the exact current build/artifact file"
            )
    except (OSError, StateError) as exc:
        failures.append(str(exc))
    return failures


def migration_report_failures(
    project: Path,
    state_root: Path,
) -> list[str]:
    path = state_root / MIGRATION_REPORT
    invalid_legacy_entries = [
        filename
        for filename in LEGACY_RECORD_FILES
        if (state_root / filename).exists()
        and not (state_root / filename).is_file()
    ]
    if invalid_legacy_entries:
        return [
            "Legacy record names must be regular files: "
            + ", ".join(invalid_legacy_entries)
            + "."
        ]
    legacy_paths = [
        state_root / filename
        for filename in LEGACY_RECORD_FILES
        if (state_root / filename).is_file()
    ]
    if not legacy_paths and not path.exists():
        return []
    if legacy_paths and not path.is_file():
        return [
            "Legacy records require a hash-bound migration report; run --migrate."
        ]
    if not path.is_file():
        return [f"{MIGRATION_REPORT} exists but is not a regular file."]
    try:
        payload = read_json(path)
    except StateError as exc:
        return [f"Invalid {MIGRATION_REPORT}: {exc}"]
    required = {
        "schema_version",
        "record_type",
        "migrated_at",
        "legacy_files",
        "record_updates",
    }
    optional = {
        "visual_review_migrations",
        "completion_downgrades",
        "asset_manifest_migrations",
        "assurance_transitions",
        "project_contrast_migrations",
    }
    if (
        not isinstance(payload, dict)
        or not required.issubset(payload)
        or set(payload) - required - optional
    ):
        return [f"{MIGRATION_REPORT} has an unsupported shape."]
    failures: list[str] = []
    if (
        payload.get("schema_version") != 1
        or payload.get("record_type") != "design-dna-project-state-migration"
    ):
        failures.append(f"{MIGRATION_REPORT} has an invalid contract identity.")
    try:
        migrated = datetime.fromisoformat(
            str(payload.get("migrated_at", "")).replace("Z", "+00:00")
        )
        if migrated.tzinfo is None or migrated.astimezone(timezone.utc) > datetime.now(timezone.utc):
            raise ValueError("invalid migration time")
    except ValueError:
        failures.append(f"{MIGRATION_REPORT} migrated_at is invalid.")
    legacy_entries = payload.get("legacy_files")
    if not isinstance(legacy_entries, list):
        failures.append(f"{MIGRATION_REPORT} legacy_files must be a list.")
        legacy_entries = []
    observed: set[str] = set()
    for entry in legacy_entries:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"path", "sha256", "bytes", "disposition"}
            or entry.get("disposition") != "preserved-unmapped"
            or not isinstance(entry.get("bytes"), int)
        ):
            failures.append(f"{MIGRATION_REPORT} contains an invalid legacy file entry.")
            continue
        relative = str(entry.get("path", ""))
        if relative not in LEGACY_RECORD_FILES or relative in observed:
            failures.append(f"{MIGRATION_REPORT} contains an invalid or duplicate legacy path.")
            continue
        observed.add(relative)
        legacy = state_root / relative
        if not legacy.is_file():
            failures.append(f"{MIGRATION_REPORT} references missing legacy file {relative}.")
            continue
        try:
            data = legacy.read_bytes()
        except OSError as exc:
            failures.append(f"Unable to verify legacy file {relative}: {exc}")
            continue
        if entry.get("bytes") != len(data):
            failures.append(f"{MIGRATION_REPORT} byte count changed for {relative}.")
        if entry.get("sha256") != hashlib.sha256(data).hexdigest():
            failures.append(f"{MIGRATION_REPORT} hash changed for {relative}.")
    expected = {path.name for path in legacy_paths}
    if observed != expected:
        failures.append(
            f"{MIGRATION_REPORT} does not exactly inventory current legacy records."
        )
    updates = payload.get("record_updates")
    if (
        not isinstance(updates, list)
        or len(updates) != len(set(map(str, updates)))
        or any(
            str(item) not in {*SUBSTANTIVE_RECORDS.values(), "project-contrast"}
            for item in updates
        )
    ):
        failures.append(f"{MIGRATION_REPORT} record_updates is invalid.")
    completion_downgrades = payload.get("completion_downgrades", [])
    if not isinstance(completion_downgrades, list):
        failures.append(
            f"{MIGRATION_REPORT} completion_downgrades must be a list."
        )
        completion_downgrades = []
    downgrade_keys = {
        "path",
        "record",
        "source_created_with",
        "source_body_sha256",
        "prior_binding_id",
        "prior_binding_path",
        "prior_binding_sha256",
        "prior_completion_owner",
        "prior_completed_at",
        "prior_limitations",
        "reasons",
    }
    observed_downgrades: set[tuple[str, str]] = set()
    for index, entry in enumerate(completion_downgrades):
        label = f"{MIGRATION_REPORT} completion_downgrades[{index}]"
        if not isinstance(entry, dict) or set(entry) != downgrade_keys:
            failures.append(f"{label} has an unsupported shape.")
            continue
        record = str(entry.get("record", ""))
        record_path = str(entry.get("path", ""))
        if SUBSTANTIVE_RECORDS.get(record_path) != record:
            failures.append(f"{label} has an invalid record/path pair.")
        source_hash = str(entry.get("source_body_sha256", ""))
        identity = (record_path, source_hash)
        if identity in observed_downgrades:
            failures.append(f"{label} duplicates a prior downgrade.")
        observed_downgrades.add(identity)
        if not re.fullmatch(r"[0-9a-f]{64}", source_hash):
            failures.append(f"{label} has an invalid source_body_sha256.")
        source_created_with = entry.get("source_created_with")
        if (
            not isinstance(source_created_with, str)
            or (
                source_created_with != "not-recorded"
                and (
                    not source_created_with.startswith("design-dna ")
                    or not SEMVER.fullmatch(
                        source_created_with.removeprefix("design-dna ")
                    )
                )
            )
        ):
            failures.append(f"{label} has an invalid source_created_with.")
        if (
            not isinstance(entry.get("prior_binding_id"), str)
            or not str(entry.get("prior_binding_id", "")).strip()
        ):
            failures.append(f"{label} has an invalid prior_binding_id.")
        for field in (
            "prior_binding_path",
            "prior_completion_owner",
            "prior_completed_at",
            "prior_limitations",
        ):
            if (
                not isinstance(entry.get(field), str)
                or not str(entry.get(field, "")).strip()
            ):
                failures.append(f"{label} has an invalid {field}.")
        prior_binding_hash = str(entry.get("prior_binding_sha256", ""))
        if (
            prior_binding_hash != "not-recorded"
            and not re.fullmatch(r"[0-9a-f]{64}", prior_binding_hash)
        ):
            failures.append(
                f"{label} has an invalid prior_binding_sha256."
            )
        reasons = entry.get("reasons")
        if (
            not isinstance(reasons, list)
            or not reasons
            or not all(
                isinstance(reason, str) and non_placeholder(reason)
                for reason in reasons
            )
            or len(reasons) != len(set(reasons))
        ):
            failures.append(f"{label} reasons must be unique and substantive.")
    asset_migrations = payload.get("asset_manifest_migrations", [])
    if not isinstance(asset_migrations, list):
        failures.append(
            f"{MIGRATION_REPORT} asset_manifest_migrations must be a list."
        )
        asset_migrations = []
    asset_migration_keys = {
        "path",
        "source_schema_version",
        "target_schema_version",
        "source_manifest_sha256",
        "migrated_manifest_sha256",
        "unresolved_asset_ids",
    }
    observed_asset_migrations: set[str] = set()
    for index, entry in enumerate(asset_migrations):
        label = f"{MIGRATION_REPORT} asset_manifest_migrations[{index}]"
        if not isinstance(entry, dict) or set(entry) != asset_migration_keys:
            failures.append(f"{label} has an unsupported shape.")
            continue
        source_hash = str(entry.get("source_manifest_sha256", ""))
        if source_hash in observed_asset_migrations:
            failures.append(f"{label} duplicates a prior asset migration.")
        observed_asset_migrations.add(source_hash)
        if (
            entry.get("path") != "assets.yml"
            or entry.get("source_schema_version") != 1
            or entry.get("target_schema_version") != ASSET_SCHEMA_VERSION
        ):
            failures.append(f"{label} has an invalid schema transition.")
        for hash_field in (
            "source_manifest_sha256",
            "migrated_manifest_sha256",
        ):
            if not re.fullmatch(
                r"[0-9a-f]{64}",
                str(entry.get(hash_field, "")),
            ):
                failures.append(f"{label} has an invalid {hash_field}.")
        unresolved_ids = entry.get("unresolved_asset_ids")
        if (
            not isinstance(unresolved_ids, list)
            or not all(
                isinstance(asset_id, str)
                and re.fullmatch(r"ASSET-[0-9]{3,}", asset_id)
                for asset_id in unresolved_ids
            )
            or len(unresolved_ids) != len(set(unresolved_ids))
        ):
            failures.append(
                f"{label} unresolved_asset_ids must be unique asset IDs."
            )
    project_contrast_migrations = payload.get("project_contrast_migrations", [])
    if not isinstance(project_contrast_migrations, list):
        failures.append(
            f"{MIGRATION_REPORT} project_contrast_migrations must be a list."
        )
        project_contrast_migrations = []
    project_contrast_migration_keys = {
        "path",
        "source_sha256",
        "migrated_sha256",
        "disposition",
        "limitations",
    }
    observed_project_contrast_migrations: set[str] = set()
    for index, entry in enumerate(project_contrast_migrations):
        label = f"{MIGRATION_REPORT} project_contrast_migrations[{index}]"
        if not isinstance(entry, dict) or set(entry) != project_contrast_migration_keys:
            failures.append(f"{label} has an unsupported shape.")
            continue
        source_hash = str(entry.get("source_sha256", ""))
        if source_hash in observed_project_contrast_migrations:
            failures.append(f"{label} duplicates a prior Project Contrast migration.")
        observed_project_contrast_migrations.add(source_hash)
        if entry.get("path") != "project-contrast.json":
            failures.append(f"{label} has an invalid Project Contrast path.")
        for hash_field in ("source_sha256", "migrated_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get(hash_field, ""))):
                failures.append(f"{label} has an invalid {hash_field}.")
        if entry.get("disposition") != "known-placeholder-record-reset-to-explicit-draft":
            failures.append(f"{label} has an unsupported disposition.")
        if not non_placeholder(str(entry.get("limitations", ""))):
            failures.append(f"{label} limitations are not substantive.")
    assurance_transitions = payload.get("assurance_transitions", [])
    if not isinstance(assurance_transitions, list):
        failures.append(
            f"{MIGRATION_REPORT} assurance_transitions must be a list."
        )
        assurance_transitions = []
    transition_keys = {
        "source_schema_version",
        "target_schema_version",
        "source_state_sha256",
        "migrated_state_sha256",
        "source_profile_field",
        "source_profile_values",
        "target_assurance_profiles",
        "required_records",
        "reason",
    }
    observed_transitions: set[str] = set()
    for index, entry in enumerate(assurance_transitions):
        label = f"{MIGRATION_REPORT} assurance_transitions[{index}]"
        if not isinstance(entry, dict) or set(entry) != transition_keys:
            failures.append(f"{label} has an unsupported shape.")
            continue
        source_hash = str(entry.get("source_state_sha256", ""))
        if source_hash in observed_transitions:
            failures.append(f"{label} duplicates a prior transition.")
        observed_transitions.add(source_hash)
        if (
            not isinstance(entry.get("source_schema_version"), int)
            or entry.get("source_schema_version") < 0
            or entry.get("target_schema_version") != STATE_SCHEMA_VERSION
            or entry.get("source_profile_field")
            not in {
                "assurance_profile",
                "assurance_profiles",
                "missing",
            }
        ):
            failures.append(f"{label} has an invalid schema/profile source.")
        for hash_field in (
            "source_state_sha256",
            "migrated_state_sha256",
        ):
            if not re.fullmatch(
                r"[0-9a-f]{64}",
                str(entry.get(hash_field, "")),
            ):
                failures.append(f"{label} has an invalid {hash_field}.")
        source_values = entry.get("source_profile_values")
        if (
            not isinstance(source_values, list)
            or not all(isinstance(item, str) for item in source_values)
            or len(source_values) != len(set(source_values))
        ):
            failures.append(f"{label} source_profile_values is invalid.")
        target_profiles = entry.get("target_assurance_profiles")
        try:
            normalized_targets = normalize_assurance_profiles(
                target_profiles
                if isinstance(target_profiles, list)
                else []
            )
            if list(normalized_targets) != target_profiles:
                failures.append(
                    f"{label} target_assurance_profiles is not canonical."
                )
        except StateError:
            failures.append(
                f"{label} target_assurance_profiles is invalid."
            )
        transition_records = entry.get("required_records")
        if (
            not isinstance(transition_records, list)
            or not transition_records
            or not all(
                isinstance(record, str) and record in RECORD_TEMPLATES
                for record in transition_records
            )
            or len(transition_records) != len(set(transition_records))
        ):
            failures.append(f"{label} required_records is invalid.")
        if not non_placeholder(str(entry.get("reason", ""))):
            failures.append(f"{label} reason is not substantive.")
    visual_migrations = payload.get("visual_review_migrations", [])
    if not isinstance(visual_migrations, list):
        failures.append(
            f"{MIGRATION_REPORT} visual_review_migrations must be a list."
        )
        visual_migrations = []
    migration_keys = {
        "path",
        "source_contract",
        "source_schema_version",
        "source_created_with",
        "source_body_sha256",
        "migrated_body_sha256",
        "source_table",
        "source_table_sha256",
        "migrated_table",
        "migrated_table_sha256",
    }
    observed_visual_migrations: set[tuple[str, str]] = set()
    for index, entry in enumerate(visual_migrations):
        label = (
            f"{MIGRATION_REPORT} visual_review_migrations[{index}]"
        )
        if not isinstance(entry, dict) or set(entry) != migration_keys:
            failures.append(f"{label} has an unsupported shape.")
            continue
        identity = (
            str(entry.get("source_body_sha256", "")),
            str(entry.get("migrated_body_sha256", "")),
        )
        if identity in observed_visual_migrations:
            failures.append(f"{label} duplicates a prior migration.")
        observed_visual_migrations.add(identity)
        if (
            entry.get("path") != "visual-review.md"
            or entry.get("source_contract")
            not in {
                "legacy-schema-1-six-column",
                "design-dna-2.2-eight-column",
            }
            or entry.get("source_schema_version") != 1
        ):
            failures.append(f"{label} has an invalid source contract.")
        source_created_with = entry.get("source_created_with")
        if (
            not isinstance(source_created_with, str)
            or not source_created_with.startswith("design-dna ")
            or not SEMVER.fullmatch(
                source_created_with.removeprefix("design-dna ")
            )
        ):
            failures.append(f"{label} has an invalid source_created_with.")
        for hash_field in (
            "source_body_sha256",
            "migrated_body_sha256",
            "source_table_sha256",
            "migrated_table_sha256",
        ):
            if not re.fullmatch(
                r"[0-9a-f]{64}",
                str(entry.get(hash_field, "")),
            ):
                failures.append(f"{label} has an invalid {hash_field}.")
        for table_field, hash_field in (
            ("source_table", "source_table_sha256"),
            ("migrated_table", "migrated_table_sha256"),
        ):
            table = entry.get(table_field)
            if not isinstance(table, str) or not table.strip():
                failures.append(f"{label} has an empty {table_field}.")
                continue
            if hashlib.sha256(table.encode("utf-8")).hexdigest() != entry.get(
                hash_field
            ):
                failures.append(
                    f"{label} {hash_field} does not bind {table_field}."
                )
    return failures


def restricted_git_tracking(
    project: Path,
    state_root: Path,
) -> tuple[list[str], str | None]:
    """Return tracked restricted records and an explicit verification warning."""
    environment = os.environ.copy()
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    ):
        environment.pop(name, None)
    environment["GIT_OPTIONAL_LOCKS"] = "0"

    try:
        probe = subprocess.run(
            ["git", "-C", str(project), "rev-parse", "--show-toplevel"],
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=10,
            env=environment,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], (
            "Git tracking for restricted research could not be verified: "
            f"{exc}. Recheck before collecting participant data."
        )
    if probe.returncode != 0:
        return [], (
            "Git tracking for restricted research was not verified because "
            "the project is not confirmed to be inside a Git worktree. "
            "Recheck after Git initialization and before collecting "
            "participant data."
        )

    raw_root = probe.stdout.strip()
    if not raw_root:
        return [], (
            "Git tracking for restricted research could not be verified "
            "because Git returned no worktree root. Recheck before collecting "
            "participant data."
        )
    repository_root = lexical_absolute(Path(raw_root))
    if not is_within(state_root, repository_root):
        return [], (
            "Git tracking for restricted research could not be verified "
            "because the reported worktree does not contain .design-dna. "
            "Recheck before collecting participant data."
        )
    state_relative = state_root.relative_to(repository_root).as_posix()

    try:
        listed = subprocess.run(
            [
                "git",
                "-C",
                str(repository_root),
                "ls-files",
                "-z",
                "--full-name",
                "--",
                state_relative,
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=10,
            env=environment,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], (
            "Git tracking for restricted research could not be verified: "
            f"{exc}. Recheck before collecting participant data."
        )
    if listed.returncode != 0:
        return [], (
            "Git tracking for restricted research could not be verified "
            "because Git could not enumerate tracked .design-dna files. "
            "Recheck before collecting participant data."
        )

    prefix = state_relative.rstrip("/")
    user_validation = f"{prefix}/user-validation.md"
    research_prefix = f"{prefix}/evidence/research/"
    prefix_key = prefix.casefold()
    user_validation_key = user_validation.casefold()
    research_prefix_key = research_prefix.casefold()
    tracked: list[str] = []
    for raw_name in listed.stdout.split(b"\0"):
        if not raw_name:
            continue
        name = raw_name.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        name_key = name.casefold()
        path = PurePosixPath(name)
        restricted_at_root = (
            path.parent.as_posix().casefold() == prefix_key
            and ".restricted." in path.name.casefold()
        )
        if (
            name_key == user_validation_key
            or name_key.startswith(research_prefix_key)
            or restricted_at_root
        ):
            tracked.append(name)
    return sorted(set(tracked)), None


def validate_state_root(
    state_root: Path,
    project: Path,
    current_version: str,
) -> tuple[list[str], list[str]]:
    assert_no_reparse_ancestors(state_root, stop=project)
    assert_safe_tree(state_root)
    failures: list[str] = []
    warnings: list[str] = []
    if not state_root.is_dir():
        return ([f"Missing project state directory: {state_root}"], warnings)
    manifest_path = state_root / "state.json"
    if not manifest_path.is_file():
        failures.append(f"Missing state file: {manifest_path}")
        return failures, warnings
    records: list[str] = []
    state_profiles: tuple[str, ...] = ()
    evidence_capabilities: tuple[str, ...] = ()
    extension_records: list[dict[str, object]] = []
    try:
        state = read_json(manifest_path)
        required_state_fields = {
            "schema_version",
            "created_with",
            "created",
            "classification",
            "assurance_profiles",
            "records",
        }
        allowed_state_fields = {
            *required_state_fields,
            "evidence_contract",
        }
        if (
            not isinstance(state, dict)
            or not required_state_fields.issubset(state)
            or not set(state).issubset(allowed_state_fields)
        ):
            failures.append("state.json has an unsupported shape.")
            state = {}
        if state.get("schema_version") != STATE_SCHEMA_VERSION:
            failures.append("state.json has an unsupported schema_version.")
        if state.get("classification") != "internal":
            failures.append("state.json classification must be internal.")
        raw_profiles = state.get("assurance_profiles")
        if (
            not isinstance(raw_profiles, list)
            or not raw_profiles
            or not all(isinstance(item, str) for item in raw_profiles)
            or len(raw_profiles) != len(set(raw_profiles))
        ):
            failures.append(
                "state.json assurance_profiles is missing or unsupported; "
                "run --migrate for an older state."
            )
        else:
            try:
                state_profiles = normalize_assurance_profiles(raw_profiles)
                if list(state_profiles) != raw_profiles:
                    failures.append(
                        "state.json assurance_profiles must use the canonical "
                        "ordered cumulative form; run --migrate."
                    )
            except StateError as exc:
                failures.append(str(exc))
        created_with = state.get("created_with")
        if (
            not isinstance(created_with, str)
            or not created_with.startswith("design-dna ")
            or not SEMVER.fullmatch(created_with.removeprefix("design-dna "))
        ):
            failures.append("state.json has an invalid created_with value.")
        created = date.fromisoformat(str(state.get("created", "")))
        if created > date.today():
            failures.append("state.json created date may not be in the future.")
        raw_records = state.get("records")
        if (
            not isinstance(raw_records, list)
            or not raw_records
            or not all(isinstance(item, str) for item in raw_records)
            or len(raw_records) != len(set(raw_records))
        ):
            failures.append(
                "state.json records must be a nonempty, unique list of "
                "strings."
            )
        else:
            records = raw_records
        unknown = set(records) - set(RECORD_TEMPLATES)
        if unknown:
            failures.append(f"state.json lists unknown records: {', '.join(sorted(unknown))}.")
        if records and state_profiles:
            if (
                state_profiles == ("quick",)
                and set(records).issubset(PROFILES["quick"])
            ):
                inferred_profiles = state_profiles
            else:
                inferred_profiles = merged_assurance_profiles(
                    list(state_profiles),
                    [],
                    records,
                )
            if inferred_profiles != state_profiles:
                failures.append(
                    "state.json assurance_profiles omit capabilities implied "
                    "by the listed records; run --migrate."
                )
        contract = state.get("evidence_contract")
        if contract is None:
            evidence_capabilities = inferred_evidence_capabilities(
                state_profiles
            )
            if state_profiles and state_profiles != ("quick",):
                failures.append(
                    "state.json needs the current reference-sourced direction "
                    "contract; run --migrate."
                )
        elif state_profiles:
            try:
                (
                    evidence_capabilities,
                    extension_records,
                ) = validate_evidence_contract(contract, state_profiles)
            except StateError as exc:
                failures.append(str(exc))
        for capability in evidence_capabilities:
            missing_records = missing_capability_records(capability, records)
            if missing_records:
                failure = (
                    f"Applicable evidence capability {capability} requires records: "
                    + ", ".join(missing_records)
                    + "."
                )
                profile_command = CAPABILITY_PROFILE_COMMANDS.get(capability)
                if profile_command is not None:
                    failure += f" Reinitialize with {profile_command}."
                failures.append(failure)
        for record in records:
            if record not in RECORD_TEMPLATES:
                continue
            filename = RECORD_TEMPLATES[record][0]
            if not (state_root / filename).is_file():
                failures.append(f"Missing selected record: {state_root / filename}")
        expected = f"design-dna {current_version}"
        if state.get("created_with") != expected:
            warnings.append(f"State was created with {state.get('created_with', 'unknown')}; current package is {expected}.")
    except (StateError, ValueError) as exc:
        failures.append(f"Invalid state.json: {exc}")

    listed_files = {
        RECORD_TEMPLATES[record][0]
        for record in records
        if record in RECORD_TEMPLATES
    }
    for record, (filename, _) in RECORD_TEMPLATES.items():
        if (state_root / filename).is_file() and filename not in listed_files:
            failures.append(
                f"Packaged record {filename} exists but state.json does not list {record}."
            )

    for filename in FRONTMATTER_FILES:
        path = state_root / filename
        if not path.is_file():
            continue
        try:
            meta, body = read_frontmatter_document(path)
            required = {"schema_version", "created_with", "classification"}
            missing = sorted(required - set(meta))
            if missing:
                failures.append(f"{filename} is missing frontmatter fields: {', '.join(missing)}.")
            if meta.get("schema_version") != str(RECORD_SCHEMA_VERSION):
                failures.append(f"{filename} has an unsupported schema_version.")
            if meta.get("classification") not in CLASSIFICATIONS:
                failures.append(f"{filename} has an invalid classification.")
            created_with = meta.get("created_with", "")
            if (
                not created_with.startswith("design-dna ")
                or not SEMVER.fullmatch(created_with.removeprefix("design-dna "))
            ):
                failures.append(f"{filename} has an invalid created_with value.")
            if "__DESIGN_DNA_VERSION__" in path.read_text(encoding="utf-8"):
                failures.append(f"{filename} contains an unresolved template token.")
            if (
                filename == "visual-review.md"
                and meta.get("findings_contract")
                != VISUAL_FINDINGS_CONTRACT
            ):
                failures.append(
                    "visual-review.md must declare findings_contract "
                    f"{VISUAL_FINDINGS_CONTRACT}; run --migrate for a "
                    "schema-1/Design DNA 2.2 review."
                )
            if filename in SUBSTANTIVE_RECORDS:
                status = meta.get("record_status")
                if status not in RECORD_STATUSES:
                    failures.append(
                        f"{filename} must declare record_status as draft or complete; "
                        "run --migrate for an older record."
                    )
                elif status == "draft":
                    stale_completion = sorted(
                        COMPLETE_RECORD_FIELDS & set(meta)
                    )
                    if stale_completion:
                        failures.append(
                            f"{filename} is draft but retains completion metadata: "
                            + ", ".join(stale_completion)
                            + "."
                        )
                    warnings.append(
                        f"{filename} remains draft and cannot support a completion "
                        "or release-readiness claim."
                    )
                else:
                    record_failures = completed_record_failures(
                        project,
                        path,
                        SUBSTANTIVE_RECORDS[filename],
                        meta,
                        body,
                        required_assurance_profiles=state_profiles,
                        required_evidence_capabilities=evidence_capabilities,
                    )
                    failures.extend(
                        f"Invalid complete {filename}: {item}."
                        for item in record_failures
                    )
            if filename == "user-validation.md":
                missing_research_fields = sorted(
                    USER_VALIDATION_FRONTMATTER_FIELDS - set(meta)
                )
                if missing_research_fields:
                    failures.append(
                        "user-validation.md is missing privacy-control "
                        "frontmatter fields: "
                        + ", ".join(missing_research_fields)
                        + "."
                    )
                empty_research_fields = sorted(
                    field
                    for field in USER_VALIDATION_FRONTMATTER_FIELDS & set(meta)
                    if not meta.get(field, "").strip()
                )
                if empty_research_fields:
                    failures.append(
                        "user-validation.md has empty privacy-control "
                        "frontmatter fields: "
                        + ", ".join(empty_research_fields)
                        + "."
                    )
                if meta.get("classification") != "restricted-research":
                    failures.append(
                        "user-validation.md classification must be "
                        "restricted-research."
                    )
                deletion_status = meta.get("deletion_status")
                if (
                    deletion_status is not None
                    and deletion_status
                    not in USER_VALIDATION_DELETION_STATUSES
                ):
                    failures.append(
                        "user-validation.md has an invalid deletion_status."
                    )
                pending_controls = sorted(
                    field
                    for field in USER_VALIDATION_FRONTMATTER_FIELDS
                    if meta.get(field, "").strip().lower() == "pending"
                )
                if pending_controls:
                    warnings.append(
                        "user-validation.md privacy controls remain pending: "
                        + ", ".join(pending_controls)
                        + ". Complete them before collecting participant data."
                    )
        except StateError as exc:
            failures.append(str(exc))

    user_validation_path = state_root / "user-validation.md"
    if user_validation_path.is_file():
        ignore_path = state_root / ".gitignore"
        if not ignore_path.is_file():
            failures.append(
                ".design-dna/.gitignore is required to protect "
                "user-validation.md from accidental commits."
            )
        else:
            try:
                ignore_text = ignore_path.read_text(encoding="utf-8")
                required_ignore_block = (
                    "\n".join(STATE_PRIVACY_IGNORE_LINES) + "\n"
                )
                if not ignore_text.endswith(required_ignore_block):
                    failures.append(
                        ".design-dna/.gitignore must end with the packaged "
                        "privacy-safeguard block so later negations cannot "
                        "re-enable restricted research files."
                    )
            except (OSError, UnicodeError) as exc:
                failures.append(
                    f"Unable to validate .design-dna/.gitignore: {exc}"
                )
        tracked_restricted, tracking_warning = restricted_git_tracking(
            project,
            state_root,
        )
        if tracked_restricted:
            failures.append(
                "Restricted Design DNA research is already tracked by Git: "
                + ", ".join(tracked_restricted)
                + ". Remove it from the Git index before collecting or "
                "retaining participant data; .gitignore cannot protect "
                "files that are already tracked."
            )
        if tracking_warning:
            warnings.append(tracking_warning)

    assets_path = state_root / "assets.yml"
    if assets_path.is_file():
        try:
            warnings.extend(
                validate_asset_manifest(
                    assets_path,
                    current_version,
                    project,
                )
            )
        except StateError as exc:
            failures.append(f"Invalid assets.yml: {exc}")
    route_family_path = state_root / "route-family.json"
    if route_family_path.is_file():
        try:
            route_family, route_family_errors = validate_route_family_record(
                route_family_path,
            )
            failures.extend(
                "Invalid route-family.json: "
                f"{item['path']} {item['code']}: {item['message']}"
                for item in route_family_errors
            )
            expected = f"design-dna {current_version}"
            if (
                isinstance(route_family, dict)
                and route_family.get("created_with") != expected
            ):
                warnings.append(
                    "route-family.json was created with "
                    f"{route_family.get('created_with', 'unknown')}; "
                    f"current package is {expected}."
                )
        except StateError as exc:
            failures.append(f"Invalid route-family.json: {exc}")
    batch_range_path = state_root / "batch-range.json"
    if batch_range_path.is_file():
        try:
            _batch_range, batch_range_errors = validate_batch_range_record(
                batch_range_path,
            )
            failures.extend(
                "Invalid batch-range.json: "
                f"{item['path']} {item['code']}: {item['message']}"
                for item in batch_range_errors
            )
        except StateError as exc:
            failures.append(f"Invalid batch-range.json: {exc}")
    project_contrast_path = state_root / "project-contrast.json"
    if project_contrast_path.is_file():
        try:
            project_contrast, project_contrast_errors = (
                validate_project_contrast_record(project_contrast_path)
            )
            failures.extend(
                "Invalid project-contrast.json: "
                f"{entry['path']} {entry['code']}: {entry['message']}"
                for entry in project_contrast_errors
            )
            expected = f"design-dna {current_version}"
            if (
                isinstance(project_contrast, dict)
                and project_contrast.get("created_with") != expected
            ):
                warnings.append(
                    "project-contrast.json was created with "
                    f"{project_contrast.get('created_with', 'unknown')}; "
                    f"current package is {expected}."
                )
            if isinstance(project_contrast, dict):
                if project_contrast.get("record_status") == "draft":
                    warnings.append(
                        "project-contrast.json remains draft: it cannot supply a "
                        "direction, proof, or reviewed recurrence claim."
                    )
                elif "record_status" not in project_contrast:
                    warnings.append(
                        "project-contrast.json predates the explicit lifecycle; "
                        "migrate or replace its unresolved record before treating "
                        "Project Contrast as clean."
                    )
        except StateError as exc:
            failures.append(f"Invalid project-contrast.json: {exc}")
    direction_challenge_path = state_root / "direction-challenge.json"
    if direction_challenge_path.is_file():
        try:
            direction_challenge, direction_challenge_errors = (
                validate_direction_challenge_record(direction_challenge_path)
            )
            failures.extend(
                "Invalid direction-challenge.json: "
                f"{entry['path']} {entry['code']}: {entry['message']}"
                for entry in direction_challenge_errors
            )
            expected = f"design-dna {current_version}"
            if (
                isinstance(direction_challenge, dict)
                and direction_challenge.get("created_with") != expected
            ):
                warnings.append(
                    "direction-challenge.json was created with "
                    f"{direction_challenge.get('created_with', 'unknown')}; "
                    f"current package is {expected}."
                )
            if isinstance(direction_challenge, dict):
                if direction_challenge.get("record_status") == "draft":
                    warnings.append(
                        "direction-challenge.json remains draft: it cannot supply "
                        "three brief-native roots, proof slices, or a reviewed "
                        "Direction Challenge claim."
                    )
                elif "record_status" not in direction_challenge:
                    warnings.append(
                        "direction-challenge.json predates the explicit lifecycle; "
                        "replace its unresolved record before treating Direction "
                        "Challenge as clean."
                    )
        except StateError as exc:
            failures.append(f"Invalid direction-challenge.json: {exc}")
    connected_public_experience_path = (
        state_root / "connected-public-experience.json"
    )
    if connected_public_experience_path.is_file():
        try:
            connected_public_experience, connected_public_errors = (
                validate_connected_public_experience_record(
                    connected_public_experience_path,
                )
            )
            failures.extend(
                "Invalid connected-public-experience.json: "
                f"{entry['path']} {entry['code']}: {entry['message']}"
                for entry in connected_public_errors
            )
            expected = f"design-dna {current_version}"
            if (
                isinstance(connected_public_experience, dict)
                and connected_public_experience.get("created_with") != expected
            ):
                warnings.append(
                    "connected-public-experience.json was created with "
                    f"{connected_public_experience.get('created_with', 'unknown')}; "
                    f"current package is {expected}."
                )
            if isinstance(connected_public_experience, dict):
                if connected_public_experience.get("record_status") == "draft":
                    warnings.append(
                        "connected-public-experience.json remains draft: it cannot "
                        "support a final continuity or functional-path claim."
                    )
        except StateError as exc:
            failures.append(f"Invalid connected-public-experience.json: {exc}")
    rejection_root = state_root / "rejections"
    if rejection_root.exists() and not rejection_root.is_dir():
        failures.append(
            ".design-dna/rejections must be an ordinary directory when present."
        )
    elif rejection_root.is_dir():
        for rejection_path in sorted(rejection_root.glob("*.json")):
            try:
                report = run_owner_rejection_audit(rejection_path, project)
            except StateError as exc:
                failures.append(
                    f"Invalid owner rejection {rejection_path.name}: {exc}"
                )
                continue
            lifecycle = report.get("lifecycle")
            status = (
                lifecycle.get("status") if isinstance(lifecycle, dict) else None
            )
            if report.get("structural_valid") is not True:
                entries = report.get("findings")
                details = " | ".join(
                    f"{entry.get('code', 'unknown')}: {entry.get('message', '')}"
                    for entry in entries
                    if isinstance(entry, dict)
                ) if isinstance(entries, list) else ""
                failures.append(
                    f"Invalid owner rejection {rejection_path.name}"
                    + (f": {details}" if details else ".")
                )
            elif status == "draft":
                warnings.append(
                    f"Owner rejection {rejection_path.name} remains a truthful "
                    "draft and cannot constrain implementation."
                )
            elif report.get("ready") is not True:
                entries = [
                    *(report.get("findings") if isinstance(report.get("findings"), list) else []),
                    *(report.get("gaps") if isinstance(report.get("gaps"), list) else []),
                ]
                details = " | ".join(
                    f"{entry.get('code', 'unknown')}: {entry.get('message', '')}"
                    for entry in entries
                    if isinstance(entry, dict)
                )
                failures.append(
                    f"Owner rejection {rejection_path.name} fails closed"
                    + (f": {details}" if details else ".")
                )
    failures.extend(migration_report_failures(project, state_root))
    for legacy in LEGACY_RECORD_FILES:
        if (state_root / legacy).is_file() and not failures:
            warnings.append(
                f"Legacy record preserved without semantic reinterpretation at "
                f"{state_root / legacy}; its exact bytes are bound by "
                f"{MIGRATION_REPORT}."
            )
    failures.extend(owner_recurrence_integration_failures(state_root))
    return failures, warnings


def validate_state(
    project: Path,
    current_version: str,
) -> tuple[list[str], list[str]]:
    return validate_state_root(
        project / ".design-dna",
        project,
        current_version,
    )


def owner_recurrence_integration_failures(
    state_root: Path,
    *,
    require_resolved: bool = False,
) -> list[str]:
    """Keep an owner recurrence escalation paired, capable, and non-orphaned.

    The trigger lives in the two canonical JSON records rather than in
    ``state.json``. Consequently either record can declare it, and a state
    check must treat that declaration as activating the complete paired
    workflow. ``require_resolved`` is reserved for the user-facing state and
    readiness gates: initialization and mutation must be able to create a
    truthful paired draft before its evidence exists. This function
    intentionally reads the supplied state root so the structural invariant
    protects live checks and staged mutations.
    """

    labels = {
        "project-contrast": "Project Contrast",
        "direction-challenge": "Direction Challenge",
    }
    payloads: dict[str, dict[str, object] | None] = {}
    trigger_lists: dict[str, list[str] | None] = {}
    declaring_records: list[str] = []

    for record in OWNER_RECURRENCE_RECORDS:
        path = state_root / RECORD_TEMPLATES[record][0]
        payload: dict[str, object] | None = None
        if path.is_file():
            try:
                candidate = read_json(path)
            except StateError:
                candidate = None
            if isinstance(candidate, dict):
                payload = candidate
        payloads[record] = payload
        scope = payload.get("scope") if isinstance(payload, dict) else None
        raw_triggers = scope.get("trigger") if isinstance(scope, dict) else None
        triggers = (
            raw_triggers
            if isinstance(raw_triggers, list)
            and all(isinstance(trigger, str) for trigger in raw_triggers)
            else None
        )
        trigger_lists[record] = triggers
        if triggers is not None and OWNER_RECURRENCE_TRIGGER in triggers:
            declaring_records.append(record)

    if not declaring_records:
        return []

    failures: list[str] = []
    missing_files = [
        record
        for record in OWNER_RECURRENCE_RECORDS
        if payloads[record] is None
    ]
    if missing_files:
        failures.append(
            "Active owner-recurrence-requirement is orphaned: both paired "
            "records must exist; missing "
            + ", ".join(RECORD_TEMPLATES[record][0] for record in missing_files)
            + "."
        )

    state: dict[str, object] | None = None
    manifest_path = state_root / "state.json"
    if manifest_path.is_file():
        try:
            candidate_state = read_json(manifest_path)
        except StateError:
            candidate_state = None
        if isinstance(candidate_state, dict):
            state = candidate_state
    if state is None:
        failures.append(
            "Active owner-recurrence-requirement cannot be kept non-orphaned "
            "without a readable state.json that selects its paired records and "
            "capabilities."
        )
    else:
        raw_records = state.get("records")
        records = (
            set(raw_records)
            if isinstance(raw_records, list)
            and all(isinstance(record, str) for record in raw_records)
            else set()
        )
        missing_records = sorted(set(OWNER_RECURRENCE_RECORDS) - records)
        if missing_records:
            failures.append(
                "Active owner-recurrence-requirement is orphaned: state.json "
                "must list both paired records; missing "
                + ", ".join(missing_records)
                + "."
            )

        evidence_contract = state.get("evidence_contract")
        raw_capabilities = (
            evidence_contract.get("applicable_capabilities")
            if isinstance(evidence_contract, dict)
            else None
        )
        capabilities = (
            set(raw_capabilities)
            if isinstance(raw_capabilities, list)
            and all(isinstance(capability, str) for capability in raw_capabilities)
            else set()
        )
        missing_capabilities = sorted(
            OWNER_RECURRENCE_CAPABILITIES - capabilities
        )
        if missing_capabilities:
            failures.append(
                "Active owner-recurrence-requirement requires both applicable "
                "evidence capabilities in state.json; missing "
                + ", ".join(missing_capabilities)
                + "."
            )

    missing_triggers = [
        record
        for record in OWNER_RECURRENCE_RECORDS
        if trigger_lists[record] is None
        or OWNER_RECURRENCE_TRIGGER not in trigger_lists[record]
    ]
    if missing_triggers:
        failures.append(
            "Active owner-recurrence-requirement has inconsistent paired "
            "triggers: it must be declared in both project-contrast.json and "
            "direction-challenge.json; missing from "
            + ", ".join(RECORD_TEMPLATES[record][0] for record in missing_triggers)
            + "."
        )

    if require_resolved:
        for record in OWNER_RECURRENCE_RECORDS:
            payload = payloads[record]
            triggers = trigger_lists[record]
            if (
                isinstance(payload, dict)
                and triggers is not None
                and OWNER_RECURRENCE_TRIGGER in triggers
                and payload.get("record_status") in {None, "draft"}
            ):
                failures.append(
                    "Active owner-recurrence-requirement is still a "
                    f"{labels[record]} draft: record its project-derived evidence "
                    "before treating state as clean."
                )
    return failures


def owner_pattern_contract_failures(
    project: Path,
    *,
    phase: str,
) -> list[str]:
    """Fail closed when the explicit owner-pattern trigger is unresolved.

    The trigger is project-local and opt-in. This prevents a host owner's
    contract from changing portable package tests or unrelated client work.
    Once either paired recurrence record declares it, both records must carry
    it and the external contract plus project review become binding.
    """

    if phase not in {"state", "prebuild", "ready"}:
        return [f"Unsupported owner-pattern audit phase: {phase}"]
    state_root = project / ".design-dna"
    declaring: list[str] = []
    missing_or_inconsistent: list[str] = []
    for record in OWNER_RECURRENCE_RECORDS:
        path = state_root / RECORD_TEMPLATES[record][0]
        triggers: list[str] | None = None
        if path.is_file():
            try:
                payload = read_json(path)
            except StateError:
                payload = None
            scope = payload.get("scope") if isinstance(payload, dict) else None
            raw = scope.get("trigger") if isinstance(scope, dict) else None
            if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
                triggers = raw
        if triggers is not None and OWNER_PATTERN_TRIGGER in triggers:
            declaring.append(record)
        else:
            missing_or_inconsistent.append(record)

    if not declaring:
        return []
    failures: list[str] = []
    if missing_or_inconsistent:
        failures.append(
            "Active owner-pattern-contract has inconsistent paired triggers: "
            "it must be declared in both project-contrast.json and "
            "direction-challenge.json; missing from "
            + ", ".join(
                RECORD_TEMPLATES[record][0]
                for record in missing_or_inconsistent
            )
            + "."
        )
        return failures

    validator_path = Path(__file__).with_name("owner_pattern_audit.py")
    if not validator_path.is_file() or is_reparse(validator_path):
        return [
            "Active owner-pattern-contract cannot be checked because the "
            "bundled owner_pattern_audit.py is missing or redirected."
        ]
    try:
        module = load_bundled_source_module(
            "_design_dna_owner_pattern_audit",
            validator_path,
        )
        audit = getattr(module, "audit_project")
        report = audit(project.resolve(strict=True), phase=phase)
    except (AttributeError, OSError, TypeError, UnicodeError, ValueError) as exc:
        return [f"Owner-pattern contract audit failed to execute: {exc}"]
    if (
        not isinstance(report, dict)
        or report.get("automatic_aesthetic_pass") is not False
        or report.get("phase") != phase
        or not isinstance(report.get("contract_active"), bool)
        or not isinstance(report.get("structural_valid"), bool)
        or not isinstance(report.get("ready"), bool)
        or not isinstance(report.get("findings"), list)
        or not isinstance(report.get("gaps"), list)
    ):
        return [
            "The bundled owner-pattern auditor returned an unsupported result."
        ]
    if report.get("ready") is True:
        return []
    entries = [*report["findings"], *report["gaps"]]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("code", "unknown"))
        message = str(entry.get("message", "Owner-pattern review is incomplete."))
        failures.append(f"Owner-pattern {phase} gate {code}: {message}")
    if not failures:
        failures.append(f"Owner-pattern {phase} gate is not ready.")
    return failures


def direction_challenge_final_build_binding_failures(
    state_root: Path,
    project: Path,
) -> list[str]:
    """Keep a reviewed Direction Challenge attached to the final build.

    The canonical Challenge record deliberately proves roots before broad
    implementation.  That is valuable, but it must not silently become a
    claim about a later build.  This state-level bridge therefore accepts an
    exact selected-proof/final-build match, or a final-review-bound delta
    ledger that names and reviews the changed decisions.  It does not change
    the Direction Challenge schema or treat prose alone as a bridge.
    """

    challenge_path = state_root / "direction-challenge.json"
    review_path = state_root / "visual-review.md"
    if not challenge_path.is_file() or not review_path.is_file():
        return []
    try:
        challenge = read_json(challenge_path)
        review_meta, review_body = read_frontmatter_document(review_path)
    except StateError as exc:
        return [f"Direction Challenge proof-to-build binding is unreadable: {exc}"]
    if (
        not isinstance(challenge, dict)
        or challenge.get("record_status") != "reviewed"
        or review_meta.get("record_status") != "complete"
    ):
        # Draft, proof-ready, and incomplete records already have their own
        # truthful readiness failures. Do not manufacture an extra bridge claim.
        return []
    selection = challenge.get("selection")
    proofs = challenge.get("proof_slices")
    if not isinstance(selection, dict) or not isinstance(proofs, list):
        return [
            "Reviewed Direction Challenge has no readable selection/proof "
            "boundary for final-build verification"
        ]
    chosen_root = selection.get("chosen_root_id")
    selected_builds = {
        proof.get("build_id")
        for proof in proofs
        if isinstance(proof, dict)
        and proof.get("root_id") == chosen_root
        and isinstance(proof.get("build_id"), str)
    }
    if not isinstance(chosen_root, str) or not selected_builds:
        return [
            "Reviewed Direction Challenge has no selected-root proof build "
            "to bind to the final visual review"
        ]
    final_build = (markdown_label_value(review_body, "Build or artifact ID") or "").strip()
    if not non_placeholder(final_build):
        return [
            "Final visual-review build identity is missing for Direction "
            "Challenge proof-to-build verification"
        ]
    if final_build in selected_builds:
        return []

    label = "Direction Challenge proof-to-build delta evidence"
    value = (markdown_label_value(review_body, label) or "").strip()
    if not value:
        return [
            "Final visual-review build differs from the selected Direction "
            "Challenge proof build; bind a completed proof-to-build delta "
            "artifact in the visual-review record"
        ]
    normalized = value.casefold().replace("not applicable", "not-applicable")
    if normalized.startswith("not-applicable"):
        return [
            "Direction Challenge proof-to-build delta cannot be not-applicable "
            "when final visual-review build differs from selected proof build"
        ]
    artifact, artifact_failures = bound_artifact(
        value,
        project=project,
        record_path=review_path,
        label="Direction Challenge proof-to-build delta evidence",
    )
    failures = list(artifact_failures)
    if artifact is None or artifact_failures:
        return failures
    if artifact.suffix.casefold() not in {".md", ".txt", ".json", ".log"}:
        return [
            *failures,
            "Direction Challenge proof-to-build delta must be a UTF-8 Markdown, "
            "text, JSON, or log artifact",
        ]
    try:
        delta = artifact.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [
            *failures,
            f"Direction Challenge proof-to-build delta is not readable UTF-8: {exc}",
        ]
    sections = markdown_sections(delta)
    required_sections = {
        "Identity",
        "Implementation delta",
        "Reconciliation",
    }
    missing_sections = sorted(required_sections - set(sections))
    if missing_sections:
        failures.append(
            "Direction Challenge proof-to-build delta is missing required "
            "reviewed-decision sections: " + ", ".join(missing_sections)
        )
        return failures
    if any(len(sections[heading].strip()) < 24 for heading in required_sections):
        failures.append(
            "Direction Challenge proof-to-build delta has an empty reviewed "
            "identity, implementation, or reconciliation section"
        )
    selected_value = (
        markdown_label_value(delta, "Selected candidate and proof build ID")
        or ""
    )
    final_value = (
        markdown_label_value(delta, "Implementation build, commit, or artifact ID")
        or ""
    )
    missing_selected = sorted(
        build for build in selected_builds if build not in selected_value
    )
    if missing_selected:
        failures.append(
            "Direction Challenge proof-to-build delta must name every exact "
            "selected proof build: " + ", ".join(missing_selected)
        )
    if final_build not in final_value:
        failures.append(
            "Direction Challenge proof-to-build delta must name the exact "
            "final visual-review build"
        )
    headers, rows = markdown_first_table(sections["Implementation delta"])
    expected_headers = (
        "Decision ID",
        "Source/content/asset/system authority",
        "Implementation path and symbol",
        "Relevant adaptation or state contract",
        "Permitted deviation and reason",
        "Current evidence",
        "Disposition and owner",
    )
    if headers != expected_headers or not rows:
        failures.append(
            "Direction Challenge proof-to-build delta needs at least one "
            "reviewed changed-decision row using the packaged ledger contract"
        )
    elif any(
        len(row) != len(expected_headers) or any(not non_placeholder(cell) for cell in row)
        for row in rows
    ):
        failures.append(
            "Direction Challenge proof-to-build delta contains an incomplete "
            "changed-decision row"
        )
    return failures


def final_build_evidence_binding_failures(
    state_root: Path,
    *,
    project_contrast_report: dict[str, object] | None = None,
    connected_public_experience_report: dict[str, object] | None = None,
) -> list[str]:
    """Require every final-evidence lane to name one reviewed build.

    Each specialist auditor verifies its own files, captures, and attestations,
    but those local checks are not enough if the records silently describe
    different website builds. A completed visual review is the canonical
    final-build identity. Completed Connected Public Experience closure and
    any concrete Project Contrast candidate must bind that same identity,
    including the build identities surfaced by their validated audit reports.

    Direction Challenge proof builds are deliberately excluded: they precede
    broad implementation and are reconciled through the separate
    proof-to-build delta contract above. User validation can also describe an
    earlier prototype, so it is not converted into an exact-build rule here.
    """

    review_path = state_root / "visual-review.md"
    if not review_path.is_file():
        return []
    try:
        review_meta, review_body = read_frontmatter_document(review_path)
    except StateError as exc:
        return [f"Final-build evidence binding is unreadable: {exc}"]
    if review_meta.get("record_status") != "complete":
        return []

    canonical_build = (
        markdown_label_value(review_body, "Build or artifact ID") or ""
    ).strip()
    observed: list[tuple[str, str]] = []

    connected_path = state_root / "connected-public-experience.json"
    if connected_path.is_file():
        try:
            connected = read_json(connected_path)
        except StateError as exc:
            return [f"Final-build Connected Public Experience binding is unreadable: {exc}"]
        if isinstance(connected, dict):
            closure = connected.get("final_closure")
            if isinstance(closure, dict) and closure.get("status") == "complete":
                reviewed_build = closure.get("reviewed_build_id")
                if isinstance(reviewed_build, str) and reviewed_build.strip():
                    observed.append(
                        (
                            "connected-public-experience.json "
                            "final_closure.reviewed_build_id",
                            reviewed_build.strip(),
                        )
                    )

    if isinstance(connected_public_experience_report, dict):
        report_evidence = connected_public_experience_report.get("evidence")
        verified = (
            report_evidence.get("verified")
            if isinstance(report_evidence, dict)
            else None
        )
        if isinstance(verified, list):
            for entry in verified:
                if not isinstance(entry, dict):
                    continue
                build_id = entry.get("build_id")
                evidence_id = entry.get("id", "unknown")
                if isinstance(build_id, str) and build_id.strip():
                    observed.append(
                        (
                            "Connected Public Experience verified evidence "
                            f"{evidence_id}",
                            build_id.strip(),
                        )
                    )

    contrast_path = state_root / "project-contrast.json"
    if contrast_path.is_file():
        try:
            contrast = read_json(contrast_path)
        except StateError as exc:
            return [f"Final-build Project Contrast binding is unreadable: {exc}"]
        if isinstance(contrast, dict):
            evidence = contrast.get("evidence")
            candidate = (
                evidence.get("candidate_build")
                if isinstance(evidence, dict)
                else None
            )
            candidate_id = candidate.get("id") if isinstance(candidate, dict) else None
            if isinstance(candidate_id, str) and candidate_id.strip():
                observed.append(
                    (
                        "project-contrast.json evidence.candidate_build.id",
                        candidate_id.strip(),
                    )
                )

    if isinstance(project_contrast_report, dict):
        report_evidence = project_contrast_report.get("evidence")
        capture_coverage = (
            report_evidence.get("capture_coverage")
            if isinstance(report_evidence, dict)
            else None
        )
        candidate_id = (
            capture_coverage.get("candidate_build_id")
            if isinstance(capture_coverage, dict)
            else None
        )
        if isinstance(candidate_id, str) and candidate_id.strip():
            observed.append(
                (
                    "Project Contrast verified capture coverage",
                    candidate_id.strip(),
                )
            )

    if not observed:
        return []
    if not non_placeholder(canonical_build):
        return [
            "Final-build evidence lanes are populated, but completed "
            "visual-review.md has no canonical Build or artifact ID."
        ]

    failures: list[str] = []
    seen: set[tuple[str, str]] = set()
    for label, build_id in observed:
        identity = (label, build_id)
        if identity in seen:
            continue
        seen.add(identity)
        if build_id != canonical_build:
            failures.append(
                "Final-build evidence drift: "
                f"{label} binds {build_id}, but completed visual-review.md "
                f"binds {canonical_build}."
            )
    return failures


def asset_prebuild_failures(
    path: Path,
    *,
    require_visual: bool,
) -> list[str]:
    """Require at least one implementation-usable material asset.

    Release approval remains a later gate.  This narrower phase check prevents
    an asset-led direction from scaling while its manifest is still empty or
    contains only unresolved placeholders.
    """

    try:
        payload = parse_strict_yaml_subset(
            path.read_text(encoding="utf-8"),
            path=path,
        )
    except (OSError, UnicodeError, StateError) as exc:
        return [f"Asset-led prebuild manifest is unreadable: {exc}"]
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list) or not assets:
        return [
            "Asset-led prebuild requires a nonempty assets.yml; a physical or "
            "explicitly photo-led brief cannot scale from an empty media plan."
        ]

    usable: list[dict[str, object]] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        asset_type = asset.get("asset_type")
        if require_visual and asset_type not in {"image", "video"}:
            continue
        accessibility = asset.get("accessibility")
        delivery = asset.get("delivery")
        usage = asset.get("usage_locations")
        has_source = non_placeholder(str(asset.get("source_path", ""))) or non_placeholder(
            str(asset.get("source_url", ""))
        )
        rights_ready = (
            asset.get("publication_status") not in {"planned-public", "public"}
            or non_placeholder(str(asset.get("license_or_terms", "")))
        )
        if (
            asset.get("publication_status") != "prohibited"
            and asset.get("factual_status") != "placeholder"
            and has_source
            and rights_ready
            and isinstance(usage, list)
            and bool(usage)
            and non_placeholder(str(asset.get("content_job", "")))
            and isinstance(accessibility, dict)
            and accessibility.get("treatment") != "pending"
            and isinstance(delivery, dict)
            and non_placeholder(str(delivery.get("responsive_behavior", "")))
        ):
            usable.append(asset)
    if usable:
        return []
    kind = "image or video" if require_visual else "material"
    return [
        "Asset-led prebuild has no implementation-usable "
        f"{kind} asset with a bound source, public-use rights when applicable, "
        "content role, usage location, accessibility treatment, and responsive "
        "behavior."
    ]


def prebuild_scaffold_text(value: object) -> bool:
    """Recognize packaged planning prompts that must not authorize a build."""

    if not isinstance(value, str):
        return False
    normalized = " ".join(value.strip().casefold().split())
    return normalized.startswith(
        (
            "replace with",
            "replace-with",
            "replace this",
            "describe ",
            "explain ",
            "record ",
            "resolve ",
            "keep destination labels",
            "no implementation has started",
            "this neutral template",
        )
    )


def scaffold_json_paths(value: object, *, path: str = "$") -> list[str]:
    paths: list[str] = []
    if prebuild_scaffold_text(value):
        paths.append(path)
    elif isinstance(value, dict):
        for key, item in value.items():
            paths.extend(scaffold_json_paths(item, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(scaffold_json_paths(item, path=f"{path}[{index}]"))
    return paths


def route_family_prebuild_failures(path: Path) -> list[str]:
    """Require a resolved route-family brief without demanding postbuild review."""

    try:
        payload, errors = validate_route_family_record(path)
    except StateError as exc:
        return [f"Route-family prebuild record is unreadable: {exc}"]
    if not isinstance(payload, dict):
        return ["Route-family prebuild record must contain an object."]
    failures: list[str] = []
    if errors:
        failures.append("Route-family prebuild record is structurally invalid.")
    scaffold_paths = scaffold_json_paths(payload)
    if scaffold_paths:
        preview = ", ".join(scaffold_paths[:12])
        suffix = "" if len(scaffold_paths) <= 12 else ", ..."
        failures.append(
            "Route-family prebuild still contains packaged scaffold language at "
            f"{preview}{suffix}."
        )
    routes = payload.get("routes")
    if not isinstance(routes, list) or len(routes) < 2:
        failures.append(
            "Route-family prebuild needs at least two resolved routes for a "
            "meaningful body-level comparison."
        )
        return failures
    project = path.parent.parent
    manifest_path = path.parent / "route-manifest.json"
    try:
        manifest = read_json(manifest_path)
    except StateError as exc:
        failures.append(f"Route-family needs the authoritative route manifest: {exc}")
        manifest = None
    manifest_routes: dict[str, dict[str, object]] = {}
    if isinstance(manifest, dict):
        manifest_failures = route_manifest_payload_failures(manifest)
        manifest_failures.extend(route_manifest_reference_failures(manifest, project=project))
        failures.extend(f"Route-family manifest: {failure}" for failure in manifest_failures)
        manifest_routes = {
            str(route.get("key")): route
            for route in manifest.get("routes", [])
            if isinstance(route, dict)
        }
        route_ids = {
            str(route.get("id")) for route in routes if isinstance(route, dict)
        }
        if route_ids != set(manifest_routes):
            failures.append(
                "Route-family routes must equal every authoritative route-manifest key."
            )
    for index, route in enumerate(routes):
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("id", f"index-{index}"))
        manifested = manifest_routes.get(route_id)
        source_mapping = route.get("source_mapping")
        if manifested is None:
            failures.append(f"Route-family route {route_id!r} is not authoritative.")
        else:
            expected_path = normalize_safe_route_path(
                urlsplit(str(manifested.get("url") or "")).path or "/"
            )
            declared_path = normalize_safe_route_path(str(route.get("path") or ""))
            expected_mapping = {
                "rank": manifested.get("mapped_reference_rank"),
                "id": manifested.get("mapped_reference_id"),
                "observation": manifested.get("mapped_reference_observation"),
                "sha256": manifested.get("mapped_reference_sha256"),
            }
            if expected_path is None or declared_path is None or declared_path != expected_path:
                failures.append(f"Route-family route {route_id!r} path differs from the route manifest.")
            if source_mapping != expected_mapping:
                failures.append(f"Route-family route {route_id!r} source_mapping differs from the exact manifested observation.")
            mapped_state_ids = {
                str(state.get("mapped_reference_state_id"))
                for state in manifested.get("states", [])
                if isinstance(state, dict)
            }
            components = route.get("component_sources")
            if not isinstance(components, list) or not components:
                failures.append(
                    f"Route-family route {route_id!r} needs at least one exact component source mapping."
                )
            else:
                for component_index, component in enumerate(components, start=1):
                    if not isinstance(component, dict):
                        failures.append(
                            f"Route-family route {route_id!r} component {component_index} is invalid."
                        )
                        continue
                    component_mapping = {
                        "rank": component.get("source_rank"),
                        "id": component.get("source_id"),
                        "observation": component.get("source_observation"),
                        "sha256": component.get("source_sha256"),
                    }
                    if (
                        component_mapping != expected_mapping
                        or component.get("source_state_id") not in mapped_state_ids
                        or not non_placeholder(str(component.get("component") or ""))
                        or not non_placeholder(str(component.get("transfer") or ""))
                    ):
                        failures.append(
                            f"Route-family route {route_id!r} component {component_index} is not bound to its exact reference observation/source state."
                        )
            decisions = route.get("observable_decisions")
            if not isinstance(decisions, list) or not decisions:
                failures.append(
                    f"Route-family route {route_id!r} needs at least one exact observable-decision source mapping."
                )
            else:
                for decision_index, decision in enumerate(decisions, start=1):
                    if not isinstance(decision, dict):
                        failures.append(
                            f"Route-family route {route_id!r} decision {decision_index} is invalid."
                        )
                        continue
                    decision_mapping = {
                        "rank": decision.get("source_rank"),
                        "id": decision.get("source_id"),
                        "observation": decision.get("source_observation"),
                        "sha256": decision.get("source_sha256"),
                    }
                    if (
                        decision_mapping != expected_mapping
                        or decision.get("source_state_id") not in mapped_state_ids
                    ):
                        failures.append(
                            f"Route-family route {route_id!r} decision {decision_index} is not bound to its exact reference observation/source state."
                        )
        differences = route.get("deliberate_differences")
        if (
            not isinstance(differences, list)
            or not differences
            or any(not non_placeholder(str(item)) for item in differences)
        ):
            failures.append(
                f"Route-family route {route_id!r} must name at least one "
                "project-specific body-level difference before implementation."
            )
        capture = route.get("capture_requirements")
        viewports = (
            capture.get("viewports") if isinstance(capture, dict) else None
        )
        if (
            not isinstance(viewports, list)
            or not isinstance(manifest, dict)
            or viewports
            != [
                {"id": viewport.get("name"), "width": viewport.get("width")}
                for viewport in manifest.get("viewports", [])
                if isinstance(viewport, dict)
            ]
            or any(
                not isinstance(viewport, dict)
                or not isinstance(viewport.get("width"), int)
                or isinstance(viewport.get("width"), bool)
                or viewport["width"] <= 0
                or prebuild_scaffold_text(viewport.get("id"))
                for viewport in viewports
            )
        ):
            failures.append(
                f"Route-family route {route_id!r} needs at least two resolved, "
                "project-derived positive capture widths before implementation."
            )
    return failures


def batch_range_prebuild_failures(path: Path) -> list[str]:
    """Reject an untouched Batch Study plan before unrelated builds begin."""

    try:
        payload, errors = validate_batch_range_record(path)
    except StateError as exc:
        return [f"Batch Study prebuild record is unreadable: {exc}"]
    if not isinstance(payload, dict):
        return ["Batch Study prebuild record must contain an object."]
    failures: list[str] = []
    if errors:
        failures.append("Batch Study prebuild record is structurally invalid.")
    scaffold_paths = scaffold_json_paths(payload)
    if scaffold_paths:
        preview = ", ".join(scaffold_paths[:12])
        suffix = "" if len(scaffold_paths) <= 12 else ", ..."
        failures.append(
            "Batch Study prebuild still contains packaged scaffold language at "
            f"{preview}{suffix}."
        )
    study = payload.get("study")
    viewports = (
        study.get("viewport_classes") if isinstance(study, dict) else None
    )
    if (
        not isinstance(viewports, list)
        or len(viewports) < 2
        or any(
            not isinstance(viewport, dict)
            or not isinstance(viewport.get("width"), int)
            or isinstance(viewport.get("width"), bool)
            or viewport["width"] <= 0
            or not isinstance(viewport.get("height"), int)
            or isinstance(viewport.get("height"), bool)
            or viewport["height"] <= 0
            for viewport in viewports
        )
    ):
        failures.append(
            "Batch Study prebuild needs at least two resolved positive viewport "
            "width/height pairs before implementation."
        )
    sites = payload.get("sites")
    if isinstance(sites, list):
        for index, site in enumerate(sites):
            if not isinstance(site, dict):
                continue
            site_id = str(site.get("id", f"index-{index}"))
            brief = site.get("brief")
            isolation = site.get("implementation_isolation")
            source_packet = (
                isolation.get("source_packet")
                if isinstance(isolation, dict)
                else None
            )
            for label, binding in (
                ("brief", brief),
                ("source packet", source_packet),
            ):
                digest = binding.get("sha256") if isinstance(binding, dict) else None
                bound_path = binding.get("path") if isinstance(binding, dict) else None
                if (
                    not non_placeholder(str(bound_path or ""))
                    or prebuild_scaffold_text(bound_path)
                    or not isinstance(digest, str)
                    or re.fullmatch(r"[0]{64}", digest) is not None
                ):
                    failures.append(
                        f"Batch Study site {site_id!r} needs a resolved {label} "
                        "path and non-placeholder SHA-256 before implementation."
                    )
    return failures


def prebuild_warnings(project: Path) -> list[str]:
    """Name omissions that do not block but usually mean a gate was skipped.

    A standard-or-stronger state with no reference-dossier record is almost
    always a fresh public build that was initialized without the Enterprise
    Candidate profile. That is not an error for a bounded repair or a
    non-public surface, so it warns and names the remedy instead of failing.
    """

    state_root = project / ".design-dna"
    try:
        state = read_json(state_root / "state.json")
    except StateError:
        return []
    if not isinstance(state, dict):
        return []
    profiles = state.get("assurance_profiles")
    records = state.get("records")
    if not isinstance(profiles, list) or not isinstance(records, list):
        return []
    if "reference-dossier" in records:
        return []
    named = {item for item in profiles if isinstance(item, str)}
    if not named or named <= {"quick"}:
        return []
    return [
        "No reference-dossier record is selected. A fresh public website "
        "initializes with --profile enterprise-candidate (or adds "
        "--evidence-capability enterprise-candidate to its existing profile) "
        "so the reference-led direction gate can hold it; a bounded repair or "
        "non-public surface may disregard this warning."
    ]


def prebuild_failures(project: Path) -> list[str]:
    """Return phase gaps that must close before broad implementation.

    Final readiness deliberately remains stricter.  This gate consumes the
    direction records at the moment they matter so a valid template inventory
    cannot be mistaken for permission to build a route family.
    """

    state_root = project / ".design-dna"
    try:
        state = read_json(state_root / "state.json")
    except StateError as exc:
        return [f"Prebuild state is unreadable: {exc}"]
    if not isinstance(state, dict):
        return ["Prebuild requires state.json to contain an object."]
    raw_profiles = state.get("assurance_profiles")
    raw_records = state.get("records")
    if (
        not isinstance(raw_profiles, list)
        or not all(isinstance(item, str) for item in raw_profiles)
        or not isinstance(raw_records, list)
        or not all(isinstance(item, str) for item in raw_records)
    ):
        return [
            "Prebuild requires valid assurance_profiles and records in state.json."
        ]
    try:
        profiles = normalize_assurance_profiles(raw_profiles)
        contract = state.get("evidence_contract")
        if not isinstance(contract, dict):
            raise StateError(
                "prebuild-contract-missing",
                "Prebuild requires the current evidence contract; run --migrate.",
                path=state_root / "state.json",
            )
        capabilities, _extensions = validate_evidence_contract(contract, profiles)
    except StateError as exc:
        return [str(exc)]

    records = set(raw_records)
    capability_set = set(capabilities)
    failures: list[str] = []
    if "direction" not in records:
        failures.append(
            "Prebuild always requires a selected direction.md record; a "
            "capability-only state cannot authorize broad implementation."
        )
    for record in PREBUILD_SUBSTANTIVE_RECORDS:
        if record not in records:
            continue
        filename = RECORD_TEMPLATES[record][0]
        path = state_root / filename
        if not path.is_file():
            failures.append(f"Prebuild record is missing: {filename}.")
            continue
        try:
            metadata, body = read_frontmatter_document(path)
        except StateError as exc:
            failures.append(f"Prebuild record {filename} is unreadable: {exc}")
            continue
        if metadata.get("record_status") != "complete":
            failures.append(
                f"Prebuild {filename} remains draft; broad implementation "
                "requires a hash-bound completed direction-stage record."
            )
            continue
        record_failures = completed_record_failures(
            project,
            path,
            record,
            metadata,
            body,
            required_assurance_profiles=profiles,
            required_evidence_capabilities=capabilities,
        )
        failures.extend(
            f"Prebuild {filename}: {failure}" for failure in record_failures
        )

    if "reference-led-direction" in capability_set:
        dossier_path = state_root / "reference-dossier.md"
        if not dossier_path.is_file():
            failures.append(
                "Reference-led prebuild requires reference-dossier.md and its "
                "first-screen source-fidelity gate."
            )
        else:
            try:
                _dossier_meta, dossier_body = read_frontmatter_document(dossier_path)
            except StateError as exc:
                failures.append(f"Reference-led prebuild dossier is unreadable: {exc}")
            else:
                failures.extend(
                    "Prebuild first-screen gate: " + failure
                    for failure in first_screen_gate_failures(
                        dossier_body,
                        project=project,
                        record_path=dossier_path,
                    )
                )

    if "route-family" in records:
        failures.extend(
            route_family_prebuild_failures(state_root / "route-family.json")
        )
    if "batch-range" in records:
        failures.extend(
            batch_range_prebuild_failures(state_root / "batch-range.json")
        )

    if "project-contrast" in capability_set:
        path = state_root / "project-contrast.json"
        try:
            contrast = read_json(path)
        except StateError as exc:
            failures.append(f"Project Contrast prebuild record is unreadable: {exc}")
        else:
            status = contrast.get("record_status") if isinstance(contrast, dict) else None
            if status not in {"direction-ready", "proof-ready", "reviewed"}:
                failures.append(
                    "Project Contrast must reach direction-ready before broad "
                    "implementation; a draft cannot carry the owner's recurrence boundary."
                )

    if "direction-challenge" in capability_set:
        path = state_root / "direction-challenge.json"
        try:
            challenge = read_json(path)
        except StateError as exc:
            failures.append(f"Direction Challenge prebuild record is unreadable: {exc}")
        else:
            status = challenge.get("record_status") if isinstance(challenge, dict) else None
            if status != "reviewed":
                failures.append(
                    "Direction Challenge must be reviewed before broad implementation: "
                    "two cross-root wide/narrow proofs, a selected-versus-rejected "
                    "decision, and the frozen independent unprimed review are required."
                )
            boundary = (
                challenge.get("implementation_boundary")
                if isinstance(challenge, dict)
                else None
            )
            if (
                not isinstance(boundary, dict)
                or boundary.get("status") != "broad-implementation"
            ):
                failures.append(
                    "Direction Challenge implementation_boundary must explicitly "
                    "advance to broad-implementation after its reviewed proof."
                )

    if "connected-public-experience" in capability_set:
        path = state_root / "connected-public-experience.json"
        try:
            report = run_connected_public_experience_prebuild_audit(
                path,
                project,
                capabilities,
            )
        except StateError as exc:
            failures.append(
                f"Connected Public Experience prebuild record is invalid: {exc}"
            )
        else:
            if report.get("implementation_authorized") is not True:
                entries = [
                    *(
                        report.get("gaps")
                        if isinstance(report.get("gaps"), list)
                        else []
                    ),
                    *(
                        report.get("findings")
                        if isinstance(report.get("findings"), list)
                        else []
                    ),
                ]
                messages = []
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    code = str(entry.get("code", "unknown"))
                    message = str(entry.get("message", "No detail recorded."))
                    messages.append(f"{code}: {message}")
                failures.append(
                    "Connected Public Experience has not authorized broad "
                    "implementation"
                    + (": " + " | ".join(messages) if messages else ".")
                )

    if "asset-led" in capability_set:
        direction_path = state_root / "direction.md"
        require_visual = False
        if direction_path.is_file():
            try:
                _metadata, direction_body = read_frontmatter_document(direction_path)
            except StateError:
                direction_body = ""
            physical = (
                markdown_label_value(direction_body, "Physical or sensory subject")
                or ""
            ).strip().casefold()
            requested = (
                markdown_label_value(
                    direction_body,
                    "Explicit owner request for photos or rich media",
                )
                or ""
            ).strip().casefold()
            require_visual = physical == "yes" or requested == "yes"
        assets_path = state_root / "assets.yml"
        if not assets_path.is_file():
            failures.append(
                "Asset-led prebuild requires .design-dna/assets.yml before broad implementation."
            )
        else:
            failures.extend(
                asset_prebuild_failures(
                    assets_path,
                    require_visual=require_visual,
                )
            )
    return failures


def readiness_failures(project: Path) -> list[str]:
    state_root = project / ".design-dna"
    failures = owner_recurrence_integration_failures(
        state_root,
        require_resolved=True,
    )
    state = read_json(state_root / "state.json")
    if not isinstance(state, dict):
        return [*failures, "state.json must contain an object."]
    profiles = state.get("assurance_profiles")
    records = state.get("records")
    if (
        not isinstance(profiles, list)
        or not profiles
        or not all(isinstance(item, str) for item in profiles)
        or not isinstance(records, list)
        or not all(isinstance(item, str) for item in records)
    ):
        return [
            *failures,
            "state.json must persist valid assurance_profiles and records "
            "before readiness can be checked."
        ]
    try:
        canonical_profiles = normalize_assurance_profiles(profiles)
    except StateError as exc:
        return [*failures, str(exc)]
    contract = state.get("evidence_contract")
    extension_records: list[dict[str, object]] = []
    try:
        if contract is None:
            evidence_capabilities = inferred_evidence_capabilities(
                canonical_profiles
            )
            if canonical_profiles != ("quick",):
                return [
                    *failures,
                    "state.json needs the current reference-sourced direction "
                    "contract before readiness; run --migrate."
                ]
        else:
            (
                evidence_capabilities,
                extension_records,
            ) = validate_evidence_contract(contract, canonical_profiles)
    except StateError as exc:
        return [*failures, str(exc)]
    required_records = tuple(records)
    profile_label = "+".join(canonical_profiles)
    for capability in evidence_capabilities:
        missing_records = missing_capability_records(
            capability,
            required_records,
        )
        if missing_records:
            failures.append(
                f"Applicable evidence capability {capability} requires records: "
                + ", ".join(missing_records)
                + "."
            )
    extension_coverage = {
        target
        for extension in extension_records
        if extension.get("status") in {"complete", "not-applicable"}
        for target in extension.get("applies_to", [])
        if isinstance(target, str)
    }
    for capability in sorted(
        set(evidence_capabilities) - CORE_EVIDENCE_CAPABILITIES
    ):
        if capability not in extension_coverage:
            failures.append(
                f"Project-specific capability {capability} needs a complete or "
                "not-applicable extension record before readiness."
            )
    for record in required_records:
        filename = RECORD_TEMPLATES[record][0]
        path = state_root / filename
        if not path.is_file():
            failures.append(
                f"Listed {profile_label} record is missing: {filename}."
            )
            continue
        if filename in SUBSTANTIVE_RECORDS:
            metadata = parse_frontmatter(path)
            if metadata.get("record_status") != "complete":
                failures.append(
                    f"Listed {profile_label} record remains draft: {filename}."
                )
    if "assets" in required_records:
        assets_path = state_root / "assets.yml"
        if assets_path.is_file():
            failures.extend(asset_readiness_failures(assets_path))
    if "route-family" in required_records:
        route_family_path = state_root / "route-family.json"
        if route_family_path.is_file():
            route_family, route_family_errors = validate_route_family_record(
                route_family_path,
            )
            if route_family_errors:
                failures.append(
                    "Listed route-family record is structurally invalid."
                )
            elif isinstance(route_family, dict):
                review = route_family.get("review")
                routes = route_family.get("routes")
                if not isinstance(review, dict):
                    failures.append(
                        "Listed route-family record has no valid review state."
                    )
                else:
                    for key in ("direct_entry", "link_integrity", "route_count"):
                        if review.get(key) != "passed":
                            failures.append(
                                f"Listed route-family review remains incomplete: {key}."
                            )
                    if review.get("body_comparison") != "reviewed":
                        failures.append(
                            "Listed route-family body comparison remains "
                            "unreviewed."
                        )
                    if review.get("atlas_artifact") != "reviewed":
                        failures.append(
                            "Listed route-family atlas artifact remains unreviewed."
                        )
                    cultural = review.get("cultural_acceptance")
                    if isinstance(cultural, dict):
                        expected_status = (
                            "accepted"
                            if cultural.get("required") is True
                            else "not-required"
                        )
                        if cultural.get("status") != expected_status:
                            failures.append(
                                "Listed route-family cultural acceptance remains "
                                "incomplete."
                            )
                if isinstance(routes, list) and any(
                    not isinstance(route, dict)
                    or route.get("review_status") != "accepted"
                    for route in routes
                ):
                    failures.append(
                        "Every listed route-family route must be accepted before "
                        "readiness can be claimed."
                    )
                if isinstance(routes, list) and any(
                    isinstance(route, dict)
                    and isinstance(route.get("capture_requirements"), dict)
                    and isinstance(
                        route["capture_requirements"].get("viewports"),
                        list,
                    )
                    and any(
                        isinstance(viewport, dict)
                        and viewport.get("width") is None
                        for viewport in route["capture_requirements"]["viewports"]
                    )
                    for route in routes
                ):
                    failures.append(
                        "Every unresolved route-family capture width must be "
                        "replaced with a project-derived integer before "
                        "readiness can be claimed."
                    )
    if "batch-range" in required_records:
        batch_range_path = state_root / "batch-range.json"
        if batch_range_path.is_file():
            try:
                batch_report = run_batch_range_readiness_audit(
                    batch_range_path,
                    project,
                )
                if batch_report.get("comparison_ready") is not True:
                    gaps = batch_report.get("gaps")
                    if isinstance(gaps, list) and gaps:
                        for gap in gaps:
                            if isinstance(gap, dict):
                                failures.append(
                                    "Batch Study evidence remains incomplete: "
                                    f"{gap.get('code', 'unknown')} "
                                    f"({gap.get('scope', 'study')}): "
                                    f"{gap.get('message', 'No detail recorded.')}"
                                )
                    else:
                        failures.append(
                            "Batch Study evidence remains incomplete without "
                            "a reported coverage gap."
                        )
                # Protocol/capture coverage is not a human contextual
                # disposition.  Keep the two reports separate so an otherwise
                # complete study cannot silently acquire an aesthetic or
                # contextual acceptance claim from mechanical coverage alone.
                if (
                    batch_report.get("comparison_ready") is True
                    and batch_report.get("final_ready") is not True
                ):
                    human_gaps = batch_report.get("human_contextual_gaps")
                    if isinstance(human_gaps, list) and human_gaps:
                        for gap in human_gaps:
                            if isinstance(gap, dict):
                                failures.append(
                                    "Batch Study human contextual disposition "
                                    "remains incomplete: "
                                    f"{gap.get('code', 'unknown')} "
                                    f"({gap.get('scope', 'study')}): "
                                    f"{gap.get('message', 'No detail recorded.')}"
                                )
                    else:
                        failures.append(
                            "Batch Study human contextual disposition remains "
                            "incomplete without a reported disposition gap."
                        )
                if batch_report.get("automatic_aesthetic_pass") is not False:
                    failures.append(
                        "Batch Study readiness cannot contain an automatic "
                        "aesthetic pass."
                    )
            except StateError as exc:
                failures.append(f"Invalid Batch Study readiness evidence: {exc}")
    project_contrast_report: dict[str, object] | None = None
    if "project-contrast" in required_records:
        project_contrast_path = state_root / "project-contrast.json"
        if project_contrast_path.is_file():
            try:
                project_contrast_report = run_project_contrast_readiness_audit(
                    project_contrast_path,
                    project,
                )
                if project_contrast_report.get("ready") is not True:
                    gaps = project_contrast_report.get("gaps")
                    findings = project_contrast_report.get("findings")
                    if isinstance(gaps, list):
                        for gap in gaps:
                            if isinstance(gap, dict):
                                failures.append(
                                    "Project Contrast evidence remains incomplete: "
                                    f"{gap.get('code', 'unknown')} "
                                    f"({gap.get('message', 'No detail recorded.')})"
                                )
                    if isinstance(findings, list):
                        for finding in findings:
                            if (
                                isinstance(finding, dict)
                                and finding.get("blocking") is True
                            ):
                                failures.append(
                                    "Project Contrast evidence is invalid: "
                                    f"{finding.get('code', 'unknown')} "
                                    f"({finding.get('message', 'No detail recorded.')})"
                                )
                    if not failures or not any(
                        entry.startswith("Project Contrast evidence")
                        for entry in failures
                    ):
                        failures.append(
                            "Project Contrast evidence remains incomplete without "
                            "a reported coverage gap."
                        )
                if project_contrast_report.get("automatic_aesthetic_pass") is not False:
                    failures.append(
                        "Project Contrast readiness cannot contain an automatic "
                        "aesthetic pass."
                    )
            except StateError as exc:
                failures.append(f"Invalid Project Contrast readiness evidence: {exc}")
    if "direction-challenge" in required_records:
        direction_challenge_path = state_root / "direction-challenge.json"
        if direction_challenge_path.is_file():
            try:
                direction_challenge_report = run_direction_challenge_readiness_audit(
                    direction_challenge_path,
                    project,
                )
                reported_incomplete = False
                if direction_challenge_report.get("ready") is not True:
                    gaps = direction_challenge_report.get("gaps")
                    findings = direction_challenge_report.get("findings")
                    if isinstance(gaps, list):
                        for gap in gaps:
                            if isinstance(gap, dict):
                                reported_incomplete = True
                                failures.append(
                                    "Direction Challenge evidence remains incomplete: "
                                    f"{gap.get('code', 'unknown')} "
                                    f"({gap.get('message', 'No detail recorded.')})"
                                )
                    if isinstance(findings, list):
                        for entry in findings:
                            if (
                                isinstance(entry, dict)
                                and entry.get("blocking") is True
                            ):
                                reported_incomplete = True
                                failures.append(
                                    "Direction Challenge evidence is invalid: "
                                    f"{entry.get('code', 'unknown')} "
                                    f"({entry.get('message', 'No detail recorded.')})"
                                )
                    if not reported_incomplete:
                        failures.append(
                            "Direction Challenge evidence remains incomplete without "
                            "a reported coverage gap."
                        )
                if direction_challenge_report.get("automatic_aesthetic_pass") is not False:
                    failures.append(
                        "Direction Challenge readiness cannot contain an automatic "
                        "aesthetic pass."
                    )
                if direction_challenge_report.get("ready") is True:
                    failures.extend(
                        direction_challenge_final_build_binding_failures(
                            state_root,
                            project,
                        )
                    )
            except StateError as exc:
                failures.append(
                    f"Invalid Direction Challenge readiness evidence: {exc}"
                )
    connected_report: dict[str, object] | None = None
    if "connected-public-experience" in evidence_capabilities:
        connected_public_experience_path = (
            state_root / "connected-public-experience.json"
        )
        if connected_public_experience_path.is_file():
            try:
                connected_report = run_connected_public_experience_readiness_audit(
                    connected_public_experience_path,
                    project,
                    evidence_capabilities,
                )
                if connected_report.get("ready") is not True:
                    reported_incomplete = False
                    gaps = connected_report.get("gaps")
                    findings = connected_report.get("findings")
                    if isinstance(gaps, list):
                        for entry in gaps:
                            if isinstance(entry, dict):
                                reported_incomplete = True
                                failures.append(
                                    "Connected Public Experience evidence remains "
                                    "incomplete: "
                                    f"{entry.get('code', 'unknown')} "
                                    f"({entry.get('message', 'No detail recorded.')})"
                                )
                    if isinstance(findings, list):
                        for entry in findings:
                            if (
                                isinstance(entry, dict)
                                and entry.get("blocking") is True
                            ):
                                reported_incomplete = True
                                failures.append(
                                    "Connected Public Experience evidence is invalid: "
                                    f"{entry.get('code', 'unknown')} "
                                    f"({entry.get('message', 'No detail recorded.')})"
                                )
                    if not reported_incomplete:
                        failures.append(
                            "Connected Public Experience evidence remains incomplete "
                            "without a reported coverage gap."
                        )
                if connected_report.get("automatic_aesthetic_pass") is not False:
                    failures.append(
                        "Connected Public Experience readiness cannot contain an "
                        "automatic aesthetic pass."
                    )
            except StateError as exc:
                failures.append(
                    "Invalid Connected Public Experience readiness evidence: "
                    f"{exc}"
                )
    failures.extend(
        final_build_evidence_binding_failures(
            state_root,
            project_contrast_report=project_contrast_report,
            connected_public_experience_report=connected_report,
        )
    )
    if "cultural-context" in evidence_capabilities:
        review_path = state_root / "visual-review.md"
        if review_path.is_file():
            _metadata, review_body = read_frontmatter_document(review_path)
            conclusion = (
                markdown_label_value(review_body, "Reviewer conclusion") or ""
            ).strip().casefold()
            relationship = (
                markdown_label_value(review_body, "Reviewer relationship") or ""
            ).strip().casefold()
            if conclusion != "owner accepted" or relationship not in {
                "accountable-owner",
                "owner-authorized-human",
                "independent-human",
            }:
                failures.append(
                    "Cultural-context readiness requires accepted review by an "
                    "accountable owner, owner-authorized human, or independent "
                    "human reviewer; producer self-review is provisional."
                )
    return failures


def append_required_ignore_lines(
    root: Path,
    required_lines: tuple[str, ...],
) -> None:
    ignore_path = root / ".gitignore"
    existing = ""
    if ignore_path.is_file():
        try:
            existing = ignore_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise StateError(
                "privacy-ignore-read-failed",
                str(exc),
                path=ignore_path,
            ) from exc
    required_block = "\n".join(required_lines) + "\n"
    if existing.endswith(required_block):
        return
    existing = existing.replace(required_block, "")
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    try:
        with ignore_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(existing + prefix + required_block)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise StateError(
            "privacy-ignore-write-failed",
            str(exc),
            path=ignore_path,
        ) from exc


def atomic_replace_bytes(path: Path, content: bytes, *, code: str) -> None:
    """Replace one ordinary file from a same-directory, fsynced private temp."""

    descriptor: int | None = None
    temporary: Path | None = None
    try:
        descriptor, raw_temporary = tempfile.mkstemp(
            prefix=f".{path.name}.design-dna-",
            dir=path.parent,
        )
        temporary = Path(raw_temporary)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if entry_exists(path) and is_reparse(path):
            raise StateError(
                "reparse-point-refused",
                "Refusing to replace a redirected privacy-guard file.",
                path=path,
            )
        os.replace(temporary, path)
        temporary = None
    except Exception as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary is not None and entry_exists(temporary):
            try:
                if not is_reparse(temporary):
                    temporary.unlink()
            except OSError:
                pass
        if isinstance(exc, StateError):
            raise
        raise StateError(code, str(exc), path=path) from exc


def install_backup_privacy_guard(root: Path) -> bool:
    """Ignore recovery contents while retaining byte-exact rollback data."""

    ignore_path = root / ".gitignore"
    existed = ignore_path.is_file()
    existing = b""
    if existed:
        try:
            existing = ignore_path.read_bytes()
        except OSError as exc:
            raise StateError(
                "privacy-ignore-read-failed",
                str(exc),
                path=ignore_path,
            ) from exc
    block = BACKUP_PRIVACY_IGNORE_BLOCK.encode("utf-8")
    if block in existing:
        raise StateError(
            "privacy-ignore-conflict",
            "The recovery privacy-guard marker already exists.",
            path=ignore_path,
        )
    # Always include the leading newline in the removable suffix. This keeps
    # the marker on its own Git-ignore line and lets rollback strip one exact
    # byte sequence without normalizing the owner's original line endings.
    guarded_suffix = b"\n" + block
    atomic_replace_bytes(
        ignore_path,
        existing + guarded_suffix,
        code="privacy-ignore-write-failed",
    )
    return existed


def remove_backup_privacy_guard(root: Path, original_existed: bool) -> None:
    ignore_path = root / ".gitignore"
    try:
        guarded = ignore_path.read_bytes()
    except OSError as exc:
        raise StateError(
            "privacy-ignore-read-failed",
            str(exc),
            path=ignore_path,
        ) from exc
    guarded_suffix = b"\n" + BACKUP_PRIVACY_IGNORE_BLOCK.encode("utf-8")
    if not guarded.endswith(guarded_suffix):
        raise StateError(
            "privacy-ignore-guard-missing",
            "The exact recovery privacy-guard suffix is missing.",
            path=ignore_path,
        )
    restored = guarded[: -len(guarded_suffix)]
    try:
        if original_existed:
            atomic_replace_bytes(
                ignore_path,
                restored,
                code="privacy-ignore-restore-failed",
            )
        else:
            if restored:
                raise StateError(
                    "privacy-ignore-restore-failed",
                    "A newly created recovery guard contains unexpected owner data.",
                    path=ignore_path,
                )
            ignore_path.unlink()
    except StateError:
        raise
    except OSError as exc:
        raise StateError(
            "privacy-ignore-restore-failed",
            str(exc),
            path=ignore_path,
        ) from exc


def render_new_state(
    skill_root: Path,
    destination: Path,
    version: str,
    records: tuple[str, ...],
    assurance_profiles: tuple[str, ...],
    evidence_capabilities: tuple[str, ...] = (),
    triggers: tuple[str, ...] = (),
) -> None:
    template_root = skill_root / "templates"
    effective_capabilities = normalize_evidence_capabilities(
        expand_enterprise_candidate_requirements([
            *inferred_evidence_capabilities(assurance_profiles),
            *evidence_capabilities,
        ])
    )
    contents: dict[str, str] = {}
    for record in records:
        content = (
            template_text(
                template_root,
                RECORD_TEMPLATES[record][1],
                version,
                assurance_profiles,
            )
            + capability_sections_text(record, effective_capabilities)
        )
        if record in {"project-contrast", "direction-challenge"} and triggers:
            record_label = (
                "Project Contrast"
                if record == "project-contrast"
                else "Direction Challenge"
            )
            try:
                triggered_payload = json.loads(content)
            except json.JSONDecodeError as exc:
                raise StateError(
                    f"{record}-template-invalid",
                    f"{record_label} template must be valid JSON before triggers are recorded.",
                    path=template_root / RECORD_TEMPLATES[record][1],
                ) from exc
            if not isinstance(triggered_payload, dict):
                raise StateError(
                    f"{record}-template-invalid",
                    f"{record_label} template root must be an object.",
                    path=template_root / RECORD_TEMPLATES[record][1],
                )
            scope = triggered_payload.get("scope")
            if not isinstance(scope, dict):
                raise StateError(
                    f"{record}-template-invalid",
                    f"{record_label} template must include a scope object.",
                    path=template_root / RECORD_TEMPLATES[record][1],
                )
            scope["trigger"] = list(triggers)
            content = json.dumps(triggered_payload, indent=2) + "\n"
        contents[RECORD_TEMPLATES[record][0]] = content
    contents["state.json"] = state_manifest(
        version,
        records,
        assurance_profiles,
        effective_capabilities,
    )
    destination.mkdir()
    for filename, content in contents.items():
        target = destination / filename
        assert_contained(target, destination)
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    (destination / "evidence").mkdir()
    if "reference-dossier" in records:
        # Contracts are rank-specific and bind real source URLs, so the
        # initializer creates only their private home.  It never fabricates a
        # `strong-N` contract or replaces an existing project-authored one.
        (destination / "references").mkdir()
    append_required_ignore_lines(destination, STATE_PRIVACY_IGNORE_LINES)


def merge_existing(
    existing: Path,
    staged: Path,
    *,
    force: bool,
    selected: tuple[str, ...],
    version: str,
    assurance_profiles: tuple[str, ...],
    evidence_capabilities: tuple[str, ...],
    triggers: tuple[str, ...],
) -> None:
    if not entry_exists(existing):
        return
    assert_safe_tree(existing)
    if not existing.is_dir():
        raise StateError("invalid-state-entry", ".design-dna exists but is not a directory.", path=existing)
    existing_manifest = existing / "state.json"
    previous_records: list[str] = []
    previous_profiles: tuple[str, ...] = ()
    previous_capabilities: tuple[str, ...] = ()
    previous_extensions: list[dict[str, object]] = []
    if existing_manifest.is_file():
        try:
            payload = read_json(existing_manifest)
            raw_records = payload.get("records") if isinstance(payload, dict) else None
            if (
                not isinstance(raw_records, list)
                or not all(isinstance(record, str) for record in raw_records)
                or len(raw_records) != len(set(raw_records))
                or any(record not in RECORD_TEMPLATES for record in raw_records)
            ):
                raise StateError(
                    "invalid-existing-state",
                    "Existing state.json has invalid records.",
                    path=existing_manifest,
                )
            previous_records = raw_records
            raw_profiles = (
                payload.get("assurance_profiles")
                if isinstance(payload, dict)
                else None
            )
            if (
                isinstance(raw_profiles, list)
                and raw_profiles
                and all(isinstance(item, str) for item in raw_profiles)
            ):
                previous_profiles = normalize_assurance_profiles(
                    raw_profiles
                )
            else:
                legacy_profile = (
                    payload.get("assurance_profile")
                    if isinstance(payload, dict)
                    else None
                )
                legacy_profiles = (
                    REQUEST_PROFILE_ASSURANCE.get(legacy_profile, ())
                    if isinstance(legacy_profile, str)
                    else ()
                )
                previous_profiles = merged_assurance_profiles(
                    list(legacy_profiles),
                    [],
                    previous_records,
                )
            existing_contract = (
                payload.get("evidence_contract")
                if isinstance(payload, dict)
                else None
            )
            if existing_contract is not None:
                (
                    previous_capabilities,
                    previous_extensions,
                ) = validate_evidence_contract(
                    existing_contract,
                    previous_profiles,
                )
        except StateError:
            if not force:
                raise
    elif not force:
        raise StateError(
            "invalid-existing-state",
            "Existing .design-dna directory has no state.json; pass --force to rebuild packaged metadata while preserving custom files.",
            path=existing_manifest,
        )
    def fail_walk(error: OSError) -> None:
        raise StateError(
            "state-enumeration-failed",
            str(error),
            path=Path(error.filename) if error.filename else existing,
        ) from error

    for current, directories, files in os.walk(
        existing,
        topdown=True,
        followlinks=False,
        onerror=fail_walk,
    ):
        relative = Path(current).relative_to(existing)
        target_dir = staged / relative
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in files:
            if relative == Path(".") and name == "state.json":
                continue
            source = Path(current) / name
            target = target_dir / name
            if is_reparse(source):
                raise StateError(
                    "reparse-point-refused",
                    "State changed to contain a link during initialization.",
                    path=source,
                )
            if target.exists() and force:
                continue
            if target.exists():
                target.unlink()
            shutil.copy2(source, target, follow_symlinks=False)
    if triggers:
        for record in ("project-contrast", "direction-challenge"):
            contract_path = staged / RECORD_TEMPLATES[record][0]
            if not contract_path.is_file():
                continue
            try:
                contract = read_json(contract_path)
            except StateError as exc:
                raise StateError(
                    "trigger-contract-invalid",
                    f"Unable to add the recurrence trigger to {contract_path.name}: {exc}",
                    path=contract_path,
                ) from exc
            scope = contract.get("scope") if isinstance(contract, dict) else None
            current_triggers = scope.get("trigger") if isinstance(scope, dict) else None
            if not isinstance(current_triggers, list) or not all(
                isinstance(item, str) for item in current_triggers
            ):
                raise StateError(
                    "trigger-contract-shape-invalid",
                    f"{contract_path.name} must contain a string trigger list.",
                    path=contract_path,
                )
            scope["trigger"] = list(dict.fromkeys([*current_triggers, *triggers]))
            try:
                contract_path.write_text(
                    json.dumps(contract, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
            except OSError as exc:
                raise StateError(
                    "trigger-contract-write-failed",
                    str(exc),
                    path=contract_path,
                ) from exc
    inferred_records = [
        record
        for record, (filename, _) in RECORD_TEMPLATES.items()
        if (staged / filename).is_file()
    ]
    merged_records = tuple(
        dict.fromkeys([*previous_records, *selected, *inferred_records])
    )
    manifest_path = staged / "state.json"
    effective_profiles = merged_assurance_profiles(
        list(previous_profiles),
        list(assurance_profiles),
        merged_records,
    )
    effective_capabilities = normalize_evidence_capabilities(
        expand_enterprise_candidate_requirements([
            *inferred_evidence_capabilities(effective_profiles),
            *previous_capabilities,
            *evidence_capabilities,
        ])
    )
    manifest_path.write_text(
        state_manifest(
            version,
            merged_records,
            effective_profiles,
            effective_capabilities,
            previous_extensions,
        ),
        encoding="utf-8",
        newline="\n",
    )
    append_required_ignore_lines(staged, STATE_PRIVACY_IGNORE_LINES)


def visual_table_cells(line: str) -> tuple[str, ...]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return ()
    return tuple(cell.strip() for cell in stripped[1:-1].split("|"))


def migrated_visual_status(
    value: str,
    verification: str,
) -> tuple[str, str]:
    normalized = value.strip().casefold()
    owner = "not-recorded (legacy schema-1)"
    recognized = sorted(
        VISUAL_FINDING_STATUSES
        | {"fixed", "accepted"},
        key=len,
        reverse=True,
    )
    status = ""
    for candidate in recognized:
        if normalized == candidate:
            status = candidate
            break
        if normalized.startswith(candidate):
            remainder = value[len(candidate):].strip()
            if remainder[:1] in {"/", ";", ",", "-", "—", ":"}:
                status = candidate
                extracted = remainder[1:].strip()
                if extracted:
                    owner = extracted
                break
    if not status:
        # Old draft templates used an option list (and some hand-edited drafts
        # left this cell blank). Do not block a lossless migration or guess that
        # the finding was resolved: preserve the exact source table in the
        # migration report/backup, carry the raw value into the owner note, and
        # conservatively reopen the migrated row for review.
        legacy_value = value.strip() or "blank"
        status = "open"
        owner = f"not-recorded (legacy status: {legacy_value})"
    if status == "fixed":
        status = (
            "verified"
            if non_placeholder(verification)
            else "fixed-unverified"
        )
    elif status == "accepted":
        status = "accepted-risk"
    return status, owner


def migrate_visual_review_contract(
    path: Path,
) -> dict[str, object] | None:
    try:
        original_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise StateError(
            "state-read-failed",
            str(exc),
            path=path,
        ) from exc
    metadata, frontmatter, body = split_frontmatter_text(
        original_text,
        path=path,
    )
    findings = re.search(r"(?m)^## Findings\s*$", body)
    if findings is None:
        raise StateError(
            "legacy-visual-review-invalid",
            "visual-review.md has no Findings section to migrate.",
            path=path,
        )
    next_heading = re.search(
        r"(?m)^##\s+.+$",
        body[findings.end():],
    )
    section_end = (
        findings.end() + next_heading.start()
        if next_heading is not None
        else len(body)
    )
    section_start = findings.end()
    section = body[section_start:section_end]
    lines = section.splitlines(keepends=True)
    table_index: int | None = None
    headers: tuple[str, ...] = ()
    recognized_headers = {
        VISUAL_FINDINGS_HEADERS,
        LEGACY_VISUAL_FINDINGS_HEADERS,
        DESIGN_DNA_22_VISUAL_FINDINGS_HEADERS,
    }
    for index, line in enumerate(lines):
        candidate = visual_table_cells(line)
        if candidate in recognized_headers:
            table_index = index
            headers = candidate
            break
    if table_index is None:
        raise StateError(
            "legacy-visual-review-invalid",
            "visual-review.md does not contain a recognized findings table.",
            path=path,
        )
    if table_index + 1 >= len(lines):
        raise StateError(
            "legacy-visual-review-invalid",
            "visual-review.md findings table has no separator row.",
            path=path,
        )
    separator = visual_table_cells(lines[table_index + 1])
    if (
        len(separator) != len(headers)
        or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator)
    ):
        raise StateError(
            "legacy-visual-review-invalid",
            "visual-review.md findings table separator is invalid.",
            path=path,
        )
    row_end = table_index + 2
    source_rows: list[tuple[str, ...]] = []
    while row_end < len(lines):
        cells = visual_table_cells(lines[row_end])
        if not cells:
            break
        if len(cells) != len(headers):
            raise StateError(
                "legacy-visual-review-invalid",
                "visual-review.md has a findings row with the wrong width.",
                path=path,
            )
        source_rows.append(cells)
        row_end += 1

    already_current = (
        headers == VISUAL_FINDINGS_HEADERS
        and metadata.get("findings_contract")
        == VISUAL_FINDINGS_CONTRACT
    )
    if already_current:
        return None

    migration: dict[str, object] | None = None
    migrated_body = body
    if headers != VISUAL_FINDINGS_HEADERS:
        migrated_rows: list[tuple[str, ...]] = []
        if headers == LEGACY_VISUAL_FINDINGS_HEADERS:
            source_contract = "legacy-schema-1-six-column"
            for (
                severity,
                evidence,
                cause,
                fix,
                verification,
                status_owner,
            ) in source_rows:
                status, owner = migrated_visual_status(
                    status_owner,
                    verification,
                )
                migrated_rows.append(
                    (
                        severity.casefold(),
                        "not-recorded",
                        evidence,
                        "not-recorded",
                        cause,
                        fix,
                        verification or "not-recorded",
                        status,
                        owner,
                    )
                )
        else:
            source_contract = "design-dna-2.2-eight-column"
            for (
                severity,
                confidence,
                evidence,
                impact,
                cause,
                fix,
                verification,
                status_owner,
            ) in source_rows:
                status, owner = migrated_visual_status(
                    status_owner,
                    verification,
                )
                migrated_rows.append(
                    (
                        severity.casefold(),
                        confidence.casefold(),
                        evidence,
                        impact,
                        cause,
                        fix,
                        verification or "not-recorded",
                        status,
                        owner,
                    )
                )
        source_table = "".join(
            lines[table_index:row_end]
        ).rstrip("\r\n")
        rendered_lines = [
            "| " + " | ".join(VISUAL_FINDINGS_HEADERS) + " |\n",
            "| "
            + " | ".join("---" for _ in VISUAL_FINDINGS_HEADERS)
            + " |\n",
            *[
                "| " + " | ".join(row) + " |\n"
                for row in migrated_rows
            ],
        ]
        if row_end == len(lines) and rendered_lines:
            rendered_lines[-1] = rendered_lines[-1].rstrip("\n")
        migrated_table = "".join(rendered_lines).rstrip("\r\n")
        prefix = "".join(lines[:table_index])
        suffix = "".join(lines[row_end:])
        migrated_section = prefix + "".join(rendered_lines) + suffix
        migrated_body = (
            body[:section_start]
            + migrated_section
            + body[section_end:]
        )
        migration = {
            "path": "visual-review.md",
            "source_contract": source_contract,
            "source_schema_version": 1,
            "source_created_with": metadata.get(
                "created_with",
                "unknown",
            ),
            "source_body_sha256": body_sha256(body),
            "migrated_body_sha256": body_sha256(migrated_body),
            "source_table": source_table,
            "source_table_sha256": hashlib.sha256(
                source_table.encode("utf-8")
            ).hexdigest(),
            "migrated_table": migrated_table,
            "migrated_table_sha256": hashlib.sha256(
                migrated_table.encode("utf-8")
            ).hexdigest(),
        }

    base_text = (
        "---\n"
        + frontmatter
        + "\n---\n"
        + migrated_body
    )
    rendered = update_frontmatter_text(
        base_text,
        path=path,
        updates={
            "record_status": "draft",
            "findings_contract": VISUAL_FINDINGS_CONTRACT,
        },
        removals=COMPLETE_RECORD_FIELDS,
    )
    try:
        path.write_text(
            rendered,
            encoding="utf-8",
            newline="\n",
        )
    except OSError as exc:
        raise StateError(
            "visual-review-migration-write-failed",
            str(exc),
            path=path,
        ) from exc
    return migration


ASSET_TYPE_BY_SUFFIX = {
    ".apng": "image",
    ".avif": "image",
    ".gif": "image",
    ".jpeg": "image",
    ".jpg": "image",
    ".png": "image",
    ".svg": "image",
    ".webp": "image",
    ".mp4": "video",
    ".mov": "video",
    ".m4v": "video",
    ".webm": "video",
    ".mp3": "audio",
    ".m4a": "audio",
    ".ogg": "audio",
    ".wav": "audio",
    ".flac": "audio",
    ".woff": "font",
    ".woff2": "font",
    ".otf": "font",
    ".ttf": "font",
    ".pdf": "document",
    ".doc": "document",
    ".docx": "document",
}


def migrate_asset_manifest_contract(
    path: Path,
    project: Path,
) -> dict[str, object] | None:
    try:
        source_bytes = path.read_bytes()
        payload = parse_strict_yaml_subset(
            source_bytes.decode("utf-8"),
            path=path,
        )
    except (OSError, UnicodeError) as exc:
        raise StateError(
            "asset-migration-read-failed",
            str(exc),
            path=path,
        ) from exc
    if not isinstance(payload, dict):
        raise StateError(
            "asset-migration-invalid",
            "assets.yml must contain a mapping before migration.",
            path=path,
        )
    source_schema = payload.get("schema_version")
    if source_schema == ASSET_SCHEMA_VERSION:
        return None
    if source_schema != 1:
        raise StateError(
            "asset-migration-unsupported",
            "Only schema-1 assets.yml can migrate to schema 2.",
            path=path,
        )
    assets = payload.get("assets")
    if not isinstance(assets, list) or not all(
        isinstance(item, dict) for item in assets
    ):
        raise StateError(
            "asset-migration-invalid",
            "Schema-1 assets.yml assets must be a list of mappings.",
            path=path,
        )
    unresolved_ids: list[str] = []
    for index, asset in enumerate(assets):
        asset_id = str(asset.get("id", f"assets[{index}]"))
        generated = asset.get("generated")
        if not isinstance(generated, dict):
            raise StateError(
                "asset-migration-invalid",
                f"{asset_id} generated must be a mapping.",
                path=path,
            )
        unresolved: list[str] = [
            "asset_type confirmation",
            "publication_status decision",
            "concept_disclosure decision",
        ]
        # Schema 1 did not have the current cryptographic source-binding
        # contract.  Never preserve or manufacture a purported visual-source
        # binding from that format: it would either be unverified legacy text
        # or falsely imply that current observer/frame evidence exists.  Keep
        # the migrated row explicitly unresolved until a reviewer supplies a
        # fresh schema-2 binding backed by current generated artifacts.
        if asset.pop("source_mapping", None) is not None:
            unresolved.append("source_mapping binding")
        source_path = str(asset.get("source_path", "")).strip()
        inferred_type = ASSET_TYPE_BY_SUFFIX.get(
            Path(source_path).suffix.casefold(),
            "image" if generated.get("used") else "other",
        )
        asset["asset_type"] = inferred_type
        asset["publication_status"] = "internal-only"
        asset["source_sha256"] = ""
        if source_path:
            try:
                source = safe_binding_path(
                    project,
                    source_path,
                    record_path=path,
                )
                asset["source_sha256"] = hashlib.sha256(
                    source.read_bytes()
                ).hexdigest()
            except (OSError, StateError):
                unresolved.append("source_path/source_sha256")
        legacy_disclosure_required = generated.pop(
            "disclosure_required",
            False,
        )
        legacy_disclosure_text_value = generated.pop(
            "disclosure_text",
            "",
        )
        if type(legacy_disclosure_required) is not bool or not isinstance(
            legacy_disclosure_text_value,
            str,
        ):
            raise StateError(
                "asset-migration-invalid",
                (
                    f"{asset_id} legacy disclosure_required must be a "
                    "boolean and disclosure_text must be a string."
                ),
                path=path,
            )
        legacy_disclosure_text = legacy_disclosure_text_value.strip()
        asset["concept_disclosure"] = {
            "decision": (
                "required"
                if legacy_disclosure_required and legacy_disclosure_text
                else "pending"
            ),
            "reason": (
                "Migrated schema-1 disclosure; owner revalidation required."
                if legacy_disclosure_required and legacy_disclosure_text
                else ""
            ),
            "text": (
                legacy_disclosure_text
                if legacy_disclosure_required
                else ""
            ),
        }
        generated_defaults: dict[str, object] = {
            "authorization_basis": "",
            "prompt_or_digest": "",
            "generated_at": "",
            "rejected_outputs": [],
            "contact_sheet_path": "",
            "contact_sheet_sha256": "",
            "artifact_inspection": "",
            "responsive_crop_evidence": [],
        }
        for key, value in generated_defaults.items():
            generated.setdefault(key, value)
        if generated.get("used") is True:
            unresolved.extend(
                [
                    "generated.authorization_basis",
                    "generated.prompt_or_digest",
                    "generated.generated_at",
                    "generated.rejected_outputs",
                    "generated.contact_sheet_path/contact_sheet_sha256",
                    "generated.artifact_inspection",
                ]
            )
            if inferred_type in {"image", "video"}:
                unresolved.append(
                    "generated.responsive_crop_evidence"
                )
        asset["factual_status"] = (
            "placeholder"
            if asset.get("factual_status") == "placeholder"
            else "pending"
        )
        asset["owner_approval"] = "pending"
        asset["migration_review"] = {
            "required": True,
            "source_schema_version": "1",
            "reason": (
                "Schema-1 asset evidence cannot establish the new type, "
                "exposure, disclosure, source-binding, and generated-media "
                "contract without accountable review."
            ),
            "unresolved_fields": list(dict.fromkeys(unresolved)),
        }
        unresolved_ids.append(asset_id)
    payload["schema_version"] = ASSET_SCHEMA_VERSION
    rendered = dump_strict_yaml_subset(payload) + "\n"
    try:
        path.write_text(rendered, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise StateError(
            "asset-migration-write-failed",
            str(exc),
            path=path,
        ) from exc
    return {
        "path": "assets.yml",
        "source_schema_version": 1,
        "target_schema_version": ASSET_SCHEMA_VERSION,
        "source_manifest_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "migrated_manifest_sha256": hashlib.sha256(
            rendered.encode("utf-8")
        ).hexdigest(),
        "unresolved_asset_ids": unresolved_ids,
    }


def legacy_project_contrast_draft_like(payload: object) -> bool:
    """Recognize only the prior packaged placeholder record, never real work."""

    if not isinstance(payload, dict) or "record_status" in payload:
        return False
    scope = payload.get("scope")
    source = payload.get("source_to_encounter")
    direction = payload.get("selected_direction")
    comparison = payload.get("comparison")
    if not all(isinstance(value, dict) for value in (scope, source, direction, comparison)):
        return False
    return (
        scope.get("project_id") == "replace-with-project-safe-id"
        and isinstance(source.get("visitor_occasion"), str)
        and source["visitor_occasion"].startswith("Replace with")
        and isinstance(direction.get("organizing_answer"), str)
        and direction["organizing_answer"].startswith("Replace with")
        and "contrast_prompt" not in comparison
    )


def migrate_project_contrast_draft_template(
    path: Path,
    version: str,
) -> dict[str, object] | None:
    """Replace only the known pre-lifecycle placeholder with an honest draft.

    A partially completed legacy record can carry real project reasoning, so it
    is intentionally left untouched for a human-directed conversion instead of
    being guessed into the new contract.
    """

    try:
        source_bytes = path.read_bytes()
        payload = read_json(path)
    except (OSError, StateError) as exc:
        raise StateError("project-contrast-migration-read-failed", str(exc), path=path) from exc
    if not legacy_project_contrast_draft_like(payload):
        return None

    template_root = Path(__file__).resolve().parents[1] / "templates"
    try:
        target = json.loads(
            template_text(
                template_root,
                "project-contrast-template.json",
                version,
            )
        )
    except (StateError, json.JSONDecodeError) as exc:
        raise StateError("project-contrast-migration-template-invalid", str(exc), path=path) from exc
    if not isinstance(target, dict):
        raise StateError(
            "project-contrast-migration-template-invalid",
            "The lifecycle template must be a JSON object.",
            path=path,
        )
    if payload.get("classification") in CLASSIFICATIONS:
        target["classification"] = payload["classification"]
    old_scope = payload.get("scope")
    if isinstance(old_scope, dict):
        old_triggers = old_scope.get("trigger")
        if isinstance(old_triggers, list) and all(
            isinstance(trigger, str) for trigger in old_triggers
        ):
            target_scope = target.get("scope")
            if isinstance(target_scope, dict):
                target_scope["trigger"] = list(dict.fromkeys(old_triggers))
    rendered = json.dumps(target, indent=2, ensure_ascii=False) + "\n"
    try:
        path.write_text(rendered, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise StateError("project-contrast-migration-write-failed", str(exc), path=path) from exc
    return {
        "path": "project-contrast.json",
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "migrated_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "disposition": "known-placeholder-record-reset-to-explicit-draft",
        "limitations": "Only the prior packaged placeholder record was reset; project-specific legacy records require human-directed conversion.",
    }


def migration_payload(
    state_root: Path,
    updated_records: list[str],
    visual_review_migrations: list[dict[str, object]],
    completion_downgrades: list[dict[str, object]],
    asset_manifest_migrations: list[dict[str, object]],
    assurance_transitions: list[dict[str, object]],
    project_contrast_migrations: list[dict[str, object]],
) -> dict[str, object]:
    legacy_files: list[dict[str, object]] = []
    for filename in LEGACY_RECORD_FILES:
        path = state_root / filename
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise StateError(
                "legacy-record-read-failed",
                str(exc),
                path=path,
            ) from exc
        legacy_files.append(
            {
                "path": filename,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "disposition": "preserved-unmapped",
            }
        )
    payload: dict[str, object] = {
        "schema_version": 1,
        "record_type": "design-dna-project-state-migration",
        "migrated_at": datetime.now(timezone.utc).isoformat(),
        "legacy_files": legacy_files,
        "record_updates": sorted(updated_records),
    }
    if visual_review_migrations:
        payload["visual_review_migrations"] = visual_review_migrations
    if completion_downgrades:
        payload["completion_downgrades"] = completion_downgrades
    if asset_manifest_migrations:
        payload["asset_manifest_migrations"] = asset_manifest_migrations
    if assurance_transitions:
        payload["assurance_transitions"] = assurance_transitions
    if project_contrast_migrations:
        payload["project_contrast_migrations"] = project_contrast_migrations
    return payload


def migrate_staged_state(state_root: Path, current_version: str) -> list[str]:
    updated: list[str] = []
    migration_changed = False
    state_path = state_root / "state.json"
    try:
        source_state_bytes = state_path.read_bytes()
    except OSError as exc:
        raise StateError(
            "invalid-existing-state",
            str(exc),
            path=state_path,
        ) from exc
    state_payload = read_json(state_path)
    if not isinstance(state_payload, dict):
        raise StateError(
            "invalid-existing-state",
            "state.json must contain an object before migration.",
            path=state_path,
        )
    raw_records = state_payload.get("records")
    if (
        not isinstance(raw_records, list)
        or not raw_records
        or not all(isinstance(item, str) for item in raw_records)
    ):
        raise StateError(
            "invalid-existing-state",
            (
                "state.json records must be a nonempty list of strings "
                "before migration."
            ),
            path=state_path,
        )
    source_schema_version = state_payload.get("schema_version")
    raw_profiles = state_payload.get("assurance_profiles")
    source_profile_field = "assurance_profiles"
    source_profile_values: list[str] = []
    if (
        isinstance(raw_profiles, list)
        and raw_profiles
        and all(isinstance(item, str) for item in raw_profiles)
    ):
        source_profile_values = list(raw_profiles)
        existing_profiles = normalize_assurance_profiles(raw_profiles)
    else:
        legacy_profile = state_payload.get("assurance_profile")
        source_profile_field = (
            "assurance_profile"
            if isinstance(legacy_profile, str)
            else "missing"
        )
        source_profile_values = (
            [legacy_profile] if isinstance(legacy_profile, str) else []
        )
        legacy_profiles = (
            REQUEST_PROFILE_ASSURANCE.get(legacy_profile, ())
            if isinstance(legacy_profile, str)
            else ()
        )
        existing_profiles = normalize_assurance_profiles(
            list(legacy_profiles) or list(infer_assurance_profiles(raw_records))
        )
    source_contract = state_payload.get("evidence_contract")
    persisted_high_risk_profile = "high-risk" in existing_profiles
    persisted_high_risk_capability = contract_declares_capability(
        source_contract,
        "high-risk",
    )
    if persisted_high_risk_capability and not persisted_high_risk_profile:
        # A state that persisted the gate but not its profile is malformed by
        # the current contract.  Preserve the stronger historical declaration
        # and reopen its evidence rather than silently weakening it.
        existing_profiles = normalize_assurance_profiles(
            [*existing_profiles, "high-risk"]
        )
    cumulative_profiles = merged_assurance_profiles(
        list(existing_profiles),
        [],
        raw_records,
    )
    # Taste calibration became a substantive Showcase/Direction Challenge
    # record.  A migration must add an explicitly *draft* record rather than
    # silently treating historical exploration as calibration evidence.
    migrated_records = list(raw_records)
    if "high-risk" in cumulative_profiles:
        # High-risk is meaningful only with its whole evidence boundary.  Add
        # missing records as drafts below; never treat their absence as proof
        # that the persisted declaration should be downgraded.
        migrated_records = list(
            dict.fromkeys([*migrated_records, *PROFILES["high-risk"]])
        )
    if (
        {"showcase", "direction-challenge"} & set(cumulative_profiles)
        and "taste-calibration" not in migrated_records
    ):
        migrated_records.append("taste-calibration")
    if (
        "enterprise-candidate" in cumulative_profiles
        and "reference-dossier" not in migrated_records
    ):
        migrated_records.append("reference-dossier")
    if (
        "enterprise-candidate" in cumulative_profiles
        and "route-manifest" not in migrated_records
    ):
        # Every build gate now derives its complete route/state/reference map
        # from this single record.  Migrate old projects by adding the truthful
        # unresolved template; never infer routes or claim coverage for them.
        migrated_records.append("route-manifest")
    if source_contract is None:
        migrated_capabilities = inferred_evidence_capabilities(
            cumulative_profiles
        )
        migrated_extensions: list[dict[str, object]] = []
    else:
        (
            migrated_capabilities,
            migrated_extensions,
        ) = migrate_evidence_contract(
            source_contract,
            cumulative_profiles,
        )
    migrated_contract = evidence_contract_payload(
        cumulative_profiles,
        migrated_capabilities,
        migrated_extensions,
    )
    state_changed = (
        state_payload.get("schema_version") != STATE_SCHEMA_VERSION
        or state_payload.get("assurance_profiles")
        != list(cumulative_profiles)
        or state_payload.get("records") != migrated_records
        or "assurance_profile" in state_payload
        or source_contract != migrated_contract
    )
    assurance_transition: dict[str, object] | None = None
    if state_changed:
        migration_changed = True
        state_payload["schema_version"] = STATE_SCHEMA_VERSION
        state_payload["assurance_profiles"] = list(cumulative_profiles)
        state_payload["records"] = migrated_records
        state_payload["evidence_contract"] = migrated_contract
        state_payload.pop("assurance_profile", None)
        state_path.write_text(
            json.dumps(state_payload, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        assurance_transition = {
            "source_schema_version": (
                source_schema_version
                if isinstance(source_schema_version, int)
                else 0
            ),
            "target_schema_version": STATE_SCHEMA_VERSION,
            "source_state_sha256": hashlib.sha256(
                source_state_bytes
            ).hexdigest(),
            "migrated_state_sha256": hashlib.sha256(
                state_path.read_bytes()
            ).hexdigest(),
            "source_profile_field": source_profile_field,
            "source_profile_values": source_profile_values,
            "target_assurance_profiles": list(cumulative_profiles),
            "required_records": list(migrated_records),
            "reason": (
                "Preserved the persisted High-risk assurance declaration or "
                "evidence gate, aligned the state to the High-risk profile, "
                "and added any missing High-risk records only as explicit "
                "draft requirements; migration does not infer completion or "
                "downgrade an incomplete consequential inventory."
                if persisted_high_risk_profile or persisted_high_risk_capability
                else (
                    "Converted scalar or incomplete assurance state to the "
                    "canonical cumulative capability set, retained every listed "
                    "record as a readiness requirement, and added any newly "
                    "required calibration record only as an explicit draft."
                )
            ),
        }
    report_path = state_root / MIGRATION_REPORT
    existing_visual_migrations: list[dict[str, object]] = []
    existing_completion_downgrades: list[dict[str, object]] = []
    existing_asset_migrations: list[dict[str, object]] = []
    existing_assurance_transitions: list[dict[str, object]] = []
    existing_project_contrast_migrations: list[dict[str, object]] = []
    existing_record_updates: list[str] = []
    if report_path.is_file():
        existing_report = read_json(report_path)
        if not isinstance(existing_report, dict):
            raise StateError(
                "invalid-migration-report",
                "Existing migration report must be a JSON object.",
                path=report_path,
            )
        existing_value = existing_report.get(
            "visual_review_migrations",
            [],
        )
        if not isinstance(existing_value, list) or not all(
            isinstance(item, dict) for item in existing_value
        ):
            raise StateError(
                "invalid-migration-report",
                "Existing visual_review_migrations must be a list of objects.",
                path=report_path,
            )
        existing_visual_migrations = [
            dict(item) for item in existing_value
        ]
        existing_downgrades = existing_report.get(
            "completion_downgrades",
            [],
        )
        if not isinstance(existing_downgrades, list) or not all(
            isinstance(item, dict) for item in existing_downgrades
        ):
            raise StateError(
                "invalid-migration-report",
                "Existing completion_downgrades must be a list of objects.",
                path=report_path,
            )
        existing_completion_downgrades = []
        for item in existing_downgrades:
            normalized = dict(item)
            for field in (
                "prior_binding_path",
                "prior_binding_sha256",
                "prior_completion_owner",
                "prior_completed_at",
                "prior_limitations",
            ):
                normalized.setdefault(field, "not-recorded")
            existing_completion_downgrades.append(normalized)
        existing_assets = existing_report.get(
            "asset_manifest_migrations",
            [],
        )
        if not isinstance(existing_assets, list) or not all(
            isinstance(item, dict) for item in existing_assets
        ):
            raise StateError(
                "invalid-migration-report",
                "Existing asset_manifest_migrations must be a list of objects.",
                path=report_path,
            )
        existing_asset_migrations = [
            dict(item) for item in existing_assets
        ]
        existing_transitions = existing_report.get(
            "assurance_transitions",
            [],
        )
        if not isinstance(existing_transitions, list) or not all(
            isinstance(item, dict) for item in existing_transitions
        ):
            raise StateError(
                "invalid-migration-report",
                "Existing assurance_transitions must be a list of objects.",
                path=report_path,
            )
        existing_assurance_transitions = [
            dict(item) for item in existing_transitions
        ]
        existing_project_contrast = existing_report.get(
            "project_contrast_migrations",
            [],
        )
        if not isinstance(existing_project_contrast, list) or not all(
            isinstance(item, dict) for item in existing_project_contrast
        ):
            raise StateError(
                "invalid-migration-report",
                "Existing project_contrast_migrations must be a list of objects.",
                path=report_path,
            )
        existing_project_contrast_migrations = [
            dict(item) for item in existing_project_contrast
        ]
        prior_updates = existing_report.get("record_updates", [])
        if not isinstance(prior_updates, list) or not all(
            isinstance(item, str) for item in prior_updates
        ):
            raise StateError(
                "invalid-migration-report",
                "Existing record_updates must be a list of strings.",
                path=report_path,
            )
        existing_record_updates = list(prior_updates)
    if assurance_transition is not None:
        identity = assurance_transition["source_state_sha256"]
        if not any(
            transition.get("source_state_sha256") == identity
            for transition in existing_assurance_transitions
        ):
            existing_assurance_transitions.append(assurance_transition)
    project_root = state_root.parent.parent
    persisted_profiles = cumulative_profiles
    new_record_names = [
        record for record in migrated_records if record not in raw_records
    ]
    if new_record_names:
        template_root = Path(__file__).resolve().parents[1] / "templates"
        for record in new_record_names:
            record_path = state_root / RECORD_TEMPLATES[record][0]
            if record_path.exists():
                continue
            record_path.write_text(
                template_text(
                    template_root,
                    RECORD_TEMPLATES[record][1],
                    current_version,
                    cumulative_profiles,
                )
                + capability_sections_text(record, migrated_capabilities),
                encoding="utf-8",
                newline="\n",
            )
            migration_changed = True
            updated.append(record)
    asset_path = state_root / "assets.yml"
    if asset_path.is_file():
        asset_migration = migrate_asset_manifest_contract(
            asset_path,
            project_root,
        )
        if asset_migration is not None:
            migration_changed = True
            identity = asset_migration["source_manifest_sha256"]
            if not any(
                existing.get("source_manifest_sha256") == identity
                for existing in existing_asset_migrations
            ):
                existing_asset_migrations.append(asset_migration)
    project_contrast_path = state_root / "project-contrast.json"
    if project_contrast_path.is_file():
        project_contrast_migration = migrate_project_contrast_draft_template(
            project_contrast_path,
            current_version,
        )
        if project_contrast_migration is not None:
            migration_changed = True
            identity = project_contrast_migration["source_sha256"]
            if not any(
                existing.get("source_sha256") == identity
                for existing in existing_project_contrast_migrations
            ):
                existing_project_contrast_migrations.append(
                    project_contrast_migration
                )
            updated.append("project-contrast")
    for filename, record in SUBSTANTIVE_RECORDS.items():
        path = state_root / filename
        if not path.is_file():
            continue
        metadata = parse_frontmatter(path)
        source_metadata, source_body = read_frontmatter_document(path)
        was_complete = source_metadata.get("record_status") == "complete"
        source_hash = body_sha256(source_body)
        record_updated = False
        if filename == "visual-review.md":
            visual_migration = migrate_visual_review_contract(path)
            if visual_migration is not None:
                identity = (
                    visual_migration["source_body_sha256"],
                    visual_migration["migrated_body_sha256"],
                )
                if not any(
                    (
                        existing.get("source_body_sha256"),
                        existing.get("migrated_body_sha256"),
                    )
                    == identity
                    for existing in existing_visual_migrations
                ):
                    existing_visual_migrations.append(
                        visual_migration
                    )
            if (
                visual_migration is not None
                or metadata.get("findings_contract")
                != VISUAL_FINDINGS_CONTRACT
            ):
                record_updated = True
                metadata = parse_frontmatter(path)
        metadata, current_body = read_frontmatter_document(path)
        if was_complete:
            downgrade_reasons: list[str] = []
            if metadata.get("record_status") != "complete":
                downgrade_reasons.append(
                    "The record contract was migrated and requires completion "
                    "against the current assurance profile."
                )
            else:
                downgrade_reasons.extend(
                    completed_record_failures(
                        project_root,
                        path,
                        record,
                        metadata,
                        current_body,
                        required_assurance_profiles=persisted_profiles,
                        required_evidence_capabilities=migrated_capabilities,
                    )
                )
            if downgrade_reasons:
                if metadata.get("record_status") == "complete":
                    write_frontmatter_update(
                        path,
                        updates={"record_status": "draft"},
                        removals=COMPLETE_RECORD_FIELDS,
                    )
                downgrade = {
                    "path": filename,
                    "record": record,
                    "source_created_with": source_metadata.get(
                        "created_with",
                        "not-recorded",
                    ),
                    "source_body_sha256": source_hash,
                    "prior_binding_id": source_metadata.get(
                        "binding_id",
                        "not-recorded",
                    ),
                    "prior_binding_path": source_metadata.get(
                        "binding_path",
                        "not-recorded",
                    ),
                    "prior_binding_sha256": source_metadata.get(
                        "binding_sha256",
                        "not-recorded",
                    ),
                    "prior_completion_owner": source_metadata.get(
                        "completion_owner",
                        "not-recorded",
                    ),
                    "prior_completed_at": source_metadata.get(
                        "completed_at",
                        "not-recorded",
                    ),
                    "prior_limitations": source_metadata.get(
                        "limitations",
                        "not-recorded",
                    ),
                    "reasons": list(dict.fromkeys(downgrade_reasons)),
                }
                identity = (
                    downgrade["path"],
                    downgrade["source_body_sha256"],
                )
                if not any(
                    (
                        existing.get("path"),
                        existing.get("source_body_sha256"),
                    )
                    == identity
                    for existing in existing_completion_downgrades
                ):
                    existing_completion_downgrades.append(downgrade)
                record_updated = True
                metadata = parse_frontmatter(path)
        if metadata.get("record_status") not in RECORD_STATUSES:
            write_frontmatter_update(
                path,
                updates={"record_status": "draft"},
                removals=COMPLETE_RECORD_FIELDS,
            )
            record_updated = True
        if record_updated:
            migration_changed = True
            updated.append(record)
    if not migration_changed:
        return []
    payload = migration_payload(
        state_root,
        list(dict.fromkeys([*existing_record_updates, *updated])),
        existing_visual_migrations,
        existing_completion_downgrades,
        existing_asset_migrations,
        existing_assurance_transitions,
        existing_project_contrast_migrations,
    )
    try:
        report_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except OSError as exc:
        raise StateError(
            "migration-report-write-failed",
            str(exc),
            path=report_path,
        ) from exc
    return updated


def mark_record_complete(
    state_root: Path,
    project: Path,
    record: str,
    *,
    binding_kind: str,
    binding_id: str,
    binding_path: str,
    owner: str,
    limitations: str,
    completed_at: str,
) -> None:
    filename = RECORD_TEMPLATES[record][0]
    path = state_root / filename
    if filename not in SUBSTANTIVE_RECORDS:
        raise StateError(
            "record-status-unsupported",
            f"{record} does not use the draft/complete evidence contract.",
            path=path,
        )
    if not path.is_file():
        raise StateError(
            "record-missing",
            f"Selected record does not exist: {record}.",
            path=path,
        )
    metadata, body = read_frontmatter_document(path)
    if (
        record == "visual-review"
        and metadata.get("findings_contract")
        != VISUAL_FINDINGS_CONTRACT
    ):
        raise StateError(
            "visual-review-migration-required",
            (
                "visual-review must use findings_contract "
                f"{VISUAL_FINDINGS_CONTRACT}; run --migrate first."
            ),
            path=path,
        )
    state_payload = read_json(state_root / "state.json")
    persisted_profiles = (
        state_payload.get("assurance_profiles")
        if isinstance(state_payload, dict)
        else None
    )
    if (
        not isinstance(persisted_profiles, list)
        or not persisted_profiles
        or not all(
            isinstance(item, str) for item in persisted_profiles
        )
    ):
        raise StateError(
            "assurance-profiles-migration-required",
            "state.json must persist valid assurance_profiles; run --migrate.",
            path=state_root / "state.json",
        )
    canonical_profiles = normalize_assurance_profiles(
        persisted_profiles
    )
    if list(canonical_profiles) != persisted_profiles:
        raise StateError(
            "assurance-profiles-migration-required",
            "state.json assurance_profiles are not canonical; run --migrate.",
            path=state_root / "state.json",
        )
    persisted_contract = (
        state_payload.get("evidence_contract")
        if isinstance(state_payload, dict)
        else None
    )
    if persisted_contract is None:
        evidence_capabilities = inferred_evidence_capabilities(
            canonical_profiles
        )
    else:
        evidence_capabilities, _extensions = validate_evidence_contract(
            persisted_contract,
            canonical_profiles,
        )
    body_failures = substantive_body_failures(
        record,
        body,
        project=project,
        record_path=path,
        required_assurance_profiles=canonical_profiles,
        required_evidence_capabilities=evidence_capabilities,
        evidence_contract=metadata.get("evidence_contract"),
        enforce_final_visual_binding=True,
    )
    if body_failures:
        raise StateError(
            "record-not-substantive",
            "The record is not complete enough to mark complete.",
            path=path,
            details={"failures": body_failures},
        )
    binding = safe_binding_path(
        project,
        binding_path,
        record_path=project / ".design-dna" / filename,
    )
    if not non_placeholder(binding_id):
        raise StateError(
            "invalid-record-binding",
            "binding_id must be an explicit build, commit, or artifact identity.",
            path=path,
        )
    if not non_placeholder(owner):
        raise StateError(
            "invalid-completion-owner",
            "completion_owner must identify an accountable reviewer.",
            path=path,
        )
    if not non_placeholder(limitations):
        raise StateError(
            "invalid-completion-limitations",
            "limitations must explicitly state known limits or that none are known in scope.",
            path=path,
        )
    try:
        completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        if completed.tzinfo is None:
            raise ValueError("timezone missing")
        if completed.astimezone(timezone.utc) > datetime.now(timezone.utc):
            raise ValueError("future time")
    except ValueError as exc:
        raise StateError(
            "invalid-completed-at",
            "completed_at must be a non-future ISO date-time with timezone.",
            path=path,
        ) from exc
    try:
        binding_hash = hashlib.sha256(binding.read_bytes()).hexdigest()
    except OSError as exc:
        raise StateError(
            "record-binding-read-failed",
            str(exc),
            path=binding,
        ) from exc
    updates = {
        "record_status": "complete",
        "record_body_sha256": body_sha256(body),
        "binding_kind": binding_kind,
        "binding_id": binding_id,
        "binding_path": binding_path,
        "binding_sha256": binding_hash,
        "completion_owner": owner,
        "completed_at": completed.astimezone(timezone.utc).isoformat(),
        "unresolved_high": "0",
        "unresolved_medium": "0",
        "limitations": limitations,
    }
    write_frontmatter_update(path, updates=updates)


def mark_record_draft(state_root: Path, record: str) -> None:
    filename = RECORD_TEMPLATES[record][0]
    path = state_root / filename
    if filename not in SUBSTANTIVE_RECORDS:
        raise StateError(
            "record-status-unsupported",
            f"{record} does not use the draft/complete evidence contract.",
            path=path,
        )
    if not path.is_file():
        raise StateError(
            "record-missing",
            f"Selected record does not exist: {record}.",
            path=path,
        )
    write_frontmatter_update(
        path,
        updates={"record_status": "draft"},
        removals=COMPLETE_RECORD_FIELDS,
    )


def add_recurrence_triggers(
    state_root: Path,
    triggers: tuple[str, ...],
) -> None:
    """Add owner workflow triggers to their paired evidence records.

    The trigger is intentionally not a cosmetic preference. It requires both
    Project Contrast and Direction Challenge evidence records so a later
    readiness result cannot present a recurrence escalation as a clean state.
    """

    if not triggers or any(trigger not in INITIALIZATION_TRIGGERS for trigger in triggers):
        raise StateError(
            "invalid-recurrence-trigger",
            "Only packaged owner workflow triggers may be added.",
            path=state_root,
        )
    manifest_path = state_root / "state.json"
    manifest = read_json(manifest_path)
    records = manifest.get("records") if isinstance(manifest, dict) else None
    required_records = set(OWNER_RECURRENCE_RECORDS)
    if not isinstance(records, list) or not required_records.issubset(records):
        raise StateError(
            "recurrence-records-required",
            "--add-trigger only updates an already paired state. Use --profile showcase with the applicable owner trigger to create or merge both Project Contrast and Direction Challenge records first.",
            path=manifest_path,
        )
    for record in OWNER_RECURRENCE_RECORDS:
        contract_path = state_root / RECORD_TEMPLATES[record][0]
        contract = read_json(contract_path)
        scope = contract.get("scope") if isinstance(contract, dict) else None
        current = scope.get("trigger") if isinstance(scope, dict) else None
        if not isinstance(current, list) or not all(isinstance(item, str) for item in current):
            raise StateError(
                "recurrence-trigger-shape-invalid",
                f"{contract_path.name} must contain a string trigger list before it can be updated.",
                path=contract_path,
            )
        merged = list(dict.fromkeys([*current, *triggers]))
        if merged == current:
            continue
        scope["trigger"] = merged
        try:
            rendered = json.dumps(contract, indent=2, ensure_ascii=False) + "\n"
            contract_path.write_text(rendered, encoding="utf-8", newline="\n")
        except OSError as exc:
            raise StateError(
                "recurrence-trigger-write-failed",
                str(exc),
                path=contract_path,
            ) from exc


def mutate_state_transaction(
    project: Path,
    current_version: str,
    *,
    action: str,
    dry_run: bool,
    mutator,
) -> list[dict[str, str]]:
    with ProjectMutationLock(project, action) as lock:
        actions = _mutate_state_transaction_locked(
            project,
            current_version,
            action=action,
            dry_run=dry_run,
            mutator=mutator,
            lock=lock,
        )
        return [*lock.recovery_actions(), *actions]


def _mutate_state_transaction_locked(
    project: Path,
    current_version: str,
    *,
    action: str,
    dry_run: bool,
    mutator,
    lock: ProjectMutationLock,
) -> list[dict[str, str]]:
    state_root = project / ".design-dna"
    assert_no_reparse_ancestors(state_root, stop=project)
    assert_safe_tree(state_root)
    if not state_root.is_dir():
        raise StateError(
            "state-missing",
            "Initialize .design-dna before migrating or changing record status.",
            path=state_root,
        )
    lock.assert_owned()
    source_identity = state_tree_identity(state_root)
    stage_parent: Path | None = None
    staged = project / ".design-dna.unallocated-stage"
    backup: Path | None = None
    backup_ignore_existed = False
    backup_guard_installed = False
    transition_started = False
    candidate_installed = False
    primary_error: StateError | None = None
    rollback_errors: list[StateError] = []
    failed_candidate: Path | None = None
    actions: list[dict[str, str]] = []
    try:
        stage_parent = create_transaction_stage_parent(
            project,
            ".design-dna-migrate-",
        )
        write_stage_owner(stage_parent, lock)
        staged = stage_parent / ".design-dna"
        assert_no_reparse_ancestors(stage_parent, stop=project)
        assert_contained(stage_parent, project)
        shutil.copytree(state_root, staged, symlinks=False)
        assert_safe_tree(staged)
        require_state_identity(
            staged,
            source_identity,
            code="staged-source-parity-mismatch",
            message="The staged source copy differs from the locked live state.",
        )
        mutator(staged)
        assert_safe_tree(staged)
        failures, warnings = validate_state_root(
            staged,
            project,
            current_version,
        )
        if failures:
            raise StateError(
                "staged-state-invalid",
                "The proposed state mutation did not validate.",
                path=staged,
                details={
                    "validation_failures": failures,
                    "validation_warnings": warnings,
                },
            )
        candidate_identity = state_tree_identity(staged)
        lock.assert_owned()
        require_state_identity(
            state_root,
            source_identity,
            code="source-state-changed",
            message=(
                "The live state changed after staging; refusing to promote "
                "a candidate based on stale source."
            ),
        )
        require_state_identity(
            staged,
            candidate_identity,
            code="candidate-state-changed",
            message="The staged mutation changed before promotion.",
        )
        if candidate_identity == source_identity:
            actions.append(
                {
                    "action": (
                        "migration-not-needed"
                        if action == "migrated"
                        else f"{action}:no-change"
                    ),
                    "path": str(state_root),
                    "validation": "passed",
                }
            )
        elif dry_run:
            actions.append(
                {
                    "action": f"would-{action}",
                    "path": str(state_root),
                    "validation": "passed",
                }
            )
        else:
            backup = unique_peer(state_root, "backup")
            assert_contained(backup, project)
            transition_started = True
            state_root.rename(backup)
            require_state_identity(
                backup,
                source_identity,
                code="backup-source-parity-mismatch",
                message="The renamed backup differs from the locked source state.",
            )
            backup_ignore_existed = install_backup_privacy_guard(backup)
            backup_guard_installed = True
            lock.assert_owned()
            require_state_identity(
                staged,
                candidate_identity,
                code="candidate-state-changed",
                message="The staged mutation changed during promotion.",
            )
            staged.rename(state_root)
            candidate_installed = True
            require_state_identity(
                state_root,
                candidate_identity,
                code="installed-candidate-parity-mismatch",
                message="The promoted state differs from the validated candidate.",
            )
            installed_failures, installed_warnings = validate_state(
                project,
                current_version,
            )
            if installed_failures:
                raise StateError(
                    "installed-state-invalid",
                    "Post-mutation validation failed.",
                    path=state_root,
                    details={
                        "validation_failures": installed_failures,
                        "validation_warnings": installed_warnings,
                    },
                )
            lock.assert_owned()
            require_state_identity(
                state_root,
                candidate_identity,
                code="installed-candidate-changed",
                message="The installed state changed during final validation.",
            )
            actions.extend(
                [{"action": action, "path": str(state_root)}]
            )
            if action == "migrated":
                actions.append(
                    {
                        "action": "backup-preserved",
                        "path": str(backup),
                        "reason": (
                            "The exact pre-migration state remains recoverable; "
                            "its privacy guard prevents accidental commits."
                        ),
                    }
                )
    except Exception as exc:
        primary_error = as_state_error(
            exc,
            code="state-mutation-failed",
            path=state_root,
        )
        if transition_started:
            failed_candidate, rollback_errors = rollback_transaction(
                state_root,
                staged,
                backup,
                project,
                candidate_installed=candidate_installed,
                backup_ignore_existed=backup_ignore_existed,
                backup_guard_installed=backup_guard_installed,
            )

    if primary_error is None and backup is not None and action != "migrated":
        backup_cleanup_error = cleanup_success_backup(backup, project)
        if backup_cleanup_error is None:
            actions.append(
                {
                    "action": "transaction-backup-removed",
                    "path": str(backup),
                    "reason": (
                        "The validated status-only mutation is installed; its "
                        "task-generated rollback copy is no longer needed."
                    ),
                }
            )
        else:
            actions.append(
                {
                    "action": "transaction-backup-preserved",
                    "path": str(backup),
                    "reason": json.dumps(
                        error_record(backup_cleanup_error),
                        ensure_ascii=False,
                    ),
                }
            )

    cleanup_error = cleanup_stage_parent(
        stage_parent,
        project,
        lock.owner_token,
    )
    if primary_error is not None:
        details = dict(primary_error.details)
        details["rollback"] = {
            "status": (
                "not-needed"
                if not transition_started
                else ("incomplete" if rollback_errors else "completed")
            ),
            "backup": str(backup) if backup is not None else None,
            "failed_candidate": (
                str(failed_candidate) if failed_candidate is not None else None
            ),
            "errors": [error_record(error) for error in rollback_errors],
        }
        if cleanup_error is not None:
            details["cleanup"] = error_record(cleanup_error)
        if rollback_errors:
            raise StateError(
                "rollback-failed",
                "State mutation failed and automatic rollback was incomplete.",
                path=state_root,
                details={"primary": error_record(primary_error), **details},
            ) from primary_error
        raise StateError(
            primary_error.code,
            str(primary_error),
            path=primary_error.path,
            details=details,
        ) from primary_error
    if cleanup_error is not None:
        actions.append(
            {
                "action": "staging-cleanup-preserved",
                "path": str(stage_parent),
                "reason": json.dumps(
                    error_record(cleanup_error),
                    ensure_ascii=False,
                ),
            }
        )
    return actions


def as_state_error(
    error: Exception,
    *,
    code: str,
    path: Path,
) -> StateError:
    if isinstance(error, StateError):
        return error
    if isinstance(error, PermissionError):
        return access_denied_state_error(error, path)
    return StateError(code, str(error), path=path)


def rollback_transaction(
    state_root: Path,
    staged: Path,
    backup: Path | None,
    project: Path,
    *,
    candidate_installed: bool,
    backup_ignore_existed: bool,
    backup_guard_installed: bool,
) -> tuple[Path | None, list[StateError]]:
    """Best-effort quarantine and restore without destroying diagnostic evidence."""
    failed: Path | None = None
    errors: list[StateError] = []
    candidate = state_root if candidate_installed else staged
    try:
        if entry_exists(candidate):
            failed = unique_peer(state_root, "failed")
            assert_contained(failed, project)
            candidate.rename(failed)
    except Exception as exc:
        errors.append(
            as_state_error(
                exc,
                code="failed-candidate-quarantine-failed",
                path=candidate,
            )
        )
    if backup is not None:
        try:
            if not entry_exists(backup):
                if not candidate_installed and entry_exists(state_root):
                    assert_safe_tree(state_root)
                    return failed, errors
                raise StateError(
                    "rollback-backup-missing",
                    "The prior-state backup is no longer available.",
                    path=backup,
                )
            if entry_exists(state_root):
                raise StateError(
                    "rollback-target-occupied",
                    "The state path is occupied, so the prior state cannot be restored safely.",
                    path=state_root,
                )
            if backup_guard_installed:
                remove_backup_privacy_guard(
                    backup,
                    backup_ignore_existed,
                )
            backup.rename(state_root)
            assert_safe_tree(state_root)
        except Exception as exc:
            errors.append(
                as_state_error(
                    exc,
                    code="prior-state-restore-failed",
                    path=backup,
                )
            )
    return failed, errors


def cleanup_stage_parent(
    stage_parent: Path | None,
    project: Path,
    owner_token: str,
) -> StateError | None:
    if stage_parent is None:
        return None
    try:
        if entry_exists(stage_parent):
            assert_no_reparse_ancestors(stage_parent, stop=project)
            assert_contained(stage_parent, project)
            if (
                stage_parent.parent != project
                or not stage_parent.name.startswith(
                    (".design-dna-stage-", ".design-dna-migrate-")
                )
            ):
                raise StateError(
                    "broad-stage-cleanup-refused",
                    "Only an exact direct transaction staging directory may be removed.",
                    path=stage_parent,
                )
            verify_stage_owner(stage_parent, owner_token)
            assert_safe_tree(stage_parent)
            shutil.rmtree(stage_parent)
    except Exception as exc:
        return as_state_error(
            exc,
            code="staging-cleanup-failed",
            path=stage_parent,
        )
    return None


def cleanup_success_backup(
    backup: Path | None,
    project: Path,
) -> StateError | None:
    """Remove only the exact task-generated rollback copy after verified success."""

    if backup is None:
        return None
    try:
        if entry_exists(backup):
            assert_no_reparse_ancestors(backup, stop=project)
            assert_contained(backup, project)
            if (
                backup.parent != project
                or not backup.name.startswith(".design-dna.backup-")
            ):
                raise StateError(
                    "broad-backup-cleanup-refused",
                    "Only an exact direct transaction backup may be removed.",
                    path=backup,
                )
            assert_safe_tree(backup)
            shutil.rmtree(backup)
    except Exception as exc:
        return as_state_error(
            exc,
            code="transaction-backup-cleanup-failed",
            path=backup,
        )
    return None


def install_transaction(
    project: Path,
    skill_root: Path,
    records: tuple[str, ...],
    *,
    force: bool,
    dry_run: bool,
    assurance_profiles: tuple[str, ...] = ("standard",),
    evidence_capabilities: tuple[str, ...] = (),
    triggers: tuple[str, ...] = (),
    version: str | None = None,
) -> list[dict[str, str]]:
    with ProjectMutationLock(project, "initialize") as lock:
        actions = _install_transaction_locked(
            project,
            skill_root,
            records,
            force=force,
            dry_run=dry_run,
            assurance_profiles=assurance_profiles,
            evidence_capabilities=evidence_capabilities,
            triggers=triggers,
            version=version,
            lock=lock,
        )
        return [*lock.recovery_actions(), *actions]


def _install_transaction_locked(
    project: Path,
    skill_root: Path,
    records: tuple[str, ...],
    *,
    force: bool,
    dry_run: bool,
    assurance_profiles: tuple[str, ...],
    evidence_capabilities: tuple[str, ...],
    triggers: tuple[str, ...],
    version: str | None = None,
    lock: ProjectMutationLock,
) -> list[dict[str, str]]:
    state_root = project / ".design-dna"
    assert_no_reparse_ancestors(state_root, stop=project)
    assert_safe_tree(state_root)
    version = release_version(skill_root) if version is None else version
    lock.assert_owned()
    source_identity = captured_state_identity(state_root)
    if dry_run:
        action = "replace" if entry_exists(state_root) and force else "merge"
        require_state_identity(
            state_root,
            source_identity,
            code="source-state-changed",
            message="The live state changed during initialization planning.",
        )
        return [{
            "action": f"would-{action}",
            "path": str(state_root),
            "records": ",".join(records),
            "assurance_profiles": ",".join(assurance_profiles),
            "evidence_capabilities": ",".join(evidence_capabilities),
            "triggers": ",".join(triggers),
        }]

    stage_parent: Path | None = None
    staged = project / ".design-dna.unallocated-stage"
    backup: Path | None = None
    backup_ignore_existed = False
    backup_guard_installed = False
    moved_existing = False
    transition_started = False
    candidate_installed = False
    primary_error: StateError | None = None
    rollback_errors: list[StateError] = []
    failed_candidate: Path | None = None
    actions: list[dict[str, str]] = []
    try:
        stage_parent = create_transaction_stage_parent(
            project,
            ".design-dna-stage-",
        )
        write_stage_owner(stage_parent, lock)
        staged = stage_parent / ".design-dna"
        assert_no_reparse_ancestors(stage_parent, stop=project)
        assert_contained(stage_parent, project)
        render_new_state(
            skill_root,
            staged,
            version,
            records,
            assurance_profiles,
            evidence_capabilities,
            triggers,
        )
        merge_existing(
            state_root,
            staged,
            force=force,
            selected=records,
            version=version,
            assurance_profiles=assurance_profiles,
            evidence_capabilities=evidence_capabilities,
            triggers=triggers,
        )
        assert_safe_tree(staged)

        failures, _ = validate_state_in_place(staged, project, version)
        if failures:
            raise StateError("staged-state-invalid", "; ".join(failures), path=staged)
        candidate_identity = state_tree_identity(staged)

        # Race-resistant recheck immediately before rename transitions.
        lock.assert_owned()
        assert_no_reparse_ancestors(state_root, stop=project)
        assert_contained(state_root, project)
        require_state_identity(
            state_root,
            source_identity,
            code="source-state-changed",
            message=(
                "The live state changed after staging; refusing to promote "
                "a candidate based on stale source."
            ),
        )
        require_state_identity(
            staged,
            candidate_identity,
            code="candidate-state-changed",
            message="The staged initialization changed before promotion.",
        )
        if entry_exists(state_root):
            backup = unique_peer(state_root, "backup")
            assert_contained(backup, project)
            transition_started = True
            state_root.rename(backup)
            require_state_identity(
                backup,
                source_identity,
                code="backup-source-parity-mismatch",
                message="The renamed backup differs from the locked source state.",
            )
            backup_ignore_existed = install_backup_privacy_guard(backup)
            backup_guard_installed = True
            moved_existing = True
        else:
            transition_started = True
        lock.assert_owned()
        require_state_identity(
            staged,
            candidate_identity,
            code="candidate-state-changed",
            message="The staged initialization changed during promotion.",
        )
        staged.rename(state_root)
        candidate_installed = True
        require_state_identity(
            state_root,
            candidate_identity,
            code="installed-candidate-parity-mismatch",
            message="The promoted state differs from the validated candidate.",
        )
        installed_failures, _ = validate_state(project, version)
        if installed_failures:
            raise StateError(
                "installed-state-invalid",
                "Post-install validation failed.",
                path=state_root,
                details={"validation_failures": installed_failures},
            )
        lock.assert_owned()
        require_state_identity(
            state_root,
            candidate_identity,
            code="installed-candidate-changed",
            message="The installed state changed during final validation.",
        )
        actions.append({"action": "installed", "path": str(state_root)})
        if moved_existing and backup is not None:
            if force:
                actions.append({
                    "action": "backup-preserved",
                    "path": str(backup),
                    "reason": (
                        "The forced refresh can replace owner-authored record "
                        "content, so the exact prior state remains recoverable."
                    ),
                })
            else:
                backup_cleanup_error = cleanup_success_backup(backup, project)
                if backup_cleanup_error is None:
                    actions.append({
                        "action": "transaction-backup-removed",
                        "path": str(backup),
                        "reason": (
                            "The validated additive merge preserved the live "
                            "record content; its task-generated rollback copy "
                            "is no longer needed."
                        ),
                    })
                else:
                    actions.append({
                        "action": "transaction-backup-preserved",
                        "path": str(backup),
                        "reason": json.dumps(
                            error_record(backup_cleanup_error),
                            ensure_ascii=False,
                        ),
                    })
            moved_existing = False
    except Exception as exc:
        primary_error = as_state_error(
            exc,
            code="initialization-failed",
            path=state_root,
        )
        if transition_started:
            failed_candidate, rollback_errors = rollback_transaction(
                state_root,
                staged,
                backup,
                project,
                candidate_installed=candidate_installed,
                backup_ignore_existed=backup_ignore_existed,
                backup_guard_installed=backup_guard_installed,
            )
            if not rollback_errors:
                moved_existing = False

    cleanup_error = cleanup_stage_parent(
        stage_parent,
        project,
        lock.owner_token,
    )
    if primary_error is not None:
        recovery: dict[str, object] = {
            "status": (
                "not-needed"
                if not transition_started
                else ("incomplete" if rollback_errors else "completed")
            ),
            "backup": str(backup) if backup is not None else None,
            "failed_candidate": (
                str(failed_candidate) if failed_candidate is not None else None
            ),
        }
        if rollback_errors:
            recovery["errors"] = [
                error_record(error) for error in rollback_errors
            ]
        details = dict(primary_error.details)
        details["rollback"] = recovery
        if cleanup_error is not None:
            details["cleanup"] = error_record(cleanup_error)
        if rollback_errors:
            raise StateError(
                "rollback-failed",
                "Initialization failed and automatic rollback was incomplete.",
                path=state_root,
                details={
                    "primary": error_record(primary_error),
                    **details,
                },
            ) from primary_error
        raise StateError(
            primary_error.code,
            str(primary_error),
            path=primary_error.path,
            details=details,
        ) from primary_error
    if cleanup_error is not None:
        actions.append({
            "action": "staging-cleanup-preserved",
            "path": str(stage_parent),
            "reason": json.dumps(error_record(cleanup_error), ensure_ascii=False),
        })
    return actions


def validate_state_in_place(
    state_root: Path,
    project: Path,
    current_version: str,
) -> tuple[list[str], list[str]]:
    """Validate staged records while resolving bindings in the real project."""

    return validate_state_root(state_root, project, current_version)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--force", action="store_true", help="Replace packaged template files; preserve other project records.")
    parser.add_argument("--dry-run", action="store_true")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--check-state", action="store_true")
    operation.add_argument(
        "--check-prebuild",
        action="store_true",
        help=(
            "Require project-specific direction, material/media, active contrast, "
            "and challenge proof/review evidence before broad implementation."
        ),
    )
    operation.add_argument(
        "--check-ready",
        action="store_true",
        help=(
            "Require structural validity plus every record listed in "
            "state.json to be complete under the persisted cumulative "
            "assurance capabilities."
        ),
    )
    operation.add_argument(
        "--print-asset-example",
        action="store_true",
        help=(
            "Print a complete schema-valid but release-blocked asset manifest "
            "example without reading or changing a project."
        ),
    )
    operation.add_argument(
        "--migrate",
        action="store_true",
        help=(
            "Safely add current record-status metadata and hash-bind preserved "
            "legacy records. The exact prior state is retained as a guarded backup."
        ),
    )
    operation.add_argument(
        "--mark-complete",
        choices=tuple(SUBSTANTIVE_RECORDS.values()),
        metavar="RECORD",
        help=(
            "Mark one substantive record complete after validating its content "
            "and binding it to an exact build/artifact file."
        ),
    )
    operation.add_argument(
        "--mark-draft",
        choices=tuple(SUBSTANTIVE_RECORDS.values()),
        metavar="RECORD",
        help="Return one substantive record to draft and remove stale completion metadata.",
    )
    operation.add_argument(
        "--add-trigger",
        action="append",
        choices=tuple(sorted(INITIALIZATION_TRIGGERS)),
        default=[],
        help=(
            "Add an owner workflow trigger to both already-initialized paired evidence "
            "records. It requires Project Contrast and Direction Challenge to be "
            "listed in state.json; it does not create a missing counterpart. "
            "Repeating a trigger is idempotent."
        ),
    )
    parser.add_argument(
        "--profile", choices=tuple(PROFILES), default="standard",
        help="Record set to initialize when --record is not supplied (default: standard).",
    )
    parser.add_argument(
        "--record", action="append", choices=tuple(RECORD_TEMPLATES),
        help=(
            "Create only this useful record; repeat to select more. Overrides "
            "--profile, including high-risk; use --profile high-risk without "
            "--record for its complete evidence set."
        ),
    )
    parser.add_argument(
        "--evidence-capability",
        action="append",
        default=[],
        metavar="SLUG",
        help=(
            "Add an applicable evidence capability without selecting an "
            "aesthetic recipe; repeat for cultural or project-specific risks. "
            "Project Contrast and Direction Challenge require their named "
            "profile or canonical record, while connected-public-experience "
            "creates its canonical record. High-risk uses --profile high-risk "
            "so its complete companion-record set is selected together."
        ),
    )
    parser.add_argument(
        "--trigger",
        action="append",
        choices=tuple(sorted(INITIALIZATION_TRIGGERS)),
        default=[],
        help=(
            "During initialization or merge, declare an owner workflow trigger. "
            "Both packaged triggers select Project Contrast and Direction Challenge "
            "records, their applicable capabilities, and the same trigger in both "
            "records. owner-pattern-contract additionally activates the installed "
            "owner-pattern audit. Triggers are available with --profile showcase, "
            "--profile project-contrast, --profile direction-challenge, or an "
            "explicit project-contrast or direction-challenge record."
        ),
    )
    parser.add_argument("--binding-kind", choices=("build", "artifact"))
    parser.add_argument(
        "--binding-id",
        help="Exact build, commit, or artifact identity for --mark-complete.",
    )
    parser.add_argument(
        "--binding-path",
        help=(
            "Safe POSIX path, relative to the project, for the immutable build "
            "or artifact file used by --mark-complete."
        ),
    )
    parser.add_argument(
        "--completion-owner",
        help="Accountable reviewer identity for --mark-complete.",
    )
    parser.add_argument(
        "--limitations",
        help=(
            "Known limitations, or an explicit statement that none are known "
            "within the reviewed scope."
        ),
    )
    parser.add_argument(
        "--completed-at",
        help=(
            "ISO date-time with timezone; defaults to the current UTC time for "
            "--mark-complete."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit a JSON success result as well as structured errors.")
    args = parser.parse_args()
    try:
        skill_root = Path(__file__).resolve().parents[1]
        version = release_version(skill_root)
        completion_values = {
            "--binding-kind": args.binding_kind,
            "--binding-id": args.binding_id,
            "--binding-path": args.binding_path,
            "--completion-owner": args.completion_owner,
            "--limitations": args.limitations,
            "--completed-at": args.completed_at,
        }
        if args.print_asset_example:
            if (
                 args.force
                 or args.dry_run
                 or args.record
                 or args.evidence_capability
                 or args.json
                or any(value is not None for value in completion_values.values())
            ):
                raise StateError(
                    "incompatible-arguments",
                    (
                        "--print-asset-example is a read-only raw-YAML output "
                        "mode and cannot be combined with mutation, record, "
                        "completion, or JSON-output arguments."
                    ),
                )
            example = (
                skill_root
                / "templates"
                / "asset-manifest.example.yml"
            ).read_text(encoding="utf-8")
            print(
                example.replace(
                    "__DESIGN_DNA_VERSION__",
                    f"design-dna {version}",
                ),
                end="",
            )
            return 0
        project = lexical_absolute(args.project)
        if not project.is_dir():
            raise StateError("project-not-found", "Project directory does not exist.", path=project)
        assert_no_reparse_ancestors(project)
        plugin_root = skill_root.parents[1]
        protected = plugin_root if (plugin_root / ".codex-plugin" / "plugin.json").is_file() else skill_root
        if project == protected or is_within(project, protected) or is_within(protected, project):
            raise StateError(
                "protected-destination",
                "Refusing to create state in or around the packaged skill/plugin.",
                path=project,
            )
        mutation_selected = bool(
            args.migrate or args.mark_complete or args.mark_draft
            or args.add_trigger
        )
        if args.mark_complete:
            missing_completion = [
                name
                for name, value in completion_values.items()
                if name != "--completed-at" and not value
            ]
            if missing_completion:
                raise StateError(
                    "completion-arguments-missing",
                    "--mark-complete requires "
                    + ", ".join(missing_completion)
                    + ".",
                    path=project / ".design-dna",
                )
        elif any(value is not None for value in completion_values.values()):
            raise StateError(
                "completion-arguments-unused",
                "Completion metadata arguments are valid only with --mark-complete.",
                path=project / ".design-dna",
            )
        if (
            args.check_state
            or args.check_prebuild
            or args.check_ready
            or mutation_selected
        ) and (
            args.force or args.record or args.evidence_capability or args.trigger
        ):
            raise StateError(
                "incompatible-arguments",
                "--force, --record, --evidence-capability, and --trigger apply only to "
                "initialization.",
                path=project,
            )
        if (args.check_state or args.check_prebuild or args.check_ready) and args.dry_run:
            raise StateError(
                "incompatible-arguments",
                "--dry-run is not used with state, prebuild, or readiness checks.",
                path=project,
            )
        if args.check_state or args.check_prebuild or args.check_ready:
            failures, warnings = validate_state(project, version)
            recurrence_failures = owner_recurrence_integration_failures(
                project / ".design-dna",
                require_resolved=True,
            )
            failures.extend(
                failure
                for failure in recurrence_failures
                if failure not in failures
            )
            owner_pattern_phase = (
                "ready"
                if args.check_ready
                else "prebuild"
                if args.check_prebuild
                else "state"
            )
            pattern_failures = owner_pattern_contract_failures(
                project,
                phase=owner_pattern_phase,
            )
            failures.extend(
                failure
                for failure in pattern_failures
                if failure not in failures
            )
            if args.check_prebuild:
                phase_failures = prebuild_failures(project)
                failures.extend(
                    failure for failure in phase_failures if failure not in failures
                )
                warnings.extend(
                    warning
                    for warning in prebuild_warnings(project)
                    if warning not in warnings
                )
            if not failures and args.check_ready:
                failures.extend(readiness_failures(project))
            result = {"ok": not failures, "project": str(project), "version": version, "failures": failures, "warnings": warnings}
            print(json.dumps(result, indent=2) if args.json else "\n".join(
                [*(f"FAIL: {item}" for item in failures), *(f"WARN: {item}" for item in warnings)]
                or [
                    (
                        "OK: Every listed Design DNA evidence record is ready "
                        "under the selected assurance capabilities."
                        if args.check_ready
                        else (
                            "OK: Design DNA prebuild evidence permits broad implementation."
                            if args.check_prebuild
                            else (
                                "OK: Design DNA state schema "
                                f"{STATE_SCHEMA_VERSION} is current."
                            )
                        )
                    )
                ]
            ))
            return 1 if failures else 0
        if args.migrate:
            actions = mutate_state_transaction(
                project,
                version,
                action="migrated",
                dry_run=args.dry_run,
                mutator=lambda staged: migrate_staged_state(staged, version),
            )
            result = {
                "ok": True,
                "project": str(project),
                "version": version,
                "actions": actions,
            }
            print(
                json.dumps(result, indent=2)
                if args.json
                else "\n".join(
                    f"{item['action']}: {item['path']}"
                    for item in actions
                )
            )
            return 0
        if args.add_trigger:
            selected_add_triggers = tuple(dict.fromkeys(args.add_trigger))
            actions = mutate_state_transaction(
                project,
                version,
                action="added-recurrence-trigger",
                dry_run=args.dry_run,
                mutator=lambda staged: add_recurrence_triggers(
                    staged,
                    selected_add_triggers,
                ),
            )
            current_contract = read_json(
                project / ".design-dna" / "project-contrast.json"
            )
            scope = (
                current_contract.get("scope")
                if isinstance(current_contract, dict)
                else None
            )
            persisted_triggers = (
                scope.get("trigger")
                if isinstance(scope, dict)
                and isinstance(scope.get("trigger"), list)
                else []
            )
            result = {
                "ok": True,
                "project": str(project),
                "version": version,
                "triggers": persisted_triggers,
                "actions": actions,
            }
            print(
                json.dumps(result, indent=2)
                if args.json
                else "\n".join(
                    f"{item['action']}: {item['path']}"
                    for item in actions
                )
            )
            return 0
        if args.mark_complete:
            completed_at = (
                args.completed_at
                or datetime.now(timezone.utc).isoformat()
            )
            actions = mutate_state_transaction(
                project,
                version,
                action=f"marked-complete:{args.mark_complete}",
                dry_run=args.dry_run,
                mutator=lambda staged: mark_record_complete(
                    staged,
                    project,
                    args.mark_complete,
                    binding_kind=str(args.binding_kind),
                    binding_id=str(args.binding_id),
                    binding_path=str(args.binding_path),
                    owner=str(args.completion_owner),
                    limitations=str(args.limitations),
                    completed_at=completed_at,
                ),
            )
            result = {
                "ok": True,
                "project": str(project),
                "version": version,
                "record": args.mark_complete,
                "actions": actions,
            }
            print(
                json.dumps(result, indent=2)
                if args.json
                else "\n".join(
                    f"{item['action']}: {item['path']}"
                    for item in actions
                )
            )
            return 0
        if args.mark_draft:
            actions = mutate_state_transaction(
                project,
                version,
                action=f"marked-draft:{args.mark_draft}",
                dry_run=args.dry_run,
                mutator=lambda staged: mark_record_draft(
                    staged,
                    args.mark_draft,
                ),
            )
            result = {
                "ok": True,
                "project": str(project),
                "version": version,
                "record": args.mark_draft,
                "actions": actions,
            }
            print(
                json.dumps(result, indent=2)
                if args.json
                else "\n".join(
                    f"{item['action']}: {item['path']}"
                    for item in actions
                )
            )
            return 0
        selected_triggers = tuple(dict.fromkeys(args.trigger))
        trigger_profile_allowed = args.profile in {
            "showcase", "project-contrast", "direction-challenge",
        }
        trigger_record_allowed = bool(
            args.record
            and (
                "project-contrast" in args.record
                or "direction-challenge" in args.record
            )
        )
        if selected_triggers and not (trigger_profile_allowed or trigger_record_allowed):
            raise StateError(
                "trigger-profile-mismatch",
                "Owner workflow triggers require --profile showcase, --profile project-contrast, --profile direction-challenge, or an explicit recurrence record.",
                path=project,
            )
        selected_evidence_capabilities = normalize_evidence_capabilities(
            [
                *args.evidence_capability,
                *(
                    capability
                    for trigger in selected_triggers
                    for capability in TRIGGER_EVIDENCE_CAPABILITIES[trigger]
                ),
            ]
        )
        selected = tuple(dict.fromkeys([
            *(args.record or PROFILES[args.profile]),
            *(
                record
                for trigger in selected_triggers
                for record in TRIGGER_RECORDS[trigger]
            ),
            *(
                "connected-public-experience"
                for capability in selected_evidence_capabilities
                if capability == "connected-public-experience"
            ),
            *(
                "reference-dossier"
                for capability in selected_evidence_capabilities
                if capability in {
                    "enterprise-candidate",
                    "reference-led-direction",
                }
            ),
            *(
                "route-manifest"
                for capability in selected_evidence_capabilities
                if capability in {
                    "enterprise-candidate",
                    "reference-led-direction",
                }
            ),
        ]))
        require_capability_record_selection(
            selected_evidence_capabilities,
            selected,
        )
        selected_profile = "custom" if args.record else args.profile
        selected_assurance_profiles = assurance_profiles_for_request(
            selected_profile,
            selected,
        )
        if selected_triggers:
            selected_assurance_profiles = normalize_assurance_profiles(
                [
                    *selected_assurance_profiles,
                    "project-contrast",
                    "direction-challenge",
                ]
            )
        if "connected-public-experience" in selected_evidence_capabilities:
            selected_assurance_profiles = normalize_assurance_profiles(
                [
                    *selected_assurance_profiles,
                    "connected-public-experience",
                ]
            )
        actions = install_transaction(
            project,
            skill_root,
            selected,
            force=args.force,
            dry_run=args.dry_run,
            assurance_profiles=selected_assurance_profiles,
            evidence_capabilities=selected_evidence_capabilities,
            triggers=selected_triggers,
            version=version,
        )
        effective_profiles = list(selected_assurance_profiles)
        effective_records = list(selected)
        effective_capabilities = list(
            normalize_evidence_capabilities(
                expand_enterprise_candidate_requirements([
                    *inferred_evidence_capabilities(
                        selected_assurance_profiles
                    ),
                    *selected_evidence_capabilities,
                ])
            )
        )
        result_scope = "planned-request" if args.dry_run else "persisted-effective-state"
        if not args.dry_run:
            # Installation is additive.  Report the state that was actually
            # promoted, not only the fragment named by this invocation.  The
            # old response made `--record reference-dossier` look as though it
            # had replaced a Showcase/Contrast/Challenge state with a lone
            # Standard record even when the transaction had preserved it.
            persisted = read_json(project / ".design-dna" / "state.json")
            if not isinstance(persisted, dict):
                raise StateError(
                    "promoted-state-unreadable",
                    "The transaction completed but the promoted state.json could not be read.",
                    path=project / ".design-dna" / "state.json",
                )
            persisted_profiles = persisted.get("assurance_profiles")
            persisted_records = persisted.get("records")
            if (
                not isinstance(persisted_profiles, list)
                or not all(isinstance(item, str) for item in persisted_profiles)
                or not isinstance(persisted_records, list)
                or not all(isinstance(item, str) for item in persisted_records)
            ):
                raise StateError(
                    "promoted-state-invalid",
                    "The transaction promoted an invalid assurance profile or record inventory.",
                    path=project / ".design-dna" / "state.json",
                )
            effective_profiles = list(persisted_profiles)
            effective_records = list(persisted_records)
            persisted_contract = persisted.get("evidence_contract")
            if isinstance(persisted_contract, dict):
                persisted_capabilities = persisted_contract.get(
                    "applicable_capabilities"
                )
                if isinstance(persisted_capabilities, list) and all(
                    isinstance(item, str) for item in persisted_capabilities
                ):
                    effective_capabilities = list(persisted_capabilities)
        result = {
            "ok": True,
            "project": str(project),
            "version": version,
            "assurance_profile": selected_profile,
            "result_scope": result_scope,
            "assurance_profiles": effective_profiles,
            "triggers": list(selected_triggers),
            "evidence_capabilities": effective_capabilities,
            "records": effective_records,
            "requested": {
                "assurance_profiles": list(selected_assurance_profiles),
                "evidence_capabilities": list(selected_evidence_capabilities),
                "records": list(selected),
                "triggers": list(selected_triggers),
            },
            "actions": actions,
        }
        print(json.dumps(result, indent=2) if args.json else "\n".join(
            f"{item['action']}: {item['path']}" for item in actions
        ))
        return 0
    except StateError as exc:
        emit_error(exc)


if __name__ == "__main__":
    raise SystemExit(main())
