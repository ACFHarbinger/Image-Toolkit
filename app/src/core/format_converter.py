import os
import glob

from PIL import Image
from typing import List
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
    def _convert_img_core(image_path, output_path, format, delete):
        """Core logic for image format conversion."""
        
        # Check input extension
        _, file_ext = os.path.splitext(image_path)
        if file_ext.lstrip('.') not in SUPPORTED_IMG_FORMATS:
            raise ValueError(f"Invalid input file extension '{file_ext}'.")

        # Check output format
        if format.lower() not in SUPPORTED_IMG_FORMATS:
            raise ValueError(f"Unsupported output format '{format}'.")

        try:
            with Image.open(image_path) as img:
                if file_ext == format or (file_ext in ['jpg', 'jpeg'] and format in ['jpg', 'jpeg']): return img

                target_format = format.lower()
                
                # Handle JPEG conversion: ensure no transparency, set output format name
                if target_format in ['jpg', 'jpeg']:
                    if img.mode in ('RGBA', 'LA', 'P'):
                        # Convert to RGB, using white background (common for JPEGs)
                        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                        rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = rgb_img
                    
                    if target_format == 'jpg': target_format = 'jpeg'
                
                # Ensure the full path is used for saving
                img.save(output_path, target_format.upper())
                if delete: os.remove(image_path)
                print(f"Converted '{os.path.basename(image_path)}' to '{os.path.basename(output_path)}'.")
                return img
        except Exception as e:
            print(f"Warning: failed to convert file {image_path} with exception {type(e)}.")
            return None

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=SINGLE_CONVERSION_PREFIX)
    def convert_img_format(self, image_path: str, output_name: str=None, format: str='png', delete: bool=False):
        """
        Converts a single image file to a specified format.
        
        The decorator ensures image_path is absolute. Output directory 
        creation is expected to be handled externally if output_name includes a path.
        """
        # Determine the final output path
        filename_only = os.path.splitext(os.path.basename(image_path))[0]
        
        # Use filename_only if output_name is not provided
        if output_name is None:
            output_name = filename_only
            # Assuming the output is saved in the same directory as the input image
            output_path = os.path.join(os.path.dirname(image_path), f"{output_name}.{format}")
        else:
             # If output_name contains a path, use it. The decorator for batch 
             # conversion will handle directory creation.
             output_path = f"{output_name}.{format}"
        
        return None if os.path.isfile(output_path) \
            else self._convert_img_core(image_path, output_path, format, delete) 

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=BATCH_CONVERSION_PREFIX)
    def batch_convert_img_format(self, input_dir: str, inputs_formats: List[str], output_dir: str=None, output_format: str='png', delete: bool=False): 
        """
        Converts all images in a directory matching input_formats to the output_format.
        
        The decorator handles creating the output_dir if needed.
        """
        if output_dir is None: output_dir = input_dir
        if output_format in inputs_formats: inputs_formats.remove(output_format)

        new_images = []
        for input_format in inputs_formats:
            # Use glob to find all files in the input directory (input_dir is absolute due to decorator)
            for input_file in glob.glob(os.path.join(input_dir, f'*.{input_format}')):
                # Create the full output path
                filename = os.path.splitext(os.path.basename(input_file))[0]
                output_path = os.path.join(output_dir, f"{filename}.{output_format}")
                
                if not os.path.isfile(output_path):
                    # Directly call the core conversion logic, as the public method
                    # is primarily for external calls and includes path logic.
                    img = self._convert_img_core(input_file, output_path, output_format, delete)
                    if img is not None: 
                        new_images.append(img)
                    
        print(f"\nBatch conversion complete! Converted {len(new_images)} images.")
        return new_images
