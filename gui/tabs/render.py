"""Render tab UI."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk

from config.config_algo import DEFAULT_SEED
from config.config_path import CITY_PROD_SCHEM
from pipeline import services

from gui import common
from gui.jobs import run_weighted_tasks_async
from gui.widgets import ImageViewer, WeightedProgressMixin, build_shared_config_frame


class CityTab(WeightedProgressMixin, ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10, style="Page.TFrame")
        self._init_weighted_progress()

        self.city_viewer = ImageViewer(self, "City Schematic Render", initial_message="Click Render to construct and render the city schematic.")
        self.city_viewer.grid(row=0, column=0, sticky="nsew")

        self.config_frame = ttk.LabelFrame(self, text="Render Config", padding=8, style="Card.TLabelframe")
        self.config_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.seed_var = tk.StringVar(value=str(DEFAULT_SEED))
        self.config_vars = common.create_config_vars()
        self.render_button = build_shared_config_frame(
            self.config_frame,
            self.seed_var,
            self.config_vars,
            "Render",
            self._run_render,
            "city_config",
            extra_actions=[("Output Folder", self._open_output_folder)],
        )
        self._build_progress_bar(2)

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def set_status(self, status):
        self.config_frame.configure(text=f"Render Config - {status}")

    def _open_output_folder(self):
        if not os.path.isdir(CITY_PROD_SCHEM):
            messagebox.showerror("Output folder missing", CITY_PROD_SCHEM)
            return
        os.startfile(CITY_PROD_SCHEM)

    def _run_render(self):
        seed = self.seed_var.get().strip()
        try:
            common.validate_seed(seed)
            env = common.build_algo_env(self.config_vars)
            fine = env["MC_CITY_FINE"]
        except ValueError as exc:
            title = "Invalid seed" if str(exc) == "Seed must be an integer." else "Invalid city config"
            messagebox.showerror(title, str(exc))
            return

        tasks = [
            ("pipeline.04_city_construct", common.RENDER_PROGRESS_WEIGHTS[0][1], lambda: services.run_city_construct_stage(seed, fine, env_overrides=env)),
            ("pipeline.04_city_render", common.RENDER_PROGRESS_WEIGHTS[1][1], lambda: services.run_city_render_stage(env_overrides=env)),
        ]
        run_weighted_tasks_async(
            self,
            self.render_button,
            tasks,
            "Starting render...",
            "Render failed",
            "Render failed",
            "Render complete",
            lambda: self.city_viewer.load_image(common.city_render_path(seed)),
        )
