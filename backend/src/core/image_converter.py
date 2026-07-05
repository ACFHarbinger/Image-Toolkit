import glob
import os
from typing import Callable, List, Optional

import base  # The new C++ extension

from backend.src.core.file_system_entries import FSETool

# Define the decorator factories needed for the format conversion methods
SINGLE_CONVERSION_PREFIX = FSETool.prefix_create_directory(
    arg_id=2, kwarg_name="output_name", is_filepath=True
)

BATCH_CONVERSION_PREFIX = FSETool.prefix_create_directory(
    arg_id=3, kwarg_name="output_dir", is_filepath=False
)


class ImageFormatConverter:
    """
    A wrapper around the C++ 'base' extension for converting image formats
    and adjusting aspect ratios.
    """

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=SINGLE_CONVERSION_PREFIX)
    def convert_single_image(
        cls,
        image_path: str,
        output_name: str = None,
        format: str = "png",
        delete: bool = False,
        aspect_ratio: Optional[float] = None,
        ar_mode: str = "crop",
    ) -> bool:
        """
        Converts a single image file using the C++ backend.
        """
        from backend.src.constants.app import SUPPORTED_IMG_FORMATS
        fmt = format.lower()
        if fmt not in SUPPORTED_IMG_FORMATS:
            raise ValueError(f"Unsupported image format: {format}")

        if not os.path.exists(image_path):
            raise ValueError(f"Failed to open file: {image_path}")

        filename_only = os.path.splitext(os.path.basename(image_path))[0]

        if output_name is None:
            output_path = os.path.join(
                os.path.dirname(image_path), f"{filename_only}.{format}"
            )
        else:
            # output_name is the path provided by the worker.
            # Check if it already includes the expected extension to prevent duplication.
            if output_name.lower().endswith(f".{format.lower()}"):
                output_path = output_name
            else:
                output_path = f"{output_name}.{format}"

        # The C++ backend raises a PyValueError on failure which will be caught by the worker
        res = base.convert_single_image(
            image_path,
            output_path,
            format,
            delete,
            aspect_ratio,
            ar_mode,
        )

        if res and not os.path.exists(output_path):
            # Try to rename if C++ saved it with alternative jpeg extension
            if output_path.lower().endswith(".jpeg"):
                alt_path = output_path[:-5] + ".jpg"
                if os.path.exists(alt_path):
                    os.rename(alt_path, output_path)
            elif output_path.lower().endswith(".jpg"):
                alt_path = output_path[:-4] + ".jpeg"
                if os.path.exists(alt_path):
                    os.rename(alt_path, output_path)

        return res

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=BATCH_CONVERSION_PREFIX)
    def convert_batch(
        cls,
        input_dir: str,
        inputs_formats: List[str],
        output_dir: str = None,
        output_format: str = "png",
        delete: bool = False,
        aspect_ratio: Optional[float] = None,
        ar_mode: str = "crop",
        output_filename_prefix: str = "",
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> List[str]:
        """
        Converts all images in a directory matching input_formats using the C++ backend.
        Returns a list of successful output paths.
        """
        if not os.path.exists(input_dir):
            raise PermissionError(f"Permission denied: {input_dir}")

        from backend.src.constants.app import SUPPORTED_IMG_FORMATS
        output_fmt = output_format.lower()
        if output_fmt not in SUPPORTED_IMG_FORMATS:
            raise ValueError(f"Unsupported output format: {output_format}")

        if output_dir is None:
            output_dir = input_dir

        def is_jpeg_or_jpg(fmt: str) -> bool:
            return fmt in ["jpg", "jpeg"]

        input_formats = [f.lower() for f in inputs_formats]

        # --- Collect all paths ---
        all_paths = []
        for input_format in input_formats:
            all_paths.extend(glob.glob(os.path.join(input_dir, f"*.{input_format}")))

        # Filter paths if no conversion needed
        if aspect_ratio is None:
            filtered_paths = []
            for input_file in all_paths:
                file_ext = os.path.splitext(input_file)[1].lstrip(".").lower()
                if not (
                    file_ext == output_fmt
                    or (is_jpeg_or_jpg(file_ext) and is_jpeg_or_jpg(output_fmt))
                ):
                    filtered_paths.append(input_file)
            all_paths = filtered_paths

        total_files = len(all_paths)
        if total_files == 0:
            return []

        if progress_callback:
            progress_callback(10)  # Started

        # --- Prepare Path Pairs ---
        image_pairs = []
        for idx, input_file in enumerate(all_paths):
            filename_base = os.path.splitext(os.path.basename(input_file))[0]

            if output_filename_prefix:
                output_filename = f"{output_filename_prefix}{idx + 1}" if total_files > 1 else output_filename_prefix
            else:
                output_filename = filename_base

            output_path = os.path.join(output_dir, f"{output_filename}.{output_format}")
            if (
                output_filename_prefix
                or aspect_ratio
                or not os.path.exists(output_path)
            ):
                image_pairs.append((input_file, output_path))

        if not image_pairs:
            if progress_callback:
                progress_callback(100)
            return []

        # --- Call C++ Backend ---
        try:
            results = base.convert_image_batch(
                image_pairs=image_pairs,
                output_format=output_format,
                delete_original=delete,
                aspect_ratio=aspect_ratio,
                ar_mode=ar_mode,
            )

            # Fix up jpg/jpeg extensions if necessary
            final_results = []
            for path in results:
                if not os.path.exists(path):
                    if path.lower().endswith(".jpeg"):
                        alt = path[:-5] + ".jpg"
                        if os.path.exists(alt):
                            os.rename(alt, path)
                            final_results.append(path)
                            continue
                    elif path.lower().endswith(".jpg"):
                        alt = path[:-4] + ".jpeg"
                        if os.path.exists(alt):
                            os.rename(alt, path)
                            final_results.append(path)
                            continue
                final_results.append(path)

            if progress_callback:
                progress_callback(100)

            print(f"\nBatch processing complete! Processed {len(final_results)} images.")
            return final_results

        except Exception as e:
            print(f"Error in convert_batch: {e}")
            return []
