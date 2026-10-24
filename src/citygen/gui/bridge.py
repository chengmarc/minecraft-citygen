"""The calls the page makes, and the events it receives.

Python answers with facts and short codes; every word the page shows is in its text.js.
Nothing here imports pywebview. The page calls the public methods of :class:`Api`
(``window.pywebview.api.<name>``); the app answers through ``emit(event, payload)``,
which the host turns into a call to ``citygen.receive`` in the page.
"""

from __future__ import annotations

import threading

from citygen.gui import files
from citygen.gui.city_tabs import CityTabs
from citygen.gui.extract_tab import ExtractTab
from citygen.gui.form import form_spec
from citygen.gui.session import Runner, Settings


class Api:
    """Every call the page can make. Methods return plain JSON-able values."""

    def __init__(self, emit, *, pick_folder, thread_factory=threading.Thread):
        self._settings = Settings()
        self._runner = Runner(emit, self._gates, thread_factory=thread_factory)
        self._extract = ExtractTab(
            self._settings, self._runner, emit, pick_folder=pick_folder, thread_factory=thread_factory,
        )
        self._algo = CityTabs(self._settings, self._runner, world_path=self._extract.world_path)

    def _gates(self):
        """Whether each tab's run can start: Extract needs a world and its areas, the others the extracted assets."""
        assets = files.extracted_assets_ready()
        return {"extract": self._extract.ready(), "preview": assets, "build": assets}

    def _extraction(self):
        return {"extraction": self._extract.view(), "gates": self._gates()}

    # The whole app, on load.

    def bootstrap(self):
        return {
            "algo": self._algo.state(),
            "form": form_spec(),
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

    def use_default_world(self):
        return {**self._extract.use_default_world(), **self._extraction()}

    def area_bounds(self, key):
        return self._extract.area_bounds(key)

    def set_area(self, key, start, end):
        self._extract.set_area(key, start, end)
        return self._extraction()

    def load_world_map(self):
        return self._extract.load_world_map()

    def run_extract(self):
        return self._extract.run()
