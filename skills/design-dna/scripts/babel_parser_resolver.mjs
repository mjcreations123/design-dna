/** Resolve the pinned parser from an explicit, project, or packaged dependency root. */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

export const BABEL_PARSER_VERSION = "7.28.5";

function failure(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

export function resolveBabelParser(moduleUrl, options = {}) {
  const env = options.env || process.env;
  const explicit = env.DESIGN_DNA_BABEL_PARSER_MODULE_DIR;
  const scriptDirectory = path.dirname(fileURLToPath(moduleUrl));
  const roots = explicit ? [explicit] : [
    env.DESIGN_DNA_PLAYWRIGHT_MODULE_DIR,
    path.join(options.projectRoot || process.cwd(), "node_modules"),
    path.resolve(scriptDirectory, "../../../maintainer/node_modules"),
    path.resolve(scriptDirectory, "../node_modules"),
  ].filter(Boolean);
  const require = createRequire(moduleUrl);
  const attempts = [];
  for (const root of [...new Set(roots)]) {
    try {
      if (!path.isAbsolute(root) || path.basename(root) !== "node_modules") {
        throw new Error("dependency root must be an absolute node_modules directory");
      }
      const packageRoot = path.join(root, "@babel", "parser");
      const metadata = JSON.parse(fs.readFileSync(path.join(packageRoot, "package.json"), "utf8"));
      if (metadata.name !== "@babel/parser" || metadata.version !== BABEL_PARSER_VERSION) {
        throw new Error(`expected @babel/parser ${BABEL_PARSER_VERSION}, found ${metadata.version || "unknown"}`);
      }
      const entry = path.resolve(packageRoot, metadata.main || "lib/index.js");
      const relative = path.relative(packageRoot, entry);
      if (relative.startsWith(`..${path.sep}`) || relative === ".." || path.isAbsolute(relative)) {
        throw new Error("parser entry escapes its package");
      }
      const parser = require(entry);
      if (typeof parser.parse !== "function") throw new Error("parser entry exports no parse function");
      return parser;
    } catch (error) {
      attempts.push(`${root}: ${error.message}`);
      if (explicit) break;
    }
  }
  throw failure("babel-parser-unavailable",
    `Pinned @babel/parser ${BABEL_PARSER_VERSION} is unavailable. Run npm ci in the package maintainer directory and set DESIGN_DNA_BABEL_PARSER_MODULE_DIR (or DESIGN_DNA_PLAYWRIGHT_MODULE_DIR) to its absolute node_modules directory. ${attempts.join("; ")}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  if (args.length === 1 && args[0] === "--help") {
    process.stdout.write("babel_parser_resolver.mjs --check\n");
  } else {
    try {
      if (args.length !== 1 || args[0] !== "--check") throw failure("usage", "Use --check to verify the installed parser dependency.");
      const parser = resolveBabelParser(import.meta.url);
      const ast = parser.parse("const proof: unknown = <main/>;", { plugins: ["typescript", "jsx"] });
      if (ast.type !== "File") throw failure("babel-parser-invalid", "The parser failed its TSX capability check.");
      process.stdout.write(JSON.stringify({ ok: true, parser: "@babel/parser", version: BABEL_PARSER_VERSION, tsx: true }) + "\n");
    } catch (error) {
      process.stdout.write(JSON.stringify({ ok: false, error: { code: error.code || "babel-parser-invalid", message: error.message } }) + "\n");
      process.exitCode = 1;
    }
  }
}
