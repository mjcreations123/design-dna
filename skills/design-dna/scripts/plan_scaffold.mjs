#!/usr/bin/env node
/**
 * plan_scaffold.mjs
 *
 * Writes the measurable half of plan.json from the studies so the producer
 * only fills the judgments: ids, urls, detected mechanisms with drivers, the
 * fonts the selected references compute and where they load from, the
 * dominant reference's sampled ground, the observation gaps to acknowledge,
 * a signature_spec per reference built from the regions the full study
 * captured (with the tool's own evidence files and hashes), one section stub
 * per captured region with its source_region and signature_transfer, and the
 * system_sections the check expects. Every field the producer must write
 * says TODO, and the check refuses a plan that still says TODO.
 *
 *   node plan_scaffold.mjs --studies .design-dna/references --select a,b,c,d --dominant a \
 *        --route http://127.0.0.1:4870/ --out .design-dna/plan.json
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { createHash } from "node:crypto";

function parseArgs(argv) {
  const out = { studies: null, select: [], dominant: null, route: null, out: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--studies") out.studies = argv[++i];
    else if (a === "--select") out.select = String(argv[++i]).split(",").map((x) => x.trim()).filter(Boolean);
    else if (a === "--dominant") out.dominant = argv[++i];
    else if (a === "--route") out.route = argv[++i];
    else if (a === "--out") out.out = argv[++i];
    else if (a === "--help" || a === "-h") { process.stdout.write("plan_scaffold.mjs --studies DIR --select a,b,c,d --dominant a --route URL --out FILE\n"); process.exit(0); }
    else { process.stdout.write(JSON.stringify({ ok: false, error: `unknown argument ${a}` }) + "\n"); process.exit(2); }
  }
  if (!out.studies || !fs.existsSync(out.studies) || !out.select.length || !out.out || !out.route) { process.stdout.write(JSON.stringify({ ok: false, error: "--studies, --select, --route and --out are required" }) + "\n"); process.exit(2); }
  if (!out.dominant) out.dominant = out.select[0];
  if (!out.select.includes(out.dominant)) { process.stdout.write(JSON.stringify({ ok: false, error: "--dominant must be one of --select" }) + "\n"); process.exit(2); }
  return out;
}
const GOOGLE = /fonts\.gstatic\.com|fonts\.googleapis\.com/i;
const VIEWPORTS = ["wide", "narrow"];
const norm = (f) => String(f || "").replace(/["']/g, "").trim();
const uniq = (xs) => [...new Set(xs)];
const sha = (file) => createHash("sha256").update(fs.readFileSync(file)).digest("hex");

const args = parseArgs(process.argv.slice(2));
const studies = new Map();
for (const entry of fs.readdirSync(args.studies, { withFileTypes: true })) {
  const file = path.join(args.studies, entry.name, "study.json");
  if (entry.isDirectory() && fs.existsSync(file)) studies.set(entry.name, JSON.parse(fs.readFileSync(file, "utf8")));
}
const missing = args.select.filter((id) => !studies.has(id));
if (missing.length) { process.stdout.write(JSON.stringify({ ok: false, error: `not studied: ${missing.join(", ")}` }) + "\n"); process.exit(1); }
const primary = (st, vp) => (st.pages || []).find((p) => p.role === "primary" && p.viewport === vp);
const regionsOf = (page) => (page?.regions || []).filter((r) => r.count === 1 && r.evidence?.file);
const measuredIn = (page, region) => (page?.motion?.mechanisms || []).filter((m) => m.selector && (region.selectors || []).includes(m.selector));
const videoEvidence = (id, page) => {
  if (!page?.video) return null;
  for (const rel of [path.join("videos", page.video), page.video]) {
    const abs = path.join(args.studies, id, rel);
    if (fs.existsSync(abs)) return { file: rel.replace(/\\/g, "/"), sha256: sha(abs) };
  }
  return null;
};

// one profile per viewport, from what the tool measured inside the captured region
function profileFor(id, st, region, viewport) {
  const page = primary(st, viewport);
  const same = regionsOf(page).find((r) => r.selector === region.selector);
  if (!same) return { kind: "TODO static|interactive", driver: `TODO re-study with --region ${region.selector} (unmeasured at ${viewport})`, medium: "TODO", composition: "TODO", pacing: "TODO", sequence: ["TODO"], mechanisms: [], evidence: [] };
  const measured = measuredIn(page, same);
  const interactive = measured.length > 0 || (same.media || []).some((m) => ["video", "canvas"].includes(m));
  const driver = interactive ? (measured.find((m) => ["scroll", "time", "pointer"].includes(m.driver))?.driver || "TODO scroll|time|hover|pointer|click") : "static";
  const medium = (same.media || [])[0] || (same.words > 0 ? "typography" : "TODO image|video|canvas|svg|background|typography");
  const evidence = [same.evidence];
  const video = interactive ? videoEvidence(id, page) : null;
  if (video) evidence.push(video);
  return {
    kind: interactive ? "interactive" : "static",
    driver,
    medium,
    composition: "TODO the arrangement and the image or type relationship a visitor sees",
    pacing: interactive ? "TODO how the sequence progresses" : "TODO why the composition holds still",
    sequence: interactive ? ["TODO first state", "TODO second state"] : ["settled"],
    mechanisms: uniq(measured.map((m) => m.type)),
    evidence,
  };
}

const references = [];
const sections = [];
for (const id of args.select) {
  const st = studies.get(id);
  const wide = primary(st, "wide"), narrow = primary(st, "narrow");
  const drivers = uniq([...(wide?.motion?.mechanisms || []), ...(narrow?.motion?.mechanisms || [])].map((m) => `${m.type}:${m.driver || "scroll"}`));
  const gaps = st.observation_gaps || [];
  const regions = regionsOf(wide);
  const first = regions[0];
  const spec = first
    ? { page: wide.url, selector: first.selector, wide: profileFor(id, st, first, "wide"), narrow: profileFor(id, st, first, "narrow") }
    : { page: wide?.url || st.url, selector: "TODO exact region selector: re-study with --region SEL", wide: { kind: "TODO", driver: "TODO", medium: "TODO", composition: "TODO", pacing: "TODO", sequence: ["TODO"], mechanisms: [], evidence: [] }, narrow: { kind: "TODO", driver: "TODO", medium: "TODO", composition: "TODO", pacing: "TODO", sequence: ["TODO"], mechanisms: [], evidence: [] } };
  references.push({
    id, url: st.url,
    source_id: "TODO registry id: awwwards | typewolf | site-of-sites | godly | minimal-gallery",
    source_url: "TODO the listing page on that source that names this site",
    quality: { desktop: "TODO what its desktop experience is, in your own words", mobile: "TODO what its phone experience is", readability: "TODO sizes, contrast, text over photos", navigation: "TODO can a visitor find and do things", reliability: "TODO loaded at both widths, overlays, redirects", suitability: "TODO why its design relationships fit THIS content and these visitor tasks" },
    contributes: "TODO what this site gives the build (dominant grammar, one component, one behavior)",
    signature: "TODO one sentence with a verb: what a stranger would say they noticed",
    signature_mechanisms: uniq([...(spec.wide.mechanisms || []), ...(spec.narrow.mechanisms || [])]),
    detected_mechanisms: drivers,
    signature_spec: spec,
    ...(gaps.length ? {
      gaps_reviewed: `TODO how each gap was inspected by hand before copying: ${uniq(gaps.map((g) => g.code)).join(", ")}`,
      gap_reviews: gaps.map((g) => ({ code: g.code, page: g.page || "home", viewport: g.viewport || "wide", disposition: "TODO inspected|excluded", method: "TODO", observed: "TODO", artifacts: [{ file: "TODO path/to/capture.png", sha256: "TODO" }] })),
    } : {}),
    ...(st.mode === "quick" ? { _warning: "TODO QUICK LOOK ONLY: run the full study before selecting" } : {}),
  });
  // one section stub per captured region: the region's own composition, transferred
  for (const [i, region] of regions.entries()) {
    const wideP = i === 0 ? spec.wide : profileFor(id, st, region, "wide");
    const narrowP = i === 0 ? spec.narrow : profileFor(id, st, region, "narrow");
    const transfer = (p) => ({ reference: id, medium: p.medium, driver: p.driver, mechanisms: p.mechanisms, sequence: p.sequence, steps: [{ action: "rest", expect: { selector: "TODO .child", visibility: "visible" } }] });
    sections.push({
      selector: `TODO .section-${sections.length + 1}`, reference: id,
      source_region: { page: wide.url, selector: region.selector },
      ...(i === 0 ? { signature_from: [id], signature_transfer: { wide: transfer(wideP), narrow: transfer(narrowP) } } : {}),
      content: "TODO what goes in it", composition: "TODO how it is arranged", image_role: "TODO or none", typography_role: "TODO which face does what",
      behavior: wideP.mechanisms.length ? `${wideP.mechanisms.join(" ")} (${wideP.driver})` : "none",
      behavior_narrow: narrowP.mechanisms.length ? `${narrowP.mechanisms.join(" ")} (${narrowP.driver})` : "none",
      mobile: "TODO how it recomposes",
    });
  }
}
// dominant first in the section order
sections.sort((a, b) => (a.reference === args.dominant ? 0 : 1) - (b.reference === args.dominant ? 0 : 1));
if (!sections.length) sections.push({ selector: "TODO .hero", reference: args.dominant, source_region: { page: studies.get(args.dominant).url, selector: "TODO re-study the dominant with --region" }, content: "TODO", composition: "TODO", image_role: "TODO or none", typography_role: "TODO", behavior: "TODO or none", mobile: "TODO" });
const domSections = sections.filter((s) => s.reference === args.dominant).map((s) => s.selector);
const system_sections = { opening: domSections[0] || "TODO selector of a dominant-owned section", navigation: domSections[1] || "TODO selector of a dominant-owned section", ending: domSections[2] || "TODO selector of a dominant-owned section" };

// typefaces: families by characters set, from the dominant first, with their sources
const faceRows = [];
for (const id of [args.dominant, ...args.select.filter((x) => x !== args.dominant)]) {
  const wide = primary(studies.get(id), "wide");
  const sources = wide?.design?.face_sources || [];
  for (const f of wide?.design?.fonts || []) {
    const src = sources.find((x) => norm(x.family).toLowerCase() === norm(f.family).toLowerCase());
    faceRows.push({ family: norm(f.family), from: id, characters: f.characters || 0, google: src ? GOOGLE.test(src.src || "") : false });
  }
}
faceRows.sort((a, b) => b.characters - a.characters);
const seen = new Set(); const typefaces = [];
for (const r of faceRows) {
  const k = r.family.toLowerCase(); if (seen.has(k) || /icon/i.test(k)) continue; seen.add(k);
  typefaces.push(r.google ? { family: r.family, from: r.from } : { family: `TODO rank-one match for ${r.family} (measure_faces.mjs then match_typeface.mjs --target)`, from: r.from, matched_for: r.family, match_record: "TODO .design-dna/typeface-match.json" });
  if (typefaces.length === 2) break;
}
const domWide = primary(studies.get(args.dominant), "wide");
const g0 = domWide?.ground_sampled?.grounds?.[0];
const ground = g0 ? { color: g0.color, from: args.dominant, share_sampled: g0.share } : { color: domWide?.design?.grounds?.[0]?.color || "TODO", from: args.dominant };

const plan = {
  project: "TODO project name",
  written: new Date().toISOString().slice(0, 10),
  owner_selection: {candidates: [], user_instructions: 'TODO preserve the actual user selection after presenting ten websites', choices: []},
  references,
  studied_not_selected: [...studies.keys()].filter((id) => !args.select.includes(id)).map((id) => ({ id, why: "TODO why it was not selected" })),
  typefaces,
  ground,
  routes: [{ url: args.route, name: "home", dominant: args.dominant, system_sections, sections }],
  review: { reviewer: "self", file: ".design-dna/review.md" },
  _notes: [
    "Fill every TODO; the check refuses a plan that still says TODO anywhere.",
    "One section per major part of the page. A section uses only what its own reference or the route's dominant computes; palette_from / behavior_from name another selected reference for a color or a behavior.",
    "signature_spec came from the regions the full study captured; if a reference has none, re-study it with --region and run the scaffold again.",
    "Add states only to a section that holds still; remove behavior_narrow when it equals behavior.",
  ],
};
fs.mkdirSync(path.dirname(path.resolve(args.out)), { recursive: true });
fs.writeFileSync(args.out, JSON.stringify(plan, null, 2) + "\n");
process.stdout.write(JSON.stringify({
  ok: true, out: args.out,
  references: references.map((r) => ({ id: r.id, mechanisms: r.detected_mechanisms, regions: regionsOf(primary(studies.get(r.id), "wide")).length, quick: !!r._warning })),
  sections: sections.length, typefaces, ground,
  todos: (JSON.stringify(plan).match(/\bTODO\b/g) || []).length,
}, null, 2) + "\n");
