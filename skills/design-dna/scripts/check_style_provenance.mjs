#!/usr/bin/env node
/**
 * check_style_provenance.mjs
 *
 * Every value in the finished build has to come from a value somebody
 * measured on a reference. This check reads the build's own computed design
 * system and asks, of each color, typeface, size, radius, border, control
 * and transition in it: which reference did this come from?
 *
 * It exists because of a specific, repeated failure. A build cited five
 * references, carried their loudest recorded mechanism, wrote a source line
 * and a capture frame against every component, and passed every gate that
 * read those lines. Then it was measured. Its neutrals traced to the
 * references within a few points. Its accent color, the single loudest
 * decision on the page and the fill of every button, was 94 points from
 * anything any reference computed. Its display face was on no reference; it
 * had been picked by matching an x-height ratio, which is how a producer
 * chooses a typeface by taste and records arithmetic as the reason.
 *
 * No gate that reads prose can catch that, because the producer writes the
 * prose. This one never reads a sentence. It reads two JSON records that
 * came out of a browser and subtracts one from the other.
 *
 * PASS is not "most of it traces". Three things fail outright:
 *   - a typeface the references do not use
 *   - a LOUD color the references do not compute, meaning one filling a
 *     control, a section ground, or a measurable share of the screen
 *   - an overall traced share below the floor
 * Quiet one-off values are reported and tolerated; the loud ones are the
 * design, and the design is not the producer's to choose.
 *
 * Usage:
 *   node check_style_provenance.mjs \
 *     --build .design-dna/evidence/build-index-styles.json \
 *     --build .design-dna/evidence/build-deals-styles.json \
 *     --reference .design-dna/references/strong-1-styles.json \
 *     --reference .design-dna/references/strong-2-styles.json \
 *     --out .design-dna/evidence/style-provenance.json
 *
 * Produce a --build record by pointing the reference extractor at the running
 * build, which is the whole point: the same reader, so the two records are
 * comparable.
 *   node extract_reference_styles.mjs --url http://127.0.0.1:4830/ \
 *     --id build-index --out .design-dna/evidence
 */
import fs from "node:fs";
import process from "node:process";

const TOOL_NAME = "check_style_provenance.mjs";
const SCHEMA_VERSION = 1;

/* A color is traced when it is within this sum-of-absolute-RGB distance of
   something a reference computes. 12 is about a point per channel of rounding
   plus a little: it forgives a value retyped from a screenshot, and refuses a
   different color. */
const COLOR_TOLERANCE = 12;
/* A color is LOUD when it fills a control, fills a section, or covers at least
   this share of the screen. Loud colors are the palette. */
const LOUD_AREA = 0.004;
/* Sizes and radii are traced within these. */
const SIZE_TOLERANCE = 0.06;
const RADIUS_TOLERANCE = 1;
/* The share of all measured values that must trace. */
const TRACED_FLOOR = 0.85;
/* A share is a statistic, and a statistic over a handful of values is noise:
   with four values measured, one untraceable hairline gray reads as 75% and
   fails a build that is faithful. A real route measures around a hundred. Below
   this many, the share is not reported as a failure; the two hard failures, an
   untraceable typeface and an untraceable loud color, still apply at any size. */
const MIN_FOR_FLOOR = 20;

function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }, null, 2) + "\n");
  process.exit(2);
}

function parseArgs(argv) {
  const out = { builds: [], references: [], outFile: null, floor: TRACED_FLOOR, substitutes: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--build") out.builds.push(argv[++i]);
    else if (a === "--reference") out.references.push(argv[++i]);
    else if (a === "--out") out.outFile = argv[++i];
    else if (a === "--floor") out.floor = Number(argv[++i]);
    else if (a === "--substitute") out.substitutes.push(argv[++i]);
  }
  return out;
}

function readRecord(file) {
  let payload;
  try { payload = JSON.parse(fs.readFileSync(file, "utf8")); } catch (e) {
    fail("unreadable", `${file}: ${String(e).slice(0, 140)}`);
  }
  if (payload.tool !== "extract_reference_styles.mjs") {
    fail("not-a-style-record", `${file} did not come from extract_reference_styles.mjs.`);
  }
  return payload;
}

/* ---------------------------------------------------------------------- */

function rgb(value) {
  const m = String(value || "").match(/-?[\d.]+/g);
  if (!m || m.length < 3) return null;
  // fully transparent is not a color anybody sees
  if (m.length >= 4 && Number(m[3]) === 0) return null;
  return [Number(m[0]), Number(m[1]), Number(m[2])].map((n) => Math.round(n));
}

function colorDistance(a, b) {
  return Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]) + Math.abs(a[2] - b[2]);
}

/* "Geist Regular", "Geist Semi Bold" and "Geist" are one typeface. A producer
   that reaches for a different family must not be able to hide behind a style
   suffix, and must not be refused for using the reference's own face. */
const WEIGHT_WORDS = new RegExp(
  "\\b(regular|italic|oblique|thin|extralight|ultralight|light|book|normal|medium"
  + "|semibold|semi|demibold|demi|bold|extrabold|ultrabold|black|heavy"
  + "|variable|vf|std|pro|mt|ms|display|text|deck|caption|subhead)\\b",
  "gi"
);

function familyStem(name) {
  return String(name || "")
    .toLowerCase()
    .replace(/^gf;/, "")
    .replace(/["']/g, "")
    .split(",")[0]
    .replace(WEIGHT_WORDS, " ")
    .replace(/[^a-z0-9]+/g, "")
    .trim();
}

const GENERIC_FAMILIES = new Set([
  "", "serif", "sansserif", "monospace", "cursive", "fantasy", "systemui",
  "uisansserif", "uiserif", "uimonospace", "inherit", "initial",
  // stacks name fallbacks the browser may never paint with; they are not the
  // build's typeface and must not be judged as one
  "timesnewroman", "times", "georgia", "arial", "helvetica", "helveticaneue",
  "segoeui", "roboto", "applesystem", "blinkmacsystemfont", "couriernew",
]);

/* ---------------------------------------------------------------------- */

function referenceIndex(records) {
  const colors = [];      // { rgb, from }
  const families = new Map(); // stem -> from
  const sizes = [];       // { size, from }
  const radii = [];       // { px, raw, from }
  const borders = new Set();
  const transitions = new Set(); // "duration|easing"
  const controlGeom = [];  // { h, padding, from }
  const numbers = new Set();

  for (const r of records) {
    const from = r.id || r.url || "a reference";
    const addColor = (v) => { const c = rgb(v); if (c) colors.push({ rgb: c, from }); };
    for (const c of r.colors || []) addColor(c.value);
    for (const t of r.type || []) {
      addColor(t.color);
      const stem = familyStem(t.family);
      if (stem && !families.has(stem)) families.set(stem, from);
      const n = Number(t.size);
      if (Number.isFinite(n) && n > 0) sizes.push({ size: n, from });
    }
    for (const c of r.controls || []) {
      addColor(c.background); addColor(c.color);
      const h = Number(c.h);
      if (Number.isFinite(h)) controlGeom.push({ h, padding: String(c.padding || ""), from });
      for (const piece of String(c.radius || "").split(/\s+/)) {
        const n = parseFloat(piece);
        if (Number.isFinite(n)) radii.push({ px: n, raw: piece, from });
      }
    }
    for (const s of r.sections || []) addColor(s.background);
    for (const raw of r.radii || []) {
      for (const piece of String(raw).split(/\s+/)) {
        const n = parseFloat(piece);
        if (Number.isFinite(n)) radii.push({ px: n, raw: piece, from });
      }
    }
    for (const b of r.borders || []) borders.add(String(b).trim());
    for (const t of r.transitions || []) {
      transitions.add(`${String(t.duration || "").trim()}|${String(t.easing || "").trim()}`);
    }
    for (const n of r.numbers || []) numbers.add(n);
  }
  return { colors, families, sizes, radii, borders, transitions, controlGeom, numbers };
}

function traceColor(value, index) {
  const c = rgb(value);
  if (!c) return { traced: true, skip: true };
  let best = null, bd = Infinity;
  for (const ref of index.colors) {
    const d = colorDistance(c, ref.rgb);
    if (d < bd) { bd = d; best = ref; }
  }
  return {
    traced: bd <= COLOR_TOLERANCE,
    distance: bd === Infinity ? null : bd,
    nearest: best ? `rgb(${best.rgb.join(", ")})` : null,
    from: best ? best.from : null,
  };
}

function traceSize(size, index) {
  const n = Number(size);
  if (!Number.isFinite(n) || n <= 0) return { traced: true, skip: true };
  let best = null, bd = Infinity;
  for (const ref of index.sizes) {
    const d = Math.abs(ref.size - n) / Math.max(ref.size, 1);
    if (d < bd) { bd = d; best = ref; }
  }
  // a value the reference computes anywhere counts, because the type scale is
  // not the only place a size legitimately comes from
  if (index.numbers.has(Math.round(n * 1000) / 1000)) {
    return { traced: true, nearest: String(n), from: "a measured value" };
  }
  return {
    traced: bd <= SIZE_TOLERANCE,
    distance: bd === Infinity ? null : +bd.toFixed(3),
    nearest: best ? String(best.size) : null,
    from: best ? best.from : null,
  };
}

function traceRadius(raw, index) {
  const pieces = String(raw || "").split(/\s+/).filter(Boolean);
  const bad = [];
  for (const piece of pieces) {
    const n = parseFloat(piece);
    if (!Number.isFinite(n)) continue;
    if (n === 0) continue; // a square corner is the absence of a radius
    const hit = index.radii.some((r) => Math.abs(r.px - n) <= RADIUS_TOLERANCE);
    if (!hit) bad.push(piece);
  }
  return { traced: bad.length === 0, untraced: bad };
}

/* ---------------------------------------------------------------------- */

function auditBuild(build, index) {
  const findings = [];
  let checked = 0, traced = 0;
  const note = (dimension, value, where, res, loud) => {
    if (res.skip) return;
    checked += 1;
    if (res.traced) { traced += 1; return; }
    findings.push({
      dimension, value, where, loud: !!loud,
      nearest: res.nearest ?? null,
      distance: res.distance ?? null,
      nearest_from: res.from ?? null,
    });
  };

  // ---- typefaces -------------------------------------------------------
  const seenFamily = new Set();
  for (const t of build.type || []) {
    const stem = familyStem(t.family);
    if (!stem || GENERIC_FAMILIES.has(stem) || seenFamily.has(stem)) continue;
    seenFamily.add(stem);
    checked += 1;
    if (index.families.has(stem)) { traced += 1; continue; }
    findings.push({
      dimension: "typeface", value: t.family, where: `set at ${t.size}px, weight ${t.weight}`,
      loud: true, nearest: [...index.families.keys()].join(", ") || null,
      distance: null, nearest_from: null,
    });
  }

  // ---- colors ----------------------------------------------------------
  for (const c of build.colors || []) {
    const loud = (c.role === "background" && Number(c.area) >= LOUD_AREA) || Number(c.area) >= LOUD_AREA;
    note("color", c.value, `${c.role}, ${Math.round((c.area || 0) * 1000) / 10}% of the screen`,
      traceColor(c.value, index), loud);
  }
  for (const c of build.controls || []) {
    const bg = rgb(c.background);
    if (bg) {
      note("color", c.background, `the fill of a <${c.tag}> control`, traceColor(c.background, index), true);
    }
    note("color", c.color, `the text of a <${c.tag}> control`, traceColor(c.color, index), false);
  }
  for (const s of build.sections || []) {
    const bg = rgb(s.background);
    if (!bg) continue;
    const loud = Number(s.height_ratio || 0) >= 0.25;
    note("color", s.background, `the ground of a <${s.tag}> section`, traceColor(s.background, index), loud);
  }

  // ---- sizes -----------------------------------------------------------
  for (const t of build.type || []) {
    note("size", `${t.size}px`, `${t.family} ${t.weight}`, traceSize(t.size, index), false);
  }

  // ---- radii -----------------------------------------------------------
  const seenRadius = new Set();
  for (const c of build.controls || []) {
    const raw = String(c.radius || "").trim();
    if (!raw || seenRadius.has(raw)) continue;
    seenRadius.add(raw);
    const res = traceRadius(raw, index);
    checked += 1;
    if (res.traced) { traced += 1; continue; }
    findings.push({
      dimension: "radius", value: raw, where: `a <${c.tag}> control`, loud: true,
      nearest: index.radii.map((r) => r.raw).filter((v, i, a) => a.indexOf(v) === i).join(", ") || null,
      distance: null, nearest_from: null,
    });
  }

  // ---- transitions -----------------------------------------------------
  for (const t of build.transitions || []) {
    const key = `${String(t.duration || "").trim()}|${String(t.easing || "").trim()}`;
    checked += 1;
    if (index.transitions.has(key)) { traced += 1; continue; }
    findings.push({
      dimension: "transition", value: `${t.duration} ${t.easing}`,
      where: `${t.property} on ${t.count} elements`, loud: Number(t.count) >= 10,
      nearest: null, distance: null, nearest_from: null,
    });
  }

  return { route: build.id || build.url, checked, traced, findings };
}

/* ---------------------------------------------------------------------- */

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.builds.length || !args.references.length) {
    fail("usage", "check_style_provenance.mjs --build FILE... --reference FILE... [--out FILE] [--substitute FROM=TO]...");
  }
  const references = args.references.map(readRecord);
  const index = referenceIndex(references);
  if (!index.colors.length || !index.families.size) {
    fail("empty-references", "The reference records carry no colors or no typefaces to trace against.");
  }
  /* A paid face measured on a reference may be replaced by a free face matched
     to it, but only declared: the substitute traces to the reference the
     original was measured on, and the record says so. A face that substitutes
     nothing measured is still the producer's own choice. */
  const substitutes = [];
  for (const raw of args.substitutes) {
    const [from, to] = String(raw).split("=").map((v) => String(v || "").trim());
    const fromStem = familyStem(from);
    const toStem = familyStem(to);
    if (!from || !to || !index.families.has(fromStem)) {
      fail("bad-substitute", `--substitute ${raw}: '${from}' is not a family any selected reference measured.`);
    }
    const origin = index.families.get(fromStem);
    if (!index.families.has(toStem)) index.families.set(toStem, `${origin} (as the declared substitute for ${from})`);
    substitutes.push({ from, to, reference: origin });
  }

  const routes = args.builds.map(readRecord).map((b) => auditBuild(b, index));
  const checked = routes.reduce((n, r) => n + r.checked, 0);
  const traced = routes.reduce((n, r) => n + r.traced, 0);
  const findings = routes.flatMap((r) => r.findings.map((f) => ({ ...f, route: r.route })));
  const share = checked ? traced / checked : 0;

  const untracedFaces = findings.filter((f) => f.dimension === "typeface");
  const loudColors = findings.filter((f) => f.dimension === "color" && f.loud);
  const loudRadii = findings.filter((f) => f.dimension === "radius" && f.loud);

  /* One sentence per distinct offending value. Twenty controls filled with the
     same untraceable yellow is one decision, not twenty, and a verdict that
     repeats it twenty times is a verdict nobody reads. */
  const distinct = (rows) => {
    const seen = new Map();
    for (const f of rows) {
      const key = `${f.dimension}|${f.value}`;
      if (seen.has(key)) { seen.get(key).places += 1; continue; }
      seen.set(key, { ...f, places: 1 });
    }
    return [...seen.values()];
  };

  const reasons = [];
  for (const f of distinct(untracedFaces)) {
    reasons.push(
      `${f.value} is not a typeface any selected reference uses. The measured families are: ${f.nearest}. `
      + "A face chosen for its proportions is a face chosen by the producer."
    );
  }
  for (const f of distinct(loudColors)) {
    reasons.push(
      `${f.value} is ${f.distance} from the nearest color any reference computes `
      + `(${f.nearest}${f.nearest_from ? ` on ${f.nearest_from}` : ""}); it is on ${f.where}`
      + `${f.places > 1 ? ` and ${f.places - 1} more place${f.places > 2 ? "s" : ""}` : ""}. `
      + "A loud color is the palette."
    );
  }
  for (const f of distinct(loudRadii)) {
    reasons.push(`a corner radius of ${f.value} on ${f.where} is not a radius any reference computes.`);
  }
  if (checked >= MIN_FOR_FLOOR && share < args.floor) {
    reasons.push(
      `only ${Math.round(share * 100)}% of the build's ${checked} measured values trace to a `
      + `reference (floor ${Math.round(args.floor * 100)}%).`
    );
  }

  const ok = reasons.length === 0;
  const record = {
    ok,
    tool: TOOL_NAME,
    schema_version: SCHEMA_VERSION,
    checked_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    references: references.map((r) => ({ id: r.id, url: r.url })),
    substitutes,
    routes: routes.map((r) => ({
      route: r.route, checked: r.checked, traced: r.traced,
      traced_share: r.checked ? +(r.traced / r.checked).toFixed(3) : 0,
    })),
    checked,
    traced,
    traced_share: +share.toFixed(3),
    floor: args.floor,
    floor_applied: checked >= MIN_FOR_FLOOR,
    findings,
    verdict: ok
      ? "Every loud value in the build traces to a value measured on a selected reference."
      : "The build carries the producer's own design: " + reasons.join(" "),
  };

  if (args.outFile) fs.writeFileSync(args.outFile, JSON.stringify(record, null, 1), "utf8");
  process.stdout.write(JSON.stringify(record, null, 1) + "\n");
  process.exit(ok ? 0 : 1);
}

main();
