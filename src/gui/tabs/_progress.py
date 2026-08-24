"""Shared progress constants for GUI tabs."""

from pipeline import services

PROGRESS_BAR_SCALE = 1000

# Pipeline-progress ticks are tagged with their stage module. Each tab maps that
# module to a step index so the status reads consistently, e.g.
# "Stage 1/2 - pipeline/04_city/construct.py - <detail>".
GENERATION_STAGE_STEPS = {
    services.CITY_CONSTRUCT: 1,
    services.CITY_RENDER: 2,
    services.WORLD_EXPORT: 3,
}
GENERATION_TOTAL_STEPS = len(GENERATION_STAGE_STEPS)

# Extract runs four scripts in sequence: roads then builds, each extract + render.
EXTRACT_STAGE_STEPS = {
    services.ROADS_EXTRACT: 1,
    services.ROADS_RENDER: 2,
    services.BUILDS_EXTRACT: 3,
    services.BUILDS_RENDER: 4,
}
EXTRACT_TOTAL_STEPS = len(EXTRACT_STAGE_STEPS)
