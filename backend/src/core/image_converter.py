import os
import glob
from typing import List, Optional, Callable
import base  # The new Rust extension
from . import FSETool

# Define the decorator factories needed for the format conversion methods
SINGLE_CONVERSION_PREFIX = FSETool.prefix_create_directory(
    arg_id=2, kwarg_name="output_name", is_filepath=True
)

BATCH_CONVERSION_PREFIX = FSETool.prefix_create_directory(
    arg_id=3, kwarg_name="output_dir", is_filepath=False
)


class ImageFormatConverter:
    """
    A wrapper around the Rust 'base' extension for converting image formats
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
        Converts a single image file using the Rust backend.
        """
        filename_only = os.path.splitext(os.path.basename(image_path))[0]

        if output_name is None:
            output_path = os.path.join(
                os.path.dirname(image_path), f"{filename_only}.{format}"
            )
        else:
            # output_name is the path/basename provided by the worker
            output_path = f"{output_name}.{format}"

        try:
            return base.convert_single_image(
                image_path,
                output_path,
                format,
                delete,
                aspect_ratio,
                ar_mode,
            )
        except Exception as e:
            print(f"Error in convert_single_image: {e}")
            return False

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
        Converts all images in a directory matching input_formats using the Rust backend.
        Returns a list of successful output paths.
        """
        if output_dir is None:
            output_dir = input_dir

        is_jpeg_or_jpg = lambda fmt: fmt in ["jpg", "jpeg"]
        output_fmt = output_format.lower()
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
                if total_files > 1:
                    output_filename = f"{output_filename_prefix}{idx + 1}"
                else:
                    output_filename = output_filename_prefix
            else:
                output_filename = filename_base

            output_path = os.path.join(output_dir, f"{output_filename}.{output_format}")

            # Simple skip logic handled in Rust? No, Rust overwrites.
            # Python checked `if output_filename_prefix or (not os.path.isfile(output_path) or aspect_ratio is not None)`
            # We will include it in the batch if it meets criteria.
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

        # --- Call Rust Backend ---
        try:
            results = base.convert_image_batch(
                image_pairs=image_pairs,
                output_format=output_format,
                delete_original=delete,
                aspect_ratio=aspect_ratio,
                ar_mode=ar_mode,
            )

            if progress_callback:
                progress_callback(100)

            print(f"\nBatch processing complete! Processed {len(results)} images.")
            return results

        except Exception as e:
            print(f"Error in convert_batch: {e}")
            return []
