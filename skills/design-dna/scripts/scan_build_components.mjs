#!/usr/bin/env node
/** Enumerate every visible component across the authoritative route/state/viewport matrix. */

import fs from "node:fs";
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { execFileSync } from "node:child_process";
import {
  aggregateServedContent,
  applyManifestState,
  beginServedContentCapture,
  canonicalJson,
  captureInteractionCensus,
  isSourceAmbientMapping,
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
import { fileURLToPath } from "node:url";
import { snapshotImplementation, implementationSnapshotsEqual } from "./implementation_snapshot.mjs";
import { firstScreenManifest, deriveFirstScreenRegionAuthority, proofRegionScopePass, mergeDecisionRootSamples } from "./construction_phase.mjs";
import {auditRenderedFontDelivery, prepareRenderedFontDelivery} from "./rendered_font_delivery.mjs";
const SCRIPT_PATH = path.resolve(fileURLToPath(import.meta.url));
const PRODUCER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(SCRIPT_PATH)).digest("hex");
const SCRIPT_DIR = path.dirname(SCRIPT_PATH);
const OBSERVER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "observe_reference.mjs"))).digest("hex");
const RECORDER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "record_reference.mjs"))).digest("hex");
const BROWSER_EVIDENCE_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "browser_evidence.mjs"))).digest("hex");
const PLAYWRIGHT_RESOLVER_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "playwright_resolver.mjs"))).digest("hex");
const SHA256_RE = /^[0-9a-f]{64}$/;
const ROUTE_FIELDS = new Set([
  "key", "url", "mapped_reference_rank", "mapped_reference_id",
  "mapped_reference_observation", "mapped_reference_sha256", "states",
]);
const SOURCE_PROFILE_VIEWPORTS = Object.freeze({
  wide: Object.freeze({ minWidth: 1280 }),
  narrow: Object.freeze({ maxWidth: 430 }),
});
// The recorder's minimum per-profile watch is the lower bound for a build's
// autonomous-surface dwell. A brief post-load pause cannot certify that a
// timer, delayed dialog, or autonomous state does not exist.
export const REFERENCE_RECORDING_DWELL_MS = 90_000;
// Fifty milliseconds is stricter than the authoritative recorder's 15 FPS
// floor (66.6ms).  It is deliberately not a convenient post-load pause.
export const AUTONOMOUS_MONITOR_SAMPLE_MS = 50;

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

export function firstScreenScopePass(scope, authority = null) {
  return proofRegionScopePass(scope, authority);
}

export function firstScreenRegionAuthority(project, mapping, routeKey, profile, stateId, viewportHeight) {
  const records = {};
  for (const decision of mapping.decisions || []) {
    if (decision.component_id !== mapping.proof_isolation?.region_component_id || decision.category !== 'layout') continue;
    const record = decision.style_provenance?.record, file = artifactFilePath(project, record?.path);
    if (!file || !regularFile(file) || fs.statSync(file).nlink !== 1) throw new Error('first-screen source style record is not one ordinary contained file');
    for (let cursor = file; pathWithin(cursor, project); cursor = path.dirname(cursor)) {
      if (fs.lstatSync(cursor).isSymbolicLink()) throw new Error('first-screen source style ancestry redirects outside its authority');
      if (cursor === path.resolve(project)) break;
    }
    const bytes = fs.readFileSync(file);
    if (sha256(bytes) !== record.sha256) throw new Error('first-screen source style record drifted from the frozen construction binding');
    records[record.path] = JSON.parse(bytes.toString('utf8'));
  }
  return deriveFirstScreenRegionAuthority(mapping, records, routeKey, profile, stateId, viewportHeight);
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

export const CENSUS_SCRIPT = `((scopeAuthorization = null) => {
  const semantic = new Set(['header','main','section','article','aside','nav','footer','form','button',
    'input','textarea','select','table','thead','tbody','tr','th','td','ul','ol','li','h1','h2','h3',
    'h4','h5','h6','img','video','picture','canvas','svg','details','summary','a']);
  const seen = new Map();
  const visibleDecisionIds = new Set();
  const unsourcedVisibleParts = new Set();
  const wrapperInheritedVisibleParts = [];
  const decisionRoots = new Map();
  const mediaInventory = [];
  const pseudoInventory = [];
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
    const declaredComponent = el.getAttribute('data-design-dna-component');
    if (declaredComponent) keys.push('component:' + encodeURIComponent(String(declaredComponent)));
    const role = el.getAttribute('role'); if (role) keys.push('role:' + encodeURIComponent(role.toLowerCase()));
    if (semantic.has(tag)) keys.push('tag:' + tag);
    const paints = v.s.backgroundImage !== 'none' || v.s.backgroundColor !== 'rgba(0, 0, 0, 0)' ||
      parseFloat(v.s.borderTopWidth) > 0 || v.s.boxShadow !== 'none' ||
      ['IMG','VIDEO','PICTURE','CANVAS','SVG'].includes(el.tagName);
    const ownsText = [...el.childNodes].some((n) => n.nodeType === 3 && n.nodeValue.trim());
    const independentlyVisible = paints || ownsText || semantic.has(tag);
    const ownDecisionId = el.getAttribute('data-design-dna-decision-id')?.trim() || '';
    const decisionOwner = el.closest('[data-design-dna-decision-id]');
    const decisionId = decisionOwner?.getAttribute('data-design-dna-decision-id')?.trim() || '';
    const componentKey = (scope === 'document' ? '' : scope + '|') +
      (declaredComponent ? 'component:' + encodeURIComponent(String(declaredComponent)) : (keys[0] || 'tag:' + tag + ':unclassed'));
    if (ownDecisionId) {
      visibleDecisionIds.add(ownDecisionId);
      const rootsForDecision = decisionRoots.get(ownDecisionId) || [];
      const parentBox = el.parentElement?.getBoundingClientRect() || {left: 0, top: 0};
      const directTextNodes = [...el.childNodes].filter((node) => node.nodeType === 3 && node.nodeValue.trim());
      const lineTops = new Set(directTextNodes.flatMap((node) => {const range = document.createRange(); range.selectNodeContents(node); return [...range.getClientRects()].map((rect) => Math.round(rect.top));}));
      let previous = el.previousElementSibling;
      while (previous && !visible(previous)) previous = previous.previousElementSibling;
      rootsForDecision.push({ component_key: componentKey, component_id: declaredComponent || null, tag, scope, direct: true,
        content_facts: {text: directTextNodes.map((node) => node.nodeValue).join('').replace(/\\s+/g, ' ').trim(),
          tag, role: el.getAttribute('role'), line_count: lineTops.size,
          parent_component: el.parentElement?.getAttribute('data-design-dna-component') || null,
          previous_component: previous?.getAttribute('data-design-dna-component') || null},
        top: Math.round(v.box.top + scrollY), left: Math.round(v.box.left), width: Math.round(v.box.width), height: Math.round(v.box.height),
        geometry: {left: Math.round(v.box.left - parentBox.left), top: Math.round(v.box.top - parentBox.top),
          width: Math.round(v.box.width), height: Math.round(v.box.height)},
        computed_style: {
          'font-family': v.s.fontFamily, 'font-size': v.s.fontSize, 'font-weight': v.s.fontWeight,
          'line-height': v.s.lineHeight, 'letter-spacing': v.s.letterSpacing,
          'color': v.s.color, 'background-color': v.s.backgroundColor,
          'background-image': v.s.backgroundImage, 'border-color': v.s.borderColor,
          'border-radius': v.s.borderRadius, 'box-shadow': v.s.boxShadow,
          'padding': v.s.padding, 'gap': v.s.gap, 'display': v.s.display,
          'margin': v.s.margin, 'width': v.s.width, 'height': v.s.height,
          'min-height': v.s.minHeight, 'min-width': v.s.minWidth, 'max-width': v.s.maxWidth,
          'box-sizing': v.s.boxSizing, 'align-items': v.s.alignItems, 'justify-content': v.s.justifyContent,
          'position': v.s.position, 'top': v.s.top, 'left': v.s.left,
          'object-fit': v.s.objectFit, 'object-position': v.s.objectPosition,
          'grid-template-columns': v.s.gridTemplateColumns, 'transform': v.s.transform,
          'transition-property': v.s.transitionProperty, 'transition-duration': v.s.transitionDuration,
          'transition-timing-function': v.s.transitionTimingFunction, 'cursor': v.s.cursor,
        } });
      decisionRoots.set(ownDecisionId, rootsForDecision);
    } else if (independentlyVisible && decisionId) {
      // A parent data attribute may source its own grid geometry, but it may
      // not launder the independently painted text/control/media descendants
      // that make up a generic header or footer.  Those need their own exact
      // source binding.
      wrapperInheritedVisibleParts.push({ decision_id: decisionId, component_key: componentKey, tag, scope });
    } else if (independentlyVisible) {
      unsourcedVisibleParts.add(componentKey);
    }
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
      pseudoInventory.push({ decision_id: ownDecisionId || decisionId || null, component_key: componentKey,
        pseudo, content, background_source: style.backgroundImage, properties: {
          'color': style.color, 'background-color': style.backgroundColor,
          'background-image': style.backgroundImage, 'border-color': style.borderColor,
          'border-radius': style.borderRadius, 'box-shadow': style.boxShadow,
          'transform': style.transform, 'opacity': style.opacity,
        } });
      if (!ownDecisionId) {
        if (decisionId) wrapperInheritedVisibleParts.push({ decision_id: decisionId,
          component_key: (scope === 'document' ? '' : scope + '|') + 'pseudo:' + pseudo.slice(2) + ':' + owner,
          tag: 'pseudo', scope });
        else unsourcedVisibleParts.add((scope === 'document' ? '' : scope + '|') + 'pseudo:' + pseudo.slice(2) + ':' + owner);
      }
    }
    const backgroundMedia = v.s.backgroundImage !== 'none' && /url\\(/i.test(v.s.backgroundImage);
    const mediaKind = el.tagName === 'IMG' ? 'image' : el.tagName === 'VIDEO' ? 'video' : el.tagName === 'AUDIO' ? 'audio' :
      el.tagName === 'CANVAS' ? 'canvas' : el.tagName === 'SVG' ? 'svg' : backgroundMedia ? 'background-image' : null;
    if (mediaKind) {
      mediaInventory.push({ decision_id: ownDecisionId || decisionId || null,
        asset_id: el.getAttribute('data-design-dna-asset-id')?.trim() || null,
        component_key: componentKey, media_kind: mediaKind,
        source: el.currentSrc || el.src || el.getAttribute('src') || (backgroundMedia ? v.s.backgroundImage : null),
        poster: el.getAttribute('poster') || null,
        object_fit: v.s.objectFit, object_position: v.s.objectPosition,
        box: { width: Math.round(v.box.width), height: Math.round(v.box.height) },
        temporal: (el.tagName === 'VIDEO' || el.tagName === 'AUDIO') ? {
          paused: Boolean(el.paused), ready_state: Number(el.readyState),
          duration: Number.isFinite(el.duration) ? Number(el.duration) : null,
          current_time: Number.isFinite(el.currentTime) ? Number(el.currentTime) : null,
        } : null });
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
  const primaryRoots = scopeAuthorization ? [...document.querySelectorAll('[data-design-dna-component]')]
    .filter((element) => element.getAttribute('data-design-dna-component') === scopeAuthorization.region_component_id) : [];
  const primary = primaryRoots.length === 1 ? primaryRoots[0] : null;
  const regionSet = scopeAuthorization ? [...primaryRoots, ...regionCandidates.filter((element) =>
    !primaryRoots.includes(element) && (!primary || !primary.contains(element) && !element.contains(primary)))] :
    regionCandidates.filter((element) => !regionCandidates.some((other) => other !== element && element.contains(other)));
  const substantial_regions = regionSet.map((element) => {
    const box = element.getBoundingClientRect();
    const classes = String(element.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean).sort();
    return { top: Math.round(box.top + scrollY), bottom: Math.round(box.bottom + scrollY), width: Math.round(box.width), height: Math.round(box.height), tag: element.tagName.toLowerCase(),
      component_id: element.getAttribute('data-design-dna-component') || null,
      component_key: element.getAttribute('data-design-dna-component') ? 'component:' + encodeURIComponent(element.getAttribute('data-design-dna-component')) :
        element.id ? 'id:' + element.id : classes.length ? 'class:' + classes.join('.') : 'tag:' + element.tagName.toLowerCase(),
      component_identity: element.id ? 'id:' + element.id : classes.length ? 'class:' + classes.join('.') : 'tag:' + element.tagName.toLowerCase() };
  }).sort((a, b) => a.top - b.top || a.bottom - b.bottom);
  const implementation_scope = { document_height: Math.round(document.documentElement.scrollHeight), viewport_height: innerHeight,
    substantial_regions, beyond_first_screen_regions: substantial_regions.filter((region) => region.top >= innerHeight) };
  if (scopeAuthorization) {
    implementation_scope.source_extent = scopeAuthorization;
    implementation_scope.extra_primary_regions = primary ? [...primary.querySelectorAll('main,section,article')]
      .filter((element) => {const style=getComputedStyle(element),box=element.getBoundingClientRect();return style.display!=='none' && style.visibility!=='hidden' && Number(style.opacity)>0 && box.width>0 && box.height>0 && !scopeAuthorization.nested_region_component_ids.includes(element.getAttribute('data-design-dna-component'));})
      .map((element) => element.getAttribute('data-design-dna-component') || element.tagName.toLowerCase()).sort() : [];
    implementation_scope.unplanned_decision_ids = [...visibleDecisionIds].filter((id) => !scopeAuthorization.proof_decision_ids.includes(id)).sort();
    implementation_scope.unsourced_visible_parts = [...unsourcedVisibleParts].sort();
    implementation_scope.wrapper_inherited_visible_parts = [...wrapperInheritedVisibleParts];
    implementation_scope.reused_decision_ids = [...decisionRoots.entries()].filter(([_id,roots]) => roots.length > 1).map(([id]) => id).sort();
    implementation_scope.outside_primary_components = [...document.querySelectorAll('[data-design-dna-component],[data-design-dna-decision-id]')]
      .filter((element) => {const style=getComputedStyle(element),box=element.getBoundingClientRect();return style.display!=='none' && style.visibility!=='hidden' && Number(style.opacity)>0 && box.width>0 && box.height>0 && (!primary || element!==primary && !primary.contains(element));})
      .map((element) => element.getAttribute('data-design-dna-component') || element.getAttribute('data-design-dna-decision-id')).sort();
  }
  return {
    components: [...seen.values()].map((row) => ({ ...row, area: +row.area.toFixed(4) }))
      .sort((a, b) => b.area - a.area || a.name.localeCompare(b.name)),
    links: [...links].sort(), inspection, implementation_scope,
    visible_decision_ids: [...visibleDecisionIds].sort(),
    unsourced_visible_parts: [...unsourcedVisibleParts].sort(),
    wrapper_inherited_visible_parts: wrapperInheritedVisibleParts.sort((a, b) =>
      (a.decision_id + '|' + a.component_key).localeCompare(b.decision_id + '|' + b.component_key)),
    decision_roots: [...decisionRoots.entries()].map(([decision_id, roots]) => ({ decision_id,
      roots: roots.sort((a, b) => a.component_key.localeCompare(b.component_key)) }))
      .sort((a, b) => a.decision_id.localeCompare(b.decision_id)),
    media_inventory: mediaInventory.sort((a, b) => (String(a.component_key) + '|' + String(a.media_kind)).localeCompare(String(b.component_key) + '|' + String(b.media_kind))),
    pseudo_inventory: pseudoInventory.sort((a, b) => (String(a.component_key) + '|' + a.pseudo).localeCompare(String(b.component_key) + '|' + b.pseudo)),
  };
})`;

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

/** A build viewport is not a free-form label. The source recorder has exactly
 * two observed profiles, so an alias such as `desktop` can never silently
 * select the wrong source evidence. The schema has no explicit profile-mapping
 * field; until it does, only these exact names are safe. */
export function sourceProfileViewportFailures(viewports) {
  if (!Array.isArray(viewports) || viewports.length !== 2) {
    return ["The manifest must declare exactly the two source-bound viewports `wide` and `narrow`; aliases and extra profiles have no source-evidence mapping."];
  }
  const byName = new Map();
  for (const viewport of viewports) {
    if (!viewport || typeof viewport.name !== "string" || byName.has(viewport.name)) {
      return ["The manifest must declare one unique `wide` and one unique `narrow` source-bound viewport."];
    }
    byName.set(viewport.name, viewport);
  }
  if (byName.size !== 2 || !byName.has("wide") || !byName.has("narrow")) {
    return ["The manifest viewport names must be exactly `wide` and `narrow`; the route schema has no source-profile alias mapping."];
  }
  if (!Number.isInteger(byName.get("wide").width) || byName.get("wide").width < SOURCE_PROFILE_VIEWPORTS.wide.minWidth) {
    return ["The source-bound `wide` viewport must be at least 1280px wide."];
  }
  if (!Number.isInteger(byName.get("narrow").width) || byName.get("narrow").width > SOURCE_PROFILE_VIEWPORTS.narrow.maxWidth) {
    return ["The source-bound `narrow` viewport must be 430px wide or less."];
  }
  return [];
}

function pathWithin(candidate, root) {
  const resolvedCandidate = path.resolve(candidate);
  const resolvedRoot = path.resolve(root);
  return resolvedCandidate === resolvedRoot || resolvedCandidate.startsWith(resolvedRoot + path.sep);
}

function regularFile(pathname) {
  try {
    const stat = fs.lstatSync(pathname);
    return stat.isFile() && !stat.isSymbolicLink();
  } catch {
    return false;
  }
}

function exactCanonicalUrl(value) {
  if (typeof value !== "string") return null;
  try {
    const normalized = normalizeHttpUrl(value);
    return normalized === value ? normalized : null;
  } catch {
    return null;
  }
}

function artifactFilePath(root, relative) {
  if (typeof relative !== "string" || !relative || relative.includes("\\") ||
      path.posix.isAbsolute(relative) || path.win32.isAbsolute(relative)) return null;
  const parts = relative.split("/");
  if (parts.some((part) => !part || part === "." || part === "..")) return null;
  const candidate = path.resolve(root, ...parts);
  return pathWithin(candidate, root) ? candidate : null;
}

/** Verify the source recording that grounds the build's autonomous dwell.
 * This is deliberately independent of the browser monitor: the exact
 * recorder/ledger bytes and its wide/narrow profiles must be sound before a
 * monitor can rely on their duration. */
export function sourceRecordingBindingFailures(route, observationPath, observation) {
  const failures = [];
  const referenceId = typeof route?.mapped_reference_id === "string" ? route.mapped_reference_id : "";
  if (!/^strong-[1-9][0-9]*(?:-[a-z][a-z0-9-]{0,47})?$/.test(referenceId) ||
      !observationPath || !regularFile(observationPath) || !observation || typeof observation !== "object") {
    return { failures: ["The mapped source recording cannot be located from an exact reference observation."], recording: null };
  }
  const referenceRoot = path.resolve(path.dirname(observationPath));
  const recordingPath = path.resolve(referenceRoot, `${referenceId}-recording.json`);
  const ledgerPath = path.resolve(referenceRoot, `${referenceId}-artifacts.json`);
  if (!pathWithin(recordingPath, referenceRoot) || !pathWithin(ledgerPath, referenceRoot) ||
      !regularFile(recordingPath) || !regularFile(ledgerPath)) {
    return { failures: ["The mapped source recording and artifact ledger must exist at the canonical strong-N recording paths."], recording: null };
  }

  let recording, ledger, recordingBytes, ledgerBytes;
  try {
    recordingBytes = fs.readFileSync(recordingPath);
    recording = JSON.parse(recordingBytes.toString("utf8"));
    ledgerBytes = fs.readFileSync(ledgerPath);
    ledger = JSON.parse(ledgerBytes.toString("utf8"));
  } catch (error) {
    return { failures: [`The mapped source recording or artifact ledger is unreadable: ${String(error).slice(0, 180)}`], recording: null };
  }

  const sourceUrl = exactCanonicalUrl(observation.url);
  const requestedUrl = exactCanonicalUrl(recording?.requested_url);
  const recordedUrl = exactCanonicalUrl(recording?.url);
  if (!sourceUrl || sourceUrl !== requestedUrl || sourceUrl !== recordedUrl ||
      recording?.tool !== "record_reference.mjs" || recording?.schema_version !== 4 ||
      recording?.producer_script_sha256 !== RECORDER_SCRIPT_SHA256 ||
      recording?.runtime_identity?.["record_reference.mjs"] !== RECORDER_SCRIPT_SHA256 ||
      recording?.id !== referenceId) {
    failures.push("The mapped source recording does not bind current recorder bytes, the exact reference ID, and the exact observed source URL.");
  }
  if (!recording?.state_contract || typeof recording.state_contract !== "object" ||
      !observation.state_contract || typeof observation.state_contract !== "object" ||
      canonicalJson(recording.state_contract) !== canonicalJson(observation.state_contract)) {
    failures.push("The mapped source recording and observation do not bind the same exact source-state contract.");
  }
  const minimumDuration = Number(recording?.minimum_duration_per_profile_s);
  const minimumDurationMs = minimumDuration * 1000;
  const fps = Number(recording?.fps);
  if (!Number.isFinite(minimumDuration) || !Number.isInteger(minimumDurationMs) || minimumDuration < REFERENCE_RECORDING_DWELL_MS / 1000 ||
      !Number.isFinite(fps) || fps < 15) {
    failures.push("The mapped source recording does not meet the 90-second per-profile and 15-FPS evidence floors.");
  }
  const profiles = recording?.profiles;
  const finalUrls = recording?.final_urls;
  const recordingCoverage = recording?.coverage;
  if (!profiles || typeof profiles !== "object" || Array.isArray(profiles) ||
      Object.keys(profiles).sort().join("|") !== "narrow|wide" ||
      !finalUrls || typeof finalUrls !== "object" || Array.isArray(finalUrls) ||
      Object.keys(finalUrls).sort().join("|") !== "narrow|wide" ||
      !recordingCoverage || recordingCoverage.wide_complete !== true ||
      recordingCoverage.narrow_complete !== true || recordingCoverage.complete !== true) {
    failures.push("The mapped source recording must prove complete exact wide and narrow profiles.");
  } else {
    for (const [profileName, dimensions] of [["wide", { width: 1440, height: 900 }], ["narrow", { width: 390, height: 844 }]]) {
      const profile = profiles[profileName];
      const durationValue = Number(profile?.duration_s);
      const durationMs = Number.isFinite(durationValue) && Number.isInteger(durationValue * 1000) ? durationValue * 1000 : null;
      const expectedFrameCount = Number.isInteger(durationMs) && Number.isFinite(fps)
        ? Math.ceil(durationMs / 1000 * fps) : null;
      if (!profile || typeof profile !== "object" || Array.isArray(profile) ||
          profile.profile !== profileName || canonicalJson(profile.viewport) !== canonicalJson({ name: profileName, ...dimensions }) ||
          !Number.isFinite(Number(profile.duration_s)) || Number(profile.duration_s) < minimumDuration ||
          !Number.isInteger(durationMs) || durationMs < minimumDurationMs ||
          profile.fps !== recording.fps || profile.coverage?.complete !== true ||
          !Number.isInteger(profile.frames?.count) || !Number.isInteger(expectedFrameCount) || profile.frames.count < expectedFrameCount ||
          exactCanonicalUrl(finalUrls[profileName]) !== sourceUrl) {
        failures.push(`The mapped source recording ${profileName} profile does not bind its packaged viewport, duration, coverage, and exact settled source URL.`);
      }
    }
  }

  const expectedLedgerKeys = ["algorithm", "artifacts", "recording", "schema_version", "sha256"].sort().join("|");
  if (!ledger || typeof ledger !== "object" || Array.isArray(ledger) ||
      Object.keys(ledger).sort().join("|") !== expectedLedgerKeys ||
      ledger.schema_version !== 1 || ledger.algorithm !== "sha256" ||
      ledger.recording !== path.basename(recordingPath) || !Array.isArray(ledger.artifacts)) {
    failures.push("The mapped source artifact ledger has an unsupported canonical shape.");
  } else {
    const ledgerCore = {
      schema_version: ledger.schema_version,
      algorithm: ledger.algorithm,
      recording: ledger.recording,
      artifacts: ledger.artifacts,
    };
    if (ledger.sha256 !== sha256(Buffer.from(canonicalJson(ledgerCore), "utf8"))) {
      failures.push("The mapped source artifact ledger canonical hash is invalid.");
    }
    const seenFiles = new Set();
    const kindsByProfile = new Map([["wide", new Set()], ["narrow", new Set()]]);
    const recordingRows = [];
    for (const [index, entry] of ledger.artifacts.entries()) {
      if (!entry || typeof entry !== "object" || Array.isArray(entry) ||
          Object.keys(entry).sort().join("|") !== "bytes|file|kind|profile|sha256" ||
          typeof entry.kind !== "string" || !entry.kind ||
          !(entry.profile === null || entry.profile === "wide" || entry.profile === "narrow") ||
          typeof entry.file !== "string" || typeof entry.bytes !== "number" || !Number.isInteger(entry.bytes) || entry.bytes < 1 ||
          typeof entry.sha256 !== "string" || !SHA256_RE.test(entry.sha256) || seenFiles.has(entry.file)) {
        failures.push(`The mapped source artifact ledger row ${index + 1} has an invalid path, profile, or hash binding.`);
        continue;
      }
      seenFiles.add(entry.file);
      const artifact = artifactFilePath(referenceRoot, entry.file);
      let artifactMatches = false;
      try {
        artifactMatches = Boolean(artifact && regularFile(artifact) && fs.statSync(artifact).size === entry.bytes &&
          sha256(fs.readFileSync(artifact)) === entry.sha256);
      } catch { artifactMatches = false; }
      if (!artifactMatches) {
        failures.push(`The mapped source artifact ledger row ${index + 1} bytes are missing or drifted.`);
      }
      if (entry.kind === "recording") recordingRows.push(entry);
      else if (entry.profile === null) failures.push(`The mapped source artifact ledger row ${index + 1} has an unbound profile.`);
      else kindsByProfile.get(entry.profile).add(entry.kind);
    }
    if (recordingRows.length !== 1 || canonicalJson(recordingRows[0]) !== canonicalJson({
      kind: "recording", profile: null, file: path.basename(recordingPath),
      bytes: recordingBytes.length, sha256: sha256(recordingBytes),
    })) {
      failures.push("The mapped source artifact ledger does not hash-bind the exact recording bytes once.");
    }
    for (const profileName of ["wide", "narrow"]) {
      const requiredKinds = ["video", "frame", "event-sheet", "cursor-path", "difference-signal", "events-index"];
      const missingKinds = requiredKinds.filter((kind) => !kindsByProfile.get(profileName).has(kind));
      if (missingKinds.length) {
        failures.push(`The mapped source artifact ledger ${profileName} profile lacks ${missingKinds.join(", ")} evidence.`);
      }
    }
  }
  return {
    failures,
    recording: failures.length ? null : {
      file: recordingPath,
      ledger_file: ledgerPath,
      sha256: sha256(recordingBytes),
      ledger_sha256: sha256(ledgerBytes),
      state_contract: recording.state_contract,
      minimum_duration_ms: minimumDurationMs,
      profile_recordings: Object.fromEntries(Object.entries(profiles).map(([profileName, profile]) => [profileName, {
        duration_ms: Number(profile.duration_s) * 1000, fps: Number(profile.fps), frame_count: Number(profile.frames.count),
      }])),
    },
  };
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
  const sourceProfileFailures = sourceProfileViewportFailures(payload.viewports);
  if (sourceProfileFailures.length) fail("manifest-invalid", sourceProfileFailures.join(" "));
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
    const sourceRecording = sourceRecordingBindingFailures(route, observationPath, observation);
    if (sourceRecording.failures.length || !sourceRecording.recording) {
      fail("manifest-invalid", `Route ${route.key} source recording is not an exact ledger-bound wide/narrow source profile: ${sourceRecording.failures.join(" ")}`);
    }
    Object.defineProperty(route, "__observation", { value: observation, enumerable: false });
    Object.defineProperty(route, "__observationPath", { value: observationPath, enumerable: false });
    Object.defineProperty(route, "__sourceRecording", { value: sourceRecording.recording, enumerable: false });
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
  const expected = ["construction_authorization","created_at","decisions","completeness","planned_decision_ids","proof_isolation","proof_build_id","record_type",
    "route_manifest","schema_version","source_contribution_scope","source_observations","source_state_dispositions",
    ...(payload && Object.hasOwn(payload, "content_transfer") ? ["content_transfer"] : [])].sort();
  if (!payload || Object.keys(payload).sort().join("|") !== expected.join("|") || payload.schema_version !== 2 ||
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

export async function captureState(page, state, firstScreen = false, authority = null) {
  await page.evaluate((value) => { window.__dnaFirstScreenOnly = value; }, firstScreen && !authority);
  const application = await applyManifestState(page, state);
  const capture = async () => {
    const snapshot = await page.evaluate(`${CENSUS_SCRIPT}(${JSON.stringify(authority)})`);
    const components = await page.evaluate(() => [...document.querySelectorAll('[data-design-dna-component]')].filter((element) => {
      const style = getComputedStyle(element), box = element.getBoundingClientRect();
      return [...element.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim()) &&
        style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && box.width > 0 && box.height > 0;
    }).map((element) => ({component_id: element.dataset.designDnaComponent,
      selector: `[data-design-dna-component="${CSS.escape(element.dataset.designDnaComponent)}"]`, family: getComputedStyle(element).fontFamily})));
    snapshot.font_delivery = await auditRenderedFontDelivery(page, components);
    return snapshot;
  };
  const snapshots = [await capture()];
  if (firstScreen && (!authority || snapshots[0].implementation_scope.document_height <= page.viewportSize().height)) return { attempted: 1, covered: 1, snapshots, application, scroll: { complete: true, surfaces: [] } };
  if (firstScreen && !firstScreenScopePass(snapshots[0].implementation_scope, authority)) return {attempted: 1, covered: 0, snapshots, application, scroll: {complete: false, surfaces: [], reason: 'source-bound-primary-extent-mismatch'}};
  const scroll = await traverseScrollSurfaces(page, { maxTicks: 240, settleMs: 180,
    onTick: async () => snapshots.push(await capture()) });
  if (firstScreen && snapshots.some((item) => !firstScreenScopePass(item.implementation_scope, authority))) {
    scroll.complete = false; scroll.reason = 'primary-region-extent-drift-during-traversal';
  }
  return { attempted: 1, covered: scroll.complete ? 1 : 0, snapshots, application, scroll };
}

// Installed before a watched navigation. It deliberately preserves raw
// additions/removals even when a first-visit timer consumes itself before the
// post-navigation monitor can take its first rendered sample.
export const AUTONOMOUS_EARLY_INIT = `(() => {
  if (window.__designDnaAutonomousEarlyWatch) return;
  const tokens = (value) => String(value || '').split(/[\\s,]+/).filter(Boolean).sort();
  // Do not let ordinary document construction (a nav link, a button, or an
  // author-owned state marker) masquerade as an autonomous surface.  This is
  // deliberately the disruptive-surface predicate used by the long watcher:
  // semantic modal names, or a genuinely viewport-covering fixed layer.
  const surfaceKind = (node, disconnected = false) => {
    if (!node || node.nodeType !== 1) return { relevant: false, lexical: false, geometric: false };
    const element = node;
    const lexical = element.matches('[role="dialog"],dialog,[aria-modal="true"],[data-ff-el="modal"],[class*="modal" i],[class*="dialog" i],[class*="overlay" i],[class*="drawer" i],[class*="toast" i],[class*="popup" i],[class*="newsletter" i],[class*="interstitial" i],[class*="survey" i],[class*="gate" i],[class*="paywall" i],[id*="modal" i],[id*="dialog" i],[id*="overlay" i],[id*="drawer" i],[id*="toast" i],[id*="popup" i],[id*="newsletter" i],[id*="interstitial" i],[id*="survey" i],[id*="gate" i],[id*="paywall" i]');
    if (disconnected || !element.isConnected) {
      const inline = String(element.getAttribute('style') || '');
      const geometric = /position\\s*:\\s*(?:fixed|sticky)/i.test(inline)
        && /(?:inset|width|height)\\s*:/i.test(inline);
      return { relevant: lexical || geometric, lexical, geometric };
    }
    const style = getComputedStyle(element), box = element.getBoundingClientRect();
    const geometric = style.position === 'fixed' && Number(style.zIndex || 0) > 0
      && box.width >= innerWidth * .5 && box.height >= innerHeight * .35;
    return { relevant: lexical || geometric, lexical, geometric };
  };
  const accessibleName = (element) => {
    const labelledBy = String(element.getAttribute('aria-labelledby') || '').split(/\\s+/).filter(Boolean)
      .map((id) => element.ownerDocument.getElementById(id)?.textContent || '').join(' ').trim();
    const heading = [...element.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')]
      .map((candidate) => (candidate.getAttribute('aria-label') || candidate.textContent || '').trim()).find(Boolean) || '';
    return (element.getAttribute('aria-label') || labelledBy || element.getAttribute('title') || heading || element.textContent || '')
      .replace(/\\s+/g, ' ').trim().slice(0, 240);
  };
  const describe = (node, disconnected = false) => {
    if (!node || node.nodeType !== 1) return null;
    const element = node;
    const kind = surfaceKind(element, disconnected);
    const classes = String(element.getAttribute('class') || '').trim().split(/\\s+/).filter(Boolean).sort();
    const name = accessibleName(element);
    const role = (element.getAttribute('role') || element.tagName.toLowerCase()).toLowerCase();
    return { tag: element.tagName.toLowerCase(), id: element.id || null, role: element.getAttribute('role') || null,
      classes, class_signature: classes, accessible_name: name, semantic_key: role + '|' + name.toLowerCase(),
      component_keys: ['tag:' + element.tagName.toLowerCase(), ...(element.getAttribute('role') ? ['role:' + role] : []), ...classes.map((value) => 'class:' + encodeURIComponent(value))].sort(),
      aria_modal: element.getAttribute('aria-modal'), aria_hidden: element.getAttribute('aria-hidden'),
      candidate: kind.relevant, lexical_surface_signal: kind.lexical, geometric_surface_signal: kind.geometric,
      connected: element.isConnected,
      rect: !disconnected && element.isConnected ? (() => { const box = element.getBoundingClientRect(); return {
        left: Math.round(box.left), top: Math.round(box.top), width: Math.round(box.width), height: Math.round(box.height) }; })() : null,
      state_ids: [element.getAttribute('data-design-dna-state'), ...tokens(element.getAttribute('data-design-dna-states'))].filter(Boolean).sort() };
  };
  const state = { navigation_start_ms: performance.now(), events: [], pending: [], sequence: 0,
    observer: null, observers: new Map(), original_attach_shadow: null, attach_shadow_wrapper: null };
  state.ingest = (records) => {
    for (const record of records) {
      const added = [...record.addedNodes].map((node) => describe(node, !node.isConnected)).filter((row) => row?.candidate);
      const removed = [...record.removedNodes].map((node) => describe(node, true)).filter((row) => row?.candidate);
      const target = describe(record.target, !record.target?.isConnected);
      if (added.length || removed.length || target?.candidate) {
        const event = { event_id: 'early-' + (++state.sequence),
          elapsed_ms: Math.round(performance.now() - state.navigation_start_ms), type: record.type,
          attribute: record.attributeName || null, target, added, removed };
        state.events.push(event);
        try {
          const pending = Promise.resolve(window.__designDnaAutonomousEarlyCallback?.(event));
          state.pending.push(pending);
        } catch { /* The raw callback-time record remains and the gate will fail it without a frame. */ }
      }
    }
  };
  state.roots = () => {
    const output = [document];
    for (let index = 0; index < output.length; index += 1) {
      output[index].querySelectorAll?.('*').forEach((element) => { if (element.shadowRoot && !output.includes(element.shadowRoot)) output.push(element.shadowRoot); });
      if (output[index].nodeType === 9) (output[index].defaultView.__designDnaCapturedShadowRoots || [])
        .forEach((item) => { if (item.root && !output.includes(item.root)) output.push(item.root); });
    }
    return output;
  };
  state.observe = () => state.roots().forEach((root) => {
    if (state.observers.has(root)) return;
    const observer = new MutationObserver((records) => state.ingest(records));
    observer.observe(root, { subtree: true, childList: true, attributes: true, attributeOldValue: true,
      attributeFilter: ['class','style','hidden','aria-hidden','aria-modal','aria-disabled','inert','open'] });
    state.observers.set(root, observer);
    if (root === document) state.observer = observer;
  });
  state.original_attach_shadow = Element.prototype.attachShadow;
  state.attach_shadow_wrapper = function(init) {
    const root = state.original_attach_shadow.call(this, init);
    // Attach the observer before the caller receives the new root.  A
    // synchronous add/remove inside a closed root is otherwise invisible even
    // to a zero-delay microtask.
    state.observe();
    return root;
  };
  Element.prototype.attachShadow = state.attach_shadow_wrapper;
  state.observe();
  window.__designDnaAutonomousEarlyWatch = state;
})()`;

// The long watcher is attached before this drain runs.  That ordering leaves
// no event window between first-visit collection and durable monitoring, while
// awaiting exposed-binding work makes a missing callback-time frame a visible
// evidence failure rather than a race that looks clean.
export const AUTONOMOUS_EARLY_DRAIN = `(async () => {
  const state = window.__designDnaAutonomousEarlyWatch || null;
  if (!state) return { navigation_start_ms: null, events: [] };
  try { state.observe?.(); state.observers?.forEach((observer) => state.ingest?.(observer.takeRecords?.() || [])); } catch { /* raw events already retained */ }
  state.observers?.forEach((observer) => observer.disconnect());
  if (state.attach_shadow_wrapper && Element.prototype.attachShadow === state.attach_shadow_wrapper) Element.prototype.attachShadow = state.original_attach_shadow;
  await Promise.allSettled(state.pending || []);
  return { navigation_start_ms: state.navigation_start_ms, events: state.events.splice(0, state.events.length) };
})()`;

export const AUTONOMOUS_MONITOR_START = `(() => {
  const blocked_frames = [];
  const roots = () => {
    const output = [document];
    for (let index = 0; index < output.length; index += 1) {
      output[index].querySelectorAll?.('*').forEach((element) => { if (element.shadowRoot && !output.includes(element.shadowRoot)) output.push(element.shadowRoot); });
      output[index].querySelectorAll?.('iframe').forEach((frame) => {
        try { if (frame.contentDocument && !output.includes(frame.contentDocument)) output.push(frame.contentDocument); else if (!frame.contentDocument) throw new Error('no same-origin document'); }
        catch { const box = frame.getBoundingClientRect(); if (box.width > 1 && box.height > 1) blocked_frames.push({ src: frame.src || null, width: Math.round(box.width), height: Math.round(box.height) }); }
      });
      if (output[index].nodeType === 9) (output[index].defaultView.__designDnaCapturedShadowRoots || [])
        .forEach((item) => { if (item.root && !output.includes(item.root)) output.push(item.root); });
    }
    return output;
  };
  let sequence = 0;
  // Audit identity must never be written into the page.  A build can observe
  // attributes, and an inspector-created data-* marker can itself change its
  // behavior or become counterfeit proof.  This identity exists only in the
  // monitor closure.
  const surfaceIds = new WeakMap();
  const rootIds = new WeakMap();
  let rootSequence = 0;
  const rootScope = (root) => {
    let value = rootIds.get(root);
    if (!value) { value = String(++rootSequence); rootIds.set(root, value); }
    return (root.nodeType === 9 ? 'frame' : 'shadow') + ':' + value;
  };
  const surfaceId = (element) => {
    let value = surfaceIds.get(element);
    if (!value) { value = String(++sequence); surfaceIds.set(element, value); }
    return value;
  };
  const visible = (element) => {
    const style = getComputedStyle(element), box = element.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && box.width > 1 && box.height > 1;
  };
  const surfaceKind = (element, disconnected = false) => {
    if (!element || element.nodeType !== 1) return { relevant: false, lexical: false, geometric: false };
    const lexical = element.matches('[role="dialog"],dialog,[aria-modal="true"],[data-ff-el="modal"],[class*="modal" i],[class*="dialog" i],[class*="overlay" i],[class*="drawer" i],[class*="toast" i],[class*="popup" i],[class*="newsletter" i],[class*="interstitial" i],[class*="survey" i],[class*="gate" i],[class*="paywall" i],[id*="modal" i],[id*="dialog" i],[id*="overlay" i],[id*="drawer" i],[id*="toast" i],[id*="popup" i],[id*="newsletter" i],[id*="interstitial" i],[id*="survey" i],[id*="gate" i],[id*="paywall" i]');
    if (disconnected || !element.isConnected) {
      const inline = String(element.getAttribute('style') || '');
      const geometric = /position\\s*:\\s*(?:fixed|sticky)/i.test(inline)
        && /(?:inset|width|height)\\s*:/i.test(inline);
      return { relevant: lexical || geometric, lexical, geometric };
    }
    const style = getComputedStyle(element), box = element.getBoundingClientRect();
    const view = element.ownerDocument?.defaultView || window;
    const geometric = style.position === 'fixed' && Number(style.zIndex || 0) > 0
      && box.width >= view.innerWidth * .5 && box.height >= view.innerHeight * .35;
    return { relevant: lexical || geometric, lexical, geometric };
  };
  const relevant = (element) => surfaceKind(element).relevant;
  const tokens = (value) => String(value || '').split(/[\\s,]+/).filter(Boolean).sort();
  const accessibleName = (element) => {
    const labelledBy = String(element.getAttribute('aria-labelledby') || '').split(/\\s+/).filter(Boolean)
      .map((id) => element.ownerDocument.getElementById(id)?.textContent || '').join(' ').trim();
    const heading = [...element.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')]
      .map((candidate) => (candidate.getAttribute('aria-label') || candidate.textContent || '').trim()).find(Boolean) || '';
    return (element.getAttribute('aria-label') || labelledBy || element.getAttribute('title') || heading || element.textContent || '')
      .replace(/\\s+/g, ' ').trim().slice(0, 240);
  };
  const describe = (element, scope) => {
    const style = getComputedStyle(element), box = element.getBoundingClientRect();
    const classes = String(element.getAttribute('class') || '').trim().split(/\\s+/).filter(Boolean).sort();
    const declared = [...new Set([element.getAttribute('data-design-dna-state'), ...tokens(element.getAttribute('data-design-dna-states'))].filter(Boolean))].sort();
    const name = accessibleName(element);
    const role = (element.getAttribute('role') || element.tagName.toLowerCase()).toLowerCase();
    const point = { x: Math.round(box.left + box.width / 2), y: Math.round(box.top + box.height / 2) };
    const view = element.ownerDocument?.defaultView || window;
    const hit = point.x >= 0 && point.y >= 0 && point.x < view.innerWidth && point.y < view.innerHeight
      ? element.ownerDocument.elementFromPoint(point.x, point.y) : null;
    const composedPath = (node) => {
      const output = [];
      let cursor = node;
      while (cursor) { output.push(cursor); const root = cursor.getRootNode?.(); cursor = cursor.parentElement || root?.host || null; }
      return output;
    };
    const hitTarget = Boolean(hit && (composedPath(element).includes(hit) || composedPath(hit).includes(element)));
    return { key: scope + ':' + surfaceId(element),
      tag: element.tagName.toLowerCase(), role: element.getAttribute('role') || null, id: element.id || null,
      classes, class_signature: classes, accessible_name: name, text: name,
      semantic_key: role + '|' + name.toLowerCase(),
      component_keys: ['tag:' + element.tagName.toLowerCase(), ...(element.getAttribute('role') ? ['role:' + role] : []), ...classes.map((value) => 'class:' + encodeURIComponent(value))].sort(),
      actionability: { center: point, hit_target: hitTarget, pointer_events: style.pointerEvents,
        inert: element.inert === true || element.hasAttribute('inert') },
      declared_state_ids: declared, state_driver: element.getAttribute('data-design-dna-state-driver') || null,
      signature: JSON.stringify({ display: style.display, visibility: style.visibility, opacity: style.opacity,
        position: style.position, z_index: style.zIndex, pointer_events: style.pointerEvents,
        inert: element.inert === true || element.hasAttribute('inert'), aria_hidden: element.getAttribute('aria-hidden'),
        aria_modal: element.getAttribute('aria-modal'), aria_expanded: element.getAttribute('aria-expanded'),
        aria_pressed: element.getAttribute('aria-pressed'), aria_busy: element.getAttribute('aria-busy'),
        aria_disabled: element.getAttribute('aria-disabled'), transform: style.transform, filter: style.filter,
        clip_path: style.clipPath, background_color: style.backgroundColor, background_image: style.backgroundImage,
        content: style.content, hit_target: hitTarget, left: Math.round(box.left), top: Math.round(box.top),
        width: Math.round(box.width), height: Math.round(box.height) }) };
  };
  const snapshot = () => {
    const surfaces = [];
    for (const root of roots()) for (const element of root.querySelectorAll('*')) {
      if (relevant(element) && visible(element)) surfaces.push(describe(element, rootScope(root)));
      for (const pseudo of ['::before','::after']) {
        const style = getComputedStyle(element, pseudo), box = element.getBoundingClientRect();
        const paints = String(style.content || '') !== 'none' && String(style.content || '') !== 'normal' || style.backgroundImage !== 'none' || style.backgroundColor !== 'rgba(0, 0, 0, 0)';
        const pseudoWidth = Math.max(box.width, Number.parseFloat(style.width) || 0), pseudoHeight = Math.max(box.height, Number.parseFloat(style.height) || 0);
        const view = element.ownerDocument?.defaultView || window;
        if (!paints || style.position !== 'fixed' || Number(style.opacity) <= 0 || pseudoWidth < view.innerWidth * .5 || pseudoHeight < view.innerHeight * .35) continue;
        const owner = describe(element, rootScope(root));
        surfaces.push({ ...owner, key: owner.key + ':' + pseudo, pseudo, signature: owner.signature + '|' + pseudo + '|' + style.opacity + '|' + style.display });
      }
    }
    const animations = [], seenAnimations = new Set();
    for (const root of roots()) for (const animation of root.getAnimations?.({ subtree: true }) || []) {
      if (seenAnimations.has(animation)) continue;
      seenAnimations.add(animation);
      const target = animation.effect?.target;
      const timing = animation.effect?.getComputedTiming?.() || {};
      const kind = surfaceKind(target);
      if (animation.playState === 'running' && kind.relevant) {
        const targetSurface = describe(target, rootScope(target.getRootNode?.() || root));
        animations.push({ target: targetSurface, current_time: Number(animation.currentTime || 0), end_time: Number(timing.endTime || 0),
          iterations: Number(timing.iterations), play_state: animation.playState,
          pseudo_element: animation.effect?.pseudoElement || null });
      }
    }
    return { at_ms: Math.round(performance.now()), surfaces: surfaces.sort((a,b) => a.key.localeCompare(b.key)), animations,
      blocked_frames: [...new Map(blocked_frames.map((frame) => [JSON.stringify(frame), frame])).values()] };
  };
  const mutations = [], animation_events = [], observers = new Map(), animationListeners = new Map();
  const raw = (node, disconnected = false) => {
    if (node?.nodeType !== 1) return null;
    const kind = surfaceKind(node, disconnected);
    const class_text = String(node.getAttribute('class') || '');
    const box = !disconnected && node.isConnected ? node.getBoundingClientRect() : null;
    const classes = class_text.trim().split(/\\s+/).filter(Boolean).sort();
    const name = accessibleName(node);
    const role = (node.getAttribute('role') || node.tagName.toLowerCase()).toLowerCase();
    return { tag: node.tagName.toLowerCase(), id: node.id || null, role: node.getAttribute('role') || null,
      classes, class_signature: classes, accessible_name: name,
      semantic_key: role + '|' + name.toLowerCase(),
      component_keys: ['tag:' + node.tagName.toLowerCase(), ...(node.getAttribute('role') ? ['role:' + role] : []), ...classes.map((value) => 'class:' + encodeURIComponent(value))].sort(),
      aria_modal: node.getAttribute('aria-modal'),
      candidate: kind.relevant, lexical_surface_signal: kind.lexical, geometric_surface_signal: kind.geometric,
      connected: node.isConnected,
      rect: box ? { left: Math.round(box.left), top: Math.round(box.top), width: Math.round(box.width), height: Math.round(box.height) } : null,
      state_ids: [node.getAttribute('data-design-dna-state'), ...tokens(node.getAttribute('data-design-dna-states'))].filter(Boolean).sort() };
  };
  const animationListener = (event) => {
    const kind = surfaceKind(event.target);
    const pseudo = event.pseudoElement || null;
    if (!kind.relevant && !pseudo) return;
    const target = kind.relevant ? describe(event.target, rootScope(event.target.getRootNode?.() || document)) : raw(event.target);
    animation_events.push({ at_ms: Math.round(performance.now()), type: event.type, target, pseudo_element: pseudo,
      candidate: Boolean(kind.relevant || pseudo) });
  };
  const animationTypes = ['animationstart','animationend','animationcancel','transitionrun','transitionstart','transitionend','transitioncancel'];
  const observe = () => roots().forEach((root) => {
    if (observers.has(root)) return;
    const observer = new MutationObserver((records) => {
      const changes = [];
      for (const record of records) {
        const target = raw(record.target, !record.target?.isConnected);
        changes.push({ type: record.type,
          attribute: record.attributeName || null, added: record.addedNodes.length, removed: record.removedNodes.length,
          old_value: record.oldValue ?? null,
          new_value: record.type === 'attributes' && record.target?.getAttribute ? record.target.getAttribute(record.attributeName) : null,
          target,
          target_tag: record.target?.tagName?.toLowerCase?.() || null,
          added_nodes: [...record.addedNodes].map((node) => raw(node, !node.isConnected)).filter(Boolean),
          removed_nodes: [...record.removedNodes].map((node) => raw(node, true)).filter(Boolean) });
      }
      if (changes.length) mutations.push({ at_ms: Math.round(performance.now()), changes, surfaces: snapshot().surfaces });
    });
    observer.observe(root, { subtree: true, childList: true, attributes: true, attributeOldValue: true, characterData: true, characterDataOldValue: true,
      attributeFilter: ['class','style','hidden','aria-hidden','aria-expanded','aria-pressed','aria-busy','aria-disabled','aria-modal','inert','open','data-state','data-design-dna-state','data-design-dna-states'] });
    observers.set(root, observer);
    for (const type of animationTypes) root.addEventListener?.(type, animationListener, true);
    animationListeners.set(root, true);
  });
  observe();
  const originalAttachShadow = Element.prototype.attachShadow;
  const monitorAttachShadow = function(init) {
    const root = originalAttachShadow.call(this, init);
    // The watcher must own the first synchronous mutation inside a newly
    // attached closed root, not wait for its next 50ms sweep.
    observe();
    return root;
  };
  Element.prototype.attachShadow = monitorAttachShadow;
  const initial = snapshot();
  const animation_samples = [];
  const interval = setInterval(() => { observe(); animation_samples.push(snapshot()); }, ${AUTONOMOUS_MONITOR_SAMPLE_MS});
  window.__designDnaAutonomousMonitor = {
    initial,
    drain() { observe(); const current = snapshot(); const batch = mutations.splice(0, mutations.length); return { current, mutations: batch }; },
    stop() { clearInterval(interval); observe(); const final = snapshot(); const tail = mutations.splice(0, mutations.length); observers.forEach((observer) => observer.disconnect()); animationListeners.forEach((_value, root) => { for (const type of animationTypes) root.removeEventListener?.(type, animationListener, true); }); if (Element.prototype.attachShadow === monitorAttachShadow) Element.prototype.attachShadow = originalAttachShadow; return { initial, final, mutations: tail, animation_samples, animation_events }; },
  };
  return initial;
})()`;

export const AUTONOMOUS_MONITOR_DRAIN = `(() => window.__designDnaAutonomousMonitor?.drain?.() || null)()`;
export const AUTONOMOUS_MONITOR_STOP = `(() => { const monitor = window.__designDnaAutonomousMonitor; delete window.__designDnaAutonomousMonitor; return monitor?.stop?.() || null; })()`;

export function autonomousSurfaceHasSourceBinding(surface, state, sourceState, buildApplication = null) {
  const sourceEvidence = sourceState?.trigger_evidence;
  const sourceFrames = sourceState?.evidence_frames;
  const buildEvidence = buildApplication?.trigger_evidence;
  const sourceTarget = sourceEvidence?.target_identity?.settled;
  const sourceRole = typeof sourceTarget?.role === 'string' ? sourceTarget.role.toLowerCase() : null;
  const surfaceRole = typeof surface?.role === 'string' ? surface.role.toLowerCase() : surface?.tag?.toLowerCase?.() || null;
  const sourceName = typeof sourceTarget?.accessible_name === 'string' ? sourceTarget.accessible_name.trim().toLowerCase() : null;
  const surfaceName = typeof surface?.accessible_name === 'string' ? surface.accessible_name.trim().toLowerCase() : null;
  const sourceSemantic = typeof sourceTarget?.semantic_key === 'string' ? sourceTarget.semantic_key.trim().toLowerCase() : null;
  const surfaceSemantic = typeof surface?.semantic_key === 'string' ? surface.semantic_key.trim().toLowerCase() : null;
  return surface?.phase === 'post-trigger'
    && isSourceAmbientMapping(state, sourceState)
    && sourceEvidence?.appearance_observed === true
    && sourceEvidence?.target === sourceState.trigger.target
    && sourceTarget && typeof sourceTarget.tag === 'string' && sourceRole && sourceName && sourceSemantic
    && surface?.tag === sourceTarget.tag.toLowerCase() && surfaceRole === sourceRole
    && surfaceName === sourceName && surfaceSemantic === sourceSemantic
    && sourceFrames?.before && sourceFrames?.appearance && sourceFrames?.settled
    && buildEvidence?.type === 'programmatic'
    && buildEvidence?.settled === true
    && (buildEvidence?.changed_properties?.length > 0 || buildApplication?.navigation);
}

export function autonomousDwellMs(sourceState, recordingFloorMs = REFERENCE_RECORDING_DWELL_MS) {
  const sourceWait = Number(sourceState?.trigger?.type === 'ambient' ? sourceState.trigger.wait_ms : 0);
  return Math.max(recordingFloorMs, Number.isFinite(sourceWait) ? sourceWait : 0);
}

function sourceRecordingFloor(route, viewportName) {
  const recording = route.__sourceRecording;
  const profile = recording?.profile_recordings?.[viewportName];
  if (!recording || !regularFile(recording.file) || !regularFile(recording.ledger_file) ||
      !Number.isInteger(recording.minimum_duration_ms) || recording.minimum_duration_ms < REFERENCE_RECORDING_DWELL_MS ||
      !profile || profile.duration_ms < recording.minimum_duration_ms || !Number.isFinite(profile.fps) || profile.fps < 15 ||
      !Number.isInteger(profile.frame_count) || profile.frame_count < Math.ceil(profile.duration_ms / 1000 * profile.fps)) {
    throw new Error(`Route ${route.key} lacks a prevalidated exact source recording and artifact ledger for autonomous dwell.`);
  }
  return { file: recording.file, ledger_file: recording.ledger_file, sha256: recording.sha256,
    ledger_sha256: recording.ledger_sha256, state_contract: recording.state_contract,
    minimum_duration_ms: recording.minimum_duration_ms, profile: viewportName,
    duration_ms: profile.duration_ms, fps: profile.fps, frame_count: profile.frame_count };
}

function parseFrameRate(value) {
  if (typeof value !== 'string' || !/^\d+(?:\.\d+)?(?:\/\d+(?:\.\d+)?)?$/.test(value)) return null;
  const [numerator, denominator = '1'] = value.split('/').map(Number);
  const rate = numerator / denominator;
  return Number.isFinite(rate) && rate > 0 ? rate : null;
}

function probeContinuousVisualRecording(file) {
  let payload;
  try {
    payload = JSON.parse(execFileSync('ffprobe', [
      '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,avg_frame_rate,width,height',
      '-of', 'json', file,
    ], { encoding: 'utf8', windowsHide: true }));
  } catch (error) {
    throw new Error(`continuous build visual recording cannot be ffprobed: ${String(error?.message || error).slice(0, 260)}`);
  }
  const stream = (payload?.streams || []).find((item) => item?.codec_type === 'video');
  const durationSeconds = Number(payload?.format?.duration);
  const fps = parseFrameRate(stream?.avg_frame_rate);
  if (!stream || !Number.isFinite(durationSeconds) || durationSeconds <= 0 || !fps ||
      !Number.isInteger(Number(stream.width)) || !Number.isInteger(Number(stream.height))) {
    throw new Error('continuous build visual recording lacks a measurable video stream, duration, frame rate, or dimensions.');
  }
  return { duration_ms: Math.floor(durationSeconds * 1000), fps,
    width: Number(stream.width), height: Number(stream.height) };
}

async function observeAutonomousBuild(page, route, state, viewportName, captureEvidence, options = {}) {
  const sourceState = route.__observation?.states_by_viewport?.[viewportName]?.[state.mapped_reference_state_id] || null;
  const recording = sourceRecordingFloor(route, viewportName);
  const dwell_ms = autonomousDwellMs(sourceState, recording.duration_ms);
  const drainEarlyWatches = async () => Promise.all(page.frames().map(async (frame) =>
    frame.evaluate(AUTONOMOUS_EARLY_DRAIN).catch(() => ({ navigation_start_ms: null, events: [] }))));
  // Attach the durable monitor before draining first-visit watches.  Both
  // observer generations overlap through this handoff, and raw callback
  // records live in the host even if an iframe detaches before a later scan.
  options.earlyPhase && (options.earlyPhase.value = 'pre-trigger');
  const initial = await page.evaluate(AUTONOMOUS_MONITOR_START);
  const initialEarlyReports = await drainEarlyWatches();
  const navigation_start_ms = initialEarlyReports.find((report) => Number.isInteger(report?.navigation_start_ms))?.navigation_start_ms
    ?? initial?.at_ms ?? null;
  const before = await captureEvidence('autonomous-watch-pre-trigger', page);
  const hostNow = () => Number(process.hrtime.bigint() / 1_000_000n);
  const host_started_monotonic_ms = hostNow();
  const trigger_started_monotonic_ms = hostNow();
  options.earlyPhase && (options.earlyPhase.value = 'post-trigger');
  const state_application = await applyManifestState(page, state);
  const post_trigger = await page.evaluate(AUTONOMOUS_MONITOR_DRAIN);
  const appearance = await captureEvidence('autonomous-watch-post-trigger', page);
  const batches = [];
  const visual_samples = [];
  let priorEventEvidence = appearance;
  const dwell_started_monotonic_ms = hostNow();
  while (hostNow() - dwell_started_monotonic_ms < dwell_ms) {
    await page.waitForTimeout(Math.min(AUTONOMOUS_MONITOR_SAMPLE_MS, Math.max(1, dwell_ms - (hostNow() - dwell_started_monotonic_ms))));
    const sampleHostMonotonicMs = hostNow();
    const batch = await page.evaluate(AUTONOMOUS_MONITOR_DRAIN);
    visual_samples.push({ at_ms: batch?.current?.at_ms ?? null, host_monotonic_ms: sampleHostMonotonicMs });
    if (!batch) continue;
    if ((batch.mutations || []).length) {
      const afterEvidence = await captureEvidence(`autonomous-watch-mutation-${batches.length + 1}`, page);
      batches.push({ ...batch, evidence: { before: priorEventEvidence, callback: afterEvidence, after: afterEvidence } });
      priorEventEvidence = afterEvidence;
    }
  }
  const stopped = await page.evaluate(AUTONOMOUS_MONITOR_STOP);
  const host_finished_monotonic_ms = hostNow();
  const after = await captureEvidence('autonomous-watch-after', page);
  await drainEarlyWatches();
  const dwellSampleTimes = (stopped?.animation_samples || []).map((sample) => sample.at_ms)
    .filter((value) => Number.isInteger(value));
  const sampleGapFailures = [];
  const cadenceLimit = AUTONOMOUS_MONITOR_SAMPLE_MS * 2;
  const dwellPageStart = post_trigger?.current?.at_ms;
  const dwellPageEnd = stopped?.final?.at_ms;
  if (!Number.isInteger(dwellPageStart) || !Number.isInteger(dwellPageEnd) || dwellPageEnd < dwellPageStart) {
    sampleGapFailures.push({ kind: 'invalid-dwell-page-clock' });
  } else {
    const inDwell = dwellSampleTimes.filter((value) => value >= dwellPageStart && value <= dwellPageEnd);
    if (!inDwell.length || inDwell[0] - dwellPageStart > cadenceLimit || dwellPageEnd - inDwell.at(-1) > cadenceLimit) {
      sampleGapFailures.push({ kind: 'dwell-edge-gap', first_at_ms: inDwell[0] ?? null, last_at_ms: inDwell.at(-1) ?? null });
    }
    for (let index = 1; index < inDwell.length; index += 1) if (inDwell[index] - inDwell[index - 1] > cadenceLimit) {
      sampleGapFailures.push({ kind: 'sample-gap', before_at_ms: inDwell[index - 1], after_at_ms: inDwell[index] });
    }
  }
  const visualPageTimes = visual_samples.map((sample) => sample.at_ms).filter((value) => Number.isInteger(value));
  const visualHostTimes = visual_samples.map((sample) => sample.host_monotonic_ms).filter((value) => Number.isInteger(value));
  const sourceCoverageMinimum = Math.max(1, Math.ceil(dwell_ms / Math.ceil(1000 / recording.fps)) - 1);
  if (dwellSampleTimes.length < sourceCoverageMinimum || visual_samples.length < sourceCoverageMinimum) {
    sampleGapFailures.push({ kind: 'source-fps-coverage-shortfall', required_samples: sourceCoverageMinimum,
      animation_samples: dwellSampleTimes.length, visual_samples: visual_samples.length });
  }
  if (visualPageTimes.length !== visual_samples.length || visualHostTimes.length !== visual_samples.length) {
    sampleGapFailures.push({ kind: 'visual-sample-clock-incomplete' });
  } else {
    if (!visualPageTimes.length || visualPageTimes[0] - dwellPageStart > cadenceLimit || dwellPageEnd - visualPageTimes.at(-1) > cadenceLimit ||
        visualHostTimes[0] - dwell_started_monotonic_ms > cadenceLimit || host_finished_monotonic_ms - visualHostTimes.at(-1) > cadenceLimit) {
      sampleGapFailures.push({ kind: 'visual-dwell-edge-gap' });
    }
    for (let index = 1; index < visualPageTimes.length; index += 1) if (
      visualPageTimes[index] <= visualPageTimes[index - 1] || visualHostTimes[index] <= visualHostTimes[index - 1] ||
      visualPageTimes[index] - visualPageTimes[index - 1] > cadenceLimit || visualHostTimes[index] - visualHostTimes[index - 1] > cadenceLimit
    ) sampleGapFailures.push({ kind: 'visual-sample-gap', before_at_ms: visualPageTimes[index - 1], after_at_ms: visualPageTimes[index] });
  }
  const startSurfaces = new Map((initial?.surfaces || []).map((surface) => [surface.key, surface]));
  const observedSnapshots = [
    { ...(post_trigger?.current || {}), phase: 'post-trigger' },
    ...(batches.map((batch) => ({ ...(batch.current || {}), phase: 'dwell' }))),
    ...((stopped?.animation_samples || []).map((sample) => ({ ...sample, phase: 'dwell-sample' }))),
    ...((stopped?.mutations || []).map((mutation) => ({ surfaces: mutation.surfaces || [] }))),
    { ...(stopped?.final || {}), phase: 'dwell-end' },
  ];
  const newSurfaceMap = new Map(), stateDiffMap = new Map();
  for (const snapshot of observedSnapshots) for (const surface of snapshot.surfaces || []) {
    const beforeSurface = startSurfaces.get(surface.key);
    const phased = { ...surface, phase: snapshot.phase || 'mutation' };
    if (!beforeSurface && !newSurfaceMap.has(phased.key)) newSurfaceMap.set(phased.key, phased);
    else if (beforeSurface.signature !== phased.signature) stateDiffMap.set(phased.key + '|' + phased.signature, phased);
  }
  const new_surfaces = [...newSurfaceMap.values()].sort((left, right) => left.key.localeCompare(right.key));
  const state_diffs = [...stateDiffMap.values()].sort((left, right) => left.key.localeCompare(right.key));
  const earlyEvents = (options.earlyRecords || []).map((record) => {
    const phase = record.phase || 'pre-navigation';
    const preEvent = phase === 'pre-navigation' ? options.preNavigationEvidence : before;
    const postEvent = phase === 'pre-navigation' || phase === 'pre-trigger' ? appearance : after;
    return { ...(record.event || {}), event_id: record.event_id, frame_identity: record.frame_identity,
      frame_url: record.frame_url, phase, evidence: { before: preEvent, callback: record.callback, after: postEvent } };
  });
  const transient_surfaces = [
    ...earlyEvents.flatMap((event, index) => [...(event.added || []), ...(event.removed || []), event.target]
      .filter((surface) => surface?.candidate).map((surface, offset) => ({ ...surface, key: `early-${index + 1}-${offset + 1}`,
        phase: event.phase, transient: true, frame_identity: event.frame_identity || null }))),
    ...[...(post_trigger?.mutations || []), ...batches.flatMap((batch) => batch.mutations || []), ...(stopped?.mutations || [])].flatMap((mutation, index) =>
      mutation.changes.flatMap((change, offset) => [
        ...(change.added_nodes || []), ...(change.removed_nodes || []),
        ...(change.type === 'attributes' && change.target?.candidate ? [change.target] : []),
      ].filter((surface) => surface?.candidate).map((surface, nested) => ({ ...surface,
        key: `mutation-${index + 1}-${offset + 1}-${nested + 1}`, phase: 'dwell', transient: true,
        mutation_kind: change.type, mutation_attribute: change.attribute || null })))),
  ];
  // No generic at-rest exemption exists. A source animation elsewhere cannot
  // authorize a build-side surface simply because it happened to be present
  // at the first sample; every candidate motion remains explicit evidence.
  const animation_events = (stopped?.animation_events || []).map((event, index) => ({ ...event,
      event_id: `animation-${index + 1}`, key: `animation-${index + 1}`, phase: 'dwell', transient: true,
      evidence: { before: appearance, callback: after, after } }));
  const waapi_events = (stopped?.animation_samples || []).flatMap((sample, sampleIndex) =>
    (sample.animations || [])
      .map((animation, animationIndex) => ({ event_id: `waapi-${sampleIndex + 1}-${animationIndex + 1}`,
        key: `waapi-${sampleIndex + 1}-${animationIndex + 1}`, kind: 'surface-waapi-active', elapsed_ms: sample.at_ms,
        surface: animation, phase: 'dwell', transient: true, evidence: { before: appearance, callback: after, after } })));
  const initialBlockedFrames = new Set((initial?.blocked_frames || []).map((frame) => JSON.stringify(frame)));
  const blocked_frame_surfaces = observedSnapshots.flatMap((snapshot, index) => (snapshot.blocked_frames || [])
    .filter((frame) => !initialBlockedFrames.has(JSON.stringify(frame)))
    .map((frame, frameIndex) => ({ key: `blocked-frame-${index + 1}-${frameIndex + 1}`, kind: 'uninspectable-cross-origin-frame',
      surface: frame, phase: snapshot.phase || 'dwell', transient: true })));
  const autonomous = [...new_surfaces, ...state_diffs, ...transient_surfaces,
    ...animation_events, ...waapi_events, ...blocked_frame_surfaces];
  const postTriggerSurfaces = [...new_surfaces, ...state_diffs].filter((surface) => surface.phase === 'post-trigger');
  const mappedSurface = postTriggerSurfaces.length === 1 &&
    autonomousSurfaceHasSourceBinding(postTriggerSurfaces[0], state, sourceState, state_application)
    ? postTriggerSurfaces[0] : null;
  const mappedSurfaceIdentity = (candidate) => {
    const surface = candidate?.target || candidate?.surface?.target || candidate?.surface || candidate;
    const phase = candidate?.phase || surface?.phase || null;
    if (!mappedSurface || !surface || !['post-trigger', 'dwell', 'dwell-sample', 'dwell-end'].includes(phase)) return false;
    if (surface === mappedSurface || surface.key === mappedSurface.key) return true;
    const role = typeof surface.role === 'string' ? surface.role.toLowerCase() : surface.tag?.toLowerCase?.() || null;
    const mappedRole = typeof mappedSurface.role === 'string' ? mappedSurface.role.toLowerCase() : mappedSurface.tag?.toLowerCase?.() || null;
    return surface.tag === mappedSurface.tag && role === mappedRole &&
      surface.semantic_key === mappedSurface.semantic_key &&
      surface.accessible_name === mappedSurface.accessible_name;
  };
  const requiresMappedSurface = sourceState?.trigger?.type === 'ambient';
  const unbound_surfaces = autonomous.filter((surface) => !mappedSurfaceIdentity(surface));
  const trigger_mutations = (post_trigger?.mutations || []).map((mutation, index) => ({ ...mutation,
    event_id: `trigger-${index + 1}`, evidence: { before, callback: appearance, after: appearance } }));
  const tail_mutations = (stopped?.mutations || []).map((mutation, index) => ({ ...mutation,
    event_id: `tail-${index + 1}`, evidence: { before: priorEventEvidence, callback: after, after } }));
  const mutationEvents = (groups, prefix, phase) => groups.flatMap((group, groupIndex) =>
    (group.mutations || [group]).flatMap((mutation, mutationIndex) => (mutation.changes || []).flatMap((change, changeIndex) => {
      const emitted = [];
      const emit = (kind, surface, suffix) => emitted.push({
        event_id: `${prefix}-${groupIndex + 1}-${mutationIndex + 1}-${changeIndex + 1}-${suffix}`,
        kind, elapsed_ms: Number.isInteger(mutation.at_ms) ? mutation.at_ms : 0,
        declared_ambient: mappedSurfaceIdentity({ ...surface, phase }), selector: null, surface,
        detail: { phase, mutation_event_id: group.event_id || null, attribute: change.attribute || null,
          old_value: change.old_value ?? null, new_value: change.new_value ?? null }, evidence: group.evidence,
      });
      if (change.type === 'attributes' && change.target?.candidate) emit('surface-attribute-mutation', change.target, 'attribute');
      (change.added_nodes || []).filter((surface) => surface?.candidate)
        .forEach((surface, index) => emit('surface-node-added', surface, `added-${index + 1}`));
      (change.removed_nodes || []).filter((surface) => surface?.candidate)
        .forEach((surface, index) => emit('surface-node-removed', surface, `removed-${index + 1}`));
      return emitted;
    })));
  const earlyEventsNormalized = earlyEvents.flatMap((event) => {
    const emitted = [];
    const emit = (kind, surface, suffix) => emitted.push({ event_id: `${event.event_id}-${suffix}`, kind,
      elapsed_ms: Number.isInteger(event.elapsed_ms) ? event.elapsed_ms : 0,
      declared_ambient: mappedSurfaceIdentity({ ...surface, phase: event.phase }), selector: null, surface,
      detail: { phase: event.phase, frame_identity: event.frame_identity || null, attribute: event.attribute || null }, evidence: event.evidence });
    if (event.type === 'attributes' && event.target?.candidate) emit('surface-attribute-mutation', event.target, 'attribute');
    (event.added || []).filter((surface) => surface?.candidate)
      .forEach((surface, index) => emit('surface-node-added', surface, `added-${index + 1}`));
    (event.removed || []).filter((surface) => surface?.candidate)
      .forEach((surface, index) => emit('surface-node-removed', surface, `removed-${index + 1}`));
    return emitted;
  });
  const normalizedEvents = [
    ...earlyEventsNormalized,
    ...mutationEvents(trigger_mutations, 'trigger', 'post-trigger'),
    ...mutationEvents(batches, 'batch', 'dwell'),
    ...mutationEvents(tail_mutations, 'tail', 'dwell-end'),
    ...animation_events.map((event) => ({ event_id: event.event_id, kind: 'surface-css-animation-event',
      elapsed_ms: event.at_ms, declared_ambient: mappedSurfaceIdentity({ ...event.target, phase: event.phase }), selector: null,
      surface: event.target, detail: { phase: event.phase, event_type: event.type, pseudo_element: event.pseudo_element || null }, evidence: event.evidence })),
    ...waapi_events.map((event) => ({ event_id: event.event_id, kind: event.kind, elapsed_ms: event.elapsed_ms,
      declared_ambient: mappedSurfaceIdentity({ ...(event.surface?.target || event.surface), phase: event.phase }), selector: null,
      surface: event.surface, detail: { phase: event.phase }, evidence: event.evidence })),
    ...[...new_surfaces, ...state_diffs].map((surface, index) => ({ event_id: `surface-${index + 1}`,
      kind: new_surfaces.includes(surface) ? 'autonomous-surface-appeared' : 'surface-state-updated',
      elapsed_ms: Number.isInteger(stopped?.final?.at_ms) ? stopped.final.at_ms : 0,
      declared_ambient: mappedSurfaceIdentity(surface), selector: null,
      surface, detail: { phase: surface.phase }, evidence: { before, callback: appearance, after } })),
    ...blocked_frame_surfaces.map((surface, index) => ({ event_id: `blocked-frame-${index + 1}`,
      kind: 'uninspectable-cross-origin-frame', elapsed_ms: Number.isInteger(stopped?.final?.at_ms) ? stopped.final.at_ms : 0,
      declared_ambient: false, selector: null, surface: surface.surface, detail: { phase: surface.phase },
      evidence: { before, callback: appearance, after } })),
  ];
  return { source_state_id: state.mapped_reference_state_id, source_trigger: sourceState?.trigger || null,
    source_state_binding: sourceState ? {
      id: state.mapped_reference_state_id, trigger: sourceState.trigger,
      trigger_evidence: sourceState.trigger_evidence, evidence_frames: sourceState.evidence_frames,
    } : null,
    source_recording: { file: path.basename(recording.file), sha256: recording.sha256,
      ledger_file: path.basename(recording.ledger_file), ledger_sha256: recording.ledger_sha256,
      state_contract: recording.state_contract, minimum_duration_ms: recording.minimum_duration_ms,
      profile: recording.profile, duration_ms: recording.duration_ms, fps: recording.fps, frame_count: recording.frame_count },
    viewport: { source_profile: viewportName, width: options.viewport?.width ?? null, height: options.viewport?.height ?? null },
    recording_grounded_dwell_ms: dwell_ms, sample_interval_ms: AUTONOMOUS_MONITOR_SAMPLE_MS, sample_gap_failures: sampleGapFailures,
    navigation_start_ms, host_started_monotonic_ms,
    trigger_started_monotonic_ms, dwell_started_monotonic_ms, host_finished_monotonic_ms,
    state_application, pre_trigger: initial, post_trigger: post_trigger?.current || null,
    initial, final: stopped?.final || null, trigger_mutations, mutation_batches: batches, tail_mutations,
    animation_samples: stopped?.animation_samples || [], visual_recording: null, visual_samples, animation_events, waapi_events, early_events: earlyEvents,
    events: normalizedEvents,
    new_surfaces, state_diffs, transient_surfaces, blocked_frame_surfaces, mapped_surface: mappedSurface, unbound_surfaces,
    evidence: { before, appearance, after }, complete: sampleGapFailures.length === 0 && unbound_surfaces.length === 0 && (!requiresMappedSurface || mappedSurface !== null) };
}

export async function runStateAutonomousAudit(browser, route, state, viewport, sourceProfile, captureEvidence, options = {}) {
  const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1,
    ...(options.video_dir ? { recordVideo: { dir: options.video_dir, size: { width: viewport.width, height: viewport.height } } } : {}) });
  await installDomInspection(context);
  const earlyRecords = [], earlyFrameIds = new WeakMap();
  let earlyFrameSequence = 0, earlyEventSequence = 0;
  const earlyPhase = { value: 'pre-navigation' };
  await context.exposeBinding('__designDnaAutonomousEarlyCallback', async (source, event) => {
    const frame = source.frame || null;
    let frameIdentity = frame ? earlyFrameIds.get(frame) : null;
    if (!frameIdentity) { frameIdentity = `frame-${++earlyFrameSequence}`; if (frame) earlyFrameIds.set(frame, frameIdentity); }
    const sourceEventId = typeof event?.event_id === 'string' ? event.event_id : `unidentified-${earlyEventSequence + 1}`;
    const record = { event_id: `early-${++earlyEventSequence}`, source_event_id: sourceEventId,
      event, frame_identity: frameIdentity, frame_url: frame?.url?.() || source.page?.url?.() || null,
      phase: earlyPhase.value, callback: null };
    earlyRecords.push(record);
    try { record.callback = source.page ? await captureEvidence(`autonomous-watch-${record.event_id}-callback`, source.page) : null; }
    catch { record.callback = null; }
  });
  await context.addInitScript(AUTONOMOUS_EARLY_INIT);
  const page = await context.newPage();
  const video = page.video();
  let navigation = null, watch = null;
  try {
    const preNavigationEvidence = await captureEvidence('autonomous-watch-pre-navigation', page);
    navigation = await navigateExact(page, route.url);
    await page.evaluate(() => document.fonts?.ready).catch(() => {});
    watch = await observeAutonomousBuild(page, route, state, sourceProfile,
      (label, evidencePage = page) => captureEvidence(label, evidencePage), { earlyRecords, earlyPhase, preNavigationEvidence, viewport });
  } finally { await context.close(); }
  if (!navigation || !watch) throw new Error(`Autonomous audit did not produce a result for ${route.key}/${sourceProfile}/${state.id}.`);
  if (!video || typeof options.persist_video !== 'function') {
    throw new Error(`Autonomous audit lacks a persisted continuous visual recording for ${route.key}/${sourceProfile}/${state.id}.`);
  }
  watch.visual_recording = await options.persist_video(video, route.key, viewport.name, state.id, viewport);

  // Target census actions run in a second exact context.  The continuous video
  // therefore proves only the settled route/state dwell and cannot be
  // contaminated by the census's intentionally mutating safe inputs.
  const censusContext = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
  await installDomInspection(censusContext);
  const censusPage = await censusContext.newPage();
  let target_census = null;
  try {
    await navigateExact(censusPage, route.url);
    await censusPage.evaluate(() => document.fonts?.ready).catch(() => {});
    const baselineApplication = await applyManifestState(censusPage, state);
    target_census = await captureInteractionCensus(censusPage, {
      profile: sourceProfile,
      pageUrl: route.url,
      authoredStates: route.states.map((item) => ({ ...item, url: route.url })),
      baselineState: { ...state, url: route.url },
      context: { phase: 'build-state-autonomous-watch', source_state_id: state.id, pass: 1, route_key: route.key },
      baselineApplication,
      plannedDeferredRoutes: options.planned_deferred_routes || [],
      captureEvidence: (label, evidencePage = censusPage) => captureEvidence(`target-census-${label}`, evidencePage),
    });
  } finally { await censusContext.close(); }
  if (!target_census) throw new Error(`Autonomous audit target census did not complete for ${route.key}/${sourceProfile}/${state.id}.`);
  return { navigation, watch, target_census };
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
  const implementationProject = path.dirname(path.dirname(path.resolve(manifest.__file)));
  const implementationBefore = snapshotImplementation(implementationProject);
  const visibleDecisionManifest = readVisibleDecisionManifest(manifest);
  if (firstScreen) manifest = firstScreenManifest(manifest, routeKeys);
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
  const interactionVideoDir = outFile ? path.resolve(`${outFile.replace(/\.json$/i, "")}-interaction-videos`) : null;
  const interactionVideoRelativeRoot = interactionVideoDir && outFile
    ? path.relative(path.dirname(path.resolve(outFile)), interactionVideoDir).split(path.sep).join("/") : null;
  for (const directory of [interactionFrameDir, interactionVideoDir]) {
    if (!directory) continue;
    if (fs.existsSync(directory) && fs.readdirSync(directory).length) {
      throw new Error(`Generated interaction artifact directory already contains evidence: ${directory}. Use a new --out path; stale frames/videos must never mix with this scan.`);
    }
    await mkdir(directory, { recursive: true });
  }
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
  const persistVideo = async (video, routeKey, viewportName, stateId, viewport) => {
    if (!interactionVideoDir || !interactionVideoRelativeRoot) {
      throw new Error('Continuous visual recordings require an explicit --out artifact path.');
    }
    const videoPath = await video.path();
    if (!regularFile(videoPath) || !pathWithin(videoPath, interactionVideoDir)) {
      throw new Error(`Continuous visual recording for ${routeKey}/${viewportName}/${stateId} is missing or outside the generated artifact directory.`);
    }
    const bytes = fs.readFileSync(videoPath);
    const measured = probeContinuousVisualRecording(videoPath);
    if (measured.width !== viewport.width || measured.height !== viewport.height) {
      throw new Error(`Continuous visual recording dimensions ${measured.width}x${measured.height} do not match ${routeKey}/${viewportName}/${stateId} ${viewport.width}x${viewport.height}.`);
    }
    return { file: `${interactionVideoRelativeRoot}/${path.basename(videoPath)}`,
      bytes: bytes.length, sha256: sha256(bytes), ...measured };
  };
  try {
    for (const viewport of manifest.viewports) {
      const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
      await installDomInspection(context);
      const selectedRoutes = routeKeys.length ? manifest.routes.filter((route) => routeKeys.includes(route.key)) : manifest.routes;
      for (const route of selectedRoutes) {
        const page = await context.newPage();
        await prepareRenderedFontDelivery(page);
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
        const stateInventory = await inferStateInventory(page, route.states);
        stateInventories.push({ route_key: route.key, viewport: viewport.name,
          discovery_scroll: discoveryScroll, ...stateInventory });
        const cleanNavigation = await navigateExact(page, route.url);
        navigations.push({ route_key: route.key, viewport: viewport.name, state_id: "rest", clean_after_inference: true, ...cleanNavigation });
        const orderedStates = [...route.states].sort((a, b) => Number(b.id === "rest") - Number(a.id === "rest"));
        for (const state of orderedStates) {
          const stateAudit = await runStateAutonomousAudit(browser, route, state, viewport, viewport.name,
            (label, evidencePage) => persistFrame(route.key, viewport.name, `${state.id}-${label}`, evidencePage),
            { video_dir: interactionVideoDir, persist_video: persistVideo,
              planned_deferred_routes: firstScreen ? manifest.__planned_routes.filter((item) => item.key !== route.key).map((item) => item.url) : [] });
          navigations.push({ route_key: route.key, viewport: viewport.name, state_id: state.id,
            autonomous_watch_first_visit: true, ...stateAudit.navigation });
          interactionCensuses.push({ route_key: route.key, viewport: viewport.name, state_id: state.id,
            ...stateAudit.target_census });
          if (state.id !== "rest") {
            const navigation = await navigateExact(page, route.url);
            navigations.push({ route_key: route.key, viewport: viewport.name, state_id: state.id, reload: 1, ...navigation });
            await page.waitForTimeout(300);
          }
          const extent = firstScreen ? firstScreenRegionAuthority(implementationProject, visibleDecisionManifest.payload,
            route.key, viewport.name, state.id, viewport.height) : null;
          const result = await captureState(page, state, firstScreen, extent);
          if (result.application?.navigation) navigations.push({ route_key: route.key, viewport: viewport.name,
            state_id: state.id, trigger_navigation: true, ...result.application.navigation });
          const snapshots = result.snapshots || [];
          if (firstScreen && result.scroll?.surfaces?.length) {
            // The measured runway was exercised above. Restore the exact
            // declared entry/state for first-screen QA instead of presenting
            // the terminal scroll position as the opening composition.
            const restored = await navigateExact(page, route.url);
            navigations.push({route_key: route.key, viewport: viewport.name, state_id: state.id,
              restored_after_primary_traversal: true, ...restored});
            await page.evaluate(() => document.fonts?.ready).catch(() => {});
            const restoredState = await applyManifestState(page, state);
            if (restoredState.navigation) navigations.push({route_key: route.key, viewport: viewport.name, state_id: state.id,
              restored_state_after_primary_traversal: true, ...restoredState.navigation});
          }
          const renderedQa = await renderedQaProbe(
            page,
            state,
            (label, evidencePage = page) => persistFrame(route.key, viewport.name, `${state.id}-${label}`, evidencePage),
          );
          const shortHeight = Math.min(viewport.height, 568);
          const shortViewport = { name: `${viewport.name}-short`, width: viewport.width, height: shortHeight };
          const shortAudit = await runStateAutonomousAudit(browser, route, state, shortViewport, viewport.name,
            (label, evidencePage) => persistFrame(route.key, shortViewport.name, `${state.id}-${label}`, evidencePage),
            { video_dir: interactionVideoDir, persist_video: persistVideo,
              planned_deferred_routes: firstScreen ? manifest.__planned_routes.filter((item) => item.key !== route.key).map((item) => item.url) : [] });
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
          renderedQa.short_height = { profile: `${viewport.name}-short`, width: viewport.width, height: shortHeight,
            autonomous_watch: shortAudit.watch, target_census: { ...shortAudit.target_census, state_id: state.id }, ...shortHeightQa };
          const scope = snapshots[0]?.implementation_scope || null;
          const firstScreenScopePassed = !firstScreen || snapshots.every((item) => firstScreenScopePass(item.implementation_scope, extent));
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
            autonomous_watch: stateAudit.watch,
            scroll_traversal: result.scroll,
            components: mergeComponents(snapshots.map((item) => item.components)),
            visible_decision_ids: [...new Set(snapshots.flatMap((item) => item.visible_decision_ids || []))].sort(),
            unsourced_visible_parts: [...new Set(snapshots.flatMap((item) => item.unsourced_visible_parts || []))].sort(),
            wrapper_inherited_visible_parts: snapshots.flatMap((item) => item.wrapper_inherited_visible_parts || []),
            decision_roots: mergeDecisionRootSamples(snapshots.map((item) => item.decision_roots || [])),
            decision_root_samples: snapshots.map((item) => item.decision_roots || []),
            media_inventory: snapshots.flatMap((item) => item.media_inventory || []),
            pseudo_inventory: snapshots.flatMap((item) => item.pseudo_inventory || []),
            links: [...new Set(snapshots.flatMap((item) => item.links || []))].sort(),
            inspection: snapshots.map((item) => item.inspection || null),
            font_delivery: {complete: snapshots.every((item) => item.font_delivery.complete),
              records: snapshots.flatMap((item) => item.font_delivery.records),
              findings: snapshots.flatMap((item) => item.font_delivery.findings)},
            implementation_scope: scope,
            scope_samples: snapshots.map((item) => item.implementation_scope),
            first_screen_scope_pass: firstScreenScopePassed,
            rendered_qa: renderedQa,
            pass: discoveryScroll.complete && stateInventory.complete && result.attempted > 0 && result.covered === result.attempted &&
              stateAudit.watch.complete === true && stateAudit.target_census.complete === true &&
              firstScreenScopePassed && snapshots.every((item) => item.inspection?.complete !== false) &&
              snapshots.every((item) => item.font_delivery.complete) &&
              snapshots.every((item) => (item.wrapper_inherited_visible_parts || []).length === 0) &&
              snapshots.every((item) => (item.unsourced_visible_parts || []).length === 0) &&
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
               shortHeightQa.accessibility.complete === true && shortAudit.watch.complete === true &&
               shortAudit.target_census.complete === true,
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
  const mediaUrl = (value, base) => {
    if (typeof value !== 'string' || !value) return null;
    const css = value.match(/url\(["']?([^"')]+)["']?\)/i);
    try { return new URL(css ? css[1] : value, base).href; } catch { return null; }
  };
  for (const check of checks) {
    const probe = (servedContent.probes || []).find((item) => item.route_key === check.route_key && item.viewport === check.viewport);
    const resources = probe?.resources || [];
    check.media_inventory = (check.media_inventory || []).map((item) => {
      const url = mediaUrl(item.source, check.url);
      const resource = resources.find((candidate) => candidate.url === url) || null;
      return { ...item, rendered_url: url,
        resource: resource ? { url: resource.url, sha256: resource.sha256, bytes: resource.bytes, resource_type: resource.resource_type } : null };
    });
    check.pseudo_inventory = (check.pseudo_inventory || []).map((item) => {
      const url = mediaUrl(item.background_source, check.url);
      const resource = resources.find((candidate) => candidate.url === url) || null;
      return { ...item, rendered_url: url,
        resource: resource ? { url: resource.url, sha256: resource.sha256, bytes: resource.bytes, resource_type: resource.resource_type } : null };
    });
  }
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
    const wide = cells.find((cell) => cell.viewport === "wide") || null;
    const narrow = cells.find((cell) => cell.viewport === "narrow") || null;
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
      const safelyBlocked = activation.some((input) => input.status === "blocked" && (input.disposition === "blocked-requires-safe-owner-handoff" ||
        firstScreen && input.disposition === "deferred-until-final-gate"));
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
        else if (firstScreen && input.status === "blocked" && input.disposition === "deferred-until-final-gate") resolution = "planned-route-pending-final";
        else if (input.status === "exercised" && finalUrl && manifestedUrls.has(normalizeHttpUrl(finalUrl))) resolution = "manifested-route";
        else if (input.status === "exercised" && stateId && manifestedStateIds.has(stateId)) resolution = "manifested-state";
        return { input_kind: input.input_kind, status: input.status, resolution,
          manifested_state_id: stateId, final_url: finalUrl, evidence: resolution === 'planned-route-pending-final'
            ? {planned_url: input.input_value, decision_id: input.decision_id, verified_arrival: false} : input.evidence || null };
      });
      const pathComplete = actions.length > 0 && actions.some((action) => action.resolution !== null);
      experiencePaths.push({ route_key: censusRecord.route_key, viewport: censusRecord.viewport, state_id: censusRecord.state_id,
        target_id: target.target_id, kind: target.kind, actions,
        missing: pathComplete ? [] : ["primary action has no manifested route/state or explicit blocked handoff"], complete: pathComplete });
      if (inputs.some((input) => input.input_kind === "focus") &&
          (!inputs.some((input) => input.input_kind === "focus" && input.status === "exercised") ||
           !inputs.some((input) => input.input_kind === "keyboard" && input.status === "exercised"))) {
        keyboardMissing.push({ target_id: target.target_id, reason: "focus-or-keyboard-path-not-exercised" });
      }
      for (const input of inputs.filter((item) => item.status === "blocked")) {
        if (input.disposition !== "blocked-requires-safe-owner-handoff" && !(firstScreen && input.disposition === 'deferred-until-final-gate')) {
          unresolvedBlocked.push({ target_id: target.target_id, input_kind: input.input_kind,
            reason: input.disposition || "blocked-without-current-safe-evidence" });
        }
      }
    }
    for (const group of censusRecord.repeat_classes || []) if (group.equivalent !== true) {
      semanticMismatches.push({ repeat_class: group.repeat_class, reason: "repeated-controls-have-non-equivalent-behavior" });
    }
    targetQaByProfile.set(`${censusRecord.route_key}|${censusRecord.viewport}|${censusRecord.state_id}`, {
      dead_controls: deadControls,
      blocked_handoffs: unresolvedBlocked,
      keyboard: { complete: keyboardMissing.length === 0, missing: keyboardMissing },
      semantic_equivalence: { complete: semanticMismatches.length === 0, mismatches: semanticMismatches },
    });
  }
  const renderedQaCells = checks.map((check) => {
    const profileKey = `${check.route_key}|${check.viewport}|${check.state_id}`;
    const targetProfileKey = `${check.route_key}|${check.viewport}|${check.state_id}`;
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
    const sourceProfile = check.viewport;
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
    (!firstScreen || (visibleDecisionManifest.payload.proof_isolation?.decision_ids || visibleDecisionManifest.payload.planned_decision_ids).includes(decision.decision_id)) &&
    (decision.bindings || []).some((binding) => selectedRoutes.some((route) => route.key === binding.route_key)));
  const implementedDecisionIds = [...new Set(checks.flatMap((check) => check.visible_decision_ids || []))].sort();
  const bindingCellFindings = [];
  const assetRoleFindings = [];
  const expectedRootBindingByCell = new Map();
  for (const decision of plannedDecisions) for (const binding of decision.bindings || []) {
    expectedRootBindingByCell.set(
      `${binding.route_key}|${binding.viewport}|${binding.state_id}|${decision.decision_id}`,
      { decision, binding },
    );
  }
  for (const decision of plannedDecisions) for (const binding of decision.bindings || []) {
    const check = checks.find((item) => item.route_key === binding.route_key && item.viewport === binding.viewport && item.state_id === binding.state_id);
    const base = { route_key: binding.route_key, viewport: binding.viewport, state_id: binding.state_id,
      decision_id: decision.decision_id, component_key: binding.component_key,
      source_reference_id: decision.source_mapping?.id || null };
    if (!check) {
      bindingCellFindings.push({ code: 'construction-binding-cell-missing', ...base,
        field: 'route_key/viewport/state_id', rerun: 'run gate.py --phase first-screen or --phase final against the authoritative route manifest' });
      continue;
    }
    if (!(check.visible_decision_ids || []).includes(decision.decision_id)) {
      bindingCellFindings.push({ code: 'construction-binding-not-rendered', ...base,
        field: 'data-design-dna-decision-id', rerun: 'add the exact decision id to the bound component and rerun scan_build_components.mjs' });
    }
    const roots = (check.decision_roots || []).filter((row) => row.decision_id === decision.decision_id).flatMap((row) => row.roots || []);
    if (roots.length !== 1 || roots[0]?.component_key !== binding.component_key ||
        roots[0]?.component_id !== decision.component_id || roots[0]?.direct !== true) {
      bindingCellFindings.push({ code: roots.length > 1 ? 'construction-decision-root-reused' : 'construction-binding-root-mismatch', ...base,
        field: 'component_key/data-design-dna-component', rerun: 'bind exactly one direct root whose data-design-dna-component equals the decision component_id; do not reuse a source marker across nav/footer/card descendants' });
    }
    const styleTuples = (decision.style_provenance?.tuples || []).filter((tuple) =>
      tuple.viewport === binding.viewport && tuple.state_id === binding.state_id &&
      tuple.source_state_id === binding.source_state?.id);
    for (const tuple of styleTuples) {
      if (roots.length !== 1 || roots[0]?.computed_style?.[tuple.property] !== tuple.build_value) {
        bindingCellFindings.push({ code: 'construction-style-tuple-mismatch', ...base,
          field: `${tuple.property} source=${tuple.source_value} build=${tuple.build_value}`,
          rerun: 'restore the exact source-bound component property value or reopen its selector/property tuple before rendering' });
      }
    }
    const asset = decision.asset_role_binding;
    if (asset) {
      const crop = asset.crop_by_viewport?.[binding.viewport] || asset.crop;
      const media = (check.media_inventory || []).filter((item) => item.decision_id === decision.decision_id &&
        item.asset_id === asset.asset_id && item.media_kind === asset.rendered_media_kind);
      if (!media.length || !media.some((item) => item.rendered_url === asset.rendered_url &&
        item.resource?.sha256 === asset.rendered_sha256 && item.resource?.bytes === asset.rendered_bytes &&
        item.resource?.resource_type === asset.resource_type && item.box?.width === crop?.width &&
        item.box?.height === crop?.height && item.object_fit === crop?.object_fit &&
        item.object_position === crop?.object_position &&
        ((asset.temporal_mode === 'moving' && item.media_kind === 'video' && item.temporal && item.temporal.ready_state >= 1) ||
          (asset.temporal_mode === 'audio' && item.media_kind === 'audio' && item.temporal) ||
          (asset.temporal_mode === 'still' && !item.temporal)))) {
        assetRoleFindings.push({ code: 'construction-asset-role-missing', ...base,
          asset_id: asset.asset_id, field: 'rendered URL/bytes/resource/crop/temporal media role',
          rerun: 'bind the exact served asset URL and bytes plus object-fit/object-position/box/temporal evidence to this source-matched media element' });
      }
    }
    const carrier = decision.dominant_behavior_carrier;
    if (carrier) {
      const interaction = interactionCells.find((item) => item.route_key === binding.route_key &&
        item.viewport === binding.viewport && item.state_id === binding.state_id);
      const sourceState = carrier.source_states?.[binding.viewport];
      const sourceTrigger = carrier.source_triggers?.[binding.viewport];
      const sourceEvents = carrier.source_event_ids?.[binding.viewport];
      const buildEvidence = interaction?.trigger_evidence;
      const targetMatches = (interaction?.target_components || []).filter((key) =>
        key === carrier.build_component_key || String(key).endsWith(`|${carrier.build_component_key}`));
      const outcomeObserved = Boolean(buildEvidence?.settled === true &&
        /^[0-9a-f]{64}$/.test(buildEvidence?.before_sha256 || '') &&
        /^[0-9a-f]{64}$/.test(buildEvidence?.after_sha256 || '') &&
        /^[0-9a-f]{64}$/.test(buildEvidence?.settled_sha256 || '') &&
        (Array.isArray(buildEvidence?.changed_properties) && buildEvidence.changed_properties.length || interaction?.trigger_navigation));
      if (!interaction || !interaction.complete || !sourceState || !sourceTrigger || !Array.isArray(sourceEvents) || !sourceEvents.length ||
          sourceState.id !== binding.source_state?.id || interaction.mapped_reference_state_id !== sourceState.id ||
          JSON.stringify(interaction.trigger) !== JSON.stringify(sourceTrigger) ||
          buildEvidence?.type !== sourceTrigger.type || buildEvidence?.target !== interaction.trigger?.target ||
          targetMatches.length !== 1 || !outcomeObserved) {
        bindingCellFindings.push({ code: 'construction-dominant-behavior-omitted', ...base,
          field: 'dominant_behavior_carrier target/trigger/state/outcome',
          rerun: 'implement one exact build carrier target with its mapped source state, trigger, recorded source event, and settled outcome at this viewport' });
      }
    }
  }
  for (const check of checks) {
    const prefix = `${check.route_key}|${check.viewport}|${check.state_id}|`;
    for (const row of check.decision_roots || []) {
      const expected = expectedRootBindingByCell.get(prefix + row.decision_id);
      const roots = row.roots || [];
      if (!expected) {
        bindingCellFindings.push({ code: 'construction-decision-root-unplanned',
          route_key: check.route_key, viewport: check.viewport, state_id: check.state_id,
          decision_id: row.decision_id, component_key: roots[0]?.component_key || null,
          source_reference_id: null, field: 'decision root',
          rerun: 'remove this direct marker or create an exact current-cell source binding before rendering it' });
      } else if (roots.length !== 1 || roots[0]?.component_key !== expected.binding.component_key ||
          roots[0]?.component_id !== expected.decision.component_id || roots[0]?.direct !== true) {
        bindingCellFindings.push({ code: 'construction-decision-root-extra-or-reused',
          route_key: check.route_key, viewport: check.viewport, state_id: check.state_id,
          decision_id: row.decision_id, component_key: roots.map((root) => root.component_key).join(','),
          source_reference_id: expected.decision.source_mapping?.id || null, field: 'direct root ownership',
          rerun: 'split every independently visible nav/footer/card descendant into its own direct source-bound decision ID' });
      }
    }
    for (const decisionId of check.visible_decision_ids || []) {
      if (!expectedRootBindingByCell.has(prefix + decisionId)) {
        bindingCellFindings.push({ code: 'construction-decision-id-out-of-cell',
          route_key: check.route_key, viewport: check.viewport, state_id: check.state_id,
          decision_id: decisionId, component_key: null, source_reference_id: null,
          field: 'route/state/viewport scope',
          rerun: 'remove this reused decision id or bind it to this exact manifest cell' });
      }
    }
    for (const media of check.media_inventory || []) {
      const matchingDecision = plannedDecisions.find((decision) => decision.decision_id === media.decision_id);
      const matchingAsset = matchingDecision?.asset_role_binding;
      if (!matchingAsset || media.asset_id !== matchingAsset.asset_id) {
        assetRoleFindings.push({ code: 'construction-rendered-media-unbound',
          route_key: check.route_key, viewport: check.viewport, state_id: check.state_id,
          decision_id: media.decision_id, component_key: media.component_key,
          asset_id: media.asset_id, source_reference_id: matchingDecision?.source_mapping?.id || null,
          field: 'asset_role_binding',
          rerun: 'every rendered image/video/audio/canvas/background medium needs one exact source-bound asset role, served URL, bytes, crop, and temporal mode' });
      }
    }
    for (const pseudo of check.pseudo_inventory || []) {
      const decision = plannedDecisions.find((item) => item.decision_id === pseudo.decision_id);
      const pseudoBindings = decision?.pseudo_bindings || [];
      const matches = pseudoBindings.filter((binding) => binding.pseudo === pseudo.pseudo &&
        binding.viewport === check.viewport && binding.state_id === check.state_id);
      if (!decision || !matches.length || !matches.every((binding) => pseudo.properties?.[binding.property] === binding.build_value)) {
        bindingCellFindings.push({ code: 'construction-pseudo-unbound-or-mismatched',
          route_key: check.route_key, viewport: check.viewport, state_id: check.state_id,
          decision_id: pseudo.decision_id, component_key: pseudo.component_key,
          source_reference_id: decision?.source_mapping?.id || null,
          field: `${pseudo.pseudo} pseudo style/media`,
          rerun: 'bind every painted pseudo-element to an exact source selector/property/value tuple or remove the ornament' });
      }
      if (pseudo.properties?.['background-image'] && pseudo.properties['background-image'] !== 'none') {
        const asset = decision?.asset_role_binding;
        if (!asset || pseudo.rendered_url !== asset.rendered_url || pseudo.resource?.sha256 !== asset.rendered_sha256 ||
            pseudo.resource?.bytes !== asset.rendered_bytes || pseudo.resource?.resource_type !== asset.resource_type) {
          assetRoleFindings.push({ code: 'construction-pseudo-media-unbound',
            route_key: check.route_key, viewport: check.viewport, state_id: check.state_id,
            decision_id: pseudo.decision_id, component_key: pseudo.component_key,
            asset_id: asset?.asset_id || null, source_reference_id: decision?.source_mapping?.id || null,
            field: `${pseudo.pseudo} background media URL/bytes`,
            rerun: 'bind pseudo background media to the exact source asset role and served bytes, or remove the pseudo ornament' });
        }
      }
    }
  }
  for (const disposition of visibleDecisionManifest.payload.source_state_dispositions || []) {
    if (disposition?.disposition !== 'omit') continue;
    const renderedCarrier = interactionCells.find((cell) =>
      cell.source_mapping?.id === disposition.source_reference_id &&
      cell.mapped_reference_state_id === disposition.source_state_id && cell.complete);
    if (renderedCarrier) {
      bindingCellFindings.push({ code: 'construction-omitted-source-state-rendered',
        route_key: renderedCarrier.route_key, viewport: renderedCarrier.viewport, state_id: renderedCarrier.state_id,
        decision_id: null, component_key: (renderedCarrier.target_components || []).join(','),
        source_reference_id: disposition.source_reference_id,
        field: `omitted source state ${disposition.source_state_id}`,
        rerun: 'change this disposition to transfer and bind its exact carrier, or remove the rendered state; prose cannot omit a carrier that the census observed' });
    }
  }
  if (firstScreen) {
    const isolation = visibleDecisionManifest.payload.proof_isolation || {};
    const regionId = isolation.region_component_id;
    const primaryRoute = isolation.primary_route_key;
    for (const check of checks.filter((item) => item.route_key === primaryRoute && item.state_id === 'rest')) {
      const regions = check.implementation_scope?.substantial_regions || [];
      const region = regions.find((item) => item?.component_id === regionId && item?.component_key === `component:${regionId}`);
      const decisionRoot = (check.decision_roots || []).flatMap((row) => row.roots || [])
        .find((root) => root?.component_id === regionId && root?.component_key === `component:${regionId}` && root?.direct === true);
      if (!region || !decisionRoot) {
        bindingCellFindings.push({ code: 'construction-proof-region-root-mismatch',
          route_key: check.route_key, viewport: check.viewport, state_id: check.state_id,
          decision_id: null, component_key: `component:${regionId || '(missing)'}`, source_reference_id: null,
          field: 'proof_isolation.region_component_id',
          rerun: 'put data-design-dna-component equal to the declared proof region component ID on the one visible direct proof root; manifest text alone is not proof' });
      }
    }
  }
  const missingDecisionIds = [...new Set(bindingCellFindings
    .filter((finding) => finding.code === 'construction-binding-not-rendered')
    .map((finding) => finding.decision_id))].sort();
  const allowedDecisionIds = new Set(firstScreen ? visibleDecisionManifest.payload.proof_isolation?.decision_ids || visibleDecisionManifest.payload.planned_decision_ids : visibleDecisionManifest.payload.planned_decision_ids);
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
  const wrapperInheritanceFindings = checks.flatMap((check) =>
    (check.wrapper_inherited_visible_parts || []).map((part) => ({
      code: 'construction-wrapper-inheritance', route_key: check.route_key,
      viewport: check.viewport, state_id: check.state_id, decision_id: part.decision_id,
      component_key: part.component_key, source_reference_id: null,
      field: 'direct data-design-dna-decision-id',
      rerun: 'bind this independently visible descendant directly; a parent wrapper cannot source it',
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
    wrapper_inheritance_findings: wrapperInheritanceFindings,
    binding_cell_findings: bindingCellFindings,
    asset_role_findings: assetRoleFindings,
    construction_findings: [...unsourcedVisibleDecisions.map((item) => ({
      code: 'construction-unsourced-visible-part', ...item, decision_id: null,
      component_key: item.part, source_reference_id: null,
      field: 'data-design-dna-decision-id',
      rerun: 'add a current source-bound construction decision or remove this visible surface',
    })), ...wrapperInheritanceFindings, ...bindingCellFindings, ...assetRoleFindings],
    scaffold_findings: copyFindings.filter((finding) => finding.kind === "builder-narration"),
    fallback_findings: copyFindings.filter((finding) => finding.kind === "prototype-fallback"),
    placeholder_findings: copyFindings.filter((finding) => finding.kind === "scaffold-placeholder"),
    complete: missingDecisionIds.length === 0 && unsourcedVisibleDecisions.length === 0 &&
      wrapperInheritanceFindings.length === 0 && bindingCellFindings.length === 0 && assetRoleFindings.length === 0 && copyFindings.length === 0,
  };
  const firstConstructionFinding = visibleDecisionReconciliation.construction_findings[0] || null;
  const constructionVerdict = firstConstructionFinding ? `${firstConstructionFinding.code}: ` +
    `${firstConstructionFinding.route_key || 'project'}/${firstConstructionFinding.viewport || 'all'}/${firstConstructionFinding.state_id || 'all'} ` +
    `component=${firstConstructionFinding.component_key || '(unknown)'} decision=${firstConstructionFinding.decision_id || '(missing)'}; ` +
    `${firstConstructionFinding.rerun || 'bind current source evidence and rerun scan_build_components.mjs'}` : null;
  failedStates = checks.filter((check) => !check.pass).map((check) => `${check.route_key}/${check.viewport}/${check.state_id}`);
  const implementationAfter = snapshotImplementation(implementationProject);
  const implementationStable = implementationSnapshotsEqual(implementationBefore, implementationAfter);
  const pass = implementationStable && !unexpected.length && !failedStates.length && servedContent.complete && interactionInventory.complete &&
    renderedQa.complete && visibleDecisionReconciliation.complete;
  return {
    tool: TOOL_NAME, schema_version: SCHEMA_VERSION, producer_script_sha256: PRODUCER_SCRIPT_SHA256,
    runtime_identity: { "scan_build_components.mjs": PRODUCER_SCRIPT_SHA256,
      "construction_phase.mjs": createHash('sha256').update(fs.readFileSync(path.join(SCRIPT_DIR, 'construction_phase.mjs'))).digest('hex'),
      "rendered_font_delivery.mjs": createHash('sha256').update(fs.readFileSync(path.join(SCRIPT_DIR, 'rendered_font_delivery.mjs'))).digest('hex'),
      "implementation_snapshot.mjs": createHash('sha256').update(fs.readFileSync(path.join(SCRIPT_DIR, 'implementation_snapshot.mjs'))).digest('hex'),
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
    implementation_snapshot: implementationStable ? implementationAfter : null,
    implementation_stable: implementationStable,
    rendered_qa: renderedQa,
    visible_decision_reconciliation: visibleDecisionReconciliation,
    interaction_frame_directory: interactionFrameRelativeRoot,
    interaction_video_directory: interactionVideoRelativeRoot,
    discovered_urls: [...discovered].sort(), unexpected_urls: unexpected, failed_states: failedStates,
    pass,
    verdict: pass ? `Scanned ${checks.length} exact route/viewport/state cells; every navigation was exact 2xx, response bytes were stable, and every internal route is manifested.` :
      [unexpected.length ? `unmanifested internal routes: ${unexpected.join(", ")}` : null,
       !implementationStable ? 'implementation tree changed during rendered census; current tree was not audited' : null,
       failedStates.length ? `declared states or DOM surfaces not exercised: ${failedStates.join(", ")}` : null,
        !servedContent.complete ? `served response bodies changed between repeated loads: ${servedContent.inconsistent_reloads.map((item) => item.key).join(", ")}` : null,
        !interactionInventory.complete ? `interaction transfer inventory incomplete: ${interactionMissing.join(", ") || "responsive/source-state binding"}` : null,
        !renderedQa.complete ? `rendered browser QA failed: ${renderedQaMissing.join(" | ")}` : null,
        !visibleDecisionReconciliation.complete ? (constructionVerdict || "visible decisions include unsourced/scaffold/fallback/placeholder output") : null].filter(Boolean).join("; "),
  };
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === SCRIPT_PATH;
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
