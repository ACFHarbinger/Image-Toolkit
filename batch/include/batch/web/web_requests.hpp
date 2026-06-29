#pragma once
// ---------------------------------------------------------------------------
// batch/include/batch/web/web_requests.hpp
//
// HTTP request sequencing driven by a JSON config.
//
// C++ replacement for Rust `base::run_web_requests_sequence`.
// Uses cpp-httplib (header-only) and nlohmann/json.
//
// Phase 5 of the Rust → C++ migration.
// See moon/roadmaps/rust_to_cpp_migration.md §Phase 5
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>

#include <functional>
#include <string>

namespace py = pybind11;

namespace batch::web {

/// Execute a JSON-configured HTTP request sequence.
///
/// config_json schema:
/// {
///   "base_url": "https://example.com",
///   "requests": [
///     {"method": "GET", "path": "/api/v1/resource", "headers": {}, "body": ""},
///     ...
///   ],
///   "actions": [
///     {"type": "save", "key": "token", "from": "response.body.json.access_token"},
///     ...
///   ]
/// }
///
/// status_cb is called with a status message string on each request.
/// Returns a JSON string of the full response sequence.
std::string run_web_requests_sequence(
    const std::string&                       config_json,
    std::function<void(const std::string&)>  status_cb);

/// pybind11-facing wrapper: status_cb is a Python object with on_status(str) method.
/// GIL is released during HTTP I/O and reacquired before each callback invocation.
py::str run_web_requests_sequence_py(
    const std::string& config_json,
    py::object         callback_obj);

} // namespace batch::web
