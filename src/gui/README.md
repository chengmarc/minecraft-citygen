# gui — PySide6 desktop app

The GUI is a PySide6 (Qt) desktop front-end over the pipeline. It runs stages in
background threads via [`pipeline.services`](../pipeline/README.md), shows
previews and renders, and persists the user's settings. It contains no generation
logic of its own — it configures and launches [engine](../engine/README.md) work
through the [pipeline](../pipeline/README.md).

← Back to the [source architecture overview](../README.md).

## Entry point

```text
application.pyw  ->  gui.launcher:main  ->  gui.app  (QApplication + main window)
```

`citygen` (the installed `gui-scripts` entry) resolves to `gui.launcher:main`.

## Modules

| Module | Responsibility |
|---|---|
| [launcher.py](launcher.py) | Installed GUI entry point; routes to the Qt app |
| [app.py](app.py) | PySide6 host shell: main window, arg parsing, theme wiring, top-level error handling |
| `tabs/` | The three main tabs: **Extract**, **Preview**, **Build** |
| `core/` | Non-widget GUI support (below) |
| `widgets/` | Custom input and viewer widgets (below) |

`core/`:

- [workers.py](core/workers.py) — background-worker signals and progress-bar
  mixins so stage runs don't block the UI thread.
- [theme.py](core/theme.py) — application styling: stylesheet, palette, and
  widget-decoration helpers.
- [algo_config.py](core/algo_config.py) — the algorithm settings form: which
  knobs the Preview/Build tabs show, their defaults, and the algo-value ↔
  `MC_CITY_*` env mapping.
- [extraction_config.py](core/extraction_config.py) — extraction settings:
  default source world and asset regions, and the version stamp/selector.
- [app_files.py](core/app_files.py) — files the GUI owns on disk: icons, the
  saved GUI config (`citygen.json`), progress timings, and artifact cleanup.
- [progress.py](core/progress.py) — progress-message formatting shared by
  worker-driven tabs.

`widgets/`:

- [widgets.py](widgets/widgets.py) — custom inputs for the algorithm and
  extraction tabs (sliders, combo controls, region editors).
- [qt_viewer.py](widgets/qt_viewer.py) — reusable image-viewer widgets for
  previews and renders.
- [region_dialog.py](widgets/region_dialog.py) — interactive world-preview dialog
  for snapping an extraction region to chunk boundaries (uses
  [`engine.render.topdown`](../engine/README.md#rendering)).

`tabs/`:

- [_algo.py](tabs/_algo.py) — shared saved-state, peer-sync, and prerequisite
  gating helper for the preview and generation tabs.
- [control.py](tabs/control.py) — shared action/control panels for extraction
  and build workflows.
- [extraction.py](tabs/extraction.py) — source-world selection, region editing,
  and road/building extraction.
- [preview.py](tabs/preview.py) — Stage 3 fast road-layout and city-layout previews.
- [generation.py](tabs/generation.py) — Stage 4 production schematic/render plus
  Stage 5 standalone world export.

## How it drives the pipeline

- The tabs collect settings into `MC_CITY_*` env overrides and call
  [`pipeline.services.run_stage`](../pipeline/README.md) from background workers,
  streaming progress back to the UI through the `workers` mixins.
- The user-facing tab order maps to the numbered pipeline: Extract runs
  Stages 1 and 2, Preview runs Stage 3, and Build runs Stage 4
  followed by Stage 5.
- The GUI passes only explicit `MC_CITY_*` overrides into `pipeline.services`,
  which owns temporary environment mutation/reload/restore; GUI code should
  not set process environment variables directly for a stage run.
- The Extraction tab detects and displays the source world's Minecraft version and
  offers the Target Version selector (see the
  [config guide](../config/README.md#version-compatibility)).
- User settings persist to `citygen.json` via `app_files.save_saved_gui_config` /
  `load_saved_gui_config`.

## Platform notes

Opening the output folder uses the platform file manager: `os.startfile(...)` on
Windows, `open` on macOS, and `xdg-open` on Linux.
