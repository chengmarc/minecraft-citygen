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
from clear_cache import purge_artifacts
from config_path import BUILDS_PROD, CITY_PROD, CITY_SIM, GRID_SIM, ROADS_PROD
from config_world import BUILD_TYPES, ROAD_BOX, SAVE
try:
    from ttkthemes import ThemedTk
except ImportError:  # pragma: no cover - optional theme package.
    ThemedTk = None

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover - tkinter can still show PNGs directly.
    Image = None
    ImageTk = None


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ROAD_CONTACT_SHEET = os.path.join(ROADS_PROD, "_contact_sheet.png")
BUILD_CONTACT_SHEET = os.path.join(BUILDS_PROD, "_contact_sheet.png")

BORDER = "#d8e0ec"
TEXT = "#1f2937"
ACCENT = "#0f6cbd"
CANVAS_BG = "#111827"
CANVAS_TEXT = "#d8e1ef"
TICK = "#bcc7d8"
TOOLTIP_BG = "#101828"
TOOLTIP_TEXT = "#f8fafc"
BUTTON_SHADOW = "#97a3ba"
BUTTON_WIDTH = 8
GUI_THEME = "breeze"


def grid_preview_path(seed):
    return os.path.join(GRID_SIM, f"seed_{seed}_preview.png")


def city_preview_path(seed):
    return os.path.join(CITY_SIM, f"seed_{seed}.png")


def city_render_path(seed):
    return os.path.join(CITY_PROD, f"seed_{seed}.png")


def format_box(box):
    return ", ".join(str(value) for value in box)


def format_build_types(build_types):
    return "; ".join(format_box(build_type) for build_type in build_types)


def format_xyz(pos):
    return ", ".join(str(value) for value in pos)


def parse_xyz(value, label):
    parts = [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    if len(parts) != 3:
        raise ValueError(f"{label} must be three values: x, y, z")
    try:
        return tuple(int(part) for part in parts)
    except ValueError as exc:
        raise ValueError(f"{label} must contain only integers.") from exc


def region_to_xyz_pair(region):
    if len(region) == 6:
        x0, x1, z0, z1, y0, y1 = region
    else:
        _kind, x0, x1, z0, z1, y0, y1 = region
    return (x0, y0, z0), (x1, y1, z1)


def first_build_region(build_types, build_type):
    for region in build_types:
        if region[0] == build_type:
            return region
    return (build_type, 0, 0, 0, 0, 64, 64)


PREVIEW_CONFIGS = [
    ("FINE", "City Size", "Fine-cell width and height of the generated map."),
    ("GAP_MIXED", "Grid Density", "Minimum clearance between a small street and a big avenue band."),
    ("GAP_BIG", "Avenue Spacing", "Coarse-cell spacing between avenues. Higher means fewer avenues."),
    ("PAD_BIG", "Avenue Padding", "Coarse-cell margin that keeps avenues away from the edge."),
    ("GAP_SMALL", "Street Spacing", "Fine-cell spacing between streets. Lower means more streets."),
    ("PAD_SMALL", "Street Padding", "Fine-cell margin that keeps streets away from the edge."),
    ("N_BIG_CORNERS", "Avenue L-corners", "Forced L-corner count in the avenue network."),
    ("N_BIG_TEES", "Avenue T-intersections", "Forced T-intersection count in the avenue network."),
    ("N_SMALL_CORNERS", "Street L-corners", "Forced L-corner count in the street network."),
    ("N_SMALL_TEES", "Street T-intersections", "Forced T-intersection count in the street network."),
    ("BANNED_BUILDINGS", "Banned Buildings", "Comma-separated house or landmark IDs skipped during city placement."),
    ("TYPE1_TOP_FIT_CHOICES", "House Variety", "Higher values allow more eligible house designs to appear in similar street lots."),
    ("TYPE2_TOP_FIT_CHOICES", "Landmark Variety", "Higher values allow more eligible landmark designs to appear along avenue frontage."),
    ("TYPE2_SAME_COARSE_SPAN", "Landmark Separation", "Controls how far apart repeated landmark designs must be. Higher values spread repeated landmarks farther apart."),
]

PREVIEW_CONFIG_GROUPS = [
    (
        "Spacing & Padding",
        ["GAP_BIG", "PAD_BIG", "GAP_SMALL", "PAD_SMALL"],
    ),
    (
        "Corners & Tees",
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
    "N_BIG_CORNERS": (0, 12),
    "N_SMALL_CORNERS": (0, 12),
    "N_BIG_TEES": (0, 12),
    "N_SMALL_TEES": (0, 12),
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

PREVIEW_PROGRESS_WEIGHTS = [
    ("01_roads_simulation/draw_roads.py", 15),
    ("02_builds_simulation/draw_builds.py", 20),
    ("03_grid_simulation/draw_grid.py", 30),
    ("04_city_simulation/draw_city.py", 35),
]

RENDER_PROGRESS_WEIGHTS = [
    ("04_city_production/schematics/construct_city.py", 60),
    ("04_city_production/render_city.py", 40),
]

SCRIPT_PROGRESS_HEADROOM = 0.88
SCRIPT_PROGRESS_TICK_MS = 120


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
    def __init__(self, master, title, initial_message="", min_height=420, show_title=False):
        super().__init__(master, style="Card.TFrame", padding=6)
        self.title = title
        self.image_path = None
        self._source_image = None
        self._photo = None
        self._zoom = 1.0
        self._image_id = None
        self._message_id = None
        self._has_title = bool(title and show_title)

        canvas_row = 1 if self._has_title else 0
        if self._has_title:
            ttk.Label(self, text=title).grid(
                row=0,
                column=0,
                sticky="w",
                pady=(0, 8),
            )
        self.canvas = tk.Canvas(
            self,
            bg=CANVAS_BG,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            bd=0,
            width=420,
            height=min_height,
        )
        self.canvas.grid(row=canvas_row, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(canvas_row, weight=1)

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
        title_offset = 28 if self._has_title else 0
        size = min(self.winfo_width(), max(self.winfo_height() - title_offset, 1))
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


class ActionButton(ttk.Frame):
    def __init__(self, master, **button_kwargs):
        super().__init__(master, style="Page.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.shadow = tk.Frame(self, bg=BUTTON_SHADOW, bd=0, highlightthickness=0)
        self.shadow.grid(row=0, column=0, sticky="nsew", padx=(2, 0), pady=(3, 0))

        self.button = ttk.Button(self, style="Action.TButton", **button_kwargs)
        self.button.grid(row=0, column=0, sticky="nsew", padx=(0, 2), pady=(0, 3))

    def configure(self, cnf=None, **kwargs):
        return self.button.configure(cnf, **kwargs)

    config = configure

    def cget(self, key):
        return self.button.cget(key)

    def state(self, states=None):
        return self.button.state(states)

    def invoke(self):
        return self.button.invoke()


class ExtractionSubPanel(ttk.LabelFrame):
    """Sub-panel for entering extraction area coordinates and triggering extraction."""
    def __init__(self, master, title, area_kind, area_value):
        super().__init__(master, text="", padding=6, style="Inset.TLabelframe")
        self.area_kind = area_kind
        self.area_vars = {}
        self.content = ttk.Frame(self, style="Card.TFrame")

        self.rowconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        self.content.grid(row=1, column=0, sticky="ew")

        if area_kind == "road":
            self._build_road_area(area_value)
        else:
            self._build_build_area(area_value)
        button_rowspan = 1 if area_kind == "road" else 2
        self.extract_button = ActionButton(self.content, text="Extract", width=BUTTON_WIDTH)
        self.extract_button.grid(row=0, column=4, rowspan=button_rowspan, padx=(4, 0))

        self.content.columnconfigure(1, weight=1)
        self.content.columnconfigure(3, weight=1)

    def _build_xyz_row(self, row, label, start_key, end_key, start_value, end_value):
        self.area_vars[start_key] = tk.StringVar(value=format_xyz(start_value))
        self.area_vars[end_key] = tk.StringVar(value=format_xyz(end_value))
        ttk.Label(self.content, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(self.content, textvariable=self.area_vars[start_key]).grid(
            row=row,
            column=1,
            sticky="ew",
            padx=(0, 6),
            pady=2,
        )
        ttk.Label(self.content, text="to").grid(row=row, column=2, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(self.content, textvariable=self.area_vars[end_key]).grid(
            row=row,
            column=3,
            sticky="ew",
            padx=(0, 6),
            pady=2,
        )

    def _build_road_area(self, road_box):
        start, end = region_to_xyz_pair(road_box)
        self._build_xyz_row(0, "Road Assets", "road_start", "road_end", start, end)

    def _build_build_area(self, build_types):
        house = first_build_region(build_types, 1)
        landmark = first_build_region(build_types, 2)
        house_start, house_end = region_to_xyz_pair(house)
        landmark_start, landmark_end = region_to_xyz_pair(landmark)
        self._build_xyz_row(0, "House Assets", "house_start", "house_end", house_start, house_end)
        self._build_xyz_row(1, "Landmark Assets", "landmark_start", "landmark_end", landmark_start, landmark_end)

    def area_env_value(self):
        if self.area_kind == "road":
            start = parse_xyz(self.area_vars["road_start"].get(), "Road cube start")
            end = parse_xyz(self.area_vars["road_end"].get(), "Road cube end")
            return f"{start[0]},{end[0]},{start[2]},{end[2]},{start[1]},{end[1]}"

        house_start = parse_xyz(self.area_vars["house_start"].get(), "House cube start")
        house_end = parse_xyz(self.area_vars["house_end"].get(), "House cube end")
        landmark_start = parse_xyz(self.area_vars["landmark_start"].get(), "Landmark cube start")
        landmark_end = parse_xyz(self.area_vars["landmark_end"].get(), "Landmark cube end")
        house = f"1,{house_start[0]},{house_end[0]},{house_start[2]},{house_end[2]},{house_start[1]},{house_end[1]}"
        landmark = f"2,{landmark_start[0]},{landmark_end[0]},{landmark_start[2]},{landmark_end[2]},{landmark_start[1]},{landmark_end[1]}"
        return f"{house};{landmark}"

    def set_extract_command(self, command):
        self.extract_button.configure(command=command)


class IntegerSlider(ttk.Frame):
    def __init__(self, master, text_var, minimum, maximum):
        super().__init__(master, style="Card.TFrame")
        self.text_var = text_var
        self.minimum = minimum
        self.maximum = maximum
        self.value_var = tk.IntVar(value=self._coerce(text_var.get()))
        tick_bg = self.tk.call("ttk::style", "lookup", "Card.TFrame", "-background") or self.cget("background")

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
        self.ticks = tk.Canvas(self, height=10, highlightthickness=0, bg=tick_bg, bd=0)
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
        super().__init__(master, padding=10, style="Page.TFrame")

        top = ttk.Frame(self, style="Page.TFrame")
        top.grid(row=0, column=0, sticky="nsew")
        top.columnconfigure(0, weight=1, uniform="extract_view")
        top.columnconfigure(1, weight=1, uniform="extract_view")
        top.rowconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.road_viewer = ImageViewer(
            top,
            title="Extracted Road Assets",
            min_height=420,
            initial_message="Click Extract to scan road assets and render the contact sheet.",
        )
        self.road_viewer.image_path = ROAD_CONTACT_SHEET
        self.road_viewer.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        self.build_viewer = ImageViewer(
            top,
            title="Extracted Build Assets",
            min_height=420,
            initial_message="Click Extract to scan build assets and render the contact sheet.",
        )
        self.build_viewer.image_path = BUILD_CONTACT_SHEET
        self.build_viewer.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        self.config_frame = ttk.LabelFrame(
            self,
            text="Extraction Config",
            padding=8,
            style="Card.TLabelframe",
        )
        self.config_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.config_frame.columnconfigure(1, weight=1)

        self.world_var = tk.StringVar(value=SAVE)
        ttk.Label(self.config_frame, text="World Location").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(self.config_frame, textvariable=self.world_var).grid(row=0, column=1, sticky="ew")

        subpanels = ttk.Frame(self.config_frame, style="Card.TFrame")
        subpanels.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        subpanels.columnconfigure(0, weight=1, uniform="extract_config")
        subpanels.columnconfigure(1, weight=1, uniform="extract_config")

        self.road_config = ExtractionSubPanel(subpanels, "Road Assets Region", "road", ROAD_BOX)
        self.road_config.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.road_config.set_extract_command(
            lambda: self._run_extract(
                "road",
                self.road_config,
                self.road_viewer,
                ["01_roads_production/schematics/extract_roads.py", "01_roads_production/render_roads.py"],
                "MC_CITY_ROAD_BOX",
                14,
            )
        )

        self.build_config = ExtractionSubPanel(subpanels, "Build Assets Region", "build", BUILD_TYPES)
        self.build_config.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.build_config.set_extract_command(
            lambda: self._run_extract(
                "build",
                self.build_config,
                self.build_viewer,
                ["02_builds_production/schematics/extract_builds.py", "02_builds_production/render_builds.py"],
                "MC_CITY_BUILD_TYPES",
                None,
            )
        )

        # ---- Progress bar (no label) ----
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self,
            mode="determinate",
            variable=self.progress_var,
        )
        self.progress_bar.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        self.rowconfigure(2, weight=0)
        self.rowconfigure(0, weight=1)

    def set_status(self, status):
        self.config_frame.configure(text=f"Extraction Config - {status}")

    def _run_extract(self, kind, config, viewer, scripts, area_env_key, expected_items):
        env = os.environ.copy()
        env["MC_CITY_SAVE"] = self.world_var.get().strip()
        try:
            env[area_env_key] = config.area_env_value()
        except ValueError as exc:
            messagebox.showerror("Invalid extraction area", str(exc))
            return

        def worker():
            self.after(0, lambda: config.extract_button.configure(state="disabled"))
            self.after(0, lambda: self.progress_bar.configure(mode='indeterminate'))
            self.after(0, lambda: self.progress_bar.start(10))
            self.after(0, lambda: self.set_status(f"Preparing {kind} extract..."))

            try:
                item_total = expected_items
                for script in scripts:
                    script_path = os.path.join(ROOT_DIR, script)
                    is_render = "render_" in os.path.basename(script)
                    phase = "Rendering" if is_render else "Extracting"
                    completed = 0
                    detected_total = 0

                    if item_total is not None:
                        self.after(0, lambda total=item_total: self._start_determinate(total))
                    else:
                        # Keep indeterminate if we don't know total yet
                        pass

                    self.after(
                        0,
                        lambda phase=phase, script=script: self.set_status(
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
                            self.after(0, lambda total=item_total: self._start_determinate(total))
                            continue

                        road_count = re.search(r"(\d+)\s+signs,\s+(\d+)\s+components", stripped)
                        if road_count and expected_items is None:
                            item_total = int(road_count.group(1))
                            self.after(0, lambda total=item_total: self._start_determinate(total))
                            continue

                        if stripped.startswith("extracted ") or stripped.startswith("saved "):
                            completed += 1
                            if item_total is None:
                                item_total = max(completed, 1)
                                self.after(0, lambda total=item_total: self._start_determinate(total))
                            self.after(0, lambda value=completed: self.progress_var.set(value))
                            self.after(
                                0,
                                lambda phase=phase, completed=completed, total=item_total: self.set_status(
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
                        self.after(0, self._finish_progress)
            except Exception as exc:
                message = str(exc).strip()
                self.after(0, self._stop_progress)
                self.after(0, lambda: self.set_status("Extract failed"))
                self.after(0, lambda: messagebox.showerror("Extract failed", message))
            else:
                self.after(0, lambda: viewer.load_image(viewer.image_path))
                self.after(0, self._finish_progress)
                self.after(0, lambda: self.set_status("Extract complete"))
            finally:
                self.after(0, lambda: config.extract_button.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _start_determinate(self, total):
        self.progress_bar.stop()
        self.progress_bar.configure(mode='determinate', maximum=max(total, 1))
        self.progress_var.set(0)

    def _finish_progress(self):
        self.progress_bar.stop()
        self.progress_bar.configure(mode='determinate')
        self.progress_var.set(self.progress_bar.cget('maximum'))

    def _stop_progress(self):
        self.progress_bar.stop()
        self.progress_bar.configure(mode='determinate')


class PreviewTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10, style="Page.TFrame")
        self._progress_after_id = None
        self._progress_soft_target = 0.0
        self._progress_hard_target = 0.0

        top = ttk.Frame(self, style="Page.TFrame")
        top.grid(row=0, column=0, sticky="nsew")
        top.columnconfigure(0, weight=1, uniform="preview")
        top.columnconfigure(1, weight=1, uniform="preview")
        top.rowconfigure(0, weight=1)

        self.grid_viewer = ImageViewer(
            top,
            "Grid Preview",
            initial_message="Click Preview to generate the grid preview image.",
        )
        self.grid_viewer.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        self.city_viewer = ImageViewer(
            top,
            "City Preview",
            initial_message="Click Preview to generate the city preview image.",
        )
        self.city_viewer.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        self.config_frame = ttk.LabelFrame(
            self,
            text="Preview Config",
            padding=8,
            style="Card.TLabelframe",
        )
        self.config_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        bottom = self.config_frame
        bottom.columnconfigure(6, weight=1)

        self.seed_var = tk.StringVar(value="5")
        self.config_vars = {
            name: tk.StringVar(value=config_default(name))
            for name, _label, _description in PREVIEW_CONFIGS
        }
        config_lookup = {
            name: (label, description)
            for name, label, description in PREVIEW_CONFIGS
        }
        ttk.Label(bottom, text="Seed").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(bottom, textvariable=self.seed_var, width=14).grid(row=0, column=1, sticky="w")
        canvas_label = ttk.Label(bottom, text="City Size")
        canvas_label.grid(row=0, column=2, sticky="w", padx=(8, 6))
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
        clearance_label.grid(row=0, column=4, sticky="w", padx=(8, 6))
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
        self.preview_button = ActionButton(
            bottom,
            text="Preview",
            command=self._run_preview,
            width=BUTTON_WIDTH,
        )
        self.preview_button.grid(row=0, column=7, sticky="e", padx=(6, 0))

        config_grid = ttk.Frame(bottom, style="Card.TFrame")
        config_grid.grid(row=1, column=0, columnspan=8, sticky="ew", pady=(6, 0))
        for column in range(len(PREVIEW_CONFIG_GROUPS)):
            config_grid.columnconfigure(column, weight=1, uniform="preview_config")

        for group_col, (group_title, names) in enumerate(PREVIEW_CONFIG_GROUPS):
            group = ttk.LabelFrame(config_grid, text="", padding=6, style="Inset.TLabelframe")
            group.grid(row=0, column=group_col, sticky="nsew", padx=(0 if group_col == 0 else 4, 0))
            group.columnconfigure(1, weight=1)
            for row, name in enumerate(names):
                label, description = config_lookup[name]
                label_widget = ttk.Label(group, text=label)
                label_widget.grid(
                    row=row,
                    column=0,
                    sticky="w",
                    padx=(0, 6),
                    pady=2,
                )
                Tooltip(label_widget, description)
                input_widget = self._config_input(group, name)
                input_widget.grid(
                    row=row,
                    column=1,
                    sticky="ew",
                    pady=2,
                )
                Tooltip(input_widget, description)

        # ---- Progress bar (no label) ----
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self,
            mode="determinate",
            variable=self.progress_var,
        )
        self.progress_bar.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def set_status(self, status):
        self.config_frame.configure(text=f"Preview Config - {status}")

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
            (["01_roads_simulation/draw_roads.py"], PREVIEW_PROGRESS_WEIGHTS[0][1]),
            (["02_builds_simulation/draw_builds.py"], PREVIEW_PROGRESS_WEIGHTS[1][1]),
            (["03_grid_simulation/draw_grid.py", "--seed", seed, "--fine", fine], PREVIEW_PROGRESS_WEIGHTS[2][1]),
            (["04_city_simulation/draw_city.py", "--seed", seed, "--fine", fine], PREVIEW_PROGRESS_WEIGHTS[3][1]),
        ]

        def worker():
            self.after(0, lambda: self.preview_button.configure(state="disabled"))
            self.after(0, self._start_progress)
            self.after(0, lambda: self.set_status("Starting preview..."))

            try:
                completed_weight = 0
                total_scripts = len(scripts)
                for index, (command, weight) in enumerate(scripts, start=1):
                    script = command[0]
                    self.after(
                        0,
                        lambda index=index, total=total_scripts, script=script, completed=completed_weight, weight=weight:
                            self._begin_script_progress(
                                completed,
                                completed + weight,
                                f"Running {index}/{total}: {os.path.basename(script)}",
                            ),
                    )
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
                    completed_weight += weight
                    self.after(0, lambda value=completed_weight: self._complete_script_progress(value))
            except Exception as exc:
                message = str(exc).strip()
                self.after(0, lambda: self.set_status("Preview failed"))
                self.after(0, lambda: messagebox.showerror("Preview failed", message))
            else:
                self.after(0, lambda: self.grid_viewer.load_image(grid_preview_path(seed)))
                self.after(0, lambda: self.city_viewer.load_image(city_preview_path(seed)))
                self.after(0, self._finish_progress)
                self.after(0, lambda: self.set_status("Preview complete"))
            finally:
                self.after(0, self._stop_progress)
                self.after(0, lambda: self.preview_button.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _start_progress(self):
        self._cancel_progress_animation()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", maximum=100)
        self.progress_var.set(0)
        self._progress_soft_target = 0.0
        self._progress_hard_target = 0.0

    def _finish_progress(self):
        self._cancel_progress_animation()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_var.set(self.progress_bar.cget("maximum"))

    def _stop_progress(self):
        self._cancel_progress_animation()
        self.progress_bar.stop()
        self.progress_bar.configure(mode='determinate')

    def _begin_script_progress(self, start_value, end_value, status):
        self._cancel_progress_animation()
        self.progress_var.set(start_value)
        self._progress_hard_target = float(end_value)
        segment = max(float(end_value) - float(start_value), 0.0)
        self._progress_soft_target = float(start_value) + segment * SCRIPT_PROGRESS_HEADROOM
        self.set_status(status)
        self._schedule_progress_tick()

    def _complete_script_progress(self, value):
        self._cancel_progress_animation()
        self.progress_var.set(value)

    def _schedule_progress_tick(self):
        self._progress_after_id = self.after(SCRIPT_PROGRESS_TICK_MS, self._progress_tick)

    def _progress_tick(self):
        self._progress_after_id = None
        current = float(self.progress_var.get())
        if current >= self._progress_soft_target:
            return
        remaining = self._progress_soft_target - current
        step = max(0.2, remaining * 0.07)
        self.progress_var.set(min(current + step, self._progress_soft_target))
        if float(self.progress_var.get()) < self._progress_soft_target:
            self._schedule_progress_tick()

    def _cancel_progress_animation(self):
        if self._progress_after_id is not None:
            self.after_cancel(self._progress_after_id)
            self._progress_after_id = None

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


class CityTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10, style="Page.TFrame")
        self._progress_after_id = None
        self._progress_soft_target = 0.0
        self._progress_hard_target = 0.0

        self.city_viewer = ImageViewer(
            self,
            "City Schematic Render",
            initial_message="Click Render to construct and render the city schematic.",
        )
        self.city_viewer.grid(row=0, column=0, sticky="nsew")

        self.config_frame = ttk.LabelFrame(
            self,
            text="Render Config",
            padding=8,
            style="Card.TLabelframe",
        )
        self.config_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        bottom = self.config_frame
        bottom.columnconfigure(6, weight=1)

        self.seed_var = tk.StringVar(value="5")
        self.config_vars = {
            name: tk.StringVar(value=config_default(name))
            for name, _label, _description in PREVIEW_CONFIGS
        }
        config_lookup = {
            name: (label, description)
            for name, label, description in PREVIEW_CONFIGS
        }

        ttk.Label(bottom, text="Seed").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(bottom, textvariable=self.seed_var, width=14).grid(row=0, column=1, sticky="w")
        city_size_label = ttk.Label(bottom, text="City Size")
        city_size_label.grid(row=0, column=2, sticky="w", padx=(8, 6))
        Tooltip(city_size_label, config_lookup["FINE"][1])
        city_size_input = ttk.Combobox(
            bottom,
            textvariable=self.config_vars["FINE"],
            values=list(CANVAS_SIZE_OPTIONS),
            state="readonly",
            width=12,
        )
        city_size_input.grid(row=0, column=3, sticky="w")
        Tooltip(city_size_input, config_lookup["FINE"][1])
        density_label = ttk.Label(bottom, text="Grid Density")
        density_label.grid(row=0, column=4, sticky="w", padx=(8, 6))
        Tooltip(density_label, config_lookup["GAP_MIXED"][1])
        density_input = ttk.Combobox(
            bottom,
            textvariable=self.config_vars["GAP_MIXED"],
            values=list(CLEARANCE_OPTIONS),
            state="readonly",
            width=13,
        )
        density_input.grid(row=0, column=5, sticky="w")
        Tooltip(density_input, config_lookup["GAP_MIXED"][1])
        self.render_button = ActionButton(bottom, text="Render", command=self._run_render, width=BUTTON_WIDTH)
        self.render_button.grid(row=0, column=7, sticky="e", padx=(6, 0))

        config_grid = ttk.Frame(bottom, style="Card.TFrame")
        config_grid.grid(row=1, column=0, columnspan=8, sticky="ew", pady=(6, 0))
        for column in range(len(PREVIEW_CONFIG_GROUPS)):
            config_grid.columnconfigure(column, weight=1, uniform="city_config")

        for group_col, (group_title, names) in enumerate(PREVIEW_CONFIG_GROUPS):
            group = ttk.LabelFrame(config_grid, text="", padding=6, style="Inset.TLabelframe")
            group.grid(row=0, column=group_col, sticky="nsew", padx=(0 if group_col == 0 else 4, 0))
            group.columnconfigure(1, weight=1)
            for row, name in enumerate(names):
                label, description = config_lookup[name]
                label_widget = ttk.Label(group, text=label)
                label_widget.grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
                Tooltip(label_widget, description)
                input_widget = self._config_input(group, name)
                input_widget.grid(row=row, column=1, sticky="ew", pady=2)
                Tooltip(input_widget, description)

        # ---- Progress bar (no label) ----
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self,
            mode="determinate",
            variable=self.progress_var,
        )
        self.progress_bar.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def set_status(self, status):
        self.config_frame.configure(text=f"Render Config - {status}")

    def _config_input(self, master, name):
        if name in PREVIEW_SLIDER_RANGES:
            lo, hi = PREVIEW_SLIDER_RANGES[name]
            return IntegerSlider(master, self.config_vars[name], lo, hi)
        return ttk.Entry(master, textvariable=self.config_vars[name], width=13)

    def _run_render(self):
        seed = self.seed_var.get().strip()
        try:
            int(seed)
        except ValueError:
            messagebox.showerror("Invalid seed", "Seed must be an integer.")
            return
        try:
            env = self._city_env()
            fine = env["MC_CITY_FINE"]
        except ValueError as exc:
            messagebox.showerror("Invalid city config", str(exc))
            return

        scripts = [
            (["04_city_production/schematics/construct_city.py", "--seed", seed, "--fine", fine], RENDER_PROGRESS_WEIGHTS[0][1]),
            (["04_city_production/render_city.py"], RENDER_PROGRESS_WEIGHTS[1][1]),
        ]

        def worker():
            self.after(0, lambda: self.render_button.configure(state="disabled"))
            self.after(0, self._start_progress)
            self.after(0, lambda: self.set_status("Starting render..."))

            try:
                completed_weight = 0
                total_scripts = len(scripts)
                for index, (command, weight) in enumerate(scripts, start=1):
                    script = command[0]
                    self.after(
                        0,
                        lambda index=index, total=total_scripts, script=script, completed=completed_weight, weight=weight:
                            self._begin_script_progress(
                                completed,
                                completed + weight,
                                f"Running {index}/{total}: {os.path.basename(script)}",
                            ),
                    )
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
                    completed_weight += weight
                    self.after(0, lambda value=completed_weight: self._complete_script_progress(value))
            except Exception as exc:
                message = str(exc).strip()
                self.after(0, lambda: self.set_status("Render failed"))
                self.after(0, lambda: messagebox.showerror("Render failed", message))
            else:
                self.after(0, lambda: self.city_viewer.load_image(city_render_path(seed)))
                self.after(0, self._finish_progress)
                self.after(0, lambda: self.set_status("Render complete"))
            finally:
                self.after(0, self._stop_progress)
                self.after(0, lambda: self.render_button.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _start_progress(self):
        self._cancel_progress_animation()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", maximum=100)
        self.progress_var.set(0)
        self._progress_soft_target = 0.0
        self._progress_hard_target = 0.0

    def _finish_progress(self):
        self._cancel_progress_animation()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_var.set(self.progress_bar.cget("maximum"))

    def _stop_progress(self):
        self._cancel_progress_animation()
        self.progress_bar.stop()
        self.progress_bar.configure(mode='determinate')

    def _begin_script_progress(self, start_value, end_value, status):
        self._cancel_progress_animation()
        self.progress_var.set(start_value)
        self._progress_hard_target = float(end_value)
        segment = max(float(end_value) - float(start_value), 0.0)
        self._progress_soft_target = float(start_value) + segment * SCRIPT_PROGRESS_HEADROOM
        self.set_status(status)
        self._schedule_progress_tick()

    def _complete_script_progress(self, value):
        self._cancel_progress_animation()
        self.progress_var.set(value)

    def _schedule_progress_tick(self):
        self._progress_after_id = self.after(SCRIPT_PROGRESS_TICK_MS, self._progress_tick)

    def _progress_tick(self):
        self._progress_after_id = None
        current = float(self.progress_var.get())
        if current >= self._progress_soft_target:
            return
        remaining = self._progress_soft_target - current
        step = max(0.2, remaining * 0.07)
        self.progress_var.set(min(current + step, self._progress_soft_target))
        if float(self.progress_var.get()) < self._progress_soft_target:
            self._schedule_progress_tick()

    def _cancel_progress_animation(self):
        if self._progress_after_id is not None:
            self.after_cancel(self._progress_after_id)
            self._progress_after_id = None

    def _city_env(self):
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


APP_TK_BASE = ThemedTk if ThemedTk is not None else tk.Tk


class CityGeneratorApp(APP_TK_BASE):
    def __init__(self):
        if ThemedTk is not None:
            super().__init__(theme=GUI_THEME)
        else:
            super().__init__()
        purge_artifacts()
        self.title("Minecraft City Generator")
        self.minsize(960, 720)
        self.geometry("1160x840")

        theme_bg = self._configure_style()
        self.configure(bg=theme_bg)

        shell = ttk.Frame(self, style="Page.TFrame", padding=10)
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(shell, style="App.TNotebook")
        notebook.grid(row=0, column=0, sticky="nsew")
        notebook.add(ExtractionTab(notebook), text="Extraction")
        notebook.add(PreviewTab(notebook), text="Preview")
        notebook.add(CityTab(notebook), text="Render")

    def _configure_style(self):
        style = ttk.Style(self)
        theme_names = set(style.theme_names())
        if GUI_THEME in theme_names:
            style.theme_use(GUI_THEME)
        elif "vista" in theme_names:
            style.theme_use("vista")
        elif "clam" in theme_names:
            style.theme_use("clam")

        frame_bg = style.lookup("TFrame", "background") or self.cget("bg")
        label_fg = style.lookup("TLabel", "foreground") or TEXT

        style.configure(".", font=("Segoe UI", 10), foreground=label_fg)
        style.configure("Page.TFrame", background=frame_bg)
        style.configure("Card.TFrame", background=frame_bg)
        style.configure("TLabel", background=frame_bg, foreground=label_fg)
        style.configure("App.TNotebook", background=frame_bg, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 6), font=("Segoe UI", 10, "bold"))
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Card.TLabelframe", background=frame_bg)
        style.configure("Card.TLabelframe.Label", background=frame_bg, foreground=label_fg, font=("Segoe UI", 10, "bold"))
        style.configure("Inset.TLabelframe", background=frame_bg)
        style.configure("Inset.TLabelframe.Label", background=frame_bg, foreground=label_fg, font=("Segoe UI", 10, "bold"))
        style.configure("TButton", font=("Segoe UI", 20, "bold"))
        style.configure("Action.TButton", font=("Segoe UI", 20, "bold"), padding=(2, 1), borderwidth=2, relief="raised")
        style.map("Action.TButton", relief=[("pressed", "sunken"), ("active", "raised")])
        style.configure("TEntry", padding=3)
        style.configure("TCombobox", padding=3)

        return frame_bg


def main():
    app = CityGeneratorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
