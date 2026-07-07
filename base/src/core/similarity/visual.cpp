// ---------------------------------------------------------------------------
// base/src/core/similarity/visual.cpp
// Tier 3 structural comparison (SSIM, ORB/SIFT + RANSAC) and visual diffing.
// ---------------------------------------------------------------------------
#include "core/similarity.hpp"

#include <algorithm>
#include <cmath>

#include <opencv2/calib3d.hpp>
#include <opencv2/core.hpp>
#include <opencv2/features2d.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

namespace base::similarity {

namespace {
constexpr double SSIM_C1 = 6.5025;    // (0.01 * 255)^2
constexpr double SSIM_C2 = 58.5225;   // (0.03 * 255)^2
}

double ssim_score(const std::string& path_a, const std::string& path_b, int resize_to) {
    cv::Mat a = cv::imread(path_a, cv::IMREAD_GRAYSCALE);
    cv::Mat b = cv::imread(path_b, cv::IMREAD_GRAYSCALE);
    if (a.empty() || b.empty()) return -1.0;

    if (resize_to > 0) {
        cv::resize(a, a, cv::Size(resize_to, resize_to), 0, 0, cv::INTER_AREA);
        cv::resize(b, b, cv::Size(resize_to, resize_to), 0, 0, cv::INTER_AREA);
    } else if (a.size() != b.size()) {
        cv::resize(b, b, a.size(), 0, 0, cv::INTER_AREA);
    }

    cv::Mat i1, i2;
    a.convertTo(i1, CV_32F);
    b.convertTo(i2, CV_32F);

    cv::Mat mu1, mu2;
    cv::GaussianBlur(i1, mu1, cv::Size(11, 11), 1.5);
    cv::GaussianBlur(i2, mu2, cv::Size(11, 11), 1.5);
    cv::Mat mu1_sq = mu1.mul(mu1), mu2_sq = mu2.mul(mu2), mu1_mu2 = mu1.mul(mu2);

    cv::Mat sigma1_sq, sigma2_sq, sigma12;
    cv::GaussianBlur(i1.mul(i1), sigma1_sq, cv::Size(11, 11), 1.5);
    sigma1_sq -= mu1_sq;
    cv::GaussianBlur(i2.mul(i2), sigma2_sq, cv::Size(11, 11), 1.5);
    sigma2_sq -= mu2_sq;
    cv::GaussianBlur(i1.mul(i2), sigma12, cv::Size(11, 11), 1.5);
    sigma12 -= mu1_mu2;

    cv::Mat num = (2 * mu1_mu2 + SSIM_C1).mul(2 * sigma12 + SSIM_C2);
    cv::Mat den = (mu1_sq + mu2_sq + SSIM_C1).mul(sigma1_sq + sigma2_sq + SSIM_C2);
    cv::Mat ssim_map;
    cv::divide(num, den, ssim_map);
    return cv::mean(ssim_map)[0];
}

FeatureMatchResult match_features(const std::string& path_a, const std::string& path_b,
                                  const std::string& method, int max_features,
                                  double lowe_ratio, double ransac_threshold) {
    FeatureMatchResult res;

    cv::Mat a = cv::imread(path_a, cv::IMREAD_GRAYSCALE);
    cv::Mat b = cv::imread(path_b, cv::IMREAD_GRAYSCALE);
    if (a.empty() || b.empty()) return res;

    // Bound working size — descriptors are scale-invariant enough at 1024px.
    auto shrink = [](cv::Mat& m) {
        int side = std::max(m.cols, m.rows);
        if (side > 1024) {
            double s = 1024.0 / side;
            cv::resize(m, m, cv::Size(), s, s, cv::INTER_AREA);
        }
    };
    shrink(a);
    shrink(b);

    cv::Ptr<cv::Feature2D> detector;
    int norm_type;
    if (method == "sift") {
        detector = cv::SIFT::create(max_features);
        norm_type = cv::NORM_L2;
    } else {
        detector = cv::ORB::create(max_features);
        norm_type = cv::NORM_HAMMING;
    }

    std::vector<cv::KeyPoint> kp_a, kp_b;
    cv::Mat des_a, des_b;
    detector->detectAndCompute(a, cv::noArray(), kp_a, des_a);
    detector->detectAndCompute(b, cv::noArray(), kp_b, des_b);

    res.keypoints_a = static_cast<int>(kp_a.size());
    res.keypoints_b = static_cast<int>(kp_b.size());
    if (des_a.empty() || des_b.empty() || kp_a.size() < 4 || kp_b.size() < 4) {
        res.ok = true;   // ran fine — just no matchable content
        return res;
    }

    cv::BFMatcher matcher(norm_type, false);
    std::vector<std::vector<cv::DMatch>> knn;
    matcher.knnMatch(des_a, des_b, knn, 2);

    std::vector<cv::DMatch> good;
    for (const auto& pair : knn)
        if (pair.size() == 2 && pair[0].distance < lowe_ratio * pair[1].distance)
            good.push_back(pair[0]);

    res.good_matches = static_cast<int>(good.size());
    res.match_ratio = static_cast<double>(good.size()) /
                      std::max(1, std::min(res.keypoints_a, res.keypoints_b));

    if (good.size() >= 4) {
        std::vector<cv::Point2f> pts_a, pts_b;
        pts_a.reserve(good.size());
        pts_b.reserve(good.size());
        for (const auto& m : good) {
            pts_a.push_back(kp_a[m.queryIdx].pt);
            pts_b.push_back(kp_b[m.trainIdx].pt);
        }
        cv::Mat inlier_mask;
        cv::Mat H = cv::findHomography(pts_a, pts_b, cv::RANSAC, ransac_threshold,
                                       inlier_mask);
        if (!H.empty()) {
            res.inliers = cv::countNonZero(inlier_mask);
            res.inlier_ratio = static_cast<double>(res.inliers) /
                               static_cast<double>(good.size());
        }
    }

    // Confidence blends the volume of geometric agreement with match density.
    double inlier_term = std::min(1.0, res.inliers / 50.0);
    res.confidence = std::max(0.0, std::min(1.0,
        0.6 * inlier_term * res.inlier_ratio + 0.4 * std::min(1.0, res.match_ratio * 4.0)));
    res.ok = true;
    return res;
}

DiffResult diff_mask(const std::string& path_a, const std::string& path_b,
                     const std::string& out_path, int tolerance) {
    DiffResult res;

    cv::Mat a = cv::imread(path_a, cv::IMREAD_COLOR);
    cv::Mat b = cv::imread(path_b, cv::IMREAD_COLOR);
    if (a.empty() || b.empty()) return res;
    if (a.size() != b.size()) cv::resize(b, b, a.size(), 0, 0, cv::INTER_AREA);

    cv::Mat diff;
    cv::absdiff(a, b, diff);
    cv::Mat diff_gray;
    cv::cvtColor(diff, diff_gray, cv::COLOR_BGR2GRAY);
    cv::Mat mask;
    cv::threshold(diff_gray, mask, tolerance, 255, cv::THRESH_BINARY);
    res.changed_ratio = static_cast<double>(cv::countNonZero(mask)) /
                        static_cast<double>(mask.total());

    // Base layer: darkened grayscale of A; changed pixels: neon green.
    cv::Mat base_gray;
    cv::cvtColor(a, base_gray, cv::COLOR_BGR2GRAY);
    cv::Mat overlay;
    cv::cvtColor(base_gray, overlay, cv::COLOR_GRAY2BGR);
    overlay *= 0.35;
    overlay.setTo(cv::Scalar(102, 255, 57), mask);   // BGR neon green #39FF66

    if (!cv::imwrite(out_path, overlay)) return res;
    res.out_path = out_path;
    res.ok = true;
    return res;
}

}  // namespace base::similarity
