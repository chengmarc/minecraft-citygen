"""Each tab's run bar: a hand-tuned weight per step its run reports, where each report puts the bar, and the bar's
segments.

Everything is keyed by tab (``extract``, ``preview``, ``build``), then by the step codes each tab's run reports (see
``run`` in citygen.step1_extract, citygen.step2_preview and citygen.step3_build). The bar runs from 0 to PROGRESS_BAR_SCALE. A report
becomes ``(value, soft_target, detail)``: where the bar jumps, where it creeps toward until the next report, and the
words that stand in for the running segment's name (or None).
"""

from __future__ import annotations

PROGRESS_BAR_SCALE = 1000

# Construction reports each of its eight steps (citygen.step3_build.STEPS) as it starts it.
CONSTRUCT_WEIGHTS = [1, 1, 1, 1, 22, 4, 4, 16]

WEIGHTS = {
    "extract": {
        "scan_roads": 1, "road_pieces": 5, "road_sheet": 3, "scan_builds": 8, "build_pieces": 50, "build_sheet": 33,
    },
    "preview": {"road_pieces": 8, "build_pieces": 8, "road_layout": 15, "city_layout": 69},
    "build": {**{f"construct.{n}": weight for n, weight in enumerate(CONSTRUCT_WEIGHTS)}, "render": 5, "world": 45},
}

# The run bar's segments, in step order: each one's code (text.js names it), and how many of the tab's steps it spans.
# Build groups construction's eight steps: road network and grid; catalog and placements; assembly, voxels and trees;
# the schematic. Then the render and the world export.
SEGMENTS = {
    "extract": [(step, 1) for step in WEIGHTS["extract"]],
    "preview": [(step, 1) for step in WEIGHTS["preview"]],
    "build": [("roads", 2), ("placement", 2), ("buildings", 3), ("schematic", 1), ("render", 1), ("world", 1)],
}

# What stands in for each Preview segment's name while it runs.
PREVIEW_DETAILS = {
    "road_pieces": "Generating road preview assets",
    "build_pieces": "Generating building preview assets",
    "road_layout": "Rendering road layout preview",
    "city_layout": "Rendering city layout preview",
}

# How far toward the next milestone the bar creeps, and how often it moves.
CREEP = {
    "extract": {"headroom": 0.90, "tick_ms": 120},
    "preview": {"headroom": 0.95, "tick_ms": 60},
    "build": {"headroom": 0.90, "tick_ms": 120},
}
CREEP_RATE = 0.10

# Extract's reports are coalesced into this many buckets per step, so the bar isn't sent events that don't move it.
EXTRACT_PROGRESS_BUCKETS = 100


def tick_ms(tab):
    return CREEP[tab]["tick_ms"]


def _milestone(weights, index):
    """Where step ``index`` starts, in bar units."""
    return int(round(sum(weights[:index]) / (sum(weights) or 1) * PROGRESS_BAR_SCALE))


def _position(tab, index, completed, total):
    """``(value, soft_target)`` for ``completed`` of ``total`` through step ``index``; at its end, no soft target."""
    weights = list(WEIGHTS[tab].values())
    start, end = _milestone(weights, index), _milestone(weights, index + 1)
    total = float(total) if total > 0 else 1.0
    completed = max(0.0, min(float(completed), total))
    value = start + completed / total * (end - start)
    if completed >= total:
        return value, None
    next_value = start + (completed + 1.0) / total * (end - start)
    return value, value + (next_value - value) * CREEP[tab]["headroom"]


def bar(tab, step, completed, total, detail=None):
    """A report's ``(value, soft_target, detail)`` on ``tab``'s bar.

    Construction reports ``completed`` as the step it's starting, out of eight, with its name as the detail.
    """
    steps = list(WEIGHTS[tab])
    if step == "construct":
        n = int(completed)
        done = n >= len(CONSTRUCT_WEIGHTS)
        value, target = _position(tab, steps.index(f"construct.{min(n, len(CONSTRUCT_WEIGHTS) - 1)}"), int(done), 1)
        return value, target, None if done else detail
    value, target = _position(tab, steps.index(step), completed, total)
    return value, target, PREVIEW_DETAILS[step] if tab == "preview" else None


def segment_spans(weights, segments):
    """Each ``(code, count)`` segment as ``{"code", "start", "end"}``, in percent of the whole run."""
    total = sum(weights) or 1
    spans = []
    index = 0
    done = 0
    for code, count in segments:
        size = sum(weights[index:index + count])
        spans.append({"code": code, "start": done * 100 / total, "end": (done + size) * 100 / total})
        index += count
        done += size
    return spans


def run_segments():
    """Every tab's run-bar segments, for the page."""
    return {tab: segment_spans(list(WEIGHTS[tab].values()), segments) for tab, segments in SEGMENTS.items()}


def coalesce(report):
    """Extract's ``report(step, completed, total, detail)``, dropping the reports that wouldn't move the bar but keeping
    each step's completion."""
    last_key = None

    def on_progress(step, completed, total, detail=None):
        nonlocal last_key
        total_i = max(int(total), 1)
        completed_i = max(0, min(int(completed), total_i))
        buckets = EXTRACT_PROGRESS_BUCKETS
        bucket = buckets if completed_i >= total_i else int((completed_i * buckets) / total_i)
        key = (step, total_i, bucket)
        if key == last_key:
            return
        last_key = key
        report(step, float(completed_i), float(total_i), detail)

    return on_progress
