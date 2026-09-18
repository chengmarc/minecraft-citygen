# config — settings, tuning, paths & versioning

Configuration is the base layer of the source tree: it depends on nothing else in
`src/` and everything else depends on it. Values are read from `MC_CITY_*`
environment variables **once, at import time**, as this process's defaults.
Per-run settings (`Algo`, the source save, regions, DataVersion) travel as
arguments, so the engine never reads those defaults.

← Back to the [source architecture overview](../README.md).

## Modules

| Module | Responsibility |
|---|---|
| [env.py](env.py) | Base layer: `env_*` typed readers for `MC_CITY_*` overrides |
| [path.py](path.py) | Runtime paths: app/resource roots, every artifact path, world-save region lookup |
| [algo.py](algo.py) | `CELL`, and the `Algo` dataclass of road-generation and city-placement knobs (`ALGO`: the process default) |
| [world.py](world.py) | Source world path, extraction regions, marker Y range, domain region models, version labels, schematic `DATA_VERSION` |
| [render.py](render.py) | Render and preview style constants (tile sizes, ground fill) |
| [doctor.py](doctor.py) | Environment diagnostics for first-run setup (`citygen-doctor`) |

Non-code assets that ship in this package:

- `default_world/` — the bundled source world (Minecraft 26.1.2)
  the app defaults to; `MC_CITY_SAVE` overrides it.
- `color_render.csv` — the isometric renderer's block-color palette (see
  [Render palette maintenance](#render-palette-maintenance)).

## The `MC_CITY_` override convention

Every tunable in `config` except `CELL` can be overridden by an
`MC_CITY_<NAME>` environment variable (for `Algo`, the upper-cased field name,
e.g. `MC_CITY_GAP_BIG`). The typed readers in `env.py` (`env_int`, `env_set`,
`env_raw`, …) apply the override or fall back to the default. This sets the
defaults for a CLI run without editing code.

In-process callers leave the environment alone: they pass per-run settings as
stage parameters, e.g. `pipeline.services.run_stage("preview", seed=5,
algo=replace(ALGO, gap_big=8))`.

## Version Compatibility

The pipeline copies block strings straight from the source world into the output
schematic, so block *content* is version-transparent. The one thing that is not
is the `DataVersion` stamped on the schematic: an older schematic can be upgraded
forward into a newer world, but a newer one cannot be downgraded safely.

Minecraft CityGen commits to **forward-only** compatibility. The export target is always
the source world's own version or newer, so every block in the palette is
guaranteed to exist in the target. Forward upgrade is left to downstream import
or load tooling, and there is no downgrade or "missing block" computation.

Handled by [world.py](world.py):

- Outputs are **always stamped with the source world's `DataVersion`** (read from
  its `level.dat`, else the **26.1.2 hard floor**, and clamped up to that floor).
  Stamping any newer version would skip the DataFixer and hole out blocks renamed
  since the source (e.g. `grass` → `short_grass`).
- Extraction stamps the version detected from its `save`. The construct stage
  has no save, so the GUI passes it the source world's `data_version`; the CLI
  default is `DATA_VERSION` (`MC_CITY_DATA_VERSION`, else the default world's).
- The floor is `HARD_FLOOR_DATA_VERSION = 4790` (Minecraft 26.1.2). Because every
  stamp is ≥ this floor, outputs always use the **Sponge v3** container; the
  writer and reader in [`engine/schematic`](../engine/README.md#schematic-io)
  are v3-only.
- `RELEASE_NAMES` maps DataVersions to release names for display. The Extraction
  tab shows the detected source version and a **Target Version** selector — an
  indicator of which versions the output can be pasted into (the source and
  newer), which does not change the stamp.

## Key configuration knobs

From [algo.py](algo.py):

- `CELL` — blocks/pixels per fine cell (9); fixed, not overridable
- `DEFAULT_SEED` — default generation seed

`Algo` fields:

- `fine` — grid edge in fine cells
- `gap_big` / `gap_small` — spacing of big avenues (coarse grid) / small streets (fine grid)
- `gap_mixed` — minimum clearance between a small street and a big-road band
- `pad_big` / `pad_small` — edge padding for big / small roads
- `n_big_corners` / `n_big_tees` — forced avenue L-corners / T-intersections
- `n_small_corners` / `n_small_tees` — forced street L-corners / T-intersections
- `banned_buildings` — building IDs excluded from placement; empty by default
- `type1_top_fit_choices` — standard-building variation depth
- `landmark_spacing` — minimum fine-cell distance between landmark footprints

From [world.py](world.py):

- `ROAD_BOX` — road extraction region
- `BUILD_TYPES` — build extraction regions (each with a `type`)
- `BUILD_MARKER_Y_RANGE` — Y range scanned for extraction markers
- `SAVE` — source Minecraft world

All of these accept `MC_CITY_`-prefixed overrides.

## Render palette maintenance

The isometric renderer loads block colors from `color_render.csv` (shipped in
this package). The generator that refreshes it is a repo-maintenance script, not
part of the runtime app:

```bash
python tools/update_render_colors.py
```

Notes:

- It downloads a Minecraft client JAR before regenerating the CSV; with
  `--version` omitted it resolves Mojang's latest release from the live manifest.
- Downloaded JARs land under `tools/` as `minecraft-client-<version>.jar` and are
  repo-local maintenance inputs — do not commit them.
- The script overwrites `color_render.csv`; rows use namespaced ids
  (`minecraft:stone`). Packaging includes only the CSV. Intended for infrequent
  manual updates when the target Minecraft version changes.
