"""Schematic transforms, block-entity handling, the Sponge v3 container, and city ground fill."""
from types import SimpleNamespace

import numpy as np
import nbtlib
from nbtlib import Byte, Compound, String

from citygen.settings import CELL
from citygen import schem
from citygen import build
from citygen.schem import (
    decode_schem_block_entities,
    decode_schem_cells,
    decode_schem_offset,
)
from citygen.schem import Tile, BlockEntity, rot_state, rot_tile
from citygen.schem import (
    sponge_schem_from_cells,
    sponge_schem_from_grid,
    write_sponge_schem_cells,
    write_sponge_schem_grid,
)

V2612 = 4790
LATEST = 4903


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
    return BlockEntity(x, y, z, "minecraft:oak_sign", Compound({
        "is_waxed": Byte(0),
        "front_text": Compound({"messages": nbtlib.List[String]([String(text)])}),
    }))


def test_cells_roundtrip_preserves_block_entity(tmp_path):
    cells = [[["minecraft:oak_sign[rotation=0]"]]]
    be = _sign(0, 0, 0, '{"text":"hello"}')
    path = tmp_path / "sign.schem"
    write_sponge_schem_cells(cells, str(path), V2612, block_entities=[be])

    got = decode_schem_block_entities(str(path))
    assert len(got) == 1
    assert (got[0].x, got[0].y, got[0].z) == (0, 0, 0)
    assert got[0].id == "minecraft:oak_sign"
    assert str(got[0].data["front_text"]["messages"][0]) == '{"text":"hello"}'


def test_grid_roundtrip_preserves_block_entity_position(tmp_path):
    grid = np.zeros((2, 3, 4), dtype=np.int16)  # (height, length, width)
    grid[1, 2, 3] = 1
    palette = {"minecraft:air": 0, "minecraft:chest[facing=north]": 1}
    be = BlockEntity(3, 1, 2, "minecraft:chest", Compound({"LootTable": String("minecraft:chests/x")}))
    path = tmp_path / "chest.schem"
    write_sponge_schem_grid(grid, palette, str(path), LATEST, block_entities=[be])

    got = decode_schem_block_entities(str(path))
    assert len(got) == 1
    assert (got[0].x, got[0].y, got[0].z) == (3, 1, 2)
    assert got[0].id == "minecraft:chest"


# --- v3 container --------------------------------------------------------

def _cells_file(data_version):
    file, _ = sponge_schem_from_cells([[["minecraft:stone"]]], data_version)
    return file


def _grid_file(data_version):
    grid = np.array([[[0]]], dtype=np.int16)
    return sponge_schem_from_grid(grid, {"minecraft:stone": 0}, data_version)


def _assert_v3(file):
    # v3: everything nested under a "Schematic" key, block data under Blocks.Data.
    assert "Schematic" in file
    schem = file["Schematic"]
    assert int(schem["Version"]) == 3
    assert "Data" in schem["Blocks"]
    assert "BlockData" not in schem


def test_cells_and_grid_emit_v3_container():
    _assert_v3(_cells_file(V2612))
    _assert_v3(_grid_file(V2612))


def test_container_carries_target_data_version():
    assert int(_cells_file(LATEST)["Schematic"]["DataVersion"]) == LATEST


def test_reader_round_trips_written_cells(tmp_path):
    # The render step reads schematics straight back after extraction.
    cells = [[["minecraft:stone", "minecraft:air"]], [["minecraft:oak_planks", "minecraft:stone"]]]
    path = tmp_path / "round.schem"
    write_sponge_schem_cells(cells, str(path), V2612)
    assert decode_schem_cells(str(path)) == cells
    assert decode_schem_offset(str(path)) == (0, 0, 0)


def test_road_asset_loaders_keep_network_tiles_fill_props_and_ground_fill_separate(tmp_path):
    write_sponge_schem_cells(
        [[["minecraft:stone"]]],
        str(tmp_path / "02_big_2x2_I.schem"),
        V2612,
        offset=(0, -1, 0),
    )
    write_sponge_schem_cells(
        [[["minecraft:oak_log"]]],
        str(tmp_path / "15_fill_1x1_A.schem"),
        V2612,
        offset=(0, -2, 0),
    )
    write_sponge_schem_cells(
        [[["minecraft:moss_block"]]],
        str(tmp_path / "18_empty_fill.schem"),
        V2612,
        offset=(0, -3, 0),
    )
    tiles = build.load_tiles(str(tmp_path))
    fillers = build.load_fillers(str(tmp_path))
    ground_fill = build.load_ground_fill_tile(str(tmp_path))

    assert set(tiles) == {"02"}
    assert tiles["02"].ground_offset == 1
    assert len(fillers) == 1
    assert fillers[0].ground_offset == 2
    assert ground_fill is not None
    assert ground_fill.ground_offset == 3


def test_building_assembly_uses_piece_shape_not_placement_type(tmp_path):
    write_sponge_schem_cells([[["minecraft:bottom"]]], str(tmp_path / "001_bottom.schem"), V2612)
    write_sponge_schem_cells([[["minecraft:middle"]]], str(tmp_path / "001_middle.schem"), V2612)
    write_sponge_schem_cells([[["minecraft:top"]]], str(tmp_path / "001_top.schem"), V2612)
    write_sponge_schem_cells([[["minecraft:whole"]]], str(tmp_path / "002.schem"), V2612)

    stacked = schem.assemble(str(tmp_path), "001", 2, {
        "001": {"type": 1, "pieces": {"bottom": 1, "middle": 1, "top": 1}},
    })
    whole = schem.assemble(str(tmp_path), "002", 0, {
        "002": {"type": 2, "pieces": {"whole": 1}},
    })

    assert [layer[0][0] for layer in stacked.cells] == [
        "minecraft:bottom",
        "minecraft:middle",
        "minecraft:middle",
        "minecraft:top",
    ]
    assert whole.cells == [[["minecraft:whole"]]]


def test_building_pieces_are_reread_after_a_new_extraction(tmp_path):
    # The app is one process: a second extraction rewrites the same 001.schem,
    # and every later read must see the new building, not the cached old one.
    catalog = {"001": {"type": 1, "pieces": {"whole": 1}}}
    write_sponge_schem_cells([[["minecraft:quartz_block"]]], str(tmp_path / "001.schem"), V2612)
    assert schem.assemble(str(tmp_path), "001", 0, catalog).cells == [[["minecraft:quartz_block"]]]

    write_sponge_schem_cells([[["minecraft:mossy_cobblestone"]]], str(tmp_path / "001.schem"), V2612)
    assert schem.assemble(str(tmp_path), "001", 0, catalog).cells == [[["minecraft:mossy_cobblestone"]]]


# --- city ground fill ----------------------------------------------------

def _fill_first_cell(tile, **kwargs):
    """Ground-fill a 12x12 grid with ``ground_y=3``; return its first cell's columns."""
    grid = np.zeros((6, 12, 12), dtype=np.int16)
    build.place_ground_fill(
        grid,
        {"minecraft:air": 0},
        np.zeros((12, 12), dtype=bool),
        road_cells=set(),
        size=SimpleNamespace(fine=1),
        ground_y=3,
        ground_fill_tile=tile,
        **kwargs,
    )
    z0 = x0 = build.PLAYER_ANCHOR_MARGIN
    return grid[:, z0:z0 + CELL, x0:x0 + CELL]


def test_city_ground_fill_tops_out_at_the_shared_ground_plane():
    tile = Tile(width=1, height=1, length=1, cells=[[["minecraft:moss_block"]]], ground_offset=0)

    cell = _fill_first_cell(tile)

    assert np.count_nonzero(cell[3]) == CELL ** 2
    assert np.count_nonzero(cell[2]) == 0


def test_city_ground_fill_ground_offset_sinks_the_tile_below_the_plane():
    tile = Tile(width=1, height=1, length=1, cells=[[["minecraft:oak_planks"]]], ground_offset=1)

    cell = _fill_first_cell(tile)

    assert np.count_nonzero(cell[2]) == CELL ** 2


def test_city_ground_fill_skips_cells_with_fill_props():
    tile = Tile(width=1, height=1, length=1, cells=[[["minecraft:dirt"]]], ground_offset=0)

    cell = _fill_first_cell(tile, skip_cells={(0, 0)})

    assert np.count_nonzero(cell) == 0
