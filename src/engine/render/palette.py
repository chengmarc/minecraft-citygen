"""Shared block color helpers for renderer modules."""

from __future__ import annotations

import csv

from config.path import COLOR_RENDER_CSV
from config.render import UNKNOWN_BLOCK_RGBA


UNKNOWN = UNKNOWN_BLOCK_RGBA


def load_render_colors(path=COLOR_RENDER_CSV):
    colors = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            block = (row.get("block_name") or "").strip()
            r, g, b = ((row.get(key) or "").strip() for key in ("r", "g", "b"))
            if not block or not r or not g or not b:
                continue
            colors[block] = (int(r), int(g), int(b))
    return colors


COLORS = load_render_colors()


def block_id(state):
    """Return a namespaced block id from a block state or base name."""
    name = str(state).split("[", 1)[0]
    return name if ":" in name else f"minecraft:{name}"


def is_air(state):
    return block_id(state) in {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}


def block_color(state, default=UNKNOWN):
    return COLORS.get(block_id(state), default)
