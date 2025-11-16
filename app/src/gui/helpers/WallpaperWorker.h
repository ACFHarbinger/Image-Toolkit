#pragma once

#include <QObject>
#include <QString>
#include <QMap>
#include <QList>

class QScreen;

// Custom exception for interruption
class InterruptedError : public std::exception {
public:
    const char* what() const noexcept override { return "Work manually cancelled."; }
};

class WallpaperWorker : public QObject
{
    Q_OBJECT

public:
    // Note: List[Monitor] is translated to QList<QScreen*>
    explicit WallpaperWorker(const QMap<QString, QString>& pathMap,
                             const QList<QScreen*>& monitors,
                             QObject* parent = nullptr);

signals:
    void statusUpdate(const QString& message);
    void workFinished(bool success, const QString& message);

public slots:
    void run();
    void stop();

private:
    void log(const QString& message);

    QMap<QString, QString> m_pathMap;
    QList<QScreen*> m_monitors;
    bool m_isRunning;
};