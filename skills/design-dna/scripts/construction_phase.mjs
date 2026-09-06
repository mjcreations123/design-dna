/** Pure first-screen phase projection. The full manifest bytes retain authority. */
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';

export function deriveFirstScreenRoutes(manifest, mapping, routeKeys = []) {
  const isolation = mapping.proof_isolation || {}, primary = isolation.primary_route_key;
  const requested = routeKeys.length ? routeKeys : [primary];
  if (requested.length !== 1 || requested[0] !== primary) throw new Error('first-screen route filter must equal the pre-code primary route');
  const route = manifest.routes.find((row) => row.key === primary);
  const ids = isolation.decision_ids || mapping.planned_decision_ids;
  if (!route || !Array.isArray(ids) || !ids.length || new Set(ids).size !== ids.length) throw new Error('first-screen needs a unique pre-code decision subset and primary route');
  const decisions = new Map(mapping.decisions.map((row) => [row.decision_id, row]));
  if (ids.some((key) => !decisions.has(key))) throw new Error('first-screen decision subset names an unplanned component');
  const states = new Set(ids.flatMap((key) => (decisions.get(key).bindings || []).filter((cell) => cell.route_key === primary).map((cell) => cell.state_id)));
  const known = new Set(route.states.map((row) => row.id));
  if (!states.has('rest') || [...states].some((id) => !known.has(id))) throw new Error('first-screen decision bindings must include rest and only full-manifest states');
  return [{...route, states: route.states.filter((row) => states.has(row.id)).map((row) => structuredClone(row))}];
}

export function deriveFirstScreenRegionAuthority(mapping, styleRecords, routeKey, profile, stateId, viewportHeight) {
  const isolation = mapping.proof_isolation || {}, proofIds = new Set(isolation.decision_ids || mapping.planned_decision_ids || []);
  const matches = (mapping.decisions || []).filter((decision) => proofIds.has(decision.decision_id) && decision.component_id === isolation.region_component_id && decision.category === 'layout')
    .flatMap((decision) => (decision.bindings || []).filter((cell) => cell.route_key === routeKey && cell.viewport === profile && cell.state_id === stateId).map((cell) => ({decision, cell})));
  if (routeKey !== isolation.primary_route_key || matches.length !== 1) throw new Error('first-screen extent needs one exact source-bound primary-region layout cell');
  const {decision, cell} = matches[0], record = decision.style_provenance?.record || {};
  const styles = styleRecords[record.path] || {}, sourceState = cell.source_state?.id;
  const rows = (styles.component_styles || []).filter((row) => row.profile === profile && row.state_id === sourceState);
  const selector = decision.source_mapping?.source_selector, sources = rows.filter((row) => row.selector === selector);
  if (sources.length !== 1) throw new Error('first-screen extent lacks its exact measured source selector/state/profile');
  let source = sources[0]; const facts = source.content_facts || {};
  if (['body','html'].includes(facts.tag)) throw new Error('a document wrapper cannot authorize a primary proof region');
  const nestedComponents = [];
  {
    const bySelector = new Map(rows.map((row) => [row.selector, row])), descendants = [];
    for (const row of rows.filter((row) => row !== source && ['main','section','article'].includes(row.content_facts?.tag))) {
      let parent = row.content_facts?.parent_selector; const visited = new Set();
      while (parent && !visited.has(parent)) {
        if (parent === selector) {descendants.push(row); break;}
        visited.add(parent); parent = bySelector.get(parent)?.content_facts?.parent_selector;
      }
    }
    const descendantSelectors = new Set(descendants.map((row) => row.selector));
    for (const boundary of new Set([selector,...descendantSelectors])) {
      const frontier = [];
      for (const row of descendants.filter((row) => row.selector !== boundary)) {
        let parent = row.content_facts?.parent_selector, offset = row.geometry?.top || 0, nested = false;
        const visited = new Set();
        while (parent && parent !== boundary && !visited.has(parent)) {
          if (descendantSelectors.has(parent)) nested = true;
          visited.add(parent); const parentRow = bySelector.get(parent);
          offset += parentRow?.geometry?.top || 0; parent = parentRow?.content_facts?.parent_selector;
        }
        if (parent === boundary && !nested) frontier.push([offset, offset + (row.geometry?.height || 0)]);
      }
      if (frontier.some((a,index) => frontier.slice(index+1).some((b) => a[1] <= b[0] || b[1] <= a[0]))) throw new Error('an enclosing wrapper aggregating sequential source regions cannot authorize a primary proof extent');
    }
    for (const descendant of descendants) {
      const bound = new Set((mapping.decisions || []).filter((row) => proofIds.has(row.decision_id) && row.source_mapping?.id === decision.source_mapping?.id &&
        row.source_mapping?.source_selector === descendant.selector && row.bindings.some((binding) => binding.route_key === routeKey && binding.viewport === profile && binding.state_id === stateId)).map((row) => row.component_id));
      if (bound.size !== 1) throw new Error('each nested source region needs one exact pre-code proof component binding');
      nestedComponents.push(...bound);
    }
  }
  const geometry = source.geometry || {};
  if (['left','top','width','height'].some((key) => !Number.isFinite(geometry[key])) || geometry.width <= 0 || geometry.height <= 0) throw new Error('first-screen source region geometry is incomplete');
  const bottom = (value) => {
    if (value === undefined || value === null) return 0;
    const tokens = String(value).trim().split(/\s+/);
    if (tokens.length < 1 || tokens.length > 4 || tokens.some((token) => !/^-?(?:\d+(?:\.\d*)?|\.\d+)(?:px)?$/.test(token))) throw new Error('first-screen source edge inset lacks measured pixel values');
    return Math.max(0, Number.parseFloat(tokens[tokens.length > 2 ? 2 : 0]));
  };
  let top = geometry.top, trailing = bottom(source.properties?.margin), parent = source.content_facts?.parent_selector;
  const seen = new Set([selector]);
  while (parent) {
    if (seen.has(parent)) throw new Error('first-screen source ancestry loops');
    seen.add(parent); const parents = rows.filter((row) => row.selector === parent);
    if (!parents.length) {
      if (source.content_facts?.parent_tag === 'html') break;
      throw new Error('first-screen source parent geometry is missing');
    }
    if (parents.length !== 1 || !Number.isFinite(parents[0].geometry?.top)) throw new Error('first-screen source parent geometry is ambiguous');
    source = parents[0]; top += source.geometry.top;
    trailing += bottom(source.properties?.margin) + bottom(source.properties?.padding);
    parent = source.content_facts?.parent_selector;
  }
  return {route_key: routeKey, viewport: profile, state_id: stateId, region_component_id: isolation.region_component_id,
    decision_id: decision.decision_id, source_reference_id: decision.source_mapping.id, source_selector: selector,
    source_state_id: sourceState, source_style_record: structuredClone(record), geometry: structuredClone(geometry),
    proof_decision_ids: (mapping.decisions || []).filter((row) => proofIds.has(row.decision_id) && row.bindings.some((binding) => binding.route_key === routeKey && binding.viewport === profile && binding.state_id === stateId)).map((row) => row.decision_id).sort(),
    nested_region_component_ids: [...new Set(nestedComponents)].sort(),
    document_top: top, document_height_ceiling: Math.max(viewportHeight, Math.ceil(top + geometry.height + trailing)), tolerance_px: 2};
}

export function proofRegionScopePass(scope, authority = null) {
  if (!scope || !Number.isFinite(scope.document_height) || !Number.isFinite(scope.viewport_height)) return false;
  const regions = scope.substantial_regions || [];
  if (!Array.isArray(regions) || regions.some((row) => !row || typeof row !== 'object' || Array.isArray(row))) return false;
  if (!authority) return regions.length === 1 && regions[0].top < scope.viewport_height && regions[0].bottom > 0 && !(scope.beyond_first_screen_regions || []).length && scope.document_height <= scope.viewport_height;
  if (JSON.stringify(scope.source_extent) !== JSON.stringify(authority) || regions.length !== 1 ||
    ['outside_primary_components','extra_primary_regions','unplanned_decision_ids','unsourced_visible_parts','wrapper_inherited_visible_parts','reused_decision_ids'].some((key) => !Array.isArray(scope[key]) || scope[key].length)) return false;
  const region = regions[0], expected = authority.geometry;
  if (['top','bottom','width','height'].some((key) => !Number.isFinite(region[key])) || Math.abs(region.bottom - region.top - region.height) > 2) return false;
  return region.component_id === authority.region_component_id && region.component_key === `component:${authority.region_component_id}` &&
    region.top < scope.viewport_height && Math.abs(region.top - authority.document_top) <= 2 &&
    ['width','height'].every((key) => Number.isFinite(region[key]) && Math.abs(region[key] - expected[key]) <= 2) &&
    scope.document_height >= Math.max(scope.viewport_height,region.bottom) - 2 && scope.document_height <= authority.document_height_ceiling + 2;
}

export function mergeDecisionRootSamples(samples) {
  const merged = new Map();
  for (const sample of samples) for (const row of sample) {
    if (!merged.has(row.decision_id) || (row.roots || []).length > (merged.get(row.decision_id).roots || []).length) merged.set(row.decision_id, structuredClone(row));
  }
  return [...merged.values()].sort((a,b) => a.decision_id < b.decision_id ? -1 : a.decision_id > b.decision_id ? 1 : 0);
}

export function firstScreenManifest(manifest, routeKeys = []) {
  const file = path.join(path.dirname(path.resolve(manifest.__file)), 'visible-decision-sources.json');
  const mapping = JSON.parse(fs.readFileSync(file, 'utf8'));
  const expectedSha = createHash('sha256').update(fs.readFileSync(manifest.__file)).digest('hex');
  if (mapping.route_manifest?.sha256 !== expectedSha || mapping.route_manifest?.manifest_id !== manifest.manifest_id) throw new Error('phase plan differs from the unchanged full route manifest');
  return {...manifest, __planned_routes: manifest.routes, __construction_mapping: mapping, routes: deriveFirstScreenRoutes(manifest, mapping, routeKeys)};
}

export function deriveFirstScreenSourceCensus(census, mapping, route, profile, buildCensus = null, sourcePageUrl = null) {
  const result = structuredClone(census);
  if (sourcePageUrl === null && (result.pages || []).length > 1) throw new Error('first-screen source projection needs the exact observed state page URL');
  if (sourcePageUrl !== null) {
    result.pages = (result.pages || []).filter((page) => page.url === sourcePageUrl);
    if (result.pages.length !== 1) throw new Error('first-screen source state page identity is absent or duplicated');
  }
  const ids = new Set(mapping.proof_isolation?.decision_ids || mapping.planned_decision_ids || []);
  const selectors = new Set(mapping.decisions.filter((row) => ids.has(row.decision_id) && row.source_mapping?.id === route.mapped_reference_id &&
    row.bindings.some((cell) => cell.route_key === route.key && cell.viewport === profile)).map((row) => row.source_mapping.source_selector));
  const targets = [];
  for (const page of result.pages || []) { page.targets = (page.targets || []).filter((row) => selectors.has(row.source_selector || row.selector)); targets.push(...page.targets); }
  const decisions = new Map(mapping.decisions.map((row) => [row.decision_id, row]));
  for (const page of buildCensus?.pages || []) for (const target of page.targets || []) for (const item of target.inputs || []) {
    if (item.disposition !== 'deferred-until-final-gate') continue;
    const decision = decisions.get(item.decision_id);
    const matches = targets.filter((row) => (row.source_selector || row.selector) === decision?.source_mapping?.source_selector && row.kind === 'route-link');
    if (!ids.has(item.decision_id) || matches.length !== 1 || !decision.bindings.some((cell) => cell.route_key === route.key && cell.viewport === profile)) throw new Error('planned route handoff lacks one exact source-mapped proof link');
    if (!matches[0].inputs.some((row) => row.input_kind === 'navigation' && row.status === 'exercised')) throw new Error('planned route handoff source did not prove its navigation');
    matches[0].inputs = matches[0].inputs.filter((row) => row.input_kind !== 'navigation');
  }
  const targetIds = new Set(targets.map((row) => row.target_id)), inputs = targets.flatMap((row) => row.inputs || []);
  result.totals = {targets_discovered: targets.length, inputs_discovered: inputs.length,
    inputs_exercised: inputs.filter((row) => row.status === 'exercised').length, inputs_blocked: inputs.filter((row) => row.status === 'blocked').length};
  result.pointer_follow = (result.pointer_follow || []).filter((row) => selectors.has(row.selector) || targetIds.has(row.target_id));
  return result;
}
