# MC CityGen — source

MC CityGen turns a small hand-built asset set (roads and buildings marked up inside an MC world) into a complete
city, exported as a schematic and as a playable world. Everything is in one package, `citygen`, laid out by what the
app does.

## Set up

```bash
python -m pip install -e .
python -m pytest -q
pythonw src/application.pyw            # the app; add --debug for the page's developer tools (F12)
```

Use pytest: [tests/conftest.py](../tests/conftest.py) puts `src/` on `sys.path`. There is no CI; run the suite before
committing. To reset, delete `appdata/` (everything the app writes) and `build/`, `dist/` (packaging).

## Where things are

The three `step*_` files are the pipeline, one per tab; they only orchestrate. The algorithms are in `core/`, the
file formats and renderers they use in `tools/`.

| File                                                                                                                                                               | What it is                                                                                                                           |     |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ | --- |
| [step1_extract.py](citygen/step1_extract.py)                                                                                                                       | **The Extract tab's run**: export each marked road piece and building as `.schem`, write `buildings.json`, render the contact sheets |     |
| [step2_preview.py](citygen/step2_preview.py)                                                                                                                       | **The Preview tab's run**: flat top-down stand-ins, laid out as the seed's road layout and city layout                               |     |
| [step3_build.py](citygen/step3_build.py)                                                                                                                           | **The Build tab's run**: the city as one `.schem`, its render, and the exported world                                                |     |
| [settings.py](citygen/settings.py)                                                                                                                                 | The algorithm's knobs (`Algo`), the bundled world's sample areas, version stamping                                                   |     |
| [paths.py](citygen/paths.py)                                                                                                                                       | Where the app keeps its data, and every output's path                                                                                |     |
| **core/**                                                                                                                                                          |                                                                                                                                      |     |
| [road_network.py](citygen/core/road_network.py)                                                                                                                    | The road grid for a seed, and the road tile catalogue                                                                                |     |
| [city_layout.py](citygen/core/city_layout.py)                                                                                                                      | Lots and building placement (`plan_city`), shared by preview and build                                                               |     |
| [markers.py](citygen/core/markers.py)                                                                                                                              | Finding assets in a world by their marker blocks, and copying them out                                                               |     |
| [assemble.py](citygen/core/assemble.py)                                                                                                                            | The city as one voxel grid: the road grid, seated buildings, lot fill                                                                |     |
| **tools/**                                                                                                                                                         |                                                                                                                                      |     |
| [schem.py](citygen/tools/schem.py)                                                                                                                                 | Sponge v3 `.schem` read/write, tile rotation, voxel grids, the building catalog and its pieces                                       |     |
| [world_reader.py](citygen/tools/world_reader.py), [world_writer.py](citygen/tools/world_writer.py)                                                                 | Read Anvil worlds; write the exported world                                                                                          |     |
| [render_isometric.py](citygen/tools/render_isometric.py), [render_topdown.py](citygen/tools/render_topdown.py), [contact_sheet.py](citygen/tools/contact_sheet.py) | Isometric renders; the region map's top-down picture and its cache; labelled thumbnail grids                                         |     |
| [blocks.py](citygen/tools/blocks.py)                                                                                                                               | Block-state strings (`name[prop=val]`), air, and each block's render colour                                                          |     |
| [data/](citygen/data)                                                                                                                                              | What ships: the sample world (`default_world/`) and the block colours (`color_render.csv`)                                           |     |
| [gui/](citygen/gui)                                                                                                                                                | The app: a native window (WebView2, through pywebview) showing the page in `gui/static/`                                             |     |

In `gui/`: `app.py` opens the window; `bridge.py` is every call the page makes; `extract_tab.py` and `city_tabs.py`
are the tabs, each starting its run on a background thread through `session.py`'s `Runner`; `form.py` is the algorithm
form; `progress.py` places each run's progress on its bar; `server.py` serves the page and the images; `files.py` is
saved settings and cleanup. The page itself: `index.html`, `app.js` (the tabs, wired to the bridge), `text.js` (every
word it shows), `tokens.css` (colours; the title bar reads three of them), `app.css`, and one folder per part:
`viewer/`, `progress/`, `form/`, `region/`.

## How a run works

The three `step*_` modules are the pipeline: each tab calls its module's `run`, which takes the tab's settings and reports
`progress(step, completed, total[, detail])` by step code; [gui/progress.py](citygen/gui/progress.py) gives each step
a hand-tuned weight on the bar, and the page names the bar's segments by the same codes (`TEXT.segments`).

| Tab | Runs | Steps |
|---|---|---|
| Extract | `step1_extract.run(save, road_box, build_types, progress)` | `scan_roads`, `road_pieces`, `road_sheet`, `scan_builds`, `build_pieces`, `build_sheet` |
| Preview | `step2_preview.run(seed, algo, progress)` | `road_pieces`, `build_pieces`, `road_layout`, `city_layout` |
| Build | `step3_build.run(seed, algo, save, progress)` | `construct` (eight steps, `step3_build.STEPS`), `render`, `world` |

Every run reads and writes `appdata/`, so runs go one at a time. Preview and Build stay disabled until extraction's two
contact sheets exist. Each launch, and each change of source world, clears `appdata/` except the exported worlds and
the saved settings, so assets from one world never leak into another's city.

Python owns the state; the page draws it and words it. Python answers with facts and short codes
(`{"code": "running"}`), and every word on screen is in `text.js`. A run tells the page `progress`, `done`, `failed`
and `finished`, plus `partial` and `piece` for what's ready early, through `citygen.receive(event, payload)`.
`bridge.py` imports nothing from pywebview, so `tests/test_gui_web.py` drives it without a window.

## How the city is made

**One unit.** `1 fine cell = 9 preview pixels = 9 blocks` (`CELL`). Buildings snap to fine cells; small roads are 1
cell wide, big roads 2.

**Roads.** Two Manhattan networks overlaid: big roads on a coarse grid (one coarse cell is 2x2 fine cells), small
roads on the fine grid; where a small road crosses a big one, a mixed 1x2 tile. Two rules hold by construction and the
tile art relies on them: a small road never lies inside a big road except as a crossing, and never runs alongside one.

**Placement.** Road cells are forbidden; the rest flood-fills into lots. Landmarks (type 2) go first, on big-road
frontage, each at most once per city and `landmark_spacing` apart; then ordinary buildings (type 1) on all frontage,
each picked at random among the `type1_top_fit_choices` best fits. Everything is deterministic for a seed: placement, stack
heights and fill props each draw from their own `seeded_rng` stream, so new randomness needs a new stream, or every
existing seed changes.

**One ground plane.** Every road, building and fill tile is seated so its emerald marker lines up with the shared
ground; that's why an asset without an emerald is skipped. Block-entity NBT (signs, chests, banners) travels verbatim
from extraction to export, its position turning with its tile.

## In-world asset conventions

Each asset is a cuboid between a **gold** and a **diamond** block at opposite corners, with an **emerald** beside the
gold at ground level. An asset with malformed markers is skipped, not repaired.

**Roads and fill props**, inside the road area: one cuboid each, named by the sign one block above the emerald (e.g.
`02_big_2x2_I`). The first two characters decide what it is:

| Prefix | Meaning |
|---|---|
| `01`–`05` | big 2x2 tiles (`BIG_TILES` in core/road_network.py) |
| `06`–`10` | small 1x1 tiles (`SMALL_TILES`) |
| `11`–`14` | mixed 1x2 crossings (`MIXED_TILES`) |
| `18` | the empty-lot ground fill, required |
| any other, name contains `fill` | a 9x9 fill prop with its own ground, one per empty lot cell |

**Buildings**, inside the house area (type 1, repeatable) and the landmark area (type 2, once per city): one cuboid is
a `whole` building; three stacked cuboids with the same footprint are `bottom`/`middle`/`top`, the middle repeating to
vary height. A sign above the emerald may say `stack: n` or `stack: min-max` (default `1`).

![One-layer convention](../docs/pics/type1.png)
![Three-layer convention](../docs/pics/type2.png)

`appdata/02_builds/buildings.json` is the catalog everything after extraction places from. Keys are `"001"`,
`"002"`, …; each entry has `type` (1 or 2), `size` (`[width, depth]`), `origin`, `ground_offset` (the emerald's
height in the asset), `pieces` (each piece's height) and, stacked buildings only, `stack` (`[min, max]`).

## Versions and data

**Forward-only.** Block strings are copied straight from the source world, so every output is stamped with the source
world's own `DataVersion`, clamped up to MC 26.1.2 (`HARD_FLOOR_DATA_VERSION`): a schematic can be upgraded into a
newer world, never down. Every stamp is inside Sponge v3, so `tools/schem.py` is v3-only. The Extract tab's target version
only shows where the output can go; it changes nothing.

**Where the data goes.** `appdata/` sits at the repo root in a checkout; beside the exe in a portable build when that's
writable; else in the per-user data folder (`%LOCALAPPDATA%\MC CityGen` on Windows), or the package's real folder for
the Store build. The bundled files are read from `src/` or PyInstaller's unpack folder (`paths.RESOURCE_ROOT`).

## How to…

**Add a knob.** Add a field to `Algo` in [settings.py](citygen/settings.py) (an `int`, or a `frozenset[str]`), and read
it from the `algo` argument, never from `ALGO`. To show it, add its name to `KNOBS` and one of the `GROUPS` in
[gui/form.py](citygen/gui/form.py), with a range in `SLIDER_RANGES` (or in `SET_KNOBS` for a set), and give it a label
and tip in `TEXT.form.knobs` in `text.js`. The form is built from `form_spec`, so there's no HTML to change.

**Add a road tile.** Add `(ports, "NN_<name>")` to `BIG_TILES`, `SMALL_TILES` or `MIXED_TILES` in
[core/road_network.py](citygen/core/road_network.py) with a new prefix, ports in the unrotated orientation, and author the
matching asset in the world. Pieces are matched to tiles by prefix alone.

**Add a step to a run.** Report it with a new code from the run, give the code a weight in `WEIGHTS` and a segment in
`SEGMENTS` in [gui/progress.py](citygen/gui/progress.py), and name the segment in `TEXT.segments` in `text.js`.

**Re-tune a progress bar.** Time a run's steps and set the weights in `WEIGHTS` in proportion; each tab's weights only
matter relative to each other.

**Refresh the block colours.** When MC gains blocks, run `python scripts/update_render_colors.py [--version 26.1.2]`:
it downloads the client JAR into `build/` and rewrites `data/color_render.csv`. `--vivid-only` re-derives the
saturated colours without downloading.

Releases, the installer and the Store package are in the [release guide](../docs/RELEASING.md).
