#include "OneDriveSync.hpp"

const QString GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0";

OneDriveSync::OneDriveSync(const QString &localPath, const QString &remoteFolderName,
                           const QString &clientId, const QString &token,
                           bool dryRun, Logger logger,
                           const QString &actionLocal, const QString &actionRemote,
                           QObject *parent)
    : AbstractSync(localPath, remoteFolderName, dryRun, logger, actionLocal, actionRemote, parent),
      m_accessToken(token) {
    m_nam = new QNetworkAccessManager(this);
}

void OneDriveSync::executeSync() {
    try {
        checkStop();
        if (m_accessToken.isEmpty()) throw std::runtime_error("Missing Access Token");

        log("📋 Scanning local and remote files...");
        auto localItems = scanLocalFiles();
        auto remoteItems = scanRemoteFiles(); // Implementation below

        log(QString("   Found %1 local items, %2 remote items.").arg(localItems.size()).arg(remoteItems.size()));

        QMap<QString, FileMetadata> remoteSkipped = remoteItems;
        int up = 0, down = 0, delL = 0, delR = 0;

        // 1. Process Local
        for (auto it = localItems.begin(); it != localItems.end(); ++it) {
            checkStop();
            QString relPath = it.key();
            
            if (it->isFolder) {
                if (remoteSkipped.contains(relPath)) {
                    remoteSkipped.remove(relPath);
                } else if (m_actionLocal == "upload") {
                    if (createRemoteFolder(relPath)) up++;
                } else if (m_actionLocal == "delete_local") {
                    if (deleteLocal(it->path)) delL++;
                }
                continue;
            }

            if (remoteSkipped.contains(relPath)) {
                remoteSkipped.remove(relPath); // Exists in both
            } else {
                if (m_actionLocal == "upload") {
                    if (uploadFile(it->path, relPath)) up++;
                } else if (m_actionLocal == "delete_local") {
                    if (deleteLocal(it->path)) delL++;
                }
            }
        }

        // 2. Process Remote Orphans
        for (auto it = remoteSkipped.begin(); it != remoteSkipped.end(); ++it) {
            checkStop();
            QString relPath = it.key();

            if (it->isFolder) {
                if (m_actionRemote == "delete_remote") {
                    if (deleteRemote(it->id, relPath)) delR++;
                }
                continue;
            }

            if (m_actionRemote == "download") {
                QString dest = QDir(m_localPath).filePath(relPath);
                if (downloadFile(it->id, dest)) down++;
            } else if (m_actionRemote == "delete_remote") {
                if (deleteRemote(it->id, relPath)) delR++;
            }
        }
        
        log(QString("✅ Sync Complete. Up: %1, Down: %2, Del-L: %3, Del-R: %4").arg(up).arg(down).arg(delL).arg(delR));

    } catch (const std::exception &e) {
        log(QString("❌ Error: %1").arg(e.what()));
    }
}

// --- API Implementation ---

QByteArray OneDriveSync::makeRequest(const QString &verb, const QString &url, 
                                     const QByteArray &data, const QString &contentType, int *statusCode) {
    QNetworkRequest req(QUrl(url));
    req.setRawHeader("Authorization", ("Bearer " + m_accessToken).toUtf8());
    if (!data.isEmpty() || verb == "POST" || verb == "PUT") {
        req.setHeader(QNetworkRequest::ContentTypeHeader, contentType);
    }

    QNetworkReply *reply = nullptr;
    if (verb == "GET") reply = m_nam->get(req);
    else if (verb == "POST") reply = m_nam->post(req, data);
    else if (verb == "PUT") reply = m_nam->put(req, data);
    else if (verb == "DELETE") reply = m_nam->deleteResource(req);

    QEventLoop loop;
    connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
    loop.exec();

    if (statusCode) *statusCode = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
    
    QByteArray result = reply->readAll();
    bool error = reply->error() != QNetworkReply::NoError;
    reply->deleteLater();

    if (error) {
        // Simple error handling, in real app parse JSON error
        log("API Error: " + url + " | " + result); 
    }
    return result;
}

QString OneDriveSync::resolvePathToId(const QString &path) {
    if (path.isEmpty()) return "root";
    if (m_remotePathToId.contains(path)) return m_remotePathToId[path];

    // Graph API allows path addressing: /drive/root:/path/to/folder
    QString url = GRAPH_ENDPOINT + "/me/drive/root:/" + path;
    int code;
    QByteArray resp = makeRequest("GET", url, {}, "", &code);
    if (code == 200) {
        QJsonObject obj = QJsonDocument::fromJson(resp).object();
        QString id = obj["id"].toString();
        m_remotePathToId[path] = id;
        return id;
    }
    return "";
}

QMap<QString, FileMetadata> OneDriveSync::scanRemoteFiles() {
    QMap<QString, FileMetadata> items;
    QString rootId = resolvePathToId(m_remotePath);
    if (rootId.isEmpty()) return items;

    struct QueueItem { QString id; QString relPath; };
    QList<QueueItem> queue;
    queue.append({rootId, ""});

    while (!queue.isEmpty()) {
        checkStop();
        QueueItem current = queue.takeFirst();
        QString url = GRAPH_ENDPOINT + "/me/drive/items/" + current.id + "/children";

        while (!url.isEmpty()) {
            QByteArray json = makeRequest("GET", url);
            QJsonObject root = QJsonDocument::fromJson(json).object();
            QJsonArray vals = root["value"].toArray();

            for (const auto &v : vals) {
                QJsonObject item = v.toObject();
                QString name = item["name"].toString();
                QString id = item["id"].toString();
                bool isFolder = item.contains("folder");
                QString relPath = current.relPath.isEmpty() ? name : current.relPath + "/" + name;

                FileMetadata meta;
                meta.id = id;
                meta.isFolder = isFolder;
                items.insert(relPath, meta);

                if (isFolder) {
                    queue.append({id, relPath});
                    QString fullPathKey = m_remotePath.isEmpty() ? relPath : m_remotePath + "/" + relPath;
                    m_remotePathToId[fullPathKey] = id;
                }
            }
            // Handle Pagination
            if (root.contains("@odata.nextLink")) url = root["@odata.nextLink"].toString();
            else url = "";
        }
    }
    return items;
}

bool OneDriveSync::uploadFile(const QString &localPath, const QString &relPath) {
    checkStop();
    if (m_dryRun) { log("   [DRY RUN] UPLOAD: " + relPath); return true; }

    QString target = m_remotePath.isEmpty() ? relPath : m_remotePath + "/" + relPath;
    QString url = GRAPH_ENDPOINT + "/me/drive/root:/" + target + ":/content";
    
    QFile f(localPath);
    if (!f.open(QIODevice::ReadOnly)) return false;
    QByteArray content = f.readAll();
    
    int code;
    makeRequest("PUT", url, content, "application/octet-stream", &code);
    return (code == 200 || code == 201);
}

bool OneDriveSync::createRemoteFolder(const QString &relPath) {
    checkStop();
    if (m_dryRun) { log("   [DRY RUN] CREATE FOLDER: " + relPath); return true; }

    // Logic: Find parent ID, create child. 
    // Simplified: Using Path addressing for creation is tricky if parent doesn't exist.
    // Assuming hierarchical traversal creates parents first.
    int lastSlash = relPath.lastIndexOf('/');
    QString parentRel = (lastSlash == -1) ? "" : relPath.left(lastSlash);
    QString name = (lastSlash == -1) ? relPath : relPath.mid(lastSlash + 1);
    
    QString fullParent = m_remotePath.isEmpty() ? parentRel : m_remotePath + "/" + parentRel;
    if (fullParent.endsWith('/')) fullParent.chop(1);
    
    QString parentId = resolvePathToId(fullParent);
    if (parentId.isEmpty()) return false;

    QString url = GRAPH_ENDPOINT + "/me/drive/items/" + parentId + "/children";
    QJsonObject body;
    body["name"] = name;
    body["folder"] = QJsonObject();
    body["@microsoft.graph.conflictBehavior"] = "replace";
    
    int code;
    QByteArray resp = makeRequest("POST", url, QJsonDocument(body).toJson(), "application/json", &code);
    if (code == 201) {
        QJsonObject res = QJsonDocument::fromJson(resp).object();
        QString fullKey = m_remotePath.isEmpty() ? relPath : m_remotePath + "/" + relPath;
        m_remotePathToId[fullKey] = res["id"].toString();
        return true;
    }
    return false;
}

bool OneDriveSync::downloadFile(const QString &itemId, const QString &localDest) {
    checkStop();
    if (m_dryRun) { log("   [DRY RUN] DOWNLOAD: " + itemId); return true; }

    QDir().mkpath(QFileInfo(localDest).absolutePath());
    QString url = GRAPH_ENDPOINT + "/me/drive/items/" + itemId + "/content";
    QByteArray data = makeRequest("GET", url);
    
    QFile f(localDest);
    if (f.open(QIODevice::WriteOnly)) {
        f.write(data);
        f.close();
        return true;
    }
    return false;
}

bool OneDriveSync::deleteRemote(const QString &itemId, const QString &relPath) {
    checkStop();
    if (m_dryRun) { log("   [DRY RUN] DELETE REMOTE: " + relPath); return true; }
    
    QString url = GRAPH_ENDPOINT + "/me/drive/items/" + itemId;
    int code;
    makeRequest("DELETE", url, {}, "", &code);
    return (code == 204);
}