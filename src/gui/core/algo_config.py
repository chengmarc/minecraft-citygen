"""Algorithm settings form: which knobs the GUI shows and how they become an ``Algo``.

Each knob names one :class:`config.algo.Algo` field, upper-cased.
"""

from __future__ import annotations

from dataclasses import replace

from config.algo import ALGO, DEFAULT_SEED
from config.env import parse_set


class SeedError(ValueError):
    """Raised when the seed field does not hold a valid integer."""


class ConfigError(ValueError):
    """Raised when an algorithm/city config value is invalid."""


PREVIEW_CONFIGS = [
    ("FINE", "City Size", "Changes the footprint of the finished city."),
    ("GAP_MIXED", "Road Density", "Controls how tightly Avenues and Streets are packed across the city."),
    ("GAP_BIG", "Avenue Spacing", "Higher values create fewer Avenues."),
    ("PAD_BIG", "Avenue Edge Margin", "Keeps Avenues farther from the edge of the city."),
    ("GAP_SMALL", "Street Spacing", "Lower values create more Streets."),
    ("PAD_SMALL", "Street Edge Margin", "Keeps Streets farther from the edge of the city."),
    ("N_BIG_CORNERS", "Avenue Turns", "Adds more bends to Avenues."),
    ("N_BIG_TEES", "Avenue T-Junctions", "Adds more T-junctions to Avenues."),
    ("N_SMALL_CORNERS", "Street Turns", "Adds more bends to Streets."),
    ("N_SMALL_TEES", "Street T-Junctions", "Adds more T-junctions to Streets."),
    ("BANNED_BUILDINGS", "Skip Building IDs", "Optional comma-separated building IDs to leave out of generation."),
    ("TYPE1_TOP_FIT_CHOICES", "House Style Variety", "Higher values mix in more different standard house designs."),
    ("LANDMARK_SPACING", "Landmark Spacing", "Minimum fine-cell distance between landmark footprints."),
]

PREVIEW_CONFIG_LOOKUP = {name: (label, description) for name, label, description in PREVIEW_CONFIGS}

PREVIEW_CONFIG_GROUPS = [
    ("Avenue and Street Spacing", ["GAP_BIG", "PAD_BIG", "GAP_SMALL", "PAD_SMALL"]),
    ("Avenue and Street Shape", ["N_BIG_CORNERS", "N_BIG_TEES", "N_SMALL_CORNERS", "N_SMALL_TEES"]),
    ("Building Mix", ["TYPE1_TOP_FIT_CHOICES", "LANDMARK_SPACING", "BANNED_BUILDINGS"]),
]

PREVIEW_SLIDER_RANGES = {
    "GAP_BIG": (2, 10),
    "GAP_SMALL": (2, 10),
    "PAD_BIG": (2, 10),
    "PAD_SMALL": (2, 10),
    "N_BIG_CORNERS": (0, 10),
    "N_SMALL_CORNERS": (0, 10),
    "N_BIG_TEES": (0, 10),
    "N_SMALL_TEES": (0, 10),
    "TYPE1_TOP_FIT_CHOICES": (1, 10),
    "LANDMARK_SPACING": (1, 10),
}

CANVAS_SIZE_OPTIONS = {
    "Very Small": "40",
    "Small": "60",
    "Normal": "80",
    "Big": "100",
    "Very Big": "120",
}

CLEARANCE_OPTIONS = {
    "Very Dense": "3",
    "Dense": "4",
    "Normal": "5",
    "Sparse": "6",
    "Very Sparse": "7",
}

# Config values the header row exposes as labelled selectors rather than raw
# integers. Maps config name -> (label->value options, human-facing name).
SELECTOR_OPTIONS = {
    "FINE": (CANVAS_SIZE_OPTIONS, "City Size"),
    "GAP_MIXED": (CLEARANCE_OPTIONS, "Grid Density"),
}


def selector_value(name, label):
    """Resolve a selector label (e.g. 'Small') to its numeric config value."""
    options, human = SELECTOR_OPTIONS[name]
    try:
        return options[label]
    except KeyError as exc:
        raise ConfigError(f"{human} must be one of the selector values.") from exc


def selector_label(name, value):
    """Resolve a numeric config value back to its selector label, or None."""
    options, _human = SELECTOR_OPTIONS[name]
    for label, numeric in options.items():
        if str(value) == numeric:
            return label
    return None


def config_default(name):
    value = getattr(ALGO, name.lower())
    if isinstance(value, frozenset):
        return ", ".join(sorted(value))
    if name in SELECTOR_OPTIONS:
        label = selector_label(name, value)
        if label is not None:
            return label
    return str(value)


def algo_defaults_snapshot():
    return {name: config_default(name) for name, _label, _description in PREVIEW_CONFIGS}


def create_config_values(initial=None):
    values = algo_defaults_snapshot()
    if initial:
        for name in values:
            if name in initial:
                values[name] = str(initial[name])
    return values


def snapshot_config_values(config_values):
    return {
        name: str(config_values[name]).strip()
        for name, _label, _description in PREVIEW_CONFIGS
    }


def build_algo_from_values(config_values):
    """The :class:`config.algo.Algo` the form's text values describe."""
    normalized = snapshot_config_values(config_values)
    knobs = {}
    for name, _label, _description in PREVIEW_CONFIGS:
        value = normalized[name]
        if name == "BANNED_BUILDINGS":
            knobs[name.lower()] = frozenset(parse_set(value))
            continue
        if name in SELECTOR_OPTIONS:
            value = selector_value(name, value)
        try:
            knobs[name.lower()] = int(value)
        except ValueError as exc:
            raise ConfigError(f"{name} must be an integer.") from exc
    return replace(ALGO, **knobs)


def default_algo_tab_config():
    return {
        "seed": str(DEFAULT_SEED),
        "algo": algo_defaults_snapshot(),
    }


def validate_seed(seed):
    try:
        int(seed)
    except ValueError as exc:
        raise SeedError("Seed must be an integer.") from exc
