#include "ConvertTab.h"
#include "src/utils/Definitions.h" // For SUPPORTED_IMG_FORMATS

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QFormLayout>
#include <QGroupBox>
#include <QLineEdit>
#include <QPushButton>
#include <QCheckBox>
#include <QLabel>
#include <QMessageBox>
#include <QFileDialog>
#include <QDir>
#include <QFileInfo>
#include <QGraphicsDropShadowEffect>

ConvertTab::ConvertTab(bool dropdown, QWidget *parent)
    : BaseTab(parent), m_dropdown(dropdown), m_worker(nullptr),
      m_outputField(nullptr), m_formatsField(nullptr), m_inputFormats(nullptr)
{
    setupUi();
}

ConvertTab::~ConvertTab()
{
    // Ensure the worker thread is properly terminated and deleted
    if (m_worker) {
        if (m_worker->isRunning()) {
            m_worker->terminate();
            m_worker->wait();
        }
        delete m_worker;
    }
}

void ConvertTab::setupUi()
{
    QVBoxLayout *mainLayout = new QVBoxLayout(this);

    // --- Convert Targets Group ---
    QGroupBox *targetGroup = new QGroupBox("Convert Targets");
    QFormLayout *targetLayout = new QFormLayout(targetGroup);

    // Input path
    QVBoxLayout *vInputGroup = new QVBoxLayout();
    m_inputPath = new QLineEdit();
    vInputGroup->addWidget(m_inputPath);

    QHBoxLayout *hButtons = new QHBoxLayout();
    QPushButton *btnInputFile = new QPushButton("Choose file...");
    connect(btnInputFile, &QPushButton::clicked, this, &ConvertTab::browseFileInput);
    applyShadowEffect(btnInputFile);
    
    QPushButton *btnInputDir = new QPushButton("Choose directory...");
    connect(btnInputDir, &QPushButton::clicked, this, &ConvertTab::browseDirectoryInput);
    applyShadowEffect(btnInputDir);

    hButtons->addWidget(btnInputFile);
    hButtons->addWidget(btnInputDir);
    vInputGroup->addLayout(hButtons);
    targetLayout->addRow("Input path (file or dir):", vInputGroup);
    
    mainLayout->addWidget(targetGroup);

    // --- Convert Settings Group ---
    QGroupBox *settingsGroup = new QGroupBox("Convert Settings");
    QFormLayout *settingsLayout = new QFormLayout(settingsGroup);

    // Output format
    m_outputFormat = new QLineEdit("png");
    settingsLayout->addRow("Output format:", m_outputFormat);

    // Output path
    QHBoxLayout *hOutput = new QHBoxLayout();
    m_outputPath = new QLineEdit();
    QPushButton *btnOutput = new QPushButton("Browse...");
    connect(btnOutput, &QPushButton::clicked, this, &ConvertTab::browseOutput);
    applyShadowEffect(btnOutput);
    hOutput->addWidget(m_outputPath);
    hOutput->addWidget(btnOutput);

    if (m_dropdown) {
        QWidget *outputContainer = new QWidget();
        outputContainer->setLayout(hOutput);
        m_outputField = new OptionalField("Output path", outputContainer, false);
        settingsLayout->addRow(m_outputField);
    } else {
        settingsLayout->addRow("Output path (optional):", hOutput);
    }

    // Input formats
    if (m_dropdown) {
        QVBoxLayout *formatsLayout = new QVBoxLayout();
        QHBoxLayout *btnLayout = new QHBoxLayout();

        for (const QString &fmt : SUPPORTED_IMG_FORMATS) {
            QPushButton *btn = new QPushButton(fmt);
            btn->setCheckable(true);
            btn->setStyleSheet("QPushButton:hover { background-color: #3498db; }");
            applyShadowEffect(btn);
            
            // Use a lambda to capture the format string
            connect(btn, &QPushButton::clicked, this, [this, fmt](bool checked){
                this->toggleFormat(fmt, checked);
            });
            
            btnLayout->addWidget(btn);
            m_formatButtons[fmt] = btn;
        }
        formatsLayout->addLayout(btnLayout);

        QHBoxLayout *allBtnLayout = new QHBoxLayout();
        m_btnAddAll = new QPushButton("Add All");
        m_btnAddAll->setStyleSheet("background-color: green; color: white;");
        applyShadowEffect(m_btnAddAll);
        connect(m_btnAddAll, &QPushButton::clicked, this, &ConvertTab::addAllFormats);

        m_btnRemoveAll = new QPushButton("Remove All");
        m_btnRemoveAll->setStyleSheet("background-color: red; color: white;");
        applyShadowEffect(m_btnRemoveAll);
        connect(m_btnRemoveAll, &QPushButton::clicked, this, &ConvertTab::removeAllFormats);
        
        allBtnLayout->addWidget(m_btnAddAll);
        allBtnLayout->addWidget(m_btnRemoveAll);
        formatsLayout->addLayout(allBtnLayout);

        QWidget *formatsContainer = new QWidget();
        formatsContainer->setLayout(formatsLayout);
        m_formatsField = new OptionalField("Input formats", formatsContainer, false);
        settingsLayout->addRow(m_formatsField);
    } else {
        m_inputFormats = new QLineEdit();
        m_inputFormats->setPlaceholderText("e.g. jpg png gif — separate with commas or spaces");
        settingsLayout->addRow("Input formats (optional):", m_inputFormats);
    }

    // Delete checkbox
    m_deleteCheckbox = new QCheckBox("Delete original files after conversion");
    m_deleteCheckbox->setStyleSheet(R"(
        QCheckBox::indicator {
            width: 16px; height: 16px; border: 1px solid #555;
            border-radius: 3px; background-color: #333;
        }
        QCheckBox::indicator:checked {
            background-color: #4CAF50; border: 1px solid #4CAF50;
            /* Note: image: url() paths need to be adjusted for C++ resources */
            /* image: url(./src/gui/assets/check.png); */
        }
    )");
    m_deleteCheckbox->setChecked(true);
    settingsLayout->addRow(m_deleteCheckbox);

    mainLayout->addWidget(settingsGroup);
    
    // Add a stretch to push button/status to the bottom
    mainLayout->addStretch(1);

    // --- Button Container ---
    m_buttonContainer = new QWidget();
    QVBoxLayout *buttonLayout = new QVBoxLayout(m_buttonContainer);
    buttonLayout->setContentsMargins(0, 0, 0, 0);

    // RUN CONVERSION BUTTON
    m_runButton = new QPushButton("Run Conversion");
    m_runButton->setStyleSheet(R"(
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #667eea, stop:1 #764ba2);
            color: white; font-weight: bold; font-size: 16px;
            padding: 12px; border-radius: 8px; min-height: 40px;
        }
        QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #764ba2, stop:1 #667eea); }
        QPushButton:disabled { background: #555; }
        QPushButton:pressed { background: #5a67d8; }
    )");
    applyShadowEffect(m_runButton);
    connect(m_runButton, &QPushButton::clicked, this, &ConvertTab::startConversion);
    buttonLayout->addWidget(m_runButton);

    // CANCEL BUTTON
    m_cancelButton = new QPushButton("Cancel Conversion");
    m_cancelButton->setStyleSheet(R"(
        QPushButton {
            background-color: #cc3333; /* Red color for cancellation */
            color: white; font-weight: bold; font-size: 16px;
            padding: 12px; border-radius: 8px; min-height: 40px;
        }
        QPushButton:hover { background-color: #ff4444; }
    )");
    applyShadowEffect(m_cancelButton);
    connect(m_cancelButton, &QPushButton::clicked, this, &ConvertTab::cancelConversion);
    m_cancelButton->hide();
    buttonLayout->addWidget(m_cancelButton);

    mainLayout->addWidget(m_buttonContainer);

    // Status label
    m_statusLabel = new QLabel("");
    m_statusLabel->setAlignment(Qt::AlignCenter);
    m_statusLabel->setStyleSheet("color: #666; font-style: italic; padding: 8px;");
    mainLayout->addWidget(m_statusLabel);
}

void ConvertTab::toggleFormat(const QString &fmt, bool checked)
{
    if (checked) {
        m_selectedFormats.insert(fmt);
        m_formatButtons[fmt]->setStyleSheet(R"(
            QPushButton:checked { background-color: #3320b5; color: white; }
            QPushButton:hover { background-color: #00838a; }
        )");
    } else {
        m_selectedFormats.remove(fmt);
        m_formatButtons[fmt]->setStyleSheet("QPushButton:hover { background-color: #3498db; }");
    }
    // Re-apply shadow effect as stylesheet might clear it
    applyShadowEffect(m_formatButtons[fmt]);
}

void ConvertTab::addAllFormats()
{
    for (auto it = m_formatButtons.begin(); it != m_formatButtons.end(); ++it) {
        it.value()->setChecked(true);
        toggleFormat(it.key(), true);
    }
}

void ConvertTab::removeAllFormats()
{
    for (auto it = m_formatButtons.begin(); it != m_formatButtons.end(); ++it) {
        it.value()->setChecked(false);
        toggleFormat(it.key(), false);
    }
}

QString ConvertTab::getStartDirectory() const
{
    // Replicates the logic to find the 'data' directory relative to 'Image-Toolkit'
    QDir currentDir(QDir::currentPath());
    while (currentDir.cdUp()) {
        if (currentDir.dirName() == "Image-Toolkit") {
            QString dataPath = currentDir.filePath("data");
            if (QFileInfo(dataPath).isDir()) {
                return dataPath;
            }
            break; // Found it but 'data' doesn't exist, stop.
        }
        if (currentDir.isRoot()) {
            break; // Reached root, stop.
        }
    }
    // Fallback to current working directory
    return QDir::currentPath();
}


void ConvertTab::browseFileInput()
{
    QString filePath = QFileDialog::getOpenFileName(
        this, "Select input file", getStartDirectory(),
        "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
    );
    if (!filePath.isEmpty()) {
        m_inputPath->setText(filePath);
    }
}

void ConvertTab::browseDirectoryInput()
{
    QString directory = QFileDialog::getExistingDirectory(this, "Select input directory", getStartDirectory());
    if (!directory.isEmpty()) {
        m_inputPath->setText(directory);
    }
}

void ConvertTab::browseOutput()
{
    // Try to get a save file name first
    QString filePath = QFileDialog::getSaveFileName(
        this, "Save as...", getStartDirectory(),
        "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)"
    );
    if (!filePath.isEmpty()) {
        m_outputPath->setText(filePath);
        return;
    }
    
    // If user cancelled, try to get an output directory
    QString directory = QFileDialog::getExistingDirectory(
        this, "Select output directory", getStartDirectory()
    );
    if (!directory.isEmpty()) {
        m_outputPath->setText(directory);
    }
}

bool ConvertTab::isValid() const
{
    QString path = m_inputPath->text().trimmed();
    return !path.isEmpty() && QFileInfo::exists(path);
}

void ConvertTab::startConversion()
{
    if (!isValid()) {
        QMessageBox::warning(this, "Invalid Input", "Please select a valid file or directory.");
        return;
    }

    // Clean up old worker if it exists
    if(m_worker) {
        delete m_worker;
        m_worker = nullptr;
    }

    QVariantMap config = collect();
    
    // UI: Switch buttons
    m_runButton->hide();
    m_cancelButton->show();
    m_statusLabel->setText("Starting conversion...");

    m_worker = new ConversionWorker(config);
    
    // Connect signals
    // Using Qt::QueuedConnection for thread safety
    connect(m_worker, &ConversionWorker::finished, this, &ConvertTab::onConversionDone, Qt::QueuedConnection);
    connect(m_worker, &ConversionWorker::error, this, &ConvertTab::onConversionError, Qt::QueuedConnection);
    
    // Clean up worker when done
    connect(m_worker, &QThread::finished, m_worker, &QObject::deleteLater);

    m_worker->start();
}

void ConvertTab::cancelConversion()
{
    if (m_worker && m_worker->isRunning()) {
        m_worker->terminate(); // Forcefully stops the thread
        m_worker->wait(); // Wait for it to finish
        onConversionDone(0, "**Conversion cancelled** by user.");
        QMessageBox::information(this, "Cancelled", "The image conversion has been stopped.");
    }
}

void ConvertTab::onConversionDone(int count, const QString &msg)
{
    // UI: Switch buttons back
    m_runButton->show();
    m_cancelButton->hide();
    m_runButton->setText("Run Conversion");
    m_statusLabel->setText(msg);
    
    // Only show the success box if it wasn't a cancellation
    if (!msg.toLower().contains("cancelled")) {
        QMessageBox::information(this, "Success", msg);
    }

    // Worker is deleted via deleteLater, no need to delete here
    m_worker = nullptr;
}

void ConvertTab::onConversionError(const QString &msg)
{
    // UI: Switch buttons back
    m_runButton->show();
    m_cancelButton->hide();
    m_runButton->setText("Run Conversion");
    m_statusLabel->setText("Conversion failed.");
    QMessageBox::critical(this, "Error", msg);

    // Worker is deleted via deleteLater, no need to delete here
    m_worker = nullptr;
}

QVariantMap ConvertTab::collect() const
{
    QVariantMap config;
    QStringList inputFormatsList;

    if (m_dropdown) {
        if (m_selectedFormats.isEmpty()) {
            inputFormatsList = SUPPORTED_IMG_FORMATS;
        } else {
            inputFormatsList.reserve(m_selectedFormats.size());
            for(const QString& fmt : m_selectedFormats) {
                inputFormatsList.append(fmt);
            }
        }
    } else {
        inputFormatsList = joinListStr(m_inputFormats->text().trimmed());
        if (inputFormatsList.isEmpty()) {
            inputFormatsList = SUPPORTED_IMG_FORMATS;
        }
    }

    // Post-process list: remove dots, set to lower
    for (QString &fmt : inputFormatsList) {
        fmt = fmt.trimmed().remove(0, fmt.startsWith('.') ? 1 : 0).toLower();
    }
    inputFormatsList.removeAll(QString("")); // Remove any empty strings

    QString outPath = m_outputPath->text().trimmed();

    config["output_format"] = m_outputFormat->text().trimmed().isEmpty() ? "png" : m_outputFormat->text().trimmed();
    config["input_path"] = m_inputPath->text().trimmed();
    config["output_path"] = outPath.isEmpty() ? QVariant() : outPath; // Use QVariant for null
    config["input_formats"] = inputFormatsList;
    config["delete"] = m_deleteCheckbox->isChecked();
    
    return config;
}

QStringList ConvertTab::joinListStr(const QString &text) const
{
    // Replaces commas with spaces, then splits by whitespace, skipping empty parts
    QString temp = text;
    temp.replace(',', ' ');
    return temp.split(' ', Qt::SkipEmptyParts);
}

void ConvertTab::applyShadowEffect(QWidget* widget, const QString& colorHex, int radius, int xOffset, int yOffset)
{
    QGraphicsDropShadowEffect *effect = new QGraphicsDropShadowEffect();
    effect->setColor(QColor(colorHex));
    effect->setBlurRadius(radius);
    effect->setXOffset(xOffset);
    effect->setYOffset(yOffset);
    widget->setGraphicsEffect(effect);
}