#!/usr/bin/env node
/**
 * check_build.mjs (13.3.0)
 *
 * Reads the BUILT site with the same eyes as its references and compares it to
 * the plan. A minute or two. It prints five lines, each quoted verbatim in the
 * report, and each meaning exactly what it says:
 *
 *   CHECK PASS (automated) ... | CHECK FAIL (automated) ...  the measurable comparisons passed or did not
 *   FUNCTIONAL PASS ... | FUNCTIONAL FAIL ...                 keyboard focus, reduced motion, overlays at rest, sideways scroll
 *   REVIEW SELF-REVIEW ... | REVIEW INDEPENDENT ... | REVIEW MISSING ...   who looked, and what they left unresolved
 *   EVIDENCE ...                                              which tool revisions made the studies and this check
 *   APPROVAL ...                                              owner approval, recorded or not
 *
 * No line claims the site is good. The measurements prove provenance and catch
 * known failure shapes; the visitor's experience is judged by eyes.
 *
 *   node check_build.mjs --plan .design-dna/plan.json --studies .design-dna/references --out .design-dna/check
 *        [--review .design-dna/review.md] [--route-seconds 10] [--early] [--browser-executable FILE]
 *
 *   --early   before building the whole site: reads only the first route, renders the review sheet
 *             (reference beside build at both widths) and stops. Look at it, then build the rest.
 *
 * plan.json, the fields this check reads (see SKILL.md for the meaning of each):
 *   references[]  id, url, source_id, source_url, quality{desktop,mobile,readability,navigation,reliability,suitability},
 *                 contributes, signature, signature_mechanisms, gaps_reviewed (required when the study recorded gaps)
 *   typefaces[]   family, from, matched_for + match_record (a typed matched_for alone never passes)
 *   ground        color, from
 *   routes[]      url, name, dominant, sections[]{selector, reference, content, composition, image_role,
 *                 typography_role, behavior, mobile, behavior_narrow?, states?, palette_from?}
 *   review        { reviewer: "self" | "independent", file }
 *   approval      { by, date } when the owner has approved; absent otherwise
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { resolvePlaywright, discoverBrowserExecutable } from "./playwright_resolver.mjs";
import { studyPage } from "./study_reference.mjs";

const TOOL = "check_build.mjs";
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REGISTRY = path.join(HERE, "..", "references", "quality", "public-reference-sources.json");
const VIEWPORTS = [{ name: "wide", width: 1440, height: 900 }, { name: "narrow", width: 390, height: 844 }];
const GENERIC_FAMILIES = new Set(["serif", "sans-serif", "monospace", "system-ui", "ui-sans-serif", "ui-serif", "ui-monospace", "cursive", "fantasy", "-apple-system", "blinkmacsystemfont", "segoe ui", "roboto", "helvetica neue", "arial", "inherit"]);
const MECHANISM_WORDS = ["pinned", "parallax", "reveal", "swap", "travel", "pointer-follow", "hover"];
const VERBS = /\b(hold|holds|held|pin|pins|pinned|stick|sticks|stays?|travel|travels|slide|slides|swap|swaps|reveal|reveals|fade|fades|follow|follows|parallax|scroll|scrolls|play|plays|move|moves|expand|expands|type|types|set|scatter|scatters|stagger|staggers|change|changes|rise|rises|sink|sinks|carry|carries|sit|sits|open|opens|close|closes|grow|grows|shrink|shrinks|appear|appears|dim|dims|underline|underlines|lift|lifts|drift|drifts|float|floats|snap|snaps|pass|passes|turn|turns|flip|flips|run|runs|animate|animates|respond|responds|react|reacts|transform|transforms|scale|scales|shift|shifts|repaint|repaints|spread|spreads|tilt|tilts|glide|glides|fill|fills|cover|covers|split|splits|stack|stacks|give|gives|yield|yields)\b/i;
const QUALITY_FIELDS = ["desktop", "mobile", "readability", "navigation", "reliability", "suitability"];
const SECTION_FIELDS = ["content", "composition", "image_role", "typography_role", "behavior", "mobile"];
const CATEGORY_ORDER = ["design", "content", "selection", "evidence", "plan", "sources"];
const sha = (buf) => createHash("sha256").update(buf).digest("hex");
const SELF_SHA = sha(fs.readFileSync(fileURLToPath(import.meta.url)));
const STUDY_SHA = sha(fs.readFileSync(path.join(HERE, "study_reference.mjs")));

function parseArgs(argv) {
  const out = { plan: null, studies: null, outDir: null, review: null, routeSeconds: 10, early: false, browserExecutable: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--plan") out.plan = argv[++i];
    else if (a === "--studies") out.studies = argv[++i];
    else if (a === "--out") out.outDir = argv[++i];
    else if (a === "--review") out.review = argv[++i];
    else if (a === "--route-seconds") out.routeSeconds = Number(argv[++i]);
    else if (a === "--early") out.early = true;
    else if (a === "--browser-executable") out.browserExecutable = argv[++i];
    else if (a === "--help" || a === "-h") { process.stdout.write(`usage: node ${TOOL} --plan FILE --studies DIR --out DIR [--review FILE] [--route-seconds S] [--early]\n`); process.exit(0); }
    else fail("invalid-argument", `Unknown argument ${a}.`);
  }
  if (!out.plan || !fs.existsSync(out.plan)) fail("plan-missing", "--plan must name an existing plan.json.");
  if (!out.studies || !fs.existsSync(out.studies)) fail("studies-missing", "--studies must name the directory holding <id>/study.json records.");
  if (!out.outDir) fail("invalid-out", "--out must name a directory.");
  return out;
}
function fail(code, message) {
  process.stdout.write(`CHECK FAIL (automated) ${code}: ${message}\nFUNCTIONAL not run\nREVIEW not read: the check did not run\nEVIDENCE none\nAPPROVAL not recorded\n`);
  process.exit(2);
}
const norm = (family) => String(family || "").replace(/["']/g, "").trim().toLowerCase();
const stem = (family) => norm(family).split(",")[0].trim();
const keyOf = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
const hostOf = (url) => { try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return null; } };
const rgb = (color) => {
  const m = String(color || "").match(/rgba?\(([^)]+)\)/); if (!m) return null;
  const [r, g, b, a] = m[1].split(",").map((x) => parseFloat(x));
  return a === 0 ? null : [r, g, b];
};
const colorDistance = (a, b) => { const x = rgb(a), y = rgb(b); if (!x || !y) return Infinity; return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]); };
const words = (s) => String(s || "").trim().split(/\s+/).filter(Boolean);
const mechanismsIn = (text) => { const t = String(Array.isArray(text) ? text.join(" ") : text || "").toLowerCase(); const head = t.split(/[(:]/)[0]; if (/^\s*(none|no)\b/.test(head)) return []; return MECHANISM_WORDS.filter((w) => new RegExp("\\b" + w.replace("-", "[- ]") + "\\b").test(head)); }; // the promise is what comes before a "(" or ":"; the rest is explanation

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
const primary = (study, viewport = "wide") => (study.pages || []).find((p) => p.role === "primary" && p.viewport === viewport);
const mechanismTypes = (page) => new Set((page?.motion?.mechanisms || []).map((m) => m.type));
const mechKey = (m) => `${m.tag || ""}.${String(m.cls || "").split(/\s+/)[0] || ""}`;
const realFamilies = (design) => (design?.fonts || []).map((f) => norm(f.family)).filter((f) => f && !GENERIC_FAMILIES.has(f));
const familiesOf = (study) => { const s = new Set(); for (const p of study.pages || []) for (const f of realFamilies(p.design)) s.add(f); return s; };
const groundsOf = (study) => { const out = []; for (const p of study.pages || []) { for (const g of p.ground_sampled?.grounds || []) if (rgb(g.color)) out.push(g.color); for (const g of p.design?.grounds || []) if (rgb(g.color)) out.push(g.color); } return out; };
const dominantGround = (page) => page?.ground_sampled?.grounds?.[0] ? { color: page.ground_sampled.grounds[0].color, share: page.ground_sampled.grounds[0].share, method: "sampled" } : page?.design?.grounds?.[0] ? { color: page.design.grounds[0].color, share: page.design.grounds[0].area_share, method: "stacked estimate" } : null;
const resolveFrom = (base, file) => { if (path.isAbsolute(file)) return file; const fromCwd = path.resolve(file); if (fs.existsSync(fromCwd)) return fromCwd; return path.resolve(path.dirname(path.resolve(base)), file); };
const dataUri = (file) => (file && fs.existsSync(file) ? `data:image/png;base64,${fs.readFileSync(file).toString("base64")}` : null);

/* Gaps an older study did not record but its data still shows. */
function gapsOf(study) {
  const gaps = [...(study.observation_gaps || [])];
  if (!study.observation_gaps) {
    for (const p of study.pages || []) {
      const shas = (p.frames || []).map((f) => f.sha256).filter(Boolean);
      if (shas.length >= 4) { let rep = 0; for (let i = 1; i < shas.length; i += 1) if (shas[i] === shas[i - 1]) rep += 1; if (rep / (shas.length - 1) >= 0.5) gaps.push({ page: p.role === "primary" ? "home" : p.url, viewport: p.viewport, code: "frames-repeat", message: `${rep} of ${shas.length - 1} consecutive frames identical; the recording did not travel` }); }
      if ((p.design?.controls || []).some((c) => /accept|cookie|consent|agree/i.test(c.text || ""))) gaps.push({ page: p.role === "primary" ? "home" : p.url, viewport: p.viewport, code: "consent-overlay", message: "consent controls sit on the first screen; the capture is probably obstructed (older study, not measured directly)" });
      for (const h of p.layout?.horizontal_scrollers || []) gaps.push({ page: p.role === "primary" ? "home" : p.url, viewport: p.viewport, code: "horizontal-untraversed", message: `horizontal scroller ${h.tag}.${(h.cls || "").split(" ")[0]} not traversed` });
    }
    for (const p of (study.pages || []).filter((x) => x.role === "inner" && !x.ok)) gaps.push({ page: p.url, viewport: p.viewport, code: "inner-page-not-studied", message: "inner page did not load" });
  }
  return gaps;
}

/* Runs in the built page: overflow, the listed sections, copy tells, duplicate photographs, emptiness. */
const PROBE = `((sections) => {
  const vw = innerWidth, vh = innerHeight;
  const out = { overflow: { scroll_width: document.documentElement.scrollWidth, viewport: vw, overflows: document.documentElement.scrollWidth > vw + 1 },
    doc_height: document.documentElement.scrollHeight, sections: [], copy: { em_dashes: [], eyebrows: [], padded_numbers: [], stray_arrows: [], disclaimers: [], narration: [], slogans: [] }, duplicate_images: [], words: 0, images: 0 };
  const transparent = (bg) => !bg || bg === 'transparent' || /rgba\\(\\s*\\d+,\\s*\\d+,\\s*\\d+,\\s*0\\s*\\)/.test(bg);
  const paintedGround = (el) => { let n = el; while (n && n !== document.documentElement) { const bg = getComputedStyle(n).backgroundColor; if (!transparent(bg)) return bg; n = n.parentElement; } return getComputedStyle(document.body).backgroundColor; };
  const snippet = (t) => String(t).replace(/\\s+/g, ' ').trim().slice(0, 80);
  const key = (el) => el.tagName.toLowerCase() + '.' + ((typeof el.className === 'string' ? el.className : '').trim().split(/\\s+/)[0] || '');
  const leafArea = (root) => { let sum = 0; const r0 = root.getBoundingClientRect(); const nodes = [root, ...root.querySelectorAll('img,video,canvas,svg,picture,h1,h2,h3,h4,p,li,a,button,figcaption,blockquote,span,label,input,textarea')].slice(0, 600);
    for (const n of nodes) { if (n !== root && n.children.length && !/^(IMG|VIDEO|CANVAS|SVG|PICTURE)$/.test(n.tagName) && !(n.childNodes && [...n.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim()))) continue; if (n === root) continue; const r = n.getBoundingClientRect(); const w = Math.max(0, Math.min(r.right, r0.right) - Math.max(r.left, r0.left)), h = Math.max(0, Math.min(r.bottom, r0.bottom) - Math.max(r.top, r0.top)); sum += w * h; }
    return Math.min(1, sum / Math.max(1, r0.width * r0.height)); };
  for (const s of sections) {
    let nodes = []; try { nodes = document.querySelectorAll(s.selector); } catch (e) { out.sections.push({ selector: s.selector, reference: s.reference, count: -1, error: 'invalid selector' }); continue; }
    const el = nodes[0];
    if (!el) { out.sections.push({ selector: s.selector, reference: s.reference, count: 0 }); continue; }
    const all = [el, ...el.querySelectorAll('*')].slice(0, 800);
    const fonts = [...new Set(all.filter((n) => n.childNodes && [...n.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim())).slice(0, 200).map((n) => getComputedStyle(n).fontFamily.split(',')[0].replace(/["']/g, '').trim().toLowerCase()))];
    const r = el.getBoundingClientRect();
    const sticky = all.some((n) => /sticky|fixed/.test(getComputedStyle(n).position));
    out.sections.push({ selector: s.selector, reference: s.reference, count: nodes.length, ground: paintedGround(el), fonts, keys: [...new Set(all.map(key))].slice(0, 800), height: Math.round(r.height), height_vh: +(r.height / vh).toFixed(2), sticky, coverage: +leafArea(el).toFixed(3), words: (el.innerText || '').trim().split(/\\s+/).filter(Boolean).length, images: el.querySelectorAll('img,video,canvas,picture').length });
  }
  const skip = /^(SCRIPT|STYLE|NOSCRIPT|CODE|PRE|TEMPLATE|TITLE)$/;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node; const disc = /\\b(demo|demonstration|fictional|fiction|placeholder|sample (site|firm|practice|company)|example (firm|practice|company|organization))\\b/i;
  const narr = /\\b(parallax|scroll-driven|hover state|sticky (header|section|panel)|pinned (section|stage|hero)|hero section|micro-?interaction|animation|call[- ]to[- ]action|\\bCTA\\b|responsive design|user experience|UX)\\b/i;
  const slogan = /\\b(elevate|seamless(ly)?|unlock|empower(ing)?|redefin(e|es|ing)|world-class|cutting-edge|next level|your journey|passionate about|we believe in|innovative solutions?|tailored solutions?)\\b/i;
  while ((node = walker.nextNode())) {
    const t = node.textContent; if (!t || !t.trim()) continue;
    const el = node.parentElement; if (!el || skip.test(el.tagName)) continue;
    const cs = getComputedStyle(el); if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    out.words += t.trim().split(/\\s+/).filter(Boolean).length;
    if (t.includes('\\u2014') && out.copy.em_dashes.length < 5) out.copy.em_dashes.push(snippet(t));
    if (/^\\s*0\\d\\s*$/.test(t) && out.copy.padded_numbers.length < 5) out.copy.padded_numbers.push(snippet(t));
    if (/[\\u2192\\u2190\\u2197\\u2198\\u21d2]|->/.test(t) && !el.closest('a,button,[role=button],summary') && out.copy.stray_arrows.length < 5) out.copy.stray_arrows.push(snippet(t));
    if (disc.test(t) && out.copy.disclaimers.length < 12) out.copy.disclaimers.push(snippet(t));
    if (narr.test(t) && out.copy.narration.length < 5) out.copy.narration.push(snippet(t));
    if (slogan.test(t) && out.copy.slogans.length < 5) out.copy.slogans.push(snippet(t));
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
    const r = img.getBoundingClientRect(); if (r.width < 40 || r.height < 40) continue; out.images += 1;
    const k = src.length > 200 ? src.slice(0, 160) + '#' + src.length : src;
    seen.set(k, (seen.get(k) || 0) + 1);
  }
  for (const [k, c] of seen) if (c > 1) out.duplicate_images.push({ src: k.slice(0, 90), uses: c });
  return out;
})`;

/* Runs in the built page: what a visitor with a keyboard, a reduced-motion setting, or a settled page meets. */
const FUNCTIONAL = `(() => {
  const vw = innerWidth, vh = innerHeight;
  const out = { focus: { visited: 0, visible: 0, invisible: [] }, overlays: [], blank: false, hidden_blocks: [] };
  const focusables = [...document.querySelectorAll('a[href],button,input,select,textarea,summary,[tabindex]:not([tabindex="-1"])')].filter((el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; }).slice(0, 14);
  for (const el of focusables) {
    try {
      el.focus({ preventScroll: true }); if (document.activeElement !== el) continue;
      const f = getComputedStyle(el); const snapF = [f.outlineStyle, f.outlineWidth, f.outlineColor, f.boxShadow, f.textDecorationLine, f.backgroundColor, f.color, f.borderColor, f.opacity].join('|');
      const ring = f.outlineStyle !== 'none' && parseFloat(f.outlineWidth) > 0;
      el.blur();
      const b = getComputedStyle(el); const snapB = [b.outlineStyle, b.outlineWidth, b.outlineColor, b.boxShadow, b.textDecorationLine, b.backgroundColor, b.color, b.borderColor, b.opacity].join('|');
      out.focus.visited += 1;
      if (ring || snapF !== snapB) out.focus.visible += 1; else if (out.focus.invisible.length < 5) out.focus.invisible.push(el.tagName.toLowerCase() + ' "' + (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30) + '"');
    } catch (e) {}
  }
  if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el); if (!/fixed|sticky/.test(cs.position)) continue;
    if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect(); const share = (Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0)) * Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0))) / (vw * vh);
    if (share < 0.3) continue; if (r.top < 5 && r.height < 160) continue;
    if (r.height >= vh * 0.9 && r.width >= vw * 0.9 && el.querySelector('img,video,canvas,h1,h2')) continue; // a pinned hero is the page, not an overlay
    out.overlays.push({ tag: el.tagName.toLowerCase(), cls: (typeof el.className === 'string' ? el.className : '').trim().slice(0, 60), share: +share.toFixed(2), text: (el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 80) });
  }
  out.blank = (document.body.innerText || '').trim().length < 40;
  for (const el of document.querySelectorAll('section,article,header,main > div,main > *')) {
    const r = el.getBoundingClientRect(); if (r.top > vh * 2 || r.bottom < 0) continue; if (r.width * r.height < vw * vh * 0.2) continue;
    const cs = getComputedStyle(el); if (Number(cs.opacity) < 0.2 || cs.visibility === 'hidden') out.hidden_blocks.push(el.tagName.toLowerCase() + '.' + ((typeof el.className === 'string' ? el.className : '').trim().split(/\\s+/)[0] || ''));
  }
  return out;
})()`;

async function probeRoute(browser, url, viewport, sections) {
  const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  try {
    await page.goto(url, { waitUntil: "load", timeout: 60_000 });
    await new Promise((r) => setTimeout(r, 1500));
    return await page.evaluate(`${PROBE}(${JSON.stringify(sections || [])})`);
  } finally { await page.close().catch(() => {}); await context.close().catch(() => {}); }
}
async function functionalPass(browser, url, viewport) {
  const out = { viewport: viewport.name };
  for (const reduced of [false, true]) {
    const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1, reducedMotion: reduced ? "reduce" : "no-preference" });
    const page = await context.newPage();
    try {
      await page.goto(url, { waitUntil: "load", timeout: 60_000 });
      await new Promise((r) => setTimeout(r, reduced ? 2500 : 4000));
      const r = await page.evaluate(FUNCTIONAL);
      if (reduced) out.reduced = { blank: r.blank, hidden_blocks: r.hidden_blocks }; else out.settled = r;
    } finally { await page.close().catch(() => {}); await context.close().catch(() => {}); }
  }
  return out;
}

/* Reference beside build, both widths, both storyboards: one image to look at. */
async function reviewSheet(browser, file, title, refDir, refStudy, buildWide, buildNarrow, frameDir) {
  const refWide = primary(refStudy, "wide"), refNarrow = primary(refStudy, "narrow");
  const img = (src, cap) => (src ? `<figure><img src="${src}"><figcaption>${cap}</figcaption></figure>` : `<figure><div class="missing">${cap}: missing</div></figure>`);
  const strip = (frames) => (frames || []).slice(0, 8).map((f) => dataUri(path.join(frameDir, f.file || f))).filter(Boolean).map((d) => `<img src="${d}">`).join("");
  const refFirst = (p) => p && dataUri(path.join(refDir, "frames", (p.first_screen_clear || p.first_screen)?.file || ""));
  const html = `<!doctype html><meta charset="utf-8"><style>
    body{margin:0;background:#151515;color:#eee;font:14px/1.4 system-ui,sans-serif;padding:16px;width:1888px}
    h1{font-size:18px;margin:0 0 12px} h2{font-size:14px;margin:18px 0 8px;color:#bbb;font-weight:400}
    .row{display:grid;grid-template-columns:1fr 1fr;gap:16px} figure{margin:0} figure img{width:100%;display:block;border:1px solid #333}
    figcaption{margin-top:6px;color:#bbb} .narrow figure img{width:390px}
    .strip{display:grid;grid-template-columns:repeat(8,1fr);gap:6px} .strip img{width:100%;border:1px solid #333} .missing{padding:24px;border:1px dashed #555;color:#999}
    p.q{color:#ddd;max-width:1200px}
  </style><h1>${title}</h1>
  <p class="q">Ask of each pair: does the reference's memorable experience come through? Judge hierarchy, density, crop, legibility and pacing. Matching a font family or a mechanism label answers none of that.</p>
  <h2>First screen, wide: reference (left) beside build (right)</h2>
  <div class="row">${img(refFirst(refWide), `${refStudy.url}`)}${img(dataUri(path.join(frameDir, buildWide?.first_screen?.file || "")), "build")}</div>
  <h2>First screen, narrow: reference (left) beside build (right)</h2>
  <div class="row narrow">${img(refFirst(refNarrow), `${refStudy.url}`)}${img(dataUri(path.join(frameDir, buildNarrow?.first_screen?.file || "")), "build")}</div>
  <h2>Scroll storyboard: reference</h2>
  ${img(dataUri(path.join(refDir, refWide?.contact_sheet?.file || "")), "reference wide scroll-through")}
  <h2>Scroll storyboard: build (frames from this check's scroll-through)</h2>
  <div class="strip">${strip(buildWide?.frames)}</div>`;
  const context = await browser.newContext({ viewport: { width: 1920, height: 1200 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  try { await page.setContent(html, { waitUntil: "load" }); await page.screenshot({ path: file, fullPage: true }); }
  finally { await page.close().catch(() => {}); await context.close().catch(() => {}); }
}

function readReview(file, selected, plan) {
  const declared = String(plan.review?.reviewer || "self").toLowerCase();
  if (!fs.existsSync(file)) return { written: false, line: `REVIEW MISSING: ${file} does not exist; look at review-*.png and write it (Reviewer: self or independent; one "- <id>: reference shows ... / build shows ... / difference ..." line per selected reference; "## Visitor walk"; "## Unresolved")` };
  const text = fs.readFileSync(file, "utf8");
  const reviewerLine = (text.match(/^\s*(?:\*\*)?reviewer(?:\*\*)?\s*:\s*(.+)$/im) || [])[1] || "";
  const independent = /independent/i.test(reviewerLine) && !/self/i.test(reviewerLine) && declared === "independent";
  const covered = selected.filter((id) => new RegExp(`^\\s*[-*]\\s*${id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*:`, "mi").test(text));
  const missing = selected.filter((id) => !covered.includes(id));
  const unresolvedBlock = text.split(/^##\s*Unresolved[^\n]*$/im)[1] || null;
  const unresolved = unresolvedBlock ? unresolvedBlock.split(/^##\s/m)[0].split("\n").filter((l) => /^\s*[-*]\s+\S/.test(l)).length : null;
  const walkBlock = text.split(/^##\s*Visitor walk[^\n]*$/im)[1] || null;
  const walkTopics = [["menus", /menu/i], ["reading flow", /reading|read/i], ["horizontal interactions", /horizontal|sideways|carousel|strip/i], ["keyboard", /keyboard|tab /i], ["focus", /focus/i], ["moving content", /moving|motion|animat/i], ["overlays", /overlay|cover|obstruct/i], ["reduced motion", /reduced[- ]motion/i], ["mobile", /mobile|phone|narrow/i], ["settled states", /settled|at rest|after load|blank/i]];
  const walkMissing = walkBlock === null ? walkTopics.map((t) => t[0]) : walkTopics.filter((t) => !t[1].test(walkBlock.split(/^##\s/m)[0])).map((t) => t[0]);
  const head = independent ? "REVIEW INDEPENDENT" : "REVIEW SELF-REVIEW";
  const parts = [`${head}: ${file}; ${covered.length} of ${selected.length} selected references compared`];
  if (!independent) parts.push("written by the builder, so it is the builder's comparison, not a second pair of eyes");
  if (missing.length) parts.push(`missing: ${missing.join(", ")}`);
  parts.push(unresolved === null ? "no \"## Unresolved\" section" : `${unresolved} unresolved difference(s) listed`);
  parts.push(walkBlock === null ? "no \"## Visitor walk\" section" : walkMissing.length ? `visitor walk does not mention: ${walkMissing.join(", ")}` : "visitor walk covers menus, reading, horizontal, keyboard, focus, motion, overlays, reduced motion, mobile, settled states");
  parts.push("a written review proves a review was written, not that the design is good");
  return { written: true, independent, covered, missing, unresolved, walkMissing, line: parts.join("; ") };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const plan = JSON.parse(fs.readFileSync(args.plan, "utf8"));
  const studies = loadStudies(args.studies);
  const registry = loadRegistry();
  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const outRoot = path.resolve(args.outDir);
  const outDir = path.join(outRoot, "runs", stamp);
  const frameDir = path.join(outDir, "frames"), videoDir = path.join(outDir, "videos");
  fs.mkdirSync(frameDir, { recursive: true }); fs.mkdirSync(videoDir, { recursive: true });
  const reviewFile = path.resolve(args.review || (plan.review?.file ? resolveFrom(args.plan, plan.review.file) : path.join(path.dirname(path.resolve(args.plan)), "review.md")));
  const problems = [], passed = [], functional = [], notes = [];
  const push = (cat, msg) => problems.push({ cat, msg });
  const evidence = { plan: args.plan, studies: [...studies.keys()], run: outDir, routes: [], sources: [], sections: [], probes: [], functional: [] };

  // ---- inputs: routes, references, both widths, duplicates
  const routes = plan.routes || [];
  if (!routes.length) push("plan", "the plan names no build route");
  const ids = (plan.references || []).map((r) => r.id);
  const dupes = ids.filter((id, i) => ids.indexOf(id) !== i);
  if (dupes.length) push("selection", `reference listed twice: ${[...new Set(dupes)].join(", ")}; a duplicate is not a second reference`);
  for (const ref of plan.references || []) if (!studies.has(ref.id)) push("plan", `plan cites reference ${ref.id} but ${args.studies}/${ref.id}/study.json does not exist`);
  const selected = [...new Set(ids.filter((id) => studies.has(id)))];
  if (selected.length < 4) push("selection", `plan selects ${selected.length} distinct studied references; the floor is four, and a filler fourth is not a reference: keep studying until the set works`);
  for (const id of selected) {
    const study = studies.get(id);
    for (const vp of ["wide", "narrow"]) {
      const p = primary(study, vp);
      if (!p?.ok) push("evidence", `${id}: the ${vp} study did not succeed (${(p?.problems || []).map((x) => x.message).join("; ") || "no record"}); a reference the tool could not read at this width is not selected`);
    }
    if ((study.problems || []).some((p) => /^http-4|^http-5/.test(p.code || ""))) push("evidence", `${id}: the study hit an HTTP error page`);
  }

  // ---- selection as a quality decision; contributions; gaps acknowledged
  for (const ref of plan.references || []) {
    if (!studies.has(ref.id)) continue;
    const q = ref.quality || {};
    const missing = QUALITY_FIELDS.filter((f) => words(q[f]).length < 4);
    if (missing.length) push("selection", `${ref.id}: no selection judgment recorded for ${missing.join(", ")}; a gallery listing is discovery, not quality. Say what its desktop and mobile experience, readability, navigation, reliability and suitability for THIS content actually are`);
    if (words(ref.contributes).length < 3) push("selection", `${ref.id}: "contributes" is empty; a reference that contributes nothing nameable is filler`);
    if (!ref.signature || !VERBS.test(ref.signature)) push("selection", `${ref.id}: signature "${ref.signature || ""}" does not say what the site DOES (no verb)`);
    const study = studies.get(ref.id);
    const detected = new Set([...mechanismTypes(primary(study, "wide")), ...mechanismTypes(primary(study, "narrow"))]);
    for (const type of ref.signature_mechanisms || []) if (!detected.has(type)) push("evidence", `${ref.id}: signature mechanism "${type}" was not detected on that site (detected: ${[...detected].join(", ") || "none"})`);
    const gaps = gapsOf(study);
    if (gaps.length && words(ref.gaps_reviewed).length < 6) push("evidence", `${ref.id}: the study has ${gaps.length} observation gap(s) (${[...new Set(gaps.map((g) => g.code))].join(", ")}); the plan does not say how they were inspected before copying (gaps_reviewed). A successful capture is not an adequate study`);
  }
  const usedBy = new Map(selected.map((id) => [id, 0]));
  for (const route of routes) for (const s of route.sections || []) for (const id of [s.reference, s.palette_from, s.behavior_from]) if (id && usedBy.has(id)) usedBy.set(id, usedBy.get(id) + 1);
  for (const [id, n] of usedBy) if (!n) push("selection", `${id} is selected but no section copies it; a reference that reaches no section is a quota filler`);

  // ---- sources (reported last; a registry fault never outranks a design fault)
  const sourceKeys = new Map();
  for (const ref of plan.references || []) {
    if (!studies.has(ref.id)) continue;
    const key = keyOf(ref.source_id || String(ref.source || "").split(/[;,(:]/)[0]);
    const src = registry.get(key);
    evidence.sources.push({ id: ref.id, key, registry: src?.id || null, curation: src?.curation || null, source_url: ref.source_url || null });
    if (!key) push("sources", `${ref.id}: no source_id; name the registry source that lists this site`);
    else if (!src) push("sources", `${ref.id}: source "${ref.source_id || ref.source}" is not in the public-reference registry; if the gallery is real and curated, correct the registry with a dated entry before building`);
    else if (!/^(award|curated)$/i.test(src.curation || "")) push("sources", `${ref.id}: source ${src.id} is a submission feed (${src.curation}); it cannot supply a selected reference`);
    else if (src.status && src.status !== "active") push("sources", `${ref.id}: source ${src.id} is ${src.status} in the registry (${src.notes || ""}); verify the current domain and record a dated correction, or pick another listing`);
    else {
      sourceKeys.set(src.id, (sourceKeys.get(src.id) || 0) + 1);
      if (!ref.source_url) push("sources", `${ref.id}: no source_url; the listing page that names this site must be recorded so anyone can verify it`);
      else { const h = hostOf(ref.source_url); const ok = [hostOf(src.url), ...(src.aliases || []).map((a) => a.replace(/^www\./, ""))].filter(Boolean).some((d) => h === d || (h && h.endsWith("." + d))); if (!ok) push("sources", `${ref.id}: source_url ${ref.source_url} is not on ${src.id}'s domain (${hostOf(src.url)}${(src.aliases || []).length ? " or " + src.aliases.join(", ") : ""})`); }
    }
  }
  if (selected.length && sourceKeys.size < 2) push("sources", `selected references come from ${sourceKeys.size} registry source(s) (${[...sourceKeys.keys()].join(", ") || "none"}); the floor is two`);
  else if (sourceKeys.size) passed.push(`sources: ${[...sourceKeys.keys()].join(", ")}`);

  // ---- read the build
  const loaded = resolvePlaywright({ moduleUrl: import.meta.url });
  const executable = discoverBrowserExecutable(loaded.playwright, args.browserExecutable);
  const browser = await loaded.playwright.chromium.launch({ executablePath: executable.path });
  const buildPages = [], probes = [];
  const routesToRead = args.early ? routes.slice(0, 1) : routes;
  try {
    for (const [index, route] of routesToRead.entries()) {
      const routeName = route.name || route.url;
      for (const viewport of VIEWPORTS) {
        const record = await studyPage(browser, route.url, viewport, { frameDir, videoDir, prefix: `route${index + 1}-${viewport.name}`, videoSeconds: viewport.name === "wide" ? (args.early ? 6 : args.routeSeconds) : 0, full: viewport.name === "wide" });
        record.role = "build"; record.route = routeName;
        buildPages.push(record);
        if (!record.ok) push("evidence", `${routeName} (${viewport.name}) could not be read: ${record.problems.map((p) => p.message).join("; ")}`);
        if (args.early) continue;
        try { probes.push({ route: routeName, viewport: viewport.name, ...(await probeRoute(browser, route.url, viewport, route.sections || [])) }); }
        catch (error) { push("evidence", `${routeName} (${viewport.name}) probe failed: ${String(error?.message || error).slice(0, 160)}`); }
        try { evidence.functional.push({ route: routeName, ...(await functionalPass(browser, route.url, viewport)) }); }
        catch (error) { functional.push(`${routeName} (${viewport.name}): functional pass failed: ${String(error?.message || error).slice(0, 160)}`); }
      }
      const dom = route.dominant && studies.get(route.dominant);
      if (dom) {
        const file = path.join(outDir, `review-${index + 1}-${String(routeName).replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.png`);
        try {
          await reviewSheet(browser, file, `${routeName}: ${route.dominant} (reference) beside the build`, path.join(path.resolve(args.studies), route.dominant), dom,
            buildPages.find((p) => p.route === routeName && p.viewport === "wide"), buildPages.find((p) => p.route === routeName && p.viewport === "narrow"), frameDir);
          evidence.routes.push({ route: routeName, review_sheet: path.relative(outRoot, file).split(path.sep).join("/") });
          fs.copyFileSync(file, path.join(outRoot, path.basename(file)));
        } catch (error) { push("evidence", `${routeName}: review sheet could not be rendered: ${String(error?.message || error).slice(0, 160)}`); }
      } else push("plan", `route ${routeName} names no studied dominant reference`);
    }
  } finally { await Promise.race([browser.close(), new Promise((r) => setTimeout(r, 15_000))]).catch(() => {}); }
  evidence.probes = probes;

  if (args.early) {
    const sheetFile = evidence.routes[0]?.review_sheet;
    process.stdout.write(`EARLY LOOK: ${sheetFile ? path.join(outRoot, sheetFile) : "no review sheet (no dominant reference or the build could not be read)"}; compare hierarchy, density, crop, legibility and pacing at both widths, and whether the reference's impression comes through, before building further\n`);
    fs.writeFileSync(path.join(outDir, "early.json"), JSON.stringify({ tool: TOOL, early: true, checked_at: new Date().toISOString(), build_pages: buildPages.map((p) => ({ route: p.route, viewport: p.viewport, ok: p.ok, first_screen: p.first_screen?.file })), evidence }, null, 2) + "\n");
    return;
  }

  // ---- typefaces: reference families or verified matches
  const familiesByRef = new Map(selected.map((id) => [id, familiesOf(studies.get(id))]));
  const referenceFamilies = new Set([].concat(...[...familiesByRef.values()].map((s) => [...s])));
  const declared = new Set((plan.typefaces || []).map((t) => norm(t.family)));
  const matchedFor = new Map(); // matched family -> reference family it stands for
  for (const t of plan.typefaces || []) {
    const fam = norm(t.family);
    if (!referenceFamilies.has(fam) && !t.matched_for) push("design", `typeface "${t.family}" is not computed by any selected reference and declares no matched_for`);
    if (t.matched_for) {
      if (!referenceFamilies.has(norm(t.matched_for))) push("design", `typeface "${t.family}" claims to match "${t.matched_for}", which no selected reference computes`);
      if (!t.match_record) push("evidence", `typeface "${t.family}" claims to match "${t.matched_for}" but names no match_record; a typed claim is not a match`);
      else {
        const file = resolveFrom(args.plan, t.match_record);
        let rec = null;
        try { rec = JSON.parse(fs.readFileSync(file, "utf8")); } catch { push("evidence", `typeface "${t.family}": match_record ${t.match_record} cannot be read`); }
        if (rec) {
          const hit = (rec.results || []).find((r) => stem(r.target?.family) === stem(t.matched_for));
          if (rec.tool !== "match_typeface.mjs") push("evidence", `typeface "${t.family}": ${t.match_record} was not written by match_typeface.mjs`);
          else if (!hit) push("evidence", `typeface "${t.family}": ${t.match_record} has no result for target "${t.matched_for}"`);
          else if (stem(hit.chosen?.family) !== fam) push("evidence", `typeface "${t.family}" is not the rank-one match for "${t.matched_for}"; the record chose "${hit.chosen?.family || "nothing"}"`);
          else if (!rec.verified_browser_measurement) push("evidence", `typeface "${t.family}": the match record's candidates were not measured in the browser`);
          else { matchedFor.set(fam, norm(t.matched_for)); passed.push(`match: ${t.family} ranks first for ${t.matched_for} (delta ${hit.chosen.delta})`); }
        }
      }
    }
  }
  if ((plan.typefaces || []).length > 2) push("design", `plan declares ${(plan.typefaces || []).length} typefaces; the rule is at most two`);
  const buildFamilies = new Set(); for (const page of buildPages) for (const f of realFamilies(page.design)) buildFamilies.add(f);
  for (const f of buildFamilies) {
    if (!declared.has(f)) push("design", `the build sets text in "${f}", which the plan does not declare`);
    else if (!referenceFamilies.has(f) && !matchedFor.has(f)) push("design", `the build sets text in "${f}", which no selected reference computes and no verified match record ranks first`);
  }
  if (buildFamilies.size) passed.push(`fonts: ${[...buildFamilies].join(", ")}`);

  // ---- ground: sampled visible ground, compared to what references visibly paint
  const groundsByRef = new Map(selected.map((id) => [id, groundsOf(studies.get(id))]));
  const refDominant = selected.map((id) => ({ id, ...dominantGround(primary(studies.get(id))) })).filter((g) => g.color);
  for (const route of routes) {
    const routeName = route.name || route.url;
    for (const viewport of VIEWPORTS) {
      const page = buildPages.find((p) => p.route === routeName && p.viewport === viewport.name && p.ok);
      const g = dominantGround(page); if (!g) continue;
      // co-dominant: sampled grounds within three points of the top share count as the page's ground too
      const co = (page.ground_sampled?.grounds || []).filter((x) => rgb(x.color) && x.share >= g.share - 0.03);
      const candidates = co.length ? co.map((x) => ({ color: x.color, share: x.share })) : [g];
      if (viewport.name === "wide") {
        const hit = candidates.map((c) => ({ c, near: refDominant.filter((r) => colorDistance(r.color, c.color) <= 24) })).find((x) => x.near.length);
        if (!hit) push("design", `${routeName} (wide): the visible ground is mostly ${candidates.map((c) => `${c.color} ${Math.round(c.share * 100)}%`).join(" / ")} (of sampled points, ${g.method}); no selected reference's dominant visible ground is near it (${refDominant.map((r) => `${r.id} ${r.color} ${Math.round(r.share * 100)}% ${r.method}`).join("; ")})`);
        else passed.push(`ground ${hit.c.color} (${Math.round(hit.c.share * 100)}% sampled${candidates.length > 1 ? ", co-dominant" : ""}) from ${hit.near.map((r) => r.id).join(", ")}`);
        if (plan.ground?.color && !candidates.some((c) => colorDistance(plan.ground.color, c.color) <= 24)) push("plan", `the plan's ground ${plan.ground.color} is not what ${routeName} mostly paints (${candidates.map((c) => c.color).join(" / ")})`);
      } else if (![...groundsByRef.values()].some((list) => list.some((c) => colorDistance(c, g.color) <= 24))) {
        push("design", `${routeName} (narrow): the visible ground ${g.color} is not a ground any selected reference paints`);
      }
    }
  }

  // ---- sections: the plan explains each relationship; the build carries it in that section, at each width
  const buildMechs = (routeName, viewport) => (buildPages.find((p) => p.route === routeName && p.viewport === viewport && p.ok)?.motion?.mechanisms || []);
  for (const route of routes) {
    const routeName = route.name || route.url;
    const sections = route.sections || [];
    if (!sections.length) { push("plan", `route ${routeName} has no sections list; every major section names its reference, content, composition, image role, typography role, behavior and mobile adaptation`); continue; }
    const dominantId = route.dominant;
    for (const s of sections) {
      const missing = SECTION_FIELDS.filter((f) => { const w = words(s[f]); return !(w.length >= 2 || (w.length === 1 && (/^(none|no)$/i.test(w[0]) || MECHANISM_WORDS.includes(w[0].toLowerCase())))); });
      if (missing.length) push("plan", `${routeName} section "${s.selector}": missing ${missing.join(", ")}`);
      if (!s.reference || !selected.includes(s.reference)) { push("plan", `${routeName} section "${s.selector}" names reference "${s.reference}", which is not a selected reference`); continue; }
      if (s.palette_from && !selected.includes(s.palette_from)) push("plan", `${routeName} section "${s.selector}": palette_from "${s.palette_from}" is not a selected reference`);
      if (s.behavior_from && !selected.includes(s.behavior_from)) push("plan", `${routeName} section "${s.selector}": behavior_from "${s.behavior_from}" is not a selected reference`);
      const allowedFamilies = new Set([...(familiesByRef.get(s.reference) || []), ...(familiesByRef.get(dominantId) || [])]);
      for (const [m, target] of matchedFor) if (allowedFamilies.has(target)) allowedFamilies.add(m);
      const allowedGrounds = [...(groundsByRef.get(s.reference) || []), ...(groundsByRef.get(dominantId) || []), ...(s.palette_from ? groundsByRef.get(s.palette_from) || [] : [])];
      const wantWide = mechanismsIn(s.behavior);
      const wantNarrow = s.behavior_narrow === undefined ? wantWide : mechanismsIn(s.behavior_narrow);
      for (const viewport of VIEWPORTS) {
        const probe = probes.find((p) => p.route === routeName && p.viewport === viewport.name);
        const ps = probe?.sections?.find((x) => x.selector === s.selector);
        if (!ps) continue;
        const where = `${routeName} (${viewport.name}) section "${s.selector}"`;
        evidence.sections.push({ ...ps, route: routeName, viewport: viewport.name });
        if (ps.count === -1) { push("plan", `${where}: invalid selector`); continue; }
        if (ps.count === 0) { push("design", `${where}: not in the page`); continue; }
        const foreign = (ps.fonts || []).filter((f) => f && !GENERIC_FAMILIES.has(f) && !allowedFamilies.has(f));
        if (foreign.length) push("design", `${where}: sets text in ${foreign.join(", ")}, which neither ${s.reference} nor the route's dominant reference computes; a family somewhere in the set does not authorize its use here`);
        if (ps.ground && rgb(ps.ground) && allowedGrounds.length && !allowedGrounds.some((c) => colorDistance(c, ps.ground) <= 24)) push("design", `${where}: paints ${ps.ground}, a ground neither ${s.reference} nor the dominant reference${s.palette_from ? ` nor ${s.palette_from}` : ""} paints`);
        const want = viewport.name === "wide" ? wantWide : wantNarrow;
        const keys = new Set(ps.keys || []);
        const have = new Set(buildMechs(routeName, viewport.name).filter((m) => keys.has(mechKey(m))).map((m) => m.type));
        const hoverOk = viewport.name === "narrow" || (buildPages.find((p) => p.route === routeName && p.viewport === "wide")?.hover?.responded || 0) > 0;
        for (const w of want) {
          if (w === "hover") { if (!hoverOk) push("design", `${where}: promises a hover response and no control on the route responded to the pointer`); continue; }
          if (!have.has(w)) push("design", `${where}: the plan says it ${w === "pinned" ? "holds still (pinned)" : w}, and no ${w} element was detected inside it at this width (detected here: ${[...have].join(", ") || "none"}). Test the behavior chosen for this section, not the page's pooled motion`);
        }
        if (want.length && want.every((w) => w === "hover" ? hoverOk : have.has(w))) passed.push(`${s.selector} ${viewport.name}: ${want.join("+")}`);
        // Proportions: the reference's relationships, not its pixel heights.
        if (ps.sticky) {
          const states = Number(s.states);
          if (!Number.isFinite(states) || states < 1) push(ps.height_vh > 2 ? "design" : "plan", `${where}: holds still for ${ps.height}px (${ps.height_vh} viewports) of scrolling and the plan gives no "states" (how many things the visitor sees while it holds); scroll distance has to be earned, about one viewport per state`);
          else if (ps.height_vh > states * 1.3 + 0.3) push("design", `${where}: asks for ${ps.height}px (${ps.height_vh} viewports) of scrolling for ${states} state(s); more than about one viewport per state is work without an experience`);
        } else if (ps.height_vh >= 1.2 && ps.coverage < 0.15 && ps.images === 0) {
          push("design", `${where}: ${ps.height}px tall (${ps.height_vh} viewports) with content covering ${Math.round(ps.coverage * 100)}% and no photograph; short copy inherited a tall container`);
        } else if (ps.height_vh >= 1.6 && ps.coverage < 0.25) {
          push("design", `${where}: ${ps.height}px tall (${ps.height_vh} viewports) with content covering ${Math.round(ps.coverage * 100)}%; the reference's proportions were transplanted without its content`);
        }
      }
    }
  }
  const promisedRoute = routes.filter((r) => (r.mechanisms || []).length);
  if (promisedRoute.length) notes.push("route-level \"mechanisms\" lists are no longer checked or pooled; behavior is tested per section and per width");
  // Inner routes copy only references with studied inner pages.
  for (const [index, route] of routes.entries()) {
    if (index === 0 || !route.dominant || !studies.has(route.dominant)) continue;
    if (!(studies.get(route.dominant).pages || []).some((p) => p.role === "inner" && p.ok)) push("evidence", `route ${route.name || route.url} copies ${route.dominant}, whose inner pages were never studied`);
  }

  // ---- whole-page emptiness, overflow, copy, duplicate photographs
  for (const probe of probes) {
    const where = `${probe.route} (${probe.viewport})`;
    const vh = VIEWPORTS.find((v) => v.name === probe.viewport).height;
    const screens = Math.max(1, probe.doc_height / vh);
    if (probe.words / screens < 20 && probe.images / screens < 0.5) push("design", `${where}: ${probe.doc_height}px of page (${screens.toFixed(1)} viewports) carries ${probe.words} words and ${probe.images} photographs; the page is mostly empty`);
    if (probe.overflow?.overflows) functional.push(`${where}: the page scrolls sideways (${probe.overflow.scroll_width}px wide in a ${probe.overflow.viewport}px viewport)`);
    const c = probe.copy || {};
    if (c.em_dashes?.length) push("content", `${where}: copy uses an em dash (${c.em_dashes.slice(0, 2).map((x) => `"${x}"`).join("; ")})`);
    if (c.eyebrows?.length) push("content", `${where}: an eyebrow label sits above a heading (${c.eyebrows.slice(0, 2).join("; ")})`);
    if (c.padded_numbers?.length) push("content", `${where}: decorative padded numbers (${c.padded_numbers.slice(0, 3).join(", ")})`);
    if (c.stray_arrows?.length) push("content", `${where}: an arrow on something that is not a link (${c.stray_arrows.slice(0, 2).map((x) => `"${x}"`).join("; ")})`);
    if ((c.disclaimers || []).length > 1) push("content", `${where}: the page explains that it is a demo ${c.disclaimers.length} times (${c.disclaimers.slice(0, 3).map((x) => `"${x}"`).join("; ")}); one quiet disclosure is enough`);
    if (c.narration?.length) push("content", `${where}: public copy narrates the design (${c.narration.slice(0, 2).map((x) => `"${x}"`).join("; ")})`);
    if (c.slogans?.length) push("content", `${where}: generic slogan (${c.slogans.slice(0, 2).map((x) => `"${x}"`).join("; ")})`);
    if (probe.duplicate_images?.length) push("design", `${where}: a photograph is used more than once (${probe.duplicate_images.slice(0, 3).map((d) => `${d.uses}x ${d.src.slice(0, 40)}`).join("; ")})`);
  }

  // ---- hover: the dominant reference's controls answer the pointer, so the build's must
  for (const route of routes) {
    const routeName = route.name || route.url;
    const page = buildPages.find((p) => p.route === routeName && p.viewport === "wide" && p.ok);
    const domHover = primary(studies.get(route.dominant) || { pages: [] })?.hover;
    if (page?.hover && domHover?.responded > 0 && page.hover.responded === 0 && page.hover.probed > 0) push("design", `${routeName}: no probed control responds to the pointer; ${route.dominant}'s controls do`);
  }

  // ---- slop shapes at both widths
  for (const page of buildPages.filter((p) => p.ok && p.design)) {
    const where = `${page.route} (${page.viewport})`;
    const d = page.design;
    const gradientText = (d.type_scale || []).some((t) => /^h[12]$|display/.test(t.role) && /transparent/.test(t.color || ""));
    if (gradientText) push("design", `${where}: slop: gradient text`);
    const types = mechanismTypes(page);
    if (types.size === 1 && types.has("reveal")) push("design", `${where}: slop: sections fading up on scroll are the only motion on this page`);
    const sections = page.layout?.sections || [];
    const threeEqualTracks = (grid) => { const px = String(grid || "").match(/[\d.]+px/g); if (!px || px.length !== 3) return /repeat\(3|1fr 1fr 1fr/.test(grid || ""); const n = px.map(parseFloat); const max = Math.max(...n), min = Math.min(...n); return max > 0 && (max - min) / max < 0.05; };
    const triplet = sections.find((s) => /grid/.test(s.display) && threeEqualTracks(s.grid) && s.images === 0 && s.text_chars < 600 && s.top < 1400);
    if (triplet) push("design", `${where}: slop: a three-column icon-card row near the top of the page (${triplet.tag}${triplet.class ? "." + triplet.class.split(" ")[0] : ""} at ${triplet.top}px)`);
  }

  // ---- functional
  for (const f of evidence.functional) {
    const where = `${f.route} (${f.viewport})`;
    const s = f.settled;
    if (s) {
      if (s.focus.visited >= 3 && s.focus.visible / s.focus.visited < 0.6) functional.push(`${where}: keyboard focus is invisible on ${s.focus.visited - s.focus.visible} of ${s.focus.visited} controls (${s.focus.invisible.slice(0, 3).join(", ")})`);
      for (const o of s.overlays) functional.push(`${where}: a fixed layer ${o.tag}${o.cls ? "." + o.cls.split(" ")[0] : ""} covers ${Math.round(o.share * 100)}% of the viewport at rest ("${o.text.slice(0, 50)}")`);
      if (s.blank) functional.push(`${where}: the page is blank four seconds after load`);
      if (s.hidden_blocks.length) functional.push(`${where}: ${s.hidden_blocks.length} large block(s) near the top sit at opacity below 0.2 at rest (${s.hidden_blocks.slice(0, 3).join(", ")}); content waits on an observer`);
    }
    if (f.reduced?.blank) functional.push(`${where}: with reduced motion the page is blank`);
    if (f.reduced?.hidden_blocks?.length) functional.push(`${where}: with reduced motion ${f.reduced.hidden_blocks.length} large block(s) stay hidden (${f.reduced.hidden_blocks.slice(0, 3).join(", ")})`);
  }

  // ---- evidence: tool revisions
  const staleStudies = selected.filter((id) => studies.get(id).runtime?.tool_sha256 !== STUDY_SHA);
  const evidenceLine = `EVIDENCE: check_build ${SELF_SHA.slice(0, 12)}, study_reference ${STUDY_SHA.slice(0, 12)}; studies by the current study revision: ${selected.length - staleStudies.length} of ${selected.length}${staleStudies.length ? ` (older: ${staleStudies.join(", ")}; re-study to gain sampled ground, observation gaps and drivers)` : ""}; run ${path.relative(process.cwd(), outDir).split(path.sep).join("/")}`;

  // ---- verdicts
  const order = (a, b) => CATEGORY_ORDER.indexOf(a.cat) - CATEGORY_ORDER.indexOf(b.cat);
  problems.sort(order);
  const routeCount = routes.length;
  const verdict = problems.length
    ? `CHECK FAIL (automated) ${problems.length} problem(s): ${problems.map((p) => `[${p.cat}] ${p.msg}`).join(" | ")}`
    : `CHECK PASS (automated): ${passed.length} measurable comparisons over ${routeCount} route(s) x 2 widths (${passed.join("; ")}); this proves provenance and the absence of known failure shapes, not that the site is good`;
  const functionalLine = functional.length ? `FUNCTIONAL FAIL ${functional.length} problem(s): ${functional.join(" | ")}` : `FUNCTIONAL PASS: keyboard focus visible, content present with reduced motion, no overlay at rest, no sideways scroll, at both widths`;
  const review = readReview(reviewFile, selected, plan);
  const approvalLine = plan.approval?.by && plan.approval?.date ? `APPROVAL recorded: ${plan.approval.by}, ${plan.approval.date}${plan.approval.note ? ` (${plan.approval.note})` : ""}` : "APPROVAL not recorded: no owner approval is claimed";
  const report = { tool: TOOL, tool_revisions: { check_build: SELF_SHA, study_reference: STUDY_SHA }, checked_at: new Date().toISOString(), verdict, functional: functionalLine, review: review.line, evidence_line: evidenceLine, approval: approvalLine, notes, problems, functional_problems: functional, passed, evidence,
    build_pages: buildPages.map((p) => ({ route: p.route, viewport: p.viewport, ok: p.ok, status: p.status ?? null, first_screen: p.first_screen?.file, mechanisms: p.motion?.mechanisms?.map((m) => `${m.type}:${m.driver || "?"}:${mechKey(m)}`), fonts: p.design?.fonts, ground: dominantGround(p), overflow_x: p.layout?.overflow_x || null })) };
  fs.writeFileSync(path.join(outDir, "check.json"), JSON.stringify(report, null, 2) + "\n");
  fs.writeFileSync(path.join(outRoot, "check.json"), JSON.stringify(report, null, 2) + "\n");
  fs.writeFileSync(path.join(outRoot, "latest.json"), JSON.stringify({ run: outDir, checked_at: report.checked_at, lines: [verdict, functionalLine, review.line, evidenceLine, approvalLine] }, null, 2) + "\n");
  process.stdout.write([verdict, functionalLine, review.line, evidenceLine, approvalLine].join("\n") + "\n");
  process.exitCode = problems.length ? 1 : 0;
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url));
if (invokedDirectly) {
  main().catch((error) => { process.stdout.write(`CHECK FAIL (automated) ${error?.code || "check-failed"}: ${String(error?.message || error).slice(0, 400)}\nFUNCTIONAL not run\nREVIEW not read: the check did not run\nEVIDENCE none\nAPPROVAL not recorded\n`); process.exitCode = 2; })
    .finally(() => { setTimeout(() => process.exit(process.exitCode ?? 0), 2000).unref(); });
}
