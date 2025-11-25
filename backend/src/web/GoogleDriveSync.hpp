#pragma once

#include "AbstractCloudSync.hpp"
#include <QNetworkAccessManager>

class GoogleDriveSync : public AbstractSync {
    Q_OBJECT
public:
    GoogleDriveSync(const QString &localPath, const QString &remoteFolderName,
                    const QJsonObject &saData, bool dryRun, Logger logger,
                    const QString &actionLocal, const QString &actionRemote,
                    QObject *parent = nullptr);

    void executeSync() override;

private:
    QJsonObject m_saData;
    QString m_accessToken;
    QNetworkAccessManager *m_nam;
    QMap<QString, QString> m_remotePathToId;
    QString m_destFolderId;

    bool authenticateServiceAccount(); // JWT creation is complex in C++, often requires OpenSSL
    // Helper API
    QByteArray apiRequest(const QString &verb, const QString &endpoint, 
                          const QByteArray &data = QByteArray(), const QString &contentType = "application/json");
    
    QString findOrCreateFolder(const QString &path);
    QMap<QString, FileMetadata> scanRemoteFiles();
    // ... Upload/Download methods similar to OneDrive
};