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
 *   - it drives both wide and narrow pages with a real cursor, recursively
 *     traverses every same-origin link, declared state, and native/transform
 *     scroll surface, and dwells on every discovered interactive target,
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
 *     <id>-recording.json (schema 4) plus an external artifact ledger binding
 *     both profile videos, every frame/event sheet, cursor path and diff. Two
 *     event-index tables carry the numbers that form the skeleton of the
 *     behaviour inventory the producer then writes by hand.
 *
 * Full frames at --fps stay in <id>-wide-frames/ and <id>-narrow-frames/
 * for anyone who wants to look
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
 *     --out .design-dna/references --state-contract strong-1-state-contract.json \
 *     [--seconds 90] [--fps 15] \
 *     [--browser-executable FILE] [--ffmpeg FILE]
 */
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { applyManifestState, canonicalJson, captureInteractionCensus, captureRenderedQA, collectSameOriginLinks, inferAndReconcileStates, installDomInspection, mergeSourceRenderedQA,
  navigateExact, normalizeHttpUrl, traverseScrollSurfaces, validateManifestState } from "./browser_evidence.mjs";
import { browserExecutableIdentity, discoverBrowserExecutable, resolvePlaywright } from "./playwright_resolver.mjs";

const TOOL_NAME = "record_reference.mjs";
const SCHEMA_VERSION = 4;
const SCRIPT_PATH = path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const PRODUCER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(SCRIPT_PATH)).digest("hex");
const BROWSER_EVIDENCE_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "browser_evidence.mjs"))).digest("hex");
const PLAYWRIGHT_RESOLVER_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "playwright_resolver.mjs"))).digest("hex");
const VIEWPORTS = [{ name: "wide", width: 1440, height: 900 }, { name: "narrow", width: 390, height: 844 }];
const SMALL_WIDTH = 320;

const HOVER_DWELL_MS = 1600;      // long enough for a slow expansion and a caption
const HOVER_SETTLE_MS = 700;      // after mouse-out, so the un-hover plays too
const SCROLL_PAUSE_MS = 1200;
const INTRO_WAIT_MS = 3500;

// percent of the screen (mean absolute difference over the gray frame, 0-100)
const QUIET_PCT = 0.6;        // below this an action changed nothing worth a frame
const SPONTANEOUS_PCT = 1.2;  // a change nobody caused
const SETTLE_PCT = 0.25;      // frame-to-frame, the page has stopped moving
const PIXEL_CHANGED = 24;     // 0-255, one pixel counts as changed

function parseArgs(argv) {
  const out = {
    url: null, id: null, out: null, seconds: 300, fps: 15,
    browser: process.env.DESIGN_DNA_BROWSER_EXECUTABLE || process.env.CHROME || null, ffmpeg: process.env.FFMPEG || "ffmpeg", stateContract: null,
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
    else if (a === "--state-contract") out.stateContract = argv[++i];
    else if (a === "--help" || a === "-h") {
      process.stdout.write("record_reference.mjs --url URL --id strong-N --out DIR --state-contract FILE [--seconds 300] [--fps 15] [--browser-executable FILE] [--ffmpeg FILE]\n");
      process.exit(0);
    } else {
      process.stdout.write(JSON.stringify({ ok: false, error: { code: "unknown-argument", message: `Unrecognized argument: ${a}` } }, null, 2) + "\n");
      process.exit(2);
    }
  }
  return out;
}

export function recordingSettingsError({ seconds, fps }) {
  if (!Number.isFinite(seconds) || seconds < 90) return "--seconds must be at least 90; shorter recordings cannot reconcile full interaction coverage.";
  if (!Number.isFinite(fps) || fps < 15) return "--fps must be at least 15; lower sampling misses slow or brief motion.";
  return null;
}

function loadPlaywright() {
  return resolvePlaywright({ moduleUrl: import.meta.url });
}

function loadBrowserDependency(loaded, explicit) {
  return browserExecutableIdentity(
    discoverBrowserExecutable(loaded.playwright, explicit),
  );
}

const sha256 = (file) => createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const round1 = (n) => +Number(n).toFixed(1);
const round2 = (n) => +Number(n).toFixed(2);

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
    } else if (["click", "navigate", "focus", "keyboard", "input", "programmatic", "none"].includes(a.action)) {
      flushTravel();
      const times = [a.t_start - 0.15, a.t_start + 0.5, a.t_start + 1.5, a.t_end - 0.1];
      const change = diffFrames(at(times[0]), at(times[3]), width, height);
      events.push({
        kind: a.action, action: a.action, target: a.target, t: a.t_start, x: a.x, y: a.y, times,
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
    else if (["click", "navigate", "focus", "keyboard", "input", "programmatic", "none"].includes(a.action)) cover(a.t_start - 0.2, a.t_end + 0.5);
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
  for (const p of peaks) {
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

function readStateContract(file, id, primaryUrl) {
  let payload;
  try { payload = JSON.parse(fs.readFileSync(file, "utf8")); }
  catch (error) { throw new Error(`State contract unreadable: ${String(error).slice(0, 180)}`); }
  if (payload?.schema_version !== 1 || payload.reference_id !== id || !Array.isArray(payload.states) ||
      Object.keys(payload).some((key) => !["schema_version", "reference_id", "states"].includes(key))) throw new Error("State contract must be exact schema 1 for this reference id.");
  const ids = new Set();
  for (const state of payload.states) {
    const core = state && { id: state.id, kind: state.kind, trigger: state.trigger, expectation: state.expectation };
    if (!state?.url || Object.keys(state).some((key) => !["id", "url", "kind", "trigger", "expectation"].includes(key)) ||
        Object.keys(state.trigger || {}).some((key) => !["type", "target", "value"].includes(key)) ||
        validateManifestState(core) || ids.has(state.id)) throw new Error("Every source state needs a unique id, exact URL, kind, trigger and expectation.");
    state.url = normalizeHttpUrl(state.url);
    if (new URL(state.url).origin !== new URL(primaryUrl).origin) throw new Error(`${state.id}: source state must remain same-origin.`);
    ids.add(state.id);
  }
  if (!payload.states.some((state) => state.id === "rest" && state.url === normalizeHttpUrl(primaryUrl))) throw new Error("State contract must include rest for the primary exact URL.");
  return { payload, file: path.resolve(file), sha256: sha256(path.resolve(file)) };
}

async function requireSafeConsent(page) {
  const result = await page.evaluate(() => {
    const containers = [...document.querySelectorAll('[role="dialog"],[aria-modal="true"],#onetrust-banner-sdk,[class*="cookie" i],[id*="cookie" i],[class*="consent" i],[id*="consent" i]')];
    const consent = containers.find((element) => /cookie|privacy|consent|tracking/i.test(`${element.id} ${element.className} ${element.getAttribute('aria-label') || ''} ${element.textContent || ''}`));
    if (!consent) return { present: false };
    const safe = ['reject','reject all','decline','decline all','only necessary','necessary only','essential only'];
    const button = [...consent.querySelectorAll('button')].find((element) => safe.includes((element.textContent || '').trim().replace(/\s+/g, ' ').toLowerCase()));
    if (!button) return { present: true, dismissed: false };
    const label = (button.textContent || '').trim(); button.click(); return { present: true, dismissed: true, label };
  });
  if (result.present && !result.dismissed) throw new Error("Consent dialog has no exact reject/necessary-only action; recorder will not make an ambiguous choice.");
  if (result.dismissed) await sleep(500);
  return result;
}

async function markPointerTargets(frame) {
  await frame.evaluate(() => {
    let sequence = Number(window.__dnaRecordPointer || 0);
    const roots = [document];
    for (let index = 0; index < roots.length; index += 1) roots[index].querySelectorAll('*').forEach((element) => { if (element.shadowRoot) roots.push(element.shadowRoot); });
    for (const root of roots) for (const element of root.querySelectorAll('*')) {
      if (getComputedStyle(element).cursor !== 'pointer') continue;
      if (!element.dataset.dnaRecordPointer) element.dataset.dnaRecordPointer = String(++sequence);
    }
    window.__dnaRecordPointer = sequence;
  }).catch(() => {});
}

async function hoverAllTargets(page, log, clock, coverage, profile, visibleOnly = false) {
  const selector = 'a[href],button,[role="button"],input,select,textarea,summary,[onclick],[tabindex],[data-dna-record-pointer]';
  for (const frame of page.frames()) {
    await markPointerTargets(frame);
    const targets = await frame.locator(selector).all();
    for (const target of targets) {
      let identity = null;
      try {
        if (!(await target.isVisible())) continue;
        identity = await target.evaluate((element) => {
          window.__dnaRecordTarget = Number(window.__dnaRecordTarget || 0);
          if (!element.dataset.dnaRecordTarget) element.dataset.dnaRecordTarget = String(++window.__dnaRecordTarget);
          return { id: element.dataset.dnaRecordTarget, tag: element.tagName.toLowerCase(),
            text: (element.getAttribute('aria-label') || element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 200) };
        });
        const key = `${normalizeHttpUrl(page.url())}|${frame.url()}|${identity.id}`;
        coverage.discovered.add(key);
        if (coverage.hovered.has(key)) continue;
        if (clock.over()) return false;
        let box = await target.boundingBox();
        if (visibleOnly && (!box || box.x + box.width <= 0 || box.y + box.height <= 0 ||
            box.x >= (page.viewportSize()?.width || 0) || box.y >= (page.viewportSize()?.height || 0))) continue;
        if (!visibleOnly) { await target.scrollIntoViewIfNeeded(); box = await target.boundingBox(); }
        if (!box || box.width < 1 || box.height < 1) continue;
        const entry = { action: "hover", profile, page_url: page.url(), t_start: clock.now(),
          x: Math.round(box.x + box.width / 2), y: Math.round(box.y + box.height / 2),
          target: `${identity.tag} ${identity.text}`.trim() };
        await target.hover({ timeout: 5000 }); await sleep(HOVER_DWELL_MS);
        entry.t_end = clock.now();
        await page.mouse.move(2, 2); await sleep(HOVER_SETTLE_MS); entry.t_left = clock.now();
        log.push(entry); coverage.hovered.add(key); coverage.hover_failures.delete(key);
      } catch (error) {
        if (identity) coverage.hover_failures.set(`${page.url()}|${frame.url()}|${identity.id}`, String(error).slice(0, 180));
      }
    }
  }
  return !clock.over();
}

async function collectVideos(page, profile) {
  const rows = [];
  for (const frame of page.frames()) rows.push(...await frame.evaluate(() => [...document.querySelectorAll('video')].map((video) => {
    const box = video.getBoundingClientRect();
    return { src: video.currentSrc || video.src || '', loop: video.loop, autoplay: video.autoplay, muted: video.muted,
      top: Math.round(box.top), left: Math.round(box.left), w: Math.round(box.width), h: Math.round(box.height) };
  })).catch(() => []));
  return rows.map((row) => ({ profile, page_url: page.url(), ...row }));
}

function mergeRecorderInteractionCensuses(profile, censuses) {
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
  const repeatClasses = [...new Set(targets.map((target) => target.repeat_class))].sort().map((repeatClass) => {
    const members = targets.filter((target) => target.repeat_class === repeatClass);
    const inputKinds = [...new Set(members.flatMap((target) => target.inputs.map((input) => input.input_kind)))].sort();
    const behaviorSignatures = [...new Set(members.flatMap((target) => target.inputs.filter((input) => input.status === 'exercised')
      .map((input) => `${input.input_kind}:${input.behavior}`)))].sort();
    return { repeat_class: repeatClass, target_ids: members.map((target) => target.target_id), input_kinds: inputKinds,
      equivalent: inputKinds.every((kind) => new Set(members.flatMap((target) => target.inputs
        .filter((input) => input.input_kind === kind && input.status === 'exercised').map((input) => input.behavior))).size <= 1),
      behavior_signatures: behaviorSignatures,
      evidence: members.flatMap((target) => target.inputs.map((input) => input.evidence).filter(Boolean)) };
  });
  const missing = censuses.flatMap((census) => census.missing || []);
  const pageStates = [...new Map(censuses.flatMap((census) => census.page_states || [])
    .map((state) => [`${state.page_url}|${state.source_state_id}`, state])).values()];
  const pointerFollow = [...new Map(censuses.flatMap((census) => census.pointer_follow || [])
    .map((item) => [`${item.page_url}|${item.target_id}`, item])).values()];
  const blockedSideEffects = [...new Map(censuses.flatMap((census) => census.blocked_side_effects || [])
    .map((item) => [`${item.target_id}|${item.input_kind}`, item])).values()];
  return { profile, pages, page_states: pageStates, repeat_classes: repeatClasses,
    pointer_follow: pointerFollow,
    blocked_side_effects: blockedSideEffects,
    totals: censuses.reduce((sum, census) => ({ targets_discovered: sum.targets_discovered + Number(census.totals?.targets_discovered || 0),
      inputs_discovered: sum.inputs_discovered + Number(census.totals?.inputs_discovered || 0),
      inputs_exercised: sum.inputs_exercised + Number(census.totals?.inputs_exercised || 0),
      inputs_blocked: sum.inputs_blocked + Number(census.totals?.inputs_blocked || 0) }),
    { targets_discovered: 0, inputs_discovered: 0, inputs_exercised: 0, inputs_blocked: 0 }),
    truncated: false, missing, complete: missing.length === 0 && censuses.every((census) => census.complete && census.truncated === false) };
}

async function runProfile(browser, args, stateContract, viewport) {
  const videoDir = fs.mkdtempSync(path.join(os.tmpdir(), `design-dna-${viewport.name}-rec-`));
  const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1,
    recordVideo: { dir: videoDir, size: { width: viewport.width, height: viewport.height } } });
  await installDomInspection(context);
  const page = await context.newPage();
  const videoHandle = page.video();
  const interactionEvidenceDirName = `${args.id}-${viewport.name}-interaction-evidence`;
  const interactionEvidenceDir = path.join(args.out, interactionEvidenceDirName);
  fs.rmSync(interactionEvidenceDir, { recursive: true, force: true }); fs.mkdirSync(interactionEvidenceDir, { recursive: true });
  let interactionEvidenceSequence = 0;
  const log = [], navigations = [], videoElements = [], scrollTraversals = [], interactionCensuses = [], renderedQARecords = [];
  const seededUrls = [...new Set([normalizeHttpUrl(args.url), ...stateContract.states.map((state) => normalizeHttpUrl(state.url))])];
  const coverage = { discovered: new Set(), hovered: new Set(), hover_failures: new Map(),
    internalDiscovered: new Set(seededUrls), internalVisited: new Set(),
    statesRequired: new Set(stateContract.states.map((state) => state.id)), statesVisited: new Set(), stateInventories: [] };
  const started = Date.now();
  // `--seconds` is a minimum recording floor, never a coverage budget. Work
  // continues past it until every route/state/surface/target is complete.
  const clock = { now: () => +((Date.now() - started) / 1000).toFixed(2), over: () => false };
  const queue = [...seededUrls], origin = new URL(args.url).origin;
  const captureInteractionEvidence = async (label, targetPage = page, stateId = null) => {
    interactionEvidenceSequence += 1;
    const safe = String(label).toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/^-+|-+$/g, '');
    const fileName = `${String(interactionEvidenceSequence).padStart(5, '0')}-${safe}.png`;
    const buffer = await targetPage.screenshot({ path: path.join(interactionEvidenceDir, fileName) });
    return { profile: viewport.name, state_id: stateId, label, video_t_s: clock.now(),
      file: `${interactionEvidenceDirName}/${fileName}`, bytes: buffer.length, sha256: createHash('sha256').update(buffer).digest('hex') };
  };
  const captureCensusUntilStable = async (pageUrl, states, stateId = null) => {
    const knownTargets = new Set();
    const localCensuses = [];
    while (true) {
      const census = await captureInteractionCensus(page, { profile: viewport.name, pageUrl,
        authoredStates: states,
        captureEvidence: (label, targetPage = page) => captureInteractionEvidence(label, targetPage, stateId) });
      interactionCensuses.push(census);
      localCensuses.push(census);
      const ids = census.pages.flatMap((pageRecord) => pageRecord.targets.map((target) => target.target_id));
      const newIds = ids.filter((id) => !knownTargets.has(id)); ids.forEach((id) => knownTargets.add(id));
      if (!newIds.length) break;
    }
    return mergeRecorderInteractionCensuses(viewport.name, localCensuses);
  };
  let runError = null;
  try {
    while (queue.length) {
      const targetUrl = queue.shift();
      if (coverage.internalVisited.has(targetUrl)) continue;
      const navLog = { action: "navigate", profile: viewport.name, target: targetUrl, t_start: clock.now() };
      const navigation = await navigateExact(page, targetUrl);
      navLog.t_end = clock.now(); log.push(navLog); navigations.push(navigation);
      await page.evaluate(() => document.fonts?.ready).catch(() => {});
      await requireSafeConsent(page);
      if (coverage.internalVisited.size === 0) await sleep(INTRO_WAIT_MS);
      else await sleep(500);
      videoElements.push(...await collectVideos(page, viewport.name));
      await hoverAllTargets(page, log, clock, coverage, viewport.name);
      const traversal = await traverseScrollSurfaces(page, { maxTicks: 240, settleMs: SCROLL_PAUSE_MS,
        deadline: clock.over,
        onTick: async (surface, tick, sample) => {
          const event = { action: "scroll", profile: viewport.name, page_url: page.url(), surface: surface.id,
            target: surface.selector_hint || surface.kind, tick, t_start: clock.now(), y: sample.y };
          await hoverAllTargets(page, log, clock, coverage, viewport.name, true);
          event.t_end = clock.now(); log.push(event);
        } });
      scrollTraversals.push({ url: targetUrl, ...traversal });
      const applicableStates = stateContract.states.filter((state) => normalizeHttpUrl(state.url) === targetUrl);
      const stateInventory = await inferAndReconcileStates(page, applicableStates);
      coverage.stateInventories.push({ url: targetUrl, ...stateInventory });
      const pageInteractionCensus = await captureCensusUntilStable(targetUrl, applicableStates);
      renderedQARecords.push(await captureRenderedQA(page, { profile: viewport.name, pageUrl: targetUrl,
        sourceState: applicableStates.find((state) => state.trigger?.type === 'none') || null,
        interactionCensus: pageInteractionCensus,
        captureEvidence: (label, targetPage = page) => captureInteractionEvidence(label, targetPage) }));
      const links = await collectSameOriginLinks(page, origin);
      links.forEach((link) => { if (!coverage.internalDiscovered.has(link)) { coverage.internalDiscovered.add(link); queue.push(link); } });
      if (coverage.internalDiscovered.size > 1000) throw new Error("More than 1000 recursive same-origin pages were discovered; complete traversal cannot be established.");
      coverage.internalVisited.add(targetUrl);
    }
    for (const state of stateContract.states) {
      const navigation = await navigateExact(page, state.url); navigations.push(navigation);
      await requireSafeConsent(page);
      const tStart = clock.now();
      const application = await applyManifestState(page, state);
      if (application.navigation) navigations.push(application.navigation);
      const tEnd = clock.now();
      log.push({ action: state.trigger.type === "url" ? "navigate" : state.trigger.type,
        profile: viewport.name, state_id: state.id, target: state.trigger.target, t_start: tStart, t_end: tEnd,
        t_left: tEnd, trigger_evidence: application.trigger_evidence });
      coverage.statesVisited.add(state.id);
      const stateInteractionCensus = await captureCensusUntilStable(state.url,
        stateContract.states.filter((item) => normalizeHttpUrl(item.url) === normalizeHttpUrl(state.url)), state.id);
      renderedQARecords.push(await captureRenderedQA(page, { profile: viewport.name, pageUrl: state.url,
        sourceState: state, interactionCensus: stateInteractionCensus,
        captureEvidence: (label, targetPage = page) => captureInteractionEvidence(label, targetPage, state.id) }));
    }
    while (Date.now() - started < args.seconds * 1000) {
      await sleep(Math.min(1000, Math.max(1, args.seconds * 1000 - (Date.now() - started))));
    }
  } catch (error) { runError = error; }
  const duration = +((Date.now() - started) / 1000).toFixed(2);
  await context.close();
  const sourceVideo = videoHandle ? await videoHandle.path() : null;
  if (runError) {
    fs.rmSync(videoDir, { recursive: true, force: true });
    fs.rmSync(interactionEvidenceDir, { recursive: true, force: true });
    throw runError;
  }
  const missingHovers = [...coverage.discovered].filter((key) => !coverage.hovered.has(key));
  const missingPages = [...coverage.internalDiscovered].filter((url) => !coverage.internalVisited.has(url));
  const missingStates = [...coverage.statesRequired].filter((id) => !coverage.statesVisited.has(id));
  const incompleteScrolls = scrollTraversals.filter((item) => !item.complete);
  const unreconciledStates = coverage.stateInventories.flatMap((item) => item.unreconciled.map((state) => ({ url: item.url, ...state })));
  const interactionCensus = mergeRecorderInteractionCensuses(viewport.name, interactionCensuses);
  const renderedQA = mergeSourceRenderedQA(viewport.name, renderedQARecords);
  return { profile: viewport.name, viewport, duration_s: duration, source_video: sourceVideo, video_dir: videoDir,
    interaction_evidence_dir: interactionEvidenceDirName,
    log, navigations, video_elements: videoElements, scroll_traversals: scrollTraversals,
    coverage: { interactive_targets_discovered: coverage.discovered.size, interactive_targets_hovered: coverage.hovered.size,
      missing_interactive_targets: missingHovers, hover_failures: Object.fromEntries(coverage.hover_failures),
      internal_pages_discovered: coverage.internalDiscovered.size, internal_pages_visited: coverage.internalVisited.size,
      internal_pages_discovered_urls: [...coverage.internalDiscovered].sort(),
      internal_pages_visited_urls: [...coverage.internalVisited].sort(),
      missing_internal_pages: missingPages, states_required: [...coverage.statesRequired], states_visited: [...coverage.statesVisited],
      missing_states: missingStates, incomplete_scroll_traversals: incompleteScrolls.map((item) => item.url),
      state_inventories: coverage.stateInventories, unreconciled_states: unreconciledStates,
      duration_floor_met: duration >= args.seconds,
      complete: !missingHovers.length && !coverage.hover_failures.size && !missingPages.length && !missingStates.length && !unreconciledStates.length &&
        !incompleteScrolls.length && interactionCensus.complete && renderedQA.complete && duration >= args.seconds },
      interaction_census: interactionCensus, rendered_qa: renderedQA };
}

function artifactEntry(root, file, kind, profile = null) {
  const absolute = path.join(root, file);
  return { kind, profile, file: file.replace(/\\/g, "/"), bytes: fs.statSync(absolute).size, sha256: sha256(absolute) };
}

function processProfile(args, run) {
  if (!run.source_video || !fs.existsSync(run.source_video)) throw new Error(`${run.profile}: Playwright did not produce a recording video.`);
  const prefix = `${args.id}-${run.profile}`;
  const videoFile = `${prefix}-recording.webm`, videoPath = path.join(args.out, videoFile);
  fs.copyFileSync(run.source_video, videoPath); fs.rmSync(run.video_dir, { recursive: true, force: true });
  const framesDirName = `${prefix}-frames`, eventsDirName = `${prefix}-events`;
  const framesDir = path.join(args.out, framesDirName), eventsDir = path.join(args.out, eventsDirName);
  for (const directory of [framesDir, eventsDir]) { fs.rmSync(directory, { recursive: true, force: true }); fs.mkdirSync(directory, { recursive: true }); }
  const extract = spawnSync(args.ffmpeg, ["-y", "-v", "error", "-i", videoPath, "-vf", `fps=${args.fps},scale=${run.viewport.width}:-1`, path.join(framesDir, "f%05d.png")], { encoding: "utf8" });
  if (extract.status !== 0) throw new Error(`${run.profile}: frame extraction failed: ${extract.stderr}`);
  const smallHeight = Math.round(SMALL_WIDTH * run.viewport.height / run.viewport.width);
  const rawFile = path.join(os.tmpdir(), `design-dna-${args.id}-${run.profile}-${process.pid}.gray`);
  const small = spawnSync(args.ffmpeg, ["-y", "-v", "error", "-i", videoPath,
    "-vf", `fps=${args.fps},scale=${SMALL_WIDTH}:${smallHeight},format=gray`, "-f", "rawvideo", "-pix_fmt", "gray", rawFile], { encoding: "utf8" });
  if (small.status !== 0) throw new Error(`${run.profile}: difference extraction failed: ${small.stderr}`);
  const smallFrames = readSmallFrames(rawFile, SMALL_WIDTH, smallHeight); fs.rmSync(rawFile, { force: true });
  const signal = smallFrames.map((frame, index) => index === 0 ? 0 : diffFrames(smallFrames[index - 1], frame, SMALL_WIDTH, smallHeight).pct);
  const fullFrames = fs.readdirSync(framesDir).filter((file) => file.endsWith(".png")).sort();
  if (!fullFrames.length || fullFrames.length < Math.floor(run.duration_s * args.fps * 0.9)) throw new Error(`${run.profile}: extracted frame count is below the recorded ${args.fps}fps floor.`);
  const frameFiles = fullFrames.map((file) => artifactEntry(args.out, path.join(framesDirName, file), "frame", run.profile));
  const { events, quiet } = buildEvents(run.log, smallFrames, signal, args.fps, SMALL_WIDTH, smallHeight, run.duration_s);
  const eventFiles = [];
  events.forEach((event, index) => {
    const id = `e${String(index + 1).padStart(4, "0")}`, name = `${id}-${event.kind}${slug(event.target) ? "-" + slug(event.target) : ""}.png`;
    const inputs = event.times.map((time) => path.join(framesDir, fullFrames[frameIndex(time, args.fps, fullFrames.length)]));
    const filters = inputs.map((_, item) => `[${item}]scale=640:-1,pad=648:ih+8:4:4:color=black[p${item}]`);
    const tile = spawnSync(args.ffmpeg, ["-y", "-v", "error", ...inputs.flatMap((file) => ["-i", file]),
      "-filter_complex", `${filters.join(";")};[p0][p1][p2][p3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0`, path.join(eventsDir, name)], { encoding: "utf8" });
    if (tile.status !== 0) throw new Error(`${run.profile}: event ${id} tiling failed: ${tile.stderr}`);
    const artifact = artifactEntry(args.out, path.join(eventsDirName, name), "event-sheet", run.profile);
    eventFiles.push({ id, file: artifact.file, bytes: artifact.bytes, sha256: artifact.sha256, kind: event.kind,
      target: event.target, t: round1(event.t), frames_s: event.times.map(round1), magnitude_pct: event.magnitude_pct ?? null,
      changed_area_pct: event.changed_area_pct ?? null, region: event.region ?? null, settle_s: event.settle_s ?? null });
  });
  const cursorFile = `${prefix}-cursor-path.json`, diffFile = `${prefix}-difference-signal.json`, eventsFile = `${prefix}-events.md`;
  fs.writeFileSync(path.join(args.out, cursorFile), JSON.stringify({ profile: run.profile, actions: run.log }, null, 2) + "\n", "utf8");
  fs.writeFileSync(path.join(args.out, diffFile), JSON.stringify({ profile: run.profile, fps: args.fps,
    small: { width: SMALL_WIDTH, height: smallHeight }, pct: signal.map(round2) }, null, 2) + "\n", "utf8");
  const markdown = [`# ${args.id} ${run.profile} events`, "", `${args.url}, ${run.duration_s}s, ${fullFrames.length} frames at ${args.fps}fps.`, "",
    "| Event | t | Kind | Target | Changed | Where | Settled after |", "| --- | --- | --- | --- | --- | --- | --- |",
    ...eventFiles.map((event) => `| ${event.id} | ${event.t}s | ${event.kind} | ${String(event.target).replace(/\|/g, "/")} | ${event.magnitude_pct ?? "-"}% | ${event.region ?? "-"} | ${event.settle_s ?? "-"}s |`), ""].join("\n");
  fs.writeFileSync(path.join(args.out, eventsFile), markdown, "utf8");
  const interactionArtifacts = fs.readdirSync(path.join(args.out, run.interaction_evidence_dir))
    .filter((file) => file.endsWith('.png')).sort()
    .map((file) => artifactEntry(args.out, path.join(run.interaction_evidence_dir, file), 'interaction-frame', run.profile));
  const artifacts = [artifactEntry(args.out, videoFile, "video", run.profile), ...frameFiles,
    ...eventFiles.map((event) => ({ kind: "event-sheet", profile: run.profile, file: event.file, bytes: event.bytes, sha256: event.sha256 })),
    ...interactionArtifacts,
    artifactEntry(args.out, cursorFile, "cursor-path", run.profile), artifactEntry(args.out, diffFile, "difference-signal", run.profile),
    artifactEntry(args.out, eventsFile, "events-index", run.profile)];
  const bindInteractionEvidence = (value) => {
    if (Array.isArray(value)) return value.map(bindInteractionEvidence);
    if (!value || typeof value !== "object") return value;
    const mapped = Object.fromEntries(Object.entries(value).map(([key, item]) => [key, bindInteractionEvidence(item)]));
    if (Number.isFinite(value.video_t_s)) {
      const index = frameIndex(value.video_t_s, args.fps, frameFiles.length);
      mapped.frame = frameFiles[index] ? { file: frameFiles[index].file, bytes: frameFiles[index].bytes,
        sha256: frameFiles[index].sha256 } : null;
      mapped.video = { file: artifacts[0].file, bytes: artifacts[0].bytes, sha256: artifacts[0].sha256 };
    }
    return mapped;
  };
  const interactionCensus = bindInteractionEvidence(run.interaction_census);
  const renderedQA = bindInteractionEvidence(run.rendered_qa);
  return { profile: run.profile, viewport: run.viewport, duration_s: run.duration_s, fps: args.fps,
    video: artifacts[0], frames: { count: frameFiles.length, directory: framesDirName, files: frameFiles },
    events: { count: eventFiles.length, directory: eventsDirName, files: eventFiles,
      index: artifacts.at(-1), quiet: quiet.map((item) => ({ kind: item.kind, target: item.target, t: round1(item.t), magnitude_pct: item.magnitude_pct })) },
    cursor_path: artifacts.find((item) => item.kind === "cursor-path"),
    difference_signal: artifacts.find((item) => item.kind === "difference-signal"),
    video_elements: run.video_elements, navigations: run.navigations, scroll_traversals: run.scroll_traversals,
    interaction_census: interactionCensus, rendered_qa: renderedQA,
    coverage: run.coverage, artifacts };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.url || !args.id || !args.out || !args.stateContract) throw new Error("--url, --id, --out and --state-contract are required.");
  const settingsError = recordingSettingsError(args); if (settingsError) throw new Error(settingsError);
  const ffmpegProbe = spawnSync(args.ffmpeg, ["-version"], { encoding: "utf8" });
  if (ffmpegProbe.error || ffmpegProbe.status !== 0) throw new Error(`ffmpeg is not runnable at '${args.ffmpeg}'.`);
  fs.mkdirSync(args.out, { recursive: true });
  const stateContract = readStateContract(args.stateContract, args.id, args.url);
  const loaded = loadPlaywright(), playwright = loaded.playwright;
  const browserDependency = loadBrowserDependency(loaded, args.browser);
  const executable = browserDependency.file;
  const browserSha256 = browserDependency.sha256;
  const browser = await playwright.chromium.launch({ executablePath: executable });
  let runs;
  try { runs = []; for (const viewport of VIEWPORTS) runs.push(await runProfile(browser, args, stateContract.payload, viewport)); }
  finally { await browser.close().catch(() => {}); }
  const profiles = runs.map((run) => processProfile(args, run));
  const complete = profiles.every((profile) => profile.coverage.complete);
  const capturesByViewport = Object.fromEntries(profiles.map((profile) => [profile.profile,
    profile.frames.files[0] ? { file: profile.frames.files[0].file, bytes: profile.frames.files[0].bytes,
      sha256: profile.frames.files[0].sha256 } : null]));
  const qualityObservations = profiles.map((profile) => ({ profile: profile.profile,
    pages_observed: profile.coverage.internal_pages_visited,
    states_observed: profile.coverage.states_visited.length,
    hover_targets_observed: profile.coverage.interactive_targets_hovered,
    event_sheets: profile.events.count, video_elements: profile.video_elements.length }));
  const defectObservations = profiles.flatMap((profile) => [
    ...profile.coverage.missing_internal_pages.map((value) => ({ profile: profile.profile, kind: "unvisited-page", value })),
    ...profile.coverage.missing_states.map((value) => ({ profile: profile.profile, kind: "unvisited-state", value })),
    ...profile.coverage.missing_interactive_targets.map((value) => ({ profile: profile.profile, kind: "unobserved-hover-target", value })),
    ...profile.coverage.incomplete_scroll_traversals.map((value) => ({ profile: profile.profile, kind: "incomplete-scroll", value })),
    ...profile.rendered_qa.pages.flatMap((pageRecord) => [
      ...['clipping','collisions','fixed_rail_overlaps','dead_controls','semantic_issues']
        .flatMap((kind) => (pageRecord[kind] || []).map((value) => ({ profile: profile.profile, page_url: pageRecord.url, kind, value }))),
      ...(pageRecord.hidden_controls || []).filter((control) => control.focusable_while_hidden)
        .map((value) => ({ profile: profile.profile, page_url: pageRecord.url, kind: 'hidden-focusable-control', value })),
      ...(pageRecord.state_semantics?.complete === false ? [{ profile: profile.profile, page_url: pageRecord.url,
        kind: 'state-semantics', value: pageRecord.state_semantics }] : []),
      ...(pageRecord.keyboard?.complete === false ? [{ profile: profile.profile, page_url: pageRecord.url,
        kind: 'keyboard-path', value: pageRecord.keyboard }] : []),
      ...(pageRecord.semantic_equivalence?.complete === false ? [{ profile: profile.profile, page_url: pageRecord.url,
        kind: 'semantic-equivalence', value: pageRecord.semantic_equivalence }] : []),
      ...(pageRecord.overlays || []).filter((overlay) => !overlay.complete)
        .map((value) => ({ profile: profile.profile, page_url: pageRecord.url, kind: 'overlay-access', value })),
      ...(!pageRecord.reduced_motion?.honors_preference ? [{ profile: profile.profile, page_url: pageRecord.url,
        kind: 'reduced-motion', value: pageRecord.reduced_motion }] : []),
      ...(pageRecord.dead_end?.problem ? [{ profile: profile.profile, page_url: pageRecord.url,
        kind: 'dead-end', value: pageRecord.dead_end }] : []),
    ]),
  ]);
  const record = { tool: TOOL_NAME, schema_version: SCHEMA_VERSION, producer_script_sha256: PRODUCER_SCRIPT_SHA256,
    runtime_identity: { "record_reference.mjs": PRODUCER_SCRIPT_SHA256, "browser_evidence.mjs": BROWSER_EVIDENCE_SHA256,
      "playwright_resolver.mjs": PLAYWRIGHT_RESOLVER_SHA256,
      "playwright-entry": loaded.dependency.sha256, "browser-executable": browserSha256 },
    dependencies: { recorder: { file: "record_reference.mjs", sha256: PRODUCER_SCRIPT_SHA256 },
      browser_evidence: { file: "browser_evidence.mjs", sha256: BROWSER_EVIDENCE_SHA256 },
      playwright_resolver: { file: "playwright_resolver.mjs", sha256: PLAYWRIGHT_RESOLVER_SHA256 },
      playwright: loaded.dependency, browser_executable: browserDependency },
    id: args.id, url: args.url,
    requested_url: args.url, final_urls: Object.fromEntries(profiles.map((profile) => [profile.profile, profile.navigations[0]?.final_url || null])),
    recorded_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"), minimum_duration_per_profile_s: args.seconds,
    fps: args.fps, state_contract: { file: path.basename(stateContract.file), sha256: stateContract.sha256 },
    captures_by_viewport: capturesByViewport,
    discovery_metadata: Object.fromEntries(profiles.map((profile) => [profile.profile, {
      discovered_urls: profile.coverage.internal_pages_discovered_urls,
      visited_urls: profile.coverage.internal_pages_visited_urls,
      states_required: profile.coverage.states_required,
      states_visited: profile.coverage.states_visited,
    }])),
    quality_observations: qualityObservations,
    defect_observations: defectObservations,
    interaction_census_by_viewport: Object.fromEntries(profiles.map((profile) => [profile.profile, profile.interaction_census])),
    rendered_qa_by_viewport: Object.fromEntries(profiles.map((profile) => [profile.profile, profile.rendered_qa])),
    profiles: Object.fromEntries(profiles.map((profile) => [profile.profile, { ...profile, artifacts: undefined }])),
    coverage: { wide_complete: profiles.find((profile) => profile.profile === "wide")?.coverage.complete === true,
      narrow_complete: profiles.find((profile) => profile.profile === "narrow")?.coverage.complete === true, complete } };
  const recordingFile = `${args.id}-recording.json`, recordingPath = path.join(args.out, recordingFile);
  fs.writeFileSync(recordingPath, JSON.stringify(record, null, 2) + "\n", "utf8");
  const artifacts = [artifactEntry(args.out, recordingFile, "recording"), ...profiles.flatMap((profile) => profile.artifacts)]
    .sort((a, b) => a.file.localeCompare(b.file));
  const ledgerCore = { schema_version: 1, algorithm: "sha256", recording: recordingFile, artifacts };
  const ledger = { ...ledgerCore, sha256: createHash("sha256").update(canonicalJson(ledgerCore)).digest("hex") };
  const ledgerFile = `${args.id}-artifacts.json`;
  fs.writeFileSync(path.join(args.out, ledgerFile), JSON.stringify(ledger, null, 2) + "\n", "utf8");
  process.stdout.write(JSON.stringify({ ok: complete, recording: recordingPath, artifact_ledger: ledgerFile,
    artifact_ledger_sha256: sha256(path.join(args.out, ledgerFile)), profiles: profiles.map((profile) => ({ profile: profile.profile,
      duration_s: profile.duration_s, frames: profile.frames.count, events: profile.events.count, coverage: profile.coverage.complete })) }, null, 2) + "\n");
  if (!complete) process.exitCode = 1;
}

const invokedDirectly = process.argv[1]
  && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
if (invokedDirectly) main().catch((error) => {
  process.stdout.write(JSON.stringify({ ok: false, error: { code: error.code || "recording-failed",
    message: String(error.message || error).slice(0, 800), navigation: error.navigation || null } }, null, 2) + "\n");
  process.exitCode = 2;
});
