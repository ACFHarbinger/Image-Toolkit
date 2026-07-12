#!/usr/bin/env python3
"""
gui/resources/generate_qrc.py
Regenerate listing_images.qrc and thumbnail_cache.qrc from the live
~/.image-toolkit/ directories.

Usage:
    python generate_qrc.py [--data-dir <path>] [--out-dir <path>]

Options:
    --data-dir  Root of the image-toolkit data directory.
                Defaults to ~/.image-toolkit/
    --out-dir   Directory where .qrc files are written.
                Defaults to the directory containing this script.

The generated files can be compiled into binary .rcc packs with:
    rcc --binary listing_images.qrc   -o listing_images.rcc
    rcc --binary thumbnail_cache.qrc  -o thumbnail_cache.rcc

And loaded at runtime with:
    QResource.registerResource("listing_images.rcc")
    QResource.registerResource("thumbnail_cache.rcc")

After registration images are accessible as Qt resource paths:
    ":/listing-images/<uuid>.jpg"
    ":/thumbnail-cache/<hash>.jpg"
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom

IMAGE_EXTS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif"}
)

TARGETS: list[tuple[str, str, str]] = [
    ("listing-images",  "/listing-images",  "listing_images.qrc"),
    ("thumbnail-cache", "/thumbnail-cache", "thumbnail_cache.qrc"),
]


def build_qrc(dir_path: pathlib.Path, prefix: str, out_dir: pathlib.Path) -> str:
    """Return a pretty-printed QRC XML string for all images in *dir_path*.

    File paths in the generated XML are expressed as paths *relative to out_dir*
    (the directory where the .qrc file will be written).  This makes the file
    portable: the same committed .qrc works on any machine, regardless of the
    absolute home-directory path.
    """
    files = sorted(
        p for p in dir_path.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )

    root = ET.Element("RCC", version="1.0")
    qr   = ET.SubElement(root, "qresource", prefix=prefix)
    for f in files:
        el = ET.SubElement(qr, "file", alias=f.name)
        # Compute the path relative to the directory that will contain the .qrc
        # file so the XML contains no absolute/username-specific paths.
        el.text = pathlib.Path(
            os.path.relpath(f.resolve(), start=out_dir.resolve())
        ).as_posix()

    raw  = ET.tostring(root, encoding="unicode")
    dom  = minidom.parseString(raw)
    body = dom.toprettyxml(indent="    ", encoding=None)
    lines = body.splitlines()
    if lines[0].startswith("<?xml"):
        lines = lines[1:]
    return "<!DOCTYPE RCC>\n" + "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=pathlib.Path,
                        default=pathlib.Path.home() / ".image-toolkit",
                        help="Root data directory (default: ~/.image-toolkit/)")
    parser.add_argument("--out-dir",  type=pathlib.Path,
                        default=pathlib.Path(__file__).parent,
                        help="Output directory for .qrc files")
    args = parser.parse_args(argv)

    args.out_dir = args.out_dir.resolve()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for subdir, prefix, filename in TARGETS:
        src = args.data_dir / subdir
        if not src.is_dir():
            print(f"WARNING: {src} does not exist — skipping {filename}", file=sys.stderr)
            continue

        xml = build_qrc(src, prefix, args.out_dir)
        out = args.out_dir / filename
        out.write_text(xml)

        n = xml.count("<file ")
        print(f"Wrote {out}  ({n} images, prefix={prefix})")


if __name__ == "__main__":
    main()
