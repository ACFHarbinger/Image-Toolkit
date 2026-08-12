// ---------------------------------------------------------------------------
// logic/src/exact_solvers_bindings.cpp
//
// pybind11 bindings for exact_solvers.hpp, compiled into Image-Toolkit's
// central `base` extension (base.hie.exact_solvers) per the product decision
// in .agent/cache/chat/hie_product_decisions_20260812.md ("follow ASP").
//
// Consumed from Python via middleware/src/hie_middleware/jobs/exact_dp.py,
// which falls back to a pure-Python reference implementation when `base`
// (or this submodule) isn't importable — see that file's module docstring.
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "exact_solvers.hpp"

namespace py = pybind11;
using namespace hybrid_image_editor;

void register_hie_exact_solvers(py::module_& m) {
    py::class_<SeamPixel>(m, "SeamPixel")
        .def(py::init<>())
        .def(py::init([](float energy, bool masked) {
                 return SeamPixel{energy, masked};
             }),
             py::arg("energy"), py::arg("masked") = false)
        .def_readwrite("energy", &SeamPixel::energy)
        .def_readwrite("masked", &SeamPixel::masked);

    py::class_<SeamResult>(m, "SeamResult")
        .def_readonly("seam_x", &SeamResult::seam_x)
        .def_readonly("total_energy", &SeamResult::total_energy)
        .def_readonly("success", &SeamResult::success)
        .def_readonly("error", &SeamResult::error);

    m.def(
        "solve_seam",
        [](const std::vector<SeamPixel>& energy_grid, std::size_t rows, std::size_t cols) {
            // Release the GIL for the duration of the (potentially large) DP
            // pass — this function does not call back into Python.
            py::gil_scoped_release release;
            return solve_seam(energy_grid, rows, cols);
        },
        py::arg("energy_grid"), py::arg("rows"), py::arg("cols"),
        "Dynamic-programming optimal seam routing (see exact_solvers.hpp for the full contract).");

    py::class_<Correspondence>(m, "Correspondence")
        .def(py::init([](float src_x, float src_y, float dst_x, float dst_y) {
                 return Correspondence{src_x, src_y, dst_x, dst_y};
             }),
             py::arg("src_x"), py::arg("src_y"), py::arg("dst_x"), py::arg("dst_y"))
        .def_readwrite("src_x", &Correspondence::src_x)
        .def_readwrite("src_y", &Correspondence::src_y)
        .def_readwrite("dst_x", &Correspondence::dst_x)
        .def_readwrite("dst_y", &Correspondence::dst_y);

    py::class_<MotionModel2DTS>(m, "MotionModel2DTS")
        .def_readonly("tx", &MotionModel2DTS::tx)
        .def_readonly("ty", &MotionModel2DTS::ty)
        .def_readonly("scale", &MotionModel2DTS::scale);

    py::class_<AlignmentResult>(m, "AlignmentResult")
        .def_readonly("model", &AlignmentResult::model)
        .def_readonly("residual", &AlignmentResult::residual)
        .def_readonly("inlier_count", &AlignmentResult::inlier_count)
        .def_readonly("success", &AlignmentResult::success)
        .def_readonly("error", &AlignmentResult::error);

    m.def(
        "solve_alignment_gnc",
        [](const std::vector<Correspondence>& correspondences, std::uint32_t gnc_iterations,
           float inlier_threshold) {
            py::gil_scoped_release release;
            return solve_alignment_gnc(correspondences, gnc_iterations, inlier_threshold);
        },
        py::arg("correspondences"), py::arg("gnc_iterations") = 8, py::arg("inlier_threshold") = 3.0f,
        "GNC-TLS robust 2D translation+scale alignment (see exact_solvers.hpp).");

    py::class_<LayerColorStats>(m, "LayerColorStats")
        .def(py::init([](float mean_l, float mean_a, float mean_b, float std_l, float std_a, float std_b) {
                 return LayerColorStats{mean_l, mean_a, mean_b, std_l, std_a, std_b};
             }),
             py::arg("mean_l"), py::arg("mean_a"), py::arg("mean_b"), py::arg("std_l"), py::arg("std_a"),
             py::arg("std_b"))
        .def_readwrite("mean_l", &LayerColorStats::mean_l)
        .def_readwrite("mean_a", &LayerColorStats::mean_a)
        .def_readwrite("mean_b", &LayerColorStats::mean_b)
        .def_readwrite("std_l", &LayerColorStats::std_l)
        .def_readwrite("std_a", &LayerColorStats::std_a)
        .def_readwrite("std_b", &LayerColorStats::std_b);

    py::class_<ColorHarmonizationResult>(m, "ColorHarmonizationResult")
        .def_readonly("alpha_l", &ColorHarmonizationResult::alpha_l)
        .def_readonly("beta_l", &ColorHarmonizationResult::beta_l)
        .def_readonly("alpha_a", &ColorHarmonizationResult::alpha_a)
        .def_readonly("beta_a", &ColorHarmonizationResult::beta_a)
        .def_readonly("alpha_b", &ColorHarmonizationResult::alpha_b)
        .def_readonly("beta_b", &ColorHarmonizationResult::beta_b)
        .def_readonly("success", &ColorHarmonizationResult::success)
        .def_readonly("error", &ColorHarmonizationResult::error);

    m.def(
        "solve_color_harmonization",
        [](const LayerColorStats& source, const LayerColorStats& target) {
            py::gil_scoped_release release;
            return solve_color_harmonization(source, target);
        },
        py::arg("source"), py::arg("target"),
        "Convex per-channel affine color transfer (see exact_solvers.hpp).");
}
