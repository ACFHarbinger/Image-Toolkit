#pragma once

#include "gtest/gtest.h"
#include "Common.h"
#include "FileSystemEntries.h"
#include "FormatConverter.h"
#include "ImageMerger.h"
#include <fstream>

// Use the project's namespace
using namespace ImageToolkit;

/**
 * @brief A base test fixture for all ImageToolkit tests.
 *
 * This class replaces the pytest fixtures by creating a temporary
 * directory structure and sample images before each test (`SetUp`)
 * and deleting it after each test (`TearDown`).
 */
class BaseTestFixture : public ::testing::Test {
protected:
    // --- Paths ---
    fs::path tempDir;
    fs::path subdirPath;
    fs::path emptySubdirPath;
    fs::path outputDir;

    // --- Test File Paths ---
    fs::path fileA_txt;
    fs::path fileB_log;
    fs::path fileC_txt;
    fs::path imgRed_png;
    fs::path imgGreen_jpg;
    fs::path imgBlue_png;
    fs::path imgTransparent_png;

    /**
     * @brief Creates a test file with empty content.
     */
    void touch(const fs::path& path) {
        std::ofstream outfile(path);
        outfile.close();
    }

    /**
     * @brief (Runs before each TEST_F)
     * Creates a temporary directory and populates it with test files.
     */
    void SetUp() override {
        // Create a unique temporary directory for this test run
        tempDir = fs::temp_directory_path() / "ImageToolkitTest_XXXXXX";
        // Note: C++17 doesn't have mkdtemp, so we create a named dir
        // and rely on TearDown to clean it.
        fs::create_directories(tempDir);

        // Define and create subdirectories
        subdirPath = tempDir / "subdirectory";
        emptySubdirPath = tempDir / "empty_subdir";
        outputDir = tempDir / "output";
        fs::create_directory(subdirPath);
        fs::create_directory(emptySubdirPath);
        fs::create_directory(outputDir);

        // --- Create test files (from test_file_system_entries.py) ---
        fileA_txt = tempDir / "file_a.txt";
        fileB_log = tempDir / "file_b.log";
        fileC_txt = subdirPath / "file_c.txt";
        touch(fileA_txt);
        touch(fileB_log);
        touch(fileC_txt);

        // --- Create test images (from test_format_converter.py / test_image_merger.py) ---
        imgRed_png = tempDir / "red_100x100.png";
        imgGreen_jpg = tempDir / "green_150x80.jpg";
        imgBlue_png = subdirPath / "blue_50x50.png";
        imgTransparent_png = tempDir / "transparent_50x50.png";
        
        try {
            // Red (100x100)
            CImg<unsigned char>(100, 100, 1, 3, 255, 0, 0).save(imgRed_png.c_str());
            
            // Green (150x80)
            CImg<unsigned char>(150, 80, 1, 3, 0, 255, 0).save(imgGreen_jpg.c_str());
            
            // Blue (50x50)
            CImg<unsigned char>(50, 50, 1, 3, 0, 0, 255).save(imgBlue_png.c_str());

            // Transparent Red (50x50, RGBA)
            CImg<unsigned char> transparent(50, 50, 1, 4, 0); // 4-channel
            // Fill R=255, A=128
            transparent.draw_rectangle(0, 0, 49, 49, CImg<unsigned char>(255, 0, 0, 128).data());
            transparent.save(imgTransparent_png.c_str());

        } catch (const CImgException& e) {
            // Fail the test immediately if image creation fails
            FAIL() << "Failed to create test images: " << e.what();
        }
    }

    /**
     * @brief (Runs after each TEST_F)
     * Cleans up the temporary directory.
     */
    void TearDown() override {
        // Recursively remove the temporary directory
        if (fs::exists(tempDir)) {
            fs::remove_all(tempDir);
        }
    }
};