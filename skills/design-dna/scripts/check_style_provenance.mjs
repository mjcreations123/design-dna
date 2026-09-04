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
import { createHash } from "node:crypto";
import path from "node:path";
import process from "node:process";
import { aggregateServedContent } from "./browser_evidence.mjs";
import {
  loadRouteManifest,
  PRODUCER_OUTPUT_SCHEMA_VERSION,
  resolveMappedObservation,
} from "./provenance_contract.mjs";

const TOOL_NAME = "check_style_provenance.mjs";
const SCRIPT_PATH = path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const PRODUCER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(SCRIPT_PATH)).digest("hex");
const EXTRACTOR_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "extract_reference_styles.mjs"))).digest("hex");
const MATCHER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "match_typeface.mjs"))).digest("hex");
const OBSERVER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "observe_reference.mjs"))).digest("hex");
const BROWSER_EVIDENCE_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "browser_evidence.mjs"))).digest("hex");
const PLAYWRIGHT_RESOLVER_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "playwright_resolver.mjs"))).digest("hex");
const PROVENANCE_CONTRACT_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "provenance_contract.mjs"))).digest("hex");

function sha256File(file) {
  return createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}
const SCHEMA_VERSION = PRODUCER_OUTPUT_SCHEMA_VERSION;

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
  const out = { builds: [], references: [], outFile: null, floor: TRACED_FLOOR, substitutes: [], match: null,
    manifest: null, buildId: null, runId: null, routeKeys: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--build") out.builds.push(argv[++i]);
    else if (a === "--reference") out.references.push(argv[++i]);
    else if (a === "--out") out.outFile = argv[++i];
    else if (a === "--floor") out.floor = Number(argv[++i]);
    else if (a === "--substitute") out.substitutes.push(argv[++i]);
    else if (a === "--match") out.match = argv[++i];
    else if (a === "--manifest") out.manifest = argv[++i];
    else if (a === "--route-key") out.routeKeys.push(argv[++i]);
    else if (a === "--build-id") out.buildId = argv[++i];
    else if (a === "--run-id") out.runId = argv[++i];
    else if (a === "--help" || a === "-h") {
      process.stdout.write("check_style_provenance.mjs --manifest FILE --build FILE... --reference FILE... --build-id ID --run-id ID [--substitute FROM=TO --match FILE] --out FILE\n");
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${a}`);
  }
  return out;
}

function readRecord(file, { buildId = null, runId = null } = {}) {
  let payload;
  try {
    const stat = fs.lstatSync(file);
    if (!stat.isFile() || stat.isSymbolicLink()) throw new Error("record is not an ordinary file");
    payload = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (e) {
    fail("unreadable", `${file}: ${String(e).slice(0, 140)}`);
  }
  if (payload.tool !== "extract_reference_styles.mjs") {
    fail("not-a-style-record", `${file} did not come from extract_reference_styles.mjs.`);
  }
  if (payload.producer_script_sha256 !== EXTRACTOR_SCRIPT_SHA256) {
    fail("style-record-identity", `${file} was not emitted by the installed extract_reference_styles.mjs bytes.`);
  }
  if (payload.schema_version !== SCHEMA_VERSION) {
    fail("stale-style-record", `${file} predates current manifest, response-body, and DOM-surface provenance; re-run extract_reference_styles.mjs.`);
  }
  if (buildId && payload.build_id !== buildId) {
    fail("build-id-mismatch", `${file} belongs to build ${payload.build_id || "(none)"}, not ${buildId}.`);
  }
  if (runId && payload.run_id !== runId) fail("run-id-mismatch", `${file} was not generated by this gate invocation.`);
  const inspection = payload.inspection;
  if (!inspection || inspection.complete !== true || !Array.isArray(inspection.uninspectable) ||
      inspection.uninspectable.length || Number(inspection.canvases || 0) !== 0 ||
      !["pseudo_elements", "open_shadow_roots", "captured_closed_shadow_roots", "same_origin_iframes"]
        .every((field) => Number.isInteger(inspection[field]) && inspection[field] >= 0)) {
    fail("dom-inspection-incomplete", `${file} did not completely inspect pseudo-elements, shadow roots, iframes, and canvas surfaces.`);
  }
  const served = payload.served_content_identity || payload.served_content;
  const ledger = payload.resource_ledger;
  if (served?.complete !== true || !/^[0-9a-f]{64}$/.test(served.sha256 || "") ||
      !Array.isArray(served.probes) || !served.probes.length ||
      !served.reload_counts || Object.values(served.reload_counts).some((count) => !Number.isInteger(count) || count < 2) ||
      !Array.isArray(served.inconsistent_reloads) || served.inconsistent_reloads.length ||
      !ledger || Object.keys(ledger).sort().join("|") !== "algorithm|file|served_content_sha256|sha256" ||
      ledger.algorithm !== served.algorithm || ledger.served_content_sha256 !== served.sha256 ||
      !/^[0-9a-f]{64}$/.test(ledger.sha256 || "") || typeof ledger.file !== "string") {
    fail("resource-ledger-invalid", `${file} has no complete, hash-bound served-content resource ledger.`);
  }
  const ledgerFile = path.resolve(path.dirname(file), ledger.file);
  const recordRoot = path.dirname(path.resolve(file));
  const relativeLedger = path.relative(recordRoot, ledgerFile);
  let ledgerStat = null;
  let ledgerReal = null;
  try { ledgerStat = fs.lstatSync(ledgerFile); } catch { /* handled below */ }
  try { ledgerReal = fs.realpathSync(ledgerFile); } catch { /* handled below */ }
  if (!relativeLedger || relativeLedger.startsWith("..") || path.isAbsolute(relativeLedger) ||
      !ledgerStat?.isFile() || ledgerStat.isSymbolicLink() || !ledgerReal ||
      !ledgerReal.startsWith(fs.realpathSync(recordRoot) + path.sep) || sha256File(ledgerFile) !== ledger.sha256) {
    fail("resource-ledger-invalid", `${file} resource ledger path or bytes do not match its binding.`);
  }
  let ledgerPayload;
  try { ledgerPayload = JSON.parse(fs.readFileSync(ledgerFile, "utf8")); }
  catch (error) { fail("resource-ledger-invalid", `${file} resource ledger is unreadable: ${error.message}`); }
  if (JSON.stringify(ledgerPayload) !== JSON.stringify(served)) {
    fail("resource-ledger-invalid", `${file} served-content object does not equal its separately bound resource ledger.`);
  }
  if (payload.served_content && JSON.stringify(payload.served_content) !== JSON.stringify(served)) {
    fail("resource-ledger-invalid", `${file} carries contradictory served-content aliases.`);
  }
  return payload;
}

function expandServedContent(served, label) {
  const expanded = [];
  for (const probe of served.probes || []) {
    const key = `${probe.route_key || probe.requested_url}/${probe.viewport || "unknown"}`;
    const count = served.reload_counts?.[key];
    if (!Number.isInteger(count) || count < 2) {
      fail("served-content-reloads-incomplete", `${label} does not bind two stable response-body loads for ${key}.`);
    }
    for (let index = 0; index < count; index += 1) expanded.push(probe);
  }
  const recomputed = aggregateServedContent(expanded);
  if (recomputed.sha256 !== served.sha256 || JSON.stringify(recomputed) !== JSON.stringify(served)) {
    fail("served-content-identity-mismatch", `${label} served-content aggregate does not recompute from its exact probe and reload bindings.`);
  }
  return expanded;
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

const NON_FACES = new Set(["", "inherit", "initial", "unset"]);

function fingerprintKey(value) {
  if (!value || !/^[0-9a-f]{16}$/i.test(String(value.raster || "")) ||
      !Number.isFinite(Number(value.probe_width)) || !Number.isFinite(Number(value.ink))) return null;
  return `${value.raster}|${Number(value.probe_width).toFixed(3)}|${Number(value.ink)}`;
}

/* ---------------------------------------------------------------------- */

function referenceIndex(records) {
  const colors = [];      // { rgb, from }
  const families = new Map(); // stem -> from
  const familyObservationHashes = new Map(); // stem -> exact observation byte hashes
  const fontFingerprints = new Map(); // rendered raster/metrics -> source
  const sizes = [];       // { size, from }
  const radii = [];       // { px, raw, from }
  const borders = new Set();
  const transitions = new Set(); // "duration|easing"
  const controlGeom = [];  // { h, padding, from }
  const numbers = new Set();
  const spacingNumbers = new Set();
  const borderNumbers = new Set();
  const opacityValues = [];

  for (const r of records) {
    const from = r.id || r.url || "a reference";
    const addColor = (v) => { const c = rgb(v); if (c) colors.push({ rgb: c, from }); };
    for (const c of r.colors || []) addColor(c.value);
    for (const t of r.type || []) {
      addColor(t.color);
      const stem = familyStem(t.family);
      if (stem && !families.has(stem)) families.set(stem, from);
      if (stem && r.source_observation?.sha256) {
        if (!familyObservationHashes.has(stem)) familyObservationHashes.set(stem, new Set());
        familyObservationHashes.get(stem).add(r.source_observation.sha256);
      }
      const fingerprint = fingerprintKey(t.font_fingerprint);
      if (fingerprint && !fontFingerprints.has(fingerprint)) fontFingerprints.set(fingerprint, from);
      const n = Number(t.size);
      if (Number.isFinite(n) && n > 0) sizes.push({ size: n, from });
    }
    for (const c of r.controls || []) {
      addColor(c.background); addColor(c.color);
      const h = Number(c.h);
      if (Number.isFinite(h)) controlGeom.push({
        h, padding: String(c.padding || ""), radius: String(c.radius || ""),
        border_width: String(c.border_width || ""), border_style: String(c.border_style || ""), from,
      });
      numericValues(c.padding).forEach((value) => spacingNumbers.add(value));
      numericValues(c.border_width || c.border).forEach((value) => borderNumbers.add(value));
      for (const piece of String(c.radius || "").split(/\s+/)) {
        const n = parseFloat(piece);
        if (Number.isFinite(n)) radii.push({ px: n, raw: piece, from });
      }
    }
    for (const s of r.sections || []) {
      addColor(s.background);
      numericValues(s.padding).forEach((value) => spacingNumbers.add(value));
      numericValues(s.gap).forEach((value) => spacingNumbers.add(value));
      numericValues(s.border_width).forEach((value) => borderNumbers.add(value));
      if (Number.isFinite(Number(s.opacity))) opacityValues.push(Number(s.opacity));
    }
    for (const pseudo of r.pseudo_elements || []) {
      addColor(pseudo.background); addColor(pseudo.color); addColor(pseudo.border_color);
      const stem = familyStem(pseudo.font_family);
      if (stem && !families.has(stem)) families.set(stem, from);
      if (stem && r.source_observation?.sha256) {
        if (!familyObservationHashes.has(stem)) familyObservationHashes.set(stem, new Set());
        familyObservationHashes.get(stem).add(r.source_observation.sha256);
      }
      const size = parseFloat(pseudo.font_size);
      if (Number.isFinite(size) && size > 0) sizes.push({ size, from });
      numericValues(pseudo.border_width).forEach((value) => borderNumbers.add(value));
      for (const piece of String(pseudo.radius || "").split(/\s+/)) {
        const value = parseFloat(piece); if (Number.isFinite(value)) radii.push({ px: value, raw: piece, from });
      }
      if (Number.isFinite(Number(pseudo.opacity))) opacityValues.push(Number(pseudo.opacity));
    }
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
  const surfaces = records.flatMap((record) => [
    ...(record.surfaces || []),
    ...(record.pseudo_elements || []).map((pseudo) => ({
      tag: pseudo.pseudo, cls: pseudo.owner_class, padding: null, gap: null,
      radius: pseudo.radius, border_width: pseudo.border_width,
      shadow: pseudo.shadow, background_image: pseudo.background_image,
      opacity: pseudo.opacity, transform: pseudo.transform, area: 0,
    })),
  ].map((surface) => ({ ...surface, from: record.id || record.url || "a reference" })));
  for (const surface of surfaces) {
    numericValues(surface.padding).forEach((value) => spacingNumbers.add(value));
    numericValues(surface.gap).forEach((value) => spacingNumbers.add(value));
    numericValues(surface.border_width).forEach((value) => borderNumbers.add(value));
    if (Number.isFinite(Number(surface.opacity))) opacityValues.push(Number(surface.opacity));
  }
  return { colors, families, familyObservationHashes, fontFingerprints, substituteFingerprints: new Map(), sizes, radii, borders,
    transitions, controlGeom, numbers, spacingNumbers, borderNumbers, opacityValues, surfaces };
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

function numericValues(raw) {
  return (String(raw || "").match(/-?\d*\.?\d+/g) || []).map(Number).filter(Number.isFinite);
}

function traceNumbers(raw, index, tolerance = 1) {
  const values = numericValues(raw);
  if (!values.length) return { traced: true, skip: true };
  const untraced = values.filter((value) => ![...index.numbers].some((reference) => Math.abs(Number(reference) - value) <= tolerance));
  return { traced: untraced.length === 0, untraced };
}

function traceNumberSet(raw, values, tolerance = 1) {
  const measured = numericValues(raw);
  if (!measured.length) return { traced: true, skip: true };
  const untraced = measured.filter((value) => ![...values].some((reference) => Math.abs(Number(reference) - value) <= tolerance));
  return { traced: untraced.length === 0, untraced };
}

function functionKinds(raw) {
  return [...String(raw || "").matchAll(/([a-z-]+)\(/gi)].map((match) => match[1].toLowerCase());
}

function surfaceFinding(surface, index) {
  const failures = [];
  for (const [name, value, source] of [["padding", surface.padding, index.spacingNumbers],
    ["gap", surface.gap, index.spacingNumbers], ["border-width", surface.border_width, index.borderNumbers]]) {
    const result = traceNumberSet(value, source);
    if (!result.traced) failures.push(`${name} ${result.untraced.join("/")}`);
  }
  const radius = traceRadius(surface.radius, index);
  if (!radius.traced) failures.push(`radius ${radius.untraced.join("/")}`);
  const requireKind = (dimension, value, field) => {
    if (!value) return;
    const wanted = functionKinds(value);
    if (!wanted.length) return;
    const available = new Set(index.surfaces.flatMap((reference) => functionKinds(reference[field])));
    for (const kind of wanted) if (!available.has(kind)) failures.push(`${dimension} ${kind}()`);
  };
  requireKind("background", surface.background_image, "background_image");
  requireKind("transform", surface.transform, "transform");
  if (surface.shadow && !index.surfaces.some((reference) => String(reference.shadow || "").replace(/\s+/g, " ").trim() === String(surface.shadow).replace(/\s+/g, " ").trim())) failures.push("shadow");
  if (Number(surface.opacity) < 0.999 && !index.opacityValues.some((value) => Math.abs(value - Number(surface.opacity)) <= 0.05)) failures.push(`opacity ${surface.opacity}`);
  return failures;
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
    const fingerprint = fingerprintKey(t.font_fingerprint);
    const identity = `${stem}|${fingerprint || "missing"}`;
    if (NON_FACES.has(stem) || seenFamily.has(identity)) continue;
    seenFamily.add(identity);
    checked += 1;
    if (fingerprint && index.fontFingerprints.has(fingerprint)) { traced += 1; continue; }
    const substitute = index.substituteFingerprints.get(stem);
    if (fingerprint && substitute && substitute === fingerprint) { traced += 1; continue; }
    if (!fingerprint) {
      findings.push({
        dimension: "font-evidence", value: t.family, where: `set at ${t.size}px, weight ${t.weight}`,
        loud: true, nearest: null, distance: null, nearest_from: null,
      });
      continue;
    }
    if (index.families.has(stem)) {
      findings.push({
        dimension: "font-rendering", value: t.family, where: `set at ${t.size}px, weight ${t.weight}`,
        loud: true, nearest: "same declared family with different rendered glyphs", distance: null,
        nearest_from: index.families.get(stem),
      });
      continue;
    }
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

  // ---- control geometry ------------------------------------------------
  for (const control of build.controls || []) {
    const height = Number(control.h);
    if (!Number.isFinite(height)) continue;
    checked += 1;
    const hit = index.controlGeom.find((reference) => {
      const closeHeight = Math.abs(reference.h - height) / Math.max(reference.h, 1) <= SIZE_TOLERANCE;
      const padding = traceNumbers(control.padding, { ...index, numbers: new Set(numericValues(reference.padding)) });
      const borderWidth = traceNumbers(control.border_width, { ...index, numbers: new Set(numericValues(reference.border_width)) });
      return closeHeight && padding.traced && borderWidth.traced && String(reference.border_style || "") === String(control.border_style || "");
    });
    if (hit) traced += 1;
    else findings.push({
      dimension: "control-geometry", value: `${height}px high; ${control.padding}; ${control.border_width} ${control.border_style}`,
      where: `<${control.tag}> ${control.cls || "control"}`, loud: true,
      nearest: index.controlGeom.slice(0, 6).map((reference) => `${reference.h}px/${reference.padding}/${reference.border_width} ${reference.border_style}`).join(", ") || null,
      distance: null, nearest_from: null,
    });
  }

  // ---- visible layout/surface values ----------------------------------
  for (const surface of build.surfaces || []) {
    const failures = surfaceFinding(surface, index);
    checked += 1;
    if (!failures.length) { traced += 1; continue; }
    findings.push({
      dimension: "surface", value: failures.join("; "),
      where: `<${surface.tag}> ${surface.cls || "unclassed"} (${Math.round(Number(surface.area || 0) * 100)}% viewport)`,
      loud: Number(surface.area || 0) >= 0.04,
      nearest: null, distance: null, nearest_from: null,
    });
  }

  // ---- generated pseudo-element design -------------------------------
  for (const pseudo of build.pseudo_elements || []) {
    const where = `${pseudo.pseudo} on <${pseudo.owner_tag}> ${pseudo.owner_class || "unclassed"}`;
    for (const [role, value] of [["pseudo-background", pseudo.background], ["pseudo-text", pseudo.color],
      ["pseudo-border", pseudo.border_color]]) {
      note("color", value, `${role} at ${where}`, traceColor(value, index), true);
    }
    const stem = familyStem(pseudo.font_family);
    if (stem && !index.families.has(stem)) {
      checked += 1;
      findings.push({ dimension: "pseudo-typeface", value: pseudo.font_family, where, loud: true,
        nearest: [...index.families.keys()].join(", ") || null, distance: null, nearest_from: null });
    } else if (stem) { checked += 1; traced += 1; }
    const surface = {
      tag: pseudo.pseudo, cls: pseudo.owner_class, padding: null, gap: null,
      radius: pseudo.radius, border_width: pseudo.border_width,
      shadow: pseudo.shadow, background_image: pseudo.background_image,
      opacity: pseudo.opacity, transform: pseudo.transform,
    };
    const failures = surfaceFinding(surface, index);
    checked += 1;
    if (!failures.length) traced += 1;
    else findings.push({ dimension: "pseudo-surface", value: failures.join("; "), where, loud: true,
      nearest: null, distance: null, nearest_from: null });
  }

  return {
    route: build.id || build.url,
    route_key: build.route_key || null,
    viewport: build.viewport || null,
    checked,
    traced,
    findings,
  };
}

/* ---------------------------------------------------------------------- */

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.manifest || !args.builds.length || !args.references.length || !args.buildId || !args.runId) {
    fail("usage", "check_style_provenance.mjs --manifest FILE --build FILE... --reference FILE... --build-id ID --run-id ID [--out FILE] [--substitute FROM=TO --match typeface-match.json]...");
  }
  let manifest;
  try { manifest = loadRouteManifest(args.manifest); }
  catch (error) { fail("manifest-invalid", String(error).slice(0, 500)); }
  if (args.routeKeys.some((key) => !manifest.routes.some((route) => route.key === key))) {
    fail("route-key-missing", "Every --route-key must exist in the manifest.");
  }
  const activeRoutes = args.routeKeys.length ? manifest.routes.filter((route) => args.routeKeys.includes(route.key)) : manifest.routes;
  const mappedBySha = new Map();
  for (const route of activeRoutes) {
    let binding;
    try { binding = resolveMappedObservation(manifest, route, OBSERVER_SCRIPT_SHA256); }
    catch (error) { fail("manifest-reference-binding-invalid", String(error).slice(0, 500)); }
    mappedBySha.set(binding.sha256, binding);
  }
  const references = args.references.map((file) => readRecord(file));
  const referenceByObservation = new Map();
  for (const reference of references) {
    const source = reference.source_observation;
    if (!source || typeof source !== "object" || !mappedBySha.has(source.sha256) ||
        source.id !== mappedBySha.get(source.sha256).id || source.url !== mappedBySha.get(source.sha256).url ||
        source.file !== mappedBySha.get(source.sha256).observation) {
      fail("reference-style-observation-mismatch", `${reference.id || "reference style record"} is not bound to an exact observation selected by the route manifest.`);
    }
    if (referenceByObservation.has(source.sha256)) fail("reference-style-duplicate", `More than one style record binds observation ${source.sha256}.`);
    referenceByObservation.set(source.sha256, reference);
  }
  const missingReferenceStyles = [...mappedBySha.keys()].filter((digest) => !referenceByObservation.has(digest));
  if (missingReferenceStyles.length || referenceByObservation.size !== mappedBySha.size) {
    fail("reference-style-coverage", "Exactly one current style record is required for every exact manifest-mapped observation.");
  }
  const index = referenceIndex(references);
  if (!index.colors.length || !index.families.size) {
    fail("empty-references", "The reference records carry no colors or no typefaces to trace against.");
  }
  /* A paid face measured on a reference may be replaced by a free face matched
     to it, but only declared: the substitute traces to the reference the
     original was measured on, and the record says so. A face that substitutes
     nothing measured is still the producer's own choice. */
  /* The producer does not choose faces. A substitute is accepted only when
     match_typeface.mjs ranked it first for the family it replaces, by the
     same measurement the observation made of the reference. The owner's
     order (2026-09-03): "this includes designs, layouts, fonts, and
     everything else." */
  let matchRecord = null;
  let matchMeta = null;
  if (args.substitutes.length) {
    if (!args.match) {
      fail("bad-substitute", "--substitute needs --match <typeface-match.json> from match_typeface.mjs; a substitute face the matcher did not rank first is the producer's choice, which is forbidden.");
    }
    try {
      matchRecord = JSON.parse(fs.readFileSync(args.match, "utf8"));
    } catch (e) {
      fail("bad-match", `Could not read ${args.match}: ${e.message}`);
    }
    if (!matchRecord || matchRecord.tool !== "match_typeface.mjs" || matchRecord.schema_version !== SCHEMA_VERSION ||
        matchRecord.producer_script_sha256 !== MATCHER_SCRIPT_SHA256 ||
        matchRecord.runtime_identity?.["observe_reference.mjs"] !== OBSERVER_SCRIPT_SHA256 ||
        matchRecord.runtime_identity?.["playwright_resolver.mjs"] !== PLAYWRIGHT_RESOLVER_SHA256 ||
        matchRecord.verified_browser_measurement !== true || !Array.isArray(matchRecord.results) ||
        !Array.isArray(matchRecord.input_observations)) {
      fail("bad-match", `${args.match} is not a verified current-schema browser measurement bound to current observation bytes.`);
    }
    const matchInputs = [...matchRecord.input_observations].sort((a, b) => String(a.sha256).localeCompare(String(b.sha256)));
    const inputSetHash = createHash("sha256")
      .update(JSON.stringify(matchInputs.map((item) => ({ id: item.id, url: item.url, sha256: item.sha256 }))))
      .digest("hex");
    if (inputSetHash !== matchRecord.observation_set_sha256 ||
        matchInputs.some((item) => !mappedBySha.has(item.sha256) || mappedBySha.get(item.sha256).id !== item.id ||
          mappedBySha.get(item.sha256).url !== item.url)) {
      fail("bad-match", `${args.match} input-observation set is not the exact manifest-selected observation byte set.`);
    }
    matchMeta = { file: args.match, sha256: sha256File(args.match) };
  }
  const substitutes = [];
  for (const raw of args.substitutes) {
    const [from, to] = String(raw).split("=").map((v) => String(v || "").trim());
    const fromStem = familyStem(from);
    const toStem = familyStem(to);
    if (!from || !to || !index.families.has(fromStem)) {
      fail("bad-substitute", `--substitute ${raw}: '${from}' is not a family any selected reference measured.`);
    }
    const origin = index.families.get(fromStem);
    const chosenFor = matchRecord.results.find((r) => r && r.target && familyStem(r.target.family) === fromStem);
    if (!chosenFor || !chosenFor.chosen) {
      fail("bad-substitute", `--substitute ${raw}: match_typeface.mjs ranked nothing for '${from}'. Run it with the observation that measured ${from}.`);
    }
    const allowedObservationHashes = index.familyObservationHashes.get(fromStem) || new Set();
    if (!allowedObservationHashes.has(chosenFor.target?.observation_sha256) ||
        !mappedBySha.has(chosenFor.target?.observation_sha256) ||
        !matchRecord.input_observations.some((item) => item?.sha256 === chosenFor.target.observation_sha256)) {
      fail("bad-match", `--substitute ${raw}: the matcher target is not bound to the exact selected observation bytes that measured '${from}'.`);
    }
    const rankedFirst = Array.isArray(chosenFor.ranked) ? chosenFor.ranked[0] : null;
    if (!rankedFirst || familyStem(rankedFirst.family) !== familyStem(chosenFor.chosen.family) ||
        String(rankedFirst.weight) !== String(chosenFor.chosen.weight) || Number(rankedFirst.delta) !== Number(chosenFor.chosen.delta)) {
      fail("bad-match", `--substitute ${raw}: chosen is not the exact first ranked measurement row.`);
    }
    if (familyStem(chosenFor.chosen.family) !== toStem) {
      fail("bad-substitute", `--substitute ${raw}: the matcher ranked '${chosenFor.chosen.family}' first for '${from}' (delta ${chosenFor.chosen.delta}), not '${to}'. The substitute is rank one; the producer does not choose faces.`);
    }
    const chosenFingerprint = fingerprintKey(chosenFor.chosen.font_fingerprint);
    if (!chosenFingerprint) {
      fail("bad-match", `--substitute ${raw}: the rank-one matcher result has no rendered-font fingerprint; re-run match_typeface.mjs.`);
    }
    if (!/^[0-9a-f]{64}$/.test(chosenFor.chosen.source_sha256 || "") || !/^https:\/\//.test(chosenFor.chosen.source_url || "")) {
      fail("bad-match", `--substitute ${raw}: the rank-one browser measurement does not bind the fetched font bytes.`);
    }
    if (!index.families.has(toStem)) index.families.set(toStem, `${origin} (as the matched substitute for ${from})`);
    index.substituteFingerprints.set(toStem, chosenFingerprint);
    substitutes.push({
      from, to, reference: origin,
      observation_sha256: chosenFor.target.observation_sha256,
      matcher_delta: chosenFor.chosen.delta,
      font_source_url: chosenFor.chosen.source_url,
      font_source_sha256: chosenFor.chosen.source_sha256,
    });
  }

  const builds = args.builds.map((file) => readRecord(file, { buildId: args.buildId, runId: args.runId }));
  const buildCells = new Map();
  const servedProbes = [];
  for (const build of builds) {
    if (build.manifest_id !== manifest.manifest_id || build.manifest_sha256 !== manifest.__sha256 ||
        !activeRoutes.some((route) => route.key === build.route_key) ||
        !manifest.viewports.some((viewport) => viewport.name === build.viewport)) {
      fail("build-style-manifest-mismatch", `${build.id || "build style record"} is not bound to an active route/profile in this exact manifest.`);
    }
    const key = `${build.route_key}|${build.viewport}`;
    if (buildCells.has(key)) fail("build-style-duplicate", `More than one build style record exists for ${key}.`);
    buildCells.set(key, build);
    const served = build.served_content_identity || build.served_content;
    if (served?.complete !== true || !Array.isArray(served.probes)) fail("served-content-invalid", `${build.id || key} has no complete response-body identity.`);
    servedProbes.push(...expandServedContent(served, build.id || key));
  }
  const expectedCells = activeRoutes.flatMap((route) => manifest.viewports.map((viewport) => `${route.key}|${viewport.name}`));
  if (expectedCells.some((key) => !buildCells.has(key)) || buildCells.size !== expectedCells.length) {
    fail("build-style-coverage", "Exactly one build style record is required for every active route/profile cell.");
  }
  const servedContent = aggregateServedContent(servedProbes);
  if (!servedContent.complete) fail("served-content-inconsistent", "Build style records were served from inconsistent response bodies.");
  const routes = builds.map((build) => auditBuild(build, index));
  const checked = routes.reduce((n, r) => n + r.checked, 0);
  const traced = routes.reduce((n, r) => n + r.traced, 0);
  const findings = routes.flatMap((r) => r.findings.map((f) => ({ ...f, route: r.route })));
  const share = checked ? traced / checked : 0;

  const untracedFaces = findings.filter((f) => ["typeface", "font-evidence", "font-rendering", "pseudo-typeface"].includes(f.dimension));
  const loudColors = findings.filter((f) => f.dimension === "color" && f.loud);
  const loudRadii = findings.filter((f) => f.dimension === "radius" && f.loud);
  const untracedSizes = findings.filter((f) => f.dimension === "size");
  const untracedTransitions = findings.filter((f) => f.dimension === "transition");
  const loudGeometry = findings.filter((f) => ["control-geometry", "surface", "pseudo-surface"].includes(f.dimension));

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
      f.dimension === "font-evidence"
        ? `${f.value} has no rendered glyph fingerprint; declared CSS family names are not proof of the face the browser painted.`
        : f.dimension === "font-rendering"
          ? `${f.value} names a reference family but renders different glyph bytes/metrics (${f.where}).`
          : `${f.value} is not a rendered typeface any selected reference uses. The measured families are: ${f.nearest}.`
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
  for (const f of distinct(untracedSizes)) reasons.push(`type size ${f.value} at ${f.where} is not in any selected reference's measured type scale.`);
  for (const f of distinct(untracedTransitions)) reasons.push(`transition ${f.value} at ${f.where} is not measured on a selected reference.`);
  for (const f of distinct(loudGeometry)) {
    reasons.push(`${f.dimension} at ${f.where} does not trace to a measured reference: ${f.value}.`);
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
    producer_script_sha256: PRODUCER_SCRIPT_SHA256,
    runtime_identity: {
      "check_style_provenance.mjs": PRODUCER_SCRIPT_SHA256,
      "extract_reference_styles.mjs": EXTRACTOR_SCRIPT_SHA256,
      "match_typeface.mjs": MATCHER_SCRIPT_SHA256,
      "observe_reference.mjs": OBSERVER_SCRIPT_SHA256,
      "browser_evidence.mjs": BROWSER_EVIDENCE_SHA256,
      "playwright_resolver.mjs": PLAYWRIGHT_RESOLVER_SHA256,
      "provenance_contract.mjs": PROVENANCE_CONTRACT_SHA256,
    },
    checked_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    build_id: args.buildId,
    run_id: args.runId,
    manifest_id: manifest.manifest_id,
    manifest_file: args.manifest,
    manifest_sha256: manifest.__sha256,
    route_filter: args.routeKeys,
    served_content_identity: servedContent,
    input_hashes: {
      builds: args.builds.map((file) => ({ file, sha256: sha256File(file) })),
      references: args.references.map((file) => ({ file, sha256: sha256File(file) })),
    },
    references: references.map((r) => ({ id: r.id, url: r.url, source_observation: r.source_observation })),
    substitutes,
    typeface_match: matchMeta,
    routes: routes.map((r) => ({
      route: r.route, route_key: r.route_key, viewport: r.viewport,
      checked: r.checked, traced: r.traced,
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
