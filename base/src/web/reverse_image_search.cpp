// ---------------------------------------------------------------------------
// base/src/web/reverse_image_search.cpp — STUB
// The Rust implementation used thirtyfour (Selenium WebDriver / tokio async).
// No equivalent C++ WebDriver client is available; raise at call time.
// ---------------------------------------------------------------------------
#include <pybind11/pybind11.h>

namespace py = pybind11;

void register_reverse_image_search(py::module_& m) {
    m.def("run_reverse_image_search",
        [](const std::string& /*config_json*/, py::object /*callback_obj*/) -> std::string {
            throw py::runtime_error(
                "run_reverse_image_search: WebDriver-based reverse image search "
                "is not available in the C++ build. "
                "Use the Python/Rust backend or an external browser automation tool.");
        },
        py::arg("config_json"), py::arg("callback_obj"),
        "STUB: reverse image search requires WebDriver and is not implemented in C++.");
}
