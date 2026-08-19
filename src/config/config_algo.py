"""Algorithm tuning for grid generation and city placement."""

from __future__ import annotations

import os


def _env_int(name, default):
    return int(os.environ.get(f"MC_CITY_{name}", default))


def _env_set(name, default):
    raw = os.environ.get(f"MC_CITY_{name}")
    if raw is None:
        return set(default)
    return {part.strip() for part in raw.replace(";", ",").split(",") if part.strip()}


CELL = _env_int("CELL", 9)              # simulation pixels and production blocks per fine cell
FINE = _env_int("FINE", 120)            # default fine grid edge (FINE x FINE cells); drivers may override
DEFAULT_SEED = _env_int("DEFAULT_SEED", 4)

# forced gap between parallel lines
GAP_MIXED = _env_int("GAP_MIXED", 5)    # fine-cell clearance between a small street and a big corridor band
GAP_BIG = _env_int("GAP_BIG", 8)        # coarse-cell spacing step between big avenues (higher = fewer big roads)
GAP_SMALL = _env_int("GAP_SMALL", 4)    # min fine-cell spacing between small streets (lower = more small roads)

# forced padding from canvas edge
PAD_BIG = _env_int("PAD_BIG", 4)        # coarse-cell padding for big road positions from the grid edge
PAD_SMALL = _env_int("PAD_SMALL", 6)    # fine-cell padding for small road positions from the grid edge

# forced L-corners and T-intersections
N_BIG_CORNERS = _env_int("N_BIG_CORNERS", 6)
N_SMALL_CORNERS = _env_int("N_SMALL_CORNERS", 8)
N_BIG_TEES = _env_int("N_BIG_TEES", 6)
N_SMALL_TEES = _env_int("N_SMALL_TEES", 8)

BANNED_BUILDINGS = _env_set("BANNED_BUILDINGS", {"026", "030"})  # building IDs to skip during placement

TYPE2_TOP_FIT_CHOICES = _env_int("TYPE2_TOP_FIT_CHOICES", 3)
TYPE1_TOP_FIT_CHOICES = _env_int("TYPE1_TOP_FIT_CHOICES", 7)

# Type-2 buildings cannot repeat inside the same coarse-cell window.
TYPE2_SAME_COARSE_SPAN = _env_int("TYPE2_SAME_COARSE_SPAN", 6)
