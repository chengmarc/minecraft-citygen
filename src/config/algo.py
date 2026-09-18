"""Algorithm tuning for grid generation and city placement.

:class:`Algo` holds the per-run knobs; the engine takes one as an argument and
never reads :data:`ALGO`, which is only this process's default (the dataclass
defaults under any ``MC_CITY_*`` overrides) for the pipeline to fall back on.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

from config.env import env_int, env_set

CELL = 9  # simulation pixels and production blocks per fine cell; fixed by the asset geometry
DEFAULT_SEED = env_int("DEFAULT_SEED", 5)


@dataclass(frozen=True)
class Algo:
    fine: int = 80  # fine grid edge (fine x fine cells); rounded down to even, since coarse = fine // 2

    # forced gap between parallel lines
    gap_mixed: int = 5  # fine-cell clearance between a small street and a big corridor band
    gap_big: int = 5  # coarse-cell spacing step between big avenues (higher = fewer big roads)
    gap_small: int = 5  # min fine-cell spacing between small streets (lower = more small roads)

    # forced padding from canvas edge
    pad_big: int = 5  # coarse-cell padding for big road positions from the grid edge
    pad_small: int = 5  # fine-cell padding for small road positions from the grid edge

    # forced L-corners and T-intersections
    n_big_corners: int = 5
    n_small_corners: int = 5
    n_big_tees: int = 5
    n_small_tees: int = 5

    banned_buildings: frozenset[str] = frozenset()  # building IDs to skip during placement
    landmark_spacing: int = 5  # min fine-cell distance between landmark footprints
    type1_top_fit_choices: int = 5  # each type-1 frontage point picks randomly among this many best fits

    @classmethod
    def from_env(cls) -> "Algo":
        """The defaults, each overridden by ``MC_CITY_<FIELD>`` when set."""
        defaults = cls()
        values = {}
        for field in fields(cls):
            name, default = field.name.upper(), getattr(defaults, field.name)
            values[field.name] = frozenset(env_set(name, default)) if isinstance(default, frozenset) else env_int(name, default)
        return cls(**values)


ALGO = Algo.from_env()
