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
        super().__init__(master, padding=10, style="Page.TFrame")
        self._init_weighted_progress()

        top = ttk.Frame(self, style="Page.TFrame")
        top.grid(row=0, column=0, sticky="nsew")
        top.columnconfigure(0, weight=1, uniform="preview")
        top.columnconfigure(1, weight=1, uniform="preview")
        top.rowconfigure(0, weight=1)

        self.grid_viewer = ImageViewer(top, "Grid Preview", initial_message="Click Preview to generate the grid preview image.")
        self.grid_viewer.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        self.city_viewer = ImageViewer(top, "City Preview", initial_message="Click Preview to generate the city preview image.")
        self.city_viewer.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        self.config_frame = ttk.LabelFrame(self, text="⬤ Preview Config", padding=8, style="Card.TLabelframe")
        self.config_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.seed_var = tk.StringVar(value=str(DEFAULT_SEED))
        self.config_vars = common.create_config_vars()
        self.preview_button = build_shared_config_frame(
            self.config_frame,
            self.seed_var,
            self.config_vars,
            "Preview",
            self._run_preview,
            "preview_config",
        )
        self._build_progress_bar(2)

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def set_status(self, status):
        self.config_frame.configure(text=f"⬤ Preview Config - {status}")

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
            lambda: (
                self.grid_viewer.load_image(common.grid_preview_path(seed)),
                self.city_viewer.load_image(common.city_preview_path(seed)),
            ),
        )
