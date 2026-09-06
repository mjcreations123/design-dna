#!/usr/bin/env node
// Inspect or recover design-dna source-study leases.
//
//   node scripts/source_study_leases.mjs --list
//   node scripts/source_study_leases.mjs --recover [--output-lock FILE]... [--lease-root DIR]
//
// Acquisition (observe_reference.mjs, record_reference.mjs) never removes a
// lease. This is the packaged explicit recovery: only a lease whose owner PID
// is provably gone is removed, after a second probe and a token re-check.
import { inspectSourceStudyLeases, recoverStaleSourceStudyLeases } from './source_study_controller.mjs';

const USAGE = `usage: node source_study_leases.mjs [--list | --recover] [--lease-root DIR] [--output-lock FILE]...\n`;
const argv = process.argv.slice(2);
const options = { output_locks: [] };
let mode = 'list';
for (let index = 0; index < argv.length; index += 1) {
  const argument = argv[index];
  if (argument === '--list') mode = 'list';
  else if (argument === '--recover') mode = 'recover';
  else if (argument === '--lease-root') options.lease_root = argv[++index];
  else if (argument === '--output-lock') options.output_locks.push(argv[++index]);
  else if (argument === '--help' || argument === '-h') { process.stdout.write(USAGE); process.exit(0); }
  else { process.stderr.write(`unknown argument ${argument}\n${USAGE}`); process.exit(2); }
}
const result = mode === 'recover' ? recoverStaleSourceStudyLeases(options) : inspectSourceStudyLeases(options);
process.stdout.write(JSON.stringify({ ok: true, mode, ...result }, null, 2) + '\n');
