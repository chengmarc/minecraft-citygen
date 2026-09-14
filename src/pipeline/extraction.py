"""Small shared helpers for extraction stages."""

from __future__ import annotations

import os


def chunk_scan_count(x0, x1, z0, z1):
    """Number of region chunks touched by an x/z block rectangle."""
    return ((max(x0, x1) >> 4) - (min(x0, x1) >> 4) + 1) * (
        (max(z0, z1) >> 4) - (min(z0, z1) >> 4) + 1
    )


def remove_existing_schems(directory):
    """Delete stale Sponge schematic outputs from ``directory``."""
    for filename in os.listdir(directory):
        if filename.endswith(".schem"):
            os.remove(os.path.join(directory, filename))
