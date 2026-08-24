"""Shared progress constants for GUI tabs."""

from pipeline import services

PROGRESS_BAR_SCALE = 1000

# Extract runs four scripts in sequence: roads then builds, each extract + render.
EXTRACT_STAGE_STEPS = {
    services.ROADS_EXTRACT: 1,
    services.ROADS_RENDER: 2,
    services.BUILDS_EXTRACT: 3,
    services.BUILDS_RENDER: 4,
}
