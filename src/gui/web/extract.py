"""Extract: the source world, its three sample areas, the region map, and Stages 1 then 2."""

from __future__ import annotations

from config.path import BUILDS_CONTACT_SHEET, ROADS_CONTACT_SHEET, has_region_files
from config.world import BlockRegion, BuildRegion, detect_world_data_version, release_name_for
from pipeline import services, stages

from gui.core import app_files, extraction_config, progress, world_preview
from gui.web.server import file_url

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
        return self._settings.get("extraction") or extraction_config.default_extraction_tab_config()

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
        versions = extraction_config.version_selector_items(version)
        target = saved.get("target_version", extraction_config.AUTO_VERSION)
        if target not in [value for _label, value in versions]:
            target = extraction_config.AUTO_VERSION
        areas = {}
        for key in AREAS:
            pair = _area_pair(saved.get(key))
            areas[key] = {
                "selected": pair is not None,
                "detail": f"{world_preview.chunk_span_text(*pair)} selected" if pair else "No area selected",
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
        app_files.clear_pipeline_artifacts()
        return {"changed": True}

    def area_bounds(self, key):
        """The area the region map opens on: the saved selection, or the default sample area."""
        pair = _area_pair(self._saved().get(key))
        if pair is None:
            default = extraction_config.default_extraction_tab_config()[key]
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
                png_path, meta = world_preview.cached_topdown_preview(
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
            app_files.save_progress_timing("extraction", timing.finish(
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
