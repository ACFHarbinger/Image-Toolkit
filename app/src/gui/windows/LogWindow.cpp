#include "LogWindow.h"

#include <QVBoxLayout>
#include <QTextEdit>
#include <QCloseEvent>

LogWindow::LogWindow(QWidget *parent)
    : QWidget(parent, Qt::Window) // Qt::Window flag makes it a separate window
{
    setWindowTitle("Synchronization Status Log");
    setGeometry(100, 100, 700, 500);

    QVBoxLayout *main_layout = new QVBoxLayout(this); // 'this' sets parent
    
    log_output = new QTextEdit;
    log_output->setReadOnly(true);
    log_output->setStyleSheet("background:#1e1e1e; color:#b9bbbe; border:none; font-family: monospace;");

    main_layout->addWidget(log_output);
    
    // No explicit setLayout(main_layout) needed, as it was parented to 'this'
}

void LogWindow::append_log(const QString &text)
{
    log_output->append(text);
}

void LogWindow::clear_log()
{
    log_output->clear();
}

void LogWindow::closeEvent(QCloseEvent *event)
{
    // Instead of closing, just hide the window
    this->hide();
    event->ignore(); // Tell Qt we've handled this event
}