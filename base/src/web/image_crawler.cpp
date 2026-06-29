// ---------------------------------------------------------------------------
// base/src/web/image_crawler.cpp — STUB
// The Rust implementation used thirtyfour (Selenium WebDriver / tokio async).
// No equivalent C++ WebDriver client is available; raise at call time.
// ---------------------------------------------------------------------------
#include <pybind11/pybind11.h>

namespace py = pybind11;

void register_image_crawler(py::module_& m) {
    m.def("run_image_crawler",
        [](const std::string& /*config_json*/, py::object /*callback_obj*/) -> int {
            throw py::runtime_error(
                "run_image_crawler: WebDriver-based image crawler "
                "is not available in the C++ build. "
                "Use the Python/Rust backend or an external browser automation tool.");
        },
        py::arg("config_json"), py::arg("callback_obj"),
        "STUB: browser image crawler requires WebDriver and is not implemented in C++.");
}
