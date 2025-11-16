#pragma once

#include <QObject>
#include <QVariantMap>
#include <QString>

class GoogleDriveSyncWorker : public QObject
{
    Q_OBJECT

public:
    explicit GoogleDriveSyncWorker(
        const QVariantMap& authConfig,
        const QString& localPath, 
        const QString& remotePath, 
        bool dryRun, 
        const QString& userEmailToShareWith = QString(),
        QObject* parent = nullptr
    );

signals:
    void statusUpdate(const QString& message);
    void syncFinished(bool success, const QString& message);

public slots:
    void run();
    void stop();

private:
    void log(const QString& message);

    QVariantMap m_authConfig;
    QString m_authMode;
    QString m_localPath;
    QString m_remotePath;
    bool m_dryRun;
    QString m_shareEmail;
    bool m_isRunning;
};