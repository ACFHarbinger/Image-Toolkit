#pragma once

#include <QLabel>
#include <QString>
#include <QMouseEvent>

class DraggableImageLabel : public QLabel
{
    Q_OBJECT

public:
    explicit DraggableImageLabel(const QString& path, int size, QWidget* parent = nullptr);

protected:
    void mouseMoveEvent(QMouseEvent* event) override;

private:
    QString m_filePath;
};