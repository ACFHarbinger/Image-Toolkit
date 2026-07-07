// ---------------------------------------------------------------------------
// base/src/web/roi/roi_processor.cpp — ROI crop + saliency auto-crop.
// ---------------------------------------------------------------------------
#include "web/roi.hpp"

#include <algorithm>
#include <filesystem>
#include <random>
#include <sstream>

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

namespace fs = std::filesystem;

namespace base::roi {

RoiRect clamp_roi(const RoiRect& roi, int image_width, int image_height) {
    RoiRect out = roi;
    out.x = std::clamp(out.x, 0, std::max(0, image_width - 1));
    out.y = std::clamp(out.y, 0, std::max(0, image_height - 1));
    out.width = std::clamp(out.width, 0, image_width - out.x);
    out.height = std::clamp(out.height, 0, image_height - out.y);
    return out;
}

namespace {
std::string make_temp_path(const std::string& suffix) {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    std::ostringstream name;
    name << "roi_crop_" << rng() << suffix;
    return (fs::temp_directory_path() / name.str()).string();
}
}  // namespace

RoiCropResult crop_roi(const std::string& image_path, const RoiRect& requested,
                       int jpeg_quality) {
    RoiCropResult result;

    cv::Mat img = cv::imread(image_path, cv::IMREAD_COLOR);
    if (img.empty()) {
        result.error = "Failed to decode source image: " + image_path;
        return result;
    }

    RoiRect roi = clamp_roi(requested, img.cols, img.rows);
    if (!roi.is_valid()) {
        result.error = "ROI is empty after clamping to image bounds (" +
                       std::to_string(img.cols) + "x" + std::to_string(img.rows) + ")";
        return result;
    }

    cv::Mat cropped = img(cv::Rect(roi.x, roi.y, roi.width, roi.height)).clone();
    std::vector<int> params{cv::IMWRITE_JPEG_QUALITY, jpeg_quality};
    if (!cv::imencode(".jpg", cropped, result.data, params)) {
        result.error = "JPEG encode of cropped ROI failed";
        return result;
    }

    std::string temp_path = make_temp_path(".jpg");
    if (!cv::imwrite(temp_path, cropped, params)) {
        result.error = "Failed to write cropped ROI to temp file " + temp_path;
        return result;
    }

    result.ok = true;
    result.temp_path = temp_path;
    result.width = cropped.cols;
    result.height = cropped.rows;
    return result;
}

// Spectral-residual saliency (Hou & Zhang 2007) — no external model weights.
RoiRect auto_crop(const std::string& image_path, double coverage) {
    RoiRect none;
    cv::Mat img = cv::imread(image_path, cv::IMREAD_GRAYSCALE);
    if (img.empty()) return none;

    cv::Mat small;
    cv::resize(img, small, cv::Size(64, 64), 0, 0, cv::INTER_AREA);
    small.convertTo(small, CV_32F, 1.0 / 255.0);

    // FFT → log amplitude → spectral residual → inverse FFT → saliency map.
    cv::Mat planes[] = {small, cv::Mat::zeros(small.size(), CV_32F)};
    cv::Mat complexI;
    cv::merge(planes, 2, complexI);
    cv::dft(complexI, complexI);
    cv::split(complexI, planes);

    cv::Mat mag, angle;
    cv::cartToPolar(planes[0], planes[1], mag, angle);
    cv::Mat log_amp;
    cv::log(mag + 1e-8, log_amp);
    cv::Mat smoothed;
    cv::blur(log_amp, smoothed, cv::Size(3, 3));
    cv::Mat spectral_residual = log_amp - smoothed;

    cv::exp(spectral_residual, spectral_residual);
    cv::polarToCart(spectral_residual, angle, planes[0], planes[1]);
    cv::merge(planes, 2, complexI);
    cv::idft(complexI, complexI);
    cv::split(complexI, planes);
    cv::magnitude(planes[0], planes[1], mag);
    cv::multiply(mag, mag, mag);
    cv::GaussianBlur(mag, mag, cv::Size(5, 5), 3, 3);
    cv::normalize(mag, mag, 0, 1, cv::NORM_MINMAX);

    // Threshold at mean + std → binary salient mask → largest contour bbox.
    cv::Scalar mean, stddev;
    cv::meanStdDev(mag, mean, stddev);
    cv::Mat mask;
    cv::threshold(mag, mask, mean[0] + stddev[0], 1.0, cv::THRESH_BINARY);
    mask.convertTo(mask, CV_8U, 255);

    std::vector<std::vector<cv::Point>> contours;
    cv::findContours(mask, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);
    if (contours.empty()) return none;

    cv::Rect best;
    double best_area = 0;
    for (const auto& c : contours) {
        cv::Rect r = cv::boundingRect(c);
        double area = static_cast<double>(r.area());
        if (area > best_area) {
            best_area = area;
            best = r;
        }
    }
    if (best_area <= 0) return none;

    // Expand slightly for `coverage`, then scale 64x64 → source resolution.
    double pad = (1.0 - std::clamp(coverage, 0.5, 1.0));
    best.x -= static_cast<int>(best.width * pad * 0.5);
    best.y -= static_cast<int>(best.height * pad * 0.5);
    best.width += static_cast<int>(best.width * pad);
    best.height += static_cast<int>(best.height * pad);

    double sx = static_cast<double>(img.cols) / 64.0;
    double sy = static_cast<double>(img.rows) / 64.0;
    RoiRect out{
        static_cast<int>(best.x * sx), static_cast<int>(best.y * sy),
        static_cast<int>(best.width * sx), static_cast<int>(best.height * sy)};
    return clamp_roi(out, img.cols, img.rows);
}

}  // namespace base::roi
