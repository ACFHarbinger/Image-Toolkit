#pragma once

#include "AbstractCloudSync.hpp"
#include <QNetworkAccessManager>

class DropboxSync : public AbstractSync {
    Q_OBJECT
public:
    DropboxSync(const QString &localPath, const QString &remoteFolderName,
                const QString &token, bool dryRun, Logger logger,
                const QString &actionLocal, const QString &actionRemote,
                QObject *parent = nullptr);

    void executeSync() override;

private:
    QString m_accessToken;
    QNetworkAccessManager *m_nam;

    QMap<QString, FileMetadata> scanRemoteFiles();
    bool uploadFile(const QString &localPath, const QString &relPath);
    bool createRemoteFolder(const QString &relPath);
    bool downloadFile(const QString &remotePath, const QString &localDest);
    bool deleteRemote(const QString &remotePath);

    QByteArray rpcRequest(const QString &endpoint, const QJsonObject &args, 
                          const QByteArray &data = QByteArray(), bool isContent = false);
};