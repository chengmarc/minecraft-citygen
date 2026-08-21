import numpy as np

from config import version_compat as vc
from engine.schematic_writer import sponge_schem_from_cells, sponge_schem_from_grid

V194 = vc.data_version_for("1.19.4")
LATEST = vc.FALLBACK_DATA_VERSION


def test_cells_path_renames_below_threshold():
    cells = [[["minecraft:short_grass"]]]
    _, palette = sponge_schem_from_cells(cells, V194)
    assert "minecraft:grass" in palette
    assert "minecraft:short_grass" not in palette


def test_cells_path_unchanged_at_latest():
    cells = [[["minecraft:short_grass"]]]
    _, palette = sponge_schem_from_cells(cells, LATEST)
    assert "minecraft:short_grass" in palette
    assert "minecraft:grass" not in palette


def _grid_palette_keys(file):
    # v3 nests the palette under Schematic.Blocks; v2 (used for pre-1.20
    # targets like 1.19.4) keeps it directly under the root Schematic tag.
    if "Schematic" in file:
        return set(file["Schematic"]["Blocks"]["Palette"].keys())
    return set(file["Palette"].keys())


def test_grid_path_renames_and_preserves_properties():
    palette = {"minecraft:air": 0, "minecraft:iron_chain[axis=y]": 1}
    grid = np.array([[[1]]], dtype=np.int16)
    file = sponge_schem_from_grid(grid, palette, V194)
    keys = _grid_palette_keys(file)
    assert "minecraft:chain[axis=y]" in keys
    assert "minecraft:iron_chain[axis=y]" not in keys


def test_grid_path_collapses_colliding_ids_after_rename():
    # short_grass and a pre-existing grass must merge to one palette entry.
    palette = {"minecraft:grass": 0, "minecraft:short_grass": 1}
    grid = np.array([[[0, 1]]], dtype=np.int16)
    file = sponge_schem_from_grid(grid, palette, V194)
    assert _grid_palette_keys(file) == {"minecraft:grass"}
