/**
 * Continuous source-side autonomous-surface watch.
 *
 * This intentionally watches only disruptive UI surfaces (dialogs, modal
 * layers, and viewport-covering fixed overlays), not every decorative DOM
 * mutation. It runs a MutationObserver plus a timer/animation sampler inside
 * the real page so an overlay that appears after an initial census cannot be
 * reclassified as a quiet rest state.
 */

import { discoverUnaddressableClosedRoots } from './browser_evidence.mjs';

function normalizeSelectors(values) {
  return [...new Set((values || []).filter((value) => typeof value === 'string' && value.trim()))];
}

export const SOURCE_SURFACE_EVENT_KINDS = new Set([
  'surface-node-added', 'surface-node-removed', 'surface-attribute-mutation',
  'autonomous-surface-appeared', 'surface-css-animation-event',
  'surface-pseudo-animation-event', 'surface-waapi-active',
  'surface-state-updated', 'uninspectable-cross-origin-frame',
]);
// 50ms is stricter than the recorder's 15fps / 66.67ms floor. The watcher is
// source evidence, so a delayed timer sample is recorded and fails rather
// than quietly stretching a claimed continuous interval.
export const SOURCE_SURFACE_SAMPLE_INTERVAL_MS = 50;

function generatedEvidence(value) {
  return Boolean(value && typeof value === 'object' && (
    (typeof value.file === 'string' && Number.isInteger(value.bytes) && typeof value.sha256 === 'string') ||
    Number.isFinite(value.video_t_s)
  ));
}

function generatedRecordingTimestamp(value) {
  return generatedEvidence(value) && Number.isFinite(value?.video_t_s) && value.video_t_s >= 0;
}

function consentAuthorizationValid(value) {
  return Boolean(value && typeof value === 'object' && value.disposition === 'reject-or-essential-only' &&
    value.root && typeof value.root === 'object' && value.evidence && typeof value.evidence === 'object' &&
    generatedEvidence(value.evidence.before) && generatedEvidence(value.evidence.action) && generatedEvidence(value.evidence.after));
}

function finiteInteger(value) {
  return Number.isInteger(value) && value >= 0;
}

function safeSurfaceLabel(surface, selector = null) {
  const tag = typeof surface?.tag === 'string' && surface.tag ? surface.tag : 'surface';
  const role = typeof surface?.role === 'string' && surface.role ? `[role="${surface.role}"]` : tag;
  const flodesk = surface?.data_ff_el === 'modal' || /\bff[-_]/i.test(String(surface?.class_name || ''));
  const named = flodesk ? 'Flodesk modal' : role;
  return selector ? `${named} ${selector}` : named;
}

function inventoryMap(sample) {
  if (!sample || !Array.isArray(sample.candidate_inventory)) return null;
  const values = new Map();
  for (const candidate of sample.candidate_inventory) {
    if (!candidate || typeof candidate !== 'object' || typeof candidate.owner_id !== 'string' || !candidate.owner_id) return null;
    values.set(candidate.owner_id, candidate);
  }
  return values;
}

function eventInGap(event, gap) {
  return finiteInteger(event?.elapsed_ms) && event.elapsed_ms >= gap.from_elapsed_ms && event.elapsed_ms <= gap.to_elapsed_ms;
}

function sameInventory(first, second) {
  if (!first || !second || first.size !== second.size) return false;
  for (const [key, value] of first) {
    const other = second.get(key);
    if (!other || other.selector !== value.selector) return false;
    const a = value.surface || {}, b = other.surface || {};
    if (a.tag !== b.tag || a.role !== b.role || a.id !== b.id || a.class_name !== b.class_name || a.connected !== b.connected) return false;
  }
  return true;
}

function describesSurface(value) {
  return Boolean(value && typeof value === 'object' && (
    value.lexical_surface_signal === true || value.geometric_surface_signal === true ||
    value.role === 'dialog' || value.aria_modal === 'true' || value.data_ff_el === 'modal'
  ));
}

/**
 * A delayed JS callback is never silently converted into a clean interval.
 * We preserve every detected gap and only clear a gap as non-ambiguous when
 * both bracketing sampler inventories are exact, unchanged, and no relevant
 * mutation/animation/event callback landed in that interval. The recorder's
 * generated video/frame stream is bound separately; this routine records the
 * exact window it must cover instead of pretending DOM samples are video.
 */
export function reconcileSourceTimingGaps({
  gaps = [], samples = [], events = [], mutationBatches = [], animationEvents = [],
  baseline = null, finalEvidence = null, watchPhase = 'normal', timelineOriginMs = null,
} = {}) {
  if (!Array.isArray(gaps)) return [];
  const orderedSamples = [...samples].filter((sample) => finiteInteger(sample?.elapsed_ms))
    .sort((a, b) => a.elapsed_ms - b.elapsed_ms);
  return gaps.map((gap, index) => {
    const gapId = `${watchPhase}-gap-${index + 1}`;
    const validGap = gap && finiteInteger(gap.from_elapsed_ms) && finiteInteger(gap.to_elapsed_ms) &&
      finiteInteger(gap.gap_ms) && finiteInteger(gap.maximum_ms) && gap.to_elapsed_ms > gap.from_elapsed_ms &&
      gap.gap_ms === gap.to_elapsed_ms - gap.from_elapsed_ms && gap.gap_ms > gap.maximum_ms;
    const beforeSample = validGap ? orderedSamples.filter((sample) => sample.elapsed_ms <= gap.from_elapsed_ms).at(-1) : null;
    const afterSample = validGap ? orderedSamples.find((sample) => sample.elapsed_ms >= gap.to_elapsed_ms) || null : null;
    const beforeInventory = inventoryMap(beforeSample), afterInventory = inventoryMap(afterSample);
    const candidateEvents = validGap ? events.filter((event) => eventInGap(event, gap) && describesSurface(event.surface)) : [];
    const candidateMutationBatches = validGap ? mutationBatches.filter((batch) => eventInGap(batch, gap) &&
      Array.isArray(batch.records) && batch.records.length > 0) : [];
    const candidateAnimationEvents = validGap ? animationEvents.filter((event) => eventInGap(event, gap) && describesSurface(event.target)) : [];
    const inventoryStable = sameInventory(beforeInventory, afterInventory);
    // A relevant mutation or animation callback in the gap means a surface
    // could have been born, changed, or removed while no timely sample ran.
    // It remains a blocker even when the root event is later coalesced.
    const ambiguous = !validGap || !beforeSample || !afterSample || !beforeInventory || !afterInventory ||
      !inventoryStable || candidateEvents.length > 0 || candidateMutationBatches.length > 0 || candidateAnimationEvents.length > 0;
    const involved = candidateEvents[0]?.surface || candidateMutationBatches[0]?.records?.[0]?.target ||
      candidateAnimationEvents[0]?.target || [...(beforeInventory?.values?.() || [])][0]?.surface || null;
    const selector = candidateEvents.find((event) => event.declared_ambient && event.selector)?.selector ||
      [...(beforeInventory?.values?.() || [])].find((candidate) => candidate.selector)?.selector || null;
    return {
      gap_id: gapId,
      watch_phase: watchPhase,
      timeline_origin_ms: finiteInteger(timelineOriginMs) ? timelineOriginMs : null,
      gap: { ...gap },
      boundary_samples: { before: beforeSample || null, after: afterSample || null },
      independent_signals: {
        inventory_stable: inventoryStable,
        candidate_events: candidateEvents.map((event) => event.event_id || null),
        mutation_batches: candidateMutationBatches.map((batch) => batch.batch_id || null),
        animation_events: candidateAnimationEvents.map((event) => event.event_type || event.kind || null),
      },
      surface: involved,
      selector,
      surface_label: safeSurfaceLabel(involved, selector),
      ambiguous_candidate_lifecycle: ambiguous,
      continuous_recording_reconciliation: {
        status: generatedRecordingTimestamp(baseline) && generatedRecordingTimestamp(finalEvidence)
          ? 'recording-timestamp-window-pending-artifact-binding'
          : 'required-from-downstream-recording',
        before: generatedRecordingTimestamp(baseline) ? baseline : null,
        after: generatedRecordingTimestamp(finalEvidence) ? finalEvidence : null,
      },
    };
  });
}

export function bindAuthorizedConsentEvents(earlyPayload, records = []) {
  if (!earlyPayload || typeof earlyPayload !== 'object' || !Array.isArray(earlyPayload.events)) return earlyPayload;
  const candidates = records.map((record) => ({ disposition: record?.disposition, root: record?.root,
    evidence: record?.evidence_frames || record?.evidence })).filter(consentAuthorizationValid);
  for (const event of earlyPayload.events) {
    if (!event || event.declared_ambient === true || !event.surface) continue;
    const match = candidates.find((candidate) => {
      const root = candidate.root, surface = event.surface;
      if (root.id && surface.id) return root.id === surface.id;
      return root.tag === surface.tag && root.role === surface.role && root.class_name === surface.class_name && root.text === surface.text;
    });
    if (match) event.detail = { ...(event.detail || {}), authorized_consent: match };
  }
  return earlyPayload;
}

/** Shared source/build event shape: no event may become clean merely because
 * a callback arrived too late to retain its source evidence. */
export function sourceSurfaceWatchFailures(report) {
  const failures = [];
  if (!report || typeof report !== 'object' || !Array.isArray(report.events)) {
    return ['source surface watch report has no event ledger'];
  }
  if (!Number.isInteger(report.sample_interval_ms) || report.sample_interval_ms < 1 || report.sample_interval_ms > 66 ||
      !Array.isArray(report.animation_samples) || !Array.isArray(report.sample_gap_failures)) {
    failures.push('source surface watch lacks the required <=66ms uncapped sampler ledger');
  }
  if (Array.isArray(report.sample_gap_failures) && report.sample_gap_failures.length) {
    if (!Array.isArray(report.gap_reconciliations) || report.gap_reconciliations.length !== report.sample_gap_failures.length) {
      failures.push('source surface watch has timing gaps without one exact reconciliation record per gap');
    } else {
      for (const reconciliation of report.gap_reconciliations) {
        const label = reconciliation?.surface_label || safeSurfaceLabel(reconciliation?.surface, reconciliation?.selector);
        if (!reconciliation || typeof reconciliation.gap_id !== 'string' || !reconciliation.gap ||
            typeof reconciliation.ambiguous_candidate_lifecycle !== 'boolean' ||
            !reconciliation.independent_signals || !reconciliation.continuous_recording_reconciliation) {
          failures.push('source surface watch has a malformed timing-gap reconciliation record');
        } else if (reconciliation.ambiguous_candidate_lifecycle) {
          failures.push(`source surface timing-integrity gap ${reconciliation.gap_id} leaves ${label} ambiguous; declared selector ${reconciliation.selector || '(none)'}`);
        }
      }
    }
  }
  const eventIds = new Set();
  for (const event of report.events) {
    if (!event || typeof event !== 'object' || typeof event.event_id !== 'string' || !event.event_id ||
        eventIds.has(event.event_id) || !SOURCE_SURFACE_EVENT_KINDS.has(event.kind) ||
        !Number.isInteger(event.elapsed_ms) || event.elapsed_ms < 0 || typeof event.declared_ambient !== 'boolean' ||
        !(event.selector === null || (typeof event.selector === 'string' && event.selector.trim())) ||
        !(event.surface === null || (typeof event.surface === 'object' && !Array.isArray(event.surface))) ||
        !event.detail || typeof event.detail !== 'object' || Array.isArray(event.detail) ||
        !event.evidence || typeof event.evidence !== 'object' ||
        !generatedEvidence(event.evidence.before) || !generatedEvidence(event.evidence.callback) ||
        !generatedEvidence(event.evidence.after)) {
      failures.push(`source surface event ${event?.event_id || '(unnamed)'} lacks the exact event/evidence contract`);
      continue;
    }
    if (event.detail.authorized_consent && !consentAuthorizationValid(event.detail.authorized_consent)) {
      failures.push(`source surface event ${event.event_id} has an unsupported consent authorization`);
      continue;
    }
    if (event.declared_ambient && typeof event.selector !== 'string') {
      failures.push(`declared ambient source surface ${event.event_id} lacks its exact source selector`);
      continue;
    }
    if (!Array.isArray(event.detail.member_events) || !event.detail.member_events.length) {
      failures.push(`source surface event ${event.event_id} lacks its raw grouped-member ledger`);
      continue;
    }
    eventIds.add(event.event_id);
  }
  return failures;
}

// Playwright cannot remove an exposed page binding. Keep exactly one durable
// dispatcher per page and register/unregister individual watches beneath it;
// a long recursive source traversal must not leak one binding per route/state.
const PAGE_CALLBACK_REGISTRIES = new WeakMap();

async function registerCallback(page, watchId, options) {
  let registry = PAGE_CALLBACK_REGISTRIES.get(page);
  if (!registry) {
    registry = { binding_name: '__designDnaSourceSurfaceCallbackV1', watches: new Map() };
    await page.exposeBinding(registry.binding_name, async ({ page: eventPage }, payload) => {
      const watch = registry.watches.get(payload?.watch_id);
      if (!watch) return;
      const work = (async () => {
        let callbackEvidence = null;
        if (typeof watch.captureEvidence === 'function') {
          callbackEvidence = await watch.captureEvidence(
            `${watch.labelPrefix || 'autonomous-surface'}-${payload.event?.event_id || 'unknown'}-callback`,
            eventPage,
          );
        }
        watch.callbackEvents.push({ event_id: payload.event?.event_id || null, callback_evidence: callbackEvidence });
      })();
      watch.callbackPending.push(work);
      await work;
    });
    PAGE_CALLBACK_REGISTRIES.set(page, registry);
  }
  const existing = registry.watches.get(watchId);
  if (existing) return { registry, ...existing };
  const callbackEvents = [], callbackPending = [];
  registry.watches.set(watchId, { callbackEvents, callbackPending,
    captureEvidence: options.captureEvidence, labelPrefix: options.labelPrefix });
  return { registry, callbackEvents, callbackPending };
}

/** Install a minimal event-equivalent recorder before the next document runs.
 * The normal watch adopts it in the same page-evaluation turn after navigation,
 * so no first-visit or pre-state timer gap is silently treated as rest. */
const EARLY_SOURCE_WATCH_INIT = ({ id, selectors, callback, interval }) => {
    const registry = window.__designDnaEarlySourceSurfaceWatches || {};
    // page.addInitScript persists for the lifetime of a Playwright page. On a
    // later navigation, retired registrations run before the current one;
    // retire them synchronously before page code can execute so they cannot
    // leave duplicate observers or an orphaned early watch behind.
    for (const [staleId, stale] of Object.entries(registry)) {
      stale?.stop?.();
      delete registry[staleId];
    }
    const state = { id, selectors, callback, document_identity: `${id}-doc-${Math.round(performance.timeOrigin)}-${Math.round(performance.now())}`,
      document_url: location.href, started_at_ms: performance.now(), timeline_origin_ms: performance.now(), events: [], sequence: 0,
      identity_sequence: 0, sample_interval_ms: interval, animation_samples: [], sample_gap_failures: [], animation_events: [],
      mutation_batches: [], tail_mutations: [], observer: null, shadow_observers: [], shadow_roots: [], observed_roots: new WeakSet(),
      timer: null, listeners: [], seen: new Set(), surface_ids: new WeakMap(), emitted_keys: new Set(), restore_attach_shadow: null,
      document_ready: document.readyState !== 'loading', sample: null };
    state.timeline_origin_ms = state.started_at_ms;
    const roots = () => {
      // Declarative roots are discovered by the browser, not attachShadow.
      for (const captured of window.__designDnaCapturedShadowRoots || []) {
        observeShadowRoot(captured?.root);
        captured?.sampleMaterial?.('early');
      }
      return [document, ...state.shadow_roots];
    };
    const text = (element) => (element.getAttribute('aria-label') || element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 240);
    const composedFlags = (element) => {
      let cursor = element, ariaHidden = false, inert = false, disabled = false, depth = 0;
      while (cursor && depth++ < 80) {
        ariaHidden ||= cursor.getAttribute?.('aria-hidden') === 'true';
        inert ||= cursor.inert === true || cursor.hasAttribute?.('inert');
        disabled ||= cursor.getAttribute?.('aria-disabled') === 'true' || cursor.disabled === true;
        cursor = cursor.parentElement || cursor.getRootNode?.().host || null;
      }
      return { aria_hidden_ancestor: ariaHidden, inert_ancestor: inert, disabled_ancestor: disabled };
    };
    const identity = (element) => {
      let value = state.surface_ids.get(element);
      if (!value) { value = `${id}-surface-${++state.identity_sequence}`; state.surface_ids.set(element, value); }
      return value;
    };
    const visible = (element) => {
      if (!element.isConnected) return false;
      let cursor = element, depth = 0;
      while (cursor && depth++ < 80) {
        const style = getComputedStyle(cursor);
        if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse' || Number(style.opacity) <= 0) return false;
        cursor = cursor.parentElement || cursor.getRootNode?.().host || null;
      }
      const box = element.getBoundingClientRect();
      return box.width > 1 && box.height > 1;
    };
    // Server/framework construction can momentarily attach unstyled dialog
    // markup before its hiding CSS or hydration state exists. It is not an
    // observed visitor-facing appearance. Once DOMContentLoaded fires, keep
    // ordinary immediate mutation coverage for real visible transients.
    const observable = (element) => state.document_ready && visible(element);
    const detachedPotentiallyVisible = (element) => {
      if (!(element instanceof Element) || element.isConnected) return false;
      const inline = String(element?.getAttribute?.('style') || '');
      if (/display\s*:\s*none(?:\s*!important)?\s*(?:;|$)|visibility\s*:\s*(?:hidden|collapse)(?:\s*!important)?\s*(?:;|$)|opacity\s*:\s*0(?:\.0+)?(?:\s*!important)?\s*(?:;|$)/i.test(inline)) return false;
      return surfaceKind(element, true).geometric;
    };
    const lexicalSurfaceSignal = (element) => {
      if (element.matches('[role="dialog"],dialog,[aria-modal="true"],[data-ff-el="modal"]')) return true;
      const names = [element.id || '', ...element.classList].map((value) => String(value).toLowerCase());
      return names.some((value) => {
        const surface = /(?:^|[-_])(modal|overlay|interstitial|survey|gate)(?:$|[-_])/.test(value);
        const activator = /(?:^|[-_])(opener|trigger|toggle|button|link|launcher|thumbnail)(?:$|[-_])/.test(value);
        return surface && !activator;
      });
    };
    const surfaceKind = (element, detached = false) => {
      if (!(element instanceof Element)) return { relevant: false, lexical: false, geometric: false };
      const lexical = lexicalSurfaceSignal(element);
      if (detached || !element.isConnected) {
        const inline = String(element.getAttribute('style') || '');
        const geometric = /position\s*:\s*(?:fixed|sticky)/i.test(inline) && /(?:inset|width|height)\s*:/i.test(inline);
        return { relevant: lexical || geometric, lexical, geometric };
      }
      const style = getComputedStyle(element), box = element.getBoundingClientRect();
      const geometric = style.position === 'fixed' && box.width >= innerWidth * .8 && box.height >= innerHeight * .65 && Number(style.zIndex || 0) > 0;
      return { relevant: lexical || geometric, lexical, geometric };
    };
    const declaredSelector = (element) => selectors.find((selector) => { try { return element.matches(selector) || Boolean(element.closest(selector)); } catch { return false; } }) || null;
    const owningSurface = (element) => {
      let cursor = element, fallback = null, depth = 0;
      while (cursor && depth++ < 80) {
        const kind = surfaceKind(cursor, !cursor.isConnected);
        if (kind.relevant) {
          if (cursor.matches?.('[role="dialog"],dialog,[aria-modal="true"],[data-ff-el="modal"]')) return cursor;
          fallback ||= cursor;
        }
        cursor = cursor.parentElement || cursor.getRootNode?.().host || null;
      }
      return fallback || element;
    };
    const describe = (element, kind = surfaceKind(element), detached = false) => {
      const box = !detached && element.isConnected ? element.getBoundingClientRect() : null;
      return { tag: element.tagName.toLowerCase(), role: element.getAttribute('role') || null,
        aria_modal: element.getAttribute('aria-modal'), aria_hidden: element.getAttribute('aria-hidden'),
        aria_disabled: element.getAttribute('aria-disabled'), data_ff_el: element.getAttribute('data-ff-el'), id: element.id || null,
        class_name: String(element.className || '').slice(0, 240), text: text(element), connected: element.isConnected,
        lexical_surface_signal: kind.lexical, geometric_surface_signal: kind.geometric,
        rect: box ? { left: Math.round(box.left), top: Math.round(box.top), width: Math.round(box.width), height: Math.round(box.height) } : null,
        ...composedFlags(element) };
    };
    const emit = (kind, element, detail = {}, detached = false) => {
      const owner = owningSurface(element), ownerDetached = detached || !owner.isConnected;
      const ownerKind = surfaceKind(owner, ownerDetached);
      if (!ownerKind.relevant) return null;
      const groupKey = `${kind}|${identity(owner)}|${detail.mutation_batch || detail.event_type || detail.animation_name || 'lifecycle'}`;
      const member = { member_id: identity(element), ...describe(element, surfaceKind(element, detached), detached) };
      if (state.emitted_keys.has(groupKey)) {
        const existing = state.events.find((event) => event.detail?.group_key === groupKey);
        if (existing) existing.detail.member_events.push(member);
        return existing || null;
      }
      state.emitted_keys.add(groupKey);
      const selector = declaredSelector(owner);
      const event = { event_id: `${id}-e${++state.sequence}`, kind, elapsed_ms: Math.round(performance.now() - state.timeline_origin_ms),
        declared_ambient: Boolean(selector), selector, surface: describe(owner, ownerKind, ownerDetached),
        detail: { ...detail, group_key: groupKey, member_events: [member] } };
      state.events.push(event); Promise.resolve(window[callback]?.({ watch_id: id, event })).catch(() => {});
      return event;
    };
    const descendants = (node) => node instanceof Element ? [node, ...node.querySelectorAll('*')] : [];
    const allAnimations = () => [...new Set(roots().flatMap((root) => typeof root.getAnimations === 'function' ? root.getAnimations({ subtree: true }) : []))];
    const sample = (reason) => {
      const elapsed = Math.round(performance.now() - state.timeline_origin_ms), prior = state.animation_samples.at(-1);
      if (prior && elapsed - prior.elapsed_ms > interval * 2) state.sample_gap_failures.push({ from_elapsed_ms: prior.elapsed_ms, to_elapsed_ms: elapsed, gap_ms: elapsed - prior.elapsed_ms, maximum_ms: interval * 2, reason, watch_phase: 'early' });
      const animations = allAnimations(), active = animations.filter((animation) => animation.playState === 'running').length;
      const candidates = roots().flatMap((root) => [...root.querySelectorAll('*')]).filter((element) => surfaceKind(element).relevant && observable(element));
      const candidateInventory = [...new Map(candidates.map((element) => {
        const owner = owningSurface(element);
        return [identity(owner), { owner_id: identity(owner), selector: declaredSelector(owner), surface: describe(owner, surfaceKind(owner), !owner.isConnected) }];
      })).values()];
      state.animation_samples.push({ elapsed_ms: elapsed, active_animations: active, reason, candidate_inventory: candidateInventory });
      for (const element of candidates) {
        const key = identity(owningSurface(element));
        if (state.seen.has(key)) continue;
        state.seen.add(key); emit('autonomous-surface-appeared', element, { reason });
      }
      for (const animation of animations) {
        const target = animation.effect?.target;
        if (target instanceof Element && animation.playState === 'running' && observable(owningSurface(target))) emit('surface-waapi-active', target, { animation_name: animation.animationName || null, play_state: animation.playState });
      }
    };
    state.sample = sample;
    const handle = (records) => {
      const batch = { batch_id: `${id}-m${state.mutation_batches.length + 1}`, elapsed_ms: Math.round(performance.now() - state.timeline_origin_ms), records: [] };
      for (const record of records) {
        const row = { type: record.type, attribute: record.attributeName || null, old_value: record.oldValue || null, added: [], removed: [], target: null };
        if (record.target instanceof Element) {
          const owner = owningSurface(record.target), kind = surfaceKind(owner, !owner.isConnected);
          if ((kind.relevant && observable(owner)) || state.seen.has(identity(owner))) {
            row.target = describe(owner, kind, !owner.isConnected);
            emit('surface-attribute-mutation', record.target, { attribute: record.attributeName || null, old_value: record.oldValue || null, mutation_batch: batch.batch_id }, !record.target.isConnected);
          }
        }
        for (const node of record.addedNodes || []) for (const element of descendants(node)) {
          const owner = owningSurface(element), kind = surfaceKind(owner, !owner.isConnected);
          if (kind.relevant && (observable(owner) || detachedPotentiallyVisible(owner))) { row.added.push(describe(element, surfaceKind(element, !element.isConnected), !element.isConnected)); emit('surface-node-added', element, { mutation_batch: batch.batch_id }, !element.isConnected); }
        }
        for (const node of record.removedNodes || []) for (const element of descendants(node)) {
          const owner = owningSurface(element), kind = surfaceKind(owner, true);
          if (state.seen.has(identity(owner)) || detachedPotentiallyVisible(owner)) { row.removed.push(describe(element, surfaceKind(element, true), true)); emit('surface-node-removed', element, { mutation_batch: batch.batch_id }, true); }
        }
        if (row.target || row.added.length || row.removed.length) batch.records.push(row);
      }
      state.mutation_batches.push(batch); state.tail_mutations.push({ elapsed_ms: batch.elapsed_ms, batch_id: batch.batch_id, records: batch.records.length }); queueMicrotask(() => sample('mutation'));
    };
    const observeShadowRoot = (root) => {
      if (!root || root.nodeType !== 11 || state.observed_roots.has(root)) return;
      state.observed_roots.add(root);
      state.shadow_roots.push(root);
      const observer = new MutationObserver(handle);
      observer.observe(root, { subtree: true, childList: true, attributes: true, attributeOldValue: true, attributeFilter: ['class','style','hidden','aria-hidden','aria-modal','aria-disabled','inert','open'] });
      state.shadow_observers.push(observer);
    };
    const priorAttachShadow = Element.prototype.attachShadow;
    const watchedAttachShadow = function(init) { const root = priorAttachShadow.call(this, init); observeShadowRoot(root); return root; };
    Object.defineProperty(Element.prototype, 'attachShadow', { configurable: true, writable: true, value: watchedAttachShadow });
    state.restore_attach_shadow = () => { if (Element.prototype.attachShadow === watchedAttachShadow) Object.defineProperty(Element.prototype, 'attachShadow', { configurable: true, writable: true, value: priorAttachShadow }); };
    state.stop = () => {
      if (state.stopped) return;
      state.stopped = true;
      state.observer?.disconnect(); clearInterval(state.timer);
      for (const observer of state.shadow_observers || []) observer.disconnect();
      for (const entry of state.listeners || []) document.removeEventListener(entry.type, entry.listener, true);
      state.restore_attach_shadow?.();
    };
    state.observer = new MutationObserver(handle); state.observer.observe(document, { subtree: true, childList: true, attributes: true, attributeOldValue: true, attributeFilter: ['class','style','hidden','aria-hidden','aria-modal','aria-disabled','inert','open'] });
    for (const type of ['animationstart','animationend','animationcancel','transitionrun','transitionstart','transitionend','transitioncancel']) {
      const listener = (event) => { const target = event.target instanceof Element ? event.target : null, pseudo = event.pseudoElement || null; if (!target) return; const owner = owningSurface(target), kind = surfaceKind(owner, !owner.isConnected); if ((!kind.relevant && !pseudo) || (!observable(owner) && !state.seen.has(identity(owner)))) return; const detail = { event_type: type, animation_name: event.animationName || null, property_name: event.propertyName || null, pseudo_element: pseudo }; state.animation_events.push({ elapsed_ms: Math.round(performance.now() - state.timeline_origin_ms), ...detail, target: describe(owner, kind, !owner.isConnected) }); emit(pseudo ? 'surface-pseudo-animation-event' : 'surface-css-animation-event', target, detail, !target.isConnected); };
      document.addEventListener(type, listener, true); state.listeners.push({ type, listener });
    }
    if (!state.document_ready) document.addEventListener('DOMContentLoaded', () => { state.document_ready = true; if (!state.stopped) sample('dom-content-loaded'); }, { once: true });
    state.timer = setInterval(() => sample('timer'), interval); sample('init'); registry[id] = state; window.__designDnaEarlySourceSurfaceWatches = registry;
};

async function installOneNavigationEarlyScript(page, source) {
  if (typeof page.context !== 'function') {
    const error = new Error('source surface watch needs a Chromium CDP page context for one-navigation early observation.');
    error.code = 'source-surface-watch-cdp-unavailable';
    throw error;
  }
  const context = page.context();
  if (!context || typeof context.newCDPSession !== 'function') {
    const error = new Error('source surface watch cannot install a one-navigation early observer without CDP support.');
    error.code = 'source-surface-watch-cdp-unavailable';
    throw error;
  }
  const session = await context.newCDPSession(page);
  try {
    await session.send('Page.enable');
    const result = await session.send('Page.addScriptToEvaluateOnNewDocument', { source });
    if (!result?.identifier) {
      const error = new Error('CDP did not return an early-observer registration identifier.');
      error.code = 'source-surface-watch-cdp-registration';
      throw error;
    }
    return { session, identifier: result.identifier, retired: false };
  } catch (error) {
    await session.detach?.().catch(() => {});
    throw error;
  }
}

async function retireOneNavigationEarlyScript(registration) {
  if (!registration || registration.retired) return;
  registration.retired = true;
  try { await registration.session?.send('Page.removeScriptToEvaluateOnNewDocument', { identifier: registration.identifier }); }
  finally { await registration.session?.detach?.().catch(() => {}); }
}

export async function armEarlySourceSurfaceWatch(page, options = {}) {
  const ambientSelectors = normalizeSelectors(options.ambientSelectors);
  const watchId = `source-early-watch-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  const callbacks = await registerCallback(page, watchId, options);
  const initSource = `(${EARLY_SOURCE_WATCH_INIT.toString()})(${JSON.stringify({
    id: watchId, selectors: ambientSelectors, callback: callbacks.registry.binding_name,
    interval: SOURCE_SURFACE_SAMPLE_INTERVAL_MS,
  })});`;
  const earlyScriptRegistration = await installOneNavigationEarlyScript(page, initSource);
  const closedRootInventory = { pending: Promise.resolve(), error: null, listener: null };
  closedRootInventory.listener = () => {
    closedRootInventory.pending = closedRootInventory.pending.then(async () => {
      try { await discoverUnaddressableClosedRoots(page); }
      catch (error) { closedRootInventory.error ||= error; }
    });
  };
  page.on('domcontentloaded', closedRootInventory.listener);
  return { id: watchId, page, ambientSelectors, baseline: options.baseline || null,
    callbackEvents: callbacks.callbackEvents, callbackPending: callbacks.callbackPending,
    callbackRegistry: callbacks.registry, captureEvidence: options.captureEvidence, early: true, earlyScriptRegistration, closedRootInventory };
}

export async function adoptEarlySourceSurfaceWatch(page, earlyWatch, options = {}) {
  // The initial and normal recorders are transferred in one page-evaluation
  // turn inside startSourceSurfaceWatch. Page JS cannot run between the early
  // disconnect and normal observer install, so timestamp lineage has no
  // hidden handoff interval or reset.
  let watch = null;
  try {
    await earlyWatch.closedRootInventory?.pending;
    if (earlyWatch.closedRootInventory?.error) throw earlyWatch.closedRootInventory.error;
    watch = await startSourceSurfaceWatch(page, {
      ...options, watchId: earlyWatch.id, adoptEarlyId: earlyWatch.id, earlyBaseline: earlyWatch.baseline,
      captureEvidence: options.captureEvidence || earlyWatch.captureEvidence,
    });
    bindAuthorizedConsentEvents(watch.earlyPayload, options.authorizedConsent || []);
    await Promise.allSettled(earlyWatch.callbackPending || []);
    return watch;
  } finally {
    if (earlyWatch.closedRootInventory?.listener) page.off('domcontentloaded', earlyWatch.closedRootInventory.listener);
    // CDP registration is deliberately one-navigation only. The current
    // document already adopted its state; retaining it would let a retired
    // early recorder reappear on a later route/state navigation.
    await retireOneNavigationEarlyScript(earlyWatch.earlyScriptRegistration);
    if (!watch) await stopSourceSurfaceWatch(earlyWatch);
  }
}

export async function startSourceSurfaceWatch(page, options = {}) {
  // Retain author-created roots before an intro/state dwell, not only when a
  // final census runs after a transient surface has already disappeared.
  await discoverUnaddressableClosedRoots(page);
  const ambientSelectors = normalizeSelectors(options.ambientSelectors);
  const watchId = options.watchId || `source-surface-watch-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  const callbacks = await registerCallback(page, watchId, options);
  const adoption = await page.evaluate(({ id, selectors, callback, adoptEarlyId }) => {
    const prior = window.__designDnaSourceSurfaceWatches || {};
    if (prior[id]) throw new Error(`duplicate source surface watch ${id}`);
    const earlyRegistry = window.__designDnaEarlySourceSurfaceWatches || {};
    const earlyState = adoptEarlyId ? earlyRegistry[adoptEarlyId] : null;
    let earlyPayload = null;
    if (earlyState) {
      // This sample and teardown execute synchronously in the same evaluation
      // as normal-watch installation below. Nothing in the page can mutate
      // between them, and the handoff is represented explicitly in the ledger.
      earlyState.sample?.('normal-watch-handoff');
      earlyPayload = { id: earlyState.id, document_identity: earlyState.document_identity, document_url: earlyState.document_url,
        elapsed_ms: Math.round(performance.now() - earlyState.timeline_origin_ms),
        timeline_origin_ms: Math.round(earlyState.timeline_origin_ms), handoff_elapsed_ms: Math.round(performance.now() - earlyState.timeline_origin_ms),
        handoff: { from: 'early', to: 'normal', gap_ms: 0, atomic: true },
        sample_interval_ms: earlyState.sample_interval_ms, animation_samples: earlyState.animation_samples.slice(),
        sample_gap_failures: earlyState.sample_gap_failures.slice(), animation_events: earlyState.animation_events.slice(),
        mutation_batches: earlyState.mutation_batches.slice(), tail_mutations: earlyState.tail_mutations.slice(), events: earlyState.events.slice() };
      earlyState.stop?.();
      delete earlyRegistry[adoptEarlyId]; window.__designDnaEarlySourceSurfaceWatches = earlyRegistry;
    }
    const startedAt = performance.now();
    const timelineOrigin = Number.isFinite(earlyPayload?.timeline_origin_ms) ? earlyPayload.timeline_origin_ms : startedAt;
    const state = { id, selectors, callback,
      document_identity: earlyState?.document_identity || `${id}-doc-${Math.round(performance.timeOrigin)}-${Math.round(startedAt)}`,
      document_url: earlyState?.document_url || location.href,
      started_at_ms: startedAt, timeline_origin_ms: timelineOrigin,
      events: [], seen: earlyState?.seen || new Set(), surface_ids: earlyState?.surface_ids || new WeakMap(),
      sequence: Number.isInteger(earlyState?.sequence) ? earlyState.sequence : 0,
      identity_sequence: Number.isInteger(earlyState?.identity_sequence) ? earlyState.identity_sequence : 0,
      mutation_batch_sequence: Array.isArray(earlyState?.mutation_batches) ? earlyState.mutation_batches.length : 0,
      mutation_count: 0, timer_samples: 0,
      sample_interval_ms: 50, animation_samples: [], sample_gap_failures: [], animation_events: [], mutation_batches: [], tail_mutations: [],
      observer: null, shadow_observers: [], observed_roots: new WeakSet(), timer: null, listeners: [], attach_shadow_restore: null, emitted_keys: new Set() };
    const roots = () => {
      const all = [document];
      for (let index = 0; index < all.length; index += 1) {
        all[index].querySelectorAll('*').forEach((element) => { if (element.shadowRoot) all.push(element.shadowRoot); });
        if (all[index].nodeType === 9) {
          for (const captured of all[index].defaultView.__designDnaCapturedShadowRoots || []) {
            if (captured?.root && !all.includes(captured.root)) all.push(captured.root);
            captured?.sampleMaterial?.('normal');
          }
        }
      }
      return all;
    };
    const visible = (element) => {
      if (!element.isConnected) return false;
      let cursor = element, depth = 0;
      while (cursor && depth++ < 80) {
        const style = getComputedStyle(cursor);
        if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse' || Number(style.opacity) <= 0) return false;
        cursor = cursor.parentElement || cursor.getRootNode?.().host || null;
      }
      const box = element.getBoundingClientRect();
      return box.width > 1 && box.height > 1;
    };
    const detachedPotentiallyVisible = (element) => {
      if (!(element instanceof Element) || element.isConnected) return false;
      const inline = String(element?.getAttribute?.('style') || '');
      if (/display\s*:\s*none(?:\s*!important)?\s*(?:;|$)|visibility\s*:\s*(?:hidden|collapse)(?:\s*!important)?\s*(?:;|$)|opacity\s*:\s*0(?:\.0+)?(?:\s*!important)?\s*(?:;|$)/i.test(inline)) return false;
      return surfaceKind(element, true).geometric;
    };
    const lexicalSurfaceSignal = (element) => {
      if (element.matches('[role="dialog"],dialog,[aria-modal="true"],[data-ff-el="modal"]')) return true;
      const names = [element.id || '', ...element.classList].map((value) => String(value).toLowerCase());
      return names.some((value) => {
        const surface = /(?:^|[-_])(modal|overlay|interstitial|survey|gate)(?:$|[-_])/.test(value);
        const activator = /(?:^|[-_])(opener|trigger|toggle|button|link|launcher|thumbnail)(?:$|[-_])/.test(value);
        return surface && !activator;
      });
    };
    const text = (element) => (element.getAttribute('aria-label') || element.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 240);
    const composedFlags = (element) => {
      let cursor = element, ariaHidden = false, inert = false, disabled = false, depth = 0;
      while (cursor && depth++ < 80) {
        ariaHidden ||= cursor.getAttribute?.('aria-hidden') === 'true';
        inert ||= cursor.inert === true || cursor.hasAttribute?.('inert');
        disabled ||= cursor.getAttribute?.('aria-disabled') === 'true' || cursor.disabled === true;
        cursor = cursor.parentElement || cursor.getRootNode?.().host || null;
      }
      return { aria_hidden_ancestor: ariaHidden, inert_ancestor: inert, disabled_ancestor: disabled };
    };
    const identity = (element) => {
      let value = state.surface_ids.get(element);
      if (!value) {
        value = `${state.id}-surface-${++state.identity_sequence}`;
        state.surface_ids.set(element, value);
      }
      return value;
    };
    const surfaceKind = (element, disconnected = false) => {
      if (!(element instanceof Element)) return { relevant: false, lexical: false, geometric: false };
      const lexical = lexicalSurfaceSignal(element);
      if (disconnected || !element.isConnected) {
        const inline = String(element.getAttribute('style') || '');
        const inlineCover = /position\s*:\s*(?:fixed|sticky)/i.test(inline) && /(?:inset|width|height)\s*:/i.test(inline);
        return { relevant: lexical || inlineCover, lexical, geometric: inlineCover };
      }
      const style = getComputedStyle(element), box = element.getBoundingClientRect();
      const geometric = style.position === 'fixed' && box.width >= innerWidth * .8 && box.height >= innerHeight * .65 && Number(style.zIndex || 0) > 0;
      return { relevant: lexical || geometric, lexical, geometric };
    };
    const declaredSelector = (element) => state.selectors.find((selector) => {
      try { return element.matches(selector) || Boolean(element.closest(selector)); } catch { return false; }
    }) || null;
    const describe = (element, kind = surfaceKind(element), disconnected = false) => {
      const box = !disconnected && element.isConnected ? element.getBoundingClientRect() : null;
      return { tag: element.tagName.toLowerCase(), role: element.getAttribute('role') || null,
        aria_modal: element.getAttribute('aria-modal'), aria_hidden: element.getAttribute('aria-hidden'),
        aria_disabled: element.getAttribute('aria-disabled'), data_ff_el: element.getAttribute('data-ff-el'), id: element.id || null,
        class_name: String(element.className || '').slice(0, 240), text: text(element), connected: element.isConnected,
        lexical_surface_signal: kind.lexical, geometric_surface_signal: kind.geometric,
        rect: box ? { left: Math.round(box.left), top: Math.round(box.top), width: Math.round(box.width), height: Math.round(box.height) } : null,
        ...composedFlags(element) };
    };
    const owningSurface = (element) => {
      let cursor = element, fallback = null, depth = 0;
      while (cursor && depth++ < 80) {
        const kind = surfaceKind(cursor, !cursor.isConnected);
        if (kind.relevant) {
          if (cursor.matches?.('[role="dialog"],dialog,[aria-modal="true"],[data-ff-el="modal"]')) return cursor;
          fallback ||= cursor;
        }
        const root = cursor.getRootNode?.();
        cursor = cursor.parentElement || root?.host || null;
      }
      return fallback || element;
    };
    const emit = (kind, element, detail = {}, disconnected = false) => {
      const owner = owningSurface(element);
      const surfaceKindValue = surfaceKind(owner, disconnected || !owner.isConnected);
      if (!surfaceKindValue.relevant) return null;
      const groupKey = `${kind}|${identity(owner)}|${detail.mutation_batch || detail.event_type || detail.animation_name || 'lifecycle'}`;
      const member = { member_id: identity(element), ...describe(element, surfaceKind(element, disconnected), disconnected) };
      if (state.emitted_keys.has(groupKey)) {
        const existing = state.events.find((event) => event.detail?.group_key === groupKey);
        if (existing) existing.detail.member_events.push(member);
        return existing || null;
      }
      state.emitted_keys.add(groupKey);
      const selector = declaredSelector(owner);
      const event = { event_id: `${state.id}-e${++state.sequence}`, kind, elapsed_ms: Math.round(performance.now() - state.timeline_origin_ms),
        declared_ambient: Boolean(selector), selector,
        surface: describe(owner, surfaceKindValue, disconnected || !owner.isConnected),
        detail: { ...detail, group_key: groupKey, member_events: [member] } };
      state.events.push(event);
      Promise.resolve(window[state.callback]?.({ watch_id: state.id, event })).catch(() => {});
      return event;
    };
    const collectDescendants = (node) => {
      if (!(node instanceof Element)) return [];
      return [node, ...node.querySelectorAll('*')];
    };
    const sample = (reason) => {
      state.timer_samples += 1;
      const elapsed = Math.round(performance.now() - state.timeline_origin_ms);
      const priorSample = state.animation_samples.at(-1);
      if (priorSample && elapsed - priorSample.elapsed_ms > state.sample_interval_ms * 2) {
        state.sample_gap_failures.push({ from_elapsed_ms: priorSample.elapsed_ms, to_elapsed_ms: elapsed,
          gap_ms: elapsed - priorSample.elapsed_ms, maximum_ms: state.sample_interval_ms * 2, reason, watch_phase: 'normal' });
      }
      const activeAnimations = typeof document.getAnimations === 'function'
        ? document.getAnimations().filter((animation) => animation.playState === 'running').length
        : 0;
      observeShadowRoots();
      const candidates = roots().flatMap((root) => [...root.querySelectorAll('*')]).filter((element) => surfaceKind(element).relevant && visible(element));
      const candidateInventory = [...new Map(candidates.map((element) => {
        const owner = owningSurface(element);
        return [identity(owner), { owner_id: identity(owner), selector: declaredSelector(owner), surface: describe(owner, surfaceKind(owner), !owner.isConnected) }];
      })).values()];
      state.animation_samples.push({ elapsed_ms: elapsed, active_animations: activeAnimations, reason, candidate_inventory: candidateInventory });
      for (const element of candidates) {
        const key = identity(owningSurface(element));
        if (state.seen.has(key)) continue;
        state.seen.add(key);
        emit('autonomous-surface-appeared', element, { reason });
      }
      const animations = typeof document.getAnimations === 'function' ? document.getAnimations() : [];
      for (const animation of animations) {
        const target = animation.effect?.target;
        if (target instanceof Element && animation.playState === 'running' && visible(owningSurface(target))) emit('surface-waapi-active', target, {
          animation_name: animation.animationName || null, play_state: animation.playState,
        });
      }
    };
    state.sample = sample;
    const handleMutations = (records) => {
      state.mutation_count += records.length;
      const batch = { batch_id: `${state.id}-m${++state.mutation_batch_sequence}`,
        elapsed_ms: Math.round(performance.now() - state.timeline_origin_ms), records: [] };
      for (const record of records) {
        const entry = { type: record.type, attribute: record.attributeName || null, old_value: record.oldValue || null,
          added: [], removed: [], target: null };
        if (record.target instanceof Element) {
          const owner = owningSurface(record.target), kind = surfaceKind(owner, !owner.isConnected);
          if ((kind.relevant && visible(owner)) || state.seen.has(identity(owner))) {
            entry.target = describe(owner, kind, !owner.isConnected);
            emit('surface-attribute-mutation', record.target, { attribute: record.attributeName || null, old_value: record.oldValue || null }, !record.target.isConnected);
          }
        }
        for (const node of record.addedNodes || []) for (const element of collectDescendants(node)) {
          const owner = owningSurface(element), kind = surfaceKind(owner, !element.isConnected);
          if (!kind.relevant || (!visible(owner) && !detachedPotentiallyVisible(owner))) continue;
          entry.added.push(describe(element, surfaceKind(element, !element.isConnected), !element.isConnected));
          emit('surface-node-added', element, { mutation_batch: batch.batch_id }, !element.isConnected);
        }
        for (const node of record.removedNodes || []) for (const element of collectDescendants(node)) {
          const owner = owningSurface(element), kind = surfaceKind(owner, true);
          if (!state.seen.has(identity(owner)) && !detachedPotentiallyVisible(owner)) continue;
          entry.removed.push(describe(element, surfaceKind(element, true), true));
          emit('surface-node-removed', element, { mutation_batch: batch.batch_id }, true);
        }
        if (entry.target || entry.added.length || entry.removed.length) batch.records.push(entry);
      }
      state.mutation_batches.push(batch);
      state.tail_mutations.push({ elapsed_ms: batch.elapsed_ms, batch_id: batch.batch_id, records: batch.records.length });
      queueMicrotask(() => sample('mutation'));
    };
    state.observer = new MutationObserver(handleMutations);
    state.observer.observe(document.documentElement, { subtree: true, childList: true, attributes: true,
      attributeOldValue: true, attributeFilter: ['class','style','hidden','aria-hidden','aria-modal','aria-disabled','inert','open'] });
    const attachAnimationListeners = (root) => forEachAnimationEvent(root);
    const observeOneShadowRoot = (root) => {
      if (!root || root.nodeType !== 11 || state.observed_roots.has(root)) return;
      state.observed_roots.add(root);
      const observer = new MutationObserver(handleMutations);
      observer.observe(root, { subtree: true, childList: true, attributes: true,
        attributeOldValue: true, attributeFilter: ['class','style','hidden','aria-hidden','aria-modal','aria-disabled','inert','open'] });
      state.shadow_observers.push(observer); attachAnimationListeners(root);
    };
    const observeShadowRoots = () => { for (const root of roots()) observeOneShadowRoot(root); };
    const forEachAnimationEvent = (root) => {
    for (const type of ['animationstart','animationend','animationcancel','transitionrun','transitionstart','transitionend','transitioncancel']) {
      const listener = (event) => {
        const target = event.target instanceof Element ? event.target : null;
        const pseudo = event.pseudoElement || null;
        if (!target) return;
        const owner = owningSurface(target), kind = surfaceKind(owner, !owner.isConnected);
        if ((!kind.relevant && !pseudo) || (!visible(owner) && !state.seen.has(identity(owner)))) return;
        const record = { event_type: type, animation_name: event.animationName || null,
          property_name: event.propertyName || null, pseudo_element: pseudo };
        state.animation_events.push({ elapsed_ms: Math.round(performance.now() - state.timeline_origin_ms), ...record,
          target: describe(owner, kind, !owner.isConnected) });
        emit(pseudo ? 'surface-pseudo-animation-event' : 'surface-css-animation-event', target, record, !target.isConnected);
      };
      root.addEventListener(type, listener, true); state.listeners.push({ root, type, listener });
    }
    };
    attachAnimationListeners(document);
    observeShadowRoots();
    const priorAttachShadow = Element.prototype.attachShadow;
    const watchedAttachShadow = function(init) {
      const root = priorAttachShadow.call(this, init);
      observeOneShadowRoot(root);
      return root;
    };
    Object.defineProperty(Element.prototype, 'attachShadow', { configurable: true, writable: true, value: watchedAttachShadow });
    state.attach_shadow_restore = () => {
      if (Element.prototype.attachShadow === watchedAttachShadow) {
        Object.defineProperty(Element.prototype, 'attachShadow', { configurable: true, writable: true, value: priorAttachShadow });
      }
    };
    state.timer = setInterval(() => sample('timer'), state.sample_interval_ms);
    sample('initial');
    prior[id] = state; window.__designDnaSourceSurfaceWatches = prior;
    return { earlyPayload, document_identity: state.document_identity, document_url: state.document_url };
  }, { id: watchId, selectors: ambientSelectors, callback: callbacks.registry.binding_name, adoptEarlyId: options.adoptEarlyId || null });
  const navigationEvents = [];
  const navigationListener = (frame) => {
    if (typeof page.mainFrame === 'function' && frame !== page.mainFrame()) return;
    navigationEvents.push({ url: frame.url(), observed_at_ms: Date.now() });
  };
  if (typeof page.on === 'function') page.on('framenavigated', navigationListener);
  return { id: watchId, page, ambientSelectors, baseline: options.baseline || null,
    callbackEvents: callbacks.callbackEvents, callbackPending: callbacks.callbackPending,
    callbackRegistry: callbacks.registry, captureEvidence: options.captureEvidence,
    earlyPayload: adoption?.earlyPayload || options.earlyPayload || null, earlyBaseline: options.earlyBaseline || null,
    documentIdentity: adoption?.document_identity || null, documentUrl: adoption?.document_url || null,
    lifecyclePhase: options.lifecyclePhase || options.labelPrefix || 'source-surface-watch',
    navigationEvents, navigationListener };
}

export async function drainSourceSurfaceWatch(watch, options = {}) {
  await Promise.allSettled(watch.callbackPending || []);
  const payload = await watch.page.evaluate(({ id, expectedDocumentIdentity, expectedDocumentUrl }) => {
    const state = window.__designDnaSourceSurfaceWatches?.[id];
    if (!state || (expectedDocumentIdentity && state.document_identity !== expectedDocumentIdentity)) {
      const navigation = performance.getEntriesByType?.('navigation')?.at(-1) || null;
      return { capture_integrity_failure: true, watch_id: id, expected_document_identity: expectedDocumentIdentity || null,
        current_document_identity: state?.document_identity || null, expected_document_url: expectedDocumentUrl || state?.document_url || null,
        current_document_url: location.href, navigation_type: navigation?.type || null };
    }
    // A final full surface pass closes the race between a late timer mutation
    // and the producer's completion claim.
    state.sample?.('final-target-state-diff');
    const events = state.events.splice(0, state.events.length);
    return { id, elapsed_ms: Math.round(performance.now() - state.timeline_origin_ms), watch_elapsed_ms: Math.round(performance.now() - state.started_at_ms),
      timeline_origin_ms: Math.round(state.timeline_origin_ms), mutation_count: state.mutation_count,
      sample_interval_ms: state.sample_interval_ms, timer_samples: state.timer_samples, animation_samples: state.animation_samples.slice(), sample_gap_failures: state.sample_gap_failures.slice(),
      animation_events: state.animation_events.slice(), mutation_batches: state.mutation_batches.slice(),
      tail_mutations: state.tail_mutations.slice(), events };
  }, { id: watch.id, expectedDocumentIdentity: watch.documentIdentity || null, expectedDocumentUrl: watch.documentUrl || null });
  if (payload?.capture_integrity_failure) {
    const latestNavigation = Array.isArray(watch.navigationEvents) ? watch.navigationEvents.at(-1) || null : null;
    const error = new Error(`${watch.lifecyclePhase || 'source-surface-watch'}: source surface watch ${watch.id} lost its document before drain; expected ${watch.documentUrl || payload.expected_document_url || '(unknown URL)'}, current ${payload.current_document_url || latestNavigation?.url || '(unknown URL)'}. An intentional navigation must drain/stop the current watch and arm an early successor before the new document runs.`);
    error.code = 'source-surface-watch-document-replaced';
    error.capture_integrity = { ...payload, lifecycle_phase: watch.lifecyclePhase || null,
      expected_document_url: watch.documentUrl || payload.expected_document_url || null,
      observed_navigation: latestNavigation };
    error.surface_watch = null;
    throw error;
  }
  await Promise.allSettled(watch.callbackPending || []);
  const capture = options.captureEvidence || watch.captureEvidence;
  const finalEvidence = typeof capture === 'function'
    ? await capture(`${options.labelPrefix || 'autonomous-surface'}-final-target-state`, watch.page)
    : null;
  const callbackEvidence = new Map((watch.callbackEvents || []).map((entry) => [entry.event_id, entry.callback_evidence]));
  const early = watch.earlyPayload && typeof watch.earlyPayload === 'object' ? watch.earlyPayload : null;
  const rawEvents = [
    ...(Array.isArray(early?.events) ? early.events.map((event) => ({ ...event, detail: { ...(event.detail || {}), watch_phase: 'early' }, __early: true })) : []),
    ...payload.events.map((event) => ({ ...event, detail: { ...(event.detail || {}), watch_phase: 'normal' } })),
  ];
  const records = [];
  for (const [index, raw] of rawEvents.entries()) {
    const { __early, ...event } = raw;
    const after = typeof capture === 'function'
      ? await capture(`${options.labelPrefix || 'autonomous-surface'}-${index + 1}-after`, watch.page)
      : null;
    records.push({ ...event, evidence: { before: __early ? watch.earlyBaseline : watch.baseline,
      callback: callbackEvidence.get(event.event_id) || null, after } });
  }
  const earlyGapReconciliations = reconcileSourceTimingGaps({
    gaps: early?.sample_gap_failures || [], samples: early?.animation_samples || [], events: early?.events || [],
    mutationBatches: early?.mutation_batches || [], animationEvents: early?.animation_events || [],
    baseline: watch.earlyBaseline, finalEvidence: watch.baseline, watchPhase: 'early', timelineOriginMs: early?.timeline_origin_ms,
  });
  const normalGapReconciliations = reconcileSourceTimingGaps({
    gaps: payload.sample_gap_failures, samples: payload.animation_samples, events: payload.events,
    mutationBatches: payload.mutation_batches, animationEvents: payload.animation_events,
    baseline: watch.baseline, finalEvidence, watchPhase: 'normal', timelineOriginMs: payload.timeline_origin_ms,
  });
  const report = { ...payload,
    animation_samples: [...(Array.isArray(early?.animation_samples) ? early.animation_samples : []), ...payload.animation_samples],
    sample_gap_failures: [...(Array.isArray(early?.sample_gap_failures) ? early.sample_gap_failures : []), ...payload.sample_gap_failures],
    animation_events: [...(Array.isArray(early?.animation_events) ? early.animation_events : []), ...payload.animation_events],
    mutation_batches: [...(Array.isArray(early?.mutation_batches) ? early.mutation_batches : []), ...payload.mutation_batches],
    tail_mutations: [...(Array.isArray(early?.tail_mutations) ? early.tail_mutations : []), ...payload.tail_mutations],
    early_watch: early ? { id: early.id, elapsed_ms: early.elapsed_ms, timeline_origin_ms: early.timeline_origin_ms,
      handoff: early.handoff || null, sample_interval_ms: early.sample_interval_ms } : null,
    final_target_state_evidence: finalEvidence,
    gap_reconciliations: [...earlyGapReconciliations, ...normalGapReconciliations],
    timing_integrity: { sample_interval_ms: payload.sample_interval_ms, continuous_recording_required: true,
      timeline: { origin_ms: payload.timeline_origin_ms, early_to_normal_handoff: early?.handoff || null },
      gaps_observed: [...(early?.sample_gap_failures || []), ...payload.sample_gap_failures],
      reconciliations: [...earlyGapReconciliations, ...normalGapReconciliations] },
    early_events: Array.isArray(early?.events) ? early.events : [], events: records };
  const failures = sourceSurfaceWatchFailures(report);
  if (failures.length) {
    const error = new Error(`Source autonomous-surface watch cannot clear ${failures.length} candidate event(s): ${failures.join('; ')}`);
    const ambiguous = report.gap_reconciliations?.find((item) => item.ambiguous_candidate_lifecycle);
    error.code = ambiguous ? 'source-surface-watch-timing-integrity-ambiguous' : 'source-surface-watch-evidence-incomplete';
    error.surface_watch = report;
    error.surface_watch_failures = failures;
    if (ambiguous) error.surface_target = { label: ambiguous.surface_label, selector: ambiguous.selector, surface: ambiguous.surface, gap_id: ambiguous.gap_id };
    throw error;
  }
  return report;
}

export async function stopSourceSurfaceWatch(watch) {
  if (watch.closedRootInventory?.listener) watch.page.off('domcontentloaded', watch.closedRootInventory.listener);
  await watch.closedRootInventory?.pending;
  await watch.page.evaluate((id) => {
    const state = window.__designDnaSourceSurfaceWatches?.[id];
    if (state) {
      state.observer?.disconnect(); clearInterval(state.timer);
      for (const observer of state.shadow_observers || []) observer.disconnect();
      for (const entry of state.listeners || []) entry.root.removeEventListener(entry.type, entry.listener, true);
      state.attach_shadow_restore?.();
      delete window.__designDnaSourceSurfaceWatches[id];
    }
    const early = window.__designDnaEarlySourceSurfaceWatches?.[id];
    if (early) {
      early.stop?.();
      delete window.__designDnaEarlySourceSurfaceWatches[id];
    }
  }, watch.id).catch(() => {});
  if (typeof watch.page?.off === 'function' && watch.navigationListener) {
    watch.page.off('framenavigated', watch.navigationListener);
  }
  await retireOneNavigationEarlyScript(watch.earlyScriptRegistration);
  watch.callbackRegistry?.watches?.delete(watch.id);
}

export function undocumentedSourceSurfaceError(report, context = {}) {
  const undocumented = (report?.events || []).filter((event) => event.declared_ambient !== true && !event.detail?.authorized_consent);
  if (!undocumented.length) return null;
  const first = undocumented[0];
  const target = safeSurfaceLabel(first?.surface, first?.selector || null);
  const error = new Error(`${context.profile || 'source'} ${context.state_id || context.phase || 'observation'}: ${undocumented.length} undocumented autonomous source surface(s) appeared after the initial census (first: ${target}; declared selector ${first?.selector || '(none)'}); add an exact source-only ambient contract and recapture, or reject the source.`);
  error.code = 'undocumented-autonomous-source-surface';
  error.surface_watch = report;
  error.undocumented_surfaces = undocumented;
  error.surface_target = { label: target, selector: first?.selector || null, surface: first?.surface || null };
  return error;
}
