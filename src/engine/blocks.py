"""Minecraft block-state strings: ``name[prop=val,...]`` parsing, formatting, and air."""

from __future__ import annotations

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
