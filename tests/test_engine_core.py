"""Core generation engine: road networks, city layout, isometric rendering."""
import random
import unittest

import numpy as np

from engine.core import city_layout as C
from engine.core import road_network as R
from engine.render.isometric import render_grid_visible_iso


def _network_snapshot(net):
    return {key: sorted(net[key].items() if isinstance(net[key], dict) else net[key]) for key in (
        "big_rows", "big_cols", "big_rows_ext", "big_cols_ext",
        "small_rows", "small_cols", "small_rows_ext", "small_cols_ext",
        "road_cells",
    )}


class RoadNetworkTests(unittest.TestCase):
    def test_seeded_generation_is_stable(self):
        size = R.make_size(40, even=True)
        first = _network_snapshot(R.gen_networks(17, size=size))
        second = _network_snapshot(R.gen_networks(17, size=size))
        different = _network_snapshot(R.gen_networks(18, size=size))

        self.assertEqual(first, second)
        self.assertNotEqual(first, different)


class CityLayoutTests(unittest.TestCase):
    def test_generated_placements_validate(self):
        fine = 6
        road_cells = {(0, y) for y in range(fine)}
        lots = C.find_lots(road_cells, fine)
        catalog = [C.Building("001", 1, 9, 9, {"type": 1})]

        placements = C.place_city(
            road_cells, lots, catalog, fine,
            rng=random.Random(5), type2_frontage_cells=road_cells,
        )

        self.assertGreater(len(placements), 0)
        C.validate_placements(road_cells, placements, fine)

    def test_validate_placements_rejects_overlaps(self):
        building = C.Building("001", 1, 9, 9, {"type": 1})
        placements = [
            C.CityPlacement(building, "N", C.PlacementRect(1, 1, 1, 1)),
            C.CityPlacement(building, "S", C.PlacementRect(1, 1, 1, 1)),
        ]
        with self.assertRaisesRegex(ValueError, "overlaps"):
            C.validate_placements(set(), placements, fine=4)

    def test_type2_building_places_at_most_once(self):
        fine = 5
        road_cells = {(0, y) for y in range(fine)}
        lots = C.find_lots(road_cells, fine)
        building = C.Building("010", 2, 9, 9, {"type": 2})
        rules = C.PlacementRules(banned_buildings=set())
        state = rules.new_state(random.Random(1))

        placements = C.place_city(
            road_cells,
            lots,
            [building],
            fine,
            rng=random.Random(5),
            rules=rules,
            rule_state=state,
            type2_frontage_cells=road_cells,
        )

        self.assertEqual(len([p for p in placements if p.building.num == "010"]), 1)

    def test_type2_buildings_place_largest_first(self):
        fine = 6
        road_cells = {(0, y) for y in range(fine)}
        lots = C.find_lots(road_cells, fine)
        small = C.Building("010", 2, 9, 9, {"type": 2})
        large = C.Building("020", 2, 18, 18, {"type": 2})
        rules = C.PlacementRules(banned_buildings=set())
        state = rules.new_state(random.Random(1))

        placements = C.place_city(
            road_cells,
            lots,
            [small, large],
            fine,
            rng=random.Random(5),
            rules=rules,
            rule_state=state,
            type2_frontage_cells=road_cells,
            landmark_spacing=0,
        )

        self.assertEqual([p.building.num for p in placements if p.building.type == 2], ["020", "010"])
        self.assertEqual(placements[0].rect, C.PlacementRect(1, 0, 2, 2))

    def test_type2_landmark_spacing_rejects_nearby_placements(self):
        fine = 5
        road_cells = {(0, y) for y in range(fine)}
        lots = C.find_lots(road_cells, fine)
        catalog = [
            C.Building("010", 2, 9, 9, {"type": 2}),
            C.Building("011", 2, 9, 9, {"type": 2}),
            C.Building("012", 2, 9, 9, {"type": 2}),
        ]
        rules = C.PlacementRules(banned_buildings=set())
        state = rules.new_state(random.Random(1))

        placements = C.place_city(
            road_cells,
            lots,
            catalog,
            fine,
            rng=random.Random(5),
            rules=rules,
            rule_state=state,
            type2_frontage_cells=road_cells,
            landmark_spacing=3,
        )

        type2 = [p for p in placements if p.building.type == 2]
        self.assertEqual([p.building.num for p in type2], ["012", "011"])
        self.assertEqual([p.rect for p in type2], [C.PlacementRect(1, 0, 1, 1), C.PlacementRect(1, 3, 1, 1)])


class IsometricRendererTests(unittest.TestCase):
    def test_render_grid_visible_iso_draws_visible_blocks(self):
        inv = {0: "minecraft:air", 1: "minecraft:stone"}
        grid = np.zeros((2, 2, 2), dtype=np.int32)
        grid[0, 0, 0] = 1
        grid[0, 1, 0] = 1
        image = render_grid_visible_iso(grid, inv, tile_w=8, tile_h=4, block_h=4, margin=2)

        self.assertEqual(image.mode, "RGBA")
        self.assertGreater(image.width, 0)
        self.assertGreater(image.height, 0)
        self.assertGreater(image.getchannel("A").getextrema()[1], 0)


if __name__ == "__main__":
    unittest.main()
