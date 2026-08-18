"""Clear generated artifacts and Python cache directories."""

from __future__ import annotations

import glob
import os
import shutil
from pathlib import Path

from config.config_path import (
    BUILD_CATALOG,
    BUILDS_PROD,
    BUILDS_PROD_SCHEM,
    BUILDS_SIM,
    CITY_PROD,
    CITY_PROD_SCHEM,
    CITY_SIM,
    GRID_PROD,
    GRID_PROD_SCHEM,
    GRID_SIM,
    ROADS_SIM,
    ROOT,
    ROADS_PROD,
    ROADS_PROD_SCHEM,
    WORLDEDIT_SCHEM,
)


REPO_ROOT = Path(ROOT).resolve()

REPO_GLOBS = [
    os.path.join(ROADS_SIM, "*.png"),
    os.path.join(ROADS_PROD, "*.png"),
    os.path.join(ROADS_PROD_SCHEM, "*.schem"),
    os.path.join(BUILDS_SIM, "*.png"),
    os.path.join(BUILDS_PROD, "*.png"),
    os.path.join(BUILDS_PROD_SCHEM, "*.schem"),
    BUILD_CATALOG,
    os.path.join(GRID_SIM, "seed_*_preview.png"),
    os.path.join(GRID_PROD, "*_render.png"),
    os.path.join(GRID_PROD_SCHEM, "seed_*.schem"),
    os.path.join(CITY_SIM, "seed_*.png"),
    os.path.join(CITY_PROD, "seed_*.png"),
    os.path.join(CITY_PROD_SCHEM, "seed_*.schem"),
]

LEGACY_REPO_GLOBS = [
    os.path.join(ROOT, "pipeline", "01_roads_simulation", "*.png"),
    os.path.join(ROOT, "pipeline", "01_roads_production", "*.png"),
    os.path.join(ROOT, "pipeline", "01_roads_production", "schematics", "*.schem"),
    os.path.join(ROOT, "pipeline", "02_builds_simulation", "*.png"),
    os.path.join(ROOT, "pipeline", "02_builds_production", "*.png"),
    os.path.join(ROOT, "pipeline", "02_builds_production", "schematics", "*.schem"),
    os.path.join(ROOT, "pipeline", "02_builds_production", "schematics", "buildings.json"),
    os.path.join(ROOT, "pipeline", "03_grid_simulation", "seed_*_preview.png"),
    os.path.join(ROOT, "pipeline", "03_grid_production", "*_render.png"),
    os.path.join(ROOT, "pipeline", "03_grid_production", "schematics", "seed_*.schem"),
    os.path.join(ROOT, "pipeline", "04_city_simulation", "seed_*.png"),
    os.path.join(ROOT, "pipeline", "04_city_production", "seed_*.png"),
    os.path.join(ROOT, "pipeline", "04_city_production", "schematics", "seed_*.schem"),
]

EXTERNAL_GLOBS = [
    os.path.join(WORLDEDIT_SCHEM, "seed_*_city.schem"),
]


def _remove_matches(pattern: str, removed: list[str]) -> None:
    for path in glob.glob(pattern):
        if os.path.isfile(path):
            os.remove(path)
            removed.append(path)


def purge_artifacts(verbose: bool = False) -> list[str]:
    removed: list[str] = []
    repo_root = os.path.normcase(str(REPO_ROOT))

    for pattern in [*REPO_GLOBS, *LEGACY_REPO_GLOBS]:
        abs_pattern = os.path.abspath(pattern)
        pattern_dir = os.path.normcase(os.path.abspath(os.path.dirname(abs_pattern)))
        if not pattern_dir.startswith(repo_root):
            raise RuntimeError(f"Refusing to purge outside repo: {pattern}")
        _remove_matches(abs_pattern, removed)

    for pattern in EXTERNAL_GLOBS:
        _remove_matches(os.path.abspath(pattern), removed)

    if verbose:
        for path in removed:
            print(f"removed {path}")
        print(f"purged {len(removed)} artifact(s)")
    return removed


def clear_pycache(verbose: bool = False) -> list[Path]:
    removed: list[Path] = []
    for path in sorted(REPO_ROOT.rglob("__pycache__"), key=lambda p: len(p.parts), reverse=True):
        resolved = path.resolve()
        if REPO_ROOT not in (resolved, *resolved.parents):
            raise RuntimeError(f"refusing to remove outside repo: {resolved}")
        shutil.rmtree(resolved)
        removed.append(resolved)

    if verbose:
        for path in removed:
            print(f"removed {path}")
        print(f"removed {len(removed)} __pycache__ director{'y' if len(removed) == 1 else 'ies'}")
    return removed


def clear_cache(verbose: bool = False) -> None:
    purge_artifacts(verbose=verbose)
    clear_pycache(verbose=verbose)


def main() -> None:
    clear_cache(verbose=True)


if __name__ == "__main__":
    main()
