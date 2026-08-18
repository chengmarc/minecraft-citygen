# City Generation Pipeline

This repository builds a procedural Minecraft city from a small set of road and building assets.

It has two parallel pipelines:

- **simulation**: fast top-down PNG previews for iteration and layout debugging
- **production**: Sponge `.schem` output and isometric PNG renders for WorldEdit / Minecraft use

The numbered folders now live under `pipeline/`. Each stage has a simulation side, a production side, or both.

## What This Repo Does

The pipeline starts with road/building assets, generates a road network, places buildings into lots, and outputs either preview images or pasteable schematics.

High-level flow:

```text
01 roads      -> road tile assets
02 builds     -> building catalog/assets
03 grid       -> generated road network
04 city       -> road grid + placed buildings
```

Simulation flow:

```text
pipeline/01_roads_simulation     draw tiny transparent road PNG tiles
pipeline/02_builds_simulation    draw pseudo top-down building PNGs from the catalog
pipeline/03_grid_simulation      compose those road PNGs into a top-down grid preview
pipeline/04_city_simulation      compose road PNGs + building PNGs into a labeled city preview
```

Production flow:

```text
pipeline/01_roads_production     extract road .schem tiles from the Minecraft world, then render them
pipeline/02_builds_production    extract real building .schem pieces and the building catalog
pipeline/03_grid_production      compose road .schem tiles into a generated grid .schem
pipeline/04_city_production      compose the final city .schem, then render it
```

`city-prod-construct` saves the generated city schematic in `pipeline/04_city_production/schematics/`
and then copies it into the WorldEdit schematics folder configured by `WORLDEDIT_SCHEM`
in `config/config_path.py` as `seed_<n>_city.schem`. The exported city schematic
includes a player paste anchor: `//paste` places you standing on the top face of
a smooth stone block at the schematic's reserved corner marker.

## Repository Layout

```text
engine/
  road_network.py          road network topology and 2D road compositing
  road_schematic.py        production road-grid schematic assembly
  building_schematic.py    production building piece assembly
  city_layout.py           city placement rules, shared helpers, type passes
  schematic_transform.py   schematic tile and block-state rotation helpers
  schematic_reader.py      Sponge schematic reader helpers
  schematic_writer.py      Sponge schematic writer helpers
  isometric_renderer.py    isometric PNG rendering
  anvil_world_reader.py    minimal Minecraft Anvil world reader
  color_render.csv         block color table used by isometric rendering

config/config_algo.py      generation and placement algorithm tuning
config/config_path.py      central repo and artifact paths
config/config_render.py    preview/render colors, isometric scale, render fill blocks
config/config_world.py     Minecraft save path, extraction regions, DataVersion
clear_cache.py             clears generated artifacts and Python __pycache__ folders
```

Generated assets currently live beside the scripts that produce them. For example, `pipeline/02_builds_simulation/*.png` are generated pseudo-building previews, and `pipeline/04_city_production/schematics/*.schem` are generated final city schematics. In production stages, `schematics/` is reserved for generated `.schem` and `.json` outputs.

## How To Run

Use the GUI from the repo root.

GUI:

```bash
pythonw application.pyw
```

Launching `application.pyw` clears previously generated pipeline artifacts before opening the window.

Manual simulation commands:

```bash
python pipeline/01_roads_simulation/draw_roads.py
python pipeline/02_builds_simulation/draw_builds.py
python pipeline/03_grid_simulation/draw_grid.py --seed 5
python pipeline/04_city_simulation/draw_city.py --seed 5
```

Or run the full simulation preview pipeline manually:

```bash
python pipeline/01_roads_simulation/draw_roads.py
python pipeline/02_builds_simulation/draw_builds.py
python pipeline/03_grid_simulation/draw_grid.py --seed 5
python pipeline/04_city_simulation/draw_city.py --seed 5
```

Manual production commands:

```bash
python pipeline/01_roads_production/extract_roads.py
python pipeline/01_roads_production/render_roads.py
python pipeline/02_builds_production/extract_builds.py
python pipeline/02_builds_production/render_builds.py
python pipeline/03_grid_production/construct_grid.py --seed 5
python pipeline/03_grid_production/render_grid.py
python pipeline/04_city_production/construct_city.py --seed 5
python pipeline/04_city_production/render_city.py
```

Clear generated artifacts and Python cache directories:

```bash
python clear_cache.py
```

## How To Modify

Use these files as the main extension points.

### Change Grid Size Or Network Shape

Edit `config/config_algo.py`.

Important knobs:

- `CELL`: simulation pixels and production blocks per fine grid cell
- `FINE`: default grid edge in fine cells
- `GAP_BIG`, `GAP_SMALL`: road spacing
- `BANNED_BUILDINGS`: building IDs to skip during placement
- `TYPE2_TOP_FIT_CHOICES`: type-2 random choice depth among fitting buildings
- `TYPE1_TOP_FIT_CHOICES`: type-1 random choice depth among fitting buildings
- `TYPE2_SAME_COARSE_SPAN`: same-ID type-2 spacing on the coarse grid;
  `6` forbids repeats inside the same coarse 6x6 window
- `N_BIG_CORNERS`, `N_SMALL_CORNERS`, `N_BIG_TEES`, `N_SMALL_TEES`: forced topology features
- `N_BIG_MASKS`, `N_SMALL_MASKS`, `MASK_MIN`, `MASK_MAX`: road-free zones

### Change Road Simulation Art

Edit `pipeline/01_roads_simulation/draw_roads.py`.

This controls the transparent top-down road PNG tiles used by simulation previews. Empty pixels are left transparent.

### Change Road Production Assets

Edit road structures in the Minecraft source world, then run:

```bash
python pipeline/01_roads_production/extract_roads.py
python pipeline/01_roads_production/render_roads.py
```

The extraction region comes from `config/config_world.py`.

### Change Building Catalog Or Real Building Assets

Edit the source-world buildings and markers, then run:

```bash
python pipeline/02_builds_production/extract_builds.py
python pipeline/02_builds_production/render_builds.py
```

The catalog is generated from wool-boundary build groups and gold/diamond
component cuboids at:

```text
pipeline/02_builds_production/schematics/buildings.json
```

Simulation buildings are generated from that catalog, not from the world:

```bash
python pipeline/02_builds_simulation/draw_builds.py
```

For type-2 buildings, a `stack: min-max` sign becomes
`stack: [min, max]`, controlling how many middle sections are stacked in
production.

For type-2 buildings, an `appearance: min-max` or `appearance: n`
sign becomes `appearance: [min, max]` in `buildings.json`. Each generated city
samples one target count from that range and places that asset until the target
is reached. To skip specific assets entirely, edit `BANNED_BUILDINGS` in
`config/config_algo.py`.

### Change City Placement

Edit `engine/city_layout.py`.

This controls:

- lot detection
- frontage scanning
- two-pass filling: type-2 buildings first by longest uninterrupted big-road frontage,
  then type-1 buildings
- random choice among the top fitting buildings ranked by asset width x length
- building footprint snapping
- shared placement origin math used by both simulation and production
- banned building IDs, type-2 target counts sampled from `appearance`, and
  same-ID type-2 spacing on the coarse grid

Keep base sim/prod placement logic here when possible. Avoid duplicating placement math in individual stage scripts.

### Change Rendering

Edit `engine/isometric_renderer.py` and `engine/color_render.csv`.

The renderer decodes `.schem` files and converts block states into isometric PNGs. Unknown blocks render magenta by default, which usually means `engine/color_render.csv` needs a new block color entry.

## Mental Model

The most important convention is:

```text
1 fine cell = 9 pixels in simulation = 9 blocks in production
```

Simulation previews are intended to match production layout, not production visuals. Production uses real `.schem` assets; simulation uses transparent PNG stand-ins that are faster to inspect.

The city layout should be deterministic for a given seed. If simulation and production disagree on building count or placement, first check for duplicated random-number usage or duplicated placement math.
