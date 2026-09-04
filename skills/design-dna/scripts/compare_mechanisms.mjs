#!/usr/bin/env node
/** Compare every build route/profile with its explicitly mapped reference. */

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { finalizeMechanisms, firstScreenSheet, mechanismPass, mechanismWeight, median } from "./observe_reference.mjs";
import {
  aggregateServedContent,
  applyManifestState,
  beginServedContentCapture,
  canonicalJson,
  captureInteractionCensus,
  installDomInspection,
  navigateExact,
} from "./browser_evidence.mjs";
import {
  bindSuppliedObservations,
  loadRouteManifest,
  PRODUCER_OUTPUT_SCHEMA_VERSION,
} from "./provenance_contract.mjs";
import { browserExecutableIdentity, discoverBrowserExecutable, resolvePlaywright } from "./playwright_resolver.mjs";

const TOOL_NAME = "compare_mechanisms.mjs";
const SCHEMA_VERSION = PRODUCER_OUTPUT_SCHEMA_VERSION;
const SCRIPT_PATH = path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const SCRIPT_DIR = path.dirname(SCRIPT_PATH);
const PRODUCER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(SCRIPT_PATH)).digest("hex");
const OBSERVER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "observe_reference.mjs"))).digest("hex");
const BROWSER_EVIDENCE_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "browser_evidence.mjs"))).digest("hex");
const PLAYWRIGHT_RESOLVER_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "playwright_resolver.mjs"))).digest("hex");
const PROVENANCE_CONTRACT_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "provenance_contract.mjs"))).digest("hex");
const SIGNIFICANT_TYPES = new Set([
  "pinned", "parallax", "reveal", "swap", "pointer-follow", "hover-transition", "state-transition", "at-rest", "page-transition",
]);
const DOMINANT_WEIGHT_TOLERANCE = 0.25;

function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }, null, 2) + "\n");
  process.exit(2);
}

function sha256(file) { return createHash("sha256").update(fs.readFileSync(file)).digest("hex"); }

function parseArgs(argv) {
  const out = { manifest: null, sources: [], outFile: null,
    browserExecutable: process.env.DESIGN_DNA_BROWSER_EXECUTABLE || process.env.CHROME || null,
    buildId: null, runId: null, routeKeys: [], firstScreen: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--manifest") out.manifest = argv[++i];
    else if (arg === "--source") out.sources.push(argv[++i]);
    else if (arg === "--out") out.outFile = argv[++i];
    else if (arg === "--build-id") out.buildId = argv[++i];
    else if (arg === "--run-id") out.runId = argv[++i];
    else if (arg === "--route-key") out.routeKeys.push(argv[++i]);
    else if (arg === "--first-screen") out.firstScreen = true;
    else if (arg === "--browser-executable") out.browserExecutable = argv[++i];
    else if (arg === "--help" || arg === "-h") {
      process.stdout.write("compare_mechanisms.mjs --manifest FILE --build-id ID --source OBS.json [--source ...] --out FILE [--browser-executable FILE]\n");
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${arg}`);
  }
  if (!out.manifest || !out.buildId || !out.runId || !out.sources.length || !out.outFile) fail("usage", "--manifest, --build-id, --run-id, --source and --out are required.");
  return out;
}

function readJson(file, code) {
  try { return JSON.parse(fs.readFileSync(file, "utf8")); }
  catch (error) { fail(code, `${file}: ${String(error).slice(0, 160)}`); }
}

function rankOf(payload, file) {
  const match = String(payload.id || path.basename(file)).match(/strong-(\d+)/i);
  return match ? Number(match[1]) : null;
}

function loadPlaywright() {
  try {
    return resolvePlaywright({ moduleUrl: import.meta.url });
  } catch (error) {
    fail(error?.code || "playwright-unavailable", String(error?.message || error));
    return null;
  }
}

function loadBrowserDependency(loaded, explicit) {
  try {
    return browserExecutableIdentity(
      discoverBrowserExecutable(loaded.playwright, explicit),
    );
  } catch (error) {
    fail(error?.code || "browser-executable-unavailable", String(error?.message || error));
    return null;
  }
}

function countTypes(sheet) {
  const recorded = sheet?.score?.type_instances;
  if (recorded && typeof recorded === "object") return { ...recorded };
  const counts = {};
  for (const mechanism of sheet?.mechanisms || []) counts[mechanism.type] = (counts[mechanism.type] || 0) + 1;
  return counts;
}

const relativeDelta = (a, b) => Math.abs(Number(a || 0) - Number(b || 0)) / Math.max(Math.abs(Number(b || 0)), 1);

const evidenceFrameComplete = (frame) => frame && /^[0-9a-f]{64}$/.test(frame.sha256 || "") &&
  Number.isInteger(frame.bytes) && frame.bytes > 0;

export function diffInteractionCensus(build, source, states) {
  const failures = [];
  if (!build?.complete || build.truncated !== false || !Array.isArray(build.missing) || build.missing.length ||
      !source?.complete || source.truncated !== false || !Array.isArray(source.missing) || source.missing.length) {
    return { pass: false, failures: ["build/source interaction census is incomplete, truncated, or has missing targets"], target_transfers: [] };
  }
  const sourceToBuildState = new Map(states.map((state) => [state.mapped_reference_state_id, state.id]));
  const flatten = (census, sourceSide) => (census.pages || []).flatMap((pageRecord) =>
    (pageRecord.targets || []).flatMap((target) => (target.inputs || []).filter((input) => input.status === "exercised")
      .map((input) => {
        const frames = input.evidence;
        if (!frames || !["before", "after", "settled"].every((phase) => evidenceFrameComplete(frames[phase]))) {
          failures.push(`${sourceSide ? "source" : "build"} target ${target.target_id}/${input.input_kind} lacks target-specific frame evidence`);
        }
        if (![input.before_sha256, input.after_sha256, input.settled_sha256].every((value) => /^[0-9a-f]{64}$/.test(value || ""))) {
          failures.push(`${sourceSide ? "source" : "build"} target ${target.target_id}/${input.input_kind} lacks before/after/settled state hashes`);
        }
        const mappedState = sourceSide && input.source_state_id
          ? sourceToBuildState.get(input.source_state_id) || `unmapped:${input.source_state_id}`
          : input.source_state_id;
        const signature = {
          input_kind: input.input_kind,
          // Content/domain values legitimately differ between the reference
          // and project. A mapped state already binds the exact source event;
          // unbound navigation is compared as navigation behavior while the
          // authoritative route inventory independently binds its destination.
          input_value: mappedState || input.input_kind === "navigation" ? null : (input.input_value ?? null),
          state_id: mappedState ?? null,
          changed_properties: (input.changed_properties || []).map((item) => ({
            property: item?.property ?? null, before: item?.before ?? null, after: item?.after ?? null,
          })),
          changed: input.before_sha256 !== input.settled_sha256,
          disposition: input.disposition,
        };
        const componentKeys = [
          ...(target.class_signature || []).map((value) => `class:${encodeURIComponent(value)}`),
          target.tag ? `tag:${target.tag}` : null,
          target.role ? `role:${encodeURIComponent(String(target.role).toLowerCase())}` : null,
        ].filter(Boolean).sort();
        return { target_id: target.target_id, repeat_class: target.repeat_class, component_keys: componentKeys,
          repeat_index: target.repeat_index, signature, canonical: JSON.stringify(signature) };
      })));
  const buildRows = flatten(build, false).sort((a, b) => a.canonical.localeCompare(b.canonical) || a.target_id.localeCompare(b.target_id));
  const sourceRows = flatten(source, true).sort((a, b) => a.canonical.localeCompare(b.canonical) || a.target_id.localeCompare(b.target_id));
  if (Number(build.totals?.targets_discovered) !== Number(source.totals?.targets_discovered)) {
    failures.push(`interaction target count ${build.totals?.targets_discovered || 0} vs source ${source.totals?.targets_discovered || 0}`);
  }
  if (buildRows.length !== sourceRows.length) failures.push(`exercised input count ${buildRows.length} vs source ${sourceRows.length}`);
  const targetTransfers = [];
  for (let index = 0; index < Math.max(buildRows.length, sourceRows.length); index += 1) {
    const buildRow = buildRows[index], sourceRow = sourceRows[index];
    if (!buildRow || !sourceRow || buildRow.canonical !== sourceRow.canonical) {
      failures.push(`interaction behavior row ${index + 1} does not exactly match its source trigger/state/property sequence`);
      continue;
    }
    targetTransfers.push({
      source_target_id: sourceRow.target_id,
      build_target_id: buildRow.target_id,
      source_component_keys: sourceRow.component_keys,
      build_component_keys: buildRow.component_keys,
      input_kind: buildRow.signature.input_kind,
      build_state_id: buildRow.signature.state_id,
      behavior_signature: buildRow.signature,
      complete: true,
    });
  }
  const sourcePointers = source.pointer_follow || [], buildPointers = build.pointer_follow || [];
  if (sourcePointers.length !== buildPointers.length) failures.push(`pointer-follow target count ${buildPointers.length} vs source ${sourcePointers.length}`);
  for (let index = 0; index < Math.min(sourcePointers.length, buildPointers.length); index += 1) {
    const a = buildPointers[index], b = sourcePointers[index];
    if (a.distinct_from_hover !== true || b.distinct_from_hover !== true ||
        relativeDelta(a.moved_px, b.moved_px) > 0.25 || Number(a.return_error_px) > Math.max(8, Number(a.moved_px) * 0.3)) {
      failures.push(`pointer-follow row ${index + 1} is hover-like or differs in movement/return magnitude`);
    }
  }
  return { pass: failures.length === 0, failures, build_targets: build.totals?.targets_discovered || 0,
    source_targets: source.totals?.targets_discovered || 0, target_transfers: targetTransfers,
    verdict: failures.length ? failures.join("; ") : "Every live interaction target/input/state/frame sequence matches the exact source interaction census." };
}

function validateSourceFrameBytes(frame, observationFile, label) {
  if (!frame || typeof frame.file !== "string" || !evidenceFrameComplete(frame)) {
    fail("source-interaction-frame-invalid", `${label} has no exact file/bytes/SHA-256 frame binding.`);
  }
  const root = path.dirname(observationFile);
  const file = path.resolve(root, ...frame.file.split("/"));
  const relative = path.relative(root, file);
  let stat, realRoot, realFile;
  try {
    stat = fs.lstatSync(file); realRoot = fs.realpathSync(root); realFile = fs.realpathSync(file);
  } catch {
    stat = null;
  }
  if (!relative || relative.startsWith("..") || path.isAbsolute(relative) || !stat?.isFile() || stat.isSymbolicLink() ||
      !realFile || !realRoot || !realFile.startsWith(realRoot + path.sep)) {
    fail("source-interaction-frame-invalid", `${label} frame path escapes or is missing from the reference evidence directory.`);
  }
  const bytes = fs.readFileSync(file);
  if (bytes.length !== frame.bytes || createHash("sha256").update(bytes).digest("hex") !== frame.sha256) {
    fail("source-interaction-frame-invalid", `${label} frame bytes drifted from the exact observation binding.`);
  }
}

function validateSourceInteractionEvidence(sourceState, observationFile, label) {
  for (const phase of ["before", "after", "settled"]) {
    validateSourceFrameBytes(sourceState?.evidence_frames?.[phase], observationFile, `${label}.${phase}`);
  }
  const census = sourceState?.interaction_census;
  if (!census?.complete || census.truncated !== false || !Array.isArray(census.missing) || census.missing.length) {
    fail("source-interaction-census-invalid", `${label} lacks a complete uncapped source interaction census.`);
  }
  for (const pageRecord of census.pages || []) for (const target of pageRecord.targets || []) {
    for (const input of target.inputs || []) {
      if (input.status === "blocked") {
        if (input.evidence !== null || input.disposition !== "blocked-requires-safe-owner-handoff") {
          fail("source-interaction-census-invalid", `${label} blocked ${target.target_id}/${input.input_kind} is falsely represented as observed transfer evidence.`);
        }
        continue;
      }
      if (input.status !== "exercised" || !["sourceable-observed-behavior", "observed-quiet"].includes(input.disposition)) {
        fail("source-interaction-census-invalid", `${label} has an interaction row without observed or safely blocked disposition.`);
      }
      for (const phase of ["before", "after", "settled"]) {
        validateSourceFrameBytes(input.evidence?.[phase], observationFile,
          `${label}.${target.target_id}.${input.input_kind}.${phase}`);
      }
    }
  }
  for (const pointer of census.pointer_follow || []) for (const phase of ["before", "after", "settled"]) {
    validateSourceFrameBytes(pointer.evidence?.[phase], observationFile, `${label}.pointer-follow.${phase}`);
  }
}

function magnitudeMismatch(type, buildMechanism, sourceMechanism) {
  if (!buildMechanism || !sourceMechanism) return null;
  const sourceArea = Number(sourceMechanism.w || 0) * Number(sourceMechanism.h || 0);
  const buildArea = Number(buildMechanism.w || 0) * Number(buildMechanism.h || 0);
  if (sourceArea > 0 && relativeDelta(buildArea, sourceArea) > 0.25) {
    return `target area ${buildArea}px2 vs ${sourceArea}px2`;
  }
  if (type === "pinned" && Number(sourceMechanism.held_px) > 0) {
    if (relativeDelta(buildMechanism.held_px, sourceMechanism.held_px) > 0.25) return `held ${buildMechanism.held_px || 0}px vs ${sourceMechanism.held_px}px`;
    if (Number(buildMechanism.swaps_while_held || 0) !== Number(sourceMechanism.swaps_while_held || 0)) {
      return `${buildMechanism.swaps_while_held || 0} swaps while held vs ${sourceMechanism.swaps_while_held || 0}`;
    }
  }
  if (type === "parallax" && Number.isFinite(Number(sourceMechanism.rate))) {
    if (Math.abs(Number(buildMechanism.rate) - Number(sourceMechanism.rate)) > 0.15) return `rate ${buildMechanism.rate} vs ${sourceMechanism.rate}`;
    if (Number(sourceMechanism.ticks) > 0 && relativeDelta(buildMechanism.ticks, sourceMechanism.ticks) > 0.25) {
      return `${buildMechanism.ticks || 0} active ticks vs ${sourceMechanism.ticks}`;
    }
  }
  if (type === "hover-transition" && Number(sourceMechanism.ms) > 0) {
    if (relativeDelta(buildMechanism.ms, sourceMechanism.ms) > 0.25) return `duration ${buildMechanism.ms || 0}ms vs ${sourceMechanism.ms}ms`;
    if (Number(buildMechanism.responded || 0) !== Number(sourceMechanism.responded || 0)) {
      return `${buildMechanism.responded || 0} responding controls vs ${sourceMechanism.responded || 0}`;
    }
  }
  if (type === "state-transition") {
    if (Number(sourceMechanism.duration_ms) > 0 && relativeDelta(buildMechanism.duration_ms, sourceMechanism.duration_ms) > 0.25) {
      return `duration ${buildMechanism.duration_ms || 0}ms vs ${sourceMechanism.duration_ms}ms`;
    }
    if (Number(buildMechanism.changed_properties || 0) !== Number(sourceMechanism.changed_properties || 0)) {
      return `${buildMechanism.changed_properties || 0} changed properties vs ${sourceMechanism.changed_properties || 0}`;
    }
  }
  if (type === "swap" && Number(buildMechanism.swaps || 0) !== Number(sourceMechanism.swaps || 0)) {
    return `${buildMechanism.swaps || 0} swaps vs ${sourceMechanism.swaps}`;
  }
  if (type === "pointer-follow" && Number(sourceMechanism.moved_px) > 0 && relativeDelta(buildMechanism.moved_px, sourceMechanism.moved_px) > 0.25) {
    return `pointer movement ${buildMechanism.moved_px || 0}px vs ${sourceMechanism.moved_px}px`;
  }
  if (type === "pointer-follow" && (
    relativeDelta(buildMechanism.return_error_px, sourceMechanism.return_error_px) > 0.25 ||
    Math.abs(Number(buildMechanism.pointer_correlation || 0) - Number(sourceMechanism.pointer_correlation || 0)) > 0.15
  )) return `pointer return/correlation ${buildMechanism.return_error_px || 0}px/${buildMechanism.pointer_correlation || 0} vs ${sourceMechanism.return_error_px || 0}px/${sourceMechanism.pointer_correlation || 0}`;
  if (["at-rest", "reveal"].includes(type)) {
    if (sourceArea > 0 && relativeDelta(buildArea, sourceArea) > 0.25) return `painted area ${buildArea}px2 vs ${sourceArea}px2`;
  }
  if (type === "reveal") {
    const sourceRise = Math.abs(Number(sourceMechanism.opacity_to || 0) - Number(sourceMechanism.opacity_from || 0));
    const buildRise = Math.abs(Number(buildMechanism.opacity_to || 0) - Number(buildMechanism.opacity_from || 0));
    if (sourceRise > 0 && relativeDelta(buildRise, sourceRise) > 0.25) return `opacity change ${buildRise.toFixed(2)} vs ${sourceRise.toFixed(2)}`;
  }
  if (type === "page-transition") {
    if (Number(buildMechanism.changed_properties || 0) !== Number(sourceMechanism.changed_properties || 0)) {
      return `${buildMechanism.changed_properties || 0} changed properties vs ${sourceMechanism.changed_properties || 0}`;
    }
    if (Array.isArray(sourceMechanism.active_arrival_animations) &&
        Number(buildMechanism.active_arrival_animations?.length || 0) !== sourceMechanism.active_arrival_animations.length) {
      return `${buildMechanism.active_arrival_animations?.length || 0} arrival animations vs ${sourceMechanism.active_arrival_animations.length}`;
    }
  }
  return null;
}

export function diffSheets(build, sources) {
  if (!Array.isArray(sources) || sources.length !== 1) {
    return { pass: false, verdict: "Exactly one mapped reference sheet is required for each comparison.", missing: [], mismatched: [], over_used: [] };
  }
  const source = sources[0];
  const buildMechanisms = finalizeMechanisms(build?.mechanisms || []);
  const sourceMechanisms = finalizeMechanisms(source?.mechanisms || []);
  const sourceByType = new Map();
  for (const mechanism of sourceMechanisms) if (SIGNIFICANT_TYPES.has(mechanism.type) && !sourceByType.has(mechanism.type)) sourceByType.set(mechanism.type, mechanism);
  const buildByType = new Map();
  for (const mechanism of buildMechanisms) if (SIGNIFICANT_TYPES.has(mechanism.type) && !buildByType.has(mechanism.type)) buildByType.set(mechanism.type, mechanism);
  const wanted = [...sourceByType.keys()];
  const missing = wanted.filter((type) => !buildByType.has(type));
  const mismatched = wanted.filter((type) => buildByType.has(type))
    .map((type) => ({ type, detail: magnitudeMismatch(type, buildByType.get(type), sourceByType.get(type)) }))
    .filter((item) => item.detail);
  const buildCounts = countTypes(build), sourceCounts = countTypes(source);
  const countMismatches = [...new Set([...Object.keys(sourceCounts), ...Object.keys(buildCounts)])]
    .filter((type) => SIGNIFICANT_TYPES.has(type) && Number(buildCounts[type] || 0) !== Number(sourceCounts[type] || 0))
    .map((type) => ({ type, build: Number(buildCounts[type] || 0), source: Number(sourceCounts[type] || 0) }));
  const sourceLoudest = sourceMechanisms.find((mechanism) => SIGNIFICANT_TYPES.has(mechanism.type)) || null;
  const buildLoudest = buildMechanisms.find((mechanism) => SIGNIFICANT_TYPES.has(mechanism.type)) || null;
  const sourceLoudestWeight = sourceLoudest ? mechanismWeight(sourceLoudest) : 0;
  const buildLoudestWeight = buildLoudest ? mechanismWeight(buildLoudest) : 0;
  const loudestTypeMismatch = (sourceLoudest?.type || null) !== (buildLoudest?.type || null);
  const loudestMagnitudeMismatch = sourceLoudestWeight > 0 && relativeDelta(buildLoudestWeight, sourceLoudestWeight) > DOMINANT_WEIGHT_TOLERANCE;
  const pass = !missing.length && !mismatched.length && !countMismatches.length && !loudestTypeMismatch && !loudestMagnitudeMismatch;
  return {
    pass,
    build_types: [...buildByType.keys()], source_types: wanted, wanted,
    carried: wanted.filter((type) => buildByType.has(type)), missing, mismatched,
    source_counts: sourceCounts, build_counts: buildCounts, instance_count_mismatches: countMismatches,
    source_loudest: sourceLoudest?.type || null,
    build_loudest: buildLoudest?.type || null,
    source_loudest_weight: sourceLoudestWeight,
    build_loudest_weight: buildLoudestWeight,
    loudest_type_match: !loudestTypeMismatch,
    loudest_magnitude_relative_delta: sourceLoudestWeight ? +relativeDelta(buildLoudestWeight, sourceLoudestWeight).toFixed(4) : 0,
    loudest_magnitude_tolerance: DOMINANT_WEIGHT_TOLERANCE,
    build_score: build?.score || null, source_score: source?.score || null,
    verdict: pass ? "The build carries the exact mechanism types, instance counts, dominant device and measured magnitude of its mapped reference." : [
      missing.length ? `missing ${missing.join(", ")}` : null,
      mismatched.length ? `magnitude mismatch ${mismatched.map((item) => `${item.type}: ${item.detail}`).join("; ")}` : null,
      countMismatches.length ? `instance-count mismatch ${countMismatches.map((item) => `${item.type} x${item.build} vs x${item.source}`).join("; ")}` : null,
      loudestTypeMismatch ? `loudest mechanism ${buildLoudest?.type || "none"} vs ${sourceLoudest?.type || "none"}` : null,
      loudestMagnitudeMismatch ? `loudest weight ${buildLoudestWeight} vs ${sourceLoudestWeight} exceeds ${Math.round(DOMINANT_WEIGHT_TOLERANCE * 100)}% tolerance` : null,
    ].filter(Boolean).join("; "),
  };
}

export function diffTriggerEvidence(build, source, state, sourceState = null) {
  const failures = [];
  if (!build || !source || !state?.trigger) return {
    pass: false,
    failures: ["missing build/source trigger evidence or manifest trigger"],
    verdict: "missing build/source trigger evidence or manifest trigger",
  };
  if (build.type !== state.trigger.type) failures.push(`build trigger type ${build.type} vs manifest ${state.trigger.type}`);
  if (source.type !== state.trigger.type) failures.push(`source trigger type ${source.type} vs manifest ${state.trigger.type}`);
  if (build.target !== state.trigger.target) failures.push(`build trigger target ${build.target} vs manifest ${state.trigger.target}`);
  if (sourceState?.trigger && source.target !== sourceState.trigger.target) {
    failures.push(`source trigger target ${source.target} vs observed state contract ${sourceState.trigger.target}`);
  }
  const digest = (value) => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
  if (![build.before_sha256, build.after_sha256, build.settled_sha256,
    source.before_sha256, source.after_sha256, source.settled_sha256].every(digest)) {
    failures.push("before/after/settled evidence is not bound by complete SHA-256 identities");
  }
  const buildMechanism = build.mechanism?.type || null;
  const sourceMechanism = source.mechanism?.type || null;
  if (buildMechanism !== sourceMechanism) failures.push(`trigger mechanism ${buildMechanism || "none"} vs ${sourceMechanism || "none"}`);
  if (Number(build.mechanism_count || 0) !== Number(source.mechanism_count || 0)) {
    failures.push(`trigger mechanism count ${build.mechanism_count || 0} vs ${source.mechanism_count || 0}`);
  }
  if (build.settled !== true || source.settled !== true) failures.push("before/after/settled sequence did not settle on both build and source");
  const buildChanged = Array.isArray(build.changed_properties) ? build.changed_properties : [];
  const sourceChanged = Array.isArray(source.changed_properties) ? source.changed_properties : [];
  const buildOrder = buildChanged.map((item) => item?.property);
  const sourceOrder = sourceChanged.map((item) => item?.property);
  if (JSON.stringify(buildOrder) !== JSON.stringify(sourceOrder)) {
    failures.push(`changed-property order ${buildOrder.join(",") || "none"} vs ${sourceOrder.join(",") || "none"}`);
  }
  const changeSignature = (rows) => rows.map((item) => ({
    property: item?.property ?? null,
    before: item?.before ?? null,
    after: item?.after ?? null,
  }));
  if (JSON.stringify(changeSignature(buildChanged)) !== JSON.stringify(changeSignature(sourceChanged))) {
    failures.push("target-specific before/after property values differ from the exact source state");
  }
  if (!Array.isArray(build.target_component_keys) || !build.target_component_keys.length ||
      !Array.isArray(source.target_component_keys) || !source.target_component_keys.length) {
    failures.push("trigger target component identity is missing");
  }
  const sourceDuration = Number(source.duration_ms || 0), buildDuration = Number(build.duration_ms || 0);
  if (sourceDuration > 0 && relativeDelta(buildDuration, sourceDuration) > 0.25) {
    failures.push(`trigger duration ${buildDuration}ms vs ${sourceDuration}ms`);
  }
  const sourceChangedState = source.before_sha256 !== source.settled_sha256;
  const buildChangedState = build.before_sha256 !== build.settled_sha256;
  if (sourceChangedState !== buildChangedState) failures.push(`trigger visual change ${buildChangedState} vs ${sourceChangedState}`);
  return {
    pass: failures.length === 0,
    failures,
    build_trigger_type: build.type,
    source_trigger_type: source.type,
    build_mechanism: buildMechanism,
    source_mechanism: sourceMechanism,
    build_duration_ms: buildDuration,
    source_duration_ms: sourceDuration,
    build_changed_property_order: buildOrder,
    source_changed_property_order: sourceOrder,
    verdict: failures.length ? failures.join("; ") : "Trigger, ordered visual changes, mechanism count, magnitude, and settled result match the exact source state.",
  };
}

async function hoverPass(page, firstScreen = false) {
  const selector = 'a[href],button,[role="button"],summary,input,select,textarea,[tabindex]:not([tabindex="-1"])';
  const elements = await page.locator(selector).all();
  const durations = [];
  const respondingComponents = new Set();
  let responded = 0, attempted = 0;
  for (const element of elements) {
    try {
      if (!(await element.isVisible())) continue;
      const initialBox = await element.boundingBox();
      if (firstScreen && (!initialBox || initialBox.y < 0 || initialBox.y + initialBox.height > page.viewportSize().height)) continue;
      if (!firstScreen) await element.scrollIntoViewIfNeeded();
      const before = await element.evaluate((node) => [node, ...node.querySelectorAll('*')].slice(0, 40).map((item) => {
        const style = getComputedStyle(item), box = item.getBoundingClientRect();
        return { visual: [style.color, style.backgroundColor, style.transform, style.opacity, style.filter, style.clipPath,
          Math.round(box.left), Math.round(box.top), Math.round(box.width), Math.round(box.height)],
          duration: style.transitionDuration, easing: style.transitionTimingFunction };
      }));
      const componentKeys = await element.evaluate((node) => {
        const keys = [...String(node.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean)
          .map((value) => 'class:' + encodeURIComponent(value))];
        if (node.id) keys.push('id:' + encodeURIComponent(node.id));
        const role = node.getAttribute('role'); if (role) keys.push('role:' + encodeURIComponent(role.toLowerCase()));
        keys.push('tag:' + node.tagName.toLowerCase());
        return [...new Set(keys)];
      });
      attempted += 1; await element.hover({ timeout: 2500 }); await page.waitForTimeout(180);
      const after = await element.evaluate((node) => [node, ...node.querySelectorAll('*')].slice(0, 40).map((item) => {
        const style = getComputedStyle(item), box = item.getBoundingClientRect();
        return [style.color, style.backgroundColor, style.transform, style.opacity, style.filter, style.clipPath,
          Math.round(box.left), Math.round(box.top), Math.round(box.width), Math.round(box.height)];
      }));
      const changed = JSON.stringify(before.map((row) => row.visual)) !== JSON.stringify(after);
      if (changed) { responded += 1; componentKeys.forEach((key) => respondingComponents.add(key)); }
      const values = before.flatMap((row) => String(row.duration).split(","))
        .map((value) => parseFloat(value) * (value.trim().endsWith("ms") ? 1 : 1000)).filter(Number.isFinite);
      if (changed && Math.max(...values, 0) > 0) durations.push(Math.max(...values));
    } catch { /* mismatch is reflected by attempted/responded */ }
  }
  if (!attempted || !responded || !durations.length) return null;
  return { type: "hover-transition", ms: Math.round(median(durations)), easing: null, responded,
    components: [...respondingComponents].sort(),
    detail: `${responded} of ${attempted} controls visibly respond to hover` };
}

async function pageTransitionPass(page, startUrl, restore) {
  const origin = new URL(startUrl).origin;
  const target = await page.evaluate((expectedOrigin) => {
    const anchor = [...document.querySelectorAll('a[href]')].find((node) => {
      try {
        const url = new URL(node.href, location.href);
        return url.origin === expectedOrigin && url.pathname !== location.pathname && !node.hasAttribute('download') &&
          !node.target && /^https?:$/.test(url.protocol);
      } catch { return false; }
    });
    if (!anchor) return null;
    const components = [...String(anchor.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean)
      .map((value) => 'class:' + encodeURIComponent(value))];
    if (anchor.id) components.push('id:' + encodeURIComponent(anchor.id));
    const role = anchor.getAttribute('role'); if (role) components.push('role:' + encodeURIComponent(role.toLowerCase()));
    components.push('tag:a');
    return { href: anchor.href, components: [...new Set(components)].sort() };
  }, origin);
  if (!target) return null;
  const before = await page.screenshot();
  const navigation = await navigateExact(page, target.href, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(180);
  const activity = await page.evaluate(() => document.getAnimations().map((animation) => {
    const timing = animation.effect?.getComputedTiming?.() || {}, target = animation.effect?.target;
    return { play_state: animation.playState, current_time: Number(animation.currentTime || 0),
      end_time: Number(timing.endTime || 0), iterations: Number(timing.iterations),
      target: target ? `${target.tagName.toLowerCase()}.${typeof target.className === 'string' ? target.className.slice(0, 48) : ''}` : null };
  }).filter((animation) => animation.play_state === 'running' && Number.isFinite(animation.iterations) &&
    animation.iterations <= 1 && animation.end_time - animation.current_time > 120));
  const changed = activity.length > 0;
  await page.waitForTimeout(900);
  await restore();
  return changed ? { type: "page-transition", components: target.components,
    detail: `mapped internal route ${navigation.final_normalized_url} continued changing after arrival`,
    active_arrival_animations: activity, before_sha256: createHash("sha256").update(before).digest("hex") } : null;
}

async function observeBuild(page, state, routeStates, profile, pageUrl, evidenceDir, evidenceRelativeRoot, evidencePrefix, firstScreen = false, navigate) {
  let frameSequence = 0;
  const persistFrame = (phase, bytes) => {
    frameSequence += 1;
    const safe = `${evidencePrefix}-${String(frameSequence).padStart(5, "0")}-${phase}`
      .toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "");
    const name = `${safe}.png`;
    fs.writeFileSync(path.join(evidenceDir, name), bytes);
    return { phase, scope: "viewport", target: state.trigger.target,
      file: `${evidenceRelativeRoot}/${name}`, bytes: bytes.length,
      sha256: createHash("sha256").update(bytes).digest("hex") };
  };
  await navigate();
  await navigate();
  const beforeFrame = await page.screenshot();
  const application = await applyManifestState(page, state);
  const afterFrame = await page.screenshot();
  await page.waitForTimeout(180);
  const settledFrame = await page.screenshot();
  const sheet = await mechanismPass(page);
  if (application.trigger_evidence?.mechanism) {
    sheet.mechanisms = finalizeMechanisms([...sheet.mechanisms, application.trigger_evidence.mechanism]);
    const type = application.trigger_evidence.mechanism.type;
    sheet.score.type_instances[type] = (sheet.score.type_instances[type] || 0) + application.trigger_evidence.mechanism_count;
    sheet.score.distinct_mechanisms = new Set(sheet.mechanisms.map((item) => item.type)).size;
  }
  const measured = firstScreen ? firstScreenSheet(sheet, page.viewportSize().height) : sheet;
  const frame = (phase, bytes) => persistFrame(phase, bytes);
  const interactionCensus = await captureInteractionCensus(page, {
    profile,
    pageUrl,
    authoredStates: routeStates.map((item) => ({ ...item, url: pageUrl })),
    captureEvidence: async (label, evidencePage = page) => {
      const bytes = await evidencePage.screenshot();
      return { ...persistFrame(label, bytes), label };
    },
  });
  return {
    sheet: measured,
    application,
    interaction_census: interactionCensus,
    evidence_frames: {
      before: frame("before", beforeFrame),
      after: frame("after", afterFrame),
      settled: frame("settled", settledFrame),
    },
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  let manifest, mappedByRoute;
  try {
    manifest = loadRouteManifest(args.manifest);
    mappedByRoute = bindSuppliedObservations(manifest, args.sources, OBSERVER_SCRIPT_SHA256);
  } catch (error) {
    fail("manifest-reference-binding-invalid", String(error).slice(0, 500));
  }
  if (args.routeKeys.some((key) => !manifest.routes.some((route) => route.key === key))) fail("route-key-missing", "Every --route-key must exist in the manifest.");
  for (const [routeKey, binding] of mappedByRoute) {
    const payload = binding.payload;
    const route = manifest.routes.find((item) => item.key === routeKey);
    if (!payload.states_by_viewport?.wide || !payload.states_by_viewport?.narrow ||
        route.states.some((state) => !payload.states_by_viewport.wide[state.mapped_reference_state_id]?.mechanisms ||
          !payload.states_by_viewport.narrow[state.mapped_reference_state_id]?.mechanisms)) {
      fail("source-not-observation", `Route ${routeKey}'s exact observation lacks a wide/narrow mechanism sheet for every mapped source state.`);
    }
    for (const profile of ["wide", "narrow"]) for (const state of route.states) {
      validateSourceInteractionEvidence(
        payload.states_by_viewport[profile][state.mapped_reference_state_id],
        binding.file,
        `${routeKey}/${profile}/${state.mapped_reference_state_id}`,
      );
    }
  }
  const loaded = loadPlaywright();
  const browserDependency = loadBrowserDependency(loaded, args.browserExecutable);
  const browser = await loaded.playwright.chromium.launch({ executablePath: browserDependency.file });
  const checks = [];
  const servedProbes = [];
  const interactionFrameDir = path.resolve(`${args.outFile.replace(/\.json$/i, "")}-interaction-frames`);
  const interactionFrameRelativeRoot = path.relative(path.dirname(path.resolve(args.outFile)), interactionFrameDir).split(path.sep).join("/");
  fs.mkdirSync(interactionFrameDir, { recursive: true });
  try {
    for (const viewport of manifest.viewports) {
      const profile = viewport.width <= 430 ? "narrow" : "wide";
      const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
      await installDomInspection(context);
      const selectedRoutes = args.routeKeys.length ? manifest.routes.filter((route) => args.routeKeys.includes(route.key)) : manifest.routes;
      for (const route of selectedRoutes) {
        const mapped = mappedByRoute.get(route.key);
        if (!mapped) fail("mapped-reference-missing", `Route ${route.key} has no exact bound observation.`);
        for (const state of route.states) {
          const page = await context.newPage();
          const restLoads = [];
          const navigations = [];
          const navigate = async () => {
            const capture = beginServedContentCapture(page, route.url);
            const navigation = await navigateExact(page, route.url);
            capture.setFinalResponse(navigation);
            await page.evaluate(() => document.fonts?.ready).catch(() => {});
            await page.waitForTimeout(500);
            const served = await capture.finish({ route_key: route.key, viewport: viewport.name });
            navigations.push(navigation);
            restLoads.push(served);
            return served;
          };
          const buildObservation = await observeBuild(
            page, state, route.states, profile, route.url,
            interactionFrameDir, interactionFrameRelativeRoot, `${route.key}-${viewport.name}-${state.id}`,
            args.firstScreen, navigate,
          );
          await page.close();
          if (restLoads.length !== 2 || new Set(restLoads.map((entry) => entry.sha256)).size !== 1) {
            fail("served-content-reload-drift", `${route.key}/${viewport.name} did not produce two identical byte-bound rest loads.`);
          }
          servedProbes.push(...restLoads);
          const sourceState = mapped.payload.states_by_viewport[profile][state.mapped_reference_state_id];
          const sourceSheet = args.firstScreen ? firstScreenSheet(sourceState, viewport.height) : sourceState;
          const diff = diffSheets(buildObservation.sheet, [sourceSheet]);
          const stateContractMatch = sourceState.id === state.mapped_reference_state_id &&
            sourceState.kind === state.kind && sourceState.trigger?.type === state.trigger.type;
          const triggerDiff = diffTriggerEvidence(
            buildObservation.application.trigger_evidence,
            sourceState.trigger_evidence,
            state,
            sourceState,
          );
          const interactionDiff = diffInteractionCensus(
            buildObservation.interaction_census,
            sourceState.interaction_census,
            route.states,
          );
          if (!stateContractMatch || !triggerDiff.pass || !interactionDiff.pass) {
            diff.pass = false;
            diff.verdict = [
              !stateContractMatch ? `source state ${state.mapped_reference_state_id} does not match ${state.kind}/${state.trigger.type}` : null,
              !triggerDiff.pass ? `trigger mismatch: ${triggerDiff.verdict}` : null,
              !interactionDiff.pass ? `interaction census mismatch: ${interactionDiff.verdict}` : null,
              diff.verdict,
            ].filter(Boolean).join("; ");
          }
          checks.push({
            route_key: route.key, url: route.url, viewport: viewport.name, width: viewport.width, height: viewport.height,
            state_id: state.id,
            state_kind: state.kind,
            state_trigger: state.trigger,
            state_expectation: state.expectation,
            mapped_reference_state_id: state.mapped_reference_state_id,
            state_application: buildObservation.application,
            evidence_frames: buildObservation.evidence_frames,
            navigations,
            state_contract_match: stateContractMatch,
            trigger_diff: triggerDiff,
            interaction_diff: interactionDiff,
            build_interaction_census: buildObservation.interaction_census,
            build_interaction_census_sha256: createHash("sha256").update(canonicalJson(buildObservation.interaction_census)).digest("hex"),
            source_interaction_census_sha256: createHash("sha256").update(canonicalJson(sourceState.interaction_census)).digest("hex"),
            mapped_reference: {
              rank: mapped.rank, id: mapped.id, observation: mapped.observation,
              sha256: mapped.sha256, url: mapped.url,
            },
            source_mapping: {
              rank: mapped.rank, id: mapped.id, observation: mapped.observation,
              sha256: mapped.sha256, state_id: state.mapped_reference_state_id,
            },
            mapped_reference_rank: mapped.rank,
            mapped_reference_id: mapped.id,
            mapped_reference_sha256: mapped.sha256,
            source_file: mapped.observation,
            source_sha256: mapped.sha256,
            served_content_sha256: restLoads[0].sha256,
            build_mechanisms: buildObservation.sheet.mechanisms,
            source_trigger_evidence: sourceState.trigger_evidence || null,
            ...diff,
          });
        }
      }
      await context.close();
    }
  } finally {
    await browser.close().catch(() => {});
  }
  const responsiveTransfers = [];
  for (const route of (args.routeKeys.length ? manifest.routes.filter((item) => args.routeKeys.includes(item.key)) : manifest.routes)) {
    const mapped = mappedByRoute.get(route.key);
    for (const state of route.states) {
      const wide = checks.find((check) => check.route_key === route.key && check.state_id === state.id && check.width >= 1280);
      const narrow = checks.find((check) => check.route_key === route.key && check.state_id === state.id && check.width <= 430);
      const sourceWide = mapped?.payload?.states_by_viewport?.wide?.[state.mapped_reference_state_id]?.trigger_evidence;
      const sourceNarrow = mapped?.payload?.states_by_viewport?.narrow?.[state.mapped_reference_state_id]?.trigger_evidence;
      const signature = (evidence) => ({
        type: evidence?.type || null,
        mechanism: evidence?.mechanism?.type || null,
        mechanism_count: Number(evidence?.mechanism_count || 0),
        changed_properties: (evidence?.changed_properties || []).map((item) => ({
          property: item?.property ?? null, before: item?.before ?? null, after: item?.after ?? null,
        })),
        changed: evidence?.before_sha256 !== evidence?.settled_sha256,
      });
      const sourceTransforms = JSON.stringify(signature(sourceWide)) !== JSON.stringify(signature(sourceNarrow));
      const buildTransforms = Boolean(wide && narrow) &&
        JSON.stringify(signature(wide.state_application?.trigger_evidence)) !==
        JSON.stringify(signature(narrow.state_application?.trigger_evidence));
      const complete = Boolean(wide?.pass && narrow?.pass && sourceWide && sourceNarrow && sourceTransforms === buildTransforms);
      responsiveTransfers.push({
        route_key: route.key,
        state_id: state.id,
        mapped_reference_state_id: state.mapped_reference_state_id,
        source_transforms_between_profiles: sourceTransforms,
        build_transforms_between_profiles: buildTransforms,
        wide_cell: wide ? `${wide.route_key}/${wide.viewport}/${wide.state_id}` : null,
        narrow_cell: narrow ? `${narrow.route_key}/${narrow.viewport}/${narrow.state_id}` : null,
        complete,
      });
    }
  }
  const failed = checks.filter((check) => !check.pass);
  const failedResponsive = responsiveTransfers.filter((item) => !item.complete);
  const record = {
    tool: TOOL_NAME, schema_version: SCHEMA_VERSION, producer_script_sha256: PRODUCER_SCRIPT_SHA256,
    runtime_identity: {
      "compare_mechanisms.mjs": PRODUCER_SCRIPT_SHA256,
      "observe_reference.mjs": OBSERVER_SCRIPT_SHA256,
      "browser_evidence.mjs": BROWSER_EVIDENCE_SHA256,
      "playwright_resolver.mjs": PLAYWRIGHT_RESOLVER_SHA256,
      "provenance_contract.mjs": PROVENANCE_CONTRACT_SHA256,
      "playwright-entry": loaded.dependency.resolved_file_sha256,
      "browser-executable": browserDependency.sha256,
    },
    dependencies: { playwright: loaded.dependency, browser_executable: browserDependency },
    compared_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    build_id: args.buildId, run_id: args.runId, manifest_id: manifest.manifest_id,
    route_filter: args.routeKeys, first_screen_only: args.firstScreen,
    manifest_file: args.manifest, manifest_sha256: manifest.__sha256,
    interaction_frame_directory: interactionFrameRelativeRoot,
    source_files: [...new Map([...mappedByRoute.values()].map((source) => [source.sha256, {
      file: source.observation, rank: source.rank, id: source.id, url: source.url, sha256: source.sha256,
    }])).values()],
    served_content_identity: aggregateServedContent(servedProbes),
    interaction_transfer: {
      complete: failed.length === 0 && failedResponsive.length === 0,
      missing: [...failed.map((check) => `${check.route_key}/${check.viewport}/${check.state_id}`),
        ...failedResponsive.map((item) => `${item.route_key}/responsive/${item.state_id}`)],
      cells: checks,
      responsive_transformations: responsiveTransfers,
    },
    checks, pass: !failed.length && !failedResponsive.length,
    verdict: !failed.length && !failedResponsive.length ? `All ${checks.length} route/viewport/state cells carry the exact target behavior, trigger sequence, instance counts, dominant device, magnitude, and responsive transformation of their bound observation state.` :
      `${failed.length} cell and ${failedResponsive.length} responsive transfer failures: ${[...failed.map((check) => `${check.route_key}/${check.viewport}/${check.state_id}: ${check.verdict}`), ...failedResponsive.map((item) => `${item.route_key}/${item.state_id}: responsive transformation mismatch`)].join(" | ")}`,
  };
  fs.mkdirSync(path.dirname(args.outFile), { recursive: true });
  fs.writeFileSync(args.outFile, JSON.stringify(record, null, 2) + "\n", "utf8");
  process.stdout.write(JSON.stringify({ ok: true, pass: record.pass, record: args.outFile, verdict: record.verdict }, null, 2) + "\n");
  process.exit(record.pass ? 0 : 1);
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
if (invokedDirectly) main();
