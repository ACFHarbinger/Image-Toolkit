#!/usr/bin/env python3
"""Generate SHA256 checksums for all files in dist/release/."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


def generate_checksums() -> None:
    release_dir = ROOT_DIR / "dist" / "release"
    if not release_dir.exists():
        print(f"Release directory {release_dir} does not exist.")
        return

    checksum_file = release_dir / "SHA256SUMS.txt"
    lines = []

    for item in sorted(release_dir.iterdir()):
        if item.is_file() and item.name != "SHA256SUMS.txt":
            sha256 = hashlib.sha256()
            with item.open("rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256.update(chunk)
            digest = sha256.hexdigest()
            lines.append(f"{digest}  {item.name}")
            print(f"{digest}  {item.name}")

    if lines:
        checksum_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"✅ SHA256 checksums written to {checksum_file}")
    else:
        print("No artifacts found in release directory.")


if __name__ == "__main__":
    generate_checksums()
