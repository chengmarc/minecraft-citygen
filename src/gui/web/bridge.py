"""The calls the page makes, and the events it receives.

Nothing here imports pywebview. The page calls the public methods of :class:`Api`
(``window.pywebview.api.<name>``); the app answers through ``emit(event, payload)``,
which the host turns into a call to ``citygen.receive`` in the page.
"""

from __future__ import annotations

import threading

from gui.core import app_files, progress
from gui.web.algo import AlgoTabs, form_spec
from gui.web.extract import ExtractTab
from gui.web.session import Runner, Settings

TOOLTIPS = {
    "preview": "Generate a fast road and city layout preview.",
    "build": "Build the final schematic, render, and export world.",
    "blocked": "Complete Extract Assets first.",
}


class Api:
    """Every call the page can make. Methods return plain JSON-able values."""

    def __init__(self, emit, *, pick_folder, thread_factory=threading.Thread):
        self._settings = Settings()
        self._runner = Runner(emit, self._gates, thread_factory=thread_factory)
        self._algo = AlgoTabs(self._settings, self._runner)
        self._extract = ExtractTab(
            self._settings, self._runner, emit, pick_folder=pick_folder, thread_factory=thread_factory,
        )

    def _gates(self):
        assets = app_files.extracted_assets_ready()
        return {
            "extract": {"ready": self._extract.ready(), "tooltip": ""},
            "preview": {"ready": assets, "tooltip": TOOLTIPS["preview"] if assets else TOOLTIPS["blocked"]},
            "build": {"ready": assets, "tooltip": TOOLTIPS["build"] if assets else TOOLTIPS["blocked"]},
        }

    def _extraction(self):
        return {"extraction": self._extract.view(), "gates": self._gates()}

    # The whole app, on load.

    def bootstrap(self):
        return {
            "algo": self._algo.state(),
            "form": form_spec(),
            "segments": progress.run_segments(),
            **self._extraction(),
        }

    # Preview and Build

    def save_algo(self, state):
        self._algo.save(state)

    def reset_algo(self):
        return self._algo.reset()

    def run_preview(self, state):
        return self._algo.run_preview(state)

    def run_build(self, state):
        return self._algo.run_build(state)

    def open_worlds_folder(self):
        return self._algo.open_worlds_folder()

    # Extract

    def set_world_path(self, path):
        self._extract.set_world_path(path)
        return self._extraction()

    def set_target_version(self, value):
        self._extract.set_target_version(value)
        return self._extraction()

    def browse_world(self):
        return {**self._extract.browse_world(), **self._extraction()}

    def area_bounds(self, key):
        return self._extract.area_bounds(key)

    def set_area(self, key, start, end):
        self._extract.set_area(key, start, end)
        return self._extraction()

    def load_world_map(self):
        return self._extract.load_world_map()

    def run_extract(self):
        return self._extract.run()
