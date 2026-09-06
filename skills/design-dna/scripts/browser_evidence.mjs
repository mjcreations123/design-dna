/** Shared, fail-closed browser evidence helpers. */

import { createHash } from "node:crypto";

export const sha256Bytes = (value) => createHash("sha256").update(value).digest("hex");
export const sha256 = sha256Bytes;

export function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

export function normalizeHttpUrl(value) {
  const url = new URL(value);
  if (!/^https?:$/.test(url.protocol)) throw new Error(`unsupported URL protocol: ${url.protocol}`);
  if (url.username || url.password) throw new Error("credential-bearing URLs are forbidden in browser evidence.");
  url.hash = "";
  return url.href;
}

export function sameOriginUrl(value, base, origin) {
  try {
    const url = new URL(value, base);
    if (!/^https?:$/.test(url.protocol) || url.origin !== origin) return null;
    url.hash = "";
    return url.href;
  } catch {
    return null;
  }
}

function navigationError(code, message, navigation = null) {
  const error = new Error(message);
  error.code = code;
  error.navigation = navigation;
  return error;
}

/**
 * Navigate without silently measuring an error page, redirect target, or SPA
 * rewrite. Every HTTP hop and its status is retained in the returned record.
 */
export async function navigateExact(page, requestedUrl, options = {}) {
  const requested = normalizeHttpUrl(requestedUrl);
  let response;
  try {
    response = await page.goto(requested, {
      waitUntil: options.waitUntil || "domcontentloaded",
      timeout: options.timeout || 60000,
    });
  } catch (error) {
    throw navigationError("navigation-failed", `${requested}: ${String(error).slice(0, 300)}`);
  }
  if (!response) throw navigationError("navigation-no-response", `${requested}: navigation produced no HTTP response.`);

  const requests = [];
  for (let cursor = response.request(); cursor; cursor = cursor.redirectedFrom()) requests.push(cursor);
  requests.reverse();
  const redirectChain = [];
  for (let index = 0; index < requests.length; index += 1) {
    const request = requests[index];
    const hopResponse = await request.response();
    redirectChain.push({
      index,
      method: request.method(),
      requested_url: request.url(),
      normalized_url: normalizeHttpUrl(request.url()),
      status: hopResponse ? hopResponse.status() : null,
      status_text: hopResponse ? hopResponse.statusText() : null,
      response_url: hopResponse ? hopResponse.url() : null,
    });
  }
  await page.waitForTimeout(options.settleMs ?? 150);
  const browserFinal = normalizeHttpUrl(page.url());
  const responseFinal = normalizeHttpUrl(response.url());
  const record = {
    requested_url: requestedUrl,
    requested_normalized_url: requested,
    response_final_url: response.url(),
    response_final_normalized_url: responseFinal,
    final_url: page.url(),
    final_normalized_url: browserFinal,
    final_status: response.status(),
    redirect_count: Math.max(0, redirectChain.length - 1),
    redirect_chain: redirectChain,
  };
  record.redirect_chain_sha256 = sha256Bytes(Buffer.from(JSON.stringify(redirectChain), "utf8"));
  if (response.status() < 200 || response.status() > 299) {
    throw navigationError("navigation-status", `${requested}: final HTTP status ${response.status()} is not 2xx.`, record);
  }
  if (responseFinal !== browserFinal) {
    throw navigationError("navigation-browser-rewrite", `${requested}: response ended at ${responseFinal}, but the browser settled at ${browserFinal}.`, record);
  }
  if (browserFinal !== requested) {
    throw navigationError("navigation-final-url", `${requested}: exact normalized final URL was ${browserFinal}. Record the canonical final URL instead of a redirecting alias.`, record);
  }
  return record;
}

export async function collectSameOriginLinks(page, origin) {
  const links = await page.evaluate((expectedOrigin) => {
    const values = new Set();
    for (const anchor of document.querySelectorAll("a[href]")) {
      if (anchor.hasAttribute("download")) continue;
      let target;
      try { target = new URL(anchor.getAttribute("href"), location.href); } catch { continue; }
      if (!/^https?:$/.test(target.protocol) || target.origin !== expectedOrigin) continue;
      target.hash = "";
      values.add(target.href);
    }
    return [...values].sort();
  }, origin);
  return [...new Set(links.map((value) => normalizeHttpUrl(value)))].sort();
}

/**
 * `ambient` deliberately does not belong to a route manifest.  It is a
 * source-observation trigger: a real page changed without an input, and the
 * recorder must wait for and prove that exact change.  A build may map that
 * source state through an explicit, test-only programmatic driver, but may
 * never declare an `ambient` trigger of its own.
 */
export const BUILD_MANIFEST_TRIGGER_TYPES = new Set(["none", "hover", "focus", "click", "keyboard", "input", "url", "programmatic"]);
export const SOURCE_STATE_TRIGGER_TYPES = new Set([...BUILD_MANIFEST_TRIGGER_TYPES, "ambient"]);
export const AMBIENT_SOURCE_WAIT_MIN_MS = 100;
export const AMBIENT_SOURCE_WAIT_MAX_MS = 60000;
const STANDARD_TRIGGER_FIELDS = ["target", "type", "value"];
const AMBIENT_TRIGGER_FIELDS = ["target", "type", "value", "wait_ms"];

function exactObjectKeys(value, expected) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const actual = Object.keys(value).sort();
  return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
}

export function isProgrammaticStateDriverSelector(value) {
  return typeof value === "string" && /^\[data-design-dna-state-driver(?:[=\]])/.test(value);
}

/** A source ambient state can transfer only through a declared build-side
 * test driver.  This does not require the build to transfer the source
 * overlay; it only makes a chosen transfer explicit and executable. */
export function isSourceAmbientMapping(buildState, sourceState) {
  return sourceState?.trigger?.type === "ambient" &&
    buildState?.kind === "system" && buildState?.trigger?.type === "programmatic" &&
    isProgrammaticStateDriverSelector(buildState?.trigger?.target);
}

export function validateManifestState(state, options = {}) {
  const sourceOnly = options.sourceOnly === true;
  const trigger = state?.trigger;
  if (!state || !/^[a-z][a-z0-9-]{0,47}$/.test(state.id || "") ||
      !["rest", "interactive", "system", "data"].includes(state.kind) ||
      typeof state.expectation !== "string" || !state.expectation.trim() ||
      !trigger || typeof trigger.type !== "string" ||
      typeof trigger.target !== "string" || !trigger.target.trim() ||
      !(trigger.value === null || typeof trigger.value === "string")) {
    return "State must have id, kind, substantive expectation, and exact {type,target,value} trigger.";
  }
  if (trigger.type === "ambient") {
    if (!sourceOnly) return "Ambient triggers are source-observation-only; route manifests must use an explicit mapped programmatic build state or omit this source state.";
    if (!exactObjectKeys(trigger, AMBIENT_TRIGGER_FIELDS) || state.kind !== "system" || trigger.value !== null ||
        !Number.isInteger(trigger.wait_ms) || trigger.wait_ms < AMBIENT_SOURCE_WAIT_MIN_MS || trigger.wait_ms > AMBIENT_SOURCE_WAIT_MAX_MS ||
        trigger.target === "document") {
      return `Ambient source states require kind=system and exact {type:"ambient",target:<exact selector>,value:null,wait_ms:${AMBIENT_SOURCE_WAIT_MIN_MS}-${AMBIENT_SOURCE_WAIT_MAX_MS}}.`;
    }
  } else if (!BUILD_MANIFEST_TRIGGER_TYPES.has(trigger.type) || !exactObjectKeys(trigger, STANDARD_TRIGGER_FIELDS)) {
    return "State must use an exact supported build trigger {type,target,value}; ambient is source-observation-only.";
  }
  if (state.kind === "rest" && (state.id !== "rest" || trigger.type !== "none" ||
      trigger.target !== "document" || trigger.value !== null)) {
    return "The rest state must be id=rest with trigger {type:none,target:document,value:null}.";
  }
  if (state.kind !== "rest" && trigger.type === "none") return "Only the rest state may use a none trigger.";
  if (options.requireMappedReference && !/^[a-z][a-z0-9-]{0,47}$/.test(state.mapped_reference_state_id || "")) {
    return "Build states require mapped_reference_state_id as a lowercase slug.";
  }
  return null;
}

async function visualSnapshot(page, selector = null) {
  const rows = await page.evaluate((targetSelector) => {
    const roots = [document];
    for (let index = 0; index < roots.length; index += 1) {
      roots[index].querySelectorAll('*').forEach((element) => { if (element.shadowRoot) roots.push(element.shadowRoot); });
      if (roots[index].nodeType === 9) {
        (roots[index].defaultView.__designDnaCapturedShadowRoots || []).forEach((item) => {
          if (!roots.includes(item.root)) roots.push(item.root);
        });
      }
    }
    let elements;
    if (targetSelector) {
      const target = roots.flatMap((root) => [...root.querySelectorAll(targetSelector)]);
      elements = target.flatMap((element) => [element, ...element.querySelectorAll('*')]);
    } else elements = roots.flatMap((root) => [...root.querySelectorAll('*')]);
    return elements.map((element, index) => {
      const style = element.ownerDocument.defaultView.getComputedStyle(element), box = element.getBoundingClientRect();
      const key = element.id ? `id:${element.id}` : element.getAttribute('data-design-dna-component') ?
        `component:${element.getAttribute('data-design-dna-component')}` :
        `tag:${element.tagName.toLowerCase()}:class:${String(element.getAttribute('class') || '').trim().replace(/\s+/g, '.')}:index:${index}`;
      return { key, tag: element.tagName.toLowerCase(), properties: {
        aria_expanded: element.getAttribute('aria-expanded'), aria_selected: element.getAttribute('aria-selected'),
        aria_pressed: element.getAttribute('aria-pressed'), aria_busy: element.getAttribute('aria-busy'),
        display: style.display, visibility: style.visibility, color: style.color,
        background_color: style.backgroundColor, border_color: style.borderColor, opacity: style.opacity,
        transform: style.transform, filter: style.filter, clip_path: style.clipPath,
        font_family: style.fontFamily, font_size: style.fontSize, font_weight: style.fontWeight,
        left: Math.round(box.left), top: Math.round(box.top), width: Math.round(box.width), height: Math.round(box.height),
        transition_duration: style.transitionDuration, transition_delay: style.transitionDelay,
        transition_property: style.transitionProperty, transition_timing: style.transitionTimingFunction,
        hovered: element.matches(':hover'),
      } };
    });
  }, selector);
  return { rows, sha256: sha256Bytes(Buffer.from(canonicalJson(rows), "utf8")) };
}

function changedVisualProperties(before, after) {
  const diagnosticProperties = new Set([
    'hovered', 'transition_duration', 'transition_delay',
    'transition_property', 'transition_timing',
  ]);
  const prior = new Map(before.rows.map((row) => [row.key, row]));
  const changes = [];
  for (const row of after.rows) {
    const old = prior.get(row.key);
    if (!old) { changes.push({ component_key: row.key, property: "presence", before: null, after: "present" }); continue; }
    for (const [property, value] of Object.entries(row.properties)) {
      if (diagnosticProperties.has(property)) continue;
      if (old.properties[property] !== value) changes.push({ component_key: row.key, property,
        before: old.properties[property], after: value });
    }
    prior.delete(row.key);
  }
  for (const row of prior.values()) changes.push({ component_key: row.key, property: "presence", before: "present", after: null });
  return changes;
}

function classifyVisualChanges(changes, diagnostics = []) {
  const cosmeticNames = new Set([
    'color', 'background_color', 'border_color', 'filter', 'opacity',
    'font_family', 'font_size', 'font_weight',
  ]);
  const cosmetic = changes.filter((change) => cosmeticNames.has(change.property));
  const structuralSemantic = changes.filter((change) => !cosmeticNames.has(change.property));
  return { cosmetic, structural_semantic: structuralSemantic, diagnostic: diagnostics };
}

function diagnosticVisualChanges(before, after) {
  const names = new Set(['hovered', 'transition_duration', 'transition_delay', 'transition_property', 'transition_timing']);
  const prior = new Map(before.rows.map((row) => [row.key, row]));
  return after.rows.flatMap((row) => {
    const old = prior.get(row.key); if (!old) return [];
    return Object.entries(row.properties).filter(([property, value]) => names.has(property) && old.properties[property] !== value)
      .map(([property, value]) => ({ component_key: row.key, property, before: old.properties[property], after: value }));
  });
}

export function classifyVisualEvidence(beforeRows, afterRows) {
  const before = { rows: beforeRows }, after = { rows: afterRows };
  const changes = changedVisualProperties(before, after);
  return { changed_properties: changes,
    change_classification: classifyVisualChanges(changes, diagnosticVisualChanges(before, after)) };
}

async function transitionDurationMs(page, selector) {
  return page.locator(selector).first().evaluate((element) => {
    const parse = (value) => String(value).split(',').map((item) => {
      const part = item.trim(), number = parseFloat(part);
      return Number.isFinite(number) ? number * (part.endsWith('ms') ? 1 : 1000) : 0;
    });
    let maximum = 0;
    for (const node of [element, ...element.querySelectorAll('*')]) {
      const style = getComputedStyle(node), durations = parse(style.transitionDuration), delays = parse(style.transitionDelay);
      for (let index = 0; index < Math.max(durations.length, delays.length); index += 1) {
        maximum = Math.max(maximum, durations[index % durations.length] + delays[index % delays.length]);
      }
    }
    return Math.round(maximum);
  });
}

async function ambientTargetStatus(page, selector) {
  let locator;
  try { locator = page.locator(selector); }
  catch (error) { throw new Error(`ambient target ${JSON.stringify(selector)} is not a valid exact selector: ${String(error?.message || error)}`); }
  let count;
  try { count = await locator.count(); }
  catch (error) { throw new Error(`ambient target ${JSON.stringify(selector)} is not a valid exact selector: ${String(error?.message || error)}`); }
  if (count !== 1) return { count, visible: false, operable: false, details: null };
  const target = locator.first();
  let visible = false, details = null, trial_actionable = false, trial_error = null;
  try {
    visible = await target.isVisible();
    details = await target.evaluate((element) => {
      const style = getComputedStyle(element), box = element.getBoundingClientRect();
      const composedAncestors = [];
      let current = element;
      while (current) {
        composedAncestors.push(current);
        const root = current.getRootNode?.();
        current = current.parentElement || root?.host || null;
      }
      const hiddenAncestor = composedAncestors.find((candidate) => candidate !== element &&
        (candidate.hasAttribute('hidden') || candidate.getAttribute('aria-hidden') === 'true' || candidate.inert === true || candidate.hasAttribute('inert')));
      const disabledAncestor = composedAncestors.find((candidate) => candidate !== element &&
        (candidate.matches?.(':disabled') || candidate.getAttribute('aria-disabled') === 'true'));
      const pointerEventsNone = composedAncestors.find((candidate) => getComputedStyle(candidate).pointerEvents === 'none');
      const point = { x: Math.round(box.left + box.width / 2), y: Math.round(box.top + box.height / 2) };
      const inViewport = point.x >= 0 && point.y >= 0 && point.x < innerWidth && point.y < innerHeight;
      const hit = inViewport ? document.elementFromPoint(point.x, point.y) : null;
      const composedPath = (node) => {
        const result = [];
        let cursor = node;
        while (cursor) {
          result.push(cursor);
          const root = cursor.getRootNode?.();
          cursor = cursor.parentElement || root?.host || null;
        }
        return result;
      };
      const targetPath = composedPath(element), hitPath = composedPath(hit);
      const hitTarget = Boolean(hit && (targetPath.includes(hit) || hitPath.includes(element)));
      const labelledBy = String(element.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean)
        .map((id) => element.ownerDocument.getElementById(id)?.textContent || '').join(' ').trim();
      const heading = [...element.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')]
        .map((candidate) => (candidate.getAttribute('aria-label') || candidate.textContent || '').trim()).find(Boolean) || '';
      const accessibleName = (element.getAttribute('aria-label') || labelledBy || element.getAttribute('title') || heading || element.textContent || '')
        .replace(/\s+/g, ' ').trim().slice(0, 240);
      const tag = element.tagName.toLowerCase();
      const role = (element.getAttribute('role') || (tag === 'dialog' ? 'dialog' : tag)).toLowerCase();
      const classSignature = String(element.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean).sort();
      return {
        aria_hidden: element.getAttribute('aria-hidden'), hidden: element.hasAttribute('hidden'),
        inert: element.inert === true || element.hasAttribute('inert'),
        disabled: element.matches(':disabled') || element.getAttribute('aria-disabled') === 'true',
        hidden_ancestor: Boolean(hiddenAncestor && hiddenAncestor !== element),
        disabled_ancestor: Boolean(disabledAncestor), pointer_events_none: Boolean(pointerEventsNone),
        in_viewport: inViewport, hit_target: hitTarget,
        display: style.display, visibility: style.visibility, opacity: style.opacity,
        width: Math.round(box.width), height: Math.round(box.height),
        target_identity: { tag, role, accessible_name: accessibleName, class_signature: classSignature,
          rect: { left: Math.round(box.left), top: Math.round(box.top), width: Math.round(box.width), height: Math.round(box.height) },
          semantic_key: `${role}|${accessibleName.toLowerCase()}` },
      };
    });
  } catch (error) {
    throw new Error(`ambient target ${JSON.stringify(selector)} could not be inspected: ${String(error?.message || error)}`);
  }
  if (visible && details?.in_viewport && details?.hit_target && !details?.pointer_events_none &&
      !details?.disabled && !details?.disabled_ancestor) {
    try {
      if (typeof target.hover === 'function') {
        await target.hover({ trial: true, timeout: 2000 });
        trial_actionable = true;
      } else {
        // Lightweight test doubles cannot expose Playwright's trial action.
        // Production locators always do, and still require the DOM hit test.
        trial_actionable = true;
      }
    } catch (error) { trial_error = String(error?.message || error); }
  }
  const operable = Boolean(visible && details && !details.hidden && !details.inert && !details.hidden_ancestor &&
    !details.disabled && !details.disabled_ancestor && !details.pointer_events_none && details.in_viewport && details.hit_target &&
    details.aria_hidden !== 'true' && details.display !== 'none' && details.visibility !== 'hidden' &&
    Number(details.opacity) > 0 && details.width > 1 && details.height > 1 && trial_actionable);
  return { count, visible: Boolean(visible), operable, details, trial_actionable, trial_error };
}

async function applyAmbientSourceState(page, state, options) {
  const trigger = state.trigger;
  const beforeTarget = await ambientTargetStatus(page, trigger.target);
  if (beforeTarget.count > 1) {
    throw new Error(`${state.id}: ambient source selector ${JSON.stringify(trigger.target)} matched ${beforeTarget.count} elements before waiting; it must identify exactly one source appearance target.`);
  }
  if (beforeTarget.operable) {
    throw new Error(`${state.id}: ambient source target ${JSON.stringify(trigger.target)} is already visibly operable before its wait; record it as rest or an input-driven state instead of inventing an appearance.`);
  }
  const before = await visualSnapshot(page);
  const started = Date.now();
  const deadline = started + trigger.wait_ms;
  let appearanceTarget = beforeTarget;
  let appearedAfterMs = null;
  while (Date.now() < deadline) {
    appearanceTarget = await ambientTargetStatus(page, trigger.target);
    if (appearanceTarget.count > 1) {
      throw new Error(`${state.id}: ambient source selector ${JSON.stringify(trigger.target)} became ambiguous (${appearanceTarget.count} matches); use the exact one target the reference displays.`);
    }
    if (appearanceTarget.count === 1 && appearanceTarget.operable) {
      appearedAfterMs = Date.now() - started;
      break;
    }
    await page.waitForTimeout(Math.min(100, Math.max(1, deadline - Date.now())));
  }
  if (appearanceTarget.count !== 1 || !appearanceTarget.operable) {
    const last = `last count=${appearanceTarget.count}, visible=${appearanceTarget.visible}, operable=${appearanceTarget.operable}`;
    throw new Error(`${state.id}: ambient source target ${JSON.stringify(trigger.target)} did not appear visibly within its bounded ${trigger.wait_ms}ms wait (${last}). Correct the exact source selector/wait_ms, or remove this source-only state; do not add an invented ambient state to a build manifest.`);
  }
  const after = await visualSnapshot(page);
  if (typeof options.onAmbientAppearance === "function") await options.onAmbientAppearance(page, {
    state_id: state.id, selector: trigger.target, appeared_after_ms: appearedAfterMs,
    target: appearanceTarget,
  });
  const expectedDuration = await transitionDurationMs(page, trigger.target).catch(() => 0);
  await page.waitForTimeout(Math.max(220, expectedDuration + 100));
  const settled = await visualSnapshot(page);
  const settledTarget = await ambientTargetStatus(page, trigger.target);
  if (settledTarget.count !== 1 || !settledTarget.operable) {
    throw new Error(`${state.id}: ambient source target ${JSON.stringify(trigger.target)} appeared but was not visibly operable after settling; bind the actual stable appearance state instead.`);
  }
  const appearanceIdentity = appearanceTarget.details?.target_identity;
  const settledIdentity = settledTarget.details?.target_identity;
  const identityValid = (identity) => identity && typeof identity.tag === 'string' && identity.tag &&
    typeof identity.role === 'string' && identity.role && typeof identity.accessible_name === 'string' && identity.accessible_name &&
    Array.isArray(identity.class_signature) && identity.class_signature.every((value) => typeof value === 'string') &&
    JSON.stringify(identity.class_signature) === JSON.stringify([...identity.class_signature].sort()) &&
    identity.rect && Object.keys(identity.rect).sort().join('|') === 'height|left|top|width' &&
    Object.values(identity.rect).every(Number.isInteger) && typeof identity.semantic_key === 'string' && identity.semantic_key;
  if (!identityValid(appearanceIdentity) || !identityValid(settledIdentity) ||
      appearanceIdentity.tag !== settledIdentity.tag || appearanceIdentity.role !== settledIdentity.role ||
      appearanceIdentity.semantic_key !== settledIdentity.semantic_key) {
    throw new Error(`${state.id}: ambient source target ${JSON.stringify(trigger.target)} lacks one stable accessible appearance/settled target identity; record a source surface with a real role and accessible name.`);
  }
  const changes = changedVisualProperties(before, settled);
  if (!changes.length || before.sha256 === settled.sha256) {
    throw new Error(`${state.id}: ambient source target ${JSON.stringify(trigger.target)} became detectable without a generated visual before/appearance/settled change; it is not transferable appearance evidence.`);
  }
  const classification = classifyVisualChanges(changes, diagnosticVisualChanges(before, settled));
  const targetSnapshot = await visualSnapshot(page, trigger.target);
  const duration = Date.now() - started;
  return { state_id: state.id, applied: true, target_count: 1, navigation: null,
    trigger_evidence: { type: "ambient", target: trigger.target, value: null, wait_ms: trigger.wait_ms,
      target_component_keys: targetSnapshot.rows.map((row) => row.key), before_sha256: before.sha256,
      after_sha256: after.sha256, settled_sha256: settled.sha256, changed_properties: changes,
      change_classification: classification, duration_ms: duration, settled: after.sha256 === settled.sha256,
      appearance_observed: true, appeared_after_ms: appearedAfterMs,
      target_before: beforeTarget, target_appearance: appearanceTarget, target_settled: settledTarget,
      target_identity: { appearance: appearanceIdentity, settled: settledIdentity },
      mechanism: { type: "ambient-appearance", trigger_type: "ambient", duration_ms: duration,
        changed_properties: changes.length }, mechanism_count: 1 },
    before_sha256: before.sha256, after_sha256: settled.sha256, changed: true, navigation: null };
}

/** Apply one explicit state trigger. Programmatic/system/data states require a
 * project-owned harness; the evidence tool will not fabricate their behavior. */
export async function applyManifestState(page, state, options = {}) {
  const invalid = validateManifestState(state, options);
  if (invalid) throw new Error(`${state?.id || "(unnamed state)"}: ${invalid}`);
  const trigger = state.trigger;
  if (trigger.type === "ambient") return applyAmbientSourceState(page, state, options);
  if (trigger.type === "none") {
    const snapshot = await visualSnapshot(page);
    return { state_id: state.id, applied: true, target_count: 1, navigation: null,
      trigger_evidence: { type: "none", target: "document", target_component_keys: snapshot.rows.map((row) => row.key),
        before_sha256: snapshot.sha256, after_sha256: snapshot.sha256, settled_sha256: snapshot.sha256,
        changed_properties: [], change_classification: { cosmetic: [], structural_semantic: [], diagnostic: [] },
        duration_ms: 0, settled: true, mechanism: null, mechanism_count: 0 } };
  }
  if (trigger.type === "url") {
    const before = await visualSnapshot(page);
    const started = Date.now();
    const destination = new URL(trigger.target, page.url()).href;
    const navigation = await navigateExact(page, destination);
    const after = await visualSnapshot(page);
    const changes = changedVisualProperties(before, after);
    const classification = classifyVisualChanges(changes, diagnosticVisualChanges(before, after));
    return { state_id: state.id, applied: true, target_count: 1, navigation,
      trigger_evidence: { type: "url", target: trigger.target,
        target_component_keys: after.rows.map((row) => row.key), before_sha256: before.sha256,
        after_sha256: after.sha256, settled_sha256: after.sha256, changed_properties: changes,
        change_classification: classification,
        duration_ms: Date.now() - started, settled: true,
        mechanism: changes.length ? { type: "page-transition", trigger_type: "url", changed_properties: changes.length } : null,
        mechanism_count: changes.length ? 1 : 0 } };
  }
  if (trigger.type === "programmatic") {
    if (!isProgrammaticStateDriverSelector(trigger.target)) {
      throw new Error(`${state.id}: programmatic target must be a stable [data-design-dna-state-driver] CSS selector.`);
    }
    const driver = page.locator(trigger.target);
    if (await driver.count() !== 1) throw new Error(`${state.id}: programmatic state driver must match exactly one element.`);
    const beforeUrl = normalizeHttpUrl(page.url());
    const before = await visualSnapshot(page);
    const started = Date.now();
    const result = await page.evaluate(async (manifestState) => {
      if (typeof window.__designDnaApplyState !== "function") return { available: false };
      const value = await window.__designDnaApplyState(manifestState);
      return { available: true, value: value === undefined ? null : value };
    }, state);
    if (!result.available) throw new Error(`${state.id}: programmatic trigger requires project-owned window.__designDnaApplyState(state).`);
    if (normalizeHttpUrl(page.url()) !== beforeUrl) throw new Error(`${state.id}: programmatic trigger navigated; declare an exact url trigger instead.`);
    await page.waitForTimeout(50);
    const after = await visualSnapshot(page);
    await page.waitForTimeout(180);
    const settled = await visualSnapshot(page);
    const changes = changedVisualProperties(before, settled);
    const classification = classifyVisualChanges(changes, diagnosticVisualChanges(before, settled));
    return { state_id: state.id, applied: true, target_count: 1, harness_result: result.value,
      trigger_evidence: { type: trigger.type, target: trigger.target,
        target_component_keys: settled.rows.map((row) => row.key), before_sha256: before.sha256,
        after_sha256: after.sha256, settled_sha256: settled.sha256, changed_properties: changes,
        change_classification: classification,
        duration_ms: Date.now() - started, settled: after.sha256 === settled.sha256,
        mechanism: changes.length ? { type: "state-transition", trigger_type: trigger.type, changed_properties: changes.length } : null,
        mechanism_count: changes.length ? 1 : 0 },
      before_sha256: before.sha256, after_sha256: settled.sha256, changed: changes.length > 0, navigation: null };
  }
  const locator = page.locator(trigger.target);
  const count = await locator.count();
  if (count !== 1) throw new Error(`${state.id}: trigger target ${JSON.stringify(trigger.target)} matched ${count} elements; exactly one is required.`);
  const target = locator.first();
  if (!(await target.isVisible())) throw new Error(`${state.id}: trigger target ${JSON.stringify(trigger.target)} is not visible.`);
  if (["click", "keyboard"].includes(trigger.type)) {
    const safety = await interactionTargetSafety(target, trigger.type, trigger.value);
    if (!safety.safe) {
      const error = new Error(`${state.id}: trigger blocked because it may cause ${safety.reason}; use an owner-authorized disposable session and bind generated handoff evidence.`);
      error.code = "side-effect-blocked";
      error.handoff = { state_id: state.id, target: trigger.target, reason: safety.reason };
      throw error;
    }
  }
  const beforeUrl = normalizeHttpUrl(page.url());
  const before = await visualSnapshot(page, trigger.target);
  const expectedDuration = await transitionDurationMs(page, trigger.target);
  const started = Date.now();
  if (trigger.type === "hover") await target.hover({ timeout: 5000 });
  else if (trigger.type === "focus") await target.focus({ timeout: 5000 });
  else if (trigger.type === "click") await target.click({ timeout: 5000 });
  else if (trigger.type === "keyboard") {
    await target.focus({ timeout: 5000 });
    if (!trigger.value) throw new Error(`${state.id}: keyboard trigger requires a nonempty value.`);
    await page.keyboard.press(trigger.value);
  } else if (trigger.type === "input") {
    if (trigger.value === null) throw new Error(`${state.id}: input trigger requires a string value.`);
    await target.fill(trigger.value);
  }
  if (normalizeHttpUrl(page.url()) !== beforeUrl) throw new Error(`${state.id}: ${trigger.type} trigger navigated; declare an exact url trigger instead.`);
  await page.waitForTimeout(50);
  const after = await visualSnapshot(page, trigger.target);
  await page.waitForTimeout(Math.max(130, expectedDuration + 100));
  const settled = await visualSnapshot(page, trigger.target);
  const changes = changedVisualProperties(before, settled);
  const classification = classifyVisualChanges(changes, diagnosticVisualChanges(before, settled));
  const mechanismType = trigger.type === "hover" ? "hover-transition" : "state-transition";
  return { state_id: state.id, applied: true, target_count: 1,
    trigger_evidence: { type: trigger.type, target: trigger.target,
      target_component_keys: settled.rows.map((row) => row.key), before_sha256: before.sha256,
      after_sha256: after.sha256, settled_sha256: settled.sha256, changed_properties: changes,
      change_classification: classification,
      duration_ms: Math.max(expectedDuration, Date.now() - started), settled: after.sha256 === settled.sha256,
      mechanism: changes.length ? { type: mechanismType, trigger_type: trigger.type,
        duration_ms: expectedDuration, changed_properties: changes.length } : null,
      mechanism_count: changes.length ? 1 : 0 },
    before_sha256: before.sha256, after_sha256: settled.sha256, changed: changes.length > 0, navigation: null };
}

/** Infer observable build/reference states, then require an explicit authored
 * trigger to cover each one. This reports facts; it never invents state IDs. */
export async function inferAndReconcileStates(page, authoredStates) {
  const candidates = await page.evaluate(() => {
    let sequence = 0;
    const roots = [document], result = [], seen = new Set();
    for (let index = 0; index < roots.length; index += 1) roots[index].querySelectorAll('*').forEach((element) => { if (element.shadowRoot) roots.push(element.shadowRoot); });
    const visible = (element) => { const style = getComputedStyle(element), box = element.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && box.width > 1 && box.height > 1; };
    const add = (element, signal, kind, triggers, declaredStateId = null) => {
      if (!visible(element)) return;
      if (!element.dataset.dnaStateCandidate) element.dataset.dnaStateCandidate = String(++sequence);
      const key = `${element.dataset.dnaStateCandidate}:${signal}`; if (seen.has(key)) return; seen.add(key);
      result.push({ key, element_key: element.dataset.dnaStateCandidate, signal, kind, required_triggers: triggers,
        declared_state_id: declaredStateId, tag: element.tagName.toLowerCase(),
        text: (element.getAttribute('aria-label') || element.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 160) });
    };
    for (const root of roots) for (const element of root.querySelectorAll('*')) {
      const explicit = element.getAttribute('data-design-dna-state');
      if (explicit) add(element, 'explicit-state', element.getAttribute('data-design-dna-state-kind') || 'data', ['programmatic'], explicit);
      if (element.matches('[data-design-dna-state-driver]')) {
        const ids = String(element.getAttribute('data-design-dna-states') || '').split(/[\s,]+/).filter(Boolean);
        if (ids.length) ids.forEach((id) => add(element, `state-driver:${id}`, /loading|error|success|empty/.test(id) ? 'system' : 'data', ['programmatic'], id));
        else add(element, 'state-driver', 'data', ['programmatic']);
      }
      if (element.matches('[aria-expanded],details,[aria-haspopup],[role="tab"][aria-selected],[aria-pressed],[aria-selected]'))
        add(element, 'disclosure-selection', 'interactive', ['click','keyboard','programmatic']);
      if (element.matches(':disabled,[aria-disabled="true"],[aria-disabled="false"]')) add(element, 'disabled', 'interactive', ['programmatic']);
      // A dialog can be opened by a visitor or arrive on its own after a
      // timed/source-side condition.  If the latter appears during the long
      // recorder pass without an authored ambient source state, reconciliation
      // remains incomplete rather than silently treating the blocker as rest.
      if (element.matches('[role="dialog"],dialog')) add(element, 'dialog', 'interactive', ['click','keyboard','programmatic','ambient']);
      if (element.matches('a[href],button,input,select,textarea,summary,[tabindex]:not([tabindex="-1"])')) {
        add(element, 'focusable', 'interactive', ['focus']); add(element, 'hover-candidate', 'interactive', ['hover']);
      }
      if (element.matches('[aria-busy],[role="alert"],[role="status"],:invalid,[aria-invalid]'))
        add(element, 'system-or-validation', 'system', ['programmatic','input']);
    }
    return result;
  });
  for (const candidate of candidates.filter((item) => item.signal === 'hover-candidate')) {
    try {
      const target = page.locator(`[data-dna-state-candidate="${candidate.element_key}"]`);
      const before = await visualSnapshot(page, `[data-dna-state-candidate="${candidate.element_key}"]`);
      await target.hover({ timeout: 3000 }); await page.waitForTimeout(180);
      const after = await visualSnapshot(page, `[data-dna-state-candidate="${candidate.element_key}"]`);
      candidate.actual_style_response = changedVisualProperties(before, after).length > 0;
    } catch { candidate.actual_style_response = false; }
  }
  const required = candidates.filter((item) => item.signal !== 'hover-candidate' || item.actual_style_response);
  for (const candidate of required) {
    candidate.reconciled_state_ids = [];
    for (const state of authoredStates) {
      if (candidate.declared_state_id === state.id) { candidate.reconciled_state_ids.push(state.id); continue; }
      if (!candidate.required_triggers.includes(state.trigger?.type) || ['url','none'].includes(state.trigger.type)) continue;
      try {
        const target = page.locator(state.trigger.target);
        if (await target.count() !== 1) continue;
        if (await target.first().getAttribute('data-dna-state-candidate') === candidate.element_key) candidate.reconciled_state_ids.push(state.id);
      } catch { /* invalid target is rejected during application */ }
    }
  }
  return { inferred: required, unreconciled: required.filter((item) => !item.reconciled_state_ids.length),
    complete: required.every((item) => item.reconciled_state_ids.length > 0) };
}

export function interactionReconciliationGaps({ domTargetIds = [], liveTargetIds = [], authoredStateIds = [], boundStateIds = [] }) {
  const live = new Set(liveTargetIds), bound = new Set(boundStateIds);
  return {
    controls: [...new Set(domTargetIds)].filter((id) => !live.has(id)).sort(),
    states: [...new Set(authoredStateIds)].filter((id) => !bound.has(id)).sort(),
  };
}

export async function interactionTargetSafety(target, inputKind, inputValue = null) {
  return target.evaluate((element, input) => {
    if (element.tagName.toLowerCase() === 'details') element = element.querySelector('summary') || element;
    const kind = input.kind, value = input.value;
    const text = [element.getAttribute('aria-label'), element.getAttribute('title'), element.textContent,
      ['BUTTON', 'INPUT'].includes(element.tagName) ? element.value : null].filter(Boolean).join(' ').trim().replace(/\s+/g, ' ').toLowerCase();
    const tag = element.tagName.toLowerCase(), role = element.getAttribute('role') || '';
    // Page-owned claims and ARIA describe a source; they cannot authorize a
    // purchase, submission, destructive action, or account/session change.
    const claimedSafe = element.getAttribute('data-design-dna-safe-state') === 'true';
    const dangerousWords = /\b(add(?: to cart)?|buy|purchase|pay|checkout|submit|send|delete|remove|cancel|confirm|book|reserve|subscribe|register|upload|sign out|log out|publish)\b/;
    const controlType = String(element.getAttribute('type') || (tag === 'button' ? 'submit' : '')).toLowerCase();
    const formSubmit = Boolean(element.form) && ((tag === 'button' && controlType === 'submit') ||
      (tag === 'input' && ['submit', 'image'].includes(controlType)));
    const navigates = tag === 'a' && element.hasAttribute('href');
    const safeDisclosure = tag === 'summary' || role === 'tab' || element.hasAttribute('aria-expanded') || element.hasAttribute('aria-pressed');
    const activatingKeyboard = kind === 'keyboard' && /^(enter|space| )$/i.test(String(value || ''));
    const unknownButton = (tag === 'button' || role === 'button') && !safeDisclosure;
    const activating = ['click', 'open-close'].includes(kind) || activatingKeyboard;
    const potentiallyMutating = activating && (formSubmit || navigates || element.hasAttribute('download') ||
      unknownButton || dangerousWords.test(text));
    return { safe: !potentiallyMutating, explicit_safe: false, ignored_page_safe_claim: claimedSafe,
      reason: potentiallyMutating ? 'potential external/state-changing side effect' : null,
      tag, role, text, href: element.getAttribute('href'), type: element.getAttribute('type') };
  }, { kind: inputKind, value: inputValue });
}

/** Discover the live interaction surface without exercising it. */
export async function discoverInteractionTargets(page) {
  return page.evaluate(async () => {
    let sequence = 0;
    const roots = [document], targets = [], stateHooks = [], animationHooks = [];
    for (let index = 0; index < roots.length; index += 1) roots[index].querySelectorAll('*').forEach((element) => { if (element.shadowRoot) roots.push(element.shadowRoot); });
    for (const root of roots) root.querySelectorAll('[data-dna-interaction-id]').forEach((element) => {
      sequence = Math.max(sequence, Number(element.dataset.dnaInteractionId || 0));
    });
    const selector = 'a[href],button,input,select,textarea,summary,details,video,audio,[role="button"],[role="tab"],[role="menuitem"],[role="switch"],[role="checkbox"],[role="radio"],[role="slider"],[draggable="true"],[ondragstart],[ondrag],[ondrop],[ontouchstart],[ontouchmove],[ontouchend],[onpointerdown],[onpointermove],[onpointerup],[onclick],[tabindex]';
    const seen = new Set();
    for (const root of roots) {
      const candidates = new Set(root.querySelectorAll(selector));
      root.querySelectorAll('*').forEach((element) => { if (['pointer','grab','grabbing'].includes(getComputedStyle(element).cursor)) candidates.add(element); });
      for (const element of candidates) {
        const style = getComputedStyle(element), box = element.getBoundingClientRect();
        if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) <= 0 || box.width <= 1 || box.height <= 1) continue;
        if (!element.dataset.dnaInteractionId) element.dataset.dnaInteractionId = String(++sequence);
        const marker = element.dataset.dnaInteractionId; if (seen.has(marker)) continue; seen.add(marker);
        const classes = String(element.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean).sort();
        const role = element.getAttribute('role') || element.tagName.toLowerCase();
        const text = (element.getAttribute('aria-label') || element.textContent || '')
          .trim().replace(/\s+/g, ' ').slice(0, 200);
        const semanticKey = `${role.toLowerCase()}|${text.toLowerCase()}`;
        const repeatClass = `${element.tagName.toLowerCase()}|${role}|${classes.join('.') || 'unclassed'}`;
        const gestureSignals = [];
        if (element.getAttribute('draggable') === 'true') gestureSignals.push('native-draggable');
        if (['grab','grabbing'].includes(style.cursor)) gestureSignals.push(`cursor:${style.cursor}`);
        if (role === 'slider' || element.matches('input[type="range"]')) gestureSignals.push('range-slider');
        for (const name of ['ondragstart','ondrag','ondrop','ontouchstart','ontouchmove','ontouchend','onpointerdown','onpointermove','onpointerup']) {
          const handler = element.getAttribute(name);
          const gestureCue = /\b(?:drag|drop|swipe|pinch|pan|slide)\s+(?:to|this|the|files|left|right|up|down)\b|\btouch-controlled\b/i.test(text);
          const visibleMutation = /\.style\.[a-zA-Z]+\s*=|\.style\.setProperty\s*\(|\.classList\.(?:add|remove|toggle|replace)\s*\(|\.(?:textContent|innerHTML|scrollTop|scrollLeft)\s*=/.test(handler || '');
          if (handler !== null && (gestureCue || visibleMutation)) gestureSignals.push(`inline:${name}`);
        }
        const standardTarget = element.matches('a[href],button,input,select,textarea,summary,details,video,audio,[role="button"],[role="tab"],[role="menuitem"],[role="switch"],[role="checkbox"],[role="radio"],[onclick],[tabindex]') || style.cursor === 'pointer';
        if (!standardTarget && !gestureSignals.length) continue;
        const sourceSelector = element.id && document.querySelectorAll('#' + CSS.escape(element.id)).length === 1
          ? '#' + CSS.escape(element.id) : `[data-dna-interaction-id="${marker}"]`;
        targets.push({ marker, selector: `[data-dna-interaction-id="${marker}"]`, source_selector: sourceSelector, tag: element.tagName.toLowerCase(), role,
          text, semantic_key: semanticKey, class_signature: classes, repeat_class: repeatClass,
          kind: ['video','audio'].includes(element.tagName.toLowerCase()) ? 'media' :
            (element.matches('details,summary,[aria-expanded]') ? 'open-close' :
              (element.matches('input,select,textarea') ? 'input-control' :
                (element.matches('a[href]') ? 'route-link' : 'control'))),
          focusable: element.matches('a[href],button,input,select,textarea,summary,[tabindex]:not([tabindex="-1"])'),
          hoverable: getComputedStyle(element).cursor === 'pointer' || element.matches('a[href],button,summary,[role="button"],[role="tab"]'),
          href: element.tagName === 'A' ? element.href : null, gesture_signals: gestureSignals,
          semantic_state: {
            aria_expanded: element.getAttribute('aria-expanded'),
            aria_pressed: element.getAttribute('aria-pressed'),
            aria_controls: element.getAttribute('aria-controls'),
            aria_haspopup: element.getAttribute('aria-haspopup'),
            disabled: element.matches(':disabled,[aria-disabled="true"]'),
          } });
        const stateAttributes = ['aria-expanded','aria-selected','aria-pressed','aria-busy','aria-invalid','data-state','data-design-dna-state']
          .filter((name) => element.hasAttribute(name)).map((name) => ({ name, value: element.getAttribute(name) }));
        if (stateAttributes.length) stateHooks.push({ marker, attributes: stateAttributes });
        if (style.transitionDuration !== '0s' || style.animationName !== 'none' || element.getAnimations().length) {
          animationHooks.push({ marker, transition_property: style.transitionProperty,
            transition_duration: style.transitionDuration, animation_name: style.animationName,
            active_animations: element.getAnimations().length });
        }
      }
    }
    const routes = [...new Set(roots.flatMap((root) => [...root.querySelectorAll('a[href]')]).map((anchor) => {
      try { const url = new URL(anchor.getAttribute('href'), location.href); if (url.origin !== location.origin || !/^https?:$/.test(url.protocol)) return null; url.hash=''; return url.href; }
      catch { return null; }
    }).filter(Boolean))].sort();
    const assets = [...new Set(roots.flatMap((root) => [...root.querySelectorAll('img,video,audio,source')]).flatMap((element) =>
      [element.currentSrc, element.src, element.poster].filter(Boolean)).concat(roots.flatMap((root) => [...root.querySelectorAll('*')]).flatMap((element) => {
        const value = getComputedStyle(element).backgroundImage; return value && value !== 'none' ? [value] : [];
      })))].sort();
    const scripts = await Promise.all(roots.filter((root) => root.nodeType === 9).flatMap((root) => [...root.scripts]).map(async (script) => {
      const inline = script.src ? null : new TextEncoder().encode(script.textContent || '');
      const digest = inline ? await crypto.subtle.digest('SHA-256', inline) : null;
      return { src: script.src || null, type: script.type || 'classic', bytes: inline?.byteLength || null,
        inline_sha256: digest ? [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('') : null };
    }));
    const inlineHandlers = roots.flatMap((root) => [...root.querySelectorAll('*')]).flatMap((element) => [...element.attributes]
      .filter((attribute) => attribute.name.startsWith('on')).map((attribute) => ({ marker: element.dataset.dnaInteractionId || null,
        attribute: attribute.name, code_length: attribute.value.length })));
    return { targets, dom_code_inventory: { routes, state_hooks: stateHooks, animation_hooks: animationHooks,
      assets, scripts, inline_handlers: inlineHandlers } };
  });
}

/** Read actual registered gesture listeners without replacing page APIs or
 * dispatching a guessed drag/touch sequence. A candidate is an unresolved
 * source-study requirement until the packaged runner supports its exact input.
 * Handler source text is deliberately not copied into the evidence. */
const sourceRuntimeGestureScripts = new WeakMap();

/** Executed read-only in the inspected root's own browser realm. */
function inspectClosedRootMaterial(root, viewportOnly) {
      const host = root.host;
      if (!host?.isConnected) return null;
      const ownerDocument = host.ownerDocument, view = ownerDocument.defaultView;
      const material = [];
      const visibleAncestry = (element) => {
        for (let current = element; current; current = current.parentElement || current.getRootNode()?.host || null) {
          const style = view.getComputedStyle(current);
          if (style.display === 'none' || ['hidden','collapse'].includes(style.visibility) || Number(style.opacity) <= 0) return false;
        }
        return true;
      };
      const inViewport = (box) => !viewportOnly || box.bottom > 0 && box.top < view.innerHeight && box.right > 0 && box.left < view.innerWidth;
      for (const node of root.childNodes) {
        if (node.nodeType !== 3 || !node.textContent.trim() || !visibleAncestry(host)) continue;
        const range = ownerDocument.createRange(); range.selectNodeContents(node);
        if ([...range.getClientRects()].some((box) => box.width > 0 && box.height > 0 && inViewport(box))) material.push({tag:'#text',kind:'text',text:node.textContent.trim().replace(/\s+/g,' ').slice(0,160)});
      }
      for (const element of root.querySelectorAll('*')) {
        if (element.matches('style,script,link,meta,template,noscript')) continue;
        const box = element.getBoundingClientRect(), style = view.getComputedStyle(element);
        if (visibleAncestry(element)) for (const pseudo of ['::before','::after']) {
          const painted = view.getComputedStyle(element, pseudo);
          const content = painted.content;
          const background = painted.backgroundImage !== 'none' || !['transparent','rgba(0, 0, 0, 0)'].includes(painted.backgroundColor);
          const border = ['Top','Right','Bottom','Left'].some((side) => parseFloat(painted['border'+side+'Width']) > 0 && painted['border'+side+'Style'] !== 'none');
          const hasContent = content && !['none','normal'].includes(content);
          const contentText = String(content || '').replace(/^(["'])([\s\S]*)\1$/, '$2').trim();
          if (hasContent && painted.display !== 'none' && !['hidden','collapse'].includes(painted.visibility) && Number(painted.opacity) > 0 &&
              (contentText || background || border) && inViewport(box)) {
            material.push({tag:element.tagName.toLowerCase()+pseudo,kind:'pseudo',text:String(content).slice(0,160)});
          }
        }
        if (!element.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) || box.width <= 0 || box.height <= 0 ||
            viewportOnly && (box.bottom <= 0 || box.top >= view.innerHeight || box.right <= 0 || box.left >= view.innerWidth)) continue;
        const control = element.matches('button,a[href],input,select,textarea,summary,[role="button"],[role="tab"],[role="slider"],[tabindex]:not([tabindex="-1"])');
        const text = [...element.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
        const media = element.matches('img,svg,canvas,video,audio,iframe,object,embed');
        const backgroundPaint = style.backgroundImage !== 'none' || !['transparent','rgba(0, 0, 0, 0)'].includes(style.backgroundColor);
        const borderPaint = ['Top','Right','Bottom','Left'].some((side) => parseFloat(style['border'+side+'Width']) > 0 && style['border'+side+'Style'] !== 'none');
        const kind = control ? 'control' : media ? 'media' : text ? 'text' : backgroundPaint || borderPaint ? 'painted-layout' : null;
        if (kind) material.push({ tag: element.tagName.toLowerCase(), kind,
          text: (element.getAttribute('aria-label') || element.textContent || '').trim().replace(/\s+/g,' ').slice(0,160) });
      }
      if (!material.length) return null;
      const inDocument = host.getRootNode() === ownerDocument;
      let hostSelector = null;
      if (inDocument && host.id && ownerDocument.querySelectorAll('#'+view.CSS.escape(host.id)).length === 1) hostSelector = '#'+view.CSS.escape(host.id);
      else if (inDocument) {
        const parts = []; let element = host;
        while (element && element.nodeType === 1) {
          const siblings = element.parentElement ? [...element.parentElement.children].filter((item) => item.tagName === element.tagName) : [];
          parts.unshift(element.tagName.toLowerCase()+(siblings.length > 1 ? ':nth-of-type('+(siblings.indexOf(element)+1)+')' : ''));
          element = element.parentElement;
        }
        hostSelector = parts.join(' > ');
      }
      return { host_selector: hostSelector, host_local_selector: hostSelector,
        host_description: host.tagName.toLowerCase() + (host.id ? '#'+host.id : '') + (inDocument ? '' : ' inside a shadow root'),
        host_selector_scope: inDocument ? 'frame-document' : 'unaddressable-shadow-boundary',
        host_tag: host.tagName.toLowerCase(), mode: 'closed', document_url: ownerDocument.URL,
        observed_kinds: [...new Set(material.map((item) => item.kind))].sort(), visible_material_count: material.length, material };
}

/** Browser-owned inventory covers both attachShadow() and parser-created
 * declarative closed roots. Backend IDs deduplicate both creation paths; the
 * JS instrumentation registry remains available to the surface watcher but is
 * never treated as proof that no parser-created root exists. */
export async function discoverUnaddressableClosedRoots(page, options = {}) {
  const clients = new Set();
  const objectGroup = `design-dna-closed-root-inventory-${Date.now()}`;
  let activeFrameContext = null;
  try {
    const frames = new Map(), candidates = new Map(), opaqueFrames = new Map(), inspectedFrames = new Set(), documents = new Map();
    const frameVisibility = new Map(), frameSessions = new Map();
    let mainFrameId;
    const collectFrames = (entry) => {
      if (!entry?.frame?.id) throw new Error('The browser returned a frame without an identity.');
      frames.set(entry.frame.id, entry.frame);
      for (const child of entry.childFrames || []) collectFrames(child);
    };
    const walk = (node, frameId, client, frameOwners = []) => {
      if (node.nodeType === 9) documents.set(frameId, {node,client,frameOwners});
      for (const shadow of node.shadowRoots || []) {
        if (shadow.shadowRootType === 'user-agent') continue;
        if (!['open','closed'].includes(shadow.shadowRootType)) throw new Error('An unknown browser shadow-root kind cannot be classified as covered.');
        if (shadow.shadowRootType === 'closed') {
          if (!Number.isInteger(shadow.backendNodeId) || !Number.isInteger(node.backendNodeId)) throw new Error('An author-closed root has no browser-owned identity.');
          candidates.set(`${frameId}:${shadow.backendNodeId}`, { root: shadow, host: node, frameId, frameOwners, client });
        }
        walk(shadow, frameId, client, frameOwners);
      }
      for (const child of node.children || []) walk(child, frameId, client, frameOwners);
      if (node.contentDocument) {
        const childFrameId = node.frameId || node.contentDocument.frameId;
        if (!childFrameId) throw new Error('A child document has no verified frame identity; its closed-root scope cannot be guessed.');
        if (!frames.has(childFrameId)) frames.set(childFrameId, {id:childFrameId,url:node.contentDocument.documentURL});
        inspectedFrames.add(childFrameId);
        walk(node.contentDocument, childFrameId, client, [...frameOwners, {client,backendNodeId:node.backendNodeId}]);
      } else if (node.nodeType === 1 && node.frameId) {
        opaqueFrames.set(node.frameId, {frameId:node.frameId,parentFrameId:frameId,frameOwners:[...frameOwners,{client,backendNodeId:node.backendNodeId}]});
      }
    };
    const inspectDocument = async (client, expectedId = null, frameOwners = []) => {
      await client.send('DOM.enable');
      const {frameTree} = await client.send('Page.getFrameTree');
      collectFrames(frameTree);
      const frameId = frameTree.frame.id;
      if (expectedId && frameId !== expectedId) throw new Error('The frame session does not match the browser-owned target frame ID.');
      activeFrameContext = {id:frameId,url:frameTree.frame.url,is_main:!expectedId || frameId === mainFrameId};
      const {root} = await client.send('DOM.getDocument', {depth:-1,pierce:true});
      if (!root?.backendNodeId) throw new Error('The browser did not return a complete document identity.');
      inspectedFrames.add(frameId);
      walk(root, frameId, client, frameOwners);
      return frameId;
    };
    const ownersVisible = async (owners) => {
      for (const {client,backendNodeId} of owners) {
        if (!frameVisibility.has(client)) frameVisibility.set(client, new Map());
        const visibilityCache = frameVisibility.get(client);
        if (!visibilityCache.has(backendNodeId)) {
          const owner = await client.send('DOM.resolveNode', { backendNodeId, objectGroup });
          if (!owner.object?.objectId) throw new Error('A frame owner disappeared before its visibility could be inspected.');
          const visibility = await client.send('Runtime.callFunctionOn', { objectId: owner.object.objectId, returnByValue: true,
            arguments: [{ value: options.viewportOnly === true }],
            functionDeclaration: `function(viewportOnly) { const box=this.getBoundingClientRect(),view=this.ownerDocument.defaultView; return this.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}) && box.width>0 && box.height>0 && (!viewportOnly || box.bottom>0 && box.top<view.innerHeight && box.right>0 && box.left<view.innerWidth); }` });
          if (visibility.exceptionDetails || typeof visibility.result?.value !== 'boolean') throw new Error('A frame owner has no reliable visibility result.');
          visibilityCache.set(backendNodeId, visibility.result.value);
        }
        if (!visibilityCache.get(backendNodeId)) return false;
      }
      return true;
    };
    const mainClient = await page.context().newCDPSession(page);
    clients.add(mainClient);
    mainFrameId = await inspectDocument(mainClient);
    const visitedOpaque = new Set();
    while ([...opaqueFrames.keys()].some((id) => !visitedOpaque.has(id))) {
      for (const entry of [...opaqueFrames.values()]) {
        if (visitedOpaque.has(entry.frameId)) continue;
        visitedOpaque.add(entry.frameId);
        if (inspectedFrames.has(entry.frameId) || !await ownersVisible(entry.frameOwners)) continue;
        const target = frames.get(entry.frameId);
        activeFrameContext = {id:entry.frameId,url:target?.url || null,is_main:false,parent_frame_id:entry.parentFrameId};
        let selected = null;
        const errors = [], candidateFrameUrls = [];
        for (const frame of page.frames()) {
          if (frame === page.mainFrame() || target?.url && frame.url() !== target.url) continue;
          candidateFrameUrls.push(frame.url());
          if (!frameSessions.has(frame)) {
            try {
              const client = await page.context().newCDPSession(frame);
              clients.add(client);
              const {frameTree} = await client.send('Page.getFrameTree');
              frameSessions.set(frame, {client,frameId:frameTree?.frame?.id});
            } catch (error) { frameSessions.set(frame, {error:String(error?.message || error)}); }
          }
          const session = frameSessions.get(frame);
          if (session.frameId === entry.frameId) { selected = session.client; break; }
          if (session.error) errors.push(session.error);
        }
        if (!selected) {
          const code = 'closed-shadow-frame-inspection-unavailable';
          const reason = 'A visible frame has no inspectable matching CDP document; closed-root coverage remains unknown.';
          const frameContext = {id:entry.frameId,url:target?.url || null,is_main:false,parent_frame_id:entry.parentFrameId,
            owner_backend_node_id:entry.frameOwners[entry.frameOwners.length-1].backendNodeId};
          throw Object.assign(new Error(reason), {code,source_harness_gap:true,frame_context:frameContext,inspection_errors:errors,candidate_frame_urls:candidateFrameUrls,
            census_diagnostic:{schema_version:1,kind:'closed-shadow-frame-coverage-incomplete',complete:false,profile:null,
              context:{phase:'closed-shadow-frame-inventory'},failures:[{code,reason,frame_context:frameContext,inspection_errors:errors,candidate_frame_urls:candidateFrameUrls,evidence:null}]}});
        }
        await inspectDocument(selected, entry.frameId, entry.frameOwners);
      }
    }
    const result = [];
    for (const candidate of candidates.values()) {
      activeFrameContext = {id:candidate.frameId,url:frames.get(candidate.frameId)?.url || null,is_main:candidate.frameId === mainFrameId};
      if (!await ownersVisible(candidate.frameOwners)) continue;
      const client = candidate.client;
      const resolved = await client.send('DOM.resolveNode', { backendNodeId: candidate.root.backendNodeId, objectGroup });
      if (!resolved.object?.objectId) throw new Error('An author-closed root disappeared before its material could be inspected.');
      const inspected = await client.send('Runtime.callFunctionOn', { objectId: resolved.object.objectId, returnByValue: true,
        arguments: [{ value: options.viewportOnly === true }, { value: { host_backend_node_id: candidate.host.backendNodeId,
          closed_root_backend_node_id: candidate.root.backendNodeId, frame_context: activeFrameContext } }],
        functionDeclaration: `function(viewportOnly, identity) {
          // Parser-created roots bypass attachShadow instrumentation. Retain the
          // actual browser object for the continuous watcher before filtering
          // current material, so hidden-then-visible-then-hidden UI is observed.
          // This harness-only registry never opens the source's native root.
          const view = this.ownerDocument.defaultView;
          if (view.__designDnaCapturedShadowRoots === undefined) {
            Object.defineProperty(view, '__designDnaCapturedShadowRoots', { value: [], configurable: false });
          }
          const roots = view.__designDnaCapturedShadowRoots;
          if (!Array.isArray(roots)) throw new Error('The captured-root inventory is unavailable.');
          let entry = roots.find((item) => item?.root === this);
          if (!entry) { entry = { host: this.host, root: this, mode: 'closed', discovery: 'browser-cdp' }; roots.push(entry); }
          entry.browser_identity = identity;
          const inspect = (${inspectClosedRootMaterial.toString()});
          entry.sampleMaterial = (phase) => {
            try {
              const material = inspect(this, false);
              if (material && !entry.observed_material) entry.observed_material = { ...material,
                material_observation: { kind: 'continuous-watch', phase, document_elapsed_ms: view.performance.now(),
                  observed_at_ms: view.performance.timeOrigin + view.performance.now() } };
            } catch (error) { entry.material_inspection_error ||= String(error?.message || error); }
          };
          if (entry.material_inspection_error) throw new Error(entry.material_inspection_error);
          return inspect(this, viewportOnly) || (!viewportOnly ? entry.observed_material || null : null);
        }` });
      if (inspected.exceptionDetails || !Object.hasOwn(inspected.result || {}, 'value')) throw new Error('Closed-root material inspection did not return a reliable result.');
      const material = inspected.result.value;
      if (material === null) continue;
      if (!material || !Array.isArray(material.material) || !material.material.length) throw new Error('Closed-root material inspection returned an unsupported shape.');
      const frame = frames.get(candidate.frameId), isMain = candidate.frameId === mainFrameId;
      if (!frame) throw new Error('Closed-root frame identity was lost during inspection.');
      if (!isMain) {
        material.host_selector = null;
        material.host_description += ` in frame ${frame.url}`;
      }
      result.push({ ...material, host_backend_node_id: candidate.host.backendNodeId,
        closed_root_backend_node_id: candidate.root.backendNodeId,
        frame_context: { id: candidate.frameId, url: frame.url, is_main: isMain, document_url: material.document_url } });
    }
    if (options.viewportOnly !== true) for (const [frameId, document] of documents) {
      if (!await ownersVisible(document.frameOwners)) continue;
      const resolved = await document.client.send('DOM.resolveNode', {backendNodeId:document.node.backendNodeId,objectGroup});
      if (!resolved.object?.objectId) throw new Error('A studied document disappeared before its retained closed-root history could be reconciled.');
      const history = await document.client.send('Runtime.callFunctionOn', {objectId:resolved.object.objectId,returnByValue:true,
        functionDeclaration: `function() {
          const roots = this.defaultView.__designDnaCapturedShadowRoots || [];
          if (!Array.isArray(roots)) throw new Error('The captured-root history is unavailable.');
          return roots.filter((entry) => entry.browser_identity && (entry.observed_material || entry.material_inspection_error))
            .map((entry) => ({identity:entry.browser_identity,material:entry.observed_material || null,error:entry.material_inspection_error || null}));
        }`});
      if (history.exceptionDetails || !Array.isArray(history.result?.value)) throw new Error('Retained closed-root history did not return a reliable result.');
      for (const entry of history.result.value) {
        if (entry.error) throw new Error(entry.error);
        if (entry.identity.frame_context?.id !== frameId) throw new Error('Retained closed-root history belongs to a different frame.');
        if (result.some((row) => row.frame_context.id === frameId && row.closed_root_backend_node_id === entry.identity.closed_root_backend_node_id)) continue;
        const material = entry.material, frame = frames.get(frameId), isMain = frameId === mainFrameId;
        if (!material?.material_observation || !frame) throw new Error('Retained closed-root material lost its observation or frame identity.');
        if (!isMain) { material.host_selector = null; material.host_description += ' in frame '+frame.url; }
        result.push({...material,...entry.identity,frame_context:{id:frameId,url:frame.url,is_main:isMain,document_url:material.document_url}});
      }
    }
    return result;
  } catch (error) {
    if (error?.source_harness_gap === true) throw error;
    const code = 'closed-shadow-root-discovery-unavailable';
    const reason = `Closed-shadow inspection is unavailable to the harness; an empty successful census cannot be inferred: ${String(error?.message || error)}`;
    throw Object.assign(new Error(reason), { code, source_harness_gap: true, frame_context:activeFrameContext,
      census_diagnostic:{schema_version:1,kind:'closed-shadow-inspection-incomplete',complete:false,profile:null,
        context:{phase:'closed-shadow-inventory'},failures:[{code,reason,frame_context:activeFrameContext,evidence:null}]}});
  } finally {
    for (const client of clients) { await client.send('Runtime.releaseObjectGroup', { objectGroup }).catch(() => {}); await client.detach().catch(() => {}); }
  }
}

async function trustedRuntimeGestureScripts(context) {
  if (!sourceRuntimeGestureScripts.has(context)) sourceRuntimeGestureScripts.set(context, (async () => {
    // Main-world locator.evaluate also injects Playwright's own interceptors.
    // Learn their exact bytes in an owned blank document, never from a source
    // site's labels, globals, URL, or claims about what its handlers do.
    const calibration = await context.newPage();
    let session;
    try {
      if (calibration.url() !== 'about:blank') throw new Error('Runtime gesture calibration requires an untouched blank document.');
      await calibration.locator('html').evaluate((element) => element.localName);
      await calibration.locator('html').hover();
      session = await context.newCDPSession(calibration);
      const ids = new Set(), hashes = new Set();
      for (const expression of ['document', 'window']) {
        const value = await session.send('Runtime.evaluate', { expression, returnByValue: false });
        if (!value.result?.objectId) throw new Error('Runtime gesture calibration could not inspect its own blank document.');
        const found = await session.send('DOMDebugger.getEventListeners', { objectId: value.result.objectId, depth: -1, pierce: true });
        for (const listener of found.listeners || []) {
          if (/^(?:drag|drop|touch|pointer)/.test(listener.type)) ids.add(listener.scriptId);
        }
      }
      await session.send('Debugger.enable');
      for (const scriptId of ids) {
        const { scriptSource } = await session.send('Debugger.getScriptSource', { scriptId });
        if (typeof scriptSource !== 'string' || !scriptSource) throw new Error('Runtime gesture calibration has no exact script bytes.');
        hashes.add(sha256Bytes(Buffer.from(scriptSource, 'utf8')));
      }
      return hashes;
    } finally { await session?.detach().catch(() => {}); await calibration.close().catch(() => {}); }
  })());
  return sourceRuntimeGestureScripts.get(context);
}

export async function discoverSourceGestureListeners(page) {
  let session;
  const objectGroup = `design-dna-gesture-discovery-${Date.now()}`;
  try {
    const runtimeScriptHashes = await trustedRuntimeGestureScripts(page.context());
    session = await page.context().newCDPSession(page);
    const contexts = new Map(), scriptContexts = new Map();
    session.on('Runtime.executionContextCreated', ({ context }) => contexts.set(context.id, context.auxData?.isDefault === true));
    session.on('Debugger.scriptParsed', (script) => scriptContexts.set(script.scriptId, script.executionContextId));
    await session.send('Runtime.enable');
    await session.send('Debugger.enable');
    const owners = new Map(), inspectedScriptHashes = new Map();
    for (const expression of ['document', 'window']) {
      const evaluated = await session.send('Runtime.evaluate', { expression, objectGroup, returnByValue: false });
      if (!evaluated.result?.objectId || evaluated.exceptionDetails) throw new Error(`Could not inspect ${expression} listeners.`);
      const found = await session.send('DOMDebugger.getEventListeners', { objectId: evaluated.result.objectId, depth: -1, pierce: true });
      for (const listener of found.listeners || []) {
        if (!/^(?:drag(?:start|end|enter|leave|over)?|drop|touch(?:start|move|end|cancel)|pointer(?:down|move|up|cancel))$/.test(listener.type)) continue;
        // DOMDebugger also sees Playwright's isolated utility-world pointer
        // interceptors. Only the browser's default document worlds describe
        // source code; never infer that boundary from a page-controlled label.
        const contextId = scriptContexts.get(listener.scriptId);
        if (!contexts.has(contextId)) throw new Error(`Gesture handler ${listener.scriptId} has no browser-verified execution context.`);
        if (contexts.get(contextId) !== true) continue;
        if (!inspectedScriptHashes.has(listener.scriptId)) {
          const { scriptSource } = await session.send('Debugger.getScriptSource', { scriptId: listener.scriptId });
          if (typeof scriptSource !== 'string') throw new Error(`Gesture handler ${listener.scriptId} has no inspectable script bytes.`);
          inspectedScriptHashes.set(listener.scriptId, sha256Bytes(Buffer.from(scriptSource, 'utf8')));
        }
        if (runtimeScriptHashes.has(inspectedScriptHashes.get(listener.scriptId))) continue;
        const key = listener.backendNodeId ? `node:${listener.backendNodeId}` : expression;
        if (!owners.has(key)) owners.set(key, { backend_node_id: listener.backendNodeId || null, scope: expression, listeners: [] });
        const owner = owners.get(key);
        const handlerText = listener.handler?.description || listener.originalHandler?.description || '';
        const directVisibleMutation = /\.style\.[a-zA-Z]+\s*=|\.style\.setProperty\s*\(|\.classList\.(?:add|remove|toggle|replace)\s*\(|\.(?:textContent|innerHTML|scrollTop|scrollLeft)\s*=/.test(handlerText);
        const fact = { type: listener.type, use_capture: listener.useCapture, passive: listener.passive, once: listener.once,
          script_id: listener.scriptId, line_number: listener.lineNumber, column_number: listener.columnNumber,
          handler_source_sha256: handlerText ? sha256Bytes(Buffer.from(handlerText, 'utf8')) : null,
          direct_visible_mutation_hook: directVisibleMutation };
        if (!owner.listeners.some((item) => JSON.stringify(item) === JSON.stringify(fact))) owner.listeners.push(fact);
      }
    }
    for (const owner of owners.values()) {
      if (!owner.backend_node_id) { owner.target = { selector: owner.scope, visible: true, node_type: 'global' }; continue; }
      const resolved = await session.send('DOM.resolveNode', { backendNodeId: owner.backend_node_id, objectGroup });
      if (!resolved.object?.objectId) throw new Error(`Registered gesture owner ${owner.backend_node_id} detached during discovery.`);
      const inspected = await session.send('Runtime.callFunctionOn', { objectId: resolved.object.objectId,
        returnByValue: true, functionDeclaration: `function () {
          if (this.nodeType !== 1) return {selector: this.nodeType === 9 ? 'document' : this.nodeName, visible: true, node_type: this.nodeType};
          const style = this.ownerDocument.defaultView.getComputedStyle(this), box = this.getBoundingClientRect();
          const parts = []; let node = this;
          while (node && node.nodeType === 1) {
            if (node.id) { parts.unshift('#' + CSS.escape(node.id)); break; }
            const siblings = node.parentElement ? [...node.parentElement.children].filter(item => item.tagName === node.tagName) : [];
            parts.unshift(node.tagName.toLowerCase() + (siblings.length > 1 ? ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')' : ''));
            const root = node.getRootNode(); node = node.parentElement || root.host || null;
          }
          return {selector: parts.join(' > '), tag: this.tagName.toLowerCase(), role: this.getAttribute('role'),
            text: (this.getAttribute('aria-label') || this.textContent || '').trim().replace(/\\s+/g, ' ').slice(0,200),
            visible: style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && box.width > 1 && box.height > 1,
            node_type: 1};
        }` });
      if (inspected.exceptionDetails || !inspected.result?.value) throw new Error(`Could not resolve registered gesture owner ${owner.backend_node_id}.`);
      owner.target = inspected.result.value;
    }
    const visibleCue = await page.evaluate(() => {
      const text = document.body?.innerText || '';
      return /\b(?:drag|drop|swipe|pinch|pan|slide)\s+(?:to|this|the|files|left|right|up|down)\b|\btouch-controlled\b/i.test(text);
    });
    for (const owner of owners.values()) {
      const targetCue = /\b(?:drag|drop|swipe|pinch|pan|slide)\s+(?:to|this|the|files|left|right|up|down)\b|\btouch-controlled\b/i.test(owner.target?.text || '');
      owner.material_signals = [];
      if (targetCue || ['window','document'].includes(owner.target?.selector) && visibleCue) owner.material_signals.push('gesture-specific-visible-cue');
      if (owner.listeners.some((listener) => listener.direct_visible_mutation_hook)) owner.material_signals.push('direct-visible-mutation-hook');
      owner.coverage_required = owner.material_signals.length > 0;
      owner.disposition = owner.coverage_required ? 'unverified-material-gesture' : 'unverified-code-hook-candidate';
    }
    return { complete: true, scope: 'listener-inventory-only', observed_gesture_behavior: false, owners: [...owners.values()], error: null };
  } catch (error) {
    return { complete: false, scope: 'listener-inventory-only', observed_gesture_behavior: false, owners: [], error: { code: 'gesture-listener-discovery-unavailable', reason: String(error?.message || error) } };
  } finally {
    if (session) {
      await session.send('Runtime.releaseObjectGroup', { objectGroup }).catch(() => {});
      await session.detach().catch(() => {});
    }
  }
}

function assignRepeatIndices(targets) {
  const repeatGroups = new Map();
  for (const target of targets) {
    if (!repeatGroups.has(target.repeat_class)) repeatGroups.set(target.repeat_class, []);
    repeatGroups.get(target.repeat_class).push(target);
  }
  for (const group of repeatGroups.values()) group.forEach((target, index) => {
    target.repeat_index = index + 1; target.repeat_count = group.length;
  });
  return repeatGroups;
}

export function mergeSourceGestureInventories(prior, next) {
  if (!prior) return next || null;
  if (!next) return prior;
  return { complete: prior.complete === true && next.complete === true,
    scope: 'listener-inventory-only', observed_gesture_behavior: false,
    owners: [...new Map([...(prior.owners || []), ...(next.owners || [])].map((owner) => [JSON.stringify(owner), owner])).values()],
    error: prior.error || next.error || null };
}

function targetObservationIdentity(target) {
  return [target.semantic_key, target.repeat_class, String(target.repeat_index)].join('\u0000');
}

function safePageUrl(page) {
  try { return normalizeHttpUrl(page.url()); } catch { return null; }
}

async function probeFailedCensusTarget(page, selector) {
  return page.evaluate((targetSelector) => {
    let matches = [];
    try { matches = [...document.querySelectorAll(targetSelector)]; }
    catch (error) { return { selector: targetSelector, selector_error: String(error?.message || error), matching_count: null }; }
    const describe = (element) => {
      if (!element) return null;
      const classes = String(element.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean).sort();
      const text = (element.getAttribute('aria-label') || element.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 200);
      return { tag: element.tagName.toLowerCase(), id: element.id || null,
        role: element.getAttribute('role') || element.tagName.toLowerCase(), classes, text,
        aria_hidden: element.getAttribute('aria-hidden'), aria_label: element.getAttribute('aria-label'),
        aria_disabled: element.getAttribute('aria-disabled'), aria_modal: element.getAttribute('aria-modal'),
        title: element.getAttribute('title'), data_ff_el: element.getAttribute('data-ff-el') };
    };
    const element = matches[0];
    if (!element) return { selector: targetSelector, matching_count: 0, target: null, hit_test: null };
    const style = getComputedStyle(element), rect = element.getBoundingClientRect();
    const visible = style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && rect.width > 1 && rect.height > 1;
    const composedAncestors = [];
    let ancestorCursor = element;
    while (ancestorCursor) {
      composedAncestors.push(ancestorCursor);
      const root = ancestorCursor.getRootNode?.();
      ancestorCursor = ancestorCursor.parentElement || root?.host || null;
    }
    const inertAncestor = composedAncestors.find((candidate) => candidate !== element &&
      (candidate.inert === true || candidate.hasAttribute?.('inert'))) || null;
    const ariaHiddenAncestor = composedAncestors.find((candidate) => candidate !== element &&
      candidate.getAttribute?.('aria-hidden') === 'true') || null;
    const point = { x: Math.max(0, Math.min(innerWidth - 1, rect.left + rect.width / 2)),
      y: Math.max(0, Math.min(innerHeight - 1, rect.top + rect.height / 2)) };
    const hit = visible ? document.elementFromPoint(point.x, point.y) : null;
    const hitsTarget = Boolean(hit && (hit === element || element.contains(hit)));
    const overlay = hit?.closest?.('[role="dialog"],[aria-modal="true"],[data-ff-el="modal"],[class*="modal" i],[class*="overlay" i]') || null;
    let focusBlocked = null;
    if (!hitsTarget && overlay && (inertAncestor || ariaHiddenAncestor)) {
      const priorFocus = document.activeElement;
      try {
        element.focus({ preventScroll: true });
        focusBlocked = document.activeElement !== element && !element.contains(document.activeElement);
      } catch { focusBlocked = true; }
      try { priorFocus?.focus?.({ preventScroll: true }); } catch { /* preserve the diagnostic only */ }
    }
    const overlayDescription = describe(overlay);
    if (overlayDescription) {
      const overlayStyle = getComputedStyle(overlay), overlayRect = overlay.getBoundingClientRect();
      overlayDescription.visible = overlayStyle.display !== 'none' && overlayStyle.visibility !== 'hidden'
        && Number(overlayStyle.opacity) > 0 && overlayRect.width > 1 && overlayRect.height > 1;
      overlayDescription.disabled = overlay.matches(':disabled,[aria-disabled="true"]');
      const overlayControls = [...overlay.querySelectorAll('button,[role="button"],a[href],input,select,textarea,summary,[tabindex]:not([tabindex="-1"])')]
        .map((candidate) => {
          const description = describe(candidate);
          const name = [description.aria_label, description.title, description.text].filter(Boolean).join(' ').trim();
          const closeSignal = candidate.getAttribute('data-ff-el') === 'modal-close'
            || /\b(close|dismiss|cancel|exit)\b/i.test(name);
          return { ...description, accessible_name: name || null, close_signal: closeSignal,
            safe_to_auto_dismiss: false };
        });
      overlayDescription.controls = overlayControls;
      overlayDescription.unnamed_controls = overlayControls.filter((candidate) => !candidate.accessible_name);
      overlayDescription.close_candidates = overlayControls.filter((candidate) => candidate.close_signal);
      overlayDescription.auto_dismissed = false;
    }
    return { selector: targetSelector, matching_count: matches.length,
      target: { ...describe(element), visible, disabled: element.matches(':disabled,[aria-disabled="true"]'),
        inert_ancestor: describe(inertAncestor), aria_hidden_ancestor: describe(ariaHiddenAncestor),
        focus_blocked: focusBlocked,
        rect: { left: Math.round(rect.left), top: Math.round(rect.top), width: Math.round(rect.width), height: Math.round(rect.height) } },
      hit_test: visible ? { point: { x: Math.round(point.x), y: Math.round(point.y) }, hits_target: hitsTarget,
        top: describe(hit), blocker: hitsTarget ? null : describe(hit),
        blocking_overlay: hitsTarget ? null : overlayDescription } : null };
  }, selector).catch((error) => ({ selector, probe_error: String(error?.message || error) }));
}

async function visibleModalControlNameProbe(page, selector) {
  return page.evaluate((targetSelector) => {
    let control;
    try { control = document.querySelector(targetSelector); }
    catch (error) { return { selector: targetSelector, selector_error: String(error?.message || error) }; }
    if (!control || !control.matches('button,[role="button"]')) return null;
    const modal = control.closest('[role="dialog"],[aria-modal="true"],[data-ff-el="modal"],[class*="modal" i],[class*="overlay" i]');
    if (!modal) return null;
    const modalStyle = getComputedStyle(modal), modalRect = modal.getBoundingClientRect();
    const visible = modalStyle.display !== 'none' && modalStyle.visibility !== 'hidden'
      && Number(modalStyle.opacity) > 0 && modalRect.width > 1 && modalRect.height > 1
      && modal.getAttribute('aria-hidden') !== 'true';
    if (!visible) return null;
    const labelledBy = String(control.getAttribute('aria-labelledby') || '').trim().split(/\s+/).filter(Boolean)
      .map((id) => document.getElementById(id)?.textContent || '').join(' ').trim();
    const accessibleName = (control.getAttribute('aria-label') || labelledBy || control.textContent || '').trim().replace(/\s+/g, ' ');
    const classes = String(control.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean).sort();
    return { selector: targetSelector, unnamed: !accessibleName, accessible_name: accessibleName || null,
      control: { tag: control.tagName.toLowerCase(), role: control.getAttribute('role') || control.tagName.toLowerCase(),
        classes, data_ff_el: control.getAttribute('data-ff-el'), aria_label: control.getAttribute('aria-label'),
        aria_labelledby: control.getAttribute('aria-labelledby') },
      modal: { tag: modal.tagName.toLowerCase(), role: modal.getAttribute('role') || null,
        aria_modal: modal.getAttribute('aria-modal'), data_ff_el: modal.getAttribute('data-ff-el') } };
  }, selector).catch((error) => ({ selector, probe_error: String(error?.message || error) }));
}

function interactionFailureCode(error, probe = null) {
  const text = String(error?.message || error || '').toLowerCase();
  if (probe?.hit_test?.hits_target === false || /intercepts pointer events|receives pointer events|subtree intercepts/.test(text)) return 'target-occluded';
  if (/not attached|detached/.test(text)) return 'target-detached';
  if (/strict mode violation|resolved to \d+ elements/.test(text)) return 'target-ambiguous';
  if (/not visible|not receive pointer events/.test(text)) return 'target-not-visible';
  if (/timeout/.test(text)) return 'interaction-timeout';
  if (/navigated without an exact url trigger|trigger navigated/.test(text)) return 'unexpected-navigation';
  if (/screenshot|visualsnapshot|snapshot/.test(text)) return 'evidence-capture-failed';
  return 'interaction-execution-failed';
}

function compactCensusContext(context = {}) {
  return {
    phase: typeof context.phase === 'string' ? context.phase : 'interaction-census',
    source_state_id: typeof context.source_state_id === 'string' ? context.source_state_id : null,
    pass: Number.isInteger(context.pass) && context.pass > 0 ? context.pass : null,
    route_key: typeof context.route_key === 'string' ? context.route_key : null,
  };
}

/** A failed census is diagnostic evidence only; it can never satisfy a gate. */
export function interactionCensusDiagnostic(census, context = {}) {
  const normalizedContext = compactCensusContext(context);
  const targets = new Map((census?.pages || []).flatMap((entry) => (entry.targets || [])
    .map((target) => [target.target_id, target])));
  const missing = Array.isArray(census?.missing) ? census.missing : [];
  return {
    schema_version: 1,
    kind: 'interaction-census-incomplete',
    complete: false,
    profile: census?.profile || null,
    context: normalizedContext,
    totals: {
      ...(census?.totals || {}),
      inputs_failed: missing.length,
      targets_with_failures: new Set(missing.map((item) => item?.target_id).filter(Boolean)).size,
    },
    failures: missing.map((item, index) => ({
      ordinal: index + 1,
      ...item,
      target: item?.target_id ? targets.get(item.target_id) || null : null,
    })),
  };
}

export function interactionCensusIncompleteError(census, context = {}) {
  const diagnostic = interactionCensusDiagnostic(census, context);
  const error = new Error(`${diagnostic.profile || 'unknown'} ${diagnostic.context.source_state_id || diagnostic.context.phase}: interaction census is incomplete (${diagnostic.failures.length} unresolved input${diagnostic.failures.length === 1 ? '' : 's'}).`);
  error.code = 'interaction-census-incomplete';
  error.census = census;
  error.census_context = diagnostic.context;
  error.census_diagnostic = diagnostic;
  return error;
}

/** A modal may make a background control unavailable only when the live DOM
 * proves it is both removed from the active accessibility path and unable to
 * receive focus. Mere visual occlusion remains a hard census failure. */
export function isProvenActiveModalBlock(probe) {
  const target = probe?.target || {};
  const hit = probe?.hit_test || {};
  const overlay = hit.blocking_overlay || {};
  const activeModal = overlay.visible === true && overlay.aria_hidden !== 'true'
    && overlay.aria_disabled !== 'true' && overlay.disabled !== true
    && (overlay.role === 'dialog' || overlay.aria_modal === 'true');
  const pointerExcluded = hit.hits_target === false && Boolean(hit.top || hit.blocker);
  const genuineInert = Boolean(target.inert_ancestor);
  return activeModal && genuineInert && target.focus_blocked === true && pointerExcluded;
}

async function freshBaselineTarget(page, target, options = {}) {
  const baselineState = options.baselineState || null;
  const baselineUrl = normalizeHttpUrl(baselineState?.url || options.pageUrl || page.url());
  const fresh = await page.context().newPage();
  try {
    const navigation = await navigateExact(fresh, baselineUrl);
    await fresh.evaluate(() => document.fonts?.ready).catch(() => {});
    await fresh.waitForTimeout(options.baselineSettleMs ?? 180);
    let application = null;
    if (baselineState && baselineState.trigger?.type !== 'none') {
      application = await applyManifestState(fresh, baselineState, { sourceOnly: options.sourceOnly === true });
    }
    const discovery = await discoverInteractionTargets(fresh);
    assignRepeatIndices(discovery.targets);
    const identity = targetObservationIdentity(target);
    const matches = discovery.targets.filter((candidate) => targetObservationIdentity(candidate) === identity);
    if (matches.length !== 1) {
      const error = new Error(`Fresh exact baseline could not resolve one live counterpart for ${target.semantic_key} (${matches.length} matches).`);
      error.code = 'baseline-target-unresolved';
      error.baseline = { requested_url: baselineUrl, navigation, state_id: baselineState?.id || null,
        state_applied: application?.applied === true, candidate_count: matches.length };
      throw error;
    }
    return { page: fresh, locator: fresh.locator(matches[0].selector), selector: matches[0].selector, baseline: {
      strategy: 'fresh-exact-state', requested_url: baselineUrl,
      final_url: navigation.final_normalized_url, state_id: baselineState?.id || null,
      state_applied: application?.applied === true, navigation,
    } };
  } catch (error) {
    await fresh.close().catch(() => {});
    throw error;
  }
}

export function needsFreshCensusBaseline(inputKind) {
  return new Set(['click', 'keyboard', 'open-close', 'media-play-pause', 'input', 'programmatic']).has(inputKind);
}

/** Uncapped target/input census for one exact page/profile. */
export async function captureInteractionCensus(page, options = {}) {
  const profile = options.profile || 'wide';
  const pageUrl = normalizeHttpUrl(options.pageUrl || page.url());
  const authoredStates = options.authoredStates || [];
  const capture = options.captureEvidence || (async () => null);
  const censusContext = compactCensusContext(options.context);
  const sourceOnly = options.sourceOnly === true;
  const plannedDeferredRoutes = options.plannedDeferredRoutes ?? [];
  if (!Array.isArray(plannedDeferredRoutes) || plannedDeferredRoutes.some((item) => typeof item !== 'string')) {
    throw new Error('plannedDeferredRoutes must contain exact normalized route URLs from the immutable build manifest.');
  }
  if (sourceOnly && plannedDeferredRoutes.length) {
    throw new Error('Public source studies cannot defer planned routes or borrow a first-screen build exception.');
  }
  const deferredRouteSet = new Set(plannedDeferredRoutes.map((item) => {
    const normalized = normalizeHttpUrl(item);
    if (normalized !== item || new URL(item).origin !== new URL(pageUrl).origin) {
      throw new Error('Each planned deferred route must be an exact normalized same-origin build URL.');
    }
    return normalized;
  }));
  const censusStartedAt = Date.now();
  const discovery = await discoverInteractionTargets(page);
  const discovered = discovery.targets;
  const repeatGroups = assignRepeatIndices(discovered);
  const targetRows = [], blocked = [], missing = [];
  const inputCount = { discovered: 0, exercised: 0, blocked: 0 };
  for (const closedRoot of await discoverUnaddressableClosedRoots(page)) {
    inputCount.discovered += 1; inputCount.blocked += 1;
    missing.push({ target_id: null, input_kind: 'closed-shadow-root',
      code: sourceOnly ? 'unsupported-source-closed-shadow-root' : 'unsupported-build-closed-shadow-root',
      reason: 'Visible material inside a closed shadow root is inaccessible to the exact locator/state protocol. This is a harness coverage gap, not a source-quality defect; no synthetic clicks or complete-coverage claim were substituted.',
      closed_shadow_root: closedRoot,
      evidence: { before: await capture('unaddressable-closed-shadow-root', page), after: null, settled: null } });
  }
  const gestureListeners = sourceOnly ? await discoverSourceGestureListeners(page) : null;
  if (gestureListeners && !gestureListeners.complete) missing.push({ target_id: null, input_kind: 'gesture-discovery',
    code: gestureListeners.error.code, reason: gestureListeners.error.reason });
  for (const owner of (gestureListeners?.owners || []).filter((item) => item.coverage_required)) {
    inputCount.discovered += 1; inputCount.blocked += 1;
    missing.push({ target_id: null, input_kind: 'gesture', code: 'unsupported-source-gesture',
      reason: `Registered ${[...new Set(owner.listeners.map(item => item.type))].join('/')} handlers on ${owner.target.selector} require exact gesture evidence; this runner will not guess a gesture or count hover/click as its substitute.`,
      gesture_owner: owner, evidence: { before: await capture('unsupported-gesture-listener', page), after: null, settled: null } });
  }
  const baselineState = options.baselineState
    || (censusContext.source_state_id ? authoredStates.find((state) => state.id === censusContext.source_state_id) : null)
    || authoredStates.find((state) => state.id === 'rest')
    || null;
  const baselineApplication = options.baselineApplication || options.stateApplication || null;
  const baselineEvidence = options.baselineEvidence || options.stateEvidence || null;
  for (const target of discovered) {
    const targetId = sha256Bytes(Buffer.from(`${pageUrl}\0${target.marker}\0${target.repeat_class}\0${target.text}`, 'utf8')).slice(0, 24);
    const locator = page.locator(target.selector);
    const sourceStates = [];
    for (const state of authoredStates) {
      if (normalizeHttpUrl(state.url || pageUrl) !== pageUrl || ['none','url','ambient'].includes(state.trigger?.type)) continue;
      try {
        const stateLocator = page.locator(state.trigger.target);
        if (await stateLocator.count() === 1 && await stateLocator.first().getAttribute('data-dna-interaction-id') === target.marker) sourceStates.push(state.id);
      } catch { /* invalid state target is separately rejected */ }
    }
    const inputs = [];
    if (target.gesture_signals.length) {
      inputCount.discovered += 1; inputCount.blocked += 1;
      const frame = await capture(`${targetId}-unsupported-gesture`, page);
      const row = { input_kind: 'gesture', input_value: null, status: 'blocked', safety: 'unsupported-input',
        source_state_id: null, before_sha256: null, after_sha256: null, settled_sha256: null,
        changed_properties: [], change_classification: { cosmetic: [], structural_semantic: [], diagnostic: [] },
        behavior: 'gesture candidate discovered; exact drag/touch sequence is not supported by this runner',
        evidence: { before: frame, after: null, settled: null }, disposition: 'blocked-unsupported-gesture' };
      inputs.push(row);
      missing.push({ target_id: targetId, input_kind: 'gesture', code: 'unsupported-source-gesture',
        reason: 'A discovered drag/touch/range affordance requires exact gesture evidence; pointer hover and click do not establish it.',
        gesture_signals: target.gesture_signals, evidence: row.evidence });
    }
    const modalName = await visibleModalControlNameProbe(page, target.selector);
    if (modalName?.unnamed) {
      const frame = await capture(`${targetId}-modal-control-accessible-name`, page);
      missing.push({ target_id: targetId, input_kind: 'accessible-name', input_value: null,
        source_state_id: null, context: censusContext, elapsed_ms_since_census_start: Date.now() - censusStartedAt,
        stage: 'modal-control-accessible-name', code: 'unlabeled-visible-modal-control',
        reason: 'A visible modal button/role=button has no aria-label, aria-labelledby text, or textual accessible name.',
        url_before: safePageUrl(page), url_after: safePageUrl(page), baseline: null,
        probe: modalName, evidence: { before: frame, after: frame, settled: frame } });
    }
    const exercise = async (inputKind, inputValue, action, sourceStateId = null) => {
      inputCount.discovered += 1;
      let safety;
      try { safety = await interactionTargetSafety(locator, inputKind, inputValue); }
      catch (error) {
        const probe = await probeFailedCensusTarget(page, target.selector);
        missing.push({ target_id: targetId, input_kind: inputKind, input_value: inputValue,
          source_state_id: sourceStateId, context: censusContext, elapsed_ms_since_census_start: Date.now() - censusStartedAt, stage: 'safety-classification',
          code: interactionFailureCode(error, probe), reason: String(error?.message || error),
          url_before: safePageUrl(page), url_after: safePageUrl(page), baseline: null, probe,
          evidence: { before: null, after: null, settled: null } });
        return;
      }
      if (!safety.safe) {
        const row = { input_kind: inputKind, input_value: inputValue, safety: 'blocked-side-effect', status: 'blocked',
          source_state_id: sourceStateId, before_sha256: null, after_sha256: null, settled_sha256: null,
          changed_properties: [], change_classification: { cosmetic: [], structural_semantic: [], diagnostic: [] },
          behavior: 'not observed because the input may change external or user state', evidence: null,
          disposition: 'blocked-requires-safe-owner-handoff' };
        inputs.push(row); blocked.push({ target_id: targetId, input_kind: inputKind, reason: safety.reason,
          handoff: 'Run only in an owner-authorized disposable/sandbox state and bind the resulting generated evidence.' });
        inputCount.blocked += 1; return;
      }
      let workingPage = page, workingLocator = locator, workingSelector = target.selector, isolated = null;
      let beforePageUrl = null, beforeFrame = null, afterFrame = null, settledFrame = null;
      let stage = 'baseline';
      try {
        if (needsFreshCensusBaseline(inputKind)) {
          isolated = await freshBaselineTarget(page, target, { pageUrl, baselineState, sourceOnly });
          workingPage = isolated.page; workingLocator = isolated.locator; workingSelector = isolated.selector;
        }
        stage = 'scroll-into-view';
        await workingLocator.scrollIntoViewIfNeeded();
        beforePageUrl = normalizeHttpUrl(workingPage.url());
        stage = 'evidence-before';
        beforeFrame = await capture(`${targetId}-${inputKind}-before`, workingPage);
        stage = 'snapshot-before';
        const before = await visualSnapshot(workingPage, workingSelector);
        stage = 'actionability-preflight';
        const actionability = await probeFailedCensusTarget(workingPage, workingSelector);
        if (actionability?.hit_test?.hits_target === false) {
          if (isProvenActiveModalBlock(actionability)) {
            stage = 'active-modal-evidence-after';
            afterFrame = await capture(`${targetId}-${inputKind}-active-modal-after`, workingPage);
            await workingPage.waitForTimeout(220);
            stage = 'active-modal-evidence-settled';
            settledFrame = await capture(`${targetId}-${inputKind}-active-modal-settled`, workingPage);
            inputs.push({ input_kind: inputKind, input_value: inputValue, safety: 'blocked-active-modal', status: 'blocked',
              source_state_id: sourceStateId, before_sha256: null, after_sha256: null, settled_sha256: null,
              changed_properties: [], change_classification: { cosmetic: [], structural_semantic: [], diagnostic: [] },
              behavior: 'not observed because a live active modal proved this background control inert or aria-hidden and focus-blocked',
              evidence: { before: beforeFrame, after: afterFrame, settled: settledFrame, active_modal: actionability },
              disposition: 'blocked-active-modal' });
            blocked.push({ target_id: targetId, input_kind: inputKind,
              reason: 'active modal blocks this background control with generated inert/aria-hidden and focus evidence',
              handoff: 'Do not dismiss or bypass the modal. Preserve this state evidence and verify the modal controls independently.',
              disposition: 'blocked-active-modal', active_modal: actionability });
            inputCount.blocked += 1;
            return;
          }
          const error = new Error('Live target is occluded at its center point; the census will not force, dismiss, or bypass the blocker.');
          error.code = 'target-occluded';
          error.probe = actionability;
          throw error;
        }
        stage = 'input-dispatch';
        await action(workingLocator, workingPage);
        stage = 'url-verification';
        if (normalizeHttpUrl(workingPage.url()) !== beforePageUrl) throw new Error('interaction navigated without an exact URL trigger/navigation binding');
        stage = 'snapshot-after';
        await workingPage.waitForTimeout(80);
        const after = await visualSnapshot(workingPage, workingSelector);
        stage = 'evidence-after';
        afterFrame = await capture(`${targetId}-${inputKind}-after`, workingPage);
        stage = 'snapshot-settled';
        await workingPage.waitForTimeout(220);
        const settled = await visualSnapshot(workingPage, workingSelector);
        stage = 'evidence-settled';
        settledFrame = await capture(`${targetId}-${inputKind}-settled`, workingPage);
        const changes = changedVisualProperties(before, settled);
        const classification = classifyVisualChanges(changes, diagnosticVisualChanges(before, settled));
        inputs.push({ input_kind: inputKind, input_value: inputValue, safety: 'safe', status: 'exercised',
          source_state_id: sourceStateId, before_sha256: before.sha256, after_sha256: after.sha256,
          settled_sha256: settled.sha256, changed_properties: changes,
          change_classification: classification,
          behavior: changes.length ? `changed ${[...new Set(changes.map((item) => item.property))].join(', ')}` : 'no visible computed-style/geometry change',
          evidence: { before: beforeFrame, after: afterFrame, settled: settledFrame,
            baseline: isolated?.baseline || { strategy: 'shared-page-nonmutating', requested_url: beforePageUrl,
              final_url: beforePageUrl, state_id: baselineState?.id || null, state_applied: null } },
          disposition: changes.length ? 'sourceable-observed-behavior' : 'observed-quiet' });
        inputCount.exercised += 1;
      } catch (error) {
        const probe = error?.probe || await probeFailedCensusTarget(workingPage, workingSelector);
        missing.push({ target_id: targetId, input_kind: inputKind, input_value: inputValue,
          source_state_id: sourceStateId, context: censusContext, elapsed_ms_since_census_start: Date.now() - censusStartedAt, stage,
          code: error?.code || interactionFailureCode(error, probe), reason: String(error?.message || error),
          url_before: beforePageUrl, url_after: safePageUrl(workingPage),
          baseline: isolated?.baseline || { strategy: 'shared-page-nonmutating', requested_url: beforePageUrl,
            final_url: beforePageUrl, state_id: baselineState?.id || null, state_applied: null },
          probe, evidence: { before: beforeFrame, after: afterFrame, settled: settledFrame } });
      } finally { if (isolated) await isolated.page.close().catch(() => {}); }
    };
    if (target.hoverable) await exercise('hover', null, async (item) => { await item.hover({ timeout: 5000 }); });
    if (target.focusable) await exercise('focus', null, async (item) => { await item.focus({ timeout: 5000 }); });
    if (target.focusable) await exercise('focus-traversal', 'Tab', async (item, actionPage) => {
      await item.focus({ timeout: 5000 }); await actionPage.keyboard.press('Tab');
    });
    if (target.kind === 'control' && (target.tag === 'button' || target.role === 'button')) {
      await exercise('keyboard', 'Enter', async (item, actionPage) => {
        await item.focus({ timeout: 5000 }); await actionPage.keyboard.press('Enter');
      });
      await exercise('keyboard', 'Space', async (item, actionPage) => {
        await item.focus({ timeout: 5000 }); await actionPage.keyboard.press('Space');
      });
    }
    if (target.kind === 'control' && (target.tag === 'button' || target.role === 'button')) await exercise('click', null,
      async (item) => { await item.click({ timeout: 5000 }); });
    if (target.kind === 'open-close') {
      const exactOpenTarget = (item) => target.tag === 'details' ? item.locator('summary').first() : item;
      await exercise('keyboard', 'Enter', async (item, actionPage) => {
        const openTarget = exactOpenTarget(item);
        if (await openTarget.count() !== 1) throw new Error('open-close target no longer resolves to exactly one control.');
        await openTarget.focus({ timeout: 5000 }); await actionPage.keyboard.press('Enter');
      });
      await exercise('keyboard', 'Space', async (item, actionPage) => {
        const openTarget = exactOpenTarget(item);
        if (await openTarget.count() !== 1) throw new Error('open-close target no longer resolves to exactly one control.');
        await openTarget.focus({ timeout: 5000 }); await actionPage.keyboard.press('Space');
      });
      await exercise('open-close', 'open then close', async (item, actionPage) => {
        const openTarget = exactOpenTarget(item);
        if (await openTarget.count() !== 1) throw new Error('open-close target no longer resolves to exactly one control.');
        await openTarget.click({ timeout: 5000 }); await actionPage.waitForTimeout(120); await openTarget.click({ timeout: 5000 });
      });
    }
    if (target.kind === 'media') await exercise('media-play-pause', null, async (item) => {
      await item.evaluate(async (media) => { await media.play(); await new Promise((resolve) => setTimeout(resolve, 180)); media.pause(); });
    });
    if (target.kind === 'input-control' && !sourceStates.some((id) => authoredStates.find((state) => state.id === id)?.trigger.type === 'input')) {
      inputCount.discovered += 1; inputCount.blocked += 1;
      inputs.push({ input_kind: 'input', input_value: null, safety: 'blocked-side-effect', status: 'blocked', source_state_id: null,
        before_sha256: null, after_sha256: null, settled_sha256: null, changed_properties: [],
        change_classification: { cosmetic: [], structural_semantic: [], diagnostic: [] },
        behavior: 'no value invented; input requires an authored disposable fixture', evidence: null,
        disposition: 'blocked-requires-safe-owner-handoff' });
      blocked.push({ target_id: targetId, input_kind: 'input', reason: 'no authorized non-personal fixture value',
        handoff: 'Provide an explicit source-state input fixture and run it in a disposable session.' });
    }
    for (const stateId of sourceStates) {
      const state = authoredStates.find((item) => item.id === stateId);
      if (!state || ['hover','focus','ambient'].includes(state.trigger.type)) continue;
      await exercise(state.trigger.type, state.trigger.value, async (_item, actionPage) => {
        // Exact state execution is owned by applyManifestState so URL changes,
        // programmatic drivers, and side-effect policy remain fail closed.
        await applyManifestState(actionPage, state, { sourceOnly });
      }, stateId);
    }
    if (target.kind === 'route-link') {
      inputCount.discovered += 1; inputCount.blocked += 1;
      inputs.push({ input_kind: 'click', input_value: target.text, safety: 'blocked-side-effect', status: 'blocked',
        source_state_id: null, before_sha256: null, after_sha256: null, settled_sha256: null, changed_properties: [],
        change_classification: { cosmetic: [], structural_semantic: [], diagnostic: [] },
        behavior: 'link click not used; the exact route is traversed by safe GET navigation', evidence: null,
        disposition: 'blocked-requires-safe-owner-handoff' });
      blocked.push({ target_id: targetId, input_kind: 'click', reason: 'link may navigate or mutate session state',
        handoff: 'Use the observer exact-navigation ledger for the destination; click only in an authorized disposable session.' });
    }
    if (target.kind === 'route-link') {
      inputCount.discovered += 1;
      let href = null;
      try { href = normalizeHttpUrl(target.href); } catch { /* non-http target */ }
      if (href && deferredRouteSet.has(href)) {
        inputs.push({ input_kind: 'navigation', input_value: href, safety: 'blocked-planned-route', status: 'blocked',
          decision_id: await locator.getAttribute('data-design-dna-decision-id'),
          source_state_id: null, before_sha256: null, after_sha256: null, settled_sha256: null, changed_properties: [],
          change_classification: { cosmetic: [], structural_semantic: [], diagnostic: [] },
          behavior: 'The immutable first-screen build plan binds this future route; arrival remains unverified until the final gate.',
          evidence: null, disposition: 'deferred-until-final-gate' });
        blocked.push({ target_id: targetId, input_kind: 'navigation', input_value: href,
          reason: 'Exact planned route is outside the active first-screen proof scope.',
          disposition: 'deferred-until-final-gate', handoff: 'The final gate must navigate this route and verify its complete source-bound body.' });
        inputCount.blocked += 1;
      } else if (href && new URL(href).origin === new URL(pageUrl).origin) {
        const navigationState = authoredStates.find((state) => state.trigger?.type === 'url' &&
          normalizeHttpUrl(new URL(state.trigger.target, pageUrl).href) === href);
        if (navigationState && !sourceStates.includes(navigationState.id)) sourceStates.push(navigationState.id);
        let verificationPage = null;
        try {
          const beforeFrame = await capture(`${targetId}-navigation-before`, page);
          const before = await visualSnapshot(page, target.selector);
          verificationPage = await page.context().newPage();
          const navigation = await navigateExact(verificationPage, href);
          const after = await visualSnapshot(verificationPage);
          const afterFrame = await capture(`${targetId}-navigation-after`, verificationPage);
          await verificationPage.waitForTimeout(220);
          const settled = await visualSnapshot(verificationPage);
          const settledFrame = await capture(`${targetId}-navigation-settled`, verificationPage);
          const changes = changedVisualProperties(before, settled);
          const classification = classifyVisualChanges(changes, diagnosticVisualChanges(before, settled));
          inputs.push({ input_kind: 'navigation', input_value: href, safety: 'safe', status: 'exercised',
            source_state_id: navigationState?.id || null, before_sha256: before.sha256, after_sha256: after.sha256,
            settled_sha256: settled.sha256, changed_properties: changes,
            change_classification: classification,
            behavior: `exact 2xx route arrival at ${navigation.final_normalized_url}`,
            evidence: { before: beforeFrame, after: afterFrame, settled: settledFrame, navigation },
            disposition: 'sourceable-observed-behavior' });
          inputCount.exercised += 1;
        } catch (error) { missing.push({ target_id: targetId, input_kind: 'navigation', reason: String(error).slice(0, 240) }); }
        finally { if (verificationPage) await verificationPage.close().catch(() => {}); }
      } else {
        inputs.push({ input_kind: 'navigation', input_value: target.href, safety: 'blocked-side-effect', status: 'blocked',
          source_state_id: null, before_sha256: null, after_sha256: null, settled_sha256: null, changed_properties: [],
          change_classification: { cosmetic: [], structural_semantic: [], diagnostic: [] },
          behavior: 'external/non-HTTP destination is outside same-origin source traversal', evidence: null,
          disposition: 'blocked-requires-safe-owner-handoff' });
        blocked.push({ target_id: targetId, input_kind: 'navigation', reason: 'external or non-HTTP destination',
          handoff: 'Review only with explicit authority in a separate safe session.' }); inputCount.blocked += 1;
      }
    }
    targetRows.push({ target_id: targetId, page_url: pageUrl, selector: target.selector, source_selector: target.source_selector, tag: target.tag, role: target.role,
      text: target.text, semantic_key: target.semantic_key,
      class_signature: target.class_signature, repeat_class: target.repeat_class, repeat_index: target.repeat_index,
      repeat_count: target.repeat_count, kind: target.kind, semantic_state: target.semantic_state,
      source_state_ids: sourceStates, inputs });
  }

  const repeatClasses = [...repeatGroups.entries()].map(([repeatClass, members]) => {
    const rows = targetRows.filter((row) => row.repeat_class === repeatClass);
    const kinds = [...new Set(rows.flatMap((row) => row.inputs.filter((input) => input.status === 'exercised')
      .map((input) => `${input.input_kind}:${input.behavior}`)))].sort();
    const inputKinds = [...new Set(rows.flatMap((row) => row.inputs.map((input) => input.input_kind)))].sort();
    const equivalent = inputKinds.every((inputKind) => new Set(rows.flatMap((row) => row.inputs
      .filter((input) => input.input_kind === inputKind && input.status === 'exercised').map((input) => input.behavior))).size <= 1);
    return { repeat_class: repeatClass, target_ids: rows.map((row) => row.target_id), input_kinds: [...new Set(rows.flatMap((row) => row.inputs.map((input) => input.input_kind)))].sort(),
      equivalent: members.length < 2 || equivalent,
      behavior_signatures: kinds, evidence: rows.flatMap((row) => row.inputs.map((input) => input.evidence).filter(Boolean)) };
  }).sort((a, b) => a.repeat_class.localeCompare(b.repeat_class));

  const pointerFollow = [];
  try {
    const viewport = page.viewportSize() || { width: 1440, height: 900 };
    const points = [{ x: Math.round(viewport.width * .15), y: Math.round(viewport.height * .25) },
      { x: Math.round(viewport.width * .85), y: Math.round(viewport.height * .72) }];
    await page.mouse.move(points[0].x, points[0].y); await page.waitForTimeout(160);
    const beforeFrame = await capture('pointer-follow-before'), before = await visualSnapshot(page);
    await page.mouse.move(points[1].x, points[1].y, { steps: 16 }); await page.waitForTimeout(180);
    const afterFrame = await capture('pointer-follow-after'), after = await visualSnapshot(page);
    await page.mouse.move(points[0].x, points[0].y, { steps: 16 }); await page.waitForTimeout(180);
    const settledFrame = await capture('pointer-follow-return'), returned = await visualSnapshot(page);
    const start = new Map(before.rows.map((row) => [row.key, row])), finish = new Map(returned.rows.map((row) => [row.key, row]));
    for (const middle of after.rows) {
      const first = start.get(middle.key), last = finish.get(middle.key); if (!first || !last) continue;
      const dx = middle.properties.left - first.properties.left, dy = middle.properties.top - first.properties.top;
      const moved = Math.hypot(dx, dy), returnError = Math.hypot(last.properties.left - first.properties.left, last.properties.top - first.properties.top);
      const pdx = points[1].x - points[0].x, pdy = points[1].y - points[0].y, plen = Math.hypot(pdx, pdy);
      const correlation = moved ? (dx * pdx + dy * pdy) / (moved * plen) : -1;
      if (moved > 8 && returnError <= Math.max(8, moved * .3) && correlation > .45 &&
          !first.properties.hovered && !middle.properties.hovered && !last.properties.hovered) {
        pointerFollow.push({ target_id: sha256Bytes(Buffer.from(`${pageUrl}\0${middle.key}`, 'utf8')).slice(0, 24), page_url: pageUrl,
          component_key: middle.key, moved_px: Math.round(moved), return_error_px: Math.round(returnError),
          pointer_correlation: Number(correlation.toFixed(2)), distinct_from_hover: true,
          evidence: { before: beforeFrame, after: afterFrame, settled: settledFrame } });
      }
    }
  } catch (error) { missing.push({ target_id: 'page-cursor-field', input_kind: 'pointer-follow', reason: String(error).slice(0, 240) }); }

  const activeAmbientState = baselineState?.trigger?.type === 'ambient' ? baselineState : null;
  const authoredStateIds = new Set(authoredStates.filter((state) => state.trigger?.type !== 'ambient' || state.id === activeAmbientState?.id)
    .map((state) => state.id));
  const boundStateIds = new Set(targetRows.flatMap((row) => row.source_state_ids));
  const pageStates = [];
  for (const state of authoredStates.filter((item) => ['none','url','programmatic'].includes(item.trigger.type) || item.id === activeAmbientState?.id)) {
    let triggerEvidence = null, evidence = null, disposition = 'covered-by-state-ledger';
    if (state.trigger.type === 'ambient') {
      const supplied = baselineApplication;
      if (supplied?.state_id !== state.id || supplied?.trigger_evidence?.type !== 'ambient' ||
          !baselineEvidence || !baselineEvidence.before || !baselineEvidence.after || !baselineEvidence.settled) {
        missing.push({ target_id: null, input_kind: 'page-state', input_value: null, source_state_id: state.id,
          context: censusContext, elapsed_ms_since_census_start: Date.now() - censusStartedAt,
          stage: 'ambient-page-state-ledger', code: 'ambient-ledger-missing',
          reason: `ambient source state ${state.id} requires one supplied generated before/appearance/settled application ledger; it must not be redispatched from a discovered target.`,
          url_before: safePageUrl(page), url_after: safePageUrl(page), baseline: null, probe: null,
          evidence: { before: null, after: null, settled: null } });
        continue;
      }
      triggerEvidence = { before_sha256: supplied.trigger_evidence.before_sha256,
        after_sha256: supplied.trigger_evidence.after_sha256,
        settled_sha256: supplied.trigger_evidence.settled_sha256,
        changed_properties: supplied.trigger_evidence.changed_properties,
        change_classification: supplied.trigger_evidence.change_classification,
        behavior: `ambient appearance observed after ${supplied.trigger_evidence.appeared_after_ms}ms` };
      evidence = baselineEvidence;
    } else if (state.trigger.type === 'none') {
      const before = await visualSnapshot(page), beforeFrame = await capture(`${state.id}-page-state-before`, page);
      const afterFrame = await capture(`${state.id}-page-state-after`, page), settledFrame = await capture(`${state.id}-page-state-settled`, page);
      triggerEvidence = { before_sha256: before.sha256, after_sha256: before.sha256, settled_sha256: before.sha256,
        changed_properties: [], change_classification: { cosmetic: [], structural_semantic: [], diagnostic: [] },
        behavior: 'settled rest state' };
      evidence = { before: beforeFrame, after: afterFrame, settled: settledFrame }; disposition = 'observed-rest';
    } else {
      const boundInput = targetRows.flatMap((row) => row.inputs).find((input) => input.source_state_id === state.id && input.status === 'exercised');
      if (boundInput) {
        triggerEvidence = { before_sha256: boundInput.before_sha256, after_sha256: boundInput.after_sha256,
          settled_sha256: boundInput.settled_sha256, changed_properties: boundInput.changed_properties,
          change_classification: boundInput.change_classification,
          behavior: boundInput.behavior };
        evidence = boundInput.evidence;
      } else if (state.trigger.type === 'url') {
        let verificationPage = null;
        try {
          const before = await visualSnapshot(page), beforeFrame = await capture(`${state.id}-page-state-before`, page);
          verificationPage = await page.context().newPage();
          const navigation = await navigateExact(verificationPage, new URL(state.trigger.target, pageUrl).href);
          const after = await visualSnapshot(verificationPage), afterFrame = await capture(`${state.id}-page-state-after`, verificationPage);
          await verificationPage.waitForTimeout(220);
          const settled = await visualSnapshot(verificationPage), settledFrame = await capture(`${state.id}-page-state-settled`, verificationPage);
          const changes = changedVisualProperties(before, settled);
          triggerEvidence = { before_sha256: before.sha256, after_sha256: after.sha256, settled_sha256: settled.sha256,
            changed_properties: changes,
            change_classification: classifyVisualChanges(changes, diagnosticVisualChanges(before, settled)),
            behavior: `exact 2xx route arrival at ${navigation.final_normalized_url}` };
          evidence = { before: beforeFrame, after: afterFrame, settled: settledFrame, navigation };
        } catch (error) { missing.push({ target_id: null, input_kind: 'page-state', reason: String(error).slice(0, 240) }); }
        finally { if (verificationPage) await verificationPage.close().catch(() => {}); }
      } else {
        missing.push({ target_id: null, input_kind: 'page-state', reason: `source state ${state.id} lacks generated before/after/settled evidence` });
      }
    }
    pageStates.push({ source_state_id: state.id, kind: state.kind, trigger: state.trigger,
      page_url: normalizeHttpUrl(state.url), disposition, trigger_evidence: triggerEvidence, evidence });
  }
  pageStates.forEach((row) => boundStateIds.add(row.source_state_id));
  const reconciliation = interactionReconciliationGaps({ domTargetIds: targetRows.map((row) => row.target_id),
    liveTargetIds: targetRows.filter((row) => row.inputs.length).map((row) => row.target_id),
    authoredStateIds: [...authoredStateIds], boundStateIds: [...boundStateIds] });
  for (const stateId of reconciliation.states) missing.push({ target_id: null, input_kind: 'authored-state', reason: `source state ${stateId} is not bound to a target or page-state ledger` });
  const targetIdByMarker = new Map(targetRows.map((row, index) => [discovered[index]?.marker, row.target_id]));
  const domCodeInventory = {
    routes_discovered: discovery.dom_code_inventory.routes,
    controls_discovered: targetRows.map((row) => row.target_id),
    state_hooks: discovery.dom_code_inventory.state_hooks.map((hook) => ({ target_id: targetIdByMarker.get(hook.marker) || null, attributes: hook.attributes })),
    animation_hooks: discovery.dom_code_inventory.animation_hooks.map((hook) => {
      const { marker, ...evidence } = hook; return { target_id: targetIdByMarker.get(marker) || null, ...evidence };
    }),
    assets: discovery.dom_code_inventory.assets, scripts: discovery.dom_code_inventory.scripts,
    gesture_listeners: gestureListeners,
    inline_handlers: discovery.dom_code_inventory.inline_handlers.map((hook) => ({ target_id: targetIdByMarker.get(hook.marker) || null,
      attribute: hook.attribute, code_length: hook.code_length })),
    live_target_ids: targetRows.map((row) => row.target_id),
    live_source_state_ids: [...boundStateIds].sort(),
    unreconciled_controls: reconciliation.controls,
  };
  domCodeInventory.complete = domCodeInventory.unreconciled_controls.length === 0 &&
    domCodeInventory.controls_discovered.length === domCodeInventory.live_target_ids.length;
  if (!domCodeInventory.complete) missing.push({ target_id: null, input_kind: 'dom-code-reconciliation', reason: 'DOM/code inventory has controls absent from live interaction evidence' });
  return { profile, pages: [{ url: pageUrl, targets: targetRows, dom_code_inventory: domCodeInventory }], page_states: pageStates,
    repeat_classes: repeatClasses, pointer_follow: pointerFollow, blocked_side_effects: blocked,
    totals: { targets_discovered: targetRows.length, inputs_discovered: inputCount.discovered,
      inputs_exercised: inputCount.exercised, inputs_blocked: inputCount.blocked },
    truncated: false, missing, complete: missing.length === 0 };
}

/** Objective rendered QA for one exact page/profile. Issues remain evidence;
 * they are never converted into generic praise or silently waived. */
export function sourceControlRequiresDisclosureSemantics(target) {
  // Native route arrival replaces DOM nodes while retaining link semantics.
  // This exemption requires generated exercised navigation evidence.
  if (target.kind === 'route-link' && target.tag === 'a' && (target.inputs || []).some((input) =>
    input.input_kind === 'navigation' && input.status === 'exercised')) return false;
  const stateful = target.kind === 'open-close' || (target.inputs || []).some((input) =>
    (input.change_classification?.structural_semantic || []).some((change) =>
      ['aria_expanded','aria_pressed','presence','display','visibility'].includes(change.property)));
  const semantic = target.semantic_state || {};
  return stateful && semantic.aria_expanded === null && semantic.aria_pressed === null && semantic.aria_controls === null;
}

export async function captureRenderedQA(page, options = {}) {
  const profile = options.profile || 'wide';
  const pageUrl = normalizeHttpUrl(options.pageUrl || page.url());
  const interactionCensus = options.interactionCensus || { pages: [] };
  const sourceState = options.sourceState || null;
  const capture = options.captureEvidence || (async () => null);
  const missing = [];
  const restEvidence = await capture('rendered-qa-rest', page);
  const geometry = await page.evaluate((authoredState) => {
    const roots = [document];
    for (let index = 0; index < roots.length; index += 1) roots[index].querySelectorAll('*').forEach((element) => { if (element.shadowRoot) roots.push(element.shadowRoot); });
    const all = roots.flatMap((root) => [...root.querySelectorAll('*')]);
    const interactiveSelector = 'a[href],button,input,select,textarea,summary,[role="button"],[role="tab"],[role="menuitem"],[role="switch"],[role="checkbox"],[role="radio"],[tabindex]';
    const textOf = (element) => (element.getAttribute('aria-label') || element.textContent || '')
      .trim().replace(/\s+/g, ' ').slice(0, 200);
    const semanticKey = (element) => {
      const role = element.getAttribute('role') || element.tagName.toLowerCase();
      return `${role.toLowerCase()}|${textOf(element).toLowerCase()}`;
    };
    const key = (element) => element.getAttribute('data-dna-interaction-id') ?
      `[data-dna-interaction-id="${element.getAttribute('data-dna-interaction-id')}"]` :
      element.id ? `#${CSS.escape(element.id)}` : `${element.tagName.toLowerCase()}.${String(element.className || '').trim().replace(/\s+/g,'.')}`;
    const visible = [], hiddenControls = [];
    for (const element of all) {
      const style = element.ownerDocument.defaultView.getComputedStyle(element), rect = element.getBoundingClientRect();
      const isInteractive = element.matches(interactiveSelector);
      const isVisible = style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && rect.width > 1 && rect.height > 1;
      if (isInteractive && !isVisible) hiddenControls.push({ selector: key(element), tag: element.tagName.toLowerCase(),
        role: element.getAttribute('role') || element.tagName.toLowerCase(), text: textOf(element),
        semantic_key: semanticKey(element), aria_hidden: element.getAttribute('aria-hidden'),
        focusable_while_hidden: element.tabIndex >= 0 && !element.matches(':disabled') && !element.closest('[inert]') });
      if (!isVisible || rect.bottom <= 0 || rect.top >= innerHeight) continue;
      if (isInteractive || element.matches('h1,h2,h3,p,img,video,[role="dialog"],dialog,[aria-modal="true"]')) {
        visible.push({ element, selector: key(element), tag: element.tagName.toLowerCase(),
          role: element.getAttribute('role') || element.tagName.toLowerCase(), text: textOf(element),
          semantic_key: semanticKey(element),
          rect: { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height },
          position: style.position, z_index: style.zIndex, overflow_x: style.overflowX, overflow_y: style.overflowY });
      }
    }
    const clipping = visible.filter((item) => item.rect.left < -1 || item.rect.right > innerWidth + 1)
      .map(({ element, ...item }) => ({ ...item, viewport_width: innerWidth }));
    const overlaySelector = 'dialog,[role="dialog"],[aria-modal],[aria-hidden],[class*="menu-panel" i],[class*="overlay" i],[class*="drawer" i]';
    const activeOverlayElements = all.filter((element) => {
      if (!element.matches(overlaySelector) || !element.querySelector(interactiveSelector) || element.getAttribute('aria-hidden') === 'true') return false;
      const style = getComputedStyle(element), rect = element.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && rect.width > 1 && rect.height > 1;
    });
    const crossesActiveOverlayBoundary = (first, second) => activeOverlayElements.some((overlay) =>
      (overlay.contains(first) && !overlay.contains(second)) || (overlay.contains(second) && !overlay.contains(first)));
    const collisions = [];
    for (let left = 0; left < visible.length; left += 1) for (let right = left + 1; right < visible.length; right += 1) {
      const a = visible[left], b = visible[right];
      if (a.element.contains(b.element) || b.element.contains(a.element)) continue;
      if (crossesActiveOverlayBoundary(a.element, b.element)) continue;
      const width = Math.max(0, Math.min(a.rect.right, b.rect.right) - Math.max(a.rect.left, b.rect.left));
      const height = Math.max(0, Math.min(a.rect.bottom, b.rect.bottom) - Math.max(a.rect.top, b.rect.top));
      const area = width * height, smaller = Math.min(a.rect.width * a.rect.height, b.rect.width * b.rect.height);
      if (smaller > 0 && area / smaller >= .2) collisions.push({ first: a.selector, second: b.selector, overlap_ratio: Number((area / smaller).toFixed(3)) });
    }
    const rails = visible.filter((item) => ['fixed','sticky'].includes(item.position));
    const fixedRailOverlaps = [];
    for (const rail of rails) for (const item of visible) {
      if (rail === item || rail.element.contains(item.element) || item.element.contains(rail.element)) continue;
      if (crossesActiveOverlayBoundary(rail.element, item.element)) continue;
      const width = Math.max(0, Math.min(rail.rect.right, item.rect.right) - Math.max(rail.rect.left, item.rect.left));
      const height = Math.max(0, Math.min(rail.rect.bottom, item.rect.bottom) - Math.max(rail.rect.top, item.rect.top));
      if (width * height > 64) fixedRailOverlaps.push({ rail: rail.selector, obscured: item.selector, overlap_px2: Math.round(width * height) });
    }
    const overlays = all.filter((element) => element.matches(overlaySelector) && element.querySelector(interactiveSelector)).map((element, index) => {
      element.setAttribute('data-design-dna-source-qa-overlay', String(index + 1));
      const style = getComputedStyle(element), rect = element.getBoundingClientRect();
      const visibleNow = style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && rect.width > 1 && rect.height > 1;
      const closed = !visibleNow || element.getAttribute('aria-hidden') === 'true';
      const active = element.ownerDocument.activeElement;
      const backgroundControls = all.filter((candidate) => {
        if (!candidate.matches(interactiveSelector) || candidate === element || element.contains(candidate) || candidate.contains(element)) return false;
        const candidateStyle = getComputedStyle(candidate), candidateRect = candidate.getBoundingClientRect();
        return candidateStyle.display !== 'none' && candidateStyle.visibility !== 'hidden' && Number(candidateStyle.opacity) > 0 &&
          candidateRect.width > 1 && candidateRect.height > 1;
      });
      backgroundControls.forEach((candidate, controlIndex) =>
        candidate.setAttribute('data-design-dna-source-qa-background', `${index + 1}-${controlIndex + 1}`));
      // aria-hidden only changes the accessibility tree. It is not proof that
      // a pointer or keyboard user cannot still operate the background.
      const backgroundInert = closed || backgroundControls.every((candidate) =>
        candidate.closest('[inert]') || candidate.matches(':disabled') || candidate.tabIndex < 0);
      const descendants = [...element.querySelectorAll(interactiveSelector)];
      descendants.forEach((candidate, descendantIndex) =>
        candidate.setAttribute('data-design-dna-source-qa-descendant', `${index + 1}-${descendantIndex + 1}`));
      const closedDescendantsInert = !closed || descendants.every((candidate) =>
        (() => { const candidateStyle = getComputedStyle(candidate), candidateRect = candidate.getBoundingClientRect();
          const removedFromRendering = candidateStyle.display === 'none' || candidateStyle.visibility === 'hidden' ||
            Number(candidateStyle.opacity) <= 0 || candidateRect.width <= 1 || candidateRect.height <= 1;
          return candidate.closest('[inert]') || candidate.matches(':disabled') || candidate.tabIndex < 0 || removedFromRendering;
        })());
      const samplePoints = closed ? [] : [
        [.5, .5], [.1, .08], [.5, .08], [.9, .08], [.1, .5], [.9, .5], [.1, .92], [.5, .92], [.9, .92],
      ].map(([x, y]) => ({ x: Math.max(0, Math.min(innerWidth - 1, rect.left + rect.width * x)),
        y: Math.max(0, Math.min(innerHeight - 1, rect.top + rect.height * y)) }));
      const hitTests = samplePoints.map((point) => {
        const stack = document.elementsFromPoint(point.x, point.y);
        const overlayIndex = stack.findIndex((candidate) => candidate === element || element.contains(candidate));
        const backgroundControlAbove = overlayIndex < 0 || stack.slice(0, overlayIndex).some((candidate) =>
          candidate.matches?.(interactiveSelector) && !element.contains(candidate));
        return { ...point, top: stack[0] ? key(stack[0]) : null, overlay_hit: overlayIndex >= 0,
          background_control_above: backgroundControlAbove };
      });
      let openerSelector = null;
      if (element.id) {
        const candidate = all.find((item) => item.getAttribute('aria-controls') === element.id);
        if (candidate) openerSelector = key(candidate);
        else if (authoredState?.trigger?.target && ['click','keyboard','programmatic'].includes(authoredState.trigger.type))
          openerSelector = authoredState.trigger.target;
      } else if (authoredState?.trigger?.target && ['click','keyboard','programmatic'].includes(authoredState.trigger.type)) {
        openerSelector = authoredState.trigger.target;
      }
      return { selector: `[data-design-dna-source-qa-overlay="${index + 1}"]`, key: key(element),
        open: !closed, aria_modal: element.getAttribute('aria-modal'),
        initial_focus_inside: closed || Boolean(active && element.contains(active)),
        inert_background: backgroundInert, closed_descendants_inert: closedDescendantsInert,
        stacking_above_background_controls: closed || hitTests.every((test) => test.overlay_hit && !test.background_control_above),
        focusable_count: descendants.filter((candidate) => candidate.tabIndex >= 0 && !candidate.matches(':disabled')).length,
        background_control_selectors: backgroundControls.map((_candidate, controlIndex) =>
          `[data-design-dna-source-qa-background="${index + 1}-${controlIndex + 1}"]`),
        descendant_selectors: descendants.map((_candidate, descendantIndex) =>
          `[data-design-dna-source-qa-descendant="${index + 1}-${descendantIndex + 1}"]`),
        opener_selector: openerSelector, hit_tests: hitTests };
    });
    let stateSemantics = { required: false, complete: true, target: null, attributes: null };
    if (authoredState?.trigger && ['click','keyboard','programmatic'].includes(authoredState.trigger.type)) {
      let stateTargets = [];
      try { stateTargets = all.filter((element) => element.matches(authoredState.trigger.target)); } catch { stateTargets = []; }
      if (stateTargets.length === 1) {
        const target = stateTargets[0];
        const attributes = { aria_expanded: target.getAttribute('aria-expanded'), aria_pressed: target.getAttribute('aria-pressed'),
          aria_selected: target.getAttribute('aria-selected'), aria_checked: target.getAttribute('aria-checked'),
          aria_controls: target.getAttribute('aria-controls') };
        const controlled = attributes.aria_controls ? document.getElementById(attributes.aria_controls) : null;
        const stateful = Boolean(controlled || overlays.some((overlay) => overlay.opener_selector === authoredState.trigger.target) ||
          target.closest('details') || ['tab','switch','checkbox','radio'].includes(target.getAttribute('role')));
        const semanticValue = [attributes.aria_expanded, attributes.aria_pressed, attributes.aria_selected,
          attributes.aria_checked].find((value) => value !== null);
        const controlledVisible = controlled ? (() => { const controlledStyle = getComputedStyle(controlled), box = controlled.getBoundingClientRect();
          return controlledStyle.display !== 'none' && controlledStyle.visibility !== 'hidden' && Number(controlledStyle.opacity) > 0 && box.width > 1 && box.height > 1; })() : null;
        const controlledMatches = !controlled || attributes.aria_expanded === null || attributes.aria_expanded === String(controlledVisible);
        stateSemantics = { required: stateful, complete: !stateful || (semanticValue !== undefined && controlledMatches),
          target: key(target), attributes, controlled_visible: controlledVisible };
      } else {
        stateSemantics = { required: true, complete: false, target: authoredState.trigger.target, attributes: null };
      }
    }
    const controlVisibility = all.filter((element) => element.matches(interactiveSelector)).map((element) => {
      const style = getComputedStyle(element), rect = element.getBoundingClientRect();
      return { selector: key(element), semantic_key: semanticKey(element), text: textOf(element),
        role: element.getAttribute('role') || element.tagName.toLowerCase(), tag: element.tagName.toLowerCase(),
        visible: style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && rect.width > 1 && rect.height > 1,
        focusable: element.tabIndex >= 0 && !element.matches(':disabled') && !element.closest('[inert]'),
        aria_hidden: element.getAttribute('aria-hidden') };
    });
    return { clipping, collisions, fixed_rail_overlaps: fixedRailOverlaps,
      hidden_controls: hiddenControls, overlays,
      control_visibility: controlVisibility, state_semantics: stateSemantics,
      document_width: document.documentElement.scrollWidth, viewport_width: innerWidth };
  }, sourceState);
  const targets = (interactionCensus.pages || []).flatMap((entry) => entry.targets || []);
  const deadControls = targets.filter((target) => {
    const observed = (target.inputs || []).filter((input) => input.status === 'exercised');
    return observed.length > 0 && observed.every((input) => input.disposition === 'observed-quiet');
  }).map((target) => ({ target_id: target.target_id, selector: target.selector, page_url: target.page_url }));
  const semanticIssues = targets.filter(sourceControlRequiresDisclosureSemantics).map((target) => ({ target_id: target.target_id, selector: target.selector,
    issue: 'visible state changes without aria-expanded/aria-pressed/aria-controls' }));
  const keyboardPaths = targets.map((target) => {
    const inputs = (target.inputs || []).filter((input) => input.input_kind === 'focus' || input.input_kind === 'keyboard')
      .map((input) => ({ input_kind: input.input_kind, status: input.status, behavior: input.behavior, evidence: input.evidence }));
    return { target_id: target.target_id, inputs,
      complete: inputs.some((input) => input.status === 'exercised' && input.evidence) };
  });
  const keyboardMissing = keyboardPaths.filter((path) => !path.complete).map((path) => path.target_id);
  const semanticMismatches = (interactionCensus.repeat_classes || [])
    .filter((row) => row.equivalent !== true).map((row) => row.repeat_class);
  const overlayResults = [];
  for (const overlay of geometry.overlays) {
    try {
      const locator = page.locator(overlay.selector);
      const before = await capture(`rendered-qa-overlay-${overlay.key}-before`, page);
      if (!overlay.open) {
        let closedFocusBlocked = true;
        for (const selector of overlay.descendant_selectors) {
          const descendant = page.locator(selector);
          await descendant.evaluate((element) => element.focus()).catch(() => {});
          const capturedFocus = await descendant.evaluate((element) => element === element.ownerDocument.activeElement ||
            element.contains(element.ownerDocument.activeElement)).catch(() => false);
          if (capturedFocus) closedFocusBlocked = false;
        }
        const after = await capture(`rendered-qa-overlay-${overlay.key}-closed-after`, page);
        const closedComplete = overlay.closed_descendants_inert && closedFocusBlocked;
        overlayResults.push({ ...overlay, closed_descendants_inert: closedComplete,
          initial_focus: true, background_focus_blocked: true,
          focus_trap: true, focus_return: true,
          escape_closes: true, evidence: { before, after, settled: after },
          complete: closedComplete });
        continue;
      }
      const focusable = locator.locator('a[href],button,input,select,textarea,summary,[tabindex]:not([tabindex="-1"])');
      const focusableCount = await focusable.count();
      let backgroundFocusBlocked = true;
      for (const selector of overlay.background_control_selectors) {
        const background = page.locator(selector);
        await background.evaluate((element) => element.focus()).catch(() => {});
        const capturedFocus = await background.evaluate((element) => element === element.ownerDocument.activeElement ||
          element.contains(element.ownerDocument.activeElement)).catch(() => false);
        if (capturedFocus) backgroundFocusBlocked = false;
      }
      let focusTrap = focusableCount > 0;
      for (let index = 0; index <= focusableCount && focusTrap; index += 1) {
        await page.keyboard.press('Tab'); await page.waitForTimeout(40);
        focusTrap = await locator.evaluate((element) => element.contains(element.ownerDocument.activeElement)).catch(() => false);
      }
      if (focusTrap) {
        await page.keyboard.press('Shift+Tab'); await page.waitForTimeout(40);
        focusTrap = await locator.evaluate((element) => element.contains(element.ownerDocument.activeElement)).catch(() => false);
      }
      await page.keyboard.press('Escape'); await page.waitForTimeout(160);
      const remainsOpen = await locator.evaluate((element) => {
        const style = getComputedStyle(element), rect = element.getBoundingClientRect();
        return element.getAttribute('aria-hidden') !== 'true' && style.display !== 'none' && style.visibility !== 'hidden' &&
          Number(style.opacity) > 0 && rect.width > 1 && rect.height > 1;
      }).catch(() => false);
      let focusReturn = false;
      if (!remainsOpen && overlay.opener_selector) {
        focusReturn = await page.locator(overlay.opener_selector).evaluateAll((targets) => targets.length === 1 &&
          (targets[0] === targets[0].ownerDocument.activeElement || targets[0].contains(targets[0].ownerDocument.activeElement))).catch(() => false);
      }
      const after = await capture(`rendered-qa-overlay-${overlay.key}-after`, page);
      await page.waitForTimeout(220);
      const settled = await capture(`rendered-qa-overlay-${overlay.key}-settled`, page);
      const complete = overlay.initial_focus_inside && overlay.inert_background && overlay.closed_descendants_inert &&
        overlay.stacking_above_background_controls && backgroundFocusBlocked && focusTrap && !remainsOpen && focusReturn;
      overlayResults.push({ ...overlay, initial_focus: overlay.initial_focus_inside, focusable_count: focusableCount,
        background_focus_blocked: backgroundFocusBlocked, focus_trap: focusTrap,
        focus_return: focusReturn, escape_closes: !remainsOpen,
        evidence: { before, after, settled }, complete });
    } catch (error) { missing.push({ kind: 'overlay-focus', selector: overlay.selector, reason: String(error).slice(0, 240) }); }
  }
  let deepLink = null, reload = null, reducedMotion = null;
  let verificationPage = null;
  try {
    verificationPage = await page.context().newPage();
    const firstNavigation = await navigateExact(verificationPage, pageUrl);
    const deepFrame = await capture('rendered-qa-deep-link', verificationPage);
    deepLink = { navigation: firstNavigation, evidence: deepFrame, complete: true };
    const firstReloadFrame = await capture('rendered-qa-reload-before', verificationPage);
    const reloadNavigation = await navigateExact(verificationPage, pageUrl);
    const secondReloadFrame = await capture('rendered-qa-reload-after', verificationPage);
    reload = { navigation: reloadNavigation, before: firstReloadFrame, after: secondReloadFrame,
      stable_pixels: firstReloadFrame?.sha256 === secondReloadFrame?.sha256, complete: true };
    await verificationPage.emulateMedia({ reducedMotion: 'reduce' });
    const reducedNavigation = await navigateExact(verificationPage, pageUrl);
    await verificationPage.waitForTimeout(300);
    const animations = await verificationPage.evaluate(() => document.getAnimations().map((animation) => ({
      play_state: animation.playState, iterations: animation.effect?.getComputedTiming?.().iterations,
      duration: animation.effect?.getComputedTiming?.().duration,
    })));
    const reducedFrame = await capture('rendered-qa-reduced-motion', verificationPage);
    reducedMotion = { navigation: reducedNavigation, animations, evidence: reducedFrame,
      honors_preference: animations.every((animation) => animation.play_state !== 'running'), complete: true };
  } catch (error) { missing.push({ kind: 'navigation-preference', reason: String(error).slice(0, 240) }); }
  finally { if (verificationPage) await verificationPage.close().catch(() => {}); }
  const routes = await collectSameOriginLinks(page, new URL(pageUrl).origin);
  const terminalSignal = await page.evaluate(() => /\b(thank|success|complete|confirmed|receipt|done)\b/i.test(document.body?.innerText || ''));
  const pageRecord = { url: pageUrl, evidence: restEvidence, clipping: geometry.clipping,
    collisions: geometry.collisions, fixed_rail_overlaps: geometry.fixed_rail_overlaps,
    hidden_controls: geometry.hidden_controls, control_visibility: geometry.control_visibility,
    dead_controls: deadControls,
    semantic_issues: semanticIssues, overlays: overlayResults, keyboard_paths: keyboardPaths,
    keyboard: { complete: keyboardMissing.length === 0, missing: keyboardMissing },
    semantic_equivalence: { complete: semanticMismatches.length === 0, mismatches: semanticMismatches },
    state_semantics: geometry.state_semantics,
    reduced_motion: reducedMotion, deep_link: deepLink, reload,
    dead_end: { same_origin_destinations: routes, is_dead_end: routes.length === 0,
      terminal_signal: terminalSignal, problem: routes.length === 0 && !terminalSignal } };
  const issueCount = geometry.clipping.length + geometry.collisions.length + geometry.fixed_rail_overlaps.length +
    geometry.hidden_controls.filter((item) => item.focusable_while_hidden).length + deadControls.length + semanticIssues.length +
    overlayResults.filter((item) => !item.complete).length + (geometry.state_semantics.complete ? 0 : 1) +
    keyboardMissing.length + semanticMismatches.length + (reducedMotion?.honors_preference ? 0 : 1) +
    (pageRecord.dead_end.problem ? 1 : 0);
  return { profile, pages: [pageRecord], totals: { pages: 1, issues: issueCount,
    controls: targets.length, overlays: overlayResults.length }, truncated: false,
    missing, complete: missing.length === 0 };
}

function uniqueEvidenceRows(values) {
  return [...new Map(values.filter((value) => value !== undefined).map((value) => [canonicalJson(value), value])).values()];
}

/** Merge repeated page/state QA without allowing a later state to erase an
 * earlier defect. The public shape remains one page row per canonical URL;
 * its inventories are the union of every observed state at that URL. */
export function mergeSourceRenderedQA(profile, records) {
  const groups = new Map();
  for (const record of records) for (const page of record?.pages || []) {
    if (!groups.has(page.url)) groups.set(page.url, []);
    groups.get(page.url).push(page);
  }
  const pages = [...groups.entries()].map(([url, states]) => {
    const first = states[0];
    const arrayFields = ['clipping','collisions','fixed_rail_overlaps','hidden_controls','control_visibility',
      'dead_controls','semantic_issues','overlays'];
    const merged = { ...first, url };
    for (const field of arrayFields) merged[field] = uniqueEvidenceRows(states.flatMap((state) => state[field] || []));
    const keyboardByTarget = new Map();
    for (const row of states.flatMap((state) => state.keyboard_paths || [])) {
      const existing = keyboardByTarget.get(row.target_id) || { target_id: row.target_id, inputs: [], complete: false };
      existing.inputs = uniqueEvidenceRows([...existing.inputs, ...(row.inputs || [])]);
      existing.complete = existing.complete || row.complete === true ||
        existing.inputs.some((input) => input.status === 'exercised' && input.evidence);
      keyboardByTarget.set(row.target_id, existing);
    }
    merged.keyboard_paths = [...keyboardByTarget.values()].sort((a, b) => String(a.target_id).localeCompare(String(b.target_id)));
    const keyboardMissing = uniqueEvidenceRows(states.flatMap((state) => state.keyboard?.missing || []));
    merged.keyboard = { complete: states.every((state) => state.keyboard?.complete === true) && keyboardMissing.length === 0,
      missing: keyboardMissing };
    const semanticMismatches = uniqueEvidenceRows(states.flatMap((state) => state.semantic_equivalence?.mismatches || []));
    merged.semantic_equivalence = { complete: states.every((state) => state.semantic_equivalence?.complete === true) && semanticMismatches.length === 0,
      mismatches: semanticMismatches };
    merged.state_semantics = states.find((state) => state.state_semantics?.complete === false)?.state_semantics ||
      states.find((state) => state.state_semantics?.required === true)?.state_semantics || first.state_semantics;
    merged.reduced_motion = states.find((state) => state.reduced_motion?.honors_preference !== true)?.reduced_motion || first.reduced_motion;
    merged.deep_link = states.find((state) => state.deep_link?.complete !== true)?.deep_link || first.deep_link;
    merged.reload = states.find((state) => state.reload?.complete !== true)?.reload || first.reload;
    merged.dead_end = states.find((state) => state.dead_end?.problem === true)?.dead_end || first.dead_end;
    return merged;
  }).sort((a, b) => a.url.localeCompare(b.url));
  const missing = records.flatMap((record) => record?.missing || []);
  const issueCount = pages.reduce((sum, page) => sum + ['clipping','collisions','fixed_rail_overlaps','dead_controls','semantic_issues']
    .reduce((count, field) => count + (page[field]?.length || 0), 0) +
    (page.hidden_controls || []).filter((control) => control.focusable_while_hidden).length +
    (page.overlays || []).filter((overlay) => !overlay.complete).length +
    (page.state_semantics?.complete === false ? 1 : 0) + (page.keyboard?.complete === false ? 1 : 0) +
    (page.semantic_equivalence?.complete === false ? 1 : 0) +
    (page.reduced_motion?.honors_preference === true ? 0 : 1) + (page.dead_end?.problem === true ? 1 : 0), 0);
  return { profile, pages, totals: { pages: pages.length, issues: issueCount,
    controls: pages.reduce((sum, page) => sum + new Set((page.control_visibility || [])
      .map((control) => `${control.selector}|${control.semantic_key}`)).size, 0),
    overlays: pages.reduce((sum, page) => sum + (page.overlays?.length || 0), 0) },
    truncated: false, missing,
    complete: missing.length === 0 && records.every((record) => record?.complete === true && record?.truncated === false) };
}

/*
 * Identify every native overflow surface plus explicit/clipped transform
 * surfaces. The page receives only inert data attributes so later samples can
 * address the exact same element.
 */
export async function discoverScrollSurfaces(page) {
  return page.evaluate(() => {
    window.__dnaScrollSurface = window.__dnaScrollSurface || 0;
    const result = [{ id: "document", kind: "document", axis: "y", required: true }];
    const selectors = "body *";
    for (const element of document.querySelectorAll(selectors)) {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      if (rect.width < 20 || rect.height < 20 || style.display === "none" || style.visibility === "hidden") continue;
      const nativeY = element.scrollHeight > element.clientHeight + 2 && /(auto|scroll|overlay)/.test(style.overflowY);
      const nativeX = element.scrollWidth > element.clientWidth + 2 && /(auto|scroll|overlay)/.test(style.overflowX);
      // "scroll-trigger" and data-scroll sections usually describe reveal
      // targets, not containers that consume wheel input. Treat only exact
      // container signals as required transform surfaces; broader transformed
      // and clipped candidates remain heuristic until wheel causality is
      // measured below.
      const classTokens = [...element.classList].map((token) => token.toLowerCase());
      const explicit = element.hasAttribute('data-scroll-container') || element.hasAttribute('data-lenis') ||
        classTokens.some((token) => /^(?:scroll-container|scroll-wrapper|smooth-scroll(?:-container)?|locomotive-scroll|lenis|horizontal-scroll|vertical-scroll)$/.test(token));
      const transformed = style.transform !== "none";
      const parentStyle = element.parentElement ? getComputedStyle(element.parentElement) : null;
      const clipped = parentStyle && /(hidden|clip|auto|scroll)/.test(`${parentStyle.overflow} ${parentStyle.overflowX} ${parentStyle.overflowY}`);
      const overflowGeometry = element.scrollHeight > element.clientHeight + 2 || element.scrollWidth > element.clientWidth + 2 ||
        rect.width > innerWidth * 1.05 || rect.height > innerHeight * 1.05;
      const transformCandidate = (explicit || (transformed && clipped)) && overflowGeometry;
      if (!nativeY && !nativeX && !transformCandidate) continue;
      if (!element.dataset.dnaScrollSurface) element.dataset.dnaScrollSurface = String(++window.__dnaScrollSurface);
      result.push({
        id: element.dataset.dnaScrollSurface,
        kind: nativeY || nativeX ? "native" : "transform",
        axis: nativeY ? "y" : nativeX ? "x" : "wheel",
        required: Boolean(nativeY || nativeX || explicit),
        discovery_basis: nativeY || nativeX ? 'native-overflow' : explicit ? 'explicit-transform-container' : 'transformed-clipped-overflow',
        selector_hint: `${element.tagName.toLowerCase()}.${typeof element.className === "string" ? element.className.trim().slice(0, 60) : ""}`,
      });
    }
    return result;
  });
}

async function resetSurface(page, surface) {
  await page.evaluate((item) => {
    if (item.id === "document") { window.scrollTo(0, 0); return; }
    const element = document.querySelector(`[data-dna-scroll-surface="${CSS.escape(item.id)}"]`);
    if (element) element.scrollIntoView({ block: "center", inline: "center", behavior: "instant" });
    if (element && item.kind === "native") element.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, surface);
}

async function surfaceSample(page, surface) {
  return page.evaluate((item) => {
    const element = item.id === "document" ? document.scrollingElement :
      document.querySelector(`[data-dna-scroll-surface="${CSS.escape(item.id)}"]`);
    if (!element) return null;
    const rect = item.id === "document" ? { left: 0, top: 0, width: innerWidth, height: innerHeight } : element.getBoundingClientRect();
    const descendants = item.id === "document" ? [...document.body.children] : [...element.children];
    const geometry = descendants.slice(0, 32).map((child) => {
      const box = child.getBoundingClientRect(), style = getComputedStyle(child);
      return [Math.round(box.left), Math.round(box.top), Math.round(box.width), Math.round(box.height), style.transform];
    });
    return {
      x: Math.round(element.scrollLeft || window.scrollX), y: Math.round(element.scrollTop || window.scrollY),
      max_x: Math.max(0, Math.round(element.scrollWidth - element.clientWidth)),
      max_y: Math.max(0, Math.round(element.scrollHeight - element.clientHeight)),
      rect: { left: rect.left, top: rect.top, width: rect.width, height: rect.height },
      fingerprint: JSON.stringify(geometry),
    };
  }, surface);
}

function surfaceSampleChanged(before, after) {
  return Boolean(before && after &&
    (after.x !== before.x || after.y !== before.y || after.fingerprint !== before.fingerprint));
}

/** Drive every discovered scroll surface to its terminal state with real wheel input. */
export async function traverseScrollSurfaces(page, options = {}) {
  const surfaces = await discoverScrollSurfaces(page);
  const records = [];
  const deadline = options.deadline || (() => false);
  const maxTicks = options.maxTicks || 240;
  const settleMs = options.settleMs ?? 180;
  for (const surface of surfaces) {
    await resetSurface(page, surface);
    await page.waitForTimeout(Math.min(settleMs, 100));
    let before = await surfaceSample(page, surface);
    if (!before) {
      records.push({ ...surface, complete: false, reason: "surface-disappeared", ticks: 0, progressed: false });
      continue;
    }
    // A clipped transform can be a carousel/virtual scroller, but it can also
    // be a marquee that moves forever without wheel input. Prove that a broad
    // heuristic candidate is quiet before spending the traversal budget on
    // it. Autonomous motion remains captured by the mechanism observer; it is
    // not misrepresented as an independent scroll surface.
    if (surface.kind === "transform" && !surface.required) {
      await page.waitForTimeout(Math.min(Math.max(settleMs, 80), 250));
      const passive = await surfaceSample(page, surface);
      if (!passive) {
        records.push({ ...surface, complete: false, reason: "surface-disappeared", ticks: 0, progressed: false });
        continue;
      }
      if (surfaceSampleChanged(before, passive)) {
        records.push({ ...surface, ticks: 0, progressed: false, terminal: true, complete: true,
          reason: null, disposition: "autonomous-transform-not-scroll-surface", autonomous_motion_observed: true,
          final: { x: passive.x, y: passive.y, max_x: passive.max_x, max_y: passive.max_y } });
        continue;
      }
      before = passive;
    }
    let noProgress = 0;
    let progressed = false;
    let terminal = false;
    let ticks = 0;
    while (ticks < maxTicks && !deadline()) {
      const x = Math.max(2, Math.min((page.viewportSize()?.width || 1440) - 2, before.rect.left + before.rect.width / 2));
      const y = Math.max(2, Math.min((page.viewportSize()?.height || 900) - 2, before.rect.top + before.rect.height / 2));
      await page.mouse.move(x, y);
      const delta = Math.max(500, Math.round((page.viewportSize()?.height || 900) * 0.72));
      await page.mouse.wheel(surface.axis === "x" ? delta : 0, surface.axis === "x" ? 0 : delta);
      await page.waitForTimeout(settleMs);
      ticks += 1;
      const after = await surfaceSample(page, surface);
      if (!after) break;
      const changed = surfaceSampleChanged(before, after);
      if (changed) { progressed = true; noProgress = 0; } else noProgress += 1;
      if (options.onTick) await options.onTick(surface, ticks, after, changed);
      const atNativeEnd = surface.kind !== "transform" &&
        (surface.axis === "x" ? after.x >= after.max_x : after.y >= after.max_y);
      if ((atNativeEnd && noProgress >= 1) || (surface.kind === "transform" && progressed && noProgress >= 4) ||
          (!surface.required && !progressed && noProgress >= 4)) {
        terminal = true;
        before = after;
        break;
      }
      before = after;
    }
    const complete = terminal && !deadline() && (!surface.required || progressed ||
      (surface.kind !== "transform" && before.max_x === 0 && before.max_y === 0));
    records.push({ ...surface, ticks, progressed, terminal, complete,
      reason: complete ? null : deadline() ? "time-budget-ended" : ticks >= maxTicks ? "tick-cap-before-terminal" : "no-wheel-progress",
      final: before ? { x: before.x, y: before.y, max_x: before.max_x, max_y: before.max_y } : null });
  }
  return { surfaces: records, complete: records.every((record) => record.complete) };
}

/** Capture actual response bodies while the page loads; URL-only lists are not evidence. */
export function createResourceByteCollector(page) {
  let sequence = 0;
  const pending = [];
  const listener = (response) => {
    const seq = sequence++;
    pending.push((async () => {
      const request = response.request();
      try {
        await response.finished();
        const body = await response.body();
        return { seq, requested_url: request.url(), response_url: response.url(), method: request.method(),
          resource_type: request.resourceType(), status: response.status(), bytes: body.length,
          body_sha256: sha256Bytes(body), body, error: null };
      } catch (error) {
        return { seq, requested_url: request.url(), response_url: response.url(), method: request.method(),
          resource_type: request.resourceType(), status: response.status(), bytes: null,
          body_sha256: null, body: null, error: String(error).slice(0, 240) };
      }
    })());
  };
  page.on("response", listener);
  return {
    async finish() {
      page.off("response", listener);
      const raw = await Promise.all(pending);
      const failures = raw.filter((entry) => entry.error);
      const digest = createHash("sha256");
      for (const entry of raw.sort((a, b) => a.seq - b.seq)) {
        digest.update(Buffer.from(`${entry.seq}\0${entry.status}\0${entry.response_url}\0${entry.bytes ?? -1}\0`, "utf8"));
        if (entry.body) digest.update(entry.body);
      }
      return {
        complete: failures.length === 0,
        response_count: raw.length,
        failed_response_count: failures.length,
        body_set_sha256: digest.digest("hex"),
        resources: raw.map(({ body, ...entry }) => entry),
      };
    },
  };
}

/* Compatibility surface used by build/style producers. The capture is based
 * on Playwright Response.body(), never performance entry names or a refetch. */
export async function installDomInspection(context) {
  await context.addInitScript(() => {
    const roots = [];
    Object.defineProperty(window, "__designDnaCapturedShadowRoots", { value: roots, configurable: false });
    const original = Element.prototype.attachShadow;
    Object.defineProperty(Element.prototype, "attachShadow", {
      configurable: true,
      writable: true,
      value(init) {
        const root = original.call(this, init);
        roots.push({ host: this, root, mode: init?.mode || "open" });
        return root;
      },
    });
    Object.defineProperty(window, "__designDnaDomInspection", {
      value: "response-bodies-v1", configurable: false, enumerable: false, writable: false,
    });
  });
}

export function beginServedContentCapture(page, requestedUrl) {
  const requested = normalizeHttpUrl(requestedUrl);
  let sequence = 0;
  let explicitFinal = null;
  const pending = [];
  const listener = (response) => {
    const seq = sequence++;
    pending.push((async () => {
      const request = response.request();
      const isDocument = request.isNavigationRequest() && request.frame() === page.mainFrame();
      try {
        await response.finished();
        const body = await response.body();
        return { seq, url: response.url(), requested_url: request.url(), status: response.status(),
          resource_type: request.resourceType(), document: isDocument, bytes: body.length,
          sha256: sha256Bytes(body), body, error: null };
      } catch (error) {
        return { seq, url: response.url(), requested_url: request.url(), status: response.status(),
          resource_type: request.resourceType(), document: isDocument, bytes: null,
          sha256: null, body: null, error: String(error).slice(0, 240) };
      }
    })());
  };
  page.on("response", listener);
  return {
    setFinalResponse(value) { explicitFinal = value || null; },
    async finish(extra = {}) {
      page.off("response", listener);
      const responses = (await Promise.all(pending)).sort((a, b) => a.seq - b.seq);
      const failed = responses.filter((entry) => entry.error);
      if (failed.length) {
        const error = new Error(`Unreadable response bodies: ${failed.map((item) => `${item.url} (${item.error})`).join("; ")}`);
        error.code = "response-body-unreadable";
        error.responses = failed.map(({ body, ...item }) => item);
        throw error;
      }
      const finalUrl = normalizeHttpUrl(
        explicitFinal?.final_normalized_url || explicitFinal?.url?.() || explicitFinal?.url || page.url()
      );
      const status = Number(explicitFinal?.final_status ?? explicitFinal?.status?.() ?? explicitFinal?.status);
      const documents = responses.filter((entry) => entry.document && normalizeHttpUrl(entry.url) === finalUrl);
      const document = documents.at(-1);
      if (!document) throw navigationError("document-body-missing", `${requested}: the final document response body was not captured.`);
      if (!(status >= 200 && status <= 299) || document.status !== status) {
        throw navigationError("document-status-mismatch", `${requested}: navigation status ${status} did not match captured document status ${document.status}.`);
      }
      const resources = responses.filter((entry) => entry !== document).map(({ body, seq, requested_url, resource_type, document: isDocument, error, ...item }) => item)
        .sort((a, b) => a.url.localeCompare(b.url) || a.status - b.status || a.sha256.localeCompare(b.sha256) || a.bytes - b.bytes);
      const byteDigest = createHash("sha256");
      for (const entry of responses) {
        byteDigest.update(Buffer.from(`${entry.seq}\0${entry.status}\0${entry.url}\0${entry.bytes}\0`, "utf8"));
        byteDigest.update(entry.body);
      }
      const core = {
        requested_url: requested,
        final_url: finalUrl,
        status,
        document_sha256: document.sha256,
        resources,
      };
      return { ...extra, ...core, document_bytes: document.bytes,
        response_body_set_sha256: byteDigest.digest("hex"),
        sha256: sha256Bytes(Buffer.from(canonicalJson(core), "utf8")) };
    },
  };
}

export function aggregateServedContent(probes) {
  if (!Array.isArray(probes) || !probes.length) throw new Error("At least one served-content probe is required.");
  for (const probe of probes) {
    if (!probe || !probe.requested_url || !probe.final_url || !Number.isInteger(probe.status) ||
        !/^[0-9a-f]{64}$/.test(probe.document_sha256 || "") || !/^[0-9a-f]{64}$/.test(probe.sha256 || "") ||
        !Array.isArray(probe.resources) || probe.resources.some((resource) =>
          !/^[0-9a-f]{64}$/.test(resource.sha256 || "") || !Number.isInteger(resource.bytes))) {
      throw new Error("Every served-content probe must bind final status and actual document/resource response bytes.");
    }
  }
  const groups = new Map();
  for (const probe of probes) {
    const key = `${probe.route_key || probe.requested_url}\0${probe.viewport || "unknown"}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(probe);
  }
  const inconsistent = [...groups.entries()].filter(([, values]) => new Set(values.map((probe) => probe.sha256)).size !== 1)
    .map(([key, values]) => ({ key: key.replace("\0", "/"), hashes: [...new Set(values.map((probe) => probe.sha256))].sort() }));
  const canonicalProbes = [...groups.values()].map((values) => {
    const probe = values[0];
    return { route_key: probe.route_key || null, viewport: probe.viewport || "unknown",
      requested_url: probe.requested_url, final_url: probe.final_url, status: probe.status,
      document_sha256: probe.document_sha256, resources: probe.resources, sha256: probe.sha256 };
  }).sort((a, b) => String(a.route_key).localeCompare(String(b.route_key)) || a.viewport.localeCompare(b.viewport));
  const bindings = canonicalProbes.map((probe) => ({ route_key: probe.route_key, viewport: probe.viewport, sha256: probe.sha256 }));
  const core = { algorithm: "sha256-response-bodies-v1", probes: canonicalProbes };
  return { ...core, reload_counts: Object.fromEntries([...groups.entries()].map(([key, values]) => [key.replace("\0", "/"), values.length])),
    inconsistent_reloads: inconsistent, sha256: sha256Bytes(Buffer.from(canonicalJson(bindings), "utf8")),
    complete: inconsistent.length === 0 };
}

/** Close a Playwright browser within a bound. A hung close (a context torn
 * down mid-screenshot) must not keep the process, and its machine-wide
 * source-study slot, alive forever: after the bound the browser process is
 * killed and the outcome is returned, never hidden. */
export async function closeBrowserBounded(browser, timeoutMs = 15000) {
  if (!browser) return { closed: false, reason: 'no-browser' };
  let timer;
  const timeout = new Promise((resolve) => {
    timer = setTimeout(() => resolve({ closed: false, reason: 'close-timeout', timeout_ms: timeoutMs }), timeoutMs);
  });
  const close = browser.close().then(() => ({ closed: true }),
    (error) => ({ closed: false, reason: 'close-error', message: String(error?.message || error).slice(0, 300) }));
  const outcome = await Promise.race([close, timeout]);
  clearTimeout(timer);
  if (!outcome.closed) {
    try { browser.process()?.kill('SIGKILL'); outcome.killed = true; }
    catch (error) { outcome.killed = false; outcome.kill_error = String(error?.message || error).slice(0, 200); }
  }
  return outcome;
}
