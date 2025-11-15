import os
import glob

from PIL import Image
from typing import List, Optional
from ..utils.definitions import SUPPORTED_IMG_FORMATS
from . import FSETool


# Define the decorator factories needed for the format conversion methods
# output_name is at index 2 (0=self, 1=image_path, 2=output_name)
SINGLE_CONVERSION_PREFIX = FSETool.prefix_create_directory(
    arg_id=2, kwarg_name='output_name', is_filepath=True
)

# output_path is at index 3 OR via kwarg 'output_path' for batch_convert_img_format
BATCH_CONVERSION_PREFIX = FSETool.prefix_create_directory(
    arg_id=3, kwarg_name='output_dir', is_filepath=False
)


class ImageFormatConverter:
    """
    A tool for converting image formats for single files and batches.
    Relies on external utilities for path management and directory creation.
    """
    @staticmethod
    def _convert_img_core(image_path: str, output_path: str, format: str, delete: bool) -> Optional[Image.Image]:
        """Core logic for image format conversion."""
        
        _, file_ext = os.path.splitext(image_path)
        if file_ext.lstrip('.') not in SUPPORTED_IMG_FORMATS:
            raise ValueError(f"Invalid input file extension '{file_ext}'.")

        if format.lower() not in SUPPORTED_IMG_FORMATS:
            raise ValueError(f"Unsupported output format '{format}'.")

        try:
            with Image.open(image_path) as img:
                target_format = format.lower()
                
                # Check if conversion is actually needed (handling jpg/jpeg synonyms)
                is_jpeg_or_jpg = lambda fmt: fmt in ['jpg', 'jpeg']
                current_format = file_ext.lstrip('.').lower()

                if current_format == target_format or (is_jpeg_or_jpg(current_format) and is_jpeg_or_jpg(target_format)):
                    return img
                
                # Handle JPEG conversion: ensure no transparency
                if is_jpeg_or_jpg(target_format):
                    if img.mode in ('RGBA', 'LA', 'P'):
                        # Convert to RGB, using white background
                        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                        rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = rgb_img
                    
                    if target_format == 'jpg': target_format = 'jpeg'
                
                img.save(output_path, target_format.upper())
                if delete: os.remove(image_path)
                print(f"Converted '{os.path.basename(image_path)}' to '{os.path.basename(output_path)}'.")
                return img
        except Exception as e:
            print(f"Warning: failed to convert file {image_path}: {e}")
            return None

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=SINGLE_CONVERSION_PREFIX)
    def convert_single_image(self, image_path: str, output_name: str=None, format: str='png', delete: bool=False) -> Optional[Image.Image]:
        """
        Converts a single image file to a specified format.
        """
        filename_only = os.path.splitext(os.path.basename(image_path))[0]
        
        if output_name is None:
            output_path = os.path.join(os.path.dirname(image_path), f"{filename_only}.{format}")
        else:
             output_path = f"{output_name}.{format}"
        
        return None if os.path.isfile(output_path) \
            else self._convert_img_core(image_path, output_path, format, delete) 

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=BATCH_CONVERSION_PREFIX)
    def convert_batch(self, input_dir: str, inputs_formats: List[str], output_dir: str=None, output_format: str='png', delete: bool=False) -> List[Image.Image]: 
        """
        Converts all images in a directory matching input_formats to the output_format.
        Returns a list of resulting PIL Image objects (only if conversion was successful).
        """
        if output_dir is None: output_dir = input_dir
        
        # Don't convert a file to itself (handling jpg/jpeg synonyms)
        is_jpeg_or_jpg = lambda fmt: fmt in ['jpg', 'jpeg']
        output_fmt = output_format.lower()
        
        input_formats = [f.lower() for f in inputs_formats if not (f.lower() == output_fmt or (is_jpeg_or_jpg(f.lower()) and is_jpeg_or_jpg(output_fmt)))]

        new_images = []
        for input_format in input_formats:
            for input_file in glob.glob(os.path.join(input_dir, f'*.{input_format}')):
                filename = os.path.splitext(os.path.basename(input_file))[0]
                output_path = os.path.join(output_dir, f"{filename}.{output_format}")
                
                if not os.path.isfile(output_path):
                    img = self._convert_img_core(input_file, output_path, output_format, delete)
                    if img is not None: 
                        new_images.append(img)
                    
        print(f"\nBatch conversion complete! Converted {len(new_images)} images.")
        return new_images
