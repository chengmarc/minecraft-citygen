# CityGen Source Architecture

This is the engineering entry point for CityGen's source tree. It explains how the
app is structured and links out to a per-package guide for the details. Start
here, then follow the link into the package you care about.

CityGen turns a small, handcrafted asset set — roads and buildings marked up
inside a Minecraft world — into a complete, paste-ready city. Everything under
`src/` is one of four packages:

| Package | Responsibility | Guide |
|---|---|---|
| [`config/`](config/README.md) | Settings, tuning knobs, paths, version compatibility, the bundled world | [config guide](config/README.md) |
| [`engine/`](engine/README.md) | Pure generation & transforms: road networks, placement, schematic I/O, rendering | [engine guide](engine/README.md) |
| [`gui/`](gui/README.md) | PySide6 desktop app that drives the pipeline | [gui guide](gui/README.md) |
| [`pipeline/`](pipeline/README.md) | Numbered stages that orchestrate engine + config into artifacts | [pipeline guide](pipeline/README.md) |

The dependency direction is one-way: `gui` and `pipeline` depend on `engine` and
`config`; `engine` depends on `config`; `config` depends on nothing else in the
tree.

## High-Level Model

CityGen produces two parallel outputs from the same source assets:

- **simulation** — fast PNG previews for iteration
- **production** — real Sponge `.schem` output plus isometric renders for
  Minecraft use

Placement logic is shared between the two; only the rendered representation
differs. The project flow runs in four numbered stages:

```text
01 roads   -> road assets            (extract from world)
02 builds  -> building assets + catalog (extract from world)
03 grid    -> generated road network  (seed -> network)
04 city    -> roads + placed buildings (final assembly)
```

The core unit tying pixels to blocks is:

```text
1 fine cell = 9 simulation pixels = 9 production blocks
```

defined by `CELL = 9` in [config/algo.py](config/algo.py). `buildings.json`
(written by stage 02) is the bridge between extraction and placement.

## Requirements & Assumptions

- Python `>= 3.10`; runtime deps: `numpy`, `nbtlib`, `PySide6`, `Pillow`
  (optional `numba` for speed). Declared in [pyproject.toml](../pyproject.toml).
- Source world: Minecraft **Java Edition**, 1.18+ Anvil region/chunk format.
  Not a Bedrock pipeline; older world formats are not supported.
- Output: Sponge `.schem` (v3 container) plus standalone world exports. The
  supported floor is Minecraft **1.20**; versioning is **forward-only** — see
  the [config guide](config/README.md#version-compatibility).
- Local filesystem access to the Minecraft save and the export directory is
  assumed. A few GUI behaviors are Windows-oriented (e.g. `os.startfile`).

## Limitations

- Roads are orthogonal Manhattan-style only (no diagonals/curves); big roads are
  `2x2` fine cells, small roads `1x1`, mixed pieces `1x2` transverse crossings.
- Extraction depends on strict in-world marker conventions; malformed markers
  skip the build. Type `1` builds resolve to exactly 1 cuboid; type `2` to
  exactly 3 (`bottom`/`middle`/`top`).
- Footprints snap to the fine-cell grid; no freeform placement.
- Simulation previews are layout-accurate stand-ins, not production-faithful
  visuals.

Treat CityGen as a structured city *assembler*, not a fully general procedural
urban simulator: it is strongest when the source world and asset kit follow the
expected conventions exactly.

## Running

GUI (installed entry point `citygen`, or from the repo):

```bash
pythonw application.pyw
```

Individual stages can be run directly; see the
[pipeline guide](pipeline/README.md#running-stages) for the full list.

## Mental Model Summary

- Roads and buildings are extracted from explicit in-world markers, not inferred.
- The road network is two layered Manhattan systems: big coarse avenues plus
  small fine streets.
- Buildings are placed on the fine grid in two passes: type-2 first, then type-1.
- Simulation and production share layout logic but render different assets.
- `buildings.json` is the bridge between extraction and placement.
