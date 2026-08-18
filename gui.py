"""Tkinter GUI for inspecting and configuring the city-generation pipeline."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading


def _configure_tcl_tk():
    tcl_root = os.path.join(sys.base_prefix, "tcl")
    tcl_library = os.path.join(tcl_root, "tcl8.6")
    tk_library = os.path.join(tcl_root, "tk8.6")
    if os.path.exists(os.path.join(tcl_library, "init.tcl")):
        os.environ.setdefault("TCL_LIBRARY", tcl_library)
    if os.path.exists(os.path.join(tk_library, "tk.tcl")):
        os.environ.setdefault("TK_LIBRARY", tk_library)


_configure_tcl_tk()

import tkinter as tk
from tkinter import messagebox, ttk

import config_algo
from config_path import BUILDS_PROD, CITY_SIM, GRID_SIM, ROADS_PROD
from config_world import BUILD_TYPES, ROAD_BOX, SAVE

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover - tkinter can still show PNGs directly.
    Image = None
    ImageTk = None


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ROAD_CONTACT_SHEET = os.path.join(ROADS_PROD, "_contact_sheet.png")
BUILD_CONTACT_SHEET = os.path.join(BUILDS_PROD, "_contact_sheet.png")

CANVAS_BG = "#17191c"
CANVAS_TEXT = "#d0d5dd"
TICK = "#8a919c"
TOOLTIP_BG = "#20242a"
TOOLTIP_TEXT = "#f5f6f8"


def grid_preview_path(seed):
    return os.path.join(GRID_SIM, f"seed_{seed}_preview.png")


def city_preview_path(seed):
    return os.path.join(CITY_SIM, f"seed_{seed}.png")


def format_box(box):
    return ", ".join(str(value) for value in box)


def format_build_types(build_types):
    return "; ".join(format_box(build_type) for build_type in build_types)


PREVIEW_CONFIGS = [
    ("FINE", "City Size", "Fine-cell width and height of the generated map. Even values work best."),
    ("GAP_MIXED", "Grid Density", "Minimum clearance between a small street and a big avenue band."),
    ("GAP_BIG", "Avenue Spacing", "Coarse-cell spacing between avenues. Higher means fewer avenues."),
    ("PAD_BIG", "Avenue Padding", "Coarse-cell margin that keeps avenues away from the edge."),
    ("GAP_SMALL", "Street Spacing", "Fine-cell spacing between streets. Lower means denser streets."),
    ("PAD_SMALL", "Street Padding", "Fine-cell margin that keeps streets away from the edge."),
    ("N_BIG_CORNERS", "Avenue Corners", "Requested L-corner count in the avenue network."),
    ("N_BIG_TEES", "Avenue T-intersections", "Requested T-intersection count in the avenue network."),
    ("N_SMALL_CORNERS", "Street Corners", "Requested L-corner count in the street network."),
    ("N_SMALL_TEES", "Street T-intersections", "Requested T-intersection count in the street network."),
    ("BANNED_BUILDINGS", "Banned Buildings", "Comma-separated house or landmark IDs skipped during city placement."),
    ("TYPE1_TOP_FIT_CHOICES", "House Variety", "Higher values allow more eligible house designs to appear in similar street lots."),
    ("TYPE2_TOP_FIT_CHOICES", "Landmark Variety", "Higher values allow more eligible landmark designs to appear along avenue frontage."),
    ("TYPE2_SAME_COARSE_SPAN", "Landmark Seperation", "Controls how far apart repeated landmark designs must be. Higher values spread repeated landmarks farther apart."),
]

PREVIEW_CONFIG_GROUPS = [
    (
        "Gap and padding",
        ["GAP_BIG", "PAD_BIG", "GAP_SMALL", "PAD_SMALL"],
    ),
    (
        "Corners and tees",
        ["N_BIG_CORNERS", "N_BIG_TEES", "N_SMALL_CORNERS", "N_SMALL_TEES"],
    ),
    (
        "Building Placement",
        ["BANNED_BUILDINGS", "TYPE1_TOP_FIT_CHOICES", "TYPE2_TOP_FIT_CHOICES", "TYPE2_SAME_COARSE_SPAN"],
    ),
]

PREVIEW_SLIDER_RANGES = {
    "GAP_BIG": (6, 10),
    "GAP_SMALL": (2, 6),
    "PAD_BIG": (2, 6),
    "PAD_SMALL": (4, 8),
    "N_BIG_CORNERS": (0, 20),
    "N_SMALL_CORNERS": (0, 20),
    "N_BIG_TEES": (0, 20),
    "N_SMALL_TEES": (0, 20),
    "TYPE1_TOP_FIT_CHOICES": (5, 9),
    "TYPE2_TOP_FIT_CHOICES": (1, 5),
    "TYPE2_SAME_COARSE_SPAN": (4, 8),
}

CANVAS_SIZE_OPTIONS = {
    "Very Small": "40",
    "Small": "60",
    "Normal": "80",
    "Big": "100",
    "Very Big": "120",
}
CLEARANCE_OPTIONS = {
    "Very Dense": "3",
    "Dense": "4",
    "Normal": "5",
    "Sparse": "6",
    "Very Sparse": "7",
}


def config_default(name):
    value = getattr(config_algo, name)
    if isinstance(value, set):
        return ", ".join(sorted(value))
    if name == "FINE":
        for label, numeric in CANVAS_SIZE_OPTIONS.items():
            if str(value) == numeric:
                return label
    if name == "GAP_MIXED":
        for label, numeric in CLEARANCE_OPTIONS.items():
            if str(value) == numeric:
                return label
    return str(value)


class ImageViewer(ttk.Frame):
    def __init__(self, master, image_path, min_height=240, initial_message=""):
        super().__init__(master)
        self.image_path = image_path
        self._photo = None
        self.initial_message = initial_message

        self.canvas = tk.Canvas(
            self,
            bg=CANVAS_BG,
            highlightthickness=0,
            height=min_height,
        )
        self.x_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.y_scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(
            xscrollcommand=self.x_scroll.set,
            yscrollcommand=self.y_scroll.set,
        )

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.y_scroll.grid(row=0, column=1, sticky="ns")
        self.x_scroll.grid(row=1, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas.bind("<Configure>", lambda _event: self._center_if_smaller())
        self.canvas.bind("<Enter>", lambda _event: self.canvas.focus_set())
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda _event: self._scroll_y(-3))
        self.canvas.bind("<Button-5>", lambda _event: self._scroll_y(3))
        self.canvas.bind("<Shift-Button-4>", lambda _event: self._scroll_x(-3))
        self.canvas.bind("<Shift-Button-5>", lambda _event: self._scroll_x(3))
        self.show_message(initial_message)

    def show_message(self, message):
        self._photo = None
        self.canvas.delete("all")
        self.canvas.create_text(
            20,
            20,
            anchor="nw",
            fill=CANVAS_TEXT,
            font=("Segoe UI", 11),
            text=message,
        )
        self.canvas.configure(scrollregion=(0, 0, 600, 160))

    def load_image(self):
        self.canvas.delete("all")
        if not os.path.exists(self.image_path):
            self.canvas.create_text(
                20,
                20,
                anchor="nw",
                fill=CANVAS_TEXT,
                font=("Segoe UI", 11),
                text=f"Image not found:\n{os.path.relpath(self.image_path, ROOT_DIR)}",
            )
            self.canvas.configure(scrollregion=(0, 0, 600, 160))
            return

        if Image and ImageTk:
            image = Image.open(self.image_path)
            self._photo = ImageTk.PhotoImage(image)
        else:
            self._photo = tk.PhotoImage(file=self.image_path)

        self.canvas.create_image(0, 0, anchor="nw", image=self._photo, tags=("image",))
        self.canvas.configure(scrollregion=(0, 0, self._photo.width(), self._photo.height()))
        self._center_if_smaller()

    def _center_if_smaller(self):
        if not self._photo:
            return
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        image_width = self._photo.width()
        image_height = self._photo.height()
        x = max((width - image_width) // 2, 0)
        y = max((height - image_height) // 2, 0)
        self.canvas.coords("image", x, y)
        self.canvas.configure(
            scrollregion=(0, 0, max(width, image_width), max(height, image_height))
        )

    def _wheel_units(self, delta):
        if delta == 0:
            return 0
        direction = -1 if delta > 0 else 1
        steps = max(1, abs(delta) // 120)
        return direction * steps * 3

    def _on_mouse_wheel(self, event):
        self._scroll_y(self._wheel_units(event.delta))
        return "break"

    def _on_shift_mouse_wheel(self, event):
        self._scroll_x(self._wheel_units(event.delta))
        return "break"

    def _scroll_y(self, units):
        if units:
            self.canvas.yview_scroll(units, "units")

    def _scroll_x(self, units):
        if units:
            self.canvas.xview_scroll(units, "units")


class SquareZoomImageViewer(ttk.Frame):
    def __init__(self, master, title, initial_message=""):
        super().__init__(master)
        self.title = title
        self.image_path = None
        self._source_image = None
        self._photo = None
        self._zoom = 1.0
        self._image_id = None
        self._message_id = None

        ttk.Label(self, text=title).grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 8),
        )
        self.canvas = tk.Canvas(
            self,
            bg=CANVAS_BG,
            highlightthickness=0,
            width=420,
            height=420,
        )
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.canvas.bind("<Configure>", lambda _event: self._fit_square())
        self.canvas.bind("<Enter>", lambda _event: self.canvas.focus_set())
        self.canvas.bind("<MouseWheel>", self._on_zoom_wheel)
        self.canvas.bind("<Button-4>", lambda event: self._zoom_at(event.x, event.y, 1.12))
        self.canvas.bind("<Button-5>", lambda event: self._zoom_at(event.x, event.y, 1 / 1.12))
        self.canvas.bind("<ButtonPress-1>", self._start_pan)
        self.canvas.bind("<B1-Motion>", self._pan)
        self.show_message(initial_message)

    def show_message(self, message):
        self._source_image = None
        self._photo = None
        self._image_id = None
        self.canvas.delete("all")
        self._message_id = self.canvas.create_text(
            20,
            20,
            anchor="nw",
            fill=CANVAS_TEXT,
            font=("Segoe UI", 11),
            text=message,
            width=360,
        )
        self.canvas.configure(scrollregion=(0, 0, 420, 420))

    def load_image(self, image_path):
        self.image_path = image_path
        self.canvas.delete("all")
        self._image_id = None
        self._message_id = None
        if not os.path.exists(image_path):
            self.show_message(f"Image not found:\n{os.path.relpath(image_path, ROOT_DIR)}")
            return
        if Image is None or ImageTk is None:
            self._photo = tk.PhotoImage(file=image_path)
            self._image_id = self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
            self.canvas.configure(scrollregion=(0, 0, self._photo.width(), self._photo.height()))
            return

        self._source_image = Image.open(image_path).convert("RGBA")
        self._zoom = self._initial_zoom()
        self._render_image(center=True)

    def _fit_square(self):
        size = min(self.winfo_width(), max(self.winfo_height() - 28, 1))
        if size > 1:
            self.canvas.configure(width=size, height=size)
        if self._source_image and not self._photo:
            self._render_image(center=True)

    def _initial_zoom(self):
        if not self._source_image:
            return 1.0
        canvas_size = max(min(self.canvas.winfo_width(), self.canvas.winfo_height()), 1)
        longest_edge = max(self._source_image.width, self._source_image.height)
        return max(canvas_size / longest_edge, 0.05)

    def _render_image(self, center=False, anchor=None):
        if not self._source_image:
            return
        width = max(1, int(self._source_image.width * self._zoom))
        height = max(1, int(self._source_image.height * self._zoom))
        resample = Image.Resampling.NEAREST if self._zoom >= 1 else Image.Resampling.BILINEAR
        image = self._source_image.resize((width, height), resample)
        self._photo = ImageTk.PhotoImage(image)

        if self._image_id is None:
            self._image_id = self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            self.canvas.itemconfigure(self._image_id, image=self._photo)

        if center:
            x = max((self.canvas.winfo_width() - width) // 2, 0)
            y = max((self.canvas.winfo_height() - height) // 2, 0)
        elif anchor:
            canvas_x, canvas_y, source_x, source_y = anchor
            x = canvas_x - source_x * self._zoom
            y = canvas_y - source_y * self._zoom
        else:
            x, y = self.canvas.coords(self._image_id)

        self.canvas.coords(self._image_id, x, y)
        bbox = self.canvas.bbox(self._image_id) or (0, 0, width, height)
        self.canvas.configure(
            scrollregion=(
                min(0, bbox[0]),
                min(0, bbox[1]),
                max(self.canvas.winfo_width(), bbox[2]),
                max(self.canvas.winfo_height(), bbox[3]),
            )
        )

    def _on_zoom_wheel(self, event):
        factor = 1.12 if event.delta > 0 else 1 / 1.12
        self._zoom_at(event.x, event.y, factor)
        return "break"

    def _zoom_at(self, canvas_x, canvas_y, factor):
        if not self._source_image or self._image_id is None:
            return "break"
        x0, y0 = self.canvas.coords(self._image_id)
        source_x = (canvas_x - x0) / self._zoom
        source_y = (canvas_y - y0) / self._zoom
        self._zoom = min(max(self._zoom * factor, 0.05), 8.0)
        self._render_image(anchor=(canvas_x, canvas_y, source_x, source_y))
        return "break"

    def _start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def _pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)


class ConfigPanel(ttk.LabelFrame):
    def __init__(self, master, title, world_value, area_value):
        super().__init__(master, text=title, padding=10)

        self.base_title = title
        self.world_var = tk.StringVar(value=world_value)
        self.area_var = tk.StringVar(value=area_value)
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0)

        ttk.Label(self, text="World location").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(self, textvariable=self.world_var).grid(row=0, column=1, sticky="ew", padx=(0, 14))
        ttk.Label(self, text="Area to scan").grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Entry(self, textvariable=self.area_var).grid(row=0, column=3, sticky="ew", padx=(0, 10))
        self.extract_button = ttk.Button(
            self,
            text="Extract",
            width=10,
        )
        self.extract_button.grid(row=0, column=4, rowspan=2, sticky="nsew")
        self.progress = ttk.Progressbar(
            self,
            mode="determinate",
            variable=self.progress_var,
            maximum=1,
        )
        self.progress.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 0), padx=(0, 10))

        self.columnconfigure(1, weight=1)
        self.columnconfigure(3, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

    def set_extract_command(self, command):
        self.extract_button.configure(command=command)

    def set_busy(self, busy):
        self.extract_button.configure(state="disabled" if busy else "normal")

    def set_status(self, status):
        self.status_var.set(status)
        self.configure(text=f"{self.base_title} - {status}")

    def start_progress(self, total_steps):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.configure(maximum=max(total_steps, 1))
        self.progress_var.set(0)

    def start_indeterminate_progress(self):
        self.progress_var.set(0)
        self.progress.configure(mode="indeterminate")
        self.progress.start(10)

    def set_progress(self, completed_steps):
        self.progress_var.set(completed_steps)

    def stop_progress(self):
        self.progress.stop()
        self.progress.configure(mode="determinate")

    def finish_progress(self):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress_var.set(float(self.progress.cget("maximum")))


class IntegerSlider(ttk.Frame):
    def __init__(self, master, text_var, minimum, maximum):
        super().__init__(master)
        self.text_var = text_var
        self.minimum = minimum
        self.maximum = maximum
        self.value_var = tk.IntVar(value=self._coerce(text_var.get()))

        self.scale = ttk.Scale(
            self,
            from_=minimum,
            to=maximum,
            orient="horizontal",
            command=self._on_slide,
        )
        self.scale.set(self.value_var.get())
        self.scale.grid(row=0, column=0, sticky="ew")
        ttk.Label(self, textvariable=self.value_var, width=3, anchor="e").grid(
            row=0,
            column=1,
            sticky="e",
            padx=(6, 0),
        )
        self.ticks = tk.Canvas(self, height=10, highlightthickness=0)
        self.ticks.grid(row=1, column=0, sticky="ew", pady=(1, 0))
        self.ticks.bind("<Configure>", lambda _event: self._draw_ticks())
        self.columnconfigure(0, weight=1)
        text_var.trace_add("write", self._on_text_change)

    def _coerce(self, value):
        try:
            parsed = int(float(value))
        except ValueError:
            parsed = self.minimum
        return min(max(parsed, self.minimum), self.maximum)

    def _on_slide(self, value):
        parsed = self._coerce(value)
        self.value_var.set(parsed)
        if abs(self.scale.get() - parsed) > 0.001:
            self.scale.set(parsed)
        if self.text_var.get() != str(parsed):
            self.text_var.set(str(parsed))

    def _on_text_change(self, *_args):
        parsed = self._coerce(self.text_var.get())
        if self.value_var.get() != parsed:
            self.value_var.set(parsed)
            self.scale.set(parsed)

    def _draw_ticks(self):
        self.ticks.delete("all")
        width = self.ticks.winfo_width()
        if width <= 1:
            return
        inset = max(8, int(9 * float(self.tk.call("tk", "scaling"))))
        span = max(width - inset * 2, 1)
        steps = max(self.maximum - self.minimum, 1)
        for index in range(steps + 1):
            x = inset + span * index / steps
            self.ticks.create_line(x, 1, x, 8, fill=TICK)


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.window = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, event):
        if self.window or not self.text:
            return
        x = event.x_root + 12
        y = event.y_root + 12
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.window,
            text=self.text,
            padx=8,
            pady=5,
            bg=TOOLTIP_BG,
            fg=TOOLTIP_TEXT,
            font=("Segoe UI", 10),
            wraplength=280,
        )
        label.pack()

    def _hide(self, _event=None):
        if self.window:
            self.window.destroy()
            self.window = None


class ExtractionTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=12)

        panes = ttk.PanedWindow(self, orient="vertical")
        panes.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        road_section = self._build_section(
            panes,
            title="Extracted production roads",
            image_path=ROAD_CONTACT_SHEET,
            config_title="Road extraction config",
            area_value=format_box(ROAD_BOX),
            min_height=220,
            scripts=[
                "01_roads_production/schematics/extract_roads.py",
                "01_roads_production/render_roads.py",
            ],
            area_env_key="MC_CITY_ROAD_BOX",
            expected_items=14,
            waiting_message="Click Extract to scan modern road assets and render the contact sheet.",
        )
        build_section = self._build_section(
            panes,
            title="Extracted production builds",
            image_path=BUILD_CONTACT_SHEET,
            config_title="Build extraction config",
            area_value=format_build_types(BUILD_TYPES),
            min_height=300,
            scripts=[
                "02_builds_production/schematics/extract_builds.py",
                "02_builds_production/render_builds.py",
            ],
            area_env_key="MC_CITY_BUILD_TYPES",
            expected_items=None,
            waiting_message="Click Extract to scan modern build assets and render the contact sheet.",
        )

        panes.add(road_section, weight=1)
        panes.add(build_section, weight=2)

    def _build_section(
        self,
        master,
        title,
        image_path,
        config_title,
        area_value,
        min_height,
        scripts,
        area_env_key,
        expected_items,
        waiting_message,
    ):
        section = ttk.Frame(master)
        ttk.Label(section, text=title).grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 8),
        )
        viewer = ImageViewer(
            section,
            image_path,
            min_height=min_height,
            initial_message=waiting_message,
        )
        viewer.grid(row=1, column=0, sticky="nsew")

        config = ConfigPanel(section, config_title, SAVE, area_value)
        config.set_extract_command(
            lambda: self._run_extract(config, viewer, scripts, area_env_key, expected_items)
        )
        config.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        section.rowconfigure(1, weight=1)
        section.columnconfigure(0, weight=1)
        return section

    def _run_extract(self, config, viewer, scripts, area_env_key, expected_items):
        env = os.environ.copy()
        env["MC_CITY_SAVE"] = config.world_var.get().strip()
        env[area_env_key] = config.area_var.get().strip()

        def worker():
            self.after(0, lambda: config.set_busy(True))
            self.after(0, config.start_indeterminate_progress)
            self.after(0, lambda: config.set_status("Preparing extract pipeline..."))
            try:
                item_total = expected_items
                for script in scripts:
                    script_path = os.path.join(ROOT_DIR, script)
                    is_render = "render_" in os.path.basename(script)
                    phase = "Rendering" if is_render else "Extracting"
                    completed = 0
                    detected_total = 0

                    if item_total is not None:
                        self.after(0, lambda total=item_total: config.start_progress(total))
                    else:
                        self.after(0, config.start_indeterminate_progress)

                    self.after(
                        0,
                        lambda phase=phase, script=script: config.set_status(
                            f"{phase}: {script}"
                        ),
                    )

                    process = subprocess.Popen(
                        [sys.executable, "-u", script_path],
                        cwd=ROOT_DIR,
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                    )
                    output = []
                    assert process.stdout is not None
                    for line in process.stdout:
                        output.append(line)
                        stripped = line.strip()

                        build_count = re.search(r"type\s+\d+\s+region:\s+(\d+)\s+builds", stripped)
                        if build_count:
                            detected_total += int(build_count.group(1))
                            item_total = detected_total
                            self.after(0, lambda total=item_total: config.start_progress(total))
                            continue

                        road_count = re.search(r"(\d+)\s+signs,\s+(\d+)\s+components", stripped)
                        if road_count and expected_items is None:
                            item_total = int(road_count.group(1))
                            self.after(0, lambda total=item_total: config.start_progress(total))
                            continue

                        if stripped.startswith("extracted ") or stripped.startswith("saved "):
                            completed += 1
                            if item_total is None:
                                item_total = max(completed, 1)
                                self.after(0, lambda total=item_total: config.start_progress(total))
                            self.after(0, lambda value=completed: config.set_progress(value))
                            self.after(
                                0,
                                lambda phase=phase, completed=completed, total=item_total: config.set_status(
                                    f"{phase} {completed}/{total}"
                                ),
                            )

                    returncode = process.wait()
                    if returncode != 0:
                        raise RuntimeError(
                            f"{script} failed with exit code {returncode}\n\n"
                            f"{''.join(output)}"
                        )
                    if item_total is not None:
                        self.after(0, config.finish_progress)
            except Exception as exc:
                message = str(exc).strip()
                self.after(0, config.stop_progress)
                self.after(0, lambda: config.set_status("Extract failed"))
                self.after(0, lambda: messagebox.showerror("Extract failed", message))
            else:
                self.after(0, viewer.load_image)
                self.after(0, config.finish_progress)
                self.after(0, lambda: config.set_status("Extract complete"))
            finally:
                self.after(0, lambda: config.set_busy(False))

        threading.Thread(target=worker, daemon=True).start()


class PreviewTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=12)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="nsew")
        top.columnconfigure(0, weight=1, uniform="preview")
        top.columnconfigure(1, weight=1, uniform="preview")
        top.rowconfigure(0, weight=1)

        self.grid_viewer = SquareZoomImageViewer(
            top,
            "Grid simulation",
            initial_message="Run Preview to generate the grid simulation image.",
        )
        self.grid_viewer.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self.city_viewer = SquareZoomImageViewer(
            top,
            "City simulation",
            initial_message="Run Preview to generate the city simulation image.",
        )
        self.city_viewer.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        self.preview_config_title = "Preview config"
        self.preview_config = ttk.LabelFrame(self, text=self.preview_config_title, padding=10)
        self.preview_config.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        bottom = self.preview_config
        bottom.columnconfigure(6, weight=1)

        self.seed_var = tk.StringVar(value="5")
        self.status_var = tk.StringVar(value="Ready")
        self.config_vars = {
            name: tk.StringVar(value=config_default(name))
            for name, _label, _description in PREVIEW_CONFIGS
        }
        config_lookup = {
            name: (label, description)
            for name, label, description in PREVIEW_CONFIGS
        }
        ttk.Label(bottom, text="Seed").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(bottom, textvariable=self.seed_var, width=14).grid(row=0, column=1, sticky="w")
        canvas_label = ttk.Label(bottom, text="City Size")
        canvas_label.grid(row=0, column=2, sticky="w", padx=(14, 8))
        Tooltip(canvas_label, config_lookup["FINE"][1])
        canvas_input = ttk.Combobox(
            bottom,
            textvariable=self.config_vars["FINE"],
            values=list(CANVAS_SIZE_OPTIONS),
            state="readonly",
            width=12,
        )
        canvas_input.grid(row=0, column=3, sticky="w")
        Tooltip(canvas_input, config_lookup["FINE"][1])
        clearance_label = ttk.Label(bottom, text="Grid Density")
        clearance_label.grid(row=0, column=4, sticky="w", padx=(14, 8))
        Tooltip(clearance_label, config_lookup["GAP_MIXED"][1])
        clearance_input = ttk.Combobox(
            bottom,
            textvariable=self.config_vars["GAP_MIXED"],
            values=list(CLEARANCE_OPTIONS),
            state="readonly",
            width=13,
        )
        clearance_input.grid(row=0, column=5, sticky="w")
        Tooltip(clearance_input, config_lookup["GAP_MIXED"][1])
        self.preview_button = ttk.Button(
            bottom,
            text="Preview",
            command=self._run_preview,
            width=10,
        )
        self.preview_button.grid(row=0, column=7, sticky="e", padx=(10, 0))

        config_grid = ttk.Frame(bottom)
        config_grid.grid(row=1, column=0, columnspan=8, sticky="ew", pady=(10, 0))
        for column in range(len(PREVIEW_CONFIG_GROUPS)):
            config_grid.columnconfigure(column, weight=1, uniform="preview_config")

        for group_col, (group_title, names) in enumerate(PREVIEW_CONFIG_GROUPS):
            group = ttk.LabelFrame(config_grid, text=group_title, padding=8)
            group.grid(row=0, column=group_col, sticky="nsew", padx=(0 if group_col == 0 else 6, 0))
            group.columnconfigure(1, weight=1)
            for row, name in enumerate(names):
                label, description = config_lookup[name]
                label_widget = ttk.Label(group, text=label)
                label_widget.grid(
                    row=row,
                    column=0,
                    sticky="w",
                    padx=(0, 8),
                    pady=3,
                )
                Tooltip(label_widget, description)
                input_widget = self._config_input(group, name)
                input_widget.grid(
                    row=row,
                    column=1,
                    sticky="ew",
                    pady=3,
                )
                Tooltip(input_widget, description)

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def set_status(self, status):
        self.status_var.set(status)
        self.preview_config.configure(text=f"{self.preview_config_title} - {status}")

    def _config_input(self, master, name):
        if name == "GAP_MIXED":
            return ttk.Combobox(
                master,
                textvariable=self.config_vars[name],
                values=list(CLEARANCE_OPTIONS),
                state="readonly",
                width=13,
            )
        if name in PREVIEW_SLIDER_RANGES:
            lo, hi = PREVIEW_SLIDER_RANGES[name]
            return IntegerSlider(master, self.config_vars[name], lo, hi)
        return ttk.Entry(master, textvariable=self.config_vars[name], width=13)

    def _run_preview(self):
        seed = self.seed_var.get().strip()
        try:
            int(seed)
        except ValueError:
            messagebox.showerror("Invalid seed", "Seed must be an integer.")
            return
        try:
            env = self._preview_env()
            fine = env["MC_CITY_FINE"]
        except ValueError as exc:
            messagebox.showerror("Invalid preview config", str(exc))
            return

        scripts = [
            ["02_builds_simulation/draw_builds.py"],
            ["03_grid_simulation/draw_grid.py", "--seed", seed, "--fine", fine],
            ["04_city_simulation/draw_city.py", "--seed", seed, "--fine", fine],
        ]

        def worker():
            self.after(0, lambda: self.preview_button.configure(state="disabled"))
            try:
                for command in scripts:
                    script = command[0]
                    self.after(0, lambda script=script: self.set_status(f"Running {script}..."))
                    result = subprocess.run(
                        [sys.executable, "-u", *command],
                        cwd=ROOT_DIR,
                        env=env,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if result.returncode != 0:
                        raise RuntimeError(
                            f"{script} failed with exit code {result.returncode}\n\n"
                            f"{result.stderr or result.stdout}"
                        )
            except Exception as exc:
                message = str(exc).strip()
                self.after(0, lambda: self.set_status("Preview failed"))
                self.after(0, lambda: messagebox.showerror("Preview failed", message))
            else:
                self.after(0, lambda: self.grid_viewer.load_image(grid_preview_path(seed)))
                self.after(0, lambda: self.city_viewer.load_image(city_preview_path(seed)))
                self.after(0, lambda: self.set_status("Preview complete"))
            finally:
                self.after(0, lambda: self.preview_button.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _preview_env(self):
        env = os.environ.copy()
        for name, _label, _description in PREVIEW_CONFIGS:
            value = self.config_vars[name].get().strip()
            if name == "BANNED_BUILDINGS":
                env[f"MC_CITY_{name}"] = value
                continue
            if name == "FINE":
                try:
                    value = CANVAS_SIZE_OPTIONS[value]
                except KeyError:
                    raise ValueError("City Size must be one of the selector values.")
            if name == "GAP_MIXED":
                try:
                    value = CLEARANCE_OPTIONS[value]
                except KeyError:
                    raise ValueError("Grid Density must be one of the selector values.")
            try:
                int(value)
            except ValueError:
                raise ValueError(f"{name} must be an integer.")
            env[f"MC_CITY_{name}"] = value
        return env


class PlaceholderTab(ttk.Frame):
    def __init__(self, master, title):
        super().__init__(master, padding=12)
        ttk.Label(self, text=title).grid(row=0, column=0, sticky="w")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)


class CityGeneratorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Minecraft City Generator")
        self.minsize(960, 720)
        self.geometry("1180x860")

        self._configure_style()

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        notebook.add(ExtractionTab(notebook), text="Extaction")
        notebook.add(PreviewTab(notebook), text="Preview")
        notebook.add(PlaceholderTab(notebook, "City"), text="City")

    def _configure_style(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")


def main():
    app = CityGeneratorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
