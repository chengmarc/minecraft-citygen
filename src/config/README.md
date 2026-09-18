# config — settings, tuning, paths & versioning

The base layer of the source tree: settings defaults, artifact paths, the source
world, and version compatibility. It imports nothing else from `src/`;
everything else imports it.

← Back to the [source architecture overview](../README.md).

## How-to guides

### Change a default for a CLI run

Set the matching `MC_CITY_*` variable before the process starts (names and
formats in [Overrides](#overrides)):

```bash
MC_CITY_GAP_BIG=8 MC_CITY_SAVE="/path/to/world" python src/pipeline/stages.py preview --seed 5
```

From Python, don't touch `os.environ` — pass the setting as a stage parameter:

```python
from dataclasses import replace
from config.algo import ALGO
from pipeline.services import run_stage

run_stage("preview", seed=5, algo=replace(ALGO, gap_big=8))
```

### Add a generation knob

1. Add a field with a default to `Algo` in [algo.py](algo.py). Keep it an `int`
   or a `frozenset[str]`: `Algo.from_env` reads those two types from
   `MC_CITY_<FIELD>` automatically, and nothing else.
2. Read it from the `algo` argument inside [`engine`](../engine/README.md) —
   never from `config.algo.ALGO`. `tests/test_dependencies.py` rejects engine
   imports of the per-run defaults.
3. To show it in the app, add it to the Preview/Build form (see the
   [gui guide](../gui/README.md#expose-an-algo-knob-in-the-form)).

### Point the app at a different world or asset regions

- World: `MC_CITY_SAVE`, or the Extract tab's world field in the app.
- Road region: `MC_CITY_ROAD_BOX`. Building regions: `MC_CITY_BUILD_TYPES`.
  Change the built-in defaults (`ROAD_REGION`, `BUILD_TYPE1_REGION`,
  `BUILD_TYPE2_REGION`) in [world.py](world.py) only if the bundled
  `default_world/` changes.

### Refresh the render palette

When the target Minecraft version gains blocks, regenerate
`color_render.csv`, the isometric renderer's block colors:

```bash
python tools/update_render_colors.py                 # latest release
python tools/update_render_colors.py --version 26.1.2
```

It downloads the Minecraft client JAR into `tools/` as
`minecraft-client-<version>.jar` (do not commit it) and overwrites
`color_render.csv`; rows use namespaced ids (`minecraft:stone`). Only the CSV
ships with the app.

### Diagnose a first-run setup

```bash
citygen-doctor               # installed
python src/config/doctor.py  # from a checkout
```

Prints the Python and dependency status, the resolved app/resource roots, the
source world, and its region directory.

## Explanation

### Defaults are read once; per-run settings are arguments

`MC_CITY_*` variables are read **once, at import time**, into this process's
defaults (`ALGO`, `SAVE`, `ROAD_BOX`, `BUILD_TYPES`, `DATA_VERSION`, ...). They
exist so a CLI run can be configured without editing code. They are not a
channel for changing settings between runs: nothing re-imports `config`, so
setting a variable after startup has no effect.

Everything that varies per run — the `Algo`, the source save, the regions, the
DataVersion — is passed to pipeline stages as an argument. The pipeline falls
back to the defaults when an argument is omitted; the engine never falls back,
it only uses what it's given. That keeps GUI runs free of global state and
lets two settings coexist in one process.

### Where outputs go

`path.ROOT` is where `artifacts/` lives. It is resolved once:

- **Repo checkout** — the repository root.
- **Frozen app (PyInstaller)** — the exe's folder when writable, else the
  per-user data dir.
- **Installed package** — the per-user data dir: `%LOCALAPPDATA%\Minecraft CityGen`
  on Windows, `~/Library/Application Support/Minecraft CityGen` on macOS,
  `$XDG_DATA_HOME` (or `~/.local/share`)`/Minecraft CityGen` on Linux.
  `MC_CITY_APP_ROOT` replaces this per-user dir.

`path.RESOURCE_ROOT` is separate: where the read-only bundled files are
(`default_world/`, `color_render.csv`, `gui/icons`) — the source tree, or
PyInstaller's unpack dir.

### Version compatibility

The pipeline copies block strings straight from the source world into the output
schematic, so block *content* is version-transparent. The one thing that is not
is the `DataVersion` stamped on the schematic: an older schematic can be upgraded
forward into a newer world, but a newer one cannot be downgraded safely.

Minecraft CityGen commits to **forward-only** compatibility. The export target is
always the source world's own version or newer, so every block in the palette is
guaranteed to exist in the target. Forward upgrade is left to downstream import
or load tooling; there is no downgrade or "missing block" computation.

How [world.py](world.py) applies it:

- Outputs are **always stamped with the source world's `DataVersion`**, read from
  its `level.dat` and clamped up to the hard floor (Minecraft 26.1.2). Stamping
  any newer version would skip the DataFixer and hole out blocks renamed since
  the source (e.g. `grass` → `short_grass`).
- Extraction stamps the version detected from its `save`. The construct stage
  has no save, so the GUI passes it the source world's version; the CLI default
  is `DATA_VERSION`.
- Because every stamp is ≥ the floor, outputs always use the **Sponge v3**
  container, so the [schematic writer and reader](../engine/README.md#schematic-io)
  are v3-only.
- The Extract tab's **Target Version** selector only indicates which versions
  the output can be pasted into (the source and newer). It does not change the
  stamp.

## Reference

### Modules

| Module | Responsibility |
|---|---|
| [env.py](env.py) | Typed readers (`env_int`, `env_str`, `env_set`, `env_raw`) for `MC_CITY_*` overrides |
| [path.py](path.py) | App and resource roots, every artifact path, the bundled world path |
| [algo.py](algo.py) | `CELL`, `DEFAULT_SEED`, and `Algo` — every road and placement knob, documented inline; `ALGO` is the process default |
| [world.py](world.py) | Source world (`SAVE`) and region lookup, extraction regions, `BUILD_MARKER_Y_RANGE`, region models, `HARD_FLOOR_DATA_VERSION`, `RELEASE_NAMES`, `DATA_VERSION` |
| [render.py](render.py) | Render and preview style constants (tile sizes, ground fill, colors) |
| [doctor.py](doctor.py) | `citygen-doctor` environment diagnostics |

Shipped data: `default_world/` (the bundled Minecraft 26.1.2 source world) and
`color_render.csv` (the renderer palette). Both are listed in
`[tool.setuptools.package-data]` in [pyproject.toml](../../pyproject.toml) and in
the [PyInstaller data set](../../docs/RELEASING.md#explanation).

### Overrides

These are the only variables read. Anything not listed — `CELL`,
`BUILD_MARKER_Y_RANGE`, `render.py` — changes only in code.

| Variable | Sets | Format |
|---|---|---|
| `MC_CITY_<ALGO_FIELD>` | that `Algo` field, e.g. `MC_CITY_GAP_BIG` | integer; `MC_CITY_BANNED_BUILDINGS` is a comma/semicolon-separated ID list |
| `MC_CITY_DEFAULT_SEED` | `DEFAULT_SEED` | integer |
| `MC_CITY_SAVE` | `SAVE`, the source world folder | path |
| `MC_CITY_DATA_VERSION` | `DATA_VERSION`, construct's default stamp | integer, clamped up to the floor |
| `MC_CITY_ROAD_BOX` | `ROAD_BOX` | `((x, y, z), (x, y, z))`, or six flat ints `x0, x1, z0, z1, y0, y1` |
| `MC_CITY_BUILD_TYPES` | `BUILD_TYPES` | `;`-separated regions, each `type, (x, y, z), (x, y, z)` or `type` plus the six flat ints |
| `MC_CITY_APP_ROOT` | the per-user data dir (see [Where outputs go](#where-outputs-go)) | path |

A blank value counts as unset.
