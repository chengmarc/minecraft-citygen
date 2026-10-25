"""The extracted road pieces by kind: the road network's tiles, the fill props, and the ground fill.

Everything extracted from the road area lands in one folder, told apart by name: a piece whose two-character prefix is
a tile's in the road catalogue is a network tile; any other named with ``fill`` is a fill prop, dropped into empty lot
cells; asset 18 is the ground fill, laid under every empty lot cell.
"""

from __future__ import annotations

import glob
import os
from typing import NamedTuple

from citygen.core.road_network import iter_tile_catalogue
from citygen.tools.schem import read_tile, Tile

_FILL_TOKEN = "fill"
_GROUND_FILL_PREFIX = "18"
_ROAD_TILE_PREFIXES = frozenset(name[:2] for _layer, _base, name in iter_tile_catalogue())


def _pieces(roads_dir):
    return sorted(glob.glob(os.path.join(roads_dir, "*.schem")))


def fill_prop_paths(roads_dir):
    """The fill props among the extracted road pieces, in the order build and preview both draw from."""
    return [
        path for path in _pieces(roads_dir)
        if _FILL_TOKEN in os.path.basename(path) and os.path.basename(path)[:2] != _GROUND_FILL_PREFIX
    ]


class RoadPieces(NamedTuple):
    tiles: dict[str, Tile]  # network tiles by prefix ("02")
    fill_props: list[Tile]
    ground_fill: Tile


def load_road_pieces(roads_dir):
    """Every road piece extracted into ``roads_dir``, as Tiles; raises if the ground fill is missing."""
    paths = _pieces(roads_dir)
    tiles = {os.path.basename(path)[:2]: read_tile(path) for path in paths
             if os.path.basename(path)[:2] in _ROAD_TILE_PREFIXES}
    ground_fill = next((path for path in paths if os.path.basename(path)[:2] == _GROUND_FILL_PREFIX), None)
    if ground_fill is None:
        raise FileNotFoundError("missing road ground-fill asset 18 among the extracted road pieces; extract again")
    return RoadPieces(tiles, [read_tile(path) for path in fill_prop_paths(roads_dir)], read_tile(ground_fill))
