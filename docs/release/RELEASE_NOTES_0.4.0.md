# CityGen 0.4.0 Release Notes

Released on August 21, 2026.

This release fills the empty space in a generated city. The gaps between roads and
buildings are now populated with **fill props** — self-contained one-cell assets
that carry their own ground — and the bundled world ships three of them as trees.
Along the way, road extraction was unified with the building marker convention, so
there is no longer any road-specific detection logic.

## Highlights

- Empty lot cells are filled with a randomly chosen, randomly rotated **fill
  prop**. The bundled world ships three trees (spruce, birch, oak), so open ground
  reads as landscaped space instead of a flat plate.
- **Road extraction now shares the building marker convention.** Road tiles and
  fill props are authored exactly like a type-1 build (wool boundary +
  gold/diamond/emerald markers + a name sign) and run through the same extraction.
- The top-down **simulation preview** places matching tree tiles in the same
  cells with the same seed, so the preview lines up with the built city.

## What Changed

### Fill props (empty-space filling)

- A new asset class — **fill props** — is authored in the road region alongside
  the road tiles (`15_fill_1x1_A`, `16_fill_1x1_B`, `17_fill_1x1_C`). Each is a
  self-contained 9x9 (one fine cell) asset that carries its own ground.
- `pipeline/04_city_construct.py` drops a random, randomly rotated prop into every
  fully-empty non-road lot cell, seated on the lot ground plane. Cells occupied by
  a building are skipped, and prop cells are excluded from the flat ground fill so
  nothing pokes up through a prop's own ground.
- `pipeline/01_roads_simulation.py` draws top-down tile PNGs for the props, and
  `pipeline/04_city_simulation.py` scatters them into the preview with the same
  seed used by the build.

### Shared marker extraction

- `engine/marker_extract.py` is a new module holding the wool-boundary +
  gold/diamond/emerald cuboid extraction. Both `02_builds_extract` and
  `01_roads_extract` now call into it.
- The old road detector (top-down surface components, `yellow_wool`/`white_wool`
  edge trimming, per-column Y-extent) is removed. Author road tiles the same way
  you author a type-1 build.

### Ground fill

- The default empty-lot ground fill block changed from `minecraft:smooth_stone`
  to `minecraft:smooth_stone_slab[type=bottom]`. The origin anchor column keeps a
  solid block.

## Fixes

- Tall road and fill assets are no longer clipped to the `ROAD_BOX` Y span: the
  marker cuboid (gold→diamond) is captured in full, regardless of the box height.
- Fill props seat flush with the lot surface instead of hovering one block above
  it, and the flat ground fill no longer leaks a block into a prop's cell.

## Upgrade notes

- **Custom road worlds must be re-authored.** Road extraction no longer keys off
  `yellow_wool`/`white_wool` surface markers. Each road tile now needs a wool
  boundary, a gold/diamond marker pair (opposite corners), a single emerald at
  ground level, and a name sign — the same convention as buildings. The bundled
  default world has already been updated.
- Regenerate roads, then the city, to pick up the new fill props and slab ground:
  re-run the road extraction, grid, and city stages.

## Verification

- `python -m pytest`
- `python packaging/build_windows_release.py --clean`
- Generate a city and confirm the empty lots are filled with randomly rotated
  trees seated flush with the ground, and that the top-down preview matches.
