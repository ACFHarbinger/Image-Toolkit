#!/usr/bin/env python3
"""Generate the external media corpus used by the desktop release checklist."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path("/home/pkhunter/Downloads/Data/Tests/release-1.0.0").resolve()
TESTS_ROOT = Path("/home/pkhunter/Downloads/Data/Tests").resolve()


def ensure_safe_root() -> None:
    if ROOT.parent != TESTS_ROOT or ROOT.name != "release-1.0.0":
        raise RuntimeError(f"Refusing unsafe fixture root: {ROOT}")
    ROOT.mkdir(parents=True, exist_ok=True)


def label_image(
    size: tuple[int, int],
    seed: int,
    label: str,
    *,
    alpha: bool = False,
) -> Image.Image:
    width, height = size
    yy, xx = np.indices((height, width))
    r = (xx * 255 // max(1, width - 1) + seed * 37) % 256
    g = (yy * 255 // max(1, height - 1) + seed * 71) % 256
    b = ((xx + yy) * 127 // max(1, width + height - 2) + seed * 19) % 256
    rgb = np.stack((r, g, b), axis=-1).astype(np.uint8)
    image = Image.fromarray(rgb, "RGB")
    if alpha:
        image = image.convert("RGBA")
        a = np.full((height, width), 220, dtype=np.uint8)
        a[((xx // 32 + yy // 32) % 2) == 0] = 90
        image.putalpha(Image.fromarray(a, "L"))
    draw = ImageDraw.Draw(image)
    margin = max(8, min(width, height) // 20)
    draw.rounded_rectangle(
        (margin, margin, width - margin, height - margin),
        radius=max(6, margin),
        outline=(255, 255, 255, 255) if alpha else "white",
        width=max(2, margin // 3),
    )
    draw.rectangle(
        (margin * 2, height // 3, width - margin * 2, height * 2 // 3),
        fill=(15, 18, 28, 190) if alpha else (15, 18, 28),
    )
    draw.text((margin * 3, height // 2 - 7), label, fill="white")
    return image


def save(image: Image.Image, path: Path, **kwargs) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, **kwargs)


def copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def create_images() -> None:
    root = ROOT / "images"
    landscape = label_image((640, 360), 1, "Landscape PNG 640x360")
    portrait = label_image((360, 640), 2, "Portrait JPEG 360x640")
    square = label_image((384, 384), 3, "Square WebP 384x384")
    transparent = label_image((512, 320), 4, "Transparent RGBA", alpha=True)

    save(landscape, root / "landscape.png")
    save(portrait, root / "portrait.jpg", quality=88)
    save(square, root / "square.webp", quality=86)
    save(label_image((512, 288), 5, "Bitmap BMP"), root / "bitmap.bmp")
    save(label_image((420, 300), 6, "Tagged TIFF"), root / "tagged.tiff")
    save(transparent, root / "transparent.png")
    save(
        label_image((480, 320), 7, "Unicode + spaces"),
        root / "café 東京 sample.webp",
        quality=88,
    )

    gif_frames = [
        label_image((320, 180), 20 + index, f"GIF frame {index + 1}")
        for index in range(8)
    ]
    gif_frames[0].save(
        root / "animated.gif",
        save_all=True,
        append_images=gif_frames[1:],
        duration=120,
        loop=0,
        disposal=2,
    )

    duplicate_a = root / "duplicate-a.png"
    duplicate_b = root / "duplicate-b.png"
    save(label_image((500, 300), 8, "Exact duplicate"), duplicate_a)
    copy(duplicate_a, duplicate_b)
    copy(duplicate_a, root / "duplicates" / "duplicate-a.png")
    copy(duplicate_b, root / "duplicates" / "duplicate-b.png")

    near_source = label_image((640, 400), 9, "Near duplicate source")
    save(near_source, root / "near-original.jpg", quality=95)
    save(near_source.resize((608, 380)), root / "near-resized.jpg", quality=90)
    save(near_source, root / "near-recompressed.jpg", quality=58)
    for name in ("near-original.jpg", "near-resized.jpg", "near-recompressed.jpg"):
        copy(root / name, root / "near-duplicates" / name)

    copy(root / "café 東京 sample.webp", root / "unicode-and-spaces" / "café 東京 sample.webp")
    (root / "corrupt-image.jpg").write_bytes(b"not a jpeg\x00\xfffixture")
    (root / "truncated.png").write_bytes(b"\x89PNG\r\n\x1a\ntruncated")
    copy(root / "corrupt-image.jpg", root / "corrupt" / "corrupt-image.jpg")

    for index in range(12):
        save(
            label_image((256, 192), 100 + index, f"Disposable {index + 1:02d}"),
            root / "disposable" / f"disposable_{index + 1:02d}.png",
        )


def create_sheets() -> None:
    root = ROOT / "sheets"
    tiles = [label_image((96, 72), 200 + i, f"F{i + 1}") for i in range(6)]

    vertical = Image.new("RGB", (96, 72 * 6))
    horizontal = Image.new("RGB", (96 * 6, 72))
    grid = Image.new("RGB", (96 * 3, 72 * 2))
    for index, tile in enumerate(tiles):
        vertical.paste(tile, (0, index * 72))
        horizontal.paste(tile, (index * 96, 0))
        grid.paste(tile, ((index % 3) * 96, (index // 3) * 72))

    bordered = Image.new("RGB", (20 + 3 * 96 + 2 * 12 + 20, 20 + 2 * 72 + 12 + 20), "#20242c")
    for index, tile in enumerate(tiles):
        x = 20 + (index % 3) * (96 + 12)
        y = 20 + (index // 3) * (72 + 12)
        bordered.paste(tile, (x, y))

    partial = Image.new("RGB", (96 * 2 + 44, 72), "#ff00ff")
    partial.paste(tiles[0], (0, 0))
    partial.paste(tiles[1], (96, 0))
    partial.paste(tiles[2].crop((0, 0, 44, 72)), (192, 0))

    fixtures = {
        "vertical-strip.png": (vertical, "vertical"),
        "horizontal-strip.png": (horizontal, "horizontal"),
        "regular-grid.png": (grid, "grid"),
        "bordered-guttered-grid.png": (bordered, "bordered-guttered"),
        "partial-final-frame.png": (partial, "partial-final-frame"),
    }
    for name, (image, subdirectory) in fixtures.items():
        save(image, root / name)
        copy(root / name, root / subdirectory / name)


def ffmpeg_video(
    output: Path,
    *,
    size: str,
    duration: int,
    audio: bool,
    rate: int = 24,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={size}:rate={rate}:duration={duration}",
    ]
    if audio:
        command += [
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=48000:duration={duration}",
        ]
    command += [
        "-t",
        str(duration),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "27",
        "-pix_fmt",
        "yuv420p",
    ]
    if audio:
        command += ["-c:a", "aac", "-b:a", "96k", "-shortest"]
    else:
        command += ["-an"]
    command.append(str(output))
    run(command)


def create_videos() -> None:
    root = ROOT / "video"
    videos = [
        ("short-with-audio.mp4", "640x360", 6, True, "with-audio"),
        ("short-silent.mp4", "480x270", 5, False, "silent"),
        ("portrait.mp4", "360x640", 5, True, "portrait"),
        ("long-cancel.mp4", "960x540", 60, True, "long-cancel"),
    ]
    for name, size, duration, audio, subdirectory in videos:
        target = root / name
        ffmpeg_video(target, size=size, duration=duration, audio=audio)
        copy(target, root / subdirectory / name)


def create_wallpapers() -> None:
    source_video = ROOT / "video" / "short-silent.mp4"
    for gallery_index, gallery_name in enumerate(("wallpaper-a", "wallpaper-b")):
        root = ROOT / gallery_name
        for index in range(104):
            image = label_image(
                (640, 360),
                500 + gallery_index * 200 + index,
                f"{gallery_name} {index + 1:03d}",
            )
            extension = ("jpg", "png", "webp")[index % 3]
            kwargs = {"quality": 82} if extension in {"jpg", "webp"} else {}
            save(image, root / f"wallpaper_{index + 1:03d}.{extension}", **kwargs)

        for gif_index in range(4):
            frames = [
                label_image(
                    (400, 225),
                    900 + gallery_index * 50 + gif_index * 8 + frame,
                    f"{gallery_name} GIF {gif_index + 1} / {frame + 1}",
                )
                for frame in range(6)
            ]
            frames[0].save(
                root / f"animated_{gif_index + 1:02d}.gif",
                save_all=True,
                append_images=frames[1:],
                duration=140,
                loop=0,
            )

        copy(source_video, root / "video_wallpaper_01.mp4")
        copy(source_video, root / "video_wallpaper_02.mp4")
        (root / "unsupported.txt").write_text("unsupported fixture\n", encoding="utf-8")
        (root / "corrupt.jpg").write_bytes(b"corrupt wallpaper fixture")


def create_stitch_fixtures() -> None:
    root = ROOT / "stitch"
    panorama = label_image((1400, 300), 1200, "Synthetic overlapping panorama")
    draw = ImageDraw.Draw(panorama)
    for x in range(50, 1400, 100):
        draw.line((x, 20, x, 280), fill="white", width=3)
        draw.ellipse((x - 18, 45, x + 18, 81), outline="yellow", width=4)
        draw.text((x - 12, 250), str(x), fill="white")
    save(panorama, root / "panorama-reference.png")

    ordered_paths: list[Path] = []
    for index, x in enumerate((0, 240, 480, 720, 960), start=1):
        crop = panorama.crop((x, 0, x + 440, 300))
        path = root / "ordered" / f"frame_{index:03d}.png"
        save(crop, path)
        ordered_paths.append(path)

    for output_index, source_index in enumerate((2, 0, 4, 1, 3), start=1):
        copy(
            ordered_paths[source_index],
            root / "shuffled" / f"shuffled_{output_index:03d}.png",
        )
    save(
        label_image((440, 300), 1300, "Weak non-overlapping frame"),
        root / "weak-nonoverlap" / "weak_frame.png",
    )

    output = root / "video" / "stitch-source.mp4"
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-framerate",
            "1",
            "-i",
            str(root / "ordered" / "frame_%03d.png"),
            "-vf",
            "fps=24,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "24",
            str(output),
        ]
    )


def create_manga_fixtures() -> None:
    root = ROOT / "manga"
    canvas = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((120, 70, 390, 360), outline="black", width=8)
    draw.ellipse((185, 165, 220, 205), fill="black")
    draw.ellipse((290, 165, 325, 205), fill="black")
    draw.arc((205, 195, 310, 285), 15, 165, fill="black", width=7)
    draw.polygon(((80, 500), (160, 320), (350, 320), (440, 500)), outline="black")
    draw.line((256, 70, 256, 20), fill="black", width=6)
    draw.text((16, 16), "LINE ART", fill="black")
    save(canvas, root / "line-art" / "character-line-art.png")
    copy(root / "line-art" / "character-line-art.png", root / "line-art.png")

    reference = canvas.copy()
    ref_draw = ImageDraw.Draw(reference)
    ref_draw.ellipse((128, 78, 382, 352), fill="#f5c7a9", outline="black", width=8)
    ref_draw.polygon(((80, 500), (160, 320), (350, 320), (440, 500)), fill="#3366cc", outline="black")
    ref_draw.ellipse((185, 165, 220, 205), fill="#224466")
    ref_draw.ellipse((290, 165, 325, 205), fill="#224466")
    save(reference, root / "color-reference" / "character-reference.png")
    copy(root / "color-reference" / "character-reference.png", root / "color-reference.png")

    for index in range(8):
        frame = Image.new("RGB", (512, 512), "white")
        frame_draw = ImageDraw.Draw(frame)
        offset = index * 8
        frame_draw.ellipse((90 + offset, 150, 250 + offset, 310), outline="black", width=7)
        frame_draw.rectangle((130 + offset, 305, 210 + offset, 450), outline="black", width=7)
        frame_draw.text((16, 16), f"SEQUENCE {index + 1:02d}", fill="black")
        save(frame, root / "sequences" / f"line_frame_{index + 1:03d}.png")

    maskable = Image.new("RGB", (512, 512), "#d7e8ff")
    mask_draw = ImageDraw.Draw(maskable)
    mask_draw.ellipse((120, 80, 400, 430), fill="#e84a5f", outline="white", width=8)
    mask_draw.rectangle((200, 180, 320, 390), fill="#2a363b")
    mask_draw.text((16, 16), "MASKABLE FOREGROUND", fill="#111111")
    save(maskable, root / "maskable" / "maskable-foreground.png")
    copy(root / "maskable" / "maskable-foreground.png", root / "maskable-foreground.png")


def create_listing_fixtures() -> None:
    root = ROOT / "listings"
    source = ROOT / "video" / "short-with-audio.mp4"
    for series_name, episode_count in (("Fixture_Series", 3), ("Unicode_Série", 2)):
        for episode in range(1, episode_count + 1):
            copy(
                source,
                root
                / "series-videos"
                / series_name
                / f"{series_name.replace('_', ' ')} - {episode:02d}.mp4",
            )

    entity_names = ("Ada Lovelace 01", "Grace Hopper 02", "Alan Turing 03")
    for index, name in enumerate(entity_names):
        image = label_image((320, 420), 1500 + index, name)
        save(image, root / "entity-images" / f"{name}.png")
        subdirectory = root / "entity-images" / name.rsplit(" ", 1)[0].replace(" ", "_")
        save(image, subdirectory / "profile.png")


def create_model_datasets() -> None:
    datasets = ROOT / "models" / "datasets"
    for index in range(12):
        image = label_image((256, 256), 1700 + index, f"LoRA subject {index + 1:02d}")
        image_path = datasets / "lora" / f"subject_{index + 1:03d}.png"
        save(image, image_path)
        image_path.with_suffix(".txt").write_text(
            f"fixture_subject, geometric portrait, sample {index + 1}\n",
            encoding="utf-8",
        )

    for dataset_name, size, count in (
        ("r3gan", (64, 64), 24),
        ("basic-gan", (64, 64), 24),
        ("evaluation", (299, 299), 16),
    ):
        for index in range(count):
            save(
                label_image(size, 1800 + index, f"{dataset_name} {index + 1}"),
                datasets / dataset_name / f"sample_{index + 1:03d}.png",
            )

    zip_path = datasets / "r3gan-fixture.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((datasets / "r3gan").glob("*.png")):
            archive.write(path, arcname=path.name)

    (ROOT / "models" / "checkpoints" / "README.md").write_text(
        "# Checkpoints\n\n"
        "Add known-good, licensed checkpoints for enabled backends here. "
        "No fake checkpoint is supplied because a loadable container with "
        "incorrect weights would create misleading acceptance results.\n",
        encoding="utf-8",
    )


def create_identity_and_search_fixtures() -> None:
    identities = ROOT / "entity-recon" / "identities"
    colors = (("identity-a", "#e84a5f"), ("identity-b", "#2a7fff"))
    held_out_sources: list[tuple[str, Image.Image]] = []
    for name, color in colors:
        for index in range(6):
            image = Image.new("RGB", (360, 360), "#f4f4f4")
            draw = ImageDraw.Draw(image)
            shift = index * 3
            draw.ellipse((70 + shift, 45, 290 + shift, 265), fill=color, outline="#111111", width=6)
            draw.ellipse((130 + shift, 120, 155 + shift, 145), fill="white")
            draw.ellipse((205 + shift, 120, 230 + shift, 145), fill="white")
            draw.arc((135 + shift, 145, 225 + shift, 220), 15, 165, fill="white", width=6)
            draw.text((12, 12), f"{name} sample {index + 1}", fill="#111111")
            save(image, identities / name / f"sample_{index + 1:02d}.png")
            if index == 5:
                held_out_sources.append((name, image))

    for name, image in held_out_sources:
        save(image, ROOT / "entity-recon" / "held-out" / f"{name}-query.png")
    for index in range(4):
        save(
            label_image((360, 360), 2000 + index, f"Unsorted {index + 1}"),
            ROOT / "entity-recon" / "unsorted" / f"unsorted_{index + 1:02d}.png",
        )

    copy(
        ROOT / "images" / "landscape.png",
        ROOT / "reverse-search" / "queries" / "known-landscape.png",
    )
    copy(
        ROOT / "entity-recon" / "held-out" / "identity-a-query.png",
        ROOT / "reverse-search" / "queries" / "identity-query.png",
    )


def create_http_and_disposable_fixtures() -> None:
    http = ROOT / "http-fixture"
    (http / "text" / "response.txt").write_text(
        "Image-Toolkit deterministic HTTP fixture.\n", encoding="utf-8"
    )
    (http / "json" / "response.json").write_text(
        json.dumps({"ok": True, "fixture": "release-1.0.0", "items": [1, 2, 3]}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (http / "errors" / "404.json").write_text(
        json.dumps({"error": "fixture not found", "status": 404}, indent=2) + "\n",
        encoding="utf-8",
    )
    (http / "delayed" / "response.txt").write_text(
        "Serve this route with an artificial delay for cancellation testing.\n",
        encoding="utf-8",
    )
    (http / "binary" / "payload.bin").write_bytes(bytes(range(256)) * 4)
    copy(ROOT / "images" / "transparent.png", http / "binary" / "fixture-image.png")

    for directory in (
        ROOT / "disposable" / "delete-files",
        ROOT / "disposable" / "delete-directories" / "remove-me",
        ROOT / "disposable" / "similarity",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    for index in range(4):
        copy(
            ROOT / "images" / "disposable" / f"disposable_{index + 1:02d}.png",
            ROOT / "disposable" / "delete-files" / f"delete_{index + 1:02d}.png",
        )
    copy(
        ROOT / "images" / "duplicate-a.png",
        ROOT / "disposable" / "similarity" / "exact-a.png",
    )
    copy(
        ROOT / "images" / "duplicate-b.png",
        ROOT / "disposable" / "similarity" / "exact-b.png",
    )
    copy(
        ROOT / "images" / "near-recompressed.jpg",
        ROOT / "disposable" / "similarity" / "near.jpg",
    )
    copy(
        ROOT / "images" / "corrupt-image.jpg",
        ROOT / "disposable" / "failures" / "corrupt-input.jpg",
    )
    copy(
        ROOT / "images" / "disposable" / "disposable_05.png",
        ROOT / "disposable" / "delete-directories" / "remove-me" / "contained-file.png",
    )


def create_sync_fixtures() -> None:
    cloud = ROOT / "cloud-sync"
    copy(ROOT / "images" / "landscape.png", cloud / "local" / "local-only.png")
    copy(ROOT / "images" / "portrait.jpg", cloud / "remote" / "remote-only.jpg")
    local_shared = cloud / "local" / "shared" / "conflict.txt"
    remote_shared = cloud / "remote" / "shared" / "conflict.txt"
    local_shared.parent.mkdir(parents=True, exist_ok=True)
    remote_shared.parent.mkdir(parents=True, exist_ok=True)
    local_shared.write_text("newer local fixture\n", encoding="utf-8")
    remote_shared.write_text("older remote fixture\n", encoding="utf-8")

    sync = ROOT / "local-directory-sync"
    copy(ROOT / "images" / "square.webp", sync / "local" / "local-only.webp")
    copy(ROOT / "images" / "transparent.png", sync / "remote" / "remote-only.png")
    sync_local = sync / "local" / "conflict" / "same-name.txt"
    sync_remote = sync / "remote" / "conflict" / "same-name.txt"
    sync_local.parent.mkdir(parents=True, exist_ok=True)
    sync_remote.parent.mkdir(parents=True, exist_ok=True)
    sync_local.write_text("local version\n", encoding="utf-8")
    sync_remote.write_text("remote version\n", encoding="utf-8")

    old_timestamp = 1_700_000_000
    new_timestamp = 1_800_000_000
    os.utime(remote_shared, (old_timestamp, old_timestamp))
    os.utime(local_shared, (new_timestamp, new_timestamp))
    os.utime(sync_remote, (old_timestamp, old_timestamp))
    os.utime(sync_local, (new_timestamp, new_timestamp))

    denylist = sync / "local" / ".image-toolkit"
    dummy_files = {
        denylist / "cache" / "thumbnail.cache": "dummy cache; must not sync\n",
        denylist / "logs" / "application.log": "dummy log; must not sync\n",
        denylist / "secrets" / "fixture.key": "NOT-A-KEY; denylist fixture only\n",
        denylist / "cryptography" / "fixture.vault": "NOT-A-VAULT; denylist fixture only\n",
        sync / "excluded" / "custom-excluded.txt": "custom exclude fixture\n",
    }
    for path, contents in dummy_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")


def probe_video(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def write_inventory() -> None:
    excluded = {
        ROOT / "README.md",
        ROOT / "generate_fixtures.py",
        ROOT / "evidence" / "checksums" / "SHA256SUMS.txt",
        ROOT / "evidence" / "reports" / "FIXTURE_MANIFEST.json",
    }
    files = sorted(path for path in ROOT.rglob("*") if path.is_file() and path not in excluded)
    checksums = []
    suffix_counts: Counter[str] = Counter()
    total_bytes = 0
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        relative = path.relative_to(ROOT).as_posix()
        checksums.append(f"{digest}  {relative}")
        suffix_counts[path.suffix.lower() or "<none>"] += 1
        total_bytes += path.stat().st_size

    checksum_path = ROOT / "evidence" / "checksums" / "SHA256SUMS.txt"
    checksum_path.write_text("\n".join(checksums) + "\n", encoding="utf-8")

    video_paths = sorted((ROOT / "video").glob("*.mp4"))
    manifest = {
        "fixture_root": str(ROOT),
        "file_count_excluding_inventory": len(files),
        "total_bytes_excluding_inventory": total_bytes,
        "suffix_counts": dict(sorted(suffix_counts.items())),
        "wallpaper_counts": {
            name: len([path for path in (ROOT / name).iterdir() if path.is_file()])
            for name in ("wallpaper-a", "wallpaper-b")
        },
        "videos": {
            path.name: probe_video(path)
            for path in video_paths
        },
        "intentional_invalid_files": [
            "images/corrupt-image.jpg",
            "images/truncated.png",
            "wallpaper-a/corrupt.jpg",
            "wallpaper-a/unsupported.txt",
            "wallpaper-b/corrupt.jpg",
            "wallpaper-b/unsupported.txt",
        ],
        "checkpoint_note": "Supply known-good licensed checkpoints separately.",
    }
    manifest_path = ROOT / "evidence" / "reports" / "FIXTURE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    (ROOT / "README.md").write_text(
        "# Image-Toolkit release 1.0.0 fixtures\n\n"
        "Generated deterministic media for `docs/RELEASE_CHECKLIST.md`.\n\n"
        "- Browse `images/`, `video/`, `wallpaper-a/`, and `wallpaper-b/` directly.\n"
        "- Sprite sheets are in `sheets/`; known overlap sequences are in `stitch/`.\n"
        "- Destructive tests must use `disposable/` only.\n"
        "- `permissions/unwritable/` is mode 0555 for error-path tests.\n"
        "- Counts and video probes are in `evidence/reports/FIXTURE_MANIFEST.json`.\n"
        "- SHA-256 hashes are in `evidence/checksums/SHA256SUMS.txt`.\n"
        "- Regenerate with `backend/release/generate_release_fixtures.py` from the repository.\n"
        "- Real model checkpoints, service credentials, remote data, and vault accounts are not fabricated.\n",
        encoding="utf-8",
    )


def main() -> None:
    ensure_safe_root()
    create_images()
    create_sheets()
    create_videos()
    create_wallpapers()
    create_stitch_fixtures()
    create_manga_fixtures()
    create_listing_fixtures()
    create_model_datasets()
    create_identity_and_search_fixtures()
    create_http_and_disposable_fixtures()
    create_sync_fixtures()
    write_inventory()
    print(f"Fixture generation complete: {ROOT}")


if __name__ == "__main__":
    main()
