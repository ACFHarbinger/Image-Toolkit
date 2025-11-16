#pragma once

#include <QThread>
#include <QVariantMap>

class ConversionWorker : public QThread
{
    Q_OBJECT

public:
    explicit ConversionWorker(const QVariantMap& config, QObject* parent = nullptr);

signals:
    void finished(int count, const QString& message);
    void error(const QString& message);

protected:
    void run() override;

private:
    QVariantMap m_config;
    const static QStringList SUPPORTED_IMG_FORMATS;
};