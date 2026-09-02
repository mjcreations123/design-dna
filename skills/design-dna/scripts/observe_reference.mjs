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
import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";

const SCHEMA_VERSION = 2;
const REST_SETTLE_MS = 700;
const HOLD_MS = 900;
const SCROLL_STEP_RATIO = 0.62;
const MAX_STEPS = 14;
const MAX_HOVERS = 4;
// the mechanism pass: many small wheel ticks so a pinned stage, a swap or a
// parallax shows up as a trend across samples rather than a single jump
const TICK_PX = 700;
const MAX_TICKS = 40;
const TICK_SETTLE_MS = 650;

function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }, null, 2) + "\n");
  process.exit(2);
}

function parseArgs(argv) {
  const out = { url: null, id: null, outDir: null, browserExecutable: null, label: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--url") out.url = argv[++i];
    else if (a === "--id") out.id = argv[++i];
    else if (a === "--out") out.outDir = argv[++i];
    else if (a === "--label") out.label = argv[++i];
    else if (a === "--browser-executable") out.browserExecutable = argv[++i];
    else if (a === "--help" || a === "-h") {
      process.stdout.write(
        "observe_reference.mjs --url URL --id ID --out DIR [--label TEXT] [--browser-executable FILE]\n"
      );
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${a}`);
  }
  if (!out.url || !/^https?:\/\//i.test(out.url)) fail("invalid-url", "--url must be an http(s) URL.");
  if (!out.id || !/^[a-z][a-z0-9-]{0,47}$/.test(out.id)) fail("invalid-id", "--id must be a short lowercase slug, e.g. strong-1.");
  if (!out.outDir) fail("invalid-out", "--out must name a directory.");
  return out;
}

function loadPlaywright() {
  const require = createRequire(import.meta.url);
  const moduleDir = process.env.DESIGN_DNA_PLAYWRIGHT_MODULE_DIR;
  const attempt = (name) => {
    if (moduleDir) {
      try {
        return require(path.join(moduleDir, name));
      } catch (e) { /* fall through */ }
    }
    return require(name);
  };
  for (const name of ["playwright", "playwright-core"]) {
    try {
      const pw = attempt(name);
      if (pw?.chromium) return pw;
    } catch (e) { /* try the next */ }
  }
  fail(
    "playwright-unavailable",
    "Playwright could not be loaded. Install it, or set DESIGN_DNA_PLAYWRIGHT_MODULE_DIR to its node_modules directory."
  );
  return null;
}

const sha = (buf) => createHash("sha256").update(buf).digest("hex");

// Tag every element large enough to be a stage, a picture, a heading or a
// block, so the scroll pass can follow each one by a stable id.
export const TAG_PROBES = `(() => {
  let i = 0;
  const existing = document.querySelectorAll('[data-dna-probe]').length;
  i = existing;
  const sel = 'section,article,div,figure,img,video,canvas,h1,h2,h3,p,ul,ol,li,a';
  document.querySelectorAll(sel).forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 120 || r.height < 56) return;
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
    const ident = { tag: first.tag, cls: first.cls, w: first.w, h: first.h, sample: first.txt.slice(0, 36) };
    let pinRun = 0, pinPx = 0, bestRun = 0, bestPx = 0, bestStart = -1, runStart = -1;
    let parallaxTicks = 0;
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
        if (rate > 0.12 && rate < 0.85) parallaxTicks += 1;
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
      seq.forEach((s) => activeTicks.add(s.tick));
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
      seq.forEach((s) => activeTicks.add(s.tick));
    }
    if (parallaxTicks >= 4) {
      mechanisms.push({
        type: "parallax",
        ...ident,
        rate: Number(median(rates.filter((r) => r > 0.12 && r < 0.85)).toFixed(2)),
        ticks: parallaxTicks,
        detail: "moved at a different rate than the page",
      });
      seq.forEach((s) => activeTicks.add(s.tick));
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
  const weight = (m) => (m.swaps_while_held || 0) * 1000 + (m.held_px || 0) + (m.swaps || 0) * 100 + (m.ticks || 0) * 10;
  const kept = mechanisms
    .sort((a, b) => weight(b) - weight(a))
    .filter((m) => { const k = `${m.type}|${m.tag}|${m.cls}`; if (seen.has(k)) return false; seen.add(k); return true; })
    .slice(0, 12);
  return { mechanisms: kept, activeTicks, scrollTicks, pageMove, typeCounts };
}

// The whole mechanism pass on an open page, shared with compare_mechanisms.mjs
// so a build is read by exactly the same eyes as its references.
export async function mechanismPass(page) {
  await page.evaluate(TAG_PROBES);
  const ticks = [];
  ticks.push(await page.evaluate(SAMPLE_PROBES));
  let stalled = 0;
  for (let t = 0; t < MAX_TICKS; t += 1) {
    await page.mouse.move(720, 450);
    await page.mouse.wheel(0, TICK_PX);
    await page.waitForTimeout(TICK_SETTLE_MS);
    await page.evaluate(TAG_PROBES);
    let snap = await page.evaluate(SAMPLE_PROBES);
    const prev = ticks[ticks.length - 1];
    const quiet = (a, b) => {
      const d = [];
      for (const [id, v] of Object.entries(b.els)) { const q = a.els[id]; if (q) d.push(Math.abs(q.top - v.top)); }
      const inner = a.inner && b.inner ? Math.abs((b.inner.top || 0) - (a.inner.top || 0)) : 0;
      return Math.abs((b.y || 0) - (a.y || 0)) < 4 && inner < 4 && median(d) < 4;
    };
    if (quiet(prev, snap)) {
      // nothing answered a normal tick; a reel with a threshold wants a bigger one
      await page.mouse.wheel(0, TICK_PX * 2);
      await page.waitForTimeout(TICK_SETTLE_MS);
      await page.evaluate(TAG_PROBES);
      snap = await page.evaluate(SAMPLE_PROBES);
    }
    ticks.push(snap);
    const deltas = [];
    for (const [id, v] of Object.entries(snap.els)) {
      const p = prev.els[id];
      if (p) deltas.push(Math.abs(p.top - v.top));
    }
    const consumed = Math.max(
      Math.abs((snap.y || 0) - (prev.y || 0)),
      snap.inner && prev.inner ? Math.abs((snap.inner.top || 0) - (prev.inner.top || 0)) : 0,
      median(deltas)
    );
    let changed = false;
    for (const [id, v] of Object.entries(snap.els)) {
      const q = prev.els[id];
      if (q && (q.src !== v.src || q.txt !== v.txt)) { changed = true; break; }
    }
    if (consumed < 4 && !changed) stalled += 1; else stalled = 0;
    if (stalled >= 3) break;
  }
  const derived = deriveMechanisms(ticks);
  const last = ticks[ticks.length - 1];
  const scroller = last.y > 0 ? "document" : (last.inner ? `inner:${last.inner.cls || "element"}` : "none");
  // pointer follow: anything whose transform tracks the pointer without hover
  let pointerFollow = null;
  try {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(400);
    await page.mouse.move(200, 300);
    await page.waitForTimeout(350);
    const a = await page.evaluate(SAMPLE_PROBES);
    await page.mouse.move(1200, 600, { steps: 12 });
    await page.waitForTimeout(350);
    const b = await page.evaluate(SAMPLE_PROBES);
    for (const [id, v] of Object.entries(b.els)) {
      const p = a.els[id];
      if (p && p.tf !== v.tf && v.top > -50 && v.top < 900) {
        pointerFollow = { tag: v.tag, cls: v.cls, sample: v.txt.slice(0, 36) };
        break;
      }
    }
  } catch (e) { pointerFollow = null; }
  if (pointerFollow) {
    derived.mechanisms.push({ type: "pointer-follow", ...pointerFollow, detail: "its transform changed as the pointer crossed the screen" });
  }
  return {
    mechanisms: derived.mechanisms,
    score: {
      distinct_mechanisms: new Set(derived.mechanisms.map((m) => m.type)).size,
      scroll_coverage: Number((derived.activeTicks.size / derived.scrollTicks).toFixed(2)),
      scroll_windows_active: derived.activeTicks.size,
      scroll_windows: derived.scrollTicks,
      elements_with_mechanism: derived.mechanisms.filter((m) => m.tag).length,
      document_scrolls: ticks.some((t) => t.y > 0),
      type_instances: derived.typeCounts,
      scroller,
      scroll_consumed_px: Math.round(derived.pageMove.reduce((a, b) => a + b, 0)),
    },
    wheel_ticks: ticks.length - 1,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const pw = loadPlaywright();
  fs.mkdirSync(args.outDir, { recursive: true });
  const frameDir = path.join(args.outDir, `${args.id}-frames`);
  fs.mkdirSync(frameDir, { recursive: true });

  const frames = [];
  const interactions = [];
  const notes = [];
  let n = 0;

  const browser = await pw.chromium.launch(
    args.browserExecutable ? { executablePath: args.browserExecutable } : {}
  );
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();

  async function shot(kind, note) {
    n += 1;
    const file = `${args.id}-${String(n).padStart(3, "0")}-${kind}.png`;
    const buf = await page.screenshot({ path: path.join(frameDir, file) });
    const rec = { seq: n, kind, file, sha256: sha(buf), note: note || null };
    frames.push(rec);
    return rec;
  }

  try {
    await page.goto(args.url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(3000);

    for (const word of ["reject", "decline", "only necessary", "essential", "accept", "agree", "got it", "allow all"]) {
      try {
        const b = page.locator(`button:has-text("${word}"), a:has-text("${word}")`).first();
        if (await b.isVisible({ timeout: 250 })) {
          await b.click({ timeout: 1200 });
          notes.push(`consent control clicked: ${word}`);
          await page.waitForTimeout(600);
          break;
        }
      } catch (e) { /* none present */ }
    }

    // --- at rest
    const rest0 = await shot("rest", "at rest, first frame");
    await page.waitForTimeout(REST_SETTLE_MS);
    const rest1 = await shot("rest", "at rest, after settle delay, no input");
    const restMoved = rest0.sha256 !== rest1.sha256;
    interactions.push({
      type: "rest", moved: restMoved, frames: [rest0.seq, rest1.seq],
      detail: restMoved ? "The page changed with no input, so something autoplays or loops." : "The page was still with no input.",
    });

    // --- the mechanism pass
    const mech = await mechanismPass(page);

    // --- scroll holds (schema 1 evidence, kept): arrival vs settled frames
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(500);
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    const view = 900;
    const step = Math.max(240, Math.round(view * SCROLL_STEP_RATIO));
    const steps = Math.max(2, Math.min(MAX_STEPS, Math.max(2, Math.floor((height - view) / step))));
    let scrollMoved = 0;
    for (let i = 1; i <= steps; i += 1) {
      await page.mouse.move(720, 450);
      await page.mouse.wheel(0, step);
      await page.waitForTimeout(120);
      const a = await shot("scroll-arrive", `arrived after wheel step ${i}`);
      await page.waitForTimeout(HOLD_MS);
      const b = await shot("scroll-settle", `held for ${HOLD_MS}ms after wheel step ${i}`);
      const moved = a.sha256 !== b.sha256;
      if (moved) scrollMoved += 1;
      interactions.push({
        type: "scroll-hold", step: i, moved, frames: [a.seq, b.seq],
        detail: moved ? "Content changed while the page sat still here, so something animated into place." : "Nothing changed while the page sat still here.",
      });
    }

    // --- hover: real pointer over real interactive elements, with timing
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(600);
    let hoverMoved = 0;
    let hoverTried = 0;
    const hoverDurations = [];
    const targets = await page.$$("a, button, [role=button], li, article, figure, img");
    for (const el of targets) {
      if (hoverTried >= MAX_HOVERS) break;
      let box = null;
      try { box = await el.boundingBox(); } catch (e) { box = null; }
      if (!box || box.width < 60 || box.height < 24 || box.y < 0 || box.y > 820) continue;
      hoverTried += 1;
      await page.mouse.move(4, 4);
      await page.waitForTimeout(200);
      const before = await shot("hover-before", "pointer away");
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.waitForTimeout(650);
      const after = await shot("hover-after", "pointer over an interactive element");
      const moved = before.sha256 !== after.sha256;
      if (moved) hoverMoved += 1;
      let duration = null;
      try {
        duration = await el.evaluate((node) => {
          const c = getComputedStyle(node);
          const d = c.transitionDuration.split(",").map((s) => parseFloat(s) * (s.trim().endsWith("ms") ? 1 : 1000));
          return { ms: Math.max(...d, 0), easing: c.transitionTimingFunction, property: c.transitionProperty };
        });
      } catch (e) { duration = null; }
      if (duration && duration.ms > 0) hoverDurations.push(duration);
      interactions.push({
        type: "hover", moved, frames: [before.seq, after.seq], transition: duration,
        detail: moved ? "The page responded to the pointer." : "Nothing responded to the pointer here.",
      });
    }
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
        await page.goto(href, { waitUntil: "domcontentloaded", timeout: 45000 });
        await page.waitForTimeout(260);
        const during = await shot("transition-during", "shortly after navigation started");
        await page.waitForTimeout(2200);
        const settled = await shot("transition-settled", "destination settled");
        transition = {
          type: "transition", attempted: true, url: href,
          moved: during.sha256 !== settled.sha256,
          frames: [before.seq, during.seq, settled.seq],
          detail: during.sha256 !== settled.sha256
            ? "The destination was still resolving after navigation, so the arrival is animated or staged."
            : "The destination appeared in its settled state immediately.",
        };
      }
    } catch (e) {
      transition.detail = `Following a link failed: ${String(e).slice(0, 160)}`;
    }
    interactions.push(transition);
    if (transition.moved) mech.mechanisms.push({ type: "page-transition", detail: "the next page arrived animated or staged" });
    if (restMoved) mech.mechanisms.push({ type: "at-rest", detail: "something plays with no input" });

    const distinct = new Set(mech.mechanisms.map((m) => m.type)).size;
    const motionObserved = restMoved || scrollMoved > 0 || hoverMoved > 0 || transition.moved === true || mech.mechanisms.length > 0;

    const record = {
      schema_version: SCHEMA_VERSION,
      tool: "observe_reference.mjs",
      id: args.id,
      label: args.label || null,
      url: args.url,
      observed_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      viewport: { width: 1440, height: 900 },
      frame_dir: path.basename(frameDir),
      frames,
      interactions,
      coverage: { rest: true, scroll_holds: steps, hovers: hoverTried, transition: transition.attempted, wheel_ticks: mech.wheel_ticks },
      motion: {
        observed: motionObserved,
        at_rest: restMoved,
        on_scroll_holds: scrollMoved,
        on_hover: hoverMoved,
        on_transition: transition.moved === true,
      },
      mechanisms: mech.mechanisms,
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
