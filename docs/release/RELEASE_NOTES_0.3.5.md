# CityGen 0.3.5 Release Notes

Released on August 20, 2026.

This release overhauls the extraction **region selector**. Its world preview is
now a true top-down surface map, rendered block-by-block at full resolution and
kept fast the way dedicated map tools do it.

## Highlights

- The region-selector preview is a real top-down surface map — the topmost block
  of each column — instead of the old thin altitude slice that painted most of
  the world flat green.
- It now renders **one pixel per block** (full resolution), yet stays fast by
  reading each chunk's precomputed surface heightmap rather than scanning columns.

## What Changed

### Region selector

- `render_topdown_preview` now derives each column's surface from the chunk's
  `WORLD_SURFACE` heightmap — a single array read per chunk replaces the previous
  per-column vertical scan, and the result no longer depends on the selection's
  Y bounds.
- Ungenerated columns render as a neutral background instead of fake grass fill.
- Colours come from each column's highest non-air block, using the corrected
  0.3.0 palette (green foliage, blue water).

### Performance

- The world reader reads each `.mca` region file once and caches its bytes, so
  all chunks in a region share a single read instead of re-opening the file.
- Per-chunk colour mapping is vectorized with NumPy (build a palette-to-RGB
  lookup once per section, gather all 256 columns at once).
- Worlds larger than the full-resolution cap are point-sampled from the same
  heightmaps so the image stays bounded.

### UI

- Removed the drop shadows from the region-selector dialog buttons ("Use
  Selection" / "Cancel"). The extraction "Pick" button keeps its shadow.

## New internals

- `World.surface_heightmap(cx, cz)` — decodes a chunk's `WORLD_SURFACE` heightmap
  to per-column surface heights.
- `World.top_solid_block(x, z)` — highest non-air block in a column (used as a
  fallback and for verification).

## Upgrade notes

- No configuration or output changes to generated schematics or renders. Only the
  region-selector preview is affected.

## Verification

- `python -m pytest`
- `python packaging/build_windows_release.py --clean`
- Open the Extraction tab, click **Pick**, and confirm the preview shows a
  block-by-block top-down surface map.
