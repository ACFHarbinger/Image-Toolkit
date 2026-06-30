// ---------------------------------------------------------------------------
// base/include/web/crawlers/sankaku.hpp
// Sankaku Complex image board crawler (OAuth2 token auth).
// ---------------------------------------------------------------------------
#pragma once
#include "crawler_base.hpp"
#include <string>
#include <utility>
#include <vector>

namespace base::web::board {

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

} // namespace base::web::board
