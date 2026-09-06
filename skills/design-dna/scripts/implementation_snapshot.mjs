/** Exact ordinary-file inventory shared with legacy_maintenance.py. */
import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";

const IGNORED_DIRECTORIES = new Set([".git", ".design-dna", "node_modules", ".venv", "__pycache__"]);
const codepointCompare = (left, right) => {
  const a = [...left], b = [...right];
  for (let index = 0; index < Math.min(a.length, b.length); index += 1) {
    const difference = a[index].codePointAt(0) - b[index].codePointAt(0);
    if (difference) return difference;
  }
  return a.length - b.length;
};
const canonical = (value) => Array.isArray(value) ? `[${value.map(canonical).join(",")}]`
  : value && typeof value === "object" ? `{${Object.keys(value).sort(codepointCompare).map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`
    : JSON.stringify(value);

function hashFile(file) {
  const before = fs.lstatSync(file);
  if (before.isSymbolicLink() || !before.isFile()) throw new Error(`Implementation snapshot refuses a non-ordinary file: ${file}`);
  if (before.nlink !== 1) throw new Error(`Implementation snapshot refuses a hardlink alias: ${file}`);
  const hash = createHash("sha256");
  const buffer = Buffer.allocUnsafe(1024 * 1024);
  const descriptor = fs.openSync(file, "r");
  let bytes = 0;
  try {
    for (;;) {
      const count = fs.readSync(descriptor, buffer, 0, buffer.length, null);
      if (!count) break;
      hash.update(buffer.subarray(0, count));
      bytes += count;
    }
  } finally { fs.closeSync(descriptor); }
  const after = fs.lstatSync(file);
  if (!after.isFile() || after.isSymbolicLink() || before.size !== bytes || before.size !== after.size
      || before.mtimeMs !== after.mtimeMs || before.ino !== after.ino) {
    throw new Error(`Implementation file changed during snapshot: ${file}`);
  }
  if (after.nlink !== 1) throw new Error(`Implementation snapshot found a changed hardlink alias: ${file}`);
  return { bytes, sha256: hash.digest("hex") };
}

export function snapshotImplementation(project) {
  const root = fs.realpathSync(path.resolve(project));
  const rootInfo = fs.lstatSync(root);
  if (!rootInfo.isDirectory() || rootInfo.isSymbolicLink()) throw new Error("Implementation snapshot needs one ordinary project directory.");
  const files = [];
  const visit = (directory) => {
    for (const name of fs.readdirSync(directory).sort(codepointCompare)) {
      const file = path.join(directory, name);
      // Match Python: only the exact root operational lock is excluded.
      if (directory === root && name === ".design-dna.lock") continue;
      const info = fs.lstatSync(file);
      // A dependency/evidence directory is outside this source inventory.
      // An ordinary file using one of those names remains a bound source file.
      if (IGNORED_DIRECTORIES.has(name) && (info.isDirectory()
          || info.isSymbolicLink() && fs.statSync(file).isDirectory())) continue;
      if (info.isSymbolicLink()) throw new Error(`Implementation snapshot refuses a symlink/junction: ${file}`);
      if (info.isDirectory()) visit(file);
      else files.push({ path: path.relative(root, file).split(path.sep).join("/"), ...hashFile(file) });
    }
  };
  visit(root);
  files.sort((a, b) => codepointCompare(a.path, b.path));
  return { algorithm: "sha256-files-v1", files, sha256: createHash("sha256").update(canonical(files)).digest("hex") };
}

export function implementationSnapshotsEqual(before, after) {
  return before?.algorithm === "sha256-files-v1" && after?.algorithm === "sha256-files-v1"
    && typeof before.sha256 === "string" && before.sha256 === after.sha256
    && canonical(before.files) === canonical(after.files);
}
