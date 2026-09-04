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
 * what fraction of the scroll depth had a scroll-linked mechanism active. The
 * dossier gate uses it to refuse a thin site on its own, so nobody has to vet
 * a list by hand.
 *
 * Usage:
 *   node observe_reference.mjs --url https://example.test/ --id strong-1 \
 *        --out .design-dna/references [--browser-executable FILE]
 */
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { STRUCTURE_SCRIPT } from "./structure_probe.mjs";
import { applyManifestState, captureInteractionCensus, captureRenderedQA, collectSameOriginLinks, inferAndReconcileStates, installDomInspection, mergeSourceRenderedQA, navigateExact, normalizeHttpUrl,
  traverseScrollSurfaces, validateManifestState } from "./browser_evidence.mjs";
import { browserExecutableIdentity, discoverBrowserExecutable, resolvePlaywright } from "./playwright_resolver.mjs";

const SCHEMA_VERSION = 5;
const SCRIPT_PATH = path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const PRODUCER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(SCRIPT_PATH)).digest("hex");
const STRUCTURE_PROBE_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "structure_probe.mjs"))).digest("hex");
const BROWSER_EVIDENCE_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "browser_evidence.mjs"))).digest("hex");
const PLAYWRIGHT_RESOLVER_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "playwright_resolver.mjs"))).digest("hex");
const REST_SETTLE_MS = 700;
const HOLD_MS = 900;
// the mechanism pass: many small wheel ticks so a pinned stage, a swap or a
// parallax shows up as a trend across samples rather than a single jump
const TICK_PX = 700;
const TICK_SETTLE_MS = 650;

function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }, null, 2) + "\n");
  process.exit(2);
}

function parseArgs(argv) {
  const out = { url: null, id: null, outDir: null,
    browserExecutable: process.env.DESIGN_DNA_BROWSER_EXECUTABLE || process.env.CHROME || null,
    label: null, stateContract: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--url") out.url = argv[++i];
    else if (a === "--id") out.id = argv[++i];
    else if (a === "--out") out.outDir = argv[++i];
    else if (a === "--label") out.label = argv[++i];
    else if (a === "--state-contract") out.stateContract = argv[++i];
    else if (a === "--browser-executable") out.browserExecutable = argv[++i];
    else if (a === "--help" || a === "-h") {
      process.stdout.write(
        "observe_reference.mjs --url URL --id ID --out DIR --state-contract FILE [--label TEXT] [--browser-executable FILE]\n"
      );
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${a}`);
  }
  if (!out.url || !/^https?:\/\//i.test(out.url)) fail("invalid-url", "--url must be an http(s) URL.");
  if (!out.id || !/^[a-z][a-z0-9-]{0,47}$/.test(out.id)) fail("invalid-id", "--id must be a short lowercase slug, e.g. strong-1.");
  if (!out.outDir) fail("invalid-out", "--out must name a directory.");
  if (!out.stateContract) fail("state-contract-required", "--state-contract is required; source states may not be auto-named or guessed.");
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
  if (payload?.schema_version !== 1 || payload.reference_id !== referenceId || !Array.isArray(payload.states) ||
      Object.keys(payload).some((key) => !["schema_version", "reference_id", "states"].includes(key))) {
    fail("state-contract-invalid", "Source state contract must be exact schema 1 with reference_id and states.");
  }
  const ids = new Set();
  for (const state of payload.states) {
    const core = state && { id: state.id, kind: state.kind, trigger: state.trigger, expectation: state.expectation };
    if (!state || Object.keys(state).some((key) => !["id", "url", "kind", "trigger", "expectation"].includes(key)) ||
        Object.keys(state.trigger || {}).some((key) => !["type", "target", "value"].includes(key)) ||
        validateManifestState(core) || ids.has(state.id)) {
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

async function dismissScopedConsent(page) {
  return page.evaluate(() => {
    const containers = [...document.querySelectorAll('[role="dialog"],[aria-modal="true"],#onetrust-banner-sdk,[class*="cookie" i],[id*="cookie" i],[class*="consent" i],[id*="consent" i]')];
    const consent = containers.find((el) => /cookie|privacy|consent|tracking/i.test(`${el.id} ${el.className} ${el.getAttribute('aria-label') || ''} ${el.textContent || ''}`));
    if (!consent) return { present: false, dismissed: false, label: null };
    const order = ['reject','reject all','decline','decline all','only necessary','necessary only','essential only'];
    const buttons = [...consent.querySelectorAll('button')];
    let button = null;
    for (const label of order) {
      button = buttons.find((el) => (el.textContent || '').trim().replace(/\s+/g, ' ').toLowerCase() === label);
      if (button) break;
    }
    if (!button) return { present: true, dismissed: false, label: null };
    const label = (button.textContent || '').trim(); button.click(); return { present: true, dismissed: true, label };
  }).catch((error) => ({ present: true, dismissed: false, error: String(error).slice(0, 120) }));
}

async function requireUnblockedConsent(page, notes = null) {
  const result = await dismissScopedConsent(page);
  if (result.present && !result.dismissed) throw new Error("A consent dialog is present without an exact reject/necessary-only control; observation will not make an ambiguous consent choice.");
  if (result.dismissed && notes) notes.push(`consent dialog button clicked: ${result.label}`);
  if (result.dismissed) await page.waitForTimeout(600);
  return result;
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

function mergeInteractionCensuses(profile, censuses) {
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
      equivalent: inputKinds.every((kind) => new Set(members.flatMap((target) => target.inputs
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

async function studyRecursiveSite(page, primaryUrl, profile, authoredStates, captureEvidence) {
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
    const navigation = await navigateExact(page, url);
    await page.evaluate(() => document.fonts?.ready).catch(() => {});
    await page.waitForTimeout(500);
    await requireUnblockedConsent(page);
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
    while (true) {
      const interactionCensus = await captureInteractionCensus(page, { profile, pageUrl: url,
        authoredStates: applicableStates, captureEvidence });
      if (!interactionCensus.complete || interactionCensus.truncated) throw new Error(`${profile} ${url}: interaction census is incomplete.`);
      interactionCensuses.push(interactionCensus);
      pageInteractionCensuses.push(interactionCensus);
      const observedTargets = interactionCensus.pages.flatMap((pageRecord) => pageRecord.targets.map((target) => target.target_id));
      const newTargets = observedTargets.filter((targetId) => !knownTargets.has(targetId));
      observedTargets.forEach((targetId) => knownTargets.add(targetId));
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

async function captureSourceStates(browser, contract, viewport, captureEvidence) {
  const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
  await installDomInspection(context);
  const page = await context.newPage();
  const result = {};
  try {
    for (const state of contract.states) {
      const navigation = await navigateExact(page, state.url);
      await page.evaluate(() => document.fonts?.ready).catch(() => {});
      await page.waitForTimeout(500);
      await requireUnblockedConsent(page);
      const beforeFrame = await captureEvidence(page, `${viewport.name}-${state.id}-state-before`);
      const application = await applyManifestState(page, state);
      const afterFrame = await captureEvidence(page, `${viewport.name}-${state.id}-state-after`);
      await page.waitForTimeout(220);
      const settledFrame = await captureEvidence(page, `${viewport.name}-${state.id}-state-settled`);
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
      const interactionCensus = await captureInteractionCensus(page, { profile: viewport.name,
        pageUrl: state.url, authoredStates: applicableStates,
        captureEvidence: (label, evidencePage = page) => captureEvidence(evidencePage, `${viewport.name}-${state.id}-${label}`) });
      if (!interactionCensus.complete) throw new Error(`${viewport.name}/${state.id}: interaction census is incomplete.`);
      const renderedQA = await captureRenderedQA(page, { profile: viewport.name, pageUrl: state.url,
        sourceState: state, interactionCensus,
        captureEvidence: (label, evidencePage = page) => captureEvidence(evidencePage, `${viewport.name}-${state.id}-${label}`) });
      if (!renderedQA.complete) throw new Error(`${viewport.name}/${state.id}: rendered QA is incomplete.`);
      result[state.id] = { id: state.id, url: state.url, kind: state.kind, trigger: state.trigger,
        expectation: state.expectation, navigation, trigger_application: application,
        trigger_evidence: application.trigger_evidence,
        evidence_frames: { before: beforeFrame, after: afterFrame, settled: settledFrame },
        interaction_census: interactionCensus,
        rendered_qa: renderedQA,
        structure, mechanisms: sheet.mechanisms, score: sheet.score, scroll_traversal: sheet.scroll_traversal };
    }
  } finally { await context.close(); }
  return result;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const loaded = loadPlaywright();
  const pw = loaded.playwright;
  const stateContract = readStateContract(args.stateContract, args.id, args.url);
  const browserDependency = loadBrowserDependency(loaded, args.browserExecutable);
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

  async function shotOn(targetPage, kind, note, viewport = { width: 1440, height: 900 }) {
    n += 1;
    const safeKind = String(kind).toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "");
    const file = `${args.id}-${String(n).padStart(5, "0")}-${safeKind}.png`;
    const buf = await targetPage.screenshot({ path: path.join(frameDir, file) });
    const rec = { seq: n, kind: safeKind, file, bytes: buf.length, sha256: sha(buf), viewport, note: note || null };
    frames.push(rec);
    return rec;
  }
  const shot = (kind, note) => shotOn(page, kind, note);
  const boundEvidenceShot = async (targetPage, kind, note, viewport) => {
    const frame = await shotOn(targetPage, kind, note, viewport);
    return { ...frame, file: `${path.basename(frameDir)}/${frame.file}` };
  };

  try {
    const primaryNavigation = await navigateExact(page, args.url);
    navigations.push({ profile: "wide", purpose: "primary-rest", ...primaryNavigation });
    await page.evaluate(() => document.fonts?.ready).catch(() => {});
    await page.waitForTimeout(3000);

    await requireUnblockedConsent(page, notes);

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
    const narrowNavigation = await navigateExact(narrowPage, args.url);
    navigations.push({ profile: "narrow", purpose: "primary-rest", ...narrowNavigation });
    await narrowPage.evaluate(() => document.fonts?.ready).catch(() => {});
    await narrowPage.waitForTimeout(700);
    await requireUnblockedConsent(narrowPage, notes);
    const narrowFirstScreen = await narrowPage.evaluate(STRUCTURE_SCRIPT);
    const narrowFrame = await shotOn(narrowPage, "narrow-rest", "narrow first screen at rest", { width: 390, height: 844 });
    const narrowFrameFile = narrowFrame.file;
    const narrowMechanism = await mechanismPass(narrowPage);
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
    const scrollHoldTraversal = await traverseScrollSurfaces(page, { maxTicks: 240, settleMs: 120,
      onTick: async (surface, tick) => {
      steps += 1;
      const a = await shot("scroll-arrive", `arrived at ${surface.kind}:${surface.selector_hint || surface.id} wheel step ${tick}`);
      await page.waitForTimeout(HOLD_MS);
      const b = await shot("scroll-settle", `held for ${HOLD_MS}ms after wheel step ${tick}`);
      const moved = a.sha256 !== b.sha256;
      if (moved) scrollMoved += 1;
      interactions.push({
        type: "scroll-hold", surface: surface.id, step: tick, moved, frames: [a.seq, b.seq],
        detail: moved ? "Content changed while the page sat still here, so something animated into place." : "Nothing changed while the page sat still here.",
      });
      mech.mechanisms.push(...(await checkAmbientVideo(page)));
    } });
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
        const transitionNavigation = await navigateExact(page, href, { timeout: 45000 });
        navigations.push({ profile: "wide", purpose: "transition", ...transitionNavigation });
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
      throw new Error(`Exact transition navigation failed: ${String(e).slice(0, 220)}`);
    }
    interactions.push(transition);
    if (transition.moved) mech.mechanisms.push({ type: "page-transition", detail: "the next page arrived animated or staged" });
    if (restAnimated) mech.mechanisms.push({ type: "at-rest", detail: "a measured animation plays with no input" });

    // Exact source-state sheets are producer-authored contracts, not names
    // guessed by the observer. Separately, every recursively discovered page
    // and every native/transform scroll surface is traversed at both profiles.
    const statesByViewport = {
      wide: await captureSourceStates(browser, stateContract.payload, { name: "wide", width: 1440, height: 900 },
        (targetPage, label) => boundEvidenceShot(targetPage, label, "source state interaction evidence", { width: 1440, height: 900 })),
      narrow: await captureSourceStates(browser, stateContract.payload, { name: "narrow", width: 390, height: 844 },
        (targetPage, label) => boundEvidenceShot(targetPage, label, "source state interaction evidence", { width: 390, height: 844 })),
    };
    const wideSiteTraversal = await studyRecursiveSite(page, args.url, "wide", stateContract.payload.states,
      (label, evidencePage = page) => boundEvidenceShot(evidencePage, `wide-${label}`, "wide interaction-census evidence", { width: 1440, height: 900 }));
    const narrowSiteContext = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
    await installDomInspection(narrowSiteContext);
    const narrowSitePage = await narrowSiteContext.newPage();
    const narrowSiteTraversal = await studyRecursiveSite(narrowSitePage, args.url, "narrow", stateContract.payload.states,
      (label, evidencePage = narrowSitePage) => boundEvidenceShot(evidencePage, `narrow-${label}`, "narrow interaction-census evidence", { width: 390, height: 844 }));
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
      throw new Error("Uncapped wide+narrow interaction census is incomplete.");
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

    const record = {
      schema_version: SCHEMA_VERSION,
      tool: "observe_reference.mjs",
      producer_script_sha256: PRODUCER_SCRIPT_SHA256,
      runtime_identity: { "observe_reference.mjs": PRODUCER_SCRIPT_SHA256, "structure_probe.mjs": STRUCTURE_PROBE_SHA256,
        "browser_evidence.mjs": BROWSER_EVIDENCE_SHA256, "playwright_resolver.mjs": PLAYWRIGHT_RESOLVER_SHA256,
        "playwright-entry": loaded.dependency.resolved_file_sha256,
        "browser-executable": browserExecutableSha256 },
      dependencies: {
        observer: { file: "observe_reference.mjs", sha256: PRODUCER_SCRIPT_SHA256 },
        structure_probe: { file: "structure_probe.mjs", sha256: STRUCTURE_PROBE_SHA256 },
        browser_evidence: { file: "browser_evidence.mjs", sha256: BROWSER_EVIDENCE_SHA256 },
        playwright_resolver: { file: "playwright_resolver.mjs", sha256: PLAYWRIGHT_RESOLVER_SHA256 },
        playwright: loaded.dependency,
        browser_executable: browserDependency,
      },
      id: args.id,
      label: args.label || null,
      url: args.url,
      requested_url: primaryNavigation.requested_url,
      final_url: primaryNavigation.final_url,
      observed_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      viewport: { width: 1440, height: 900 },
      frame_dir: path.basename(frameDir),
      frames,
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
    fail("observation-failed", String(error).slice(0, 400));
  } finally {
    await browser.close().catch(() => {});
  }
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
if (invokedDirectly) main();
