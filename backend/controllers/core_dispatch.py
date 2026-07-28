"""`core` command group: format conversion, merging, and the legacy
in-`core`-namespace `stitch` subcommand (Hydra-config-aware; distinct from
the top-level `stitch` command in :mod:`backend.controllers.stitch_dispatch`).
"""

from __future__ import annotations

import os
import sys

import yaml

from backend.src.constants import BACKEND_DIR
from backend.src.core.image_converter import ImageFormatConverter
from backend.src.core.image_merger import ImageMerger


def dispatch_core(args: dict) -> None:
    command = args.get("core_command")
    if command == "convert":
        inputs = args.get("input")
        output = args.get("output")
        fmt = args.get("format")
        recursive = args.get("recursive", False)

        # Determine if single or batch
        if len(inputs) == 1 and os.path.isfile(inputs[0]):
            success = ImageFormatConverter.convert_single_image(
                image_path=inputs[0],
                output_name=output,
                format=fmt,
            )
            print(
                f"Conversion {'successful' if success else 'failed'}", file=sys.stderr
            )
        else:
            # Batch conversion — multiple inputs or a directory
            for input_path in inputs:
                if os.path.isdir(input_path):
                    ImageFormatConverter.convert_batch(
                        input_dir=input_path,
                        inputs_formats=[
                            "webp",
                            "png",
                            "jpg",
                            "jpeg",
                            "bmp",
                            "gif",
                            "tiff",
                            "avif",
                        ],
                        output_dir=output,
                        output_format=fmt,
                        recursive=recursive,
                    )
                elif os.path.isfile(input_path):
                    success = ImageFormatConverter.convert_single_image(
                        image_path=input_path,
                        output_name=output,
                        format=fmt,
                    )
    elif command == "stitch":
        # Load defaults from Hydra config if available
        config_path = os.path.join(BACKEND_DIR, "config", "core", "stitch.yaml")
        defaults = {}
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                defaults = yaml.safe_load(os.path.expandvars(f.read())) or {}

        inputs = args.get("input") or [defaults.get("input_dir")]
        output = args.get("output") or defaults.get(
            "output_path", "/tmp/stitched_panorama.png"
        )

        # Filter out None if both CLI and config are empty
        inputs = [i for i in inputs if i]
        if not inputs:
            print(
                "❌ Error: No input directory specified in CLI or stitch.yaml",
                file=sys.stderr,
            )
            return
        image_paths = []
        for inp in inputs:
            if os.path.isdir(inp):
                # Get images from dir, excluding the output file if it's in the same dir
                images = [
                    os.path.join(inp, f)
                    for f in os.listdir(inp)
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
                    and os.path.realpath(os.path.join(inp, f))
                    != os.path.realpath(output)
                ]
                image_paths.extend(sorted(images))
            elif os.path.isfile(inp):
                image_paths.append(inp)

        if len(image_paths) < 2:
            print("❌ Error: Need at least 2 images for stitching.", file=sys.stderr)
            return

        print(f"🚀 Starting Perfect Stitch on {len(image_paths)} frames...")
        merger = ImageMerger()
        try:
            # Use default settings from stitch.yaml via Hydra or explicit params
            # For now we use the merger's default which delegates to the pipeline
            merger.perfect_stitch(image_paths, output)
            print(f"✅ Panorama saved to: {output}")
        except Exception as e:
            print(f"❌ Stitching failed: {e}", file=sys.stderr)
    elif command == "merge":
        # Placeholder for other merge modes
        print("Merge command not yet fully connected to CLI", file=sys.stderr)
