#!/usr/bin/env node
/** Prove that each selected reference's dominant grammar exists in the build. */

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { finalizeMechanisms, firstScreenSheet, mechanismWeight } from "./observe_reference.mjs";
import {
  bindSuppliedObservations,
  loadRouteManifest,
  PRODUCER_OUTPUT_SCHEMA_VERSION,
} from "./provenance_contract.mjs";

const TOOL_NAME = "check_signature_transfer.mjs";
const SCHEMA_VERSION = PRODUCER_OUTPUT_SCHEMA_VERSION;
const SCRIPT_PATH = path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const SCRIPT_DIR = path.dirname(SCRIPT_PATH);
const PRODUCER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(SCRIPT_PATH)).digest("hex");
const scriptHash = (name) => createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, name))).digest("hex");
const PROVENANCE_CONTRACT_SHA256 = scriptHash("provenance_contract.mjs");

function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }, null, 2) + "\n");
  process.exit(2);
}

const VERB_TYPES = [
  [/\b(hold|holds|held|pin|pins|pinned|stick|sticks|stuck|stay|stays|lock|locks)\b/i, ["pinned"]],
  [/\b(swap|swaps|change|changes|cycle|cycles|replace|replaces|crossfade|dissolve|turn|turns)\b/i, ["swap"]],
  [/\b(reveal|reveals|rise|rises|arrive|arrives|enter|enters|appear|appears|slide|slides|fade|fades|assemble|grow|expand|unfold|land)\b/i, ["reveal"]],
  [/\b(parallax|drift|drifts|float|floats|lag|lags|trail|trails)\b/i, ["parallax", "pointer-follow"]],
  [/\b(follow|follows|track|tracks|tilt|tilts|lean|leans|respond|responds|react|reacts)\b/i, ["pointer-follow", "hover-transition"]],
  [/\b(hover|hovers|fill|fills|light|lights|glow|glows)\b/i, ["hover-transition"]],
  [/\b(click|clicks|press|presses|focus|focuses|toggle|toggles|open|opens|close|closes|select|selects|input|type|types)\b/i, ["state-transition"]],
  [/\b(transition|transitions|wipe|wipes|mask|masks|cut|cuts|arrives|route)\b/i, ["page-transition"]],
  [/\b(play|plays|loop|loops|run|runs|tick|ticks|breathe|breathes|autoplay)\b/i, ["at-rest"]],
];

function parseArgs(argv) {
  const out = { dossier: null, observations: [], out: null, mechanismDiff: null, structureDiff: null,
    styleProvenance: null, census: null, manifest: null, buildId: null, runId: null, onlyRank: null };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--dossier") out.dossier = argv[++i];
    else if (arg === "--observation") out.observations.push(argv[++i]);
    else if (arg === "--out") out.out = argv[++i];
    else if (arg === "--mechanism-diff") out.mechanismDiff = argv[++i];
    else if (arg === "--structure-diff") out.structureDiff = argv[++i];
    else if (arg === "--style-provenance") out.styleProvenance = argv[++i];
    else if (arg === "--census") out.census = argv[++i];
    else if (arg === "--manifest") out.manifest = argv[++i];
    else if (arg === "--build-id") out.buildId = argv[++i];
    else if (arg === "--run-id") out.runId = argv[++i];
    else if (arg === "--only-rank") out.onlyRank = Number(argv[++i]);
    else if (arg === "--help" || arg === "-h") {
      process.stdout.write("check_signature_transfer.mjs --dossier FILE --manifest FILE --observation FILE... --mechanism-diff FILE --structure-diff FILE --style-provenance FILE --census FILE --build-id ID --run-id ID --out FILE\n");
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${arg}`);
  }
  for (const field of ["dossier", "manifest", "out", "mechanismDiff", "structureDiff", "styleProvenance", "census", "buildId", "runId"]) {
    if (!out[field]) fail("usage", `--${field.replace(/[A-Z]/g, (letter) => "-" + letter.toLowerCase())} is required.`);
  }
  if (!out.observations.length) fail("usage", "At least one --observation is required.");
  return out;
}

function sha256(file) { return createHash("sha256").update(fs.readFileSync(file)).digest("hex"); }

function readJson(file, code) {
  try { return JSON.parse(fs.readFileSync(file, "utf8")); }
  catch (error) { fail(code, `${file}: ${String(error).slice(0, 160)}`); }
}

function sectionOf(body, heading) {
  const lines = body.split(/\r?\n/);
  const start = lines.findIndex((line) => line.trim().toLowerCase() === `## ${heading}`.toLowerCase());
  if (start === -1) return "";
  let end = lines.length;
  for (let i = start + 1; i < lines.length; i += 1) if (/^##\s/.test(lines[i])) { end = i; break; }
  return lines.slice(start + 1, end).join("\n");
}

function firstTable(section) {
  const rows = []; let headers = null;
  for (const raw of section.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line.startsWith("|")) { if (headers) break; else continue; }
    const cells = line.replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
    if (cells.every((cell) => /^:?-{2,}:?$/.test(cell))) continue;
    if (!headers) headers = cells; else rows.push(cells);
  }
  return { headers: headers || [], rows };
}

function rankOf(payload, file) {
  const match = String(payload.id || path.basename(file)).match(/strong-(\d+)/i);
  return match ? Number(match[1]) : null;
}

function claimedTypes(signature) {
  const named = new Set();
  for (const [pattern, types] of VERB_TYPES) if (pattern.test(signature)) for (const type of types) named.add(type);
  return named;
}

function observationSummary(payload, firstScreen = false) {
  const byProfile = (firstScreen ? payload.first_screen_mechanisms_by_viewport : payload.mechanisms_by_viewport) || {};
  const stateSheets = payload.states_by_viewport || {};
  const stateMechanisms = (profile) => Object.values(stateSheets[profile] || {}).flatMap((state) =>
    (firstScreen ? firstScreenSheet(state, profile === "narrow" ? 844 : 900) : state)?.mechanisms || []);
  const all = finalizeMechanisms([
    ...(byProfile.wide?.mechanisms || payload.mechanisms || []),
    ...(byProfile.narrow?.mechanisms || []),
    ...stateMechanisms("wide"),
    ...stateMechanisms("narrow"),
  ]);
  const wideCoverage = Number(byProfile.wide?.score?.scroll_coverage ?? payload.score?.scroll_coverage ?? 0);
  const narrowCoverage = Number(byProfile.narrow?.score?.scroll_coverage ?? 0);
  const loudest = all[0] || null;
  const strongMotion = Boolean(loudest) && (
    mechanismWeight(loudest) >= 900 || Math.max(wideCoverage, narrowCoverage) >= 0.25 ||
    ["page-transition", "pinned", "swap", "pointer-follow"].includes(loudest.type)
  );
  return { mechanisms: all, loudest, strongMotion, scrollCoverage: { wide: wideCoverage, narrow: narrowCoverage } };
}

const args = parseArgs(process.argv.slice(2));
let dossierBody;
try { dossierBody = fs.readFileSync(args.dossier, "utf8"); }
catch (error) { fail("dossier-unreadable", `${args.dossier}: ${error.message}`); }
let manifest, mappedByRoute;
try {
  manifest = loadRouteManifest(args.manifest);
  mappedByRoute = bindSuppliedObservations(manifest, args.observations, scriptHash("observe_reference.mjs"));
} catch (error) {
  fail("manifest-reference-binding-invalid", String(error).slice(0, 500));
}

const mechanism = readJson(args.mechanismDiff, "mechanism-unreadable");
const structure = readJson(args.structureDiff, "structure-unreadable");
const styles = readJson(args.styleProvenance, "style-unreadable");
const census = readJson(args.census, "census-unreadable");
for (const [name, record, tool] of [
  ["mechanism", mechanism, "compare_mechanisms.mjs"], ["structure", structure, "compare_structure.mjs"],
  ["style", styles, "check_style_provenance.mjs"], ["census", census, "scan_build_components.mjs"],
]) {
  const passing = tool === "check_style_provenance.mjs" ? record?.ok === true : record?.pass === true;
  if (record?.tool !== tool || record.schema_version !== SCHEMA_VERSION || record.producer_script_sha256 !== scriptHash(tool) ||
      record.build_id !== args.buildId || record.run_id !== args.runId || record.manifest_id !== manifest.manifest_id ||
      record.manifest_sha256 !== manifest.__sha256 || !passing) {
    fail("evidence-invalid", `${name} evidence must be a passing current-schema ${tool} record for this exact build, run, and manifest.`);
  }
  if (tool === "compare_mechanisms.mjs" && record.runtime_identity?.["observe_reference.mjs"] !== scriptHash("observe_reference.mjs")) {
    fail("evidence-runtime-drift", "Mechanism evidence used a different observer runtime.");
  }
  if (tool === "compare_structure.mjs" && record.runtime_identity?.["structure_probe.mjs"] !== scriptHash("structure_probe.mjs")) {
    fail("evidence-runtime-drift", "Structure evidence used a different structure probe runtime.");
  }
  if (tool === "check_style_provenance.mjs" && record.runtime_identity?.["extract_reference_styles.mjs"] !== scriptHash("extract_reference_styles.mjs")) {
    fail("evidence-runtime-drift", "Style evidence used a different extractor runtime.");
  }
}
if (mechanism.interaction_transfer?.complete !== true ||
    !Array.isArray(mechanism.interaction_transfer?.missing) || mechanism.interaction_transfer.missing.length ||
    !Array.isArray(mechanism.interaction_transfer?.cells) ||
    mechanism.interaction_transfer.cells.length !== mechanism.checks?.length) {
  fail("mechanism-interaction-transfer-incomplete", "Mechanism evidence lacks the complete uncapped exact source-state interaction-transfer inventory.");
}
if (census.interaction_inventory?.complete !== true ||
    !Array.isArray(census.interaction_inventory?.missing) || census.interaction_inventory.missing.length ||
    !Array.isArray(census.interaction_inventory?.cells)) {
  fail("census-interaction-inventory-incomplete", "The build census lacks a complete uncapped manifest-state interaction inventory.");
}
const expectedInteractionCells = new Map();
for (const route of manifest.routes) for (const viewport of manifest.viewports) for (const state of route.states) {
  const key = `${route.key}|${viewport.name}|${state.id}`;
  expectedInteractionCells.set(key, { route, viewport, state });
}
for (const [label, cells] of [
  ["mechanism", mechanism.interaction_transfer.cells],
  ["census", census.interaction_inventory.cells],
]) {
  const observed = new Map();
  for (const cell of cells) {
    const key = `${cell?.route_key}|${cell?.viewport}|${cell?.state_id}`;
    if (observed.has(key)) fail("interaction-inventory-duplicate", `${label} repeats interaction cell ${key}.`);
    observed.set(key, cell);
  }
  if (observed.size !== expectedInteractionCells.size || [...expectedInteractionCells.keys()].some((key) => !observed.has(key))) {
    fail("interaction-inventory-coverage", `${label} interaction inventory does not equal every authoritative route/viewport/state cell.`);
  }
  for (const [key, expected] of expectedInteractionCells) {
    const cell = observed.get(key);
    const expectedMapping = {
      rank: expected.route.mapped_reference_rank,
      id: expected.route.mapped_reference_id,
      observation: expected.route.mapped_reference_observation,
      sha256: expected.route.mapped_reference_sha256,
      state_id: expected.state.mapped_reference_state_id,
    };
    const cellMapping = cell.source_mapping || {
      rank: cell.mapped_reference?.rank,
      id: cell.mapped_reference?.id,
      observation: cell.mapped_reference?.observation,
      sha256: cell.mapped_reference?.sha256,
      state_id: cell.mapped_reference_state_id,
    };
    const trigger = cell.trigger || cell.state_trigger;
    if (JSON.stringify(cellMapping) !== JSON.stringify(expectedMapping) ||
        JSON.stringify(trigger) !== JSON.stringify(expected.state.trigger) ||
        cell.mapped_reference_state_id !== expected.state.mapped_reference_state_id ||
        cell.complete === false || cell.pass === false) {
      fail("interaction-inventory-binding", `${label} interaction cell ${key} is not bound to its exact route, source state, trigger, and passing evidence.`);
    }
  }
}
const servedRecords = [mechanism, structure, styles, census].map((record) => record.served_content_identity || record.served_content);
if (servedRecords.some((record) => !record?.complete || !/^[0-9a-f]{64}$/.test(record.sha256 || "") ||
    !Array.isArray(record.probes) || !record.probes.length ||
    !record.reload_counts || Object.values(record.reload_counts).some((count) => !Number.isInteger(count) || count < 2) ||
    !Array.isArray(record.inconsistent_reloads) || record.inconsistent_reloads.length)) {
  fail("served-content-invalid", "Every direct evidence chain must carry complete served-content response-body identity.");
}
const servedHash = servedRecords[0].sha256;
if (servedRecords.some((record) => record.sha256 !== servedHash)) {
  fail("served-content-mismatch", "Census, structure, mechanism, and style evidence were not produced from the same served response bodies.");
}

const strong = firstTable(sectionOf(dossierBody, "Strong references"));
if (!strong.rows.length) fail("no-strong-rows", "The dossier has no Strong references table.");
const rankColumn = strong.headers.findIndex((header) => /^rank$/i.test(header));
const signatureColumn = strong.headers.findIndex((header) => /^signature/i.test(header));
const observedEvidenceColumn = strong.headers.findIndex((header) => /^observed evidence$/i.test(header));
if (rankColumn === -1 || signatureColumn === -1 || observedEvidenceColumn === -1) {
  fail("strong-headers", "The Strong references table needs Rank, Observed evidence, and Signature columns.");
}

const synthesis = sectionOf(dossierBody, "Selected synthesis");
const selectedLine = synthesis.match(/^-\s+Selected positive ranks[^:]*:\s*([\d,\s]+)$/m);
const selectedRanks = new Set(selectedLine ? selectedLine[1].split(",").map((value) => Number(value.trim())).filter((value) => value > 0) : []);
const isSelected = (rank) => selectedRanks.size ? selectedRanks.has(rank) : true;
if (args.onlyRank !== null && (!Number.isInteger(args.onlyRank) || args.onlyRank < 1 || !isSelected(args.onlyRank))) {
  fail("only-rank-invalid", "--only-rank must name a selected strong reference.");
}

const components = firstTable(sectionOf(dossierBody, "Component sources"));
const componentRankColumn = components.headers.findIndex((header) => /source rank/i.test(header));
const citations = new Map();
if (componentRankColumn !== -1) for (const row of components.rows) {
  for (const match of String(row[componentRankColumn] || "").matchAll(/\d+/g)) {
    const rank = Number(match[0]);
    if (!citations.has(rank)) citations.set(rank, []);
    citations.get(rank).push((row[0] || "").trim());
  }
}

const transfers = firstTable(sectionOf(dossierBody, "Signature transfer"));
const transferRankColumn = transfers.headers.findIndex((header) => /^rank$/i.test(header));
const transferSignatureColumn = transfers.headers.findIndex((header) => /^signature/i.test(header));
const transferCarrierColumn = transfers.headers.findIndex((header) => /build part.*carr/i.test(header));
if (transferRankColumn === -1 || transferSignatureColumn === -1 || transferCarrierColumn === -1) {
  fail("signature-transfer-headers", "The Signature transfer table needs Rank, Signature, and The build part that carries it columns.");
}
const transferByRank = new Map();
for (const row of transfers.rows) {
  const rank = Number(String(row[transferRankColumn] || "").trim());
  if (!Number.isInteger(rank) || rank < 1) continue;
  if (transferByRank.has(rank)) fail("signature-transfer-duplicate", `Signature transfer has more than one row for rank ${rank}.`);
  transferByRank.set(rank, {
    signature: String(row[transferSignatureColumn] || "").trim(),
    carrier: String(row[transferCarrierColumn] || "").trim(),
  });
}

const censusNames = new Set(Array.isArray(census.names) ? census.names : []);
const censusByName = new Map((Array.isArray(census.census) ? census.census : []).map((item) => [item?.name, item]));
if (!censusNames.size || censusByName.size !== censusNames.size) {
  fail("census-components-invalid", "The census must expose one exact component record for every name.");
}

const observationBySha = new Map();
for (const binding of mappedByRoute.values()) {
  if (observationBySha.has(binding.sha256)) continue;
  if (args.onlyRank !== null && (!binding.payload.first_screen_mechanisms_by_viewport?.wide ||
      !binding.payload.first_screen_mechanisms_by_viewport?.narrow)) {
    fail("observation-stale", `${binding.observation} lacks first-screen mechanism sheets.`);
  }
  observationBySha.set(binding.sha256, {
    ...binding,
    ...observationSummary(binding.payload, args.onlyRank !== null),
  });
}

function boundObservationFromStrongRow(row, rank) {
  const cell = String(row[observedEvidenceColumn] || "");
  const match = cell.match(/(\.design-dna\/references\/[A-Za-z0-9._:-]+-observation\.json)[^|\n]*?sha256:([0-9a-f]{64})/i);
  if (!match) return null;
  const observed = observationBySha.get(match[2].toLowerCase());
  if (!observed || observed.rank !== rank || observed.observation !== match[1]) return null;
  return observed;
}

function mechanismCarriesComponent(mechanismValue, component) {
  if (!mechanismValue || !component) return false;
  if (Array.isArray(mechanismValue.components) && mechanismValue.components.includes(component)) return true;
  if (component.startsWith("class:")) {
    const wanted = decodeURIComponent(component.slice(6));
    return String(mechanismValue.cls || "").trim().split(/\s+/).includes(wanted);
  }
  if (component.startsWith("tag:")) return String(mechanismValue.tag || "").toLowerCase() === component.slice(4).toLowerCase();
  if (component.startsWith("id:")) return String(mechanismValue.id || "") === decodeURIComponent(component.slice(3));
  return false;
}

const verdicts = [];
for (const row of strong.rows) {
  const rank = Number((row[rankColumn] || "").trim());
  if (!Number.isFinite(rank)) continue;
  const selected = isSelected(rank) && (args.onlyRank === null || rank === args.onlyRank);
  const signature = (row[signatureColumn] || "").trim();
  const modeMatch = signature.match(/^(motion|static):\s*(.+)$/i);
  const observed = boundObservationFromStrongRow(row, rank), componentRows = citations.get(rank) || [];
  const transfer = transferByRank.get(rank) || null;
  const carrier = transfer?.carrier || "";
  const carrierCensus = censusByName.get(carrier) || null;
  const exactBinding = (check) => check?.mapped_reference?.rank === rank && check.mapped_reference.id === observed?.id &&
    check.mapped_reference.sha256 === observed?.sha256 && check.mapped_reference.observation === observed?.observation;
  const mechanismChecks = (mechanism.checks || []).filter(exactBinding);
  const structureChecks = (structure.routes || []).filter(exactBinding);
  const carrierRoutes = new Set(Array.isArray(carrierCensus?.routes) ? carrierCensus.routes : []);
  const result = {
    rank, selected, signature, mode: modeMatch?.[1].toLowerCase() || null,
    transfer_signature: transfer?.signature || null, carrier_component: carrier || null,
    component_rows: componentRows,
    observation: observed?.observation || null,
    observation_sha256: observed?.sha256 || null,
    loudest_recorded: observed?.loudest?.type || null,
    loudest_weight: observed?.loudest ? mechanismWeight(observed.loudest) : 0,
    scroll_coverage: observed?.scrollCoverage || null,
    mapped_mechanism_cells: mechanismChecks.length, mapped_structure_cells: structureChecks.length,
  };
  const failures = [];
  if (selected && !observed) failures.push("the Strong references row does not bind an exact manifest-mapped observation path and SHA-256");
  if (selected && !modeMatch) failures.push("Signature must begin motion: or static:");
  if (selected && !componentRows.length) failures.push("no component source row cites this rank");
  if (selected && !transfer) failures.push("no Signature transfer row exists for this selected rank");
  if (selected && transfer && transfer.signature !== signature) failures.push("Signature transfer text is not an exact copy of the Strong references signature");
  if (selected && !carrier) failures.push("Signature transfer names no exact census component as its carrier");
  if (selected && carrier && !censusNames.has(carrier)) failures.push(`signature carrier ${carrier} is not an exact component key in the bound census`);
  if (selected && carrier && !componentRows.includes(carrier)) failures.push(`signature carrier ${carrier} has no Component sources row citing rank ${rank}`);
  if (selected && modeMatch?.[2].trim().length < 12) failures.push("signature description is too vague to identify a grammar");
  if (selected && observed && modeMatch?.[1].toLowerCase() === "motion") {
    const named = claimedTypes(modeMatch[2]);
    result.signature_names = [...named];
    if (!observed.loudest) failures.push("motion: was claimed but the observation records no mechanism");
    else if (!named.has(observed.loudest.type)) failures.push(`signature names ${[...named].join(", ") || "no recognized mechanism"}, but the dominant measured mechanism is ${observed.loudest.type}`);
    if (!mechanismChecks.length) failures.push("no build route is mapped to this motion reference");
    const carrierMechanismChecks = mechanismChecks.filter((check) => {
      if (!carrierRoutes.has(check.route_key)) return false;
      const profile = Number(check.width) <= 430 ? "narrow" : "wide";
      const sourceCell = observed.payload.states_by_viewport?.[profile]?.[check.mapped_reference_state_id];
      return (sourceCell?.mechanisms || []).some((item) => item.type === observed.loudest?.type);
    });
    if (!carrierMechanismChecks.length) failures.push(`signature carrier ${carrier || "(missing)"} is not present on a route mapped to this observation`);
    for (const check of carrierMechanismChecks) if (!check.pass || check.build_loudest !== observed.loudest?.type ||
        !check.loudest_type_match || Number(check.loudest_magnitude_relative_delta) > Number(check.loudest_magnitude_tolerance) ||
        check.trigger_diff?.pass !== true || check.state_contract_match !== true ||
        !check.evidence_frames || !["before", "after", "settled"].every((phase) =>
          /^[0-9a-f]{64}$/.test(check.evidence_frames?.[phase]?.sha256 || "") &&
          Number.isInteger(check.evidence_frames?.[phase]?.bytes) && check.evidence_frames[phase].bytes > 0) ||
        (!((check.build_mechanisms || []).some((item) => item.type === observed.loudest?.type && mechanismCarriesComponent(item, carrier))) &&
          !(check.state_application?.trigger_evidence?.target_component_keys || [])
            .some((key) => key === carrier || carrier.endsWith(`|${key}`)) &&
          !(check.interaction_diff?.target_transfers || []).some((transfer) =>
            (transfer.build_component_keys || []).some((key) => key === carrier || carrier.endsWith(`|${key}`))))) {
      failures.push(`${check.route_key}/${check.viewport} does not render dominant ${observed.loudest?.type}`);
    }
  }
  if (selected && observed && modeMatch?.[1].toLowerCase() === "static") {
    if (observed.strongMotion) failures.push(`static: contradicts dominant measured motion ${observed.loudest?.type} (weight ${result.loudest_weight})`);
    if (!structureChecks.length) failures.push("no build route is mapped to this static reference");
    const profiles = new Set(structureChecks.filter((check) => check.pass).map((check) => check.width <= 430 ? "narrow" : "wide"));
    if (!profiles.has("wide") || !profiles.has("narrow")) failures.push("mapped structure does not pass at both wide and narrow profiles");
    if (carrier && !structureChecks.some((check) => carrierRoutes.has(check.route_key))) failures.push(`signature carrier ${carrier} is not present on a structurally matched route`);
    if (!styles.ok) failures.push("style provenance did not pass");
  }
  result.status = selected ? (failures.length ? "fail" : "pass") : "listed";
  result.failures = failures;
  verdicts.push(result);
}

const failed = verdicts.filter((verdict) => verdict.selected && verdict.status === "fail");
const record = {
  tool: TOOL_NAME, schema_version: SCHEMA_VERSION, producer_script_sha256: PRODUCER_SCRIPT_SHA256,
  runtime_identity: {
    "check_signature_transfer.mjs": PRODUCER_SCRIPT_SHA256,
    "observe_reference.mjs": scriptHash("observe_reference.mjs"),
    "compare_mechanisms.mjs": scriptHash("compare_mechanisms.mjs"),
    "compare_structure.mjs": scriptHash("compare_structure.mjs"),
    "check_style_provenance.mjs": scriptHash("check_style_provenance.mjs"),
    "scan_build_components.mjs": scriptHash("scan_build_components.mjs"),
    "provenance_contract.mjs": PROVENANCE_CONTRACT_SHA256,
  },
  checked_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
  build_id: args.buildId, run_id: args.runId,
  manifest_id: manifest.manifest_id, manifest_file: args.manifest, manifest_sha256: manifest.__sha256,
  only_rank: args.onlyRank,
  dossier: args.dossier, dossier_sha256: sha256(args.dossier),
  evidence_hashes: {
    mechanism_diff: sha256(args.mechanismDiff), structure_diff: sha256(args.structureDiff),
    style_provenance: sha256(args.styleProvenance), census: sha256(args.census),
  },
  served_content_identity: servedRecords[0],
  served_content_sha256: servedHash,
  verdicts, pass: !failed.length,
  verdict: !failed.length ? "Every selected signature is bound to its exact observation, exact census carrier, component-source row, and matching dominant wide/narrow build evidence." :
    `${failed.length} selected reference signature(s) failed transfer: ${failed.map((item) => `rank ${item.rank}: ${item.failures.join("; ")}`).join(" | ")}`,
};
fs.mkdirSync(path.dirname(args.out), { recursive: true });
fs.writeFileSync(args.out, JSON.stringify(record, null, 2) + "\n", "utf8");
process.stdout.write(JSON.stringify({ ok: true, pass: record.pass, record: args.out, verdict: record.verdict }, null, 2) + "\n");
process.exit(record.pass ? 0 : 1);
