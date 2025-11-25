#pragma once

#include "AbstractCloudSync.hpp"
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QEventLoop>

class OneDriveSync : public AbstractSync {
    Q_OBJECT
public:
    OneDriveSync(const QString &localPath, const QString &remoteFolderName,
                 const QString &clientId, const QString &token, // Assuming pre-acquired token for simplicity
                 bool dryRun, Logger logger,
                 const QString &actionLocal, const QString &actionRemote,
                 QObject *parent = nullptr);

    void executeSync() override;

private:
    QString m_accessToken;
    QNetworkAccessManager *m_nam;
    QMap<QString, QString> m_remotePathToId; // Cache path -> ID

    // API Wrappers
    QMap<QString, FileMetadata> scanRemoteFiles();
    QString resolvePathToId(const QString &path);
    bool uploadFile(const QString &localPath, const QString &relPath);
    bool createRemoteFolder(const QString &relPath);
    bool downloadFile(const QString &itemId, const QString &localDest);
    bool deleteRemote(const QString &itemId, const QString &relPath);

    // Network Helper
    QByteArray makeRequest(const QString &verb, const QString &url, 
                           const QByteArray &data = QByteArray(), 
                           const QString &contentType = "application/json",
                           int *statusCode = nullptr);
};