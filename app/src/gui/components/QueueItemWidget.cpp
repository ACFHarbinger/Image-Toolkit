#include "QueueItemWidget.h"
#include <QLabel>
#include <QHBoxLayout>
#include <QFileInfo>
#include <QSize>

QueueItemWidget::QueueItemWidget(const QString& path, const QPixmap& pixmap, QWidget* parent)
    : QWidget(parent), m_path(path)
{
    QHBoxLayout* layout = new QHBoxLayout(this);
    layout->setContentsMargins(5, 5, 5, 5);

    // Image Preview Label
    QLabel* imgLabel = new QLabel;
    imgLabel->setPixmap(pixmap.scaled(
        QSize(80, 60),
        Qt::KeepAspectRatio,
        Qt::SmoothTransformation
    ));
    imgLabel->setFixedSize(80, 60);
    imgLabel->setStyleSheet("border: 1px solid #4f545c; border-radius: 4px;");
    layout->addWidget(imgLabel);

    // Filename Label
    QString filename = QFileInfo(path).fileName();
    QLabel* fileLabel = new QLabel(filename);
    fileLabel->setToolTip(path);
    fileLabel->setStyleSheet("color: #b9bbbe; font-size: 12px;");
    fileLabel->setWordWrap(True);
    layout->addWidget(fileLabel, 1); // Add with stretch factor 1

    setLayout(layout);
    setFixedSize(QSize(350, 70));
}