#include "ImagePreviewWindow.h"
#include <QPixmap>
#include <QMessageBox>
#include <QApplication>
#include <QScreen>
#include <QScrollArea>
#include <QLabel>
#include <QVBoxLayout>
#include <QFileInfo>
#include <QRect>
#include <QSize>

ImagePreviewWindow::ImagePreviewWindow(const QString& imagePath, QWidget* dbTabRef, QWidget* parent)
    : QDialog(parent), m_imagePath(imagePath)
{
    Q_UNUSED(dbTabRef); // Mark as unused

    setWindowTitle(QString("Full-Size Image Preview: %1").arg(QFileInfo(imagePath).fileName()));
    setMinimumSize(400, 300);

    // Set native window buttons
    setWindowFlags(
        Qt::Window |
        Qt::WindowSystemMenuHint |
        Qt::WindowCloseButtonHint |
        Qt::WindowMinimizeButtonHint |
        Qt::WindowMaximizeButtonHint
    );

    // Ensure deletion on close
    setAttribute(Qt::WA_DeleteOnClose);

    // 1. Load the image
    QPixmap pixmap(imagePath);
    if (pixmap.isNull()) {
        QMessageBox::critical(this, "Error", QString("Could not load image file: %1").arg(imagePath));
        this->deleteLater(); // Schedule for deletion
        return;
    }

    // 2. Determine screen size
    QScreen* screen = QApplication::primaryScreen();
    QRect screenGeo = screen->availableGeometry();

    m_maxWidth = static_cast<int>(screenGeo.width() * 0.95);
    m_maxHeight = static_cast<int>(screenGeo.height() * 0.95);

    m_originalPixmapSiz = pixmap.size();

    // 3. Scale pixmap if larger than screen
    QPixmap scaledPixmap;
    if (pixmap.width() > m_maxWidth || pixmap.height() > m_maxHeight) {
        scaledPixmap = pixmap.scaled(
            m_maxWidth, m_maxHeight,
            Qt::KeepAspectRatio, Qt::SmoothTransformation
        );
    } else {
        scaledPixmap = pixmap;
    }

    // Determine initial dialog size
    int targetWidth = qMin(scaledPixmap.width() + 50, m_maxWidth + 50);
    int targetHeight = qMin(scaledPixmap.height() + 50, m_maxHeight + 50);
    resize(QSize(targetWidth, targetHeight));

    // 4. Setup image label
    QLabel* imageLabel = new QLabel;
    imageLabel->setPixmap(scaledPixmap);
    imageLabel->setAlignment(Qt::AlignCenter);
    imageLabel->setMinimumSize(scaledPixmap.size());

    // 5. Use QScrollArea
    m_scrollArea = new QScrollArea;
    m_scrollArea->setWidgetResizable(true);
    m_scrollArea->setWidget(imageLabel);

    // 6. Main layout
    QVBoxLayout* vbox = new QVBoxLayout(this);
    vbox->addWidget(m_scrollArea);
    setLayout(vbox);
}