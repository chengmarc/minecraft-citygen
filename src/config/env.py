"""Typed readers for ``MC_CITY_*`` configuration overrides.

Every tunable in :mod:`config` can be overridden by an environment variable named
``MC_CITY_<NAME>``. These helpers centralise how that environment is read so each
config module applies the same override contract: a variable that is unset -- or
set to an empty/whitespace-only string -- falls back to the provided default.

The readers hold no state; they consult ``os.environ`` on every call, so the
in-process reload mechanism (see :mod:`pipeline.runtime`) picks up overrides simply
by re-importing the config module that calls them -- ``env`` itself never needs
reloading.
"""

from __future__ import annotations

import os

PREFIX = "MC_CITY_"


def env_raw(name: str) -> str | None:
    """Raw value of ``MC_CITY_<name>``, or ``None`` when unset or blank."""
    value = os.environ.get(f"{PREFIX}{name}")
    if value is None or not value.strip():
        return None
    return value


def env_str(name: str, default: str) -> str:
    """String override, falling back to ``default`` when unset or blank."""
    value = env_raw(name)
    return default if value is None else value


def env_int(name: str, default: int) -> int:
    """Integer override, falling back to ``default`` when unset or blank."""
    value = env_raw(name)
    return default if value is None else int(value.strip())


def env_set(name: str, default) -> set[str]:
    """Comma/semicolon-separated string set, falling back to ``default``.

    ``default`` is copied into a fresh set so callers can pass a literal without
    it being shared across reloads.
    """
    value = env_raw(name)
    if value is None:
        return set(default)
    return {part.strip() for part in value.replace(";", ",").split(",") if part.strip()}
