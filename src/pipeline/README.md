# pipeline — stage orchestration

The pipeline drives [engine](../engine/README.md) and [config](../config/README.md)
through five numbered stages to produce the simulation previews, production
schematics, and a ready-to-play world. Each stage exposes a uniform
`run(*, logger=None, progress=None, ...)` entry so the GUI and CLI can call it the
same way.

← Back to the [source architecture overview](../README.md).

## Layout

| Module / package | Responsibility |
|---|---|
| [services.py](services.py) | In-process pipeline services used by both the GUI and CLI |
| [stages.py](stages.py) | Central registry of stage modules plus the stage registry CLI |
| [runtime.py](runtime.py) | `configured_environment` and the import-time config model helpers |
| `01_roads/` | road extraction and road contact-sheet rendering |
| `02_builds/` | building extraction, catalog writing, and building contact-sheet rendering |
| `03_preview/` | road assets, build stand-ins, road-layout preview, and city-layout preview |
| `04_city/` | final city schematic construction and isometric render |
| `05_world/` | standalone Minecraft world export |

`extract` pulls assets from the world, `render` produces isometric/contact-sheet
PNGs, `preview` renders the fast road-layout and city-layout PNGs, `construct`
builds the final city `.schem`, and `world` exports the final city as a
standalone Minecraft save.

## Runtime boundary

Pipeline stages read configuration from `MC_CITY_*` environment variables at
import time through the `config` package. In-process callers should not mutate
`os.environ` directly; call [`services.py`](services.py) functions with an
`env_overrides` dict containing only the `MC_CITY_*` values needed for that run.
[`runtime.py`](runtime.py) applies those values under a process-wide lock,
reloads config/engine/stage modules in dependency order, runs the stage, then
restores the previous environment and reloads again.

This keeps GUI runs deterministic, but it is still process-global state. Run
overridden stages one at a time inside a process. For true concurrent generation
with different configs, use separate processes or replace the import-time config
model with explicit config objects.

## Pipeline stages

**1. Roads.** [01_roads/extract.py](01_roads/extract.py) exports named road
`.schem` pieces from the `ROAD_BOX` region, plus fill props.
[01_roads/render.py](01_roads/render.py) renders those extracted road pieces and
writes the road contact sheet.

**2. Builds.** [02_builds/extract.py](02_builds/extract.py) scans the `BUILD_TYPES`
regions, exports individual `.schem` pieces, and writes
`artifacts/02_builds/buildings.json` — the source of truth for
placement. [02_builds/render.py](02_builds/render.py) renders those extracted
building pieces and writes the building contact sheet.

**3. Preview.** `stages.py run_preview` is the unified preview stage. It runs
[03_preview/roads.py](03_preview/roads.py),
[03_preview/builds.py](03_preview/builds.py),
[03_preview/grid.py](03_preview/grid.py), and
[03_preview/city.py](03_preview/city.py): generating road preview assets,
generating pseudo top-down building assets from the catalog, rendering the
seed-driven road-layout preview, and rendering the city-layout preview.
Internally it reuses the same road-network and placement logic as the final city
build.

**4. City.** [04_city/construct.py](04_city/construct.py) assembles the final
result — builds the road grid, loads the catalog, generates placements from the
seed, samples stack counts for three-piece buildings, assembles rotated building
schematics, places roads and buildings into one master 3D grid, optionally fills
non-road ground cells, and writes the Sponge `.schem` (with an offset so the
schematic import origin lands correctly). [04_city/render.py](04_city/render.py)
renders the final city schematic as an isometric PNG.

**5. World.** [05_world/export.py](05_world/export.py) reads the final city
`.schem` and writes a standalone, ready-to-play world to
`artifacts/05_world/saves/CityGen World <n>/` (via
[`engine.world.writer`](../engine/world/writer.py), the inverse of the Anvil
reader). It copies the selected source save, purges only the copied overworld
region files, writes generated city chunks back into that same layout, seats the
ground near y=64, centres the city on the world origin, and pins the player spawn
to solid ground so the world opens directly on the city.

## In-world asset conventions

Extraction is driven by explicit marker blocks, not guesswork.

### Roads & fill props

Roads are scanned inside `ROAD_BOX` with the shared marker extractor. A
one-layer gold/diamond asset with an emerald ground marker becomes one road
schematic, and the sign above the emerald provides the exported name (e.g.
`02_big_2x2_I`). Because markers define the cuboid directly, a tile taller than
`ROAD_BOX`'s Y span is still captured in full (markers are searched over
`BUILD_MARKER_Y_RANGE`).

Fill props are authored in the road region and named with a `fill` token
(`15_fill_1x1_A`, ...). Each is a self-contained 9x9 (one fine cell) asset
carrying its own ground. `engine.schematic.road` keeps them out of the road tile
set and exposes them via `load_fillers()`; `04_city/construct.py` drops a random,
randomly-rotated fill prop into every fully-empty non-road lot cell. The
dedicated road-region ground-fill asset `18` is also required for ordinary empty
lot ground; it is repeated across empty non-road, non-building columns and skips
cells already occupied by self-contained fill props.

### Builds

Each build region in `BUILD_TYPES` carries a placement `type`. Builds are detected
from direct gold/diamond marker pairs: each gold is paired with the closest unused
diamond, and each pair defines one cuboid's opposite corners. Cuboids with the
same X/Z footprint are grouped by vertical alignment. Each grouped asset must
also have an emerald marker horizontally adjacent to the bottom gold; that
emerald marks the asset ground level and anchors the metadata sign above it.

- **One layer** — one gold/diamond pair; exported as one complete schematic.

  ![Type 1 convention](../../docs/pics/type1.png)

- **Three layers** — three vertically aligned gold/diamond pairs; exported as
  `bottom`/`middle`/`top` pieces. City generation can repeat the middle piece to
  vary height.

  ![Type 2 convention](../../docs/pics/type2.png)

Type and layer count are independent: a type-1 building can have three layers,
and a type-2 landmark can have one. Type-2 catalog IDs are placed exactly once per
city, largest footprints first with `LANDMARK_SPACING` between landmarks; type-1
IDs have no repeat limit.

**Sign directives** above the emerald marker add catalog metadata: `stack: n` or
`stack: min-max` (how many middle sections a three-layer building can receive).

## Generated build catalog

`artifacts/02_builds/buildings.json` is written by stage 02 and consumed
by both simulation stand-ins and production placement. Each entry contains: `type`,
`size`, `origin`, `ground_offset`, and `pieces`, plus `stack` for three-layer
buildings.

## Preview vs city build

Stage 3 writes fast road-layout and city-layout PNGs for iteration and layout
validation. Stage 4 writes the real combined city schematic and its isometric
render. Placement logic is shared; only the rendered representation differs.

## Outputs

```text
artifacts/01_roads/schem/*.schem
artifacts/01_roads/renders/*.png
artifacts/02_builds/schem/*.schem
artifacts/02_builds/renders/*.png
artifacts/02_builds/buildings.json
artifacts/03_preview/roads/*.png
artifacts/03_preview/builds/*.png
artifacts/03_preview/grid/seed_<n>.png
artifacts/03_preview/city/seed_<n>.png
artifacts/04_city/schem/seed_<n>.schem
artifacts/04_city/renders/seed_<n>.png
artifacts/05_world/saves/CityGen World <n>/       # standalone playable world
```

The final city schematic in `artifacts/04_city/schem/` is a Sponge `.schem`;
`artifacts/05_world/saves/CityGen World <n>/` is a copied source-world save with generated
city regions, ready to drop straight into `.minecraft/saves/`.

## Running stages

From a repo checkout, the stage registry CLI works without installing the
package:

```bash
python src/pipeline/stages.py roads
python src/pipeline/stages.py builds
python src/pipeline/stages.py preview --seed 5
python src/pipeline/stages.py city --seed 5
python src/pipeline/stages.py world --seed 5
```

Package-module execution is also supported when `src/` is on `PYTHONPATH` or the
project is installed:

```bash
python -m pipeline.stages roads
python -m pipeline.stages builds
python -m pipeline.stages preview --seed 5
python -m pipeline.stages city --seed 5
python -m pipeline.stages world --seed 5
```

The lower-level extract/render/construct/export modules remain runnable for
debugging, but the five commands above are the canonical numbered pipeline.
