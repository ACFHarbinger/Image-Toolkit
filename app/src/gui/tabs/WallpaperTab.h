#pragma once

#include <QtWidgets>
#include "tabs/BaseTab.h"
#include "tabs/DatabaseTab.h"
#include <QMap>
#include <QList>

// Assuming 'Monitor' struct/class is defined in an included header
// e.g., from a C++ port of 'screeninfo'
#include "utils/ScreenInfo.h" // Assumed header for Monitor and get_monitors()

// Forward declarations
class QLineEdit;
class QPushButton;
class QSpinBox;
class QCheckBox;
class QLabel;
class QScrollArea;
class QGridLayout;
class QTimer;
class MonitorDropWidget;
class SlideshowQueueWindow;
class ImageScannerWorker;
class BatchThumbnailLoaderWorker;
class WallpaperWorker; // Assumes QRunnable and QObject

class WallpaperTab : public BaseTab {
    Q_OBJECT

public:
    explicit WallpaperTab(DatabaseTab *dbTabRef, bool dropdown = true, QWidget *parent = nullptr);
    ~WallpaperTab() override;
    QVariantMap collect();

private slots:
    // Layout and Scanning
    void handleRefreshLayout();
    void browseScanDirectory();
    void populateScanImageGallery(const QString &directory);
    void displayScanResults(const QStringList &imagePaths);
    void createThumbnailPlaceholder(int index, const QString &path);
    void updateThumbnailSlot(int index, const QPixmap &pixmap, const QString &path);
    void handleScanError(const QString &message);
    void cleanupThumbnailThreadRef();
    void cleanupScanThreadRef();
    void populateMonitorLayout();

    // Wallpaper Logic
    void handleSetWallpaperClick();
    void runWallpaperWorker(bool slideshowMode = false);
    void stopWallpaperWorker();
    void handleWallpaperStatus(const QString &msg);
    void handleWallpaperFinished(bool success, const QString &message);
    void onImageDropped(const QString &monitorId, const QString &imagePath);
    void checkAllMonitorsSet();
    
    // Slideshow Logic
    void startSlideshow();
    void stopSlideshow();
    void updateCountdown();
    void cycleSlideshowWallpaper();
    void handleMonitorDoubleClick(const QString &monitorId);
    void onQueueReordered(const QString &monitorId, const QStringList &newQueue);
    void removeQueueWindow();

private:
    QPair<bool, int> isSlideshowValidationReady();
    QMap<QString, QString> getRotatedPathMap(const QMap<QString, QString> &sourcePaths);
    int calculateColumns() const;
    void lockUiForWallpaper();
    void unlockUiForWallpaper();

    DatabaseTab *m_dbTabRef;

    // Monitor State
    QList<Monitor> m_monitors;
    QMap<QString, MonitorDropWidget *> m_monitorWidgets;
    QMap<QString, QString> m_monitorImagePaths;
    
    // Slideshow State
    QMap<QString, QStringList> m_monitorSlideshowQueues;
    QMap<QString, int> m_monitorCurrentIndex;
    QTimer *m_slideshowTimer = nullptr;
    QTimer *m_countdownTimer = nullptr;
    int m_timeRemainingSec = 0;
    int m_intervalSec = 0;
    QList<SlideshowQueueWindow *> m_openQueueWindows;

    // Worker State
    WallpaperWorker *m_currentWallpaperWorker = nullptr; // QRunnable
    
    // Scanner State
    QString m_lastBrowsedScanDir;
    QString m_scannedDir;
    QStringList m_scanImageList;
    QMap<QString, QWidget *> m_pathToLabelMap; // Stores DraggableImageLabel
    QThread *m_scanThread = nullptr;
    ImageScannerWorker *m_scanWorker = nullptr;
    QThread *m_currentThumbnailLoaderThread = nullptr;
    BatchThumbnailLoaderWorker *m_currentThumbnailLoaderWorker = nullptr;

    // UI Constants
    const int m_thumbnailSize = 150;
    const int m_paddingWidth = 10;
    const int m_approxItemWidth = 160;

    // UI Members
    QHBoxLayout *m_monitorLayout;
    QGroupBox *m_slideshowGroup;
    QCheckBox *m_slideshowEnabledCheckbox;
    QSpinBox *m_intervalMinSpinbox;
    QSpinBox *m_intervalSecSpinbox;
    QLabel *m_countdownLabel;
    QLineEdit *m_scanDirectoryPath;
    QScrollArea *m_scanScrollArea;
    QWidget *m_scanThumbnailWidget;
    QGridLayout *m_scanThumbnailLayout;
    QPushButton *m_refreshBtn;
    QPushButton *m_setWallpaperBtn;
};