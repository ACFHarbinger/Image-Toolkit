#include "MonitorDropWidget.h"
#include <QScreen>
#include <QMimeData>
#include <QUrl>
#include <QFileInfo>
#include <QPixmap>
#include <QStyle>

// Define the supported formats (this was imported in Python)
const QStringList MonitorDropWidget::SUPPORTED_IMG_FORMATS = {
    ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"
};

MonitorDropWidget::MonitorDropWidget(QScreen* screen, const QString& monitorId, QWidget* parent)
    : QLabel(parent), m_screen(screen), m_monitorId(monitorId)
{
    setAcceptDrops(true);
    setAlignment(Qt::AlignCenter);
    setMinimumSize(220, 160);
    setWordWrap(true);
    setFixedHeight(160);

    updateText();
    setStyleSheet(R"(
        QLabel {
            background-color: #36393f;
            border: 2px dashed #4f545c;
            border-radius: 8px;
            color: #b9bbbe;
            font-size: 14px;
        }
        QLabel[dragging="true"] {
            border: 2px solid #5865f2; /* Highlight on drag over */
            background-color: #40444b;
        }
    )");
}

void MonitorDropWidget::mouseDoubleClickEvent(QMouseEvent* event)
{
    if (event->button() == Qt::LeftButton) {
        emit doubleClicked(m_monitorId);
    }
    QLabel::mouseDoubleClickEvent(event);
}

void MonitorDropWidget::updateText()
{
    QString monitorName = QString("Monitor %1").arg(m_monitorId);
    if (m_screen && !m_screen->name().isEmpty()) {
         monitorName = QString("%1 (%2)").arg(monitorName, m_screen->name());
    }

    int w = m_screen ? m_screen->geometry().width() : 0;
    int h = m_screen ? m_screen->geometry().height() : 0;

    setText(QString("<b>%1</b>\n(%2x%3)\n\nDrag & Drop Image Here")
            .arg(monitorName)
            .arg(w)
            .arg(h));
}

void MonitorDropWidget::dragEnterEvent(QDragEnterEvent* event)
{
    if (hasValidImageUrl(event->mimeData())) {
        event->acceptProposedAction();
        setProperty("dragging", true);
        style()->polish(this);
    } else {
        event->ignore();
    }
}

void MonitorDropWidget::dragMoveEvent(QDragMoveEvent* event)
{
    if (hasValidImageUrl(event->mimeData())) {
        event->acceptProposedAction();
    } else {
        event->ignore();
    }
}

void MonitorDropWidget::dragLeaveEvent(QDragLeaveEvent* event)
{
    setProperty("dragging", false);
    style()->polish(this);
}

void MonitorDropWidget::dropEvent(QDropEvent* event)
{
    setProperty("dragging", false);
    style()->polish(this);

    if (hasValidImageUrl(event->mimeData())) {
        QUrl url = event->mimeData()->urls().first();
        QString filePath = url.toLocalFile();

        if (QFileInfo::isFile(filePath)) {
            emit imageDropped(m_monitorId, filePath);
            event->acceptProposedAction();
            return;
        }
    }
    event->ignore();
}

bool MonitorDropWidget::hasValidImageUrl(const QMimeData* mimeData) const
{
    if (!mimeData->hasUrls() || mimeData->urls().isEmpty()) {
        return false;
    }

    QUrl url = mimeData->urls().first();
    if (!url.isLocalFile()) {
        return false;
    }

    QString filePath = url.toLocalFile().toLower();
    for (const QString& fmt : SUPPORTED_IMG_FORMATS) {
        if (filePath.endsWith(fmt)) {
            return true;
        }
    }
    return false;
}

void MonitorDropWidget::setImage(const QString& filePath)
{
    m_imagePath = filePath;
    QPixmap pixmap(filePath);

    if (!pixmap.isNull()) {
        QPixmap scaledPixmap = pixmap.scaled(size(), Qt::KeepAspectRatio, Qt::SmoothTransformation);
        setPixmap(scaledPixmap);
        setText(""); // Clear text
    } else {
        m_imagePath.clear();
        updateText(); // Reset to default text
        
        int w = m_screen ? m_screen->geometry().width() : 0;
        int h = m_screen ? m_screen->geometry().height() : 0;
        
        setText(QString("<b>Monitor %1</b>\n(%2x%3)\n\n<b>Error:</b> Could not load image.")
                .arg(m_monitorId)
                .arg(w)
                .arg(h));
    }
}

void MonitorDropWidget::resizeEvent(QResizeEvent* event)
{
    QLabel::resizeEvent(event);
    if (!m_imagePath.isEmpty()) {
        QPixmap pixmap(m_imagePath);
        if (!pixmap.isNull()) {
            QPixmap scaledPixmap = pixmap.scaled(size(), Qt::KeepAspectRatio, Qt::SmoothTransformation);
            setPixmap(scaledPixmap);
        }
    }
}