# engine — generation & transforms

The engine is CityGen's pure logic layer: no GUI, no stage orchestration, no
side effects beyond reading/writing schematic and image files it is handed. The
[pipeline](../pipeline/README.md) stages import these modules and drive them.

← Back to the [source architecture overview](../README.md).

## Subpackages

| Subpackage | Modules | Responsibility |
|---|---|---|
| `core/` | [road_network.py](core/road_network.py), [city_layout.py](core/city_layout.py) | Road-network generation & tile compositing; lot finding & building placement |
| `world/` | [anvil_world_reader.py](world/anvil_world_reader.py), [marker_extract.py](world/marker_extract.py) | Read Anvil worlds; the shared marker-based extraction geometry pass |
| `schematic/` | [transform.py](schematic/transform.py), [reader.py](schematic/reader.py), [writer.py](schematic/writer.py), [road.py](schematic/road.py), [building.py](schematic/building.py) | Sponge `.schem` I/O, tile transforms, road/building assembly |
| `render/` | [isometric.py](render/isometric.py), [topdown.py](render/topdown.py), [palette.py](render/palette.py) | Isometric and top-down PNG rendering |

## How the road grid is generated

Road generation lives in [core/road_network.py](core/road_network.py). It uses an
overlay model with two independent Manhattan networks:

- a **big-road** network on the coarse grid
- a **small-road** network on the fine grid

**Fine grid vs coarse grid.** The fine grid is the real city cell grid used for
building placement; the coarse grid is `fine // 2`, so one coarse cell covers a
`2x2` block of fine cells. That is why big roads are effectively 2 cells wide and
small roads 1 cell wide.

**Three road layers** are composited: big `2x2`, small `1x1`, and mixed `1x2`.
Mixed pieces exist because a small road can cross a big corridor transversely; the
overlap occupies exactly two fine cells, so the mixed art is `1x2`.

**Big roads are generated first:** avenue positions are chosen on the coarse grid,
spaced by `GAP_BIG` with `PAD_BIG` edge padding, evenly stepped then jittered by
`-1/0/+1`, with nearby duplicates collapsed to preserve minimum spacing. Some
full-span roads are truncated into T-intersections and some pairs into L-corners
(`N_BIG_TEES`, `N_BIG_CORNERS`).

**Small roads come next:** streets on the fine grid, spaced by `GAP_SMALL` with
`PAD_SMALL` padding, filtered so they don't sit too close to big-road bands. The
critical clearance rule is `GAP_MIXED` — the minimum fine-cell clearance between a
small street and a big corridor band. Small roads also receive forced L-corners
and T-intersections (`N_SMALL_CORNERS`, `N_SMALL_TEES`), and their endpoints snap
either to another small road or to the edge of a big corridor.

**Overlap rules** keep compositing predictable: a small road never lives inside a
big-road footprint except as a transverse mixed crossing, and never runs
collinear along a big corridor.

[schematic/road.py](schematic/road.py) maps the generated tile layout to extracted
road `.schem` pieces for production, and keeps fill props out of the road tile set
(exposing them via `load_fillers()` instead).

## How building placement works

Placement lives in [core/city_layout.py](core/city_layout.py). It is deterministic
for a given seed:

- roads define forbidden cells; all remaining fine cells are lots
- buildings snap to the 9-block fine-cell grid
- type-2 buildings are placed first; type-1 fill the remaining frontage

**Lot detection.** `find_lots()` flood-fills all non-road fine cells into
connected lots, each processed for frontage placement.

**Catalog loading** reads `buildings.json`, filters banned IDs, computes footprint
size in fine cells, and sorts buildings descending by physical score
(`width * depth`), area, footprint dimensions, then ID.

**Two-pass placement** (`place_city()`):

- *Pass 1* — type-2 buildings, using only big-road frontage, processing the
  longest uninterrupted frontage runs first.
- *Pass 2* — type-1 buildings, using ordinary road adjacency on each lot.

**Candidate selection.** At each frontage point, buildings are checked in sorted
order, the first N fitting candidates collected, and one chosen randomly from that
top-fit set (`TYPE1_TOP_FIT_CHOICES`, `TYPE2_TOP_FIT_CHOICES`) — variation without
abandoning fit quality.

**Repetition & appearance (type-2 only).** Each type-2 building can define an
`appearance` range; a target count is sampled per city and, once reached, that
building stops being placed. Type-2 buildings also cannot repeat within the same
coarse-cell window (`TYPE2_SAME_COARSE_SPAN`). Banned IDs (`BANNED_BUILDINGS`) are
filtered before placement.

## Schematic I/O

[schematic/writer.py](schematic/writer.py) and
[schematic/reader.py](schematic/reader.py) handle the Sponge `.schem` container.
Because the hard floor is Minecraft 1.20, every output stamp lands in the v3
window, so **both are v3-only**: the writer always emits the v3 container and the
reader assumes the v3 layout. Versioning rationale lives in the
[config guide](../config/README.md#version-compatibility).

### Block entities

Signs, banners, chests, barrels, beds, furnaces, skulls, etc. carry their state in
*block-entity NBT*, separate from the block id. The pipeline preserves that NBT
end to end:

- `marker_extract.extract_cuboid` returns `(cells, block_entities)`; each
  `BlockEntity` ([schematic/transform.py](schematic/transform.py)) holds a local
  `(x, y, z)`, the id, and a `Data` compound copied verbatim. Authoring markers
  live outside the extracted cuboid, so in-cuboid signs stay as real content.
- `writer.py` emits them into the Sponge v3 `BlockEntities` list, nested under
  `Data`; `reader.decode_schem_block_entities` reads them back.
- Positions ride along with their blocks through assembly: `rot_tile` rotates a
  block entity to its cell's new coordinate (and `rot_state` turns the block's own
  `facing`/`rotation`), `building.assemble` offsets stacked pieces, and
  `04_city.construct` translates each into master-grid coordinates, clipping to
  bounds and collapsing duplicates (one per cell).

The NBT is carried unchanged so downstream import/load tooling can apply normal
forward upgrades (e.g. a legacy sign's `Text1`–`Text4` can become
`front_text`/`back_text`).

## Rendering

- [render/isometric.py](render/isometric.py) renders `.schem` files (and raw block
  grids) to isometric PNGs, using the color palette via
  [render/palette.py](render/palette.py) (`color_render.csv` from `config`).
- [render/topdown.py](render/topdown.py) renders a top-down world preview, used by
  the GUI region dialog.
