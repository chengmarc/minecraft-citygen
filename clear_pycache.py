"""Remove Python __pycache__ directories under this repository."""
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main():
    removed = 0
    for path in sorted(ROOT.rglob("__pycache__"), key=lambda p: len(p.parts), reverse=True):
        resolved = path.resolve()
        if ROOT not in (resolved, *resolved.parents):
            raise RuntimeError(f"refusing to remove outside repo: {resolved}")
        shutil.rmtree(resolved)
        removed += 1
        print(f"removed {resolved}")
    print(f"removed {removed} __pycache__ director{'y' if removed == 1 else 'ies'}")


if __name__ == "__main__":
    main()
