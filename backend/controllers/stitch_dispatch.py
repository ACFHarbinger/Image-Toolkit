"""Top-level `stitch` command: single-sequence or `--batch-dir` mode over
:class:`~backend.src.animation.AnimeStitchPipeline` (distinct from the
`core stitch` subcommand in :mod:`backend.controllers.core_dispatch`, which
goes through :class:`~backend.src.core.image_merger.ImageMerger` instead)."""

from __future__ import annotations

import json
import os
import sys

_IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}


def _collect_image_paths(directory: str) -> list:
    """Return sorted image paths from a directory (non-recursive)."""
    return sorted(
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if os.path.splitext(f)[1].lower() in _IMG_EXTS
    )


def _run_single_stitch(image_paths: list, output: str, renderer: str) -> bool:
    """Run AnimeStitchPipeline on image_paths; return True on success."""
    from backend.src.animation import AnimeStitchPipeline

    pipeline = AnimeStitchPipeline(renderer=renderer)
    try:
        pipeline.run(image_paths=image_paths, output_path=output)
        return True
    except Exception as exc:
        print(f"  ❌ Stitching failed: {exc}", file=sys.stderr)
        return False


def dispatch_stitch(args: dict) -> None:  # noqa: C901
    batch_dir = (args.get("batch_dir") or "").strip()
    renderer = args.get("renderer") or "median"
    resume = bool(args.get("resume"))

    if batch_dir:
        # ── Batch mode ─────────────────────────────────────────────────────
        if not os.path.isdir(batch_dir):
            print(f"❌ --batch-dir '{batch_dir}' is not a directory.", file=sys.stderr)
            return

        suffix = (args.get("output_suffix") or "_stitched").strip()
        progress_path = os.path.join(batch_dir, ".stitch_progress.json")

        # Load progress state (Option E)
        progress: dict = {}
        if resume and os.path.isfile(progress_path):
            try:
                with open(progress_path) as f:
                    progress = json.load(f)
            except Exception:
                progress = {}

        subdirs = sorted(
            d.path
            for d in os.scandir(batch_dir)
            if d.is_dir() and not d.name.startswith(".")
        )
        if not subdirs:
            print(f"❌ No sub-directories found in '{batch_dir}'.", file=sys.stderr)
            return

        total = len(subdirs)
        done = skipped = failed = 0
        print(f"📂 Batch stitch: {total} sequence(s) in '{batch_dir}'")
        for i, seq_dir in enumerate(subdirs, 1):
            seq_name = os.path.basename(seq_dir)
            out_path = os.path.join(seq_dir, f"{seq_name}{suffix}.png")

            # Option C: resume — skip if output already exists
            if resume and (
                os.path.isfile(out_path) or progress.get(seq_name) == "done"
            ):
                print(f"  [{i}/{total}] ⏭  {seq_name}  (skipped — output exists)")
                skipped += 1
                continue

            image_paths = _collect_image_paths(seq_dir)
            if len(image_paths) < 2:
                print(
                    f"  [{i}/{total}] ⚠  {seq_name}  (skipped — fewer than 2 images)",
                    file=sys.stderr,
                )
                progress[seq_name] = "skipped"
                failed += 1
                continue

            print(
                f"  [{i}/{total}] 🚀 {seq_name}  ({len(image_paths)} frames) → {out_path}"
            )
            success = _run_single_stitch(image_paths, out_path, renderer)
            if success:
                print(f"  [{i}/{total}] ✅ {seq_name}")
                progress[seq_name] = "done"
                done += 1
            else:
                progress[seq_name] = "failed"
                failed += 1

            # Persist progress after each sequence (Option E)
            try:
                with open(progress_path, "w") as f:
                    json.dump(progress, f, indent=2)
            except Exception:
                pass

        print(f"\n📊 Batch complete: {done} done, {skipped} skipped, {failed} failed.")

    else:
        # ── Single-sequence mode ────────────────────────────────────────────
        inputs = args.get("input") or []
        output = (args.get("output") or "").strip() or "stitched_panorama.png"

        image_paths: list = []
        for inp in inputs:
            if os.path.isdir(inp):
                image_paths.extend(_collect_image_paths(inp))
            elif os.path.isfile(inp):
                image_paths.append(inp)

        if len(image_paths) < 2:
            print("❌ Need at least 2 images for stitching.", file=sys.stderr)
            return

        print(f"🚀 Stitching {len(image_paths)} frames → {output}")
        if _run_single_stitch(image_paths, output, renderer):
            print(f"✅ Panorama saved to: {output}")
