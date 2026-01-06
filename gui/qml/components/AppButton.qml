import QtQuick 2.15
import QtQuick.Controls 2.15
import "../"

Button {
    id: control
    text: "Button"
    
    contentItem: Text {
        text: control.text
        font.family: Style.fontFamily
        font.pixelSize: Style.fontSize
        font.bold: true
        color: "white"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        implicitWidth: 100
        implicitHeight: 40
        color: control.pressed ? Style.accentPressed : 
               control.hovered ? Style.accentHover : Style.accent
        radius: Style.borderRadius
    }
}
