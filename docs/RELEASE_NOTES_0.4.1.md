# CityGen 0.4.1 Release Notes

Released on August 20, 2026.

This is a patch release for the extracted-asset ground offset refactor. Building
placement already read the authored `ground_offset`; this release extends that
same offset path to roads and fill props so every marker-authored asset seats
from extracted metadata instead of assuming a hard-coded flush origin.

## Highlights

- **Roads and trees now seat from extracted asset metadata.** The city
  constructor no longer treats them as implicitly flush assets with a baked-in
  `0` Y offset.
- **Road/fill schematics now persist their authored ground offset.** The
  extraction stage writes the asset ground seat into the Sponge `Offset` field,
  and the loader preserves it through rotation and composition.

## What Changed

### Unified offset plumbing

- `pipeline/01_roads_extract.py` now writes each extracted road or fill asset's
  ground offset into the schematic `Offset` field.
- `engine/schematic_reader.py` now reads the Sponge `Offset` field, and
  `engine/road_schematic.py` attaches that value to loaded tiles as
  `ground_offset`.
- `engine/schematic_transform.py` now preserves `ground_offset` when rotating a
  tile, so randomized fill-prop rotation does not lose the authored seat.

### City construction

- `pipeline/04_city_construct.py` now seats the road grid from the shared road
  offset returned by the road schematic builder.
- Fill props are now seated from each tile's extracted `ground_offset` instead
  of from a hard-coded flush assumption.
- `pipeline/03_grid_construct.py` now preserves the road-grid offset when
  exporting the combined grid schematic.

## Upgrade notes

- **Re-extract road assets before rebuilding outputs.** Existing road and fill
  schematics exported before 0.4.1 do not carry the new offset metadata, so
  they will still read as zero-offset assets until regenerated.
- After re-extraction, re-run the grid and city construction stages to pick up
  the corrected seating.

## Verification

- `python -m compileall src/engine/schematic_reader.py src/engine/schematic_transform.py src/engine/road_schematic.py src/pipeline/01_roads_extract.py src/pipeline/03_grid_construct.py src/pipeline/04_city_construct.py`
- `python src/pipeline/03_grid_construct.py --seed 1 --fine 8 --out .codex/grid_offset_smoke.schem`
- `python src/pipeline/04_city_construct.py --seed 1 --fine 8 --out .codex/city_offset_smoke.schem`
