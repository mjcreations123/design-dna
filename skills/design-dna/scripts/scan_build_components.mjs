#!/usr/bin/env node
/**
 * scan_build_components.mjs
 *
 * Enumerates the components a finished build ACTUALLY renders, so that the
 * dossier's Component sources table can be checked against the build instead
 * of against the producer's memory of it.
 *
 * The failure this exists for: a producer researched six sites, copied the
 * home page faithfully, and then invented two entire inner pages, a form and
 * a footer. Every one of those parts was in the shipped build. Not one of
 * them appeared in the sources table, because the table's required rows were
 * a fixed list and nothing compared that list to the build. The producer also
 * wrote a source line for a footer it had never looked at, because a source
 * line is prose and prose is free.
 *
 * This reads the rendered DOM of every route and reports the class stem of
 * every painted element under <body>. A stem with no row in the table is a
 * part of the design that came from nowhere.
 *
 * Usage:
 *   node scan_build_components.mjs \
 *     --url http://127.0.0.1:4960/ \
 *     --url http://127.0.0.1:4960/owners.html \
 *     --out .design-dna/evidence/component-census.json
 */

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const TOOL_NAME = "scan_build_components.mjs";
const SCHEMA_VERSION = 1;

/* A stem is the first class on the element, with any BEM element or modifier
   suffix removed: folio__stage and folio__item are both the folio component,
   pill and pill--ghost are both the pill. */
export function stemOf(className) {
  const first = String(className || "").trim().split(/\s+/)[0] || "";
  return first.split("--")[0].split("__")[0];
}

const CENSUS_SCRIPT = `(() => {
  const stem = (c) => {
    const first = String(c || '').trim().split(/\\s+/)[0] || '';
    return first.split('--')[0].split('__')[0];
  };
  const seen = new Map();
  const note = (name, el, box) => {
    const row = seen.get(name) || { name, count: 0, area: 0, tags: [], sample: '' };
    row.count += 1;
    row.area = Math.max(row.area, (box.width * box.height) / (innerWidth * innerHeight));
    const tag = el.tagName.toLowerCase();
    if (row.tags.indexOf(tag) < 0 && row.tags.length < 4) row.tags.push(tag);
    if (!row.sample) row.sample = (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 48);
    seen.set(name, row);
  };
  document.querySelectorAll('body *').forEach((el) => {
    const cls = el.getAttribute('class');
    if (!cls) return;
    const s = getComputedStyle(el);
    if (s.display === 'none') return;
    const box = el.getBoundingClientRect();
    // A one-pixel clipped box is a screen-reader affordance, not a design
    // decision, and demanding a source line for it would teach the producer
    // to write source lines it does not mean.
    if (box.width <= 1 || box.height <= 1) return;
    const name = stem(cls);
    if (!name) return;
    note(name, el, box);
  });
  /* Unclassed structure still ships. A <form>, a <footer>, a <nav> or a
     control with no class of its own is a component all the same, and the
     build that invented a form invented it without a class. */
  const semantic = { form: 'form', footer: 'footer', nav: 'nav', input: 'input',
    textarea: 'textarea', select: 'select', button: 'button', table: 'table' };
  Object.keys(semantic).forEach((tag) => {
    document.querySelectorAll(tag).forEach((el) => {
      const s = getComputedStyle(el);
      if (s.display === 'none') return;
      const box = el.getBoundingClientRect();
      if (box.width <= 1 || box.height <= 1) return;
      note(semantic[tag], el, box);
    });
  });
  return [...seen.values()]
    .map((r) => ({ ...r, area: +r.area.toFixed(4) }))
    .sort((a, b) => b.area - a.area);
})()`;

function parseArgs(argv) {
  const out = { urls: [], out: null, width: 1440, height: 900, chrome: process.env.CHROME || undefined };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--url") out.urls.push(argv[++i]);
    else if (a === "--out") out.out = argv[++i];
    else if (a === "--width") out.width = Number(argv[++i]);
    else if (a === "--height") out.height = Number(argv[++i]);
    else if (a === "--chrome") out.chrome = argv[++i];
  }
  return out;
}

function loadPlaywright() {
  const dir = process.env.DESIGN_DNA_PLAYWRIGHT_MODULE_DIR;
  const require_ = createRequire(dir ? path.join(dir, "noop.js") : import.meta.url);
  try {
    return require_("playwright-core");
  } catch {
    return require_("playwright");
  }
}

export async function scanBuild({ urls, width = 1440, height = 900, chrome }) {
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({ executablePath: chrome });
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
  const routes = [];
  try {
    for (const url of urls) {
      const page = await context.newPage();
      await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
      await page.waitForTimeout(600);
      const components = await page.evaluate(CENSUS_SCRIPT);
      routes.push({ url, components });
      await page.close();
    }
  } finally {
    await browser.close();
  }

  const census = new Map();
  for (const route of routes) {
    for (const c of route.components) {
      const row = census.get(c.name) || { name: c.name, routes: [], count: 0, area: 0 };
      row.routes.push(route.url);
      row.count += c.count;
      row.area = Math.max(row.area, c.area);
      census.set(c.name, row);
    }
  }

  return {
    tool: TOOL_NAME,
    schema_version: SCHEMA_VERSION,
    scanned_at: new Date().toISOString(),
    viewport: { w: width, h: height },
    routes: routes.map((r) => ({ url: r.url, components: r.components })),
    census: [...census.values()].sort((a, b) => b.area - a.area),
    names: [...census.keys()].sort(),
  };
}

const invokedDirectly =
  process.argv[1] && import.meta.url === new URL(`file://${process.argv[1].split(path.sep).join("/")}`).href;

if (invokedDirectly || process.argv.includes("--url")) {
  const opts = parseArgs(process.argv.slice(2));
  if (!opts.urls.length) {
    console.error("scan_build_components.mjs: at least one --url is required.");
    process.exit(2);
  }
  const record = await scanBuild(opts);
  const text = JSON.stringify(record, null, 1);
  if (opts.out) {
    await mkdir(path.dirname(opts.out), { recursive: true });
    await writeFile(opts.out, text, "utf8");
    console.error(
      `scan_build_components.mjs: ${record.names.length} components across ` +
        `${record.routes.length} route(s) -> ${opts.out}`
    );
    console.error(record.names.join(", "));
  } else {
    console.log(text);
  }
}
