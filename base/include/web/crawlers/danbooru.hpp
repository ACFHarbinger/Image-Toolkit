// ---------------------------------------------------------------------------
// base/include/web/crawlers/danbooru.hpp
// Danbooru image board crawler.
// ---------------------------------------------------------------------------
#pragma once
#include "crawler_base.hpp"
#include <algorithm>
#include <string>
#include <utility>
#include <vector>

namespace base::web::board {

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

} // namespace base::web::board
