#pragma once

#include <QThread>
#include <QVariantMap>

// Forward-declare the crawler class
class ImageCrawler;

class ImageCrawlWorker : public QThread
{
    Q_OBJECT

public:
    explicit ImageCrawlWorker(const QVariantMap& config, QObject* parent = nullptr);
    ~ImageCrawlWorker();

signals:
    void progress(int current, int total);
    void status(const QString& message);
    void finished(int count, const QString& message);
    void error(const QString& message);

protected:
    void run() override;

private:
    QVariantMap m_config;
    ImageCrawler* m_crawler; // Keep a pointer to delete it
    int m_downloaded; // Member to be modified by lambda
};