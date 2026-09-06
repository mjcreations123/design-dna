#!/usr/bin/env python3
"""A reached inner-route cap is a recorded scope; anything short of it is incomplete."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]


def load_initializer():
    spec = importlib.util.spec_from_file_location("init_project_state", SKILL / "scripts" / "init_project_state.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


INITIALIZER = load_initializer()
HOME = "https://reference.example.test/"
STATES = ["https://reference.example.test/state-a", "https://reference.example.test/state-b"]
INNER = [f"https://reference.example.test/page-{index}" for index in range(1, 10)]


class InnerRouteScopeTests(unittest.TestCase):
    def test_full_visit_is_complete_without_a_cap(self) -> None:
        entry = {"discovered_urls": [HOME, *INNER[:3]], "visited_urls": [HOME, *INNER[:3]]}
        self.assertTrue(INITIALIZER.discovery_route_scope_complete(entry))

    def test_unvisited_routes_without_a_declared_cap_are_incomplete(self) -> None:
        entry = {"discovered_urls": [HOME, *INNER[:3]], "visited_urls": [HOME, *INNER[:2]], "unvisited_urls": [INNER[2]]}
        self.assertFalse(INITIALIZER.discovery_route_scope_complete(entry))

    def test_cap_reached_with_every_remaining_route_recorded_is_complete(self) -> None:
        entry = {"discovered_urls": [HOME, *INNER], "visited_urls": [HOME, *INNER[:6]],
                 "unvisited_urls": INNER[6:], "inner_route_cap": 6, "inner_routes_visited": 6}
        self.assertTrue(INITIALIZER.discovery_route_scope_complete(entry))

    def test_cap_declared_but_not_reached_with_routes_left_is_incomplete(self) -> None:
        entry = {"discovered_urls": [HOME, *INNER], "visited_urls": [HOME, *INNER[:4]],
                 "unvisited_urls": INNER[4:], "inner_route_cap": 6, "inner_routes_visited": 4}
        self.assertFalse(INITIALIZER.discovery_route_scope_complete(entry))

    def test_authored_routes_cannot_substitute_for_missing_inner_routes(self) -> None:
        entry = {"discovered_urls": [HOME, *STATES, *INNER[:6]], "visited_urls": [HOME, *STATES, *INNER[:4]],
                 "unvisited_urls": INNER[4:6], "inner_route_cap": 6, "inner_routes_visited": 4}
        self.assertFalse(INITIALIZER.discovery_route_scope_complete(entry))

    def test_reached_cap_without_the_inner_count_in_the_record_is_incomplete(self) -> None:
        entry = {"discovered_urls": [HOME, *INNER], "visited_urls": [HOME, *INNER[:6]],
                 "unvisited_urls": INNER[6:], "inner_route_cap": 6}
        self.assertFalse(INITIALIZER.discovery_route_scope_complete(entry))

    def test_unvisited_list_must_account_for_every_discovered_route(self) -> None:
        entry = {"discovered_urls": [HOME, *INNER], "visited_urls": [HOME, *INNER[:6]],
                 "unvisited_urls": INNER[6:8], "inner_route_cap": 6, "inner_routes_visited": 6}
        self.assertFalse(INITIALIZER.discovery_route_scope_complete(entry))

    def test_cap_below_the_two_inner_page_floor_is_refused(self) -> None:
        entry = {"discovered_urls": [HOME, *INNER], "visited_urls": [HOME, INNER[0]],
                 "unvisited_urls": INNER[1:], "inner_route_cap": 1, "inner_routes_visited": 1}
        self.assertFalse(INITIALIZER.discovery_route_scope_complete(entry))

    def test_duplicate_or_blank_routes_are_refused(self) -> None:
        self.assertFalse(INITIALIZER.discovery_route_scope_complete({"discovered_urls": [HOME, HOME], "visited_urls": [HOME, HOME]}))
        self.assertFalse(INITIALIZER.discovery_route_scope_complete({"discovered_urls": [HOME, ""], "visited_urls": [HOME, ""]}))


if __name__ == "__main__":
    unittest.main()
