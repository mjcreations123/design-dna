#!/usr/bin/env node
/**
 * measure_faces.mjs
 *
 * Measures the glyph geometry of typefaces AS A LIVE REFERENCE RENDERS THEM,
 * so match_typeface.mjs can rank an open-licence substitute for a face the
 * build cannot self-host. It is the 13.x replacement for the type block the
 * legacy observer used to write: study_reference.mjs names the families a
 * site computes; this script measures the ones the plan needs matched.
 *
 * The probe is byte-for-byte the one match_typeface.mjs applies to every
 * candidate (100px canvas: x-height over cap height, the advance of
 * "Handgloves 0123", the capital-I width, lowercase, uppercase, digit and
 * punctuation advances, and a 96px rendered-glyph raster fingerprint), so the
 * target and the candidates are measured the same way in the same engine.
 *
 * Usage:
 *   node measure_faces.mjs --url https://example.test/ \
 *        --family "Cardinal Fruit" [--family "Sweet Sans Pro:700"] \
 *        --out .design-dna/references/<id>/faces.json [--browser-executable FILE]
 *
 * Then:
 *   node match_typeface.mjs --target .design-dna/references/<id>/faces.json \
 *        --family "Cardinal Fruit" --out .design-dna/typeface-match.json
 *
 * A family the page never actually renders (the browser fell back to a system
 * face) is reported with `fallback_suspected: true` and is not a usable target;
 * the record says so instead of measuring the fallback and calling it the face.
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { browserExecutableIdentity, discoverBrowserExecutable, resolvePlaywright } from "./playwright_resolver.mjs";

const TOOL_NAME = "measure_faces.mjs";
const SCHEMA_VERSION = 1;
const SCRIPT_PATH = path.resolve(fileURLToPath(import.meta.url));
const PRODUCER_SCRIPT_SHA256 = createHash("sha256").update(fs.readFileSync(SCRIPT_PATH)).digest("hex");

function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }, null, 2) + "\n");
  process.exit(2);
}

function parseArgs(argv) {
  const out = { url: null, families: [], out: null, browser: process.env.DESIGN_DNA_BROWSER_EXECUTABLE || process.env.CHROME || null, settleMs: 2500 };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--url") out.url = argv[++i];
    else if (a === "--family") out.families.push(String(argv[++i]));
    else if (a === "--out") out.out = argv[++i];
    else if (a === "--browser-executable") out.browser = argv[++i];
    else if (a === "--settle-ms") out.settleMs = Number(argv[++i]);
    else if (a === "--help" || a === "-h") {
      process.stdout.write("measure_faces.mjs --url URL --family \"Family[:weight]\"... --out FILE [--browser-executable FILE]\n");
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${a}`);
  }
  if (!out.url || !/^https?:\/\//i.test(out.url)) fail("invalid-url", "--url must be an http(s) URL.");
  if (!out.families.length) fail("no-families", "--family must name at least one family the reference computes.");
  if (!out.out) fail("invalid-out", "--out must name the record to write.");
  return out;
}

/* Runs in the page. Identical probe to match_typeface.mjs measureCandidates,
   applied to a family the page itself has loaded. */
const MEASURE_IN_PAGE = `(async (specs) => {
  const out = [];
  const probeOf = (fontSpec) => {
    const c = document.createElement("canvas").getContext("2d");
    c.font = fontSpec;
    const H = c.measureText("H"), x = c.measureText("x");
    const cap = H.actualBoundingBoxAscent || 0;
    const xh = x.actualBoundingBoxAscent || 0;
    const adv = c.measureText("Handgloves 0123").width;
    const iw = c.measureText("I").width;
    return { c, cap, xh, adv, iw };
  };
  for (const spec of specs) {
    const idx = spec.lastIndexOf(":");
    const family = idx > 0 && /^\\d{3}$/.test(spec.slice(idx + 1)) ? spec.slice(0, idx) : spec;
    const weight = idx > 0 && /^\\d{3}$/.test(spec.slice(idx + 1)) ? spec.slice(idx + 1) : "400";
    try {
      const fontSpec = weight + ' 100px "' + family + '"';
      let loaded = [];
      try { loaded = await document.fonts.load(fontSpec, "Handgloves 0123 Il1 @&?"); } catch (e) { loaded = []; }
      const available = document.fonts.check(fontSpec);
      const p = probeOf(fontSpec);
      // Fallback detection: the same string in the generic families. If the
      // named face is not really there, the browser draws one of these and the
      // widths coincide exactly.
      const fallbacks = ["serif", "sans-serif", "monospace"].map((g) => probeOf(weight + " 100px " + g));
      const fallbackSuspected = !available || loaded.length === 0 || fallbacks.some((f) => Math.abs(f.adv - p.adv) < 0.01 && Math.abs(f.iw - p.iw) < 0.01 && Math.abs(f.xh - p.xh) < 0.01);
      const raster = document.createElement("canvas"); raster.width = 720; raster.height = 150;
      const rc = raster.getContext("2d", { willReadFrequently: true });
      rc.fillStyle = "#000"; rc.font = weight + ' 96px "' + family + '"'; rc.textBaseline = "alphabetic";
      const probe = "Hamburgefontsiv 0123 Il1 @&?"; rc.fillText(probe, 4, 108);
      const data = rc.getImageData(0, 0, raster.width, raster.height).data;
      let hash = 2166136261, hash2 = 2654435769, ink = 0;
      for (let i = 3; i < data.length; i += 4) {
        if (!data[i]) continue;
        const signal = ((i / 4) & 0xffff) ^ data[i];
        ink += 1; hash ^= signal; hash = Math.imul(hash, 16777619);
        hash2 ^= signal + ink; hash2 = Math.imul(hash2, 2246822519);
      }
      const faces = [...document.fonts].filter((f) => f.family.replace(/["']/g, "").toLowerCase() === family.toLowerCase()).map((f) => ({ weight: f.weight, style: f.style, status: f.status }));
      out.push({
        family, weight, available, loaded_faces: loaded.length, declared_faces: faces, fallback_suspected: fallbackSuspected,
        x_ratio: p.cap ? +(p.xh / p.cap).toFixed(3) : null, advance: +(p.adv / 100).toFixed(3),
        i_ratio: p.cap ? +(p.iw / p.cap).toFixed(3) : null,
        lower_advance: +(p.c.measureText("abcdefghijklmnopqrstuvwxyz").width / 100).toFixed(3),
        upper_advance: +(p.c.measureText("ABCDEFGHIJKLMNOPQRSTUVWXYZ").width / 100).toFixed(3),
        digit_advance: +(p.c.measureText("0123456789").width / 100).toFixed(3),
        punct_advance: +(p.c.measureText(".,:;!?@&()[]").width / 100).toFixed(3),
        font_fingerprint: { raster: (hash >>> 0).toString(16).padStart(8, "0") + (hash2 >>> 0).toString(16).padStart(8, "0"), ink, probe_width: +rc.measureText(probe).width.toFixed(3) },
      });
    } catch (e) {
      out.push({ family, weight, error: String(e).slice(0, 120) });
    }
  }
  return out;
})`;

const args = parseArgs(process.argv.slice(2));
let loaded;
try { loaded = resolvePlaywright({ moduleUrl: import.meta.url }); }
catch (error) { fail(error?.code || "playwright-missing", String(error?.message || error)); }
let browserDependency;
try { browserDependency = browserExecutableIdentity(discoverBrowserExecutable(loaded.playwright, args.browser)); }
catch (error) { fail(error?.code || "browser-executable-unavailable", String(error?.message || error)); }

const problems = [];
const browser = await loaded.playwright.chromium.launch({ executablePath: browserDependency.file });
let faces = [];
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(args.url, { waitUntil: "load", timeout: 60_000 });
  await page.evaluate(() => document.fonts.ready.then(() => true)).catch(() => problems.push("document.fonts.ready did not settle"));
  await new Promise((r) => setTimeout(r, args.settleMs));
  faces = await page.evaluate(`${MEASURE_IN_PAGE}(${JSON.stringify(args.families)})`);
} catch (error) {
  problems.push(`measurement failed: ${String(error?.message || error).slice(0, 200)}`);
} finally {
  await browser.close().catch(() => {});
}
for (const f of faces) {
  if (f.error) problems.push(`${f.family}: ${f.error}`);
  else if (f.fallback_suspected) problems.push(`${f.family} ${f.weight}: the page did not render this family here (fallback suspected); not a usable target`);
}

const record = {
  tool: TOOL_NAME,
  schema_version: SCHEMA_VERSION,
  producer_script_sha256: PRODUCER_SCRIPT_SHA256,
  runtime_identity: {
    "measure_faces.mjs": PRODUCER_SCRIPT_SHA256,
    "playwright-entry": loaded.dependency?.resolved_file_sha256 || null,
    "browser-executable": browserDependency.sha256 || null,
  },
  dependencies: { playwright: loaded.dependency, browser_executable: browserDependency },
  url: args.url,
  id: args.url,
  measured_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
  measurement: "100px canvas geometry on seven axes plus a 96px rendered-glyph raster fingerprint, applied to the family as the live page loaded it",
  faces,
  problems,
  ok: faces.some((f) => !f.error && !f.fallback_suspected),
};
fs.mkdirSync(path.dirname(args.out), { recursive: true });
fs.writeFileSync(args.out, JSON.stringify(record, null, 2) + "\n", "utf8");
process.stdout.write(JSON.stringify({ ok: record.ok, out: args.out, faces: faces.map((f) => ({ family: f.family, weight: f.weight, x_ratio: f.x_ratio ?? null, advance: f.advance ?? null, i_ratio: f.i_ratio ?? null, fallback_suspected: f.fallback_suspected ?? null, error: f.error || null })), problems }, null, 2) + "\n");
process.exit(record.ok ? 0 : 1);
