// WebDriverClient.h
#pragma once
#include <QString>
#include <QJsonObject>
#include <QJsonDocument>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QEventLoop>
#include <QThread>

// Simple structure to mimic a Selenium WebElement
struct WebElement {
    QString id;
};

class WebDriverClient : public QObject {
    Q_OBJECT
public:
    QString sessionId;
    QString baseUrl = "http://localhost:9515"; // Default ChromeDriver port
    QNetworkAccessManager* manager;

    WebDriverClient(QObject* parent = nullptr) : QObject(parent) {
        manager = new QNetworkAccessManager(this);
    }

    // Helper for Synchronous Requests (mimicking Python blocking calls)
    QJsonObject sendRequest(const QString& method, const QString& endpoint, const QJsonObject& body = QJsonObject()) {
        QNetworkRequest request(QUrl(baseUrl + "/session/" + sessionId + endpoint));
        request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
        
        QNetworkReply* reply;
        if (method == "POST") {
            reply = manager->post(request, QJsonDocument(body).toJson());
        } else if (method == "DELETE") {
            reply = manager->deleteResource(request);
        } else {
            reply = manager->get(request);
        }

        // Block until finished (Synchronous wrapper)
        QEventLoop loop;
        connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
        loop.exec();

        QByteArray data = reply->readAll();
        reply->deleteLater();
        return QJsonDocument::fromJson(data).object();
    }

    bool initSession() {
        QJsonObject caps;
        QJsonObject args;
        args["args"] = QJsonArray({"--headless", "--disable-gpu"}); // minimal args
        QJsonObject chromeOptions;
        chromeOptions["goog:chromeOptions"] = args;
        caps["capabilities"] = chromeOptions; // Simplified W3C caps

        // POST /session (New Session)
        QNetworkRequest req(QUrl(baseUrl + "/session"));
        req.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
        QNetworkReply* reply = manager->post(req, QJsonDocument(caps).toJson());
        
        QEventLoop loop;
        connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
        loop.exec();

        QJsonObject resp = QJsonDocument::fromJson(reply->readAll()).object();
        reply->deleteLater();

        if (resp.contains("value")) {
            sessionId = resp["value"].toObject()["sessionId"].toString();
            return !sessionId.isEmpty();
        }
        return false;
    }

    void navigate(const QString& url) {
        QJsonObject body; body["url"] = url;
        sendRequest("POST", "/url", body);
    }

    QString getCurrentUrl() {
        return sendRequest("GET", "/url")["value"].toString();
    }

    // Mimic find_elements
    QList<WebElement> findElements(const QString& strategy, const QString& value) {
        QJsonObject body;
        body["using"] = strategy; // "css selector", "xpath", etc.
        body["value"] = value;

        QJsonObject resp = sendRequest("POST", "/elements", body);
        QList<WebElement> elements;
        
        QJsonArray arr = resp["value"].toArray();
        for(const auto& val : arr) {
            // Selenium returns element ID with a weird key like "element-6066-11e4-a52e-4f735466cecf"
            QJsonObject obj = val.toObject();
            elements.append({obj.begin().value().toString()});
        }
        return elements;
    }
    
    // Mimic element.get_attribute("src")
    QString getAttribute(const WebElement& el, const QString& attr) {
        return sendRequest("GET", "/element/" + el.id + "/attribute/" + attr)["value"].toString();
    }

    void clickElement(const WebElement& el) {
        sendRequest("POST", "/element/" + el.id + "/click");
    }

    void sendKeys(const WebElement& el, const QString& text) {
        QJsonObject body;
        body["text"] = text;
        sendRequest("POST", "/element/" + el.id + "/value", body);
    }

    void quit() {
        sendRequest("DELETE", "");
    }
};