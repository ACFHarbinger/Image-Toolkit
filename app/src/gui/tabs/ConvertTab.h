#ifndef CONVERT_TAB_H
#define CONVERT_TAB_H

#include <QWidget>
#include <QSet>
#include <QMap>
#include <QStringList>
#include <QVariantMap>

#include "BaseTab.h" // Assumed base class
#include "helpers/ConversionWorker.h" // Stubbed worker thread
#include "components/OptionalField.h" // Recreated OptionalField widget

// Forward declarations for Qt classes
class QLineEdit;
class QPushButton;
class QCheckBox;
class QLabel;
class QGroupBox;

class ConvertTab : public BaseTab
{
    Q_OBJECT

public:
    explicit ConvertTab(bool dropdown = true, QWidget *parent = nullptr);
    ~ConvertTab(); // Add a destructor to clean up the worker

private slots:
    // File dialog slots
    void browseFileInput();
    void browseDirectoryInput();
    void browseOutput();

    // Format selection slots (for dropdown=true)
    void toggleFormat(const QString &fmt, bool checked);
    void addAllFormats();
    void removeAllFormats();

    // Conversion control slots
    void startConversion();
    void cancelConversion();

    // Worker result slots
    void onConversionDone(int count, const QString &msg);
    void onConversionError(const QString &msg);

private:
    void setupUi();
    bool isValid() const;
    QVariantMap collect() const;
    QStringList joinListStr(const QString &text) const;
    void applyShadowEffect(QWidget* widget, const QString& colorHex = "#000000", int radius = 8, int xOffset = 0, int yOffset = 3);
    QString getStartDirectory() const;

    // --- Member Variables ---
    bool m_dropdown;
    ConversionWorker *m_worker;

    // --- UI Elements ---
    // Target Group
    QLineEdit *m_inputPath;

    // Settings Group
    QLineEdit *m_outputFormat;
    QLineEdit *m_outputPath;
    OptionalField *m_outputField; // for dropdown=true
    
    // Input formats (conditional)
    OptionalField *m_formatsField; // for dropdown=true
    QMap<QString, QPushButton*> m_formatButtons;
    QSet<QString> m_selectedFormats;
    QPushButton *m_btnAddAll;
    QPushButton *m_btnRemoveAll;
    
    QLineEdit *m_inputFormats; // for dropdown=false

    QCheckBox *m_deleteCheckbox;

    // Buttons & Status
    QWidget *m_buttonContainer;
    QPushButton *m_runButton;
    QPushButton *m_cancelButton;
    QLabel *m_statusLabel;
};

#endif // CONVERT_TAB_H