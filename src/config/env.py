"""Typed readers for ``MC_CITY_*`` environment overrides; the base of the config layer."""

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
    """Comma/semicolon-separated string set, falling back to ``default``."""
    value = env_raw(name)
    if value is None:
        return set(default)
    return {part.strip() for part in value.replace(";", ",").split(",") if part.strip()}
