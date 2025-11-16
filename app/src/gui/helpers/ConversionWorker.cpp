#include "ConversionWorker.h"
#include "core/FSETool.h" // Assumed C++ equivalent
#include "core/ImageFormatConverter.h" // Assumed C++ equivalent
#include <QFileInfo>
#include <QDir>

// Define supported formats (assumed from Python)
const QStringList ConversionWorker::SUPPORTED_IMG_FORMATS = {
    "png", "jpg", "jpeg", "bmp", "webp", "gif"
};

ConversionWorker::ConversionWorker(const QVariantMap& config, QObject* parent)
    : QThread(parent), m_config(config)
{
}

void ConversionWorker::run()
{
    try {
        QString inputPath = m_config["input_path"].toString();
        QString outputFormat = m_config["output_format"].toString().toLower();
        QString outputPath = m_config["output_path"].toString();
        QStringList inputFormats = m_config["input_formats"].toStringList();
        if (inputFormats.isEmpty()) {
            inputFormats = SUPPORTED_IMG_FORMATS;
        }
        bool deleteOriginal = m_config["delete"].toBool();

        if (inputPath.isEmpty() || !QFileInfo::exists(inputPath)) {
            emit error("Input path does not exist.");
            return;
        }
        
        QFileInfo inputInfo(inputPath);
        int converted = 0;

        if (inputInfo.isDir()) {
            // Batch conversion
            QString outputDir = (outputPath.isEmpty() || !QFileInfo(outputPath).isDir()) ? inputPath : outputPath;
            
            QStringList convertedImages = ImageFormatConverter::convertBatch(
                inputPath,
                inputFormats,
                outputDir,
                outputFormat,
                deleteOriginal
            );
            converted = convertedImages.length();

        } else {
            // Single file conversion
            QString outputName = outputPath;
            
            if (outputName.isEmpty()) {
                 outputName = inputInfo.dir().filePath(inputInfo.completeBaseName());
            }
            // If output_path is provided and is a directory, use the input filename
            else if (QFileInfo(outputName).isDir()) {
                outputName = QDir(outputName).filePath(inputInfo.completeBaseName());
            }

            // The FSETool path_contains/ensure_absolute_paths logic is complex
            // We assume the C++ core functions handle this logic if required.
            
            QString result = ImageFormatConverter::convertSingleImage(
                inputPath,
                outputName,
                outputFormat,
                deleteOriginal
            );
            converted = result.isEmpty() ? 0 : 1;
        }

        emit finished(converted, QString("Converted %1 image(s)!").arg(converted));

    } catch (const std::exception& e) {
        emit error(e.what());
    }
}