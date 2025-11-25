#pragma once

#include <QObject>
#include <QString>
#include <functional>
#include <QDir>
#include <QDirIterator>
#include <QDateTime>
#include <QMap>
#include <QVariant>
#include <iostream>

// Structure to hold file metadata
struct FileMetadata {
    QString id;
    QString path; // Absolute for local, relative/id for remote
    qint64 mtime = 0;
    bool isFolder = false;
};

class AbstractSync : public QObject {
    Q_OBJECT
public:
    using Logger = std::function<void(const QString&)>;

    AbstractSync(const QString &localPath, const QString &remotePath, 
                 bool dryRun, Logger logger, 
                 const QString &actionLocal, const QString &actionRemote, QObject *parent = nullptr)
        : QObject(parent), m_localPath(localPath), m_remotePath(remotePath),
          m_dryRun(dryRun), m_logger(logger), 
          m_actionLocal(actionLocal), m_actionRemote(actionRemote) {}

    virtual ~AbstractSync() {}

    // Main entry point
    virtual void executeSync() = 0;

    // Stop signal
    void stop() { m_isRunning = false; }

protected:
    QString m_localPath;
    QString m_remotePath;
    bool m_dryRun;
    Logger m_logger;
    QString m_actionLocal;  // "upload", "delete_local", "ignore_local"
    QString m_actionRemote; // "download", "delete_remote", "ignore_remote"
    volatile bool m_isRunning = true;

    void log(const QString &msg) {
        if (m_logger) m_logger(msg);
        else std::cout << msg.toStdString() << std::endl;
    }

    void checkStop() {
        if (!m_isRunning) throw std::runtime_error("Synchronization manually interrupted.");
    }

    // Common Local Scanner
    QMap<QString, FileMetadata> scanLocalFiles() {
        QMap<QString, FileMetadata> items;
        QDir dir(m_localPath);
        if (!dir.exists()) return items;

        int baseLen = m_localPath.length();
        if (!m_localPath.endsWith('/')) baseLen++;

        QDirIterator it(m_localPath, QDir::Files | QDir::Dirs | QDir::NoDotAndDotDot, QDirIterator::Subdirectories);
        while (it.hasNext()) {
            checkStop();
            it.next();
            QString absPath = it.filePath();
            QString relPath = absPath.mid(baseLen);
            
            FileMetadata meta;
            meta.path = absPath;
            meta.isFolder = it.fileInfo().isDir();
            meta.mtime = it.fileInfo().lastModified().toSecsSinceEpoch();
            
            items.insert(relPath, meta);
        }
        return items;
    }
    
    // Helper to delete local files recursively
    bool deleteLocal(const QString &absPath) {
        checkStop();
        if (m_dryRun) {
            log("   [DRY RUN] DELETE LOCAL: " + absPath);
            return true;
        }
        QFileInfo fi(absPath);
        if (fi.isDir()) return QDir(absPath).removeRecursively();
        return QFile::remove(absPath);
    }
};