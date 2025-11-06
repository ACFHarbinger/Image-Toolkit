#pragma once
#include "Common.h"
#include "FileSystemEntries.h"

namespace ImageToolkit
{
    /**
     * @brief A tool for converting image formats for single files and batches.
     * Replaces ImageFormatConverter.
     */
    class ImageConverter
    {
    private:
        /**
         * @brief Core logic for image format conversion.
         */
        static CImg<unsigned char> _convert_img_core(
            const fs::path& imagePath, 
            const fs::path& outputPath, 
            std::string format, 
            bool del);

    public:
        /**
         * @brief Converts a single image file to a specified format.
         */
        static void convertImgFormat(
            fs::path imagePath, 
            fs::path outputName, 
            std::string format = "png", 
            bool del = false);

        /**
         * @brief Converts all images in a directory matching input_formats.
         */
        static void batchConvertImgFormat(
            fs::path inputDir, 
            std::vector<std::string> inputsFormats, 
            fs::path outputDir, 
            std::string outputFormat = "png", 
            bool del = false);
    };

} // namespace ImageToolkit