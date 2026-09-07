#!/usr/bin/env node
/**
 * check_build.mjs
 *
 * Reads the BUILT site with the same eyes as its references and compares it to
 * the plan. One command, about a minute, one verdict line to quote verbatim.
 *
 *   node check_build.mjs --plan .design-dna/plan.json --studies .design-dna/references --out .design-dna/check
 *        [--route-seconds 10] [--browser-executable FILE]
 *
 * plan.json (written by the AI before building, read here):
 * {
 *   "references": [ { "id": "strong-1", "signature": "the product images slide sideways under a pinned heading",
 *                     "signature_mechanisms": ["pinned", "travel"], "take": ["pinned", "travel", "hover-transition"] } ],
 *   "typefaces": [ { "family": "Fraunces", "from": "strong-1" }, { "family": "Inter", "from": "strong-2" } ],
 *   "ground": { "color": "rgb(14, 14, 14)", "from": "strong-1" },
 *   "routes": [ { "url": "http://127.0.0.1:4870/", "name": "home", "dominant": "strong-1", "mechanisms": ["pinned", "travel", "reveal"] } ]
 * }
 *
 * Checks, each with its evidence in check.json:
 *   fonts        every family the build computes comes from a studied reference (or a declared match);
 *   ground       the build's dominant painted ground is a studied reference's dominant ground;
 *   signatures   each reference's signature mechanisms were detected on that reference AND appear in the build;
 *   mechanisms   each route carries the mechanisms the plan promised, and every one of them exists in a studied reference;
 *   hover        if a reference's controls respond to the pointer, the build's controls do too;
 *   motion       the build is not a static page dressed as a copy: distinct mechanisms and scroll coverage are at least the weakest selected reference's;
 *   slop         no gradient-text headline, no icon-card triplet hero, no all-same-radius pill wall, no fade-up-on-everything as the only motion.
 *
 * Verdict: "CHECK PASS <n> checks" or "CHECK FAIL <reasons>". Nothing here scores taste; it proves the build
 * carries what the plan said it took from sites the tool actually watched.
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { resolvePlaywright, discoverBrowserExecutable } from "./playwright_resolver.mjs";
import { studyPage } from "./study_reference.mjs";

const TOOL = "check_build.mjs";
const VIEWPORTS = [{ name: "wide", width: 1440, height: 900 }, { name: "narrow", width: 390, height: 844 }];
const GENERIC_FAMILIES = new Set(["serif", "sans-serif", "monospace", "system-ui", "ui-sans-serif", "ui-serif", "ui-monospace", "cursive", "fantasy", "-apple-system", "blinkmacsystemfont", "segoe ui", "roboto", "helvetica neue", "arial", "inherit"]);

function parseArgs(argv) {
  const out = { plan: null, studies: null, outDir: null, routeSeconds: 10, browserExecutable: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--plan") out.plan = argv[++i];
    else if (a === "--studies") out.studies = argv[++i];
    else if (a === "--out") out.outDir = argv[++i];
    else if (a === "--route-seconds") out.routeSeconds = Number(argv[++i]);
    else if (a === "--browser-executable") out.browserExecutable = argv[++i];
    else if (a === "--help" || a === "-h") { process.stdout.write(`usage: node ${TOOL} --plan FILE --studies DIR --out DIR [--route-seconds S]\n`); process.exit(0); }
    else fail("invalid-argument", `Unknown argument ${a}.`);
  }
  if (!out.plan || !fs.existsSync(out.plan)) fail("plan-missing", "--plan must name an existing plan.json.");
  if (!out.studies || !fs.existsSync(out.studies)) fail("studies-missing", "--studies must name the directory holding <id>/study.json records.");
  if (!out.outDir) fail("invalid-out", "--out must name a directory.");
  return out;
}
function fail(code, message) {
  process.stdout.write(`CHECK FAIL ${code}: ${message}\n`);
  process.exit(2);
}
const norm = (family) => String(family || "").replace(/["']/g, "").trim().toLowerCase();
const rgb = (color) => {
  const m = String(color || "").match(/rgba?\(([^)]+)\)/); if (!m) return null;
  const [r, g, b, a] = m[1].split(",").map((x) => parseFloat(x));
  return a === 0 ? null : [r, g, b];
};
const colorDistance = (a, b) => { const x = rgb(a), y = rgb(b); if (!x || !y) return Infinity; return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]); };

function loadStudies(dir) {
  const studies = new Map();
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const file = path.join(dir, entry.name, "study.json");
    if (fs.existsSync(file)) studies.set(entry.name, JSON.parse(fs.readFileSync(file, "utf8")));
  }
  return studies;
}
const primary = (study, viewport = "wide") => study.pages.find((p) => p.role === "primary" && p.viewport === viewport);
const mechanismTypes = (page) => new Set((page?.motion?.mechanisms || []).map((m) => m.type));
const realFamilies = (design) => (design?.fonts || []).map((f) => norm(f.family)).filter((f) => f && !GENERIC_FAMILIES.has(f));

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const plan = JSON.parse(fs.readFileSync(args.plan, "utf8"));
  const studies = loadStudies(args.studies);
  const outDir = path.resolve(args.outDir);
  const frameDir = path.join(outDir, "frames"), videoDir = path.join(outDir, "videos");
  fs.mkdirSync(frameDir, { recursive: true }); fs.mkdirSync(videoDir, { recursive: true });
  const problems = [], passed = [];
  const evidence = { plan: args.plan, studies: [...studies.keys()], routes: [] };

  // The plan must cite studied references only.
  for (const ref of plan.references || []) {
    if (!studies.has(ref.id)) problems.push(`plan cites reference ${ref.id} but ${args.studies}/${ref.id}/study.json does not exist`);
  }
  const selected = (plan.references || []).map((r) => r.id).filter((id) => studies.has(id));
  if (selected.length < 4) problems.push(`plan selects ${selected.length} studied references; the owner's floor is four`);

  // Signatures must be measured on their own reference.
  for (const ref of plan.references || []) {
    const study = studies.get(ref.id); if (!study) continue;
    const detected = new Set([...mechanismTypes(primary(study, "wide")), ...mechanismTypes(primary(study, "narrow"))]);
    for (const type of ref.signature_mechanisms || []) {
      if (!detected.has(type)) problems.push(`${ref.id}: signature mechanism "${type}" was not detected on that site (detected: ${[...detected].join(", ") || "none"})`);
    }
    if (!ref.signature || !/\b(hold|holds|pin|pins|pinned|stick|sticks|travel|travels|slide|slides|swap|swaps|reveal|reveals|fade|fades|follow|follows|parallax|scroll|scrolls|play|plays|move|moves|expand|expands|type|types|set)\b/i.test(ref.signature)) {
      problems.push(`${ref.id}: signature "${ref.signature || ""}" does not say what the site DOES (no verb)`);
    }
  }

  // Read the build.
  const loaded = resolvePlaywright({ moduleUrl: import.meta.url });
  const executable = discoverBrowserExecutable(loaded.playwright, args.browserExecutable);
  const browser = await loaded.playwright.chromium.launch({ executablePath: executable.path });
  const buildPages = [];
  try {
    for (const [index, route] of (plan.routes || []).entries()) {
      for (const viewport of VIEWPORTS) {
        const record = await studyPage(browser, route.url, viewport, { frameDir, videoDir, prefix: `route${index + 1}-${viewport.name}`, videoSeconds: viewport.name === "wide" ? args.routeSeconds : 0, full: viewport.name === "wide" });
        record.role = "build"; record.route = route.name || route.url;
        buildPages.push(record);
        if (!record.ok) problems.push(`${route.name || route.url} (${viewport.name}) could not be read: ${record.problems.map((p) => p.message).join("; ")}`);
      }
    }
  } finally { await Promise.race([browser.close(), new Promise((r) => setTimeout(r, 15_000))]).catch(() => {}); }

  // Fonts: every real family in the build comes from a studied reference or a declared match.
  const referenceFamilies = new Set();
  for (const id of selected) for (const page of studies.get(id).pages) for (const f of realFamilies(page.design)) referenceFamilies.add(f);
  const declared = new Set((plan.typefaces || []).map((t) => norm(t.family)));
  const matched = new Set((plan.typefaces || []).filter((t) => t.matched_for).map((t) => norm(t.family)));
  for (const t of plan.typefaces || []) {
    const fam = norm(t.family);
    if (!referenceFamilies.has(fam) && !t.matched_for) problems.push(`typeface "${t.family}" is not computed by any selected reference and declares no matched_for`);
    if (t.matched_for && !referenceFamilies.has(norm(t.matched_for))) problems.push(`typeface "${t.family}" claims to match "${t.matched_for}", which no selected reference computes`);
  }
  if ((plan.typefaces || []).length > 2) problems.push(`plan declares ${(plan.typefaces || []).length} typefaces; the rule is at most two`);
  const buildFamilies = new Set();
  for (const page of buildPages) for (const f of realFamilies(page.design)) buildFamilies.add(f);
  for (const f of buildFamilies) {
    if (!declared.has(f)) problems.push(`the build sets text in "${f}", which the plan does not declare`);
    else if (!referenceFamilies.has(f) && !matched.has(f)) problems.push(`the build sets text in "${f}", which no selected reference computes`);
  }
  if (buildFamilies.size) passed.push(`fonts: ${[...buildFamilies].join(", ")}`);

  // Ground: the dominant painted ground of the build is a selected reference's dominant ground.
  const buildWide = buildPages.find((p) => p.role === "build" && p.viewport === "wide" && p.ok);
  const buildGround = buildWide?.design?.grounds?.[0]?.color;
  if (buildGround) {
    const referenceGrounds = selected.map((id) => ({ id, color: primary(studies.get(id))?.design?.grounds?.[0]?.color })).filter((g) => g.color);
    const near = referenceGrounds.filter((g) => colorDistance(g.color, buildGround) <= 24);
    if (!near.length) problems.push(`the build's dominant ground ${buildGround} is not the dominant ground of any selected reference (${referenceGrounds.map((g) => `${g.id} ${g.color}`).join("; ")})`);
    else passed.push(`ground ${buildGround} from ${near.map((g) => g.id).join(", ")}`);
    if (plan.ground?.color && colorDistance(plan.ground.color, buildGround) > 24) problems.push(`the plan's ground ${plan.ground.color} is not what the build paints (${buildGround})`);
  }

  // Mechanisms and signatures arrive in the build.
  const buildTypes = new Set(); for (const page of buildPages) for (const t of mechanismTypes(page)) buildTypes.add(t);
  const referenceTypes = new Set(); for (const id of selected) for (const page of studies.get(id).pages) for (const t of mechanismTypes(page)) referenceTypes.add(t);
  for (const ref of plan.references || []) {
    for (const type of ref.signature_mechanisms || []) if (!buildTypes.has(type)) problems.push(`${ref.id}'s signature mechanism "${type}" did not arrive in the build (build has: ${[...buildTypes].join(", ") || "none"})`);
  }
  for (const [index, route] of (plan.routes || []).entries()) {
    const pages = buildPages.filter((p) => p.route === (route.name || route.url) && p.ok);
    const types = new Set(); for (const p of pages) for (const t of mechanismTypes(p)) types.add(t);
    evidence.routes.push({ route: route.name || route.url, mechanisms: [...types], promised: route.mechanisms || [] });
    for (const type of route.mechanisms || []) {
      if (!types.has(type)) problems.push(`route ${route.name || route.url} promised "${type}" and does not have it (has: ${[...types].join(", ") || "none"})`);
      if (!referenceTypes.has(type)) problems.push(`route ${route.name || route.url} promised "${type}", which no selected reference has; that is the producer's own design`);
    }
    if (route.dominant && !studies.has(route.dominant)) problems.push(`route ${route.name || route.url} names dominant reference ${route.dominant}, which was not studied`);
  }

  // Motion floor: at least the weakest selected reference.
  const refDistinct = selected.map((id) => primary(studies.get(id))?.motion?.distinct_mechanisms ?? 0);
  const refCoverage = selected.map((id) => primary(studies.get(id))?.motion?.scroll_coverage ?? 0);
  if (buildWide?.motion && refDistinct.length) {
    const floorDistinct = Math.min(...refDistinct), floorCoverage = Math.min(...refCoverage);
    if (buildWide.motion.distinct_mechanisms < floorDistinct) problems.push(`the home route has ${buildWide.motion.distinct_mechanisms} distinct mechanisms; the weakest selected reference has ${floorDistinct}`);
    if (buildWide.motion.scroll_coverage < floorCoverage) problems.push(`the home route's scroll choreography covers ${Math.round(buildWide.motion.scroll_coverage * 100)}% of its depth; the weakest selected reference covers ${Math.round(floorCoverage * 100)}%`);
    else passed.push(`motion: ${buildWide.motion.distinct_mechanisms} mechanisms over ${Math.round(buildWide.motion.scroll_coverage * 100)}% of the depth`);
  }
  // Hover: references that respond to the pointer demand a build that does.
  const refHover = selected.map((id) => primary(studies.get(id))?.hover).filter(Boolean);
  if (buildWide?.hover && refHover.some((h) => h.responded > 0) && buildWide.hover.responded === 0 && buildWide.hover.probed > 0) {
    problems.push(`no probed control on the home route responds to the pointer; the selected references' controls do`);
  }

  // Slop: the patterns that read as generated.
  if (buildWide?.design) {
    const d = buildWide.design;
    const gradientText = (d.type_scale || []).some((t) => /^h[12]$|display/.test(t.role) && /transparent/.test(t.color || ""));
    if (gradientText || (d.grounds || []).some((g) => /gradient/.test(g.color) && g.area_share > 0.3)) problems.push("slop: gradient text or a gradient ground carries the page");
    const onlyReveal = buildTypes.size === 1 && buildTypes.has("reveal");
    if (onlyReveal) problems.push("slop: sections fading up on scroll are the only motion; that is the default every generated site ships");
    const pills = (d.controls || []).filter((c) => /px/.test(c.radius) && parseFloat(c.radius) >= 999 || /9999px|100px|50%/.test(c.radius || ""));
    if (d.controls?.length >= 6 && pills.length === d.controls.length && !referenceFamilies.size) problems.push("slop: every control is a pill");
    const sections = buildWide.layout?.sections || [];
    const triplet = sections.find((s) => /grid/.test(s.display) && /repeat\(3|1fr 1fr 1fr/.test(s.grid || "") && s.images === 0 && s.text_chars < 600 && s.top < 1400);
    if (triplet) problems.push(`slop: a three-column icon-card row near the top of the page (${triplet.tag}${triplet.class ? "." + triplet.class.split(" ")[0] : ""} at ${triplet.top}px)`);
  }

  const verdict = problems.length ? `CHECK FAIL ${problems.length} problem(s): ${problems.join(" | ")}` : `CHECK PASS ${passed.length + evidence.routes.length} checks (${passed.join("; ")})`;
  const report = { tool: TOOL, checked_at: new Date().toISOString(), verdict, problems, passed, evidence, build_pages: buildPages.map((p) => ({ route: p.route, viewport: p.viewport, ok: p.ok, first_screen: p.first_screen?.file, contact_sheet: p.contact_sheet?.file, mechanisms: p.motion?.mechanisms?.map((m) => m.type), fonts: p.design?.fonts, ground: p.design?.grounds?.[0] })) };
  fs.writeFileSync(path.join(outDir, "check.json"), JSON.stringify(report, null, 2) + "\n");
  process.stdout.write(verdict + "\n");
  process.exitCode = problems.length ? 1 : 0;
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url));
if (invokedDirectly) {
  main().catch((error) => { process.stdout.write(`CHECK FAIL ${error?.code || "check-failed"}: ${String(error?.message || error).slice(0, 400)}\n`); process.exitCode = 2; })
    .finally(() => { setTimeout(() => process.exit(process.exitCode ?? 0), 2000).unref(); });
}
