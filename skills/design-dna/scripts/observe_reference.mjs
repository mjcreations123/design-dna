#!/usr/bin/env node
/**
 * observe_reference.mjs
 *
 * Watch one public reference site the way a person does, and emit an evidence
 * record of what the site actually does.
 *
 * Schema 1 (6.6.0) proved that motion existed by comparing frame hashes. That
 * stopped a producer from claiming motion it never saw, but it could not say
 * what the motion was, so the producer went on measuring font sizes and
 * padding and calling that the design. Schema 2 records mechanisms: which
 * elements hold still in the viewport while the page moves under them and for
 * how far, what swaps inside them while they hold, what reveals as it enters,
 * what parallaxes, what follows the pointer, and how long a hover transition
 * takes. Those are the parts a stranger would name, and they are reproducible
 * as numbers.
 *
 * The scroll pass is driven by real wheel gestures and reads element geometry
 * against the viewport, never against window.scrollY. A site that intercepts
 * the wheel and moves content by transform has a document that never scrolls
 * at all; the previous version was blind to exactly that kind of site, and it
 * is the kind that wins awards.
 *
 * The record also carries a score: how many distinct mechanisms were seen and
 * what fraction of the scroll depth had a scroll-linked mechanism active.
 * Those measurements bound a motion claim; they do not judge static quality,
 * brief fit, or the source's dominant experience. Attributable candidate and
 * rendered reviews remain mandatory.
 *
 * Usage:
 *   node observe_reference.mjs --url https://example.test/ --id strong-1 \
 *        --out .design-dna/references [--browser-executable FILE]
 */
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { STRUCTURE_SCRIPT } from "./structure_probe.mjs";
import { applyManifestState, captureInteractionCensus, captureRenderedQA, collectSameOriginLinks, discoverUnaddressableClosedRoots, inferAndReconcileStates, installDomInspection, interactionCensusIncompleteError, mergeSourceGestureInventories, mergeSourceRenderedQA, navigateExact, normalizeHttpUrl,
  traverseScrollSurfaces, validateManifestState } from "./browser_evidence.mjs";
import { browserExecutableIdentity, discoverBrowserExecutable, resolvePlaywright } from "./playwright_resolver.mjs";
import { adoptEarlySourceSurfaceWatch, armEarlySourceSurfaceWatch, drainSourceSurfaceWatch, startSourceSurfaceWatch, stopSourceSurfaceWatch, undocumentedSourceSurfaceError } from "./source_surface_watch.mjs";
import { acquireSourceStudyOutputLease, acquireSourceStudyRunnerLease, createSourceStudyController, sourceStudyFailureStatus } from "./source_study_controller.mjs";

const SCHEMA_VERSION = 5;
const SCRIPT_PATH = path.resolve(fileURLToPath(import.meta.url));
const PRODUCER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(SCRIPT_PATH)).digest("hex");
const STRUCTURE_PROBE_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "structure_probe.mjs"))).digest("hex");
const BROWSER_EVIDENCE_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "browser_evidence.mjs"))).digest("hex");
const PLAYWRIGHT_RESOLVER_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "playwright_resolver.mjs"))).digest("hex");
const SOURCE_SURFACE_WATCH_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "source_surface_watch.mjs"))).digest("hex");
const SOURCE_STUDY_CONTROLLER_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "source_study_controller.mjs"))).digest("hex");
const REST_SETTLE_MS = 700;
const HOLD_MS = 900;
// the mechanism pass: many small wheel ticks so a pinned stage, a swap or a
// parallax shows up as a trend across samples rather than a single jump
const TICK_PX = 700;
const TICK_SETTLE_MS = 650;

async function requireAddressableSourceStructure(page, profile, stateId = null, evidence = null) {
  const roots = await discoverUnaddressableClosedRoots(page);
  if (!roots.length) return;
  const context = { phase: 'source-structure-precheck', source_state_id: stateId };
  const message = `${profile}${stateId ? '/'+stateId : ''}: visible closed-shadow material is inaccessible to the locator/state protocol; this is a harness coverage gap, not an empty or defective source.`;
  throw Object.assign(new Error(message), { code: 'unsupported-source-closed-shadow-root', source_harness_gap: true,
    census_diagnostic: { schema_version: 1, kind: 'closed-shadow-coverage-incomplete', complete: false, profile, context,
      failures: roots.map((root) => ({ code: 'unsupported-source-closed-shadow-root', input_kind: 'closed-shadow-root',
        source_harness_gap: true, reason: message, closed_shadow_root: root, evidence })) } });
}

function fail(code, message, details = null) {
  throw Object.assign(new Error(message), { code, terminal_details: details || {} });
}

function emitFailure(code, message, details = null) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message, ...(details || {}) } }, null, 2) + "\n");
  process.exitCode = 2;
}

function parseArgs(argv) {
  const out = { url: null, id: null, outDir: null,
    browserExecutable: process.env.DESIGN_DNA_BROWSER_EXECUTABLE || process.env.CHROME || null,
    label: null, stateContract: null, proofSource: false, sourceState: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--url") out.url = argv[++i];
    else if (a === "--id") out.id = argv[++i];
    else if (a === "--out") out.outDir = argv[++i];
    else if (a === "--label") out.label = argv[++i];
    else if (a === "--state-contract") out.stateContract = argv[++i];
    else if (a === "--proof-source") out.proofSource = true;
    else if (a === "--state") out.sourceState = argv[++i];
    else if (a === "--browser-executable") out.browserExecutable = argv[++i];
    else if (a === "--help" || a === "-h") {
      process.stdout.write(
        "observe_reference.mjs --url URL --id ID --out DIR --state-contract FILE [--proof-source --state ID] [--label TEXT] [--browser-executable FILE]\n"
      );
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${a}`);
  }
  if (!out.url || !/^https?:\/\//i.test(out.url)) fail("invalid-url", "--url must be an http(s) URL.");
  if (!out.id || !/^[a-z][a-z0-9-]{0,47}$/.test(out.id)) fail("invalid-id", "--id must be a short lowercase slug, e.g. strong-1.");
  if (!out.outDir) fail("invalid-out", "--out must name a directory.");
  if (!out.stateContract) fail("state-contract-required", "--state-contract is required; source states may not be auto-named or guessed.");
  if (out.proofSource !== Boolean(out.sourceState)) fail("proof-state-required", "--proof-source requires one exact --state ID; --state is unavailable in public-source mode.");
  return out;
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

function readStateContract(file, referenceId, primaryUrl) {
  let payload;
  try { payload = JSON.parse(fs.readFileSync(file, "utf8")); }
  catch (error) { fail("state-contract-unreadable", `${file}: ${String(error).slice(0, 220)}`); }
  if (![1, 2].includes(payload?.schema_version) || payload.reference_id !== referenceId || !Array.isArray(payload.states) ||
      Object.keys(payload).some((key) => !["schema_version", "reference_id", "states"].includes(key))) {
    fail("state-contract-invalid", "Source state contract must be exact schema 1 (legacy) or schema 2 (ambient-capable) with reference_id and states.");
  }
  const ids = new Set();
  for (const state of payload.states) {
    const core = state && { id: state.id, kind: state.kind, trigger: state.trigger, expectation: state.expectation };
    const ambient = state?.trigger?.type === "ambient";
    const expectedTriggerKeys = ambient ? ["type", "target", "value", "wait_ms"] : ["type", "target", "value"];
    if (!state || Object.keys(state).some((key) => !["id", "url", "kind", "trigger", "expectation"].includes(key)) ||
        Object.keys(state.trigger || {}).sort().join("|") !== expectedTriggerKeys.sort().join("|") ||
        (ambient && payload.schema_version !== 2) || validateManifestState(core, { sourceOnly: true }) || ids.has(state.id)) {
      fail("state-contract-invalid", "Every source state needs a globally unique id, exact URL, kind, trigger and expectation.");
    }
    let normalized;
    try { normalized = normalizeHttpUrl(state.url); } catch { fail("state-contract-invalid", `${state.id}: invalid URL.`); }
    if (new URL(normalized).origin !== new URL(primaryUrl).origin) fail("state-contract-invalid", `${state.id}: state URL must be same-origin.`);
    state.url = normalized; ids.add(state.id);
  }
  if (!payload.states.some((state) => state.id === "rest" && state.url === normalizeHttpUrl(primaryUrl))) {
    fail("state-contract-invalid", "The primary exact URL requires the canonical rest source state.");
  }
  return { payload, file: path.resolve(file), sha256: sha(fs.readFileSync(file)) };
}

const sha = (buf) => createHash("sha256").update(buf).digest("hex");

function writeJsonAtomically(file, payload) {
  const temporary = `${file}.tmp-${process.pid}-${Date.now()}`;
  fs.writeFileSync(temporary, JSON.stringify(payload, null, 2) + "\n", "utf8");
  fs.renameSync(temporary, file);
}

function writeObservationFailureReport(args, stateContract, frameDir, frames, runtimeIdentity, error) {
  const file = path.join(args.outDir, `${args.id}-observation-failure.json`);
  const diagnostic = error?.census_diagnostic || null;
  const report = {
    schema_version: 1,
    kind: "reference-observation-failure",
    status: "incomplete-not-selection-evidence",
    source_status: error?.source_study?.source_status || sourceStudyFailureStatus(error?.code, { source_error: String(error?.message || error) }, frames.length),
    eligible_for_source_selection: false,
    id: args.id,
    requested_url: args.url,
    state_contract: { file: path.basename(stateContract.file), sha256: stateContract.sha256 },
    runtime_identity: runtimeIdentity,
    error: { code: error?.code || "observation-failed", message: String(error?.message || error) },
    interaction_census: diagnostic,
    autonomous_surface_watch: error?.surface_watch || null,
    capture_integrity: error?.capture_integrity || null,
    source_study: error?.source_study || null,
    source_study_progress: error?.source_study_progress || null,
    source_study_failure: error?.source_study_failure || null,
    consent_handoff: error?.consent_candidate || error?.consent_disposition || null,
    frames: frames.map((frame) => ({ ...frame, file: `${path.basename(frameDir)}/${frame.file}` })),
  };
  writeJsonAtomically(file, report);
  return { file, sha256: sha(fs.readFileSync(file)) };
}

// Tag every element large enough to be a stage, a picture, a heading or a
// block, so the scroll pass can follow each one by a stable id.
export const TAG_PROBES = `(() => {
  let i = 0;
  const existing = document.querySelectorAll('[data-dna-probe]').length;
  i = existing;
  const sel = 'section,article,div,figure,img,video,canvas,svg,h1,h2,h3,p,ul,ol,li,a';
  document.querySelectorAll(sel).forEach((el) => {
    const r = el.getBoundingClientRect();
    // a mascot, a logo mark or a cursor-following icon is exactly as
    // significant as a hero photograph and much smaller; the 120x56 floor
    // exists to skip inline text noise, not to make small media invisible.
    const isSmallMedia = ['IMG', 'VIDEO', 'CANVAS', 'SVG'].includes(el.tagName) && r.width >= 12 && r.height >= 12;
    if (!isSmallMedia && (r.width < 120 || r.height < 56)) return;
    if (!el.hasAttribute('data-dna-probe')) el.setAttribute('data-dna-probe', String(i += 1));
  });
  return i;
})()`;

export const SAMPLE_PROBES = `(() => {
  const out = {};
  const vh = window.innerHeight;
  document.querySelectorAll('[data-dna-probe]').forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.bottom < -vh || r.top > vh * 2) return;
    const c = getComputedStyle(el);
    const media = el.tagName === 'IMG' || el.tagName === 'VIDEO' ? el : el.querySelector('img,video');
    let src = '';
    if (media) src = (media.currentSrc || media.src || media.poster || '').slice(-48);
    out[el.getAttribute('data-dna-probe')] = {
      top: Math.round(r.top),
      left: Math.round(r.left),
      h: Math.round(r.height),
      w: Math.round(r.width),
      op: Number(c.opacity),
      tf: c.transform === 'none' ? '' : c.transform,
      pos: c.position,
      hov: el.matches(':hover'),
      src,
      txt: (el.innerText || el.textContent || '').trim().slice(0, 40),
      tag: el.tagName.toLowerCase(),
      cls: (typeof el.className === 'string' ? el.className : '').trim().slice(0, 40),
      parent: (el.parentElement && el.parentElement.closest('[data-dna-probe]') || {getAttribute(){return null;}}).getAttribute('data-dna-probe'),
    };
  });
  let inner = null;
  document.querySelectorAll('div,main,section,article').forEach((el) => {
    const cs = getComputedStyle(el);
    if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 200) {
      if (!inner || el.scrollHeight > inner.h) inner = { h: el.scrollHeight, top: el.scrollTop, cls: (typeof el.className === 'string' ? el.className : '').slice(0, 40) };
    }
  });
  return { y: window.scrollY, docH: document.documentElement.scrollHeight, inner, els: out };
})()`;

export function median(values) {
  if (!values.length) return 0;
  const s = [...values].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export function mechanismWeight(mechanism) {
  const area = Math.max(0, Number(mechanism.w || 0) * Number(mechanism.h || 0));
  if (mechanism.type === "at-rest") return 400 + area / 100;
  if (mechanism.type === "page-transition") return 1800;
  if (mechanism.type === "pinned") return 1400 + Number(mechanism.held_px || 0) + Number(mechanism.swaps_while_held || 0) * 1000;
  if (mechanism.type === "pointer-follow") return 1200 + Number(mechanism.moved_px || 0);
  if (mechanism.type === "swap") return 900 + Number(mechanism.swaps || 0) * 100;
  if (mechanism.type === "parallax") return 700 + Number(mechanism.ticks || 0) * 10;
  if (mechanism.type === "reveal") return 500 + area / 1000;
  if (mechanism.type === "hover-transition") return 300 + Number(mechanism.responded || 0) * 20;
  if (mechanism.type === "state-transition") return 900
    + Number(mechanism.changed_properties || 0) * 100
    + Number(mechanism.duration_ms || 0);
  return 0;
}

export function finalizeMechanisms(mechanisms) {
  const seen = new Set();
  return [...mechanisms]
    .sort((a, b) => mechanismWeight(b) - mechanismWeight(a))
    .filter((mechanism) => {
      const key = `${mechanism.type}|${mechanism.tag || ""}|${mechanism.cls || ""}|${mechanism.src || ""}|${mechanism.detail || ""}`;
      if (seen.has(key)) return false;
      seen.add(key); return true;
    });
}

export function firstScreenSheet(sheet, viewportHeight = 900) {
  const globalTypes = new Set(["page-transition", "hover-transition", "state-transition"]);
  const mechanisms = finalizeMechanisms((sheet?.mechanisms || []).filter((mechanism) => {
    if (globalTypes.has(mechanism.type)) return true;
    if (mechanism.type === "pointer-follow" && Number(mechanism.depth_fraction || 0) === 0) return true;
    const top = Number(mechanism.initial_top ?? mechanism.top);
    return Number.isFinite(top) && top < viewportHeight && top + Number(mechanism.h || 0) > 0;
  }));
  const typeInstances = {};
  for (const mechanism of mechanisms) typeInstances[mechanism.type] = (typeInstances[mechanism.type] || 0) + 1;
  return { mechanisms, score: { ...(sheet?.score || {}), type_instances: typeInstances } };
}

// Turn the per-tick samples into named mechanisms with numbers a build can
// reproduce. The page's own motion each tick is the median movement of every
// visible probe, so a site that never changes scrollY still reads correctly.
export function deriveMechanisms(ticks) {
  const track = new Map();
  ticks.forEach((snap, tickIndex) => {
    for (const [id, v] of Object.entries(snap.els)) {
      if (!track.has(id)) track.set(id, []);
      track.get(id).push({ tick: tickIndex, ...v });
    }
  });
  const pageMove = [];
  for (let t = 1; t < ticks.length; t += 1) {
    const deltas = [];
    for (const [id, v] of Object.entries(ticks[t].els)) {
      const prev = ticks[t - 1].els[id];
      if (prev && prev.pos !== "fixed") deltas.push(prev.top - v.top);
    }
    const a = ticks[t - 1], b = ticks[t];
    const docConsumed = Math.abs((b.y || 0) - (a.y || 0));
    const innerConsumed = a.inner && b.inner ? Math.abs((b.inner.top || 0) - (a.inner.top || 0)) : 0;
    pageMove.push(Math.max(docConsumed, innerConsumed, Math.abs(median(deltas))));
  }
  const mechanisms = [];
  const activeTicks = new Set();
  // which probes travelled a long way over the run, and who contains whom
  const travelled = new Set();
  const parentOf = new Map();
  for (const [id, seq] of track) {
    parentOf.set(id, seq[0].parent);
    let lo = Infinity, hi = -Infinity;
    for (const s of seq) { lo = Math.min(lo, s.top); hi = Math.max(hi, s.top); }
    if (hi - lo > 300) travelled.add(id);
  }
  const hasTravellingDescendant = (id) => {
    for (const t of travelled) {
      let p = parentOf.get(t);
      let guard = 0;
      while (p && guard++ < 64) { if (p === id) return true; p = parentOf.get(p); }
    }
    return false;
  };
  const pinnedIds = new Set();
  for (const [id, seq] of track) {
    if (seq.length < 3) continue;
    const first = seq[0];
    const ident = { tag: first.tag, cls: first.cls, w: first.w, h: first.h, initial_top: first.top, sample: first.txt.slice(0, 36) };
    let pinRun = 0, pinPx = 0, bestRun = 0, bestPx = 0, bestStart = -1, runStart = -1;
    let parallaxTicks = 0;
    const parallaxTickIds = [];
    const rates = [];
    for (let i = 1; i < seq.length; i += 1) {
      const a = seq[i - 1], b = seq[i];
      if (b.tick !== a.tick + 1) { pinRun = 0; pinPx = 0; continue; }
      const move = pageMove[b.tick - 1] || 0;
      const dTop = a.top - b.top;
      if (move > 40) {
        const rate = dTop / move;
        rates.push(rate);
        if (Math.abs(dTop) < move * 0.22 && b.top > -b.h && b.top < 900) {
          if (pinRun === 0) runStart = a.tick;
          pinRun += 1; pinPx += move;
          if (pinRun > bestRun) { bestRun = pinRun; bestPx = pinPx; bestStart = runStart; }
        } else { pinRun = 0; pinPx = 0; }
        if (rate > 0.12 && rate < 0.85) { parallaxTicks += 1; parallaxTickIds.push(b.tick); }
      }
    }
    const ops = seq.map((s) => s.op);
    const opRise = Math.max(...ops) - Math.min(...ops);
    const srcs = [...new Set(seq.map((s) => s.src).filter(Boolean))];
    const txts = [...new Set(seq.map((s) => s.txt).filter(Boolean))];
    const tfs = [...new Set(seq.map((s) => s.tf))];
    const swaps = Math.max(srcs.length, txts.length) - 1;

    const framesTravel = hasTravellingDescendant(id);
    if (bestRun >= 3 && first.pos !== "fixed" && (swaps > 0 || framesTravel)) {
      pinnedIds.add(id);
      mechanisms.push({
        type: "pinned",
        id,
        ...ident,
        content_travels_through: framesTravel,
        held_ticks: bestRun,
        held_px: Math.round(bestPx),
        swaps_while_held: Math.max(0, swaps),
        detail: `held still in the viewport for ${Math.round(bestPx)}px of scroll` +
          (swaps > 0 ? ` while its content changed ${swaps} time(s)` : ""),
      });
      for (let t = bestStart; t < bestStart + bestRun; t += 1) activeTicks.add(t);
    }
    if (swaps > 0 && bestRun < 3) {
      mechanisms.push({ type: "swap", ...ident, swaps, detail: `its content changed ${swaps} time(s) as the page moved` });
      for (let i = 1; i < seq.length; i += 1) {
        if (seq[i].src !== seq[i - 1].src || seq[i].txt !== seq[i - 1].txt) activeTicks.add(seq[i].tick);
      }
    }
    if (opRise >= 0.35 || (tfs.length > 1 && tfs.includes(""))) {
      mechanisms.push({
        type: "reveal",
        ...ident,
        opacity_from: Number(Math.min(...ops).toFixed(2)),
        opacity_to: Number(Math.max(...ops).toFixed(2)),
        transform_shed: tfs.length > 1 && tfs.includes(""),
        detail: "changed opacity or shed a transform as it came into view",
      });
      for (let i = 1; i < seq.length; i += 1) {
        if (Math.abs(seq[i].op - seq[i - 1].op) >= 0.08 || seq[i].tf !== seq[i - 1].tf) activeTicks.add(seq[i].tick);
      }
    }
    if (parallaxTicks >= 4) {
      mechanisms.push({
        type: "parallax",
        ...ident,
        rate: Number(median(rates.filter((r) => r > 0.12 && r < 0.85)).toFixed(2)),
        ticks: parallaxTicks,
        detail: "moved at a different rate than the page",
      });
      parallaxTickIds.forEach((tick) => activeTicks.add(tick));
    }
  }
  const scrollTicks = Math.max(1, ticks.length - 1);
  for (const t of [...activeTicks]) if (t < 1 || t > scrollTicks) activeTicks.delete(t);
  // how many elements each device is applied to, counted before the record is
  // deduplicated. One reveal on every section collapses to a single line but
  // is eight instances, and that count is the "fade on everything" tell.
  const typeCounts = {};
  for (const m of mechanisms) typeCounts[m.type] = (typeCounts[m.type] || 0) + 1;
  // an outer frame that only holds because an inner frame holds is the same
  // mechanism reported twice; keep the innermost
  const containsPinned = (id) => {
    for (const other of pinnedIds) {
      if (other === id) continue;
      let p = parentOf.get(other); let guard = 0;
      while (p && guard++ < 64) { if (p === id) return true; p = parentOf.get(p); }
    }
    return false;
  };
  for (let i = mechanisms.length - 1; i >= 0; i -= 1) {
    const m = mechanisms[i];
    if (m.type === "pinned" && containsPinned(m.id)) mechanisms.splice(i, 1);
  }
  mechanisms.forEach((m) => { delete m.id; });
  // one line per element kind, the most significant first, so the record
  // reads as a list of mechanisms rather than a census of every node
  const seen = new Set();
  const kept = mechanisms
    .sort((a, b) => mechanismWeight(b) - mechanismWeight(a))
    .filter((m) => { const k = `${m.type}|${m.tag}|${m.cls}`; if (seen.has(k)) return false; seen.add(k); return true; });
  return { mechanisms: kept, activeTicks, scrollTicks, pageMove, typeCounts };
}

// The whole mechanism pass on an open page, shared with compare_mechanisms.mjs
// so a build is read by exactly the same eyes as its references.
export async function mechanismPass(page) {
  await page.evaluate(TAG_PROBES);
  const ticks = [];
  ticks.push(await page.evaluate(SAMPLE_PROBES));
  const scrollTraversal = await traverseScrollSurfaces(page, {
    maxTicks: 240,
    settleMs: TICK_SETTLE_MS,
    onTick: async () => {
      await page.evaluate(TAG_PROBES);
      ticks.push(await page.evaluate(SAMPLE_PROBES));
    },
  });
  const derived = deriveMechanisms(ticks);
  const last = ticks[ticks.length - 1];
  const scroller = last.y > 0 ? "document" : (last.inner ? `inner:${last.inner.cls || "element"}` : "none");
  // Pointer follow must move with the pointer and return when the pointer
  // returns. A one-way before/after comparison falsely labeled ordinary
  // :hover transforms and unrelated autoplay as pointer-follow.
  let pointerFollow = null;
  const docHeight = await page.evaluate(() => document.documentElement.scrollHeight).catch(() => 0);
  const viewport = page.viewportSize() || { width: 1440, height: 900 };
  const points = [
    { x: Math.max(40, viewport.width * 0.14), y: Math.max(40, viewport.height * 0.28) },
    { x: Math.min(viewport.width - 40, viewport.width * 0.84), y: Math.min(viewport.height - 40, viewport.height * 0.68) },
  ];
  for (const fraction of [0, 0.4, 0.75]) {
    if (pointerFollow) break;
    try {
      await page.evaluate((y) => window.scrollTo(0, y), Math.round(docHeight * fraction));
      await page.waitForTimeout(400);
      await page.evaluate(TAG_PROBES);
      await page.mouse.move(points[0].x, points[0].y);
      await page.waitForTimeout(350);
      const a = await page.evaluate(SAMPLE_PROBES);
      await page.mouse.move(points[1].x, points[1].y, { steps: 12 });
      await page.waitForTimeout(350);
      const b = await page.evaluate(SAMPLE_PROBES);
      await page.mouse.move(points[0].x, points[0].y, { steps: 12 });
      await page.waitForTimeout(350);
      const c = await page.evaluate(SAMPLE_PROBES);
      const pdx = points[1].x - points[0].x, pdy = points[1].y - points[0].y;
      const plen = Math.hypot(pdx, pdy);
      for (const [id, middle] of Object.entries(b.els)) {
        const start = a.els[id], returned = c.els[id];
        if (!start || !returned || start.hov || middle.hov || returned.hov) continue;
        const dx = middle.left - start.left, dy = middle.top - start.top;
        const moved = Math.hypot(dx, dy);
        const returnedDistance = Math.hypot(returned.left - start.left, returned.top - start.top);
        const correlation = moved && plen ? (dx * pdx + dy * pdy) / (moved * plen) : -1;
        const transformTracked = start.tf !== middle.tf && middle.tf !== returned.tf;
        if (moved > 8 && correlation > 0.45 && returnedDistance <= Math.max(8, moved * 0.3) &&
            (transformTracked || moved > 14) && middle.top > -50 && middle.top < viewport.height + 50) {
          pointerFollow = { tag: middle.tag, cls: middle.cls, w: middle.w, h: middle.h,
            depth_fraction: fraction,
            moved_px: Math.round(moved), return_error_px: Math.round(returnedDistance),
            pointer_correlation: +correlation.toFixed(2), sample: middle.txt.slice(0, 36) };
          break;
        }
      }
    } catch (e) { /* try the next depth */ }
  }
  await page.evaluate(() => window.scrollTo(0, 0)).catch(() => {});
  if (pointerFollow) {
    derived.mechanisms.push({ type: "pointer-follow", ...pointerFollow, detail: "its transform changed as the pointer crossed the screen" });
  }
  derived.mechanisms.push(...await checkAmbientVideo(page));
  const allTypeCounts = { ...derived.typeCounts };
  for (const mechanism of derived.mechanisms) {
    if (!(mechanism.type in allTypeCounts)) allTypeCounts[mechanism.type] = 0;
  }
  if (pointerFollow) allTypeCounts["pointer-follow"] = (allTypeCounts["pointer-follow"] || 0) + 1;
  for (const video of derived.mechanisms.filter((mechanism) => mechanism.type === "at-rest" && mechanism.tag === "video")) {
    allTypeCounts[video.type] = Math.max(allTypeCounts[video.type] || 0, 1);
  }
  derived.mechanisms = finalizeMechanisms(derived.mechanisms);
  return {
    mechanisms: derived.mechanisms,
    score: {
      distinct_mechanisms: new Set(derived.mechanisms.map((m) => m.type)).size,
      scroll_coverage: Number((derived.activeTicks.size / derived.scrollTicks).toFixed(2)),
      scroll_windows_active: derived.activeTicks.size,
      scroll_windows: derived.scrollTicks,
      elements_with_mechanism: derived.mechanisms.filter((m) => m.tag).length,
      document_scrolls: ticks.some((t) => t.y > 0),
      type_instances: allTypeCounts,
      scroller,
      scroll_consumed_px: Math.round(derived.pageMove.reduce((a, b) => a + b, 0)),
    },
    wheel_ticks: ticks.length - 1,
    scroll_traversal: scrollTraversal,
  };
}

// A "photograph" that is actually a looping/autoplaying <video> is one of
// the most common misses in a hand-written sequence read: the frame-diff
// tooling only ever compares scroll positions, so a video that quietly plays
// in place, unrelated to scroll or hover (a swiveling chair, smoke off a
// candle, a fireplace), never triggers a scroll-hold or hover mechanism at
// all. This checks the DOM directly instead of relying on any diff: real
// playback progress on a real <video> element proves it, at whatever size
// and wherever on the page it currently sits.
async function checkAmbientVideo(page) {
  const before = await page.evaluate(() =>
    [...document.querySelectorAll("video")].map((v) => {
      const r = v.getBoundingClientRect();
      return {
        src: (v.currentSrc || v.src || "").slice(-60),
        t: v.currentTime,
        loop: v.loop,
        autoplay: v.autoplay,
        muted: v.muted,
        paused: v.paused,
        top: Math.round(r.top),
        w: Math.round(r.width),
        h: Math.round(r.height),
        visible: r.bottom > 0 && r.top < innerHeight,
      };
    })
  ).catch(() => []);
  if (!before.length) return [];
  await page.waitForTimeout(1200);
  const afterT = await page.evaluate(() => [...document.querySelectorAll("video")].map((v) => v.currentTime)).catch(() => []);
  const found = [];
  before.forEach((v, i) => {
    if (!v.visible || v.w < 40 || v.h < 40) return;
    const advanced = (afterT[i] || 0) > v.t + 0.15;
    if (advanced || (!v.paused && (v.loop || v.autoplay))) {
      found.push({
        type: "at-rest", tag: "video", w: v.w, h: v.h, top: v.top, loop: v.loop, autoplay: v.autoplay, src: v.src,
        detail: `a ${v.w}x${v.h} video plays on its own${v.loop ? ", looped" : ""}, not a static photograph`,
      });
    }
  });
  return found;
}

export const CONSENT_SAFE_DISPOSITIONS = [
  'reject', 'reject all', 'decline', 'decline all',
  'only necessary', 'necessary only', 'essential only',
];

export function isConstrainedConsentSignal(value) {
  return /\bcookie(?:s)?\b|\bconsent\b|onetrust|privacy\s+(?:choices|settings|preferences)|tracking\s+(?:choices|settings|preferences)/i.test(String(value || ''));
}

/** Discover only a narrow, visible consent choice.  A generic dialog that
 * happens to mention privacy/tracking is an ambiguity, not permission to
 * click it.  Markers are inert data attributes used solely to make the one
 * generated locator exact after the pre-action frame is captured. */
async function classifyScopedConsent(page) {
  return page.evaluate((safeLabels) => {
    const visible = (element) => {
      const style = getComputedStyle(element), box = element.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && box.width > 1 && box.height > 1;
    };
    const text = (element) => (element.getAttribute('aria-label') || element.textContent || '').trim().replace(/\s+/g, ' ');
    const candidates = [...new Set(document.querySelectorAll('[role="dialog"],[aria-modal="true"],#onetrust-banner-sdk,[class*="cookie" i],[id*="cookie" i],[class*="consent" i],[id*="consent" i]'))]
      .filter(visible);
    const outer = candidates.filter((element) => !candidates.some((other) => other !== element && other.contains(element)));
    const describe = (element) => ({ tag: element.tagName.toLowerCase(), id: element.id || null,
      role: element.getAttribute('role') || null, aria_label: element.getAttribute('aria-label') || null,
      class_name: String(element.className || '').slice(0, 240), text: text(element).slice(0, 400) });
    const identified = outer.map((element) => {
      const signal = `${element.id} ${element.className} ${element.getAttribute('aria-label') || ''} ${text(element)}`;
      const strong = /\bcookie(?:s)?\b|\bconsent\b|onetrust|privacy\s+(?:choices|settings|preferences)|tracking\s+(?:choices|settings|preferences)/i.test(signal);
      const broad = /\bprivacy\b|\btracking\b/i.test(signal);
      return { element, strong, broad, description: describe(element) };
    }).filter((item) => item.strong || item.broad);
    if (!identified.length) return { present: false };
    const eligible = identified.filter((item) => item.strong);
    if (eligible.length !== 1 || identified.length !== 1) {
      return { present: true, eligible: false, reason: 'multiple-or-broad-consent-like-dialogs', candidates: identified.map((item) => item.description) };
    }
    const consent = eligible[0].element;
    const buttons = [...consent.querySelectorAll('button')].filter(visible);
    const safe = buttons.filter((button) => safeLabels.includes(text(button).toLowerCase()));
    if (safe.length !== 1) {
      return { present: true, eligible: false, reason: 'missing-or-ambiguous-safe-reject-action', candidates: [eligible[0].description],
        safe_action_count: safe.length, button_labels: buttons.map((button) => text(button).slice(0, 160)) };
    }
    const token = `consent-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    consent.setAttribute('data-design-dna-consent-root', token);
    safe[0].setAttribute('data-design-dna-consent-action', token);
    return { present: true, eligible: true, disposition: 'reject-or-essential-only', label: text(safe[0]),
      root: eligible[0].description, root_selector: `[data-design-dna-consent-root="${token}"]`,
      action_selector: `[data-design-dna-consent-action="${token}"]`, token };
  }, CONSENT_SAFE_DISPOSITIONS).catch((error) => ({ present: true, eligible: false, reason: 'consent-inspection-failed', error: String(error?.message || error).slice(0, 240) }));
}

async function requireUnblockedConsent(page, options = {}) {
  const result = await classifyScopedConsent(page);
  if (!result.present) return { present: false, dismissed: false };
  if (!result.eligible) {
    const error = new Error(`Consent-like dialog requires owner-safe handoff before observation; no automatic choice was made (${result.reason || 'ambiguous-consent'}).`);
    error.code = 'consent-handoff-required'; error.consent_candidate = result;
    throw error;
  }
  const capture = options.captureEvidence;
  if (typeof capture !== 'function') {
    throw new Error('A scoped consent disposition requires generated before/action/after evidence; the caller did not provide captureEvidence.');
  }
  const labelPrefix = options.labelPrefix || 'consent-disposition';
  const before = await capture(`${labelPrefix}-before`, page);
  const action = page.locator(result.action_selector);
  if (await action.count() !== 1 || !(await action.first().isVisible())) {
    throw new Error(`Scoped consent action ${JSON.stringify(result.action_selector)} no longer resolves to one visible exact control; no automatic choice was made.`);
  }
  const started = Date.now();
  await action.first().click({ timeout: 5000 });
  const actionFrame = await capture(`${labelPrefix}-action`, page);
  await page.waitForTimeout(600);
  const after = await capture(`${labelPrefix}-after`, page);
  const remaining = page.locator(result.root_selector);
  const remainingVisible = await remaining.count() === 1 && await remaining.first().isVisible();
  if (remainingVisible) {
    throw new Error(`Scoped consent disposition ${JSON.stringify(result.label)} did not remove its exact visible consent surface; no further dismissal will be attempted.`);
  }
  const record = { kind: 'consent-disposition', disposition: result.disposition, label: result.label,
    root: result.root, action_selector: result.action_selector, duration_ms: Date.now() - started,
    evidence_frames: { before, action: actionFrame, after } };
  if (Array.isArray(options.notes)) options.notes.push(record);
  return { present: true, dismissed: true, ...record };
}

function mergeMechanismSheets(sheets) {
  const mechanisms = finalizeMechanisms(sheets.flatMap((sheet) => sheet.mechanisms || []));
  const typeInstances = {};
  for (const sheet of sheets) for (const [type, count] of Object.entries(sheet.score?.type_instances || {})) {
    typeInstances[type] = (typeInstances[type] || 0) + Number(count || 0);
  }
  return { mechanisms, score: {
    distinct_mechanisms: new Set(mechanisms.map((item) => item.type)).size,
    scroll_coverage: sheets.length ? Number((sheets.reduce((sum, sheet) => sum + Number(sheet.score?.scroll_coverage || 0), 0) / sheets.length).toFixed(2)) : 0,
    scroll_windows_active: sheets.reduce((sum, sheet) => sum + Number(sheet.score?.scroll_windows_active || 0), 0),
    scroll_windows: sheets.reduce((sum, sheet) => sum + Number(sheet.score?.scroll_windows || 0), 0),
    elements_with_mechanism: mechanisms.filter((item) => item.tag).length,
    document_scrolls: sheets.some((sheet) => sheet.score?.document_scrolls),
    type_instances: typeInstances,
    scroller: [...new Set(sheets.map((sheet) => sheet.score?.scroller).filter(Boolean))].join(",") || "none",
    scroll_consumed_px: sheets.reduce((sum, sheet) => sum + Number(sheet.score?.scroll_consumed_px || 0), 0),
  } };
}

export function mergeInteractionCensuses(profile, censuses) {
  const pageMap = new Map();
  for (const pageRecord of censuses.flatMap((census) => census.pages || [])) {
    const current = pageMap.get(pageRecord.url) || { url: pageRecord.url, targets: [], dom_code_inventory: pageRecord.dom_code_inventory };
    const targetMap = new Map(current.targets.map((target) => [target.target_id, target]));
    for (const target of pageRecord.targets || []) {
      if (!targetMap.has(target.target_id)) targetMap.set(target.target_id, target);
      else {
        const existing = targetMap.get(target.target_id), keys = new Set(existing.inputs.map((input) =>
          `${input.input_kind}|${input.source_state_id || ''}|${input.before_sha256 || ''}|${input.after_sha256 || ''}`));
        for (const input of target.inputs || []) {
          const key = `${input.input_kind}|${input.source_state_id || ''}|${input.before_sha256 || ''}|${input.after_sha256 || ''}`;
          if (!keys.has(key)) { existing.inputs.push(input); keys.add(key); }
        }
        existing.source_state_ids = [...new Set([...existing.source_state_ids, ...target.source_state_ids])].sort();
      }
    }
    current.targets = [...targetMap.values()];
    const priorDom = current.dom_code_inventory, nextDom = pageRecord.dom_code_inventory;
    current.dom_code_inventory = nextDom || priorDom;
    if (priorDom?.gesture_listeners || nextDom?.gesture_listeners) current.dom_code_inventory.gesture_listeners =
      mergeSourceGestureInventories(priorDom?.gesture_listeners, nextDom?.gesture_listeners);
    if (priorDom && nextDom) for (const field of ['routes_discovered','state_hooks','animation_hooks','assets','scripts','inline_handlers']) {
      current.dom_code_inventory[field] = [...new Map([...(priorDom[field] || []), ...(nextDom[field] || [])]
        .map((item) => [typeof item === 'string' ? item : JSON.stringify(item), item])).values()];
    }
    if (current.dom_code_inventory) {
      current.dom_code_inventory.controls_discovered = current.targets.map((target) => target.target_id);
      current.dom_code_inventory.live_target_ids = current.targets.map((target) => target.target_id);
      current.dom_code_inventory.unreconciled_controls = [];
      current.dom_code_inventory.complete = true;
    }
    pageMap.set(pageRecord.url, current);
  }
  const pages = [...pageMap.values()].sort((a, b) => a.url.localeCompare(b.url));
  const targets = pages.flatMap((pageRecord) => pageRecord.targets || []);
  const classNames = [...new Set(targets.map((target) => target.repeat_class))].sort();
  const repeatClasses = classNames.map((repeatClass) => {
    const members = targets.filter((target) => target.repeat_class === repeatClass);
    const inputKinds = [...new Set(members.flatMap((target) => target.inputs.map((input) => input.input_kind)))].sort();
    const signatures = [...new Set(members.flatMap((target) => target.inputs.filter((input) => input.status === 'exercised')
      .map((input) => `${input.input_kind}:${input.behavior}`)))].sort();
    return { repeat_class: repeatClass, target_ids: members.map((target) => target.target_id), input_kinds: inputKinds,
      equivalent: members.length < 2 || inputKinds.every((kind) => new Set(members.flatMap((target) => target.inputs
        .filter((input) => input.input_kind === kind && input.status === 'exercised').map((input) => input.behavior))).size <= 1),
      behavior_signatures: signatures,
      evidence: members.flatMap((target) => target.inputs.map((input) => input.evidence).filter(Boolean)) };
  });
  const totals = censuses.reduce((sum, census) => ({
    targets_discovered: sum.targets_discovered + Number(census.totals?.targets_discovered || 0),
    inputs_discovered: sum.inputs_discovered + Number(census.totals?.inputs_discovered || 0),
    inputs_exercised: sum.inputs_exercised + Number(census.totals?.inputs_exercised || 0),
    inputs_blocked: sum.inputs_blocked + Number(census.totals?.inputs_blocked || 0),
  }), { targets_discovered: 0, inputs_discovered: 0, inputs_exercised: 0, inputs_blocked: 0 });
  const missing = censuses.flatMap((census) => census.missing || []);
  const pageStates = [...new Map(censuses.flatMap((census) => census.page_states || [])
    .map((state) => [`${state.page_url}|${state.source_state_id}`, state])).values()];
  const pointerFollow = [...new Map(censuses.flatMap((census) => census.pointer_follow || [])
    .map((item) => [`${item.page_url}|${item.target_id}`, item])).values()];
  const blockedSideEffects = [...new Map(censuses.flatMap((census) => census.blocked_side_effects || [])
    .map((item) => [`${item.target_id}|${item.input_kind}`, item])).values()];
  return { profile, pages, page_states: pageStates,
    repeat_classes: repeatClasses, pointer_follow: pointerFollow,
    blocked_side_effects: blockedSideEffects, totals,
    truncated: false, missing, complete: missing.length === 0 && censuses.every((census) => census.complete && census.truncated === false) };
}

async function studyRecursiveSite(page, primaryUrl, profile, authoredStates, captureEvidence, notes, sourceStudy = null) {
  const origin = new URL(primaryUrl).origin;
  const queue = [...new Set([normalizeHttpUrl(primaryUrl), ...authoredStates.map((state) => normalizeHttpUrl(state.url))])];
  const discovered = new Set(queue), visited = new Set();
  const pages = [];
  const interactionCensuses = [];
  const renderedQARecords = [];
  while (queue.length) {
    if (discovered.size > 1000) throw new Error(`${profile}: more than 1000 recursive same-origin pages were discovered; traversal cannot be claimed complete.`);
    const url = queue.shift();
    if (visited.has(url)) continue;
    sourceStudy?.markRoute(url, { profile, phase: 'recursive-site' });
    const ambientSelectors = authoredStates.filter((state) => state.trigger?.type === 'ambient').map((state) => state.trigger.target);
    const earlyBaseline = await captureEvidence(`${profile}-early-before-navigation`, page);
    const earlyWatch = await armEarlySourceSurfaceWatch(page, {
      ambientSelectors, baseline: earlyBaseline, labelPrefix: `${profile}-early-autonomous-surface`,
      captureEvidence: (label, targetPage = page) => captureEvidence(label, targetPage),
    });
    const navigation = sourceStudy
      ? await sourceStudy.step(`navigate:${profile}:recursive-site`, () => navigateExact(page, url), {
        detail: { url }, abort: async () => { await page.context().close().catch(() => {}); },
      })
      : await navigateExact(page, url);
    await page.evaluate(() => document.fonts?.ready).catch(() => {});
    await page.waitForTimeout(500);
    const consent = await requireUnblockedConsent(page, {
      notes,
      labelPrefix: `${profile}-consent-${visited.size + 1}`,
      captureEvidence: (label, targetPage = page) => captureEvidence(label, targetPage),
    });
    const surfaceBaseline = await captureEvidence(`${profile}-autonomous-watch-baseline`, page);
    const surfaceWatch = await adoptEarlySourceSurfaceWatch(page, earlyWatch, {
      ambientSelectors,
      baseline: surfaceBaseline,
      authorizedConsent: consent.dismissed ? [consent] : [],
      labelPrefix: `${profile}-autonomous-surface`,
      captureEvidence: (label, targetPage = page) => captureEvidence(label, targetPage),
    });
    let surfaceWatchClosed = false, closedSurfaceWatchReport = null;
    const closeSurfaceWatch = async (error = null) => {
      if (surfaceWatchClosed) {
        if (error && closedSurfaceWatchReport) error.surface_watch = closedSurfaceWatchReport;
        return closedSurfaceWatchReport;
      }
      surfaceWatchClosed = true;
      let report;
      try {
        report = await drainSourceSurfaceWatch(surfaceWatch, {
          labelPrefix: `${profile}-autonomous-surface`, captureEvidence,
        });
      } finally { await stopSourceSurfaceWatch(surfaceWatch); }
      if (report?.events?.length && Array.isArray(notes)) notes.push({ kind: 'autonomous-surface-watch', profile, page_url: url, report });
      const undocumented = undocumentedSourceSurfaceError(report, { profile, phase: 'recursive-site' });
      if (undocumented) throw undocumented;
      closedSurfaceWatchReport = report;
      if (error && report) error.surface_watch = report;
      return report;
    };
    try {
    await requireAddressableSourceStructure(page, profile);
    const structure = await page.evaluate(STRUCTURE_SCRIPT);
    if (!structure || !structure.dominant) throw new Error(`${profile} ${url}: first-screen structure is empty.`);
    const sheet = await mechanismPass(page);
    if (!sheet.scroll_traversal?.complete) {
      const gaps = (sheet.scroll_traversal?.surfaces || []).filter((item) => !item.complete).map((item) => `${item.kind}:${item.selector_hint || item.id}:${item.reason}`);
      throw new Error(`${profile} ${url}: incomplete scroll traversal (${gaps.join(", ")}).`);
    }
    const applicableStates = authoredStates.filter((state) => normalizeHttpUrl(state.url) === url);
    const stateInventory = await inferAndReconcileStates(page, applicableStates);
    if (!stateInventory.complete) throw new Error(`${profile} ${url}: ${stateInventory.unreconciled.length} inferred states lack authored source-state triggers.`);
    const knownTargets = new Set();
    const pageInteractionCensuses = [];
    let censusPass = 0;
    while (true) {
      censusPass += 1;
      const baselineState = applicableStates.find((state) => state.id === 'rest') || null;
      const censusOptions = { profile, pageUrl: url,
        authoredStates: applicableStates, baselineState,
        sourceOnly: true,
        context: { phase: 'recursive-site', source_state_id: baselineState?.id || null, pass: censusPass },
        captureEvidence };
      const interactionCensus = sourceStudy
        ? await sourceStudy.step(`interaction-census:${profile}:recursive-site`, () => captureInteractionCensus(page, censusOptions), {
          timeout_ms: 180_000, detail: { url, pass: censusPass }, abort: async () => { await page.context().close().catch(() => {}); },
        })
        : await captureInteractionCensus(page, censusOptions);
      if (!interactionCensus.complete || interactionCensus.truncated) {
        throw interactionCensusIncompleteError(interactionCensus,
          { phase: 'recursive-site', source_state_id: baselineState?.id || null, pass: censusPass });
      }
      interactionCensuses.push(interactionCensus);
      pageInteractionCensuses.push(interactionCensus);
      const observedTargets = interactionCensus.pages.flatMap((pageRecord) => pageRecord.targets.map((target) => target.target_id));
      const newTargets = observedTargets.filter((targetId) => !knownTargets.has(targetId));
      observedTargets.forEach((targetId) => knownTargets.add(targetId));
      for (const targetId of newTargets) sourceStudy?.markTarget(`${profile}|recursive-site|${url}|${targetId}`, { pass: censusPass });
      sourceStudy?.markEvent({ profile, kind: 'interaction-census', targets: observedTargets.length, pass: censusPass });
      if (!newTargets.length) break;
    }
    const pageInteractionCensus = mergeInteractionCensuses(profile, pageInteractionCensuses);
    const renderedQA = await captureRenderedQA(page, { profile, pageUrl: url,
      sourceState: applicableStates.find((state) => state.trigger?.type === 'none') || null,
      interactionCensus: pageInteractionCensus, captureEvidence });
    if (!renderedQA.complete || renderedQA.truncated) throw new Error(`${profile} ${url}: rendered QA evidence is incomplete.`);
    renderedQARecords.push(renderedQA);
    const links = await collectSameOriginLinks(page, origin);
    links.forEach((link) => { if (!discovered.has(link)) { discovered.add(link); queue.push(link); } });
    visited.add(url);
    pages.push({ url, navigation, structure, mechanisms: sheet.mechanisms, score: sheet.score,
      state_inventory: stateInventory,
      rendered_qa: renderedQA,
      scroll_traversal: sheet.scroll_traversal, discovered_links: links });
    await closeSurfaceWatch();
    } catch (error) {
      await closeSurfaceWatch(error);
      throw error;
    }
  }
  const missing = [...discovered].filter((url) => !visited.has(url));
  const interactionCensus = mergeInteractionCensuses(profile, interactionCensuses);
  const codeDiscoveredRoutes = [...new Set(interactionCensus.pages.flatMap((pageRecord) =>
    pageRecord.dom_code_inventory?.routes_discovered || []))].sort();
  const codeRouteGaps = codeDiscoveredRoutes.filter((url) => !visited.has(url));
  interactionCensus.dom_code_reconciliation = { routes_discovered: codeDiscoveredRoutes,
    routes_visited: [...visited].sort(), missing_routes: codeRouteGaps,
    complete: codeRouteGaps.length === 0 && interactionCensus.pages.every((pageRecord) => pageRecord.dom_code_inventory?.complete === true) };
  if (!interactionCensus.dom_code_reconciliation.complete) {
    interactionCensus.missing.push(...codeRouteGaps.map((url) => ({ target_id: null, input_kind: 'dom-route', reason: `DOM/code-discovered route was not visited: ${url}` })));
    interactionCensus.complete = false;
  }
  return { profile, origin, discovered_urls: [...discovered].sort(), visited_urls: [...visited].sort(),
    missing_urls: missing, complete: missing.length === 0 && pages.every((item) => item.scroll_traversal.complete) && interactionCensus.complete,
    pages, interaction_census: interactionCensus,
    rendered_qa: mergeSourceRenderedQA(profile, renderedQARecords),
    sheet: mergeMechanismSheets(pages.map((item) => ({ mechanisms: item.mechanisms, score: item.score }))) };
}

async function captureSourceStates(browser, contract, viewport, captureEvidence, notes, sourceStudy = null) {
  const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
  await installDomInspection(context);
  const page = await context.newPage();
  const result = {};
  try {
    for (const state of contract.states) {
      sourceStudy?.markState(`${viewport.name}:${state.id}:started`, { profile: viewport.name, phase: 'source-state-start' });
      const ambientSelectors = contract.states.filter((item) => item.trigger?.type === 'ambient').map((item) => item.trigger.target);
      const earlyBaseline = await captureEvidence(page, `${viewport.name}-${state.id}-early-before-navigation`);
      const earlyWatch = await armEarlySourceSurfaceWatch(page, {
        ambientSelectors, baseline: earlyBaseline, labelPrefix: `${viewport.name}-${state.id}-early-autonomous-surface`,
        captureEvidence: (label, targetPage = page) => captureEvidence(targetPage, label),
      });
      const navigation = sourceStudy
        ? await sourceStudy.step(`navigate:${viewport.name}:source-state`, () => navigateExact(page, state.url), {
          detail: { state_id: state.id, url: state.url }, abort: async () => { await context.close().catch(() => {}); },
        })
        : await navigateExact(page, state.url);
      await page.evaluate(() => document.fonts?.ready).catch(() => {});
      await page.waitForTimeout(500);
      const consent = await requireUnblockedConsent(page, {
        notes,
        labelPrefix: `${viewport.name}-${state.id}-consent`,
        captureEvidence: (label, targetPage = page) => captureEvidence(targetPage, label),
      });
      const beforeFrame = await captureEvidence(page, `${viewport.name}-${state.id}-state-before`);
      const surfaceWatch = await adoptEarlySourceSurfaceWatch(page, earlyWatch, {
        ambientSelectors,
        baseline: beforeFrame,
        authorizedConsent: consent.dismissed ? [consent] : [],
        labelPrefix: `${viewport.name}-${state.id}-autonomous-surface`,
        captureEvidence: (label, targetPage = page) => captureEvidence(targetPage, label),
      });
      let surfaceWatchClosed = false, closedSurfaceWatchReport = null;
      const closeSurfaceWatch = async (error = null) => {
        if (surfaceWatchClosed) {
          if (error && closedSurfaceWatchReport) error.surface_watch = closedSurfaceWatchReport;
          return closedSurfaceWatchReport;
        }
        surfaceWatchClosed = true;
        let report;
        try {
          report = await drainSourceSurfaceWatch(surfaceWatch, {
            labelPrefix: `${viewport.name}-${state.id}-autonomous-surface`,
            captureEvidence: (label, targetPage = page) => captureEvidence(targetPage, label),
          });
        } finally { await stopSourceSurfaceWatch(surfaceWatch); }
        if (report?.events?.length && Array.isArray(notes)) notes.push({ kind: 'autonomous-surface-watch', profile: viewport.name, state_id: state.id, page_url: state.url, report });
        const undocumented = undocumentedSourceSurfaceError(report, { profile: viewport.name, state_id: state.id, phase: 'source-state' });
        if (undocumented) throw undocumented;
        closedSurfaceWatchReport = report;
        if (error && report) error.surface_watch = report;
        return report;
      };
      try {
      let appearanceFrame = null;
      const application = await applyManifestState(page, state, {
        sourceOnly: true,
        onAmbientAppearance: state.trigger.type === "ambient" ? async (appearancePage) => {
          appearanceFrame = await captureEvidence(appearancePage, `${viewport.name}-${state.id}-state-appearance`);
        } : undefined,
      });
      const afterFrame = state.trigger.type === "ambient"
        ? appearanceFrame
        : await captureEvidence(page, `${viewport.name}-${state.id}-state-after`);
      if (!afterFrame) throw new Error(`${viewport.name}/${state.id}: ambient source appearance did not produce generated appearance-frame evidence.`);
      await page.waitForTimeout(220);
      const settledFrame = await captureEvidence(page, `${viewport.name}-${state.id}-state-settled`);
      await requireAddressableSourceStructure(page, viewport.name, state.id,
        { before: beforeFrame, after: afterFrame, settled: settledFrame });
      const structure = await page.evaluate(STRUCTURE_SCRIPT);
      if (!structure || !structure.dominant) throw new Error(`${viewport.name}/${state.id}: source-state first screen is empty.`);
      const sheet = await mechanismPass(page);
      if (!sheet.scroll_traversal?.complete) throw new Error(`${viewport.name}/${state.id}: source-state scroll traversal is incomplete.`);
      if (application.trigger_evidence?.mechanism) {
        sheet.mechanisms = finalizeMechanisms([...sheet.mechanisms, application.trigger_evidence.mechanism]);
        const type = application.trigger_evidence.mechanism.type;
        sheet.score.type_instances[type] = (sheet.score.type_instances[type] || 0) + application.trigger_evidence.mechanism_count;
        sheet.score.distinct_mechanisms = new Set(sheet.mechanisms.map((item) => item.type)).size;
      }
      const applicableStates = contract.states.filter((item) => normalizeHttpUrl(item.url) === normalizeHttpUrl(state.url));
       const censusOptions = { profile: viewport.name,
         pageUrl: state.url, authoredStates: applicableStates, baselineState: state,
         baselineApplication: application,
         baselineEvidence: { before: beforeFrame, after: afterFrame, settled: settledFrame },
         sourceOnly: true,
         context: { phase: 'source-state', source_state_id: state.id, pass: 1 },
         captureEvidence: (label, evidencePage = page) => captureEvidence(evidencePage, `${viewport.name}-${state.id}-${label}`) };
       const interactionCensus = sourceStudy
         ? await sourceStudy.step(`interaction-census:${viewport.name}:source-state`, () => captureInteractionCensus(page, censusOptions), {
           timeout_ms: 180_000, detail: { state_id: state.id, url: state.url }, abort: async () => { await context.close().catch(() => {}); },
         })
         : await captureInteractionCensus(page, censusOptions);
       for (const target of interactionCensus.pages.flatMap((pageRecord) => pageRecord.targets)) {
         sourceStudy?.markTarget(`${viewport.name}|source-state|${state.id}|${target.target_id}`, { state_id: state.id });
       }
       sourceStudy?.markEvent({ profile: viewport.name, kind: 'interaction-census', state_id: state.id,
         targets: interactionCensus.pages.reduce((total, pageRecord) => total + pageRecord.targets.length, 0) });
      if (!interactionCensus.complete) {
        throw interactionCensusIncompleteError(interactionCensus,
          { phase: 'source-state', source_state_id: state.id, pass: 1 });
      }
      const renderedQA = await captureRenderedQA(page, { profile: viewport.name, pageUrl: state.url,
        sourceState: state, interactionCensus,
        captureEvidence: (label, evidencePage = page) => captureEvidence(evidencePage, `${viewport.name}-${state.id}-${label}`) });
      if (!renderedQA.complete) throw new Error(`${viewport.name}/${state.id}: rendered QA is incomplete.`);
       result[state.id] = { id: state.id, url: state.url, kind: state.kind, trigger: state.trigger,
        expectation: state.expectation, navigation, trigger_application: application,
        trigger_evidence: application.trigger_evidence,
        evidence_frames: state.trigger.type === "ambient"
          ? { before: beforeFrame, appearance: afterFrame, settled: settledFrame }
          : { before: beforeFrame, after: afterFrame, settled: settledFrame },
        interaction_census: interactionCensus,
         rendered_qa: renderedQA,
         structure, mechanisms: sheet.mechanisms, score: sheet.score, scroll_traversal: sheet.scroll_traversal };
       sourceStudy?.markState(`${viewport.name}:${state.id}:complete`, { profile: viewport.name, phase: 'source-state-complete' });
      await closeSurfaceWatch();
      } catch (error) {
        await closeSurfaceWatch(error);
        throw error;
      }
    }
  } finally { await context.close(); }
  return result;
}

/** Capture one exact state at both canonical viewports for an internal specimen.
 * This deliberately emits no recursive/interaction completion claim. Its frames,
 * component identities and live values authorize only the bounded proof workflow.
 */
async function captureProofSource(args, stateContract, loaded, browserDependency) {
  const selected = stateContract.payload.states.find((state) => state.id === args.sourceState);
  if (!selected || normalizeHttpUrl(selected.url) !== normalizeHttpUrl(args.url)) {
    throw Object.assign(new Error('Proof-source capture requires one declared state at the exact primary URL.'), { code: 'proof-state-invalid' });
  }
  const frames = [], notes = [], navigations = [], proofComponentMaps = [];
  const frameDir = path.join(args.outDir, `${args.id}-frames`);
  const study = createSourceStudyController({ output_dir: args.outDir, id: args.id, producer: 'observe_reference.mjs', source_kind: 'proof-slice',
    limits: { max_total_elapsed_ms: 180_000, max_routes: 1, max_targets: 2_000 },
    required_completion_artifact_kinds: ['frame'],
    abort: async () => { await browser?.close().catch(() => {}); },
    partial_evidence: () => ({ frames, navigations, selected_state: selected.id, proof_only: true }) });
  fs.mkdirSync(frameDir, { recursive: true });
  let browser;
  const states = {}, firstScreens = {}, inventory = {}, captures = {}, proofDocumentStyles = {};
  const runtimeIdentity = { 'observe_reference.mjs': PRODUCER_SCRIPT_SHA256, 'structure_probe.mjs': STRUCTURE_PROBE_SHA256,
    'browser_evidence.mjs': BROWSER_EVIDENCE_SHA256, 'playwright_resolver.mjs': PLAYWRIGHT_RESOLVER_SHA256,
    'source_surface_watch.mjs': SOURCE_SURFACE_WATCH_SHA256, 'source_study_controller.mjs': SOURCE_STUDY_CONTROLLER_SHA256,
    'playwright-entry': loaded.dependency.resolved_file_sha256, 'browser-executable': browserDependency.sha256 };
  const shot = async (page, profile, label) => {
    const file = `${args.id}-${String(frames.length + 1).padStart(5, '0')}-${profile}-${label}.png`;
    const data = await study.step(`proof:${profile}:screenshot:${label}`, () => page.screenshot({ path: path.join(frameDir, file) }), { screenshot: true });
    const row = { file: `${path.basename(frameDir)}/${file}`, bytes: data.length, sha256: sha(data) };
    frames.push({ ...row, profile, label }); study.markFrame(row); return row;
  };
  try {
    browser = await loaded.playwright.chromium.launch({ executablePath: browserDependency.file });
    for (const viewport of [{ name: 'wide', width: 1440, height: 900 }, { name: 'narrow', width: 390, height: 844 }]) {
      const profile = viewport.name;
      const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
      try {
        await installDomInspection(context);
        const page = await context.newPage();
        study.markRoute(selected.url, { profile, selected_state: selected.id });
        const navigation = await study.step(`proof:${profile}:navigate`, () => navigateExact(page, selected.url));
        navigations.push(navigation);
        await shot(page, profile, 'loaded-unsettled');
        const mediaProblems = await study.step(`proof:${profile}:settle`, () => page.evaluate(async () => {
          await document.fonts.ready;
          const visible = [...document.images].filter((image) => {
            const style = getComputedStyle(image), rect = image.getBoundingClientRect();
            return style.display !== 'none' && style.visibility === 'visible' && Number(style.opacity) > 0 && image.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) &&
              rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < innerHeight && rect.right > 0 && rect.left < innerWidth;
          });
          return (await Promise.all(visible.map(async (image) => {
            const sourceBefore = image.currentSrc || image.src;
            const selector = image.id ? '#' + CSS.escape(image.id) : 'img[src=' + JSON.stringify(image.getAttribute('src')) + ']';
            let decodeError = null;
            try { await image.decode(); if (!image.naturalWidth) throw new Error('decoded image has no pixels'); }
            catch (error) { decodeError = String(error?.message || error); }
            const sourceAfter = image.currentSrc || image.src;
            if (sourceBefore !== sourceAfter) return { selector, url: sourceAfter,
              code: 'proof-media-source-unstable', source_before: sourceBefore, source_after: sourceAfter,
              error: 'The visible image source changed during decode. This is an unsettled image sequence, not proof that its media file is broken; use the full recorded source study or an observable settled source state.' };
            return decodeError ? { selector, url: sourceAfter, code: 'proof-visible-media-decode-failed', error: decodeError } : null;
          }))).filter(Boolean);
        }));
        if (mediaProblems.length) {
          const unsettled = mediaProblems.every((item) => item.code === 'proof-media-source-unstable');
          throw Object.assign(new Error(unsettled
            ? `${profile}: visible source image sequence changed while capturing one settled proof state; the source is not classified as broken, and the unsettled frame and exact source URLs are retained.`
            : `${profile}: ${mediaProblems.length} visible source media asset(s) could not be decoded; the unsettled frame and exact targets are retained.`),
          { code: unsettled ? 'proof-media-source-unstable' : 'proof-visible-media-decode-failed', media_problems: mediaProblems });
        }
        await requireUnblockedConsent(page, { captureEvidence: (label, targetPage = page) => shot(targetPage, profile, label), notes });
        const before = await shot(page, profile, 'before');
        let appearance = null;
        const application = await study.step(`proof:${profile}:selected-state`, () => applyManifestState(page, selected, { sourceOnly: true,
          onAmbientAppearance: selected.trigger.type === 'ambient' ? async (appearancePage) => { appearance = await shot(appearancePage, profile, 'appearance'); } : undefined }),
          { timeout_ms: selected.trigger.type === 'ambient' ? selected.trigger.wait_ms + 10_000 : 30_000 });
        const after = appearance || await shot(page, profile, 'after');
        await study.step(`proof:${profile}:state-settle`, () => page.waitForTimeout(220));
        const closedRoots = await study.step(`proof:${profile}:closed-root-coverage`, () => discoverUnaddressableClosedRoots(page, { viewportOnly: true }));
        if (closedRoots.length) throw Object.assign(new Error(`${profile}: visible closed-shadow material at ${closedRoots[0].host_selector || closedRoots[0].host_description} is inaccessible to the proof's exact component/state protocol; this is a harness gap, not a source-quality defect.`),
          { code: 'proof-closed-shadow-root-unaddressable', closed_shadow_roots: closedRoots, source_harness_gap: true });
        const structure = await study.step(`proof:${profile}:arrangement`, () => page.evaluate(STRUCTURE_SCRIPT));
        if (!structure?.dominant) throw Object.assign(new Error(`${profile}: selected proof state has no visible arrangement.`), { code: 'proof-arrangement-empty' });
        const sampled = await study.step(`proof:${profile}:components`, () => page.evaluate(() => {
          const selectorFor = (element) => {
            if (element.id && document.querySelectorAll('#' + CSS.escape(element.id)).length === 1) return '#' + CSS.escape(element.id);
            const parts = []; let current = element;
            while (current && current !== document.documentElement) {
              const parent = current.parentElement; if (!parent) return null;
              const siblings = [...parent.children].filter((item) => item.tagName === current.tagName);
              parts.unshift(current.tagName.toLowerCase() + ':nth-of-type(' + (siblings.indexOf(current) + 1) + ')'); current = parent;
            }
            return 'html > ' + parts.join(' > ');
          };
          const properties = ['font-family', 'font-size', 'font-weight', 'line-height', 'letter-spacing', 'color', 'background-color', 'background-image',
            'padding', 'margin', 'gap', 'display', 'grid-template-columns', 'border-color', 'border-radius', 'box-shadow', 'transform', 'object-fit', 'object-position',
            'width', 'height', 'min-width', 'min-height', 'max-width', 'max-height', 'box-sizing', 'align-items', 'justify-content', 'align-content', 'justify-items',
            'flex-direction', 'flex-wrap', 'grid-template-rows', 'position', 'top', 'right', 'bottom', 'left', 'z-index', 'border-width', 'border-style',
            'text-transform', 'text-align', 'overflow', 'visibility', 'opacity', 'aspect-ratio', 'background-position', 'background-size', 'background-repeat',
            'transition-property', 'transition-duration', 'transition-timing-function', 'animation-name', 'animation-duration', 'cursor'];
          const documentStyles = Object.fromEntries([['html', document.documentElement], ['body', document.body]].map(([role, element]) => {
            const style = getComputedStyle(element); return [role, Object.fromEntries(properties.map((property) => [property, style.getPropertyValue(property)]))];
          }));
          const components = [...document.querySelectorAll('body *')].flatMap((element) => {
            const style = getComputedStyle(element), rect = element.getBoundingClientRect();
            if (!element.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) || style.display === 'none' || style.visibility !== 'visible' || Number(style.opacity) === 0 || rect.width < 1 || rect.height < 1 ||
                rect.bottom <= 0 || rect.right <= 0 || rect.top >= innerHeight || rect.left >= innerWidth) return [];
            const selector = selectorFor(element); if (!selector) return [];
            return [{ selector, component_key: element.id ? 'id:' + element.id : element.getAttribute('data-design-dna-component') ?
              'component:' + element.getAttribute('data-design-dna-component') : 'selector:' + selector,
              tag: element.tagName.toLowerCase(), role: element.getAttribute('role'),
              control: element.matches('a[href],button,input,select,textarea,summary,[role="button"],[role="link"],[role="tab"],[role="checkbox"],[role="switch"],[contenteditable="true"]'),
              text: (element.textContent || '').replace(/\s+/g, ' ').trim(),
              rect: { left: rect.left, top: rect.top, width: rect.width, height: rect.height },
              properties: Object.fromEntries(properties.map((property) => [property, style.getPropertyValue(property)])),
              media: { tag: element.tagName.toLowerCase(), source_url: element.currentSrc || element.src || null,
                object_fit: style.objectFit, object_position: style.objectPosition } }];
          });
          return { components, document_styles: documentStyles };
        }));
        const components = sampled.components;
        proofDocumentStyles[profile] = sampled.document_styles;
        for (const row of components) {
          study.markTarget(`${profile}|${selected.id}|${row.selector}`);
          proofComponentMaps.push({ ...row, profile, state_id: selected.id, text_sha256: sha(Buffer.from(row.text, 'utf8')) });
        }
        const settled = await shot(page, profile, 'settled');
        states[profile] = { [selected.id]: { ...selected, navigation, trigger_application: application, trigger_evidence: application.trigger_evidence,
          evidence_frames: { before, after, settled }, structure, proof_only: true } };
        firstScreens[profile] = structure; captures[profile] = settled;
        inventory[profile] = { profile, complete: false, scope: 'proof-first-screen-only', pages: [{ url: selected.url,
          targets: components.filter((row) => row.control).map((row) => ({ selector: row.selector, tag: row.tag, role: row.role,
            kind: row.tag === 'a' ? 'link' : row.tag === 'button' ? 'button' : row.role || row.tag, component_key: row.component_key,
            source_state_id: selected.id, inputs: [], complete: false })),
          dom_code_inventory: { assets: [...new Set(components.map((row) => row.media.source_url).filter(Boolean))] } }] };
        study.markState(`${profile}:${selected.id}`, { profile, proof_only: true });
      } finally { await context.close().catch(() => {}); }
    }
    const completed = study.complete({ terminal_success: true, coverage_complete: true, proof_only: true,
      signed_artifacts: Object.values(captures).map((frame) => ({ ...frame, kind: 'frame', producer: 'observe_reference.mjs' })) });
    const boundStudy = { ...completed, progress: { file: path.basename(study.progressFile), bytes: fs.statSync(study.progressFile).size, sha256: sha(fs.readFileSync(study.progressFile)) },
      progress_events: { file: path.basename(study.eventFile), bytes: fs.statSync(study.eventFile).size, sha256: sha(fs.readFileSync(study.eventFile)) } };
    const record = { schema_version: SCHEMA_VERSION, tool: 'observe_reference.mjs', producer_script_sha256: PRODUCER_SCRIPT_SHA256,
      runtime_identity: runtimeIdentity, dependencies: {
        observer: { file: 'observe_reference.mjs', sha256: PRODUCER_SCRIPT_SHA256 }, structure_probe: { file: 'structure_probe.mjs', sha256: STRUCTURE_PROBE_SHA256 },
        browser_evidence: { file: 'browser_evidence.mjs', sha256: BROWSER_EVIDENCE_SHA256 }, playwright_resolver: { file: 'playwright_resolver.mjs', sha256: PLAYWRIGHT_RESOLVER_SHA256 },
        source_surface_watch: { file: 'source_surface_watch.mjs', sha256: SOURCE_SURFACE_WATCH_SHA256 }, source_study_controller: { file: 'source_study_controller.mjs', sha256: SOURCE_STUDY_CONTROLLER_SHA256 },
        playwright: loaded.dependency, browser_executable: browserDependency },
      id: args.id, url: args.url, requested_url: args.url, final_url: navigations[0].final_url, observed_at: new Date().toISOString(),
      source_kind: 'proof-slice', source_status: 'complete', eligible_for_source_selection: false,
      source_study: boundStudy, state_contract: { file: path.basename(stateContract.file), sha256: stateContract.sha256 },
      states_by_viewport: states, first_screens: firstScreens, captures_by_viewport: captures,
      proof_component_maps: proofComponentMaps, proof_document_styles: proofDocumentStyles, interaction_census_by_viewport: inventory,
      frame_dir: path.basename(frameDir), frames, navigations,
      coverage: { scope: 'primary-first-screen-selected-state-only', complete: false, proof_complete: true, recursive_routes: false, full_interaction_study: false } };
    const file = path.join(args.outDir, `${args.id}-observation.json`);
    writeJsonAtomically(file, record);
    process.stdout.write(JSON.stringify({ ok: true, source_kind: 'proof-slice', eligible_for_source_selection: false,
      observation: file, sha256: sha(fs.readFileSync(file)), profiles: ['wide', 'narrow'], source_state_id: selected.id,
      disposition: 'internal-unverified-proof-source-only; first-screen gate has not run' }, null, 2) + '\n');
  } catch (error) {
    const terminal = error?.source_study ? error : study.terminate(error?.code || 'source-study-proof-capture-failed', String(error?.message || error),
      { source_error: String(error?.message || error), media_problems: error?.media_problems || null,
        closed_shadow_roots: error?.closed_shadow_roots || null, source_harness_gap: error?.source_harness_gap === true });
    const failure = writeObservationFailureReport(args, stateContract, frameDir,
      frames.map((frame) => ({ ...frame, file: path.basename(frame.file) })), runtimeIdentity, terminal);
    throw Object.assign(error, { source_study: terminal.source_study, source_study_progress: terminal.source_study_progress,
      source_study_failure: terminal.source_study_failure, failure_report: failure });
  } finally { await browser?.close().catch(() => {}); }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const leaseOptions = { output_dir: args.outDir, id: args.id, producer: 'observe_reference.mjs' };
  const outputLease = acquireSourceStudyOutputLease(leaseOptions);
  let lease;
  try { lease = acquireSourceStudyRunnerLease(leaseOptions); return await observeMain(args); }
  finally { lease?.release(); outputLease.release(); }
}

async function observeMain(args) {
  for (const suffix of ['-observation.json', '-source-study-progress.json', '-source-study-progress.jsonl', '-source-study-failure.json']) {
    if (fs.existsSync(path.join(args.outDir, `${args.id}${suffix}`))) {
      throw Object.assign(new Error(`Observation output already exists for ${args.id}; use a fresh output directory to retain prior evidence.`), { code: 'source-study-existing-output' });
    }
  }
  const loaded = loadPlaywright();
  const pw = loaded.playwright;
  const stateContract = readStateContract(args.stateContract, args.id, args.url);
  const browserDependency = loadBrowserDependency(loaded, args.browserExecutable);
  if (args.proofSource) return captureProofSource(args, stateContract, loaded, browserDependency);
  const browserExecutable = browserDependency.file;
  if (!loaded.dependency.resolved_file_sha256 || !browserExecutable) {
    fail("browser-dependency-identity", "The Playwright entry and exact browser executable must both be readable and hashable.");
  }
  const browserExecutableSha256 = browserDependency.sha256;
  fs.mkdirSync(args.outDir, { recursive: true });
  const frameDir = path.join(args.outDir, `${args.id}-frames`);
  fs.mkdirSync(frameDir, { recursive: true });

  const frames = [];
  const interactions = [];
  const notes = [];
  const navigations = [];
  let n = 0;

  const browser = await pw.chromium.launch(
    { executablePath: browserExecutable }
  );
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });
  await installDomInspection(context);
  const page = await context.newPage();
  const sourceStudy = createSourceStudyController({
    output_dir: args.outDir, id: args.id, producer: 'observe_reference.mjs', source_kind: 'public-source',
    required_completion_artifact_kinds: ['frame'],
    abort: async () => { await context.close().catch(() => {}); },
    partial_evidence: () => ({
      frames: frames.map((frame) => ({ ...frame, file: `${path.basename(frameDir)}/${frame.file}` })),
      interactions: interactions.slice(), notes: notes.slice(), navigations: navigations.slice(),
    }),
  });

  async function shotOn(targetPage, kind, note, viewport = { width: 1440, height: 900 }) {
    n += 1;
    const safeKind = String(kind).toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "");
    const file = `${args.id}-${String(n).padStart(5, "0")}-${safeKind}.png`;
    const buf = await sourceStudy.step(`screenshot:${safeKind}`,
      () => targetPage.screenshot({ path: path.join(frameDir, file) }), {
        screenshot: true, detail: { kind: safeKind, viewport },
        abort: async () => { await targetPage.context().close().catch(() => {}); },
      });
    const rec = { seq: n, kind: safeKind, file, bytes: buf.length, sha256: sha(buf), viewport, note: note || null };
    frames.push(rec);
    sourceStudy.markFrame({ file: `${path.basename(frameDir)}/${file}`, sha256: rec.sha256, kind: safeKind });
    return rec;
  }
  const shot = (kind, note) => shotOn(page, kind, note);
  const boundEvidenceShot = async (targetPage, kind, note, viewport) => {
    const frame = await shotOn(targetPage, kind, note, viewport);
    return { ...frame, file: `${path.basename(frameDir)}/${frame.file}` };
  };

  try {
    const primaryAmbientSelectors = stateContract.payload.states.filter((state) => state.trigger?.type === 'ambient').map((state) => state.trigger.target);
    const primaryEarlyBaseline = await boundEvidenceShot(page, 'wide-primary-early-before-navigation', 'wide early source-surface baseline', { width: 1440, height: 900 });
    const primaryEarlyWatch = await armEarlySourceSurfaceWatch(page, {
      ambientSelectors: primaryAmbientSelectors, baseline: primaryEarlyBaseline, labelPrefix: 'wide-primary-early-autonomous-surface',
      captureEvidence: (label, targetPage = page) => boundEvidenceShot(targetPage, label, 'wide early source-surface evidence', { width: 1440, height: 900 }),
    });
    sourceStudy.markRoute(args.url, { profile: 'wide', phase: 'primary-rest' });
    const primaryNavigation = await sourceStudy.step('navigate:wide:primary-rest', () => navigateExact(page, args.url), {
      detail: { url: args.url }, abort: async () => { await context.close().catch(() => {}); },
    });
    navigations.push({ profile: "wide", purpose: "primary-rest", ...primaryNavigation });
    await page.evaluate(() => document.fonts?.ready).catch(() => {});
    await page.waitForTimeout(3000);

    const primaryConsent = await requireUnblockedConsent(page, {
      notes,
      labelPrefix: 'wide-primary-consent',
      captureEvidence: (label, targetPage = page) => boundEvidenceShot(targetPage, label, 'constrained consent disposition', { width: 1440, height: 900 }),
    });
    const primarySurfaceBaseline = await boundEvidenceShot(page, 'wide-primary-autonomous-baseline', 'wide source-surface baseline', { width: 1440, height: 900 });
    let primarySurfaceWatch = await adoptEarlySourceSurfaceWatch(page, primaryEarlyWatch, {
      ambientSelectors: primaryAmbientSelectors, baseline: primarySurfaceBaseline,
      authorizedConsent: primaryConsent.dismissed ? [primaryConsent] : [], labelPrefix: 'wide-primary-autonomous-surface',
      captureEvidence: (label, targetPage = page) => boundEvidenceShot(targetPage, label, 'wide source-surface evidence', { width: 1440, height: 900 }),
    });
    const closePrimarySurfaceWatch = async (phase) => {
      if (!primarySurfaceWatch) return null;
      const watch = primarySurfaceWatch;
      // Clear ownership before async drain/stop so a failure cleanup cannot
      // accidentally drain or stop the same page-local watch twice.
      primarySurfaceWatch = null;
      let report;
      try {
        report = await drainSourceSurfaceWatch(watch, {
          labelPrefix: 'wide-primary-autonomous-surface',
          captureEvidence: (label, targetPage = page) => boundEvidenceShot(targetPage, label, 'wide source-surface evidence', { width: 1440, height: 900 }),
        });
      } finally { await stopSourceSurfaceWatch(watch); }
      if (report.events.length) notes.push({ kind: 'autonomous-surface-watch', profile: 'wide', page_url: page.url(), report });
      const undocumented = undocumentedSourceSurfaceError(report, { profile: 'wide', phase });
      if (undocumented) throw undocumented;
      return report;
    };

    // --- at rest
    const rest0 = await shot("rest", "at rest, first frame");
    await page.waitForTimeout(REST_SETTLE_MS);
    const rest1 = await shot("rest", "at rest, after settle delay, no input");
    const restMoved = rest0.sha256 !== rest1.sha256;
    const restAnimations = await page.evaluate(() => document.getAnimations()
      .filter((animation) => animation.playState === 'running').length).catch(() => 0);
    const restAnimated = restMoved && restAnimations > 0;
    interactions.push({
      type: "rest", moved: restAnimated, pixel_hash_changed: restMoved, active_animations: restAnimations,
      frames: [rest0.seq, rest1.seq],
      detail: restAnimated ? "The page changed with no input and exposed an active animation."
        : restMoved ? "Pixels changed, but no active animation was measured; this alone is not classified as at-rest motion."
          : "The page was still with no input.",
    });

    // --- the structure of the first screen, before anything is scrolled.
    // A property reader can see a font size; only this can see that the first
    // screen is a photograph with the wordmark pushed into the corners.
    const firstScreen = await page.evaluate(STRUCTURE_SCRIPT);

    // References are measured at both mandatory build profiles. A wide home
    // capture cannot prove the source of a narrow composition.
    const narrowContext = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
    await installDomInspection(narrowContext);
    const narrowPage = await narrowContext.newPage();
    const narrowEarlyBaseline = await boundEvidenceShot(narrowPage, 'narrow-primary-early-before-navigation', 'narrow early source-surface baseline', { width: 390, height: 844 });
    const narrowEarlyWatch = await armEarlySourceSurfaceWatch(narrowPage, {
      ambientSelectors: primaryAmbientSelectors, baseline: narrowEarlyBaseline, labelPrefix: 'narrow-primary-early-autonomous-surface',
      captureEvidence: (label, targetPage = narrowPage) => boundEvidenceShot(targetPage, label, 'narrow early source-surface evidence', { width: 390, height: 844 }),
    });
    sourceStudy.markRoute(args.url, { profile: 'narrow', phase: 'primary-rest' });
    const narrowNavigation = await sourceStudy.step('navigate:narrow:primary-rest', () => navigateExact(narrowPage, args.url), {
      detail: { url: args.url }, abort: async () => { await narrowContext.close().catch(() => {}); },
    });
    navigations.push({ profile: "narrow", purpose: "primary-rest", ...narrowNavigation });
    await narrowPage.evaluate(() => document.fonts?.ready).catch(() => {});
    await narrowPage.waitForTimeout(700);
    const narrowConsent = await requireUnblockedConsent(narrowPage, {
      notes,
      labelPrefix: 'narrow-primary-consent',
      captureEvidence: (label, targetPage = narrowPage) => boundEvidenceShot(targetPage, label, 'constrained consent disposition', { width: 390, height: 844 }),
    });
    const narrowSurfaceBaseline = await boundEvidenceShot(narrowPage, 'narrow-primary-autonomous-baseline', 'narrow source-surface baseline', { width: 390, height: 844 });
    const narrowSurfaceWatch = await adoptEarlySourceSurfaceWatch(narrowPage, narrowEarlyWatch, {
      ambientSelectors: primaryAmbientSelectors, baseline: narrowSurfaceBaseline,
      authorizedConsent: narrowConsent.dismissed ? [narrowConsent] : [], labelPrefix: 'narrow-primary-autonomous-surface',
      captureEvidence: (label, targetPage = narrowPage) => boundEvidenceShot(targetPage, label, 'narrow source-surface evidence', { width: 390, height: 844 }),
    });
    const narrowFirstScreen = await narrowPage.evaluate(STRUCTURE_SCRIPT);
    const narrowFrame = await shotOn(narrowPage, "narrow-rest", "narrow first screen at rest", { width: 390, height: 844 });
    const narrowFrameFile = narrowFrame.file;
    const narrowMechanism = await mechanismPass(narrowPage);
    let narrowSurfaceReport;
    try {
      narrowSurfaceReport = await drainSourceSurfaceWatch(narrowSurfaceWatch, {
        labelPrefix: 'narrow-primary-autonomous-surface',
        captureEvidence: (label, targetPage = narrowPage) => boundEvidenceShot(targetPage, label, 'narrow source-surface evidence', { width: 390, height: 844 }),
      });
    } finally { await stopSourceSurfaceWatch(narrowSurfaceWatch); }
    if (narrowSurfaceReport.events.length) notes.push({ kind: 'autonomous-surface-watch', profile: 'narrow', page_url: args.url, report: narrowSurfaceReport });
    const narrowUndocumented = undocumentedSourceSurfaceError(narrowSurfaceReport, { profile: 'narrow', phase: 'primary-pre-traversal' });
    if (narrowUndocumented) throw narrowUndocumented;
    await narrowContext.close();

    // --- is anything on the first screen actually a video, not a photo
    const ambientVideos = await checkAmbientVideo(page);

    // --- the mechanism pass
    const mech = await mechanismPass(page);
    mech.mechanisms.push(...ambientVideos);

    // --- scroll holds across every native/transform surface, with no sampled
    // first-N cutoff. Any surface that does not reach a terminal state blocks.
    let scrollMoved = 0;
    let steps = 0;
    const scrollHoldTraversal = await sourceStudy.step('scroll-traversal:wide-primary', () => traverseScrollSurfaces(page, { maxTicks: 240, settleMs: 120,
      onTick: async (surface, tick) => {
       steps += 1;
       sourceStudy.markTarget(`wide|scroll|${surface.id}|${tick}`, { phase: 'primary-scroll', surface: surface.id, tick });
       const a = await shot("scroll-arrive", `arrived at ${surface.kind}:${surface.selector_hint || surface.id} wheel step ${tick}`);
      await page.waitForTimeout(HOLD_MS);
      const b = await shot("scroll-settle", `held for ${HOLD_MS}ms after wheel step ${tick}`);
      const moved = a.sha256 !== b.sha256;
      if (moved) scrollMoved += 1;
       interactions.push({
        type: "scroll-hold", surface: surface.id, step: tick, moved, frames: [a.seq, b.seq],
        detail: moved ? "Content changed while the page sat still here, so something animated into place." : "Nothing changed while the page sat still here.",
       });
       sourceStudy.markEvent({ profile: 'wide', kind: 'scroll-hold', surface: surface.id, tick });
       mech.mechanisms.push(...(await checkAmbientVideo(page)));
    } }), { timeout_ms: 180_000, detail: { phase: 'primary-scroll' }, abort: async () => { await context.close().catch(() => {}); } });
    if (!scrollHoldTraversal.complete) throw new Error("Scroll-hold capture did not fully traverse every scroll surface.");
    // one line per distinct video, not one per scroll step it was visible on
    {
      const seenVideo = new Set();
      for (let i = mech.mechanisms.length - 1; i >= 0; i -= 1) {
        const m = mech.mechanisms[i];
        if (m.tag !== "video") continue;
        const k = `${m.src}|${m.w}x${m.h}`;
        if (seenVideo.has(k)) mech.mechanisms.splice(i, 1); else seenVideo.add(k);
      }
    }

    // --- hover: real pointer over real interactive elements, with timing
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(600);
    let hoverMoved = 0;
    let hoverTried = 0;
    let hoverFailed = 0;
    const hoverDurations = [];
    const targets = (await Promise.all(page.frames().map((frame) =>
      frame.locator("a, button, [role=button], li, article, figure, img").all()))).flat();
    for (const el of targets) {
      let box = null;
      try {
        if (!(await el.isVisible())) continue;
        await el.scrollIntoViewIfNeeded(); await page.waitForTimeout(120);
        box = await el.boundingBox();
      } catch (e) { box = null; }
      if (!box || box.width < 24 || box.height < 24) continue;
      hoverTried += 1;
      const targetKey = await sourceStudy.step('target-identity:wide-primary-hover', () => el.evaluate((node) => {
        const classes = typeof node.className === 'string' ? node.className.split(/\s+/).filter(Boolean).sort().join('.') : '';
        return `${node.tagName.toLowerCase()}|${node.id || ''}|${node.getAttribute('data-dna-interaction-id') || ''}|${classes}`;
      }), { timeout_ms: 10_000, detail: { ordinal: hoverTried }, abort: async () => { await context.close().catch(() => {}); } });
      sourceStudy.markTarget(`wide|primary-hover|${targetKey}`, { ordinal: hoverTried });
      try {
        await page.mouse.move(4, 4);
        await page.waitForTimeout(200);
        const before = await shot("hover-before", "pointer away");
        const beforeStyles = await el.evaluate((node) => [node, ...node.querySelectorAll('*')].map((item) => {
        const style = getComputedStyle(item), box = item.getBoundingClientRect();
        return [style.color, style.backgroundColor, style.transform, style.opacity, style.filter, style.clipPath,
          Math.round(box.left), Math.round(box.top), Math.round(box.width), Math.round(box.height)];
        }));
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
        await page.waitForTimeout(650);
        const after = await shot("hover-after", "pointer over an interactive element");
        const afterStyles = await el.evaluate((node) => [node, ...node.querySelectorAll('*')].map((item) => {
        const style = getComputedStyle(item), box = item.getBoundingClientRect();
        return [style.color, style.backgroundColor, style.transform, style.opacity, style.filter, style.clipPath,
          Math.round(box.left), Math.round(box.top), Math.round(box.width), Math.round(box.height)];
        }));
        const moved = JSON.stringify(beforeStyles) !== JSON.stringify(afterStyles);
        if (moved) hoverMoved += 1;
        const duration = await el.evaluate((node) => {
          const c = getComputedStyle(node);
          const d = c.transitionDuration.split(",").map((s) => parseFloat(s) * (s.trim().endsWith("ms") ? 1 : 1000));
          return { ms: Math.max(...d, 0), easing: c.transitionTimingFunction, property: c.transitionProperty };
        });
        if (moved && duration.ms > 0) hoverDurations.push(duration);
        interactions.push({ type: "hover", moved, page_hash_changed: before.sha256 !== after.sha256,
          frames: [before.seq, after.seq], transition: duration,
          detail: moved ? "The page responded to the pointer." : "Nothing responded to the pointer here." });
        sourceStudy.markEvent({ profile: 'wide', kind: 'hover', target_key: targetKey, moved });
      } catch { hoverFailed += 1; }
    }
    if (hoverFailed) throw new Error(`${hoverFailed} of ${hoverTried} visible hover targets could not be completely observed.`);
    if (hoverDurations.length) {
      const ms = Math.round(median(hoverDurations.map((d) => d.ms)));
      mech.mechanisms.push({
        type: "hover-transition", ms, easing: hoverDurations[0].easing, responded: hoverMoved,
        detail: `hovered controls transition over ~${ms}ms`,
      });
    }

    // --- click through one in-page link and watch the transition
    let transition = { type: "transition", attempted: false, moved: false, frames: [], detail: "No same-origin link was available to follow." };
    try {
      const origin = new URL(args.url).origin;
      const href = await page.evaluate((o) => {
        const a = Array.from(document.querySelectorAll("a[href]")).find((x) => {
          try {
            const u = new URL(x.href, location.href);
            return u.origin === o && u.pathname !== location.pathname && !x.href.includes("#");
          } catch (e) { return false; }
        });
        return a ? a.href : null;
      }, origin);
      if (href) {
        await page.mouse.move(4, 4);
        const before = await shot("transition-before", "before following a link");
        // A page-scoped observer is destroyed by document navigation. Drain it
        // while its evidence is still reachable, then arm a fresh early watch
        // before the destination document begins. This is a lifecycle handoff,
        // not permission to discard the first document's surface ledger.
        await closePrimarySurfaceWatch('primary-before-transition');
        const transitionEarlyBaseline = await boundEvidenceShot(page, 'wide-transition-early-before-navigation',
          'wide transition early source-surface baseline', { width: 1440, height: 900 });
        const transitionEarlyWatch = await armEarlySourceSurfaceWatch(page, {
          ambientSelectors: primaryAmbientSelectors, baseline: transitionEarlyBaseline,
          labelPrefix: 'wide-transition-early-autonomous-surface',
          captureEvidence: (label, targetPage = page) => boundEvidenceShot(targetPage, label,
            'wide transition early source-surface evidence', { width: 1440, height: 900 }),
        });
        sourceStudy.markRoute(href, { profile: 'wide', phase: 'primary-transition' });
        const transitionNavigation = await sourceStudy.step('navigate:wide:primary-transition', () => navigateExact(page, href, { timeout: 45000 }), {
          timeout_ms: 45_000, detail: { url: href }, abort: async () => { await context.close().catch(() => {}); },
        });
        navigations.push({ profile: "wide", purpose: "transition", ...transitionNavigation });
        await page.evaluate(() => document.fonts?.ready).catch(() => {});
        const transitionSurfaceBaseline = await boundEvidenceShot(page, 'wide-transition-autonomous-baseline',
          'wide transition source-surface baseline', { width: 1440, height: 900 });
        primarySurfaceWatch = await adoptEarlySourceSurfaceWatch(page, transitionEarlyWatch, {
          ambientSelectors: primaryAmbientSelectors, baseline: transitionSurfaceBaseline,
          labelPrefix: 'wide-transition-autonomous-surface',
          captureEvidence: (label, targetPage = page) => boundEvidenceShot(targetPage, label,
            'wide transition source-surface evidence', { width: 1440, height: 900 }),
        });
        await page.waitForTimeout(260);
        const during = await shot("transition-during", "shortly after navigation started");
        const duringActivity = await page.evaluate(() => document.getAnimations().map((animation) => {
          const timing = animation.effect?.getComputedTiming?.() || {};
          const target = animation.effect?.target;
          return { play_state: animation.playState, current_time: Number(animation.currentTime || 0),
            end_time: Number(timing.endTime || 0), iterations: Number(timing.iterations),
            target: target ? `${target.tagName.toLowerCase()}.${typeof target.className === 'string' ? target.className.slice(0, 48) : ''}` : null };
        }).filter((animation) => animation.play_state === 'running' && Number.isFinite(animation.iterations) &&
          animation.iterations <= 1 && animation.end_time - animation.current_time > 120));
        await page.waitForTimeout(2200);
        const settled = await shot("transition-settled", "destination settled");
        const settledActivity = await page.evaluate(() => document.getAnimations()
          .filter((animation) => animation.playState === 'running').length);
        const staged = duringActivity.length > 0 && (settledActivity < duringActivity.length || duringActivity.some((animation) => animation.end_time > animation.current_time));
        transition = {
          type: "transition", attempted: true, url: href,
          navigation: transitionNavigation,
          moved: staged,
          frames: [before.seq, during.seq, settled.seq],
          visual_hash_changed: during.sha256 !== settled.sha256,
          active_arrival_animations: duringActivity,
          detail: staged ? "The destination exposed active arrival animation after navigation."
            : "No active arrival animation was measured; later pixel changes alone are not treated as a page transition.",
        };
      }
    } catch (e) {
      if (e?.code) throw e;
      const transitionError = new Error(`Exact transition navigation failed: ${String(e).slice(0, 220)}`);
      transitionError.code = 'transition-navigation-failed';
      throw transitionError;
    }
    interactions.push(transition);
    if (transition.moved) mech.mechanisms.push({ type: "page-transition", detail: "the next page arrived animated or staged" });
    if (restAnimated) mech.mechanisms.push({ type: "at-rest", detail: "a measured animation plays with no input" });

    // Exact source-state sheets are producer-authored contracts, not names
    // guessed by the observer. Separately, every recursively discovered page
    // and every native/transform scroll surface is traversed at both profiles.
    await closePrimarySurfaceWatch('primary-pre-traversal');

    const statesByViewport = {
      wide: await captureSourceStates(browser, stateContract.payload, { name: "wide", width: 1440, height: 900 },
        (targetPage, label) => boundEvidenceShot(targetPage, label, "source state interaction evidence", { width: 1440, height: 900 }), notes, sourceStudy),
      narrow: await captureSourceStates(browser, stateContract.payload, { name: "narrow", width: 390, height: 844 },
        (targetPage, label) => boundEvidenceShot(targetPage, label, "source state interaction evidence", { width: 390, height: 844 }), notes, sourceStudy),
    };
    const wideSiteTraversal = await studyRecursiveSite(page, args.url, "wide", stateContract.payload.states,
      (label, evidencePage = page) => boundEvidenceShot(evidencePage, `wide-${label}`, "wide interaction-census evidence", { width: 1440, height: 900 }), notes, sourceStudy);
    const narrowSiteContext = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
    await installDomInspection(narrowSiteContext);
    const narrowSitePage = await narrowSiteContext.newPage();
    const narrowSiteTraversal = await studyRecursiveSite(narrowSitePage, args.url, "narrow", stateContract.payload.states,
      (label, evidencePage = narrowSitePage) => boundEvidenceShot(evidencePage, `narrow-${label}`, "narrow interaction-census evidence", { width: 390, height: 844 }), notes, sourceStudy);
    await narrowSiteContext.close();
    if (!wideSiteTraversal.complete || !narrowSiteTraversal.complete) throw new Error("Recursive wide+narrow site traversal is incomplete.");

    const combinedWide = mergeMechanismSheets([
      wideSiteTraversal.sheet,
      { mechanisms: mech.mechanisms, score: mech.score },
      ...Object.values(statesByViewport.wide).map((state) => ({ mechanisms: state.mechanisms, score: state.score })),
    ]);
    const combinedNarrow = mergeMechanismSheets([
      narrowSiteTraversal.sheet,
      narrowMechanism,
      ...Object.values(statesByViewport.narrow).map((state) => ({ mechanisms: state.mechanisms, score: state.score })),
    ]);
    const interactionCensusByViewport = {
      wide: mergeInteractionCensuses("wide", [wideSiteTraversal.interaction_census,
        ...Object.values(statesByViewport.wide).map((state) => state.interaction_census)]),
      narrow: mergeInteractionCensuses("narrow", [narrowSiteTraversal.interaction_census,
        ...Object.values(statesByViewport.narrow).map((state) => state.interaction_census)]),
    };
    const renderedQAByViewport = {
      wide: mergeSourceRenderedQA("wide", [wideSiteTraversal.rendered_qa,
        ...Object.values(statesByViewport.wide).map((state) => state.rendered_qa)]),
      narrow: mergeSourceRenderedQA("narrow", [narrowSiteTraversal.rendered_qa,
        ...Object.values(statesByViewport.narrow).map((state) => state.rendered_qa)]),
    };
    if (!interactionCensusByViewport.wide.complete || !interactionCensusByViewport.narrow.complete ||
        interactionCensusByViewport.wide.truncated || interactionCensusByViewport.narrow.truncated) {
      const profile = !interactionCensusByViewport.wide.complete || interactionCensusByViewport.wide.truncated ? 'wide' : 'narrow';
      throw interactionCensusIncompleteError(interactionCensusByViewport[profile],
        { phase: 'wide-narrow-aggregate', source_state_id: null, pass: 1 });
    }
    mech.mechanisms = finalizeMechanisms(combinedWide.mechanisms);
    mech.score = combinedWide.score;
    for (const mechanism of mech.mechanisms) {
      if (!(mechanism.type in mech.score.type_instances)) mech.score.type_instances[mechanism.type] = 1;
    }

    const distinct = new Set(mech.mechanisms.map((m) => m.type)).size;
    const motionObserved = restAnimated || scrollMoved > 0 || hoverMoved > 0 || transition.moved === true || mech.mechanisms.length > 0;
    const capturesByViewport = {
      wide: { file: `${path.basename(frameDir)}/${rest0.file}`, bytes: rest0.bytes, sha256: rest0.sha256 },
      narrow: { file: `${path.basename(frameDir)}/${narrowFrameFile}`, bytes: narrowFrame.bytes, sha256: narrowFrame.sha256 },
    };
    const stateCells = Object.entries(statesByViewport).flatMap(([profile, states]) =>
      Object.values(states).map((state) => ({ profile, state_id: state.id, trigger_type: state.trigger.type,
        changed_properties: state.trigger_evidence?.changed_properties?.length || 0,
        mechanism_count: state.trigger_evidence?.mechanism_count || 0 })));
    const qualityObservations = [
      { category: "responsive-first-screen", wide_dominant: firstScreen.dominant, narrow_dominant: narrowFirstScreen.dominant },
      { category: "experience-coverage", wide_pages: wideSiteTraversal.visited_urls.length,
        narrow_pages: narrowSiteTraversal.visited_urls.length, authored_state_cells: stateCells.length },
      { category: "behavior", distinct_mechanisms: distinct, mechanisms: mech.mechanisms.map((item) => item.type),
        responsive_state_results: stateCells },
    ];
    const defectObservations = [
      ...(restMoved && !restAnimated ? [{ category: "unattributed-rest-change", detail: "Pixels changed at rest without a measured active animation." }] : []),
      ...stateCells.filter((cell) => cell.trigger_type !== "none" && cell.changed_properties === 0)
        .map((cell) => ({ category: "declared-state-no-visible-change", ...cell })),
      ...Object.entries(renderedQAByViewport).flatMap(([profile, qa]) => qa.pages.flatMap((pageRecord) => [
        ...['clipping','collisions','fixed_rail_overlaps','dead_controls','semantic_issues']
          .flatMap((category) => (pageRecord[category] || []).map((detail) => ({ category, profile, page_url: pageRecord.url, detail }))),
        ...(pageRecord.hidden_controls || []).filter((control) => control.focusable_while_hidden)
          .map((detail) => ({ category: 'hidden-focusable-control', profile, page_url: pageRecord.url, detail })),
        ...(pageRecord.state_semantics?.complete === false ? [{ category: 'state-semantics', profile,
          page_url: pageRecord.url, detail: pageRecord.state_semantics }] : []),
        ...(pageRecord.keyboard?.complete === false ? [{ category: 'keyboard-path', profile,
          page_url: pageRecord.url, detail: pageRecord.keyboard }] : []),
        ...(pageRecord.semantic_equivalence?.complete === false ? [{ category: 'semantic-equivalence', profile,
          page_url: pageRecord.url, detail: pageRecord.semantic_equivalence }] : []),
        ...(pageRecord.overlays || []).filter((overlay) => !overlay.complete)
          .map((detail) => ({ category: 'overlay-access', profile, page_url: pageRecord.url, detail })),
        ...(!pageRecord.reduced_motion?.honors_preference ? [{ category: 'reduced-motion', profile, page_url: pageRecord.url,
          detail: pageRecord.reduced_motion }] : []),
        ...(pageRecord.dead_end?.problem ? [{ category: 'dead-end', profile, page_url: pageRecord.url,
          detail: pageRecord.dead_end }] : []),
      ])),
    ];
    const sourceStudySnapshot = sourceStudy.complete({
      terminal_success: true,
      signed_artifacts: [{ kind: 'frame', file: `${path.basename(frameDir)}/${rest0.file}`,
        bytes: rest0.bytes, sha256: rest0.sha256, producer: 'observe_reference.mjs' }],
      final_url: primaryNavigation.final_url,
    });
    const sourceStudyBinding = { ...sourceStudySnapshot,
      progress: { file: path.basename(sourceStudy.progressFile), bytes: fs.statSync(sourceStudy.progressFile).size, sha256: sha(fs.readFileSync(sourceStudy.progressFile)) },
      progress_events: { file: path.basename(sourceStudy.eventFile), bytes: fs.statSync(sourceStudy.eventFile).size, sha256: sha(fs.readFileSync(sourceStudy.eventFile)) } };

    const record = {
      schema_version: SCHEMA_VERSION,
      tool: "observe_reference.mjs",
      producer_script_sha256: PRODUCER_SCRIPT_SHA256,
      runtime_identity: { "observe_reference.mjs": PRODUCER_SCRIPT_SHA256, "structure_probe.mjs": STRUCTURE_PROBE_SHA256,
        "browser_evidence.mjs": BROWSER_EVIDENCE_SHA256, "playwright_resolver.mjs": PLAYWRIGHT_RESOLVER_SHA256,
        "source_surface_watch.mjs": SOURCE_SURFACE_WATCH_SHA256,
        "source_study_controller.mjs": SOURCE_STUDY_CONTROLLER_SHA256,
        "playwright-entry": loaded.dependency.resolved_file_sha256,
        "browser-executable": browserExecutableSha256 },
      dependencies: {
        observer: { file: "observe_reference.mjs", sha256: PRODUCER_SCRIPT_SHA256 },
        structure_probe: { file: "structure_probe.mjs", sha256: STRUCTURE_PROBE_SHA256 },
        browser_evidence: { file: "browser_evidence.mjs", sha256: BROWSER_EVIDENCE_SHA256 },
        playwright_resolver: { file: "playwright_resolver.mjs", sha256: PLAYWRIGHT_RESOLVER_SHA256 },
        source_surface_watch: { file: "source_surface_watch.mjs", sha256: SOURCE_SURFACE_WATCH_SHA256 },
        source_study_controller: { file: "source_study_controller.mjs", sha256: SOURCE_STUDY_CONTROLLER_SHA256 },
        playwright: loaded.dependency,
        browser_executable: browserDependency,
      },
      id: args.id,
      source_kind: 'public-source', source_status: 'complete', eligible_for_source_selection: true,
      label: args.label || null,
      url: args.url,
      requested_url: primaryNavigation.requested_url,
      final_url: primaryNavigation.final_url,
      observed_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      viewport: { width: 1440, height: 900 },
      frame_dir: path.basename(frameDir),
      frames,
      source_study: sourceStudyBinding,
      captures_by_viewport: capturesByViewport,
      discovery_metadata: {
        wide: { discovered_urls: wideSiteTraversal.discovered_urls, visited_urls: wideSiteTraversal.visited_urls,
          source_state_ids: Object.keys(statesByViewport.wide) },
        narrow: { discovered_urls: narrowSiteTraversal.discovered_urls, visited_urls: narrowSiteTraversal.visited_urls,
          source_state_ids: Object.keys(statesByViewport.narrow) },
      },
      quality_observations: qualityObservations,
      defect_observations: defectObservations,
      interactions,
      navigations,
      state_contract: { file: path.basename(stateContract.file), sha256: stateContract.sha256 },
      states_by_viewport: statesByViewport,
      site_traversal_by_viewport: { wide: wideSiteTraversal, narrow: narrowSiteTraversal },
      interaction_census_by_viewport: interactionCensusByViewport,
      rendered_qa_by_viewport: renderedQAByViewport,
      coverage: { rest: true, scroll_holds: steps, hovers: hoverTried, transition: transition.attempted,
        wheel_ticks: mech.wheel_ticks, authored_states: stateContract.payload.states.length,
        wide_pages: wideSiteTraversal.visited_urls.length, narrow_pages: narrowSiteTraversal.visited_urls.length,
        wide_complete: wideSiteTraversal.complete, narrow_complete: narrowSiteTraversal.complete },
      motion: {
        observed: motionObserved,
        at_rest: restAnimated,
        on_scroll_holds: scrollMoved,
        on_hover: hoverMoved,
        on_transition: transition.moved === true,
      },
      first_screen: firstScreen,
      first_screens: { wide: firstScreen, narrow: narrowFirstScreen },
      mechanisms: mech.mechanisms,
      mechanisms_by_viewport: {
        wide: { mechanisms: mech.mechanisms, score: mech.score },
        narrow: combinedNarrow,
      },
      first_screen_mechanisms_by_viewport: {
        wide: firstScreenSheet(statesByViewport.wide.rest, 900),
        narrow: firstScreenSheet(statesByViewport.narrow.rest, 844),
      },
      score: { ...mech.score, distinct_mechanisms: distinct },
      notes,
    };
    const outFile = path.join(args.outDir, `${args.id}-observation.json`);
    fs.writeFileSync(outFile, JSON.stringify(record, null, 2) + "\n", "utf8");
    process.stdout.write(
      JSON.stringify(
        {
          ok: true,
          observation: outFile,
          frames: frames.length,
          motion_observed: motionObserved,
          distinct_mechanisms: distinct,
          first_screen: firstScreen.dominant
            ? `${firstScreen.dominant.kind} <${firstScreen.dominant.tag}> fills ${Math.round(firstScreen.dominant.area_share * 100)}%`
            : 'empty',
          scroll_coverage: record.score.scroll_coverage,
          document_scrolls: record.score.document_scrolls,
          mechanisms: mech.mechanisms.map((m) => m.type + (m.held_px ? `(${m.held_px}px)` : "")),
        },
        null,
        2
      ) + "\n"
    );
  } catch (error) {
    if (!error?.source_study && !sourceStudy.closed) {
      const terminal = sourceStudy.terminate(error?.code || 'source-study-observation-failed',
        'Observer terminated before a complete source observation could be emitted; partial evidence is ineligible.',
        { source_code: error?.code || null, source_error: String(error?.message || error) });
      error.source_study = terminal.source_study;
      error.source_study_progress = terminal.source_study_progress;
      error.source_study_failure = terminal.source_study_failure;
    }
    const failureReport = writeObservationFailureReport(args, stateContract, frameDir, frames, {
      "observe_reference.mjs": PRODUCER_SCRIPT_SHA256,
      "structure_probe.mjs": STRUCTURE_PROBE_SHA256,
      "browser_evidence.mjs": BROWSER_EVIDENCE_SHA256,
      "playwright_resolver.mjs": PLAYWRIGHT_RESOLVER_SHA256,
      "source_surface_watch.mjs": SOURCE_SURFACE_WATCH_SHA256,
      "source_study_controller.mjs": SOURCE_STUDY_CONTROLLER_SHA256,
      "playwright-entry": loaded.dependency.resolved_file_sha256,
      "browser-executable": browserExecutableSha256,
    }, error);
    const summary = error?.census_diagnostic
      ? `${String(error.message)} Review the generated incomplete-census report; it is not selection evidence.`
      : String(error?.message || error).slice(0, 1000);
    await browser.close().catch(() => {});
    // Propagate only after retaining the failure artifact. The outer main()
    // finally owns both leases; process.exit here would strand its live slots.
    throw Object.assign(error, { message: summary, failure_report: failureReport });
  } finally {
    await browser.close().catch(() => {});
  }
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url));
if (invokedDirectly) main().catch((error) => emitFailure(error?.code || 'observation-failed', String(error?.message || error), {
  ...(error?.terminal_details || {}),
  interaction_census: error?.census_diagnostic
    ? { profile: error.census_diagnostic.profile, context: error.census_diagnostic.context,
      failures: error.census_diagnostic.failures.length } : null,
  failure_report: error?.failure_report || null, source_study: error?.source_study || null,
  source_study_progress: error?.source_study_progress || null, source_study_failure: error?.source_study_failure || null,
}));
