#include "WallpaperTab.h"
#include "windows/SlideshowQueueWindow.h"
#include "components/MonitorDropWidget.h"
#include "components/DraggableImageLabel.h"
#include "helpers/ImageScannerWorker.h"
#include "helpers/BatchThumbnailLoaderWorker.h"
#include "helpers/WallpaperWorker.h"
#include "styles/Style.h"
#include <QDir>
#include <QFileDialog>
#include <QMessageBox>
#include <QThreadPool>
#include <QSysInfo>

// Assumed styles from Python file
const QString STYLE_SYNC_RUN = R"(
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #667eea, stop:1 #764ba2);
        color: white; font-weight: bold; font-size: 16px;
        padding: 14px; border-radius: 10px; min-height: 44px;
    }
    QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #764ba2, stop:1 #667eea); }
    QPushButton:disabled { background: #718096; }
)";
const QString STYLE_SYNC_STOP = R"(
    QPushButton {
        background-color: #cc3333; color: white; font-weight: bold; font-size: 16px;
        padding: 14px; border-radius: 10px; min-height: 44px;
    }
    QPushButton:hover { background-color: #ff4444; }
    QPushButton:disabled { background: #718096; }
)";


WallpaperTab::WallpaperTab(DatabaseTab *dbTabRef, bool dropdown, QWidget *parent)
    : BaseTab(parent), m_dbTabRef(dbTabRef) {
    
    auto *layout = new QVBoxLayout(this);

    // Monitor Layout Group
    auto *layoutGroup = new QGroupBox("Monitor Layout (Drop images here, double-click to see queue)");
    layoutGroup->setStyleSheet(R"(
        QGroupBox {  
            border: 1px solid #4f545c; border-radius: 8px; margin-top: 10px;
        }
        QGroupBox::title { 
            subcontrol-origin: margin; subcontrol-position: top left; 
            padding: 4px 10px; color: white; border-radius: 4px;
        }
    )");
    
    auto *monitorLayoutContainer = new QWidget();
    m_monitorLayout = new QHBoxLayout(monitorLayoutContainer);
    m_monitorLayout->setSpacing(15);
    m_monitorLayout->setAlignment(Qt::AlignCenter);
    
    layoutGroup->setLayout(m_monitorLayout);
    layout->addWidget(layoutGroup);

    // Slideshow Controls Group
    m_slideshowGroup = new QGroupBox("Slideshow Settings (Per-Monitor Cycle)");
    m_slideshowGroup->setStyleSheet(layoutGroup->styleSheet());
    auto *slideshowLayout = new QHBoxLayout(m_slideshowGroup);
    slideshowLayout->setContentsMargins(10, 20, 10, 10);

    m_slideshowEnabledCheckbox = new QCheckBox("Enable Slideshow");
    m_slideshowEnabledCheckbox->setToolTip("Cycles through dropped images on each monitor. All monitors must have the same number of dropped images.");
    slideshowLayout->addWidget(m_slideshowEnabledCheckbox);

    slideshowLayout->addWidget(new QLabel("Interval:"));
    m_intervalMinSpinbox = new QSpinBox();
    m_intervalMinSpinbox->setRange(0, 60);
    m_intervalMinSpinbox->setValue(5);
    m_intervalMinSpinbox->setFixedWidth(50);
    slideshowLayout->addWidget(m_intervalMinSpinbox);
    slideshowLayout->addWidget(new QLabel("min"));

    m_intervalSecSpinbox = new QSpinBox();
    m_intervalSecSpinbox->setRange(0, 59);
    m_intervalSecSpinbox->setValue(0);
    m_intervalSecSpinbox->setFixedWidth(50);
    slideshowLayout->addWidget(m_intervalSecSpinbox);
    slideshowLayout->addWidget(new QLabel("sec"));
    slideshowLayout->addStretch(1);
    
    m_countdownLabel = new QLabel("Timer: --:--");
    m_countdownLabel->setStyleSheet("color: #2ecc71; font-weight: bold; font-size: 14px;");
    m_countdownLabel->setFixedWidth(100);
    slideshowLayout->addWidget(m_countdownLabel);
    layout->addWidget(m_slideshowGroup);

    // Scan Directory Section
    auto *scanGroup = new QGroupBox("Scan Directory (Image Source)");
    scanGroup->setStyleSheet(layoutGroup->styleSheet());
    auto *scanLayout = new QVBoxLayout();
    scanLayout->setContentsMargins(10, 20, 10, 10);
    
    auto *scanDirLayout = new QHBoxLayout();
    m_scanDirectoryPath = new QLineEdit();
    m_scanDirectoryPath->setPlaceholderText("Select directory to scan...");
    auto *btnBrowseScan = new QPushButton("Browse...");
    connect(btnBrowseScan, &QPushButton::clicked, this, &WallpaperTab::browseScanDirectory);
    apply_shadow_effect(btnBrowseScan, "#000000", 8, 0, 3);
    scanDirLayout->addWidget(m_scanDirectoryPath);
    scanDirLayout->addWidget(btnBrowseScan);
    scanLayout->addLayout(scanDirLayout);
    scanGroup->setLayout(scanLayout);
    layout->addWidget(scanGroup);

    // Thumbnail Gallery Scroll Area
    m_scanScrollArea = new QScrollArea();
    m_scanScrollArea->setWidgetResizable(true);
    m_scanScrollArea->setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }");
    m_scanThumbnailWidget = new QWidget();
    m_scanThumbnailWidget->setStyleSheet("QWidget { background-color: #2c2f33; }");
    m_scanThumbnailLayout = new QGridLayout(m_scanThumbnailWidget);
    m_scanThumbnailLayout->setAlignment(Qt::AlignTop | Qt::AlignHCenter);
    m_scanScrollArea->setWidget(m_scanThumbnailWidget);
    layout->addWidget(m_scanScrollArea, 1);
    
    // Action Buttons
    auto *actionLayout = new QHBoxLayout();
    actionLayout->setSpacing(10);
    
    m_refreshBtn = new QPushButton("Refresh Layout");
    m_refreshBtn->setStyleSheet("background-color: #f1c40f; color: black; padding: 10px; border-radius: 8px; font-weight: bold;");
    apply_shadow_effect(m_refreshBtn, "#000000", 8, 0, 3);
    connect(m_refreshBtn, &QPushButton::clicked, this, &WallpaperTab::handleRefreshLayout);
    actionLayout->addWidget(m_refreshBtn);
    
    m_setWallpaperBtn = new QPushButton("Set Wallpaper");
    m_setWallpaperBtn->setStyleSheet(STYLE_SYNC_RUN);
    apply_shadow_effect(m_setWallpaperBtn, "#000000", 8, 0, 3);
    connect(m_setWallpaperBtn, &QPushButton::clicked, this, &WallpaperTab::handleSetWallpaperClick);
    actionLayout->addWidget(m_setWallpaperBtn, 1);
    
    layout->addLayout(actionLayout);

    // --- Find base directory ---
    try {
        QDir baseDir(QDir::currentPath());
        while (baseDir.dirName() != "Image-Toolkit" && baseDir.cdUp());
        if (baseDir.dirName() == "Image-Toolkit") {
            m_lastBrowsedScanDir = baseDir.filePath("data");
        } else {
            m_lastBrowsedScanDir = QDir::currentPath();
        }
    } catch (...) {
         m_lastBrowsedScanDir = QDir::currentPath();
    }
    
    // Initial setup
    populateMonitorLayout();
    checkAllMonitorsSet();
    stopSlideshow();
}

WallpaperTab::~WallpaperTab() {
    stopSlideshow();
    stopWallpaperWorker();
    
    if (m_scanThread && m_scanThread->isRunning()) {
        m_scanThread->quit();
        m_scanThread->wait();
    }
    if (m_currentThumbnailLoaderThread && m_currentThumbnailLoaderThread->isRunning()) {
        m_currentThumbnailLoaderThread->quit();
        m_currentThumbnailLoaderThread->wait();
    }
    
    for (auto *window : qAsConst(m_openQueueWindows)) {
        window->close();
    }
}

QVariantMap WallpaperTab::collect() {
    QVariantMap queues;
    for(auto it = m_monitorSlideshowQueues.constBegin(); it != m_monitorSlideshowQueues.constEnd(); ++it) {
        queues[it.key()] = it.value();
    }
    QVariantMap out;
    out["monitor_queues"] = queues;
    return out;
}

QPair<bool, int> WallpaperTab::isSlideshowValidationReady() {
    QStringList monitorIds = m_monitorWidgets.keys();
    int numMonitors = monitorIds.size();
    
    if (numMonitors == 0) {
        return qMakePair(false, 0);
    }
        
    QList<int> queueLengths;
    for (const QString &mid : monitorIds) {
        queueLengths.append(m_monitorSlideshowQueues.value(mid, QStringList()).size());
    }
    
    if (std::all_of(queueLengths.begin(), queueLengths.end(), [](int l){ return l > 0; })) {
        int firstLength = queueLengths[0];
        if (std::all_of(queueLengths.begin(), queueLengths.end(), [firstLength](int l){ return l == firstLength; })) {
            return qMakePair(true, firstLength);
        }
    }
        
    return qMakePair(false, 0);
}

void WallpaperTab::checkAllMonitorsSet() {
    if (m_slideshowTimer && m_slideshowTimer->isActive()) {
         return;
    }
    if (m_currentWallpaperWorker) {
        return;
    }

    if (m_setWallpaperBtn->text().contains("Missing")) {
         m_setWallpaperBtn->setText("Set Wallpaper");
    }
        
    QStringList targetMonitorIds = m_monitorWidgets.keys();
    int numMonitors = targetMonitorIds.size();
    
    int setCount = 0;
    for (const QString &mid : targetMonitorIds) {
        if (m_monitorImagePaths.contains(mid) && !m_monitorImagePaths[mid].isEmpty()) {
            setCount++;
        }
    }
    bool allSetSingle = (setCount == numMonitors);

    QPair<bool, int> slideshowState = isSlideshowValidationReady();
    bool isReady = slideshowState.first;
    int queueLen = slideshowState.second;

    if (m_slideshowEnabledCheckbox->isChecked()) {
        if (isReady) {
             m_setWallpaperBtn->setEnabled(true);
             m_setWallpaperBtn->setText(QString("Start Slideshow (%1 images per display)").arg(queueLen));
        } else {
             m_setWallpaperBtn->setEnabled(false);
             m_setWallpaperBtn->setText("Slideshow (Fix image counts)");
        }
    } else if (allSetSingle) {
        m_setWallpaperBtn->setText("Set and Rotate Wallpaper");
        m_setWallpaperBtn->setEnabled(true);
    } else {
        int missing = numMonitors - setCount;
        m_setWallpaperBtn->setText(QString("Set Wallpaper (%1 more)").arg(missing));
        m_setWallpaperBtn->setEnabled(false);
    }
}

// --- Slideshow Handlers ---

void WallpaperTab::updateCountdown() {
    if (m_timeRemainingSec > 0) {
        m_timeRemainingSec--;
        int minutes = m_timeRemainingSec / 60;
        int seconds = m_timeRemainingSec % 60;
        m_countdownLabel->setText(QString("Timer: %1:%2").arg(minutes, 2, 10, QChar('0')).arg(seconds, 2, 10, QChar('0')));
    } else {
        m_countdownLabel->setText("Timer: 00:00");
    }
}

void WallpaperTab::handleSetWallpaperClick() {
    if (m_slideshowTimer && m_slideshowTimer->isActive()) {
        stopSlideshow();
    } else if (m_slideshowEnabledCheckbox->isChecked()) {
        startSlideshow();
    } else {
        if (m_currentWallpaperWorker) {
            stopWallpaperWorker();
        } else {
            runWallpaperWorker();
        }
    }
}

void WallpaperTab::startSlideshow() {
    int numMonitors = m_monitorWidgets.size();
    QPair<bool, int> slideshowState = isSlideshowValidationReady();
    bool isReady = slideshowState.first;
    int queueLen = slideshowState.second;
    
    if (numMonitors == 0) {
        QMessageBox::warning(this, "Slideshow Error", "No monitors detected or configured.");
        m_slideshowEnabledCheckbox->setChecked(false);
        return;
    }
        
    if (!isReady) {
        QMessageBox::critical(this, "Slideshow Error", 
                             "To start the slideshow, all monitors must have the EXACT same, non-zero number of images dropped on them.");
        m_slideshowEnabledCheckbox->setChecked(false);
        return;
    }

    stopSlideshow(); // Clear any existing timers
    
    m_monitorCurrentIndex.clear();
    for (const QString &mid : m_monitorWidgets.keys()) {
        m_monitorCurrentIndex[mid] = -1;
    }

    int intervalMinutes = m_intervalMinSpinbox->value();
    int intervalSeconds = m_intervalSecSpinbox->value();
    m_intervalSec = (intervalMinutes * 60) + intervalSeconds;
    
    if (m_intervalSec <= 0) {
        QMessageBox::critical(this, "Slideshow Error", "Slideshow interval must be greater than 0 seconds.");
        m_slideshowEnabledCheckbox->setChecked(false);
        return;
    }

    m_timeRemainingSec = m_intervalSec;

    m_slideshowTimer = new QTimer(this);
    connect(m_slideshowTimer, &QTimer::timeout, this, &WallpaperTab::cycleSlideshowWallpaper);
    m_slideshowTimer->start(m_intervalSec * 1000);
    
    m_countdownTimer = new QTimer(this);
    connect(m_countdownTimer, &QTimer::timeout, this, &WallpaperTab::updateCountdown);
    m_countdownTimer->start(1000); // 1 second
    
    QMessageBox::information(this, "Slideshow Started", 
                            QString("Per-monitor slideshow started with %1 images per monitor, cycling every %2 minutes and %3 seconds.")
                            .arg(queueLen).arg(intervalMinutes).arg(intervalSeconds));
    
    cycleSlideshowWallpaper(); // Set first image immediately

    m_setWallpaperBtn->setText("Slideshow Running (Stop)");
    m_setWallpaperBtn->setStyleSheet(STYLE_SYNC_STOP);
    m_setWallpaperBtn->setEnabled(true);
}

void WallpaperTab::stopSlideshow() {
    if (m_slideshowTimer) {
        m_slideshowTimer->stop();
        m_slideshowTimer->deleteLater();
        m_slideshowTimer = nullptr;
        QMessageBox::information(this, "Slideshow Stopped", "Wallpaper slideshow stopped.");
    }
    if (m_countdownTimer) {
        m_countdownTimer->stop();
        m_countdownTimer->deleteLater();
        m_countdownTimer = nullptr;
    }

    stopWallpaperWorker();

    for (auto *win : qAsConst(m_openQueueWindows)) {
        win->close();
    }
    m_openQueueWindows.clear();
    
    m_monitorCurrentIndex.clear();
    m_timeRemainingSec = 0;
    m_countdownLabel->setText("Timer: --:--");

    m_slideshowEnabledCheckbox->setChecked(false);
    unlockUiForWallpaper();
}

void WallpaperTab::cycleSlideshowWallpaper() {
    QStringList monitorIds = m_monitorWidgets.keys();
    if (monitorIds.isEmpty()) return;
    
    int currentQueueLength = m_monitorSlideshowQueues.value(monitorIds[0], QStringList()).size();
    if (currentQueueLength == 0) {
        stopSlideshow();
        return;
    }
    
    try {
        QMap<QString, QString> newMonitorPaths;
        
        for (const QString &monitorId : monitorIds) {
            int currentIndex = m_monitorCurrentIndex.value(monitorId, -1);
            const QStringList &queue = m_monitorSlideshowQueues.value(monitorId, QStringList());

            int nextIndex = (currentIndex + 1) % currentQueueLength;
            
            newMonitorPaths[monitorId] = queue[nextIndex];
            m_monitorCurrentIndex[monitorId] = nextIndex;
        }
             
        m_monitorImagePaths = newMonitorPaths;
        runWallpaperWorker(true);
        
        QMap<QString, QString> rotatedPaths = getRotatedPathMap(newMonitorPaths);
        for (auto it = rotatedPaths.constBegin(); it != rotatedPaths.constEnd(); ++it) {
             if (m_monitorWidgets.contains(it.key())) {
                m_monitorWidgets[it.key()]->setImage(it.value());
             }
        }
        
        m_timeRemainingSec = m_intervalSec;
        updateCountdown(); // Update label immediately
        
    } catch (...) {
        QMessageBox::critical(this, "Slideshow Cycle Error", "Failed to cycle wallpaper.");
        stopSlideshow();
    }
}

void WallpaperTab::handleMonitorDoubleClick(const QString &monitorId) {
    for (auto *win : qAsConst(m_openQueueWindows)) {
        if (win->getMonitorId() == monitorId) { // Assumes getMonitorId()
            win->activateWindow();
            return;
        }
    }

    QStringList queue = m_monitorSlideshowQueues.value(monitorId, QStringList());
    QString monitorName = m_monitorWidgets[monitorId]->getMonitor().name; // Assumes getMonitor()
    
    auto *window = new SlideshowQueueWindow(monitorName, monitorId, queue, this);
    window->setAttribute(Qt::WA_DeleteOnClose);
    
    connect(window, &SlideshowQueueWindow::queueReordered, this, &WallpaperTab::onQueueReordered);
    connect(window, &QObject::destroyed, this, &WallpaperTab::removeQueueWindow);
    
    window->show();
    m_openQueueWindows.append(window);
}

void WallpaperTab::removeQueueWindow() {
    SlideshowQueueWindow* window = qobject_cast<SlideshowQueueWindow*>(sender());
    if (window) {
        m_openQueueWindows.removeAll(window);
    }
}

void WallpaperTab::onQueueReordered(const QString &monitorId, const QStringList &newQueue) {
    m_monitorSlideshowQueues[monitorId] = newQueue;
    m_monitorCurrentIndex[monitorId] = -1;
    
    QString newFirstImage = newQueue.isEmpty() ? QString() : newQueue.first();
    m_monitorImagePaths[monitorId] = newFirstImage;
    
    if (m_monitorWidgets.contains(monitorId)) {
        if (!newFirstImage.isEmpty()) {
            m_monitorWidgets[monitorId]->setImage(newFirstImage);
        } else {
            m_monitorWidgets[monitorId]->updateText(); // Assumes this clears the image
        }
    }
    
    checkAllMonitorsSet();
}

// --- Layout and Scanning ---

void WallpaperTab::handleRefreshLayout() {
    stopSlideshow();
    m_monitorSlideshowQueues.clear();
    m_monitorCurrentIndex.clear();
    m_monitorImagePaths.clear();
    m_scanDirectoryPath->clear();
    m_scannedDir.clear();
    m_scanImageList.clear();
    
    clear_scan_image_gallery();
    populateMonitorLayout();
    checkAllMonitorsSet();
    
    auto *readyLabel = new QLabel("Layout Refreshed. Browse for a directory.");
    readyLabel->setAlignment(Qt::AlignCenter);
    readyLabel->setStyleSheet("color: #b9bbbe;");
    m_scanThumbnailLayout->addWidget(readyLabel, 0, 0, 1, calculateColumns());
}

void WallpaperTab::populateMonitorLayout() {
    qDeleteAll(m_monitorLayoutContainer->findChildren<QWidget*>(QString(), Qt::FindDirectChildrenOnly));
    m_monitorWidgets.clear();
    
    try {
        QList<Monitor> systemMonitors = get_monitors(); // Assumed C++ function
        std::sort(systemMonitors.begin(), systemMonitors.end(), [](const Monitor &a, const Monitor &b) {
            return a.x < b.x;
        });
        m_monitors = get_monitors(); // Unsorted list
        
        if (m_monitors.isEmpty()) {
             m_monitorLayout->addWidget(new QLabel("Could not detect any monitors."));
             return;
        }

        QList<Monitor> monitorsToShow = systemMonitors;

        if (QSysInfo::productType() == "windows") {
             monitorsToShow.clear();
             for(const auto& mon : systemMonitors) {
                 if (mon.is_primary) {
                     monitorsToShow.prepend(mon);
                     break;
                 }
             }
             if (monitorsToShow.isEmpty()) monitorsToShow.append(systemMonitors.first());
             
             auto *label = new QLabel("Windows only supports one wallpaper across all screens.");
             label->setStyleSheet("color: #7289da;");
             m_monitorLayout->addWidget(label);
        }

        for (const Monitor &monitor : monitorsToShow) {
            int systemIndex = -1;
            for (int i = 0; i < m_monitors.size(); ++i) {
                if (m_monitors[i].x == monitor.x && 
                    m_monitors[i].y == monitor.y &&
                    m_monitors[i].width == monitor.width && 
                    m_monitors[i].height == monitor.height) {
                    systemIndex = i;
                    break;
                }
            }
            if (systemIndex == -1) continue;

            QString monitorId = QString::number(systemIndex);
            auto *dropWidget = new MonitorDropWidget(monitor, monitorId);
            connect(dropWidget, &MonitorDropWidget::imageDropped, this, &WallpaperTab::onImageDropped);
            connect(dropWidget, &MonitorDropWidget::doubleClicked, this, &WallpaperTab::handleMonitorDoubleClick);
            
            QString currentImage = m_monitorImagePaths.value(monitorId);
            if (!currentImage.isEmpty()) {
                dropWidget->setImage(currentImage);
            }
            
            m_monitorLayout->addWidget(dropWidget);
            m_monitorWidgets[monitorId] = dropWidget;
        }
        
        checkAllMonitorsSet();

    } catch (...) {
         QMessageBox::critical(this, "Error", "Could not get monitor info.");
         m_monitors.clear();
    }
}

void WallpaperTab::onImageDropped(const QString &monitorId, const QString &imagePath) {
    if (!m_monitorSlideshowQueues.contains(monitorId)) {
        m_monitorSlideshowQueues[monitorId] = QStringList();
    }
    m_monitorSlideshowQueues[monitorId].append(imagePath);
    m_monitorImagePaths[monitorId] = imagePath;
    
    if (m_monitorWidgets.contains(monitorId)) {
        m_monitorWidgets[monitorId]->setImage(imagePath);
    }
    
    checkAllMonitorsSet();
}

QMap<QString, QString> WallpaperTab::getRotatedPathMap(const QMap<QString, QString> &sourcePaths) {
    int n = m_monitors.size();
    if (n == 0) return {};
        
    QMap<QString, QString> rotatedMap;
    for (int i = 0; i < n; ++i) {
        QString currentMonitorId = QString::number(i);
        int prevMonitorIndex = (i - 1 + n) % n;
        QString prevMonitorId = QString::number(prevMonitorIndex);
        
        rotatedMap[currentMonitorId] = sourcePaths.value(prevMonitorId);
    }
    return rotatedMap;
}

// --- Worker Handlers ---

void WallpaperTab::runWallpaperWorker(bool slideshowMode) {
    if (m_currentWallpaperWorker) {
        return; // Worker already running
    }
    if (m_monitorImagePaths.values().isEmpty()) {
        if (!slideshowMode) {
            QMessageBox::warning(this, "Incomplete", "No images have been dropped on the monitors.");
        }
        return;
    }

    QMap<QString, QString> pathMap = getRotatedPathMap(m_monitorImagePaths);
    
    if (!slideshowMode) {
        lockUiForWallpaper();
    }
    
    m_currentWallpaperWorker = new WallpaperWorker(pathMap, m_monitors);
    // connect signals from WallpaperWorker's internal QObject (m_signals)
    connect(m_currentWallpaperWorker->getSignals(), &WallpaperWorkerSignals::statusUpdate, this, &WallpaperTab::handleWallpaperStatus);
    connect(m_currentWallpaperWorker->getSignals(), &WallpaperWorkerSignals::workFinished, this, &WallpaperTab::handleWallpaperFinished);
    
    // Auto-delete the worker when finished
    connect(m_currentWallpaperWorker->getSignals(), &WallpaperWorkerSignals::workFinished, m_currentWallpaperWorker, &QObject::deleteLater);
    // Clear the pointer when deleted
    connect(m_currentWallpaperWorker, &QObject::destroyed, [this](){ m_currentWallpaperWorker = nullptr; });
    
    QThreadPool::globalInstance()->start(m_currentWallpaperWorker);
}

void WallpaperTab::stopWallpaperWorker() {
    if (m_currentWallpaperWorker) {
        m_currentWallpaperWorker->stop(); // Assumes worker has a stop() method
        handleWallpaperStatus("Manual stop requested.");
        unlockUiForWallpaper();
        // Worker will self-delete, just null the pointer
        m_currentWallpaperWorker = nullptr;
    }
}

void WallpaperTab::lockUiForWallpaper() {
    m_setWallpaperBtn->setText("Applying (Click to Stop)");
    m_setWallpaperBtn->setStyleSheet(STYLE_SYNC_STOP);
    m_setWallpaperBtn->setEnabled(true);
    m_refreshBtn->setEnabled(false);
    m_slideshowGroup->setEnabled(false);
    m_scanScrollArea->setEnabled(false);
    QApplication::processEvents();
}

void WallpaperTab::unlockUiForWallpaper() {
    m_setWallpaperBtn->setText("Set Wallpaper");
    m_setWallpaperBtn->setStyleSheet(STYLE_SYNC_RUN);
    m_refreshBtn->setEnabled(true);
    m_slideshowGroup->setEnabled(true);
    m_scanScrollArea->setEnabled(true);
    checkAllMonitorsSet();
    QApplication::processEvents();
}

void WallpaperTab::handleWallpaperStatus(const QString &msg) {
    qDebug() << "[WallpaperWorker]" << msg;
}

void WallpaperTab::handleWallpaperFinished(bool success, const QString &message) {
    bool isSlideshowActive = (m_slideshowTimer && m_slideshowTimer->isActive());

    if (success) {
        if (!isSlideshowActive) {
            QMessageBox::information(this, "Success", "Wallpaper has been rotated and updated!");
            
            // This logic seems reversed from Python, but it's what's written.
            // Python sets the *new* image (from the *previous* monitor)
            // C++ also does this in cycleSlideshowWallpaper()
        }
    } else {
        if (!message.toLower().contains("manually cancelled")) {
            if (isSlideshowActive) {
                qWarning() << "Slideshow Error: Failed to set wallpaper:" << message;
                stopSlideshow();
            } else {
                QMessageBox::critical(this, "Error", QString("Failed to set wallpaper:\n%1").arg(message));
            }
        }
    }
    
    if (!isSlideshowActive) {
        unlockUiForWallpaper();
    }
    // m_currentWallpaperWorker is cleared via signal/slot
}

// --- Scanner ---
// (Identical to ScanMetadataTab, but using DraggableImageLabel)

void WallpaperTab::browseScanDirectory() {
    QString directory = QFileDialog::getExistingDirectory(
        this, "Select directory to scan", m_lastBrowsedScanDir,
        QFileDialog::ShowDirsOnly | QFileDialog::DontResolveSymlinks
    );
    if (!directory.isEmpty()) {
        m_lastBrowsedScanDir = directory;
        m_scanDirectoryPath->setText(directory);
        populateScanImageGallery(directory);
    }
}

void WallpaperTab::populateScanImageGallery(const QString &directory) {
    m_scannedDir = directory;
    clear_scan_image_gallery();
    
    auto *loadingLabel = new QLabel("Scanning directory, please wait...");
    loadingLabel->setAlignment(Qt::AlignCenter);
    loadingLabel->setStyleSheet("color: #b9bbbe;");
    m_scanThumbnailLayout->addWidget(loadingLabel, 0, 0, 1, 10);
    
    m_scanWorker = new ImageScannerWorker(directory);
    m_scanThread = new QThread();
    m_scanWorker->moveToThread(m_scanThread);
    
    connect(m_scanThread, &QThread::started, m_scanWorker, &ImageScannerWorker::runScan);
    connect(m_scanWorker, &ImageScannerWorker::scanFinished, this, &WallpaperTab::displayScanResults);
    connect(m_scanWorker, &ImageScannerWorker::scanError, this, &WallpaperTab::handleScanError);
    
    connect(m_scanWorker, &ImageScannerWorker::scanFinished, m_scanThread, &QThread::quit);
    connect(m_scanWorker, &ImageScannerWorker::scanFinished, m_scanWorker, &QObject::deleteLater);
    connect(m_scanThread, &QThread::finished, m_scanThread, &QObject::deleteLater);
    connect(m_scanThread, &QThread::finished, this, &WallpaperTab::cleanupScanThreadRef);
    
    m_scanThread->start();
}

void WallpaperTab::displayScanResults(const QStringList &imagePaths) {
    clear_scan_image_gallery();
    m_scanImageList = imagePaths;
    checkAllMonitorsSet();
    
    int columns = calculateColumns();
    if (m_scanImageList.isEmpty()) {
        auto *noImagesLabel = new QLabel("No supported images found.");
        noImagesLabel->setAlignment(Qt::AlignCenter);
        noImagesLabel->setStyleSheet("color: #b9bbbe;");
        m_scanThumbnailLayout->addWidget(noImagesLabel, 0, 0, 1, columns);
        return;
    }
    
    m_currentThumbnailLoaderWorker = new BatchThumbnailLoaderWorker(m_scanImageList, m_thumbnailSize);
    m_currentThumbnailLoaderThread = new QThread();
    m_currentThumbnailLoaderWorker->moveToThread(m_currentThumbnailLoaderThread);
    
    connect(m_currentThumbnailLoaderThread, &QThread::started, m_currentThumbnailLoaderWorker, &BatchThumbnailLoaderWorker::runLoadBatch);
    connect(m_currentThumbnailLoaderWorker, &BatchThumbnailLoaderWorker::createPlaceholder, this, &WallpaperTab::createThumbnailPlaceholder);
    connect(m_currentThumbnailLoaderWorker, &BatchThumbnailLoaderWorker::thumbnailLoaded, this, &WallpaperTab::updateThumbnailSlot);
    
    connect(m_currentThumbnailLoaderWorker, &BatchThumbnailLoaderWorker::loadingFinished, m_currentThumbnailLoaderThread, &QThread::quit);
    connect(m_currentThumbnailLoaderWorker, &BatchThumbnailLoaderWorker::loadingFinished, m_currentThumbnailLoaderWorker, &QObject::deleteLater);
    connect(m_currentThumbnailLoaderThread, &QThread::finished, m_currentThumbnailLoaderThread, &QObject::deleteLater);
    connect(m_currentThumbnailLoaderThread, &QThread::finished, this, &WallpaperTab::cleanupThumbnailThreadRef);
    
    // Connect "loading finished" message
    connect(m_currentThumbnailLoaderWorker, &BatchThumbnailLoaderWorker::loadingFinished, [this](){
        int count = m_scanImageList.size();
        if (count > 0) {
            QMessageBox::information(this, "Scan Complete", 
                QString("Finished loading **%1** images from the directory. They are now available in the gallery below.").arg(count));
        }
    });
    
    m_currentThumbnailLoaderThread->start();
}

void WallpaperTab::createThumbnailPlaceholder(int index, const QString &path) {
    int columns = calculateColumns();
    int row = index / columns;
    int col = index % columns;
    auto *draggableLabel = new DraggableImageLabel(path, m_thumbnailSize);
    m_scanThumbnailLayout->addWidget(draggableLabel, row, col);
    m_pathToLabelMap[path] = draggableLabel;
    m_scanThumbnailWidget->update();
    QApplication::processEvents();
}

void WallpaperTab::updateThumbnailSlot(int index, const QPixmap &pixmap, const QString &path) {
    auto *label = qobject_cast<DraggableImageLabel*>(m_pathToLabelMap.value(path));
    if (!label) return;

    if (!pixmap.isNull()) {
        label->setPixmap(pixmap);
        label->setText("");
        label->setStyleSheet("border: 1px solid #4f545c;");
    } else {
        label->setText("Load Error");
        label->setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;");
    }
}

void WallpaperTab::cleanupThumbnailThreadRef() {
    m_currentThumbnailLoaderThread = nullptr;
    m_currentThumbnailLoaderWorker = nullptr;
}

void WallpaperTab::cleanupScanThreadRef() {
    m_scanThread = nullptr;
    m_scanWorker = nullptr;
}

void WallpaperTab::clear_scan_image_gallery() {
    if (m_currentThumbnailLoaderThread && m_currentThumbnailLoaderThread->isRunning()) {
        m_currentThumbnailLoaderThread->quit();
        m_currentThumbnailLoaderThread->wait(1000);
    }
    m_currentThumbnailLoaderThread = nullptr;
    m_currentThumbnailLoaderWorker = nullptr;
    m_pathToLabelMap.clear();

    qDeleteAll(m_scanThumbnailWidget->findChildren<QWidget*>(QString(), Qt::FindDirectChildrenOnly));
    m_scanImageList.clear();
}

void WallpaperTab::handleScanError(const QString &message) {
    clear_scan_image_gallery();
    QMessageBox::warning(this, "Error Scanning", message);
    auto *readyLabel = new QLabel("Browse for a directory.");
    readyLabel->setAlignment(Qt::AlignCenter);
    readyLabel->setStyleSheet("color: #b9bbbe;");
    m_scanThumbnailLayout->addWidget(readyLabel, 0, 0, 1, 1);
}

int WallpaperTab::calculateColumns() const {
    int widgetWidth = m_scanThumbnailWidget->width();
    if (widgetWidth <= 0) {
        if(m_scanThumbnailWidget->parentWidget()) {
            widgetWidth = m_scanThumbnailWidget->parentWidget()->width();
        } else {
            widgetWidth = 800; // Default
        }
    }
    if (widgetWidth <= 0) return 4;
    return qMax(1, widgetWidth / m_approxItemWidth);
}