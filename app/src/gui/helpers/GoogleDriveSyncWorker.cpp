#include "GoogleDriveSyncWorker.h"
#include "web/google_drive_sync.h" // Assumed C++ equivalent
#include <QDateTime>
#include <QPair> // For the return value

GoogleDriveSyncWorker::GoogleDriveSyncWorker(
    const QVariantMap& authConfig,
    const QString& localPath, 
    const QString& remotePath, 
    bool dryRun, 
    const QString& userEmailToShareWith,
    QObject* parent
)
    : QObject(parent),
      m_authConfig(authConfig),
      m_localPath(localPath),
      m_remotePath(remotePath),
      m_dryRun(dryRun),
      m_shareEmail(userEmailToShareWith),
      m_isRunning(true)
{
    m_authMode = m_authConfig.value("mode", "unknown").toString();
}

void GoogleDriveSyncWorker::log(const QString& message)
{
    if (m_isRunning) {
        QString timestamp = QDateTime::currentDateTime().toString("[HH:mm:ss]");
        emit statusUpdate(QString("%1 %2").arg(timestamp, message));
    }
}

void GoogleDriveSyncWorker::run()
{
    emit statusUpdate("\n" + QString("=").repeated(50));
    log(QString("--- Google Drive Sync Initiated ---"));
    log(QString("Authentication Mode: %1").arg(m_authMode.toUpper()));
    log(QString("Sync Mode: %1").arg(m_dryRun ? "DRY RUN" : "LIVE"));
    emit statusUpdate(QString("=").repeated(50) + "\n");

    bool success = false;
    QString finalMessage = "Cancelled by user.";
    GoogleDriveSync* syncManager = nullptr;
    
    // Logger function (C++ lambda)
    auto logger = [this](const QString& msg){ this->log(msg); };

    try {
        if (m_authMode == "service_account") {
            syncManager = new GoogleDriveSync(
                m_localPath,
                m_remotePath,
                m_dryRun,
                logger,
                m_authConfig.value("key_file").toString(),
                m_shareEmail
            );
        } else if (m_authMode == "personal_account") {
             syncManager = new GoogleDriveSync(
                m_localPath,
                m_remotePath,
                m_dryRun,
                logger,
                m_authConfig.value("client_secrets_file").toString(),
                m_authConfig.value("token_file").toString()
            );
        } else {
             throw std::runtime_error(QString("Unsupported authentication mode: %1").arg(m_authMode).toStdString());
        }

        if (m_isRunning) {
            QPair<bool, QString> result = syncManager->execute_sync();
            success = result.first;
            finalMessage = result.second;
        }
        
    } catch (const std::exception& e) {
        success = false;
        finalMessage = QString("Critical error: %1").arg(e.what());
        log(QString("ERROR: %1").arg(finalMessage));
    }
    
    delete syncManager; // Clean up
    syncManager = nullptr;

    if (!m_isRunning && success) {
        success = false;
        finalMessage = "Synchronization manually cancelled.";
    }

    if (m_isRunning) {
        emit syncFinished(success, finalMessage);
    }
}

void GoogleDriveSyncWorker::stop()
{
    if (m_isRunning) {
        m_isRunning = false;
        emit statusUpdate("\n!!! SYNCHRONIZATION INTERRUPTED !!!");
    }
}