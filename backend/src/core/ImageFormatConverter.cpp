#include "ImageFormatConverter.hpp"
#include "FileSystemTool.hpp"
#include <iostream>
#include <filesystem>
#include <algorithm>

namespace fs = std::filesystem;

// Helper to check if format is jpg
bool isJpeg(const std::string& fmt) {
    std::string f = fmt;
    std::transform(f.begin(), f.end(), f.begin(), ::tolower);
    return f == "jpg" || f == "jpeg";
}

cv::Mat ImageFormatConverter::removeAlphaChannel(const cv::Mat& src) {
    if (src.channels() != 4) return src;

    // Create white background
    cv::Mat bg(src.size(), CV_8UC3, cv::Scalar(255, 255, 255));
    
    // Split source
    std::vector<cv::Mat> channels;
    cv::split(src, channels);
    
    cv::Mat alpha = channels[3];
    cv::Mat rgb;
    cv::merge(std::vector<cv::Mat>{channels[0], channels[1], channels[2]}, rgb);
    
    // Blend: dst = src * alpha + bg * (1 - alpha)
    alpha.convertTo(alpha, CV_32F, 1.0/255.0);
    rgb.convertTo(rgb, CV_32F);
    bg.convertTo(bg, CV_32F);
    
    cv::Mat dst = cv::Mat::zeros(src.size(), CV_32FC3);
    
    for (int i = 0; i < 3; ++i) {
        cv::Mat src_c, bg_c;
        cv::extractChannel(rgb, src_c, i);
        cv::extractChannel(bg, bg_c, i);
        
        cv::Mat res = src_c.mul(alpha) + bg_c.mul(1.0 - alpha);
        cv::insertChannel(res, dst, i);
    }
    
    dst.convertTo(dst, CV_8UC3);
    return dst;
}

bool ImageFormatConverter::convertImgCore(const std::string& image_path, 
                                          const std::string& output_path, 
                                          const std::string& format, 
                                          bool delete_original) {
    try {
        cv::Mat img = cv::imread(image_path, cv::IMREAD_UNCHANGED);
        if (img.empty()) {
            std::cerr << "Warning: Failed to load " << image_path << std::endl;
            return false;
        }

        // Handle transparency for JPEGs
        if (isJpeg(format) && img.channels() == 4) {
            img = removeAlphaChannel(img);
        }

        // Ensure output directory exists (mimics prefix_create_directory)
        FSETool::createDirectoryForFile(output_path);

        if (cv::imwrite(output_path, img)) {
            std::cout << "Converted '" << fs::path(image_path).filename().string() 
                      << "' to '" << fs::path(output_path).filename().string() << "'." << std::endl;
            if (delete_original) {
                FileDeleter::deletePath(image_path);
            }
            return true;
        }
        return false;
    } catch (const std::exception& e) {
        std::cerr << "Conversion Error: " << e.what() << std::endl;
        return false;
    }
}

bool ImageFormatConverter::convertSingleImage(const std::string& image_path, 
                                              const std::string& output_name, 
                                              const std::string& format, 
                                              bool delete_original) {
    std::string abs_path = FSETool::toAbsolutePath(image_path);
    if (!fs::exists(abs_path)) return false;

    fs::path p(abs_path);
    std::string out_path;

    if (output_name.empty()) {
        out_path = (p.parent_path() / (p.stem().string() + "." + format)).string();
    } else {
        // If output_name is just a name, append format. If it has a path, use it.
        fs::path out_p(output_name);
        if (!out_p.has_extension()) out_p.replace_extension("." + format);
        out_path = out_p.string();
    }

    if (fs::exists(out_path)) return false;
    return convertImgCore(abs_path, out_path, format, delete_original);
}

std::vector<std::string> ImageFormatConverter::convertBatch(const std::string& input_dir, 
                                                            const std::vector<std::string>& input_formats, 
                                                            const std::string& output_dir, 
                                                            const std::string& output_format, 
                                                            bool delete_original) {
    std::vector<std::string> converted_files;
    std::string in_dir_abs = FSETool::toAbsolutePath(input_dir);
    std::string out_dir_abs = output_dir.empty() ? in_dir_abs : FSETool::toAbsolutePath(output_dir);

    for (const auto& fmt : input_formats) {
        // Skip converting same format
        if (fmt == output_format) continue; 
        if (isJpeg(fmt) && isJpeg(output_format)) continue;

        auto files = FSETool::getFilesByExtension(in_dir_abs, fmt);
        for (const auto& file : files) {
            fs::path p(file);
            fs::path out_p = fs::path(out_dir_abs) / (p.stem().string() + "." + output_format);
            
            if (!fs::exists(out_p)) {
                if (convertImgCore(file, out_p.string(), output_format, delete_original)) {
                    converted_files.push_back(out_p.string());
                }
            }
        }
    }
    std::cout << "\nBatch conversion complete! Converted " << converted_files.size() << " images." << std::endl;
    return converted_files;
}