#include "ClickableLabel.h"
#include <QMouseEvent>
#include <QFileInfo>

ClickableLabel::ClickableLabel(const QString& filePath, QWidget* parent)
    : QLabel(parent), m_path(filePath)
{
    setCursor(Qt::PointingHandCursor);
    setAlignment(Qt::AlignCenter);
    setToolTip(QFileInfo(m_path).fileName());
    setFixedSize(100, 100);

    // Enable mouse tracking if needed, though not strictly
    // necessary for press/double-click events
    setMouseTracking(true);
}

void ClickableLabel::mousePressEvent(QMouseEvent* event)
{
    if (event->button() == Qt::LeftButton) {
        emit pathClicked(m_path);
    }
    QLabel::mousePressEvent(event);
}

void ClickableLabel::mouseDoubleClickEvent(QMouseEvent* event)
{
    if (event->button() == Qt::LeftButton) {
        emit pathDoubleClicked(m_path);
    }
    QLabel::mouseDoubleClickEvent(event);
}