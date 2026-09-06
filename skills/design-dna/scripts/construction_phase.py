"""Derive a bounded first-screen view from the unchanged pre-code full plan."""
from copy import deepcopy
import math
import re

def derive_first_screen_routes(manifest, mapping, route_keys=None):
    isolation = mapping.get("proof_isolation", {})
    primary = isolation.get("primary_route_key")
    requested = route_keys or [primary]
    if requested != [primary]:
        raise ValueError("first-screen route filter must equal the pre-code primary route")
    route = next((row for row in manifest.get("routes", []) if row.get("key") == primary), None)
    ids = isolation.get("decision_ids", mapping.get("planned_decision_ids"))
    if route is None or not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
        raise ValueError("first-screen needs a unique pre-code decision subset and primary route")
    decisions = {row.get("decision_id"): row for row in mapping.get("decisions", [])}
    if any(key not in decisions for key in ids):
        raise ValueError("first-screen decision subset names an unplanned component")
    states = {binding.get("state_id") for key in ids for binding in decisions[key].get("bindings", [])
              if binding.get("route_key") == primary}
    known = {state["id"] for state in route.get("states", [])}
    if "rest" not in states or not states.issubset(known):
        raise ValueError("first-screen decision bindings must include rest and only full-manifest states")
    result = deepcopy(route)
    result["states"] = [state for state in result["states"] if state["id"] in states]
    return [result]

def derive_first_screen_source_census(census, mapping, route, profile, build_census=None, source_page_url=None):
    result = deepcopy(census)
    if source_page_url is None and len(result.get("pages", [])) > 1:
        raise ValueError("first-screen source projection needs the exact observed state page URL")
    if source_page_url is not None:
        result["pages"] = [page for page in result.get("pages", []) if page.get("url") == source_page_url]
        if len(result["pages"]) != 1:
            raise ValueError("first-screen source state page identity is absent or duplicated")
    proof_ids = set(mapping.get("proof_isolation", {}).get("decision_ids", mapping.get("planned_decision_ids", [])))
    selectors = {row.get("source_mapping", {}).get("source_selector") for row in mapping.get("decisions", [])
                 if row.get("decision_id") in proof_ids and row.get("source_mapping", {}).get("id") == route.get("mapped_reference_id")
                 and any(cell.get("route_key") == route["key"] and cell.get("viewport") == profile for cell in row.get("bindings", []))}
    targets = []
    for page in result.get("pages", []):
        page["targets"] = [row for row in page.get("targets", []) if (row.get("source_selector") or row.get("selector")) in selectors]
        targets.extend(page["targets"])
    decisions = {row.get("decision_id"): row for row in mapping.get("decisions", [])}
    for page in (build_census or {}).get("pages", []):
        for target in page.get("targets", []):
            for item in target.get("inputs", []):
                if item.get("disposition") != "deferred-until-final-gate":
                    continue
                decision = decisions.get(item.get("decision_id"), {})
                source_selector = decision.get("source_mapping", {}).get("source_selector")
                matches = [row for row in targets if (row.get("source_selector") or row.get("selector")) == source_selector and row.get("kind") == "route-link"]
                if (item.get("decision_id") not in proof_ids or len(matches) != 1
                    or not any(cell.get("route_key") == route["key"] and cell.get("viewport") == profile for cell in decision.get("bindings", []))):
                    raise ValueError("planned route handoff lacks one exact source-mapped proof link")
                if not any(row.get("input_kind") == "navigation" and row.get("status") == "exercised" for row in matches[0].get("inputs", [])):
                    raise ValueError("planned route handoff source did not prove its navigation")
                matches[0]["inputs"] = [row for row in matches[0]["inputs"] if row.get("input_kind") != "navigation"]
    ids = {row.get("target_id") for row in targets}
    inputs = [item for row in targets for item in row.get("inputs", [])]
    result["totals"] = {"targets_discovered": len(targets), "inputs_discovered": len(inputs),
                        "inputs_exercised": sum(item.get("status") == "exercised" for item in inputs),
                        "inputs_blocked": sum(item.get("status") == "blocked" for item in inputs)}
    result["pointer_follow"] = [row for row in result.get("pointer_follow", []) if row.get("selector") in selectors or row.get("target_id") in ids]
    return result


def planned_deferred_routes(project, active_routes):
    """Resolve pending URLs only from the unchanged, hash-bound full plan."""
    import hashlib
    import json
    state = project / ".design-dna"
    raw = (state / "route-manifest.json").read_bytes()
    manifest = json.loads(raw)
    mapping = json.loads((state / "visible-decision-sources.json").read_text(encoding="utf-8"))
    if mapping.get("route_manifest", {}).get("sha256") != hashlib.sha256(raw).hexdigest():
        raise ValueError("planned route handoff manifest identity drifted")
    active = {row["key"] for row in active_routes}
    if active != {mapping.get("proof_isolation", {}).get("primary_route_key")}:
        raise ValueError("planned route handoff is only available to its primary first-screen route")
    return {row["url"] for row in manifest["routes"] if row["key"] not in active}


def derive_first_screen_region_authority(mapping, style_records, route_key, profile, state_id, viewport_height):
    """Derive the one proof region's measured extent; never a viewport multiplier."""
    isolation = mapping.get("proof_isolation", {})
    proof_ids = set(isolation.get("decision_ids", mapping.get("planned_decision_ids", [])))
    matches = [(decision, cell) for decision in mapping.get("decisions", [])
               if decision.get("decision_id") in proof_ids and decision.get("component_id") == isolation.get("region_component_id")
               and decision.get("category") == "layout" for cell in decision.get("bindings", [])
               if cell.get("route_key") == route_key and cell.get("viewport") == profile and cell.get("state_id") == state_id]
    if route_key != isolation.get("primary_route_key") or len(matches) != 1:
        raise ValueError("first-screen extent needs one exact source-bound primary-region layout cell")
    decision, cell = matches[0]
    record = decision.get("style_provenance", {}).get("record", {})
    styles = style_records.get(record.get("path"), {})
    source_state = cell.get("source_state", {}).get("id")
    rows = [row for row in styles.get("component_styles", []) if row.get("profile") == profile and row.get("state_id") == source_state]
    selector = decision.get("source_mapping", {}).get("source_selector")
    source = [row for row in rows if row.get("selector") == selector]
    if len(source) != 1:
        raise ValueError("first-screen extent lacks its exact measured source selector/state/profile")
    source = source[0]
    facts = source.get("content_facts", {})
    if facts.get("tag") in {"body", "html"}:
        raise ValueError("a document wrapper cannot authorize a primary proof region")
    by_selector = {row.get("selector"): row for row in rows}
    descendants = []
    for row in rows:
        if row is source or row.get("content_facts", {}).get("tag") not in {"main", "section", "article"}:
            continue
        parent_selector, visited = row.get("content_facts", {}).get("parent_selector"), set()
        while parent_selector and parent_selector not in visited:
            if parent_selector == selector:
                descendants.append(row)
                break
            visited.add(parent_selector)
            parent_selector = by_selector.get(parent_selector, {}).get("content_facts", {}).get("parent_selector")
    descendant_selectors = {row.get("selector") for row in descendants}
    for boundary in {selector, *descendant_selectors}:
        frontier = []
        for row in descendants:
            if row.get("selector") == boundary:
                continue
            parent_selector, visited, nested = row.get("content_facts", {}).get("parent_selector"), set(), False
            offset = row.get("geometry", {}).get("top", 0)
            while parent_selector and parent_selector != boundary and parent_selector not in visited:
                if parent_selector in descendant_selectors:
                    nested = True
                visited.add(parent_selector)
                parent_row = by_selector.get(parent_selector, {})
                offset += parent_row.get("geometry", {}).get("top", 0)
                parent_selector = parent_row.get("content_facts", {}).get("parent_selector")
            if parent_selector == boundary and not nested:
                frontier.append((offset, offset + row.get("geometry", {}).get("height", 0)))
        if any(a[1] <= b[0] or b[1] <= a[0] for index, a in enumerate(frontier) for b in frontier[index + 1:]):
            raise ValueError("an enclosing wrapper aggregating sequential source regions cannot authorize a primary proof extent")
    nested_components = []
    for descendant in descendants:
        bound = {row.get("component_id") for row in mapping.get("decisions", [])
                 if row.get("decision_id") in proof_ids and row.get("source_mapping", {}).get("id") == decision.get("source_mapping", {}).get("id")
                 and row.get("source_mapping", {}).get("source_selector") == descendant.get("selector")
                 and any(binding.get("route_key") == route_key and binding.get("viewport") == profile and binding.get("state_id") == state_id for binding in row.get("bindings", []))}
        if len(bound) != 1:
            raise ValueError("each nested source region needs one exact pre-code proof component binding")
        nested_components.extend(bound)
    geometry = source.get("geometry", {})
    if any(type(geometry.get(key)) not in {int, float} or not math.isfinite(geometry[key]) for key in ("left", "top", "width", "height")) or geometry["height"] <= 0 or geometry["width"] <= 0:
        raise ValueError("first-screen source region geometry is incomplete")
    def bottom(value):
        if value is None:
            return 0
        tokens = str(value).split()
        if not 1 <= len(tokens) <= 4 or any(re.fullmatch(r"-?(?:\d+(?:\.\d*)?|\.\d+)(?:px)?", token) is None for token in tokens):
            raise ValueError("first-screen source edge inset lacks measured pixel values")
        return max(0, float(tokens[2 if len(tokens) > 2 else 0].removesuffix("px")))
    top = geometry["top"]
    trailing = bottom(source.get("properties", {}).get("margin"))
    parent = source.get("content_facts", {}).get("parent_selector")
    seen = {selector}
    while parent:
        if parent in seen:
            raise ValueError("first-screen source ancestry loops")
        seen.add(parent)
        parents = [row for row in rows if row.get("selector") == parent]
        if not parents:
            # html is deliberately outside the component style map.
            if source.get("content_facts", {}).get("parent_tag") == "html":
                break
            raise ValueError("first-screen source parent geometry is missing")
        if len(parents) != 1 or type(parents[0].get("geometry", {}).get("top")) not in {int, float}:
            raise ValueError("first-screen source parent geometry is ambiguous")
        source = parents[0]
        top += source["geometry"]["top"]
        trailing += bottom(source.get("properties", {}).get("margin")) + bottom(source.get("properties", {}).get("padding"))
        parent = source.get("content_facts", {}).get("parent_selector")
    return {"route_key": route_key, "viewport": profile, "state_id": state_id,
            "region_component_id": isolation["region_component_id"], "decision_id": decision["decision_id"],
            "source_reference_id": decision["source_mapping"]["id"], "source_selector": selector,
            "source_state_id": source_state, "source_style_record": deepcopy(record), "geometry": deepcopy(geometry),
            "proof_decision_ids": sorted(row["decision_id"] for row in mapping.get("decisions", []) if row.get("decision_id") in proof_ids
                and any(binding.get("route_key") == route_key and binding.get("viewport") == profile and binding.get("state_id") == state_id for binding in row.get("bindings", []))),
            "nested_region_component_ids": sorted(set(nested_components)),
            "document_top": top, "document_height_ceiling": max(viewport_height, math.ceil(top + geometry["height"] + trailing)), "tolerance_px": 2}


def first_screen_scope_pass(scope, authority=None):
    if not isinstance(scope, dict) or any(type(scope.get(key)) not in {int, float} or not math.isfinite(scope[key]) for key in ("document_height", "viewport_height")):
        return False
    regions = scope.get("substantial_regions", [])
    if not isinstance(regions, list) or any(not isinstance(row, dict) for row in regions):
        return False
    if authority is None:
        return len(regions) == 1 and regions[0].get("top", scope["viewport_height"]) < scope["viewport_height"] and regions[0].get("bottom", 0) > 0 and not scope.get("beyond_first_screen_regions") and scope["document_height"] <= scope["viewport_height"]
    if (scope.get("source_extent") != authority or len(regions) != 1 or scope.get("outside_primary_components") != []
        or scope.get("extra_primary_regions") != [] or scope.get("unplanned_decision_ids") != [] or scope.get("unsourced_visible_parts") != []
        or scope.get("wrapper_inherited_visible_parts") != [] or scope.get("reused_decision_ids") != []):
        return False
    region = regions[0]
    if any(type(region.get(key)) not in {int, float} or not math.isfinite(region[key]) for key in ("top", "bottom", "width", "height")) or abs(region["bottom"] - region["top"] - region["height"]) > 2:
        return False
    if region.get("component_id") != authority["region_component_id"] or region.get("component_key") != "component:" + authority["region_component_id"]:
        return False
    expected = authority["geometry"]
    return (region.get("top", scope["viewport_height"]) < scope["viewport_height"]
            and abs(region.get("top", float("inf")) - authority["document_top"]) <= 2
            and all(type(region.get(key)) in {int, float} and abs(region[key] - expected[key]) <= 2 for key in ("width", "height"))
            and max(scope["viewport_height"], region.get("bottom", float("inf"))) - 2 <= scope["document_height"] <= authority["document_height_ceiling"] + 2)


def merge_decision_root_samples(samples):
    """Keep initial geometry while retaining any simultaneous duplicate roots."""
    merged = {}
    for sample in samples:
        for row in sample:
            key = row.get("decision_id")
            if key not in merged or len(row.get("roots", [])) > len(merged[key].get("roots", [])):
                merged[key] = deepcopy(row)
    return [merged[key] for key in sorted(merged)]
