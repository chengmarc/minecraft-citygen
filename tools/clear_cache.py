"""Clear generated artifacts, build outputs, and Python cache directories.

Run from anywhere: ``python tools/clear_cache.py``. Everything removed lives
inside the repository and is regenerated on the next run/build, so this is safe
to invoke at any time.
"""

from __future__ import annotations

import glob
import os
import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config.config_path import (
    BUILD_CATALOG,
    BUILDS_PROD,
    BUILDS_SIM,
    CITY_PROD,
    CITY_SIM,
    GRID_PROD,
    GRID_SIM,
    ROADS_PROD,
    ROADS_SIM,
    ROOT,
)

REPO_ROOT = Path(ROOT).resolve()

# Generated pipeline artifacts (previews, renders, schematics, catalog).
ARTIFACT_GLOBS = [
    os.path.join(ROADS_SIM, "*.png"),
    os.path.join(ROADS_PROD, "*.png"),
    os.path.join(ROADS_PROD, "*.schem"),
    os.path.join(BUILDS_SIM, "*.png"),
    os.path.join(BUILDS_PROD, "*.png"),
    os.path.join(BUILDS_PROD, "*.schem"),
    BUILD_CATALOG,
    os.path.join(GRID_SIM, "seed_*_preview.png"),
    os.path.join(GRID_PROD, "*_render.png"),
    os.path.join(GRID_PROD, "seed_*.schem"),
    os.path.join(CITY_SIM, "seed_*.png"),
    os.path.join(CITY_PROD, "seed_*.png"),
    os.path.join(CITY_PROD, "seed_*.schem"),
]

# Build / packaging / test outputs that regenerate on the next build or test run.
BUILD_OUTPUT_DIRS = [
    REPO_ROOT / "build",
    REPO_ROOT / "dist",
    REPO_ROOT / ".pytest_cache",
]
BUILD_OUTPUT_FILE_GLOBS = [
    str(REPO_ROOT / "src" / "*.egg-info"),
    str(REPO_ROOT / "application_startup_error.log"),
]


def _within_repo(path: Path) -> bool:
    return REPO_ROOT in (path, *path.parents)


def _remove_matches(pattern: str, removed: list[str]) -> None:
    for path in glob.glob(pattern):
        if os.path.isfile(path):
            os.remove(path)
            removed.append(path)


def purge_artifacts(verbose: bool = False) -> list[str]:
    removed: list[str] = []
    repo_root = os.path.normcase(str(REPO_ROOT))
    for pattern in ARTIFACT_GLOBS:
        abs_pattern = os.path.abspath(pattern)
        pattern_dir = os.path.normcase(os.path.abspath(os.path.dirname(abs_pattern)))
        if not pattern_dir.startswith(repo_root):
            raise RuntimeError(f"Refusing to purge outside repo: {pattern}")
        _remove_matches(abs_pattern, removed)

    if verbose:
        for path in removed:
            print(f"removed {path}")
        print(f"purged {len(removed)} artifact(s)")
    return removed


def clear_build_outputs(verbose: bool = False) -> list[Path]:
    removed: list[Path] = []
    for directory in BUILD_OUTPUT_DIRS:
        resolved = directory.resolve()
        if not _within_repo(resolved):
            raise RuntimeError(f"refusing to remove outside repo: {resolved}")
        if resolved.is_dir():
            shutil.rmtree(resolved)
            removed.append(resolved)
    for pattern in BUILD_OUTPUT_FILE_GLOBS:
        for match in glob.glob(pattern):
            path = Path(match).resolve()
            if not _within_repo(path):
                raise RuntimeError(f"refusing to remove outside repo: {path}")
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed.append(path)

    if verbose:
        for path in removed:
            print(f"removed {path}")
        print(f"removed {len(removed)} build output(s)")
    return removed


def clear_pycache(verbose: bool = False) -> list[Path]:
    removed: list[Path] = []
    for path in sorted(REPO_ROOT.rglob("__pycache__"), key=lambda p: len(p.parts), reverse=True):
        resolved = path.resolve()
        if not _within_repo(resolved):
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
    clear_build_outputs(verbose=verbose)
    clear_pycache(verbose=verbose)


def main() -> None:
    clear_cache(verbose=True)


if __name__ == "__main__":
    main()
