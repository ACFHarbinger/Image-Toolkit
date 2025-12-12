import os
import sys
import pytest
import numpy as np

from PIL import Image
from unittest.mock import patch, MagicMock, call

# Add project root to Python path to import modules
project_root = sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, project_root)

from src.core import ImageMerger


class ImageMergerTest:
    def test_merge_images_horizontal(self, sample_images, output_dir):
        """Test horizontal image merging"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "horizontal_merge.png")

        # Use the public class method with direction='horizontal'
        result = ImageMerger.merge_images(
            image_paths, output_path, direction="horizontal"
        )

        # Verify output file exists
        assert os.path.exists(output_path)

        # Verify result is PIL Image
        assert isinstance(result, Image.Image)

        # Verify dimensions
        original_images = [Image.open(img) for img in image_paths]
        total_width = sum(img.width for img in original_images)
        max_height = max(img.height for img in original_images)

        assert result.size == (total_width, max_height)

    def test_merge_images_horizontal_with_spacing(self, sample_images, output_dir):
        """Test horizontal merging with spacing"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "horizontal_spacing.png")
        spacing = 10

        # Use the public class method with direction='horizontal' and spacing
        result = ImageMerger.merge_images(
            image_paths, output_path, direction="horizontal", spacing=spacing
        )

        assert os.path.exists(output_path)
        assert isinstance(result, Image.Image)

        original_images = [Image.open(img) for img in image_paths]
        total_width = sum(img.width for img in original_images) + (
            spacing * (len(original_images) - 1)
        )
        max_height = max(img.height for img in original_images)
        assert result.size == (total_width, max_height)

    def test_merge_images_vertical(self, sample_images, output_dir):
        """Test vertical image merging"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "vertical_merge.png")

        # Use the public class method with direction='vertical'
        result = ImageMerger.merge_images(
            image_paths, output_path, direction="vertical"
        )

        assert os.path.exists(output_path)
        assert isinstance(result, Image.Image)

        original_images = [Image.open(img) for img in image_paths]
        max_width = max(img.width for img in original_images)
        total_height = sum(img.height for img in original_images)

        assert result.size == (max_width, total_height)

    def test_merge_images_vertical_with_spacing(self, sample_images, output_dir):
        """Test vertical merging with spacing"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "vertical_spacing.png")
        spacing = 15

        # Use the public class method with direction='vertical' and spacing
        result = ImageMerger.merge_images(
            image_paths, output_path, direction="vertical", spacing=spacing
        )

        assert os.path.exists(output_path)
        assert isinstance(result, Image.Image)

        original_images = [Image.open(img) for img in image_paths]
        max_width = max(img.width for img in original_images)
        total_height = sum(img.height for img in original_images) + (
            spacing * (len(original_images) - 1)
        )

        assert result.size == (max_width, total_height)

    def test_merge_images_grid(self, sample_images, output_dir):
        """Test grid image merging"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "grid_merge.png")
        grid_size = (2, 2)  # 2x2 grid

        # Use the public class method with direction='grid' and grid_size
        result = ImageMerger.merge_images(
            image_paths, output_path, direction="grid", grid_size=grid_size
        )

        assert os.path.exists(output_path)
        assert isinstance(result, Image.Image)

        original_images = [Image.open(img) for img in image_paths]
        max_width = max(img.width for img in original_images)
        max_height = max(img.height for img in original_images)

        expected_width = 2 * max_width  # 2 columns
        expected_height = 2 * max_height  # 2 rows

        assert result.size == (expected_width, expected_height)

    def test_merge_images_grid_with_spacing(self, sample_images, output_dir):
        """Test grid merging with spacing"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "grid_spacing.png")
        grid_size = (2, 2)
        spacing = 5

        # Use the public class method with direction='grid', grid_size, and spacing
        result = ImageMerger.merge_images(
            image_paths,
            output_path,
            direction="grid",
            grid_size=grid_size,
            spacing=spacing,
        )

        assert os.path.exists(output_path)
        assert isinstance(result, Image.Image)

        original_images = [Image.open(img) for img in image_paths]
        max_width = max(img.width for img in original_images)
        max_height = max(img.height for img in original_images)

        expected_width = 2 * max_width + spacing  # 2 columns with 1 spacing
        expected_height = 2 * max_height + spacing  # 2 rows with 1 spacing

        assert result.size == (expected_width, expected_height)

    def test_merge_images_grid_too_many_images(self, sample_images, output_dir):
        """Test grid merging with more images than grid slots"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "grid_error.png")
        grid_size = (1, 2)  # Only 2 slots but we have 4 images

        # Updated to reflect the ValueError raised by the ImageMerger class logic
        with pytest.raises(
            ValueError, match="More images provided than the grid slots can hold."
        ):
            ImageMerger.merge_images(image_paths, output_path, "grid", grid_size)

    def test_merge_images_function(self, sample_images, output_dir):
        """Test the main merge_images function with different directions"""
        temp_dir, image_paths = sample_images

        # Test horizontal direction
        output_horizontal = os.path.join(output_dir, "test_horizontal.png")
        result_horizontal = ImageMerger.merge_images(
            image_paths, output_horizontal, "horizontal"
        )
        assert os.path.exists(output_horizontal)
        assert isinstance(result_horizontal, Image.Image)

        # Test vertical direction
        output_vertical = os.path.join(output_dir, "test_vertical.png")
        result_vertical = ImageMerger.merge_images(
            image_paths, output_vertical, "vertical"
        )
        assert os.path.exists(output_vertical)
        assert isinstance(result_vertical, Image.Image)

        # Test grid direction
        output_grid = os.path.join(output_dir, "test_grid.png")
        result_grid = ImageMerger.merge_images(
            image_paths, output_grid, "grid", grid_size=(2, 2)
        )
        assert os.path.exists(output_grid)
        assert isinstance(result_grid, Image.Image)

    def test_merge_images_invalid_direction(self, sample_images, output_dir):
        """Test merge_images with invalid direction"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "invalid.png")

        with pytest.raises(ValueError, match="invalid direction"):
            ImageMerger.merge_images(image_paths, output_path, "invalid_direction")

    def test_merge_images_grid_no_size(self, sample_images, output_dir):
        """Test merge_images grid direction without grid_size"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "grid_no_size.png")

        # Updated to reflect the ValueError raised by the ImageMerger class logic
        with pytest.raises(
            ValueError, match="grid_size must be provided for grid merging"
        ):
            ImageMerger.merge_images(
                image_paths, output_path, "grid"
            )  # No grid_size provided

    def test_merge_directory_images(self, sample_images, output_dir):
        """Test merging images from a directory"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "directory_merge.png")

        # Use the public class method ImageMerger.merge_directory_images
        result = ImageMerger.merge_directory_images(
            directory=temp_dir,
            input_formats=["png"],
            output_path=output_path,
            direction="horizontal",
        )

        assert os.path.exists(output_path)
        assert isinstance(result, Image.Image)

    def test_merge_directory_images_multiple_formats(self, sample_images, output_dir):
        """Test merging with multiple input formats"""
        temp_dir, image_paths = sample_images

        # Create a JPEG image alongside PNGs
        jpeg_path = os.path.join(temp_dir, "test_jpeg.jpeg")
        jpeg_img = Image.new("RGB", (100, 100), (128, 128, 128))
        jpeg_img.save(jpeg_path)

        output_path = os.path.join(output_dir, "multi_format.png")

        # Use the public class method ImageMerger.merge_directory_images
        result = ImageMerger.merge_directory_images(
            directory=temp_dir,
            input_formats=["png", "jpeg"],
            output_path=output_path,
            direction="horizontal",
        )

        assert os.path.exists(output_path)
        assert isinstance(result, Image.Image)
        # Should merge all 5 images (4 PNG + 1 JPEG)

    def test_merge_directory_images_empty_directory(self, tmp_path):
        """Test merging from empty directory"""
        output_path = os.path.join(tmp_path, "empty_merge.png")

        # Use the public class method ImageMerger.merge_directory_images
        result = ImageMerger.merge_directory_images(
            directory=str(tmp_path),
            input_formats=["png", "jpeg"],
            output_path=output_path,
            direction="horizontal",
        )

        # Should return None and print warning
        assert result is None
        # Output file should not be created for empty directory
        assert not os.path.exists(output_path)

    def test_merge_directory_images_nonexistent_format(self, sample_images, output_dir):
        """Test merging with format that doesn't exist in directory"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "nonexistent_format.png")

        # Use the public class method ImageMerger.merge_directory_images
        result = ImageMerger.merge_directory_images(
            directory=temp_dir,
            input_formats=["bmp"],  # No BMP files in our test directory
            output_path=output_path,
            direction="horizontal",
        )

        # Should return None and print warning
        assert result is None
        assert not os.path.exists(output_path)

    def test_output_directory_creation(self, sample_images, output_dir):
        """Test that output directories are created automatically"""
        temp_dir, image_paths = sample_images

        # Create a nested output path that doesn't exist
        nested_output = os.path.join(output_dir, "nested", "subdirectory", "output.png")

        # This should create the directories automatically via the decorator on merge_images
        result = ImageMerger.merge_images(image_paths, nested_output, "horizontal")

        assert os.path.exists(nested_output)
        assert isinstance(result, Image.Image)
        assert os.path.exists(os.path.dirname(nested_output))

    def test_image_content_preservation(self, sample_images, output_dir):
        """Test that image content is preserved in merging"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "content_test.png")

        # Merge images using the public class method
        result = ImageMerger.merge_images(
            [image_paths[0], image_paths[1]], output_path, direction="horizontal"
        )

        # Open the result and verify it's a valid image
        result_img = Image.open(output_path)
        assert result_img.size == result.size

        # Verify it's not just a blank image
        # Convert to grayscale and check if it has variation
        grayscale = result_img.convert("L")
        extrema = grayscale.getextrema()
        assert extrema[0] != extrema[1]  # Should have some color variation

    @pytest.mark.parametrize(
        "direction,grid_size,expected_success",
        [
            ("horizontal", None, True),
            ("vertical", None, True),
            ("grid", (2, 2), True),
            ("grid", (1, 4), True),
            ("grid", None, False),  # Should fail without grid_size
            ("invalid", None, False),  # Should fail with invalid direction
        ],
    )
    def test_merge_images_parameterized(
        self, sample_images, output_dir, direction, grid_size, expected_success
    ):
        """Parameterized test for different merge scenarios"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, f"param_test_{direction}.png")

        if expected_success:
            result = ImageMerger.merge_images(
                image_paths, output_path, direction, grid_size
            )
            assert os.path.exists(output_path)
            assert isinstance(result, Image.Image)
        else:
            if direction == "grid" and grid_size is None:
                # Updated to match the ValueError message
                with pytest.raises(
                    ValueError, match="grid_size must be provided for grid merging"
                ):
                    ImageMerger.merge_images(
                        image_paths, output_path, direction, grid_size
                    )
            elif direction == "invalid":
                # Updated to match the ValueError message
                with pytest.raises(ValueError, match="invalid direction"):
                    ImageMerger.merge_images(
                        image_paths, output_path, direction, grid_size
                    )

    def test_single_image_merge(self, sample_images, output_dir):
        """Test merging with just one image (edge case)"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "single_image.png")

        # Test with single image
        single_image = [image_paths[0]]

        # Should work for all directions
        for direction in ["horizontal", "vertical"]:
            specific_output = output_path.replace(".png", f"_{direction}.png")
            result = ImageMerger.merge_images(single_image, specific_output, direction)
            assert os.path.exists(specific_output)
            assert isinstance(result, Image.Image)

        # Grid should also work with single image
        grid_output = output_path.replace(".png", "_grid.png")
        result = ImageMerger.merge_images(
            single_image, grid_output, "grid", grid_size=(1, 1)
        )
        assert os.path.exists(grid_output)
        assert isinstance(result, Image.Image)
    @patch("src.core.image_merger.cv2")
    def test_merge_images_panorama(self, mock_cv2, sample_images, output_dir):
        """Test panorama stitching (mocked)"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "panorama.png")

        # Mock Stitcher
        mock_stitcher = MagicMock()
        # Create method needs to return the stitcher instance
        mock_cv2.Stitcher_create.return_value = mock_stitcher
        mock_cv2.createStitcher.return_value = mock_stitcher  # Fallback

        # Mock successful stitch
        # stitch returns (status, pano_image)
        # Create a dummy pano image (numpy array)
        mock_pano = np.zeros((100, 200, 3), dtype=np.uint8)
        mock_stitcher.stitch.return_value = (0, mock_pano)  # 0 is usually OK

        # Mock constants
        mock_cv2.Stitcher_OK = 0
        mock_cv2.COLOR_BGR2RGB = 4

        # Mock imread to return valid images
        mock_cv2.imread.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

        # Mock cvtColor
        mock_cv2.cvtColor.return_value = mock_pano

        # Execute
        result = ImageMerger.merge_images(image_paths, output_path, "panorama")

        # Verify
        assert os.path.exists(output_path)
        assert isinstance(result, Image.Image)
        mock_cv2.Stitcher_create.assert_called()
        mock_stitcher.stitch.assert_called()

    @patch("src.core.image_merger.cv2")
    def test_merge_images_scan_stitch(self, mock_cv2, sample_images, output_dir):
        """Test scan stitching (mocked)"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "scan_stitch.png")

        # Mock Stitcher
        mock_stitcher = MagicMock()
        mock_cv2.Stitcher_create.return_value = mock_stitcher

        # Mock successful stitch
        mock_pano = np.zeros((100, 200, 3), dtype=np.uint8)
        mock_stitcher.stitch.return_value = (0, mock_pano)

        # Mock constants
        mock_cv2.Stitcher_OK = 0
        mock_cv2.COLOR_BGR2RGB = 4

        # Mock imread
        mock_cv2.imread.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cv2.cvtColor.return_value = mock_pano

        # Execute
        result = ImageMerger.merge_images(image_paths, output_path, "stitch")

        # Verify
        assert os.path.exists(output_path)
        assert isinstance(result, Image.Image)
        # Verify mode 1 (SCANS) was used
        mock_cv2.Stitcher_create.assert_called_with(mode=1)
        mock_stitcher.setRegistrationResol.assert_called()

    @patch("src.core.image_merger.cv2")
    def test_merge_images_sequential(self, mock_cv2, sample_images, output_dir):
        """Test sequential stitching (mocked w/ template matching)"""
        temp_dir, image_paths = sample_images
        output_path = os.path.join(output_dir, "sequential.png")

        # Mock imread - Create 2 dummy images with variance (random noise)
        # Variance is needed to pass the np.std(template) > 5.0 check
        # Img 1: 100x100
        # Img 2: 100x100
        img1 = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        img2 = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        mock_cv2.imread.side_effect = [img1, img2, None]

        # Mock resize (just return the input or a resized clone)
        mock_cv2.resize.side_effect = lambda src, dsize: np.zeros(
            (dsize[1], dsize[0], 3), dtype=np.uint8
        )

        # Mock matchTemplate
        # Return a result map where match is good enough
        mock_res = np.zeros((50, 50), dtype=np.float32)
        mock_res[0, 0] = 0.9  # Good match at 0,0
        mock_cv2.matchTemplate.return_value = mock_res
        mock_cv2.TM_CCOEFF_NORMED = 5

        # Mock minMaxLoc -> min_val, max_val, min_loc, max_loc
        # Return max_val=0.9 at (0,0)
        mock_cv2.minMaxLoc.return_value = (0, 0.9, (0, 0), (0, 0))

        # Mock COLOR conversion
        mock_cv2.COLOR_BGR2RGB = 4
        # Just return input as is for color conversion mock, needs to be array compatible
        mock_cv2.cvtColor.return_value = np.zeros((200, 100, 3), dtype=np.uint8)

        # Execute
        result = ImageMerger.merge_images(image_paths[:2], output_path, "sequential")

        # Verify
        assert os.path.exists(output_path)
        assert isinstance(result, Image.Image)
        # Verify matchTemplate was called to check overlap
        assert mock_cv2.matchTemplate.called
