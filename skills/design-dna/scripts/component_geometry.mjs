/** Compare every mapped component's observed parent-relative composition. */
export function compareComponentGeometry(binding, censusChecks, sourceStyles, routeKeys, contentPlan = null, firstScreen = false) {
  const findings = [], cells = [];
  for (const decision of binding.decisions || []) for (const cell of decision.bindings || []) {
    if (firstScreen && binding.proof_isolation?.decision_ids && !binding.proof_isolation.decision_ids.includes(decision.decision_id)) continue;
    if (!routeKeys.includes(cell.route_key)) continue;
    const base = {route_key: cell.route_key, viewport: cell.viewport, state_id: cell.state_id,
      component_id: decision.component_id, decision_id: decision.decision_id, source_reference_id: decision.source_mapping?.id};
    const check = censusChecks.find((row) => row.route_key === cell.route_key && row.viewport === cell.viewport && row.state_id === cell.state_id);
    const roots = (check?.decision_roots || []).filter((row) => row.decision_id === decision.decision_id).flatMap((row) => row.roots || []);
    const composition = contentPlan?.decisions?.find((row) => row.decision_id === decision.decision_id)?.arrangement_source;
    const selector = composition?.source_selector || decision.source_mapping?.source_selector;
    const tuple = decision.style_provenance?.tuples?.find((row) => row.viewport === cell.viewport && row.state_id === cell.state_id);
    const source = (sourceStyles.get(composition?.source_reference_id || decision.source_mapping?.id)?.component_styles || []).find((row) =>
      row.profile === cell.viewport && row.state_id === (composition?.source_state_id || cell.source_state?.id) && row.selector === (composition?.source_selector || tuple?.source_selector || selector));
    const actual = roots.length === 1 ? roots[0]?.geometry : null;
    const expected = source?.geometry;
    const fields = ['left', 'top', 'width', 'height'];
    const missing = !actual || !expected || fields.some((field) => !Number.isFinite(actual[field]) || !Number.isFinite(expected[field]));
    const mismatches = missing ? fields : fields.filter((field) => Math.abs(actual[field] - expected[field]) > 2);
    const result = {...base, source_selector: tuple?.source_selector || selector, expected, actual, pass: !mismatches.length};
    cells.push(result);
    if (mismatches.length) findings.push({...base, code: missing ? 'component-composition-evidence-missing' : 'component-composition-mismatch',
      source_selector: result.source_selector, properties: mismatches, expected, actual,
      remedy: 'Restore the source component dimensions and parent-relative arrangement; a matching first screen cannot authorize invented later sections.'});
  }
  return {complete: cells.length > 0 && !findings.length, cells, findings, tolerance_px: 2};
}

/** Aliases sharing indistinguishable rendered content do not prove separate route jobs. */
export function indistinguishableRouteFindings(routeCells) {
  const findings = [];
  const groups = new Map();
  for (const cell of routeCells.filter((row) => row.state_id === 'rest')) {
    const key = `${cell.viewport}|${cell.rendered_route_identity}`;
    if (!cell.rendered_route_identity) continue;
    const prior = groups.get(key);
    if (prior && prior.route_key !== cell.route_key) findings.push({code: 'route-job-indistinguishable',
      route_key: cell.route_key, other_route_key: prior.route_key, viewport: cell.viewport,
      remedy: 'Prove a meaningful direct-entry content or interaction state difference; a query/hash alias alone is not another route.'});
    else groups.set(key, cell);
  }
  return findings;
}
