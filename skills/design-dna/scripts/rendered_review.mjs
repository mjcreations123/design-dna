#!/usr/bin/env node

import { createHash, randomBytes } from "node:crypto";
import { createReadStream } from "node:fs";
import {
  access,
  copyFile,
  lstat,
  mkdir,
  mkdtemp,
  open,
  readdir,
  readFile,
  realpath,
  rename,
  rm,
  stat,
  unlink,
  writeFile,
} from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { browserExecutableIdentity, discoverBrowserExecutable as discoverSharedBrowser, resolvePlaywright } from "./playwright_resolver.mjs";

const TOOL_NAME = "design-dna-rendered-review";
const TOOL_VERSION = "3.0.0";
const SCHEMA_VERSION = 3;
const MARKER_TYPE = "design-dna-render-review-output";
const SCRIPT_PATH = fileURLToPath(import.meta.url);
const PACKAGE_ROOT = path.resolve(path.dirname(SCRIPT_PATH), "../../..");
const MAX_EVENTS = 200;
const MAX_CANDIDATES = 120;
const MAX_ROUTES = 12;
const MAX_CAPTURE_MANIFEST_BYTES = 64 * 1024;
const MAX_CAPTURE_PROFILES = 12;
const MAX_CAPTURE_SCENARIOS = 12;
const MAX_CAPTURE_PLANS = 72;
const MAX_INTERACTIONS_PER_SCENARIO = 12;
const MAX_INTERACTIONS_TOTAL = 60;
const MAX_SELECTOR_LENGTH = 512;
const MAX_INTERACTION_VALUE_LENGTH = 1000;
const MAX_OWNERSHIP_MARKER_BYTES = 16 * 1024;
const ARTIFACT_METADATA_RESERVE_BYTES = 256 * 1024;
const DEFAULT_LIMITS = Object.freeze({
  source_files: 1000,
  source_bytes: 100 * 1024 * 1024,
  source_file_bytes: 20 * 1024 * 1024,
  page_height_css_px: 18000,
  screenshot_pixels: 30 * 1000 * 1000,
  screenshot_bytes: 12 * 1024 * 1024,
  total_artifact_bytes: 80 * 1024 * 1024,
  report_bytes: 5 * 1024 * 1024,
});
const HARD_LIMITS = Object.freeze({
  source_files: 2000,
  source_bytes: 150 * 1024 * 1024,
  source_file_bytes: 30 * 1024 * 1024,
  page_height_css_px: 30000,
  screenshot_pixels: 40 * 1000 * 1000,
  screenshot_bytes: 24 * 1024 * 1024,
  total_artifact_bytes: 150 * 1024 * 1024,
  report_bytes: 8 * 1024 * 1024,
});
const OUTPUT_TREE_LIMITS = Object.freeze({
  files: 4096,
  directories: 1024,
  bytes: HARD_LIMITS.total_artifact_bytes,
  depth: 64,
});
const PUBLIC_ROOT_NAMES = new Set(["dist", "build", "out", "public"]);
const DENIED_PATH_SEGMENTS = new Set([
  ".design-dna",
  ".git",
  ".github",
  ".hg",
  ".svn",
  "config",
  "maintainer",
  "node_modules",
  "private",
  "scripts",
  "secrets",
  "source",
  "src",
  "test",
  "tests",
]);
const DENIED_FILE_NAMES = new Set([
  ".env",
  ".npmrc",
  ".pypirc",
  "composer.json",
  "composer.lock",
  "credentials.json",
  "package-lock.json",
  "package.json",
  "pnpm-lock.yaml",
  "pyproject.toml",
  "requirements.txt",
  "secrets.json",
  "tsconfig.json",
  "yarn.lock",
]);
const PUBLIC_EXTENSIONS = new Set([
  ".avif",
  ".css",
  ".gif",
  ".htm",
  ".html",
  ".ico",
  ".jpeg",
  ".jpg",
  ".js",
  ".json",
  ".mjs",
  ".mp4",
  ".otf",
  ".pdf",
  ".png",
  ".svg",
  ".ttf",
  ".txt",
  ".wasm",
  ".webm",
  ".webmanifest",
  ".webp",
  ".woff",
  ".woff2",
  ".xml",
]);

const PROFILES = Object.freeze([
  {
    id: "mobile-320-text-spacing",
    label: "Mobile 320 · text spacing · touch/no-hover",
    viewport: { width: 320, height: 568, device_scale_factor: 1 },
    is_mobile: true,
    has_touch: true,
    input_modalities: ["touch", "keyboard"],
    pointer: "coarse",
    hover: "none",
    color_scheme: "light",
    reduced_motion: "no-preference",
    forced_colors: "none",
    text_spacing: "wcag-1.4.12",
    zoom: "none",
  },
  {
    id: "mobile-375-light-touch",
    label: "Mobile 375 · light · touch/no-hover",
    viewport: { width: 375, height: 812, device_scale_factor: 1 },
    is_mobile: true,
    has_touch: true,
    input_modalities: ["touch", "keyboard"],
    pointer: "coarse",
    hover: "none",
    color_scheme: "light",
    reduced_motion: "no-preference",
    forced_colors: "none",
    text_spacing: "none",
    zoom: "none",
  },
  {
    id: "mobile-430-light-touch",
    label: "Mobile 430 · light · touch/no-hover",
    viewport: { width: 430, height: 932, device_scale_factor: 1 },
    is_mobile: true,
    has_touch: true,
    input_modalities: ["touch", "keyboard"],
    pointer: "coarse",
    hover: "none",
    color_scheme: "light",
    reduced_motion: "no-preference",
    forced_colors: "none",
    text_spacing: "none",
    zoom: "none",
  },
  {
    id: "intermediate-light",
    label: "Intermediate · light",
    viewport: { width: 768, height: 1024, device_scale_factor: 1 },
    is_mobile: false,
    has_touch: false,
    input_modalities: ["keyboard", "pointer"],
    pointer: "fine",
    hover: "hover",
    color_scheme: "light",
    reduced_motion: "no-preference",
    forced_colors: "none",
    text_spacing: "none",
    zoom: "none",
  },
  {
    id: "desktop-short-light",
    label: "Desktop short height · light",
    viewport: { width: 1280, height: 480, device_scale_factor: 1 },
    is_mobile: false,
    has_touch: false,
    input_modalities: ["keyboard", "pointer"],
    pointer: "fine",
    hover: "hover",
    color_scheme: "light",
    reduced_motion: "no-preference",
    forced_colors: "none",
    text_spacing: "none",
    zoom: "none",
  },
  {
    id: "desktop-light",
    label: "Desktop · light",
    viewport: { width: 1440, height: 1000, device_scale_factor: 1 },
    is_mobile: false,
    has_touch: false,
    input_modalities: ["keyboard", "pointer"],
    pointer: "fine",
    hover: "hover",
    color_scheme: "light",
    reduced_motion: "no-preference",
    forced_colors: "none",
    text_spacing: "none",
    zoom: "none",
  },
  {
    id: "desktop-dark",
    label: "Desktop · dark preference",
    viewport: { width: 1440, height: 1000, device_scale_factor: 1 },
    is_mobile: false,
    has_touch: false,
    input_modalities: ["keyboard", "pointer"],
    pointer: "fine",
    hover: "hover",
    color_scheme: "dark",
    reduced_motion: "no-preference",
    forced_colors: "none",
    text_spacing: "none",
    zoom: "none",
  },
  {
    id: "desktop-reduced-motion",
    label: "Desktop · reduced motion",
    viewport: { width: 1440, height: 1000, device_scale_factor: 1 },
    is_mobile: false,
    has_touch: false,
    input_modalities: ["keyboard", "pointer"],
    pointer: "fine",
    hover: "hover",
    color_scheme: "light",
    reduced_motion: "reduce",
    forced_colors: "none",
    text_spacing: "none",
    zoom: "none",
  },
  {
    id: "desktop-forced-colors",
    label: "Desktop · forced colors",
    viewport: { width: 1440, height: 1000, device_scale_factor: 1 },
    is_mobile: false,
    has_touch: false,
    input_modalities: ["keyboard", "pointer"],
    pointer: "fine",
    hover: "hover",
    color_scheme: "light",
    reduced_motion: "no-preference",
    forced_colors: "active",
    text_spacing: "none",
    zoom: "none",
  },
]);
const MAX_DEFAULT_ROUTES = Math.floor(MAX_CAPTURE_PLANS / PROFILES.length);

class RenderReviewError extends Error {
  constructor(code, message, details = {}, exitCode = 2) {
    super(message);
    this.name = "RenderReviewError";
    this.code = code;
    this.details = details;
    this.exitCode = exitCode;
  }
}

function helpText() {
  return `Design DNA rendered review ${TOOL_VERSION}

Runtime:
  Node.js 20 or newer

Usage:
  node rendered_review.mjs TARGET --output DIR --build-id ID [options]

TARGET:
  http:// or https:// URL
  file:// URL or local HTML file, copied into a bounded public snapshot
  local public/build directory, frozen and served read-only on 127.0.0.1

Options:
  --output DIR                 Required artifact directory
  --build-id ID                Required implementation/build identifier
  --route PATH                 Add a same-origin or local route; repeatable. With
                               --capture-manifest, declare its exact route set.
  --capture-manifest FILE      Strict optional v1 profile/scenario JSON contract
  --browser-executable FILE    Explicit Chrome/Edge/Chromium executable
  --replace                    Transactionally replace an existing safe output
  --timeout-ms N               Navigation timeout, 1000-120000 (default 30000)
  --settle-ms N                Post-load settle time, 0-10000 (default 250)
  --scroll-sweep               Opt-in local viewport sweep before capture
  --video                      Capture optional WebM temporal evidence
  --video-duration-ms N        Extra video observation, 0-10000 (default 1200)
  --max-source-files N         Snapshot file cap, at most ${HARD_LIMITS.source_files}
  --max-source-bytes N         Snapshot byte cap, at most ${HARD_LIMITS.source_bytes}
  --max-source-file-bytes N    Per-file cap, at most ${HARD_LIMITS.source_file_bytes}
  --max-page-height N          Full-page CSS-pixel cap, at most ${HARD_LIMITS.page_height_css_px}
  --max-screenshot-pixels N    Per-screenshot pixel cap, at most ${HARD_LIMITS.screenshot_pixels}
  --max-screenshot-bytes N     Per-screenshot byte cap, at most ${HARD_LIMITS.screenshot_bytes}
  --max-artifact-bytes N       Total evidence cap, at most ${HARD_LIMITS.total_artifact_bytes}
  --max-report-bytes N         JSON report cap, at most ${HARD_LIMITS.report_bytes}
  --help                       Show this help without loading Playwright

Playwright discovery:
  An explicit absolute DESIGN_DNA_PLAYWRIGHT_MODULE_DIR (invalid paths fail
  closed), then the target project's node_modules, a recognized source
  checkout's maintainer/node_modules, then exact node_modules directories inside
  the installed skill.
  Browser discovery uses Playwright's installed Chromium, common Chrome/Edge
  locations, PATH, or --browser-executable; a browser executable never replaces
  the Playwright module prerequisite.

Capture manifest v1:
  A strict JSON object with profiles and scenarios. Profiles declare the
  viewport/device contract, color scheme, reduced motion, forced colors,
  text_spacing (none or wcag-1.4.12), and zoom (none, 200-percent, or
  400-percent). Scenarios declare route/state labels, profile IDs, and up to
  ${MAX_INTERACTIONS_PER_SCENARIO} click/focus/fill/select/check actions.
  State-changing actions are limited to frozen local targets. Selectors must
  match exactly once. Raw fill/select values are not persisted. Browser zoom
  is not simulated and is recorded as manual-required.

Output:
  render-review.json, contact-sheet.html, hashed PNG screenshots, optional
  WebM videos, and a package marker. Automated candidates are advisory. The
  tool never emits an AI score or an automatic visual-quality pass. Existing
  output is replaceable only when its path-bound ownership marker and report
  identity validate. Local snapshots block outbound requests by default.`;
}

function parseInteger(raw, name, minimum, maximum) {
  if (!/^[0-9]+$/.test(raw ?? "")) {
    throw new RenderReviewError(
      "invalid-argument",
      `${name} must be an integer between ${minimum} and ${maximum}.`,
      { argument: name, value: raw ?? null },
    );
  }
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < minimum || value > maximum) {
    throw new RenderReviewError(
      "invalid-argument",
      `${name} must be between ${minimum} and ${maximum}.`,
      { argument: name, value: raw },
    );
  }
  return value;
}

function takeValue(argv, index, option) {
  const value = argv[index + 1];
  if (value === undefined || value.startsWith("--")) {
    throw new RenderReviewError(
      "missing-argument-value",
      `${option} requires a value.`,
      { argument: option },
    );
  }
  return value;
}

function parseArgs(argv) {
  const options = {
    target: null,
    output: null,
    buildId: null,
    routes: [],
    captureManifest: null,
    browserExecutable: process.env.DESIGN_DNA_BROWSER_EXECUTABLE || process.env.CHROME || null,
    replace: false,
    timeoutMs: 30000,
    settleMs: 250,
    scrollSweep: false,
    video: false,
    videoDurationMs: 1200,
    limits: { ...DEFAULT_LIMITS },
    help: false,
  };
  const positionals = [];

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--help" || argument === "-h") {
      options.help = true;
    } else if (argument === "--output") {
      options.output = takeValue(argv, index, argument);
      index += 1;
    } else if (argument === "--build-id") {
      options.buildId = takeValue(argv, index, argument);
      index += 1;
    } else if (argument === "--route") {
      options.routes.push(takeValue(argv, index, argument));
      index += 1;
    } else if (argument === "--capture-manifest") {
      if (options.captureManifest !== null) {
        throw new RenderReviewError(
          "duplicate-capture-manifest",
          "--capture-manifest may be provided only once.",
          {},
        );
      }
      options.captureManifest = takeValue(argv, index, argument);
      index += 1;
    } else if (argument === "--browser-executable") {
      options.browserExecutable = takeValue(argv, index, argument);
      index += 1;
    } else if (argument === "--timeout-ms") {
      options.timeoutMs = parseInteger(
        takeValue(argv, index, argument),
        argument,
        1000,
        120000,
      );
      index += 1;
    } else if (argument === "--settle-ms") {
      options.settleMs = parseInteger(
        takeValue(argv, index, argument),
        argument,
        0,
        10000,
      );
      index += 1;
    } else if (argument === "--video-duration-ms") {
      options.videoDurationMs = parseInteger(
        takeValue(argv, index, argument),
        argument,
        0,
        10000,
      );
      index += 1;
    } else if (argument === "--max-source-files") {
      options.limits.source_files = parseInteger(
        takeValue(argv, index, argument),
        argument,
        1,
        HARD_LIMITS.source_files,
      );
      index += 1;
    } else if (argument === "--max-source-bytes") {
      options.limits.source_bytes = parseInteger(
        takeValue(argv, index, argument),
        argument,
        1024,
        HARD_LIMITS.source_bytes,
      );
      index += 1;
    } else if (argument === "--max-source-file-bytes") {
      options.limits.source_file_bytes = parseInteger(
        takeValue(argv, index, argument),
        argument,
        1024,
        HARD_LIMITS.source_file_bytes,
      );
      index += 1;
    } else if (argument === "--max-page-height") {
      options.limits.page_height_css_px = parseInteger(
        takeValue(argv, index, argument),
        argument,
        500,
        HARD_LIMITS.page_height_css_px,
      );
      index += 1;
    } else if (argument === "--max-screenshot-pixels") {
      options.limits.screenshot_pixels = parseInteger(
        takeValue(argv, index, argument),
        argument,
        100000,
        HARD_LIMITS.screenshot_pixels,
      );
      index += 1;
    } else if (argument === "--max-screenshot-bytes") {
      options.limits.screenshot_bytes = parseInteger(
        takeValue(argv, index, argument),
        argument,
        1024,
        HARD_LIMITS.screenshot_bytes,
      );
      index += 1;
    } else if (argument === "--max-artifact-bytes") {
      options.limits.total_artifact_bytes = parseInteger(
        takeValue(argv, index, argument),
        argument,
        4096,
        HARD_LIMITS.total_artifact_bytes,
      );
      index += 1;
    } else if (argument === "--max-report-bytes") {
      options.limits.report_bytes = parseInteger(
        takeValue(argv, index, argument),
        argument,
        4096,
        HARD_LIMITS.report_bytes,
      );
      index += 1;
    } else if (argument === "--replace") {
      options.replace = true;
    } else if (argument === "--scroll-sweep") {
      options.scrollSweep = true;
    } else if (argument === "--video") {
      options.video = true;
    } else if (argument.startsWith("--")) {
      throw new RenderReviewError(
        "unknown-argument",
        `Unknown option: ${argument}`,
        { argument },
      );
    } else {
      positionals.push(argument);
    }
  }

  if (options.help) {
    return options;
  }
  if (positionals.length !== 1) {
    throw new RenderReviewError(
      "invalid-target",
      "Provide exactly one URL, local HTML file, or local directory target.",
      { targets: positionals },
    );
  }
  options.target = positionals[0];
  if (!options.target.trim() || options.target.length > 4096) {
    throw new RenderReviewError(
      "invalid-target",
      "TARGET cannot be empty or whitespace and cannot exceed 4096 characters.",
      {},
    );
  }
  if (!options.output) {
    throw new RenderReviewError(
      "missing-output",
      "--output is required.",
      {},
    );
  }
  if (
    !options.buildId ||
    !options.buildId.trim() ||
    options.buildId.length > 256 ||
    /[\u0000-\u001f\u007f]/u.test(options.buildId)
  ) {
    throw new RenderReviewError(
      "invalid-build-id",
      "--build-id is required, must be 1-256 characters, and cannot contain control characters.",
      { value: options.buildId },
    );
  }
  if (
    options.captureManifest === null &&
    options.routes.length > MAX_DEFAULT_ROUTES - 1
  ) {
    throw new RenderReviewError(
      "too-many-routes",
      `At most ${MAX_DEFAULT_ROUTES - 1} additional routes may be captured with the ${PROFILES.length}-profile default while preserving the ${MAX_CAPTURE_PLANS}-capture limit.`,
      {
        count: options.routes.length,
        maximum: MAX_DEFAULT_ROUTES - 1,
        default_profile_count: PROFILES.length,
        maximum_captures: MAX_CAPTURE_PLANS,
      },
    );
  }
  if (options.routes.some((route) => route.length > 2048)) {
    throw new RenderReviewError(
      "route-too-long",
      "Each additional route is limited to 2048 characters.",
      {},
    );
  }
  if (
    options.captureManifest &&
    (!options.captureManifest.trim() ||
      options.captureManifest.length > 4096 ||
      /[\u0000-\u001f\u007f]/u.test(options.captureManifest))
  ) {
    throw new RenderReviewError(
      "capture-manifest-path-invalid",
      "--capture-manifest must be a non-empty path of at most 4096 characters without control characters.",
      {},
    );
  }
  if (options.limits.source_file_bytes > options.limits.source_bytes) {
    throw new RenderReviewError(
      "invalid-limit-combination",
      "--max-source-file-bytes cannot exceed --max-source-bytes.",
      {
        source_file_bytes: options.limits.source_file_bytes,
        source_bytes: options.limits.source_bytes,
      },
    );
  }
  if (options.limits.screenshot_bytes > options.limits.total_artifact_bytes) {
    throw new RenderReviewError(
      "invalid-limit-combination",
      "--max-screenshot-bytes cannot exceed --max-artifact-bytes.",
      {
        screenshot_bytes: options.limits.screenshot_bytes,
        artifact_bytes: options.limits.total_artifact_bytes,
      },
    );
  }
  if (
    options.limits.total_artifact_bytes <
    options.limits.report_bytes + ARTIFACT_METADATA_RESERVE_BYTES
  ) {
    throw new RenderReviewError(
      "invalid-limit-combination",
      `--max-artifact-bytes must reserve at least ${ARTIFACT_METADATA_RESERVE_BYTES} bytes beyond --max-report-bytes for the contact sheet and marker.`,
      {
        artifact_bytes: options.limits.total_artifact_bytes,
        report_bytes: options.limits.report_bytes,
        required_reserve_bytes: ARTIFACT_METADATA_RESERVE_BYTES,
      },
    );
  }
  return options;
}

function normalizePathForComparison(value) {
  const resolved = path.resolve(value);
  return process.platform === "win32" ? resolved.toLowerCase() : resolved;
}

function sha256Value(value) {
  return createHash("sha256").update(value).digest("hex");
}

function sanitizeUrl(raw) {
  if (typeof raw !== "string" || !raw) return "";
  if (raw.startsWith("data:")) return "data:[payload omitted]";
  if (raw.startsWith("blob:")) {
    const nested = sanitizeUrl(raw.slice(5));
    return nested ? `blob:${nested}` : "blob:[origin omitted]";
  }
  try {
    const parsed = new URL(raw);
    parsed.username = "";
    parsed.password = "";
    parsed.search = "";
    parsed.hash = "";
    if (parsed.protocol === "file:") return "local-snapshot:[file URL omitted]";
    return parsed.href;
  } catch {
    return raw
      .replace(/^[^?#]*[?#].*$/u, (match) => match.split(/[?#]/u, 1)[0])
      .replace(/\/\/[^/@\s]+@/u, "//[userinfo-omitted]@")
      .slice(0, 500);
  }
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
}

function sanitizeDiagnosticText(raw, extraSensitivePaths = []) {
  let value = String(raw ?? "");
  const sensitivePaths = [
    ...extraSensitivePaths,
    os.homedir(),
    process.cwd(),
    PACKAGE_ROOT,
  ]
    .filter(Boolean)
    .map((item) => path.resolve(item))
    .sort((left, right) => right.length - left.length);
  for (const sensitivePath of sensitivePaths) {
    value = value.replace(
      new RegExp(escapeRegExp(sensitivePath), process.platform === "win32" ? "giu" : "gu"),
      "[absolute-path-omitted]",
    );
  }
  value = value.replace(
    /https?:\/\/[^\s"'<>]+/giu,
    (match) => sanitizeUrl(match.replace(/[),.;]+$/u, "")),
  );
  value = value
    .replace(/\b[A-Za-z]:[\\/][^\s"'<>|]+/gu, "[absolute-path-omitted]")
    .replace(/\\\\[^\\\s]+\\[^ \t\r\n"'<>|]+/gu, "[absolute-path-omitted]")
    .replace(
      /(^|[\s("'=])\/(?:Users|home|private|tmp|var|etc|opt|root|workspace|mnt)\/[^\s"'<>)]*/gmu,
      "$1[absolute-path-omitted]",
    )
    .replace(
      /\b(?:authorization|proxy-authorization)\s*[:=]\s*(?:bearer\s+)?[^\s,;]+/giu,
      "[credential-omitted]",
    )
    .replace(
      /\b(access[_-]?token|api[_-]?key|auth|credential|password|secret|signature|sig|token)\s*[=:]\s*[^&\s,;]+/giu,
      "$1=[sensitive-value-omitted]",
    )
    .replace(
      /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]{10,})?\b/gu,
      "[token-omitted]",
    )
    .replace(
      /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/giu,
      "[email-omitted]",
    );
  return value;
}

function sanitizeDetails(value, sensitivePaths = []) {
  if (Array.isArray(value)) {
    return value.slice(0, 100).map((item) => sanitizeDetails(item, sensitivePaths));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .slice(0, 100)
        .map(([key, item]) => [key, sanitizeDetails(item, sensitivePaths)]),
    );
  }
  if (typeof value === "string") {
    return sanitizeDiagnosticText(value, sensitivePaths).slice(0, 2000);
  }
  return value;
}

function isInside(candidate, parent) {
  const normalizedCandidate = normalizePathForComparison(candidate);
  const normalizedParent = normalizePathForComparison(parent);
  return (
    normalizedCandidate === normalizedParent ||
    normalizedCandidate.startsWith(`${normalizedParent}${path.sep}`)
  );
}

async function pathExists(value) {
  try {
    await access(value);
    return true;
  } catch {
    return false;
  }
}

async function assertNoSymlinkComponents(absolutePath, allowMissingTail = false) {
  const resolved = path.resolve(absolutePath);
  const parsed = path.parse(resolved);
  const relative = resolved.slice(parsed.root.length);
  const parts = relative.split(path.sep).filter(Boolean);
  let current = parsed.root;

  for (let index = 0; index < parts.length; index += 1) {
    current = path.join(current, parts[index]);
    try {
      const info = await lstat(current);
      if (info.isSymbolicLink()) {
        throw new RenderReviewError(
          "unsafe-symlink-path",
          "Local serving and output paths cannot traverse symbolic links or junctions.",
          { path: current },
        );
      }
    } catch (error) {
      if (
        error instanceof RenderReviewError ||
        !allowMissingTail ||
        error?.code !== "ENOENT"
      ) {
        throw error;
      }
      return;
    }
  }
}

async function classifyTarget(rawTarget) {
  let parsed = null;
  const windowsPath =
    /^[A-Za-z]:[\\/]/u.test(rawTarget) || rawTarget.startsWith("\\\\");
  if (!windowsPath) {
    try {
      parsed = new URL(rawTarget);
    } catch {
      parsed = null;
    }
  }

  if (parsed) {
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      if (parsed.username || parsed.password) {
        throw new RenderReviewError(
          "unsafe-target-credentials",
          "Target URLs cannot contain embedded credentials.",
          { target: rawTarget },
        );
      }
      return {
        kind: "remote-url",
        input: sanitizeUrl(rawTarget),
        url: parsed.href,
        localPath: null,
        sourceBoundary: null,
      };
    }
    if (parsed.protocol === "file:") {
      const localPath = path.resolve(fileURLToPath(parsed));
      await assertNoSymlinkComponents(localPath);
      const info = await lstat(localPath).catch(() => null);
      if (!info?.isFile()) {
        throw new RenderReviewError(
          "invalid-file-target",
          "The file URL must identify an existing regular file.",
          { target: rawTarget, path: localPath },
        );
      }
      if (![".html", ".htm"].includes(path.extname(localPath).toLowerCase())) {
        throw new RenderReviewError(
          "invalid-file-target",
          "A file URL target must identify an HTML file.",
          { target: path.basename(localPath) },
        );
      }
      return {
        kind: "local-file",
        input: `local-file:${path.basename(localPath)}`,
        url: null,
        localPath,
        sourceBoundary: path.dirname(localPath),
      };
    }
    throw new RenderReviewError(
      "invalid-target-scheme",
      "TARGET must use http, https, or file, or identify a local directory.",
      { target: rawTarget, scheme: parsed.protocol },
    );
  }

  const localPath = path.resolve(rawTarget);
  await assertNoSymlinkComponents(localPath);
  const info = await lstat(localPath).catch(() => null);
  if (!info) {
    throw new RenderReviewError(
      "target-not-found",
      "The local target does not exist.",
      { target: rawTarget, path: localPath },
    );
  }
  if (info.isDirectory()) {
    return {
      kind: "local-directory",
      input: "local-directory:[source path omitted]",
      url: null,
      localPath,
      sourceBoundary: localPath,
    };
  }
  if (info.isFile()) {
    if (![".html", ".htm"].includes(path.extname(localPath).toLowerCase())) {
      throw new RenderReviewError(
        "invalid-file-target",
        "A local file target must be an HTML file. Use an explicit public/build directory for other assets.",
        { target: path.basename(localPath) },
      );
    }
    return {
      kind: "local-file",
      input: `local-file:${path.basename(localPath)}`,
      url: null,
      localPath,
      sourceBoundary: path.dirname(localPath),
    };
  }
  throw new RenderReviewError(
    "invalid-local-target",
    "The local target must be a regular file or directory.",
    { target: rawTarget, path: localPath },
  );
}

function protectedOutputRoots() {
  const home = os.homedir();
  const oneDriveRoots = [
    process.env.OneDrive,
    process.env.OneDriveConsumer,
    process.env.OneDriveCommercial,
  ].filter(Boolean);
  const broadRoots = [
    path.parse(path.resolve(home)).root,
    home,
    os.tmpdir(),
    path.join(home, "Desktop"),
    path.join(home, "Documents"),
    path.join(home, "Downloads"),
    ...oneDriveRoots,
    ...oneDriveRoots.flatMap((root) => [
      path.join(root, "Desktop"),
      path.join(root, "Documents"),
      path.join(root, "Pictures"),
    ]),
  ].filter(Boolean);
  const systemTrees = [
    process.env.SystemRoot,
    process.env.WINDIR,
    process.env.PROGRAMDATA,
    process.env.PROGRAMFILES,
    process.env["PROGRAMFILES(X86)"],
    "/bin",
    "/boot",
    "/dev",
    "/etc",
    "/lib",
    "/lib64",
    "/opt",
    "/proc",
    "/sbin",
    "/sys",
    "/usr",
    "/var",
  ].filter(Boolean);
  const workspaceTrees = [PACKAGE_ROOT];
  if (
    normalizePathForComparison(process.cwd()) !==
      normalizePathForComparison(home) &&
    normalizePathForComparison(process.cwd()) !==
      normalizePathForComparison(path.parse(process.cwd()).root)
  ) {
    workspaceTrees.push(process.cwd());
  }
  return { broadRoots, systemTrees, workspaceTrees };
}

function assertOutputSeparation(output, target) {
  const normalized = normalizePathForComparison(output);
  const { broadRoots, systemTrees, workspaceTrees } = protectedOutputRoots();
  for (const protectedRoot of broadRoots) {
    const resolvedProtected = path.resolve(protectedRoot);
    if (isInside(resolvedProtected, output)) {
      throw new RenderReviewError(
        "unsafe-output",
        "The output cannot equal or contain a filesystem, profile, workspace, or common user-data root.",
        { output: "[output path omitted]", protected_class: "broad-root" },
      );
    }
  }
  for (const workspaceTree of workspaceTrees) {
    const resolvedWorkspace = path.resolve(workspaceTree);
    if (
      isInside(output, resolvedWorkspace) ||
      isInside(resolvedWorkspace, output)
    ) {
      throw new RenderReviewError(
        "unsafe-output",
        "The output cannot be inside, equal to, or contain the active workspace or package tree.",
        { output: "[output path omitted]", protected_class: "workspace-tree" },
      );
    }
  }
  for (const systemTree of systemTrees) {
    const resolvedSystem = path.resolve(systemTree);
    if (isInside(output, resolvedSystem) || isInside(resolvedSystem, output)) {
      throw new RenderReviewError(
        "unsafe-output",
        "The output cannot be inside, equal to, or contain an operating-system or program tree.",
        { output: "[output path omitted]", protected_class: "system-tree" },
      );
    }
  }
  if (target.sourceBoundary) {
    if (
      isInside(output, target.sourceBoundary) ||
      isInside(target.sourceBoundary, output)
    ) {
      throw new RenderReviewError(
        "output-source-overlap",
        "The output must be outside the local source and cannot contain or be contained by it.",
        {
          output: "[output path omitted]",
          source: "[source path omitted]",
        },
      );
    }
  }
  if (normalized === normalizePathForComparison(path.parse(output).root)) {
    throw new RenderReviewError(
      "unsafe-output",
      "A filesystem root cannot be used as output.",
      { output: "[output path omitted]" },
    );
  }
}

async function readBoundedJson(filePath, maximumBytes, code) {
  const info = await lstat(filePath).catch(() => null);
  if (!info?.isFile() || info.isSymbolicLink() || info.size > maximumBytes) {
    throw new RenderReviewError(
      code,
      "Ownership metadata is missing, not a regular file, symbolic, or exceeds its size limit.",
      { file: path.basename(filePath), maximum_bytes: maximumBytes },
    );
  }
  try {
    return JSON.parse(await readFile(filePath, "utf8"));
  } catch (error) {
    throw new RenderReviewError(
      code,
      "Ownership metadata is not valid JSON.",
      {
        file: path.basename(filePath),
        cause: sanitizeDiagnosticText(error?.message ?? error),
      },
    );
  }
}

function hasExactKeys(value, expected) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const actual = Object.keys(value).sort();
  return (
    actual.length === expected.length &&
    expected.slice().sort().every((key, index) => key === actual[index])
  );
}

function validManifestText(value, minimum, maximum) {
  return (
    typeof value === "string" &&
    value.length >= minimum &&
    value.length <= maximum &&
    !/[\u0000-\u001f\u007f]/u.test(value)
  );
}

function captureManifestInvalid(message, details = {}) {
  throw new RenderReviewError(
    "capture-manifest-invalid",
    message,
    details,
  );
}

function normalizeManifestProfile(raw, index) {
  const keys = [
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
  ];
  if (!hasExactKeys(raw, keys)) {
    captureManifestInvalid(
      "Each capture profile must contain only the documented v1 fields.",
      { profile_index: index },
    );
  }
  if (!/^[a-z][a-z0-9-]{0,47}$/u.test(raw.id ?? "")) {
    captureManifestInvalid(
      "Profile IDs must be 1-48 lowercase letters, digits, or hyphens and start with a letter.",
      { profile_index: index },
    );
  }
  if (!validManifestText(raw.label, 1, 80)) {
    captureManifestInvalid(
      "Profile labels must be 1-80 printable characters.",
      { profile_index: index },
    );
  }
  if (
    !hasExactKeys(raw.viewport, ["width", "height", "device_scale_factor"]) ||
    !Number.isInteger(raw.viewport.width) ||
    raw.viewport.width < 240 ||
    raw.viewport.width > 3840 ||
    !Number.isInteger(raw.viewport.height) ||
    raw.viewport.height < 240 ||
    raw.viewport.height > 2160 ||
    typeof raw.viewport.device_scale_factor !== "number" ||
    !Number.isFinite(raw.viewport.device_scale_factor) ||
    raw.viewport.device_scale_factor < 1 ||
    raw.viewport.device_scale_factor > 3
  ) {
    captureManifestInvalid(
      "Profile viewports require width 240-3840, height 240-2160, and device scale factor 1-3.",
      { profile_index: index },
    );
  }
  if (typeof raw.is_mobile !== "boolean" || typeof raw.has_touch !== "boolean") {
    captureManifestInvalid(
      "Profile is_mobile and has_touch values must be booleans.",
      { profile_index: index },
    );
  }
  if (raw.is_mobile && !raw.has_touch) {
    captureManifestInvalid(
      "A mobile-emulation profile must enable touch to keep its reported input contract honest.",
      { profile_index: index },
    );
  }
  const expectedModalities = raw.has_touch
    ? ["touch", "keyboard"]
    : ["keyboard", "pointer"];
  const expectedPointer = raw.has_touch ? "coarse" : "fine";
  const expectedHover = raw.has_touch ? "none" : "hover";
  if (
    !Array.isArray(raw.input_modalities) ||
    raw.input_modalities.length !== expectedModalities.length ||
    new Set(raw.input_modalities).size !== raw.input_modalities.length ||
    !expectedModalities.every((item) => raw.input_modalities.includes(item)) ||
    raw.pointer !== expectedPointer ||
    raw.hover !== expectedHover
  ) {
    captureManifestInvalid(
      "Profile pointer, hover, and input modalities must agree with has_touch.",
      { profile_index: index },
    );
  }
  if (!["light", "dark"].includes(raw.color_scheme)) {
    captureManifestInvalid("Profile color_scheme must be light or dark.", {
      profile_index: index,
    });
  }
  if (!["no-preference", "reduce"].includes(raw.reduced_motion)) {
    captureManifestInvalid(
      "Profile reduced_motion must be no-preference or reduce.",
      { profile_index: index },
    );
  }
  if (!["none", "active"].includes(raw.forced_colors)) {
    captureManifestInvalid(
      "Profile forced_colors must be none or active.",
      { profile_index: index },
    );
  }
  if (!["none", "wcag-1.4.12"].includes(raw.text_spacing)) {
    captureManifestInvalid(
      "Profile text_spacing must be none or wcag-1.4.12.",
      { profile_index: index },
    );
  }
  if (!["none", "200-percent", "400-percent"].includes(raw.zoom)) {
    captureManifestInvalid(
      "Profile zoom must be none, 200-percent, or 400-percent.",
      { profile_index: index },
    );
  }
  return {
    id: raw.id,
    label: raw.label,
    viewport: {
      width: raw.viewport.width,
      height: raw.viewport.height,
      device_scale_factor: raw.viewport.device_scale_factor,
    },
    is_mobile: raw.is_mobile,
    has_touch: raw.has_touch,
    input_modalities: expectedModalities,
    pointer: expectedPointer,
    hover: expectedHover,
    color_scheme: raw.color_scheme,
    reduced_motion: raw.reduced_motion,
    forced_colors: raw.forced_colors,
    text_spacing: raw.text_spacing,
    zoom: raw.zoom,
  };
}

function normalizeManifestInteraction(raw, scenarioIndex, actionIndex) {
  const action = raw?.action;
  const needsValue = ["fill", "select"].includes(action);
  const expectedKeys = needsValue
    ? ["action", "selector", "value"]
    : ["action", "selector"];
  if (
    !["click", "focus", "fill", "select", "check"].includes(action) ||
    !hasExactKeys(raw, expectedKeys)
  ) {
    captureManifestInvalid(
      "Interactions allow only click, focus, fill, select, or check with their documented fields.",
      { scenario_index: scenarioIndex, action_index: actionIndex },
    );
  }
  if (
    !validManifestText(raw.selector, 1, MAX_SELECTOR_LENGTH) ||
    sanitizeDiagnosticText(raw.selector) !== raw.selector
  ) {
    captureManifestInvalid(
      `Interaction selectors must be 1-${MAX_SELECTOR_LENGTH} printable, non-sensitive characters.`,
      { scenario_index: scenarioIndex, action_index: actionIndex },
    );
  }
  if (
    needsValue &&
    (typeof raw.value !== "string" ||
      raw.value.length > MAX_INTERACTION_VALUE_LENGTH ||
      /[\u0000\u000b\u000c\u007f]/u.test(raw.value))
  ) {
    captureManifestInvalid(
      `Interaction values must be strings of at most ${MAX_INTERACTION_VALUE_LENGTH} characters without unsafe controls.`,
      { scenario_index: scenarioIndex, action_index: actionIndex },
    );
  }
  return needsValue
    ? { action, selector: raw.selector, value: raw.value }
    : { action, selector: raw.selector };
}

function normalizeManifestScenario(raw, index, profileIds, targetKind) {
  const keys = [
    "id",
    "label",
    "route",
    "route_label",
    "state_label",
    "profile_ids",
    "interactions",
  ];
  if (!hasExactKeys(raw, keys)) {
    captureManifestInvalid(
      "Each scenario must contain only the documented v1 fields.",
      { scenario_index: index },
    );
  }
  if (!/^[a-z][a-z0-9-]{0,47}$/u.test(raw.id ?? "")) {
    captureManifestInvalid(
      "Scenario IDs must be 1-48 lowercase letters, digits, or hyphens and start with a letter.",
      { scenario_index: index },
    );
  }
  for (const [field, value] of [
    ["label", raw.label],
    ["route_label", raw.route_label],
    ["state_label", raw.state_label],
  ]) {
    if (!validManifestText(value, 1, 80)) {
      captureManifestInvalid(
        `Scenario ${field} must be 1-80 printable characters.`,
        { scenario_index: index },
      );
    }
  }
  if (
    raw.route !== null &&
    (!validManifestText(raw.route, 1, 2048) || raw.route.includes("\\"))
  ) {
    captureManifestInvalid(
      "Scenario route must be null or a printable route of at most 2048 characters without backslashes.",
      { scenario_index: index },
    );
  }
  if (
    !Array.isArray(raw.profile_ids) ||
    raw.profile_ids.length < 1 ||
    raw.profile_ids.length > MAX_CAPTURE_PROFILES ||
    new Set(raw.profile_ids).size !== raw.profile_ids.length ||
    raw.profile_ids.some((id) => !profileIds.has(id))
  ) {
    captureManifestInvalid(
      "Scenario profile_ids must be a non-empty unique subset of declared profiles.",
      { scenario_index: index },
    );
  }
  if (
    !Array.isArray(raw.interactions) ||
    raw.interactions.length > MAX_INTERACTIONS_PER_SCENARIO
  ) {
    captureManifestInvalid(
      `A scenario may contain at most ${MAX_INTERACTIONS_PER_SCENARIO} interactions.`,
      { scenario_index: index },
    );
  }
  const interactions = raw.interactions.map((interaction, actionIndex) =>
    normalizeManifestInteraction(interaction, index, actionIndex),
  );
  if (
    targetKind === "remote-url" &&
    interactions.some((interaction) => interaction.action !== "focus")
  ) {
    throw new RenderReviewError(
      "remote-interaction-unsupported",
      "Remote capture manifests may use focus only; state-changing actions are limited to frozen local targets.",
      { scenario_index: index },
    );
  }
  return {
    id: raw.id,
    label: raw.label,
    route: raw.route,
    route_label: raw.route_label,
    state_label: raw.state_label,
    profile_ids: [...raw.profile_ids],
    interactions,
  };
}

async function loadCaptureManifest(manifestValue, target, outputPath) {
  if (!manifestValue) return null;
  const manifestPath = path.resolve(manifestValue);
  await assertNoSymlinkComponents(manifestPath);
  if (
    (target.sourceBoundary && isInside(manifestPath, target.sourceBoundary)) ||
    isInside(manifestPath, outputPath)
  ) {
    throw new RenderReviewError(
      "capture-manifest-path-overlap",
      "The capture manifest must be outside the local public source and output tree.",
      { file: path.basename(manifestPath) },
    );
  }
  const beforeInfo = await lstat(manifestPath).catch(() => null);
  if (
    !beforeInfo?.isFile() ||
    beforeInfo.isSymbolicLink() ||
    beforeInfo.size < 2 ||
    beforeInfo.size > MAX_CAPTURE_MANIFEST_BYTES
  ) {
    throw new RenderReviewError(
      "capture-manifest-invalid",
      `The capture manifest must be a regular JSON file between 2 and ${MAX_CAPTURE_MANIFEST_BYTES} bytes.`,
      { file: path.basename(manifestPath) },
    );
  }
  const beforeIdentity = stableFileIdentity(beforeInfo);
  const payload = await readFile(manifestPath);
  const afterInfo = await lstat(manifestPath).catch(() => null);
  if (
    !afterInfo?.isFile() ||
    afterInfo.isSymbolicLink() ||
    !sameFileIdentity(beforeIdentity, stableFileIdentity(afterInfo))
  ) {
    throw new RenderReviewError(
      "capture-manifest-changed",
      "The capture manifest changed while it was being read.",
      { file: path.basename(manifestPath) },
    );
  }
  let raw;
  try {
    raw = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(payload));
  } catch {
    throw new RenderReviewError(
      "capture-manifest-invalid",
      "The capture manifest is not valid UTF-8 JSON.",
      { file: path.basename(manifestPath) },
    );
  }
  if (
    !hasExactKeys(raw, ["schema_version", "profiles", "scenarios"]) ||
    raw.schema_version !== 1 ||
    !Array.isArray(raw.profiles) ||
    raw.profiles.length < 1 ||
    raw.profiles.length > MAX_CAPTURE_PROFILES ||
    !Array.isArray(raw.scenarios) ||
    raw.scenarios.length < 1 ||
    raw.scenarios.length > MAX_CAPTURE_SCENARIOS
  ) {
    captureManifestInvalid(
      `Capture manifest v1 requires 1-${MAX_CAPTURE_PROFILES} profiles and 1-${MAX_CAPTURE_SCENARIOS} scenarios with no extra top-level fields.`,
      {},
    );
  }
  const profiles = raw.profiles.map(normalizeManifestProfile);
  const profileIds = new Set(profiles.map((profile) => profile.id));
  if (profileIds.size !== profiles.length) {
    captureManifestInvalid("Profile IDs must be unique.", {});
  }
  const scenarios = raw.scenarios.map((scenario, index) =>
    normalizeManifestScenario(scenario, index, profileIds, target.kind),
  );
  if (new Set(scenarios.map((scenario) => scenario.id)).size !== scenarios.length) {
    captureManifestInvalid("Scenario IDs must be unique.", {});
  }
  const interactionCount = scenarios.reduce(
    (total, scenario) => total + scenario.interactions.length,
    0,
  );
  const captureCount = scenarios.reduce(
    (total, scenario) => total + scenario.profile_ids.length,
    0,
  );
  if (interactionCount > MAX_INTERACTIONS_TOTAL) {
    captureManifestInvalid(
      `The manifest may contain at most ${MAX_INTERACTIONS_TOTAL} total interactions.`,
      { interaction_count: interactionCount },
    );
  }
  if (captureCount > MAX_CAPTURE_PLANS) {
    captureManifestInvalid(
      `The manifest may produce at most ${MAX_CAPTURE_PLANS} captures.`,
      { capture_count: captureCount },
    );
  }
  return {
    path: manifestPath,
    file_identity: beforeIdentity,
    schema_version: 1,
    sha256: sha256Value(payload),
    bytes: payload.length,
    profiles,
    scenarios,
  };
}

async function verifyCaptureManifest(manifest) {
  if (!manifest) return;
  const info = await lstat(manifest.path).catch(() => null);
  if (
    !info?.isFile() ||
    info.isSymbolicLink() ||
    !sameFileIdentity(manifest.file_identity, stableFileIdentity(info))
  ) {
    throw new RenderReviewError(
      "capture-manifest-changed",
      "The capture manifest changed during rendered review.",
      { file: path.basename(manifest.path) },
    );
  }
  const payload = await readFile(manifest.path);
  if (
    payload.length !== manifest.bytes ||
    sha256Value(payload) !== manifest.sha256
  ) {
    throw new RenderReviewError(
      "capture-manifest-changed",
      "The capture manifest content changed during rendered review.",
      { file: path.basename(manifest.path) },
    );
  }
}

async function validateOwnershipMarker(output) {
  const markerPath = path.join(output, ".design-dna-render-review.json");
  const marker = await readBoundedJson(
    markerPath,
    MAX_OWNERSHIP_MARKER_BYTES,
    "output-not-owned",
  );
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
    marker.schema_version !== SCHEMA_VERSION ||
    marker.marker_type !== MARKER_TYPE ||
    !hasExactKeys(marker.tool, ["name", "version"]) ||
    marker.tool.name !== TOOL_NAME ||
    marker.tool.version !== TOOL_VERSION ||
    !hasExactKeys(marker.output_identity, ["id", "path_sha256"]) ||
    !/^[0-9a-f]{64}$/u.test(marker.output_identity.id ?? "") ||
    !/^[0-9a-f]{64}$/u.test(marker.output_identity.path_sha256 ?? "") ||
    !hasExactKeys(marker.report, ["path", "sha256", "bytes"]) ||
    marker.report.path !== "render-review.json" ||
    !/^[0-9a-f]{64}$/u.test(marker.report.sha256 ?? "") ||
    !Number.isSafeInteger(marker.report.bytes) ||
    marker.report.bytes < 1 ||
    marker.report.bytes > HARD_LIMITS.report_bytes ||
    !/^[0-9a-f]{64}$/u.test(marker.build_id_sha256 ?? "") ||
    !Number.isFinite(Date.parse(marker.created_at ?? ""))
  ) {
    throw new RenderReviewError(
      "output-marker-invalid",
      "The existing ownership marker does not match the strict Design DNA marker contract.",
      { marker: ".design-dna-render-review.json" },
    );
  }
  const expectedPathHash = sha256Value(normalizePathForComparison(output));
  if (marker.output_identity.path_sha256 !== expectedPathHash) {
    throw new RenderReviewError(
      "output-marker-path-mismatch",
      "The ownership marker is bound to a different output path.",
      { marker: ".design-dna-render-review.json" },
    );
  }
  const reportPath = path.join(output, marker.report.path);
  const reportInfo = await lstat(reportPath).catch(() => null);
  const reportBytes =
    reportInfo?.isFile() &&
    !reportInfo.isSymbolicLink() &&
    reportInfo.size <= HARD_LIMITS.report_bytes
      ? await readFile(reportPath).catch(() => null)
      : null;
  if (
    !reportBytes ||
    reportBytes.length > HARD_LIMITS.report_bytes ||
    reportBytes.length !== marker.report.bytes ||
    sha256Value(reportBytes) !== marker.report.sha256
  ) {
    throw new RenderReviewError(
      "output-report-identity-mismatch",
      "The existing report is missing, oversized, or does not match its ownership marker.",
      { report: marker.report.path },
    );
  }
  let report;
  try {
    report = JSON.parse(reportBytes.toString("utf8"));
  } catch {
    throw new RenderReviewError(
      "output-report-invalid",
      "The existing ownership report is not valid JSON.",
      { report: marker.report.path },
    );
  }
  if (
    report.schema_version !== SCHEMA_VERSION ||
    report.tool?.name !== TOOL_NAME ||
    report.tool?.version !== marker.tool.version ||
    report.tool?.report_schema !== "render-review.schema.json" ||
    report.review_required !== true ||
    report.automatic_visual_quality_pass !== false ||
    report.output_identity?.id !== marker.output_identity.id ||
    report.output_identity?.path_sha256 !== marker.output_identity.path_sha256 ||
    report.artifacts?.report?.path !== marker.report.path ||
    report.artifacts?.marker?.path !== ".design-dna-render-review.json" ||
    sha256Value(String(report.build?.id ?? "")) !== marker.build_id_sha256
  ) {
    throw new RenderReviewError(
      "output-report-identity-mismatch",
      "The existing report and ownership marker identities do not agree.",
      { report: marker.report.path },
    );
  }
  return marker;
}

async function directoryIdentity(directory) {
  const info = await lstat(directory);
  if (!info.isDirectory() || info.isSymbolicLink()) {
    throw new RenderReviewError(
      "output-identity-changed",
      "The output is no longer a regular directory.",
      { output: "[output path omitted]" },
    );
  }
  return {
    device: String(info.dev),
    inode: String(info.ino),
    birthtime_ms: Math.round(info.birthtimeMs),
    canonical_path: normalizePathForComparison(await realpath(directory)),
  };
}

function sameDirectoryIdentity(left, right, includePath = true) {
  return (
    left.device === right.device &&
    left.inode === right.inode &&
    left.birthtime_ms === right.birthtime_ms &&
    (!includePath || left.canonical_path === right.canonical_path)
  );
}

function stableFileIdentity(info) {
  return {
    device: String(info.dev),
    inode: String(info.ino),
    birthtime_ms: Math.round(info.birthtimeMs),
    size: info.size,
    mtime_ms: Math.round(info.mtimeMs),
  };
}

function sameFileIdentity(left, right) {
  return (
    left.device === right.device &&
    left.inode === right.inode &&
    left.birthtime_ms === right.birthtime_ms &&
    left.size === right.size &&
    left.mtime_ms === right.mtime_ms
  );
}

async function hashStableOwnedFile(filePath, maximumBytes) {
  const beforePathInfo = await lstat(filePath);
  if (!beforePathInfo.isFile() || beforePathInfo.isSymbolicLink()) {
    throw new RenderReviewError(
      "output-tree-unsafe",
      "The owned output contains a non-regular or symbolic file.",
      { file: "[owned output relative path omitted]" },
    );
  }
  if (beforePathInfo.size > maximumBytes) {
    throw new RenderReviewError(
      "output-tree-limit-exceeded",
      "The owned output exceeds the bounded replacement-verification byte limit.",
      {
        bytes: beforePathInfo.size,
        maximum_remaining_bytes: maximumBytes,
        maximum_bytes: OUTPUT_TREE_LIMITS.bytes,
      },
    );
  }
  const handle = await open(filePath, "r");
  try {
    const openedInfo = await handle.stat();
    if (
      !openedInfo.isFile() ||
      !sameFileIdentity(
        stableFileIdentity(beforePathInfo),
        stableFileIdentity(openedInfo),
      )
    ) {
      throw new RenderReviewError(
        "output-content-changed",
        "The owned output changed while its replacement boundary was being verified.",
        { output: "[output path omitted]" },
      );
    }
    const hash = createHash("sha256");
    const buffer = Buffer.allocUnsafe(1024 * 1024);
    let bytes = 0;
    while (true) {
      const result = await handle.read(buffer, 0, buffer.length, bytes);
      if (result.bytesRead === 0) break;
      bytes += result.bytesRead;
      if (bytes > maximumBytes) {
        throw new RenderReviewError(
          "output-tree-limit-exceeded",
          "The owned output exceeds the bounded replacement-verification byte limit.",
          {
            bytes,
            maximum_bytes: OUTPUT_TREE_LIMITS.bytes,
          },
        );
      }
      hash.update(buffer.subarray(0, result.bytesRead));
    }
    const afterHandleInfo = await handle.stat();
    const afterPathInfo = await lstat(filePath).catch(() => null);
    if (
      !afterPathInfo ||
      !afterPathInfo.isFile() ||
      afterPathInfo.isSymbolicLink() ||
      bytes !== openedInfo.size ||
      !sameFileIdentity(
        stableFileIdentity(openedInfo),
        stableFileIdentity(afterHandleInfo),
      ) ||
      !sameFileIdentity(
        stableFileIdentity(openedInfo),
        stableFileIdentity(afterPathInfo),
      )
    ) {
      throw new RenderReviewError(
        "output-content-changed",
        "The owned output changed while its replacement boundary was being verified.",
        { output: "[output path omitted]" },
      );
    }
    return { bytes, sha256: hash.digest("hex") };
  } finally {
    await handle.close();
  }
}

async function fingerprintOwnedOutput(output) {
  const canonicalRoot = normalizePathForComparison(await realpath(output));
  const entries = [];
  let fileCount = 0;
  let directoryCount = 0;
  let totalBytes = 0;

  async function walk(directory, relativeDirectory = "", depth = 0) {
    if (depth > OUTPUT_TREE_LIMITS.depth) {
      throw new RenderReviewError(
        "output-tree-limit-exceeded",
        "The owned output exceeds the bounded replacement-verification depth limit.",
        { depth, maximum_depth: OUTPUT_TREE_LIMITS.depth },
      );
    }
    const directoryBefore = await lstat(directory);
    if (!directoryBefore.isDirectory() || directoryBefore.isSymbolicLink()) {
      throw new RenderReviewError(
        "output-tree-unsafe",
        "The owned output contains a non-regular directory or reparse point.",
        { output: "[output path omitted]" },
      );
    }
    const canonicalDirectory = normalizePathForComparison(await realpath(directory));
    if (
      canonicalDirectory !== canonicalRoot &&
      !isInside(canonicalDirectory, canonicalRoot)
    ) {
      throw new RenderReviewError(
        "output-tree-unsafe",
        "The owned output resolves outside its replacement boundary.",
        { output: "[output path omitted]" },
      );
    }
    const children = await readdir(directory, { withFileTypes: true });
    children.sort((left, right) => left.name.localeCompare(right.name, "en"));
    for (const child of children) {
      const relative = relativeDirectory
        ? path.join(relativeDirectory, child.name)
        : child.name;
      const portable = relative.split(path.sep).join("/");
      const absolute = path.join(directory, child.name);
      const info = await lstat(absolute);
      if (child.isSymbolicLink() || info.isSymbolicLink()) {
        throw new RenderReviewError(
          "output-tree-unsafe",
          "The owned output contains a symbolic link or junction.",
          { path: portable },
        );
      }
      if (info.isDirectory()) {
        directoryCount += 1;
        if (directoryCount > OUTPUT_TREE_LIMITS.directories) {
          throw new RenderReviewError(
            "output-tree-limit-exceeded",
            "The owned output exceeds the bounded replacement-verification directory limit.",
            {
              directories: directoryCount,
              maximum_directories: OUTPUT_TREE_LIMITS.directories,
            },
          );
        }
        entries.push({ path: portable, type: "directory" });
        await walk(absolute, relative, depth + 1);
        continue;
      }
      if (!child.isFile() || !info.isFile()) {
        throw new RenderReviewError(
          "output-tree-unsafe",
          "The owned output contains a non-regular filesystem entry.",
          { path: portable },
        );
      }
      fileCount += 1;
      if (fileCount > OUTPUT_TREE_LIMITS.files) {
        throw new RenderReviewError(
          "output-tree-limit-exceeded",
          "The owned output exceeds the bounded replacement-verification file limit.",
          { files: fileCount, maximum_files: OUTPUT_TREE_LIMITS.files },
        );
      }
      const remainingBytes = OUTPUT_TREE_LIMITS.bytes - totalBytes;
      const hashed = await hashStableOwnedFile(absolute, remainingBytes);
      totalBytes += hashed.bytes;
      entries.push({
        path: portable,
        type: "file",
        bytes: hashed.bytes,
        sha256: hashed.sha256,
      });
    }
    const directoryAfter = await lstat(directory).catch(() => null);
    const afterRealPath = directoryAfter
      ? await realpath(directory).catch(() => null)
      : null;
    const canonicalAfter = afterRealPath
      ? normalizePathForComparison(afterRealPath)
      : null;
    if (
      !directoryAfter ||
      !directoryAfter.isDirectory() ||
      directoryAfter.isSymbolicLink() ||
      canonicalAfter !== canonicalDirectory ||
      !sameFileIdentity(
        stableFileIdentity(directoryBefore),
        stableFileIdentity(directoryAfter),
      )
    ) {
      throw new RenderReviewError(
        "output-content-changed",
        "The owned output changed while its replacement boundary was being verified.",
        { output: "[output path omitted]" },
      );
    }
  }

  await walk(output);
  entries.sort((left, right) => left.path.localeCompare(right.path, "en"));
  return {
    manifest_sha256: sha256Value(JSON.stringify(entries)),
    file_count: fileCount,
    directory_count: directoryCount,
    total_bytes: totalBytes,
  };
}

function sameTreeFingerprint(left, right) {
  return (
    left.manifest_sha256 === right.manifest_sha256 &&
    left.file_count === right.file_count &&
    left.directory_count === right.directory_count &&
    left.total_bytes === right.total_bytes
  );
}

async function validateOutput(outputValue, replace, target) {
  const output = path.resolve(outputValue);
  assertOutputSeparation(output, target);
  await assertNoSymlinkComponents(output, true);
  const exists = await pathExists(output);
  if (!exists) return { path: output, exists: false, identity: null, marker: null };

  const info = await lstat(output);
  if (!info.isDirectory() || info.isSymbolicLink()) {
    throw new RenderReviewError(
      "output-not-directory",
      "The output path exists and is not a regular directory.",
      { output: "[output path omitted]" },
    );
  }
  if (!replace) {
    throw new RenderReviewError(
      "output-exists",
      "The output directory already exists. Use --replace only for an owned Design DNA output.",
      { output: "[output path omitted]" },
    );
  }
  const marker = await validateOwnershipMarker(output);
  return {
    path: output,
    exists: true,
    identity: await directoryIdentity(output),
    marker,
    tree_fingerprint: await fingerprintOwnedOutput(output),
  };
}

async function recheckOutput(output, expected, replace, target) {
  assertOutputSeparation(output, target);
  await assertNoSymlinkComponents(output, true);
  const exists = await pathExists(output);
  if (!expected.exists) {
    if (exists) {
      throw new RenderReviewError(
        "output-created-during-run",
        "The output appeared after capture began; no replacement was attempted.",
        { output: "[output path omitted]" },
      );
    }
    return;
  }
  if (!exists || !replace) {
    throw new RenderReviewError(
      "output-identity-changed",
      "The owned output disappeared or replacement authorization changed during capture.",
      { output: "[output path omitted]" },
    );
  }
  const identity = await directoryIdentity(output);
  if (!sameDirectoryIdentity(identity, expected.identity)) {
    throw new RenderReviewError(
      "output-identity-changed",
      "The output directory identity changed during capture.",
      { output: "[output path omitted]" },
    );
  }
  const marker = await validateOwnershipMarker(output);
  if (marker.output_identity.id !== expected.marker.output_identity.id) {
    throw new RenderReviewError(
      "output-identity-changed",
      "The output ownership identity changed during capture.",
      { output: "[output path omitted]" },
    );
  }
  const treeFingerprint = await fingerprintOwnedOutput(output);
  if (!sameTreeFingerprint(treeFingerprint, expected.tree_fingerprint)) {
    throw new RenderReviewError(
      "output-content-changed",
      "The owned output contents changed during capture; no replacement was attempted.",
      { output: "[output path omitted]" },
    );
  }
}

async function acquireOutputLock(output) {
  const lockPath = path.join(
    path.dirname(output),
    `.${path.basename(output)}.design-dna-render-review.lock`,
  );
  const token = randomBytes(32).toString("hex");
  let handle;
  try {
    handle = await open(lockPath, "wx", 0o600);
  } catch (error) {
    if (error?.code === "EEXIST") {
      throw new RenderReviewError(
        "output-locked",
        "Another rendered-review transaction owns the output lock.",
        { lock: path.basename(lockPath) },
      );
    }
    throw error;
  }
  try {
    await handle.writeFile(
      `${JSON.stringify({
        schema_version: 1,
        tool: TOOL_NAME,
        token,
        output_path_sha256: sha256Value(normalizePathForComparison(output)),
        created_at: new Date().toISOString(),
        pid: process.pid,
      })}\n`,
      "utf8",
    );
    await handle.sync();
  } finally {
    await handle.close();
  }
  return {
    path: lockPath,
    token,
    async release() {
      const info = await lstat(lockPath).catch(() => null);
      if (!info?.isFile() || info.isSymbolicLink() || info.size > 4096) return false;
      let lock;
      try {
        lock = JSON.parse(await readFile(lockPath, "utf8"));
      } catch {
        return false;
      }
      if (lock.token !== token) return false;
      await unlink(lockPath);
      return true;
    },
  };
}

function validateLocalRoute(raw) {
  if (/^[A-Za-z][A-Za-z0-9+.-]*:/u.test(raw)) {
    throw new RenderReviewError(
      "unsafe-local-route",
      "Local routes must be relative paths, not URLs.",
      { route: raw },
    );
  }
  if (raw.startsWith("//")) {
    throw new RenderReviewError(
      "unsafe-local-route",
      "Local routes cannot use network-path references.",
      { route: raw },
    );
  }
  const rawPathname = raw.split(/[?#]/u, 1)[0];
  let rawDecoded;
  try {
    rawDecoded = decodeURIComponent(rawPathname);
  } catch {
    throw new RenderReviewError(
      "invalid-route-encoding",
      "Local route contains invalid percent encoding.",
      { route: raw },
    );
  }
  if (
    rawDecoded.includes("\\") ||
    rawDecoded.includes("\0") ||
    rawDecoded.split("/").some((segment) => segment === "." || segment === "..")
  ) {
    throw new RenderReviewError(
      "unsafe-local-route",
      "Local routes cannot contain traversal, backslashes, or null bytes.",
      { route: raw },
    );
  }
  const route = new URL(raw.startsWith("/") ? raw : `/${raw}`, "http://local.invalid");
  let decoded;
  try {
    decoded = decodeURIComponent(route.pathname);
  } catch {
    throw new RenderReviewError(
      "invalid-route-encoding",
      "Local route contains invalid percent encoding.",
      { route: raw },
    );
  }
  const segments = decoded.split("/");
  if (
    decoded.includes("\\") ||
    decoded.includes("\0") ||
    segments.some((segment) => segment === "." || segment === "..")
  ) {
    throw new RenderReviewError(
      "unsafe-local-route",
      "Local routes cannot contain traversal, backslashes, or null bytes.",
      { route: raw },
    );
  }
  return `${route.pathname}${route.search}${route.hash}`;
}

function buildRemoteRoutes(target, additions) {
  const base = new URL(target.url);
  const candidates = [{ requested: target.input, url: base.href }];
  for (const raw of additions) {
    const candidate = new URL(raw, base);
    if (
      candidate.origin !== base.origin ||
      !["http:", "https:"].includes(candidate.protocol) ||
      candidate.username ||
      candidate.password
    ) {
      throw new RenderReviewError(
        "cross-origin-route",
        "Additional routes must remain on the target origin and cannot contain credentials.",
        { route: raw, target_origin: base.origin },
      );
    }
    candidates.push({ requested: raw, url: candidate.href });
  }
  const seen = new Set();
  return candidates
    .filter((candidate) => {
      if (seen.has(candidate.url)) return false;
      seen.add(candidate.url);
      return true;
    })
    .map((candidate, index) => ({
      id: `route-${String(index + 1).padStart(2, "0")}`,
      requested: candidate.requested,
      url: candidate.url,
    }));
}

function snapshotPathAllowed(relativePath, isDirectory = false) {
  const portable = relativePath.split(path.sep).join("/");
  const segments = portable.split("/").filter(Boolean);
  const lowerSegments = segments.map((segment) => segment.toLowerCase());
  if (
    !segments.length ||
    lowerSegments.some(
      (segment) => segment.startsWith(".") || DENIED_PATH_SEGMENTS.has(segment),
    )
  ) {
    return { allowed: false, reason: "hidden-or-source-only-path" };
  }
  if (isDirectory) return { allowed: true, reason: null };
  const name = lowerSegments.at(-1);
  const extension = path.extname(name);
  if (
    DENIED_FILE_NAMES.has(name) ||
    name.startsWith(".env") ||
    name.endsWith(".map") ||
    /(?:^|[-_.])(credential|private[-_]?key|secret|token)(?:[-_.]|$)/u.test(name) ||
    /(?:^|\.)(?:babel|eslint|next|nuxt|postcss|prettier|rollup|tailwind|vite|webpack)\.config\./u.test(
      name,
    )
  ) {
    return { allowed: false, reason: "sensitive-or-source-config" };
  }
  if (!PUBLIC_EXTENSIONS.has(extension)) {
    return { allowed: false, reason: "extension-not-public-allowlist" };
  }
  return { allowed: true, reason: null };
}

async function hasIndexHtml(directory) {
  for (const name of ["index.html", "index.htm"]) {
    const info = await lstat(path.join(directory, name)).catch(() => null);
    if (info?.isFile() && !info.isSymbolicLink()) return name;
  }
  return null;
}

async function selectPublicSource(target) {
  if (target.kind === "local-file") {
    return {
      root: path.dirname(target.localPath),
      entry_path: path.basename(target.localPath),
      root_kind: "single-html-parent-public-subset",
    };
  }
  if (target.kind !== "local-directory") return null;

  const baseName = path.basename(target.localPath).toLowerCase();
  const directIndex = await hasIndexHtml(target.localPath);
  if (PUBLIC_ROOT_NAMES.has(baseName) && directIndex) {
    return {
      root: target.localPath,
      entry_path: directIndex,
      root_kind: `explicit-${baseName}-root`,
    };
  }
  for (const candidateName of ["dist", "build", "out", "public"]) {
    const candidate = path.join(target.localPath, candidateName);
    const info = await lstat(candidate).catch(() => null);
    if (!info?.isDirectory() || info.isSymbolicLink()) continue;
    const entry = await hasIndexHtml(candidate);
    if (entry) {
      return {
        root: candidate,
        entry_path: entry,
        root_kind: `auto-selected-${candidateName}-root`,
      };
    }
  }
  if (directIndex) {
    return {
      root: target.localPath,
      entry_path: directIndex,
      root_kind: "explicit-target-public-root",
    };
  }
  throw new RenderReviewError(
    "public-root-not-found",
    "No index.html was found in the explicit target or a dist, build, out, or public child.",
    { target: "[source path omitted]" },
  );
}

async function enumeratePublicFiles(root, limits) {
  const files = [];
  const excludedCounts = {
    hidden_or_source_only_path: 0,
    sensitive_or_source_config: 0,
    extension_not_public_allowlist: 0,
  };
  async function walk(directory, relativeDirectory = "") {
    const entries = await readdir(directory, { withFileTypes: true });
    entries.sort((left, right) => left.name.localeCompare(right.name, "en"));
    for (const entry of entries) {
      const relative = relativeDirectory
        ? path.join(relativeDirectory, entry.name)
        : entry.name;
      const portable = relative.split(path.sep).join("/");
      const allowed = snapshotPathAllowed(relative, entry.isDirectory());
      if (!allowed.allowed) {
        const key = allowed.reason.replaceAll("-", "_");
        excludedCounts[key] += 1;
        continue;
      }
      const absolute = path.join(root, relative);
      const info = await lstat(absolute);
      if (entry.isSymbolicLink() || info.isSymbolicLink()) {
        throw new RenderReviewError(
          "source-symlink-refused",
          "A public snapshot cannot include symbolic links or junctions.",
          { path: portable },
        );
      }
      if (entry.isDirectory()) {
        await walk(absolute, relative);
        continue;
      }
      if (!entry.isFile() || !info.isFile()) continue;
      if (info.size > limits.source_file_bytes) {
        throw new RenderReviewError(
          "source-file-limit-exceeded",
          "A public source file exceeds the configured per-file snapshot limit.",
          {
            path: portable,
            bytes: info.size,
            maximum_bytes: limits.source_file_bytes,
          },
        );
      }
      files.push({ relative: portable, absolute, bytes: info.size });
      if (files.length > limits.source_files) {
        throw new RenderReviewError(
          "source-file-count-exceeded",
          "The public snapshot exceeds its configured file-count limit.",
          { count: files.length, maximum: limits.source_files },
        );
      }
      const totalBytes = files.reduce((total, file) => total + file.bytes, 0);
      if (totalBytes > limits.source_bytes) {
        throw new RenderReviewError(
          "source-byte-limit-exceeded",
          "The public snapshot exceeds its configured total-byte limit.",
          { bytes: totalBytes, maximum_bytes: limits.source_bytes },
        );
      }
    }
  }
  await walk(root);
  return { files, excluded_counts: excludedCounts };
}

async function createFrozenSnapshot(target, snapshotDirectory, limits) {
  const selected = await selectPublicSource(target);
  const canonicalRoot = await realpath(selected.root);
  await assertNoSymlinkComponents(canonicalRoot);
  const enumerated = await enumeratePublicFiles(canonicalRoot, limits);
  if (!enumerated.files.some((file) => file.relative === selected.entry_path)) {
    throw new RenderReviewError(
      "snapshot-entry-excluded",
      "The selected HTML entry was excluded by the deny-by-default public snapshot policy.",
      { entry_path: selected.entry_path },
    );
  }
  await mkdir(snapshotDirectory, { recursive: true });
  const manifestFiles = [];
  for (const file of enumerated.files) {
    const payload = await readFile(file.absolute);
    if (payload.length !== file.bytes) {
      throw new RenderReviewError(
        "source-drift",
        "A source file changed while the frozen snapshot was being created.",
        { path: file.relative },
      );
    }
    const destination = path.join(
      snapshotDirectory,
      ...file.relative.split("/"),
    );
    await mkdir(path.dirname(destination), { recursive: true });
    await writeFile(destination, payload, { flag: "wx", mode: 0o600 });
    manifestFiles.push({
      path: file.relative,
      bytes: payload.length,
      sha256: sha256Value(payload),
    });
  }
  const totalBytes = manifestFiles.reduce((total, file) => total + file.bytes, 0);
  const manifestHash = sha256Value(
    JSON.stringify(
      manifestFiles.map(({ path: filePath, bytes, sha256 }) => ({
        path: filePath,
        bytes,
        sha256,
      })),
    ),
  );
  return {
    source_root: canonicalRoot,
    snapshot_root: path.resolve(snapshotDirectory),
    root_kind: selected.root_kind,
    entry_path: selected.entry_path,
    manifest: {
      algorithm: "sha256",
      manifest_sha256: manifestHash,
      file_count: manifestFiles.length,
      total_bytes: totalBytes,
      files: manifestFiles,
      excluded_counts: enumerated.excluded_counts,
    },
  };
}

async function verifyFrozenSnapshot(snapshot, limits, target) {
  const selected = await selectPublicSource(target);
  if (
    normalizePathForComparison(await realpath(selected.root)) !==
      normalizePathForComparison(snapshot.source_root) ||
    selected.entry_path !== snapshot.entry_path ||
    selected.root_kind !== snapshot.root_kind
  ) {
    throw new RenderReviewError(
      "source-drift",
      "Public-root selection changed during capture.",
      { source: "[source path omitted]" },
    );
  }
  const enumerated = await enumeratePublicFiles(snapshot.source_root, limits);
  const expected = snapshot.manifest.files;
  if (
    enumerated.files.length !== expected.length ||
    enumerated.files.some((file, index) => file.relative !== expected[index]?.path)
  ) {
    throw new RenderReviewError(
      "source-drift",
      "The public source file set changed during capture.",
      {
        expected_file_count: expected.length,
        observed_file_count: enumerated.files.length,
      },
    );
  }
  if (
    JSON.stringify(enumerated.excluded_counts) !==
    JSON.stringify(snapshot.manifest.excluded_counts)
  ) {
    throw new RenderReviewError(
      "source-drift",
      "The excluded source-file classification changed during capture.",
      { source: "[source path omitted]" },
    );
  }
  for (let index = 0; index < enumerated.files.length; index += 1) {
    const file = enumerated.files[index];
    const payload = await readFile(file.absolute);
    if (
      payload.length !== expected[index].bytes ||
      sha256Value(payload) !== expected[index].sha256
    ) {
      throw new RenderReviewError(
        "source-drift",
        "Public source content changed during capture.",
        { path: file.relative },
      );
    }
  }
  const frozen = await enumeratePublicFiles(snapshot.snapshot_root, limits);
  if (
    frozen.files.length !== expected.length ||
    frozen.files.some((file, index) => file.relative !== expected[index]?.path)
  ) {
    throw new RenderReviewError(
      "snapshot-drift",
      "The frozen public snapshot file set changed during capture.",
      {
        expected_file_count: expected.length,
        observed_file_count: frozen.files.length,
      },
    );
  }
  for (let index = 0; index < frozen.files.length; index += 1) {
    const payload = await readFile(frozen.files[index].absolute);
    if (
      payload.length !== expected[index].bytes ||
      sha256Value(payload) !== expected[index].sha256
    ) {
      throw new RenderReviewError(
        "snapshot-drift",
        "Frozen public snapshot content changed during capture.",
        { path: frozen.files[index].relative },
      );
    }
  }
}

function mimeType(filePath) {
  const extension = path.extname(filePath).toLowerCase();
  return {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".pdf": "application/pdf",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
  }[extension] ?? "application/octet-stream";
}

async function resolveServedFile(root, rawUrl) {
  const parsed = new URL(rawUrl, "http://127.0.0.1");
  let decoded;
  try {
    decoded = decodeURIComponent(parsed.pathname);
  } catch {
    return { status: 400, reason: "invalid-encoding" };
  }
  if (decoded.includes("\\") || decoded.includes("\0")) {
    return { status: 400, reason: "unsafe-path" };
  }
  const segments = decoded.split("/").filter(Boolean);
  if (segments.some((segment) => segment === "." || segment === "..")) {
    return { status: 403, reason: "path-traversal" };
  }

  let current = root;
  for (const segment of segments) {
    current = path.join(current, segment);
    if (!isInside(current, root)) {
      return { status: 403, reason: "path-escape" };
    }
    const info = await lstat(current).catch(() => null);
    if (!info) {
      return { status: 404, reason: "not-found" };
    }
    if (info.isSymbolicLink()) {
      return { status: 403, reason: "symlink-refused" };
    }
  }

  let info = await lstat(current).catch(() => null);
  if (info?.isDirectory()) {
    current = path.join(current, "index.html");
    if (!isInside(current, root)) {
      return { status: 403, reason: "path-escape" };
    }
    info = await lstat(current).catch(() => null);
    if (info?.isSymbolicLink()) {
      return { status: 403, reason: "symlink-refused" };
    }
  }
  if (!info?.isFile()) {
    return { status: 404, reason: "not-found" };
  }
  const publicDecision = snapshotPathAllowed(path.relative(root, current));
  if (!publicDecision.allowed) {
    return { status: 403, reason: "snapshot-policy-refused" };
  }
  return { status: 200, path: current, size: info.size };
}

async function startStaticServer(root, entryPath = "index.html") {
  const canonicalRoot = await realpath(root);
  const server = http.createServer(async (request, response) => {
    try {
      if (!["GET", "HEAD"].includes(request.method ?? "")) {
        response.writeHead(405, { Allow: "GET, HEAD" });
        response.end("Method not allowed");
        return;
      }
      const resolved = await resolveServedFile(canonicalRoot, request.url ?? "/");
      if (resolved.status !== 200) {
        response.writeHead(resolved.status, {
          "Content-Type": "text/plain; charset=utf-8",
          "Cache-Control": "no-store",
        });
        response.end(resolved.reason);
        return;
      }
      response.writeHead(200, {
        "Content-Type": mimeType(resolved.path),
        "Content-Length": String(resolved.size),
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
      });
      if (request.method === "HEAD") {
        response.end();
        return;
      }
      createReadStream(resolved.path)
        .on("error", () => response.destroy())
        .pipe(response);
    } catch {
      response.writeHead(500, {
        "Content-Type": "text/plain; charset=utf-8",
        "Cache-Control": "no-store",
      });
      response.end("Internal server error");
    }
  });

  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  if (!address || typeof address === "string") {
    server.close();
    throw new RenderReviewError(
      "local-server-failed",
      "Could not determine the local review server address.",
      {},
      3,
    );
  }
  return {
    server,
    origin: `http://127.0.0.1:${address.port}`,
    entryPath,
    async close() {
      await new Promise((resolve) => server.close(resolve));
    },
  };
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
    throw new RenderReviewError(
      error?.code || "playwright-unavailable",
      String(error?.message || error),
      error?.details || {},
      3,
    );
  }
}

function safeEventUrl(raw) {
  return sanitizeUrl(raw).slice(0, 500);
}

function boundedPush(list, value, counter) {
  if (list.length < MAX_EVENTS) {
    list.push(value);
  } else {
    counter.truncated += 1;
  }
}

async function inspectDocument(page) {
  return page.evaluate(({ maxCandidates }) => {
    const compact = (value, limit = 240) =>
      String(value ?? "").replace(/\s+/g, " ").trim().slice(0, limit);
    const visible = (element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return (
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        Number(style.opacity || 1) > 0 &&
        rect.width > 0 &&
        rect.height > 0
      );
    };
    const selectorFor = (element) => {
      if (!(element instanceof Element)) return "";
      if (element.id) return `#${CSS.escape(element.id)}`;
      const parts = [];
      let current = element;
      while (current && current !== document.documentElement && parts.length < 6) {
        let part = current.localName;
        if (!part) break;
        const parent = current.parentElement;
        if (parent) {
          const siblings = [...parent.children].filter((node) => node.localName === current.localName);
          if (siblings.length > 1) {
            part += `:nth-of-type(${siblings.indexOf(current) + 1})`;
          }
        }
        parts.unshift(part);
        current = parent;
      }
      return parts.join(" > ");
    };
    const rectFor = (element) => {
      const rect = element.getBoundingClientRect();
      return {
        x: Math.round(rect.x * 100) / 100,
        y: Math.round(rect.y * 100) / 100,
        width: Math.round(rect.width * 100) / 100,
        height: Math.round(rect.height * 100) / 100,
        right: Math.round(rect.right * 100) / 100,
        bottom: Math.round(rect.bottom * 100) / 100,
      };
    };
    const roundedRatio = (value, divisor) => {
      if (!Number.isFinite(value) || !Number.isFinite(divisor) || divisor <= 0) return 0;
      return Math.round((value / divisor) * 10000) / 10000;
    };
    const normalizedRectFor = (element) => {
      const rect = element.getBoundingClientRect();
      const documentHeight = Math.max(
        document.documentElement.scrollHeight,
        document.body?.scrollHeight || 0,
        window.innerHeight,
        1,
      );
      const viewportWidth = Math.max(window.innerWidth, 1);
      return {
        x: roundedRatio(rect.left, viewportWidth),
        y: roundedRatio(rect.top + window.scrollY, documentHeight),
        width: roundedRatio(rect.width, viewportWidth),
        height: roundedRatio(rect.height, documentHeight),
      };
    };
    const splitCssTracks = (value) => {
      const source = String(value || "").trim();
      if (!source || source === "none" || source === "subgrid") return [];
      const tracks = [];
      let current = "";
      let depth = 0;
      for (const character of source) {
        if (character === "(") depth += 1;
        if (character === ")") depth = Math.max(0, depth - 1);
        if (/\s/.test(character) && depth === 0) {
          if (current) tracks.push(current);
          current = "";
        } else {
          current += character;
        }
      }
      if (current) tracks.push(current);
      return tracks;
    };
    const roleFor = (element) => {
      const explicit = element.getAttribute("role");
      if (explicit) return explicit;
      const tag = element.localName;
      if (tag === "a" && element.hasAttribute("href")) return "link";
      if (tag === "button") return "button";
      if (tag === "select") return "combobox";
      if (tag === "textarea") return "textbox";
      if (tag === "summary") return "button";
      if (tag === "input") {
        const type = (element.getAttribute("type") || "text").toLowerCase();
        if (["button", "submit", "reset", "image"].includes(type)) return "button";
        if (type === "checkbox") return "checkbox";
        if (type === "radio") return "radio";
        if (type === "range") return "slider";
        return "textbox";
      }
      return "";
    };
    const nameFor = (element) => {
      const ariaLabel = element.getAttribute("aria-label");
      if (ariaLabel) return { value: compact(ariaLabel), source: "aria-label" };
      const labelledBy = element.getAttribute("aria-labelledby");
      if (labelledBy) {
        const value = labelledBy
          .split(/\s+/)
          .map((id) => document.getElementById(id)?.textContent ?? "")
          .join(" ");
        if (compact(value)) return { value: compact(value), source: "aria-labelledby" };
      }
      if ("labels" in element && element.labels?.length) {
        return {
          value: compact([...element.labels].map((label) => label.textContent).join(" ")),
          source: "label",
        };
      }
      if (element instanceof HTMLImageElement && element.alt) {
        return { value: compact(element.alt), source: "alt" };
      }
      if (
        element instanceof HTMLInputElement &&
        ["button", "submit", "reset"].includes(element.type)
      ) {
        return { value: compact(element.value), source: "value" };
      }
      if (element instanceof HTMLSelectElement) {
        const selected = compact(
          [...element.selectedOptions].map((option) => option.textContent).join(" "),
        );
        if (selected) return { value: selected, source: "text" };
      }
      const text = compact(element.textContent);
      if (text) return { value: text, source: "text" };
      if (element.getAttribute("title")) {
        return { value: compact(element.getAttribute("title")), source: "title" };
      }
      return { value: "", source: "text" };
    };
    const styleSnapshot = (element) => {
      const style = getComputedStyle(element);
      const cssValue = (value, limit = 500) => {
        const raw = String(value ?? "");
        if (raw.includes("data:")) return "data:[computed-style payload omitted]";
        return raw.slice(0, limit);
      };
      return {
        color: cssValue(style.color),
        background_color: cssValue(style.backgroundColor),
        background_image: cssValue(style.backgroundImage),
        font_family: cssValue(style.fontFamily),
        font_weight: cssValue(style.fontWeight),
        font_style: cssValue(style.fontStyle),
        font_size: cssValue(style.fontSize),
        text_decoration_line: cssValue(style.textDecorationLine),
        outline_color: cssValue(style.outlineColor),
        outline_style: cssValue(style.outlineStyle),
        outline_width: cssValue(style.outlineWidth),
        box_shadow: cssValue(style.boxShadow),
        border_color: cssValue(style.borderColor),
      };
    };

    const headings = [...document.querySelectorAll("h1,h2,h3,h4,h5,h6,[role='heading']")]
      .filter(visible)
      .slice(0, maxCandidates)
      .map((element) => ({
        level: Number(element.getAttribute("aria-level")) || Number(element.localName.slice(1)) || null,
        text: compact(element.textContent),
        id: element.id || null,
        selector: selectorFor(element),
      }));

    const landmarks = [
      ...document.querySelectorAll(
        "header,nav,main,aside,footer,form,[role='banner'],[role='navigation'],[role='main'],[role='complementary'],[role='contentinfo'],[role='search'],[role='region']",
      ),
    ]
      .filter(visible)
      .slice(0, maxCandidates)
      .map((element) => ({
        tag: element.localName,
        role: element.getAttribute("role") || null,
        label: compact(element.getAttribute("aria-label") || element.getAttribute("aria-labelledby") || ""),
        selector: selectorFor(element),
      }));

    const silhouetteRoot = document.querySelector("main,[role='main']") || document.body;
    const structuralChildren = (root) =>
      [...root.children].filter(
        (element) =>
          !["script", "style", "template"].includes(element.localName) && visible(element),
      );
    let silhouetteElements = structuralChildren(silhouetteRoot);
    for (let depth = 0; depth < 3 && silhouetteElements.length === 1; depth += 1) {
      const nested = structuralChildren(silhouetteElements[0]);
      if (nested.length < 2) break;
      silhouetteElements = nested;
    }
    const routeSilhouette = silhouetteElements
      .slice(0, maxCandidates)
      .map((element, index) => {
        const heading = element.matches("h1,h2,h3,h4,h5,h6")
          ? element
          : element.querySelector("h1,h2,h3,h4,h5,h6,[role='heading']");
        const style = getComputedStyle(element);
        const headingStyle = heading ? getComputedStyle(heading) : null;
        const visibleChildren = [...element.children].filter(visible);
        const media = [
          ...element.querySelectorAll("img,picture,video,canvas,svg,model-viewer,iframe"),
        ].filter(visible);
        const controls = [
          ...element.querySelectorAll(
            "a[href],button,input,select,textarea,summary,[role='button'],[role='link'],[role='tab']",
          ),
        ].filter(visible);
        const elementRect = element.getBoundingClientRect();
        const largestMediaArea = media.reduce((largest, candidate) => {
          const mediaRect = candidate.getBoundingClientRect();
          return Math.max(largest, Math.max(0, mediaRect.width) * Math.max(0, mediaRect.height));
        }, 0);
        const elementArea = Math.max(0, elementRect.width) * Math.max(0, elementRect.height);
        const firstChildTop = visibleChildren.length
          ? Math.min(...visibleChildren.map((child) => child.getBoundingClientRect().top))
          : null;
        const firstRowTolerance = Math.max(16, elementRect.height * 0.05);
        const visualColumnCount = firstChildTop === null
          ? 0
          : visibleChildren.filter(
              (child) => Math.abs(child.getBoundingClientRect().top - firstChildTop) <= firstRowTolerance,
            ).length;
        return {
          order: index + 1,
          tag: element.localName,
          role: element.getAttribute("role") || null,
          heading: compact(heading?.textContent ?? ""),
          label: compact(element.getAttribute("aria-label") || ""),
          selector: selectorFor(element),
          rect: rectFor(element),
          normalized_rect: normalizedRectFor(element),
          display: style.display,
          position: style.position,
          grid_column_count: style.display.includes("grid")
            ? splitCssTracks(style.gridTemplateColumns).length
            : 0,
          flex_direction: style.display.includes("flex") ? style.flexDirection : null,
          visual_column_count: visualColumnCount,
          direct_visible_child_count: visibleChildren.length,
          text_length: compact(element.textContent, 100000).length,
          media_count: media.length,
          control_count: controls.length,
          sticky_or_fixed: ["sticky", "fixed"].includes(style.position),
          dominant_media_area_ratio: roundedRatio(largestMediaArea, Math.max(elementArea, 1)),
          heading_rect: heading && visible(heading) ? rectFor(heading) : null,
          heading_font_size_px: headingStyle ? Number.parseFloat(headingStyle.fontSize) || null : null,
          heading_font_weight: headingStyle ? headingStyle.fontWeight : null,
          heading_text_align: headingStyle ? headingStyle.textAlign : null,
        };
      });

    const allVisible = [...document.querySelectorAll("body *")].filter(visible);
    const overflowCandidates = [];
    const handledHorizontalOverflowValues = new Set([
      "auto",
      "scroll",
      "overlay",
      "hidden",
      "clip",
    ]);
    const horizontalOverflowHandledByAncestor = (element) => {
      for (
        let ancestor = element.parentElement;
        ancestor;
        ancestor = ancestor.parentElement
      ) {
        if (handledHorizontalOverflowValues.has(getComputedStyle(ancestor).overflowX)) {
          return true;
        }
      }
      return false;
    };
    for (const element of allVisible) {
      if (overflowCandidates.length >= maxCandidates) break;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      const reasons = [];
      const horizontalOverflowHandledByContainer =
        horizontalOverflowHandledByAncestor(element);
      if (
        (rect.left < -1 || rect.right > window.innerWidth + 1) &&
        !horizontalOverflowHandledByContainer
      ) {
        reasons.push("outside-horizontal-viewport");
      }
      if (
        element.clientWidth > 0 &&
        element.scrollWidth > element.clientWidth + 1 &&
        !handledHorizontalOverflowValues.has(style.overflowX) &&
        !horizontalOverflowHandledByContainer &&
        !element.matches("input,textarea,select,option,img,video,canvas,iframe,svg")
      ) {
        reasons.push("internal-horizontal-content-overflow");
      }
      if (
        ["hidden", "clip"].includes(style.overflowY) &&
        element.scrollHeight > element.clientHeight + 1
      ) {
        reasons.push("vertical-content-clipped");
      }
      if (reasons.length) {
        overflowCandidates.push({
          classification: "advisory-candidate",
          selector: selectorFor(element),
          text: compact(element.textContent, 160),
          reasons,
          rect: rectFor(element),
          client: { width: element.clientWidth, height: element.clientHeight },
          scroll: { width: element.scrollWidth, height: element.scrollHeight },
          overflow: { x: style.overflowX, y: style.overflowY },
        });
      }
    }

    // Sample painted text in the current viewport for peer elements that sit
    // above it. This is deliberately an advisory: overlap can be intentional,
    // but a sibling band, sticky surface, or positioned ornament covering a
    // caption is not detectable from scrollWidth/scrollHeight alone.
    const occlusionWalker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          if (!compact(node.textContent, 1)) return NodeFilter.FILTER_REJECT;
          const parent = node.parentElement;
          if (!parent || !visible(parent)) return NodeFilter.FILTER_REJECT;
          if (parent.closest("script,style,noscript,template")) {
            return NodeFilter.FILTER_REJECT;
          }
          return NodeFilter.FILTER_ACCEPT;
        },
      },
    );
    let inspectedTextNodes = 0;
    while (
      overflowCandidates.length < maxCandidates &&
      inspectedTextNodes < maxCandidates * 12
    ) {
      const textNode = occlusionWalker.nextNode();
      if (!textNode) break;
      inspectedTextNodes += 1;
      const element = textNode.parentElement;
      if (!element) continue;
      const range = document.createRange();
      range.selectNodeContents(textNode);
      const blockers = new Set();
      for (const textRect of [...range.getClientRects()].slice(0, 12)) {
        if (textRect.width < 3 || textRect.height < 3) continue;
        if (
          textRect.bottom <= 0 ||
          textRect.top >= window.innerHeight ||
          textRect.right <= 0 ||
          textRect.left >= window.innerWidth
        ) {
          continue;
        }
        const y = Math.min(window.innerHeight - 1, Math.max(0, textRect.top + textRect.height / 2));
        for (const fraction of [0.2, 0.5, 0.8]) {
          const x = Math.min(
            window.innerWidth - 1,
            Math.max(0, textRect.left + textRect.width * fraction),
          );
          const top = document.elementFromPoint(x, y);
          if (!top || element.contains(top) || top.contains(element)) continue;
          blockers.add(selectorFor(top));
        }
      }
      range.detach();
      if (!blockers.size) continue;
      const selector = selectorFor(element);
      const existing = overflowCandidates.find((candidate) => candidate.selector === selector);
      if (existing) {
        if (!existing.reasons.includes("text-occluded-by-peer")) {
          existing.reasons.push("text-occluded-by-peer");
        }
        existing.occluding_selectors = [...new Set([
          ...(existing.occluding_selectors || []),
          ...blockers,
        ])].slice(0, 12);
        continue;
      }
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      overflowCandidates.push({
        classification: "advisory-candidate",
        selector,
        text: compact(element.textContent, 160),
        reasons: ["text-occluded-by-peer"],
        rect: rectFor(element),
        client: { width: element.clientWidth, height: element.clientHeight },
        scroll: { width: element.scrollWidth, height: element.scrollHeight },
        overflow: { x: style.overflowX, y: style.overflowY },
        occluding_selectors: [...blockers].slice(0, 12),
      });
    }

    const images = [...document.images].slice(0, maxCandidates).map((image) => {
      const style = getComputedStyle(image);
      const rendered = image.getBoundingClientRect();
      const naturalRatio =
        image.naturalWidth && image.naturalHeight ? image.naturalWidth / image.naturalHeight : null;
      const renderedRatio =
        rendered.width && rendered.height ? rendered.width / rendered.height : null;
      const ratioDelta =
        naturalRatio && renderedRatio
          ? Math.abs(naturalRatio - renderedRatio) / naturalRatio
          : null;
      return {
        selector: selectorFor(image),
        src: image.getAttribute("src")?.startsWith("data:")
          ? "data:[payload omitted]"
          : compact(image.getAttribute("src"), 500),
        current_src: image.currentSrc?.startsWith("data:")
          ? "data:[payload omitted]"
          : compact(image.currentSrc, 500),
        alt_present: image.hasAttribute("alt"),
        alt: compact(image.getAttribute("alt")),
        role: image.getAttribute("role") || null,
        aria_label: compact(image.getAttribute("aria-label")),
        loading: image.loading || null,
        decoding: image.decoding || null,
        complete: image.complete,
        failed: image.complete && image.naturalWidth === 0,
        natural: { width: image.naturalWidth, height: image.naturalHeight },
        rendered: {
          width: Math.round(rendered.width * 100) / 100,
          height: Math.round(rendered.height * 100) / 100,
        },
        object_fit: style.objectFit,
        object_position: style.objectPosition,
        crop_candidate:
          style.objectFit === "cover" && ratioDelta !== null && ratioDelta > 0.04,
        ratio_delta: ratioDelta === null ? null : Math.round(ratioDelta * 10000) / 10000,
      };
    });

    const fontMap = new Map();
    const fontAvailable = (weight, size, primaryFamily) => {
      if (!primaryFamily || !document.fonts?.check) return null;
      try {
        const escapedFamily = primaryFamily.replaceAll("\\", "\\\\").replaceAll('"', '\\"');
        return document.fonts.check(`${weight} ${size} "${escapedFamily}"`);
      } catch {
        return null;
      }
    };
    for (const element of allVisible) {
      if (!compact(element.textContent, 1)) continue;
      const style = getComputedStyle(element);
      const family = String(style.fontFamily || "").slice(0, 500);
      const primaryFamily = family.split(",")[0]?.trim().replace(/^['"]|['"]$/g, "") || "";
      const key = `${family}\u0000${style.fontWeight}\u0000${style.fontStyle}`;
      if (!fontMap.has(key)) {
        fontMap.set(key, {
          family,
          primary_family: primaryFamily,
          weight: style.fontWeight,
          style: style.fontStyle,
          element_count: 0,
          sample_selectors: [],
          css_font_check: fontAvailable(
            style.fontWeight,
            style.fontSize,
            primaryFamily,
          ),
        });
      }
      const record = fontMap.get(key);
      record.element_count += 1;
      if (record.sample_selectors.length < 5) {
        record.sample_selectors.push(selectorFor(element));
      }
    }
    const fonts = [...fontMap.values()]
      .sort((left, right) =>
        `${left.family}|${left.weight}|${left.style}`.localeCompare(
          `${right.family}|${right.weight}|${right.style}`,
        ),
      )
      .slice(0, maxCandidates);

    const typographyRoleFor = (element) => {
      if (element.matches("h1,h2,h3,h4,h5,h6,[role='heading']")) return "heading";
      if (element.closest("nav,[role='navigation']")) return "navigation";
      if (element.matches("button,input,select,textarea,summary,[role='button'],[role='tab']")) {
        return "control";
      }
      if (element.matches("label,legend,dt")) return "label";
      if (element.matches("figcaption,caption")) return "caption";
      if (element.matches("code,pre,kbd,samp")) return "code";
      if (element.matches("li,dd")) return "list-or-definition";
      if (element.matches("p,blockquote")) return "body";
      return "other";
    };
    const typographyRoles = [
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
    const typographySamplingStrategy =
      "semantic-role-and-document-position-stratified-v1";
    const evenlySpacedIndices = (candidateCount, sampleCount) => {
      if (sampleCount >= candidateCount) {
        return Array.from({ length: candidateCount }, (_value, index) => index);
      }
      if (sampleCount === 1) {
        return [Math.floor((candidateCount - 1) / 2)];
      }
      return Array.from({ length: sampleCount }, (_value, index) =>
        Math.round((index * (candidateCount - 1)) / (sampleCount - 1)),
      );
    };
    const stratifiedTypographySample = (candidates, limit) => {
      const grouped = new Map(typographyRoles.map((role) => [role, []]));
      candidates.forEach((candidate, documentIndex) => {
        grouped.get(candidate.role).push({ ...candidate, documentIndex });
      });

      const quotas = new Map(typographyRoles.map((role) => [role, 0]));
      if (candidates.length <= limit) {
        for (const role of typographyRoles) {
          quotas.set(role, grouped.get(role).length);
        }
      } else {
        const nonemptyRoles = typographyRoles.filter(
          (role) => grouped.get(role).length > 0,
        );
        const minimumPerRole =
          limit >= nonemptyRoles.length * 2 ? 2 : 1;
        for (const role of nonemptyRoles) {
          quotas.set(role, Math.min(minimumPerRole, grouped.get(role).length));
        }

        const remainingSlots =
          limit - [...quotas.values()].reduce((total, value) => total + value, 0);
        const residual = nonemptyRoles.map((role, roleIndex) => ({
          role,
          roleIndex,
          available: grouped.get(role).length - quotas.get(role),
        }));
        const residualTotal = residual.reduce(
          (total, item) => total + item.available,
          0,
        );
        if (remainingSlots > 0 && residualTotal > 0) {
          for (const item of residual) {
            const exact = (remainingSlots * item.available) / residualTotal;
            item.floor = Math.min(item.available, Math.floor(exact));
            item.fraction = exact - Math.floor(exact);
            quotas.set(item.role, quotas.get(item.role) + item.floor);
          }
          let assigned = residual.reduce((total, item) => total + item.floor, 0);
          const remainderOrder = [...residual].sort(
            (left, right) =>
              right.fraction - left.fraction ||
              right.available - left.available ||
              left.roleIndex - right.roleIndex,
          );
          while (assigned < remainingSlots) {
            let progressed = false;
            for (const item of remainderOrder) {
              if (assigned >= remainingSlots) break;
              if (quotas.get(item.role) >= grouped.get(item.role).length) continue;
              quotas.set(item.role, quotas.get(item.role) + 1);
              assigned += 1;
              progressed = true;
            }
            if (!progressed) break;
          }
        }
      }

      const selectedDocumentIndices = new Set();
      for (const role of typographyRoles) {
        const roleCandidates = grouped.get(role);
        for (const roleIndex of evenlySpacedIndices(
          roleCandidates.length,
          quotas.get(role),
        )) {
          selectedDocumentIndices.add(roleCandidates[roleIndex].documentIndex);
        }
      }
      const sampled = candidates.filter((_candidate, documentIndex) =>
        selectedDocumentIndices.has(documentIndex),
      );
      const sampledByRole = new Map(typographyRoles.map((role) => [role, 0]));
      for (const candidate of sampled) {
        sampledByRole.set(candidate.role, sampledByRole.get(candidate.role) + 1);
      }
      return {
        sampled,
        evidence: {
          strategy: typographySamplingStrategy,
          candidate_count: candidates.length,
          sampled_count: sampled.length,
          truncated: sampled.length < candidates.length,
          role_counts: Object.fromEntries(
            typographyRoles.map((role) => [
              role,
              {
                candidate_count: grouped.get(role).length,
                sampled_count: sampledByRole.get(role),
              },
            ]),
          ),
        },
      };
    };
    const numericCssPx = (value) => {
      const parsed = Number.parseFloat(String(value || ""));
      return Number.isFinite(parsed) ? parsed : null;
    };
    // A person can type into these, so whatever they hold belongs to the
    // operator or the visitor, not to the page. Their type is still
    // measured; their characters are never persisted. Only the length
    // survives, which is all the measure and line-length checks need.
    const userEditable = (element) =>
      element.localName === "input" ||
      element.localName === "textarea" ||
      element.isContentEditable === true;
    const typographyTextOf = (element) =>
      element.textContent || element.value || "";
    const typographyCandidates = [
      ...document.querySelectorAll(
        "h1,h2,h3,h4,h5,h6,[role='heading'],p,blockquote,li,dt,dd,figcaption,caption,label,legend,a[href],button,input,select,textarea,summary,code,pre,kbd,samp",
      ),
    ]
      .filter((element) => visible(element) && compact(typographyTextOf(element), 1))
      .map((element) => ({ element, role: typographyRoleFor(element) }));
    const typographySampling = stratifiedTypographySample(
      typographyCandidates,
      maxCandidates,
    );
    const typographySamples = typographySampling.sampled.map(({ element, role }) => {
      const style = getComputedStyle(element);
      const lineHeight = numericCssPx(style.lineHeight);
      const rect = rectFor(element);
      const family = String(style.fontFamily || "").slice(0, 500);
      return {
          selector: selectorFor(element),
          tag: element.localName,
          role,
          // An empty sample beside a non-zero length is the redaction: the
          // report keeps what typography needs and drops what it must not
          // carry. The schema is a published contract, so this adds no field.
          text_sample: userEditable(element)
            ? ""
            : compact(typographyTextOf(element), 160),
          text_length: compact(typographyTextOf(element), 100000).length,
          rect,
          family,
          primary_family: family.split(",")[0]?.trim().replace(/^['"]|['"]$/g, "") || "",
          font_size_px: numericCssPx(style.fontSize),
          font_weight: style.fontWeight,
          font_style: style.fontStyle,
          font_stretch: style.fontStretch,
          line_height: style.lineHeight,
          line_height_px: lineHeight,
          letter_spacing: style.letterSpacing,
          letter_spacing_px: numericCssPx(style.letterSpacing),
          word_spacing: style.wordSpacing,
          word_spacing_px: numericCssPx(style.wordSpacing),
          text_transform: style.textTransform,
          text_align: style.textAlign,
          rendered_line_count_estimate:
            lineHeight && lineHeight > 0 && rect.height > 0
              ? Math.max(1, Math.round(rect.height / lineHeight))
              : null,
      };
    });

    const interactiveSelector =
      "a[href],button,input,select,textarea,summary,[contenteditable='true'],[tabindex],[role='button'],[role='link'],[role='checkbox'],[role='radio'],[role='switch'],[role='tab'],[role='menuitem'],[role='option'],[role='slider'],[role='spinbutton'],[role='textbox'],[role='combobox']";
    const controls = [...document.querySelectorAll(interactiveSelector)]
      .slice(0, maxCandidates)
      .map((element) => {
        const name = nameFor(element);
        return {
          selector: selectorFor(element),
          tag: element.localName,
          role: roleFor(element) || null,
          name: name.value,
          name_source: name.source,
          type: element.getAttribute("type"),
          href: element.getAttribute("href"),
          disabled:
            element.hasAttribute("disabled") ||
            element.getAttribute("aria-disabled") === "true",
          tab_index: element.tabIndex,
          visible: visible(element),
          rect: rectFor(element),
          baseline_focus_style: styleSnapshot(element),
        };
      });

    const prominentParents = [
      ...document.querySelectorAll("h1,h2,h3,[role='heading']"),
      ...allVisible.filter((element) => {
        const style = getComputedStyle(element);
        const size = Number.parseFloat(style.fontSize);
        const weight = Number.parseInt(style.fontWeight, 10) || 400;
        const text = compact(element.textContent, 220);
        return size >= 28 && weight >= 550 && text.length >= 2 && text.length <= 220;
      }),
    ];
    const uniqueParents = [...new Set(prominentParents)].filter(visible);
    const prominentFragmentCandidates = [];
    for (const parent of uniqueParents) {
      if (prominentFragmentCandidates.length >= maxCandidates) break;
      const parentStyle = styleSnapshot(parent);
      const fragments = parent.querySelectorAll("span,em,strong,i,b,mark,u");
      for (const fragment of fragments) {
        if (prominentFragmentCandidates.length >= maxCandidates) break;
        if (!visible(fragment)) continue;
        const text = compact(fragment.textContent, 100);
        const words = text ? text.split(/\s+/).length : 0;
        if (!text || words > 4 || text.length > 48) continue;
        const fragmentStyle = styleSnapshot(fragment);
        const reasons = [];
        if (fragmentStyle.color !== parentStyle.color) reasons.push("foreground-color-change");
        if (fragmentStyle.font_family !== parentStyle.font_family) reasons.push("font-family-change");
        if (fragmentStyle.font_style !== parentStyle.font_style) reasons.push("font-style-change");
        if (fragmentStyle.font_weight !== parentStyle.font_weight) reasons.push("font-weight-change");
        if (
          fragmentStyle.text_decoration_line !== parentStyle.text_decoration_line &&
          fragmentStyle.text_decoration_line !== "none"
        ) {
          reasons.push("text-decoration-change");
        }
        if (
          fragmentStyle.background_image !== parentStyle.background_image &&
          fragmentStyle.background_image !== "none"
        ) {
          reasons.push("background-image-or-gradient");
        }
        if (
          fragmentStyle.background_color !== parentStyle.background_color &&
          !["rgba(0, 0, 0, 0)", "transparent"].includes(fragmentStyle.background_color)
        ) {
          reasons.push("background-color-change");
        }
        if (reasons.length) {
          prominentFragmentCandidates.push({
            classification: "advisory-candidate",
            advisory_only: true,
            selector: selectorFor(fragment),
            parent_selector: selectorFor(parent),
            text,
            parent_text: compact(parent.textContent, 220),
            reasons,
            parent_style: parentStyle,
            fragment_style: fragmentStyle,
          });
        }
      }
    }

    return {
      title: compact(document.title, 500),
      lang: compact(document.documentElement.lang, 50) || null,
      direction:
        compact(
          document.documentElement.dir ||
            getComputedStyle(document.documentElement).direction,
          20,
        ) ||
        null,
      headings,
      landmarks,
      route_silhouette: routeSilhouette,
      layout: {
        document: {
          client_width: document.documentElement.clientWidth,
          client_height: document.documentElement.clientHeight,
          scroll_width: document.documentElement.scrollWidth,
          scroll_height: document.documentElement.scrollHeight,
        },
        horizontal_overflow:
          document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
        overflow_candidates: overflowCandidates,
      },
      images,
      fonts,
      typography_sampling: typographySampling.evidence,
      typography_samples: typographySamples,
      controls,
      prominent_fragment_candidates: prominentFragmentCandidates,
    };
  }, { maxCandidates: MAX_CANDIDATES });
}

function pixels(raw) {
  const value = Number.parseFloat(String(raw ?? "0"));
  return Number.isFinite(value) ? value : 0;
}

function indicatorEvidence(baseline, focused) {
  const outlineVisible =
    focused.outline_style !== "none" &&
    pixels(focused.outline_width) >= 1 &&
    !["rgba(0, 0, 0, 0)", "transparent"].includes(focused.outline_color);
  const shadowVisible =
    focused.box_shadow !== "none" &&
    (!baseline || focused.box_shadow !== baseline.box_shadow);
  const colorChange =
    Boolean(baseline) &&
    (focused.border_color !== baseline.border_color ||
      focused.background_color !== baseline.background_color);
  const foregroundChange =
    Boolean(baseline) && focused.color !== baseline.color;
  return {
    candidate_present:
      outlineVisible || shadowVisible || colorChange || foregroundChange,
    reasons: [
      ...(outlineVisible ? ["visible-outline"] : []),
      ...(shadowVisible ? ["changed-box-shadow"] : []),
      ...(colorChange ? ["changed-border-or-background"] : []),
      ...(foregroundChange ? ["changed-foreground-color"] : []),
    ],
  };
}

async function traverseFocus(page, controls) {
  const baseline = new Map(
    controls.map((control) => [control.selector, control.baseline_focus_style]),
  );
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
    window.scrollTo(0, 0);
  });
  const maximum = Math.min(80, Math.max(10, controls.length + 10));
  const seen = new Set();
  const steps = [];
  let cycleDetected = false;

  for (let index = 0; index < maximum; index += 1) {
    await page.keyboard.press("Tab");
    const step = await page.evaluate(() => {
      const element = document.activeElement;
      if (!(element instanceof Element) || element === document.body || element === document.documentElement) {
        return null;
      }
      const compact = (value, limit = 200) =>
        String(value ?? "").replace(/\s+/g, " ").trim().slice(0, limit);
      const selectorFor = (node) => {
        if (node.id) return `#${CSS.escape(node.id)}`;
        const parts = [];
        let current = node;
        while (current && current !== document.documentElement && parts.length < 6) {
          let part = current.localName;
          const parent = current.parentElement;
          if (parent) {
            const siblings = [...parent.children].filter((item) => item.localName === current.localName);
            if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(current) + 1})`;
          }
          parts.unshift(part);
          current = parent;
        }
        return parts.join(" > ");
      };
      const roleFor = (node) => {
        const explicit = node.getAttribute("role");
        if (explicit) return explicit;
        if (node.matches("a[href]")) return "link";
        if (node.matches("button,summary")) return "button";
        if (node.matches("select")) return "combobox";
        if (node.matches("textarea")) return "textbox";
        if (node instanceof HTMLInputElement) {
          const type = (node.type || "text").toLowerCase();
          if (["button", "submit", "reset", "image"].includes(type)) return "button";
          if (type === "checkbox") return "checkbox";
          if (type === "radio") return "radio";
          if (type === "range") return "slider";
          return "textbox";
        }
        return null;
      };
      const nameFor = (node) => {
        const ariaLabel = node.getAttribute("aria-label");
        if (ariaLabel) return compact(ariaLabel);
        const labelledBy = node.getAttribute("aria-labelledby");
        if (labelledBy) {
          const labelledText = labelledBy
            .split(/\s+/)
            .map((id) => document.getElementById(id)?.textContent ?? "")
            .join(" ");
          if (compact(labelledText)) return compact(labelledText);
        }
        if ("labels" in node && node.labels?.length) {
          const labelText = [...node.labels].map((label) => label.textContent).join(" ");
          if (compact(labelText)) return compact(labelText);
        }
        if (
          node instanceof HTMLInputElement &&
          ["button", "submit", "reset"].includes(node.type) &&
          compact(node.value)
        ) {
          return compact(node.value);
        }
        return compact(
          node.textContent ||
            node.getAttribute("alt") ||
            node.getAttribute("title") ||
            node.getAttribute("value"),
        );
      };
      const style = getComputedStyle(element);
      const cssValue = (value, limit = 500) => {
        const raw = String(value ?? "");
        if (raw.includes("data:")) return "data:[computed-style payload omitted]";
        return raw.slice(0, limit);
      };
      return {
        selector: selectorFor(element),
        tag: element.localName,
        role: roleFor(element),
        name: nameFor(element),
        focus_visible_matches: element.matches(":focus-visible"),
        focused_style: {
          color: cssValue(style.color),
          background_color: cssValue(style.backgroundColor),
          background_image: cssValue(style.backgroundImage),
          font_family: cssValue(style.fontFamily),
          font_weight: cssValue(style.fontWeight),
          font_style: cssValue(style.fontStyle),
          font_size: cssValue(style.fontSize),
          text_decoration_line: cssValue(style.textDecorationLine),
          outline_color: cssValue(style.outlineColor),
          outline_style: cssValue(style.outlineStyle),
          outline_width: cssValue(style.outlineWidth),
          box_shadow: cssValue(style.boxShadow),
          border_color: cssValue(style.borderColor),
        },
      };
    });
    if (!step) break;
    if (seen.has(step.selector)) {
      cycleDetected = true;
      break;
    }
    seen.add(step.selector);
    const baselineStyle = baseline.get(step.selector) ?? null;
    steps.push({
      order: steps.length + 1,
      ...step,
      baseline_style: baselineStyle,
      indicator_evidence: indicatorEvidence(baselineStyle, step.focused_style),
    });
  }
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    window.scrollTo(0, 0);
  });
  return {
    attempted: true,
    maximum_steps: maximum,
    observed_steps: steps.length,
    cycle_detected: cycleDetected,
    truncated: steps.length >= maximum,
    steps,
    interpretation:
      "Computed-style differences are advisory focus-indicator evidence, not a contrast or accessibility pass.",
  };
}

async function waitForPageAssets(page, timeoutMs) {
  const bounded = Math.min(timeoutMs, 10000);
  await page.evaluate(async (milliseconds) => {
    const timeout = new Promise((resolve) => setTimeout(resolve, milliseconds));
    const fonts =
      document.fonts?.ready?.catch?.(() => undefined) ?? Promise.resolve();
    const images = Promise.allSettled(
      [...document.images].map((image) => {
        if (image.complete) return Promise.resolve();
        return image.decode?.() ?? new Promise((resolve) => {
          image.addEventListener("load", resolve, { once: true });
          image.addEventListener("error", resolve, { once: true });
        });
      }),
    );
    await Promise.race([Promise.allSettled([fonts, images]), timeout]);
  }, bounded);
}

async function sweepPageForRendering(page) {
  return await page.evaluate(async () => {
    const root = document.documentElement;
    const priorBehavior = root.style.scrollBehavior;
    root.style.scrollBehavior = "auto";
    const visited = [];
    try {
      const viewport = Math.max(window.innerHeight, 320);
      for (let index = 0; index < 80; index += 1) {
        const height = Math.max(
          root.scrollHeight,
          document.body?.scrollHeight ?? 0,
        );
        const maximum = Math.max(0, height - window.innerHeight);
        const target = Math.min(
          maximum,
          index * Math.max(320, Math.floor(viewport * 0.82)),
        );
        window.scrollTo(0, target);
        visited.push(target);
        await new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        );
        if (target >= maximum) break;
      }
    } finally {
      window.scrollTo(0, 0);
      root.style.scrollBehavior = priorBehavior;
      await new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      );
    }
    return {
      positions: visited.length,
      maximum_y: visited.length ? visited[visited.length - 1] : 0,
    };
  });
}

async function sha256File(filePath) {
  const payload = await readFile(filePath);
  return createHash("sha256").update(payload).digest("hex");
}

async function pngDimensions(filePath) {
  const payload = await readFile(filePath);
  if (
    payload.length < 24 ||
    payload.toString("hex", 0, 8) !== "89504e470d0a1a0a"
  ) {
    throw new RenderReviewError(
      "invalid-screenshot",
      "Playwright did not produce a valid PNG screenshot.",
      { path: filePath },
      4,
    );
  }
  return {
    width: payload.readUInt32BE(16),
    height: payload.readUInt32BE(20),
  };
}

function artifactPath(...parts) {
  return parts.join("/");
}

async function applyProfileReviewModes(page, profile) {
  let textSpacingStatus = "not-requested";
  if (profile.text_spacing === "wcag-1.4.12") {
    await page.addStyleTag({
      content: `
        * {
          line-height: 1.5 !important;
          letter-spacing: 0.12em !important;
          word-spacing: 0.16em !important;
        }
        p {
          margin-bottom: 2em !important;
        }
      `,
    });
    textSpacingStatus = "applied-browser-css-override";
  }
  return {
    text_spacing: {
      requested: profile.text_spacing,
      evidence_status: textSpacingStatus,
    },
    zoom: {
      requested: profile.zoom,
      evidence_status:
        profile.zoom === "none"
          ? "not-requested"
          : "manual-required-not-simulated",
    },
  };
}

async function assertSafeClickTarget(locator, page, allowedOrigin) {
  const metadata = await locator.evaluate((element) => {
    const tag = element.tagName.toLowerCase();
    const type =
      "type" in element && typeof element.type === "string"
        ? element.type.toLowerCase()
        : "";
    const anchor = element.closest("a[href]");
    return {
      tag,
      type,
      href: anchor?.href ?? null,
      target: anchor?.target ?? null,
      download: anchor?.hasAttribute("download") ?? false,
    };
  });
  if (
    (metadata.tag === "button" && (!metadata.type || metadata.type === "submit")) ||
    (metadata.tag === "input" && ["submit", "image"].includes(metadata.type))
  ) {
    throw new RenderReviewError(
      "interaction-submit-blocked",
      "Capture-manifest click actions cannot activate form submission controls.",
      {},
    );
  }
  if (metadata.href) {
    let destination;
    try {
      destination = new URL(metadata.href, page.url());
    } catch {
      throw new RenderReviewError(
        "interaction-navigation-blocked",
        "The click target has an invalid navigation destination.",
        {},
      );
    }
    if (
      destination.origin !== allowedOrigin ||
      !["http:", "https:"].includes(destination.protocol) ||
      metadata.target === "_blank" ||
      metadata.download
    ) {
      throw new RenderReviewError(
        "interaction-cross-origin-navigation",
        "Capture-manifest clicks cannot navigate cross-origin, open a new context, or download a file.",
        {},
      );
    }
  }
}

function interactionEvidenceFor(scenario) {
  return {
    policy:
      "single-match-allowlisted-actions-local-state-change-only-no-submit-no-popup-no-cross-origin",
    requested_steps: scenario.interactions.length,
    completed_steps: 0,
    status: scenario.interactions.length ? "pending" : "not-requested",
    failed_step: null,
  };
}

async function executeInteractionSequence({
  page,
  scenario,
  networkPolicy,
  options,
  evidence,
}) {
  if (!scenario.interactions.length) return;
  let popupAttempted = false;
  const onPopup = (popup) => {
    popupAttempted = true;
    popup.close().catch(() => undefined);
  };
  page.on("popup", onPopup);
  try {
    for (let index = 0; index < scenario.interactions.length; index += 1) {
      const interaction = scenario.interactions[index];
      evidence.failed_step = index + 1;
      let locator;
      try {
        locator = page.locator(interaction.selector);
        const count = await locator.count();
        if (count !== 1) {
          throw new RenderReviewError(
            "interaction-selector-count",
            "Each interaction selector must resolve to exactly one element.",
            { action_index: index, matched_count: Math.min(count, 1000) },
          );
        }
        const timeout = Math.min(options.timeoutMs, 5000);
        if (interaction.action === "click") {
          await assertSafeClickTarget(
            locator,
            page,
            networkPolicy.allowed_origin,
          );
          await locator.click({ timeout });
        } else if (interaction.action === "focus") {
          await locator.focus({ timeout });
        } else if (interaction.action === "fill") {
          await locator.fill(interaction.value, { timeout });
        } else if (interaction.action === "select") {
          const selected = await locator.selectOption(
            { value: interaction.value },
            { timeout },
          );
          if (selected.length !== 1) {
            throw new RenderReviewError(
              "interaction-select-value-missing",
              "The select interaction did not match exactly one option value.",
              { action_index: index },
            );
          }
        } else if (interaction.action === "check") {
          await locator.check({ timeout });
        }
      } catch (error) {
        evidence.status = "failed";
        if (error instanceof RenderReviewError) throw error;
        throw new RenderReviewError(
          "interaction-action-failed",
          sanitizeDiagnosticText(error?.message ?? error).slice(0, 1000),
          { action_index: index },
        );
      }
      if (popupAttempted) {
        evidence.status = "failed";
        throw new RenderReviewError(
          "interaction-popup-blocked",
          "An interaction attempted to open a new browsing context.",
          { action_index: index },
        );
      }
      let currentOrigin;
      try {
        currentOrigin = new URL(page.url()).origin;
      } catch {
        currentOrigin = null;
      }
      if (currentOrigin !== networkPolicy.allowed_origin) {
        evidence.status = "failed";
        throw new RenderReviewError(
          "interaction-cross-origin-navigation",
          "An interaction left the allowed capture origin.",
          { action_index: index },
        );
      }
      evidence.completed_steps += 1;
      evidence.failed_step = null;
    }
    evidence.status = "complete";
  } finally {
    page.off("popup", onPopup);
  }
}

async function captureOne({
  browser,
  route,
  scenario,
  profile,
  scenarioIndex,
  profileIndex,
  staging,
  options,
  networkPolicy,
  sensitivePaths,
  artifactBudget,
}) {
  const id = `${scenario.id}-${profile.id}`;
  const screenshotRelative = artifactPath(
    "screenshots",
    `${String(scenarioIndex + 1).padStart(2, "0")}-${String(profileIndex + 1).padStart(2, "0")}-${id}.png`,
  );
  const screenshotAbsolute = path.join(staging, ...screenshotRelative.split("/"));
  const videoRawDir = path.join(staging, "videos", ".raw");
  const contextOptions = {
    acceptDownloads: false,
    viewport: {
      width: profile.viewport.width,
      height: profile.viewport.height,
    },
    deviceScaleFactor: profile.viewport.device_scale_factor,
    isMobile: profile.is_mobile,
    hasTouch: profile.has_touch,
    colorScheme: profile.color_scheme,
    reducedMotion: profile.reduced_motion,
    forcedColors: profile.forced_colors,
    locale: "en-US",
    timezoneId: "UTC",
    serviceWorkers: "block",
    ...(options.video
      ? {
          recordVideo: {
            dir: videoRawDir,
            size: {
              width: profile.viewport.width,
              height: profile.viewport.height,
            },
          },
        }
      : {}),
  };
  const context = await browser.newContext(contextOptions);
  const consoleEntries = [];
  const pageErrors = [];
  const requestFailures = [];
  const httpFailures = [];
  const blockedOutbound = [];
  const eventCounts = {
    console: { truncated: 0 },
    page: { truncated: 0 },
    request: { truncated: 0 },
    http: { truncated: 0 },
    blocked: { truncated: 0 },
  };

  await context.route("**/*", async (intercepted) => {
    const request = intercepted.request();
    const rawUrl = request.url();
    let parsed;
    try {
      parsed = new URL(rawUrl);
    } catch {
      await intercepted.abort("blockedbyclient");
      boundedPush(
        blockedOutbound,
        {
          method: request.method(),
          url: sanitizeUrl(rawUrl),
          resource_type: request.resourceType(),
          reason: "invalid-url",
        },
        eventCounts.blocked,
      );
      return;
    }
    if (["data:", "blob:", "about:"].includes(parsed.protocol)) {
      await intercepted.continue();
      return;
    }
    const sameOrigin = parsed.origin === networkPolicy.allowed_origin;
    if (networkPolicy.mode === "local-same-origin-only" && !sameOrigin) {
      boundedPush(
        blockedOutbound,
        {
          method: request.method(),
          url: sanitizeUrl(rawUrl),
          resource_type: request.resourceType(),
          reason: "local-cross-origin-blocked",
        },
        eventCounts.blocked,
      );
      await intercepted.abort("blockedbyclient");
      return;
    }
    if (networkPolicy.mode === "remote-credential-isolated" && !sameOrigin) {
      let topLevelNavigation = false;
      try {
        topLevelNavigation =
          request.isNavigationRequest() && request.frame().parentFrame() === null;
      } catch {
        topLevelNavigation = false;
      }
      const serverRedirect = Boolean(request.redirectedFrom());
      if (!topLevelNavigation || !serverRedirect) {
        boundedPush(
          blockedOutbound,
          {
            method: request.method(),
            url: sanitizeUrl(rawUrl),
            resource_type: request.resourceType(),
            reason: topLevelNavigation
              ? "remote-cross-origin-navigation-blocked"
              : "remote-cross-origin-subresource-blocked",
          },
          eventCounts.blocked,
        );
        await intercepted.abort("blockedbyclient");
        return;
      }
      const sensitiveQuery = [...parsed.searchParams.keys()].some((key) =>
        /(?:auth|credential|key|password|secret|signature|sig|token)/iu.test(key),
      );
      if (parsed.username || parsed.password || sensitiveQuery) {
        boundedPush(
          blockedOutbound,
          {
            method: request.method(),
            url: sanitizeUrl(rawUrl),
            resource_type: request.resourceType(),
            reason: "cross-origin-credential-bearing-url-blocked",
          },
          eventCounts.blocked,
        );
        await intercepted.abort("blockedbyclient");
        return;
      }
      const headers = { ...request.headers() };
      for (const key of Object.keys(headers)) {
        if (
          ["authorization", "cookie", "proxy-authorization"].includes(
            key.toLowerCase(),
          )
        ) {
          delete headers[key];
        }
      }
      const refererKey = Object.keys(headers).find(
        (key) => key.toLowerCase() === "referer",
      );
      if (refererKey) headers[refererKey] = `${networkPolicy.allowed_origin}/`;
      await intercepted.continue({ headers });
      return;
    }
    await intercepted.continue();
  });
  if (typeof context.routeWebSocket === "function") {
    await context.routeWebSocket(/.*/u, async (webSocket) => {
      const rawUrl = webSocket.url();
      let normalizedOrigin = null;
      try {
        const parsed = new URL(rawUrl);
        if (parsed.protocol === "ws:") parsed.protocol = "http:";
        if (parsed.protocol === "wss:") parsed.protocol = "https:";
        normalizedOrigin = parsed.origin;
      } catch {
        normalizedOrigin = null;
      }
      const sameOrigin = normalizedOrigin === networkPolicy.allowed_origin;
      if (sameOrigin) {
        webSocket.connectToServer();
        return;
      }
      boundedPush(
        blockedOutbound,
        {
          method: "WEBSOCKET",
          url: sanitizeUrl(rawUrl),
          resource_type: "websocket",
          reason:
            networkPolicy.mode === "local-same-origin-only"
              ? "local-cross-origin-websocket-blocked"
              : "remote-cross-origin-websocket-blocked",
        },
        eventCounts.blocked,
      );
      await webSocket.close({
        code: 1008,
        reason: "Cross-origin WebSocket blocked by rendered-review policy",
      });
    });
  }

  const page = await context.newPage();

  page.on("console", (message) => {
    const location = message.location();
    boundedPush(
      consoleEntries,
      {
        type: message.type(),
        text: sanitizeDiagnosticText(
          message.text(),
          sensitivePaths,
        ).slice(0, 2000),
        location: {
          url: safeEventUrl(location.url),
          line: location.lineNumber ?? null,
          column: location.columnNumber ?? null,
        },
      },
      eventCounts.console,
    );
  });
  page.on("pageerror", (error) => {
    boundedPush(
      pageErrors,
      {
        name: sanitizeDiagnosticText(error.name || "Error", sensitivePaths).slice(
          0,
          200,
        ),
        message: sanitizeDiagnosticText(
          error.message || error,
          sensitivePaths,
        ).slice(0, 4000),
      },
      eventCounts.page,
    );
  });
  page.on("requestfailed", (request) => {
    boundedPush(
      requestFailures,
      {
        method: request.method(),
        url: safeEventUrl(request.url()),
        failure: sanitizeDiagnosticText(
          request.failure()?.errorText ?? "unknown",
          sensitivePaths,
        ).slice(0, 500),
        resource_type: request.resourceType(),
      },
      eventCounts.request,
    );
  });
  page.on("response", (response) => {
    if (response.status() >= 400) {
      boundedPush(
        httpFailures,
        {
          status: response.status(),
          status_text: sanitizeDiagnosticText(
            response.statusText(),
            sensitivePaths,
          ).slice(0, 200),
          url: safeEventUrl(response.url()),
          resource_type: response.request().resourceType(),
        },
        eventCounts.http,
      );
    }
  });

  let responseStatus = null;
  let finalUrl = route.url;
  let documentInspection = null;
  let focus = null;
  let screenshot = null;
  let video = null;
  let failure = null;
  let videoHandle = null;
  let reviewMode = {
    text_spacing: {
      requested: profile.text_spacing,
      evidence_status: "not-applied-capture-failed",
    },
    zoom: {
      requested: profile.zoom,
      evidence_status:
        profile.zoom === "none"
          ? "not-requested"
          : "manual-required-not-simulated",
    },
  };
  const interactionEvidence = interactionEvidenceFor(scenario);

  try {
    const response = await page.goto(route.url, {
      waitUntil: "domcontentloaded",
      timeout: options.timeoutMs,
    });
    responseStatus = response?.status() ?? null;
    finalUrl = page.url();
    if (responseStatus === null) {
      failure ??= {
        code: "main-document-response-missing",
        message: "The main document did not produce an HTTP response.",
      };
    } else if (responseStatus >= 400) {
      failure ??= {
        code: "main-document-http-error",
        message: `The main document returned HTTP ${responseStatus}.`,
      };
    }
    try {
      if (new URL(finalUrl).origin !== new URL(route.url).origin) {
        failure ??= {
          code: "unexpected-cross-origin-redirect",
          message:
            "The main document redirected to an unexpected origin; the capture is incomplete.",
        };
      }
    } catch {
      failure ??= {
        code: "invalid-final-url",
        message: "The final page URL could not be validated.",
      };
    }
    await waitForPageAssets(page, options.timeoutMs);
    if (options.settleMs) await page.waitForTimeout(options.settleMs);
    if (options.scrollSweep) {
      await sweepPageForRendering(page);
      await waitForPageAssets(page, options.timeoutMs);
      if (options.settleMs) await page.waitForTimeout(options.settleMs);
    }
    reviewMode = await applyProfileReviewModes(page, profile);
    await executeInteractionSequence({
      page,
      scenario,
      networkPolicy,
      options,
      evidence: interactionEvidence,
    });
    if (scenario.interactions.length) {
      await waitForPageAssets(page, options.timeoutMs);
      if (options.settleMs) await page.waitForTimeout(options.settleMs);
    }
    documentInspection = await inspectDocument(page);
    const pageHeight = documentInspection.layout.document.scroll_height;
    const projectedPixels =
      Math.max(
        documentInspection.layout.document.scroll_width,
        profile.viewport.width,
      ) *
      Math.max(pageHeight, profile.viewport.height) *
      profile.viewport.device_scale_factor ** 2;
    if (pageHeight > options.limits.page_height_css_px) {
      failure ??= {
        code: "page-height-limit-exceeded",
        message: `The page height exceeded the ${options.limits.page_height_css_px} CSS-pixel capture limit.`,
      };
    } else if (projectedPixels > options.limits.screenshot_pixels) {
      failure ??= {
        code: "screenshot-pixel-limit-exceeded",
        message: `The projected full-page screenshot exceeded the ${options.limits.screenshot_pixels}-pixel limit.`,
      };
    } else {
      await mkdir(path.dirname(screenshotAbsolute), { recursive: true });
      await page.screenshot({
        path: screenshotAbsolute,
        fullPage: true,
        animations: "disabled",
        caret: "hide",
        type: "png",
      });
      const screenshotInfo = await stat(screenshotAbsolute);
      if (screenshotInfo.size > options.limits.screenshot_bytes) {
        await rm(screenshotAbsolute, { force: true });
        failure ??= {
          code: "screenshot-byte-limit-exceeded",
          message: `The PNG exceeded the ${options.limits.screenshot_bytes}-byte per-screenshot limit.`,
        };
      } else if (
        artifactBudget.used + screenshotInfo.size >
        artifactBudget.maximum
      ) {
        await rm(screenshotAbsolute, { force: true });
        failure ??= {
          code: "artifact-byte-limit-exceeded",
          message: `The capture would exceed the reserved ${artifactBudget.maximum}-byte capture-artifact budget.`,
        };
      } else {
        artifactBudget.used += screenshotInfo.size;
        const dimensions = await pngDimensions(screenshotAbsolute);
        screenshot = {
          path: screenshotRelative,
          sha256: await sha256File(screenshotAbsolute),
          media_type: "image/png",
          bytes: screenshotInfo.size,
          pixel_width: dimensions.width,
          pixel_height: dimensions.height,
        };
      }
    }
    focus = await traverseFocus(page, documentInspection.controls);
    if (options.video && options.videoDurationMs) {
      await page.waitForTimeout(options.videoDurationMs);
    }
    videoHandle = page.video();
  } catch (error) {
    failure ??= {
      code:
        error instanceof RenderReviewError
          ? error.code
          : "capture-failed",
      message: sanitizeDiagnosticText(
        error?.message ?? error,
        sensitivePaths,
      ).slice(0, 4000),
    };
    try {
      finalUrl = page.url();
    } catch {
      finalUrl = route.url;
    }
  } finally {
    try {
      if (!page.isClosed()) await page.close();
    } catch {
      // Preserve the primary capture result.
    }
    try {
      await context.close();
    } catch (error) {
      failure ??= {
        code: "context-close-failed",
        message: sanitizeDiagnosticText(
          error?.message ?? error,
          sensitivePaths,
        ).slice(0, 4000),
      };
    }
  }

  if (options.video && videoHandle) {
    try {
      const rawPath = await videoHandle.path();
      const videoRelative = artifactPath(
        "videos",
        `${String(scenarioIndex + 1).padStart(2, "0")}-${String(profileIndex + 1).padStart(2, "0")}-${id}.webm`,
      );
      const videoAbsolute = path.join(staging, ...videoRelative.split("/"));
      await mkdir(path.dirname(videoAbsolute), { recursive: true });
      await copyFile(rawPath, videoAbsolute);
      const videoInfo = await stat(videoAbsolute);
      if (
        artifactBudget.used + videoInfo.size >
        artifactBudget.maximum
      ) {
        await rm(videoAbsolute, { force: true });
        failure ??= {
          code: "artifact-byte-limit-exceeded",
          message: `The video would exceed the reserved ${artifactBudget.maximum}-byte capture-artifact budget.`,
        };
      } else {
        artifactBudget.used += videoInfo.size;
        video = {
          path: videoRelative,
          sha256: await sha256File(videoAbsolute),
          media_type: "video/webm",
          bytes: videoInfo.size,
          duration_ms: options.videoDurationMs,
        };
      }
    } catch (error) {
      failure ??= {
        code: "video-capture-failed",
        message: sanitizeDiagnosticText(
          error?.message ?? error,
          sensitivePaths,
        ).slice(0, 4000),
      };
    }
  }

  const emptyInspection = {
    title: "",
    lang: null,
    direction: null,
    headings: [],
    landmarks: [],
    route_silhouette: [],
    layout: {
      document: {
        client_width: 0,
        client_height: 0,
        scroll_width: 0,
        scroll_height: 0,
      },
      horizontal_overflow: false,
      overflow_candidates: [],
    },
    images: [],
    fonts: [],
    typography_sampling: {
      strategy: "semantic-role-and-document-position-stratified-v1",
      candidate_count: 0,
      sampled_count: 0,
      truncated: false,
      role_counts: Object.fromEntries(
        [
          "heading",
          "navigation",
          "control",
          "label",
          "caption",
          "code",
          "list-or-definition",
          "body",
          "other",
        ].map((role) => [role, { candidate_count: 0, sampled_count: 0 }]),
      ),
    },
    typography_samples: [],
    controls: [],
    prominent_fragment_candidates: [],
  };
  if (interactionEvidence.status === "pending") {
    interactionEvidence.status = "not-attempted";
    interactionEvidence.failed_step = null;
  }
  return {
    id,
    route_id: route.id,
    scenario_id: scenario.id,
    route_label: scenario.route_label,
    state_label: scenario.state_label,
    profile_id: profile.id,
    capture_status: failure ? "failed" : "complete",
    failure,
    requested_url: sanitizeUrl(route.url),
    final_url: sanitizeUrl(finalUrl),
    http_status: responseStatus,
    viewport: profile.viewport,
    preferences: {
      color_scheme: profile.color_scheme,
      reduced_motion: profile.reduced_motion,
      forced_colors: profile.forced_colors,
      is_mobile: profile.is_mobile,
      has_touch: profile.has_touch,
      pointer: profile.pointer,
      hover: profile.hover,
      input_modalities: profile.input_modalities,
      locale: "en-US",
      timezone: "UTC",
    },
    review_mode: reviewMode,
    interaction: interactionEvidence,
    screenshot,
    video,
    console: {
      entries: consoleEntries,
      truncated_count: eventCounts.console.truncated,
    },
    page_errors: {
      entries: pageErrors,
      truncated_count: eventCounts.page.truncated,
    },
    network: {
      request_failures: requestFailures,
      request_failures_truncated_count: eventCounts.request.truncated,
      http_failures: httpFailures,
      http_failures_truncated_count: eventCounts.http.truncated,
      blocked_outbound: blockedOutbound,
      blocked_outbound_truncated_count: eventCounts.blocked.truncated,
    },
    document: documentInspection ?? emptyInspection,
    focus:
      focus ?? {
        attempted: false,
        maximum_steps: 0,
        observed_steps: 0,
        cycle_detected: false,
        truncated: false,
        steps: [],
        interpretation:
          "Focus traversal was not performed because capture execution failed.",
      },
  };
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function buildContactSheet(report) {
  const cards = report.captures
    .map((capture) => {
      const screenshot = capture.screenshot
        ? `<a href="${escapeHtml(capture.screenshot.path)}"><img src="${escapeHtml(capture.screenshot.path)}" alt="Screenshot for ${escapeHtml(capture.id)}"></a>`
        : `<div class="missing">Screenshot unavailable</div>`;
      const counts = {
        console: capture.console.entries.length,
        page_errors: capture.page_errors.entries.length,
        request_failures: capture.network.request_failures.length,
        http_failures: capture.network.http_failures.length,
        blocked_outbound: capture.network.blocked_outbound.length,
        overflow: capture.document.layout.overflow_candidates.length,
        fragment_candidates: capture.document.prominent_fragment_candidates.length,
        typography_candidates: capture.document.typography_sampling.candidate_count,
        typography_sampled: capture.document.typography_sampling.sampled_count,
        typography_truncated: capture.document.typography_sampling.truncated,
      };
      return `<article>
  <header>
    <h2>${escapeHtml(capture.id)}</h2>
    <p>${escapeHtml(capture.route_label)} / ${escapeHtml(capture.state_label)}</p>
    <p>${escapeHtml(capture.capture_status)} · ${capture.viewport.width}×${capture.viewport.height} · ${escapeHtml(capture.preferences.color_scheme)} · motion ${escapeHtml(capture.preferences.reduced_motion)} · forced colors ${escapeHtml(capture.preferences.forced_colors)}</p>
    <p>Text spacing: ${escapeHtml(capture.review_mode.text_spacing.evidence_status)} / zoom: ${escapeHtml(capture.review_mode.zoom.evidence_status)} / interactions: ${escapeHtml(capture.interaction.status)}</p>
    <p class="url">${escapeHtml(capture.final_url)}</p>
  </header>
  ${screenshot}
  <dl>
    ${Object.entries(counts).map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${value}</dd></div>`).join("")}
  </dl>
</article>`;
    })
    .join("\n");
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Design DNA rendered review · ${escapeHtml(report.build.id)}</title>
<style>
:root{color-scheme:light dark;font-family:system-ui,sans-serif;background:#111;color:#f5f5f5}
body{margin:0;padding:24px}header.page{max-width:80rem;margin:0 auto 24px}
.boundary{padding:12px;border:1px solid #d4a72c;background:#2a220d}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:20px;max-width:96rem;margin:auto}
article{border:1px solid #555;background:#1b1b1b;padding:14px;min-width:0}
h1,h2,p{margin-block:0 10px}.url{overflow-wrap:anywhere;color:#bbb;font-size:.8rem}
img{display:block;width:100%;height:min(44rem,70vh);object-fit:contain;object-position:top;background:#fff;border:1px solid #444}
.missing{min-height:12rem;display:grid;place-items:center;background:#2a1515}
dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin:12px 0 0}
dl div{display:flex;justify-content:space-between;gap:8px;border-top:1px solid #444;padding-top:5px}
dt{color:#bbb}dd{margin:0;font-variant-numeric:tabular-nums}
</style>
</head>
<body>
<header class="page">
  <h1>Rendered review · ${escapeHtml(report.build.id)}</h1>
  <p class="boundary">Potentially sensitive review evidence. Automated capture is separate from human review. Screenshots can contain personal or confidential page content and are not pixel-redacted. This sheet does not establish visual quality, accessibility conformance, truth, or authorship.</p>
  <p>${report.captures.length} captures · schema ${report.schema_version} · ${escapeHtml(report.quality_status)}</p>
</header>
<main>${cards}</main>
</body>
</html>`;
}

async function promoteOutput({
  staging,
  transaction,
  output,
  outputState,
  replace,
  target,
}) {
  await recheckOutput(output, outputState, replace, target);
  if (!outputState.exists) {
    await rename(staging, output);
    return;
  }

  const previous = path.join(transaction.root, "validated-previous-output");
  await rename(output, previous);
  transaction.preservePrior = true;
  const movedIdentity = await directoryIdentity(previous);
  if (!sameDirectoryIdentity(movedIdentity, outputState.identity, false)) {
    await rename(previous, output).catch(() => undefined);
    transaction.preservePrior = await pathExists(previous);
    throw new RenderReviewError(
      "output-identity-changed",
      "The output identity changed at the replacement commit boundary.",
      { output: "[output path omitted]" },
      4,
    );
  }
  const movedFingerprint = await fingerprintOwnedOutput(previous);
  if (!sameTreeFingerprint(movedFingerprint, outputState.tree_fingerprint)) {
    await rename(previous, output).catch(() => undefined);
    transaction.preservePrior = await pathExists(previous);
    throw new RenderReviewError(
      "output-content-changed",
      "The moved prior output failed its exact content-integrity check and was preserved.",
      { preserved: true },
      4,
    );
  }

  try {
    await rename(staging, output);
  } catch (error) {
    await rename(previous, output).catch(() => undefined);
    transaction.preservePrior = await pathExists(previous);
    throw new RenderReviewError(
      "output-promotion-failed",
      "The new evidence could not be promoted; the prior owned output was preserved.",
      { cause: sanitizeDiagnosticText(error?.message ?? error) },
      4,
    );
  }

  const priorBeforeDelete = await directoryIdentity(previous);
  if (!sameDirectoryIdentity(priorBeforeDelete, outputState.identity, false)) {
    transaction.preservePrior = true;
    throw new RenderReviewError(
      "prior-output-identity-changed",
      "The moved prior output changed identity and was preserved rather than deleted.",
      { preserved: true },
      4,
    );
  }
  const priorFingerprint = await fingerprintOwnedOutput(previous);
  if (!sameTreeFingerprint(priorFingerprint, outputState.tree_fingerprint)) {
    transaction.preservePrior = true;
    throw new RenderReviewError(
      "prior-output-content-changed",
      "The moved prior output changed contents and was preserved rather than deleted.",
      { preserved: true },
      4,
    );
  }
  await rm(previous, { recursive: true, force: false });
  transaction.preservePrior = false;
}

async function removeOwnedTransaction(transaction) {
  if (!transaction?.root || transaction.preservePrior) return false;
  const resolved = path.resolve(transaction.root);
  const expectedParent = path.resolve(transaction.parent);
  if (
    !isInside(resolved, expectedParent) ||
    !path.basename(resolved).startsWith(
      `.${transaction.outputBase}.design-dna-transaction-`,
    )
  ) {
    throw new RenderReviewError(
      "unsafe-transaction-cleanup",
      "The transaction directory failed its ownership boundary check.",
      { transaction: "[transaction path omitted]" },
      4,
    );
  }
  const info = await lstat(resolved).catch(() => null);
  if (!info) return true;
  if (!info.isDirectory() || info.isSymbolicLink()) {
    throw new RenderReviewError(
      "unsafe-transaction-cleanup",
      "The transaction path changed type and was preserved.",
      { transaction: "[transaction path omitted]" },
      4,
    );
  }
  await rm(resolved, { recursive: true, force: false });
  return true;
}

async function prepareRoutes(target, additions, localServer) {
  if (target.kind === "remote-url") {
    return buildRemoteRoutes(target, additions);
  }
  if (target.kind === "local-file") {
    if (additions.length) {
      throw new RenderReviewError(
        "file-routes-unsupported",
        "--route cannot be combined with a single file target. Serve a directory for multiple routes.",
        { routes: additions },
      );
    }
    const entryRoute = `/${localServer.entryPath
      .split("/")
      .map((segment) => encodeURIComponent(segment))
      .join("/")}`;
    return [
      {
        id: "route-01",
        requested: target.input,
        url: new URL(entryRoute, localServer.origin).href,
      },
    ];
  }
  const rawRoutes = ["/", ...additions.map(validateLocalRoute)];
  return [...new Set(rawRoutes)].map((route, index) => ({
    id: `route-${String(index + 1).padStart(2, "0")}`,
    requested: route,
    url: new URL(route, localServer.origin).href,
  }));
}

function publicInteractionContract(interaction, index) {
  return {
    index: index + 1,
    action: interaction.action,
    selector: interaction.selector,
    value:
      Object.hasOwn(interaction, "value")
        ? {
            persisted_as: "sha256-and-length-only",
            sha256: sha256Value(interaction.value),
            length: interaction.value.length,
          }
        : null,
  };
}

function resolveManifestScenarioRoute(target, rawRoute, localServer) {
  if (target.kind === "local-file") {
    if (rawRoute !== null) {
      throw new RenderReviewError(
        "file-routes-unsupported",
        "A capture manifest for a single-file target must use a null route.",
        {},
      );
    }
    const entryRoute = `/${localServer.entryPath
      .split("/")
      .map((segment) => encodeURIComponent(segment))
      .join("/")}`;
    return {
      requested: target.input,
      url: new URL(entryRoute, localServer.origin).href,
    };
  }
  if (target.kind === "local-directory") {
    const route = rawRoute === null ? "/" : validateLocalRoute(rawRoute);
    return {
      requested: route,
      url: new URL(route, localServer.origin).href,
    };
  }
  const base = new URL(target.url);
  let candidate;
  try {
    candidate = rawRoute === null ? base : new URL(rawRoute, base);
  } catch {
    throw new RenderReviewError(
      "invalid-route",
      "A capture-manifest route could not be resolved as a URL.",
      {},
    );
  }
  if (
    candidate.origin !== base.origin ||
    !["http:", "https:"].includes(candidate.protocol) ||
    candidate.username ||
    candidate.password
  ) {
    throw new RenderReviewError(
      "cross-origin-route",
      "Capture-manifest routes must remain on the target origin and cannot contain credentials.",
      { target_origin: base.origin },
    );
  }
  return {
    requested: rawRoute === null ? target.input : rawRoute,
    url: candidate.href,
  };
}

function assertManifestRouteDeclarationsMatch(
  target,
  declarations,
  localServer,
  manifestRoutes,
) {
  if (!declarations.length) return;

  const declaredByUrl = new Map();
  for (const rawRoute of declarations) {
    const resolved = resolveManifestScenarioRoute(target, rawRoute, localServer);
    if (!declaredByUrl.has(resolved.url)) {
      declaredByUrl.set(resolved.url, resolved.requested);
    }
  }
  const manifestByUrl = new Map(
    manifestRoutes.map((route) => [route.url, route.requested]),
  );
  const missingRoutes = [...manifestByUrl]
    .filter(([url]) => !declaredByUrl.has(url))
    .map(([, requested]) => requested);
  const unexpectedRoutes = [...declaredByUrl]
    .filter(([url]) => !manifestByUrl.has(url))
    .map(([, requested]) => requested);

  if (missingRoutes.length || unexpectedRoutes.length) {
    throw new RenderReviewError(
      "capture-manifest-route-conflict",
      "When --route is combined with --capture-manifest, the normalized route declarations must match the manifest scenario route set.",
      {
        declared_route_count: declaredByUrl.size,
        manifest_route_count: manifestByUrl.size,
        missing_routes: missingRoutes,
        unexpected_routes: unexpectedRoutes,
      },
    );
  }
}

async function prepareCapturePlan(target, options, localServer, manifest) {
  if (!manifest) {
    const routes = await prepareRoutes(target, options.routes, localServer);
    const scenarios = routes.map((route, index) => ({
      id: route.id,
      label: `Default route ${String(index + 1).padStart(2, "0")}`,
      route_label: `Route ${String(index + 1).padStart(2, "0")}`,
      state_label: "Initial state",
      route_id: route.id,
      profile_ids: PROFILES.map((profile) => profile.id),
      interactions: [],
    }));
    return {
      mode: "deterministic-default-v1",
      routes,
      profiles: PROFILES,
      scenarios,
      plans: scenarios.flatMap((scenario, scenarioIndex) =>
        PROFILES.map((profile, profileIndex) => ({
          scenario,
          scenarioIndex,
          profile,
          profileIndex,
          route: routes[scenarioIndex],
        })),
      ),
    };
  }

  const routeByUrl = new Map();
  const routes = [];
  const scenarios = manifest.scenarios.map((scenario) => {
    const resolved = resolveManifestScenarioRoute(
      target,
      scenario.route,
      localServer,
    );
    let route = routeByUrl.get(resolved.url);
    if (!route) {
      if (routes.length >= MAX_ROUTES) {
        throw new RenderReviewError(
          "too-many-routes",
          `A capture manifest may resolve to at most ${MAX_ROUTES} unique routes.`,
          { maximum: MAX_ROUTES },
        );
      }
      route = {
        id: `route-${String(routes.length + 1).padStart(2, "0")}`,
        requested: resolved.requested,
        url: resolved.url,
      };
      routes.push(route);
      routeByUrl.set(route.url, route);
    }
    return {
      ...scenario,
      route_id: route.id,
    };
  });
  assertManifestRouteDeclarationsMatch(
    target,
    options.routes,
    localServer,
    routes,
  );
  const profilesById = new Map(
    manifest.profiles.map((profile, index) => [profile.id, { profile, index }]),
  );
  return {
    mode: "capture-manifest-v1",
    routes,
    profiles: manifest.profiles,
    scenarios,
    plans: scenarios.flatMap((scenario, scenarioIndex) =>
      scenario.profile_ids.map((profileId) => {
        const selected = profilesById.get(profileId);
        return {
          scenario,
          scenarioIndex,
          profile: selected.profile,
          profileIndex: selected.index,
          route: routes.find((route) => route.id === scenario.route_id),
        };
      }),
    ),
  };
}

function publicScenarioContract(scenario) {
  return {
    id: scenario.id,
    label: scenario.label,
    route_id: scenario.route_id,
    route_label: scenario.route_label,
    state_label: scenario.state_label,
    profile_ids: scenario.profile_ids,
    interactions: scenario.interactions.map(publicInteractionContract),
  };
}

function jsonPayload(value) {
  return `${JSON.stringify(value, null, 2)}\n`;
}

function buildOwnershipMarker({
  outputIdentity,
  reportSha256,
  reportBytes,
  buildId,
  createdAt,
}) {
  return {
    schema_version: SCHEMA_VERSION,
    marker_type: MARKER_TYPE,
    tool: {
      name: TOOL_NAME,
      version: TOOL_VERSION,
    },
    output_identity: outputIdentity,
    report: {
      path: "render-review.json",
      sha256: reportSha256,
      bytes: reportBytes,
    },
    created_at: createdAt,
    build_id_sha256: sha256Value(buildId),
  };
}

function stabilizeReportArtifactBytes(report, fixedArtifactBytes, markerBytes) {
  let previous = -1;
  for (let attempt = 0; attempt < 8; attempt += 1) {
    const payload = jsonPayload(report);
    const reportBytes = Buffer.byteLength(payload);
    report.artifacts.report.bytes = reportBytes;
    report.artifacts.marker.bytes = markerBytes;
    report.artifacts.total_bytes =
      fixedArtifactBytes + reportBytes + markerBytes;
    if (reportBytes === previous) return payload;
    previous = reportBytes;
  }
  return jsonPayload(report);
}

async function run(options) {
  const started = new Date();
  const target = await classifyTarget(options.target);
  if (options.scrollSweep && target.kind === "remote-url") {
    throw new RenderReviewError(
      "remote-scroll-sweep-unsupported",
      "--scroll-sweep is limited to frozen local targets because scrolling can trigger remote analytics or state.",
      {},
    );
  }
  const preliminaryOutput = await validateOutput(
    options.output,
    options.replace,
    target,
  );
  const captureManifest = await loadCaptureManifest(
    options.captureManifest,
    target,
    preliminaryOutput.path,
  );
  const parent = path.dirname(preliminaryOutput.path);
  await assertNoSymlinkComponents(parent, true);
  await mkdir(parent, { recursive: true });
  await assertNoSymlinkComponents(parent);

  const lock = await acquireOutputLock(preliminaryOutput.path);
  let output = null;
  let transaction = null;
  let staging = null;
  let localServer = null;
  let browser = null;
  let primaryError = null;

  try {
    output = await validateOutput(options.output, options.replace, target);
    if (
      output.exists !== preliminaryOutput.exists ||
      (output.exists &&
        !sameDirectoryIdentity(output.identity, preliminaryOutput.identity))
    ) {
      throw new RenderReviewError(
        "output-identity-changed",
        "The output identity changed before the transaction lock was acquired.",
        { output: "[output path omitted]" },
      );
    }
    if (
      output.exists &&
      !sameTreeFingerprint(
        output.tree_fingerprint,
        preliminaryOutput.tree_fingerprint,
      )
    ) {
      throw new RenderReviewError(
        "output-content-changed",
        "The output contents changed before the transaction lock was acquired.",
        { output: "[output path omitted]" },
      );
    }

    const transactionRoot = await mkdtemp(
      path.join(
        parent,
        `.${path.basename(output.path)}.design-dna-transaction-`,
      ),
    );
    transaction = {
      root: transactionRoot,
      parent,
      outputBase: path.basename(output.path),
      preservePrior: false,
    };
    staging = path.join(transactionRoot, "new-output");
    await mkdir(staging, { recursive: false, mode: 0o700 });

    let sourceSnapshot = null;
    if (target.kind !== "remote-url") {
      sourceSnapshot = await createFrozenSnapshot(
        target,
        path.join(transactionRoot, "frozen-public-source"),
        options.limits,
      );
      localServer = await startStaticServer(
        path.join(transactionRoot, "frozen-public-source"),
        sourceSnapshot.entry_path,
      );
    }

    const capturePlan = await prepareCapturePlan(
      target,
      options,
      localServer,
      captureManifest,
    );
    const routes = capturePlan.routes;
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
          "--dns-prefetch-disable",
          "--disable-sync",
          "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
          "--no-first-run",
        ],
      });
    } catch (error) {
      throw new RenderReviewError(
        "browser-launch-failed",
        "Chromium could not be launched for rendered review.",
        {
          browser: browserExecutable.name,
          cause: sanitizeDiagnosticText(error?.message ?? error, [
            browserExecutable.path,
          ]),
        },
        3,
      );
    }

    const captures = [];
    const artifactBudget = {
      used: 0,
      maximum:
        options.limits.total_artifact_bytes -
        options.limits.report_bytes -
        64 * 1024,
    };
    const sensitivePaths = [
      target.localPath,
      target.sourceBoundary,
      output.path,
      transactionRoot,
      browserExecutable.path,
      captureManifest?.path,
    ].filter(Boolean);
    for (const plan of capturePlan.plans) {
      const allowedOrigin = new URL(plan.route.url).origin;
      captures.push(
        await captureOne({
          browser,
          route: plan.route,
          scenario: plan.scenario,
          profile: plan.profile,
          scenarioIndex: plan.scenarioIndex,
          profileIndex: plan.profileIndex,
          staging,
          options,
          networkPolicy: {
            mode:
              target.kind === "remote-url"
                ? "remote-credential-isolated"
                : "local-same-origin-only",
            allowed_origin: allowedOrigin,
          },
          sensitivePaths,
          artifactBudget,
        }),
      );
    }
    if (sourceSnapshot) {
      await verifyFrozenSnapshot(sourceSnapshot, options.limits, target);
    }
    await verifyCaptureManifest(captureManifest);
    const completed = new Date();
    const executionOk = captures.every((capture) => capture.capture_status === "complete");
    const advisoryCounts = captures.reduce(
      (totals, capture) => {
        totals.console_errors += capture.console.entries.filter((entry) =>
          ["error", "assert"].includes(entry.type),
        ).length;
        totals.page_errors += capture.page_errors.entries.length;
        totals.request_failures += capture.network.request_failures.length;
        totals.http_failures += capture.network.http_failures.length;
        totals.blocked_outbound += capture.network.blocked_outbound.length;
        totals.failed_captures += capture.capture_status === "failed" ? 1 : 0;
        totals.quota_failures +=
          capture.failure && /(?:limit|quota)/u.test(capture.failure.code) ? 1 : 0;
        totals.horizontal_overflow_documents += capture.document.layout.horizontal_overflow ? 1 : 0;
        totals.overflow_candidates += capture.document.layout.overflow_candidates.length;
        totals.failed_images += capture.document.images.filter((image) => image.failed).length;
        totals.missing_alt_attributes += capture.document.images.filter(
          (image) => !image.alt_present,
        ).length;
        totals.prominent_fragment_candidates +=
          capture.document.prominent_fragment_candidates.length;
        totals.focus_steps_without_indicator_candidate += capture.focus.steps.filter(
          (step) => !step.indicator_evidence.candidate_present,
        ).length;
        return totals;
      },
      {
        console_errors: 0,
        page_errors: 0,
        request_failures: 0,
        http_failures: 0,
        blocked_outbound: 0,
        failed_captures: 0,
        quota_failures: 0,
        horizontal_overflow_documents: 0,
        overflow_candidates: 0,
        failed_images: 0,
        missing_alt_attributes: 0,
        prominent_fragment_candidates: 0,
        focus_steps_without_indicator_candidate: 0,
      },
    );

    const outputIdentity = {
      id: randomBytes(32).toString("hex"),
      path_sha256: sha256Value(normalizePathForComparison(output.path)),
    };
    const report = {
      schema_version: SCHEMA_VERSION,
      tool: {
        name: TOOL_NAME,
        version: TOOL_VERSION,
        report_schema: "render-review.schema.json",
      },
      output_identity: outputIdentity,
      execution_ok: executionOk,
      review_required: true,
      automatic_visual_quality_pass: false,
      quality_status: executionOk
        ? "manual-review-required"
        : "execution-incomplete",
      execution: {
        started_at: started.toISOString(),
        completed_at: completed.toISOString(),
        duration_ms: completed.getTime() - started.getTime(),
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
      },
      privacy: {
        classification: "potentially-sensitive-rendered-review-evidence",
        operator_action: "explicit-cli-invocation",
        consent_notice:
          "The operator is responsible for authorization to capture the selected site and any people or confidential material it displays.",
        retention_notice:
          "Artifacts persist at the operator-selected output until the operator deliberately removes or replaces that owned output.",
        visual_content_not_redacted: true,
        diagnostic_sanitization: "best-effort-sensitive-value-and-path-redaction",
        url_sanitization: "userinfo-query-and-fragment-stripped-from-persisted-records",
        absolute_paths_persisted: false,
        limitations: [
          "Screenshots and videos can visibly contain personal, confidential, or credential-like page content; pixels are not automatically redacted.",
          "Diagnostic redaction is best effort and cannot guarantee removal of every application-specific secret format.",
          "Source hashes and output path hashes are pseudonymous identifiers and can still be sensitive when correlated with other records.",
          "HTTP, HTTPS, and WebSocket traffic is routed by policy and direct WebRTC UDP is restricted, but this is not a general-purpose browser sandbox or network noninterference proof.",
          "The path-bound ownership marker prevents accidental replacement and detects ordinary copying or tampering; it is not a cryptographic signature against an attacker who can rewrite both marker and report.",
        ],
      },
      build: {
        id: options.buildId,
        target_input: target.input,
        target_kind: target.kind,
      },
      source_snapshot: sourceSnapshot
        ? {
            policy: "frozen-deny-by-default-public-root",
            root_kind: sourceSnapshot.root_kind,
            entry_path: sourceSnapshot.entry_path,
            drift_check:
              "passed-source-and-frozen-snapshot-before-report-and-commit",
            manifest: sourceSnapshot.manifest,
          }
        : null,
      capture_contract: {
        deterministic_profile_version: 1,
        contract_mode: capturePlan.mode,
        capture_manifest: captureManifest
          ? {
              supplied: true,
              schema_version: captureManifest.schema_version,
              sha256: captureManifest.sha256,
              bytes: captureManifest.bytes,
            }
          : {
              supplied: false,
              schema_version: null,
              sha256: null,
              bytes: null,
            },
        wait_until: "domcontentloaded",
        timeout_ms: options.timeoutMs,
        settle_ms: options.settleMs,
        screenshot_animation_handling: "disabled-and-fast-forwarded",
        service_workers: "blocked",
        downloads: "blocked",
        locale: "en-US",
        timezone: "UTC",
        video_requested: options.video,
        video_duration_ms: options.video ? options.videoDurationMs : 0,
        local_network_policy: "same-origin-data-blob-only-outbound-blocked",
        remote_network_policy:
          "fresh-context-cross-origin-subresources-blocked-navigation-credentials-stripped",
        spa_fallback: "disabled-no-history-fallback",
        lazy_loading_policy:
          options.scrollSweep
            ? "opt-in-local-scroll-sweep-assets-waited-and-full-page-screenshot-attempted"
            : "passive-no-scroll-sweep-assets-waited-and-full-page-screenshot-attempted",
        interaction_policy:
          "single-match-allowlisted-actions-local-state-change-only-no-submit-no-popup-no-cross-origin",
        limits: options.limits,
        profiles: capturePlan.profiles,
        scenarios: capturePlan.scenarios.map(publicScenarioContract),
      },
      routes: routes.map((route) => ({
        ...route,
        requested:
          target.kind === "remote-url"
            ? sanitizeUrl(route.requested)
            : route.requested.startsWith("local-file:")
              ? route.requested
              : route.requested.split(/[?#]/u, 1)[0] || "/",
        url: sanitizeUrl(route.url),
      })),
      captures,
      artifacts: {
        contact_sheet: null,
        report: { path: "render-review.json", bytes: 0 },
        marker: { path: ".design-dna-render-review.json", bytes: 0 },
        capture_bytes: artifactBudget.used,
        total_bytes: 0,
      },
      manual_review: {
        status: "required",
        candidates_are_advisory: true,
        advisory_counts: advisoryCounts,
        limitations: [
          "Screenshots and computed styles do not establish visual quality, project specificity, truth, or authorship.",
          "DOM-derived names are approximations and are not an accessibility-tree or screen-reader result.",
          "Focus style differences are candidates; contrast, obstruction, and perception still require human review.",
          "Computed font-family values do not prove which glyph face rendered or that licensing and language coverage are complete.",
          "Typography sampling distributes bounded evidence by semantic role and document position; it does not rank font families or infer quality or authorship.",
          "Image crop heuristics cannot judge subject integrity, consent, provenance, or generated-media artifacts.",
          "Canvas, WebGL, shadow-DOM internals, cross-origin frame internals, and interaction states not reached by passive loading remain uninspected.",
          options.scrollSweep
            ? "The opt-in local scroll sweep visited the rendered document before capture to warm lazy and offscreen content; this is evidence collection, not proof that every scroll-linked state is correct."
            : "No active scroll sweep is performed; passive lazy content that does not load during asset waiting or full-page screenshot preparation can remain unobserved.",
          "The local server has no single-page-app history fallback; every requested route must resolve to a real frozen public file.",
          "Local captures block outbound cross-origin requests, so third-party-dependent states can differ from production and blocked requests require review.",
          "Remote captures also block cross-origin subresources by default; only credential-isolated top-level redirects are allowed for redirect evidence.",
          "Requested browser zoom modes are not simulated; their captures are unzoomed supporting baselines and true zoom review remains manual-required.",
          "Text-spacing evidence applies a deterministic author-style override; it is useful rendered evidence but does not replace manual reflow, zoom, reading, or assistive-technology review.",
          "Manifest interaction values are bound by the manifest hash but persisted only as SHA-256 and length; screenshots can still visibly contain entered values.",
          "A successful execution proves evidence collection completed within limits; it never proves design quality, accessibility conformance, privacy compliance, or human authorship.",
          "The ownership marker is a fail-closed accidental-deletion guard and integrity binding, not a signed authenticity or hostile-filesystem security boundary.",
        ],
      },
    };

    const contactSheetRelative = "contact-sheet.html";
    const contactSheetAbsolute = path.join(staging, contactSheetRelative);
    await writeFile(contactSheetAbsolute, buildContactSheet(report), {
      encoding: "utf8",
      flag: "wx",
      mode: 0o600,
    });
    const contactInfo = await stat(contactSheetAbsolute);
    if (
      contactInfo.size + MAX_OWNERSHIP_MARKER_BYTES >
      ARTIFACT_METADATA_RESERVE_BYTES
    ) {
      throw new RenderReviewError(
        "artifact-byte-limit-exceeded",
        "The contact sheet and maximum ownership marker exceed their reserved artifact budget.",
        {
          contact_sheet_bytes: contactInfo.size,
          maximum_marker_bytes: MAX_OWNERSHIP_MARKER_BYTES,
          reserved_bytes: ARTIFACT_METADATA_RESERVE_BYTES,
        },
      );
    }
    report.artifacts.contact_sheet = {
      path: contactSheetRelative,
      sha256: await sha256File(contactSheetAbsolute),
      media_type: "text/html",
      bytes: contactInfo.size,
    };
    await rm(path.join(staging, "videos", ".raw"), {
      recursive: true,
      force: true,
    }).catch(() => undefined);

    const markerCreatedAt = new Date().toISOString();
    let markerBytes = Buffer.byteLength(
      jsonPayload(
        buildOwnershipMarker({
          outputIdentity,
          reportSha256: "0".repeat(64),
          reportBytes: 1,
          buildId: options.buildId,
          createdAt: markerCreatedAt,
        }),
      ),
    );
    let reportPayload = "";
    for (let attempt = 0; attempt < 8; attempt += 1) {
      reportPayload = stabilizeReportArtifactBytes(
        report,
        artifactBudget.used + contactInfo.size,
        markerBytes,
      );
      const nextMarkerBytes = Buffer.byteLength(
        jsonPayload(
          buildOwnershipMarker({
            outputIdentity,
            reportSha256: "0".repeat(64),
            reportBytes: Buffer.byteLength(reportPayload),
            buildId: options.buildId,
            createdAt: markerCreatedAt,
          }),
        ),
      );
      if (nextMarkerBytes === markerBytes) break;
      markerBytes = nextMarkerBytes;
    }
    reportPayload = stabilizeReportArtifactBytes(
      report,
      artifactBudget.used + contactInfo.size,
      markerBytes,
    );
    const reportBytes = Buffer.byteLength(reportPayload);
    if (reportBytes > options.limits.report_bytes) {
      throw new RenderReviewError(
        "report-byte-limit-exceeded",
        "The rendered-review JSON exceeds the configured report limit.",
        { bytes: reportBytes, maximum_bytes: options.limits.report_bytes },
      );
    }
    if (report.artifacts.total_bytes > options.limits.total_artifact_bytes) {
      throw new RenderReviewError(
        "artifact-byte-limit-exceeded",
        "The complete evidence package exceeds the configured artifact limit.",
        {
          bytes: report.artifacts.total_bytes,
          maximum_bytes: options.limits.total_artifact_bytes,
        },
      );
    }
    const reportAbsolute = path.join(staging, report.artifacts.report.path);
    await writeFile(reportAbsolute, reportPayload, {
      encoding: "utf8",
      flag: "wx",
      mode: 0o600,
    });
    const reportSha256 = await sha256File(reportAbsolute);
    const marker = buildOwnershipMarker({
      outputIdentity,
      reportSha256,
      reportBytes,
      buildId: options.buildId,
      createdAt: markerCreatedAt,
    });
    const markerPayload = jsonPayload(marker);
    if (Buffer.byteLength(markerPayload) !== markerBytes) {
      throw new RenderReviewError(
        "marker-size-instability",
        "The ownership marker size changed after report finalization.",
        {},
        4,
      );
    }
    await writeFile(
      path.join(staging, report.artifacts.marker.path),
      markerPayload,
      { encoding: "utf8", flag: "wx", mode: 0o600 },
    );

    if (sourceSnapshot) {
      await verifyFrozenSnapshot(sourceSnapshot, options.limits, target);
    }
    await verifyCaptureManifest(captureManifest);
    await promoteOutput({
      staging,
      transaction,
      output: output.path,
      outputState: output,
      replace: options.replace,
      target,
    });
    staging = null;

    const summary = {
      schema_version: SCHEMA_VERSION,
      ok: executionOk,
      execution_ok: executionOk,
      review_required: true,
      automatic_visual_quality_pass: false,
      quality_status: report.quality_status,
      output_reference: "operator-selected-output",
      report_path: report.artifacts.report.path,
      contact_sheet_path: contactSheetRelative,
      route_count: routes.length,
      scenario_count: capturePlan.scenarios.length,
      capture_count: captures.length,
      advisory_counts: advisoryCounts,
    };
    process.stdout.write(`${JSON.stringify(summary)}\n`);
    return executionOk ? 0 : 1;
  } catch (error) {
    primaryError = error;
    throw error;
  } finally {
    if (browser) {
      await browser.close().catch(() => undefined);
    }
    if (localServer) {
      await localServer.close().catch(() => undefined);
    }
    try {
      await removeOwnedTransaction(transaction);
    } catch (cleanupError) {
      if (!primaryError) throw cleanupError;
    }
    const released = await lock.release().catch(() => false);
    if (!released && !primaryError) {
      throw new RenderReviewError(
        "output-lock-release-failed",
        "The transaction completed but its ownership lock could not be safely released.",
        { lock: path.basename(lock.path) },
        4,
      );
    }
  }
}

function emitFatal(error) {
  const normalized =
    error instanceof RenderReviewError
      ? error
      : new RenderReviewError(
          "render-review-failed",
          sanitizeDiagnosticText(error?.message ?? error),
          {},
          4,
        );
  const incomplete =
    /(?:limit|quota|source-drift|snapshot-drift|http-error|redirect|capture)/u.test(
      normalized.code,
    );
  const payload = {
    schema_version: SCHEMA_VERSION,
    ok: false,
    execution_ok: false,
    review_required: true,
    automatic_visual_quality_pass: false,
    quality_status: incomplete ? "execution-incomplete" : "execution-failed",
    error: {
      code: normalized.code,
      message: sanitizeDiagnosticText(normalized.message).slice(0, 4000),
      details: sanitizeDetails(normalized.details),
    },
  };
  process.stderr.write(`${JSON.stringify(payload)}\n`);
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
