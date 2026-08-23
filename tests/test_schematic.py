"""Schematic transforms, block-entity handling, and Sponge container versioning.

The Sponge container version is chosen by the target's WorldEdit, not the blocks:
WorldEdit 7.3.0 (Minecraft 1.20+) added the v3 container; the 7.2.x line shipping
with 1.19.x reads only v2 and rejects v3. The writer therefore emits v2 below
DataVersion 3463 (1.20) and v3 at or above it.
"""
import numpy as np
import pytest
from nbtlib import Compound, String

from engine.schematic.reader import (
    decode_schem_block_entities,
    decode_schem_cells,
    decode_schem_offset,
)
from engine.schematic.transform import Tile, BlockEntity, rot_state, rot_tile
from engine.schematic.writer import (
    SPONGE_V3_MIN_DATA_VERSION,
    sponge_schem_from_cells,
    sponge_schem_from_grid,
    write_sponge_schem_cells,
    write_sponge_schem_grid,
)

V2 = 3337       # Minecraft 1.19.4, the hard floor and only release in [1.19.4, 1.20)
V120 = 3463     # Minecraft 1.20, the v2 -> v3 container threshold
V3 = 3700       # >= 1.20 -> Sponge v3 container
LATEST = 4000   # any DataVersion well above the v3 threshold


# --- transforms -----------------------------------------------------------

def test_rot_state_rotates_directional_properties():
    state = "minecraft:oak_stairs[east=none,facing=north,half=bottom,north=low,shape=straight,south=tall,waterlogged=false]"
    assert rot_state(state, 1) == (
        "minecraft:oak_stairs[east=low,facing=east,half=bottom,shape=straight,south=none,waterlogged=false,west=tall]"
    )


def test_rot_state_rotates_standing_sign_rotation():
    # rotation is 0-15 around the compass; a 90 deg CW turn adds 4 (mod 16).
    assert rot_state("minecraft:oak_sign[rotation=0]", 1) == "minecraft:oak_sign[rotation=4]"
    assert rot_state("minecraft:oak_sign[rotation=14]", 1) == "minecraft:oak_sign[rotation=2]"


def test_rot_tile_rotates_dimensions_cells_and_preserves_ground_offset():
    tile = Tile(
        2,
        1,
        3,
        [[
            ["a", "b"],
            ["c", "d"],
            ["minecraft:oak_log[axis=x]", "minecraft:oak_stairs[facing=north]"],
        ]],
        ground_offset=3,
    )

    rotated = rot_tile(tile, 1)

    assert (rotated.width, rotated.height, rotated.length) == (3, 1, 2)
    assert rotated.cells[0][0][0] == "minecraft:oak_log[axis=z]"
    assert rotated.cells[0][0][1] == "c"
    assert rotated.cells[0][0][2] == "a"
    assert rotated.cells[0][1][0] == "minecraft:oak_stairs[facing=east]"
    assert rotated.ground_offset == 3


def test_rot_tile_moves_block_entity_with_its_cell():
    # 3 wide x 2 long tile; a BE sits at (x=0, z=0). One CW turn sends a cell at
    # (x, z) to (length - 1 - z, x) -> (1, 0) for length=2.
    cells = [[["a", "b", "c"], ["d", "e", "f"]]]  # height 1, length 2, width 3
    tile = Tile(3, 1, 2, cells, block_entities=(BlockEntity(0, 0, 0, "minecraft:x", Compound()),))
    rotated = rot_tile(tile, 1)
    assert (rotated.width, rotated.length) == (2, 3)
    assert len(rotated.block_entities) == 1
    be = rotated.block_entities[0]
    assert (be.x, be.y, be.z) == (1, 0, 0)


# --- block-entity round-trips --------------------------------------------

def _sign(x, y, z, text):
    return BlockEntity(x, y, z, "minecraft:oak_sign", Compound({"Text1": String(text)}))


@pytest.mark.parametrize("data_version", [V2, V3])
def test_cells_roundtrip_preserves_block_entity(tmp_path, data_version):
    cells = [[["minecraft:oak_sign[rotation=0]"]]]
    be = _sign(0, 0, 0, '{"text":"hello"}')
    path = tmp_path / "sign.schem"
    write_sponge_schem_cells(cells, str(path), data_version, block_entities=[be])

    got = decode_schem_block_entities(str(path))
    assert len(got) == 1
    assert (got[0].x, got[0].y, got[0].z) == (0, 0, 0)
    assert got[0].id == "minecraft:oak_sign"
    assert str(got[0].data["Text1"]) == '{"text":"hello"}'


def test_grid_roundtrip_preserves_block_entity_position(tmp_path):
    grid = np.zeros((2, 3, 4), dtype=np.int16)  # (height, length, width)
    grid[1, 2, 3] = 1
    palette = {"minecraft:air": 0, "minecraft:chest[facing=north]": 1}
    be = BlockEntity(3, 1, 2, "minecraft:chest", Compound({"LootTable": String("minecraft:chests/x")}))
    path = tmp_path / "chest.schem"
    write_sponge_schem_grid(grid, palette, str(path), V3, block_entities=[be])

    got = decode_schem_block_entities(str(path))
    assert len(got) == 1
    assert (got[0].x, got[0].y, got[0].z) == (3, 1, 2)
    assert got[0].id == "minecraft:chest"


# --- container versioning ------------------------------------------------

def _cells_file(data_version):
    file, _ = sponge_schem_from_cells([[["minecraft:stone"]]], data_version)
    return file


def _grid_file(data_version):
    grid = np.array([[[0]]], dtype=np.int16)
    return sponge_schem_from_grid(grid, {"minecraft:stone": 0}, data_version)


def _assert_v2(file):
    # v2: fields sit directly under a root tag named "Schematic" (no wrapper),
    # block data is "BlockData", palette carries "PaletteMax".
    assert file.root_name == "Schematic"
    assert "Schematic" not in file
    assert int(file["Version"]) == 2
    assert "BlockData" in file
    assert int(file["PaletteMax"]) == len(file["Palette"])


def _assert_v3(file):
    # v3: everything nested under a "Schematic" key, block data under Blocks.Data.
    assert "Schematic" in file
    schem = file["Schematic"]
    assert int(schem["Version"]) == 3
    assert "Data" in schem["Blocks"]
    assert "BlockData" not in schem


def test_cells_container_boundary_is_exact():
    assert SPONGE_V3_MIN_DATA_VERSION == V120 == 3463
    # One below the threshold is v2; exactly the threshold is v3.
    _assert_v2(_cells_file(SPONGE_V3_MIN_DATA_VERSION - 1))
    _assert_v3(_cells_file(SPONGE_V3_MIN_DATA_VERSION))


def test_grid_emits_versioned_container():
    _assert_v2(_grid_file(V2))
    _assert_v3(_grid_file(LATEST))


def test_both_containers_carry_target_data_version():
    assert int(_cells_file(V2)["DataVersion"]) == V2
    assert int(_cells_file(LATEST)["Schematic"]["DataVersion"]) == LATEST


def test_reader_round_trips_both_containers(tmp_path):
    # The render step reads schematics straight back after extraction; a v2 file
    # must decode without tripping the reader's v3 "Schematic" child lookup.
    cells = [[["minecraft:stone", "minecraft:air"]], [["minecraft:oak_planks", "minecraft:stone"]]]
    for data_version in (V2, LATEST):
        path = tmp_path / f"round-{data_version}.schem"
        write_sponge_schem_cells(cells, str(path), data_version)
        assert decode_schem_cells(str(path)) == cells
        assert decode_schem_offset(str(path)) == (0, 0, 0)
