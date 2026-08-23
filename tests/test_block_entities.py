"""Block-entity preservation: write -> read round-trip and transform behaviour."""

import numpy as np
import pytest
from nbtlib import Compound, String

from engine.schematic.reader import decode_schem_block_entities
from engine.schematic.transform import (
    BlockEntity,
    Tile,
    rot_state,
    rot_tile,
    translate_block_entities,
)
from engine.schematic.writer import write_sponge_schem_cells, write_sponge_schem_grid

V2 = 3337   # 1.19.4 -> Sponge v2 container
V3 = 3700   # >= 1.20 -> Sponge v3 container


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


@pytest.mark.parametrize("data_version", [V2, V3])
def test_grid_roundtrip_preserves_block_entity_position(tmp_path, data_version):
    grid = np.zeros((2, 3, 4), dtype=np.int16)  # (height, length, width)
    grid[1, 2, 3] = 1
    palette = {"minecraft:air": 0, "minecraft:chest[facing=north]": 1}
    be = BlockEntity(3, 1, 2, "minecraft:chest", Compound({"LootTable": String("minecraft:chests/x")}))
    path = tmp_path / "chest.schem"
    write_sponge_schem_grid(grid, palette, str(path), data_version, block_entities=[be])

    got = decode_schem_block_entities(str(path))
    assert len(got) == 1
    assert (got[0].x, got[0].y, got[0].z) == (3, 1, 2)
    assert got[0].id == "minecraft:chest"


def test_no_block_entities_reads_empty(tmp_path):
    write_sponge_schem_cells([[["minecraft:stone"]]], str(tmp_path / "s.schem"), V3)
    assert decode_schem_block_entities(str(tmp_path / "s.schem")) == []


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


def test_translate_block_entities():
    bes = [BlockEntity(1, 2, 3, "minecraft:x", Compound())]
    moved = translate_block_entities(bes, 10, 20, 30)
    assert (moved[0].x, moved[0].y, moved[0].z) == (11, 22, 33)


def test_rot_state_rotates_standing_sign_rotation():
    # rotation is 0-15 around the compass; a 90 deg CW turn adds 4 (mod 16).
    assert rot_state("minecraft:oak_sign[rotation=0]", 1) == "minecraft:oak_sign[rotation=4]"
    assert rot_state("minecraft:oak_sign[rotation=14]", 1) == "minecraft:oak_sign[rotation=2]"
