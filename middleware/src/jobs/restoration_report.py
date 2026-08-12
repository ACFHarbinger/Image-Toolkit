"""Structured diagnostic reports for restoration previews (deblur, masked inpainting).

`restore_cli.py`'s `--report` flag already writes a JSON preview report, but
builds it inline with a sharpness proxy (PIL's `FIND_EDGES` filter variance,
which measures edge strength, not literally "Laplacian"). This module is the
reusable, independently-testable extraction Gemini's Phase 3 delegation asked
for: a real discrete Laplacian convolution + variance, the standard
"variance of Laplacian" blur-detection diagnostic (Pech-Pacheco et al., 2000)
used across computer-vision blur-quality tooling.

Dependency-light: only imports PIL, lazily, inside the function body — no
module-level heavy import for callers that never need it (matches every
other module in `jobs/`/`models/`).
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

# 4-connected discrete Laplacian kernel: highlights local intensity change,
# so its variance across the image is a standard proxy for focus/sharpness —
# a blurred image has a small, tightly clustered Laplacian response; a sharp
# one has a wide spread of strong positive/negative edges.
_LAPLACIAN_KERNEL = (0, 1, 0, 1, -4, 1, 0, 1, 0)


def _laplacian_variance(image: Any) -> float:
    """Variance of the discrete Laplacian response — higher means sharper.

    PIL's `ImageFilter.Kernel` can't center a 3×3 kernel on a border pixel
    (no out-of-bounds neighbors to sample), so it leaves the outermost
    1-pixel ring unfiltered — passed through as the original source pixel
    value rather than a Laplacian response. Left uncropped, that ring's
    value (unrelated to blur) would dominate the variance for anything but
    a large image, and differs run-to-run based only on border content, not
    actual sharpness. Cropped out before computing variance.
    """
    from PIL import ImageFilter

    kernel = ImageFilter.Kernel((3, 3), _LAPLACIAN_KERNEL, scale=1, offset=0)
    grayscale = image.convert("L")
    laplacian = grayscale.filter(kernel)
    if laplacian.width <= 2 or laplacian.height <= 2:
        raise ValueError("image must be larger than 2x2 to compute a Laplacian sharpness score")
    interior = laplacian.crop((1, 1, laplacian.width - 1, laplacian.height - 1))
    values = list(interior.get_flattened_data())
    return float(statistics.pvariance(values))


def generate_restoration_report(
    input_path: str,
    output_path: str,
    metrics: dict[str, Any] | None = None,
    *,
    write_to: str | None = None,
) -> dict[str, Any]:
    """Build a JSON-serializable diagnostic report comparing two preview images.

    `metrics` is an optional dict of caller-supplied fields (operation name,
    backend, mask coverage, etc.) merged into the report as-is — this
    function only computes the image-derived sharpness diagnostics; callers
    own everything about *what operation* produced the images, matching this
    package's "no hidden side effects" convention for boundary functions.

    Returns the report dict always; if `write_to` is given, also writes it
    there as indented JSON (this is what `restore_cli.py --report` uses —
    `write_to` is opt-in so unit tests stay filesystem-free by default).

    Raises `FileNotFoundError` if either image path doesn't exist.
    """
    if not Path(input_path).is_file():
        raise FileNotFoundError(f"input image not found: {input_path}")
    if not Path(output_path).is_file():
        raise FileNotFoundError(f"output image not found: {output_path}")

    from PIL import Image

    input_image = Image.open(input_path)
    output_image = Image.open(output_path)
    input_sharpness = _laplacian_variance(input_image)
    output_sharpness = _laplacian_variance(output_image)

    report: dict[str, Any] = {
        "schema_version": 1,
        "preview_only": True,
        "sharpness_metric": "laplacian_variance",
        "input": str(Path(input_path).resolve()),
        "output": str(Path(output_path).resolve()),
        "input_size": list(input_image.size),
        "output_size": list(output_image.size),
        "input_sharpness": input_sharpness,
        "output_sharpness": output_sharpness,
        "sharpness_delta": output_sharpness - input_sharpness,
    }
    if metrics:
        report.update(metrics)

    if write_to:
        Path(write_to).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    return report
