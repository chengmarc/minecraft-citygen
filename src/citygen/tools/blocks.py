"""MC block states: ``name[prop=val,...]`` parsing and formatting, air, and each block's render colour."""

from __future__ import annotations

import csv

from citygen.paths import COLOR_RENDER_CSV

AIR_BLOCKS = frozenset({"minecraft:air", "minecraft:cave_air", "minecraft:void_air"})


def parse_state(state):
    """Split ``name[prop=val,...]`` into (name, properties_dict_or_None)."""
    if "[" not in state:
        return state, None
    name, rest = state.split("[", 1)
    props = {}
    for pair in rest.rstrip("]").split(","):
        key, _, value = pair.partition("=")
        props[key] = value
    return name, props


def format_state(name, props):
    """Inverse of :func:`parse_state`, with properties in sorted key order."""
    if not props:
        return name
    return name + "[" + ",".join(f"{key}={props[key]}" for key in sorted(props)) + "]"


def block_id(state):
    """Return a namespaced block id from a block state or base name."""
    name = str(state).split("[", 1)[0]
    return name if ":" in name else f"minecraft:{name}"


def is_air(state):
    return state in AIR_BLOCKS or block_id(state) in AIR_BLOCKS


# --- Render colours, from data/color_render.csv

UNKNOWN_BLOCK_RGBA = (255, 0, 255)


def load_render_colors():
    """Each block's render colour: its vivid_* columns, or the sampled r/g/b where a row has none."""
    colors = {}
    with open(COLOR_RENDER_CSV, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            block = (row.get("block_name") or "").strip()
            keys = ("vivid_r", "vivid_g", "vivid_b") if (row.get("vivid_r") or "").strip() else ("r", "g", "b")
            r, g, b = ((row.get(key) or "").strip() for key in keys)
            if not block or not r or not g or not b:
                continue
            colors[block] = (int(r), int(g), int(b))
    return colors


COLORS = load_render_colors()


def block_color(state):
    return COLORS.get(block_id(state), UNKNOWN_BLOCK_RGBA)
