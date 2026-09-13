"""Shared progress-bar weights, milestones, and creep settings."""

from __future__ import annotations

from pipeline import services

PROGRESS_BAR_SCALE = 1000

EXTRACTION_PHASE_WEIGHTS = [
    (services.ROADS_EXTRACT, "scan", 1),
    (services.ROADS_EXTRACT, "export", 5),
    (services.ROADS_RENDER, "render", 3),
    (services.BUILDS_EXTRACT, "scan", 8),
    (services.BUILDS_EXTRACT, "export", 50),
    (services.BUILDS_RENDER, "render", 33),
]

PREVIEW_STEP_WEIGHTS = [8, 8, 15, 69]

GENERATION_CONSTRUCT_WEIGHTS = [1, 1, 1, 1, 22, 4, 4, 16]
GENERATION_RENDER_WEIGHT = 5
GENERATION_WORLD_WEIGHT = 45

PROGRESS_CREEP = {
    "default": {"headroom": 0.90, "tick_ms": 120},
    "extraction": {"headroom": 0.90, "tick_ms": 120},
    "preview": {"headroom": 0.95, "tick_ms": 60},
    "generation": {"headroom": 0.90, "tick_ms": 120},
}

PROGRESS_CREEP_RATE = 0.10


def creep_headroom(tab_name):
    return PROGRESS_CREEP.get(tab_name, PROGRESS_CREEP["default"])["headroom"]


def creep_tick_ms(tab_name):
    return PROGRESS_CREEP.get(tab_name, PROGRESS_CREEP["default"])["tick_ms"]


def weighted_milestone(weights, completed_steps, maximum):
    step = max(0, min(int(completed_steps), len(weights)))
    total = sum(weights) or 1
    return int(round(sum(weights[:step]) / total * maximum))


def weighted_segment(weights, index, maximum):
    index = max(0, min(int(index), len(weights) - 1))
    start = weighted_milestone(weights, index, maximum)
    end = weighted_milestone(weights, index + 1, maximum)
    return start, end


def weighted_item_milestone(weights, index, completed, total, maximum):
    start, end = weighted_segment(weights, index, maximum)
    total_f = float(total) if total > 0 else 1.0
    completed_f = max(0.0, min(float(completed), total_f))
    return start + completed_f / total_f * (end - start)


def soft_target(milestone, next_milestone, tab_name):
    return milestone + (next_milestone - milestone) * creep_headroom(tab_name)
