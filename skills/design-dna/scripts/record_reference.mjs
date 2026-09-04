#!/usr/bin/env node
/**
 * record_reference.mjs
 *
 * Record a reference the way a person uses it, then find the moments worth
 * looking at, so that WATCHING a site costs minutes and not hours.
 *
 * Why this exists: three instruments in a row let a producer say it had
 * watched a site without looking. Stills called a sequence, computed styles
 * called a copy, and a harness whose mechanism numbers were read while one
 * rest frame out of forty-one was opened. The owner recorded himself using
 * the site for a minute; walked at ten frames a second the recording held
 * nineteen behaviours the build had never seen. The first fix (9.0.0) cut the
 * recording into contact sheets and demanded a narrated line for every one of
 * them. It worked, and it cost hours per site: three hundred sheets, nearly
 * all of them showing nothing changing. The owner's words: "I need some
 * quicker way, in between creating thousands of frames and going through
 * each one individually, and I also don't want just a screenshot."
 *
 * So this version knows what it did, and looks only where something happened:
 *   - it drives the page with a real cursor (a dwell on every interactive
 *     thing on the first screen, a stepped scroll hovering what arrives, one
 *     internal link so the transition and an inner page are on tape),
 *     recording video the whole time and logging every action with the time
 *     it started and the time it ended;
 *   - it reduces the video to small grayscale frames and differences them,
 *     so it knows, for every tenth of a second, how much of the screen
 *     changed and where;
 *   - it turns the actions into EVENTS, each with four full-size frames
 *     (before, during, after, settled), a magnitude (percent of the screen
 *     that changed), a region, and how long the change took to settle. A
 *     hover that changed nothing is listed as quiet and gets no sheet. Scroll
 *     steps that only translated the page are merged into one travel event.
 *     Changes nobody caused (a video, a self-playing carousel, a card that
 *     cycles on its own) are found from the difference signal and become
 *     spontaneous events;
 *   - it tiles the four frames of each event into one sheet, and writes
 *     <id>-recording.json (schema 2) binding all of it, plus <id>-events.md,
 *     a table of the events with their numbers, which is the skeleton of the
 *     behaviour inventory the producer then writes by hand.
 *
 * Full frames at --fps stay in <id>-frames/ for anyone who wants to look
 * between the events. Nobody has to, except for one case that has to: a
 * "photograph" that is really a looping video (a swiveling chair, smoke off
 * a candle) changes too slowly and too locally to cross the event threshold,
 * so it produces no events at all and reads as a still. The output manifest
 * lists every `<video>` element the page had at load, with its position and
 * size, specifically so the narrator is told to go watch that spot in the
 * full frame sheet rather than assume it is a photograph. Raise --fps for a
 * site suspected of this (20-30 catches slow ambient motion the default
 * misses).
 *
 * ffmpeg must be on PATH (or given with --ffmpeg). Without it there are no
 * frames, and without frames there is nothing to narrate, so it fails loudly.
 *
 * Usage:
 *   node record_reference.mjs --url https://example.test/ --id strong-1 \
 *     --out .design-dna/references [--seconds 90] [--fps 15] \
 *     [--browser-executable FILE] [--ffmpeg FILE]
 */
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const TOOL_NAME = "record_reference.mjs";
const SCHEMA_VERSION = 2;
const VIEWPORT = { width: 1440, height: 900 };
const SMALL_WIDTH = 320;

const HOVER_DWELL_MS = 1600;      // long enough for a slow expansion and a caption
const HOVER_SETTLE_MS = 700;      // after mouse-out, so the un-hover plays too
const FIRST_SCREEN_HOVERS = 10;
const SCROLL_STEP_PX = 600;
const SCROLL_PAUSE_MS = 1200;
const HOVERS_PER_STOP = 1;
const INTRO_WAIT_MS = 3500;
const TRANSITION_WAIT_MS = 3500;

// percent of the screen (mean absolute difference over the gray frame, 0-100)
const QUIET_PCT = 0.6;        // below this an action changed nothing worth a frame
const SPONTANEOUS_PCT = 1.2;  // a change nobody caused
const SETTLE_PCT = 0.25;      // frame-to-frame, the page has stopped moving
const PIXEL_CHANGED = 24;     // 0-255, one pixel counts as changed
const MAX_SPONTANEOUS = 12;

function parseArgs(argv) {
  const out = {
    url: null, id: null, out: null, seconds: 90, fps: 15,
    browser: process.env.CHROME || undefined, ffmpeg: process.env.FFMPEG || "ffmpeg",
  };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--url") out.url = argv[++i];
    else if (a === "--id") out.id = argv[++i];
    else if (a === "--out") out.out = argv[++i];
    else if (a === "--seconds") out.seconds = Number(argv[++i]);
    else if (a === "--fps") out.fps = Number(argv[++i]);
    else if (a === "--browser-executable") out.browser = argv[++i];
    else if (a === "--ffmpeg") out.ffmpeg = argv[++i];
  }
  return out;
}

function loadPlaywright() {
  const dir = process.env.DESIGN_DNA_PLAYWRIGHT_MODULE_DIR;
  const require_ = createRequire(dir ? path.join(dir, "noop.js") : import.meta.url);
  try { return require_("playwright-core"); } catch { return require_("playwright"); }
}

const sha256 = (file) => createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const round1 = (n) => +Number(n).toFixed(1);
const round2 = (n) => +Number(n).toFixed(2);

/* Everything a person could hover: links, buttons, controls, and anything the
   page itself marks as clickable with a pointer cursor. Visible, big enough to
   aim at, inside the given band of the document. */
const FIND_TARGETS = `(({ top, bottom }) => {
  const out = [];
  const seen = new Set();
  const sel = 'a[href], button, [role="button"], input, select, textarea, summary, [onclick], [tabindex]';
  const all = new Set(document.querySelectorAll(sel));
  document.querySelectorAll('div, span, figure, li, img, video, h1, h2, h3, p').forEach((el) => {
    if (getComputedStyle(el).cursor === 'pointer') all.add(el);
  });
  for (const el of all) {
    const r = el.getBoundingClientRect();
    if (r.width < 24 || r.height < 24) continue;
    const cy = r.top + window.scrollY + r.height / 2;
    if (cy < top || cy > bottom) continue;
    if (r.left < 0 || r.right > innerWidth) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || Number(cs.opacity) < 0.05 || cs.display === 'none') continue;
    const key = Math.round(r.left / 40) + ':' + Math.round((r.top + window.scrollY) / 40);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2),
      area: Math.round(r.width * r.height),
      tag: el.tagName.toLowerCase(),
      text: (el.innerText || el.getAttribute('aria-label') || el.getAttribute('alt') || '').replace(/\s+/g, ' ').trim().slice(0, 40),
      href: el.getAttribute('href') || '',
    });
  }
  return out.sort((a, b) => b.area - a.area);
})`;

async function findTargets(page, top, bottom) {
  const found = await page.evaluate(`${FIND_TARGETS}({ top: ${Number(top)}, bottom: ${Number(bottom)} })`);
  return Array.isArray(found) ? found : [];
}

async function hoverEach(page, targets, log, clock, dwell) {
  for (const t of targets) {
    if (clock.over()) return;
    await page.mouse.move(t.x, t.y, { steps: 28 });
    const entry = { action: "hover", t_start: clock.now(), x: t.x, y: t.y, target: `${t.tag} ${t.text}`.trim() };
    await sleep(dwell);
    entry.t_end = clock.now();
    // leave by a visible route so the un-hover state is on tape too
    await page.mouse.move(Math.max(40, t.x - 260), Math.min(VIEWPORT.height - 60, t.y + 140), { steps: 18 });
    await sleep(HOVER_SETTLE_MS);
    entry.t_left = clock.now();
    log.push(entry);
  }
}

async function scrollThrough(page, log, clock, budgetMs) {
  const started = Date.now();
  let lastY = -1;
  let stop = 0;
  while (!clock.over() && Date.now() - started < budgetMs) {
    const entry = { action: "scroll", t_start: clock.now() };
    await page.mouse.wheel(0, SCROLL_STEP_PX);
    await sleep(SCROLL_PAUSE_MS);
    entry.t_end = clock.now();
    entry.y = await page.evaluate(() => Math.round(window.scrollY));
    log.push(entry);
    if (entry.y === lastY) break; // the bottom, or a page that scrolls something else
    lastY = entry.y;
    stop += 1;
    if (stop % 2 === 0) {
      const inView = await findTargets(page, entry.y + 80, entry.y + VIEWPORT.height - 80);
      await hoverEach(page, inView.slice(0, HOVERS_PER_STOP), log, clock, 1000);
    }
  }
}

/* ------------------------------------------------------------------------- */
/* the difference signal                                                      */
/* ------------------------------------------------------------------------- */

function readSmallFrames(rawFile, width, height) {
  const buf = fs.readFileSync(rawFile);
  const size = width * height;
  const count = Math.floor(buf.length / size);
  const frames = [];
  for (let i = 0; i < count; i += 1) frames.push(buf.subarray(i * size, (i + 1) * size));
  return frames;
}

/* mean absolute difference as a percent of full scale, and where it happened */
function diffFrames(a, b, width, height) {
  if (!a || !b) return { pct: 0, area_pct: 0, bbox: null };
  let sum = 0;
  let changed = 0;
  let minx = width, miny = height, maxx = -1, maxy = -1;
  for (let y = 0; y < height; y += 1) {
    const row = y * width;
    for (let x = 0; x < width; x += 1) {
      const d = Math.abs(a[row + x] - b[row + x]);
      sum += d;
      if (d > PIXEL_CHANGED) {
        changed += 1;
        if (x < minx) minx = x;
        if (x > maxx) maxx = x;
        if (y < miny) miny = y;
        if (y > maxy) maxy = y;
      }
    }
  }
  const n = width * height;
  return {
    pct: round2((sum / n) / 255 * 100),
    area_pct: round1(changed / n * 100),
    bbox: maxx < 0 ? null : {
      left: round2(minx / width), top: round2(miny / height),
      right: round2((maxx + 1) / width), bottom: round2((maxy + 1) / height),
    },
  };
}

function regionName(bbox, areaPct) {
  if (!bbox) return "nowhere";
  const w = bbox.right - bbox.left;
  const h = bbox.bottom - bbox.top;
  if (w > 0.8 && h > 0.8) return "the whole screen";
  const cx = (bbox.left + bbox.right) / 2;
  const cy = (bbox.top + bbox.bottom) / 2;
  const col = cx < 0.34 ? "left" : cx > 0.66 ? "right" : "centre";
  const row = cy < 0.34 ? "top" : cy > 0.66 ? "bottom" : "middle";
  const extent = w > 0.8 ? "a full-width band" : h > 0.8 ? "a full-height column" : w * h > 0.3 ? "a large area" : "a small area";
  return `${extent} at ${row} ${col} (${areaPct}% of pixels)`;
}

/* how long after t the frame-to-frame difference stays above SETTLE_PCT */
function settleAfter(signal, fromIdx, fps, maxSeconds) {
  const limit = Math.min(signal.length - 1, fromIdx + Math.round(maxSeconds * fps));
  let last = fromIdx;
  for (let i = fromIdx + 1; i <= limit; i += 1) if (signal[i] >= SETTLE_PCT) last = i;
  return round1((last - fromIdx) / fps);
}

/* ------------------------------------------------------------------------- */
/* events                                                                     */
/* ------------------------------------------------------------------------- */

function frameIndex(t, fps, count) {
  return Math.max(0, Math.min(count - 1, Math.round(t * fps)));
}

function slug(text) {
  return String(text || "").toLowerCase().replace(/^(a|button|div|span|img|li|p|h1|h2|h3|video|figure|summary|input)\s+/, "")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 18);
}

function buildEvents(log, small, signal, fps, width, height, duration) {
  const count = small.length;
  const at = (t) => small[frameIndex(t, fps, count)];
  const events = [];
  const quiet = [];

  // the first screen arriving
  events.push({
    kind: "load", action: "load", target: "the first screen", t: 0,
    times: [0.3, 1.2, 2.4, INTRO_WAIT_MS / 1000 - 0.1],
  });

  let travel = null;
  const flushTravel = () => {
    if (!travel) return;
    const n = travel.steps.length;
    const first = travel.steps[0];
    const last = travel.steps[n - 1];
    const mid1 = travel.steps[Math.floor((n - 1) / 3)];
    const mid2 = travel.steps[Math.floor((2 * (n - 1)) / 3)];
    events.push({
      kind: "travel", action: "scroll", target: `${n} quiet scroll step(s), y ${first.y_before} to ${last.y}`,
      t: first.t_start, times: [first.t_start - 0.1, mid1.t_end - 0.1, mid2.t_end - 0.1, last.t_end - 0.1],
      steps: n, y_from: first.y_before, y_to: last.y,
    });
    travel = null;
  };

  let yBefore = 0;
  for (const a of log) {
    if (a.action === "hover") {
      const times = [a.t_start - 0.15, a.t_start + 0.4, a.t_end - 0.1, a.t_left - 0.05];
      const before = at(times[0]);
      const during = diffFrames(before, at(times[1]), width, height);
      const after = diffFrames(before, at(times[2]), width, height);
      const strongest = after.pct >= during.pct ? after : during;
      const ev = {
        kind: "hover", action: "hover", target: a.target, t: a.t_start, x: a.x, y: a.y, times,
        magnitude_pct: strongest.pct, changed_area_pct: strongest.area_pct,
        region: regionName(strongest.bbox, strongest.area_pct),
        settle_s: settleAfter(signal, frameIndex(a.t_start, fps, count), fps, (a.t_end - a.t_start)),
      };
      if (strongest.pct < QUIET_PCT) { quiet.push(ev); continue; }
      flushTravel();
      events.push(ev);
    } else if (a.action === "scroll") {
      const times = [a.t_start - 0.1, a.t_start + 0.35, a.t_start + 0.8, a.t_end - 0.05];
      const during = at(times[1]);
      const motion = diffFrames(during, at(times[2]), width, height);
      const late = diffFrames(at(times[2]), at(times[3]), width, height);
      const animated = Math.max(motion.pct, late.pct);
      const strongest = motion.pct >= late.pct ? motion : late;
      const ev = {
        kind: "scroll", action: "scroll", target: `scroll to y ${a.y}`, t: a.t_start, y: a.y, y_before: yBefore, times,
        magnitude_pct: animated, changed_area_pct: strongest.area_pct,
        region: regionName(strongest.bbox, strongest.area_pct),
        settle_s: settleAfter(signal, frameIndex(a.t_start + 0.3, fps, count), fps, (a.t_end - a.t_start)),
      };
      yBefore = a.y;
      if (animated < QUIET_PCT) {
        // nothing but the translation: fold into a travel run
        if (!travel) travel = { steps: [] };
        travel.steps.push({ t_start: a.t_start, t_end: a.t_end, y: a.y, y_before: ev.y_before });
        continue;
      }
      flushTravel();
      events.push(ev);
    } else if (a.action === "click") {
      flushTravel();
      const times = [a.t_start - 0.15, a.t_start + 0.5, a.t_start + 1.5, a.t_end - 0.1];
      const change = diffFrames(at(times[0]), at(times[3]), width, height);
      events.push({
        kind: "click", action: "click", target: a.target, t: a.t_start, x: a.x, y: a.y, times,
        magnitude_pct: change.pct, changed_area_pct: change.area_pct, region: regionName(change.bbox, change.area_pct),
        settle_s: settleAfter(signal, frameIndex(a.t_start, fps, count), fps, (a.t_end - a.t_start)),
      });
    }
  }
  flushTravel();

  // changes nobody caused: peaks in the signal outside every action window
  const covered = new Array(count).fill(false);
  const cover = (from, to) => {
    for (let i = frameIndex(from, fps, count); i <= frameIndex(to, fps, count); i += 1) covered[i] = true;
  };
  cover(0, INTRO_WAIT_MS / 1000 + 0.3);
  for (const a of log) {
    if (a.action === "hover") cover(a.t_start - 0.3, a.t_left + 0.3);
    else if (a.action === "scroll") cover(a.t_start - 0.2, a.t_end + 0.2);
    else if (a.action === "click") cover(a.t_start - 0.2, a.t_end + 0.5);
  }
  const peaks = [];
  for (let i = 1; i < count; i += 1) {
    if (covered[i] || signal[i] < SPONTANEOUS_PCT) continue;
    const t = i / fps;
    const last = peaks[peaks.length - 1];
    if (last && t - last.t_last < 1.0) { last.t_last = t; last.peak = Math.max(last.peak, signal[i]); continue; }
    peaks.push({ t_first: t, t_last: t, peak: signal[i] });
  }
  peaks.sort((p, q) => q.peak - p.peak);
  for (const p of peaks.slice(0, MAX_SPONTANEOUS)) {
    const t = p.t_first;
    const times = [t - 0.4, t - 0.1, t + 0.2, Math.min(duration - 0.1, p.t_last + 0.8)];
    const change = diffFrames(at(times[0]), at(times[2]), width, height);
    events.push({
      kind: "spontaneous", action: "none", target: "the page on its own", t: round1(t), times,
      magnitude_pct: change.pct, changed_area_pct: change.area_pct, region: regionName(change.bbox, change.area_pct),
      settle_s: round1(p.t_last - p.t_first + 0.3),
    });
  }

  events.sort((a, b) => a.t - b.t);
  return { events, quiet };
}

/* ------------------------------------------------------------------------- */

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.url || !args.id || !args.out) {
    console.error("record_reference.mjs --url URL --id strong-N --out DIR [--seconds 90] [--fps 15]");
    process.exit(2);
  }
  const probe = spawnSync(args.ffmpeg, ["-version"], { encoding: "utf8" });
  if (probe.error || probe.status !== 0) {
    console.error(`ffmpeg is not runnable at '${args.ffmpeg}'. Without it there are no frames, and without frames there is nothing to narrate.`);
    process.exit(2);
  }

  fs.mkdirSync(args.out, { recursive: true });
  const videoDir = fs.mkdtempSync(path.join(os.tmpdir(), "design-dna-rec-"));
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({ executablePath: args.browser });
  const context = await browser.newContext({
    viewport: VIEWPORT, deviceScaleFactor: 1,
    recordVideo: { dir: videoDir, size: VIEWPORT },
  });
  const page = await context.newPage();
  const log = [];
  const pages = [];
  const t0 = Date.now();
  const clock = { now: () => +((Date.now() - t0) / 1000).toFixed(2), over: () => Date.now() - t0 > args.seconds * 1000 };

  try {
    await page.goto(args.url, { waitUntil: "domcontentloaded", timeout: 60000 });
    pages.push(page.url());
    await page.mouse.move(60, VIEWPORT.height - 80);
    await sleep(INTRO_WAIT_MS);

    // named up front so the narrator is told which "photographs" are really
    // video before writing a single event line, rather than discovering it
    // by eye in a frame sheet after the fact (or not discovering it at all)
    const videoElements = await page.evaluate(() =>
      [...document.querySelectorAll("video")].map((v) => {
        const r = v.getBoundingClientRect();
        return {
          src: (v.currentSrc || v.src || "").slice(-80),
          loop: v.loop, autoplay: v.autoplay, muted: v.muted,
          top: Math.round(r.top), left: Math.round(r.left),
          w: Math.round(r.width), h: Math.round(r.height),
        };
      })
    ).catch(() => []);

    // the first screen, slowly, everything a hand would reach for
    const first = await findTargets(page, 0, VIEWPORT.height);
    await hoverEach(page, first.slice(0, FIRST_SCREEN_HOVERS), log, clock, HOVER_DWELL_MS);

    // down the page in steps, hovering what arrives
    await scrollThrough(page, log, clock, args.seconds * 1000 * 0.45);

    // back to the top, then through the first internal link so the transition
    // and one inner page are on tape
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
    await sleep(1400);
    const origin = new URL(args.url).origin;
    const link = await page.evaluate((origin) => {
      const links = Array.from(document.querySelectorAll("a[href]"));
      for (const a of links) {
        let href;
        try { href = new URL(a.getAttribute("href"), location.href); } catch { continue; }
        if (href.origin !== origin) continue;
        if (href.pathname === location.pathname && !href.hash) continue;
        if (href.hash && href.pathname === location.pathname) continue;
        const r = a.getBoundingClientRect();
        if (r.width < 24 || r.height < 16) continue;
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), href: href.href };
      }
      return null;
    }, origin);
    if (link && !clock.over()) {
      await page.mouse.move(link.x, link.y, { steps: 24 });
      await sleep(900);
      const entry = { action: "click", t_start: clock.now(), x: link.x, y: link.y, target: link.href };
      await page.mouse.click(link.x, link.y);
      await sleep(TRANSITION_WAIT_MS);
      entry.t_end = clock.now();
      log.push(entry);
      pages.push(page.url());
      const innerFirst = await findTargets(page, 0, VIEWPORT.height);
      await hoverEach(page, innerFirst.slice(0, 4), log, clock, 1200);
      await scrollThrough(page, log, clock, args.seconds * 1000 * 0.3);
    }
  } finally {
    const video = page.video();
    await context.close(); // flushes the video
    await browser.close().catch(() => {});
    const duration = +((Date.now() - t0) / 1000).toFixed(1);

    const src = video ? await video.path() : null;
    if (!src || !fs.existsSync(src)) {
      console.error("No video was written. Playwright's recordVideo needs a Chromium build that can encode webm.");
      process.exit(2);
    }
    const webm = path.join(args.out, `${args.id}-recording.webm`);
    fs.copyFileSync(src, webm);
    fs.rmSync(videoDir, { recursive: true, force: true });

    const framesDir = path.join(args.out, `${args.id}-frames`);
    const eventsDir = path.join(args.out, `${args.id}-events`);
    for (const dir of [framesDir, eventsDir]) {
      fs.rmSync(dir, { recursive: true, force: true });
      fs.mkdirSync(dir, { recursive: true });
    }
    // the old per-sheet output is superseded; clear it so nobody reads stale sheets
    fs.rmSync(path.join(args.out, `${args.id}-sheets`), { recursive: true, force: true });

    const extract = spawnSync(args.ffmpeg, [
      "-y", "-v", "error", "-i", webm,
      "-vf", `fps=${args.fps},scale=1280:-1`,
      path.join(framesDir, "f%04d.png"),
    ], { encoding: "utf8" });
    if (extract.status !== 0) {
      console.error(`ffmpeg could not extract frames: ${extract.stderr}`);
      process.exit(2);
    }
    const smallHeight = Math.round(SMALL_WIDTH * VIEWPORT.height / VIEWPORT.width);
    const rawFile = path.join(os.tmpdir(), `design-dna-${args.id}-${process.pid}.gray`);
    const small = spawnSync(args.ffmpeg, [
      "-y", "-v", "error", "-i", webm,
      "-vf", `fps=${args.fps},scale=${SMALL_WIDTH}:${smallHeight},format=gray`,
      "-f", "rawvideo", "-pix_fmt", "gray", rawFile,
    ], { encoding: "utf8" });
    if (small.status !== 0) {
      console.error(`ffmpeg could not reduce the video for differencing: ${small.stderr}`);
      process.exit(2);
    }
    const smallFrames = readSmallFrames(rawFile, SMALL_WIDTH, smallHeight);
    fs.rmSync(rawFile, { force: true });
    const signal = smallFrames.map((f, i) => (i === 0 ? 0 : diffFrames(smallFrames[i - 1], f, SMALL_WIDTH, smallHeight).pct));

    const fullFrames = fs.readdirSync(framesDir).filter((f) => f.endsWith(".png")).sort();
    const { events, quiet } = buildEvents(log, smallFrames, signal, args.fps, SMALL_WIDTH, smallHeight, duration);

    const eventFiles = [];
    events.forEach((ev, i) => {
      const id = `e${String(i + 1).padStart(3, "0")}`;
      const name = `${id}-${ev.kind}${slug(ev.target) ? "-" + slug(ev.target) : ""}.png`;
      const inputs = ev.times.map((t) => path.join(framesDir, fullFrames[frameIndex(t, args.fps, fullFrames.length)]));
      const filterParts = inputs.map((_, k) => `[${k}]scale=640:-1,pad=648:ih+8:4:4:color=black[p${k}]`);
      const tile = spawnSync(args.ffmpeg, [
        "-y", "-v", "error",
        ...inputs.flatMap((f) => ["-i", f]),
        "-filter_complex", `${filterParts.join(";")};[p0][p1][p2][p3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0`,
        path.join(eventsDir, name),
      ], { encoding: "utf8" });
      if (tile.status !== 0) {
        console.error(`ffmpeg could not tile event ${id}: ${tile.stderr}`);
        process.exit(2);
      }
      eventFiles.push({
        id, file: `${args.id}-events/${name}`, kind: ev.kind, target: ev.target,
        t: round1(ev.t), frames_s: ev.times.map(round1),
        magnitude_pct: ev.magnitude_pct ?? null, changed_area_pct: ev.changed_area_pct ?? null,
        region: ev.region ?? null, settle_s: ev.settle_s ?? null,
        ...(ev.kind === "travel" ? { steps: ev.steps, y_from: ev.y_from, y_to: ev.y_to } : {}),
      });
    });

    const record = {
      tool: TOOL_NAME,
      schema_version: SCHEMA_VERSION,
      id: args.id,
      url: args.url,
      recorded_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      viewport: VIEWPORT,
      duration_s: duration,
      fps: args.fps,
      frames: fullFrames.length,
      frames_dir: `${args.id}-frames`,
      events: eventFiles.length,
      event_files: eventFiles,
      quiet: quiet.map((q) => ({ kind: q.kind, target: q.target, t: round1(q.t), magnitude_pct: q.magnitude_pct })),
      video: { file: `${args.id}-recording.webm`, sha256: sha256(webm) },
      video_elements: videoElements,
      pages_visited: pages,
      cursor_path: log,
      difference_signal: { fps: args.fps, small: { width: SMALL_WIDTH, height: smallHeight }, pct: signal.map(round2) },
    };
    const out = path.join(args.out, `${args.id}-recording.json`);
    fs.writeFileSync(out, JSON.stringify(record, null, 1), "utf8");

    // the skeleton of the inventory: one row per event with its numbers
    const md = [
      `# ${args.id} events`,
      "",
      `${args.url}, ${duration}s, ${fullFrames.length} frames at ${args.fps}fps, ${eventFiles.length} events, ${quiet.length} quiet hovers.`,
      "Each event sheet shows before, during, after and settled, left to right, top to bottom.",
      "",
      "| Event | t | Kind | Target | Changed | Where | Settled after |",
      "| --- | --- | --- | --- | --- | --- | --- |",
      ...eventFiles.map((e) =>
        `| ${e.id} | ${e.t}s | ${e.kind} | ${e.target.replace(/\|/g, "/")} | ${e.magnitude_pct ?? "-"}% | ${e.region ?? "-"} | ${e.settle_s ?? "-"}s |`),
      "",
      quiet.length ? "Quiet (hovered, nothing changed): " + quiet.map((q) => `${q.target} (${q.t}s)`).join("; ") : "",
      "",
    ].join("\n");
    fs.writeFileSync(path.join(args.out, `${args.id}-events.md`), md, "utf8");

    console.error(
      `${args.id}: ${duration}s recorded, ${fullFrames.length} frames at ${args.fps}fps, ` +
      `${eventFiles.length} events (${quiet.length} quiet hovers dropped), ` +
      `${log.filter((l) => l.action === "hover").length} hovers, ${pages.length} page(s) -> ${out}`
    );
    if (videoElements.length) {
      console.error(
        `${args.id}: ${videoElements.length} <video> element(s) present at load ` +
        `(${videoElements.map((v) => `${v.w}x${v.h} at (${v.left},${v.top})`).join("; ")}) ` +
        "-- these are NOT photographs; watch that spot in the frame sheet and narrate it as video."
      );
    }
  }
}

main();
