// ---------------------------------------------------------------------------
// base/src/web/cloud_sync.cpp — cloud storage sync (Dropbox / GDrive / OneDrive)
// Phase 9 of Rust→C++ migration.
// Uses cpp-httplib + nlohmann/json.  No external dependencies beyond httplib.
// ---------------------------------------------------------------------------
#include <httplib.h>
#include <nlohmann/json.hpp>
#include <pybind11/pybind11.h>

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <functional>
#include <memory>
#include <optional>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace py = pybind11;
using json   = nlohmann::json;
namespace fs = std::filesystem;

namespace base::web::cloud {

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

struct RemoteFile {
    std::string name;
    std::string path;
    std::string id;
    int64_t     size;
    std::string modified;
    bool        is_folder;
};

using StatusCb = std::function<void(const std::string&)>;
using ErrorCb  = std::function<void(const std::string&)>;

// ---------------------------------------------------------------------------
// Abstract CloudSync interface
// ---------------------------------------------------------------------------

struct CloudSync {
    virtual ~CloudSync() = default;
    virtual std::string provider_name() const = 0;

    virtual void authenticate(const json& cfg) = 0;
    virtual std::vector<RemoteFile> get_remote_files(const std::string& folder) = 0;
    virtual bool upload_file(const std::string& local_path, const std::string& remote_path) = 0;
    virtual bool download_file(const std::string& remote_path, const std::string& local_path) = 0;
    virtual bool create_remote_folder(const std::string& path) = 0;
    virtual bool delete_remote(const std::string& path) = 0;
};

// ---------------------------------------------------------------------------
// Dropbox
// ---------------------------------------------------------------------------

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
                    rf.name = e.value("name", "");
                    rf.path = e.value("path_lower", "");
                    rf.id   = e.value("id", "");
                    rf.size = e.value("size", int64_t{0});
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

// ---------------------------------------------------------------------------
// Google Drive
// ---------------------------------------------------------------------------

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
        // Accept either a Drive folder ID directly or try to resolve "root"
        if (path.empty() || path == "/") return "root";
        return path; // caller is expected to pass Drive folder IDs
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

        // Multipart upload
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

// ---------------------------------------------------------------------------
// OneDrive
// ---------------------------------------------------------------------------

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
        std::string next_link;

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

        next_link = process(ep);
        while (!next_link.empty()) {
            // next_link is a full URL; strip https://graph.microsoft.com prefix
            std::string path_part = next_link;
            const std::string host = "https://graph.microsoft.com";
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

// ---------------------------------------------------------------------------
// Sync runner (orchestrates bidirectional sync)
// ---------------------------------------------------------------------------

enum class SyncAction { Upload, Download, DeleteLocal, DeleteRemote };

struct SyncTask {
    SyncAction  action;
    std::string local;
    std::string remote;
};

static std::vector<SyncTask> build_sync_plan(
    const std::vector<RemoteFile>& remote_files,
    const std::string& local_dir,
    const std::string& remote_dir,
    bool bidirectional)
{
    std::vector<SyncTask> tasks;

    // Build remote map by name
    std::unordered_map<std::string, const RemoteFile*> remote_map;
    for (const auto& rf : remote_files)
        remote_map[rf.name] = &rf;

    // Walk local files
    if (fs::is_directory(local_dir)) {
        for (const auto& entry : fs::directory_iterator(local_dir)) {
            if (!entry.is_regular_file()) continue;
            std::string fname = entry.path().filename().string();
            if (remote_map.find(fname) == remote_map.end()) {
                // Local only → upload
                tasks.push_back({SyncAction::Upload,
                                 entry.path().string(),
                                 (fs::path(remote_dir) / fname).string()});
            }
        }
    }

    // Walk remote files
    for (const auto& rf : remote_files) {
        if (rf.is_folder) continue;
        fs::path lp = fs::path(local_dir) / rf.name;
        if (!fs::exists(lp)) {
            if (bidirectional) {
                tasks.push_back({SyncAction::Download, lp.string(), rf.id.empty() ? rf.path : rf.id});
            }
        }
    }

    return tasks;
}

static std::string run_sync_impl(
    CloudSync& sync,
    const json& cfg,
    py::object callback_obj)
{
    auto emit = [&](const std::string& msg) {
        py::gil_scoped_acquire acq;
        try { callback_obj.attr("on_status_emitted")(msg); } catch (...) {}
    };
    auto emit_err = [&](const std::string& msg) {
        py::gil_scoped_acquire acq;
        try { callback_obj.attr("on_error_emitted")(msg); } catch (...) {}
    };

    emit("Authenticating with " + sync.provider_name() + "...");
    sync.authenticate(cfg);
    emit("Authenticated.");

    std::string local_dir  = cfg.value("local_dir",  ".");
    std::string remote_dir = cfg.value("remote_dir", "/");
    bool bidirectional     = cfg.value("bidirectional", true);

    emit("Listing remote files...");
    auto remote_files = sync.get_remote_files(remote_dir);
    emit("Found " + std::to_string(remote_files.size()) + " remote entries.");

    auto tasks = build_sync_plan(remote_files, local_dir, remote_dir, bidirectional);
    emit("Sync plan: " + std::to_string(tasks.size()) + " tasks.");

    int uploads = 0, downloads = 0, errors = 0;
    for (const auto& task : tasks) {
        bool ok = false;
        if (task.action == SyncAction::Upload) {
            emit("Uploading: " + task.local);
            ok = sync.upload_file(task.local, task.remote);
            if (ok) ++uploads; else ++errors;
        } else if (task.action == SyncAction::Download) {
            emit("Downloading: " + task.remote);
            fs::create_directories(fs::path(task.local).parent_path());
            ok = sync.download_file(task.remote, task.local);
            if (ok) ++downloads; else ++errors;
        }
        if (!ok) emit_err("Failed: " + task.local + " ↔ " + task.remote);
    }

    std::string summary = "Sync complete. ↑" + std::to_string(uploads) +
                          " ↓" + std::to_string(downloads) +
                          " errors=" + std::to_string(errors);
    emit(summary);
    return summary;
}

} // namespace base::web::cloud

// ---------------------------------------------------------------------------
// pybind11 registration
// ---------------------------------------------------------------------------

void register_cloud_sync(pybind11::module_& m) {
    m.def("run_sync",
        [](const std::string& provider,
           const std::string& config_json,
           py::object callback_obj) -> std::string {
            auto cfg = json::parse(config_json, nullptr, false);
            if (cfg.is_discarded())
                throw py::value_error("run_sync: invalid JSON config");

            std::string p = provider;
            std::transform(p.begin(), p.end(), p.begin(), ::tolower);

            py::gil_scoped_release rel;

            if (p == "dropbox") {
                base::web::cloud::DropboxSync s;
                py::gil_scoped_acquire acq;
                return base::web::cloud::run_sync_impl(s, cfg, callback_obj);
            } else if (p == "googledrive" || p == "google_drive") {
                base::web::cloud::GoogleDriveSync s;
                py::gil_scoped_acquire acq;
                return base::web::cloud::run_sync_impl(s, cfg, callback_obj);
            } else if (p == "onedrive" || p == "one_drive") {
                base::web::cloud::OneDriveSync s;
                py::gil_scoped_acquire acq;
                return base::web::cloud::run_sync_impl(s, cfg, callback_obj);
            }
            throw py::value_error("run_sync: unknown provider '" + provider + "'");
        },
        py::arg("provider_name"), py::arg("config_json"), py::arg("callback_obj"),
        R"doc(
            Bidirectional cloud sync (Dropbox / GoogleDrive / OneDrive).

            Parameters
            ----------
                provider_name : str   "dropbox", "googledrive", or "onedrive"
                config_json   : str   JSON with: access_token, local_dir, remote_dir,
                                      bidirectional (bool, default true)
                callback_obj  : obj   Must have on_status_emitted(msg), on_error_emitted(msg).
            Returns
            -------
                str   Summary string "Sync complete. ↑N ↓M errors=E"
        )doc");
}
