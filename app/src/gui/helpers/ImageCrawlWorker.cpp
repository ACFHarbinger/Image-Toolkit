#include "ImageCrawlWorker.h"
#include "web/ImageCrawler.h" // Assumed C++ equivalent
#include <QDir>
#include <QFileInfo>

ImageCrawlWorker::ImageCrawlWorker(const QVariantMap& config, QObject* parent)
    : QThread(parent), m_config(config), m_crawler(nullptr), m_downloaded(0)
{
}

ImageCrawlWorker::~ImageCrawlWorker()
{
    // Ensure crawler is deleted if it was created
    delete m_crawler;
}

void ImageCrawlWorker::run()
{
    try {
        // Create directories
        QDir().mkpath(m_config["download_dir"].toString());
        QString screenshotDir = m_config["screenshot_dir"].toString();
        if (!screenshotDir.isEmpty()) {
            QDir().mkpath(screenshotDir);
        }
            
        m_crawler = new ImageCrawler(
            m_config["url"].toString(),
            m_config["headless"].toBool(),
            m_config["download_dir"].toString(),
            m_config["browser"].toString(),
            screenshotDir, 
            m_config["skip_first"].toInt(),
            m_config["skip_last"].toInt(),
            nullptr // Create with no parent, will be managed by this thread
        );

        // C++ lambda to replace 'nonlocal'
        auto on_saved = [this](const QString& path) {
            m_downloaded += 1;
            emit status(QString("Saved: %1").arg(QFileInfo(path).fileName()));
        };

        connect(m_crawler, &ImageCrawler::onProgress, this, &ImageCrawlWorker::progress);
        connect(m_crawler, &ImageCrawler::onStatus, this, &ImageCrawlWorker::status);
        connect(m_crawler, &ImageCrawler::onImageSaved, this, on_saved);

        emit status("Starting crawl...");
        m_crawler->run();

        emit finished(m_downloaded, QString("Downloaded %1 image(s)!").arg(m_downloaded));

        delete m_crawler; // Clean up
        m_crawler = nullptr;

    } catch (const std::exception& e) {
        emit error(e.what());
        delete m_crawler; // Clean up on error
        m_crawler = nullptr;
    }
}