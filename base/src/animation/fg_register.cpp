// ---------------------------------------------------------------------------
// batch/src/fg_register.cpp
//
// ARAP foreground registration: SLIC-SGM proxy, ARAP grid regulariser,
// ECC single-pair refinement, LSD collinearity wrapper.
//
// Replaces (non-flow-inference parts):
//   alignment/fg_register.py  :: _arap_regularise (non-scipy bilinear interp)
//   alignment/ecc.py          :: _ecc_refine (per-pair cv::findTransformECC)
//
// Dependencies:
//   Required : OpenCV imgproc, video, Eigen3
//   Optional : OpenCV ximgproc (SLIC) — guarded with HAVE_OPENCV_XIMGPROC
//
// Phase 5 implementation.
// See moon/roadmaps/asp_cpp_migration.md §base::fg_register
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/video/tracking.hpp>

#ifdef HAVE_OPENCV_XIMGPROC
#include <opencv2/ximgproc/slic.hpp>
#endif

#include "base/common.hpp"

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

inline cv::Mat as_mat_f32(py::array_t<float> arr) {
    auto req = arr.request();
    int type = (req.ndim == 3) ? CV_32FC(static_cast<int>(req.shape[2]))
                                : CV_32FC1;
    return cv::Mat(
        static_cast<int>(req.shape[0]),
        static_cast<int>(req.shape[1]),
        type, req.ptr).clone();
}

// ---------------------------------------------------------------------------
// ecc_refine
//
// Single-pair ECC refinement (innermost call from Python _ecc_refine).
// Python's _ecc_refine wraps this with per-frame pyramid and drift clamp.
//
// C++ advantage: cv::findTransformECC has no ndarray→Mat copy overhead vs
// the Python binding.  Also exposes gaussFiltSize=5 which the Python cv2
// binding supports but requires an explicit call.
//
// Args
// ----
// template_frame : uint8 (H, W) grayscale
// source_frame   : uint8 (H, W) grayscale — frame to align to template
// initial_M      : float32 (2, 3) — initial warp matrix (modified in-place in cv::)
// mask           : uint8 (H, W) or None — region to use for ECC
// motion_type    : int — cv::MOTION_TRANSLATION=2, cv::MOTION_EUCLIDEAN=4,
//                        cv::MOTION_AFFINE=0
// max_iters      : int — ECC termination criterion (count)
// eps            : float — ECC termination criterion (eps)
//
// Returns float32 ndarray (2, 3) — refined warp matrix.
// Throws std::runtime_error if cv::findTransformECC fails.
// ---------------------------------------------------------------------------
static py::array_t<float> ecc_refine(
    py::array_t<uint8_t> template_frame,
    py::array_t<uint8_t> source_frame,
    py::array_t<float>   initial_M,
    py::object           mask        = py::none(),
    int                  motion_type = 4,   // cv::MOTION_EUCLIDEAN
    int                  max_iters   = 50,
    double               eps         = 1e-3)
{
    cv::Mat tmpl = as_mat_u8(template_frame);
    cv::Mat src  = as_mat_u8(source_frame);

    // Ensure grayscale
    if (tmpl.channels() > 1) cv::cvtColor(tmpl, tmpl, cv::COLOR_BGR2GRAY);
    if (src.channels()  > 1) cv::cvtColor(src,  src,  cv::COLOR_BGR2GRAY);

    // Build warp matrix (must be float32, CV_32F)
    {
        auto req = initial_M.request();
        if (req.shape[0] != 2 || req.shape[1] != 3)
            throw std::runtime_error("ecc_refine: initial_M must be shape (2,3)");
    }
    cv::Mat M(2, 3, CV_32F);
    {
        auto req = initial_M.request();
        std::memcpy(M.data, req.ptr, 6 * sizeof(float));
    }

    // Optional mask
    cv::Mat cv_mask;
    if (!mask.is_none()) {
        cv_mask = as_mat_u8(mask.cast<py::array_t<uint8_t>>());
        if (cv_mask.channels() > 1)
            cv::cvtColor(cv_mask, cv_mask, cv::COLOR_BGR2GRAY);
    }

    cv::TermCriteria criteria(
        cv::TermCriteria::EPS | cv::TermCriteria::COUNT,
        max_iters, eps);

    {
        py::gil_scoped_release release;
        try {
            if (cv_mask.empty())
                cv::findTransformECC(tmpl, src, M, motion_type, criteria,
                                     cv::noArray(), 5);
            else
                cv::findTransformECC(tmpl, src, M, motion_type, criteria,
                                     cv_mask, 5);
        } catch (const cv::Exception& e) {
            throw std::runtime_error(
                std::string("ecc_refine: cv::findTransformECC failed: ") + e.what());
        }
    }

    return base::array_from_f32(M);
}

// ---------------------------------------------------------------------------
// arap_push_regularise
//
// ARAP grid regulariser — C++ port of Python _arap_regularise.
// Key speedup: per-cell median via std::nth_element (replaces np.median);
// bilinear interp via cv::resize instead of scipy.interpolate.
//
// Args
// ----
// flow      : float32 (H, W, 2) — raw optical flow to regularise
// fg_mask   : uint8  (H, W) — > 0 = foreground character pixels
// cell_size : int — grid cell size (default 32)
// n_iter    : int — number of regularise passes (default 3)
// image     : uint8 (H, W, 3) or None — for LSD collinearity
// image_offset_y, image_offset_x : crop-to-canvas offset
//
// Returns float32 ndarray (H, W, 2) — regularised flow.
// ---------------------------------------------------------------------------
static py::array_t<float> arap_push_regularise(
    py::array_t<float>   flow_arr,
    py::array_t<uint8_t> fg_mask_arr,
    int                  cell_size      = 32,
    int                  n_iter         = 3,
    py::object           image          = py::none(),
    int                  image_offset_y = 0,
    int                  image_offset_x = 0)
{
    // Load inputs
    cv::Mat flow_in = as_mat_f32(flow_arr);   // (H, W, 2)
    cv::Mat fgm     = as_mat_u8(fg_mask_arr); // (H, W)
    if (fgm.channels() > 1) cv::cvtColor(fgm, fgm, cv::COLOR_BGR2GRAY);

    int H = flow_in.rows, W = flow_in.cols;
    // Separate fx / fy channels
    std::vector<cv::Mat> flow_ch(2);
    cv::split(flow_in, flow_ch);
    cv::Mat fx = flow_ch[0].clone();  // (H, W, 1) CV_32F
    cv::Mat fy = flow_ch[1].clone();

    // LSD line detection from optional image
    struct LineSegment { float x1, y1, x2, y2; };
    std::vector<LineSegment> lsd_lines;

    if (!image.is_none()) {
        try {
            cv::Mat img = as_mat_u8(image.cast<py::array_t<uint8_t>>());
            cv::Mat gray;
            if (img.channels() == 1) gray = img;
            else cv::cvtColor(img, gray, cv::COLOR_BGR2GRAY);

            auto lsd = cv::createLineSegmentDetector(0);
            std::vector<cv::Vec4f> lines;
            lsd->detect(gray, lines);

            for (const auto& ln : lines) {
                float dx = ln[2] - ln[0], dy = ln[3] - ln[1];
                float length = std::sqrt(dx*dx + dy*dy);
                if (length >= static_cast<float>(cell_size)) {
                    lsd_lines.push_back({
                        ln[0] + image_offset_x,
                        ln[1] + image_offset_y,
                        ln[2] + image_offset_x,
                        ln[3] + image_offset_y
                    });
                }
            }
        } catch (...) {}
    }

    // Grid dimensions
    int ny = std::max(1, H / cell_size);
    int nx = std::max(1, W / cell_size);

    for (int iter = 0; iter < n_iter; ++iter) {
        cv::Mat cell_tx = cv::Mat::zeros(ny, nx, CV_32F);
        cv::Mat cell_ty = cv::Mat::zeros(ny, nx, CV_32F);
        cv::Mat cell_cnt = cv::Mat::zeros(ny, nx, CV_32F);

        // Per-cell fg median (nth_element in scratch buffers)
        std::vector<float> buf_x, buf_y;
        buf_x.reserve(cell_size * cell_size);
        buf_y.reserve(cell_size * cell_size);

        for (int ci = 0; ci < ny; ++ci) {
            int y0 = ci * cell_size, y1 = std::min(H, (ci + 1) * cell_size);
            for (int cj = 0; cj < nx; ++cj) {
                int x0 = cj * cell_size, x1 = std::min(W, (cj + 1) * cell_size);
                buf_x.clear(); buf_y.clear();
                for (int y = y0; y < y1; ++y) {
                    const uint8_t* fgr = fgm.ptr<uint8_t>(y);
                    const float*   fxr = fx.ptr<float>(y);
                    const float*   fyr = fy.ptr<float>(y);
                    for (int x = x0; x < x1; ++x) {
                        if (fgr[x] > 0) {
                            buf_x.push_back(fxr[x]);
                            buf_y.push_back(fyr[x]);
                        }
                    }
                }
                if (!buf_x.empty()) {
                    int mid = static_cast<int>(buf_x.size()) / 2;
                    std::nth_element(buf_x.begin(), buf_x.begin() + mid, buf_x.end());
                    std::nth_element(buf_y.begin(), buf_y.begin() + mid, buf_y.end());
                    cell_tx.at<float>(ci, cj) = buf_x[mid];
                    cell_ty.at<float>(ci, cj) = buf_y[mid];
                    cell_cnt.at<float>(ci, cj) = static_cast<float>(buf_x.size());
                }
            }
        }

        // LSD collinearity: cells intersected by a long line segment share
        // the mean translation of the group.
        if (!lsd_lines.empty()) {
            for (const auto& ln : lsd_lines) {
                float dx = ln.x2 - ln.x1, dy = ln.y2 - ln.y1;
                float length = std::sqrt(dx*dx + dy*dy);
                int n_pts = std::max(2, static_cast<int>(length / (cell_size / 2.0f)));
                std::vector<std::pair<int,int>> cells_hit;
                for (int k = 0; k < n_pts; ++k) {
                    float t = static_cast<float>(k) / (n_pts - 1);
                    float lx = ln.x1 + t * dx;
                    float ly = ln.y1 + t * dy;
                    int ci = static_cast<int>(ly) / cell_size;
                    int cj = static_cast<int>(lx) / cell_size;
                    int fy_i = static_cast<int>(ly);
                    int fx_i = static_cast<int>(lx);
                    if (ci >= 0 && ci < ny && cj >= 0 && cj < nx
                        && fy_i >= 0 && fy_i < H && fx_i >= 0 && fx_i < W
                        && fgm.at<uint8_t>(fy_i, fx_i) > 0) {
                        cells_hit.emplace_back(ci, cj);
                    }
                }
                // Deduplicate
                std::sort(cells_hit.begin(), cells_hit.end());
                cells_hit.erase(std::unique(cells_hit.begin(), cells_hit.end()), cells_hit.end());
                if (cells_hit.size() > 1) {
                    float sum_tx = 0, sum_ty = 0; int cnt = 0;
                    for (auto& [ci, cj] : cells_hit) {
                        if (cell_cnt.at<float>(ci, cj) > 0) {
                            sum_tx += cell_tx.at<float>(ci, cj);
                            sum_ty += cell_ty.at<float>(ci, cj);
                            ++cnt;
                        }
                    }
                    if (cnt > 0) {
                        float atx = sum_tx / cnt, aty = sum_ty / cnt;
                        for (auto& [ci, cj] : cells_hit) {
                            cell_tx.at<float>(ci, cj) = atx;
                            cell_ty.at<float>(ci, cj) = aty;
                        }
                    }
                }
            }
        }

        // Bilinear interpolate cell grids to pixel resolution via cv::resize
        if (ny > 1 && nx > 1) {
            cv::Mat smooth_tx, smooth_ty;
            cv::resize(cell_tx, smooth_tx, cv::Size(W, H), 0, 0, cv::INTER_LINEAR);
            cv::resize(cell_ty, smooth_ty, cv::Size(W, H), 0, 0, cv::INTER_LINEAR);

            // Blend: fg pixels → ARAP value; bg pixels → unchanged
            for (int y = 0; y < H; ++y) {
                const uint8_t* fgr = fgm.ptr<uint8_t>(y);
                float* fxr = fx.ptr<float>(y);
                float* fyr = fy.ptr<float>(y);
                const float* stx = smooth_tx.ptr<float>(y);
                const float* sty = smooth_ty.ptr<float>(y);
                for (int x = 0; x < W; ++x) {
                    if (fgr[x] > 0) {
                        float blend = fgr[x] / 255.0f;
                        fxr[x] = blend * stx[x] + (1.0f - blend) * fxr[x];
                        fyr[x] = blend * sty[x] + (1.0f - blend) * fyr[x];
                    }
                }
            }
        }
    }

    // Merge fx, fy back into (H, W, 2)
    cv::Mat out;
    cv::merge(std::vector<cv::Mat>{fx, fy}, out);
    return base::array_from_f32(out);
}

// ---------------------------------------------------------------------------
// slic_sgm_proxy
//
// SLIC superpixel centroid tracking as a colour-affinity SGM proxy.
// Requires HAVE_OPENCV_XIMGPROC at compile time (cv::ximgproc::SLICO).
// On missing ximgproc, falls back to a per-pixel direct nearest-centroid match
// using the same LAB colour metric as the Python scikit-image version.
//
// Args
// ----
// crop_a, crop_b : uint8 (H, W, 3) — seam-band crops from each frame
// fg_mask        : uint8 (H, W)    — >0 = foreground
// n_segments     : int — target SLIC superpixel count (default 64)
// compactness    : float — SLIC compactness (default 10.0)
// max_dist_frac  : float — max centroid displacement as fraction of diagonal
// min_match_score: float — min colour affinity × distance score
//
// Returns float32 ndarray (H, W, 2) flow, or raises std::runtime_error if
// too few segments match (caller falls back to RAFT/DIS).
// ---------------------------------------------------------------------------
static py::array_t<float> slic_sgm_proxy(
    py::array_t<uint8_t> crop_a_arr,
    py::array_t<uint8_t> crop_b_arr,
    py::array_t<uint8_t> fg_mask_arr,
    int   n_segments      = 64,
    float compactness     = 10.0f,
    float max_dist_frac   = 0.20f,
    float min_match_score = 0.30f)
{
    cv::Mat ca = as_mat_u8(crop_a_arr);
    cv::Mat cb = as_mat_u8(crop_b_arr);
    cv::Mat fg = as_mat_u8(fg_mask_arr);
    if (fg.channels() > 1) cv::cvtColor(fg, fg, cv::COLOR_BGR2GRAY);

    int H = ca.rows, W = ca.cols;
    float diag = std::sqrt(float(H*H + W*W));
    float max_dist = max_dist_frac * diag;

    // Convert to LAB
    cv::Mat lab_a, lab_b;
    cv::cvtColor(ca, lab_a, cv::COLOR_BGR2Lab);
    cv::cvtColor(cb, lab_b, cv::COLOR_BGR2Lab);

    // SLIC labels — try ximgproc, fallback to k-means-style grid labels
#ifdef HAVE_OPENCV_XIMGPROC
    cv::Mat labels_a(H, W, CV_32S, cv::Scalar(0));
    cv::Mat labels_b(H, W, CV_32S, cv::Scalar(0));
    {
        auto slic_a = cv::ximgproc::createSuperpixelSLIC(lab_a,
            cv::ximgproc::SLICO, n_segments > 0 ? int(std::sqrt(float(H*W)/n_segments)) : 10,
            compactness);
        slic_a->iterate(10); slic_a->getLabels(labels_a);
        auto slic_b = cv::ximgproc::createSuperpixelSLIC(lab_b,
            cv::ximgproc::SLICO, n_segments > 0 ? int(std::sqrt(float(H*W)/n_segments)) : 10,
            compactness);
        slic_b->iterate(10); slic_b->getLabels(labels_b);
    }
#else
    // Fallback: regular grid labels (cheaper than SLIC but correct for flat cel-shading)
    int cell_h = std::max(1, H / (int)std::sqrt(float(n_segments)));
    int cell_w = std::max(1, W / (int)std::sqrt(float(n_segments)));
    cv::Mat labels_a(H, W, CV_32S), labels_b(H, W, CV_32S);
    int nx = std::max(1, W / cell_w);
    for (int y = 0; y < H; ++y)
        for (int x = 0; x < W; ++x) {
            int lbl = (y / cell_h) * nx + (x / cell_w);
            labels_a.at<int>(y, x) = lbl;
            labels_b.at<int>(y, x) = lbl;
        }
#endif

    // Compute per-segment centroid + mean LAB for foreground segments
    struct SegProp { float cy, cx; float lab[3]; };
    auto build_props = [&](const cv::Mat& lbl_mat, const cv::Mat& lab_img)
        -> std::vector<std::pair<int, SegProp>>
    {
        std::map<int, std::vector<int>> seg_ys, seg_xs;
        std::map<int, std::array<double,3>> seg_lab;
        for (int y = 0; y < H; ++y) {
            const int* lr = lbl_mat.ptr<int>(y);
            const uint8_t* fgr = fg.ptr<uint8_t>(y);
            const cv::Vec3b* lr3 = lab_img.ptr<cv::Vec3b>(y);
            for (int x = 0; x < W; ++x) {
                if (fgr[x] > 0) {
                    int l = lr[x];
                    seg_ys[l].push_back(y);
                    seg_xs[l].push_back(x);
                    seg_lab[l][0] += lr3[x][0];
                    seg_lab[l][1] += lr3[x][1];
                    seg_lab[l][2] += lr3[x][2];
                }
            }
        }
        std::vector<std::pair<int, SegProp>> props;
        for (auto& [l, ys] : seg_ys) {
            if (ys.size() < 4) continue;
            SegProp p;
            p.cy = float(std::accumulate(ys.begin(), ys.end(), 0)) / ys.size();
            p.cx = float(std::accumulate(seg_xs[l].begin(), seg_xs[l].end(), 0)) / ys.size();
            double n = ys.size();
            p.lab[0] = float(seg_lab[l][0] / n);
            p.lab[1] = float(seg_lab[l][1] / n);
            p.lab[2] = float(seg_lab[l][2] / n);
            props.emplace_back(l, p);
        }
        return props;
    };

    auto props_a = build_props(labels_a, lab_a);
    auto props_b = build_props(labels_b, lab_b);

    if (props_a.size() < 2 || props_b.size() < 2)
        throw std::runtime_error("slic_sgm_proxy: too few segments");

    // For each segment in A, find best-matching B segment
    std::map<int, std::pair<float,float>> seg_flow;
    for (auto& [la, pa] : props_a) {
        float best_score = -1.0f;
        float best_dx = 0, best_dy = 0;
        for (auto& [lb, pb] : props_b) {
            float ddx = pb.cx - pa.cx, ddy = pb.cy - pa.cy;
            float dist = std::sqrt(ddx*ddx + ddy*ddy);
            if (dist > max_dist) continue;
            float dl0 = pa.lab[0] - pb.lab[0];
            float dl1 = pa.lab[1] - pb.lab[1];
            float dl2 = pa.lab[2] - pb.lab[2];
            float lab_dist = std::sqrt(dl0*dl0 + dl1*dl1 + dl2*dl2);
            float colour_aff = std::max(0.0f, 1.0f - lab_dist / 128.0f);
            float dist_score = 1.0f - dist / std::max(max_dist, 1.0f);
            float score = colour_aff * dist_score;
            if (score > best_score) {
                best_score = score;
                best_dx = ddx; best_dy = ddy;
            }
        }
        if (best_score >= min_match_score)
            seg_flow[la] = {best_dx, best_dy};
    }

    // Build per-pixel flow from segment assignments
    cv::Mat out = cv::Mat::zeros(H, W, CV_32FC2);
    for (int y = 0; y < H; ++y) {
        const int* lr = labels_a.ptr<int>(y);
        const uint8_t* fgr = fg.ptr<uint8_t>(y);
        cv::Vec2f* or_ = out.ptr<cv::Vec2f>(y);
        for (int x = 0; x < W; ++x) {
            if (fgr[x] > 0) {
                auto it = seg_flow.find(lr[x]);
                if (it != seg_flow.end()) {
                    or_[x][0] = it->second.first;
                    or_[x][1] = it->second.second;
                }
            }
        }
    }
    return base::array_from_f32(out);
}

// ---------------------------------------------------------------------------
// lsd_collinearity
//
// Detect line segments in seam_band_crop via cv::createLineSegmentDetector.
// Returns a list of dicts with keys "x1","y1","x2","y2","length" (canvas coords).
// ---------------------------------------------------------------------------
static py::list lsd_collinearity(
    py::array_t<uint8_t> seam_band_arr,
    int                  offset_y    = 0,
    int                  offset_x    = 0,
    int                  min_length  = 32)
{
    cv::Mat band = as_mat_u8(seam_band_arr);
    cv::Mat gray;
    if (band.channels() == 1) gray = band.clone();
    else cv::cvtColor(band, gray, cv::COLOR_BGR2GRAY);

    auto lsd = cv::createLineSegmentDetector(0);
    std::vector<cv::Vec4f> lines;
    lsd->detect(gray, lines);

    py::list result;
    for (const auto& ln : lines) {
        float dx = ln[2] - ln[0], dy = ln[3] - ln[1];
        float length = std::sqrt(dx*dx + dy*dy);
        if (length < static_cast<float>(min_length)) continue;
        py::dict d;
        d["x1"]     = ln[0] + static_cast<float>(offset_x);
        d["y1"]     = ln[1] + static_cast<float>(offset_y);
        d["x2"]     = ln[2] + static_cast<float>(offset_x);
        d["y2"]     = ln[3] + static_cast<float>(offset_y);
        d["length"] = length;
        result.append(d);
    }
    return result;
}

// ---------------------------------------------------------------------------
// register_fg_register — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_fg_register(py::module_& m) {
    m.doc() = R"doc(
        batch.fg_register — ARAP foreground registration (non-flow parts).

        The flow inference (SEA-RAFT, DISOpticalFlow) stays in Python.
        C++ accelerates SLIC-SGM proxy, LSD collinearity, ARAP grid regulariser,
        and ECC single-pair affine refinement.

        Functions
        ---------
        ecc_refine(template, source, initial_M, mask, motion_type, max_iters, eps)
            -> float32 (2,3) refined warp matrix
        arap_push_regularise(flow, fg_mask, cell_size, n_iter, image,
                              image_offset_y, image_offset_x)
            -> float32 (H,W,2) regularised flow
        slic_sgm_proxy(crop_a, crop_b, fg_mask, n_segments, compactness,
                       max_dist_frac, min_match_score)
            -> float32 (H,W,2) flow
        lsd_collinearity(seam_band, offset_y, offset_x, min_length)
            -> list[dict{x1,y1,x2,y2,length}]
    )doc";

    m.def("ecc_refine", &ecc_refine,
        py::arg("template_frame"),
        py::arg("source_frame"),
        py::arg("initial_M"),
        py::arg("mask")        = py::none(),
        py::arg("motion_type") = 4,
        py::arg("max_iters")   = 50,
        py::arg("eps")         = 1e-3,
        "ECC single-pair refinement via cv::findTransformECC. "
        "Returns float32 (2,3) refined warp matrix.");

    m.def("arap_push_regularise", &arap_push_regularise,
        py::arg("flow"),
        py::arg("fg_mask"),
        py::arg("cell_size")      = 32,
        py::arg("n_iter")         = 3,
        py::arg("image")          = py::none(),
        py::arg("image_offset_y") = 0,
        py::arg("image_offset_x") = 0,
        "ARAP grid regulariser via per-cell nth_element median + cv::resize bilinear interp. "
        "Returns float32 (H,W,2) regularised flow.");

    m.def("slic_sgm_proxy", &slic_sgm_proxy,
        py::arg("crop_a"),
        py::arg("crop_b"),
        py::arg("fg_mask"),
        py::arg("n_segments")      = 64,
        py::arg("compactness")     = 10.0f,
        py::arg("max_dist_frac")   = 0.20f,
        py::arg("min_match_score") = 0.30f,
        "SLIC superpixel centroid tracking as colour-affinity SGM proxy. "
        "Raises RuntimeError if too few segments match (caller falls back to RAFT).");

    m.def("lsd_collinearity", &lsd_collinearity,
        py::arg("seam_band"),
        py::arg("offset_y")   = 0,
        py::arg("offset_x")   = 0,
        py::arg("min_length") = 32,
        "Detect LSD line segments in seam-band crop. "
        "Returns list[dict{x1,y1,x2,y2,length}] in canvas coordinates.");
}
