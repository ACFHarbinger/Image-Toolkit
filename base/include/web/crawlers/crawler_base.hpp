// ---------------------------------------------------------------------------
// base/include/web/crawlers/crawler_base.hpp
// Abstract Crawler interface shared by Danbooru, Gelbooru, Sankaku.
// ---------------------------------------------------------------------------
#pragma once
#include <httplib.h>
#include <nlohmann/json.hpp>
#include <optional>
#include <string>

namespace base::web::board {

using json = nlohmann::json;

struct Crawler {
    virtual ~Crawler() = default;
    virtual std::string name() const = 0;
    virtual std::string base_url() const = 0;
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

} // namespace base::web::board
