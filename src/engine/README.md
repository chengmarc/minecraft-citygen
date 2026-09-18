# engine — generation & transforms

The pure logic layer: road networks, building placement, schematic and world
I/O, and rendering. It has no GUI, no stage orchestration, and no side effects
beyond reading and writing the files it is handed. The
[pipeline](../pipeline/README.md) decides which files and settings; the engine
takes them as arguments.

← Back to the [source architecture overview](../README.md).

## How-to guides

### Change how roads are laid out

Edit `gen_networks` in [core/road_network.py](core/road_network.py). Keep the two
[overlap rules](#how-the-road-grid-is-generated) — every road tile's art assumes
them. If the change needs a new tuning value, add it as an `Algo` field
([config guide](../config/README.md#add-a-generation-knob)) and read it from the
`algo` argument. Check with:

```bash
python -m pytest -q tests/test_engine_core.py
python src/pipeline/stages.py preview --seed 5   # then open artifacts/03_preview/grid/seed_5.png
```

### Change building placement

Edit [core/city_layout.py](core/city_layout.py). `plan_city` is the one entry
point for both the Stage 3 preview and the Stage 4 build, so a change there
shows up in the preview exactly as it will be built. Draw new randomness from
`seeded_rng(seed, stream)` with its own stream constant rather than reusing an
existing stream: sharing one would shift every later draw and change existing
cities for the same seed. `validate_placements` and the type-2 tests in
`tests/test_engine_core.py` guard overlap, once-only landmarks, and spacing.

### Add a road tile shape

1. Add `(ports, "NN_<name>")` to `BIG_TILES`, `SMALL_TILES`, or `MIXED_TILES` in
   [core/road_network.py](core/road_network.py), with a new two-digit prefix.
   Ports are listed in the tile's unrotated orientation; the catalogue derives
   the rotations.
2. Author the matching road asset in the world, named with that prefix
   (conventions in the [pipeline guide](../pipeline/README.md#roads--fill-props)).
   [schematic/road.py](schematic/road.py) matches schematics to tiles by the
   prefix alone.

### Carry a new kind of block data through the pipeline

Block states (`name[prop=val]`) and block-entity NBT already travel unchanged
from extraction to export (see [Block entities](#block-entities)). If a block's
state has a direction the rotation doesn't turn yet, extend `rot_state` in
[schematic/transform.py](schematic/transform.py) and add a case to
`tests/test_schematic.py`.

## Explanation

### How the road grid is generated

[core/road_network.py](core/road_network.py) overlays two independent Manhattan
networks:

- a **big-road** network on the **coarse** grid, where one coarse cell covers a
  `2x2` block of fine cells — so big roads are 2 cells wide;
- a **small-road** network on the **fine** grid, the real cell grid buildings
  are placed on — so small roads are 1 cell wide.

Where a small road crosses a big corridor, the overlap is exactly two fine
cells, so that crossing uses a third, **mixed** `1x2` tile.

Big roads come first: avenue positions on the coarse grid are evenly stepped by
`gap_big` inside `pad_big`, jittered by `-1/0/+1`, and de-duplicated to keep the
spacing. Some full-span roads are then cut into T-intersections and L-corners
(`n_big_tees`, `n_big_corners`).

Small roads follow on the fine grid (`gap_small`, `pad_small`), filtered by
`gap_mixed` — the minimum clearance between a small street and a big corridor.
They get their own T's and L's, and their ends snap to another small road or to
a big corridor's edge.

Two rules hold by construction, and the tile art relies on them:

1. A small road never lies inside a big footprint except as a transverse mixed
   crossing.
2. A small road never runs collinear along a big corridor.

[schematic/road.py](schematic/road.py) turns the tile layout into blocks. Fill
props are kept out of the road tile set and loaded separately
(`load_fillers`).

### How building placement works

[core/city_layout.py](core/city_layout.py):

- Road cells are forbidden; `find_lots` flood-fills the rest into lots.
- `load_catalog` reads the `buildings.json` entries, drops banned IDs, and
  sorts buildings by physical size (`width * depth`), then area, dimensions, and
  ID.
- **Pass 1: type-2 landmarks.** Only big-road frontage, longest uninterrupted
  runs first. Each landmark is tried once, largest first, and takes the first
  fitting position at least `landmark_spacing` from other landmarks. So each
  landmark ID appears at most once per city.
- **Pass 2: type-1 buildings.** Ordinary road frontage on every lot. At each
  frontage point the first `type1_top_fit_choices` fitting buildings are
  collected and one is picked at random — variety without giving up fit. No
  repeat limit.

Everything is deterministic for a seed: placement, stack heights, and filler
props each draw from their own `seeded_rng` stream.

### Schematic I/O

[schematic/writer.py](schematic/writer.py) and
[schematic/reader.py](schematic/reader.py) handle the Sponge `.schem` container.
Every output stamp is at or above the 26.1.2 floor, which is inside the Sponge v3
range, so **both are v3-only**. Why the floor exists is in the
[config guide](../config/README.md#version-compatibility).

### Block entities

Signs, banners, chests, beds, skulls, etc. keep their state in *block-entity
NBT*, separate from the block id. The engine carries it end to end without
interpreting it, so downstream tooling can preserve or upgrade it normally:

- `marker_extract.extract_cuboid` returns `(cells, block_entities)`. Each
  `BlockEntity` ([schematic/transform.py](schematic/transform.py)) holds a local
  `(x, y, z)`, the id, and the `Data` compound copied verbatim. Authoring markers
  sit outside the extracted cuboid, so signs inside it are real content.
- The writer emits them into the v3 `BlockEntities` list;
  `reader.decode_schem_block_entities` reads them back.
- Positions travel with their blocks: `rot_tile` moves each block entity to its
  cell's rotated coordinate (and `rot_state` turns the block's own
  `facing`/`rotation`), `building.assemble` offsets stacked pieces, and
  [schematic/city.py](schematic/city.py) translates them to city coordinates,
  clipping to bounds and keeping one per cell.

### One ground plane

[schematic/city.py](schematic/city.py) seats every road, building, and fill tile
against one shared ground height. Each asset's bottom row goes at
`ground_y - ground_offset`, where `ground_offset` is the height of the asset's
emerald marker. That is why extraction rejects an asset without an emerald:
there would be no way to line its floor up with its neighbours'.

## Reference

| Subpackage | Modules | Responsibility |
|---|---|---|
| `core/` | [road_network.py](core/road_network.py), [city_layout.py](core/city_layout.py) | Road networks and the tile catalogue; lots and building placement (`plan_city`) |
| `schematic/` | [transform.py](schematic/transform.py), [reader.py](schematic/reader.py), [writer.py](schematic/writer.py), [grid.py](schematic/grid.py), [road.py](schematic/road.py), [building.py](schematic/building.py), [city.py](schematic/city.py) | Sponge `.schem` I/O, tile rotation, stamping into palette-indexed voxel grids, road assembly, the building catalog and its pieces, the final city grid |
| `world/` | [anvil_world_reader.py](world/anvil_world_reader.py), [marker_extract.py](world/marker_extract.py), [writer.py](world/writer.py) | Read Anvil worlds, extract marker-defined cuboids, write exported worlds |
| `render/` | [isometric.py](render/isometric.py), [road_layout.py](render/road_layout.py), [contact_sheet.py](render/contact_sheet.py), [topdown.py](render/topdown.py), [palette.py](render/palette.py), [fonts.py](render/fonts.py) | Isometric `.schem` renders, the Stage 3 road-layout image, contact sheets, the top-down world preview for the GUI region dialog |
| (top level) | [blocks.py](blocks.py) | Block-state strings: `name[prop=val]` parsing/formatting and the air check |

Road assets are matched by the first two characters of their schematic name:

| Prefix | Meaning | Source of truth |
|---|---|---|
| `01`–`05` | big `2x2` tiles | `BIG_TILES` in [core/road_network.py](core/road_network.py) |
| `06`–`10` | small `1x1` tiles | `SMALL_TILES` |
| `11`–`14` | mixed `1x2` crossings | `MIXED_TILES` |
| `18` | empty-lot ground fill (required) | `GROUND_FILL_PREFIX` in [schematic/road.py](schematic/road.py) |
| any other, name contains `fill` | 9x9 fill props | `FILL_TOKEN` in [schematic/road.py](schematic/road.py) |

Layers inside `engine` import only downward: `blocks`, `core` → `schematic` →
`world` → `render` (enforced by `tests/test_dependencies.py`).
