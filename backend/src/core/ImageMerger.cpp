#include "image_tools.h"
#include "FileSystemTool.hpp"
#include <iostream>
#include <numeric>

// For Stitching
#include <opencv2/stitching.hpp>

// Helper to determine white background
cv::Mat createWhiteCanvas(int width, int height) {
    return cv::Mat(height, width, CV_8UC3, cv::Scalar(255, 255, 255));
}

cv::Mat ImageMerger::prepareImage(const cv::Mat& img, cv::Size target_size) {
    if (img.size() == target_size) return img;
    cv::Mat resized;
    cv::resize(img, resized, target_size, 0, 0, cv::INTER_LANCZOS4);
    return resized;
}

bool ImageMerger::mergeHorizontal(const std::vector<cv::Mat>& images, const std::string& output_path, int spacing, AlignMode align_mode) {
    if (images.empty()) return false;

    int max_h = 0, min_h = 999999;
    int max_w = 0, min_w = 999999;
    
    for (const auto& img : images) {
        max_h = std::max(max_h, img.rows);
        min_h = std::min(min_h, img.rows);
        max_w = std::max(max_w, img.cols);
        min_w = std::min(min_w, img.cols);
    }

    bool is_full_resize = (align_mode == AlignMode::ScaledGrow || align_mode == AlignMode::SquishShrink);
    
    int target_h = max_h;
    int target_w = 0; // Only relevant for resizing modes
    
    if (is_full_resize) {
        target_h = (align_mode == AlignMode::ScaledGrow) ? max_h : min_h;
        target_w = (align_mode == AlignMode::ScaledGrow) ? max_w : min_w;
    }

    int total_width = 0;
    if (is_full_resize) {
        total_width = target_w * images.size() + (spacing * (images.size() - 1));
    } else {
        for (const auto& img : images) total_width += img.cols;
        total_width += spacing * (images.size() - 1);
    }

    cv::Mat canvas = createWhiteCanvas(total_width, target_h);
    int x_offset = 0;

    for (const auto& img : images) {
        cv::Mat prep_img;
        if (is_full_resize) {
            prep_img = prepareImage(img, cv::Size(target_w, target_h));
        } else {
            // Only resize height if necessary, maintain aspect ratio logic could go here, 
            // but Python logic implies strict resizing or no resizing. 
            // Python: _prepare_image(img, (img.width, canvas_height))
            // But standard behavior usually preserves width.
            // Let's assume standard resize logic from Python script:
            prep_img = prepareImage(img, cv::Size(img.cols, target_h)); 
        }

        int y_offset = 0;
        if (align_mode == AlignMode::AlignBottomRight) {
            y_offset = target_h - prep_img.rows;
        } else if (align_mode == AlignMode::Center || align_mode == AlignMode::Default) {
            y_offset = (target_h - prep_img.rows) / 2;
        }

        // Copy
        prep_img.copyTo(canvas(cv::Rect(x_offset, y_offset, prep_img.cols, prep_img.rows)));
        x_offset += prep_img.cols + spacing;
    }

    return cv::imwrite(output_path, canvas);
}

bool ImageMerger::mergeVertical(const std::vector<cv::Mat>& images, const std::string& output_path, int spacing, AlignMode align_mode) {
    if (images.empty()) return false;

    int max_w = 0, min_w = 999999;
    int max_h = 0, min_h = 999999;

    for (const auto& img : images) {
        max_w = std::max(max_w, img.cols);
        min_w = std::min(min_w, img.cols);
        max_h = std::max(max_h, img.rows);
        min_h = std::min(min_h, img.rows);
    }

    bool is_full_resize = (align_mode == AlignMode::ScaledGrow || align_mode == AlignMode::SquishShrink);
    int target_w = max_w;
    int target_h = 0;

    if (is_full_resize) {
        target_w = (align_mode == AlignMode::ScaledGrow) ? max_w : min_w;
        target_h = (align_mode == AlignMode::ScaledGrow) ? max_h : min_h;
    }

    int total_height = 0;
    if (is_full_resize) {
        total_height = target_h * images.size() + (spacing * (images.size() - 1));
    } else {
        for (const auto& img : images) total_height += img.rows;
        total_height += spacing * (images.size() - 1);
    }

    cv::Mat canvas = createWhiteCanvas(target_w, total_height);
    int y_offset = 0;

    for (const auto& img : images) {
        cv::Mat prep_img;
        if (is_full_resize) {
            prep_img = prepareImage(img, cv::Size(target_w, target_h));
        } else {
            prep_img = prepareImage(img, cv::Size(target_w, img.rows));
        }

        int x_offset = 0;
        if (align_mode == AlignMode::AlignBottomRight) {
            x_offset = target_w - prep_img.cols;
        } else if (align_mode == AlignMode::Center || align_mode == AlignMode::Default) {
            x_offset = (target_w - prep_img.cols) / 2;
        }

        prep_img.copyTo(canvas(cv::Rect(x_offset, y_offset, prep_img.cols, prep_img.rows)));
        y_offset += prep_img.rows + spacing;
    }
    
    return cv::imwrite(output_path, canvas);
}

bool ImageMerger::mergeGrid(const std::vector<cv::Mat>& images, const std::string& output_path, std::pair<int, int> grid_size, int spacing) {
    int rows = grid_size.first;
    int cols = grid_size.second;
    
    if (images.empty() || images.size() > rows * cols) {
        std::cerr << "Grid Error: Invalid number of images." << std::endl;
        return false;
    }

    int max_w = 0;
    int max_h = 0;
    for (const auto& img : images) {
        max_w = std::max(max_w, img.cols);
        max_h = std::max(max_h, img.rows);
    }

    int total_w = cols * max_w + (spacing * (cols - 1));
    int total_h = rows * max_h + (spacing * (rows - 1));

    cv::Mat canvas = createWhiteCanvas(total_w, total_h);

    for (size_t i = 0; i < images.size(); ++i) {
        int r = i / cols;
        int c = i % cols;

        int x_off = c * (max_w + spacing) + (max_w - images[i].cols) / 2;
        int y_off = r * (max_h + spacing) + (max_h - images[i].rows) / 2;

        images[i].copyTo(canvas(cv::Rect(x_off, y_off, images[i].cols, images[i].rows)));
    }

    return cv::imwrite(output_path, canvas);
}

bool ImageMerger::mergeScanStitch(const std::vector<std::string>& image_paths, const std::string& output_path) {
    if (image_paths.size() < 2) return false;

    // Use OpenCV Stitcher
    // Mode Scans = 1
    auto stitcher = cv::Stitcher::create(cv::Stitcher::SCANS);
    stitcher->setRegistrationResol(0.8);

    std::vector<cv::Mat> cv_images;
    for (const auto& p : image_paths) {
        cv::Mat img = cv::imread(p);
        if (!img.empty()) cv_images.push_back(img);
    }

    cv::Mat pano;
    auto status = stitcher->stitch(cv_images, pano);

    if (status != cv::Stitcher::OK) {
        std::cerr << "Stitching failed with error code: " << status << std::endl;
        return false;
    }

    return cv::imwrite(output_path, pano);
}

bool ImageMerger::mergeImages(const std::vector<std::string>& image_paths, 
                              const std::string& output_path, 
                              const std::string& direction, 
                              std::pair<int, int> grid_size, 
                              int spacing, 
                              AlignMode align_mode) {
    
    // Ensure Directory Exists
    FSETool::createDirectoryForFile(output_path);

    // If Stitching, we don't load into vector<Mat> first because Stitcher handles file loading or we do it specifically
    if (direction == "stitch") {
        return mergeScanStitch(image_paths, output_path);
    }

    std::vector<cv::Mat> images;
    for (const auto& path : image_paths) {
        cv::Mat img = cv::imread(path);
        // Ensure 3 channels for consistency
        if (!img.empty()) {
            if (img.channels() == 4) cv::cvtColor(img, img, cv::COLOR_BGRA2BGR);
            else if (img.channels() == 1) cv::cvtColor(img, img, cv::COLOR_GRAY2BGR);
            images.push_back(img);
        }
    }

    if (images.empty()) return false;

    if (direction == "horizontal") {
        return mergeHorizontal(images, output_path, spacing, align_mode);
    } else if (direction == "vertical") {
        return mergeVertical(images, output_path, spacing, align_mode);
    } else if (direction == "grid") {
        return mergeGrid(images, output_path, grid_size, spacing);
    }
    
    std::cerr << "Invalid Direction: " << direction << std::endl;
    return false;
}

bool ImageMerger::mergeDirectoryImages(const std::string& directory, 
                                       const std::vector<std::string>& input_formats, 
                                       const std::string& output_path, 
                                       const std::string& direction, 
                                       std::pair<int, int> grid_size, 
                                       int spacing, 
                                       AlignMode align_mode) {
    std::vector<std::string> all_images;
    for (const auto& fmt : input_formats) {
        auto files = FSETool::getFilesByExtension(directory, fmt);
        all_images.insert(all_images.end(), files.begin(), files.end());
    }

    if (all_images.empty()) {
        std::cerr << "No images found in " << directory << std::endl;
        return false;
    }

    return mergeImages(all_images, output_path, direction, grid_size, spacing, align_mode);
}