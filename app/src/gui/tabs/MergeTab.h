#pragma once

#include <QtWidgets>
#include "tabs/BaseTab.h"
#include <QSet>
#include <QMap>

// Forward declarations
class QLineEdit;
class QPushButton;
class QComboBox;
class QSpinBox;
class QLabel;
class QGroupBox;
class QGridLayout;
class ClickableLabel;
class MarqueeScrollArea;
class MergeWorker;
class ImageScannerWorker;
class BatchThumbnailLoaderWorker;

class MergeTab : public BaseTab {
    Q_OBJECT

public:
    explicit MergeTab(bool dropdown = true, QWidget *parent = nullptr);
    ~MergeTab() override;

private slots:
    // Thread cleanup
    void cleanupScanThreadRef();
    void cleanupLoaderThreadRef();
    void cleanupMergeThreadRef();

    // UI Controls
    void toggleGridVisibility(const QString &direction);
    void updateRunButtonState();

    // Input/Gallery
    void browseFilesLogic();
    void browseScanDirectory();
    void handleScanDirectoryReturn();
    void populateScanGallery(const QString &directory);
    void displayScanResults(const QStringList &imagePaths);
    void handleScanError(const QString &message);
    void createThumbnailPlaceholder(int idx, const QString &path);
    void updateThumbnailSlot(int idx, const QPixmap &pixmap, const QString &path);

    // Selection
    void toggleSelection(const QString &path);
    void handleMarqueeSelection(const QSet<QString> &paths, bool ctrlPressed);
    void refreshSelectedPanel();
    
    // Merge
    void startMerge();
    void updateProgress(int cur, int total);
    void onMergeDone(const QString &path);
    void onMergeError(const QString &msg);

private:
    void clearGallery(QGridLayout *layout);
    void showPlaceholder(const QString &text);
    int columns(QScrollArea *area) const;
    void updateLabelStyle(ClickableLabel *label, const QString &path, bool selected);
    QVariantMap collect(const QString &outputPath);
    
    // State
    QSet<QString> m_selectedImagePaths;
    QStringList m_mergeImageList;
    QMap<QString, ClickableLabel *> m_pathToLabelMap;
    QMap<QString, ClickableLabel *> m_selectedCardMap;
    QString m_scannedDir;
    QString m_lastBrowsedDir;

    // Threading
    QThread *m_currentScanThread = nullptr;
    ImageScannerWorker *m_currentScanWorker = nullptr;
    QThread *m_currentLoaderThread = nullptr;
    BatchThumbnailLoaderWorker *m_currentLoaderWorker = nullptr;
    QThread *m_currentMergeThread = nullptr;
    MergeWorker *m_currentMergeWorker = nullptr;

    // UI Constants
    const int m_thumbnailSize = 150;
    const int m_paddingWidth = 10;
    const int m_approxItemWidth = 160;

    // UI Members
    QComboBox *m_direction;
    QSpinBox *m_spacing;
    QGroupBox *m_gridGroup;
    QSpinBox *m_gridRows;
    QSpinBox *m_gridCols;
    QLineEdit *m_inputPathInfo;
    QLabel *m_selectionLabel;
    MarqueeScrollArea *m_mergeScrollArea;
    QWidget *m_mergeThumbnailWidget;
    QGridLayout *m_mergeThumbnailLayout;
    MarqueeScrollArea *m_selectedImagesArea;
    QWidget *m_selectedImagesWidget;
    QGridLayout *m_selectedGridLayout;
    QPushButton *m_runButton;
    QLabel *m_statusLabel;
};