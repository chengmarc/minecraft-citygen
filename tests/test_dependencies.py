"""The source tree's import graph stays a layered DAG.

Reads every module under ``src/`` with ``ast`` (nothing is imported) and checks
the three dependency rules: packages -- and the parts inside each package --
only import downward, no module-level cycles, and imports land on public names
only. A string literal naming an in-tree module (``importlib.import_module``
targets such as the stage registry's step modules) counts as an import.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

# Lower layers never import higher ones; a package may import itself.
LAYERS = {"config": 0, "engine": 1, "pipeline": 2, "gui": 3}

# Layers inside each package, keyed by the first name under it. A part may import
# itself or a strictly lower layer, so parts sharing a layer (the numbered pipeline
# stages) never import each other. Every module must belong to a listed part.
PART_LAYERS = {
    "config": {"env": 0, "render": 0, "path": 1, "algo": 1, "world": 2, "doctor": 3},
    "engine": {"blocks": 0, "core": 0, "schematic": 1, "world": 2, "render": 3},
    "pipeline": {
        "step": 0,
        "extraction": 1,
        "rendering": 1,
        "01_roads": 2,
        "02_builds": 2,
        "03_preview": 2,
        "04_city": 2,
        "05_world": 2,
        "stages": 3,
        "services": 4,
    },
    "gui": {"core": 0, "widgets": 1, "tabs": 2, "app": 3, "launcher": 4},
}

# This process's per-run defaults, read from MC_CITY_* overrides. The engine takes
# these settings as arguments; only the pipeline and GUI fall back on the defaults.
PER_RUN_DEFAULTS = {
    "config.algo": {"ALGO"},
    "config.world": {"SAVE", "REGION_DIR", "REGION_DIR_CANDIDATES", "DATA_VERSION", "ROAD_BOX", "BUILD_TYPES"},
}

# The only pipeline modules the GUI may use: the stage registry and its runner.
PIPELINE_ENTRY_POINTS = {"pipeline.stages", "pipeline.services"}


def _module_name(path):
    return ".".join(path.relative_to(SRC).with_suffix("").parts)


MODULES = {_module_name(path): path for path in SRC.rglob("*.py")}


def _imports(name, path):
    """Yield ``(target_module, imported_name_or_None)`` for each in-tree import."""
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in LAYERS:
                    yield alias.name, None
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = name.split(".")[:-node.level]
                target = ".".join(base + ([node.module] if node.module else []))
            else:
                target = node.module or ""
            if target.split(".")[0] not in LAYERS:
                continue
            for alias in node.names:
                submodule = f"{target}.{alias.name}"
                if submodule in MODULES:
                    yield submodule, None
                else:
                    yield target, alias.name
        elif isinstance(node, ast.Constant) and node.value in MODULES and node.value != name:
            yield node.value, None


EDGES = {name: sorted(set(_imports(name, path)), key=str) for name, path in MODULES.items()}


def test_packages_import_only_lower_layers():
    upward = [
        f"{source} -> {target}"
        for source, imports in EDGES.items()
        for target, _name in imports
        if LAYERS[target.split(".")[0]] > LAYERS[source.split(".")[0]]
    ]
    assert upward == []


def _part(module):
    package, part = module.split(".")[:2]
    return package, part


def test_every_module_has_a_part_layer():
    unlisted = sorted({".".join(_part(name)) for name in MODULES if _part(name)[1] not in PART_LAYERS[_part(name)[0]]})
    assert unlisted == []


def test_parts_import_only_lower_layers():
    upward = []
    for source, imports in EDGES.items():
        package, source_part = _part(source)
        for target, _name in imports:
            target_package, target_part = _part(target)
            if target_package != package or target_part == source_part:
                continue
            layers = PART_LAYERS[package]
            if layers[target_part] >= layers[source_part]:
                upward.append(f"{source} -> {target}")
    assert upward == []


def test_engine_takes_per_run_settings_as_arguments():
    reads = [
        f"{source} -> {target}" + (f".{name}" if name else "")
        for source, imports in EDGES.items()
        if source.startswith("engine.")
        for target, name in imports
        if target == "config.env" or name in PER_RUN_DEFAULTS.get(target, ()) or (target in PER_RUN_DEFAULTS and not name)
    ]
    assert reads == []


def test_gui_uses_only_pipeline_entry_points():
    reaches = [
        f"{source} -> {target}"
        for source, imports in EDGES.items()
        if source.startswith("gui.")
        for target, _name in imports
        if target.startswith("pipeline.") and target not in PIPELINE_ENTRY_POINTS
    ]
    assert reaches == []


def test_module_import_graph_has_no_cycles():
    graph = {name: {target for target, _name in imports if target in MODULES} for name, imports in EDGES.items()}
    visiting, done, cycles = set(), set(), []

    def visit(node, trail):
        visiting.add(node)
        for nxt in sorted(graph[node]):
            if nxt in visiting:
                cycles.append(" -> ".join(trail[trail.index(nxt):] + [nxt]))
            elif nxt not in done:
                visit(nxt, trail + [nxt])
        visiting.discard(node)
        done.add(node)

    for name in sorted(graph):
        if name not in done:
            visit(name, [name])
    assert cycles == []


def test_imports_land_on_public_names_only():
    private = [
        f"{source} imports {target}.{name}"
        for source, imports in EDGES.items()
        for target, name in imports
        if name and name.startswith("_")
    ]
    private += [
        f"{source} imports {target}"
        for source, imports in EDGES.items()
        for target, _name in imports
        if any(part.startswith("_") for part in target.split(".")[1:]) and target.split(".")[0] != source.split(".")[0]
    ]
    assert private == []
