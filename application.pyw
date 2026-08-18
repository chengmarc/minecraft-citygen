"""Tkinter GUI for inspecting and configuring the city-generation pipeline."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import traceback


def _configure_tcl_tk():
    tcl_root = os.path.normpath(os.path.join(sys.base_prefix, "tcl"))
    dll_root = os.path.normpath(os.path.join(sys.base_prefix, "DLLs"))
    tcl_library = os.path.join(tcl_root, "tcl8.6")
    tk_library = os.path.join(tcl_root, "tk8.6")
    if os.path.isdir(dll_root):
        os.environ["PATH"] = dll_root + os.pathsep + os.environ.get("PATH", "")
    if os.path.exists(os.path.join(tcl_library, "init.tcl")):
        os.environ["TCL_LIBRARY"] = tcl_library.replace("\\", "/")
    if os.path.exists(os.path.join(tk_library, "tk.tcl")):
        os.environ["TK_LIBRARY"] = tk_library.replace("\\", "/")
    if os.path.isdir(tcl_root):
        roots = [
            os.path.join(tcl_root, "tcl8.6").replace("\\", "/"),
            tcl_root.replace("\\", "/"),
        ]
        os.environ["TCLLIBPATH"] = " ".join("{" + root + "}" for root in roots)


_configure_tcl_tk()

import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

from clear_cache import purge_artifacts
from config import config_algo
from config.config_path import BUILDS_PROD, CITY_PROD, CITY_PROD_SCHEM, CITY_SIM, GRID_SIM, ROADS_PROD
from config.config_algo import DEFAULT_SEED
from config.config_world import BUILD_TYPES, ROAD_BOX, SAVE

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:  # pragma: no cover - tkinter can still show PNGs directly.
    Image = None
    ImageDraw = None
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
GUI_THEME = "vista"
APP_WIDTH = 1024
APP_HEIGHT = 768
UI_RADIUS = 4
STARTUP_ERROR_LOG = os.path.join(ROOT_DIR, "application_startup_error.log")
UI_FONT_FAMILY = "SF Pro Text"
UI_FONT_FALLBACKS = ("Segoe UI Variable", "Segoe UI", "Inter", "Arial")


def _resolve_color(widget, color, fallback):
    try:
        source = color or fallback
        r, g, b = widget.winfo_rgb(source)
        return f"#{r // 256:02x}{g // 256:02x}{b // 256:02x}"
    except Exception:
        return fallback


def _blend(hex_a, hex_b, ratio):
    ratio = max(0.0, min(1.0, float(ratio)))
    a = tuple(int(hex_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(hex_b[i:i + 2], 16) for i in (1, 3, 5))
    mixed = tuple(round(av + (bv - av) * ratio) for av, bv in zip(a, b))
    return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"


def _rounded_image(width, height, radius, fill, outline=None, outline_width=1):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    inset = max(outline_width / 2, 0)
    draw.rounded_rectangle(
        (inset, inset, width - 1 - inset, height - 1 - inset),
        radius=radius,
        fill=fill,
        outline=outline,
        width=outline_width,
    )
    return img


def _replace_layout_element(layout, source, target):
    replaced = []
    for name, options in layout:
        new_options = dict(options)
        children = new_options.get("children")
        if children:
            new_options["children"] = _replace_layout_element(children, source, target)
        replaced.append((target if name == source else name, new_options))
    return replaced


def pick_ui_font(root):
    try:
        installed = set(tkfont.families(root))
    except Exception:
        installed = set()
    for family in (UI_FONT_FAMILY, *UI_FONT_FALLBACKS):
        if family in installed:
            return family
    return "TkDefaultFont"


def ui_font(family, size, *styles):
    return (family, size, *styles)


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
PREVIEW_CONFIG_LOOKUP = {
    name: (label, description)
    for name, label, description in PREVIEW_CONFIGS
}

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
    ("pipeline/01_roads_simulation/draw_roads.py", 15),
    ("pipeline/02_builds_simulation/draw_builds.py", 20),
    ("pipeline/03_grid_simulation/draw_grid.py", 30),
    ("pipeline/04_city_simulation/draw_city.py", 35),
]

RENDER_PROGRESS_WEIGHTS = [
    ("pipeline/04_city_production/construct_city.py", 60),
    ("pipeline/04_city_production/render_city.py", 40),
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


def create_config_vars():
    return {
        name: tk.StringVar(value=config_default(name))
        for name, _label, _description in PREVIEW_CONFIGS
    }


def build_algo_env(config_vars):
    env = os.environ.copy()
    for name, _label, _description in PREVIEW_CONFIGS:
        value = config_vars[name].get().strip()
        if name == "BANNED_BUILDINGS":
            env[f"MC_CITY_{name}"] = value
            continue
        if name == "FINE":
            try:
                value = CANVAS_SIZE_OPTIONS[value]
            except KeyError as exc:
                raise ValueError("City Size must be one of the selector values.") from exc
        if name == "GAP_MIXED":
            try:
                value = CLEARANCE_OPTIONS[value]
            except KeyError as exc:
                raise ValueError("Grid Density must be one of the selector values.") from exc
        try:
            int(value)
        except ValueError as exc:
            raise ValueError(f"{name} must be an integer.") from exc
        env[f"MC_CITY_{name}"] = value
    return env


def validate_seed(seed):
    try:
        int(seed)
    except ValueError as exc:
        raise ValueError("Seed must be an integer.") from exc


def create_config_input(master, text_var, name):
    if name in PREVIEW_SLIDER_RANGES:
        lo, hi = PREVIEW_SLIDER_RANGES[name]
        return IntegerSlider(master, text_var, lo, hi)
    return ttk.Entry(master, textvariable=text_var, width=13)


def build_shared_config_frame(
    config_frame,
    seed_var,
    config_vars,
    action_text,
    action_command,
    uniform_name,
    extra_actions=None,
):
    config_frame.columnconfigure(6, weight=1)

    ttk.Label(config_frame, text="Seed").grid(row=0, column=0, sticky="w", padx=(0, 6))
    ttk.Entry(config_frame, textvariable=seed_var, width=14).grid(row=0, column=1, sticky="w")

    city_size_label = ttk.Label(config_frame, text="City Size")
    city_size_label.grid(row=0, column=2, sticky="w", padx=(8, 6))
    Tooltip(city_size_label, PREVIEW_CONFIG_LOOKUP["FINE"][1])
    city_size_input = ttk.Combobox(
        config_frame,
        textvariable=config_vars["FINE"],
        values=list(CANVAS_SIZE_OPTIONS),
        state="readonly",
        width=12,
    )
    city_size_input.grid(row=0, column=3, sticky="w")
    Tooltip(city_size_input, PREVIEW_CONFIG_LOOKUP["FINE"][1])

    density_label = ttk.Label(config_frame, text="Grid Density")
    density_label.grid(row=0, column=4, sticky="w", padx=(8, 6))
    Tooltip(density_label, PREVIEW_CONFIG_LOOKUP["GAP_MIXED"][1])
    density_input = ttk.Combobox(
        config_frame,
        textvariable=config_vars["GAP_MIXED"],
        values=list(CLEARANCE_OPTIONS),
        state="readonly",
        width=13,
    )
    density_input.grid(row=0, column=5, sticky="w")
    Tooltip(density_input, PREVIEW_CONFIG_LOOKUP["GAP_MIXED"][1])

    actions_frame = ttk.Frame(config_frame, style="Card.TFrame")
    actions_frame.grid(row=0, column=7, sticky="e")

    if extra_actions:
        for column, (text, command) in enumerate(extra_actions):
            extra_button = ActionButton(
                actions_frame,
                text=text,
                command=command,
                width=max(BUTTON_WIDTH, len(text) + 1),
            )
            extra_button.grid(row=0, column=column, sticky="e", padx=(0, 6))

    action_column = len(extra_actions or [])
    action_button = ActionButton(
        actions_frame,
        text=action_text,
        command=action_command,
        width=BUTTON_WIDTH,
    )
    action_button.grid(row=0, column=action_column, sticky="e")

    config_grid = ttk.Frame(config_frame, style="Card.TFrame")
    config_grid.grid(row=1, column=0, columnspan=8, sticky="ew", pady=(6, 0))
    for column in range(len(PREVIEW_CONFIG_GROUPS)):
        config_grid.columnconfigure(column, weight=1, uniform=uniform_name)

    for group_col, (_group_title, names) in enumerate(PREVIEW_CONFIG_GROUPS):
        group = ttk.LabelFrame(config_grid, text="", padding=6, style="Inset.TLabelframe")
        group.grid(row=0, column=group_col, sticky="nsew", padx=(0 if group_col == 0 else 4, 0))
        group.columnconfigure(1, weight=1)
        for row, name in enumerate(names):
            label, description = PREVIEW_CONFIG_LOOKUP[name]
            label_widget = ttk.Label(group, text=label)
            label_widget.grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
            Tooltip(label_widget, description)
            input_widget = create_config_input(group, config_vars[name], name)
            input_widget.grid(row=row, column=1, sticky="ew", pady=2)
            Tooltip(input_widget, description)

    return action_button


def run_weighted_scripts_async(
    owner,
    button,
    scripts,
    env,
    start_status,
    fail_title,
    fail_status,
    complete_status,
    on_success,
):
    def worker():
        owner.after(0, lambda: button.configure(state="disabled"))
        owner.after(0, owner._start_progress)
        owner.after(0, lambda: owner.set_status(start_status))

        try:
            completed_weight = 0
            total_scripts = len(scripts)
            for index, (command, weight) in enumerate(scripts, start=1):
                script = command[0]
                owner.after(
                    0,
                    lambda index=index, total=total_scripts, script=script, completed=completed_weight, weight=weight:
                        owner._begin_script_progress(
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
                owner.after(0, lambda value=completed_weight: owner._complete_script_progress(value))
        except Exception as exc:
            message = str(exc).strip()
            owner.after(0, lambda: owner.set_status(fail_status))
            owner.after(0, lambda: messagebox.showerror(fail_title, message))
        else:
            owner.after(0, on_success)
            owner.after(0, owner._finish_progress)
            owner.after(0, lambda: owner.set_status(complete_status))
        finally:
            owner.after(0, owner._stop_progress)
            owner.after(0, lambda: button.configure(state="normal"))

    threading.Thread(target=worker, daemon=True).start()


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
        self._layout_after_id = None

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

        self.canvas.bind("<Configure>", self._schedule_layout)
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
        font_family = self.winfo_toplevel().ui_font_family
        self._message_id = self.canvas.create_text(
            20,
            20,
            anchor="nw",
            fill=CANVAS_TEXT,
            font=ui_font(font_family, 11),
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

    def _schedule_layout(self, _event=None):
        if self._source_image is None or self._photo is None or self._image_id is None:
            return
        if self._layout_after_id is not None:
            self.after_cancel(self._layout_after_id)
        self._layout_after_id = self.after(60, self._apply_layout)

    def _apply_layout(self):
        self._layout_after_id = None
        if self._image_id is None or self._photo is None:
            return
        x, y = self.canvas.coords(self._image_id)
        width = self._photo.width()
        height = self._photo.height()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if width <= canvas_width:
            x = max((canvas_width - width) // 2, 0)
        if height <= canvas_height:
            y = max((canvas_height - height) // 2, 0)
        self.canvas.coords(self._image_id, x, y)
        self._update_scrollregion()

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
        self._update_scrollregion()

    def _update_scrollregion(self):
        if self._image_id is None:
            return
        bbox = self.canvas.bbox(self._image_id) or (
            0,
            0,
            self._photo.width() if self._photo else 0,
            self._photo.height() if self._photo else 0,
        )
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

        self.button = ttk.Button(self, style="Action.TButton", **button_kwargs)
        self.button.grid(row=0, column=0, sticky="nsew")

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
        self._tick_after_id = None
        self._last_tick_width = None
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
        self.ticks.bind("<Configure>", self._schedule_draw_ticks)
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

    def _schedule_draw_ticks(self, _event=None):
        if self._tick_after_id is not None:
            self.after_cancel(self._tick_after_id)
        self._tick_after_id = self.after(16, self._draw_ticks)

    def _draw_ticks(self):
        self._tick_after_id = None
        self.ticks.delete("all")
        width = self.ticks.winfo_width()
        if width <= 1:
            self._last_tick_width = None
            return
        if self._last_tick_width == width:
            return
        self._last_tick_width = width
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
            font=ui_font(self.widget.winfo_toplevel().ui_font_family, 10),
            wraplength=280,
        )
        label.pack()

    def _hide(self, _event=None):
        if self.window:
            self.window.destroy()
            self.window = None


class WeightedProgressMixin:
    def _init_weighted_progress(self):
        self._progress_after_id = None
        self._progress_soft_target = 0.0

    def _build_progress_bar(self, row):
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self,
            mode="determinate",
            variable=self.progress_var,
        )
        self.progress_bar.grid(row=row, column=0, sticky="ew", pady=(6, 0))

    def _start_progress(self):
        self._cancel_progress_animation()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", maximum=100)
        self.progress_var.set(0)
        self._progress_soft_target = 0.0

    def _finish_progress(self):
        self._cancel_progress_animation()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_var.set(self.progress_bar.cget("maximum"))

    def _stop_progress(self):
        self._cancel_progress_animation()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")

    def _begin_script_progress(self, start_value, end_value, status):
        self._cancel_progress_animation()
        self.progress_var.set(start_value)
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
                    ["pipeline/01_roads_production/extract_roads.py", "pipeline/01_roads_production/render_roads.py"],
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
                    ["pipeline/02_builds_production/extract_builds.py", "pipeline/02_builds_production/render_builds.py"],
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


class PreviewTab(WeightedProgressMixin, ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10, style="Page.TFrame")
        self._init_weighted_progress()

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
        self.seed_var = tk.StringVar(value=str(DEFAULT_SEED))
        self.config_vars = create_config_vars()
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
        self.config_frame.configure(text=f"Preview Config - {status}")

    def _run_preview(self):
        seed = self.seed_var.get().strip()
        try:
            validate_seed(seed)
            env = build_algo_env(self.config_vars)
            fine = env["MC_CITY_FINE"]
        except ValueError as exc:
            title = "Invalid seed" if str(exc) == "Seed must be an integer." else "Invalid preview config"
            messagebox.showerror(title, str(exc))
            return

        scripts = [
            (["pipeline/01_roads_simulation/draw_roads.py"], PREVIEW_PROGRESS_WEIGHTS[0][1]),
            (["pipeline/02_builds_simulation/draw_builds.py"], PREVIEW_PROGRESS_WEIGHTS[1][1]),
            (["pipeline/03_grid_simulation/draw_grid.py", "--seed", seed, "--fine", fine], PREVIEW_PROGRESS_WEIGHTS[2][1]),
            (["pipeline/04_city_simulation/draw_city.py", "--seed", seed, "--fine", fine], PREVIEW_PROGRESS_WEIGHTS[3][1]),
        ]
        run_weighted_scripts_async(
            self,
            self.preview_button,
            scripts,
            env,
            "Starting preview...",
            "Preview failed",
            "Preview failed",
            "Preview complete",
            lambda: (
                self.grid_viewer.load_image(grid_preview_path(seed)),
                self.city_viewer.load_image(city_preview_path(seed)),
            ),
        )


class CityTab(WeightedProgressMixin, ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10, style="Page.TFrame")
        self._init_weighted_progress()

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
        self.seed_var = tk.StringVar(value=str(DEFAULT_SEED))
        self.config_vars = create_config_vars()
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
            validate_seed(seed)
            env = build_algo_env(self.config_vars)
            fine = env["MC_CITY_FINE"]
        except ValueError as exc:
            title = "Invalid seed" if str(exc) == "Seed must be an integer." else "Invalid city config"
            messagebox.showerror(title, str(exc))
            return

        scripts = [
            (["pipeline/04_city_production/construct_city.py", "--seed", seed, "--fine", fine], RENDER_PROGRESS_WEIGHTS[0][1]),
            (["pipeline/04_city_production/render_city.py"], RENDER_PROGRESS_WEIGHTS[1][1]),
        ]
        run_weighted_scripts_async(
            self,
            self.render_button,
            scripts,
            env,
            "Starting render...",
            "Render failed",
            "Render failed",
            "Render complete",
            lambda: self.city_viewer.load_image(city_render_path(seed)),
        )


APP_TK_BASE = tk.Tk


class CityGeneratorApp(APP_TK_BASE):
    def __init__(self):
        purge_artifacts()
        super().__init__()
        self.withdraw()
        self.ui_font_family = pick_ui_font(self)
        self.title("Minecraft City Generator")
        self.geometry(f"{APP_WIDTH}x{APP_HEIGHT}")

        theme_bg = self._configure_style()
        self.configure(bg=theme_bg)

        shell = ttk.Frame(self, style="Page.TFrame", padding=10)
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(shell, style="App.TNotebook")
        notebook.grid(row=0, column=0, sticky="nsew")
        self.notebook = notebook
        self._tab_builders = {
            "Extraction": ExtractionTab,
            "Preview": PreviewTab,
            "Render": CityTab,
        }
        self._tab_frames = {}
        self._loaded_tabs = set()
        for title in self._tab_builders:
            frame = ttk.Frame(notebook, style="Page.TFrame")
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
            notebook.add(frame, text=title)
            self._tab_frames[title] = frame
        notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed, add="+")
        self._load_tab("Extraction")
        self.update_idletasks()
        self.deiconify()

    def _tab_title(self, tab_id):
        return self.notebook.tab(tab_id, "text")

    def _load_tab(self, title):
        if title in self._loaded_tabs:
            return
        frame = self._tab_frames[title]
        tab = self._tab_builders[title](frame)
        tab.grid(row=0, column=0, sticky="nsew")
        self._loaded_tabs.add(title)

    def _on_tab_changed(self, _event=None):
        self._load_tab(self._tab_title(self.notebook.select()))

    def _photo_asset(self, key, width, height, radius, fill, outline=None, outline_width=1):
        image = ImageTk.PhotoImage(
            _rounded_image(width, height, radius, fill, outline=outline, outline_width=outline_width)
        )
        self._theme_images[key] = image
        return image

    def _replace_style_element(self, style, style_name, source, target):
        try:
            current = style.layout(style_name)
            style.layout(style_name, _replace_layout_element(current, source, target))
        except tk.TclError:
            return

    def _create_image_element(self, style, name, default, *states, border=8, sticky="nsew"):
        try:
            style.element_create(name, "image", default, *states, border=border, sticky=sticky)
        except tk.TclError:
            return

    def _apply_rounded_theme(self, style, frame_bg, label_fg):
        if Image is None or ImageDraw is None or ImageTk is None:
            return

        self._theme_images = {}
        surface = _blend(frame_bg, "#ffffff", 0.78)
        surface_alt = _blend(surface, "#ffffff", 0.20)
        outline = _blend(frame_bg, BORDER, 0.80)
        panel_outline = _blend(frame_bg, "#2b3444", 0.82)
        subtle_outline = _blend(outline, "#ffffff", 0.18)
        accent_active = _blend(ACCENT, "#ffffff", 0.14)
        accent_pressed = _blend(ACCENT, "#000000", 0.12)
        disabled_fill = _blend(surface, frame_bg, 0.35)
        disabled_outline = _blend(outline, frame_bg, 0.35)
        slider_fill = _blend(ACCENT, "#ffffff", 0.05)

        button_normal = self._photo_asset("button_normal", 28, 28, UI_RADIUS + 2, ACCENT, outline=ACCENT)
        button_active = self._photo_asset("button_active", 28, 28, UI_RADIUS + 2, accent_active, outline=accent_active)
        button_pressed = self._photo_asset("button_pressed", 28, 28, UI_RADIUS + 2, accent_pressed, outline=accent_pressed)
        button_disabled = self._photo_asset("button_disabled", 28, 28, UI_RADIUS + 2, disabled_fill, outline=disabled_outline)
        field_normal = self._photo_asset("field_normal", 28, 28, UI_RADIUS + 2, "#ffffff", outline=outline)
        field_focus = self._photo_asset("field_focus", 28, 28, UI_RADIUS + 2, "#ffffff", outline=ACCENT)
        field_disabled = self._photo_asset("field_disabled", 28, 28, UI_RADIUS + 2, disabled_fill, outline=disabled_outline)
        tab_normal = self._photo_asset("tab_normal", 30, 24, UI_RADIUS + 2, surface, outline=subtle_outline)
        tab_selected = self._photo_asset("tab_selected", 30, 24, UI_RADIUS + 2, "#ffffff", outline=ACCENT)
        group_border = self._photo_asset("group_border", 28, 28, UI_RADIUS + 2, frame_bg, outline=panel_outline, outline_width=2)
        progress_trough = self._photo_asset("progress_trough", 28, 14, UI_RADIUS + 3, surface, outline=subtle_outline)
        progress_bar = self._photo_asset("progress_bar", 28, 14, UI_RADIUS + 3, ACCENT, outline=ACCENT)
        scale_trough = self._photo_asset("scale_trough", 28, 10, UI_RADIUS + 1, surface, outline=subtle_outline)
        scale_slider = self._photo_asset("scale_slider", 18, 18, 9, slider_fill, outline=ACCENT)

        self._create_image_element(
            style,
            "Rounded.Button.border",
            button_normal,
            ("disabled", button_disabled),
            ("pressed", button_pressed),
            ("active", button_active),
        )
        self._create_image_element(
            style,
            "Rounded.Entry.field",
            field_normal,
            ("disabled", field_disabled),
            ("focus", field_focus),
            ("invalid", field_focus),
        )
        self._create_image_element(
            style,
            "Rounded.Combobox.field",
            field_normal,
            ("readonly", field_normal),
            ("disabled", field_disabled),
            ("focus", field_focus),
        )
        self._create_image_element(
            style,
            "Rounded.Notebook.tab",
            tab_normal,
            ("selected", tab_selected),
            ("active", tab_selected),
        )
        self._create_image_element(style, "Rounded.Labelframe.border", group_border)
        self._create_image_element(style, "Rounded.Progressbar.trough", progress_trough, border=7)
        self._create_image_element(style, "Rounded.Progressbar.pbar", progress_bar, border=7)
        self._create_image_element(style, "Rounded.Scale.trough", scale_trough, border=5)
        self._create_image_element(
            style,
            "Rounded.Scale.slider",
            scale_slider,
            ("pressed", button_pressed),
            ("active", button_active),
            border=9,
        )

        self._replace_style_element(style, "TButton", "Button.border", "Rounded.Button.border")
        self._replace_style_element(style, "TEntry", "Entry.field", "Rounded.Entry.field")
        self._replace_style_element(style, "TCombobox", "Combobox.field", "Rounded.Combobox.field")
        self._replace_style_element(style, "TNotebook.Tab", "Notebook.tab", "Rounded.Notebook.tab")
        self._replace_style_element(style, "TLabelframe", "Labelframe.border", "Rounded.Labelframe.border")
        self._replace_style_element(
            style,
            "Horizontal.TProgressbar",
            "Horizontal.Progressbar.trough",
            "Rounded.Progressbar.trough",
        )
        self._replace_style_element(
            style,
            "Horizontal.TProgressbar",
            "Horizontal.Progressbar.pbar",
            "Rounded.Progressbar.pbar",
        )
        self._replace_style_element(style, "Horizontal.TScale", "Horizontal.Scale.trough", "Rounded.Scale.trough")
        self._replace_style_element(style, "Horizontal.TScale", "Horizontal.Scale.slider", "Rounded.Scale.slider")

        style.configure("TEntry", padding=(10, 6), fieldbackground="#ffffff", borderwidth=0, relief="flat")
        style.configure("TCombobox", padding=(10, 6), fieldbackground="#ffffff", borderwidth=0, relief="flat", arrowsize=12)
        style.configure("TNotebook.Tab", padding=(14, 8))
        style.configure("Horizontal.TProgressbar", thickness=14, borderwidth=0)
        style.configure("Horizontal.TScale", sliderthickness=18, troughcolor=surface)
        style.map("TNotebook.Tab", foreground=[("selected", label_fg), ("active", label_fg)])
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#ffffff"), ("focus", "#ffffff")],
            background=[("readonly", "#ffffff")],
        )

    def _configure_style(self):
        style = ttk.Style(self)
        style.theme_use(GUI_THEME)

        frame_bg = _resolve_color(self, style.lookup("TFrame", "background"), "#f3f6fb")
        label_fg = style.lookup("TLabel", "foreground") or TEXT
        ui_family = self.ui_font_family

        style.configure(".", font=ui_font(ui_family, 10), foreground=label_fg)
        style.configure("Page.TFrame", background=frame_bg)
        style.configure("Card.TFrame", background=frame_bg)
        style.configure("TLabel", background=frame_bg, foreground=label_fg)
        style.configure("App.TNotebook", background=frame_bg, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 6), font=ui_font(ui_family, 10, "bold"))
        style.configure("TLabelframe.Label", font=ui_font(ui_family, 10, "bold"))
        style.configure("Card.TLabelframe", background=frame_bg)
        style.configure("Card.TLabelframe.Label", background=frame_bg, foreground=label_fg, font=ui_font(ui_family, 10, "bold"))
        style.configure("Inset.TLabelframe", background=frame_bg)
        style.configure("Inset.TLabelframe.Label", background=frame_bg, foreground=label_fg, font=ui_font(ui_family, 10, "bold"))
        style.configure("TButton", font=ui_font(ui_family, 20, "bold"), padding=(12, 6), borderwidth=0, relief="flat")
        style.configure(
            "Action.TButton",
            font=ui_font(ui_family, 20, "bold"),
            padding=(12, 6),
            borderwidth=0,
            relief="flat",
        )

        return frame_bg


def main():
    try:
        app = CityGeneratorApp()
        app.mainloop()
    except Exception:
        message = traceback.format_exc()
        try:
            with open(STARTUP_ERROR_LOG, "w", encoding="utf-8") as fh:
                fh.write(message)
        except Exception:
            pass
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None,
                f"GUI startup failed.\n\nDetails were written to:\n{STARTUP_ERROR_LOG}",
                "Minecraft City Generator",
                0x10,
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
