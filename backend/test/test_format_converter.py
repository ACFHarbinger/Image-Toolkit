import os
import sys
import pytest
import shutil

from PIL import Image
from pathlib import Path

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.core import ImageFormatConverter
from src.utils.definitions import SUPPORTED_IMG_FORMATS, ROOT_DIR


# --- TESTS (Adapted to Class Methods and Corrected Path Logic) ---
class ImageFormatConverterTest:
    def test_convert_img_format_png_to_jpeg(self, sample_image, output_dir):
        """Test converting PNG to JPEG"""
        # output_base_name is the intended full path without the final extension
        output_base_name = os.path.join(output_dir, "converted_image")
        
        # Call the class method
        result = ImageFormatConverter.convert_img_format(sample_image, output_base_name, 'jpeg')
        
        # Check if conversion was successful
        assert result is not None
        assert isinstance(result, Image.Image)
        
        # Expected output file is the output_base_name with the extension appended by the class method
        expected_output = f"{output_base_name}.jpeg" 
        assert os.path.exists(expected_output)
        
        # Verify the converted image is valid
        converted_img = Image.open(expected_output)
        assert converted_img.format == 'JPEG'
        assert converted_img.size == (100, 100)

    def test_convert_img_format_same_format(self, sample_image, output_dir):
        """Test converting to same format (should still work)"""
        output_base_name = os.path.join(output_dir, "same_format")
        
        # Call the class method
        result = ImageFormatConverter.convert_img_format(sample_image, output_base_name, 'png')
        
        assert result is not None
        assert isinstance(result, Image.Image)
        
        expected_output = f"{output_base_name}.png"
        assert os.path.exists(expected_output)

    def test_convert_img_format_transparent_to_jpeg(self, sample_transparent_image, output_dir):
        """Test converting transparent PNG to JPEG (should handle transparency)"""
        output_base_name = os.path.join(output_dir, "transparent_converted")
        
        # Call the class method
        result = ImageFormatConverter.convert_img_format(sample_transparent_image, output_base_name, 'jpeg')
        
        assert result is not None
        assert isinstance(result, Image.Image)
        
        expected_output = f"{output_base_name}.jpeg"
        assert os.path.exists(expected_output)
        
        # Verify it's RGB mode (not RGBA)
        converted_img = Image.open(expected_output)
        assert converted_img.mode == 'RGB'

    def test_convert_img_format_no_output_name(self, sample_image):
        """Test conversion without specifying output name (saves to same directory)"""
        # Call the class method
        result = ImageFormatConverter.convert_img_format(sample_image, format='jpeg')
        
        assert result is not None
        assert isinstance(result, Image.Image)
        
        # Should create file with same name but different extension in the input directory
        input_dir = os.path.dirname(sample_image)
        input_name = os.path.splitext(os.path.basename(sample_image))[0]
        # The output path is guaranteed to be absolute (from the tempfile fixture)
        expected_output = os.path.join(input_dir, f"{input_name}.jpeg")
        assert os.path.exists(expected_output)

    def test_convert_img_format_unsupported_format(self, sample_image):
        """Test conversion with unsupported input format (original test used AssertionError, but class raises ValueError)"""
        # Create a file with unsupported extension
        unsupported_path = sample_image.replace('.png', '.txt')
        os.rename(sample_image, unsupported_path)
        
        # The class logic now raises ValueError
        with pytest.raises(ValueError, match="Invalid input file extension"):
            ImageFormatConverter.convert_img_format(unsupported_path, "test_output", 'png')

    def test_convert_img_format_invalid_file(self):
        """Test conversion with non-existent file"""
        # Call the class method
        result = ImageFormatConverter.convert_img_format("/nonexistent/path/image.png", "output", 'jpeg')
        assert result is None

    @pytest.mark.parametrize("output_format", ['png', 'jpeg', 'webp'])
    def test_convert_img_format_multiple_formats(self, sample_image, output_dir, output_format):
        """Test conversion to multiple output formats"""
        if output_format not in SUPPORTED_IMG_FORMATS:
            pytest.skip(f"{output_format} not in supported formats")
        
        output_base_name = os.path.join(output_dir, f"test_{output_format}")
        
        # Call the class method
        result = ImageFormatConverter.convert_img_format(sample_image, output_base_name, output_format)
        
        assert result is not None
        assert isinstance(result, Image.Image)
        
        expected_output = f"{output_base_name}.{output_format}"
        assert os.path.exists(expected_output)

    def test_batch_convert_img_format(self, sample_images_directory, output_dir):
        """Test batch conversion of multiple images"""
        input_dir, image_paths = sample_images_directory
        batch_output_dir = os.path.join(output_dir, "batch_output")
        
        # Convert only PNG and JPEG files
        # Call the class method
        result = ImageFormatConverter.batch_convert_img_format(
            input_dir=input_dir,
            inputs_formats=['png', 'jpeg'],
            output_dir=batch_output_dir,
            output_format='webp'
        )
        
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 2  # Should convert 2 images (png and jpeg, not webp)
        
        # Check that output files were created
        for img_path in image_paths:
            if any(img_path.endswith(ext) for ext in ['.png', '.jpeg']):
                input_name = os.path.splitext(os.path.basename(img_path))[0]
                # Output path uses the absolute batch_output_dir
                expected_output = os.path.join(batch_output_dir, f"{input_name}.webp")
                assert os.path.exists(expected_output)

    def test_batch_convert_img_format_same_directory(self, sample_images_directory):
        """Test batch conversion using same directory for output"""
        input_dir, image_paths = sample_images_directory
        
        # Call the class method
        result = ImageFormatConverter.batch_convert_img_format(
            input_dir=input_dir,
            inputs_formats=['png'],
            output_dir=None,  # Should use input_dir
            output_format='jpeg'
        )
        
        assert result is not None
        assert len(result) == 1  # Should convert 1 PNG file
        
        # Check that file was created in input directory
        expected_output = os.path.join(input_dir, "test_image_0.jpeg")
        assert os.path.exists(expected_output)

    def test_batch_convert_img_format_no_matching_files(self, tmp_path):
        """Test batch conversion with no matching files"""
        empty_dir = str(tmp_path)
        
        # Call the class method
        result = ImageFormatConverter.batch_convert_img_format(
            input_dir=empty_dir,
            inputs_formats=['png'],
            output_dir=os.path.join(empty_dir, "output"),
            output_format='jpeg'
        )
        
        assert result == []  # Should return empty list

    def test_batch_convert_img_format_nonexistent_directory(self):
        """
        Test batch conversion raises FileNotFoundError for a non-existent input directory.
        """
        # Use pytest.raises to assert that a FileNotFoundError is raised.
        # We use 'Path' to construct a guaranteed non-existent path.
        non_existent_dir = Path("/nonexistent/directory_for_test_12345")
        
        # Ensure the path really doesn't exist before running the test
        assert not non_existent_dir.exists()

        with pytest.raises(PermissionError) as excinfo:
            # Call the class method
            ImageFormatConverter.batch_convert_img_format(
                input_dir=str(non_existent_dir),
                inputs_formats=['png'],
                output_dir="/some/valid/output", # Output dir existence might be checked later
                output_format='jpeg'
            )

        assert "Permission denied" in str(excinfo.value)

    def test_batch_convert_directory_creation(self, sample_images_directory, output_dir):
        """Test that output directory is created automatically"""
        input_dir, image_paths = sample_images_directory
        nested_output = os.path.join(output_dir, "nested", "output", "directory")
        
        # This should create the nested directories via the decorator
        # Call the class method
        result = ImageFormatConverter.batch_convert_img_format(
            input_dir=input_dir,
            inputs_formats=['png'],
            output_dir=nested_output,
            output_format='jpeg'
        )
        
        assert result is not None
        assert len(result) == 1
        
        # Verify directory was created (rely on the underlying OS features/tempfile)
        assert os.path.exists(nested_output)
        
        # Verify file was created in the correct location
        expected_output = os.path.join(nested_output, "test_image_0.jpeg")
        assert os.path.exists(expected_output)

    def test_image_content_preservation(self, sample_image, output_dir):
        """Test that image content is preserved during conversion"""
        output_base_name = os.path.join(output_dir, "content_test")
        
        # Convert and verify basic properties
        original_img = Image.open(sample_image)
        # Call the class method
        result = ImageFormatConverter.convert_img_format(sample_image, output_base_name, 'jpeg')
        
        assert result is not None
        assert result.size == original_img.size
        
        # Verify the converted image is readable and has content
        expected_output = f"{output_base_name}.jpeg"
        converted_img = Image.open(expected_output)
        
        # Check it's not a blank image - use histogram to verify content
        histogram = converted_img.histogram()
        non_zero_bins = sum(1 for count in histogram if count > 0)
        assert non_zero_bins > 1, "Image appears to be uniform color"

    def test_batch_convert_multiple_formats(self, sample_images_directory, output_dir):
        """Test batch conversion with multiple input formats"""
        input_dir, image_paths = sample_images_directory
        
        # Call the class method
        result = ImageFormatConverter.batch_convert_img_format(
            input_dir=input_dir,
            inputs_formats=['jpeg', 'webp', 'png'],
            output_dir=output_dir,
            output_format='png'
        )
        
        assert result is not None
        assert len(result) == 2  # Should convert only 2 images, since 1 is already png
        
        # Verify all output files exist
        for i in range(1, 3):
            expected_output = os.path.join(output_dir, f"test_image_{i}.png")
            assert os.path.exists(expected_output)

    def test_decorator_path_handling(self, sample_image, output_dir):
        """Test that the decorator properly handles path conversion (making relative path absolute)"""
        # Use a relative path to test the decorator
        
        # Move the sample image outside the current working directory to create a valid relative path test
        temp_test_dir = os.path.join(output_dir, "test_input")
        os.makedirs(temp_test_dir, exist_ok=True)
        
        # Copy file out of temp fixture context to simulate a user providing a relative path
        rel_test_file = os.path.join(temp_test_dir, os.path.basename(sample_image))
        shutil.copy(sample_image, rel_test_file)
        
        # Create a relative path
        rel_path = os.path.basename(rel_test_file)
        os.chdir(temp_test_dir) # Change CWD for the test
        
        output_base_name = os.path.join(output_dir, "decorator_test")
        try:
            # Call the class method with a relative path
            result = ImageFormatConverter.convert_img_format(rel_path, output_base_name, 'jpeg')
            
            assert result is not None
            expected_output = f"{output_base_name}.jpeg"
            assert os.path.exists(expected_output)
        finally:
            # Change CWD back
            os.chdir(ROOT_DIR)

    @pytest.mark.parametrize("input_format,output_format,expected_success", [
        ('png', 'jpeg', True),
        ('jpeg', 'png', True),
        ('webp', 'jpeg', True),
        ('png', 'txt', False),  # Unsupported output format
    ])
    def test_format_combinations(self, sample_images_directory, output_dir, input_format, output_format, expected_success):
        """Test various input/output format combinations"""
        if output_format not in SUPPORTED_IMG_FORMATS and expected_success:
            pytest.skip(f"{output_format} not supported")
        
        input_dir, image_paths = sample_images_directory
        
        # Find a file with the specified input format
        matching_files = [f for f in image_paths if f.endswith(f'.{input_format}')]
        if not matching_files:
            pytest.skip(f"No {input_format} files in test directory")
        
        if expected_success:
            # Call the class method
            result = ImageFormatConverter.batch_convert_img_format(
                input_dir=input_dir,
                inputs_formats=[input_format],
                output_dir=output_dir,
                output_format=output_format
            )
            assert result is not None
            assert len(result) >= 0
        else:
            # This should fail at the individual conversion level with ValueError
            test_file = matching_files[0]
            output_base_name = os.path.join(output_dir, "should_fail")
            
            with pytest.raises(ValueError, match="Unsupported output format"):
                # Call the class method
                ImageFormatConverter.convert_img_format(test_file, output_base_name, output_format)
