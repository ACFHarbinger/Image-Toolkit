#pragma once

#include <QThread>
#include <QVariantMap>
#include <QWaitCondition>
#include <QMutex>

class DeletionWorker : public QThread
{
    Q_OBJECT

public:
    explicit DeletionWorker(const QVariantMap& config, QObject* parent = nullptr);

signals:
    void progress(int deleted, int total);
    void finished(int count, const QString& message);
    void error(const QString& message);
    void confirmSignal(const QString& message, int count);

public slots:
    void setConfirmationResponse(bool response);

protected:
    void run() override;

private:
    QVariantMap m_config;
    bool m_confirmationResponse;
    QWaitCondition m_waitCondition;
    QMutex m_mutex;
    const static QStringList SUPPORTED_IMG_FORMATS;
};