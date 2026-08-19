"""Preview tab UI."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from config.config_algo import DEFAULT_SEED
from pipeline import services

from gui import common
from gui.jobs import run_weighted_tasks_async
from gui.widgets import ImageViewer, WeightedProgressMixin, build_shared_config_frame


class PreviewTab(WeightedProgressMixin, ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self._init_weighted_progress()
        self._suspend_auto_save = False
        saved_config = self.winfo_toplevel().get_saved_config_section("preview") or common.default_algo_tab_config()

        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="nsew")
        top.columnconfigure(0, weight=1, uniform="preview")
        top.columnconfigure(1, weight=1, uniform="preview")
        top.rowconfigure(0, weight=1)

        self.grid_viewer = ImageViewer(
            top,
            "Grid Preview",
            initial_message="Click Preview to generate the grid preview image.",
            smooth_zoom=True,
        )
        self.grid_viewer.grid(row=0, column=0, sticky="nsew")

        self.city_viewer = ImageViewer(
            top,
            "City Preview",
            initial_message="Click Preview to generate the city preview image.",
            smooth_zoom=True,
        )
        self.city_viewer.grid(row=0, column=1, sticky="nsew")
        self.grid_viewer.set_view_change_callback(self._sync_preview_viewers)
        self.city_viewer.set_view_change_callback(self._sync_preview_viewers)

        self.config_frame = ttk.LabelFrame(self, text="Preview")
        self.config_frame.grid(row=1, column=0, sticky="ew")
        self.seed_var = tk.StringVar(value=str(saved_config.get("seed", DEFAULT_SEED)))
        self.config_vars = common.create_config_vars(saved_config.get("algo"))
        self.preview_button = build_shared_config_frame(
            self.config_frame,
            self.seed_var,
            self.config_vars,
            "Preview",
            self._run_preview,
            "preview_config",
        )
        self._bind_auto_save()
        self._build_progress_bar(2)

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def set_status(self, status):
        self.config_frame.configure(text=f"Preview - {status}")

    def _current_config_state(self):
        return {
            "seed": self.seed_var.get().strip(),
            "algo": common.snapshot_config_vars(self.config_vars),
        }

    def _bind_auto_save(self):
        self.seed_var.trace_add("write", self._on_config_changed)
        for variable in self.config_vars.values():
            variable.trace_add("write", self._on_config_changed)

    def _on_config_changed(self, *_args):
        if self._suspend_auto_save:
            return
        self.winfo_toplevel().set_saved_config_section("preview", self._current_config_state())

    def _apply_config_state(self, config):
        if not config:
            return
        self._suspend_auto_save = True
        try:
            self.seed_var.set(str(config.get("seed", DEFAULT_SEED)))
            common.apply_config_vars(self.config_vars, config.get("algo"))
        finally:
            self._suspend_auto_save = False

    def _sync_preview_viewers(self, source, state, reason):
        target = self.city_viewer if source is self.grid_viewer else self.grid_viewer
        if target.image_path is None:
            return
        target._apply_view_state(state)

    def _run_preview(self):
        seed = self.seed_var.get().strip()
        try:
            common.validate_seed(seed)
            env = common.build_algo_env(self.config_vars)
            fine = env["MC_CITY_FINE"]
        except ValueError as exc:
            title = "Invalid seed" if str(exc) == "Seed must be an integer." else "Invalid preview config"
            messagebox.showerror(title, str(exc))
            return

        tasks = [
            ("pipeline.01_roads_simulation", common.PREVIEW_PROGRESS_WEIGHTS[0][1], lambda: services.run_roads_simulation_stage(env_overrides=env)),
            ("pipeline.02_builds_simulation", common.PREVIEW_PROGRESS_WEIGHTS[1][1], lambda: services.run_builds_simulation_stage(env_overrides=env)),
            ("pipeline.03_grid_simulation", common.PREVIEW_PROGRESS_WEIGHTS[2][1], lambda: services.run_grid_simulation_stage(seed, fine, env_overrides=env)),
            ("pipeline.04_city_simulation", common.PREVIEW_PROGRESS_WEIGHTS[3][1], lambda: services.run_city_simulation_stage(seed, fine, env_overrides=env)),
        ]
        run_weighted_tasks_async(
            self,
            self.preview_button,
            tasks,
            "Starting preview...",
            "Preview failed",
            "Preview failed",
            "Preview complete",
            lambda: self._load_synced_previews(seed),
        )

    def _load_synced_previews(self, seed):
        self.grid_viewer.load_image(common.grid_preview_path(seed))
        self.city_viewer.load_image(common.city_preview_path(seed))
        self.city_viewer.sync_view_from(self.grid_viewer)
