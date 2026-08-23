"""Export the final city .schem as a standalone, ready-to-play void world."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.algo import DEFAULT_SEED
from config.path import CITY_PROD, SAVES
from config.world import SAVE
from engine.world.writer import schem_to_world
from pipeline.stages import noop, run_stage_cli


def run(*, seed=DEFAULT_SEED, out=None, logger=None, progress=None):
    logger = logger or noop

    schem = os.path.join(CITY_PROD, f"seed_{seed}.schem")
    if not os.path.exists(schem):
        raise FileNotFoundError(f"City schematic not found: {schem}. Run city construct first.")
    out = out or os.path.join(SAVES, f"seed_{seed}_world")

    # Clone the source world's level.dat so the export is native to its version.
    summary = schem_to_world(schem, out, base_world=SAVE, progress=progress)
    logger(
        f"seed={seed}: wrote world to {out} "
        f"({summary['chunks']} chunks, {summary['regions']} regions, "
        f"{summary['block_entities']} block entities)"
    )
    return {"output_path": out, **summary}


if __name__ == "__main__":
    run_stage_cli(run, "seed", "out")
