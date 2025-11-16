#include "GoogleDriveSync.h"
#include <iostream>
#include <fstream>
#include <curl/curl.h>
#include "../core/FileSystemUtil.h" // Assumed from previous step

// API Endpoints
const std::string API_FILES_LIST = "https://www.googleapis.com/drive/v3/files";
const std::string API_FILES_CREATE = "https://www.googleapis.com/drive/v3/files";
const std::string API_FILES_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart";
const std::string API_FILES_GET = "https://www.googleapis.com/drive/v3/files/"; // Append {fileId}?alt=media

GoogleDriveSync::GoogleDriveSync(const std::string& accessToken,
                                 const fs::path& localPath,
                                 const std::string& remotePath,
                                 bool dryRun,
                                 LoggerCallback logger)
    : m_accessToken(accessToken), m_localPath(localPath), m_remotePath(remotePath), m_dryRun(dryRun), m_logger(logger) {
    
    m_authHeader = "Authorization: Bearer " + m_accessToken;
    curl_global_init(CURL_GLOBAL_ALL);
    m_curlHandle = curl_easy_init();
    if (!m_curlHandle) {
        throw std::runtime_error("Failed to initialize libcurl");
    }
    log("GoogleDriveSync initialized.");
}

GoogleDriveSync::~GoogleDriveSync() {
    if (m_curlHandle) {
        curl_easy_cleanup(static_cast<CURL*>(m_curlHandle));
    }
    curl_global_cleanup();
}

void GoogleDriveSync::log(const std::string& message) {
    if (m_logger) {
        m_logger(message);
    } else {
        std::cout << message << std::endl;
    }
}

size_t GoogleDriveSync::writeCallback(void* contents, size_t size, size_t nmemb, void* userp) {
    static_cast<std::string*>(userp)->append(static_cast<char*>(contents), size * nmemb);
    return size * nmemb;
}

// --- API Call Helpers ---

bool GoogleDriveSync::apiRequest(const std::string& url, const std::string& method, const std::string& postData, const std::vector<std::string>& headers, std::string& response) {
    CURL* curl = static_cast<CURL*>(m_curlHandle);
    if (!curl) return false;

    response.clear();
    curl_slist* headerList = nullptr;
    for (const auto& h : headers) {
        headerList = curl_slist_append(headerList, h.c_str());
    }

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_CUSTOMREQUEST, method.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headerList);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, writeCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    
    if (method == "POST" || method == "PATCH") {
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, postData.c_str());
    }

    CURLcode res = curl_easy_perform(curl);
    curl_slist_free_all(headerList);

    if (res != CURLE_OK) {
        log("curl_easy_perform() failed: " + std::string(curl_easy_strerror(res)));
        return false;
    }

    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    if (http_code < 200 || http_code >= 300) {
        log("HTTP Error " + std::to_string(http_code) + ": " + response);
        return false;
    }
    return true;
}

json GoogleDriveSync::apiGet(const std::string& url) {
    std::string response;
    if (apiRequest(url, "GET", "", {m_authHeader}, response)) {
        return json::parse(response);
    }
    return nullptr;
}

json GoogleDriveSync::apiPost(const std::string& url, const json& data) {
    std::string response;
    std::vector<std::string> headers = {m_authHeader, "Content-Type: application/json"};
    if (apiRequest(url, "POST", data.dump(), headers, response)) {
        return json::parse(response);
    }
    return nullptr;
}

// ... Implementations for apiPostMedia and apiDownload are complex and omitted for brevity ...
// They would involve setting up curl_formadd or read callbacks.
// This is a placeholder for the upload logic.
bool GoogleDriveSync::uploadFile(const fs::path& localPath, const std::string& remoteName, const std::string& parentId) {
    if (m_dryRun) {
        log("   [DRY RUN] UPLOAD: " + localPath.string());
        return true;
    }
    log("   UPLOADING: " + localPath.string() + " (Full C++ upload logic is complex and omitted)");
    // This requires a full multipart/form-data POST using libcurl,
    // which is significantly more complex than the other requests.
    return false; // Placeholder
}

bool GoogleDriveSync::apiDownload(const std::string& fileId, const fs::path& localDestination) {
    if (m_dryRun) {
        log("   [DRY RUN] DOWNLOAD: " + localDestination.filename().string());
        return true;
    }
    log("   DOWNLOADING: " + localDestination.filename().string() + " (Full C++ download logic is omitted)");
    // This would use curl to GET from API_FILES_GET + fileId + "?alt=media"
    // and write the response to a file.
    return false; // Placeholder
}


// --- Core Logic ---

std::string GoogleDriveSync::createRemoteFolder(const std::string& name, const std::string& parentId) {
    if (m_dryRun) {
        std::string dryRunId = "DRY_RUN_ID_" + name;
        log("   [DRY RUN] Would have created folder '" + name + "'");
        return dryRunId;
    }

    json metadata = {
        {"name", name},
        {"mimeType", "application/vnd.google-apps.folder"},
        {"parents", {parentId}}
    };
    json result = apiPost(API_FILES_CREATE, metadata);
    if (result != nullptr && result.contains("id")) {
        std::string newId = result["id"];
        log("   Created folder: " + name + " (ID: " + newId + ")");
        return newId;
    }
    log("   ERROR: Failed to create folder " + name);
    return "";
}

std::string GoogleDriveSync::findOrCreateDestinationFolder() {
    std::string parentId = "root";
    fs::path remotePath(m_remotePath);
    std::string currentRemotePathStr;

    for (const auto& part : remotePath) {
        std::string folderName = part.string();
        if (folderName == "/") continue;

        if (currentRemotePathStr.empty()) {
            currentRemotePathStr = folderName;
        } else {
            currentRemotePathStr += "/" + folderName;
        }

        std::string query = "name='" + folderName + "' and "
                            "mimeType='application/vnd.google-apps.folder' and "
                            "'" + parentId + "' in parents and "
                            "trashed=false";
        
        std::string url = API_FILES_LIST + "?q=" + curl_easy_escape(static_cast<CURL*>(m_curlHandle), query.c_str(), 0) + "&fields=files(id,name)";
        
        json result = apiGet(url);
        if (result == nullptr || !result.contains("files")) {
            throw std::runtime_error("Failed to list files in Drive.");
        }

        if (result["files"].empty()) {
            // Not found, create it
            parentId = createRemoteFolder(folderName, parentId);
            if (parentId.empty()) {
                throw std::runtime_error("Failed to create remote folder " + folderName);
            }
        } else {
            // Found, get its ID
            parentId = result["files"][0]["id"];
        }
        m_remotePathToId[currentRemotePathStr] = parentId;
    }
    
    log("✅ Destination Folder ID: " + parentId);
    return parentId;
}

std::map<std::string, FileData> GoogleDriveSync::getLocalFilesMap() {
    std::map<std::string, FileData> localItems;
    std::string basePath = fs::canonical(m_localPath).string();
    size_t baseLen = basePath.length() + 1; // +1 for the separator

    for (const auto& entry : fs::recursive_directory_iterator(m_localPath)) {
        std::string absPath = fs::canonical(entry.path()).string();
        std::string relPath = absPath.substr(baseLen);
        std::replace(relPath.begin(), relPath.end(), '\\', '/'); // Normalize separators

        FileData data;
        data.path = absPath;
        auto mtime = fs::last_write_time(entry);
        data.mtime = std::chrono::duration_cast<std::chrono::seconds>(mtime.time_since_epoch()).count();
        data.isFolder = entry.is_directory();
        
        localItems[relPath] = data;
    }
    return localItems;
}

std::map<std::string, FileData> GoogleDriveSync::getRemoteFilesMap(const std::string& rootFolderId) {
    std::map<std::string, FileData> remoteItems;
    std::vector<std::pair<std::string, std::string>> folderQueue = {{rootFolderId, ""}};
    m_remotePathToId.clear(); // Clear and rebuild from root

    while (!folderQueue.empty()) {
        auto [currentFolderId, currentRelPath] = folderQueue.front();
        folderQueue.erase(folderQueue.begin());

        std::string pageToken = "";
        do {
            std::string query = "'" + currentFolderId + "' in parents and trashed=false";
            std::string url = API_FILES_LIST + "?q=" + curl_easy_escape(static_cast<CURL*>(m_curlHandle), query.c_str(), 0)
                            + "&fields=nextPageToken,files(id,name,modifiedTime,mimeType)";
            if (!pageToken.empty()) {
                url += "&pageToken=" + pageToken;
            }

            json result = apiGet(url);
            if (result == nullptr || !result.contains("files")) break;

            for (const auto& item : result["files"]) {
                std::string name = item["name"];
                std::string id = item["id"];
                std::string fullPath = currentRelPath.empty() ? name : currentRelPath + "/" + name;
                bool isFolder = item["mimeType"] == "application/vnd.google-apps.folder";

                FileData data;
                data.id = id;
                data.isFolder = isFolder;
                
                // Parse timestamp
                std::string mtimeStr = item["modifiedTime"];
                std::tm tm = {};
                std::stringstream ss(mtimeStr);
                ss >> std::get_time(&tm, "%Y-%m-%dT%H:%M:%S");
                data.mtime = std::mktime(&tm);

                remoteItems[fullPath] = data;
                if (isFolder) {
                    folderQueue.push_back({id, fullPath});
                    m_remotePathToId[fullPath] = id;
                }
            }
            pageToken = result.contains("nextPageToken") ? result["nextPageToken"].get<std::string>() : "";
        } while (!pageToken.empty());
    }
    
    log("\n--- Current Remote Files in Destination Folder ---");
    // (Log dump omitted for brevity)
    return remoteItems;
}


std::pair<bool, std::string> GoogleDriveSync::executeSync() {
    try {
        std::string destFolderId = findOrCreateDestinationFolder();
        if (destFolderId.empty()) return {false, "Failed to secure destination folder."};
        
        log("📋 Comparing local and remote files recursively...");
        auto localItems = getLocalFilesMap();
        auto remoteItems = getRemoteFilesMap(destFolderId);

        log("\n--- Sync Operation Analysis & Execution ---");
        int uploaded = 0;
        int downloaded = 0;
        int skipped = 0;
        
        std::map<std::string, FileData> remoteCopy = remoteItems;

        // 1. Process Local Items (Upload Missing)
        for (const auto& [relPath, localData] : localItems) {
            auto it = remoteCopy.find(relPath);
            
            if (localData.isFolder) {
                if (it == remoteCopy.end()) {
                    // Create remote folder
                    fs::path p(relPath);
                    std::string parentId = (p.has_parent_path() && m_remotePathToId.count(p.parent_path().string()))
                                           ? m_remotePathToId[p.parent_path().string()]
                                           : destFolderId;
                    std::string newId = createRemoteFolder(p.filename().string(), parentId);
                    m_remotePathToId[relPath] = newId;
                } else {
                    remoteCopy.erase(it); // Mark as processed
                }
                continue;
            }

            // It's a file
            if (it != remoteCopy.end()) {
                // File exists in both. Skip.
                log("   SKIPPING: " + relPath);
                skipped++;
                remoteCopy.erase(it);
            } else {
                // File only exists locally. Upload.
                fs::path p(relPath);
                std::string parentId = (p.has_parent_path() && m_remotePathToId.count(p.parent_path().string()))
                                       ? m_remotePathToId[p.parent_path().string()]
                                       : destFolderId;
                if (uploadFile(localData.path, p.filename().string(), parentId)) {
                    uploaded++;
                }
            }
        }

        // 2. Process Remaining Remote Items (Download Missing)
        for (const auto& [relPath, remoteData] : remoteCopy) {
            if (remoteData.isFolder) continue; // Skip folders

            // File only exists remotely. Download.
            fs::path localDest = m_localPath / relPath;
            FileSystemUtil::createDirectory(localDest, true);
            if (apiDownload(remoteData.id, localDest)) {
                downloaded++;
            }
        }
        
        std::string finalMsg = "Sync " + std::string(m_dryRun ? "simulation" : "complete") + ". "
                             + "Uploads: " + std::to_string(uploaded)
                             + ", Downloads: " + std::to_string(downloaded)
                             + ", Skipped: " + std::to_string(skipped);
        log(finalMsg);
        return {true, finalMsg};
        
    } catch (const std::exception& e) {
        log("❌ Sync failed: " + std::string(e.what()));
        return {false, "Sync failed: " + std::string(e.what())};
    }
}