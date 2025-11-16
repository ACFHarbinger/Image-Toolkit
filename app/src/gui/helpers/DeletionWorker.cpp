#include "DeletionWorker.h"
#include "core/FSETool.h" // Assumed C++ equivalent
#include "core/FileDeleter.h" // Assumed C++ equivalent
#include <QFileInfo>
#include <QDir>
#include <QSet>

// Define supported formats (assumed from Python)
const QStringList DeletionWorker::SUPPORTED_IMG_FORMATS = {
    "png", "jpg", "jpeg", "bmp", "webp", "gif"
};

DeletionWorker::DeletionWorker(const QVariantMap& config, QObject* parent)
    : QThread(parent), m_config(config), m_confirmationResponse(false)
{
}

void DeletionWorker::setConfirmationResponse(bool response)
{
    QMutexLocker locker(&m_mutex);
    m_confirmationResponse = response;
    m_waitCondition.wakeOne();
}

void DeletionWorker::run()
{
    try {
        QString targetPath = m_config["target_path"].toString();
        QString mode = m_config.value("mode", "files").toString();
        bool requireConfirm = m_config["require_confirm"].toBool();

        if (targetPath.isEmpty() || !QFileInfo::exists(targetPath)) {
            emit error("Target path does not exist.");
            return;
        }

        // --- DIRECTORY DELETION MODE ---
        if (mode == "directory") {
            if (!QFileInfo(targetPath).isDir()) {
                emit error(QString("Error: Target path is not a directory: %1").arg(targetPath));
                return;
            }
            
            if (requireConfirm) {
                QString msg = QString("Permanently delete the directory and all its contents: \n\n%1\n\nThis cannot be undone!").arg(targetPath);
                
                m_mutex.lock();
                emit confirmSignal(msg, 1);
                m_waitCondition.wait(&m_mutex);
                m_mutex.unlock();

                if (!m_confirmationResponse) {
                    emit finished(0, "Directory deletion cancelled by user.");
                    return;
                }
            }

            emit progress(0, 1);
            
            if (FileDeleter::deletePath(targetPath)) {
                emit finished(1, QString("Successfully deleted directory and its contents: %1").arg(targetPath));
            } else {
                emit error(QString("Failed to delete directory %1").arg(targetPath));
            }
            return; 
        }

        // --- FILE DELETION MODE ---
        QStringList extensions = m_config["target_extensions"].toStringList();
        if (extensions.isEmpty()) {
            extensions = SUPPORTED_IMG_FORMATS;
        }
        
        QSet<QString> exts;
        for (const QString& ext : extensions) {
            exts.insert(QString(".%1").arg(ext.remove(0, 1).toLower()));
        }
        
        QSet<QString> filesToDeleteSet;
        QFileInfo targetInfo(targetPath);
        
        if (targetInfo.isFile()) {
            QString suffix = targetInfo.suffix().toLower();
            if (!suffix.startsWith('.')) suffix.prepend('.');
            if (exts.contains(suffix)) {
                filesToDeleteSet.insert(targetPath);
            }
        } else {
            // Recursively search the directory
            for (const QString& ext : extensions) {
                QStringList files = FSETool::getFilesByExtension(targetPath, ext, true);
                filesToDeleteSet.unite(QSet<QString>(files.begin(), files.end()));
            }
        }

        QStringList filesToDelete = QList<QString>::fromSet(filesToDeleteSet);
        filesToDelete.sort();

        int total = filesToDelete.length();
        if (total == 0) {
            emit finished(0, "No files found matching the selected extensions.");
            return;
        }

        if (requireConfirm) {
            QString msg = QString("Permanently delete %1 file(s) matching extensions?\n\nThis cannot be undone!").arg(total);
            
            m_mutex.lock();
            emit confirmSignal(msg, total);
            m_waitCondition.wait(&m_mutex);
            m_mutex.unlock();

            if (!m_confirmationResponse) {
                emit finished(0, "Deletion cancelled by user.");
                return;
            }
        }

        int deleted = 0;
        for (const QString& filePath : filesToDelete) {
            if (FileDeleter::deletePath(filePath)) {
                deleted += 1;
            }
            emit progress(deleted, total);
        }
        
        emit finished(deleted, QString("Deleted %1 file(s).").arg(deleted));
        
    } catch (const std::exception& e) {
        emit error(e.what());
    }
}