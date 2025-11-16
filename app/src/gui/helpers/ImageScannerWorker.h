#pragma once

#include <QObject>
#include <QStringList>

class ImageScannerWorker : public QObject
{
    Q_OBJECT

public:
    // Handle both single string and list inputs, as in the Python file
    explicit ImageScannerWorker(const QString& directory, QObject* parent = nullptr);
    explicit ImageScannerWorker(const QStringList& directories, QObject* parent = nullptr);

signals:
    void scanFinished(const QStringList& imagePaths);
    void scanError(const QString& error);

public slots:
    void runScan(); // Renamed from run_scan

private:
    QStringList m_directories;
    const static QStringList SUPPORTED_IMG_FORMATS;
};