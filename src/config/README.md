# config — settings, tuning, paths & versioning

Configuration is the base layer of the source tree: it depends on nothing else in
`src/` and everything else depends on it. Values are read from `MC_CITY_*`
environment variables **at import time** and exposed as module-level constants, so
a stage's behavior is fixed once its config module is imported.

← Back to the [source architecture overview](../README.md).

## Modules

| Module | Responsibility |
|---|---|
| [path.py](path.py) | Base layer: `env_*` typed override readers and runtime path/artifact discovery |
| [algo.py](algo.py) | Road-generation and city-placement tuning knobs |
| [world.py](world.py) | Source world path, extraction regions, marker Y range, schematic `DATA_VERSION` |
| [render.py](render.py) | Render and preview style constants (tile sizes, ground fill) |
| [models.py](models.py) | Typed domain models shared across stages (`BlockRegion`, `BuildRegion`) |
| [versions.py](versions.py) | DataVersion detection, release-name labels, and the hard floor |
| [doctor.py](doctor.py) | Environment diagnostics for first-run setup (`citygen-doctor`) |

Non-code assets that ship in this package:

- [default_world/](default_world) — the bundled source world (Minecraft 1.20)
  the app defaults to; `MC_CITY_SAVE` overrides it.
- `color_render.csv` — the isometric renderer's block-color palette (see
  [Render palette maintenance](#render-palette-maintenance)).

## The `MC_CITY_` override convention

Every tunable in `config` can be overridden by an `MC_CITY_<NAME>` environment
variable. The typed readers in `path.py` (`env_int`, `env_set`, `env_raw`, …)
apply the override or fall back to the default. The GUI and CLI set these
variables before importing/reloading a stage, which is how a run is configured
without editing code.

## Version Compatibility

The pipeline copies block strings straight from the source world into the output
schematic, so block *content* is version-transparent. The one thing that is not
is the `DataVersion` stamped on the schematic: WorldEdit upgrades an older
schematic forward into a newer world but cannot downgrade a newer one.

CityGen commits to **forward-only** compatibility. The export target is always
the source world's own version or newer, so every block in the palette is
guaranteed to exist in the target — WorldEdit's DataFixer handles the forward
upgrade for free, and there is no downgrade or "missing block" computation.

Handled by [versions.py](versions.py):

- Outputs are **always stamped with the source world's `DataVersion`** (read from
  its `level.dat`, else the **1.20 hard floor**, and clamped up to that floor).
  Stamping any newer version would skip the DataFixer and hole out blocks renamed
  since the source (e.g. `grass` → `short_grass`).
- `DATA_VERSION` is pinned via `MC_CITY_DATA_VERSION` so construct/render stages —
  which do not set `MC_CITY_SAVE` — stamp the source version rather than
  re-detecting the default world.
- The floor is `HARD_FLOOR_DATA_VERSION = 3463` (Minecraft 1.20). Because every
  stamp is ≥ this floor, outputs always use the **Sponge v3** container; the
  writer and reader in [`engine/schematic`](../engine/README.md#schematic-io)
  are v3-only.
- `RELEASE_NAMES` maps DataVersions to release names for display. The Extraction
  tab shows the detected source version and a **Target Version** selector — an
  indicator of which versions the output can be pasted into (the source and
  newer), which does not change the stamp.

## Key configuration knobs

From [algo.py](algo.py):

- `CELL` — blocks/pixels per fine cell (9)
- `FINE` — grid edge in fine cells
- `DEFAULT_SEED` — default generation seed
- `GAP_BIG` / `GAP_SMALL` — spacing of big avenues (coarse grid) / small streets (fine grid)
- `GAP_MIXED` — minimum clearance between a small street and a big-road band
- `PAD_BIG` / `PAD_SMALL` — edge padding for big / small roads
- `N_BIG_CORNERS` / `N_BIG_TEES` — forced avenue L-corners / T-intersections
- `N_SMALL_CORNERS` / `N_SMALL_TEES` — forced street L-corners / T-intersections
- `BANNED_BUILDINGS` — building IDs excluded from placement
- `TYPE1_TOP_FIT_CHOICES` / `TYPE2_TOP_FIT_CHOICES` — variation depth per type
- `TYPE2_SAME_COARSE_SPAN` — type-2 repeat-exclusion window

From [world.py](world.py):

- `ROAD_BOX` — road extraction region
- `BUILD_TYPES` — build extraction regions (each with a `type`)
- `BUILD_MARKER_Y_RANGE` — Y range scanned for emerald/gold/diamond markers
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
