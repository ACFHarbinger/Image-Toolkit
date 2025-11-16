#include "MergeTab.h"
#include "components/ClickableLabel.h"
#include "components/MarqueeScrollArea.h"
#include "helpers/MergeWorker.h"
#include "helpers/ImageScannerWorker.h"
#include "helpers/BatchThumbnailLoaderWorker.h"
#include "styles/Style.h"
#include "utils/Definitions.h" // For SUPPORTED_IMG_FORMATS
#include <QFormLayout>
#include <QGroupBox>
#include <QFileDialog>
#include <QMessageBox>
#include <QDir>

MergeTab::MergeTab(bool dropdown, QWidget *parent)
    : BaseTab(parent) {
    
    // --- Find base directory ---
    try {
        QDir baseDir(QDir::currentPath());
        while (baseDir.dirName() != "Image-Toolkit" && baseDir.cdUp());
        if (baseDir.dirName() == "Image-Toolkit") {
            m_lastBrowsedDir = baseDir.filePath("data");
        } else {
            m_lastBrowsedDir = QDir(QDir::currentPath()).filePath("data");
        }
    } catch (...) {
        m_lastBrowsedDir = QDir::currentPath();
    }

    // --- Layout Setup ---
    auto *mainLayout = new QVBoxLayout(this);
    auto *scrollArea = new QScrollArea();
    scrollArea->setWidgetResizable(true);
    scrollArea->setStyleSheet("QScrollArea { border: none; }");

    auto *scrollContent = new QWidget();
    auto *contentLayout = new QVBoxLayout(scrollContent);
    contentLayout->setContentsMargins(0, 0, 0, 0);

    // === 1. Merge Settings ===
    auto *configGroup = new QGroupBox("Merge Settings");
    auto *configLayout = new QFormLayout(configGroup);

    m_direction = new QComboBox();
    m_direction->addItems({"horizontal", "vertical", "grid"});
    connect(m_direction, &QComboBox::currentTextChanged, this, &MergeTab::toggleGridVisibility);
    configLayout->addRow("Direction:", m_direction);

    m_spacing = new QSpinBox();
    m_spacing->setRange(0, 1000);
    m_spacing->setValue(10);
    configLayout->addRow("Spacing (px):", m_spacing);

    m_gridGroup = new QGroupBox("Grid Size");
    auto *gridLayout = new QHBoxLayout();
    m_gridRows = new QSpinBox();
    m_gridRows->setRange(1, 100);
    m_gridCols = new QSpinBox();
    m_gridCols->setRange(1, 100);
    gridLayout->addWidget(new QLabel("Rows:"));
    gridLayout->addWidget(m_gridRows);
    gridLayout->addWidget(new QLabel("Cols:"));
    gridLayout->addWidget(m_gridCols);
    m_gridGroup->setLayout(gridLayout);
    configLayout->addRow(m_gridGroup);
    m_gridGroup->hide();

    contentLayout->addWidget(configGroup);

    // === 2. Input Gallery ===
    auto *galleryGroup = new QGroupBox("Select Images to Merge");
    auto *galleryVBox = new QVBoxLayout(galleryGroup);

    auto *inputControls = new QHBoxLayout();
    m_inputPathInfo = new QLineEdit();
    m_inputPathInfo->setPlaceholderText("Scan directory (press Enter) or use buttons.");
    m_inputPathInfo->setStyleSheet("background-color: #333; color: #b9bbbe;");
    connect(m_inputPathInfo, &QLineEdit::returnPressed, this, &MergeTab::handleScanDirectoryReturn);

    auto *btnAddFiles = new QPushButton("Add Files");
    apply_shadow_effect(btnAddFiles, "#000000", 8, 0, 3);
    connect(btnAddFiles, &QPushButton::clicked, this, &MergeTab::browseFilesLogic);
    
    auto *btnScanDir = new QPushButton("Scan Directory");
    apply_shadow_effect(btnScanDir, "#000000", 8, 0, 3);
    connect(btnScanDir, &QPushButton::clicked, this, &MergeTab::browseScanDirectory);

    inputControls->addWidget(m_inputPathInfo);
    inputControls->addWidget(btnAddFiles);
    inputControls->addWidget(btnScanDir);
    galleryVBox->addLayout(inputControls);

    m_selectionLabel = new QLabel("0 images selected.");
    galleryVBox->addWidget(m_selectionLabel);

    // Top Gallery
    m_mergeScrollArea = new MarqueeScrollArea();
    m_mergeScrollArea->setWidgetResizable(true);
    m_mergeScrollArea->setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }");
    m_mergeScrollArea->setMinimumHeight(600);
    m_mergeThumbnailWidget = new QWidget();
    m_mergeThumbnailWidget->setStyleSheet("background-color: #2c2f33;");
    m_mergeThumbnailLayout = new QGridLayout(m_mergeThumbnailWidget);
    m_mergeThumbnailLayout->setAlignment(Qt::AlignTop | Qt::AlignHCenter);
    m_mergeScrollArea->setWidget(m_mergeThumbnailWidget);
    connect(m_mergeScrollArea, &MarqueeScrollArea::selectionChanged, this, &MergeTab::handleMarqueeSelection);
    galleryVBox->addWidget(m_mergeScrollArea, 1);

    // Bottom Selected Gallery
    m_selectedImagesArea = new MarqueeScrollArea();
    m_selectedImagesArea->setWidgetResizable(true);
    m_selectedImagesArea->setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }");
    m_selectedImagesArea->setMinimumHeight(600);
    m_selectedImagesWidget = new QWidget();
    m_selectedImagesWidget->setStyleSheet("background-color: #2c2f33;");
    m_selectedGridLayout = new QGridLayout(m_selectedImagesWidget);
    m_selectedGridLayout->setSpacing(10);
    m_selectedGridLayout->setAlignment(Qt::AlignTop | Qt::AlignHCenter);
    m_selectedImagesArea->setWidget(m_selectedImagesWidget);
    galleryVBox->addWidget(m_selectedImagesArea, 1);

    contentLayout->addWidget(galleryGroup, 6);
    scrollArea->setWidget(scrollContent);
    mainLayout->addWidget(scrollArea);

    // === 3. Action Buttons (Fixed Bottom) ===
    auto *actionVBox = new QVBoxLayout();
    m_runButton = new QPushButton("Run Merge");
    m_runButton->setStyleSheet(R"(
        QPushButton {
            background-color: #5865f2; color: white; font-weight: bold;
            font-size: 16px; padding: 14px; border-radius: 10px; min-height: 44px;
        }
        QPushButton:hover { background-color: #4754c4; }
        QPushButton:disabled { background: #718096; }
        QPushButton:pressed { background: #3f479a; }
    )");
    apply_shadow_effect(m_runButton, "#000000", 8, 0, 3);
    connect(m_runButton, &QPushButton::clicked, this, &MergeTab::startMerge);
    
    actionVBox->addWidget(m_runButton);

    m_statusLabel = new QLabel("");
    m_statusLabel->setAlignment(Qt::AlignCenter);
    m_statusLabel->setStyleSheet("color: #b9bbbe; font-style: italic; padding: 10px;");
    actionVBox->addWidget(m_statusLabel);

    mainLayout->addLayout(actionVBox);

    updateRunButtonState();
    toggleGridVisibility(m_direction->currentText());
    showPlaceholder("No images loaded. Use buttons above to add files or scan a directory.");
}

MergeTab::~MergeTab() {
    if (m_currentScanThread && m_currentScanThread->isRunning()) {
        m_currentScanThread->quit();
        m_currentScanThread->wait();
    }
    if (m_currentLoaderThread && m_currentLoaderThread->isRunning()) {
        m_currentLoaderThread->quit();
        m_currentLoaderThread->wait();
    }
    if (m_currentMergeThread && m_currentMergeThread->isRunning()) {
        m_currentMergeThread->quit();
        m_currentMergeThread->wait();
    }
}

// === THREAD SAFETY CLEANUP ===
void MergeTab::cleanupScanThreadRef() {
    m_currentScanThread = nullptr;
    m_currentScanWorker = nullptr;
}
void MergeTab::cleanupLoaderThreadRef() {
    m_currentLoaderThread = nullptr;
    m_currentLoaderWorker = nullptr;
}
void MergeTab::cleanupMergeThreadRef() {
    m_currentMergeThread = nullptr;
    m_currentMergeWorker = nullptr;
}

// === GALLERY MANAGEMENT ===
void MergeTab::clearGallery(QGridLayout *layout) {
    while (layout->count()) {
        QLayoutItem *item = layout->takeAt(0);
        if (QWidget *w = item->widget()) {
            w->deleteLater();
        }
        delete item;
    }
}

void MergeTab::showPlaceholder(const QString &text) {
    clearGallery(m_mergeThumbnailLayout);
    auto *lbl = new QLabel(text);
    lbl->setAlignment(Qt::AlignCenter);
    lbl->setStyleSheet("color: #b9bbbe; font-style: italic;");
    m_mergeThumbnailLayout->addWidget(lbl, 0, 0, 1, columns(m_mergeScrollArea), Qt::AlignCenter);
}

int MergeTab::columns(QScrollArea *area) const {
    int w = area->viewport()->width();
    return qMax(1, w / m_approxItemWidth);
}

void MergeTab::createThumbnailPlaceholder(int idx, const QString &path) {
    auto *label = new ClickableLabel(path);
    label->setFixedSize(m_thumbnailSize, m_thumbnailSize);
    label->setScaledContents(true);
    label->setStyleSheet("background:#444; border:1px solid #555;");
    label->setText("Loading...");
    label->setAlignment(Qt::AlignCenter);

    int colCount = columns(m_mergeScrollArea);
    int row = idx / colCount;
    int col = idx % colCount;
    m_mergeThumbnailLayout->addWidget(label, row, col, Qt::AlignCenter);
    m_pathToLabelMap[path] = label;

    connect(label, &ClickableLabel::pathClicked, this, &MergeTab::toggleSelection);
    connect(label, &ClickableLabel::pathDoubleClicked, [this](const QString &p) {
        QMessageBox::information(this, "Path", p);
    });
    
    QApplication::processEvents();
}

void MergeTab::updateThumbnailSlot(int idx, const QPixmap &pixmap, const QString &path) {
    ClickableLabel *label = m_pathToLabelMap.value(path);
    if (label && !pixmap.isNull()) {
        label->setPixmap(pixmap);
        label->setText("");
        updateLabelStyle(label, path, m_selectedImagePaths.contains(path));
    } else if (label) {
        label->setText("Load Error");
        updateLabelStyle(label, path, m_selectedImagePaths.contains(path));
    }
}

void MergeTab::updateLabelStyle(ClickableLabel *label, const QString &path, bool selected) {
    if (!label) return;
    if (selected) {
        label->setStyleSheet("border: 3px solid #5865f2;");
    } else {
        if (label->pixmap() && !label->pixmap()->isNull()) {
            label->setStyleSheet("border: 1px solid #4f545c;");
        } else {
            label->setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;");
        }
    }
}

// === SELECTION HANDLING ===
void MergeTab::toggleSelection(const QString &path) {
    bool selected;
    if (m_selectedImagePaths.contains(path)) {
        m_selectedImagePaths.remove(path);
        selected = false;
    } else {
        m_selectedImagePaths.insert(path);
        selected = true;
    }
        
    ClickableLabel *label = m_pathToLabelMap.value(path);
    if (label) {
        updateLabelStyle(label, path, selected);
    }
        
    refreshSelectedPanel();
    updateRunButtonState();
}

void MergeTab::handleMarqueeSelection(const QSet<QString> &paths, bool ctrlPressed) {
    QSet<QString> pathsToUpdate;
    if (!ctrlPressed) {
        QSet<QString> pathsToDeselect = m_selectedImagePaths - paths;
        m_selectedImagePaths = paths;
        pathsToUpdate = paths + pathsToDeselect;
    } else {
        pathsToUpdate = paths - m_selectedImagePaths;
        m_selectedImagePaths.unite(paths);
    }
    
    for (const QString &path : pathsToUpdate) {
        ClickableLabel *label = m_pathToLabelMap.value(path);
        if (label) {
            updateLabelStyle(label, path, m_selectedImagePaths.contains(path));
        }
    }
            
    refreshSelectedPanel();
    updateRunButtonState();
}

void MergeTab::refreshSelectedPanel() {
    clearGallery(m_selectedGridLayout);
    m_selectedCardMap.clear();
    
    int cols = columns(m_selectedImagesArea);
    QStringList sortedPaths = m_selectedImagePaths.values();
    std::sort(sortedPaths.begin(), sortedPaths.end());

    int i = 0;
    for (const QString &path : sortedPaths) {
        ClickableLabel *src = m_pathToLabelMap.value(path);
        QPixmap pixmap;
        if (src && src->pixmap()) {
            pixmap = *src->pixmap();
        } else {
            pixmap = QPixmap(path);
        }

        auto *card = new ClickableLabel(path);
        card->setFixedSize(m_thumbnailSize, m_thumbnailSize);
        card->setScaledContents(True);
        
        if (!pixmap.isNull()) {
            card->setPixmap(pixmap.scaled(m_thumbnailSize, m_thumbnailSize, Qt::KeepAspectRatio, Qt::SmoothTransformation));
        } else {
            card->setText("Error");
            card->setStyleSheet("background: #333; color: red;");
        }
        connect(card, &ClickableLabel::pathClicked, [this, path](){ toggleSelection(path); });

        int row = i / cols;
        int col = i % cols;
        m_selectedGridLayout->addWidget(card, row, col, Qt::AlignCenter);
        m_selectedCardMap[path] = card;
        i++;
    }
}

// === INPUT LOGIC ===
void MergeTab::browseFilesLogic() {
    QStringList files = QFileDialog::getOpenFileNames(
        this, "Select Images", m_lastBrowsedDir,
        "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
    );
    if (!files.isEmpty()) {
        m_lastBrowsedDir = QFileInfo(files[0]).absolutePath();
        QStringList newPaths = m_mergeImageList;
        int addedCount = 0;
        for (const QString &f : files) {
            if (!newPaths.contains(f)) {
                newPaths.append(f);
                addedCount++;
            }
        }
        
        displayScanResults(newPaths); // This will reload everything
        m_inputPathInfo->setText(QString("Added %1 files.").arg(addedCount));
    }
}

void MergeTab::handleScanDirectoryReturn() {
    QString directory = m_inputPathInfo->text().trimmed();
    if (!directory.isEmpty() && QFileInfo(directory).isDir()) {
        populateScanGallery(directory);
    } else {
        browseScanDirectory();
    }
}

void MergeTab::browseScanDirectory() {
    QString directory = QFileDialog::getExistingDirectory(
        this, "Scan Directory", m_lastBrowsedDir
    );
    if (!directory.isEmpty()) {
        m_lastBrowsedDir = directory;
        m_inputPathInfo->setText(directory);
        populateScanGallery(directory);
    }
}
            
void MergeTab::handleScanError(const QString &message) {
    clearGallery(m_mergeThumbnailLayout);
    QMessageBox::warning(this, "Error Scanning", message);
    showPlaceholder("Browse for a directory.");
}

void MergeTab::populateScanGallery(const QString &directory) {
    m_scannedDir = directory;
    
    if (m_currentScanThread && m_currentScanThread->isRunning()) {
        m_currentScanThread->quit();
        m_currentScanThread->wait(2000);
    }
    if (m_currentLoaderThread && m_currentLoaderThread->isRunning()) {
        m_currentLoaderThread->quit();
        m_currentLoaderThread->wait(2000);
    }

    clearGallery(m_mergeThumbnailLayout);
    m_pathToLabelMap.clear();
    m_mergeImageList.clear();

    auto *loadingLabel = new QLabel("Scanning directory, please wait...");
    loadingLabel->setAlignment(Qt::AlignCenter);
    loadingLabel->setStyleSheet("color: #b9bbbe;");
    m_mergeThumbnailLayout->addWidget(loadingLabel, 0, 0, 1, 10);
    
    m_currentScanWorker = new ImageScannerWorker(directory);
    m_currentScanThread = new QThread();
    m_currentScanWorker->moveToThread(m_currentScanThread);

    connect(m_currentScanThread, &QThread::started, m_currentScanWorker, &ImageScannerWorker::runScan);
    connect(m_currentScanWorker, &ImageScannerWorker::scanFinished, this, &MergeTab::displayScanResults);
    connect(m_currentScanWorker, &ImageScannerWorker::scanError, this, &MergeTab::handleScanError);

    connect(m_currentScanWorker, &ImageScannerWorker::scanFinished, m_currentScanThread, &QThread::quit);
    connect(m_currentScanWorker, &ImageScannerWorker::scanFinished, m_currentScanWorker, &QObject::deleteLater);
    connect(m_currentScanWorker, &ImageScannerWorker::scanError, m_currentScanThread, &QThread::quit);
    connect(m_currentScanWorker, &ImageScannerWorker::scanError, m_currentScanWorker, &QObject::deleteLater);
    connect(m_currentScanThread, &QThread::finished, m_currentScanThread, &QObject::deleteLater);
    connect(m_currentScanThread, &QThread::finished, this, &MergeTab::cleanupScanThreadRef);
    
    m_currentScanThread->start();
}

void MergeTab::displayScanResults(const QStringList &imagePaths) {
    m_mergeImageList = imagePaths;
    std::sort(m_mergeImageList.begin(), m_mergeImageList.end());
    
    if (!m_scannedDir.isEmpty()) {
         m_inputPathInfo->setText(QString("Source: %1 | %2 images").arg(QFileInfo(m_scannedDir).fileName()).arg(imagePaths.size()));
    }
    
    clearGallery(m_mergeThumbnailLayout);
    m_pathToLabelMap.clear();

    if (imagePaths.isEmpty()) {
        showPlaceholder("No supported images found.");
        return;
    }

    if (m_currentLoaderThread && m_currentLoaderThread->isRunning()) {
        m_currentLoaderThread->quit();
        m_currentLoaderThread->wait(2000);
    }

    m_currentLoaderWorker = new BatchThumbnailLoaderWorker(m_mergeImageList, m_thumbnailSize);
    m_currentLoaderThread = new QThread();
    m_currentLoaderWorker->moveToThread(m_currentLoaderThread);
    
    connect(m_currentLoaderThread, &QThread::started, m_currentLoaderWorker, &BatchThumbnailLoaderWorker::runLoadBatch);
    connect(m_currentLoaderWorker, &BatchThumbnailLoaderWorker::createPlaceholder, this, &MergeTab::createThumbnailPlaceholder);
    connect(m_currentLoaderWorker, &BatchThumbnailLoaderWorker::thumbnailLoaded, this, &MergeTab::updateThumbnailSlot);
    
    connect(m_currentLoaderWorker, &BatchThumbnailLoaderWorker::loadingFinished, m_currentLoaderThread, &QThread::quit);
    connect(m_currentLoaderWorker, &BatchThumbnailLoaderWorker::loadingFinished, m_currentLoaderWorker, &QObject::deleteLater);
    connect(m_currentLoaderThread, &QThread::finished, m_currentLoaderThread, &QObject::deleteLater);
    connect(m_currentLoaderThread, &QThread::finished, this, &MergeTab::cleanupLoaderThreadRef);
    
    m_currentLoaderThread->start();
}

// === MERGE EXECUTION ===
void MergeTab::startMerge() {
    if (m_selectedImagePaths.size() < 2) {
        QMessageBox::warning(this, "Invalid", "Select at least 2 images.");
        return;
    }

    QString output_path = QFileDialog::getSaveFileName(
        this, "Save Merged Image", m_lastBrowsedDir, "PNG (*.png)"
    );
    if (output_path.isEmpty()) {
        m_statusLabel->setText("Cancelled.");
        return;
    }
    if (!output_path.toLower().endsWith(".png")) {
        output_path += ".png";
    }
    m_lastBrowsedDir = QFileInfo(output_path).absolutePath();

    QVariantMap config = collect(output_path);
    m_runButton->setEnabled(false);
    m_runButton->setText("Merging...");
    m_statusLabel->setText("Processing...");

    if (m_currentMergeThread && m_currentMergeThread->isRunning()) {
        m_currentMergeThread->quit();
        m_currentMergeThread->wait(2000);
    }

    m_currentMergeWorker = new MergeWorker(config);
    m_currentMergeThread = new QThread();
    m_currentMergeWorker->moveToThread(m_currentMergeThread);
    
    connect(m_currentMergeThread, &QThread::started, m_currentMergeWorker, &MergeWorker::run);
    connect(m_currentMergeWorker, &MergeWorker::progress, this, &MergeTab::updateProgress);
    connect(m_currentMergeWorker, &MergeWorker::finished, this, &MergeTab::onMergeDone);
    connect(m_currentMergeWorker, &MergeWorker::error, this, &MergeTab::onMergeError); // 'scan_error' is 'error'
    
    connect(m_currentMergeWorker, &MergeWorker::finished, m_currentMergeThread, &QThread::quit);
    connect(m_currentMergeWorker, &MergeWorker::finished, m_currentMergeWorker, &QObject::deleteLater);
    connect(m_currentMergeWorker, &MergeWorker::error, m_currentMergeThread, &QThread::quit);
    connect(m_currentMergeWorker, &MergeWorker::error, m_currentMergeWorker, &QObject::deleteLater);
    connect(m_currentMergeThread, &QThread::finished, m_currentMergeThread, &QObject::deleteLater);
    connect(m_currentMergeThread, &QThread::finished, this, &MergeTab::cleanupMergeThreadRef);
    
    m_currentMergeThread->start();
}

void MergeTab::updateProgress(int cur, int total) {
    m_statusLabel->setText(QString("Merging %1/%2...").arg(cur).arg(total));
}

void MergeTab::onMergeDone(const QString &path) {
    updateRunButtonState();
    m_statusLabel->setText(QString("Saved: %1").arg(QFileInfo(path).fileName()));
    QMessageBox::information(this, "Success", QString("Merge complete!\n%1").arg(path));
}

void MergeTab::onMergeError(const QString &msg) {
    updateRunButtonState();
    m_statusLabel->setText("Failed.");
    QMessageBox::critical(this, "Error", msg);
}

QVariantMap MergeTab::collect(const QString &outputPath) {
    QStringList formats;
    for(const QString& f : SUPPORTED_IMG_FORMATS) {
        formats.append(f.trimmed().remove(0, 1)); // .png -> png
    }

    QVariantMap config;
    config["direction"] = m_direction->currentText();
    config["input_path"] = m_selectedImagePaths.values();
    config["output_path"] = outputPath;
    config["input_formats"] = formats;
    config["spacing"] = m_spacing->value();
    
    if (m_direction->currentText() == "grid") {
        config["grid_size"] = QVariantList{m_gridRows->value(), m_gridCols->value()};
    } else {
        config["grid_size"] = QVariant();
    }
    return config;
}

// === UI UTILS ===
void MergeTab::updateRunButtonState() {
    int count = m_selectedImagePaths.size();
    m_selectionLabel->setText(QString("%1 images selected.").arg(count));
    if (count < 2) {
        m_runButton->setEnabled(false);
        m_runButton->setText("Run Merge (Select 2+ images)");
    } else {
        m_runButton->setEnabled(true);
        m_runButton->setText(QString("Run Merge (%1 images)").arg(count));
    }
    m_statusLabel->setText(count < 2 ? "" : QString("Ready to merge %1 images.").arg(count));
}

void MergeTab::toggleGridVisibility(const QString &direction) {
    m_gridGroup->setVisible(direction == "grid");
}