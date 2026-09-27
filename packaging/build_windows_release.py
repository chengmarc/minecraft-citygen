"""Build Windows release artifacts for Minecraft CityGen.

Default output:
- dist/release/Minecraft CityGen-setup.exe
- dist/release/Minecraft CityGen-portable-windows.zip

Optional outputs:
- dist/release/Minecraft CityGen.exe
- dist/store/Minecraft CityGen.msix (Microsoft Store upload; not a release artifact)
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
BUILD_ROOT = ROOT / "build" / "release"
DIST_ROOT = ROOT / "dist"
PORTABLE_DIST = DIST_ROOT / "portable"
ONEFILE_DIST = DIST_ROOT / "onefile"
RELEASE_DIST = DIST_ROOT / "release"
STORE_DIST = DIST_ROOT / "store"
APP_NAME = "Minecraft CityGen"
ZIP_BASENAME = "Minecraft CityGen-portable-windows"
ZIP_PATH = RELEASE_DIST / f"{ZIP_BASENAME}.zip"
ONEFILE_EXE = RELEASE_DIST / f"{APP_NAME}.exe"
INSTALLER_EXE = RELEASE_DIST / f"{APP_NAME}-setup.exe"
MSIX_PATH = STORE_DIST / f"{APP_NAME}.msix"
MSIX_LAYOUT = BUILD_ROOT / "msix"
MSIX_MANIFEST_TEMPLATE = ROOT / "packaging" / "AppxManifest.xml"
# From Partner Center > Product identity once the app name is reserved for the MSIX listing.
MSIX_IDENTITY_NAME = "chengmarc.MCCityGen"
MSIX_PUBLISHER = "CN=58F02A86-A694-404A-8E09-F891292262CA"
MSIX_PUBLISHER_DISPLAY_NAME = "chengmarc"
MSIX_DISPLAY_NAME = "MC CityGen"  # must match the app name reserved in Partner Center
MSIX_LOGOS = {  # manifest asset name -> square size in pixels
    "StoreLogo.png": 50,
    "Square44x44Logo.png": 44,
    "Square150x150Logo.png": 150,
}
ICON_PNG = SRC_ROOT / "gui" / "icons" / "app-icon.png"
ICON_ICO = BUILD_ROOT / "app-icon.ico"
DEFAULT_WORLD_DIR = SRC_ROOT / "config" / "default_world"
README_FILES = (
    (ROOT / "README.md", "README.md"),
)
WINDOWS_DATA_SEP = ";"
PIPELINE_STAGE_HIDDEN_IMPORTS = (
    "pipeline.01_roads.extract",
    "pipeline.01_roads.render",
    "pipeline.02_builds.extract",
    "pipeline.02_builds.render",
    "pipeline.03_preview.roads",
    "pipeline.03_preview.builds",
    "pipeline.03_preview.grid",
    "pipeline.03_preview.city",
    "pipeline.04_city.construct",
    "pipeline.04_city.render",
    "pipeline.05_world.export",
)


def load_version() -> str:
    with open(ROOT / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def run(command: list[str]) -> None:
    print(">", " ".join(command))
    subprocess.run(command, cwd=ROOT, env=build_environment(), check=True)


def build_environment() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    src_path = str(SRC_ROOT)
    env["PYTHONPATH"] = src_path if not existing else os.pathsep.join((src_path, existing))
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
        "--paths",
        str(SRC_ROOT),
        "--collect-submodules",
        "pipeline",
        "--collect-submodules",
        "gui",
        "--add-data",
        data_arg(SRC_ROOT / "gui" / "icons", "gui/icons"),
        "--add-data",
        data_arg(SRC_ROOT / "config" / "color_render.csv", "config"),
        "--add-data",
        data_arg(DEFAULT_WORLD_DIR, "config/default_world"),
    ]
    for module_name in PIPELINE_STAGE_HIDDEN_IMPORTS:
        command.extend(["--hidden-import", module_name])
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
        raise SystemExit("Installer build completed without producing Minecraft CityGen-setup.exe.")
    return INSTALLER_EXE


def msix_version(version: str) -> str:
    """Store packages need a four-part version whose last part is 0."""
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise SystemExit(f"Cannot turn version {version!r} into an MSIX version; expected MAJOR.MINOR.PATCH.")
    return f"{version}.0"


def render_msix_manifest(version: str) -> str:
    missing = [
        name
        for name, value in (
            ("MSIX_IDENTITY_NAME", MSIX_IDENTITY_NAME),
            ("MSIX_PUBLISHER", MSIX_PUBLISHER),
            ("MSIX_PUBLISHER_DISPLAY_NAME", MSIX_PUBLISHER_DISPLAY_NAME),
        )
        if not value
    ]
    if missing:
        raise SystemExit(
            f"Set {', '.join(missing)} in build_windows_release.py from Partner Center > Product identity."
        )
    template = MSIX_MANIFEST_TEMPLATE.read_text(encoding="utf-8")
    return template.format(
        identity_name=MSIX_IDENTITY_NAME,
        publisher=MSIX_PUBLISHER,
        publisher_display_name=MSIX_PUBLISHER_DISPLAY_NAME,
        version=msix_version(version),
        display_name=MSIX_DISPLAY_NAME,
        executable=f"{APP_NAME}.exe",
    )


def find_makeappx() -> str | None:
    path = shutil.which("makeappx")
    if path:
        return path
    bin_dirs = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Windows Kits" / "10" / "bin",
        # Unzipped Microsoft.Windows.SDK.BuildTools NuGet package: the tools without the full SDK.
        Path(os.environ.get("LOCALAPPDATA", "")) / "Minecraft CityGen Build" / "sdk-buildtools" / "bin",
    ]
    candidates = sorted(
        (path for bin_dir in bin_dirs for path in bin_dir.glob("10.*/x64/makeappx.exe")),
        key=lambda p: tuple(int(n) for n in p.parent.parent.name.split(".")),
    )
    return str(candidates[-1]) if candidates else None


def build_msix(version: str, app_dir: Path) -> Path:
    manifest = render_msix_manifest(version)
    makeappx = find_makeappx()
    if makeappx is None:
        raise SystemExit(
            "makeappx.exe was not found. Install the Windows SDK so the MSIX package can be built."
        )
    from PIL import Image

    shutil.rmtree(MSIX_LAYOUT, ignore_errors=True)
    shutil.copytree(app_dir, MSIX_LAYOUT)
    (MSIX_LAYOUT / "AppxManifest.xml").write_text(manifest, encoding="utf-8")
    assets = MSIX_LAYOUT / "Assets"
    assets.mkdir()
    with Image.open(ICON_PNG) as image:
        for name, size in MSIX_LOGOS.items():
            image.resize((size, size), Image.LANCZOS).save(assets / name)

    STORE_DIST.mkdir(parents=True, exist_ok=True)
    run([makeappx, "pack", "/o", "/d", str(MSIX_LAYOUT), "/p", str(MSIX_PATH)])
    return MSIX_PATH


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
        help="also publish the standalone Minecraft CityGen.exe to dist/release",
    )
    parser.add_argument(
        "--msix",
        action="store_true",
        help="also build the Microsoft Store package to dist/store",
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
    if args.msix:
        render_msix_manifest(version)  # fail on missing Store identity before the slow build
    icon_path = build_icon()
    app_dir = build_portable(icon_path)
    installer_path = build_installer(version, app_dir)
    zip_path = build_zip(app_dir)
    exe_path = build_onefile(icon_path) if args.include_standalone else None
    msix_path = build_msix(version, app_dir) if args.msix else None
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
    if msix_path is not None:
        print(f"- {msix_path} (Microsoft Store upload)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
