#include "WallpaperWorker.h"
#include "core/WallpaperManager.h" // Assumed C++ equivalent header
#include <QDateTime>
#include <QScreen>

WallpaperWorker::WallpaperWorker(const QMap<QString, QString>& pathMap,
                                 const QList<QScreen*>& monitors,
                                 QObject* parent)
    : QObject(parent), m_pathMap(pathMap), m_monitors(monitors), m_isRunning(true)
{
    // C++ import check is at compile-time
}

void WallpaperWorker::log(const QString& message)
{
    if (m_isRunning) {
        QString timestamp = QDateTime::currentDateTime().toString("[HH:mm:ss]");
        emit statusUpdate(QString("%1 %2").arg(timestamp, message));
    }
}

void WallpaperWorker::run()
{
    if (!m_isRunning) {
        return;
    }

    log("Wallpaper set worker started...");
    bool success = false;
    QString message = "Worker did not run.";

    try {
        // --- Main Task ---
        WallpaperManager::applyWallpaper(m_pathMap, m_monitors);

        if (!m_isRunning) {
            // Check if stop() was called during the blocking call
            throw InterruptedError();
        }

        success = true;
        message = "Wallpaper applied successfully.";

    } catch (const InterruptedError& e) {
        success = false;
        message = e.what();
        log(QString("Warning: %1").arg(message));
    } catch (const std::exception& e) {
        success = false;
        message = QString("Critical error: %1").arg(e.what());
        log(QString("ERROR: %1").arg(message));
    }

    // "finally" block
    if (m_isRunning) {
        log(QString("Worker finished. Success: %1").arg(success));
        emit workFinished(success, message);
    }
}

void WallpaperWorker::stop()
{
    if (m_isRunning) {
        m_isRunning = false;
        log("Stop signal received. Worker will terminate.");
    }
}