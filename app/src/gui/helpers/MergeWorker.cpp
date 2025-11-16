#include "MergeWorker.h"
#include "core/FSETool.h" // Assumed C++ equivalent
#include "core/ImageMerger.h" // Assumed C++ equivalent
#include <QStringList>
#include <QFileInfo>
#include <QSet> // For removing duplicates

// Define supported formats (assumed from Python)
const QStringList MergeWorker::SUPPORTED_IMG_FORMATS = {
    "png", "jpg", "jpeg", "bmp", "webp", "gif"
};

MergeWorker::MergeWorker(const QVariantMap& config, QObject* parent)
    : QThread(parent), m_config(config)
{
}

void MergeWorker::run()
{
    try {
        QStringList inputPaths = m_config["input_path"].toStringList();
        QString outputPath = m_config["output_path"].toString();
        QString direction = m_config["direction"].toString();
        int spacing = m_config["spacing"].toInt();
        int gridSize = m_config["grid_size"].toInt();
        QStringList formats = m_config["input_formats"].toStringList();
        if (formats.isEmpty()) {
            formats = SUPPORTED_IMG_FORMATS;
        }
        
        // 1. Resolve all image files
        QSet<QString> imageFileSet;
        for (const QString& path : inputPaths) {
            QFileInfo info(path);
            if (info.isFile()) {
                QString suffix = info.suffix().toLower();
                if (formats.contains(suffix)) {
                    imageFileSet.insert(path);
                }
            } else if (info.isDir()) {
                for (const QString& fmt : formats) {
                    QStringList files = FSETool::getFilesByExtension(path, fmt, false);
                    imageFileSet.unite(QSet<QString>(files.begin(), files.end()));
                }
            }
        }
        
        // Remove duplicates and sort
        QStringList imageFiles = QList<QString>::fromSet(imageFileSet);
        imageFiles.sort();

        if (imageFiles.isEmpty()) {
            emit error("No images found to merge.");
            return;
        }
        if (imageFiles.length() < 2) {
            emit error("Need at least 2 images to merge.");
            return;
        }

        // 2. Progress update
        emit progress(0, imageFiles.length());

        // 3. Perform merge
        ImageMerger::mergeImages(
            imageFiles,
            outputPath,
            direction,
            gridSize,
            spacing
        );
        
        // 4. Final progress update
        emit progress(imageFiles.length(), imageFiles.length());
        
        // 5. Emit output path
        emit finished(outputPath);

    } catch (const std::exception& e) {
        emit error(QString("Merge failed: %1").arg(e.what()));
    }
}