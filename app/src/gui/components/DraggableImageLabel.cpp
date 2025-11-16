#include "DraggableImageLabel.h"
#include <QDrag>
#include <QMimeData>
#include <QUrl>
#include <QList>
#include <QPixmap>

DraggableImageLabel::DraggableImageLabel(const QString& path, int size, QWidget* parent)
    : QLabel(parent), m_filePath(path)
{
    setFixedSize(size, size);
    setAlignment(Qt::AlignCenter);
    setText("Loading...");
    setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;");
}

void DraggableImageLabel::mouseMoveEvent(QMouseEvent* event)
{
    if (m_filePath.isEmpty() || pixmap().isNull()) {
        return; // Don't drag if not a valid image
    }

    // QDrag and QMimeData can be stack-allocated for a blocking exec()
    QDrag drag(this);
    QMimeData mimeData;

    QList<QUrl> urls;
    urls.append(QUrl::fromLocalFile(m_filePath));
    mimeData.setUrls(urls);

    drag.setMimeData(&mimeData);

    // Set a pixmap for the drag preview
    drag.setPixmap(pixmap().scaled(
        width() / 2, height() / 2,
        Qt::KeepAspectRatio, Qt::SmoothTransformation
    ));

    drag.exec(Qt::MoveAction);
}