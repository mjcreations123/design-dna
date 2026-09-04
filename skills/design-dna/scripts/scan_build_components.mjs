#!/usr/bin/env node
/** Enumerate every visible component across the authoritative route/state/viewport matrix. */

import fs from "node:fs";
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import {
  aggregateServedContent,
  applyManifestState,
  beginServedContentCapture,
  captureInteractionCensus,
  installDomInspection,
  navigateExact,
  normalizeHttpUrl,
  sha256,
  traverseScrollSurfaces,
  validateManifestState,
} from "./browser_evidence.mjs";
import { browserExecutableIdentity, discoverBrowserExecutable, resolvePlaywright } from "./playwright_resolver.mjs";

const TOOL_NAME = "scan_build_components.mjs";
const SCHEMA_VERSION = 3;
const SCRIPT_PATH = path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const PRODUCER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(SCRIPT_PATH)).digest("hex");
const SCRIPT_DIR = path.dirname(SCRIPT_PATH);
const OBSERVER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "observe_reference.mjs"))).digest("hex");
const BROWSER_EVIDENCE_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "browser_evidence.mjs"))).digest("hex");
const PLAYWRIGHT_RESOLVER_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "playwright_resolver.mjs"))).digest("hex");
const SHA256_RE = /^[0-9a-f]{64}$/;
const ROUTE_FIELDS = new Set([
  "key", "url", "mapped_reference_rank", "mapped_reference_id",
  "mapped_reference_observation", "mapped_reference_sha256", "states",
]);

function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }, null, 2) + "\n");
  process.exit(2);
}

export function classKeys(className) {
  return [...new Set(String(className || "").trim().split(/\s+/).filter(Boolean)
    .map((token) => encodeURIComponent(token))
    .filter(Boolean).map((token) => `class:${token}`))].sort();
}

/* Backward-compatible export, but intentionally no longer collapses BEM or
   trusts the first class.  A caller asking for one name receives the complete
   class signature, so two unrelated elements cannot hide under a common stem. */
export function stemOf(className) {
  return classKeys(className).join("+");
}

export function firstScreenScopePass(scope) {
  if (!scope || !Number.isFinite(scope.document_height) || !Number.isFinite(scope.viewport_height)) return false;
  const first = (scope.substantial_regions || []).filter((region) => region.top < scope.viewport_height && region.bottom > 0);
  return first.length === 1 && (scope.beyond_first_screen_regions || []).length === 0 &&
    scope.document_height <= scope.viewport_height;
}

function sourceTargetSemanticKeys(census, mappedReferenceStateId) {
  const keys = new Set();
  for (const pageRecord of census?.pages || []) {
    for (const target of pageRecord?.targets || []) {
      const semanticKey = typeof target?.semantic_key === "string" ? target.semantic_key.trim() : "";
      const sourceStateIds = Array.isArray(target?.source_state_ids) ? target.source_state_ids : [];
      if (semanticKey && (!sourceStateIds.length || sourceStateIds.includes(mappedReferenceStateId))) keys.add(semanticKey);
    }
  }
  return keys;
}

/** Allow a responsive omission only when this exact role/text semantic is
 * absent in the mapped source profile and present in the opposite source
 * profile. A global target-count delta can excuse the wrong control. */
export function reconcileResponsiveHiddenControls(
  candidates,
  sourceCurrent,
  sourceOpposite,
  mappedReferenceStateId,
  sourceProfile,
) {
  return responsiveControlParity(
    candidates,
    [],
    sourceCurrent,
    sourceOpposite,
    mappedReferenceStateId,
    sourceProfile,
  ).findings;
}

export function responsiveControlParity(
  candidates,
  buildVisibleSemanticKeys,
  sourceCurrent,
  sourceOpposite,
  mappedReferenceStateId,
  sourceProfile,
) {
  const currentKeys = sourceTargetSemanticKeys(sourceCurrent, mappedReferenceStateId);
  const oppositeKeys = sourceTargetSemanticKeys(sourceOpposite, mappedReferenceStateId);
  const authorizedOmissions = new Set(
    [...oppositeKeys].filter((semanticKey) => !currentKeys.has(semanticKey)),
  );
  const findings = (candidates || [])
    .filter((candidate) => !authorizedOmissions.has(candidate?.semantic_key))
    .map((candidate) => ({
      ...candidate,
      source_profile: sourceProfile,
      mapped_reference_state_id: mappedReferenceStateId,
      source_authorized_omission: false,
    }));
  return {
    source_profile: sourceProfile,
    mapped_reference_state_id: mappedReferenceStateId,
    source_current_semantic_keys: [...currentKeys].sort(),
    source_opposite_semantic_keys: [...oppositeKeys].sort(),
    source_authorized_omissions: [...authorizedOmissions].sort(),
    build_visible_semantic_keys: [...new Set(buildVisibleSemanticKeys || [])].sort(),
    findings,
    complete: findings.length === 0,
  };
}

const CENSUS_SCRIPT = `(() => {
  const semantic = new Set(['header','main','section','article','aside','nav','footer','form','button',
    'input','textarea','select','table','thead','tbody','tr','th','td','ul','ol','li','h1','h2','h3',
    'h4','h5','h6','img','video','picture','canvas','svg','details','summary','a']);
  const seen = new Map();
  const visibleDecisionIds = new Set();
  const unsourcedVisibleParts = new Set();
  const visible = (el) => {
    const s = getComputedStyle(el), box = el.getBoundingClientRect();
    if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) === 0) return null;
    if (box.width <= 1 || box.height <= 1) return null;
    if (window.__dnaFirstScreenOnly && (box.bottom <= 0 || box.top >= innerHeight)) return null;
    return { s, box };
  };
  const note = (name, el, box) => {
    const row = seen.get(name) || { name, count: 0, area: 0, tags: [], samples: [] };
    row.count += 1;
    row.area = Math.max(row.area, Math.max(0, box.width * box.height) / (innerWidth * innerHeight));
    const tag = el.tagName.toLowerCase();
    if (!row.tags.includes(tag) && row.tags.length < 8) row.tags.push(tag);
    const sample = (el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 64);
    if (sample && !row.samples.includes(sample) && row.samples.length < 3) row.samples.push(sample);
    seen.set(name, row);
  };
  const inspection = { document_roots: 0, open_shadow_roots: 0, captured_closed_shadow_roots: 0, same_origin_iframes: 0,
    hook_installed: window.__designDnaDomInspection === 'response-bodies-v1',
    blocked_frames: [], unknown_closed_surfaces: [], pseudo_elements: 0, canvases: [], complete: true };
  const links = new Set();
  const roots = [];
  const enqueueRoot = (root, scope, mode = null) => {
    if (!root || roots.some((item) => item.root === root)) return;
    roots.push({ root, scope });
    if (root.nodeType === 9) inspection.document_roots += 1;
    else if (mode === 'closed') inspection.captured_closed_shadow_roots += 1;
    else inspection.open_shadow_roots += 1;
  };
  enqueueRoot(document, 'document');
  for (let rootIndex = 0; rootIndex < roots.length; rootIndex += 1) {
    const { root, scope } = roots[rootIndex];
    if (root.nodeType === 9) {
      const captured = root.defaultView.__designDnaCapturedShadowRoots || [];
      captured.forEach((item) => enqueueRoot(item.root, scope + '>shadow:' + item.host.tagName.toLowerCase(), item.mode));
    }
    root.querySelectorAll('*').forEach((el) => {
      if (el.shadowRoot) enqueueRoot(el.shadowRoot, scope + '>shadow:' + el.tagName.toLowerCase());
      if (el.tagName === 'IFRAME') {
        try {
          if (el.contentDocument) { inspection.same_origin_iframes += 1; enqueueRoot(el.contentDocument, scope + '>iframe'); }
          else throw new Error('no contentDocument');
        } catch {
          const box = el.getBoundingClientRect();
          if (box.width > 1 && box.height > 1) inspection.blocked_frames.push(el.src || '(unattributed iframe)');
        }
      }
    });
  }
  const capturedHosts = new Set(roots.filter(({ root }) => root.nodeType === 9)
    .flatMap(({ root }) => (root.defaultView.__designDnaCapturedShadowRoots || []).map((item) => item.host)));
  for (const { root } of roots) root.querySelectorAll('*').forEach((element) => {
    if (!element.tagName.includes('-') || element.shadowRoot || capturedHosts.has(element) || element.childNodes.length) return;
    const box = element.getBoundingClientRect();
    if (box.width > 1 && box.height > 1) inspection.unknown_closed_surfaces.push(element.tagName.toLowerCase());
  });
  for (const { root, scope } of roots) root.querySelectorAll('*').forEach((el) => {
    const v = visible(el); if (!v) return;
    const tag = el.tagName.toLowerCase();
    const keys = [];
    const classes = String(el.getAttribute('class') || '').trim().split(/\\s+/).filter(Boolean);
    for (const raw of classes) {
      const token = encodeURIComponent(raw);
      if (token) keys.push('class:' + token);
    }
    if (el.id) keys.push('id:' + encodeURIComponent(String(el.id)));
    const role = el.getAttribute('role'); if (role) keys.push('role:' + encodeURIComponent(role.toLowerCase()));
    if (semantic.has(tag)) keys.push('tag:' + tag);
    const paints = v.s.backgroundImage !== 'none' || v.s.backgroundColor !== 'rgba(0, 0, 0, 0)' ||
      parseFloat(v.s.borderTopWidth) > 0 || v.s.boxShadow !== 'none' ||
      ['IMG','VIDEO','PICTURE','CANVAS','SVG'].includes(el.tagName);
    const ownsText = [...el.childNodes].some((n) => n.nodeType === 3 && n.nodeValue.trim());
    const decisionOwner = el.closest('[data-design-dna-decision-id]');
    const decisionId = decisionOwner?.getAttribute('data-design-dna-decision-id')?.trim() || '';
    if (decisionId) visibleDecisionIds.add(decisionId);
    else if (paints || ownsText || semantic.has(tag)) unsourcedVisibleParts.add((scope === 'document' ? '' : scope + '|') +
      (keys[0] || 'tag:' + tag + ':unclassed'));
    if (!keys.length && (paints || ownsText)) keys.push('tag:' + tag + ':unclassed');
    [...new Set(keys)].forEach((key) => note((scope === 'document' ? '' : scope + '|') + key, el, v.box));
    for (const pseudo of ['::before', '::after']) {
      const style = getComputedStyle(el, pseudo);
      const content = String(style.content || '');
      const paints = content !== 'none' && content !== 'normal' || style.backgroundImage !== 'none' ||
        style.backgroundColor !== 'rgba(0, 0, 0, 0)' || parseFloat(style.borderTopWidth) > 0 || style.boxShadow !== 'none';
      if (!paints || style.display === 'none' || Number(style.opacity) === 0) continue;
      inspection.pseudo_elements += 1;
      const owner = keys[0] || 'tag:' + tag + ':unclassed';
      note((scope === 'document' ? '' : scope + '|') + 'pseudo:' + pseudo.slice(2) + ':' + owner, el, v.box);
    }
    if (el.tagName === 'CANVAS') {
      try {
        const encoded = el.toDataURL('image/png');
        inspection.canvases.push({ width: el.width, height: el.height, readable: true,
          rendered_bytes_base64: Math.max(0, encoded.length - encoded.indexOf(',') - 1),
          fingerprint: encoded.slice(0, 96) + ':' + encoded.slice(-96) });
      } catch (error) {
        inspection.canvases.push({ width: el.width, height: el.height, readable: false, error: String(error).slice(0, 120) });
      }
    }
    if (el.tagName === 'A' && el.hasAttribute('href') && !el.hasAttribute('download')) {
      try {
        const u = new URL(el.getAttribute('href'), el.ownerDocument.location.href);
        if (/^https?:$/.test(u.protocol) && u.origin === location.origin) { u.hash = ''; links.add(u.href); }
      } catch { /* invalid links are not routes */ }
    }
  });
  inspection.complete = inspection.hook_installed && inspection.blocked_frames.length === 0 && inspection.unknown_closed_surfaces.length === 0 && inspection.canvases.length === 0;
  const regionCandidates = [...document.querySelectorAll('body > section,body > article,body > main,main > section,main > article,main > div,[role="main"] > *')]
    .filter((element) => { const style = getComputedStyle(element), box = element.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && box.height >= 80 && box.width >= innerWidth * 0.5; });
  const regionSet = regionCandidates.filter((element) => !regionCandidates.some((other) => other !== element && element.contains(other)));
  const substantial_regions = regionSet.map((element) => {
    const box = element.getBoundingClientRect();
    const classes = String(element.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean).sort();
    return { top: Math.round(box.top + scrollY), bottom: Math.round(box.bottom + scrollY), tag: element.tagName.toLowerCase(),
      component_identity: element.id ? 'id:' + element.id : classes.length ? 'class:' + classes.join('.') : 'tag:' + element.tagName.toLowerCase() };
  }).sort((a, b) => a.top - b.top || a.bottom - b.bottom);
  const implementation_scope = { document_height: Math.round(document.documentElement.scrollHeight), viewport_height: innerHeight,
    substantial_regions, beyond_first_screen_regions: substantial_regions.filter((region) => region.top >= innerHeight) };
  return {
    components: [...seen.values()].map((row) => ({ ...row, area: +row.area.toFixed(4) }))
      .sort((a, b) => b.area - a.area || a.name.localeCompare(b.name)),
    links: [...links].sort(), inspection, implementation_scope,
    visible_decision_ids: [...visibleDecisionIds].sort(),
    unsourced_visible_parts: [...unsourcedVisibleParts].sort(),
  };
})()`;

function parseArgs(argv) {
  const out = { manifest: null, out: null, buildId: null, runId: null, routeKeys: [], firstScreen: false,
    browserExecutable: process.env.DESIGN_DNA_BROWSER_EXECUTABLE || process.env.CHROME || null };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--manifest") out.manifest = argv[++i];
    else if (arg === "--out") out.out = argv[++i];
    else if (arg === "--build-id") out.buildId = argv[++i];
    else if (arg === "--run-id") out.runId = argv[++i];
    else if (arg === "--route-key") out.routeKeys.push(argv[++i]);
    else if (arg === "--first-screen") out.firstScreen = true;
    else if (arg === "--browser-executable" || arg === "--chrome") out.browserExecutable = argv[++i];
    else if (arg === "--help" || arg === "-h") {
      process.stdout.write("scan_build_components.mjs --manifest FILE --build-id ID --run-id ID --out FILE [--browser-executable FILE]\n");
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${arg}`);
  }
  if (!out.manifest || !out.buildId || !out.runId || !out.out) fail("usage", "--manifest, --build-id, --run-id and --out are required.");
  return out;
}

function readManifest(file) {
  let payload;
  try { payload = JSON.parse(fs.readFileSync(file, "utf8")); }
  catch (error) { fail("manifest-unreadable", `${file}: ${String(error).slice(0, 160)}`); }
  if (payload?.schema_version !== 2 || !/^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/.test(payload.manifest_id || "") ||
      Object.keys(payload).some((key) => !["schema_version", "manifest_id", "viewports", "routes"].includes(key)) ||
      !Array.isArray(payload.routes) || !Array.isArray(payload.viewports)) {
    fail("manifest-invalid", "The route manifest must use schema 2 with only manifest_id, routes, and viewports.");
  }
  const viewportNames = new Set();
  for (const viewport of payload.viewports) {
    if (!viewport || Object.keys(viewport).some((key) => !["name", "width", "height"].includes(key)) ||
        typeof viewport.name !== "string" || viewportNames.has(viewport.name) || !Number.isInteger(viewport.width) ||
        !Number.isInteger(viewport.height) || viewport.width < 240 || viewport.height < 240) {
      fail("manifest-invalid", "Viewport entries must have unique names and exact integer width/height fields.");
    }
    viewportNames.add(viewport.name);
  }
  if (!payload.viewports.some((viewport) => viewport.width >= 1280) || !payload.viewports.some((viewport) => viewport.width <= 430)) {
    fail("manifest-invalid", "The manifest requires at least one wide and one narrow viewport.");
  }
  const routeKeys = new Set(), urls = new Set(), origins = new Set();
  const manifestPath = path.resolve(file);
  const projectRoot = path.basename(path.dirname(manifestPath)) === ".design-dna" ? path.dirname(path.dirname(manifestPath)) : path.dirname(manifestPath);
  for (const route of payload.routes) {
    if (!route || Object.keys(route).some((key) => !ROUTE_FIELDS.has(key)) || Object.keys(route).length !== ROUTE_FIELDS.size ||
        !/^[a-z][a-z0-9-]{0,47}$/.test(route.key) || routeKeys.has(route.key)) fail("manifest-invalid", "Route entries must use the exact schema-2 fields and unique lowercase keys.");
    let normalized;
    try { normalized = normalizeHttpUrl(route.url); } catch { fail("manifest-invalid", `Route ${route.key} needs an absolute http(s) URL.`); }
    if (normalized !== route.url || urls.has(normalized)) fail("manifest-invalid", "Route URLs must be canonical and unique after normalization.");
    const referenceMatch = String(route.mapped_reference_id || "").match(/^strong-([1-9][0-9]*)$/);
    if (!Number.isInteger(route.mapped_reference_rank) || route.mapped_reference_rank < 1 ||
        !referenceMatch || Number(referenceMatch[1]) !== route.mapped_reference_rank ||
        route.mapped_reference_observation !== `.design-dna/references/${route.mapped_reference_id}-observation.json` ||
        !SHA256_RE.test(route.mapped_reference_sha256 || "")) fail("manifest-invalid", `Route ${route.key} has an invalid exact reference-observation binding.`);
    if (!Array.isArray(route.states) || !route.states.length || route.states[0]?.id !== "rest" ||
        route.states[0]?.kind !== "rest" || route.states[0]?.trigger?.type !== "none" ||
        route.states[0]?.trigger?.target !== "document" || route.states[0]?.trigger?.value !== null ||
        route.states[0]?.expectation !== "initial settled route" || route.states[0]?.mapped_reference_state_id !== "rest" ||
        new Set(route.states.map((state) => state.id)).size !== route.states.length ||
        route.states.some((state) => validateManifestState(state, { requireMappedReference: true }) ||
          Object.keys(state).some((key) => !["id", "kind", "trigger", "expectation", "mapped_reference_state_id"].includes(key)) ||
          Object.keys(state.trigger || {}).some((key) => !["type", "target", "value"].includes(key)))) {
      fail("manifest-invalid", `Route ${route.key} has invalid, duplicate, or unmapped state objects.`);
    }
    const observationPath = path.resolve(projectRoot, route.mapped_reference_observation);
    if (!observationPath.startsWith(projectRoot + path.sep) || !fs.existsSync(observationPath) ||
        createHash("sha256").update(fs.readFileSync(observationPath)).digest("hex") !== route.mapped_reference_sha256) {
      fail("manifest-invalid", `Route ${route.key} observation path/hash does not bind exact bytes.`);
    }
    let observation;
    try { observation = JSON.parse(fs.readFileSync(observationPath, "utf8")); }
    catch { fail("manifest-invalid", `Route ${route.key} observation is not readable JSON.`); }
    if (observation.tool !== "observe_reference.mjs" || !Number.isInteger(observation.schema_version) || observation.schema_version < 5 ||
        observation.producer_script_sha256 !== OBSERVER_SCRIPT_SHA256 || observation.id !== route.mapped_reference_id ||
        Object.keys(observation.interaction_census_by_viewport || {}).sort().join("|") !== "narrow|wide" ||
        Object.keys(observation.rendered_qa_by_viewport || {}).sort().join("|") !== "narrow|wide" ||
        route.states.some((state) => !observation.states_by_viewport?.wide?.[state.mapped_reference_state_id] ||
          !observation.states_by_viewport?.narrow?.[state.mapped_reference_state_id])) {
      fail("manifest-invalid", `Route ${route.key} does not bind current wide+narrow source-state observation evidence.`);
    }
    Object.defineProperty(route, "__observation", { value: observation, enumerable: false });
    routeKeys.add(route.key); urls.add(normalized); origins.add(new URL(normalized).origin);
  }
  if (origins.size !== 1) fail("manifest-invalid", "Every authoritative route must share one exact build origin.");
  return payload;
}

function readVisibleDecisionManifest(manifest) {
  const file = path.resolve(path.dirname(path.resolve(manifest.__file || "")), "visible-decision-sources.json");
  let payload, bytes;
  try { bytes = fs.readFileSync(file); payload = JSON.parse(bytes.toString("utf8")); }
  catch (error) { throw new Error(`visible decision source manifest is missing or unreadable: ${String(error).slice(0, 180)}`); }
  const expected = ["created_at","decisions","completeness","planned_decision_ids","proof_build_id","record_type",
    "route_manifest","schema_version","source_observations"].sort();
  if (!payload || Object.keys(payload).sort().join("|") !== expected.join("|") || payload.schema_version !== 1 ||
      payload.record_type !== "design-dna-visible-decision-source-manifest" || !Array.isArray(payload.planned_decision_ids) ||
      !Array.isArray(payload.decisions) || new Set(payload.planned_decision_ids).size !== payload.planned_decision_ids.length ||
      payload.decisions.length !== payload.planned_decision_ids.length || payload.route_manifest?.manifest_id !== manifest.manifest_id ||
      payload.route_manifest?.path !== ".design-dna/route-manifest.json" ||
      payload.route_manifest?.sha256 !== createHash("sha256").update(fs.readFileSync(manifest.__file)).digest("hex")) {
    throw new Error("visible decision source manifest does not bind the exact route manifest and unique planned decisions");
  }
  return { file, sha256: createHash("sha256").update(bytes).digest("hex"), payload };
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

function mergeComponents(records) {
  const merged = new Map();
  for (const components of records) {
    for (const component of components) {
      const row = merged.get(component.name) || { name: component.name, count: 0, area: 0, tags: [], samples: [] };
      row.count += component.count;
      row.area = Math.max(row.area, component.area);
      for (const tag of component.tags || []) if (!row.tags.includes(tag) && row.tags.length < 8) row.tags.push(tag);
      for (const sample of component.samples || []) if (!row.samples.includes(sample) && row.samples.length < 3) row.samples.push(sample);
      merged.set(row.name, row);
    }
  }
  return [...merged.values()].sort((a, b) => b.area - a.area || a.name.localeCompare(b.name));
}

async function captureState(page, state, firstScreen = false) {
  await page.evaluate((value) => { window.__dnaFirstScreenOnly = value; }, firstScreen);
  const application = await applyManifestState(page, state);
  const snapshots = [await page.evaluate(CENSUS_SCRIPT)];
  if (firstScreen) return { attempted: 1, covered: 1, snapshots, application, scroll: { complete: true, surfaces: [] } };
  const scroll = await traverseScrollSurfaces(page, { maxTicks: 240, settleMs: 180,
    onTick: async () => snapshots.push(await page.evaluate(CENSUS_SCRIPT)) });
  return { attempted: 1, covered: scroll.complete ? 1 : 0, snapshots, application, scroll };
}

async function inferStateInventory(page, manifestStates) {
  const candidates = await page.evaluate(() => {
    window.__dnaInferredState = 0;
    const output = [];
    const roots = [document];
    for (let index = 0; index < roots.length; index += 1) {
      roots[index].querySelectorAll('*').forEach((element) => { if (element.shadowRoot) roots.push(element.shadowRoot); });
    }
    const seen = new Set();
    const visible = (element) => {
      const style = getComputedStyle(element), box = element.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && box.width > 1 && box.height > 1;
    };
    const add = (element, signal, kind, requiredTrigger, declaredStateId = null) => {
      if (!visible(element)) return;
      if (!element.dataset.dnaInferredStateKey) element.dataset.dnaInferredStateKey = String(++window.__dnaInferredState);
      const key = `${element.dataset.dnaInferredStateKey}:${signal}`;
      if (seen.has(key)) return; seen.add(key);
      output.push({ key, element_key: element.dataset.dnaInferredStateKey, signal, kind, required_trigger: requiredTrigger,
        declared_state_id: declaredStateId, tag: element.tagName.toLowerCase(),
        text: (element.getAttribute('aria-label') || element.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60) });
    };
    for (const root of roots) for (const element of root.querySelectorAll('*')) {
      const explicit = element.getAttribute('data-design-dna-state');
      if (explicit) add(element, 'explicit-state', element.getAttribute('data-design-dna-state-kind') || 'data', ['programmatic'], explicit);
      if (element.matches('[data-design-dna-state-driver]')) {
        const declared = String(element.getAttribute('data-design-dna-states') || '').split(/[\s,]+/).filter(Boolean);
        if (declared.length) declared.forEach((stateId) => add(element, 'state-driver:' + stateId,
          /loading|error|success|empty/.test(stateId) ? 'system' : 'data', ['programmatic'], stateId));
        else add(element, 'state-driver', 'data', ['programmatic']);
      }
      if (element.matches('[aria-expanded],details,[aria-haspopup],[role="tab"][aria-selected],[aria-pressed],[aria-selected]'))
        add(element, 'disclosure-selection', 'interactive', ['click','keyboard','programmatic']);
      if (element.matches(':disabled,[aria-disabled="true"],[aria-disabled="false"]'))
        add(element, 'disabled', 'interactive', ['programmatic']);
      if (element.matches('[role="dialog"],dialog')) add(element, 'dialog', 'interactive', ['click','keyboard','programmatic']);
      if (element.matches('a[href],button,input,select,textarea,summary,[tabindex]:not([tabindex="-1"])')) {
        add(element, 'focusable', 'interactive', ['focus']);
        add(element, 'hover-candidate', 'interactive', ['hover']);
      }
      if (element.matches('[aria-busy],[role="alert"],[role="status"],:invalid,[aria-invalid]'))
        add(element, 'system-or-validation', 'system', ['programmatic','input']);
    }
    return output;
  });

  // A hover state is required only where real computed appearance responds.
  for (const candidate of candidates.filter((item) => item.signal === "hover-candidate")) {
    try {
      const target = page.locator(`[data-dna-inferred-state-key="${candidate.element_key}"]`);
      const before = await target.evaluate((element) => {
        const style = getComputedStyle(element), box = element.getBoundingClientRect();
        return [style.color, style.backgroundColor, style.borderColor, style.transform, style.opacity, style.filter,
          Math.round(box.left), Math.round(box.top), Math.round(box.width), Math.round(box.height)];
      });
      await target.hover({ timeout: 3000 }); await page.waitForTimeout(180);
      const after = await target.evaluate((element) => {
        const style = getComputedStyle(element), box = element.getBoundingClientRect();
        return [style.color, style.backgroundColor, style.borderColor, style.transform, style.opacity, style.filter,
          Math.round(box.left), Math.round(box.top), Math.round(box.width), Math.round(box.height)];
      });
      candidate.actual_style_response = JSON.stringify(before) !== JSON.stringify(after);
    } catch { candidate.actual_style_response = false; }
  }
  const required = candidates.filter((item) => item.signal !== "hover-candidate" || item.actual_style_response);
  for (const candidate of required) {
    candidate.reconciled_state_ids = [];
    for (const state of manifestStates) {
      if (candidate.declared_state_id && candidate.declared_state_id === state.id) {
        candidate.reconciled_state_ids.push(state.id); continue;
      }
      if (!candidate.required_trigger.includes(state.trigger.type)) continue;
      if (["url", "none"].includes(state.trigger.type)) continue;
      try {
        const target = page.locator(state.trigger.target);
        if (await target.count() !== 1) continue;
        const key = await target.first().getAttribute("data-dna-inferred-state-key");
        if (key === candidate.element_key) candidate.reconciled_state_ids.push(state.id);
      } catch { /* invalid/unmatched selectors are rejected when applying */ }
    }
  }
  return { inferred: required, unreconciled: required.filter((item) => !item.reconciled_state_ids.length),
    complete: required.every((item) => item.reconciled_state_ids.length > 0) };
}

/** Live rendered QA for one exact route/profile/state. Source/DOM discovery
 * supplies candidates; only browser-computed geometry, focus, and animation
 * behavior can clear them. */
async function renderedQaProbe(page, state, captureEvidence) {
  await page.evaluate(() => window.scrollTo(0, 0)).catch(() => {});
  await page.waitForTimeout(120);
  const geometry = await page.evaluate((manifestState) => {
    const roots = [document];
    for (let index = 0; index < roots.length; index += 1) roots[index].querySelectorAll('*').forEach((element) => {
      if (element.shadowRoot && !roots.includes(element.shadowRoot)) roots.push(element.shadowRoot);
    });
    const elements = [...new Set(roots.flatMap((root) => [...root.querySelectorAll('*')]))];
    const controlSelector = 'a[href],button,input,select,textarea,summary,[role="button"],[role="tab"],[role="menuitem"],[role="switch"],[role="checkbox"],[role="radio"],[tabindex]';
    const textOf = (element) => (element.getAttribute('aria-label') || element.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 80);
    const keyOf = (element) => {
      const classes = String(element.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean).sort();
      const text = textOf(element);
      return element.id ? `id:${element.id}` : `${element.tagName.toLowerCase()}|${classes.join('.') || 'unclassed'}|${text}`;
    };
    const record = (element) => {
      const style = getComputedStyle(element), box = element.getBoundingClientRect();
      const visible = style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && box.width > 1 && box.height > 1;
      const tag = element.tagName.toLowerCase(), role = element.getAttribute('role') || tag, text = textOf(element);
      return { element, key: keyOf(element), semantic_key: `${role.toLowerCase()}|${text.toLowerCase()}`,
        text, role, tag, visible,
        focusable: element.matches(controlSelector) && !element.matches(':disabled') &&
          !element.closest('[inert]') && element.getAttribute('tabindex') !== '-1',
        aria_hidden: element.getAttribute('aria-hidden'),
        display: style.display, visibility: style.visibility, opacity: Number(style.opacity),
        rendered_box: box.width > 1 && box.height > 1, tab_index: element.tabIndex,
        rect: { left: box.left, right: box.right, top: box.top, bottom: box.bottom, width: box.width, height: box.height },
        position: style.position, overflow: `${style.overflow} ${style.overflowX} ${style.overflowY}` };
    };
    const controlElements = elements.filter((element) => element.matches(controlSelector));
    controlElements.forEach((element, index) => element.setAttribute('data-design-dna-qa-control', String(index + 1)));
    const controls = controlElements.map(record);
    const visibleControls = controls.filter((item) => item.visible);
    const renderedContent = elements.map(record).filter((item) => {
      if (!item.visible) return false;
      const directText = [...item.element.childNodes].some((node) => node.nodeType === 3 && String(node.nodeValue || '').trim());
      return !item.element.matches(controlSelector) &&
        (directText || ['img','video','picture','canvas','svg'].includes(item.tag));
    });
    const clipping = [];
    if (document.documentElement.scrollWidth > innerWidth + 2) clipping.push({ target: 'document', reason: 'horizontal-overflow',
      measured: document.documentElement.scrollWidth, boundary: innerWidth });
    for (const item of visibleControls) {
      for (let parent = item.element.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
        const style = getComputedStyle(parent);
        if (!/(hidden|clip)/.test(`${style.overflow} ${style.overflowX} ${style.overflowY}`)) continue;
        const boundary = parent.getBoundingClientRect(), rect = item.rect;
        if (rect.left < boundary.left - 1 || rect.right > boundary.right + 1 || rect.top < boundary.top - 1 || rect.bottom > boundary.bottom + 1) {
          clipping.push({ target: item.key, reason: 'focusable-clipped-by-overflow', parent: keyOf(parent) });
        }
      }
    }
    for (const item of renderedContent.filter((entry) => !['img','video','picture','canvas','svg'].includes(entry.tag))) {
      const element = item.element, style = getComputedStyle(element);
      const directNodes = [...element.childNodes].filter((node) => node.nodeType === 3 && String(node.nodeValue || '').trim());
      const lineRects = directNodes.flatMap((node) => { const range = document.createRange(); range.selectNodeContents(node);
        return [...range.getClientRects()].map((rect) => ({ left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom })); });
      const clippedBySelf = /(hidden|clip)/.test(`${style.overflow} ${style.overflowX} ${style.overflowY}`) &&
        (element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1);
      const horizontalEscape = lineRects.some((rect) => rect.left < -1 || rect.right > innerWidth + 1);
      let clippedByAncestor = false;
      for (let parent = element.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
        const parentStyle = getComputedStyle(parent);
        if (!/(hidden|clip)/.test(`${parentStyle.overflow} ${parentStyle.overflowX} ${parentStyle.overflowY}`)) continue;
        const boundary = parent.getBoundingClientRect();
        if (lineRects.some((rect) => rect.left < boundary.left - 1 || rect.right > boundary.right + 1 ||
          rect.top < boundary.top - 1 || rect.bottom > boundary.bottom + 1)) { clippedByAncestor = true; break; }
      }
      if (clippedBySelf || horizontalEscape || clippedByAncestor) clipping.push({ target: item.key,
        reason: clippedBySelf ? 'rendered-text-overflows-own-box' : horizontalEscape ? 'rendered-text-escapes-viewport' : 'rendered-text-clipped-by-ancestor',
        direction: style.direction, language: element.closest('[lang]')?.getAttribute('lang') || document.documentElement.lang || null,
        line_rects: lineRects });
    }
    const intersection = (a, b) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) *
      Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
    const overlaySelector = 'dialog,[role="dialog"],[aria-modal],[aria-hidden],[class*="menu-panel" i],[class*="overlay" i],[class*="drawer" i]';
    const activeOverlayFor = (element) => {
      const overlay = element.closest?.(overlaySelector);
      if (!overlay || overlay.getAttribute('aria-hidden') === 'true') return null;
      const style = getComputedStyle(overlay), box = overlay.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && box.width > 1 && box.height > 1
        ? overlay : null;
    };
    const collisions = [];
    const ordered = [...visibleControls, ...renderedContent]
      .sort((a, b) => a.rect.top - b.rect.top || a.rect.left - b.rect.left);
    for (let i = 0; i < ordered.length; i += 1) for (let j = i + 1; j < ordered.length && ordered[j].rect.top < ordered[i].rect.bottom; j += 1) {
      const a = ordered[i], b = ordered[j];
      if (a.element.contains(b.element) || b.element.contains(a.element)) continue;
      const aOverlay = activeOverlayFor(a.element), bOverlay = activeOverlayFor(b.element);
      if ((aOverlay || bOverlay) && aOverlay !== bOverlay) continue;
      const overlap = intersection(a.rect, b.rect), smaller = Math.min(a.rect.width * a.rect.height, b.rect.width * b.rect.height);
      if (overlap > 16 && overlap / Math.max(smaller, 1) >= .15) collisions.push({ first: a.key, second: b.key, overlap_ratio: +(overlap / smaller).toFixed(3) });
    }
    const rails = elements.map(record).filter((item) => item.visible && ['fixed','sticky'].includes(item.position) && item.rect.width >= innerWidth * .12);
    const fixed_rail_overlaps = [];
    for (const rail of rails) for (const target of [...visibleControls, ...renderedContent]) {
      if (rail.element === target.element || rail.element.contains(target.element) || target.element.contains(rail.element)) continue;
      if (activeOverlayFor(target.element) && !activeOverlayFor(rail.element)) continue;
      const overlap = intersection(rail.rect, target.rect), area = target.rect.width * target.rect.height;
      if (overlap / Math.max(area, 1) >= .15) fixed_rail_overlaps.push({ rail: rail.key, target: target.key,
        target_kind: visibleControls.includes(target) ? 'control' : 'content', overlap_ratio: +(overlap / area).toFixed(3) });
    }
    const overlays = elements.filter((element) =>
      element.matches(overlaySelector) &&
      element.querySelector(controlSelector)).map(record);
    overlays.forEach((item, index) => item.element.setAttribute('data-design-dna-qa-overlay', String(index + 1)));
    const overlayRows = overlays.map((item, index) => {
      const background = elements.filter((element) => !item.element.contains(element) && !element.contains(item.element) && element !== item.element);
      const backgroundControls = background.filter((element) => element.matches(controlSelector));
      backgroundControls.forEach((element, controlIndex) =>
        element.setAttribute('data-design-dna-qa-background', `${index + 1}-${controlIndex + 1}`));
      const inertBackground = backgroundControls.every((element) =>
        element.closest('[inert]') || element.matches(':disabled') || element.getAttribute('tabindex') === '-1');
      const descendants = [...item.element.querySelectorAll(controlSelector)];
      descendants.forEach((element, descendantIndex) =>
        element.setAttribute('data-design-dna-qa-descendant', `${index + 1}-${descendantIndex + 1}`));
      const closed = !item.visible || item.element.getAttribute('aria-hidden') === 'true';
      const closedDescendantsInert = !closed || descendants.every((element) =>
        element.matches(':disabled') || element.tabIndex < 0 || element.closest('[inert]'));
      const samplePoints = [
        [.5, .5], [.1, .08], [.5, .08], [.9, .08], [.1, .5], [.9, .5], [.1, .92], [.5, .92], [.9, .92],
      ].map(([x, y]) => ({ x: Math.max(0, Math.min(innerWidth - 1, item.rect.left + item.rect.width * x)),
        y: Math.max(0, Math.min(innerHeight - 1, item.rect.top + item.rect.height * y)) }));
      const hitTests = closed ? [] : samplePoints.map((point) => {
        const stack = document.elementsFromPoint(point.x, point.y);
        const overlayIndex = stack.findIndex((element) => element === item.element || item.element.contains(element));
        const backgroundControlAbove = overlayIndex < 0 || stack.slice(0, overlayIndex).some((element) =>
          element.matches?.(controlSelector) && !item.element.contains(element));
        return { ...point, top: stack[0] ? keyOf(stack[0]) : null, overlay_hit: overlayIndex >= 0, background_control_above: backgroundControlAbove };
      });
      const backgroundControlAbove = hitTests.some((test) => test.background_control_above);
      return { key: item.key, selector: `[data-design-dna-qa-overlay="${index + 1}"]`, open: !closed,
        inert_background: closed ? true : inertBackground, closed_descendants_inert: closedDescendantsInert,
        stacking_above_background_controls: closed ? true : !backgroundControlAbove,
        initial_focus: closed ? true : item.element.contains(item.element.ownerDocument.activeElement),
        background_control_selectors: backgroundControls.map((_element, controlIndex) =>
          `[data-design-dna-qa-background="${index + 1}-${controlIndex + 1}"]`),
        descendant_selectors: descendants.map((_element, descendantIndex) =>
          `[data-design-dna-qa-descendant="${index + 1}-${descendantIndex + 1}"]`),
        hit_tests: hitTests };
    });
    let stateSemantics = { required: false, complete: true, target: null, attributes: null };
    if (manifestState?.trigger && ['click','keyboard','programmatic'].includes(manifestState.trigger.type)) {
      let targets = [];
      try { targets = roots.flatMap((root) => [...root.querySelectorAll(manifestState.trigger.target)]); } catch { targets = []; }
      if (targets.length === 1) {
        const target = targets[0], controlledId = target.getAttribute('aria-controls');
        const controlled = controlledId ? document.getElementById(controlledId) : null;
        const attributes = { aria_expanded: target.getAttribute('aria-expanded'), aria_pressed: target.getAttribute('aria-pressed'),
          aria_selected: target.getAttribute('aria-selected'), aria_checked: target.getAttribute('aria-checked'), aria_controls: controlledId };
        const role = target.getAttribute('role');
        const requires = Boolean(controlled || target.closest('details') ||
          ['tab','switch','checkbox','radio'].includes(role) ||
          attributes.aria_expanded !== null || attributes.aria_pressed !== null ||
          attributes.aria_selected !== null || attributes.aria_checked !== null);
        const semanticValuePresent = [attributes.aria_expanded, attributes.aria_pressed,
          attributes.aria_selected, attributes.aria_checked].some((value) => value !== null);
        const controlledVisible = controlled ? (() => { const style = getComputedStyle(controlled), box = controlled.getBoundingClientRect();
          return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && box.width > 1 && box.height > 1; })() : null;
        const controlledMatches = !controlled || attributes.aria_expanded === String(controlledVisible);
        stateSemantics = { required: requires, complete: !requires || (semanticValuePresent && controlledMatches),
          target: keyOf(target), attributes };
      } else stateSemantics = { required: true, complete: false, target: manifestState.trigger.target, attributes: null };
    }
    const visibleText = [];
    const copyRoots = [...roots];
    for (const frame of document.querySelectorAll('iframe')) {
      try { if (frame.contentDocument) copyRoots.push(frame.contentDocument); }
      catch { /* cross-origin frames are rejected by the DOM inspection ledger */ }
    }
    for (const root of copyRoots) {
      const container = root.body || root;
      const rootDocument = container.ownerDocument || document;
      const walker = rootDocument.createTreeWalker(container, rootDocument.defaultView.NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const parent = node.parentElement;
        if (!parent) continue;
        const style = rootDocument.defaultView.getComputedStyle(parent), box = parent.getBoundingClientRect();
        const text = String(node.nodeValue || '').replace(/\s+/g, ' ').trim();
        if (!text || style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) <= 0 || box.width <= 1 || box.height <= 1) continue;
        visibleText.push({ parent: keyOf(parent), text });
      }
    }
    const blockingPatterns = [
      ['scaffold-placeholder', /__REPLACE(?:_WITH)?|\blorem ipsum\b|\b(?:TODO|TBD)\b|\breplace with\b|\brecorded evidence for\b|\bplaceholder(?: copy| text)?\b/i],
      ['prototype-fallback', /\b(?:local )?(?:concept|demo|prototype) preview\b|\bthis preview\b|\bwould (?:ask|show|connect|send|collect)\b|\bbefore (?:it|this) is connected\b|\bnot (?:yet )?(?:connected|available|functional|implemented)\b/i],
      ['builder-narration', /\b(?:this|the) (?:section|layout|component|page) (?:uses|shows|demonstrates|is designed|was built)\b|\b(?:built|implemented|designed) (?:with|using)\b/i],
    ];
    const copyFindings = visibleText.flatMap((entry) => blockingPatterns
      .filter(([, pattern]) => pattern.test(entry.text))
      .map(([kind]) => ({ kind, parent: entry.parent, text: entry.text })));
    const contextualReview = visibleText.filter((entry) =>
      /\b(?:layout|component|design system|responsive|breakpoint|animation)\b/i.test(entry.text) &&
      !copyFindings.some((finding) => finding.parent === entry.parent && finding.text === entry.text));
    const headings = elements.filter((element) => /^H[1-6]$/.test(element.tagName) && record(element).visible)
      .map((element) => ({ key: keyOf(element), level: Number(element.tagName.slice(1)), text: textOf(element) }));
    const landmarks = elements.filter((element) => element.matches('main,nav,header,footer,aside,[role="main"],[role="navigation"],[role="banner"],[role="contentinfo"],[role="complementary"]'))
      .map((element) => ({ key: keyOf(element), tag: element.tagName.toLowerCase(), role: element.getAttribute('role'),
        label: element.getAttribute('aria-label') || element.getAttribute('aria-labelledby'), visible: record(element).visible }));
    const semanticMissing = [];
    if (!headings.some((heading) => heading.level === 1)) semanticMissing.push('visible-h1-missing');
    if (landmarks.filter((landmark) => landmark.visible && (landmark.tag === 'main' || landmark.role === 'main')).length !== 1)
      semanticMissing.push('exactly-one-visible-main-required');
    if (landmarks.some((landmark) => landmark.visible && (landmark.tag === 'nav' || landmark.role === 'navigation') && !landmark.label))
      semanticMissing.push('navigation-landmark-name-missing');
    return {
      clipping, collisions, fixed_rail_overlaps,
      control_visibility: controls.map(({ key, semantic_key: semanticKey, text, role, visible, focusable, aria_hidden: ariaHidden, tag, display, visibility, opacity, rendered_box: renderedBox, tab_index: tabIndex }) =>
        ({ key, semantic_key: semanticKey, text, role, visible, focusable, aria_hidden: ariaHidden, tag, display, visibility, opacity, rendered_box: renderedBox, tab_index: tabIndex })),
      overlays: overlayRows,
      state_semantics: stateSemantics,
      public_copy: { visible_text: visibleText, findings: copyFindings,
        contextual_review: contextualReview, truncated: false, complete: copyFindings.length === 0 },
      accessibility_semantics: { headings, landmarks, missing: semanticMissing,
        complete: semanticMissing.length === 0 },
      focus_targets: controls.map((item, index) => ({ key: item.key,
        selector: `[data-design-dna-qa-control="${index + 1}"]`, visible: item.visible, focusable: item.focusable })),
      viewport: { width: innerWidth, height: innerHeight },
      truncated: false,
    };
  }, state);
  geometry.public_copy.evidence = await captureEvidence('public-copy');
  const focusIndicators = [];
  for (const target of geometry.focus_targets.filter((item) => item.visible && item.focusable)) {
    const locator = page.locator(target.selector);
    const sample = () => locator.evaluate((element) => { const style = getComputedStyle(element);
      return { outline_style: style.outlineStyle, outline_width: style.outlineWidth, outline_color: style.outlineColor,
        box_shadow: style.boxShadow, border_color: style.borderColor, background_color: style.backgroundColor,
        color: style.color }; });
    const beforeFrame = await captureEvidence(`focus-${target.key}-before`);
    const before = await sample().catch(() => null);
    await locator.focus().catch(() => {});
    await page.waitForTimeout(80);
    const after = await sample().catch(() => null);
    const active = await locator.evaluate((element) => element === element.ownerDocument.activeElement ||
      element.contains(element.ownerDocument.activeElement)).catch(() => false);
    const focusStyleChanged = Boolean(before && after && JSON.stringify(before) !== JSON.stringify(after));
    const visibleIndicator = Boolean(active && focusStyleChanged && after &&
      (parseFloat(after.outline_width) >= 1 && after.outline_style !== 'none' ||
        after.box_shadow !== before.box_shadow || after.border_color !== before.border_color ||
        after.background_color !== before.background_color || after.color !== before.color));
    const afterFrame = await captureEvidence(`focus-${target.key}-after`);
    focusIndicators.push({ target: target.key, active, visible_indicator: visibleIndicator,
      before, after, evidence: { before: beforeFrame, after: afterFrame }, complete: active && visibleIndicator });
    await locator.evaluate((element) => element.blur()).catch(() => {});
  }
  const focusMissing = focusIndicators.filter((item) => !item.complete).map((item) => item.target);
  geometry.accessibility = { headings: geometry.accessibility_semantics.headings,
    landmarks: geometry.accessibility_semantics.landmarks, focus_indicators: focusIndicators,
    missing: [...geometry.accessibility_semantics.missing, ...focusMissing.map((target) => `visible-focus:${target}`)],
    truncated: false, complete: geometry.accessibility_semantics.complete && focusMissing.length === 0 };
  delete geometry.accessibility_semantics;
  delete geometry.focus_targets;
  const overlayEvidence = [];
  for (const overlay of geometry.overlays) {
    const locator = page.locator(overlay.selector);
    const before = await captureEvidence(`overlay-${overlay.key}-before`);
    if (!overlay.open) {
      let closedFocusBlocked = true;
      for (const selector of overlay.descendant_selectors) {
        const descendant = page.locator(selector);
        await descendant.evaluate((element) => element.focus()).catch(() => {});
        const capturedFocus = await descendant.evaluate((element) => element === element.ownerDocument.activeElement ||
          element.contains(element.ownerDocument.activeElement)).catch(() => false);
        if (capturedFocus) closedFocusBlocked = false;
      }
      const after = await captureEvidence(`overlay-${overlay.key}-closed-after`);
      overlayEvidence.push({ ...overlay, closed_descendants_inert: overlay.closed_descendants_inert && closedFocusBlocked,
        initial_focus: true, background_focus_blocked: true, focusable_count: 0,
        focus_trap: true, focus_return: true, escape_closes: true, evidence: { before, after, settled: after } });
      continue;
    }
    const focusable = locator.locator('a[href],button,input,select,textarea,summary,[tabindex]:not([tabindex="-1"])');
    const focusableCount = await focusable.count();
    const initialFocus = overlay.initial_focus;
    let backgroundFocusBlocked = true;
    for (const selector of overlay.background_control_selectors) {
      const background = page.locator(selector);
      await background.evaluate((element) => element.focus()).catch(() => {});
      const capturedFocus = await background.evaluate((element) => element === element.ownerDocument.activeElement ||
        element.contains(element.ownerDocument.activeElement)).catch(() => false);
      if (capturedFocus) backgroundFocusBlocked = false;
    }
    let focusTrap = focusableCount > 0;
    if (focusableCount > 0) {
      await focusable.first().focus().catch(() => {});
      for (let index = 0; index <= focusableCount; index += 1) {
        await page.keyboard.press('Tab');
        if (!(await locator.evaluate((element) => element.contains(element.ownerDocument.activeElement)).catch(() => false))) focusTrap = false;
      }
    }
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(160);
    const remainsVisible = await locator.isVisible().catch(() => false);
    const focusReturn = !remainsVisible && state.trigger.type !== 'none'
      ? await page.locator(state.trigger.target).evaluateAll((targets) => targets.length === 1 &&
          (targets[0] === targets[0].ownerDocument.activeElement || targets[0].contains(targets[0].ownerDocument.activeElement))).catch(() => false)
      : !remainsVisible;
    const after = await captureEvidence(`overlay-${overlay.key}-after`);
    overlayEvidence.push({ ...overlay, initial_focus: initialFocus, background_focus_blocked: backgroundFocusBlocked,
      focusable_count: focusableCount, focus_trap: focusTrap,
      focus_return: focusReturn, escape_closes: !remainsVisible, evidence: { before, after } });
  }
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.waitForTimeout(250);
  const reducedMotion = await page.evaluate(() => {
    const active = document.getAnimations().filter((animation) => animation.playState === 'running').map((animation) => {
      const timing = animation.effect?.getComputedTiming?.() || {};
      return { end_time: Number(timing.endTime), iterations: Number(timing.iterations), current_time: Number(animation.currentTime || 0) };
    });
    const violations = active.filter((animation) => !Number.isFinite(animation.iterations) || animation.iterations > 1 || animation.end_time - animation.current_time > 500);
    return { active_animations: active, violations, complete: violations.length === 0 };
  });
  reducedMotion.evidence = await captureEvidence('reduced-motion');
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  const overlayFailures = overlayEvidence.filter((item) => !item.inert_background || !item.closed_descendants_inert ||
    !item.stacking_above_background_controls || !item.initial_focus || !item.background_focus_blocked ||
    !item.focus_trap || !item.focus_return || !item.escape_closes);
  return { ...geometry, overlays: { records: overlayEvidence, inert_background: overlayFailures.length === 0,
    closed_descendants_inert: overlayEvidence.every((item) => item.closed_descendants_inert),
    stacking: overlayEvidence.every((item) => item.stacking_above_background_controls),
    initial_focus: overlayEvidence.every((item) => item.initial_focus),
    background_focus_blocked: overlayEvidence.every((item) => item.background_focus_blocked),
    focus_trap: overlayFailures.length === 0, focus_return: overlayFailures.length === 0 },
    state_semantics: geometry.state_semantics, reduced_motion: reducedMotion };
}

export async function scanBuild({ manifest, buildId, runId, routeKeys = [], firstScreen = false, browserExecutable, outFile = null }) {
  const visibleDecisionManifest = readVisibleDecisionManifest(manifest);
  const loaded = loadPlaywright();
  const browserDependency = loadBrowserDependency(loaded, browserExecutable);
  const browser = await loaded.playwright.chromium.launch({ executablePath: browserDependency.file });
  const checks = [];
  const servedProbes = [];
  const navigations = [];
  const stateInventories = [];
  const interactionCensuses = [];
  let interactionFrameSequence = 0;
  const interactionFrameDir = outFile ? path.resolve(`${outFile.replace(/\.json$/i, "")}-interaction-frames`) : null;
  const interactionFrameRelativeRoot = interactionFrameDir && outFile
    ? path.relative(path.dirname(path.resolve(outFile)), interactionFrameDir).split(path.sep).join("/") : null;
  if (interactionFrameDir) await mkdir(interactionFrameDir, { recursive: true });
  const persistFrame = async (routeKey, viewportName, label, evidencePage) => {
    const bytes = await evidencePage.screenshot();
    interactionFrameSequence += 1;
    const safe = `${routeKey}-${viewportName}-${String(interactionFrameSequence).padStart(6, "0")}-${label}`
      .toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "");
    const record = { label, scope: "viewport", bytes: bytes.length, sha256: sha256(bytes) };
    if (interactionFrameDir && interactionFrameRelativeRoot) {
      const name = `${safe}.png`;
      await writeFile(path.join(interactionFrameDir, name), bytes);
      record.file = `${interactionFrameRelativeRoot}/${name}`;
    }
    return record;
  };
  try {
    for (const viewport of manifest.viewports) {
      const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
      await installDomInspection(context);
      const selectedRoutes = routeKeys.length ? manifest.routes.filter((route) => routeKeys.includes(route.key)) : manifest.routes;
      for (const route of selectedRoutes) {
        const page = await context.newPage();
        // Two byte-identical loads are required before the DOM census. A
        // transient/error response or a build that changes what it serves
        // between reloads cannot establish an immutable build identity.
        for (let reload = 1; reload <= 2; reload += 1) {
          const capture = beginServedContentCapture(page, route.url);
          const navigation = await navigateExact(page, route.url);
          capture.setFinalResponse(navigation);
          await page.evaluate(() => document.fonts?.ready).catch(() => {});
          await page.waitForTimeout(500);
          servedProbes.push(await capture.finish({ route_key: route.key, viewport: viewport.name }));
          navigations.push({ route_key: route.key, viewport: viewport.name, state_id: "rest", reload, ...navigation });
        }
        await page.evaluate(() => document.fonts?.ready).catch(() => {});
        await page.waitForTimeout(500);
        // Rendering and incremental live scrolling remain the authority. This
        // activates lazy targets before the DOM/code inventory is reconciled;
        // source markup alone never certifies an interaction.
        const discoveryScroll = firstScreen ? { complete: true, surfaces: [] } :
          await traverseScrollSurfaces(page, { maxTicks: 240, settleMs: 180 });
        const targetCensus = await captureInteractionCensus(page, {
          profile: viewport.name,
          pageUrl: route.url,
          authoredStates: route.states.map((state) => ({ ...state, url: route.url })),
          captureEvidence: (label, evidencePage = page) => persistFrame(route.key, viewport.name, label, evidencePage),
        });
        interactionCensuses.push({ route_key: route.key, viewport: viewport.name, ...targetCensus });
        const stateInventory = await inferStateInventory(page, route.states);
        stateInventories.push({ route_key: route.key, viewport: viewport.name,
          discovery_scroll: discoveryScroll, ...stateInventory });
        const cleanNavigation = await navigateExact(page, route.url);
        navigations.push({ route_key: route.key, viewport: viewport.name, state_id: "rest", clean_after_inference: true, ...cleanNavigation });
        const orderedStates = [...route.states].sort((a, b) => Number(b.id === "rest") - Number(a.id === "rest"));
        for (const state of orderedStates) {
          if (state.id !== "rest") {
            const navigation = await navigateExact(page, route.url);
            navigations.push({ route_key: route.key, viewport: viewport.name, state_id: state.id, reload: 1, ...navigation });
            await page.waitForTimeout(300);
          }
          const result = await captureState(page, state, firstScreen);
          if (result.application?.navigation) navigations.push({ route_key: route.key, viewport: viewport.name,
            state_id: state.id, trigger_navigation: true, ...result.application.navigation });
          const snapshots = result.snapshots || [];
          const renderedQa = await renderedQaProbe(
            page,
            state,
            (label, evidencePage = page) => persistFrame(route.key, viewport.name, `${state.id}-${label}`, evidencePage),
          );
          const shortHeight = Math.min(viewport.height, 568);
          await page.setViewportSize({ width: viewport.width, height: shortHeight });
          const shortNavigation = await navigateExact(page, route.url);
          navigations.push({ route_key: route.key, viewport: `${viewport.name}-short`, state_id: state.id,
            derived_short_height: true, ...shortNavigation });
          await page.evaluate(() => document.fonts?.ready).catch(() => {});
          await page.waitForTimeout(180);
          await applyManifestState(page, state);
          const shortHeightQa = await renderedQaProbe(
            page,
            state,
            (label, evidencePage = page) => persistFrame(route.key, `${viewport.name}-short`, `${state.id}-${label}`, evidencePage),
          );
          await page.setViewportSize({ width: viewport.width, height: viewport.height });
          renderedQa.short_height = { profile: `${viewport.name}-short`, width: viewport.width, height: shortHeight, ...shortHeightQa };
          const scope = snapshots[0]?.implementation_scope || null;
          const firstScreenScopePassed = !firstScreen || firstScreenScopePass(scope);
          checks.push({
            route_key: route.key, url: route.url, mapped_reference_rank: route.mapped_reference_rank,
            mapped_reference_id: route.mapped_reference_id,
            mapped_reference_observation: route.mapped_reference_observation,
            mapped_reference_sha256: route.mapped_reference_sha256,
            viewport: viewport.name, width: viewport.width, height: viewport.height,
            state_id: state.id, state_kind: state.kind, state_trigger: state.trigger,
            mapped_reference_state_id: state.mapped_reference_state_id,
            attempted: result.attempted, covered: result.covered,
            state_application: result.application,
            scroll_traversal: result.scroll,
            components: mergeComponents(snapshots.map((item) => item.components)),
            visible_decision_ids: [...new Set(snapshots.flatMap((item) => item.visible_decision_ids || []))].sort(),
            unsourced_visible_parts: [...new Set(snapshots.flatMap((item) => item.unsourced_visible_parts || []))].sort(),
            links: [...new Set(snapshots.flatMap((item) => item.links || []))].sort(),
            inspection: snapshots.map((item) => item.inspection || null),
            implementation_scope: scope,
            first_screen_scope_pass: firstScreenScopePassed,
            rendered_qa: renderedQa,
            pass: discoveryScroll.complete && stateInventory.complete && result.attempted > 0 && result.covered === result.attempted &&
              firstScreenScopePassed && snapshots.every((item) => item.inspection?.complete !== false) &&
              renderedQa.clipping.length === 0 && renderedQa.collisions.length === 0 &&
              renderedQa.fixed_rail_overlaps.length === 0 && renderedQa.reduced_motion.complete === true &&
              renderedQa.overlays.inert_background === true && renderedQa.overlays.closed_descendants_inert === true &&
              renderedQa.overlays.stacking === true && renderedQa.overlays.initial_focus === true &&
              renderedQa.overlays.background_focus_blocked === true &&
              renderedQa.overlays.focus_trap === true && renderedQa.overlays.focus_return === true &&
              renderedQa.state_semantics.complete === true && renderedQa.public_copy.complete === true &&
              renderedQa.accessibility.complete === true &&
              shortHeightQa.clipping.length === 0 && shortHeightQa.collisions.length === 0 && shortHeightQa.fixed_rail_overlaps.length === 0 &&
              shortHeightQa.reduced_motion.complete === true && shortHeightQa.overlays.inert_background === true &&
              shortHeightQa.overlays.closed_descendants_inert === true && shortHeightQa.overlays.stacking === true &&
              shortHeightQa.overlays.initial_focus === true && shortHeightQa.overlays.focus_trap === true &&
              shortHeightQa.overlays.background_focus_blocked === true &&
              shortHeightQa.overlays.focus_return === true &&
              shortHeightQa.state_semantics.complete === true && shortHeightQa.public_copy.complete === true &&
              shortHeightQa.accessibility.complete === true,
          });
        }
        await page.close();
      }
      await context.close();
    }
  } finally {
    await browser.close();
  }

  const servedContent = aggregateServedContent(servedProbes);
  const expected = new Set(manifest.routes.map((route) => normalizeHttpUrl(route.url)));
  const origin = new URL(manifest.routes[0].url).origin;
  const discovered = new Set();
  for (const check of checks) for (const value of check.links) {
    const url = new URL(value); url.hash = "";
    if (url.origin === origin) discovered.add(url.href);
  }
  const unexpected = [...discovered].filter((url) => !expected.has(url)).sort();
  let failedStates = checks.filter((check) => !check.pass).map((check) => `${check.route_key}/${check.viewport}/${check.state_id}`);
  const selectedRoutes = routeKeys.length ? manifest.routes.filter((route) => routeKeys.includes(route.key)) : manifest.routes;
  const routeComponents = selectedRoutes.map((route) => {
    const relevant = checks.filter((check) => check.route_key === route.key);
    return { key: route.key, url: route.url, mapped_reference_rank: route.mapped_reference_rank,
      mapped_reference_id: route.mapped_reference_id, mapped_reference_observation: route.mapped_reference_observation,
      mapped_reference_sha256: route.mapped_reference_sha256,
      components: mergeComponents(relevant.map((check) => check.components)) };
  });
  const implementationScope = selectedRoutes.flatMap((route) => manifest.viewports.map((viewport) => {
    const rest = checks.find((check) => check.route_key === route.key && check.viewport === viewport.name && check.state_id === "rest");
    return { route_key: route.key, viewport: viewport.name, ...(rest?.implementation_scope || {}),
      first_screen_scope_pass: rest?.first_screen_scope_pass ?? false };
  }));
  const census = mergeComponents(routeComponents.map((route) => route.components)).map((component) => ({
    ...component,
    routes: routeComponents.filter((route) => route.components.some((item) => item.name === component.name)).map((route) => route.key),
  }));
  const interactionCells = checks.map((check) => {
    const evidence = check.state_application?.trigger_evidence || null;
    const targetComponents = [...new Set(evidence?.target_component_keys || [])].sort();
    const routeComponentNames = new Set(
      routeComponents.find((route) => route.key === check.route_key)?.components.map((item) => item.name) || []
    );
    const targetComponentsPresent = targetComponents.every((target) =>
      routeComponentNames.has(target) || [...routeComponentNames].some((name) => name.endsWith(`|${target}`))
    );
    const hashesComplete = ["before_sha256", "after_sha256", "settled_sha256"]
      .every((field) => /^[0-9a-f]{64}$/.test(evidence?.[field] || ""));
    const changes = Array.isArray(evidence?.changed_properties) ? evidence.changed_properties : [];
    const behaviorObserved = check.state_id === "rest"
      ? evidence?.type === "none" && changes.length === 0 && evidence?.before_sha256 === evidence?.settled_sha256
      : evidence?.type === check.state_trigger?.type &&
        (changes.length > 0 || evidence?.before_sha256 !== evidence?.settled_sha256 || check.state_application?.navigation);
    const complete = Boolean(evidence && hashesComplete && evidence.settled === true && targetComponents.length &&
      targetComponentsPresent && behaviorObserved);
    return {
      route_key: check.route_key,
      viewport: check.viewport,
      state_id: check.state_id,
      mapped_reference_state_id: check.mapped_reference_state_id,
      source_mapping: {
        rank: check.mapped_reference_rank,
        id: check.mapped_reference_id,
        observation: check.mapped_reference_observation,
        sha256: check.mapped_reference_sha256,
        state_id: check.mapped_reference_state_id,
      },
      trigger: check.state_trigger,
      target_components: targetComponents,
      target_components_present: targetComponentsPresent,
      trigger_evidence: evidence,
      trigger_navigation: check.state_application?.navigation || null,
      complete,
    };
  });
  const interactionMissing = interactionCells.filter((cell) => !cell.complete)
    .map((cell) => `${cell.route_key}/${cell.viewport}/${cell.state_id}`);
  const responsiveTransformations = selectedRoutes.flatMap((route) => route.states.map((state) => {
    const cells = interactionCells.filter((cell) => cell.route_key === route.key && cell.state_id === state.id);
    const wide = cells.find((cell) => manifest.viewports.find((viewport) => viewport.name === cell.viewport)?.width >= 1280) || null;
    const narrow = cells.find((cell) => manifest.viewports.find((viewport) => viewport.name === cell.viewport)?.width <= 430) || null;
    return {
      route_key: route.key,
      state_id: state.id,
      mapped_reference_state_id: state.mapped_reference_state_id,
      wide: wide ? { viewport: wide.viewport, trigger_evidence: wide.trigger_evidence } : null,
      narrow: narrow ? { viewport: narrow.viewport, trigger_evidence: narrow.trigger_evidence } : null,
      complete: Boolean(wide?.complete && narrow?.complete),
    };
  }));
  const interactionInventory = {
    complete: interactionMissing.length === 0 && responsiveTransformations.every((item) => item.complete) &&
      stateInventories.every((item) => item.complete) && interactionCensuses.every((item) => item.complete && item.truncated === false),
    missing: [...interactionMissing, ...interactionCensuses.flatMap((item) =>
      (item.missing || []).map((missing) => `${item.route_key}/${item.viewport}/${missing.target_id || "page"}/${missing.input_kind}`))],
    cells: interactionCells,
    responsive_transformations: responsiveTransformations,
    inferred_components: stateInventories,
    target_censuses: interactionCensuses,
  };
  const visibleControlsByProfile = new Map();
  const visibleSemanticsByProfile = new Map();
  const controlRecordsByRouteState = new Map();
  for (const check of checks) {
    const key = `${check.route_key}|${check.viewport}|${check.state_id}`;
    const routeStateKey = `${check.route_key}|${check.state_id}`;
    if (!visibleControlsByProfile.has(key)) visibleControlsByProfile.set(key, new Set());
    if (!visibleSemanticsByProfile.has(key)) visibleSemanticsByProfile.set(key, new Set());
    if (!controlRecordsByRouteState.has(routeStateKey)) controlRecordsByRouteState.set(routeStateKey, new Map());
    for (const control of check.rendered_qa?.control_visibility || []) {
      if (control.visible) {
        visibleControlsByProfile.get(key).add(control.key);
        visibleSemanticsByProfile.get(key).add(control.semantic_key);
      }
      const routeRecords = controlRecordsByRouteState.get(routeStateKey);
      const existing = routeRecords.get(control.key);
      if (!existing || control.visible) routeRecords.set(control.key, control);
    }
  }
  const targetQaByProfile = new Map();
  const experiencePaths = [];
  for (const censusRecord of interactionCensuses) {
    const deadControls = [], keyboardMissing = [], semanticMismatches = [], unresolvedBlocked = [];
    for (const pageRecord of censusRecord.pages || []) for (const target of pageRecord.targets || []) {
      const inputs = target.inputs || [];
      const activationKinds = target.kind === "route-link" ? new Set(["navigation"]) :
        target.kind === "open-close" ? new Set(["open-close", "click", "keyboard"]) :
          target.kind === "media" ? new Set(["media-play-pause"]) :
            target.kind === "input-control" ? new Set(["input"]) : new Set(["click"]);
      const activation = inputs.filter((input) => activationKinds.has(input.input_kind));
      const safelyExercised = activation.filter((input) => input.status === "exercised");
      const safelyBlocked = activation.some((input) => input.status === "blocked" && input.disposition === "blocked-requires-safe-owner-handoff");
      const route = manifest.routes.find((item) => item.key === censusRecord.route_key);
      const manifestedStateIds = new Set((route?.states || []).map((item) => item.id));
      const hasEffect = safelyExercised.some((input) => (input.change_classification?.structural_semantic || []).length > 0 ||
        input.evidence?.navigation || /^exact 2xx route arrival/.test(input.behavior || "") ||
        (input.source_state_id && manifestedStateIds.has(input.source_state_id)));
      if ((!safelyExercised.length && !safelyBlocked) || (safelyExercised.length && !hasEffect)) {
        deadControls.push({ target_id: target.target_id, kind: target.kind, reason: safelyExercised.length ? "activation-produced-no-semantic-or-visible-result" : "activation-not-exercised" });
      }
      const manifestedUrls = new Set(manifest.routes.map((item) => normalizeHttpUrl(item.url)));
      const actions = activation.map((input) => {
        const finalUrl = input.evidence?.navigation?.final_normalized_url || null;
        const stateId = input.source_state_id || null;
        let resolution = null;
        if (input.status === "blocked" && input.disposition === "blocked-requires-safe-owner-handoff") resolution = "blocked-handoff";
        else if (input.status === "exercised" && finalUrl && manifestedUrls.has(normalizeHttpUrl(finalUrl))) resolution = "manifested-route";
        else if (input.status === "exercised" && stateId && manifestedStateIds.has(stateId)) resolution = "manifested-state";
        return { input_kind: input.input_kind, status: input.status, resolution,
          manifested_state_id: stateId, final_url: finalUrl, evidence: input.evidence || null };
      });
      const pathComplete = actions.length > 0 && actions.some((action) => action.resolution !== null);
      experiencePaths.push({ route_key: censusRecord.route_key, viewport: censusRecord.viewport,
        target_id: target.target_id, kind: target.kind, actions,
        missing: pathComplete ? [] : ["primary action has no manifested route/state or explicit blocked handoff"], complete: pathComplete });
      if (inputs.some((input) => input.input_kind === "focus") &&
          (!inputs.some((input) => input.input_kind === "focus" && input.status === "exercised") ||
           !inputs.some((input) => input.input_kind === "keyboard" && input.status === "exercised"))) {
        keyboardMissing.push({ target_id: target.target_id, reason: "focus-or-keyboard-path-not-exercised" });
      }
      for (const input of inputs.filter((item) => item.status === "blocked")) {
        if (input.disposition !== "blocked-requires-safe-owner-handoff") {
          unresolvedBlocked.push({ target_id: target.target_id, input_kind: input.input_kind,
            reason: input.disposition || "blocked-without-current-safe-evidence" });
        }
      }
    }
    for (const group of censusRecord.repeat_classes || []) if (group.equivalent !== true) {
      semanticMismatches.push({ repeat_class: group.repeat_class, reason: "repeated-controls-have-non-equivalent-behavior" });
    }
    targetQaByProfile.set(`${censusRecord.route_key}|${censusRecord.viewport}`, {
      dead_controls: deadControls,
      blocked_handoffs: unresolvedBlocked,
      keyboard: { complete: keyboardMissing.length === 0, missing: keyboardMissing },
      semantic_equivalence: { complete: semanticMismatches.length === 0, mismatches: semanticMismatches },
    });
  }
  const renderedQaCells = checks.map((check) => {
    const profileKey = `${check.route_key}|${check.viewport}|${check.state_id}`;
    const targetProfileKey = `${check.route_key}|${check.viewport}`;
    const routeStateKey = `${check.route_key}|${check.state_id}`;
    const visibleKeys = visibleControlsByProfile.get(profileKey) || new Set();
    const visibleSemantics = visibleSemanticsByProfile.get(profileKey) || new Set();
    const currentControls = check.rendered_qa?.control_visibility || [];
    const currentByKey = new Map(currentControls.map((control) => [control.key, control]));
    const crossProfileHidden = [];
    for (const control of controlRecordsByRouteState.get(routeStateKey)?.values() || []) {
      const current = currentByKey.get(control.key);
      const visibleHere = visibleKeys.has(control.key);
      const equivalentHere = visibleSemantics.has(control.semantic_key);
      if (!visibleHere && !equivalentHere) {
        crossProfileHidden.push({ target: control.key, semantic_key: control.semantic_key,
          reason: current ? "control-hidden-in-every-declared-state-for-required-profile" : "control-absent-without-responsive-equivalent" });
      }
    }
    const route = manifest.routes.find((item) => item.key === check.route_key);
    const viewportWidth = manifest.viewports.find((item) => item.name === check.viewport)?.width || check.width;
    const sourceProfile = viewportWidth <= 430 ? "narrow" : "wide";
    const oppositeProfile = sourceProfile === "narrow" ? "wide" : "narrow";
    const sourceCensuses = route?.__observation?.interaction_census_by_viewport || {};
    const responsiveControlParityRecord = responsiveControlParity(
      crossProfileHidden,
      [...visibleSemantics],
      sourceCensuses[sourceProfile],
      sourceCensuses[oppositeProfile],
      check.mapped_reference_state_id,
      sourceProfile,
    );
    const hiddenControls = [...responsiveControlParityRecord.findings];
    for (const control of currentControls) if (!control.visible && control.focusable && control.aria_hidden !== "true" &&
      control.rendered_box && control.tab_index >= 0 && !hiddenControls.some((item) => item.target === control.key)) {
      hiddenControls.push({ target: control.key, semantic_key: control.semantic_key,
        reason: "focusable-control-is-visually-hidden" });
    }
    const targetQa = targetQaByProfile.get(targetProfileKey) || {
      dead_controls: [{ target_id: null, reason: "target-census-missing" }],
      blocked_handoffs: [{ target_id: null, reason: "target-census-missing" }],
      keyboard: { complete: false, missing: [{ target_id: null, reason: "target-census-missing" }] },
      semantic_equivalence: { complete: false, mismatches: [{ repeat_class: null, reason: "target-census-missing" }] },
    };
    const navigationRows = navigations.filter((item) => item.route_key === check.route_key && item.viewport === check.viewport && item.state_id === "rest" && Number.isInteger(item.reload));
    const deepLink = { complete: navigationRows.some((item) => item.final_status >= 200 && item.final_status <= 299 && item.final_normalized_url === route?.url),
      requested_url: route?.url || null, final_urls: [...new Set(navigationRows.map((item) => item.final_normalized_url))].sort() };
    const reloadKey = `${check.route_key}/${check.viewport}`;
    const reload = { complete: Number(servedContent.reload_counts?.[reloadKey] || 0) >= 2 &&
      !(servedContent.inconsistent_reloads || []).some((item) => item.key === reloadKey),
      count: Number(servedContent.reload_counts?.[reloadKey] || 0), served_content_sha256: servedContent.sha256 };
    const routeLinks = [...new Set(checks.filter((item) => item.route_key === check.route_key).flatMap((item) => item.links || []))];
    const otherManifestUrls = new Set(manifest.routes.filter((item) => item.key !== check.route_key).map((item) => normalizeHttpUrl(item.url)));
    const deadEnds = !firstScreen && manifest.routes.length > 1 && !routeLinks.some((url) => otherManifestUrls.has(normalizeHttpUrl(url)))
      ? [{ route_key: check.route_key, reason: "no-rendered-link-to-another-authoritative-route" }] : [];
    const missing = [
      ...(check.rendered_qa.clipping.length ? ["clipping"] : []),
      ...(check.rendered_qa.collisions.length ? ["collisions"] : []),
      ...(check.rendered_qa.fixed_rail_overlaps.length ? ["fixed-rail-overlaps"] : []),
      ...(hiddenControls.length ? ["hidden-controls"] : []),
      ...(targetQa.dead_controls.length ? ["dead-controls"] : []),
      ...(targetQa.blocked_handoffs.length ? ["blocked-handoff"] : []),
      ...(check.rendered_qa.overlays.inert_background && check.rendered_qa.overlays.closed_descendants_inert &&
        check.rendered_qa.overlays.stacking && check.rendered_qa.overlays.initial_focus &&
        check.rendered_qa.overlays.background_focus_blocked &&
        check.rendered_qa.overlays.focus_trap && check.rendered_qa.overlays.focus_return ? [] : ["overlay-focus-inertness"]),
      ...(check.rendered_qa.state_semantics.complete ? [] : ["state-semantics"]),
      ...(check.rendered_qa.public_copy.complete ? [] : ["public-copy-residue"]),
      ...(check.rendered_qa.accessibility.complete ? [] : ["accessibility"]),
      ...(check.rendered_qa.short_height.clipping.length || check.rendered_qa.short_height.collisions.length ||
        check.rendered_qa.short_height.fixed_rail_overlaps.length ? ["short-height-layout"] : []),
      ...(check.rendered_qa.short_height.overlays.inert_background && check.rendered_qa.short_height.overlays.closed_descendants_inert &&
        check.rendered_qa.short_height.overlays.stacking && check.rendered_qa.short_height.overlays.initial_focus &&
        check.rendered_qa.short_height.overlays.background_focus_blocked &&
        check.rendered_qa.short_height.overlays.focus_trap && check.rendered_qa.short_height.overlays.focus_return &&
        check.rendered_qa.short_height.state_semantics.complete ? [] : ["short-height-overlay-state"]),
      ...(check.rendered_qa.short_height.public_copy.complete ? [] : ["short-height-public-copy-residue"]),
      ...(check.rendered_qa.short_height.accessibility.complete ? [] : ["short-height-accessibility"]),
      ...(check.rendered_qa.short_height.reduced_motion.complete ? [] : ["short-height-reduced-motion"]),
      ...(targetQa.keyboard.complete ? [] : ["keyboard"]),
      ...(check.rendered_qa.reduced_motion.complete ? [] : ["reduced-motion"]),
      ...(deepLink.complete ? [] : ["deep-link"]),
      ...(reload.complete ? [] : ["reload"]),
      ...(deadEnds.length ? ["dead-end"] : []),
      ...(targetQa.semantic_equivalence.complete ? [] : ["semantic-equivalence"]),
      ...(experiencePaths.some((item) => item.route_key === check.route_key && item.viewport === check.viewport && !item.complete)
        ? ["experience-path"] : []),
    ];
    const cell = {
      route_key: check.route_key, viewport: check.viewport, state_id: check.state_id,
      clipping: check.rendered_qa.clipping, collisions: check.rendered_qa.collisions,
      fixed_rail_overlaps: check.rendered_qa.fixed_rail_overlaps,
      control_visibility: currentControls,
      responsive_control_parity: responsiveControlParityRecord,
      hidden_controls: hiddenControls, dead_controls: targetQa.dead_controls,
      blocked_handoffs: targetQa.blocked_handoffs,
      overlays: check.rendered_qa.overlays, state_semantics: check.rendered_qa.state_semantics,
      public_copy: check.rendered_qa.public_copy, accessibility: check.rendered_qa.accessibility,
      keyboard: targetQa.keyboard,
      reduced_motion: check.rendered_qa.reduced_motion, deep_link: deepLink, reload,
      dead_ends: deadEnds, semantic_equivalence: targetQa.semantic_equivalence,
      experience_paths: experiencePaths.filter((item) => item.route_key === check.route_key && item.viewport === check.viewport),
      short_height: check.rendered_qa.short_height,
      missing, truncated: false, complete: missing.length === 0,
    };
    check.rendered_qa = cell;
    check.pass = check.pass && cell.complete;
    return cell;
  });
  const renderedQaMissing = renderedQaCells.filter((cell) => !cell.complete)
    .map((cell) => `${cell.route_key}/${cell.viewport}/${cell.state_id}:${cell.missing.join(",")}`);
  const experiencePathMissing = experiencePaths.filter((item) => !item.complete)
    .map((item) => `${item.route_key}/${item.viewport}/${item.target_id}`);
  const experiencePathSummary = {
    complete: experiencePathMissing.length === 0,
    missing: experiencePathMissing,
    truncated: false,
    totals: {
      targets: experiencePaths.length,
      resolved: experiencePaths.filter((item) => item.complete).length,
      blocked_handoffs: experiencePaths.filter((item) => item.actions.some((action) => action.resolution === "blocked-handoff")).length,
    },
    paths: experiencePaths,
  };
  const renderedQa = {
    schema_version: 1,
    complete: renderedQaMissing.length === 0 && experiencePathSummary.complete,
    missing: [...renderedQaMissing, ...experiencePathMissing.map((item) => `${item}:experience-path`)],
    truncated: false,
    cells: renderedQaCells,
    presentation_ready: !firstScreen && renderedQaMissing.length === 0 && experiencePathSummary.complete,
    presentation_blocker: firstScreen ? "first-screen authorization is not post-build multi-route/site QA" : null,
    experience_paths: experiencePathSummary,
  };
  const plannedDecisions = visibleDecisionManifest.payload.decisions.filter((decision) =>
    (decision.route_keys || []).some((routeKey) => selectedRoutes.some((route) => route.key === routeKey)));
  const implementedDecisionIds = [...new Set(checks.flatMap((check) => check.visible_decision_ids || []))].sort();
  const missingDecisionIds = [...new Set(plannedDecisions.flatMap((decision) => checks
    .filter((check) => (decision.route_keys || []).includes(check.route_key) && (decision.state_ids || []).includes(check.state_id))
    .some((check) => !(check.visible_decision_ids || []).includes(decision.decision_id)) ? [decision.decision_id] : []))].sort();
  const allowedDecisionIds = new Set(visibleDecisionManifest.payload.planned_decision_ids);
  const unsourcedVisibleDecisions = checks.flatMap((check) =>
    (check.unsourced_visible_parts || []).map((part) => ({
      route_key: check.route_key,
      viewport: check.viewport,
      state_id: check.state_id,
      part,
    })))
    .concat(implementedDecisionIds
      .filter((decisionId) => !allowedDecisionIds.has(decisionId))
      .map((decisionId) => ({
        route_key: null,
        viewport: null,
        state_id: null,
        part: `unknown-decision-id:${decisionId}`,
      })));
  const copyFindings = renderedQaCells.flatMap((cell) => [
    ...(cell.public_copy?.findings || []).map((finding) => ({ route_key: cell.route_key, viewport: cell.viewport, state_id: cell.state_id, ...finding })),
    ...(cell.short_height?.public_copy?.findings || []).map((finding) => ({ route_key: cell.route_key,
      viewport: cell.short_height.profile, state_id: cell.state_id, ...finding })),
  ]);
  const visibleDecisionReconciliation = {
    manifest_path: ".design-dna/visible-decision-sources.json",
    manifest_sha256: visibleDecisionManifest.sha256,
    implemented_decision_ids: implementedDecisionIds,
    missing_decision_ids: missingDecisionIds,
    unsourced_visible_decisions: unsourcedVisibleDecisions,
    scaffold_findings: copyFindings.filter((finding) => finding.kind === "builder-narration"),
    fallback_findings: copyFindings.filter((finding) => finding.kind === "prototype-fallback"),
    placeholder_findings: copyFindings.filter((finding) => finding.kind === "scaffold-placeholder"),
    complete: missingDecisionIds.length === 0 && unsourcedVisibleDecisions.length === 0 && copyFindings.length === 0,
  };
  failedStates = checks.filter((check) => !check.pass).map((check) => `${check.route_key}/${check.viewport}/${check.state_id}`);
  const pass = !unexpected.length && !failedStates.length && servedContent.complete && interactionInventory.complete &&
    renderedQa.complete && visibleDecisionReconciliation.complete;
  return {
    tool: TOOL_NAME, schema_version: SCHEMA_VERSION, producer_script_sha256: PRODUCER_SCRIPT_SHA256,
    runtime_identity: { "scan_build_components.mjs": PRODUCER_SCRIPT_SHA256,
      "browser_evidence.mjs": BROWSER_EVIDENCE_SHA256, "observe_reference.mjs": OBSERVER_SCRIPT_SHA256,
      "playwright_resolver.mjs": PLAYWRIGHT_RESOLVER_SHA256,
      "playwright-entry": loaded.dependency.resolved_file_sha256,
      "browser-executable": browserDependency.sha256 },
    dependencies: { playwright: loaded.dependency, browser_executable: browserDependency },
    scanned_at: new Date().toISOString(), build_id: buildId, run_id: runId,
    manifest_id: manifest.manifest_id,
    route_filter: routeKeys, first_screen_only: firstScreen,
    manifest_sha256: createHash("sha256").update(fs.readFileSync(manifest.__file)).digest("hex"),
    viewports: manifest.viewports, state_ids: [...new Set(manifest.routes.flatMap((route) => route.states.map((state) => state.id)))].sort(),
    routes: routeComponents, checks, census, names: census.map((row) => row.name).sort(),
    navigations, served_content: servedContent, served_content_identity: servedContent,
    state_inventories: stateInventories, interaction_inventory: interactionInventory,
    implementation_scope: implementationScope,
    rendered_qa: renderedQa,
    visible_decision_reconciliation: visibleDecisionReconciliation,
    interaction_frame_directory: interactionFrameRelativeRoot,
    discovered_urls: [...discovered].sort(), unexpected_urls: unexpected, failed_states: failedStates,
    pass,
    verdict: pass ? `Scanned ${checks.length} exact route/viewport/state cells; every navigation was exact 2xx, response bytes were stable, and every internal route is manifested.` :
      [unexpected.length ? `unmanifested internal routes: ${unexpected.join(", ")}` : null,
       failedStates.length ? `declared states or DOM surfaces not exercised: ${failedStates.join(", ")}` : null,
        !servedContent.complete ? `served response bodies changed between repeated loads: ${servedContent.inconsistent_reloads.map((item) => item.key).join(", ")}` : null,
        !interactionInventory.complete ? `interaction transfer inventory incomplete: ${interactionMissing.join(", ") || "responsive/source-state binding"}` : null,
        !renderedQa.complete ? `rendered browser QA failed: ${renderedQaMissing.join(" | ")}` : null,
        !visibleDecisionReconciliation.complete ? "visible decisions include unsourced/scaffold/fallback/placeholder output" : null].filter(Boolean).join("; "),
  };
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
if (invokedDirectly) {
  const opts = parseArgs(process.argv.slice(2));
  const manifest = readManifest(opts.manifest);
  if (opts.routeKeys.some((key) => !manifest.routes.some((route) => route.key === key))) fail("route-key-missing", "Every --route-key must exist in the manifest.");
  manifest.__file = opts.manifest;
  const record = await scanBuild({ manifest, buildId: opts.buildId, runId: opts.runId, routeKeys: opts.routeKeys,
    firstScreen: opts.firstScreen, browserExecutable: opts.browserExecutable, outFile: opts.out });
  await mkdir(path.dirname(opts.out), { recursive: true });
  await writeFile(opts.out, JSON.stringify(record, null, 2) + "\n", "utf8");
  process.stdout.write(JSON.stringify({ ok: record.pass, pass: record.pass, verdict: record.verdict, record: opts.out, names: record.names.length }, null, 2) + "\n");
  process.exit(record.pass ? 0 : 1);
}
