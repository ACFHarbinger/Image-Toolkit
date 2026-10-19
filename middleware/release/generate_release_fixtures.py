#!/usr/bin/env python3
"""Build the external release corpus from real local media only."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps

DATA_HOME = Path.home() / "Downloads" / "Data"
ROOT = (DATA_HOME / "Tests" / "release-1.0.0").resolve()
TESTS_ROOT = (DATA_HOME / "Tests").resolve()
DATA = DATA_HOME.resolve()
ARTIFACTS = frozenset({"ImageToolkit-1.0.0-x86_64.appimage", "ImageToolkit-1.0.0-x86_64.AppImage", "image-toolkit_1.0.0_amd64.deb", "SHA256SUMS.txt"})
FIXTURE_DIRS = ("images", "sheets", "video", "wallpaper-a", "wallpaper-b", "stitch", "manga", "models", "listings", "entity-recon", "reverse-search", "http-fixture", "cloud-sync", "local-directory-sync", "disposable", "evidence")
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
SOURCE_DIRS = (DATA / "Gaming", DATA / "Wallpapers", DATA / "Frames", DATA / "Anime", DATA / "Models")
CLIPS = (
    DATA / "Frames/Videos/Akane wa Tsumare Somerareru - 01 [1080p-HEVC][hstream.moe]_182927ms_185303ms.mp4",
    DATA / "Frames/Videos/Ajisai no Chiru Koro ni - 01 [1080p-HEVC][hstream.moe][v2]_632106ms_640483ms.mp4",
    DATA / "Frames/Videos/Himawari wa Yoru ni Saku - 01 [1080p-HEVC][hstream.moe][v2]_57836ms_66789ms.mp4",
)
LONG_CLIP = DATA / "Cinematography/master17.mp4"


def safe_root() -> None:
    if ROOT.parent != TESTS_ROOT or ROOT.name != "release-1.0.0":
        raise RuntimeError(f"Unsafe fixture root: {ROOT}")
    ROOT.mkdir(parents=True, exist_ok=True)


def clean() -> None:
    for name in FIXTURE_DIRS:
        target = ROOT / name
        if target.exists():
            shutil.rmtree(target)
    (ROOT / "README.md").unlink(missing_ok=True)


def choose(paths: list[Path], count: int) -> list[Path]:
    if len(paths) < count:
        raise RuntimeError(f"Required {count} usable sources, found {len(paths)}")
    step = (len(paths) - 1) / (count - 1)
    return [paths[round(index * step)] for index in range(count)]


def valid_images(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    for path in paths:
        try:
            with Image.open(path) as image:
                image.verify()
        except (OSError, ValueError):
            continue
        result.append(path)
    return result


def sources(root: Path, extensions: set[str]) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in extensions)


def cp(source: Path, destination: Path, provenance: dict[str, str]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    provenance[destination.relative_to(ROOT).as_posix()] = str(source)


def corrupt(source: Path, destination: Path, provenance: dict[str, str]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes()[:4096])
    provenance[destination.relative_to(ROOT).as_posix()] = f"truncated copy of {source}"


def derive(source: Path, destination: Path, fmt: str, provenance: dict[str, str], **save_args) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image.convert("RGB").save(destination, fmt, **save_args)
    provenance[destination.relative_to(ROOT).as_posix()] = f"{fmt} conversion of {source}"


def contact_sheet(media: list[Path], destination: Path, columns: int, rows: int, provenance: dict[str, str]) -> None:
    sheet = Image.new("RGB", (columns * 320, rows * 240))
    for index, source in enumerate(media[: columns * rows]):
        with Image.open(source) as image:
            sheet.paste(ImageOps.fit(image.convert("RGB"), (320, 240)), ((index % columns) * 320, (index // columns) * 240))
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination)
    provenance[destination.relative_to(ROOT).as_posix()] = f"real-media contact sheet beginning with {media[0]}"


def make_images(provenance: dict[str, str]) -> list[Path]:
    candidates = [
        path
        for root in SOURCE_DIRS
        for path in sources(root, IMAGE_EXTS)[:1_000]
        if 20_000 < path.stat().st_size < 2_500_000
    ]
    media = valid_images(candidates)
    selected = choose(media, 200)
    for index, source in enumerate(selected[:48], 1):
        cp(source, ROOT / "images/library" / f"library_{index:03d}{source.suffix.lower()}", provenance)
    for index, source in enumerate(choose(valid_images(sources(DATA, {".webp"})), 4), 1):
        cp(source, ROOT / "images/library" / f"library-webp-{index:02d}.webp", provenance)
    for index, source in enumerate(choose(valid_images(sources(DATA / "Anime", {".gif"})), 2), 1):
        cp(source, ROOT / "images/library" / f"library-animation-{index:02d}.gif", provenance)
    primary = selected[0]
    cp(primary, ROOT / "images/duplicates" / f"duplicate-a{primary.suffix.lower()}", provenance)
    cp(primary, ROOT / "images/duplicates" / f"duplicate-b{primary.suffix.lower()}", provenance)
    derive(primary, ROOT / "images/derived/real-source.bmp", "BMP", provenance)
    derive(primary, ROOT / "images/derived/real-source.tiff", "TIFF", provenance)
    with Image.open(primary) as image:
        rgba = image.convert("RGBA")
        rgba.putalpha(ImageOps.grayscale(rgba.convert("RGB")).point(lambda value: 96 + value // 2))
        alpha_path = ROOT / "images/derived/real-source-alpha.png"
        alpha_path.parent.mkdir(parents=True, exist_ok=True)
        rgba.save(alpha_path)
        provenance[alpha_path.relative_to(ROOT).as_posix()] = f"alpha conversion of {primary}"
        resized = ROOT / "images/derived/real-source-resized.jpg"
        rgba.resize((max(1, rgba.width // 2), max(1, rgba.height // 2))).convert("RGB").save(resized, quality=82)
        provenance[resized.relative_to(ROOT).as_posix()] = f"resized conversion of {primary}"
    derive(primary, ROOT / "images/derived/real-source-recompressed.jpg", "JPEG", provenance, quality=45)
    corrupt(primary, ROOT / "images/corrupt/truncated-image.jpg", provenance)
    for name, cols, rows in (("vertical", 1, 6), ("horizontal", 6, 1), ("grid", 3, 2), ("guttered-grid", 3, 2), ("partial-final-frame", 2, 2)):
        contact_sheet(selected, ROOT / "sheets" / f"real-{name}.png", cols, rows, provenance)
    return selected


def make_videos(provenance: dict[str, str]) -> list[Path]:
    if not LONG_CLIP.is_file() or not all(path.is_file() for path in CLIPS):
        raise RuntimeError("Required real video sources are missing")
    for index, source in enumerate(CLIPS, 1):
        cp(source, ROOT / "video/library" / f"library-clip-{index:02d}.mp4", provenance)
    cp(LONG_CLIP, ROOT / "video/library/long-cancel-master17.mp4", provenance)
    corrupt(CLIPS[0], ROOT / "video/corrupt/truncated-video.mp4", provenance)
    return list(CLIPS)


def make_wallpapers(media: list[Path], videos: list[Path], provenance: dict[str, str]) -> None:
    gifs = choose(valid_images(sources(DATA / "Anime", {".gif"})), 8)
    for name, selected, selected_gifs in (("wallpaper-a", media[:100], gifs[:4]), ("wallpaper-b", media[100:200], gifs[4:])):
        for index, source in enumerate(selected, 1):
            cp(source, ROOT / name / f"library-{index:03d}{source.suffix.lower()}", provenance)
        for index, source in enumerate(selected_gifs, 1):
            cp(source, ROOT / name / f"animated-{index:02d}.gif", provenance)
        for index, source in enumerate(videos[:2], 1):
            cp(source, ROOT / name / f"video-{index:02d}.mp4", provenance)
        corrupt(selected[0], ROOT / name / "corrupt-image.jpg", provenance)


def make_workflows(media: list[Path], videos: list[Path], provenance: dict[str, str]) -> None:
    ordered = media[48:54]
    for index, source in enumerate(ordered, 1):
        cp(source, ROOT / "stitch/ordered" / f"frame-{index:03d}{source.suffix.lower()}", provenance)
    for index, source in enumerate((ordered[2], ordered[0], ordered[5], ordered[1], ordered[4], ordered[3]), 1):
        cp(source, ROOT / "stitch/shuffled" / f"frame-{index:03d}{source.suffix.lower()}", provenance)
    cp(media[-1], ROOT / "stitch/weak-nonoverlap" / f"weak{media[-1].suffix.lower()}", provenance)
    cp(videos[0], ROOT / "stitch/video/real-source.mp4", provenance)
    for index, source in enumerate(media[54:66], 1):
        cp(source, ROOT / "manga/real-library" / f"reference-{index:02d}{source.suffix.lower()}", provenance)
    for index, source in enumerate(media[66:90], 1):
        cp(source, ROOT / "models/datasets/real-library" / f"sample-{index:03d}{source.suffix.lower()}", provenance)
    for index, source in enumerate(media[90:96], 1):
        cp(source, ROOT / "listings/entity-images" / f"entity-{index:02d}{source.suffix.lower()}", provenance)
    for index, source in enumerate(videos, 1):
        cp(source, ROOT / "listings/series-videos/Real_Library" / f"Real Library - {index:02d}.mp4", provenance)
    for directory, source in (("reverse-search/queries", media[96]), ("entity-recon/queries", media[97]), ("cloud-sync/local", media[98]), ("local-directory-sync/local", media[99]), ("disposable/delete-files", media[100]), ("http-fixture/binary", media[103])):
        cp(source, ROOT / directory / f"real{source.suffix.lower()}", provenance)
    cp(media[101], ROOT / "disposable/similarity" / f"duplicate-a{media[101].suffix.lower()}", provenance)
    cp(media[101], ROOT / "disposable/similarity" / f"duplicate-b{media[101].suffix.lower()}", provenance)
    corrupt(media[102], ROOT / "disposable/failures/corrupt-input.jpg", provenance)


def inventory(provenance: dict[str, str]) -> None:
    excluded = {ROOT / "README.md", ROOT / "evidence/checksums/SHA256SUMS.txt", ROOT / "evidence/reports/FIXTURE_MANIFEST.json", ROOT / "evidence/reports/SOURCE_MANIFEST.json"}
    files = sorted(path for path in ROOT.rglob("*") if path.is_file() and path not in excluded and not (path.parent == ROOT and path.name in ARTIFACTS))
    sums, counts, total = [], Counter(), 0
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        sums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {rel}")
        counts[path.suffix.lower() or "<none>"] += 1
        total += path.stat().st_size
    reports = ROOT / "evidence/reports"
    reports.mkdir(parents=True, exist_ok=True)
    (ROOT / "evidence/checksums").mkdir(parents=True, exist_ok=True)
    (ROOT / "evidence/checksums/SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    (reports / "SOURCE_MANIFEST.json").write_text(json.dumps(dict(sorted(provenance.items())), indent=2) + "\n", encoding="utf-8")
    (reports / "FIXTURE_MANIFEST.json").write_text(json.dumps({"fixture_root": str(ROOT), "file_count_excluding_inventory_and_release_artifacts": len(files), "total_bytes_excluding_inventory_and_release_artifacts": total, "suffix_counts": dict(sorted(counts.items())), "media_policy": "all media copied from or directly derived from real local library media", "source_manifest": "evidence/reports/SOURCE_MANIFEST.json"}, indent=2) + "\n", encoding="utf-8")
    (ROOT / "README.md").write_text("# Real-media release fixtures\n\nAll media comes from the local library; see `evidence/reports/SOURCE_MANIFEST.json`.\n", encoding="utf-8")


def main() -> None:
    safe_root()
    clean()
    provenance: dict[str, str] = {}
    media = make_images(provenance)
    videos = make_videos(provenance)
    make_wallpapers(media, videos, provenance)
    make_workflows(media, videos, provenance)
    inventory(provenance)
    print(f"Real-media fixture generation complete: {ROOT}")


if __name__ == "__main__":
    main()
