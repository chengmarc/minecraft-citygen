# Minecraft CityGen Source Architecture

This is the engineering entry point for Minecraft CityGen's source tree. It explains how the
app is structured and links out to a per-package guide for the details. Start
here, then follow the link into the package you care about.

Minecraft CityGen turns a small, handcrafted asset set — roads and buildings marked up
inside a Minecraft world — into a complete, paste-ready city. Everything under
`src/` is one of four packages:

| Package | Responsibility | Guide |
|---|---|---|
| `config/` | Settings, tuning knobs, paths, version compatibility, the bundled world | [config guide](config/README.md) |
| `engine/` | Pure generation & transforms: road networks, placement, schematic I/O, rendering | [engine guide](engine/README.md) |
| `gui/` | PySide6 desktop app that drives the pipeline | [gui guide](gui/README.md) |
| `pipeline/` | Numbered stages that orchestrate engine + config into artifacts | [pipeline guide](pipeline/README.md) |

The dependency direction is one-way: `gui/` and `pipeline/` depend on `engine/` and
`config/`; `engine/` depends on `config/`; `config/` depends on nothing else in the
tree.

## High-Level Model

Minecraft CityGen runs one numbered pipeline from source assets to a playable exported
world. Preview images are generated in the same sequence as an iteration step;
they are not a separate parallel pipeline. The project flow runs in five stages:

```text
01 roads   -> road assets + road asset render
02 builds  -> building assets + catalog + build asset render
03 preview -> generated road-layout and city-layout PNG previews
04 city    -> final city schematic + isometric city render
05 world   -> copied source save with generated city regions
```

The core unit tying pixels to blocks is:

```text
1 fine cell = 9 simulation pixels = 9 production blocks
```

defined by `CELL = 9` in [config/algo.py](config/algo.py). `buildings.json`
(written by stage 02) is the bridge between extraction and placement.

## Requirements & Assumptions

- Python `>= 3.10`; runtime deps: `numpy`, `nbtlib`, `numba`, `PySide6`,
  `Pillow`. Declared in [pyproject.toml](../pyproject.toml).
- Source world: Minecraft **Java Edition**, 1.18+ Anvil region/chunk format.
  Not a Bedrock pipeline; older world formats are not supported.
- Output: Sponge `.schem` (v3 container) plus standalone world exports. The
  supported floor is Minecraft **26.1.2**; versioning is **forward-only** — see
  the [config guide](config/README.md#version-compatibility).
- Local filesystem access to the Minecraft save and the export directory is
  assumed. Opening output folders uses the platform file manager (`os.startfile`,
  `open`, or `xdg-open`).

## Limitations

- Roads are orthogonal Manhattan-style only (no diagonals/curves); big roads are
  `2x2` fine cells, small roads `1x1`, mixed pieces `1x2` transverse crossings.
- Extraction depends on strict in-world marker conventions; malformed markers
  skip the build. Building type controls placement, while one or three
  vertically aligned gold/diamond pairs control whether the asset is exported as
  a whole schematic or `bottom`/`middle`/`top` pieces. Each asset also needs an
  emerald block next to the bottom gold block to mark its authored ground level.
- Footprints snap to the fine-cell grid; no freeform placement.
- Stage 3 previews are layout-accurate stand-ins, not production-faithful
  visuals.

Treat Minecraft CityGen as a structured city *assembler*, not a fully general procedural
urban simulator: it is strongest when the source world and asset kit follow the
expected conventions exactly.

## Running

GUI (installed entry point `citygen`, or from the repo):

```bash
pythonw application.pyw
```

Individual stages can be run directly from their script path, or as package
modules when `src/` is on `PYTHONPATH`; see the
[pipeline guide](pipeline/README.md#running-stages) for the full list and the
runtime configuration contract.

Generated outputs are intentionally kept outside source packages:

```text
artifacts/     previews, schematics, renders, exported worlds
build/ dist/   packaging outputs
.pytest_cache/ test-run cache
```

These directories are git-ignored and can be regenerated. Remove the generated
directories directly when you need a clean local run.

## Mental Model Summary

- Roads and buildings are extracted from explicit in-world markers, not inferred.
- The road network is two layered Manhattan systems: big coarse avenues plus
  small fine streets.
- Buildings are placed on the fine grid in two passes: type-2 first, then type-1.
- Preview and city construction share layout logic but render different assets.
- `buildings.json` is the bridge between extraction and placement.
- World export copies the source save, replaces its overworld region files, and
  recenters spawn/player onto the generated city.
