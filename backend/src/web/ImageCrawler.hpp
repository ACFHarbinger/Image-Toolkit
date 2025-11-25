#pragma once

#include <QObject>
#include <QFile>
#include <QDir>
#include <QJsonObject>
#include <QJsonArray>
#include "WebDriverClient.hpp"

#include <QObject>
#include <QWebEnginePage>
#include <QWebEngineProfile>
#include <QWebEngineSettings>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QEventLoop>
#include <QFile>
#include <QDir>
#include <QJsonObject>
#include <QJsonArray>
#include <QJsonDocument>

// === WebCrawler Base Class ===
class WebCrawler : public QObject {
    Q_OBJECT
public:
    explicit WebCrawler(const QJsonObject &config, QObject *parent = nullptr);
    virtual ~WebCrawler();

    // Replaces the Python abstract methods
    virtual void login() = 0;
    virtual void processData() = 0;

protected:
    // Helper to run JS synchronously (simulates Selenium's blocking behavior)
    QVariant evaluateJsSync(const QString &script);
    
    // Helper to load a URL and wait for it
    bool navigateToUrlSync(const QString &url);

    // Helper to wait
    void waitSeconds(int seconds);

    QWebEnginePage *m_page;
    QString m_downloadDir;
    QString m_screenshotDir;
    QNetworkAccessManager *m_netManager;
};

// === ImageCrawler Implementation ===
class ImageCrawler : public WebCrawler {
    Q_OBJECT
public:
    explicit ImageCrawler(const QJsonObject &config, QObject *parent = nullptr);
    void run();

signals:
    void onStatus(const QString &message);
    void onImageSaved(const QString &path);
    void finished();

private:
    void login() override;
    void processData() override;
    int processPage(const QString &url);
    bool runActionSequence(const QJsonArray &actions, const QString &originalTabId);
    bool downloadImage(const QString &url, QJsonObject &scrapedData);
    QString getUniqueFilename(const QString &filepath);
    void saveMetadata(const QString &baseFilename, const QJsonObject &data);

    // Configuration members
    QString m_targetUrl;
    QJsonObject m_loginConfig;
    QJsonArray m_actions;
    int m_skipFirst;
    int m_skipLast;
    QStringList m_urlsToScrape;
};