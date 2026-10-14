"""Shared block color helpers for renderer modules."""

from __future__ import annotations

import csv

from config.path import COLOR_RENDER_CSV
from config.render import UNKNOWN_BLOCK_RGBA
from engine.blocks import block_id



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
