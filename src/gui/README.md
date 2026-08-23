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
| [tabs.py](tabs.py) | The three main tabs: **Extraction**, **Preview**, **Render** |
| `core/` | Non-widget GUI support (below) |
| `widgets/` | Custom input and viewer widgets (below) |

`core/`:

- [workers.py](core/workers.py) — background-worker signals and progress-bar
  mixins so stage runs don't block the UI thread.
- [theme.py](core/theme.py) — application styling: stylesheet, palette, and
  widget-decoration helpers.
- [common.py](core/common.py) — shared constants and non-widget helpers: loading
  and saving the GUI config (`citygen.json`), default tab configs, algo-value ↔
  env mapping, and version display helpers.

`widgets/`:

- [widgets.py](widgets/widgets.py) — custom inputs for the algorithm and
  extraction tabs (sliders, combo controls, region editors).
- [qt_viewer.py](widgets/qt_viewer.py) — reusable image-viewer widgets for
  previews and renders.
- [region_dialog.py](widgets/region_dialog.py) — interactive world-preview dialog
  for snapping an extraction region to chunk boundaries (uses
  [`engine.render.topdown`](../engine/README.md#rendering)).

## How it drives the pipeline

- The tabs collect settings into `MC_CITY_*` env overrides and call
  [`pipeline.services`](../pipeline/README.md) functions from background workers,
  streaming progress back to the UI through the `workers` mixins.
- The Extraction tab detects and displays the source world's Minecraft version and
  offers the Target Version selector (see the
  [config guide](../config/README.md#version-compatibility)).
- User settings persist to `citygen.json` via `common.save_saved_gui_config` /
  `load_saved_gui_config`.

## Platform notes

A few behaviors are Windows-oriented — most notably opening the output folder via
`os.startfile(...)`.
