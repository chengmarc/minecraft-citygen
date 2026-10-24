"""Shared progress-bar weights, milestones, and creep settings."""

from __future__ import annotations

import time

from pipeline import stages

PROGRESS_BAR_SCALE = 1000

EXTRACTION_PHASE_WEIGHTS = [
    (stages.ROADS_EXTRACT, "scan", 1),
    (stages.ROADS_EXTRACT, "export", 5),
    (stages.ROADS_RENDER, "render", 3),
    (stages.BUILDS_EXTRACT, "scan", 8),
    (stages.BUILDS_EXTRACT, "export", 50),
    (stages.BUILDS_RENDER, "render", 33),
]

PREVIEW_STEP_WEIGHTS = [8, 8, 15, 69]

GENERATION_CONSTRUCT_WEIGHTS = [1, 1, 1, 1, 22, 4, 4, 16]
GENERATION_RENDER_WEIGHT = 5
GENERATION_WORLD_WEIGHT = 45
GENERATION_WEIGHTS = GENERATION_CONSTRUCT_WEIGHTS + [GENERATION_RENDER_WEIGHT, GENERATION_WORLD_WEIGHT]

# The run bar's segments, in step order: each one's label, and how many of the tab's weights it spans.
EXTRACTION_SEGMENTS = [
    ("Scan roads", 1),
    ("Road pieces", 1),
    ("Road sheet", 1),
    ("Scan buildings", 1),
    ("Building pieces", 1),
    ("Building sheet", 1),
]
PREVIEW_SEGMENTS = [("Road pieces", 1), ("Building pieces", 1), ("Road layout", 1), ("City layout", 1)]
# Construction's eight steps, grouped: road network and grid; catalog and placements; assembly, voxels and
# trees; the schematic. Then the render and the world export.
GENERATION_SEGMENTS = [
    ("Roads", 2),
    ("Placement", 2),
    ("Buildings", 3),
    ("Schematic", 1),
    ("Render", 1),
    ("World", 1),
]

PROGRESS_CREEP = {
    "default": {"headroom": 0.90, "tick_ms": 120},
    "preview": {"headroom": 0.95, "tick_ms": 60},
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


def segment_spans(weights, segments):
    """Each ``(label, count)`` segment as ``{"label", "start", "end"}``, in percent of the whole run."""
    total = sum(weights) or 1
    spans = []
    index = 0
    done = 0
    for label, count in segments:
        size = sum(weights[index:index + count])
        spans.append({"label": label, "start": done * 100 / total, "end": (done + size) * 100 / total})
        index += count
        done += size
    return spans


def run_segments():
    """Every tab's run-bar segments, for the page."""
    return {
        "extract": segment_spans([weight for _stage, _phase, weight in EXTRACTION_PHASE_WEIGHTS], EXTRACTION_SEGMENTS),
        "preview": segment_spans(PREVIEW_STEP_WEIGHTS, PREVIEW_SEGMENTS),
        "build": segment_spans(GENERATION_WEIGHTS, GENERATION_SEGMENTS),
    }


class ProgressTimingRecorder:
    """Collect repeated progress states and emit a timing diagnostics payload."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.started_at = None
        self.last = None
        self.events = []

    def start(self):
        self.reset()
        self.started_at = time.perf_counter()

    def record(self, stage, completed, total, label, *, phase=None):
        now = time.perf_counter()
        if self.started_at is None:
            self.started_at = now

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

    def finish(self, *, phase_key=None, weights=None):
        now = time.perf_counter()
        if self.last is not None:
            self.events.append(self._event_from_last(now))

        started_at = self.started_at or now
        phase_seconds = {}
        for event in self.events:
            key = phase_key(event) if phase_key is not None else event.get("phase")
            if key is None:
                continue
            phase_seconds[key] = phase_seconds.get(key, 0.0) + event["seconds"]

        payload = {
            "total_seconds": round(now - started_at, 4),
            "phase_seconds": {key: round(value, 4) for key, value in phase_seconds.items()},
            "events": self.events,
        }
        if weights is not None:
            payload["weights"] = weights

        self.reset()
        return payload

    def _event_from_last(self, now):
        return {
            "stage": self.last["stage"],
            "phase": self.last["phase"],
            "completed": self.last["completed"],
            "total": self.last["total"],
            "label": self.last["label"],
            "seconds": round(now - self.last["time"], 4),
        }
