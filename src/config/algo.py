"""Algorithm tuning for grid generation and city placement."""

from __future__ import annotations

from config.env import env_int, env_set

CELL = env_int("CELL", 9)              # simulation pixels and production blocks per fine cell
FINE = env_int("FINE", 80)            # default fine grid edge (FINE x FINE cells); drivers may override
DEFAULT_SEED = env_int("DEFAULT_SEED", 5)

# forced gap between parallel lines
GAP_MIXED = env_int("GAP_MIXED", 5)    # fine-cell clearance between a small street and a big corridor band
GAP_BIG = env_int("GAP_BIG", 5)        # coarse-cell spacing step between big avenues (higher = fewer big roads)
GAP_SMALL = env_int("GAP_SMALL", 5)    # min fine-cell spacing between small streets (lower = more small roads)

# forced padding from canvas edge
PAD_BIG = env_int("PAD_BIG", 5)        # coarse-cell padding for big road positions from the grid edge
PAD_SMALL = env_int("PAD_SMALL", 5)    # fine-cell padding for small road positions from the grid edge

# forced L-corners and T-intersections
N_BIG_CORNERS = env_int("N_BIG_CORNERS", 5)
N_SMALL_CORNERS = env_int("N_SMALL_CORNERS", 5)
N_BIG_TEES = env_int("N_BIG_TEES", 5)
N_SMALL_TEES = env_int("N_SMALL_TEES", 5)

BANNED_BUILDINGS = env_set("BANNED_BUILDINGS", set())  # building IDs to skip during placement

LANDMARK_SPACING = env_int("LANDMARK_SPACING", 5)  # min fine-cell distance between landmark footprints
TYPE1_TOP_FIT_CHOICES = env_int("TYPE1_TOP_FIT_CHOICES", 5)
