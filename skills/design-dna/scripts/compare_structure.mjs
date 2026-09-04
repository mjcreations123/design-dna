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
 * All four dimensions must pass; one mismatch cannot be outvoted by three
 * coarse similarities.
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
import path from "node:path";
import process from "node:process";
import { STRUCTURE_SCRIPT, diffStructure } from "./structure_probe.mjs";
import {
  aggregateServedContent,
  applyManifestState,
  beginServedContentCapture,
  installDomInspection,
  navigateExact,
} from "./browser_evidence.mjs";
import {
  bindSuppliedObservations,
  loadRouteManifest,
  PRODUCER_OUTPUT_SCHEMA_VERSION,
} from "./provenance_contract.mjs";
import { browserExecutableIdentity, discoverBrowserExecutable, resolvePlaywright } from "./playwright_resolver.mjs";

const SCHEMA_VERSION = PRODUCER_OUTPUT_SCHEMA_VERSION;
const SCRIPT_PATH = path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const SCRIPT_DIR = path.dirname(SCRIPT_PATH);
const PRODUCER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(SCRIPT_PATH)).digest("hex");
const OBSERVER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "observe_reference.mjs"))).digest("hex");
const CENSUS_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "scan_build_components.mjs"))).digest("hex");
const STRUCTURE_PROBE_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "structure_probe.mjs"))).digest("hex");
const BROWSER_EVIDENCE_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "browser_evidence.mjs"))).digest("hex");
const PLAYWRIGHT_RESOLVER_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "playwright_resolver.mjs"))).digest("hex");
const PROVENANCE_CONTRACT_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(SCRIPT_DIR, "provenance_contract.mjs"))).digest("hex");

function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }, null, 2) + "\n");
  process.exit(2);
}

function parseArgs(argv) {
  const out = { references: [], outFile: null,
    browserExecutable: process.env.DESIGN_DNA_BROWSER_EXECUTABLE || process.env.CHROME || null,
    census: null, manifest: null, buildId: null, runId: null, routeKeys: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--reference") out.references.push(argv[++i]);
    else if (a === "--out") out.outFile = argv[++i];
    else if (a === "--census") out.census = argv[++i];
    else if (a === "--manifest") out.manifest = argv[++i];
    else if (a === "--build-id") out.buildId = argv[++i];
    else if (a === "--run-id") out.runId = argv[++i];
    else if (a === "--route-key") out.routeKeys.push(argv[++i]);
    else if (a === "--browser-executable") out.browserExecutable = argv[++i];
    else if (a === "--help" || a === "-h") {
      process.stdout.write("compare_structure.mjs --manifest FILE --census FILE --build-id ID --reference OBS.json [--reference ...] --out FILE\n");
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${a}`);
  }
  if (!out.manifest || !out.census || !out.buildId || !out.runId) fail("usage", "--manifest, --census, --build-id and --run-id are required.");
  if (!out.references.length) fail("no-reference", "At least one --reference observation is required.");
  if (!out.outFile) fail("invalid-out", "--out must name the diff file to write.");
  return out;
}

function readJson(file, code) {
  try { return JSON.parse(fs.readFileSync(file, "utf8")); }
  catch (error) { fail(code, `${file}: ${String(error).slice(0, 160)}`); }
}

function rankOf(payload, file) {
  const match = String(payload.id || path.basename(file)).match(/strong-(\d+)/i);
  return match ? Number(match[1]) : null;
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

async function main() {
  const args = parseArgs(process.argv.slice(2));
  let manifest, mappedByRoute;
  try {
    manifest = loadRouteManifest(args.manifest);
    mappedByRoute = bindSuppliedObservations(manifest, args.references, OBSERVER_SCRIPT_SHA256);
  } catch (error) {
    fail("manifest-reference-binding-invalid", String(error).slice(0, 500));
  }
  if (args.routeKeys.some((key) => !manifest.routes.some((route) => route.key === key))) fail("route-key-missing", "Every --route-key must exist in the manifest.");
  const census = readJson(args.census, "census-unreadable");
  if (census?.tool !== "scan_build_components.mjs" || census.schema_version !== SCHEMA_VERSION || census.build_id !== args.buildId ||
      census.run_id !== args.runId || census.manifest_id !== manifest.manifest_id || census.manifest_sha256 !== manifest.__sha256 ||
      census.pass !== true || census.producer_script_sha256 !== CENSUS_SCRIPT_SHA256) {
    fail("census-invalid", "The census must be a passing current-schema record for this exact build, run, and route manifest.");
  }
  const manifestSha = manifest.__sha256;
  const censusSha = createHash("sha256").update(fs.readFileSync(args.census)).digest("hex");
  for (const [routeKey, binding] of mappedByRoute) {
    const payload = binding.payload;
    const route = manifest.routes.find((item) => item.key === routeKey);
    if (payload.runtime_identity?.["structure_probe.mjs"] !== STRUCTURE_PROBE_SHA256 ||
        !payload.states_by_viewport?.wide || !payload.states_by_viewport?.narrow ||
        route.states.some((state) => !payload.states_by_viewport.wide[state.mapped_reference_state_id]?.structure ||
          !payload.states_by_viewport.narrow[state.mapped_reference_state_id]?.structure)) {
      fail("reference-structure-invalid", `Route ${routeKey}'s exact observation lacks a wide/narrow structure sheet for every mapped source state.`);
    }
  }

  const loaded = loadPlaywright();
  const browserDependency = loadBrowserDependency(loaded, args.browserExecutable);
  const browser = await loaded.playwright.chromium.launch({ executablePath: browserDependency.file });
  try {
    const routes = [];
    const servedProbes = [];
    for (const viewport of manifest.viewports) {
      const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
      await installDomInspection(context);
      const selectedRoutes = args.routeKeys.length ? manifest.routes.filter((route) => args.routeKeys.includes(route.key)) : manifest.routes;
      for (const route of selectedRoutes) {
        const mapped = mappedByRoute.get(route.key);
        if (!mapped) fail("mapped-reference-missing", `Route ${route.key} has no exact bound observation.`);
        const profile = viewport.width <= 430 ? "narrow" : "wide";
        for (const state of route.states) {
          const sourceState = mapped.payload.states_by_viewport[profile][state.mapped_reference_state_id];
          const page = await context.newPage();
          const navigations = [];
          const restLoads = [];
          for (let reload = 0; reload < 2; reload += 1) {
            const capture = beginServedContentCapture(page, route.url);
            const navigation = await navigateExact(page, route.url);
            capture.setFinalResponse(navigation);
            await page.evaluate(() => document.fonts?.ready).catch(() => {});
            await page.waitForTimeout(700);
            const served = await capture.finish({ route_key: route.key, viewport: viewport.name });
            navigations.push(navigation);
            restLoads.push(served);
            servedProbes.push(served);
          }
          if (new Set(restLoads.map((entry) => entry.sha256)).size !== 1) {
            fail("served-content-reload-drift", `${route.key}/${viewport.name} returned different response-body identities across its two required rest loads.`);
          }
          const stateApplication = await applyManifestState(page, state);
          const build = await page.evaluate(STRUCTURE_SCRIPT);
          await page.close();
          const result = {
            reference: mapped.observation,
            id: mapped.id,
            rank: mapped.rank,
            url: mapped.url,
            sha256: mapped.sha256,
            source_viewport: profile,
            source_state_id: state.mapped_reference_state_id,
            ...diffStructure(build, sourceState.structure),
          };
          const structuralInspectionComplete = build.inspection?.complete === true &&
            sourceState.structure.inspection?.complete === true;
          if (!structuralInspectionComplete) {
            result.pass = false;
            result.verdict = `Visible pseudo/shadow/iframe/canvas structure was not completely comparable (build: ${(build.inspection?.uninspectable || []).join(", ") || "incomplete"}; source: ${(sourceState.structure.inspection?.uninspectable || []).join(", ") || "incomplete"}).`;
          }
          const stateContractMatch = sourceState.id === state.mapped_reference_state_id &&
            sourceState.kind === state.kind && sourceState.trigger?.type === state.trigger.type;
          if (!stateContractMatch) {
            result.pass = false;
            result.verdict = `Mapped source state ${state.mapped_reference_state_id} does not use the build state's ${state.kind}/${state.trigger.type} behavior contract.`;
          }
          routes.push({
            route_key: route.key, url: route.url, viewport: viewport.name,
            width: viewport.width, height: viewport.height,
            state_id: state.id,
            state_kind: state.kind,
            state_trigger: state.trigger,
            state_expectation: state.expectation,
            mapped_reference_state_id: state.mapped_reference_state_id,
            state_application: stateApplication,
            mapped_reference: {
              rank: mapped.rank, id: mapped.id, observation: mapped.observation,
              sha256: mapped.sha256, url: mapped.url,
            },
            source_mapping: {
              rank: mapped.rank, id: mapped.id, observation: mapped.observation,
              sha256: mapped.sha256, state_id: state.mapped_reference_state_id,
            },
            mapped_reference_rank: mapped.rank,
            mapped_reference_id: mapped.id,
            mapped_reference_sha256: mapped.sha256,
            state_contract_match: stateContractMatch,
            structural_inspection_complete: structuralInspectionComplete,
            navigations,
            pass: Boolean(result.pass),
            verdict: result.pass ? `Built like exact mapped ${result.id}/${state.mapped_reference_state_id} (${result.passed} of ${result.of} structural tests).` : result.verdict,
            served_content_sha256: restLoads[0].sha256,
            build_first_screen: build,
            result,
          });
        }
      }
      await context.close();
    }

    const failed = routes.filter((r) => !r.pass);
    const record = {
      schema_version: SCHEMA_VERSION,
      tool: "compare_structure.mjs",
      producer_script_sha256: PRODUCER_SCRIPT_SHA256,
      runtime_identity: {
        "compare_structure.mjs": PRODUCER_SCRIPT_SHA256,
        "structure_probe.mjs": STRUCTURE_PROBE_SHA256,
        "scan_build_components.mjs": CENSUS_SCRIPT_SHA256,
        "browser_evidence.mjs": BROWSER_EVIDENCE_SHA256,
        "playwright_resolver.mjs": PLAYWRIGHT_RESOLVER_SHA256,
        "provenance_contract.mjs": PROVENANCE_CONTRACT_SHA256,
        "playwright-entry": loaded.dependency.resolved_file_sha256,
        "browser-executable": browserDependency.sha256,
      },
      dependencies: { playwright: loaded.dependency, browser_executable: browserDependency },
      build_id: args.buildId,
      run_id: args.runId,
      manifest_id: manifest.manifest_id,
      route_filter: args.routeKeys,
      manifest_file: args.manifest,
      manifest_sha256: manifestSha,
      census_file: args.census,
      census_sha256: censusSha,
      compared_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      served_content_identity: aggregateServedContent(servedProbes),
      pass: failed.length === 0,
      routes_compared: routes.length,
      verdict: failed.length === 0
        ? `All ${routes.length} route/viewport/state cells match their exact bound reference observation and source state.`
        : `${failed.length} of ${routes.length} route/viewport/state cells fail their mapped reference. ` +
          failed.map((r) => `${r.route_key}/${r.viewport}/${r.state_id}: ${r.verdict}`).join(" | "),
      routes,
    };
    fs.mkdirSync(path.dirname(args.outFile), { recursive: true });
    fs.writeFileSync(args.outFile, JSON.stringify(record, null, 2) + "\n", "utf8");
    process.stdout.write(JSON.stringify({
      ok: true, diff: args.outFile, pass: record.pass,
      routes_compared: record.routes_compared,
      verdict: record.verdict,
      per_route: routes.map((r) => `${r.route_key}/${r.viewport}/${r.state_id} -> ${r.mapped_reference_id}/${r.mapped_reference_state_id}@${r.mapped_reference_sha256.slice(0, 12)} ${r.pass ? "pass" : "FAIL"}`),
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
