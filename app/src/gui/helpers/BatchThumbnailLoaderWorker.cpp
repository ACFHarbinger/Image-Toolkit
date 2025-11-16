#include "BatchThumbnailLoaderWorker.h"

BatchThumbnailLoaderWorker::BatchThumbnailLoaderWorker(const QStringList& paths, int size, QObject* parent)
    : QObject(parent), m_paths(paths), m_size(size)
{
}

void BatchThumbnailLoaderWorker::runLoadBatch()
{
    for (int i = 0; i < m_paths.size(); ++i) {
        const QString& path = m_paths.at(i);
        try {
            // 1. Notify main thread to create placeholder
            emit createPlaceholder(i, path);

            // 2. Load the image
            QPixmap pixmap(path);

            if (!pixmap.isNull()) {
                // 3. Scale the QPixmap
                QPixmap scaled = pixmap.scaled(
                    m_size, m_size,
                    Qt::KeepAspectRatio, Qt::SmoothTransformation
                );
                // 4. Emit the result
                emit thumbnailLoaded(i, scaled, path);
            } else {
                // Emit empty pixmap on load errors
                emit thumbnailLoaded(i, QPixmap(), path);
            }

        } catch (const std::exception&) {
            // Emit empty pixmap on unexpected error
            emit thumbnailLoaded(i, QPixmap(), path);
        }
    }
    
    // 5. Signal finish
    emit loadingFinished();
}