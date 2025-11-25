#pragma once

#include <string>
#include <vector>
#include <optional>
#include <opencv2/opencv.hpp>

class ImageFormatConverter {
public:
    static bool convertSingleImage(const std::string& image_path, 
                                   const std::string& output_name = "", 
                                   const std::string& format = "png", 
                                   bool delete_original = false);

    static std::vector<std::string> convertBatch(const std::string& input_dir, 
                                                 const std::vector<std::string>& input_formats, 
                                                 const std::string& output_dir = "", 
                                                 const std::string& output_format = "png", 
                                                 bool delete_original = false);

private:
    static bool convertImgCore(const std::string& image_path, 
                               const std::string& output_path, 
                               const std::string& format, 
                               bool delete_original);
    
    // Helper to handle transparency (Alpha -> White Background)
    static cv::Mat removeAlphaChannel(const cv::Mat& src);
};