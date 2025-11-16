#pragma once

#include <QThread>
#include <QVariantMap>

class MergeWorker : public QThread
{
    Q_OBJECT

public:
    explicit MergeWorker(const QVariantMap& config, QObject* parent = nullptr);

signals:
    void progress(int current, int total);
    void finished(const QString& outputPath);
    void error(const QString& message);

protected:
    void run() override;

private:
    QVariantMap m_config;
    const static QStringList SUPPORTED_IMG_FORMATS;
};