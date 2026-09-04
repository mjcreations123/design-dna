#!/usr/bin/env node

import { createHash, randomBytes } from "node:crypto";
import {
  lstat,
  mkdir,
  open,
  readFile,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { browserExecutableIdentity, discoverBrowserExecutable as discoverSharedBrowser, resolvePlaywright } from "./playwright_resolver.mjs";

const TOOL_NAME = "design-dna-render-comparison";
const TOOL_VERSION = "2.0.0";
const SCHEMA_VERSION = 2;
const REPORT_NAME = "render-comparison.json";
const CONTACT_SHEET_NAME = "comparison.html";
const MARKER_NAME = ".design-dna-render-comparison.json";
const TRANSACTION_MARKER = ".design-dna-render-comparison.transaction.json";
const SCRIPT_PATH = fileURLToPath(import.meta.url);
const PRODUCER_SCRIPT_SHA256 = createHash("sha256").update(await readFile(SCRIPT_PATH)).digest("hex");
const PLAYWRIGHT_RESOLVER_SHA256 = createHash("sha256").update(
  await readFile(path.join(path.dirname(SCRIPT_PATH), "playwright_resolver.mjs")),
).digest("hex");
const SKILL_ROOT = path.resolve(path.dirname(SCRIPT_PATH), "..");
const PACKAGE_ROOT = path.resolve(path.dirname(SCRIPT_PATH), "../../..");
const RENDER_SCHEMA_PATH = path.join(
  SKILL_ROOT,
  "schemas",
  "render-review.schema.json",
);
const MAX_REPORT_BYTES = 8 * 1024 * 1024;
const MAX_MARKER_BYTES = 16 * 1024;
const MAX_SCREENSHOT_BYTES = 24 * 1024 * 1024;
const MAX_SCREENSHOT_PIXELS = 40 * 1000 * 1000;
const MAX_INPUT_ARTIFACT_BYTES = 150 * 1024 * 1024;
const MAX_DIFF_BYTES = 64 * 1024 * 1024;
const MAX_CAPTURE_COUNT = 72;
const MAX_OUTPUT_BYTES = 512 * 1024 * 1024;
const BASELINE_STALE_DAYS = 30;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const ID_PATTERN = /^[a-z][a-z0-9-]{0,47}$/u;
const CAPTURE_ID_PATTERN =
  /^[a-z][a-z0-9-]{0,47}-[a-z][a-z0-9-]{0,47}$/u;
const COMPARISON_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u;
const TYPOGRAPHY_ROLES = [
  "heading",
  "navigation",
  "control",
  "label",
  "caption",
  "code",
  "list-or-definition",
  "body",
  "other",
];
const TYPOGRAPHY_SAMPLING_STRATEGY =
  "semantic-role-and-document-position-stratified-v1";
const MAX_TYPOGRAPHY_SAMPLES = 120;
const PNG_SIGNATURE = Buffer.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
]);

class ComparisonError extends Error {
  constructor(code, message, details = {}, exitCode = 2) {
    super(message);
    this.name = "ComparisonError";
    this.code = code;
    this.details = details;
    this.exitCode = exitCode;
  }
}

function helpText() {
  return `Design DNA rendered comparison ${TOOL_VERSION}

Runtime:
  Node.js 20 or newer

Usage:
  node compare_render_reviews.mjs BASELINE_REPORT CANDIDATE_REPORT \\
    --output DIR --comparison-id ID --masks none [options]

Inputs:
  BASELINE_REPORT and CANDIDATE_REPORT must be original, local, schema-v3
  render-review.json files with valid path-bound ownership markers. Remote
  render targets, URLs, incomplete captures, symlinks, and path escapes are
  refused.

Options:
  --output DIR                 Required new output directory; never replaced
  --comparison-id ID          Required operator-selected comparison identifier
  --masks none                Required; region masks are not supported
  --browser-executable FILE    Explicit Chrome/Edge/Chromium executable
  --help                       Show this help without loading Playwright

Output:
  ${REPORT_NAME}, ${CONTACT_SHEET_NAME}, a path-bound marker, and one
  baseline/actual/diff PNG triplet per compatible capture. Exact RGBA mismatch
  counts are diagnostic only. Every successful result remains
  human-accept-reject-required; this tool never approves a visual change,
  updates a baseline, applies a threshold, or accesses the network.`;
}

function takeValue(argv, index, option) {
  const value = argv[index + 1];
  if (value === undefined || value.startsWith("--")) {
    throw new ComparisonError(
      "missing-argument-value",
      `${option} requires a value.`,
      { argument: option },
    );
  }
  return value;
}

function parseArgs(argv) {
  const options = {
    baseline: null,
    candidate: null,
    output: null,
    comparisonId: null,
    masks: null,
    browserExecutable: process.env.DESIGN_DNA_BROWSER_EXECUTABLE || process.env.CHROME || null,
    help: false,
  };
  const seen = new Set();
  const positionals = [];
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--help" || argument === "-h") {
      options.help = true;
    } else if (
      ["--output", "--comparison-id", "--masks", "--browser-executable"].includes(
        argument,
      )
    ) {
      if (seen.has(argument)) {
        throw new ComparisonError(
          "duplicate-argument",
          `${argument} may be supplied only once.`,
          { argument },
        );
      }
      seen.add(argument);
      const value = takeValue(argv, index, argument);
      index += 1;
      if (argument === "--output") options.output = value;
      if (argument === "--comparison-id") options.comparisonId = value;
      if (argument === "--masks") options.masks = value;
      if (argument === "--browser-executable") {
        options.browserExecutable = value;
      }
    } else if (argument.startsWith("--")) {
      throw new ComparisonError(
        "unknown-argument",
        `Unknown option: ${argument}`,
        { argument },
      );
    } else {
      positionals.push(argument);
    }
  }
  if (options.help) return options;
  if (positionals.length !== 2) {
    throw new ComparisonError(
      "invalid-input-count",
      "Exactly two local render-review.json paths are required.",
      { received: positionals.length },
    );
  }
  [options.baseline, options.candidate] = positionals;
  if (!options.output || !options.comparisonId || options.masks === null) {
    throw new ComparisonError(
      "missing-required-argument",
      "--output, --comparison-id, and the explicit --masks none declaration are required.",
      {},
    );
  }
  if (!COMPARISON_ID_PATTERN.test(options.comparisonId)) {
    throw new ComparisonError(
      "invalid-comparison-id",
      "--comparison-id must use 1-128 letters, digits, dots, underscores, or hyphens and begin with a letter or digit.",
      {},
    );
  }
  if (options.masks !== "none") {
    throw new ComparisonError(
      "masks-unsupported",
      "Region masks are unsupported. Declare their explicit absence with --masks none.",
      {},
    );
  }
  return options;
}

function isPlainObject(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.getPrototypeOf(value) === Object.prototype
  );
}

function hasExactKeys(value, keys) {
  if (!isPlainObject(value)) return false;
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return (
    actual.length === expected.length &&
    actual.every((key, index) => key === expected[index])
  );
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (!isPlainObject(value)) return value;
  return Object.fromEntries(
    Object.keys(value)
      .sort()
      .map((key) => [key, canonicalize(value[key])]),
  );
}

function canonicalJson(value) {
  return JSON.stringify(canonicalize(value));
}

function deepEqual(left, right) {
  return canonicalJson(left) === canonicalJson(right);
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function sha256Json(value) {
  return sha256(canonicalJson(value));
}

function jsonPayload(value) {
  return `${JSON.stringify(value, null, 2)}\n`;
}

function normalizePathForComparison(value) {
  const normalized = path.normalize(path.resolve(value));
  return process.platform === "win32" ? normalized.toLowerCase() : normalized;
}

function isSamePath(left, right) {
  return normalizePathForComparison(left) === normalizePathForComparison(right);
}

function isWithin(parent, child) {
  const relative = path.relative(path.resolve(parent), path.resolve(child));
  return (
    relative === "" ||
    (!relative.startsWith(`..${path.sep}`) &&
      relative !== ".." &&
      !path.isAbsolute(relative))
  );
}

function looksLikeUri(value) {
  return (
    /^[A-Za-z][A-Za-z0-9+.-]*:\/\//u.test(value) ||
    /^(?:file|data|javascript):/iu.test(value)
  );
}

function assertSafeFilesystemArgument(value) {
  if (
    typeof value !== "string" ||
    value.length < 1 ||
    /[\u0000-\u001f\u007f]/u.test(value)
  ) {
    throw new ComparisonError(
      "unsafe-path",
      "A filesystem argument contains unsupported characters.",
      {},
    );
  }
  if (
    value.startsWith("\\\\") ||
    value.startsWith("//") ||
    path.resolve(value).startsWith("\\\\")
  ) {
    throw new ComparisonError(
      "remote-filesystem-unsupported",
      "Network filesystem paths are unsupported for comparison evidence.",
      {},
    );
  }
  if (process.platform !== "win32") return;
  const absolute = path.resolve(value);
  const relative = path.relative(path.parse(absolute).root, absolute);
  const windowsReserved =
    /^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:[.]|$)/iu;
  if (
    relative.includes(":") ||
    relative
      .split(path.sep)
      .filter(Boolean)
      .some(
        (part) =>
          part.endsWith(".") ||
          part.endsWith(" ") ||
          windowsReserved.test(part),
      )
  ) {
    throw new ComparisonError(
      "unsafe-path",
      "Windows alternate-data-stream and reserved path forms are unsupported.",
      {},
    );
  }
}

async function assertNoSymlinkComponents(target, includeLeaf = true) {
  const absolute = path.resolve(target);
  const parsed = path.parse(absolute);
  const segments = path
    .relative(parsed.root, absolute)
    .split(path.sep)
    .filter(Boolean);
  let current = parsed.root;
  for (let index = 0; index < segments.length; index += 1) {
    current = path.join(current, segments[index]);
    if (!includeLeaf && index === segments.length - 1) break;
    const info = await lstat(current).catch((error) => {
      if (error?.code === "ENOENT") return null;
      throw error;
    });
    if (!info) break;
    if (info.isSymbolicLink()) {
      throw new ComparisonError(
        "symlink-path-unsupported",
        "Input and output paths may not contain symbolic links or junction-like symbolic entries.",
        {},
      );
    }
  }
}

async function readBoundedRegularFile(
  filePath,
  maximum,
  missingCode,
  sizeCode,
) {
  await assertNoSymlinkComponents(filePath);
  const info = await lstat(filePath).catch(() => null);
  if (!info?.isFile() || info.isSymbolicLink()) {
    throw new ComparisonError(
      missingCode,
      "A required local regular file is missing.",
      {},
    );
  }
  if (info.size < 1 || info.size > maximum) {
    throw new ComparisonError(
      sizeCode,
      "A required file is outside the supported byte limit.",
      { maximum_bytes: maximum },
    );
  }
  let handle = null;
  try {
    handle = await open(filePath, "r");
    const before = await handle.stat();
    if (!before.isFile() || before.size !== info.size || before.size > maximum) {
      throw new ComparisonError(
        "input-file-changed",
        "An input file changed while it was being validated.",
        {},
      );
    }
    const bytes = await handle.readFile();
    const after = await handle.stat();
    if (
      bytes.length !== before.size ||
      after.size !== before.size ||
      after.mtimeMs !== before.mtimeMs ||
      (before.ino && after.ino && before.ino !== after.ino) ||
      (before.dev && after.dev && before.dev !== after.dev)
    ) {
      throw new ComparisonError(
        "input-file-changed",
        "An input file changed while it was being validated.",
        {},
      );
    }
    await assertNoSymlinkComponents(filePath);
    return bytes;
  } finally {
    if (handle) await handle.close().catch(() => undefined);
  }
}

function parseJson(bytes, code, message) {
  try {
    const value = JSON.parse(bytes.toString("utf8"));
    if (!isPlainObject(value)) throw new Error("root is not an object");
    return value;
  } catch {
    throw new ComparisonError(code, message, {});
  }
}

function assertPortablePath(value) {
  if (
    typeof value !== "string" ||
    value.length < 1 ||
    value.length > 512 ||
    value.endsWith("/") ||
    value.includes("\\") ||
    value.includes("//") ||
    value.includes(":") ||
    /^(?:\/|[A-Za-z]:)/u.test(value) ||
    /[\u0000-\u001f\u007f]/u.test(value)
  ) {
    throw new ComparisonError(
      "screenshot-path-escape",
      "A screenshot path is not a safe portable relative path.",
      {},
    );
  }
  const parts = value.split("/");
  const windowsReserved =
    /^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:[.]|$)/iu;
  if (
    parts.some(
      (part) =>
        part === "" ||
        part === "." ||
        part === ".." ||
        part.endsWith(".") ||
        part.endsWith(" ") ||
        windowsReserved.test(part),
    )
  ) {
    throw new ComparisonError(
      "screenshot-path-escape",
      "A screenshot path escapes its evidence root.",
      {},
    );
  }
  return value;
}

function assertFiniteDate(value, code) {
  const milliseconds = Date.parse(value ?? "");
  if (!Number.isFinite(milliseconds)) {
    throw new ComparisonError(code, "A required timestamp is invalid.", {});
  }
  return milliseconds;
}

function assertLoopbackUrl(value) {
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    throw new ComparisonError(
      "render-report-invalid",
      "A local render report contains an invalid capture URL.",
      {},
    );
  }
  if (
    parsed.protocol !== "http:" ||
    !["127.0.0.1", "localhost", "[::1]"].includes(parsed.hostname)
  ) {
    throw new ComparisonError(
      "remote-report-unsupported",
      "Only frozen local render reports are accepted; remote capture metadata is refused.",
      {},
    );
  }
}

function validateViewport(value) {
  if (
    !hasExactKeys(value, ["width", "height", "device_scale_factor"]) ||
    !Number.isSafeInteger(value.width) ||
    value.width < 240 ||
    value.width > 3840 ||
    !Number.isSafeInteger(value.height) ||
    value.height < 240 ||
    value.height > 2160 ||
    typeof value.device_scale_factor !== "number" ||
    !Number.isFinite(value.device_scale_factor) ||
    value.device_scale_factor < 1 ||
    value.device_scale_factor > 3
  ) {
    throw new ComparisonError(
      "render-report-invalid",
      "A capture viewport does not match the render-review v3 contract.",
      {},
    );
  }
}

function validateProfile(profile) {
  if (
    !hasExactKeys(profile, [
      "id",
      "label",
      "viewport",
      "is_mobile",
      "has_touch",
      "input_modalities",
      "pointer",
      "hover",
      "color_scheme",
      "reduced_motion",
      "forced_colors",
      "text_spacing",
      "zoom",
    ]) ||
    !ID_PATTERN.test(profile.id ?? "") ||
    typeof profile.label !== "string"
  ) {
    throw new ComparisonError(
      "render-report-invalid",
      "A capture profile does not match the render-review v3 contract.",
      {},
    );
  }
  validateViewport(profile.viewport);
}

function validateScenario(scenario, profiles, routes) {
  if (
    !hasExactKeys(scenario, [
      "id",
      "label",
      "route_id",
      "route_label",
      "state_label",
      "profile_ids",
      "interactions",
    ]) ||
    !ID_PATTERN.test(scenario.id ?? "") ||
    typeof scenario.label !== "string" ||
    typeof scenario.route_label !== "string" ||
    typeof scenario.state_label !== "string" ||
    !Array.isArray(scenario.profile_ids) ||
    scenario.profile_ids.length < 1 ||
    scenario.profile_ids.length > 12 ||
    !Array.isArray(scenario.interactions) ||
    scenario.interactions.length > 12 ||
    !routes.has(scenario.route_id)
  ) {
    throw new ComparisonError(
      "render-report-invalid",
      "A capture scenario does not match the render-review v3 contract.",
      {},
    );
  }
  const unique = new Set(scenario.profile_ids);
  if (
    unique.size !== scenario.profile_ids.length ||
    scenario.profile_ids.some((id) => !profiles.has(id))
  ) {
    throw new ComparisonError(
      "render-report-invalid",
      "A capture scenario references an unknown or duplicate profile.",
      {},
    );
  }
}

function validateScreenshotContract(screenshot) {
  if (
    !hasExactKeys(screenshot, [
      "path",
      "sha256",
      "media_type",
      "bytes",
      "pixel_width",
      "pixel_height",
    ]) ||
    !SHA256_PATTERN.test(screenshot.sha256 ?? "") ||
    screenshot.media_type !== "image/png" ||
    !Number.isSafeInteger(screenshot.bytes) ||
    screenshot.bytes < 1 ||
    screenshot.bytes > MAX_SCREENSHOT_BYTES ||
    !Number.isSafeInteger(screenshot.pixel_width) ||
    screenshot.pixel_width < 1 ||
    screenshot.pixel_width > 32768 ||
    !Number.isSafeInteger(screenshot.pixel_height) ||
    screenshot.pixel_height < 1 ||
    screenshot.pixel_height > 262144 ||
    screenshot.pixel_width * screenshot.pixel_height > MAX_SCREENSHOT_PIXELS
  ) {
    throw new ComparisonError(
      "render-report-invalid",
      "A screenshot does not match the bounded PNG contract.",
      {},
    );
  }
  assertPortablePath(screenshot.path);
}

function validateTypographySampling(documentEvidence) {
  const samples = documentEvidence?.typography_samples;
  const sampling = documentEvidence?.typography_sampling;
  if (
    !isPlainObject(documentEvidence) ||
    !Array.isArray(samples) ||
    samples.length > MAX_TYPOGRAPHY_SAMPLES ||
    !hasExactKeys(sampling, [
      "strategy",
      "candidate_count",
      "sampled_count",
      "truncated",
      "role_counts",
    ]) ||
    sampling.strategy !== TYPOGRAPHY_SAMPLING_STRATEGY ||
    !Number.isSafeInteger(sampling.candidate_count) ||
    sampling.candidate_count < 0 ||
    !Number.isSafeInteger(sampling.sampled_count) ||
    sampling.sampled_count < 0 ||
    sampling.sampled_count > MAX_TYPOGRAPHY_SAMPLES ||
    sampling.sampled_count !== samples.length ||
    sampling.candidate_count < sampling.sampled_count ||
    sampling.truncated !== (sampling.candidate_count > sampling.sampled_count) ||
    !hasExactKeys(sampling.role_counts, TYPOGRAPHY_ROLES)
  ) {
    throw new ComparisonError(
      "render-report-invalid",
      "Typography sampling evidence is missing, inconsistent, or unbounded.",
      {},
    );
  }

  const observedSamples = new Map(TYPOGRAPHY_ROLES.map((role) => [role, 0]));
  for (const sample of samples) {
    if (!isPlainObject(sample) || !observedSamples.has(sample.role)) {
      throw new ComparisonError(
        "render-report-invalid",
        "A typography sample has an unsupported semantic role.",
        {},
      );
    }
    observedSamples.set(sample.role, observedSamples.get(sample.role) + 1);
  }

  let candidateTotal = 0;
  let sampledTotal = 0;
  for (const role of TYPOGRAPHY_ROLES) {
    const counts = sampling.role_counts[role];
    if (
      !hasExactKeys(counts, ["candidate_count", "sampled_count"]) ||
      !Number.isSafeInteger(counts.candidate_count) ||
      counts.candidate_count < 0 ||
      !Number.isSafeInteger(counts.sampled_count) ||
      counts.sampled_count < 0 ||
      counts.sampled_count > counts.candidate_count ||
      counts.sampled_count !== observedSamples.get(role)
    ) {
      throw new ComparisonError(
        "render-report-invalid",
        "Per-role typography sampling counts are inconsistent.",
        {},
      );
    }
    candidateTotal += counts.candidate_count;
    sampledTotal += counts.sampled_count;
  }
  if (
    candidateTotal !== sampling.candidate_count ||
    sampledTotal !== sampling.sampled_count
  ) {
    throw new ComparisonError(
      "render-report-invalid",
      "Typography sampling totals do not match the per-role evidence.",
      {},
    );
  }
}

function validateRenderReport(report) {
  const topLevel = [
    "schema_version",
    "tool",
    "output_identity",
    "execution_ok",
    "review_required",
    "automatic_visual_quality_pass",
    "quality_status",
    "execution",
    "privacy",
    "build",
    "source_snapshot",
    "capture_contract",
    "routes",
    "captures",
    "artifacts",
    "manual_review",
  ];
  if (
    !hasExactKeys(report, topLevel) ||
    report.schema_version !== 3 ||
    !hasExactKeys(report.tool, ["name", "version", "report_schema"]) ||
    report.tool.name !== "design-dna-rendered-review" ||
    report.tool.version !== "3.0.0" ||
    report.tool.report_schema !== "render-review.schema.json" ||
    !hasExactKeys(report.output_identity, ["id", "path_sha256"]) ||
    !SHA256_PATTERN.test(report.output_identity.id ?? "") ||
    !SHA256_PATTERN.test(report.output_identity.path_sha256 ?? "") ||
    report.execution_ok !== true ||
    report.review_required !== true ||
    report.automatic_visual_quality_pass !== false ||
    report.quality_status !== "manual-review-required"
  ) {
    throw new ComparisonError(
      "render-report-invalid",
      "The input is not a complete schema-v3 Design DNA render report.",
      {},
    );
  }
  if (
    !hasExactKeys(report.build, ["id", "target_input", "target_kind"]) ||
    typeof report.build.id !== "string" ||
    report.build.id.length < 1 ||
    report.build.id.length > 256 ||
    !["local-file", "local-directory"].includes(report.build.target_kind)
  ) {
    if (report.build?.target_kind === "remote-url") {
      throw new ComparisonError(
        "remote-report-unsupported",
        "Remote render reports are refused; compare frozen local evidence only.",
        {},
      );
    }
    throw new ComparisonError(
      "render-report-invalid",
      "The report build identity is invalid.",
      {},
    );
  }
  if (
    !isPlainObject(report.source_snapshot) ||
    report.source_snapshot.drift_check !==
      "passed-source-and-frozen-snapshot-before-report-and-commit" ||
    !isPlainObject(report.source_snapshot.manifest) ||
    !SHA256_PATTERN.test(
      report.source_snapshot.manifest.manifest_sha256 ?? "",
    )
  ) {
    throw new ComparisonError(
      "render-report-invalid",
      "The report lacks a verified frozen local source identity.",
      {},
    );
  }
  if (
    !isPlainObject(report.execution) ||
    !isPlainObject(report.execution.browser) ||
    typeof report.execution.node_version !== "string" ||
    typeof report.execution.platform !== "string" ||
    typeof report.execution.architecture !== "string" ||
    typeof report.execution.playwright_version !== "string" ||
    typeof report.execution.browser.engine !== "string" ||
    typeof report.execution.browser.product_hint !== "string" ||
    typeof report.execution.browser.version !== "string"
  ) {
    throw new ComparisonError(
      "render-report-invalid",
      "The report execution environment is incomplete.",
      {},
    );
  }
  assertFiniteDate(report.execution.completed_at, "render-report-invalid");

  const contractKeys = [
    "deterministic_profile_version",
    "contract_mode",
    "capture_manifest",
    "wait_until",
    "timeout_ms",
    "settle_ms",
    "screenshot_animation_handling",
    "service_workers",
    "downloads",
    "locale",
    "timezone",
    "video_requested",
    "video_duration_ms",
    "local_network_policy",
    "remote_network_policy",
    "spa_fallback",
    "lazy_loading_policy",
    "interaction_policy",
    "limits",
    "profiles",
    "scenarios",
  ];
  const contract = report.capture_contract;
  if (
    !hasExactKeys(contract, contractKeys) ||
    contract.deterministic_profile_version !== 1 ||
    !Array.isArray(contract.profiles) ||
    contract.profiles.length < 1 ||
    contract.profiles.length > 12 ||
    !Array.isArray(contract.scenarios) ||
    contract.scenarios.length < 1 ||
    contract.scenarios.length > 12
  ) {
    throw new ComparisonError(
      "render-report-invalid",
      "The capture contract is invalid or contains unsupported fields.",
      {},
    );
  }

  if (
    !Array.isArray(report.routes) ||
    report.routes.length < 1 ||
    report.routes.length > 12
  ) {
    throw new ComparisonError(
      "render-report-invalid",
      "The route contract is invalid.",
      {},
    );
  }
  const routes = new Map();
  for (const route of report.routes) {
    if (
      !hasExactKeys(route, ["id", "requested", "url"]) ||
      !/^route-[0-9]{2}$/u.test(route.id ?? "") ||
      typeof route.requested !== "string" ||
      routes.has(route.id)
    ) {
      throw new ComparisonError(
        "render-report-invalid",
        "A route identity is invalid or duplicated.",
        {},
      );
    }
    assertLoopbackUrl(route.url);
    routes.set(route.id, route);
  }

  const profiles = new Map();
  for (const profile of contract.profiles) {
    validateProfile(profile);
    if (profiles.has(profile.id)) {
      throw new ComparisonError(
        "render-report-invalid",
        "A capture profile is duplicated.",
        {},
      );
    }
    profiles.set(profile.id, profile);
  }
  const scenarios = new Map();
  for (const scenario of contract.scenarios) {
    validateScenario(scenario, profiles, routes);
    if (scenarios.has(scenario.id)) {
      throw new ComparisonError(
        "render-report-invalid",
        "A capture scenario is duplicated.",
        {},
      );
    }
    scenarios.set(scenario.id, scenario);
  }

  if (
    !Array.isArray(report.captures) ||
    report.captures.length < 1 ||
    report.captures.length > MAX_CAPTURE_COUNT
  ) {
    throw new ComparisonError(
      "render-report-invalid",
      "The report capture set is empty or unbounded.",
      {},
    );
  }
  const expectedCaptureIds = new Set();
  for (const scenario of scenarios.values()) {
    for (const profileId of scenario.profile_ids) {
      expectedCaptureIds.add(`${scenario.id}-${profileId}`);
    }
  }
  const captureKeys = [
    "id",
    "route_id",
    "scenario_id",
    "route_label",
    "state_label",
    "profile_id",
    "capture_status",
    "failure",
    "requested_url",
    "final_url",
    "http_status",
    "viewport",
    "preferences",
    "review_mode",
    "interaction",
    "screenshot",
    "video",
    "console",
    "page_errors",
    "network",
    "document",
    "focus",
  ];
  const captures = new Map();
  const screenshotPaths = new Set();
  for (const capture of report.captures) {
    if (
      !hasExactKeys(capture, captureKeys) ||
      !CAPTURE_ID_PATTERN.test(capture.id ?? "") ||
      !expectedCaptureIds.has(capture.id) ||
      captures.has(capture.id) ||
      capture.capture_status !== "complete" ||
      capture.failure !== null ||
      !ID_PATTERN.test(capture.scenario_id ?? "") ||
      !ID_PATTERN.test(capture.profile_id ?? "") ||
      !routes.has(capture.route_id) ||
      !scenarios.has(capture.scenario_id) ||
      !profiles.has(capture.profile_id)
    ) {
      throw new ComparisonError(
        "render-report-invalid",
        "A capture is incomplete, duplicated, or inconsistent with its contract.",
        {},
      );
    }
    const scenario = scenarios.get(capture.scenario_id);
    const profile = profiles.get(capture.profile_id);
    if (
      capture.id !== `${capture.scenario_id}-${capture.profile_id}` ||
      scenario.route_id !== capture.route_id ||
      scenario.route_label !== capture.route_label ||
      scenario.state_label !== capture.state_label ||
      !scenario.profile_ids.includes(capture.profile_id) ||
      !deepEqual(capture.viewport, profile.viewport)
    ) {
      throw new ComparisonError(
        "render-report-invalid",
        "A capture identity does not match its profile and state contract.",
        {},
      );
    }
    assertLoopbackUrl(capture.requested_url);
    assertLoopbackUrl(capture.final_url);
    validateViewport(capture.viewport);
    validateScreenshotContract(capture.screenshot);
    validateTypographySampling(capture.document);
    if (screenshotPaths.has(capture.screenshot.path)) {
      throw new ComparisonError(
        "render-report-invalid",
        "A screenshot path is duplicated.",
        {},
      );
    }
    screenshotPaths.add(capture.screenshot.path);
    captures.set(capture.id, capture);
  }
  if (
    captures.size !== expectedCaptureIds.size ||
    [...expectedCaptureIds].some((id) => !captures.has(id))
  ) {
    throw new ComparisonError(
      "render-report-invalid",
      "The report does not contain exactly the capture set declared by its scenarios.",
      {},
    );
  }
  return { captures, profiles, scenarios, routes };
}

async function readRenderEvidence(rawPath, role, renderSchemaSha256) {
  if (looksLikeUri(rawPath)) {
    throw new ComparisonError(
      "remote-input-unsupported",
      "Render comparison accepts local filesystem paths only.",
      { role },
    );
  }
  assertSafeFilesystemArgument(rawPath);
  const reportPath = path.resolve(rawPath);
  if (path.basename(reportPath) !== "render-review.json") {
    throw new ComparisonError(
      "invalid-report-name",
      "Each input must identify an original render-review.json file.",
      { role },
    );
  }
  const root = path.dirname(reportPath);
  const reportBytes = await readBoundedRegularFile(
    reportPath,
    MAX_REPORT_BYTES,
    "render-report-missing",
    "render-report-size-invalid",
  );
  const report = parseJson(
    reportBytes,
    "render-report-invalid",
    "A render report is not valid bounded JSON.",
  );

  const markerPath = path.join(root, ".design-dna-render-review.json");
  const markerBytes = await readBoundedRegularFile(
    markerPath,
    MAX_MARKER_BYTES,
    "render-marker-missing",
    "render-marker-size-invalid",
  );
  const marker = parseJson(
    markerBytes,
    "render-marker-invalid",
    "A render ownership marker is not valid bounded JSON.",
  );
  const expectedPathSha = sha256(normalizePathForComparison(root));
  if (
    !hasExactKeys(marker, [
      "schema_version",
      "marker_type",
      "tool",
      "output_identity",
      "report",
      "created_at",
      "build_id_sha256",
    ]) ||
    marker.schema_version !== 3 ||
    marker.marker_type !== "design-dna-render-review-output" ||
    !hasExactKeys(marker.tool, ["name", "version"]) ||
    marker.tool.name !== "design-dna-rendered-review" ||
    marker.tool.version !== "3.0.0" ||
    !hasExactKeys(marker.output_identity, ["id", "path_sha256"]) ||
    !hasExactKeys(marker.report, ["path", "sha256", "bytes"]) ||
    marker.report.path !== "render-review.json" ||
    marker.report.bytes !== reportBytes.length ||
    marker.report.sha256 !== sha256(reportBytes) ||
    marker.output_identity.path_sha256 !== expectedPathSha ||
    !SHA256_PATTERN.test(marker.output_identity.id ?? "") ||
    !SHA256_PATTERN.test(marker.build_id_sha256 ?? "") ||
    !Number.isFinite(Date.parse(marker.created_at ?? ""))
  ) {
    throw new ComparisonError(
      "render-evidence-identity-invalid",
      "The report and its path-bound ownership marker do not form valid original evidence.",
      { role },
    );
  }
  if (
    !deepEqual(marker.output_identity, report.output_identity) ||
    marker.build_id_sha256 !== sha256(report.build?.id ?? "")
  ) {
    throw new ComparisonError(
      "render-evidence-identity-invalid",
      "The render report identity does not match its ownership marker.",
      { role },
    );
  }
  const validated = validateRenderReport(report);
  if (
    report.artifacts?.report?.path !== "render-review.json" ||
    report.artifacts.report.bytes !== reportBytes.length ||
    report.artifacts?.marker?.path !== ".design-dna-render-review.json" ||
    report.artifacts.marker.bytes !== markerBytes.length ||
    !Number.isSafeInteger(report.artifacts.capture_bytes) ||
    report.artifacts.capture_bytes < 0 ||
    report.artifacts.capture_bytes > MAX_INPUT_ARTIFACT_BYTES ||
    !Number.isSafeInteger(report.artifacts.total_bytes) ||
    report.artifacts.total_bytes < 1 ||
    report.artifacts.total_bytes > MAX_INPUT_ARTIFACT_BYTES
  ) {
    throw new ComparisonError(
      "render-report-invalid",
      "The report's artifact accounting does not match its evidence files.",
      { role },
    );
  }

  const screenshots = new Map();
  let screenshotBytes = 0;
  for (const capture of report.captures) {
    const relative = capture.screenshot.path;
    const screenshotPath = path.resolve(root, ...relative.split("/"));
    if (!isWithin(root, screenshotPath)) {
      throw new ComparisonError(
        "screenshot-path-escape",
        "A screenshot path escapes its render evidence root.",
        { role, capture_id: capture.id },
      );
    }
    const bytes = await readBoundedRegularFile(
      screenshotPath,
      MAX_SCREENSHOT_BYTES,
      "screenshot-missing",
      "screenshot-size-invalid",
    );
    if (
      bytes.length !== capture.screenshot.bytes ||
      sha256(bytes) !== capture.screenshot.sha256
    ) {
      throw new ComparisonError(
        "screenshot-hash-mismatch",
        "A screenshot does not match the byte count and SHA-256 pinned by its report.",
        { role, capture_id: capture.id },
      );
    }
    screenshotBytes += bytes.length;
    if (
      screenshotBytes > report.artifacts.capture_bytes ||
      screenshotBytes > MAX_INPUT_ARTIFACT_BYTES
    ) {
      throw new ComparisonError(
        "render-artifact-accounting-invalid",
        "Screenshot bytes exceed the bounded artifact accounting pinned by the report.",
        { role },
      );
    }
    if (
      bytes.length < PNG_SIGNATURE.length ||
      !bytes.subarray(0, PNG_SIGNATURE.length).equals(PNG_SIGNATURE)
    ) {
      throw new ComparisonError(
        "screenshot-invalid-png",
        "A screenshot is not a PNG despite its report contract.",
        { role, capture_id: capture.id },
      );
    }
    screenshots.set(capture.id, bytes);
  }
  return {
    role,
    root,
    report,
    reportBytes,
    reportSha256: sha256(reportBytes),
    marker,
    renderSchemaSha256,
    ...validated,
    screenshots,
  };
}

function routeProjection(report) {
  return report.routes.map((route) => ({
    id: route.id,
    requested: route.requested,
  }));
}

function captureIdentity(capture) {
  return {
    id: capture.id,
    route_id: capture.route_id,
    scenario_id: capture.scenario_id,
    profile_id: capture.profile_id,
    route_label: capture.route_label,
    state_label: capture.state_label,
    viewport: capture.viewport,
    preferences: capture.preferences,
    review_mode: capture.review_mode,
    interaction: capture.interaction,
  };
}

function environmentProjection(report) {
  return {
    "report.tool.version": report.tool.version,
    "execution.node_version": report.execution.node_version,
    "execution.platform": report.execution.platform,
    "execution.architecture": report.execution.architecture,
    "execution.playwright_version": report.execution.playwright_version,
    "execution.playwright_entry_sha256": report.execution.playwright_entry_sha256,
    "execution.browser.engine": report.execution.browser.engine,
    "execution.browser.product_hint": report.execution.browser.product_hint,
    "execution.browser.version": report.execution.browser.version,
    "execution.browser.executable_source":
      report.execution.browser.executable_source,
    "execution.browser.executable_name":
      report.execution.browser.executable_name,
    "execution.browser.executable_sha256":
      report.execution.browser.executable_sha256,
  };
}

function requireCompatible(baseline, candidate) {
  if (
    baseline.renderSchemaSha256 !== candidate.renderSchemaSha256 ||
    baseline.report.schema_version !== candidate.report.schema_version ||
    baseline.report.tool.version !== candidate.report.tool.version
  ) {
    throw new ComparisonError(
      "report-schema-incompatible",
      "Baseline and candidate report schema identities are incompatible.",
      {},
    );
  }
  if (
    !deepEqual(
      baseline.report.capture_contract,
      candidate.report.capture_contract,
    )
  ) {
    throw new ComparisonError(
      "capture-contract-incompatible",
      "Baseline and candidate capture contracts differ. Recapture them with one identical contract.",
      {
        baseline_contract_sha256: sha256Json(
          baseline.report.capture_contract,
        ),
        candidate_contract_sha256: sha256Json(
          candidate.report.capture_contract,
        ),
      },
    );
  }
  if (
    !deepEqual(
      routeProjection(baseline.report),
      routeProjection(candidate.report),
    )
  ) {
    throw new ComparisonError(
      "route-contract-incompatible",
      "Baseline and candidate route identities differ.",
      {},
    );
  }
  const baselineIds = [...baseline.captures.keys()].sort();
  const candidateIds = [...candidate.captures.keys()].sort();
  if (!deepEqual(baselineIds, candidateIds)) {
    throw new ComparisonError(
      "capture-set-incompatible",
      "Baseline and candidate capture sets differ.",
      { baseline_count: baselineIds.length, candidate_count: candidateIds.length },
    );
  }
  for (const id of baselineIds) {
    const baselineCapture = baseline.captures.get(id);
    const candidateCapture = candidate.captures.get(id);
    if (!deepEqual(captureIdentity(baselineCapture), captureIdentity(candidateCapture))) {
      throw new ComparisonError(
        "capture-identity-incompatible",
        "A matched capture differs in route, profile, state, viewport, preferences, or interaction evidence.",
        { capture_id: id },
      );
    }
    if (
      baselineCapture.screenshot.pixel_width !==
        candidateCapture.screenshot.pixel_width ||
      baselineCapture.screenshot.pixel_height !==
        candidateCapture.screenshot.pixel_height
    ) {
      throw new ComparisonError(
        "screenshot-dimensions-incompatible",
        "Matched screenshots declare different pixel dimensions.",
        { capture_id: id },
      );
    }
  }

  const baselineEnvironment = environmentProjection(baseline.report);
  const candidateEnvironment = environmentProjection(candidate.report);
  const environmentDifferences = [];
  for (const field of Object.keys(baselineEnvironment)) {
    if (baselineEnvironment[field] !== candidateEnvironment[field]) {
      environmentDifferences.push({
        field,
        baseline: String(baselineEnvironment[field]),
        candidate: String(candidateEnvironment[field]),
      });
    }
  }
  const warnings = [];
  if (environmentDifferences.length) warnings.push("environment-difference");
  if (
    baseline.report.output_identity.id ===
    candidate.report.output_identity.id
  ) {
    warnings.push("same-render-output-identity");
  }
  if (baseline.report.build.id === candidate.report.build.id) {
    warnings.push("same-build-id");
  }
  return {
    captureIds: baselineIds,
    environmentDifferences,
    warnings,
  };
}

function baselineFreshness(baseline, candidate) {
  const baselineTime = assertFiniteDate(
    baseline.report.execution.completed_at,
    "render-report-invalid",
  );
  const candidateTime = assertFiniteDate(
    candidate.report.execution.completed_at,
    "render-report-invalid",
  );
  const ageDays = (candidateTime - baselineTime) / 86_400_000;
  const warnings = [];
  let status = "current";
  if (ageDays > BASELINE_STALE_DAYS) {
    status = "stale";
    warnings.push("baseline-older-than-30-days-at-candidate-capture");
  } else if (ageDays < 0) {
    status = "indeterminate";
    warnings.push("baseline-captured-after-candidate");
  }
  if (
    Math.abs(
      Date.parse(baseline.marker.created_at) -
        Date.parse(baseline.report.execution.completed_at),
    ) >
    5 * 60 * 1000
  ) {
    warnings.push("baseline-marker-and-capture-times-differ");
  }
  return {
    status,
    threshold_days: BASELINE_STALE_DAYS,
    age_days: Number(ageDays.toFixed(6)),
    warnings,
  };
}

async function validateOutput(raw, inputRoots) {
  if (looksLikeUri(raw)) {
    throw new ComparisonError(
      "remote-output-unsupported",
      "The output must be a local filesystem directory path.",
      {},
    );
  }
  assertSafeFilesystemArgument(raw);
  const output = path.resolve(raw);
  const unsafeExact = [
    path.parse(output).root,
    process.cwd(),
    PACKAGE_ROOT,
    os.homedir(),
  ].filter(Boolean);
  if (unsafeExact.some((candidate) => isSamePath(candidate, output))) {
    throw new ComparisonError(
      "unsafe-output",
      "The selected output is an unsafe broad directory.",
      {},
    );
  }
  if (
    inputRoots.some(
      (root) => isWithin(root, output) || isWithin(output, root),
    )
  ) {
    throw new ComparisonError(
      "output-input-overlap",
      "The comparison output must be separate from both input evidence trees.",
      {},
    );
  }
  await assertNoSymlinkComponents(output, false);
  const existing = await lstat(output).catch(() => null);
  if (existing) {
    throw new ComparisonError(
      "output-exists",
      "The output directory already exists. This tool never replaces evidence.",
      {},
    );
  }
  const parent = path.dirname(output);
  await mkdir(parent, { recursive: true });
  await assertNoSymlinkComponents(parent);
  return output;
}

function loadPlaywright() {
  try {
    const loaded = resolvePlaywright({ moduleUrl: import.meta.url });
    return {
      playwright: loaded.playwright,
      version: loaded.dependency.version,
      source: loaded.source,
      dependency: loaded.dependency,
    };
  } catch (error) {
    throw new ComparisonError(
      error?.code || "playwright-unavailable",
      String(error?.message || error),
      error?.details || {},
      3,
    );
  }
}

async function comparePngs(page, baselineBytes, candidateBytes, expected) {
  let result;
  try {
    result = await page.evaluate(
      async ({ baselineBase64, candidateBase64 }) => {
        const decode = async (encoded) => {
          const binary = atob(encoded);
          const bytes = new Uint8Array(binary.length);
          for (let index = 0; index < binary.length; index += 1) {
            bytes[index] = binary.charCodeAt(index);
          }
          return createImageBitmap(new Blob([bytes], { type: "image/png" }));
        };
        const baseline = await decode(baselineBase64);
        const candidate = await decode(candidateBase64);
        if (
          baseline.width !== candidate.width ||
          baseline.height !== candidate.height
        ) {
          return {
            incompatible: true,
            baseline_width: baseline.width,
            baseline_height: baseline.height,
            candidate_width: candidate.width,
            candidate_height: candidate.height,
          };
        }
        const width = baseline.width;
        const height = baseline.height;
        const first = document.createElement("canvas");
        const second = document.createElement("canvas");
        const diff = document.createElement("canvas");
        for (const canvas of [first, second, diff]) {
          canvas.width = width;
          canvas.height = height;
        }
        const firstContext = first.getContext("2d", {
          alpha: true,
          willReadFrequently: true,
        });
        const secondContext = second.getContext("2d", {
          alpha: true,
          willReadFrequently: true,
        });
        const diffContext = diff.getContext("2d", {
          alpha: false,
          willReadFrequently: true,
        });
        firstContext.drawImage(baseline, 0, 0);
        secondContext.drawImage(candidate, 0, 0);
        const firstPixels = firstContext.getImageData(0, 0, width, height);
        const secondPixels = secondContext.getImageData(0, 0, width, height);
        const diffPixels = diffContext.createImageData(width, height);
        let mismatchPixels = 0;
        for (let offset = 0; offset < firstPixels.data.length; offset += 4) {
          const changed =
            firstPixels.data[offset] !== secondPixels.data[offset] ||
            firstPixels.data[offset + 1] !== secondPixels.data[offset + 1] ||
            firstPixels.data[offset + 2] !== secondPixels.data[offset + 2] ||
            firstPixels.data[offset + 3] !== secondPixels.data[offset + 3];
          if (changed) {
            mismatchPixels += 1;
            diffPixels.data[offset] = 255;
            diffPixels.data[offset + 1] = 0;
            diffPixels.data[offset + 2] = 96;
            diffPixels.data[offset + 3] = 255;
          } else {
            const luminance = Math.round(
              firstPixels.data[offset] * 0.2126 +
                firstPixels.data[offset + 1] * 0.7152 +
                firstPixels.data[offset + 2] * 0.0722,
            );
            const quiet = Math.round(24 + luminance * 0.18);
            diffPixels.data[offset] = quiet;
            diffPixels.data[offset + 1] = quiet;
            diffPixels.data[offset + 2] = quiet;
            diffPixels.data[offset + 3] = 255;
          }
        }
        diffContext.putImageData(diffPixels, 0, 0);
        baseline.close();
        candidate.close();
        return {
          incompatible: false,
          width,
          height,
          mismatch_pixels: mismatchPixels,
          diff_base64: diff.toDataURL("image/png").split(",", 2)[1],
        };
      },
      {
        baselineBase64: baselineBytes.toString("base64"),
        candidateBase64: candidateBytes.toString("base64"),
      },
    );
  } catch {
    throw new ComparisonError(
      "png-decode-failed",
      "Chromium could not decode and compare a validated PNG pair.",
      {},
      3,
    );
  }
  if (
    result.incompatible ||
    result.width !== expected.width ||
    result.height !== expected.height
  ) {
    throw new ComparisonError(
      "screenshot-dimensions-incompatible",
      "Decoded PNG dimensions do not match the compatible report contract.",
      {},
    );
  }
  const diffBytes = Buffer.from(result.diff_base64, "base64");
  if (
    diffBytes.length < PNG_SIGNATURE.length ||
    !diffBytes.subarray(0, PNG_SIGNATURE.length).equals(PNG_SIGNATURE)
  ) {
    throw new ComparisonError(
      "diff-generation-failed",
      "Chromium did not return a valid PNG diff artifact.",
      {},
      3,
    );
  }
  return {
    width: result.width,
    height: result.height,
    mismatchPixels: result.mismatch_pixels,
    diffBytes,
  };
}

function artifactRecord(relativePath, bytes, width, height) {
  return {
    path: relativePath.replaceAll(path.sep, "/"),
    sha256: sha256(bytes),
    media_type: "image/png",
    bytes: bytes.length,
    pixel_width: width,
    pixel_height: height,
  };
}

function artifactManifest(comparisons, contactSheet) {
  const records = [
    { path: contactSheet.path, bytes: contactSheet.bytes, sha256: contactSheet.sha256 },
    ...comparisons.flatMap((comparison) => ["baseline", "actual", "diff"].map((name) => {
      const artifact = comparison.artifacts[name];
      return { path: artifact.path, bytes: artifact.bytes, sha256: artifact.sha256 };
    })),
  ].sort((a, b) => a.path.localeCompare(b.path));
  return {
    algorithm: "sha256-canonical-artifact-list-v1",
    sha256: sha256(canonicalJson(records)),
    count: records.length,
    bytes: records.reduce((total, record) => total + record.bytes, 0),
  };
}

function inputIdentity(evidence) {
  return {
    role: evidence.role,
    report_sha256: evidence.reportSha256,
    report_bytes: evidence.reportBytes.length,
    render_report_schema_sha256: evidence.renderSchemaSha256,
    output_identity: evidence.report.output_identity,
    build: {
      id: evidence.report.build.id,
      id_sha256: sha256(evidence.report.build.id),
      target_kind: evidence.report.build.target_kind,
      source_manifest_sha256:
        evidence.report.source_snapshot.manifest.manifest_sha256,
    },
    captured_at: evidence.report.execution.completed_at,
    marker_created_at: evidence.marker.created_at,
    execution_environment: environmentProjection(evidence.report),
  };
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function buildContactSheet(comparisonId, comparisons, freshness, warnings) {
  const rows = comparisons
    .map(
      (comparison) => `<article>
  <header>
    <h2>${escapeHtml(comparison.capture_id)}</h2>
    <p>${escapeHtml(comparison.identity.route_label)} · ${escapeHtml(comparison.identity.state_label)} · ${escapeHtml(comparison.identity.profile_id)}</p>
    <p><strong>${comparison.metrics.mismatch_pixels.toLocaleString("en-US")}</strong> changed pixels (${(comparison.metrics.mismatch_pixel_ratio * 100).toFixed(6)}%). Human accept/reject remains required.</p>
  </header>
  <div class="triplet">
    <figure><img src="${escapeHtml(comparison.artifacts.baseline.path)}" alt="Baseline capture"><figcaption>Baseline</figcaption></figure>
    <figure><img src="${escapeHtml(comparison.artifacts.actual.path)}" alt="Candidate capture"><figcaption>Actual candidate</figcaption></figure>
    <figure><img src="${escapeHtml(comparison.artifacts.diff.path)}" alt="Exact pixel difference visualization"><figcaption>Pixel diff: magenta changed, gray unchanged</figcaption></figure>
  </div>
</article>`,
    )
    .join("\n");
  const warningText = [...freshness.warnings, ...warnings];
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
  <title>Rendered comparison — ${escapeHtml(comparisonId)}</title>
  <style>
    :root{font-family:system-ui,sans-serif;color:#171717;background:#f4f4f1}
    body{margin:0;padding:2rem}main{max-width:1600px;margin:auto}
    h1{font-size:clamp(2rem,5vw,4rem);margin:.2em 0}.notice{max-width:75ch}
    article{margin:3rem 0;padding-top:1.5rem;border-top:2px solid #171717}
    .triplet{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}
    figure{margin:0;background:white;border:1px solid #bbb;padding:.5rem}
    img{display:block;width:100%;height:auto;background:#222}
    figcaption{padding:.65rem .2rem .15rem;font-weight:700}
    @media(max-width:800px){body{padding:1rem}.triplet{grid-template-columns:1fr}}
  </style>
</head>
<body><main>
  <p>Design DNA cross-build evidence</p>
  <h1>${escapeHtml(comparisonId)}</h1>
  <p class="notice"><strong>Decision status: human accept/reject required.</strong>
  Exact pixel equality is not visual approval. This tool applies no threshold,
  masks, baseline update, or automatic decision.</p>
  <p class="notice">Baseline freshness: ${escapeHtml(freshness.status)}.
  Warnings: ${escapeHtml(warningText.length ? warningText.join(", ") : "none")}.</p>
  ${rows}
</main></body></html>`;
}

function outputMarker(outputIdentity, reportBytes, comparisonId, createdAt, runtimeIdentity, artifacts) {
  return {
    schema_version: SCHEMA_VERSION,
    marker_type: "design-dna-render-comparison-output",
    tool: { name: TOOL_NAME, version: TOOL_VERSION },
    producer_script_sha256: PRODUCER_SCRIPT_SHA256,
    runtime_identity: runtimeIdentity,
    output_identity: outputIdentity,
    report: {
      path: REPORT_NAME,
      sha256: sha256(reportBytes),
      bytes: reportBytes.length,
    },
    artifact_manifest: artifacts,
    created_at: createdAt,
    comparison_id_sha256: sha256(comparisonId),
  };
}

async function removeOwnedStaging(staging, parent) {
  if (!staging || !isWithin(parent, staging) || isSamePath(parent, staging)) {
    return;
  }
  if (!path.basename(staging).startsWith(".design-dna-comparison-transaction-")) {
    return;
  }
  const marker = path.join(staging, TRANSACTION_MARKER);
  const markerBytes = await readFile(marker).catch(() => null);
  if (!markerBytes || markerBytes.toString("utf8") !== "owned\n") return;
  await rm(staging, { recursive: true, force: true });
}

async function run(options) {
  const renderSchemaBytes = await readBoundedRegularFile(
    RENDER_SCHEMA_PATH,
    MAX_REPORT_BYTES,
    "render-schema-missing",
    "render-schema-invalid",
  );
  const renderSchema = parseJson(
    renderSchemaBytes,
    "render-schema-invalid",
    "The canonical render-review schema is unavailable or invalid.",
  );
  if (
    renderSchema.$id !==
      "https://design-dna.local/schemas/render-review.schema.json" ||
    renderSchema.properties?.schema_version?.const !== 3 ||
    renderSchema.properties?.tool?.properties?.version?.const !== "3.0.0"
  ) {
    throw new ComparisonError(
      "render-schema-invalid",
      "The canonical render-review schema identity is unexpected.",
      {},
    );
  }
  const renderSchemaSha256 = sha256(renderSchemaBytes);
  const baseline = await readRenderEvidence(
    options.baseline,
    "baseline",
    renderSchemaSha256,
  );
  const candidate = await readRenderEvidence(
    options.candidate,
    "candidate",
    renderSchemaSha256,
  );
  const compatible = requireCompatible(baseline, candidate);
  const freshness = baselineFreshness(baseline, candidate);
  const output = await validateOutput(options.output, [
    baseline.root,
    candidate.root,
  ]);
  const parent = path.dirname(output);
  const staging = path.join(
    parent,
    `.design-dna-comparison-transaction-${randomBytes(12).toString("hex")}`,
  );
  let browser = null;
  let context = null;
  let committed = false;
  try {
    await mkdir(staging);
    await writeFile(path.join(staging, TRANSACTION_MARKER), "owned\n");
    const captureRoot = path.join(staging, "captures");
    await mkdir(captureRoot);

    const loaded = loadPlaywright();
    const browserExecutable = browserExecutableIdentity(
      discoverSharedBrowser(loaded.playwright, options.browserExecutable),
    );
    try {
      browser = await loaded.playwright.chromium.launch({
        headless: true,
        executablePath: browserExecutable.path,
        args: [
          "--disable-background-networking",
          "--disable-component-update",
          "--disable-default-apps",
          "--disable-sync",
          "--dns-prefetch-disable",
          "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
          "--no-first-run",
        ],
      });
    } catch {
      throw new ComparisonError(
        "browser-launch-failed",
        "Chromium could not be launched for offline PNG comparison.",
        {},
        3,
      );
    }
    context = await browser.newContext({
      serviceWorkers: "block",
      locale: "en-US",
      timezoneId: "UTC",
    });
    await context.route("**/*", async (route) => {
      await route.abort("blockedbyclient");
    });
    const page = await context.newPage();
    await page.goto("about:blank");

    const comparisons = [];
    let outputBytes = 0;
    let totalPixels = 0;
    let mismatchPixels = 0;
    for (let index = 0; index < compatible.captureIds.length; index += 1) {
      const captureId = compatible.captureIds[index];
      const baselineCapture = baseline.captures.get(captureId);
      const candidateCapture = candidate.captures.get(captureId);
      const baselineBytes = baseline.screenshots.get(captureId);
      const candidateBytes = candidate.screenshots.get(captureId);
      const compared = await comparePngs(
        page,
        baselineBytes,
        candidateBytes,
        {
          width: baselineCapture.screenshot.pixel_width,
          height: baselineCapture.screenshot.pixel_height,
        },
      );
      if (compared.diffBytes.length > MAX_DIFF_BYTES) {
        throw new ComparisonError(
          "diff-artifact-limit-exceeded",
          "A generated pixel-diff PNG exceeds the bounded per-artifact limit.",
          { maximum_bytes: MAX_DIFF_BYTES },
        );
      }
      const captureDirectory = path.join(
        "captures",
        `${String(index + 1).padStart(3, "0")}-${captureId}`,
      );
      const absoluteDirectory = path.join(staging, captureDirectory);
      await mkdir(absoluteDirectory);
      const baselineRelative = path.join(captureDirectory, "baseline.png");
      const actualRelative = path.join(captureDirectory, "actual.png");
      const diffRelative = path.join(captureDirectory, "diff.png");
      const nextBytes =
        baselineBytes.length +
        candidateBytes.length +
        compared.diffBytes.length;
      if (outputBytes + nextBytes > MAX_OUTPUT_BYTES) {
        throw new ComparisonError(
          "comparison-output-limit-exceeded",
          "The comparison artifact set exceeds the bounded output limit.",
          { maximum_bytes: MAX_OUTPUT_BYTES },
        );
      }
      await writeFile(path.join(staging, baselineRelative), baselineBytes);
      await writeFile(path.join(staging, actualRelative), candidateBytes);
      await writeFile(path.join(staging, diffRelative), compared.diffBytes);
      outputBytes += nextBytes;
      const pixels = compared.width * compared.height;
      totalPixels += pixels;
      mismatchPixels += compared.mismatchPixels;
      comparisons.push({
        capture_id: captureId,
        identity: captureIdentity(baselineCapture),
        artifacts: {
          baseline: artifactRecord(
            baselineRelative,
            baselineBytes,
            compared.width,
            compared.height,
          ),
          actual: artifactRecord(
            actualRelative,
            candidateBytes,
            compared.width,
            compared.height,
          ),
          diff: artifactRecord(
            diffRelative,
            compared.diffBytes,
            compared.width,
            compared.height,
          ),
        },
        metrics: {
          algorithm: "exact-decoded-rgba-v1",
          total_pixels: pixels,
          mismatch_pixels: compared.mismatchPixels,
          mismatch_pixel_ratio: compared.mismatchPixels / pixels,
        },
        review_status: "human-accept-reject-required",
      });
    }

    const contactPayload = Buffer.from(
      buildContactSheet(
        options.comparisonId,
        comparisons,
        freshness,
        compatible.warnings,
      ),
      "utf8",
    );
    if (outputBytes + contactPayload.length > MAX_OUTPUT_BYTES) {
      throw new ComparisonError(
        "comparison-output-limit-exceeded",
        "The comparison artifact set exceeds the bounded output limit.",
        { maximum_bytes: MAX_OUTPUT_BYTES },
      );
    }
    await writeFile(path.join(staging, CONTACT_SHEET_NAME), contactPayload);
    outputBytes += contactPayload.length;
    const contactSheet = {
      path: CONTACT_SHEET_NAME,
      sha256: sha256(contactPayload),
      media_type: "text/html",
      bytes: contactPayload.length,
    };
    const artifactsManifest = artifactManifest(comparisons, contactSheet);
    if (artifactsManifest.bytes !== outputBytes) {
      throw new ComparisonError(
        "artifact-manifest-accounting-invalid",
        "The canonical artifact manifest byte total does not equal the generated comparison artifacts.",
        {},
      );
    }

    const createdAt = new Date().toISOString();
    const outputIdentity = {
      id: randomBytes(32).toString("hex"),
      path_sha256: sha256(normalizePathForComparison(output)),
    };
    const runtimeIdentity = {
      "compare_render_reviews.mjs": PRODUCER_SCRIPT_SHA256,
      "playwright_resolver.mjs": PLAYWRIGHT_RESOLVER_SHA256,
      "render-review.schema.json": renderSchemaSha256,
    };
    const report = {
      schema_version: SCHEMA_VERSION,
      tool: {
        name: TOOL_NAME,
        version: TOOL_VERSION,
        report_schema: "render-comparison.schema.json",
      },
      producer_script_sha256: PRODUCER_SCRIPT_SHA256,
      runtime_identity: runtimeIdentity,
      comparison_id: options.comparisonId,
      created_at: createdAt,
      output_identity: outputIdentity,
      execution_ok: true,
      review_required: true,
      automatic_visual_approval: false,
      decision_status: "human-accept-reject-required",
      execution: {
        node_version: process.version,
        platform: process.platform,
        architecture: process.arch,
        playwright_version: loaded.version,
        playwright_source: loaded.source,
        playwright_entry_sha256: loaded.dependency.resolved_file_sha256,
        browser: {
          engine: "chromium",
          product_hint: browserExecutable.name,
          version: browser.version(),
          executable_source: browserExecutable.source,
          executable_name: path.basename(browserExecutable.path),
          executable_sha256: browserExecutable.sha256,
        },
        network_policy:
          "offline-about-blank-data-png-decode-all-routed-requests-blocked",
      },
      privacy: {
        classification: "potentially-sensitive-rendered-comparison-evidence",
        visual_content_not_redacted: true,
        absolute_paths_persisted: false,
        retention_notice:
          "The output persists at the operator-selected path until the operator deliberately removes it.",
        limitations: [
          "Baseline and candidate screenshots can visibly contain personal, confidential, or credential-like content; pixels are copied without redaction.",
          "Hashes and build identifiers are pseudonymous or operator-selected evidence and can remain sensitive when correlated with other records.",
        ],
      },
      mask_policy: {
        supported: false,
        mode: "none",
        declaration: "operator-explicit",
        regions_applied: 0,
      },
      inputs: {
        baseline: inputIdentity(baseline),
        candidate: inputIdentity(candidate),
      },
      compatibility: {
        status: "compatible",
        capture_count: comparisons.length,
        capture_contract_sha256: sha256Json(
          baseline.report.capture_contract,
        ),
        route_contract_sha256: sha256Json(
          routeProjection(baseline.report),
        ),
        capture_identity_sha256: sha256Json(
          comparisons.map((item) => item.identity),
        ),
        environment_differences: compatible.environmentDifferences,
        warnings: compatible.warnings,
      },
      baseline_freshness: freshness,
      comparisons,
      summary: {
        capture_count: comparisons.length,
        changed_capture_count: comparisons.filter(
          (item) => item.metrics.mismatch_pixels > 0,
        ).length,
        total_pixels: totalPixels,
        mismatch_pixels: mismatchPixels,
        mismatch_pixel_ratio: totalPixels ? mismatchPixels / totalPixels : 0,
      },
      artifacts: {
        contact_sheet: contactSheet,
        comparison_bytes: outputBytes,
        manifest: artifactsManifest,
      },
      manual_review: {
        status: "required",
        required_actions: [
          "Inspect every baseline, actual, and pixel-diff triplet in context.",
          "Review baseline freshness and every pinned execution-environment difference.",
          "Record a human accept or reject decision outside this immutable evidence output.",
        ],
        limitations: [
          "Exact RGBA equality does not establish perceptual equivalence, usability, accessibility, design quality, or intentionality.",
          "The comparator does not inspect DOM structure, interactions, motion over time, content truth, performance, or behavior outside the supplied still captures.",
          "No threshold or region mask is applied, and the tool never updates or approves the baseline.",
          "The path-bound markers detect ordinary copying or tampering but are not cryptographic signatures against an attacker able to rewrite all evidence.",
        ],
      },
    };
    const reportPayload = Buffer.from(jsonPayload(report), "utf8");
    if (outputBytes + reportPayload.length > MAX_OUTPUT_BYTES) {
      throw new ComparisonError(
        "comparison-output-limit-exceeded",
        "The comparison report exceeds the bounded output limit.",
        { maximum_bytes: MAX_OUTPUT_BYTES },
      );
    }
    await writeFile(path.join(staging, REPORT_NAME), reportPayload);
    const markerPayload = Buffer.from(
      jsonPayload(
        outputMarker(
          outputIdentity,
          reportPayload,
          options.comparisonId,
          createdAt,
          runtimeIdentity,
          artifactsManifest,
        ),
      ),
      "utf8",
    );
    await writeFile(path.join(staging, MARKER_NAME), markerPayload);
    await assertNoSymlinkComponents(parent);
    if (await lstat(output).catch(() => null)) {
      throw new ComparisonError(
        "output-race",
        "The output path appeared before the transaction could commit.",
        {},
      );
    }
    await rm(path.join(staging, TRANSACTION_MARKER));
    try {
      await rename(staging, output);
    } catch (error) {
      await writeFile(path.join(staging, TRANSACTION_MARKER), "owned\n").catch(
        () => undefined,
      );
      throw error;
    }
    committed = true;
    process.stdout.write(
      `${JSON.stringify({
        schema_version: SCHEMA_VERSION,
        ok: true,
        execution_ok: true,
        review_required: true,
        automatic_visual_approval: false,
        decision_status: "human-accept-reject-required",
        report_path: REPORT_NAME,
        contact_sheet_path: CONTACT_SHEET_NAME,
        capture_count: comparisons.length,
        changed_capture_count: report.summary.changed_capture_count,
        mismatch_pixels: report.summary.mismatch_pixels,
        mismatch_pixel_ratio: report.summary.mismatch_pixel_ratio,
      })}\n`,
    );
    return 0;
  } finally {
    if (context) await context.close().catch(() => undefined);
    if (browser) await browser.close().catch(() => undefined);
    if (!committed) await removeOwnedStaging(staging, parent);
  }
}

function emitFatal(error) {
  const normalized =
    error instanceof ComparisonError
      ? error
      : new ComparisonError(
          "render-comparison-failed",
          "The rendered comparison failed unexpectedly.",
          {},
          4,
        );
  process.stderr.write(
    `${JSON.stringify({
      schema_version: SCHEMA_VERSION,
      ok: false,
      execution_ok: false,
      review_required: true,
      automatic_visual_approval: false,
      decision_status: "comparison-failed",
      error: {
        code: normalized.code,
        message: normalized.message,
        details: normalized.details,
      },
    })}\n`,
  );
  return normalized.exitCode;
}

let exitCode = 0;
try {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    process.stdout.write(`${helpText()}\n`);
  } else {
    exitCode = await run(options);
  }
} catch (error) {
  exitCode = emitFatal(error);
}
process.exitCode = exitCode;
