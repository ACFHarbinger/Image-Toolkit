#pragma once

#include <QObject>
#include <QStringList>
#include <QPixmap>

class BatchThumbnailLoaderWorker : public QObject
{
    Q_OBJECT

public:
    explicit BatchThumbnailLoaderWorker(const QStringList& paths, int size, QObject* parent = nullptr);

signals:
    // Signal to create placeholder on main thread
    void createPlaceholder(int index, const QString& path);
    // Signal with the loaded thumbnail
    void thumbnailLoaded(int index, const QPixmap& pixmap, const QString& path);
    // Signal when all images are processed
    void loadingFinished();

public slots:
    void runLoadBatch(); // Renamed from run_load_batch

private:
    QStringList m_paths;
    int m_size;
};