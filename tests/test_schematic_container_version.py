"""Sponge container version is chosen by the target's WorldEdit, not the blocks.

WorldEdit 7.3.0 (Minecraft 1.20+) introduced the Sponge v3 container; the 7.2.x
line shipping with 1.19.x and earlier reads only v2 and rejects v3 outright. The
writer therefore emits v2 below DataVersion 3463 (1.20) and v3 at or above it.
"""
import os
import tempfile

import numpy as np

from engine.schematic.reader import decode_schem_cells, decode_schem_offset
from engine.schematic.writer import (
    SPONGE_V3_MIN_DATA_VERSION,
    sponge_schem_from_cells,
    sponge_schem_from_grid,
    write_sponge_schem_cells,
)

# 1.19.4 is the hard floor and the only release in the v2 window [1.19.4, 1.20).
V194 = 3337    # Minecraft 1.19.4, the hard floor
V120 = 3463    # Minecraft 1.20, the v2 -> v3 container threshold
LATEST = 4000  # any DataVersion well above the v3 threshold


def _cells_file(data_version):
    file, _ = sponge_schem_from_cells([[["minecraft:stone"]]], data_version)
    return file


def _grid_file(data_version):
    palette = {"minecraft:stone": 0}
    grid = np.array([[[0]]], dtype=np.int16)
    return sponge_schem_from_grid(grid, palette, data_version)


def _assert_v2(file):
    # v2: fields sit directly under a root tag named "Schematic" (no wrapper),
    # block data is "BlockData", palette carries "PaletteMax".
    assert file.root_name == "Schematic"
    assert "Schematic" not in file
    assert int(file["Version"]) == 2
    assert "BlockData" in file
    assert "Blocks" not in file
    assert int(file["PaletteMax"]) == len(file["Palette"])


def _assert_v3(file):
    # v3: everything nested under a "Schematic" key, block data under Blocks.Data.
    assert "Schematic" in file
    schem = file["Schematic"]
    assert int(schem["Version"]) == 3
    assert "Blocks" in schem
    assert "Data" in schem["Blocks"]
    assert "BlockData" not in schem


def test_threshold_matches_minecraft_1_20():
    assert SPONGE_V3_MIN_DATA_VERSION == V120 == 3463


def test_cells_pre_1_20_targets_emit_v2():
    _assert_v2(_cells_file(V194))


def test_cells_1_20_and_later_emit_v3():
    _assert_v3(_cells_file(V120))
    _assert_v3(_cells_file(LATEST))


def test_grid_pre_1_20_targets_emit_v2():
    _assert_v2(_grid_file(V194))


def test_grid_1_20_and_later_emit_v3():
    _assert_v3(_grid_file(V120))
    _assert_v3(_grid_file(LATEST))


def test_boundary_is_exact():
    # One below the threshold is v2; exactly the threshold is v3.
    _assert_v2(_cells_file(SPONGE_V3_MIN_DATA_VERSION - 1))
    _assert_v3(_cells_file(SPONGE_V3_MIN_DATA_VERSION))


def test_both_containers_carry_target_data_version():
    v2 = _cells_file(V194)
    assert int(v2["DataVersion"]) == V194
    v3 = _cells_file(LATEST)
    assert int(v3["Schematic"]["DataVersion"]) == LATEST


def test_reader_round_trips_both_containers():
    # The render step reads schematics straight back after extraction; a v2 file
    # must decode without tripping the reader's v3 "Schematic" child lookup.
    cells = [[["minecraft:stone", "minecraft:air"]], [["minecraft:oak_planks", "minecraft:stone"]]]
    for data_version in (V194, LATEST):
        fd, path = tempfile.mkstemp(suffix=".schem")
        os.close(fd)
        try:
            write_sponge_schem_cells(cells, path, data_version)
            assert decode_schem_cells(path) == cells
            assert decode_schem_offset(path) == (0, 0, 0)
        finally:
            os.remove(path)
