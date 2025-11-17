from . import FSETool
from PIL import Image
from typing import List, Tuple, Optional
from ..utils.definitions import AlignMode

# Define the decorator factories needed for the merge methods
# output_path is at index 2 for merge_images
MERGE_IMAGES_PREFIX = FSETool.prefix_create_directory(
    arg_id=2, is_filepath=True
)

# output_path is at index 3 OR via kwarg 'output_path' for merge_directory_images
MERGE_DIR_IMAGES_PREFIX = FSETool.prefix_create_directory(
    arg_id=3, kwarg_name='output_path', is_filepath=True
)


class ImageMerger:
    """
    A comprehensive tool for merging and transforming images, 
    supporting horizontal, vertical, and grid layouts, with various 
    alignment and resizing options.
    """
    
    # --- Helper Static Method for Image Preparation ---
    @staticmethod
    def _prepare_image(img: Image.Image, target_size: Tuple[int, int], align_mode: AlignMode) -> Image.Image:
        """
        Resizes the image if needed based on the align_mode. 
        target_size is (W, H) of the desired output for this image.
        """
        # If the image size already matches the target size, no need to resize
        if img.size == target_size:
            return img
        
        # If a resize is needed, use high quality resampling
        return img.resize(target_size, Image.Resampling.LANCZOS)
    
    # --- Core Merging Logic (Private Static Methods) ---
    @staticmethod
    def _merge_images_horizontal(image_paths: List[str], output_path: str, spacing: int=0, align_mode: AlignMode="Default (Top/Center)") -> Image.Image:
        """Merge images horizontally, supporting alignment and resizing."""
        images = [Image.open(img) for img in image_paths]
        
        widths, heights = zip(*(img.size for img in images))
        
        max_height = max(heights)
        min_height = min(heights)
        max_width = max(widths)
        min_width = min(widths)
        
        is_full_resize = align_mode in ["Scaled (Grow Smallest)", "Squish (Shrink Largest)"]
        
        if is_full_resize:
            # Full WxH resize: All images will be scaled to this size.
            target_width = max_width if align_mode == "Scaled (Grow Smallest)" else min_width
            target_height = max_height if align_mode == "Scaled (Grow Smallest)" else min_height
            
            # Canvas size is based on the uniform size
            total_width = target_width * len(images) + (spacing * (len(images) - 1))
            canvas_height = target_height
        
        else:
            # Alignment only: Canvas height is max_height, total width is sum of original widths.
            target_height = max_height # Only height is reference
            total_width = sum(widths) + (spacing * (len(images) - 1))
            canvas_height = max_height

        merged_image = Image.new('RGB', (total_width, canvas_height), (255, 255, 255))
        
        x_offset = 0
        for img in images:
            if is_full_resize:
                # Resize to the calculated uniform size
                prep_img = ImageMerger._prepare_image(img, (target_width, target_height), align_mode)
            else:
                # Alignment only: Resize height to max_height, keep original width
                prep_img = ImageMerger._prepare_image(img, (img.width, canvas_height), align_mode) 

            # Calculate Y-offset based on alignment mode
            current_height = prep_img.height
            
            y_offset = 0
            if align_mode == "Align Bottom/Right":
                y_offset = canvas_height - current_height
            elif align_mode in ["Center", "Default (Top/Center)"]:
                y_offset = (canvas_height - current_height) // 2
            # else: Align Top, y_offset = 0
            
            merged_image.paste(prep_img, (x_offset, y_offset))
            x_offset += prep_img.width + spacing
        
        merged_image.save(output_path)
        return merged_image

    @staticmethod
    def _merge_images_vertical(image_paths: List[str], output_path: str, spacing: int=0, align_mode: AlignMode="Default (Top/Center)") -> Image.Image:
        """Merge images vertically, supporting alignment and resizing."""
        images = [Image.open(img) for img in image_paths]
        
        widths, heights = zip(*(img.size for img in images))
        
        max_width = max(widths)
        min_width = min(widths)
        max_height = max(heights)
        min_height = min(heights)
        
        is_full_resize = align_mode in ["Scaled (Grow Smallest)", "Squish (Shrink Largest)"]

        if is_full_resize:
            # Full WxH resize: All images will be scaled to this size.
            target_width = max_width if align_mode == "Scaled (Grow Smallest)" else min_width
            target_height = max_height if align_mode == "Scaled (Grow Smallest)" else min_height
            
            # Canvas size is based on the uniform size
            total_height = target_height * len(images) + (spacing * (len(images) - 1))
            canvas_width = target_width
        
        else:
            # Alignment only: Canvas width is max_width, total height is sum of original heights.
            canvas_width = max_width
            total_height = sum(heights) + (spacing * (len(images) - 1))
        
        merged_image = Image.new('RGB', (canvas_width, total_height), (255, 255, 255))
        
        y_offset = 0
        for img in images:
            if is_full_resize:
                # Resize to the calculated uniform size
                prep_img = ImageMerger._prepare_image(img, (target_width, target_height), align_mode)
            else:
                # Alignment only: Resize width to max_width, keep original height
                prep_img = ImageMerger._prepare_image(img, (canvas_width, img.height), align_mode)

            # Calculate X-offset based on alignment mode (Horizontal alignment in a vertical merge)
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
        """Merge images in a grid layout (rows, cols), centering them in their cell."""
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

    # --- Public Methods (Class Methods) ---

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
        Merge images based on direction ('horizontal', 'vertical', or 'grid').
        Applies alignment/resizing based on align_mode for horizontal/vertical merges.
        """
        if direction == 'horizontal':
            merged_img = self._merge_images_horizontal(image_paths, output_path, spacing, align_mode)
        elif direction == 'vertical':
            merged_img = self._merge_images_vertical(image_paths, output_path, spacing, align_mode)
        elif direction == 'grid':
            if grid_size is None:
                raise ValueError("grid_size must be provided for grid merging")
            # Grid logic uses centering within cells, alignment mode is ignored.
            merged_img = self._merge_images_grid(image_paths, output_path, grid_size, spacing)
        else:
            raise ValueError(f"ERROR: invalid direction '{direction}'-> choose from 'horizontal'|'vertical'|'grid'.")
        
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
        """
        Merge all images of specified formats found in a directory.
        """
        image_paths = []
        for fmt in input_formats:
            image_paths.extend(FSETool.get_files_by_extension(directory, fmt))
        
        if not image_paths:
            print(f"WARNING: No images found in directory '{directory}' with formats {input_formats}.")
            return None
        
        return self.merge_images(image_paths, output_path, direction, grid_size, spacing, align_mode)
