# Minecraft CityGen — source architecture

The technical entry point. Minecraft CityGen turns a small hand-built asset set —
roads and buildings marked up inside a Minecraft world — into a complete city,
exported as a schematic and as a playable world. This page covers the whole
tree; each package guide covers one boundary.

## How-to guides

### Set up and check a development checkout

```bash
python -m pip install -e .
python -m pytest -q
pythonw application.pyw
```

Use pytest, not `unittest`: [tests/conftest.py](../tests/conftest.py) puts
`src/` on `sys.path`, and only pytest loads it. There is no CI; run the suite
before committing.

### Find where a change belongs

| To change… | Go to |
|---|---|
| a default, a tuning knob, where files go, version handling | [config guide](config/README.md#how-to-guides) |
| road layout, building placement, schematic/world I/O, rendering | [engine guide](engine/README.md#how-to-guides) |
| stage order, a new step, in-world marker conventions, `buildings.json` | [pipeline guide](pipeline/README.md#how-to-guides) |
| a tab, the settings form, progress bars | [gui guide](gui/README.md#how-to-guides) |
| the installer, zip, or a release | [packaging guide](../packaging/README.md) |

### Reset local state

Delete `artifacts/` (everything the pipeline generates), `build/` and `dist/`
(packaging output), and `src/config/citygen.json` (saved GUI settings). All are
git-ignored and regenerate on the next run.

## Tutorial: add a tuning knob end to end

This walks through the change that touches the most layers: a new setting that
the engine uses, the CLI can override, and the app shows. The example makes
avenue jitter configurable. Avenues are currently nudged by a random `-1/0/+1`
coarse cells.

1. **Declare it in config.** In [config/algo.py](config/algo.py), add to `Algo`:

   ```python
   big_jitter: int = 1  # max coarse-cell nudge applied to each avenue position
   ```

   `MC_CITY_BIG_JITTER` now works automatically, because `Algo.from_env` reads
   every field.

2. **Use it in the engine.** In
   [engine/core/road_network.py](engine/core/road_network.py), pass
   `algo.big_jitter` down to `_generate_avenues` and replace
   `rng.randint(-1, 1)` with `rng.randint(-jitter, jitter)`. Read it from the
   `algo` argument — the engine never imports `config.algo.ALGO`. With the
   default of `1`, the random draws are identical, so existing seeds still
   produce the same cities.

3. **Try it from the CLI.**

   ```bash
   python src/pipeline/stages.py roads
   python src/pipeline/stages.py builds
   MC_CITY_BIG_JITTER=3 python src/pipeline/stages.py preview --seed 5
   ```

   Compare `artifacts/03_preview/grid/seed_5.png` against a run without the
   variable.

4. **Show it in the app.** In [gui/core/algo_config.py](gui/core/algo_config.py),
   add `("BIG_JITTER", "Avenue Wobble", "…")` to `PREVIEW_CONFIGS`, put
   `"BIG_JITTER"` in the "Avenue and Street Shape" group, and give it a slider
   range such as `(0, 3)`.

5. **Test it.** Add a case next to `test_generation_follows_the_algo_argument` in
   `tests/test_engine_core.py`, then run `python -m pytest -q`.
   `tests/test_dependencies.py` will fail if step 2 read the process default
   instead of the argument.

Every knob follows this path. The package guides cover each step on its own.

## Explanation

### Four packages, one direction

| Package | Responsibility |
|---|---|
| [`config/`](config/README.md) | Defaults, paths, the source world, version compatibility |
| [`engine/`](engine/README.md) | Pure generation and transforms: roads, placement, schematic and world I/O, rendering |
| [`pipeline/`](pipeline/README.md) | The five numbered stages that drive the engine and produce artifacts |
| [`gui/`](gui/README.md) | The PySide6 app that configures and runs the stages |

Imports only point downward: `gui` → `pipeline` → `engine` → `config`. `gui`
may use only `pipeline.stages` and `pipeline.services`. Each package is layered
internally too. [tests/test_dependencies.py](../tests/test_dependencies.py)
enforces all of it, along with no import cycles and no imports of another
module's `_`-prefixed names.

The layering keeps settings explicit. Per-run settings (an `Algo`, the source
save, the regions, the DataVersion) are passed down as arguments. Only the
pipeline falls back to process-wide defaults, so the engine can be called
twice with different settings in one process — which is how the GUI works.

### One pipeline, five stages

```text
01 roads   -> road pieces + contact sheet
02 builds  -> building pieces + buildings.json + contact sheet
03 preview -> road-layout and city-layout PNGs for a seed
04 city    -> the city .schem + isometric render
05 world   -> a copy of the source save with the city written in
```

Preview isn't a separate pipeline. It's a fast iteration step that shares
Stage 4's layout code, so what you preview is what gets built.
`buildings.json` connects extraction to placement. Details are in the
[pipeline guide](pipeline/README.md#the-stages).

### The unit that ties it together

```text
1 fine cell = 9 preview pixels = 9 blocks
```

`CELL = 9` in [config/algo.py](config/algo.py). Buildings snap to fine cells;
small roads are 1 cell wide, big roads 2.

### What it is not

A structured city *assembler*, not a general urban simulator. It is strongest
when the assets follow the conventions exactly:

- Roads are orthogonal (Manhattan) only — no diagonals or curves.
- Assets are found through strict in-world markers; malformed markers mean the
  asset is skipped.
- Footprints snap to the fine-cell grid; no freeform placement.
- Stage 3 previews are layout-accurate stand-ins, not faithful visuals.

## Reference

- **Python** `>= 3.10`. Runtime dependencies (`numpy`, `nbtlib`, `numba`,
  `PySide6`, `Pillow`) and entry points (`citygen`, `citygen-doctor`) are
  declared in [pyproject.toml](../pyproject.toml).
- **Input:** a Minecraft **Java Edition** world, 1.18+ Anvil format. Bedrock
  and older formats are not supported.
- **Output:** Sponge `.schem` v3, and standalone worlds. Minimum Minecraft
  version 26.1.2, forward-only — see the
  [config guide](config/README.md#version-compatibility).
- **Generated directories** (all git-ignored): `artifacts/` (pipeline outputs,
  see [pipeline outputs](pipeline/README.md#outputs)), `build/` and `dist/`
  (packaging), `.pytest_cache/`.
- **Repo maintenance scripts** in [tools/](../tools): `update_render_colors.py`
  (see the [config guide](config/README.md#refresh-the-render-palette)) and
  `remove_init_and_pycache.py`, which deletes every `__pycache__` and
  `__init__.py`.
- **No `__init__.py`.** Every package under `src/` is a namespace package;
  don't add one.
