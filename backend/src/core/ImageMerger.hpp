#pragma once

#include <string>
#include <vector>
#include <optional>
#include <opencv2/opencv.hpp>

class ImageMerger {
public:
    static bool mergeImages(const std::vector<std::string>& image_paths, 
                            const std::string& output_path, 
                            const std::string& direction, // horizontal, vertical, grid, stitch
                            std::pair<int, int> grid_size = {0, 0}, 
                            int spacing = 0, 
                            AlignMode align_mode = AlignMode::Default);

    static bool mergeDirectoryImages(const std::string& directory, 
                                     const std::vector<std::string>& input_formats, 
                                     const std::string& output_path, 
                                     const std::string& direction = "horizontal", 
                                     std::pair<int, int> grid_size = {0, 0}, 
                                     int spacing = 0, 
                                     AlignMode align_mode = AlignMode::Default);

private:
    static cv::Mat prepareImage(const cv::Mat& img, cv::Size target_size);

    static bool mergeHorizontal(const std::vector<cv::Mat>& images, const std::string& output_path, int spacing, AlignMode align_mode);
    static bool mergeVertical(const std::vector<cv::Mat>& images, const std::string& output_path, int spacing, AlignMode align_mode);
    static bool mergeGrid(const std::vector<cv::Mat>& images, const std::string& output_path, std::pair<int, int> grid_size, int spacing);
    static bool mergeScanStitch(const std::vector<std::string>& image_paths, const std::string& output_path);
};