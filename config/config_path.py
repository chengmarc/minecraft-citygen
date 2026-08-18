"""Repository path constants for the city-generation pipelines."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "engine")
PIPELINE = os.path.join(ROOT, "pipeline")

ROADS_SIM = os.path.join(PIPELINE, "01_roads_simulation")
ROADS_PROD = os.path.join(PIPELINE, "01_roads_production")
ROADS_PROD_SCHEM = os.path.join(ROADS_PROD, "schematics")

GRID_SIM = os.path.join(PIPELINE, "03_grid_simulation")
GRID_PROD = os.path.join(PIPELINE, "03_grid_production")
GRID_PROD_SCHEM = os.path.join(GRID_PROD, "schematics")

BUILDS_SIM = os.path.join(PIPELINE, "02_builds_simulation")
BUILDS_PROD = os.path.join(PIPELINE, "02_builds_production")
BUILDS_PROD_SCHEM = os.path.join(BUILDS_PROD, "schematics")
BUILD_CATALOG = os.path.join(BUILDS_PROD_SCHEM, "buildings.json")

CITY_SIM = os.path.join(PIPELINE, "04_city_simulation")
CITY_PROD = os.path.join(PIPELINE, "04_city_production")
CITY_PROD_SCHEM = os.path.join(CITY_PROD, "schematics")

APPDATA = os.environ.get("APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming"))
WORLDEDIT_SCHEM = os.path.join(
    APPDATA,
    "PrismLauncher",
    "instances",
    "Keo optimized",
    "minecraft",
    "config",
    "worldedit",
    "schematics",
)

COLOR_RENDER_CSV = os.path.join(ENGINE, "color_render.csv")
