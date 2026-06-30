// ---------------------------------------------------------------------------
// base/include/web/crawlers/gelbooru.hpp
// Gelbooru image board crawler.
// ---------------------------------------------------------------------------
#pragma once
#include "crawler_base.hpp"
#include <string>
#include <utility>
#include <vector>

namespace base::web::board {

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

} // namespace base::web::board
