"""Export the final city .schem into a copied, ready-to-play source world."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.algo import DEFAULT_SEED
from config.path import CITY_SCHEM, SAVES
from config.world import SAVE
from engine.world.writer import schem_to_world
from pipeline.stages import noop, run_stage_cli


def exported_world_name(seed):
    return f"CityGen World {seed}"


def run(*, seed=DEFAULT_SEED, out=None, logger=None, progress=None):
    logger = logger or noop

    schem = os.path.join(CITY_SCHEM, f"seed_{seed}.schem")
    if not os.path.exists(schem):
        raise FileNotFoundError(f"City schematic not found: {schem}. Run Stage 4 first.")
    world_name = exported_world_name(seed)
    out = out or os.path.join(SAVES, world_name)

    # Copy the source world and replace only the output overworld region files.
    logger(f"building world from source level.dat: {os.path.join(SAVE, 'level.dat')}")
    summary = schem_to_world(schem, out, source_world=SAVE, world_name=world_name, progress=progress)
    logger(
        f"seed={seed}: wrote world to {out} "
        f"({summary['chunks']} chunks, {summary['regions']} regions, "
        f"{summary['block_entities']} block entities)"
    )
    return {"output_path": out, **summary}


if __name__ == "__main__":
    run_stage_cli(run, "seed", "out")
