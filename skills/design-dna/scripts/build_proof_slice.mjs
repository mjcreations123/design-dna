#!/usr/bin/env node
/** Deterministically emit one proof-slice HTML artifact from its static JSX source. */

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { resolveBabelParser } from "./babel_parser_resolver.mjs";

const TOOL = "build_proof_slice.mjs";
const SCHEMA = 1;
const SCRIPT = fileURLToPath(import.meta.url);
const SCRIPT_SHA = createHash("sha256").update(fs.readFileSync(SCRIPT)).digest("hex");
const VOID = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"]);

function digest(bytes) { return createHash("sha256").update(bytes).digest("hex"); }
function fail(message) { process.stderr.write(`${message}\n`); process.exit(2); }
function esc(value) { return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }

function parseArgs(argv) {
  const out = { manifest: null, source: null, output: null, record: null };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--manifest") out.manifest = argv[++index];
    else if (arg === "--source") out.source = argv[++index];
    else if (arg === "--output") out.output = argv[++index];
    else if (arg === "--record") out.record = argv[++index];
    else if (arg === "--help") {
      process.stdout.write("build_proof_slice.mjs --manifest proof-slice.json --source proof.tsx --output index.html --record build.json\n");
      process.exit(0);
    } else fail(`unknown argument: ${arg}`);
  }
  if (!out.manifest || !out.source || !out.output || !out.record) fail("--manifest, --source, --output, and --record are required");
  return out;
}

function parser() {
  try { return resolveBabelParser(import.meta.url); }
  catch (error) { fail(error.message); }
}

function staticRoot(ast) {
  const declaration = ast.program.body.find((node) => node.type === "ExportDefaultDeclaration")?.declaration;
  if (!declaration) return null;
  if ((declaration.type === "ArrowFunctionExpression" || declaration.type === "FunctionExpression") && declaration.body?.type === "JSXElement") return declaration.body;
  if ((declaration.type === "ArrowFunctionExpression" || declaration.type === "FunctionExpression" || declaration.type === "FunctionDeclaration") && declaration.body?.type === "BlockStatement") {
    const returnNode = declaration.body.body.find((node) => node.type === "ReturnStatement" && node.argument?.type === "JSXElement");
    return returnNode?.argument || null;
  }
  return null;
}

function tagName(name) {
  if (name?.type !== "JSXIdentifier") fail("proof source contains a non-static JSX tag");
  return name.name;
}

function serialize(node) {
  if (node.type === "JSXText") return node.value.trim() === "Internal unverified proof slice — not for public release" ? "" : esc(node.value);
  if (node.type !== "JSXElement") fail("proof source contains a non-static JSX expression; only the typed static proof root can be built");
  const tag = tagName(node.openingElement.name);
  const attributes = [];
  for (const attribute of node.openingElement.attributes || []) {
    if (attribute.type !== "JSXAttribute" || attribute.name?.type !== "JSXIdentifier") fail("proof source contains a spread/dynamic JSX attribute");
    const name = attribute.name.name;
    if (attribute.value === null) attributes.push(name);
    else if (attribute.value.type === "StringLiteral") attributes.push(`${name}="${esc(attribute.value.value)}"`);
    else fail("proof source contains a dynamic JSX attribute value");
  }
  const opening = `<${tag}${attributes.length ? " " + attributes.join(" ") : ""}>`;
  if (VOID.has(tag.toLowerCase())) return opening;
  return `${opening}${(node.children || []).map(serialize).join("")}</${tag}>`;
}

function attributeValue(opening, wanted) {
  const attribute = (opening.attributes || []).find((item) => item?.type === "JSXAttribute" && item.name?.type === "JSXIdentifier" && item.name.name === wanted);
  return attribute?.value?.type === "StringLiteral" ? attribute.value.value : null;
}

function textContent(node) {
  // The mandatory tool label is an internal disposition, not source copy.
  // Exclude only the exact standalone label node, never a substring of copy.
  if (node.type === "JSXText") return node.value.trim() === "Internal unverified proof slice — not for public release" ? "" : node.value;
  if (node.type !== "JSXElement") return "";
  return (node.children || []).map(textContent).join("");
}

function componentTextRecords(root) {
  const records = [];
  const visit = (node) => {
    if (node?.type !== "JSXElement") return;
    const id = attributeValue(node.openingElement, "data-design-dna-component");
    if (id) records.push({ component_id: id, text_sha256: digest(" ".concat(textContent(node)).replace(/\s+/g, " ").trim()) });
    for (const child of node.children || []) visit(child);
  };
  visit(root);
  return records.sort((a, b) => a.component_id.localeCompare(b.component_id));
}

function css(manifest) {
  const byViewport = new Map([["wide", new Map()], ["narrow", new Map()]]);
  for (const component of manifest.visible_components || []) {
    const id = component?.component_id;
    if (typeof id !== "string") fail("proof manifest has a component without an ID");
    for (const tuple of component?.styles?.tuples || []) {
      if (!byViewport.has(tuple?.viewport) || typeof tuple?.property !== "string" || typeof tuple?.build_value !== "string") continue;
      const props = byViewport.get(tuple.viewport).get(id) || new Map();
      props.set(tuple.property, tuple.build_value);
      byViewport.get(tuple.viewport).set(id, props);
    }
    const media = component?.media;
    if (media?.kind && media.kind !== "none" && (media.crop || media.crop_by_viewport)) {
      for (const viewport of ["wide", "narrow"]) {
        const crop = media.crop_by_viewport?.[viewport] || media.crop;
        const props = byViewport.get(viewport).get(id) || new Map();
        props.set("width", `${crop.width}px`);
        props.set("height", `${crop.height}px`);
        props.set("object-fit", crop.object_fit);
        props.set("object-position", crop.object_position);
        byViewport.get(viewport).set(id, props);
      }
    }
  }
  const emit = (viewport) => [...byViewport.get(viewport).entries()].map(([id, props]) =>
    `[data-design-dna-component="${id}"]{${[...props].map(([key, value]) => `${key}:${value}`).join(";")}}`).join("\n");
  const observationFile = path.resolve(path.dirname(path.dirname(path.resolve(input.manifest))), manifest.source.observation);
  const observation = JSON.parse(fs.readFileSync(observationFile, 'utf8'));
  if (digest(fs.readFileSync(observationFile)) !== manifest.source.sha256) fail('source observation changed before proof build');
  const documentCss = (profile) => ['html', 'body'].map((tag) => {
    const properties = observation.proof_document_styles?.[profile]?.[tag] || {};
    return `${tag}{${Object.entries(properties).map(([key,value]) => `${key}:${value}`).join(';')}}`;
  }).join('\n');
  return `html,body{margin:0;overflow:hidden}\n@media (min-width:900px){${documentCss("wide")}${emit("wide")}}\n@media (max-width:899px){${documentCss("narrow")}${emit("narrow")}}`;
}

const input = parseArgs(process.argv.slice(2));
let manifest, source;
try { manifest = JSON.parse(fs.readFileSync(input.manifest, "utf8")); source = fs.readFileSync(input.source, "utf8"); }
catch (error) { fail(`proof build inputs unreadable: ${String(error).slice(0, 260)}`); }
const sourceSha256 = digest(source);
if (manifest?.implementation?.source_file_sha256 !== sourceSha256) fail("proof source bytes differ from the manifest-bound source_file_sha256");
let ast;
try { ast = parser().parse(source, { sourceType: "module", plugins: ["jsx", "typescript"], errorRecovery: false }); }
catch (error) { fail(`proof source parse failed: ${String(error?.message || error).slice(0, 300)}`); }
const root = staticRoot(ast);
if (!root) fail("proof source must export one static JSX root for the controlled proof builder");
const markup = serialize(root);
const dispositionLabel = '<aside data-design-dna-proof-label="internal-unverified" style="position:fixed;left:4px;bottom:4px;z-index:2147483647;padding:4px;background:#fff;color:#000;font:12px/1.4 monospace;pointer-events:none">Internal unverified proof slice — not for public release</aside>';
const output = `<!doctype html><meta charset="utf-8"><meta name="design-dna-proof-source-file" content="${esc(manifest.implementation.source_file)}"><meta name="design-dna-proof-source-sha256" content="${sourceSha256}"><style>${css(manifest)}</style>${markup}${dispositionLabel}`;
const outputPath = path.resolve(input.output);
fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, output, "utf8");
const outputBytes = fs.readFileSync(outputPath);
const record = {
  tool: TOOL, schema_version: SCHEMA, producer_script_sha256: SCRIPT_SHA,
  runtime_identity: {"babel_parser_resolver.mjs": digest(fs.readFileSync(path.join(path.dirname(SCRIPT), 'babel_parser_resolver.mjs')))},
  parser: { name: "@babel/parser", version: "8.0.4" },
  manifest: { path: path.resolve(input.manifest), sha256: digest(fs.readFileSync(input.manifest)) },
  source: { path: path.resolve(input.source), sha256: sourceSha256 },
  components: componentTextRecords(root),
  output: { path: outputPath, bytes: outputBytes.length, sha256: digest(outputBytes) },
};
fs.mkdirSync(path.dirname(path.resolve(input.record)), { recursive: true });
fs.writeFileSync(path.resolve(input.record), JSON.stringify(record, null, 2) + "\n", { encoding: "utf8", flag: "wx" });
process.stdout.write(JSON.stringify(record) + "\n");
