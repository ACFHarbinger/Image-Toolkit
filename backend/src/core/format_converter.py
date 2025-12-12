import os
import glob

from PIL import Image, ImageSequence
from typing import List, Optional, Callable
from ..utils.definitions import SUPPORTED_IMG_FORMATS
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
    A tool for converting image formats and adjusting aspect ratios 
    (Crop, Pad, or Stretch) for single files and batches.
    """

    @staticmethod
    def _crop_center(img: Image.Image, target_ratio: float) -> Image.Image:
        """Crops an image to the specific aspect ratio from the center."""
        w, h = img.size
        current_ratio = w / h

        if current_ratio > target_ratio:
            # Image is too wide; crop width
            new_w = int(h * target_ratio)
            offset = (w - new_w) // 2
            box = (offset, 0, offset + new_w, h)
        else:
            # Image is too tall; crop height
            new_h = int(w / target_ratio)
            offset = (h - new_h) // 2
            box = (0, offset, w, offset + new_h)

        return img.crop(box)

    @staticmethod
    def _pad_image(img: Image.Image, target_ratio: float) -> Image.Image:
        """Pads an image to fit the aspect ratio (Letterbox/Pillarbox)."""
        w, h = img.size
        current_ratio = w / h
        
        # Convert P mode to RGBA to ensure padding transparency/color works safely
        if img.mode == 'P':
            img = img.convert('RGBA')

        if current_ratio > target_ratio:
            # Image is wider than target. Need to add height (Letterbox).
            new_h = int(w / target_ratio)
            new_w = w
        else:
            # Image is taller than target. Need to add width (Pillarbox).
            new_w = int(h * target_ratio)
            new_h = h
            
        # Create background. Transparent if supported, else Black.
        mode = img.mode
        if mode in ("RGBA", "LA"):
            fill_color = (0, 0, 0, 0)
        else:
            fill_color = (0, 0, 0)
            
        result = Image.new(mode, (new_w, new_h), fill_color)
        
        # Center image
        x = (new_w - w) // 2
        y = (new_h - h) // 2
        result.paste(img, (x, y))
        return result

    @staticmethod
    def _stretch_image(img: Image.Image, target_ratio: float) -> Image.Image:
        """Resizes the image to fit the aspect ratio, distorting it."""
        w, h = img.size
        current_ratio = w / h
        
        if current_ratio > target_ratio:
            # Current is wider than target.
            new_h = int(w / target_ratio)
            new_w = w
        else:
            # Current is taller. Grow Width.
            new_w = int(h * target_ratio)
            new_h = h
            
        return img.resize((new_w, new_h), Image.LANCZOS)

    @staticmethod
    def _apply_ar_transform(img: Image.Image, ratio: float, mode: str) -> Image.Image:
        """Applies the selected AR transformation."""
        if mode == 'pad':
            return ImageFormatConverter._pad_image(img, ratio)
        elif mode == 'stretch':
            return ImageFormatConverter._stretch_image(img, ratio)
        else:
            # Default to crop
            return ImageFormatConverter._crop_center(img, ratio)

    @staticmethod
    def _convert_img_core(
        image_path: str,
        output_path: str,
        format: str,
        delete: bool,
        aspect_ratio: Optional[float] = None,
        ar_mode: str = "crop",
    ) -> Optional[Image.Image]:
        """Core logic for image format conversion and aspect ratio adjustment."""

        _, file_ext = os.path.splitext(image_path)
        if file_ext.lstrip(".") not in SUPPORTED_IMG_FORMATS:
            raise ValueError(f"Invalid input file extension '{file_ext}'.")

        if format.lower() not in SUPPORTED_IMG_FORMATS:
            raise ValueError(f"Unsupported output format '{format}'.")

        try:
            with Image.open(image_path) as img:
                target_format = format.lower()
                is_animated = getattr(img, "is_animated", False)

                # --- 1. Handle Aspect Ratio ---
                frames = []
                if aspect_ratio:
                    if is_animated:
                        for frame in ImageSequence.Iterator(img):
                            # Copy to avoid pipeline issues
                            frames.append(
                                ImageFormatConverter._apply_ar_transform(
                                    frame.copy(), aspect_ratio, ar_mode
                                )
                            )
                        img = frames[0]
                    else:
                        img = ImageFormatConverter._apply_ar_transform(
                            img, aspect_ratio, ar_mode
                        )

                # --- 2. Handle Format Conversion ---
                
                is_jpeg_or_jpg = lambda fmt: fmt in ["jpg", "jpeg"]
                current_format = file_ext.lstrip(".").lower()

                # Optimization: If no AR change and formats match, return original object (logic handled by caller usually)
                if aspect_ratio is None:
                    if current_format == target_format or (
                        is_jpeg_or_jpg(current_format) and is_jpeg_or_jpg(target_format)
                    ):
                        if os.path.abspath(image_path) != os.path.abspath(output_path):
                            # Same format but different path: Check if we need to copy
                            # But simply letting it fall through to save() is safer/easier
                            pass 
                        else:
                            return img

                # Handle JPEG transparency (Convert to RGB)
                if is_jpeg_or_jpg(target_format):
                    if img.mode in ("RGBA", "LA", "P"):
                        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                            
                        rgb_img.paste(
                            img, mask=img.split()[-1] if img.mode == "RGBA" else None
                        )
                        img = rgb_img
                        frames = [img] # Reset frames if we flattened

                    if target_format == "jpg":
                        target_format = "jpeg"

                # --- 3. Save ---
                if is_animated and aspect_ratio and target_format in ["gif", "webp", "png"]:
                    img.save(
                        output_path,
                        save_all=True,
                        append_images=frames[1:],
                        optimize=False,
                        duration=img.info.get("duration", 100),
                        loop=img.info.get("loop", 0),
                    )
                else:
                    img.save(output_path, target_format.upper())

                if delete:
                    os.remove(image_path)
                
                print(
                    f"Processed '{os.path.basename(image_path)}' -> '{os.path.basename(output_path)}'."
                )
                return img

        except Exception as e:
            print(f"Warning: failed to process file {image_path}: {e}")
            return None

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=SINGLE_CONVERSION_PREFIX)
    def convert_single_image(
        self,
        image_path: str,
        output_name: str = None,
        format: str = "png",
        delete: bool = False,
        aspect_ratio: Optional[float] = None,
        ar_mode: str = "crop",
    ) -> Optional[Image.Image]:
        """
        Converts a single image file to a specified format with optional aspect ratio adjustment.
        """
        filename_only = os.path.splitext(os.path.basename(image_path))[0]

        if output_name is None:
            output_path = os.path.join(
                os.path.dirname(image_path), f"{filename_only}.{format}"
            )
        else:
            # output_name is the path/basename provided by the worker (e.g., /dir/processed_)
            output_path = f"{output_name}.{format}"

        return self._convert_img_core(
            image_path, output_path, format, delete, aspect_ratio, ar_mode
        )

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=BATCH_CONVERSION_PREFIX)
    def convert_batch(
        self,
        input_dir: str,
        inputs_formats: List[str],
        output_dir: str = None,
        output_format: str = "png",
        delete: bool = False,
        aspect_ratio: Optional[float] = None,
        ar_mode: str = "crop",
        output_filename_prefix: str = "",
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> List[Image.Image]:
        """
        Converts all images in a directory matching input_formats.
        """
        if output_dir is None:
            output_dir = input_dir

        is_jpeg_or_jpg = lambda fmt: fmt in ["jpg", "jpeg"]
        output_fmt = output_format.lower()
        
        input_formats = [f.lower() for f in inputs_formats]
        
        # --- Collect all paths to get a total count for the progress bar ---
        all_paths = []
        for input_format in input_formats:
            all_paths.extend(glob.glob(os.path.join(input_dir, f"*.{input_format}")))

        # Filter paths if no AR change is requested
        if aspect_ratio is None:
            filtered_paths = []
            for input_file in all_paths:
                file_ext = os.path.splitext(input_file)[1].lstrip(".").lower()
                # Check if file format requires conversion
                if not (
                    file_ext == output_fmt
                    or (is_jpeg_or_jpg(file_ext) and is_jpeg_or_jpg(output_fmt))
                ):
                    filtered_paths.append(input_file)
            all_paths = filtered_paths

        total_files = len(all_paths)
        new_images = []
        
        # --- Main Processing Loop ---
        for idx, input_file in enumerate(all_paths):
            
            # --- Filename Logic (Updated for single file handling) ---
            filename_base = os.path.splitext(os.path.basename(input_file))[0]
            
            if output_filename_prefix:
                if total_files > 1:
                    # Multiple files: Use prefix + index (1-based index)
                    output_filename = f"{output_filename_prefix}{idx + 1}"
                else:
                    # Single file: Use prefix without numbering
                    output_filename = output_filename_prefix
            else:
                # Use original filename base
                output_filename = filename_base
                
            output_path = os.path.join(output_dir, f"{output_filename}.{output_format}")
            # ------------------------------

            # Calculate and report progress
            if progress_callback and total_files > 0:
                progress = int((idx / total_files) * 100)
                progress_callback(progress)

            # Proceed if filename prefix is used OR if it passes standard overwrite check
            if output_filename_prefix or (not os.path.isfile(output_path) or aspect_ratio is not None):
                img = self._convert_img_core(
                    input_file, output_path, output_format, delete, aspect_ratio, ar_mode
                )
                if img is not None:
                    new_images.append(img)
            
        # Report 100% completion
        if progress_callback and total_files > 0:
            progress_callback(100)
        
        print(f"\nBatch processing complete! Processed {len(new_images)} images.")
        return new_images