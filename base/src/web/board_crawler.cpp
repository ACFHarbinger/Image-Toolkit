// ---------------------------------------------------------------------------
// base/src/web/board_crawler.cpp
// Board-crawler orchestrator + pybind11 registration.
// Individual crawler classes live in include/web/crawlers/.
// ---------------------------------------------------------------------------
#include "web/crawlers/danbooru.hpp"
#include "web/crawlers/gelbooru.hpp"
#include "web/crawlers/sankaku.hpp"

#include <pybind11/pybind11.h>

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <string>
#include <thread>

namespace py = pybind11;
namespace fs = std::filesystem;

namespace base::web::board {

static void emit_status(py::object& cb, const std::string& msg) {
    py::gil_scoped_acquire acq;
    try { cb.attr("on_status_emitted")(msg); } catch (...) {}
}
static void emit_error(py::object& cb, const std::string& msg) {
    py::gil_scoped_acquire acq;
    try { cb.attr("on_error_emitted")(msg); } catch (...) {}
}
static bool is_running(py::object& cb) {
    py::gil_scoped_acquire acq;
    try { return cb.attr("_is_running").cast<bool>(); }
    catch (...) { return false; }
}

static int run_crawler(
    Crawler& crawler,
    const json& cfg,
    py::object callback_obj)
{
    int max_pages  = cfg.value("max_pages",  5);
    std::string dl = cfg.value("download_dir", "downloads");
    int request_count = 0;
    int total_dl = 0;

    {
        py::gil_scoped_release rel;
        fs::create_directories(dl);
    }

    emit_status(callback_obj,
        "Starting " + crawler.name() + " crawl on: " + crawler.base_url());

    httplib::Client cli(crawler.base_url());
    cli.set_default_headers({
        {"User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/91.0.4472.124 Safari/537.36"}
    });

    for (int page = 1; page <= max_pages; ++page) {
        if (!is_running(callback_obj)) {
            emit_status(callback_obj, "Crawl cancelled.");
            break;
        }

        emit_status(callback_obj, "Fetching page " + std::to_string(page) + "...");

        json posts;
        {
            py::gil_scoped_release rel;
            posts = crawler.fetch_posts(cli, page);
        }

        if (!posts.is_array() || posts.empty()) {
            emit_status(callback_obj, "No posts found or end of results.");
            break;
        }

        for (const auto& post : posts) {
            auto file_url_opt = crawler.extract_file_url(post);
            if (!file_url_opt) continue;
            const std::string& file_url = *file_url_opt;

            std::string ext = fs::path(file_url).extension().string();
            if (ext.empty()) ext = ".jpg";
            std::string filename = crawler.extract_id(post) + "_" +
                                   crawler.extract_md5(post) + ext;
            fs::path save_path = fs::path(dl) / filename;

            if (fs::exists(save_path)) {
                emit_status(callback_obj, "Skipping existing: " + filename);
                continue;
            }

            emit_status(callback_obj, "Downloading: " + filename);

            if (++request_count % 5 == 0) {
                emit_status(callback_obj, "Rate limiting: waiting 1s...");
                std::this_thread::sleep_for(std::chrono::seconds(1));
            }

            bool ok;
            {
                py::gil_scoped_release rel;
                httplib::Client dl_cli(file_url.substr(0, file_url.find('/', 8)));
                std::string path_part = file_url.substr(file_url.find('/', 8));
                auto res = dl_cli.Get(path_part.c_str());
                ok = (res && res->status == 200);
                if (ok) {
                    std::ofstream f(save_path, std::ios::binary);
                    f.write(res->body.data(), static_cast<std::streamsize>(res->body.size()));
                }
                if (ok) {
                    std::ofstream mf(fs::path(save_path).replace_extension(".json"));
                    mf << post.dump(2);
                }
            }

            if (ok) {
                ++total_dl;
                py::gil_scoped_acquire acq;
                try { callback_obj.attr("on_image_saved")(save_path.string()); }
                catch (...) {}
                std::this_thread::sleep_for(std::chrono::milliseconds(500));
            } else {
                emit_error(callback_obj, "Download failed: " + file_url);
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }

    emit_status(callback_obj,
        "Crawl complete. Downloaded " + std::to_string(total_dl) + " images.");
    return total_dl;
}

} // namespace base::web::board

// ---------------------------------------------------------------------------
// pybind11 registration
// ---------------------------------------------------------------------------

void register_board_crawler(pybind11::module_& m) {
    using json = nlohmann::json;

    m.def("run_board_crawler",
        [](const std::string& crawler_name,
           py::object config_json_obj,
           py::object callback_obj) -> int {
            std::string config_json;
            if (py::isinstance<py::str>(config_json_obj)) {
                config_json = config_json_obj.cast<std::string>();
            } else {
                py::object json_module = py::module_::import("json");
                config_json = json_module.attr("dumps")(config_json_obj).cast<std::string>();
            }

            auto cfg = json::parse(config_json, nullptr, false);
            if (cfg.is_discarded())
                throw py::value_error("run_board_crawler: invalid JSON config");

            std::string name_lc = crawler_name;
            std::transform(name_lc.begin(), name_lc.end(), name_lc.begin(), ::tolower);

            py::gil_scoped_release rel;

            if (name_lc == "danbooru") {
                base::web::board::Danbooru c(cfg);
                py::gil_scoped_acquire acq;
                return base::web::board::run_crawler(c, cfg, callback_obj);
            } else if (name_lc == "gelbooru") {
                base::web::board::Gelbooru c(cfg);
                py::gil_scoped_acquire acq;
                return base::web::board::run_crawler(c, cfg, callback_obj);
            } else if (name_lc == "sankaku" || name_lc == "sankakucrawler") {
                base::web::board::Sankaku c(cfg);
                py::gil_scoped_acquire acq;
                return base::web::board::run_crawler(c, cfg, callback_obj);
            }
            throw py::value_error("run_board_crawler: unknown crawler '" + crawler_name + "'");
        },
        py::arg("crawler_name"), py::arg("config_json"), py::arg("callback_obj"),
        R"doc(
Run an image-board crawler (Danbooru / Gelbooru / Sankaku).

Parameters
----------
crawler_name : str   "danbooru", "gelbooru", or "sankaku"
config_json  : str   JSON config with keys: url, resource, tags, limit,
                     max_pages, download_dir, login_config, extra_params
callback_obj : obj   Must have on_status_emitted(msg), on_error_emitted(msg),
                     on_image_saved(path), _is_running attributes.
Returns
-------
int   Number of images downloaded.
        )doc");
}
