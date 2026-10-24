"""Extract: the source world, its three sample areas, the region map over the world's top-down preview, and
Stages 1 then 2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from config.path import (
    BUILDS_CONTACT_SHEET, ROADS_CONTACT_SHEET, WORLD_PREVIEW_CACHE, has_region_files, resolve_region_dir,
)
from config.world import (
    BUILD_TYPES, RELEASE_NAMES, ROAD_BOX, SAVE,
    BlockRegion, BuildRegion, detect_world_data_version, release_name_for,
)
from engine.render.topdown import render_topdown_preview
from pipeline import services, stages

from gui import files, progress
from gui.server import file_url


# --- Settings: source world, sample areas, and the version stamp

# Sentinel meaning "no explicit paste target chosen" in the selector.
AUTO_VERSION = "auto"


def region_to_xyz_pair(region):
    if isinstance(region, BuildRegion):
        return region.bounds.as_xyz_pair()
    if isinstance(region, BlockRegion):
        return region.as_xyz_pair()
    raise TypeError(f"Unsupported region type: {type(region).__name__}")


def first_build_region(build_types, build_type):
    for region in build_types:
        if region.build_type == build_type:
            return region
    return BuildRegion(build_type, BlockRegion(0, 0, 0, 0, 64, 64))


def _serialize_xyz_pair(start, end):
    return {
        "start": list(start),
        "end": list(end),
    }


def default_extraction_tab_config():
    road_start, road_end = region_to_xyz_pair(ROAD_BOX)
    house_start, house_end = region_to_xyz_pair(first_build_region(BUILD_TYPES, 1))
    landmark_start, landmark_end = region_to_xyz_pair(first_build_region(BUILD_TYPES, 2))
    return {
        "world_path": SAVE,
        "target_version": AUTO_VERSION,
        "road": _serialize_xyz_pair(road_start, road_end),
        "house": _serialize_xyz_pair(house_start, house_end),
        "landmark": _serialize_xyz_pair(landmark_start, landmark_end),
    }


def version_selector_items(min_data_version=None):
    """(label, value) pairs for the paste-target dropdown, newest first.

    Indicator only: it lists the MC versions the output can be pasted into
    -- the source version and newer -- so the user can confirm the target. It
    does not affect the stamp, which is always the source version (see
    config.world.source_data_version). When min_data_version is given, only versions at
    or above it are listed.
    """
    items = [("Auto", AUTO_VERSION)]
    items.extend(
        (name, name)
        for dv, name in sorted(RELEASE_NAMES.items(), reverse=True)
        if min_data_version is None or dv >= min_data_version
    )
    return items


# --- The region map's world preview, rendered once per world and cached on disk

CHUNK_SIZE = 16


def _preview_cache_paths(save_path):
    key = hashlib.md5(str(save_path).encode()).hexdigest()[:16]
    cache_dir = Path(WORLD_PREVIEW_CACHE)
    return cache_dir / f"{key}.png", cache_dir / f"{key}.json"


def _preview_region_mtime(save_path):
    try:
        region_dir = resolve_region_dir(save_path)
        mtimes = [p.stat().st_mtime for p in Path(region_dir).glob("*.mca")]
        return max(mtimes) if mtimes else 0.0
    except Exception:
        return 0.0


def cached_topdown_preview(save_path, on_progress=None):
    """The world's top-down preview as ``(png_path, meta)``, rendered only when the cache is stale.

    The cache in ``WORLD_PREVIEW_CACHE`` is keyed on save_path and invalidated when
    any .mca file changes, so reopening the region map is instant. ``on_progress``
    is only called on a cache miss (an actual render).
    """
    png_path, json_path = _preview_cache_paths(save_path)
    mtime = _preview_region_mtime(save_path)

    if png_path.exists() and json_path.exists():
        try:
            with open(json_path) as f:
                cached_meta = json.load(f)
            if cached_meta.get("mtime") == mtime:
                return png_path, {k: v for k, v in cached_meta.items() if k != "mtime"}
        except Exception:
            pass  # fall through to re-render on any cache read failure

    image, meta = render_topdown_preview(save_path, on_progress=on_progress)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(png_path)
    with open(json_path, "w") as f:
        json.dump({**meta, "mtime": mtime}, f)
    return png_path, meta


def chunk_span_text(start, end):
    """How many chunks a block region covers, as "x x z chunks"."""
    min_x, max_x = sorted((int(start[0]), int(end[0])))
    min_z, max_z = sorted((int(start[2]), int(end[2])))
    x_chunks = max_x // CHUNK_SIZE - min_x // CHUNK_SIZE + 1
    z_chunks = max_z // CHUNK_SIZE - min_z // CHUNK_SIZE + 1
    return f"{x_chunks} x {z_chunks} chunks"


# --- The tab

AREAS = ("road", "house", "landmark")

PROGRESS_BUCKETS = 100

EXTRACT_PHASE_INDEX = {
    (stage, phase): index
    for index, (stage, phase, _weight) in enumerate(progress.EXTRACTION_PHASE_WEIGHTS)
}
EXTRACT_PHASE_WEIGHT_VALUES = [weight for _stage, _phase, weight in progress.EXTRACTION_PHASE_WEIGHTS]

EXTRACT_STATUS_LABELS = {
    (stages.ROADS_EXTRACT, "scan"): "Scanning road region",
    (stages.ROADS_EXTRACT, "export"): "Extracting road pieces",
    (stages.ROADS_RENDER, "render"): "Building road contact sheet",
    (stages.BUILDS_EXTRACT, "scan"): "Scanning build regions",
    (stages.BUILDS_EXTRACT, "export"): "Extracting building pieces",
    (stages.BUILDS_RENDER, "render"): "Building asset sheet",
}

TIMING_PREFIXES = {
    stages.ROADS_EXTRACT: "roads",
    stages.ROADS_RENDER: "roads",
    stages.BUILDS_EXTRACT: "builds",
    stages.BUILDS_RENDER: "builds",
}


def _extract_phase(stage, label):
    if stage in (stages.ROADS_EXTRACT, stages.BUILDS_EXTRACT):
        return "scan" if (label or "").startswith("Scanning") else "export"
    return "render"


def coalesce_pipeline_progress(emit):
    """Drop progress events that wouldn't move the bar, keeping each phase's completion."""
    last_key = None

    def on_progress(stage, completed, total, label):
        nonlocal last_key
        total_i = max(int(total), 1)
        completed_i = max(0, min(int(completed), total_i))
        bucket = PROGRESS_BUCKETS if completed_i >= total_i else int((completed_i * PROGRESS_BUCKETS) / total_i)
        key = (stage, _extract_phase(stage, label), total_i, bucket)
        if key == last_key:
            return
        last_key = key
        emit(stage, float(completed_i), float(total_i), label)

    return on_progress


def extract_progress(stage, phase, completed, total):
    """``(value, soft_target, status)`` for an extraction phase, in PROGRESS_BAR_SCALE units."""
    scale = progress.PROGRESS_BAR_SCALE
    phase_index = EXTRACT_PHASE_INDEX[(stage, phase)]
    status = EXTRACT_STATUS_LABELS.get((stage, phase), "Extracting assets")
    total_f = float(total) if total > 0 else 1.0
    completed_f = max(0.0, min(float(completed), total_f))
    if completed_f >= total_f:
        return progress.weighted_segment(EXTRACT_PHASE_WEIGHT_VALUES, phase_index, scale)[1], None, status
    value = progress.weighted_item_milestone(EXTRACT_PHASE_WEIGHT_VALUES, phase_index, completed_f, total_f, scale)
    next_value = progress.weighted_item_milestone(
        EXTRACT_PHASE_WEIGHT_VALUES, phase_index, completed_f + 1.0, total_f, scale,
    )
    return value, progress.soft_target(value, next_value, "extraction"), status


def _area_pair(area_state):
    """A saved area's ``(start, end)`` block corners, or None if it isn't selected."""
    if not isinstance(area_state, dict):
        return None
    start, end = area_state.get("start"), area_state.get("end")
    if not (isinstance(start, list) and isinstance(end, list) and len(start) == 3 and len(end) == 3):
        return None
    return tuple(int(v) for v in start), tuple(int(v) for v in end)


def _timing_key(event):
    prefix = TIMING_PREFIXES.get(event["stage"])
    return None if prefix is None else f"{prefix}_{event['phase']}"


def _image(path):
    url = file_url(path)
    return {"src": url} if url else {"message": f"Image not found:\n{path}"}


class ExtractTab:
    """The Extract tab's calls. The saved ``extraction`` section is the tab's state."""

    def __init__(self, settings, runner, emit, *, pick_folder, thread_factory):
        self._settings = settings
        self._runner = runner
        self._emit = emit
        self._pick_folder = pick_folder
        self._thread_factory = thread_factory

    def _saved(self):
        return self._settings.get("extraction") or default_extraction_tab_config()

    def _save(self, state):
        self._settings.set("extraction", state)

    def world_ready(self):
        path = str(self._saved().get("world_path", "")).strip()
        return bool(path) and has_region_files(path)

    def ready(self):
        saved = self._saved()
        return self.world_ready() and all(_area_pair(saved.get(key)) for key in AREAS)

    def view(self):
        """The tab as the page draws it: the saved state plus what's derived from the world."""
        saved = self._saved()
        path = str(saved.get("world_path", "")).strip()
        version = detect_world_data_version(path) if path else None
        versions = version_selector_items(version)
        target = saved.get("target_version", AUTO_VERSION)
        if target not in [value for _label, value in versions]:
            target = AUTO_VERSION
        areas = {}
        for key in AREAS:
            pair = _area_pair(saved.get(key))
            areas[key] = {
                "selected": pair is not None,
                "detail": f"{chunk_span_text(*pair)} selected" if pair else "No area selected",
            }
        return {
            "worldPath": path,
            "worldReady": self.world_ready(),
            "sourceVersion": release_name_for(version) if version is not None else "",
            "versions": [{"label": label, "value": value} for label, value in versions],
            "targetVersion": target,
            "areas": areas,
        }

    def set_world_path(self, path):
        self._save({**self._saved(), "world_path": str(path).strip()})

    def set_target_version(self, value):
        self._save({**self._saved(), "target_version": value})

    def browse_world(self):
        """Ask for a world folder; a new world clears the areas and the pipeline's artifacts.

        Returns ``{"changed": True}``, ``{"warning": ...}``, or ``{}`` when cancelled.
        """
        folder = self._pick_folder(str(self._saved().get("world_path", "")).strip())
        if not folder:
            return {}
        if not has_region_files(folder):
            return {"warning": {
                "title": "Not an MC world",
                "message": f"No region files (.mca) were found in:\n{folder}\n\nPlease select a valid MC world folder.",
            }}
        state = {**self._saved(), "world_path": folder}
        for key in AREAS:
            state[key] = {"start": None, "end": None}
        self._save(state)
        files.clear_pipeline_artifacts()
        return {"changed": True}

    def area_bounds(self, key):
        """The area the region map opens on: the saved selection, or the default sample area."""
        pair = _area_pair(self._saved().get(key))
        if pair is None:
            default = default_extraction_tab_config()[key]
            pair = tuple(default["start"]), tuple(default["end"])
        return {"start": list(pair[0]), "end": list(pair[1])}

    def set_area(self, key, start, end):
        self._save({**self._saved(), key: {"start": [int(v) for v in start], "end": [int(v) for v in end]}})

    def load_world_map(self):
        """Render (or load the cached) top-down world preview; answers with ``worldMap`` events."""
        save_path = str(self._saved().get("world_path", "")).strip()
        if not save_path or not has_region_files(save_path):
            return {"error": {
                "title": "Missing world path",
                "message": "Choose a valid MC world before selecting an area on the map.",
            }}

        def worker():
            try:
                png_path, meta = cached_topdown_preview(
                    save_path,
                    on_progress=lambda done, total: self._emit("worldMap", {"completed": done, "total": total}),
                )
                url = file_url(png_path)
                if url is None:
                    raise OSError(f"World preview not found:\n{png_path}")
            except Exception as exc:  # boundary: surface any preview-load failure in the map
                self._emit("worldMap", {"error": str(exc).strip() or "Failed to load world preview."})
                return
            self._emit("worldMap", {"src": url, "meta": meta})

        self._thread_factory(target=worker, daemon=True).start()
        return {}

    def run(self):
        """Start Stages 1 then 2 on the saved world and areas."""
        if self._runner.is_running("extract"):
            return {"error": {"title": "Extract running", "message": "An extraction is already running."}}
        saved = self._saved()
        pairs = {key: _area_pair(saved.get(key)) for key in AREAS}
        if not self.world_ready() or not all(pairs.values()):
            return {"error": {
                "title": "Invalid extraction region",
                "message": "Choose an MC world and all three areas first.",
            }}
        save = str(saved["world_path"]).strip()
        road_box = BlockRegion.from_xyz_pair(*pairs["road"])
        build_types = (
            BuildRegion(1, BlockRegion.from_xyz_pair(*pairs["house"])),
            BuildRegion(2, BlockRegion.from_xyz_pair(*pairs["landmark"])),
        )
        timing = progress.ProgressTimingRecorder()
        timing.start()

        def job(report):
            def on_stage_progress(stage, completed, total, label):
                phase = _extract_phase(stage, label)
                timing.record(stage, completed, total, label, phase=phase)
                report(*extract_progress(stage, phase, completed, total), creep="extraction")

            on_progress = coalesce_pipeline_progress(on_stage_progress)
            # No data_version: extraction stamps the version detected from ``save``.
            services.run_stage("roads", save=save, road_box=road_box, progress=on_progress)
            services.run_stage("builds", save=save, build_types=build_types, progress=on_progress)

        def on_success(_result):
            files.save_progress_timing("extraction", timing.finish(
                phase_key=_timing_key,
                weights={f"{stage}:{phase}": weight for stage, phase, weight in progress.EXTRACTION_PHASE_WEIGHTS},
            ))
            return {
                "images": {"roads": _image(ROADS_CONTACT_SHEET), "builds": _image(BUILDS_CONTACT_SHEET)},
                "status": "Extraction complete",
            }

        self._runner.start("extract", job, failure_title="Extract failed", status="Preparing extraction",
                           on_success=on_success)
        return {}
