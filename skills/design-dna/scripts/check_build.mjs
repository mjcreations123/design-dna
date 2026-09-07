#!/usr/bin/env node
/**
 * check_build.mjs
 *
 * Reads the BUILT site with the same eyes as its references and compares it to
 * the plan. One command, a minute or two, two lines to quote verbatim:
 *
 *   CHECK PASS (automated) ... | CHECK FAIL (automated) ...   what the programs could measure
 *   REVIEW ...                                                  whether the producer's written visual review exists and what it leaves unresolved
 *
 *   node check_build.mjs --plan .design-dna/plan.json --studies .design-dna/references --out .design-dna/check
 *        [--review .design-dna/review.md] [--route-seconds 10] [--browser-executable FILE]
 *
 * plan.json (written by the AI before building, read here):
 * {
 *   "references": [ { "id": "strong-1", "url": "https://...", "source_id": "awwwards", "source": "awwwards; site of the day 2026-03-02",
 *                     "signature": "the product images slide sideways under a pinned heading",
 *                     "signature_mechanisms": ["pinned", "travel"], "take": ["first screen", "pinned heading with travelling media"] } ],
 *   "typefaces": [ { "family": "Fraunces", "from": "strong-1" },
 *                  { "family": "Instrument Serif", "from": "strong-2", "matched_for": "Cardinal Fruit", "match_record": ".design-dna/typeface-match.json" } ],
 *   "ground": { "color": "rgb(14, 14, 14)", "from": "strong-1" },
 *   "routes": [ { "url": "http://127.0.0.1:4870/", "name": "home", "dominant": "strong-1", "mechanisms": ["pinned", "travel", "reveal"],
 *                 "sections": [ { "selector": ".hero", "reference": "strong-1", "takes": "first-screen composition, nav, ring button" } ] } ]
 * }
 *
 * Automated checks (evidence in check.json):
 *   inputs       at least one route; at least four selected references, each studied ok at both widths, from at least two
 *                registry sources marked award or curated; signatures measured on their own reference and phrased as behavior;
 *   fonts        every family the build computes comes from a selected reference or a declared match whose match record ranks it first;
 *   ground       the dominant painted ground at each width is a selected reference's own;
 *   sections     every listed section exists, names a selected reference, and paints a ground that reference (or the route's dominant) paints;
 *   mechanisms   each reference's signature mechanisms and each route's promised mechanisms arrive; nothing promised that no reference has;
 *   both widths  motion floor, overflow and slop are read at desktop AND at phone width; a desktop pass never covers a phone failure;
 *   hover        if the references' controls respond to the pointer, the build's do;
 *   copy         no em dashes, no eyebrow label over a heading, no padded 01/02 numbers, no arrow on a thing that is not a link;
 *   images       no photograph used twice on a page;
 *   inner pages  a route beyond the first copies only a reference whose inner pages were studied;
 *   slop         no gradient ground carrying the page, no icon-card triplet near the top, no pill wall, no fade-up as the only motion.
 *
 * The visual review is the producer's, not the tool's. The tool writes review-<n>-<route>.png (reference beside build at both
 * widths, plus both scroll storyboards) and reports whether <plan dir>/review.md exists with a line per selected reference
 * and an "Unresolved" section. CHECK PASS means the automated checks passed for these routes and widths; it is not approval.
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { resolvePlaywright, discoverBrowserExecutable } from "./playwright_resolver.mjs";
import { studyPage } from "./study_reference.mjs";

const TOOL = "check_build.mjs";
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REGISTRY = path.join(HERE, "..", "references", "quality", "public-reference-sources.json");
const VIEWPORTS = [{ name: "wide", width: 1440, height: 900 }, { name: "narrow", width: 390, height: 844 }];
const GENERIC_FAMILIES = new Set(["serif", "sans-serif", "monospace", "system-ui", "ui-sans-serif", "ui-serif", "ui-monospace", "cursive", "fantasy", "-apple-system", "blinkmacsystemfont", "segoe ui", "roboto", "helvetica neue", "arial", "inherit"]);
const VERBS = /\b(hold|holds|held|pin|pins|pinned|stick|sticks|stays?|travel|travels|slide|slides|swap|swaps|reveal|reveals|fade|fades|follow|follows|parallax|scroll|scrolls|play|plays|move|moves|expand|expands|type|types|set|scatter|scatters|stagger|staggers|change|changes|rise|rises|sink|sinks|carry|carries|sit|sits|open|opens|close|closes|grow|grows|shrink|shrinks|appear|appears|dim|dims|underline|underlines|lift|lifts|drift|drifts|float|floats|snap|snaps|pass|passes|turn|turns|flip|flips|run|runs|animate|animates|respond|responds|react|reacts|transform|transforms|scale|scales|shift|shifts|repaint|repaints|spread|spreads|tilt|tilts|glide|glides|fill|fills|cover|covers|split|splits|stack|stacks)\b/i;

function parseArgs(argv) {
  const out = { plan: null, studies: null, outDir: null, review: null, routeSeconds: 10, browserExecutable: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--plan") out.plan = argv[++i];
    else if (a === "--studies") out.studies = argv[++i];
    else if (a === "--out") out.outDir = argv[++i];
    else if (a === "--review") out.review = argv[++i];
    else if (a === "--route-seconds") out.routeSeconds = Number(argv[++i]);
    else if (a === "--browser-executable") out.browserExecutable = argv[++i];
    else if (a === "--help" || a === "-h") { process.stdout.write(`usage: node ${TOOL} --plan FILE --studies DIR --out DIR [--review FILE] [--route-seconds S]\n`); process.exit(0); }
    else fail("invalid-argument", `Unknown argument ${a}.`);
  }
  if (!out.plan || !fs.existsSync(out.plan)) fail("plan-missing", "--plan must name an existing plan.json.");
  if (!out.studies || !fs.existsSync(out.studies)) fail("studies-missing", "--studies must name the directory holding <id>/study.json records.");
  if (!out.outDir) fail("invalid-out", "--out must name a directory.");
  if (!out.review) out.review = path.join(path.dirname(path.resolve(out.plan)), "review.md");
  return out;
}
function fail(code, message) {
  process.stdout.write(`CHECK FAIL (automated) ${code}: ${message}\nREVIEW not read: the check did not run\n`);
  process.exit(2);
}
const norm = (family) => String(family || "").replace(/["']/g, "").trim().toLowerCase();
const stem = (family) => norm(family).split(",")[0].trim();
const keyOf = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
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
function loadRegistry() {
  try {
    const reg = JSON.parse(fs.readFileSync(REGISTRY, "utf8"));
    const byKey = new Map();
    for (const src of reg.sources || []) { byKey.set(keyOf(src.id), src); byKey.set(keyOf(src.name), src); }
    return byKey;
  } catch { return new Map(); }
}
const primary = (study, viewport = "wide") => study.pages.find((p) => p.role === "primary" && p.viewport === viewport);
const mechanismTypes = (page) => new Set((page?.motion?.mechanisms || []).map((m) => m.type));
const realFamilies = (design) => (design?.fonts || []).map((f) => norm(f.family)).filter((f) => f && !GENERIC_FAMILIES.has(f));
const allGrounds = (study) => { const out = []; for (const p of study.pages || []) for (const g of p.design?.grounds || []) if (rgb(g.color)) out.push(g.color); return out; };
const resolveFrom = (base, file) => { if (path.isAbsolute(file)) return file; const fromCwd = path.resolve(file); if (fs.existsSync(fromCwd)) return fromCwd; return path.resolve(path.dirname(path.resolve(base)), file); };
const dataUri = (file) => (file && fs.existsSync(file) ? `data:image/png;base64,${fs.readFileSync(file).toString("base64")}` : null);

/* Runs in the built page: overflow, the listed sections, copy tells, duplicate photographs. */
const PROBE = `((sections) => {
  const vw = innerWidth;
  const out = { overflow: { scroll_width: document.documentElement.scrollWidth, viewport: vw, overflows: document.documentElement.scrollWidth > vw + 1 },
    sections: [], copy: { em_dashes: [], eyebrows: [], padded_numbers: [], stray_arrows: [] }, duplicate_images: [] };
  const transparent = (bg) => !bg || bg === 'transparent' || /rgba\\(\\s*\\d+,\\s*\\d+,\\s*\\d+,\\s*0\\s*\\)/.test(bg);
  const paintedGround = (el) => { let n = el; while (n && n !== document.documentElement) { const bg = getComputedStyle(n).backgroundColor; if (!transparent(bg)) return bg; n = n.parentElement; } return getComputedStyle(document.body).backgroundColor; };
  const snippet = (t) => String(t).replace(/\\s+/g, ' ').trim().slice(0, 80);
  for (const s of sections) {
    let nodes = []; try { nodes = document.querySelectorAll(s.selector); } catch (e) { out.sections.push({ selector: s.selector, reference: s.reference, count: -1, error: 'invalid selector' }); continue; }
    const el = nodes[0];
    const fonts = el ? [...new Set([el, ...el.querySelectorAll('h1,h2,h3,h4,p,a,li,span,figcaption,blockquote')].slice(0, 120).map((n) => getComputedStyle(n).fontFamily.split(',')[0].replace(/["']/g, '').trim().toLowerCase()))] : [];
    out.sections.push({ selector: s.selector, reference: s.reference, count: nodes.length, ground: el ? paintedGround(el) : null, fonts, height: el ? Math.round(el.getBoundingClientRect().height) : 0 });
  }
  const skip = /^(SCRIPT|STYLE|NOSCRIPT|CODE|PRE|TEMPLATE|TITLE)$/;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const t = node.textContent; if (!t || !t.trim()) continue;
    const el = node.parentElement; if (!el || skip.test(el.tagName)) continue;
    const cs = getComputedStyle(el); if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    if (t.includes('\\u2014') && out.copy.em_dashes.length < 5) out.copy.em_dashes.push(snippet(t));
    if (/^\\s*0\\d\\s*$/.test(t) && out.copy.padded_numbers.length < 5) out.copy.padded_numbers.push(snippet(t));
    if (/[\\u2192\\u2190\\u2197\\u2198\\u21d2]|->/.test(t) && !el.closest('a,button,[role=button],summary') && out.copy.stray_arrows.length < 5) out.copy.stray_arrows.push(snippet(t));
  }
  for (const h of document.querySelectorAll('h1,h2,h3')) {
    const prev = h.previousElementSibling; if (!prev) continue;
    const txt = (prev.textContent || '').trim(); if (!txt || txt.length > 40 || prev.querySelector('h1,h2,h3,img,a,button')) continue;
    const cs = getComputedStyle(prev);
    const caps = cs.textTransform === 'uppercase' || (txt === txt.toUpperCase() && /[A-Z]/.test(txt));
    if (caps && parseFloat(cs.fontSize) <= 15 && out.copy.eyebrows.length < 5) out.copy.eyebrows.push(snippet(txt) + ' > ' + snippet(h.textContent));
  }
  const seen = new Map();
  for (const img of document.querySelectorAll('img')) {
    const src = img.currentSrc || img.src || ''; if (!src) continue;
    const r = img.getBoundingClientRect(); if (r.width < 40 || r.height < 40) continue;
    const key = src.length > 200 ? src.slice(0, 160) + '#' + src.length : src;
    seen.set(key, (seen.get(key) || 0) + 1);
  }
  for (const [k, c] of seen) if (c > 1) out.duplicate_images.push({ src: k.slice(0, 90), uses: c });
  return out;
})`;

async function probeRoute(browser, url, viewport, sections) {
  const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  try {
    await page.goto(url, { waitUntil: "load", timeout: 60_000 });
    await new Promise((r) => setTimeout(r, 1500));
    return await page.evaluate(`${PROBE}(${JSON.stringify(sections || [])})`);
  } finally { await page.close().catch(() => {}); await context.close().catch(() => {}); }
}

/* Reference beside build, both widths, both storyboards: one image the producer must look at. */
async function reviewSheet(browser, file, title, refDir, refStudy, buildWide, buildNarrow, frameDir) {
  const refWide = primary(refStudy, "wide"), refNarrow = primary(refStudy, "narrow");
  const img = (src, cap) => (src ? `<figure><img src="${src}"><figcaption>${cap}</figcaption></figure>` : `<figure><div class="missing">${cap}: missing</div></figure>`);
  const strip = (frames) => (frames || []).slice(0, 8).map((f) => dataUri(path.join(frameDir, f.file || f))).filter(Boolean).map((d) => `<img src="${d}">`).join("");
  const html = `<!doctype html><meta charset="utf-8"><style>
    body{margin:0;background:#151515;color:#eee;font:14px/1.4 system-ui,sans-serif;padding:16px;width:1888px}
    h1{font-size:18px;margin:0 0 12px} h2{font-size:14px;margin:18px 0 8px;color:#bbb;font-weight:400}
    .row{display:grid;grid-template-columns:1fr 1fr;gap:16px} figure{margin:0} figure img{width:100%;display:block;border:1px solid #333}
    figcaption{margin-top:6px;color:#bbb} .narrow figure img{width:390px}
    .strip{display:grid;grid-template-columns:repeat(8,1fr);gap:6px} .strip img{width:100%;border:1px solid #333} .missing{padding:24px;border:1px dashed #555;color:#999}
  </style><h1>${title}</h1>
  <h2>First screen, wide: reference (left) beside build (right)</h2>
  <div class="row">${img(dataUri(path.join(refDir, "frames", refWide?.first_screen?.file || "")), `${refStudy.url}`)}${img(dataUri(path.join(frameDir, buildWide?.first_screen?.file || "")), "build")}</div>
  <h2>First screen, narrow: reference (left) beside build (right)</h2>
  <div class="row narrow">${img(dataUri(path.join(refDir, "frames", refNarrow?.first_screen?.file || "")), `${refStudy.url}`)}${img(dataUri(path.join(frameDir, buildNarrow?.first_screen?.file || "")), "build")}</div>
  <h2>Scroll storyboard: reference</h2>
  ${img(dataUri(path.join(refDir, refWide?.contact_sheet?.file || "")), "reference wide scroll-through")}
  <h2>Scroll storyboard: build (frames from the check's own scroll-through)</h2>
  <div class="strip">${strip(buildWide?.frames)}</div>`;
  const context = await browser.newContext({ viewport: { width: 1920, height: 1200 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  try {
    await page.setContent(html, { waitUntil: "load" });
    await page.screenshot({ path: file, fullPage: true });
  } finally { await page.close().catch(() => {}); await context.close().catch(() => {}); }
}

function readReview(file, selected) {
  if (!fs.existsSync(file)) return { written: false, line: `REVIEW MISSING: ${file} does not exist; write it after looking at review-*.png (one "- <reference id>: reference shows ... / build shows ... / difference ..." line per selected reference, then "## Unresolved")` };
  const text = fs.readFileSync(file, "utf8");
  const covered = selected.filter((id) => new RegExp(`^\\s*[-*]\\s*${id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*:`, "mi").test(text));
  const missing = selected.filter((id) => !covered.includes(id));
  const unresolvedBlock = text.split(/^##\s*Unresolved[^\n]*$/im)[1] || null;
  const unresolved = unresolvedBlock ? unresolvedBlock.split(/^##\s/m)[0].split("\n").filter((l) => /^\s*[-*]\s+\S/.test(l)).length : null;
  const parts = [`REVIEW WRITTEN: ${file}; ${covered.length} of ${selected.length} selected references compared`];
  if (missing.length) parts.push(`missing: ${missing.join(", ")}`);
  parts.push(unresolved === null ? "no \"## Unresolved\" section (write one, even if it says none)" : `${unresolved} unresolved difference(s) listed`);
  parts.push("this is the producer's own comparison, not approval");
  return { written: true, covered, missing, unresolved, line: parts.join("; ") };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const plan = JSON.parse(fs.readFileSync(args.plan, "utf8"));
  const studies = loadStudies(args.studies);
  const registry = loadRegistry();
  const outDir = path.resolve(args.outDir);
  const frameDir = path.join(outDir, "frames"), videoDir = path.join(outDir, "videos");
  fs.mkdirSync(frameDir, { recursive: true }); fs.mkdirSync(videoDir, { recursive: true });
  const problems = [], passed = [];
  const evidence = { plan: args.plan, studies: [...studies.keys()], routes: [], sources: [], sections: [], probes: [] };

  // ---- inputs
  if (!(plan.routes || []).length) problems.push("the plan names no build route");
  for (const ref of plan.references || []) {
    if (!studies.has(ref.id)) problems.push(`plan cites reference ${ref.id} but ${args.studies}/${ref.id}/study.json does not exist`);
  }
  const selected = [...new Set((plan.references || []).map((r) => r.id).filter((id) => studies.has(id)))];
  if (selected.length < 4) problems.push(`plan selects ${selected.length} distinct studied references; the owner's floor is four`);
  for (const id of selected) {
    const study = studies.get(id);
    for (const vp of ["wide", "narrow"]) {
      const p = primary(study, vp);
      if (!p?.ok) problems.push(`${id}: the ${vp} study did not succeed (${(p?.problems || []).map((x) => x.message).join("; ") || "no record"}); a reference the tool could not read at this width is not selected`);
    }
    if ((study.problems || []).some((p) => /^http-4|^http-5/.test(p.code || ""))) problems.push(`${id}: the study hit an HTTP error page`);
  }
  const sourceKeys = new Map();
  for (const ref of plan.references || []) {
    if (!studies.has(ref.id)) continue;
    const key = keyOf(ref.source_id || String(ref.source || "").split(/[;,(:]/)[0]);
    const src = registry.get(key);
    evidence.sources.push({ id: ref.id, key, registry: src?.id || null, curation: src?.curation || null });
    if (!key) problems.push(`${ref.id}: no source_id; name the registry source that lists this site`);
    else if (!src) problems.push(`${ref.id}: source "${ref.source_id || ref.source}" is not in the public-reference registry`);
    else if (!/^(award|curated)$/i.test(src.curation || "")) problems.push(`${ref.id}: source ${src.id} is a submission feed (${src.curation}); it cannot supply a selected reference`);
    else if (src.status && src.status !== "active") problems.push(`${ref.id}: source ${src.id} is ${src.status} in the registry`);
    else sourceKeys.set(src.id, (sourceKeys.get(src.id) || 0) + 1);
  }
  if (selected.length && sourceKeys.size < 2) problems.push(`selected references come from ${sourceKeys.size} registry source(s) (${[...sourceKeys.keys()].join(", ") || "none"}); the floor is two`);
  else if (sourceKeys.size) passed.push(`sources: ${[...sourceKeys.keys()].join(", ")}`);

  // ---- signatures measured on their own reference, phrased as behavior
  for (const ref of plan.references || []) {
    const study = studies.get(ref.id); if (!study) continue;
    const detected = new Set([...mechanismTypes(primary(study, "wide")), ...mechanismTypes(primary(study, "narrow"))]);
    for (const type of ref.signature_mechanisms || []) {
      if (!detected.has(type)) problems.push(`${ref.id}: signature mechanism "${type}" was not detected on that site (detected: ${[...detected].join(", ") || "none"})`);
    }
    if (!ref.signature || !VERBS.test(ref.signature)) problems.push(`${ref.id}: signature "${ref.signature || ""}" does not say what the site DOES (no verb)`);
  }

  // ---- read the build at both widths
  const loaded = resolvePlaywright({ moduleUrl: import.meta.url });
  const executable = discoverBrowserExecutable(loaded.playwright, args.browserExecutable);
  const browser = await loaded.playwright.chromium.launch({ executablePath: executable.path });
  const buildPages = [];
  const probes = [];
  try {
    for (const [index, route] of (plan.routes || []).entries()) {
      const routeName = route.name || route.url;
      for (const viewport of VIEWPORTS) {
        const record = await studyPage(browser, route.url, viewport, { frameDir, videoDir, prefix: `route${index + 1}-${viewport.name}`, videoSeconds: viewport.name === "wide" ? args.routeSeconds : 0, full: viewport.name === "wide" });
        record.role = "build"; record.route = routeName;
        buildPages.push(record);
        if (!record.ok) problems.push(`${routeName} (${viewport.name}) could not be read: ${record.problems.map((p) => p.message).join("; ")}`);
        try {
          const probe = await probeRoute(browser, route.url, viewport, route.sections || []);
          probes.push({ route: routeName, viewport: viewport.name, ...probe });
        } catch (error) { problems.push(`${routeName} (${viewport.name}) probe failed: ${String(error?.message || error).slice(0, 160)}`); }
      }
      // The review sheet: dominant reference beside the build.
      const dom = route.dominant && studies.get(route.dominant);
      if (dom) {
        const file = path.join(outDir, `review-${index + 1}-${String(routeName).replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.png`);
        try {
          await reviewSheet(browser, file, `${routeName}: ${route.dominant} (reference) beside the build`, path.join(path.resolve(args.studies), route.dominant), dom,
            buildPages.find((p) => p.route === routeName && p.viewport === "wide"), buildPages.find((p) => p.route === routeName && p.viewport === "narrow"), frameDir);
          evidence.routes.push({ route: routeName, review_sheet: path.basename(file) });
        } catch (error) { problems.push(`${routeName}: review sheet could not be rendered: ${String(error?.message || error).slice(0, 160)}`); }
      }
    }
  } finally { await Promise.race([browser.close(), new Promise((r) => setTimeout(r, 15_000))]).catch(() => {}); }
  evidence.probes = probes;

  // ---- fonts
  const referenceFamilies = new Set();
  for (const id of selected) for (const page of studies.get(id).pages) for (const f of realFamilies(page.design)) referenceFamilies.add(f);
  const declared = new Set((plan.typefaces || []).map((t) => norm(t.family)));
  const matched = new Set();
  for (const t of plan.typefaces || []) {
    const fam = norm(t.family);
    if (!referenceFamilies.has(fam) && !t.matched_for) problems.push(`typeface "${t.family}" is not computed by any selected reference and declares no matched_for`);
    if (t.matched_for) {
      if (!referenceFamilies.has(norm(t.matched_for))) problems.push(`typeface "${t.family}" claims to match "${t.matched_for}", which no selected reference computes`);
      if (!t.match_record) problems.push(`typeface "${t.family}" claims to match "${t.matched_for}" but names no match_record; a typed claim is not a match`);
      else {
        const file = resolveFrom(args.plan, t.match_record);
        let rec = null;
        try { rec = JSON.parse(fs.readFileSync(file, "utf8")); } catch { problems.push(`typeface "${t.family}": match_record ${t.match_record} cannot be read`); }
        if (rec) {
          const hit = (rec.results || []).find((r) => stem(r.target?.family) === stem(t.matched_for));
          if (rec.tool !== "match_typeface.mjs") problems.push(`typeface "${t.family}": ${t.match_record} was not written by match_typeface.mjs`);
          else if (!hit) problems.push(`typeface "${t.family}": ${t.match_record} has no result for target "${t.matched_for}"`);
          else if (stem(hit.chosen?.family) !== fam) problems.push(`typeface "${t.family}" is not the rank-one match for "${t.matched_for}"; the record chose "${hit.chosen?.family || "nothing"}"`);
          else if (!rec.verified_browser_measurement) problems.push(`typeface "${t.family}": the match record's candidates were not measured in the browser (verified_browser_measurement is false)`);
          else { matched.add(fam); passed.push(`match: ${t.family} ranks first for ${t.matched_for} (delta ${hit.chosen.delta})`); }
        }
      }
    }
  }
  if ((plan.typefaces || []).length > 2) problems.push(`plan declares ${(plan.typefaces || []).length} typefaces; the rule is at most two`);
  const buildFamilies = new Set();
  for (const page of buildPages) for (const f of realFamilies(page.design)) buildFamilies.add(f);
  for (const f of buildFamilies) {
    if (!declared.has(f)) problems.push(`the build sets text in "${f}", which the plan does not declare`);
    else if (!referenceFamilies.has(f) && !matched.has(f)) problems.push(`the build sets text in "${f}", which no selected reference computes and no verified match record ranks first`);
  }
  if (buildFamilies.size) passed.push(`fonts: ${[...buildFamilies].join(", ")}`);

  // ---- ground at both widths
  const referenceDominant = selected.map((id) => ({ id, color: primary(studies.get(id))?.design?.grounds?.[0]?.color })).filter((g) => g.color);
  const referenceAnyGround = new Map(selected.map((id) => [id, allGrounds(studies.get(id))]));
  for (const viewport of VIEWPORTS) {
    for (const route of plan.routes || []) {
      const routeName = route.name || route.url;
      const page = buildPages.find((p) => p.route === routeName && p.viewport === viewport.name && p.ok);
      const g = page?.design?.grounds?.[0]?.color; if (!g) continue;
      if (viewport.name === "wide") {
        const near = referenceDominant.filter((r) => colorDistance(r.color, g) <= 24);
        if (!near.length) problems.push(`${routeName} (wide): dominant ground ${g} is not the dominant ground of any selected reference (${referenceDominant.map((r) => `${r.id} ${r.color}`).join("; ")})`);
        else passed.push(`ground ${g} from ${near.map((r) => r.id).join(", ")}`);
        if (plan.ground?.color && colorDistance(plan.ground.color, g) > 24) problems.push(`the plan's ground ${plan.ground.color} is not what ${routeName} paints (${g})`);
      } else {
        const ok = [...referenceAnyGround.values()].some((list) => list.some((c) => colorDistance(c, g) <= 24));
        if (!ok) problems.push(`${routeName} (narrow): dominant ground ${g} is not a ground any selected reference paints`);
      }
    }
  }

  // ---- mechanisms and signatures
  const buildTypesByViewport = { wide: new Set(), narrow: new Set() };
  for (const page of buildPages) for (const t of mechanismTypes(page)) buildTypesByViewport[page.viewport]?.add(t);
  const buildTypes = new Set([...buildTypesByViewport.wide, ...buildTypesByViewport.narrow]);
  const referenceTypes = new Set(); for (const id of selected) for (const page of studies.get(id).pages) for (const t of mechanismTypes(page)) referenceTypes.add(t);
  for (const ref of plan.references || []) {
    for (const type of ref.signature_mechanisms || []) if (!buildTypes.has(type)) problems.push(`${ref.id}'s signature mechanism "${type}" did not arrive in the build (build has: ${[...buildTypes].join(", ") || "none"})`);
  }
  for (const [index, route] of (plan.routes || []).entries()) {
    const routeName = route.name || route.url;
    const pages = buildPages.filter((p) => p.route === routeName && p.ok);
    const types = new Set(); for (const p of pages) for (const t of mechanismTypes(p)) types.add(t);
    let row = evidence.routes.find((r) => r.route === routeName);
    if (!row) { row = { route: routeName }; evidence.routes.push(row); }
    Object.assign(row, { mechanisms: [...types], promised: route.mechanisms || [], wide: [...mechanismTypes(pages.find((p) => p.viewport === "wide"))], narrow: [...mechanismTypes(pages.find((p) => p.viewport === "narrow"))] });
    for (const type of route.mechanisms || []) {
      if (!types.has(type)) problems.push(`route ${routeName} promised "${type}" and does not have it (has: ${[...types].join(", ") || "none"})`);
      if (!referenceTypes.has(type)) problems.push(`route ${routeName} promised "${type}", which no selected reference has; that is the producer's own design`);
    }
    if (route.dominant && !studies.has(route.dominant)) problems.push(`route ${routeName} names dominant reference ${route.dominant}, which was not studied`);
    if (index > 0 && route.dominant && studies.has(route.dominant)) {
      const innerOk = (studies.get(route.dominant).pages || []).filter((p) => p.role === "inner" && p.ok).length;
      if (!innerOk) problems.push(`route ${routeName} copies ${route.dominant}, whose inner pages were never studied; an inner route copies only a reference with studied inner pages`);
    }
  }

  // ---- motion floor at both widths: the weakest selected reference at the SAME width
  for (const viewport of VIEWPORTS) {
    const refDistinct = selected.map((id) => primary(studies.get(id), viewport.name)?.motion?.distinct_mechanisms ?? 0);
    const refCoverage = selected.map((id) => primary(studies.get(id), viewport.name)?.motion?.scroll_coverage ?? 0);
    for (const route of plan.routes || []) {
      const routeName = route.name || route.url;
      const page = buildPages.find((p) => p.route === routeName && p.viewport === viewport.name && p.ok);
      if (!page?.motion || !refDistinct.length) continue;
      const floorDistinct = Math.min(...refDistinct), floorCoverage = Math.min(...refCoverage);
      if (page.motion.distinct_mechanisms < floorDistinct) problems.push(`${routeName} (${viewport.name}) has ${page.motion.distinct_mechanisms} distinct mechanisms; the weakest selected reference has ${floorDistinct} at this width`);
      if (page.motion.scroll_coverage < floorCoverage) problems.push(`${routeName} (${viewport.name}): scroll choreography covers ${Math.round(page.motion.scroll_coverage * 100)}% of the depth; the weakest selected reference covers ${Math.round(floorCoverage * 100)}% at this width`);
      else passed.push(`motion ${viewport.name}: ${page.motion.distinct_mechanisms} mechanisms over ${Math.round(page.motion.scroll_coverage * 100)}%`);
    }
  }

  // ---- hover (wide only; a phone has no pointer)
  const refHover = selected.map((id) => primary(studies.get(id))?.hover).filter(Boolean);
  for (const route of plan.routes || []) {
    const routeName = route.name || route.url;
    const page = buildPages.find((p) => p.route === routeName && p.viewport === "wide" && p.ok);
    if (page?.hover && refHover.some((h) => h.responded > 0) && page.hover.responded === 0 && page.hover.probed > 0) {
      problems.push(`${routeName}: no probed control responds to the pointer; the selected references' controls do`);
    }
  }

  // ---- probes: overflow, sections, copy, duplicate images (both widths)
  for (const probe of probes) {
    const where = `${probe.route} (${probe.viewport})`;
    if (probe.overflow?.overflows) problems.push(`${where}: the page scrolls sideways (${probe.overflow.scroll_width}px wide in a ${probe.overflow.viewport}px viewport)`);
    for (const s of probe.sections || []) {
      evidence.sections.push({ ...s, route: probe.route, viewport: probe.viewport });
      if (s.count === -1) { problems.push(`${where}: section selector "${s.selector}" is invalid`); continue; }
      if (s.count === 0) { problems.push(`${where}: section "${s.selector}" is not in the page`); continue; }
      if (!s.reference || !selected.includes(s.reference)) { problems.push(`${where}: section "${s.selector}" names reference "${s.reference}", which is not a selected reference`); continue; }
      const route = (plan.routes || []).find((r) => (r.name || r.url) === probe.route);
      const palette = [...(referenceAnyGround.get(s.reference) || []), ...(route?.dominant ? referenceAnyGround.get(route.dominant) || [] : [])];
      if (s.ground && rgb(s.ground) && palette.length && !palette.some((c) => colorDistance(c, s.ground) <= 24)) {
        problems.push(`${where}: section "${s.selector}" paints ${s.ground}, a ground neither ${s.reference} nor the route's dominant reference paints`);
      }
      const foreign = (s.fonts || []).filter((f) => f && !GENERIC_FAMILIES.has(f) && !declared.has(f));
      if (foreign.length) problems.push(`${where}: section "${s.selector}" sets text in ${foreign.join(", ")}, not declared in the plan`);
    }
    const c = probe.copy || {};
    if (c.em_dashes?.length) problems.push(`${where}: copy uses an em dash (${c.em_dashes.slice(0, 2).map((x) => `"${x}"`).join("; ")})`);
    if (c.eyebrows?.length) problems.push(`${where}: an eyebrow label sits above a heading (${c.eyebrows.slice(0, 2).join("; ")})`);
    if (c.padded_numbers?.length) problems.push(`${where}: decorative padded numbers (${c.padded_numbers.slice(0, 3).join(", ")})`);
    if (c.stray_arrows?.length) problems.push(`${where}: an arrow on something that is not a link (${c.stray_arrows.slice(0, 2).map((x) => `"${x}"`).join("; ")})`);
    if (probe.duplicate_images?.length) problems.push(`${where}: a photograph is used more than once (${probe.duplicate_images.slice(0, 3).map((d) => `${d.uses}x ${d.src.slice(0, 40)}`).join("; ")})`);
  }
  if (probes.length) {
    const routesWithSections = (plan.routes || []).filter((r) => (r.sections || []).length);
    if (routesWithSections.length < (plan.routes || []).length) problems.push(`every route needs a sections list (selector, reference, takes); ${(plan.routes || []).length - routesWithSections.length} route(s) have none`);
    else passed.push(`sections: ${probes.filter((p) => p.viewport === "wide").reduce((n, p) => n + (p.sections || []).filter((s) => s.count > 0).length, 0)} listed and present`);
  }

  // ---- slop at both widths
  for (const page of buildPages.filter((p) => p.ok && p.design)) {
    const where = `${page.route} (${page.viewport})`;
    const d = page.design;
    const gradientText = (d.type_scale || []).some((t) => /^h[12]$|display/.test(t.role) && /transparent/.test(t.color || ""));
    if (gradientText || (d.grounds || []).some((g) => /gradient/.test(g.color) && g.area_share > 0.3)) problems.push(`${where}: slop: gradient text or a gradient ground carries the page`);
    const types = buildTypesByViewport[page.viewport];
    if (types.size === 1 && types.has("reveal")) problems.push(`${where}: slop: sections fading up on scroll are the only motion; that is the default every generated site ships`);
    const pills = (d.controls || []).filter((c) => /px/.test(c.radius) && parseFloat(c.radius) >= 999 || /9999px|100px|50%/.test(c.radius || ""));
    if (d.controls?.length >= 6 && pills.length === d.controls.length && !referenceFamilies.size) problems.push(`${where}: slop: every control is a pill`);
    const sections = page.layout?.sections || [];
    const triplet = sections.find((s) => /grid/.test(s.display) && /repeat\(3|1fr 1fr 1fr/.test(s.grid || "") && s.images === 0 && s.text_chars < 600 && s.top < 1400);
    if (triplet) problems.push(`${where}: slop: a three-column icon-card row near the top of the page (${triplet.tag}${triplet.class ? "." + triplet.class.split(" ")[0] : ""} at ${triplet.top}px)`);
  }

  // ---- verdict and review
  const routeCount = (plan.routes || []).length;
  const verdict = problems.length
    ? `CHECK FAIL (automated) ${problems.length} problem(s): ${problems.join(" | ")}`
    : `CHECK PASS (automated): ${passed.length} checks over ${routeCount} route(s) x 2 widths (${passed.join("; ")}); automated checks only, not a review or an approval`;
  const review = readReview(path.resolve(args.review), selected);
  const report = { tool: TOOL, checked_at: new Date().toISOString(), verdict, review: review.line, problems, passed, evidence,
    build_pages: buildPages.map((p) => ({ route: p.route, viewport: p.viewport, ok: p.ok, status: p.status ?? null, first_screen: p.first_screen?.file, mechanisms: p.motion?.mechanisms?.map((m) => m.type), fonts: p.design?.fonts, ground: p.design?.grounds?.[0], overflow_x: p.layout?.overflow_x || null })) };
  fs.writeFileSync(path.join(outDir, "check.json"), JSON.stringify(report, null, 2) + "\n");
  process.stdout.write(verdict + "\n" + review.line + "\n");
  process.exitCode = problems.length ? 1 : 0;
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url));
if (invokedDirectly) {
  main().catch((error) => { process.stdout.write(`CHECK FAIL (automated) ${error?.code || "check-failed"}: ${String(error?.message || error).slice(0, 400)}\nREVIEW not read: the check did not run\n`); process.exitCode = 2; })
    .finally(() => { setTimeout(() => process.exit(process.exitCode ?? 0), 2000).unref(); });
}
