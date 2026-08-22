"""Algorithm tuning for grid generation and city placement."""

from __future__ import annotations

from config.env import env_int, env_set

CELL = env_int("CELL", 9)              # simulation pixels and production blocks per fine cell
FINE = env_int("FINE", 80)            # default fine grid edge (FINE x FINE cells); drivers may override
DEFAULT_SEED = env_int("DEFAULT_SEED", 4)

# forced gap between parallel lines
GAP_MIXED = env_int("GAP_MIXED", 5)    # fine-cell clearance between a small street and a big corridor band
GAP_BIG = env_int("GAP_BIG", 8)        # coarse-cell spacing step between big avenues (higher = fewer big roads)
GAP_SMALL = env_int("GAP_SMALL", 4)    # min fine-cell spacing between small streets (lower = more small roads)

# forced padding from canvas edge
PAD_BIG = env_int("PAD_BIG", 4)        # coarse-cell padding for big road positions from the grid edge
PAD_SMALL = env_int("PAD_SMALL", 6)    # fine-cell padding for small road positions from the grid edge

# forced L-corners and T-intersections
N_BIG_CORNERS = env_int("N_BIG_CORNERS", 6)
N_SMALL_CORNERS = env_int("N_SMALL_CORNERS", 8)
N_BIG_TEES = env_int("N_BIG_TEES", 6)
N_SMALL_TEES = env_int("N_SMALL_TEES", 8)

BANNED_BUILDINGS = env_set("BANNED_BUILDINGS", {"001", "002"})  # building IDs to skip during placement

TYPE2_TOP_FIT_CHOICES = env_int("TYPE2_TOP_FIT_CHOICES", 3)
TYPE1_TOP_FIT_CHOICES = env_int("TYPE1_TOP_FIT_CHOICES", 7)

# Type-2 buildings cannot repeat inside the same coarse-cell window.
TYPE2_SAME_COARSE_SPAN = env_int("TYPE2_SAME_COARSE_SPAN", 6)
