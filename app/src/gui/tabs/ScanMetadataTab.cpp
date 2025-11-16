#include "ScanMetadataTab.h"
#include "components/ImagePreviewWindow.h"
#include "components/ClickableLabel.h"
#include "components/MarqueeScrollArea.h"
#include "helpers/ImageScannerWorker.h"
#include "helpers/BatchThumbnailLoaderWorker.h"
#include "styles/Style.h"
#include <QFormLayout>
#include <QDir>
#include <QFileDialog>
#include <QMessageBox>

ScanMetadataTab::ScanMetadataTab(DatabaseTab *dbTabRef, bool dropdown, QWidget *parent)
    : BaseTab(parent), m_dbTabRef(dbTabRef), m_dropdown(dropdown) {

    // --- Find base directory ---
    try {
        QDir baseDir(QDir::currentPath());
        while (baseDir.dirName() != "Image-Toolkit" && baseDir.cdUp());
        if (baseDir.dirName() == "Image-Toolkit") {
            m_lastBrowsedScanDir = baseDir.filePath("data");
        } else {
            m_lastBrowsedScanDir = QDir(QDir::currentPath()).filePath("data");
        }
    } catch (...) {
        m_lastBrowsedScanDir = QDir::currentPath();
    }

    auto *mainLayout = new QVBoxLayout(this);
    auto *scrollArea = new QScrollArea();
    scrollArea->setWidgetResizable(true);
    scrollArea->setStyleSheet("QScrollArea { border: none; }");

    auto *scrollContent = new QWidget();
    auto *contentLayout = new QVBoxLayout(scrollContent);
    contentLayout->setContentsMargins(0, 0, 0, 0);

    // --- Scan Directory Section ---
    auto *scanGroup = new QGroupBox("Scan Directory");
    scanGroup->setStyleSheet(R"(
        QGroupBox {  
            border: 1px solid #4f545c; 
            border-radius: 8px; 
            margin-top: 10px; 
        }
        QGroupBox::title { 
            subcontrol-origin: margin; 
            subcontrol-position: top left; 
            padding: 4px 10px; 
            color: white; 
            border-radius: 4px; 
        }
    )");

    auto *scanLayout = new QVBoxLayout();
    scanLayout->setContentsMargins(10, 20, 10, 10);
    auto *scanDirLayout = new QHBoxLayout();
    m_scanDirectoryPath = new QLineEdit();
    m_scanDirectoryPath->setPlaceholderText("Select directory to scan...");
    connect(m_scanDirectoryPath, &QLineEdit::returnPressed, this, &ScanMetadataTab::handleScanDirectoryReturn);
    
    auto *btnBrowseScan = new QPushButton("Browse...");
    connect(btnBrowseScan, &QPushButton::clicked, this, &ScanMetadataTab::browseScanDirectory);
    apply_shadow_effect(btnBrowseScan, "#000000", 8, 0, 3);

    scanDirLayout->addWidget(m_scanDirectoryPath);
    scanDirLayout->addWidget(btnBrowseScan);
    scanLayout->addLayout(scanDirLayout);
    scanGroup->setLayout(scanLayout);
    contentLayout->addWidget(scanGroup);

    // View Image button
    m_scanViewImageBtn = new QPushButton("View Full Size Selected Image(s)");
    connect(m_scanViewImageBtn, &QPushButton::clicked, this, &ScanMetadataTab::viewSelectedScanImage);
    m_scanViewImageBtn->setStyleSheet(R"(
        QPushButton { 
            background-color: #5865f2; color: white; 
            padding: 10px; border-radius: 8px; 
        } 
        QPushButton:hover { background-color: #4754c4; }
        QPushButton:disabled { background-color: #4f545c; color: #a0a0a0; }
    )");
    apply_shadow_effect(m_scanViewImageBtn, "#000000", 8, 0, 3);
    contentLayout->addWidget(m_scanViewImageBtn);

    // Main Gallery
    m_scanScrollArea = new MarqueeScrollArea();
    m_scanScrollArea->setWidgetResizable(true);
    m_scanScrollArea->setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }");
    m_scanScrollArea->setMinimumHeight(600);
    m_scanThumbnailWidget = new QWidget();
    m_scanThumbnailWidget->setStyleSheet("QWidget { background-color: #2c2f33; }");
    m_scanThumbnailLayout = new QGridLayout(m_scanThumbnailWidget);
    m_scanThumbnailLayout->setAlignment(Qt::AlignTop | Qt::AlignHCenter);
    m_scanScrollArea->setWidget(m_scanThumbnailWidget);
    connect(m_scanScrollArea, &MarqueeScrollArea::selectionChanged, this, &ScanMetadataTab::handleMarqueeSelection);
    contentLayout->addWidget(m_scanScrollArea, 1);

    // Selected Images Area (Bottom Gallery)
    m_selectedImagesArea = new MarqueeScrollArea();
    m_selectedImagesArea->setWidgetResizable(true);
    m_selectedImagesArea->setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }");
    m_selectedImagesArea->setMinimumHeight(600);
    m_selectedImagesWidget = new QWidget();
    m_selectedImagesWidget->setStyleSheet("QWidget { background-color: #2c2f33; }");
    m_selectedGridLayout = new QGridLayout(m_selectedImagesWidget);
    m_selectedGridLayout->setSpacing(10);
    m_selectedGridLayout->setAlignment(Qt::AlignTop | Qt::AlignHCenter);
    m_selectedImagesArea->setWidget(m_selectedImagesWidget);
    m_selectedImagesArea->setVisible(true);
    connect(m_selectedImagesArea, &MarqueeScrollArea::selectionChanged, this, &ScanMetadataTab::handleMarqueeSelection);
    contentLayout->addWidget(m_selectedImagesArea, 1);

    // --- Metadata Group Box ---
    m_metadataGroup = new QGroupBox("Batch Metadata (Applies to ALL Selected Images)");
    m_metadataGroup->setVisible(False);
    auto *metadataVBox = new QVBoxLayout(m_metadataGroup);
    auto *formLayout = new QFormLayout();

    auto *seriesLayout = new QHBoxLayout();
    m_seriesCombo = new QComboBox();
    m_seriesCombo->setEditable(true);
    m_seriesCombo->setPlaceholderText("Enter or select series name...");
    seriesLayout->addWidget(m_seriesCombo);
    formLayout->addRow("Series Name:", seriesLayout);

    auto *charLayout = new QVBoxLayout();
    m_charactersEdit = new QLineEdit();
    m_charactersEdit->setPlaceholderText("Enter character names (comma-separated)...");
    charLayout->addWidget(m_charactersEdit);
    m_charSuggestions = new QLabel();
    m_charSuggestions->setStyleSheet("font-size: 9px; color: #b9bbbe;");
    charLayout->addWidget(m_charSuggestions);
    formLayout->addRow("Characters:", charLayout);

    auto *tagsScroll = new QScrollArea();
    tagsScroll->setMaximumHeight(150);
    tagsScroll->setWidgetResizable(true);
    auto *tagsWidget = new QWidget();
    auto *tagsLayout = new QGridLayout(tagsWidget);
    tagsScroll->setWidget(tagsWidget);
    
    const QStringList commonTags = {
        "landscape", "night", "day", "indoor", "outdoor",
        "solo", "multiple", "fanart", "official", "cosplay",
        "portrait", "full_body", "action", "close_up", "nsfw",
        "color", "monochrome", "sketch", "digital", "traditional"
    };
    int columns = 4;
    for (int i = 0; i < commonTags.size(); ++i) {
        const QString &tag = commonTags[i];
        QString title = tag;
        title.replace("_", " ");
        title[0] = title[0].toUpper();
        
        auto *checkbox = new QCheckBox(title);
        checkbox->setStyleSheet(R"(
            QCheckBox::indicator {
                width: 16px; height: 16px; border: 1px solid #555; 
                border-radius: 3px; background-color: #333; 
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50; border: 1px solid #4CAF50; 
                image: url(./src/gui/assets/check.png); 
            }
        )");
        m_tagCheckboxes[tag] = checkbox;
        tagsLayout->addWidget(checkbox, i / columns, i % columns);
    }
    formLayout->addRow("Tags:", tagsScroll);
    metadataVBox->addLayout(formLayout);
    contentLayout->addWidget(m_metadataGroup);
    
    // Connect metadata inputs to upsert button
    connect(m_seriesCombo->lineEdit(), &QLineEdit::returnPressed, m_upsertButton, &QPushButton::click);
    connect(m_charactersEdit, &QLineEdit::returnPressed, m_upsertButton, &QPushButton::click);

    scrollArea->setWidget(scrollContent);
    mainLayout->addWidget(scrollArea, 1);

    // --- Action buttons (Fixed at the bottom) ---
    m_viewBatchButton = new QPushButton("View Selected");
    m_viewBatchButton->setStyleSheet(R"(
        QPushButton { background-color: #3498db; color: white; padding: 10px 8px; border-radius: 8px; font-weight: bold; } 
        QPushButton:hover { background-color: #2980b9; }
        QPushButton:disabled { background-color: #4f545c; color: #a0a0a0; }
    )");
    apply_shadow_effect(m_viewBatchButton, "#000000", 8, 0, 3);
    connect(m_viewBatchButton, &QPushButton::clicked, this, &ScanMetadataTab::toggleSelectedImagesView);

    m_upsertButton = new QPushButton("Add/Update Database Data");
    m_upsertButton->setStyleSheet(R"(
        QPushButton { background-color: #2ecc71; color: white; padding: 10px 8px; border-radius: 8px; font-weight: bold; } 
        QPushButton:hover { background-color: #1e8449; }
        QPushButton:disabled { background-color: #4f545c; color: #a0a0a0; }
    )");
    apply_shadow_effect(m_upsertButton, "#000000", 8, 0, 3);
    connect(m_upsertButton, &QPushButton::clicked, this, &ScanMetadataTab::performUpsertOperation);

    m_refreshImageButton = new QPushButton("Refresh Image Directory");
    m_refreshImageButton->setStyleSheet(R"(
        QPushButton { background-color: #f1c40f; color: white; padding: 10px 8px; border-radius: 8px; font-weight: bold; } 
        QPushButton:hover { background-color: #d4ac0d; }
        QPushButton:disabled { background-color: #4f545c; color: #a0a0a0; }
    )");
    apply_shadow_effect(m_refreshImageButton, "#000000", 8, 0, 3);
    connect(m_refreshImageButton, &QPushButton::clicked, this, &ScanMetadataTab::refreshImageDirectory);

    m_deleteSelectedButton = new QPushButton("Delete Images Data from Database");
    m_deleteSelectedButton->setStyleSheet(R"(
        QPushButton { background-color: #e74c3c; color: white; padding: 10px 8px; border-radius: 8px; font-weight: bold; } 
        QPushButton:hover { background-color: #c0392b; }
        QPushButton:disabled { background-color: #4f545c; color: #a0a0a0; }
    )");
    apply_shadow_effect(m_deleteSelectedButton, "#000000", 8, 0, 3);
    connect(m_deleteSelectedButton, &QPushButton::clicked, this, &ScanMetadataTab::deleteSelectedImages);
    
    auto *scanActionLayout = new QHBoxLayout();
    scanActionLayout->addWidget(m_viewBatchButton);
    scanActionLayout->addWidget(m_upsertButton);
    scanActionLayout->addWidget(m_refreshImageButton);
    scanActionLayout->addWidget(m_deleteSelectedButton);
    
    mainLayout->addLayout(scanActionLayout);
    
    updateButtonStates(false); 
    populateSelectedImagesGallery();
}

ScanMetadataTab::~ScanMetadataTab() {
    // Stop any running threads
    if (m_scanThread && m_scanThread->isRunning()) {
        m_scanThread->quit();
        m_scanThread->wait();
    }
    if (m_currentThumbnailLoaderThread && m_currentThumbnailLoaderThread->isRunning()) {
        m_currentThumbnailLoaderThread->quit();
        m_currentThumbnailLoaderThread->wait();
    }
    // Close preview windows
    for (auto *window : qAsConst(m_openPreviewWindows)) {
        window->close();
    }
}

void ScanMetadataTab::cleanupThumbnailThreadRef() {
    m_currentThumbnailLoaderThread = nullptr;
    m_currentThumbnailLoaderWorker = nullptr;
}

void ScanMetadataTab::cleanupScanThreadRef() {
    m_scanThread = nullptr;
    m_scanWorker = nullptr;
}

void ScanMetadataTab::createThumbnailPlaceholder(int index, const QString &path) {
    int columns = calculateColumns(m_scanThumbnailWidget, m_approxItemWidth);
    int row = index / columns;
    int col = index % columns;

    auto *clickableLabel = new ClickableLabel(path);
    clickableLabel->setText("Loading...");
    clickableLabel->setAlignment(Qt::AlignCenter);
    clickableLabel->setFixedSize(m_thumbnailSize, m_thumbnailSize);
    clickableLabel->setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;");
    connect(clickableLabel, &ClickableLabel::pathClicked, this, &ScanMetadataTab::selectScanImage);
    connect(clickableLabel, &ClickableLabel::pathDoubleClicked, this, &ScanMetadataTab::viewSelectedScanImageFromDoubleClick);

    m_scanThumbnailLayout->addWidget(clickableLabel, row, col);
    m_pathToLabelMap[path] = clickableLabel;
    
    m_scanThumbnailWidget->update();
    QApplication::processEvents();
}

void ScanMetadataTab::displayScanResults(const QStringList &imagePaths) {
    if (m_currentThumbnailLoaderThread && m_currentThumbnailLoaderThread->isRunning()) {
        m_currentThumbnailLoaderThread->quit();
        // Wait for it to finish to avoid conflicts
        m_currentThumbnailLoaderThread->wait(1000); 
    }
    
    m_currentThumbnailLoaderThread = nullptr;
    m_currentThumbnailLoaderWorker = nullptr;
    m_pathToLabelMap.clear();

    while (m_scanThumbnailLayout->count()) {
        QLayoutItem *item = m_scanThumbnailLayout->takeAt(0);
        if (QWidget *widget = item->widget()) {
            widget->deleteLater();
        }
        delete item;
    }
    m_scanImageList = imagePaths;
    
    int columns = calculateColumns(m_scanThumbnailWidget, m_approxItemWidth);
    
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
    connect(m_currentThumbnailLoaderWorker, &BatchThumbnailLoaderWorker::createPlaceholder, this, &ScanMetadataTab::createThumbnailPlaceholder);
    connect(m_currentThumbnailLoaderWorker, &BatchThumbnailLoaderWorker::thumbnailLoaded, this, &ScanMetadataTab::updateThumbnailSlot);
    
    connect(m_currentThumbnailLoaderWorker, &BatchThumbnailLoaderWorker::loadingFinished, m_currentThumbnailLoaderThread, &QThread::quit);
    connect(m_currentThumbnailLoaderWorker, &BatchThumbnailLoaderWorker::loadingFinished, m_currentThumbnailLoaderWorker, &QObject::deleteLater);
    connect(m_currentThumbnailLoaderThread, &QThread::finished, m_currentThumbnailLoaderThread, &QObject::deleteLater);
    connect(m_currentThumbnailLoaderThread, &QThread::finished, this, &ScanMetadataTab::cleanupThumbnailThreadRef);
    
    m_currentThumbnailLoaderThread->start();
}

void ScanMetadataTab::updateThumbnailSlot(int index, const QPixmap &pixmap, const QString &path) {
    ClickableLabel *label = m_pathToLabelMap.value(path);
    if (!label) return;

    bool isSelected = m_selectedImagePaths.contains(path);
    
    if (!pixmap.isNull()) {
        label->setPixmap(pixmap);
        label->setText("");
        label->setStyleSheet(isSelected ? "border: 3px solid #5865f2;" : "border: 1px solid #4f545c;");
    } else {
        label->setText("Load Error");
        label->setStyleSheet(isSelected 
            ? "border: 3px solid #5865f2; background-color: #4f545c; font-size: 8px;"
            : "border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;");
    }
}

void ScanMetadataTab::clearScanImageGallery() {
    if (m_currentThumbnailLoaderThread && m_currentThumbnailLoaderThread->isRunning()) {
        m_currentThumbnailLoaderThread->quit();
        m_currentThumbnailLoaderThread->wait(1000);
    }
    
    m_currentThumbnailLoaderThread = nullptr;
    m_currentThumbnailLoaderWorker = nullptr;
    m_pathToLabelMap.clear();

    while (m_scanThumbnailLayout->count()) {
        QLayoutItem *item = m_scanThumbnailLayout->takeAt(0);
        if (QWidget *widget = item->widget()) {
            widget->deleteLater();
        }
        delete item;
    }
    
    while (m_selectedGridLayout->count()) {
        QLayoutItem *item = m_selectedGridLayout->takeAt(0);
        if (QWidget *widget = item->widget()) {
            widget->deleteLater();
        }
        delete item;
    }
    m_selectedCardMap.clear();
    
    m_scanImageList.clear();
    m_selectedImagePaths.clear();
    m_selectedScanImagePath.clear();
    updateButtonStates(m_dbTabRef && m_dbTabRef->getDatabase()); // Assumes getDatabase()
    m_metadataGroup->setVisible(false);
    populateSelectedImagesGallery();
}

void ScanMetadataTab::handleScanError(const QString &message) {
    clearScanImageGallery();
    QMessageBox::warning(this, "Error Scanning", message);
    auto *readyLabel = new QLabel("Browse for a directory.");
    readyLabel->setAlignment(Qt::AlignCenter);
    readyLabel->setStyleSheet("color: #b9bbbe;");
    m_scanThumbnailLayout->addWidget(readyLabel, 0, 0, 1, 1);
}

void ScanMetadataTab::handleScanDirectoryReturn() {
    QString directory = m_scanDirectoryPath->text().trimmed();
    if (!directory.isEmpty() && QFileInfo(directory).isDir()) {
        populateScanImageGallery(directory);
    } else {
        browseScanDirectory();
    }
}

void ScanMetadataTab::browseScanDirectory() {
    QFileDialog::Options options = QFileDialog::ShowDirsOnly | QFileDialog::DontResolveSymlinks;
    QString directory = QFileDialog::getExistingDirectory(this, "Select directory to scan", m_lastBrowsedScanDir, options);
    
    if (!directory.isEmpty()) {
        m_lastBrowsedScanDir = directory;
        m_scanDirectoryPath->setText(directory);
        populateScanImageGallery(directory);
    }
}

int ScanMetadataTab::calculateColumns(QWidget *widget, int approxWidth) const {
    int widgetWidth = widget->width();
    if (widgetWidth <= 0) {
        if (widget->parentWidget()) {
            widgetWidth = widget->parentWidget()->width();
        } else {
            return 4; // Default
        }
    }
    int columns = widgetWidth / approxWidth;
    return qMax(1, columns);
}

void ScanMetadataTab::populateScanImageGallery(const QString &directory) {
    m_scannedDir = directory;
    
    // Stop and clear previous threads
    if (m_scanThread && m_scanThread->isRunning()) {
        m_scanThread->quit();
        m_scanThread->wait(1000);
    }
    if (m_currentThumbnailLoaderThread && m_currentThumbnailLoaderThread->isRunning()) {
        m_currentThumbnailLoaderThread->quit();
        m_currentThumbnailLoaderThread->wait(1000);
    }
    
    m_pathToLabelMap.clear();
    while (m_scanThumbnailLayout->count()) {
        QLayoutItem *item = m_scanThumbnailLayout->takeAt(0);
        if (QWidget *widget = item->widget()) {
            widget->deleteLater();
        }
        delete item;
    }
    m_scanImageList.clear();
    m_scanViewImageBtn->setEnabled(false);
    
    auto *loadingLabel = new QLabel("Scanning directory, please wait...");
    loadingLabel->setAlignment(Qt::AlignCenter);
    loadingLabel->setStyleSheet("color: #b9bbbe;");
    m_scanThumbnailLayout->addWidget(loadingLabel, 0, 0, 1, 10);
    
    m_scanWorker = new ImageScannerWorker(directory);
    m_scanThread = new QThread();
    m_scanWorker->moveToThread(m_scanThread);
    
    connect(m_scanThread, &QThread::started, m_scanWorker, &ImageScannerWorker::runScan);
    connect(m_scanWorker, &ImageScannerWorker::scanFinished, this, &ScanMetadataTab::displayScanResults);
    connect(m_scanWorker, &ImageScannerWorker::scanError, this, &ScanMetadataTab::handleScanError);
    
    connect(m_scanWorker, &ImageScannerWorker::scanFinished, m_scanThread, &QThread::quit);
    connect(m_scanWorker, &ImageScannerWorker::scanFinished, m_scanWorker, &QObject::deleteLater);
    connect(m_scanThread, &QThread::finished, m_scanThread, &QObject::deleteLater);
    connect(m_scanThread, &QThread::finished, this, &ScanMetadataTab::cleanupScanThreadRef);

    m_scanThread->start();
}

void ScanMetadataTab::selectScanImage(const QString &filePath) {
    ClickableLabel *clickedWidget = m_pathToLabelMap.value(filePath);
    if (!clickedWidget) return;

    bool isSelected;
    if (m_selectedImagePaths.contains(filePath)) {
        m_selectedImagePaths.remove(filePath);
        isSelected = false;
    } else {
        m_selectedImagePaths.insert(filePath);
        isSelected = true;
    }

    if (isSelected) {
        if (clickedWidget->text().contains("Error")) {
            clickedWidget->setStyleSheet("border: 3px solid #5865f2; background-color: #4f545c; font-size: 8px;");
        } else {
            clickedWidget->setStyleSheet("border: 3px solid #5865f2;");
        }
    } else {
        if (!clickedWidget->pixmap() || clickedWidget->pixmap()->isNull()) {
            if (clickedWidget->text().contains("Error")) {
                 clickedWidget->setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;");
            } else {
                 clickedWidget->setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;"); 
            }
        } else {
            clickedWidget->setStyleSheet("border: 1px solid #4f545c;");
        }
    }

    m_selectedScanImagePath = filePath;
    updateButtonStates(m_dbTabRef && m_dbTabRef->getDatabase());
    
    if (m_selectedImagesArea->isVisible()) {
        populateSelectedImagesGallery();
    }
}

void ScanMetadataTab::selectSelectedImageCard(const QString &filePath) {
    ClickableLabel *cardWrapper = m_selectedCardMap.value(filePath);
    if (!cardWrapper) return;
        
    bool isSelected;
    if (m_selectedImagePaths.contains(filePath)) {
        m_selectedImagePaths.remove(filePath);
        isSelected = false;
    } else {
        m_selectedImagePaths.insert(filePath);
        isSelected = true;
    }
        
    QFrame *cardFrame = cardWrapper->findChild<QFrame *>();
    if (cardFrame) {
        if (isSelected) {
            cardFrame->setStyleSheet(R"(
                QFrame {
                    background-color: #2c2f33; 
                    border-radius: 8px; 
                    border: 3px solid #5865f2; 
                }
            )");
        } else {
            cardFrame->setStyleSheet(R"(
                QFrame {
                    background-color: #2c2f33; 
                    border-radius: 8px; 
                    border: 1px solid #4f545c; 
                }
            )");
        }
    }
        
    ClickableLabel *mainLabel = m_pathToLabelMap.value(filePath);
    if (mainLabel) {
        if (isSelected) {
            mainLabel->setStyleSheet("border: 3px solid #5865f2;");
        } else {
            if (mainLabel->pixmap() && !mainLabel->pixmap()->isNull()) {
                mainLabel->setStyleSheet("border: 1px solid #4f545c;");
            } else {
                mainLabel->setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;");
            }
        }
    }
    
    updateButtonStates(m_dbTabRef && m_dbTabRef->getDatabase());
}

void ScanMetadataTab::viewSelectedImageFromCard(const QString &path) {
    if (!m_selectedImagePaths.contains(path)) {
        m_selectedImagePaths.insert(path);
        selectSelectedImageCard(path); // Update styling
    }
    m_selectedScanImagePath = path;
    viewSelectedScanImage();
}

void ScanMetadataTab::handleMarqueeSelection(const QSet<QString> &pathsFromMarquee, bool isCtrlPressed) {
    QSet<QString> pathsToUpdate;
    if (!isCtrlPressed) {
        QSet<QString> pathsToDeselect = m_selectedImagePaths - pathsFromMarquee;
        QSet<QString> pathsToSelect = pathsFromMarquee - m_selectedImagePaths;
        m_selectedImagePaths = pathsFromMarquee;
        pathsToUpdate = pathsToDeselect + pathsToSelect;
    } else {
        pathsToUpdate = pathsFromMarquee - m_selectedImagePaths;
        m_selectedImagePaths.unite(pathsFromMarquee);
    }

    for (const QString &path : pathsToUpdate) {
        ClickableLabel *label = m_pathToLabelMap.value(path);
        if (!label) continue;
        
        bool isSelected = m_selectedImagePaths.contains(path);
        if (isSelected) {
            if (label->text().contains("Error")) {
                label->setStyleSheet("border: 3px solid #5865f2; background-color: #4f545c; font-size: 8px;");
            } else {
                label->setStyleSheet("border: 3px solid #5865f2;");
            }
        } else {
             if (label->pixmap() && !label->pixmap()->isNull()) {
                label->setStyleSheet("border: 1px solid #4f545c;");
            } else {
                if (label->text().contains("Error")) {
                     label->setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;");
                } else {
                     label->setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;"); 
                }
            }
        }
    }

    updateButtonStates(m_dbTabRef && m_dbTabRef->getDatabase());
    if (m_selectedImagesArea->isVisible()) {
        populateSelectedImagesGallery();
    }
}

void ScanMetadataTab::viewSelectedScanImageFromDoubleClick(const QString &path) {
    if (!m_selectedImagePaths.contains(path)) {
        selectScanImage(path);
    }
    m_selectedScanImagePath = path;
    viewSelectedScanImage();
}

void ScanMetadataTab::removePreviewWindow(QObject *windowInstance) {
    ImagePreviewWindow *window = qobject_cast<ImagePreviewWindow *>(windowInstance);
    if (window) {
        m_openPreviewWindows.removeAll(window);
    }
}

void ScanMetadataTab::viewSelectedScanImage() {
    if (m_selectedImagePaths.isEmpty()) {
        if (!m_selectedScanImagePath.isEmpty()) {
            m_selectedImagePaths.insert(m_selectedScanImagePath);
            updateButtonStates(m_dbTabRef && m_dbTabRef->getDatabase());
        } else {
            QMessageBox::warning(this, "No Images Selected", "Please select one or more image thumbnails from the gallery first.");
            return;
        }
    }

    for (const QString &path : m_selectedImagePaths) {
        QFileInfo fileInfo(path);
        if (!fileInfo.exists() || !fileInfo.isFile()) {
            QMessageBox::warning(this, "Invalid Path", QString("The path '%1' is invalid or not a file. Skipping.").arg(path));
            continue;
        }

        bool alreadyOpen = false;
        for (ImagePreviewWindow *window : qAsConst(m_openPreviewWindows)) {
            if (window->getImagePath() == path) { // Assumes getImagePath() exists
                window->activateWindow();
                alreadyOpen = true;
                break;
            }
        }
        
        if (!alreadyOpen) {
            auto *preview = new ImagePreviewWindow(path, m_dbTabRef, this);
            // Connect the finished signal (which Qt provides for dialogs) or a custom signal
            connect(preview, &QObject::destroyed, this, &ScanMetadataTab::removePreviewWindow);
            preview->show();
            m_openPreviewWindows.append(preview);
        }
    }
}

void ScanMetadataTab::toggleSelectedImagesView() {
    int selectionCount = m_selectedImagePaths.size();
    if (selectionCount == 0 && !m_selectedImagesArea->isVisible()) {
        updateButtonStates(m_dbTabRef && m_dbTabRef->getDatabase());
        return;
    }

    if (m_selectedImagesArea->isVisible()) {
        m_selectedImagesArea->setVisible(false);
        m_viewBatchButton->setText(QString("View %1 Selected").arg(selectionCount));
    } else {
        populateSelectedImagesGallery();
        m_selectedImagesArea->setVisible(true);
        m_viewBatchButton->setText(QString("Hide %1 Selected").arg(selectionCount));
    }
}

void ScanMetadataTab::populateSelectedImagesGallery() {
    while (m_selectedGridLayout->count()) {
        QLayoutItem *item = m_selectedGridLayout->takeAt(0);
        if (QWidget *widget = item->widget()) {
            widget->deleteLater();
        }
        delete item;
    }
    m_selectedCardMap.clear();
    
    QStringList paths = m_selectedImagePaths.values();
    std::sort(paths.begin(), paths.end());
    
    int approxWidth = m_thumbnailSize + m_paddingWidth + 10;
    int columns = calculateColumns(m_selectedImagesWidget, approxWidth);
    
    int wrapperHeight = m_thumbnailSize + 30;
    int wrapperWidth = m_thumbnailSize + 10;
    
    if (paths.isEmpty()) {
        auto *emptyLabel = new QLabel("Select images from the scan directory above to view them here.");
        emptyLabel->setAlignment(Qt::AlignCenter);
        emptyLabel->setStyleSheet("color: #b9bbbe; padding: 50px;");
        m_selectedGridLayout->addWidget(emptyLabel, 0, 0, 1, columns);
        return;
    }

    for (int i = 0; i < paths.size(); ++i) {
        const QString &path = paths[i];
        
        auto *cardClickableWrapper = new ClickableLabel(path);
        cardClickableWrapper->setFixedSize(wrapperWidth, wrapperHeight);
        connect(cardClickableWrapper, &ClickableLabel::pathClicked, this, &ScanMetadataTab::selectSelectedImageCard);
        connect(cardClickableWrapper, &ClickableLabel::pathDoubleClicked, this, &ScanMetadataTab::viewSelectedImageFromCard);
        
        auto *card = new QFrame();
        bool isMasterSelected = m_selectedImagePaths.contains(path);
        
        QString cardStyle = (isMasterSelected)
            ? R"(QFrame { 
                    background-color: #2c2f33; 
                    border-radius: 8px; 
                    border: 3px solid #5865f2; 
                })"
            : R"(QFrame { 
                    background-color: #2c2f33; 
                    border-radius: 8px; 
                    border: 1px solid #4f545c; 
                })";
        card->setStyleSheet(cardStyle);
        
        auto *cardLayout = new QVBoxLayout(card);
        cardLayout->setContentsMargins(0, 0, 0, 0);
        
        auto *imgLabel = new QLabel();
        imgLabel->setAlignment(Qt::AlignCenter);
        imgLabel->setFixedSize(m_thumbnailSize, m_thumbnailSize);
        
        QPixmap pixmap(path);
        if (!pixmap.isNull()) {
            imgLabel->setPixmap(pixmap.scaled(m_thumbnailSize, m_thumbnailSize, Qt::KeepAspectRatio, Qt::SmoothTransformation));
        } else {
            imgLabel->setText("Failed to Load");
            imgLabel->setStyleSheet("color: #e74c3c;");
        }

        auto *pathLabel = new QLabel(QFileInfo(path).fileName());
        pathLabel->setStyleSheet("color: #b9bbbe; font-size: 10px; border: none; padding: 2px 0;");
        pathLabel->setAlignment(Qt::AlignCenter);
        pathLabel->setWordWrap(true);

        cardLayout->addWidget(imgLabel);
        cardLayout->addWidget(pathLabel);
        
        // This is a bit of a hack to put the card inside the ClickableLabel
        // A better C++ design would be a custom QWidget.
        auto *wrapperLayout = new QVBoxLayout(cardClickableWrapper);
        wrapperLayout->setContentsMargins(0,0,0,0);
        wrapperLayout->addWidget(card);
        
        int row = i / columns;
        int col = i % columns;
        
        m_selectedCardMap[path] = cardClickableWrapper;
        m_selectedGridLayout->addWidget(cardClickableWrapper, row, col, Qt::AlignCenter);
    }
}

void ScanMetadataTab::performUpsertOperation() {
    auto *db = m_dbTabRef->getDatabase(); // Assumes getDatabase()
    if (!db) {
        QMessageBox::warning(this, "Error", "Please connect to a database first (in Database tab)");
        return;
    }
    
    QStringList selectedPaths = m_selectedImagePaths.values();
    if (selectedPaths.isEmpty()) {
        QMessageBox::warning(this, "Error", "No images selected.");
        return;
    }

    if (!m_metadataGroup->isVisible()) {
        m_metadataGroup->setVisible(true);
        m_upsertButton->setText(QString("Confirm & Upsert %1 Images").arg(selectedPaths.size()));
        return;
    }
        
    m_upsertButton->setText(QString("Processing %1...").arg(selectedPaths.size()));
    m_upsertButton->setEnabled(false);
    QApplication::processEvents();
    
    try {
        int addedCount = 0;
        int updatedCount = 0;
        
        QString series = m_seriesCombo->currentText().trimmed();
        QStringList characters;
        for (const QString &c : m_charactersEdit->text().split(',')) {
            if (!c.trimmed().isEmpty()) characters.append(c.trimmed());
        }
        QStringList tags;
        for (auto it = m_tagCheckboxes.constBegin(); it != m_tagCheckboxes.constEnd(); ++it) {
            if (it.value()->isChecked()) {
                tags.append(it.key());
            }
        }

        for (const QString &path : selectedPaths) {
            // This logic depends heavily on the DatabaseManager C++ API
            QVariantMap existingData = db->getImageByPath(path); 
            
            if (!existingData.isEmpty()) {
                db->updateImage(
                    existingData["id"].toInt(),
                    series.isEmpty() ? QVariant() : series,
                    characters.isEmpty() ? QVariant() : characters,
                    tags.isEmpty() ? QVariant() : tags
                );
                updatedCount++;
            } else {
                db->addImage(
                    path,
                    QVariant(), // Embedding
                    series.isEmpty() ? QVariant() : series,
                    characters.isEmpty() ? QVariant() : characters,
                    tags.isEmpty() ? QVariant() : tags
                );
                addedCount++;
            }
        }
        
        clearScanImageGallery();
        if (!m_scannedDir.isEmpty()) {
            populateScanImageGallery(m_scannedDir);
        }
        
        m_dbTabRef->updateStatistics();
        m_dbTabRef->refreshAutocompleteData();
        
        QMessageBox::information(this, "Success", QString("Operation Complete:\nAdded: %1\nUpdated: %2").arg(addedCount).arg(updatedCount));
    
    } catch (...) { // Should be more specific
        QMessageBox::critical(this, "Error", "Failed to process images.");
    }
    
    m_metadataGroup->setVisible(false);
    updateButtonStates(true);
}

void ScanMetadataTab::refreshImageDirectory() {
    m_scanDirectoryPath->clear();
    m_scannedDir.clear();
    
    if (m_currentThumbnailLoaderThread && m_currentThumbnailLoaderThread->isRunning()) {
        m_currentThumbnailLoaderThread->quit();
        m_currentThumbnailLoaderThread->wait(1000);
    }
    
    m_currentThumbnailLoaderThread = nullptr;
    m_currentThumbnailLoaderWorker = nullptr;
    m_pathToLabelMap.clear();

    while (m_scanThumbnailLayout->count()) {
        QLayoutItem *item = m_scanThumbnailLayout->takeAt(0);
        if (QWidget *widget = item->widget()) {
            widget->deleteLater();
        }
        delete item;
    }
    m_scanImageList.clear();
    
    auto *readyLabel = new QLabel("Image preview cleared. Browse for a new directory.");
    readyLabel->setAlignment(Qt::AlignCenter);
    readyLabel->setStyleSheet("color: #b9bbbe;");
    int columns = calculateColumns(m_scanThumbnailWidget, m_approxItemWidth);
    m_scanThumbnailLayout->addWidget(readyLabel, 0, 0, 1, columns);

    updateButtonStates(m_dbTabRef && m_dbTabRef->getDatabase());
}

void ScanMetadataTab::deleteSelectedImages() {
    auto *db = m_dbTabRef->getDatabase();
    if (!db) {
        QMessageBox::warning(this, "Error", "Please connect to a database first (in Database tab)");
        return;
    }
        
    QStringList selectedPaths = m_selectedImagePaths.values();
    if (selectedPaths.isEmpty()) {
        QMessageBox::warning(this, "Error", "No images selected for deletion.");
        return;
    }

    auto confirm = QMessageBox::question(
        this, "Confirm Delete",
        QString("Are you sure you want to delete **%1** selected image entries from the database?\nThis action is irreversible.").arg(selectedPaths.size()),
        QMessageBox::Yes | QMessageBox::No
    );
    
    if (confirm == QMessageBox::Yes) {
        m_deleteSelectedButton->setText(QString("Deleting %1...").arg(selectedPaths.size()));
        m_deleteSelectedButton->setEnabled(false);
        QApplication::processEvents();
        
        try {
            QList<int> imageIds;
            for (const QString &path : selectedPaths) {
                QVariantMap imgData = db->getImageByPath(path);
                if (!imgData.isEmpty()) {
                    imageIds.append(imgData["id"].toInt());
                }
            }
            
            int count = 0;
            for (int imgId : imageIds) {
                db->deleteImage(imgId);
                count++;
            }
            
            clearScanImageGallery();
            if (!m_scannedDir.isEmpty()) {
                populateScanImageGallery(m_scannedDir);
            }
            m_dbTabRef->updateStatistics();
            QMessageBox::information(this, "Deleted", QString("Deleted %1 image entries from database.").arg(count));
        } catch (...) {
            QMessageBox::critical(this, "Error", "Failed to delete images.");
        }
        
        updateButtonStates(true);
    } else {
        QMessageBox::information(this, "Aborted", "Delete operation aborted by user.");
    }
}

void ScanMetadataTab::updateButtonStates(bool connected) {
    int selectionCount = m_selectedImagePaths.size();
    
    m_scanViewImageBtn->setEnabled(selectionCount > 0);
    m_scanViewImageBtn->setText(QString("View Full Size %1 Selected Image(s)").arg(selectionCount));
    
    m_refreshImageButton->setEnabled(true);

    if (m_selectedImagesArea->isVisible()) {
        m_viewBatchButton->setText(QString("Hide %1 Selected").arg(selectionCount));
    } else {
        m_viewBatchButton->setText(QString("View %1 Selected").arg(selectionCount));
    }
    m_viewBatchButton->setEnabled(selectionCount > 0 || m_selectedImagesArea->isVisible());

    if (m_metadataGroup->isVisible() && m_upsertButton->text().startsWith("Confirm & Upsert")) {
         m_upsertButton->setText(QString("Confirm & Upsert %1 Images").arg(selectionCount));
    } else {
        m_upsertButton->setText(QString("Add/Update %1 Selected Images").arg(selectionCount));
    }
    
    m_upsertButton->setEnabled(connected && selectionCount > 0);

    m_deleteSelectedButton->setText(QString("Delete %1 Images from DB").arg(selectionCount));
    m_deleteSelectedButton->setEnabled(connected && selectionCount > 0);
}

QVariantMap ScanMetadataTab::collect() {
    QVariantMap out;
    out["scan_directory"] = m_scanDirectoryPath->text().trimmed();
    out["selected_images"] = m_selectedImagePaths.values();
    return out;
}