#pragma once

#include <QLabel>
#include <QString>
#include <QScreen>
#include <QDragEnterEvent>
#include <QDropEvent>
#include <QDragMoveEvent>
#include <QDragLeaveEvent>
#include <QMouseEvent>

class MonitorDropWidget : public QLabel
{
    Q_OBJECT

public:
    // NOTE: Assumes Python's 'Monitor' object is best mapped to QScreen
    explicit MonitorDropWidget(QScreen* screen, const QString& monitorId, QWidget* parent = nullptr);

    void setImage(const QString& filePath);

signals:
    void imageDropped(const QString& monitorId, const QString& imagePath);
    void doubleClicked(const QString& monitorId);

protected:
    void mouseDoubleClickEvent(QMouseEvent* event) override;
    void dragEnterEvent(QDragEnterEvent* event) override;
    void dragMoveEvent(QDragMoveEvent* event) override;
    void dragLeaveEvent(QDragLeaveEvent* event) override;
    void dropEvent(QDropEvent* event) override;
    void resizeEvent(QResizeEvent* event) override;

private:
    void updateText();
    bool hasValidImageUrl(const QMimeData* mimeData) const;

    QScreen* m_screen;
    QString m_monitorId;
    QString m_imagePath; // Equivalent to Optional[str]

    // Definition for SUPPORTED_IMG_FORMATS (assumed)
    const static QStringList SUPPORTED_IMG_FORMATS;
};