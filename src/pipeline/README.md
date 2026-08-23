# pipeline — stage orchestration

The pipeline drives [engine](../engine/README.md) and [config](../config/README.md)
through four numbered stages to produce the simulation previews and production
schematics. Each stage exposes a uniform `run(*, logger=None, progress=None, ...)`
entry so the GUI and CLI can call it the same way.

← Back to the [source architecture overview](../README.md).

## Layout

| Module / package | Responsibility |
|---|---|
| [services.py](services.py) | In-process pipeline services used by both the GUI and CLI |
| [stages.py](stages.py) | Central registry of stage modules plus the shared stage runner |
| [runtime.py](runtime.py) | `configured_environment` and the import-time config model helpers |
| `01_roads/` | `extract`, `simulation`, `render` |
| `02_builds/` | `extract`, `simulation`, `render` |
| `03_grid/` | `simulation`, `construct`, `render` |
| `04_city/` | `simulation`, `construct`, `render` |

`extract` pulls assets from the world, `simulation` renders fast PNG previews,
`construct` builds production `.schem` output, and `render` produces isometric
PNGs.

## Pipeline stages

**1. Roads.** [01_roads/extract.py](01_roads/extract.py) exports named road `.schem`
pieces from the `ROAD_BOX` region, plus fill props. [01_roads/simulation.py](01_roads/simulation.py)
draws the preview road PNGs.

**2. Builds.** [02_builds/extract.py](02_builds/extract.py) scans the `BUILD_TYPES`
regions, exports individual `.schem` pieces, and writes
`artifacts/builds/production/buildings.json` — the source of truth for placement.

**3. Grid.** [03_grid/simulation.py](03_grid/simulation.py) generates the road
network from a seed and composites the top-down preview;
[03_grid/construct.py](03_grid/construct.py) maps the same seed-driven network to
extracted road schematics and writes a production schematic grid. Both share the
same logical network (via [`engine.core.road_network`](../engine/README.md#how-the-road-grid-is-generated)),
rendered differently.

**4. City.** [04_city/simulation.py](04_city/simulation.py) renders the full city
preview; [04_city/construct.py](04_city/construct.py) assembles the final result —
loads/regenerates the road grid, loads the catalog, generates placements from the
seed, samples type-2 stack counts, assembles rotated building schematics, places
roads and buildings into one master 3D grid, optionally fills non-road ground
cells, and writes the Sponge `.schem` (with an offset so the WorldEdit paste
origin lands correctly).

## In-world asset conventions

Extraction is driven by explicit marker blocks, not guesswork. Roads, fill props,
and buildings all use the **same** convention, so they share one geometry pass in
[`engine.world.marker_extract`](../engine/world/marker_extract.py).

Markers inside each asset:

- a **wool** rectangle bounds each asset; connected wool components separate assets
- one `gold_block` + one `diamond_block` mark two opposite corners of a cuboid
- exactly one `emerald_block` marks ground level (its Y becomes the
  `ground_offset` used to seat the build on city ground)
- marker blocks and signs are blanked to air in the saved schematic

### Roads & fill props

Roads are scanned inside `ROAD_BOX`. `detect_assets(..., expected_components=1)`
resolves each wool-bounded component into a single cuboid (roads are single-solid,
like a type-1 build), and a sign inside the boundary provides the exported name
(e.g. `02_big_2x2_I`). Because markers define the cuboid directly, a tile taller
than `ROAD_BOX`'s Y span is still captured in full (markers are searched over
`BUILD_MARKER_Y_RANGE`).

Fill props are authored in the road region with the same convention and named with
a `fill` token (`15_fill_1x1_A`, …). Each is a self-contained 9x9 (one fine cell)
asset carrying its own ground. `engine.schematic.road` keeps them out of the road
tile set and exposes them via `load_fillers()`; `04_city/construct.py` drops a
random, randomly-rotated fill prop into every fully-empty non-road lot cell.

### Builds

Each build region in `BUILD_TYPES` carries a `type`. Builds are grouped by
connected X/Z components containing wool in the allowed Y range. Inside each
boundary: exactly one `emerald_block`, and matching counts of `gold_block` /
`diamond_block` markers, sorted by Y and paired in order — each pair defines one
cuboid's opposite corners.

- **Type 1** — expected components: 1; exported as one complete schematic.
  Typically smaller frontage buildings.

  ![Type 1 convention](../../docs/type1.png)

- **Type 2** — expected components: 3; exported as `bottom`/`middle`/`top` pieces.
  Intended for stackable or landmark buildings, supporting height variation and
  appearance targeting.

  ![Type 2 convention](../../docs/type2.png)

**Sign directives** inside a build boundary add catalog metadata: `stack: n` or
`stack: min-max` (how many middle sections a type-2 building can receive), and
`appearance: n` or `appearance: min-max` (how many times it should appear per
city). These are parsed into `buildings.json` and stripped from the exported
pieces.

## Generated build catalog

`artifacts/builds/production/buildings.json` is written by stage 02 and consumed
by both simulation stand-ins and production placement. Each entry contains: `type`,
`size`, `origin`, `ground_offset`, `pieces`, plus `stack` and `appearance` for
type-2 buildings.

## Simulation vs production

- **Simulation** — road PNGs and pseudo-build PNGs generated from catalog
  dimensions; fast iteration and layout validation.
- **Production** — extracted road and building schematics, the final combined city
  schematic, and the isometric render.

Placement logic is shared; only the rendered representation differs.

## Outputs

```text
artifacts/roads/production/*.schem
artifacts/builds/production/*.schem
artifacts/builds/production/buildings.json
artifacts/grid/production/seed_<n>.schem
artifacts/city/production/seed_<n>.schem
artifacts/*/*/*.png                        # preview and render images
```

The final city schematic in `artifacts/city/production/` is a Sponge `.schem`
ready to import with WorldEdit.

## Running stages

```bash
python -m pipeline.01_roads.extract
python -m pipeline.02_builds.extract
python -m pipeline.03_grid.simulation --seed 5
python -m pipeline.03_grid.construct --seed 5
python -m pipeline.04_city.simulation --seed 5
python -m pipeline.04_city.construct --seed 5
python -m pipeline.04_city.render
```
