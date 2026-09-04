#!/usr/bin/env node
/**
 * Read-only browser prerequisite check for an installed Design DNA skill.
 * It never runs npm, writes configuration, downloads a browser, or scans
 * global package locations. Run it from the target project's root.
 */

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import {
  browserExecutableIdentity,
  discoverBrowserExecutable,
  PlaywrightResolutionError,
  resolvePlaywright,
} from "./playwright_resolver.mjs";

function emit(value, code = 0) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
  process.exitCode = code;
}

function parseArgs(argv) {
  const options = {
    projectRoot: process.cwd(),
    browserExecutable: process.env.DESIGN_DNA_BROWSER_EXECUTABLE || null,
    launch: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--project-root") options.projectRoot = argv[++index];
    else if (value === "--browser-executable") options.browserExecutable = argv[++index];
    else if (value === "--launch") options.launch = true;
    else if (value === "--help" || value === "-h") {
      process.stdout.write(
        "browser_preflight.mjs [--project-root ABSOLUTE_DIRECTORY] [--browser-executable ABSOLUTE_FILE] [--launch]\n"
        + "Checks only existing local Playwright and Chromium resources. It never installs, downloads, or changes configuration.\n",
      );
      process.exit(0);
    } else {
      throw new PlaywrightResolutionError("browser-preflight-argument-invalid", `Unknown argument: ${value}`);
    }
  }
  if (!options.projectRoot || !path.isAbsolute(options.projectRoot)) {
    throw new PlaywrightResolutionError(
      "browser-project-root-invalid",
      "--project-root must be an absolute existing project directory.",
      { project_root: options.projectRoot ?? null },
    );
  }
  const projectRoot = path.resolve(options.projectRoot);
  if (!fs.existsSync(projectRoot) || !fs.statSync(projectRoot).isDirectory()) {
    throw new PlaywrightResolutionError(
      "browser-project-root-invalid",
      "--project-root must be an absolute existing project directory.",
      { project_root: projectRoot },
    );
  }
  return { ...options, projectRoot };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const loaded = resolvePlaywright({
    moduleUrl: import.meta.url,
    projectRoot: options.projectRoot,
  });
  const browser = browserExecutableIdentity(discoverBrowserExecutable(
    loaded.playwright,
    options.browserExecutable,
  ));
  let browserVersion = null;
  if (options.launch) {
    const instance = await loaded.playwright.chromium.launch({
      headless: true,
      executablePath: browser.path,
    });
    try {
      browserVersion = instance.version();
      const page = await instance.newPage();
      await page.goto("about:blank");
      await page.close();
    } finally {
      await instance.close();
    }
  }
  emit({
    ok: true,
    record_type: "design-dna-browser-preflight",
    schema_version: 1,
    project_root: options.projectRoot,
    launch_checked: options.launch,
    playwright: loaded.dependency,
    browser: {
      path: browser.path,
      source: browser.source,
      name: browser.name,
      sha256: browser.sha256,
      launch_version: browserVersion,
    },
    limitations: [
      "This checks one local Node process and does not prove Codex or Claude Code activated the skill.",
      "This check does not install Playwright, download Chromium, or replace rendered project QA.",
    ],
  });
}

main().catch((error) => {
  const known = error instanceof PlaywrightResolutionError;
  emit({
    ok: false,
    record_type: "design-dna-browser-preflight",
    schema_version: 1,
    error: {
      code: known ? error.code : "browser-preflight-failed",
      message: String(error?.message ?? error).slice(0, 800),
      details: known ? error.details : {},
    },
  }, 3);
});
