#include "OptionalField.h"
#include <QPushButton>
#include <QLabel>
#include <QFrame>
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QApplication>
#include <QPalette>
#include <QGraphicsDropShadowEffect>
#include <QEvent>
#include <QMouseEvent>

OptionalField::OptionalField(const QString& title, QWidget* innerWidget, bool startOpen, QWidget* parent)
    : QWidget(parent), m_innerWidget(innerWidget)
{
    m_innerWidget->setVisible(startOpen);

    // Header bar
    m_toggleBtn = new QPushButton(startOpen ? "➖" : "➕");
    m_toggleBtn->setObjectName("OptionalFieldToggleBtn");
    m_toggleBtn->setFixedWidth(30);
    m_toggleBtn->setFlat(true);

    // Replacing apply_shadow_effect with QGraphicsDropShadowEffect
    QGraphicsDropShadowEffect* shadow = new QGraphicsDropShadowEffect;
    shadow->setColor(QColor("#000000"));
    shadow->setBlurRadius(8);
    shadow->setOffset(0, 3);
    m_toggleBtn->setGraphicsEffect(shadow);


    m_label = new QLabel(title);
    m_label->setAlignment(Qt::AlignLeft | Qt::AlignVCenter);

    QHBoxLayout* headerLayout = new QHBoxLayout();
    headerLayout->setContentsMargins(6, 3, 6, 3);
    headerLayout->addWidget(m_toggleBtn);
    headerLayout->addWidget(m_label);
    headerLayout->addStretch(1);

    m_headerFrame = new QFrame(); // Assign to member
    m_headerFrame->setLayout(headerLayout);
    m_headerFrame->setFrameShape(QFrame::Box);

    // Adaptive color based on theme
    QPalette palette = QApplication::palette();
    QColor baseColor = palette.color(QPalette::Base);
    QColor textColor = palette.color(QPalette::Text);
    QColor borderColor = palette.color(QPalette::Mid);
    QColor hoverColor = baseColor.value() < 128 ? baseColor.lighter(110) : baseColor.darker(110);

    // Apply the style to the QFrame
    m_headerFrame->setStyleSheet(QString(R"(
        QFrame {
            background-color: %1;
            border: 1px solid %2;
            border-radius: 3px;
        }
        QLabel {
            color: %3;
            font-weight: 600;
        }
        QPushButton#OptionalFieldToggleBtn {
            color: %3;
            background-color: transparent;
            border: none;
            padding: 0;
            font-size: 14px;
        }
        QPushButton#OptionalFieldToggleBtn:hover {
            color: %4;
            background-color: transparent;
        }
        QFrame:hover {
            background-color: %4;
        }
    )").arg(baseColor.name(), borderColor.name(), textColor.name(), hoverColor.name()));

    // Main layout
    QVBoxLayout* mainLayout = new QVBoxLayout();
    mainLayout->setContentsMargins(0, 0, 0, 0);
    mainLayout->setSpacing(0);
    mainLayout->addWidget(m_headerFrame);
    mainLayout->addWidget(m_innerWidget);
    setLayout(mainLayout);

    // Connect toggles
    connect(m_toggleBtn, &QPushButton::clicked, this, &OptionalField::toggle);
    // Install event filter on header frame to catch clicks
    m_headerFrame->installEventFilter(this);
}

bool OptionalField::eventFilter(QObject* watched, QEvent* event)
{
    // C++ equivalent of monkey-patched mousePressEvent
    if (watched == m_headerFrame && event->type() == QEvent::MouseButtonPress) {
        // Check if the click was on the button itself to avoid double-toggling
        QMouseEvent* mouseEvent = static_cast<QMouseEvent*>(event);
        if (!m_toggleBtn->geometry().contains(mouseEvent->pos())) {
            toggle();
            return true; // Event handled
        }
    }
    return QWidget::eventFilter(watched, event);
}

void OptionalField::toggle()
{
    bool visible = !m_innerWidget->isVisible();
    m_innerWidget->setVisible(visible);
    m_toggleBtn->setText(visible ? "➖" : "➕");
}