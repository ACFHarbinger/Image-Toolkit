#pragma once

#include <QWidget>
#include <QString>
#include <QPixmap>

class QueueItemWidget : public QWidget
{
    Q_OBJECT

public:
    explicit QueueItemWidget(const QString& path, const QPixmap& pixmap, QWidget* parent = nullptr);

    QString path() const { return m_path; }

private:
    QString m_path;
};