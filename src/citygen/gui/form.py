"""The algorithm form Preview and Build share: which knobs show, and how the form's values become an ``Algo``.

Each knob names one :class:`config.algo.Algo` field, upper-cased. Its value is text, as the page sends it. The form's
words -- each knob's label and tip, the groups' names, the selectors' option names -- are in the page's text.js, keyed
by the codes here.
"""

from __future__ import annotations

from dataclasses import replace

from citygen.settings import ALGO, DEFAULT_SEED


class ConfigError(ValueError):
    """A knob's value is invalid. Its message is the knob's name, which the page words."""


# Every knob, in the order the form's values are kept.
KNOBS = [
    "FINE",
    "GAP_MIXED",
    "GAP_BIG",
    "PAD_BIG",
    "GAP_SMALL",
    "PAD_SMALL",
    "N_BIG_CORNERS",
    "N_BIG_TEES",
    "N_SMALL_CORNERS",
    "N_SMALL_TEES",
    "BANNED_BUILDINGS",
    "TYPE1_TOP_FIT_CHOICES",
    "LANDMARK_SPACING",
]

# The header's selectors: knobs chosen from a few values, which text.js names.
SELECTOR_OPTIONS = {
    "FINE": ("40", "60", "80", "100", "120"),
    "GAP_MIXED": ("3", "4", "5", "6", "7"),
}

# The advanced panel's groups, by code; it builds fields only for grouped knobs.
GROUPS = [
    ("spacing", ["GAP_BIG", "PAD_BIG", "GAP_SMALL", "PAD_SMALL"]),
    ("shape", ["N_BIG_CORNERS", "N_BIG_TEES", "N_SMALL_CORNERS", "N_SMALL_TEES"]),
    ("buildings", ["TYPE1_TOP_FIT_CHOICES", "LANDMARK_SPACING", "BANNED_BUILDINGS"]),
]

SLIDER_RANGES = {
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

# Knobs typed as text: a comma-separated set, which becomes a ``frozenset`` field.
SET_KNOBS = {"BANNED_BUILDINGS"}


def _default(name):
    value = getattr(ALGO, name.lower())
    return ", ".join(sorted(value)) if isinstance(value, frozenset) else str(value)


def form_values(saved=None):
    """Every knob's value: the saved one, else the default.

    A selector's saved value that isn't one of its options is dropped, as are the option labels older versions saved.
    """
    values = {}
    for name in KNOBS:
        value = str(saved[name]).strip() if saved and name in saved else None
        if value is None or (name in SELECTOR_OPTIONS and value not in SELECTOR_OPTIONS[name]):
            value = _default(name)
        values[name] = value
    return values


def build_algo(values):
    """The :class:`config.algo.Algo` that :func:`form_values` describes; raises :class:`ConfigError`."""
    knobs = {}
    for name in KNOBS:
        value = values[name]
        if name in SET_KNOBS:
            knobs[name.lower()] = frozenset(part.strip() for part in value.replace(";", ",").split(",") if part.strip())
            continue
        if name in SELECTOR_OPTIONS and value not in SELECTOR_OPTIONS[name]:
            raise ConfigError(name)
        try:
            knobs[name.lower()] = int(value)
        except ValueError as exc:
            raise ConfigError(name) from exc
    return replace(ALGO, **knobs)


def default_state():
    """The Preview and Build tabs' saved state as a fresh install has it."""
    return {"seed": str(DEFAULT_SEED), "algo": form_values()}


def form_spec():
    """The form the page builds: the header's selectors and the advanced panel's groups."""

    def field(name):
        if name in SET_KNOBS:
            return {"name": name, "kind": "text"}
        minimum, maximum = SLIDER_RANGES.get(name, (-99999, 99999))
        return {"name": name, "kind": "slider", "min": minimum, "max": maximum}

    return {
        "selectors": [{"name": name, "options": list(options)} for name, options in SELECTOR_OPTIONS.items()],
        "groups": [{"code": code, "fields": [field(name) for name in names]} for code, names in GROUPS],
    }
