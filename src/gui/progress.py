"""Each tab's run bar: its hand-tuned weight per pipeline step, how the pipeline's progress lands on it, its segments,
and the timings recorded to re-tune the weights.

Everything is keyed by tab: ``extract``, ``preview``, ``build``. The bar runs from 0 to PROGRESS_BAR_SCALE. A step's
``(value, soft_target, detail)`` is where the bar jumps, where it creeps toward until the next event, and the
pipeline's own name for the step under way (or None).
"""

from __future__ import annotations

import time

from pipeline import stages

PROGRESS_BAR_SCALE = 1000

# Stages 1-2, each extraction step split into its scan and its export.
EXTRACT_PHASE_WEIGHTS = [
    (stages.ROADS_EXTRACT, "scan", 1),
    (stages.ROADS_EXTRACT, "export", 5),
    (stages.ROADS_RENDER, "render", 3),
    (stages.BUILDS_EXTRACT, "scan", 8),
    (stages.BUILDS_EXTRACT, "export", 50),
    (stages.BUILDS_RENDER, "render", 33),
]

PREVIEW_STEP_WEIGHTS = [8, 8, 15, 69]

BUILD_CONSTRUCT_WEIGHTS = [1, 1, 1, 1, 22, 4, 4, 16]
BUILD_RENDER_WEIGHT = 5
BUILD_WORLD_WEIGHT = 45

WEIGHTS = {
    "extract": [weight for _stage, _phase, weight in EXTRACT_PHASE_WEIGHTS],
    "preview": PREVIEW_STEP_WEIGHTS,
    "build": BUILD_CONSTRUCT_WEIGHTS + [BUILD_RENDER_WEIGHT, BUILD_WORLD_WEIGHT],
}

# The run bar's segments, in step order: each one's code (text.js names it), and how many of the tab's weights it
# spans. Build groups construction's eight steps: road network and grid; catalog and placements; assembly, voxels and
# trees; the schematic. Then the render and the world export.
SEGMENTS = {
    "extract": [
        ("scan_roads", 1), ("road_pieces", 1), ("road_sheet", 1),
        ("scan_builds", 1), ("build_pieces", 1), ("build_sheet", 1),
    ],
    "preview": [("road_pieces", 1), ("build_pieces", 1), ("road_layout", 1), ("city_layout", 1)],
    "build": [("roads", 2), ("placement", 2), ("buildings", 3), ("schematic", 1), ("render", 1), ("world", 1)],
}

# How far toward the next milestone the bar creeps, and how often it moves.
CREEP = {
    "extract": {"headroom": 0.90, "tick_ms": 120},
    "preview": {"headroom": 0.95, "tick_ms": 60},
    "build": {"headroom": 0.90, "tick_ms": 120},
}
CREEP_RATE = 0.10

# Extracting coalesces its progress into this many buckets per phase, so the bar isn't sent events that don't move it.
EXTRACT_PROGRESS_BUCKETS = 100

_PREVIEW_STEPS = {step.module: (index, step.label) for index, step in enumerate(stages.STAGES["preview"])}


def tick_ms(tab):
    return CREEP[tab]["tick_ms"]


def soft_target(milestone, next_milestone, tab):
    return milestone + (next_milestone - milestone) * CREEP[tab]["headroom"]


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
    return {tab: segment_spans(WEIGHTS[tab], segments) for tab, segments in SEGMENTS.items()}


# --- Extract: Stages 1 then 2

def extract_phase(stage, detail):
    """``scan``, ``export`` or ``render``: an extraction step scans first, and says so in its detail."""
    if stage in (stages.ROADS_EXTRACT, stages.BUILDS_EXTRACT):
        return "scan" if (detail or "").startswith(stages.SCANNING) else "export"
    return "render"


_EXTRACT_PHASE_INDEX = {(stage, phase): index for index, (stage, phase, _weight) in enumerate(EXTRACT_PHASE_WEIGHTS)}


def coalesce_extract_progress(emit):
    """Drop extraction progress events that wouldn't move the bar, keeping each phase's completion."""
    last_key = None

    def on_progress(stage, completed, total, label):
        nonlocal last_key
        total_i = max(int(total), 1)
        completed_i = max(0, min(int(completed), total_i))
        buckets = EXTRACT_PROGRESS_BUCKETS
        bucket = buckets if completed_i >= total_i else int((completed_i * buckets) / total_i)
        key = (stage, extract_phase(stage, label), total_i, bucket)
        if key == last_key:
            return
        last_key = key
        emit(stage, float(completed_i), float(total_i), label)

    return on_progress


def extract_progress(stage, phase, completed, total):
    """An extraction phase's ``(value, soft_target, None)``: no detail, as each phase is a segment the page names."""
    weights = WEIGHTS["extract"]
    phase_index = _EXTRACT_PHASE_INDEX[(stage, phase)]
    total_f = float(total) if total > 0 else 1.0
    completed_f = max(0.0, min(float(completed), total_f))
    if completed_f >= total_f:
        return weighted_segment(weights, phase_index, PROGRESS_BAR_SCALE)[1], None, None
    value = weighted_item_milestone(weights, phase_index, completed_f, total_f, PROGRESS_BAR_SCALE)
    next_value = weighted_item_milestone(weights, phase_index, completed_f + 1.0, total_f, PROGRESS_BAR_SCALE)
    return value, soft_target(value, next_value, "extract"), None


# --- Preview: Stage 3

def preview_progress(stage, completed, total):
    """A Stage 3 step's ``(value, soft_target, detail)``; the detail is the step's name."""
    step_index, step_label = _PREVIEW_STEPS[stage]
    total_f = float(total) if total > 0 else 1.0
    completed_f = max(0.0, min(float(completed), total_f))

    def milestone(done):
        return weighted_item_milestone(WEIGHTS["preview"], step_index, done, total_f, PROGRESS_BAR_SCALE)

    value = milestone(completed_f)
    target = None
    if completed_f < total_f:
        target = soft_target(value, milestone(completed_f + 1.0), "preview")
    return value, target, step_label


# --- Build: Stage 4 then 5

def build_progress(stage, completed, total, label=""):
    """A Stage 4 or 5 step's ``(value, soft_target, detail)``.

    Construction names the step it's starting in ``label``, which is the detail; the other steps have none.
    """
    weights = WEIGHTS["build"]
    construct_steps = len(BUILD_CONSTRUCT_WEIGHTS)
    n = int(completed)
    detail = label if stage == stages.CITY_CONSTRUCT and label and n < construct_steps else None

    if stage == stages.CITY_CONSTRUCT:
        value = weighted_milestone(weights, n, PROGRESS_BAR_SCALE)
        target = None
        if n < construct_steps:
            target = soft_target(value, weighted_milestone(weights, n + 1, PROGRESS_BAR_SCALE), "build")
        return value, target, detail

    segment = construct_steps if stage == stages.CITY_RENDER else construct_steps + 1
    t = float(total) if total > 0 else 1.0
    value = weighted_item_milestone(weights, segment, n, t, PROGRESS_BAR_SCALE)
    target = None
    if n < total:
        target = soft_target(value, weighted_item_milestone(weights, segment, n + 1, t, PROGRESS_BAR_SCALE), "build")
    return value, target, detail


# --- Timings, to re-tune the weights from

_TIMING_PREFIXES = {
    stages.ROADS_EXTRACT: "roads",
    stages.ROADS_RENDER: "roads",
    stages.BUILDS_EXTRACT: "builds",
    stages.BUILDS_RENDER: "builds",
}
_BUILD_TIMING_KEYS = {stages.CITY_CONSTRUCT: "construct", stages.CITY_RENDER: "render", stages.WORLD_EXPORT: "export"}


def _timing_key(tab, event):
    """The weight an event's time counts toward: ``roads_scan`` and the like for Extract, a stage's for Build."""
    if tab == "extract":
        prefix = _TIMING_PREFIXES.get(event["stage"])
        return None if prefix is None else f"{prefix}_{event['phase']}"
    return _BUILD_TIMING_KEYS.get(event["stage"])


def _timing_weights(tab):
    """The weights in use, recorded beside the timings they're tuned from."""
    if tab == "extract":
        return {f"{stage}:{phase}": weight for stage, phase, weight in EXTRACT_PHASE_WEIGHTS}
    return {"construct": list(BUILD_CONSTRUCT_WEIGHTS), "render": BUILD_RENDER_WEIGHT, "export": BUILD_WORLD_WEIGHT}


class ProgressTimingRecorder:
    """Times one Extract or Build run, from its creation, step by step."""

    def __init__(self, tab):
        self.tab = tab
        self.started_at = time.perf_counter()
        self.last = None
        self.events = []

    def record(self, stage, completed, total, label, *, phase=None):
        now = time.perf_counter()
        completed_i = int(completed)
        total_i = int(total)
        label = label or ""
        key = (stage, phase, completed_i, total_i, label)
        if self.last is not None and self.last["key"] != key:
            self.events.append(self._event_from_last(now))
        if self.last is None or self.last["key"] != key:
            self.last = {
                "key": key,
                "stage": stage,
                "phase": phase,
                "completed": completed_i,
                "total": total_i,
                "label": label,
                "time": now,
            }

    def finish(self):
        """The run's timings: in total, per weight, and per event, with the weights they were taken under."""
        now = time.perf_counter()
        if self.last is not None:
            self.events.append(self._event_from_last(now))

        phase_seconds = {}
        for event in self.events:
            key = _timing_key(self.tab, event)
            if key is not None:
                phase_seconds[key] = phase_seconds.get(key, 0.0) + event["seconds"]

        return {
            "total_seconds": round(now - self.started_at, 4),
            "phase_seconds": {key: round(value, 4) for key, value in phase_seconds.items()},
            "events": self.events,
            "weights": _timing_weights(self.tab),
        }

    def _event_from_last(self, now):
        return {
            "stage": self.last["stage"],
            "phase": self.last["phase"],
            "completed": self.last["completed"],
            "total": self.last["total"],
            "label": self.last["label"],
            "seconds": round(now - self.last["time"], 4),
        }
