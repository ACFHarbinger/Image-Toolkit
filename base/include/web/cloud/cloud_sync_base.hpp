// ---------------------------------------------------------------------------
// base/include/web/cloud/cloud_sync_base.hpp
// Abstract CloudSync interface + shared data types (RemoteFile, SyncTask).
// ---------------------------------------------------------------------------
#pragma once
#include <nlohmann/json.hpp>
#include <functional>
#include <string>
#include <vector>

namespace base::web::cloud {

using json = nlohmann::json;

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

enum class SyncAction { Upload, Download, DeleteLocal, DeleteRemote };

struct SyncTask {
    SyncAction  action;
    std::string local;
    std::string remote;
};

} // namespace base::web::cloud
