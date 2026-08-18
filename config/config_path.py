"""Repository path constants for the city-generation pipelines."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "engine")
PIPELINE = os.path.join(ROOT, "pipeline")
ARTIFACTS = os.path.join(ROOT, "artifacts")


def _artifact_dir(*parts):
    return os.path.join(ARTIFACTS, *parts)


ROADS_SIM = _artifact_dir("roads", "simulation")
ROADS_PROD = _artifact_dir("roads", "production")
ROADS_PROD_SCHEM = ROADS_PROD

GRID_SIM = _artifact_dir("grid", "simulation")
GRID_PROD = _artifact_dir("grid", "production")
GRID_PROD_SCHEM = GRID_PROD

BUILDS_SIM = _artifact_dir("builds", "simulation")
BUILDS_PROD = _artifact_dir("builds", "production")
BUILDS_PROD_SCHEM = BUILDS_PROD
BUILD_CATALOG = os.path.join(BUILDS_PROD, "buildings.json")

CITY_SIM = _artifact_dir("city", "simulation")
CITY_PROD = _artifact_dir("city", "production")
CITY_PROD_SCHEM = CITY_PROD

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
