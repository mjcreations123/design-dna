"""Validate attributable, candidate-specific selection reviews, without grading beauty.

This verifies review evidence and unresolved dispositions.  It cannot establish
that a reviewer has good taste, that a declared identity is cryptographically
authenticated, or that the owner accepts a design.  The complete source-study
validator and the later rendered signature-transfer gates remain mandatory.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable


DIMENSIONS = frozenset({"organization", "audience", "visitor-jobs", "content", "route-jobs", "media", "access", "quality"})
RECORD_TYPE = "design-dna-candidate-selection-review"
SHA = re.compile(r"[0-9a-f]{64}\Z")
GENERIC = re.compile(r"^(?:pass|good|great|beautiful|matches|compatible|relevant|approved|looks good|no issues|yes|n/?a|not applicable)[.! ]*$", re.I)


def canonical_sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _substantive(value: object) -> bool:
    if not isinstance(value, str) or GENERIC.fullmatch(value.strip()):
        return False
    words = re.findall(r"\w+", value.casefold())
    return len(value.strip()) >= 40 and len(words) >= 8 and len(set(words)) >= 6 and not re.search(r"__REPLACE|\bTODO\b|\bTBD\b", value, re.I)


def _file(project: Path, binding: object, label: str) -> Path:
    if not isinstance(binding, dict) or set(binding) != {"path", "bytes", "sha256"}:
        raise ValueError(f"{label} needs exact path/bytes/SHA-256 evidence.")
    raw = binding.get("path")
    if (not isinstance(raw, str) or not raw or "\\" in raw or ":" in raw or PurePosixPath(raw).is_absolute()
            or ".." in PurePosixPath(raw).parts or PurePosixPath(raw).as_posix() != raw
            or type(binding.get("bytes")) is not int or binding["bytes"] < 1
            or not isinstance(binding.get("sha256"), str) or not SHA.fullmatch(binding["sha256"])):
        raise ValueError(f"{label} has an unsafe or incomplete artifact binding.")
    file = project / raw
    cursor = project
    for part in PurePosixPath(raw).parts:
        cursor /= part
        info = cursor.lstat()
        reparse = bool(getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        tag = getattr(info, "st_reparse_tag", 0)
        redirected = reparse and (not tag or bool(tag & 0x20000000) or tag in {0xA0000003, 0xA000000C})
        if stat.S_ISLNK(info.st_mode) or redirected:
            raise ValueError(f"{label} cannot traverse a symlink/junction.")
    if not file.is_file():
        raise ValueError(f"{label} is not an ordinary file.")
    before = file.stat()
    if before.st_nlink != 1:
        raise ValueError(f"{label} cannot use a hardlink alias to mutable external bytes.")
    content = file.read_bytes()
    after = file.stat()
    if (before.st_ino != after.st_ino or before.st_mtime_ns != after.st_mtime_ns
            or before.st_size != after.st_size or after.st_nlink != 1):
        raise ValueError(f"{label} changed while its evidence was read.")
    if len(content) != binding["bytes"] or hashlib.sha256(content).hexdigest() != binding["sha256"]:
        raise ValueError(f"{label} artifact bytes drifted.")
    return file


def _pointer(payload: object, value: object) -> object:
    if not isinstance(value, str) or not value.startswith("/") or value == "/":
        raise ValueError("Source evidence needs one exact JSON pointer into generated observation.")
    current = payload
    for raw in value[1:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if key not in current:
                raise ValueError(f"Source evidence pointer does not exist: {value}")
            current = current[key]
        elif isinstance(current, list) and re.fullmatch(r"0|[1-9][0-9]*", key) and int(key) < len(current):
            current = current[int(key)]
        else:
            raise ValueError(f"Source evidence pointer cannot resolve: {value}")
    if current is None or current is False or current in ("", [], {}):
        raise ValueError(f"Source evidence points to an empty/non-observation value: {value}")
    return current


def _evidence(row: object, observation: dict, frames: dict, label: str) -> tuple[str, str]:
    expected = {"viewport", "state_id", "capture", "pointer", "value_sha256", "observed_fact"}
    if not isinstance(row, dict) or set(row) != expected or row.get("viewport") not in {"wide", "narrow"}:
        raise ValueError(f"{label} needs an exact viewport/state/capture/generated-value observation.")
    profile = row["viewport"]
    state_id = row.get("state_id")
    if row["capture"] != frames[profile]["capture"] or state_id != frames[profile]["state_id"]:
        raise ValueError(f"{label} does not bind the reviewed source state and canonical capture.")
    pointer = row.get("pointer")
    # Cross-viewport facts and broad source metadata are not visual evidence.
    prefixes = (f"/states_by_viewport/{profile}/{state_id}/", f"/first_screens/{profile}/",
                f"/mechanisms_by_viewport/{profile}/", f"/interaction_census_by_viewport/{profile}/")
    if not isinstance(pointer, str) or not pointer.startswith(prefixes):
        raise ValueError(f"{label} must point to generated facts for its own source state/viewport.")
    value = _pointer(observation, pointer)
    if canonical_sha(value) != row.get("value_sha256") or not _substantive(row.get("observed_fact")):
        raise ValueError(f"{label} has generic prose or does not bind the exact measured source fact.")
    return profile, pointer


def candidate_review_failures(
    project: Path,
    payload: object,
    *,
    brief_path: Path,
    observation_path: Path,
    candidate_id: str,
    validate_observation: Callable[[dict], list[str]],
    require_selected: bool = True,
) -> list[str]:
    """Require complete selected-source study plus an explicit attributable fit review.

    The caller supplies its full generated-source validator.  Inaccessible or
    incomplete candidates remain rejected/blocked in the discovery dossier;
    they cannot use this selected-candidate evidence lane to become eligible.
    """
    failures = []
    try:
        project = project.resolve()
        expected_top = {"schema_version", "record_type", "candidate_id", "brief", "source", "reviewer", "reviewed_at",
                        "judgments", "dominant_experience", "concerns", "decision", "assurance"}
        if not isinstance(payload, dict) or set(payload) != expected_top or payload.get("schema_version") != 1 or payload.get("record_type") != RECORD_TYPE or payload.get("candidate_id") != candidate_id:
            return ["Candidate selection needs the exact versioned, candidate-specific review record."]
        brief = _file(project, payload["brief"], "Candidate current brief")
        if brief.resolve() != brief_path.resolve():
            failures.append("Candidate review does not bind the project's current brief artifact.")
        brief_text = brief.read_text(encoding="utf-8")
        source = payload["source"]
        if not isinstance(source, dict) or set(source) != {"id", "url", "observation", "states"}:
            return [*failures, "Candidate review source needs exact ID/URL/observation and wide+narrow state captures."]
        observation_file = _file(project, source["observation"], "Candidate source observation")
        if observation_file.resolve() != observation_path.resolve():
            failures.append("Candidate review references a different source observation artifact.")
        observation = json.loads(observation_file.read_text(encoding="utf-8"))
        if not isinstance(observation, dict) or source["id"] != candidate_id or source["id"] != observation.get("id") or source["url"] != observation.get("url"):
            return [*failures, "Candidate review source identity differs from its generated observation."]
        if not callable(validate_observation):
            return [*failures, "Candidate selection requires the full packaged source-study validator; a pass flag cannot replace it."]
        source_failures = validate_observation(observation)
        if not isinstance(source_failures, list) or not all(isinstance(item, str) for item in source_failures):
            return [*failures, "Candidate source validator did not return its complete failure list."]
        failures.extend(source_failures)
        if (observation.get("source_kind", "public-source") != "public-source"
                or observation.get("source_study", {}).get("status") != "complete"
                or observation.get("source_study", {}).get("eligible_for_source_selection") is not True):
            failures.append("Partial, failed, proof-only, consent-blocked, and inaccessible sources cannot become selected references.")
        frames = source["states"]
        if not isinstance(frames, dict) or set(frames) != {"wide", "narrow"}:
            return [*failures, "Candidate review lacks separate wide and narrow source-state captures."]
        for profile in ("wide", "narrow"):
            row = frames[profile]
            if not isinstance(row, dict) or set(row) != {"state_id", "state_sha256", "capture"}:
                return [*failures, f"Candidate {profile} state binding is incomplete."]
            state = observation.get("states_by_viewport", {}).get(profile, {}).get(row["state_id"])
            if not isinstance(state, dict) or canonical_sha(state) != row["state_sha256"]:
                return [*failures, f"Candidate {profile} state hash does not match the generated source."]
            frame = state.get("evidence_frames", {}).get("settled")
            if not isinstance(frame, dict):
                return [*failures, f"Candidate {profile} source state lacks its generated settled frame."]
            expected_capture = {"path": (observation_file.parent.relative_to(project) / frame["file"]).as_posix(), "bytes": frame["bytes"], "sha256": frame["sha256"]}
            if row["capture"] != expected_capture:
                failures.append(f"Candidate {profile} review capture is not the canonical observed arrangement.")
            capture = _file(project, row["capture"], f"Candidate {profile} capture")
            if not capture.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                failures.append(f"Candidate {profile} capture is not PNG evidence.")
        reviewer = payload["reviewer"]
        if (not isinstance(reviewer, dict) or set(reviewer) != {"identity", "kind", "producer_identity", "evidence"}
                or reviewer.get("kind") not in {"producer-self-review", "independent-agent", "human-review"}
                or not isinstance(reviewer.get("identity"), str) or len(reviewer["identity"].strip()) < 3
                or not isinstance(reviewer.get("producer_identity"), str) or len(reviewer["producer_identity"].strip()) < 3):
            return [*failures, "Candidate review must identify the reviewer and explicitly distinguish self, independent-agent, and human review."]
        if (reviewer["kind"] == "producer-self-review") != (reviewer["identity"] == reviewer["producer_identity"]):
            failures.append("Candidate review mislabels producer self-review as independent, or misidentifies the self reviewer.")
        reviewed_at = datetime.fromisoformat(str(payload["reviewed_at"]).replace("Z", "+00:00"))
        if reviewed_at.tzinfo is None or reviewed_at > datetime.now(timezone.utc):
            failures.append("Candidate review needs a real, timezone-aware, non-future review time.")
        observed_at = datetime.fromisoformat(str(observation.get("observed_at", "")).replace("Z", "+00:00"))
        if observed_at.tzinfo is None or reviewed_at.tzinfo is None or reviewed_at < observed_at:
            failures.append("Candidate review predates the generated source observation it claims to review.")
        reviewer_file = _file(project, reviewer["evidence"], "Original attributable candidate review")
        original = json.loads(reviewer_file.read_text(encoding="utf-8"))
        expected_original = {"reviewer_identity": reviewer["identity"], "reviewer_kind": reviewer["kind"],
            "producer_identity": reviewer["producer_identity"], "reviewed_at": payload["reviewed_at"],
            "candidate_id": candidate_id, "brief_sha256": payload["brief"]["sha256"],
            "observation_sha256": source["observation"]["sha256"], "judgments": payload["judgments"],
            "dominant_experience": payload["dominant_experience"], "concerns": payload["concerns"], "decision": payload["decision"]}
        if original != expected_original:
            failures.append("Candidate review differs from the original attributable reviewer artifact or its exact brief/source scope.")
        judgments = payload["judgments"]
        if not isinstance(judgments, list) or len(judgments) != len(DIMENSIONS) or {row.get("dimension") for row in judgments if isinstance(row, dict)} != DIMENSIONS:
            return [*failures, "Candidate review must cover organization, audience, visitor jobs, content, route jobs, media, access, and quality exactly once."]
        notes = []
        for row in judgments:
            if set(row) != {"dimension", "brief_excerpt", "fit", "reason", "observations"}:
                failures.append("Candidate fit judgment has an unsupported shape.")
                continue
            dimension = row["dimension"]
            if not isinstance(row["brief_excerpt"], str) or len(row["brief_excerpt"].strip()) < 12 or row["brief_excerpt"] not in brief_text:
                failures.append(f"Candidate {dimension} judgment does not quote a real current brief requirement.")
            if row["fit"] not in {"compatible", "mismatch", "unresolved", "not-applicable"} or not _substantive(row["reason"]):
                failures.append(f"Candidate {dimension} has generic pass flags instead of a specific fit judgment.")
            if require_selected and row["fit"] not in {"compatible", "not-applicable"}:
                failures.append(f"Selected candidate has {row['fit']} {dimension} fit: {row['reason']}")
            notes.append(str(row["reason"]).strip().casefold())
            observations = row["observations"]
            if not isinstance(observations, list) or len(observations) < 2:
                failures.append(f"Candidate {dimension} lacks source-specific wide/narrow observations.")
            else:
                profiles = {_evidence(item, observation, frames, f"Candidate {dimension}")[0] for item in observations}
                if profiles != {"wide", "narrow"}:
                    failures.append(f"Candidate {dimension} review omits a source viewport.")
        if len(notes) != len(set(notes)):
            failures.append("Candidate review repeats generic rationale across distinct brief dimensions.")
        experience = payload["dominant_experience"]
        if not isinstance(experience, dict) or set(experience) != {"kind", "description", "signature_evidence", "supporting_relationships", "planned_carriers", "deletion_effect"}:
            return [*failures, "Candidate needs a dominant memorable experience and explicit source-signature carrier plan."]
        if experience["kind"] not in {"composition", "behavior"} or not _substantive(experience["description"]) or not _substantive(experience["deletion_effect"]):
            failures.append("A source color, font, card, isolated detail, or pass flag cannot substitute for its dominant experience.")
        signature = experience["signature_evidence"]
        if not isinstance(signature, list) or len(signature) != 2:
            failures.append("Candidate dominant experience needs exact wide+narrow generated signature evidence.")
        else:
            profiles = set()
            for row in signature:
                profile, pointer = _evidence(row, observation, frames, "Dominant source signature")
                profiles.add(profile)
                value = _pointer(observation, pointer)
                if experience["kind"] == "composition":
                    if not isinstance(value, dict) or not (pointer.endswith("/structure") or re.fullmatch(r"/first_screens/(wide|narrow)/dominant", pointer)) or not (value.get("dominant") or "area_share" in value):
                        failures.append("Composition signature must bind the generated dominant arrangement, not a color/font/card token.")
                elif not ("/mechanisms/" in pointer or pointer.endswith("/mechanisms")) or not isinstance(value, (dict, list)):
                    failures.append("Behavior signature must bind generated observed mechanisms, not an isolated style token.")
            if profiles != {"wide", "narrow"}:
                failures.append("Dominant source signature duplicates one viewport instead of observing both.")
        relationships = experience["supporting_relationships"]
        if not isinstance(relationships, list) or len(relationships) < 2:
            failures.append("Dominant source transfer needs the supporting composition/behavior relationships that make it work.")
        else:
            relationship_texts = []
            for relation in relationships:
                if not isinstance(relation, dict) or set(relation) != {"relationship", "evidence"} or not _substantive(relation["relationship"]):
                    failures.append("Source supporting relationship is generic or incomplete.")
                    continue
                _evidence(relation["evidence"], observation, frames, "Source supporting relationship")
                relationship_texts.append(relation["relationship"].strip().casefold())
            if len(relationship_texts) != len(set(relationship_texts)):
                failures.append("Source signature repeats one supporting detail instead of recording its relationships.")
        carriers = experience["planned_carriers"]
        if not isinstance(carriers, list) or not carriers:
            failures.append("Selected source has no planned route/component carrier for its dominant signature.")
        else:
            seen = set()
            for carrier in carriers:
                if not isinstance(carrier, dict) or set(carrier) != {"route_key", "component_id", "transfer_relationship", "source_evidence"} or not all(isinstance(carrier.get(key), str) and re.fullmatch(r"[a-z][a-z0-9-]{1,63}", carrier[key]) for key in ("route_key", "component_id")) or not _substantive(carrier.get("transfer_relationship")):
                    failures.append("Source signature carrier must identify its actual planned route/component relationship.")
                    continue
                identity = (carrier["route_key"], carrier["component_id"])
                if identity in seen:
                    failures.append("Source signature repeats a planned carrier instead of binding a distinct consumer.")
                seen.add(identity)
                if carrier["source_evidence"] != signature:
                    failures.append("Planned carrier must transfer this exact dominant wide+narrow source signature.")
        concerns = payload["concerns"]
        if not isinstance(concerns, list):
            failures.append("Candidate concerns must be explicit; unresolved negative review cannot disappear in prose.")
        else:
            for concern in concerns:
                if not isinstance(concern, dict) or set(concern) != {"description", "status", "resolution", "evidence"} or concern.get("status") not in {"unresolved", "resolved"} or not _substantive(concern.get("description")):
                    failures.append("Candidate concern is missing its negative observation and explicit disposition.")
                    continue
                _evidence(concern["evidence"], observation, frames, "Candidate concern")
                if concern["status"] == "resolved" and not _substantive(concern["resolution"]):
                    failures.append("Candidate concern claims resolution without evidence-backed reasoning.")
                if require_selected and concern["status"] == "unresolved":
                    failures.append("Selected candidate retains an unresolved negative review: " + concern["description"])
        decision = payload["decision"]
        if not isinstance(decision, dict) or set(decision) != {"status", "reason"} or decision.get("status") not in {"selected", "rejected", "blocked"} or not _substantive(decision.get("reason")):
            failures.append("Candidate selection decision must be explicit and supported by its own observed evidence.")
        elif require_selected and decision["status"] != "selected":
            failures.append("Rejected or blocked research is not a selected reference.")
        if payload["assurance"] != {"scope": "attributable-review-evidence-only", "automatic_beauty_verdict": False, "owner_approval": False, "independent_identity_authenticated": False}:
            failures.append("Candidate review must not claim algorithmic beauty, owner approval, or cryptographically authenticated independence.")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        failures.append("Candidate review evidence could not be validated: " + str(exc))
    return failures


def scaffold_candidate_review(project: Path, *, brief_path: Path, observation_path: Path, candidate_id: str) -> dict:
    """Prepare exact raw bindings, with every judgment explicitly pending.

    This is an operator aid only. It does not create a reviewer artifact, choose
    a signature, supply fit reasoning, or make the candidate eligible.
    """
    project = project.resolve()
    def binding(file: Path) -> dict:
        file = file.resolve()
        relative = file.relative_to(project).as_posix()
        data = file.read_bytes()
        result = {"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        _file(project, result, "Candidate scaffold input")
        return result
    brief_binding = binding(brief_path)
    observation_binding = binding(observation_path)
    observed = json.loads(observation_path.read_text(encoding="utf-8"))
    if observed.get("id") != candidate_id:
        raise ValueError("Candidate scaffold ID must equal its exact source observation ID.")
    frames = {}
    for profile in ("wide", "narrow"):
        state = observed.get("states_by_viewport", {}).get(profile, {}).get("rest")
        if not isinstance(state, dict) or not isinstance(state.get("evidence_frames", {}).get("settled"), dict):
            raise ValueError(f"Candidate scaffold requires a generated {profile} rest-state settled capture.")
        frame = state["evidence_frames"]["settled"]
        actual = binding(observation_path.parent / frame["file"])
        if actual["bytes"] != frame["bytes"] or actual["sha256"] != frame["sha256"]:
            raise ValueError(f"Candidate scaffold {profile} source frame bytes drifted.")
        frames[profile] = {"state_id": "rest", "state_sha256": canonical_sha(state), "capture": actual}
    return {
        "schema_version": 1, "record_type": RECORD_TYPE, "candidate_id": candidate_id,
        "brief": brief_binding, "source": {"id": candidate_id, "url": observed["url"], "observation": observation_binding, "states": frames},
        "reviewer": {"identity": "__REPLACE_WITH_ACTUAL_REVIEWER_IDENTITY__", "kind": "pending", "producer_identity": "__REPLACE_WITH_ACTUAL_PRODUCER_IDENTITY__",
            "evidence": {"path": f".design-dna/reviews/{candidate_id}-original-review.json", "bytes": 0, "sha256": "__PENDING_ATTRIBUTABLE_REVIEW__"}},
        "reviewed_at": "__PENDING_ACTUAL_REVIEW_TIME__",
        "judgments": [{"dimension": dimension, "brief_excerpt": "__REPLACE_WITH_EXACT_CURRENT_BRIEF_EXCERPT__", "fit": "unresolved",
            "reason": "__PENDING_CANDIDATE_SPECIFIC_REVIEW__", "observations": []} for dimension in sorted(DIMENSIONS)],
        "dominant_experience": {"kind": "pending", "description": "__PENDING_DOMINANT_SOURCE_EXPERIENCE__", "signature_evidence": [],
            "supporting_relationships": [], "planned_carriers": [], "deletion_effect": "__PENDING_SOURCE_RECOGNITION_DELETION_REVIEW__"},
        "concerns": [], "decision": {"status": "blocked", "reason": "__PENDING_ATTRIBUTABLE_SELECTION_REVIEW__"},
        "assurance": {"scope": "attributable-review-evidence-only", "automatic_beauty_verdict": False, "owner_approval": False, "independent_identity_authenticated": False},
    }
