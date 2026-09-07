#!/usr/bin/env node
/**
 * study_reference.mjs
 *
 * One command, a few minutes, one reference site: everything a designer needs
 * to COPY the site's front-end design, written by the tool, not by the AI.
 *
 *   node study_reference.mjs --url https://example.test/ --id strong-1 --out .design-dna/references
 *        [--inner 3] [--video-seconds 25] [--browser-executable FILE]
 *
 * For each width (wide 1440x900, narrow 390x844) it records:
 *   - the design system out of the live CSS: fonts and where they load from,
 *     the type scale actually used, colors weighted by painted area (so the
 *     dominant ground is a measurement, not a taste), radii, shadows, controls,
 *     declared transitions, @keyframes, and the animation libraries running;
 *   - the layout outline: every top-level section with its box, ground, and
 *     what is in it;
 *   - motion: a wheel-driven pass sampled at fourteen scroll positions read
 *     against the viewport (pinned, travelling, swapping, revealing, parallax),
 *     what the Web Animations API says is animating at six depths, a
 *     pointer-follow probe, autoplay video and canvas;
 *   - hover: the first twenty visible controls, each moved onto with the real
 *     pointer, and whether anything responded;
 *   - a real-time scroll-through video (webm) and an eight-frame contact sheet;
 *   - up to --inner inner pages from the site's own navigation, the same way
 *     but shorter.
 *
 * Output: <out>/<id>/study.json (machine record), <out>/<id>/sheet.md (the
 * reference sheet the AI reads), frames, videos and contact sheets. No leases,
 * no state contracts, no machine-wide slots: the only bounds are per call.
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { resolvePlaywright, discoverBrowserExecutable } from "./playwright_resolver.mjs";
import { TAG_PROBES, SAMPLE_PROBES, deriveMechanisms, finalizeMechanisms, mechanismWeight } from "./observe_reference.mjs";
import { collectSameOriginLinks } from "./browser_evidence.mjs";

const TOOL = "study_reference.mjs";
const SCHEMA_VERSION = 1;
const VIEWPORTS = [
  { name: "wide", width: 1440, height: 900 },
  { name: "narrow", width: 390, height: 844 },
];
const MOTION_TICKS = 14;          // wheel steps of 0.72 viewport heights
const TICK_SETTLE_MS = 350;
const WAAPI_DEPTHS = [0, 0.2, 0.4, 0.6, 0.8, 1];
const HOVER_TARGETS = 20;
const CONTACT_FRAMES = 8;
const CALL_TIMEOUT_MS = 45_000;   // any single browser call; a page that is alive answers well within this

function parseArgs(argv) {
  const out = { url: null, id: null, outDir: null, inner: 3, videoSeconds: 25, browserExecutable: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--url") out.url = argv[++i];
    else if (a === "--id") out.id = argv[++i];
    else if (a === "--out") out.outDir = argv[++i];
    else if (a === "--inner") out.inner = Number(argv[++i]);
    else if (a === "--video-seconds") out.videoSeconds = Number(argv[++i]);
    else if (a === "--browser-executable") out.browserExecutable = argv[++i];
    else if (a === "--help" || a === "-h") { process.stdout.write(usage()); process.exit(0); }
    else fail("invalid-argument", `Unknown argument ${a}.\n${usage()}`);
  }
  if (!out.url || !/^https?:\/\//.test(out.url)) fail("invalid-url", "--url must be an absolute http(s) URL.");
  if (!out.id || !/^[a-z0-9][a-z0-9-]{0,63}$/.test(out.id)) fail("invalid-id", "--id must be a short lowercase slug.");
  if (!out.outDir) fail("invalid-out", "--out must name a directory.");
  if (!Number.isInteger(out.inner) || out.inner < 0 || out.inner > 8) fail("invalid-inner", "--inner must be 0-8.");
  if (!Number.isFinite(out.videoSeconds) || out.videoSeconds < 10 || out.videoSeconds > 90) fail("invalid-video-seconds", "--video-seconds must be 10-90.");
  return out;
}
function usage() {
  return `usage: node ${TOOL} --url URL --id ID --out DIR [--inner N] [--video-seconds S] [--browser-executable FILE]\n`;
}
function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }, null, 2) + "\n");
  process.exit(2);
}
const sha = (buf) => createHash("sha256").update(buf).digest("hex");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function bounded(promise, label, ms = CALL_TIMEOUT_MS) {
  let timer;
  const timeout = new Promise((_, reject) => { timer = setTimeout(() => reject(Object.assign(new Error(`${label} exceeded ${ms}ms`), { code: "browser-call-timeout" })), ms); });
  try { return await Promise.race([promise, timeout]); } finally { clearTimeout(timer); }
}

/* ------------------------------------------------------------------ in-page */

// Design system out of the live CSS. Colors are weighted by painted area so
// the dominant ground is measured; type is grouped by role.
const DESIGN_SYSTEM = `(() => {
  const vw = innerWidth, vh = innerHeight;
  const area = (r) => Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0)) * Math.max(0, r.bottom - r.top);
  const els = [...document.querySelectorAll('body *')].filter((el) => {
    const r = el.getBoundingClientRect(); return r.width >= 8 && r.height >= 8;
  });
  const transparent = (c) => !c || c === 'transparent' || /rgba\\([^)]*,\\s*0\\)$/.test(c);
  const grounds = new Map(), inks = new Map(), fonts = new Map(), type = new Map();
  const radii = new Map(), shadows = new Map(), transitions = new Map();
  const controls = [];
  const bump = (map, key, by, sample) => { const cur = map.get(key) || { weight: 0, count: 0, sample: sample || null }; cur.weight += by; cur.count += 1; map.set(key, cur); };
  for (const el of els) {
    const s = getComputedStyle(el); const r = el.getBoundingClientRect(); const a = area(r);
    if (!transparent(s.backgroundColor)) bump(grounds, s.backgroundColor, a);
    if (s.backgroundImage && s.backgroundImage !== 'none' && /gradient/.test(s.backgroundImage)) bump(grounds, 'gradient:' + s.backgroundImage.slice(0, 80), a);
    const text = (el.childNodes && [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) ? el.textContent.trim() : '';
    if (text) {
      const fam = s.fontFamily.split(',')[0].replace(/["']/g, '').trim();
      const size = parseFloat(s.fontSize);
      bump(inks, s.color, text.length * size);
      bump(fonts, fam, text.length);
      const role = /^H[1-6]$/.test(el.tagName) ? el.tagName.toLowerCase() : (el.closest('nav,header') ? 'nav' : (el.matches('a,button,[role=button]') ? 'control' : (size >= 28 ? 'display' : 'body')));
      const key = [role, fam, Math.round(size), s.fontWeight, s.lineHeight, s.letterSpacing, s.textTransform].join('|');
      bump(type, key, text.length, { role, family: fam, size: Math.round(size * 10) / 10, weight: s.fontWeight, line_height: s.lineHeight, letter_spacing: s.letterSpacing, transform: s.textTransform, color: s.color, sample: text.slice(0, 60) });
    }
    if (s.borderRadius && s.borderRadius !== '0px') bump(radii, s.borderRadius, a);
    if (s.boxShadow && s.boxShadow !== 'none') bump(shadows, s.boxShadow, a);
    if (s.transitionDuration && s.transitionDuration !== '0s') bump(transitions, s.transitionProperty + ' ' + s.transitionDuration + ' ' + s.transitionTimingFunction, 1);
    if (controls.length < 40 && el.matches('a,button,[role=button],input,select,textarea') && r.width >= 24 && r.height >= 16 && r.top < vh * 3) {
      controls.push({ tag: el.tagName.toLowerCase(), text: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 40),
        w: Math.round(r.width), h: Math.round(r.height), padding: s.padding, radius: s.borderRadius, border: s.border, bg: s.backgroundColor, color: s.color,
        font: s.fontFamily.split(',')[0].replace(/["']/g, '') + ' ' + s.fontWeight + ' ' + s.fontSize, transform: s.textTransform, letter_spacing: s.letterSpacing });
    }
  }
  const top = (map, n, f) => [...map.entries()].sort((x, y) => y[1].weight - x[1].weight).slice(0, n).map(([k, v]) => f(k, v));
  const faces = [];
  try { document.fonts.forEach((f) => faces.push({ family: f.family.replace(/["']/g, ''), weight: f.weight, style: f.style, status: f.status })); } catch {}
  const faceSrc = [];
  for (const sheet of document.styleSheets) {
    let rules = []; try { rules = [...sheet.cssRules]; } catch { faceSrc.push({ sheet: sheet.href, readable: false }); continue; }
    for (const rule of rules) {
      if (rule.type === 5) faceSrc.push({ family: rule.style.fontFamily.replace(/["']/g, ''), src: (rule.style.src || '').slice(0, 200), sheet: sheet.href || 'inline' });
    }
  }
  const keyframes = [];
  for (const sheet of document.styleSheets) {
    let rules = []; try { rules = [...sheet.cssRules]; } catch { continue; }
    const walk = (list) => { for (const rule of list) { if (rule.type === 7) keyframes.push({ name: rule.name, steps: rule.cssRules.length, sheet: sheet.href || 'inline' }); else if (rule.cssRules) walk([...rule.cssRules]); } };
    walk(rules);
  }
  const libs = {};
  for (const [name, test] of [['gsap', () => window.gsap], ['ScrollTrigger', () => window.ScrollTrigger || window.gsap?.plugins?.scrollTrigger], ['Lenis', () => window.Lenis || document.documentElement.classList.contains('lenis')],
    ['locomotive', () => window.LocomotiveScroll || document.querySelector('[data-scroll-container]')], ['barba', () => window.barba], ['Swiper', () => window.Swiper || document.querySelector('.swiper')],
    ['Splide', () => window.Splide || document.querySelector('.splide')], ['Flickity', () => window.Flickity || document.querySelector('.flickity-enabled')], ['lottie', () => window.lottie || document.querySelector('lottie-player,[data-animation-path]')],
    ['three', () => window.THREE || document.querySelector('canvas[data-engine*="three"]')], ['framer-motion', () => document.querySelector('[data-framer-name],[data-framer-component-type]')],
    ['webflow-ix2', () => document.querySelector('[data-wf-page],[data-w-id]')], ['nextjs', () => document.querySelector('#__next,script#__NEXT_DATA__')], ['nuxt', () => document.querySelector('#__nuxt')]]) {
    try { if (test()) libs[name] = true; } catch {}
  }
  const media = { video: [...document.querySelectorAll('video')].map((v) => { const r = v.getBoundingClientRect(); return { autoplay: v.autoplay, loop: v.loop, muted: v.muted, paused: v.paused, src: (v.currentSrc || v.src || '').slice(-80), w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top) }; }),
    canvas: [...document.querySelectorAll('canvas')].map((c) => { const r = c.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top), fixed: getComputedStyle(c).position === 'fixed' }; }),
    images: document.querySelectorAll('img').length, svg: document.querySelectorAll('svg').length };
  return {
    viewport: { w: vw, h: vh, doc_height: document.documentElement.scrollHeight },
    grounds: top(grounds, 8, (k, v) => ({ color: k, area_share: Math.round(v.weight / (vw * Math.max(vh, document.documentElement.scrollHeight)) * 1000) / 1000, elements: v.count })),
    inks: top(inks, 6, (k, v) => ({ color: k, weight: Math.round(v.weight) })),
    fonts: top(fonts, 6, (k, v) => ({ family: k, characters: v.count })),
    faces, face_sources: faceSrc.slice(0, 24),
    type_scale: top(type, 24, (k, v) => ({ ...v.sample, characters: v.weight })),
    radii: top(radii, 8, (k, v) => ({ value: k, elements: v.count })),
    shadows: top(shadows, 6, (k, v) => ({ value: k.slice(0, 120), elements: v.count })),
    transitions: top(transitions, 12, (k, v) => ({ value: k, elements: v.count })),
    controls,
    keyframes: keyframes.slice(0, 40),
    libraries: Object.keys(libs),
    media,
  };
})()`;

// Top-level sections with their boxes, grounds and contents.
const LAYOUT = `(() => {
  const root = document.querySelector('main') || document.body;
  const vw = innerWidth;
  let blocks = [...root.children];
  if (blocks.length < 3) blocks = [...root.querySelectorAll(':scope > * > *')];
  const rows = [];
  for (const el of blocks) {
    const r = el.getBoundingClientRect(); if (r.height < 120 || r.width < vw * 0.3) continue;
    const s = getComputedStyle(el);
    const heading = el.querySelector('h1,h2,h3');
    rows.push({ tag: el.tagName.toLowerCase(), class: (typeof el.className === 'string' ? el.className : '').trim().slice(0, 60), id: el.id || null,
      top: Math.round(r.top + scrollY), height: Math.round(r.height), width: Math.round(r.width),
      ground: s.backgroundColor, position: s.position, display: s.display, grid: s.display.includes('grid') ? s.gridTemplateColumns.slice(0, 80) : null,
      heading: heading ? heading.textContent.trim().slice(0, 80) : null,
      text_chars: el.textContent.trim().length, images: el.querySelectorAll('img,picture').length, videos: el.querySelectorAll('video').length,
      links: el.querySelectorAll('a').length, buttons: el.querySelectorAll('button,[role=button]').length });
  }
  const header = document.querySelector('header,[role=banner]'); const nav = document.querySelector('nav');
  const hs = header ? getComputedStyle(header) : null; const hr = header ? header.getBoundingClientRect() : null;
  return { sections: rows.slice(0, 40), header: header ? { position: hs.position, height: Math.round(hr.height), ground: hs.backgroundColor, links: header.querySelectorAll('a').length } : null,
    nav_links: nav ? [...nav.querySelectorAll('a')].slice(0, 20).map((a) => ({ text: a.textContent.trim().slice(0, 40), href: a.getAttribute('href') })) : [] };
})()`;

// What the Web Animations API says is animating right now.
const ANIMATIONS = `(() => {
  const out = [];
  for (const a of document.getAnimations()) {
    const t = a.effect?.target; if (!t) continue;
    const r = t.getBoundingClientRect?.();
    const timing = a.effect.getTiming?.() || {};
    out.push({ kind: a.constructor.name, name: a.animationName || a.transitionProperty || null, state: a.playState, duration: timing.duration, iterations: timing.iterations,
      target: t.tagName.toLowerCase() + (typeof t.className === 'string' && t.className ? '.' + t.className.trim().split(/\\s+/).slice(0, 2).join('.') : ''),
      on_screen: r ? (r.bottom > 0 && r.top < innerHeight) : null });
    if (out.length >= 40) break;
  }
  return { count: document.getAnimations().length, sample: out };
})()`;

export const HOVER_CANDIDATES = `(() => {
  const vw = innerWidth, vh = innerHeight; const rows = [];
  window.__dnaStudyHover = Number(window.__dnaStudyHover || 0);
  for (const el of document.querySelectorAll('a,button,[role=button],summary,[onclick]')) {
    const r = el.getBoundingClientRect();
    if (r.width < 16 || r.height < 12 || r.bottom <= 0 || r.top >= vh || r.right <= 0 || r.left >= vw) continue;
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || Number(cs.opacity) === 0) continue;
    if (!el.dataset.dnaStudyHover) el.dataset.dnaStudyHover = String(++window.__dnaStudyHover);
    rows.push({ id: el.dataset.dnaStudyHover, tag: el.tagName.toLowerCase(), text: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 40),
      x: r.left + r.width / 2, y: r.top + r.height / 2, w: Math.round(r.width), h: Math.round(r.height) });
    if (rows.length >= ${HOVER_TARGETS}) break;
  }
  return rows;
})()`;
const HOVER_SNAPSHOT = `((id) => {
  const el = document.querySelector('[data-dna-study-hover="' + id + '"]'); if (!el) return null;
  const rows = [el, ...el.querySelectorAll('*')].slice(0, 30).map((n) => { const s = getComputedStyle(n), r = n.getBoundingClientRect();
    return [s.color, s.backgroundColor, s.transform, s.opacity, s.filter, s.textDecorationLine, Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)].join(','); });
  const s = getComputedStyle(el);
  return { rows, transition: s.transitionDuration + ' ' + s.transitionProperty, cursor: s.cursor };
})`;

/* ------------------------------------------------------------------ study */

export async function motionPass(page, viewport) {
  // Fourteen real wheel steps read against the viewport; the same probes and
  // the same derivation as the full observer, at a fraction of the positions.
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(300);
  await bounded(page.evaluate(TAG_PROBES), "tag-probes");
  const ticks = [await bounded(page.evaluate(SAMPLE_PROBES), "sample-probes")];
  const delta = Math.round(viewport.height * 0.72);
  await page.mouse.move(Math.round(viewport.width / 2), Math.round(viewport.height / 2));
  for (let i = 0; i < MOTION_TICKS; i += 1) {
    await bounded(page.mouse.wheel(0, delta), "wheel", 15_000);
    await sleep(TICK_SETTLE_MS);
    await bounded(page.evaluate(TAG_PROBES), "tag-probes");
    const sample = await bounded(page.evaluate(SAMPLE_PROBES), "sample-probes");
    ticks.push(sample);
    if (sample.y + viewport.height >= sample.docH - 2 && i >= 2) break;
  }
  const derived = deriveMechanisms(ticks);
  // Pointer follow: something that moves with the pointer and returns with it.
  let pointerFollow = null;
  const docHeight = ticks[ticks.length - 1].docH || viewport.height;
  const points = [{ x: Math.max(40, viewport.width * 0.14), y: Math.max(40, viewport.height * 0.28) }, { x: Math.min(viewport.width - 40, viewport.width * 0.84), y: Math.min(viewport.height - 40, viewport.height * 0.68) }];
  for (const fraction of [0, 0.5]) {
    if (pointerFollow) break;
    try {
      await page.evaluate((y) => window.scrollTo(0, y), Math.round(docHeight * fraction));
      await sleep(400);
      await bounded(page.evaluate(TAG_PROBES), "tag-probes");
      await page.mouse.move(points[0].x, points[0].y); await sleep(350);
      const a = await bounded(page.evaluate(SAMPLE_PROBES), "sample-probes");
      await page.mouse.move(points[1].x, points[1].y, { steps: 12 }); await sleep(350);
      const b = await bounded(page.evaluate(SAMPLE_PROBES), "sample-probes");
      await page.mouse.move(points[0].x, points[0].y, { steps: 12 }); await sleep(350);
      const c = await bounded(page.evaluate(SAMPLE_PROBES), "sample-probes");
      const pdx = points[1].x - points[0].x, pdy = points[1].y - points[0].y, plen = Math.hypot(pdx, pdy);
      for (const [id, middle] of Object.entries(b.els)) {
        const start = a.els[id], returned = c.els[id];
        if (!start || !returned || start.hov || middle.hov || returned.hov) continue;
        const dx = middle.left - start.left, dy = middle.top - start.top, moved = Math.hypot(dx, dy);
        const back = Math.hypot(returned.left - start.left, returned.top - start.top);
        const correlation = moved && plen ? (dx * pdx + dy * pdy) / (moved * plen) : -1;
        if (moved > 8 && correlation > 0.45 && back <= Math.max(8, moved * 0.3) && middle.top > -50 && middle.top < viewport.height + 50) {
          pointerFollow = { tag: middle.tag, cls: middle.cls, w: middle.w, h: middle.h, moved_px: Math.round(moved), return_error_px: Math.round(back), depth_fraction: fraction };
          break;
        }
      }
    } catch (error) { if (error?.code === "browser-call-timeout") throw error; }
  }
  if (pointerFollow) derived.mechanisms.push({ type: "pointer-follow", ...pointerFollow, detail: "moved with the pointer and returned with it" });
  const mechanisms = finalizeMechanisms(derived.mechanisms).sort((x, y) => mechanismWeight(y) - mechanismWeight(x));
  return {
    wheel_ticks: ticks.length - 1, scroll_windows_active: derived.activeTicks.size, scroll_windows: derived.scrollTicks,
    scroll_coverage: Number((derived.activeTicks.size / Math.max(1, derived.scrollTicks)).toFixed(2)),
    distinct_mechanisms: new Set(mechanisms.map((m) => m.type)).size, type_instances: derived.typeCounts, mechanisms,
  };
}

async function animationsByDepth(page) {
  const out = [];
  const docHeight = await page.evaluate(() => document.documentElement.scrollHeight);
  for (const f of WAAPI_DEPTHS) {
    await page.evaluate((y) => window.scrollTo(0, y), Math.round((docHeight - 1) * f));
    await sleep(450);
    const snap = await bounded(page.evaluate(ANIMATIONS), "animations");
    out.push({ depth: f, ...snap });
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  return out;
}

export async function hoverProbe(page) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.mouse.move(8, 8);
  await bounded(page.mouse.wheel(0, -20000), "wheel", 15_000).catch(() => {});
  await sleep(600);
  let candidates = await bounded(page.evaluate(HOVER_CANDIDATES), "hover-candidates");
  if (!candidates.length) { await sleep(1200); candidates = await bounded(page.evaluate(HOVER_CANDIDATES), "hover-candidates"); }
  const rows = [];
  for (const c of candidates) {
    try {
      await page.mouse.move(4, 4); await sleep(150);
      const before = await bounded(page.evaluate(HOVER_SNAPSHOT, c.id), "hover-before", 10_000);
      if (!before) continue;
      await page.mouse.move(c.x, c.y, { steps: 6 }); await sleep(450);
      const after = await bounded(page.evaluate(HOVER_SNAPSHOT, c.id), "hover-after", 10_000);
      if (!after) continue;
      const changed = before.rows.filter((row, i) => row !== after.rows[i]).length;
      rows.push({ target: `${c.tag} ${c.text}`.trim(), w: c.w, h: c.h, responded: changed > 0, changed_nodes: changed, transition: after.transition, cursor: after.cursor });
    } catch (error) { if (error?.code === "browser-call-timeout") throw error; rows.push({ target: `${c.tag} ${c.text}`.trim(), responded: null, error: String(error?.message || error).slice(0, 80) }); }
  }
  await page.mouse.move(4, 4);
  return { probed: rows.length, responded: rows.filter((r) => r.responded).length, rows };
}

async function scrollThrough(page, viewport, seconds, frameDir, prefix) {
  // A real-time scroll-through, recorded as video by the context, with eight
  // evenly spaced frames kept for the contact sheet.
  const frames = [];
  const docHeight = await page.evaluate(() => document.documentElement.scrollHeight);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.mouse.move(Math.round(viewport.width / 2), Math.round(viewport.height / 2));
  const started = Date.now();
  const stepMs = 400;
  const totalSteps = Math.max(1, Math.round((seconds * 1000) / stepMs));
  const perStep = Math.max(40, Math.round((docHeight - viewport.height) / Math.max(1, totalSteps - 6)));
  const frameEvery = Math.max(1, Math.floor(totalSteps / CONTACT_FRAMES));
  for (let i = 0; i < totalSteps; i += 1) {
    if (i % frameEvery === 0 && frames.length < CONTACT_FRAMES) {
      const t = ((Date.now() - started) / 1000).toFixed(1);
      const file = `${prefix}-t${String(t).padStart(5, "0")}s.png`;
      const buf = await bounded(page.screenshot(), "frame", 60_000);
      fs.writeFileSync(path.join(frameDir, file), buf);
      frames.push({ file, t_s: Number(t), sha256: sha(buf) });
    }
    await bounded(page.mouse.wheel(0, perStep), "wheel", 15_000);
    await sleep(stepMs);
  }
  return frames;
}

export async function contactSheet(browser, frameDir, frames, outFile, label) {
  if (!frames.length) return null;
  const page = await browser.newPage({ viewport: { width: 1920, height: 100 + Math.ceil(frames.length / 4) * 300 } });
  try {
    const tiles = frames.map((f) => ({ t: f.t_s, data: "data:image/png;base64," + fs.readFileSync(path.join(frameDir, f.file)).toString("base64") }));
    await page.setContent(`<body style="margin:0;background:#111;font:14px system-ui;color:#ddd"><div style="padding:12px 16px">${label}</div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:0 8px 8px">${tiles.map((t) => `<figure style="margin:0"><img src="${t.data}" style="width:100%;display:block;background:#000"><figcaption style="padding:4px 0">t=${t.t}s</figcaption></figure>`).join("")}</div></body>`);
    const buf = await page.screenshot({ fullPage: true });
    fs.writeFileSync(outFile, buf);
    return { file: path.basename(outFile), sha256: sha(buf) };
  } finally { await page.close(); }
}

export async function studyPage(browser, url, viewport, options) {
  const { frameDir, videoDir, prefix, videoSeconds, full } = options;
  const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1,
    recordVideo: videoSeconds ? { dir: videoDir, size: { width: viewport.width, height: viewport.height } } : undefined });
  const page = await context.newPage();
  const record = { url, viewport: viewport.name, ok: false, problems: [] };
  try {
    const response = await bounded(page.goto(url, { waitUntil: "load", timeout: 60_000 }), "navigate", 70_000);
    record.status = response?.status() ?? null;
    record.final_url = page.url();
    await sleep(2500);
    const first = await bounded(page.screenshot(), "first-screen", 60_000);
    record.first_screen = { file: `${prefix}-first-screen.png`, sha256: sha(first) };
    fs.writeFileSync(path.join(frameDir, record.first_screen.file), first);
    record.design = await bounded(page.evaluate(DESIGN_SYSTEM), "design-system");
    record.layout = await bounded(page.evaluate(LAYOUT), "layout");
    if (full) {
      // Hover first, at rest on the first screen: a smooth-scroll library can
      // ignore window.scrollTo after a traversal and leave the page elsewhere.
      record.hover = await hoverProbe(page);
      record.motion = await motionPass(page, viewport);
      record.animations_by_depth = await animationsByDepth(page);
    } else {
      record.motion = await motionPass(page, viewport);
    }
    if (videoSeconds) record.frames = await scrollThrough(page, viewport, videoSeconds, frameDir, prefix);
    record.ok = true;
  } catch (error) {
    record.problems.push({ code: error?.code || "study-page-failed", message: String(error?.message || error).slice(0, 300) });
  } finally {
    const video = page.video();
    await page.close().catch(() => {});
    await context.close().catch(() => {});
    if (video) {
      try {
        const tmp = await video.path();
        const target = path.join(videoDir, `${prefix}.webm`);
        if (fs.existsSync(tmp)) { fs.renameSync(tmp, target); record.video = { file: path.basename(target), bytes: fs.statSync(target).size, seconds: videoSeconds }; }
      } catch (error) { record.problems.push({ code: "video-unavailable", message: String(error?.message || error).slice(0, 200) }); }
    }
  }
  return record;
}

function pickInnerRoutes(navLinks, allLinks, origin, primary, limit) {
  const skip = /privacy|terms|cookie|login|sign-?in|account|cart|checkout|#|mailto:|tel:/i;
  const seen = new Set([primary.replace(/\/$/, "")]);
  const out = [];
  const consider = (href) => {
    if (!href || out.length >= limit) return;
    let abs; try { abs = new URL(href, primary).href; } catch { return; }
    if (!abs.startsWith(origin) || skip.test(abs)) return;
    const key = abs.replace(/\/$/, "").split("#")[0];
    if (seen.has(key)) return;
    seen.add(key); out.push(key);
  };
  for (const link of navLinks) consider(link.href);
  for (const link of allLinks) consider(link);
  return out;
}

/* ------------------------------------------------------------------ sheet */

export function sheet(study) {
  const w = study.pages.find((p) => p.viewport === "wide" && p.role === "primary") || study.pages[0];
  const n = study.pages.find((p) => p.viewport === "narrow" && p.role === "primary");
  const d = w?.design || {};
  const lines = [];
  lines.push(`# Reference sheet: ${study.url}`, "", `Studied ${study.studied_at} by ${TOOL} (schema ${SCHEMA_VERSION}). Every number below was read from the live site; nothing here was typed by hand.`, "");
  lines.push("## Ground and ink (measured by painted area)");
  for (const g of d.grounds || []) lines.push(`- ground ${g.color}: ${(g.area_share * 100).toFixed(1)}% of the painted page across ${g.elements} elements`);
  for (const i of d.inks || []) lines.push(`- text ${i.color} (weight ${i.weight})`);
  lines.push("", "## Typefaces (as computed; the file that serves each is in study.json face_sources)");
  for (const f of d.fonts || []) lines.push(`- ${f.family}: ${f.characters} characters set in it`);
  lines.push("", "## Type scale in use");
  lines.push("| role | family | size | weight | line-height | tracking | transform | sample |", "| --- | --- | --- | --- | --- | --- | --- | --- |");
  for (const t of d.type_scale || []) lines.push(`| ${t.role} | ${t.family} | ${t.size} | ${t.weight} | ${t.line_height} | ${t.letter_spacing} | ${t.transform} | ${(t.sample || "").replace(/\|/g, "/")} |`);
  lines.push("", "## Controls (first screens)");
  for (const c of (d.controls || []).slice(0, 12)) lines.push(`- ${c.tag} "${c.text}": ${c.w}x${c.h}, padding ${c.padding}, radius ${c.radius}, ${c.bg} on ${c.color}, ${c.font}, ${c.transform}`);
  lines.push("", `## Radii, shadows, transitions`, `- radii: ${(d.radii || []).map((r) => r.value).join("; ") || "none"}`, `- shadows: ${(d.shadows || []).map((s) => s.value).join("; ") || "none"}`, `- transitions: ${(d.transitions || []).map((t) => t.value).join("; ") || "none"}`);
  lines.push("", `## Motion source`, `- libraries detected: ${(d.libraries || []).join(", ") || "none detected"}`, `- @keyframes declared: ${(d.keyframes || []).map((k) => k.name).join(", ") || "none readable"}`,
    `- video elements: ${(d.media?.video || []).length} (${(d.media?.video || []).filter((v) => v.autoplay).length} autoplay); canvas: ${(d.media?.canvas || []).length}`);
  for (const p of study.pages.filter((x) => x.role === "primary")) {
    lines.push("", `## What the page does as it scrolls (${p.viewport}, ${p.motion?.wheel_ticks ?? 0} wheel steps, ${Math.round((p.motion?.scroll_coverage || 0) * 100)}% of windows active, ${p.motion?.distinct_mechanisms ?? 0} distinct mechanisms)`);
    const byType = new Map();
    for (const m of p.motion?.mechanisms || []) { const g = byType.get(m.type) || []; g.push(m); byType.set(m.type, g); }
    for (const [type, group] of byType) {
      const examples = group.slice(0, 2).map((m) => `${m.tag || ""}${m.cls ? "." + String(m.cls).split(" ")[0] : ""}`).filter(Boolean).join(", ");
      lines.push(`- ${type} x${group.length}${examples ? ` (${examples})` : ""}: ${group[0].detail || ""}`);
    }
    if (p.animations_by_depth) lines.push(`- Web Animations running by depth: ${p.animations_by_depth.map((a) => `${Math.round(a.depth * 100)}%:${a.count}`).join("  ")}`);
    if (p.hover) lines.push(`- hover: ${p.hover.responded} of ${p.hover.probed} probed controls responded; transitions: ${[...new Set(p.hover.rows.filter((r) => r.responded).map((r) => r.transition))].slice(0, 4).join("; ") || "none"}`);
    if (p.video) lines.push(`- scroll-through video: videos/${p.video.file} (${p.video.seconds}s); contact sheet: ${p.contact_sheet?.file || "n/a"}`);
  }
  lines.push("", "## Layout outline (wide)");
  for (const s of w?.layout?.sections || []) lines.push(`- ${s.tag}${s.class ? "." + s.class.split(" ")[0] : ""} at ${s.top}px, ${s.height}px tall, ground ${s.ground}${s.grid ? ", grid " + s.grid : ""}: ${s.heading ? '"' + s.heading + '"' : ""} ${s.images} images, ${s.videos} videos, ${s.links} links`);
  if (w?.layout?.header) lines.push(`- header: ${w.layout.header.position}, ${w.layout.header.height}px, ground ${w.layout.header.ground}, ${w.layout.header.links} links`);
  if (n?.layout) lines.push("", "## Narrow recomposition", `- ${n.layout.sections.length} sections; header ${n.layout.header ? n.layout.header.position + " " + n.layout.header.height + "px" : "none"}; first screen frames/${n.first_screen?.file}`);
  const inner = study.pages.filter((p) => p.role === "inner");
  if (inner.length) {
    lines.push("", "## Inner pages");
    for (const p of inner) lines.push(`- ${p.url} (${p.viewport}): ${p.layout?.sections?.length ?? 0} sections, ${p.motion?.distinct_mechanisms ?? 0} mechanisms (${(p.motion?.mechanisms || []).slice(0, 5).map((m) => m.type).join(", ")}), ground ${p.design?.grounds?.[0]?.color || "?"}; first screen frames/${p.first_screen?.file}`);
  }
  lines.push("", "## Signature candidates (what a stranger would name first, by measured weight)");
  const cands = [...new Map((w?.motion?.mechanisms || []).map((m) => [m.type, m])).values()].slice(0, 5);
  for (const m of cands) lines.push(`- ${m.type}: ${m.detail || ""}`);
  if (!cands.length) lines.push("- no scroll or pointer mechanism detected; if this site is selected its signature is typographic, photographic or a color relationship, and the sheet frames must show it");
  if (study.problems.length) { lines.push("", "## Problems"); for (const p of study.problems) lines.push(`- ${p.page || ""} ${p.viewport || ""}: ${p.code}: ${p.message}`); }
  return lines.join("\n") + "\n";
}

/* ------------------------------------------------------------------ main */

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const started = Date.now();
  const outDir = path.join(path.resolve(args.outDir), args.id);
  const frameDir = path.join(outDir, "frames"), videoDir = path.join(outDir, "videos");
  fs.mkdirSync(frameDir, { recursive: true }); fs.mkdirSync(videoDir, { recursive: true });
  const loaded = resolvePlaywright({ moduleUrl: import.meta.url });
  const executable = discoverBrowserExecutable(loaded.playwright, args.browserExecutable);
  const browser = await loaded.playwright.chromium.launch({ executablePath: executable.path });
  const study = { schema_version: SCHEMA_VERSION, tool: TOOL, id: args.id, url: args.url, studied_at: new Date().toISOString(), pages: [], problems: [], complete: false };
  try {
    for (const viewport of VIEWPORTS) {
      const record = await studyPage(browser, args.url, viewport, { frameDir, videoDir, prefix: `${viewport.name}-home`, videoSeconds: args.videoSeconds, full: true });
      record.role = "primary";
      if (record.frames?.length) record.contact_sheet = await contactSheet(browser, frameDir, record.frames, path.join(outDir, `${viewport.name}-home-contact-sheet.png`), `${args.url} — ${viewport.name} scroll-through, ${args.videoSeconds}s`);
      for (const p of record.problems) study.problems.push({ page: "home", viewport: viewport.name, ...p });
      study.pages.push(record);
    }
    // Inner routes from the site's own navigation, in the order the site lists them.
    const wideHome = study.pages.find((p) => p.viewport === "wide");
    let inner = [];
    if (args.inner > 0 && wideHome?.ok) {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();
      try {
        await bounded(page.goto(args.url, { waitUntil: "load", timeout: 60_000 }), "navigate", 70_000);
        await sleep(1500);
        const origin = new URL(args.url).origin;
        const links = await bounded(collectSameOriginLinks(page, origin), "links");
        inner = pickInnerRoutes(wideHome.layout?.nav_links || [], links, origin, page.url(), args.inner);
        study.discovered_same_origin_links = links.length;
      } catch (error) { study.problems.push({ page: "inner-discovery", code: error?.code || "inner-discovery-failed", message: String(error?.message || error).slice(0, 200) }); }
      finally { await context.close().catch(() => {}); }
    }
    study.inner_routes = inner;
    for (const [index, url] of inner.entries()) {
      for (const viewport of VIEWPORTS) {
        const prefix = `${viewport.name}-inner${index + 1}`;
        const record = await studyPage(browser, url, viewport, { frameDir, videoDir, prefix, videoSeconds: viewport.name === "wide" ? 10 : 0, full: false });
        record.role = "inner";
        if (record.frames?.length) record.contact_sheet = await contactSheet(browser, frameDir, record.frames, path.join(outDir, `${prefix}-contact-sheet.png`), `${url} — ${viewport.name}`);
        for (const p of record.problems) study.problems.push({ page: url, viewport: viewport.name, ...p });
        study.pages.push(record);
      }
    }
    study.complete = study.pages.filter((p) => p.role === "primary").every((p) => p.ok);
  } finally {
    await Promise.race([browser.close(), sleep(15_000)]).catch(() => {});
  }
  study.elapsed_s = Math.round((Date.now() - started) / 1000);
  study.runtime = { node: process.version, browser: executable.path, tool_sha256: sha(fs.readFileSync(fileURLToPath(import.meta.url))) };
  fs.writeFileSync(path.join(outDir, "study.json"), JSON.stringify(study, null, 2) + "\n");
  fs.writeFileSync(path.join(outDir, "sheet.md"), sheet(study));
  const summary = { ok: study.complete, id: args.id, out: outDir, elapsed_s: study.elapsed_s, pages: study.pages.map((p) => ({ url: p.url, viewport: p.viewport, role: p.role, ok: p.ok,
    mechanisms: p.motion?.distinct_mechanisms ?? null, video: p.video?.file || null, contact_sheet: p.contact_sheet?.file || null })), problems: study.problems };
  process.stdout.write(JSON.stringify(summary, null, 2) + "\n");
  if (!study.complete) process.exitCode = 1;
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url));
if (invokedDirectly) {
  main().catch((error) => {
    process.stdout.write(JSON.stringify({ ok: false, error: { code: error?.code || "study-failed", message: String(error?.message || error).slice(0, 500) } }, null, 2) + "\n");
    process.exitCode = 2;
  }).finally(() => { setTimeout(() => process.exit(process.exitCode ?? 0), 2000).unref(); });
}
