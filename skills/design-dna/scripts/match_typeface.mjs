#!/usr/bin/env node
/**
 * match_typeface.mjs
 *
 * The producer does not choose typefaces. This is the instrument that chooses
 * the substitute when a selected reference's family cannot be licensed.
 *
 * Why it exists, in the owner's words (2026-09-03): "There is absolutely no
 * using your design. You must only use the designs from the websites you are
 * copying from. And this includes designs, layouts, fonts, and everything
 * else." A build made the same day had paired Fraunces with Inter because
 * they "read as food-brand-appropriate", which is a taste decision with a
 * reason written next to it. An earlier build had picked Cormorant Garamond
 * by matching an x-height by hand, which is the same decision with
 * arithmetic written next to it.
 *
 * So: the observation session already measured the reference's display and
 * body faces with proportions a face cannot fake (x-height ratio, advance
 * width). This script measures candidate open-licence faces the SAME way,
 * in the same browser engine, and ranks them by distance. Rank one is the
 * substitute. check_style_provenance.mjs refuses any --substitute this
 * record did not rank first.
 *
 * Usage:
 *   node match_typeface.mjs \
 *     --observation .design-dna/references/strong-1-observation.json \
 *     [--observation ...] [--family "Louize Display"] \
 *     [--candidates "Fraunces:500,EB Garamond:400"] [--candidates-file FILE] \
 *     [--measured FILE]        (skip the browser; a JSON array of measured faces) \
 *     --out .design-dna/evidence/typeface-match.json \
 *     [--browser-executable FILE]
 *
 * Measurement (identical to structure_probe.mjs): at 100px, x_ratio is the
 * canvas ascent of "x" over the ascent of "H", advance is the width of
 * "Handgloves 0123" divided by 100, and i_ratio is the width of "I" over the
 * ascent of "H", which separates serif (brackets widen the I), sans and mono
 * (every glyph the same width). The distance is the sum of the relative
 * differences on every axis the target carries. Measured on live sites the
 * I width does not split serif from sans cleanly (Louize Display 0.342,
 * ABC Diatype 0.389, Tobias 0.44), so no serif/sans label is claimed; only
 * mono (0.8 and above) is a class. --posture mono|proportional keeps the
 * ranking inside one of those two when the target observation predates the
 * axis; it is measured geometry, not a choice.
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";

const TOOL_NAME = "match_typeface.mjs";
const SCHEMA_VERSION = 1;
/* The I-width axis is one glyph; x-height and advance are the texture of
   every line. Equal weights let the I override both (Louize Display, whose
   capitals carry tiny serifs, ranked a face with the wrong x-height and the
   wrong width first). At 0.4 the axis separates postures when the texture
   axes are close and cannot outrank them when they are not. */
const I_WEIGHT = 0.4;
const FONTS_CSS = "https://fonts.googleapis.com/css2";

/* A search space, not a shortlist: open-licence families across postures.
   Extend it with --candidates; the ranking, not the pool, makes the choice. */
const DEFAULT_CANDIDATES = [
  "Inter:400", "Inter:500", "Inter:700",
  "Geist:400", "Geist:500", "Geist:600",
  "DM Sans:400", "DM Sans:500", "DM Sans:700",
  "Figtree:400", "Figtree:500", "Figtree:700",
  "Hanken Grotesk:400", "Hanken Grotesk:500", "Hanken Grotesk:700",
  "Instrument Sans:400", "Instrument Sans:500", "Instrument Sans:700",
  "Public Sans:400", "Public Sans:500", "Public Sans:700",
  "Schibsted Grotesk:400", "Schibsted Grotesk:500", "Schibsted Grotesk:700",
  "Work Sans:400", "Work Sans:500", "Work Sans:700",
  "Manrope:400", "Manrope:500", "Manrope:700",
  "Plus Jakarta Sans:400", "Plus Jakarta Sans:500", "Plus Jakarta Sans:700",
  "Space Grotesk:400", "Space Grotesk:500", "Space Grotesk:700",
  "Archivo:400", "Archivo:500", "Archivo:700",
  "Roboto:400", "Roboto:500", "Roboto:700",
  "Noto Sans:400", "Noto Sans:500", "Noto Sans:700",
  "Cormorant Garamond:400", "Cormorant Garamond:500", "Cormorant Garamond:600",
  "EB Garamond:400", "EB Garamond:500", "EB Garamond:600",
  "Libre Caslon Display:400",
  "Libre Caslon Text:400", "Libre Caslon Text:700",
  "Newsreader:400", "Newsreader:500", "Newsreader:600",
  "Playfair Display:400", "Playfair Display:500", "Playfair Display:700",
  "Crimson Pro:400", "Crimson Pro:500", "Crimson Pro:600",
  "Fraunces:400", "Fraunces:500", "Fraunces:600",
  "Bodoni Moda:400", "Bodoni Moda:500", "Bodoni Moda:700",
  "Instrument Serif:400",
  "Lora:400", "Lora:500", "Lora:700",
  "Source Serif 4:400", "Source Serif 4:500", "Source Serif 4:600",
  "Literata:400", "Literata:500", "Literata:700",
  "Spectral:400", "Spectral:500", "Spectral:600",
  "DM Serif Display:400",
  "Texturina:400", "Texturina:500", "Texturina:700",
  "Geist Mono:400", "Geist Mono:500",
  "DM Mono:400", "DM Mono:500",
  "JetBrains Mono:400", "JetBrains Mono:500",
  "IBM Plex Mono:400", "IBM Plex Mono:500",
  "Space Mono:400", "Space Mono:700",
];

function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }, null, 2) + "\n");
  process.exit(2);
}

function parseArgs(argv) {
  const out = {
    observations: [], family: null, candidates: [], candidatesFile: null,
    measured: null, out: null, browser: undefined, posture: null,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--observation") out.observations.push(argv[++i]);
    else if (a === "--family") out.family = argv[++i];
    else if (a === "--candidates") out.candidates.push(...String(argv[++i]).split(",").map((s) => s.trim()).filter(Boolean));
    else if (a === "--candidates-file") out.candidatesFile = argv[++i];
    else if (a === "--measured") out.measured = argv[++i];
    else if (a === "--out") out.out = argv[++i];
    else if (a === "--browser-executable") out.browser = argv[++i];
    else if (a === "--posture") out.posture = String(argv[++i]).toLowerCase();
    else if (a === "--help" || a === "-h") {
      process.stdout.write("match_typeface.mjs --observation FILE... [--family NAME] [--candidates \"Family:weight,...\"] [--candidates-file FILE] [--measured FILE] --out FILE [--browser-executable FILE]\n");
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${a}`);
  }
  if (!out.observations.length) fail("invalid-observation", "--observation must name at least one observation session.");
  if (out.posture && !["mono", "proportional"].includes(out.posture)) fail("invalid-posture", "--posture must be mono or proportional.");
  if (!out.out) fail("invalid-out", "--out must name the record to write.");
  return out;
}

function sha256(file) {
  return createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function stem(family) {
  return String(family || "").toLowerCase().replace(/["']/g, "").split(",")[0].trim();
}

function loadPlaywright() {
  const dir = process.env.DESIGN_DNA_PLAYWRIGHT_MODULE_DIR;
  const require_ = createRequire(dir ? path.join(dir, "noop.js") : import.meta.url);
  for (const name of ["playwright", "playwright-core"]) {
    try { return require_(name); } catch { /* next */ }
  }
  fail("playwright-missing", "Playwright is not installed; set DESIGN_DNA_PLAYWRIGHT_MODULE_DIR to a node_modules that has it, or pass --measured with pre-measured candidates.");
  return null;
}

/* The targets: every face the observation measured on the reference. */
function targetsFrom(observationPath, familyFilter) {
  let payload;
  try {
    payload = JSON.parse(fs.readFileSync(observationPath, "utf8"));
  } catch (e) {
    fail("observation-unreadable", `Could not read ${observationPath}: ${e.message}`);
  }
  const type = payload && payload.first_screen && payload.first_screen.type;
  if (!type || typeof type !== "object") {
    fail("no-type-measurements", `${observationPath} carries no first_screen.type; re-run observe_reference.mjs (schema 3).`);
  }
  const targets = [];
  for (const role of ["display", "body"]) {
    const t = type[role];
    if (!t || !t.family || typeof t.x_ratio !== "number" || typeof t.advance !== "number") continue;
    if (familyFilter && stem(t.family) !== stem(familyFilter)) continue;
    targets.push({
      family: t.family, role, weight: String(t.weight || "400"),
      x_ratio: t.x_ratio, advance: t.advance,
      i_ratio: typeof t.i_ratio === "number" ? t.i_ratio : null,
      observation: path.relative(process.cwd(), observationPath).split(path.sep).join("/"),
      observation_sha256: sha256(observationPath),
    });
  }
  return targets;
}

async function measureCandidates(specs, browserPath) {
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({ executablePath: browserPath });
  const page = await browser.newPage();
  await page.goto("https://fonts.google.com/", { waitUntil: "domcontentloaded", timeout: 60000 });
  const rows = await page.evaluate(async ({ specs, cssBase }) => {
    const out = [];
    for (const spec of specs) {
      const [family, weight = "400"] = spec.split(":");
      const url = cssBase + "?family=" + family.replace(/ /g, "+") + ":wght@" + weight + "&display=block";
      try {
        const css = await (await fetch(url)).text();
        /* Google serves one @font-face block per subset, cyrillic-ext first.
           The first src has no Latin glyphs, so "H" and "x" fall back to the
           system face and every candidate measures the same ratio. Load the
           block whose unicode-range covers basic Latin. */
        const blocks = css.split("@font-face").slice(1);
        let src = null, subset = null;
        for (const block of blocks) {
          const range = (block.match(/unicode-range:\s*([^;]+);/) || [])[1] || "";
          const m = block.match(/src:\s*url\(([^)]+)\)/);
          if (!m) continue;
          const latin = /U\+0000-00FF/i.test(range) || /U\+0041/i.test(range);
          if (latin) { src = m[1]; subset = "latin"; break; }
          if (!src) { src = m[1]; subset = "first"; }
        }
        if (!src) { out.push({ family, weight, error: "no src in the css" }); continue; }
        const name = family.replace(/[^A-Za-z0-9]/g, "") + "_" + weight;
        const face = new FontFace(name, `url(${src})`, { weight });
        await face.load();
        document.fonts.add(face);
        const c = document.createElement("canvas").getContext("2d");
        c.font = `${weight} 100px "${name}"`;
        const H = c.measureText("H"), x = c.measureText("x");
        const cap = H.actualBoundingBoxAscent || 0;
        const xh = x.actualBoundingBoxAscent || 0;
        const adv = c.measureText("Handgloves 0123").width;
        const iw = c.measureText("I").width;
        out.push({ family, weight, subset, x_ratio: cap ? +(xh / cap).toFixed(3) : null, advance: +(adv / 100).toFixed(3), i_ratio: cap ? +(iw / cap).toFixed(3) : null });
      } catch (e) {
        out.push({ family, weight, error: String(e).slice(0, 60) });
      }
    }
    return out;
  }, { specs, cssBase: FONTS_CSS });
  await browser.close();
  return rows;
}

/* Posture from the I width: monos give every glyph the same width, so the
   capital I is as wide as the cap height or nearly. Serif against sans is
   not claimed: measured on live sites the two overlap (0.34 to 0.44), and a
   label the numbers cannot support would be a false instrument. */
function postureOf(iRatio) {
  if (typeof iRatio !== "number") return null;
  return iRatio >= 0.8 ? "mono" : "proportional";
}

function rank(target, measured, posture) {
  return measured
    .filter((r) => !r.error && typeof r.x_ratio === "number" && typeof r.advance === "number")
    .filter((r) => !posture || postureOf(r.i_ratio) === posture)
    .map((r) => {
      let delta = Math.abs(r.x_ratio - target.x_ratio) / target.x_ratio
        + Math.abs(r.advance - target.advance) / target.advance;
      if (typeof target.i_ratio === "number" && typeof r.i_ratio === "number" && target.i_ratio > 0) {
        delta += I_WEIGHT * Math.abs(r.i_ratio - target.i_ratio) / target.i_ratio;
      }
      return {
        family: r.family, weight: String(r.weight),
        x_ratio: r.x_ratio, advance: r.advance, i_ratio: r.i_ratio ?? null,
        posture: postureOf(r.i_ratio),
        delta: +delta.toFixed(4),
      };
    })
    .sort((a, b) => a.delta - b.delta);
}

const args = parseArgs(process.argv.slice(2));

let targets = [];
for (const file of args.observations) targets.push(...targetsFrom(file, args.family));
if (!targets.length) fail("no-targets", "No measured faces found in the observation(s)" + (args.family ? ` for family ${args.family}` : "") + ".");

let specs = [...args.candidates];
if (args.candidatesFile) {
  try {
    const extra = JSON.parse(fs.readFileSync(args.candidatesFile, "utf8"));
    if (!Array.isArray(extra)) throw new Error("not an array");
    specs.push(...extra.map(String));
  } catch (e) {
    fail("candidates-unreadable", `Could not read ${args.candidatesFile}: ${e.message}`);
  }
}
if (!specs.length) specs = [...DEFAULT_CANDIDATES];

let measured;
let measuredSource;
if (args.measured) {
  try {
    measured = JSON.parse(fs.readFileSync(args.measured, "utf8"));
    if (!Array.isArray(measured)) throw new Error("not an array");
  } catch (e) {
    fail("measured-unreadable", `Could not read ${args.measured}: ${e.message}`);
  }
  measuredSource = { file: path.relative(process.cwd(), args.measured).split(path.sep).join("/"), sha256: sha256(args.measured) };
} else {
  measured = await measureCandidates(specs, args.browser);
  measuredSource = { file: null, css: FONTS_CSS, candidates: specs.length };
}

const results = targets.map((target) => {
  const ranked = rank(target, measured, args.posture);
  return {
    target: { ...target, posture: postureOf(target.i_ratio) || args.posture || null },
    axes: typeof target.i_ratio === "number" ? ["x_ratio", "advance", "i_ratio"] : ["x_ratio", "advance"],
    posture_filter: args.posture,
    ranked: ranked.slice(0, 12),
    chosen: ranked.length ? ranked[0] : null,
  };
});

const record = {
  tool: TOOL_NAME,
  schema_version: SCHEMA_VERSION,
  matched_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
  measurement: "100px canvas; x_ratio = ascent(x)/ascent(H); advance = width(\"Handgloves 0123\")/100; i_ratio = width(I)/ascent(H); identical to structure_probe.mjs",
  distance: "|dx|/x + |dadv|/adv + " + I_WEIGHT + " * |dI|/I",
  candidates: measuredSource,
  candidates_measured: measured,
  results,
  note: "The substitute for each target is `chosen`, rank one by numbers. check_style_provenance.mjs refuses any --substitute this record did not rank first. The producer does not choose faces.",
};

fs.mkdirSync(path.dirname(args.out), { recursive: true });
fs.writeFileSync(args.out, JSON.stringify(record, null, 2) + "\n", "utf8");

process.stdout.write(JSON.stringify({
  ok: true,
  record: args.out,
  results: results.map((r) => ({
    target: `${r.target.family} (${r.target.role}, x ${r.target.x_ratio}, adv ${r.target.advance})`,
    axes: r.axes.join("+") + (r.posture_filter ? ` within ${r.posture_filter}` : ""),
    chosen: r.chosen ? `${r.chosen.family}:${r.chosen.weight} (${r.chosen.posture}, x ${r.chosen.x_ratio}, adv ${r.chosen.advance}, I ${r.chosen.i_ratio}, delta ${r.chosen.delta})` : null,
  })),
  not_measured: measured.filter((m) => m.error).map((m) => `${m.family}:${m.weight} (${m.error})`),
}, null, 2) + "\n");
