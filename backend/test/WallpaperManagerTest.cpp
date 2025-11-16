#include "gtest/gtest.h"
#include "../src/core/WallpaperManager.h"
#include <map>
#include <string>

TEST(WallpaperManagerTest, ApplyWallpaper) {
    // --- THIS TEST IS INTENTIONALLY DISABLED ---
    //
    // Running this test would change your actual desktop wallpaper,
    // which is a dangerous side effect for an automated test.
    //
    // To run this manually:
    // 1. Create a dummy image:
    //    fs::path imgPath = "/tmp/test_wallpaper.png";
    //    cv::Mat img(100, 100, CV_8UC3, cv::Scalar(255, 0, 0)); // Blue
    //    cv::imwrite(imgPath.string(), img);
    //
    // 2. Call the manager:
    //    std::map<std::string, std::string> pathMap;
    //    pathMap["0"] = imgPath.string();
    //    WallpaperManager::applyWallpaper(pathMap, 1);
    //
    // 3. Visually confirm your wallpaper changed.
    
    FAIL() << "Test skipped: This test modifies the live desktop wallpaper and is unsafe to run automatically.";
}