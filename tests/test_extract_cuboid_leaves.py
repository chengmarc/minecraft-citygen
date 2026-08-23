"""extract_cuboid leaf-persistence transform.

Grown leaves (persistent=false) decay after a paste unless a log stays in range;
for a stable export we rewrite them to persistent=true. The transform must touch
only leaves, only the persistent flag, and only when explicitly enabled.
"""
from engine.world.marker_extract import extract_cuboid


class _FakeWorld:
    """Returns a fixed (name, props) for every column, ignoring coordinates."""

    def __init__(self, name, props):
        self._name = name
        self._props = props

    def block(self, x, y, z):
        return self._name, (dict(self._props) if self._props else None)

    def load_chunk(self, cx, cz):
        return None  # no block entities in this fake


def _single(world, *, force):
    # A 1x1x1 cuboid -> cells[0][0][0] is the one block state string.
    cells, _block_entities = extract_cuboid(world, (0, 0, 0, 0, 0, 0), force_persistent_leaves=force)
    return cells[0][0][0]


def test_grown_leaves_forced_persistent():
    world = _FakeWorld("minecraft:cherry_leaves", {"distance": "7", "persistent": "false"})
    assert _single(world, force=True) == "minecraft:cherry_leaves[distance=7,persistent=true]"


def test_grown_leaves_untouched_when_disabled():
    world = _FakeWorld("minecraft:cherry_leaves", {"distance": "7", "persistent": "false"})
    assert _single(world, force=False) == "minecraft:cherry_leaves[distance=7,persistent=false]"


def test_already_persistent_leaves_unchanged():
    world = _FakeWorld("minecraft:oak_leaves", {"distance": "1", "persistent": "true"})
    assert _single(world, force=True) == "minecraft:oak_leaves[distance=1,persistent=true]"


def test_non_leaf_blocks_untouched():
    # "persistent" would never appear here, but guard against over-broad matching.
    world = _FakeWorld("minecraft:stone", None)
    assert _single(world, force=True) == "minecraft:stone"
