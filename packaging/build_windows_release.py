"""Build Windows release artifacts for CityGen.

Default output:
- dist/release/CityGen-setup.exe
- dist/release/CityGen-portable-windows.zip

Optional outputs:
- dist/release/CityGen.exe
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
DOCS_ROOT = ROOT / "docs"
BUILD_ROOT = ROOT / "build" / "release"
DIST_ROOT = ROOT / "dist"
PORTABLE_DIST = DIST_ROOT / "portable"
ONEFILE_DIST = DIST_ROOT / "onefile"
RELEASE_DIST = DIST_ROOT / "release"
HOOKS_DIR = ROOT / "packaging" / "pyinstaller_hooks"
APP_NAME = "CityGen"
ZIP_BASENAME = "CityGen-portable-windows"
ZIP_PATH = RELEASE_DIST / f"{ZIP_BASENAME}.zip"
ONEFILE_EXE = RELEASE_DIST / f"{APP_NAME}.exe"
INSTALLER_EXE = RELEASE_DIST / f"{APP_NAME}-setup.exe"
ICON_PNG = SRC_ROOT / "gui" / "icons" / "app-icon.png"
ICON_ICO = BUILD_ROOT / "app-icon.ico"
DEFAULT_WORLD_DIR = SRC_ROOT / "config" / "default_world"
README_FILES = (
    (ROOT / "README.md", "README.md"),
    (DOCS_ROOT / "TECHNICAL.md", "TECHNICAL.md"),
)
WINDOWS_DATA_SEP = ";"


def load_version() -> str:
    with open(ROOT / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def run(command: list[str], *, cwd: Path | None = None) -> None:
    print(">", " ".join(command))
    subprocess.run(command, cwd=cwd or ROOT, env=build_environment(), check=True)


def build_environment() -> dict[str, str]:
    env = os.environ.copy()
    tcl_root = Path(sys.base_prefix) / "tcl"
    dll_root = Path(sys.base_prefix) / "DLLs"
    tcl_library = tcl_root / "tcl8.6"
    tk_library = tcl_root / "tk8.6"
    if dll_root.is_dir():
        env["PATH"] = str(dll_root) + os.pathsep + env.get("PATH", "")
    if (tcl_library / "init.tcl").is_file():
        env["TCL_LIBRARY"] = str(tcl_library).replace("\\", "/")
    if (tk_library / "tk.tcl").is_file():
        env["TK_LIBRARY"] = str(tk_library).replace("\\", "/")
    if tcl_root.is_dir():
        roots = [str(tcl_library).replace("\\", "/"), str(tcl_root).replace("\\", "/")]
        env["TCLLIBPATH"] = " ".join("{" + root + "}" for root in roots)
    return env


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:  # pragma: no cover - handled in live build flow
        raise SystemExit(
            "PyInstaller is not installed. Run `python -m pip install .[build]` first."
        ) from exc


def build_icon() -> Path | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    with Image.open(ICON_PNG) as image:
        image.save(
            ICON_ICO,
            format="ICO",
            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
        )
    return ICON_ICO


def data_arg(source: Path, target: str) -> str:
    return f"{source}{WINDOWS_DATA_SEP}{target}"


def base_pyinstaller_command(*, onefile: bool, icon_path: Path | None) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--distpath",
        str(ONEFILE_DIST if onefile else PORTABLE_DIST),
        "--workpath",
        str(BUILD_ROOT / ("onefile" if onefile else "portable")),
        "--specpath",
        str(BUILD_ROOT / "spec"),
        "--additional-hooks-dir",
        str(HOOKS_DIR),
        "--paths",
        str(SRC_ROOT),
        "--collect-submodules",
        "pipeline",
        "--collect-submodules",
        "tkinter",
        "--collect-data",
        "ttkbootstrap",
        "--hidden-import",
        "tkinter",
        "--hidden-import",
        "_tkinter",
        "--add-data",
        data_arg(SRC_ROOT / "gui" / "icons", "gui/icons"),
        "--add-data",
        data_arg(SRC_ROOT / "engine" / "color_render.csv", "engine"),
        "--add-data",
        data_arg(DEFAULT_WORLD_DIR, "config/default_world"),
    ]
    if onefile:
        command.append("--onefile")
    if icon_path is not None and icon_path.exists():
        command.extend(["--icon", str(icon_path)])
    command.append(str(SRC_ROOT / "gui" / "launcher.py"))
    return command


def copy_docs(target_dir: Path) -> None:
    for source_path, output_name in README_FILES:
        shutil.copy2(source_path, target_dir / output_name)


def build_portable(icon_path: Path | None) -> Path:
    shutil.rmtree(PORTABLE_DIST, ignore_errors=True)
    run(base_pyinstaller_command(onefile=False, icon_path=icon_path))
    app_dir = PORTABLE_DIST / APP_NAME
    copy_docs(app_dir)
    if icon_path is not None and icon_path.exists():
        shutil.copy2(icon_path, app_dir / icon_path.name)
    return app_dir


def build_onefile(icon_path: Path | None) -> Path:
    shutil.rmtree(ONEFILE_DIST, ignore_errors=True)
    RELEASE_DIST.mkdir(parents=True, exist_ok=True)
    run(base_pyinstaller_command(onefile=True, icon_path=icon_path))
    built = ONEFILE_DIST / f"{APP_NAME}.exe"
    shutil.copy2(built, ONEFILE_EXE)
    return ONEFILE_EXE


def build_zip(app_dir: Path) -> Path:
    RELEASE_DIST.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    archive = shutil.make_archive(
        str(RELEASE_DIST / ZIP_BASENAME),
        "zip",
        root_dir=PORTABLE_DIST,
        base_dir=APP_NAME,
    )
    return Path(archive)


def find_iscc() -> str | None:
    path = shutil.which("ISCC")
    if path:
        return path
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def build_installer(version: str, app_dir: Path) -> Path:
    iscc = find_iscc()
    if iscc is None:
        raise SystemExit(
            "Inno Setup was not found. Install it first so the installer can be built."
        )
    RELEASE_DIST.mkdir(parents=True, exist_ok=True)
    if INSTALLER_EXE.exists():
        INSTALLER_EXE.unlink()
    command = [
        iscc,
        f"/DAppVersion={version}",
        f"/DSourceDir={app_dir}",
        f"/DOutputDir={RELEASE_DIST}",
        f"/DOutputBaseFilename={INSTALLER_EXE.stem}",
        str(ROOT / "packaging" / "windows_installer.iss"),
    ]
    run(command)
    if not INSTALLER_EXE.exists():
        raise SystemExit("Installer build completed without producing CityGen-setup.exe.")
    return INSTALLER_EXE


def prune_release_artifacts(*, keep_installer: bool, keep_zip: bool, keep_exe: bool) -> None:
    RELEASE_DIST.mkdir(parents=True, exist_ok=True)
    removable = [
        (INSTALLER_EXE, keep_installer),
        (ZIP_PATH, keep_zip),
        (ONEFILE_EXE, keep_exe),
    ]
    for path, keep in removable:
        if keep or not path.exists():
            continue
        path.unlink()


def clean() -> None:
    for path in (BUILD_ROOT, DIST_ROOT):
        shutil.rmtree(path, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true", help="remove prior build outputs before building")
    parser.add_argument(
        "--include-standalone",
        action="store_true",
        help="also publish the standalone CityGen.exe to dist/release",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.name != "nt":
        raise SystemExit("This release script targets Windows only.")
    if args.clean:
        clean()
    ensure_pyinstaller()
    version = load_version()
    icon_path = build_icon()
    app_dir = build_portable(icon_path)
    installer_path = build_installer(version, app_dir)
    zip_path = build_zip(app_dir)
    exe_path = build_onefile(icon_path) if args.include_standalone else None
    prune_release_artifacts(
        keep_installer=True,
        keep_zip=True,
        keep_exe=args.include_standalone,
    )

    print()
    print("Built artifacts:")
    print(f"- {installer_path}")
    print(f"- {zip_path}")
    if exe_path is not None:
        print(f"- {exe_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
