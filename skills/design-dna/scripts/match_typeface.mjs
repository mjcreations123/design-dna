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
 * body faces with proportions a face cannot fake (seven geometry axes and a
 * rendered-glyph fingerprint). This script measures candidate open-licence faces the SAME way,
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
 * Measurement (identical to structure_probe.mjs): at 100px it records x-height,
 * mixed-case, lowercase, uppercase, digit and punctuation advance, capital-I
 * ratio, plus a 96px raster fingerprint. The distance is a weighted mean of
 * relative differences on every axis the target carries. Measured on live sites the
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
import { browserExecutableIdentity, discoverBrowserExecutable, resolvePlaywright } from "./playwright_resolver.mjs";

const TOOL_NAME = "match_typeface.mjs";
const SCHEMA_VERSION = 3;
const SCRIPT_PATH = path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const PRODUCER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(SCRIPT_PATH)).digest("hex");
const OBSERVER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "observe_reference.mjs"))).digest("hex");
const STRUCTURE_PROBE_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "structure_probe.mjs"))).digest("hex");
const PLAYWRIGHT_RESOLVER_SHA256 = createHash("sha256").update(fs.readFileSync(path.join(path.dirname(SCRIPT_PATH), "playwright_resolver.mjs"))).digest("hex");
/* The I-width axis is one glyph; x-height and advance are the texture of
   every line. Equal weights let the I override both (Louize Display, whose
   capitals carry tiny serifs, ranked a face with the wrong x-height and the
   wrong width first). At 0.4 the axis separates postures when the texture
   axes are close and cannot outrank them when they are not. */
const AXIS_WEIGHTS = {
  x_ratio: 1,
  advance: 1,
  i_ratio: 0.4,
  lower_advance: 0.8,
  upper_advance: 0.8,
  digit_advance: 0.6,
  punct_advance: 0.4,
};
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
    measured: null, out: null,
    browser: process.env.DESIGN_DNA_BROWSER_EXECUTABLE || process.env.CHROME || null,
    posture: null,
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
  try {
    return resolvePlaywright({ moduleUrl: import.meta.url });
  } catch (error) {
    fail(error?.code || "playwright-missing", String(error?.message || error));
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

/* The targets: every face the observation measured on the reference. */
function targetsFrom(observationPath, familyFilter) {
  let payload;
  try {
    payload = JSON.parse(fs.readFileSync(observationPath, "utf8"));
  } catch (e) {
    fail("observation-unreadable", `Could not read ${observationPath}: ${e.message}`);
  }
  const type = payload && payload.first_screen && payload.first_screen.type;
  if (payload?.tool !== "observe_reference.mjs" || !Number.isInteger(payload.schema_version) || payload.schema_version < 5 ||
      payload.producer_script_sha256 !== OBSERVER_SCRIPT_SHA256 ||
      payload.runtime_identity?.["structure_probe.mjs"] !== STRUCTURE_PROBE_SHA256 ||
      payload.runtime_identity?.["playwright_resolver.mjs"] !== PLAYWRIGHT_RESOLVER_SHA256) {
    fail("observation-identity", `${observationPath} was not emitted by the current observe_reference.mjs runtime.`);
  }
  if (!type || typeof type !== "object") {
    fail("no-type-measurements", `${observationPath} carries no first_screen.type; re-run the current observe_reference.mjs (schema 5).`);
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
      lower_advance: typeof t.lower_advance === "number" ? t.lower_advance : null,
      upper_advance: typeof t.upper_advance === "number" ? t.upper_advance : null,
      digit_advance: typeof t.digit_advance === "number" ? t.digit_advance : null,
      punct_advance: typeof t.punct_advance === "number" ? t.punct_advance : null,
      font_fingerprint: t.font_fingerprint || null,
      observation: path.relative(process.cwd(), observationPath).split(path.sep).join("/"),
      observation_sha256: sha256(observationPath),
    });
  }
  return targets;
}

async function measureCandidates(specs, loaded, browserDependency) {
  const browser = await loaded.playwright.chromium.launch({ executablePath: browserDependency.file });
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
        const fontBytes = await (await fetch(src)).arrayBuffer();
        const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', fontBytes))]
          .map((byte) => byte.toString(16).padStart(2, '0')).join('');
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
        const raster = document.createElement('canvas'); raster.width = 720; raster.height = 150;
        const rc = raster.getContext('2d', { willReadFrequently: true });
        rc.fillStyle = '#000'; rc.font = `${weight} 96px "${name}"`; rc.textBaseline = 'alphabetic';
        const probe = 'Hamburgefontsiv 0123 Il1 @&?'; rc.fillText(probe, 4, 108);
        const data = rc.getImageData(0, 0, raster.width, raster.height).data;
        let hash = 2166136261, hash2 = 2654435769, ink = 0;
        for (let i = 3; i < data.length; i += 4) {
          if (!data[i]) continue;
          const signal = ((i / 4) & 0xffff) ^ data[i];
          ink += 1; hash ^= signal; hash = Math.imul(hash, 16777619);
          hash2 ^= signal + ink; hash2 = Math.imul(hash2, 2246822519);
        }
        out.push({
          family, weight, subset, source_url: src, source_sha256: digest,
          x_ratio: cap ? +(xh / cap).toFixed(3) : null, advance: +(adv / 100).toFixed(3),
          i_ratio: cap ? +(iw / cap).toFixed(3) : null,
          lower_advance: +(c.measureText('abcdefghijklmnopqrstuvwxyz').width / 100).toFixed(3),
          upper_advance: +(c.measureText('ABCDEFGHIJKLMNOPQRSTUVWXYZ').width / 100).toFixed(3),
          digit_advance: +(c.measureText('0123456789').width / 100).toFixed(3),
          punct_advance: +(c.measureText('.,:;!?@&()[]').width / 100).toFixed(3),
          font_fingerprint: { raster: (hash >>> 0).toString(16).padStart(8, '0') + (hash2 >>> 0).toString(16).padStart(8, '0'), ink,
            probe_width: +rc.measureText(probe).width.toFixed(3) },
        });
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
      let delta = 0, weight = 0;
      const axes = [];
      for (const [axis, axisWeight] of Object.entries(AXIS_WEIGHTS)) {
        if (typeof target[axis] !== "number" || typeof r[axis] !== "number" || target[axis] === 0) continue;
        delta += axisWeight * Math.abs(r[axis] - target[axis]) / Math.abs(target[axis]);
        weight += axisWeight; axes.push(axis);
      }
      return {
        family: r.family, weight: String(r.weight),
        x_ratio: r.x_ratio, advance: r.advance, i_ratio: r.i_ratio ?? null,
        lower_advance: r.lower_advance ?? null, upper_advance: r.upper_advance ?? null,
        digit_advance: r.digit_advance ?? null, punct_advance: r.punct_advance ?? null,
        font_fingerprint: r.font_fingerprint || null,
        source_url: r.source_url || null, source_sha256: r.source_sha256 || null,
        posture: postureOf(r.i_ratio),
        axes, delta: +(weight ? delta / weight : Infinity).toFixed(4),
      };
    })
    .sort((a, b) => a.delta - b.delta);
}

const args = parseArgs(process.argv.slice(2));

let targets = [];
for (const file of args.observations) targets.push(...targetsFrom(file, args.family));
if (!targets.length) fail("no-targets", "No measured faces found in the observation(s)" + (args.family ? ` for family ${args.family}` : "") + ".");
const inputObservations = args.observations.map((file) => {
  let payload;
  try { payload = JSON.parse(fs.readFileSync(file, "utf8")); }
  catch (error) { fail("observation-unreadable", `Could not re-read ${file}: ${error.message}`); }
  return {
    file: path.relative(process.cwd(), file).split(path.sep).join("/"),
    id: payload.id,
    url: payload.url,
    sha256: sha256(file),
  };
}).sort((a, b) => a.sha256.localeCompare(b.sha256));
const observationSetSha256 = createHash("sha256")
  .update(JSON.stringify(inputObservations.map((item) => ({ id: item.id, url: item.url, sha256: item.sha256 }))))
  .digest("hex");

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
// User-supplied candidates extend the maintained search space; they cannot
// shrink it until a preferred answer becomes rank one.
specs = [...new Set([...DEFAULT_CANDIDATES, ...specs])];

let measured;
let measuredSource;
if (args.measured) {
  try {
    const payload = JSON.parse(fs.readFileSync(args.measured, "utf8"));
    measured = Array.isArray(payload) ? payload : payload?.candidates;
    if (!Array.isArray(measured)) throw new Error("not an array or measurement record");
  } catch (e) {
    fail("measured-unreadable", `Could not read ${args.measured}: ${e.message}`);
  }
  measuredSource = { mode: "offline-diagnostic", verified: false, file: path.relative(process.cwd(), args.measured).split(path.sep).join("/"), sha256: sha256(args.measured) };
} else {
  const loaded = loadPlaywright();
  const browserDependency = loadBrowserDependency(loaded, args.browser);
  measured = await measureCandidates(specs, loaded, browserDependency);
  measuredSource = {
    mode: "browser", verified: measured.some((row) => !row.error) && measured.filter((row) => !row.error).every((row) => row.source_sha256 && row.font_fingerprint),
    file: null, css: FONTS_CSS, candidates: specs.length,
    playwright: loaded.dependency, browser_executable: browserDependency,
  };
}

const results = targets.map((target) => {
  const ranked = rank(target, measured, args.posture);
  return {
    target: { ...target, posture: postureOf(target.i_ratio) || args.posture || null },
    axes: Object.keys(AXIS_WEIGHTS).filter((axis) => typeof target[axis] === "number" && ranked.some((row) => typeof row[axis] === "number")),
    posture_filter: args.posture,
    ranked: ranked.slice(0, 12),
    chosen: ranked.length ? ranked[0] : null,
  };
});

const record = {
  tool: TOOL_NAME,
  schema_version: SCHEMA_VERSION,
  producer_script_sha256: PRODUCER_SCRIPT_SHA256,
  runtime_identity: {
    "match_typeface.mjs": PRODUCER_SCRIPT_SHA256,
    "observe_reference.mjs": OBSERVER_SCRIPT_SHA256,
    "structure_probe.mjs": STRUCTURE_PROBE_SHA256,
    "playwright_resolver.mjs": PLAYWRIGHT_RESOLVER_SHA256,
    ...(measuredSource.mode === "browser" ? {
      "playwright-entry": measuredSource.playwright.resolved_file_sha256,
      "browser-executable": measuredSource.browser_executable.sha256,
    } : {}),
  },
  dependencies: measuredSource.mode === "browser"
    ? { playwright: measuredSource.playwright, browser_executable: measuredSource.browser_executable }
    : {},
  matched_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
  input_observations: inputObservations,
  observation_set_sha256: observationSetSha256,
  measurement: "100px canvas geometry on seven axes plus a 96px rendered-glyph raster fingerprint; browser candidates bind the fetched font bytes by SHA-256",
  distance: "weighted mean relative error over every shared axis",
  axis_weights: AXIS_WEIGHTS,
  verified_browser_measurement: measuredSource.verified,
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
