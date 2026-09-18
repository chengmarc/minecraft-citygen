"""Minecraft block-id facts shared by the world reader/writer and renderers."""

from __future__ import annotations

AIR_BLOCKS = frozenset({"minecraft:air", "minecraft:cave_air", "minecraft:void_air"})


def block_id(state):
    """Return a namespaced block id from a block state or base name."""
    name = str(state).split("[", 1)[0]
    return name if ":" in name else f"minecraft:{name}"


def is_air(state):
    return block_id(state) in AIR_BLOCKS
