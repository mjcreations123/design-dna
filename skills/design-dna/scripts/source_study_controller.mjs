/**
 * Bounded, evidence-preserving controller for source observation/recording.
 *
 * Source studies must never silently stall, fan out forever, or turn a lost
 * browser attachment into a plausible-looking source record. Every meaningful
 * advance is written to an append-only hash-chained journal plus an atomic
 * current-state file. A terminal failure is explicitly ineligible for source
 * selection and retains the caller-provided partial evidence manifest.
 */
import { createHash, randomUUID } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

export const SOURCE_STUDY_SCHEMA_VERSION = 1;
export const SOURCE_STUDY_STATUSES = Object.freeze(['complete', 'partial', 'failed', 'blocked-consent', 'inaccessible', 'rejected']);

export function sourceStudyFailureStatus(code, detail = {}, capturedFrames = 0) {
  const cause = `${code || ''} ${detail.source_code || ''} ${detail.source_error || ''}`;
  if (/consent-handoff|consent-ambiguous|blocked-consent/i.test(cause)) return 'blocked-consent';
  if (/rejected|source-quality-rejection/i.test(cause)) return 'rejected';
  if (/navigation-(?:http|network|status|no-response)|ERR_NAME_NOT_RESOLVED|ERR_CONNECTION|inaccessible|http-status/i.test(cause)) return 'inaccessible';
  if (capturedFrames > 0 && /incomplete|no-progress|timeout|duration-exceeded|attachment-lost|recording-failed|observation-failed|graph-explosion|target-loop/i.test(cause)) return 'partial';
  return 'failed';
}
export const DEFAULT_SOURCE_STUDY_LIMITS = Object.freeze({
  max_no_progress_ms: 60_000,
  max_step_ms: 60_000,
  max_screenshot_ms: 30_000,
  max_total_elapsed_ms: 1_800_000,
  max_progress_events: 100_000,
  max_routes: 1_000,
  max_targets: 10_000,
  max_target_edges: 20_000,
  max_consecutive_target_repeats: 3,
  max_total_target_visits_per_key: 12,
  max_repeated_target_edge_visits: 6,
});
export const HARD_SOURCE_STUDY_LIMITS = Object.freeze({
  max_no_progress_ms: 300_000,
  max_step_ms: 300_000,
  max_screenshot_ms: 120_000,
  // A complete study of a reference with six inner routes at two profiles
  // costs well over an hour; the producer derives its budget from its declared
  // route scope and this is the ceiling that derivation may reach.
  max_total_elapsed_ms: 14_400_000,
  max_progress_events: 200_000,
  max_routes: 5_000,
  max_targets: 50_000,
  max_target_edges: 100_000,
  max_consecutive_target_repeats: 12,
  max_total_target_visits_per_key: 100,
  max_repeated_target_edge_visits: 50,
});
export const SOURCE_STUDY_EVENT_KINDS = new Set([
  'started', 'frame-captured', 'event-observed', 'state-complete',
  'route-visited', 'target-observed', 'step-complete', 'postprocess-start',
  'postprocess-chunk', 'postprocess-complete', 'artifact-retained', 'complete', 'failed',
]);

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (!value || typeof value !== 'object') return JSON.stringify(value);
  return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
}

function sha(value) {
  return createHash('sha256').update(canonical(value)).digest('hex');
}

function safeArtifactBinding(file) {
  if (typeof file !== 'string' || !file) return null;
  try {
    const stat = fs.lstatSync(file);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1) return null;
    return { file, sha256: createHash('sha256').update(fs.readFileSync(file)).digest('hex') };
  } catch { return null; }
}

function safeFilePart(value) {
  return String(value || 'source-study').replace(/[^a-zA-Z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || 'source-study';
}

function typedError(code, message, details = {}) {
  const error = new Error(message);
  error.code = code;
  Object.assign(error, details);
  return error;
}

function attachmentLost(error) {
  return /target page, context or browser has been closed|execution context was destroyed|frame was detached|most likely because of a navigation|not attached|session closed/i
    .test(String(error?.message || error));
}

function isWithin(child, parent) {
  const relative = path.relative(parent, child);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

export class SourceStudyController {
  constructor(options = {}) {
    if (!options.output_dir || !options.id || !options.producer) {
      throw new Error('source study controller requires output_dir, id, and producer.');
    }
    this.now = typeof options.now === 'function' ? options.now : () => Date.now();
    this.partialEvidence = typeof options.partial_evidence === 'function' ? options.partial_evidence : () => null;
    this.abort = typeof options.abort === 'function' ? options.abort : null;
    this.requiredCompletionArtifactKinds = Array.isArray(options.required_completion_artifact_kinds)
      ? [...new Set(options.required_completion_artifact_kinds)] : ['frame'];
    if (!this.requiredCompletionArtifactKinds.length || this.requiredCompletionArtifactKinds.some((kind) => typeof kind !== 'string' || !kind)) {
      throw new Error('source study completion requires one or more explicit immutable artifact kinds.');
    }
    if (options.source_kind && options.source_kind !== 'public-source' && options.source_kind !== 'proof-slice') {
      throw new Error('source study source_kind must be public-source or proof-slice.');
    }
    this.limits = { ...DEFAULT_SOURCE_STUDY_LIMITS, ...(options.limits || {}) };
    for (const [name, value] of Object.entries(this.limits)) {
      if (!Object.hasOwn(HARD_SOURCE_STUDY_LIMITS, name) || !Number.isInteger(value) || value < 1 || value > HARD_SOURCE_STUDY_LIMITS[name]) {
        throw new Error(`source study limit ${name} must be a positive integer within its hard safety cap.`);
      }
    }
    const prefix = `${safeFilePart(options.id)}${options.profile ? `-${safeFilePart(options.profile)}` : ''}`;
    this.outputDir = path.resolve(options.output_dir);
    fs.mkdirSync(this.outputDir, { recursive: true });
    this.progressFile = path.join(this.outputDir, `${prefix}-source-study-progress.json`);
    this.eventFile = path.join(this.outputDir, `${prefix}-source-study-progress.jsonl`);
    this.failureFile = path.join(this.outputDir, `${prefix}-source-study-failure.json`);
    if ([this.progressFile, this.eventFile, this.failureFile].some((file) => fs.existsSync(file))) {
      throw typedError('source-study-existing-output',
        `Source study output already exists for ${prefix}; refusing to splice a new run into an existing progress hash chain.`,
        { source_study_output: { progress: this.progressFile, events: this.eventFile, failure: this.failureFile } });
    }
    // Atomic creation closes the same-ID race between the read-only preflight
    // above and the first durable event; a second writer never opens this log.
    try { fs.writeFileSync(this.eventFile, '', { encoding: 'utf8', flag: 'wx' }); }
    catch (error) { throw typedError('source-study-existing-output', `Source study journal is already owned for ${prefix}.`, { source_error: String(error?.message || error) }); }
    const epoch = this.now();
    const commandStarted = options.started_epoch_ms ?? epoch;
    if (!Number.isInteger(commandStarted) || commandStarted < 0 || commandStarted > epoch) {
      throw new Error('source study started_epoch_ms must be an actual prior command start.');
    }
    this.state = {
      schema_version: SOURCE_STUDY_SCHEMA_VERSION,
      kind: 'source-study-progress',
      status: 'active',
      source_status: 'partial',
      eligible_for_source_selection: false,
      id: options.id,
      profile: options.profile || null,
      producer: options.producer,
      source_kind: options.source_kind || 'public-source',
      started_at: new Date(commandStarted).toISOString(),
      last_progress_at: new Date(epoch).toISOString(),
      last_progress_epoch_ms: epoch,
      last_progress_kind: 'started',
      counters: { frames: 0, events: 0, states: 0, routes: 0, targets: 0 },
      limits: { ...this.limits },
      progress_event_file: path.basename(this.eventFile),
      progress_event_count: 0,
      tail_event_sha256: null,
    };
    this.routeKeys = new Set();
    this.targetKeys = new Set();
    this.targetVisitCounts = new Map();
    this.targetEdgeCounts = new Map();
    this.retainedArtifacts = [];
    this.lastTargetKey = null;
    this.consecutiveTargetRepeats = 0;
    this.terminated = false;
    this.closed = false;
    this.activeSteps = new Set();
    this.terminationListeners = new Set();
    this.writeSnapshot();
    this.appendEvent('started', { detail: options.detail || null });
    // Bounds also apply while a browser API is pending outside an individual
    // step. The timer closes only this study's owned context, never a sibling.
    this.watchdog = setInterval(() => {
      try { this.assertHealthy(); }
      catch (error) {
        clearInterval(this.watchdog);
        if (this.abort) Promise.resolve().then(() => this.abort({ kind: 'watchdog', code: error.code })).catch(() => {});
      }
    }, Math.min(250, Math.max(5, Math.floor(this.limits.max_no_progress_ms / 4))));
    this.watchdog.unref?.();
  }

  snapshot() {
    return JSON.parse(JSON.stringify(this.state));
  }

  retainArtifact(artifact) {
    if (this.closed || this.terminated) {
      throw typedError('source-study-terminal-closed', 'A terminal source study cannot accept a newly retained artifact.', {
        source_study: this.snapshot(),
      });
    }
    if (!artifact || typeof artifact !== 'object' || typeof artifact.kind !== 'string' || !artifact.kind) {
      throw new Error('source study retained artifact needs a named kind.');
    }
    this.assertHealthy();
    this.retainedArtifacts.push(JSON.parse(JSON.stringify(artifact)));
    this.progress('artifact-retained', { kind: artifact.kind, file: artifact.file || null });
  }

  writeSnapshot() {
    const temporary = `${this.progressFile}.tmp-${process.pid}-${this.state.progress_event_count}`;
    try {
      fs.writeFileSync(temporary, `${JSON.stringify(this.state, null, 2)}\n`, 'utf8');
      try { fs.renameSync(temporary, this.progressFile); }
      catch (renameError) {
        // Copying over an existing pathname is neither atomic nor safe when
        // that name has become an alias. Preserve the old snapshot and fail.
        fs.rmSync(temporary, { force: true });
        return { ok: false, error: `atomic rename: ${String(renameError?.message || renameError)}` };
      }
      return { ok: true };
    } catch (error) {
      fs.rmSync(temporary, { force: true });
      return { ok: false, error: String(error?.message || error) };
    }
  }

  appendEvent(kind, detail = {}) {
    if (this.closed || (this.terminated && kind !== 'failed')) {
      throw typedError('source-study-terminal-closed', 'A terminal source study cannot append new progress events.');
    }
    if (!SOURCE_STUDY_EVENT_KINDS.has(kind)) {
      throw this.terminate('source-study-invalid-progress-event', `Source study attempted unsupported progress event ${JSON.stringify(kind)}.`, { kind });
    }
    if (kind !== 'failed' && this.state.progress_event_count >= this.limits.max_progress_events) {
      throw this.terminate('source-study-progress-budget-exhausted',
        `Source study reached its explicit ${this.limits.max_progress_events}-event progress budget.`, { kind });
    }
    const now = this.now();
    const core = {
      schema_version: SOURCE_STUDY_SCHEMA_VERSION,
      sequence: this.state.progress_event_count + 1,
      at: new Date(now).toISOString(),
      kind,
      counters: { ...this.state.counters },
      previous_sha256: this.state.tail_event_sha256,
      detail,
    };
    const entry = { ...core, sha256: sha(core) };
    fs.appendFileSync(this.eventFile, `${JSON.stringify(entry)}\n`, 'utf8');
    this.state.progress_event_count = entry.sequence;
    this.state.tail_event_sha256 = entry.sha256;
    this.state.last_progress_at = entry.at;
    this.state.last_progress_epoch_ms = now;
    this.state.last_progress_kind = kind;
    const snapshot = this.writeSnapshot();
    if (!snapshot.ok) {
      const error = typedError('source-study-snapshot-commit-failed',
        'Source-study journal advanced but its current snapshot could not be committed.',
        { snapshot_commit_error: snapshot.error, journal_tail_sha256: entry.sha256, journal_sequence: entry.sequence });
      this.lastSnapshotCommitFailure = error;
      throw error;
    }
    return entry;
  }

  progress(kind, detail = {}) {
    this.assertHealthy();
    return this.appendEvent(kind, detail);
  }

  markFrame(detail = {}) {
    this.assertHealthy();
    this.state.counters.frames += 1;
    return this.progress('frame-captured', detail);
  }

  markEvent(detail = {}) {
    this.assertHealthy();
    this.state.counters.events += 1;
    return this.progress('event-observed', detail);
  }

  markState(stateId, detail = {}) {
    this.assertHealthy();
    if (typeof stateId !== 'string' || !stateId) {
      throw this.terminate('source-study-invalid-state', 'Source study attempted to mark an unnamed state.', detail);
    }
    this.state.counters.states += 1;
    return this.progress('state-complete', { state_id: stateId, ...detail });
  }

  markRoute(route, detail = {}) {
    this.assertHealthy();
    if (typeof route !== 'string' || !route) {
      throw this.terminate('source-study-invalid-route', 'Source study attempted to queue an unnamed route.', detail);
    }
    this.routeKeys.add(route);
    if (this.routeKeys.size > this.limits.max_routes) {
      throw this.terminate('source-study-recursive-graph-explosion',
        `Source study discovered ${this.routeKeys.size} routes, above its explicit ${this.limits.max_routes}-route safety bound.`,
        { route, routes: [...this.routeKeys].sort() });
    }
    this.state.counters.routes = this.routeKeys.size;
    return this.progress('route-visited', { route, ...detail });
  }

  markTarget(targetKey, detail = {}) {
    this.assertHealthy();
    if (typeof targetKey !== 'string' || !targetKey) {
      throw this.terminate('source-study-invalid-target', 'Source study attempted to exercise an unnamed target.', detail);
    }
    this.targetKeys.add(targetKey);
    if (this.targetKeys.size > this.limits.max_targets) {
      throw this.terminate('source-study-target-graph-explosion',
        `Source study discovered ${this.targetKeys.size} targets, above its explicit ${this.limits.max_targets}-target safety bound.`,
        { target_key: targetKey });
    }
    this.consecutiveTargetRepeats = this.lastTargetKey === targetKey ? this.consecutiveTargetRepeats + 1 : 1;
    const totalVisits = (this.targetVisitCounts.get(targetKey) || 0) + 1;
    this.targetVisitCounts.set(targetKey, totalVisits);
    const edge = this.lastTargetKey ? `${this.lastTargetKey}\u0000${targetKey}` : null;
    const edgeVisits = edge ? (this.targetEdgeCounts.get(edge) || 0) + 1 : 0;
    if (edge) this.targetEdgeCounts.set(edge, edgeVisits);
    if (this.targetEdgeCounts.size > this.limits.max_target_edges) {
      throw this.terminate('source-study-target-edge-explosion',
        `Source study discovered ${this.targetEdgeCounts.size} target edges, above its explicit ${this.limits.max_target_edges}-edge safety bound.`,
        { target_key: targetKey, edge });
    }
    this.lastTargetKey = targetKey;
    if (this.consecutiveTargetRepeats > this.limits.max_consecutive_target_repeats ||
        totalVisits > this.limits.max_total_target_visits_per_key ||
        edgeVisits > this.limits.max_repeated_target_edge_visits) {
      throw this.terminate('source-study-repeated-target-loop',
        `Source study detected a repeated target path at ${targetKey}, exceeding an explicit loop bound.`,
        { target_key: targetKey, consecutive_repeats: this.consecutiveTargetRepeats,
          total_visits: totalVisits, edge, edge_visits: edgeVisits });
    }
    this.state.counters.targets = this.targetKeys.size;
    return this.progress('target-observed', { target_key: targetKey, ...detail });
  }

  assertHealthy() {
    if (this.closed) {
      throw typedError('source-study-terminal-closed', 'Source study reached a terminal state and cannot accept further progress or mutation.', {
        source_study: this.snapshot(),
      });
    }
    if (this.terminated) {
      throw typedError('source-study-already-terminated', 'Source study was already terminated and is ineligible for source selection.', {
        source_study: this.snapshot(),
      });
    }
    const elapsed = this.now() - this.state.last_progress_epoch_ms;
    const totalElapsed = this.now() - Date.parse(this.state.started_at);
    if (totalElapsed > this.limits.max_total_elapsed_ms) {
      throw this.terminate('source-study-total-duration-exceeded',
        `Source study exceeded its explicit ${this.limits.max_total_elapsed_ms}ms total-duration bound.`,
        { elapsed_ms: totalElapsed });
    }
    if (elapsed > this.limits.max_no_progress_ms) {
      throw this.terminate('source-study-no-progress',
        `Source study made no durable progress for ${elapsed}ms (limit ${this.limits.max_no_progress_ms}ms).`,
        { elapsed_ms: elapsed, last_progress_kind: this.state.last_progress_kind });
    }
  }

  async step(kind, work, options = {}) {
    this.assertHealthy();
    if (options.target_key) this.markTarget(options.target_key, { step: kind });
    const timeout = options.timeout_ms || (options.screenshot ? this.limits.max_screenshot_ms : this.limits.max_step_ms);
    if (!Number.isInteger(timeout) || timeout < 1) throw new Error(`source study step ${kind} has invalid timeout.`);
    const abort = options.abort || this.abort;
    if (typeof abort !== 'function') {
      throw this.terminate('source-study-cancellation-unavailable',
        `${kind} has no explicit cancellation/close teardown, so it cannot be bounded safely.`, { source_study_step: kind });
    }
    let timeoutId = null;
    const timeoutFailure = new Promise((_, reject) => {
      timeoutId = setTimeout(() => {
        // Teardown itself can lose its browser attachment. Request it without
        // making the deterministic deadline wait for that unresolved promise.
        Promise.resolve().then(() => abort({ kind, timeout_ms: timeout, screenshot: options.screenshot === true })).catch(() => {});
        reject(typedError(
          options.screenshot ? 'source-study-screenshot-timeout' : 'source-study-step-timeout',
          `${kind} exceeded its explicit ${timeout}ms source-study bound and its page/context teardown was requested.`,
          { source_study_step: kind, timeout_ms: timeout, teardown_requested: true },
        ));
      }, timeout);
    });
    const token = `${kind}:${this.now()}:${Math.random().toString(36).slice(2, 10)}`;
    let onTermination;
    const terminalFailure = new Promise((_, reject) => {
      onTermination = reject;
      this.terminationListeners.add(onTermination);
    });
    this.activeSteps.add(token);
    try {
      const result = await Promise.race([Promise.resolve().then(work), timeoutFailure, terminalFailure]);
      this.progress('step-complete', { step: kind, ...(options.detail || {}) });
      return result;
    } catch (error) {
      if (error?.code?.startsWith('source-study-')) throw this.terminate(error.code, error.message, error);
      if (attachmentLost(error)) {
        throw this.terminate('source-study-attachment-lost',
          `${kind} lost its page/frame/browser attachment; partial evidence is retained but ineligible.`,
          { source_error: String(error?.message || error) });
      }
      if (typeof error?.code === 'string' && error.code) {
        throw this.terminate(error.code, String(error.message || error), {
          source_code: error.code, source_error: String(error.message || error), navigation: error.navigation || null,
          census_diagnostic: error.census_diagnostic || null, consent_candidate: error.consent_candidate || null,
        });
      }
      throw this.terminate('source-study-step-failed', `${kind} failed during source study.`,
        { source_error: String(error?.message || error) });
    } finally {
      if (timeoutId !== null) clearTimeout(timeoutId);
      this.terminationListeners.delete(onTermination);
      this.activeSteps.delete(token);
    }
  }

  terminate(code, message, detail = {}) {
    if (this.closed) {
      return typedError('source-study-terminal-closed', 'Source study reached a terminal state and cannot be rewritten as new source evidence.', {
        source_study: this.snapshot(),
      });
    }
    if (!this.terminated) {
      this.terminated = true;
      clearInterval(this.watchdog);
      this.state.status = 'failed';
      this.state.source_status = sourceStudyFailureStatus(code, detail, this.state.counters.frames);
      this.state.eligible_for_source_selection = false;
      this.terminalCause = { code, message };
      let snapshotCommitFailure = null;
      try { this.appendEvent('failed', { code, message }); }
      catch (error) { snapshotCommitFailure = String(error?.message || error); }
      let partialEvidence;
      try { partialEvidence = this.partialEvidence(); }
      catch (error) { partialEvidence = { capture_failed: true, reason: String(error?.message || error) }; }
      partialEvidence = partialEvidence && typeof partialEvidence === 'object' && !Array.isArray(partialEvidence)
        ? { ...partialEvidence, retained_artifacts: this.retainedArtifacts.slice() }
        : { value: partialEvidence, retained_artifacts: this.retainedArtifacts.slice() };
      const failure = {
        schema_version: SOURCE_STUDY_SCHEMA_VERSION,
        kind: 'source-study-partial-failure',
        status: 'incomplete-not-selection-evidence',
        source_status: this.state.source_status,
        eligible_for_source_selection: false,
        id: this.state.id,
        profile: this.state.profile,
        producer: this.state.producer,
        error: { code, message },
        progress: this.snapshot(),
        partial_evidence: partialEvidence,
        detail: detail && typeof detail === 'object' ? detail : { value: String(detail) },
        snapshot_commit_failure: snapshotCommitFailure,
      };
      try {
        fs.writeFileSync(this.failureFile, `${JSON.stringify(failure, null, 2)}\n`, 'utf8');
        this.failureBinding = { file: this.failureFile, sha256: createHash('sha256').update(fs.readFileSync(this.failureFile)).digest('hex') };
        this.state.failure_artifact = { file: path.basename(this.failureFile), sha256: this.failureBinding.sha256 };
      } catch (error) { this.failureWriteFailure = String(error?.message || error); }
      const terminalSnapshot = this.writeSnapshot();
      if (!terminalSnapshot.ok) snapshotCommitFailure = snapshotCommitFailure || terminalSnapshot.error;
      if (snapshotCommitFailure && this.failureBinding) {
        try {
          const persisted = JSON.parse(fs.readFileSync(this.failureFile, 'utf8'));
          persisted.snapshot_commit_failure = snapshotCommitFailure;
          fs.writeFileSync(this.failureFile, `${JSON.stringify(persisted, null, 2)}\n`, 'utf8');
          this.failureBinding = { file: this.failureFile, sha256: createHash('sha256').update(fs.readFileSync(this.failureFile)).digest('hex') };
          this.state.failure_artifact = { file: path.basename(this.failureFile), sha256: this.failureBinding.sha256 };
          this.writeSnapshot();
        } catch (error) { this.failureWriteFailure = String(error?.message || error); }
      }
    }
    let progressBinding = safeArtifactBinding(this.progressFile);
    try { if (canonical(JSON.parse(fs.readFileSync(this.progressFile, 'utf8'))) !== canonical(this.state)) progressBinding = null; }
    catch { progressBinding = null; }
    const failureBinding = safeArtifactBinding(this.failureFile);
    if (!failureBinding) this.failureBinding = null;
    const bindingsValid = Boolean(progressBinding && failureBinding);
    const originalCause = this.terminalCause || { code, message };
    const terminalCode = bindingsValid ? originalCause.code : 'source-study-artifact-binding-invalid';
    const terminalMessage = bindingsValid ? originalCause.message
      : `Source study could not verify its terminal artifact bindings after ${originalCause.code}; the original cause is retained.`;
    const terminalError = typedError(terminalCode, terminalMessage, {
      source_study: this.snapshot(), source_study_progress: progressBinding,
      source_study_failure: failureBinding, original_cause: originalCause,
      navigation: detail.navigation || null, census_diagnostic: detail.census_diagnostic || null,
      consent_candidate: detail.consent_candidate || null,
      snapshot_commit_failure: this.lastSnapshotCommitFailure?.snapshot_commit_error || null,
    });
    // A watchdog deadline must also reject pending browser work when closing
    // the lost attachment itself never resolves. Teardown is still requested,
    // but a larger per-step timeout cannot extend the command/idle boundary.
    for (const reject of this.terminationListeners) reject(terminalError);
    return terminalError;
  }

  complete(detail = {}) {
    this.assertHealthy();
    const artifacts = Array.isArray(detail.signed_artifacts) ? detail.signed_artifacts : [];
    const artifactProblems = [];
    const validArtifacts = [];
    for (const artifact of artifacts) {
      if (!artifact || typeof artifact !== 'object' || typeof artifact.kind !== 'string' ||
          typeof artifact.file !== 'string' || !Number.isInteger(artifact.bytes) || artifact.bytes < 1 ||
          typeof artifact.sha256 !== 'string' || !/^[a-f0-9]{64}$/i.test(artifact.sha256) ||
          artifact.producer !== this.state.producer) {
        artifactProblems.push('artifact metadata/provenance is incomplete');
        continue;
      }
      const candidate = path.resolve(this.outputDir, artifact.file);
      try {
        if (!isWithin(candidate, this.outputDir)) {
          artifactProblems.push(`artifact ${artifact.file} escapes the source-study output root`);
          continue;
        }
        const stat = fs.lstatSync(candidate);
        if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1 ||
            stat.size !== artifact.bytes || createHash('sha256').update(fs.readFileSync(candidate)).digest('hex') !== artifact.sha256) {
          artifactProblems.push(`artifact ${artifact.file} does not match immutable bytes/provenance`);
          continue;
        }
      } catch {
        artifactProblems.push(`artifact ${artifact.file} is not a readable regular file`);
        continue;
      }
      validArtifacts.push(artifact);
    }
    const kinds = new Set(validArtifacts.map((artifact) => artifact.kind));
    const missingKinds = this.requiredCompletionArtifactKinds.filter((kind) => !kinds.has(kind));
    if (detail.terminal_success !== true || detail.coverage_complete === false || !this.state.counters.frames || missingKinds.length || artifactProblems.length || this.activeSteps.size) {
      throw this.terminate('source-study-completion-unproven',
        'Source study cannot become eligible without terminal success, captured frames, no active work, and required immutable signed artifacts.',
        { terminal_success: detail.terminal_success === true, frames: this.state.counters.frames,
          active_steps: this.activeSteps.size, missing_artifact_kinds: missingKinds, artifact_problems: artifactProblems });
    }
    this.state.status = 'complete';
    this.state.source_status = 'complete';
    this.state.eligible_for_source_selection = this.state.source_kind === 'public-source';
    this.state.signed_artifacts = validArtifacts.map((artifact) => ({
      kind: artifact.kind, file: artifact.file, bytes: artifact.bytes,
      sha256: artifact.sha256, producer: artifact.producer,
    }));
    this.appendEvent('complete', detail);
    this.closed = true;
    clearInterval(this.watchdog);
    return this.snapshot();
  }
}

export function createSourceStudyController(options) {
  return new SourceStudyController(options);
}

export function sourceStudyPreflightFailure(options, code, message, detail = {}) {
  try {
    const study = createSourceStudyController({ output_dir: options.output_dir, id: `${options.id}-preflight`, producer: options.producer,
      partial_evidence: () => ({ phase: 'preflight', browser_started: false, ...detail }) });
    return study.terminate(code, message, detail);
  } catch (error) {
    return typedError(code, message, { source_status: 'failed', eligible_for_source_selection: false,
      preflight_artifact_error: String(error?.message || error), detail });
  }
}

export function acquireSourceStudyOutputLease(options) {
  fs.mkdirSync(options.output_dir, { recursive: true });
  const file = path.join(path.resolve(options.output_dir), `.design-dna-source-study-${safeFilePart(options.id)}.lock.json`);
  let owner = null, ownerAlive = null;
  {
    const token = randomUUID();
    try {
      fs.writeFileSync(file, JSON.stringify({ schema_version: 1, pid: process.pid, token, id: options.id, producer: options.producer }) + '\n', { encoding: 'utf8', flag: 'wx' });
      return { release() { try { if (JSON.parse(fs.readFileSync(file, 'utf8')).token === token) fs.rmSync(file); } catch {} } };
    } catch (error) {
      if (error.code !== 'EEXIST') throw error;
      let existing;
      try {
        const stat = fs.lstatSync(file);
        if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1) throw new Error('Lease is not a single-link ordinary file.');
        existing = JSON.parse(fs.readFileSync(file, 'utf8'));
        if (!Number.isInteger(existing.pid) || existing.pid < 1 || !existing.token) throw new Error('Lease owner is malformed.');
        owner = { pid: existing.pid, token: existing.token, id: existing.id, producer: existing.producer };
        ownerAlive = true;
        try { process.kill(existing.pid, 0); } catch (probe) { ownerAlive = probe.code !== 'ESRCH'; }
      } catch { /* uncertain ownership is preserved and never reclaimed */ }
    }
  }
  throw sourceStudyPreflightFailure(options, ownerAlive === false ? 'source-study-stale-output-lease' : 'source-study-output-busy',
    ownerAlive === false
      ? `Source-study output for ${options.id} retains a stale lease. No lease was removed and no browser started; inspect the exact owner and recover the lease separately ("node scripts/source_study_leases.mjs --recover --output-lock <lock file>"), or use a fresh output directory.`
      : `Source-study output for ${options.id} is owned by another command; no browser or second evidence writer was started.`,
    { output_lock: file, observed_owner: owner, observed_owner_alive: ownerAlive, automatic_recovery: false });
}

/** A fixed two-run machine-wide ceiling across IDs and output directories.
 * Stale, live, and malformed leases are preserved. A check-then-unlink stale
 * takeover could remove a racing fresh owner, so recovery is a separate action.
 * A third caller receives a durable typed refusal immediately, never a queue of
 * invisible Chromium processes or permission to delete another runner's files.
 */
export function acquireSourceStudyRunnerLease(options) {
  const leaseRoot = options.lease_root || path.join(os.tmpdir(), 'design-dna-source-study-runners-v1');
  fs.mkdirSync(leaseRoot, { recursive: true });
  if (fs.lstatSync(leaseRoot).isSymbolicLink()) throw new Error('Source runner lease root cannot be a symbolic link.');
  const active = [];
  for (let slot = 1; slot <= 2; slot += 1) {
    const file = path.join(leaseRoot, `runner-${slot}.json`);
    {
      const token = randomUUID();
      const record = { schema_version: 1, pid: process.pid, token, id: options.id, producer: options.producer, started_at: new Date().toISOString() };
      try {
        fs.writeFileSync(file, JSON.stringify(record) + '\n', { encoding: 'utf8', flag: 'wx' });
        let released = false;
        return { slot, release() {
          if (released) return;
          released = true;
          try { if (JSON.parse(fs.readFileSync(file, 'utf8')).token === token) fs.rmSync(file); } catch {}
        } };
      } catch (error) {
        if (error.code !== 'EEXIST') throw error;
        let existing;
        try {
          const stat = fs.lstatSync(file);
          if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1) throw new Error('Lease is not a single-link ordinary file.');
          existing = JSON.parse(fs.readFileSync(file, 'utf8'));
          if (!Number.isInteger(existing.pid) || existing.pid < 1 || !existing.token) throw new Error('Lease owner is malformed.');
        } catch { active.push({ slot, lease_file: file, observed_owner_alive: null, state: 'unverified-owner' }); continue; }
        let alive = true;
        try { process.kill(existing.pid, 0); } catch (probe) { alive = probe.code !== 'ESRCH'; }
        active.push({ slot, pid: existing.pid, id: existing.id, producer: existing.producer,
          lease_file: file, observed_owner_alive: alive, state: alive ? 'active-owner' : 'stale-owner' });
      }
    }
  }
  const stale = active.some((owner) => owner.observed_owner_alive === false);
  throw sourceStudyPreflightFailure(options, stale ? 'source-study-stale-runner-lease' : 'source-study-concurrency-limited',
    stale ? 'The machine-wide source-study slots include a stale lease. No lease was removed and no browser launched; inspect and recover the exact stale lease separately: "node scripts/source_study_leases.mjs --list", then "--recover" for a provably dead owner.'
      : 'Two source-study runner slots are occupied or have unverified ownership. No browser was launched; finish or inspect those runs before retrying.',
    { maximum_active_runners: 2, active_runners: active, automatic_recovery: false });
}

function describeSourceStudyLeaseFile(file, slot = null) {
  if (!fs.existsSync(file)) return { slot, lease_file: file, state: 'free' };
  try {
    const stat = fs.lstatSync(file);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1) {
      return { slot, lease_file: file, state: 'unverified-owner', reason: 'not a single-link ordinary file' };
    }
    const existing = JSON.parse(fs.readFileSync(file, 'utf8'));
    if (!Number.isInteger(existing.pid) || existing.pid < 1 || !existing.token) {
      return { slot, lease_file: file, state: 'unverified-owner', reason: 'malformed owner record' };
    }
    let alive = true;
    try { process.kill(existing.pid, 0); } catch (probe) { alive = probe.code !== 'ESRCH'; }
    return { slot, lease_file: file, pid: existing.pid, id: existing.id || null, producer: existing.producer || null,
      started_at: existing.started_at || null, token: existing.token,
      observed_owner_alive: alive, state: alive ? 'active-owner' : 'stale-owner' };
  } catch (error) {
    return { slot, lease_file: file, state: 'unverified-owner', reason: String(error?.message || error).slice(0, 200) };
  }
}

/** Read-only inspection of the machine-wide runner slots (and any named
 * output locks). Nothing is created or removed. */
export function inspectSourceStudyLeases(options = {}) {
  const leaseRoot = options.lease_root || path.join(os.tmpdir(), 'design-dna-source-study-runners-v1');
  const slots = [];
  for (let slot = 1; slot <= 2; slot += 1) slots.push(describeSourceStudyLeaseFile(path.join(leaseRoot, `runner-${slot}.json`), slot));
  const outputLocks = (options.output_locks || []).map((file) => describeSourceStudyLeaseFile(path.resolve(file)));
  return { lease_root: leaseRoot, maximum_active_runners: 2, slots, output_locks: outputLocks };
}

/** Explicit recovery of leases whose owner PID is provably gone. Acquisition
 * never does this. The owner is probed a second time and the file's token is
 * re-read immediately before unlink, so a fresh owner that raced into the
 * slot is never removed. Every removal is appended to a recovery log. */
export function recoverStaleSourceStudyLeases(options = {}) {
  const inspection = inspectSourceStudyLeases(options);
  const recovered = [], kept = [];
  for (const lease of [...inspection.slots, ...inspection.output_locks]) {
    if (lease.state !== 'stale-owner') { kept.push(lease); continue; }
    let alive = true;
    try { process.kill(lease.pid, 0); } catch (probe) { alive = probe.code !== 'ESRCH'; }
    if (alive) { kept.push({ ...lease, state: 'active-owner', observed_owner_alive: true }); continue; }
    try {
      const current = JSON.parse(fs.readFileSync(lease.lease_file, 'utf8'));
      if (current.token !== lease.token) { kept.push({ ...lease, state: 'replaced-during-recovery' }); continue; }
      fs.rmSync(lease.lease_file);
      recovered.push({ ...lease, state: 'recovered' });
    } catch (error) {
      kept.push({ ...lease, state: 'recovery-failed', reason: String(error?.message || error).slice(0, 200) });
    }
  }
  const log = path.join(inspection.lease_root, 'recovery-log.jsonl');
  if (recovered.length) {
    fs.mkdirSync(inspection.lease_root, { recursive: true });
    fs.appendFileSync(log, JSON.stringify({ at: new Date().toISOString(), by_pid: process.pid, recovered }) + '\n');
  }
  return { ...inspection, recovered, kept, recovery_log: log };
}
