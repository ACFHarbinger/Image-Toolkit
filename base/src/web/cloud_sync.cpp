// ---------------------------------------------------------------------------
// base/src/web/cloud_sync.cpp
// Cloud sync orchestrator + pybind11 registration.
// Individual provider classes live in include/web/cloud/.
// ---------------------------------------------------------------------------
#include "web/cloud/dropbox_sync.hpp"
#include "web/cloud/google_drive_sync.hpp"
#include "web/cloud/onedrive_sync.hpp"

#include <pybind11/pybind11.h>

#include <algorithm>
#include <filesystem>
#include <string>
#include <unordered_map>
#include <vector>

namespace py = pybind11;
namespace fs = std::filesystem;

namespace base::web::cloud {

static std::vector<SyncTask> build_sync_plan(
    const std::vector<RemoteFile>& remote_files,
    const std::string& local_dir,
    const std::string& remote_dir,
    bool bidirectional)
{
    std::vector<SyncTask> tasks;

    std::unordered_map<std::string, const RemoteFile*> remote_map;
    for (const auto& rf : remote_files)
        remote_map[rf.name] = &rf;

    if (fs::is_directory(local_dir)) {
        for (const auto& entry : fs::directory_iterator(local_dir)) {
            if (!entry.is_regular_file()) continue;
            std::string fname = entry.path().filename().string();
            if (remote_map.find(fname) == remote_map.end()) {
                tasks.push_back({SyncAction::Upload,
                                 entry.path().string(),
                                 (fs::path(remote_dir) / fname).string()});
            }
        }
    }

    for (const auto& rf : remote_files) {
        if (rf.is_folder) continue;
        fs::path lp = fs::path(local_dir) / rf.name;
        if (!fs::exists(lp)) {
            if (bidirectional) {
                tasks.push_back({SyncAction::Download, lp.string(),
                                 rf.id.empty() ? rf.path : rf.id});
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
        if (!ok) emit_err("Failed: " + task.local + " <-> " + task.remote);
    }

    std::string summary = "Sync complete. up=" + std::to_string(uploads) +
                          " down=" + std::to_string(downloads) +
                          " errors=" + std::to_string(errors);
    emit(summary);
    return summary;
}

} // namespace base::web::cloud

// ---------------------------------------------------------------------------
// pybind11 registration
// ---------------------------------------------------------------------------

void register_cloud_sync(pybind11::module_& m) {
    using json = nlohmann::json;

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
str   Summary string "Sync complete. up=N down=M errors=E"
        )doc");
}
