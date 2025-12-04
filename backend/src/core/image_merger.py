import cv2
import numpy as np

from . import FSETool
from PIL import Image
from typing import List, Tuple, Optional
from ..utils.definitions import AlignMode


# Define the decorator factories needed for the merge methods
MERGE_IMAGES_PREFIX = FSETool.prefix_create_directory(arg_id=2, is_filepath=True)

MERGE_DIR_IMAGES_PREFIX = FSETool.prefix_create_directory(
    arg_id=3, kwarg_name="output_path", is_filepath=True
)


class ImageMerger:
    """
    A comprehensive tool for merging and transforming images,
    supporting horizontal, vertical, grid layouts, panoramic stitching, and GIFs.
    """

    # --- Helper Static Method for Image Preparation ---
    @staticmethod
    def _prepare_image(
        img: Image.Image, target_size: Tuple[int, int], align_mode: AlignMode
    ) -> Image.Image:
        """
        Resizes the image if needed based on the align_mode.
        target_size is (W, H) of the desired output for this image.
        """
        if img.size == target_size:
            return img
        return img.resize(target_size, Image.Resampling.LANCZOS)

    # --- Core Merging Logic (Private Static Methods) ---
    @staticmethod
    def _merge_images_horizontal(
        image_paths: List[str],
        output_path: str,
        spacing: int = 0,
        align_mode: AlignMode = "Default (Top/Center)",
    ) -> Image.Image:
        images = [Image.open(img) for img in image_paths]

        widths, heights = zip(*(img.size for img in images))

        max_height = max(heights)
        min_height = min(heights)
        max_width = max(widths)
        min_width = min(widths)

        is_full_resize = align_mode in [
            "Scaled (Grow Smallest)",
            "Squish (Shrink Largest)",
        ]

        if is_full_resize:
            target_width = (
                max_width if align_mode == "Scaled (Grow Smallest)" else min_width
            )
            target_height = (
                max_height if align_mode == "Scaled (Grow Smallest)" else min_height
            )
            total_width = target_width * len(images) + (spacing * (len(images) - 1))
            canvas_height = target_height
        else:
            target_height = max_height
            total_width = sum(widths) + (spacing * (len(images) - 1))
            canvas_height = max_height

        merged_image = Image.new("RGB", (total_width, canvas_height), (255, 255, 255))

        x_offset = 0
        for img in images:
            if is_full_resize:
                prep_img = ImageMerger._prepare_image(
                    img, (target_width, target_height), align_mode
                )
            else:
                prep_img = ImageMerger._prepare_image(
                    img, (img.width, canvas_height), align_mode
                )

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
    def _merge_images_vertical(
        image_paths: List[str],
        output_path: str,
        spacing: int = 0,
        align_mode: AlignMode = "Default (Top/Center)",
    ) -> Image.Image:
        images = [Image.open(img) for img in image_paths]

        widths, heights = zip(*(img.size for img in images))

        max_width = max(widths)
        min_width = min(widths)
        max_height = max(heights)
        min_height = min(heights)

        is_full_resize = align_mode in [
            "Scaled (Grow Smallest)",
            "Squish (Shrink Largest)",
        ]

        if is_full_resize:
            target_width = (
                max_width if align_mode == "Scaled (Grow Smallest)" else min_width
            )
            target_height = (
                max_height if align_mode == "Scaled (Grow Smallest)" else min_height
            )
            total_height = target_height * len(images) + (spacing * (len(images) - 1))
            canvas_width = target_width
        else:
            canvas_width = max_width
            total_height = sum(heights) + (spacing * (len(images) - 1))

        merged_image = Image.new("RGB", (canvas_width, total_height), (255, 255, 255))

        y_offset = 0
        for img in images:
            if is_full_resize:
                prep_img = ImageMerger._prepare_image(
                    img, (target_width, target_height), align_mode
                )
            else:
                prep_img = ImageMerger._prepare_image(
                    img, (canvas_width, img.height), align_mode
                )

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
    def _merge_images_grid(
        image_paths: List[str],
        output_path: str,
        grid_size: Tuple[int, int],
        spacing: int = 0,
    ) -> Image.Image:
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
        merged_image = Image.new("RGB", (total_width, total_height), (255, 255, 255))

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
                cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "Camera params failed",
            }
            err_msg = error_map.get(status, f"Error code {status}")
            raise RuntimeError(f"Panorama stitching failed: {err_msg}")

        # Convert BGR (OpenCV) to RGB (PIL)
        pano_rgb = cv2.cvtColor(pano, cv2.COLOR_BGR2RGB)
        merged_image = Image.fromarray(pano_rgb)

        merged_image.save(output_path)
        return merged_image

    @staticmethod
    def _merge_images_scan_stitch(
        image_paths: List[str], output_path: str
    ) -> Image.Image:
        """
        Stitches a large number of images with small differences (flat scans).
        Uses OpenCV's SCANS mode which optimizes for affine/flat transformations.
        """
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
            stitcher = cv2.createStitcher(True)  # True often maps to scans/try_use_gpu

        # 3. Setting Registration Resol (higher value = more keypoints for small diffs)
        # Default is usually 0.6, increasing helps with small overlaps
        stitcher.setRegistrationResol(0.8)

        # 4. Perform Stitching
        status, pano = stitcher.stitch(cv_images)

        if status != cv2.Stitcher_OK:
            error_map = {
                cv2.Stitcher_ERR_NEED_MORE_IMGS: "Need more images",
                cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "Homography estimation failed",
                cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "Camera params failed",
            }
            err_msg = error_map.get(status, f"Error code {status}")
            raise RuntimeError(f"Scan stitching failed: {err_msg}")

        # 5. Convert & Save
        pano_rgb = cv2.cvtColor(pano, cv2.COLOR_BGR2RGB)
        merged_image = Image.fromarray(pano_rgb)

        merged_image.save(output_path)
        return merged_image

    @staticmethod
    def _merge_images_sequential(
        image_paths: List[str], output_path: str
    ) -> Image.Image:
        """
        Sequentially stitches images (A->B) vertically using template matching.
        Ideal for webtoons, chat logs, or vertical screenshots with overlap.
        Uses bidirectional matching (A->B and B->A) for robustness and sub-pixel refinement.
        Applies gradient blending (cross-dissolve) at the seam to hide transition lines.
        """
        cv_images = []
        for p in image_paths:
            img = cv2.imread(p)
            if img is not None:
                cv_images.append(img)

        if len(cv_images) < 2:
            raise ValueError("Need 2+ images for sequential merge.")

        # 1. Normalize widths to the first image
        target_w = cv_images[0].shape[1]
        resized = []
        for img in cv_images:
            h, w = img.shape[:2]
            if w != target_w:
                scale = target_w / w
                new_h = int(h * scale)
                img = cv2.resize(img, (target_w, new_h))
            resized.append(img)

        # 2. Accumulate Vertically
        canvas = resized[0]
        prev_h = canvas.shape[0]  # Track height of the last added segment

        for i in range(1, len(resized)):
            next_img = resized[i]
            h_canvas, w_canvas = canvas.shape[:2]
            h_next = next_img.shape[:2][0]

            # Match the bottom strip of 'canvas' with the top of 'next_img'
            # SEARCH RANGE: Increased to 90% of image height to catch massive overlaps
            max_search_px = int(min(h_next * 0.90, 5000))
            overlap_search = min(h_canvas, max_search_px)
            slice_h = 64

            best_match_val = 0
            best_pixel_y_in_roi = -1
            match_type = None  # 'A' or 'B'

            # --- Sub-pixel refinement helper ---
            def calculate_subpixel_y(res, max_loc):
                """Uses weighted average of max_loc and its vertical neighbors for sub-pixel estimation."""
                y = max_loc[1]
                x = max_loc[0]

                # Check bounds for y-neighbors
                if y > 0 and y < res.shape[0] - 1:
                    # Parabola approximation to estimate the true peak position
                    y_sub = (res[y - 1, x] - res[y + 1, x]) / (
                        2 * res[y - 1, x] - 4 * res[y, x] + 2 * res[y + 1, x]
                    )
                    return y + y_sub
                return y

            # -----------------------------------

            # --- Method A: Forward Match (Find Bottom of Canvas inside Top of Next) ---
            if overlap_search > slice_h:
                template_a = canvas[-slice_h:, :]
                if np.std(template_a) > 5.0:  # Variance check
                    roi_a = next_img[:overlap_search, :]
                    res_a = cv2.matchTemplate(roi_a, template_a, cv2.TM_CCOEFF_NORMED)
                    _, max_val_a, _, max_loc_a = cv2.minMaxLoc(res_a)

                    subpixel_y_a = calculate_subpixel_y(res_a, max_loc_a)

                    # Cut point: Canvas end - slice height - distance into next image
                    cut_y_a = (h_canvas - slice_h) - int(round(subpixel_y_a))

                    min_safe_y = h_canvas - prev_h
                    if max_val_a > 0.6 and min_safe_y < cut_y_a < h_canvas:
                        if max_val_a > best_match_val:
                            best_match_val = max_val_a
                            best_pixel_y_in_roi = subpixel_y_a
                            match_type = "A"

            # --- Method B: Reverse Match (Find Top of Next inside Bottom of Canvas) ---
            if overlap_search > slice_h:
                template_b = next_img[:slice_h, :]
                if np.std(template_b) > 5.0:  # Variance check
                    roi_b = canvas[-overlap_search:, :]
                    res_b = cv2.matchTemplate(roi_b, template_b, cv2.TM_CCOEFF_NORMED)
                    _, max_val_b, _, max_loc_b = cv2.minMaxLoc(res_b)

                    subpixel_y_b = calculate_subpixel_y(res_b, max_loc_b)

                    # Cut point: ROI start + match Y
                    roi_start_y = h_canvas - overlap_search
                    cut_y_b = roi_start_y + int(round(subpixel_y_b))

                    min_safe_y = h_canvas - prev_h
                    if max_val_b > 0.6 and min_safe_y < cut_y_b < h_canvas:
                        if max_val_b > best_match_val:
                            best_match_val = max_val_b
                            best_pixel_y_in_roi = subpixel_y_b
                            match_type = "B"

            # --- Apply Best Match with BLENDING ---
            if match_type:
                # Calculate final integer cut point based on the best subpixel match
                if match_type == "A":
                    final_cut_y = (h_canvas - slice_h) - int(round(best_pixel_y_in_roi))
                else:  # match_type == 'B'
                    roi_start_y = h_canvas - overlap_search
                    final_cut_y = roi_start_y + int(round(best_pixel_y_in_roi))

                # Apply overlap bias to ensure we have content to blend
                overlap_bias = 0
                final_cut_y = final_cut_y - overlap_bias

                # Boundary check
                min_safe_y = h_canvas - prev_h
                final_cut_y = min(final_cut_y, h_canvas)
                final_cut_y = max(final_cut_y, min_safe_y)

                # --- Blending Logic ---
                # overlap_h: Amount of 'canvas' that extends beyond the cut point.
                # Since final_cut_y is where we would ideally start next_img,
                # any canvas existing below this point is overlap.
                overlap_h = h_canvas - final_cut_y

                # Only blend if we have a decent overlap to work with
                if overlap_h > 0:
                    # Limit blending height to avoid ghosting on large misalignments
                    # 64px max blend, or whatever overlap we have
                    blend_h = min(overlap_h, 64)

                    # 1. Top (unblended)
                    top_part = canvas[:final_cut_y, :]

                    # 2. Middle (blended)
                    # Canvas strip: starts at final_cut_y, height blend_h
                    img1_strip = canvas[final_cut_y : final_cut_y + blend_h].astype(
                        float
                    )

                    # Next Img strip: starts at 0, height blend_h
                    img2_strip = next_img[0:blend_h].astype(float)

                    # Alpha mask: 1.0 at top (canvas), 0.0 at bottom (next_img)
                    alpha = np.linspace(1, 0, blend_h).reshape(-1, 1, 1)
                    blended = (img1_strip * alpha + img2_strip * (1.0 - alpha)).astype(
                        np.uint8
                    )

                    # 3. Bottom (unblended)
                    bottom_part = next_img[blend_h:, :]

                    canvas = np.vstack([top_part, blended, bottom_part])
                else:
                    # Fallback to hard cut if calculation says 0 overlap
                    canvas = np.vstack([canvas[:final_cut_y, :], next_img])

                prev_h = h_next
            else:
                # Append with no overlap
                canvas = np.vstack([canvas, next_img])
                prev_h = h_next

        # Convert to PIL
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        merged_image = Image.fromarray(rgb)

        merged_image.save(output_path)
        return merged_image

    @staticmethod
    def _create_gif(
        image_paths: List[str], output_path: str, duration: int = 500
    ) -> Image.Image:
        """
        Creates an animated GIF from the provided images.
        Resizes all images to match the size of the first image to ensure consistency.
        """
        if not image_paths:
            raise ValueError("No images provided for GIF creation.")

        # Open all images
        images = [Image.open(p) for p in image_paths]

        # Use first image as base size
        base_size = images[0].size

        # Normalize all frames to the base size
        frames = []
        for img in images:
            if img.size != base_size:
                # Resize using Lanczos for quality
                frames.append(img.resize(base_size, Image.Resampling.LANCZOS))
            else:
                frames.append(img)

        # Save GIF
        # append_images takes the rest of the list (frames[1:])
        # loop=0 means infinite loop
        if output_path.lower().endswith(".png"):
            output_path = output_path[:-4] + ".gif"

        frames[0].save(
            output_path,
            format="GIF",
            append_images=frames[1:],
            save_all=True,
            duration=duration,
            loop=0,
            optimize=True,
        )

        return frames[0]

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=MERGE_IMAGES_PREFIX)
    def merge_images(
        self,
        image_paths: List[str],
        output_path: str,
        direction: str,
        grid_size: Optional[Tuple[int, int]] = None,
        spacing: int = 0,
        align_mode: AlignMode = "Default (Top/Center)",
        duration: int = 500,
    ) -> Image.Image:
        """
        Merge images based on direction.
        Options: 'horizontal', 'vertical', 'grid', 'panorama', 'stitch', 'sequential', 'gif'.
        """
        if direction == "horizontal":
            merged_img = self._merge_images_horizontal(
                image_paths, output_path, spacing, align_mode
            )
        elif direction == "vertical":
            merged_img = self._merge_images_vertical(
                image_paths, output_path, spacing, align_mode
            )
        elif direction == "grid":
            if grid_size is None:
                raise ValueError("grid_size must be provided for grid merging")
            merged_img = self._merge_images_grid(
                image_paths, output_path, grid_size, spacing
            )
        elif direction == "panorama":
            merged_img = self._merge_images_panorama(image_paths, output_path)
        elif direction == "stitch":
            merged_img = self._merge_images_scan_stitch(image_paths, output_path)
        elif direction == "sequential":
            merged_img = self._merge_images_sequential(image_paths, output_path)
        elif direction == "gif":
            merged_img = self._create_gif(image_paths, output_path, duration)
        else:
            raise ValueError(f"ERROR: invalid direction '{direction}'")

        print(
            f"Merged {len(image_paths)} images into '{output_path}' using direction '{direction}'."
        )
        return merged_img

    @classmethod
    @FSETool.ensure_absolute_paths(prefix_func=MERGE_DIR_IMAGES_PREFIX)
    def merge_directory_images(
        self,
        directory: str,
        input_formats: List[str],
        output_path: str,
        direction: str = "horizontal",
        grid_size: Optional[Tuple[int, int]] = None,
        spacing: int = 0,
        align_mode: AlignMode = "Default (Top/Center)",
        duration: int = 500,
    ) -> Optional[Image.Image]:

        image_paths = []
        for fmt in input_formats:
            image_paths.extend(FSETool.get_files_by_extension(directory, fmt))

        if not image_paths:
            print(
                f"WARNING: No images found in directory '{directory}' with formats {input_formats}."
            )
            return None

        return self.merge_images(
            image_paths,
            output_path,
            direction,
            grid_size,
            spacing,
            align_mode,
            duration,
        )
