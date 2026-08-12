"""Command-line entry point for HIE's local restoration baselines."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .jobs import (
    cpu_deblur_runner,
    cpu_masked_inpainting_runner,
    generate_restoration_report,
    opencv_masked_inpainting_runner,
    opencv_deblur_runner,
    submit_restoration_job,
)
from .jobs.cpu_restoration import validate_inpainting_mask


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hie-restore", description="HIE image restoration tools")
    subparsers = parser.add_subparsers(dest="operation", required=True)

    deblur = subparsers.add_parser("deblur", help="enhance a blurred image")
    deblur.add_argument("input", help="input image path")
    deblur.add_argument("--output", help="output preview path")
    deblur.add_argument("--strength", type=float, default=1.0)
    deblur.add_argument("--radius", type=float, default=1.2)
    deblur.add_argument("--backend", choices=("opencv", "pillow"), default="pillow")
    deblur.add_argument("--report", help="write a JSON preview report")

    inpaint = subparsers.add_parser("inpaint", help="remove a masked logo from an owned/licensed image")
    inpaint.add_argument("input", help="input image path")
    inpaint.add_argument("--mask", required=True, help="white-on-black mask image")
    inpaint.add_argument("--output", help="output preview path")
    inpaint.add_argument("--backend", choices=("auto", "opencv", "pillow"), default="auto")
    inpaint.add_argument("--permission-confirmed", action="store_true",
                         help="confirm that you own or may edit this image")
    inpaint.add_argument("--radius", type=float, default=3.0)
    inpaint.add_argument("--max-mask-coverage", type=float, default=0.5,
                         help="reject masks covering more than this fraction of the image")
    inpaint.add_argument("--report", help="write a JSON preview report")
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
            "max_mask_coverage": args.max_mask_coverage,
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
        if operation == "masked_inpainting":
            from PIL import Image

            with Image.open(args.mask) as mask_image:
                options["mask_coverage"] = validate_inpainting_mask(
                    mask_image, max_coverage=args.max_mask_coverage
                )
        handle = submit_restoration_job(operation, args.input, options=options, runner=runner)
        result = handle.result()
    except (ValueError, PermissionError, FileNotFoundError) as exc:
        print(f"hie-restore: {exc}", file=sys.stderr)
        return 2
    if not result.ok:
        print(f"hie-restore: {result.error}", file=sys.stderr)
        return 1
    if args.report:
        _write_report(args, result.value.output_ref, operation, options)
    print(result.value.output_ref)
    return 0


def _write_report(args: argparse.Namespace, output_ref: str, operation: str, options: dict) -> None:
    metrics = {"operation": operation, "backend": getattr(args, "backend", "pillow")}
    if operation == "masked_inpainting":
        metrics["mask_coverage"] = options["mask_coverage"]
        metrics["mask"] = str(Path(args.mask).resolve())
    generate_restoration_report(args.input, output_ref, metrics, write_to=args.report)


if __name__ == "__main__":
    raise SystemExit(main())
