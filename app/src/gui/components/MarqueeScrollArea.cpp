#include "MarqueeScrollArea.h"
#include "ClickableLabel.h" // Include the ClickableLabel header
#include <QRubberBand>
#include <QMouseEvent>
#include <QApplication>
#include <QScrollBar>
#include <QWidget>
#include <QRect>

MarqueeScrollArea::MarqueeScrollArea(QWidget* parent)
    : QScrollArea(parent)
{
    // Rubber band MUST be a child of the viewport
    m_rubberBand = new QRubberBand(QRubberBand::Rectangle, viewport());
    m_origin = QPoint();
}

void MarqueeScrollArea::mousePressEvent(QMouseEvent* event)
{
    QWidget* contentWidget = widget();
    if (!contentWidget) {
        QScrollArea::mousePressEvent(event);
        return;
    }

    // Map viewport click position to content widget position
    QPoint mappedPos = contentWidget->mapFrom(viewport(), event->pos());
    // Check if a child (a label) exists at that *mapped* position
    QWidget* child = contentWidget->childAt(mappedPos);

    if (event->button() == Qt::LeftButton && child == nullptr) {
        // Click is on the background
        m_origin = event->pos(); // Store viewport coords
        m_rubberBand->setGeometry(QRect(m_origin, QSize()));
        m_rubberBand->show();
        m_lastSelectedPaths.clear();
        event->accept();
    } else {
        // Click is on a child OR is not a left-click.
        QScrollArea::mousePressEvent(event);
    }
}

void MarqueeScrollArea::mouseMoveEvent(QMouseEvent* event)
{
    if (m_rubberBand->isVisible()) {
        // 1. Update geometry in viewport coordinates
        m_rubberBand->setGeometry(QRect(m_origin, event->pos()).normalized());

        // 2. Get selection rect (in viewport coordinates)
        QRect selectionRectViewport = m_rubberBand->geometry();

        // 3. Translate viewport rect to content widget coordinates
        int hOffset = horizontalScrollBar()->value();
        int vOffset = verticalScrollBar()->value();
        QRect selectionRectContent = selectionRectViewport.translated(hOffset, vOffset);

        // 4. Find selected paths
        QSet<QString> currentSelectedPaths;
        QWidget* contentWidget = widget();
        if (!contentWidget) {
            QScrollArea::mouseMoveEvent(event);
            return;
        }

        // Find all ClickableLabel children
        QList<ClickableLabel*> labels = contentWidget->findChildren<ClickableLabel*>();
        for (ClickableLabel* label : labels) {
            // Check intersection using content coordinates
            if (selectionRectContent.intersects(label->geometry())) {
                currentSelectedPaths.insert(label->path());
            }
        }

        // 5. Check for Ctrl key
        Qt::KeyboardModifiers mods = QApplication::keyboardModifiers();
        bool isCtrlPressed = (mods & Qt::ControlModifier);

        // 6. Optimization: Emit only if selection changed
        if (currentSelectedPaths != m_lastSelectedPaths) {
            emit selectionChanged(currentSelectedPaths, isCtrlPressed);
            m_lastSelectedPaths = currentSelectedPaths;
        }

        event->accept();
    } else {
        QScrollArea::mouseMoveEvent(event);
    }
}

void MarqueeScrollArea::mouseReleaseEvent(QMouseEvent* event)
{
    if (event->button() == Qt::LeftButton && m_rubberBand->isVisible()) {
        m_rubberBand->hide();
        m_lastSelectedPaths.clear(); // Clear cache on release
        event->accept();
    } else {
        QScrollArea::mouseReleaseEvent(event);
    }
}