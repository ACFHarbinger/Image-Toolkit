#pragma once
#include "Common.h"
#include "FileSystemEntries.h"

namespace ImageToolkit
{
    /**
     * @brief A tool for merging images horizontally, vertically, or in a grid.
     * Replaces the Python ImageMerger class.
     */
    class ImageMerger
    {
    private:
        // --- Core Merging Logic ---
        
        static CImg<unsigned char> _merge_images_horizontal(
            const std::vector<fs::path>& imagePaths, 
            int spacing);

        static CImg<unsigned char> _merge_images_vertical(
            const std::vector<fs::path>& imagePaths, 
            int spacing);

        static CImg<unsigned char> _merge_images_grid(
            const std::vector<fs::path>& imagePaths, 
            std::pair<int, int> gridSize, 
            int spacing);

    public:
        /**
         * @brief Merges images based on direction ('horizontal', 'vertical', or 'grid').
         */
        static void mergeImages(
            std::vector<fs::path> imagePaths, 
            fs::path outputPath, 
            const std::string& direction, 
            std::pair<int, int> gridSize = {0, 0}, 
            int spacing = 0);

        /**
         * @brief Merges all images of specified formats found in a directory.
         */
        static void mergeDirectoryImages(
            fs::path directory, 
            const std::vector<std::string>& inputFormats, 
            fs::path outputPath, 
            const std::string& direction = "horizontal", 
            std::pair<int, int> gridSize = {0, 0}, 
            int spacing = 0);
    };

} // namespace ImageToolkit