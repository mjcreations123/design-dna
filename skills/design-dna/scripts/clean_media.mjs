#!/usr/bin/env node
/**
 * clean_media.mjs
 *
 * Owner directive (Motty, 2026-11-02): once he approves a design, its
 * screenshots and screen recordings are not kept. They were made to be looked
 * at; the text records are what keep the design traceable.
 *
 * For one project whose design is approved, this removes from
 * <project>/.design-dna:
 *   - images and video: .png .jpg .jpeg .webp .gif .avif .bmp .webm .mp4 .mov
 *     .m4v .mkv .gray (frames, first screens, contact sheets, review sheets,
 *     candidates sheets, recordings, raw capture frames);
 *   - captured browser profiles: every folder holding a "Local State" file or
 *     "Default/Preferences", removed whole (Chrome caches such as
 *     optimization_guide_model_store/.../model.tflite live there).
 * Everything else stays: sheet.md, study.json, plan.json, check.json,
 * latest.json, review.md, notes, logs, scripts, fonts. What was removed, with
 * each file's size and SHA-256, is written to <project>/.design-dna/retention.json,
 * so every hash a plan, study or check record cites still resolves to a record
 * of the file it named.
 *
 *   node clean_media.mjs --project DIR              report only (the default; nothing is removed)
 *   node clean_media.mjs --project DIR --dry-run    the same, said explicitly
 *   node clean_media.mjs --project DIR --apply      remove what the report lists
 *        [--approved] [--keep RELATIVE_PATH]...
 *
 * It refuses and removes nothing (exit 2) when:
 *   - the design is not approved: plan.json records no approval {by, date}
 *     and --approved was not given;
 *   - plan.json is unreadable or still says TODO (the plan is unfinished);
 *   - work continued after the recorded approval date (a study, check or
 *     capture written after that day) and --approved was not given;
 *   - anything under .design-dna changed in the last 10 minutes: a study, a
 *     check or a browser may still be writing there;
 *   - the legacy project lock (<project>/.design-dna.lock) is active or unreadable;
 *   - the folder is the owner record (~/.design-dna), a link, or missing.
 *
 * --approved is the operator's statement that the owner approved this design
 * as it now stands. Use it only when he did: for a project whose approval is
 * not recorded in plan.json (a pre-13 layout), or to confirm that his approval
 * covers work done after the recorded date. Never on a guess, never for a
 * design still being worked on.
 * --keep protects a file or folder (relative to .design-dna) that the report
 * lists, such as client-supplied images or an image the site itself loads.
 *
 * Exit: 0 done (or report clean), 1 some files could not be removed, 2 refused.
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { createHash } from "node:crypto";

const TOOL = "clean_media.mjs";
const MEDIA = new Set([".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".bmp", ".webm", ".mp4", ".mov", ".m4v", ".mkv", ".gray"]);
const QUIET_MINUTES = 10;
const LEDGER = "retention.json";
const LOCK = ".design-dna.lock";
const CHUNK = 4 * 1024 * 1024;

function usage() {
  return "clean_media.mjs --project DIR [--dry-run | --apply] [--approved] [--keep RELATIVE_PATH]...\n";
}
function out(payload, code) {
  process.stdout.write(JSON.stringify(payload, null, 2) + "\n");
  process.exit(code);
}
function parseArgs(argv) {
  const args = { project: null, apply: false, dryRun: false, approved: false, keep: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--project") args.project = argv[++i];
    else if (a === "--apply") args.apply = true;
    else if (a === "--dry-run") args.dryRun = true;
    else if (a === "--approved") args.approved = true;
    else if (a === "--keep") args.keep.push(argv[++i]);
    else if (a === "--help" || a === "-h") { process.stdout.write(usage()); process.exit(0); }
    else out({ ok: false, tool: TOOL, error: `unknown argument ${a}` }, 2);
  }
  if (!args.project) out({ ok: false, tool: TOOL, error: "--project is required" }, 2);
  if (args.apply && args.dryRun) out({ ok: false, tool: TOOL, error: "--apply and --dry-run cannot be combined" }, 2);
  if (args.keep.some((k) => typeof k !== "string" || !k.trim())) out({ ok: false, tool: TOOL, error: "--keep needs a path relative to .design-dna" }, 2);
  args.keep = args.keep.map((k) => k.replace(/\\/g, "/").replace(/^\.\/+/, "").replace(/\/+$/, ""));
  if (args.keep.some((k) => path.posix.isAbsolute(k) || /^[A-Za-z]:/.test(k) || k.split("/").includes(".."))) out({ ok: false, tool: TOOL, error: "--keep paths are relative to .design-dna and stay inside it" }, 2);
  return args;
}

const posix = (rel) => rel.split(path.sep).join("/");
const sameFsPath = (a, b) => (process.platform === "win32" ? a.toLowerCase() === b.toLowerCase() : a === b);
const kept = (rel, keep) => keep.some((k) => rel === k || rel.startsWith(`${k}/`));
const folderOf = (rel) => { const parts = rel.split("/").slice(0, -1); return parts.length ? parts.slice(0, 2).join("/") : "(top level)"; };

function isProfile(dir) {
  try {
    if (fs.lstatSync(path.join(dir, "Local State")).isFile()) return true;
  } catch {}
  try {
    return fs.lstatSync(path.join(dir, "Default", "Preferences")).isFile();
  } catch { return false; }
}

// Walk .design-dna without following links. Media files and profile folders are
// collected; links are reported and never touched; the newest write is tracked
// for the quiet-window and post-approval checks.
function inventory(root, keep) {
  const inv = { media: [], profiles: [], keptMedia: [], links: [], textFiles: 0, newest: [], unreadable: [] };
  const consider = (rel, mtimeMs) => { if (rel !== LEDGER) inv.newest.push({ rel, mtimeMs }); };
  const sizeOf = (dir) => {
    let files = 0, bytes = 0, newest = 0;
    const stack = [dir];
    while (stack.length) {
      const d = stack.pop();
      let entries = [];
      try { entries = fs.readdirSync(d, { withFileTypes: true }); } catch (e) { inv.unreadable.push(posix(path.relative(root, d))); continue; }
      for (const e of entries) {
        const p = path.join(d, e.name);
        let st; try { st = fs.lstatSync(p); } catch { continue; }
        if (st.isDirectory()) stack.push(p);
        else { files += 1; bytes += st.size; newest = Math.max(newest, st.mtimeMs); }
      }
    }
    return { files, bytes, newest };
  };
  const stack = [root];
  while (stack.length) {
    const dir = stack.pop();
    let entries = [];
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { inv.unreadable.push(posix(path.relative(root, dir)) || "."); continue; }
    for (const entry of entries) {
      const abs = path.join(dir, entry.name);
      const rel = posix(path.relative(root, abs));
      let st; try { st = fs.lstatSync(abs); } catch { inv.unreadable.push(rel); continue; }
      if (st.isSymbolicLink()) { inv.links.push(rel); continue; }
      if (st.isDirectory()) {
        if (isProfile(abs)) {
          const size = sizeOf(abs);
          if (size.files) consider(rel, size.newest);
          if (kept(rel, keep)) inv.keptMedia.push(rel);
          else inv.profiles.push({ rel, abs, files: size.files, bytes: size.bytes });
          continue;
        }
        // A folder's own time changes when anything inside it is removed, so
        // only files count as work.
        stack.push(abs);
        continue;
      }
      if (!st.isFile()) continue;
      consider(rel, st.mtimeMs);
      if (MEDIA.has(path.extname(entry.name).toLowerCase())) {
        if (kept(rel, keep)) inv.keptMedia.push(rel);
        else inv.media.push({ rel, abs, bytes: st.size });
      } else inv.textFiles += 1;
    }
  }
  inv.media.sort((a, b) => a.rel.localeCompare(b.rel));
  inv.profiles.sort((a, b) => a.rel.localeCompare(b.rel));
  return inv;
}

function readPlan(root) {
  const file = path.join(root, "plan.json");
  if (!fs.existsSync(file)) return { present: false };
  try {
    const text = fs.readFileSync(file, "utf8");
    return { present: true, text, plan: JSON.parse(text) };
  } catch (error) {
    return { present: true, error: String(error?.message || error) };
  }
}

// The legacy state tooling keeps .design-dna.lock: byte 0 is the locked byte,
// the record from byte 1 says "active" while an operation holds it.
function legacyLock(project) {
  const file = path.join(project, LOCK);
  if (!fs.existsSync(file)) return null;
  try {
    const raw = fs.readFileSync(file).subarray(1).toString("utf8").trim();
    if (!raw) return null;
    const record = JSON.parse(raw);
    if (record?.status === "released") return null;
    return record?.status === "active" ? "active" : "unreadable";
  } catch { return "unreadable"; }
}

function endOfDay(date) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(date || "").trim());
  if (!m) return null;
  const end = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]) + 1, 0, 0, 0, 0);
  return Number.isNaN(end.getTime()) ? null : end.getTime();
}

function sha256(file) {
  const hash = createHash("sha256");
  const fd = fs.openSync(file, "r");
  try {
    const buf = Buffer.allocUnsafe(CHUNK);
    for (;;) {
      const n = fs.readSync(fd, buf, 0, CHUNK, null);
      if (!n) break;
      hash.update(buf.subarray(0, n));
    }
  } finally { fs.closeSync(fd); }
  return hash.digest("hex");
}

function writeLedger(file, ledger) {
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(ledger, null, 2) + "\n");
  fs.renameSync(tmp, file);
}

function removeEmptyParents(root, dirs) {
  const sorted = [...dirs].sort((a, b) => b.length - a.length);
  for (let dir of sorted) {
    while (dir.length > root.length && !sameFsPath(dir, root)) {
      try {
        if (fs.readdirSync(dir).length) break;
        fs.rmdirSync(dir);
      } catch { break; }
      dir = path.dirname(dir);
    }
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const project = path.resolve(args.project);
  const root = path.join(project, ".design-dna");
  const refusals = [];
  const refuse = (code, message) => refusals.push({ code, message });

  let rootStat = null;
  try { rootStat = fs.lstatSync(root); } catch {}
  if (!rootStat) out({ ok: false, tool: TOOL, project, refused: [{ code: "no-design-dna", message: `${root} does not exist` }] }, 2);
  if (rootStat.isSymbolicLink() || !rootStat.isDirectory()) out({ ok: false, tool: TOOL, project, refused: [{ code: "not-a-folder", message: ".design-dna is a link or not a folder; nothing is removed through a link" }] }, 2);
  const ownerRecord = path.join(os.homedir(), ".design-dna");
  if (sameFsPath(path.resolve(root), path.resolve(ownerRecord)) || sameFsPath(project, path.resolve(os.homedir()))) {
    out({ ok: false, tool: TOOL, project, refused: [{ code: "owner-record", message: "~/.design-dna is the owner record, evidence and reviews, not a project; it is never cleaned by this tool" }] }, 2);
  }

  // Approval: the field check_build.mjs reports on its APPROVAL line.
  const planRead = readPlan(root);
  let approval = null;
  if (planRead.present && planRead.error) refuse("plan-unreadable", `plan.json cannot be read (${planRead.error}); fix it before removing anything`);
  if (planRead.plan) {
    const a = planRead.plan.approval;
    if (a?.by && a?.date) approval = { by: String(a.by), date: String(a.date), note: a.note ? String(a.note) : undefined, source: "plan.json" };
    const todos = (planRead.text.match(/\bTODO\b/g) || []).length;
    if (todos) refuse("plan-unfinished", `plan.json still says TODO in ${todos} place${todos === 1 ? "" : "s"}; the design is still in progress`);
  }
  if (!approval && args.approved) approval = { by: "operator statement (--approved)", date: new Date().toISOString().slice(0, 10), source: "--approved" };
  if (!approval) refuse("not-approved", planRead.present
    ? "plan.json records no approval {by, date}. When the owner approves, record his name and the date there; never write it for him. Pass --approved only if he approved and it cannot be recorded."
    : "this project has no plan.json approval record; pass --approved only if the owner approved this design");

  const lock = legacyLock(project);
  if (lock) refuse("project-lock", `${LOCK} is ${lock}; a state operation may still be running`);

  const inv = inventory(root, args.keep);
  const now = Date.now();
  const recent = inv.newest.filter((x) => now - x.mtimeMs < QUIET_MINUTES * 60_000).map((x) => x.rel);
  if (recent.length) refuse("recent-activity", `${recent.length} item${recent.length === 1 ? "" : "s"} under .design-dna changed in the last ${QUIET_MINUTES} minutes (e.g. ${recent.slice(0, 3).join(", ")}); a study, check or browser may still be writing. Wait, then run again.`);
  if (approval?.source === "plan.json" && !args.approved) {
    const end = endOfDay(approval.date);
    if (end === null) refuse("approval-date-unreadable", `approval.date "${approval.date}" is not YYYY-MM-DD, so later work cannot be ruled out; pass --approved only if the owner approved the design as it now stands`);
    else {
      const later = inv.newest.filter((x) => x.rel !== "plan.json" && x.mtimeMs >= end).map((x) => x.rel);
      if (later.length) refuse("work-after-approval", `${later.length} item${later.length === 1 ? "" : "s"} were written after the approval date ${approval.date} (e.g. ${later.slice(0, 3).join(", ")}); the design may be in revision. Record the new approval in plan.json, or pass --approved only if the owner approved the design as it now stands.`);
    }
  }
  if (inv.unreadable.length) refuse("unreadable", `${inv.unreadable.length} item${inv.unreadable.length === 1 ? "" : "s"} could not be read (e.g. ${inv.unreadable.slice(0, 3).join(", ")})`);

  const byFolder = {};
  for (const m of inv.media) {
    const f = folderOf(m.rel);
    byFolder[f] ||= { files: 0, bytes: 0 };
    byFolder[f].files += 1; byFolder[f].bytes += m.bytes;
  }
  const totals = {
    media_files: inv.media.length,
    media_bytes: inv.media.reduce((s, m) => s + m.bytes, 0),
    profiles: inv.profiles.length,
    profile_files: inv.profiles.reduce((s, p) => s + p.files, 0),
    profile_bytes: inv.profiles.reduce((s, p) => s + p.bytes, 0),
    text_files_kept: inv.textFiles,
  };
  const summary = {
    tool: TOOL,
    project,
    approval,
    keep: args.keep,
    totals,
    by_folder: byFolder,
    profiles: inv.profiles.map((p) => ({ dir: p.rel, files: p.files, bytes: p.bytes })),
    kept_by_request: inv.keptMedia,
    links_not_followed: inv.links,
  };

  if (refusals.length) out({ ok: false, mode: args.apply ? "refused" : "report", ...summary, refused: refusals, removed: "nothing" }, 2);
  if (!args.apply) out({ ok: true, mode: "report", ...summary, next: totals.media_files || totals.profiles ? "run again with --apply to remove these" : "nothing to remove" }, 0);
  if (!totals.media_files && !totals.profiles) out({ ok: true, mode: "applied", ...summary, removed: "nothing to remove" }, 0);

  // Record first (planned), remove, then record what actually happened.
  const ledgerFile = path.join(root, LEDGER);
  let ledger = { tool: TOOL, policy: "Owner directive, Motty, 2026-11-02: screenshots and recordings are removed once the design is approved; the text records stay.", runs: [] };
  if (fs.existsSync(ledgerFile)) {
    try {
      const prior = JSON.parse(fs.readFileSync(ledgerFile, "utf8"));
      if (!Array.isArray(prior.runs)) throw new Error("runs is not an array");
      ledger = prior;
    } catch (error) {
      out({ ok: false, mode: "refused", ...summary, refused: [{ code: "ledger-unreadable", message: `${LEDGER} exists but cannot be read (${error.message}); nothing is removed` }], removed: "nothing" }, 2);
    }
  }
  const run = {
    started_at: new Date().toISOString(),
    status: "in-progress",
    approval,
    keep: args.keep,
    files: inv.media.map((m) => ({ file: m.rel, bytes: m.bytes, sha256: sha256(m.abs) })),
    profiles: inv.profiles.map((p) => ({ dir: p.rel, files: p.files, bytes: p.bytes })),
    totals,
    not_removed: [],
  };
  ledger.runs.push(run);
  writeLedger(ledgerFile, ledger);

  const touched = new Set();
  for (const m of inv.media) {
    try { fs.unlinkSync(m.abs); touched.add(path.dirname(m.abs)); }
    catch (error) { run.not_removed.push({ path: m.rel, error: error.code || String(error.message || error) }); }
  }
  for (const p of inv.profiles) {
    try { fs.rmSync(p.abs, { recursive: true, force: false, maxRetries: 2 }); touched.add(path.dirname(p.abs)); }
    catch (error) { run.not_removed.push({ path: p.rel, error: error.code || String(error.message || error) }); }
  }
  removeEmptyParents(root, touched);
  run.finished_at = new Date().toISOString();
  run.status = run.not_removed.length ? "partial" : "complete";
  writeLedger(ledgerFile, ledger);
  out({ ok: !run.not_removed.length, mode: "applied", ...summary, ledger: path.join(".design-dna", LEDGER), not_removed: run.not_removed }, run.not_removed.length ? 1 : 0);
}

main();
