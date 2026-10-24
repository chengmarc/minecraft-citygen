"""Core generation engine: road networks, city layout, isometric rendering."""
import random
import unittest

import numpy as np

from citygen.settings import Algo
from citygen.core import city_layout as C
from citygen.core import road_network as R
from citygen.tools.render_isometric import render_grid_visible_iso


def _network_snapshot(net):
    return {key: sorted(net[key].items() if isinstance(net[key], dict) else net[key]) for key in (
        "big_rows", "big_cols", "big_rows_ext", "big_cols_ext",
        "small_rows", "small_cols", "small_rows_ext", "small_cols_ext",
        "road_cells",
    )}


class RoadNetworkTests(unittest.TestCase):
    def test_seeded_generation_is_stable(self):
        size = R.make_size(40)
        first = _network_snapshot(R.gen_networks(17, size, Algo()))
        second = _network_snapshot(R.gen_networks(17, size, Algo()))
        different = _network_snapshot(R.gen_networks(18, size, Algo()))

        self.assertEqual(first, second)
        self.assertNotEqual(first, different)

    def test_generation_follows_the_algo_argument(self):
        size = R.make_size(40)
        default = _network_snapshot(R.gen_networks(17, size, Algo()))
        sparse = _network_snapshot(R.gen_networks(17, size, Algo(gap_small=10)))

        self.assertNotEqual(default["small_rows"], sparse["small_rows"])


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

        placements = C.place_city(
            road_cells,
            lots,
            [building],
            fine,
            rng=random.Random(5),
            type2_frontage_cells=road_cells,
        )

        self.assertEqual(len([p for p in placements if p.building.num == "010"]), 1)

    def test_type2_buildings_place_largest_first(self):
        fine = 6
        road_cells = {(0, y) for y in range(fine)}
        lots = C.find_lots(road_cells, fine)
        small = C.Building("010", 2, 9, 9, {"type": 2})
        large = C.Building("020", 2, 18, 18, {"type": 2})

        placements = C.place_city(
            road_cells,
            lots,
            [small, large],
            fine,
            rng=random.Random(5),
            type2_frontage_cells=road_cells,
            algo=Algo(landmark_spacing=0),
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

        placements = C.place_city(
            road_cells,
            lots,
            catalog,
            fine,
            rng=random.Random(5),
            type2_frontage_cells=road_cells,
            algo=Algo(landmark_spacing=3),
        )

        type2 = [p for p in placements if p.building.type == 2]
        self.assertEqual([p.building.num for p in type2], ["012", "011"])
        self.assertEqual([p.rect for p in type2], [C.PlacementRect(1, 0, 1, 1), C.PlacementRect(1, 3, 1, 1)])


    def test_load_catalog_skips_banned_ids_in_any_spelling(self):
        catalog_meta = {"001": {"type": 1, "size": [9, 9]}, "002": {"type": 1, "size": [9, 9]}}

        buildings = C.load_catalog(catalog_meta, banned_buildings={"1"})

        self.assertEqual([b.num for b in buildings], ["002"])


class IsometricRendererTests(unittest.TestCase):
    def test_render_grid_visible_iso_draws_visible_blocks(self):
        inv = {0: "minecraft:air", 1: "minecraft:stone"}
        grid = np.zeros((2, 2, 2), dtype=np.int32)
        grid[0, 0, 0] = 1
        grid[0, 1, 0] = 1
        image = render_grid_visible_iso(grid, inv, tile_w=8, tile_h=4, block_h=4)

        self.assertGreater(image.getchannel("A").getextrema()[1], 0)


if __name__ == "__main__":
    unittest.main()


def test_render_colors_prefer_vivid_columns_and_fall_back_to_sampled_rgb(tmp_path, monkeypatch):
    # color_render.csv contract: renders use vivid_*; a row whose vivid_* is blank
    # (e.g. hand-added) still renders with its sampled r/g/b instead of vanishing.
    from citygen.tools import blocks as palette

    csv_path = tmp_path / "colors.csv"
    csv_path.write_text(
        "block_name,r,g,b,vivid_r,vivid_g,vivid_b\n"
        "minecraft:dirt,100,80,60,120,80,40\n"
        "minecraft:stone,90,90,90,,,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(palette, "COLOR_RENDER_CSV", str(csv_path))

    assert palette.load_render_colors() == {"minecraft:dirt": (120, 80, 40), "minecraft:stone": (90, 90, 90)}


def test_contact_sheet_is_transparent_between_thumbnails(tmp_path):
    from PIL import Image

    from citygen.tools.contact_sheet import write_contact

    thumb = Image.new("RGBA", (20, 20), (200, 40, 40, 255))
    sheet = write_contact([("a", thumb)], tmp_path / "sheet.png", cols=2, cell_w=60, cell_h=60)

    assert sheet.getpixel((sheet.width - 1, sheet.height - 1))[3] == 0   # the empty second cell
    assert Image.open(tmp_path / "sheet.png").mode == "RGBA"


def test_city_render_is_trimmed_to_what_is_drawn_with_its_margin():
    from PIL import Image

    from citygen.tools.render_isometric import trim_to_content

    image = Image.new("RGBA", (200, 300), (0, 0, 0, 0))
    image.paste((90, 120, 60, 255), (40, 150, 160, 280))   # the city, low on a tall canvas

    trimmed = trim_to_content(image, margin=10)

    assert trimmed.size == (140, 150)
    assert trimmed.getchannel("A").getbbox() == (10, 10, 130, 140)
    assert trim_to_content(Image.new("RGBA", (5, 5)), margin=10).size == (5, 5)   # nothing drawn: as it was

