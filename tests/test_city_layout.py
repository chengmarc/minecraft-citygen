import random
import unittest

from engine.core import city_layout as C


class CityLayoutTests(unittest.TestCase):
    def test_generated_placements_validate(self):
        fine = 6
        road_cells = {(0, y) for y in range(fine)}
        lots = C.find_lots(road_cells, fine)
        catalog = [C.Building("001", 1, 9, 9, {"type": 1})]

        placements = C.place_city(
            road_cells,
            lots,
            catalog,
            fine,
            rng=random.Random(5),
            type2_frontage_cells=road_cells,
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


if __name__ == "__main__":
    unittest.main()
