// ---------------------------------------------------------------------------
// base/src/web/reverse_image_search.cpp — STUB
// The Rust implementation used thirtyfour (Selenium WebDriver / tokio async).
// No equivalent C++ WebDriver client is available; raise at call time.
// ---------------------------------------------------------------------------
#include <pybind11/pybind11.h>
#include <stdexcept>

namespace py = pybind11;

void register_reverse_image_search(py::module_& m) {
    m.def("run_reverse_image_search",
        [](py::args /*args*/, py::kwargs /*kwargs*/) -> std::string {
            throw std::runtime_error(
                "run_reverse_image_search: WebDriver-based reverse image search "
                "is not available in the C++ build. "
                "Use the Python/Rust backend or an external browser automation tool.");
        },
        "STUB: reverse image search requires WebDriver and is not implemented in C++.");
}
