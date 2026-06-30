// ---------------------------------------------------------------------------
// base/include/web/cloud/dropbox_sync.hpp
// Dropbox cloud storage sync provider.
// ---------------------------------------------------------------------------
#pragma once
#include "cloud_sync_base.hpp"
#include <httplib.h>
#include <fstream>
#include <sstream>
#include <stdexcept>

namespace base::web::cloud {

struct DropboxSync : CloudSync {
    std::string token_;

    std::string provider_name() const override { return "Dropbox"; }

    void authenticate(const json& cfg) override {
        token_ = cfg.value("access_token", "");
        if (token_.empty())
            throw std::runtime_error("Dropbox: access_token missing from config");
    }

    httplib::Headers auth_headers() const {
        return {{"Authorization", "Bearer " + token_},
                {"Content-Type",  "application/json; charset=utf-8"}};
    }

    std::vector<RemoteFile> get_remote_files(const std::string& folder) override {
        httplib::Client cli("https://api.dropboxapi.com");
        std::vector<RemoteFile> files;

        json body{{"path", folder.empty() ? "" : folder},
                  {"recursive", false},
                  {"include_media_info", false},
                  {"include_deleted", false}};

        auto process = [&](const json& b) {
            auto r = cli.Post("/2/files/list_folder", auth_headers(),
                              b.dump(), "application/json");
            if (!r || r->status != 200) return std::string{};
            auto data = json::parse(r->body, nullptr, false);
            if (data.is_discarded()) return std::string{};
            if (data.contains("entries") && data["entries"].is_array()) {
                for (const auto& e : data["entries"]) {
                    RemoteFile rf{};
                    rf.name      = e.value("name", "");
                    rf.path      = e.value("path_lower", "");
                    rf.id        = e.value("id", "");
                    rf.size      = e.value("size", int64_t{0});
                    rf.modified  = e.value("server_modified", "");
                    rf.is_folder = e.value(".tag", "") == "folder";
                    files.push_back(std::move(rf));
                }
            }
            if (data.value("has_more", false))
                return data.value("cursor", std::string{});
            return std::string{};
        };

        std::string cursor = process(body);
        while (!cursor.empty()) {
            json cont_body{{"cursor", cursor}};
            auto r = cli.Post("/2/files/list_folder/continue", auth_headers(),
                              cont_body.dump(), "application/json");
            if (!r || r->status != 200) break;
            auto data = json::parse(r->body, nullptr, false);
            if (data.is_discarded()) break;
            if (data.contains("entries") && data["entries"].is_array()) {
                for (const auto& e : data["entries"]) {
                    RemoteFile rf{};
                    rf.name      = e.value("name", "");
                    rf.path      = e.value("path_lower", "");
                    rf.id        = e.value("id", "");
                    rf.size      = e.value("size", int64_t{0});
                    rf.modified  = e.value("server_modified", "");
                    rf.is_folder = e.value(".tag", "") == "folder";
                    files.push_back(std::move(rf));
                }
            }
            if (!data.value("has_more", false)) break;
            cursor = data.value("cursor", std::string{});
        }
        return files;
    }

    bool upload_file(const std::string& local_path,
                     const std::string& remote_path) override {
        std::ifstream f(local_path, std::ios::binary);
        if (!f) return false;
        std::string body((std::istreambuf_iterator<char>(f)),
                          std::istreambuf_iterator<char>());

        json arg{{"path", remote_path}, {"mode", "overwrite"},
                 {"autorename", false},  {"mute", false}};

        httplib::Client cli("https://content.dropboxapi.com");
        auto r = cli.Post("/2/files/upload",
            httplib::Headers{
                {"Authorization",    "Bearer " + token_},
                {"Dropbox-API-Arg",  arg.dump()},
                {"Content-Type",     "application/octet-stream"}},
            body, "application/octet-stream");
        return (r && r->status == 200);
    }

    bool download_file(const std::string& remote_path,
                       const std::string& local_path) override {
        json arg{{"path", remote_path}};
        httplib::Client cli("https://content.dropboxapi.com");
        auto r = cli.Post("/2/files/download",
            httplib::Headers{
                {"Authorization",   "Bearer " + token_},
                {"Dropbox-API-Arg", arg.dump()},
                {"Content-Type",    ""}},
            "", "text/plain");
        if (!r || r->status != 200) return false;
        std::ofstream out(local_path, std::ios::binary);
        if (!out) return false;
        out.write(r->body.data(), static_cast<std::streamsize>(r->body.size()));
        return true;
    }

    bool create_remote_folder(const std::string& path) override {
        httplib::Client cli("https://api.dropboxapi.com");
        json body{{"path", path}, {"autorename", false}};
        auto r = cli.Post("/2/files/create_folder_v2", auth_headers(),
                          body.dump(), "application/json");
        return (r && (r->status == 200 || r->status == 409));
    }

    bool delete_remote(const std::string& path) override {
        httplib::Client cli("https://api.dropboxapi.com");
        json body{{"path", path}};
        auto r = cli.Post("/2/files/delete_v2", auth_headers(),
                          body.dump(), "application/json");
        return (r && r->status == 200);
    }
};

} // namespace base::web::cloud
