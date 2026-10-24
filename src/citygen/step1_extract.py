"""Step 1, the Extract tab's run: the marked road pieces and buildings, exported as ``.schem`` with their
contact sheets.
"""

from __future__ import annotations

import glob
import os
from pathlib import Path

from citygen.core.markers import detect_marker_assets, extract_cuboid, parse_range, sign_text_above
from citygen.paths import (
    BUILD_CATALOG, BUILDS_CONTACT_SHEET, BUILDS_RENDERS, BUILDS_SCHEM, ROADS_CONTACT_SHEET, ROADS_RENDERS, ROADS_SCHEM,
)
from citygen.settings import BUILD_MARKER_Y_RANGE
from citygen.tools.contact_sheet import render_contact_sheet
from citygen.tools.render_isometric import render_cells_visible_iso
from citygen.tools.catalog import assemble, new_entry, piece_path, read_catalog, STACK_PARTS, WHOLE, write_catalog
from citygen.tools.schem import decode_schem_cells, write_sponge_schem_cells
from citygen.tools.world_reader import source_data_version, World


def run(save, road_box, build_types, progress):
    """Extract the road pieces in ``road_box`` and the buildings in ``build_types``' regions of the ``save`` world, and
    render each set with its contact sheet.

    Every output is stamped with the source world's version (see ``source_data_version``). ``progress(step, completed,
    total, detail)`` reports each step by its code -- ``scan_roads``, ``road_pieces``, ``road_sheet``, ``scan_builds``,
    ``build_pieces``, ``build_sheet`` -- and a sheet step names each piece once its PNG is saved.
    """
    data_version = source_data_version(save)
    extract_roads(World(save), road_box, data_version, progress)
    render_contact_sheet(
        sorted(glob.glob(os.path.join(ROADS_SCHEM, "*.schem"))),
        lambda path: (Path(path).stem, render_cells_visible_iso(decode_schem_cells(path))),
        ROADS_RENDERS, ROADS_CONTACT_SHEET,
        lambda completed, total, detail: progress("road_sheet", completed, total, detail),
    )
    extract_builds(World(save), build_types, data_version, progress)
    catalog = read_catalog(BUILD_CATALOG)
    render_contact_sheet(
        sorted(catalog),
        lambda key: (key, render_cells_visible_iso(assemble(BUILDS_SCHEM, key, 1, catalog).cells)),
        BUILDS_RENDERS, BUILDS_CONTACT_SHEET,
        lambda completed, total, detail: progress("build_sheet", completed, total, detail),
    )


def chunk_scan_count(x0, x1, z0, z1):
    """Number of region chunks touched by an x/z block rectangle."""
    return ((max(x0, x1) >> 4) - (min(x0, x1) >> 4) + 1) * ((max(z0, z1) >> 4) - (min(z0, z1) >> 4) + 1)


def clear_schems(directory):
    """Make ``directory`` and delete the last run's ``.schem`` files from it."""
    os.makedirs(directory, exist_ok=True)
    for filename in os.listdir(directory):
        if filename.endswith(".schem"):
            os.remove(os.path.join(directory, filename))


def extract_roads(world, road_box, data_version, progress):
    """Each marked road piece and fill prop, as ``<the name on its sign>.schem``."""
    clear_schems(ROADS_SCHEM)
    progress("scan_roads", 0, chunk_scan_count(road_box.x0, road_box.x1, road_box.z0, road_box.z1))
    components = detect_marker_assets(
        world, road_box.x0, road_box.x1, road_box.z0, road_box.z1, BUILD_MARKER_Y_RANGE,
        on_progress=lambda done, total: progress("scan_roads", done, total),
    )
    extracted = 0
    total = len(components)
    for index, comp in enumerate(components, start=1):
        progress("road_pieces", index - 1, total)   # before its (slow) extraction
        name = sign_text_above(world, comp.emerald).replace(" ", "").strip()
        if name and len(comp.cuboids) == 1:   # a road piece has one layer, and a sign naming it
            cells, block_entities = extract_cuboid(world, comp.cuboids[0])
            write_sponge_schem_cells(
                cells, os.path.join(ROADS_SCHEM, name + ".schem"), data_version,
                offset=(0, -comp.ground_offset, 0), block_entities=block_entities,
            )
            extracted += 1
        progress("road_pieces", index, total)
    if not extracted:
        raise RuntimeError(
            "Road extraction found no assets in the configured region. "
            "Check the road bounds or the bundled default world content."
        )


def extract_builds(world, build_types, data_version, progress):
    """Each marked building as its pieces' ``.schem`` files, and the catalog of them all (``buildings.json``)."""
    clear_schems(BUILDS_SCHEM)
    regions = [region.bounds for region in build_types]
    chunk_counts = [chunk_scan_count(r.x0, r.x1, r.z0, r.z1) for r in regions]
    total_chunks = sum(chunk_counts)
    progress("scan_builds", 0, total_chunks)
    builds = []
    for index, (region_type, r) in enumerate(zip((region.build_type for region in build_types), regions)):
        offset = sum(chunk_counts[:index])
        components = detect_marker_assets(
            world, r.x0, r.x1, r.z0, r.z1, BUILD_MARKER_Y_RANGE,
            on_progress=lambda done, _total, _offset=offset: progress("scan_builds", _offset + done, total_chunks),
        )
        builds.extend((region_type, component) for component in components)

    catalog = {}
    total = len(builds)
    for index, (build_type, comp) in enumerate(builds):
        key = f"{index + 1:03d}"
        progress("build_pieces", index, total)   # before its (slow) extraction
        stack = None
        if len(comp.cuboids) == 1:
            parts = (WHOLE,)
        else:
            parts = STACK_PARTS
            stack = parse_range(sign_text_above(world, comp.emerald), (r"stack\s*:\s*",))
        pieces = {}
        for part, cuboid in zip(parts, comp.cuboids):
            cells, block_entities = extract_cuboid(world, cuboid)
            write_sponge_schem_cells(cells, piece_path(BUILDS_SCHEM, key, part), data_version, block_entities=block_entities)
            pieces[part] = cuboid[3] - cuboid[2] + 1
        catalog[key] = new_entry(build_type, comp.size, comp.origin, comp.ground_offset, pieces, stack)
        progress("build_pieces", index + 1, total)
    write_catalog(catalog, BUILD_CATALOG)
