# gui — PySide6 desktop app

A PySide6 (Qt) front end over the pipeline. It collects settings, runs stages on
background threads, shows previews and renders, and remembers the user's
settings. It has no generation logic of its own.

← Back to the [source architecture overview](../README.md).

## How-to guides

### Run the app

```bash
pythonw application.pyw          # from a checkout
citygen                          # installed
pythonw application.pyw --no-custom-theme --qt-style Windows
```

Arguments the app doesn't recognise are forwarded to `QApplication`, so Qt
platform flags work too.

### Expose an `Algo` knob in the form

Once the field exists on `Algo`
([config guide](../config/README.md#add-a-generation-knob)), in
[core/algo_config.py](core/algo_config.py):

1. Add `("<FIELD_UPPER>", "<Label>", "<tooltip>")` to `PREVIEW_CONFIGS`. The
   default comes from `config.algo.ALGO`.
2. Add the name to one of the `PREVIEW_CONFIG_GROUPS` — the advanced panel only
   builds widgets for grouped names.
3. For an integer, add a `(min, max)` slider range to `PREVIEW_SLIDER_RANGES`.
   A `frozenset` field needs its own branch in `build_algo_from_values` and in
   `_build_widget` ([widgets/widgets.py](widgets/widgets.py)), as
   `BANNED_BUILDINGS` has.

The Preview and Build tabs share one form state, so the knob shows up in both.

### Run a pipeline stage from a tab

Build the stage parameters from the widgets, then call
`pipeline.services.run_stage` inside a job passed to
`start_background_job` ([core/workers.py](core/workers.py)). See
`PreviewTab._run_preview` in [tabs/preview.py](tabs/preview.py) for the full
pattern. Only `pipeline.services` and `pipeline.stages` may be imported from
`gui/`; `tests/test_dependencies.py` rejects anything deeper.

### Re-tune a progress bar

Progress bars are weighted per step by hand in
[core/progress.py](core/progress.py). Extract and Build runs write measured
timings to `artifacts/progress_timings.json`; set the weights from those. Keep one weight
per step: `tests/test_gui.py` checks that the preview and construct weight lists
match the pipeline's steps, so adding a step fails the test until you add a
weight.

## Explanation

**The GUI never touches `os.environ` for a run.** Each tab passes its settings
(an `Algo`, the source save, the regions, the DataVersion) as stage
parameters. `MC_CITY_*` only sets the defaults the form starts with
([config guide](../config/README.md#defaults-are-read-once-per-run-settings-are-arguments)).

**Tabs follow the numbered pipeline.** Extract runs Stages 1–2, Preview runs
Stage 3, and Build runs Stage 4 then Stage 5. Preview and Build stay disabled
until both extraction contact sheets exist (`app_files.extracted_assets_ready`),
because every later stage reads the extracted assets.

**Every launch starts from a clean slate.** On startup, and when the user
switches source worlds, `app_files.clear_pipeline_artifacts` wipes
`artifacts/` except `05_world/saves/`. Extracted assets from a different world
can't leak into a new city, and exported worlds are never deleted.

**Preview and Build are peers.** Both edit the same seed and `Algo` form;
saving one pushes the state into the other (`AlgoTabMixin.set_peer` in
[tabs/_algo.py](tabs/_algo.py)), so the city you preview is the one you build.

**Version display only.** The Extract tab shows the source world's detected
Minecraft version and a Target Version selector. The selector doesn't change
what's written — see the
[config guide](../config/README.md#version-compatibility).

## Reference

```text
application.pyw  ->  gui.launcher:main  ->  gui.app  (QApplication + main window)
```

| Module | Responsibility |
|---|---|
| [launcher.py](launcher.py) | Installed `citygen` entry point (`gui-scripts`); routes to the Qt app |
| [app.py](app.py) | Main window, argument parsing, theme wiring, top-level error handling |
| **`core/`** | Non-widget support |
| [core/workers.py](core/workers.py) | `start_background_job` and progress mixins, so stage runs don't block the UI thread |
| [core/algo_config.py](core/algo_config.py) | The algorithm form: which knobs show, labels, ranges, form values → `Algo` |
| [core/extraction_config.py](core/extraction_config.py) | Extraction settings: default world and regions, version stamp and selector |
| [core/app_files.py](core/app_files.py) | Files the GUI owns (below), artifact cleanup, opening folders |
| [core/progress.py](core/progress.py) | Per-step progress weights and message formatting |
| [core/theme.py](core/theme.py) | Stylesheet, palette, widget decoration |
| **`widgets/`** | Custom widgets |
| [widgets/widgets.py](widgets/widgets.py) | Sliders, selectors, region editors, the algorithm form panels |
| [widgets/qt_viewer.py](widgets/qt_viewer.py) | Image viewers for previews and renders |
| [widgets/region_dialog.py](widgets/region_dialog.py) | World top-down preview for snapping a region to chunk boundaries |
| **`tabs/`** | The three tabs |
| [tabs/extraction.py](tabs/extraction.py) | **Extract**: source world, regions, road and building extraction |
| [tabs/preview.py](tabs/preview.py) | **Preview**: Stage 3 road-layout and city-layout previews |
| [tabs/generation.py](tabs/generation.py) | **Build**: Stage 4 schematic and render, Stage 5 world export |
| [tabs/control.py](tabs/control.py) | Action/control panels shared by the tabs |
| [tabs/_algo.py](tabs/_algo.py) | Saved state, peer sync, and prerequisite gating for Preview and Build |

Files the GUI writes (`ROOT` is the app root, see the
[config guide](../config/README.md#where-outputs-go)):

| Path | Contents |
|---|---|
| `ROOT/src/config/citygen.json` | Saved settings; a legacy `ROOT/citygen_saved_config.json` is migrated on load. Git-ignored |
| `ROOT/artifacts/progress_timings.json` | Measured Extract/Build step timings for weight tuning |
| `ROOT/artifacts/world_preview/` | Cached top-down world previews for the region dialog |
| `ROOT/application_startup_error.log` | Written if the app fails to start |

Opening an output folder uses `os.startfile` on Windows, `open` on macOS, and
`xdg-open` on Linux (`app_files.open_in_file_manager`).
