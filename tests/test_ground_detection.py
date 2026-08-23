"""Source-world ground detection and the extraction search-window shift.

Assets are authored on a flat terrain surface; detection recovers that surface
Y (via a column scan, not the paste-stale heightmap) so extraction follows the
ground plane wherever the source world is seated.
"""
from engine.world.marker_extract import detect_source_ground_y, ground_shift


def _chunk_tops(surface_y):
    """Build a 256-entry top_solid_blocks array from a ``(x, z) -> y`` callable.

    Columns are indexed ``z_local * 16 + x_local`` and world coords are the
    caller's absolute block positions -- matching the real World API.
    """
    def blocks(cx, cz):
        entries = []
        for col in range(256):
            x = (cx << 4) + (col & 15)
            z = (cz << 4) + (col >> 4)
            entries.append(("minecraft:grass_block", surface_y(x, z)))
        return entries
    return blocks


class _FakeWorld:
    """Flat ground at ``ground_y``; a sparse grid of columns raised (builds)."""

    def __init__(self, ground_y, empty=False):
        self.ground_y = ground_y
        self.empty = empty

    def is_chunk_empty(self, cx, cz):
        return self.empty

    def top_solid_blocks(self, cx, cz):
        raised = lambda x, z: self.ground_y + (8 if (x % 20 == 0 and z % 20 == 0) else 0)
        return _chunk_tops(raised)(cx, cz)


class _RoadDenseWorld:
    """Most columns at a raised road surface; grass ground exposed in a minority."""

    def __init__(self, ground_y, road_y):
        self.ground_y = ground_y
        self.road_y = road_y

    def is_chunk_empty(self, cx, cz):
        return False

    def top_solid_blocks(self, cx, cz):
        # ~1/3 of columns show bare ground, the rest the higher road surface.
        surface = lambda x, z: self.ground_y if (x + z) % 3 == 0 else self.road_y
        return _chunk_tops(surface)(cx, cz)


def test_detects_ground_plane():
    # Ground dominates; the sparse raised columns must not sway detection.
    assert detect_source_ground_y(_FakeWorld(-61), -272, 47, -272, 47) == -61
    assert detect_source_ground_y(_FakeWorld(63), -80, -17, -256, -145) == 63


def test_ground_is_lowest_common_surface_not_the_mode():
    # The road surface (-58) is the *most common* level, but ground is -61; the
    # detector must return the lower broadly-present plane, not the mode.
    assert detect_source_ground_y(_RoadDenseWorld(-61, -58), -80, -17, -256, -145) == -61


def test_detect_returns_none_for_empty_region():
    assert detect_source_ground_y(_FakeWorld(0, empty=True), 0, 15, 0, 15) is None


def test_ground_shift_is_delta_from_reference():
    # New 1.19.4 world (ground -61) against the config reference (63) -> -124.
    assert ground_shift(_FakeWorld(-61), -80, -17, -256, -145, 63) == -124
    # A world already at the reference needs no shift.
    assert ground_shift(_FakeWorld(63), -80, -17, -256, -145, 63) == 0


def test_ground_shift_zero_when_undetectable():
    # Undetectable ground preserves the configured absolute windows.
    assert ground_shift(_FakeWorld(0, empty=True), 0, 15, 0, 15, 63) == 0
