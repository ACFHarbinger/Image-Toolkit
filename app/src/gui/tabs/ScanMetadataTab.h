#pragma once

#include <QtWidgets>
#include "tabs/BaseTab.h"
#include "tabs/DatabaseTab.h" // Assuming this is the type
#include <QSet>
#include <QMap>

// Forward declarations
class QLineEdit;
class QPushButton;
class QComboBox;
class QCheckBox;
class QLabel;
class QScrollArea;
class QGridLayout;
class QGroupBox;
class ImagePreviewWindow;
class ClickableLabel;
class MarqueeScrollArea;
class ImageScannerWorker;
class BatchThumbnailLoaderWorker;

class ScanMetadataTab : public BaseTab {
    Q_OBJECT

public:
    explicit ScanMetadataTab(DatabaseTab *dbTabRef, bool dropdown = true, QWidget *parent = nullptr);
    ~ScanMetadataTab() override;

    void updateButtonStates(bool connected);
    QVariantMap collect();

private slots:
    // Thread management
    void cleanupThumbnailThreadRef();
    void cleanupScanThreadRef();

    // Gallery population
    void browseScanDirectory();
    void handleScanDirectoryReturn();
    void populateScanImageGallery(const QString &directory);
    void displayScanResults(const QStringList &imagePaths);
    void createThumbnailPlaceholder(int index, const QString &path);
    void updateThumbnailSlot(int index, const QPixmap &pixmap, const QString &path);
    void handleScanError(const QString &message);

    // Selection
    void selectScanImage(const QString &filePath);
    void selectSelectedImageCard(const QString &filePath);
    void handleMarqueeSelection(const QSet<QString> &paths, bool ctrlPressed);
    
    // Actions
    void viewSelectedScanImage();
    void viewSelectedScanImageFromDoubleClick(const QString &path);
    void viewSelectedImageFromCard(const QString &path);
    void toggleSelectedImagesView();
    void performUpsertOperation();
    void refreshImageDirectory();
    void deleteSelectedImages();

    // Preview window
    void removePreviewWindow(QObject *windowInstance); // Use QObject* to match signal

private:
    void clearScanImageGallery();
    void populateSelectedImagesGallery();
    int calculateColumns(QWidget *widget, int approxWidth) const;

    DatabaseTab *m_dbTabRef;
    bool m_dropdown;

    // State
    QStringList m_scanImageList;
    QSet<QString> m_selectedImagePaths;
    QString m_selectedScanImagePath;
    QList<ImagePreviewWindow *> m_openPreviewWindows;
    QString m_lastBrowsedScanDir;
    QString m_scannedDir;

    // Gallery/Card tracking
    QMap<QString, ClickableLabel *> m_pathToLabelMap;
    QMap<QString, ClickableLabel *> m_selectedCardMap; // Wrapper is a ClickableLabel

    // Threading
    QThread *m_scanThread = nullptr;
    ImageScannerWorker *m_scanWorker = nullptr;
    QThread *m_currentThumbnailLoaderThread = nullptr;
    BatchThumbnailLoaderWorker *m_currentThumbnailLoaderWorker = nullptr;
    
    // UI Constants
    const int m_thumbnailSize = 150;
    const int m_paddingWidth = 10;
    const int m_approxItemWidth = 160; // 150 + 10

    // UI Members
    QLineEdit *m_scanDirectoryPath;
    QPushButton *m_scanViewImageBtn;
    MarqueeScrollArea *m_scanScrollArea;
    QWidget *m_scanThumbnailWidget;
    QGridLayout *m_scanThumbnailLayout;
    
    MarqueeScrollArea *m_selectedImagesArea;
    QWidget *m_selectedImagesWidget;
    QGridLayout *m_selectedGridLayout;
    
    QGroupBox *m_metadataGroup;
    QComboBox *m_seriesCombo;
    QLineEdit *m_charactersEdit;
    QLabel *m_charSuggestions;
    QMap<QString, QCheckBox *> m_tagCheckboxes;

    QPushButton *m_viewBatchButton;
    QPushButton *m_upsertButton;
    QPushButton *m_refreshImageButton;
    QPushButton *m_deleteSelectedButton;
};