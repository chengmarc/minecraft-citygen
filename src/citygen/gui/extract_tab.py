"""Extract: the source world, its three sample areas, the region map over the world's top-down preview
(:func:`citygen.tools.render_topdown.cached_topdown_preview`), and the extraction run.
"""

from __future__ import annotations

from pathlib import Path

from citygen import step1_extract
from citygen.tools import render_topdown
from citygen.gui import files
from citygen.gui.server import image
from citygen.paths import BUILDS_CONTACT_SHEET, BUILDS_RENDERS, has_region_files, ROADS_CONTACT_SHEET, ROADS_RENDERS
from citygen.settings import (
    BlockRegion,
    BUILD_TYPES,
    BuildRegion,
    detect_world_data_version,
    release_name_for,
    RELEASE_NAMES,
    ROAD_BOX,
    SAVE,
)


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
    """The paste-target dropdown's values, newest first after ``AUTO_VERSION`` (which text.js names).

    Indicator only: it lists the MC versions the output can be pasted into
    -- the source version and newer -- so the user can confirm the target. It
    does not affect the stamp, which is always the source version (see
    config.world.source_data_version). When min_data_version is given, only versions at
    or above it are listed.
    """
    return [AUTO_VERSION] + [
        name
        for dv, name in sorted(RELEASE_NAMES.items(), reverse=True)
        if min_data_version is None or dv >= min_data_version
    ]


# --- The tab

CHUNK_SIZE = 16   # static/region/region.js snaps to the same chunks


def chunk_span(start, end):
    """How many chunks a block region covers, as ``[x, z]``."""
    min_x, max_x = sorted((int(start[0]), int(end[0])))
    min_z, max_z = sorted((int(start[2]), int(end[2])))
    return [max_x // CHUNK_SIZE - min_x // CHUNK_SIZE + 1, max_z // CHUNK_SIZE - min_z // CHUNK_SIZE + 1]


AREAS = ("road", "house", "landmark")

# Extract's reports are coalesced into this many buckets per step, so the page isn't sent events that don't move its bar.
PROGRESS_BUCKETS = 100


def coalesce(report):
    """Extract's ``report(step, completed, total)``, dropping the reports that wouldn't move the bar but keeping each
    step's completion."""
    last_key = None

    def on_progress(step, completed, total):
        nonlocal last_key
        total_i = max(int(total), 1)
        completed_i = max(0, min(int(completed), total_i))
        bucket = PROGRESS_BUCKETS if completed_i >= total_i else int((completed_i * PROGRESS_BUCKETS) / total_i)
        key = (step, total_i, bucket)
        if key == last_key:
            return
        last_key = key
        report(step, completed_i, total_i)

    return on_progress


def _area_pair(area_state):
    """A saved area's ``(start, end)`` block corners, or None if it isn't selected."""
    if not isinstance(area_state, dict):
        return None
    start, end = area_state.get("start"), area_state.get("end")
    if not (isinstance(start, list) and isinstance(end, list) and len(start) == 3 and len(end) == 3):
        return None
    return tuple(int(v) for v in start), tuple(int(v) for v in end)


class ExtractTab:
    """The Extract tab's calls. The saved ``extraction`` section is the tab's state.

    An error is ``{"error": {"code", "detail"}}``, which the page words.
    """

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

    def world_path(self):
        """The source world's folder, as saved: the bundled sample world until the user picks another."""
        return str(self._saved().get("world_path", "")).strip()

    def world_ready(self):
        path = self.world_path()
        return bool(path) and has_region_files(path)

    def ready(self):
        saved = self._saved()
        return self.world_ready() and all(_area_pair(saved.get(key)) for key in AREAS)

    def view(self):
        """The tab as the page draws it: the saved state plus what's derived from the world."""
        saved = self._saved()
        path = self.world_path()
        version = detect_world_data_version(path) if path else None
        versions = version_selector_items(version)
        target = saved.get("target_version", AUTO_VERSION)
        if target not in versions:
            target = AUTO_VERSION
        areas = {}
        for key in AREAS:
            pair = _area_pair(saved.get(key))
            areas[key] = {"chunks": chunk_span(*pair) if pair else None}
        return {
            "worldPath": path,
            "worldReady": self.world_ready(),
            "sourceVersion": release_name_for(version) if version is not None else "",
            "versions": versions,
            "targetVersion": target,
            "areas": areas,
        }

    def set_world_path(self, path):
        self._save({**self._saved(), "world_path": str(path).strip()})

    def set_target_version(self, value):
        self._save({**self._saved(), "target_version": value})

    def browse_world(self):
        """Ask for a world folder; a new world clears the areas and the pipeline's artifacts.

        Returns ``{"changed": True}``, ``{"warning": {"code": "not_a_world", ...}}``, or ``{}`` when cancelled.
        """
        folder = self._pick_folder(self.world_path())
        if not folder:
            return {}
        if not has_region_files(folder):
            return {"warning": {"code": "not_a_world", "detail": folder}}
        state = {**self._saved(), "world_path": folder}
        for key in AREAS:
            state[key] = {"start": None, "end": None}
        self._save(state)
        files.clear_pipeline_artifacts()
        return {"changed": True}

    def use_default_world(self):
        """Back to the bundled sample world, with its own three areas: as a fresh install starts. Like any change of
        world, the pipeline's artifacts are cleared."""
        self._save(default_extraction_tab_config())
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
        """Render (or load the cached) top-down world preview; answers with ``worldMap`` events: progress, the map so
        far (``partial``) while it's drawn, then the map."""
        save_path = self.world_path()
        if not save_path or not has_region_files(save_path):
            return {"error": {"code": "no_world"}}

        drawn = 0.0   # how far down the map has been drawn, from 0 to 1: the progress just before each snapshot

        def on_progress(done, total):
            nonlocal drawn
            drawn = done / total if total else 1.0
            self._emit("worldMap", {"completed": done, "total": total})

        def on_partial(path, meta):
            self._emit("worldMap", {**image(path), "meta": meta, "partial": True, "drawn": drawn})

        def worker():
            try:
                png_path, meta = render_topdown.cached_topdown_preview(save_path, on_progress=on_progress, on_partial=on_partial)
            except Exception as exc:  # boundary: surface any preview-load failure in the map
                self._emit("worldMap", {"error": str(exc).strip() or None})
                return
            self._emit("worldMap", {**image(png_path), "meta": meta})

        self._thread_factory(target=worker, daemon=True).start()
        return {}

    def run(self):
        """Start the extraction on the saved world and areas."""
        if self._runner.is_running("extract"):
            return {"error": {"code": "running"}}
        saved = self._saved()
        pairs = {key: _area_pair(saved.get(key)) for key in AREAS}
        if not self.world_ready() or not all(pairs.values()):
            return {"error": {"code": "areas_missing"}}
        save = self.world_path()
        road_box = BlockRegion.from_xyz_pair(*pairs["road"])
        build_types = (
            BuildRegion(1, BlockRegion.from_xyz_pair(*pairs["house"])),
            BuildRegion(2, BlockRegion.from_xyz_pair(*pairs["landmark"])),
        )

        # Each piece's render is saved as <its name>.png before its progress names it: shown as it lands.
        renders = {"road_sheet": ("roads", ROADS_RENDERS), "build_sheet": ("builds", BUILDS_RENDERS)}

        def job(report):
            coalesced = coalesce(report)

            def on_progress(step, completed, total, detail=None):
                if step in renders and detail:   # before the coalescing, which would drop some pieces
                    viewer, folder = renders[step]
                    piece = Path(folder) / f"{detail}.png"
                    if piece.is_file():
                        self._runner.piece("extract", viewer, int(completed), image(piece))
                coalesced(step, completed, total)

            step1_extract.run(save, road_box, build_types, on_progress)

        self._runner.start("extract", job, on_success=lambda _result: {
            "images": {"roads": image(ROADS_CONTACT_SHEET), "builds": image(BUILDS_CONTACT_SHEET)},
        })
        return {}
