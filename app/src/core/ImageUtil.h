#ifndef IMAGE_UTIL_H
#define IMAGE_UTIL_H

#include <string>
#include <vector>
#include <filesystem>
#include <opencv2/opencv.hpp> // Requires OpenCV dependency

// Corresponds to ImageFormatConverter and ImageMerger
class ImageUtil {
public:
    // --- ImageFormatConverter Methods ---

    /**
     * @brief Converts a single image file to a specified format.
     * @param imagePath Path to the input image.
     * @param outputPath Path to the output image (including new extension).
     * @param deleteOriginal If true, delete the original image.
     * @return true on success, false on failure.
     */
    static bool convertSingleImage(const std::filesystem::path& imagePath, const std::filesystem::path& outputPath, bool deleteOriginal = false);

    /**
     * @brief Converts a batch of images in a directory.
     * @param inputDir Directory to search for images.
     * @param inputFormats Vector of formats to convert (e.g., {".png", ".bmp"}).
     * @param outputDir Directory to save converted images.
     * @param outputFormat Format to convert to (e.g., "jpg").
     * @param deleteOriginal If true, delete original images.
     * @return Number of images successfully converted.
     */
    static int convertBatch(const std::filesystem::path& inputDir, const std::vector<std::string>& inputFormats, const std::filesystem::path& outputDir, const std::string& outputFormat, bool deleteOriginal = false);


    // --- ImageMerger Methods ---

    enum class MergeDirection {
        HORIZONTAL,
        VERTICAL,
        GRID
    };

    /**
     * @brief Merges a list of images.
     * @param imagePaths Vector of paths to the images.
     * @param outputPath Path to save the merged image.
     * @param direction How to merge (HORIZONTAL, VERTICAL, GRID).
     * @param gridCols Number of columns (only for GRID).
     * @param spacing Spacing in pixels between images.
     * @return true on success, false on failure.
     */
    static bool mergeImages(const std::vector<std::string>& imagePaths, const std::filesystem::path& outputPath, MergeDirection direction, int gridCols = 2, int spacing = 0);

private:
    /**
     * @brief Core logic for reading, converting, and saving an image.
     */
    static bool convertCore(const std::filesystem::path& inPath, const std::filesystem::path& outPath, bool delOriginal);
};

#endif // IMAGE_UTIL_H