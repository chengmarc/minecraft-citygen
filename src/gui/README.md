# gui — the desktop app

An HTML page in a native window (WebView2, through
[pywebview](https://pywebview.flowrl.com/)), over the pipeline. The page draws the
three tabs; Python collects settings, runs stages on background threads, and
remembers the user's settings. It has no generation logic of its own.

← Back to the [source architecture overview](../README.md).

## How-to guides

### Run the app

```bash
pythonw src/application.pyw      # from a checkout
citygen                          # installed
pythonw src/application.pyw --debug  # with the page's developer tools (F12)
```

### Expose an `Algo` knob in the form

Once the field exists on `Algo`
([config guide](../config/README.md#add-a-generation-knob)), in
[algo.py](algo.py):

1. Add `("<FIELD_UPPER>", "<Label>", "<tooltip>")` to `PREVIEW_CONFIGS`. The
   default comes from `config.algo.ALGO`.
2. Add the name to one of the `PREVIEW_CONFIG_GROUPS` — the advanced panel only
   builds fields for grouped names.
3. For an integer, add a `(min, max)` slider range to `PREVIEW_SLIDER_RANGES`.
   A `frozenset` field needs its own branch in `build_algo_from_values` and in
   `form_spec`, as `BANNED_BUILDINGS` has.

The page builds the form from `form_spec`, so there's no HTML to change. The
Preview and Build tabs share one form state, so the knob shows up in both.

### Run a pipeline stage from a tab

Add a method to [bridge.py](bridge.py)'s `Api`, which the page calls as
`window.pywebview.api.<name>(...)`. Build the stage parameters, then call
`pipeline.services.run_stage` inside a job passed to `Runner.start`
([session.py](session.py)), which reports progress and the result to
the page as events. See `AlgoTabs.run_preview` in [algo.py](algo.py) for
the full pattern. Only `pipeline.services` and `pipeline.stages` may be imported
from `gui/`; `tests/test_dependencies.py` rejects anything deeper.

### Re-tune a progress bar

Progress bars are weighted per step by hand in
[progress.py](progress.py). Extract and Build runs write measured
timings to `appdata/progress_timings.json`; set the weights from those. Keep one weight
per step: `tests/test_gui_web.py` checks that the preview and construct weight lists
match the pipeline's steps, so adding a step fails the test until you add a
weight.

## Explanation

**Python owns the state; the page draws it and words it.** The saved settings,
the prerequisite gates, and every run live in Python, which answers with facts
and short codes (`{"code": "running"}`, a chunk count, the pipeline's own step
names); every other word the page shows is in [static/text.js](static/text.js). The page calls the bridge and
redraws from what it answers, or from the events a run sends: `progress`,
`done`, `failed`, and `finished`, each naming its tab, through
`citygen.receive(event, payload)`. [bridge.py](bridge.py) imports
nothing from pywebview, so `tests/test_gui_web.py` exercises it without a window.

**The page is served, not loaded from disk.** [server.py](server.py) is
a small WSGI app that pywebview runs on 127.0.0.1: the page from `static/`,
its icons included, and previews and renders from `appdata/` by URL,
each with its modification time in the URL so a new run never shows a stale image.

**The GUI never touches `os.environ` for a run.** Each tab passes its settings
(an `Algo`, the source save, the regions, the DataVersion) as stage
parameters. `MC_CITY_*` only sets the defaults the form starts with
([config guide](../config/README.md#defaults-are-read-once-per-run-settings-are-arguments)).

**Tabs follow the numbered pipeline.** Extract runs Stages 1–2, Preview runs
Stage 3, and Build runs Stage 4 then Stage 5. Preview and Build stay disabled
until both extraction contact sheets exist (`files.extracted_assets_ready`),
because every later stage reads the extracted assets.

**Every launch starts from a clean slate.** On startup, and when the user
switches source worlds, `files.clear_pipeline_artifacts` wipes
`appdata/` except `05_world/saves/` and the saved settings. Extracted assets from a different world
can't leak into a new city, and exported worlds are never deleted.

**Preview and Build are peers.** Both edit the same seed and `Algo` form; a
change in one is copied into the other and saved, so the city you preview is
the one you build.

**Version display only.** The Extract tab shows the source world's detected
MC version and a Target Version selector. The selector doesn't change
what's written — see the
[config guide](../config/README.md#version-compatibility).

**WebView2 or nothing.** Without the WebView2 Runtime, pywebview falls back to
Internet Explorer's engine, which can't run the page, so the app checks first
and offers the download page instead. WebView2 comes with Windows 11 and most of
Windows 10.

## Reference

```text
src/application.pyw  ->  gui.app:main  (window + server + bridge)  ->  static/ (the page)
```

| Module | Responsibility |
|---|---|
| [app.py](app.py) | Process entry (`citygen`, and the release build's script): arguments, the WebView2 check, the window and its title bar, top-level error handling |
| [server.py](server.py) | What the page can load: itself, the app icon, files under `appdata/` |
| [bridge.py](bridge.py) | `Api`: every call the page makes |
| [session.py](session.py) | Saved settings, and background runs that report to the page |
| [extract.py](extract.py) | **Extract**: source world, sample areas and their defaults, the version selector, the region map's cached world preview, Stages 1–2 |
| [algo.py](algo.py) | **Preview** (Stage 3) and **Build** (Stages 4–5): the algorithm form, form values → `Algo` |
| [progress.py](progress.py) | Per-step progress weights, milestones, run-bar segments, and timing records |
| [files.py](files.py) | Files the GUI owns (below), artifact cleanup, opening folders |
| [static/](static/) | The page: `index.html`, `app.css` (the colours), `text.js` (the words), `components.js`, `region.js`, `app.js`, and the button icons, SVGs in `icons/` |

Files the GUI writes (`ROOT` is the app root, see the
[config guide](../config/README.md#where-outputs-go)):

| Path | Contents |
|---|---|
| `ROOT/appdata/citygen.json` | Saved settings. Git-ignored |
| `ROOT/appdata/progress_timings.json` | Measured Extract/Build step timings for weight tuning |
| `ROOT/appdata/world_preview/` | Cached top-down world previews for the region map |
| `ROOT/application_startup_error.log` | Written if the app fails to start |

Opening an output folder uses `os.startfile` on Windows, `open` on macOS, and
`xdg-open` on Linux (`files.open_in_file_manager`).
