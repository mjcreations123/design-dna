#!/usr/bin/env node
/** Render one local, internal proof slice at exact wide+narrow viewports. */

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { browserExecutableIdentity, discoverBrowserExecutable, resolvePlaywright } from "./playwright_resolver.mjs";
import { auditRenderedFontDelivery, prepareRenderedFontDelivery } from "./rendered_font_delivery.mjs";

const TOOL = "scan_proof_slice.mjs";
const SCHEMA = 1;
const SCRIPT = fileURLToPath(import.meta.url);
const SCRIPT_SHA = createHash("sha256").update(fs.readFileSync(SCRIPT)).digest("hex");
const LABEL = "Internal unverified proof slice — not for public release";
const VIEWPORTS = [
  { name: "wide", width: 1440, height: 900 },
  { name: "narrow", width: 390, height: 844 },
];

function sha(file) { return createHash("sha256").update(fs.readFileSync(file)).digest("hex"); }
function fail(message) { process.stderr.write(`${message}\n`); process.exit(2); }

function args(argv) {
  const out = { url: null, manifest: null, buildRecord: null, out: null, browser: null };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--url") out.url = argv[++index];
    else if (arg === "--manifest") out.manifest = argv[++index];
    else if (arg === "--build-record") out.buildRecord = argv[++index];
    else if (arg === "--out") out.out = argv[++index];
    else if (arg === "--browser-executable" || arg === "--chrome") out.browser = argv[++index];
    else if (arg === "--help") {
      process.stdout.write("scan_proof_slice.mjs --url http://127.0.0.1:PORT/ --manifest proof-slice.json --build-record build.json --out proof-render.json\n");
      process.exit(0);
    } else fail(`unknown argument: ${arg}`);
  }
  if (!out.url || !out.manifest || !out.buildRecord || !out.out) fail("--url, --manifest, --build-record, and --out are required");
  return out;
}

function localUrl(value) {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" && ["127.0.0.1", "localhost", "[::1]"].includes(parsed.hostname);
  } catch { return false; }
}

function canonicalUrl(value) {
  const parsed = new URL(value);
  parsed.hash = "";
  return parsed.href;
}

function writeRecord(file, record) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(record, null, 2) + "\n", { encoding: "utf8", flag: "wx" });
}

const input = args(process.argv.slice(2));
if (!localUrl(input.url)) fail("proof slice URL must be a local http://127.0.0.1, localhost, or [::1] server");
let manifest;
try { manifest = JSON.parse(fs.readFileSync(input.manifest, "utf8")); }
catch (error) { fail(`proof-slice manifest unreadable: ${String(error).slice(0, 240)}`); }
let buildRecord;
try { buildRecord = JSON.parse(fs.readFileSync(input.buildRecord, "utf8")); }
catch (error) { fail(`proof-slice controlled build record unreadable: ${String(error).slice(0, 240)}`); }
const components = Array.isArray(manifest?.visible_components) ? manifest.visible_components : [];
const sourceObservationFile = path.resolve(path.dirname(path.dirname(path.resolve(input.manifest))), manifest.source?.observation || '');
if (!fs.existsSync(sourceObservationFile) || sha(sourceObservationFile) !== manifest.source?.sha256) fail('proof source observation is missing or changed');
const sourceObservation = JSON.parse(fs.readFileSync(sourceObservationFile, 'utf8'));
const componentIds = components.map((component) => component?.component_id).filter((id) => typeof id === "string");
const controlIds = manifest?.transfer_coverage?.control?.status === "present" && Array.isArray(manifest?.transfer_coverage?.control?.component_ids)
  ? manifest.transfer_coverage.control.component_ids : [];
const sourceFile = manifest?.implementation?.source_file;
const sourceSha256 = manifest?.implementation?.source_file_sha256;
const servedOutput = buildRecord?.output;
if (!componentIds.length || componentIds.length !== new Set(componentIds).size) fail("proof-slice manifest has no unique visible component IDs");
const primaryId = manifest?.implementation?.primary_component_id;
if (!componentIds.includes(primaryId)) fail("proof-slice primary component is not mapped");
if (!sourceFile || !/^[a-f0-9]{64}$/.test(sourceSha256 || "") || !servedOutput || !/^[a-f0-9]{64}$/.test(servedOutput.sha256 || "") || !Number.isInteger(servedOutput.bytes) ||
    buildRecord?.tool !== "build_proof_slice.mjs" || buildRecord?.schema_version !== 1 || buildRecord?.source?.sha256 !== sourceSha256) {
  fail("proof-slice manifest lacks source-file and served-output runtime identity bindings");
}

let resolved, executable, browser;
try {
  resolved = resolvePlaywright({ projectRoot: process.cwd(), moduleUrl: import.meta.url });
  executable = discoverBrowserExecutable(resolved.playwright, input.browser);
  browser = await resolved.playwright.chromium.launch({ headless: true, executablePath: executable.path });
} catch (error) {
  const record = { tool: TOOL, schema_version: SCHEMA, producer_script_sha256: SCRIPT_SHA,
    url: input.url, manifest: path.resolve(input.manifest), pass: false,
    findings: [{ code: "proof-browser-unavailable", message: String(error?.message || error).slice(0, 500) }] };
  writeRecord(path.resolve(input.out), record);
  process.stdout.write(JSON.stringify(record) + "\n");
  process.exit(1);
}

const checks = [];
try {
  for (const viewport of VIEWPORTS) {
    const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
    await prepareRenderedFontDelivery(page);
    await page.addInitScript(() => {
      const captured = [];
      const original = Element.prototype.attachShadow;
      Element.prototype.attachShadow = function patchedAttachShadow(options) {
        const root = original.call(this, options);
        captured.push({ host: this, mode: options?.mode || null });
        return root;
      };
      window.__designDnaProofShadowRoots = captured;
    });
    let response = null;
    try { response = await page.goto(input.url, { waitUntil: "networkidle", timeout: 30000 }); }
    catch (error) { checks.push({ viewport: viewport.name, pass: false, findings: [{ code: "proof-navigation", message: String(error).slice(0, 300) }] }); await page.close(); continue; }
    await page.evaluate(() => document.fonts?.ready).catch(() => {});
    let redirectCount = 0;
    for (let request = response.request().redirectedFrom(); request; request = request.redirectedFrom()) redirectCount += 1;
    const quiet = await page.evaluate(async () => {
      let mutations = 0;
      const observer = new MutationObserver((rows) => { mutations += rows.length; });
      observer.observe(document.documentElement, { subtree: true, childList: true, attributes: true, characterData: true });
      await new Promise((resolve) => setTimeout(resolve, 1200));
      observer.disconnect();
      return mutations;
    });
    const responseBytes = await response.body();
    const report = await page.evaluate(({ ids, primary, label, controlIds, expectedSourceFile, expectedSourceSha }) => {
      const visible = (element) => {
        if (!element) return false;
        const style = getComputedStyle(element), box = element.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity) > 0 && box.width > 1 && box.height > 1;
      };
      const actualIds = [...document.querySelectorAll("[data-design-dna-component]")]
        .map((element) => element.getAttribute("data-design-dna-component")).filter(Boolean).sort();
      const findings = [];
      if (JSON.stringify(actualIds) !== JSON.stringify([...ids].sort())) findings.push({ code: "proof-component-runtime-map", message: "rendered component IDs do not exactly equal the typed proof map" });
      const root = document.querySelector(`[data-design-dna-component="${CSS.escape(primary)}"]`);
      const labels = [...document.querySelectorAll('[data-design-dna-proof-label="internal-unverified"]')];
      if (!visible(root) || root?.getAttribute("data-design-dna-proof-status") !== "internal-unverified" || labels.length !== 1 || !visible(labels[0]) || labels[0].textContent !== label) {
        findings.push({ code: "proof-visible-label", message: "primary proof root lacks a visible internal-unverified status label" });
      }
      const regions = [...document.querySelectorAll("main,section,article")];
      if (regions.length !== 1 || !visible(regions[0])) findings.push({ code: "proof-region-runtime-count", message: `expected exactly one visible main/section/article region and no hidden extra region, found ${regions.length}` });
      const routes = [...document.querySelectorAll("a[href]")].map((element) => element.getAttribute("href"))
        .filter((href) => href && !href.startsWith("#"));
      if (routes.length) findings.push({ code: "proof-route-runtime-link", message: "rendered proof contains a non-fragment route/navigation link" });
      const sourceFileMeta = document.querySelector('meta[name="design-dna-proof-source-file"]')?.getAttribute("content");
      const sourceShaMeta = document.querySelector('meta[name="design-dna-proof-source-sha256"]')?.getAttribute("content");
      if (sourceFileMeta !== expectedSourceFile || sourceShaMeta !== expectedSourceSha) {
        findings.push({ code: "proof-runtime-source-identity", message: "served proof does not expose the exact bound source file/SHA-256 identity" });
      }
      const frames = [...document.querySelectorAll("iframe,object,embed,portal,fencedframe")];
      if (frames.length) findings.push({ code: "proof-frame-surface", message: `proof slice contains ${frames.length} embedded browsing/document surface(s); frames are fail-closed` });
      const shadowHosts = [...document.querySelectorAll("*")].filter((element) => element.shadowRoot || (window.__designDnaProofShadowRoots || []).some((item) => item.host === element));
      if (shadowHosts.length) findings.push({ code: "proof-shadow-surface", message: `proof slice contains ${shadowHosts.length} shadow-root host(s); shadow surfaces are fail-closed` });
      const canvases = [...document.querySelectorAll("canvas")];
      if (canvases.length) findings.push({ code: "proof-canvas-surface", message: `proof slice contains ${canvases.length} canvas surface(s); untyped raster surfaces are fail-closed` });
      if (document.documentElement.scrollHeight > innerHeight + 2) findings.push({ code: "proof-beyond-first-screen", message: "rendered proof exceeds one first-screen viewport" });
      const semantic = new Set(["header", "main", "section", "article", "aside", "nav", "footer", "form", "button", "input", "textarea", "select", "a", "img", "video", "audio", "canvas", "svg", "h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]);
      for (const element of document.querySelectorAll("body *")) {
        if (element === labels[0]) continue;
        const directText = [...element.childNodes].some((node) => node.nodeType === 3 && node.nodeValue.trim());
        const style = getComputedStyle(element);
        const paints = style.backgroundImage !== "none" || style.backgroundColor !== "rgba(0, 0, 0, 0)" ||
          parseFloat(style.borderTopWidth) > 0 || style.boxShadow !== "none";
        if (visible(element) && (semantic.has(element.tagName.toLowerCase()) || directText || paints) && !element.hasAttribute("data-design-dna-component")) {
          findings.push({ code: "proof-unmapped-runtime-visible", message: `visible <${element.tagName.toLowerCase()}> has no typed source component map` });
        }
      }
      const paintedPseudos = [];
      for (const element of document.querySelectorAll("body *")) for (const pseudo of ["::before", "::after"]) {
        const style = getComputedStyle(element, pseudo);
        const content = String(style.content || "");
        const paints = (content !== "none" && content !== "normal") || style.backgroundImage !== "none" ||
          style.backgroundColor !== "rgba(0, 0, 0, 0)" || parseFloat(style.borderTopWidth) > 0 || style.boxShadow !== "none";
        if (paints && style.display !== "none" && Number(style.opacity) > 0) paintedPseudos.push(`${element.tagName.toLowerCase()}${pseudo}`);
      }
      if (paintedPseudos.length) findings.push({ code: "proof-pseudo-surface", message: `proof slice contains painted pseudo surface(s): ${paintedPseudos.join(", ")}` });
      for (const controlId of controlIds || []) {
        const element = document.querySelector(`[data-design-dna-component="${CSS.escape(controlId)}"]`);
        const tag = element?.tagName?.toLowerCase();
        const role = element?.getAttribute?.("role");
        if (!visible(element) || !["button", "a", "input", "select", "textarea"].includes(tag) && !["button", "link", "checkbox", "switch", "tab"].includes(role)) {
          findings.push({ code: "proof-control-runtime-map", message: `mapped control ${controlId} is not a visible semantic control` });
        }
      }
      return { findings, document_height: document.documentElement.scrollHeight, viewport_height: innerHeight };
    }, { ids: componentIds, primary: primaryId, label: LABEL, controlIds, expectedSourceFile: sourceFile, expectedSourceSha: sourceSha256 });
    // Typed tuples stay off the page itself: pass them into a deterministic
    // browser evaluation for exact computed-value/media comparison.
    const componentReports = await page.evaluate(({mapped, profile, sourceComponents}) => mapped.map((component) => {
      const element = document.querySelector(`[data-design-dna-component="${CSS.escape(component.component_id)}"]`);
      const findings = [];
      const visible = (node) => { if (!node) return false; const s = getComputedStyle(node), b = node.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity) > 0 && b.width > 1 && b.height > 1; };
      if (!visible(element)) findings.push('component-not-visible');
      const source = sourceComponents.find((row) => row.profile === profile && row.selector === component.source_selector && row.component_key === component.source_component_key);
      const actualBox = element?.getBoundingClientRect();
      if (!source?.rect || !actualBox) findings.push('source-component-arrangement-missing');
      else for (const property of ['left','top','width','height']) {
        if (!Number.isFinite(source.rect[property]) || Math.abs(actualBox[property] - source.rect[property]) > 2) findings.push(`arrangement:${property}: expected ${source.rect[property]}, got ${actualBox[property]}`);
      }
      const style = element ? getComputedStyle(element) : null;
      for (const tuple of component.styles?.tuples || []) {
        if (tuple.viewport !== profile) continue;
        const actual = style?.getPropertyValue(tuple.property)?.trim();
        if (actual !== tuple.build_value) findings.push(`style:${tuple.property}: expected ${tuple.build_value}, got ${actual || '(missing)'}`);
      }
      const media = component.media || {};
      if (media.kind === 'none') {
        const directChildren = element ? [...element.children] : [];
        const hasMedia = directChildren.some((child) => child.matches?.('img,video,audio,canvas') && !child.hasAttribute('data-design-dna-component')) || (style?.backgroundImage && style.backgroundImage !== 'none');
        if (hasMedia) findings.push('unbound-media-present');
      } else {
        const crop = media.crop_by_viewport?.[profile] || media.crop;
        const selector = media.kind === 'background-image' ? null : media.kind === 'image' ? 'img' : media.kind;
        const medium = selector ? (element?.matches?.(selector) ? element : element?.querySelector(selector)) : element;
        const mediumStyle = medium ? getComputedStyle(medium) : null;
        const box = medium?.getBoundingClientRect?.();
        if (!visible(medium)) findings.push('mapped-media-not-visible');
        else if (mediumStyle.objectFit !== crop?.object_fit || mediumStyle.objectPosition !== crop?.object_position ||
                 Math.round(box.width) !== crop?.width || Math.round(box.height) !== crop?.height) findings.push('media-crop-mismatch');
        if (media.kind === 'image' && (!medium?.complete || medium.naturalWidth < 1)) findings.push('media-image-not-delivered');
        if (media.kind !== 'background-image' && (medium?.currentSrc || medium?.src) !== media.source_url) findings.push('media-source-url-mismatch');
      }
      return { component_id: component.component_id, pass: !findings.length, findings };
    }), {mapped: components, profile: viewport.name, sourceComponents: sourceObservation.proof_component_maps || []});
    report.component_reports = componentReports;
    report.font_delivery = await auditRenderedFontDelivery(page, components.flatMap((component) => {
      const tuple = component.styles?.tuples?.find((item) => item.viewport === viewport.name && item.property === 'font-family');
      return tuple ? [{component_id: component.component_id, selector: `[data-design-dna-component="${component.component_id}"]`, family: tuple.build_value}] : [];
    }));
    const screenshotDirectory = path.resolve(path.dirname(input.out), `${path.basename(input.out, path.extname(input.out))}-frames`);
    fs.mkdirSync(screenshotDirectory, {recursive: true});
    const screenshot = path.join(screenshotDirectory, `proof-${viewport.name}.png`);
    if (fs.existsSync(screenshot)) throw new Error(`Refusing to overwrite immutable proof frame: ${screenshot}`);
    await page.screenshot({ path: screenshot, fullPage: false });
    const status = response?.status?.() ?? null;
    const body = await page.content();
    const responseSha256 = createHash("sha256").update(responseBytes).digest("hex");
    const findings = [
      ...report.findings,
      ...report.font_delivery.findings,
      ...(redirectCount !== 0 || canonicalUrl(page.url()) !== canonicalUrl(input.url) || !localUrl(page.url()) || canonicalUrl(response.url()) !== canonicalUrl(input.url)
        ? [{ code: "proof-navigation-identity", message: "final page/response URL differs from the declared local proof URL or redirects" }] : []),
      ...(quiet > 0 ? [{ code: "proof-postload-mutation", message: `proof DOM mutated ${quiet} time(s) during the required post-load quiet window` }] : []),
      ...(responseBytes.length !== servedOutput.bytes || responseSha256 !== servedOutput.sha256
        ? [{ code: "proof-served-output-identity", message: "served response bytes do not equal the manifest-bound proof output artifact" }] : []),
      ...componentReports.flatMap((item) => item.findings.map((message) => ({ code: "proof-component-runtime", component_id: item.component_id, message }))),
    ];
    checks.push({ viewport: viewport.name, width: viewport.width, height: viewport.height, status,
      requested_url: input.url, final_url: page.url(), response_url: response.url(), redirect_count: redirectCount, quiet_mutations: quiet,
      response_sha256: responseSha256, response_bytes: responseBytes.length,
      screenshot: { path: screenshot, bytes: fs.statSync(screenshot).size, sha256: sha(screenshot) },
      ...report, findings, pass: status >= 200 && status < 300 && !findings.length });
    await page.close();
  }
} finally {
  await browser.close();
}

const record = {
  tool: TOOL, schema_version: SCHEMA, producer_script_sha256: SCRIPT_SHA,
  runtime_identity: { "playwright_resolver.mjs": sha(path.join(path.dirname(SCRIPT), "playwright_resolver.mjs")),
    "rendered_font_delivery.mjs": sha(path.join(path.dirname(SCRIPT), "rendered_font_delivery.mjs")) },
  playwright: resolved.dependency, browser: browserExecutableIdentity(executable),
  url: input.url, manifest: { path: path.resolve(input.manifest), sha256: sha(path.resolve(input.manifest)) },
  viewports: VIEWPORTS, checks, pass: checks.length === VIEWPORTS.length && checks.every((check) => check.pass),
};
writeRecord(path.resolve(input.out), record);
process.stdout.write(JSON.stringify(record) + "\n");
process.exit(record.pass ? 0 : 1);
