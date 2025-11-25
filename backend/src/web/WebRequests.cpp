#include "WebRequests.hpp"
#include <QTimer>
#include <QFile>
#include <QDir>
#include <QDateTime>
#include <QDebug>
#include <QUrlQuery>

WebRequestsLogic::WebRequestsLogic(const QJsonObject &config, QObject *parent)
    : QObject(parent), m_config(config) {
    
    m_netManager = new QNetworkAccessManager(this);
    
    // Parse configuration
    m_baseUrl = config.value("base_url").toString();
    m_requestList = config.value("requests").toArray();
    m_actionList = config.value("actions").toArray();
}

Q_SLOT void WebRequestsLogic::stop() {
    m_isRunning = false;
    emit onStatus("Cancellation pending...");
}

void WebRequestsLogic::waitSeconds(double seconds) {
    QEventLoop loop;
    QTimer::singleShot(static_cast<int>(seconds * 1000), &loop, &QEventLoop::quit);
    loop.exec();
}

QUrl WebRequestsLogic::encodeUrl(const QString &path) const {
    // Correctly join path to base URL
    QUrl url = m_baseUrl;
    if (!path.isEmpty()) {
        url = url.resolved(QUrl(path));
    }
    return url;
}

QByteArray WebRequestsLogic::createPostData(const QString &paramStr) const {
    // Converts 'key:val, k2:v2' into QUrlQuery for POST data (application/x-www-form-urlencoded)
    if (paramStr.isEmpty()) {
        return QByteArray();
    }
    
    QUrlQuery postData;
    QStringList pairs = paramStr.split(',');
    
    for (const QString &pair : pairs) {
        if (pair.contains(':')) {
            QStringList parts = pair.split(':', Qt::SkipEmptyParts);
            if (parts.size() == 2) {
                postData.addQueryItem(parts[0].trimmed(), parts[1].trimmed());
            }
        } else {
            // Emit error if format is invalid
            emit onError(QString("Invalid POST data format: '%1'. Skipping.").arg(pair));
        }
    }
    return postData.toString(QUrl::FullyEncoded).toUtf8();
}

void WebRequestsLogic::runActions(QNetworkReply *reply) {
    // Check for HTTP errors before running actions, mirroring Python's raise_for_status()
    if (reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt() >= 400) {
        return;
    }
    
    for (const QJsonValue &actionValue : m_actionList) {
        if (!m_isRunning) return;

        QJsonObject action = actionValue.toObject();
        QString type = action.value("type").toString();
        QString param = action.value("param").toString();

        try {
            if (type == "Print Response URL") {
                emit onStatus(QString("  > Action: Response URL: %1").arg(reply->url().toString()));
            }
            else if (type == "Print Response Status Code") {
                int statusCode = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
                emit onStatus(QString("  > Action: Status Code: %1").arg(statusCode));
            }
            else if (type == "Print Response Headers") {
                QString headersStr;
                for (const auto &pair : reply->rawHeaderPairs()) {
                    headersStr += QString("    %1: %2\n").arg(QString(pair.first), QString(pair.second));
                }
                emit onStatus("  > Action: Response Headers:\n" + headersStr.trimmed());
            }
            else if (type == "Print Response Content (Text)") {
                // Truncate content
                QString contentPreview = QString(reply->readAll()).trimmed();
                emit onStatus("  > Action: Response Content:\n" + contentPreview);
            }
            else if (type == "Save Response Content (Binary)") {
                if (param.isEmpty()) {
                    emit onError("  > Action: Save failed. No file path provided in parameter.");
                    continue;
                }
                
                QString filepath = param;
                if (QFileInfo(param).isDir()) {
                    // Get filename from URL
                    QString filename = reply->url().fileName().split("?").first();
                    if (filename.isEmpty()) {
                        filename = QString("response_%1.dat").arg(QDateTime::currentMSecsSinceEpoch());
                    }
                    filepath = QDir(param).filePath(filename);
                }
                
                QDir().mkpath(QFileInfo(filepath).absolutePath());
                QFile file(filepath);
                if (file.open(QIODevice::WriteOnly)) {
                    file.write(reply->readAll());
                    file.close();
                    emit onStatus(QString("  > Action: Response content saved to %1").arg(filepath));
                } else {
                    emit onError(QString("  > Action: Failed to save file to %1: %2").arg(filepath, file.errorString()));
                }
            }
        } catch (const std::exception &e) {
            emit onError(QString("  > Action: Failed to execute '%1': %2").arg(type, e.what()));
        }
    }
}

bool WebRequestsLogic::executeRequest(const QJsonObject &req) {
    if (!m_isRunning) return false;

    QString reqType = req.value("type").toString("GET");
    QString param = req.value("param").toString();
    
    QUrl urlToRequest = encodeUrl(reqType == "GET" ? param : QString());
    
    QNetworkRequest request(urlToRequest);
    request.setRawHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36");

    QNetworkReply *reply = nullptr;
    QEventLoop loop;
    
    if (reqType == "GET") {
        emit onStatus(QString("Executing GET: %1").arg(urlToRequest.toString()));
        reply = m_netManager->get(request);
    } 
    else if (reqType == "POST") {
        QByteArray postData = createPostData(param);
        request.setHeader(QNetworkRequest::ContentTypeHeader, "application/x-www-form-urlencoded");
        emit onStatus(QString("Executing POST: %1 with data: %2").arg(urlToRequest.toString(), QString(postData)));
        reply = m_netManager->post(request, postData);
    } else {
        emit onError(QString("Unsupported request type: %1").arg(reqType));
        return false;
    }

    // Connect signals for sequential execution (mimics blocking nature)
    QObject::connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
    
    // Start waiting for the reply to finish
    QTimer::singleShot(10000, &loop, &QEventLoop::quit); // Timeout (10 seconds)
    loop.exec();
    
    // Check if the reply finished normally or timed out/was cancelled
    if (!reply->isFinished()) {
        reply->abort();
        emit onError("Request failed: Timeout.");
        reply->deleteLater();
        return false;
    }

    emit onStatus(QString("Request complete. Status: %1").arg(reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt()));

    // Check for errors (Network/HTTP)
    if (reply->error() != QNetworkReply::NoError) {
        if (reply->error() == QNetworkReply::TimeoutError) {
            emit onError("Request failed: Timeout.");
        } else {
            // Check for explicit HTTP errors (4xx/5xx)
            int statusCode = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
            if (statusCode >= 400) {
                 emit onError(QString("Request failed: HTTP %1 %2").arg(statusCode).arg(reply->errorString()));
            } else {
                 emit onError(QString("Request failed: Connection Error: %1").arg(reply->errorString()));
            }
        }
        reply->deleteLater();
        return false;
    }
    
    // Run actions on success
    runActions(reply);
    
    reply->deleteLater();
    return true;
}

void WebRequestsLogic::run() {
    emit onStatus(QString("Starting request sequence for %1").arg(m_baseUrl.toString()));

    for (int i = 0; i < m_requestList.size(); ++i) {
        if (!m_isRunning) {
            emit onStatus("Request sequence cancelled.");
            emit onFinished("Cancelled.");
            return;
        }

        QJsonObject req = m_requestList[i].toObject();
        emit onStatus(QString("--- Request %1/%2: [%3] ---").arg(i + 1).arg(m_requestList.size()).arg(req.value("type").toString("GET")));
        
        executeRequest(req);
        
        waitSeconds(0.5); // Small delay between requests
    }
    
    if (m_isRunning) {
        emit onStatus("--- All requests finished. ---");
        emit onFinished("All requests finished.");
    }
}