"""
Contact Sheet Generator (§2.19B).

Composites a list of image paths into a structured grid proof sheet
with customizable columns, thumbnail dimensions, padding, margins,
background color, and filename labels using Pillow.
"""

from __future__ import annotations

import math
import os
from typing import Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont


def generate_contact_sheet(
    image_paths: Sequence[str],
    columns: int = 4,
    thumb_size: Tuple[int, int] = (256, 256),
    padding: int = 12,
    margin: int = 24,
    bg_color: Tuple[int, int, int] = (30, 30, 30),
    show_labels: bool = True,
    label_color: Tuple[int, int, int] = (220, 220, 220),
    output_path: Optional[str] = None,
) -> Image.Image:
    """Generate a Pillow Image contact sheet from *image_paths*.

    Args:
        image_paths: List of image file paths to tile.
        columns: Number of grid columns (>= 1).
        thumb_size: (width, height) box for each thumbnail.
        padding: Gap in pixels between adjacent cells.
        margin: Outer canvas border in pixels.
        bg_color: RGB tuple for canvas background.
        show_labels: Whether to print filenames below each thumbnail.
        label_color: RGB tuple for label text.
        output_path: Optional file path to save the generated image to.

    Returns:
        The composited PIL.Image instance.
    """
    valid_paths = [p for p in image_paths if os.path.isfile(p)]
    if not valid_paths:
        raise ValueError("No valid image files provided for contact sheet generation.")

    columns = max(1, columns)
    num_images = len(valid_paths)
    rows = math.ceil(num_images / columns)

    thumb_w, thumb_h = thumb_size
    label_h = 24 if show_labels else 0
    cell_w = thumb_w
    cell_h = thumb_h + label_h

    total_w = 2 * margin + columns * cell_w + (columns - 1) * padding
    total_h = 2 * margin + rows * cell_h + (rows - 1) * padding

    # Create master canvas
    sheet = Image.new("RGB", (total_w, total_h), bg_color)
    draw = ImageDraw.Draw(sheet)

    # Attempt to load a clean default font
    font = None
    if show_labels:
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

    for idx, path in enumerate(valid_paths):
        col_idx = idx % columns
        row_idx = idx // columns

        cell_x = margin + col_idx * (cell_w + padding)
        cell_y = margin + row_idx * (cell_h + padding)

        try:
            with Image.open(path) as img:
                # Convert to RGB if palette or alpha
                img_rgb = img.convert("RGB") if img.mode in ("RGBA", "LA", "P") else img.copy()

                # Calculate aspect-ratio preserving fit inside (thumb_w, thumb_h)
                img_rgb.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                w, h = img_rgb.size

                # Center within thumbnail area
                offset_x = cell_x + (thumb_w - w) // 2
                offset_y = cell_y + (thumb_h - h) // 2
                sheet.paste(img_rgb, (offset_x, offset_y))

        except Exception:
            # Draw placeholder error box if corrupted or unreadable
            draw.rectangle(
                [cell_x, cell_y, cell_x + thumb_w, cell_y + thumb_h],
                outline=(200, 80, 80),
                width=1,
            )
            draw.text(
                (cell_x + 8, cell_y + thumb_h // 2 - 6),
                "Error loading",
                fill=(200, 80, 80),
                font=font,
            )

        # Draw label
        if show_labels:
            filename = os.path.basename(path)
            # Truncate filename if overly long
            if len(filename) > 32:
                filename = filename[:14] + "…" + filename[-14:]

            text_y = cell_y + thumb_h + 4
            draw.text(
                (cell_x + 4, text_y),
                filename,
                fill=label_color,
                font=font,
            )

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        sheet.save(output_path)

    return sheet


__all__ = ["generate_contact_sheet"]
