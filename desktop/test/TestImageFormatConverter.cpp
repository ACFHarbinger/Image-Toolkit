#include "BaseTestFixture.h"

class ImageConverterTest : public BaseTestFixture {};

TEST_F(ImageConverterTest, ConvertPngToJpeg) {
    fs::path outputPath = outputDir / "converted_image.jpeg";
    
    ImageConverter::convertImgFormat(imgRed_png, outputPath, "jpeg");
    
    ASSERT_TRUE(fs::exists(outputPath));
    CImg<unsigned char> result(outputPath.c_str());
    ASSERT_EQ(result.width(), 100);
    ASSERT_EQ(result.height(), 100);
    ASSERT_EQ(result.spectrum(), 3); // Should be 3-channel (RGB), not 4
}

TEST_F(ImageConverterTest, ConvertTransparentPngToJpeg) {
    fs::path outputPath = outputDir / "transparent_converted.jpeg";
    
    ImageConverter::convertImgFormat(imgTransparent_png, outputPath, "jpeg");
    
    ASSERT_TRUE(fs::exists(outputPath));
    CImg<unsigned char> result(outputPath.c_str());
    ASSERT_EQ(result.spectrum(), 3); // Alpha channel should be removed
}

TEST_F(ImageConverterTest, ConvertWithNoOutputName) {
    // Should save to the same directory as the input
    fs::path expectedOutput = imgRed_png.parent_path() / "red_100x100.jpeg";
    
    ImageConverter::convertImgFormat(imgRed_png, "", "jpeg");
    
    ASSERT_TRUE(fs::exists(expectedOutput));
}

TEST_F(ImageConverterTest, UnsupportedOutputFormat) {
    fs::path outputPath = outputDir / "unsupported.txt";
    ASSERT_THROW(
        ImageConverter::convertImgFormat(imgRed_png, outputPath, "txt"),
        ImageToolException
    );
}

TEST_F(ImageConverterTest, BatchConvertCreatesDirectory) {
    fs::path nestedOutputDir = outputDir / "nested" / "batch";
    
    // Directory should be created automatically
    ASSERT_FALSE(fs::exists(nestedOutputDir));
    
    ImageConverter::batchConvertImgFormat(tempDir, {"png"}, nestedOutputDir, "jpeg");
    
    ASSERT_TRUE(fs::exists(nestedOutputDir));
    ASSERT_TRUE(fs::exists(nestedOutputDir / "red_100x100.jpeg"));
    ASSERT_TRUE(fs::exists(nestedOutputDir / "transparent_50x50.jpeg"));
}

TEST_F(ImageConverterTest, BatchConvertMultipleFormats) {
    ImageConverter::batchConvertImgFormat(tempDir, {"png", "jpg"}, outputDir, "bmp");
    
    ASSERT_TRUE(fs::exists(outputDir / "red_100x100.bmp"));
    ASSERT_TRUE(fs::exists(outputDir / "green_150x80.bmp"));
    ASSERT_TRUE(fs::exists(outputDir / "transparent_50x50.bmp"));
    
    // Check that the file from the subdirectory was NOT converted (batch is not recursive)
    ASSERT_FALSE(fs::exists(outputDir / "blue_50x50.bmp"));
}