# Minecraft CityGen 1.1.0 Release Notes

Released on September 15, 2026.

Minecraft CityGen 1.1.0 makes building authoring more flexible by decoupling
layer count from placement type. A building can now be a one-layer or
three-layer asset independently of whether it is a repeatable type-1 building or
a unique type-2 landmark. This release also refreshes the public project
presentation, simplifies the GUI and pipeline control flow, updates the bundled
default world, and keeps the Windows installer plus portable zip as the curated
release artifacts.

## Highlights

- **Building layers and placement types are independent.** One-layer and
  three-layer assets can now be authored as either type-1 repeatable buildings
  or type-2 landmarks. Type controls placement behavior; layer count controls
  whether the asset is exported as a whole schematic or bottom/middle/top
  stackable pieces.
- **Updated bundled world.** The default world and marker extraction workflow
  have been refreshed for the current independent type/layer authoring path.
- **Cleaner generation controls.** Pipeline execution and GUI controls now flow
  through shared stage services, centralized progress reporting, and a dedicated
  Control tab.
- **Renderer consistency.** `numba` is now a required dependency, so release
  builds use the accelerated rendering path by default.
- **Refreshed identity.** The app now has the Minecraft CityGen branding pass,
  updated icon assets, README badges, current download links, and a reorganized
  screenshot/GIF gallery.

## What Changed

### Building authoring

- Decoupled building placement type from extracted layer count.
- Type-1 and type-2 now describe placement behavior: type-1 catalog IDs may
  repeat, while type-2 catalog IDs are placed once as landmarks.
- One-layer and three-layer now describe asset assembly: one-layer builds export
  as a complete schematic, while three-layer builds export bottom/middle/top
  pieces and can vary height by repeating the middle piece.
- Updated the bundled default world and marker workflow around the independent
  type/layer model.

### GUI and workflow

- Added a Control tab for centralized generation settings.
- Refined action controls, preview defaults reset behavior, seed randomization,
  export naming, and Qt theme polish.
- Consolidated worker progress handling into shared GUI core support.

### Pipeline and engine

- Simplified stage orchestration around shared services and preview-stage
  modules.
- Split extraction and rendering helpers into clearer pipeline support modules.
- Optimized top-down preview reads with heightmap-backed world access.
- Removed legacy configuration modules, stale package initializers, and older
  pipeline/test/tool surfaces no longer used by the current flow.

### Documentation and packaging

- Rebuilt the README around the current Minecraft CityGen brand, screenshots,
  asset showcases, and release links.
- Explicitly included the numbered pipeline stage modules in Windows release
  bundles, so frozen extraction can import `pipeline.01_roads` and the rest of
  the stage packages at runtime.
- Moved historical release notes under `docs/release/`.
- Tightened the release checklist to publish only the installer and portable zip
  from `dist/release`.

## Upgrade Notes

- Re-run extraction with the 1.1.0 build before producing final outputs from
  older artifacts. Building type and layer count are now independent, and fresh
  catalog metadata is the safest path.
- For release builds, use the curated artifacts only:
  `Minecraft CityGen-setup.exe` and `Minecraft CityGen-portable-windows.zip`.

## Verification

- `python -m compileall -q src application.pyw packaging`
- `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest discover -s tests`
- `python -m pytest -q`
- `python packaging/build_windows_release.py --clean`
