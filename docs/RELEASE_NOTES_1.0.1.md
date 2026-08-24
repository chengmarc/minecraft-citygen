# CityGen 1.0.1 Release Notes

Released on August 24, 2026.

CityGen 1.0.1 is a follow-up patch for the road-region empty-space fill change.
It wires the new authored asset `18` into the bundled default world, corrects
how that asset is applied in production outputs, and keeps the simulation
preview intentionally lightweight.

## Highlights

- **Bundled fill asset in the default world.** The default source world now
  includes the road-region asset `18` required by the new production ground-fill
  path.
- **Correct production lot filling.** Asset `18` now fills empty lot columns
  the way the old flat fill did, while still respecting marker-authored
  `ground_offset` metadata.
- **No prop/fill collisions.** Self-contained fill props (`15` / `16` / `17`)
  keep exclusive ownership of the lot cells they occupy.
- **Preview kept simple.** The city simulation preview goes back to the old flat
  gray fill instead of trying to render the production-only asset pattern.

## What Changed

### Default world content

- Added the authored road-region asset `18` to the bundled default world so the
  shipped asset kit matches the production ground-fill logic.

### Production city assembly

- `pipeline/04_city/construct.py` now treats asset `18` as a repeated fill
  pattern across empty block columns inside a lot cell, rather than as a
  one-time tile paste.
- The asset seats through the shared marker-asset alignment path:
  `_seat_y(ground_y, ground_offset)`.
- Ground fill now skips whole lot cells that already received a self-contained
  `15` / `16` / `17` filler prop.

### GUI and preview behavior

- The Extraction tab now preserves contact-sheet target paths when resetting the
  viewer placeholder, so the road/build asset sheets reload after a successful
  extraction run.
- The city simulation preview no longer samples asset `18`; it returns to the
  flat gray lot fill.

## Upgrade Notes

- If you use the bundled default world, update to the 1.0.1 build before
  re-running extraction or final generation so asset `18` is present in the
  shipped road region.
- If you use a custom source world, author the road-region asset `18` there as
  well; the production fill path depends on that marker-authored asset being
  available.

## Verification

- `python -m pytest tests\\test_gui.py`
- `python -m pytest tests\\test_pipeline.py -k "city_ground_fill_"`
- `python src/pipeline/04_city/construct.py --seed 4`
- `python src/pipeline/05_world/world.py --seed 4`
