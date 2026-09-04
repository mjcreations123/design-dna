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

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import path from "node:path";
import process from "node:process";
import {
  aggregateServedContent,
  applyManifestState,
  beginServedContentCapture,
  installDomInspection,
  navigateExact,
  normalizeHttpUrl,
  traverseScrollSurfaces,
} from "./browser_evidence.mjs";
import { browserExecutableIdentity, discoverBrowserExecutable, resolvePlaywright } from "./playwright_resolver.mjs";

const TOOL_NAME = "extract_reference_styles.mjs";
const SCHEMA_VERSION = 3;
export const REQUIRED_SERVED_RELOADS = 2;
const SCRIPT_PATH = path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const PRODUCER_SCRIPT_SHA256 = createHash("sha256").update(readFileSync(SCRIPT_PATH)).digest("hex");
const BROWSER_EVIDENCE_SHA256 = createHash("sha256").update(readFileSync(path.join(path.dirname(SCRIPT_PATH), "browser_evidence.mjs"))).digest("hex");
const OBSERVER_SCRIPT_SHA256 = createHash("sha256").update(readFileSync(path.join(path.dirname(SCRIPT_PATH), "observe_reference.mjs"))).digest("hex");
const PLAYWRIGHT_RESOLVER_SHA256 = createHash("sha256").update(readFileSync(path.join(path.dirname(SCRIPT_PATH), "playwright_resolver.mjs"))).digest("hex");

const EXTRACT = `(() => {
  const inspection = { document_roots: 0, open_shadow_roots: 0, captured_closed_shadow_roots: 0, same_origin_iframes: 0,
    hook_installed: window.__designDnaDomInspection === 'response-bodies-v1',
    blocked_frames: [], unknown_closed_surfaces: [], pseudo_elements: 0, canvases: [], complete: true };
  const roots = [];
  const enqueue = (root, scope, mode = null) => {
    if (!root || roots.some((item) => item.root === root)) return;
    roots.push({ root, scope });
    if (root.nodeType === 9) inspection.document_roots += 1;
    else if (mode === 'closed') inspection.captured_closed_shadow_roots += 1;
    else inspection.open_shadow_roots += 1;
  };
  enqueue(document, 'document');
  for (let index = 0; index < roots.length; index += 1) {
    const { root, scope } = roots[index];
    if (root.nodeType === 9) {
      const captured = root.defaultView.__designDnaCapturedShadowRoots || [];
      captured.forEach((item) => enqueue(item.root, scope + '>shadow:' + item.host.tagName.toLowerCase(), item.mode));
    }
    root.querySelectorAll('*').forEach((element) => {
      if (element.shadowRoot) enqueue(element.shadowRoot, scope + '>shadow:' + element.tagName.toLowerCase());
      if (element.tagName !== 'IFRAME') return;
      try {
        if (!element.contentDocument) throw new Error('cross-origin or unavailable frame');
        inspection.same_origin_iframes += 1; enqueue(element.contentDocument, scope + '>iframe');
      } catch {
        const box = element.getBoundingClientRect();
        if (box.width > 1 && box.height > 1) inspection.blocked_frames.push(element.src || '(unattributed iframe)');
      }
    });
  }
  const all = (selector) => roots.flatMap(({ root }) => [...root.querySelectorAll(selector)]);
  const styleOf = (element, pseudo) => element.ownerDocument.defaultView.getComputedStyle(element, pseudo);
  const capturedHosts = new Set(roots.filter(({ root }) => root.nodeType === 9)
    .flatMap(({ root }) => (root.defaultView.__designDnaCapturedShadowRoots || []).map((item) => item.host)));
  all('*').filter((element) => element.tagName.includes('-') && !element.shadowRoot && !capturedHosts.has(element) && !element.childNodes.length)
    .forEach((element) => { const box = element.getBoundingClientRect(); if (box.width > 1 && box.height > 1) inspection.unknown_closed_surfaces.push(element.tagName.toLowerCase()); });
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
    const s = styleOf(el);
    if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0) return null;
    const b = el.getBoundingClientRect();
    if (b.width < 2 || b.height < 2) return null;
    if (window.__dnaFirstScreenOnly && (b.bottom <= 0 || b.top >= innerHeight)) return null;
    return { s, b };
  };
  const ownText = (el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.nodeValue.trim());
  const fontFingerprint = (family, weight, style) => {
    try {
      const canvas = document.createElement('canvas'); canvas.width = 720; canvas.height = 150;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#000'; ctx.font = style + ' ' + weight + ' 96px ' + family;
      ctx.textBaseline = 'alphabetic';
      const probe = 'Hamburgefontsiv 0123 Il1 @&?';
      ctx.fillText(probe, 4, 108);
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      let hash = 2166136261, hash2 = 2654435769, ink = 0;
      for (let i = 3; i < data.length; i += 4) {
        if (!data[i]) continue;
        const signal = ((i / 4) & 0xffff) ^ data[i];
        ink += 1; hash ^= signal; hash = Math.imul(hash, 16777619);
        hash2 ^= signal + ink; hash2 = Math.imul(hash2, 2246822519);
      }
      const H = ctx.measureText('H'), x = ctx.measureText('x');
      const cap = H.actualBoundingBoxAscent || 0;
      return {
        raster: (hash >>> 0).toString(16).padStart(8, '0') + (hash2 >>> 0).toString(16).padStart(8, '0'), ink,
        probe_width: round(ctx.measureText(probe).width),
        x_ratio: cap ? round((x.actualBoundingBoxAscent || 0) / cap) : null,
        i_ratio: cap ? round(ctx.measureText('I').width / cap) : null,
      };
    } catch { return null; }
  };

  /* ---- type: every distinct setting that actually carries words ---- */
  const typeMap = new Map();
  all('*').forEach((el) => {
    if (!ownText(el)) return;
    const v = vis(el); if (!v) return;
    const s = v.s;
    const size = round(px(s.fontSize));
    const lead = px(s.lineHeight);
    const family = s.fontFamily.split(',')[0].replace(/["']/g, '');
    const key = [family, size, s.fontWeight,
      s.letterSpacing, s.textTransform, s.fontStyle].join('|');
    const row = typeMap.get(key) || {
      family, stack: s.fontFamily,
      size, weight: s.fontWeight,
      leading: lead && size ? round(lead / size) : null,
      tracking: s.letterSpacing === 'normal' ? 'normal' : round(px(s.letterSpacing)),
      transform: s.textTransform, style: s.fontStyle,
      color: s.color, count: 0, sample: '',
      font_fingerprint: fontFingerprint(s.fontFamily, s.fontWeight, s.fontStyle),
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
  all('a, button, input, textarea, select, [role="button"]').forEach((el) => {
    const v = vis(el); if (!v) return;
    const s = v.s;
    if (controls.length > 60) return;
    const row = {
      tag: el.tagName.toLowerCase(),
      cls: (typeof el.className === 'string' ? el.className : '').trim().slice(0, 40),
      w: Math.round(v.b.width), h: Math.round(v.b.height),
      padding: s.padding, radius: s.borderRadius,
      border: s.borderTopWidth + ' ' + s.borderTopStyle,
      border_width: s.borderTopWidth, border_style: s.borderTopStyle, border_color: s.borderTopColor,
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
  all('*').forEach((el) => {
    const s = styleOf(el);
    if (!s.transitionDuration || s.transitionDuration === '0s') return;
    const key = s.transitionProperty + '|' + s.transitionDuration + '|' + s.transitionTimingFunction;
    trans.set(key, (trans.get(key) || 0) + 1);
    noteNums(s.transitionDuration); noteNums(s.transitionTimingFunction);
  });

  /* ---- sections: their grounds, their heights, how they divide ---- */
  const sections = [];
  all('body > *, main > *, body > * > *').forEach((el) => {
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
      radius: s.borderRadius, border_width: s.borderTopWidth, border_style: s.borderTopStyle,
      border_color: s.borderTopColor, shadow: s.boxShadow === 'none' ? null : s.boxShadow,
      background_image: s.backgroundImage === 'none' ? null : s.backgroundImage,
      opacity: Number(s.opacity), transform: s.transform === 'none' ? null : s.transform,
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
  all('*').forEach((el) => {
    const v = vis(el); if (!v) return;
    const a = (v.b.width * v.b.height) / (innerWidth * innerHeight);
    bump(v.s.backgroundColor, 'background', a);
    if (ownText(el)) bump(v.s.color, 'text', 0);
    if (parseFloat(v.s.borderTopWidth) > 0) bump(v.s.borderTopColor, 'border', 0);
  });

  /* ---- radii and border widths in use ---- */
  const radii = new Set(), borders = new Set();
  all('*').forEach((el) => {
    const s = styleOf(el);
    if (s.borderRadius && s.borderRadius !== '0px') { radii.add(s.borderRadius); noteNums(s.borderRadius); }
    const bw = parseFloat(s.borderTopWidth);
    if (bw > 0) { borders.add(s.borderTopWidth); noteNums(s.borderTopWidth); }
  });

  /* ---- surfaces/layout: values that used to escape the provenance gate ---- */
  const surfaceMap = new Map();
  all('*').forEach((el) => {
    const v = vis(el); if (!v) return;
    const s = v.s;
    const area = (v.b.width * v.b.height) / (innerWidth * innerHeight);
    const backgroundImage = s.backgroundImage === 'none' ? null : s.backgroundImage;
    const shadow = s.boxShadow === 'none' ? null : s.boxShadow;
    const transform = s.transform === 'none' ? null : s.transform;
    const gap = s.gap === 'normal' ? null : s.gap;
    const meaningful = backgroundImage || shadow || transform || gap || parseFloat(s.borderTopWidth) > 0 ||
      s.borderRadius !== '0px' || Number(s.opacity) !== 1 || area >= 0.04;
    if (!meaningful) return;
    const key = [el.tagName, s.padding, gap, s.borderRadius, s.borderTop, shadow, backgroundImage,
      s.opacity, transform, Math.round(v.b.width), Math.round(v.b.height)].join('|');
    const row = surfaceMap.get(key) || {
      tag: el.tagName.toLowerCase(), cls: (typeof el.className === 'string' ? el.className : '').trim().slice(0, 80),
      w: Math.round(v.b.width), h: Math.round(v.b.height), area: round(area),
      padding: s.padding, gap, radius: s.borderRadius,
      border_width: s.borderTopWidth, border_style: s.borderTopStyle, border_color: s.borderTopColor,
      shadow, background_image: backgroundImage, opacity: Number(s.opacity), transform, count: 0,
    };
    row.count += 1; surfaceMap.set(key, row);
    [s.padding, gap, s.borderRadius, s.borderTopWidth, shadow, transform, v.b.width, v.b.height, s.opacity].forEach(noteNums);
  });

  /* Pseudo-elements, open shadow trees, same-origin frames and canvas output
     are visible design too; omitting them would leave producer choices outside
     the provenance record. */
  const pseudo_elements = [];
  all('*').forEach((el) => {
    for (const pseudo of ['::before', '::after']) {
      const s = styleOf(el, pseudo);
      const content = String(s.content || '');
      const paints = (content !== 'none' && content !== 'normal') || s.backgroundImage !== 'none' ||
        s.backgroundColor !== 'rgba(0, 0, 0, 0)' || parseFloat(s.borderTopWidth) > 0 || s.boxShadow !== 'none';
      if (!paints || s.display === 'none' || Number(s.opacity) === 0) continue;
      inspection.pseudo_elements += 1;
      pseudo_elements.push({ pseudo, owner_tag: el.tagName.toLowerCase(),
        owner_class: (typeof el.className === 'string' ? el.className : '').trim().slice(0, 80),
        content: content.slice(0, 120), color: s.color, background: s.backgroundColor,
        background_image: s.backgroundImage === 'none' ? null : s.backgroundImage,
        border_width: s.borderTopWidth, border_style: s.borderTopStyle, border_color: s.borderTopColor,
        radius: s.borderRadius, shadow: s.boxShadow === 'none' ? null : s.boxShadow,
        opacity: Number(s.opacity), transform: s.transform === 'none' ? null : s.transform,
        font_family: s.fontFamily, font_size: s.fontSize, font_weight: s.fontWeight });
      bump(s.backgroundColor, 'pseudo-background', 0); bump(s.color, 'pseudo-text', 0);
      [s.borderTopWidth, s.borderRadius, s.fontSize, s.transform].forEach(noteNums);
    }
    if (el.tagName !== 'CANVAS') return;
    if (!vis(el)) return;
    try {
      const encoded = el.toDataURL('image/png');
      inspection.canvases.push({ width: el.width, height: el.height, readable: true,
        rendered_bytes_base64: Math.max(0, encoded.length - encoded.indexOf(',') - 1),
        fingerprint: encoded.slice(0, 128) + ':' + encoded.slice(-128) });
    } catch (error) {
      inspection.canvases.push({ width: el.width, height: el.height, readable: false, error: String(error).slice(0, 160) });
    }
  });
  inspection.complete = inspection.hook_installed && inspection.blocked_frames.length === 0 && inspection.unknown_closed_surfaces.length === 0 && inspection.canvases.length === 0;
  const font_faces = roots.flatMap(({ root }) => root.nodeType === 9 && root.fonts ? [...root.fonts] : [])
    .map((face) => ({ family: String(face.family || '').replace(/["']/g, ''), weight: face.weight,
      style: face.style, stretch: face.stretch, status: face.status }));

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
    surfaces: [...surfaceMap.values()].sort((a, b) => b.area - a.area).slice(0, 120),
    pseudo_elements,
    font_faces: font_faces.sort((a, b) => a.family.localeCompare(b.family)),
    numbers: [...numbers].sort((a, b) => a - b),
    inspection,
  };
})()`;

function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }, null, 2) + "\n");
  process.exit(2);
}

function parseArgs(argv) {
  const out = {
    url: null, id: null, out: null,
    browser: process.env.DESIGN_DNA_BROWSER_EXECUTABLE || process.env.CHROME || null,
    holds: 6, width: 1440, height: 900, buildId: null, runId: null, firstScreen: false,
    manifest: null, routeKey: null, viewportName: null, observation: null,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--url") out.url = argv[++i];
    else if (a === "--id") out.id = argv[++i];
    else if (a === "--out") out.out = argv[++i];
    else if (a === "--browser-executable") out.browser = argv[++i];
    else if (a === "--holds") out.holds = Number(argv[++i]);
    else if (a === "--width") out.width = Number(argv[++i]);
    else if (a === "--height") out.height = Number(argv[++i]);
    else if (a === "--build-id") out.buildId = argv[++i];
    else if (a === "--run-id") out.runId = argv[++i];
    else if (a === "--manifest") out.manifest = argv[++i];
    else if (a === "--route-key") out.routeKey = argv[++i];
    else if (a === "--viewport") out.viewportName = argv[++i];
    else if (a === "--observation") out.observation = argv[++i];
    else if (a === "--first-screen") out.firstScreen = true;
    else if (a === "--help" || a === "-h") {
      process.stdout.write("extract_reference_styles.mjs --url URL --id ID --out DIR [--observation FILE] [--manifest FILE --route-key KEY --viewport NAME --build-id ID --run-id ID] [--browser-executable FILE]\n");
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${a}`);
  }
  return out;
}

function loadPlaywright() {
  try {
    return resolvePlaywright({ moduleUrl: import.meta.url });
  } catch (error) {
    fail(error?.code || "playwright-unavailable", String(error?.message || error));
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

const uniqueRows = (rows) => {
  const seen = new Set();
  return rows.filter((row) => {
    const key = JSON.stringify(row);
    if (seen.has(key)) return false;
    seen.add(key); return true;
  });
};

function mergePasses(passes) {
  const merged = {
    measured_viewport: passes[0]?.viewport || null, type: [], controls: [], transitions: [], sections: [],
    colors: [], radii: [], borders: [], surfaces: [], pseudo_elements: [], font_faces: [], numbers: [], inspections: [],
  };
  const numbers = new Set();
  for (const pass of passes) {
    for (const key of ["type", "controls", "transitions", "sections", "colors", "surfaces", "pseudo_elements", "font_faces"]) {
      merged[key].push(...(pass[key] || []));
    }
    if (pass.inspection) merged.inspections.push(pass.inspection);
    for (const value of pass.radii || []) if (!merged.radii.includes(value)) merged.radii.push(value);
    for (const value of pass.borders || []) if (!merged.borders.includes(value)) merged.borders.push(value);
    for (const value of pass.numbers || []) numbers.add(value);
  }
  for (const key of ["type", "controls", "transitions", "sections", "colors", "surfaces", "pseudo_elements", "font_faces"]) {
    merged[key] = uniqueRows(merged[key]);
  }
  merged.numbers = [...numbers].sort((a, b) => a - b);
  return merged;
}

async function captureState(page, state, holds, firstScreen = false) {
  await page.evaluate((value) => { window.__dnaFirstScreenOnly = value; }, firstScreen);
  const application = await applyManifestState(page, state);
  const passes = [await page.evaluate(EXTRACT)];
  if (firstScreen) return { attempted: 1, covered: 1, passes, application, scroll: { complete: true, surfaces: [] } };
  const scroll = await traverseScrollSurfaces(page, { maxTicks: Math.max(240, holds * 40), settleMs: 300,
    onTick: async () => { passes.push(await page.evaluate(EXTRACT)); } });
  return { attempted: 1, covered: scroll.complete ? 1 : 0, passes, application, scroll };
}

function readBoundJson(file, code) {
  try { return JSON.parse(readFileSync(file, "utf8")); }
  catch (error) { fail(code, `${file}: ${String(error).slice(0, 200)}`); }
}

const canonicalStateIds = (sheet) => Object.keys(sheet || {}).sort().join("\n");

function resolveInputBinding(args) {
  if (!args.id.startsWith("build-")) {
    const file = path.resolve(args.observation || path.join(args.out, `${args.id}-observation.json`));
    const payload = readBoundJson(file, "observation-unreadable");
    if (payload?.tool !== "observe_reference.mjs" || !Number.isInteger(payload.schema_version) || payload.schema_version < 5 ||
        payload.producer_script_sha256 !== OBSERVER_SCRIPT_SHA256 || payload.id !== args.id ||
        normalizeHttpUrl(payload.url) !== normalizeHttpUrl(args.url) ||
        !payload.states_by_viewport?.wide || !payload.states_by_viewport?.narrow ||
        !Object.keys(payload.states_by_viewport.wide).length ||
        canonicalStateIds(payload.states_by_viewport.wide) !== canonicalStateIds(payload.states_by_viewport.narrow)) {
      fail("observation-binding", "Reference style extraction requires the current schema-5 observation for the same id and exact URL.");
    }
    return { sourceObservation: { id: payload.id, url: payload.url, file: path.basename(file),
      sha256: createHash("sha256").update(readFileSync(file)).digest("hex") }, manifest: null,
      states: Object.values(payload.states_by_viewport.wide).map((state) => ({ id: state.id, url: state.url,
        kind: state.kind, trigger: state.trigger, expectation: state.expectation })) };
  }
  if (!args.buildId || !args.runId || !args.manifest || !args.routeKey || !args.viewportName) {
    fail("missing-build-binding", "Build style records require --build-id, --run-id, --manifest, --route-key and --viewport.");
  }
  const file = path.resolve(args.manifest);
  const manifest = readBoundJson(file, "manifest-unreadable");
  const route = manifest?.routes?.find((item) => item.key === args.routeKey);
  const viewport = manifest?.viewports?.find((item) => item.name === args.viewportName);
  if (manifest.schema_version !== 2 || !manifest.manifest_id || !route || !viewport ||
      normalizeHttpUrl(route.url) !== normalizeHttpUrl(args.url) || viewport.width !== args.width || viewport.height !== args.height) {
    fail("manifest-binding", "Build style route, URL and viewport must match the exact schema-2 manifest cell.");
  }
  const projectRoot = path.basename(path.dirname(file)) === ".design-dna" ? path.dirname(path.dirname(file)) : path.dirname(file);
  const observationPath = path.resolve(projectRoot, route.mapped_reference_observation || "");
  let observation;
  try { observation = JSON.parse(readFileSync(observationPath, "utf8")); } catch { fail("manifest-binding", "Mapped observation is unreadable."); }
  if (createHash("sha256").update(readFileSync(observationPath)).digest("hex") !== route.mapped_reference_sha256 ||
      observation.tool !== "observe_reference.mjs" || !Number.isInteger(observation.schema_version) || observation.schema_version < 5 ||
      observation.producer_script_sha256 !== OBSERVER_SCRIPT_SHA256 || observation.id !== route.mapped_reference_id ||
      route.states.some((state) => !observation.states_by_viewport?.wide?.[state.mapped_reference_state_id] ||
        !observation.states_by_viewport?.narrow?.[state.mapped_reference_state_id])) {
    fail("manifest-binding", "Mapped observation bytes and every wide+narrow source-state ID must be exact and current.");
  }
  return { sourceObservation: null, manifest: { id: manifest.manifest_id, file: args.manifest,
    sha256: createHash("sha256").update(readFileSync(file)).digest("hex") }, states: route.states };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.url || !args.id || !args.out) {
    fail("usage", "--url, --id and --out are required.");
  }
  if (!Number.isInteger(args.width) || !Number.isInteger(args.height) || args.width < 280 || args.height < 480) {
    fail("invalid-viewport", "--width and --height must be sensible integer viewport dimensions.");
  }
  const binding = resolveInputBinding(args);
  const loaded = loadPlaywright();
  const browserDependency = loadBrowserDependency(loaded, args.browser);
  const browser = await loaded.playwright.chromium.launch({ executablePath: browserDependency.file });
  try {
    const passes = [];
    const stateCoverage = [];
    const servedProbes = [];
    const navigations = [];
    const viewports = args.buildId
      ? [{ name: args.viewportName, width: args.width, height: args.height }]
      : [{ name: "wide", width: 1440, height: 900 }, { name: "narrow", width: 390, height: 844 }];
    for (const viewport of viewports) {
      const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
      await installDomInspection(context);
      const page = await context.newPage();
      try {
        for (const state of binding.states) {
          const stateUrl = state.url || args.url;
          const restLoads = [];
          for (let reload = 0; reload < REQUIRED_SERVED_RELOADS; reload += 1) {
            const contentCapture = beginServedContentCapture(page, stateUrl);
            const navigation = await navigateExact(page, stateUrl);
            contentCapture.setFinalResponse(navigation);
            await page.evaluate(() => document.fonts?.ready).catch(() => {});
            await page.waitForTimeout(500);
            const served = await contentCapture.finish({ route_key: args.routeKey || `${args.id}:${state.id}`, viewport: viewport.name });
            servedProbes.push(served);
            restLoads.push(served);
            navigations.push({ viewport: viewport.name, state_id: state.id, reload_index: reload + 1, ...navigation });
          }
          if (restLoads.length !== REQUIRED_SERVED_RELOADS || new Set(restLoads.map((entry) => entry.sha256)).size !== 1) {
            fail("served-content-reload-drift", `${args.id}/${viewport.name}/${state.id} returned different response-body identities across its two required exact loads.`);
          }
          const result = await captureState(page, state, args.holds, args.firstScreen);
          passes.push(...result.passes);
          const inspectionComplete = result.passes.every((pass) => pass.inspection?.complete !== false);
          stateCoverage.push({ viewport: viewport.name, state_id: state.id, state_kind: state.kind,
            trigger: state.trigger, attempted: result.attempted, covered: result.covered,
            scroll_surfaces: result.scroll?.surfaces || [], inspection_complete: inspectionComplete,
            pass: result.attempted > 0 && result.covered === result.attempted && inspectionComplete && result.scroll?.complete !== false });
        }
      } finally {
        await context.close();
      }
    }
    if (!passes.length || stateCoverage.some((state) => !state.pass)) {
      fail("state-coverage", "Every declared state must exist and be fully exercised: " + stateCoverage.map((s) => `${s.state_id} ${s.covered}/${s.attempted}`).join(", "));
    }
    const merged = mergePasses(passes);
    const uninspectable = [...new Set(merged.inspections.flatMap((item) => [
      ...(item.blocked_frames || []).map((value) => `cross-origin-frame:${value}`),
      ...(!item.hook_installed ? ["dom-inspection-hook-not-installed"] : []),
      ...(item.unknown_closed_surfaces || []).map((value) => `unknown-closed-shadow:${value}`),
      ...(item.canvases || []).map(() => "canvas-visible-content-not-proven"),
    ]))];
    const inspection = {
      complete: merged.inspections.length > 0 && merged.inspections.every((item) => item.complete) && uninspectable.length === 0,
      pseudo_elements: Math.max(0, ...merged.inspections.map((item) => item.pseudo_elements || 0)),
      open_shadow_roots: Math.max(0, ...merged.inspections.map((item) => item.open_shadow_roots || 0)),
      captured_closed_shadow_roots: Math.max(0, ...merged.inspections.map((item) => item.captured_closed_shadow_roots || 0)),
      same_origin_iframes: Math.max(0, ...merged.inspections.map((item) => item.same_origin_iframes || 0)),
      canvases: Math.max(0, ...merged.inspections.map((item) => (item.canvases || []).length)),
      uninspectable,
    };
    if (!inspection.complete) fail("dom-inspection-incomplete", `Visible DOM/canvas content could not be inspected: ${uninspectable.join("; ") || "unknown inspection gap"}`);
    const servedContent = aggregateServedContent(servedProbes);
    const resourceUrls = [...new Set(servedProbes.flatMap((probe) => probe.resources.map((resource) => resource.url)))].sort();
    mkdirSync(args.out, { recursive: true });
    const resourceLedgerFile = `${args.id}-resource-ledger.json`;
    const resourceLedgerPath = path.join(args.out, resourceLedgerFile);
    const resourceLedgerBytes = Buffer.from(JSON.stringify(servedContent, null, 2) + "\n", "utf8");
    writeFileSync(resourceLedgerPath, resourceLedgerBytes);
    const resourceHash = createHash("sha256").update(resourceLedgerBytes).digest("hex");

    const record = {
      tool: TOOL_NAME,
      schema_version: SCHEMA_VERSION,
      producer_script_sha256: PRODUCER_SCRIPT_SHA256,
      runtime_identity: { "extract_reference_styles.mjs": PRODUCER_SCRIPT_SHA256,
        "browser_evidence.mjs": BROWSER_EVIDENCE_SHA256,
        "playwright_resolver.mjs": PLAYWRIGHT_RESOLVER_SHA256,
        "playwright-entry": loaded.dependency.resolved_file_sha256,
        "browser-executable": browserDependency.sha256 },
      dependencies: { playwright: loaded.dependency, browser_executable: browserDependency },
      id: args.id,
      url: args.url,
      build_id: args.buildId,
      run_id: args.runId,
      route_key: args.routeKey,
      viewport: args.viewportName,
      manifest_id: binding.manifest?.id || null,
      manifest_file: binding.manifest ? binding.manifest.file : null,
      manifest_sha256: binding.manifest?.sha256 || null,
      source_observation: binding.sourceObservation,
      extracted_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      driven_holds: args.holds,
      states_checked: binding.states.map((state) => state.id),
      viewports_measured: viewports,
      first_screen_only: args.firstScreen,
      state_coverage: stateCoverage,
      navigations,
      resource_urls: resourceUrls,
      resource_manifest_sha256: resourceHash,
      resource_ledger: { file: resourceLedgerFile, sha256: resourceHash,
        algorithm: servedContent.algorithm, served_content_sha256: servedContent.sha256 },
      served_content: servedContent,
      served_content_identity: servedContent,
      inspection,
      ...merged,
    };
    const file = path.join(args.out, `${args.id}-styles.json`);
    writeFileSync(file, JSON.stringify(record, null, 2) + "\n", "utf8");
    process.stdout.write(JSON.stringify({
      ok: true, record: file,
      verdict: `${args.id}: ${record.type.length} type settings, ${record.controls.length} controls, ${record.surfaces.length} surfaces across ${viewports.length} viewport(s) and ${binding.states.length} state(s).`,
    }, null, 2) + "\n");
  } finally {
    await browser.close().catch(() => {});
  }
}

const invokedDirectly = process.argv[1]
  && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
if (invokedDirectly) main();
