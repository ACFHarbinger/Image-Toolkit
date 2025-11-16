#pragma once

#include <QWidget>

class QPushButton;
class QLabel;
class QFrame;
class QEvent;

class OptionalField : public QWidget
{
    Q_OBJECT

public:
    explicit OptionalField(const QString& title, QWidget* innerWidget, bool startOpen = false, QWidget* parent = nullptr);

protected:
    // Used to catch clicks on the header frame
    bool eventFilter(QObject* watched, QEvent* event) override;

private slots:
    void toggle();

private:
    QWidget* m_innerWidget;
    QPushButton* m_toggleBtn;
    QLabel* m_label;
    QFrame* m_headerFrame; // Must be a member to install event filter
};