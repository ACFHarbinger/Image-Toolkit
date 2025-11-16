#pragma once

#include <QDialog>
#include <QString>
#include <QSize>

class QScrollArea;

class ImagePreviewWindow : public QDialog
{
    Q_OBJECT

public:
    // Kept dbTabRef for signature matching, though it's unused
    explicit ImagePreviewWindow(const QString& imagePath, QWidget* dbTabRef, QWidget* parent = nullptr);

private:
    QString m_imagePath;
    QScrollArea* m_scrollArea;
    QSize m_originalPixmapSiz;
    int m_maxWidth;
    int m_maxHeight;
};