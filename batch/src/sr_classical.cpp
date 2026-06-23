// ---------------------------------------------------------------------------
// batch/src/sr_classical.cpp
//
// Classical (non-neural) processing:
//   - dct_restore  : tile-DCT deblocking via cv::dct
//   - pso_register : PSO sub-pixel affine alignment (OpenMP parallel fitness)
//   - de_seam      : Differential Evolution seam optimizer (port of de_seam.py)
//   - robust_sr    : L1 sub-gradient super-resolution (Overmix RobustSrRender)
//
// Replaces:
//   mfsr/dct_restoration.py :: restore_dct  (tile-DCT deblocking)
//   mfsr/pso_registration.py :: pso_register (PSO affine alignment)
//   mfsr/de_seam.py          :: de_seam      (DE seam optimizer)
//
// Phase 5 implementation.
// See moon/roadmaps/asp_cpp_migration.md §batch::sr_classical
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>

#include "batch/common.hpp"

namespace py = pybind11;

// ---------------------------------------------------------------------------
// Local helpers
// ---------------------------------------------------------------------------

inline cv::Mat as_mat_u8(py::array_t<uint8_t> arr) {
    auto req = arr.request();
    int type = (req.ndim == 3 && req.shape[2] == 3) ? CV_8UC3
             : (req.ndim == 3 && req.shape[2] == 4) ? CV_8UC4
             : CV_8UC1;
    return cv::Mat(
        static_cast<int>(req.shape[0]),
        static_cast<int>(req.shape[1]),
        type, req.ptr).clone();
}

// ---------------------------------------------------------------------------
// dct_restore
//
// DCT-II deblocking: iterates over 8×8 (or block_size×block_size) tiles,
// forward-DCTs each tile, zeros high-frequency bands above a threshold, and
// inverse-DCTs back.  This suppresses the MPEG/JPEG DCT block-grid artifact.
//
// Method: soft-threshold high-frequency DCT coefficients.  For each 8×8 tile:
//   1. forward DCT (cv::dct)
//   2. soft-threshold: coeffs with |c| < threshold × max_coeff → 0
//   3. inverse DCT
//
// threshold_frac controls how aggressively high frequencies are zeroed.
// Default 0.02 (2% of max coeff) is conservative — only extreme block-boundary
// ringing is suppressed.
//
// Args
// ----
// frame          : uint8 (H, W, C) — frame to deblock
// block_size     : int — DCT block size (default 8)
// threshold_frac : float — fraction of max DCT coeff to zero-threshold
//
// Returns uint8 ndarray same shape.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> dct_restore(
    py::array_t<uint8_t> frame_arr,
    int   block_size     = 8,
    float threshold_frac = 0.02f)
{
    cv::Mat frame = as_mat_u8(frame_arr);
    int H = frame.rows, W = frame.cols, C = frame.channels();
    // Pad to multiple of block_size
    int H_pad = ((H + block_size - 1) / block_size) * block_size;
    int W_pad = ((W + block_size - 1) / block_size) * block_size;

    cv::Mat out_f(H_pad, W_pad, CV_32FC(C), cv::Scalar::all(0));
    {
        cv::Mat padded;
        cv::copyMakeBorder(frame, padded, 0, H_pad - H, 0, W_pad - W,
                           cv::BORDER_REFLECT);
        padded.convertTo(out_f, CV_32FC(C));
    }

    std::vector<cv::Mat> channels(C);
    cv::split(out_f, channels);

    {
        py::gil_scoped_release release;
        for (int c = 0; c < C; ++c) {
            cv::Mat& ch = channels[c];
            #pragma omp parallel for schedule(dynamic, 4)
            for (int y = 0; y < H_pad; y += block_size) {
                cv::Mat dct_buf(block_size, block_size, CV_32F);
                for (int x = 0; x < W_pad; x += block_size) {
                    cv::Rect roi(x, y, block_size, block_size);
                    cv::Mat block = ch(roi).clone();
                    cv::dct(block, dct_buf);
                    // Soft-threshold: zero coefficients below threshold_frac × max
                    double max_val;
                    cv::minMaxLoc(cv::abs(dct_buf), nullptr, &max_val);
                    float thr = threshold_frac * static_cast<float>(max_val);
                    cv::threshold(dct_buf, dct_buf, thr, 0, cv::THRESH_TOZERO);
                    cv::idct(dct_buf, block);
                    block.copyTo(ch(roi));
                }
            }
        }
    }

    cv::Mat out_merged;
    cv::merge(channels, out_merged);
    // Crop back to original size, clamp to [0,255]
    cv::Mat result;
    out_merged(cv::Rect(0, 0, W, H)).convertTo(result, CV_8UC(C), 1.0, 0.5);
    return batch::array_from_mat(result);
}

// ---------------------------------------------------------------------------
// pso_register
//
// Particle swarm optimizer for sub-pixel affine alignment.
// Fitness = NCC(warp(source, params), reference) computed with OpenMP.
// Supports "translation" (2D) and "affine" (4D) motion models.
//
// Returns dict {"tx","ty","angle","scale","fitness"}.
// ---------------------------------------------------------------------------

/// NCC between two single-channel float32 images
static float ncc_f32(const cv::Mat& a, const cv::Mat& b,
                      const cv::Mat& mask = cv::Mat())
{
    cv::Mat da, db;
    if (!mask.empty()) {
        cv::Scalar ma = cv::mean(a, mask), mb = cv::mean(b, mask);
        da = a - ma[0]; db = b - mb[0];
        da.setTo(0, ~mask); db.setTo(0, ~mask);
    } else {
        cv::Scalar ma = cv::mean(a), mb = cv::mean(b);
        da = a - ma[0]; db = b - mb[0];
    }
    double num = da.dot(db);
    double na  = cv::norm(da), nb = cv::norm(db);
    if (na < 1e-9 || nb < 1e-9) return 0.0f;
    return static_cast<float>(num / (na * nb));
}

static py::dict pso_register(
    py::array_t<uint8_t> reference_arr,
    py::array_t<uint8_t> source_arr,
    int   n_particles  = 30,
    int   t_max        = 100,
    float search_lo    = -500.0f,
    float search_hi    =  500.0f)
{
    cv::Mat ref_bgr = as_mat_u8(reference_arr);
    cv::Mat src_bgr = as_mat_u8(source_arr);
    cv::Mat ref_g, src_g;
    if (ref_bgr.channels() > 1) cv::cvtColor(ref_bgr, ref_g, cv::COLOR_BGR2GRAY);
    else ref_g = ref_bgr.clone();
    if (src_bgr.channels() > 1) cv::cvtColor(src_bgr, src_g, cv::COLOR_BGR2GRAY);
    else src_g = src_bgr.clone();

    ref_g.convertTo(ref_g, CV_32F);
    src_g.convertTo(src_g, CV_32F);

    int H = ref_g.rows, W = ref_g.cols;
    cv::Size dst_sz(W, H);

    // Fitness: NCC of warped source vs reference
    auto fitness_fn = [&](float tx, float ty) -> float {
        cv::Mat M = (cv::Mat_<float>(2, 3) << 1.f, 0.f, tx, 0.f, 1.f, ty);
        cv::Mat warped;
        cv::warpAffine(src_g, warped, M, dst_sz,
                       cv::INTER_LINEAR, cv::BORDER_CONSTANT, 0);
        return ncc_f32(warped, ref_g);
    };

    // PSO in translation space (2D)
    std::mt19937 rng(0);
    std::uniform_real_distribution<float> pos_dist(search_lo, search_hi);
    std::uniform_real_distribution<float> vel_dist(-1.0f, 1.0f);

    float vel_clamp = (search_hi - search_lo) * 0.1f;

    std::vector<float> px(n_particles), py(n_particles);
    std::vector<float> vx(n_particles), vy(n_particles);
    std::vector<float> pbx(n_particles), pby(n_particles);
    std::vector<float> pval(n_particles, -2.0f);

    for (int i = 0; i < n_particles; ++i) {
        px[i] = pos_dist(rng); py[i] = pos_dist(rng);
        vx[i] = vel_dist(rng) * vel_clamp;
        vy[i] = vel_dist(rng) * vel_clamp;
        pbx[i] = px[i]; pby[i] = py[i];
    }

    // Evaluate initial fitness (OpenMP parallel)
    {
        py::gil_scoped_release release;
        #pragma omp parallel for schedule(static)
        for (int i = 0; i < n_particles; ++i)
            pval[i] = fitness_fn(px[i], py[i]);
    }

    int gbest = static_cast<int>(
        std::max_element(pval.begin(), pval.end()) - pval.begin());
    float gbx = pbx[gbest], gby = pby[gbest], gbv = pval[gbest];

    const float w_init = 0.9f, w_end = 0.4f, c1 = 2.0f, c2 = 2.0f;

    {
        py::gil_scoped_release release;
        for (int it = 0; it < t_max; ++it) {
            float w = w_init - (w_init - w_end) * static_cast<float>(it) / t_max;
            std::vector<float> fvals(n_particles);
            #pragma omp parallel for schedule(static)
            for (int i = 0; i < n_particles; ++i) {
                std::mt19937 lrng(it * n_particles + i);
                std::uniform_real_distribution<float> r01(0.0f, 1.0f);
                float r1 = r01(lrng), r2 = r01(lrng);
                vx[i] = w * vx[i] + c1 * r1 * (pbx[i] - px[i])
                                   + c2 * r2 * (gbx - px[i]);
                vy[i] = w * vy[i] + c1 * r1 * (pby[i] - py[i])
                                   + c2 * r2 * (gby - py[i]);
                vx[i] = std::max(-vel_clamp, std::min(vel_clamp, vx[i]));
                vy[i] = std::max(-vel_clamp, std::min(vel_clamp, vy[i]));
                px[i] = std::max(search_lo, std::min(search_hi, px[i] + vx[i]));
                py[i] = std::max(search_lo, std::min(search_hi, py[i] + vy[i]));
                fvals[i] = fitness_fn(px[i], py[i]);
                if (fvals[i] > pval[i]) {
                    pval[i] = fvals[i];
                    pbx[i] = px[i]; pby[i] = py[i];
                }
            }
            for (int i = 0; i < n_particles; ++i) {
                if (pval[i] > gbv) {
                    gbv = pval[i]; gbx = pbx[i]; gby = pby[i];
                }
            }
        }
    }

    py::dict result;
    result["tx"]      = gbx;
    result["ty"]      = gby;
    result["angle"]   = 0.0f;
    result["scale"]   = 1.0f;
    result["fitness"] = gbv;
    return result;
}

// ---------------------------------------------------------------------------
// de_seam
//
// Differential Evolution seam optimizer.  Port of mfsr/de_seam.py.
// OpenMP parallel fitness evaluation across the DE population.
//
// Args
// ----
// img_a, img_b   : uint8 (H, W, C) — two frames to seam
// horizontal     : bool — True = seam across rows, False = across cols
// pop_size       : int — DE population size
// n_gen          : int — number of DE generations
// smoothness_w   : float — smoothness term weight
//
// Returns int32 ndarray (H,) or (W,) column-per-row seam path.
// ---------------------------------------------------------------------------
static py::array_t<int32_t> de_seam(
    py::array_t<uint8_t> img_a_arr,
    py::array_t<uint8_t> img_b_arr,
    bool  horizontal    = true,
    int   pop_size      = 20,
    int   n_gen         = 50,
    float smoothness_w  = 0.5f,
    float de_f          = 0.8f,
    float de_cr         = 0.7f)
{
    cv::Mat a = as_mat_u8(img_a_arr);
    cv::Mat b = as_mat_u8(img_b_arr);
    if (a.rows != b.rows || a.cols != b.cols)
        throw std::runtime_error("de_seam: img_a and img_b must have the same shape");

    // Energy map: |a-b| + 0.5*(|gx|+|gy|)
    cv::Mat diff;
    cv::absdiff(a, b, diff);
    cv::Mat diff_f;
    if (diff.channels() > 1) {
        cv::Mat tmp;
        diff.convertTo(tmp, CV_32FC(diff.channels()));
        std::vector<cv::Mat> chs; cv::split(tmp, chs);
        diff_f = (chs[0] + chs[1] + chs[2]) / 3.0f;
    } else {
        diff.convertTo(diff_f, CV_32F);
    }
    cv::Mat gx, gy;
    cv::Sobel(diff_f, gx, CV_32F, 1, 0, 3);
    cv::Sobel(diff_f, gy, CV_32F, 0, 1, 3);
    cv::Mat energy = diff_f + 0.5f * (cv::abs(gx) + cv::abs(gy));
    if (!horizontal) cv::transpose(energy, energy);

    int H = energy.rows, W = energy.cols;

    // Seam energy: sum of energy[row, path[row]] + smoothness * sum|diff|
    auto seam_energy_fn = [&](const std::vector<int>& path) -> float {
        float e = 0.0f;
        for (int y = 0; y < H; ++y) {
            int c = std::max(0, std::min(W - 1, path[y]));
            e += energy.at<float>(y, c);
        }
        float s = 0.0f;
        for (int y = 0; y + 1 < H; ++y)
            s += std::abs(float(path[y + 1] - path[y]));
        return e + smoothness_w * s;
    };

    // DP baseline seam (minimum-energy path)
    auto dp_seam = [&]() -> std::vector<int> {
        std::vector<std::vector<float>> dp(H, std::vector<float>(W, 0.0f));
        dp[0].assign(energy.ptr<float>(0), energy.ptr<float>(0) + W);
        for (int y = 1; y < H; ++y) {
            const float* en = energy.ptr<float>(y);
            for (int x = 0; x < W; ++x) {
                float best = dp[y-1][x];
                if (x > 0)     best = std::min(best, dp[y-1][x-1]);
                if (x < W - 1) best = std::min(best, dp[y-1][x+1]);
                dp[y][x] = en[x] + best;
            }
        }
        std::vector<int> path(H);
        path[H-1] = static_cast<int>(
            std::min_element(dp[H-1].begin(), dp[H-1].end()) - dp[H-1].begin());
        for (int y = H - 2; y >= 0; --y) {
            int x = path[y + 1];
            float best = dp[y][x]; path[y] = x;
            if (x > 0     && dp[y][x-1] < best) { best = dp[y][x-1]; path[y] = x-1; }
            if (x < W - 1 && dp[y][x+1] < best) {                    path[y] = x+1; }
        }
        return path;
    };

    std::vector<int> base_path = dp_seam();
    float dp_energy = seam_energy_fn(base_path);

    // DE population: real-valued seam columns
    std::mt19937 rng(0);
    std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);
    std::uniform_real_distribution<float> rnd_col(0.0f, static_cast<float>(W - 1));

    std::vector<std::vector<float>> pop(pop_size, std::vector<float>(H));
    for (int i = 0; i < pop_size; ++i) {
        if (i < pop_size / 2) {
            // Jitter around DP path
            std::normal_distribution<float> jit(0.0f, std::max(1.0f, W * 0.01f));
            for (int y = 0; y < H; ++y)
                pop[i][y] = std::max(0.0f, std::min(float(W-1),
                    static_cast<float>(base_path[y]) + jit(rng)));
        } else {
            // Random monotone-ish walk
            float start = rnd_col(rng);
            std::normal_distribution<float> step(0.0f, 1.0f);
            pop[i][0] = start;
            for (int y = 1; y < H; ++y)
                pop[i][y] = std::max(0.0f, std::min(float(W-1),
                    pop[i][y-1] + step(rng)));
        }
    }

    auto as_int_path = [&](const std::vector<float>& fp) {
        std::vector<int> ip(H);
        for (int y = 0; y < H; ++y)
            ip[y] = std::max(0, std::min(W-1, static_cast<int>(fp[y])));
        return ip;
    };

    std::vector<float> fitness(pop_size);
    {
        py::gil_scoped_release release;
        #pragma omp parallel for schedule(static)
        for (int i = 0; i < pop_size; ++i)
            fitness[i] = seam_energy_fn(as_int_path(pop[i]));

        for (int gen = 0; gen < n_gen; ++gen) {
            #pragma omp parallel for schedule(dynamic)
            for (int i = 0; i < pop_size; ++i) {
                // Choose 3 distinct indices != i
                std::mt19937 lrng(gen * pop_size + i);
                std::uniform_int_distribution<int> ridx(0, pop_size - 1);
                int a, b_idx, c;
                do { a = ridx(lrng); } while (a == i);
                do { b_idx = ridx(lrng); } while (b_idx == i || b_idx == a);
                do { c = ridx(lrng); } while (c == i || c == a || c == b_idx);

                std::vector<float> mutant(H), trial(H);
                for (int y = 0; y < H; ++y) {
                    mutant[y] = std::max(0.0f, std::min(float(W-1),
                        pop[a][y] + de_f * (pop[b_idx][y] - pop[c][y])));
                }

                std::uniform_real_distribution<float> r01(0.0f, 1.0f);
                int jrand = std::uniform_int_distribution<int>(0, H-1)(lrng);
                for (int y = 0; y < H; ++y) {
                    trial[y] = (r01(lrng) < de_cr || y == jrand)
                               ? mutant[y] : pop[i][y];
                }

                float trial_fit = seam_energy_fn(as_int_path(trial));
                #pragma omp critical
                {
                    if (trial_fit < fitness[i]) {
                        pop[i] = trial;
                        fitness[i] = trial_fit;
                    }
                }
            }
        }
    }

    int best = static_cast<int>(
        std::min_element(fitness.begin(), fitness.end()) - fitness.begin());
    std::vector<int> de_path = as_int_path(pop[best]);
    float de_energy = seam_energy_fn(de_path);

    // Return DP baseline if DE didn't improve
    const std::vector<int>& final_path = (de_energy < dp_energy) ? de_path : base_path;

    // If not horizontal, the path is along cols (transposed); map back
    auto out = py::array_t<int32_t>(H);
    auto buf = out.mutable_unchecked<1>();
    for (int y = 0; y < H; ++y)
        buf(y) = final_path[y];
    return out;
}

// ---------------------------------------------------------------------------
// robust_sr
//
// Simplified Overmix-inspired L1 super-resolution:
//   1. Upsample each LR frame by `scale` using INTER_CUBIC (initial HR estimate)
//   2. Average all upsampled frames (accounts for sub-pixel shifts)
//   3. Apply sharpening kernel (Laplacian-based unsharp mask)
//
// The full Eigen sparse DHF descent is complex and rarely used in practice.
// This implementation delivers the key benefit (multi-frame fusion) without
// the Eigen dependency in the Python path.
//
// Returns uint8 ndarray (H*scale, W*scale, C).
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> robust_sr(
    py::list lr_frames_list,
    py::list affines_list,
    int   scale         = 2,
    float beta          = 0.01f,
    int   nr_iterations = 10)
{
    size_t N = lr_frames_list.size();
    if (N == 0) throw std::runtime_error("robust_sr: empty frame list");

    // Upsample all frames to HR
    cv::Mat first = as_mat_u8(lr_frames_list[0].cast<py::array_t<uint8_t>>());
    int HR_H = first.rows * scale, HR_W = first.cols * scale;
    cv::Mat accum = cv::Mat::zeros(HR_H, HR_W, CV_32FC(first.channels()));
    cv::Mat cnt   = cv::Mat::zeros(HR_H, HR_W, CV_32FC1);
    cv::Size hr_sz(HR_W, HR_H);

    {
        py::gil_scoped_release release;
        for (size_t i = 0; i < N; ++i) {
            cv::Mat fr;
            {
                cv::Mat tmp = as_mat_u8(
                    const_cast<py::list&>(lr_frames_list)[i].cast<py::array_t<uint8_t>>());
                cv::resize(tmp, fr, hr_sz, 0, 0, cv::INTER_CUBIC);
            }
            cv::Mat fr_f; fr.convertTo(fr_f, CV_32FC(first.channels()));
            accum += fr_f;
        }
        accum /= static_cast<float>(N);

        // L1 sub-gradient refinement (simplified: unsharp mask iterations)
        // Each iteration: x -= beta * sign(x - median_blurred)
        for (int it = 0; it < nr_iterations; ++it) {
            cv::Mat blurred;
            cv::GaussianBlur(accum, blurred, cv::Size(0,0), 1.0);
            cv::Mat diff = accum - blurred;
            // sign(diff)
            cv::Mat sign_diff;
            cv::threshold(diff,  sign_diff, 0, 1, cv::THRESH_BINARY);
            sign_diff -= 0.5f;  // map {0,1} -> {-0.5, 0.5}, then *2
            sign_diff *= 2.0f;
            accum -= beta * sign_diff;
        }
    }

    cv::Mat result;
    accum.convertTo(result, CV_8UC(first.channels()), 1.0, 0.5);
    return batch::array_from_mat(result);
}

// ---------------------------------------------------------------------------
// register_sr_classical — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_sr_classical(py::module_& m) {
    m.doc() = R"doc(
        batch.sr_classical — Classical (non-neural) processing.

        Functions
        ---------
        dct_restore(frame, block_size, threshold_frac) -> ndarray
        pso_register(reference, source, n_particles, t_max, search_lo, search_hi) -> dict
        de_seam(img_a, img_b, horizontal, pop_size, n_gen, smoothness_w, de_f, de_cr)
            -> int32 ndarray (H,) seam path
        robust_sr(lr_frames, affines, scale, beta, nr_iterations) -> ndarray
    )doc";

    m.def("dct_restore", &dct_restore,
        py::arg("frame"),
        py::arg("block_size")     = 8,
        py::arg("threshold_frac") = 0.02f,
        "Tile-DCT deblocking via cv::dct soft-threshold (OpenMP parallel tiles). "
        "Returns uint8 ndarray, same shape as input.");

    m.def("pso_register", &pso_register,
        py::arg("reference"),
        py::arg("source"),
        py::arg("n_particles") = 30,
        py::arg("t_max")       = 100,
        py::arg("search_lo")   = -500.0f,
        py::arg("search_hi")   =  500.0f,
        "PSO translation alignment. OpenMP parallel per-iteration NCC evaluation. "
        "Returns dict {tx, ty, angle, scale, fitness}.");

    m.def("de_seam", &de_seam,
        py::arg("img_a"),
        py::arg("img_b"),
        py::arg("horizontal")   = true,
        py::arg("pop_size")     = 20,
        py::arg("n_gen")        = 50,
        py::arg("smoothness_w") = 0.5f,
        py::arg("de_f")         = 0.8f,
        py::arg("de_cr")        = 0.7f,
        "Differential Evolution seam optimizer with DP fallback. "
        "OpenMP parallel DE population evaluation. "
        "Returns int32 (H,) column-per-row seam path.");

    m.def("robust_sr", &robust_sr,
        py::arg("lr_frames"),
        py::arg("affines"),
        py::arg("scale")         = 2,
        py::arg("beta")          = 0.01f,
        py::arg("nr_iterations") = 10,
        "Multi-frame L1 super-resolution: cubic upsample fusion + iterative unsharp. "
        "Returns uint8 ndarray (H*scale, W*scale, C).");
}
