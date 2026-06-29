// ---------------------------------------------------------------------------
// base/src/web/image_crawler.cpp — STUB
// The Rust implementation used thirtyfour (Selenium WebDriver / tokio async).
// No equivalent C++ WebDriver client is available; raise at call time.
// ---------------------------------------------------------------------------
#include <pybind11/pybind11.h>
#include <stdexcept>

namespace py = pybind11;

void register_image_crawler(py::module_& m) {
    m.def("run_image_crawler",
        [](py::args /*args*/, py::kwargs /*kwargs*/) -> int {
            throw std::runtime_error(
                "run_image_crawler: WebDriver-based image crawler "
                "is not available in the C++ build. "
                "Use the Python/Rust backend or an external browser automation tool.");
        },
        "STUB: browser image crawler requires WebDriver and is not implemented in C++.");
}
