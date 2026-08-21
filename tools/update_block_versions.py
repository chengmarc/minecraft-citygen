#!/usr/bin/env python
"""Regenerate the block-version compatibility tables from Minecraft server JARs.

This is a maintenance script (not part of the packaged runtime). It downloads
every Java Edition *release* server JAR from the supported floor (1.18) upward,
reads each jar's DataVersion from its bundled ``version.json``, and runs the
vanilla data generator (``--reports``) to dump the full block registry for that
version. Diffing the registries across versions in DataVersion order yields the
first version each block appears in.

Outputs (loaded by ``config/version_compat.py`` when present, replacing its
hand-curated fallback tables):

  - ``src/config/mc_versions.json``     ``{release: data_version}``, oldest first
  - ``src/config/block_versions.json``  ``{block_id: min_data_version}``

Requirements and behaviour:

  - a Java runtime new enough for the newest jar scanned (1.20.5+ needs Java 21)
  - downloaded server JARs are cached under ``tools/`` and are git-ignored
  - a version whose download or data generator fails is skipped with a warning,
    so a partial-but-valid table is still written; the summary lists what failed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
CONFIG_DIR = ROOT / "src" / "config"
RELEASES_OUTPUT = CONFIG_DIR / "mc_versions.json"
BLOCKS_OUTPUT = CONFIG_DIR / "block_versions.json"

VERSION_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
HTTP_TIMEOUT_SECONDS = 120
USER_AGENT = "CityGen block-version updater"

# 1.18's release timestamp. Filtering the manifest by release time bounds the
# download set to the supported range without fragile version-string parsing.
FLOOR_RELEASE_TIME = "2021-11-30T00:00:00+00:00"
DATA_GENERATOR_MAIN = "net.minecraft.data.Main"


def load_json_url(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.load(response)


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_release_metadata(since: str) -> list[dict]:
    """Release manifest entries at or after ``since``, oldest first."""
    manifest = load_json_url(VERSION_MANIFEST_URL)
    items = [
        item
        for item in manifest["versions"]
        if item.get("type") == "release" and item.get("releaseTime", "") >= since
    ]
    items.sort(key=lambda item: item["releaseTime"])
    return items


def download_server_jar(version_meta: dict) -> Path | None:
    """Download (and cache) a version's server JAR, or None if it has no server."""
    version_manifest = load_json_url(version_meta["url"])
    server = version_manifest.get("downloads", {}).get("server")
    if not server:
        return None

    expected_sha1 = server.get("sha1")
    jar_path = TOOLS_DIR / f"minecraft-server-{version_meta['id']}.jar"
    if jar_path.is_file() and expected_sha1 and sha1_file(jar_path) == expected_sha1:
        return jar_path

    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = jar_path.with_suffix(".jar.part")
    request = urllib.request.Request(server["url"], headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        with temp_path.open("wb") as fh:
            shutil.copyfileobj(response, fh)

    if expected_sha1:
        digest = sha1_file(temp_path)
        if digest != expected_sha1:
            temp_path.unlink(missing_ok=True)
            raise RuntimeError(f"server JAR SHA-1 mismatch: expected {expected_sha1}, got {digest}")

    temp_path.replace(jar_path)
    return jar_path


def read_data_version(jar_path: Path) -> tuple[int, str]:
    """DataVersion and release name from the jar's bundled version.json."""
    with zipfile.ZipFile(jar_path) as zf:
        with zf.open("version.json") as fh:
            meta = json.load(fh)
    return int(meta["world_version"]), str(meta.get("name") or meta.get("id"))


def generate_block_ids(jar_path: Path, java_exe: str) -> set[str]:
    """Full block-id registry for a version via the vanilla data generator."""
    with tempfile.TemporaryDirectory() as tmp:
        command = [
            java_exe,
            f"-DbundlerMainClass={DATA_GENERATOR_MAIN}",
            "-jar",
            str(jar_path),
            "--reports",
        ]
        proc = subprocess.run(command, cwd=tmp, capture_output=True, text=True)
        report = Path(tmp) / "generated" / "reports" / "blocks.json"
        if proc.returncode != 0 or not report.is_file():
            detail = (proc.stderr or proc.stdout or "data generator produced no report").strip()
            raise RuntimeError(detail[-500:])
        with report.open(encoding="utf-8") as fh:
            return set(json.load(fh).keys())


def attribute_first_versions(registries: dict[int, set[str]]) -> tuple[dict[str, int], int | None]:
    """Map each block id to the earliest DataVersion it appears in."""
    first_seen: dict[str, int] = {}
    for data_version in sorted(registries):
        for block_id in registries[data_version]:
            first_seen.setdefault(block_id, data_version)
    floor = min(registries) if registries else None
    return first_seen, floor


def write_releases_json(releases: dict[int, str], path: Path) -> None:
    # {release: data_version}, written in DataVersion order for readable diffs.
    ordered = {name: data_version for data_version, name in sorted(releases.items())}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(ordered, fh, indent=2)
        fh.write("\n")


def write_blocks_json(first_seen: dict[str, int], floor: int, path: Path) -> int:
    # {block_id: min_data_version} for blocks introduced after the floor version.
    blocks = {
        block_id: data_version
        for block_id, data_version in first_seen.items()
        if data_version > floor
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(blocks, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return len(blocks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Regenerate src/config/mc_versions.csv and block_versions.csv from server JARs."
    )
    parser.add_argument(
        "--since",
        default=FLOOR_RELEASE_TIME,
        help="ISO release-time floor for versions to scan (default: 1.18's release).",
    )
    parser.add_argument(
        "--java",
        help="Path to the Java executable. Defaults to 'java' on PATH.",
    )
    parser.add_argument(
        "--max-versions",
        type=int,
        help="Scan only the oldest N selected releases (for a quick test run).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    java_exe = args.java or shutil.which("java")
    if not java_exe:
        print("error: no Java runtime found. Install a JRE (21+) or pass --java.", file=sys.stderr)
        return 1

    metas = selected_release_metadata(args.since)
    if args.max_versions is not None:
        metas = metas[: args.max_versions]
    print(f"scanning {len(metas)} release(s) from {args.since} onward")

    releases: dict[int, str] = {}
    registries: dict[int, set[str]] = {}
    failed: list[tuple[str, str]] = []

    for meta in metas:
        version_id = meta["id"]
        try:
            jar_path = download_server_jar(meta)
        except (OSError, RuntimeError, ValueError) as exc:
            failed.append((version_id, f"download: {exc}"))
            continue
        if jar_path is None:
            failed.append((version_id, "no server download available"))
            continue
        try:
            data_version, name = read_data_version(jar_path)
        except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
            failed.append((version_id, f"version.json: {exc}"))
            continue
        releases[data_version] = name
        try:
            block_ids = generate_block_ids(jar_path, java_exe)
        except (OSError, RuntimeError, ValueError) as exc:
            failed.append((version_id, f"data generator: {exc}"))
            continue
        registries[data_version] = block_ids
        print(f"  {name}: DataVersion {data_version}, {len(block_ids)} blocks")

    if not registries:
        print("error: no block registries were generated; nothing written.", file=sys.stderr)
        for version_id, reason in failed:
            print(f"  - {version_id}: {reason}", file=sys.stderr)
        return 1

    first_seen, floor = attribute_first_versions(registries)
    write_releases_json(releases, RELEASES_OUTPUT)
    block_count = write_blocks_json(first_seen, floor, BLOCKS_OUTPUT)

    print(f"wrote {len(releases)} releases to {RELEASES_OUTPUT}")
    print(f"wrote {block_count} post-floor blocks to {BLOCKS_OUTPUT} (floor DataVersion {floor})")
    if failed:
        print(f"skipped {len(failed)} version(s):")
        for version_id, reason in failed:
            print(f"  - {version_id}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
