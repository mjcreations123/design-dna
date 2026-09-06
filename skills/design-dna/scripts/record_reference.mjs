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
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { applyManifestState, canonicalJson, captureInteractionCensus, captureRenderedQA, collectSameOriginLinks, inferAndReconcileStates, installDomInspection, interactionCensusDiagnostic, mergeSourceGestureInventories, mergeSourceRenderedQA,
  navigateExact, normalizeHttpUrl, traverseScrollSurfaces, validateManifestState, closeBrowserBounded, launchOwnedBrowser, hoverWithPointerFallback, scrollIntoViewBounded, raceBound } from "./browser_evidence.mjs";
import { browserExecutableIdentity, discoverBrowserExecutable, resolvePlaywright } from "./playwright_resolver.mjs";
import { adoptEarlySourceSurfaceWatch, armEarlySourceSurfaceWatch, drainSourceSurfaceWatch, startSourceSurfaceWatch, stopSourceSurfaceWatch, undocumentedSourceSurfaceError } from "./source_surface_watch.mjs";
import { acquireSourceStudyOutputLease, acquireSourceStudyRunnerLease, createSourceStudyController, DEFAULT_SOURCE_STUDY_LIMITS, sourceStudyFailureStatus, sourceStudyPreflightFailure } from "./source_study_controller.mjs";

const TOOL_NAME = "record_reference.mjs";
const SCHEMA_VERSION = 4;
export const RECORDER_PLAYWRIGHT_VERSION = '1.61.1';
const SCRIPT_PATH = path.resolve(fileURLToPath(import.meta.url));
const PRODUCER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(SCRIPT_PATH)).digest("hex");
const BROWSER_EVIDENCE_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "browser_evidence.mjs"))).digest("hex");
const PLAYWRIGHT_RESOLVER_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "playwright_resolver.mjs"))).digest("hex");
const SOURCE_SURFACE_WATCH_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "source_surface_watch.mjs"))).digest("hex");
const SOURCE_STUDY_CONTROLLER_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "source_study_controller.mjs"))).digest("hex");
const VIEWPORTS = [{ name: "wide", width: 1440, height: 900 }, { name: "narrow", width: 390, height: 844 }];
const SMALL_WIDTH = 320;
export const POSTPROCESS_SUBPROCESS_TIMEOUT_MS = 300_000;
export const MAX_RECORDING_SECONDS = Math.floor((DEFAULT_SOURCE_STUDY_LIMITS.max_total_elapsed_ms - 2 * POSTPROCESS_SUBPROCESS_TIMEOUT_MS) / 2000);
export const POSTPROCESS_HEARTBEAT_MS = 5_000;

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

export function exactRecordingDurationMs(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return null;
  const milliseconds = Math.round(seconds * 1000);
  return Number.isSafeInteger(milliseconds) && milliseconds / 1000 === seconds ? milliseconds : null;
}

export function recordingSettingsError({ seconds, fps }) {
  if (!Number.isFinite(seconds) || seconds < 90) return "--seconds must be at least 90; shorter recordings cannot reconcile full interaction coverage.";
  if (exactRecordingDurationMs(seconds) === null) return "--seconds must be exactly millisecond-representable; rounded durations are not source evidence.";
  if (seconds > MAX_RECORDING_SECONDS) return `--seconds must not exceed ${MAX_RECORDING_SECONDS}; two source profiles must remain within the bounded source-study dwell budget.`;
  if (!Number.isFinite(fps) || fps < 15) return "--fps must be at least 15; lower sampling misses slow or brief motion.";
  if (!Number.isInteger(fps) || fps > 60) return "--fps must be an integer no greater than 60; recording extraction has an explicit frame-data bound.";
  return null;
}

export function verifyRecorderPlaywright(dependency, sourceStudyOptions) {
  if (dependency?.version !== RECORDER_PLAYWRIGHT_VERSION) throw sourceStudyPreflightFailure(sourceStudyOptions,
    'source-study-recorder-runtime-unqualified',
    `The recorder requires the audited Playwright ${RECORDER_PLAYWRIGHT_VERSION} runtime for its timestamped video and backing-artifact protocol. Use the pinned shared dependency bundle; no browser was opened and no automatic upgrade was attempted.`,
    { required_version: RECORDER_PLAYWRIGHT_VERSION, observed_version: dependency?.version || null });
}

export function verifySourceEncoder(command, sourceStudyOptions, { probeArgs = ['-version'], timeoutMs = 5000 } = {}) {
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 5000) throw new Error('Encoder preflight timeout must be within the fixed 5000ms ceiling.');
  const probe = spawnSync(command, probeArgs, { encoding: 'utf8', timeout: timeoutMs, windowsHide: true });
  if (probe.error || probe.status !== 0) throw sourceStudyPreflightFailure(sourceStudyOptions,
    probe.error?.code === 'ETIMEDOUT' ? 'source-study-preflight-timeout' : 'source-study-preflight-unavailable',
    `Encoder preflight did not complete successfully within its ${timeoutMs}ms bound at '${command}'.`,
    { source_error: String(probe.error?.message || probe.stderr || `exit ${probe.status}`), timeout_ms: timeoutMs });
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

export async function runBoundedSourceSubprocess({
  command, args, label, sourceStudy, timeoutMs = POSTPROCESS_SUBPROCESS_TIMEOUT_MS,
  heartbeatMs = POSTPROCESS_HEARTBEAT_MS, cwd = undefined, progressProbe = null,
}) {
  if (!sourceStudy || typeof sourceStudy.progress !== 'function' || typeof sourceStudy.terminate !== 'function') {
    throw new Error(`${label}: bounded postprocess requires a source study controller.`);
  }
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > DEFAULT_SOURCE_STUDY_LIMITS.max_total_elapsed_ms ||
      !Number.isInteger(heartbeatMs) || heartbeatMs < 1 || heartbeatMs > timeoutMs) {
    throw new Error(`${label}: invalid bounded postprocess timeout/heartbeat.`);
  }
  sourceStudy.progress('postprocess-start', { label, command, args: args.map(String), timeout_ms: timeoutMs });
  const started = Date.now();
  let child;
  try { child = spawn(command, args, { cwd, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] }); }
  catch (error) {
    throw sourceStudy.terminate('source-study-postprocess-spawn-failed', `${label}: unable to spawn bounded postprocess.`,
      { source_error: String(error?.message || error) });
  }
  let stdout = '', stderr = '', outputBytes = 0, timeoutError = null, controllerError = null;
  let priorOutputBytes = 0, priorProbeValue = null;
  child.stdout?.on('data', (chunk) => { stdout += chunk; outputBytes += chunk.length; });
  child.stderr?.on('data', (chunk) => { stderr += chunk; outputBytes += chunk.length; });
  const close = new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('close', (code, signal) => resolve({ code, signal }));
  });
  const heartbeat = setInterval(() => {
    if (timeoutError || controllerError) return;
    try {
      let probeValue = null;
      try {
        const measured = typeof progressProbe === 'function' ? progressProbe() : null;
        probeValue = Number.isFinite(measured) ? Number(measured) : null;
      } catch { probeValue = null; }
      const advanced = outputBytes > priorOutputBytes || (probeValue !== null && (priorProbeValue === null || probeValue > priorProbeValue));
      if (advanced) {
        sourceStudy.progress('postprocess-chunk', { label, elapsed_ms: Date.now() - started,
          output_bytes: outputBytes, probe_value: probeValue });
        priorOutputBytes = outputBytes;
        priorProbeValue = probeValue;
      } else {
        sourceStudy.assertHealthy();
      }
    } catch (error) {
      controllerError = error;
      child.kill('SIGKILL');
    }
  }, heartbeatMs);
  const deadline = setTimeout(() => {
    if (timeoutError) return;
    timeoutError = sourceStudy.terminate('source-study-postprocess-timeout',
      `${label} exceeded its explicit ${timeoutMs}ms postprocess bound; the child process was killed.`,
      { command, args: args.map(String), timeout_ms: timeoutMs, elapsed_ms: Date.now() - started });
    child.kill('SIGKILL');
  }, timeoutMs);
  let result;
  try { result = await close; }
  catch (error) {
    clearInterval(heartbeat); clearTimeout(deadline);
    throw sourceStudy.terminate('source-study-postprocess-child-error', `${label}: postprocess child failed before completion.`,
      { source_error: String(error?.message || error) });
  }
  clearInterval(heartbeat); clearTimeout(deadline);
  if (controllerError) throw controllerError;
  if (timeoutError) throw timeoutError;
  if (result.code !== 0) {
    throw sourceStudy.terminate('source-study-postprocess-failed', `${label}: postprocess exited ${result.code ?? 'null'}${result.signal ? ` (${result.signal})` : ''}.`,
      { command, args: args.map(String), exit_code: result.code, signal: result.signal, stderr: stderr.slice(-4000) });
  }
  sourceStudy.progress('postprocess-complete', { label, elapsed_ms: Date.now() - started, output_bytes: outputBytes });
  return { stdout, stderr, elapsed_ms: Date.now() - started };
}

function writeJsonAtomically(file, payload) {
  const temporary = `${file}.tmp-${process.pid}-${Date.now()}`;
  fs.writeFileSync(temporary, JSON.stringify(payload, null, 2) + "\n", "utf8");
  fs.renameSync(temporary, file);
}

function retainedArtifacts(root, directory, kind, profile) {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => {
      const absolute = path.join(entry.parentPath || entry.path || directory, entry.name);
      const relative = path.relative(root, absolute).replace(/\\/g, "/");
      return { kind, profile, file: relative, bytes: fs.statSync(absolute).size, sha256: sha256(absolute) };
    }).sort((left, right) => left.file.localeCompare(right.file));
}

/* ------------------------------------------------------------------------- */
/* the difference signal                                                      */
/* ------------------------------------------------------------------------- */

async function readSmallFrames(rawFile, width, height, { sourceStudy = null, label = 'raw-frame-read', batchFrames = 64 } = {}) {
  const buf = await fs.promises.readFile(rawFile);
  const size = width * height;
  const count = Math.floor(buf.length / size);
  const frames = [];
  for (let start = 0; start < count; start += batchFrames) {
    const end = Math.min(count, start + batchFrames);
    for (let i = start; i < end; i += 1) frames.push(buf.subarray(i * size, (i + 1) * size));
    if (sourceStudy) sourceStudy.progress('postprocess-chunk', { label, phase: 'raw-frame-read', frames_read: end, bytes_read: end * size });
    await new Promise((resolve) => setImmediate(resolve));
  }
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
    } else if (["click", "navigate", "focus", "keyboard", "input", "programmatic", "none", "consent-disposition"].includes(a.action)) {
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
    else if (["click", "navigate", "focus", "keyboard", "input", "programmatic", "none", "consent-disposition"].includes(a.action)) cover(a.t_start - 0.2, a.t_end + 0.5);
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
  if (![1, 2].includes(payload?.schema_version) || payload.reference_id !== id || !Array.isArray(payload.states) ||
      Object.keys(payload).some((key) => !["schema_version", "reference_id", "states"].includes(key))) throw new Error("State contract must be exact schema 1 (legacy) or schema 2 (ambient-capable) for this reference id.");
  const ids = new Set();
  for (const state of payload.states) {
    const core = state && { id: state.id, kind: state.kind, trigger: state.trigger, expectation: state.expectation };
    const ambient = state?.trigger?.type === "ambient";
    const expectedTriggerKeys = ambient ? ["type", "target", "value", "wait_ms"] : ["type", "target", "value"];
    if (!state?.url || Object.keys(state).some((key) => !["id", "url", "kind", "trigger", "expectation"].includes(key)) ||
        Object.keys(state.trigger || {}).sort().join("|") !== expectedTriggerKeys.sort().join("|") ||
        (ambient && payload.schema_version !== 2) || validateManifestState(core, { sourceOnly: true }) || ids.has(state.id)) throw new Error("Every source state needs a unique id, exact URL, kind, trigger and expectation.");
    state.url = normalizeHttpUrl(state.url);
    if (new URL(state.url).origin !== new URL(primaryUrl).origin) throw new Error(`${state.id}: source state must remain same-origin.`);
    ids.add(state.id);
  }
  if (!payload.states.some((state) => state.id === "rest" && state.url === normalizeHttpUrl(primaryUrl))) throw new Error("State contract must include rest for the primary exact URL.");
  return { payload, file: path.resolve(file), sha256: sha256(path.resolve(file)) };
}

export const CONSENT_SAFE_DISPOSITIONS = [
  'reject', 'reject all', 'decline', 'decline all',
  'only necessary', 'necessary only', 'essential only',
];

export function isConstrainedConsentSignal(value) {
  return /\bcookie(?:s)?\b|\bconsent\b|onetrust|privacy\s+(?:choices|settings|preferences)|tracking\s+(?:choices|settings|preferences)/i.test(String(value || ''));
}

async function classifyScopedConsent(page) {
  return page.evaluate((safeLabels) => {
    const visible = (element) => {
      const style = getComputedStyle(element), box = element.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && box.width > 1 && box.height > 1;
    };
    const text = (element) => (element.getAttribute('aria-label') || element.textContent || '').trim().replace(/\s+/g, ' ');
    const containers = [...new Set(document.querySelectorAll('[role="dialog"],[aria-modal="true"],#onetrust-banner-sdk,[class*="cookie" i],[id*="cookie" i],[class*="consent" i],[id*="consent" i]'))]
      .filter(visible);
    const outer = containers.filter((element) => !containers.some((other) => other !== element && other.contains(element)));
    const describe = (element) => ({ tag: element.tagName.toLowerCase(), id: element.id || null,
      role: element.getAttribute('role') || null, aria_label: element.getAttribute('aria-label') || null,
      class_name: String(element.className || '').slice(0, 240), text: text(element).slice(0, 400) });
    const candidates = outer.map((element) => {
      const signal = `${element.id} ${element.className} ${element.getAttribute('aria-label') || ''} ${text(element)}`;
      const strong = /\bcookie(?:s)?\b|\bconsent\b|onetrust|privacy\s+(?:choices|settings|preferences)|tracking\s+(?:choices|settings|preferences)/i.test(signal);
      const broad = /\bprivacy\b|\btracking\b/i.test(signal);
      return { element, strong, broad, description: describe(element) };
    }).filter((item) => item.strong || item.broad);
    if (!candidates.length) return { present: false };
    const eligible = candidates.filter((item) => item.strong);
    if (candidates.length !== 1 || eligible.length !== 1) {
      return { present: true, eligible: false, reason: 'multiple-or-broad-consent-like-dialogs', candidates: candidates.map((item) => item.description) };
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
      action_selector: `[data-design-dna-consent-action="${token}"]` };
  }, CONSENT_SAFE_DISPOSITIONS).catch((error) => ({ present: true, eligible: false, reason: 'consent-inspection-failed', error: String(error?.message || error).slice(0, 240) }));
}

/** The running recording is the generated evidence source. `captureEvidence`
 * returns video timestamps which processProfile binds to immutable frames. */
export async function requireSafeConsent(page, options = {}) {
  const result = await classifyScopedConsent(page);
  if (!result.present) return { present: false, dismissed: false };
  if (!result.eligible) {
    const error = new Error(`Consent-like dialog requires owner-safe handoff before recording; no automatic choice was made (${result.reason || 'ambiguous-consent'}).`);
    error.code = 'consent-handoff-required'; error.consent_candidate = result;
    throw error;
  }
  const capture = options.captureEvidence;
  if (typeof capture !== 'function') throw new Error('A scoped consent disposition requires generated before/action/after recording evidence.');
  const tStart = options.now ? options.now() : 0;
  const before = await capture('consent-disposition-before', page);
  const action = page.locator(result.action_selector);
  if (await action.count() !== 1 || !(await action.first().isVisible())) {
    throw new Error(`Scoped consent action ${JSON.stringify(result.action_selector)} no longer resolves to one visible exact control; no automatic choice was made.`);
  }
  const started = Date.now();
  await action.first().click({ timeout: 5000 });
  const actionEvidence = await capture('consent-disposition-action', page);
  await page.waitForTimeout(600);
  const after = await capture('consent-disposition-after', page);
  const remaining = page.locator(result.root_selector);
  const remainingVisible = await remaining.count() === 1 && await remaining.first().isVisible();
  if (remainingVisible) throw new Error(`Scoped consent disposition ${JSON.stringify(result.label)} did not remove its exact visible consent surface; no further dismissal will be attempted.`);
  const record = { action: 'consent-disposition', disposition: result.disposition, label: result.label,
    root: result.root, action_selector: result.action_selector, duration_ms: Date.now() - started,
    evidence: { before, action: actionEvidence, after } };
  if (Array.isArray(options.log)) options.log.push({ ...record, profile: options.profile || null,
    page_url: page.url(), t_start: tStart, t_end: options.now ? options.now() : tStart });
  return { present: true, dismissed: true, ...record };
}

async function markPointerTargets(frame) {
  await raceBound(frame.evaluate(() => {
    let sequence = Number(window.__dnaRecordPointer || 0);
    const roots = [document];
    for (let index = 0; index < roots.length; index += 1) roots[index].querySelectorAll('*').forEach((element) => { if (element.shadowRoot) roots.push(element.shadowRoot); });
    for (const root of roots) for (const element of root.querySelectorAll('*')) {
      if (getComputedStyle(element).cursor !== 'pointer') continue;
      if (!element.dataset.dnaRecordPointer) element.dataset.dnaRecordPointer = String(++sequence);
    }
    window.__dnaRecordPointer = sequence;
  }), 5_000, 'pointer-target-marking');
}

// A visible-only hover pass runs at every scroll position. On a page whose
// carousels replace their anchors every second, a stale locator costs its
// whole bound; the pass is capped per position and the cap is journaled.
const VISIBLE_HOVER_PASS_MS = 20_000;

async function hoverAllTargets(page, log, clock, coverage, profile, visibleOnly = false, sourceStudy = null) {
  const selector = 'a[href],button,[role="button"],input,select,textarea,summary,[onclick],[tabindex],[data-dna-record-pointer]';
  const passStarted = Date.now();
  let truncated = false;
  for (const frame of page.frames()) {
    if (truncated) break;
    await markPointerTargets(frame);
    const targets = await raceBound(frame.locator(selector).all(), 5_000, 'hover-target-listing');
    for (const target of targets) {
      if (visibleOnly && Date.now() - passStarted > VISIBLE_HOVER_PASS_MS) { truncated = true; break; }
      let identity = null;
      try {
        if (!(await raceBound(target.isVisible(), 3_000, 'hover-target-visibility'))) continue;
        identity = await target.evaluate((element) => {
          window.__dnaRecordTarget = Number(window.__dnaRecordTarget || 0);
          if (!element.dataset.dnaRecordTarget) element.dataset.dnaRecordTarget = String(++window.__dnaRecordTarget);
          return { id: element.dataset.dnaRecordTarget, tag: element.tagName.toLowerCase(),
            text: (element.getAttribute('aria-label') || element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 200) };
        }, undefined, { timeout: 1500 });
        const key = `${normalizeHttpUrl(page.url())}|${frame.url()}|${identity.id}`;
        coverage.discovered.add(key);
        if (coverage.hovered.has(key)) continue;
        sourceStudy?.markTarget(`${profile}|hover|${key}`, { profile, visible_only: visibleOnly });
        if (clock.over()) return false;
        // A locator whose element the page has since replaced waits 30s by
        // default; the target list is a snapshot, so every wait is bounded.
        let box = await target.boundingBox({ timeout: 3000 });
        if (visibleOnly && (!box || box.x + box.width <= 0 || box.y + box.height <= 0 ||
            box.x >= (page.viewportSize()?.width || 0) || box.y >= (page.viewportSize()?.height || 0))) continue;
        if (!visibleOnly) { await scrollIntoViewBounded(target, 5000); box = await target.boundingBox({ timeout: 3000 }); }
        if (!box || box.width < 1 || box.height < 1) continue;
        const entry = { action: "hover", profile, page_url: page.url(), t_start: clock.now(),
          x: Math.round(box.x + box.width / 2), y: Math.round(box.y + box.height / 2),
          target: `${identity.tag} ${identity.text}`.trim() };
        // An unactionable target is a recorded outcome for that target, never
        // a study failure: the step returns the outcome instead of throwing.
        const hoverOnce = async () => {
          try { return await hoverWithPointerFallback(target, page, 4000); }
          catch (error) {
            if (String(error?.code || '').startsWith('source-study-')) throw error;
            return { mode: null, reason: String(error?.message || error).split('\n')[0].slice(0, 180) };
          }
        };
        const hoverOutcome = sourceStudy
          ? await sourceStudy.step(`hover:${profile}`, hoverOnce, {
            // The locator hover may spend its whole 4s bound retrying an
            // unstable target before the pointer fallback runs; the step must
            // enclose both, or a slow hover tears the whole recording down.
            timeout_ms: 20_000, detail: { target_key: key }, abort: async () => { await page.context().close().catch(() => {}); },
          })
          : await hoverOnce();
        if (!hoverOutcome.mode) {
          coverage.hover_failures.set(key, hoverOutcome.reason);
          sourceStudy?.markEvent({ profile, kind: 'hover-unactionable', target_key: key, reason: hoverOutcome.reason });
          continue;
        }
        entry.hover_mode = hoverOutcome.mode;
        await sleep(HOVER_DWELL_MS);
        entry.t_end = clock.now();
        await page.mouse.move(2, 2); await sleep(HOVER_SETTLE_MS); entry.t_left = clock.now();
        log.push(entry); coverage.hovered.add(key); coverage.hover_failures.delete(key);
        sourceStudy?.markEvent({ profile, kind: 'hover', target_key: key });
      } catch (error) {
        if (String(error?.code || '').startsWith('source-study-')) throw error;
        const reason = String(error?.message || error).split('\n')[0].slice(0, 180);
        if (identity) coverage.hover_failures.set(`${normalizeHttpUrl(page.url())}|${frame.url()}|${identity.id}`, reason);
        // A target the page replaced under us is a recorded decision, and a
        // recorded decision is progress; a page of them must not read as
        // silence to the watchdog.
        sourceStudy?.markEvent({ profile, kind: 'hover-unactionable', target_key: identity ? `${normalizeHttpUrl(page.url())}|${frame.url()}|${identity.id}` : null, reason });
      }
    }
  }
  // The end of a pass is measured work even when every remaining target was
  // skipped without a journal line of its own.
  sourceStudy?.markEvent({ profile, kind: 'hover-pass-complete', visible_only: visibleOnly, hovered: coverage.hovered.size,
    failures: coverage.hover_failures.size, truncated, elapsed_ms: Date.now() - passStarted });
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

export function mergeRecorderInteractionCensuses(profile, censuses) {
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
  const repeatClasses = [...new Set(targets.map((target) => target.repeat_class))].sort().map((repeatClass) => {
    const members = targets.filter((target) => target.repeat_class === repeatClass);
    const inputKinds = [...new Set(members.flatMap((target) => target.inputs.map((input) => input.input_kind)))].sort();
    const behaviorSignatures = [...new Set(members.flatMap((target) => target.inputs.filter((input) => input.status === 'exercised')
      .map((input) => `${input.input_kind}:${input.behavior}`)))].sort();
    return { repeat_class: repeatClass, target_ids: members.map((target) => target.target_id), input_kinds: inputKinds,
      equivalent: members.length < 2 || inputKinds.every((kind) => new Set(members.flatMap((target) => target.inputs
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
  const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
  await installDomInspection(context);
  const page = await context.newPage();
  const sourceVideo = path.join(videoDir, 'source-recording.webm');
  const interactionEvidenceDirName = `${args.id}-${viewport.name}-interaction-evidence`;
  const interactionEvidenceDir = path.join(args.out, interactionEvidenceDirName);
  fs.rmSync(interactionEvidenceDir, { recursive: true, force: true }); fs.mkdirSync(interactionEvidenceDir, { recursive: true });
  let interactionEvidenceSequence = 0;
  const log = [], navigations = [], videoElements = [], scrollTraversals = [], interactionCensuses = [], renderedQARecords = [], activeSurfaceWatches = [];
  let sourceEntryCapture = null;
  const seededUrls = [...new Set([normalizeHttpUrl(args.url), ...stateContract.states.map((state) => normalizeHttpUrl(state.url))])];
  const coverage = { discovered: new Set(), hovered: new Set(), hover_failures: new Map(),
    internalDiscovered: new Set(seededUrls), internalVisited: new Set(),
    statesRequired: new Set(stateContract.states.map((state) => state.id)), statesVisited: new Set(), stateInventories: [] };
  let started = Date.now();
  const videoClock = { method: 'playwright-screencast-frame-wall-clock', first_frame_epoch_ms: null,
    last_frame_epoch_ms: null, frames_delivered: 0 };
  const sourceStudy = createSourceStudyController({
    output_dir: args.out, id: `${args.id}-study`, profile: viewport.name, producer: 'record_reference.mjs', source_kind: 'public-source',
    started_epoch_ms: args.sourceStudyStartedAt,
    // Every screencast frame is journaled (measured about 66 per second on a
    // busy page), so the default 100k event budget is a few minutes, not a
    // recording. The ceiling is the hard limit.
    limits: { max_progress_events: 200_000 },
    required_completion_artifact_kinds: ['frame', 'video'],
    abort: async () => { await context.close().catch(() => {}); },
    partial_evidence: () => ({
      interaction_evidence: fs.existsSync(interactionEvidenceDir)
        ? fs.readdirSync(interactionEvidenceDir).sort().map((file) => `${interactionEvidenceDirName}/${file}`) : [],
      log: log.slice(), navigations: navigations.slice(), interaction_censuses: interactionCensuses.slice(),
    }),
  });
  if (!page.screencast?.start || !page.screencast?.stop) {
    throw sourceStudy.terminate('source-study-recording-clock-unavailable',
      'This Playwright runtime lacks the timestamped screencast API required for exact source video/event binding; use the packaged dependency.');
  }
  let firstFrameResolve;
  const firstFrame = new Promise((resolve) => { firstFrameResolve = resolve; });
  await sourceStudy.step('timestamped-recording-start', async () => {
    await page.screencast.start({ path: sourceVideo, size: { width: viewport.width, height: viewport.height },
      onFrame: (frame) => {
        if (!Number.isFinite(frame.timestamp) || sourceStudy.terminated || sourceStudy.closed) return;
        if (videoClock.first_frame_epoch_ms === null) {
          started = frame.timestamp;
          videoClock.first_frame_epoch_ms = frame.timestamp;
          firstFrameResolve();
        }
        videoClock.last_frame_epoch_ms = frame.timestamp;
        videoClock.frames_delivered += 1;
        try { sourceStudy.markEvent({ kind: 'recorded-source-frame', profile: viewport.name,
          video_t_s: (frame.timestamp - videoClock.first_frame_epoch_ms) / 1000, frame_epoch_ms: frame.timestamp }); } catch {}
      } });
    await firstFrame;
  });
  // `--seconds` is a minimum recording floor, never a coverage budget. Work
  // continues past it until every route/state/surface/target is complete.
  const clock = { now: () => +((Date.now() - started) / 1000).toFixed(2), over: () => false };
  const queue = [...seededUrls], origin = new URL(args.url).origin;
  const captureInteractionEvidence = async (label, targetPage = page, stateId = null) => {
    interactionEvidenceSequence += 1;
    const safe = String(label).toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/^-+|-+$/g, '');
    const fileName = `${String(interactionEvidenceSequence).padStart(5, '0')}-${safe}.png`;
    const buffer = await sourceStudy.step(`screenshot:${safe}`,
      () => targetPage.screenshot({ path: path.join(interactionEvidenceDir, fileName) }), {
        screenshot: true, detail: { profile: viewport.name, state_id: stateId, label },
        abort: async () => { await targetPage.context().close().catch(() => {}); },
      });
    const evidence = { profile: viewport.name, state_id: stateId, label, video_t_s: clock.now(),
      file: `${interactionEvidenceDirName}/${fileName}`, bytes: buffer.length, sha256: createHash('sha256').update(buffer).digest('hex') };
    sourceStudy.markFrame({ profile: viewport.name, file: evidence.file, sha256: evidence.sha256, label });
    return evidence;
  };
  const captureConsentEvidence = (label, targetPage = page) => ({
    profile: viewport.name, label, video_t_s: clock.now(), page_url: targetPage.url(),
    evidence_kind: 'recorded-video-frame',
  });
  const sourceAmbientSelectors = stateContract.states.filter((state) => state.trigger?.type === 'ambient').map((state) => state.trigger.target);
  const startSurfaceWatch = async (label, baseline = null, earlyWatch = null, authorizedConsent = []) => {
    const options = {
      ambientSelectors: sourceAmbientSelectors,
      baseline: baseline || captureConsentEvidence(`${label}-baseline`, page),
      authorizedConsent, labelPrefix: `${label}-autonomous-surface`, captureEvidence: captureConsentEvidence,
    };
    const watch = earlyWatch
      ? await adoptEarlySourceSurfaceWatch(page, earlyWatch, options)
      : await startSourceSurfaceWatch(page, options);
    activeSurfaceWatches.push({ watch, label });
    return watch;
  };
  const finishSurfaceWatch = async (watch, label, context = {}) => {
    let report;
    try {
      report = await drainSourceSurfaceWatch(watch, {
        labelPrefix: `${label}-autonomous-surface`, captureEvidence: captureConsentEvidence,
      });
    } finally {
      await stopSourceSurfaceWatch(watch);
      const index = activeSurfaceWatches.findIndex((item) => item.watch === watch);
      if (index >= 0) activeSurfaceWatches.splice(index, 1);
    }
    // Keep even empty watches: their final frame/video binding is the proof
    // that a quiet source interval was continuously watched, not an omitted
    // interval that later gets described as quiet.
    log.push({ action: 'autonomous-surface-watch', profile: viewport.name,
      target: label, page_url: page.url(), t_start: clock.now(), t_end: clock.now(), report });
    for (const event of report.events) sourceStudy.markEvent({ profile: viewport.name, kind: event.kind,
      source_surface: true, selector: event.selector, declared_ambient: event.declared_ambient });
    const undocumented = undocumentedSourceSurfaceError(report, { profile: viewport.name, ...context });
    if (undocumented) throw undocumented;
    return report;
  };
  const captureCensusUntilStable = async (pageUrl, states, stateId = null, baselineApplication = null, baselineEvidence = null) => {
    const knownTargets = new Set();
    const localCensuses = [];
    let pass = 0;
    while (true) {
      pass += 1;
      const baselineState = states.find((state) => state.id === stateId)
        || states.find((state) => state.id === 'rest')
        || null;
      const censusOptions = { profile: viewport.name, pageUrl,
        authoredStates: states, baselineState,
        baselineApplication, baselineEvidence,
        sourceOnly: true,
        context: { phase: 'recording', source_state_id: stateId || baselineState?.id || null, pass },
        captureEvidence: (label, targetPage = page) => captureInteractionEvidence(label, targetPage, stateId) };
      const census = await sourceStudy.step(`interaction-census:${viewport.name}:recording`, () => captureInteractionCensus(page, censusOptions), {
        timeout_ms: RECORDER_CENSUS_TIMEOUT_MS, detail: { page_url: pageUrl, state_id: stateId || baselineState?.id || null, pass },
        abort: async () => { await context.close().catch(() => {}); },
      });
      interactionCensuses.push(census);
      localCensuses.push(census);
      const ids = census.pages.flatMap((pageRecord) => pageRecord.targets.map((target) => target.target_id));
      const newIds = ids.filter((id) => !knownTargets.has(id)); ids.forEach((id) => knownTargets.add(id));
      for (const targetId of newIds) sourceStudy.markTarget(`${viewport.name}|recording|${pageUrl}|${stateId || baselineState?.id || 'rest'}|${targetId}`, { pass });
      sourceStudy.markEvent({ profile: viewport.name, kind: 'interaction-census', targets: ids.length, pass });
      if (!newIds.length) break;
    }
    return mergeRecorderInteractionCensuses(viewport.name, localCensuses);
  };
  let runError = null;
  try {
    while (queue.length) {
      const targetUrl = queue.shift();
      if (coverage.internalVisited.has(targetUrl)) continue;
      sourceStudy.markRoute(targetUrl, { profile: viewport.name, phase: 'recursive-route' });
      const routeEarlyWatch = await armEarlySourceSurfaceWatch(page, {
        ambientSelectors: sourceAmbientSelectors,
        baseline: captureConsentEvidence(`route-${coverage.internalVisited.size + 1}-early-before-navigation`, page),
        labelPrefix: `route-${coverage.internalVisited.size + 1}-early-autonomous-surface`, captureEvidence: captureConsentEvidence,
      });
      const navLog = { action: "navigate", profile: viewport.name, target: targetUrl, t_start: clock.now() };
      const navigation = await sourceStudy.step(`navigate:${viewport.name}:recursive-route`, () => navigateExact(page, targetUrl), {
        detail: { url: targetUrl }, abort: async () => { await context.close().catch(() => {}); },
      });
      navLog.t_end = clock.now(); log.push(navLog); navigations.push(navigation);
      await page.evaluate(() => document.fonts?.ready).catch(() => {});
      const routeConsent = await requireSafeConsent(page, { captureEvidence: captureConsentEvidence, log, profile: viewport.name, now: clock.now });
      const routeSurfaceWatch = await startSurfaceWatch(`route-${coverage.internalVisited.size + 1}`, null, routeEarlyWatch,
        routeConsent.dismissed ? [routeConsent] : []);
      if (coverage.internalVisited.size === 0) await sleep(INTRO_WAIT_MS);
      else await sleep(500);
      if (!sourceEntryCapture) {
        sourceEntryCapture = { ...await captureInteractionEvidence('primary-source-entry', page),
          source_url: normalizeHttpUrl(page.url()), navigation };
      }
      videoElements.push(...await collectVideos(page, viewport.name));
      await hoverAllTargets(page, log, clock, coverage, viewport.name, false, sourceStudy);
      const traversal = await sourceStudy.step(`scroll-traversal:${viewport.name}`, () => traverseScrollSurfaces(page, { maxTicks: 240, settleMs: SCROLL_PAUSE_MS,
        deadline: clock.over,
        onTick: async (surface, tick, sample) => {
          sourceStudy.markTarget(`${viewport.name}|scroll|${targetUrl}|${surface.id}|${tick}`, { phase: 'recording-scroll', tick });
          const event = { action: "scroll", profile: viewport.name, page_url: page.url(), surface: surface.id,
            target: surface.selector_hint || surface.kind, tick, t_start: clock.now(), y: sample.y };
          await hoverAllTargets(page, log, clock, coverage, viewport.name, true, sourceStudy);
          event.t_end = clock.now(); log.push(event);
          sourceStudy.markEvent({ profile: viewport.name, kind: 'scroll', surface: surface.id, tick });
        } }), { timeout_ms: RECORDER_SCROLL_TRAVERSAL_TIMEOUT_MS, detail: { url: targetUrl }, abort: async () => { await context.close().catch(() => {}); } });
      scrollTraversals.push({ url: targetUrl, ...traversal });
      const applicableStates = stateContract.states.filter((state) => normalizeHttpUrl(state.url) === targetUrl);
      const stateInventory = await inferAndReconcileStates(page, applicableStates);
      coverage.stateInventories.push({ url: targetUrl, ...stateInventory });
      const pageInteractionCensus = await captureCensusUntilStable(targetUrl, applicableStates);
      renderedQARecords.push(await captureRenderedQA(page, { profile: viewport.name, pageUrl: targetUrl,
        sourceState: applicableStates.find((state) => state.trigger?.type === 'none') || null,
        interactionCensus: pageInteractionCensus,
        captureEvidence: (label, targetPage = page) => captureInteractionEvidence(label, targetPage) }));
      await finishSurfaceWatch(routeSurfaceWatch, `route-${coverage.internalVisited.size + 1}`, { phase: 'recursive-route' });
      const links = await collectSameOriginLinks(page, origin);
      links.forEach((link) => { if (!coverage.internalDiscovered.has(link)) { coverage.internalDiscovered.add(link); queue.push(link); } });
      if (coverage.internalDiscovered.size > 1000) throw new Error("More than 1000 recursive same-origin pages were discovered; complete traversal cannot be established.");
      coverage.internalVisited.add(targetUrl);
    }
    for (const state of stateContract.states) {
      sourceStudy.markState(`${viewport.name}:${state.id}:started`, { profile: viewport.name, phase: 'recording-state-start' });
      const stateEarlyWatch = await armEarlySourceSurfaceWatch(page, {
        ambientSelectors: sourceAmbientSelectors,
        baseline: captureConsentEvidence(`state-${state.id}-early-before-navigation`, page),
        labelPrefix: `state-${state.id}-early-autonomous-surface`, captureEvidence: captureConsentEvidence,
      });
      const navigation = await sourceStudy.step(`navigate:${viewport.name}:recording-state`, () => navigateExact(page, state.url), {
        detail: { state_id: state.id, url: state.url }, abort: async () => { await context.close().catch(() => {}); },
      }); navigations.push(navigation);
      const stateConsent = await requireSafeConsent(page, { captureEvidence: captureConsentEvidence, log, profile: viewport.name, now: clock.now });
      const stateSurfaceWatch = await startSurfaceWatch(`state-${state.id}`, null, stateEarlyWatch,
        stateConsent.dismissed ? [stateConsent] : []);
      const tStart = clock.now();
      const ambientBefore = state.trigger.type === "ambient"
        ? await captureInteractionEvidence(`${state.id}-ambient-before`, page, state.id)
        : null;
      let ambientAppearance = null;
      const application = await applyManifestState(page, state, {
        sourceOnly: true,
        onAmbientAppearance: state.trigger.type === "ambient" ? async (appearancePage) => {
          ambientAppearance = await captureInteractionEvidence(`${state.id}-ambient-appearance`, appearancePage, state.id);
        } : undefined,
      });
      const ambientAfter = state.trigger.type === "ambient" ? ambientAppearance : null;
      if (state.trigger.type === "ambient" && !ambientAfter) {
        throw new Error(`${viewport.name}/${state.id}: ambient source appearance did not produce generated evidence.`);
      }
      if (state.trigger.type === "ambient") await page.waitForTimeout(220);
      const ambientSettled = state.trigger.type === "ambient"
        ? await captureInteractionEvidence(`${state.id}-ambient-settled`, page, state.id)
        : null;
      if (application.navigation) navigations.push(application.navigation);
      const tEnd = clock.now();
      log.push({ action: state.trigger.type === "url" ? "navigate" : state.trigger.type,
        profile: viewport.name, state_id: state.id, target: state.trigger.target, t_start: tStart, t_end: tEnd,
        t_left: tEnd, trigger_evidence: application.trigger_evidence });
      coverage.statesVisited.add(state.id);
      const stateInteractionCensus = await captureCensusUntilStable(state.url,
        stateContract.states.filter((item) => normalizeHttpUrl(item.url) === normalizeHttpUrl(state.url)), state.id,
        application,
        state.trigger.type === "ambient"
          ? { before: ambientBefore, after: ambientAfter, settled: ambientSettled }
          : null);
      renderedQARecords.push(await captureRenderedQA(page, { profile: viewport.name, pageUrl: state.url,
        sourceState: state, interactionCensus: stateInteractionCensus,
        captureEvidence: (label, targetPage = page) => captureInteractionEvidence(label, targetPage, state.id) }));
      await finishSurfaceWatch(stateSurfaceWatch, `state-${state.id}`, { state_id: state.id, phase: 'source-state' });
      sourceStudy.markState(`${viewport.name}:${state.id}:complete`, { profile: viewport.name, phase: 'recording-state-complete' });
    }
    const finalSurfaceWatch = await startSurfaceWatch('post-dwell');
    while (Date.now() - started < args.seconds * 1000) {
      sourceStudy.assertHealthy();
      const dwellSliceMs = Math.min(1000, Math.max(1, Math.ceil(args.seconds * 1000 - (Date.now() - started))));
      await sourceStudy.step('post-dwell-wait', () => sleep(dwellSliceMs), {
        timeout_ms: Math.min(5000, dwellSliceMs + 1000), detail: { dwell_slice_ms: dwellSliceMs },
        abort: async () => { await context.close().catch(() => {}); },
      });
    }
    await finishSurfaceWatch(finalSurfaceWatch, 'post-dwell', { phase: 'post-dwell' });
  } catch (error) {
    const reports = [];
    while (activeSurfaceWatches.length) {
      const { watch, label } = activeSurfaceWatches[0];
      try { reports.push(await finishSurfaceWatch(watch, label, { phase: 'failure-cleanup' })); }
      catch (watchError) { reports.push(watchError.surface_watch || null); if (!error.surface_watch) error = watchError; }
    }
    if (reports.length && !error.surface_watch) error.surface_watch = reports.find(Boolean) || null;
    if (!error?.source_study && !sourceStudy.closed) {
      const terminal = sourceStudy.terminate(error?.code || 'source-study-recording-failed',
        'Recorder terminated before a complete source recording could be emitted; partial evidence is ineligible.',
        { source_code: error?.code || null, source_error: String(error?.message || error) });
      error.source_study = terminal.source_study;
      error.source_study_progress = terminal.source_study_progress;
      error.source_study_failure = terminal.source_study_failure;
    }
    runError = error;
  }
  const duration = +((Date.now() - started) / 1000).toFixed(2);
  // The selected interval ends here. Keep the real browser recording for one
  // additional quarter-second so the encoder's 25fps terminal quantization
  // cannot cut off the last selected sample during lower-rate extraction.
  // This extra unselected footage never advances route/state coverage.
  if (!runError) await sourceStudy.step('recording-terminal-sample-hold', () => page.waitForTimeout(250), { timeout_ms: 5000 });
  // The pinned local Playwright artifact exposes its encoder backing file.
  // Observe growing encoded bytes while stop() flushes static-frame holds;
  // elapsed time alone is never reported as encoder progress.
  const backingVideo = page.screencast._artifact?._initializer?.absolutePath;
  let stopTimer, stopProgress, stopBytes = 0, stopFailure = null;
  try {
    if (!runError) sourceStudy.progress('postprocess-start', { label: 'video-finalization', timeout_ms: POSTPROCESS_SUBPROCESS_TIMEOUT_MS });
    stopProgress = setInterval(() => {
      if (sourceStudy.terminated || sourceStudy.closed) return;
      try {
        const bytes = typeof backingVideo === 'string' && path.isAbsolute(backingVideo) && fs.existsSync(backingVideo) ? fs.statSync(backingVideo).size : 0;
        if (bytes > stopBytes) {
          stopBytes = bytes;
          sourceStudy.progress('postprocess-chunk', { label: 'video-finalization', encoded_bytes: bytes });
        } else sourceStudy.assertHealthy();
      } catch (error) { stopFailure = error; void context.close().catch(() => {}); }
    }, 500);
    await Promise.race([page.screencast.stop(), new Promise((_, reject) => {
      stopTimer = setTimeout(() => reject(new Error(`Timestamped source recording finalization exceeded ${POSTPROCESS_SUBPROCESS_TIMEOUT_MS}ms.`)), POSTPROCESS_SUBPROCESS_TIMEOUT_MS);
    })]);
    if (stopFailure) throw stopFailure;
    if (!runError) sourceStudy.progress('postprocess-complete', { label: 'video-finalization', encoded_bytes: stopBytes });
  } catch (error) {
    if (!runError) runError = sourceStudy.terminate('source-study-video-finalization-failed', String(error?.message || error));
  } finally { clearTimeout(stopTimer); clearInterval(stopProgress); }
  await context.close();
  if (runError) {
    const prefix = `${args.id}-${viewport.name}`;
    let retainedVideo = null;
    if (sourceVideo && fs.existsSync(sourceVideo)) {
      const videoFile = `${prefix}-incomplete-recording.webm`;
      fs.copyFileSync(sourceVideo, path.join(args.out, videoFile));
      retainedVideo = artifactEntry(args.out, videoFile, "incomplete-video", viewport.name);
    }
    const partialCensus = mergeRecorderInteractionCensuses(viewport.name, interactionCensuses);
    const failureFile = path.join(args.out, `${prefix}-recording-failure.json`);
    const failure = {
      schema_version: 1,
      kind: "reference-recording-failure",
      status: "incomplete-not-selection-evidence",
      source_status: runError?.source_study?.source_status || sourceStudyFailureStatus(runError?.code, { source_error: String(runError?.message || runError) }, interactionEvidenceSequence),
      eligible_for_source_selection: false,
      id: args.id,
      profile: viewport.name,
      viewport,
      duration_s: duration,
      error: { code: runError?.code || "recording-failed", message: String(runError?.message || runError) },
      interaction_census: interactionCensusDiagnostic(partialCensus,
        { phase: "recording-runtime", source_state_id: null, pass: null }),
      autonomous_surface_watch: runError?.surface_watch || null,
      source_study: runError?.source_study || null,
      source_study_progress: runError?.source_study_progress || null,
      source_study_failure: runError?.source_study_failure || null,
      consent_handoff: runError?.consent_candidate || runError?.consent_disposition || null,
      retained_artifacts: [
        ...(retainedVideo ? [retainedVideo] : []),
        ...retainedArtifacts(args.out, interactionEvidenceDir, "interaction-evidence", viewport.name),
      ],
    };
    writeJsonAtomically(failureFile, failure);
    fs.rmSync(videoDir, { recursive: true, force: true });
    const error = new Error(String(runError?.message || runError));
    error.code = runError?.code || "recording-failed";
    error.failure_report = { file: failureFile, sha256: sha256(failureFile) };
    error.source_study = runError.source_study;
    error.source_study_progress = runError.source_study_progress;
    error.source_study_failure = runError.source_study_failure;
    throw error;
  }
  const missingHovers = [...coverage.discovered].filter((key) => !coverage.hovered.has(key));
  const missingPages = [...coverage.internalDiscovered].filter((url) => !coverage.internalVisited.has(url));
  const missingStates = [...coverage.statesRequired].filter((id) => !coverage.statesVisited.has(id));
  const incompleteScrolls = scrollTraversals.filter((item) => !item.complete);
  const unreconciledStates = coverage.stateInventories.flatMap((item) => item.unreconciled.map((state) => ({ url: item.url, ...state })));
  const interactionCensus = mergeRecorderInteractionCensuses(viewport.name, interactionCensuses);
  const renderedQA = mergeSourceRenderedQA(viewport.name, renderedQARecords);
  return { profile: viewport.name, viewport, duration_s: duration, source_video: sourceVideo, video_dir: videoDir,
    video_clock: videoClock, source_entry_capture: sourceEntryCapture,
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
    interaction_census: interactionCensus, rendered_qa: renderedQA, source_study: sourceStudy };
}

function artifactEntry(root, file, kind, profile = null) {
  const absolute = path.join(root, file);
  return { kind, profile, file: file.replace(/\\/g, "/"), bytes: fs.statSync(absolute).size, sha256: sha256(absolute) };
}

async function processProfile(args, run) {
  if (!run.source_video || !fs.existsSync(run.source_video)) throw new Error(`${run.profile}: Playwright did not produce a recording video.`);
  const prefix = `${args.id}-${run.profile}`;
  const videoFile = `${prefix}-recording.webm`, videoPath = path.join(args.out, videoFile);
  fs.copyFileSync(run.source_video, videoPath); fs.rmSync(run.video_dir, { recursive: true, force: true });
  const framesDirName = `${prefix}-frames`, eventsDirName = `${prefix}-events`;
  const framesDir = path.join(args.out, framesDirName), eventsDir = path.join(args.out, eventsDirName);
  for (const directory of [framesDir, eventsDir]) { fs.rmSync(directory, { recursive: true, force: true }); fs.mkdirSync(directory, { recursive: true }); }
  const videoArtifact = artifactEntry(args.out, videoFile, "video", run.profile);
  run.source_study.retainArtifact({ ...videoArtifact, producer: 'record_reference.mjs' });
  await runBoundedSourceSubprocess({
    command: args.ffmpeg,
    args: ["-y", "-v", "error", "-i", videoPath, "-vf", `fps=${args.fps},scale=${run.viewport.width}:-1`, path.join(framesDir, "f%05d.png")],
    label: `${run.profile}:frame-extraction`, sourceStudy: run.source_study,
    progressProbe: () => fs.existsSync(framesDir) ? fs.readdirSync(framesDir).filter((file) => file.endsWith('.png')).length : 0,
  });
  const smallHeight = Math.round(SMALL_WIDTH * run.viewport.height / run.viewport.width);
  const rawFile = path.join(os.tmpdir(), `design-dna-${args.id}-${run.profile}-${process.pid}.gray`);
  await runBoundedSourceSubprocess({
    command: args.ffmpeg,
    args: ["-y", "-v", "error", "-i", videoPath,
      "-vf", `fps=${args.fps},scale=${SMALL_WIDTH}:${smallHeight},format=gray`, "-f", "rawvideo", "-pix_fmt", "gray", rawFile],
    label: `${run.profile}:grayscale-analysis`, sourceStudy: run.source_study,
    progressProbe: () => fs.existsSync(rawFile) ? fs.statSync(rawFile).size : 0,
  });
  run.source_study.progress('postprocess-chunk', { label: `${run.profile}:read-grayscale-frames`, phase: 'start' });
  const smallFrames = await readSmallFrames(rawFile, SMALL_WIDTH, smallHeight, { sourceStudy: run.source_study, label: `${run.profile}:read-grayscale-frames` }); fs.rmSync(rawFile, { force: true });
  run.source_study.progress('postprocess-chunk', { label: `${run.profile}:read-grayscale-frames`, phase: 'complete', frames: smallFrames.length });
  const signal = [];
  for (let index = 0; index < smallFrames.length; index += 1) {
    signal.push(index === 0 ? 0 : diffFrames(smallFrames[index - 1], smallFrames[index], SMALL_WIDTH, smallHeight).pct);
    if ((index + 1) % 4 === 0 || index + 1 === smallFrames.length) {
      run.source_study.progress('postprocess-chunk', { label: `${run.profile}:difference-signal`, phase: 'difference-analysis', frames_analyzed: index + 1 });
      await new Promise((resolve) => setImmediate(resolve));
    }
  }
  const fullFrames = fs.readdirSync(framesDir).filter((file) => file.endsWith(".png")).sort();
  const exactDurationMs = exactRecordingDurationMs(run.duration_s);
  if (exactDurationMs === null) throw new Error(`${run.profile}: selected recording duration ${run.duration_s}s is not exactly millisecond-representable.`);
  const requiredFrameCount = Math.ceil(run.duration_s * args.fps);
  if (!fullFrames.length || fullFrames.length < requiredFrameCount) {
    throw new Error(`${run.profile}: extracted ${fullFrames.length} frames, below the exact ${requiredFrameCount}-frame requirement for ${run.duration_s}s at ${args.fps}fps.`);
  }
  const frameFiles = fullFrames.map((file) => artifactEntry(args.out, path.join(framesDirName, file), "frame", run.profile));
  const bindVideoEvidence = (value) => {
    if (Array.isArray(value)) return value.map(bindVideoEvidence);
    if (!value || typeof value !== "object") return value;
    const mapped = Object.fromEntries(Object.entries(value).map(([key, item]) => [key, bindVideoEvidence(item)]));
    if (Number.isFinite(value.video_t_s)) {
      const index = frameIndex(value.video_t_s, args.fps, frameFiles.length);
      mapped.frame = frameFiles[index] ? { file: frameFiles[index].file, bytes: frameFiles[index].bytes,
        sha256: frameFiles[index].sha256 } : null;
      mapped.video = { file: videoArtifact.file, bytes: videoArtifact.bytes, sha256: videoArtifact.sha256 };
    }
    return mapped;
  };
  const boundLog = bindVideoEvidence(run.log);
  const bindContinuousSurfaceWatch = (entry) => {
    const bound = bindVideoEvidence(entry);
    const report = bound?.report;
    if (!report || typeof report !== 'object') throw new Error(`${run.profile}: autonomous-source-surface watch entry is malformed.`);
    const reconciliations = report.gap_reconciliations || [];
    for (const reconciliation of reconciliations) {
      const window = reconciliation?.continuous_recording_reconciliation;
      if (!window || typeof window !== 'object') throw new Error(`${run.profile}: timing gap ${reconciliation?.gap_id || '(unnamed)'} has no continuous-recording reconciliation.`);
      const before = window.before, after = window.after;
      if (!before?.frame || !before?.video || !after?.frame || !after?.video) {
        throw new Error(`${run.profile}: timing gap ${reconciliation?.gap_id || '(unnamed)'} lacks immutable recording frame/video binding.`);
      }
      window.status = 'generated-recording-frame-window-bound';
      window.profile = run.profile;
      window.duration_s = run.duration_s;
      window.exact_millisecond_duration = true;
      window.fps = args.fps;
      window.frame_count = frameFiles.length;
    }
    report.recording_binding = { profile: run.profile, duration_s: run.duration_s, exact_millisecond_duration: true,
      fps: args.fps, frame_count: frameFiles.length, frame_requirement: requiredFrameCount,
      continuous_video_frame_coverage: true };
    return bound;
  };
  const autonomousSurfaceWatches = run.log.filter((entry) => entry?.action === 'autonomous-surface-watch')
    .map(bindContinuousSurfaceWatch);
  const { events, quiet } = buildEvents(boundLog, smallFrames, signal, args.fps, SMALL_WIDTH, smallHeight, run.duration_s);
  const eventFiles = [];
  for (const [index, event] of events.entries()) {
    const id = `e${String(index + 1).padStart(4, "0")}`, name = `${id}-${event.kind}${slug(event.target) ? "-" + slug(event.target) : ""}.png`;
    const inputs = event.times.map((time) => path.join(framesDir, fullFrames[frameIndex(time, args.fps, fullFrames.length)]));
    const filters = inputs.map((_, item) => `[${item}]scale=640:-1,pad=648:ih+8:4:4:color=black[p${item}]`);
    await runBoundedSourceSubprocess({
      command: args.ffmpeg,
      args: ["-y", "-v", "error", ...inputs.flatMap((file) => ["-i", file]),
        "-filter_complex", `${filters.join(";")};[p0][p1][p2][p3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0`, path.join(eventsDir, name)],
      label: `${run.profile}:event-tile:${id}`, sourceStudy: run.source_study,
      progressProbe: () => fs.existsSync(path.join(eventsDir, name)) ? fs.statSync(path.join(eventsDir, name)).size : 0,
    });
    const artifact = artifactEntry(args.out, path.join(eventsDirName, name), "event-sheet", run.profile);
    eventFiles.push({ id, file: artifact.file, bytes: artifact.bytes, sha256: artifact.sha256, kind: event.kind,
      target: event.target, t: round1(event.t), frames_s: event.times.map(round1), magnitude_pct: event.magnitude_pct ?? null,
      changed_area_pct: event.changed_area_pct ?? null, region: event.region ?? null, settle_s: event.settle_s ?? null });
  }
  const cursorFile = `${prefix}-cursor-path.json`, diffFile = `${prefix}-difference-signal.json`, eventsFile = `${prefix}-events.md`;
  fs.writeFileSync(path.join(args.out, cursorFile), JSON.stringify({ profile: run.profile, actions: boundLog }, null, 2) + "\n", "utf8");
  fs.writeFileSync(path.join(args.out, diffFile), JSON.stringify({ profile: run.profile, fps: args.fps,
    small: { width: SMALL_WIDTH, height: smallHeight }, pct: signal.map(round2) }, null, 2) + "\n", "utf8");
  const markdown = [`# ${args.id} ${run.profile} events`, "", `${args.url}, ${run.duration_s}s, ${fullFrames.length} frames at ${args.fps}fps.`, "",
    "| Event | t | Kind | Target | Changed | Where | Settled after |", "| --- | --- | --- | --- | --- | --- | --- |",
    ...eventFiles.map((event) => `| ${event.id} | ${event.t}s | ${event.kind} | ${String(event.target).replace(/\|/g, "/")} | ${event.magnitude_pct ?? "-"}% | ${event.region ?? "-"} | ${event.settle_s ?? "-"}s |`), ""].join("\n");
  fs.writeFileSync(path.join(args.out, eventsFile), markdown, "utf8");
  const interactionArtifacts = fs.readdirSync(path.join(args.out, run.interaction_evidence_dir))
    .filter((file) => file.endsWith('.png')).sort()
    .map((file) => artifactEntry(args.out, path.join(run.interaction_evidence_dir, file), 'interaction-frame', run.profile));
  const sourceEntryCapture = bindVideoEvidence(run.source_entry_capture);
  if (!sourceEntryCapture?.frame || sourceEntryCapture.source_url !== normalizeHttpUrl(args.url)) {
    throw new Error(`${run.profile}: no generated navigated source-entry capture can represent this recording.`);
  }
  const completion = {
    terminal_success: true,
    coverage_complete: run.coverage.complete === true,
    signed_artifacts: [
      { kind: 'video', file: videoArtifact.file, bytes: videoArtifact.bytes, sha256: videoArtifact.sha256, producer: 'record_reference.mjs' },
      { kind: 'frame', ...sourceEntryCapture.frame, producer: 'record_reference.mjs' },
    ],
    final_url: run.navigations[0]?.final_url || null,
  };
  let sourceStudySnapshot;
  if (run.coverage.complete === true) sourceStudySnapshot = run.source_study.complete(completion);
  else {
    run.source_study.terminate('source-study-coverage-incomplete',
      'Recording artifacts were retained, but route/state/interaction coverage is incomplete and cannot authorize source selection.',
      { coverage: run.coverage, interaction_census: interactionCensusDiagnostic(run.interaction_census, { phase: 'recording-completion' }) });
    sourceStudySnapshot = run.source_study.snapshot();
  }
  const sourceStudyProgressRelative = path.relative(args.out, run.source_study.progressFile).replace(/\\/g, '/');
  const sourceStudyProgressArtifact = artifactEntry(args.out, sourceStudyProgressRelative, 'source-study-progress', run.profile);
  const sourceStudyJournalRelative = path.relative(args.out, run.source_study.eventFile).replace(/\\/g, '/');
  const sourceStudyJournalArtifact = artifactEntry(args.out, sourceStudyJournalRelative, 'source-study-progress-journal', run.profile);
  const sourceStudy = { ...sourceStudySnapshot,
    progress: { file: sourceStudyProgressArtifact.file, bytes: sourceStudyProgressArtifact.bytes, sha256: sourceStudyProgressArtifact.sha256 },
    progress_events: { file: sourceStudyJournalArtifact.file, bytes: sourceStudyJournalArtifact.bytes, sha256: sourceStudyJournalArtifact.sha256 } };
  const eventIndexArtifact = artifactEntry(args.out, eventsFile, 'events-index', run.profile);
  const artifacts = [videoArtifact, ...frameFiles,
    ...eventFiles.map((event) => ({ kind: "event-sheet", profile: run.profile, file: event.file, bytes: event.bytes, sha256: event.sha256 })),
    ...interactionArtifacts,
    artifactEntry(args.out, cursorFile, "cursor-path", run.profile), artifactEntry(args.out, diffFile, "difference-signal", run.profile),
    eventIndexArtifact, sourceStudyProgressArtifact, sourceStudyJournalArtifact];
  const interactionCensus = bindVideoEvidence(run.interaction_census);
  const renderedQA = bindVideoEvidence(run.rendered_qa);
  return { profile: run.profile, viewport: run.viewport, duration_s: run.duration_s, fps: args.fps,
    video_clock: run.video_clock, source_entry_capture: sourceEntryCapture,
    video: artifacts[0], frames: { count: frameFiles.length, directory: framesDirName, files: frameFiles },
    events: { count: eventFiles.length, directory: eventsDirName, files: eventFiles,
      index: eventIndexArtifact, quiet: quiet.map((item) => ({ kind: item.kind, target: item.target, t: round1(item.t), magnitude_pct: item.magnitude_pct })) },
    cursor_path: artifacts.find((item) => item.kind === "cursor-path"),
    difference_signal: artifacts.find((item) => item.kind === "difference-signal"),
    video_elements: run.video_elements, navigations: run.navigations, scroll_traversals: run.scroll_traversals,
    interaction_census: interactionCensus, rendered_qa: renderedQA,
    autonomous_surface_watches: autonomousSurfaceWatches,
    source_study: sourceStudy,
    coverage: run.coverage, artifacts };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  args.sourceStudyStartedAt = Date.now();
  if (!args.url || !args.id || !args.out || !args.stateContract) throw new Error("--url, --id, --out and --state-contract are required.");
  const leaseOptions = { output_dir: args.out, id: args.id, producer: 'record_reference.mjs' };
  const outputLease = acquireSourceStudyOutputLease(leaseOptions);
  let lease;
  try { lease = acquireSourceStudyRunnerLease(leaseOptions); return await recordMain(args); }
  finally { lease?.release(); outputLease.release(); }
}

async function recordMain(args) {
  const settingsError = recordingSettingsError(args); if (settingsError) throw new Error(settingsError);
  verifySourceEncoder(args.ffmpeg, { output_dir: args.out, id: args.id, producer: 'record_reference.mjs' });
  fs.mkdirSync(args.out, { recursive: true });
  const priorOutput = fs.readdirSync(args.out).find((name) => name.startsWith(`${args.id}-`) &&
    ![path.basename(args.stateContract), `${args.id}-observation.json`, `${args.id}-styles.json`, `${args.id}-frames`].includes(name) &&
    /(?:recording|artifacts|study-(?:wide|narrow)|(?:wide|narrow)-(?:frames|events|interaction-evidence))/.test(name));
  if (priorOutput) throw Object.assign(new Error(`Recorder output already exists (${priorOutput}); use a fresh output directory to retain the earlier evidence.`), { code: 'source-study-existing-output' });
  const stateContract = readStateContract(args.stateContract, args.id, args.url);
  const loaded = loadPlaywright(), playwright = loaded.playwright;
  verifyRecorderPlaywright(loaded.dependency, { output_dir: args.out, id: args.id, producer: TOOL_NAME });
  const browserDependency = loadBrowserDependency(loaded, args.browser);
  const executable = browserDependency.file;
  const browserSha256 = browserDependency.sha256;
  const browser = await launchOwnedBrowser(playwright.chromium, { executablePath: executable });
  let profiles, activeRun = null;
  try {
    profiles = [];
    for (const viewport of VIEWPORTS) {
      activeRun = await runProfile(browser, args, stateContract.payload, viewport);
      profiles.push(await processProfile(args, activeRun));
      activeRun = null;
    }
  }
  catch (error) {
    if (activeRun?.source_study && !activeRun.source_study.closed) {
        const terminal = activeRun.source_study.terminate('source-study-recording-artifact-failed',
          'Recording post-processing failed before immutable source-study artifacts could be completed; partial evidence is ineligible.',
          { source_error: String(error?.message || error) });
        error.source_study = error.source_study || terminal.source_study;
        error.source_study_progress = error.source_study_progress || terminal.source_study_progress;
        error.source_study_failure = error.source_study_failure || terminal.source_study_failure;
      }
    throw error;
  }
  finally { await closeBrowserBounded(browser); }
  const complete = profiles.every((profile) => profile.coverage.complete);
  const capturesByViewport = Object.fromEntries(profiles.map((profile) => [profile.profile,
    { file: profile.source_entry_capture.file, bytes: profile.source_entry_capture.bytes,
      sha256: profile.source_entry_capture.sha256 }]));
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
      "source_surface_watch.mjs": SOURCE_SURFACE_WATCH_SHA256,
      "source_study_controller.mjs": SOURCE_STUDY_CONTROLLER_SHA256,
      "playwright-entry": loaded.dependency.sha256, "browser-executable": browserSha256 },
    dependencies: { recorder: { file: "record_reference.mjs", sha256: PRODUCER_SCRIPT_SHA256 },
      browser_evidence: { file: "browser_evidence.mjs", sha256: BROWSER_EVIDENCE_SHA256 },
      playwright_resolver: { file: "playwright_resolver.mjs", sha256: PLAYWRIGHT_RESOLVER_SHA256 },
      source_surface_watch: { file: "source_surface_watch.mjs", sha256: SOURCE_SURFACE_WATCH_SHA256 },
      source_study_controller: { file: "source_study_controller.mjs", sha256: SOURCE_STUDY_CONTROLLER_SHA256 },
      playwright: loaded.dependency, browser_executable: browserDependency },
    id: args.id, url: args.url,
    source_kind: 'public-source', source_status: complete ? 'complete' : 'partial', eligible_for_source_selection: complete,
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
  let failureReport = null;
  if (!complete) {
    const failureFile = path.join(args.out, `${args.id}-recording-failure.json`);
    const failure = {
      schema_version: 1,
      kind: "reference-recording-incomplete",
      status: "incomplete-not-selection-evidence",
      source_status: 'partial', eligible_for_source_selection: false,
      id: args.id,
      recording: artifactEntry(args.out, recordingFile, "recording"),
      artifact_ledger: artifactEntry(args.out, ledgerFile, "artifact-ledger"),
      profiles: profiles.map((profile) => ({
        profile: profile.profile,
        coverage_complete: profile.coverage.complete,
        interaction_census: interactionCensusDiagnostic(profile.interaction_census,
          { phase: "recording-complete-run", source_state_id: null, pass: null }),
        hover_failures: profile.coverage.hover_failures,
        missing_internal_pages: profile.coverage.missing_internal_pages,
        missing_states: profile.coverage.missing_states,
        incomplete_scroll_traversals: profile.coverage.incomplete_scroll_traversals,
        unreconciled_states: profile.coverage.unreconciled_states,
      })),
    };
    writeJsonAtomically(failureFile, failure);
    failureReport = { file: failureFile, sha256: sha256(failureFile) };
  }
  process.stdout.write(JSON.stringify({ ok: complete, recording: recordingPath, artifact_ledger: ledgerFile,
    artifact_ledger_sha256: sha256(path.join(args.out, ledgerFile)), profiles: profiles.map((profile) => ({ profile: profile.profile,
      duration_s: profile.duration_s, frames: profile.frames.count, events: profile.events.count, coverage: profile.coverage.complete })),
    failure_report: failureReport }, null, 2) + "\n");
  if (!complete) process.exitCode = 1;
}

// Bounds derived from scope, not from a fixed number: an interaction census
// walks every discovered target, and a scroll traversal may take 240 settled
// positions with per-position evidence. The silence watchdog catches a hang.
const RECORDER_CENSUS_TIMEOUT_MS = 600_000;
const RECORDER_SCROLL_TRAVERSAL_TIMEOUT_MS = 240 * 5_500 + 60_000;

function scheduleExitAfterSettle() {
  // The recording settled and both leases are released. If a stuck browser
  // handle still keeps the event loop alive, exit with the recorded code;
  // unref() means a clean run never waits on this timer.
  setTimeout(() => process.exit(process.exitCode ?? 0), 3000).unref();
}
const invokedDirectly = process.argv[1]
  && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url));
if (invokedDirectly) main().catch((error) => {
  process.stdout.write(JSON.stringify({ ok: false, error: { code: error.code || "recording-failed",
    message: String(error.message || error).slice(0, 1000), navigation: error.navigation || null,
    failure_report: error.failure_report || null,
    source_study: error.source_study || null,
    source_study_progress: error.source_study_progress || null,
    source_study_failure: error.source_study_failure || null,
    original_cause: error.original_cause || null } }, null, 2) + "\n");
  process.exitCode = 2;
}).finally(scheduleExitAfterSettle);
