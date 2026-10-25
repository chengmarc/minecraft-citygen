"""The three runs the tabs start: extract, preview, build."""
from __future__ import annotations

import os
import types
from pathlib import Path
from unittest import mock

import pytest
from PIL import Image

from citygen import step1_extract, step2_preview, step3_build
from citygen.tools import contact_sheet
from citygen.settings import ALGO, BlockRegion, BuildRegion


def _component(cuboid, *, ground_offset=0, emerald=(1, 64, 1)):
    return types.SimpleNamespace(
        cuboids=[cuboid], ground_offset=ground_offset, emerald=emerald, size=[3, 3], origin=[0, 0, 65],
    )


ROAD_BOX = BlockRegion(0, 15, 0, 15, 60, 80)


# --- extract

def test_road_pieces_are_named_by_their_sign_and_seated_by_their_ground_offset(tmp_path):
    component = _component((0, 2, 65, 70, 0, 2), ground_offset=2)
    with mock.patch.object(step1_extract, "ROADS_SCHEM", str(tmp_path)), \
            mock.patch.object(step1_extract, "detect_marker_assets", return_value=[component]), \
            mock.patch.object(step1_extract, "sign_text_above", return_value=" 02_big _2x2 _I "), \
            mock.patch.object(step1_extract, "extract_cuboid", return_value=([[["minecraft:stone"]]], [])), \
            mock.patch.object(step1_extract, "write_sponge_schem_cells") as write_schem:
        step1_extract.extract_roads(object(), ROAD_BOX, 4790, lambda *report: None)

    write_schem.assert_called_once()
    assert write_schem.call_args.args[1] == str(tmp_path / "02_big_2x2_I.schem")
    assert write_schem.call_args.kwargs["offset"] == (0, -2, 0)


def test_road_extraction_clears_the_last_runs_pieces_even_when_it_finds_none(tmp_path):
    stale = tmp_path / "stale.schem"
    stale.write_text("old", encoding="utf-8")
    with mock.patch.object(step1_extract, "ROADS_SCHEM", str(tmp_path)), \
            mock.patch.object(step1_extract, "detect_marker_assets", return_value=[]):
        with pytest.raises(RuntimeError, match="found no assets"):
            step1_extract.extract_roads(object(), ROAD_BOX, 4790, lambda *report: None)
    assert not stale.exists()


def test_an_area_counts_the_chunks_it_touches_partly_and_below_zero():
    assert BlockRegion.from_xyz_pair((-1, 0, 0), (16, 0, 15)).chunk_span() == (3, 1)


def test_extraction_reports_its_steps_in_order(monkeypatch, tmp_path):
    def fake_extract_roads(_world, _box, _version, progress):
        progress("scan_roads", 1, 1)
        progress("road_pieces", 1, 1)

    def fake_extract_builds(_world, _types, _version, progress):
        progress("scan_builds", 1, 1)
        progress("build_pieces", 1, 1)

    def fake_sheet(_items, _render_item, _out, _sheet, progress):
        progress(1, 1, "piece")

    monkeypatch.setattr(step1_extract, "World", lambda save: save)
    monkeypatch.setattr(step1_extract, "extract_roads", fake_extract_roads)
    monkeypatch.setattr(step1_extract, "extract_builds", fake_extract_builds)
    monkeypatch.setattr(step1_extract, "read_catalog", lambda _path: {})
    monkeypatch.setattr(step1_extract, "render_contact_sheet", fake_sheet)
    steps = []

    step1_extract.run(str(tmp_path), ROAD_BOX, (BuildRegion(1, ROAD_BOX),), lambda step, *_rest: steps.append(step))

    assert steps == ["scan_roads", "road_pieces", "road_sheet", "scan_builds", "build_pieces", "build_sheet"]


def test_contact_sheet_saves_each_piece_then_the_sheet_from_their_files(tmp_path):
    real_write_contact = contact_sheet.write_contact

    def checking_write_contact(images, out, **kwargs):
        assert all(isinstance(source, (str, os.PathLike)) for _key, source in images)
        return real_write_contact(images, out, **kwargs)

    named = []
    with mock.patch.object(contact_sheet, "write_contact", side_effect=checking_write_contact):
        contact_sheet.render_contact_sheet(
            ["a", "b"], lambda name: (name, Image.new("RGBA", (16, 16), (200, 40, 40, 255))),
            str(tmp_path), str(tmp_path / "_contact_sheet.png"),
            lambda _completed, _total, detail: named.append(detail),
        )

    assert (tmp_path / "a.png").exists() and (tmp_path / "b.png").exists()
    assert (tmp_path / "_contact_sheet.png").exists()
    assert [name for name in named if name] == ["a", "b"]   # each named once its PNG is there


# --- preview

def test_preview_writes_the_road_layout_before_the_city_layout(monkeypatch, tmp_path):
    catalog = {"001": {"type": 1, "size": [9, 9]}}
    monkeypatch.setattr(step2_preview, "read_catalog", lambda _path: catalog)
    monkeypatch.setattr(step2_preview, "grid_preview_path", lambda seed: str(tmp_path / "grid" / f"seed_{seed}.png"))
    monkeypatch.setattr(step2_preview, "city_preview_path", lambda seed: str(tmp_path / "city" / f"seed_{seed}.png"))
    reports = []

    def on_progress(step, completed, total):
        reports.append((step, completed >= total))
        if step == "road_layout" and completed >= total:
            assert (tmp_path / "grid" / "seed_3.png").exists()

    step2_preview.run(3, ALGO, on_progress)

    assert [step for step, _done in reports if _done] == ["road_pieces", "build_pieces", "road_layout", "city_layout"]
    with Image.open(tmp_path / "city" / "seed_3.png") as city, Image.open(tmp_path / "grid" / "seed_3.png") as grid:
        assert city.size == grid.size


# --- build

def test_build_constructs_renders_then_exports_into_a_world_named_for_its_seed(monkeypatch, tmp_path):
    calls = []

    def fake_construct(seed, algo, data_version, step):
        calls.append(("construct", seed, data_version))
        step(0)
        step(step3_build.CONSTRUCT_STEPS)

    def fake_schem_to_world(schem, out, **kwargs):
        calls.append(("world", Path(out).name, kwargs["world_name"], kwargs["source_world"]))
        kwargs["progress"](1, 1, "World saved")

    monkeypatch.setattr(step3_build, "construct", fake_construct)
    monkeypatch.setattr(step3_build, "source_data_version", lambda save: 4903)
    monkeypatch.setattr(step3_build, "render_schem_visible_iso", lambda path: Image.new("RGBA", (4, 4), (1, 2, 3, 255)))
    monkeypatch.setattr(step3_build, "city_render_path", lambda seed: str(tmp_path / f"seed_{seed}.png"))
    monkeypatch.setattr(step3_build, "schem_to_world", fake_schem_to_world)
    steps = []

    step3_build.run(12, ALGO, "source", lambda step, completed, total: steps.append((step, completed)))

    assert calls == [("construct", 12, 4903), ("world", "MC CityGen World 12", "MC CityGen World 12", "source")]
    assert (tmp_path / "seed_12.png").exists()
    assert steps[0] == ("construct", 0)
    assert [step for step, _completed in steps[-3:]] == ["render", "render", "world"]
