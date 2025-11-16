#pragma once

#include <QtWidgets>
#include "tabs/BaseTab.h"
#include <QSet>
#include <QMap>

// Forward declarations
class QLineEdit;
class QPushButton;
class QCheckBox;
class QLabel;
class OptionalField;
class DeletionWorker;

class DeleteTab : public BaseTab {
    Q_OBJECT

public:
    explicit DeleteTab(bool dropdown = true, QWidget *parent = nullptr);
    ~DeleteTab() override;

private slots:
    void browseFile();
    void browseDirectory();
    void startDeletion(const QString &mode);
    void toggleExtension(const QString &ext, bool checked);
    void addAllExtensions();
    void removeAllExtensions();
    void handleConfirmationRequest(const QString &message, int totalItems);
    void updateProgress(int deleted, int total);
    void onDeletionDone(int count, const QString &msg);
    void onDeletionError(const QString &msg);

private:
    bool isValid(const QString &mode);
    QString getStartingDir();
    QVariantMap collect(const QString &mode);
    QStringList joinListStr(const QString &text);

    bool m_dropdown;
    DeletionWorker *m_worker = nullptr;

    // UI Members
    QLineEdit *m_targetPath;
    QLineEdit *m_targetExtensions = nullptr; // Only if not dropdown
    QCheckBox *m_confirmCheckbox;
    QPushButton *m_btnDeleteFiles;
    QPushButton *m_btnDeleteDirectory;
    QLabel *m_statusLabel;

    // Dropdown-specific UI
    OptionalField *m_extensionsField = nullptr;
    QMap<QString, QPushButton *> m_extensionButtons;
    QSet<QString> m_selectedExtensions;
};