#pragma once

#include <QScrollArea>
#include <QSet>
#include <QString>
#include <QPoint>

class QRubberBand;
class QMouseEvent;

class MarqueeScrollArea : public QScrollArea
{
    Q_OBJECT

public:
    explicit MarqueeScrollArea(QWidget* parent = nullptr);

signals:
    void selectionChanged(const QSet<QString>& selectedPaths, bool isCtrlPressed);

protected:
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;

private:
    QRubberBand* m_rubberBand;
    QPoint m_origin;
    QSet<QString> m_lastSelectedPaths;
};