"""Remove every ``__pycache__`` directory and ``__init__.py`` file in the repo."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _within_repo(path: Path) -> bool:
    resolved = path.resolve()
    return resolved == REPO_ROOT or REPO_ROOT in resolved.parents


def _targets() -> tuple[list[Path], list[Path]]:
    pycache_dirs = sorted(
        (path for path in REPO_ROOT.rglob("__pycache__") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    init_files = sorted(path for path in REPO_ROOT.rglob("__init__.py") if path.is_file())
    return pycache_dirs, init_files


def remove_targets(*, dry_run: bool = False) -> tuple[list[Path], list[Path]]:
    pycache_dirs, init_files = _targets()
    for path in (*pycache_dirs, *init_files):
        if not _within_repo(path):
            raise RuntimeError(f"refusing to remove outside repo: {path}")

    if not dry_run:
        for path in pycache_dirs:
            shutil.rmtree(path)
        for path in init_files:
            path.unlink()

    return pycache_dirs, init_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be removed without deleting anything",
    )
    args = parser.parse_args(argv)

    pycache_dirs, init_files = remove_targets(dry_run=args.dry_run)
    action = "would remove" if args.dry_run else "removed"
    for path in pycache_dirs:
        print(f"{action} dir  {path.relative_to(REPO_ROOT)}")
    for path in init_files:
        print(f"{action} file {path.relative_to(REPO_ROOT)}")
    print(f"{action} {len(pycache_dirs)} __pycache__ dir(s) and {len(init_files)} __init__.py file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
