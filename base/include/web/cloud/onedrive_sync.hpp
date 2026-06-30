// ---------------------------------------------------------------------------
// base/include/web/cloud/onedrive_sync.hpp
// Microsoft OneDrive cloud storage sync provider.
// ---------------------------------------------------------------------------
#pragma once
#include "cloud_sync_base.hpp"
#include <httplib.h>
#include <fstream>
#include <stdexcept>

namespace base::web::cloud {

struct OneDriveSync : CloudSync {
    std::string token_;

    std::string provider_name() const override { return "OneDrive"; }

    void authenticate(const json& cfg) override {
        token_ = cfg.value("access_token", "");
        if (token_.empty())
            throw std::runtime_error("OneDrive: access_token missing from config");
    }

    std::vector<RemoteFile> get_remote_files(const std::string& folder) override {
        httplib::Client cli("https://graph.microsoft.com");
        std::string ep = folder.empty() || folder == "/"
            ? "/v1.0/me/drive/root/children"
            : "/v1.0/me/drive/root:/" + folder + ":/children";

        std::vector<RemoteFile> files;

        auto process = [&](const std::string& url_path) {
            auto r = cli.Get(url_path.c_str(),
                             httplib::Headers{{"Authorization","Bearer "+token_}});
            if (!r || r->status != 200) return std::string{};
            auto data = json::parse(r->body, nullptr, false);
            if (data.is_discarded()) return std::string{};
            if (data.contains("value") && data["value"].is_array()) {
                for (const auto& e : data["value"]) {
                    RemoteFile rf{};
                    rf.name      = e.value("name", "");
                    rf.id        = e.value("id", "");
                    rf.modified  = e.value("lastModifiedDateTime", "");
                    rf.is_folder = e.contains("folder");
                    rf.size      = e.value("size", int64_t{0});
                    files.push_back(std::move(rf));
                }
            }
            return data.value("@odata.nextLink", std::string{});
        };

        std::string next_link = process(ep);
        while (!next_link.empty()) {
            const std::string host = "https://graph.microsoft.com";
            std::string path_part = next_link;
            if (path_part.substr(0, host.size()) == host)
                path_part = path_part.substr(host.size());
            next_link = process(path_part);
        }
        return files;
    }

    bool upload_file(const std::string& local_path,
                     const std::string& remote_path) override {
        std::ifstream f(local_path, std::ios::binary);
        if (!f) return false;
        std::string body((std::istreambuf_iterator<char>(f)),
                          std::istreambuf_iterator<char>());

        std::string ep = "/v1.0/me/drive/root:/" + remote_path + ":/content";
        httplib::Client cli("https://graph.microsoft.com");
        auto r = cli.Put(ep.c_str(),
            httplib::Headers{{"Authorization","Bearer "+token_}},
            body, "application/octet-stream");
        return (r && (r->status == 200 || r->status == 201));
    }

    bool download_file(const std::string& item_id,
                       const std::string& local_path) override {
        std::string ep = "/v1.0/me/drive/items/" + item_id + "/content";
        httplib::Client cli("https://graph.microsoft.com");
        auto r = cli.Get(ep.c_str(),
                         httplib::Headers{{"Authorization","Bearer "+token_}});
        if (!r || r->status != 200) return false;
        std::ofstream out(local_path, std::ios::binary);
        if (!out) return false;
        out.write(r->body.data(), static_cast<std::streamsize>(r->body.size()));
        return true;
    }

    bool create_remote_folder(const std::string& name) override {
        httplib::Client cli("https://graph.microsoft.com");
        json body{{"name", name}, {"folder", json::object()},
                  {"@microsoft.graph.conflictBehavior", "fail"}};
        auto r = cli.Post("/v1.0/me/drive/root/children",
            httplib::Headers{
                {"Authorization","Bearer "+token_},
                {"Content-Type", "application/json"}},
            body.dump(), "application/json");
        return (r && (r->status == 201 || r->status == 409));
    }

    bool delete_remote(const std::string& item_id) override {
        std::string ep = "/v1.0/me/drive/items/" + item_id;
        httplib::Client cli("https://graph.microsoft.com");
        auto r = cli.Delete(ep.c_str(),
                            httplib::Headers{{"Authorization","Bearer "+token_}},
                            "", "");
        return (r && r->status == 204);
    }
};

} // namespace base::web::cloud
