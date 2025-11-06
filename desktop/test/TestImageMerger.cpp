#include "BaseTestFixture.h"

class ImageMergerTest : public BaseTestFixture {};

TEST_F(ImageMergerTest, MergeHorizontal) {
    fs::path outputPath = outputDir / "horizontal_merge.png";
    std::vector<fs::path> paths = {imgRed_png, imgGreen_jpg}; // 100x100, 150x80
    
    ImageMerger::mergeImages(paths, outputPath, "horizontal");
    
    ASSERT_TRUE(fs::exists(outputPath));
    CImg<unsigned char> result(outputPath.c_str());
    
    // total width = 100 + 150 = 250
    // max height = max(100, 80) = 100
    ASSERT_EQ(result.width(), 250);
    ASSERT_EQ(result.height(), 100);
}

TEST_F(ImageMergerTest, MergeHorizontalWithSpacing) {
    fs::path outputPath = outputDir / "horizontal_spacing.png";
    std::vector<fs::path> paths = {imgRed_png, imgGreen_jpg}; // 100x100, 150x80
    int spacing = 10;
    
    ImageMerger::mergeImages(paths, outputPath, "horizontal", {0,0}, spacing);
    
    ASSERT_TRUE(fs::exists(outputPath));
    CImg<unsigned char> result(outputPath.c_str());
    
    // total width = 100 + 150 + 10 (spacing) = 260
    // max height = 100
    ASSERT_EQ(result.width(), 260);
    ASSERT_EQ(result.height(), 100);
}

TEST_F(ImageMergerTest, MergeVertical) {
    fs::path outputPath = outputDir / "vertical_merge.png";
    std::vector<fs::path> paths = {imgRed_png, imgGreen_jpg}; // 100x100, 150x80
    
    ImageMerger::mergeImages(paths, outputPath, "vertical");
    
    ASSERT_TRUE(fs::exists(outputPath));
    CImg<unsigned char> result(outputPath.c_str());
    
    // max width = max(100, 150) = 150
    // total height = 100 + 80 = 180
    ASSERT_EQ(result.width(), 150);
    ASSERT_EQ(result.height(), 180);
}

TEST_F(ImageMergerTest, MergeGrid) {
    fs::path outputPath = outputDir / "grid_merge.png";
    std::vector<fs::path> paths = {imgRed_png, imgGreen_jpg, imgBlue_png, imgTransparent_png};
    std::pair<int, int> gridSize = {2, 2}; // 2x2
    
    ImageMerger::mergeImages(paths, outputPath, "grid", gridSize, 10);
    
    ASSERT_TRUE(fs::exists(outputPath));
    CImg<unsigned char> result(outputPath.c_str());
    
    // max width = 150 (from green)
    // max height = 100 (from red)
    // total width = 2 * 150 + 10 (spacing) = 310
    // total height = 2 * 100 + 10 (spacing) = 210
    ASSERT_EQ(result.width(), 310);
    ASSERT_EQ(result.height(), 210);
}

TEST_F(ImageMergerTest, MergeGridTooManyImages) {
    fs::path outputPath = outputDir / "grid_error.png";
    std::vector<fs::path> paths = {imgRed_png, imgGreen_jpg, imgBlue_png}; // 3 images
    std::pair<int, int> gridSize = {1, 2}; // 1x2 grid (2 slots)

    ASSERT_THROW(
        ImageMerger::mergeImages(paths, outputPath, "grid", gridSize),
        ImageToolException
    );
}

TEST_F(ImageMergerTest, MergeInvalidDirection) {
    fs::path outputPath = outputDir / "invalid.png";
    std::vector<fs::path> paths = {imgRed_png};
    
    ASSERT_THROW(
        ImageMerger::mergeImages(paths, outputPath, "diagonal"),
        ImageToolException
    );
}

TEST_F(ImageMergerTest, MergeDirectoryImages) {
    fs::path outputPath = outputDir / "directory_merge.png";
    
    // Should find imgRed_png, imgGreen_jpg, imgTransparent_png
    ImageMerger::mergeDirectoryImages(tempDir, {"png", "jpg"}, outputPath, "horizontal");
    
    ASSERT_TRUE(fs::exists(outputPath));
    CImg<unsigned char> result(outputPath.c_str());

    // 100 (red) + 150 (green) + 50 (transparent)
    ASSERT_EQ(result.width(), 100 + 150 + 50); 
    // max(100, 80, 50)
    ASSERT_EQ(result.height(), 100); 
}