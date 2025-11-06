from PIL import Image
from . import FSETool

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
    supporting horizontal, vertical, and grid layouts. Uses 
    FSETool for path management and directory creation.
    """
    # --- Core Merging Logic (Private Static Methods) ---
    @staticmethod
    def _merge_images_horizontal(image_paths, output_path, spacing=0):
        """Merge images horizontally, aligning to the top."""
        images = [Image.open(img) for img in image_paths]
        
        widths, heights = zip(*(img.size for img in images))
        total_width = sum(widths) + (spacing * (len(images) - 1))
        max_height = max(heights)
        
        merged_image = Image.new('RGB', (total_width, max_height), (255, 255, 255))
        
        x_offset = 0
        for img in images:
            merged_image.paste(img, (x_offset, 0))
            x_offset += img.width + spacing
        
        merged_image.save(output_path)
        return merged_image

    @staticmethod
    def _merge_images_vertical(image_paths, output_path, spacing=0):
        """Merge images vertically, centering them horizontally."""
        images = [Image.open(img) for img in image_paths]
        
        widths, heights = zip(*(img.size for img in images))
        max_width = max(widths)
        total_height = sum(heights) + (spacing * (len(images) - 1))
        
        merged_image = Image.new('RGB', (max_width, total_height), (255, 255, 255))
        
        y_offset = 0
        for img in images:
            x_offset = (max_width - img.width) // 2
            merged_image.paste(img, (x_offset, y_offset))
            y_offset += img.height + spacing
        
        merged_image.save(output_path)
        return merged_image

    @staticmethod
    def _merge_images_grid(image_paths, output_path, grid_size, spacing=0):
        """Merge images in a grid layout (rows, cols), centering them in their cell."""
        images = [Image.open(img) for img in image_paths]
        rows, cols = grid_size
        
        if len(images) > rows * cols:
            raise ValueError("More images provided than the grid slots can hold.")
        
        widths, heights = zip(*(img.size for img in images))
        max_width = max(widths) if widths else 0
        max_height = max(heights) if heights else 0
        
        if not images:
             print("No images to merge for grid layout.")
             return None

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
    def merge_images(self, image_paths, output_path, direction, grid_size=None, spacing=0):
        """
        Merge images based on direction ('horizontal', 'vertical', or 'grid').
        Directory creation for output_path is handled by the decorator.
        """
        if direction == 'horizontal':
            merged_img = self._merge_images_horizontal(image_paths, output_path, spacing)
        elif direction == 'vertical':
            merged_img = self._merge_images_vertical(image_paths, output_path, spacing)
        elif direction == 'grid':
            if grid_size is None:
                raise ValueError("grid_size must be provided for grid merging")
            merged_img = self._merge_images_grid(image_paths, output_path, grid_size, spacing)
        else:
            raise ValueError(f"ERROR: invalid direction '{direction}'-> choose from 'horizontal'|'vertical'|'grid'.")
        
        print(f"Merged {len(image_paths)} images into '{output_path}' using direction '{direction}'.")
        return merged_img

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=MERGE_DIR_IMAGES_PREFIX)
    def merge_directory_images(self, directory, input_formats, output_path, direction='horizontal', grid_size=None, spacing=0):
        """
        Merge all images of specified formats found in a directory.
        Directory creation for output_path is handled by the decorator.
        """
        image_paths = []
        for fmt in input_formats:
            # Use the method that internally uses the file system tool
            image_paths.extend(FSETool.get_files_by_extension(directory, fmt))
        
        if not image_paths:
            print(f"WARNING: No images found in directory '{directory}' with formats {input_formats}.")
            return None
        
        # Use the public method to perform the merge
        return self.merge_images(image_paths, output_path, direction, grid_size, spacing)
