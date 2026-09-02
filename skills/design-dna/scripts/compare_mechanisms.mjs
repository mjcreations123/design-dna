#!/usr/bin/env node
/**
 * compare_mechanisms.mjs
 *
 * Read the finished build with exactly the same eyes that read its references,
 * and say whether the references' mechanisms actually arrived.
 *
 * A producer who copied a background color and a font size from a site whose
 * signature was a pinned stage will pass every static review. This is the
 * check that catches it: the build is observed with observe_reference.mjs's
 * mechanism pass, and its mechanism sheet is diffed against the sheets of the
 * selected references.
 *
 * It fails when:
 *   - a scroll or pointer mechanism the references rely on is absent from the
 *     build (missing);
 *   - one device is used far more often in the build than in any source, which
 *     is the "same fade on every section" tell (over_used);
 *   - the references carry scroll choreography and the build carries none
 *     (skeleton), because a page with nothing that holds, travels, swaps or
 *     reveals is the generic skeleton however it is dressed.
 *
 * Usage:
 *   node compare_mechanisms.mjs --url http://127.0.0.1:4880/ \
 *        --source .design-dna/references/strong-1-observation.json \
 *        --source .design-dna/references/strong-2-observation.json \
 *        --out .design-dna/evidence/mechanism-diff.json [--browser-executable FILE]
 */
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";
import { mechanismPass } from "./observe_reference.mjs";

const SCHEMA_VERSION = 1;
const SCROLL_TYPES = new Set(["pinned", "parallax", "reveal", "swap"]);
const POINTER_TYPES = new Set(["pointer-follow", "hover-transition"]);
const OVERUSE_FLOOR = 4;
const OVERUSE_RATIO = 2;

function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }, null, 2) + "\n");
  process.exit(2);
}

function parseArgs(argv) {
  const out = { url: null, sources: [], outFile: null, browserExecutable: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--url") out.url = argv[++i];
    else if (a === "--source") out.sources.push(argv[++i]);
    else if (a === "--out") out.outFile = argv[++i];
    else if (a === "--browser-executable") out.browserExecutable = argv[++i];
    else if (a === "--help" || a === "-h") {
      process.stdout.write("compare_mechanisms.mjs --url URL --source OBS.json [--source ...] --out FILE [--browser-executable FILE]\n");
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${a}`);
  }
  if (!out.url || !/^https?:\/\//i.test(out.url)) fail("invalid-url", "--url must be an http(s) URL of the built site.");
  if (!out.sources.length) fail("no-sources", "At least one --source observation is required.");
  if (!out.outFile) fail("invalid-out", "--out must name the diff file to write.");
  return out;
}

function loadPlaywright() {
  const require = createRequire(import.meta.url);
  const moduleDir = process.env.DESIGN_DNA_PLAYWRIGHT_MODULE_DIR;
  const attempt = (name) => {
    if (moduleDir) { try { return require(path.join(moduleDir, name)); } catch (e) { /* fall through */ } }
    return require(name);
  };
  for (const name of ["playwright", "playwright-core"]) {
    try { const pw = attempt(name); if (pw?.chromium) return pw; } catch (e) { /* next */ }
  }
  fail("playwright-unavailable", "Playwright could not be loaded. Install it, or set DESIGN_DNA_PLAYWRIGHT_MODULE_DIR.");
  return null;
}

// How many elements carry each device. The observation records this before
// its mechanism list is deduplicated, so a fade applied to every section is
// eight instances even though it prints as one line.
function countTypes(sheet) {
  const recorded = sheet && sheet.score && sheet.score.type_instances;
  if (recorded && typeof recorded === "object") return { ...recorded };
  const counts = {};
  for (const m of (sheet && sheet.mechanisms) || []) counts[m.type] = (counts[m.type] || 0) + 1;
  return counts;
}

export function diffSheets(build, sources) {
  const buildCounts = countTypes(build);
  const sourceTypes = new Set();
  const sourceMax = {};
  const perSource = [];
  for (const s of sources) {
    const counts = countTypes(s);
    for (const [t, c] of Object.entries(counts)) {
      sourceTypes.add(t);
      sourceMax[t] = Math.max(sourceMax[t] || 0, c);
    }
    perSource.push({ id: s.id || null, url: s.url || null, types: Object.keys(counts), score: s.score || null });
  }
  const buildTypes = new Set(Object.keys(buildCounts));
  const wanted = [...sourceTypes].filter((t) => SCROLL_TYPES.has(t) || POINTER_TYPES.has(t));
  const missing = wanted.filter((t) => !buildTypes.has(t));
  const overUsed = Object.entries(buildCounts)
    .filter(([t, c]) => SCROLL_TYPES.has(t) && c >= OVERUSE_FLOOR && c > (sourceMax[t] || 0) * OVERUSE_RATIO)
    .map(([t, c]) => ({ type: t, build: c, source_max: sourceMax[t] || 0 }));
  const sourcesHaveScroll = wanted.some((t) => SCROLL_TYPES.has(t));
  const buildHasScroll = [...buildTypes].some((t) => SCROLL_TYPES.has(t));
  const skeleton = sourcesHaveScroll && !buildHasScroll;
  // a build must carry at least half of the references' scroll and pointer
  // mechanism types, and never be a skeleton or a one-device page
  const carried = wanted.filter((t) => buildTypes.has(t));
  const carriedEnough = wanted.length === 0 || carried.length * 2 >= wanted.length;
  const pass = carriedEnough && overUsed.length === 0 && !skeleton;
  return {
    pass,
    build_types: [...buildTypes].sort(),
    source_types: [...sourceTypes].sort(),
    wanted, carried, missing,
    over_used: overUsed,
    skeleton,
    build_score: build.score || null,
    sources: perSource,
    verdict: pass
      ? "The build carries the references' mechanisms and no single device is overused."
      : [
        skeleton ? "the references carry scroll choreography and the build carries none" : null,
        !carriedEnough ? `the build carries ${carried.length} of ${wanted.length} mechanism types the references rely on (${missing.join(", ")} missing)` : null,
        overUsed.length ? `one device is overused: ${overUsed.map((o) => `${o.type} x${o.build} vs source max ${o.source_max}`).join("; ")}` : null,
      ].filter(Boolean).join("; "),
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const sources = args.sources.map((file) => {
    let payload;
    try { payload = JSON.parse(fs.readFileSync(file, "utf8")); } catch (e) { fail("source-unreadable", `${file}: ${String(e).slice(0, 120)}`); }
    if (payload.tool !== "observe_reference.mjs" || payload.schema_version !== 2) {
      fail("source-not-observation", `${file} is not a schema-2 observe_reference.mjs record.`);
    }
    return payload;
  });
  const pw = loadPlaywright();
  const browser = await pw.chromium.launch(args.browserExecutable ? { executablePath: args.browserExecutable } : {});
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })).newPage();
  try {
    await page.goto(args.url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(1500);
    const build = await mechanismPass(page);
    const diff = diffSheets(build, sources);
    const record = {
      schema_version: SCHEMA_VERSION,
      tool: "compare_mechanisms.mjs",
      url: args.url,
      compared_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      source_files: args.sources.map((f) => path.basename(f)),
      build_mechanisms: build.mechanisms,
      ...diff,
    };
    fs.mkdirSync(path.dirname(args.outFile), { recursive: true });
    fs.writeFileSync(args.outFile, JSON.stringify(record, null, 2) + "\n", "utf8");
    process.stdout.write(JSON.stringify({ ok: true, diff: args.outFile, pass: diff.pass, verdict: diff.verdict, build_types: diff.build_types, missing: diff.missing, over_used: diff.over_used }, null, 2) + "\n");
  } catch (error) {
    fail("comparison-failed", String(error).slice(0, 400));
  } finally {
    await browser.close().catch(() => {});
  }
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
if (invokedDirectly) main();
