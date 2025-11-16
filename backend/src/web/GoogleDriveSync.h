#ifndef GOOGLE_DRIVE_SYNC_H
#define GOOGLE_DRIVE_SYNC_H

#include <string>
#include <vector>
#include <map>
#include <filesystem>
#include <functional>
#include "nlohmann/json.hpp" // Requires nlohmann/json dependency

namespace fs = std::filesystem;
using json = nlohmann::json;

// Represents file metadata
struct FileData {
    std::string id;
    std::string path;
    long mtime = 0;
    bool isFolder = false;
};

/**
 * @brief Replicates the core file sync logic of google_drive_sync.py.
 *
 * This class uses libcurl and nlohmann/json to interact directly with the
 * Google Drive v3 REST API.
 *
 * NOTE: This class assumes a valid OAuth 2.0 Access Token is provided.
 * It does not implement the token generation/refresh flow.
 */
class GoogleDriveSync {
public:
    using LoggerCallback = std::function<void(const std::string&)>;

    /**
     * @param accessToken A valid OAuth 2.0 access token.
     * @param localPath The local directory to sync.
     * @param remotePath The path in Google Drive (e.g., "Backups/2025").
     * @param dryRun If true, simulate changes without executing them.
     * @param logger A callback for logging status messages.
     */
    GoogleDriveSync(const std::string& accessToken,
                    const fs::path& localPath,
                    const std::string& remotePath,
                    bool dryRun = false,
                    LoggerCallback logger = nullptr);

    ~GoogleDriveSync();

    /**
     * @brief Runs the synchronization logic.
     * Uploads missing local files, downloads missing remote files.
     * @return A pair<bool, string> indicating success and a final message.
     */
    std::pair<bool, std::string> executeSync();

private:
    // --- API Call Helpers ---
    bool apiRequest(const std::string& url, const std::string& method, const std::string& postData, const std::vector<std::string>& headers, std::string& response);
    json apiGet(const std::string& url);
    json apiPost(const std::string& url, const json& data);
    json apiPostMedia(const std::string& url, const json& metadata, const fs::path& filePath);
    bool apiDownload(const std::string& fileId, const fs::path& localDestination);

    // --- Core Logic ---
    std::string findOrCreateDestinationFolder();
    std::string createRemoteFolder(const std::string& name, const std::string& parentId);
    std::map<std::string, FileData> getLocalFilesMap();
    std::map<std::string, FileData> getRemoteFilesMap(const std::string& rootFolderId);
    bool uploadFile(const fs::path& localPath, const std::string& remoteName, const std::string& parentId);

    // --- libcurl Callbacks ---
    static size_t writeCallback(void* contents, size_t size, size_t nmemb, void* userp);

    void log(const std::string& message);

    void* m_curlHandle;
    std::string m_accessToken;
    std::string m_authHeader;
    fs::path m_localPath;
    std::string m_remotePath;
    bool m_dryRun;
    LoggerCallback m_logger;
    
    std::map<std::string, std::string> m_remotePathToId;
};

#endif // GOOGLE_DRIVE_SYNC_H