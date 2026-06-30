/*!
    \qmltype AppButton
    \inqmlmodule ImageToolkit.Components
    \brief Styled accent-colour push button.

    AppButton extends \l Button with Image Toolkit's accent palette.  The
    background lightens on hover and darkens on press.  Default size is
    100 × 40 px.

    \qmlproperty string AppButton::text
    Label displayed on the button face.  Defaults to \c "Button".
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import "../"

Button {
    id: control
    text: "Button"
    
    contentItem: Text {
        text: control.text
        font: control.font
        color: Style.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        implicitWidth: 100
        implicitHeight: 40
        color: control.pressed ? Qt.darker(Style.accent, 1.2) : (control.hovered ? Qt.lighter(Style.accent, 1.1) : Style.accent)
        border.color: Style.border
        border.width: 1
        radius: Style.borderRadius
    }
}

