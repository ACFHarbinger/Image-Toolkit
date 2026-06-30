// ---------------------------------------------------------------------------
// base/include/web/cloud/google_drive_sync.hpp
// Google Drive cloud storage sync provider.
// ---------------------------------------------------------------------------
#pragma once
#include "cloud_sync_base.hpp"
#include <httplib.h>
#include <filesystem>
#include <fstream>
#include <stdexcept>

namespace base::web::cloud {

namespace fs = std::filesystem;

struct GoogleDriveSync : CloudSync {
    std::string token_; // OAuth2 Bearer

    std::string provider_name() const override { return "GoogleDrive"; }

    void authenticate(const json& cfg) override {
        token_ = cfg.value("access_token", "");
        if (token_.empty())
            throw std::runtime_error("GoogleDrive: access_token missing from config");
    }

    httplib::Headers json_headers() const {
        return {{"Authorization", "Bearer " + token_},
                {"Content-Type",  "application/json; charset=utf-8"}};
    }

    std::string folder_id_for_path(const std::string& path) {
        if (path.empty() || path == "/") return "root";
        return path;
    }

    std::vector<RemoteFile> get_remote_files(const std::string& folder) override {
        httplib::Client cli("https://www.googleapis.com");
        std::string parent = folder_id_for_path(folder);
        std::vector<RemoteFile> files;
        std::string page_token;

        do {
            httplib::Params params{
                {"q",        "'" + parent + "' in parents and trashed = false"},
                {"fields",   "nextPageToken,files(id,name,mimeType,size,modifiedTime)"},
                {"pageSize", "1000"}
            };
            if (!page_token.empty()) params.emplace("pageToken", page_token);

            auto r = cli.Get("/drive/v3/files", params,
                             httplib::Headers{{"Authorization","Bearer "+token_}});
            if (!r || r->status != 200) break;
            auto data = json::parse(r->body, nullptr, false);
            if (data.is_discarded()) break;

            if (data.contains("files") && data["files"].is_array()) {
                for (const auto& e : data["files"]) {
                    RemoteFile rf{};
                    rf.name      = e.value("name", "");
                    rf.id        = e.value("id", "");
                    rf.modified  = e.value("modifiedTime", "");
                    rf.is_folder = e.value("mimeType","") ==
                                   "application/vnd.google-apps.folder";
                    rf.size = 0;
                    if (e.contains("size") && e["size"].is_string())
                        rf.size = std::stoll(e["size"].get<std::string>());
                    files.push_back(std::move(rf));
                }
            }
            page_token = data.value("nextPageToken", std::string{});
        } while (!page_token.empty());

        return files;
    }

    bool upload_file(const std::string& local_path,
                     const std::string& remote_name) override {
        std::ifstream f(local_path, std::ios::binary);
        if (!f) return false;
        std::string body((std::istreambuf_iterator<char>(f)),
                          std::istreambuf_iterator<char>());

        std::string boundary = "boundary_image_toolkit_upload";
        json meta{{"name", fs::path(remote_name).filename().string()}};
        std::string mp =
            "--" + boundary + "\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n\r\n" +
            meta.dump() + "\r\n" +
            "--" + boundary + "\r\n"
            "Content-Type: application/octet-stream\r\n\r\n" +
            body + "\r\n" +
            "--" + boundary + "--";

        httplib::Client cli("https://www.googleapis.com");
        auto r = cli.Post("/upload/drive/v3/files?uploadType=multipart",
            httplib::Headers{
                {"Authorization", "Bearer " + token_},
                {"Content-Type",  "multipart/related; boundary=" + boundary}},
            mp, "multipart/related; boundary=" + boundary);
        return (r && r->status == 200);
    }

    bool download_file(const std::string& file_id,
                       const std::string& local_path) override {
        httplib::Client cli("https://www.googleapis.com");
        httplib::Params params{{"alt", "media"}};
        auto r = cli.Get(("/drive/v3/files/" + file_id).c_str(), params,
                         httplib::Headers{{"Authorization","Bearer "+token_}});
        if (!r || r->status != 200) return false;
        std::ofstream out(local_path, std::ios::binary);
        if (!out) return false;
        out.write(r->body.data(), static_cast<std::streamsize>(r->body.size()));
        return true;
    }

    bool create_remote_folder(const std::string& name) override {
        httplib::Client cli("https://www.googleapis.com");
        json body{{"name", name},
                  {"mimeType", "application/vnd.google-apps.folder"}};
        auto r = cli.Post("/drive/v3/files", json_headers(),
                          body.dump(), "application/json");
        return (r && r->status == 200);
    }

    bool delete_remote(const std::string& file_id) override {
        httplib::Client cli("https://www.googleapis.com");
        auto r = cli.Delete(("/drive/v3/files/" + file_id).c_str(),
                            httplib::Headers{{"Authorization","Bearer "+token_}},
                            "", "");
        return (r && r->status == 204);
    }
};

} // namespace base::web::cloud
