#!/usr/bin/env node
/**
 * candidates_sheet.mjs
 *
 * One image to choose from. Tiles every study in a folder (quick looks and
 * full studies alike) as a row: desktop first screen, phone first screen, the
 * scroll storyboard, and a caption with what the tool measured (fonts, sampled
 * ground, mechanisms, gaps, time). Look at it once and pick the references.
 *
 *   node candidates_sheet.mjs --studies .design-dna/references --out .design-dna/candidates.png [--ids a,b,c]
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { resolvePlaywright, discoverBrowserExecutable } from "./playwright_resolver.mjs";

function parseArgs(argv) {
  const out = { studies: null, out: null, ids: null, browserExecutable: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--studies") out.studies = argv[++i];
    else if (a === "--out") out.out = argv[++i];
    else if (a === "--ids") out.ids = String(argv[++i]).split(",").map((x) => x.trim()).filter(Boolean);
    else if (a === "--browser-executable") out.browserExecutable = argv[++i];
    else if (a === "--help" || a === "-h") { process.stdout.write("candidates_sheet.mjs --studies DIR --out FILE [--ids a,b,c]\n"); process.exit(0); }
    else { process.stdout.write(JSON.stringify({ ok: false, error: `unknown argument ${a}` }) + "\n"); process.exit(2); }
  }
  if (!out.studies || !fs.existsSync(out.studies) || !out.out) { process.stdout.write(JSON.stringify({ ok: false, error: "--studies DIR and --out FILE are required" }) + "\n"); process.exit(2); }
  return out;
}
const dataUri = (file) => (file && fs.existsSync(file) ? `data:image/png;base64,${fs.readFileSync(file).toString("base64")}` : null);
const esc = (t) => String(t ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;");

const args = parseArgs(process.argv.slice(2));
const rows = [];
for (const entry of fs.readdirSync(args.studies, { withFileTypes: true })) {
  if (!entry.isDirectory()) continue;
  if (args.ids && !args.ids.includes(entry.name)) continue;
  const dir = path.join(args.studies, entry.name);
  const file = path.join(dir, "study.json");
  if (!fs.existsSync(file)) continue;
  const st = JSON.parse(fs.readFileSync(file, "utf8"));
  const wide = (st.pages || []).find((p) => p.role === "primary" && p.viewport === "wide");
  const narrow = (st.pages || []).find((p) => p.role === "primary" && p.viewport === "narrow");
  const fonts = (wide?.design?.fonts || []).slice(0, 3).map((f) => f.family).join(", ") || "?";
  const grounds = (wide?.ground_sampled?.grounds || []).slice(0, 2).map((g) => `${g.color} ${Math.round(g.share * 100)}%`).join("; ") || (wide?.design?.grounds?.[0] ? `${wide.design.grounds[0].color} (estimate)` : "?");
  const mechs = [...new Set((wide?.motion?.mechanisms || []).map((m) => `${m.type}${m.driver ? ":" + m.driver : ""}`))].join(", ") || "none detected";
  const gaps = [...new Set((st.observation_gaps || []).map((g) => g.code))].join(", ") || "none";
  rows.push({
    id: entry.name, url: st.url, mode: st.mode || "full", ok: st.complete, elapsed: st.elapsed_s,
    wideShot: dataUri(path.join(dir, "frames", (wide?.first_screen_clear || wide?.first_screen)?.file || "")),
    narrowShot: dataUri(path.join(dir, "frames", (narrow?.first_screen_clear || narrow?.first_screen)?.file || "")),
    sheet: dataUri(path.join(dir, wide?.contact_sheet?.file || "")),
    caption: `${fonts} · ground ${grounds} · ${mechs} · gaps: ${gaps} · hover ${wide?.hover ? `${wide.hover.responded}/${wide.hover.probed}` : "not probed"} · ${st.elapsed_s ?? "?"}s ${st.mode === "quick" ? "quick look" : "full study"}${st.complete ? "" : " · NOT OK"}`,
  });
}
if (!rows.length) { process.stdout.write(JSON.stringify({ ok: false, error: "no studies found" }) + "\n"); process.exit(1); }

const html = `<!doctype html><meta charset="utf-8"><style>
  body{margin:0;background:#151515;color:#eee;font:13px/1.4 system-ui,sans-serif;padding:14px;width:1892px}
  h1{font-size:16px;margin:0 0 10px} .row{display:grid;grid-template-columns:560px 152px 1fr;gap:12px;align-items:start;margin:0 0 18px;padding-bottom:14px;border-bottom:1px solid #333}
  img{display:block;width:100%;border:1px solid #333} .cap{grid-column:1/-1;color:#ccc} .id{font-weight:600;color:#fff;font-size:14px} .missing{border:1px dashed #555;color:#888;padding:20px;text-align:center}
</style><h1>Candidates: choose four that work together. Judge desktop, phone, readability, navigation, reliability, suitability. A listing is discovery, not quality.</h1>
${rows.map((r) => `<div class="row">
  ${r.wideShot ? `<img src="${r.wideShot}">` : `<div class="missing">no desktop first screen</div>`}
  ${r.narrowShot ? `<img src="${r.narrowShot}">` : `<div class="missing">no phone first screen</div>`}
  ${r.sheet ? `<img src="${r.sheet}">` : `<div class="missing">no storyboard</div>`}
  <div class="cap"><span class="id">${esc(r.id)}</span> · ${esc(r.url)} · ${esc(r.caption)}</div>
</div>`).join("\n")}`;

const loaded = resolvePlaywright({ moduleUrl: import.meta.url });
const exe = discoverBrowserExecutable(loaded.playwright, args.browserExecutable);
const browser = await loaded.playwright.chromium.launch({ executablePath: exe.path });
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1200 } });
  await page.setContent(html, { waitUntil: "load" });
  fs.mkdirSync(path.dirname(path.resolve(args.out)), { recursive: true });
  await page.screenshot({ path: args.out, fullPage: true });
} finally { await browser.close().catch(() => {}); }
process.stdout.write(JSON.stringify({ ok: true, out: args.out, candidates: rows.map((r) => ({ id: r.id, mode: r.mode, ok: r.ok, elapsed_s: r.elapsed })) }, null, 2) + "\n");
