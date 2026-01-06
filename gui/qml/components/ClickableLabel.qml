import QtQuick 2.15
import QtQuick.Controls 2.15
import "../"

Text {
    id: root
    property string path: ""
    signal pathClicked(string path)
    signal pathDoubleClicked(string path)
    signal pathRightClicked(point pos, string path)

    color: mouseArea.containsMouse ? Style.accent : Style.text
    font.pixelSize: 14
    elide: Text.ElideRight
    
    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        
        onClicked: {
            if (mouse.button === Qt.LeftButton) {
                root.pathClicked(root.path)
            } else if (mouse.button === Qt.RightButton) {
                root.pathRightClicked(Qt.point(mouse.x, mouse.y), root.path)
            }
        }
        
        onDoubleClicked: {
            if (mouse.button === Qt.LeftButton) {
                root.pathDoubleClicked(root.path)
            }
        }
    }
    
    ToolTip {
        visible: mouseArea.containsMouse
        text: root.path.split('/').pop()
        delay: 500
    }
}

