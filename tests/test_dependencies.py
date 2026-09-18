"""The source tree's import graph stays a layered DAG.

Reads every module under ``src/`` with ``ast`` (nothing is imported) and checks
the three dependency rules: packages only import downward, no module-level
cycles, and imports land on public names only.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

# Lower layers never import higher ones; a package may import itself.
LAYERS = {"config": 0, "engine": 1, "pipeline": 2, "gui": 3}

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


EDGES = {name: sorted(set(_imports(name, path)), key=str) for name, path in MODULES.items()}


def test_packages_import_only_lower_layers():
    upward = [
        f"{source} -> {target}"
        for source, imports in EDGES.items()
        for target, _name in imports
        if LAYERS[target.split(".")[0]] > LAYERS[source.split(".")[0]]
    ]
    assert upward == []


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
