// ---------------------------------------------------------------------------
// batch/src/web/web_requests.cpp
//
// HTTP request sequencing driven by a JSON config.
//
// Dependencies:
//   - cpp-httplib (header-only, FetchContent): HTTP/HTTPS client
//   - nlohmann/json (header-only, FetchContent): JSON parsing
//
// Phase 5 of the Rust → C++ migration.
// See moon/roadmaps/rust_to_cpp_migration.md §Phase 5
// ---------------------------------------------------------------------------

#ifdef _WIN32
#  define WIN32_LEAN_AND_MEAN
#endif

// Enable HTTPS if OpenSSL is available; falls back to HTTP-only if not.
#ifdef CPPHTTPLIB_OPENSSL_SUPPORT
// defined externally via cmake if OpenSSL found
#endif

#include "base/web/web_requests.hpp"

#include <httplib.h>
#include <nlohmann/json.hpp>

#include <pybind11/pybind11.h>

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace py = pybind11;
using json   = nlohmann::json;
namespace fs = std::filesystem;

namespace base::web {

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

static std::map<std::string, std::string> parse_post_data(const std::string& param) {
    std::map<std::string, std::string> data;
    if (param.empty()) return data;
    std::istringstream ss(param);
    std::string token;
    while (std::getline(ss, token, ',')) {
        auto colon = token.find(':');
        if (colon == std::string::npos) continue;
        std::string key = token.substr(0, colon);
        std::string val = token.substr(colon + 1);
        // trim leading/trailing whitespace
        auto trim = [](std::string& s) {
            s.erase(s.begin(), std::find_if(s.begin(), s.end(), [](unsigned char c){ return !std::isspace(c); }));
            s.erase(std::find_if(s.rbegin(), s.rend(), [](unsigned char c){ return !std::isspace(c); }).base(), s.end());
        };
        trim(key); trim(val);
        data[key] = val;
    }
    return data;
}

// Parse "scheme://host[:port]/path" into {scheme, host, port, path}.
struct ParsedUrl {
    std::string scheme;
    std::string host;
    int         port{-1};
    std::string base_path;
};

static ParsedUrl parse_base_url(const std::string& base_url) {
    ParsedUrl out;
    std::string url = base_url;
    // scheme
    auto scheme_end = url.find("://");
    if (scheme_end != std::string::npos) {
        out.scheme = url.substr(0, scheme_end);
        url = url.substr(scheme_end + 3);
    } else {
        out.scheme = "http";
    }
    // host[:port]/path
    auto slash = url.find('/');
    std::string host_port = (slash != std::string::npos) ? url.substr(0, slash) : url;
    out.base_path = (slash != std::string::npos) ? url.substr(slash) : "";
    auto colon = host_port.find(':');
    if (colon != std::string::npos) {
        out.host = host_port.substr(0, colon);
        try { out.port = std::stoi(host_port.substr(colon + 1)); } catch (...) {}
    } else {
        out.host = host_port;
        out.port = (out.scheme == "https") ? 443 : 80;
    }
    return out;
}

// ---------------------------------------------------------------------------
// run_web_requests_sequence_py
//
// GIL management:
//   - Released for every HTTP I/O call
//   - Re-acquired to call Python callbacks and to read _is_running
// ---------------------------------------------------------------------------

py::str run_web_requests_sequence_py(
    const std::string& config_json,
    py::object         callback_obj)
{
    // Parse config — must hold GIL (we still have it here)
    json config;
    try { config = json::parse(config_json); }
    catch (const json::exception& e) {
        throw py::value_error(std::string("batch.web: invalid JSON config: ") + e.what());
    }

    std::string base_url   = config.value("base_url", "");
    auto        requests   = config.value("requests", json::array());
    auto        actions    = config.value("actions",  json::array());

    ParsedUrl parsed = parse_base_url(base_url);

    auto emit_status = [&](const std::string& msg) {
        py::gil_scoped_acquire acq;
        callback_obj.attr("on_status_emitted")(msg);
    };
    auto emit_error = [&](const std::string& msg) {
        py::gil_scoped_acquire acq;
        callback_obj.attr("on_error_emitted")(msg);
    };
    auto is_running = [&]() -> bool {
        py::gil_scoped_acquire acq;
        try { return callback_obj.attr("_is_running").cast<bool>(); }
        catch (...) { return true; }
    };

    emit_status("Starting request sequence for " + base_url);

    // Build HTTP client (GIL not needed for construction)
    std::unique_ptr<httplib::Client> client;
    {
        py::gil_scoped_release rel;
        if (parsed.scheme == "https") {
            client = std::make_unique<httplib::Client>(
                parsed.host, parsed.port > 0 ? parsed.port : 443);
        } else {
            client = std::make_unique<httplib::Client>(
                parsed.host, parsed.port > 0 ? parsed.port : 80);
        }
        client->set_connection_timeout(15, 0);
        client->set_read_timeout(15, 0);
    }

    int req_count = static_cast<int>(requests.size());

    for (int i = 0; i < req_count; ++i) {
        if (!is_running()) {
            emit_status("Request sequence cancelled.");
            return py::str("Cancelled.");
        }

        const auto& req   = requests[i];
        std::string rtype = req.value("type",  "GET");
        std::string param = req.value("param", "");

        emit_status("--- Request " + std::to_string(i + 1) + "/" +
                    std::to_string(req_count) + ": [" + rtype + "] ---");

        // Build request path
        std::string path = parsed.base_path.empty() ? "/" : parsed.base_path;
        if (rtype == "GET" && !param.empty()) {
            if (path.back() != '/') path += '/';
            if (!param.empty() && param.front() == '/') param = param.substr(1);
            path += param;
        }

        httplib::Result res;
        {
            py::gil_scoped_release rel;
            if (rtype == "GET") {
                emit_status("Executing GET: " + parsed.scheme + "://" + parsed.host + path);
                res = client->Get(path.c_str());
            } else if (rtype == "POST") {
                auto post_data = parse_post_data(param);
                httplib::Params params;
                for (const auto& [k, v] : post_data) params.emplace(k, v);
                emit_status("Executing POST: " + parsed.scheme + "://" + parsed.host + path);
                res = client->Post(path.c_str(), params);
            } else {
                emit_error("Unsupported request type: " + rtype);
                continue;
            }
        }

        if (!res) {
            emit_error("Request failed: " + httplib::to_string(res.error()));
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
            continue;
        }

        emit_status("Request complete. Status: " + std::to_string(res->status));

        if (res->status < 200 || res->status >= 300) {
            emit_error("Request failed: HTTP " + std::to_string(res->status));
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
            continue;
        }

        // Run actions
        const std::string& body = res->body;
        for (const auto& action : actions) {
            std::string atype = action.value("type",  "");
            std::string aparam = action.value("param", "");

            if (atype == "Print Response URL") {
                emit_status("  > Action: Response URL: " +
                            parsed.scheme + "://" + parsed.host + path);
            } else if (atype == "Print Response Status Code") {
                emit_status("  > Action: Status Code: " + std::to_string(res->status));
            } else if (atype == "Print Response Headers") {
                std::string hdr_str;
                for (const auto& [k, v] : res->headers)
                    hdr_str += "    " + k + ": " + v + "\n";
                emit_status("  > Action: Response Headers:\n " + hdr_str);
            } else if (atype == "Print Response Content (Text)") {
                emit_status("  > Action: Response Content:\n " + body);
            } else if (atype == "Save Response Content (Binary)") {
                if (aparam.empty()) {
                    emit_error("  > Action: Save failed. No file path provided in parameter.");
                    continue;
                }
                try {
                    fs::path fpath(aparam);
                    if (fs::is_directory(fpath)) {
                        // derive filename from URL path
                        std::string fname = path;
                        auto last_slash = fname.rfind('/');
                        if (last_slash != std::string::npos) fname = fname.substr(last_slash + 1);
                        if (fname.empty()) fname = "response.dat";
                        fpath /= fname;
                    }
                    if (fpath.has_parent_path())
                        fs::create_directories(fpath.parent_path());
                    std::ofstream out(fpath, std::ios::binary);
                    out.write(body.data(), static_cast<std::streamsize>(body.size()));
                    emit_status("  > Action: Response content saved to " + fpath.string());
                } catch (const std::exception& e) {
                    emit_error(std::string("  > Action: Save failed: ") + e.what());
                }
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }

    emit_status("--- All requests finished. ---");
    return py::str("All requests finished.");
}

} // namespace base::web

// ---------------------------------------------------------------------------
// pybind11 registration (called from bindings.cpp)
// ---------------------------------------------------------------------------

void register_web(py::module_& m) {
    m.doc() =
        "HTTP request sequencing (cpp-httplib + nlohmann/json). "
        "Phase 5 — replaces Rust run_web_requests_sequence.";

    m.def("run_web_requests_sequence",
          &base::web::run_web_requests_sequence_py,
          py::arg("config_json"),
          py::arg("callback_obj"),
          R"doc(
Execute a JSON-configured HTTP request sequence.

Parameters
----------
config_json : str
    JSON string with keys: base_url (str), requests (list), actions (list).
    Each request: {"type": "GET"|"POST", "param": str}
    Each action:  {"type": str, "param": str}
    Action types: "Print Response URL", "Print Response Status Code",
                  "Print Response Headers", "Print Response Content (Text)",
                  "Save Response Content (Binary)"
callback_obj : object
    Object with on_status_emitted(msg), on_error_emitted(msg) methods
    and a bool attribute _is_running (False → cancels the sequence).

Returns
-------
str
    "All requests finished." or "Cancelled."
          )doc");
}
