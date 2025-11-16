#pragma once

#include <QWidget>
#include <QCloseEvent>

class QTextEdit;

/**
 * @brief A dedicated window to display the synchronization log.
 * Hides on close instead of deleting.
 */
class LogWindow : public QWidget
{
    Q_OBJECT

public:
    explicit LogWindow(QWidget* parent = nullptr);

public slots:
    void appendLog(const QString& text);
    void clearLog();

protected:
    void closeEvent(QCloseEvent* event) override;

private:
    QTextEdit* m_logOutput;
};