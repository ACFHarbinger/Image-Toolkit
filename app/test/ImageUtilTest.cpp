#include "gtest/gtest.h"
#include "ImageUtil.h"
#include "FileSystemUtil.h"
#include <filesystem>
#include <opencv2/opencv.hpp>

namespace fs = std::filesystem;

class ImageUtilTest : public ::testing::Test {
protected:
    fs::path testDir;

    void SetUp() override {
        testDir = fs::temp_directory_path() / "img_toolkit_tests" / ::testing::UnitTest::GetInstance()->current_test_info()->name();
        fs::create_directories(testDir);
    }

    void TearDown() override {
        fs::remove_all(testDir.parent_path());
    }

    // Helper to create a dummy image for testing
    bool createDummyImage(const fs::path& path, int width, int height) {
        cv::Mat img(height, width, CV_8UC3, cv::Scalar(0, 0, 255)); // Red image
        return cv::imwrite(path.string(), img);
    }
};

TEST_F(ImageUtilTest, ConvertSingleImage) {
    fs::path inImg = testDir / "test.png";
    fs::path outImg = testDir / "test.jpg";
    ASSERT_TRUE(createDummyImage(inImg, 100, 100));

    ASSERT_TRUE(ImageUtil::convertSingleImage(inImg, outImg, false));
    
    ASSERT_TRUE(fs::exists(outImg));
    cv::Mat loaded = cv::imread(outImg.string());
    ASSERT_FALSE(loaded.empty());
    ASSERT_EQ(loaded.cols, 100);
    ASSERT_EQ(loaded.rows, 100);
}

TEST_F(ImageUtilTest, ConvertBatch) {
    fs::path inDir = testDir / "input";
    fs::path outDir = testDir / "output";
    fs::create_directories(inDir);
    fs::create_directories(outDir);
    
    ASSERT_TRUE(createDummyImage(inDir / "a.png", 50, 50));
    ASSERT_TRUE(createDummyImage(inDir / "b.bmp", 50, 50));
    ASSERT_TRUE(createDummyImage(inDir / "c.jpg", 50, 50)); // Should be skipped

    int converted = ImageUtil::convertBatch(inDir, {".png", ".bmp"}, outDir, "jpg", false);
    ASSERT_EQ(converted, 2);
    ASSERT_TRUE(fs::exists(outDir / "a.jpg"));
    ASSERT_TRUE(fs::exists(outDir / "b.jpg"));
    ASSERT_FALSE(fs::exists(outDir / "c.jpg"));
}

TEST_F(ImageUtilTest, MergeHorizontal) {
    fs::path img1 = testDir / "img1.png";
    fs::path img2 = testDir / "img2.png";
    fs::path outImg = testDir / "merged.png";
    ASSERT_TRUE(createDummyImage(img1, 100, 100));
    ASSERT_TRUE(createDummyImage(img2, 100, 100));

    ASSERT_TRUE(ImageUtil::mergeImages({img1.string(), img2.string()}, outImg, ImageUtil::MergeDirection::HORIZONTAL, 2, 0));

    ASSERT_TRUE(fs::exists(outImg));
    cv::Mat loaded = cv::imread(outImg.string());
    ASSERT_FALSE(loaded.empty());
    ASSERT_EQ(loaded.cols, 200);
    ASSERT_EQ(loaded.rows, 100);
}

TEST_F(ImageUtilTest, MergeVertical) {
    fs::path img1 = testDir / "img1.png";
    fs::path img2 = testDir / "img2.png";
    fs::path outImg = testDir / "merged.png";
    ASSERT_TRUE(createDummyImage(img1, 100, 100));
    ASSERT_TRUE(createDummyImage(img2, 100, 100));

    ASSERT_TRUE(ImageUtil::mergeImages({img1.string(), img2.string()}, outImg, ImageUtil::MergeDirection::VERTICAL, 2, 0));

    ASSERT_TRUE(fs::exists(outImg));
    cv::Mat loaded = cv::imread(outImg.string());
    ASSERT_FALSE(loaded.empty());
    ASSERT_EQ(loaded.cols, 100);
    ASSERT_EQ(loaded.rows, 200);
}