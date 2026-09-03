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
 * EVERY route is compared, not only the home page. Pass --url once per
 * route. A producer that copied one first screen faithfully and then
 * invented two whole inner pages passed this check when it read one
 * screen; it does not pass when it reads all of them. Each route has to
 * resemble some reference PAGE, which means an inner route needs an
 * observation of a reference's inner page to be compared against: a home
 * page capture cannot tell you how that site builds its second screen.
 *
 * Usage:
 *   node compare_structure.mjs \
 *     --census .design-dna/evidence/component-census.json \
 *     --reference .design-dna/references/strong-1-observation.json \
 *     --reference .design-dna/references/strong-1-inner-observation.json \
 *     --out .design-dna/evidence/structure-diff.json [--browser-executable FILE]
 *
 * --census takes the route list from scan_build_components.mjs, which is
 * the only way this check covers the routes a producer would rather not
 * compare.
 */
import { createHash } from "node:crypto";
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
  const out = { urls: [], references: [], outFile: null, browserExecutable: null, census: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--url") out.urls.push(argv[++i]);
    else if (a === "--reference") out.references.push(argv[++i]);
    else if (a === "--out") out.outFile = argv[++i];
    else if (a === "--census") out.census = argv[++i];
    else if (a === "--browser-executable") out.browserExecutable = argv[++i];
    else if (a === "--help" || a === "-h") {
      process.stdout.write("compare_structure.mjs --url URL [--url URL ...] --reference OBS.json [--reference ...] --out FILE\n");
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${a}`);
  }
  // The route list comes from the census of what the build actually renders,
  // so a producer cannot structure-check the one screen it copied and leave
  // the pages it invented uncompared.
  if (out.census) {
    let payload;
    try { payload = JSON.parse(fs.readFileSync(out.census, "utf8")); } catch (e) {
      fail("census-unreadable", `${out.census}: ${String(e).slice(0, 120)}`);
    }
    if (payload.tool !== "scan_build_components.mjs" || !Array.isArray(payload.routes)) {
      fail("census-invalid", `${out.census} is not a scan_build_components.mjs record.`);
    }
    out.censusSha = createHash("sha256").update(fs.readFileSync(out.census)).digest("hex");
    for (const route of payload.routes) {
      if (route && typeof route.url === "string" && out.urls.indexOf(route.url) < 0) {
        out.urls.push(route.url);
      }
    }
  }
  if (!out.urls.length || out.urls.some((u) => !/^https?:\/\//i.test(u))) {
    fail("invalid-url", "--url must be the built site's http(s) URL, once per route, or --census must name the component census.");
  }
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
    const context = await browser.newContext({
      viewport: { width: ref0.w || 1440, height: ref0.h || 900 },
      deviceScaleFactor: 1,
    });

    // Every route is read, and each is compared against every reference page
    // it might have been built from. A route that resembles nothing is a page
    // the producer designed.
    const routes = [];
    for (const url of args.urls) {
      const page = await context.newPage();
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
      await page.waitForTimeout(2600);
      const build = await page.evaluate(STRUCTURE_SCRIPT);
      await page.close();
      const results = refs.map((r) => ({ reference: r.file, id: r.id, url: r.url, ...diffStructure(build, r.structure) }));
      results.sort((a, b) => b.passed - a.passed);
      const best = results[0];
      routes.push({
        url,
        pass: best.pass,
        best_match: best.reference,
        verdict: best.pass
          ? `Built like ${best.id} (${best.passed} of ${best.of} structural tests).`
          : best.verdict,
        build_first_screen: build,
        results,
      });
    }

    const failed = routes.filter((r) => !r.pass);
    const record = {
      schema_version: SCHEMA_VERSION,
      tool: "compare_structure.mjs",
      urls: args.urls,
      url: args.urls[0],
      census_file: args.census || null,
      census_sha256: args.censusSha || null,
      compared_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      pass: failed.length === 0,
      routes_compared: routes.length,
      best_match: routes[0] ? routes[0].best_match : null,
      verdict: failed.length === 0
        ? `All ${routes.length} route(s) are built like a reference page.`
        : `${failed.length} of ${routes.length} route(s) resemble no reference page. ` +
          failed.map((r) => `${r.url}: ${r.verdict}`).join(" | "),
      routes,
    };
    fs.mkdirSync(path.dirname(args.outFile), { recursive: true });
    fs.writeFileSync(args.outFile, JSON.stringify(record, null, 2) + "\n", "utf8");
    process.stdout.write(JSON.stringify({
      ok: true, diff: args.outFile, pass: record.pass,
      routes_compared: record.routes_compared,
      verdict: record.verdict,
      per_route: routes.map((r) => `${r.url} -> ${r.best_match || "nothing"} ${r.pass ? "pass" : "FAIL"}`),
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
