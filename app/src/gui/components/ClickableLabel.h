#pragma once

#include <QLabel>
#include <QString>
#include <QMouseEvent>

class ClickableLabel : public QLabel
{
    Q_OBJECT

public:
    explicit ClickableLabel(const QString& filePath, QWidget* parent = nullptr);

    // Public getter for MarqueeScrollArea to access
    QString path() const { return m_path; }

signals:
    void pathClicked(const QString& path);
    void pathDoubleClicked(const QString& path);

protected:
    void mousePressEvent(QMouseEvent* event) override;
    void mouseDoubleClickEvent(QMouseEvent* event) override;

private:
    QString m_path;
};