#include "DeleteTab.h"
#include "helpers/DeletionWorker.h"
#include "components/OptionalField.h"
#include "styles/Style.h"
#include "utils/Definitions.h" // For SUPPORTED_IMG_FORMATS
#include <QFormLayout>
#include <QGroupBox>
#include <QFileDialog>
#include <QMessageBox>
#include <QDir>

DeleteTab::DeleteTab(bool dropdown, QWidget *parent)
    : BaseTab(parent), m_dropdown(dropdown), m_worker(nullptr) {

    auto *mainLayout = new QVBoxLayout(this);

    // --- Delete Targets Group ---
    auto *targetGroup = new QGroupBox("Delete Targets");
    auto *targetLayout = new QFormLayout(targetGroup);

    // Target path
    auto *vTargetGroup = new QVBoxLayout();
    m_targetPath = new QLineEdit();
    vTargetGroup->addWidget(m_targetPath);

    auto *hButtons = new QHBoxLayout();
    auto *btnTargetFile = new QPushButton("Choose file...");
    apply_shadow_effect(btnTargetFile, "#000000", 8, 0, 3);
    connect(btnTargetFile, &QPushButton::clicked, this, &DeleteTab::browseFile);
    auto *btnTargetDir = new QPushButton("Choose directory...");
    apply_shadow_effect(btnTargetDir, "#000000", 8, 0, 3);
    connect(btnTargetDir, &QPushButton::clicked, this, &DeleteTab::browseDirectory);
    hButtons->addWidget(btnTargetFile);
    hButtons->addWidget(btnTargetDir);
    vTargetGroup->addLayout(hButtons);
    targetLayout->addRow("Target path (file or dir):", vTargetGroup);

    mainLayout->addWidget(targetGroup);

    // --- Delete Settings Group ---
    auto *settingsGroup = new QGroupBox("Delete Settings");
    auto *settingsLayout = new QFormLayout(settingsGroup);

    // Extensions
    if (m_dropdown) {
        m_selectedExtensions.clear();
        auto *extLayout = new QVBoxLayout();
        auto *btnLayout = new QHBoxLayout();
        
        for (const QString &ext : SUPPORTED_IMG_FORMATS) {
            auto *btn = new QPushButton(ext);
            btn->setCheckable(true);
            btn->setStyleSheet("QPushButton:hover { background-color: #3498db; }");
            apply_shadow_effect(btn, "#000000", 8, 0, 3);
            connect(btn, &QPushButton::clicked, [this, ext, btn](bool checked) {
                toggleExtension(ext, checked);
            });
            btnLayout->addWidget(btn);
            m_extensionButtons[ext] = btn;
        }
        extLayout->addLayout(btnLayout);

        auto *allBtnLayout = new QHBoxLayout();
        auto *btnAddAll = new QPushButton("Add All");
        btnAddAll->setStyleSheet("background-color: green; color: white;");
        apply_shadow_effect(btnAddAll, "#000000", 8, 0, 3);
        connect(btnAddAll, &QPushButton::clicked, this, &DeleteTab::addAllExtensions);
        auto *btnRemoveAll = new QPushButton("Remove All");
        btnRemoveAll->setStyleSheet("background-color: red; color: white;");
        apply_shadow_effect(btnRemoveAll, "#000000", 8, 0, 3);
        connect(btnRemoveAll, &QPushButton::clicked, this, &DeleteTab::removeAllExtensions);
        allBtnLayout->addWidget(btnAddAll);
        allBtnLayout->addWidget(btnRemoveAll);
        extLayout->addLayout(allBtnLayout);

        auto *extContainer = new QWidget();
        extContainer->setLayout(extLayout);
        m_extensionsField = new OptionalField("Target extensions", extContainer, false);
        settingsLayout->addRow(m_extensionsField);
    } else {
        m_targetExtensions = new QLineEdit();
        m_targetExtensions->setPlaceholderText("e.g. .txt .jpg or txt jpg");
        settingsLayout->addRow("Target extensions (optional):", m_targetExtensions);
    }

    // Confirmation
    m_confirmCheckbox = new QCheckBox("Require confirmation before delete (recommended)");
    m_confirmCheckbox->setChecked(true);
    settingsLayout->addRow(m_confirmCheckbox);

    mainLayout->addWidget(settingsGroup);
    mainLayout->addStretch(1);

    // --- Run Buttons Layout ---
    auto *runButtonsLayout = new QHBoxLayout();
    const QString SHARED_BUTTON_STYLE = R"(
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #667eea, stop:1 #764ba2);
            color: white; font-weight: bold; font-size: 14px;
            padding: 14px 8px; border-radius: 10px; min-height: 44px;
        }
        QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #764ba2, stop:1 #667eea); }
        QPushButton:disabled { background: #718096; }
        QPushButton:pressed { background: #5a67d8; }
    )";

    m_btnDeleteFiles = new QPushButton("Delete Files Only");
    m_btnDeleteFiles->setStyleSheet(SHARED_BUTTON_STYLE);
    apply_shadow_effect(m_btnDeleteFiles, "#000000", 8, 0, 3);
    connect(m_btnDeleteFiles, &QPushButton::clicked, [this]() { startDeletion("files"); });
    runButtonsLayout->addWidget(m_btnDeleteFiles);

    m_btnDeleteDirectory = new QPushButton("Delete Directory and Contents");
    m_btnDeleteDirectory->setStyleSheet(SHARED_BUTTON_STYLE);
    apply_shadow_effect(m_btnDeleteDirectory, "#000000", 8, 0, 3);
    connect(m_btnDeleteDirectory, &QPushButton::clicked, [this]() { startDeletion("directory"); });
    runButtonsLayout->addWidget(m_btnDeleteDirectory);

    mainLayout->addLayout(runButtonsLayout);

    // --- Status ---
    m_statusLabel = new QLabel("Ready.");
    m_statusLabel->setAlignment(Qt::AlignCenter);
    m_statusLabel->setStyleSheet("color: #666; font-style: italic; padding: 10px;");
    mainLayout->addWidget(m_statusLabel);
}

DeleteTab::~DeleteTab() {
    if (m_worker && m_worker->isRunning()) {
        m_worker->terminate();
        m_worker->wait();
    }
}

void DeleteTab::toggleExtension(const QString &ext, bool checked) {
    QPushButton *btn = m_extensionButtons[ext];
    if (checked) {
        m_selectedExtensions.insert(ext);
        btn->setStyleSheet(R"(
            QPushButton:checked { background-color: #3320b5; color: white; }
            QPushButton:hover { background-color: #00838a; }
        )");
        apply_shadow_effect(btn, "#000000", 8, 0, 3);
    } else {
        m_selectedExtensions.remove(ext);
        btn->setStyleSheet("QPushButton:hover { background-color: #3498db; }");
        apply_shadow_effect(btn, "#000000", 8, 0, 3);
    }
}

void DeleteTab::addAllExtensions() {
    for (auto it = m_extensionButtons.begin(); it != m_extensionButtons.end(); ++it) {
        it.value()->setChecked(true);
        toggleExtension(it.key(), true);
    }
}

void DeleteTab::removeAllExtensions() {
    for (auto it = m_extensionButtons.begin(); it != m_extensionButtons.end(); ++it) {
        it.value()->setChecked(false);
        toggleExtension(it.key(), false);
    }
}

QString DeleteTab::getStartingDir() {
    QDir dir(QDir::currentPath());
    while (dir.dirName() != "Image-Toolkit" && dir.cdUp());
    if (dir.dirName() == "Image-Toolkit") {
        QString dataDir = QDir::cleanPath(dir.filePath("data"));
        if (QFileInfo::exists(dataDir) && QFileInfo(dataDir).isDir()) {
            return dataDir;
        }
    }
    return QDir::currentPath();
}

void DeleteTab::browseFile() {
    QString startDir = getStartingDir();
    QStringList filters;
    QStringList imageFilters;
    for(const QString& ext : SUPPORTED_IMG_FORMATS) {
        imageFilters.append("*" + ext);
    }
    filters.append(QString("Image Files (%1)").arg(imageFilters.join(" ")));
    filters.append("All Files (*)");

    QString filePath = QFileDialog::getOpenFileName(
        this, "Select File", startDir, filters.join(";;"));
    
    if (!filePath.isEmpty()) {
        m_targetPath->setText(filePath);
    }
}

void DeleteTab::browseDirectory() {
    QString startDir = getStartingDir();
    QString directory = QFileDialog::getExistingDirectory(
        this, "Select Directory to Delete", startDir,
        QFileDialog::ShowDirsOnly | QFileDialog::DontResolveSymlinks);
    
    if (!directory.isEmpty()) {
        m_targetPath->setText(directory);
    }
}

bool DeleteTab::isValid(const QString &mode) {
    QString path = m_targetPath->text().trimmed();
    if (path.isEmpty() || !QFileInfo::exists(path)) {
        QMessageBox::warning(this, "Invalid Path", "Please select a valid file or folder.");
        return false;
    }
    
    if (mode == "directory" && !QFileInfo(path).isDir()) {
        QMessageBox::warning(this, "Invalid Target", "The 'Delete Directory & Contents' action requires a directory path.");
        return false;
    }
    return true;
}

void DeleteTab::startDeletion(const QString &mode) {
    if (!isValid(mode)) {
        return;
    }

    QVariantMap config = collect(mode);
    config["require_confirm"] = m_confirmCheckbox->isChecked();

    m_btnDeleteFiles->setEnabled(False);
    m_btnDeleteDirectory->setEnabled(False);
    m_statusLabel->setText(QString("Starting %1 deletion...").arg(mode));
    QApplication::processEvents();

    m_worker = new DeletionWorker(config);
    
    connect(m_worker, &DeletionWorker::confirmSignal, this, &DeleteTab::handleConfirmationRequest);
    connect(m_worker, &DeletionWorker::progress, this, &DeleteTab::updateProgress);
    connect(m_worker, &DeletionWorker::finishedSignal, this, &DeleteTab::onDeletionDone); // Renamed
    connect(m_worker, &DeletionWorker::error, this, &DeleteTab::onDeletionError);
    
    // Clean up worker when done
    connect(m_worker, &QThread::finished, m_worker, &QObject::deleteLater);

    m_worker->start();
}

void DeleteTab::handleConfirmationRequest(const QString &message, int totalItems) {
    QString title = (totalItems == 1 && message.contains("directory")) 
                  ? "Confirm Directory Deletion" 
                  : "Confirm File Deletion";
    
    QMessageBox::StandardButton reply = QMessageBox::question(
        this, title, message,
        QMessageBox::Yes | QMessageBox::No, QMessageBox::No
    );
    
    bool response = (reply == QMessageBox::Yes);
    m_worker->setConfirmationResponse(response); // Assumes this slot exists
}

void DeleteTab::updateProgress(int deleted, int total) {
    m_statusLabel->setText(QString("Deleted %1 of %2...").arg(deleted).arg(total));
}

void DeleteTab::onDeletionDone(int count, const QString &msg) {
    m_btnDeleteFiles->setEnabled(True);
    m_btnDeleteDirectory->setEnabled(True);
    m_statusLabel->setText(msg);
    QMessageBox::information(this, "Complete", msg);
    m_worker = nullptr; // Worker is deleted via deleteLater
}

void DeleteTab::onDeletionError(const QString &msg) {
    m_btnDeleteFiles->setEnabled(True);
    m_btnDeleteDirectory->setEnabled(True);
    m_statusLabel->setText("Failed.");
    QMessageBox::critical(this, "Error", msg);
    m_worker = nullptr; // Worker is deleted via deleteLater
}

QVariantMap DeleteTab::collect(const QString &mode) {
    QStringList extensions;
    if (mode == "files") {
        if (m_dropdown && !m_selectedExtensions.isEmpty()) {
            extensions = QStringList(m_selectedExtensions.values());
        } else if (!m_dropdown) {
            extensions = joinListStr(m_targetExtensions->text().trimmed());
        } else {
            extensions = SUPPORTED_IMG_FORMATS;
        }
    }
    
    QStringList cleanedExtensions;
    for (QString ext : extensions) {
        ext = ext.trimmed();
        if (ext.startsWith('.')) {
            ext = ext.mid(1);
        }
        if (!ext.isEmpty()) {
            cleanedExtensions.append(ext);
        }
    }
    
    QVariantMap config;
    config["target_path"] = m_targetPath->text().trimmed();
    config["mode"] = mode;
    config["target_extensions"] = cleanedExtensions;
    return config;
}

QStringList DeleteTab::joinListStr(const QString &text) {
    QStringList parts = text.replace(',', ' ').split(' ', Qt::SkipEmptyParts);
    QStringList result;
    for (QString item : parts) {
        item = item.trimmed();
        if (item.startsWith('.')) {
            item = item.mid(1);
        }
        if (!item.isEmpty()) {
            result.append(item);
        }
    }
    return result;
}