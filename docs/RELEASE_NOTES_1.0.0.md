# CityGen 1.0.0 Release Notes

Released on August 25, 2026.

CityGen 1.0.0 is the stable world-export release. In addition to the
WorldEdit-ready `.schem`, the app now exports a standalone Minecraft world that
opens directly on the generated city.

## Highlights

- **Standalone world export.** Build City now produces a ready-to-play world at
  `artifacts/saves/seed_<n>_world/`, centered on the city with the player spawn
  placed on solid ground.
- **One-click generation flow.** The old Render tab is now Generation; one click
  constructs the city schematic, renders the isometric preview, and exports the
  playable world.
- **Source-world-safe output.** Exported worlds are copied from the selected
  source save, then only the copied overworld region files are replaced with the
  generated city.
- **Better Minecraft compatibility.** Outputs are stamped with the source
  world's `DataVersion`, so Minecraft or WorldEdit can apply forward upgrades
  instead of skipping block rename fixes.

## What Changed

### World export

- Added pipeline stage 5 (`pipeline/05_world/world.py`) to convert the generated
  city schematic into a standalone Minecraft save.
- The export preserves the source world's native save structure, level metadata,
  dimensions, data packs, and non-overworld content.
- Region-directory discovery now prefers candidates that actually contain `.mca`
  files, so nested overworld layouts are handled correctly.
- The exporter rejects missing explicit source paths and overlapping
  source/output directories before deleting or rewriting output files.

### Schematic and asset fidelity

- Block entities are preserved through extraction, rotation, stacking, city
  assembly, and world export. Signs, banners, containers, beds, furnaces, skulls,
  and similar authored details keep their NBT.
- Extraction no longer blanks in-cuboid signs to air; authoring markers are
  stripped, but real signs inside captured structures remain content.
- Grown leaves are forced to `persistent=true` during extraction, preventing
  generated canopies from decaying after paste or world load.

### Version compatibility

- CityGen now follows a forward-only compatibility model: outputs target the
  selected source world's version or newer.
- The Target Version selector is informational. It helps users confirm their
  paste/load target but does not rewrite the schematic stamp.
- The render palette includes aliases for renamed block ids such as
  `minecraft:grass` and `minecraft:chain`, so older-world exports render without
  magenta placeholder blocks.

### Release artifacts

- The default release publishes both `CityGen-setup.exe` and
  `CityGen-portable-windows.zip`.
- The standalone one-file `CityGen.exe` remains an optional testing artifact via
  `python packaging/build_windows_release.py --clean --include-standalone`.

## Upgrade Notes

- Re-run extraction before generating final 1.0.0 outputs if your current
  artifacts were produced by an older build. This ensures block entities,
  persistent leaves, source `DataVersion`, and current road/building metadata
  are all present.
- If you use a custom source world, select the world folder itself or a valid
  region directory. CityGen now fails fast for missing or unsafe paths instead
  of falling back silently.

## Verification

- `python -m compileall -q src tests tools packaging`
- `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
- `$env:PYTHONPATH='src'; python -m pytest -q -p no:cacheprovider`
- `python packaging/build_windows_release.py --clean`
