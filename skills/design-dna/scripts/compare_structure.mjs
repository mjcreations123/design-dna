#!/usr/bin/env node
/**
 * compare_structure.mjs
 *
 * Does the finished build's first screen look like it came from the reference
 * it names?
 *
 * Every gate before this one checked that the producer LOOKED at a reference.
 * None checked whether the build RESEMBLED one. With only a property reader
 * available, the producer measured font sizes and padding, invented the
 * layout, chose typefaces by taste, and shipped its own design with a single
 * borrowed button on it. The owner saw it in one second. This is the check
 * that sees it too.
 *
 * It reads the build's first screen with the same probe that recorded the
 * reference's, and compares four things:
 *   dominant  what the largest thing on the first screen is: a photograph, a
 *             text block, or a filled box
 *   ink       where the ink actually sits, over a 24x16 sampled grid
 *   edges     what lives against each edge and in each corner
 *   type      the proportions of the type: display-to-body scale, leading,
 *             x-height ratio, width, case. This is what refuses a typeface
 *             chosen by taste.
 *
 * Fewer than three of four is a fail.
 *
 * Usage:
 *   node compare_structure.mjs --url http://127.0.0.1:4920/ \
 *     --reference .design-dna/references/strong-1-observation.json \
 *     --out .design-dna/evidence/structure-diff.json [--browser-executable FILE]
 */
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";
import { STRUCTURE_SCRIPT, diffStructure } from "./structure_probe.mjs";

const SCHEMA_VERSION = 1;

function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }, null, 2) + "\n");
  process.exit(2);
}

function parseArgs(argv) {
  const out = { url: null, references: [], outFile: null, browserExecutable: null, route: "/" };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--url") out.url = argv[++i];
    else if (a === "--reference") out.references.push(argv[++i]);
    else if (a === "--out") out.outFile = argv[++i];
    else if (a === "--browser-executable") out.browserExecutable = argv[++i];
    else if (a === "--help" || a === "-h") {
      process.stdout.write("compare_structure.mjs --url URL --reference OBS.json [--reference ...] --out FILE\n");
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${a}`);
  }
  if (!out.url || !/^https?:\/\//i.test(out.url)) fail("invalid-url", "--url must be the built site's http(s) URL.");
  if (!out.references.length) fail("no-reference", "At least one --reference observation is required.");
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

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const refs = args.references.map((file) => {
    let payload;
    try { payload = JSON.parse(fs.readFileSync(file, "utf8")); } catch (e) {
      fail("reference-unreadable", `${file}: ${String(e).slice(0, 120)}`);
    }
    if (payload.tool !== "observe_reference.mjs" || payload.schema_version !== 3) {
      fail("reference-not-schema-3", `${file} is not a schema-3 observe_reference.mjs record; re-run the harness.`);
    }
    if (!payload.first_screen || !payload.first_screen.grid) {
      fail("reference-has-no-structure", `${file} carries no first-screen structure.`);
    }
    return { file: path.basename(file), id: payload.id, url: payload.url, structure: payload.first_screen };
  });

  const pw = loadPlaywright();
  const browser = await pw.chromium.launch(args.browserExecutable ? { executablePath: args.browserExecutable } : {});
  try {
    const ref0 = refs[0].structure.viewport || { w: 1440, h: 900 };
    const page = await (await browser.newContext({
      viewport: { width: ref0.w || 1440, height: ref0.h || 900 },
      deviceScaleFactor: 1,
    })).newPage();
    await page.goto(args.url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(2600);
    const build = await page.evaluate(STRUCTURE_SCRIPT);

    // The build is compared against every reference it might have been built
    // from; the best match is the one it actually resembles, and it has to
    // resemble at least one of them.
    const results = refs.map((r) => ({ reference: r.file, id: r.id, url: r.url, ...diffStructure(build, r.structure) }));
    results.sort((a, b) => b.passed - a.passed);
    const best = results[0];
    const record = {
      schema_version: SCHEMA_VERSION,
      tool: "compare_structure.mjs",
      url: args.url,
      compared_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      pass: best.pass,
      best_match: best.reference,
      verdict: best.pass
        ? `The first screen is built like ${best.id} (${best.passed} of ${best.of} structural tests).`
        : best.verdict,
      build_first_screen: build,
      results,
    };
    fs.mkdirSync(path.dirname(args.outFile), { recursive: true });
    fs.writeFileSync(args.outFile, JSON.stringify(record, null, 2) + "\n", "utf8");
    process.stdout.write(JSON.stringify({
      ok: true, diff: args.outFile, pass: record.pass, best_match: best.reference,
      verdict: record.verdict,
      scores: results.map((r) => `${r.id}:${r.passed}/${r.of}`),
    }, null, 2) + "\n");
  } catch (error) {
    fail("comparison-failed", String(error).slice(0, 400));
  } finally {
    await browser.close().catch(() => {});
  }
}

const invokedDirectly = process.argv[1]
  && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
if (invokedDirectly) main();
