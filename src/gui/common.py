"""Shared GUI constants and non-widget helpers."""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont

from config import config_algo
from config.config_algo import DEFAULT_SEED
from config.config_path import GUI, ROOT
from config.models import BlockRegion, BuildRegion
from config.config_path import BUILDS_PROD, CITY_PROD, CITY_PROD_SCHEM, CITY_SIM, GRID_SIM, ROADS_PROD

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageTk = None

ROOT_DIR = ROOT
ICON_DIR = os.path.join(GUI, "icons")
APP_ICON_PATH = os.path.join(ICON_DIR, "app-icon.png")
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
BUTTON_WIDTH = 8
GUI_THEME = "vista"
APP_WIDTH = 1024
APP_HEIGHT = 768
UI_RADIUS = 4
STARTUP_ERROR_LOG = os.path.join(ROOT_DIR, "application_startup_error.log")
UI_FONT_FAMILY = "SF Pro Text"
UI_FONT_FALLBACKS = ("Segoe UI Variable", "Segoe UI", "Inter", "Arial")

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
PREVIEW_CONFIG_LOOKUP = {name: (label, description) for name, label, description in PREVIEW_CONFIGS}

PREVIEW_CONFIG_GROUPS = [
    ("Spacing & Padding", ["GAP_BIG", "PAD_BIG", "GAP_SMALL", "PAD_SMALL"]),
    ("Corners & Tees", ["N_BIG_CORNERS", "N_BIG_TEES", "N_SMALL_CORNERS", "N_SMALL_TEES"]),
    ("Building Placement", ["BANNED_BUILDINGS", "TYPE1_TOP_FIT_CHOICES", "TYPE2_TOP_FIT_CHOICES", "TYPE2_SAME_COARSE_SPAN"]),
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
    ("pipeline.01_roads_simulation", 15),
    ("pipeline.02_builds_simulation", 20),
    ("pipeline.03_grid_simulation", 30),
    ("pipeline.04_city_simulation", 35),
]
RENDER_PROGRESS_WEIGHTS = [
    ("pipeline.04_city_construct", 60),
    ("pipeline.04_city_render", 40),
]

SCRIPT_PROGRESS_HEADROOM = 0.88
SCRIPT_PROGRESS_TICK_MS = 120
_ICON_CACHE = {}
_ICON_COLOR_CACHE = {}


def resolve_color(widget, color, fallback):
    try:
        source = color or fallback
        r, g, b = widget.winfo_rgb(source)
        return f"#{r // 256:02x}{g // 256:02x}{b // 256:02x}"
    except Exception:
        return fallback


def blend(hex_a, hex_b, ratio):
    ratio = max(0.0, min(1.0, float(ratio)))
    a = tuple(int(hex_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(hex_b[i:i + 2], 16) for i in (1, 3, 5))
    mixed = tuple(round(av + (bv - av) * ratio) for av, bv in zip(a, b))
    return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"


def rounded_image(width, height, radius, fill, outline=None, outline_width=1):
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


def replace_layout_element(layout, source, target):
    replaced = []
    for name, options in layout:
        new_options = dict(options)
        children = new_options.get("children")
        if children:
            new_options["children"] = replace_layout_element(children, source, target)
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


def load_icon(name, size=16):
    cache_key = (name, int(size))
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]
    if Image is None or ImageTk is None:
        return None

    icon_path = os.path.join(ICON_DIR, f"{name}.png")
    if not os.path.exists(icon_path):
        return None

    try:
        image = Image.open(icon_path).convert("RGBA")
        image = image.resize((int(size), int(size)), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image)
    except Exception:
        return None

    _ICON_CACHE[cache_key] = photo
    return photo


def icon_text_color(name):
    if name in _ICON_COLOR_CACHE:
        return _ICON_COLOR_CACHE[name]
    if Image is None:
        return TEXT

    icon_path = os.path.join(ICON_DIR, f"{name}.png")
    if not os.path.exists(icon_path):
        return TEXT

    try:
        image = Image.open(icon_path).convert("RGBA")
        samples = [
            (r, g, b, a)
            for (r, g, b, a) in image.getdata()
            if a > 0
        ]
        if not samples:
            return TEXT
        total_alpha = sum(a for _r, _g, _b, a in samples)
        red = round(sum(r * a for r, _g, _b, a in samples) / total_alpha)
        green = round(sum(g * a for _r, g, _b, a in samples) / total_alpha)
        blue = round(sum(b * a for _r, _g, b, a in samples) / total_alpha)
        color = f"#{red:02x}{green:02x}{blue:02x}"
    except Exception:
        return TEXT

    _ICON_COLOR_CACHE[name] = color
    return color


def grid_preview_path(seed):
    return os.path.join(GRID_SIM, f"seed_{seed}_preview.png")


def city_preview_path(seed):
    return os.path.join(CITY_SIM, f"seed_{seed}.png")


def city_render_path(seed):
    return os.path.join(CITY_PROD, f"seed_{seed}.png")


def format_box(box):
    if isinstance(box, BlockRegion):
        box = box.as_tuple()
    elif isinstance(box, BuildRegion):
        box = box.as_tuple()
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
    if isinstance(region, BuildRegion):
        return region.bounds.as_xyz_pair()
    if isinstance(region, BlockRegion):
        return region.as_xyz_pair()
    if len(region) == 6:
        return BlockRegion.from_values(region).as_xyz_pair()
    return BuildRegion.from_values(region).bounds.as_xyz_pair()


def first_build_region(build_types, build_type):
    for region in build_types:
        region_type = region.build_type if isinstance(region, BuildRegion) else region[0]
        if region_type == build_type:
            return region
    return BuildRegion(build_type, BlockRegion(0, 0, 0, 0, 64, 64))


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


def open_in_file_manager(path):
    target = os.path.abspath(path)
    if sys.platform.startswith("win"):
        os.startfile(target)
        return
    command = ["open", target] if sys.platform == "darwin" else ["xdg-open", target]
    subprocess.Popen(command)
