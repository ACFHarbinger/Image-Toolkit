import cv2
import numpy as np

from . import FSETool
from PIL import Image
from typing import List, Tuple, Optional
from ..utils.definitions import AlignMode


# Define the decorator factories needed for the merge methods
MERGE_IMAGES_PREFIX = FSETool.prefix_create_directory(
    arg_id=2, is_filepath=True
)

MERGE_DIR_IMAGES_PREFIX = FSETool.prefix_create_directory(
    arg_id=3, kwarg_name='output_path', is_filepath=True
)


class ImageMerger:
    """
    A comprehensive tool for merging and transforming images, 
    supporting horizontal, vertical, grid layouts, and panoramic stitching.
    """
    
    # --- Helper Static Method for Image Preparation ---
    @staticmethod
    def _prepare_image(img: Image.Image, target_size: Tuple[int, int], align_mode: AlignMode) -> Image.Image:
        """
        Resizes the image if needed based on the align_mode. 
        target_size is (W, H) of the desired output for this image.
        """
        if img.size == target_size:
            return img
        return img.resize(target_size, Image.Resampling.LANCZOS)
    
    # --- Core Merging Logic (Private Static Methods) ---
    @staticmethod
    def _merge_images_horizontal(image_paths: List[str], output_path: str, spacing: int=0, align_mode: AlignMode="Default (Top/Center)") -> Image.Image:
        images = [Image.open(img) for img in image_paths]
        
        widths, heights = zip(*(img.size for img in images))
        
        max_height = max(heights)
        min_height = min(heights)
        max_width = max(widths)
        min_width = min(widths)
        
        is_full_resize = align_mode in ["Scaled (Grow Smallest)", "Squish (Shrink Largest)"]
        
        if is_full_resize:
            target_width = max_width if align_mode == "Scaled (Grow Smallest)" else min_width
            target_height = max_height if align_mode == "Scaled (Grow Smallest)" else min_height
            total_width = target_width * len(images) + (spacing * (len(images) - 1))
            canvas_height = target_height
        else:
            target_height = max_height
            total_width = sum(widths) + (spacing * (len(images) - 1))
            canvas_height = max_height

        merged_image = Image.new('RGB', (total_width, canvas_height), (255, 255, 255))
        
        x_offset = 0
        for img in images:
            if is_full_resize:
                prep_img = ImageMerger._prepare_image(img, (target_width, target_height), align_mode)
            else:
                prep_img = ImageMerger._prepare_image(img, (img.width, canvas_height), align_mode) 

            current_height = prep_img.height
            y_offset = 0
            if align_mode == "Align Bottom/Right":
                y_offset = canvas_height - current_height
            elif align_mode in ["Center", "Default (Top/Center)"]:
                y_offset = (canvas_height - current_height) // 2
            
            merged_image.paste(prep_img, (x_offset, y_offset))
            x_offset += prep_img.width + spacing
        
        merged_image.save(output_path)
        return merged_image

    @staticmethod
    def _merge_images_vertical(image_paths: List[str], output_path: str, spacing: int=0, align_mode: AlignMode="Default (Top/Center)") -> Image.Image:
        images = [Image.open(img) for img in image_paths]
        
        widths, heights = zip(*(img.size for img in images))
        
        max_width = max(widths)
        min_width = min(widths)
        max_height = max(heights)
        min_height = min(heights)
        
        is_full_resize = align_mode in ["Scaled (Grow Smallest)", "Squish (Shrink Largest)"]

        if is_full_resize:
            target_width = max_width if align_mode == "Scaled (Grow Smallest)" else min_width
            target_height = max_height if align_mode == "Scaled (Grow Smallest)" else min_height
            total_height = target_height * len(images) + (spacing * (len(images) - 1))
            canvas_width = target_width
        else:
            canvas_width = max_width
            total_height = sum(heights) + (spacing * (len(images) - 1))
        
        merged_image = Image.new('RGB', (canvas_width, total_height), (255, 255, 255))
        
        y_offset = 0
        for img in images:
            if is_full_resize:
                prep_img = ImageMerger._prepare_image(img, (target_width, target_height), align_mode)
            else:
                prep_img = ImageMerger._prepare_image(img, (canvas_width, img.height), align_mode)

            current_width = prep_img.width
            x_offset = 0
            if align_mode == "Align Top/Left":
                x_offset = 0
            elif align_mode == "Align Bottom/Right":
                x_offset = canvas_width - current_width
            elif align_mode in ["Center", "Default (Top/Center)"]:
                x_offset = (canvas_width - current_width) // 2
            
            merged_image.paste(prep_img, (x_offset, y_offset))
            y_offset += prep_img.height + spacing
        
        merged_image.save(output_path)
        return merged_image

    @staticmethod
    def _merge_images_grid(image_paths: List[str], output_path: str, grid_size: Tuple[int, int], spacing: int=0) -> Image.Image:
        images = [Image.open(img) for img in image_paths]
        rows, cols = grid_size
        
        if len(images) > rows * cols:
            raise ValueError("More images provided than the grid slots can hold.")
        
        if not images:
             raise ValueError("No images found to merge for grid layout.")
        
        widths, heights = zip(*(img.size for img in images))
        max_width = max(widths)
        max_height = max(heights)
        
        total_width = cols * max_width + (spacing * (cols - 1))
        total_height = rows * max_height + (spacing * (rows - 1))
        merged_image = Image.new('RGB', (total_width, total_height), (255, 255, 255))
        
        for idx, img in enumerate(images):
            row = idx // cols
            col = idx % cols
            
            x_offset = col * (max_width + spacing) + (max_width - img.width) // 2
            y_offset = row * (max_height + spacing) + (max_height - img.height) // 2
            
            merged_image.paste(img, (x_offset, y_offset))
        
        merged_image.save(output_path)
        return merged_image

    @staticmethod
    def _merge_images_panorama(image_paths: List[str], output_path: str) -> Image.Image:
        """
        Stitches images into a panorama using OpenCV's default PANORAMA mode.
        Good for rotating camera shots (perspective transformation).
        """
        import cv2
        
        cv_images = []
        for path in image_paths:
            img = cv2.imread(path)
            if img is not None:
                cv_images.append(img)
            else:
                 print(f"Warning: Could not read image for panorama: {path}")

        if len(cv_images) < 2:
            raise ValueError("Need at least 2 valid images to create a panorama.")
            
        # Initialize Stitcher in PANORAMA mode (Mode 0)
        try:
            stitcher = cv2.Stitcher_create(mode=0)
        except AttributeError:
             # Fallback for older OpenCV versions
             stitcher = cv2.createStitcher(False) 
        
        # Perform stitching
        status, pano = stitcher.stitch(cv_images)

        if status != cv2.Stitcher_OK:
            error_map = {
                cv2.Stitcher_ERR_NEED_MORE_IMGS: "Need more images",
                cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "Homography estimation failed",
                cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "Camera params failed"
            }
            err_msg = error_map.get(status, f"Error code {status}")
            raise RuntimeError(f"Panorama stitching failed: {err_msg}")

        # Convert BGR (OpenCV) to RGB (PIL)
        pano_rgb = cv2.cvtColor(pano, cv2.COLOR_BGR2RGB)
        merged_image = Image.fromarray(pano_rgb)
        
        merged_image.save(output_path)
        return merged_image

    @staticmethod
    def _merge_images_scan_stitch(image_paths: List[str], output_path: str) -> Image.Image:
        """
        Stitches a large number of images with small differences (flat scans).
        Uses OpenCV's SCANS mode which optimizes for affine/flat transformations.
        """
        import cv2
        
        # 1. Read images
        cv_images = []
        for path in image_paths:
            img = cv2.imread(path)
            if img is not None and img.size > 0:
                cv_images.append(img)
            else:
                print(f"Warning: Could not read image: {path}")

        if len(cv_images) < 2:
            raise ValueError("Need at least 2 valid images to stitch.")

        # 2. Initialize Stitcher in SCANS mode
        # Mode 1 = SCANS (Optimized for flat/affine stitching)
        try:
            stitcher = cv2.Stitcher_create(mode=1) 
        except AttributeError:
            # Fallback: older OpenCV versions might not accept mode arg in create
            stitcher = cv2.createStitcher(True) # True often maps to scans/try_use_gpu

        # 3. Setting Registration Resol (higher value = more keypoints for small diffs)
        # Default is usually 0.6, increasing helps with small overlaps
        stitcher.setRegistrationResol(0.6) 

        # 4. Perform Stitching
        status, pano = stitcher.stitch(cv_images)

        if status != cv2.Stitcher_OK:
            error_map = {
                cv2.Stitcher_ERR_NEED_MORE_IMGS: "Need more images",
                cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "Homography estimation failed",
                cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "Camera params failed"
            }
            err_msg = error_map.get(status, f"Error code {status}")
            raise RuntimeError(f"Scan stitching failed: {err_msg}")

        # 5. Convert & Save
        pano_rgb = cv2.cvtColor(pano, cv2.COLOR_BGR2RGB)
        merged_image = Image.fromarray(pano_rgb)
        
        merged_image.save(output_path)
        return merged_image

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=MERGE_IMAGES_PREFIX)
    def merge_images(self, 
                     image_paths: List[str], 
                     output_path: str, 
                     direction: str, 
                     grid_size: Optional[Tuple[int, int]]=None, 
                     spacing: int=0, 
                     align_mode: AlignMode="Default (Top/Center)") -> Image.Image:
        """
        Merge images based on direction.
        Options: 'horizontal', 'vertical', 'grid', 'panorama', 'stitch'.
        """
        if direction == 'horizontal':
            merged_img = self._merge_images_horizontal(image_paths, output_path, spacing, align_mode)
        elif direction == 'vertical':
            merged_img = self._merge_images_vertical(image_paths, output_path, spacing, align_mode)
        elif direction == 'grid':
            if grid_size is None:
                raise ValueError("grid_size must be provided for grid merging")
            merged_img = self._merge_images_grid(image_paths, output_path, grid_size, spacing)
        elif direction == 'panorama':
            merged_img = self._merge_images_panorama(image_paths, output_path)
        elif direction == 'stitch':
            merged_img = self._merge_images_scan_stitch(image_paths, output_path)
        else:
            raise ValueError(f"ERROR: invalid direction '{direction}'")
        
        print(f"Merged {len(image_paths)} images into '{output_path}' using direction '{direction}'.")
        return merged_img

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=MERGE_DIR_IMAGES_PREFIX)
    def merge_directory_images(self, 
                               directory: str, 
                               input_formats: List[str], 
                               output_path: str, 
                               direction: str='horizontal', 
                               grid_size: Optional[Tuple[int, int]]=None, 
                               spacing: int=0, 
                               align_mode: AlignMode="Default (Top/Center)") -> Optional[Image.Image]:
        
        image_paths = []
        for fmt in input_formats:
            image_paths.extend(FSETool.get_files_by_extension(directory, fmt))
        
        if not image_paths:
            print(f"WARNING: No images found in directory '{directory}' with formats {input_formats}.")
            return None
        
        return self.merge_images(image_paths, output_path, direction, grid_size, spacing, align_mode)