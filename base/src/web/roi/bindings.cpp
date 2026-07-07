// ---------------------------------------------------------------------------
// base/src/web/roi/bindings.cpp — pybind11 API for base.roi
// ---------------------------------------------------------------------------
#include "web/roi.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

namespace base::roi {

void register_roi(py::module_& m) {
    m.doc() = "Reverse-search ROI preprocessing: pixel-space crop + saliency "
              "auto-crop.";

    py::class_<RoiRect>(m, "RoiRect")
        .def(py::init<>())
        .def_readwrite("x", &RoiRect::x)
        .def_readwrite("y", &RoiRect::y)
        .def_readwrite("width", &RoiRect::width)
        .def_readwrite("height", &RoiRect::height)
        .def_property_readonly("is_valid", &RoiRect::is_valid);

    m.def("crop_roi",
        [](const std::string& image_path, int x, int y, int width, int height,
           int jpeg_quality) {
            RoiRect roi{x, y, width, height};
            RoiCropResult r;
            {
                py::gil_scoped_release rel;
                r = crop_roi(image_path, roi, jpeg_quality);
            }
            py::dict out;
            out["ok"] = r.ok;
            out["error"] = r.error;
            out["temp_path"] = r.temp_path;
            out["width"] = r.width;
            out["height"] = r.height;
            out["data"] = py::bytes(reinterpret_cast<const char*>(r.data.data()),
                                    r.data.size());
            return out;
        },
        py::arg("image_path"), py::arg("x"), py::arg("y"), py::arg("width"),
        py::arg("height"), py::arg("jpeg_quality") = 95,
        "Crop image_path to a pixel-space ROI (clamped). Returns "
        "{ok, error, temp_path, width, height, data}.");

    m.def("auto_crop",
        [](const std::string& image_path, double coverage) {
            RoiRect r;
            {
                py::gil_scoped_release rel;
                r = auto_crop(image_path, coverage);
            }
            py::dict out;
            out["ok"] = r.is_valid();
            out["x"] = r.x;
            out["y"] = r.y;
            out["width"] = r.width;
            out["height"] = r.height;
            return out;
        },
        py::arg("image_path"), py::arg("coverage") = 0.9,
        "Spectral-residual saliency auto-crop; returns {ok, x, y, width, height}. "
        "ok=False means no salient subject (use the full image).");
}

}  // namespace base::roi
