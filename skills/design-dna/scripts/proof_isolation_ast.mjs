#!/usr/bin/env node
/** Fail-closed JSX/TSX proof-isolation AST audit using pinned @babel/parser. */

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { resolveBabelParser } from "./babel_parser_resolver.mjs";


function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }) + "\n");
  process.exit(2);
}

function parseArgs(argv) {
  const out = { file: null, otherRoutes: [], plannedRoutes: [], requiredComponents: [], proofLabel: false, strictComponentMaps: false, forbidStaticImports: false, allowBoundNestedRegions: false };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--file") out.file = argv[++index];
    else if (arg === "--other-route") out.otherRoutes.push(argv[++index]);
    else if (arg === "--planned-route") out.plannedRoutes.push(argv[++index]);
    else if (arg === "--required-component") out.requiredComponents.push(argv[++index]);
    else if (arg === "--require-proof-label") out.proofLabel = true;
    else if (arg === "--strict-component-maps") out.strictComponentMaps = true;
    else if (arg === "--forbid-static-imports") out.forbidStaticImports = true;
    else if (arg === "--allow-bound-nested-regions") out.allowBoundNestedRegions = true;
    else if (arg === "--help") {
      process.stdout.write("proof_isolation_ast.mjs --file PROOF.tsx [--other-route /about] [--required-component component-id] [--require-proof-label] [--strict-component-maps] [--forbid-static-imports]\n");
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${arg}`);
  }
  if (!out.file) fail("usage", "--file is required.");
  return out;
}

function loadParser() {
  try { return resolveBabelParser(import.meta.url); }
  catch (error) { fail(error.code || "babel-parser-unavailable", error.message); }
}

function childNodes(value) {
  if (!value || typeof value !== "object") return [];
  if (Array.isArray(value)) return value.filter((item) => item && typeof item.type === "string");
  return Object.entries(value).flatMap(([key, item]) => {
    if (key === "loc" || key === "start" || key === "end" || key === "extra") return [];
    if (item && typeof item === "object" && typeof item.type === "string") return [item];
    if (Array.isArray(item)) return item.filter((entry) => entry && typeof entry.type === "string");
    return [];
  });
}

function walk(node, parent, parents, visit) {
  if (!node || typeof node.type !== "string") return;
  visit(node, parent, parents);
  for (const child of childNodes(node)) walk(child, node, [...parents, node], visit);
}

function memberPropertyName(node) {
  if (!node || node.type !== "MemberExpression") return null;
  if (!node.computed && node.property?.type === "Identifier") return node.property.name;
  if (node.computed && (node.property?.type === "StringLiteral" || node.property?.type === "NumericLiteral")) {
    return String(node.property.value);
  }
  return null;
}

function memberRootName(node) {
  let current = node;
  while (current?.type === "MemberExpression") current = current.object;
  return current?.type === "Identifier" ? current.name : null;
}

function jsxTagName(node) {
  if (!node || node.type !== "JSXElement") return null;
  const name = node.openingElement?.name;
  return name?.type === "JSXIdentifier" ? name.name.toLowerCase() : null;
}

const opts = parseArgs(process.argv.slice(2));
let source;
try { source = fs.readFileSync(path.resolve(opts.file), "utf8"); }
catch (error) { fail("proof-source-unreadable", `${opts.file}: ${String(error).slice(0, 220)}`); }
const parser = loadParser();
let ast;
try {
  ast = parser.parse(source, {
    sourceType: "module",
    plugins: ["jsx", "typescript", "dynamicImport", "importAttributes"],
    errorRecovery: false,
  });
} catch (error) {
  fail("proof-source-parse-failed", `${opts.file}: ${String(error?.message || error).slice(0, 320)}. Fix the proof source; parser failure is a proof-isolation blocker.`);
}

const findings = [];
const regionTags = [];
const jsxRoots = [];
const jsxNodes = [];
const renderedComponentIds = new Set();
const proofLabelRoots = [];
const routeValues = new Set(opts.otherRoutes.filter(Boolean));
const plannedRouteValues = new Set(opts.plannedRoutes.filter(Boolean));
const domMutationProperties = new Set([
  "innerHTML", "outerHTML", "insertAdjacentHTML", "write", "writeln",
  "append", "appendChild", "prepend", "replaceChild", "replaceWith",
  "insertBefore", "before", "after", "appendTo",
]);
const dynamicCodeIdentifiers = new Set(["eval", "Function", "atob"]);
walk(ast, null, [], (node, parent, parents) => {
  if (node.type === "ImportExpression" || (node.type === "CallExpression" && node.callee?.type === "Import")) {
    findings.push({ code: "dynamic-import", message: "dynamic import can defer later route/UI code" });
  }
  if (node.type === "CallExpression" && (
    (node.callee?.type === "MemberExpression" && node.callee.object?.name === "React" && node.callee.property?.name === "lazy") ||
    (node.callee?.type === "Identifier" && ["lazy", "dynamic"].includes(node.callee.name))
  )) findings.push({ code: "lazy-component", message: "lazy/dynamic component can hide later UI" });
  if (node.type === "StringLiteral" && routeValues.has(node.value) &&
      !(parent?.type === "JSXAttribute" && parent.name?.name === "href" && plannedRouteValues.has(node.value))) {
    findings.push({ code: "other-route-literal", message: `prewrites another manifested route: ${node.value}` });
  }
  if (node.type === "JSXOpeningElement" && node.name?.type === "JSXIdentifier") {
    const tag = node.name.name.toLowerCase();
    if (["main", "section", "article"].includes(tag)) regionTags.push(tag);
    const attributes = new Map((node.attributes || [])
      .filter((attribute) => attribute?.type === "JSXAttribute" && attribute.name?.type === "JSXIdentifier")
      .map((attribute) => [attribute.name.name, attribute.value?.type === "StringLiteral" ? attribute.value.value : null]));
    const componentId = attributes.get("data-design-dna-component");
    if (typeof componentId === "string" && componentId) renderedComponentIds.add(componentId);
    const proofStatus = attributes.get("data-design-dna-proof-status");
    if (proofStatus === "internal-unverified" && parent?.type === "JSXElement") proofLabelRoots.push(parent);
    if (opts.strictComponentMaps && !componentId && proofStatus !== "internal-unverified") {
      findings.push({ code: "proof-unmapped-visible-jsx", message: `mounted <${tag}> has no data-design-dna-component source map` });
    }
    if (attributes.has("href") && (typeof attributes.get("href") !== "string" ||
        !attributes.get("href").startsWith("#") && !plannedRouteValues.has(attributes.get("href")))) {
      findings.push({ code: "proof-route-link", message: "a proof slice cannot prewrite a second route or outward navigation" });
    }
  }
  if (node.type === "JSXAttribute" && node.name?.name === "dangerouslySetInnerHTML") {
    findings.push({ code: "dangerous-html", message: "dangerouslySetInnerHTML can conceal unreviewed future markup" });
  }
  if ((opts.strictComponentMaps || opts.forbidStaticImports) && node.type === "ImportDeclaration") {
    findings.push({ code: "proof-static-import", message: "the isolated proof may not import a second component, stylesheet, or route before full construction authorization" });
  }
  if (opts.forbidStaticImports && node.type === "CallExpression" && node.callee?.type === "Identifier" && node.callee.name === "require") {
    findings.push({ code: "proof-static-require", message: "the isolated proof may not require a prewritten module before full construction authorization" });
  }
  if (node.type === "CallExpression" && (
    (node.callee?.type === "MemberExpression" && node.callee.object?.name === "React" && node.callee.property?.name === "createElement") ||
    (node.callee?.type === "Identifier" && ["createElement", "h", "hyperscript"].includes(node.callee.name))
  )) findings.push({ code: "non-jsx-element-factory", message: "element factory/hyperscript can conceal unmounted proof UI" });
  if (node.type === "CallExpression" && node.callee?.type === "MemberExpression") {
    const property = memberPropertyName(node.callee);
    const root = memberRootName(node.callee);
    if (property && domMutationProperties.has(property)) {
      findings.push({ code: "dom-html-mutation", message: `DOM mutation sink ${property} can conceal deferred or dormant UI` });
    } else if (node.callee.computed && ["document", "window", "globalThis"].includes(root)) {
      findings.push({ code: "dynamic-global-dom-access", message: "computed global DOM access can conceal a deferred mutation sink" });
    }
  }
  if (node.type === "AssignmentExpression" && node.left?.type === "MemberExpression") {
    const property = memberPropertyName(node.left);
    const root = memberRootName(node.left);
    if (property && domMutationProperties.has(property)) {
      findings.push({ code: "dom-html-mutation", message: `DOM mutation sink ${property} can conceal deferred or dormant UI` });
    } else if (node.left.computed && ["document", "window", "globalThis"].includes(root)) {
      findings.push({ code: "dynamic-global-dom-access", message: "computed global DOM access can conceal a deferred mutation sink" });
    }
  }
  if (node.type === "CallExpression" && node.callee?.type === "Identifier" && dynamicCodeIdentifiers.has(node.callee.name)) {
    findings.push({ code: "dynamic-code-or-decoder", message: `${node.callee.name} can construct unreviewed future UI` });
  }
  if (node.type === "NewExpression" && node.callee?.type === "Identifier" && node.callee.name === "Function") {
    findings.push({ code: "dynamic-code-or-decoder", message: "Function can construct unreviewed future UI" });
  }
  if (node.type === "NewExpression" && node.callee?.type === "MemberExpression" &&
      (memberPropertyName(node.callee) === "Function" ||
       (node.callee.computed && ["window", "globalThis"].includes(memberRootName(node.callee))))) {
    findings.push({ code: "dynamic-code-or-decoder", message: "computed global constructor can construct unreviewed future UI" });
  }
  if (node.type === "CallExpression" && node.callee?.type === "MemberExpression" &&
      node.callee.object?.name === "ReactDOM" && node.callee.property?.name === "createPortal") {
    findings.push({ code: "portal-ui", message: "ReactDOM.createPortal can render UI outside the declared proof region" });
  }
  if (node.type === "TemplateLiteral" && node.quasis?.some((quasi) => /<\s*[A-Za-z]/.test(quasi.value?.raw || ""))) {
    findings.push({ code: "template-markup", message: "template markup can conceal unparsed future UI" });
  }
  if (node.type === "JSXElement" || node.type === "JSXFragment") {
    jsxNodes.push({ node, parents });
    const nested = parents.some((ancestor) => ancestor.type === "JSXElement" || ancestor.type === "JSXFragment");
    if (!nested) jsxRoots.push(node);
    if (parents.some((ancestor) => ["LogicalExpression", "ConditionalExpression", "CallExpression", "ArrayExpression", "AwaitExpression", "YieldExpression"].includes(ancestor.type))) {
      findings.push({ code: "conditional-jsx", message: "JSX inside an expression can conceal inactive/deferred future UI" });
    }
  }
});
if (regionTags.length !== 1 && !(opts.allowBoundNestedRegions && opts.strictComponentMaps && opts.requiredComponents.length && !opts.proofLabel)) findings.push({ code: "proof-region-count", message: `proof source must declare exactly one main/section/article region, found ${regionTags.length}` });
if (jsxRoots.length !== 1) findings.push({ code: "proof-jsx-root-count", message: `proof source must have exactly one mounted JSX root; found ${jsxRoots.length}` });
if (jsxRoots.length === 1 && !["main", "section", "article"].includes(jsxTagName(jsxRoots[0]))) {
  findings.push({ code: "proof-root-not-region", message: "the sole mounted JSX root must itself be the declared main/section/article proof region" });
}
if (jsxNodes.length && jsxRoots.length !== 1) {
  findings.push({ code: "unmounted-or-extra-jsx", message: "every JSX surface must descend from the one declared proof-region root; extra component declarations are not permitted before first-screen authorization" });
}
const requiredComponents = new Set(opts.requiredComponents.filter(Boolean));
if (opts.requiredComponents.length !== requiredComponents.size) {
  findings.push({ code: "duplicate-required-component", message: "required proof component IDs must be unique" });
}
if (requiredComponents.size && (renderedComponentIds.size !== requiredComponents.size ||
    [...requiredComponents].some((componentId) => !renderedComponentIds.has(componentId)))) {
  findings.push({ code: "proof-component-map-mismatch", message: "mounted data-design-dna-component IDs do not exactly equal the proof-slice component map" });
}
const proofLabelPresent = jsxRoots.length === 1 && proofLabelRoots.includes(jsxRoots[0]);
if (opts.proofLabel && !proofLabelPresent) {
  findings.push({ code: "proof-label-missing", message: "the sole mounted proof region root must carry data-design-dna-proof-status=internal-unverified" });
}
const unique = [...new Map(findings.map((item) => [item.code + "|" + item.message, item])).values()];
process.stdout.write(JSON.stringify({ ok: unique.length === 0, findings: unique, regions: regionTags,
  rendered_component_ids: [...renderedComponentIds].sort(), proof_label_present: proofLabelPresent }, null, 2) + "\n");
process.exit(unique.length ? 1 : 0);
