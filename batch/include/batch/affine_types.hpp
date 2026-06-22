#pragma once

// ---------------------------------------------------------------------------
// batch/affine_types.hpp
//
// Plain-data structs shared across batch submodules.
// All structs are passable via pybind11 dicts for Python interop.
// ---------------------------------------------------------------------------

#include <string>
#include <vector>
#include <opencv2/core.hpp>

namespace batch {

// ---------------------------------------------------------------------------
// AffineParams — represents a 2D affine transform for one frame
// ---------------------------------------------------------------------------
struct AffineParams {
    float tx        = 0.0f;  ///< Translation in x (pixels)
    float ty        = 0.0f;  ///< Translation in y (pixels)
    float scale     = 1.0f;  ///< Uniform scale factor
    float rotation  = 0.0f;  ///< Rotation angle (radians, CCW positive)
    int   frame_idx = -1;    ///< Frame index in the sequence (0-based)

    /// Build a 2×3 affine matrix [cos(r)*s, -sin(r)*s, tx;
    ///                             sin(r)*s,  cos(r)*s, ty]
    cv::Mat to_mat2x3() const {
        cv::Mat M(2, 3, CV_64F);
        double c = std::cos(static_cast<double>(rotation)) * scale;
        double s = std::sin(static_cast<double>(rotation)) * scale;
        M.at<double>(0, 0) = c;  M.at<double>(0, 1) = -s; M.at<double>(0, 2) = tx;
        M.at<double>(1, 0) = s;  M.at<double>(1, 1) =  c; M.at<double>(1, 2) = ty;
        return M;
    }
};

// ---------------------------------------------------------------------------
// Edge — a directed match between two frames with observed displacement
// ---------------------------------------------------------------------------
struct Edge {
    int         src    = 0;         ///< Source frame index
    int         dst    = 0;         ///< Destination frame index
    float       dx     = 0.0f;      ///< Observed x displacement (pixels)
    float       dy     = 0.0f;      ///< Observed y displacement (pixels)
    float       weight = 0.0f;      ///< Match confidence [0, 1]
    std::string type   = "adjacent";///< "adjacent" | "skip" | "panorama"
};

// ---------------------------------------------------------------------------
// ZonePair — a pair of adjacent zone crops for seam computation
// ---------------------------------------------------------------------------
struct ZonePair {
    cv::Mat fa;    ///< Zone crop from frame A (uint8, BGR)
    cv::Mat fb;    ///< Zone crop from frame B (uint8, BGR)
    cv::Mat cost;  ///< Pre-computed semantic cost map (float32, H×W) — may be empty
};

// ---------------------------------------------------------------------------
// pybind11 dict <-> struct converters
// ---------------------------------------------------------------------------

/// Convert a Python dict → AffineParams.
/// Expected keys: "tx", "ty", optionally "scale", "rotation", "frame_idx".
inline AffineParams affine_from_dict(pybind11::dict d) {
    AffineParams a;
    if (d.contains("tx"))        a.tx        = d["tx"].cast<float>();
    if (d.contains("ty"))        a.ty        = d["ty"].cast<float>();
    if (d.contains("scale"))     a.scale     = d["scale"].cast<float>();
    if (d.contains("rotation"))  a.rotation  = d["rotation"].cast<float>();
    if (d.contains("frame_idx")) a.frame_idx = d["frame_idx"].cast<int>();
    return a;
}

/// Convert AffineParams → Python dict.
inline pybind11::dict affine_to_dict(const AffineParams& a) {
    pybind11::dict d;
    d["tx"]        = a.tx;
    d["ty"]        = a.ty;
    d["scale"]     = a.scale;
    d["rotation"]  = a.rotation;
    d["frame_idx"] = a.frame_idx;
    return d;
}

/// Convert a Python dict → Edge.
/// Expected keys: "i" (or "src"), "j" (or "dst"), "dx", "dy", "weight",
/// optionally "type".
inline Edge edge_from_dict(pybind11::dict d) {
    Edge e;
    // Accept both ("i","j") and ("src","dst") key conventions
    if (d.contains("i"))   e.src = d["i"].cast<int>();
    if (d.contains("src")) e.src = d["src"].cast<int>();
    if (d.contains("j"))   e.dst = d["j"].cast<int>();
    if (d.contains("dst")) e.dst = d["dst"].cast<int>();
    if (d.contains("dx"))     e.dx     = d["dx"].cast<float>();
    if (d.contains("dy"))     e.dy     = d["dy"].cast<float>();
    if (d.contains("weight")) e.weight = d["weight"].cast<float>();
    if (d.contains("type"))   e.type   = d["type"].cast<std::string>();
    return e;
}

/// Convert Edge → Python dict.
inline pybind11::dict edge_to_dict(const Edge& e) {
    pybind11::dict d;
    d["i"]      = e.src;
    d["j"]      = e.dst;
    d["src"]    = e.src;
    d["dst"]    = e.dst;
    d["dx"]     = e.dx;
    d["dy"]     = e.dy;
    d["weight"] = e.weight;
    d["type"]   = e.type;
    return d;
}

/// Convert std::vector<Edge> → Python list of dicts.
inline pybind11::list edges_to_list(const std::vector<Edge>& edges) {
    pybind11::list out;
    for (const auto& e : edges)
        out.append(edge_to_dict(e));
    return out;
}

/// Convert std::vector<AffineParams> → Python list of dicts.
inline pybind11::list affines_to_list(const std::vector<AffineParams>& affines) {
    pybind11::list out;
    for (const auto& a : affines)
        out.append(affine_to_dict(a));
    return out;
}

} // namespace batch
