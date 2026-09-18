# Minecraft CityGen 1.2.0 Release Notes

Released on September 19, 2026.

Minecraft CityGen 1.2.0 is a reliability and maintenance release. The preview
and the final build now share one placement path, so what you preview is what
gets built. The first extraction no longer appears to stall, and a handful of
rendering and block-copy bugs are fixed. Most of the remaining work is internal:
clearer module ownership, dependency rules enforced by tests, less dead code,
and restructured documentation. The Windows installer and portable zip are
still the only release artifacts.

## Highlights

- **Preview matches the build.** Stage 3 preview and Stage 4 build call the
  same placement entry point with the same seeded random streams, and both
  round odd grid sizes down to even.
- **Smoother first extraction.** The GUI compiles the `numba` renderer in the
  background at launch, so the first extraction no longer sits near 6% while it
  compiles. The build-render progress bar now counts the showcase GIF and
  reaches 100% when the output is actually ready.
- **Rendering and block fixes.** The road contact sheet no longer cuts off fill
  props, `cave_air`/`void_air` are no longer copied into city grids, and mixed
  preview road tiles render the same way on every run.

## What Changed

### GUI and workflow

- Generation settings are passed to each stage as arguments instead of through
  `MC_CITY_*` environment overrides.
- Preview progress is reported per step module.
- The renderer is compiled in the background at launch.

### Pipeline and engine

- `plan_city()` is the single placement entry point for preview and build.
- Stage 4 render renders only the requested seed, not every `.schem` on disk.
- Extraction opens the world per run instead of caching it for the whole
  process.
- Block states, artifact paths, road tiles, and city voxel composition each
  have a single owner module. Tests now enforce the dependency rules between
  layers.
- Removed dead code: unused ground detection, no-op placement rule hooks, GUI
  pass-through wrappers, region env serializers, and parameters no caller
  overrides.
- The world writer's standalone CLI is gone. World export runs through
  `pipeline.stages world`.

### Documentation and packaging

- Restructured the source, engine, pipeline, GUI, and config READMEs into
  tutorial, how-to, explanation, and reference sections.
- The release runbook lives at `docs/RELEASING.md`.
- A test keeps the packaging hidden imports in step with the pipeline stage
  registry.

## Upgrade Notes

- Seeds from 1.1.0 use the same random formulas, so existing seeds should still
  give the same layouts. If you need byte-identical outputs, re-run extraction
  and generation with 1.2.0 instead of mixing artifacts from both versions.
- If you called the world writer module directly, use
  `python -m pipeline.stages world` instead.
- Publish only the curated artifacts:
  `Minecraft CityGen-setup.exe` and `Minecraft CityGen-portable-windows.zip`.

## Verification

- `python -m pytest -q`
- `python packaging/build_windows_release.py --clean`
