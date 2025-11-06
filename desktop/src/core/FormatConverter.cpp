#include "FormatConverter.h"

namespace ImageToolkit
{
    CImg<unsigned char> ImageConverter::_convert_img_core(
        const fs::path& imagePath, 
        const fs::path& outputPath, 
        std::string format, 
        bool del)
    {
        // 1. Check input extension
        std::string fileExt = to_lower(imagePath.extension().string());
        if (std::find(SUPPORTED_IMG_FORMATS.begin(), SUPPORTED_IMG_FORMATS.end(), fileExt.substr(1)) == SUPPORTED_IMG_FORMATS.end())
        {
            throw ImageToolException("Invalid input file extension: " + fileExt);
        }

        // 2. Check output format
        std::string targetFormat = to_lower(format);
        if (std::find(SUPPORTED_IMG_FORMATS.begin(), SUPPORTED_IMG_FORMATS.end(), targetFormat) == SUPPORTED_IMG_FORMATS.end())
        {
            throw ImageToolException("Unsupported output format: " + targetFormat);
        }

        try
        {
            CImg<unsigned char> img(imagePath.c_str());

            // 3. Handle JPEG conversion (remove alpha channel)
            if (targetFormat == "jpg" || targetFormat == "jpeg")
            {
                if (img.spectrum() == 4) // 4 channels (RGBA)
                {
                    // Create a white background
                    CImg<unsigned char> background(img.width(), img.height(), 1, 3, 255);
                    // Draw the image on top, using the alpha channel as a mask
                    background.draw_image(0, 0, 0, 0, img.get_channels(0, 2), img.get_channel(3));
                    img = background;
                }
            }

            // 4. Save the image
            img.save(outputPath.c_str());

            if (del) {
                fs::remove(imagePath);
            }
            std::cout << "Converted '" << imagePath.filename().string() << "' to '" << outputPath.filename().string() << "'." << std::endl;
            return img;
        }
        catch (const CImgException& e)
        {
            std::cerr << "Warning: CImg failed to convert file " << imagePath.string() << ". Reason: " << e.what() << std::endl;
            throw ImageToolException("CImg conversion failed.");
        }
    }

    void ImageConverter::convertImgFormat(
        fs::path imagePath, 
        fs::path outputName, 
        std::string format, 
        bool del)
    {
        // Explicitly replace decorator logic
        imagePath = FileSystemEntries::makeAbsolute(imagePath);
        fs::path outputPath;

        if (outputName.empty()) {
            // Save in the same directory
            outputName = imagePath.stem();
            outputPath = imagePath.parent_path() / outputName.replace_extension(format);
        } else {
             // Use the provided output name/path
            outputPath = FileSystemEntries::makeAbsolute(outputName);
            if (outputPath.extension().empty()) {
                 outputPath.replace_extension(format);
            }
        }
        
        // Ensure the *output* directory exists
        FileSystemEntries::ensureDirectoryExists(outputPath);

        if (!fs::exists(outputPath)) {
            _convert_img_core(imagePath, outputPath, format, del);
        }
    }

    void ImageConverter::batchConvertImgFormat(
        fs::path inputDir, 
        std::vector<std::string> inputsFormats, 
        fs::path outputDir, 
        std::string outputFormat, 
        bool del)
    {
        // Explicitly replace decorator logic
        inputDir = FileSystemEntries::makeAbsolute(inputDir);
        if (outputDir.empty()) {
            outputDir = inputDir;
        }
        outputDir = FileSystemEntries::makeAbsolute(outputDir);
        FileSystemEntries::ensureDirectoryExists(outputDir / "temp.txt"); // Ensure the *directory* exists

        int convertedCount = 0;
        for (const std::string& inputFormat : inputsFormats)
        {
            auto files = FileSystemEntries::getFilesByExtension(inputDir, inputFormat, false);
            for (const auto& inputFile : files)
            {
                fs::path outputPath = outputDir / inputFile.filename().replace_extension(outputFormat);
                if (!fs::exists(outputPath))
                {
                    try {
                        _convert_img_core(inputFile, outputPath, outputFormat, del);
                        convertedCount++;
                    } catch (const std::exception& e) {
                        // Log and continue
                        std::cerr << e.what() << std::endl;
                    }
                }
            }
        }
        std::cout << "\nBatch conversion complete! Converted " << convertedCount << " images." << std::endl;
    }

} // namespace ImageToolkit