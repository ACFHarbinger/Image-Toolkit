"""Command-line entry point for HIE's local restoration baselines."""

from __future__ import annotations

import argparse
import sys

from .jobs import (
    cpu_deblur_runner,
    cpu_masked_inpainting_runner,
    opencv_masked_inpainting_runner,
    opencv_deblur_runner,
    submit_restoration_job,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hie-restore", description="HIE image restoration tools")
    subparsers = parser.add_subparsers(dest="operation", required=True)

    deblur = subparsers.add_parser("deblur", help="enhance a blurred image")
    deblur.add_argument("input", help="input image path")
    deblur.add_argument("--output", help="output preview path")
    deblur.add_argument("--strength", type=float, default=1.0)
    deblur.add_argument("--radius", type=float, default=1.2)
    deblur.add_argument("--backend", choices=("opencv", "pillow"), default="pillow")

    inpaint = subparsers.add_parser("inpaint", help="remove a masked logo from an owned/licensed image")
    inpaint.add_argument("input", help="input image path")
    inpaint.add_argument("--mask", required=True, help="white-on-black mask image")
    inpaint.add_argument("--output", help="output preview path")
    inpaint.add_argument("--backend", choices=("auto", "opencv", "pillow"), default="auto")
    inpaint.add_argument("--permission-confirmed", action="store_true",
                         help="confirm that you own or may edit this image")
    inpaint.add_argument("--radius", type=float, default=3.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.operation == "deblur":
        options = {"output_ref": args.output, "strength": args.strength, "radius": args.radius}
        runner = opencv_deblur_runner if args.backend == "opencv" else cpu_deblur_runner
        operation = "deblur"
    else:
        options = {
            "output_ref": args.output,
            "mask_ref": args.mask,
            "permission_confirmed": args.permission_confirmed,
            "radius": int(args.radius),
        }
        if args.backend == "opencv":
            runner = opencv_masked_inpainting_runner
        elif args.backend == "pillow":
            runner = cpu_masked_inpainting_runner
        else:
            try:
                import cv2  # noqa: F401
            except ImportError:
                runner = cpu_masked_inpainting_runner
            else:
                runner = opencv_masked_inpainting_runner
        operation = "masked_inpainting"

    try:
        handle = submit_restoration_job(operation, args.input, options=options, runner=runner)
        result = handle.result()
    except (ValueError, PermissionError, FileNotFoundError) as exc:
        print(f"hie-restore: {exc}", file=sys.stderr)
        return 2
    if not result.ok:
        print(f"hie-restore: {result.error}", file=sys.stderr)
        return 1
    print(result.value.output_ref)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
