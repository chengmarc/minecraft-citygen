# Changelog

All notable changes to this project should be documented in this file.

The format is based on Keep a Changelog, and versions should match the release version you publish.

## [Unreleased]

### Added

- block entities are now preserved through extraction and city assembly: signs
  (text), banners, chests/barrels (contents), beds, furnaces, skulls, etc. keep
  their NBT in the output schematic instead of pasting as empty blocks. Positions
  follow their blocks through rotation, stacking, and composition, and the NBT is
  upgraded forward by WorldEdit's DataFixer like block ids (source-stamped)

### Changed

- extraction no longer blanks signs to air; the gold/diamond/emerald authoring
  markers live outside the extracted cuboid, so in-cuboid signs are real content
- both extractors now force grown leaves to `persistent=true` so exported
  canopies (cherry especially) do not decay after a paste
- committed to forward-only version compatibility: the export target is always
  the source world's version or newer, so WorldEdit's forward upgrade covers
  every block and no backward-compat machinery is needed
- output schematics are now always stamped with the **source** world's
  `DataVersion` so WorldEdit's DataFixer upgrades them forward on paste; the
  Target Version selector is informational only and no longer changes the stamp

### Fixed

- picking a target version newer than the source no longer stamps the schematic
  with that newer version (which skipped the DataFixer and holed out blocks
  renamed since the source, e.g. `grass` → `short_grass`)

### Removed

- the block-rename/downgrade path (`downgrade_block`, `BLOCK_RENAMES`), the
  per-block minimum-version map, and the `compatibility_report` "missing block"
  warnings across the GUI and pipeline — all unreachable under forward-only
  targeting
- `src/config/block_versions.json` and the block-registry half of the refresh
  tool; `tools/update_block_versions.py` is now `tools/update_mc_versions.py`,
  a release-table scrape that no longer needs a Java runtime or the vanilla
  data generator

## [0.4.1] - 2026-08-20

This is a patch release for the extracted-asset ground offset refactor. Building
placement already read the authored `ground_offset`; this release extends that
same offset path to roads and fill props so every marker-authored asset seats
from extracted metadata instead of assuming a hard-coded flush origin.

### Changed

- road and fill schematics now persist their authored ground offset in the
  Sponge `Offset` field during extraction
- the road-grid build preserves that shared road offset when exporting the
  combined grid schematic

### Fixed

- city construction no longer hard-codes `0` as the seating offset for roads
  and trees; both now read the extracted asset offset
- rotated fill props retain their authored ground offset instead of dropping
  back to a flush placement assumption

### Upgrade notes

- re-run road extraction before rebuilding grid or city outputs, otherwise
  previously exported road/fill schematics will still carry the old zero offset

## [0.4.0] - 2026-08-21

This release fills the empty space between roads and buildings with scatter props
(trees in the bundled world) and unifies road extraction with the building
marker convention.

### Added

- fill props: a set of self-contained one-cell (9x9) assets that carry their own
  ground and are dropped into every empty non-road lot cell of the generated
  city, chosen at random and randomly rotated (the bundled world ships three
  trees: `15_fill_1x1_A`/`B`/`C`)
- the top-down simulation preview draws matching fill-prop tiles into the same
  empty cells with the same seed, so the preview lines up with the built city
- `engine/marker_extract.py`: the shared wool-boundary + gold/diamond/emerald
  cuboid extraction now used by both the road/fill and building extractors

### Changed

- road extraction now uses the exact same marker convention and geometry pass as
  buildings (author road tiles like a type-1 build: wool boundary +
  gold/diamond/emerald + a name sign); the bespoke surface-scan / wool-strip /
  Y-extent road detection is gone
- the default empty-lot ground fill is now `smooth_stone_slab[type=bottom]`
  instead of a full `smooth_stone` block

### Fixed

- tall road and fill assets are no longer truncated to the `ROAD_BOX` Y span —
  the marker cuboid (gold→diamond) is captured in full
- fill props seat flush with the lot surface instead of hovering one block above
  it, and the flat ground fill no longer pokes a block up through a prop's cell

## [0.3.5] - 2026-08-20

This release overhauls the extraction region selector's world preview.

### Changed

- the region-selector preview is now a true top-down surface map (topmost block per column) built from each chunk's `WORLD_SURFACE` heightmap, instead of a thin altitude slice tied to the selection's Y bounds
- it renders one pixel per block (full resolution); ungenerated columns show a neutral background instead of fake grass
- removed the drop shadows from the region-selector dialog buttons (the extraction "Pick" button keeps its shadow)

### Performance

- region `.mca` files are read once and cached, so all chunks in a region share a single read
- per-chunk colour mapping is vectorized with NumPy; larger worlds are point-sampled from the same heightmaps

### Added

- `World.surface_heightmap` and `World.top_solid_block` in the Anvil reader, with tests

## [0.3.0] - 2026-08-20

This release follows up the Tkinter-to-Qt migration with a structural cleanup of
the GUI layer and surrounding tooling.

### Changed

- split the monolithic `gui/qt_app.py` into focused modules (`theme`, `workers`, `widgets`, `region_dialog`, `tabs`, `app`) and flattened the Qt image-viewer factory into module-level classes with a direct PySide6 import
- gave `QtImageViewer` a public overlay API so the region-selector dialog no longer reaches into private members
- replaced string-matched error handling with typed `SeedError`/`ConfigError`, and the hand-rolled argument loop with `argparse` (adds `--help` and a real `--no-custom-theme` flag)
- centralized the brand palette and the label-to-value selector mapping, and made the button-icon helper idempotent
- moved `clear_cache.py` into `tools/` and expanded it to also clear `build/`, `dist/`, `*.egg-info/`, `.pytest_cache/`, and the startup error log
- deduplicated `numba` across the `speed`/`build` dependency extras

### Removed

- removed the WorldEdit auto-copy step and the `MC_CITY_WORLDEDIT_SCHEM` override; the final city schematic is still written to `artifacts/city/production/` as a WorldEdit-ready `.schem`
- deleted dead code left over from the Tkinter era (unused arguments, duplicated helpers, stale flags, and unreachable region/format branches)

### Fixed

- replaced the deprecated `QFontDatabase()` instance call with the static form
- corrected stale “Tkinter” references in entry-point docstrings and comments

### Added

- headless GUI unit tests covering argument parsing, style configuration, and widget value round-trips

## [0.2.1] - 2026-08-20

This is a hot-fix release for the Windows installer build. There are no changes
to application code or generated output.

### Fixed

- fixed the frozen Windows build failing to start with `invalid command name "::msgcat::mcmset"`: the PyInstaller Tcl/Tk hook now bundles the Tcl 8.x module tree (`tcl8/`), which contains `msgcat` and other `.tm` packages that ship alongside — not inside — the `tcl8.6/` script directory. `ttkbootstrap`'s localization requires msgcat 1.6+ at startup.

## [0.2.0] - 2026-08-20

This is an internal refactor and maintenance release. There are no intended
changes to generated output: the city constructor was verified to produce
byte-identical results (decoded) against the previous implementation.

### Changed

- reorganized the monolithic GUI widgets module into focused submodules (image viewer, region-selector dialog, buttons/sliders, tooltip, progress, extraction panel, config frame) and extracted a shared pan/zoom base for the two viewers
- decomposed the city constructor into named stages and renamed terse identifiers, including the `Tile` dimension fields, for readability
- standardized path construction on `pathlib`, applied `from __future__ import annotations` uniformly, replaced initial-only aliased imports with explicit names, and unified the logger call contract to a single string
- replaced the mutable theme module globals with a single theme object
- made the per-user data directory platform-aware (macOS and Linux conventions) instead of Windows-only
- added upper version bounds to declared dependencies
- documented the pipeline environment-override and module-reload invariant

### Fixed

- narrowed overly broad exception handlers that could mask real failures, while keeping the intended top-level and worker error boundaries
- corrected stale file references and machine-specific absolute links in `docs/TECHNICAL.md`

## [0.1.0] - 2026-08-19

### Added

- installable project metadata and command entry points for the GUI and environment doctor
- a bundled default Minecraft world that ships with the app
- Windows installer build pipeline with PyInstaller, Inno Setup, and local packaging hooks for Tcl/Tk
- installer-only release flow with a documented Windows release command
- release support docs in `README.md`, plus this changelog and `RELEASING.md`
- regression tests for path discovery and isometric renderer fallback behavior

### Changed

- hard-coded machine-specific default paths were replaced with bundled defaults and explicit environment overrides
- frozen builds now package Tcl/Tk explicitly instead of relying on PyInstaller's broken auto-detection on this Python install
- the isometric renderer now works without `numba`, while using CPU `numba` acceleration when it is available
- release artifacts are now published to `dist/release`, with `CityGen-setup.exe` as the primary deliverable

### Fixed

- missing runtime dependencies in project metadata
- Windows-only output-folder behavior replaced with a cross-platform helper
- clearer extraction errors when the configured world path is missing
- packaged app startup failure caused by missing `tkinter` in the frozen build
