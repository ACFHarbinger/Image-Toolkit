// ---------------------------------------------------------------------------
// batch/src/http/web_requests.cpp
//
// HTTP request sequencing driven by a JSON config (skeleton).
//
// Dependencies (Phase 5 implementation):
//   - cpp-httplib (header-only): HTTP/HTTPS client, FetchContent in CMakeLists
//   - nlohmann/json (header-only): JSON parsing, FetchContent in CMakeLists
//
// Phase 5 of the Rust → C++ migration.
// See moon/roadmaps/rust_to_cpp_migration.md §Phase 5
// ---------------------------------------------------------------------------

#include "batch/web/web_requests.hpp"

#include <pybind11/pybind11.h>

#include <stdexcept>

namespace py = pybind11;

namespace batch::web {

// ---------------------------------------------------------------------------
// Skeleton stub — raises NotImplementedError so the Python dispatch shim
// falls back to the Rust base module.  Replace in Phase 5.
// ---------------------------------------------------------------------------

std::string run_web_requests_sequence(
    const std::string& /*config_json*/,
    std::function<void(const std::string&)> /*status_cb*/)
{
    throw std::runtime_error(
        "batch.http.run_web_requests_sequence: Phase 5 not yet implemented. "
        "Falling back to Rust base module.");
}

py::str run_web_requests_sequence_py(
    const std::string& config_json,
    py::object         callback_obj)
{
    auto cb = [&](const std::string& msg) {
        py::gil_scoped_acquire acquire;
        callback_obj.attr("on_status")(msg);
    };
    py::gil_scoped_release release;
    return py::str(run_web_requests_sequence(config_json, cb));
}

} // namespace batch::web

// ---------------------------------------------------------------------------
// pybind11 registration (called from bindings.cpp)
// ---------------------------------------------------------------------------

void register_web(py::module_& m) {
    m.doc() =
        "HTTP request sequencing (cpp-httplib + nlohmann/json). "
        "Phase 5 skeleton — raises until implementation is complete.";

    m.def("run_web_requests_sequence",
          &batch::web::run_web_requests_sequence_py,
          py::arg("config_json"),
          py::arg("callback_obj"),
          R"doc(
Execute a JSON-configured HTTP request sequence.

Parameters
----------
config_json : str
    JSON string describing base_url, requests, and actions.
    See batch/include/batch/web/web_requests.hpp for the schema.
callback_obj : object
    Object with an on_status(msg: str) method, called for each request.

Returns
-------
str
    JSON string of the full response sequence.
          )doc");
}
