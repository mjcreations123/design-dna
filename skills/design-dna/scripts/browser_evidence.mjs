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

const MANIFEST_TRIGGER_TYPES = new Set(["none", "hover", "focus", "click", "keyboard", "input", "url", "programmatic"]);

export function validateManifestState(state, options = {}) {
  if (!state || !/^[a-z][a-z0-9-]{0,47}$/.test(state.id || "") ||
      !["rest", "interactive", "system", "data"].includes(state.kind) ||
      typeof state.expectation !== "string" || !state.expectation.trim() ||
      !state.trigger || !MANIFEST_TRIGGER_TYPES.has(state.trigger.type) ||
      typeof state.trigger.target !== "string" || !state.trigger.target.trim() ||
      !(state.trigger.value === null || typeof state.trigger.value === "string")) {
    return "State must have id, kind, substantive expectation, and exact {type,target,value} trigger.";
  }
  if (state.kind === "rest" && (state.id !== "rest" || state.trigger.type !== "none" ||
      state.trigger.target !== "document" || state.trigger.value !== null)) {
    return "The rest state must be id=rest with trigger {type:none,target:document,value:null}.";
  }
  if (state.kind !== "rest" && state.trigger.type === "none") return "Only the rest state may use a none trigger.";
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

/** Apply one explicit state trigger. Programmatic/system/data states require a
 * project-owned harness; the evidence tool will not fabricate their behavior. */
export async function applyManifestState(page, state) {
  const invalid = validateManifestState(state);
  if (invalid) throw new Error(`${state?.id || "(unnamed state)"}: ${invalid}`);
  const trigger = state.trigger;
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
    if (!/^\[data-design-dna-state-driver(?:[=\]])/.test(trigger.target)) {
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
      if (element.matches('[role="dialog"],dialog')) add(element, 'dialog', 'interactive', ['click','keyboard','programmatic']);
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

async function interactionTargetSafety(target, inputKind, inputValue = null) {
  return target.evaluate((element, input) => {
    const kind = input.kind, value = input.value;
    const text = (element.getAttribute('aria-label') || element.textContent || '').trim().replace(/\s+/g, ' ').toLowerCase();
    const tag = element.tagName.toLowerCase(), role = element.getAttribute('role') || '';
    const explicitSafe = element.getAttribute('data-design-dna-safe-state') === 'true';
    const dangerousWords = /\b(add(?: to cart)?|buy|purchase|pay|checkout|submit|send|delete|remove|cancel|confirm|book|reserve|subscribe|register|upload|sign out|log out|publish)\b/;
    const formSubmit = tag === 'button' && (!element.getAttribute('type') || element.getAttribute('type').toLowerCase() === 'submit');
    const navigates = tag === 'a' && element.hasAttribute('href');
    const safeDisclosure = tag === 'summary' || role === 'tab' || element.hasAttribute('aria-expanded') || element.hasAttribute('aria-pressed');
    const activatingKeyboard = kind === 'keyboard' && /^(enter|space| )$/i.test(String(value || ''));
    const unknownButton = (tag === 'button' || role === 'button') && !safeDisclosure;
    const potentiallyMutating = (kind === 'click' || activatingKeyboard) && (formSubmit || navigates || unknownButton || dangerousWords.test(text));
    return { safe: explicitSafe || safeDisclosure || !potentiallyMutating, explicit_safe: explicitSafe,
      reason: potentiallyMutating && !explicitSafe && !safeDisclosure ? 'potential external/state-changing side effect' : null,
      tag, role, text, href: element.getAttribute('href'), type: element.getAttribute('type') };
  }, { kind: inputKind, value: inputValue });
}

/** Uncapped target/input census for one exact page/profile. */
export async function captureInteractionCensus(page, options = {}) {
  const profile = options.profile || 'wide';
  const pageUrl = normalizeHttpUrl(options.pageUrl || page.url());
  const authoredStates = options.authoredStates || [];
  const capture = options.captureEvidence || (async () => null);
  const discovery = await page.evaluate(async () => {
    let sequence = 0;
    const roots = [document], targets = [], stateHooks = [], animationHooks = [];
    for (let index = 0; index < roots.length; index += 1) roots[index].querySelectorAll('*').forEach((element) => { if (element.shadowRoot) roots.push(element.shadowRoot); });
    for (const root of roots) root.querySelectorAll('[data-dna-interaction-id]').forEach((element) => {
      sequence = Math.max(sequence, Number(element.dataset.dnaInteractionId || 0));
    });
    const selector = 'a[href],button,input,select,textarea,summary,details,video,audio,[role="button"],[role="tab"],[role="menuitem"],[role="switch"],[role="checkbox"],[role="radio"],[onclick],[tabindex]';
    const seen = new Set();
    for (const root of roots) {
      const candidates = new Set(root.querySelectorAll(selector));
      root.querySelectorAll('*').forEach((element) => { if (getComputedStyle(element).cursor === 'pointer') candidates.add(element); });
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
        targets.push({ marker, selector: `[data-dna-interaction-id="${marker}"]`, tag: element.tagName.toLowerCase(), role,
          text, semantic_key: semanticKey, class_signature: classes, repeat_class: repeatClass,
          kind: ['video','audio'].includes(element.tagName.toLowerCase()) ? 'media' :
            (element.matches('details,summary,[aria-expanded]') ? 'open-close' :
              (element.matches('input,select,textarea') ? 'input-control' :
                (element.matches('a[href]') ? 'route-link' : 'control'))),
          focusable: element.matches('a[href],button,input,select,textarea,summary,[tabindex]:not([tabindex="-1"])'),
          hoverable: getComputedStyle(element).cursor === 'pointer' || element.matches('a[href],button,summary,[role="button"],[role="tab"]'),
          href: element.tagName === 'A' ? element.href : null,
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
  const discovered = discovery.targets;
  const repeatGroups = new Map();
  for (const target of discovered) {
    if (!repeatGroups.has(target.repeat_class)) repeatGroups.set(target.repeat_class, []);
    repeatGroups.get(target.repeat_class).push(target);
  }
  for (const group of repeatGroups.values()) group.forEach((target, index) => {
    target.repeat_index = index + 1; target.repeat_count = group.length;
  });
  const targetRows = [], blocked = [], missing = [];
  const inputCount = { discovered: 0, exercised: 0, blocked: 0 };
  for (const target of discovered) {
    const targetId = sha256Bytes(Buffer.from(`${pageUrl}\0${target.marker}\0${target.repeat_class}\0${target.text}`, 'utf8')).slice(0, 24);
    const locator = page.locator(target.selector);
    const sourceStates = [];
    for (const state of authoredStates) {
      if (normalizeHttpUrl(state.url || pageUrl) !== pageUrl || ['none','url'].includes(state.trigger?.type)) continue;
      try {
        const stateLocator = page.locator(state.trigger.target);
        if (await stateLocator.count() === 1 && await stateLocator.first().getAttribute('data-dna-interaction-id') === target.marker) sourceStates.push(state.id);
      } catch { /* invalid state target is separately rejected */ }
    }
    const inputs = [];
    const exercise = async (inputKind, inputValue, action, sourceStateId = null) => {
      inputCount.discovered += 1;
      const safety = await interactionTargetSafety(locator, inputKind, inputValue);
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
      try {
        await locator.scrollIntoViewIfNeeded();
        const beforePageUrl = normalizeHttpUrl(page.url());
        const beforeFrame = await capture(`${targetId}-${inputKind}-before`);
        const before = await visualSnapshot(page, target.selector);
        await action(locator);
        if (normalizeHttpUrl(page.url()) !== beforePageUrl) throw new Error('interaction navigated without an exact URL trigger/navigation binding');
        await page.waitForTimeout(80);
        const after = await visualSnapshot(page, target.selector);
        const afterFrame = await capture(`${targetId}-${inputKind}-after`);
        await page.waitForTimeout(220);
        const settled = await visualSnapshot(page, target.selector);
        const settledFrame = await capture(`${targetId}-${inputKind}-settled`);
        const changes = changedVisualProperties(before, settled);
        const classification = classifyVisualChanges(changes, diagnosticVisualChanges(before, settled));
        inputs.push({ input_kind: inputKind, input_value: inputValue, safety: 'safe', status: 'exercised',
          source_state_id: sourceStateId, before_sha256: before.sha256, after_sha256: after.sha256,
          settled_sha256: settled.sha256, changed_properties: changes,
          change_classification: classification,
          behavior: changes.length ? `changed ${[...new Set(changes.map((item) => item.property))].join(', ')}` : 'no visible computed-style/geometry change',
          evidence: { before: beforeFrame, after: afterFrame, settled: settledFrame },
          disposition: changes.length ? 'sourceable-observed-behavior' : 'observed-quiet' });
        inputCount.exercised += 1;
      } catch (error) {
        missing.push({ target_id: targetId, input_kind: inputKind, reason: String(error).slice(0, 240) });
      }
    };
    if (target.hoverable) await exercise('hover', null, async (item) => { await item.hover({ timeout: 5000 }); });
    if (target.focusable) await exercise('focus', null, async (item) => { await item.focus({ timeout: 5000 }); });
    if (target.focusable) await exercise('focus-traversal', 'Tab', async (item) => {
      await item.focus({ timeout: 5000 }); await page.keyboard.press('Tab');
    });
    if (target.kind === 'control' && (target.tag === 'button' || target.role === 'button')) {
      await exercise('keyboard', 'Enter', async (item) => {
        await item.focus({ timeout: 5000 }); await page.keyboard.press('Enter');
      });
      await exercise('keyboard', 'Space', async (item) => {
        await item.focus({ timeout: 5000 }); await page.keyboard.press('Space');
      });
    }
    if (target.kind === 'control' && (target.tag === 'button' || target.role === 'button')) await exercise('click', null,
      async (item) => { await item.click({ timeout: 5000 }); });
    if (target.kind === 'open-close') {
      const openTarget = target.tag === 'details' ? locator.locator('summary').first() : locator;
      if (await openTarget.count()) {
        await exercise('keyboard', 'Enter', async () => {
          await openTarget.focus({ timeout: 5000 }); await page.keyboard.press('Enter');
        });
        await exercise('keyboard', 'Space', async () => {
          await openTarget.focus({ timeout: 5000 }); await page.keyboard.press('Space');
        });
        await exercise('open-close', 'open then close', async () => {
          await openTarget.click({ timeout: 5000 }); await page.waitForTimeout(120); await openTarget.click({ timeout: 5000 });
        });
      }
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
      if (!state || ['hover','focus'].includes(state.trigger.type)) continue;
      await exercise(state.trigger.type, state.trigger.value, async () => {
        // Exact state execution is owned by applyManifestState so URL changes,
        // programmatic drivers, and side-effect policy remain fail closed.
        await applyManifestState(page, state);
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
      if (href && new URL(href).origin === new URL(pageUrl).origin) {
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
    targetRows.push({ target_id: targetId, page_url: pageUrl, selector: target.selector, tag: target.tag, role: target.role,
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

  const authoredStateIds = new Set(authoredStates.map((state) => state.id));
  const boundStateIds = new Set(targetRows.flatMap((row) => row.source_state_ids));
  const pageStates = [];
  for (const state of authoredStates.filter((item) => ['none','url','programmatic'].includes(item.trigger.type))) {
    let triggerEvidence = null, evidence = null, disposition = 'covered-by-state-ledger';
    if (state.trigger.type === 'none') {
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
  const semanticIssues = targets.filter((target) => {
    const stateful = target.kind === 'open-close' || (target.inputs || []).some((input) =>
      (input.change_classification?.structural_semantic || []).some((change) =>
        ['aria_expanded','aria_pressed','presence','display','visibility'].includes(change.property)));
    const semantic = target.semantic_state || {};
    return stateful && semantic.aria_expanded === null && semantic.aria_pressed === null && semantic.aria_controls === null;
  }).map((target) => ({ target_id: target.target_id, selector: target.selector,
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
      const explicit = element.matches("[data-scroll],[data-scroll-container],[data-lenis],[data-scroll-section],[class*='scroll' i]");
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
      const changed = after.x !== before.x || after.y !== before.y || after.fingerprint !== before.fingerprint;
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
