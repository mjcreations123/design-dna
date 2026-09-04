#!/usr/bin/env node
/** Strict route-manifest and exact reference-observation bindings. */

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const MANIFEST_SCHEMA_VERSION = 2;
export const PRODUCER_OUTPUT_SCHEMA_VERSION = 3;
export const SHA256_RE = /^[0-9a-f]{64}$/;
export const ROUTE_FIELDS = [
  "key",
  "mapped_reference_id",
  "mapped_reference_observation",
  "mapped_reference_rank",
  "mapped_reference_sha256",
  "states",
  "url",
];
const TOP_LEVEL_FIELDS = ["manifest_id", "routes", "schema_version", "viewports"];
const VIEWPORT_FIELDS = ["height", "name", "width"];
const STATE_FIELDS = ["expectation", "id", "kind", "mapped_reference_state_id", "trigger"];
const TRIGGER_FIELDS = ["target", "type", "value"];
const STATE_KINDS = new Set(["rest", "interactive", "system", "data"]);
const TRIGGER_TYPES = new Set(["none", "hover", "focus", "click", "keyboard", "input", "url", "programmatic"]);
const RUNTIME_DIR = path.dirname(fileURLToPath(import.meta.url));
const CURRENT_STRUCTURE_PROBE_SHA256 = sha256File(path.join(RUNTIME_DIR, "structure_probe.mjs"));
const CURRENT_BROWSER_EVIDENCE_SHA256 = sha256File(path.join(RUNTIME_DIR, "browser_evidence.mjs"));
const CURRENT_PLAYWRIGHT_RESOLVER_SHA256 = sha256File(path.join(RUNTIME_DIR, "playwright_resolver.mjs"));

export function sha256Bytes(value) {
  return createHash("sha256").update(value).digest("hex");
}

export function sha256File(file) {
  return sha256Bytes(fs.readFileSync(file));
}

function exactKeys(value, expected) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const actual = Object.keys(value).sort();
  return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
}

function normalizeUrl(value) {
  const parsed = new URL(value);
  if (!/^https?:$/.test(parsed.protocol)) throw new Error(`unsupported URL protocol ${parsed.protocol}`);
  if (parsed.username || parsed.password) throw new Error("credential-bearing URLs are forbidden in provenance records");
  parsed.hash = "";
  return parsed.href;
}

function rankOfObservation(payload) {
  const match = String(payload?.id || "").match(/^strong-(\d+)(?:$|[-_.:])/i);
  return match ? Number(match[1]) : null;
}

function isWithin(parent, child) {
  const relative = path.relative(path.resolve(parent), path.resolve(child));
  return relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative));
}

export function loadRouteManifest(file) {
  const manifestFile = path.resolve(file);
  let payload;
  try {
    const stat = fs.lstatSync(manifestFile);
    if (!stat.isFile() || stat.isSymbolicLink()) throw new Error("route manifest must be an ordinary file, not a link");
    payload = JSON.parse(fs.readFileSync(manifestFile, "utf8"));
  } catch (error) {
    throw new Error(`route manifest is unreadable JSON: ${String(error).slice(0, 180)}`);
  }
  if (!exactKeys(payload, TOP_LEVEL_FIELDS) || payload.schema_version !== MANIFEST_SCHEMA_VERSION) {
    throw new Error(`route manifest must have schema_version ${MANIFEST_SCHEMA_VERSION} and exactly schema_version, manifest_id, viewports, routes`);
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/.test(payload.manifest_id || "")) {
    throw new Error("manifest_id must be an immutable 8-128 character slug or hash identity");
  }
  if (!Array.isArray(payload.viewports) || !payload.viewports.length || !Array.isArray(payload.routes) || !payload.routes.length) {
    throw new Error("route manifest needs non-empty viewports and routes arrays");
  }
  const viewportNames = new Set();
  for (const viewport of payload.viewports) {
    if (!exactKeys(viewport, VIEWPORT_FIELDS) || !/^[a-z][a-z0-9-]{0,31}$/.test(viewport.name || "") ||
        viewportNames.has(viewport.name) || !Number.isInteger(viewport.width) || viewport.width < 280 ||
        !Number.isInteger(viewport.height) || viewport.height < 480) {
      throw new Error("every viewport must have exact name/width/height fields, a unique slug, and sensible integer dimensions");
    }
    viewportNames.add(viewport.name);
  }
  if (!payload.viewports.some((item) => item.width >= 1280) || !payload.viewports.some((item) => item.width <= 430)) {
    throw new Error("route manifest must include both wide and narrow viewports");
  }
  const routeKeys = new Set(), routeUrls = new Set(), routeOrigins = new Set();
  for (const route of payload.routes) {
    if (!exactKeys(route, ROUTE_FIELDS)) throw new Error(`every route must contain exactly ${ROUTE_FIELDS.join(", ")}`);
    if (!/^[a-z][a-z0-9-]{0,47}$/.test(route.key || "") || routeKeys.has(route.key)) {
      throw new Error("route keys must be unique lowercase slugs");
    }
    let normalized;
    try { normalized = normalizeUrl(route.url); } catch (error) { throw new Error(`route ${route.key}: ${error.message}`); }
    if (normalized !== route.url || routeUrls.has(normalized)) throw new Error(`route ${route.key} URL is noncanonical or duplicated`);
    if (!Number.isInteger(route.mapped_reference_rank) || route.mapped_reference_rank < 1) {
      throw new Error(`route ${route.key} needs a positive mapped_reference_rank`);
    }
    const referenceMatch = String(route.mapped_reference_id || "").match(/^strong-([1-9][0-9]*)$/);
    if (!referenceMatch || Number(referenceMatch[1]) !== route.mapped_reference_rank) {
      throw new Error(`route ${route.key} mapped_reference_id must be the exact strong-N identity for its rank`);
    }
    const expectedObservation = `.design-dna/references/${route.mapped_reference_id}-observation.json`;
    if (route.mapped_reference_observation !== expectedObservation) {
      throw new Error(`route ${route.key} mapped_reference_observation must be exactly ${expectedObservation}`);
    }
    if (!SHA256_RE.test(route.mapped_reference_sha256 || "")) {
      throw new Error(`route ${route.key} has an invalid mapped_reference_sha256`);
    }
    if (!Array.isArray(route.states) || !route.states.length) throw new Error(`route ${route.key} states must be a non-empty array`);
    const stateIds = new Set();
    for (const state of route.states) {
      if (!exactKeys(state, STATE_FIELDS) || !/^[a-z][a-z0-9-]{0,47}$/.test(state.id || "") || stateIds.has(state.id) ||
          !STATE_KINDS.has(state.kind) || !exactKeys(state.trigger, TRIGGER_FIELDS) || !TRIGGER_TYPES.has(state.trigger.type) ||
          !/^[a-z][a-z0-9-]{0,47}$/.test(state.mapped_reference_state_id || "") ||
          typeof state.trigger.target !== "string" || !state.trigger.target.trim() ||
          !(state.trigger.value === null || typeof state.trigger.value === "string") ||
          typeof state.expectation !== "string" || state.expectation.trim().length < 12) {
        throw new Error(`route ${route.key} has an invalid, duplicate, or underspecified state contract`);
      }
      stateIds.add(state.id);
    }
    const rest = route.states[0];
    if (rest.id !== "rest" || rest.kind !== "rest" || rest.trigger.type !== "none" ||
        rest.trigger.target !== "document" || rest.trigger.value !== null || rest.expectation !== "initial settled route" ||
        rest.mapped_reference_state_id !== "rest") {
      throw new Error(`route ${route.key} must begin with the exact rest-state contract`);
    }
    routeKeys.add(route.key); routeUrls.add(normalized); routeOrigins.add(new URL(normalized).origin);
  }
  if (routeOrigins.size !== 1) throw new Error("every route in the manifest must share one exact build origin");
  return {
    ...payload,
    __file: manifestFile,
    __sha256: sha256File(manifestFile),
  };
}

export function resolveMappedObservation(manifest, route, expectedProducerSha256) {
  const manifestFile = path.resolve(manifest.__file || "");
  const dnaRoot = path.dirname(manifestFile);
  if (path.basename(dnaRoot) !== ".design-dna") {
    throw new Error("route manifest must live directly in the project's .design-dna directory");
  }
  const projectRoot = path.dirname(dnaRoot);
  const referenceRoot = path.resolve(dnaRoot, "references");
  const observationFile = path.resolve(projectRoot, ...route.mapped_reference_observation.split("/"));
  let referenceReal, observationReal;
  try {
    const dnaStat = fs.lstatSync(dnaRoot), referenceStat = fs.lstatSync(referenceRoot), observationStat = fs.lstatSync(observationFile);
    if (!dnaStat.isDirectory() || dnaStat.isSymbolicLink() || !referenceStat.isDirectory() || referenceStat.isSymbolicLink() ||
        !observationStat.isFile() || observationStat.isSymbolicLink()) throw new Error("linked or non-ordinary provenance path");
    referenceReal = fs.realpathSync(referenceRoot);
    observationReal = fs.realpathSync(observationFile);
  } catch (error) {
    throw new Error(`route ${route.key} mapped observation is not an ordinary in-project file: ${String(error).slice(0, 120)}`);
  }
  if (!isWithin(referenceRoot, observationFile) || path.dirname(observationFile) !== referenceRoot ||
      !isWithin(referenceReal, observationReal) || path.dirname(observationReal) !== referenceReal) {
    throw new Error(`route ${route.key} mapped observation escapes .design-dna/references`);
  }
  let bytes, payload;
  try {
    bytes = fs.readFileSync(observationFile);
    payload = JSON.parse(bytes.toString("utf8"));
  } catch (error) {
    throw new Error(`route ${route.key} mapped observation is unreadable: ${String(error).slice(0, 160)}`);
  }
  const digest = sha256Bytes(bytes);
  if (digest !== route.mapped_reference_sha256) throw new Error(`route ${route.key} mapped observation SHA-256 does not match its exact bytes`);
  if (payload?.tool !== "observe_reference.mjs" || !Number.isInteger(payload.schema_version) || payload.schema_version < 5 ||
      payload.producer_script_sha256 !== expectedProducerSha256 ||
      payload.runtime_identity?.["structure_probe.mjs"] !== CURRENT_STRUCTURE_PROBE_SHA256 ||
      payload.runtime_identity?.["browser_evidence.mjs"] !== CURRENT_BROWSER_EVIDENCE_SHA256 ||
      payload.runtime_identity?.["playwright_resolver.mjs"] !== CURRENT_PLAYWRIGHT_RESOLVER_SHA256) {
    throw new Error(`route ${route.key} mapped observation was not emitted by the current observer runtime`);
  }
  if (payload.id !== route.mapped_reference_id) throw new Error(`route ${route.key} mapped_reference_id does not equal observation payload id`);
  if (rankOfObservation(payload) !== route.mapped_reference_rank) throw new Error(`route ${route.key} mapped_reference_rank does not equal observation id rank`);
  let sourceUrl;
  try { sourceUrl = normalizeUrl(payload.url); } catch { throw new Error(`route ${route.key} observation has no canonical HTTP(S) source URL`); }
  if (sourceUrl !== payload.url) throw new Error(`route ${route.key} observation URL is not canonical`);
  const states = payload.states_by_viewport;
  for (const viewport of ["wide", "narrow"]) {
    if (!states?.[viewport] || typeof states[viewport] !== "object" || Array.isArray(states[viewport])) {
      throw new Error(`route ${route.key} observation lacks current ${viewport} state evidence`);
    }
    for (const state of route.states) {
      if (!Object.prototype.hasOwnProperty.call(states[viewport], state.mapped_reference_state_id)) {
        throw new Error(`route ${route.key} state ${state.id} maps to missing ${viewport} observation state ${state.mapped_reference_state_id}`);
      }
    }
  }
  return {
    rank: route.mapped_reference_rank,
    id: route.mapped_reference_id,
    observation: route.mapped_reference_observation,
    sha256: digest,
    url: payload.url,
    file: observationFile,
    payload,
  };
}

export function bindSuppliedObservations(manifest, suppliedFiles, expectedProducerSha256) {
  const supplied = new Map(suppliedFiles.map((file) => [path.resolve(file), path.resolve(file)]));
  const mapped = new Map();
  for (const route of manifest.routes) {
    const binding = resolveMappedObservation(manifest, route, expectedProducerSha256);
    if (!supplied.has(binding.file)) {
      throw new Error(`route ${route.key} exact mapped observation was not supplied: ${binding.observation}`);
    }
    mapped.set(route.key, binding);
  }
  const required = new Set([...mapped.values()].map((binding) => binding.file));
  const extras = [...supplied.keys()].filter((file) => !required.has(file));
  if (extras.length) throw new Error(`unmapped observation input(s) were supplied: ${extras.map((file) => path.basename(file)).join(", ")}`);
  return mapped;
}
