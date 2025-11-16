#include "ImageCrawlTab.h"
#include "helpers/ImageCrawlWorker.h"
#include "components/OptionalField.h"
#include "styles/Style.h" // For apply_shadow_effect
#include <QFormLayout>
#include <QGroupBox>
#include <QFileDialog>
#include <QMessageBox>
#include <QDir>

ImageCrawlTab::ImageCrawlTab(bool dropdown, QWidget *parent)
    : BaseTab(parent), m_dropdown(dropdown), m_worker(nullptr) {

    m_lastBrowsedDownloadDir = getInitialDirectory();
    m_lastBrowsedScreenshotDir = m_lastBrowsedDownloadDir;

    auto *mainLayout = new QVBoxLayout(this);

    // --- Crawler Settings Group ---
    auto *crawlGroup = new QGroupBox("Web Crawler Settings");
    crawlGroup->setStyleSheet(R"(
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

    auto *formLayout = new QFormLayout();
    formLayout->setContentsMargins(10, 20, 10, 10);
    formLayout->setSpacing(15);

    // Target URL
    m_urlInput = new QLineEdit();
    m_urlInput->setPlaceholderText("https://example.com/gallery?page=1");
    formLayout->addRow("Target URL:", m_urlInput);

    // URL Replacement Fields
    m_replaceStrInput = new QLineEdit();
    m_replaceStrInput->setPlaceholderText("e.g., page=1 (optional)");
    formLayout->addRow("String to Replace:", m_replaceStrInput);

    m_replacementsInput = new QLineEdit();
    m_replacementsInput->setPlaceholderText("e.g., page=2, page=3, page=4 (comma-separated)");
    formLayout->addRow("Replacements:", m_replacementsInput);

    // Download Directory
    auto *downloadDirLayout = new QHBoxLayout();
    m_downloadDirPath = new QLineEdit(m_lastBrowsedDownloadDir);
    auto *btnBrowseDownload = new QPushButton("Browse...");
    connect(btnBrowseDownload, &QPushButton::clicked, this, &ImageCrawlTab::browseDownloadDirectory);
    apply_shadow_effect(btnBrowseDownload, "#000000", 8, 0, 3);
    downloadDirLayout->addWidget(m_downloadDirPath);
    downloadDirLayout->addWidget(btnBrowseDownload);
    formLayout->addRow("Download Dir:", downloadDirLayout);

    // Screenshot Directory
    auto *screenshotDirLayout = new QHBoxLayout();
    m_screenshotDirPath = new QLineEdit();
    m_screenshotDirPath->setPlaceholderText("Optional: directory for screenshots (None)");
    auto *btnBrowseScreenshot = new QPushButton("Browse...");
    connect(btnBrowseScreenshot, &QPushButton::clicked, this, &ImageCrawlTab::browseScreenshotDirectory);
    btnBrowseScreenshot->setStyleSheet(R"(
        QPushButton { background-color: #4f545c; padding: 6px 12px; }
        QPushButton:hover { background-color: #5865f2; }
    )");
    apply_shadow_effect(btnBrowseScreenshot, "#000000", 8, 0, 3);
    screenshotDirLayout->addWidget(m_screenshotDirPath);
    screenshotDirLayout->addWidget(btnBrowseScreenshot);

    auto *screenshotContainer = new QWidget();
    screenshotContainer->setLayout(screenshotDirLayout);

    m_screenshotField = new OptionalField("Screenshot Dir", screenshotContainer, false);
    formLayout->addRow(m_screenshotField);

    // Browser
    m_browserCombo = new QComboBox();
    m_browserCombo->addItems({"chrome", "firefox", "edge", "brave"});
    m_browserCombo->setCurrentText("brave");
    formLayout->addRow("Browser:", m_browserCombo);

    // Headless
    m_headlessCheckbox = new QCheckBox("Run in headless mode");
    m_headlessCheckbox->setChecked(true);
    m_headlessCheckbox->setStyleSheet(R"(
        QCheckBox::indicator {
            width: 16px; height: 16px; border: 1px solid #555;
            border-radius: 3px; background-color: #333;
        }
        QCheckBox::indicator:checked {
            background-color: #4CAF50; border: 1px solid #4CAF50;
        }
    )");
    formLayout->addRow("", m_headlessCheckbox);

    // Image Skip Count
    auto *skipLayout = new QHBoxLayout();
    m_skipFirstInput = new QLineEdit("0");
    m_skipFirstInput->setFixedWidth(50);
    m_skipFirstInput->setAlignment(Qt::AlignCenter);
    m_skipLastInput = new QLineEdit("9");
    m_skipLastInput->setFixedWidth(50);
    m_skipLastInput->setAlignment(Qt::AlignCenter);

    skipLayout->addWidget(new QLabel("Skip First:"));
    skipLayout->addWidget(m_skipFirstInput);
    skipLayout->addSpacing(20);
    skipLayout->addWidget(new QLabel("Skip Last:"));
    skipLayout->addWidget(m_skipLastInput);
    skipLayout->addStretch();
    formLayout->addRow("Image Skip Count:", skipLayout);

    crawlGroup->setLayout(formLayout);
    mainLayout->addWidget(crawlGroup);

    // --- Progress & Status ---
    m_statusLabel = new QLabel("Ready.");
    m_statusLabel->setAlignment(Qt::AlignCenter);
    m_statusLabel->setStyleSheet("color: #aaa; font-style: italic; padding: 8px;");
    mainLayout->addWidget(m_statusLabel);

    m_progressBar = new QProgressBar();
    m_progressBar->setRange(0, 0);
    m_progressBar->setTextVisible(false);
    m_progressBar->hide();
    mainLayout->addWidget(m_progressBar);

    // --- Run/Cancel Button Container ---
    m_buttonContainer = new QWidget();
    auto *buttonLayout = new QVBoxLayout(m_buttonContainer);
    buttonLayout->setContentsMargins(0, 0, 0, 0);

    // Run Button
    m_runButton = new QPushButton("Run Crawler");
    m_runButton->setStyleSheet(R"(
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #667eea, stop:1 #764ba2);
            color: white; font-weight: bold; font-size: 16px;
            padding: 14px; border-radius: 10px; min-height: 44px;
        }
        QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #764ba2, stop:1 #667eea); }
        QPushButton:disabled { background: #718096; }
    )");
    apply_shadow_effect(m_runButton, "#000000", 8, 0, 3);
    connect(m_runButton, &QPushButton::clicked, this, &ImageCrawlTab::startCrawl);
    buttonLayout->addWidget(m_runButton, 0, Qt::AlignBottom);

    // Cancel Button
    m_cancelButton = new QPushButton("Cancel Crawl");
    m_cancelButton->setStyleSheet(R"(
        QPushButton {
            background-color: #cc3333;
            color: white; font-weight: bold; font-size: 16px;
            padding: 14px; border-radius: 10px; min-height: 44px;
        }
        QPushButton:hover { background-color: #ff4444; }
    )");
    apply_shadow_effect(m_cancelButton, "#000000", 8, 0, 3);
    connect(m_cancelButton, &QPushButton::clicked, this, &ImageCrawlTab::cancelCrawl);
    m_cancelButton->hide();
    buttonLayout->addWidget(m_cancelButton, 0, Qt::AlignBottom);

    mainLayout->addWidget(m_buttonContainer);
    mainLayout->addStretch(1);
}

ImageCrawlTab::~ImageCrawlTab() {
    if (m_worker && m_worker->isRunning()) {
        m_worker->terminate();
        m_worker->wait();
    }
    // m_worker is cleaned up via deleteLater() in its connected slots
}

QString ImageCrawlTab::getInitialDirectory() {
    QDir dir(QDir::currentPath());
    while (dir.dirName() != "Image-Toolkit" && dir.cdUp());
    if (dir.dirName() == "Image-Toolkit") {
        return QDir::cleanPath(dir.filePath("data/tmp"));
    }
    return QDir::cleanPath(QDir::currentPath() + "/data/tmp");
}

void ImageCrawlTab::browseDownloadDirectory() {
    QString directory = QFileDialog::getExistingDirectory(
        this, "Select Download Directory", m_lastBrowsedDownloadDir);
    if (!directory.isEmpty()) {
        m_lastBrowsedDownloadDir = directory;
        m_downloadDirPath->setText(directory);
    }
}

void ImageCrawlTab::browseScreenshotDirectory() {
    QString directory = QFileDialog::getExistingDirectory(
        this, "Select Screenshot Directory", m_lastBrowsedScreenshotDir);
    if (!directory.isEmpty()) {
        m_lastBrowsedScreenshotDir = directory;
        m_screenshotDirPath->setText(directory);
    }
}

QVariantMap ImageCrawlTab::collectConfig() {
    QString url = m_urlInput->text().trimmed();
    QString downloadDir = m_downloadDirPath->text().trimmed();
    QString screenshotDir = m_screenshotDirPath->text().trimmed();
    QString skipFirstStr = m_skipFirstInput->text().trimmed();
    QString skipLastStr = m_skipLastInput->text().trimmed();
    QString replaceStr = m_replaceStrInput->text().trimmed();
    QString replacementsStr = m_replacementsInput->text().trimmed();
    
    QStringList replacementsList;
    if (!replacementsStr.isEmpty()) {
        for (const QString &r : replacementsStr.split(',')) {
            replacementsList.append(r.trimmed());
        }
    }

    if (url.isEmpty()) {
        QMessageBox::warning(this, "Missing URL", "Please enter a target URL.");
        return QVariantMap();
    }
    if (!url.startsWith("http://") && !url.startsWith("https://")) {
        QMessageBox::warning(this, "Invalid URL", "URL must start with http:// or https://");
        return QVariantMap();
    }
    if (downloadDir.isEmpty()) {
        QMessageBox::warning(this, "Missing Path", "Please select a download directory.");
        return QVariantMap();
    }
    if (!replaceStr.isEmpty() && replacementsList.isEmpty()) {
        QMessageBox::warning(this, "Invalid Input", "You provided a 'String to Replace' but no 'Replacements'.");
        return QVariantMap();
    }
    if (replaceStr.isEmpty() && !replacementsList.isEmpty()) {
        QMessageBox::warning(this, "Invalid Input", "You provided 'Replacements' but no 'String to Replace'.");
        return QVariantMap();
    }
    if (!replaceStr.isEmpty() && !url.contains(replaceStr)) {
        QMessageBox::warning(this, "Invalid Input", QString("The 'String to Replace' ('%1') was not found in the Target URL.").arg(replaceStr));
        return QVariantMap();
    }

    bool okFirst, okLast;
    int skipFirst = skipFirstStr.toInt(&okFirst);
    int skipLast = skipLastStr.toInt(&okLast);
    if (!okFirst || !okLast) {
        QMessageBox::warning(this, "Invalid Input", "Skip First and Skip Last must be integers.");
        return QVariantMap();
    }

    QVariantMap config;
    config["url"] = url;
    config["download_dir"] = downloadDir;
    config["screenshot_dir"] = screenshotDir.isEmpty() ? QVariant() : screenshotDir;
    config["headless"] = m_headlessCheckbox->isChecked();
    config["browser"] = m_browserCombo->currentText();
    config["skip_first"] = skipFirst;
    config["skip_last"] = skipLast;
    config["replace_str"] = replaceStr.isEmpty() ? QVariant() : replaceStr;
    config["replacements"] = replacementsList.isEmpty() ? QVariant() : replacementsList;

    return config;
}

void ImageCrawlTab::startCrawl() {
    QVariantMap config = collectConfig();
    if (config.isEmpty()) {
        return;
    }

    // UI: Show working state
    m_runButton->hide();
    m_cancelButton->show();
    m_statusLabel->setText("Initializing browser...");
    m_progressBar->show();
    m_progressBar->setRange(0, 0);

    // Start worker
    m_worker = new ImageCrawlWorker(config);
    connect(m_worker, &ImageCrawlWorker::status, m_statusLabel, &QLabel::setText);
    connect(m_worker, &ImageCrawlWorker::finishedSignal, this, &ImageCrawlTab::onCrawlDone); // Renamed 'finished' to 'finishedSignal' to avoid QObject conflict
    connect(m_worker, &ImageCrawlWorker::error, this, &ImageCrawlTab::onCrawlError);
    
    // Clean up worker when it's done
    connect(m_worker, &QThread::finished, m_worker, &QObject::deleteLater);

    m_worker->start();
}

void ImageCrawlTab::cancelCrawl() {
    if (m_worker && m_worker->isRunning()) {
        m_worker->terminate();
        onCrawlDone(0, "Crawl **cancelled** by user.");
        QMessageBox::information(this, "Cancelled", "The image crawl has been stopped.");
    }
}

void ImageCrawlTab::onCrawlDone(int count, const QString &message) {
    m_runButton->show();
    m_cancelButton->hide();
    m_runButton->setText("Run Crawler");
    m_progressBar->hide();
    m_statusLabel->setText(message);

    if (!message.toLower().contains("cancelled")) {
        QMessageBox::information(this, "Success", QString("%1\n\nSaved to:\n%2").arg(message, m_downloadDirPath->text()));
    }
    
    if (m_worker) {
        m_worker->deleteLater();
        m_worker = nullptr;
    }
}

void ImageCrawlTab::onCrawlError(const QString &msg) {
    m_runButton->show();
    m_cancelButton->hide();
    m_runButton->setText("Run Crawler");
    m_progressBar->hide();
    m_statusLabel->setText("Failed.");
    QMessageBox::critical(this, "Error", msg);
    
    if (m_worker) {
        m_worker->deleteLater();
        m_worker = nullptr;
    }
}