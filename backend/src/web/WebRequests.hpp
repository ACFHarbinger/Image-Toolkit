#pragma once

#include <QObject>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QJsonObject>
#include <QJsonArray>
#include <QUrl>
#include <QEventLoop>

class WebRequestsLogic : public QObject {
    Q_OBJECT
public:
    explicit WebRequestsLogic(const QJsonObject &config, QObject *parent = nullptr);
    
    // Public method to start the execution loop
    void run();

    // Public method to stop the execution loop
    Q_SLOT void stop();

signals:
    // === SIGNALS === (Matching Python's signals)
    void onStatus(const QString &message);
    void onError(const QString &message);
    void onFinished(const QString &result);

private:
    // Helper methods
    QUrl encodeUrl(const QString &path) const;
    QByteArray createPostData(const QString &paramStr) const;
    void runActions(QNetworkReply *reply);
    void waitSeconds(double seconds);
    
    // Main request execution logic
    bool executeRequest(const QJsonObject &req);

    // Configuration members
    QJsonObject m_config;
    QUrl m_baseUrl;
    QJsonArray m_requestList;
    QJsonArray m_actionList;
    
    QNetworkAccessManager *m_netManager;
    
    volatile bool m_isRunning = true; // Flag to control cancellation
};