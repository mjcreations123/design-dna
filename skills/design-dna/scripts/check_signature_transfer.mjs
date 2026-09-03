#!/usr/bin/env node
/**
 * check_signature_transfer.mjs
 *
 * The failure this exists for, in the owner's words: "you still took the crack
 * in the sidewalk instead of the waterfall."
 *
 * Six references were researched, watched with the harness, and measured out of
 * their live CSS. Every gate passed. And two of the six reached the build as a
 * background colour and a set of control dimensions, because a producer will
 * take the part it is most comfortable rebuilding and a source line does not
 * care which part that was.
 *
 * One half of that failure is objective and this script owns it. The harness
 * already sorts a reference's mechanisms by weight, so it knows which one is
 * the biggest thing that site does. If the producer's `Signature` cell names a
 * behaviour that is nowhere near the top of that list, the producer has written
 * down a small true thing instead of the large one: shopfunner.com's buttons do
 * change colour under the pointer, and that is not what anyone would name about
 * shopfunner.com.
 *
 * The other half is a judgment and no script can take it: what would actually
 * be lost if this reference were cut out of the set. That belongs in the
 * dossier's `Signature transfer` table, where it has to name a component the
 * build would lose, and `init_project_state.py` holds it.
 *
 * Usage:
 *   node check_signature_transfer.mjs \
 *     --dossier .design-dna/reference-dossier.md \
 *     --observation .design-dna/references/strong-1-observation.json \
 *     --observation .design-dna/references/strong-2-observation.json \
 *     --out .design-dna/evidence/signature-transfer.json
 */

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const SCHEMA_VERSION = 1;
const TOOL_NAME = "check_signature_transfer.mjs";
// The top of a weight-sorted list, not the whole list. A site records small
// true behaviours all the way down; the signature is the loud one.
const TOP_MECHANISMS = 2;

function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }, null, 2) + "\n");
  process.exit(2);
}

/* A verb can mean more than one mechanism, so a signature passes when ANY
   mechanism its verbs name is among the reference's loudest. */
const VERB_TYPES = [
  [/\b(hold|holds|held|pin|pins|pinned|stick|sticks|stuck|stay|stays|stayed|lock|locks)\b/i, ["pinned"]],
  [/\b(swap|swaps|swapped|change|changes|changed|become|becomes|cycle|cycles|replace|replaces|crossfade|crossfades|dissolve|dissolves|turn|turns)\b/i, ["swap"]],
  [/\b(reveal|reveals|rise|rises|arrive|arrives|enter|enters|appear|appears|slide|slides|settle|settles|fade|fades|assemble|assembles|write|writes|grow|grows|expand|expands|unfold|unfolds|build|builds|land|lands)\b/i, ["reveal"]],
  [/\b(parallax|parallaxes|drift|drifts|float|floats|lag|lags|trail|trails)\b/i, ["parallax", "pointer-follow"]],
  [/\b(follow|follows|track|tracks|tilt|tilts|lean|leans|answer|answers|respond|responds|react|reacts)\b/i, ["pointer-follow", "hover-transition"]],
  [/\b(hover|hovers|fill|fills|light|lights|glow|glows)\b/i, ["hover-transition"]],
  [/\b(transition|transitions|wipe|wipes|mask|masks|cut|cuts)\b/i, ["hover-transition", "page-transition"]],
  [/\b(play|plays|loop|loops|run|runs|tick|ticks|breathe|breathes)\b/i, ["at-rest"]],
  [/\b(travel|travels|push|pushes|climb|climbs)\b/i, ["pinned", "parallax"]],
];

/* "responds in colour rather than by moving" claims a hover, not a reveal.
   Everything after a negation describes what the site does NOT do, and reading
   it as a claim is how a signature about buttons passed as a signature about
   panels crossfading. */
const NEGATION = /\b(rather than|instead of|not by|without)\b/i;

function claimedPortion(signature) {
  const cut = signature.search(NEGATION);
  return cut === -1 ? signature : signature.slice(0, cut);
}

function parseArgs(argv) {
  const out = { dossier: null, observations: [], out: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--dossier") out.dossier = argv[++i];
    else if (a === "--observation") out.observations.push(argv[++i]);
    else if (a === "--out") out.out = argv[++i];
    else if (a === "--help" || a === "-h") {
      process.stdout.write(
        "check_signature_transfer.mjs --dossier FILE --observation FILE [--observation FILE ...] --out FILE\n"
      );
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${a}`);
  }
  if (!out.dossier) fail("invalid-dossier", "--dossier must name the project's reference-dossier.md.");
  if (!out.observations.length) fail("invalid-observation", "--observation must name at least one observation session.");
  if (!out.out) fail("invalid-out", "--out must name the record to write.");
  return out;
}

/* The dossier's tables, read the way the state gate reads them: the first
   table under a heading, split on unescaped pipes. */
function sectionOf(body, heading) {
  const lines = body.split(/\r?\n/);
  const start = lines.findIndex((l) => l.trim().toLowerCase() === `## ${heading}`.toLowerCase());
  if (start === -1) return "";
  let end = lines.length;
  for (let i = start + 1; i < lines.length; i += 1) {
    if (/^##\s/.test(lines[i])) { end = i; break; }
  }
  return lines.slice(start + 1, end).join("\n");
}

function firstTable(section) {
  const rows = [];
  let headers = null;
  for (const raw of section.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line.startsWith("|")) { if (headers) break; else continue; }
    const cells = line.replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
    if (cells.every((c) => /^:?-{2,}:?$/.test(c))) continue;
    if (!headers) headers = cells;
    else rows.push(cells);
  }
  return { headers: headers || [], rows };
}

function sha256(file) {
  return createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

const args = parseArgs(process.argv.slice(2));

let dossierBody;
try {
  dossierBody = fs.readFileSync(args.dossier, "utf8");
} catch (e) {
  fail("dossier-unreadable", `Could not read ${args.dossier}: ${e.message}`);
}

const strong = firstTable(sectionOf(dossierBody, "Strong references"));
if (!strong.rows.length) {
  fail("no-strong-rows", "The dossier has no Strong references table to read.");
}
const rankColumn = strong.headers.findIndex((h) => /^rank$/i.test(h));
const signatureColumn = strong.headers.findIndex((h) => /^signature/i.test(h));
if (rankColumn === -1 || signatureColumn === -1) {
  fail("strong-headers", "The Strong references table needs a Rank column and a Signature column.");
}

/* Six rows are listed so that no one site is the template; four or more of
   them are selected. Only a SELECTED reference owes the build a part, so only
   a selected rank can fail for being cited by no component row. */
const synthesis = sectionOf(dossierBody, "Selected synthesis");
const selectedLine = synthesis.match(/^-\s+Selected positive ranks[^:]*:\s*([\d,\s]+)$/m);
const selectedRanks = new Set(
  selectedLine
    ? selectedLine[1].split(",").map((s) => Number(s.trim())).filter((n) => Number.isFinite(n) && n > 0)
    : []
);
const isSelected = (rank) => (selectedRanks.size ? selectedRanks.has(rank) : true);

const components = firstTable(sectionOf(dossierBody, "Component sources"));
const componentSourceColumn = components.headers.findIndex((h) => /source rank/i.test(h));
const citations = new Map(); // rank -> [component names]
if (componentSourceColumn !== -1) {
  for (const row of components.rows) {
    const cell = row[componentSourceColumn] || "";
    if (/^owner-approved/i.test(cell.trim())) continue;
    for (const m of cell.matchAll(/\d+/g)) {
      const rank = Number(m[0]);
      if (!citations.has(rank)) citations.set(rank, []);
      citations.get(rank).push((row[0] || "").trim());
    }
  }
}

const byRank = new Map();
for (const file of args.observations) {
  let payload;
  try {
    payload = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (e) {
    fail("observation-unreadable", `Could not read ${file}: ${e.message}`);
  }
  const id = String(payload.id || path.basename(file));
  const match = id.match(/(\d+)/);
  if (!match) continue;
  const rank = Number(match[1]);
  const mechanisms = Array.isArray(payload.mechanisms) ? payload.mechanisms : [];
  // observe_reference.mjs emits these already sorted, loudest first
  const ranked = mechanisms.map((m) => m.type).filter(Boolean);
  const existing = byRank.get(rank);
  const record = {
    rank,
    id,
    url: payload.url || null,
    observation: path.relative(process.cwd(), file).split(path.sep).join("/"),
    sha256: sha256(file),
    loudest: ranked.slice(0, TOP_MECHANISMS),
    all_types: [...new Set(ranked)],
    detail: mechanisms.slice(0, TOP_MECHANISMS).map((m) => m.detail || m.type),
  };
  // a rank observed on several pages keeps the page with the most to say
  if (!existing || record.all_types.length > existing.all_types.length) byRank.set(rank, record);
}

const verdicts = [];
for (const row of strong.rows) {
  const rank = Number((row[rankColumn] || "").trim());
  if (!Number.isFinite(rank)) continue;
  const signature = (row[signatureColumn] || "").trim();
  const observed = byRank.get(rank);
  const claimed = claimedPortion(signature);
  const named = new Set();
  for (const [pattern, types] of VERB_TYPES) {
    if (pattern.test(claimed)) types.forEach((t) => named.add(t));
  }
  const cited = citations.get(rank) || [];
  const verdict = {
    rank,
    selected: isSelected(rank),
    url: observed ? observed.url : null,
    signature,
    signature_names: [...named],
    loudest_recorded: observed ? observed.loudest : [],
    loudest_detail: observed ? observed.detail : [],
    component_rows: cited,
    observation: observed ? observed.observation : null,
    observation_sha256: observed ? observed.sha256 : null,
  };
  if (!observed) {
    verdict.status = "unobserved";
    verdict.note =
      "No observation session was supplied for this rank, so its signature could not be checked against what the harness recorded.";
  } else if (!observed.loudest.length) {
    verdict.status = "static";
    verdict.note =
      "The session recorded no mechanisms, so this is a static signature and the structure diff is the only evidence that it arrived.";
  } else if (!named.size) {
    verdict.status = "no-verb";
    verdict.note =
      "The signature names no behaviour at all, so it cannot be matched against what the harness recorded.";
  } else if (observed.loudest.some((t) => named.has(t))) {
    verdict.status = "pass";
    verdict.note = `The signature names ${observed.loudest.filter((t) => named.has(t)).join(", ")}, which is what this site does loudest.`;
  } else {
    verdict.status = "sidewalk";
    verdict.note =
      `The signature names ${[...named].join(", ")}, but the loudest thing this site does is ` +
      `${observed.loudest.join(" then ")}: ${observed.detail.join(" / ")}. A small true behaviour has been ` +
      "written down in place of the large one, which is how a reference ends up contributing a colour and a " +
      "set of control dimensions. Rewrite the signature to name what the harness ranked first, then take THAT.";
  }
  verdicts.push(verdict);
}

const sidewalks = verdicts.filter((v) => v.selected && (v.status === "sidewalk" || v.status === "no-verb"));
const uncited = verdicts.filter((v) => v.selected && !v.component_rows.length);
for (const v of verdicts) {
  if (!v.selected) v.note = `${v.note} Listed, not selected: no component row is owed to this rank.`;
}
const pass = sidewalks.length === 0 && uncited.length === 0;

const record = {
  schema_version: SCHEMA_VERSION,
  tool: TOOL_NAME,
  checked_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
  dossier: path.relative(process.cwd(), args.dossier).split(path.sep).join("/"),
  dossier_sha256: sha256(args.dossier),
  top_mechanisms_considered: TOP_MECHANISMS,
  verdicts,
  pass,
  verdict: pass
    ? "Every selected reference's recorded signature is the loudest thing that site does, and every one of them is cited by a component the build ships."
    : [
        sidewalks.length
          ? `${sidewalks.length} reference(s) recorded a signature that is not the loudest thing the site does: ranks ${sidewalks.map((v) => v.rank).join(", ")}.`
          : null,
        uncited.length
          ? `${uncited.length} reference(s) are cited by no component row at all: ranks ${uncited.map((v) => v.rank).join(", ")}.`
          : null,
      ].filter(Boolean).join(" "),
};

fs.mkdirSync(path.dirname(args.out), { recursive: true });
fs.writeFileSync(args.out, JSON.stringify(record, null, 2) + "\n", "utf8");

process.stdout.write(
  JSON.stringify(
    {
      ok: true,
      record: args.out,
      pass,
      verdict: record.verdict,
      per_rank: verdicts.map((v) => `${v.rank} -> ${v.status}${v.selected ? "" : " (listed, not selected)"}`),
    },
    null,
    2
  ) + "\n"
);
process.exit(pass ? 0 : 1);
