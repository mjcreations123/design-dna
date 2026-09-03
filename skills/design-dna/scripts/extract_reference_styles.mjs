#!/usr/bin/env node
/**
 * extract_reference_styles.mjs
 *
 * Reads a reference's DESIGN SYSTEM out of the live page: every distinct type
 * setting, color, control geometry, transition, radius, border, section
 * background and spacing value that the site actually computes.
 *
 * This exists because a producer cannot build from a picture. Given a
 * screenshot it will report what a screenshot can carry, which is caption
 * alignment, a pill radius and a hover duration it guessed, and it will fill
 * everything else in from memory while believing it is copying. The values a
 * build claims to reproduce have to come from a tool that read the live CSS,
 * so that a number nobody measured cannot be written down.
 *
 * The `numbers` array is the point: the dossier's "Recorded values reproduced"
 * column is checked against it. A value the reference does not compute cannot
 * be claimed.
 *
 * Usage:
 *   node extract_reference_styles.mjs --url https://example.test/ --id strong-1 \
 *     --out .design-dna/references [--browser-executable FILE]
 */

import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const TOOL_NAME = "extract_reference_styles.mjs";
const SCHEMA_VERSION = 1;

const EXTRACT = `(() => {
  const px = (v) => { const n = parseFloat(v); return Number.isFinite(n) ? n : null; };
  const round = (n) => (n === null ? null : Math.round(n * 1000) / 1000);
  const numbers = new Set();
  const noteNums = (str) => {
    String(str || '').replace(/-?\\d*\\.?\\d+/g, (m) => {
      const n = parseFloat(m);
      if (Number.isFinite(n)) numbers.add(Math.round(n * 1000) / 1000);
      return m;
    });
  };

  const vis = (el) => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0) return null;
    const b = el.getBoundingClientRect();
    if (b.width < 2 || b.height < 2) return null;
    return { s, b };
  };
  const ownText = (el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.nodeValue.trim());

  /* ---- type: every distinct setting that actually carries words ---- */
  const typeMap = new Map();
  document.querySelectorAll('body *').forEach((el) => {
    if (!ownText(el)) return;
    const v = vis(el); if (!v) return;
    const s = v.s;
    const size = round(px(s.fontSize));
    const lead = px(s.lineHeight);
    const key = [s.fontFamily.split(',')[0].replace(/["']/g, ''), size, s.fontWeight,
      s.letterSpacing, s.textTransform, s.fontStyle].join('|');
    const row = typeMap.get(key) || {
      family: s.fontFamily.split(',')[0].replace(/["']/g, ''),
      size, weight: s.fontWeight,
      leading: lead && size ? round(lead / size) : null,
      tracking: s.letterSpacing === 'normal' ? 'normal' : round(px(s.letterSpacing)),
      transform: s.textTransform, style: s.fontStyle,
      color: s.color, count: 0, sample: '',
    };
    row.count += 1;
    if (!row.sample) row.sample = el.textContent.trim().replace(/\\s+/g, ' ').slice(0, 40);
    typeMap.set(key, row);
    noteNums(size); if (row.leading !== null) noteNums(row.leading);
    if (row.tracking !== 'normal') noteNums(row.tracking);
    noteNums(s.fontWeight);
  });

  /* ---- controls: what a link, a button and a field are actually shaped like ---- */
  const controls = [];
  document.querySelectorAll('a, button, input, textarea, select, [role="button"]').forEach((el) => {
    const v = vis(el); if (!v) return;
    const s = v.s;
    if (controls.length > 60) return;
    const row = {
      tag: el.tagName.toLowerCase(),
      cls: (typeof el.className === 'string' ? el.className : '').trim().slice(0, 40),
      w: Math.round(v.b.width), h: Math.round(v.b.height),
      padding: s.padding, radius: s.borderRadius,
      border: s.borderTopWidth + ' ' + s.borderTopStyle,
      background: s.backgroundColor, color: s.color,
      font: round(px(s.fontSize)) + ' ' + s.fontWeight + ' ' + s.textTransform,
      tracking: s.letterSpacing,
      transition: s.transitionProperty + ' ' + s.transitionDuration + ' ' + s.transitionTimingFunction,
      decoration: s.textDecorationLine,
    };
    controls.push(row);
    [s.padding, s.borderRadius, s.borderTopWidth, s.fontSize, s.letterSpacing,
      s.transitionDuration, s.transitionTimingFunction].forEach(noteNums);
    noteNums(v.b.width); noteNums(v.b.height);
  });

  /* ---- transitions actually declared anywhere ---- */
  const trans = new Map();
  document.querySelectorAll('body *').forEach((el) => {
    const s = getComputedStyle(el);
    if (!s.transitionDuration || s.transitionDuration === '0s') return;
    const key = s.transitionProperty + '|' + s.transitionDuration + '|' + s.transitionTimingFunction;
    trans.set(key, (trans.get(key) || 0) + 1);
    noteNums(s.transitionDuration); noteNums(s.transitionTimingFunction);
  });

  /* ---- sections: their grounds, their heights, how they divide ---- */
  const sections = [];
  document.querySelectorAll('body > *, main > *, body > * > *').forEach((el) => {
    const v = vis(el); if (!v) return;
    if (v.b.height < 80 || v.b.width < innerWidth * 0.5) return;
    if (sections.length > 40) return;
    const s = v.s;
    sections.push({
      tag: el.tagName.toLowerCase(),
      cls: (typeof el.className === 'string' ? el.className : '').trim().slice(0, 40),
      background: s.backgroundColor,
      padding: s.padding,
      display: s.display,
      columns: s.gridTemplateColumns === 'none' ? null : s.gridTemplateColumns,
      gap: s.gap === 'normal' ? null : s.gap,
      height_ratio: round(v.b.height / innerHeight),
      width_ratio: round(v.b.width / innerWidth),
    });
    [s.padding, s.gap].forEach(noteNums);
    noteNums(v.b.height); noteNums(v.b.width);
  });

  /* ---- color: every value the page actually paints, with how much it covers ---- */
  const colors = new Map();
  const bump = (value, role, area) => {
    if (!value || value === 'rgba(0, 0, 0, 0)') return;
    const k = value + '|' + role;
    const row = colors.get(k) || { value, role, count: 0, area: 0 };
    row.count += 1; row.area += area || 0;
    colors.set(k, row);
  };
  document.querySelectorAll('body *').forEach((el) => {
    const v = vis(el); if (!v) return;
    const a = (v.b.width * v.b.height) / (innerWidth * innerHeight);
    bump(v.s.backgroundColor, 'background', a);
    if (ownText(el)) bump(v.s.color, 'text', 0);
    if (parseFloat(v.s.borderTopWidth) > 0) bump(v.s.borderTopColor, 'border', 0);
  });

  /* ---- radii and border widths in use ---- */
  const radii = new Set(), borders = new Set();
  document.querySelectorAll('body *').forEach((el) => {
    const s = getComputedStyle(el);
    if (s.borderRadius && s.borderRadius !== '0px') { radii.add(s.borderRadius); noteNums(s.borderRadius); }
    const bw = parseFloat(s.borderTopWidth);
    if (bw > 0) { borders.add(s.borderTopWidth); noteNums(s.borderTopWidth); }
  });

  return {
    viewport: { w: innerWidth, h: innerHeight },
    type: [...typeMap.values()].sort((a, b) => b.count - a.count).slice(0, 30),
    controls: controls.slice(0, 40),
    transitions: [...trans.entries()].map(([k, n]) => {
      const [property, duration, easing] = k.split('|');
      return { property, duration, easing, count: n };
    }).sort((a, b) => b.count - a.count).slice(0, 20),
    sections: sections,
    colors: [...colors.values()].sort((a, b) => b.area - a.area).slice(0, 30)
      .map((c) => ({ ...c, area: Math.round(c.area * 1000) / 1000 })),
    radii: [...radii].slice(0, 20),
    borders: [...borders].slice(0, 12),
    numbers: [...numbers].sort((a, b) => a - b),
  };
})()`;

function parseArgs(argv) {
  const out = { url: null, id: null, out: null, browser: process.env.CHROME || undefined, holds: 6 };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--url") out.url = argv[++i];
    else if (a === "--id") out.id = argv[++i];
    else if (a === "--out") out.out = argv[++i];
    else if (a === "--browser-executable") out.browser = argv[++i];
    else if (a === "--holds") out.holds = Number(argv[++i]);
  }
  return out;
}

function loadPlaywright() {
  const dir = process.env.DESIGN_DNA_PLAYWRIGHT_MODULE_DIR;
  const require_ = createRequire(dir ? path.join(dir, "noop.js") : import.meta.url);
  try { return require_("playwright-core"); } catch { return require_("playwright"); }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.url || !args.id || !args.out) {
    console.error("extract_reference_styles.mjs --url URL --id strong-N --out DIR");
    process.exit(2);
  }
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({ executablePath: args.browser });
  const page = await (await browser.newContext({
    viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1,
  })).newPage();
  try {
    await page.goto(args.url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(3800);

    // The page is DRIVEN, not photographed. Styles are read at rest and again
    // deeper in, because a site's system is not all present on its first screen.
    const passes = [];
    passes.push(await page.evaluate(EXTRACT));
    for (let i = 0; i < args.holds; i += 1) {
      await page.mouse.wheel(0, 900);
      await page.waitForTimeout(650);
      passes.push(await page.evaluate(EXTRACT));
    }

    const merged = passes[0];
    const seenType = new Set(merged.type.map((t) => t.family + t.size + t.weight));
    const numbers = new Set(merged.numbers);
    for (const p of passes.slice(1)) {
      for (const t of p.type) {
        const k = t.family + t.size + t.weight;
        if (!seenType.has(k)) { seenType.add(k); merged.type.push(t); }
      }
      for (const c of p.controls) merged.controls.push(c);
      for (const s of p.sections) merged.sections.push(s);
      for (const t of p.transitions) {
        if (!merged.transitions.some((x) => x.property === t.property && x.duration === t.duration)) {
          merged.transitions.push(t);
        }
      }
      for (const c of p.colors) {
        if (!merged.colors.some((x) => x.value === c.value && x.role === c.role)) merged.colors.push(c);
      }
      p.radii.forEach((r) => { if (!merged.radii.includes(r)) merged.radii.push(r); });
      p.borders.forEach((b) => { if (!merged.borders.includes(b)) merged.borders.push(b); });
      p.numbers.forEach((n) => numbers.add(n));
    }
    merged.controls = merged.controls.slice(0, 80);
    merged.sections = merged.sections.slice(0, 60);
    merged.numbers = [...numbers].sort((a, b) => a - b);

    const record = {
      tool: TOOL_NAME,
      schema_version: SCHEMA_VERSION,
      id: args.id,
      url: args.url,
      extracted_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      driven_holds: args.holds,
      ...merged,
    };
    mkdirSync(args.out, { recursive: true });
    const file = path.join(args.out, `${args.id}-styles.json`);
    writeFileSync(file, JSON.stringify(record, null, 1), "utf8");
    console.error(
      `${args.id}: ${record.type.length} type settings, ${record.controls.length} controls, ` +
      `${record.transitions.length} transitions, ${record.colors.length} colors, ` +
      `${record.numbers.length} distinct measured values -> ${file}`
    );
  } finally {
    await browser.close().catch(() => {});
  }
}

main();
