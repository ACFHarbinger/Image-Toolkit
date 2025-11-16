#include "ImageScannerWorker.h"
#include <QDir>
#include <QDirIterator>
#include <QFileInfo>

// Define supported formats (assumed from Python's SUPPORTED_IMG_FORMATS)
const QStringList ImageScannerWorker::SUPPORTED_IMG_FORMATS = {
    "png", "jpg", "jpeg", "bmp", "webp", "gif"
};

ImageScannerWorker::ImageScannerWorker(const QString& directory, QObject* parent)
    : QObject(parent)
{
    // Handle single string input
    if (!directory.isEmpty() && QFileInfo(directory).isDir()) {
        m_directories.append(directory);
    }
}

ImageScannerWorker::ImageScannerWorker(const QStringList& directories, QObject* parent)
    : QObject(parent)
{
    // Filter out empty or non-directory entries
    for (const QString& dir : directories) {
        if (!dir.isEmpty() && QFileInfo(dir).isDir()) {
            m_directories.append(dir);
        }
    }
}

void ImageScannerWorker::runScan()
{
    QStringList imagePaths;
    
    // Create a set of lowercase suffixes, e.g., ".png"
    QSet<QString> supportedSuffixes;
    for (const QString& fmt : SUPPORTED_IMG_FORMATS) {
        supportedSuffixes.insert(QString(".%1").arg(fmt.toLower()));
    }

    if (m_directories.isEmpty()) {
        emit scanError("No valid directories provided for scanning.");
        return;
    }

    try {
        for (const QString& directory : m_directories) {
            // QDirIterator replaces os.walk
            QDirIterator it(directory, QDir::Files, QDirIterator::Subdirectories);
            while (it.hasNext()) {
                QString path = it.next();
                QString suffix = QFileInfo(path).suffix().toLower();
                
                if (!suffix.startsWith('.')) {
                    suffix.prepend('.');
                }

                if (supportedSuffixes.contains(suffix)) {
                    imagePaths.append(QDir::toNativeSeparators(path));
                }
            }
        }
        
        imagePaths.sort();
        emit scanFinished(imagePaths);
        
    } catch (const std::exception& e) {
        emit scanError(QString("Could not scan directory and subdirectories: %1").arg(e.what()));
    }
}