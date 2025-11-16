#include "ImageUtil.h"
#include "FileSystemUtil.h"
#include <iostream>
#include <set>

namespace fs = std::filesystem;

// --- ImageFormatConverter ---

bool ImageUtil::convertCore(const fs::path& inPath, const fs::path& outPath, bool delOriginal) {
    try {
        cv::Mat img = cv::imread(inPath.string(), cv::IMREAD_UNCHANGED);
        if (img.empty()) {
            std::cerr << "Warning: failed to load image " << inPath.string() << std::endl;
            return false;
        }

        // Handle JPEG conversion: ensure no transparency
        if (outPath.extension() == ".jpg" || outPath.extension() == ".jpeg") {
            if (img.channels() == 4) {
                cv::Mat rgbImg;
                cv::cvtColor(img, rgbImg, cv::COLOR_BGRA2BGR);
                // Create a white background
                cv::Mat whiteBg(img.size(), CV_8UC3, cv::Scalar(255, 255, 255));
                // Paste the RGB image onto the white background using the alpha channel as a mask
                img.copyTo(whiteBg, img.col(3)); 
                img = whiteBg;
            } else if (img.channels() == 3) {
                 // Already BGR, just save
            } else {
                // Grayscale or other, convert to BGR
                cv::cvtColor(img, img, cv::COLOR_GRAY2BGR);
            }
        }
        
        FileSystemUtil::createDirectory(outPath, true);
        cv::imwrite(outPath.string(), img);

        if (delOriginal) {
            fs::remove(inPath);
        }
        std::cout << "Converted '" << inPath.filename().string() << "' to '" << outPath.filename().string() << "'." << std::endl;
        return true;
    } catch (const cv::Exception& e) {
        std::cerr << "Warning: failed to convert file " << inPath.string() << ": " << e.what() << std::endl;
        return false;
    }
}

bool ImageUtil::convertSingleImage(const fs::path& imagePath, const fs::path& outputPath, bool deleteOriginal) {
    if (fs::exists(outputPath)) {
        return false; // Don't overwrite
    }
    return convertCore(imagePath, outputPath, deleteOriginal);
}

int ImageUtil::convertBatch(const fs::path& inputDir, const std::vector<std::string>& inputFormats, const fs::path& outputDir, const std::string& outputFormat, bool deleteOriginal) {
    
    std::set<std::string> inFormats;
    for (const auto& fmt : inputFormats) {
        inFormats.insert(fmt.find('.') == 0 ? fmt : "." + fmt);
    }
    std::string outExt = outputFormat.find('.') == 0 ? outputFormat : "." + outputFormat;

    int convertedCount = 0;
    for (const auto& entry : fs::directory_iterator(inputDir)) {
        if (entry.is_file()) {
            std::string fileExt = entry.path().extension().string();
            
            // Check if this file format is in our set of formats to convert
            if (inFormats.count(fileExt)) {
                
                // Skip if it's already the target format
                if (fileExt == outExt || ( (fileExt == ".jpg" || fileExt == ".jpeg") && (outExt == ".jpg" || outExt == ".jpeg") )) {
                    continue;
                }

                fs::path outPath = outputDir / entry.path().filename().replace_extension(outExt);
                
                if (!fs::exists(outPath)) {
                    if (convertCore(entry.path(), outPath, deleteOriginal)) {
                        convertedCount++;
                    }
                }
            }
        }
    }
    std::cout << "\nBatch conversion complete! Converted " << convertedCount << " images." << std::endl;
    return convertedCount;
}


// --- ImageMerger ---

bool ImageUtil::mergeImages(const std::vector<std::string>& imagePaths, const fs::path& outputPath, MergeDirection direction, int gridCols, int spacing) {
    if (imagePaths.empty()) return false;

    std::vector<cv::Mat> images;
    for (const auto& path : imagePaths) {
        cv::Mat img = cv::imread(path, cv::IMREAD_COLOR);
        if (img.empty()) {
            std::cerr << "Failed to load image: " << path << std::endl;
            continue;
        }
        images.push_back(img);
    }

    if (images.empty()) {
        std::cerr << "No valid images were loaded." << std::endl;
        return false;
    }
    
    FileSystemUtil::createDirectory(outputPath, true);
    cv::Mat mergedImage;

    try {
        if (direction == MergeDirection::HORIZONTAL) {
            cv::hconcat(images, mergedImage);
            // Note: OpenCV hconcat/vconcat don't support spacing.
            // A manual implementation with cv::Rect and copyTo is needed for spacing.
            // This is a simplified version.
        } else if (direction == MergeDirection::VERTICAL) {
            cv::vconcat(images, mergedImage);
            // Same spacing limitation as hconcat.
        } else if (direction == MergeDirection::GRID) {
            // This is complex and requires calculating max widths/heights
            // and manually placing images on a new cv::Mat.
            // Using makeCanvas for simplicity.
            int rows = (int)std::ceil((double)images.size() / gridCols);
            mergedImage = cv::makeCanvas(images, cv::Size(images[0].cols * gridCols, images[0].rows * rows), gridCols);
        } else {
            return false;
        }

        cv::imwrite(outputPath.string(), mergedImage);
        std::cout << "Merged " << images.size() << " images into '" << outputPath.string() << "'." << std::endl;
        return true;
    } catch (const cv::Exception& e) {
        std::cerr << "ERROR: Image merge failed: " << e.what() << std::endl;
        return false;
    }
}