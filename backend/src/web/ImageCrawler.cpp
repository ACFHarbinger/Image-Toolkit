#include "ImageCrawler.hpp"
#include <QCoreApplication>
#include <QTimer>
#include <QStandardPaths>
#include <QFileInfo>
#include <iostream>

// ================= WebCrawler Base =================

WebCrawler::WebCrawler(const QJsonObject &config, QObject *parent)
    : QObject(parent) {
    
    // Initialize headless browser engine
    m_page = new QWebEnginePage(this);
    m_netManager = new QNetworkAccessManager(this);

    // Setup dirs
    m_downloadDir = config.value("download_dir").toString("downloads");
    m_screenshotDir = config.value("screenshot_dir").toString("screenshots");
    QDir().mkpath(m_downloadDir);
    QDir().mkpath(m_screenshotDir);
}

WebCrawler::~WebCrawler() {
    delete m_page;
}

QVariant WebCrawler::evaluateJsSync(const QString &script) {
    QEventLoop loop;
    QVariant result;
    // Inject JS and wait for callback
    m_page->runJavaScript(script, [&loop, &result](const QVariant &v) {
        result = v;
        loop.quit();
    });
    loop.exec();
    return result;
}

bool WebCrawler::navigateToUrlSync(const QString &url) {
    QEventLoop loop;
    QObject::connect(m_page, &QWebEnginePage::loadFinished, &loop, &QEventLoop::quit);
    m_page->setUrl(QUrl(url));
    loop.exec();
    return true; // Simplified success check
}

void WebCrawler::waitSeconds(int seconds) {
    QEventLoop loop;
    QTimer::singleShot(seconds * 1000, &loop, &QEventLoop::quit);
    loop.exec();
}

// ================= ImageCrawler Logic =================

ImageCrawler::ImageCrawler(const QJsonObject &config, QObject *parent)
    : WebCrawler(config, parent) {
    
    m_targetUrl = config.value("url").toString();
    m_loginConfig = config.value("login_config").toObject();
    m_actions = config.value("actions").toArray();
    m_skipFirst = config.value("skip_first").toInt(0);
    m_skipLast = config.value("skip_last").toInt(0);
    
    // Handle URL replacements if configured (Porting logic from Python)
    m_urlsToScrape.append(m_targetUrl);
    QString replaceStr = config.value("replace_str").toString();
    QJsonArray replacements = config.value("replacements").toArray();
    
    if (!replaceStr.isEmpty() && !replacements.isEmpty()) {
        for (const auto &rep : replacements) {
            QString newUrl = m_targetUrl;
            m_urlsToScrape.append(newUrl.replace(replaceStr, rep.toString()));
        }
    }
}

void ImageCrawler::run() {
    emit onStatus("Starting Crawler...");
    login();
    
    for (const QString &url : m_urlsToScrape) {
        processPage(url);
    }
    
    emit onStatus("Crawl Complete.");
    emit finished();
}

void ImageCrawler::login() {
    QString url = m_loginConfig.value("url").toString();
    QString user = m_loginConfig.value("username").toString();
    QString pass = m_loginConfig.value("password").toString();

    if (url.isEmpty() || user.isEmpty()) return;

    emit onStatus("Navigating to login page: " + url);
    navigateToUrlSync(url);

    // Logic: Fill fields using JS injection instead of Selenium find_element
    QString js = QString(
        "var u = document.querySelector('input[name*=\"user\"], input[type=\"email\"]');"
        "if(u) { u.value = '%1'; u.dispatchEvent(new Event('input')); }"
        "var p = document.querySelector('input[name*=\"pass\"], input[type=\"password\"]');"
        "if(p) { p.value = '%2'; p.dispatchEvent(new Event('input')); }"
        "var btn = document.querySelector('input[type=\"submit\"], button');"
        "if(btn) { btn.click(); }"
    ).arg(user, pass);

    evaluateJsSync(js);
    emit onStatus("Credentials submitted. Waiting for redirect...");
    waitSeconds(5); // Wait for login processing
}

int ImageCrawler::processPage(const QString &url) {
    emit onStatus("Processing Page: " + url);
    navigateToUrlSync(url);
    waitSeconds(2); // Wait for dynamic content

    // Get number of images via JS
    int totalImages = evaluateJsSync("document.getElementsByTagName('img').length").toInt();
    emit onStatus(QString("Found %1 images.").arg(totalImages));

    int count = 0;
    int endIndex = totalImages - m_skipLast;

    for (int i = m_skipFirst; i < endIndex; ++i) {
        // In C++, we can't pass a generic "WebElement" object around easily like in Python.
        // Instead, we mark the 'current' element in the JS context using a global var.
        QString selectJs = QString("window.__currentImg = document.getElementsByTagName('img')[%1];").arg(i);
        evaluateJsSync(selectJs);

        // Run actions on window.__currentImg
        if (runActionSequence(m_actions, "main")) {
            count++;
        }
    }
    return count;
}

bool ImageCrawler::runActionSequence(const QJsonArray &actions, const QString &originalTabId) {
    bool downloaded = false;
    QJsonObject scrapedData;

    for (const auto &val : actions) {
        QJsonObject action = val.toObject();
        QString type = action.value("type").toString();
        QVariant param = action.value("param").toVariant();

        emit onStatus("Action: " + type);

        if (type == "Download Simple Thumbnail (Legacy)" || type == "Download Image from Element") {
            QString src = evaluateJsSync("window.__currentImg ? window.__currentImg.src : ''").toString();
            if (!src.isEmpty()) {
                downloaded = downloadImage(src, scrapedData);
            }
        }
        else if (type == "Wait X Seconds") {
            waitSeconds(param.toInt());
        }
        else if (type == "Click Element by Text") {
             // Complex JS logic to find element by text and click
             QString js = QString(
                 "var el = Array.from(document.querySelectorAll('a, button')).find(el => el.textContent.includes('%1'));"
                 "if(el) { el.click(); }"
             ).arg(param.toString());
             evaluateJsSync(js);
        }
        else if (type == "Find Parent Link (<a>)") {
            evaluateJsSync("if(window.__currentImg) { window.__currentImg = window.__currentImg.closest('a'); }");
        }
        // Additional actions can be ported here...
    }
    return downloaded;
}

bool ImageCrawler::downloadImage(const QString &url, QJsonObject &scrapedData) {
    QUrl target(url);
    if (!target.isValid()) return false;

    QEventLoop loop;
    QNetworkRequest request(target);
    request.setHeader(QNetworkRequest::UserAgentHeader, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...");
    
    QNetworkReply *reply = m_netManager->get(request);
    QObject::connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
    loop.exec();

    if (reply->error() == QNetworkReply::NoError) {
        QString filename = QFileInfo(target.path()).fileName();
        if (filename.isEmpty()) filename = "image_" + QString::number(QDateTime::currentMSecsSinceEpoch()) + ".jpg";
        
        QString savePath = m_downloadDir + "/" + filename;
        savePath = getUniqueFilename(savePath);

        QFile file(savePath);
        if (file.open(QIODevice::WriteOnly)) {
            file.write(reply->readAll());
            file.close();
            emit onImageSaved(savePath);
            
            scrapedData["image_filename"] = QFileInfo(savePath).fileName();
            saveMetadata(savePath, scrapedData); // Save JSON like Python version
            
            reply->deleteLater();
            return true;
        }
    }
    
    emit onStatus("Download Failed: " + url);
    reply->deleteLater();
    return false;
}

QString ImageCrawler::getUniqueFilename(const QString &filepath) {
    // Port of Python's get_unique_filename
    QString finalPath = filepath;
    int counter = 1;
    QFileInfo fi(filepath);
    
    while (QFile::exists(finalPath)) {
        finalPath = QString("%1/%2 (%3).%4")
            .arg(fi.absolutePath())
            .arg(fi.baseName())
            .arg(counter++)
            .arg(fi.suffix());
    }
    return finalPath;
}

void ImageCrawler::saveMetadata(const QString &baseFilename, const QJsonObject &data) {
    if (data.isEmpty()) return;
    
    QFileInfo fi(baseFilename);
    QString jsonPath = fi.absolutePath() + "/" + fi.baseName() + ".json";
    
    QFile file(jsonPath);
    if (file.open(QIODevice::WriteOnly)) {
        file.write(QJsonDocument(data).toJson());
        file.close();
    }
}