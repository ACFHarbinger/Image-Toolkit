#include "GoogleDriveSync.hpp"
#include <QUrlQuery>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QNetworkReply>
#include <QEventLoop>

const QString G_API = "https://www.googleapis.com/drive/v3/files";
const QString G_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart";

GoogleDriveSync::GoogleDriveSync(const QString &localPath, const QString &remoteFolderName,
                                 const QJsonObject &saData, bool dryRun, Logger logger,
                                 const QString &actionLocal, const QString &actionRemote,
                                 QObject *parent)
    : AbstractSync(localPath, remoteFolderName, dryRun, logger, actionLocal, actionRemote, parent),
      m_saData(saData) {
    m_nam = new QNetworkAccessManager(this);
}

void GoogleDriveSync::executeSync() {
    try {
        checkStop();
        // In a real C++ app, you'd use a JWT library here to exchange m_saData key for a token.
        // For this port, we assume the user provides a token or authentication logic is external.
        if (m_accessToken.isEmpty()) {
            log("⚠️  Skipping Google Sync: JWT Auth logic required (requires OpenSSL dependency).");
            return;
        }

        log("🔍 Resolving Destination ID...");
        m_destFolderId = findOrCreateFolder(m_remotePath);

        log("📋 Scanning...");
        auto localItems = scanLocalFiles();
        auto remoteItems = scanRemoteFiles();

        // Sync Logic matches the Python abstract logic
        // ... (Loop over localItems and remoteItems)

    } catch (const std::exception &e) {
        log(QString("❌ Error: %1").arg(e.what()));
    }
}

QByteArray GoogleDriveSync::apiRequest(const QString &verb, const QString &endpoint, 
                                       const QByteArray &data, const QString &contentType) {
    QNetworkRequest req(QUrl(endpoint));
    req.setRawHeader("Authorization", ("Bearer " + m_accessToken).toUtf8());
    if (!data.isEmpty()) req.setHeader(QNetworkRequest::ContentTypeHeader, contentType);

    QNetworkReply *reply = nullptr;
    if (verb == "GET") reply = m_nam->get(req);
    else if (verb == "POST") reply = m_nam->post(req, data);
    else if (verb == "DELETE") reply = m_nam->deleteResource(req);

    QEventLoop loop;
    connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
    loop.exec();

    QByteArray res = reply->readAll();
    reply->deleteLater();
    return res;
}

QMap<QString, FileMetadata> GoogleDriveSync::scanRemoteFiles() {
    QMap<QString, FileMetadata> items;
    if (m_destFolderId.isEmpty()) return items;

    struct QueueItem { QString id; QString relPath; };
    QList<QueueItem> queue;
    queue.append({m_destFolderId, ""});

    while (!queue.isEmpty()) {
        checkStop();
        QueueItem current = queue.takeFirst();
        
        QString query = QString("'%1' in parents and trashed=false").arg(current.id);
        QUrl url(G_API);
        QUrlQuery q;
        q.addQueryItem("q", query);
        q.addQueryItem("fields", "files(id, name, mimeType)");
        url.setQuery(q);

        QByteArray json = apiRequest("GET", url.toString());
        QJsonObject root = QJsonDocument::fromJson(json).object();
        QJsonArray files = root["files"].toArray();

        for (const auto &val : files) {
            QJsonObject f = val.toObject();
            QString name = f["name"].toString();
            QString id = f["id"].toString();
            bool isFolder = (f["mimeType"].toString() == "application/vnd.google-apps.folder");
            QString relPath = current.relPath.isEmpty() ? name : current.relPath + "/" + name;

            FileMetadata meta;
            meta.id = id;
            meta.isFolder = isFolder;
            items.insert(relPath, meta);

            if (isFolder) queue.append({id, relPath});
        }
    }
    return items;
}

// Helper to find folder ID by path traversal
QString GoogleDriveSync::findOrCreateFolder(const QString &path) {
    if (path.isEmpty()) return "root";
    // Logic: Split path, query children of 'root', create if missing, iterate.
    // ... Implementation similar to Python _find_or_create_destination_folder ...
    return ""; // Placeholder
}