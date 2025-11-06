#include "ImageMerger.h"
#include <numeric>

namespace ImageToolkit
{
    // --- Private Core Logic ---

    CImg<unsigned char> ImageMerger::_merge_images_horizontal(
        const std::vector<fs::path>& imagePaths, 
        int spacing)
    {
        std::vector<CImg<unsigned char>> images;
        int totalWidth = 0;
        int maxHeight = 0;

        for (const auto& p : imagePaths) {
            images.emplace_back(p.c_str());
            totalWidth += images.back().width();
            if (images.back().height() > maxHeight) {
                maxHeight = images.back().height();
            }
        }
        totalWidth += spacing * (images.size() - 1);

        CImg<unsigned char> mergedImage(totalWidth, maxHeight, 1, 3, 255); // White background
        
        int x_offset = 0;
        for (auto& img : images) {
            // Align to top (y=0)
            mergedImage.draw_image(x_offset, 0, 0, 0, img);
            x_offset += img.width() + spacing;
        }
        return mergedImage;
    }

    CImg<unsigned char> ImageMerger::_merge_images_vertical(
        const std::vector<fs::path>& imagePaths, 
        int spacing)
    {
        std::vector<CImg<unsigned char>> images;
        int totalHeight = 0;
        int maxWidth = 0;

        for (const auto& p : imagePaths) {
            images.emplace_back(p.c_str());
            totalHeight += images.back().height();
            if (images.back().width() > maxWidth) {
                maxWidth = images.back().width();
            }
        }
        totalHeight += spacing * (images.size() - 1);

        CImg<unsigned char> mergedImage(maxWidth, totalHeight, 1, 3, 255); // White background
        
        int y_offset = 0;
        for (auto& img : images) {
            // Center horizontally
            int x_offset = (maxWidth - img.width()) / 2;
            mergedImage.draw_image(x_offset, y_offset, 0, 0, img);
            y_offset += img.height() + spacing;
        }
        return mergedImage;
    }

    CImg<unsigned char> ImageMerger::_merge_images_grid(
        const std::vector<fs::path>& imagePaths, 
        std::pair<int, int> gridSize, 
        int spacing)
    {
        int rows = gridSize.first;
        int cols = gridSize.second;
        if (rows <= 0 || cols <= 0) {
             throw ImageToolException("Grid rows and columns must be greater than 0.");
        }
        if (imagePaths.size() > (size_t)rows * cols) {
            throw ImageToolException("More images provided than grid slots can hold.");
        }

        std::vector<CImg<unsigned char>> images;
        int maxWidth = 0;
        int maxHeight = 0;

        for (const auto& p : imagePaths) {
            images.emplace_back(p.c_str());
            if (images.back().width() > maxWidth) maxWidth = images.back().width();
            if (images.back().height() > maxHeight) maxHeight = images.back().height();
        }

        if (images.empty()) {
            throw ImageToolException("No images to merge for grid layout.");
        }

        int totalWidth = cols * maxWidth + (spacing * (cols - 1));
        int totalHeight = rows * maxHeight + (spacing * (rows - 1));
        CImg<unsigned char> mergedImage(totalWidth, totalHeight, 1, 3, 255); // White background

        for (size_t idx = 0; idx < images.size(); ++idx) {
            int row = idx / cols;
            int col = idx % cols;

            // Center in cell
            int x_offset = col * (maxWidth + spacing) + (maxWidth - images[idx].width()) / 2;
            int y_offset = row * (maxHeight + spacing) + (maxHeight - images[idx].height()) / 2;
            
            mergedImage.draw_image(x_offset, y_offset, 0, 0, images[idx]);
        }
        return mergedImage;
    }

    // --- Public Methods ---

    void ImageMerger::mergeImages(
        std::vector<fs::path> imagePaths, 
        fs::path outputPath, 
        const std::string& direction, 
        std::pair<int, int> gridSize, 
        int spacing)
    {
        // Explicitly replace decorator logic
        for (auto& p : imagePaths) {
            p = FileSystemEntries::makeAbsolute(p);
        }
        outputPath = FileSystemEntries::makeAbsolute(outputPath);
        FileSystemEntries::ensureDirectoryExists(outputPath);

        CImg<unsigned char> mergedImg;
        if (direction == "horizontal") {
            mergedImg = _merge_images_horizontal(imagePaths, spacing);
        } else if (direction == "vertical") {
            mergedImg = _merge_images_vertical(imagePaths, spacing);
        } else if (direction == "grid") {
            mergedImg = _merge_images_grid(imagePaths, gridSize, spacing);
        } else {
            throw ImageToolException("Invalid direction: choose from 'horizontal', 'vertical', or 'grid'.");
        }
        
        mergedImg.save(outputPath.c_str());
        std::cout << "Merged " << imagePaths.size() << " images into '" << outputPath.string() << "'." << std::endl;
    }

    void ImageMerger::mergeDirectoryImages(
        fs::path directory, 
        const std::vector<std::string>& inputFormats, 
        fs::path outputPath, 
        const std::string& direction, 
        std::pair<int, int> gridSize, 
        int spacing)
    {
        // Explicitly replace decorator logic
        directory = FileSystemEntries::makeAbsolute(directory);
        // Note: outputPath will be made absolute by mergeImages

        std::vector<fs::path> imagePaths;
        for (const auto& fmt : inputFormats) {
            auto files = FileSystemEntries::getFilesByExtension(directory, fmt);
            imagePaths.insert(imagePaths.end(), files.begin(), files.end());
        }

        if (imagePaths.empty()) {
            std::cerr << "WARNING: No images found in directory '" << directory.string() << "' with specified formats." << std::endl;
            return;
        }
        
        mergeImages(imagePaths, outputPath, direction, gridSize, spacing);
    }

} // namespace ImageToolkit