// ---------------------------------------------------------------------------
// base/src/web/board_crawler.cpp
// Image board crawlers: Danbooru, Gelbooru, Sankaku — Phase 9.
// Uses cpp-httplib (JSON REST APIs, no WebDriver required).
// ---------------------------------------------------------------------------
#include <httplib.h>
#include <nlohmann/json.hpp>
#include <pybind11/pybind11.h>

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <memory>
#include <optional>
#include <string>
#include <thread>
#include <vector>

namespace py = pybind11;
using json   = nlohmann::json;
namespace fs = std::filesystem;

namespace base::web::board {

// ---------------------------------------------------------------------------
// Abstract Crawler interface
// ---------------------------------------------------------------------------

struct Crawler {
    virtual ~Crawler() = default;
    virtual std::string name() const = 0;
    virtual std::string base_url() const = 0;
    // Fetch page of posts; returns JSON array of post objects
    virtual json fetch_posts(httplib::Client& cli, int page) const = 0;
    virtual std::optional<std::string> extract_file_url(const json& post) const = 0;

    virtual std::string extract_id(const json& post) const {
        if (post.contains("id")) {
            const auto& v = post["id"];
            if (v.is_number()) return std::to_string(v.get<int64_t>());
            if (v.is_string()) return v.get<std::string>();
        }
        return "unknown";
    }
    virtual std::string extract_md5(const json& post) const {
        if (post.contains("md5") && post["md5"].is_string())
            return post["md5"].get<std::string>();
        return "none";
    }
};

// ---------------------------------------------------------------------------
// Danbooru
// ---------------------------------------------------------------------------

struct Danbooru : Crawler {
    std::string base_url_, resource_, tags_;
    int limit_;
    std::string username_, api_key_;
    std::vector<std::pair<std::string,std::string>> extra_params_;

    Danbooru(const json& cfg) {
        base_url_ = cfg.value("url", "https://danbooru.donmai.us");
        resource_ = cfg.value("resource", "posts");
        tags_     = cfg.value("tags", "");
        limit_    = cfg.value("limit", 20);
        if (cfg.contains("login_config")) {
            const auto& lc = cfg["login_config"];
            username_ = lc.value("username", "");
            api_key_  = lc.value("password", "");
        }
        if (cfg.contains("extra_params") && cfg["extra_params"].is_object())
            for (auto& [k,v] : cfg["extra_params"].items())
                extra_params_.emplace_back(k, v.is_string() ? v.get<std::string>() : "");
    }

    std::string name() const override { return "Danbooru"; }
    std::string base_url() const override { return base_url_; }

    json fetch_posts(httplib::Client& cli, int page) const override {
        std::string path = "/" + resource_ + ".json";
        httplib::Params params{
            {"page",  std::to_string(page)},
            {"limit", std::to_string(limit_)}
        };
        if (!tags_.empty()) params.emplace("tags", tags_);
        if (!username_.empty()) params.emplace("login",   username_);
        if (!api_key_.empty())  params.emplace("api_key", api_key_);
        for (const auto& [k,v] : extra_params_) params.emplace(k, v);

        auto res = cli.Get(path, params, httplib::Headers{});
        if (!res || res->status != 200) return json::array();
        return json::parse(res->body, nullptr, false);
    }

    std::optional<std::string> extract_file_url(const json& post) const override {
        if (post.contains("file_url") && post["file_url"].is_string())
            return post["file_url"].get<std::string>();
        return std::nullopt;
    }
};

// ---------------------------------------------------------------------------
// Gelbooru
// ---------------------------------------------------------------------------

struct Gelbooru : Crawler {
    std::string base_url_, resource_, tags_;
    int limit_;
    std::string username_, api_key_;
    std::vector<std::pair<std::string,std::string>> extra_params_;

    Gelbooru(const json& cfg) {
        base_url_ = cfg.value("url", "https://gelbooru.com");
        resource_ = cfg.value("resource", "posts");
        tags_     = cfg.value("tags", "");
        limit_    = cfg.value("limit", 100);
        if (cfg.contains("login_config")) {
            const auto& lc = cfg["login_config"];
            username_ = lc.value("username", "");
            api_key_  = lc.value("password", "");
        }
        if (cfg.contains("extra_params") && cfg["extra_params"].is_object())
            for (auto& [k,v] : cfg["extra_params"].items())
                extra_params_.emplace_back(k, v.is_string() ? v.get<std::string>() : "");
    }

    std::string name() const override { return "Gelbooru"; }
    std::string base_url() const override { return base_url_; }

    json fetch_posts(httplib::Client& cli, int page) const override {
        // Gelbooru API: /index.php?page=dapi&s=post&q=index&json=1
        std::string s_param = resource_;
        if (!s_param.empty() && s_param.back() == 's')
            s_param = s_param.substr(0, s_param.size() - 1);

        httplib::Params params{
            {"page",  "dapi"},
            {"s",     s_param},
            {"q",     "index"},
            {"json",  "1"},
            {"limit", std::to_string(limit_)},
            {"pid",   std::to_string(page - 1)}
        };
        if (!tags_.empty())    params.emplace(s_param == "post" ? "tags" : "name_pattern",
                                              s_param == "post" ? tags_ : "%" + tags_ + "%");
        if (!username_.empty()) params.emplace("user_id", username_);
        if (!api_key_.empty())  params.emplace("api_key", api_key_);
        for (const auto& [k,v] : extra_params_) params.emplace(k, v);

        auto res = cli.Get("/index.php", params, httplib::Headers{});
        if (!res || res->status != 200) return json::array();

        auto data = json::parse(res->body, nullptr, false);
        if (data.is_discarded()) return json::array();
        if (data.is_array()) return data;
        // Unwrap common envelope keys
        for (const auto& key : {"post", "posts", "tag", "tags"}) {
            if (data.contains(key) && data[key].is_array()) return data[key];
        }
        return json::array();
    }

    std::optional<std::string> extract_file_url(const json& post) const override {
        if (post.contains("file_url") && post["file_url"].is_string())
            return post["file_url"].get<std::string>();
        return std::nullopt;
    }
};

// ---------------------------------------------------------------------------
// Sankaku
// ---------------------------------------------------------------------------

struct Sankaku : Crawler {
    std::string base_url_, login_url_, tags_, username_, api_key_;
    int limit_;
    std::vector<std::pair<std::string,std::string>> extra_params_;
    mutable std::string token_; // lazy-populated on first fetch

    Sankaku(const json& cfg) {
        base_url_  = "https://capi-v2.sankakucomplex.com";
        login_url_ = "https://login.sankakucomplex.com/auth/token";
        tags_      = cfg.value("tags", "");
        limit_     = cfg.value("limit", 20);
        if (cfg.contains("login_config")) {
            const auto& lc = cfg["login_config"];
            username_ = lc.value("username", "");
            api_key_  = lc.value("password", "");
        }
        if (cfg.contains("extra_params") && cfg["extra_params"].is_object())
            for (auto& [k,v] : cfg["extra_params"].items())
                extra_params_.emplace_back(k, v.is_string() ? v.get<std::string>() : "");
    }

    std::string name() const override { return "Sankaku"; }
    std::string base_url() const override { return base_url_; }

    void try_authenticate(httplib::Client& auth_cli) const {
        if (username_.empty() || api_key_.empty()) return;
        json payload{{"login", username_}, {"password", api_key_}};
        auto res = auth_cli.Post("/auth/token",
            httplib::Headers{{"Content-Type", "application/json; charset=utf-8"}},
            payload.dump(), "application/json");
        if (!res || res->status != 200) return;
        auto data = json::parse(res->body, nullptr, false);
        if (data.is_discarded()) return;
        if (data.contains("token_type") && data.contains("access_token"))
            token_ = data["token_type"].get<std::string>() + " " +
                     data["access_token"].get<std::string>();
    }

    json fetch_posts(httplib::Client& cli, int page) const override {
        if (token_.empty() && !username_.empty()) {
            // Need a separate client for the login endpoint
            httplib::Client auth_cli("https://login.sankakucomplex.com");
            try_authenticate(auth_cli);
        }

        httplib::Params params{
            {"lang",  "en"},
            {"page",  std::to_string(page)},
            {"limit", std::to_string(limit_)},
            {"tags",  tags_}
        };
        for (const auto& [k,v] : extra_params_) params.emplace(k, v);

        httplib::Headers headers;
        if (!token_.empty())
            headers.emplace("Authorization", token_);

        auto res = cli.Get("/posts", params, headers);
        if (!res || res->status != 200) return json::array();
        auto data = json::parse(res->body, nullptr, false);
        if (data.is_discarded()) return json::array();
        if (data.is_array()) return data;
        if (data.contains("data") && data["data"].is_array()) return data["data"];
        return json::array();
    }

    std::optional<std::string> extract_file_url(const json& post) const override {
        for (const auto& key : {"file_url", "sample_url", "preview_url"}) {
            if (post.contains(key) && post[key].is_string())
                return post[key].get<std::string>();
        }
        return std::nullopt;
    }
};

// ---------------------------------------------------------------------------
// Board crawl orchestrator
// ---------------------------------------------------------------------------

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

// Download url → save_path, return true on success
static bool download_file(httplib::Client& cli,
                          const std::string& url,
                          const fs::path& save_path) {
    // Use a fresh client if URL doesn't match the crawler's base
    std::string result_body;
    auto res = cli.Get(url.c_str());
    if (!res || res->status != 200) return false;
    std::ofstream out(save_path, std::ios::binary);
    if (!out) return false;
    out.write(res->body.data(), static_cast<std::streamsize>(res->body.size()));
    return true;
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

            // Rate limiting every 5 requests
            if (++request_count % 5 == 0) {
                emit_status(callback_obj, "Rate limiting: waiting 1s...");
                std::this_thread::sleep_for(std::chrono::seconds(1));
            }

            bool ok;
            {
                py::gil_scoped_release rel;
                // Download via httplib (simple GET, any URL)
                httplib::Client dl_cli(file_url.substr(0, file_url.find('/', 8)));
                std::string path_part = file_url.substr(file_url.find('/', 8));
                auto res = dl_cli.Get(path_part.c_str());
                ok = (res && res->status == 200);
                if (ok) {
                    std::ofstream f(save_path, std::ios::binary);
                    f.write(res->body.data(), static_cast<std::streamsize>(res->body.size()));
                }
                // Write metadata JSON sidecar
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
// pybind11 registration (called from register_web in web_requests.cpp)
// ---------------------------------------------------------------------------

void register_board_crawler(pybind11::module_& m) {
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
