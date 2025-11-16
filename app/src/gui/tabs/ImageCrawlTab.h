#pragma once

#include <QtWidgets>
#include "tabs/BaseTab.h"

// Forward declarations
class QLineEdit;
class QPushButton;
class QComboBox;
class QCheckBox;
class QProgressBar;
class QLabel;
class ImageCrawlWorker;
class OptionalField;

class ImageCrawlTab : public BaseTab {
    Q_OBJECT

public:
    explicit ImageCrawlTab(bool dropdown = true, QWidget *parent = nullptr);
    ~ImageCrawlTab() override;

private slots:
    void browseDownloadDirectory();
    void browseScreenshotDirectory();
    void startCrawl();
    void cancelCrawl();
    void onCrawlDone(int count, const QString &message);
    void onCrawlError(const QString &msg);

private:
    QString getInitialDirectory();
    QVariantMap collectConfig();

    bool m_dropdown;
    ImageCrawlWorker *m_worker = nullptr;
    QString m_lastBrowsedDownloadDir;
    QString m_lastBrowsedScreenshotDir;

    // UI Members
    QLineEdit *m_urlInput;
    QLineEdit *m_replaceStrInput;
    QLineEdit *m_replacementsInput;
    QLineEdit *m_downloadDirPath;
    QLineEdit *m_screenshotDirPath;
    QLineEdit *m_skipFirstInput;
    QLineEdit *m_skipLastInput;
    QPushButton *m_runButton;
    QPushButton *m_cancelButton;
    QComboBox *m_browserCombo;
    QCheckBox *m_headlessCheckbox;
    OptionalField *m_screenshotField;
    QLabel *m_statusLabel;
    QProgressBar *m_progressBar;
    QWidget *m_buttonContainer;
};