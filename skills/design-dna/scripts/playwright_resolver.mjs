/**
 * Resolve a pre-existing Playwright module without installing, downloading, or
 * searching global package locations. Runtime browser evidence has to work from
 * an installed skill tree, where Node's ordinary script-relative lookup cannot
 * see a project's own node_modules directory.
 */

import { createHash } from "node:crypto";
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const MODULE_NAMES = ["playwright", "playwright-core"];
const SHA256_HEX = /^[a-f0-9]{64}$/u;

export class PlaywrightResolutionError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = "PlaywrightResolutionError";
    this.code = code;
    this.details = details;
  }
}

function sha256(file) {
  return createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function isDirectory(candidate) {
  try {
    return fs.statSync(candidate).isDirectory();
  } catch {
    return false;
  }
}

function isFile(candidate) {
  try {
    return fs.statSync(candidate).isFile();
  } catch {
    return false;
  }
}

function realFile(candidate) {
  if (!isFile(candidate)) return null;
  try {
    return fs.realpathSync.native(candidate);
  } catch {
    return path.resolve(candidate);
  }
}

function scriptPath(moduleUrl) {
  try {
    return fileURLToPath(moduleUrl);
  } catch (error) {
    throw new PlaywrightResolutionError(
      "playwright-resolver-path-invalid",
      "The browser resolver cannot determine its installed skill path.",
      { cause: String(error?.message ?? error) },
    );
  }
}

function exactDirectoryResolution(moduleDirectory, source) {
  const directory = path.resolve(moduleDirectory);
  const requireFrom = createRequire(
    path.join(directory, "__design_dna_playwright_loader__.cjs"),
  );
  const attempts = [];
  for (const name of MODULE_NAMES) {
    try {
      const requested = path.join(directory, name);
      const entry = realFile(requireFrom.resolve(requested));
      const packageFile = realFile(
        requireFrom.resolve(path.join(directory, name, "package.json")),
      );
      if (!entry || !packageFile) {
        throw new Error("package entry or package.json is not an ordinary file");
      }
      const playwright = requireFrom(requested);
      if (!playwright?.chromium) {
        throw new Error("resolved module does not expose chromium");
      }
      const metadata = JSON.parse(fs.readFileSync(packageFile, "utf8"));
      const entrySha256 = sha256(entry);
      return {
        playwright,
        source,
        module_directory: directory,
        dependency: {
          name,
          version: typeof metadata.version === "string" ? metadata.version : "unknown",
          source,
          module_directory: directory,
          resolved_file: entry,
          resolved_file_sha256: entrySha256,
          // Keep the historical alias consumed by existing evidence validators.
          sha256: entrySha256,
          package_file: packageFile,
          package_sha256: sha256(packageFile),
        },
      };
    } catch (error) {
      attempts.push({ name, message: String(error?.message ?? error).slice(0, 240) });
    }
  }
  return { attempts };
}

function skillLocalResolution(moduleUrl) {
  const scripts = path.dirname(scriptPath(moduleUrl));
  const skillRoot = path.resolve(scripts, "..");
  const directories = [
    path.join(scripts, "node_modules"),
    path.join(skillRoot, "node_modules"),
  ];
  const attempts = [];
  for (const directory of [...new Set(directories.map((value) => path.resolve(value)))]) {
    if (!isDirectory(directory)) continue;
    const resolved = exactDirectoryResolution(directory, "skill-local-node-modules");
    if (resolved.playwright) return resolved;
    attempts.push({
      source: "skill-local-node-modules",
      module_directory: directory,
      attempts: resolved.attempts,
    });
  }
  return { attempts };
}

function sourcePackageModules(moduleUrl) {
  const scripts = path.dirname(scriptPath(moduleUrl));
  const skillRoot = path.resolve(scripts, "..");
  const packageRoot = path.resolve(skillRoot, "..", "..");
  if (
    path.resolve(packageRoot, "skills", "design-dna") !== skillRoot
    || !isFile(path.join(packageRoot, "maintainer", "package-lock.json"))
  ) {
    return null;
  }
  const modules = path.join(packageRoot, "maintainer", "node_modules");
  return isDirectory(modules) ? modules : null;
}

function existingDirectory(value, label, attempts) {
  if (!path.isAbsolute(value)) {
    throw new PlaywrightResolutionError(
      "playwright-module-directory-invalid",
      `${label} must be an absolute node_modules directory.`,
      { module_directory: value },
    );
  }
  const directory = path.resolve(value);
  if (!isDirectory(directory)) {
    throw new PlaywrightResolutionError(
      "playwright-module-directory-invalid",
      `${label} is not an existing node_modules directory.`,
      { module_directory: directory },
    );
  }
  const resolved = exactDirectoryResolution(directory, label);
  if (resolved.playwright) return resolved;
  attempts.push({ source: label, module_directory: directory, attempts: resolved.attempts });
  return null;
}

/**
 * Resolve a module using only deterministic local locations:
 *
 * 1. an explicit absolute environment directory (never silently bypassed);
 * 2. the calling project's exact node_modules directory;
 * 3. maintainer/node_modules beside a canonical source checkout;
 * 4. exact node_modules directories physically inside the installed skill.
 */
export function resolvePlaywright(options = {}) {
  const moduleUrl = options.moduleUrl ?? import.meta.url;
  const attempts = [];
  const hasExplicitOption = Object.prototype.hasOwnProperty.call(options, "moduleDirectory");
  const hasExplicitEnvironment = Object.prototype.hasOwnProperty.call(
    process.env,
    "DESIGN_DNA_PLAYWRIGHT_MODULE_DIR",
  );
  if (hasExplicitOption || hasExplicitEnvironment) {
    const explicit = hasExplicitOption
      ? options.moduleDirectory
      : process.env.DESIGN_DNA_PLAYWRIGHT_MODULE_DIR;
    if (explicit === undefined || explicit === null || !String(explicit).trim()) {
      throw new PlaywrightResolutionError(
        "playwright-module-directory-invalid",
        "DESIGN_DNA_PLAYWRIGHT_MODULE_DIR must be a non-empty absolute node_modules directory when it is set.",
        { module_directory: explicit ?? null },
      );
    }
    const resolved = existingDirectory(
      String(explicit),
      "environment-module-directory",
      attempts,
    );
    if (resolved) return resolved;
    throw new PlaywrightResolutionError(
      "playwright-unavailable",
      "The explicit DESIGN_DNA_PLAYWRIGHT_MODULE_DIR does not contain a usable Playwright module; it was not bypassed.",
      { attempts, explicit_module_directory: path.resolve(String(explicit)) },
    );
  }

  const projectRoot = path.resolve(options.projectRoot ?? process.cwd());
  const projectModules = path.join(projectRoot, "node_modules");
  if (isDirectory(projectModules)) {
    const resolved = exactDirectoryResolution(
      projectModules,
      "project-local-node-modules",
    );
    if (resolved.playwright) return resolved;
    attempts.push({ source: "project-local-node-modules", module_directory: projectModules, attempts: resolved.attempts });
  }

  const packageModules = sourcePackageModules(moduleUrl);
  if (packageModules) {
    const resolved = exactDirectoryResolution(
      packageModules,
      "source-package-maintainer-node-modules",
    );
    if (resolved.playwright) return resolved;
    attempts.push({ source: "source-package-maintainer-node-modules", module_directory: packageModules, attempts: resolved.attempts });
  }

  const skillLocal = skillLocalResolution(moduleUrl);
  if (skillLocal.playwright) return skillLocal;
  attempts.push({ source: "skill-local-node-modules", attempts: skillLocal.attempts });
  throw new PlaywrightResolutionError(
    "playwright-unavailable",
    "Playwright could not be resolved from the project, a canonical source checkout, or exact node_modules directories inside the installed skill. Install it in the project, or set DESIGN_DNA_PLAYWRIGHT_MODULE_DIR to an absolute existing node_modules directory.",
    { project_root: projectRoot, attempts },
  );
}

function systemBrowserCandidates() {
  const candidates = [];
  if (process.platform === "win32") {
    for (const base of [
      process.env.PROGRAMFILES,
      process.env["PROGRAMFILES(X86)"],
      process.env.LOCALAPPDATA,
      process.env.ProgramW6432,
    ]) {
      if (!base) continue;
      candidates.push(
        { name: "chrome", path: path.join(base, "Google", "Chrome", "Application", "chrome.exe") },
        { name: "edge", path: path.join(base, "Microsoft", "Edge", "Application", "msedge.exe") },
      );
    }
  } else if (process.platform === "darwin") {
    candidates.push(
      { name: "chrome", path: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" },
      { name: "edge", path: "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" },
      { name: "chromium", path: "/Applications/Chromium.app/Contents/MacOS/Chromium" },
    );
  } else {
    for (const name of ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"]) {
      for (const directory of String(process.env.PATH ?? "").split(path.delimiter)) {
        if (directory) candidates.push({ name, path: path.join(directory, name) });
      }
    }
  }
  return candidates;
}

/** Resolve but do not launch a Chromium-family browser. */
export function discoverBrowserExecutable(playwright, explicitPath = null) {
  if (explicitPath) {
    if (!path.isAbsolute(explicitPath) || !isFile(explicitPath)) {
      throw new PlaywrightResolutionError(
        "browser-executable-invalid",
        "--browser-executable must be an absolute existing ordinary file.",
        { browser_executable: explicitPath },
      );
    }
    return { path: realFile(explicitPath), source: "explicit", name: path.basename(explicitPath) };
  }
  try {
    const bundled = playwright?.chromium?.executablePath?.();
    if (bundled && isFile(bundled)) {
      return { path: realFile(bundled), source: "playwright", name: "chromium" };
    }
  } catch {
    // A valid playwright-core module may not carry a browser; try existing system browsers.
  }
  for (const candidate of systemBrowserCandidates()) {
    if (isFile(candidate.path)) {
      return { path: realFile(candidate.path), source: "system-discovery", name: candidate.name };
    }
  }
  throw new PlaywrightResolutionError(
    "browser-executable-unavailable",
    "A Playwright module resolved, but no compatible Chromium-family executable was found. Install Playwright Chromium or pass --browser-executable with an absolute existing browser path.",
  );
}

/** Bind the executable bytes selected for a browser-evidence run. */
export function browserExecutableIdentity(browser) {
  if (!browser || !isFile(browser.path)) {
    throw new PlaywrightResolutionError(
      "browser-executable-invalid",
      "A browser identity requires an existing ordinary executable file.",
    );
  }
  const file = realFile(browser.path);
  return {
    path: file,
    file,
    sha256: sha256(file),
    source: browser.source,
    name: browser.name,
  };
}

export function validSha256(value) {
  return typeof value === "string" && SHA256_HEX.test(value);
}
