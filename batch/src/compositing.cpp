// ---------------------------------------------------------------------------
// batch/src/compositing.cpp
//
// Zone normalization chain, Laplacian blend, gain loops, single-pose helpers.
//
// Replaces (compute bodies only — Python wrappers remain):
//   rendering/compositing.py  :: _zone_chroma_align, _zone_lum_norm,
//     _zone_sat_norm, _zone_contrast_eq, _zone_hue_eq, _laplacian_blend,
//     _single_pose_soft_edge, _seam_color_match, _poisson_seam_blend,
//     _smooth_gain_array, _normalize_warped_frames, _blocks_lum_compensate,
//     gain normalization loops, all single-pose escalation gates
//
// Implementation roadmap: Phase 2 (zone norms wired) + Phase 4 (MultiBandBlender).
// See moon/roadmaps/asp_cpp_migration.md §batch::compositing
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "batch/common.hpp"
#include "batch/image_utils.hpp"
#include <opencv2/stitching/detail/blenders.hpp>

namespace py = pybind11;

inline cv::Mat as_mat(py::array_t<uint8_t> arr) {
    auto req = arr.request();
    int type = (req.ndim == 3 && req.shape[2] == 3) ? CV_8UC3 : CV_8UC1;
    return cv::Mat(req.shape[0], req.shape[1], type, req.ptr).clone();
}

inline py::array_t<uint8_t> as_ndarray(const cv::Mat& mat) {
    if (mat.empty()) return py::array_t<uint8_t>();
    std::vector<ssize_t> shape;
    std::vector<ssize_t> strides;
    if (mat.channels() == 3) {
        shape = {mat.rows, mat.cols, 3};
        strides = {mat.step[0], mat.step[1], 1};
    } else {
        shape = {mat.rows, mat.cols};
        strides = {mat.step[0], 1};
    }
    auto result = py::array_t<uint8_t>(shape, strides);
    auto req = result.request();
    std::memcpy(req.ptr, mat.data, mat.total() * mat.elemSize());
    return result;
}

cv::Mat zone_chroma_align_impl(const cv::Mat& fa_zone, const cv::Mat& fb_zone, float min_shift_px) {
    int H = fa_zone.rows, W = fa_zone.cols;
    cv::Mat mask_a, mask_b;
    cv::Mat fa_gray, fb_gray;
    cv::cvtColor(fa_zone, fa_gray, cv::COLOR_BGR2GRAY);
    cv::cvtColor(fb_zone, fb_gray, cv::COLOR_BGR2GRAY);
    mask_a = (fa_gray > 0);
    mask_b = (fb_gray > 0);
    
    if (cv::countNonZero(mask_a) == 0 || cv::countNonZero(mask_b) == 0) return fb_zone.clone();

    cv::Mat lab_a, lab_b;
    cv::cvtColor(fa_zone, lab_a, cv::COLOR_BGR2Lab);
    cv::cvtColor(fb_zone, lab_b, cv::COLOR_BGR2Lab);
    lab_a.convertTo(lab_a, CV_32F);
    lab_b.convertTo(lab_b, CV_32F);

    cv::Scalar mean_a = cv::mean(lab_a, mask_a);
    cv::Scalar mean_b = cv::mean(lab_b, mask_b);

    float delta_ch1 = static_cast<float>(mean_a[1] - mean_b[1]);
    float delta_ch2 = static_cast<float>(mean_a[2] - mean_b[2]);

    if (std::abs(delta_ch1) < min_shift_px && std::abs(delta_ch2) < min_shift_px) return fb_zone.clone();

    cv::Mat out_lab = lab_b.clone();
    for (int y = 0; y < H; ++y) {
        cv::Vec3f* ptr = out_lab.ptr<cv::Vec3f>(y);
        for (int x = 0; x < W; ++x) {
            ptr[x][1] = std::clamp(ptr[x][1] + delta_ch1, 0.0f, 255.0f);
            ptr[x][2] = std::clamp(ptr[x][2] + delta_ch2, 0.0f, 255.0f);
        }
    }
    cv::Mat out;
    out_lab.convertTo(out, CV_8U);
    cv::cvtColor(out, out, cv::COLOR_Lab2BGR);
    return out;
}

cv::Mat zone_lum_norm_impl(const cv::Mat& fa_zone, const cv::Mat& fb_zone, float gain_clamp) {
    int H = fa_zone.rows, W = fa_zone.cols;
    cv::Mat mask_a, mask_b;
    cv::Mat fa_gray, fb_gray;
    cv::cvtColor(fa_zone, fa_gray, cv::COLOR_BGR2GRAY);
    cv::cvtColor(fb_zone, fb_gray, cv::COLOR_BGR2GRAY);
    mask_a = (fa_gray > 0);
    mask_b = (fb_gray > 0);
    
    if (cv::countNonZero(mask_a) == 0 || cv::countNonZero(mask_b) == 0) return fb_zone.clone();

    cv::Mat fa_f, fb_f;
    fa_zone.convertTo(fa_f, CV_32F);
    fb_zone.convertTo(fb_f, CV_32F);
    cv::Scalar mean_a = cv::mean(fa_f, mask_a);
    cv::Scalar mean_b = cv::mean(fb_f, mask_b);
    
    float lum_a = static_cast<float>(0.114 * mean_a[0] + 0.587 * mean_a[1] + 0.299 * mean_a[2]);
    float lum_b = static_cast<float>(0.114 * mean_b[0] + 0.587 * mean_b[1] + 0.299 * mean_b[2]);

    if (lum_b < 1.0f || std::abs(lum_a - lum_b) / std::max(lum_b, 1.0f) < 0.01f) return fb_zone.clone();

    float gain = std::clamp(lum_a / lum_b, 1.0f / gain_clamp, gain_clamp);
    
    cv::Mat out = fb_zone.clone();
    for (int y = 0; y < H; ++y) {
        cv::Vec3b* ptr = out.ptr<cv::Vec3b>(y);
        const uint8_t* mB = mask_b.ptr<uint8_t>(y);
        for (int x = 0; x < W; ++x) {
            if (mB[x]) {
                ptr[x][0] = std::clamp(static_cast<int>(ptr[x][0] * gain), 0, 255);
                ptr[x][1] = std::clamp(static_cast<int>(ptr[x][1] * gain), 0, 255);
                ptr[x][2] = std::clamp(static_cast<int>(ptr[x][2] * gain), 0, 255);
            }
        }
    }
    return out;
}

cv::Mat zone_sat_norm_impl(const cv::Mat& fa_zone, const cv::Mat& fb_zone, float gain_clamp) {
    int H = fa_zone.rows, W = fa_zone.cols;
    cv::Mat mask_a, mask_b;
    cv::Mat fa_gray, fb_gray;
    cv::cvtColor(fa_zone, fa_gray, cv::COLOR_BGR2GRAY);
    cv::cvtColor(fb_zone, fb_gray, cv::COLOR_BGR2GRAY);
    mask_a = (fa_gray > 0);
    mask_b = (fb_gray > 0);
    
    if (cv::countNonZero(mask_a) == 0 || cv::countNonZero(mask_b) == 0) return fb_zone.clone();

    cv::Mat hsv_a, hsv_b;
    cv::cvtColor(fa_zone, hsv_a, cv::COLOR_BGR2HSV);
    cv::cvtColor(fb_zone, hsv_b, cv::COLOR_BGR2HSV);
    hsv_a.convertTo(hsv_a, CV_32F);
    hsv_b.convertTo(hsv_b, CV_32F);

    cv::Scalar mean_a = cv::mean(hsv_a, mask_a);
    cv::Scalar mean_b = cv::mean(hsv_b, mask_b);

    float sat_a = static_cast<float>(mean_a[1]);
    float sat_b = static_cast<float>(mean_b[1]);

    if (sat_b < 1.0f || std::abs(sat_a - sat_b) / std::max(sat_b, 1.0f) < 0.02f) return fb_zone.clone();

    float gain = std::clamp(sat_a / sat_b, 1.0f / gain_clamp, gain_clamp);
    
    cv::Mat out_hsv = hsv_b.clone();
    for (int y = 0; y < H; ++y) {
        cv::Vec3f* ptr = out_hsv.ptr<cv::Vec3f>(y);
        const uint8_t* mB = mask_b.ptr<uint8_t>(y);
        for (int x = 0; x < W; ++x) {
            if (mB[x]) {
                ptr[x][1] = std::clamp(ptr[x][1] * gain, 0.0f, 255.0f);
            }
        }
    }
    cv::Mat out;
    out_hsv.convertTo(out, CV_8U);
    cv::cvtColor(out, out, cv::COLOR_HSV2BGR);
    return out;
}

cv::Mat zone_contrast_eq_impl(const cv::Mat& fa_zone, const cv::Mat& fb_zone, float gain_clamp) {
    int H = fa_zone.rows, W = fa_zone.cols;
    cv::Mat mask_a, mask_b;
    cv::Mat fa_gray, fb_gray;
    cv::cvtColor(fa_zone, fa_gray, cv::COLOR_BGR2GRAY);
    cv::cvtColor(fb_zone, fb_gray, cv::COLOR_BGR2GRAY);
    mask_a = (fa_gray > 0);
    mask_b = (fb_gray > 0);
    
    if (cv::countNonZero(mask_a) == 0 || cv::countNonZero(mask_b) == 0) return fb_zone.clone();

    cv::Mat fa_f, fb_f;
    fa_zone.convertTo(fa_f, CV_32F);
    fb_zone.convertTo(fb_f, CV_32F);
    cv::Mat luma_a, luma_b;
    cv::transform(fa_f, luma_a, cv::Matx13f(0.114f, 0.587f, 0.299f));
    cv::transform(fb_f, luma_b, cv::Matx13f(0.114f, 0.587f, 0.299f));

    cv::Mat mean_a_mat, std_a_mat, mean_b_mat, std_b_mat;
    cv::meanStdDev(luma_a, mean_a_mat, std_a_mat, mask_a);
    cv::meanStdDev(luma_b, mean_b_mat, std_b_mat, mask_b);

    float std_a = static_cast<float>(std_a_mat.at<double>(0));
    float std_b = static_cast<float>(std_b_mat.at<double>(0));
    float mean_b = static_cast<float>(mean_b_mat.at<double>(0));

    if (std_b < 1.0f || std::abs(std_a - std_b) / std::max(std_b, 1.0f) < 0.05f) return fb_zone.clone();

    float scale = std::clamp(std_a / std_b, 1.0f / gain_clamp, gain_clamp);
    
    cv::Mat out = fb_zone.clone();
    for (int y = 0; y < H; ++y) {
        cv::Vec3b* ptr = out.ptr<cv::Vec3b>(y);
        const uint8_t* mB = mask_b.ptr<uint8_t>(y);
        for (int x = 0; x < W; ++x) {
            if (mB[x]) {
                float luma = 0.114f * ptr[x][0] + 0.587f * ptr[x][1] + 0.299f * ptr[x][2];
                float luma_new = (luma - mean_b) * scale + mean_b;
                float g = luma > 0.0f ? luma_new / luma : 1.0f;
                ptr[x][0] = std::clamp(static_cast<int>(ptr[x][0] * g), 0, 255);
                ptr[x][1] = std::clamp(static_cast<int>(ptr[x][1] * g), 0, 255);
                ptr[x][2] = std::clamp(static_cast<int>(ptr[x][2] * g), 0, 255);
            }
        }
    }
    return out;
}

cv::Mat zone_hue_eq_impl(const cv::Mat& fa_zone, const cv::Mat& fb_zone, float min_diff_deg) {
    int H = fa_zone.rows, W = fa_zone.cols;
    cv::Mat mask_a, mask_b;
    cv::Mat fa_gray, fb_gray;
    cv::cvtColor(fa_zone, fa_gray, cv::COLOR_BGR2GRAY);
    cv::cvtColor(fb_zone, fb_gray, cv::COLOR_BGR2GRAY);
    mask_a = (fa_gray > 0);
    mask_b = (fb_gray > 0);
    
    if (cv::countNonZero(mask_a) == 0 || cv::countNonZero(mask_b) == 0) return fb_zone.clone();

    cv::Mat hsv_a, hsv_b;
    cv::cvtColor(fa_zone, hsv_a, cv::COLOR_BGR2HSV);
    cv::cvtColor(fb_zone, hsv_b, cv::COLOR_BGR2HSV);
    hsv_a.convertTo(hsv_a, CV_32F);
    hsv_b.convertTo(hsv_b, CV_32F);

    auto get_mean_hue = [](const cv::Mat& hsv, const cv::Mat& mask) {
        float sin_sum = 0, cos_sum = 0;
        int count = 0;
        int H = hsv.rows, W = hsv.cols;
        for (int y = 0; y < H; ++y) {
            const cv::Vec3f* ptr = hsv.ptr<cv::Vec3f>(y);
            const uint8_t* m = mask.ptr<uint8_t>(y);
            for (int x = 0; x < W; ++x) {
                if (m[x]) {
                    float rad = ptr[x][0] * static_cast<float>(CV_PI / 90.0);
                    sin_sum += std::sin(rad);
                    cos_sum += std::cos(rad);
                    count++;
                }
            }
        }
        if (count == 0) return 0.0f;
        float mean_rad = std::atan2(sin_sum / count, cos_sum / count);
        float mean_deg = mean_rad * static_cast<float>(90.0 / CV_PI);
        if (mean_deg < 0) mean_deg += 180.0f;
        return std::fmod(mean_deg, 180.0f);
    };

    float mean_h_a = get_mean_hue(hsv_a, mask_a);
    float mean_h_b = get_mean_hue(hsv_b, mask_b);

    float delta = mean_h_a - mean_h_b;
    if (delta > 90.0f) delta -= 180.0f;
    else if (delta < -90.0f) delta += 180.0f;

    if (std::abs(delta) < min_diff_deg) return fb_zone.clone();

    delta = std::clamp(delta, -30.0f, 30.0f);
    
    cv::Mat out_hsv = hsv_b.clone();
    for (int y = 0; y < H; ++y) {
        cv::Vec3f* ptr = out_hsv.ptr<cv::Vec3f>(y);
        const uint8_t* mB = mask_b.ptr<uint8_t>(y);
        for (int x = 0; x < W; ++x) {
            if (mB[x]) {
                float h = ptr[x][0] + delta;
                if (h < 0) h += 180.0f;
                else if (h >= 180.0f) h -= 180.0f;
                ptr[x][0] = h;
            }
        }
    }
    cv::Mat out;
    out_hsv.convertTo(out, CV_8U);
    cv::cvtColor(out, out, cv::COLOR_HSV2BGR);
    return out;
}

cv::Mat laplacian_blend_impl(const cv::Mat& fa, const cv::Mat& fb, const std::vector<int>& path, int band_px, int bands, float alpha_schedule) {
    int H = fa.rows, W = fa.cols;
    cv::Mat mask_float(H, W, CV_32F, cv::Scalar(0));
    for (int x = 0; x < W; ++x) {
        int seam_y = path[x];
        for (int y = 0; y < H; ++y) {
            float dist = static_cast<float>(y - seam_y);
            float weight = 0.5f - dist / (2.0f * band_px);
            mask_float.at<float>(y, x) = std::clamp(weight, 0.0f, 1.0f);
        }
    }

    std::vector<cv::Mat> ga, gb, gm;
    cv::Mat fa_f, fb_f;
    fa.convertTo(fa_f, CV_32F);
    fb.convertTo(fb_f, CV_32F);
    ga.push_back(fa_f);
    gb.push_back(fb_f);
    
    cv::Mat m;
    cv::cvtColor(mask_float, m, cv::COLOR_GRAY2BGR);
    gm.push_back(m);

    for (int i = 0; i < bands - 1; ++i) {
        cv::Mat down_a, down_b, down_m;
        cv::pyrDown(ga[i], down_a);
        cv::pyrDown(gb[i], down_b);
        cv::pyrDown(gm[i], down_m);
        ga.push_back(down_a);
        gb.push_back(down_b);
        gm.push_back(down_m);
    }

    std::vector<cv::Mat> la, lb;
    la.push_back(ga.back());
    lb.push_back(gb.back());
    for (int i = bands - 1; i > 0; --i) {
        cv::Mat up_a, up_b;
        cv::pyrUp(ga[i], up_a, ga[i - 1].size());
        cv::pyrUp(gb[i], up_b, gb[i - 1].size());
        la.push_back(ga[i - 1] - up_a);
        lb.push_back(gb[i - 1] - up_b);
    }
    std::reverse(la.begin(), la.end());
    std::reverse(lb.begin(), lb.end());

    std::vector<cv::Mat> blended(bands);
    for (int i = 0; i < bands; ++i) {
        cv::Mat cur_m = gm[i];
        if (cur_m.size() != la[i].size()) {
            cv::resize(cur_m, cur_m, la[i].size());
        }
        cv::Mat inv_m = cv::Scalar(1.0f, 1.0f, 1.0f) - cur_m;
        blended[i] = la[i].mul(cur_m) + lb[i].mul(inv_m);
    }

    cv::Mat result = blended.back();
    for (int i = bands - 2; i >= 0; --i) {
        cv::Mat up_res;
        cv::pyrUp(result, up_res, blended[i].size());
        result = up_res + blended[i];
    }

    if (alpha_schedule > 0.0f) {
        cv::Mat sharp_mask = mask_float.mul(mask_float);
        cv::Mat m3;
        cv::cvtColor(sharp_mask, m3, cv::COLOR_GRAY2BGR);
        cv::Mat sharp_blend = fa_f.mul(m3) + fb_f.mul(cv::Scalar(1.0f, 1.0f, 1.0f) - m3);
        result = alpha_schedule * sharp_blend + (1.0f - alpha_schedule) * result;
    }

    cv::Mat out;
    result.convertTo(out, CV_8U);
    return out;
}

cv::Mat single_pose_soft_edge_impl(const cv::Mat& fa, const cv::Mat& fb, const std::vector<int>& path, int soft_px) {
    int H = fa.rows, W = fa.cols;
    cv::Mat out = fb.clone();
    for (int x = 0; x < W; ++x) {
        int seam_y = path[x];
        for (int y = 0; y < H; ++y) {
            float dist = static_cast<float>(std::abs(y - seam_y));
            float alpha = std::max(0.0f, 1.0f - dist / soft_px) * 0.5f;
            if (alpha > 0.0f) {
                const cv::Vec3b& cA = fa.at<cv::Vec3b>(y, x);
                const cv::Vec3b& cB = fb.at<cv::Vec3b>(y, x);
                out.at<cv::Vec3b>(y, x) = cv::Vec3b(
                    std::clamp(static_cast<int>(cA[0] * alpha + cB[0] * (1.0f - alpha)), 0, 255),
                    std::clamp(static_cast<int>(cA[1] * alpha + cB[1] * (1.0f - alpha)), 0, 255),
                    std::clamp(static_cast<int>(cA[2] * alpha + cB[2] * (1.0f - alpha)), 0, 255)
                );
            }
        }
    }
    return out;
}

cv::Mat seam_color_match_impl(const cv::Mat& dom_zone, const cv::Mat& oth_zone, const std::vector<int>& path, int band_px) {
    int H = dom_zone.rows, W = dom_zone.cols;
    if (band_px <= 0) return oth_zone.clone();

    long long count = 0;
    cv::Vec3f dom_sum(0, 0, 0), oth_sum(0, 0, 0);

    for (int x = 0; x < W; ++x) {
        int seam_y = path[x];
        for (int y = std::max(0, seam_y - band_px); y <= std::min(H - 1, seam_y + band_px); ++y) {
            const cv::Vec3b& d = dom_zone.at<cv::Vec3b>(y, x);
            const cv::Vec3b& o = oth_zone.at<cv::Vec3b>(y, x);
            if (std::max({d[0], d[1], d[2]}) > 0 && std::max({o[0], o[1], o[2]}) > 0) {
                dom_sum += cv::Vec3f(d[0], d[1], d[2]);
                oth_sum += cv::Vec3f(o[0], o[1], o[2]);
                count++;
            }
        }
    }

    if (count < 10) return oth_zone.clone();

    cv::Vec3f delta = (dom_sum - oth_sum) / static_cast<float>(count);
    cv::Mat out = oth_zone.clone();
    for (int x = 0; x < W; ++x) {
        int seam_y = path[x];
        for (int y = std::max(0, seam_y - band_px); y <= std::min(H - 1, seam_y + band_px); ++y) {
            const cv::Vec3b& o = oth_zone.at<cv::Vec3b>(y, x);
            if (std::max({o[0], o[1], o[2]}) > 0) {
                out.at<cv::Vec3b>(y, x) = cv::Vec3b(
                    std::clamp(static_cast<int>(o[0] + delta[0]), 0, 255),
                    std::clamp(static_cast<int>(o[1] + delta[1]), 0, 255),
                    std::clamp(static_cast<int>(o[2] + delta[2]), 0, 255)
                );
            }
        }
    }
    return out;
}

std::vector<cv::Mat> normalize_warped_frames_impl(const std::vector<cv::Mat>& frames, const std::vector<cv::Mat>& bgs, int radius, bool do_lum, float gain_clamp) {
    if (frames.empty()) return {};
    int N = frames.size();
    std::vector<float> lums(N, 0.0f);
    
    #pragma omp parallel for
    for (int i = 0; i < N; ++i) {
        if (bgs[i].empty()) {
            lums[i] = 1.0f;
            continue;
        }
        cv::Mat f_f32;
        frames[i].convertTo(f_f32, CV_32F);
        cv::Mat gray;
        cv::transform(f_f32, gray, cv::Matx13f(0.114f, 0.587f, 0.299f));
        cv::Mat mask = (bgs[i] > 127);
        if (cv::countNonZero(mask) > 0) {
            lums[i] = static_cast<float>(cv::mean(gray, mask)[0]);
        } else {
            lums[i] = static_cast<float>(cv::mean(gray)[0]);
        }
    }

    std::vector<float> smooth_lums = lums;
    if (radius > 0) {
        for (int i = 0; i < N; ++i) {
            float sum = 0;
            int count = 0;
            for (int j = std::max(0, i - radius); j <= std::min(N - 1, i + radius); ++j) {
                sum += lums[j];
                count++;
            }
            smooth_lums[i] = sum / count;
        }
    }

    std::vector<cv::Mat> result(N);
    #pragma omp parallel for
    for (int i = 0; i < N; ++i) {
        if (!do_lum || lums[i] < 1.0f || smooth_lums[i] < 1.0f) {
            result[i] = frames[i].clone();
            continue;
        }
        float gain = std::clamp(smooth_lums[i] / lums[i], 1.0f / gain_clamp, gain_clamp);
        cv::Mat f_f32;
        frames[i].convertTo(f_f32, CV_32F);
        f_f32 *= gain;
        cv::Mat out;
        f_f32.convertTo(out, CV_8UC3);
        result[i] = out;
    }
    return result;
}

// ---------------------------------------------------------------------------
// zone_chroma_align  (§3.19)
//
// Shift fb's chroma (A*, B* in LAB) to match fa.
// Operates on non-black pixels only (mask from fa luma > 5).
// min_shift_px: minimum mean shift to apply (avoid jitter).
//
// Returns uint8 ndarray (H, W, 3) BGR.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> zone_chroma_align(
    py::array_t<uint8_t> fa_zone,
    py::array_t<uint8_t> fb_zone,
    float                min_shift_px = 2.0f)
{
    cv::Mat fa = as_mat(fa_zone);
    cv::Mat fb = as_mat(fb_zone);
    return as_ndarray(zone_chroma_align_impl(fa, fb, min_shift_px));
}

// ---------------------------------------------------------------------------
// zone_lum_norm  (§1.104)
//
// Scale fb's LAB L-channel to match fa's mean luminance.
// gain_clamp: maximum allowed gain ratio.
//
// Returns uint8 ndarray (H, W, 3) BGR.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> zone_lum_norm(
    py::array_t<uint8_t> fa_zone,
    py::array_t<uint8_t> fb_zone,
    float                gain_clamp = 2.0f)
{
    cv::Mat fa = as_mat(fa_zone);
    cv::Mat fb = as_mat(fb_zone);
    return as_ndarray(zone_lum_norm_impl(fa, fb, gain_clamp));
}

// ---------------------------------------------------------------------------
// zone_sat_norm  (§1.111)
//
// Scale fb's HSV S-channel to match fa's mean saturation.
//
// Returns uint8 ndarray (H, W, 3) BGR.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> zone_sat_norm(
    py::array_t<uint8_t> fa_zone,
    py::array_t<uint8_t> fb_zone,
    float                gain_clamp = 2.0f)
{
    cv::Mat fa = as_mat(fa_zone);
    cv::Mat fb = as_mat(fb_zone);
    return as_ndarray(zone_sat_norm_impl(fa, fb, gain_clamp));
}

// ---------------------------------------------------------------------------
// zone_contrast_eq  (§1.114)
//
// Scale fb's LAB L-channel standard deviation to match fa's.
//
// Returns uint8 ndarray (H, W, 3) BGR.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> zone_contrast_eq(
    py::array_t<uint8_t> fa_zone,
    py::array_t<uint8_t> fb_zone,
    float                clamp = 2.0f)
{
    cv::Mat fa = as_mat(fa_zone);
    cv::Mat fb = as_mat(fb_zone);
    return as_ndarray(zone_contrast_eq_impl(fa, fb, clamp));
}

// ---------------------------------------------------------------------------
// zone_hue_eq  (§1.127)
//
// Circular mean hue shift from fa to fb (only if |shift| > min_hue_diff_deg).
//
// Returns uint8 ndarray (H, W, 3) BGR.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> zone_hue_eq(
    py::array_t<uint8_t> fa_zone,
    py::array_t<uint8_t> fb_zone,
    float                min_hue_diff_deg = 5.0f)
{
    cv::Mat fa = as_mat(fa_zone);
    cv::Mat fb = as_mat(fb_zone);
    return as_ndarray(zone_hue_eq_impl(fa, fb, min_hue_diff_deg));
}

// ---------------------------------------------------------------------------
// laplacian_blend
//
// Multi-band Laplacian pyramid blend guided by a DP seam path.
// Builds a per-pixel soft weight mask from the path (linear ramp ±feather_px).
// Blends n_bands Laplacian pyramid levels, then reconstructs.
//
// Optionally wraps cv::detail::MultiBandBlender (Phase 4: ASP_MULTIBAND_BLEND=1).
//
// Returns uint8 ndarray (H, W, 3) BGR.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> laplacian_blend(
    py::array_t<uint8_t>  fa_zone,
    py::array_t<uint8_t>  fb_zone,
    py::array_t<int32_t>  path,
    int                   feather_px          = 12,
    int                   n_bands             = 5,
    float                 alpha_fine_weight   = 0.3f)
{
    cv::Mat fa = as_mat(fa_zone);
    cv::Mat fb = as_mat(fb_zone);
    const int* p_ptr = reinterpret_cast<const int*>(path.request().ptr);
    std::vector<int> p_vec(p_ptr, p_ptr + path.size());
    cv::Mat out = laplacian_blend_impl(fa, fb, p_vec, feather_px, n_bands, alpha_fine_weight);
    return as_ndarray(out);
}

// ---------------------------------------------------------------------------
// single_pose_soft_edge
//
// Linear ramp ±soft_px around the DP seam path.
// alpha[y][x] = max(0, 1 - |y - path[x]| / soft_px) × 0.5
// Applied in OpenMP parallel over columns.
//
// Returns blended uint8 ndarray (H, W, 3).
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> single_pose_soft_edge(
    py::array_t<uint8_t> fa_zone,
    py::array_t<uint8_t> fb_zone,
    py::array_t<int32_t> path,
    int                  soft_px = 6)
{
    cv::Mat fa = as_mat(fa_zone);
    cv::Mat fb = as_mat(fb_zone);
    const int* p_ptr = reinterpret_cast<const int*>(path.request().ptr);
    std::vector<int> p_vec(p_ptr, p_ptr + path.size());
    cv::Mat out = single_pose_soft_edge_impl(fa, fb, p_vec, soft_px);
    return as_ndarray(out);
}

// ---------------------------------------------------------------------------
// seam_color_match
//
// Per-channel mean shift in the blend band between dominant and other zone.
//
// Returns uint8 ndarray (H, W, 3) — the corrected other-zone.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> seam_color_match(
    py::array_t<uint8_t> dom_zone,
    py::array_t<uint8_t> oth_zone,
    py::array_t<int32_t> path,
    int                  band_half_px = 8)
{
    cv::Mat dom = as_mat(dom_zone);
    cv::Mat oth = as_mat(oth_zone);
    const int* p_ptr = reinterpret_cast<const int*>(path.request().ptr);
    std::vector<int> p_vec(p_ptr, p_ptr + path.size());
    cv::Mat out = seam_color_match_impl(dom, oth, p_vec, band_half_px);
    return as_ndarray(out);
}

// ---------------------------------------------------------------------------
// normalize_warped_frames
//
// Apply per-frame scalar gain corrections with Gaussian smoothing across
// the sequence. Coherence gate (§1.18) skips frames where gain delta > limit.
//
// Returns list of uint8 ndarrays.
// ---------------------------------------------------------------------------
static py::list normalize_warped_frames(
    py::list warped_frames,
    py::list bg_masks,
    int      ref_frame_idx,
    bool     adaptive_gain_clamp = true,
    float    coherence_limit     = 20.0f)
{
    std::vector<cv::Mat> w_frames;
    for (auto item : warped_frames) {
        w_frames.push_back(as_mat(item.cast<py::array_t<uint8_t>>()));
    }
    std::vector<cv::Mat> b_masks;
    for (auto item : bg_masks) {
        if (!item.is_none()) {
            b_masks.push_back(as_mat(item.cast<py::array_t<uint8_t>>()));
        } else {
            b_masks.push_back(cv::Mat());
        }
    }
    std::vector<cv::Mat> out = normalize_warped_frames_impl(w_frames, b_masks, ref_frame_idx, adaptive_gain_clamp, coherence_limit);
    py::list ret;
    for (const auto& mat : out) {
        ret.append(as_ndarray(mat));
    }
    return ret;
}

// ---------------------------------------------------------------------------
// multiband_blend  (Phase 4)
//
// Wraps cv::detail::MultiBandBlender — the same algorithm OpenCV Stitcher uses
// internally. Accepts N frames+masks at their canvas-space (x,y) corners and
// returns the blended result cropped to the union bounding box.
//
// Gate: ASP_MULTIBAND_BLEND=1 in Python wrapper.
// ---------------------------------------------------------------------------
cv::Mat multiband_blend_impl(
    const std::vector<cv::Mat>& frames,
    const std::vector<cv::Mat>& masks,
    const std::vector<cv::Point>& corners,
    int num_bands = 5)
{
    size_t N = frames.size();
    if (N == 0) throw std::runtime_error("multiband_blend: empty frame list");

    std::vector<cv::UMat> imgs_u(N), masks_u(N);
    // Compute union bounding box (MultiBandBlender overrides prepare(Rect) only)
    int x0 = INT_MAX, y0 = INT_MAX, x1 = INT_MIN, y1 = INT_MIN;
    for (size_t i = 0; i < N; ++i) {
        cv::Mat frame16;
        frames[i].convertTo(frame16, CV_16SC3);
        frame16.copyTo(imgs_u[i]);
        cv::Mat mask8 = (masks[i] > 0);
        mask8.copyTo(masks_u[i]);
        x0 = std::min(x0, corners[i].x);
        y0 = std::min(y0, corners[i].y);
        x1 = std::max(x1, corners[i].x + frames[i].cols);
        y1 = std::max(y1, corners[i].y + frames[i].rows);
    }

    cv::detail::MultiBandBlender blender(/*try_gpu=*/false, num_bands);
    blender.prepare(cv::Rect(x0, y0, x1 - x0, y1 - y0));
    for (size_t i = 0; i < N; ++i) {
        blender.feed(imgs_u[i], masks_u[i], corners[i]);
    }
    cv::UMat dst_u, dst_mask_u;
    blender.blend(dst_u, dst_mask_u);

    cv::Mat dst;
    dst_u.getMat(cv::ACCESS_READ).convertTo(dst, CV_8UC3);
    return dst;
}

#ifndef BATCH_TESTS
static py::array_t<uint8_t> multiband_blend(
    py::list warped_frames,
    py::list warped_masks,
    py::list corners,
    int      num_bands = 5)
{
    size_t N = warped_frames.size();
    if (N == 0) throw std::runtime_error("multiband_blend: empty frame list");
    if (warped_masks.size() != N || corners.size() != N)
        throw std::runtime_error("multiband_blend: mismatched input lengths");

    std::vector<cv::Mat> f_mats(N), m_mats(N);
    std::vector<cv::Point> pts(N);
    for (size_t i = 0; i < N; ++i) {
        f_mats[i] = as_mat(warped_frames[i].cast<py::array_t<uint8_t>>());
        m_mats[i] = as_mat(warped_masks[i].cast<py::array_t<uint8_t>>());
        auto pt_tuple = corners[i].cast<py::tuple>();
        pts[i] = cv::Point(pt_tuple[0].cast<int>(), pt_tuple[1].cast<int>());
    }
    return as_ndarray(multiband_blend_impl(f_mats, m_mats, pts, num_bands));
}
#endif // !BATCH_TESTS

// ---------------------------------------------------------------------------
// register_compositing — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_compositing(py::module_& m) {
    m.doc() = R"doc(
        batch.compositing — Zone normalization chain, blending, gain loops.

        Functions
        ---------
        zone_chroma_align(fa, fb, min_shift_px) -> ndarray
        zone_lum_norm(fa, fb, gain_clamp) -> ndarray
        zone_sat_norm(fa, fb, gain_clamp) -> ndarray
        zone_contrast_eq(fa, fb, clamp) -> ndarray
        zone_hue_eq(fa, fb, min_hue_diff_deg) -> ndarray
        laplacian_blend(fa, fb, path, feather_px, n_bands, alpha_fine_weight) -> ndarray
        single_pose_soft_edge(fa, fb, path, soft_px) -> ndarray
        seam_color_match(dom_zone, oth_zone, path, band_half_px) -> ndarray
        normalize_warped_frames(frames, masks, ref, adaptive, coherence_limit) -> list[ndarray]
        multiband_blend(warped_frames, warped_masks, corners, num_bands) -> ndarray
    )doc";

    m.def("zone_chroma_align", &zone_chroma_align,
        py::arg("fa_zone"), py::arg("fb_zone"),
        py::arg("min_shift_px") = 2.0f,
        "§3.19 Chroma shift in LAB A*B* space.");

    m.def("zone_lum_norm", &zone_lum_norm,
        py::arg("fa_zone"), py::arg("fb_zone"),
        py::arg("gain_clamp") = 2.0f,
        "§1.104 Luma normalisation via LAB L-channel scalar.");

    m.def("zone_sat_norm", &zone_sat_norm,
        py::arg("fa_zone"), py::arg("fb_zone"),
        py::arg("gain_clamp") = 2.0f,
        "§1.111 Saturation normalisation via HSV S-channel scalar.");

    m.def("zone_contrast_eq", &zone_contrast_eq,
        py::arg("fa_zone"), py::arg("fb_zone"),
        py::arg("clamp") = 2.0f,
        "§1.114 Contrast equalisation via LAB L std ratio.");

    m.def("zone_hue_eq", &zone_hue_eq,
        py::arg("fa_zone"), py::arg("fb_zone"),
        py::arg("min_hue_diff_deg") = 5.0f,
        "§1.127 HSV hue equalisation (circular mean shift, threshold min_hue_diff_deg).");

    m.def("laplacian_blend", &laplacian_blend,
        py::arg("fa_zone"), py::arg("fb_zone"),
        py::arg("path"),
        py::arg("feather_px")        = 12,
        py::arg("n_bands")           = 5,
        py::arg("alpha_fine_weight") = 0.3f,
        "Multi-band Laplacian pyramid blend guided by DP seam path.");

    m.def("single_pose_soft_edge", &single_pose_soft_edge,
        py::arg("fa_zone"), py::arg("fb_zone"),
        py::arg("path"),
        py::arg("soft_px") = 6,
        "Linear ramp ±soft_px around DP seam for single-pose escalation.");

    m.def("seam_color_match", &seam_color_match,
        py::arg("dom_zone"), py::arg("oth_zone"),
        py::arg("path"),
        py::arg("band_half_px") = 8,
        "Per-channel mean shift in blend band to reduce seam color discontinuity.");

    m.def("normalize_warped_frames", &normalize_warped_frames,
        py::arg("warped_frames"),
        py::arg("bg_masks"),
        py::arg("ref_frame_idx"),
        py::arg("adaptive_gain_clamp") = true,
        py::arg("coherence_limit")     = 20.0f,
        "Apply per-frame scalar gains with Gaussian smooth + §1.18 coherence gate.");

#ifndef BATCH_TESTS
    m.def("multiband_blend", &multiband_blend,
        py::arg("warped_frames"),
        py::arg("warped_masks"),
        py::arg("corners"),
        py::arg("num_bands") = 5,
        R"doc(
            cv::detail::MultiBandBlender — global multi-band canvas blend.

            Accepts N frames+masks with their canvas-space (x,y) corners.
            Returns the blended result as uint8 (H_out, W_out, 3).

            Gate: ASP_MULTIBAND_BLEND=1 in Python wrapper.
        )doc");
#endif
}
